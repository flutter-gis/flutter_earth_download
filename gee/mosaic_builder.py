"""
Mosaic building logic - combines images from multiple satellites using quality-based selection.
"""
import logging
from datetime import datetime
from typing import Tuple, Optional, List
from collections import Counter
import ee

from .config import TARGET_RES, MAX_IMAGES_PER_SATELLITE
from .utils import lonlat_to_utm_zone, is_satellite_operational
from .ee_collections import (
    sentinel_collection, sentinel_cloudprob_collection, add_s2_cloudprob,
    landsat_collections, modis_collection, aster_collection, viirs_collection,
    spot_collection, landsat_mss_collections, noaa_avhrr_collection
)
from .cloud_detection import estimate_cloud_fraction, estimate_modis_cloud_fraction
from .image_preparation import (
    s2_prepare_image, landsat_prepare_image, prepare_modis_image,
    prepare_aster_image, prepare_viirs_image, harmonize_image,
    prepare_spot_image, prepare_landsat_mss_image, prepare_noaa_avhrr_image
)
from .quality_scoring import compute_quality_score, check_band_completeness
from .optimization_helpers import (
    get_cached_band_names, batch_fetch_metadata, extract_metadata_parallel
)


def standardize_raw_bands_for_collection(img):
    """
    Standardize RAW bands only (no indices) to ensure all images have the same band structure.
    This is called BEFORE adding images to the collection, so qualityMosaic can fill missing bands
    from fallback images. Returns image with standardized raw band names: B4, B3, B2, B8, B11, B12, quality
    Missing bands are filled with zeros (will be filled by qualityMosaic from fallback images).
    """
    try:
        band_names = img.bandNames().getInfo()
        standardized_bands = []
        
        # Only raw bands - NO indices yet (indices created AFTER mosaic is unified)
        required_bands = {
            "B4": None,  # Red
            "B3": None,  # Green
            "B2": None,  # Blue
            "B8": None,  # NIR
            "B11": None, # SWIR1
            "B12": None, # SWIR2
        }
        
        # Detect satellite type by checking band names
        has_sr_b1 = "SR_B1" in band_names  # Landsat 4/5
        has_xs = any("XS" in b for b in band_names)  # SPOT 1-3
        has_spot4 = any(b in ["B1", "B2", "B3", "MIR"] for b in band_names) and not has_sr_b1  # SPOT 4 (but not Landsat)
        has_mss = any("SR_B" in b for b in band_names) and len([b for b in band_names if "SR_B" in b]) <= 4  # MSS has fewer bands
        # Also check for raw MSS bands (B1-B4 without SR prefix in some collections)
        is_mss_raw = all(b in band_names for b in ["B1", "B2", "B3", "B4"]) and "SR_B" not in str(band_names)
        
        # Map existing bands to standard names
        if has_xs or has_spot4:
            # SPOT satellites: XS1/B1=Green, XS2/B2=Red, XS3/B3=NIR, MIR=SWIR (SPOT 4 only)
            if has_xs:
                band_mapping = {
                    "XS1": "B3",  # Green
                    "XS2": "B4",  # Red
                    "XS3": "B8",  # NIR
                }
            else:  # SPOT 4
                band_mapping = {
                    "B1": "B3",   # Green
                    "B2": "B4",   # Red
                    "B3": "B8",   # NIR
                    "MIR": "B11", # SWIR1
                }
            # SPOT doesn't have blue band - will be filled with placeholder
        elif has_mss or is_mss_raw:
            # Landsat MSS: Band 4/1=Green, Band 5/2=Red, Band 6/3=NIR, Band 7/4=NIR2 (used as SWIR)
            if has_mss:
                band_mapping = {
                    "SR_B1": "B3",  # Green
                    "SR_B2": "B4",  # Red
                    "SR_B3": "B8",  # NIR
                    "SR_B4": "B11", # NIR2 used as SWIR approximation
                }
            else:  # Raw MSS bands
                band_mapping = {
                    "B1": "B3",  # Green
                    "B2": "B4",  # Red
                    "B3": "B8",  # NIR
                    "B4": "B11", # NIR2 used as SWIR approximation
                }
            # MSS doesn't have blue band - will be filled with placeholder
        elif has_sr_b1:
            # Landsat 4/5 Collection 2: SR_B1=Blue, SR_B2=Green, SR_B3=Red, SR_B4=NIR, SR_B5=SWIR1, SR_B7=SWIR2
            band_mapping = {
                # RGB bands
                "SR_B1": "B2",  # Blue
                "SR_B2": "B3",  # Green
                "SR_B3": "B4",  # Red
                # IR bands
                "SR_B4": "B8",  # NIR
                "SR_B5": "B11", # SWIR1
                "SR_B7": "B12", # SWIR2
            }
        else:
            # Landsat 8/9 Collection 2: SR_B2=Blue, SR_B3=Green, SR_B4=Red, SR_B5=NIR, SR_B6=SWIR1, SR_B7=SWIR2
            band_mapping = {
                # RGB bands
                "SR_B4": "B4", "SR_B3": "B3", "SR_B2": "B2",
                # IR bands
                "SR_B5": "B8", "SR_B6": "B11", "SR_B7": "B12",
            }
        
        # Collect existing bands
        for band_name in band_names:
            if band_name in required_bands:
                required_bands[band_name] = img.select(band_name)
            elif band_name in band_mapping:
                std_name = band_mapping[band_name]
                if required_bands[std_name] is None:
                    required_bands[std_name] = img.select(band_name)
        
        # Special handling for SPOT and MSS - they don't have blue band
        # Create blue band approximation from green for SPOT/MSS
        if (has_xs or has_spot4 or has_mss or is_mss_raw) and required_bands["B2"] is None:
            if required_bands["B3"] is not None:
                # Approximate blue from green (green * 0.85-0.9)
                required_bands["B2"] = required_bands["B3"].multiply(0.875)
        
        # Build standardized image with all required RAW bands in fixed order
        # CRITICAL: Convert all bands to Float type to ensure homogeneous collection
        # Use existing bands where available, zeros where missing (will be filled by qualityMosaic)
        for std_name in ["B4", "B3", "B2", "B8", "B11", "B12"]:
            if required_bands[std_name] is not None:
                # Convert to Float to ensure type consistency across all images
                standardized_bands.append(required_bands[std_name].toFloat().rename(std_name))
            else:
                # Fill missing bands with zeros (qualityMosaic will fill from fallback images)
                # Use Float constant to match type
                # IMPORTANT: Make missing bands fully masked so they don't count as 'valid' in coverage checks
                missing = ee.Image.constant(0.0).toFloat().rename(std_name)
                missing = missing.updateMask(ee.Image(0))  # fully masked placeholder
                standardized_bands.append(missing)
        
        # Combine all standardized bands
        standardized = ee.Image.cat(standardized_bands)
        
        # Preserve the quality band if it exists (required for qualityMosaic)
        # CRITICAL: Ensure quality band is also Float type
        if "quality" in band_names:
            quality_band = img.select("quality")
            # Ensure quality band is Float (it should already be, but ensure it)
            standardized = standardized.addBands(quality_band.toFloat())
        
        return standardized
    except Exception as e:
        logging.warning(f"Error standardizing raw bands, using original image: {e}")
        return img


def add_indices_to_unified_mosaic(mosaic):
    """
    Add all vegetation and water indices to the unified mosaic AFTER bands are filled.
    This is called at the VERY END (after reprojection and clipping) for better performance.
    OPTIMIZED: Minimizes .getInfo() calls by caching band names.
    """
    try:
        # OPTIMIZATION: Cache band names with single .getInfo() call
        band_names = mosaic.bandNames().getInfo()
        has_b8 = "B8" in band_names
        has_b4 = "B4" in band_names
        has_b3 = "B3" in band_names
        has_b2 = "B2" in band_names
        has_b11 = "B11" in band_names
        
        indices = []
        
        # NDVI: (NIR - Red) / (NIR + Red)
        if has_b8 and has_b4:
            ndvi = mosaic.normalizedDifference(["B8", "B4"]).rename("NDVI")
            indices.append(ndvi)
        
        # NDWI: (Green - NIR) / (Green + NIR) - standard water index
        if has_b3 and has_b8:
            ndwi = mosaic.normalizedDifference(["B3", "B8"]).rename("NDWI")
            indices.append(ndwi)
        
        # MNDWI: (Green - SWIR1) / (Green + SWIR1) - better for water detection
        if has_b3 and has_b11:
            mndwi = mosaic.normalizedDifference(["B3", "B11"]).rename("MNDWI")
            indices.append(mndwi)
        
        # EVI: 2.5 * ((NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1))
        if has_b8 and has_b4 and has_b2:
            nir = mosaic.select("B8")
            red = mosaic.select("B4")
            blue = mosaic.select("B2")
            evi = nir.subtract(red).divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)).multiply(2.5).rename("EVI")
            indices.append(evi)
        
        # SAVI: ((NIR - Red) / (NIR + Red + L)) * (1 + L), where L = 0.5
        if has_b8 and has_b4:
            nir = mosaic.select("B8")
            red = mosaic.select("B4")
            L = 0.5
            savi = nir.subtract(red).divide(nir.add(red).add(L)).multiply(1 + L).rename("SAVI")
            indices.append(savi)
        
        # FVI: Floating Vegetation Index (NIR - SWIR1) / (NIR + SWIR1)
        if has_b8 and has_b11:
            fvi = mosaic.normalizedDifference(["B8", "B11"]).rename("FVI")
            indices.append(fvi)
        
        # If no indices were created, return original mosaic
        if not indices:
            return mosaic
        
        # Add all indices at once
        mosaic_with_indices = mosaic.addBands(indices)
        
        # AVI: Aquatic Vegetation Index (requires NDVI and water index)
        # OPTIMIZATION: Only check for AVI if we have NDVI (which we just added)
        if has_b8 and has_b4:  # NDVI exists
            # Use cached band check - MNDWI or NDWI should be in indices if bands exist
            has_mndwi = has_b3 and has_b11
            has_ndwi = has_b3 and has_b8
            
            if has_mndwi or has_ndwi:
                ndvi_band = mosaic_with_indices.select("NDVI")
                # Use MNDWI if available, otherwise NDWI
                if has_mndwi:
                    water_idx = mosaic_with_indices.select("MNDWI").abs()
                else:
                    water_idx = mosaic_with_indices.select("NDWI").abs()
                
                water_mask = water_idx.lt(0.3)  # Moderate water presence
                avi = ndvi_band.multiply(water_mask).multiply(water_idx.multiply(-1).add(1)).rename("AVI")
                return mosaic_with_indices.addBands(avi)
        
        return mosaic_with_indices
    except Exception as e:
        logging.warning(f"Error adding indices to unified mosaic: {e}")
        return mosaic


def build_best_mosaic_for_tile(tile_bounds: Tuple[float, float, float, float], 
                            start: str, end: str, 
                            include_l7: bool = False, 
                            enable_harmonize: bool = True,
                            include_s2: bool = True,
                            include_landsat: bool = True,
                            include_modis: bool = True, 
                            include_aster: bool = True, 
                            include_viirs: bool = True,
                            include_spot: bool = True,
                            include_mss: bool = True,
                            include_noaa: bool = True,
                            tile_idx: Optional[int] = None, 
                            test_callback=None,
                            server_mode: bool = False,
                            tile_geometry=None):
    """
    Build best mosaic using two-phase approach:
    1. Find 3 excellent images (quality > 0.85) - stop searching early
    2. Create initial mosaic and identify missing pixels
    3. Find minimal high-quality patches to fill only the gaps
    
    This ensures no blank areas while minimizing processing time.
    
    Args:
        tile_geometry: Optional Shapely Polygon - if provided, uses this instead of bounds rectangle
    """
    import ee
    from shapely.geometry import mapping
    
    # Use provided geometry if available, otherwise create rectangle from bounds
    if tile_geometry is not None:
        # Convert Shapely polygon to Earth Engine geometry
        geom_dict = mapping(tile_geometry)
        # Extract coordinates from GeoJSON format
        if geom_dict['type'] == 'Polygon':
            coords = geom_dict['coordinates'][0]  # First ring (exterior)
            # Convert to Earth Engine format: list of [lon, lat] pairs
            geom = ee.Geometry.Polygon(coords)
        else:
            # Fallback to bounds rectangle
            lon_min, lat_min, lon_max, lat_max = tile_bounds
            geom = ee.Geometry.Polygon([[lon_min, lat_min], [lon_min, lat_max], 
                                        [lon_max, lat_max], [lon_max, lat_min], 
                                        [lon_min, lat_min]])
    else:
        # Use rectangular bounds
        lon_min, lat_min, lon_max, lat_max = tile_bounds
        geom = ee.Geometry.Polygon([[lon_min, lat_min], [lon_min, lat_max], 
                                    [lon_max, lat_max], [lon_max, lat_min], 
                                    [lon_min, lat_min]])
    
    start_date = datetime.fromisoformat(start)
    end_date = datetime.fromisoformat(end)
    max_days = (end_date - start_date).days if end_date > start_date else 365
    
    # Determine satellite availability for the requested date range up-front
    # This prevents querying collections that cannot have data for this month
    try:
        if include_s2 and not is_satellite_operational("SENTINEL_2", start, end):
            include_s2 = False
            if tile_idx is None or int(tile_idx) == 0:
                logging.debug("Skipping Sentinel-2 entirely for this month (out of operational range)")
        if include_modis:
            # MODIS has two platforms; operational check is handled inside collection helpers too,
            # but we still gate here for clarity and early exit logging.
            modis_any = is_satellite_operational("MODIS_TERRA", start, end) or is_satellite_operational("MODIS_AQUA", start, end)
            if not modis_any:
                include_modis = False
                if tile_idx is None or int(tile_idx) == 0:
                    logging.debug("Skipping MODIS entirely for this month (out of operational range)")
        if include_aster and not is_satellite_operational("ASTER", start, end):
            include_aster = False
            if tile_idx is None or int(tile_idx) == 0:
                logging.debug("Skipping ASTER entirely for this month (out of operational range)")
        if include_viirs and not is_satellite_operational("VIIRS", start, end):
            include_viirs = False
            if tile_idx is None or int(tile_idx) == 0:
                logging.debug("Skipping VIIRS entirely for this month (out of operational range)")
        # SPOT: Check if any SPOT satellite was operational
        if include_spot:
            spot_any = (is_satellite_operational("SPOT_1", start, end) or
                        is_satellite_operational("SPOT_2", start, end) or
                        is_satellite_operational("SPOT_3", start, end) or
                        is_satellite_operational("SPOT_4", start, end))
            if not spot_any:
                include_spot = False
                if tile_idx is None or int(tile_idx) == 0:
                    logging.debug("Skipping SPOT entirely for this month (out of operational range)")
        # Landsat MSS: Check if any MSS satellite was operational
        if include_mss:
            mss_any = (is_satellite_operational("LANDSAT_1_MSS", start, end) or
                       is_satellite_operational("LANDSAT_2_MSS", start, end) or
                       is_satellite_operational("LANDSAT_3_MSS", start, end))
            if not mss_any:
                include_mss = False
                if tile_idx is None or int(tile_idx) == 0:
                    logging.debug("Skipping Landsat MSS entirely for this month (out of operational range)")
        # NOAA AVHRR: Only check operational status, but don't skip it (it's last resort)
        # We'll check if it's needed later (only if prepared list is empty)
        if include_noaa and not is_satellite_operational("NOAA_AVHRR", start, end):
            include_noaa = False
            if tile_idx is None or int(tile_idx) == 0:
                logging.debug("Skipping NOAA AVHRR entirely for this month (out of operational range)")
    except Exception:
        # If operational checks fail for any reason, fall back to original include_* flags
        pass
    
    # Helper: safe tile index formatting for logs (defined early for use in pre-check)
    def _fmt_idx(idx):
        try:
            return f"{int(idx):04d}"
        except Exception:
            return "????"
    
    # Early exit if nothing to process for this date range
    # Note: NOAA is not included here because it's only used as last resort when prepared list is empty
    if not (include_s2 or include_landsat or include_modis or include_aster or include_viirs or include_spot or include_mss or include_noaa):
        logging.debug(f"[Tile {_fmt_idx(tile_idx) if tile_idx is not None else '????'}] No operational satellites for {start} to {end}.")
        return None
    
    # PRE-CHECK: Count total available images across ALL satellites to determine threshold strategy
    # This allows us to set appropriate thresholds upfront instead of waiting to test multiple images
    total_available_images = 0
    try:
        if include_s2:
            try:
                s2_col_temp = sentinel_collection(start, end)
                if s2_col_temp is not None:
                    s2_col_temp = s2_col_temp.filterBounds(geom)
                    s2_count_temp = int(s2_col_temp.size().getInfo())
                    total_available_images += s2_count_temp
            except Exception as e:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting Sentinel-2 images: {e}")
        
        if include_landsat:
            try:
                landsat_cols_temp = landsat_collections(start, end)
                for key, col_temp in landsat_cols_temp.items():
                    try:
                        col_temp = col_temp.filterBounds(geom)
                        count_temp = int(col_temp.size().getInfo())
                        total_available_images += count_temp
                    except Exception as e:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting {key} images: {e}")
            except Exception as e:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting Landsat images: {e}")
        
        if include_modis:
            try:
                modis_col_temp = modis_collection(start, end)
                if modis_col_temp is not None:
                    modis_col_temp = modis_col_temp.filterBounds(geom)
                    modis_count_temp = int(modis_col_temp.size().getInfo())
                    total_available_images += modis_count_temp
            except Exception as e:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting MODIS images: {e}")
        
        if include_aster:
            try:
                aster_col_temp = aster_collection(start, end)
                if aster_col_temp is not None:
                    aster_col_temp = aster_col_temp.filterBounds(geom)
                    aster_count_temp = int(aster_col_temp.size().getInfo())
                    total_available_images += aster_count_temp
            except Exception as e:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting ASTER images: {e}")
        
        if include_viirs:
            try:
                viirs_col_temp = viirs_collection(start, end)
                if viirs_col_temp is not None:
                    viirs_col_temp = viirs_col_temp.filterBounds(geom)
                    viirs_count_temp = int(viirs_col_temp.size().getInfo())
                    total_available_images += viirs_count_temp
            except Exception as e:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting VIIRS images: {e}")
        
        if include_spot:
            try:
                spot_col_temp = spot_collection(start, end)
                if spot_col_temp is not None:
                    spot_col_temp = spot_col_temp.filterBounds(geom)
                    spot_count_temp = int(spot_col_temp.size().getInfo())
                    total_available_images += spot_count_temp
            except Exception as e:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting SPOT images: {e}")
        
        if include_mss:
            try:
                mss_cols_temp = landsat_mss_collections(start, end)
                for key, col_temp in mss_cols_temp.items():
                    try:
                        col_temp = col_temp.filterBounds(geom)
                        count_temp = int(col_temp.size().getInfo())
                        total_available_images += count_temp
                    except Exception as e:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting {key} images: {e}")
            except Exception as e:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error counting Landsat MSS images: {e}")
        
        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Total available images across all satellites: {total_available_images}")
    except Exception as e:
        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error during image count pre-check: {e}")
        # Continue with default strategy if count fails
        total_available_images = 100  # Default to conservative strategy
    
    # Determine threshold lowering strategy based on total available images
    # If we have very few images (<= 3), lower thresholds aggressively after first image
    # If we have more images, we can afford to test more before lowering
    if total_available_images <= 3:
        MIN_TESTS_BEFORE_LOWERING = 1  # Lower immediately after first image
    elif total_available_images <= 10:
        MIN_TESTS_BEFORE_LOWERING = 2  # Lower after 2 images
    else:
        MIN_TESTS_BEFORE_LOWERING = 3  # Lower after 3 images (default)
    
    # TWO-PHASE APPROACH: Find best 3 images from EACH satellite, then select best overall and fill gaps
    # Server mode: Process more images for higher quality
    EXCELLENT_QUALITY_THRESHOLD = 0.85  # Quality threshold for "excellent" images
    TARGET_EXCELLENT_PER_SATELLITE = 5 if server_mode else 3  # Server mode: 5 excellent images per satellite
    MAX_IMAGES_TO_PROCESS = MAX_IMAGES_PER_SATELLITE * 2 if server_mode else MAX_IMAGES_PER_SATELLITE  # Server mode: process 2x images
    prepared = []  # Images to use in mosaic
    prepared_timestamps = []  # Track timestamps for prepared images (to avoid API calls in gap-filling)
    prepared_excellent = []  # Track excellent images separately (best from all satellites)
    
    # Log which sensors are enabled for this tile/month (helps diagnose unexpected skips)
    try:
        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Sensors enabled: "
                      f"S2={include_s2}, Landsat={include_landsat}, MODIS={include_modis}, "
                      f"ASTER={include_aster}, VIIRS={include_viirs}")
    except Exception:
        pass
    satellite_contributions = []  # Track which satellites contributed images to this tile
    satellite_quality_scores = {}  # Track best quality score per satellite (for dominance determination)
    satellite_detailed_stats = {}  # Track detailed statistics per satellite (for debugging/visualization)
    best_image = None  # Track the single best image (highest quality score)
    best_score = -1.0  # Track the best quality score found
    best_satellite_name = None  # Track which satellite the best image came from
    best_detailed_stats = None  # Track detailed stats for the best image
    # Track all images with their stats for fallback ranking (2nd, 3rd, etc. best)
    all_image_stats = []  # List of (image, quality_score, detailed_stats, satellite_name) tuples
    # Track excellent images per satellite (up to 3 per satellite)
    excellent_per_satellite = {}  # Dict: satellite_name -> list of (image, score, stats) tuples
    phase_2_mode = False  # Whether we're in gap-filling phase
    
    # Process Sentinel-2 (skip entire section if not included for this month)
    try:
        if not include_s2:
            if tile_idx is None or int(tile_idx) == 0:
                logging.debug("Skipping Sentinel-2 entirely for this month (out of operational range)")
            raise Exception("include_s2_false_skip")
        s2_col = sentinel_collection(start, end)
        if s2_col is None:
            logging.debug("Skipping Sentinel-2: not operational during requested date range")
        else:
            s2_col = s2_col.filterBounds(geom)
            s2_prob = sentinel_cloudprob_collection(start, end)
            if s2_prob is not None:
                s2_prob = s2_prob.filterBounds(geom)
                try:
                    s2_col = add_s2_cloudprob(s2_col, s2_prob)
                except Exception:
                    pass
            # OPTIMIZATION #2: Pre-filter collection before iteration (server-side filtering)
            # NOTE: Server-side cloud filter removed to allow adaptive cloud thresholds to work
            # We'll filter by cloud percentage client-side with adaptive thresholds
            # OPTIMIZATION: Server-side filtering - sort by cloud probability and take best
            s2_col = s2_col.sort("CLOUDY_PIXEL_PERCENTAGE")
            # Get collection size with error handling for quota/network issues
            try:
                s2_count = int(s2_col.size().getInfo())
            except Exception as e:
                error_msg = str(e)
                # Check for quota errors
                if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                    logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Quota/rate limit error while checking Sentinel-2 collection size: {e}")
                else:
                    logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error checking Sentinel-2 collection size: {e}")
                s2_count = 0
            
            if s2_count == 0:
                logging.debug("No Sentinel-2 images with <20% clouds found")
            else:
                # ADAPTIVE QUALITY THRESHOLD: Start high, lower incrementally until images are found
                # This ensures poor quality images are still used if they're all we have
                quality_threshold = 0.9  # Start with high threshold
                threshold_lowered = False
                images_accepted = 0  # Track how many images we've accepted at current threshold
                
                # OPTIMIZATION #1 & #4: Batch fetch metadata for all images at once
                # Collect all images first
                images_to_process = []
                # Server mode: process more images for higher quality
                max_images = MAX_IMAGES_TO_PROCESS if 'MAX_IMAGES_TO_PROCESS' in locals() else MAX_IMAGES_PER_SATELLITE
                for i in range(min(s2_count, max_images)):
                    try:
                        img = ee.Image(s2_col.toList(s2_count).get(i))
                        images_to_process.append(img)
                    except Exception:
                        continue
                
                # Batch fetch metadata in parallel
                # Server mode: use more parallel workers for faster metadata fetching
                if images_to_process:
                    metadata_workers = min(16, len(images_to_process) * 2) if server_mode else 4
                    metadata_list = extract_metadata_parallel(
                        images_to_process,
                        ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", 
                         "MEAN_SOLAR_ZENITH_ANGLE", "MEAN_INCIDENCE_ZENITH_ANGLE"],
                        max_workers=metadata_workers
                    )
                else:
                    metadata_list = []
                
                test_num = 0
                sat_name = "Copernicus Sentinel-2"
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                
                # ADAPTIVE CLOUD THRESHOLDS: Start strict, lower incrementally if no images found
                # Progressive lowering ensures we accept high-cloud images when they're all we have
                # Initialize cloud thresholds per satellite
                cloud_threshold_metadata = 20.0  # Start with 20% for metadata cloud cover
                cloud_fraction_threshold = 0.2  # Start with 20% for calculated cloud fraction
                images_accepted_after_clouds = 0  # Track images that passed cloud checks
                
                # FALLBACK: Track best rejected image - use if all images fail checks
                # Track images rejected by cloud checks separately (clouds are better than holes)
                best_rejected_by_clouds = None
                best_rejected_cloud_pct = 999.0  # Track lowest cloud fraction (0.0-1.0)
                best_rejected_image = None
                best_rejected_score = -1.0
                best_rejected_detailed_stats = None
                
                for idx, img in enumerate(images_to_process):
                    if idx >= len(metadata_list):
                        break
                    
                    try:
                        metadata = metadata_list[idx]
                        test_num += 1
                        
                        # Get image date from batched metadata
                        img_date_str = start  # Default to start date
                        days_since = None
                        try:
                            if metadata.get("system:time_start"):
                                img_dt = datetime.fromtimestamp(int(metadata["system:time_start"]) / 1000)
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                                days_since = (img_dt - start_date).days
                        except Exception:
                            pass
                        
                        # ADAPTIVE CLOUD THRESHOLD (METADATA): Lower progressively if no images accepted
                        # Progressive lowering: 20% → 30% → 40% → 50% → 60% → 80%
                        # This ensures we accept high-cloud images when they're all we have
                        # Use pre-computed MIN_TESTS_BEFORE_LOWERING based on total available images
                        if images_accepted_after_clouds == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and cloud_threshold_metadata < 80.0:
                            old_threshold = cloud_threshold_metadata
                            if cloud_threshold_metadata <= 20.0:
                                cloud_threshold_metadata = 30.0
                            elif cloud_threshold_metadata <= 30.0:
                                cloud_threshold_metadata = 40.0
                            elif cloud_threshold_metadata <= 40.0:
                                cloud_threshold_metadata = 50.0
                            elif cloud_threshold_metadata <= 50.0:
                                cloud_threshold_metadata = 60.0
                            elif cloud_threshold_metadata <= 60.0:
                                cloud_threshold_metadata = 80.0
                            
                            if cloud_threshold_metadata != old_threshold:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Lowered metadata cloud threshold for {sat_name} from {old_threshold:.0f}% to {cloud_threshold_metadata:.0f}% (no images found at lower threshold)")
                        
                        # OPTIMIZATION: Quick cloud check from batched metadata
                        cp_val = metadata.get("CLOUDY_PIXEL_PERCENTAGE")
                        if cp_val is not None and float(cp_val) > cloud_threshold_metadata:
                            # Track best rejected by clouds for fallback (clouds better than no data)
                            cloud_pct = float(cp_val) / 100.0  # Convert to fraction (0.0-1.0)
                            if cloud_pct < best_rejected_cloud_pct:
                                best_rejected_cloud_pct = cloud_pct
                                best_rejected_by_clouds = (img, metadata, img_date_str, cloud_pct, None)  # cf not calculated yet
                            if test_callback:
                                test_callback(tile_idx, test_num, "S2", img_date_str, None, f"SKIPPED (>{cloud_threshold_metadata:.0f}% clouds)")
                            continue
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # CRITICAL: Calculate cloud fraction BEFORE masking
                        # Otherwise we're calculating cloud fraction from an already-masked image
                        cf, vf = estimate_cloud_fraction(img, geom)  # Use original image, not masked
                        
                        # Debug logging for Sentinel-2 cloud fraction
                        if tile_idx is not None:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Sentinel-2 {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}%")
                        
                        # ADAPTIVE CLOUD FRACTION THRESHOLD: Lower progressively if no images accepted
                        # Progressive lowering: 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.8
                        # This ensures we accept high-cloud images when they're all we have
                        # Use pre-computed MIN_TESTS_BEFORE_LOWERING based on total available images
                        if images_accepted_after_clouds == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and cloud_fraction_threshold < 0.8:
                            old_threshold = cloud_fraction_threshold
                            if cloud_fraction_threshold <= 0.2:
                                cloud_fraction_threshold = 0.3
                            elif cloud_fraction_threshold <= 0.3:
                                cloud_fraction_threshold = 0.4
                            elif cloud_fraction_threshold <= 0.4:
                                cloud_fraction_threshold = 0.5
                            elif cloud_fraction_threshold <= 0.5:
                                cloud_fraction_threshold = 0.6
                            elif cloud_fraction_threshold <= 0.6:
                                cloud_fraction_threshold = 0.8
                            
                            if cloud_fraction_threshold != old_threshold:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Lowered cloud fraction threshold for {sat_name} from {old_threshold*100:.0f}% to {cloud_fraction_threshold*100:.0f}% (no images found at lower threshold)")
                        
                        # OPTIMIZATION: Early exit if too cloudy (before processing)
                        if cf > cloud_fraction_threshold:
                            # Track best rejected by cloud fraction for fallback (clouds better than no data)
                            if cf < best_rejected_cloud_pct:
                                best_rejected_cloud_pct = cf
                                best_rejected_by_clouds = (img, metadata, img_date_str, cf, vf)
                            if test_callback:
                                test_callback(tile_idx, test_num, "S2", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        # Image passed both cloud checks - increment counter
                        images_accepted_after_clouds += 1
                        
                        # Now prepare the image (this masks clouds)
                        img_p = s2_prepare_image(img)
                        
                        # Get metadata from batched results (already fetched)
                        sun_zen_val = None
                        view_zen_val = None
                        try:
                            if metadata.get("MEAN_SOLAR_ZENITH_ANGLE") is not None:
                                sun_zen_val = float(metadata["MEAN_SOLAR_ZENITH_ANGLE"])
                            if metadata.get("MEAN_INCIDENCE_ZENITH_ANGLE") is not None:
                                view_zen_val = float(metadata["MEAN_INCIDENCE_ZENITH_ANGLE"])
                        except Exception:
                            pass
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # Harmonize to common standard
                        if enable_harmonize:
                            img_p = harmonize_image(img_p, "S2_to_LS")
                        
                        # OPTIMIZATION #3: Cache band name lookups
                        # Collect band information using cached lookup
                        try:
                            band_names = get_cached_band_names(img_p, "S2")
                            if not band_names:  # Cache miss or first time
                                band_names = img_p.bandNames().getInfo()
                            # Calculate band completeness from collected bands
                            try:
                                band_completeness = check_band_completeness(band_names)
                            except Exception:
                                band_completeness = None
                        except Exception:
                            band_names = []
                            band_completeness = None
                        
                        # STEP 2: Now calculate quality score ONCE with all complete data
                        # Sentinel-2 native resolution: 10m
                        quality_score = compute_quality_score(cf, sun_zen_val, view_zen_val, vf, days_since, max_days, native_resolution=10.0, band_completeness=band_completeness)
                        
                        # STEP 3: Create complete detailed stats with all collected data
                        # Store timestamp for gap-filling (to avoid API calls later)
                        img_timestamp = None
                        try:
                            if metadata.get("system:time_start"):
                                img_timestamp = int(metadata["system:time_start"]) / 1000
                        except Exception:
                            pass
                        
                        detailed_stats = {
                            "satellite": "Copernicus Sentinel-2",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": sun_zen_val,
                            "view_zenith": view_zen_val,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 10.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0,  # Use 0.0 instead of None
                            "timestamp": img_timestamp  # Store timestamp for gap-filling (avoids API calls)
                        }
                        
                        # STEP 4: Report test result with complete data
                        if test_callback:
                            test_callback(tile_idx, test_num, "S2", img_date_str, quality_score, None, detailed_stats)
                        
                        # ADAPTIVE QUALITY THRESHOLD: Start high, lower incrementally until images are found
                        # Progressive lowering: 0.9 -> 0.7 -> 0.5 -> 0.3 -> 0.1 -> 0.0
                        
                        # Check if we should lower threshold (no images accepted yet and we've tested multiple)
                        # Use pre-computed MIN_TESTS_BEFORE_LOWERING based on total available images
                        if images_accepted == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and quality_threshold > 0.0:
                            old_threshold = quality_threshold
                            if quality_threshold >= 0.9:
                                quality_threshold = 0.7
                            elif quality_threshold >= 0.7:
                                quality_threshold = 0.5
                            elif quality_threshold >= 0.5:
                                quality_threshold = 0.3
                            elif quality_threshold >= 0.3:
                                quality_threshold = 0.1
                            else:
                                quality_threshold = 0.0
                            
                            if quality_threshold != old_threshold:
                                threshold_lowered = True
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Lowered quality threshold for Sentinel-2 from {old_threshold:.1f} to {quality_threshold:.1f} (no images found at higher threshold)")
                        
                        # Track best rejected image for fallback (always track, even if rejected)
                        if quality_score > best_rejected_score:
                            best_rejected_score = quality_score
                            # Store image selection info for later use if needed
                            best_rejected_image = (img_p, quality_score, detailed_stats, img_date_str)
                        
                        # Accept image if it meets current threshold (or if at minimum threshold of 0.0)
                        if quality_score < quality_threshold and quality_threshold > 0.0:
                            if test_callback:
                                test_callback(tile_idx, test_num, "S2", img_date_str, None, f"SKIPPED (quality {quality_score:.3f} < threshold {quality_threshold:.1f})")
                            logging.debug(f"Sentinel-2 image skipped: quality score {quality_score:.3f} < threshold {quality_threshold:.1f}")
                            # Track best rejected image for fallback (even if rejected by quality)
                            if quality_score > best_rejected_score:
                                best_rejected_score = quality_score
                                # Will store the prepared image after band selection
                                best_rejected_image = (img_p, quality_score, detailed_stats, img_date_str, band_names)
                                continue
                        
                        # Image accepted - increment counter
                        images_accepted += 1
                        
                        # Select bands: RGB + IR bands + water indices + vegetation indices
                        # Allow partial bands - missing bands will be filled from fallback images via qualityMosaic
                        try:
                            sel_bands = []
                            # Select RGB bands (allow partial selection)
                            if "B4" in band_names:
                                sel_bands.append("B4")
                            if "B3" in band_names:
                                sel_bands.append("B3")
                            if "B2" in band_names:
                                sel_bands.append("B2")
                            
                            # Require at least one band
                            if len(sel_bands) == 0:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Sentinel-2 {img_date_str} Test {test_num:02d}: No RGB bands found. Available bands: {band_names}")
                                # Track best rejected image even if no bands
                                if quality_score > best_rejected_score:
                                    best_rejected_score = quality_score
                                    best_rejected_image = (img_p, quality_score, detailed_stats, img_date_str, band_names)
                                continue
                            
                            # Log if RGB bands are incomplete
                            if len(sel_bands) < 3:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Sentinel-2 {img_date_str} Test {test_num:02d}: Partial RGB bands ({len(sel_bands)}/3). Missing bands will be filled from fallback images.")
                            
                            # Add IR bands if available (ONLY raw bands - indices created AFTER mosaic)
                            if "B8" in band_names:
                                sel_bands.append("B8")  # NIR
                            if "B11" in band_names:
                                sel_bands.append("B11")  # SWIR1
                            if "B12" in band_names:
                                sel_bands.append("B12")  # SWIR2
                            
                            # NO INDICES HERE - indices are created AFTER qualityMosaic unifies all bands
                            # This allows qualityMosaic to fill missing bands from fallback images
                            
                            sel = img_p.select(sel_bands)
                            
                            # Store detailed stats for this satellite
                            sat_name = "Copernicus Sentinel-2"
                            if sat_name not in satellite_detailed_stats or quality_score > satellite_detailed_stats[sat_name]["quality_score"]:
                                satellite_detailed_stats[sat_name] = detailed_stats
                        except Exception as e:
                            logging.debug(f"Sentinel-2 band selection error: {e}")
                            # Track best rejected image even if band selection fails
                            if quality_score > best_rejected_score:
                                best_rejected_score = quality_score
                                best_rejected_image = (img_p, quality_score, detailed_stats, img_date_str, band_names)
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        sel = sel.addBands(quality_band)
                        # CRITICAL: Standardize RAW bands BEFORE adding to collection to ensure homogeneous band structure
                        # This ensures all images have the same RAW bands (B4, B3, B2, B8, B11, B12, quality)
                        # Indices are created AFTER qualityMosaic unifies all bands
                        sel = standardize_raw_bands_for_collection(sel)
                        
                        # TWO-PHASE APPROACH: Track excellent images per satellite (up to 3 per satellite)
                        if quality_score >= EXCELLENT_QUALITY_THRESHOLD:
                            excellent_count_for_sat += 1
                            if sat_name not in excellent_per_satellite:
                                excellent_per_satellite[sat_name] = []
                            excellent_per_satellite[sat_name].append((sel, quality_score, detailed_stats.copy()))
                            # Stop searching THIS satellite after finding 3 excellent images
                            if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Found {excellent_count_for_sat} excellent images from {sat_name}, continuing to next satellite")
                                break
                        
                        prepared.append(sel)
                        satellite_contributions.append("Copernicus Sentinel-2")
                        # Track best quality score for this satellite
                        sat_name = "Copernicus Sentinel-2"
                        if sat_name not in satellite_quality_scores or quality_score > satellite_quality_scores[sat_name]:
                            satellite_quality_scores[sat_name] = quality_score
                        
                        # Track this image for fallback ranking
                        all_image_stats.append((sel, quality_score, detailed_stats.copy(), sat_name))
                        
                        # Track the single best image overall (highest quality score)
                        # CRITICAL: Always prioritize higher quality score when difference is > 5%
                        # Only use band completeness as tiebreaker when scores are truly close
                        score_diff = quality_score - best_score
                        if score_diff > 0.05:  # Clear winner (5%+ better) - always use higher score
                            best_score = quality_score
                            best_image = sel
                            best_satellite_name = sat_name
                            best_detailed_stats = satellite_detailed_stats.get(sat_name)
                        elif abs(score_diff) <= 0.05:  # Scores are truly close (within 5% in either direction)
                            # Only in this case, use band completeness as tiebreaker
                            try:
                                current_bands = sel.bandNames().getInfo()
                                current_completeness = check_band_completeness(current_bands)
                                
                                if best_image is not None:
                                    best_bands = best_image.bandNames().getInfo()
                                    best_completeness = check_band_completeness(best_bands)
                                    
                                    # If current image has significantly better completeness (>10%), prefer it
                                    # But only if scores are close (already checked above)
                                    if current_completeness > best_completeness + 0.1:  # 10% threshold
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = sat_name
                                        best_detailed_stats = satellite_detailed_stats.get(sat_name)
                                    elif quality_score > best_score:  # If completeness similar, use higher score
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = sat_name
                                        best_detailed_stats = satellite_detailed_stats.get(sat_name)
                                else:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = sat_name
                                    best_detailed_stats = satellite_detailed_stats.get(sat_name)
                            except Exception:
                                # Fallback: use higher score if band check fails
                                if quality_score > best_score:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = sat_name
                                    best_detailed_stats = satellite_detailed_stats.get(sat_name)
                            # If score is significantly lower (< -0.05), don't update
                    except Exception as e:
                        logging.debug(f"Skipping S2 image {idx}: {e}")
                        continue
                
                # FALLBACK: If no images were accepted but we tested some, use the best one we saw
                # Priority: 1) Best rejected by quality, 2) Best rejected by clouds (clouds better than holes)
                if images_accepted == 0 and len(images_to_process) > 0:
                    # First try: use best rejected by quality (if we calculated quality scores)
                    if best_rejected_image is not None:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Sentinel-2: No images passed thresholds, using best rejected image (quality={best_rejected_score:.3f})")
                        try:
                            img_p_fallback, quality_score_fallback, detailed_stats_fallback, img_date_str_fallback, band_names_fallback = best_rejected_image
                            sel_bands_fallback = []
                            if "B4" in band_names_fallback:
                                sel_bands_fallback.append("B4")
                            if "B3" in band_names_fallback:
                                sel_bands_fallback.append("B3")
                            if "B2" in band_names_fallback:
                                sel_bands_fallback.append("B2")
                            if len(sel_bands_fallback) > 0:
                                if "B8" in band_names_fallback:
                                    sel_bands_fallback.append("B8")
                                if "B11" in band_names_fallback:
                                    sel_bands_fallback.append("B11")
                                if "B12" in band_names_fallback:
                                    sel_bands_fallback.append("B12")
                                sel_fallback = img_p_fallback.select(sel_bands_fallback)
                                quality_band_fallback = ee.Image.constant(float(quality_score_fallback)).toFloat().rename("quality")
                                sel_fallback = sel_fallback.addBands(quality_band_fallback)
                                sel_fallback = standardize_raw_bands_for_collection(sel_fallback)
                                prepared.append(sel_fallback)
                                satellite_contributions.append("Copernicus Sentinel-2")
                                sat_name = "Copernicus Sentinel-2"
                                if sat_name not in satellite_quality_scores or quality_score_fallback > satellite_quality_scores[sat_name]:
                                    satellite_quality_scores[sat_name] = quality_score_fallback
                                all_image_stats.append((sel_fallback, quality_score_fallback, detailed_stats_fallback.copy(), sat_name))
                                images_accepted = 1  # Mark as accepted so we don't try again
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Sentinel-2: Error using quality fallback image: {e}")
                    # Second try: use best rejected by clouds (if all failed cloud checks before quality calculation)
                    elif best_rejected_by_clouds is not None and images_accepted_after_clouds == 0:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Sentinel-2: No images passed cloud checks, using best rejected by clouds ({best_rejected_cloud_pct*100:.1f}% clouds - clouds better than holes)")
                        try:
                            img_cloud_fallback, metadata_cloud_fallback, img_date_str_cloud_fallback, cloud_pct_fallback, vf_cloud_fallback = best_rejected_by_clouds
                            # Calculate cloud fraction if not already calculated
                            if vf_cloud_fallback is None:
                                cf_fallback, vf_cloud_fallback = estimate_cloud_fraction(img_cloud_fallback, geom)
                            else:
                                cf_fallback = cloud_pct_fallback
                            # Prepare the image fully (even with clouds)
                            img_p_cloud_fallback = s2_prepare_image(img_cloud_fallback)
                            if enable_harmonize:
                                img_p_cloud_fallback = harmonize_image(img_p_cloud_fallback, "S2_to_LS")
                            # Get band names
                            try:
                                band_names_cloud_fallback = get_cached_band_names(img_p_cloud_fallback, "S2")
                                if not band_names_cloud_fallback:
                                    band_names_cloud_fallback = img_p_cloud_fallback.bandNames().getInfo()
                            except Exception:
                                band_names_cloud_fallback = img_p_cloud_fallback.bandNames().getInfo()
                            # Select bands
                            sel_bands_cloud_fallback = []
                            if "B4" in band_names_cloud_fallback:
                                sel_bands_cloud_fallback.append("B4")
                            if "B3" in band_names_cloud_fallback:
                                sel_bands_cloud_fallback.append("B3")
                            if "B2" in band_names_cloud_fallback:
                                sel_bands_cloud_fallback.append("B2")
                            if len(sel_bands_cloud_fallback) > 0:
                                if "B8" in band_names_cloud_fallback:
                                    sel_bands_cloud_fallback.append("B8")
                                if "B11" in band_names_cloud_fallback:
                                    sel_bands_cloud_fallback.append("B11")
                                if "B12" in band_names_cloud_fallback:
                                    sel_bands_cloud_fallback.append("B12")
                                sel_cloud_fallback = img_p_cloud_fallback.select(sel_bands_cloud_fallback)
                                # Calculate quality score (even if low, use it)
                                sun_zen_val_cloud = None
                                view_zen_val_cloud = None
                                try:
                                    if metadata_cloud_fallback.get("MEAN_SOLAR_ZENITH_ANGLE") is not None:
                                        sun_zen_val_cloud = float(metadata_cloud_fallback["MEAN_SOLAR_ZENITH_ANGLE"])
                                    if metadata_cloud_fallback.get("MEAN_INCIDENCE_ZENITH_ANGLE") is not None:
                                        view_zen_val_cloud = float(metadata_cloud_fallback["MEAN_INCIDENCE_ZENITH_ANGLE"])
                                except Exception:
                                    pass
                                try:
                                    if metadata_cloud_fallback.get("system:time_start"):
                                        days_since_cloud = (datetime.fromtimestamp(int(metadata_cloud_fallback["system:time_start"]) / 1000) - start_date).days
                                    else:
                                        days_since_cloud = None
                                except Exception:
                                    days_since_cloud = None
                                try:
                                    band_completeness_cloud = check_band_completeness(band_names_cloud_fallback)
                                except Exception:
                                    band_completeness_cloud = None
                                quality_score_cloud_fallback = compute_quality_score(cf_fallback, sun_zen_val_cloud, view_zen_val_cloud, vf_cloud_fallback, days_since_cloud, max_days, native_resolution=10.0, band_completeness=band_completeness_cloud)
                                quality_band_cloud_fallback = ee.Image.constant(float(quality_score_cloud_fallback)).toFloat().rename("quality")
                                sel_cloud_fallback = sel_cloud_fallback.addBands(quality_band_cloud_fallback)
                                sel_cloud_fallback = standardize_raw_bands_for_collection(sel_cloud_fallback)
                                prepared.append(sel_cloud_fallback)
                                satellite_contributions.append("Copernicus Sentinel-2")
                                sat_name = "Copernicus Sentinel-2"
                                if sat_name not in satellite_quality_scores or quality_score_cloud_fallback > satellite_quality_scores[sat_name]:
                                    satellite_quality_scores[sat_name] = quality_score_cloud_fallback
                                all_image_stats.append((sel_cloud_fallback, quality_score_cloud_fallback, {"satellite": sat_name, "quality_score": quality_score_cloud_fallback, "cloud_fraction": cf_fallback}.copy(), sat_name))
                                images_accepted = 1
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Sentinel-2: Error using cloud fallback image: {e}")
    except Exception as e:
        if str(e) != "include_s2_false_skip":
            logging.debug(f"Error processing Sentinel-2: {e}")
    
    # Process Landsat - filter by operational date ranges
    ls_defs = [
        ("LANDSAT/LT04/C02/T1_L2", "LANDSAT_4"),  # Landsat 4 TM (30m, 1982-1993)
        ("LANDSAT/LT05/C02/T1_L2", "LANDSAT_5"),
        ("LANDSAT/LE07/C02/T1_L2", "LANDSAT_7"),
        ("LANDSAT/LC08/C02/T1_L2", "LANDSAT_8"),
        ("LANDSAT/LC09/C02/T1_L2", "LANDSAT_9"),
    ]
    
    if include_landsat:
        for coll_id, key in ls_defs:
            if not include_landsat:
                logging.debug("Skipping Landsat entirely for this month (out of operational range)")
                break
            # Skip this Landsat sensor if not operational in requested date range
            try:
                if not is_satellite_operational(key, start, end):
                    logging.debug(f"Skipping {key} for this month (out of operational range)")
                    continue
            except Exception:
                # If check fails, proceed conservatively (do not skip)
                pass
            try:
                # Use landsat_col to avoid name collision with final mosaic collection
                landsat_col = ee.ImageCollection(coll_id).filterBounds(geom).filterDate(start, end)
                # OPTIMIZATION #2: Pre-filter collection before iteration (server-side filtering)
                # NOTE: Server-side cloud filter removed to allow adaptive cloud thresholds to work properly
                # We'll filter by cloud cover client-side with adaptive thresholds that lower progressively
                # OPTIMIZATION: Server-side filtering - sort by cloud cover and take best
                landsat_col = landsat_col.sort("CLOUD_COVER")
                # Get collection size with error handling for quota/network issues
                try:
                    cnt = int(landsat_col.size().getInfo())
                except Exception as e:
                    error_msg = str(e)
                    # Check for quota errors
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Quota/rate limit error while checking {key} collection size: {e}")
                    else:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error checking {key} collection size: {e}")
                    continue
                if cnt == 0:
                    continue
                
                # ADAPTIVE QUALITY THRESHOLD: Start high, lower incrementally until images are found
                # This ensures poor quality images (e.g., Landsat 4) are still used if they're all we have
                quality_threshold = 0.9  # Start with high threshold
                threshold_lowered = False
                images_accepted = 0  # Track how many images we've accepted at current threshold
                
                # OPTIMIZATION #1 & #4: Batch fetch metadata for all images at once
                images_to_process = []
                # Server mode: process more images for higher quality
                max_images = MAX_IMAGES_TO_PROCESS if 'MAX_IMAGES_TO_PROCESS' in locals() else MAX_IMAGES_PER_SATELLITE
                for i in range(min(cnt, max_images)):
                    try:
                        img = ee.Image(landsat_col.toList(cnt).get(i))
                        images_to_process.append(img)
                    except Exception:
                        continue
                
                # Batch fetch metadata in parallel
                # Server mode: use more parallel workers for faster metadata fetching
                if images_to_process:
                    metadata_workers = min(16, len(images_to_process) * 2) if server_mode else 4
                    try:
                        metadata_list = extract_metadata_parallel(
                            images_to_process,
                            ["system:time_start", "CLOUD_COVER", "CLOUD_COVER_LAND", "SUN_ELEVATION"],
                            max_workers=metadata_workers
                        )
                        # Check if metadata list is shorter than images (some may have failed)
                        if len(metadata_list) < len(images_to_process):
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Metadata fetch returned {len(metadata_list)} results for {len(images_to_process)} images")
                    except Exception as e:
                        error_msg = str(e)
                        if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                            logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Quota/rate limit error fetching {key} metadata: {e}")
                        else:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error fetching {key} metadata: {e}")
                        metadata_list = []
                else:
                    metadata_list = []
                
                test_num = 0
                sat_name = key.replace("LANDSAT_", "Landsat-").replace("_", "-")
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                
                # ADAPTIVE CLOUD THRESHOLDS: Start strict, lower incrementally if no images found
                # Progressive lowering ensures we accept high-cloud images when they're all we have
                # Initialize cloud thresholds per satellite
                cloud_threshold_metadata = 20.0  # Start with 20% for metadata cloud cover
                cloud_fraction_threshold = 0.2  # Start with 20% for calculated cloud fraction
                images_accepted_after_clouds = 0  # Track images that passed cloud checks
                
                # FALLBACK: Track best rejected image - use if all images fail checks
                # Track images rejected by cloud checks separately (clouds are better than holes)
                best_rejected_by_clouds_landsat = None
                best_rejected_cloud_pct_landsat = 999.0  # Track lowest cloud fraction (0.0-1.0)
                best_rejected_image_landsat = None
                best_rejected_score_landsat = -1.0
                best_rejected_detailed_stats_landsat = None
                
                # Special handling for Landsat 4 when alone (pre-1984): start with relaxed thresholds
                if key == "LANDSAT_4":
                    try:
                        overlap_start = datetime.fromisoformat("1984-03-01")
                        month_start_dt = datetime.fromisoformat(start)
                        if month_start_dt < overlap_start:
                            # When L4 is alone, start with 25% instead of 20%
                            cloud_threshold_metadata = 25.0
                            cloud_fraction_threshold = 0.25
                    except:
                        pass
                
                for idx, img in enumerate(images_to_process):
                    if idx >= len(metadata_list):
                        # Skip images that don't have metadata (failed to fetch)
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Skipping image {idx} (no metadata available)")
                        break
                    
                    try:
                        metadata = metadata_list[idx]
                        test_num += 1
                        
                        # Get image date from batched metadata
                        img_date_str = start  # Default to start date
                        days_since = None
                        img_dt = None  # Initialize to avoid scope issues
                        is_l7_post_slc_failure = False
                        try:
                            if metadata.get("system:time_start"):
                                img_dt = datetime.fromtimestamp(int(metadata["system:time_start"]) / 1000)
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                                days_since = (img_dt - start_date).days
                                
                                # Check if this is Landsat 7 after SLC failure (2003-05-31)
                                if key == "LANDSAT_7":
                                    slc_failure_date = datetime.fromisoformat("2003-05-31")
                                    if img_dt >= slc_failure_date:
                                        is_l7_post_slc_failure = True
                                        logging.debug(f"Landsat 7 image after SLC failure (2003-05-31): {img_dt.date()}")
                        except Exception:
                            pass
                        
                        # ADAPTIVE CLOUD THRESHOLD (METADATA): Lower progressively if no images accepted
                        # Progressive lowering: 20% → 30% → 40% → 50% → 60% → 80%
                        # This ensures we accept high-cloud images when they're all we have
                        # Use pre-computed MIN_TESTS_BEFORE_LOWERING based on total available images
                        if images_accepted_after_clouds == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and cloud_threshold_metadata < 80.0:
                            old_threshold = cloud_threshold_metadata
                            if cloud_threshold_metadata <= 20.0:
                                cloud_threshold_metadata = 30.0
                            elif cloud_threshold_metadata <= 30.0:
                                cloud_threshold_metadata = 40.0
                            elif cloud_threshold_metadata <= 40.0:
                                cloud_threshold_metadata = 50.0
                            elif cloud_threshold_metadata <= 50.0:
                                cloud_threshold_metadata = 60.0
                            elif cloud_threshold_metadata <= 60.0:
                                cloud_threshold_metadata = 80.0
                            
                            if cloud_threshold_metadata != old_threshold:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Lowered metadata cloud threshold for {sat_name} from {old_threshold:.0f}% to {cloud_threshold_metadata:.0f}% (no images found at lower threshold)")
                        
                        # OPTIMIZATION: Quick cloud check from batched metadata
                        cc_val = metadata.get("CLOUD_COVER") or metadata.get("CLOUD_COVER_LAND")
                        
                        if cc_val is not None and float(cc_val) > cloud_threshold_metadata:
                            # Track best rejected by clouds for fallback (clouds better than no data)
                            cloud_pct_landsat = float(cc_val) / 100.0  # Convert to fraction (0.0-1.0)
                            if cloud_pct_landsat < best_rejected_cloud_pct_landsat:
                                best_rejected_cloud_pct_landsat = cloud_pct_landsat
                                best_rejected_by_clouds_landsat = (img, metadata, img_date_str, cloud_pct_landsat, None, key)  # cf not calculated yet
                            if test_callback:
                                test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED (>{cloud_threshold_metadata:.0f}% clouds)")
                            continue
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # CRITICAL: Calculate cloud fraction BEFORE masking (like MODIS)
                        # Otherwise we're calculating cloud fraction from an already-masked image
                        cf, vf = estimate_cloud_fraction(img, geom)  # Use original image, not masked
                        
                        # Debug logging for Landsat cloud fraction
                        if tile_idx is not None:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key} {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}%")
                        
                        # ADAPTIVE CLOUD FRACTION THRESHOLD: Lower progressively if no images accepted
                        # Progressive lowering: 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.8
                        # This ensures we accept high-cloud images when they're all we have
                        # Use pre-computed MIN_TESTS_BEFORE_LOWERING based on total available images
                        if images_accepted_after_clouds == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and cloud_fraction_threshold < 0.8:
                            old_threshold = cloud_fraction_threshold
                            if cloud_fraction_threshold <= 0.2:
                                cloud_fraction_threshold = 0.3
                            elif cloud_fraction_threshold <= 0.3:
                                cloud_fraction_threshold = 0.4
                            elif cloud_fraction_threshold <= 0.4:
                                cloud_fraction_threshold = 0.5
                            elif cloud_fraction_threshold <= 0.5:
                                cloud_fraction_threshold = 0.6
                            elif cloud_fraction_threshold <= 0.6:
                                cloud_fraction_threshold = 0.8
                            
                            if cloud_fraction_threshold != old_threshold:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Lowered cloud fraction threshold for {sat_name} from {old_threshold*100:.0f}% to {cloud_fraction_threshold*100:.0f}% (no images found at lower threshold)")
                        
                        # OPTIMIZATION: Early exit if too cloudy (before processing)
                        if cf > cloud_fraction_threshold:
                            # Track best rejected by cloud fraction for fallback (clouds better than no data)
                            if cf < best_rejected_cloud_pct_landsat:
                                best_rejected_cloud_pct_landsat = cf
                                best_rejected_by_clouds_landsat = (img, metadata, img_date_str, cf, vf, key)
                            if test_callback:
                                test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        # Image passed both cloud checks - increment counter
                        images_accepted_after_clouds += 1
                        
                        # Now prepare the image (this masks clouds)
                        img_p = landsat_prepare_image(img)
                        
                        if key == "LANDSAT_7":
                            try:
                                # Mask out invalid pixels (helps with SLC gaps)
                                img_p = img_p.updateMask(img_p.reduce(ee.Reducer.allNonZero()))
                            except Exception:
                                pass
                        
                        # Get solar zenith from batched metadata (already fetched)
                        sun_zen_val = None
                        try:
                            if metadata.get("SUN_ELEVATION") is not None:
                                sun_zen_val = 90.0 - float(metadata["SUN_ELEVATION"])
                        except Exception:
                            pass
                        
                        # Handle negative days (image before start date)
                        if days_since is not None and days_since < 0:
                            days_since = 0  # Clamp to 0 for images before start date
                        
                        # Harmonize and collect band information
                        if enable_harmonize:
                            img_p = harmonize_image(img_p, "LS_to_S2")
                        
                        # OPTIMIZATION #3: Cache band name lookups
                        # Collect band information using cached lookup
                        try:
                            bands = get_cached_band_names(img_p, key)
                            if not bands:  # Cache miss or first time
                                bands = img_p.bandNames().getInfo()
                            # Calculate band completeness from collected bands
                            try:
                                band_completeness = check_band_completeness(bands)
                            except Exception:
                                band_completeness = None
                        except Exception:
                            bands = []
                            band_completeness = None
                        
                        # STEP 2: Now calculate quality score ONCE with all complete data
                        # Landsat native resolution: 30m
                        # Heavily penalize Landsat 7 after SLC failure (2003-05-31) due to data gaps/black stripes
                        base_quality_score = compute_quality_score(cf, sun_zen_val, None, vf, days_since, max_days, native_resolution=30.0, band_completeness=band_completeness)
                        
                        # IMPROVEMENT: Prefer Landsat 5 over Landsat 4 when both are available (overlap period 1984-1993)
                        # Landsat 5 is generally more reliable and has better calibration than Landsat 4
                        # When mixing L4 and L5, prefer L5 for better consistency and quality
                        # When L4 is alone, optimize it for best possible quality
                        if key == "LANDSAT_4":
                            # Check if Landsat 5 images are already in the prepared list
                            has_landsat5 = any("Landsat-5" in stats[3] for stats in all_image_stats) if all_image_stats else False
                            # Also check if we're in the overlap period where L5 is likely available
                            try:
                                overlap_start = datetime.fromisoformat("1984-03-01")
                                overlap_end = datetime.fromisoformat("1993-12-14")
                                month_start_dt = datetime.fromisoformat(start)
                                in_overlap_period = overlap_start <= month_start_dt <= overlap_end
                            except:
                                in_overlap_period = False
                            
                            if has_landsat5 or in_overlap_period:
                                # Small penalty for L4 when L5 is available or likely available (-8% quality)
                                # This helps when mixing L4 and L5 by favoring L5 for better data quality
                                # L5 has better calibration and more consistent data quality than L4
                                quality_score = base_quality_score * 0.92
                                if tile_idx is not None and has_landsat5:
                                    logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Landsat 4 penalty applied (-8%) because Landsat 5 is available")
                            else:
                                # IMPROVEMENT: When Landsat 4 is alone (pre-1984), optimize for best quality
                                # Give bonus for later L4 data (1983+) which may have better calibration
                                quality_score = base_quality_score
                                try:
                                    # Check image date - img_dt is initialized earlier, check if it's set
                                    if img_dt is not None:
                                        img_date_for_bonus = img_dt
                                    else:
                                        # Fallback: parse from metadata if img_dt not available
                                        if metadata.get("system:time_start"):
                                            img_date_for_bonus = datetime.fromtimestamp(int(metadata["system:time_start"]) / 1000)
                                        else:
                                            img_date_for_bonus = None
                                    
                                    if img_date_for_bonus and img_date_for_bonus.year >= 1983:
                                        # Small bonus for later L4 data (1983-1984) - better calibration than early 1982 data
                                        # Early L4 (1982) may have calibration issues, later L4 is more reliable
                                        quality_score = min(1.0, base_quality_score * 1.05)  # Clamp to 1.0 immediately
                                        if tile_idx is not None:
                                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Landsat 4 bonus applied (+5%) for later data (1983+) - better calibration")
                                except Exception:
                                    pass
                        elif key == "LANDSAT_5":
                            # Small bonus for L5 (+5% quality) to prefer it over L4 when both are available
                            # This makes L5 slightly better even with similar quality metrics
                            # Helps ensure L5 wins when mixing with L4 in overlap period (1984-1993)
                            # L5 has better calibration, more consistent quality, and longer operational period
                            has_landsat4 = any("Landsat-4" in stats[3] for stats in all_image_stats) if all_image_stats else False
                            if has_landsat4:
                                quality_score = min(1.0, base_quality_score * 1.05)  # Clamp to 1.0 immediately
                                if tile_idx is not None:
                                    logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Landsat 5 bonus applied (+5%) because mixing with Landsat 4")
                            else:
                                quality_score = base_quality_score
                        elif is_l7_post_slc_failure:
                            # Apply severe penalty for SLC failure - reduce quality by 50% to make it last resort
                            # This ensures other satellites (Landsat 5, MODIS, ASTER) are preferred
                            quality_score = base_quality_score * 0.5
                            logging.debug(f"Landsat 7 post-SLC failure: quality reduced from {base_quality_score:.3f} to {quality_score:.3f} (last resort)")
                        else:
                            quality_score = base_quality_score
                        
                        # Additional safety for Landsat 7 after SLC failure:
                        # If band completeness is low, stripes/gaps are likely problematic – skip such images
                        if key == "LANDSAT_7" and is_l7_post_slc_failure:
                            try:
                                if band_completeness is not None and band_completeness < 0.7:
                                    if test_callback:
                                        test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED (L7 stripes: low completeness {band_completeness:.2f})")
                                    logging.debug(f"Landsat 7 post-SLC failure skipped due to low band completeness ({band_completeness:.2f} < 0.70)")
                                    continue
                            except Exception:
                                # If we can't evaluate completeness, continue with penalty applied above
                                pass
                        
                        # STEP 3: Create complete detailed stats with all collected data
                        sat_name = key.replace("LANDSAT_", "Landsat-").replace("_", "-")
                        # Store timestamp for gap-filling (to avoid API calls later)
                        img_timestamp = None
                        if img_dt is not None:
                            img_timestamp = img_dt.timestamp()
                        elif metadata.get("system:time_start"):
                            try:
                                img_timestamp = int(metadata["system:time_start"]) / 1000
                            except Exception:
                                pass
                        
                        detailed_stats = {
                            "satellite": sat_name,
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": sun_zen_val,
                            "view_zenith": None,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 30.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0,  # Use 0.0 instead of None
                            "timestamp": img_timestamp  # Store timestamp for gap-filling (avoids API calls)
                        }
                        
                        # STEP 4: Report test result with complete data
                        if test_callback:
                            test_callback(tile_idx, test_num, key, img_date_str, quality_score, None, detailed_stats)
                        
                        # Update satellite_detailed_stats
                        if sat_name not in satellite_detailed_stats or quality_score > satellite_detailed_stats[sat_name]["quality_score"]:
                            satellite_detailed_stats[sat_name] = detailed_stats
                        
                        # Continue with band selection using collected bands
                        try:
                            if not bands:
                                bands = img_p.bandNames().getInfo()
                            
                            if tile_idx is not None:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key} {img_date_str} Test {test_num:02d}: Available bands: {bands}")
                            
                            # Get RGB bands - check both original and renamed bands
                            sel = []
                            # Try renamed bands first (after landsat_prepare_image)
                            for candidate in ["B4","B3","B2"]:
                                if candidate in bands and len(sel) < 3:
                                    sel.append(candidate)
                            # If not found, try original Landsat band names
                            if len(sel) < 3:
                                for candidate in ["SR_B4","SR_B3","SR_B2"]:
                                    if candidate in bands and len(sel) < 3:
                                        sel.append(candidate)
                            # If still not found, try older Landsat names (B1, B2, B3 for L5/L7)
                            if len(sel) < 3:
                                # Older Landsat might use different band order
                                # Check if we have any RGB-like bands
                                for candidate in bands:
                                    if candidate in ["B1","B2","B3","B4","B5","B6","B7"] and len(sel) < 3:
                                        # For older Landsat: B1=Blue, B2=Green, B3=Red
                                        if candidate in ["B1","B2","B3"]:
                                            sel.append(candidate)
                            
                            # Allow images with missing bands - they'll be filled from fallback images via qualityMosaic
                            # Just log a warning if RGB bands are incomplete
                            if len(sel) < 3:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key} {img_date_str} Test {test_num:02d}: Partial RGB bands ({len(sel)}/3). Missing bands will be filled from fallback images. Available bands: {bands}")
                            
                            # Require at least one band to be present (can't add image with zero bands)
                            if len(sel) == 0:
                                logging.warning(f"[Tile {_fmt_idx(tile_idx)}] {key} {img_date_str} Test {test_num:02d}: No RGB bands found. Available bands: {bands}")
                                if test_callback:
                                    test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED (no RGB bands found)")
                                continue
                            
                            # Add IR bands (ONLY raw bands - indices created AFTER mosaic)
                            ir_bands = []
                            if "B8" in bands:
                                ir_bands.append("B8")
                            elif "SR_B5" in bands:
                                ir_bands.append("SR_B5")
                            if "B11" in bands:
                                ir_bands.append("B11")
                            elif "SR_B6" in bands:
                                ir_bands.append("SR_B6")
                            if "B12" in bands:
                                ir_bands.append("B12")
                            elif "SR_B7" in bands:
                                ir_bands.append("SR_B7")
                            
                            # NO INDICES HERE - indices are created AFTER qualityMosaic unifies all bands
                            # This allows qualityMosaic to fill missing bands from fallback images
                            
                            # Combine only raw bands
                            all_bands = sel[:3] + ir_bands
                            
                            img_sel = img_p.select(all_bands)
                        except Exception as e:
                            logging.debug(f"Landsat {key} image failed band selection: {e}")
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        img_sel = img_sel.addBands(quality_band)
                        # CRITICAL: Standardize RAW bands BEFORE adding to collection to ensure homogeneous band structure
                        # This ensures all images have the same RAW bands (B4, B3, B2, B8, B11, B12, quality)
                        # Indices are created AFTER qualityMosaic unifies all bands
                        img_sel = standardize_raw_bands_for_collection(img_sel)
                        
                        # ADAPTIVE QUALITY THRESHOLD: Start high, lower incrementally until images are found
                        # This ensures that even poor quality images (e.g., Landsat 4) are used if they're all we have
                        # Progressive lowering: 0.9 -> 0.7 -> 0.5 -> 0.3 -> 0.1 -> 0.0
                        
                        # Check if we should lower threshold (no images accepted yet and we've tested multiple)
                        # Use pre-computed MIN_TESTS_BEFORE_LOWERING based on total available images
                        if images_accepted == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and quality_threshold > 0.0:
                            old_threshold = quality_threshold
                            if quality_threshold >= 0.9:
                                quality_threshold = 0.7
                            elif quality_threshold >= 0.7:
                                quality_threshold = 0.5
                            elif quality_threshold >= 0.5:
                                quality_threshold = 0.3
                            elif quality_threshold >= 0.3:
                                quality_threshold = 0.1
                            else:
                                quality_threshold = 0.0
                            
                            if quality_threshold != old_threshold:
                                threshold_lowered = True
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Lowered quality threshold for {sat_name} from {old_threshold:.1f} to {quality_threshold:.1f} (no images found at higher threshold)")
                        
                        # Track best rejected image for fallback (always track after quality calculation)
                        if quality_score > best_rejected_score_landsat:
                            best_rejected_score_landsat = quality_score
                            # Will store the prepared image after band selection
                            best_rejected_image_landsat = (img_p, quality_score, detailed_stats, img_date_str, bands, key, sat_name)
                        
                        # Accept image if it meets current threshold (or if at minimum threshold of 0.0)
                        if quality_score < quality_threshold and quality_threshold > 0.0:
                            if test_callback:
                                test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED (quality {quality_score:.3f} < threshold {quality_threshold:.1f})")
                            logging.debug(f"Landsat {key} image skipped: quality score {quality_score:.3f} < threshold {quality_threshold:.1f}")
                            continue
                        
                        # Image accepted - increment counter
                        images_accepted += 1
                        
                        # TWO-PHASE APPROACH: Track excellent images and stop after finding target number
                        if quality_score >= EXCELLENT_QUALITY_THRESHOLD:
                            excellent_count_for_sat += 1
                            if sat_name not in excellent_per_satellite:
                                excellent_per_satellite[sat_name] = []
                            excellent_per_satellite[sat_name].append((img_sel, quality_score, detailed_stats.copy()))
                            prepared_excellent.append(img_sel)
                        
                        prepared.append(img_sel)
                        # Store timestamp for gap-filling (avoid API calls later)
                        prepared_timestamps.append(img_timestamp if img_timestamp is not None else None)
                        # Format satellite name for histogram
                        sat_name = key.replace("LANDSAT_", "Landsat-").replace("_", "-")
                        satellite_contributions.append(sat_name)
                        # Track best quality score for this satellite
                        if sat_name not in satellite_quality_scores or quality_score > satellite_quality_scores[sat_name]:
                            satellite_quality_scores[sat_name] = quality_score
                        
                        # Track this image for fallback ranking
                        all_image_stats.append((img_sel, quality_score, detailed_stats.copy(), sat_name))
                        
                        # Debug: Log successful addition to prepared list
                        if tile_idx is not None:
                            logging.debug(f"[Tile {tile_idx:04d}] {sat_name} image added to prepared list with quality score {quality_score:.3f}")
                        
                        # Stop searching THIS satellite after finding target number of excellent images
                        if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                            logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Found {excellent_count_for_sat} excellent images from {sat_name}, continuing to next satellite")
                            break
                        
                        # Track the single best image overall (highest quality score)
                        # CRITICAL: Always prioritize higher quality score when difference is > 5%
                        # Only use band completeness as tiebreaker when scores are truly close
                        score_diff = quality_score - best_score
                        if score_diff > 0.05:  # Clear winner (5%+ better) - always use higher score
                            if tile_idx is not None:
                                logging.debug(f"[Tile {tile_idx:04d}] New best image: {sat_name} (score: {quality_score:.3f}, previous best: {best_score:.3f})")
                            best_score = quality_score
                            best_image = img_sel
                            best_satellite_name = sat_name
                            best_detailed_stats = satellite_detailed_stats.get(sat_name)
                        elif abs(score_diff) <= 0.05:  # Scores are truly close (within 5% in either direction)
                            # Only in this case, use band completeness as tiebreaker
                            try:
                                current_bands = img_sel.bandNames().getInfo()
                                current_completeness = check_band_completeness(current_bands)
                                
                                if best_image is not None:
                                    best_bands = best_image.bandNames().getInfo()
                                    best_completeness = check_band_completeness(best_bands)
                                    
                                    # If current image has significantly better completeness (>10%), prefer it
                                    # But only if scores are close (already checked above)
                                    if current_completeness > best_completeness + 0.1:  # 10% threshold
                                        best_score = quality_score
                                        best_image = img_sel
                                        best_satellite_name = sat_name
                                        best_detailed_stats = satellite_detailed_stats.get(sat_name)
                                    elif quality_score > best_score:  # If completeness similar, use higher score
                                        best_score = quality_score
                                        best_image = img_sel
                                        best_satellite_name = sat_name
                                        best_detailed_stats = satellite_detailed_stats.get(sat_name)
                                else:
                                    best_score = quality_score
                                    best_image = img_sel
                                    best_satellite_name = sat_name
                                    best_detailed_stats = satellite_detailed_stats.get(sat_name)
                            except Exception:
                                # Fallback: use higher score if band check fails
                                if quality_score > best_score:
                                    best_score = quality_score
                                    best_image = img_sel
                                    best_satellite_name = sat_name
                                    best_detailed_stats = satellite_detailed_stats.get(sat_name)
                            # If score is significantly lower (< -0.05), don't update
                    except Exception as e:
                        # img_sel may not be defined if exception occurred before band selection
                        error_msg = str(e)
                        logging.debug(f"Skipping {key} image {idx}: {error_msg}")
                        continue
                
                # FALLBACK: If no images were accepted but we tested some, use the best one we saw
                # Priority: 1) Best rejected by quality, 2) Best rejected by clouds (clouds better than holes)
                if images_accepted == 0 and len(images_to_process) > 0:
                    # First try: use best rejected by quality (if we calculated quality scores)
                    if best_rejected_image_landsat is not None:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: No images passed thresholds, using best rejected image (quality={best_rejected_score_landsat:.3f})")
                        try:
                            img_p_fallback_landsat, quality_score_fallback_landsat, detailed_stats_fallback_landsat, img_date_str_fallback_landsat, bands_fallback_landsat, key_fallback_landsat, sat_name_fallback_landsat = best_rejected_image_landsat
                            # Get RGB bands
                            sel_fallback_landsat = []
                            for candidate in ["B4","B3","B2"]:
                                if candidate in bands_fallback_landsat and len(sel_fallback_landsat) < 3:
                                    sel_fallback_landsat.append(candidate)
                            if len(sel_fallback_landsat) < 3:
                                for candidate in ["SR_B4","SR_B3","SR_B2"]:
                                    if candidate in bands_fallback_landsat and len(sel_fallback_landsat) < 3:
                                        sel_fallback_landsat.append(candidate)
                            if len(sel_fallback_landsat) > 0:
                                ir_bands_fallback_landsat = []
                                if "B8" in bands_fallback_landsat:
                                    ir_bands_fallback_landsat.append("B8")
                                elif "SR_B5" in bands_fallback_landsat:
                                    ir_bands_fallback_landsat.append("SR_B5")
                                if "B11" in bands_fallback_landsat:
                                    ir_bands_fallback_landsat.append("B11")
                                all_bands_fallback_landsat = sel_fallback_landsat + ir_bands_fallback_landsat
                                img_sel_fallback_landsat = img_p_fallback_landsat.select(all_bands_fallback_landsat)
                                quality_band_fallback_landsat = ee.Image.constant(float(quality_score_fallback_landsat)).toFloat().rename("quality")
                                img_sel_fallback_landsat = img_sel_fallback_landsat.addBands(quality_band_fallback_landsat)
                                img_sel_fallback_landsat = standardize_raw_bands_for_collection(img_sel_fallback_landsat)
                                prepared.append(img_sel_fallback_landsat)
                                satellite_contributions.append(sat_name_fallback_landsat)
                                if sat_name_fallback_landsat not in satellite_quality_scores or quality_score_fallback_landsat > satellite_quality_scores[sat_name_fallback_landsat]:
                                    satellite_quality_scores[sat_name_fallback_landsat] = quality_score_fallback_landsat
                                all_image_stats.append((img_sel_fallback_landsat, quality_score_fallback_landsat, detailed_stats_fallback_landsat.copy(), sat_name_fallback_landsat))
                                images_accepted = 1
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Error using quality fallback image: {e}")
                    # Second try: use best rejected by clouds (if all failed cloud checks before quality calculation)
                    elif best_rejected_by_clouds_landsat is not None and images_accepted_after_clouds == 0:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: No images passed cloud checks, using best rejected by clouds ({best_rejected_cloud_pct_landsat*100:.1f}% clouds - clouds better than holes)")
                        try:
                            img_cloud_fallback_landsat, metadata_cloud_fallback_landsat, img_date_str_cloud_fallback_landsat, cf_fallback_landsat, vf_cloud_fallback_landsat, key_cloud_fallback_landsat = best_rejected_by_clouds_landsat
                            # Calculate cloud fraction if not already calculated
                            if vf_cloud_fallback_landsat is None:
                                cf_fallback_landsat, vf_cloud_fallback_landsat = estimate_cloud_fraction(img_cloud_fallback_landsat, geom)
                            # Prepare the image fully (even with clouds)
                            img_p_cloud_fallback_landsat = landsat_prepare_image(img_cloud_fallback_landsat)
                            if enable_harmonize:
                                img_p_cloud_fallback_landsat = harmonize_image(img_p_cloud_fallback_landsat, "LS_to_LS")
                            # Get band names
                            try:
                                bands_cloud_fallback_landsat = img_p_cloud_fallback_landsat.bandNames().getInfo()
                            except Exception:
                                bands_cloud_fallback_landsat = []
                            # Select bands
                            sel_cloud_fallback_landsat = []
                            for candidate in ["B4","B3","B2"]:
                                if candidate in bands_cloud_fallback_landsat and len(sel_cloud_fallback_landsat) < 3:
                                    sel_cloud_fallback_landsat.append(candidate)
                            if len(sel_cloud_fallback_landsat) < 3:
                                for candidate in ["SR_B4","SR_B3","SR_B2"]:
                                    if candidate in bands_cloud_fallback_landsat and len(sel_cloud_fallback_landsat) < 3:
                                        sel_cloud_fallback_landsat.append(candidate)
                            if len(sel_cloud_fallback_landsat) > 0:
                                ir_bands_cloud_fallback_landsat = []
                                if "B8" in bands_cloud_fallback_landsat:
                                    ir_bands_cloud_fallback_landsat.append("B8")
                                elif "SR_B5" in bands_cloud_fallback_landsat:
                                    ir_bands_cloud_fallback_landsat.append("SR_B5")
                                if "B11" in bands_cloud_fallback_landsat:
                                    ir_bands_cloud_fallback_landsat.append("B11")
                                all_bands_cloud_fallback_landsat = sel_cloud_fallback_landsat + ir_bands_cloud_fallback_landsat
                                img_sel_cloud_fallback_landsat = img_p_cloud_fallback_landsat.select(all_bands_cloud_fallback_landsat)
                                # Calculate quality score (even if low, use it)
                                sun_zen_val_cloud_landsat = None
                                try:
                                    if metadata_cloud_fallback_landsat.get("SUN_ELEVATION") is not None:
                                        sun_elev = float(metadata_cloud_fallback_landsat["SUN_ELEVATION"])
                                        sun_zen_val_cloud_landsat = 90.0 - sun_elev
                                except Exception:
                                    pass
                                try:
                                    if metadata_cloud_fallback_landsat.get("system:time_start"):
                                        days_since_cloud_landsat = (datetime.fromtimestamp(int(metadata_cloud_fallback_landsat["system:time_start"]) / 1000) - start_date).days
                                    else:
                                        days_since_cloud_landsat = None
                                except Exception:
                                    days_since_cloud_landsat = None
                                try:
                                    band_completeness_cloud_landsat = check_band_completeness(bands_cloud_fallback_landsat)
                                except Exception:
                                    band_completeness_cloud_landsat = None
                                quality_score_cloud_fallback_landsat = compute_quality_score(cf_fallback_landsat, sun_zen_val_cloud_landsat, None, vf_cloud_fallback_landsat, days_since_cloud_landsat, max_days, native_resolution=30.0, band_completeness=band_completeness_cloud_landsat)
                                quality_band_cloud_fallback_landsat = ee.Image.constant(float(quality_score_cloud_fallback_landsat)).toFloat().rename("quality")
                                img_sel_cloud_fallback_landsat = img_sel_cloud_fallback_landsat.addBands(quality_band_cloud_fallback_landsat)
                                img_sel_cloud_fallback_landsat = standardize_raw_bands_for_collection(img_sel_cloud_fallback_landsat)
                                prepared.append(img_sel_cloud_fallback_landsat)
                                sat_name_cloud_fallback_landsat = key_cloud_fallback_landsat.replace("LANDSAT_", "Landsat-").replace("_", "-")
                                satellite_contributions.append(sat_name_cloud_fallback_landsat)
                                if sat_name_cloud_fallback_landsat not in satellite_quality_scores or quality_score_cloud_fallback_landsat > satellite_quality_scores[sat_name_cloud_fallback_landsat]:
                                    satellite_quality_scores[sat_name_cloud_fallback_landsat] = quality_score_cloud_fallback_landsat
                                all_image_stats.append((img_sel_cloud_fallback_landsat, quality_score_cloud_fallback_landsat, {"satellite": sat_name_cloud_fallback_landsat, "quality_score": quality_score_cloud_fallback_landsat, "cloud_fraction": cf_fallback_landsat}.copy(), sat_name_cloud_fallback_landsat))
                                images_accepted = 1
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Error using cloud fallback image: {e}")
            except Exception as e:
                logging.debug(f"Error processing {key}: {e}")
                continue
    
    # Process SPOT - Higher resolution (10-20m) than Landsat, good for 1986-2013 period
    # SPOT has similar spectral bands to Landsat, making it compatible for mosaicking
    if include_spot:
        try:
            spot_col = spot_collection(start, end)
            if spot_col is None:
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Skipping SPOT: not operational during requested date range")
            else:
                spot_col = spot_col.filterBounds(geom)
                try:
                    spot_count = int(spot_col.size().getInfo())
                except Exception as e:
                    error_msg = str(e)
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Quota/rate limit error while checking SPOT collection size: {e}")
                    else:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error checking SPOT collection size: {e}")
                    spot_count = 0
                
                if spot_count > 0:
                    # SPOT processing similar to Landsat
                    sat_name = "SPOT"
                    test_num = 0
                    excellent_count_for_sat = 0
                    quality_threshold = 0.9
                    cloud_threshold_metadata = 20.0
                    cloud_fraction_threshold = 0.2
                    images_accepted = 0
                    images_accepted_after_clouds = 0
                    
                    # Fallback tracking
                    best_rejected_image_spot = None
                    best_rejected_score_spot = -1.0
                    best_rejected_detailed_stats_spot = None
                    best_rejected_by_clouds_spot = None
                    best_rejected_cloud_pct_spot = 999.0
                    
                    # Process up to MAX_IMAGES_TO_PROCESS SPOT images
                    max_images = MAX_IMAGES_TO_PROCESS if 'MAX_IMAGES_TO_PROCESS' in locals() else MAX_IMAGES_PER_SATELLITE
                    images_to_process = []
                    for i in range(min(spot_count, max_images)):
                        img = ee.Image(spot_col.toList(spot_count).get(i))
                        images_to_process.append(img)
                    
                    # Batch fetch metadata
                    metadata_list = extract_metadata_parallel(images_to_process, server_mode=server_mode)
                    
                    for idx, img in enumerate(images_to_process):
                        if idx >= len(metadata_list):
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Skipping image {idx} (no metadata available)")
                            break
                        
                        metadata = metadata_list[idx]
                        test_num += 1
                        
                        img_date_str = start
                        img_dt = None
                        try:
                            if metadata.get("system:time_start"):
                                img_dt = datetime.fromtimestamp(int(metadata["system:time_start"]) / 1000)
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                        
                        # Adaptive cloud thresholds (similar to Landsat)
                        if images_accepted_after_clouds == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and cloud_threshold_metadata < 80.0:
                            cloud_threshold_metadata = min(cloud_threshold_metadata + 10.0, 80.0)
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Lowering cloud threshold to {cloud_threshold_metadata}% (no images accepted yet)")
                        
                        if images_accepted_after_clouds == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and cloud_fraction_threshold < 0.8:
                            cloud_fraction_threshold = min(cloud_fraction_threshold + 0.1, 0.8)
                        
                        # SPOT doesn't have built-in cloud metadata like Landsat
                        # Calculate cloud fraction directly
                        try:
                            cf, vf = estimate_cloud_fraction(img, geom)
                        except Exception:
                            cf, vf = 0.0, 1.0
                        
                        if cf > cloud_fraction_threshold:
                            if cf * 100 < best_rejected_cloud_pct_spot:
                                best_rejected_cloud_pct_spot = cf * 100
                                best_rejected_by_clouds_spot = (img, None, None, None, img_date_str, None)
                            if test_callback:
                                test_callback(tile_idx, test_num, sat_name, img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        images_accepted_after_clouds += 1
                        
                        # Prepare SPOT image
                        try:
                            img_p = prepare_spot_image(img)
                            if enable_harmonize:
                                img_p = harmonize_image(img_p, mode="SPOT_to_LS")
                            
                            # Calculate quality score
                            try:
                                quality_score, detailed_stats = compute_quality_score(img_p, geom, "SPOT")
                                
                                # Store timestamp in detailed_stats for gap-filling
                                if img_dt is not None:
                                    detailed_stats["timestamp"] = img_dt
                                    detailed_stats["img_date_str"] = img_date_str
                            except Exception as e:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Error computing quality score: {e}")
                                quality_score = 0.5
                                detailed_stats = {}
                            
                            # Adaptive quality threshold
                            if images_accepted == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and quality_threshold > 0.0:
                                quality_threshold = max(quality_threshold - 0.1, 0.0)
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Lowering quality threshold to {quality_threshold:.2f} (no images accepted yet)")
                            
                            if quality_score < quality_threshold and quality_threshold > 0.0:
                                if quality_score > best_rejected_score_spot:
                                    best_rejected_score_spot = quality_score
                                    best_rejected_image_spot = (img_p, quality_score, detailed_stats, img_date_str, None)
                                if test_callback:
                                    test_callback(tile_idx, test_num, sat_name, img_date_str, quality_score, f"SKIPPED (quality {quality_score:.2f} < {quality_threshold:.2f})")
                                continue
                            
                            # Standardize bands and add to collection
                            img_sel = standardize_raw_bands_for_collection(img_p.select(["B4", "B3", "B2", "B8", "B11", "B12"]))
                            quality_band = ee.Image.constant(quality_score).rename("quality")
                            img_sel = img_sel.addBands(quality_band)
                            
                            prepared.append(img_sel)
                            if img_dt is not None:
                                prepared_timestamps.append(int(img_dt.timestamp()))
                            images_accepted += 1
                            excellent_count_for_sat += 1
                            
                            if test_callback:
                                test_callback(tile_idx, test_num, sat_name, img_date_str, quality_score, "ACCEPTED")
                            
                            if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                                break
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Error processing image {idx}: {e}")
                            continue
                    
                    # Fallback: use best rejected image if no images accepted
                    if images_accepted == 0:
                        if best_rejected_image_spot is not None and len(images_to_process) > 0:
                            img_p, quality_score, detailed_stats, img_date_str, _ = best_rejected_image_spot
                            img_sel = standardize_raw_bands_for_collection(img_p.select(["B4", "B3", "B2", "B8", "B11", "B12"]))
                            quality_band = ee.Image.constant(quality_score).rename("quality")
                            img_sel = img_sel.addBands(quality_band)
                            prepared.append(img_sel)
                            if detailed_stats.get("timestamp"):
                                prepared_timestamps.append(int(detailed_stats["timestamp"].timestamp()))
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Using best rejected image (quality={quality_score:.2f}) as fallback")
                        elif best_rejected_by_clouds_spot is not None and len(images_to_process) > 0:
                            img, _, _, _, img_date_str, _ = best_rejected_by_clouds_spot
                            try:
                                img_p = prepare_spot_image(img)
                                if enable_harmonize:
                                    img_p = harmonize_image(img_p, mode="SPOT_to_LS")
                                quality_score, detailed_stats = compute_quality_score(img_p, geom, "SPOT")
                                img_sel = standardize_raw_bands_for_collection(img_p.select(["B4", "B3", "B2", "B8", "B11", "B12"]))
                                quality_band = ee.Image.constant(quality_score).rename("quality")
                                img_sel = img_sel.addBands(quality_band)
                                prepared.append(img_sel)
                                if detailed_stats.get("timestamp"):
                                    prepared_timestamps.append(int(detailed_stats["timestamp"].timestamp()))
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Using best rejected-by-clouds image (cloud={best_rejected_cloud_pct_spot:.1f}%) as fallback")
                            except Exception as e:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] SPOT: Error processing fallback image: {e}")
        except Exception as e:
            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error processing SPOT: {e}")
    
    # Process Landsat MSS - Lower resolution (60m) but fills 1972-1983 period
    # MSS has different bands than TM/ETM+, but we standardize them for compatibility
    if include_mss:
        try:
            mss_cols = landsat_mss_collections(start, end)
            for key, mss_col in mss_cols.items():
                if mss_col is None:
                    continue
                
                try:
                    mss_col = mss_col.filterBounds(geom).filterDate(start, end).sort("CLOUD_COVER")
                    mss_count = int(mss_col.size().getInfo())
                except Exception as e:
                    error_msg = str(e)
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Quota/rate limit error while checking {key} collection size: {e}")
                    else:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error checking {key} collection size: {e}")
                    continue
                
                if mss_count == 0:
                    continue
                
                # MSS processing similar to Landsat
                sat_name = key
                test_num = 0
                excellent_count_for_sat = 0
                quality_threshold = 0.9
                cloud_threshold_metadata = 20.0
                cloud_fraction_threshold = 0.2
                images_accepted = 0
                images_accepted_after_clouds = 0
                
                # Fallback tracking
                best_rejected_image_mss = None
                best_rejected_score_mss = -1.0
                best_rejected_detailed_stats_mss = None
                best_rejected_by_clouds_mss = None
                best_rejected_cloud_pct_mss = 999.0
                
                # Process up to MAX_IMAGES_TO_PROCESS MSS images
                max_images = MAX_IMAGES_TO_PROCESS if 'MAX_IMAGES_TO_PROCESS' in locals() else MAX_IMAGES_PER_SATELLITE
                images_to_process = []
                for i in range(min(mss_count, max_images)):
                    img = ee.Image(mss_col.toList(mss_count).get(i))
                    images_to_process.append(img)
                
                # Batch fetch metadata
                metadata_list = extract_metadata_parallel(images_to_process, server_mode=server_mode)
                
                for idx, img in enumerate(images_to_process):
                    if idx >= len(metadata_list):
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Skipping image {idx} (no metadata available)")
                        break
                    
                    metadata = metadata_list[idx]
                    test_num += 1
                    
                    img_date_str = start
                    img_dt = None
                    try:
                        if metadata.get("system:time_start"):
                            img_dt = datetime.fromtimestamp(int(metadata["system:time_start"]) / 1000)
                            img_date_str = img_dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                    
                    # Adaptive cloud thresholds
                    if images_accepted_after_clouds == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and cloud_fraction_threshold < 0.8:
                        cloud_fraction_threshold = min(cloud_fraction_threshold + 0.1, 0.8)
                    
                    # MSS doesn't have built-in cloud metadata like Landsat TM
                    # Calculate cloud fraction directly
                    try:
                        cf, vf = estimate_cloud_fraction(img, geom)
                    except Exception:
                        cf, vf = 0.0, 1.0
                    
                    if cf > cloud_fraction_threshold:
                        if cf * 100 < best_rejected_cloud_pct_mss:
                            best_rejected_cloud_pct_mss = cf * 100
                            best_rejected_by_clouds_mss = (img, None, None, None, img_date_str, None)
                        if test_callback:
                            test_callback(tile_idx, test_num, sat_name, img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                        continue
                    
                    images_accepted_after_clouds += 1
                    
                    # Prepare MSS image
                    try:
                        img_p = prepare_landsat_mss_image(img)
                        if enable_harmonize:
                            img_p = harmonize_image(img_p, mode="MSS_to_LS")
                        
                        # Calculate quality score
                        try:
                            quality_score, detailed_stats = compute_quality_score(img_p, geom, "MSS")
                            
                            # Store timestamp in detailed_stats for gap-filling
                            if img_dt is not None:
                                detailed_stats["timestamp"] = img_dt
                                detailed_stats["img_date_str"] = img_date_str
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Error computing quality score: {e}")
                            quality_score = 0.5
                            detailed_stats = {}
                        
                        # Adaptive quality threshold
                        if images_accepted == 0 and test_num >= MIN_TESTS_BEFORE_LOWERING and quality_threshold > 0.0:
                            quality_threshold = max(quality_threshold - 0.1, 0.0)
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Lowering quality threshold to {quality_threshold:.2f} (no images accepted yet)")
                        
                        if quality_score < quality_threshold and quality_threshold > 0.0:
                            if quality_score > best_rejected_score_mss:
                                best_rejected_score_mss = quality_score
                                best_rejected_image_mss = (img_p, quality_score, detailed_stats, img_date_str, None)
                            if test_callback:
                                test_callback(tile_idx, test_num, sat_name, img_date_str, quality_score, f"SKIPPED (quality {quality_score:.2f} < {quality_threshold:.2f})")
                            continue
                        
                        # Standardize bands and add to collection
                        img_sel = standardize_raw_bands_for_collection(img_p.select(["B4", "B3", "B2", "B8", "B11", "B12"]))
                        quality_band = ee.Image.constant(quality_score).rename("quality")
                        img_sel = img_sel.addBands(quality_band)
                        
                        prepared.append(img_sel)
                        if img_dt is not None:
                            prepared_timestamps.append(int(img_dt.timestamp()))
                        images_accepted += 1
                        excellent_count_for_sat += 1
                        
                        if test_callback:
                            test_callback(tile_idx, test_num, sat_name, img_date_str, quality_score, "ACCEPTED")
                        
                        if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                            break
                    except Exception as e:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Error processing image {idx}: {e}")
                        continue
                
                # Fallback: use best rejected image if no images accepted
                if images_accepted == 0:
                    if best_rejected_image_mss is not None and len(images_to_process) > 0:
                        img_p, quality_score, detailed_stats, img_date_str, _ = best_rejected_image_mss
                        img_sel = standardize_raw_bands_for_collection(img_p.select(["B4", "B3", "B2", "B8", "B11", "B12"]))
                        quality_band = ee.Image.constant(quality_score).rename("quality")
                        img_sel = img_sel.addBands(quality_band)
                        prepared.append(img_sel)
                        if detailed_stats.get("timestamp"):
                            prepared_timestamps.append(int(detailed_stats["timestamp"].timestamp()))
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Using best rejected image (quality={quality_score:.2f}) as fallback")
                    elif best_rejected_by_clouds_mss is not None and len(images_to_process) > 0:
                        img, _, _, _, img_date_str, _ = best_rejected_by_clouds_mss
                        try:
                            img_p = prepare_landsat_mss_image(img)
                            if enable_harmonize:
                                img_p = harmonize_image(img_p, mode="MSS_to_LS")
                            quality_score, detailed_stats = compute_quality_score(img_p, geom, "MSS")
                            img_sel = standardize_raw_bands_for_collection(img_p.select(["B4", "B3", "B2", "B8", "B11", "B12"]))
                            quality_band = ee.Image.constant(quality_score).rename("quality")
                            img_sel = img_sel.addBands(quality_band)
                            prepared.append(img_sel)
                            if detailed_stats.get("timestamp"):
                                prepared_timestamps.append(int(detailed_stats["timestamp"].timestamp()))
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Using best rejected-by-clouds image (cloud={best_rejected_cloud_pct_mss:.1f}%) as fallback")
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key}: Error processing fallback image: {e}")
        except Exception as e:
            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error processing Landsat MSS: {e}")
    
    # Process MODIS - LAST RESORT ONLY (only if no other satellite has <50% clouds)
    # MODIS should be tested and evaluated fairly like all other satellites
    # The 50% quality score penalty ensures it only wins when truly the best option
    # But it should still be in the running for fallback filling of missing bands/pixels
    if include_modis:
        try:
            modis_col = modis_collection(start, end)
            if modis_col is None:
                logging.debug("Skipping MODIS: not operational during requested date range")
            else:
                modis_col = modis_col.filterBounds(geom)
                # MODIS is LAST RESORT - only use if no other options available
                # Limit to fewer images since it's only for emergency cases
                modis_count = int(modis_col.size().getInfo())
                test_num = 0
                sat_name = "MODIS"
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                # MODIS: last resort - limit to fewer images
                # Server mode: slightly more MODIS images for better coverage
                modis_limit = MAX_IMAGES_PER_SATELLITE * 2 if server_mode else MAX_IMAGES_PER_SATELLITE
                for i in range(min(modis_count, modis_limit)):
                    try:
                        img = ee.Image(modis_col.toList(modis_count).get(i))
                        test_num += 1
                        
                        # Get image date for display
                        img_date_str = start
                        try:
                            img_date = img.get("system:time_start")
                            if img_date:
                                img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                        
                        # FIX: Calculate cloud fraction BEFORE masking (critical bug fix)
                        # MODIS cloud detection must happen on original image, not masked one
                        cf, vf = estimate_modis_cloud_fraction(img, geom)
                        
                        # Debug logging - show cloud fraction calculation
                        if tile_idx is not None:
                            logging.debug(f"[Tile {tile_idx:04d}] MODIS {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}% (calculated from state_1km band)")
                        
                        # MODIS should be tested fairly like all other satellites
                        # The 50% quality score penalty ensures it only wins when truly the best option
                        if cf > 0.2:  # Skip if >20% clouds (fair threshold, same as all satellites)
                            if test_callback:
                                test_callback(tile_idx, test_num, "MODIS", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        # Now prepare the image (this masks clouds)
                        img_p = prepare_modis_image(img)
                        
                        try:
                            img_date = img.get("system:time_start")
                            if img_date:
                                img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                                days_since = (img_dt - start_date).days
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                            else:
                                days_since = None
                        except Exception:
                            days_since = None
                        
                        # Handle negative days (image before start date)
                        if days_since is not None and days_since < 0:
                            days_since = 0  # Clamp to 0 for images before start date
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # Collect band information
                        try:
                            bands = img_p.bandNames().getInfo()
                            # Calculate band completeness from collected bands
                            try:
                                band_completeness = check_band_completeness(bands)
                            except Exception:
                                band_completeness = None
                        except Exception:
                            bands = []
                            band_completeness = None
                        
                        # STEP 2: Now calculate quality score ONCE with all complete data
                        # MODIS typically has higher view angles, so estimate
                        # MODIS native resolution: 250m - HEAVILY PENALIZED (last resort only)
                        # Apply severe penalty: MODIS should only win if everything else is >50% clouds
                        base_score = compute_quality_score(cf, None, 15.0, vf, days_since, max_days, native_resolution=250.0, band_completeness=band_completeness)
                        # Additional 50% penalty to make MODIS truly last resort
                        quality_score = base_score * 0.5
                        
                        # STEP 3: Create complete detailed stats with all collected data
                        # Store timestamp for gap-filling (to avoid API calls later)
                        img_timestamp_modis = None
                        try:
                            if metadata.get("system:time_start"):
                                img_timestamp_modis = int(metadata["system:time_start"]) / 1000
                        except Exception:
                            pass
                        
                        detailed_stats = {
                            "satellite": "MODIS",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": None,
                            "view_zenith": 15.0,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 250.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0,  # Use 0.0 instead of None
                            "timestamp": img_timestamp_modis  # Store timestamp for gap-filling (avoids API calls)
                        }
                        if "MODIS" not in satellite_detailed_stats or quality_score > satellite_detailed_stats["MODIS"]["quality_score"]:
                            satellite_detailed_stats["MODIS"] = detailed_stats
                        
                        # STEP 4: Report test result with complete data
                        if test_callback:
                            test_callback(tile_idx, test_num, "MODIS", img_date_str, quality_score, None, detailed_stats)
                        
                        # MODIS is tested fairly - cloud threshold already checked above (20%)
                        # The 50% quality score penalty ensures it only wins when truly the best option
                        
                        # Skip very low quality MODIS images (after penalty)
                        if quality_score < 0.2:  # Lower threshold since we already penalized heavily
                            continue
                        
                        # Harmonize MODIS (lower resolution, so scale appropriately)
                        if enable_harmonize:
                            img_p = img_p.multiply(1.05)  # Slight adjustment
                        
                        try:
                            band_names = img_p.bandNames().getInfo()
                            sel_bands = []
                            
                            # Select RGB bands (allow partial selection - missing bands filled from fallback)
                            if "B4" in band_names:
                                sel_bands.append("B4")
                            if "B3" in band_names:
                                sel_bands.append("B3")
                            if "B2" in band_names:
                                sel_bands.append("B2")
                            
                            # Require at least one band to be present
                            if len(sel_bands) == 0:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] MODIS {img_date_str} Test {test_num:02d}: No RGB bands found. Available bands: {band_names}")
                                continue
                            
                            # Log if RGB bands are incomplete
                            if len(sel_bands) < 3:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] MODIS {img_date_str} Test {test_num:02d}: Partial RGB bands ({len(sel_bands)}/3). Missing bands will be filled from fallback images.")
                            
                            # Add IR bands (ONLY raw bands - indices created AFTER mosaic)
                            if "B8" in band_names:
                                sel_bands.append("B8")
                            if "B11" in band_names:
                                sel_bands.append("B11")
                            if "B12" in band_names:
                                sel_bands.append("B12")
                            
                            # NO INDICES HERE - indices are created AFTER qualityMosaic unifies all bands
                            # This allows qualityMosaic to fill missing bands from fallback images
                            
                            sel = img_p.select(sel_bands)
                        except Exception as e:
                            logging.debug(f"MODIS band selection error: {e}")
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        sel = sel.addBands(quality_band)
                        # CRITICAL: Standardize RAW bands BEFORE adding to collection to ensure homogeneous band structure
                        # This ensures all images have the same RAW bands (B4, B3, B2, B8, B11, B12, quality)
                        # Indices are created AFTER qualityMosaic unifies all bands
                        sel = standardize_raw_bands_for_collection(sel)
                        
                        # TWO-PHASE APPROACH: Track excellent images per satellite (up to 3 per satellite)
                        if quality_score >= EXCELLENT_QUALITY_THRESHOLD:
                            excellent_count_for_sat += 1
                            if sat_name not in excellent_per_satellite:
                                excellent_per_satellite[sat_name] = []
                            excellent_per_satellite[sat_name].append((sel, quality_score, detailed_stats.copy()))
                            # Stop searching THIS satellite after finding 3 excellent images
                            if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Found {excellent_count_for_sat} excellent images from {sat_name}, continuing to next satellite")
                                break
                        
                        prepared.append(sel)
                        # Store timestamp for gap-filling (avoid API calls later) - use from detailed_stats
                        prepared_timestamps.append(img_timestamp_modis)
                        satellite_contributions.append("MODIS")
                        
                        # Track best quality score for this satellite
                        if "MODIS" not in satellite_quality_scores or quality_score > satellite_quality_scores["MODIS"]:
                            satellite_quality_scores["MODIS"] = quality_score
                        
                        # Track this image for fallback ranking
                        all_image_stats.append((sel, quality_score, detailed_stats.copy(), "MODIS"))
                        
                        # Track the single best image overall (highest quality score)
                        # CRITICAL: Always prioritize higher quality score when difference is > 5%
                        # Only use band completeness as tiebreaker when scores are truly close
                        score_diff = quality_score - best_score
                        if score_diff > 0.05:  # Clear winner (5%+ better) - always use higher score
                            best_score = quality_score
                            best_image = sel
                            best_satellite_name = "MODIS"
                            best_detailed_stats = satellite_detailed_stats.get("MODIS")
                        elif abs(score_diff) <= 0.05:  # Scores are truly close (within 5% in either direction)
                            # Only in this case, use band completeness as tiebreaker
                            try:
                                current_bands = sel.bandNames().getInfo()
                                current_completeness = check_band_completeness(current_bands)
                                
                                if best_image is not None:
                                    best_bands = best_image.bandNames().getInfo()
                                    best_completeness = check_band_completeness(best_bands)
                                    
                                    # If current image has significantly better completeness (>10%), prefer it
                                    # But only if scores are close (already checked above)
                                    if current_completeness > best_completeness + 0.1:  # 10% threshold
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = "MODIS"
                                        best_detailed_stats = satellite_detailed_stats.get("MODIS")
                                    elif quality_score > best_score:  # If completeness similar, use higher score
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = "MODIS"
                                        best_detailed_stats = satellite_detailed_stats.get("MODIS")
                                else:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = "MODIS"
                                    best_detailed_stats = satellite_detailed_stats.get("MODIS")
                            except Exception:
                                # Fallback: use higher score if band check fails
                                if quality_score > best_score:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = "MODIS"
                                    best_detailed_stats = satellite_detailed_stats.get("MODIS")
                        # If score is significantly lower (< -0.05), don't update
                    except Exception as e:
                        logging.debug(f"Skipping MODIS image {i}: {e}")
                        continue
        except Exception as e:
            logging.debug(f"Error processing MODIS: {e}")
    
    # Process ASTER (if available for date range)
    if include_aster:
        try:
            aster_col = aster_collection(start, end)
            if aster_col is None:
                logging.debug("Skipping ASTER: not operational during requested date range (ended 2008)")
            else:
                aster_col = aster_col.filterBounds(geom)
                aster_count = int(aster_col.size().getInfo())
                aster_cap = MAX_IMAGES_PER_SATELLITE
                test_num = 0
                sat_name = "ASTER"
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                for i in range(min(aster_count, aster_cap)):
                    try:
                        img = ee.Image(aster_col.toList(aster_count).get(i))
                        test_num += 1
                        
                        # Get image date for display
                        img_date_str = start
                        try:
                            img_date = img.get("system:time_start")
                            if img_date:
                                img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # CRITICAL: Calculate cloud fraction BEFORE masking
                        cf, vf = estimate_cloud_fraction(img, geom)  # Use original image, not masked
                        
                        # Debug logging for ASTER cloud fraction
                        if tile_idx is not None:
                            logging.debug(f"[Tile {tile_idx:04d}] ASTER {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}%")
                        
                        # OPTIMIZATION: Early exit if too cloudy
                        if cf > 0.2:  # Skip if >20% clouds (fair threshold for all satellites)
                            if test_callback:
                                test_callback(tile_idx, test_num, "ASTER", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        # Now prepare the image (this masks clouds)
                        img_p = prepare_aster_image(img)
                        
                        # Collect temporal data
                        try:
                            img_date = img.get("system:time_start")
                            if img_date:
                                img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                                days_since = (img_dt - start_date).days
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                            else:
                                days_since = None
                        except Exception:
                            days_since = None
                        
                        # Handle negative days (image before start date)
                        if days_since is not None and days_since < 0:
                            days_since = 0  # Clamp to 0 for images before start date
                        
                        # Collect band information
                        try:
                            bands = img_p.bandNames().getInfo()
                            # Calculate band completeness from collected bands
                            try:
                                band_completeness = check_band_completeness(bands)
                            except Exception:
                                band_completeness = None
                        except Exception:
                            bands = []
                            band_completeness = None
                        
                        # STEP 2: Now calculate quality score ONCE with all complete data
                        # ASTER native resolution: 15m
                        quality_score = compute_quality_score(cf, None, None, vf, days_since, max_days, native_resolution=15.0, band_completeness=band_completeness)
                        
                        # STEP 3: Create complete detailed stats with all collected data
                        # Store timestamp for gap-filling (to avoid API calls later)
                        img_timestamp_aster = None
                        try:
                            if img_dt is not None:
                                img_timestamp_aster = img_dt.timestamp()
                            else:
                                img_date = img.get("system:time_start")
                                if img_date:
                                    img_timestamp_aster = int(img_date.getInfo()) / 1000
                        except Exception:
                            pass
                        
                        detailed_stats = {
                            "satellite": "ASTER",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": None,
                            "view_zenith": None,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 15.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0,  # Use 0.0 instead of None
                            "timestamp": img_timestamp_aster  # Store timestamp for gap-filling (avoids API calls)
                        }
                        if "ASTER" not in satellite_detailed_stats or quality_score > satellite_detailed_stats["ASTER"]["quality_score"]:
                            satellite_detailed_stats["ASTER"] = detailed_stats
                        
                        # STEP 4: Report test result with complete data
                        if test_callback:
                            test_callback(tile_idx, test_num, "ASTER", img_date_str, quality_score, None, detailed_stats)
                        
                        try:
                            band_names = img_p.bandNames().getInfo()
                            sel_bands = []
                            
                            # Select RGB bands (allow partial selection - missing bands filled from fallback)
                            if "B4" in band_names:
                                sel_bands.append("B4")
                            if "B3" in band_names:
                                sel_bands.append("B3")
                            if "B2" in band_names:
                                sel_bands.append("B2")
                            
                            # Require at least one band to be present
                            if len(sel_bands) == 0:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] MODIS {img_date_str} Test {test_num:02d}: No RGB bands found. Available bands: {band_names}")
                                continue
                            
                            # Log if RGB bands are incomplete
                            if len(sel_bands) < 3:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] MODIS {img_date_str} Test {test_num:02d}: Partial RGB bands ({len(sel_bands)}/3). Missing bands will be filled from fallback images.")
                            
                            # Add IR bands (ONLY raw bands - indices created AFTER mosaic)
                            if "B8" in band_names:
                                sel_bands.append("B8")
                            if "B11" in band_names:
                                sel_bands.append("B11")
                            if "B12" in band_names:
                                sel_bands.append("B12")
                            
                            # NO INDICES HERE - indices are created AFTER qualityMosaic unifies all bands
                            # This allows qualityMosaic to fill missing bands from fallback images
                            
                            sel = img_p.select(sel_bands)
                        except Exception as e:
                            logging.debug(f"ASTER band selection error: {e}")
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        sel = sel.addBands(quality_band)
                        # CRITICAL: Standardize RAW bands BEFORE adding to collection to ensure homogeneous band structure
                        # This ensures all images have the same RAW bands (B4, B3, B2, B8, B11, B12, quality)
                        # Indices are created AFTER qualityMosaic unifies all bands
                        sel = standardize_raw_bands_for_collection(sel)
                        
                        # TWO-PHASE APPROACH: Track excellent images per satellite (up to 3 per satellite)
                        if quality_score >= EXCELLENT_QUALITY_THRESHOLD:
                            excellent_count_for_sat += 1
                            if sat_name not in excellent_per_satellite:
                                excellent_per_satellite[sat_name] = []
                            excellent_per_satellite[sat_name].append((sel, quality_score, detailed_stats.copy()))
                            # Stop searching THIS satellite after finding 3 excellent images
                            if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Found {excellent_count_for_sat} excellent images from {sat_name}, continuing to next satellite")
                                break
                        
                        prepared.append(sel)
                        # Store timestamp for gap-filling (avoid API calls later) - use from detailed_stats
                        prepared_timestamps.append(img_timestamp_aster)
                        satellite_contributions.append("ASTER")
                        
                        # Track this image for fallback ranking
                        all_image_stats.append((sel, quality_score, detailed_stats.copy(), "ASTER"))
                        # Track best quality score for this satellite
                        if "ASTER" not in satellite_quality_scores or quality_score > satellite_quality_scores["ASTER"]:
                            satellite_quality_scores["ASTER"] = quality_score
                        
                        # Track the single best image overall (highest quality score)
                        # CRITICAL: Always prioritize higher quality score when difference is > 5%
                        # Only use band completeness as tiebreaker when scores are truly close
                        score_diff = quality_score - best_score
                        if score_diff > 0.05:  # Clear winner (5%+ better) - always use higher score
                            best_score = quality_score
                            best_image = sel
                            best_satellite_name = "ASTER"
                            best_detailed_stats = satellite_detailed_stats.get("ASTER")
                        elif abs(score_diff) <= 0.05:  # Scores are truly close (within 5% in either direction)
                            # Only in this case, use band completeness as tiebreaker
                            try:
                                current_bands = sel.bandNames().getInfo()
                                current_completeness = check_band_completeness(current_bands)
                                
                                if best_image is not None:
                                    best_bands = best_image.bandNames().getInfo()
                                    best_completeness = check_band_completeness(best_bands)
                                    
                                    # If current image has significantly better completeness (>10%), prefer it
                                    # But only if scores are close (already checked above)
                                    if current_completeness > best_completeness + 0.1:  # 10% threshold
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = "ASTER"
                                        best_detailed_stats = satellite_detailed_stats.get("ASTER")
                                    elif quality_score > best_score:  # If completeness similar, use higher score
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = "ASTER"
                                        best_detailed_stats = satellite_detailed_stats.get("ASTER")
                                else:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = "ASTER"
                                    best_detailed_stats = satellite_detailed_stats.get("ASTER")
                            except Exception:
                                # Fallback: use higher score if band check fails
                                if quality_score > best_score:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = "ASTER"
                                    best_detailed_stats = satellite_detailed_stats.get("ASTER")
                        # If score is significantly lower (< -0.05), don't update
                    except Exception as e:
                        logging.debug(f"Skipping ASTER image {i}: {e}")
                        continue
        except Exception as e:
            logging.debug(f"Error processing ASTER: {e}")
    
    # Process VIIRS
    if include_viirs:
        try:
            viirs_col = viirs_collection(start, end)
            if viirs_col is None:
                logging.debug("Skipping VIIRS: not operational during requested date range (started 2011)")
            else:
                viirs_col = viirs_col.filterBounds(geom)
                viirs_count = int(viirs_col.size().getInfo())
                # Do NOT reassign the imported constant; use a local cap instead
                viirs_cap = min(20, MAX_IMAGES_PER_SATELLITE)
                test_num = 0
                sat_name = "VIIRS"
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                for i in range(min(viirs_count, viirs_cap)):
                    try:
                        img = ee.Image(viirs_col.toList(viirs_count).get(i))
                        test_num += 1
                        
                        # Get image date for display
                        img_date_str = start
                        try:
                            img_date = img.get("system:time_start")
                            if img_date:
                                img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # CRITICAL: Calculate cloud fraction BEFORE masking
                        cf, vf = estimate_cloud_fraction(img, geom)  # Use original image, not masked
                        
                        # Debug logging for VIIRS cloud fraction
                        if tile_idx is not None:
                            logging.debug(f"[Tile {tile_idx:04d}] VIIRS {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}%")
                        
                        # OPTIMIZATION: Early exit if too cloudy
                        if cf > 0.2:  # Skip if >20% clouds (fair threshold for all satellites)
                            if test_callback:
                                test_callback(tile_idx, test_num, "VIIRS", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        # Now prepare the image (this masks clouds)
                        img_p = prepare_viirs_image(img)
                        
                        # Collect temporal data
                        try:
                            img_date = img.get("system:time_start")
                            if img_date:
                                img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                                days_since = (img_dt - start_date).days
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                            else:
                                days_since = None
                        except Exception:
                            days_since = None
                        
                        # Handle negative days (image before start date)
                        if days_since is not None and days_since < 0:
                            days_since = 0  # Clamp to 0 for images before start date
                        
                        # Collect band information
                        try:
                            bands = img_p.bandNames().getInfo()
                            # Calculate band completeness from collected bands
                            try:
                                band_completeness = check_band_completeness(bands)
                            except Exception:
                                band_completeness = None
                        except Exception:
                            bands = []
                            band_completeness = None
                        
                        # STEP 2: Now calculate quality score ONCE with all complete data
                        # VIIRS native resolution: 375m
                        quality_score = compute_quality_score(cf, None, None, vf, days_since, max_days, native_resolution=375.0, band_completeness=band_completeness)
                        
                        # STEP 3: Create complete detailed stats with all collected data
                        # Store timestamp for gap-filling (to avoid API calls later)
                        img_timestamp_viirs = None
                        try:
                            if img_dt is not None:
                                img_timestamp_viirs = img_dt.timestamp()
                            else:
                                img_date = img.get("system:time_start")
                                if img_date:
                                    img_timestamp_viirs = int(img_date.getInfo()) / 1000
                        except Exception:
                            pass
                        
                        detailed_stats = {
                            "satellite": "VIIRS",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": None,
                            "view_zenith": None,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 375.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0,  # Use 0.0 instead of None
                            "timestamp": img_timestamp_viirs  # Store timestamp for gap-filling (avoids API calls)
                        }
                        if "VIIRS" not in satellite_detailed_stats or quality_score > satellite_detailed_stats["VIIRS"]["quality_score"]:
                            satellite_detailed_stats["VIIRS"] = detailed_stats
                        
                        # STEP 4: Report test result with complete data
                        if test_callback:
                            test_callback(tile_idx, test_num, "VIIRS", img_date_str, quality_score, None, detailed_stats)
                        
                        try:
                            band_names = img_p.bandNames().getInfo()
                            sel_bands = []
                            
                            # Select RGB bands (allow partial selection - missing bands filled from fallback)
                            if "B4" in band_names:
                                sel_bands.append("B4")
                            if "B3" in band_names:
                                sel_bands.append("B3")
                            if "B2" in band_names:
                                sel_bands.append("B2")
                            
                            # Require at least one band to be present
                            if len(sel_bands) == 0:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] MODIS {img_date_str} Test {test_num:02d}: No RGB bands found. Available bands: {band_names}")
                                continue
                            
                            # Log if RGB bands are incomplete
                            if len(sel_bands) < 3:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] MODIS {img_date_str} Test {test_num:02d}: Partial RGB bands ({len(sel_bands)}/3). Missing bands will be filled from fallback images.")
                            
                            # Add IR bands (ONLY raw bands - indices created AFTER mosaic)
                            if "B8" in band_names:
                                sel_bands.append("B8")
                            if "B11" in band_names:
                                sel_bands.append("B11")
                            if "B12" in band_names:
                                sel_bands.append("B12")
                            
                            # NO INDICES HERE - indices are created AFTER qualityMosaic unifies all bands
                            # This allows qualityMosaic to fill missing bands from fallback images
                            
                            sel = img_p.select(sel_bands)
                        except Exception as e:
                            logging.debug(f"VIIRS band selection error: {e}")
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        sel = sel.addBands(quality_band)
                        # CRITICAL: Standardize RAW bands BEFORE adding to collection to ensure homogeneous band structure
                        # This ensures all images have the same RAW bands (B4, B3, B2, B8, B11, B12, quality)
                        # Indices are created AFTER qualityMosaic unifies all bands
                        sel = standardize_raw_bands_for_collection(sel)
                        
                        # TWO-PHASE APPROACH: Track excellent images per satellite (up to 3 per satellite)
                        if quality_score >= EXCELLENT_QUALITY_THRESHOLD:
                            excellent_count_for_sat += 1
                            if sat_name not in excellent_per_satellite:
                                excellent_per_satellite[sat_name] = []
                            excellent_per_satellite[sat_name].append((sel, quality_score, detailed_stats.copy()))
                            # Stop searching THIS satellite after finding 3 excellent images
                            if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Found {excellent_count_for_sat} excellent images from {sat_name}, continuing to next satellite")
                                break
                        
                        prepared.append(sel)
                        # Store timestamp for gap-filling (avoid API calls later) - use from detailed_stats
                        prepared_timestamps.append(img_timestamp_viirs)
                        satellite_contributions.append("VIIRS")
                        # Track best quality score for this satellite
                        if "VIIRS" not in satellite_quality_scores or quality_score > satellite_quality_scores["VIIRS"]:
                            satellite_quality_scores["VIIRS"] = quality_score
                        
                        # Track this image for fallback ranking
                        all_image_stats.append((sel, quality_score, detailed_stats.copy(), "VIIRS"))
                        
                        # Track the single best image overall (highest quality score)
                        # CRITICAL: Always prioritize higher quality score when difference is > 5%
                        # Only use band completeness as tiebreaker when scores are truly close
                        score_diff = quality_score - best_score
                        if score_diff > 0.05:  # Clear winner (5%+ better) - always use higher score
                            best_score = quality_score
                            best_image = sel
                            best_satellite_name = "VIIRS"
                            best_detailed_stats = satellite_detailed_stats.get("VIIRS")
                        elif abs(score_diff) <= 0.05:  # Scores are truly close (within 5% in either direction)
                            # Only in this case, use band completeness as tiebreaker
                            try:
                                current_bands = sel.bandNames().getInfo()
                                current_completeness = check_band_completeness(current_bands)
                                
                                if best_image is not None:
                                    best_bands = best_image.bandNames().getInfo()
                                    best_completeness = check_band_completeness(best_bands)
                                    
                                    # If current image has significantly better completeness (>10%), prefer it
                                    # But only if scores are close (already checked above)
                                    if current_completeness > best_completeness + 0.1:  # 10% threshold
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = "VIIRS"
                                        best_detailed_stats = satellite_detailed_stats.get("VIIRS")
                                    elif quality_score > best_score:  # If completeness similar, use higher score
                                        best_score = quality_score
                                        best_image = sel
                                        best_satellite_name = "VIIRS"
                                        best_detailed_stats = satellite_detailed_stats.get("VIIRS")
                                else:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = "VIIRS"
                                    best_detailed_stats = satellite_detailed_stats.get("VIIRS")
                            except Exception:
                                # Fallback: use higher score if band check fails
                                if quality_score > best_score:
                                    best_score = quality_score
                                    best_image = sel
                                    best_satellite_name = "VIIRS"
                                    best_detailed_stats = satellite_detailed_stats.get("VIIRS")
                        # If score is significantly lower (< -0.05), don't update
                    except Exception as e:
                        logging.debug(f"Skipping VIIRS image {i}: {e}")
                        continue
        except Exception as e:
            logging.debug(f"Error processing VIIRS: {e}")
    
    # Process NOAA AVHRR - ABSOLUTE LAST RESORT ONLY
    # Only test if ALL other satellites failed to provide ANY usable images
    # AVHRR has very coarse resolution (1km), much worse than MODIS (250m-1km)
    # Only use when prepared list is completely empty
    if include_noaa and len(prepared) == 0:
        try:
            logging.warning(f"[Tile {_fmt_idx(tile_idx)}] All other satellites failed - attempting NOAA AVHRR as absolute last resort (1km resolution)")
            noaa_col = noaa_avhrr_collection(start, end)
            if noaa_col is None:
                # AVHRR collection not available in GEE - this is expected and acceptable
                # Since it's absolute last resort, just log and continue (tile will fail with no_imagery)
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] NOAA AVHRR not available in GEE catalog (collection may not exist)")
                # Don't log as error - this is expected behavior when AVHRR isn't in GEE
            else:
                noaa_col = noaa_col.filterBounds(geom)
                try:
                    noaa_count = int(noaa_col.size().getInfo())
                except Exception as e:
                    error_msg = str(e)
                    # Check if collection doesn't exist (expected - AVHRR may not be in GEE catalog)
                    if "not found" in error_msg.lower() or "does not exist" in error_msg.lower() or "does not have access" in error_msg.lower():
                        # This is expected - AVHRR collections may not be available in GEE
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] NOAA AVHRR collection not available in GEE (expected)")
                        noaa_count = 0
                    elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Quota/rate limit error while checking NOAA AVHRR collection size: {e}")
                        noaa_count = 0
                    else:
                        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error checking NOAA AVHRR collection size: {e}")
                        noaa_count = 0
                
                if noaa_count > 0:
                    # NOAA AVHRR processing - very lenient thresholds since it's last resort
                    sat_name = "NOAA_AVHRR"
                    test_num = 0
                    quality_threshold = 0.0  # Accept any quality since it's last resort
                    cloud_fraction_threshold = 0.8  # Very lenient cloud threshold
                    
                    # Process only a few images (AVHRR is last resort)
                    max_images = min(5, noaa_count)  # Only test 5 images max
                    images_to_process = []
                    for i in range(max_images):
                        img = ee.Image(noaa_col.toList(noaa_count).get(i))
                        images_to_process.append(img)
                    
                    # Batch fetch metadata
                    metadata_list = extract_metadata_parallel(images_to_process, server_mode=server_mode)
                    
                    for idx, img in enumerate(images_to_process):
                        if idx >= len(metadata_list):
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] NOAA AVHRR: Skipping image {idx} (no metadata available)")
                            break
                        
                        metadata = metadata_list[idx]
                        test_num += 1
                        
                        img_date_str = start
                        img_dt = None
                        try:
                            if metadata.get("system:time_start"):
                                img_dt = datetime.fromtimestamp(int(metadata["system:time_start"]) / 1000)
                                img_date_str = img_dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                        
                        # Very lenient cloud check (80% threshold)
                        try:
                            cf, vf = estimate_cloud_fraction(img, geom)
                        except Exception:
                            cf, vf = 0.0, 1.0
                        
                        if cf > cloud_fraction_threshold:
                            if test_callback:
                                test_callback(tile_idx, test_num, sat_name, img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        # Prepare NOAA AVHRR image
                        try:
                            img_p = prepare_noaa_avhrr_image(img)
                            if enable_harmonize:
                                img_p = harmonize_image(img_p, mode="AVHRR_to_LS")
                            
                            # Calculate quality score (will be low due to 1km resolution)
                            try:
                                quality_score, detailed_stats = compute_quality_score(img_p, geom, "NOAA_AVHRR")
                                
                                # Store timestamp in detailed_stats for gap-filling
                                if img_dt is not None:
                                    detailed_stats["timestamp"] = img_dt
                                    detailed_stats["img_date_str"] = img_date_str
                            except Exception as e:
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] NOAA AVHRR: Error computing quality score: {e}")
                                quality_score = 0.3  # Low quality score for AVHRR
                                detailed_stats = {}
                            
                            # Accept any quality (threshold is 0.0)
                            # Standardize bands and add to collection
                            img_sel = standardize_raw_bands_for_collection(img_p.select(["B4", "B3", "B2", "B8", "B11", "B12"]))
                            quality_band = ee.Image.constant(quality_score).rename("quality")
                            img_sel = img_sel.addBands(quality_band)
                            
                            prepared.append(img_sel)
                            if img_dt is not None:
                                prepared_timestamps.append(int(img_dt.timestamp()))
                            
                            if test_callback:
                                test_callback(tile_idx, test_num, sat_name, img_date_str, quality_score, "ACCEPTED (last resort)")
                            
                            logging.warning(f"[Tile {_fmt_idx(tile_idx)}] NOAA AVHRR: Using image {img_date_str} as absolute last resort (quality={quality_score:.2f}, resolution=1km)")
                            
                            # Only use first acceptable AVHRR image (it's last resort)
                            break
                        except Exception as e:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] NOAA AVHRR: Error processing image {idx}: {e}")
                            continue
        except Exception as e:
            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Error processing NOAA AVHRR: {e}")
    
    # TWO-PHASE APPROACH: Phase 1 - Select best images from all satellites
    # Collect best 3 from each satellite, then select the overall best
    all_excellent_candidates = []  # All excellent images from all satellites
    
    for sat_name, excellent_list in excellent_per_satellite.items():
        # Sort by quality score (descending) and take top 3
        sorted_excellent = sorted(excellent_list, key=lambda x: x[1], reverse=True)
        for img, score, stats in sorted_excellent[:TARGET_EXCELLENT_PER_SATELLITE]:
            all_excellent_candidates.append((img, score, stats, sat_name))
    
    # Sort all excellent candidates by quality score (descending)
    all_excellent_candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Select the best overall images (up to 3-5 best from all satellites combined)
    # This ensures we get the absolute best quality, not just best per satellite
    selected_best = []
    for img, score, stats, sat_name in all_excellent_candidates[:5]:  # Top 5 overall
        selected_best.append(img)
        prepared_excellent.append(img)
        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Phase 1: Selected best image from {sat_name} (score={score:.3f})")
    
    if len(selected_best) > 0:
        prepared = selected_best
        logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Phase 1: Selected {len(selected_best)} best images from {len(excellent_per_satellite)} satellites")
    elif len(prepared) == 0:
        empty_gap_stats = {
            "gaps_identified": 0,
            "gaps_filled": 0,
            "gaps_unfillable": 0,
            "gap_filling_attempts": 0,
            "images_added_for_gaps": 0,
            "unfillable_gap_details": [],
            "initial_coverage": 0.0,
            "final_coverage": 0.0,
            "coverage_improvement": 0.0
        }
        return None, None, None, None, [], empty_gap_stats
    
    # Create initial mosaic from selected best images
    col = ee.ImageCollection(prepared)
    
    # PHASE 2: Targeted gap-filling - focus on one gap area at a time
    # Detect gaps, test only intersecting images, skip already-applied images
    target_coverage = 0.999  # Practical ceiling; exact 1.0 often unattainable
    max_gap_iterations = 30 if server_mode else 20  # Server mode: more iterations for better coverage
    gap_filling_stats = {
        "gaps_identified": 0,
        "gaps_filled": 0,
        "gaps_unfillable": 0,
        "gap_filling_attempts": 0,
        "images_added_for_gaps": 0,
        "unfillable_gap_details": []
    }
    
    gap_iteration = 0
    initial_coverage = 0.0
    previous_coverage = 0.0
    no_progress_count = 0  # Track iterations with no coverage improvement
    
    while gap_iteration < max_gap_iterations:
        gap_iteration += 1
        try:
            # Create mosaic from current prepared images to detect gaps
            current_col = ee.ImageCollection(prepared)
            test_mosaic = current_col.qualityMosaic("quality")
            
            # Check coverage: count valid (non-masked) pixels in RGB bands
            rgb_mask = test_mosaic.select(["B4", "B3", "B2"]).mask()
            coverage_stats = rgb_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom,
                scale=TARGET_RES * 20,  # Coarse scale for quick check
                maxPixels=1e5
            )
            
            coverage_info = coverage_stats.getInfo()
            if coverage_info and len(coverage_info) > 0:
                # Get mean coverage (average of all bands)
                mean_coverage = sum(coverage_info.values()) / len(coverage_info) if coverage_info else 0.0
                # Validate coverage is reasonable (0.0 to 1.0)
                if mean_coverage < 0.0 or mean_coverage > 1.0:
                    logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Invalid coverage value: {mean_coverage}, defaulting to 0.0")
                    mean_coverage = 0.0
                
                if gap_iteration == 1:
                    initial_coverage = mean_coverage
                    previous_coverage = mean_coverage
                
                # Track coverage progress to avoid infinite loops
                if gap_iteration > 1:
                    coverage_change = mean_coverage - previous_coverage
                    if coverage_change < 0.001:  # Less than 0.1% improvement
                        no_progress_count += 1
                        if no_progress_count >= 3:  # No progress for 3 iterations
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] No coverage improvement for 3 iterations (change: {coverage_change*100:.2f}%), stopping gap-filling")
                            gap_filling_stats["unfillable_gap_details"].append({
                                "tile_idx": tile_idx,
                                "iteration": gap_iteration,
                                "coverage": mean_coverage,
                                "reason": "No progress for 3 iterations"
                            })
                            break
                    else:
                        no_progress_count = 0  # Reset counter if progress made
                
                previous_coverage = mean_coverage
                
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Gap-filling iteration {gap_iteration}: Coverage {mean_coverage*100:.1f}%")
                
                # If coverage is sufficient, we're done
                if mean_coverage >= target_coverage:
                    logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Gap-filling complete: Coverage {mean_coverage*100:.1f}% >= {target_coverage*100:.0f}%")
                    break
                
                # Coverage < target - identify gap area and fill it
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Coverage {mean_coverage*100:.1f}% < {target_coverage*100:.0f}%, identifying gap area...")
                
                # Identify gap area: inverse of valid mask (where mask is 0)
                # This includes both:
                # 1. Pixels with no data from any image (true gaps)
                # 2. Pixels that are cloud-masked in the best image (cloud gaps)
                # qualityMosaic will automatically fill cloud gaps with valid data from other images
                # Multiple iterations allow us to progressively fill cloud gaps with higher-resolution images
                gap_mask = rgb_mask.Not()  # 1 where there are gaps, 0 where valid
                
                # Get gap geometry (where gaps exist)
                # Use reduceToVectors to get gap regions, or use the gap mask directly
                # For efficiency, we'll work with the gap mask and test images that intersect the tile
                gap_geometry = geom  # Use full tile geometry for gap-filling (gaps are within tile)
                
                # OPTIMIZATION: Sort images for gap-filling with multiple priorities
                # 1. Resolution (higher = better) - PRIMARY
                # 2. Temporal consistency (closer to already-selected images) - SECONDARY
                # 3. Quality score - TERTIARY
                # Calculate temporal consistency: prefer images from dates similar to already-selected images
                # OPTIMIZATION: Use cached timestamps instead of making API calls
                selected_dates = []
                for idx, prep_img in enumerate(prepared):
                    # Use cached timestamp if available (avoids API call)
                    if idx < len(prepared_timestamps) and prepared_timestamps[idx] is not None:
                        selected_dates.append(prepared_timestamps[idx])
                    else:
                        # Fallback: get from image metadata (API call - may hit quota)
                        try:
                            img_date = prep_img.get("system:time_start")
                            if img_date:
                                timestamp = int(img_date.getInfo()) / 1000
                                selected_dates.append(timestamp)
                                # Cache it for next time
                                if idx < len(prepared_timestamps):
                                    prepared_timestamps[idx] = timestamp
                        except Exception:
                            pass
                
                def gap_filling_score(img_data):
                    """Score for gap-filling: resolution + temporal consistency + quality"""
                    img, quality_score, stats, sat_name = img_data
                    resolution = stats.get("native_resolution", 999.0)
                    
                    # Resolution score (higher resolution = much better)
                    res_score = 1.0 / (1.0 + resolution / 30.0)  # Normalize: 30m = 0.5, 10m = 0.75, 250m = 0.11
                    
                    # Temporal consistency: prefer images from similar dates
                    # Use cached timestamp from stats if available, otherwise try to get from image
                    temporal_bonus = 0.0
                    if selected_dates:
                        img_timestamp = None
                        # First try to get from stats (cached, no API call)
                        if "timestamp" in stats:
                            img_timestamp = stats["timestamp"]
                        elif "date" in stats:
                            try:
                                # If date is stored as datetime string or timestamp
                                img_timestamp = stats["date"]
                            except Exception:
                                pass
                        
                        # Fallback: get from image metadata (API call - may hit quota)
                        if img_timestamp is None:
                            try:
                                img_date = img.get("system:time_start")
                                if img_date:
                                    img_timestamp = int(img_date.getInfo()) / 1000
                            except Exception as e:
                                # Skip temporal bonus if we can't get timestamp (quota errors, etc.)
                                # This is okay - resolution and quality are more important anyway
                                pass
                        
                        if img_timestamp is not None:
                            try:
                                # Find closest selected date
                                min_days_diff = min([abs(img_timestamp - d) / 86400.0 for d in selected_dates])
                                # Bonus for images within 10 days of selected images
                                if min_days_diff <= 10:
                                    temporal_bonus = 0.15 * (1.0 - min_days_diff / 10.0)
                                elif min_days_diff <= 30:
                                    temporal_bonus = 0.05 * (1.0 - (min_days_diff - 10) / 20.0)
                            except Exception:
                                pass
                    
                    # Combined score: resolution (70%) + temporal (15%) + quality (15%)
                    return res_score * 0.7 + temporal_bonus + quality_score * 0.15
                
                # Sort by gap-filling score (resolution + temporal + quality)
                remaining_images = sorted(all_image_stats, key=gap_filling_score, reverse=True)
                
                # Check if there are any remaining images to process
                if not remaining_images:
                    logging.debug(f"[Tile {_fmt_idx(tile_idx)}] No remaining images for gap-filling, stopping")
                    gap_filling_stats["unfillable_gap_details"].append({
                        "tile_idx": tile_idx,
                        "iteration": gap_iteration,
                        "coverage": mean_coverage,
                        "reason": "No remaining images available"
                    })
                    break
                
                # Track image IDs to avoid duplicates (more efficient than equals())
                # Use system:id if available, otherwise use a combination of properties
                applied_image_ids = set()
                for prep_img in prepared:
                    try:
                        img_id = prep_img.get("system:id")
                        if img_id:
                            applied_image_ids.add(img_id.getInfo())
                    except Exception:
                        # Fallback: try to get date and satellite name as identifier
                        try:
                            img_date = prep_img.get("system:time_start")
                            if img_date:
                                applied_image_ids.add(str(img_date.getInfo()))
                        except Exception:
                            pass
                
                # Find best image that intersects the gap area and isn't already applied
                # RESOLUTION-FIRST: Higher resolution wins even with slightly lower quality
                # A 10m image with some clouds beats a 250m image with no clouds
                best_gap_filler = None
                best_gap_score = 0.0
                best_gap_resolution = 999.0  # Start with worst resolution
                best_gap_sat = None
                best_gap_stats = None  # Store stats for timestamp extraction
                gap_filling_stats["gap_filling_attempts"] += 1
                
                for img, score, stats, sat_name in remaining_images:
                    # Skip if already applied - check by ID first (faster)
                    is_duplicate = False
                    try:
                        img_id = img.get("system:id")
                        if img_id:
                            img_id_val = img_id.getInfo()
                            if img_id_val in applied_image_ids:
                                is_duplicate = True
                    except Exception:
                        # Fallback: use equals() if ID check fails
                    for prep_img in prepared:
                        try:
                            if img.equals(prep_img):
                                is_duplicate = True
                                break
                        except Exception:
                            pass
                    
                    if is_duplicate:
                        continue
                    
                    # Check if image intersects the gap area (tile geometry)
                    # All images in all_image_stats were already filtered by tile bounds, so they should intersect
                    try:
                        # Get image geometry to verify intersection
                        img_geom = img.geometry()
                        if img_geom is None:
                            continue
                        
                        # Get resolution from stats - this is the PRIMARY factor for gap-filling
                        img_resolution = stats.get("native_resolution", 999.0)
                        
                        # Accept if quality is reasonable (lower threshold for gap-filling)
                        quality_threshold = max(0.2, 0.5 - (gap_iteration * 0.05))  # Lower threshold as iterations increase
                        
                        if score >= quality_threshold:
                            # RESOLUTION-FIRST SELECTION: Higher resolution always wins, even with slightly lower quality
                            # This ensures a 10m image with some clouds beats a 250m image with no clouds
                            resolution_diff = best_gap_resolution - img_resolution  # Positive if new image is higher res
                            
                            # If new image has significantly better resolution (>50m better), prefer it
                            # Even if quality score is slightly lower
                            if resolution_diff > 50.0:
                                # Much better resolution - prefer it even if score is 10% lower
                                if score >= best_gap_score * 0.9:  # Allow 10% quality difference
                                    best_gap_resolution = img_resolution
                                    best_gap_score = score
                                    best_gap_filler = img
                                    best_gap_sat = sat_name
                                    best_gap_stats = stats  # Store stats for timestamp
                            elif resolution_diff > 20.0:
                                # Moderately better resolution - prefer if score is within 5%
                                if score >= best_gap_score * 0.95:  # Allow 5% quality difference
                                    best_gap_resolution = img_resolution
                                    best_gap_score = score
                                    best_gap_filler = img
                                    best_gap_sat = sat_name
                                    best_gap_stats = stats  # Store stats for timestamp
                            elif abs(resolution_diff) <= 20.0:
                                # Similar resolution (within 20m) - use quality score as tiebreaker
                                if score > best_gap_score:
                                    best_gap_resolution = img_resolution
                                    best_gap_score = score
                                    best_gap_filler = img
                                    best_gap_sat = sat_name
                                    best_gap_stats = stats  # Store stats for timestamp
                            # If new image has worse resolution, only use if quality is MUCH better
                            elif resolution_diff < -50.0 and score > best_gap_score * 1.15:
                                # Much worse resolution (>50m worse) - only use if 15% better quality
                                best_gap_resolution = img_resolution
                                best_gap_score = score
                                best_gap_filler = img
                                best_gap_sat = sat_name
                                best_gap_stats = stats  # Store stats for timestamp
                            elif resolution_diff < -20.0 and score > best_gap_score * 1.10:
                                # Moderately worse resolution (20-50m worse) - require 10% better quality
                                best_gap_resolution = img_resolution
                                best_gap_score = score
                                best_gap_filler = img
                                best_gap_sat = sat_name
                                best_gap_stats = stats  # Store stats for timestamp
                    except Exception as e:
                        logging.debug(f"Error checking image intersection: {e}")
                        continue
                
                # Add best gap-filling image if found
                if best_gap_filler is not None:
                    prepared.append(best_gap_filler)
                    # Store timestamp for gap-filling (get from stats if available)
                    gap_timestamp = None
                    try:
                        if best_gap_stats is not None and "timestamp" in best_gap_stats:
                            gap_timestamp = best_gap_stats["timestamp"]
                    except Exception:
                        pass
                    prepared_timestamps.append(gap_timestamp)
                    gap_filling_stats["images_added_for_gaps"] += 1
                    gap_filling_stats["gaps_filled"] += 1
                    # Update applied_image_ids for next iteration
                    try:
                        img_id = best_gap_filler.get("system:id")
                        if img_id:
                            applied_image_ids.add(img_id.getInfo())
                    except Exception:
                        pass
                    logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Added gap-filling image from {best_gap_sat} (score={best_gap_score:.3f}, resolution={best_gap_resolution:.0f}m)")
                    # Continue to next iteration immediately to check if coverage improved
                    continue
                else:
                    # No suitable image found for this gap
                    # Try expanding search with lower quality threshold, but still prioritize resolution
                    if gap_iteration < max_gap_iterations - 5:  # Give up after many attempts
                        # Try with very low threshold, but prefer higher resolution
                        fallback_best = None
                        fallback_score = 0.0
                        fallback_resolution = 999.0
                        fallback_sat = None
                        
                        for img, score, stats, sat_name in remaining_images:
                            # Skip if already applied - use ID check (faster)
                            is_duplicate = False
                            try:
                                img_id = img.get("system:id")
                                if img_id:
                                    img_id_val = img_id.getInfo()
                                    if img_id_val in applied_image_ids:
                                        is_duplicate = True
                            except Exception:
                                # Fallback: use equals() if ID check fails
                            for prep_img in prepared:
                                try:
                                    if img.equals(prep_img):
                                        is_duplicate = True
                                        break
                                except Exception:
                                    pass
                            
                            if is_duplicate:
                                continue
                            
                            if score >= 0.1:  # Very low threshold
                                img_resolution = stats.get("native_resolution", 999.0)
                                resolution_diff = fallback_resolution - img_resolution
                                
                                # Still prioritize resolution even in fallback
                                if resolution_diff > 50.0 or (abs(resolution_diff) <= 20.0 and score > fallback_score):
                                    fallback_resolution = img_resolution
                                    fallback_score = score
                                    fallback_best = img
                                    fallback_sat = sat_name
                        
                        if fallback_best is not None:
                            prepared.append(fallback_best)
                            # Store timestamp for gap-filling (get from stats if available)
                            fallback_timestamp = None
                            try:
                                # Find stats for this image
                                for img_check, score_check, stats_check, sat_check in remaining_images:
                                    if img_check.equals(fallback_best):
                                        if "timestamp" in stats_check:
                                            fallback_timestamp = stats_check["timestamp"]
                                        break
                            except Exception:
                                pass
                            prepared_timestamps.append(fallback_timestamp)
                            gap_filling_stats["images_added_for_gaps"] += 1
                            # Update applied_image_ids for next iteration
                            try:
                                img_id = fallback_best.get("system:id")
                                if img_id:
                                    applied_image_ids.add(img_id.getInfo())
                            except Exception:
                                pass
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Added low-quality gap-filling image from {fallback_sat} (score={fallback_score:.3f}, resolution={fallback_resolution:.0f}m)")
                            # Continue to next iteration to check if this helped
                            continue
                        else:
                            # Truly no more images
                            gap_filling_stats["gaps_unfillable"] += 1
                            gap_filling_stats["unfillable_gap_details"].append({
                                "tile_idx": tile_idx,
                                "iteration": gap_iteration,
                                "coverage": mean_coverage,
                                "reason": "No intersecting images available"
                            })
                            logging.warning(f"[Tile {_fmt_idx(tile_idx)}] No more gap-filling images available. Coverage: {mean_coverage*100:.1f}%")
                            break
                    else:
                        # Too many iterations, give up
                        gap_filling_stats["gaps_unfillable"] += 1
                        gap_filling_stats["unfillable_gap_details"].append({
                            "tile_idx": tile_idx,
                            "iteration": gap_iteration,
                            "coverage": mean_coverage,
                            "reason": "Max iterations reached"
                        })
                        logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Max gap-filling iterations reached. Coverage: {mean_coverage*100:.1f}%")
                        break
            else:
                # Coverage check failed - no valid coverage info returned
                logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Coverage check failed (no coverage_info), stopping gap-filling")
                gap_filling_stats["unfillable_gap_details"].append({
                    "tile_idx": tile_idx,
                    "iteration": gap_iteration,
                    "coverage": previous_coverage if gap_iteration > 1 else 0.0,
                    "reason": "Coverage calculation failed"
                })
                break
        except Exception as e:
            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Gap-filling iteration failed: {e}")
            break
    
    # Update gap stats
    gap_filling_stats["gaps_identified"] = gap_filling_stats["gaps_filled"] + gap_filling_stats["gaps_unfillable"]
    
    if len(prepared) == 0:
        empty_gap_stats = {
            "gaps_identified": 0,
            "gaps_filled": 0,
            "gaps_unfillable": 0,
            "gap_filling_attempts": 0,
            "images_added_for_gaps": 0,
            "unfillable_gap_details": [],
            "initial_coverage": 0.0,
            "final_coverage": 0.0,
            "coverage_improvement": 0.0
        }
        return None, None, None, None, [], empty_gap_stats
    
    # Recreate collection from updated prepared list (may have been modified during gap-filling)
    col = ee.ImageCollection(prepared)
    
    # Validate collection is not empty
    try:
        col_size = col.size().getInfo()
        if col_size == 0:
            logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Collection is empty after gap-filling, returning None")
            empty_gap_stats = {
                "gaps_identified": gap_filling_stats.get("gaps_identified", 0),
                "gaps_filled": gap_filling_stats.get("gaps_filled", 0),
                "gaps_unfillable": gap_filling_stats.get("gaps_unfillable", 0),
                "gap_filling_attempts": gap_filling_stats.get("gap_filling_attempts", 0),
                "images_added_for_gaps": gap_filling_stats.get("images_added_for_gaps", 0),
                "unfillable_gap_details": gap_filling_stats.get("unfillable_gap_details", []),
                "initial_coverage": gap_filling_stats.get("initial_coverage", 0.0),
                "final_coverage": 0.0,
                "coverage_improvement": 0.0
            }
            return None, None, None, None, [], empty_gap_stats
    except Exception as e:
        logging.warning(f"[Tile {_fmt_idx(tile_idx)}] Error validating collection size: {e}, proceeding anyway")
    
    # IMPROVED: Use qualityMosaic for per-pixel best selection with automatic fallback
    # This uses the best image where valid, and automatically fills masked pixels
    # with real data from 2nd best, 3rd best, etc. images (not interpolation!)
    # This naturally fills cloud gaps with real observed data from lower-ranked images
    
    # Debug: Log what's in the prepared list
    if tile_idx is not None:
        logging.debug(f"[Tile {tile_idx:04d}] Prepared list contains {len(prepared)} images")
        if len(prepared) > 0:
            # Try to get quality scores from prepared images for debugging
            try:
                # Get first few images' quality scores
                for idx, prep_img in enumerate(prepared[:5]):
                    try:
                        q_band = prep_img.select("quality")
                        q_stats = q_band.reduceRegion(ee.Reducer.first(), geom, scale=1000, maxPixels=1).getInfo()
                        if q_stats and 'quality' in q_stats:
                            q_val = q_stats['quality']
                            logging.debug(f"[Tile {tile_idx:04d}] Prepared image {idx}: quality={q_val}")
                    except Exception:
                        pass
            except Exception:
                pass
    
    try:
        mosaic = col.qualityMosaic("quality")
        # Validate mosaic is not None
        if mosaic is None:
            raise ValueError("qualityMosaic returned None")
        method = f"qualityMosaic_best_with_fallback_{best_satellite_name if best_satellite_name else 'multi_sensor'}"
        if tile_idx is not None:
            logging.debug(f"[Tile {tile_idx:04d}] Using qualityMosaic: best image ({best_satellite_name}) with fallbacks for masked pixels")
    except Exception as e:
        logging.warning(f"[Tile {_fmt_idx(tile_idx)}] qualityMosaic failed: {e}, falling back to median()")
        try:
            mosaic = col.median()
            # Validate median result is not None
            if mosaic is None:
                raise ValueError("median() returned None")
            method = "median_multi_sensor_fallback"
        except Exception:
            mosaic = col.mean()
            method = "mean_multi_sensor_fallback"
    
    # Rank all images by quality score for fallback visualization
    # Sort all_image_stats by quality score (descending) to identify ranks
    ranked_image_stats = []  # Will contain (detailed_stats, fallback_rank) tuples
    if len(all_image_stats) > 0:
        # Sort by quality score (descending)
        sorted_stats = sorted(all_image_stats, key=lambda x: x[1], reverse=True)
        
        for rank, (image, quality_score, detailed_stats, sat_name) in enumerate(sorted_stats, start=1):
            # Rank 1 is the best (primary selected image)
            # Rank 2, 3, etc. are fallbacks (used to fill masked pixels)
            if rank == 1:
                # Primary selected image
                detailed_stats["is_selected"] = True
                detailed_stats["is_fallback_rank"] = None
            else:
                # Fallback image (2nd, 3rd, etc. best)
                detailed_stats["is_selected"] = False
                detailed_stats["is_fallback_rank"] = rank
            
            ranked_image_stats.append(detailed_stats)
    
    # Mosaic already has standardized raw bands + indices from add_indices_to_unified_mosaic
    # No need to standardize again - proceed directly to reprojection
    
    # Use more accurate reprojection: determine optimal CRS for the tile
    center_lon = (lon_min + lon_max) / 2.0
    center_lat = (lat_min + lat_max) / 2.0
    zone, north = lonlat_to_utm_zone(center_lon, center_lat)
    if north:
        utm_crs = f"EPSG:{32600 + zone}"
    else:
        utm_crs = f"EPSG:{32700 + zone}"
    
    # Reproject to UTM for better accuracy, then clip
    # CRITICAL: Use TARGET_RES (10m) - native Sentinel-2 resolution
    # This preserves Sentinel-2's native quality and upsamples other satellites to match
    # All tiles will have consistent 10m pixel size for seamless mosaicking
    mosaic = mosaic.reproject(crs=utm_crs, scale=TARGET_RES)
    mosaic = mosaic.clip(geom)
    
    # Apply additional quality filters: ensure no invalid values
    mosaic = mosaic.updateMask(mosaic.select(0).gt(0))  # Mask pixels where first band is invalid
    
    # NOTE: Indices are NOT calculated here - they will be calculated locally after tiles are downloaded
    # and the final mosaic is stitched together. This is much faster and reduces Earth Engine API calls.
    
    # Determine dominant satellite for this tile
    # Since we're downloading only the single best image, the dominant satellite is the one with the highest quality score
    # Quality score is computed from weighted factors: cloud fraction, solar zenith, view zenith, 
    # valid pixels, temporal recency, and resolution. Image count has NO role in dominance determination.
    dominant_satellite = best_satellite_name  # The satellite of the single best image
    
    # Debug: Log satellite contributions and quality scores for this tile
    if tile_idx is not None:
        satellite_counts = Counter(satellite_contributions)
        total_images = len(satellite_contributions)
        sat_summary = ", ".join([f"{sat}: {count}" for sat, count in satellite_counts.most_common()])
        quality_summary = ", ".join([f"{sat}: {score:.3f}" for sat, score in sorted(satellite_quality_scores.items(), key=lambda x: x[1], reverse=True)])
        logging.debug(f"[Tile {tile_idx:04d}] Evaluated {total_images} images from {len(satellite_counts)} sensors ({sat_summary})")
        logging.debug(f"[Tile {tile_idx:04d}] Quality scores: {quality_summary}")
        logging.debug(f"[Tile {tile_idx:04d}] Selected single best image: {dominant_satellite} with quality score {best_score:.3f}")
    
    # Calculate final coverage for reporting
    try:
        final_col = ee.ImageCollection(prepared)
        final_test_mosaic = final_col.qualityMosaic("quality")
        final_rgb_mask = final_test_mosaic.select(["B4", "B3", "B2"]).mask()
        final_coverage_stats = final_rgb_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=TARGET_RES * 20,
            maxPixels=1e5
        )
        final_coverage_info = final_coverage_stats.getInfo()
        if final_coverage_info:
            final_coverage = sum(final_coverage_info.values()) / len(final_coverage_info) if final_coverage_info else 0.0
        else:
            final_coverage = initial_coverage
    except Exception:
        final_coverage = initial_coverage
    
    # Add coverage info to gap stats
    gap_filling_stats["initial_coverage"] = initial_coverage
    gap_filling_stats["final_coverage"] = final_coverage
    gap_filling_stats["coverage_improvement"] = final_coverage - initial_coverage
    
    return mosaic, method, dominant_satellite, best_detailed_stats, ranked_image_stats, gap_filling_stats


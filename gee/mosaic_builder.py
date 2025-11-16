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
    landsat_collections, modis_collection, aster_collection, viirs_collection
)
from .cloud_detection import estimate_cloud_fraction, estimate_modis_cloud_fraction
from .image_preparation import (
    s2_prepare_image, landsat_prepare_image, prepare_modis_image,
    prepare_aster_image, prepare_viirs_image, harmonize_image
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
        
        # Map existing bands to standard names
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
                standardized_bands.append(ee.Image.constant(0.0).toFloat().rename(std_name))
        
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
                            tile_idx: Optional[int] = None, 
                            test_callback=None):
    """
    Build best mosaic using two-phase approach:
    1. Find 3 excellent images (quality > 0.85) - stop searching early
    2. Create initial mosaic and identify missing pixels
    3. Find minimal high-quality patches to fill only the gaps
    
    This ensures no blank areas while minimizing processing time.
    """
    lon_min, lat_min, lon_max, lat_max = tile_bounds
    geom = ee.Geometry.Polygon([[lon_min, lat_min], [lon_min, lat_max], 
                                [lon_max, lat_max], [lon_max, lat_min], 
                                [lon_min, lat_min]])
    
    start_date = datetime.fromisoformat(start)
    end_date = datetime.fromisoformat(end)
    max_days = (end_date - start_date).days if end_date > start_date else 365
    
    # TWO-PHASE APPROACH: Find best 3 images from EACH satellite, then select best overall and fill gaps
    EXCELLENT_QUALITY_THRESHOLD = 0.85  # Quality threshold for "excellent" images
    TARGET_EXCELLENT_PER_SATELLITE = 3  # Collect up to 3 excellent images per satellite
    prepared = []  # Images to use in mosaic
    prepared_excellent = []  # Track excellent images separately (best from all satellites)
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
    
    # Helper: safe tile index formatting for logs
    def _fmt_idx(idx):
        try:
            return f"{int(idx):04d}"
        except Exception:
            return "????"
    
    # Process Sentinel-2 (skip entire section if not included for this month)
    try:
        if not include_s2:
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
            # Filter by cloud percentage on server before downloading metadata
            s2_col = s2_col.filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20.0))
            # OPTIMIZATION: Server-side filtering - sort by cloud probability and take best
            s2_col = s2_col.sort("CLOUDY_PIXEL_PERCENTAGE")
            s2_count = int(s2_col.size().getInfo())
            
            if s2_count == 0:
                logging.debug("No Sentinel-2 images with <20% clouds found")
            else:
                # OPTIMIZATION #8: Progressive quality threshold - start high, lower if needed
                quality_threshold = 0.9  # Start with high threshold
                threshold_lowered = False
                
                # OPTIMIZATION #1 & #4: Batch fetch metadata for all images at once
                # Collect all images first
                images_to_process = []
                for i in range(min(s2_count, MAX_IMAGES_PER_SATELLITE)):
                    try:
                        img = ee.Image(s2_col.toList(s2_count).get(i))
                        images_to_process.append(img)
                    except Exception:
                        continue
                
                # Batch fetch metadata in parallel
                if images_to_process:
                    metadata_list = extract_metadata_parallel(
                        images_to_process,
                        ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE", 
                         "MEAN_SOLAR_ZENITH_ANGLE", "MEAN_INCIDENCE_ZENITH_ANGLE"],
                        max_workers=4
                    )
                else:
                    metadata_list = []
                
                test_num = 0
                sat_name = "Copernicus Sentinel-2"
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                
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
                        
                        # OPTIMIZATION: Quick cloud check from batched metadata
                        cp_val = metadata.get("CLOUDY_PIXEL_PERCENTAGE")
                        if cp_val is not None and float(cp_val) > 20.0:
                            if test_callback:
                                test_callback(tile_idx, test_num, "S2", img_date_str, None, "SKIPPED (>20% clouds)")
                            continue
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # CRITICAL: Calculate cloud fraction BEFORE masking
                        # Otherwise we're calculating cloud fraction from an already-masked image
                        cf, vf = estimate_cloud_fraction(img, geom)  # Use original image, not masked
                        
                        # Debug logging for Sentinel-2 cloud fraction
                        if tile_idx is not None:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Sentinel-2 {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}%")
                        
                        # OPTIMIZATION: Early exit if too cloudy (before processing)
                        if cf > 0.2:  # Skip if >20% clouds (fair threshold for all satellites)
                            if test_callback:
                                test_callback(tile_idx, test_num, "S2", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
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
                        detailed_stats = {
                            "satellite": "Copernicus Sentinel-2",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": sun_zen_val,
                            "view_zenith": view_zen_val,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 10.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0  # Use 0.0 instead of None
                        }
                        
                        # STEP 4: Report test result with complete data
                        if test_callback:
                            test_callback(tile_idx, test_num, "S2", img_date_str, quality_score, None, detailed_stats)
                        
                        # OPTIMIZATION #8: Progressive quality threshold
                        # Start with high threshold, lower if no images pass
                        if quality_score < quality_threshold:
                            if not threshold_lowered and test_num >= 3:
                                # Lower threshold if we've tested 3+ images and none passed
                                quality_threshold = 0.7
                                threshold_lowered = True
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Lowered quality threshold to 0.7 (no images > 0.9 found)")
                            if quality_score < quality_threshold:
                                continue
                        
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
    except Exception as e:
        if str(e) != "include_s2_false_skip":
            logging.debug(f"Error processing Sentinel-2: {e}")
    
    # Process Landsat - filter by operational date ranges
    ls_defs = [
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
            try:
                col = ee.ImageCollection(coll_id).filterBounds(geom).filterDate(start, end)
                # OPTIMIZATION #2: Pre-filter collection before iteration (server-side filtering)
                # Filter by cloud cover on server before downloading metadata
                col = col.filter(ee.Filter.lt("CLOUD_COVER", 20.0))
                # OPTIMIZATION: Server-side filtering - sort by cloud cover and take best
                col = col.sort("CLOUD_COVER")
                cnt = int(col.size().getInfo())
                if cnt == 0:
                    continue
                
                # OPTIMIZATION #8: Progressive quality threshold - start high, lower if needed
                quality_threshold = 0.9  # Start with high threshold
                threshold_lowered = False
                
                # OPTIMIZATION #1 & #4: Batch fetch metadata for all images at once
                images_to_process = []
                for i in range(min(cnt, MAX_IMAGES_PER_SATELLITE)):
                    try:
                        img = ee.Image(col.toList(cnt).get(i))
                        images_to_process.append(img)
                    except Exception:
                        continue
                
                # Batch fetch metadata in parallel
                if images_to_process:
                    metadata_list = extract_metadata_parallel(
                        images_to_process,
                        ["system:time_start", "CLOUD_COVER", "CLOUD_COVER_LAND", "SUN_ELEVATION"],
                        max_workers=4
                    )
                else:
                    metadata_list = []
                
                test_num = 0
                sat_name = key.replace("LANDSAT_", "Landsat-").replace("_", "-")
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                
                for idx, img in enumerate(images_to_process):
                    if idx >= len(metadata_list):
                        break
                    
                    try:
                        metadata = metadata_list[idx]
                        test_num += 1
                        
                        # Get image date from batched metadata
                        img_date_str = start  # Default to start date
                        days_since = None
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
                        
                        # OPTIMIZATION: Quick cloud check from batched metadata
                        cc_val = metadata.get("CLOUD_COVER") or metadata.get("CLOUD_COVER_LAND")
                        if cc_val is not None and float(cc_val) > 20.0:
                            if test_callback:
                                test_callback(tile_idx, test_num, key, img_date_str, None, "SKIPPED (>20% clouds)")
                            continue
                        
                        # STEP 1: Collect ALL parameters first (before any calculations)
                        # CRITICAL: Calculate cloud fraction BEFORE masking (like MODIS)
                        # Otherwise we're calculating cloud fraction from an already-masked image
                        cf, vf = estimate_cloud_fraction(img, geom)  # Use original image, not masked
                        
                        # Debug logging for Landsat cloud fraction
                        if tile_idx is not None:
                            logging.debug(f"[Tile {_fmt_idx(tile_idx)}] {key} {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}%")
                        
                        # OPTIMIZATION: Early exit if too cloudy (before processing)
                        if cf > 0.2:  # Skip if >20% clouds (fair threshold for all satellites)
                            if test_callback:
                                test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
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
                        if is_l7_post_slc_failure:
                            # Apply severe penalty for SLC failure - reduce quality by 50% to make it last resort
                            # This ensures other satellites (Landsat 5, MODIS, ASTER) are preferred
                            quality_score = base_quality_score * 0.5
                            logging.debug(f"Landsat 7 post-SLC failure: quality reduced from {base_quality_score:.3f} to {quality_score:.3f} (last resort)")
                        else:
                            quality_score = base_quality_score
                        
                        # STEP 3: Create complete detailed stats with all collected data
                        sat_name = key.replace("LANDSAT_", "Landsat-").replace("_", "-")
                        detailed_stats = {
                            "satellite": sat_name,
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": sun_zen_val,
                            "view_zenith": None,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 30.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0  # Use 0.0 instead of None
                        }
                        
                        # STEP 4: Report test result with complete data
                        if test_callback:
                            test_callback(tile_idx, test_num, key, img_date_str, quality_score, None, detailed_stats)
                        
                        # OPTIMIZATION #8: Progressive quality threshold
                        # Use threshold to adapt search aggressiveness, but do not exclude images solely on this gate.
                        # We already exclude very low quality images (< 0.3) above.
                        if quality_score < quality_threshold:
                            if not threshold_lowered and test_num >= 3:
                                # Lower threshold if we've tested 3+ images and none exceeded the high bar
                                quality_threshold = 0.7
                                threshold_lowered = True
                                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Lowered quality threshold to 0.7 (no images > 0.9 found)")
                            # Do not 'continue' here; still allow this image into prepared for fallback/mosaic
                        
                        # TWO-PHASE APPROACH: Track excellent images per satellite (up to 3 per satellite)
                        if quality_score >= EXCELLENT_QUALITY_THRESHOLD:
                            excellent_count_for_sat += 1
                            if sat_name not in excellent_per_satellite:
                                excellent_per_satellite[sat_name] = []
                            excellent_per_satellite[sat_name].append((img_sel, quality_score, detailed_stats.copy()))
                            # Stop searching THIS satellite after finding 3 excellent images
                            if excellent_count_for_sat >= TARGET_EXCELLENT_PER_SATELLITE:
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Found {excellent_count_for_sat} excellent images from {sat_name}, continuing to next satellite")
                                break
                        
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
                        
                        # OPTIMIZATION: Only add images with reasonable quality scores
                        # Skip very low quality images to reduce processing
                        if quality_score < 0.3:  # Skip images with quality < 30%
                            if test_callback:
                                test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED (quality too low: {quality_score:.3f})")
                            logging.debug(f"Landsat {key} image skipped: quality score {quality_score:.3f} < 0.3")
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        img_sel = img_sel.addBands(quality_band)
                        # CRITICAL: Standardize RAW bands BEFORE adding to collection to ensure homogeneous band structure
                        # This ensures all images have the same RAW bands (B4, B3, B2, B8, B11, B12, quality)
                        # Indices are created AFTER qualityMosaic unifies all bands
                        img_sel = standardize_raw_bands_for_collection(img_sel)
                        
                        # TWO-PHASE APPROACH: Track excellent images and stop after finding 3
                        if quality_score >= EXCELLENT_QUALITY_THRESHOLD:
                            prepared_excellent.append(img_sel)
                        
                        prepared.append(img_sel)
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
                        logging.debug(f"Skipping {key} image {idx}: {e}")
                        continue
            except Exception as e:
                logging.debug(f"Error processing {key}: {e}")
                continue
    
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
                # Only process top 5 MODIS images (last resort, don't need many)
                for i in range(min(modis_count, 5)):
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
                        detailed_stats = {
                            "satellite": "MODIS",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": None,
                            "view_zenith": 15.0,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 250.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0  # Use 0.0 instead of None
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
                MAX_IMAGES_PER_SATELLITE = 20  # Reduced to speed up processing
                test_num = 0
                sat_name = "ASTER"
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                for i in range(min(aster_count, MAX_IMAGES_PER_SATELLITE)):
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
                        detailed_stats = {
                            "satellite": "ASTER",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": None,
                            "view_zenith": None,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 15.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0  # Use 0.0 instead of None
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
                MAX_IMAGES_PER_SATELLITE = 20  # Reduced to speed up processing
                test_num = 0
                sat_name = "VIIRS"
                excellent_count_for_sat = 0  # Track excellent images for THIS satellite
                for i in range(min(viirs_count, MAX_IMAGES_PER_SATELLITE)):
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
                        detailed_stats = {
                            "satellite": "VIIRS",
                            "quality_score": quality_score,
                            "cloud_fraction": cf,
                            "solar_zenith": None,
                            "view_zenith": None,
                            "valid_pixel_fraction": vf,
                            "temporal_recency_days": days_since,
                            "native_resolution": 375.0,
                            "band_completeness": band_completeness if band_completeness is not None else 0.0  # Use 0.0 instead of None
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
        return None, None, None, None, []
    
    # Create initial mosaic from selected best images
    col = ee.ImageCollection(prepared)
    
    # PHASE 2: Detect missing pixels and fill gaps with minimal high-quality patches
    # Check coverage of selected best images, then fill any remaining gaps
    # Continue until 100% coverage is achieved - no gaps allowed
    max_iterations = 10  # Increased iterations to ensure 100% coverage
    iteration = 0
    target_coverage = 0.999  # Practical ceiling; exact 1.0 often unattainable
    
    while iteration < max_iterations:
        iteration += 1
        try:
            # Create mosaic from current prepared images to detect gaps
            current_col = ee.ImageCollection(prepared)
            test_mosaic = current_col.qualityMosaic("quality")
            
            # Check coverage: count valid (non-masked) pixels in RGB bands
            # Use a sample to quickly estimate coverage
            rgb_mask = test_mosaic.select(["B4", "B3", "B2"]).mask()
            # Get mean mask value (1.0 = all valid, 0.0 = all masked)
            coverage_stats = rgb_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom,
                scale=TARGET_RES * 20,  # Coarse scale for quick check
                maxPixels=1e5
            )
            
            coverage_info = coverage_stats.getInfo()
            if coverage_info:
                # Get mean coverage (average of all bands)
                mean_coverage = sum(coverage_info.values()) / len(coverage_info) if coverage_info else 0.0
                
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Phase 2 Iteration {iteration}: Coverage {mean_coverage*100:.1f}%")
                
                # If coverage is sufficient, we're done
                if mean_coverage >= target_coverage:
                    logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Phase 2: Coverage {mean_coverage*100:.1f}% >= {target_coverage*100:.0f}%, gap-filling complete")
                    break
                
                # Coverage < target - need to add gap-filling images
                logging.debug(f"[Tile {_fmt_idx(tile_idx)}] Phase 2: Coverage {mean_coverage*100:.1f}% < {target_coverage*100:.0f}%, searching for gap-filling images")
                phase_2_mode = True
                
                # Find additional images that can fill gaps
                # Use ALL images from all_image_stats (sorted by quality, descending)
                # This includes images from all satellites, not just the ones we've selected
                remaining_images = sorted(all_image_stats, key=lambda x: x[1], reverse=True)
                
                # Add images that can fill gaps (prioritize high quality, but accept lower quality if needed)
                # For 100% coverage, we must be aggressive in filling gaps
                gap_filling_added = 0
                quality_threshold_for_gaps = 0.5  # Start with moderate threshold
                max_gap_fillers_per_iteration = 15  # Allow more gap-fillers per iteration
                
                for img, score, stats, sat_name in remaining_images:
                    # Check if image is already in prepared by comparing directly
                    is_duplicate = False
                    for prep_img in prepared:
                        try:
                            if img.equals(prep_img):
                                is_duplicate = True
                                break
                        except Exception:
                            pass
                    if is_duplicate:
                        continue
                    
                    # Add if quality is acceptable for gap-filling
                    # For 100% coverage, we must accept lower quality images if needed
                    if score >= quality_threshold_for_gaps and gap_filling_added < max_gap_fillers_per_iteration:
                        prepared.append(img)
                        gap_filling_added += 1
                        logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: Added gap-filling image from {sat_name} (score={score:.3f})")
                        
                        # Aggressively lower quality threshold if we're not finding enough images
                        # This ensures we can fill all gaps, even if it means using lower quality images
                        if gap_filling_added < 5:
                            quality_threshold_for_gaps = max(0.2, quality_threshold_for_gaps - 0.1)  # Lower to 0.2 minimum
                        elif gap_filling_added < 10:
                            quality_threshold_for_gaps = max(0.1, quality_threshold_for_gaps - 0.05)  # Lower to 0.1 minimum
                
                # Recreate collection with gap-filling images
                if gap_filling_added > 0:
                    col = ee.ImageCollection(prepared)
                    logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: Added {gap_filling_added} gap-filling images, total: {len(prepared)}")
                else:
                    # No more images to add - but we need 100% coverage
                    # Try one more time with even lower threshold
                    if iteration < max_iterations - 1:
                        quality_threshold_for_gaps = 0.1  # Very low threshold for final attempt
                        logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: No images found, lowering threshold to {quality_threshold_for_gaps} for final attempt")
                        # Try again with lower threshold
                        for img, score, stats, sat_name in remaining_images:
                            # Skip duplicates
                            is_duplicate = False
                            for prep_img in prepared:
                                try:
                                    if img.equals(prep_img):
                                        is_duplicate = True
                                        break
                                except Exception:
                                    pass
                            if is_duplicate:
                                continue
                            
                            if score >= quality_threshold_for_gaps:
                                prepared.append(img)
                                gap_filling_added += 1
                                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: Added low-quality gap-filling image from {sat_name} (score={score:.3f})")
                                if gap_filling_added >= 5:  # Limit final attempt
                                    break
                        
                        if gap_filling_added > 0:
                            col = ee.ImageCollection(prepared)
                            logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: Final attempt added {gap_filling_added} images, total: {len(prepared)}")
                        else:
                            # Truly no more images - log warning but continue
                            logging.warning(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: No more gap-filling images available even with lowest threshold. Coverage may be < 100%")
                            break
                    else:
                        # Last iteration and no images found
                        logging.warning(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: Reached max iterations without 100% coverage. Current coverage: {mean_coverage*100:.1f}%")
                        break
            else:
                # Coverage check failed - break to avoid infinite loop
                logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2: Coverage check failed, using current images")
                break
        except Exception as e:
            logging.debug(f"[Tile {tile_idx:04d if tile_idx is not None else '???'}] Phase 2 gap detection failed: {e}")
            # Fallback: use current images (qualityMosaic will handle gaps)
            break
    
    if len(prepared) == 0:
        return None, None, None, None, []
    
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
        method = f"qualityMosaic_best_with_fallback_{best_satellite_name if best_satellite_name else 'multi_sensor'}"
        if tile_idx is not None:
            logging.debug(f"[Tile {tile_idx:04d}] Using qualityMosaic: best image ({best_satellite_name}) with fallbacks for masked pixels")
    except Exception:
        try:
            mosaic = col.median()
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
    # CRITICAL: Use TARGET_RES to ensure unified resolution across all tiles for final mosaic
    # This ensures all tiles have the same pixel size regardless of source satellite
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
    
    return mosaic, method, dominant_satellite, best_detailed_stats, ranked_image_stats


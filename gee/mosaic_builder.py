"""
Mosaic building logic - combines images from multiple satellites using quality-based selection.
"""
import logging
from datetime import datetime
from typing import Tuple, Optional
from collections import Counter
import ee

from .config import TARGET_RES
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
from .quality_scoring import compute_quality_score


def build_best_mosaic_for_tile(tile_bounds: Tuple[float, float, float, float], 
                                start: str, end: str, 
                                include_l7: bool = False, 
                                enable_harmonize: bool = True,
                                include_modis: bool = True, 
                                include_aster: bool = True, 
                                include_viirs: bool = True,
                                tile_idx: Optional[int] = None, 
                                test_callback=None):
    """
    Build best mosaic from ALL available satellites using quality-weighted per-pixel selection.
    No sensor priority - purely quality-based selection across all sensors.
    
    OPTIMIZED: Does aggressive server-side filtering to minimize downloads and processing time.
    """
    lon_min, lat_min, lon_max, lat_max = tile_bounds
    geom = ee.Geometry.Polygon([[lon_min, lat_min], [lon_min, lat_max], 
                                [lon_max, lat_max], [lon_max, lat_min], 
                                [lon_min, lat_min]])
    
    start_date = datetime.fromisoformat(start)
    end_date = datetime.fromisoformat(end)
    max_days = (end_date - start_date).days if end_date > start_date else 365
    
    # OPTIMIZATION: Limit images per satellite to reduce processing time
    MAX_IMAGES_PER_SATELLITE = 20  # Reduced from 50-200 to speed up processing dramatically
    prepared = []
    satellite_contributions = []  # Track which satellites contributed images to this tile
    
    # Process Sentinel-2
    try:
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
            # OPTIMIZATION: Server-side filtering - sort by cloud probability and take best
            s2_col = s2_col.sort("CLOUDY_PIXEL_PERCENTAGE")
            s2_count = int(s2_col.size().getInfo())
            # Only process top N images (best quality, lowest clouds)
            MAX_IMAGES_PER_SATELLITE = 20  # Reduced from 200 to speed up processing
            test_num = 0
            for i in range(min(s2_count, MAX_IMAGES_PER_SATELLITE)):
                try:
                    img = ee.Image(s2_col.toList(s2_count).get(i))
                    test_num += 1
                    
                    # Get image date for display
                    img_date_str = start  # Default to start date
                    try:
                        img_date = img.get("system:time_start")
                        if img_date:
                            img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                            img_date_str = img_dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                    
                    # OPTIMIZATION: Quick cloud check from metadata before expensive processing
                    try:
                        cp = img.get("CLOUDY_PIXEL_PERCENTAGE")
                        if cp is not None:
                            cp_val = cp.getInfo()
                            if cp_val is not None and float(cp_val) > 50.0:  # Skip if >50% clouds
                                if test_callback:
                                    test_callback(tile_idx, test_num, "S2", img_date_str, None, "SKIPPED (>50% clouds)")
                                continue  # Skip this image, too cloudy
                    except Exception:
                        pass
                    
                    img_p = s2_prepare_image(img)
                    cf, vf = estimate_cloud_fraction(img_p, geom)
                    
                    # OPTIMIZATION: Early exit if too cloudy after processing
                    if cf > 0.6:  # Skip if >60% clouds
                        if test_callback:
                            test_callback(tile_idx, test_num, "S2", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                        continue
                    
                    # Get metadata
                    try:
                        sun_zen = img.get("MEAN_SOLAR_ZENITH_ANGLE")
                        sun_zen_val = float(sun_zen.getInfo()) if sun_zen else None
                        view_zen = img.get("MEAN_INCIDENCE_ZENITH_ANGLE")
                        view_zen_val = float(view_zen.getInfo()) if view_zen else None
                        img_date = img.get("system:time_start")
                        if img_date:
                            img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                            days_since = (img_dt - start_date).days
                            img_date_str = img_dt.strftime("%Y-%m-%d")
                        else:
                            days_since = None
                    except Exception:
                        sun_zen_val = None
                        view_zen_val = None
                        days_since = None
                    
                    # Compute quality score (no sensor bias)
                    # Sentinel-2 native resolution: 10m
                    quality_score = compute_quality_score(cf, sun_zen_val, view_zen_val, vf, days_since, max_days, native_resolution=10.0)
                    
                    # Report test result
                    if test_callback:
                        test_callback(tile_idx, test_num, "S2", img_date_str, quality_score, None)
                    
                    # OPTIMIZATION: Early exit for low quality
                    if quality_score < 0.3:  # Skip images with quality < 30%
                        continue
                    
                    # Harmonize to common standard
                    if enable_harmonize:
                        img_p = harmonize_image(img_p, "S2_to_LS")
                    
                    # Select bands: RGB + IR bands + water indices + vegetation indices
                    try:
                        band_names = img_p.bandNames().getInfo()
                        if "B4" in band_names and "B3" in band_names and "B2" in band_names:
                            sel_bands = ["B4","B3","B2"]  # RGB
                            
                            # Add IR bands if available
                            if "B8" in band_names:
                                sel_bands.append("B8")  # NIR
                            if "B11" in band_names:
                                sel_bands.append("B11")  # SWIR1
                            if "B12" in band_names:
                                sel_bands.append("B12")  # SWIR2
                            
                            # Add water indices
                            water_band = "MNDWI" if "MNDWI" in band_names else ("NDWI" if "NDWI" in band_names else None)
                            if water_band:
                                sel_bands.append(water_band)
                            
                            # Add vegetation indices
                            if "NDVI" in band_names:
                                sel_bands.append("NDVI")
                            if "EVI" in band_names:
                                sel_bands.append("EVI")
                            if "SAVI" in band_names:
                                sel_bands.append("SAVI")
                            if "AVI" in band_names:
                                sel_bands.append("AVI")  # Aquatic Vegetation Index
                            if "FVI" in band_names:
                                sel_bands.append("FVI")  # Floating Vegetation Index
                            
                            sel = img_p.select(sel_bands)
                        else:
                            continue
                    except Exception:
                        continue
                    
                    # Ensure quality band is explicitly float to match all images in collection
                    # Use toFloat() to ensure server-side type consistency
                    quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                    sel = sel.addBands(quality_band)
                    prepared.append(sel)
                    satellite_contributions.append("Sentinel-2")
                except Exception as e:
                    logging.debug(f"Skipping S2 image {i}: {e}")
                    continue
    except Exception as e:
        logging.debug(f"Error processing Sentinel-2: {e}")
    
    # Process Landsat - filter by operational date ranges
    ls_defs = []
    if is_satellite_operational("LANDSAT_9", start, end):
        ls_defs.append(("LANDSAT/LC09/C02/T1_L2", "LANDSAT_9"))
    if is_satellite_operational("LANDSAT_8", start, end):
        ls_defs.append(("LANDSAT/LC08/C02/T1_L2", "LANDSAT_8"))
    if is_satellite_operational("LANDSAT_5", start, end):
        ls_defs.append(("LANDSAT/LT05/C02/T1_L2", "LANDSAT_5"))
    # Landsat 7: Include but note SLC failure on 2003-05-31 causes data gaps
    # After SLC failure, Landsat 7 will be heavily penalized in quality scoring (last resort)
    if include_l7 and is_satellite_operational("LANDSAT_7", start, end):
        ls_defs.append(("LANDSAT/LE07/C02/T1_L2", "LANDSAT_7"))
        # Log warning if date range includes post-SLC failure period
        try:
            start_date = datetime.fromisoformat(start)
            slc_failure_date = datetime.fromisoformat("2003-05-31")
            if start_date < slc_failure_date:
                end_date = datetime.fromisoformat(end)
                if end_date >= slc_failure_date:
                    logging.warning("Date range includes Landsat 7 post-SLC failure period (after 2003-05-31). "
                                  "Landsat 7 images will be heavily penalized due to data gaps/black stripes.")
        except Exception:
            pass
    
    for coll_id, key in ls_defs:
        try:
            col = ee.ImageCollection(coll_id).filterBounds(geom).filterDate(start, end)
            # OPTIMIZATION: Server-side filtering - sort by cloud cover and take best
            col = col.sort("CLOUD_COVER")
            cnt = int(col.size().getInfo())
            if cnt == 0:
                continue
            MAX_IMAGES_PER_SATELLITE = 20  # Reduced from 200 to speed up processing
            test_num = 0
            for i in range(min(cnt, MAX_IMAGES_PER_SATELLITE)):
                try:
                    img = ee.Image(col.toList(cnt).get(i))
                    test_num += 1
                    
                    # Get image date for display
                    img_date_str = start  # Default to start date
                    try:
                        img_date = img.get("system:time_start")
                        if img_date:
                            img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                            img_date_str = img_dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                    
                    # Check if this is Landsat 7 after SLC failure (2003-05-31)
                    # SLC failure causes black stripes/data gaps - use as last resort
                    is_l7_post_slc_failure = False
                    if key == "LANDSAT_7":
                        try:
                            img_date = img.get("system:time_start")
                            if img_date:
                                img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                                slc_failure_date = datetime.fromisoformat("2003-05-31")
                                if img_dt >= slc_failure_date:
                                    is_l7_post_slc_failure = True
                                    logging.debug(f"Landsat 7 image after SLC failure (2003-05-31): {img_dt.date()}")
                        except Exception:
                            pass
                    
                    # OPTIMIZATION: Quick cloud check from metadata before expensive processing
                    try:
                        cc = img.get("CLOUD_COVER")
                        if cc is not None:
                            cc_val = cc.getInfo()
                            if cc_val is not None and float(cc_val) > 50.0:  # Skip if >50% clouds
                                if test_callback:
                                    test_callback(tile_idx, test_num, key, img_date_str, None, "SKIPPED (>50% clouds)")
                                continue  # Skip this image, too cloudy
                    except Exception:
                        pass
                    
                    img_p = landsat_prepare_image(img)
                    
                    if key == "LANDSAT_7":
                        try:
                            # Mask out invalid pixels (helps with SLC gaps)
                            img_p = img_p.updateMask(img_p.reduce(ee.Reducer.allNonZero()))
                        except Exception:
                            pass
                    
                    cf, vf = estimate_cloud_fraction(img_p, geom)
                    
                    # Debug logging for Landsat cloud fraction
                    if tile_idx is not None:
                        logging.debug(f"[Tile {tile_idx:04d}] {key} {img_date_str} Test {test_num:02d}: cloud_frac={cf*100:.1f}%, valid_frac={vf*100:.1f}%")
                    
                    # OPTIMIZATION: Early exit if too cloudy after processing
                    if cf > 0.6:  # Skip if >60% clouds
                        if test_callback:
                            test_callback(tile_idx, test_num, key, img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                        continue
                    
                    try:
                        sun_zen = img.get("SUN_ELEVATION")
                        sun_zen_val = 90.0 - float(sun_zen.getInfo()) if sun_zen else None
                        img_date = img.get("system:time_start")
                        if img_date:
                            img_dt = datetime.fromtimestamp(int(img_date.getInfo()) / 1000)
                            days_since = (img_dt - start_date).days
                            img_date_str = img_dt.strftime("%Y-%m-%d")
                        else:
                            days_since = None
                    except Exception:
                        sun_zen_val = None
                        days_since = None
                    
                    # Landsat native resolution: 30m
                    # Heavily penalize Landsat 7 after SLC failure (2003-05-31) due to data gaps/black stripes
                    base_quality_score = compute_quality_score(cf, sun_zen_val, None, vf, days_since, max_days, native_resolution=30.0)
                    if is_l7_post_slc_failure:
                        # Apply severe penalty for SLC failure - reduce quality by 50% to make it last resort
                        # This ensures other satellites (Landsat 5, MODIS, ASTER) are preferred
                        quality_score = base_quality_score * 0.5
                        logging.debug(f"Landsat 7 post-SLC failure: quality reduced from {base_quality_score:.3f} to {quality_score:.3f} (last resort)")
                    else:
                        quality_score = base_quality_score
                    
                    # Report test result
                    if test_callback:
                        test_callback(tile_idx, test_num, key, img_date_str, quality_score, None)
                    
                    if enable_harmonize:
                        img_p = harmonize_image(img_p, "LS_to_S2")
                    
                    try:
                        bands = img_p.bandNames().getInfo()
                        sel = []
                        # Get RGB bands
                        for candidate in ["SR_B4","SR_B3","SR_B2","B4","B3","B2"]:
                            if candidate in bands and len(sel) < 3:
                                sel.append(candidate)
                        if len(sel) < 3:
                            continue
                        
                        # Add IR bands
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
                        
                        # Add water indices
                        water_band = "MNDWI" if "MNDWI" in bands else ("NDWI" if "NDWI" in bands else None)
                        
                        # Add vegetation indices
                        veg_bands = []
                        if "NDVI" in bands:
                            veg_bands.append("NDVI")
                        if "EVI" in bands:
                            veg_bands.append("EVI")
                        if "SAVI" in bands:
                            veg_bands.append("SAVI")
                        if "AVI" in bands:
                            veg_bands.append("AVI")
                        if "FVI" in bands:
                            veg_bands.append("FVI")
                        
                        # Combine all bands
                        all_bands = sel[:3] + ir_bands
                        if water_band:
                            all_bands.append(water_band)
                        all_bands.extend(veg_bands)
                        
                        img_sel = img_p.select(all_bands)
                    except Exception:
                        continue
                    
                    # OPTIMIZATION: Only add images with reasonable quality scores
                    # Skip very low quality images to reduce processing
                    if quality_score < 0.3:  # Skip images with quality < 30%
                        continue
                    
                    # Ensure quality band is explicitly float to match all images in collection
                    # Use toFloat() to ensure server-side type consistency
                    quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                    img_sel = img_sel.addBands(quality_band)
                    prepared.append(img_sel)
                    # Format satellite name for histogram
                    sat_name = key.replace("LANDSAT_", "Landsat-").replace("_", "-")
                    satellite_contributions.append(sat_name)
                except Exception as e:
                    logging.debug(f"Skipping {key} image {i}: {e}")
                    continue
        except Exception as e:
            logging.debug(f"Error processing {key}: {e}")
            continue
    
    # Process MODIS - LAST RESORT ONLY (only if no other satellite has <50% clouds)
    # First, check if we have any acceptable images from higher-resolution satellites
    has_acceptable_images = len(prepared) > 0  # If we have any images from other satellites, MODIS is not needed
    
    # Check cloud fractions of existing images to see if MODIS is needed
    if include_modis and has_acceptable_images:
        # MODIS is only needed if all other satellites have >50% clouds
        # Since we already filtered for <50% clouds in metadata and <60% after processing,
        # if we have any images in 'prepared', it means we have acceptable alternatives
        # So skip MODIS entirely
        logging.debug("Skipping MODIS: higher-resolution satellites have acceptable images available")
        include_modis = False
    
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
                        
                        # MODIS is LAST RESORT - check clouds BEFORE processing further
                        if cf > 0.5:  # Only use MODIS if it has <50% clouds
                            if test_callback:
                                test_callback(tile_idx, test_num, "MODIS", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds - last resort only)")
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
                        
                        # OPTIMIZATION: Early exit for very cloudy MODIS
                        # Note: cf was already calculated above, no need to recalculate
                        if cf > 0.7:  # MODIS is lower res, be more lenient but still filter
                            if test_callback:
                                test_callback(tile_idx, test_num, "MODIS", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds)")
                            continue
                        
                        # MODIS typically has higher view angles, so estimate
                        # MODIS native resolution: 250m - HEAVILY PENALIZED (last resort only)
                        # Apply severe penalty: MODIS should only win if everything else is >50% clouds
                        base_score = compute_quality_score(cf, None, 15.0, vf, days_since, max_days, native_resolution=250.0)
                        # Additional 50% penalty to make MODIS truly last resort
                        quality_score = base_score * 0.5
                        
                        # Report test result
                        if test_callback:
                            test_callback(tile_idx, test_num, "MODIS", img_date_str, quality_score, None)
                        
                        # MODIS is last resort - only use if cloud fraction is acceptable
                        # Since MODIS already has severe penalty, be more lenient on quality threshold
                        # but still require reasonable clouds
                        # Note: cf was already checked above, but check again after quality score calculation
                        if cf > 0.5:  # Only use MODIS if it has <50% clouds (same as other satellites)
                            if test_callback:
                                test_callback(tile_idx, test_num, "MODIS", img_date_str, None, f"SKIPPED ({cf*100:.1f}% clouds - last resort only)")
                            continue
                        
                        # Skip very low quality MODIS images (after penalty)
                        if quality_score < 0.2:  # Lower threshold since we already penalized heavily
                            continue
                        
                        # Harmonize MODIS (lower resolution, so scale appropriately)
                        if enable_harmonize:
                            img_p = img_p.multiply(1.05)  # Slight adjustment
                        
                        try:
                            band_names = img_p.bandNames().getInfo()
                            if "B4" in band_names and "B3" in band_names and "B2" in band_names:
                                sel_bands = ["B4","B3","B2"]  # RGB
                                
                                # Add IR bands
                                if "B8" in band_names:
                                    sel_bands.append("B8")
                                if "B11" in band_names:
                                    sel_bands.append("B11")
                                if "B12" in band_names:
                                    sel_bands.append("B12")
                                
                                # Add water indices
                                water_band = "NDWI" if "NDWI" in band_names else None
                                if water_band:
                                    sel_bands.append(water_band)
                                
                                # Add vegetation indices
                                if "NDVI" in band_names:
                                    sel_bands.append("NDVI")
                                if "EVI" in band_names:
                                    sel_bands.append("EVI")
                                if "SAVI" in band_names:
                                    sel_bands.append("SAVI")
                                if "AVI" in band_names:
                                    sel_bands.append("AVI")
                                if "FVI" in band_names:
                                    sel_bands.append("FVI")
                                
                                sel = img_p.select(sel_bands)
                            else:
                                continue
                        except Exception:
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        sel = sel.addBands(quality_band)
                        prepared.append(sel)
                        satellite_contributions.append("MODIS")
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
                        
                        img_p = prepare_aster_image(img)
                        cf, vf = estimate_cloud_fraction(img_p, geom)
                        
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
                        
                        # ASTER native resolution: 15m
                        quality_score = compute_quality_score(cf, None, None, vf, days_since, max_days, native_resolution=15.0)
                        
                        # Report test result
                        if test_callback:
                            test_callback(tile_idx, test_num, "ASTER", img_date_str, quality_score, None)
                        
                        try:
                            band_names = img_p.bandNames().getInfo()
                            if "B4" in band_names and "B3" in band_names and "B2" in band_names:
                                sel_bands = ["B4","B3","B2"]  # RGB
                                
                                # Add IR bands
                                if "B8" in band_names:
                                    sel_bands.append("B8")
                                if "B11" in band_names:
                                    sel_bands.append("B11")
                                if "B12" in band_names:
                                    sel_bands.append("B12")
                                
                                # Add water indices
                                water_band = "NDWI" if "NDWI" in band_names else None
                                if water_band:
                                    sel_bands.append(water_band)
                                
                                # Add vegetation indices
                                if "NDVI" in band_names:
                                    sel_bands.append("NDVI")
                                if "EVI" in band_names:
                                    sel_bands.append("EVI")
                                if "SAVI" in band_names:
                                    sel_bands.append("SAVI")
                                if "AVI" in band_names:
                                    sel_bands.append("AVI")
                                if "FVI" in band_names:
                                    sel_bands.append("FVI")
                                
                                sel = img_p.select(sel_bands)
                            else:
                                continue
                        except Exception:
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        sel = sel.addBands(quality_band)
                        prepared.append(sel)
                        satellite_contributions.append("ASTER")
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
                        
                        img_p = prepare_viirs_image(img)
                        cf, vf = estimate_cloud_fraction(img_p, geom)
                        
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
                        
                        # VIIRS native resolution: 375m
                        quality_score = compute_quality_score(cf, None, None, vf, days_since, max_days, native_resolution=375.0)
                        
                        # Report test result
                        if test_callback:
                            test_callback(tile_idx, test_num, "VIIRS", img_date_str, quality_score, None)
                        
                        try:
                            band_names = img_p.bandNames().getInfo()
                            if "B4" in band_names and "B3" in band_names and "B2" in band_names:
                                sel_bands = ["B4","B3","B2"]  # RGB
                                
                                # Add IR bands
                                if "B8" in band_names:
                                    sel_bands.append("B8")
                                if "B11" in band_names:
                                    sel_bands.append("B11")
                                if "B12" in band_names:
                                    sel_bands.append("B12")
                                
                                # Add water indices
                                water_band = "NDWI" if "NDWI" in band_names else None
                                if water_band:
                                    sel_bands.append(water_band)
                                
                                # Add vegetation indices
                                if "NDVI" in band_names:
                                    sel_bands.append("NDVI")
                                if "EVI" in band_names:
                                    sel_bands.append("EVI")
                                if "SAVI" in band_names:
                                    sel_bands.append("SAVI")
                                if "AVI" in band_names:
                                    sel_bands.append("AVI")
                                if "FVI" in band_names:
                                    sel_bands.append("FVI")
                                
                                sel = img_p.select(sel_bands)
                            else:
                                continue
                        except Exception:
                            continue
                        
                        # Ensure quality band is explicitly float to match all images in collection
                        # Use toFloat() to ensure server-side type consistency
                        quality_band = ee.Image.constant(float(quality_score)).toFloat().rename("quality")
                        sel = sel.addBands(quality_band)
                        prepared.append(sel)
                        satellite_contributions.append("VIIRS")
                    except Exception as e:
                        logging.debug(f"Skipping VIIRS image {i}: {e}")
                        continue
        except Exception as e:
            logging.debug(f"Error processing VIIRS: {e}")
    
    if len(prepared) == 0:
        return None, None, None
    
    # Create collection from ALL satellites
    col = ee.ImageCollection(prepared)
    
    # Use qualityMosaic - this selects the BEST pixel from ALL images based on quality score
    # This is per-pixel selection across ALL satellites - no sensor bias!
    try:
        mosaic = col.qualityMosaic("quality")
        method = "qualityMosaic_multi_sensor"
    except Exception:
        # Fallback to median composite if qualityMosaic fails
        try:
            mosaic = col.median()
            method = "median_multi_sensor"
        except Exception:
            # Last resort: mean
            mosaic = col.mean()
            method = "mean_multi_sensor"
    
    # Use more accurate reprojection: determine optimal CRS for the tile
    center_lon = (lon_min + lon_max) / 2.0
    center_lat = (lat_min + lat_max) / 2.0
    zone, north = lonlat_to_utm_zone(center_lon, center_lat)
    if north:
        utm_crs = f"EPSG:{32600 + zone}"
    else:
        utm_crs = f"EPSG:{32700 + zone}"
    
    # Reproject to UTM for better accuracy, then clip
    # Note: resolution is handled in process_tile, so we use a reasonable default here
    mosaic = mosaic.reproject(crs=utm_crs, scale=TARGET_RES)
    mosaic = mosaic.clip(geom)
    
    # Apply additional quality filters: ensure no invalid values
    mosaic = mosaic.updateMask(mosaic.select(0).gt(0))  # Mask pixels where first band is invalid
    
    # Determine dominant satellite for this tile (most common contributor)
    dominant_satellite = None
    if satellite_contributions:
        satellite_counts = Counter(satellite_contributions)
        dominant_satellite = satellite_counts.most_common(1)[0][0] if satellite_counts else None
        
        # Debug: Log satellite contributions for this tile
        if tile_idx is not None:
            total_images = len(satellite_contributions)
            sat_summary = ", ".join([f"{sat}: {count}" for sat, count in satellite_counts.most_common()])
            logging.debug(f"[Tile {tile_idx:04d}] Mosaic contributors: {total_images} images from {len(satellite_counts)} sensors ({sat_summary}), dominant: {dominant_satellite}")
    
    return mosaic, method, dominant_satellite


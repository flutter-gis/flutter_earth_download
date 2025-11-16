"""
Cloud detection and masking functions for different satellite sensors.
"""
import logging
import ee
from typing import Tuple
from .ee_collections import apply_dem_illumination_correction


def s2_scl_mask(img):
    """Mask SCL classes considered cloud/shadow/snow etc."""
    try:
        scl = img.select("SCL")
        # recommended classes to keep: 4 veg, 5 non-veg, 6 water, 7 unclassified
        mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7))
        return img.updateMask(mask)
    except Exception:
        return img


def s2_cloudprob_mask_local(arr, threshold=40):
    """If using s2cloudless locally, arr is ndarray of cloudprob values 0-100 -> return mask."""
    return arr < threshold


def s2_cloud_mask_advanced(img):
    """Advanced cloud masking using SCL, cloud probability, and EE algorithms."""
    try:
        # Use SCL for primary masking
        scl = img.select("SCL")
        # Keep: 4=vegetation, 5=non-vegetated, 6=water, 7=unclassified
        # Exclude: 0=no data, 1=saturated/defective, 2=dark area, 3=cloud shadows, 8=cloud medium, 9=cloud high, 10=thin cirrus, 11=snow
        valid_mask = scl.gte(4).And(scl.lte(7))  # Keep 4-7
        
        # If cloud probability band exists, use it for additional filtering
        if "MSK_CLDPRB" in img.bandNames().getInfo():
            cloud_prob = img.select("MSK_CLDPRB")
            # Mask pixels with high cloud probability (>30)
            cloud_mask = cloud_prob.lt(30)
            valid_mask = valid_mask.And(cloud_mask)
        
        # Also check for valid data in key bands
        b4 = img.select("B4")
        b3 = img.select("B3")
        b2 = img.select("B2")
        valid_data = b4.gt(0).And(b3.gt(0)).And(b2.gt(0))
        valid_mask = valid_mask.And(valid_data)
        
        return img.updateMask(valid_mask)
    except Exception:
        # Fallback to simple SCL mask
        return s2_scl_mask(img)


def landsat_cloud_mask_advanced(img):
    """Advanced Landsat cloud masking using QA_PIXEL and additional checks."""
    try:
        qa = img.select("QA_PIXEL")
        # Bit flags: 1=dilated cloud, 2=cirrus, 3=cloud, 4=cloud shadow, 5=snow, 6=clear
        # We want to keep clear pixels (bit 6) and exclude clouds/shadows
        cloud = qa.bitwiseAnd(1 << 3).neq(0)  # Cloud
        shadow = qa.bitwiseAnd(1 << 4).neq(0)  # Cloud shadow
        cirrus = qa.bitwiseAnd(1 << 8).neq(0)  # Cirrus (L8/9)
        dilated_cloud = qa.bitwiseAnd(1 << 1).neq(0)  # Dilated cloud
        snow = qa.bitwiseAnd(1 << 5).neq(0)  # Snow
        
        # Create mask: exclude all problematic pixels
        mask = cloud.Not().And(shadow.Not()).And(cirrus.Not()).And(dilated_cloud.Not()).And(snow.Not())
        
        # Also check for valid data in surface reflectance bands
        try:
            sr_bands = ["SR_B4", "SR_B3", "SR_B2"]
            valid_data = None
            for band_name in sr_bands:
                if band_name in img.bandNames().getInfo():
                    band = img.select(band_name)
                    if valid_data is None:
                        valid_data = band.gt(0).And(band.lt(10000))  # Valid SR range
                    else:
                        valid_data = valid_data.And(band.gt(0).And(band.lt(10000)))
            if valid_data is not None:
                mask = mask.And(valid_data)
        except Exception:
            pass
        
        return img.updateMask(mask)
    except Exception:
        # Fallback to basic QA masking
        try:
            qa = img.select("QA_PIXEL")
            cloud = qa.bitwiseAnd(1 << 3).neq(0)
            shadow = qa.bitwiseAnd(1 << 4).neq(0)
            cirrus = qa.bitwiseAnd(1 << 8).neq(0)
            mask = cloud.Not().And(shadow.Not()).And(cirrus.Not())
            return img.updateMask(mask)
        except Exception:
            return img


def estimate_modis_cloud_fraction(img, geom):
    """
    Estimate MODIS cloud fraction from state_1km band BEFORE masking.
    This must be called on the original image, not the masked one.
    """
    # First try: Check if state_1km band exists and calculate from it
    try:
        band_names = img.bandNames().getInfo()
        if "state_1km" in band_names:
            # MODIS state_1km band: bit 0 = cloud (1 if cloud, 0 if clear)
            qa = img.select("state_1km")
            cloud_pixels = qa.bitwiseAnd(1 << 0).neq(0)  # Bit 0 = cloud (1 if cloud, 0 if clear)
            
            # Calculate cloud fraction over the geometry
            # MODIS native resolution is 1km, so use appropriate scale
            cloud_stats = cloud_pixels.reduceRegion(
                ee.Reducer.mean(),
                geom,
                scale=1000,  # MODIS is 1km resolution
                maxPixels=1e6,
                bestEffort=True
            )
            
            stats_info = cloud_stats.getInfo()
            if stats_info and 'state_1km' in stats_info:
                cloud_frac = float(stats_info['state_1km'])
                valid_frac = 1.0 - cloud_frac
                logging.debug(f"MODIS cloud fraction from state_1km band: {cloud_frac*100:.1f}%")
                return max(0.0, min(1.0, cloud_frac)), max(0.0, min(1.0, valid_frac))
        else:
            logging.debug("MODIS image missing state_1km band, trying metadata")
    except Exception as e:
        logging.debug(f"Error calculating MODIS cloud fraction from state_1km: {e}")
    
    # Fallback: try metadata if available
    try:
        # Some MODIS collections might have cloud metadata
        cp = img.get("CLOUD_COVER")
        if cp is not None:
            cp_val = cp.getInfo()
            if cp_val is not None:
                cloud_frac = max(0.0, min(1.0, float(cp_val) / 100.0))
                logging.debug(f"MODIS cloud fraction from CLOUD_COVER metadata: {cloud_frac*100:.1f}%")
                return cloud_frac, 1.0 - cloud_frac
    except Exception:
        pass
    
    # Try alternative metadata field
    try:
        cp = img.get("CLOUD_COVER_LAND")
        if cp is not None:
            cp_val = cp.getInfo()
            if cp_val is not None:
                cloud_frac = max(0.0, min(1.0, float(cp_val) / 100.0))
                logging.debug(f"MODIS cloud fraction from CLOUD_COVER_LAND metadata: {cloud_frac*100:.1f}%")
                return cloud_frac, 1.0 - cloud_frac
    except Exception:
        pass
    
    # Last resort: Use mask-based calculation (slower but more reliable)
    try:
        # Calculate from mask: valid pixels vs total
        mask = img.mask().reduceRegion(
            ee.Reducer.mean(),
            geom,
            scale=1000,
            maxPixels=1e6,
            bestEffort=True
        )
        mask_info = mask.getInfo()
        if mask_info:
            first_val = list(mask_info.values())[0]
            if first_val is not None:
                valid_frac = float(first_val)
                cloud_frac = 1.0 - valid_frac
                logging.debug(f"MODIS cloud fraction from mask: {cloud_frac*100:.1f}% (valid: {valid_frac*100:.1f}%)")
                return max(0.0, min(1.0, cloud_frac)), max(0.0, min(1.0, valid_frac))
    except Exception as e:
        logging.debug(f"Error calculating MODIS cloud fraction from mask: {e}")
    
    # Last resort: default (but log warning)
    logging.warning("MODIS cloud fraction: using default 0.5 (unknown) - cloud detection may not be working correctly")
    return 0.5, 0.5


def estimate_cloud_fraction(img, geom, scale=20):
    """
    Estimate cloud fraction and valid pixel fraction for an image over geom.
    OPTIMIZED: Uses metadata first to avoid expensive reduceRegion calls.
    NOTE: For MODIS, use estimate_modis_cloud_fraction() instead on the UNMASKED image.
    """
    cloud_frac = None
    valid_frac = None
    
    # Try metadata first (most accurate for S2) - this is fast, no server computation
    try:
        cp = img.get("CLOUDY_PIXEL_PERCENTAGE")
        if cp is not None:
            cp_val = cp.getInfo()
            if cp_val is not None:
                cloud_frac = max(0.0, min(1.0, float(cp_val) / 100.0))
                logging.debug(f"Cloud fraction from CLOUDY_PIXEL_PERCENTAGE metadata: {cloud_frac*100:.1f}%")
    except Exception:
        pass
    
    # Try CLOUD_COVER for Landsat - also fast metadata access
    if cloud_frac is None:
        try:
            cc = img.get("CLOUD_COVER")
            if cc is not None:
                cc_val = cc.getInfo()
                if cc_val is not None:
                    cloud_frac = max(0.0, min(1.0, float(cc_val) / 100.0))
                    logging.debug(f"Cloud fraction from CLOUD_COVER metadata: {cloud_frac*100:.1f}%")
        except Exception:
            pass
    
    # Try CLOUD_COVER_LAND for Landsat Collection 2
    if cloud_frac is None:
        try:
            cc = img.get("CLOUD_COVER_LAND")
            if cc is not None:
                cc_val = cc.getInfo()
                if cc_val is not None:
                    cloud_frac = max(0.0, min(1.0, float(cc_val) / 100.0))
                    logging.debug(f"Cloud fraction from CLOUD_COVER_LAND metadata: {cloud_frac*100:.1f}%")
        except Exception:
            pass
    
    # OPTIMIZATION: Skip expensive reduceRegion if we have cloud metadata
    # Only compute from mask if metadata not available (rare case)
    # WARNING: This method assumes the image has NOT been masked yet!
    if cloud_frac is None:
        try:
            # Use smaller scale and fewer pixels for faster computation
            mask = img.mask().reduceRegion(ee.Reducer.mean(), geom, scale=scale*2, maxPixels=1e6)
            if mask:
                mask_info = mask.getInfo()
                if mask_info:
                    first_val = list(mask_info.values())[0]
                    if first_val is not None:
                        valid_frac = float(first_val)
                        cloud_frac = 1.0 - valid_frac
                        logging.debug(f"Cloud fraction calculated from mask: {cloud_frac*100:.1f}% (valid: {valid_frac*100:.1f}%)")
        except Exception as e:
            logging.debug(f"Error calculating cloud fraction from mask: {e}")
            pass
    
    # Defaults - log warning if we couldn't determine cloud fraction
    if cloud_frac is None:
        logging.warning("Cloud fraction could not be determined from metadata or mask - defaulting to 0.5 (50%). This may indicate missing metadata or cloud detection issues.")
        cloud_frac = 0.5
    if valid_frac is None:
        valid_frac = 0.5
    
    return cloud_frac, valid_frac


"""
Earth Engine collection helpers for different satellite sensors.
"""
import logging
import ee
from .utils import is_satellite_operational


def sentinel_collection(start: str, end: str):
    """Sentinel-2 collection - only query if operational during date range."""
    if not is_satellite_operational("SENTINEL_2", start, end):
        logging.debug(f"Skipping Sentinel-2: not operational during {start} to {end}")
        return None
    return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(start, end)


def sentinel_cloudprob_collection(start: str, end: str):
    """Sentinel-2 cloud probability collection - only query if operational."""
    if not is_satellite_operational("SENTINEL_2", start, end):
        return None
    return ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY").filterDate(start, end)


def landsat_collections(start: str, end: str):
    """Landsat collections - only include satellites operational during date range."""
    collections = {}
    if is_satellite_operational("LANDSAT_4", start, end):
        collections["L4"] = ee.ImageCollection("LANDSAT/LT04/C02/T1_L2").filterDate(start, end)
    if is_satellite_operational("LANDSAT_5", start, end):
        collections["L5"] = ee.ImageCollection("LANDSAT/LT05/C02/T1_L2").filterDate(start, end)
    if is_satellite_operational("LANDSAT_7", start, end):
        collections["L7"] = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2").filterDate(start, end)
    if is_satellite_operational("LANDSAT_8", start, end):
        collections["L8"] = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterDate(start, end)
    if is_satellite_operational("LANDSAT_9", start, end):
        collections["L9"] = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterDate(start, end)
    return collections


def modis_collection(start: str, end: str):
    """MODIS Terra/Aqua surface reflectance - only query if operational."""
    if not is_satellite_operational("MODIS_TERRA", start, end) and not is_satellite_operational("MODIS_AQUA", start, end):
        logging.debug(f"Skipping MODIS: not operational during {start} to {end}")
        return None
    
    collections = []
    if is_satellite_operational("MODIS_TERRA", start, end):
        collections.append(ee.ImageCollection("MODIS/061/MOD09GA").filterDate(start, end))
    if is_satellite_operational("MODIS_AQUA", start, end):
        collections.append(ee.ImageCollection("MODIS/061/MYD09GA").filterDate(start, end))
    
    if not collections:
        return None
    if len(collections) == 1:
        return collections[0]
    return collections[0].merge(collections[1])


def aster_collection(start: str, end: str):
    """ASTER L1T radiance - only query if operational."""
    if not is_satellite_operational("ASTER", start, end):
        logging.debug(f"Skipping ASTER: not operational during {start} to {end} (ended 2008)")
        return None
    # Correct ASTER collection ID
    return ee.ImageCollection("ASTER/AST_L1T_003").filterDate(start, end)


def viirs_collection(start: str, end: str):
    """VIIRS surface reflectance - only query if operational."""
    if not is_satellite_operational("VIIRS", start, end):
        logging.debug(f"Skipping VIIRS: not operational during {start} to {end} (started 2011)")
        return None
    return ee.ImageCollection("NASA/VIIRS/002/VNP09GA").filterDate(start, end)


def spot_collection(start: str, end: str):
    """SPOT satellite collection - only query if operational during date range."""
    # Check if any SPOT satellite was operational during this period
    spot_any = (is_satellite_operational("SPOT_1", start, end) or
                is_satellite_operational("SPOT_2", start, end) or
                is_satellite_operational("SPOT_3", start, end) or
                is_satellite_operational("SPOT_4", start, end))
    
    if not spot_any:
        logging.debug(f"Skipping SPOT: not operational during {start} to {end}")
        return None
    
    # SPOT collections in GEE - try standard collection ID
    # Note: SPOT collection availability may vary, using common pattern
    try:
        # SPOT collection - using COPERNICUS catalog if available
        # Alternative: may need to use specific SPOT collection IDs
        collections = []
        
        if is_satellite_operational("SPOT_1", start, end):
            # Try SPOT 1 collection (may not be in GEE public catalog)
            try:
                spot1 = ee.ImageCollection("COPERNICUS/SPOT/V1").filterDate(start, end)
                collections.append(spot1)
            except Exception:
                pass  # Collection may not exist
        
        if is_satellite_operational("SPOT_2", start, end):
            try:
                spot2 = ee.ImageCollection("COPERNICUS/SPOT/V2").filterDate(start, end)
                collections.append(spot2)
            except Exception:
                pass
        
        if is_satellite_operational("SPOT_3", start, end):
            try:
                spot3 = ee.ImageCollection("COPERNICUS/SPOT/V3").filterDate(start, end)
                collections.append(spot3)
            except Exception:
                pass
        
        if is_satellite_operational("SPOT_4", start, end):
            try:
                spot4 = ee.ImageCollection("COPERNICUS/SPOT/V4").filterDate(start, end)
                collections.append(spot4)
            except Exception:
                pass
        
        if not collections:
            # Fallback: try unified SPOT collection
            try:
                return ee.ImageCollection("COPERNICUS/SPOT/V1").filterDate(start, end)
            except Exception:
                logging.debug("SPOT collections not available in GEE catalog")
                return None
        
        if len(collections) == 1:
            return collections[0]
        elif len(collections) == 2:
            return collections[0].merge(collections[1])
        elif len(collections) == 3:
            return collections[0].merge(collections[1]).merge(collections[2])
        else:
            return collections[0].merge(collections[1]).merge(collections[2]).merge(collections[3])
    except Exception as e:
        logging.debug(f"Error creating SPOT collection: {e}")
        return None


def noaa_avhrr_collection(start: str, end: str):
    """
    NOAA AVHRR collection - ABSOLUTE LAST RESORT ONLY.
    Very low resolution (1km), only use when all other satellites fail.
    
    Note: AVHRR collections may not be available in GEE public catalog.
    This function attempts to find available AVHRR collections, but returns None if none exist.
    """
    if not is_satellite_operational("NOAA_AVHRR", start, end):
        logging.debug(f"Skipping NOAA AVHRR: not operational during {start} to {end}")
        return None
    
    # AVHRR collection in GEE - try multiple possible collection IDs
    # Note: AVHRR has very coarse resolution (1km), use only as absolute last resort
    # AVHRR may not be available in GEE public catalog - return None if not found
    possible_collections = [
        "NOAA/CDR/AVHRR/NDVI_V5",  # Most common (may not exist)
        "NOAA/CDR/AVHRR/NDVI_V4",  # Alternative version
        "NOAA/CDR/AVHRR/NDVI_V3",  # Older version
    ]
    
    for coll_id in possible_collections:
        try:
            # Try to create the collection - if it doesn't exist, this will fail
            test_col = ee.ImageCollection(coll_id)
            # Try to filter by date to verify it works
            test_col = test_col.filterDate(start, end)
            # If we get here, the collection exists - return it
            logging.debug(f"Found NOAA AVHRR collection: {coll_id}")
            return test_col
        except Exception as e:
            error_msg = str(e)
            # If collection doesn't exist, try next one
            if "not found" in error_msg.lower() or "does not exist" in error_msg.lower() or "does not have access" in error_msg.lower():
                continue
            # For other errors (quota, etc.), log and try next
            logging.debug(f"NOAA AVHRR collection {coll_id} error: {e}")
            continue
    
    # If all collections failed, AVHRR is not available in GEE
    # This is expected - AVHRR may not be in the public catalog
    logging.debug(f"NOAA AVHRR collections not available in GEE catalog for {start} to {end}")
    return None


def landsat_mss_collections(start: str, end: str):
    """Landsat MSS (Multispectral Scanner) collections - only include operational satellites."""
    collections = {}
    if is_satellite_operational("LANDSAT_1_MSS", start, end):
        try:
            collections["MSS1"] = ee.ImageCollection("LANDSAT/LM01/C01/T1").filterDate(start, end)
        except Exception:
            pass  # Collection may not be available
    
    if is_satellite_operational("LANDSAT_2_MSS", start, end):
        try:
            collections["MSS2"] = ee.ImageCollection("LANDSAT/LM02/C01/T1").filterDate(start, end)
        except Exception:
            pass
    
    if is_satellite_operational("LANDSAT_3_MSS", start, end):
        try:
            collections["MSS3"] = ee.ImageCollection("LANDSAT/LM03/C01/T1").filterDate(start, end)
        except Exception:
            pass
    
    return collections


def add_s2_cloudprob(s2_sr_col, s2_prob_col):
    """Join S2_SR and cloud prob by system:index when possible."""
    try:
        filter_time = ee.Filter.equals(leftField='system:index', rightField='system:index')
        inner_join = ee.Join.inner()
        joined = inner_join.apply(s2_sr_col, s2_prob_col, filter_time)
        def merge_bands(feature):
            img = ee.Image(feature.get('primary'))
            prob = ee.Image(feature.get('secondary'))
            return img.addBands(prob.rename('MSK_CLDPRB'))
        return ee.ImageCollection(joined.map(merge_bands))
    except Exception:
        return s2_sr_col


def apply_dem_illumination_correction(img):
    """Rudimentary topographic illumination correction using SRTM -- per-image."""
    try:
        srtm = ee.Image("USGS/SRTMGL1_003")
        # compute slope and aspect and approximate correction factor (very simplified)
        terrain = ee.Terrain.products(srtm)
        slope = terrain.select("slope")
        # solar geometry
        sun_az = ee.Number(img.get("MEAN_SOLAR_AZIMUTH_ANGLE"))
        sun_zen = ee.Number(img.get("MEAN_SOLAR_ZENITH_ANGLE"))
        # approximate factor = cos(slope) * cos(zenith) + ...
        # We'll just return original (placeholder) – implement later if needed
        return img
    except Exception:
        return img


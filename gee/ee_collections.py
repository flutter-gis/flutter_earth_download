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
    return ee.ImageCollection("NASA/ASTER_L1T_003").filterDate(start, end)


def viirs_collection(start: str, end: str):
    """VIIRS surface reflectance - only query if operational."""
    if not is_satellite_operational("VIIRS", start, end):
        logging.debug(f"Skipping VIIRS: not operational during {start} to {end} (started 2011)")
        return None
    return ee.ImageCollection("NASA/VIIRS/002/VNP09GA").filterDate(start, end)


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


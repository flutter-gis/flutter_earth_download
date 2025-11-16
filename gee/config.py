"""
Configuration constants and default values.
"""
import multiprocessing
import logging

# Default bounding box (Dead Sea approximate)
DEFAULT_BBOX = (34.9, 31.0, 35.8, 32.0)
DEFAULT_START = "2000-11-01"
DEFAULT_END = "2025-11-30"

# Tile configuration
DEFAULT_TILE_PIX = 2048  # Reduced from 4096 to avoid 50MB download limit
TARGET_RES = 5.0  # meters (5m resolution)
DEFAULT_TILE_SIDE_M = DEFAULT_TILE_PIX * TARGET_RES

# Download limits
MAX_DOWNLOAD_SIZE_BYTES = 50331648  # 50MB limit for getDownloadURL
SAFE_DOWNLOAD_SIZE_BYTES = 41943040  # 40MB safe limit (80% of 50MB)
MIN_TILE_PIXELS = 256  # Minimum tile size for GEE getDownloadURL

# Retry configuration
EXPORT_RETRIES = 5
EXPORT_POLL_INTERVAL = 8
EXPORT_POLL_TIMEOUT = 60 * 30
DOWNLOAD_RETRIES = 3
DOWNLOAD_RETRY_DELAY = 2  # seconds, with exponential backoff

# Processing configuration
MIN_WATER_AREA_PX = 40
MANIFEST_CSV = "deadsea_manifest.csv"
OUTDIR_DEFAULT = "deadsea_outputs"
COG_OVERVIEWS = [2, 4, 8, 16, 32]
MAX_CONCURRENT_TILES = 10  # Limit concurrent tile processing to avoid memory issues
DEFAULT_WORKERS = min(multiprocessing.cpu_count(), 8)  # Auto-detect CPU count, cap at 8
ENABLE_DYNAMIC_WORKERS = True  # Enable dynamic worker scaling based on system performance
DYNAMIC_WORKER_CHECK_INTERVAL = 10  # Check and adjust workers every N completed tiles
MIN_WORKERS = 1  # Minimum number of workers
MAX_WORKERS = 16  # Maximum number of workers (can exceed CPU count for I/O-bound tasks)

# Limit images fetched per satellite after server-side filtering/sorting
MAX_IMAGES_PER_SATELLITE = 5

# Quality weights for scoring (no sensor bias - purely quality-based)
# Resolution is prioritized: a 30m image with some clouds is better than a 400m image with no clouds
QUALITY_WEIGHTS = {
    "cloud_fraction": 0.25,      # 25% weight on cloud cover (lower is better)
    "solar_zenith": 0.15,        # 15% weight on sun angle (lower zenith = better)
    "view_zenith": 0.10,         # 10% weight on view angle (lower = more nadir = better)
    "valid_pixels": 0.15,        # 15% weight on valid data coverage
    "temporal_recency": 0.05,    # 5% weight on how recent the image is
    "resolution": 0.30           # 30% weight on native resolution (higher res = better) - PRIORITIZED
}

# Satellite operational date ranges
SATELLITE_DATE_RANGES = {
    # Landsat satellites
    "LANDSAT_5": ("1984-03-01", "2013-05-30"),  # Ended May 2013
    "LANDSAT_7": ("1999-04-15", None),  # Still operational, but SLC failure on 2003-05-31 causes data gaps
    "LANDSAT_7_SLC_FAILURE": ("2003-05-31", None),  # SLC failure date - images have black stripes after this
    "LANDSAT_8": ("2013-02-11", None),  # Still operational
    "LANDSAT_9": ("2021-09-27", None),  # Launched September 2021
    
    # Sentinel satellites
    "SENTINEL_2": ("2015-06-23", None),  # Operational since June 2015
    
    # MODIS
    "MODIS_TERRA": ("2000-02-24", None),  # Terra launched February 2000
    "MODIS_AQUA": ("2002-07-04", None),   # Aqua launched July 2002
    
    # ASTER
    "ASTER": ("2000-03-01", "2008-04-01"),  # ASTER on Terra, ended April 2008
    
    # VIIRS
    "VIIRS": ("2011-10-28", None),  # VIIRS on Suomi NPP, launched October 2011
}

# Sensor harmonization coefficients
HARMONIZATION_COEFFS = {
    # sentinel to landsat-ish mapping example: out = a * sentinel + b
    "S2_to_LS": {"a": 0.98, "b": 0.01},
    "LS_to_S2": {"a": 1.02, "b": -0.01}
}


def update_connection_pool_size(worker_count: int):
    """
    Dynamically update urllib3 connection pool size based on worker count.
    Each worker can make multiple concurrent requests, so we need 2x + buffer.
    
    Args:
        worker_count: Current number of active workers
    
    Returns:
        int: The new pool size that was set, or None if update failed
    """
    try:
        import urllib3
        
        # Calculate pool size: 2x workers + 10 for headroom
        pool_size = max(worker_count * 2 + 10, 20)  # Minimum 20
        
        # Update the default pool size for new connections
        urllib3.poolmanager.PoolManager.DEFAULT_POOLSIZE = pool_size
        
        # Also try to update existing pool managers if possible
        # Note: This affects new connections, existing ones will use their current pool size
        # but new requests will use the updated size
        
        logging.debug(f"Updated urllib3 connection pool size to {pool_size} (workers: {worker_count})")
        return pool_size
    except Exception as e:
        logging.warning(f"Failed to update connection pool size: {e}")
        return None


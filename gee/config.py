"""
Configuration constants and default values.
"""
import multiprocessing
import logging
import os

# Earth Engine authentication
# Service account key file path (if using service account authentication)
# Set to None to use user authentication, or provide a path to a service account JSON key file
# Common locations checked (in order):
# 1. GEE_SERVICE_ACCOUNT_KEY environment variable
# 2. "gee_service_account.json" in project root
# 3. "keys/gee_service_account.json" in project root
# 4. Custom path set here
GEE_SERVICE_ACCOUNT_KEY = None  # Set to path like "/path/to/service-account-key.json" if using service account
GEE_PROJECT = None  # Set to your Google Cloud project ID if needed (extracted from key file if not set)

# Default bounding box (Dead Sea approximate)
# Set to None to start with empty bbox, or provide default coordinates
DEFAULT_BBOX = None  # None = empty, user must enter or select from map
DEFAULT_START = "1985-01-01"  # Both Landsat 4 and 5 operational - better coverage and redundancy
DEFAULT_END = "2025-11-30"

# Tile configuration
DEFAULT_TILE_PIX = 2048  # Reduced from 4096 to avoid 50MB download limit
TARGET_RES = 10.0  # meters (10m resolution - native Sentinel-2, preserves best quality)
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
    "LANDSAT_4": ("1982-07-16", "1993-12-14"),  # Landsat 4 TM (30m resolution) - fills gap before L5
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
    
    # SPOT satellites (10m pan, 20m multispectral)
    "SPOT_1": ("1986-02-22", "2003-05-31"),  # SPOT 1 operational period
    "SPOT_2": ("1990-01-22", "2009-07-31"),  # SPOT 2 operational period
    "SPOT_3": ("1993-09-26", "1997-11-14"),  # SPOT 3 operational period (failed 1996)
    "SPOT_4": ("1998-03-24", "2013-07-31"),  # SPOT 4 operational period
    
    # Landsat MSS (Multispectral Scanner) - earlier Landsat missions
    "LANDSAT_1_MSS": ("1972-07-23", "1978-01-06"),  # Landsat 1 MSS
    "LANDSAT_2_MSS": ("1975-01-22", "1982-02-25"),  # Landsat 2 MSS
    "LANDSAT_3_MSS": ("1978-03-05", "1983-03-31"),  # Landsat 3 MSS
    
    # NOAA AVHRR - ABSOLUTE LAST RESORT (1km resolution, very coarse)
    # Only use when ALL other satellites fail to provide usable imagery
    "NOAA_AVHRR": ("1978-06-01", None),  # AVHRR operational since 1978, very low resolution (1km)
}

# Sensor harmonization coefficients
HARMONIZATION_COEFFS = {
    # sentinel to landsat-ish mapping example: out = a * sentinel + b
    "S2_to_LS": {"a": 0.98, "b": 0.01},
    "LS_to_S2": {"a": 1.02, "b": -0.01},
    # SPOT to Landsat harmonization (SPOT has similar spectral bands but needs slight adjustment)
    "SPOT_to_LS": {"a": 1.00, "b": 0.00},  # SPOT bands are reasonably compatible, minimal adjustment needed
    "LS_to_SPOT": {"a": 1.00, "b": 0.00},
    # Landsat MSS to TM harmonization (MSS has different bands, requires scaling)
    "MSS_to_LS": {"a": 0.95, "b": 0.02},  # MSS bands need slight adjustment for compatibility
    "LS_to_MSS": {"a": 1.05, "b": -0.02},
    # NOAA AVHRR harmonization (very coarse resolution, minimal adjustment)
    "AVHRR_to_LS": {"a": 0.98, "b": 0.01},  # AVHRR bands are reasonably compatible
    "LS_to_AVHRR": {"a": 1.02, "b": -0.01},
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


"""
Utility functions for date ranges, coordinate transformations, and tiling.
"""
import math
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
import pyproj
from shapely.geometry import box
from shapely.ops import transform as shp_transform

from .config import SAFE_DOWNLOAD_SIZE_BYTES


def month_ranges(start_iso: str, end_iso: str):
    """Generate month ranges between start and end dates."""
    s = datetime.fromisoformat(start_iso)
    e = datetime.fromisoformat(end_iso)
    cur = datetime(s.year, s.month, 1)
    end_month = datetime(e.year, e.month, 1)
    while cur <= end_month:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = nxt - timedelta(days=1)
        yield cur.date().isoformat(), last.date().isoformat()
        cur = nxt


def lonlat_to_utm_zone(lon: float, lat: float):
    """Calculate UTM zone number and hemisphere from longitude/latitude."""
    zone = int((lon + 180) / 6) + 1
    north = lat >= 0
    return zone, north


def calculate_max_tile_pixels_for_size(max_size_bytes: int = SAFE_DOWNLOAD_SIZE_BYTES, 
                                       num_bands: int = 4, 
                                       bytes_per_pixel: int = 4) -> int:
    """Calculate maximum tile pixels (width*height) that fit within size limit."""
    max_pixels_squared = max_size_bytes / (num_bands * bytes_per_pixel)
    max_pixels_per_side = int(math.sqrt(max_pixels_squared))
    return max_pixels_per_side


def make_utm_tiles(bbox: Tuple[float, float, float, float], 
                   tile_side_m: Optional[float] = None, 
                   max_tiles: Optional[int] = None):
    """
    Divide bbox into tiles in UTM projection near center and return wgs84 bounds.
    
    If max_tiles is specified, calculates tile size to achieve approximately that many tiles.
    Otherwise, uses tile_side_m to determine tile size.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    center_lon = (lon_min + lon_max) / 2.0
    center_lat = (lat_min + lat_max) / 2.0
    zone, north = lonlat_to_utm_zone(center_lon, center_lat)
    proj_wgs84 = pyproj.CRS("EPSG:4326")
    if north:
        utm_crs = pyproj.CRS.from_proj4(f"+proj=utm +zone={zone} +datum=WGS84 +units=m +no_defs")
    else:
        utm_crs = pyproj.CRS.from_proj4(f"+proj=utm +zone={zone} +south +datum=WGS84 +units=m +no_defs")
    to_utm = pyproj.Transformer.from_crs(proj_wgs84, utm_crs, always_xy=True).transform
    to_wgs = pyproj.Transformer.from_crs(utm_crs, proj_wgs84, always_xy=True).transform
    poly = box(lon_min, lat_min, lon_max, lat_max)
    poly_utm = shp_transform(to_utm, poly)
    minx, miny, maxx, maxy = poly_utm.bounds
    width_m = maxx - minx
    height_m = maxy - miny
    
    # If max_tiles is specified, calculate tile size to achieve that many tiles
    if max_tiles is not None and max_tiles > 0:
        # Calculate aspect ratio
        aspect = width_m / height_m if height_m > 0 else 1.0
        # For approximately square tiles, solve: nx * ny ≈ max_tiles, where nx/ny ≈ aspect
        nx = max(1, round(math.sqrt(max_tiles * aspect)))
        ny = max(1, round(math.sqrt(max_tiles / aspect)))
        # Adjust to get as close as possible to max_tiles
        while nx * ny < max_tiles and (nx + 1) * ny <= max_tiles * 1.1:
            nx += 1
        while nx * ny < max_tiles and nx * (ny + 1) <= max_tiles * 1.1:
            ny += 1
        # Now calculate tile size from nx and ny
        tile_side_x = width_m / nx
        tile_side_y = height_m / ny
        tile_side_m = min(tile_side_x, tile_side_y)  # Use smaller dimension for square tiles
        logging.info("Calculated tile size for max_tiles=%d: %.1fm, resulting in %dx%d=%d tiles", 
                    max_tiles, tile_side_m, nx, ny, nx * ny)
    else:
        # Use provided tile_side_m
        if tile_side_m is None or tile_side_m <= 0:
            raise ValueError("Either tile_side_m or max_tiles must be provided")
        nx = max(1, math.ceil(width_m / tile_side_m))
        ny = max(1, math.ceil(height_m / tile_side_m))
    
    tiles = []
    for i in range(nx):
        for j in range(ny):
            x0 = minx + i * width_m / nx
            x1 = minx + (i + 1) * width_m / nx
            y0 = miny + j * height_m / ny
            y1 = miny + (j + 1) * height_m / ny
            tile_utm = box(x0, y0, x1, y1)
            tile_wgs = shp_transform(to_wgs, tile_utm)
            tiles.append(tile_wgs.bounds)
    return tiles


def is_satellite_operational(satellite_name: str, start: str, end: str) -> bool:
    """
    Check if a satellite was operational during the requested date range.
    
    Args:
        satellite_name: Name of the satellite (e.g., "LANDSAT_9", "SENTINEL_2")
        start: Start date in ISO format (YYYY-MM-DD)
        end: End date in ISO format (YYYY-MM-DD)
    
    Returns:
        True if satellite was operational during the date range, False otherwise
    """
    from .config import SATELLITE_DATE_RANGES
    
    if satellite_name not in SATELLITE_DATE_RANGES:
        # If satellite not in our list, assume it's available (backward compatibility)
        return True
    
    sat_start, sat_end = SATELLITE_DATE_RANGES[satellite_name]
    request_start = datetime.fromisoformat(start)
    request_end = datetime.fromisoformat(end)
    
    # Check if request overlaps with satellite operational period
    if sat_end is None:
        # Satellite still operational - check if request is after start
        sat_start_dt = datetime.fromisoformat(sat_start)
        return request_end >= sat_start_dt
    else:
        # Satellite has ended - check if request overlaps
        sat_start_dt = datetime.fromisoformat(sat_start)
        sat_end_dt = datetime.fromisoformat(sat_end)
        return request_start <= sat_end_dt and request_end >= sat_start_dt


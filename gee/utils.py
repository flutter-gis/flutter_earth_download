"""
Utility functions for date ranges, coordinate transformations, and tiling.
"""
import math
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Union, List, Dict
import pyproj
from shapely.geometry import box, shape, Polygon, GeometryCollection
from shapely.ops import transform as shp_transform

try:
    import fiona
    from fiona.crs import from_epsg
    FIONA_AVAILABLE = True
except ImportError:
    FIONA_AVAILABLE = False

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


def make_utm_tiles(geometry: Union[Tuple[float, float, float, float], Polygon, Dict], 
                   tile_side_m: Optional[float] = None, 
                   max_tiles: Optional[int] = None) -> List[Dict]:
    """
    Divide geometry (bbox or polygon) into tiles in UTM projection and return wgs84 bounds.
    
    Supports both rectangular bounding boxes and arbitrary polygons.
    For polygons, only tiles that intersect the polygon are returned, and tiles are clipped.
    
    Args:
        geometry: Either:
            - Tuple[float, float, float, float]: (lon_min, lat_min, lon_max, lat_max) for bbox
            - Polygon: Shapely Polygon geometry
            - Dict: GeoJSON-like dict with 'type' and 'coordinates' or 'geometry'
        tile_side_m: Optional tile side length in meters
        max_tiles: Optional maximum number of tiles (calculates tile size automatically)
    
    Returns:
        List of dicts, each containing:
            - 'bounds': (lon_min, lat_min, lon_max, lat_max) - bounding box of tile
            - 'geometry': Optional Polygon - clipped geometry if original was polygon, None for bbox
            - 'is_clipped': bool - True if tile was clipped to polygon boundary
    """
    # Convert input to Shapely Polygon
    if isinstance(geometry, tuple) and len(geometry) == 4:
        # Bounding box: (lon_min, lat_min, lon_max, lat_max)
        lon_min, lat_min, lon_max, lat_max = geometry
        polygon = box(lon_min, lat_min, lon_max, lat_max)
        is_bbox = True
    elif isinstance(geometry, Polygon):
        polygon = geometry
        is_bbox = False
    elif isinstance(geometry, dict):
        # GeoJSON-like dict
        if 'geometry' in geometry:
            polygon = shape(geometry['geometry'])
            is_bbox = False
        elif 'type' in geometry and geometry['type'] == 'Polygon':
            polygon = shape(geometry)
            is_bbox = False
        elif 'type' in geometry and geometry['type'] == 'Feature':
            polygon = shape(geometry.get('geometry', geometry))
            is_bbox = False
        elif 'coordinates' in geometry:
            polygon = shape({'type': 'Polygon', 'coordinates': geometry['coordinates']})
            is_bbox = False
        else:
            # Try to extract bbox
            if 'bbox' in geometry:
                bbox = geometry['bbox']
                if len(bbox) == 4:
                    lon_min, lat_min, lon_max, lat_max = bbox
                    polygon = box(lon_min, lat_min, lon_max, lat_max)
                    is_bbox = True
                else:
                    raise ValueError(f"Invalid bbox format: {bbox}")
            else:
                raise ValueError(f"Cannot parse geometry from dict: {geometry}")
    else:
        raise ValueError(f"Unsupported geometry type: {type(geometry)}")
    
    # Get bounding box of polygon
    lon_min, lat_min, lon_max, lat_max = polygon.bounds
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
    
    # Transform polygon to UTM for accurate tile generation
    poly_utm = shp_transform(to_utm, polygon)
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
        logging.info("Calculated tile size for max_tiles=%d: %.1fm, resulting in %dx%d=%d potential tiles", 
                    max_tiles, tile_side_m, nx, ny, nx * ny)
    else:
        # Use provided tile_side_m
        if tile_side_m is None or tile_side_m <= 0:
            raise ValueError("Either tile_side_m or max_tiles must be provided")
        nx = max(1, math.ceil(width_m / tile_side_m))
        ny = max(1, math.ceil(height_m / tile_side_m))
    
    tiles = []
    tiles_intersecting = 0
    
    # Generate grid of tiles and filter/clip to polygon
    for i in range(nx):
        for j in range(ny):
            x0 = minx + i * width_m / nx
            x1 = minx + (i + 1) * width_m / nx
            y0 = miny + j * height_m / ny
            y1 = miny + (j + 1) * height_m / ny
            tile_utm = box(x0, y0, x1, y1)
            
            # Check if tile intersects with polygon
            if not tile_utm.intersects(poly_utm):
                continue  # Skip tiles that don't intersect
            
            tiles_intersecting += 1
            
            if is_bbox:
                # For bbox, just return the bounds (no clipping needed)
                tile_wgs = shp_transform(to_wgs, tile_utm)
                tiles.append({
                    'bounds': tile_wgs.bounds,
                    'geometry': None,
                    'is_clipped': False
                })
            else:
                # For polygon, clip tile to polygon boundary
                clipped_utm = tile_utm.intersection(poly_utm)
                
                # Skip if intersection is empty or invalid
                if clipped_utm.is_empty or not clipped_utm.is_valid:
                    continue
                
                # Convert back to WGS84
                clipped_wgs = shp_transform(to_wgs, clipped_utm)
                
                # Get bounds of clipped geometry
                clipped_bounds = clipped_wgs.bounds
                
                # Store as GeoJSON-like dict for easy serialization
                if isinstance(clipped_wgs, GeometryCollection):
                    # Take first valid geometry from collection
                    for geom in clipped_wgs.geoms:
                        if geom.is_valid and not geom.is_empty:
                            clipped_wgs = geom
                            break
                
                tiles.append({
                    'bounds': clipped_bounds,
                    'geometry': clipped_wgs,  # Shapely Polygon
                    'is_clipped': True
                })
    
    logging.info("Generated %d tiles (out of %d potential) that intersect with geometry", 
                tiles_intersecting, nx * ny)
    
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


def geojson_to_shapefile(geojson_path: str, shapefile_path: str) -> bool:
    """
    Convert a GeoJSON file to a shapefile.
    
    Args:
        geojson_path: Path to input GeoJSON file
        shapefile_path: Path to output shapefile (without extension, .shp will be added)
    
    Returns:
        True if successful, False otherwise
    """
    if not FIONA_AVAILABLE:
        logging.error("fiona is required for shapefile export. Install with: pip install fiona")
        return False
    
    try:
        # Read GeoJSON with UTF-8 encoding
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        # Handle both Feature and FeatureCollection
        if geojson_data.get('type') == 'Feature':
            features = [geojson_data]
        elif geojson_data.get('type') == 'FeatureCollection':
            features = geojson_data.get('features', [])
        else:
            logging.error("Invalid GeoJSON format: expected Feature or FeatureCollection")
            return False
        
        if not features:
            logging.error("No features found in GeoJSON")
            return False
        
        # Get geometry from first feature to determine schema
        first_geom = features[0].get('geometry', {})
        geom_type = first_geom.get('type', 'Polygon')
        
        # Sanitize property names for shapefile (no spaces, max 10 chars, alphanumeric + underscore)
        # Shapefile field names have restrictions: max 10 characters, no spaces, alphanumeric + underscore only
        def sanitize_field_name(name):
            """Sanitize field name for shapefile compatibility."""
            # Replace spaces and special chars with underscore
            import re
            sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
            # Truncate to 10 characters (shapefile limit)
            if len(sanitized) > 10:
                sanitized = sanitized[:10]
            # Ensure it starts with a letter or underscore
            if sanitized and not (sanitized[0].isalpha() or sanitized[0] == '_'):
                sanitized = '_' + sanitized
            # Ensure it's not empty
            if not sanitized:
                sanitized = 'field'
            return sanitized
        
        # Sanitize properties from first feature
        original_props = features[0].get('properties', {})
        sanitized_props = {}
        for key, value in original_props.items():
            sanitized_key = sanitize_field_name(key)
            # Handle value types - shapefiles support: str, int, float, date
            if isinstance(value, (int, float, str)):
                # Determine type from value
                if isinstance(value, int):
                    sanitized_props[sanitized_key] = 'int'
                elif isinstance(value, float):
                    sanitized_props[sanitized_key] = 'float'
                else:
                    # String - limit to 254 chars (shapefile limit)
                    sanitized_props[sanitized_key] = 'str:254'
            else:
                # Convert other types to string
                sanitized_props[sanitized_key] = 'str:254'
        
        # Also create a mapping to transform feature properties when writing
        field_mapping = {}
        for key in original_props.keys():
            sanitized_key = sanitize_field_name(key)
            field_mapping[key] = sanitized_key
        
        # Define schema
        schema = {
            'geometry': geom_type,
            'properties': sanitized_props
        }
        
        # Ensure shapefile path has .shp extension
        if not shapefile_path.endswith('.shp'):
            shapefile_path = shapefile_path + '.shp'
        
        # Create shapefile
        with fiona.open(shapefile_path, 'w', 
                       driver='ESRI Shapefile',
                       crs=from_epsg(4326),  # WGS84
                       schema=schema) as shp:
            for feature in features:
                # Transform feature properties to match sanitized schema
                original_feature_props = feature.get('properties', {})
                sanitized_feature_props = {}
                for orig_key, orig_value in original_feature_props.items():
                    sanitized_key = sanitize_field_name(orig_key)
                    # Convert value to appropriate type
                    if isinstance(orig_value, (int, float, str)):
                        sanitized_feature_props[sanitized_key] = orig_value
                    else:
                        # Convert other types to string
                        sanitized_feature_props[sanitized_key] = str(orig_value)[:254] if orig_value else ''
                
                # Create new feature with sanitized properties
                sanitized_feature = {
                    'type': 'Feature',
                    'geometry': feature.get('geometry'),
                    'properties': sanitized_feature_props
                }
                shp.write(sanitized_feature)
        
        logging.info(f"Successfully converted GeoJSON to shapefile: {shapefile_path}")
        return True
        
    except Exception as e:
        logging.error(f"Error converting GeoJSON to shapefile: {e}")
        return False


def geojson_string_to_shapefile(geojson_str: str, shapefile_path: str) -> bool:
    """
    Convert a GeoJSON string to a shapefile.
    
    Args:
        geojson_str: GeoJSON string (Feature or FeatureCollection)
        shapefile_path: Path to output shapefile (without extension, .shp will be added)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        geojson_data = json.loads(geojson_str)
        
        # Create temporary GeoJSON file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp:
            json.dump(geojson_data, tmp)
            tmp_path = tmp.name
        
        try:
            result = geojson_to_shapefile(tmp_path, shapefile_path)
            return result
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        logging.error(f"Error converting GeoJSON string to shapefile: {e}")
        return False


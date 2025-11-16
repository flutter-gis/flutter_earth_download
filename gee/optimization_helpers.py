"""
Optimization helper functions for batch operations, caching, and parallel processing.
"""
import logging
import threading
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import ee


# Global cache for band names (per satellite type)
_band_name_cache: Dict[str, List[str]] = {}
_cache_lock = threading.Lock()


def get_cached_band_names(img: ee.Image, satellite_type: str) -> List[str]:
    """
    Get band names with caching per satellite type.
    Band names are usually consistent within a satellite type, so we cache them.
    
    Args:
        img: Earth Engine image
        satellite_type: Satellite identifier (e.g., "S2", "LANDSAT_8", "MODIS")
    
    Returns:
        List of band names
    """
    with _cache_lock:
        if satellite_type not in _band_name_cache:
            try:
                _band_name_cache[satellite_type] = img.bandNames().getInfo()
            except Exception as e:
                logging.debug(f"Failed to cache band names for {satellite_type}: {e}")
                return []
        return _band_name_cache[satellite_type].copy()


def clear_band_name_cache():
    """Clear the band name cache (useful for testing or when switching regions)."""
    global _band_name_cache
    with _cache_lock:
        _band_name_cache.clear()


def batch_fetch_metadata(images: List[ee.Image], metadata_keys: List[str]) -> List[Dict[str, Any]]:
    """
    Batch fetch metadata from multiple images to reduce round-trips.
    Instead of N individual .getInfo() calls, this batches them efficiently.
    
    Args:
        images: List of Earth Engine images
        metadata_keys: List of metadata keys to fetch (e.g., ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE"])
    
    Returns:
        List of dictionaries, each containing the requested metadata for one image
    """
    if not images:
        return []
    
    results = []
    
    # Use ThreadPoolExecutor to fetch metadata in parallel
    # This allows multiple .getInfo() calls to happen concurrently
    def fetch_single_metadata(img: ee.Image, keys: List[str]) -> Dict[str, Any]:
        """Fetch metadata for a single image."""
        metadata = {}
        for key in keys:
            try:
                value = img.get(key)
                if value is not None:
                    metadata[key] = value.getInfo()
                else:
                    metadata[key] = None
            except Exception as e:
                logging.debug(f"Failed to fetch {key} from image: {e}")
                metadata[key] = None
        return metadata
    
    # Fetch metadata in parallel (up to 4 concurrent requests)
    with ThreadPoolExecutor(max_workers=min(4, len(images))) as executor:
        futures = {executor.submit(fetch_single_metadata, img, metadata_keys): i 
                   for i, img in enumerate(images)}
        
        # Collect results in order
        temp_results = [None] * len(images)
        for future in as_completed(futures):
            idx = futures[future]
            try:
                temp_results[idx] = future.result()
            except Exception as e:
                logging.debug(f"Error fetching metadata for image {idx}: {e}")
                temp_results[idx] = {key: None for key in metadata_keys}
        
        results = temp_results
    
    return results


def extract_metadata_parallel(images: List[ee.Image], 
                               metadata_keys: List[str],
                               max_workers: int = 4) -> List[Dict[str, Any]]:
    """
    Extract metadata from multiple images in parallel using ThreadPoolExecutor.
    This is more efficient than sequential .getInfo() calls.
    
    Args:
        images: List of Earth Engine images
        metadata_keys: List of metadata keys to extract
        max_workers: Maximum number of concurrent workers
    
    Returns:
        List of metadata dictionaries (one per image)
    """
    if not images:
        return []
    
    def extract_single(img: ee.Image) -> Dict[str, Any]:
        """Extract all requested metadata from a single image."""
        result = {}
        for key in metadata_keys:
            try:
                value = img.get(key)
                if value is not None:
                    result[key] = value.getInfo()
                else:
                    result[key] = None
            except Exception:
                result[key] = None
        return result
    
    results = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(images))) as executor:
        futures = [executor.submit(extract_single, img) for img in images]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logging.debug(f"Error in parallel metadata extraction: {e}")
                results.append({key: None for key in metadata_keys})
    
    return results


def calculate_tile_variance(tile_bounds: Tuple[float, float, float, float],
                            start: str, end: str) -> float:
    """
    Calculate a variance score for a tile to prioritize processing.
    Higher variance = more likely to need multiple images = process first.
    
    This is a heuristic based on:
    - Tile size (larger tiles = more variance)
    - Date range (longer ranges = more variance)
    - Geographic location (coastal/water areas = more variance)
    
    Args:
        tile_bounds: (min_lon, min_lat, max_lon, max_lat)
        start: Start date string
        end: End date string
    
    Returns:
        Variance score (higher = more priority)
    """
    # Simple heuristic: tile area * date range length
    min_lon, min_lat, max_lon, max_lat = tile_bounds
    tile_area = (max_lon - min_lon) * (max_lat - min_lat)
    
    # Date range length (in days, approximate)
    try:
        from datetime import datetime
        start_date = datetime.fromisoformat(start)
        end_date = datetime.fromisoformat(end)
        days = (end_date - start_date).days
    except Exception:
        days = 365  # Default
    
    # Variance score: larger tiles and longer date ranges = higher variance
    variance_score = tile_area * (1 + days / 365.0)
    
    return variance_score


"""
Quality score computation for satellite imagery.
"""
from typing import Optional
from .config import QUALITY_WEIGHTS


def compute_quality_score(cloud_fraction: float, 
                         solar_zenith: Optional[float] = None, 
                         view_zenith: Optional[float] = None, 
                         valid_pixel_fraction: Optional[float] = None,
                         days_since_start: Optional[int] = None, 
                         max_days: int = 365, 
                         native_resolution: Optional[float] = None):
    """
    Compute unified quality score across all sensors based on actual quality metrics.
    No sensor bias - purely based on image quality.
    Returns score 0-1, higher is better.
    """
    weights = QUALITY_WEIGHTS
    
    # Cloud fraction score (lower is better, so invert)
    cloud_score = max(0.0, 1.0 - cloud_fraction * 1.5)  # Penalize clouds more
    cloud_weighted = cloud_score * weights["cloud_fraction"]
    
    # Solar zenith score (lower zenith = higher sun = better)
    sun_score = 1.0
    if solar_zenith:
        if solar_zenith > 60:
            sun_score = max(0.2, 1.0 - (solar_zenith - 60) / 60.0)
        elif solar_zenith < 30:
            sun_score = 1.0
        else:
            sun_score = 1.0 - (solar_zenith - 30) / 100.0
    sun_weighted = sun_score * weights["solar_zenith"]
    
    # View zenith score (lower = more nadir = better)
    view_score = 1.0
    if view_zenith:
        if view_zenith > 10:
            view_score = max(0.5, 1.0 - (view_zenith - 10) / 40.0)
    view_weighted = view_score * weights["view_zenith"]
    
    # Valid pixel fraction score
    valid_score = 1.0
    if valid_pixel_fraction is not None:
        valid_score = max(0.3, valid_pixel_fraction)  # Penalize if < 30% valid
    valid_weighted = valid_score * weights["valid_pixels"]
    
    # Temporal recency score (prefer more recent images)
    temporal_score = 1.0
    if days_since_start is not None and max_days > 0:
        # Linear decay: newer images get higher score
        temporal_score = max(0.5, 1.0 - (days_since_start / max_days) * 0.5)
    temporal_weighted = temporal_score * weights["temporal_recency"]
    
    # Resolution score (higher resolution = better quality) - PRIORITIZED
    # Dramatic differences: 30m native is MUCH better than 400m native
    # Sentinel-2 (10m) > Landsat (30m) > MODIS (250m) > VIIRS (375m)
    resolution_score = 1.0
    if native_resolution:
        if native_resolution <= 4:
            resolution_score = 1.0   # Best: Sentinel-2 (10m) - perfect score
        elif native_resolution <= 15:
            resolution_score = 0.95  # Excellent: Sentinel-2 (10m), ASTER (15m)
        elif native_resolution <= 30:
            resolution_score = 0.85  # Good: Landsat (30m) - still very good
        elif native_resolution <= 60:
            resolution_score = 0.60  # Moderate: Lower resolution Landsat variants
        elif native_resolution <= 250:
            resolution_score = 0.40  # Poor: MODIS (250m) - significant penalty
        elif native_resolution <= 400:
            resolution_score = 0.25  # Very poor: VIIRS (375m) - heavy penalty
        else:
            resolution_score = 0.15  # Worst: Very coarse resolution - minimal score
    resolution_weighted = resolution_score * weights["resolution"]
    
    # Sum all weighted scores
    total_score = (cloud_weighted + sun_weighted + view_weighted + 
                   valid_weighted + temporal_weighted + resolution_weighted)
    
    return total_score


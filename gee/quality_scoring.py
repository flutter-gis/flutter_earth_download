"""
Quality score computation for satellite imagery.
"""
from typing import Optional, List
from .config import QUALITY_WEIGHTS


def check_band_completeness(band_names: List[str]) -> float:
    """
    Check completeness of critical bands for mosaic quality.
    Returns a completeness score (0.0 to 1.0) based on presence of critical bands.
    
    Critical bands:
    - RGB: B4 (Red), B3 (Green), B2 (Blue) - REQUIRED
    - IR: B8 (NIR), B11 (SWIR1), B12 (SWIR2) - HIGHLY DESIRED
    - Indices: NDWI/MNDWI, NDVI - DESIRED
    
    Handles multiple naming conventions:
    - Sentinel-2: B4, B3, B2, B8, B11, B12
    - Landsat 8/9: SR_B2, SR_B3, SR_B4, SR_B5 (NIR), SR_B6 (SWIR1), SR_B7 (SWIR2)
    - Landsat 4/5 Collection 2: SR_B1 (Blue), SR_B2 (Green), SR_B3 (Red), SR_B4 (NIR), SR_B5 (SWIR1), SR_B7 (SWIR2)
    - Landsat 5/7 Collection 1: B1, B2, B3, B4 (NIR), B5 (SWIR1), B7 (SWIR2)
    - MODIS: sur_refl_b01 (Red), sur_refl_b04 (Green), sur_refl_b03 (Blue), sur_refl_b02 (NIR)
    
    Returns:
        float: Completeness score (1.0 = all bands present, 0.0 = missing critical bands)
    """
    # Convert to set for faster lookup
    band_set = set(band_names)
    
    # Required bands (RGB) - must have all
    # Check multiple naming conventions
    required_present = 0
    
    # Detect Landsat version: Landsat 4/5 have SR_B1, Landsat 8/9 don't
    has_sr_b1 = "SR_B1" in band_set
    
    # Check for Red band
    if "B4" in band_set:
        required_present += 1
    elif has_sr_b1:
        # Landsat 4/5 Collection 2: SR_B3 is Red
        if "SR_B3" in band_set:
            required_present += 1
    else:
        # Landsat 8/9 Collection 2: SR_B4 is Red
        if "SR_B4" in band_set:
            required_present += 1
    
    # Check for Green band
    if "B3" in band_set:
        required_present += 1
    elif "SR_B3" in band_set and not has_sr_b1:  # Landsat 8/9: SR_B3 is Green
        required_present += 1
    elif "SR_B2" in band_set and has_sr_b1:  # Landsat 4/5: SR_B2 is Green
        required_present += 1
    
    # Check for Blue band
    if "B2" in band_set:
        required_present += 1
    elif has_sr_b1:
        # Landsat 4/5 Collection 2: SR_B1 is Blue
        if "SR_B1" in band_set:
            required_present += 1
    else:
        # Landsat 8/9 Collection 2: SR_B2 is Blue
        if "SR_B2" in band_set:
            required_present += 1
    
    if required_present < 3:
        return 0.0  # Missing critical RGB bands
    
    # Highly desired IR bands - check multiple naming conventions
    # After image preparation, bands should be renamed to B8, B11, B12
    # But we also check original names in case renaming hasn't happened yet
    ir_present = 0
    
    # Detect Landsat version: Landsat 4/5 have SR_B1, Landsat 8/9 don't
    has_sr_b1 = "SR_B1" in band_set
    
    # NIR band (B8)
    # Check renamed bands first (after landsat_prepare_image)
    if "B8" in band_set:
        ir_present += 1
    elif has_sr_b1:
        # Landsat 4/5 Collection 2: SR_B4 is NIR
        if "SR_B4" in band_set:
            ir_present += 1
    else:
        # Landsat 8/9 Collection 2: SR_B5 is NIR
        if "SR_B5" in band_set:
            ir_present += 1
        # For older Landsat (L5/L7 Collection 1), B4 is NIR, but we need to distinguish from red band
        # If we have SR_B4 (red from Landsat 8/9) and B4, then B4 is likely the NIR band
        elif "B4" in band_set and "SR_B4" in band_set:  # Older Landsat: B4 is NIR when SR_B4 exists (red)
            ir_present += 1
    
    # SWIR1 band (B11)
    if "B11" in band_set:
        ir_present += 1
    elif has_sr_b1:
        # Landsat 4/5 Collection 2: SR_B5 is SWIR1
        if "SR_B5" in band_set:
            ir_present += 1
    else:
        # Landsat 8/9 Collection 2: SR_B6 is SWIR1
        if "SR_B6" in band_set:
            ir_present += 1
        # Older Landsat Collection 1: B5 is SWIR1
        elif "B5" in band_set and "B11" not in band_set and "SR_B6" not in band_set:
            ir_present += 1
    
    # SWIR2 band (B12)
    if "B12" in band_set:
        ir_present += 1
    elif "SR_B7" in band_set:  # All Landsat Collection 2: SR_B7 is SWIR2
        ir_present += 1
    elif "B7" in band_set and "B12" not in band_set and "SR_B7" not in band_set:  # Older Landsat Collection 1: B7 is SWIR2
        ir_present += 1
    
    ir_score = ir_present / 3.0  # 0.0 to 1.0 based on IR completeness
    
    # Desired indices
    has_water_idx = any(b in band_set for b in ["NDWI", "MNDWI"])
    has_veg_idx = "NDVI" in band_set
    index_score = (1.0 if has_water_idx else 0.5) * (1.0 if has_veg_idx else 0.5)
    
    # Weighted completeness: RGB (required) + IR (60% weight) + Indices (20% weight)
    # Minimum score is 0.2 (if RGB present but no IR/indices)
    completeness = 1.0 * 0.2 + ir_score * 0.6 + index_score * 0.2
    
    return completeness


def compute_quality_score(cloud_fraction: float, 
                         solar_zenith: Optional[float] = None, 
                         view_zenith: Optional[float] = None, 
                         valid_pixel_fraction: Optional[float] = None,
                         days_since_start: Optional[int] = None, 
                         max_days: int = 365, 
                         native_resolution: Optional[float] = None,
                         band_completeness: Optional[float] = None):
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
    
    # Temporal recency score (prefer images closer to month midpoint for consistency)
    # OPTIMIZATION: Prefer images from middle of month for better temporal coherence
    temporal_score = 1.0
    if days_since_start is not None and max_days > 0:
        # Prefer images near month midpoint (better temporal consistency)
        month_midpoint = max_days / 2.0
        days_from_midpoint = abs(days_since_start - month_midpoint)
        
        # Best score at midpoint, decay as we move away
        # Within 5 days of midpoint: perfect score
        if days_from_midpoint <= 5:
            temporal_score = 1.0
        # Within 15 days: slight penalty
        elif days_from_midpoint <= 15:
            temporal_score = 0.95 - (days_from_midpoint - 5) / 200.0
        # Within 30 days: moderate penalty
        elif days_from_midpoint <= 30:
            temporal_score = 0.85 - (days_from_midpoint - 15) / 150.0
        # Beyond 30 days: significant penalty (but still better than very old)
        else:
            # Still prefer newer images over older ones
            recency_bonus = max(0.0, 0.3 - (days_since_start / max_days) * 0.2)
            temporal_score = max(0.5, 0.7 - (days_from_midpoint - 30) / max_days * 0.5) + recency_bonus
            temporal_score = min(1.0, temporal_score)
    
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
    
    # Band completeness score (penalize missing bands, especially IR bands)
    # Missing IR bands significantly impact mosaic quality (can't compute indices, etc.)
    completeness_weight = 0.10  # 10% weight on band completeness
    if band_completeness is not None:
        # Apply penalty: missing IR bands reduces score
        # If completeness < 0.7 (missing 2+ IR bands), apply significant penalty
        if band_completeness < 0.7:
            completeness_score = band_completeness * 0.7  # Heavy penalty for missing IR
        elif band_completeness < 0.9:
            completeness_score = 0.7 + (band_completeness - 0.7) * 1.5  # Moderate penalty
        else:
            completeness_score = 1.0  # Full score for complete bands
    else:
        completeness_score = 1.0  # Assume complete if not specified
    
    completeness_weighted = completeness_score * completeness_weight
    
    # Sum all weighted scores (normalize by total weight including completeness)
    total_weight = sum(weights.values()) + completeness_weight
    total_score = (cloud_weighted + sun_weighted + view_weighted + 
                   valid_weighted + temporal_weighted + resolution_weighted + 
                   completeness_weighted) / total_weight
    
    return total_score


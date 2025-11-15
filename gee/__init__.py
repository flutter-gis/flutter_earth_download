"""
GEE Satellite Imagery Processing Package

A production-grade satellite imagery downloader and processor with support for
multiple sensors (Sentinel-2, Landsat, MODIS, ASTER, VIIRS) with quality-based
mosaic generation.
"""

__version__ = "1.0.0"

# Main entry points
from .cli_gui import gui_and_run
from .processing import process_tile, process_month

# Core functions
from .mosaic_builder import build_best_mosaic_for_tile
from .cloud_detection import estimate_cloud_fraction, estimate_modis_cloud_fraction
from .quality_scoring import compute_quality_score

__all__ = [
    'gui_and_run',
    'process_tile',
    'process_month',
    'build_best_mosaic_for_tile',
    'estimate_cloud_fraction',
    'estimate_modis_cloud_fraction',
    'compute_quality_score',
]


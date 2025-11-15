# Modularization Plan

This document outlines the plan to split `gee.py` (3195 lines) into a modular structure.

## Module Structure

```
gee/
├── __init__.py              # Package initialization & exports
├── config.py                # ✅ DONE - Constants & configuration
├── utils.py                 # ✅ DONE - General utilities (tiling, dates, etc.)
├── ee_collections.py        # ✅ DONE - Earth Engine collection helpers
├── cloud_detection.py       # Cloud masking & fraction estimation
├── image_preparation.py     # Image prep (harmonization, indices, sensor-specific prep)
├── quality_scoring.py       # Quality score computation
├── mosaic_builder.py         # build_best_mosaic_for_tile
├── raster_processing.py      # Local raster ops (validation, masking, stitching)
├── download.py              # Download & export helpers
├── manifest.py              # Manifest management
├── visualization.py         # SatelliteHistogram class
├── processing.py            # process_tile, process_month
└── cli_gui.py              # GUI and CLI entry points
```

## Progress

- [x] config.py - All constants extracted
- [x] utils.py - Utility functions extracted
- [x] ee_collections.py - Earth Engine collections extracted
- [x] cloud_detection.py - Cloud masking and fraction estimation
- [x] image_preparation.py - Sensor-specific image prep and harmonization
- [x] quality_scoring.py - Quality score computation
- [x] mosaic_builder.py - Mosaic building logic (build_best_mosaic_for_tile)
- [x] raster_processing.py - Local raster operations (validation, masking, stitching, COG)
- [x] download.py - Download helpers (wait_for_task_done, download_tile_from_url)
- [x] manifest.py - Manifest management
- [x] visualization.py - SatelliteHistogram class
- [x] processing.py - process_tile, process_month
- [x] cli_gui.py - GUI and CLI entry points
- [x] main.py - New entry point created

## Next Steps

1. Continue extracting remaining modules
2. Update imports in each module
3. Create main.py entry point
4. Test that everything works
5. Update gee.py to import from modules (backward compatibility)


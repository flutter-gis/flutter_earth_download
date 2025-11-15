#!/usr/bin/env python3
"""
Main entry point for GEE Satellite Imagery Downloader.

This is the modularized version of the original gee.py file.
All functionality has been split into organized modules in the gee/ package.
"""
import sys
import logging

# Initialize Earth Engine
try:
    import ee
    ee.Initialize()
except Exception as e:
    print(f"ERROR: Earth Engine initialization failed: {e}", file=sys.stderr)
    print("Please run: earthengine authenticate", file=sys.stderr)
    sys.exit(1)

# Logging configuration
# Set to DEBUG to see detailed cloud fraction calculations
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
# Uncomment below to enable DEBUG logging for cloud fraction debugging:
# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s: %(message)s")

from gee.cli_gui import gui_and_run


if __name__ == "__main__":
    try:
        print("Starting GEE Downloader...")
        print("Initializing GUI...")
        gui_and_run()
        print("Program completed successfully.")
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logging.exception("Fatal error in main execution")
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")  # Keep window open to see error
        sys.exit(1)


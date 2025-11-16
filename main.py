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
    from gee.config import MAX_WORKERS, update_connection_pool_size
    
    # Set initial connection pool size based on MAX_WORKERS
    # This ensures we have enough connections from the start
    initial_pool_size = update_connection_pool_size(MAX_WORKERS)
    if initial_pool_size:
        logging.info(f"Initialized urllib3 connection pool size: {initial_pool_size} (based on MAX_WORKERS={MAX_WORKERS})")
    
    ee.Initialize()
except Exception as e:
    print(f"ERROR: Earth Engine initialization failed: {e}", file=sys.stderr)
    print("Please run: earthengine authenticate", file=sys.stderr)
    sys.exit(1)

# Logging configuration - output to both console and file
import os
from datetime import datetime

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# Create log file with timestamp
log_filename = f"gee_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_filepath = os.path.join(log_dir, log_filename)

# Set up logging with both console and file handlers
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Set root logger to DEBUG to capture all messages

# Suppress verbose DEBUG messages from third-party libraries
# These libraries are very chatty at DEBUG level
logging.getLogger('rasterio').setLevel(logging.WARNING)
logging.getLogger('rasterio._env').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('googleapiclient').setLevel(logging.WARNING)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)
logging.getLogger('google.auth').setLevel(logging.WARNING)
logging.getLogger('google.auth.transport').setLevel(logging.WARNING)

# Console handler - INFO level for console output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
console_handler.setFormatter(console_format)

# File handler - DEBUG level to capture everything (but third-party libs are suppressed)
file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter("%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s")
file_handler.setFormatter(file_format)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Log startup message
logging.info(f"Logging initialized. Log file: {log_filepath}")
logging.debug("DEBUG logging enabled - detailed information will be written to log file (third-party library DEBUG messages suppressed)")

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


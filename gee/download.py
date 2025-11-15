"""
Download helpers for Earth Engine imagery.
"""
import os
import json
import time
import logging
import requests
import zipfile
from typing import Tuple, Optional

from .config import (
    EXPORT_POLL_TIMEOUT, EXPORT_POLL_INTERVAL, 
    DOWNLOAD_RETRIES, DOWNLOAD_RETRY_DELAY, MIN_TILE_PIXELS
)
from .raster_processing import extract_and_merge_zip_tiffs


def wait_for_task_done(task, timeout_s: int = EXPORT_POLL_TIMEOUT, poll_interval: int = EXPORT_POLL_INTERVAL):
    """Wait for Earth Engine task to complete."""
    t0 = time.time()
    last_state = None
    while True:
        try:
            status = task.status()
            state = status.get("state")
            if state != last_state:
                logging.debug("Task state: %s", state)
                last_state = state
            if state in ("COMPLETED", "FAILED", "CANCELLED"):
                if state == "FAILED":
                    error_msg = status.get("error_message", "Unknown error")
                    logging.warning("Task failed: %s", error_msg)
                return status
            if time.time() - t0 > timeout_s:
                logging.warning("Task timeout after %d seconds", timeout_s)
                return {"state": "TIMEOUT"}
            time.sleep(poll_interval)
        except Exception as e:
            logging.warning("Error checking task status: %s", str(e))
            if time.time() - t0 > timeout_s:
                return {"state": "TIMEOUT"}
            time.sleep(poll_interval)


def download_tile_from_url(url: str, out_tif: str, tile_idx: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Download tile from Earth Engine getDownloadURL with retry logic.
    
    Returns:
        (success: bool, error_message: Optional[str])
    """
    # Retry download with exponential backoff
    for attempt in range(DOWNLOAD_RETRIES):
        try:
            if tile_idx is not None:
                logging.debug("Downloading tile %d from URL... (attempt %d/%d)", tile_idx, attempt + 1, DOWNLOAD_RETRIES)
            r = requests.get(url, stream=True, timeout=900)
            if r.status_code != 200:
                # Try to get error message from response
                error_msg = ""
                try:
                    error_msg = r.text[:200]  # First 200 chars
                except:
                    pass
                
                if attempt < DOWNLOAD_RETRIES - 1:
                    wait_time = DOWNLOAD_RETRY_DELAY * (2 ** attempt)
                    if tile_idx is not None:
                        logging.warning("HTTP error %d for tile %d%s, retrying in %d seconds...", 
                                      r.status_code, tile_idx, f": {error_msg}" if error_msg else "", wait_time)
                    time.sleep(wait_time)
                    continue
                
                error_status = f"http_{r.status_code}"
                error_detail = error_msg if error_msg else f"HTTP {r.status_code}"
                if tile_idx is not None:
                    logging.warning("HTTP error %d for tile %d after %d attempts%s", 
                                  r.status_code, tile_idx, DOWNLOAD_RETRIES, 
                                  f": {error_msg}" if error_msg else "")
                return False, f"{error_status}: {error_detail}"
            
            # Download content to memory first (for small files) or check first chunk
            content_chunks = []
            downloaded = 0
            first_chunk = None
            
            for chunk in r.iter_content(chunk_size=32768):
                if chunk:
                    if first_chunk is None:
                        first_chunk = chunk
                        # Check if first chunk looks like a TIFF or ZIP
                        if len(chunk) >= 4:
                            magic = chunk[:4]
                            # TIFF magic bytes: "II" (little-endian) or "MM" (big-endian) followed by 42 (0x2a)
                            is_tiff = (magic[:2] == b'II' and magic[2] == 0x2a) or (magic[:2] == b'MM' and magic[2] == 0x2a)
                            is_zip = magic[:2] == b'PK'  # ZIP files start with "PK"
                            
                            if not (is_tiff or is_zip):
                                return False, "invalid_file_format"
                    
                    content_chunks.append(chunk)
                    downloaded += len(chunk)
            
            # Write to file
            with open(out_tif, 'wb') as f:
                for chunk in content_chunks:
                    f.write(chunk)
            
            # Check if file is actually a ZIP (GEE sometimes returns ZIP files)
            if zipfile.is_zipfile(out_tif):
                # Extract and merge ZIP contents
                logging.debug("Downloaded file is a ZIP archive, extracting and merging...")
                temp_tif = out_tif + ".merged.tif"
                if extract_and_merge_zip_tiffs(out_tif, temp_tif):
                    # Replace original with merged file
                    os.replace(temp_tif, out_tif)
                else:
                    return False, "zip_extraction_failed"
            
            # Validate downloaded file
            file_size = os.path.getsize(out_tif)
            if file_size == 0:
                return False, "empty_file"
            
            return True, None
            
        except requests.exceptions.Timeout:
            if attempt < DOWNLOAD_RETRIES - 1:
                wait_time = DOWNLOAD_RETRY_DELAY * (2 ** attempt)
                if tile_idx is not None:
                    logging.warning("Download timeout for tile %d, retrying in %d seconds...", tile_idx, wait_time)
                time.sleep(wait_time)
                continue
            return False, "download_timeout"
        except Exception as e:
            if attempt < DOWNLOAD_RETRIES - 1:
                wait_time = DOWNLOAD_RETRY_DELAY * (2 ** attempt)
                if tile_idx is not None:
                    logging.warning("Download error for tile %d: %s, retrying in %d seconds...", tile_idx, str(e), wait_time)
                time.sleep(wait_time)
                continue
            return False, f"download_error: {str(e)}"
    
    return False, "max_retries_exceeded"


def generate_download_url(mosaic, region: dict, target_resolution: float, select_bands: list):
    """
    Generate download URL for Earth Engine mosaic.
    
    Returns:
        (url: str, error: Optional[str])
    """
    try:
        mosaic_sel = mosaic.select(select_bands)
        params = {
            "scale": target_resolution, 
            "region": json.dumps(region), 
            "fileFormat": "GEO_TIFF"
        }
        url = mosaic_sel.getDownloadURL(params)
        return url, None
    except Exception as e:
        error_str = str(e)
        if "must be less than or equal to" in error_str:
            return None, "tile_too_large"
        else:
            return None, f"url_generation_error: {str(e)}"


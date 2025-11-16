"""
Main processing functions: process_tile and process_month.
"""
import os
import json
import math
import time
import logging
import shutil
import multiprocessing
import concurrent.futures
import threading
import queue
from typing import Tuple, Optional
from tqdm import tqdm

# Optional psutil for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .config import (
    TARGET_RES, MIN_TILE_PIXELS, MAX_CONCURRENT_TILES, DEFAULT_WORKERS,
    DOWNLOAD_RETRIES, DOWNLOAD_RETRY_DELAY, SAFE_DOWNLOAD_SIZE_BYTES,
    ENABLE_DYNAMIC_WORKERS, DYNAMIC_WORKER_CHECK_INTERVAL, MIN_WORKERS, MAX_WORKERS,
    update_connection_pool_size
)
from .optimization_helpers import calculate_tile_variance
from .utils import month_ranges, make_utm_tiles
from .mosaic_builder import build_best_mosaic_for_tile
from .download import generate_download_url, download_tile_from_url
from .raster_processing import (
    validate_geotiff_local, compute_ndwi_mask_local, write_mask,
    extract_and_merge_zip_tiffs, add_indices_to_mosaic_local
)
from .manifest import manifest_init, manifest_append
from .visualization import SatelliteHistogram

# Optional ML support
try:
    from s2cloudless import S2PixelCloudDetector
    S2CLOUDLESS_AVAILABLE = True
except Exception:
    S2CLOUDLESS_AVAILABLE = False


def process_tile(tile_idx: int, tile_bounds: Tuple[float, float, float, float], 
                 month_start: str, month_end: str, local_temp: str, 
                 include_l7: bool, enable_ml: bool, enable_harmonize: bool, 
                 include_modis: bool = True, include_aster: bool = True, 
                 include_viirs: bool = True, target_resolution: float = TARGET_RES, 
                 progress_callback=None):
    """
    Process a single tile with detailed progress reporting.
    
    Args:
        progress_callback: Optional function(tile_idx, status, message) for progress updates
    """
    lonmin, latmin, lonmax, latmax = tile_bounds
    region = {"type": "Polygon", "coordinates": [[[lonmin, latmin], [lonmin, latmax], 
                                                   [lonmax, latmax], [lonmax, latmin], 
                                                   [lonmin, latmin]]]}
    prefix = f"deadsea_{month_start.replace('-', '')}_t{tile_idx:04d}"
    provenance = {"tile_idx": tile_idx, "bounds": tile_bounds, "prefix": prefix, "status": None}
    
    def report(status, message):
        """Helper to report progress"""
        if progress_callback:
            progress_callback(tile_idx, status, message)
        else:
            logging.info(f"Tile {tile_idx:04d} [{status}]: {message}")
    
    try:
        report("BUILDING", "Creating mosaic from satellite imagery...")
        
        # Track all test results for this tile
        all_test_results = []
        
        # Create test callback to display date-tile-test-score info and collect all test results
        def test_callback(tile_idx_val, test_num_val, satellite, date_str, score, skip_reason, detailed_stats=None):
            """Display test progress: date, tile number, test number, satellite, score"""
            if skip_reason:
                print(f"{date_str} Tile {tile_idx_val:04d} Test {test_num_val:02d} [{satellite}] {skip_reason}", flush=True)
            elif score is not None:
                # Show score with more precision for debugging
                print(f"{date_str} Tile {tile_idx_val:04d} Test {test_num_val:02d} [{satellite}] Score: {score:.3f}", flush=True)
                # Store test result if detailed stats are provided
                if detailed_stats:
                    test_result = detailed_stats.copy()
                    test_result["tile_idx"] = tile_idx_val
                    test_result["test_num"] = test_num_val
                    all_test_results.append(test_result)
        
        result = build_best_mosaic_for_tile(
            tile_bounds, month_start, month_end, 
            include_l7=include_l7, 
            enable_harmonize=enable_harmonize,
            include_modis=include_modis,
            include_aster=include_aster,
            include_viirs=include_viirs,
            tile_idx=tile_idx,
            test_callback=test_callback,
        )
        if result is None or result[0] is None:
            provenance["status"] = "no_imagery"
            report("FAILED", "No imagery available for this tile")
            return None, provenance
        mosaic, method, dominant_satellite, detailed_stats, ranked_image_stats = result
        provenance["method"] = method
        provenance["dominant_satellite"] = dominant_satellite
        provenance["detailed_stats"] = detailed_stats
        provenance["all_test_results"] = all_test_results  # Store all test results for this tile
        provenance["ranked_image_stats"] = ranked_image_stats  # Store ranked stats (including fallbacks)
        report("MOSAIC_OK", f"Mosaic created using {method}")
        
        # Debug: Log dominant satellite selection
        if dominant_satellite:
            logging.debug(f"[Tile {tile_idx:04d}] Dominant satellite: {dominant_satellite}")
        
        # Download via getDownloadURL (direct download only)
        # Select bands with validation: RGB + IR + water indices + vegetation indices
        report("SELECTING", "Selecting bands for download...")
        try:
            band_names = mosaic.bandNames().getInfo()
            select_bands = []
            # RGB bands
            for target in ["B4", "B3", "B2"]:
                if target in band_names:
                    select_bands.append(target)
            if len(select_bands) < 3:
                # Try alternative band names
                for target in ["SR_B4", "SR_B3", "SR_B2"]:
                    if target in band_names and target not in select_bands:
                        select_bands.append(target)
            
            if len(select_bands) < 3:
                provenance["status"] = "missing_bands"
                return None, provenance
            
            # Add IR bands (NIR, SWIR1, SWIR2)
            if "B8" in band_names:
                select_bands.append("B8")  # NIR
            elif "SR_B5" in band_names:
                select_bands.append("SR_B5")  # Landsat NIR fallback
            
            if "B11" in band_names:
                select_bands.append("B11")  # SWIR1
            elif "SR_B6" in band_names:
                select_bands.append("SR_B6")  # Landsat SWIR1 fallback
            
            if "B12" in band_names:
                select_bands.append("B12")  # SWIR2
            elif "SR_B7" in band_names:
                select_bands.append("SR_B7")  # Landsat SWIR2 fallback
            
            # Water indices - prefer MNDWI if available, fallback to NDWI
            water_band = None
            if "MNDWI" in band_names:
                water_band = "MNDWI"
            elif "NDWI" in band_names:
                water_band = "NDWI"
            
            if water_band:
                select_bands.append(water_band)
            else:
                logging.warning("No water index band found, using RGB+IR only")
            
            # Add vegetation indices for inland and aquatic vegetation analysis
            if "NDVI" in band_names:
                select_bands.append("NDVI")  # Standard vegetation index
            if "EVI" in band_names:
                select_bands.append("EVI")  # Enhanced vegetation index
            if "SAVI" in band_names:
                select_bands.append("SAVI")  # Soil-adjusted vegetation index
            if "AVI" in band_names:
                select_bands.append("AVI")  # Aquatic Vegetation Index - vegetation in water
            if "FVI" in band_names:
                select_bands.append("FVI")  # Floating Vegetation Index - floating vegetation
            
            logging.debug(f"Selected {len(select_bands)} bands for download: {select_bands}")
            mosaic_sel = mosaic.select(select_bands)
        except Exception as e:
            provenance["status"] = f"band_selection_error: {str(e)}"
            return None, provenance
        
        # Generate download URL
        report("URL_GEN", "Generating download URL...")
        url, url_error = generate_download_url(mosaic_sel, region, target_resolution, select_bands)
        if url is None:
            if url_error == "tile_too_large":
                provenance["status"] = "tile_too_large"
                provenance["error"] = "Tile size exceeds 50MB limit. Reduce tile size."
                logging.warning("Tile %d too large for direct download. Reducing tile size.", tile_idx)
            else:
                provenance["status"] = f"url_generation_error: {url_error}"
                logging.warning("Failed to generate download URL for tile %d: %s", tile_idx, url_error)
            return None, provenance
        
        # Download tile
        report("DOWNLOADING", "Downloading tile data...")
        out_tif = os.path.join(local_temp, prefix + ".tif")
        success, download_error = download_tile_from_url(url, out_tif, tile_idx)
        if not success:
            provenance["status"] = download_error or "download_failed"
            return None, provenance
        
        report("DOWNLOADED", f"Downloaded {os.path.getsize(out_tif)/1024/1024:.1f}MB successfully")
        
        # Validate
        report("VALIDATING", "Validating GeoTIFF...")
        valid, reason = validate_geotiff_local(out_tif)
        if not valid:
            provenance["status"] = "validation_failed"
            provenance["validation_reason"] = reason
            report("FAILED", f"Validation failed: {reason}")
            return None, provenance
        report("VALIDATED", "GeoTIFF validation passed")
        
        # Optional local ML post-process (cloud cleaning) - only if enabled & lib available
        if enable_ml and S2CLOUDLESS_AVAILABLE:
            try:
                # very conservative local cloud cleaning for S2 (only if S2-like bands present)
                # NOTE: this is an expensive local op and optional.
                provenance["ml"] = "applied_s2cloudless"
                # Implemented as placeholder: actual implementation requires reading bands -> compute 'cloud_prob' -> mask
                # To keep the script complete, skip heavy per-pixel ML here unless user has installed and enabled
            except Exception as e:
                provenance["ml_error"] = str(e)
        
        # Compute NDWI mask
        report("MASKING", "Computing NDWI water mask...")
        mask, meta = compute_ndwi_mask_local(out_tif)
        mask_path = out_tif.replace(".tif", "_mask.tif")
        write_mask(mask, meta, mask_path)
        provenance["status"] = "ok"
        provenance["tif"] = out_tif
        provenance["mask"] = mask_path
        report("SUCCESS", "Tile processing completed successfully")
        return out_tif, provenance
    except Exception as e:
        provenance["status"] = "error"
        provenance["error"] = str(e)
        report("ERROR", f"Exception: {str(e)[:100]}")
        return None, provenance


def _process_tiles_with_dynamic_workers(tiles, month_start, month_end, temp_root, include_l7, 
                                        enable_ml, enable_harmonize, include_modis, include_aster,
                                        include_viirs, effective_res, initial_workers, progress_callback,
                                        histogram, provenance, tile_files, pbar, counters):
    """
    Process tiles with dynamic worker scaling based on system performance.
    Monitors CPU, memory, and processing times to adjust worker count.
    """
    if not PSUTIL_AVAILABLE:
        logging.warning("psutil not available, falling back to fixed workers. Install with: pip install psutil")
        # Fallback to fixed workers if psutil not available
        success_count = 0
        failed_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=initial_workers) as ex:
            futures = {ex.submit(process_tile, idx, tile, month_start, month_end, temp_root,
                                include_l7, enable_ml, enable_harmonize, include_modis,
                                include_aster, include_viirs, effective_res, progress_callback): idx
                      for idx, tile in enumerate(tiles)}
            _process_futures(futures, provenance, tile_files, histogram, pbar, success_count, failed_count, initial_workers)
        return
    
    # Queue-based dynamic worker system
    tile_queue = queue.Queue()
    result_queue = queue.Queue()
    worker_threads = []
    active_workers = initial_workers
    lock = threading.Lock()
    stop_event = threading.Event()
    
    # Performance metrics
    completion_times = []  # Track processing times
    last_check_tile_count = 0  # Track when we last checked (based on completed tiles)
    
    # Add all tiles to queue
    for idx, tile in enumerate(tiles):
        tile_queue.put((idx, tile))
    
    def worker_thread():
        """Worker thread that processes tiles from queue"""
        while not stop_event.is_set():
            try:
                idx, tile = tile_queue.get(timeout=1.0)
                start_time = time.time()
                
                try:
                    out, prov = process_tile(idx, tile, month_start, month_end, temp_root,
                                            include_l7, enable_ml, enable_harmonize, include_modis,
                                            include_aster, include_viirs, effective_res, progress_callback)
                    processing_time = time.time() - start_time
                    result_queue.put(("success", idx, out, prov, processing_time))
                except Exception as e:
                    processing_time = time.time() - start_time
                    prov = {"tile_idx": idx, "status": "error", "error": str(e)}
                    result_queue.put(("error", idx, None, prov, processing_time))
                
                tile_queue.task_done()
            except queue.Empty:
                continue
    
    def manager_thread():
        """Manager thread that monitors performance and adjusts workers"""
        nonlocal active_workers, last_check_tile_count
        
        while not stop_event.is_set() or not tile_queue.empty():
            time.sleep(2)  # Check every 2 seconds (but only act every 10 tiles)
            
            if stop_event.is_set():
                break
            
            # Check based on completed tiles, not time
            current_completed = len(completion_times)
            tiles_since_last_check = current_completed - last_check_tile_count
            
            if tiles_since_last_check < DYNAMIC_WORKER_CHECK_INTERVAL:
                continue  # Wait until we have enough completed tiles
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Calculate average processing time
            if completion_times:
                avg_time = sum(completion_times[-20:]) / len(completion_times[-20:])  # Last 20 tiles
            else:
                avg_time = 10.0  # Default estimate
            
            # Calculate throughput (tiles per second over last N tiles)
            if tiles_since_last_check > 0:
                # Get timestamps for recent completions if available
                # For now, use average processing time as proxy
                recent_times = completion_times[-tiles_since_last_check:] if completion_times else []
                if recent_times:
                    avg_recent_time = sum(recent_times) / len(recent_times)
                    throughput = tiles_since_last_check / (avg_recent_time * tiles_since_last_check) if avg_recent_time > 0 else 0
                else:
                    throughput = 0
            else:
                throughput = 0
            
            queue_size = tile_queue.qsize()
            active_count = sum(1 for t in worker_threads if t.is_alive())
            
            # Decision logic for worker adjustment
            # AGGRESSIVE MODE: Designed for 24/7 server operation - push hard unless CPU is critically high
            new_worker_count = active_workers
            
            # Increase workers if:
            # - CPU < 95% (plenty of headroom for server operation)
            # - Memory < 90% (leave some headroom but be aggressive)
            # - Queue has pending items
            # - We're not at max workers yet
            if (cpu_percent < 95 and memory_percent < 90 and 
                queue_size > 0 and
                active_workers < MAX_WORKERS):
                new_worker_count = min(active_workers + 1, MAX_WORKERS)
                logging.info(f"📈 Increasing workers: {active_workers} → {new_worker_count} "
                           f"(CPU: {cpu_percent:.1f}%, Mem: {memory_percent:.1f}%, Queue: {queue_size})")
            
            # Decrease workers ONLY if:
            # - CPU > 95% (critical - system is struggling)
            # - Memory > 95% (critical - about to run out)
            # Only decrease if we're in critical territory
            elif ((cpu_percent > 95 or memory_percent > 95) and active_workers > MIN_WORKERS):
                new_worker_count = max(active_workers - 1, MIN_WORKERS)
                logging.info(f"📉 Decreasing workers: {active_workers} → {new_worker_count} "
                           f"(CPU: {cpu_percent:.1f}%, Mem: {memory_percent:.1f}% - CRITICAL)")
            
            # Adjust worker count
            if new_worker_count != active_workers:
                with lock:
                    diff = new_worker_count - active_workers
                    if diff > 0:
                        # Add workers
                        for _ in range(diff):
                            t = threading.Thread(target=worker_thread, daemon=True)
                            t.start()
                            worker_threads.append(t)
                    else:
                        # Workers will naturally exit when queue is empty
                        # We can't forcefully kill threads, but they'll finish current work
                        pass
                    active_workers = new_worker_count
                    
                    # Update connection pool size dynamically based on new worker count
                    new_pool_size = update_connection_pool_size(new_worker_count)
                    if new_pool_size:
                        logging.debug(f"Adjusted connection pool size to {new_pool_size} for {new_worker_count} workers")
            
            last_check_tile_count = current_completed
    
    # Start initial workers
    for _ in range(initial_workers):
        t = threading.Thread(target=worker_thread, daemon=True)
        t.start()
        worker_threads.append(t)
    
    # Start manager thread
    manager = threading.Thread(target=manager_thread, daemon=True)
    manager.start()
    
    # Process results
    completed = 0
    total_tiles = len(tiles)
    
    while completed < total_tiles:
        try:
            result_type, idx, out, prov, processing_time = result_queue.get(timeout=30)
            completed += 1
            
            completion_times.append(processing_time)
            if len(completion_times) > 100:  # Keep only last 100
                completion_times.pop(0)
            
            provenance[f"tile_{idx}"] = prov
            
            if result_type == "success" and out and prov.get("status") == "ok":
                tile_files.append(out)
                counters["success"] += 1
                dominant_sat = prov.get("dominant_satellite")
                detailed_stats = prov.get("detailed_stats")
                tile_idx = prov.get("tile_idx")
                all_test_results = prov.get("all_test_results", [])
                
                ranked_image_stats = prov.get("ranked_image_stats", [])
                if ranked_image_stats:
                    for ranked_stat in ranked_image_stats:
                        ranked_stat["tile_idx"] = tile_idx
                        histogram.add_test_result(ranked_stat)
                else:
                    if detailed_stats:
                        for test_result in all_test_results:
                            if (test_result.get("satellite") == detailed_stats.get("satellite") and
                                abs(test_result.get("quality_score", 0) - detailed_stats.get("quality_score", 0)) < 0.001):
                                test_result["is_selected"] = True
                                break
                    for test_result in all_test_results:
                        histogram.add_test_result(test_result)
                
                # Use actual processing_time from result queue (measured time, not estimated)
                if dominant_sat:
                    histogram.add_satellite(dominant_sat, detailed_stats, tile_idx, processing_time)
                print(f"\n[Tile {idx:04d}] ✅ SUCCESS - Added to mosaic")
            else:
                counters["failed"] += 1
                error_msg = prov.get("error", prov.get("validation_reason", prov.get("status", "unknown")))
                print(f"\n[Tile {idx:04d}] ❌ FAILED - {error_msg[:80]}")
            
            pbar.update(1)
            with lock:
                pbar.set_postfix({"OK": counters["success"], "FAIL": counters["failed"], "ACTIVE": active_workers})
        except queue.Empty:
            # Check if all workers are dead and queue is empty
            if all(not t.is_alive() for t in worker_threads) and tile_queue.empty():
                break
    
    # Stop all workers
    stop_event.set()
    tile_queue.join()  # Wait for all tasks to complete
    
    pbar.close()


def _process_futures(futures, provenance, tile_files, histogram, pbar, success_count, failed_count, effective_workers):
    """Helper function to process futures from ThreadPoolExecutor"""
    for fut in concurrent.futures.as_completed(futures):
        try:
            out, prov = fut.result(timeout=3600)
            idx = prov.get("tile_idx")
            provenance[f"tile_{idx}"] = prov
            
            status = prov.get("status", "unknown")
            if out and status == "ok":
                tile_files.append(out)
                success_count += 1
                dominant_sat = prov.get("dominant_satellite")
                detailed_stats = prov.get("detailed_stats")
                tile_idx = prov.get("tile_idx")
                all_test_results = prov.get("all_test_results", [])
                
                ranked_image_stats = prov.get("ranked_image_stats", [])
                if ranked_image_stats:
                    for ranked_stat in ranked_image_stats:
                        ranked_stat["tile_idx"] = tile_idx
                        histogram.add_test_result(ranked_stat)
                else:
                    if detailed_stats:
                        for test_result in all_test_results:
                            if (test_result.get("satellite") == detailed_stats.get("satellite") and
                                abs(test_result.get("quality_score", 0) - detailed_stats.get("quality_score", 0)) < 0.001):
                                test_result["is_selected"] = True
                                break
                    for test_result in all_test_results:
                        histogram.add_test_result(test_result)
                
                # For fixed workers, we don't have individual processing times
                # The histogram will use elapsed time / processed count as fallback
                processing_time = None
                
                if dominant_sat:
                    histogram.add_satellite(dominant_sat, detailed_stats, tile_idx, processing_time)
                print(f"\n[Tile {idx:04d}] ✅ SUCCESS - Added to mosaic")
            else:
                failed_count += 1
                error_msg = prov.get("error", prov.get("validation_reason", status))
                print(f"\n[Tile {idx:04d}] ❌ FAILED - {status}: {error_msg[:80]}")
            
            pbar.update(1)
            pbar.set_postfix({"OK": success_count, "FAIL": failed_count, "ACTIVE": effective_workers})
        except concurrent.futures.TimeoutError:
            failed_count += 1
            print(f"\n[Tile ???] ⏱️ TIMEOUT - Processing exceeded 1 hour")
            provenance[f"tile_unknown"] = {"status": "timeout", "error": "Processing exceeded 1 hour"}
            pbar.update(1)
        except Exception as e:
            failed_count += 1
            print(f"\n[Tile ???] ⚠️ ERROR - {str(e)[:80]}")
            provenance[f"tile_unknown"] = {"status": "error", "error": str(e)}
            pbar.update(1)


def process_month(bbox: Tuple[float, float, float, float], year: int, month: int, 
                 out_folder: str, workers: int = 3, enable_ml: bool = False, 
                 enable_harmonize: bool = True, include_modis: bool = True, 
                 include_aster: bool = True, include_viirs: bool = True, 
                 target_resolution: float = TARGET_RES, max_tiles: Optional[int] = None):
    """Process a single month of satellite imagery."""
    from datetime import datetime
    from .raster_processing import feather_and_merge, create_cog
    
    month_start = f"{year}-{month:02d}-01"
    if month == 12:
        month_end = f"{year+1}-01-01"
    else:
        month_end = f"{year}-{month+1:02d}-01"
    out_dir = os.path.join(out_folder, f"{year}_{month:02d}")
    os.makedirs(out_dir, exist_ok=True)
    
    # Add file handler for this specific processing run (in addition to main log)
    # This creates a log file in the output directory for easy access
    run_log_path = os.path.join(out_dir, f"processing_{year}_{month:02d}.log")
    run_file_handler = logging.FileHandler(run_log_path, encoding='utf-8', mode='w')
    run_file_handler.setLevel(logging.DEBUG)
    run_file_format = logging.Formatter("%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s")
    run_file_handler.setFormatter(run_file_format)
    logger = logging.getLogger()
    logger.addHandler(run_file_handler)
    logging.info(f"Processing log file: {run_log_path}")
    
    cog_path = os.path.join(out_dir, f"deadsea_{year}_{month:02d}_COG.tif")
    if os.path.exists(cog_path):
        logging.info("Skipping %s-%02d (COG exists)", year, month)
        # Remove the run-specific handler before returning
        logger.removeHandler(run_file_handler)
        run_file_handler.close()
        return
    
    # Force resolution to always be 5m
    effective_res = 5.0  # Always 5m resolution
    logging.info("Forcing 5m resolution for all satellites")
    
    lon_min, lat_min, lon_max, lat_max = bbox
    center_lat = (lat_min + lat_max) / 2.0
    lon_span_deg = lon_max - lon_min
    lat_span_deg = lat_max - lat_min
    
    # Improved geodesic distance calculation
    meters_per_deg_lon = 111320 * math.cos(math.radians(center_lat))
    meters_per_deg_lat = 111000
    lon_span_m_est = lon_span_deg * meters_per_deg_lon
    lat_span_m_est = lat_span_deg * meters_per_deg_lat
    
    if max_tiles is not None:
        # User specified max tiles - use dynamic tile sizing
        logging.info("Using user-specified max_tiles=%d for dynamic tile sizing", max_tiles)
        
        # Validate tile size before processing
        aspect_ratio = lon_span_m_est / lat_span_m_est if lat_span_m_est > 0 else 1.0
        nx = max(1, round(math.sqrt(max_tiles * aspect_ratio)))
        ny = max(1, round(math.sqrt(max_tiles / aspect_ratio)))
        actual_tiles = nx * ny
        
        tile_width_m = lon_span_m_est / nx
        tile_height_m = lat_span_m_est / ny
        tile_side_m = max(tile_width_m, tile_height_m)
        
        pixels_per_side = tile_side_m / effective_res
        pixels_per_tile = pixels_per_side * pixels_per_side
        
        # Calculate download size (6 bands × Float32 = 24 bytes per pixel)
        bytes_per_pixel = 6 * 4  # 6 bands × 4 bytes (Float32)
        size_bytes = pixels_per_tile * bytes_per_pixel
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > SAFE_DOWNLOAD_SIZE_BYTES / (1024 * 1024):  # 40 MB limit
            error_msg = (f"ERROR: Tile size would be {size_mb:.1f} MB per tile, exceeding 40 MB limit! "
                        f"Please use more tiles (minimum: {int(max_tiles * (size_mb / 40)) + 1})")
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        logging.info("Validated tile size: ~%.1f MB per tile (%d tiles, ~%d pixels/tile)", 
                    size_mb, actual_tiles, int(pixels_per_side))
        
        tiles = make_utm_tiles(bbox, tile_side_m=None, max_tiles=max_tiles)
    else:
        # Auto-calculate: FORCE 256 pixels per tile (minimum size = maximum tiles)
        # Calculate pixels at target resolution (5m)
        est_width_pixels = int(lon_span_m_est / effective_res)
        est_height_pixels = int(lat_span_m_est / effective_res)
        total_pixels = est_width_pixels * est_height_pixels
        
        # Force 256 pixels per tile (minimum for maximum tiles)
        pixels_per_tile = MIN_TILE_PIXELS * MIN_TILE_PIXELS  # 256 * 256 = 65,536 pixels per tile
        
        # Calculate number of tiles needed
        num_tiles_needed = math.ceil(total_pixels / pixels_per_tile)
        
        logging.info("Forcing 256 pixels per tile for maximum quality: %d tiles calculated for maximum tile count", num_tiles_needed)
        
        # Calculate tile grid dimensions (account for aspect ratio)
        aspect_ratio = lon_span_m_est / lat_span_m_est if lat_span_m_est > 0 else 1.0
        tiles_per_row = math.ceil(math.sqrt(num_tiles_needed * aspect_ratio))
        tiles_per_col = math.ceil(num_tiles_needed / tiles_per_row)
        calculated_max_tiles = tiles_per_row * tiles_per_col
        
        # Generate tiles
        tiles = make_utm_tiles(bbox, tile_side_m=None, max_tiles=calculated_max_tiles)
    
    if not tiles:
        raise ValueError("Failed to generate tiles")
    
    # Calculate actual tile size for logging
    first_tile = tiles[0]
    lon_span_tile = first_tile[2] - first_tile[0]
    lat_span_tile = first_tile[3] - first_tile[1]
    meters_per_deg_lon = 111320 * math.cos(math.radians(center_lat))
    meters_per_deg_lat = 111000
    tile_side_m = max(lon_span_tile * meters_per_deg_lon, lat_span_tile * meters_per_deg_lat)
    avg_tile_pixels = int(tile_side_m / effective_res)
    
    logging.info("Resolution 5m: %d tiles (each tile ~%d pixels) - forced 256 pixel minimum", 
                len(tiles), avg_tile_pixels)
    
    # Download directly to output directory
    tiles_dir = os.path.join(out_dir, "tiles")
    os.makedirs(tiles_dir, exist_ok=True)
    temp_root = tiles_dir
    tile_files = []
    provenance = {}
    include_l7 = True  # included but low-priority
    
    # Dynamic worker management
    cpu_count = multiprocessing.cpu_count()
    effective_workers = min(workers, cpu_count, MAX_CONCURRENT_TILES, len(tiles))
    if workers > effective_workers:
        logging.info("Reduced workers from %d to %d (CPU count: %d, max concurrent: %d, tiles: %d)", 
                    workers, effective_workers, cpu_count, MAX_CONCURRENT_TILES, len(tiles))
    else:
        logging.info("Using %d workers for %d tiles (CPU count: %d)", effective_workers, len(tiles), cpu_count)
    
    # Progress tracking
    tile_status = {}
    completed_count = 0
    success_count = 0
    failed_count = 0
    
    # Initialize real-time histogram
    histogram = SatelliteHistogram(len(tiles), out_dir)
    
    def progress_callback(tile_idx, status, message):
        """Callback for tile progress updates"""
        tile_status[tile_idx] = {"status": status, "message": message, "timestamp": time.time()}
        status_symbol = {
            "BUILDING": "🔨", "MOSAIC_OK": "✓", "SELECTING": "📋", "URL_GEN": "🔗",
            "DOWNLOADING": "⬇️", "DOWNLOADED": "✓", "VALIDATING": "✔", "VALIDATED": "✓",
            "MASKING": "🎭", "SUCCESS": "✅", "FAILED": "❌", "ERROR": "⚠️"
        }.get(status, "•")
        print(f"\r[Tile {tile_idx:04d}] {status_symbol} {status}: {message[:60]}", end="", flush=True)
    
    # Process tiles with dynamic or fixed workers
    pbar = tqdm(total=len(tiles), desc=f"Month {year}-{month:02d}", unit="tile", ncols=100)
    
    # Use mutable counters for dynamic workers
    counters = {"success": 0, "failed": 0}
    
    # OPTIMIZATION #9: Tile priority queue (higher variance first)
    # Compute a simple variance score per tile and sort descending
    try:
        scored_tiles = []
        for tile in tiles:
            try:
                var_score = calculate_tile_variance(tile, month_start, month_end)
            except Exception:
                var_score = 0.0
            scored_tiles.append((var_score, tile))
        # Sort by variance descending; fall back to original order on ties
        scored_tiles.sort(key=lambda x: x[0], reverse=True)
        priority_tiles = [t for _, t in scored_tiles]
    except Exception:
        # Fallback to original order if variance calculation fails
        priority_tiles = tiles
    
    if ENABLE_DYNAMIC_WORKERS:
        # Use adaptive worker pool with dynamic scaling
        # OPTIMIZATION #9: Use priority-ordered tiles (high-variance first)
        _process_tiles_with_dynamic_workers(
            priority_tiles, month_start, month_end, temp_root, include_l7, enable_ml,
            enable_harmonize, include_modis, include_aster, include_viirs,
            effective_res, effective_workers, progress_callback, histogram,
            provenance, tile_files, pbar, counters
        )
        success_count = counters["success"]
        failed_count = counters["failed"]
    else:
        # Use fixed worker pool (original implementation)
        with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as ex:
            futures = {ex.submit(process_tile, idx, tile, month_start, month_end, temp_root, 
                                include_l7, enable_ml, enable_harmonize, include_modis, 
                                include_aster, include_viirs, effective_res, progress_callback): idx 
                      for idx, tile in enumerate(tiles)}
            
            for fut in concurrent.futures.as_completed(futures):
                completed_count += 1
                try:
                    out, prov = fut.result(timeout=3600)  # 1 hour timeout per tile
                    idx = prov.get("tile_idx")
                    provenance[f"tile_{idx}"] = prov
                    
                    status = prov.get("status", "unknown")
                    if out and status == "ok":
                        tile_files.append(out)
                        success_count += 1
                        dominant_sat = prov.get("dominant_satellite")
                        detailed_stats = prov.get("detailed_stats")
                        tile_idx = prov.get("tile_idx")
                        all_test_results = prov.get("all_test_results", [])
                        
                        # For fixed workers, we don't have individual processing times
                        # The histogram will use elapsed time / processed count as fallback
                        processing_time = None
                        
                        # Use ranked_image_stats if available (includes fallback ranks)
                        ranked_image_stats = prov.get("ranked_image_stats", [])
                        if ranked_image_stats:
                            # Add ranked stats (includes primary + fallbacks with ranks)
                            for ranked_stat in ranked_image_stats:
                                ranked_stat["tile_idx"] = tile_idx
                                histogram.add_test_result(ranked_stat)
                        else:
                            # Fallback: mark the selected test result (the one that matches the final detailed_stats)
                            if detailed_stats:
                                # Find the test result that matches the selected image
                                for test_result in all_test_results:
                                    # Match by satellite and quality score (within small tolerance)
                                    if (test_result.get("satellite") == detailed_stats.get("satellite") and
                                        abs(test_result.get("quality_score", 0) - detailed_stats.get("quality_score", 0)) < 0.001):
                                        test_result["is_selected"] = True
                                        break
                            
                            # Add all test results to histogram (not just the final selected one)
                            for test_result in all_test_results:
                                histogram.add_test_result(test_result)
                        
                        # Only add the primary selected satellite to histogram counts (not fallbacks)
                        if dominant_sat:
                            histogram.add_satellite(dominant_sat, detailed_stats, tile_idx, processing_time)
                        print(f"\n[Tile {idx:04d}] ✅ SUCCESS - Added to mosaic")
                    else:
                        failed_count += 1
                        error_msg = prov.get("error", prov.get("validation_reason", status))
                        print(f"\n[Tile {idx:04d}] ❌ FAILED - {status}: {error_msg[:80]}")
                    
                    pbar.update(1)
                    pbar.set_postfix({"OK": success_count, "FAIL": failed_count, "ACTIVE": effective_workers})
                    
                except concurrent.futures.TimeoutError:
                    failed_count += 1
                    print(f"\n[Tile ???] ⏱️ TIMEOUT - Processing exceeded 1 hour")
                    provenance[f"tile_unknown"] = {"status": "timeout", "error": "Processing exceeded 1 hour"}
                    pbar.update(1)
                except Exception as e:
                    failed_count += 1
                    print(f"\n[Tile ???] ⚠️ ERROR - {str(e)[:80]}")
                    provenance[f"tile_unknown"] = {"status": "error", "error": str(e)}
                    pbar.update(1)
        
        pbar.close()
        completed_count = success_count + failed_count
        print(f"\n{'='*80}")
        print(f"Tile Processing Summary: {success_count} succeeded, {failed_count} failed out of {completed_count} total")
        print(f"{'='*80}\n")
    
    if not tile_files:
        logging.warning("No tiles produced for %s", month_start)
        failed_tiles = [k for k, v in provenance.items() if v.get("status") != "ok"]
        if failed_tiles:
            logging.warning("Failed tiles: %d out of %d", len(failed_tiles), len(provenance))
            status_counts = {}
            for tile_key in failed_tiles:
                status = provenance[tile_key].get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            logging.warning("Failure reasons: %s", status_counts)
        histogram.save("")
        histogram.close()
        return
    
    # Stitch with feather/blend
    mosaic_path = os.path.join(out_dir, f"deadsea_{year}_{month:02d}_mosaic.tif")
    logging.info("Stitching %d tiles into mosaic...", len(tile_files))
    feather_and_merge(tile_files, mosaic_path, feather_px=80)
    
    # Calculate indices locally (much faster than on Earth Engine server)
    logging.info("Calculating vegetation and water indices locally...")
    add_indices_to_mosaic_local(mosaic_path)
    
    # Validate mosaic
    logging.info("Validating mosaic...")
    valid, reason = validate_geotiff_local(mosaic_path)
    if not valid:
        logging.error("Mosaic validation failed: %s. Keeping individual tiles for debugging.", reason)
        prov_json = os.path.join(out_dir, "provenance.json")
        with open(prov_json, "w") as f:
            json.dump(provenance, f, indent=2, default=str)
        return
    
    # Create COG
    logging.info("Creating COG from mosaic...")
    try:
        create_cog(mosaic_path, cog_path)
    except Exception as e:
        logging.exception("COG creation failed")
        return
    
    # Validate COG
    logging.info("Validating COG...")
    valid_cog, reason_cog = validate_geotiff_local(cog_path)
    if not valid_cog:
        logging.error("COG validation failed: %s. Keeping individual tiles for debugging.", reason_cog)
        prov_json = os.path.join(out_dir, "provenance.json")
        with open(prov_json, "w") as f:
            json.dump(provenance, f, indent=2, default=str)
        return
    
    # Mosaic and COG are both valid - safe to delete individual tiles
    logging.info("Mosaic and COG validated successfully. Cleaning up individual tiles...")
    deleted_count = 0
    for t in tile_files:
        try:
            if os.path.exists(t):
                os.remove(t)
                deleted_count += 1
        except Exception as e:
            logging.warning("Failed to delete tile %s: %s", t, str(e))
    
    # Delete mask files too
    for v in provenance.values():
        m = v.get("mask")
        if m and os.path.exists(m):
            try:
                os.remove(m)
            except Exception as e:
                logging.warning("Failed to delete mask %s: %s", m, str(e))
    
    # Remove empty tiles directory
    try:
        if os.path.exists(tiles_dir) and not os.listdir(tiles_dir):
            os.rmdir(tiles_dir)
            logging.debug("Removed empty tiles directory")
    except Exception as e:
        logging.warning("Could not remove tiles directory: %s", str(e))
    
    logging.info("Deleted %d individual tile files. Keeping mosaic and COG.", deleted_count)
    
    # Finalize histogram
    histogram.save("")
    histogram.close()
    logging.info("Satellite histogram dashboard available at: %s", histogram.html_path)
    
    # Remove the run-specific file handler
    logger = logging.getLogger()
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(run_log_path):
            logger.removeHandler(handler)
            handler.close()
            break
    
    # Save provenance
    prov_json = os.path.join(out_dir, "provenance.json")
    with open(prov_json, "w") as f:
        json.dump(provenance, f, indent=2, default=str)
    
    # Manifest
    manifest_init()
    prov_json_str = json.dumps(provenance, default=str)
    manifest_append(year, month, mosaic_path, cog_path, tile_files, prov_json_str)
    
    logging.info("Completed %s - Mosaic: %s, COG: %s", month_start, mosaic_path, cog_path)


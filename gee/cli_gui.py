"""
CLI and GUI entry points for the GEE downloader.
"""
import sys
import multiprocessing
from datetime import datetime

from .config import DEFAULT_BBOX, DEFAULT_START, DEFAULT_END, OUTDIR_DEFAULT, TARGET_RES, DEFAULT_WORKERS, ENABLE_DYNAMIC_WORKERS
from .utils import month_ranges
from .processing import process_month

# Try to import tkinter for GUI
try:
    import tkinter as tk
    from tkinter import ttk, filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


def gui_and_run():
    """Run GUI or CLI interface and process months."""
    if TKINTER_AVAILABLE:
        print("Creating GUI window (tkinter)...")
        root = tk.Tk()
        root.title("Dead Sea — All Upgrades Downloader")
        root.geometry("650x700")
        
        # Variables
        bbox_var = tk.StringVar(value=",".join(map(str, DEFAULT_BBOX)))
        start_var = tk.StringVar(value=DEFAULT_START)
        end_var = tk.StringVar(value=DEFAULT_END)
        out_var = tk.StringVar(value=OUTDIR_DEFAULT)
        ml_var = tk.BooleanVar(value=False)
        harm_var = tk.BooleanVar(value=True)
        modis_var = tk.BooleanVar(value=True)
        aster_var = tk.BooleanVar(value=True)
        viirs_var = tk.BooleanVar(value=True)
        workers_var = tk.StringVar(value=str(DEFAULT_WORKERS))
        max_tiles_var = tk.StringVar(value="")  # Empty = auto-calculate
        dynamic_workers_var = tk.BooleanVar(value=True)  # Enable dynamic workers by default
        submit_clicked = [False]
        
        def browse_folder():
            folder = filedialog.askdirectory(initialdir=out_var.get())
            if folder:
                out_var.set(folder)
        
        def submit():
            # Validate tile count before submitting
            if not validate_tile_count():
                # Show error dialog
                import tkinter.messagebox as messagebox
                messagebox.showerror("Validation Error", 
                    "Tile count would result in tiles exceeding 40 MB limit!\n"
                    "Please increase the tile count or leave empty for auto-calculation.")
                return
            
            submit_clicked[0] = True
            root.quit()
            root.destroy()
        
        def cancel():
            root.quit()
            root.destroy()
        
        # Layout
        tk.Label(root, text="Dead Sea — All Upgrades Downloader", font=("Arial", 14, "bold")).pack(pady=10)
        
        frame = ttk.Frame(root, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="BBox lon_min,lat_min,lon_max,lat_max:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=bbox_var, width=40).grid(row=0, column=1, pady=5)
        
        ttk.Label(frame, text="Start date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=start_var, width=40).grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="End date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=end_var, width=40).grid(row=2, column=1, pady=5)
        
        ttk.Label(frame, text="Output folder:").grid(row=3, column=0, sticky=tk.W, pady=5)
        folder_frame = ttk.Frame(frame)
        folder_frame.grid(row=3, column=1, sticky=tk.W+tk.E, pady=5)
        ttk.Entry(folder_frame, textvariable=out_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(folder_frame, text="Browse", command=browse_folder).pack(side=tk.LEFT, padx=5)
        
        ttk.Checkbutton(frame, text="Enable ML cloud cleanup (optional)", variable=ml_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Enable harmonization (S2 <-> LS)", variable=harm_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Checkbutton(frame, text="Include MODIS", variable=modis_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Include ASTER", variable=aster_var).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Include VIIRS", variable=viirs_var).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Enable dynamic worker scaling (auto-adjust based on system performance)", 
                       variable=dynamic_workers_var).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="Resolution (meters, forced to 5m):").grid(row=10, column=0, sticky=tk.W, pady=5)
        resolution_var = tk.StringVar(value="5.0")
        ttk.Entry(frame, textvariable=resolution_var, width=40).grid(row=10, column=1, pady=5)
        ttk.Label(frame, text="Workers:").grid(row=11, column=0, sticky=tk.W, pady=5)
        workers_entry = ttk.Entry(frame, textvariable=workers_var, width=40)
        workers_entry.grid(row=11, column=1, pady=5)
        
        ttk.Label(frame, text="Max tiles (empty = auto):").grid(row=12, column=0, sticky=tk.W, pady=5)
        tile_entry = ttk.Entry(frame, textvariable=max_tiles_var, width=40)
        tile_entry.grid(row=12, column=1, pady=5)
        
        # Validation label for tile size warning
        tile_warning_label = ttk.Label(frame, text="", font=("Arial", 8), foreground="red")
        tile_warning_label.grid(row=13, column=1, sticky=tk.W, pady=2)
        
        def validate_tile_count(*args):
            """Validate tile count and calculate expected tile size."""
            try:
                tile_count_str = max_tiles_var.get().strip()
                if not tile_count_str:
                    tile_warning_label.config(text="", foreground="green")
                    return True
                
                tile_count = int(tile_count_str)
                if tile_count < 1:
                    tile_warning_label.config(text="Error: Tile count must be at least 1", foreground="red")
                    return False
                
                # Calculate expected tile size
                try:
                    bbox_str = bbox_var.get()
                    bbox = tuple(map(float, bbox_str.split(",")))
                    lon_min, lat_min, lon_max, lat_max = bbox
                    center_lat = (lat_min + lat_max) / 2.0
                    
                    import math
                    meters_per_deg_lon = 111320 * math.cos(math.radians(center_lat))
                    meters_per_deg_lat = 111000
                    lon_span_m = (lon_max - lon_min) * meters_per_deg_lon
                    lat_span_m = (lat_max - lat_min) * meters_per_deg_lat
                    
                    # Calculate aspect ratio
                    aspect = lon_span_m / lat_span_m if lat_span_m > 0 else 1.0
                    nx = max(1, round(math.sqrt(tile_count * aspect)))
                    ny = max(1, round(math.sqrt(tile_count / aspect)))
                    actual_tiles = nx * ny
                    
                    # Calculate tile dimensions
                    tile_width_m = lon_span_m / nx
                    tile_height_m = lat_span_m / ny
                    tile_side_m = max(tile_width_m, tile_height_m)
                    
                    # Calculate pixels per tile at 5m resolution
                    pixels_per_side = tile_side_m / TARGET_RES
                    pixels_per_tile = pixels_per_side * pixels_per_side
                    
                    # Calculate download size (6 bands × Float32 = 24 bytes per pixel)
                    bytes_per_pixel = 6 * 4  # 6 bands × 4 bytes (Float32)
                    size_bytes = pixels_per_tile * bytes_per_pixel
                    size_mb = size_bytes / (1024 * 1024)
                    
                    # Check against 40 MB limit
                    if size_mb > 40:
                        tile_warning_label.config(
                            text=f"ERROR: {size_mb:.1f} MB per tile exceeds 40 MB limit! Use more tiles.",
                            foreground="red"
                        )
                        return False
                    else:
                        # Estimate processing time
                        # Factors: Earth Engine processing (~3-5 sec), download (~size/10 Mbps), local processing (~1-2 sec)
                        # Conservative estimate: 5 seconds base + download time
                        try:
                            num_workers = int(workers_var.get()) if workers_var.get().strip() else 8
                            num_workers = max(1, min(num_workers, 8))  # Cap at 8
                        except (ValueError, AttributeError):
                            num_workers = 8
                        
                        # Estimate time per tile (seconds)
                        # Earth Engine processing: ~3-5 seconds (depends on complexity, resolution)
                        # Download time: size_mb / download_speed_mbps (assume 10 Mbps = 1.25 MB/s)
                        # Local processing: ~1-2 seconds
                        ee_processing_time = 4.0  # Average Earth Engine processing time
                        download_speed_mbps = 10.0  # Conservative estimate: 10 Mbps
                        download_time = size_mb / (download_speed_mbps / 8)  # Convert Mbps to MB/s
                        local_processing_time = 1.5  # Local validation, masking, etc.
                        time_per_tile = ee_processing_time + download_time + local_processing_time
                        
                        # Total time with parallel workers
                        total_tiles = actual_tiles
                        tiles_per_worker = total_tiles / num_workers
                        estimated_total_seconds = tiles_per_worker * time_per_tile
                        
                        # Format time estimate
                        if estimated_total_seconds < 60:
                            time_str = f"{estimated_total_seconds:.0f} sec"
                        elif estimated_total_seconds < 3600:
                            minutes = estimated_total_seconds / 60
                            time_str = f"{minutes:.1f} min"
                        else:
                            hours = estimated_total_seconds / 3600
                            time_str = f"{hours:.1f} hours"
                        
                        tile_warning_label.config(
                            text=f"OK: ~{size_mb:.1f} MB/tile, {actual_tiles} tiles, ~{int(pixels_per_side)} px/tile | Est. time: {time_str}",
                            foreground="green"
                        )
                        return True
                except (ValueError, ZeroDivisionError) as e:
                    tile_warning_label.config(text="Error: Invalid bbox or calculation", foreground="red")
                    return False
                    
            except ValueError:
                tile_warning_label.config(text="Error: Tile count must be a number", foreground="red")
                return False
        
        # Bind validation to tile count, bbox, and workers changes
        max_tiles_var.trace('w', validate_tile_count)
        bbox_var.trace('w', validate_tile_count)
        workers_var.trace('w', validate_tile_count)
        
        ttk.Label(frame, text="(All satellites forced to 5m resolution)", font=("Arial", 8)).grid(row=14, column=1, sticky=tk.W, pady=2)
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=15, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Submit", command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=5)
        
        print("Opening GUI window...", flush=True)
        root.mainloop()
        
        if not submit_clicked[0]:
            print("Cancelled", flush=True)
            return
        
        bbox = tuple(map(float, bbox_var.get().split(",")))
        start = start_var.get()
        end = end_var.get()
        out = out_var.get()
        enable_ml = ml_var.get()
        enable_harmonize = harm_var.get()
        include_modis = modis_var.get()
        include_aster = aster_var.get()
        include_viirs = viirs_var.get()
        try:
            workers = int(workers_var.get())
            if workers < 1:
                workers = DEFAULT_WORKERS
        except (ValueError, AttributeError):
            workers = DEFAULT_WORKERS
        resolution_str = resolution_var.get().strip()
        target_resolution = float(resolution_str) if resolution_str else TARGET_RES
        
        # Get max tiles (empty = None for auto-calculation)
        max_tiles_str = max_tiles_var.get().strip()
        max_tiles = None
        if max_tiles_str:
            try:
                max_tiles = int(max_tiles_str)
                if max_tiles < 1:
                    max_tiles = None
            except ValueError:
                max_tiles = None
        
        # Get dynamic workers setting
        enable_dynamic_workers = dynamic_workers_var.get()
    else:
        # Fallback to command line input
        print("No GUI library available. Using command line input.")
        print("Enter parameters:")
        bbox_str = input(f"BBox (lon_min,lat_min,lon_max,lat_max) [{','.join(map(str, DEFAULT_BBOX))}]: ").strip()
        bbox = tuple(map(float, (bbox_str or ",".join(map(str, DEFAULT_BBOX))).split(",")))
        start = input(f"Start date (YYYY-MM-DD) [{DEFAULT_START}]: ").strip() or DEFAULT_START
        end = input(f"End date (YYYY-MM-DD) [{DEFAULT_END}]: ").strip() or DEFAULT_END
        out = input(f"Output folder [{OUTDIR_DEFAULT}]: ").strip() or OUTDIR_DEFAULT
        ml_str = input("Enable ML cloud cleanup? (y/n) [n]: ").strip().lower()
        enable_ml = ml_str == 'y'
        harm_str = input("Enable harmonization? (y/n) [y]: ").strip().lower()
        enable_harmonize = harm_str != 'n'
        workers_str = input(f"Workers (default {DEFAULT_WORKERS}, CPU count: {multiprocessing.cpu_count()}): ").strip()
        try:
            workers = int(workers_str) if workers_str else DEFAULT_WORKERS
            if workers < 1:
                workers = DEFAULT_WORKERS
        except ValueError:
            workers = DEFAULT_WORKERS
        modis_str = input("Include MODIS? (y/n) [y]: ").strip().lower()
        include_modis = modis_str != 'n'
        aster_str = input("Include ASTER? (y/n) [y]: ").strip().lower()
        include_aster = aster_str != 'n'
        viirs_str = input("Include VIIRS? (y/n) [y]: ").strip().lower()
        include_viirs = viirs_str != 'n'
        resolution_str = input("Resolution in meters (default 5.0, forced to 5m): ").strip()
        target_resolution = float(resolution_str) if resolution_str else TARGET_RES
        dynamic_workers_str = input(f"Enable dynamic worker scaling? (y/n) [{'y' if ENABLE_DYNAMIC_WORKERS else 'n'}]: ").strip().lower()
        enable_dynamic_workers = dynamic_workers_str != 'n' if dynamic_workers_str else ENABLE_DYNAMIC_WORKERS
        max_tiles_str = input("Max tiles (empty = auto): ").strip()
        max_tiles = None
        if max_tiles_str:
            try:
                max_tiles = int(max_tiles_str)
                if max_tiles < 1:
                    max_tiles = None
                else:
                    # Validate tile size for CLI
                    try:
                        bbox_tuple = tuple(map(float, bbox_str.split(",")))
                        lon_min, lat_min, lon_max, lat_max = bbox_tuple
                        center_lat = (lat_min + lat_max) / 2.0
                        import math
                        meters_per_deg_lon = 111320 * math.cos(math.radians(center_lat))
                        meters_per_deg_lat = 111000
                        lon_span_m = (lon_max - lon_min) * meters_per_deg_lon
                        lat_span_m = (lat_max - lat_min) * meters_per_deg_lat
                        aspect = lon_span_m / lat_span_m if lat_span_m > 0 else 1.0
                        nx = max(1, round(math.sqrt(max_tiles * aspect)))
                        ny = max(1, round(math.sqrt(max_tiles / aspect)))
                        tile_width_m = lon_span_m / nx
                        tile_height_m = lat_span_m / ny
                        tile_side_m = max(tile_width_m, tile_height_m)
                        pixels_per_side = tile_side_m / TARGET_RES
                        pixels_per_tile = pixels_per_side * pixels_per_side
                        bytes_per_pixel = 6 * 4
                        size_bytes = pixels_per_tile * bytes_per_pixel
                        size_mb = size_bytes / (1024 * 1024)
                        if size_mb > 40:
                            print(f"ERROR: Tile size would be {size_mb:.1f} MB per tile, exceeding 40 MB limit!")
                            print(f"Please use more tiles (minimum: {int(max_tiles * (size_mb / 40)) + 1})")
                            max_tiles = None
                        else:
                            # Estimate processing time
                            try:
                                num_workers = int(workers_str) if workers_str else DEFAULT_WORKERS
                                num_workers = max(1, min(num_workers, 8))
                            except ValueError:
                                num_workers = DEFAULT_WORKERS
                            
                            # Time estimation (same as GUI)
                            ee_processing_time = 4.0
                            download_speed_mbps = 10.0
                            download_time = size_mb / (download_speed_mbps / 8)
                            local_processing_time = 1.5
                            time_per_tile = ee_processing_time + download_time + local_processing_time
                            
                            total_tiles = nx * ny
                            tiles_per_worker = total_tiles / num_workers
                            estimated_total_seconds = tiles_per_worker * time_per_tile
                            
                            if estimated_total_seconds < 60:
                                time_str = f"{estimated_total_seconds:.0f} sec"
                            elif estimated_total_seconds < 3600:
                                time_str = f"{estimated_total_seconds / 60:.1f} min"
                            else:
                                time_str = f"{estimated_total_seconds / 3600:.1f} hours"
                            
                            print(f"OK: ~{size_mb:.1f} MB per tile ({nx * ny} tiles, ~{int(pixels_per_side)} pixels/tile)")
                            print(f"Estimated processing time: {time_str} (with {num_workers} workers)")
                    except (ValueError, ZeroDivisionError):
                        print("Warning: Could not validate tile size, proceeding anyway...")
            except ValueError:
                max_tiles = None
    
    # Get dynamic workers setting (from GUI/CLI if available, otherwise use config default)
    try:
        enable_dynamic_workers
    except NameError:
        enable_dynamic_workers = ENABLE_DYNAMIC_WORKERS
    
    # Temporarily override config if user specified
    from . import config
    original_dynamic_workers = config.ENABLE_DYNAMIC_WORKERS
    config.ENABLE_DYNAMIC_WORKERS = enable_dynamic_workers
    
    months = list(month_ranges(start, end))
    for ms, me in months:
        dt = datetime.fromisoformat(ms)
        process_month(bbox, dt.year, dt.month, out, workers, enable_ml, enable_harmonize, 
                     include_modis, include_aster, include_viirs, target_resolution=target_resolution, max_tiles=max_tiles)
    
    # Restore original config value
    config.ENABLE_DYNAMIC_WORKERS = original_dynamic_workers


"""
CLI and GUI entry points for the GEE downloader.
"""
import sys
import multiprocessing
from datetime import datetime

from .config import DEFAULT_BBOX, DEFAULT_START, DEFAULT_END, OUTDIR_DEFAULT, TARGET_RES, DEFAULT_WORKERS
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
        root.geometry("650x650")
        
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
        submit_clicked = [False]
        
        def browse_folder():
            folder = filedialog.askdirectory(initialdir=out_var.get())
            if folder:
                out_var.set(folder)
        
        def submit():
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
        
        ttk.Label(frame, text="Resolution (meters, forced to 5m):").grid(row=9, column=0, sticky=tk.W, pady=5)
        resolution_var = tk.StringVar(value="5.0")
        ttk.Entry(frame, textvariable=resolution_var, width=40).grid(row=9, column=1, pady=5)
        ttk.Label(frame, text="Workers:").grid(row=10, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=workers_var, width=40).grid(row=10, column=1, pady=5)
        
        ttk.Label(frame, text="(All satellites forced to 5m resolution)", font=("Arial", 8)).grid(row=11, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="(Tiles forced to 256 pixels minimum for maximum tile count)", font=("Arial", 8), foreground="green").grid(row=12, column=1, sticky=tk.W, pady=2)
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=13, column=0, columnspan=2, pady=20)
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
    
    months = list(month_ranges(start, end))
    for ms, me in months:
        dt = datetime.fromisoformat(ms)
        process_month(bbox, dt.year, dt.month, out, workers, enable_ml, enable_harmonize, 
                     include_modis, include_aster, include_viirs, target_resolution=target_resolution)


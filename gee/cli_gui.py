"""
CLI and GUI entry points for the GEE downloader.
"""
import sys
import os
import math
import multiprocessing
import time
import logging
from datetime import datetime, timedelta

from .config import DEFAULT_BBOX, DEFAULT_START, DEFAULT_END, OUTDIR_DEFAULT, TARGET_RES, DEFAULT_WORKERS, ENABLE_DYNAMIC_WORKERS
from .utils import month_ranges
from .processing import process_month

# Try to import tkinter for GUI
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


def show_settings_dialog(parent=None):
    """Show settings dialog for Earth Engine authentication."""
    if not TKINTER_AVAILABLE:
        print("ERROR: tkinter not available. Cannot show settings dialog.")
        return False
    
    from .settings import load_settings, save_settings
    
    # Load existing settings
    settings = load_settings()
    
    # Create dialog window
    dialog = tk.Toplevel(parent) if parent else tk.Tk()
    dialog.title("Earth Engine Settings")
    dialog.geometry("600x350")
    dialog.resizable(False, False)
    
    if not parent:
        dialog.transient()
        dialog.grab_set()
    
    result = [False]  # Use list to allow modification in nested functions
    
    # Variables
    key_path_var = tk.StringVar(value=settings.get('service_account_key', ''))
    project_id_var = tk.StringVar(value=settings.get('project_id', ''))
    
    # Main frame
    main_frame = ttk.Frame(dialog, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    title_label = tk.Label(main_frame, text="Earth Engine Authentication Settings", 
                          font=("Arial", 14, "bold"))
    title_label.pack(pady=(0, 15))
    
    # Instructions
    instructions = tk.Label(main_frame, 
                           text="Configure your Earth Engine authentication.\n"
                                "You can use a service account key file (recommended) or set a project ID for user authentication.",
                           justify=tk.LEFT, wraplength=550)
    instructions.pack(pady=(0, 15))
    
    # Service account key section
    key_frame = ttk.LabelFrame(main_frame, text="Service Account Key (Recommended)", padding="10")
    key_frame.pack(fill=tk.X, pady=(0, 10))
    
    key_entry_frame = ttk.Frame(key_frame)
    key_entry_frame.pack(fill=tk.X)
    
    key_entry = ttk.Entry(key_entry_frame, textvariable=key_path_var, width=50)
    key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    
    def browse_key_file():
        try:
            filename = filedialog.askopenfilename(
                title="Select Service Account Key File",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                parent=dialog
            )
            if filename:
                key_path_var.set(filename)
        except Exception as e:
            import logging
            logging.error(f"Error browsing for service account key: {e}", exc_info=True)
            import tkinter.messagebox as messagebox
            messagebox.showerror(
                "Error",
                f"Failed to browse for service account key file:\n\n{str(e)}\n\nPlease enter the path manually."
            )
    
    browse_btn = ttk.Button(key_entry_frame, text="Browse", command=browse_key_file, width=12)
    browse_btn.pack(side=tk.LEFT)
    
    key_help = tk.Label(key_frame, 
                       text="Select your Google Cloud service account JSON key file.\n"
                            "This automatically includes your project ID.",
                       font=("Arial", 8), fg="gray", justify=tk.LEFT)
    key_help.pack(anchor=tk.W, pady=(5, 0))
    
    # Divider
    divider = ttk.Separator(main_frame, orient=tk.HORIZONTAL)
    divider.pack(fill=tk.X, pady=15)
    
    # OR label
    or_label = tk.Label(main_frame, text="OR", font=("Arial", 10, "bold"))
    or_label.pack()
    
    # Project ID section (for user authentication)
    project_frame = ttk.LabelFrame(main_frame, text="Project ID (User Authentication)", padding="10")
    project_frame.pack(fill=tk.X, pady=(10, 0))
    
    project_entry = ttk.Entry(project_frame, textvariable=project_id_var, width=50)
    project_entry.pack(fill=tk.X, pady=(0, 5))
    
    project_help = tk.Label(project_frame, 
                           text="Enter your Google Cloud project ID.\n"
                                "Required if using user authentication (browser-based login).",
                           font=("Arial", 8), fg="gray", justify=tk.LEFT)
    project_help.pack(anchor=tk.W)
    
    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=(20, 0))
    
    def save_and_close():
        key_path = key_path_var.get().strip()
        project_id = project_id_var.get().strip()
        
        # Validate key file if provided
        if key_path:
            if not os.path.exists(key_path):
                messagebox.showerror("Error", f"Service account key file not found:\n{key_path}")
                return
            
            # Try to validate it's a JSON file
            try:
                import json
                with open(key_path, 'r') as f:
                    key_data = json.load(f)
                    if 'project_id' not in key_data:
                        messagebox.showwarning("Warning", 
                            "Key file doesn't contain 'project_id' field.\n"
                            "Make sure it's a valid Google Cloud service account key file.")
            except json.JSONDecodeError:
                messagebox.showerror("Error", "Invalid JSON file. Please select a valid service account key file.")
                return
            except Exception as e:
                messagebox.showerror("Error", f"Error reading key file: {e}")
                return
        
        # Save settings
        save_settings(service_account_key=key_path if key_path else None,
                     project_id=project_id if project_id else None)
        
        result[0] = True
        dialog.destroy()
    
    def cancel():
        dialog.destroy()
    
    save_btn = ttk.Button(button_frame, text="Save", command=save_and_close, width=15)
    save_btn.pack(side=tk.LEFT, padx=5)
    
    cancel_btn = ttk.Button(button_frame, text="Cancel", command=cancel, width=15)
    cancel_btn.pack(side=tk.LEFT, padx=5)
    
    # Make dialog modal
    if parent:
        dialog.transient(parent)
        dialog.grab_set()
    
    # Center dialog
    dialog.update_idletasks()
    if parent:
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (dialog.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            # Fallback to center of screen if parent geometry not available
            dialog.eval('tk::PlaceWindow %s center' % dialog.winfo_pathname(dialog.winfo_id()))
    else:
        dialog.eval('tk::PlaceWindow %s center' % dialog.winfo_pathname(dialog.winfo_id()))
    
    # Wait for dialog to close
    if parent:
        dialog.wait_window()
    else:
        dialog.mainloop()
    
    return result[0]


def check_earth_engine_initialized():
    """Check if Earth Engine is initialized."""
    try:
        import ee
        ee.Number(1).getInfo()  # Try a simple operation
        return True
    except Exception:
        return False


def gui_and_run():
    """Run GUI or CLI interface and process months."""
    if TKINTER_AVAILABLE:
        print("Initializing GUI...", flush=True)
        logging.info("Initializing GUI...")
        
        root = tk.Tk()
        root.title("Dead Sea — All Upgrades Downloader")
        root.geometry("700x800")
        
        # Create main container with scrollbar
        main_container = ttk.Frame(root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def configure_canvas_width(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_frame, width=canvas_width)
        
        canvas.bind('<Configure>', configure_canvas_width)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Make mousewheel scroll work
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Load saved settings
        from .settings import load_settings, save_settings
        settings = load_settings()
        
        # Variables - load from settings if available, otherwise use defaults
        bbox_default = settings.get('bbox', (",".join(map(str, DEFAULT_BBOX)) if DEFAULT_BBOX else ""))
        bbox_var = tk.StringVar(value=bbox_default)
        
        # Store imported geometry (polygon) separately from bbox string
        imported_geometry = [None]  # Use list to allow modification in nested functions
        start_var = tk.StringVar(value=settings.get('start_date', DEFAULT_START))
        end_var = tk.StringVar(value=settings.get('end_date', DEFAULT_END))
        out_var = tk.StringVar(value=settings.get('output_folder', OUTDIR_DEFAULT))
        service_account_key_var = tk.StringVar(value=settings.get('service_account_key', ''))
        project_id_var = tk.StringVar(value=settings.get('project_id', ''))
        ml_var = tk.BooleanVar(value=False)
        harm_var = tk.BooleanVar(value=True)
        modis_var = tk.BooleanVar(value=True)
        aster_var = tk.BooleanVar(value=True)
        viirs_var = tk.BooleanVar(value=True)
        workers_var = tk.StringVar(value=str(DEFAULT_WORKERS))
        max_tiles_var = tk.StringVar(value=settings.get('max_tiles', ""))  # Empty = auto-calculate
        dynamic_workers_var = tk.BooleanVar(value=True)  # Enable dynamic workers by default
        server_mode_var = tk.BooleanVar(value=False)  # Server mode - maximize resources
        submit_clicked = [False]
        
        def browse_folder():
            try:
                initial_dir = out_var.get().strip()
                # Validate initial directory exists, otherwise use None
                if initial_dir and os.path.exists(initial_dir):
                    folder = filedialog.askdirectory(initialdir=initial_dir, parent=root)
                else:
                    # Use default directory selection if initial dir doesn't exist
                    folder = filedialog.askdirectory(parent=root)
                
                if folder:
                    out_var.set(folder)
            except Exception as e:
                import tkinter.messagebox as messagebox
                logging.error(f"Error browsing for output folder: {e}", exc_info=True)
                messagebox.showerror(
                    "Error",
                    f"Failed to browse for output folder:\n\n{str(e)}\n\nPlease enter the path manually."
                )
        
        def browse_service_account_key():
            try:
                filename = filedialog.askopenfilename(
                    title="Select Service Account Key File",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                    parent=root
                )
                if filename:
                    service_account_key_var.set(filename)
            except Exception as e:
                import tkinter.messagebox as messagebox
                logging.error(f"Error browsing for service account key: {e}", exc_info=True)
                messagebox.showerror(
                    "Error",
                    f"Failed to browse for service account key file:\n\n{str(e)}\n\nPlease enter the path manually."
                )
        
        def check_satellites_available(start: str, end: str) -> bool:
            """Check if any satellites are operational during the date range."""
            from .utils import is_satellite_operational
            from .config import SATELLITE_DATE_RANGES
            
            # Check all satellites except SLC_FAILURE (that's a special flag)
            satellites_to_check = [
                "LANDSAT_4", "LANDSAT_5", "LANDSAT_7", "LANDSAT_8", "LANDSAT_9",
                "SENTINEL_2", "MODIS_TERRA", "MODIS_AQUA", "ASTER", "VIIRS"
            ]
            
            # Find the earliest satellite start date
            earliest_start = None
            for sat in satellites_to_check:
                if sat in SATELLITE_DATE_RANGES:
                    sat_start = SATELLITE_DATE_RANGES[sat][0]
                    if earliest_start is None or sat_start < earliest_start:
                        earliest_start = sat_start
            
            # Check if start date is before earliest satellite
            start_dt = datetime.fromisoformat(start)
            earliest_dt = datetime.fromisoformat(earliest_start) if earliest_start else None
            
            if earliest_dt and start_dt < earliest_dt:
                # Start date is before any satellites exist
                logging.info(f"Start date {start} is before earliest satellite ({earliest_start})")
                return False
            
            # Check if any satellites are operational during the date range
            available_sats = []
            for sat in satellites_to_check:
                if is_satellite_operational(sat, start, end):
                    available_sats.append(sat)
                    logging.debug(f"Satellite {sat} is operational for {start} to {end}")
            
            if available_sats:
                logging.debug(f"Found {len(available_sats)} operational satellites: {available_sats}")
                return True
            else:
                logging.info(f"No satellites operational for date range {start} to {end}")
                return False
        
        def calculate_suggested_date_range() -> tuple:
            """Calculate suggested date range: Landsat 4 start to current/previous month."""
            from datetime import datetime
            from .config import SATELLITE_DATE_RANGES
            
            # Get Landsat 4 start date (first month: 1982-07)
            landsat4_start = SATELLITE_DATE_RANGES["LANDSAT_4"][0]  # "1982-07-16"
            landsat4_start_dt = datetime.fromisoformat(landsat4_start)
            suggested_start = landsat4_start_dt.replace(day=1).strftime("%Y-%m-%d")  # "1982-07-01"
            
            # Get current date
            now = datetime.now()
            current_day = now.day
            current_month = now.month
            current_year = now.year
            
            # If we're past the 15th of the month, include current month, otherwise use previous month
            if current_day >= 15:
                # Use current month
                suggested_end = now.replace(day=1)
                # Get last day of current month
                if current_month == 12:
                    last_day = datetime(current_year, 12, 31)
                else:
                    next_month = datetime(current_year, current_month + 1, 1)
                    last_day = next_month - timedelta(days=1)
                suggested_end_str = last_day.strftime("%Y-%m-%d")
            else:
                # Use previous month
                if current_month == 1:
                    prev_month = 12
                    prev_year = current_year - 1
                else:
                    prev_month = current_month - 1
                    prev_year = current_year
                prev_month_start = datetime(prev_year, prev_month, 1)
                # Get last day of previous month
                if prev_month == 12:
                    last_day = datetime(prev_year, 12, 31)
                else:
                    next_month = datetime(prev_year, prev_month + 1, 1)
                    last_day = next_month - timedelta(days=1)
                suggested_end_str = last_day.strftime("%Y-%m-%d")
            
            return suggested_start, suggested_end_str
        
        def submit():
            # Save all settings including parameters
            key_path = service_account_key_var.get().strip()
            project_id = project_id_var.get().strip()
            bbox = bbox_var.get().strip()
            start_date = start_var.get().strip()
            end_date = end_var.get().strip()
            output_folder = out_var.get().strip()
            max_tiles = max_tiles_var.get().strip()
            
            # Validate date range - check if any satellites are available
            try:
                if start_date and end_date:
                    logging.info(f"Checking satellite availability for date range: {start_date} to {end_date}")
                    satellites_available = check_satellites_available(start_date, end_date)
                    logging.info(f"Satellite availability check result: {satellites_available}")
                    
                    if not satellites_available:
                        # No satellites available for this date range
                        logging.info("No satellites available, calculating suggested date range...")
                        suggested_start, suggested_end = calculate_suggested_date_range()
                        logging.info(f"Suggested date range: {suggested_start} to {suggested_end}")
                        
                        response = messagebox.askyesno(
                            "No Satellites Available",
                            f"The selected date range ({start_date} to {end_date}) has no operational satellites.\n\n"
                            f"Suggested date range:\n"
                            f"Start: {suggested_start}\n"
                            f"End: {suggested_end}\n\n"
                            f"Would you like to use the suggested date range instead?",
                            icon='question'
                        )
                        if response:
                            start_var.set(suggested_start)
                            end_var.set(suggested_end)
                            start_date = suggested_start
                            end_date = suggested_end
                            logging.info(f"User accepted suggested date range: {suggested_start} to {suggested_end}")
                        else:
                            # User declined - ask if they want to proceed anyway
                            proceed = messagebox.askyesno(
                                "Proceed Anyway?",
                                "No satellites are available for the selected date range.\n\n"
                                "Processing will likely result in no imagery.\n\n"
                                "Do you want to proceed anyway?",
                                icon='warning'
                            )
                            if not proceed:
                                logging.info("User cancelled processing due to no satellites available")
                                return
            except Exception as e:
                logging.error(f"Error checking satellite availability: {e}", exc_info=True)
                # Continue anyway if check fails
            
            # Save all settings
            save_settings(
                service_account_key=key_path if key_path else None,
                project_id=project_id if project_id else None,
                bbox=bbox if bbox else None,
                start_date=start_date if start_date else None,
                end_date=end_date if end_date else None,
                output_folder=output_folder if output_folder else None,
                max_tiles=max_tiles if max_tiles else None
            )
            
            # Initialize Earth Engine if we have credentials
            if key_path or project_id:
                try:
                    import sys
                    import importlib
                    main_module = sys.modules.get('main') or importlib.import_module('main')
                    if not main_module.initialize_earth_engine():
                        messagebox.showerror(
                            "Authentication Failed",
                            "Failed to initialize Earth Engine.\n\n"
                            "Please check:\n"
                            "1. Service account key file is valid\n"
                            "2. Project ID is correct (if provided)\n"
                            "3. You have proper permissions"
                        )
                        return
                except Exception as e:
                    messagebox.showerror(
                        "Error",
                        f"Error initializing Earth Engine: {e}\n\n"
                        "Please check your settings and try again."
                    )
                    return
            
            # Validate tile count before submitting
            if not validate_tile_count():
                # Show error dialog
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
        title_label = tk.Label(scrollable_frame, text="Dead Sea — All Upgrades Downloader", font=("Arial", 14, "bold"))
        title_label.pack(pady=10)
        
        frame = ttk.Frame(scrollable_frame, padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Label(frame, text="BBox lon_min,lat_min,lon_max,lat_max:").grid(row=0, column=0, sticky=tk.W, pady=5)
        bbox_frame = ttk.Frame(frame)
        bbox_frame.grid(row=0, column=1, sticky=tk.W+tk.E, pady=5)
        ttk.Entry(bbox_frame, textvariable=bbox_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def open_map_selector():
            """Open interactive map selector in embedded Python window."""
            try:
                from .map_window import open_map_selector_window
                import tkinter.messagebox as messagebox
                import threading
                
                # Get current bbox if set
                try:
                    bbox_str = bbox_var.get().strip()
                    if bbox_str:
                        current_bbox = tuple(map(float, bbox_str.split(",")))
                        if len(current_bbox) == 4:
                            initial_bbox = current_bbox
                        else:
                            initial_bbox = None
                    else:
                        initial_bbox = None
                except (ValueError, AttributeError):
                    initial_bbox = None
                
                # Show info message first
                messagebox.showinfo(
                    "Map Selector",
                    "Map selector will open in a Python window!\n\n"
                    "1. Draw a rectangle or polygon on the map (use draw tool top-left)\n"
                    "2. Click 'Save BBox' button\n"
                    "3. Use 'Paste from Map' button to add bbox to the main window\n\n"
                    "Tip: Search for locations and click results to zoom to them"
                )
                
                # Open map window - pass tkinter root so webview can run on main thread
                def open_map():
                    html_file = open_map_selector_window(initial_bbox, tkinter_root=root)
                    if not html_file:
                        root.after(0, lambda: messagebox.showerror(
                            "Error",
                            "Could not open map selector.\n\n"
                            "Please install required packages:\n"
                            "pip install folium"
                        ))
                
                # Open map in background thread (HTML creation can be async, webview scheduled on main thread)
                monitor_thread = threading.Thread(target=open_map, daemon=True)
                monitor_thread.start()
                
            except ImportError as e:
                import tkinter.messagebox as messagebox
                messagebox.showerror(
                    "Missing Dependencies",
                    f"Map selector requires additional package:\n\n"
                    f"pip install folium\n"
                    f"pip install pywebview (optional, for embedded window)\n\n"
                    f"Error: {e}"
                )
            except Exception as e:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Error", f"Failed to open map selector: {e}")
        
        def paste_from_map():
            """Paste bbox from clipboard (after user saves from map selector)."""
            try:
                import tkinter.messagebox as messagebox
                try:
                    # Try multiple methods to get clipboard
                    clipboard_text = None
                    
                    # Method 1: Try tkinter clipboard
                    try:
                        root_temp = tk.Tk()
                        root_temp.withdraw()
                        clipboard_text = root_temp.clipboard_get()
                        root_temp.destroy()
                    except tk.TclError:
                        pass
                    
                    # Method 2: Try pyperclip if available
                    if not clipboard_text:
                        try:
                            import pyperclip
                            clipboard_text = pyperclip.paste()
                        except (ImportError, Exception):
                            pass
                    
                    if not clipboard_text:
                        messagebox.showwarning(
                            "No BBox Found",
                            "Clipboard is empty or couldn't be accessed.\n\n"
                            "Please:\n"
                            "1. Draw a rectangle or polygon on the map\n"
                            "2. Click 'Save BBox' in the map window\n"
                            "3. Try clicking 'Paste from Map' again"
                        )
                        return
                    
                    # Check for special marker from map window
                    bbox_str = None
                    if clipboard_text.startswith('GEE_BBOX:'):
                        bbox_str = clipboard_text.replace('GEE_BBOX:', '').strip()
                    else:
                        # Try to parse as bbox
                        parts = clipboard_text.strip().split(',')
                        if len(parts) == 4:
                            try:
                                bbox = tuple(map(float, parts))
                                bbox_str = ",".join(map(str, bbox))
                            except (ValueError, TypeError):
                                pass
                    
                    if bbox_str:
                        bbox_var.set(bbox_str)
                        messagebox.showinfo("Success", f"BBox pasted from map selector:\n{bbox_str}")
                    else:
                        messagebox.showwarning(
                            "No BBox Found",
                            f"No valid BBox found in clipboard.\n\n"
                            f"Clipboard content: {clipboard_text[:50]}...\n\n"
                            "Please:\n"
                            "1. Draw a rectangle or polygon on the map\n"
                            "2. Click 'Save BBox' in the map window\n"
                            "3. The bbox will be automatically added, or click 'Paste from Map' again"
                        )
                except Exception as e:
                    import tkinter.messagebox as messagebox
                    messagebox.showerror("Error", f"Failed to paste BBox: {e}")
            except Exception as e:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Error", f"Failed to paste BBox: {e}")
        
        # Periodic clipboard check disabled - user must manually paste or use "Paste from Map" button
        # def check_clipboard_periodically():
        #     """Periodically check clipboard for GEE_BBOX: prefix and auto-populate."""
        #     ... (disabled)
        
        # Periodic clipboard checking disabled - no auto-population
        # root.after(2000, check_clipboard_periodically)
        
        # Bbox file monitoring disabled - no auto-import
        # def check_bbox_files():
        #     """Check bbox_files folder for new GeoJSON files and auto-populate bbox."""
        #     ... (disabled)
        
        # Bbox file monitoring disabled - user must manually import or paste
        
        def import_bbox_file():
            """Import bbox from a file."""
            try:
                import tkinter.messagebox as messagebox
                try:
                    filename = filedialog.askopenfilename(
                        title="Import BBox from File",
                        filetypes=[
                            ("Text files", "*.txt"),
                            ("CSV files", "*.csv"),
                            ("GeoJSON files", "*.geojson"),
                            ("All files", "*.*")
                        ],
                        parent=root
                    )
                    if not filename:
                        return
                except Exception as e:
                    import tkinter.messagebox as messagebox
                    logging.error(f"Error browsing for BBox file: {e}", exc_info=True)
                    messagebox.showerror(
                        "Error",
                        f"Failed to browse for BBox file:\n\n{str(e)}\n\nPlease check the file path manually."
                    )
                    return
                
                # Read and parse file with encoding handling
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                except UnicodeDecodeError:
                    # Try with different encoding
                    with open(filename, 'r', encoding='latin-1') as f:
                        content = f.read().strip()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to read file: {e}")
                    return
                
                bbox = None
                
                # Try CSV format: lon_min,lat_min,lon_max,lat_max
                parts = content.split(',')
                if len(parts) >= 4:
                    try:
                        coords = [float(x.strip()) for x in parts[:4]]
                        if all(not math.isnan(x) for x in coords):
                            bbox = coords
                    except ValueError:
                        pass
                
                # Try GeoJSON format - store full geometry for polygon support
                geometry_obj = None
                if not bbox:
                    try:
                        import json
                        from shapely.geometry import shape
                        geojson = json.loads(content)
                        if geojson.get('type') == 'Feature' and geojson.get('geometry'):
                            geometry_obj = shape(geojson['geometry'])
                            if geometry_obj.geom_type == 'Polygon':
                                coords = geojson['geometry']['coordinates'][0]
                                lons = [c[0] for c in coords]
                                lats = [c[1] for c in coords]
                                bbox = [min(lons), min(lats), max(lons), max(lats)]
                        elif geojson.get('type') == 'FeatureCollection' and geojson.get('features'):
                            if geojson['features']:
                                geom_dict = geojson['features'][0].get('geometry', {})
                                if geom_dict.get('type') == 'Polygon':
                                    geometry_obj = shape(geom_dict)
                                    coords = geom_dict['coordinates'][0]
                                    lons = [c[0] for c in coords]
                                    lats = [c[1] for c in coords]
                                    bbox = [min(lons), min(lats), max(lons), max(lats)]
                        elif geojson.get('type') == 'Polygon':
                            geometry_obj = shape(geojson)
                            coords = geojson['coordinates'][0]
                            lons = [c[0] for c in coords]
                            lats = [c[1] for c in coords]
                            bbox = [min(lons), min(lats), max(lons), max(lats)]
                    except (json.JSONDecodeError, KeyError, IndexError, Exception) as e:
                        logging.debug(f"Error parsing GeoJSON: {e}")
                        pass
                
                if bbox and len(bbox) == 4:
                    # Validate bbox coordinates
                    lon_min, lat_min, lon_max, lat_max = bbox
                    if not (-180 <= lon_min <= 180 and -180 <= lon_max <= 180 and
                            -90 <= lat_min <= 90 and -90 <= lat_max <= 90 and
                            lon_min < lon_max and lat_min < lat_max):
                        messagebox.showerror(
                            "Invalid Coordinates",
                            "BBox coordinates are out of valid range:\n"
                            "Longitude: -180 to 180\n"
                            "Latitude: -90 to 90\n"
                            "And min < max for both"
                        )
                        return
                    
                    bbox_str = ",".join(map(str, bbox))
                    bbox_var.set(bbox_str)
                    
                    # Store geometry object if it's a polygon (not just bbox)
                    if geometry_obj is not None and geometry_obj.geom_type == 'Polygon':
                        imported_geometry[0] = geometry_obj
                        logging.info("Stored polygon geometry from imported file")
                    else:
                        imported_geometry[0] = None
                    
                    # Ask if user wants to view on map (non-blocking)
                    view_on_map = messagebox.askyesno(
                        "Import Successful",
                        f"BBox imported from file:\n{bbox_str}\n\n"
                        "Would you like to view it on the map?"
                    )
                    
                    if view_on_map:
                        try:
                            from .map_window import open_map_selector_window
                            # Open map in background (pass tkinter root for webview)
                            def open_map():
                                try:
                                    open_map_selector_window(tuple(bbox), tkinter_root=root)
                                except Exception as e:
                                    logging.error(f"Error opening map window: {e}")
                                    root.after(0, lambda: messagebox.showwarning(
                                        "Map Window",
                                        f"BBox imported successfully, but could not open map window:\n{e}"
                                    ))
                            import threading
                            thread = threading.Thread(target=open_map, daemon=True)
                            thread.start()
                        except Exception as e:
                            logging.error(f"Error opening map window: {e}")
                            messagebox.showwarning(
                                "Map Window",
                                f"BBox imported successfully, but could not open map window:\n{e}"
                            )
                else:
                    messagebox.showerror(
                        "Invalid Format",
                        "Could not parse BBox from file.\n\n"
                        "Expected formats:\n"
                        "1. CSV: lon_min,lat_min,lon_max,lat_max\n"
                        "2. GeoJSON: Feature or FeatureCollection with Polygon geometry"
                    )
            except Exception as e:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Error", f"Failed to import BBox file: {e}")
        
        ttk.Button(bbox_frame, text="🗺️ Map", command=open_map_selector, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(bbox_frame, text="📋 Paste", command=paste_from_map, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(bbox_frame, text="📁 Import", command=import_bbox_file, width=10).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(frame, text="Start date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=start_var, width=40).grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="End date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=end_var, width=40).grid(row=2, column=1, pady=5)
        
        ttk.Label(frame, text="Output folder:").grid(row=3, column=0, sticky=tk.W, pady=5)
        folder_frame = ttk.Frame(frame)
        folder_frame.grid(row=3, column=1, sticky=tk.W+tk.E, pady=5)
        ttk.Entry(folder_frame, textvariable=out_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(folder_frame, text="Browse", command=browse_folder).pack(side=tk.LEFT, padx=5)
        
        # Earth Engine Authentication section
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)
        ttk.Label(frame, text="Earth Engine Authentication", font=("Arial", 10, "bold")).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="Service Account Key:").grid(row=6, column=0, sticky=tk.W, pady=5)
        key_frame = ttk.Frame(frame)
        key_frame.grid(row=6, column=1, sticky=tk.W+tk.E, pady=5)
        ttk.Entry(key_frame, textvariable=service_account_key_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(key_frame, text="Browse", command=browse_service_account_key, width=10).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(frame, text="Project ID (optional):").grid(row=7, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=project_id_var, width=40).grid(row=7, column=1, pady=5)
        # Use tk.Label instead of ttk.Label for fg color support
        help_style = ttk.Style()
        help_style.configure("Help.TLabel", foreground="gray", font=("Arial", 8))
        ttk.Label(frame, text="(Required if using user authentication instead of service account)", 
                 style="Help.TLabel").grid(row=8, column=1, sticky=tk.W, pady=2)
        
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=9, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)
        
        ttk.Checkbutton(frame, text="Enable ML cloud cleanup (optional)", variable=ml_var).grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Enable harmonization (S2 <-> LS)", variable=harm_var).grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Checkbutton(frame, text="Include MODIS", variable=modis_var).grid(row=12, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Include ASTER", variable=aster_var).grid(row=13, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Include VIIRS", variable=viirs_var).grid(row=14, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Enable dynamic worker scaling (auto-adjust based on system performance)", 
                       variable=dynamic_workers_var).grid(row=15, column=0, columnspan=2, sticky=tk.W, pady=5)
        # Fix: ttk.Checkbutton doesn't support foreground/font directly - use Style instead
        style = ttk.Style()
        style.configure("ServerMode.TCheckbutton", foreground="blue", font=("Arial", 9, "bold"))
        ttk.Checkbutton(frame, text="Server Mode (maximize resources, focus all CPU/memory on processing)", 
                       variable=server_mode_var, style="ServerMode.TCheckbutton").grid(row=16, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="Resolution (meters, forced to 5m):").grid(row=17, column=0, sticky=tk.W, pady=5)
        resolution_var = tk.StringVar(value="5.0")
        ttk.Entry(frame, textvariable=resolution_var, width=40).grid(row=17, column=1, pady=5)
        ttk.Label(frame, text="Workers:").grid(row=18, column=0, sticky=tk.W, pady=5)
        workers_entry = ttk.Entry(frame, textvariable=workers_var, width=40)
        workers_entry.grid(row=18, column=1, pady=5)
        
        ttk.Label(frame, text="Max tiles (empty = auto):").grid(row=19, column=0, sticky=tk.W, pady=5)
        tile_entry = ttk.Entry(frame, textvariable=max_tiles_var, width=40)
        tile_entry.grid(row=19, column=1, pady=5)
        
        # Validation label for tile size warning
        # Fix: Use Style for ttk.Label foreground color (more reliable across platforms)
        warning_style = ttk.Style()
        warning_style.configure("Warning.TLabel", foreground="red", font=("Arial", 8))
        tile_warning_label = ttk.Label(frame, text="", style="Warning.TLabel")
        tile_warning_label.grid(row=20, column=1, sticky=tk.W, pady=2)
        
        def validate_tile_count(*args):
            """Validate tile count and calculate expected tile size."""
            try:
                tile_count_str = max_tiles_var.get().strip()
                if not tile_count_str:
                    tile_warning_label.config(text="")
                    return True
                
                tile_count = int(tile_count_str)
                if tile_count < 1:
                    warning_style.configure("Warning.TLabel", foreground="red")
                    tile_warning_label.config(text="Error: Tile count must be at least 1", style="Warning.TLabel")
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
                        warning_style.configure("Warning.TLabel", foreground="red")
                        tile_warning_label.config(
                            text=f"ERROR: {size_mb:.1f} MB per tile exceeds 40 MB limit! Use more tiles.",
                            style="Warning.TLabel"
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
                        
                        warning_style.configure("Warning.TLabel", foreground="green")
                        tile_warning_label.config(
                            text=f"OK: ~{size_mb:.1f} MB/tile, {actual_tiles} tiles, ~{int(pixels_per_side)} px/tile | Est. time: {time_str}",
                            style="Warning.TLabel"
                        )
                        return True
                except (ValueError, ZeroDivisionError) as e:
                    warning_style.configure("Warning.TLabel", foreground="red")
                    tile_warning_label.config(text="Error: Invalid bbox or calculation", style="Warning.TLabel")
                    return False
                    
            except ValueError:
                warning_style.configure("Warning.TLabel", foreground="red")
                tile_warning_label.config(text="Error: Tile count must be a number", style="Warning.TLabel")
                return False
        
        # Bind validation to tile count, bbox, and workers changes
        max_tiles_var.trace('w', validate_tile_count)
        bbox_var.trace('w', validate_tile_count)
        workers_var.trace('w', validate_tile_count)
        
        ttk.Label(frame, text="(All satellites forced to 5m resolution)", font=("Arial", 8)).grid(row=21, column=1, sticky=tk.W, pady=2)
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=22, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Submit", command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=5)
        
        print("Opening GUI window...", flush=True)
        root.mainloop()
        
        if not submit_clicked[0]:
            print("Cancelled", flush=True)
            return
        
        # Fix: Add logging to track execution flow
        logging.info("Start menu closed, beginning processing setup...")
        print("Start menu closed, setting up processing...", flush=True)
        
        # Parse bbox string to geometry (bbox tuple or polygon from imported file)
        bbox_str = bbox_var.get().strip()
        geometry = None
        
        # First, check if we have an imported geometry object
        if imported_geometry[0] is not None:
            geometry = imported_geometry[0]
            logging.info("Using imported polygon geometry")
        else:
            # Try to parse as bbox tuple
            try:
                bbox = tuple(map(float, bbox_str.split(",")))
                if len(bbox) == 4:
                    geometry = bbox  # Use bbox tuple
            except (ValueError, AttributeError):
                pass
            
            # If bbox parsing failed, try to load from saved geometry file in bbox_files folder
            if geometry is None:
                try:
                    # Get bbox_files directory
                    from .map_window import _get_bbox_files_dir
                    bbox_dir = _get_bbox_files_dir()
                    # Look for most recent GeoJSON file
                    import json
                    from shapely.geometry import shape
                    import glob
                    geojson_files = sorted(glob.glob(os.path.join(bbox_dir, '*.geojson')), key=os.path.getmtime, reverse=True)
                    if geojson_files:
                        # Try to load the most recent one
                        with open(geojson_files[0], 'r') as f:
                            geojson = json.load(f)
                            if geojson.get('type') == 'Feature' and geojson.get('geometry'):
                                geometry = shape(geojson['geometry'])
                            elif geojson.get('type') == 'Polygon':
                                geometry = shape(geojson)
                except Exception as e:
                    logging.debug(f"Could not load geometry from file: {e}")
            
            # Fallback to bbox if geometry still not set
            if geometry is None:
                try:
                    bbox_tuple = tuple(map(float, bbox_str.split(",")))
                    if len(bbox_tuple) == 4:
                        geometry = bbox_tuple
                    else:
                        raise ValueError(f"Invalid bbox format: expected 4 coordinates, got {len(bbox_tuple)}")
                except (ValueError, AttributeError) as e:
                    raise ValueError(f"Invalid bbox format: {bbox_str}. Error: {e}")
        start = start_var.get()
        end = end_var.get()
        out = out_var.get()
        enable_ml = ml_var.get()
        enable_harmonize = harm_var.get()
        include_modis = modis_var.get()
        include_aster = aster_var.get()
        include_viirs = viirs_var.get()
        server_mode = server_mode_var.get()
        
        try:
            workers = int(workers_var.get())
            if workers < 1:
                workers = DEFAULT_WORKERS
        except (ValueError, AttributeError):
            workers = DEFAULT_WORKERS
        
        # Server mode: maximize resources
        if server_mode:
            # Use all available CPU cores
            workers = multiprocessing.cpu_count()
            # Increase max workers for dynamic scaling (server mode = overclock)
            from . import config
            config.MAX_WORKERS = multiprocessing.cpu_count() * 4  # Server mode: 4x CPU count (I/O-bound tasks benefit)
            logging.info(f"Server mode enabled: Using {workers} workers, max workers: {config.MAX_WORKERS} (overclocked)")
            
            # Set maximum priority (Windows) - try REALTIME if available, fallback to HIGH
            priority_set = False
            try:
                if os.name == 'nt':  # Windows
                    try:
                        import psutil
                        p = psutil.Process()
                        # Try REALTIME_PRIORITY_CLASS first (maximum performance)
                        try:
                            # REALTIME can be dangerous but we're in server mode - push to limit
                            if hasattr(psutil, 'REALTIME_PRIORITY_CLASS'):
                                p.nice(psutil.REALTIME_PRIORITY_CLASS)
                                priority_set = True
                                logging.info("Server mode: Set process priority to REALTIME_PRIORITY_CLASS (Windows - MAXIMUM)")
                            else:
                                p.nice(psutil.HIGH_PRIORITY_CLASS)
                                priority_set = True
                                logging.info("Server mode: Set process priority to HIGH_PRIORITY_CLASS (Windows)")
                        except (OSError, PermissionError, AttributeError):
                            # Fallback to HIGH if REALTIME fails
                            p.nice(psutil.HIGH_PRIORITY_CLASS)
                            priority_set = True
                            logging.info("Server mode: Set process priority to HIGH_PRIORITY_CLASS (Windows - REALTIME unavailable)")
                    except ImportError:
                        logging.warning("Server mode: psutil not available, cannot set process priority. Install with: pip install psutil")
                    except Exception as e:
                        logging.warning(f"Server mode: Failed to set process priority: {e}")
            except Exception as e:
                logging.debug(f"Server mode: Error checking OS: {e}")
            
            # Set maximum priority (Unix/Linux) - push to limit in server mode
            if not priority_set:
                try:
                    if os.name != 'nt':  # Unix/Linux
                        try:
                            os.nice(-19)  # Server mode: Maximum priority (-20 is system level, -19 is highest user level)
                            priority_set = True
                            logging.info("Server mode: Set process priority to -19 (Unix/Linux - MAXIMUM)")
                        except PermissionError:
                            logging.warning("Server mode: Insufficient permissions to set process priority. Run with sudo/admin privileges for maximum performance.")
                        except OSError as e:
                            logging.warning(f"Server mode: Failed to set process priority: {e}")
                except Exception as e:
                    logging.debug(f"Server mode: Error setting Unix priority: {e}")
            
            if not priority_set:
                logging.info("Server mode: Process priority unchanged (may require elevated privileges)")
        
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
        geometry = bbox  # Set geometry to match GUI path
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
    logging.info(f"Processing {len(months)} months from {start} to {end}")
    print(f"Processing {len(months)} months...", flush=True)
    
    # Create console progress display
    from .console_progress import ConsoleProgress
    
    logging.info("Initializing console progress display...")
    print("Initializing console progress display...", flush=True)
    
    # Estimate total tiles (will be updated when we know actual count)
    progress_window = ConsoleProgress(total_tiles=100, total_months=len(months))
    
    # Process months with progress updates
    try:
        for month_idx, (ms, me) in enumerate(months):
            dt = datetime.fromisoformat(ms)
            print(f"\n{'='*80}")
            print(f"Starting month {dt.year}-{dt.month:02d} ({month_idx + 1}/{len(months)})")
            print(f"{'='*80}\n")
            
            if progress_window:
                try:
                    progress_window.update_mosaic_progress(month_idx + 1, len(months))
                except Exception as e:
                    logging.debug(f"Error updating progress display: {e}")
            
            process_month(geometry, dt.year, dt.month, out, workers, enable_ml, enable_harmonize, 
                         include_modis, include_aster, include_viirs, 
                         target_resolution=target_resolution, max_tiles=max_tiles,
                         progress_window=progress_window, server_mode=server_mode)
        
        # Show completion
        if progress_window:
            try:
                progress_window.destroy()
                print("\n✅ All processing complete!\n")
            except Exception as e:
                logging.debug(f"Error finalizing progress display: {e}")
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logging.error(f"Error during processing: {e}\nFull traceback:\n{error_traceback}")
        print(f"\n❌ Processing error: {e}\n")
        print(f"Full traceback:\n{error_traceback}")
        if progress_window:
            try:
                progress_window.destroy()
            except Exception:
                pass
    
    # Restore original config value
    config.ENABLE_DYNAMIC_WORKERS = original_dynamic_workers


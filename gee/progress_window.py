"""
Progress window for real-time monitoring of mosaic processing.
Replaces HTML dashboard with native Python GUI.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import queue
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging


class ProgressWindow:
    """Real-time progress monitoring window with progress bars, countdown, pause, and console."""
    
    def __init__(self, total_tiles: int, total_months: int = 1):
        self.total_tiles = total_tiles
        self.total_months = total_months
        self.current_month = 0
        self.processed_tiles = 0
        self.failed_tiles = 0
        self.start_time = time.time()
        self.paused = False
        self.pause_start_time = None
        self.total_pause_time = 0.0
        self.processing_times = []
        self.satellite_counts = {}
        self.satellite_stats = {}
        self.all_test_results = []
        # Fix: Add max size to prevent memory leak
        self.message_queue = queue.Queue(maxsize=1000)
        # Fix: All closed flag access must be protected by lock
        self._closed = False
        # Fix: Add lock for thread synchronization
        self._lock = threading.Lock()
        self._destroying = False
        # Fix: Track thread health
        self._update_thread_alive = True
        # Track recent tile completions for dynamic throughput calculation
        # Each entry is (timestamp, tile_count) - tracks when tiles were completed
        self.recent_completions = []  # Sliding window of (timestamp, count) tuples
        self.recent_window_size = 30  # Use last 30 tiles for dynamic calculation
        # Fix: Track scheduled UI updates to prevent accumulation
        self._update_ui_scheduled = None
        
        # Create window
        self.root = tk.Tk()
        self.root.title("Mosaic Processing Progress")
        self.root.geometry("900x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Fix: Ensure window is visible and on top
        self.root.deiconify()  # Make sure window is visible
        self.root.lift()  # Bring to front
        self.root.focus_force()  # Focus the window
        self.root.update_idletasks()  # Process pending events to show window
        
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Mosaic Processing Progress", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=5)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=5)
        
        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(fill=tk.X)
        
        # Processed tiles
        self.processed_label = ttk.Label(stats_inner, text="Processed: 0 / 0", font=("Arial", 12))
        self.processed_label.pack(side=tk.LEFT, padx=10)
        
        # Failed tiles
        # Fix: Use Style for ttk.Label foreground color
        failed_style = ttk.Style()
        failed_style.configure("Failed.TLabel", foreground="red", font=("Arial", 12))
        self.failed_label = ttk.Label(stats_inner, text="Failed: 0", style="Failed.TLabel")
        self.failed_label.pack(side=tk.LEFT, padx=10)
        
        # Countdown timer
        self.countdown_label = ttk.Label(stats_inner, text="Time Remaining: --:--:--", 
                                        font=("Courier New", 12, "bold"))
        self.countdown_label.pack(side=tk.LEFT, padx=10)
        
        # Elapsed time
        self.elapsed_label = ttk.Label(stats_inner, text="Elapsed: 00:00:00", font=("Arial", 10))
        self.elapsed_label.pack(side=tk.LEFT, padx=10)
        
        # Progress bars frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.pack(fill=tk.X, pady=5)
        
        # Tile progress
        ttk.Label(progress_frame, text="Tile Progress:").pack(anchor=tk.W)
        self.tile_progress = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.tile_progress.pack(fill=tk.X, pady=2)
        self.tile_progress_label = ttk.Label(progress_frame, text="0%")
        self.tile_progress_label.pack(anchor=tk.W)
        
        # Mosaic progress (per month)
        ttk.Label(progress_frame, text="Mosaic Progress (Current Month):").pack(anchor=tk.W, pady=(10, 0))
        self.mosaic_progress = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.mosaic_progress.pack(fill=tk.X, pady=2)
        self.mosaic_progress_label = ttk.Label(progress_frame, text="0%")
        self.mosaic_progress_label.pack(anchor=tk.W)
        
        # Full project progress
        ttk.Label(progress_frame, text="Full Project Progress:").pack(anchor=tk.W, pady=(10, 0))
        self.project_progress = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.project_progress.pack(fill=tk.X, pady=2)
        self.project_progress_label = ttk.Label(progress_frame, text="0%")
        self.project_progress_label.pack(anchor=tk.W)
        
        # Satellite usage frame
        satellite_frame = ttk.LabelFrame(main_frame, text="Satellite Usage", padding="10")
        satellite_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Satellite stats text (scrollable)
        self.satellite_text = scrolledtext.ScrolledText(satellite_frame, height=8, wrap=tk.WORD)
        self.satellite_text.pack(fill=tk.BOTH, expand=True)
        self.satellite_text.insert(tk.END, "Waiting for processing to start...\n")
        self.satellite_text.config(state=tk.DISABLED)
        
        # Console output frame
        console_frame = ttk.LabelFrame(main_frame, text="Console Output", padding="10")
        console_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.console_text = scrolledtext.ScrolledText(console_frame, height=10, wrap=tk.WORD, 
                                                     font=("Courier New", 9))
        self.console_text.pack(fill=tk.BOTH, expand=True)
        self.console_text.insert(tk.END, "Console output will appear here...\n")
        self.console_text.config(state=tk.DISABLED)
        
        # Control buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.pause_button = ttk.Button(button_frame, text="Pause", command=self.toggle_pause)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Clear Console", command=self.clear_console).pack(side=tk.LEFT, padx=5)
        
        # Fix: Start update thread (but GUI updates will go through root.after)
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()
    
    @property
    def closed(self) -> bool:
        """Thread-safe access to closed flag."""
        with self._lock:
            return self._closed
    
    def _set_closed(self, value: bool):
        """Thread-safe setter for closed flag."""
        with self._lock:
            self._closed = value
    
    def is_alive(self) -> bool:
        """Check if window and update thread are still alive."""
        with self._lock:
            if self._closed or self._destroying:
                return False
            if not self._update_thread_alive:
                return False
        # Check if update thread is actually alive
        if not self.update_thread.is_alive():
            with self._lock:
                self._update_thread_alive = False
            return False
        return True
    
    def toggle_pause(self):
        """Toggle pause state (thread-safe)."""
        pause_msg = None
        with self._lock:
            if self.paused:
                # Resume
                if self.pause_start_time:
                    self.total_pause_time += time.time() - self.pause_start_time
                    self.pause_start_time = None
                self.paused = False
                pause_msg = "Processing RESUMED"
            else:
                # Pause
                self.pause_start_time = time.time()
                self.paused = True
                pause_msg = "Processing PAUSED"
        
        # Fix: Update button and send message outside lock to avoid deadlock
        try:
            if pause_msg == "Processing RESUMED":
                self.pause_button.config(text="Pause")
            else:
                self.pause_button.config(text="Resume")
            if pause_msg:
                self.add_console_message(pause_msg)
        except Exception as e:
            logging.debug(f"Error updating pause button: {e}")
    
    def clear_console(self):
        """Clear console output (thread-safe)."""
        try:
            if not self._is_window_valid():
                return
            self.console_text.config(state=tk.NORMAL)
            self.console_text.delete(1.0, tk.END)
            self.console_text.config(state=tk.DISABLED)
        except Exception as e:
            logging.debug(f"Error clearing console: {e}")
    
    def _is_window_valid(self) -> bool:
        """Check if window is still valid (thread-safe)."""
        try:
            with self._lock:
                if self._closed or self._destroying:
                    return False
                # Check window existence while holding lock to prevent race
                window_exists = False
                try:
                    window_exists = self.root.winfo_exists()
                except (tk.TclError, RuntimeError):
                    return False
                return window_exists
        except Exception:
            return False
    
    def add_console_message(self, message: str, level: str = "INFO"):
        """Add message to console output (thread-safe)."""
        # Fix: Check closed flag with lock protection
        with self._lock:
            if self._closed:
                return
        
        # Fix: Check if update thread is alive before queuing
        if not self.is_alive():
            return
        
        # Map status strings to levels
        status_to_level = {
            "BUILDING": "INFO",
            "MOSAIC_OK": "SUCCESS",
            "SELECTING": "INFO",
            "URL_GEN": "INFO",
            "DOWNLOADING": "INFO",
            "DOWNLOADED": "SUCCESS",
            "VALIDATING": "INFO",
            "VALIDATED": "SUCCESS",
            "MASKING": "INFO",
            "SUCCESS": "SUCCESS",
            "FAILED": "ERROR",
            "ERROR": "ERROR"
        }
        
        # If message is a status, map it
        if level in status_to_level:
            level = status_to_level[level]
        
        # Queue message for main thread processing (with timeout to prevent blocking)
        try:
            self.message_queue.put({"type": "console", "message": message, "level": level}, timeout=0.1)
        except queue.Full:
            # Queue is full, drop oldest message
            try:
                self.message_queue.get_nowait()
                self.message_queue.put_nowait({"type": "console", "message": message, "level": level})
            except queue.Empty:
                pass
    
    def update_tile_progress(self, processed: int, failed: int = 0):
        """Update tile progress (thread-safe)."""
        if not self.is_alive():
            return
        try:
            self.message_queue.put({"type": "tile_progress", "processed": processed, "failed": failed}, timeout=0.1)
        except queue.Full:
            pass  # Drop update if queue is full
    
    def update_mosaic_progress(self, month: int, total_months: int):
        """Update mosaic progress (thread-safe via root.after)."""
        if not self.is_alive():
            return
        
        def _update():
            if not self._is_window_valid():
                return
            try:
                # Fix: Thread-safe assignment to current_month
                with self._lock:
                    self.current_month = month
                if total_months > 0:
                    percent = int((month / total_months) * 100)
                    self.mosaic_progress['value'] = percent
                    self.mosaic_progress_label.config(text=f"{percent}% (Month {month}/{total_months})")
                else:
                    self.mosaic_progress['value'] = 0
                    self.mosaic_progress_label.config(text="0%")
            except Exception as e:
                logging.debug(f"Error updating mosaic progress: {e}")
        
        if self._is_window_valid():
            try:
                self.root.after(0, _update)
            except Exception:
                pass
    
    def update_project_progress(self, overall_percent: float):
        """Update full project progress (thread-safe via root.after)."""
        if not self.is_alive():
            return
        
        def _update():
            if not self._is_window_valid():
                return
            try:
                percent = int(overall_percent)
                self.project_progress['value'] = percent
                self.project_progress_label.config(text=f"{percent}%")
            except Exception as e:
                logging.debug(f"Error updating project progress: {e}")
        
        if self._is_window_valid():
            try:
                self.root.after(0, _update)
            except Exception:
                pass
    
    def add_satellite(self, satellite: str, detailed_stats: Dict = None):
        """Add satellite usage (thread-safe)."""
        if not self.is_alive() or not satellite:
            return
        try:
            self.message_queue.put({"type": "satellite", "satellite": satellite, "stats": detailed_stats}, timeout=0.1)
        except queue.Full:
            pass
    
    def add_test_result(self, test_result: Dict):
        """Add test result (thread-safe)."""
        if not self.is_alive() or not test_result:
            return
        try:
            self.message_queue.put({"type": "test_result", "result": test_result}, timeout=0.1)
        except queue.Full:
            pass
    
    def add_processing_time(self, processing_time: float):
        """Add processing time for countdown estimation (thread-safe)."""
        if not self.is_alive() or not processing_time or processing_time <= 0:
            return
        try:
            self.message_queue.put({"type": "processing_time", "time": processing_time}, timeout=0.1)
        except queue.Full:
            pass
    
    def _update_satellite_display_safe(self):
        """Update satellite usage display (called from main thread)."""
        if not self._is_window_valid():
            return
        
        try:
            self.satellite_text.config(state=tk.NORMAL)
            self.satellite_text.delete(1.0, tk.END)
            
            with self._lock:
                satellite_counts = self.satellite_counts.copy()
                satellite_stats = self.satellite_stats.copy()
            
            if not satellite_counts:
                self.satellite_text.insert(tk.END, "No satellite data yet...\n")
            else:
                # Sort by count descending
                sorted_sats = sorted(satellite_counts.items(), key=lambda x: x[1], reverse=True)
                
                self.satellite_text.insert(tk.END, "Satellite Usage:\n")
                self.satellite_text.insert(tk.END, "-" * 60 + "\n")
                
                for sat, count in sorted_sats:
                    stats = satellite_stats.get(sat, {})
                    quality = stats.get("quality_score", 0.0)
                    cloud_frac = stats.get("cloud_fraction", 0.0) * 100
                    resolution = stats.get("native_resolution", "N/A")
                    
                    self.satellite_text.insert(tk.END, 
                        f"{sat:25s} | Tiles: {count:3d} | Quality: {quality:.3f} | "
                        f"Clouds: {cloud_frac:.1f}% | Res: {resolution}\n")
            
            self.satellite_text.see(tk.END)
            self.satellite_text.config(state=tk.DISABLED)
        except Exception as e:
            logging.debug(f"Error updating satellite display: {e}")
    
    def format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        if seconds <= 0 or not isinstance(seconds, (int, float)) or not (seconds < 1e10):
            return "--:--:--"
        try:
            td = timedelta(seconds=int(seconds))
            hours, remainder = divmod(td.seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        except Exception:
            return "--:--:--"
    
    def update_loop(self):
        """Main update loop running in separate thread - processes queue and schedules GUI updates."""
        consecutive_errors = 0
        max_errors = 10
        
        try:
            while True:
                # Fix: Check closed flag with lock
                with self._lock:
                    if self._closed:
                        break
                
                try:
                    # Process message queue
                    try:
                        while True:
                            msg = self.message_queue.get_nowait()
                            # Fix: All GUI updates must go through root.after()
                            if msg['type'] == 'console':
                                def _add_console():
                                    if not self._is_window_valid():
                                        return
                                    try:
                                        timestamp = datetime.now().strftime("%H:%M:%S")
                                        level = msg.get('level', 'INFO')
                                        message = msg['message']
                                        self.console_text.config(state=tk.NORMAL)
                                        self.console_text.insert(tk.END, f"[{timestamp}] {message}\n")
                                        self.console_text.see(tk.END)
                                        self.console_text.config(state=tk.DISABLED)
                                        # Keep console size manageable
                                        lines = int(self.console_text.index('end-1c').split('.')[0])
                                        if lines > 1000:
                                            self.console_text.config(state=tk.NORMAL)
                                            self.console_text.delete(1.0, f"{lines - 1000}.0")
                                            self.console_text.config(state=tk.DISABLED)
                                    except Exception as e:
                                        logging.debug(f"Error adding console message: {e}")
                                
                                if self._is_window_valid():
                                    try:
                                        self.root.after(0, _add_console)
                                    except Exception:
                                        pass
                            
                            elif msg['type'] == 'tile_progress':
                                def _update_tile():
                                    if not self._is_window_valid():
                                        return
                                    try:
                                        processed = msg['processed']
                                        failed = msg.get('failed', 0)
                                        with self._lock:
                                            # Track completion timestamps for dynamic throughput calculation
                                            if processed > self.processed_tiles:
                                                current_time = time.time()
                                                # Add new completion entry
                                                self.recent_completions.append((current_time, processed))
                                                # Keep only recent window
                                                if len(self.recent_completions) > self.recent_window_size * 2:
                                                    # Keep last window_size entries plus first entry for span calculation
                                                    self.recent_completions = [self.recent_completions[0]] + self.recent_completions[-self.recent_window_size:]
                                            
                                            self.processed_tiles = processed
                                            self.failed_tiles = failed
                                            total = self.total_tiles  # Fix: Read total_tiles within lock
                                        if total > 0:
                                            percent = int((processed / total) * 100)
                                            self.tile_progress['value'] = percent
                                            self.tile_progress_label.config(text=f"{percent}% ({processed}/{total} tiles)")
                                        self.processed_label.config(text=f"Processed: {processed} / {total}")
                                        self.failed_label.config(text=f"Failed: {failed}")
                                    except Exception as e:
                                        logging.debug(f"Error updating tile progress: {e}")
                                
                                if self._is_window_valid():
                                    try:
                                        self.root.after(0, _update_tile)
                                    except Exception:
                                        pass
                            
                            elif msg['type'] == 'satellite':
                                def _add_satellite():
                                    if not self._is_window_valid():
                                        return
                                    try:
                                        satellite = msg['satellite']
                                        detailed_stats = msg.get('stats')
                                        if satellite:
                                            with self._lock:
                                                self.satellite_counts[satellite] = self.satellite_counts.get(satellite, 0) + 1
                                                if detailed_stats:
                                                    if satellite not in self.satellite_stats:
                                                        self.satellite_stats[satellite] = detailed_stats
                                                    elif detailed_stats.get("quality_score", 0) > self.satellite_stats[satellite].get("quality_score", 0):
                                                        self.satellite_stats[satellite] = detailed_stats
                                    except Exception as e:
                                        logging.debug(f"Error adding satellite: {e}")
                                
                                if self._is_window_valid():
                                    try:
                                        self.root.after(0, _add_satellite)
                                    except Exception:
                                        pass
                            
                            elif msg['type'] == 'test_result':
                                test_result = msg['result']
                                if test_result:
                                    with self._lock:
                                        self.all_test_results.append(test_result)
                            
                            elif msg['type'] == 'processing_time':
                                processing_time = msg['time']
                                if processing_time and processing_time > 0:
                                    with self._lock:
                                        self.processing_times.append(processing_time)
                                        if len(self.processing_times) > 100:
                                            self.processing_times.pop(0)
                    
                    except queue.Empty:
                        pass
                    
                    # Schedule UI update (must be done in main thread via root.after)
                    # Fix: Only schedule if not already scheduled to prevent accumulation
                    if self._is_window_valid():
                        try:
                            # Cancel any pending update_ui calls to prevent accumulation
                            if hasattr(self, '_update_ui_scheduled'):
                                try:
                                    self.root.after_cancel(self._update_ui_scheduled)
                                except (tk.TclError, AttributeError):
                                    pass
                            self._update_ui_scheduled = self.root.after(0, self.update_ui)
                        except Exception:
                            pass
                    
                    consecutive_errors = 0  # Reset error counter on success
                    time.sleep(0.5)  # Update every 500ms
                    
                except Exception as e:
                    consecutive_errors += 1
                    logging.debug(f"Error in progress window update loop: {e}")
                    if consecutive_errors >= max_errors:
                        logging.error(f"Progress window update loop failed {max_errors} times, stopping")
                        break
                    time.sleep(1)
        finally:
            # Fix: Mark thread as dead
            with self._lock:
                self._update_thread_alive = False
    
    def update_ui(self):
        """Update UI elements (called from main thread via root.after)."""
        # Fix: Clear scheduled flag
        if hasattr(self, '_update_ui_scheduled'):
            self._update_ui_scheduled = None
        
        if not self._is_window_valid():
            return
        
        try:
            # Calculate elapsed time (excluding pause time)
            current_time = time.time()
            with self._lock:
                if self.paused and self.pause_start_time:
                    elapsed = (self.pause_start_time - self.start_time) - self.total_pause_time
                else:
                    elapsed = (current_time - self.start_time) - self.total_pause_time
                processing_times = self.processing_times.copy()
                processed_tiles = self.processed_tiles
                total_tiles = self.total_tiles
                current_month = self.current_month
                total_months = self.total_months
            
            self.elapsed_label.config(text=f"Elapsed: {self.format_time(elapsed)}")
            
            # Fix: Division by zero - add check
            # Calculate remaining time using dynamic recent performance
            # This adapts to current throughput and accounts for worker scaling changes
            remaining_tiles = max(0, total_tiles - processed_tiles)
            
            with self._lock:
                recent_completions = list(self.recent_completions)  # Copy for thread safety
            
            if remaining_tiles > 0 and len(recent_completions) >= 2:
                # Use recent completions for dynamic calculation (accounts for current worker count)
                recent_window = recent_completions[-self.recent_window_size:]
                if len(recent_window) >= 2:
                    time_span = recent_window[-1][0] - recent_window[0][0]
                    tiles_completed = recent_window[-1][1] - recent_window[0][1]
                    
                    if time_span > 0 and tiles_completed > 0:
                        # Recent throughput: tiles per second
                        recent_tiles_per_second = tiles_completed / time_span
                        remaining_seconds = remaining_tiles / recent_tiles_per_second
                    else:
                        # Fallback to overall average
                        if processed_tiles > 0 and elapsed > 0:
                            effective_time_per_tile = elapsed / processed_tiles
                            remaining_seconds = remaining_tiles * effective_time_per_tile
                        else:
                            remaining_seconds = 0
                else:
                    # Not enough recent data, use overall average
                    if processed_tiles > 0 and elapsed > 0:
                        effective_time_per_tile = elapsed / processed_tiles
                        remaining_seconds = remaining_tiles * effective_time_per_tile
                    else:
                        remaining_seconds = 0
            elif processed_tiles > 0 and elapsed > 0:
                # Fallback to overall average when not enough recent data
                effective_time_per_tile = elapsed / processed_tiles
                remaining_seconds = remaining_tiles * effective_time_per_tile
            else:
                remaining_seconds = 0
            
            # Update countdown
            countdown_str = self.format_time(remaining_seconds)
            self.countdown_label.config(text=f"Time Remaining: {countdown_str}")
            
            # Color code countdown
            if remaining_seconds > 0:
                if remaining_seconds < 1800:  # Less than 30 minutes
                    self.countdown_label.config(foreground="red")
                elif remaining_seconds < 3600:  # Less than 1 hour
                    self.countdown_label.config(foreground="orange")
                else:
                    self.countdown_label.config(foreground="black")
            
            # Update satellite display periodically
            if int(time.time()) % 2 == 0:  # Every 2 seconds
                self._update_satellite_display_safe()
            
            # Update project progress (overall across all months)
            if total_months > 0:
                month_progress = (current_month / total_months) * 100
                # Fix: Division by zero check
                tile_progress = (processed_tiles / max(1, total_tiles)) * 100 if total_tiles > 0 else 0
                overall_progress = (month_progress + tile_progress) / 2.0  # Average of month and tile progress
                self.update_project_progress(overall_progress)
        except Exception as e:
            logging.debug(f"Error updating UI: {e}")
    
    def on_close(self):
        """Handle window close (thread-safe)."""
        with self._lock:
            if self._destroying:
                return
            self._destroying = True
            self._closed = True
        
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception as e:
            logging.debug(f"Error closing window: {e}")
        finally:
            self._cleanup()
    
    def wait_for_pause(self):
        """Wait if paused (called from processing thread)."""
        # Fix: Add timeout to prevent infinite blocking
        max_wait_time = 3600  # 1 hour max wait
        start_wait = time.time()
        
        while True:
            with self._lock:
                # Fix: Check closed first, then paused
                if self._closed:
                    break
                if not self.paused:
                    break
                # Check timeout
                if time.time() - start_wait > max_wait_time:
                    logging.warning("wait_for_pause() timeout exceeded, continuing anyway")
                    break
            time.sleep(0.1)
    
    def run(self):
        """Run the window using mainloop with scheduled updates (fixes threading issue)."""
        # Fix: Tkinter requires GUI operations in the main thread
        # Use root.after() to schedule updates instead of root.update() from background thread
        # This method should ideally run in main thread, but we'll use after() for thread-safe updates
        
        # Fix: Ensure window is visible when run starts
        try:
            # Make window visible and bring to front
            self.root.deiconify()
            self.root.lift()
            self.root.attributes('-topmost', True)  # Temporarily bring to top
            self.root.attributes('-topmost', False)  # Then allow normal stacking
            self.root.focus_force()
            # Process events to ensure window is rendered
            self.root.update_idletasks()
            logging.info("Progress window initialized and should be visible")
        except Exception as e:
            logging.error(f"Error showing window initially: {e}")
        
        # Schedule periodic UI updates using root.after() (thread-safe)
        self._schedule_update()
        
        try:
            # Run mainloop - this processes events and scheduled callbacks
            self.root.mainloop()
        except Exception as e:
            logging.error(f"Error in progress window mainloop: {e}")
        finally:
            self._cleanup()
    
    def _schedule_update(self):
        """Schedule the next UI update (thread-safe via root.after())."""
        try:
            with self._lock:
                if self._closed:
                    return
            
            # Update UI elements
            if self._is_window_valid():
                self.update_ui()
                # Schedule next update in 100ms (10 FPS) - this is thread-safe
                self.root.after(100, self._schedule_update)
        except tk.TclError:
            # Window was destroyed
            pass
        except Exception as e:
            logging.debug(f"Error in scheduled update: {e}")
            # Try to continue scheduling updates if window is still valid
            try:
                if self._is_window_valid():
                    self.root.after(100, self._schedule_update)
            except Exception:
                pass
    
    def _cleanup(self):
        """Clean up resources."""
        with self._lock:
            self._closed = True
            self._destroying = True
            self._update_thread_alive = False
        
        # Fix: Cancel any pending UI updates
        try:
            if hasattr(self, '_update_ui_scheduled') and self._update_ui_scheduled is not None:
                try:
                    if self.root.winfo_exists():
                        self.root.after_cancel(self._update_ui_scheduled)
                except (tk.TclError, AttributeError):
                    pass
                self._update_ui_scheduled = None
        except Exception:
            pass
        
        # Clear message queue to prevent memory leak
        try:
            while True:
                self.message_queue.get_nowait()
        except queue.Empty:
            pass
    
    def destroy(self):
        """Destroy the window (thread-safe)."""
        with self._lock:
            if self._destroying:
                return
            self._destroying = True
            self._closed = True
        
        def _destroy():
            try:
                if self.root.winfo_exists():
                    self.root.destroy()
            except Exception:
                pass
        
        try:
            if self.root.winfo_exists():
                self.root.after(0, _destroy)
        except Exception:
            pass
        
        self._cleanup()

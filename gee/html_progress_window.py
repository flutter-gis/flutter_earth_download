"""
HTML-based progress window that writes a static HTML file that auto-refreshes.
No server needed - just file I/O.
"""
import os
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging


class HTMLProgressWindow:
    """HTML-based progress monitoring that writes a static HTML file."""
    
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="2">
    <title>Mosaic Processing Progress</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 30px;
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
            text-align: center;
            font-size: 28px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }
        .stat-value.warning { color: #ff9800; }
        .stat-value.error { color: #f44336; }
        .stat-value.success { color: #4caf50; }
        .progress-section {
            margin-bottom: 25px;
        }
        .progress-label {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        .progress-bar-container {
            background: #e0e0e0;
            border-radius: 10px;
            height: 30px;
            overflow: hidden;
            position: relative;
        }
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
        }
        .two-column {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (max-width: 768px) {
            .two-column {
                grid-template-columns: 1fr;
            }
        }
        .panel {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            border: 1px solid #e0e0e0;
        }
        .panel-title {
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
            font-size: 16px;
        }
        #console {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 15px;
            border-radius: 5px;
            height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        #satellite-usage {
            background: white;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            padding: 10px;
            border-radius: 5px;
            height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
        }
        .console-line {
            margin: 2px 0;
        }
        .console-line.info { color: #d4d4d4; }
        .console-line.success { color: #4ec9b0; }
        .console-line.error { color: #f48771; }
        .console-line.warning { color: #dcdcaa; }
        .paused {
            opacity: 0.6;
        }
        .paused::after {
            content: " (PAUSED)";
            color: #ff9800;
            font-weight: bold;
        }
        .refresh-info {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Mosaic Processing Progress</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Processed Tiles</div>
                <div class="stat-value" id="processed">{{PROCESSED_TILES}} / {{TOTAL_TILES}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Failed Tiles</div>
                <div class="stat-value error" id="failed">{{FAILED_TILES}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Time Remaining</div>
                <div class="stat-value {{COUNTDOWN_CLASS}}" id="countdown">{{COUNTDOWN}}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Elapsed Time</div>
                <div class="stat-value" id="elapsed">{{ELAPSED}}</div>
            </div>
        </div>
        
        <div class="progress-section">
            <div class="progress-label">
                <span>Tile Progress</span>
                <span id="tile-progress-text">{{TILE_PERCENT}}% ({{PROCESSED_TILES}}/{{TOTAL_TILES}} tiles)</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" id="tile-progress" style="width: {{TILE_PERCENT}}%">{{TILE_PERCENT}}%</div>
            </div>
        </div>
        
        <div class="progress-section">
            <div class="progress-label">
                <span>Mosaic Progress (Current Month)</span>
                <span id="mosaic-progress-text">{{MOSAIC_PERCENT}}% (Month {{CURRENT_MONTH}}/{{TOTAL_MONTHS}})</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" id="mosaic-progress" style="width: {{MOSAIC_PERCENT}}%">{{MOSAIC_PERCENT}}%</div>
            </div>
        </div>
        
        <div class="progress-section">
            <div class="progress-label">
                <span>Full Project Progress</span>
                <span id="project-progress-text">{{PROJECT_PERCENT}}%</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" id="project-progress" style="width: {{PROJECT_PERCENT}}%">{{PROJECT_PERCENT}}%</div>
            </div>
        </div>
        
        <div class="two-column">
            <div class="panel">
                <div class="panel-title">Console Output</div>
                <div id="console">{{CONSOLE_OUTPUT}}</div>
            </div>
            <div class="panel">
                <div class="panel-title">Satellite Usage</div>
                <div id="satellite-usage">{{SATELLITE_OUTPUT}}</div>
            </div>
        </div>
        
        <div class="refresh-info">
            Page auto-refreshes every 2 seconds | Last updated: {{LAST_UPDATED}}
        </div>
    </div>
</body>
</html>"""
    
    def __init__(self, total_tiles: int, total_months: int = 1, output_file: str = "progress.html"):
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
        self.console_messages = []
        self.max_console_messages = 1000
        self.output_file = output_file
        self._lock = threading.Lock()
        self._closed = False
        # Track recent tile completions for dynamic throughput calculation
        # Each entry is (timestamp, tile_count) - tracks when tiles were completed
        self.recent_completions = []  # Sliding window of (timestamp, count) tuples
        self.recent_window_size = 30  # Use last 30 tiles for dynamic calculation
        
        # Write initial HTML file
        self._update_html()
        logging.info(f"HTML progress window created: {os.path.abspath(self.output_file)}")
        print(f"Progress dashboard: {os.path.abspath(self.output_file)}", flush=True)
        
        # Try to open in browser
        try:
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(self.output_file)}")
            logging.info("Browser opened automatically")
        except Exception as e:
            logging.debug(f"Could not open browser automatically: {e}")
    
    def _format_time(self, seconds: float) -> str:
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
    
    def _update_html(self):
        """Update the HTML file with current data."""
        try:
            with self._lock:
                if self._closed:
                    return
                
                # Force immediate write by opening file in write mode and closing
                # This ensures the file is updated on disk for browser refresh
                
                current_time = time.time()
                if self.paused and self.pause_start_time:
                    elapsed = (self.pause_start_time - self.start_time) - self.total_pause_time
                else:
                    elapsed = (current_time - self.start_time) - self.total_pause_time
                
                # Calculate remaining time using dynamic recent performance
                # This adapts to current throughput and accounts for worker scaling changes
                remaining_tiles = max(0, self.total_tiles - self.processed_tiles)
                
                if remaining_tiles > 0 and len(self.recent_completions) >= 2:
                    # Use recent completions for dynamic calculation (accounts for current worker count)
                    recent_window = self.recent_completions[-self.recent_window_size:]
                    if len(recent_window) >= 2:
                        time_span = recent_window[-1][0] - recent_window[0][0]
                        tiles_completed = recent_window[-1][1] - recent_window[0][1]
                        
                        if time_span > 0 and tiles_completed > 0:
                            # Recent throughput: tiles per second
                            recent_tiles_per_second = tiles_completed / time_span
                            remaining_seconds = remaining_tiles / recent_tiles_per_second
                        else:
                            # Fallback to overall average
                            if self.processed_tiles > 0 and elapsed > 0:
                                effective_time_per_tile = elapsed / self.processed_tiles
                                remaining_seconds = remaining_tiles * effective_time_per_tile
                            else:
                                remaining_seconds = 0
                    else:
                        # Not enough recent data, use overall average
                        if self.processed_tiles > 0 and elapsed > 0:
                            effective_time_per_tile = elapsed / self.processed_tiles
                            remaining_seconds = remaining_tiles * effective_time_per_tile
                        else:
                            remaining_seconds = 0
                elif self.processed_tiles > 0 and elapsed > 0:
                    # Fallback to overall average when not enough recent data
                    effective_time_per_tile = elapsed / self.processed_tiles
                    remaining_seconds = remaining_tiles * effective_time_per_tile
                else:
                    remaining_seconds = 0
                
                # Calculate percentages
                tile_percent = int((self.processed_tiles / max(1, self.total_tiles)) * 100) if self.total_tiles > 0 else 0
                mosaic_percent = int((self.current_month / max(1, self.total_months)) * 100) if self.total_months > 0 else 0
                
                if self.total_months > 0:
                    month_progress = (self.current_month / self.total_months) * 100
                    tile_progress = (self.processed_tiles / max(1, self.total_tiles)) * 100 if self.total_tiles > 0 else 0
                    project_percent = int((month_progress + tile_progress) / 2.0)
                else:
                    project_percent = 0
                
                # Countdown color class
                if remaining_seconds < 1800:
                    countdown_class = "error"
                elif remaining_seconds < 3600:
                    countdown_class = "warning"
                else:
                    countdown_class = ""
                
                # Format console output
                console_html = ""
                for msg in self.console_messages[-500:]:  # Last 500 messages
                    level = msg.get('level', 'info').lower()
                    timestamp = msg.get('timestamp', '')
                    message = msg.get('message', '')
                    console_html += f'<div class="console-line {level}">[{timestamp}] {message}</div>\n'
                
                if not console_html:
                    console_html = '<div class="console-line info">Waiting for processing to start...</div>'
                
                # Format satellite output
                if self.satellite_counts:
                    sat_text = "Satellite Usage:\n"
                    sat_text += "-" * 80 + "\n"
                    sorted_sats = sorted(self.satellite_counts.items(), key=lambda x: x[1], reverse=True)
                    for sat, count in sorted_sats:
                        stats = self.satellite_stats.get(sat, {})
                        quality = stats.get('quality_score', 0.0)
                        cloud_frac = stats.get('cloud_fraction', 0.0) * 100
                        resolution = stats.get('native_resolution', 'N/A')
                        sat_text += f"{sat:25s} | Tiles: {count:3d} | Quality: {quality:.3f} | "
                        sat_text += f"Clouds: {cloud_frac:.1f}% | Res: {resolution}\n"
                    satellite_output = sat_text
                else:
                    satellite_output = "No satellite data yet..."
                
                # Replace template variables
                html = self.HTML_TEMPLATE
                html = html.replace("{{PROCESSED_TILES}}", str(self.processed_tiles))
                html = html.replace("{{TOTAL_TILES}}", str(self.total_tiles))
                html = html.replace("{{FAILED_TILES}}", str(self.failed_tiles))
                html = html.replace("{{COUNTDOWN}}", self._format_time(remaining_seconds))
                html = html.replace("{{COUNTDOWN_CLASS}}", countdown_class)
                html = html.replace("{{ELAPSED}}", self._format_time(elapsed))
                html = html.replace("{{TILE_PERCENT}}", str(tile_percent))
                html = html.replace("{{MOSAIC_PERCENT}}", str(mosaic_percent))
                html = html.replace("{{PROJECT_PERCENT}}", str(project_percent))
                html = html.replace("{{CURRENT_MONTH}}", str(self.current_month))
                html = html.replace("{{TOTAL_MONTHS}}", str(self.total_months))
                html = html.replace("{{CONSOLE_OUTPUT}}", console_html)
                html = html.replace("{{SATELLITE_OUTPUT}}", satellite_output.replace('\n', '<br>'))
                html = html.replace("{{LAST_UPDATED}}", datetime.now().strftime("%H:%M:%S"))
                
                # Write HTML file with explicit flush
                try:
                    with open(self.output_file, 'w', encoding='utf-8') as f:
                        f.write(html)
                        f.flush()  # Force write to disk immediately
                        os.fsync(f.fileno())  # Ensure OS writes to disk
                except Exception as write_error:
                    logging.error(f"Error writing HTML file: {write_error}")
                    
        except Exception as e:
            logging.error(f"Error updating HTML file: {e}")
    
    def is_alive(self) -> bool:
        """Check if window is alive."""
        with self._lock:
            return not self._closed
    
    def add_console_message(self, message: str, level: str = "INFO"):
        """Add message to console output."""
        with self._lock:
            if self._closed:
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
            
            if level in status_to_level:
                level = status_to_level[level]
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.console_messages.append({
                'timestamp': timestamp,
                'message': message,
                'level': level
            })
            
            # Keep only recent messages
            if len(self.console_messages) > self.max_console_messages:
                self.console_messages = self.console_messages[-self.max_console_messages:]
            
            # Update HTML file
            self._update_html()
    
    def update_tile_progress(self, processed: int, failed: int = 0):
        """Update tile progress."""
        with self._lock:
            if not self._closed:
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
                self._update_html()
    
    def update_mosaic_progress(self, month: int, total_months: int):
        """Update mosaic progress."""
        with self._lock:
            if not self._closed:
                self.current_month = month
                self.total_months = total_months
                self._update_html()
    
    def update_project_progress(self, overall_percent: float):
        """Update full project progress."""
        # This is calculated in _update_html
        self._update_html()
    
    def add_satellite(self, satellite: str, detailed_stats: Dict = None):
        """Add satellite usage."""
        with self._lock:
            if not self._closed and satellite:
                self.satellite_counts[satellite] = self.satellite_counts.get(satellite, 0) + 1
                if detailed_stats:
                    if satellite not in self.satellite_stats:
                        self.satellite_stats[satellite] = detailed_stats
                    elif detailed_stats.get("quality_score", 0) > self.satellite_stats[satellite].get("quality_score", 0):
                        self.satellite_stats[satellite] = detailed_stats
                self._update_html()
    
    def add_test_result(self, test_result: Dict):
        """Add test result."""
        # Not used in HTML version
        pass
    
    def add_processing_time(self, processing_time: float):
        """Add processing time for countdown estimation."""
        with self._lock:
            if not self._closed and processing_time and processing_time > 0:
                self.processing_times.append(processing_time)
                if len(self.processing_times) > 100:
                    self.processing_times.pop(0)
                self._update_html()
    
    def toggle_pause(self):
        """Toggle pause state."""
        with self._lock:
            if self.paused:
                # Resume
                if self.pause_start_time:
                    self.total_pause_time += time.time() - self.pause_start_time
                    self.pause_start_time = None
                self.paused = False
            else:
                # Pause
                self.paused = True
                self.pause_start_time = time.time()
            self._update_html()
    
    def wait_for_pause(self):
        """Wait if paused."""
        while True:
            with self._lock:
                if self._closed:
                    break
                if not self.paused:
                    break
            time.sleep(0.1)
    
    def destroy(self):
        """Close the window."""
        with self._lock:
            self._closed = True
            # Write final update
            self._update_html()
    
    @property
    def closed(self) -> bool:
        """Check if window is closed."""
        with self._lock:
            return self._closed
    
    def is_alive(self) -> bool:
        """Check if the progress window is still alive (not closed)."""
        return not self.closed

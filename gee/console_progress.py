"""
Console-based progress display with tables and frequent updates.
"""
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging


class ConsoleProgress:
    """Console-based progress monitoring with table displays."""
    
    def __init__(self, total_tiles: int, total_months: int = 1):
        self.total_tiles = total_tiles
        self.total_months = total_months
        self.current_month = 0
        self.processed_tiles = 0
        self.failed_tiles = 0
        self.start_time = time.time()
        self.processing_times = []
        self.satellite_counts = {}
        self.satellite_stats = {}
        self.last_update_time = 0
        self.update_interval = 2.0  # Update every 2 seconds for frequent updates
        # Track recent tile completions for dynamic throughput calculation
        # Each entry is (timestamp, tile_count) - tracks when tiles were completed
        self.recent_completions = []  # Sliding window of (timestamp, count) tuples
        self.last_completion_count = 0  # Track tile count at last completion
        self.recent_window_size = 30  # Use last 30 tiles for dynamic calculation
        
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        if seconds <= 0 or not isinstance(seconds, (int, float)) or not (seconds < 1e10):
            return "--:--:--"
        try:
            td = timedelta(seconds=int(seconds))
            hours, remainder = divmod(td.seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes:02d}:{secs:02d}"
        except Exception:
            return "--:--:--"
    
    def _should_update(self) -> bool:
        """Check if enough time has passed for an update."""
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_interval:
            self.last_update_time = current_time
            return True
        return False
    
    def _print_progress_table(self):
        """Print a formatted progress table to console."""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Calculate remaining time using dynamic recent performance
        # This adapts to current throughput and accounts for worker scaling changes
        remaining_tiles = max(0, self.total_tiles - self.processed_tiles)
        
        if remaining_tiles > 0 and len(self.recent_completions) >= 2:
            # Use recent completions for dynamic calculation (accounts for current worker count)
            # Get the time window for recent completions
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
        tile_percent = (self.processed_tiles / max(1, self.total_tiles)) * 100 if self.total_tiles > 0 else 0
        mosaic_percent = (self.current_month / max(1, self.total_months)) * 100 if self.total_months > 0 else 0
        
        # Print separator and table (Windows-friendly, no cursor movement)
        print("\n" + "=" * 80)
        print(f"  FLUTTER EARTH PROGRESS DASHBOARD  |  {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 80)
        print()
        
        # Progress Summary Table
        print("📊 PROGRESS SUMMARY")
        print("-" * 80)
        print(f"  Tiles Processed:     {self.processed_tiles:5d} / {self.total_tiles:5d}  ({tile_percent:5.1f}%)")
        print(f"  Failed Tiles:        {self.failed_tiles:5d}")
        print(f"  Current Month:       {self.current_month:5d} / {self.total_months:5d}  ({mosaic_percent:5.1f}%)")
        print(f"  Elapsed Time:        {self._format_time(elapsed)}")
        print(f"  Estimated Remaining: {self._format_time(remaining_seconds)}")
        print()
        
        # Satellite Usage Table
        if self.satellite_stats:
            print("🛰️  SATELLITE USAGE & QUALITY SCORES")
            print("-" * 80)
            print(f"  {'Satellite':<25} {'Tiles':>8} {'Quality':>10} {'Clouds':>10} {'Resolution':>12}")
            print("-" * 80)
            
            # Sort by tile count (descending)
            sorted_sats = sorted(self.satellite_counts.items(), key=lambda x: x[1], reverse=True)
            for sat, count in sorted_sats[:10]:  # Top 10
                stats = self.satellite_stats.get(sat, {})
                quality = stats.get('quality_score', 0.0)
                cloud_frac = stats.get('cloud_fraction', 0.0) * 100
                resolution = stats.get('native_resolution', 'N/A')
                if isinstance(resolution, (int, float)):
                    resolution = f"{resolution:.0f}m"
                
                print(f"  {sat:<25} {count:>8} {quality:>9.3f}  {cloud_frac:>8.1f}%  {resolution:>12}")
            print()
        
        # Performance Stats
        if self.processing_times:
            avg_time = sum(self.processing_times) / len(self.processing_times)
            min_time = min(self.processing_times)
            max_time = max(self.processing_times)
            print("⚡ PERFORMANCE STATISTICS")
            print("-" * 80)
            print(f"  Avg Time/Tile (per-worker): {avg_time:.2f} seconds")
            print(f"  Fastest Tile:        {min_time:.2f} seconds")
            print(f"  Slowest Tile:        {max_time:.2f} seconds")
            # Use effective throughput (elapsed time / processed) which accounts for parallel workers
            if self.processed_tiles > 0 and elapsed > 0:
                effective_time_per_tile = elapsed / self.processed_tiles
                effective_tiles_per_hour = 3600 / effective_time_per_tile
                print(f"  Effective Tiles/Hour:  {effective_tiles_per_hour:.1f} (accounts for parallel workers)")
            else:
                print(f"  Effective Tiles/Hour:  N/A")
            print()
        
        print("=" * 80 + "\n")
        sys.stdout.flush()
    
    def update_tile_progress(self, processed: int, failed: int = 0):
        """Update tile progress."""
        # Track completion timestamps for dynamic throughput calculation
        if processed > self.processed_tiles:
            current_time = time.time()
            tiles_added = processed - self.processed_tiles
            # Add new completion entry
            self.recent_completions.append((current_time, processed))
            # Keep only recent window
            if len(self.recent_completions) > self.recent_window_size * 2:
                # Keep last window_size entries plus first entry for span calculation
                self.recent_completions = [self.recent_completions[0]] + self.recent_completions[-self.recent_window_size:]
        
        self.processed_tiles = processed
        self.failed_tiles = failed
        # Always update table when progress changes (frequent updates)
        self._print_progress_table()
    
    def update_mosaic_progress(self, month: int, total_months: int):
        """Update mosaic progress."""
        self.current_month = month
        self.total_months = total_months
        if self._should_update():
            self._print_progress_table()
    
    def add_satellite(self, satellite: str, detailed_stats: Dict = None):
        """Add satellite usage."""
        if satellite:
            self.satellite_counts[satellite] = self.satellite_counts.get(satellite, 0) + 1
            if detailed_stats:
                if satellite not in self.satellite_stats:
                    self.satellite_stats[satellite] = detailed_stats
                elif detailed_stats.get("quality_score", 0) > self.satellite_stats[satellite].get("quality_score", 0):
                    self.satellite_stats[satellite] = detailed_stats
            # Update table when satellite data changes
            if self._should_update():
                self._print_progress_table()
    
    def add_processing_time(self, processing_time: float):
        """Add processing time for countdown estimation."""
        if processing_time and processing_time > 0:
            self.processing_times.append(processing_time)
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)
    
    def add_console_message(self, message: str, level: str = "INFO"):
        """Add message (for compatibility, but we print directly)."""
        # Messages are printed directly in progress_callback, so this is mainly for compatibility
        pass
    
    def add_test_result(self, test_result: Dict):
        """Add test result (not used in console version)."""
        pass
    
    def is_alive(self) -> bool:
        """Check if progress display is alive (always True for console)."""
        return True
    
    def wait_for_pause(self):
        """Wait if paused (not implemented for console)."""
        pass
    
    def destroy(self):
        """Finalize progress display."""
        # Print final table
        print("\n" * 3)
        self._print_progress_table()
        print("\n✅ Processing complete!\n")


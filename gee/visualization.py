"""
Visualization helpers for satellite imagery processing.
"""
import os
import json
import logging
import time
import webbrowser
import shutil
from datetime import datetime


class SatelliteHistogram:
    """Lightweight HTML-based histogram showing satellite usage across tiles."""
    def __init__(self, total_tiles: int, output_dir: str):
        self.total_tiles = total_tiles
        self.satellite_counts = {}
        self.satellite_stats = {}  # Track detailed stats per satellite (best score for each)
        self.all_tile_stats = []  # Track ALL tile statistics (every tile, not just best per satellite)
        self.all_test_results = []  # Track ALL test results (every test for every tile)
        self.output_dir = output_dir
        self.json_path = os.path.join(output_dir, "satellite_stats.json")
        self.html_path = os.path.join(output_dir, "satellite_histogram.html")
        self.start_time = time.time()  # Track start time for countdown
        self.processing_times = []  # Track processing times for each tile
        self.processed_tile_indices = set()  # Track unique tile indices that have been processed
        self._create_html_dashboard()
        self.update()
        # Auto-open in browser
        try:
            # Use absolute path and convert to file:// URL format
            abs_path = os.path.abspath(self.html_path)
            # Windows: file:///C:/path/to/file.html (three slashes)
            # Unix: file:///path/to/file.html
            if os.name == 'nt':  # Windows
                file_url = f"file:///{abs_path.replace(os.sep, '/')}"
            else:  # Unix/Mac
                file_url = f"file://{abs_path}"
            webbrowser.open(file_url)
            logging.info(f"Opened satellite histogram dashboard in browser: {self.html_path}")
        except Exception as e:
            logging.warning(f"Could not auto-open browser: {e}. Please manually open: {self.html_path}")
    
    def _create_html_dashboard(self, data=None):
        """Create a lightweight HTML dashboard with Chart.js. Data is embedded directly to work with file:// protocol."""
        if data is None:
            data = {
                "satellite_counts": self.satellite_counts,
                "satellite_stats": self.satellite_stats,
                "all_tile_stats": self.all_tile_stats,
                "all_test_results": self.all_test_results,
                "total_tiles": self.total_tiles,
                "last_update": datetime.utcnow().isoformat()
            }
        
        # Embed data as JSON in the HTML
        data_json = json.dumps(data)
        html_content = """<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="5">
    <title>Satellite Usage Histogram - Real-time</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .stat-box {
            padding: 10px;
            background: #f0f0f0;
            border-radius: 4px;
            min-width: 120px;
        }
        .stat-label {
            color: #666;
            font-size: 12px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }
        #chartContainer {
            position: relative;
            height: 400px;
            margin-top: 20px;
        }
        .auto-refresh {
            color: #666;
            font-size: 12px;
            margin-top: 10px;
        }
        .stats-table {
            margin-top: 30px;
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #2196F3;
            color: white;
            font-weight: bold;
            position: sticky;
            top: 0;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .score-high {
            color: #4CAF50;
            font-weight: bold;
        }
        .score-medium {
            color: #FF9800;
        }
        .score-low {
            color: #F44336;
        }
        .selected-row {
            background-color: #fff9c4 !important;
            border-left: 4px solid #FFC107;
            font-weight: bold;
        }
        .selected-row:hover {
            background-color: #fff59d !important;
        }
        .fallback-row {
            background-color: #e3f2fd !important;
            border-left: 4px solid #2196F3;
        }
        .fallback-row:hover {
            background-color: #bbdefb !important;
        }
        .copy-button {
            margin-top: 10px;
            padding: 10px 20px;
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
        }
        .copy-button:hover {
            background-color: #1976D2;
        }
        .copy-button:active {
            background-color: #0D47A1;
        }
        .copy-success {
            margin-left: 10px;
            color: #4CAF50;
            font-weight: bold;
        }
        #countdown {
            font-family: 'Courier New', monospace;
        }
        .countdown-warning {
            color: #FF9800;
        }
        .countdown-critical {
            color: #F44336;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Satellite Usage in Mosaic</h1>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-label">Processed</div>
                <div class="stat-value" id="processed">0</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Total Tiles</div>
                <div class="stat-value" id="total">0</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Progress</div>
                <div class="stat-value" id="progress">0%</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Time Remaining</div>
                <div class="stat-value" id="countdown">--:--:--</div>
            </div>
        </div>
        <div id="completionMessage" style="display: none; padding: 15px; background: #4CAF50; color: white; border-radius: 4px; margin-bottom: 20px; text-align: center; font-weight: bold;">
            ✅ Mosaic Complete! Histogram saved. Ready for next mosaic...
        </div>
        <div id="chartContainer">
            <canvas id="satelliteChart"></canvas>
        </div>
        <div class="auto-refresh">Auto-refreshing every 1 second...</div>
        <div class="stats-table">
            <h2>All Test Results (Sorted by Tile Number, then Quality Score)</h2>
            <p style="font-size: 12px; color: #666; margin-bottom: 10px;">
                <span style="background-color: #fff9c4; padding: 2px 6px; border-left: 3px solid #FFC107;">* = Primary Selected</span> | 
                <span style="background-color: #e3f2fd; padding: 2px 6px; border-left: 3px solid #2196F3;">** = 2nd Best (Fallback)</span> | 
                <span style="background-color: #e3f2fd; padding: 2px 6px; border-left: 3px solid #2196F3;">*** = 3rd Best (Fallback)</span> | 
                Fallbacks fill masked pixels with real data (not in histogram counts)
            </p>
            <button class="copy-button" onclick="copyTableToClipboard()">📋 Copy Table to Clipboard</button>
            <span id="copySuccess" class="copy-success"></span>
            <div id="statsTableContainer"></div>
        </div>
    </div>
    
    <script>
        // Embedded data (works with file:// protocol)
        // JSON is valid JavaScript, so we can embed it directly
        const embeddedData = """ + data_json + """;
        
        const colors = {
            "Copernicus Sentinel-2": "#1f77b4",
            "Sentinel-2": "#1f77b4",  // Legacy name support
            "Landsat-5": "#ff7f0e",
            "Landsat-7": "#2ca02c",
            "Landsat-8": "#d62728",
            "Landsat-9": "#9467bd",
            "MODIS": "#8c564b",
            "ASTER": "#e377c2",
            "VIIRS": "#7f7f7f"
        };
        
        let chart = null;
        let lastDataHash = null;
        
        function updateChart() {
            // Try to load fresh data using XMLHttpRequest (works better with file://)
            let data = embeddedData; // Start with embedded data
            const xhr = new XMLHttpRequest();
            xhr.open('GET', 'satellite_stats.json?' + new Date().getTime(), true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200 || xhr.status === 0) { // 0 for file:// protocol
                        try {
                            const freshData = JSON.parse(xhr.responseText);
                            const dataHash = JSON.stringify(freshData);
                            if (dataHash !== lastDataHash) {
                                data = freshData;
                                lastDataHash = dataHash;
                                renderChart(data);
                            }
                        } catch(e) {
                            // Fall back to embedded data
                            renderChart(embeddedData);
                        }
                    } else {
                        // Fall back to embedded data
                        renderChart(embeddedData);
                    }
                }
            };
            xhr.send(null);
            
            // Also render with current data immediately
            renderChart(data);
        }
        
        function formatTime(seconds) {
            if (seconds <= 0 || !isFinite(seconds)) return '--:--:--';
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }
        
        function updateCountdown(data) {
            const countdownEl = document.getElementById('countdown');
            const completionMsg = document.getElementById('completionMessage');
            const processed = data.processed_tiles || 0;
            const total = data.total_tiles || 0;
            const remaining = data.estimated_remaining_seconds || 0;
            
            // Check if complete
            if (processed >= total && total > 0) {
                countdownEl.textContent = '00:00:00';
                countdownEl.className = 'stat-value';
                completionMsg.style.display = 'block';
                return;
            }
            
            // Update countdown
            countdownEl.textContent = formatTime(remaining);
            
            // Color coding based on remaining time (warning/critical for less time)
            countdownEl.className = 'stat-value';
            if (remaining > 0 && remaining < 1800) {  // Less than 30 minutes
                countdownEl.classList.add('countdown-critical');
            } else if (remaining > 0 && remaining < 3600) {  // Less than 1 hour
                countdownEl.classList.add('countdown-warning');
            }
            
            completionMsg.style.display = 'none';
        }
        
        function renderChart(data) {
            const satellites = Object.keys(data.satellite_counts || {});
            const counts = satellites.map(sat => data.satellite_counts[sat]);
            const totalProcessed = counts.reduce((a, b) => a + b, 0);
            
            // Update stats
            document.getElementById('processed').textContent = totalProcessed;
            document.getElementById('total').textContent = data.total_tiles || 0;
            const progress = data.total_tiles > 0 ? Math.round((totalProcessed / data.total_tiles) * 100) : 0;
            document.getElementById('progress').textContent = progress + '%';
            
            // Update countdown timer
            updateCountdown(data);
            
            // Render statistics table - show all test results
            renderStatsTable(data.all_test_results || []);
            
            // Update chart
            if (chart) {
                chart.data.labels = satellites;
                chart.data.datasets[0].data = counts;
                chart.data.datasets[0].backgroundColor = satellites.map(sat => colors[sat] || "#17becf");
                chart.update('none'); // 'none' mode for instant updates
            } else {
                // Initialize chart
                const ctx = document.getElementById('satelliteChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: satellites,
                        datasets: [{
                            label: 'Number of Tiles',
                            data: counts,
                            backgroundColor: satellites.map(sat => colors[sat] || "#17becf"),
                            borderColor: '#000',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return context.parsed.y + ' tiles';
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Number of Tiles'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Satellite'
                                }
                            }
                        },
                        animation: {
                            duration: 0 // Instant updates
                        }
                    }
                });
            }
        }
        
        // Store stats array globally for copy function
        let currentStatsArray = [];
        
        function renderStatsTable(stats) {
            const container = document.getElementById('statsTableContainer');
            if (!stats || stats.length === 0) {
                container.innerHTML = '<p>No statistics available yet. Processing tiles...</p>';
                currentStatsArray = [];
                return;
            }
            
            // Sort by tile number first, then by quality_score (highest first)
            currentStatsArray = stats.slice().sort((a, b) => {
                const tileA = a.tile_idx !== null && a.tile_idx !== undefined ? a.tile_idx : -1;
                const tileB = b.tile_idx !== null && b.tile_idx !== undefined ? b.tile_idx : -1;
                if (tileA !== tileB) {
                    return tileA - tileB;  // Sort by tile number ascending
                }
                // If same tile number, sort by quality score descending
                const scoreA = a.quality_score || 0;
                const scoreB = b.quality_score || 0;
                return scoreB - scoreA;
            });
            
            let html = '<table><thead><tr>';
            html += '<th>Satellite</th>';
            html += '<th>Quality Score</th>';
            html += '<th>Tile #</th>';
            html += '<th>Cloud Fraction</th>';
            html += '<th>Resolution (m)</th>';
            html += '<th>Band Completeness</th>';
            html += '</tr></thead><tbody>';
            
            currentStatsArray.forEach(stat => {
                const score = stat.quality_score || 0;
                const scoreClass = score >= 0.7 ? 'score-high' : (score >= 0.4 ? 'score-medium' : 'score-low');
                const tileNum = stat.tile_idx !== null && stat.tile_idx !== undefined ? stat.tile_idx : 'N/A';
                const isSelected = stat.is_selected === true;
                const fallbackRank = stat.is_fallback_rank !== null && stat.is_fallback_rank !== undefined ? stat.is_fallback_rank : null;
                
                // Determine row class: selected (yellow) or fallback (blue)
                let rowClass = '';
                if (isSelected) {
                    rowClass = 'selected-row';  // Primary selected - yellow highlight
                } else if (fallbackRank !== null) {
                    rowClass = 'fallback-row';  // Fallback - blue highlight
                }
                
                // Determine asterisks: * for primary, ** for 2nd, *** for 3rd, etc.
                let asterisk = '';
                if (isSelected) {
                    asterisk = ' *';  // Primary selected
                } else if (fallbackRank !== null) {
                    asterisk = ' ' + '*'.repeat(fallbackRank);  // ** for 2nd, *** for 3rd, etc.
                }
                
                html += `<tr class="${rowClass}">`;
                html += `<td>${stat.satellite || 'Unknown'}${asterisk}</td>`;
                html += `<td class="${scoreClass}">${score.toFixed(3)}</td>`;
                html += `<td>${tileNum}</td>`;
                html += `<td>${(stat.cloud_fraction * 100).toFixed(1)}%</td>`;
                html += `<td>${stat.native_resolution || 'N/A'}</td>`;
                const bandComp = stat.band_completeness !== null && stat.band_completeness !== undefined ? stat.band_completeness : 0.0;
                html += `<td>${(bandComp * 100).toFixed(1)}%</td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        function copyTableToClipboard() {
            if (currentStatsArray.length === 0) {
                showCopyMessage('No data to copy', false);
                return;
            }
            
            // Create CSV-like format
            let csv = 'Satellite,Quality Score,Tile #,Cloud Fraction (%),Resolution (m),Band Completeness (%),Selected\\n';
            
            currentStatsArray.forEach(stat => {
                const tileNum = stat.tile_idx !== null && stat.tile_idx !== undefined ? stat.tile_idx : 'N/A';
                const score = stat.quality_score || 0;
                const cloudFrac = (stat.cloud_fraction * 100).toFixed(1);
                const resolution = stat.native_resolution || 'N/A';
                const bandComp = stat.band_completeness !== null && stat.band_completeness !== undefined ? (stat.band_completeness * 100).toFixed(1) : '0.0';
                const selected = stat.is_selected === true ? 'Yes' : 'No';
                const asterisk = stat.is_selected === true ? ' *' : '';
                
                csv += (stat.satellite || 'Unknown') + asterisk + ',' + score.toFixed(3) + ',' + tileNum + ',' + cloudFrac + ',' + resolution + ',' + bandComp + ',' + selected + '\\n';
            });
            
            // Copy to clipboard
            navigator.clipboard.writeText(csv).then(() => {
                showCopyMessage('✓ Copied to clipboard!', true);
            }).catch(err => {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = csv;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                    showCopyMessage('✓ Copied to clipboard!', true);
                } catch (err) {
                    showCopyMessage('✗ Copy failed', false);
                }
                document.body.removeChild(textArea);
            });
        }
        
        function showCopyMessage(message, success) {
            const successEl = document.getElementById('copySuccess');
            successEl.textContent = message;
            successEl.style.color = success ? '#4CAF50' : '#F44336';
            setTimeout(() => {
                successEl.textContent = '';
            }, 3000);
        }
        
        // Update immediately and then every 1 second
        updateChart();
        setInterval(updateChart, 1000);
        
        // Check for completion and auto-reset if needed
        function checkForCompletion() {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', 'satellite_stats.json?' + new Date().getTime(), true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4 && (xhr.status === 200 || xhr.status === 0)) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        const processed = data.processed_tiles || 0;
                        const total = data.total_tiles || 0;
                        
                        // If complete, wait 5 seconds then reset for next mosaic
                        if (processed >= total && total > 0) {
                            setTimeout(() => {
                                // Reset page by reloading (will show new data when next mosaic starts)
                                location.reload();
                            }, 5000);
                        }
                    } catch(e) {
                        // Ignore errors
                    }
                }
            };
            xhr.send(null);
        }
        
        // Check for completion every 5 seconds
        setInterval(checkForCompletion, 5000);
    </script>
</body>
</html>"""
        with open(self.html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def add_test_result(self, test_result: dict):
        """Add a test result (all tests for all tiles)."""
        if test_result:
            self.all_test_results.append(test_result)
            self.update()
    
    def add_satellite(self, satellite: str, detailed_stats: dict = None, tile_idx: int = None, processing_time: float = None):
        """Add a satellite to the count and track detailed statistics."""
        if satellite:
            self.satellite_counts[satellite] = self.satellite_counts.get(satellite, 0) + 1
            # Track unique processed tiles
            if tile_idx is not None:
                self.processed_tile_indices.add(tile_idx)
            # Track processing time for countdown estimation (only use actual measured times)
            if processing_time is not None and processing_time > 0:
                self.processing_times.append(processing_time)
                # Keep only last 100 processing times for rolling average
                if len(self.processing_times) > 100:
                    self.processing_times.pop(0)
            # Track best detailed stats for each satellite (highest quality score)
            if detailed_stats:
                if satellite not in self.satellite_stats:
                    self.satellite_stats[satellite] = detailed_stats
                elif detailed_stats.get("quality_score", 0) > self.satellite_stats[satellite].get("quality_score", 0):
                    self.satellite_stats[satellite] = detailed_stats
                
                # Track ALL tile statistics (every tile, not just best per satellite)
                if tile_idx is not None:
                    tile_stat = detailed_stats.copy()
                    tile_stat["tile_idx"] = tile_idx
                    self.all_tile_stats.append(tile_stat)
            self.update()
    
    def update(self):
        """Update the JSON file and regenerate HTML with fresh embedded data."""
        try:
            # Use unique tile indices for accurate processed count (not satellite counts)
            processed_count = len(self.processed_tile_indices)
            current_time = time.time()
            elapsed_time = current_time - self.start_time
            
            # Calculate average processing time per tile
            # Prefer actual measured processing times over elapsed/processed ratio
            avg_time_per_tile = 0.0
            if self.processing_times and len(self.processing_times) > 0:
                # Use rolling average of actual processing times
                avg_time_per_tile = sum(self.processing_times) / len(self.processing_times)
            elif processed_count > 0:
                # Fallback: estimate from total elapsed time
                avg_time_per_tile = elapsed_time / processed_count
            
            # Estimate remaining time
            remaining_tiles = max(0, self.total_tiles - processed_count)
            estimated_remaining_seconds = remaining_tiles * avg_time_per_tile if avg_time_per_tile > 0 else 0
            
            stats = {
                "satellite_counts": self.satellite_counts,
                "satellite_stats": self.satellite_stats,
                "all_tile_stats": self.all_tile_stats,
                "all_test_results": self.all_test_results,
                "total_tiles": self.total_tiles,
                "processed_tiles": processed_count,
                "elapsed_time": elapsed_time,
                "estimated_remaining_seconds": estimated_remaining_seconds,
                "avg_time_per_tile": avg_time_per_tile,
                "start_time": self.start_time,
                "last_update": datetime.utcnow().isoformat()
            }
            # Update JSON file
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
            # Regenerate HTML with fresh embedded data (ensures it works even if XMLHttpRequest fails)
            self._create_html_dashboard(stats)
        except Exception as e:
            logging.debug(f"Error updating histogram: {e}")
    
    def save(self, filepath: str):
        """Save final snapshot and archive it with timestamp."""
        self.update()  # Final update
        
        # Archive the histogram with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_json = os.path.join(self.output_dir, f"satellite_stats_{timestamp}.json")
        archived_html = os.path.join(self.output_dir, f"satellite_histogram_{timestamp}.html")
        
        try:
            # Copy JSON and HTML to archived versions
            if os.path.exists(self.json_path):
                shutil.copy2(self.json_path, archived_json)
            if os.path.exists(self.html_path):
                shutil.copy2(self.html_path, archived_html)
            logging.info("Archived histogram: %s, %s", archived_json, archived_html)
        except Exception as e:
            logging.warning("Could not archive histogram: %s", e)
        
        logging.info("Satellite histogram data saved to %s", self.json_path)
        logging.info("Open %s in your browser to view the histogram", self.html_path)

    def close(self):
        """Final update before closing."""
        self.update()
    
    def reset(self, total_tiles: int):
        """Reset histogram for next mosaic."""
        self.total_tiles = total_tiles
        self.satellite_counts = {}
        self.satellite_stats = {}
        self.all_tile_stats = []
        self.all_test_results = []
        self.start_time = time.time()
        self.processing_times = []
        self.processed_tile_indices = set()
        self.update()


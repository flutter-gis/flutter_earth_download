"""
Visualization helpers for satellite imagery processing.
"""
import os
import json
import logging
import webbrowser
from datetime import datetime


class SatelliteHistogram:
    """Lightweight HTML-based histogram showing satellite usage across tiles."""
    def __init__(self, total_tiles: int, output_dir: str):
        self.total_tiles = total_tiles
        self.satellite_counts = {}
        self.output_dir = output_dir
        self.json_path = os.path.join(output_dir, "satellite_stats.json")
        self.html_path = os.path.join(output_dir, "satellite_histogram.html")
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
        </div>
        <div id="chartContainer">
            <canvas id="satelliteChart"></canvas>
        </div>
        <div class="auto-refresh">Auto-refreshing every 1 second...</div>
    </div>
    
    <script>
        // Embedded data (works with file:// protocol)
        // JSON is valid JavaScript, so we can embed it directly
        const embeddedData = """ + data_json + """;
        
        const colors = {
            "Sentinel-2": "#1f77b4",
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
        
        function renderChart(data) {
            const satellites = Object.keys(data.satellite_counts || {});
            const counts = satellites.map(sat => data.satellite_counts[sat]);
            const totalProcessed = counts.reduce((a, b) => a + b, 0);
            
            // Update stats
            document.getElementById('processed').textContent = totalProcessed;
            document.getElementById('total').textContent = data.total_tiles || 0;
            const progress = data.total_tiles > 0 ? Math.round((totalProcessed / data.total_tiles) * 100) : 0;
            document.getElementById('progress').textContent = progress + '%';
            
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
        
        // Update immediately and then every 1 second
        updateChart();
        setInterval(updateChart, 1000);
    </script>
</body>
</html>"""
        with open(self.html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def add_satellite(self, satellite: str):
        """Add a satellite to the count."""
        if satellite:
            self.satellite_counts[satellite] = self.satellite_counts.get(satellite, 0) + 1
            self.update()
    
    def update(self):
        """Update the JSON file and regenerate HTML with fresh embedded data."""
        try:
            stats = {
                "satellite_counts": self.satellite_counts,
                "total_tiles": self.total_tiles,
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
        """Save final snapshot (JSON already saved, just log)."""
        self.update()  # Final update
        logging.info("Satellite histogram data saved to %s", self.json_path)
        logging.info("Open %s in your browser to view the histogram", self.html_path)
    
    def close(self):
        """Final update before closing."""
        self.update()


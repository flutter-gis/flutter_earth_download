"""
Embedded map selector window using tkinter and webview.
"""
import os
import sys
import tempfile
import threading
import http.server
import socketserver
import shutil
import glob
import time
import logging
from typing import Tuple, Optional

try:
    import tkinter as tk
    from tkinter import ttk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

try:
    import webview
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False

try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Module-level flag to track if geometry file monitoring has started
_geometry_monitor_started = False
_geometry_monitor_lock = threading.Lock()


def _get_bbox_files_dir() -> str:
    """
    Get the bbox_files directory path.
    Creates bbox_files folder in the same directory as the main script (where bat file is).
    """
    # Find the project root - same directory as main.py or where script is executed from
    # Try multiple methods to find the correct directory
    project_root = None
    
    # Method 1: Use sys.path[0] which is the directory of the script being run
    if hasattr(sys, 'path') and len(sys.path) > 0:
        script_dir = sys.path[0]
        if os.path.exists(script_dir) and (os.path.exists(os.path.join(script_dir, 'main.py')) or 
                                           os.path.exists(os.path.join(script_dir, 'run_gee.bat'))):
            project_root = script_dir
    
    # Method 2: Go up from this file's location
    if project_root is None:
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)  # gee/
        parent_dir = os.path.dirname(current_dir)    # project root
        if os.path.exists(os.path.join(parent_dir, 'main.py')) or os.path.exists(os.path.join(parent_dir, 'run_gee.bat')):
            project_root = parent_dir
    
    # Method 3: Use current working directory as fallback
    if project_root is None:
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, 'main.py')) or os.path.exists(os.path.join(cwd, 'run_gee.bat')):
            project_root = cwd
        else:
            project_root = cwd  # Fallback to current directory
    
    bbox_dir = os.path.join(project_root, 'bbox_files')
    os.makedirs(bbox_dir, exist_ok=True)
    logging.debug(f"Bbox files directory: {bbox_dir}")
    return bbox_dir


def _get_downloads_bbox_dir() -> str:
    """Get the bbox folder in Downloads directory."""
    try:
        # Get Downloads folder path
        if os.name == 'nt':  # Windows
            downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        else:  # Linux/Mac
            downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        # Create bbox subfolder in Downloads
        bbox_downloads_dir = os.path.join(downloads_path, 'bbox')
        os.makedirs(bbox_downloads_dir, exist_ok=True)
        return bbox_downloads_dir
    except Exception as e:
        logging.warning(f"Could not create bbox folder in Downloads: {e}")
        # Fallback to user's home Downloads
        try:
            downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
            return downloads_path
        except Exception:
            return tempfile.gettempdir()


def _monitor_and_move_geometry_files():
    """Monitor Downloads folder and move geometry*.geojson files to project bbox_files folder."""
    global _geometry_monitor_started
    
    # Only start monitoring once
    with _geometry_monitor_lock:
        if _geometry_monitor_started:
            return
        _geometry_monitor_started = True
    
    def monitor_loop():
        """Background thread that monitors and moves geometry and bbox files."""
        # Get Downloads path - try multiple methods for Windows
        downloads_path = None
        if os.name == 'nt':  # Windows
            # Try common Windows Downloads paths
            user_profile = os.environ.get('USERPROFILE', '')
            if user_profile:
                downloads_path = os.path.join(user_profile, 'Downloads')
            if not downloads_path or not os.path.exists(downloads_path):
                # Fallback to expanduser
                downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        else:
            downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        bbox_dir = _get_bbox_files_dir()  # Project bbox_files folder
        
        logging.info(f"Monitoring Downloads folder for bbox files: {downloads_path}")
        logging.info(f"Target bbox_files folder: {bbox_dir}")
        
        # Track files we've already moved
        moved_files = set()
        
        while True:
            try:
                if not os.path.exists(downloads_path):
                    logging.debug(f"Downloads folder does not exist: {downloads_path}")
                    time.sleep(5)
                    continue
                
                # Look for geometry*.geojson files in Downloads (from shapefile export)
                pattern1 = os.path.join(downloads_path, 'geometry_*.geojson')
                files1 = glob.glob(pattern1)
                
                # Look for bbox_*.geojson files in Downloads (from bbox save)
                pattern2 = os.path.join(downloads_path, 'bbox_*.geojson')
                files2 = glob.glob(pattern2)
                
                # Combine both file types
                files = files1 + files2
                
                if files:
                    logging.info(f"Found {len(files)} potential bbox/geometry files in Downloads: {[os.path.basename(f) for f in files]}")
                else:
                    # Log occasionally to show monitoring is active
                    if int(time.time()) % 10 == 0:  # Log every 10 seconds
                        logging.debug(f"Monitoring Downloads folder (no files found yet): {downloads_path}")
                
                for file_path in files:
                    if file_path not in moved_files:
                        try:
                            # Check if file exists and has content
                            if not os.path.exists(file_path):
                                continue
                                
                            filename = os.path.basename(file_path)
                            dest_path = os.path.join(bbox_dir, filename)
                            
                            # Skip if already moved
                            if os.path.exists(dest_path):
                                moved_files.add(file_path)
                                logging.debug(f"File already exists in bbox_files: {filename}")
                                continue
                            
                            # Check if file is ready (not being written)
                            try:
                                file_size = os.path.getsize(file_path)
                                if file_size == 0:
                                    # File is empty, might still be downloading
                                    logging.debug(f"File {filename} is empty, waiting...")
                                    continue
                                
                                # Quick check if file is stable (not being written)
                                time.sleep(0.5)  # Increased wait time for webview downloads
                                if not os.path.exists(file_path):
                                    # File disappeared (maybe deleted by browser cleanup)
                                    logging.debug(f"File {filename} disappeared, skipping")
                                    continue
                                
                                new_size = os.path.getsize(file_path)
                                if new_size != file_size:
                                    # File is still being written
                                    logging.debug(f"File {filename} is still being written ({file_size} -> {new_size} bytes)")
                                    continue
                                
                                # Try to move the file immediately
                                try:
                                    logging.info(f"Attempting to move file: {filename} ({file_size} bytes) from {file_path} to {dest_path}")
                                    # Attempt to move the file - use copy2 then remove to handle locked files better
                                    # But first try direct move (faster)
                                    try:
                                        shutil.move(file_path, dest_path)
                                        logging.info(f"Successfully moved file: {filename}")
                                    except (PermissionError, OSError) as lock_err:
                                        # File might be locked, try copy then remove
                                        logging.warning(f"File locked during move, trying copy+remove: {filename} - {lock_err}")
                                        shutil.copy2(file_path, dest_path)
                                        logging.info(f"Copied file: {filename}, attempting to remove original...")
                                        # Wait a bit then try to remove original
                                        time.sleep(1.0)  # Longer wait for locked files
                                        try:
                                            os.remove(file_path)
                                            logging.info(f"Removed original file: {filename}")
                                        except (PermissionError, OSError) as remove_err:
                                            # Couldn't remove original, but copy succeeded
                                            logging.warning(f"Could not remove original file {filename}, but copied successfully: {remove_err}")
                                    
                                    moved_files.add(file_path)
                                    logging.info(f"✅ Successfully moved file to bbox_files folder: {filename} ({file_size} bytes) -> {dest_path}")
                                    
                                    # Convert any GeoJSON file to shapefile (bbox_* or geometry_*)
                                    if filename.endswith('.geojson'):
                                        try:
                                            from .utils import geojson_to_shapefile
                                            # Remove .geojson extension and add .shp
                                            base_name = filename.replace('.geojson', '')
                                            shapefile_path = os.path.join(bbox_dir, base_name + '.shp')
                                            
                                            logging.info(f"Converting GeoJSON to shapefile: {dest_path} -> {shapefile_path}")
                                            if geojson_to_shapefile(dest_path, shapefile_path):
                                                logging.info(f"✅ Converted GeoJSON to shapefile: {shapefile_path}")
                                                # Verify shapefile was created
                                                if os.path.exists(shapefile_path):
                                                    shp_size = os.path.getsize(shapefile_path)
                                                    logging.info(f"Shapefile created successfully: {shapefile_path} ({shp_size} bytes)")
                                                else:
                                                    logging.warning(f"Shapefile conversion reported success but file not found: {shapefile_path}")
                                            else:
                                                logging.warning(f"Failed to convert GeoJSON to shapefile: {shapefile_path}")
                                        except ImportError as e:
                                            logging.warning(f"fiona not available for shapefile conversion: {e}")
                                        except Exception as e:
                                            logging.warning(f"Could not convert GeoJSON to shapefile: {e}", exc_info=True)
                                except Exception as move_err:
                                    logging.error(f"❌ Error moving file {filename}: {move_err}", exc_info=True)
                                    logging.error(f"   Source: {file_path}")
                                    logging.error(f"   Destination: {dest_path}")
                                    logging.error(f"   File exists: {os.path.exists(file_path)}")
                                    if os.path.exists(file_path):
                                        logging.error(f"   File size: {os.path.getsize(file_path)} bytes")
                            except (PermissionError, OSError) as e:
                                # File might be locked or inaccessible
                                logging.warning(f"File {filename} is locked or inaccessible: {e}")
                                logging.warning(f"   Will retry on next check cycle")
                        except Exception as e:
                            logging.error(f"Error processing file {file_path}: {e}", exc_info=True)
                
                # Clean up old entries (keep last 100)
                if len(moved_files) > 100:
                    moved_files = set(list(moved_files)[-100:])
                
                # Check every 1 second (more frequent to catch files faster)
                time.sleep(1)
            except Exception as e:
                logging.error(f"Error in file monitor: {e}")
                time.sleep(5)
    
    # Start monitoring in background thread
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    return monitor_thread


def create_map_html(initial_bbox: Optional[Tuple[float, float, float, float]] = None, callback_url: str = None) -> str:
    """Create HTML map with embedded JavaScript for better interaction."""
    if not FOLIUM_AVAILABLE:
        raise ImportError("folium is required for map selector. Install with: pip install folium")
    
    # Determine initial center and zoom
    if initial_bbox:
        lon_min, lat_min, lon_max, lat_max = initial_bbox
        center_lat = (lat_min + lat_max) / 2.0
        center_lon = (lon_min + lon_max) / 2.0
        lat_span = lat_max - lat_min
        lon_span = lon_max - lon_min
        max_span = max(lat_span, lon_span)
        if max_span > 10:
            zoom = 4
        elif max_span > 5:
            zoom = 5
        elif max_span > 2:
            zoom = 6
        elif max_span > 1:
            zoom = 7
        elif max_span > 0.5:
            zoom = 8
        elif max_span > 0.2:
            zoom = 9
        else:
            zoom = 10
    else:
        center_lat = 31.5
        center_lon = 35.4
        zoom = 8
    
    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles='OpenStreetMap'
    )
    
    # Add satellite imagery layer
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite Imagery',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Add drawing tools - enable both rectangle and polygon
    draw = plugins.Draw(
        export=False,
        position='topleft',
        draw_options={
            'rectangle': {
                'shapeOptions': {
                    'color': '#3388ff',
                    'fillColor': '#3388ff',
                    'fillOpacity': 0.2
                }
            },
            'polygon': {
                'shapeOptions': {
                    'color': '#ff3388',
                    'fillColor': '#ff3388',
                    'fillOpacity': 0.2
                },
                'allowIntersection': False,
                'showArea': True
            },
            'circle': False,
            'polyline': False,
            'marker': False,
            'circlemarker': False
        },
        edit_options={
            'featureGroup': None,
            'remove': True
        }
    )
    draw.add_to(m)
    
    # Add initial bbox rectangle if provided
    if initial_bbox:
        lon_min, lat_min, lon_max, lat_max = initial_bbox
        bbox_rect = folium.Rectangle(
            bounds=[[lat_min, lon_min], [lat_max, lon_max]],
            color='#ff0000',
            fillColor='#ff0000',
            fillOpacity=0.2,
            weight=2,
            popup='Current BBox'
        )
        bbox_rect.add_to(m)
    
    # Enhanced search with clickable results
    search_html = """
        <div style="position: fixed; top: 10px; right: 10px; width: 300px; z-index:9999; background-color: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
            <h4 style="margin-top: 0;">Location Search</h4>
            <input type="text" id="search-input" placeholder="Search location or address..." style="width: 100%; padding: 5px; margin-bottom: 5px;">
            <button onclick="searchLocation()" style="width: 100%; padding: 5px; background-color: #3388ff; color: white; border: none; border-radius: 3px; cursor: pointer;">Search</button>
            <div id="search-results" style="margin-top: 10px; max-height: 200px; overflow-y: auto;"></div>
        </div>
        <script>
            // Store map reference when it's available
            var foliumMap = null;
            
            // Function to find and store the map object
            function findMapObject() {
                if (foliumMap) return foliumMap;
                
                // Method 1: Try global 'map' variable (Folium's standard)
                if (typeof map !== 'undefined' && map && typeof map.setView === 'function') {
                    foliumMap = map;
                    return foliumMap;
                }
                
                // Method 2: Try window.map
                if (typeof window.map !== 'undefined' && window.map && typeof window.map.setView === 'function') {
                    foliumMap = window.map;
                    return foliumMap;
                }
                
                // Method 3: Find via Leaflet container
                var containers = document.getElementsByClassName('leaflet-container');
                if (containers.length > 0 && window.L) {
                    // Leaflet stores map instances - try to find it
                    var container = containers[0];
                    if (container._leaflet_id) {
                        // Try Leaflet's internal map storage
                        if (window.L.Map && window.L.Map.instances) {
                            var mapId = container._leaflet_id;
                            var foundMap = window.L.Map.instances[mapId];
                            if (foundMap && typeof foundMap.setView === 'function') {
                                foliumMap = foundMap;
                                return foliumMap;
                            }
                        }
                        // Alternative: access via container's stored reference
                        if (container._leaflet) {
                            foliumMap = container._leaflet;
                            return foliumMap;
                        }
                    }
                }
                
                // Method 4: Search all window properties for Leaflet map
                if (window.L && window.L.Map) {
                    for (var prop in window) {
                        try {
                            var obj = window[prop];
                            if (obj && typeof obj === 'object' && typeof obj.setView === 'function' && obj.getCenter) {
                                foliumMap = obj;
                                return foliumMap;
                            }
                        } catch (e) {
                            // Skip inaccessible properties
                        }
                    }
                }
                
                return null;
            }
            
            // Wait for map to initialize, then store reference
            function waitForMap(callback, maxAttempts) {
                maxAttempts = maxAttempts || 50;
                var attempts = 0;
                
                var checkMap = function() {
                    attempts++;
                    var mapObj = findMapObject();
                    if (mapObj) {
                        foliumMap = mapObj;
                        if (callback) callback(mapObj);
                        return;
                    }
                    
                    if (attempts < maxAttempts) {
                        setTimeout(checkMap, 100);
                    } else {
                        console.error('Map object not found after ' + maxAttempts + ' attempts');
                        if (callback) callback(null);
                    }
                };
                
                // Start checking after a short delay to let Folium initialize
                setTimeout(checkMap, 100);
            }
            
            // Initialize map reference when page loads
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    waitForMap();
                });
            } else {
                waitForMap();
            }
            
            // Ensure goToLocation is globally accessible
            window.goToLocation = function(lat, lon) {
                var targetLat = parseFloat(lat);
                var targetLon = parseFloat(lon);
                
                if (isNaN(targetLat) || isNaN(targetLon)) {
                    alert('Invalid coordinates');
                    return;
                }
                
                // Try to use stored map reference first
                var mapObj = foliumMap || findMapObject();
                
                if (!mapObj) {
                    // If not found, wait for it
                    waitForMap(function(foundMap) {
                        if (foundMap) {
                            navigateToLocation(foundMap, targetLat, targetLon);
                        } else {
                            alert('Map not ready. Please wait a moment and try again.');
                        }
                    }, 20);
                        } else {
                    navigateToLocation(mapObj, targetLat, targetLon);
                }
            };
            
            function navigateToLocation(mapObj, lat, lon) {
                try {
                    if (!mapObj || typeof mapObj.setView !== 'function') {
                        throw new Error('Map object is not valid');
                    }
                    
                    // Navigate to location
                    mapObj.setView([lat, lon], 12);
                    
                    // Clear search results
                    var resultsDiv = document.getElementById('search-results');
                    if (resultsDiv) {
                        resultsDiv.innerHTML = '';
                    }
                    
                    // Remove existing marker if present
                            if (window.locationMarker) {
                        try {
                                mapObj.removeLayer(window.locationMarker);
                        } catch (e) {
                            // Ignore if marker doesn't exist
                        }
                    }
                    
                    // Add new marker
                    if (window.L && window.L.marker) {
                        window.locationMarker = window.L.marker([lat, lon]).addTo(mapObj);
                        window.locationMarker.bindPopup('Selected: ' + lat.toFixed(4) + ', ' + lon.toFixed(4)).openPopup();
                        }
                    } catch (e) {
                    console.error('Error navigating to location:', e);
                    alert('Error navigating to location: ' + (e.message || 'Unknown error'));
                }
                    }
            
            function searchLocation() {
                var query = document.getElementById('search-input').value.trim();
                if (!query) {
                    alert('Please enter a search term');
                    return;
                }
                
                var resultsDiv = document.getElementById('search-results');
                resultsDiv.innerHTML = '<p>Searching...</p>';
                
                // Use Nominatim geocoding API with required User-Agent header
                // Note: Nominatim requires a User-Agent header per their usage policy
                var url = 'https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(query) + '&limit=5&addressdetails=1';
                
                fetch(url, {
                    method: 'GET',
                    headers: {
                        'User-Agent': 'GEE-Map-Selector/1.0'
                    }
                })
                    .then(function(response) {
                        if (!response.ok) {
                            throw new Error('Search failed: HTTP ' + response.status);
                        }
                        return response.json();
                    })
                    .then(function(data) {
                        if (!data || data.length === 0) {
                            resultsDiv.innerHTML = '<p style="color: red;">No results found for "' + query + '"</p>';
                            return;
                        }
                        
                        var html = '<ul style="list-style: none; padding: 0; margin: 0;">';
                        data.forEach(function(item) {
                            var lat = parseFloat(item.lat);
                            var lon = parseFloat(item.lon);
                            var displayName = item.display_name || item.name || 'Unknown location';
                            html += '<li style="padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; background-color: #f9f9f9;" ';
                            html += 'onmouseover="this.style.backgroundColor=\\'#e3f2fd\\';" ';
                            html += 'onmouseout="this.style.backgroundColor=\\'#f9f9f9\\';" ';
                            html += 'onclick="window.goToLocation(' + lat + ',' + lon + ');">';
                            html += '<strong>' + displayName + '</strong><br>';
                            html += '<small style="color: #666;">Lat: ' + lat.toFixed(4) + ', Lon: ' + lon.toFixed(4) + '</small>';
                            html += '</li>';
                        });
                        html += '</ul>';
                        resultsDiv.innerHTML = html;
                    })
                    .catch(function(error) {
                        console.error('Search error:', error);
                        var errorMsg = 'Search failed. ';
                        if (error.message) {
                            errorMsg += error.message;
                        } else {
                            errorMsg += 'Please check your internet connection and try again.';
                        }
                        resultsDiv.innerHTML = '<p style="color: red;">' + errorMsg + '</p>';
                    });
            }
            
            // Allow Enter key to trigger search
            document.getElementById('search-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    searchLocation();
                }
            });
        </script>
        """
    m.get_root().html.add_child(folium.Element(search_html))
    
    # Instructions and save button
    instructions_html = """
    <script>
        // Declare drawnItems at global scope BEFORE any functions that use it
        var drawnItems = null;
        
        // Define saveGeometry function IMMEDIATELY before HTML that uses it
        // This ensures it's available when the button is clicked
        function saveGeometry() {
            console.log('saveGeometry called');
            
            try {
                // Try to get drawn layers - first from drawnItems, then try to find them on the map
                var layers = [];
                var layer = null;
                
                // Method 1: Use drawnItems if it exists and has layers
                if (typeof drawnItems !== 'undefined' && drawnItems !== null) {
                    var drawnLayers = drawnItems.getLayers();
                    if (drawnLayers && drawnLayers.length > 0) {
                        layers = drawnLayers;
                        layer = layers[0];
                        console.log('Found layers in drawnItems:', layers.length);
                    }
                }
                
                // Method 2: If no layers found, try to find them on the map directly
                if (!layer || layers.length === 0) {
                    console.log('drawnItems not ready or empty, trying to find layers on map...');
                    var mapObj = foliumMap || findMapObject();
                    if (mapObj && mapObj.eachLayer) {
                        var allLayers = [];
                        mapObj.eachLayer(function(l) {
                            // Check if it's a Rectangle or Polygon layer (drawn shapes)
                            if (l instanceof L.Rectangle || l instanceof L.Polygon) {
                                // Make sure it's not the base tile layer or controls
                                if (l.options && (l.options.color === '#3388ff' || l.options.color === '#ff3388' || l.options.color === '#ff0000')) {
                                    allLayers.push(l);
                                }
                            }
                        });
                        if (allLayers.length > 0) {
                            layers = allLayers;
                            layer = layers[0];
                            console.log('Found layers on map:', layers.length);
                        }
                    }
                }
                
                // Method 3: Try to initialize drawnItems if map is ready
                if ((!layer || layers.length === 0) && typeof L !== 'undefined') {
                    console.log('Trying to initialize drawnItems...');
                    try {
                        var mapObj = foliumMap || findMapObject();
                        if (mapObj && typeof L !== 'undefined' && L.FeatureGroup) {
                            if (!drawnItems) {
                                drawnItems = new L.FeatureGroup();
                                mapObj.addLayer(drawnItems);
                            }
                            // Check again after initialization
                            var drawnLayers = drawnItems.getLayers();
                            if (drawnLayers && drawnLayers.length > 0) {
                                layers = drawnLayers;
                                layer = layers[0];
                                console.log('Found layers after initialization:', layers.length);
                            }
                        }
                    } catch (initErr) {
                        console.warn('Could not initialize drawnItems:', initErr);
                    }
                }
                
                // Final check: if still no layers, show error
                if (!layer || layers.length === 0) {
                    alert('Please draw a rectangle or polygon first!\\n\\nClick the drawing tool (top-left) and draw your area on the map.');
                    return;
                }
                
                console.log('Drawn items found, processing...');
                
                var layer = layers[0];
                var bounds = layer.getBounds();
                var sw = bounds.getSouthWest();
                var ne = bounds.getNorthEast();
                var bboxStr = sw.lng + ',' + sw.lat + ',' + ne.lng + ',' + ne.lat;
                console.log('BBox:', bboxStr);
                
                // Get stored geometry data (for polygons, use actual geometry; for rectangles, use bbox)
                var geometryData = document.getElementById('geometry-data').textContent;
                var actualGeojson = null;
                
                if (geometryData && geometryData.trim()) {
                    try {
                        actualGeojson = JSON.parse(geometryData);
                        console.log('Using stored geometry data');
                    } catch (e) {
                        console.warn('Could not parse stored geometry, creating from bbox:', e);
                    }
                }
                
                // If no stored geometry, create from bbox
                if (!actualGeojson) {
                    console.log('No stored geometry, creating from bbox');
                    var coords = bboxStr.split(',');
                    if (coords.length >= 4) {
                        var lonMin = parseFloat(coords[0]);
                        var latMin = parseFloat(coords[1]);
                        var lonMax = parseFloat(coords[2]);
                        var latMax = parseFloat(coords[3]);
                        
                        // Check if it's a rectangle or polygon
                        var isRectangle = false;
                        if (window.L && layer instanceof window.L.Rectangle) {
                            isRectangle = true;
                        }
                        
                        actualGeojson = {
                            'type': 'Feature',
                            'properties': {
                                'name': isRectangle ? 'BoundingBox' : 'Polygon',
                                'bbox': bboxStr,
                                'created': new Date().toISOString()
                            },
                            'geometry': {
                                'type': 'Polygon',
                                'coordinates': [[
                                    [lonMin, latMin],
                                    [lonMax, latMin],
                                    [lonMax, latMax],
                                    [lonMin, latMax],
                                    [lonMin, latMin]
                                ]]
                            }
                        };
                    }
                }
                
                if (!actualGeojson) {
                    alert('Error: Could not create geometry data');
                    return;
                }
                
                var geojsonStr = JSON.stringify(actualGeojson, null, 2);
                console.log('GeoJSON created, length:', geojsonStr.length);
                
                // Try Python backend first (webview bridge), then fallback to download
                var usePythonBackend = false;
                var pythonApi = null;
                
                // Check if pywebview API is available - try multiple ways
                console.log('Checking for pywebview API...');
                console.log('  typeof pywebview:', typeof pywebview);
                console.log('  typeof window.pywebview:', typeof window.pywebview);
                
                if (typeof pywebview !== 'undefined' && pywebview.api && typeof pywebview.api.save_geometry === 'function') {
                    pythonApi = pywebview.api;
                    usePythonBackend = true;
                    console.log('Found pywebview.api.save_geometry - will use Python backend');
                } else if (typeof window.pywebview !== 'undefined' && window.pywebview.api && typeof window.pywebview.api.save_geometry === 'function') {
                    pythonApi = window.pywebview.api;
                    usePythonBackend = true;
                    console.log('Found window.pywebview.api.save_geometry - will use Python backend');
                } else {
                    console.log('Python backend not found, checking available APIs...');
                    if (typeof pywebview !== 'undefined') {
                        console.log('  pywebview exists:', Object.keys(pywebview || {}));
                    }
                    if (typeof window.pywebview !== 'undefined') {
                        console.log('  window.pywebview exists:', Object.keys(window.pywebview || {}));
                    }
                }
                
                if (usePythonBackend && pythonApi) {
                    try {
                        console.log('Calling Python backend save_geometry...');
                        var result = pythonApi.save_geometry(geojsonStr);
                        console.log('Python backend result type:', typeof result);
                        console.log('Python backend result:', result);
                        
                        // Handle both promise and direct result
                        if (result && typeof result.then === 'function') {
                            // It's a promise - handle asynchronously
                            console.log('Result is a promise, waiting...');
                            result.then(function(res) {
                                console.log('Python backend promise resolved:', res);
                                if (res && res.status === 'success') {
                                    var msg = '✅ Geometry saved!\\n\\n📄 File: ' + res.filename + '\\n\\n📁 Location: bbox_files/ folder';
                                    if (res.shapefile_created) {
                                        msg += '\\n\\n✅ Shapefile created automatically!';
                                    } else {
                                        msg += '\\n\\n⚠️ Shapefile conversion may have failed (check logs)';
                                    }
                                    alert(msg);
                                } else {
                                    console.error('Python backend save failed:', res);
                                    // Fallback to download
                                    _downloadFile(geojsonStr, 'geometry_');
                                    alert('Geometry saved to Downloads (fallback)!\\n\\nFile will be moved to bbox_files/ folder automatically.');
                                }
                            }).catch(function(err) {
                                console.error('Python backend promise rejected:', err);
                                // Fallback to download
                                _downloadFile(geojsonStr, 'geometry_');
                                alert('Geometry saved to Downloads (fallback)!\\n\\nFile will be moved to bbox_files/ folder automatically.');
                            });
                            return; // Promise is handling result
                        } else if (result && result.status === 'success') {
                            // Direct result (synchronous)
                            console.log('Got direct success result');
                            var msg = '✅ Geometry saved!\\n\\n📄 File: ' + result.filename + '\\n\\n📁 Location: bbox_files/ folder';
                            if (result.shapefile_created) {
                                msg += '\\n\\n✅ Shapefile created automatically!';
                            } else {
                                msg += '\\n\\n⚠️ Shapefile conversion may have failed (check logs)';
                            }
                            alert(msg);
                        } else {
                            console.error('Python backend returned error:', result);
                            throw new Error(result ? result.message : 'Unknown error from Python backend');
                        }
                    } catch (err) {
                        console.error('Python backend exception:', err);
                        console.error('Exception stack:', err.stack);
                        // Fallback to download method (for browser)
                        _downloadFile(geojsonStr, 'geometry_');
                        alert('Geometry saved to Downloads (fallback)!\\n\\nFile will be moved to bbox_files/ folder and converted to shapefile automatically.');
                    }
                } else {
                    // No Python backend, use download method (for browser)
                    console.log('Python backend not available (pywebview.api not found), using download fallback');
                    var downloaded = _downloadFile(geojsonStr, 'geometry_');
                    if (downloaded) {
                        alert('Geometry saved to Downloads!\\n\\nFile will be moved to bbox_files/ folder and converted to shapefile automatically.');
                    } else {
                        alert('Error: Could not save geometry. Please check browser console for errors.');
                    }
                }
            } catch (e) {
                console.error('Error saving geometry:', e);
                console.error('Error stack:', e.stack);
                alert('Error saving geometry: ' + (e.message || 'Unknown error') + '\\n\\nCheck browser console (F12) for details.');
            }
        }
        
        // Also assign to window to ensure global access
        window.saveGeometry = saveGeometry;
        
        // Define _downloadFile helper function (used by saveGeometry)
        function _downloadFile(geojsonStr, prefix) {
            // Download file - works in both browser and webview
            try {
                var now = new Date();
                var timestamp = now.getFullYear() + 
                    String(now.getMonth() + 1).padStart(2, '0') + 
                    String(now.getDate()).padStart(2, '0') + '_' +
                    String(now.getHours()).padStart(2, '0') + 
                    String(now.getMinutes()).padStart(2, '0') + 
                    String(now.getSeconds()).padStart(2, '0');
                var filename = prefix + timestamp + '.geojson';
                
                var blob = new Blob([geojsonStr], { type: 'application/json' });
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.style.display = 'none';
                document.body.appendChild(a);
                
                // Trigger download
                try {
                    a.click();
                    console.log('File download initiated:', filename);
                } catch (clickErr) {
                    console.warn('Click failed, trying alternative method:', clickErr);
                    // Alternative: create event and dispatch
                    var event = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true
                    });
                    a.dispatchEvent(event);
                }
                
                // Clean up after delay
                setTimeout(function() {
                    try {
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                    } catch (e) {
                        console.warn('Cleanup error (non-critical):', e);
                    }
                }, 1000);
                
                return true;
            } catch (downloadErr) {
                console.error('Download failed:', downloadErr);
                alert('Error downloading file: ' + (downloadErr.message || 'Unknown error'));
                return false;
            }
        }
        window._downloadFile = _downloadFile;
    </script>
    <div style="position: fixed; bottom: 10px; left: 10px; width: 350px; z-index:9999; background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
        <h4 style="margin-top: 0;">Instructions</h4>
        <ol style="margin: 0; padding-left: 20px;">
            <li>Use the <strong>draw rectangle</strong> or <strong>polygon</strong> tool (top-left) to draw your area</li>
            <li>Search for locations using the search box (top-right) - click results to zoom</li>
            <li>Click <strong>Save</strong> to save as GeoJSON and Shapefile</li>
        </ol>
        <button id="save-geometry-btn" onclick="if(typeof saveGeometry === 'function') { saveGeometry(); } else if(typeof window.saveGeometry === 'function') { window.saveGeometry(); } else { alert('Save function not ready. Please wait a moment and try again.'); } return false;" style="width: 100%; padding: 10px; margin-top: 10px; background-color: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-weight: bold;">💾 Save Geometry</button>
        <input type="file" id="bbox-file-input" accept=".txt,.csv,.geojson" style="display: none;" onchange="importBBoxFile(event)">
        <button onclick="document.getElementById('bbox-file-input').click()" style="width: 100%; padding: 10px; margin-top: 10px; background-color: #6c757d; color: white; border: none; border-radius: 3px; cursor: pointer; font-weight: bold;">📁 Import BBox from File</button>
        <div id="bbox-display" style="margin-top: 10px; padding: 5px; background-color: #f8f9fa; border-radius: 3px; font-family: monospace; font-size: 12px; word-break: break-all;"></div>
        <div id="geometry-data" style="display: none;"></div>
    </div>
    <script>
        // NOW attach button handler AFTER functions are defined (functions are already defined above)
        (function() {
            function attachSaveButton() {
                var btn = document.getElementById('save-geometry-btn');
                if (btn) {
                    // Remove any existing handlers
                    btn.onclick = null;
                    // Add new handler
                    btn.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('Save button clicked!');
                        try {
                            if (typeof saveGeometry === 'function') {
                                saveGeometry();
                            } else if (typeof window.saveGeometry === 'function') {
                                window.saveGeometry();
                            } else {
                                alert('Error: saveGeometry function not found!\\n\\nType: ' + typeof saveGeometry + '\\nWindow type: ' + typeof window.saveGeometry);
                                console.error('saveGeometry not found. Available functions:', Object.keys(window).filter(function(k) { return typeof window[k] === 'function'; }));
                            }
                        } catch (err) {
                            console.error('Error in save button handler:', err);
                            alert('Error saving geometry: ' + (err.message || 'Unknown error'));
                        }
                        return false;
                    }, false);
                    console.log('Save button handler attached successfully');
                } else {
                    console.error('Save button not found, retrying...');
                    setTimeout(attachSaveButton, 100);
                }
            }
            // Try immediately, or wait for DOM
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', attachSaveButton);
            } else {
                // DOM already ready, but wait a tick to ensure button exists
                setTimeout(attachSaveButton, 50);
            }
        })();
        
        // drawnItems already declared above - just initialize it here
        // Wait for map to be ready before initializing drawing
        function initializeDrawing() {
            var mapObj = foliumMap || findMapObject();
            if (!mapObj) {
                setTimeout(initializeDrawing, 100);
                return;
            }
            
            if (!drawnItems) {
                drawnItems = new L.FeatureGroup();
                mapObj.addLayer(drawnItems);
                
                mapObj.on('draw:created', function(e) {
            var layer = e.layer;
            drawnItems.clearLayers();
            drawnItems.addLayer(layer);
            updateBBoxDisplay();
        });
        
                mapObj.on('draw:edited', function(e) {
            updateBBoxDisplay();
        });
        
                mapObj.on('draw:deleted', function(e) {
            document.getElementById('bbox-display').innerHTML = 'No area selected';
                    document.getElementById('geometry-data').textContent = '';
                });
            }
        }
        
        // Initialize drawing when map is ready
        waitForMap(function(mapObj) {
            if (mapObj) {
                initializeDrawing();
            }
        });
        
        function updateBBoxDisplay() {
            if (!drawnItems) {
                return;
            }
            
            var layers = drawnItems.getLayers();
            if (layers.length === 0) {
                document.getElementById('bbox-display').innerHTML = 'No area selected';
                document.getElementById('geometry-data').textContent = '';
                return;
            }
            
            var layer = layers[0];
            var bounds = layer.getBounds();
            var sw = bounds.getSouthWest();
            var ne = bounds.getNorthEast();
            var bbox = sw.lng + ',' + sw.lat + ',' + ne.lng + ',' + ne.lat;
            
            // Store geometry data for shapefile export
            var geometry = null;
            if (layer instanceof L.Rectangle || layer instanceof L.Polygon) {
                var latlngs = layer.getLatLngs();
                if (latlngs && latlngs.length > 0) {
                    // Convert to GeoJSON format
                    var coordinates = [];
                    if (layer instanceof L.Rectangle) {
                        // Rectangle: [[sw, se, ne, nw, sw]]
                        var rectBounds = layer.getBounds();
                        var sw_coord = [rectBounds.getSouthWest().lng, rectBounds.getSouthWest().lat];
                        var se_coord = [rectBounds.getSouthEast().lng, rectBounds.getSouthEast().lat];
                        var ne_coord = [rectBounds.getNorthEast().lng, rectBounds.getNorthEast().lat];
                        var nw_coord = [rectBounds.getNorthWest().lng, rectBounds.getNorthWest().lat];
                        coordinates = [[sw_coord, se_coord, ne_coord, nw_coord, sw_coord]];
                    } else {
                        // Polygon: array of coordinate arrays
                        if (Array.isArray(latlngs[0])) {
                            // Multi-polygon or polygon with holes
                            coordinates = latlngs.map(function(ring) {
                                return ring.map(function(ll) {
                                    return [ll.lng, ll.lat];
                                });
                            });
                        } else {
                            // Simple polygon
                            var ring = latlngs.map(function(ll) {
                                return [ll.lng, ll.lat];
                            });
                            // Close the ring
                            if (ring.length > 0 && (ring[0][0] !== ring[ring.length-1][0] || ring[0][1] !== ring[ring.length-1][1])) {
                                ring.push([ring[0][0], ring[0][1]]);
                            }
                            coordinates = [ring];
                        }
                    }
                    
                    geometry = {
                        type: layer instanceof L.Rectangle ? 'Polygon' : 'Polygon',
                        coordinates: coordinates
                    };
                }
            }
            
            // Store geometry as JSON string
            if (geometry) {
                var geoJson = {
                    type: 'Feature',
                    properties: {},
                    geometry: geometry
                };
                document.getElementById('geometry-data').textContent = JSON.stringify(geoJson);
            }
            
            var shapeType = layer instanceof L.Rectangle ? 'Rectangle' : 'Polygon';
            document.getElementById('bbox-display').innerHTML = '<strong>' + shapeType + ' BBox:</strong><br>' + bbox;
        }
        
        function saveBBoxToFile(bboxStr, actualGeojson) {
            // Create GeoJSON from bbox for GIS import (ArcGIS, QGIS, etc.)
            // If actualGeojson is provided (for polygons), use that instead of creating from bbox
            try {
                var geojson = null;
                
                if (actualGeojson && actualGeojson.geometry) {
                    // Use the actual polygon geometry
                    geojson = {
                        'type': 'Feature',
                        'properties': {
                            'name': 'Polygon',
                            'bbox': bboxStr,
                            'created': new Date().toISOString()
                        },
                        'geometry': actualGeojson.geometry
                    };
                    console.log('Using actual polygon geometry for save');
                        } else {
                    // Create GeoJSON from bounding box (for rectangles)
                var coords = bboxStr.split(',');
                if (coords.length >= 4) {
                    var lonMin = parseFloat(coords[0]);
                    var latMin = parseFloat(coords[1]);
                    var lonMax = parseFloat(coords[2]);
                    var latMax = parseFloat(coords[3]);
                    
                    // Validate coordinates
                    if (isNaN(lonMin) || isNaN(latMin) || isNaN(lonMax) || isNaN(latMax)) {
                        console.error('Invalid coordinates in bbox:', bboxStr);
                            alert('Error: Invalid coordinates in bbox. Please check the format.');
                        return false;
                    }
                    
                    // Create GeoJSON Feature with Polygon geometry
                        geojson = {
                        'type': 'Feature',
                        'properties': {
                                'name': 'BoundingBox',
                            'bbox': bboxStr,
                            'created': new Date().toISOString()
                        },
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [[
                                [lonMin, latMin],
                                [lonMax, latMin],
                                [lonMax, latMax],
                                [lonMin, latMax],
                                [lonMin, latMin]
                            ]]
                        }
                    };
                } else {
                    console.error('Invalid bbox format:', bboxStr);
                    return false;
                }
                }
                
                var geojsonStr = JSON.stringify(geojson, null, 2);
                    
                    // Try Python backend first (webview bridge), then fallback to download
                    var saved = false;
                    
                    // Check if pywebview API is available (when running in Python window)
                    // pywebview exposes API as pywebview.api
                    var usePythonBackend = false;
                    var pythonApi = null;
                    
                    // Try different ways to access the API
                    if (typeof pywebview !== 'undefined' && pywebview.api && typeof pywebview.api.save_bbox === 'function') {
                        pythonApi = pywebview.api;
                        usePythonBackend = true;
                        console.log('Found pywebview.api - will use Python backend');
                    }
                    
                    if (usePythonBackend && pythonApi) {
                        try {
                            console.log('Calling Python backend save_bbox...');
                            var result = pythonApi.save_bbox(bboxStr, geojsonStr);
                            console.log('Python backend result:', result);
                            
                            // Handle both promise and direct result
                            if (result && typeof result.then === 'function') {
                                // It's a promise - handle asynchronously
                                result.then(function(res) {
                                    console.log('Python backend promise resolved:', res);
                                    if (res && res.status === 'success') {
                                        alert('BBox saved!\\n\\n' + bboxStr + '\\n\\nFile saved: ' + res.filename + '\\n\\nLocation: bbox_files/ folder\\n\\nShapefile created automatically!');
                                    } else {
                                        console.error('Python backend save failed:', res);
                                        // Fallback to download
                                        _downloadFile(geojsonStr, 'bbox_');
                                        alert('BBox saved to Downloads (fallback)!\\n\\n' + bboxStr + '\\n\\nFile will be moved to bbox_files/ folder automatically.');
                                    }
                                }).catch(function(err) {
                                    console.error('Python backend promise rejected:', err);
                                    // Fallback to download
                                    _downloadFile(geojsonStr, 'bbox_');
                                    alert('BBox saved to Downloads (fallback)!\\n\\n' + bboxStr + '\\n\\nFile will be moved to bbox_files/ folder automatically.');
                                });
                                return true; // Promise is handling result
                            } else if (result && result.status === 'success') {
                                // Direct result (synchronous)
                                saved = true;
                                alert('BBox saved!\\n\\n' + bboxStr + '\\n\\nFile saved: ' + result.filename + '\\n\\nLocation: bbox_files/ folder\\n\\nShapefile created automatically!');
                            } else {
                                console.error('Python backend returned error:', result);
                                throw new Error(result ? result.message : 'Unknown error from Python backend');
                            }
                        } catch (err) {
                            console.error('Python backend exception:', err);
                            // Fallback to download method (for browser)
                            saved = _downloadFile(geojsonStr, 'bbox_');
                            if (saved) {
                                alert('BBox saved to Downloads (fallback)!\\n\\n' + bboxStr + '\\n\\nFile will be moved to bbox_files/ folder and converted to shapefile automatically.');
                            }
                        }
                    } else {
                        // No Python backend, use download method (for browser)
                        console.log('Python backend not available (pywebview.api not found), using download fallback');
                        saved = _downloadFile(geojsonStr, 'bbox_');
                        if (saved) {
                            alert('BBox saved to Downloads!\\n\\n' + bboxStr + '\\n\\nFile will be moved to bbox_files/ folder and converted to shapefile automatically.');
                        }
                    }
                    
                    return saved;
                } else {
                    console.error('Invalid bbox format - need 4 coordinates:', bboxStr);
                    alert('Error: Invalid bbox format. Expected: lon_min,lat_min,lon_max,lat_max');
                    return false;
                }
            } catch (e) {
                console.error('Error creating GeoJSON file:', e);
                alert('Error saving bbox: ' + (e.message || 'Unknown error'));
                return false;
            }
        }
        
        function _downloadFile(geojsonStr, prefix) {
            // Download file - works in both browser and webview
            try {
                var now = new Date();
                var timestamp = now.getFullYear() + 
                    String(now.getMonth() + 1).padStart(2, '0') + 
                    String(now.getDate()).padStart(2, '0') + '_' +
                    String(now.getHours()).padStart(2, '0') + 
                    String(now.getMinutes()).padStart(2, '0') + 
                    String(now.getSeconds()).padStart(2, '0');
                var filename = prefix + timestamp + '.geojson';
                
                var blob = new Blob([geojsonStr], { type: 'application/json' });
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.style.display = 'none';
                document.body.appendChild(a);
                
                // Trigger download
                try {
                a.click();
                    console.log('File download initiated:', filename);
                } catch (clickErr) {
                    console.warn('Click failed, trying alternative method:', clickErr);
                    // Alternative: create event and dispatch
                    var event = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true
                    });
                    a.dispatchEvent(event);
                }
                
                // Clean up after delay
                setTimeout(function() {
                    try {
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } catch (e) {
                        console.warn('Cleanup error (non-critical):', e);
                    }
                }, 1000); // Longer delay to ensure download completes
                
                return true;
            } catch (downloadErr) {
                console.error('Download failed:', downloadErr);
                alert('Error downloading file: ' + (downloadErr.message || 'Unknown error'));
                return false;
            }
        }
        
        
        function importBBoxFile(event) {
            var file = event.target.files[0];
            if (!file) return;
            
            var reader = new FileReader();
            reader.onload = function(e) {
                try {
                    var content = e.target.result.trim();
                    var bbox = null;
                    var geojson = null;
                    var geometry = null;
                    
                    // Try to parse as CSV/text (lon_min,lat_min,lon_max,lat_max)
                    var parts = content.split(/[,\\s]+/);
                    if (parts.length >= 4) {
                        var coords = parts.slice(0, 4).map(function(x) { return parseFloat(x.trim()); });
                        if (coords.every(function(x) { return !isNaN(x); })) {
                            bbox = coords;
                        }
                    }
                    
                    // Try to parse as GeoJSON
                    if (!bbox) {
                        try {
                            geojson = JSON.parse(content);
                            if (geojson.type === 'Feature' && geojson.geometry) {
                                geometry = geojson.geometry;
                                if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
                                    var coords = geometry.coordinates[0];
                                    var lons = coords.map(function(c) { return c[0]; });
                                    var lats = coords.map(function(c) { return c[1]; });
                                    bbox = [Math.min.apply(null, lons), Math.min.apply(null, lats), 
                                           Math.max.apply(null, lons), Math.max.apply(null, lats)];
                                    // Keep the full GeoJSON feature
                                    geojson = geojson;
                                }
                            } else if (geojson.type === 'FeatureCollection' && geojson.features && geojson.features.length > 0) {
                                var feature = geojson.features[0];
                                if (feature.geometry && feature.geometry.type === 'Polygon' && feature.geometry.coordinates && feature.geometry.coordinates[0]) {
                                    geometry = feature.geometry;
                                    var coords = geometry.coordinates[0];
                                    var lons = coords.map(function(c) { return c[0]; });
                                    var lats = coords.map(function(c) { return c[1]; });
                                    bbox = [Math.min.apply(null, lons), Math.min.apply(null, lats), 
                                           Math.max.apply(null, lons), Math.max.apply(null, lats)];
                                    // Use first feature as the GeoJSON
                                    geojson = feature;
                                }
                            } else if (geojson.type === 'Polygon' && geojson.coordinates) {
                                // Direct Polygon geometry
                                geometry = geojson;
                                if (geometry.coordinates && geometry.coordinates[0]) {
                                    var coords = geometry.coordinates[0];
                                    var lons = coords.map(function(c) { return c[0]; });
                                    var lats = coords.map(function(c) { return c[1]; });
                                    bbox = [Math.min.apply(null, lons), Math.min.apply(null, lats), 
                                           Math.max.apply(null, lons), Math.max.apply(null, lats)];
                                    // Create Feature from Polygon
                                    geojson = {
                                        type: 'Feature',
                                        properties: {},
                                        geometry: geometry
                                    };
                                }
                            }
                        } catch (jsonErr) {
                            console.warn('Could not parse as JSON:', jsonErr);
                            // Not JSON, continue
                        }
                    }
                    
                    if (bbox && bbox.length === 4) {
                        // Display geometry on map (preserve actual shape if GeoJSON)
                        displayGeometryOnMap(bbox, geojson);
                        alert('BBox imported successfully!\\n\\n' + bbox.join(',') + '\\n\\nThe geometry has been displayed on the map.');
                    } else {
                        alert('Could not parse BBox from file.\\n\\nExpected format:\\n- CSV: lon_min,lat_min,lon_max,lat_max\\n- GeoJSON: Feature, FeatureCollection, or Polygon geometry');
                    }
                } catch (err) {
                    console.error('Error reading file:', err);
                    alert('Error reading file: ' + (err.message || 'Unknown error'));
                }
            };
            reader.readAsText(file);
            
            // Reset file input
            event.target.value = '';
        }
        
        function displayBBoxOnMap(bbox) {
            // Legacy function - for backward compatibility, just call displayGeometryOnMap
            displayGeometryOnMap(bbox, null);
        }
        
        function displayGeometryOnMap(bbox, geojson) {
            // bbox format: [lon_min, lat_min, lon_max, lat_max]
            // geojson: Optional GeoJSON Feature with actual geometry
            var lonMin = bbox[0];
            var latMin = bbox[1];
            var lonMax = bbox[2];
            var latMax = bbox[3];
            
            var mapObj = foliumMap || findMapObject();
            if (!mapObj) {
                waitForMap(function(foundMap) {
                    if (foundMap) {
                        displayGeometryOnMapHelper(foundMap, lonMin, latMin, lonMax, latMax, geojson);
                    }
                });
                return;
            }
            
            displayGeometryOnMapHelper(mapObj, lonMin, latMin, lonMax, latMax, geojson);
        }
        
        function displayGeometryOnMapHelper(mapObj, lonMin, latMin, lonMax, latMax, geojson) {
            try {
                // Ensure drawnItems is initialized
                if (!drawnItems && window.L && window.L.FeatureGroup) {
                    drawnItems = new L.FeatureGroup();
                    mapObj.addLayer(drawnItems);
                }
                
                // Clear existing drawn items
                if (drawnItems) {
                    drawnItems.clearLayers();
                }
                
                var layer = null;
                var bounds = null;
                
                if (window.L) {
                    // If we have GeoJSON with actual polygon geometry, display that
                    if (geojson && geojson.geometry && geojson.geometry.type === 'Polygon' && geojson.geometry.coordinates) {
                        try {
                            // Use Leaflet's GeoJSON layer to display the actual polygon shape
                            var geoJsonLayer = L.geoJSON(geojson, {
                                style: {
                                    color: '#ff3388',
                                    fillColor: '#ff3388',
                                    fillOpacity: 0.2,
                                    weight: 2
                                }
                            });
                            
                            // Get the first layer (the polygon)
                            geoJsonLayer.eachLayer(function(polygonLayer) {
                                layer = polygonLayer;
                                bounds = polygonLayer.getBounds();
                            });
                            
                            if (layer && drawnItems) {
                                drawnItems.addLayer(layer);
                                console.log('Added polygon layer from GeoJSON');
                            } else if (layer) {
                                mapObj.addLayer(layer);
                                console.log('Added polygon layer directly to map (drawnItems not ready)');
                            }
                        } catch (geoJsonErr) {
                            console.warn('Could not create GeoJSON layer, falling back to rectangle:', geoJsonErr);
                            // Fall through to rectangle creation
                        }
                    }
                    
                    // If no polygon was created (or GeoJSON failed), create rectangle from bbox
                    if (!layer && window.L.rectangle) {
                        bounds = [[latMin, lonMin], [latMax, lonMax]];
                        layer = window.L.rectangle(bounds, {
                            color: '#3388ff',
                            fillColor: '#3388ff',
                            fillOpacity: 0.2,
                            weight: 2
                        });
                        
                        if (drawnItems) {
                            drawnItems.addLayer(layer);
                        } else {
                            mapObj.addLayer(layer);
                        }
                        console.log('Created rectangle layer from bbox');
                    }
                    
                    // Store geometry data if we have GeoJSON
                    if (geojson && geojson.geometry) {
                        var geometryDataEl = document.getElementById('geometry-data');
                        if (geometryDataEl) {
                            geometryDataEl.textContent = JSON.stringify(geojson);
                            console.log('Stored geometry data from GeoJSON');
                        }
                    }
                    
                    // Fit map to bounds
                    if (bounds) {
                        mapObj.fitBounds(bounds);
                    } else if (layer && layer.getBounds) {
                        mapObj.fitBounds(layer.getBounds());
                    }
                    
                    // Update display
                    updateBBoxDisplay();
                }
            } catch (e) {
                console.error('Error displaying geometry on map:', e);
                alert('Error displaying geometry: ' + (e.message || 'Unknown error'));
            }
        }
    </script>
    """
    m.get_root().html.add_child(folium.Element(instructions_html))
    
    # Save to temp file
    temp_dir = tempfile.gettempdir()
    html_file = os.path.join(temp_dir, 'gee_map_selector.html')
    m.save(html_file)
    
    # Ensure bbox_files directory exists in project
    bbox_dir = _get_bbox_files_dir()
    logging.info(f"BBox folder ready: {bbox_dir}")
    
    # Verify bbox_files directory is writable
    try:
        test_file = os.path.join(bbox_dir, '.test_write')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logging.debug(f"BBox folder is writable: {bbox_dir}")
    except Exception as e:
        logging.warning(f"BBox folder may not be writable: {e}")
    
    # Start monitoring Downloads folder as fallback (for browser usage)
    monitor_thread = _monitor_and_move_geometry_files()
    if monitor_thread:
        logging.info("File monitoring thread started successfully")
    else:
        logging.warning("File monitoring thread may not have started")
    
    return html_file


class MapAPI:
    """API class for webview JavaScript bridge."""
    
    def save_bbox(self, bbox_str: str, geojson_data: str = None) -> dict:
        """
        Save bbox file directly from Python (called from JavaScript via webview bridge).
        
        Args:
            bbox_str: Bounding box string in format "lon_min,lat_min,lon_max,lat_max"
            geojson_data: Optional GeoJSON string (if provided, uses this; otherwise creates from bbox)
        
        Returns:
            dict with status and message
        """
        try:
            import json
            from datetime import datetime
            
            logging.info(f"save_bbox called with bbox_str={bbox_str}, geojson_data length={len(geojson_data) if geojson_data else 0}")
            
            # Get bbox_files directory
            bbox_dir = _get_bbox_files_dir()
            
            # Parse bbox
            coords = bbox_str.split(',')
            if len(coords) != 4:
                return {'status': 'error', 'message': 'Invalid bbox format'}
            
            lon_min = float(coords[0])
            lat_min = float(coords[1])
            lon_max = float(coords[2])
            lat_max = float(coords[3])
            
            # Create GeoJSON if not provided
            if geojson_data:
                try:
                    geojson = json.loads(geojson_data)
                except Exception as e:
                    logging.warning(f"Failed to parse provided GeoJSON, creating from bbox: {e}")
                    geojson = None
            else:
                geojson = None
            
            if geojson is None:
                # Create GeoJSON from bbox
                geojson = {
                    'type': 'Feature',
                    'properties': {
                        'name': 'Bounding Box',
                        'bbox': bbox_str,
                        'created': datetime.now().isoformat()
                    },
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': [[
                            [lon_min, lat_min],
                            [lon_max, lat_min],
                            [lon_max, lat_max],
                            [lon_min, lat_max],
                            [lon_min, lat_min]
                        ]]
                    }
                }
            
            # Generate filename
            now = datetime.now()
            timestamp = now.strftime('%Y%m%d_%H%M%S')
            filename = f'bbox_{timestamp}.geojson'
            dest_path = os.path.join(bbox_dir, filename)
            
            # Save GeoJSON file
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, indent=2)
            
            logging.info(f"✅ Saved bbox file: {filename} -> {dest_path}")
            
            # Convert to shapefile if possible
            shapefile_created = False
            try:
                from .utils import geojson_to_shapefile
                base_name = filename.replace('.geojson', '')
                shapefile_path = os.path.join(bbox_dir, base_name + '.shp')
                logging.info(f"Converting bbox GeoJSON to shapefile: {dest_path} -> {shapefile_path}")
                if geojson_to_shapefile(dest_path, shapefile_path):
                    logging.info(f"✅ Converted bbox GeoJSON to shapefile: {shapefile_path}")
                    shapefile_created = True
                    # Verify shapefile was created
                    if os.path.exists(shapefile_path):
                        shp_size = os.path.getsize(shapefile_path)
                        logging.info(f"Shapefile verified: {shapefile_path} ({shp_size} bytes)")
                    else:
                        logging.warning(f"Shapefile conversion reported success but file not found: {shapefile_path}")
                else:
                    logging.warning(f"Failed to convert bbox GeoJSON to shapefile: {shapefile_path}")
            except ImportError as e:
                logging.warning(f"fiona not available for shapefile conversion: {e}")
            except Exception as e:
                logging.warning(f"Could not convert bbox to shapefile: {e}", exc_info=True)
            
            message = f'File saved: {filename}'
            if shapefile_created:
                message += f' (shapefile created: {base_name}.shp)'
            
            return {'status': 'success', 'message': message, 'filename': filename, 'shapefile_created': shapefile_created}
            
        except Exception as e:
            logging.error(f"Error saving bbox file: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def save_geometry(self, geojson_data: str) -> dict:
        """
        Save geometry file directly from Python (called from JavaScript via webview bridge).
        
        Args:
            geojson_data: GeoJSON string
        
        Returns:
            dict with status and message
        """
        try:
            import json
            from datetime import datetime
            
            logging.info(f"save_geometry called with geojson_data length={len(geojson_data) if geojson_data else 0}")
            
            # Get bbox_files directory
            bbox_dir = _get_bbox_files_dir()
            
            # Parse GeoJSON
            geojson = json.loads(geojson_data)
            
            # Generate filename
            now = datetime.now()
            timestamp = now.strftime('%Y%m%d_%H%M%S')
            filename = f'geometry_{timestamp}.geojson'
            dest_path = os.path.join(bbox_dir, filename)
            
            # Save GeoJSON file
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, indent=2)
            
            logging.info(f"✅ Saved geometry file: {filename} -> {dest_path}")
            
            # Convert to shapefile if possible
            shapefile_created = False
            try:
                from .utils import geojson_to_shapefile
                base_name = filename.replace('.geojson', '')
                shapefile_path = os.path.join(bbox_dir, base_name + '.shp')
                logging.info(f"Converting geometry GeoJSON to shapefile: {dest_path} -> {shapefile_path}")
                if geojson_to_shapefile(dest_path, shapefile_path):
                    logging.info(f"✅ Converted geometry GeoJSON to shapefile: {shapefile_path}")
                    shapefile_created = True
                    if os.path.exists(shapefile_path):
                        shp_size = os.path.getsize(shapefile_path)
                        logging.info(f"Shapefile verified: {shapefile_path} ({shp_size} bytes)")
            except ImportError as e:
                logging.warning(f"fiona not available for shapefile conversion: {e}")
            except Exception as e:
                logging.warning(f"Could not convert geometry to shapefile: {e}", exc_info=True)
            
            message = f'File saved: {filename}'
            if shapefile_created:
                message += f' (shapefile created: {base_name}.shp)'
            
            return {'status': 'success', 'message': message, 'filename': filename, 'shapefile_created': shapefile_created}
            
        except Exception as e:
            logging.error(f"Error saving geometry file: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}


# Create API instance
_map_api = MapAPI()




def open_embedded_map_window(initial_bbox: Optional[Tuple[float, float, float, float]] = None, parent=None, tkinter_root=None) -> Optional[str]:
    """
    Open map in an embedded Python window using webview (preferred over browser).
    
    Args:
        initial_bbox: Optional initial bounding box
        parent: Optional parent widget (unused, kept for compatibility)
        tkinter_root: Optional tkinter root window for scheduling webview on main thread
    """
    if not FOLIUM_AVAILABLE:
        return None
    
    try:
        html_file = create_map_html(initial_bbox)
        
        # Try webview first (preferred - Python window)
        if WEBVIEW_AVAILABLE:
            def start_webview():
                """Start webview window - must be called from main thread."""
                try:
                    # Create webview window with JavaScript bridge
                    # Use API instance methods
                    webview.create_window(
                        'Map Selector - Draw Bounding Box',
                        html_file,
                        width=1200,
                        height=800,
                        resizable=True,
                        js_api=_map_api  # Expose Python API class to JavaScript
                    )
                    # webview.start() blocks, but this is acceptable for a window
                    webview.start(debug=False)
                    logging.info(f"Webview window closed: {html_file}")
                except Exception as e:
                    logging.error(f"Error starting webview: {e}")
                    # Fallback to browser if webview fails
                    try:
                        import webbrowser
                        abs_path = os.path.abspath(html_file)
                        if os.name == 'nt':
                            file_url = f"file:///{abs_path.replace(os.sep, '/')}"
                        else:
                            file_url = f"file://{abs_path}"
                        webbrowser.open(file_url)
                        logging.info(f"Fell back to browser after webview error: {html_file}")
                    except Exception:
                        pass
            
            # Check if we have tkinter root to schedule on main thread
            if tkinter_root is not None:
                # Schedule webview to run on tkinter main thread
                tkinter_root.after(100, start_webview)
                logging.info(f"Scheduled embedded map window (Python window) to open: {html_file}")
            return html_file
        else:
            # Check if we're on main thread
            try:
                is_main = threading.current_thread() == threading.main_thread()
                if is_main:
                    # We're on main thread, start webview directly
                    webview.create_window(
                        'Map Selector - Draw Bounding Box',
                        html_file,
                        width=1200,
                        height=800,
                        resizable=True,
                        js_api=_map_api  # Expose Python API class to JavaScript
                    )
                    # Start webview in background thread so it doesn't block
                    webview_thread = threading.Thread(target=webview.start, args=(False,), daemon=True)
                    webview_thread.start()
                    time.sleep(0.3)
                    logging.info(f"Started embedded map window (Python window): {html_file}")
                    return html_file
                else:
                    # Not on main thread and no tkinter root - try anyway
                    logging.warning("Not on main thread, attempting webview anyway...")
                    webview_thread = threading.Thread(target=start_webview, daemon=True)
                    webview_thread.start()
                    time.sleep(0.3)
                    logging.info(f"Started embedded map window in thread: {html_file}")
                    return html_file
            except RuntimeError as e:
                if "main thread" in str(e).lower():
                    logging.warning(f"Webview requires main thread: {e}")
                    # Fall back to browser
                    pass
                else:
                    raise
            except Exception as e:
                logging.warning(f"Webview error: {e}")
        
        # Fallback: open in browser
        import webbrowser
        abs_path = os.path.abspath(html_file)
        if os.name == 'nt':  # Windows
            file_url = f"file:///{abs_path.replace(os.sep, '/')}"
        else:  # Unix/Mac
            file_url = f"file://{abs_path}"
        webbrowser.open(file_url)
        logging.info(f"Opened map in browser: {html_file}")
        return html_file
        
    except Exception as e:
        logging.error(f"Error creating map window: {e}", exc_info=True)
        return None


def open_map_selector_window(initial_bbox: Optional[Tuple[float, float, float, float]] = None, tkinter_root=None) -> Optional[str]:
    """Open map selector - tries embedded window (webview) first, falls back to browser."""
    return open_embedded_map_window(initial_bbox, parent=None, tkinter_root=tkinter_root)


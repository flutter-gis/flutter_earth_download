"""
Interactive map selector for choosing bounding boxes.
Uses folium to create an interactive map with location search and drawing tools.
"""
import os
import json
import tempfile
import webbrowser
import shutil
import threading
import time
import glob
import logging
from typing import Tuple, Optional

try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Module-level flag to track if geometry file monitoring has started
_geometry_monitor_started = False
_geometry_monitor_lock = threading.Lock()


def create_map_selector(initial_bbox: Optional[Tuple[float, float, float, float]] = None) -> str:
    """
    Create an interactive map selector with location search and bbox drawing.
    
    Args:
        initial_bbox: Optional initial bounding box (lon_min, lat_min, lon_max, lat_max)
    
    Returns:
        Path to the HTML file that was created and opened in browser
    """
    if not FOLIUM_AVAILABLE:
        raise ImportError("folium is required for map selector. Install with: pip install folium")
    
    # Determine initial center and zoom
    if initial_bbox:
        lon_min, lat_min, lon_max, lat_max = initial_bbox
        center_lat = (lat_min + lat_max) / 2.0
        center_lon = (lon_min + lon_max) / 2.0
        # Calculate zoom level based on bbox size
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
        # Default to Dead Sea area
        center_lat = 31.5
        center_lon = 35.4
        zoom = 8
    
    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles='OpenStreetMap'
    )
    
    # Add satellite imagery layer option
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
    
    # Add location search using geocoding (works in browser, doesn't need geopy)
    # Create custom HTML/JavaScript for location search
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
    
    # Add instructions and save button
    instructions_html = """
    <div style="position: fixed; bottom: 10px; left: 10px; width: 350px; z-index:9999; background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
        <h4 style="margin-top: 0;">Instructions</h4>
        <ol style="margin: 0; padding-left: 20px;">
            <li>Use the <strong>draw rectangle</strong> or <strong>polygon</strong> tool (top-left) to draw your area</li>
            <li>Search for locations using the search box (top-right)</li>
            <li>Click <strong>Save BBox</strong> to copy coordinates or <strong>Export Shapefile</strong> to save as shapefile</li>
        </ol>
        <button onclick="saveBBox()" style="width: 48%; padding: 10px; margin-top: 10px; background-color: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-weight: bold;">Save BBox</button>
        <button onclick="exportShapefile()" style="width: 48%; padding: 10px; margin-top: 10px; margin-left: 4%; background-color: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; font-weight: bold;">Export Shapefile</button>
        <input type="file" id="bbox-file-input" accept=".txt,.csv,.geojson" style="display: none;" onchange="importBBoxFile(event)">
        <button onclick="document.getElementById('bbox-file-input').click()" style="width: 100%; padding: 10px; margin-top: 10px; background-color: #6c757d; color: white; border: none; border-radius: 3px; cursor: pointer; font-weight: bold;">📁 Import BBox from File</button>
        <div id="bbox-display" style="margin-top: 10px; padding: 5px; background-color: #f8f9fa; border-radius: 3px; font-family: monospace; font-size: 12px; word-break: break-all;"></div>
        <div id="geometry-data" style="display: none;"></div>
    </div>
    <script>
        var drawnItems = null;
        
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
        
        function saveBBox() {
            if (!drawnItems) {
                alert('Map not ready. Please wait a moment and try again.');
                return;
            }
            
            var layers = drawnItems.getLayers();
            if (layers.length === 0) {
                alert('Please draw a rectangle or polygon first!');
                return;
            }
            
            try {
                var layer = layers[0];
                var bounds = layer.getBounds();
                var sw = bounds.getSouthWest();
                var ne = bounds.getNorthEast();
                var bboxStr = sw.lng + ',' + sw.lat + ',' + ne.lng + ',' + ne.lat;
                
                // Save to clipboard with GEE_BBOX: prefix for auto-detection
                var markedData = 'GEE_BBOX:' + bboxStr;
                
                // Save to clipboard and file
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(markedData).then(function() {
                        // Also save to file for automatic import
                        var fileSaved = saveBBoxToFile(bboxStr);
                        if (fileSaved) {
                            alert('BBox saved!\\n\\n' + bboxStr + '\\n\\nThe bbox has been automatically added to the main application.\\n\\nFiles saved:\\n• GeoJSON (for GIS import)\\n• Shapefile (for ArcGIS)\\n\\nBoth files will be moved to bbox_files/ folder automatically.');
                        } else {
                            alert('BBox saved to clipboard!\\n\\n' + bboxStr + '\\n\\nNote: File download may have been blocked by browser. The bbox has been copied to clipboard.');
                        }
                    }).catch(function(err) {
                        console.error('Clipboard error:', err);
                        var fileSaved = saveBBoxToFile(bboxStr);
                        var copied = prompt('BBox (copy this text):', markedData);
                        if (copied) {
                            if (fileSaved) {
                                alert('BBox saved to file. Please paste "' + copied + '" into the BBox field if needed.');
                            } else {
                                alert('BBox copied to clipboard. Please paste "' + copied + '" into the BBox field.');
                            }
                        }
                    });
                } else {
                    var fileSaved = saveBBoxToFile(bboxStr);
                    var copied = prompt('BBox (copy this text):', markedData);
                    if (copied) {
                        if (fileSaved) {
                            alert('BBox saved to file. Please paste "' + copied + '" into the BBox field if needed.');
                        } else {
                            alert('BBox copied. Please paste "' + copied + '" into the BBox field.');
                        }
                    }
                }
            } catch (e) {
                console.error('Error saving BBox:', e);
                alert('Error saving BBox: ' + (e.message || 'Unknown error'));
            }
        }
        
        function saveBBoxToFile(bboxStr) {
            // Create GeoJSON from bbox for GIS import (ArcGIS, QGIS, etc.)
            try {
                var coords = bboxStr.split(',');
                if (coords.length >= 4) {
                    var lonMin = parseFloat(coords[0]);
                    var latMin = parseFloat(coords[1]);
                    var lonMax = parseFloat(coords[2]);
                    var latMax = parseFloat(coords[3]);
                    
                    // Validate coordinates
                    if (isNaN(lonMin) || isNaN(latMin) || isNaN(lonMax) || isNaN(latMax)) {
                        console.error('Invalid coordinates in bbox:', bboxStr);
                        return false;
                    }
                    
                    // Create GeoJSON Feature with Polygon geometry
                    var geojson = {
                        'type': 'Feature',
                        'properties': {
                            'name': 'Bounding Box',
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
                    
                    var now = new Date();
                    var timestamp = now.getFullYear() + 
                        String(now.getMonth() + 1).padStart(2, '0') + 
                        String(now.getDate()).padStart(2, '0') + '_' +
                        String(now.getHours()).padStart(2, '0') + 
                        String(now.getMinutes()).padStart(2, '0') + 
                        String(now.getSeconds()).padStart(2, '0');
                    var filename = 'bbox_' + timestamp + '.geojson';
                    
                    // Download GeoJSON file (will be converted to shapefile by Python)
                    try {
                        var geojsonStr = JSON.stringify(geojson, null, 2);
                        var blob = new Blob([geojsonStr], { type: 'application/json' });
                        var url = URL.createObjectURL(blob);
                        var a = document.createElement('a');
                        a.href = url;
                        a.download = filename;
                        a.style.display = 'none';
                        document.body.appendChild(a);
                        a.click();
                        
                        // Clean up after a short delay
                        setTimeout(function() {
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                        }, 100);
                        
                        console.log('GeoJSON file download initiated:', filename);
                        return true;
                    } catch (downloadErr) {
                        console.error('Error downloading GeoJSON file:', downloadErr);
                        return false;
                    }
                } else {
                    console.error('Invalid bbox format:', bboxStr);
                    return false;
                }
            } catch (e) {
                console.error('Error creating GeoJSON file:', e);
                return false;
            }
        }
        
        function exportShapefile() {
            if (!drawnItems) {
                alert('Map not ready. Please wait a moment and try again.');
                return;
            }
            
            var layers = drawnItems.getLayers();
            if (layers.length === 0) {
                alert('Please draw a rectangle or polygon first!');
                return;
            }
            
            var geomData = document.getElementById('geometry-data').textContent;
            if (!geomData) {
                alert('No geometry data available. Please redraw your area.');
                return;
            }
            
            try {
                // Generate filename with timestamp
                var now = new Date();
                var timestamp = now.getFullYear() + 
                    String(now.getMonth() + 1).padStart(2, '0') + 
                    String(now.getDate()).padStart(2, '0') + '_' +
                    String(now.getHours()).padStart(2, '0') + 
                    String(now.getMinutes()).padStart(2, '0') + 
                    String(now.getSeconds()).padStart(2, '0');
                var filename = 'geometry_' + timestamp + '.geojson';
                
                // Create a download link with the geometry data
                var blob = new Blob([geomData], { type: 'application/json' });
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                var downloadsBboxPath = 'Downloads\\\\bbox';
                alert('✅ Geometry exported as GeoJSON!\\n\\n📄 File: ' + filename + '\\n\\n📁 File Location:\\nThe file will be automatically moved to:\\nbbox_files/' + filename + '\\n(in your project directory)\\n\\n✅ You can:\\n• Use this GeoJSON directly in GIS software\\n• Convert to shapefile using Python (fiona/geopandas)\\n• Use the geometry for tile breakdown in the application\\n• Import it back using the Import button');
            } catch (e) {
                console.error('Error exporting shapefile:', e);
                alert('Error exporting geometry: ' + (e.message || 'Unknown error'));
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
                            var geojson = JSON.parse(content);
                            if (geojson.type === 'Feature' && geojson.geometry) {
                                var geom = geojson.geometry;
                                if (geom.type === 'Polygon' && geom.coordinates && geom.coordinates[0]) {
                                    var coords = geom.coordinates[0];
                                    var lons = coords.map(function(c) { return c[0]; });
                                    var lats = coords.map(function(c) { return c[1]; });
                                    bbox = [Math.min.apply(null, lons), Math.min.apply(null, lats), 
                                           Math.max.apply(null, lons), Math.max.apply(null, lats)];
                                }
                            } else if (geojson.type === 'FeatureCollection' && geojson.features && geojson.features.length > 0) {
                                var geom = geojson.features[0].geometry;
                                if (geom && geom.type === 'Polygon' && geom.coordinates && geom.coordinates[0]) {
                                    var coords = geom.coordinates[0];
                                    var lons = coords.map(function(c) { return c[0]; });
                                    var lats = coords.map(function(c) { return c[1]; });
                                    bbox = [Math.min.apply(null, lons), Math.min.apply(null, lats), 
                                           Math.max.apply(null, lons), Math.max.apply(null, lats)];
                                }
                            }
                        } catch (jsonErr) {
                            // Not JSON, continue
                        }
                    }
                    
                    if (bbox && bbox.length === 4) {
                        // Display bbox on map
                        displayBBoxOnMap(bbox);
                        alert('BBox imported successfully!\\n\\n' + bbox.join(',') + '\\n\\nThe bounding box has been displayed on the map.');
                    } else {
                        alert('Could not parse BBox from file.\\n\\nExpected format:\\n- CSV: lon_min,lat_min,lon_max,lat_max\\n- GeoJSON: Feature or FeatureCollection with Polygon geometry');
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
            // bbox format: [lon_min, lat_min, lon_max, lat_max]
            var lonMin = bbox[0];
            var latMin = bbox[1];
            var lonMax = bbox[2];
            var latMax = bbox[3];
            
            var mapObj = foliumMap || findMapObject();
            if (!mapObj) {
                waitForMap(function(foundMap) {
                    if (foundMap) {
                        displayBBoxOnMapHelper(foundMap, lonMin, latMin, lonMax, latMax);
                    }
                });
                return;
            }
            
            displayBBoxOnMapHelper(mapObj, lonMin, latMin, lonMax, latMax);
        }
        
        function displayBBoxOnMapHelper(mapObj, lonMin, latMin, lonMax, latMax) {
            try {
                // Clear existing drawn items
                if (drawnItems) {
                    drawnItems.clearLayers();
                }
                
                // Create rectangle from bbox
                if (window.L && window.L.rectangle) {
                    var bounds = [[latMin, lonMin], [latMax, lonMax]];
                    var rect = window.L.rectangle(bounds, {
                        color: '#3388ff',
                        fillColor: '#3388ff',
                        fillOpacity: 0.2,
                        weight: 2
                    });
                    
                    if (drawnItems) {
                        drawnItems.addLayer(rect);
            } else {
                        mapObj.addLayer(rect);
                    }
                    
                    // Fit map to bounds
                    mapObj.fitBounds(bounds);
                    
                    // Update display
                    updateBBoxDisplay();
                }
            } catch (e) {
                console.error('Error displaying bbox on map:', e);
                alert('Error displaying bbox: ' + (e.message || 'Unknown error'));
            }
        }
    </script>
    """
    m.get_root().html.add_child(folium.Element(instructions_html))
    
    # Save map to temporary HTML file
    temp_dir = tempfile.gettempdir()
    html_file = os.path.join(temp_dir, 'gee_map_selector.html')
    m.save(html_file)
    
            # Ensure bbox directories exist
            try:
                # Project bbox_files folder
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                bbox_dir = os.path.join(project_root, 'bbox_files')
                os.makedirs(bbox_dir, exist_ok=True)
                
                # Get Downloads path for monitoring
                if os.name == 'nt':  # Windows
                    downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
                else:  # Linux/Mac
                    downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
                
                logging.info(f"BBox folder ready: {bbox_dir}")
                
                # Start monitoring Downloads folder to automatically move geometry files to project bbox_files
                _monitor_and_move_geometry_files(downloads_path, bbox_dir)
        except Exception as e:
            logging.warning(f"Could not create bbox folders: {e}")


def _monitor_and_move_geometry_files(downloads_path: str, bbox_dir: str):
    """Monitor Downloads folder and move geometry*.geojson files to project bbox_files folder."""
    global _geometry_monitor_started
    
    # Only start monitoring once
    with _geometry_monitor_lock:
        if _geometry_monitor_started:
            return
        _geometry_monitor_started = True
    
    def monitor_loop():
        """Background thread that monitors and moves geometry and bbox files."""
        moved_files = set()
        
        while True:
            try:
                # Look for geometry*.geojson files in Downloads (from shapefile export)
                pattern1 = os.path.join(downloads_path, 'geometry_*.geojson')
                files1 = glob.glob(pattern1)
                
                # Look for bbox_*.geojson files in Downloads (from bbox save)
                pattern2 = os.path.join(downloads_path, 'bbox_*.geojson')
                files2 = glob.glob(pattern2)
                
                # Combine both file types
                files = files1 + files2
                
                for file_path in files:
                    if file_path not in moved_files:
                        try:
                            # Wait a moment to ensure file is fully written
                            time.sleep(0.5)
                            
                            # Check if file exists and is readable
                            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                                filename = os.path.basename(file_path)
                                dest_path = os.path.join(bbox_dir, filename)
                                
                                # Move file to bbox_files folder in project
                                if not os.path.exists(dest_path):
                                    shutil.move(file_path, dest_path)
                                    moved_files.add(file_path)
                                    logging.info(f"Moved file to bbox_files folder: {filename}")
                                    
                                    # If it's a bbox_*.geojson file, also convert to shapefile
                                    if filename.startswith('bbox_') and filename.endswith('.geojson'):
                                        try:
                                            from .utils import geojson_to_shapefile
                                            shapefile_path = os.path.join(bbox_dir, filename.replace('.geojson', '.shp'))
                                            if geojson_to_shapefile(dest_path, shapefile_path):
                                                logging.info(f"Converted bbox GeoJSON to shapefile: {shapefile_path}")
                                        except Exception as e:
                                            logging.warning(f"Could not convert bbox to shapefile: {e}")
                        except Exception as e:
                            logging.debug(f"Error moving file {file_path}: {e}")
                
                # Clean up old entries (keep last 100)
                if len(moved_files) > 100:
                    moved_files = set(list(moved_files)[-100:])
                
                # Check every 2 seconds
                time.sleep(2)
            except Exception as e:
                logging.debug(f"Error in file monitor: {e}")
                time.sleep(5)
    
    # Start monitoring in background thread
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    return monitor_thread
    
    logging.info(f"Map selector created: {html_file}")
    return html_file


def open_map_selector(initial_bbox: Optional[Tuple[float, float, float, float]] = None) -> Optional[str]:
    """
    Open the map selector in a browser and return the path to the HTML file.
    
    Args:
        initial_bbox: Optional initial bounding box (lon_min, lat_min, lon_max, lat_max)
    
    Returns:
        Path to the HTML file, or None if folium is not available
    """
    if not FOLIUM_AVAILABLE:
        return None
    
    try:
        html_file = create_map_selector(initial_bbox)
        webbrowser.open(f'file://{html_file}')
        logging.info(f"Opened map selector in browser: {html_file}")
        return html_file
    except Exception as e:
        logging.error(f"Error creating map selector: {e}")
        return None


def get_bbox_from_clipboard() -> Optional[Tuple[float, float, float, float]]:
    """
    Try to get bbox from clipboard (fallback method).
    This is a helper function for when the HTTP server method doesn't work.
    
    Returns:
        Bbox tuple if found in clipboard, None otherwise
    """
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        clipboard_text = root.clipboard_get()
        root.destroy()
        
        # Try to parse as bbox
        parts = clipboard_text.strip().split(',')
        if len(parts) == 4:
            return tuple(map(float, parts))
    except Exception:
        pass
    return None


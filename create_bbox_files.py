"""Create GeoJSON bbox files for all project ideas."""
import json
import os

# Read project ideas
with open('bbox_files/project_ideas.json', 'r') as f:
    data = json.load(f)

# Create bbox_files directory if it doesn't exist
os.makedirs('bbox_files', exist_ok=True)

# Generate GeoJSON file for each project
for project in data['projects']:
    name = project['name']
    bbox = project['bbox']
    lon_min, lat_min, lon_max, lat_max = bbox
    
    # Create safe filename
    safe_name = name.lower().replace(' ', '_').replace('/', '_').replace('\\', '_')
    filename = f'bbox_files/{safe_name}.geojson'
    
    # Create GeoJSON
    geojson = {
        "type": "Feature",
        "properties": {
            "name": name,
            "category": project['category'],
            "description": project['description'],
            "dates": project['dates'],
            "bbox": f"{lon_min},{lat_min},{lon_max},{lat_max}",
            "created": "2025-11-22T00:00:00.000Z"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon_min, lat_min],
                [lon_max, lat_min],
                [lon_max, lat_max],
                [lon_min, lat_max],
                [lon_min, lat_min]
            ]]
        }
    }
    
    # Write file
    with open(filename, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"Created: {filename}")

print(f"\nCreated {len(data['projects'])} bbox files!")


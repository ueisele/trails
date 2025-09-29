# GraphHopper Setup Guide for Norwegian Trail Routing

## Quick Start

### 1. Docker Installation (Recommended)
```bash
# Pull GraphHopper image
docker pull graphhopper/graphhopper:latest

# Create directories
mkdir -p ~/graphhopper/data ~/graphhopper/elevation

# Download Norwegian OSM data
wget -O ~/graphhopper/data/norway-latest.osm.pbf \
  https://download.geofabrik.de/europe/norway-latest.osm.pbf

# Run GraphHopper
docker run -d --name graphhopper \
  -p 8989:8989 \
  -v ~/graphhopper/data:/data \
  -v ~/graphhopper/elevation:/elevation \
  graphhopper/graphhopper:latest \
  --url /data/norway-latest.osm.pbf \
  --profiles hiking,foot
```

### 2. Manual Installation
```bash
# Download GraphHopper
wget https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/8.0/graphhopper-web-8.0.jar

# Prepare configuration
cat > config.yml << 'EOF'
graphhopper:
  datareader.file: norway-latest.osm.pbf
  graph.location: graph-cache

  profiles:
    - name: hiking
      vehicle: foot
      weighting: shortest
      turn_costs: false

    - name: hiking_elevation
      vehicle: foot
      weighting: custom
      custom_model_files: [hiking_elevation.yml]

  elevation:
    provider: multi
    cache_dir: ./elevation-cache/
    dataaccess: RAM_STORE

server:
  application_connectors:
    - type: http
      port: 8989
  request_log:
    appenders: []
EOF

# Run GraphHopper
java -jar graphhopper-web-8.0.jar server config.yml
```

## Integrating Kartverket Elevation Data

### Download Kartverket 10m DEM
```python
#!/usr/bin/env python3
import requests
import rasterio
from rasterio.merge import merge
from pathlib import Path

def download_kartverket_dem(bounds, output_dir):
    """Download Kartverket 10m DEM tiles for given bounds"""

    # WCS request to Kartverket
    wcs_url = "https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm"

    params = {
        'SERVICE': 'WCS',
        'VERSION': '2.0.1',
        'REQUEST': 'GetCoverage',
        'COVERAGEID': 'nhm_dtm_10m',
        'FORMAT': 'image/tiff',
        'SUBSET': f'X({bounds[0]},{bounds[2]})',
        'SUBSET': f'Y({bounds[1]},{bounds[3]})',
        'SUBSETTINGCRS': 'EPSG:4326'
    }

    response = requests.get(wcs_url, params=params, stream=True)

    output_path = Path(output_dir) / 'kartverket_10m.tif'
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path

# Download DEM for Southern Norway
dem_path = download_kartverket_dem(
    [4.5, 57.9, 11.0, 62.5],  # [west, south, east, north]
    './elevation/'
)
```

### Convert to GraphHopper Format
```bash
# Convert Kartverket GeoTIFF to HGT format for GraphHopper
gdal_translate -of SRTMHGT \
  -co COMPRESS=NONE \
  kartverket_10m.tif \
  N59E010.hgt

# Place in GraphHopper elevation directory
mv N59E010.hgt ~/graphhopper/elevation/
```

## Custom Trail Data Import

### Prepare Norwegian Trail Network
```python
#!/usr/bin/env python3
import geopandas as gpd
import osmium
from shapely.geometry import LineString

class TrailHandler(osmium.SimpleHandler):
    """Extract trails from OSM data"""

    def __init__(self):
        super().__init__()
        self.trails = []

    def way(self, w):
        tags = {tag.k: tag.v for tag in w.tags}

        # Check for hiking trails
        if any(key in tags for key in ['highway', 'footway', 'path']):
            if 'sac_scale' in tags or 'trail_visibility' in tags:
                coords = [(n.lon, n.lat) for n in w.nodes]
                if len(coords) >= 2:
                    self.trails.append({
                        'geometry': LineString(coords),
                        'osm_id': w.id,
                        'highway': tags.get('highway'),
                        'sac_scale': tags.get('sac_scale'),
                        'trail_visibility': tags.get('trail_visibility'),
                        'surface': tags.get('surface'),
                        'width': tags.get('width')
                    })

# Process OSM file
handler = TrailHandler()
handler.apply_file('norway-latest.osm.pbf')

# Create GeoDataFrame
gdf = gpd.GeoDataFrame(handler.trails, crs='EPSG:4326')
gdf.to_file('norwegian_trails.gpkg', driver='GPKG')
```

### Import DNT Trail Data
```bash
# Download DNT trails from Kartverket
wget https://nedlasting.geonorge.no/geonorge/Friluftsdata/DNT_stier/GeoJSON/DNT_stier.geojson

# Convert to OSM format for GraphHopper
ogr2ogr -f "OSM" dnt_trails.osm DNT_stier.geojson \
  -sql "SELECT *, 'path' as highway, 'hiking' as foot, \
        CASE \
          WHEN vanskelighetsgrad='Enkel' THEN 'T1' \
          WHEN vanskelighetsgrad='Middels' THEN 'T2' \
          WHEN vanskelighetsgrad='Krevende' THEN 'T3' \
          WHEN vanskelighetsgrad='Ekspert' THEN 'T4' \
        END as sac_scale \
        FROM DNT_stier"

# Merge with OSM data
osmconvert norway-latest.osm.pbf dnt_trails.osm -o=norway_with_dnt.osm.pbf
```

## Custom Routing Profiles

### Hiking with Elevation Profile
```yaml
# hiking_elevation.yml
priority:
  - if: sac_scale == T1
    multiply by: 1.0
  - else if: sac_scale == T2
    multiply by: 0.9
  - else if: sac_scale == T3
    multiply by: 0.7
  - else if: sac_scale == T4
    multiply by: 0.5
  - else if: sac_scale == T5
    multiply by: 0.3
  - else if: sac_scale == T6
    multiply by: 0.1

speed:
  - if: sac_scale == T1
    limit to: 5
  - else if: sac_scale == T2
    limit to: 4
  - else if: sac_scale == T3
    limit to: 3
  - else if: sac_scale == T4
    limit to: 2
  - else:
    limit to: 1

# Elevation penalties
distance_influence: 50
elevation_influence: 150

# Prefer marked trails
areas:
  - if: norwegian_trail == DNT
    multiply priority by: 1.5
```

## API Usage Examples

### Basic Routing Request
```python
import requests

def calculate_route(start_point, end_point):
    """Calculate hiking route between two points"""

    url = "http://localhost:8989/route"

    params = {
        'point': [
            f"{start_point[1]},{start_point[0]}",  # lat,lon
            f"{end_point[1]},{end_point[0]}"
        ],
        'profile': 'hiking_elevation',
        'elevation': 'true',
        'instructions': 'true',
        'points_encoded': 'false',
        'locale': 'en',
        'details': ['surface', 'sac_scale', 'trail_visibility']
    }

    response = requests.get(url, params=params)
    return response.json()

# Example: Oslo to nearby hiking area
route = calculate_route(
    [10.7522, 59.9139],  # Oslo
    [10.6631, 60.1285]   # Nordmarka
)

print(f"Distance: {route['paths'][0]['distance']}m")
print(f"Time: {route['paths'][0]['time'] / 1000 / 60:.1f} minutes")
print(f"Ascent: {route['paths'][0]['ascend']}m")
print(f"Descent: {route['paths'][0]['descend']}m")
```

### Snap to Trail Network
```python
def snap_to_trail(points, max_distance=50):
    """Snap GPS points to nearest trail"""

    url = "http://localhost:8989/route"

    params = {
        'point': [f"{p[1]},{p[0]}" for p in points],
        'profile': 'hiking',
        'snap_preventions': ['ferry', 'motorway'],
        'point_hint': ['trail'] * len(points),
        'heading': [0] * len(points),
        'heading_penalty': 120,
        'pass_through': 'true',
        'algorithm': 'round_trip',
        'points_encoded': 'false'
    }

    response = requests.get(url, params=params)
    route = response.json()

    # Extract snapped coordinates
    if 'paths' in route:
        coordinates = route['paths'][0]['points']['coordinates']
        return [(lon, lat) for lon, lat, *_ in coordinates]

    return None
```

### Elevation Profile Extraction
```python
def get_elevation_profile(route_response):
    """Extract elevation profile from route"""

    if 'paths' not in route_response:
        return None

    path = route_response['paths'][0]
    points = path['points']['coordinates']

    profile = []
    cumulative_distance = 0

    for i, (lon, lat, ele) in enumerate(points):
        if i > 0:
            prev_lon, prev_lat, _ = points[i-1]
            # Calculate distance (simplified)
            distance = ((lon - prev_lon)**2 + (lat - prev_lat)**2)**0.5 * 111000
            cumulative_distance += distance

        profile.append({
            'distance': cumulative_distance,
            'elevation': ele,
            'lat': lat,
            'lon': lon
        })

    return profile
```

## Production Deployment

### Docker Compose Setup
```yaml
# docker-compose.yml
version: '3.8'

services:
  graphhopper:
    image: graphhopper/graphhopper:latest
    container_name: graphhopper_norway
    ports:
      - "8989:8989"
    volumes:
      - ./data:/data
      - ./elevation:/elevation
      - ./config:/config
    environment:
      - JAVA_OPTS=-Xmx4g -Xms2g
    command: >
      --config /config/config.yml
      --url /data/norway_with_trails.osm.pbf
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - graphhopper
```

### Nginx Configuration
```nginx
upstream graphhopper {
    server graphhopper:8989;
}

server {
    listen 443 ssl http2;
    server_name routing.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # API endpoints
    location /route {
        proxy_pass http://graphhopper;
        proxy_set_header Host $host;

        # Cache responses
        proxy_cache_valid 200 1h;
        proxy_cache_key "$request_method$request_uri$request_body";
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
}
```

## Performance Optimization

### Memory Configuration
```bash
# For large networks (all of Norway)
export JAVA_OPTS="-Xmx8g -Xms4g -XX:+UseG1GC"

# Enable memory-mapped files
echo "graph.dataaccess=MMAP" >> config.properties
```

### Preprocessing for Speed
```bash
# Create contraction hierarchies for faster routing
java -cp graphhopper.jar com.graphhopper.tools.Prepare \
  --graph-location ./graph-cache \
  --prepare.ch.weightings shortest \
  --prepare.ch.edge_based false
```

## Monitoring and Maintenance

### Health Check Endpoint
```python
def check_graphhopper_health():
    """Monitor GraphHopper status"""

    try:
        response = requests.get("http://localhost:8989/health")
        data = response.json()

        return {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'version': data.get('version'),
            'profiles': data.get('profiles'),
            'graph_loaded': data.get('graph_loaded')
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
```

### Automated Updates
```bash
#!/bin/bash
# update_trails.sh - Weekly trail data update

# Download latest OSM data
wget -O norway-latest-new.osm.pbf \
  https://download.geofabrik.de/europe/norway-latest.osm.pbf

# Download latest DNT trails
wget -O dnt-latest.geojson \
  https://nedlasting.geonorge.no/geonorge/Friluftsdata/DNT_stier/GeoJSON/DNT_stier.geojson

# Merge datasets
osmconvert norway-latest-new.osm.pbf dnt-latest.osm \
  -o=norway_updated.osm.pbf

# Rebuild graph
java -jar graphhopper.jar import \
  --input norway_updated.osm.pbf \
  --profiles hiking,foot

# Restart service
docker-compose restart graphhopper
```

## Troubleshooting

### Common Issues

1. **Out of Memory**
```bash
# Increase heap size
export JAVA_OPTS="-Xmx16g"
```

2. **Slow Routing**
```bash
# Enable contraction hierarchies
echo "prepare.ch.weightings=shortest" >> config.properties
```

3. **Missing Elevation Data**
```bash
# Check elevation cache
ls -la ./elevation-cache/
# Re-download if missing
wget https://elevation.example.com/N60E010.hgt
```

4. **Trail Not Snapping**
```python
# Increase snap distance
params['max_visited_nodes'] = 10000
params['heading_penalty'] = 30
```

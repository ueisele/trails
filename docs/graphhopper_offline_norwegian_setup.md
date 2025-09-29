# GraphHopper Offline Setup with Norwegian Data

## Overview

Yes, GraphHopper can run **completely offline** with Norwegian maps, trails, land cover, and elevation data. Once configured, it requires no internet connection for routing.

## Complete Offline Setup Guide

### Step 1: Prepare Norwegian Data Package

#### 1.1 Download Base OSM Data
```bash
# Create data directory
mkdir -p ~/graphhopper-offline/data
cd ~/graphhopper-offline/data

# Download Norway OSM extract
wget https://download.geofabrik.de/europe/norway-latest.osm.pbf
```

#### 1.2 Download and Merge Norwegian Trail Data
```bash
# Download DNT trails from Geonorge
wget https://nedlasting.geonorge.no/geonorge/Friluftsdata/DNT_stier/GeoJSON/DNT_stier.geojson

# Download additional trail data
wget https://nedlasting.geonorge.no/geonorge/Friluftsdata/TuristiFjell/GeoJSON/TuristiFjell.geojson

# Convert to OSM format
ogr2ogr -f "OSM" dnt_trails.osm DNT_stier.geojson \
  -sql "SELECT *, \
    'path' as highway, \
    'yes' as foot, \
    'DNT' as operator, \
    CASE \
      WHEN vanskelighetsgrad='Enkel' THEN 'T1' \
      WHEN vanskelighetsgrad='Middels' THEN 'T2' \
      WHEN vanskelighetsgrad='Krevende' THEN 'T3' \
      WHEN vanskelighetsgrad='Ekspert' THEN 'T4' \
    END as sac_scale \
    FROM DNT_stier"

# Merge with OSM data
osmium merge norway-latest.osm.pbf dnt_trails.osm -o norway-with-trails.osm.pbf
```

#### 1.3 Add Land Cover Data (AR5/AR50)
```python
#!/usr/bin/env python3
# add_landcover_to_osm.py
import osmium
import geopandas as gpd
from shapely.geometry import Point

class LandCoverHandler(osmium.SimpleHandler):
    """Add AR5 land cover tags to OSM ways"""

    def __init__(self, ar5_data):
        super().__init__()
        self.ar5 = gpd.read_file(ar5_data)
        self.ar5 = self.ar5.to_crs('EPSG:4326')
        self.writer = None

    def way(self, w):
        # Get way center point
        if len(w.nodes) > 0:
            center_lat = sum(n.lat for n in w.nodes) / len(w.nodes)
            center_lon = sum(n.lon for n in w.nodes) / len(w.nodes)
            point = Point(center_lon, center_lat)

            # Find intersecting land cover
            intersects = self.ar5[self.ar5.contains(point)]
            if not intersects.empty:
                land_cover = intersects.iloc[0]

                # Add land cover tags
                tags = dict(w.tags)
                tags['ar5:type'] = str(land_cover['artype'])
                tags['ar5:surface'] = self.get_surface(land_cover['artype'])

                # Write modified way
                self.writer.add_way(w.replace(tags=tags))

    def get_surface(self, artype):
        surface_map = {
            30: 'forest_floor',
            50: 'grass',
            53: 'wetland',
            60: 'bog',
            70: 'rock'
        }
        return surface_map.get(artype, 'ground')

# Download AR5 data
wget https://nedlasting.geonorge.no/geonorge/Basisdata/ArealressursAR5/GPKG/ArealressursAR5.gpkg

# Apply land cover to OSM
python3 add_landcover_to_osm.py \
  --input norway-with-trails.osm.pbf \
  --ar5 ArealressursAR5.gpkg \
  --output norway-complete.osm.pbf
```

### Step 2: Prepare Offline Elevation Data

#### 2.1 Download Kartverket 10m DEM
```python
#!/usr/bin/env python3
# download_kartverket_dem.py
import requests
import os
from osgeo import gdal

def download_norway_dem(output_dir):
    """Download complete Norwegian DEM for offline use"""

    # Define tiles covering Norway
    tiles = []
    for lat in range(58, 72):  # Norway latitude range
        for lon in range(4, 32):   # Norway longitude range
            tiles.append((lat, lon))

    os.makedirs(output_dir, exist_ok=True)

    for lat, lon in tiles:
        filename = f"dem_{lat}_{lon}.tif"
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            print(f"Skipping existing: {filename}")
            continue

        # Download from Kartverket WCS
        wcs_url = "https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm"
        params = {
            'SERVICE': 'WCS',
            'VERSION': '2.0.1',
            'REQUEST': 'GetCoverage',
            'COVERAGEID': 'nhm_dtm_10m',
            'FORMAT': 'image/tiff',
            'SUBSET': f'Lat({lat},{lat+1})',
            'SUBSET': f'Long({lon},{lon+1})'
        }

        print(f"Downloading: {filename}")
        response = requests.get(wcs_url, params=params, stream=True)

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    # Merge all tiles into single VRT for efficiency
    tif_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith('.tif')]
    vrt_path = os.path.join(output_dir, 'norway_dem.vrt')
    gdal.BuildVRT(vrt_path, tif_files)

    print(f"Created VRT: {vrt_path}")
    return vrt_path

# Download complete DEM
download_norway_dem('~/graphhopper-offline/elevation')
```

#### 2.2 Convert DEM for GraphHopper
```bash
# GraphHopper expects specific elevation file structure
cd ~/graphhopper-offline/elevation

# Convert to GraphHopper-compatible format
for file in dem_*.tif; do
    lat=$(echo $file | cut -d_ -f2)
    lon=$(echo $file | cut -d_ -f3 | cut -d. -f1)

    # Create HGT filename (SRTM format)
    if [ $lat -ge 0 ]; then
        ns="N"
    else
        ns="S"
        lat=$((0 - lat))
    fi

    if [ $lon -ge 0 ]; then
        ew="E"
    else
        ew="W"
        lon=$((0 - lon))
    fi

    hgt_name=$(printf "%s%02d%s%03d.hgt" $ns $lat $ew $lon)

    # Convert to HGT format
    gdal_translate -of SRTMHGT -ot Int16 $file $hgt_name
done
```

### Step 3: Configure GraphHopper for Offline Use

#### 3.1 Create Configuration File
```yaml
# config-offline.yml
graphhopper:
  # Data file
  datareader.file: norway-complete.osm.pbf

  # Offline graph location
  graph.location: graph-norway-offline

  # Disable online services
  routing.ch.disabling_allowed: true
  elevation.cache_dir: ./elevation
  elevation.provider: srtm
  elevation.dataaccess: MMAP  # Memory-mapped for large files

  # Norwegian hiking profiles
  profiles:
    - name: norwegian_hiking
      vehicle: foot
      weighting: custom
      custom_model_files: [norwegian_hiking.yml]

    - name: winter_skiing
      vehicle: foot
      weighting: custom
      custom_model_files: [winter_skiing.yml]

    - name: family_hiking
      vehicle: foot
      weighting: custom
      custom_model_files: [family_hiking.yml]

  # Import settings
  import.osm.ignored_highways: ""  # Import all paths
  graph.encoded_values: |
    road_class,
    road_environment,
    surface,
    sac_scale,
    hiking_rating,
    horse_rating,
    foot_network,
    ar5_type,
    ar5_surface,
    operator,
    seasonal,
    winter_accessible

  # Performance for offline
  prepare.min_network_size: 0
  prepare.ch.weightings: no  # Disable CH for flexibility
  index.max_region_search: 100

  # Disable online features
  web.disable_vehicle_param: false
  routing.non_ch.max_waypoint_distance: -1

# Server settings for offline use
server:
  application_connectors:
    - type: http
      port: 8989
      bind_host: 0.0.0.0  # Allow local network access

  # Disable external calls
  request_log:
    appenders: []

  # No external services
  gzip:
    enabled: true

  cors:
    allowed_origins: ["*"]  # For local network
```

#### 3.2 Custom Norwegian Profiles
```yaml
# norwegian_hiking.yml
priority:
  # Prefer DNT trails
  - if: operator == DNT
    multiply by: 1.5
  - else if: operator == Kommune
    multiply by: 1.3

  # Trail difficulty
  - if: sac_scale == T1
    multiply by: 1.0
  - else if: sac_scale == T2
    multiply by: 0.9
  - else if: sac_scale == T3
    multiply by: 0.7
  - else if: sac_scale == T4
    multiply by: 0.4
  - else if: sac_scale == T5|T6
    multiply by: 0.1

  # Land cover preferences
  - if: ar5_type == 30|31|32  # Forest
    multiply by: 1.1
  - else if: ar5_type == 50|51  # Open ground
    multiply by: 1.0
  - else if: ar5_type == 53|60  # Wetland/bog
    multiply by: 0.3
  - else if: ar5_type == 70  # Rock
    multiply by: 0.6

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

distance_influence: 50
elevation_influence: 70
```

### Step 4: Build Offline GraphHopper Package

#### 4.1 Import and Process Data
```bash
cd ~/graphhopper-offline

# Download GraphHopper
wget https://github.com/graphhopper/graphhopper/releases/download/8.0/graphhopper-web-8.0.jar

# Import Norwegian data (this takes time but only needs to be done once)
java -Xmx8g -jar graphhopper-web-8.0.jar import \
  --config config-offline.yml \
  --input data/norway-complete.osm.pbf \
  --vehicle foot,hike \
  --elevation-provider srtm \
  --elevation-cache-dir ./elevation

# The graph is now built and stored in ./graph-norway-offline
```

#### 4.2 Create Portable Package
```bash
# Create offline package
tar -czf graphhopper-norway-offline.tar.gz \
  graphhopper-web-8.0.jar \
  config-offline.yml \
  graph-norway-offline/ \
  elevation/ \
  *.yml

# This package can be deployed anywhere without internet
```

### Step 5: Run Offline GraphHopper

#### 5.1 Standalone Server
```bash
# Extract package on target machine
tar -xzf graphhopper-norway-offline.tar.gz

# Run completely offline
java -Xmx4g -jar graphhopper-web-8.0.jar \
  server config-offline.yml \
  --graph-location ./graph-norway-offline \
  --elevation-cache-dir ./elevation

# Access at http://localhost:8989 - works without internet!
```

#### 5.2 Docker Deployment
```dockerfile
# Dockerfile for offline GraphHopper
FROM openjdk:17-slim

WORKDIR /graphhopper

# Copy pre-built graph and elevation data
COPY graphhopper-web-8.0.jar ./
COPY config-offline.yml ./
COPY graph-norway-offline/ ./graph-norway-offline/
COPY elevation/ ./elevation/
COPY *.yml ./

# No internet needed from here
EXPOSE 8989

CMD ["java", "-Xmx4g", "-jar", "graphhopper-web-8.0.jar", \
     "server", "config-offline.yml"]
```

```yaml
# docker-compose-offline.yml
version: '3.8'

services:
  graphhopper-offline:
    build: .
    container_name: graphhopper-norway-offline
    ports:
      - "8989:8989"
    volumes:
      - ./graph-norway-offline:/graphhopper/graph-norway-offline:ro
      - ./elevation:/graphhopper/elevation:ro
    environment:
      - JAVA_OPTS=-Xmx4g -Xms2g
    restart: unless-stopped
    # No external networks needed
    network_mode: bridge
```

### Step 6: Offline API Usage

#### 6.1 Basic Routing (No Internet Required)
```python
import requests
import json

class OfflineGraphHopper:
    def __init__(self, host="localhost", port=8989):
        self.base_url = f"http://{host}:{port}"

    def route(self, points, profile="norwegian_hiking"):
        """Calculate route completely offline"""

        # Format points
        point_params = []
        for lat, lon in points:
            point_params.append(f"point={lat},{lon}")

        # Build request URL (local only)
        url = f"{self.base_url}/route"
        params = "&".join(point_params) + f"&profile={profile}&elevation=true"

        # Make request to local server
        response = requests.get(f"{url}?{params}")
        return response.json()

    def check_status(self):
        """Verify offline server is running"""
        try:
            response = requests.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False

# Use offline routing
router = OfflineGraphHopper()
if router.check_status():
    route = router.route([
        (59.9139, 10.7522),  # Oslo
        (60.1285, 10.6631)   # Nordmarka
    ])
    print(f"Distance: {route['paths'][0]['distance']}m")
    print("Routing works completely offline!")
```

#### 6.2 Offline Mobile App Integration
```javascript
// React Native offline routing
class OfflineRouter {
    constructor() {
        // Use local GraphHopper instance
        this.baseUrl = 'http://192.168.1.100:8989';  // Local network
    }

    async calculateRoute(waypoints) {
        // No internet required - uses local server
        const points = waypoints.map(p => `point=${p.lat},${p.lon}`).join('&');
        const url = `${this.baseUrl}/route?${points}&profile=norwegian_hiking`;

        const response = await fetch(url);
        return response.json();
    }
}
```

## Offline Data Updates

### Periodic Update Process
```bash
#!/bin/bash
# update_offline_data.sh

# This script can be run when internet IS available to update the offline package

# Download latest data
wget -N https://download.geofabrik.de/europe/norway-latest.osm.pbf
wget -N https://nedlasting.geonorge.no/geonorge/Friluftsdata/DNT_stier/GeoJSON/DNT_stier.geojson

# Rebuild graph
java -jar graphhopper-web-8.0.jar import \
  --config config-offline.yml \
  --input norway-latest.osm.pbf

# Create new offline package
tar -czf graphhopper-norway-offline-$(date +%Y%m%d).tar.gz \
  graph-norway-offline/ elevation/ *.yml

echo "New offline package created"
```

## Storage Requirements

### Disk Space Needed
```
OSM Data:           ~500 MB  (norway-complete.osm.pbf)
Graph Database:     ~2-3 GB  (graph-norway-offline/)
Elevation Data:     ~5-10 GB (Kartverket 10m DEM)
-------------------------------------------
Total:             ~8-14 GB
```

### Memory Requirements
```
Import/Build:       8 GB RAM recommended
Runtime:            2-4 GB RAM
Mobile Devices:     1-2 GB RAM minimum
```

## Offline Capabilities

### What Works Offline ✅
- Complete routing calculations
- Snap-to-trail with all Norwegian trails
- Elevation profiles from Kartverket DEM
- Land cover aware routing (AR5/AR50)
- Seasonal routing profiles
- Turn-by-turn instructions
- Alternative route calculation
- Custom routing profiles
- Multi-waypoint routing

### What Doesn't Work Offline ❌
- Real-time traffic (not applicable for trails)
- Weather-based routing adjustments
- Live trail condition updates
- New trail additions without rebuild

## Deployment Options

### 1. Raspberry Pi Server
```bash
# Perfect for cabin/remote location
# Install on Raspberry Pi 4 (8GB recommended)
scp graphhopper-norway-offline.tar.gz pi@cabin-server:~
ssh pi@cabin-server
tar -xzf graphhopper-norway-offline.tar.gz
java -Xmx3g -jar graphhopper-web-8.0.jar server config-offline.yml
```

### 2. Android Device
```kotlin
// Embed in Android app
class OfflineRoutingService {
    init {
        // Copy graph files from assets
        copyGraphFiles()
        // Start embedded GraphHopper
        startGraphHopper()
    }
}
```

### 3. Docker Swarm for Organizations
```bash
# Deploy to multiple offline locations
docker stack deploy -c docker-compose-offline.yml gh-offline
```

## Advantages of Offline GraphHopper

1. **No Internet Dependency**: Works in remote areas
2. **Fast Response**: No network latency
3. **Data Privacy**: All routing calculations local
4. **Predictable Performance**: No external service issues
5. **Customizable**: Full control over routing rules
6. **Cost Effective**: No API fees or bandwidth costs

## Conclusion

GraphHopper can run completely offline with full Norwegian data including:
- ✅ All trails (OSM + DNT + custom)
- ✅ Kartverket elevation (10m DEM)
- ✅ Land cover data (AR5/AR50)
- ✅ Custom routing profiles
- ✅ Seasonal adaptations

Once set up, it requires **zero internet connectivity** for routing operations, making it perfect for:
- Remote cabins
- Mobile apps with offline mode
- Privacy-conscious deployments
- High-performance local routing
- Emergency/backup systems

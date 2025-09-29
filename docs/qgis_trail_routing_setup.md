# QGIS Trail Routing Setup with Norwegian Data

## Overview

QGIS provides a complete GIS platform for trail routing analysis with extensive plugin support and PostGIS/pgRouting integration. This guide covers setup for Norwegian trail planning with Kartverket data.

## Installation

### 1. QGIS Installation (Ubuntu/Debian)
```bash
# Add QGIS repository
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key 51F523511C7028C3
sudo add-apt-repository "deb https://qgis.org/ubuntu-ltr $(lsb_release -cs) main"

# Install QGIS with all features
sudo apt update
sudo apt install qgis qgis-plugin-grass python3-qgis

# Install PostgreSQL and PostGIS
sudo apt install postgresql postgis postgresql-14-pgrouting

# Install additional tools
sudo apt install gdal-bin python3-gdal osm2pgsql
```

### 2. Database Setup
```sql
-- Create routing database
CREATE DATABASE trail_routing;
\c trail_routing;

-- Enable extensions
CREATE EXTENSION postgis;
CREATE EXTENSION pgrouting;
CREATE EXTENSION hstore;
CREATE EXTENSION postgis_topology;

-- Create schema for trails
CREATE SCHEMA trails;
CREATE SCHEMA elevation;
```

## Essential QGIS Plugins

### Install via Plugin Manager
1. **pgRouting Layer** - Database routing integration
2. **QNEAT3** - Network analysis toolkit
3. **ORS Tools** - OpenRouteService integration
4. **QuickOSM** - OSM data downloader
5. **Terrain Analysis** - Elevation processing
6. **GRASS** - Advanced GIS algorithms

```python
# Automated plugin installation
import pyplugin_installer
from qgis.utils import plugins

plugin_list = [
    'pgRoutingLayer',
    'QNEAT3',
    'ORStools',
    'QuickOSM',
    'profiletool',
    'processing_saga'
]

installer = pyplugin_installer.instance()
for plugin_name in plugin_list:
    installer.installPlugin(plugin_name)
```

## Kartverket Data Integration

### 1. Add WMS/WMTS Services
```python
# PyQGIS script to add Kartverket services
from qgis.core import QgsRasterLayer, QgsProject

# Topographic basemap
topo_wms = QgsRasterLayer(
    'contextualWMSLegend=0&crs=EPSG:25833&dpiMode=7&'
    'featureCount=10&format=image/png&layers=topo4&'
    'styles=&url=https://wms.geonorge.no/skwms1/wms.topo4',
    'Kartverket Topographic',
    'wms'
)

# Elevation data (10m DEM)
dem_wcs = QgsRasterLayer(
    'contextualWMSLegend=0&crs=EPSG:25833&dpiMode=7&'
    'identifier=nhm_dtm_10m&'
    'url=https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm',
    'Kartverket 10m DEM',
    'wcs'
)

# Hiking trails
trails_wfs = QgsVectorLayer(
    'https://wfs.geonorge.no/skwms1/wfs.friluftsruter?'
    'service=WFS&version=2.0.0&request=GetFeature&'
    'typeName=app:Sti&srsName=EPSG:25833',
    'Norwegian Hiking Trails',
    'WFS'
)

# Add layers to project
QgsProject.instance().addMapLayers([topo_wms, dem_wcs, trails_wfs])
```

### 2. Download and Process Trail Data
```python
import processing
from qgis.core import QgsVectorLayer, QgsFeature

def import_norwegian_trails():
    """Import and process Norwegian trail network"""

    # Download DNT trails
    dnt_url = 'https://nedlasting.geonorge.no/geonorge/Friluftsdata/DNT_stier/GPKG/DNT_stier.gpkg'

    # Load into QGIS
    dnt_layer = QgsVectorLayer(dnt_url, 'DNT Trails', 'ogr')

    # Clean geometry
    result = processing.run("native:fixgeometries", {
        'INPUT': dnt_layer,
        'OUTPUT': 'memory:fixed_trails'
    })

    fixed_layer = result['OUTPUT']

    # Snap endpoints for network connectivity
    snapped = processing.run("native:snapgeometries", {
        'INPUT': fixed_layer,
        'REFERENCE_LAYER': fixed_layer,
        'TOLERANCE': 10,
        'BEHAVIOR': 1,  # Snap to vertices and segments
        'OUTPUT': 'memory:snapped_trails'
    })

    return snapped['OUTPUT']

# Process trails
trail_network = import_norwegian_trails()
```

## Creating Routable Network

### 1. Network Topology Creation
```python
def create_routable_network(trail_layer):
    """Create pgRouting-compatible network"""

    # Add required fields
    processing.run("native:addfieldtoattributestable", {
        'INPUT': trail_layer,
        'FIELD_NAME': 'source',
        'FIELD_TYPE': 1,  # Integer
        'OUTPUT': 'memory:with_source'
    })

    processing.run("native:addfieldtoattributestable", {
        'INPUT': 'memory:with_source',
        'FIELD_NAME': 'target',
        'FIELD_TYPE': 1,
        'OUTPUT': 'memory:with_target'
    })

    # Split lines at intersections
    split = processing.run("native:splitwithlines", {
        'INPUT': 'memory:with_target',
        'LINES': 'memory:with_target',
        'OUTPUT': 'memory:split_network'
    })

    # Create nodes at endpoints
    nodes = processing.run("native:extractspecificvertices", {
        'INPUT': split['OUTPUT'],
        'VERTICES': '0,-1',  # First and last vertices
        'OUTPUT': 'memory:nodes'
    })

    return split['OUTPUT'], nodes['OUTPUT']

network_edges, network_nodes = create_routable_network(trail_network)
```

### 2. Import to PostGIS
```bash
# Import trail network to PostGIS
ogr2ogr -f PostgreSQL \
  "PG:dbname=trail_routing user=postgres" \
  norwegian_trails.gpkg \
  -nln trails.edges \
  -lco GEOMETRY_NAME=geom \
  -lco FID=gid \
  -overwrite

# Create pgRouting topology
psql -d trail_routing << EOF
-- Add pgRouting columns
ALTER TABLE trails.edges ADD COLUMN source INTEGER;
ALTER TABLE trails.edges ADD COLUMN target INTEGER;
ALTER TABLE trails.edges ADD COLUMN cost DOUBLE PRECISION;
ALTER TABLE trails.edges ADD COLUMN reverse_cost DOUBLE PRECISION;

-- Build topology
SELECT pgr_createTopology('trails.edges', 0.0001, 'geom', 'gid');

-- Analyze network
SELECT pgr_analyzeGraph('trails.edges', 0.0001, 'geom', 'gid');
EOF
```

## Routing with pgRouting

### 1. Basic Route Calculation
```sql
-- Find shortest path between two points
WITH route AS (
    SELECT * FROM pgr_dijkstra(
        'SELECT gid AS id,
                source,
                target,
                ST_Length(geom::geography) AS cost,
                ST_Length(geom::geography) AS reverse_cost
         FROM trails.edges',
        100,  -- Start node
        500,  -- End node
        directed := false
    )
)
SELECT
    r.seq,
    r.node,
    r.edge,
    r.cost,
    e.geom,
    e.trail_name,
    e.difficulty
FROM route r
LEFT JOIN trails.edges e ON r.edge = e.gid
ORDER BY r.seq;
```

### 2. Elevation-Aware Routing
```python
def calculate_elevation_cost(edge_layer, dem_layer):
    """Add elevation-based cost to edges"""

    # Sample elevation along trails
    result = processing.run("native:extractzvalues", {
        'INPUT': edge_layer,
        'RASTER': dem_layer,
        'COLUMN_PREFIX': 'elev_',
        'OUTPUT': 'memory:with_elevation'
    })

    edges_with_elev = result['OUTPUT']

    # Calculate slope and update cost
    edges_with_elev.startEditing()

    for feature in edges_with_elev.getFeatures():
        geom = feature.geometry()
        length = geom.length()

        # Get elevation at start and end
        points = geom.asPolyline()
        if len(points) >= 2:
            start_elev = feature['elev_1']
            end_elev = feature['elev_2']

            # Calculate slope
            slope = abs(end_elev - start_elev) / length if length > 0 else 0

            # Update cost based on slope
            base_cost = length
            if slope > 0.15:  # Steep
                cost_multiplier = 2.0
            elif slope > 0.10:  # Moderate
                cost_multiplier = 1.5
            else:
                cost_multiplier = 1.0

            feature['cost'] = base_cost * cost_multiplier
            edges_with_elev.updateFeature(feature)

    edges_with_elev.commitChanges()
    return edges_with_elev
```

## QNEAT3 Network Analysis

### 1. Service Area Analysis
```python
# Find all trails reachable within 2 hours
result = processing.run("qneat3:isoareaaspolygonsfrompoint", {
    'INPUT': network_edges,
    'START_POINT': '10.7522,59.9139',  # Oslo
    'MAX_DIST': 7200,  # 2 hours in seconds
    'CELL_SIZE': 100,
    'STRATEGY': 0,  # Shortest path
    'OUTPUT': 'memory:service_area'
})

# Visualize service area
service_area = result['OUTPUT']
QgsProject.instance().addMapLayer(service_area)
```

### 2. Origin-Destination Matrix
```python
# Calculate distances between multiple trailheads
result = processing.run("qneat3:odmatrixfromlayersaslines", {
    'INPUT': network_edges,
    'FROM_POINT_LAYER': trailheads_layer,
    'TO_POINT_LAYER': destinations_layer,
    'STRATEGY': 0,
    'OUTPUT': 'memory:od_matrix'
})
```

## Custom Processing Scripts

### Trail Difficulty Analysis
```python
from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource
from qgis.PyQt.QtCore import QCoreApplication

class TrailDifficultyAnalysis(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'trail_difficulty_analysis'

    def displayName(self):
        return 'Analyze Trail Difficulty'

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)

        # Analyze trail characteristics
        for feature in source.getFeatures():
            geometry = feature.geometry()

            # Calculate metrics
            length = geometry.length()
            vertices = len(geometry.asPolyline())
            sinuosity = length / geometry.boundingBox().width()

            # Get elevation profile
            elevation_gain = self.calculate_elevation_gain(geometry)

            # Determine difficulty
            difficulty = self.classify_difficulty(
                length, elevation_gain, sinuosity
            )

            feature['calculated_difficulty'] = difficulty

        return {self.OUTPUT: dest_id}

    def calculate_elevation_gain(self, geometry):
        # Implementation here
        pass

    def classify_difficulty(self, length, elevation, sinuosity):
        if elevation > 1000 or length > 20000:
            return 'Expert'
        elif elevation > 500 or length > 10000:
            return 'Difficult'
        elif elevation > 200 or length > 5000:
            return 'Moderate'
        else:
            return 'Easy'
```

## Web Deployment with QGIS Server

### 1. QGIS Server Setup
```bash
# Install QGIS Server
sudo apt install qgis-server apache2 libapache2-mod-fcgid

# Configure Apache
cat > /etc/apache2/sites-available/qgis-server.conf << 'EOF'
<VirtualHost *:80>
    ServerName trails.example.com

    FcgidIOTimeout 120
    FcgidInitialEnv LC_ALL "en_US.UTF-8"
    FcgidInitialEnv QGIS_SERVER_LOG_LEVEL "0"
    FcgidInitialEnv QGIS_SERVER_PARALLEL_RENDERING "1"

    ScriptAlias /qgis/ /usr/lib/cgi-bin/qgis_mapserv.fcgi

    <Directory "/usr/lib/cgi-bin/">
        AllowOverride None
        Options +ExecCGI -MultiViews +FollowSymLinks
        Require all granted
    </Directory>
</VirtualHost>
EOF

sudo a2ensite qgis-server
sudo systemctl restart apache2
```

### 2. Publishing Trail Routes
```python
def publish_trail_project():
    """Prepare QGIS project for web serving"""

    project = QgsProject.instance()

    # Configure WMS capabilities
    project.writeEntry("WMSServiceTitle", "/", "Norwegian Trail Routing")
    project.writeEntry("WMSServiceAbstract", "/", "Trail routing service")
    project.writeEntry("WMSKeywordList", "/", ["trails", "hiking", "norway"])

    # Enable WFS for trail data
    project.writeEntry("WFSLayers", "/", ["trail_network", "trailheads"])

    # Save project
    project.write('/var/www/qgis/trail_routing.qgs')

# Access services at:
# WMS: http://trails.example.com/qgis/?SERVICE=WMS&REQUEST=GetCapabilities
# WFS: http://trails.example.com/qgis/?SERVICE=WFS&REQUEST=GetCapabilities
```

## Python API for Routing

### Flask API Wrapper
```python
from flask import Flask, request, jsonify
from qgis.core import QgsApplication, QgsProject
import processing

app = Flask(__name__)

# Initialize QGIS
QgsApplication.setPrefixPath('/usr', True)
qgs = QgsApplication([], False)
qgs.initQgis()

@app.route('/api/route', methods=['POST'])
def calculate_route():
    """REST API for trail routing"""

    data = request.json
    start = data['start']  # [lon, lat]
    end = data['end']

    # Run pgRouting through QGIS
    result = processing.run("pgRouting:dijkstra_shortest_path", {
        'DATABASE': 'trail_routing',
        'SCHEMA': 'trails',
        'TABLE': 'edges',
        'START_POINT': f'{start[0]},{start[1]}',
        'END_POINT': f'{end[0]},{end[1]}'
    })

    # Extract route geometry
    route_layer = result['OUTPUT']
    features = list(route_layer.getFeatures())

    route_geom = {
        'type': 'LineString',
        'coordinates': []
    }

    for feature in features:
        geom = feature.geometry()
        for point in geom.asPolyline():
            route_geom['coordinates'].append([point.x(), point.y()])

    return jsonify({
        'route': route_geom,
        'distance': sum(f['cost'] for f in features),
        'segments': len(features)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## Performance Optimization

### 1. Spatial Indexing
```sql
-- Create spatial indexes
CREATE INDEX idx_edges_geom ON trails.edges USING GIST (geom);
CREATE INDEX idx_edges_source ON trails.edges (source);
CREATE INDEX idx_edges_target ON trails.edges (target);

-- Cluster table by geometry
CLUSTER trails.edges USING idx_edges_geom;
ANALYZE trails.edges;
```

### 2. Caching Strategies
```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_route(start_hash, end_hash):
    """Cache frequently requested routes"""
    # Route calculation here
    pass

def get_route(start, end):
    start_hash = hashlib.md5(f"{start[0]},{start[1]}".encode()).hexdigest()
    end_hash = hashlib.md5(f"{end[0]},{end[1]}".encode()).hexdigest()
    return cached_route(start_hash, end_hash)
```

## Automation Scripts

### Daily Data Updates
```bash
#!/bin/bash
# update_trail_data.sh

# Download latest trail data
wget -O /tmp/trails_latest.gpkg \
  https://nedlasting.geonorge.no/geonorge/Friluftsdata/DNT_stier/GPKG/DNT_stier.gpkg

# Import to PostGIS
ogr2ogr -f PostgreSQL \
  "PG:dbname=trail_routing" \
  /tmp/trails_latest.gpkg \
  -nln trails.edges_new \
  -overwrite

# Update routing topology
psql -d trail_routing << EOF
BEGIN;
DROP TABLE IF EXISTS trails.edges_old;
ALTER TABLE trails.edges RENAME TO edges_old;
ALTER TABLE trails.edges_new RENAME TO edges;
SELECT pgr_createTopology('trails.edges', 0.0001, 'geom', 'gid');
COMMIT;
EOF
```

## Troubleshooting

### Common Issues

1. **Network Disconnected**
```sql
-- Find disconnected segments
SELECT * FROM pgr_analyzeGraph('trails.edges', 0.0001);

-- Fix by snapping endpoints
UPDATE trails.edges e1
SET geom = ST_Snap(e1.geom, e2.geom, 0.001)
FROM trails.edges e2
WHERE e1.gid != e2.gid
  AND ST_DWithin(e1.geom, e2.geom, 0.001);
```

2. **Routing Fails**
```python
# Increase tolerance for point snapping
result = processing.run("pgRouting:dijkstra", {
    'TOLERANCE': 50,  # meters
    'DIRECTED': False,
    'REVERSE_COST': True
})
```

3. **Memory Issues with Large Networks**
```bash
# Increase PostgreSQL memory
echo "shared_buffers = 2GB" >> /etc/postgresql/14/main/postgresql.conf
echo "work_mem = 256MB" >> /etc/postgresql/14/main/postgresql.conf
sudo systemctl restart postgresql
```

## Integration with Other Tools

### Export to GraphHopper
```bash
# Export QGIS network to OSM format
ogr2ogr -f OSM trails_for_graphhopper.osm \
  "PG:dbname=trail_routing" \
  -sql "SELECT * FROM trails.edges"
```

### Import from BRouter
```python
# Load BRouter RD5 files
brouter_layer = QgsVectorLayer(
    '/path/to/brouter/segments4.rd5',
    'BRouter Network',
    'ogr'
)
```

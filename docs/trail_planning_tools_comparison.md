# Trail Planning Tools: Comprehensive Comparison

## Executive Summary

For snap-to-trail route planning with custom overlays and elevation data, three open-source tools stand out:

1. **GraphHopper** - Best for API-based integration and custom routing
2. **QGIS with plugins** - Best for advanced GIS analysis and flexibility
3. **BRouter** - Best for offline routing with custom profiles

All three support Norwegian Kartverket/Geonorge data and can be extended to other countries.

## Key Requirements Analysis

### Must-Have Features
- ✅ Snap-to-trail routing with custom trail networks
- ✅ Custom elevation data sources (Kartverket 10m DEM)
- ✅ Linux or browser-based access
- ✅ API availability
- ✅ Extensible to other countries/data sources

### Norwegian Data Integration
All recommended tools can integrate:
- **Maps**: Kartverket WMS/WMTS services
- **Trails**: DNT trail data, N50 Kartdata, custom GPX/GeoJSON
- **Elevation**: Kartverket 10m DEM (GeoTIFF format)

## Detailed Tool Comparison

### 1. GraphHopper (⭐ Recommended for API-based solutions)

#### Overview
Open-source routing engine with excellent customization capabilities and production-ready API.

#### Key Strengths
- **Custom Data Import**: Full control over routing network
- **Elevation Integration**: Native support for custom DEM files
- **API-First Design**: RESTful API with comprehensive endpoints
- **Scalability**: Handles large networks efficiently
- **Active Development**: Regular updates and community support

#### Norwegian Data Setup
```bash
# Import Norwegian trails
java -jar graphhopper.jar import \
  --input norwegian_trails.osm.pbf \
  --vehicle-profiles hiking \
  --elevation-provider cgiar \
  --elevation-cache-dir ./elevation/kartverket/

# Configure custom elevation
elevation:
  provider: multi
  base_url: https://hoydedata.no/LaserInnsyn/
  dataaccess: MMAP
```

#### API Capabilities
```json
POST /route
{
  "points": [[10.7522, 59.9139], [10.7389, 59.9275]],
  "profile": "hiking",
  "elevation": true,
  "instructions": true,
  "points_encoded": false,
  "snap_preventions": ["ferry", "highway"]
}
```

#### Deployment Options
- **Self-hosted**: Docker, Linux server, Kubernetes
- **Browser**: Web UI for testing (localhost:8989)
- **Cloud**: Can be deployed on any cloud platform

### 2. QGIS with pgRouting (⭐ Recommended for advanced GIS workflows)

#### Overview
Full GIS platform with routing capabilities through plugins and PostGIS/pgRouting.

#### Key Strengths
- **Complete GIS Suite**: Analysis, visualization, processing
- **Plugin Ecosystem**: Extensive routing and trail planning plugins
- **Data Format Support**: Reads virtually any geo format
- **Python Scripting**: Full automation capabilities
- **Professional Tools**: Advanced network analysis

#### Norwegian Data Integration
```python
# PyQGIS script for Kartverket integration
from qgis.core import QgsRasterLayer, QgsVectorLayer

# Load Kartverket DEM
dem = QgsRasterLayer(
    'https://wms.geonorge.no/skwms1/wms.hoyde-dtm',
    'Kartverket 10m DEM',
    'wms'
)

# Load trail network
trails = QgsVectorLayer(
    'path/to/norwegian_trails.gpkg',
    'Norwegian Trails',
    'ogr'
)

# Configure pgRouting
from processing import run
result = run("pgRouting:dijkstra", {
    'INPUT': trails,
    'START_POINT': start,
    'END_POINT': end,
    'EDGE_TABLE': 'trail_network',
    'COST': 'difficulty_weight'
})
```

#### Plugin Options
- **pgRouting Layer**: Database-based routing
- **QNEAT3**: Network analysis toolkit
- **ORS Tools**: OpenRouteService integration
- **Networks Plugin**: Trail network creation

#### Deployment
- **Desktop**: Native Linux application (QGIS Desktop)
- **Server**: QGIS Server with WMS/WFS capabilities
- **API**: PyQGIS scripts can provide REST endpoints

### 3. BRouter (⭐ Recommended for offline mobile routing)

#### Overview
Lightweight, offline routing engine optimized for outdoor activities.

#### Key Strengths
- **Offline First**: Complete offline operation
- **Custom Profiles**: Highly configurable routing profiles
- **Elevation Aware**: Built-in elevation consideration
- **Low Resource**: Runs on modest hardware
- **Mobile Support**: Android app available

#### Norwegian Data Configuration
```ini
# Custom profile for Norwegian hiking
assign turncost = 20
assign uphillcost = 50
assign downhillcost = 10

assign validForFoot = true

way:
  if trail:class=T1 then 1.0
  else if trail:class=T2 then 1.5
  else if trail:class=T3 then 2.0
  else if trail:class=T4 then 3.0
  else if trail:class=T5 then 5.0
  else 10.0
```

#### Data Processing
```bash
# Convert Kartverket DEM to BRouter format
gdal_translate -of HGT kartverket_10m.tif norway.hgt

# Process trail network
osmconvert norwegian_trails.osm -o=norwegian_trails.o5m
```

#### Deployment Options
- **Standalone Server**: Java application on Linux
- **Web Interface**: http://brouter.de/brouter-web/
- **API**: HTTP API for route calculation

## Feature Comparison Matrix

| Feature | GraphHopper | QGIS/pgRouting | BRouter |
|---------|------------|----------------|---------|
| **Routing Capabilities** |
| Snap-to-trail | ✅ Custom import | ✅ Network topology | ✅ Profile-based |
| Turn restrictions | ✅ Full support | ✅ Via pgRouting | ✅ Configurable |
| Alternative routes | ✅ Built-in | ✅ With plugins | ✅ Limited |
| Route optimization | ✅ Multiple algorithms | ✅ Advanced GIS | ✅ Basic |
| **Elevation** |
| Custom DEM | ✅ Any format | ✅ Native GIS support | ✅ HGT format |
| Kartverket 10m | ✅ Direct import | ✅ WMS or local | ✅ With conversion |
| Profile generation | ✅ API response | ✅ Full analysis | ✅ Built-in |
| 3D visualization | ❌ | ✅ QGIS 3D | ❌ |
| **Data Sources** |
| OSM data | ✅ Native | ✅ Via plugins | ✅ Native |
| Custom trails | ✅ Import any format | ✅ Any GIS format | ✅ OSM format |
| WMS/WMTS | ✅ Via tiles | ✅ Native support | ❌ |
| GPX/KML | ✅ Convert to network | ✅ Direct import | ✅ Convert |
| **Platform Support** |
| Linux desktop | ✅ Java app | ✅ Native app | ✅ Java app |
| Web browser | ✅ Web UI | ✅ QGIS Server | ✅ Web interface |
| API | ✅ RESTful | ✅ PyQGIS/Server | ✅ HTTP |
| Docker | ✅ Official images | ✅ Available | ✅ Community |
| **Extensibility** |
| Custom algorithms | ✅ Java plugins | ✅ Python scripts | ✅ Profiles |
| Plugin system | ✅ Extensions | ✅ Rich ecosystem | ❌ |
| Scripting | ✅ Java/Kotlin | ✅ Python | ❌ |
| Multi-country | ✅ Designed for | ✅ Full GIS | ✅ Profile-based |

## Integration with Norwegian Data Sources

### Kartverket/Geonorge Services

#### Available Data
1. **Elevation**: 10m DEM via WCS or download
2. **Trails**: N50 Kartdata, DNT trails
3. **Base maps**: Topographic via WMS/WMTS
4. **Land cover**: AR5/AR50 for trail surface analysis

#### GraphHopper Integration
```java
// Custom elevation provider for Kartverket
public class KartverketElevationProvider extends TileBasedElevationProvider {
    @Override
    protected String getDownloadURL(int lat, int lon) {
        return String.format(
            "https://hoydedata.no/LaserInnsyn/rest/services/Elevation/ImageServer/exportImage?" +
            "bbox=%d,%d,%d,%d&format=tiff&f=image",
            lon, lat, lon+1, lat+1
        );
    }
}
```

#### QGIS Processing
```python
# Automated trail network creation from Kartverket data
import processing
from qgis.core import QgsProject

# Download and process N50 trail data
processing.run("native:filedownloader", {
    'URL': 'https://nedlasting.geonorge.no/geonorge/Basisdata/N50Kartdata/GML/',
    'OUTPUT': '/tmp/n50_trails.gml'
})

# Convert to routable network
processing.run("native:snapgeometries", {
    'INPUT': '/tmp/n50_trails.gml',
    'REFERENCE_LAYER': '/tmp/n50_trails.gml',
    'TOLERANCE': 10,
    'OUTPUT': 'ogr:dbname=/path/to/trails.gpkg table=trail_network'
})
```

#### BRouter Configuration
```ini
# Norwegian-specific routing rules
assign stick_to_hiking_routes = true
assign prefer_hiking_routes = 5.0

way:
  if norwegian:trail=DNT then 0.8  # Prefer DNT marked trails
  else if surface=gravel then 1.0
  else if surface=ground then 1.2
  else if tracktype=grade1 then 1.0
  else if tracktype=grade2 then 1.1
  else 2.0
```

## Recommended Architecture

### For API-Based Solution (GraphHopper)
```
┌─────────────────┐     ┌──────────────┐     ┌────────────────┐
│   Web Client    │────▶│  REST API    │────▶│  GraphHopper   │
│  (Browser/App)  │     │  (FastAPI)   │     │    Engine      │
└─────────────────┘     └──────────────┘     └────────────────┘
                                │                     │
                                ▼                     ▼
                        ┌──────────────┐     ┌────────────────┐
                        │   PostGIS    │     │ Kartverket DEM │
                        │  Trail Data  │     │   (GeoTIFF)    │
                        └──────────────┘     └────────────────┘
```

### For GIS Analysis (QGIS)
```
┌─────────────────┐     ┌──────────────┐     ┌────────────────┐
│   QGIS Desktop  │────▶│  pgRouting   │────▶│    PostGIS     │
│   or PyQGIS     │     │   Plugin     │     │   Database     │
└─────────────────┘     └──────────────┘     └────────────────┘
                                │
                                ▼
                        ┌──────────────────────────┐
                        │  Kartverket Services    │
                        │  (WMS/WCS/WFS)          │
                        └──────────────────────────┘
```

## Implementation Recommendations

### Phase 1: Proof of Concept
1. **GraphHopper Setup**
   - Import sample Norwegian trail data
   - Configure Kartverket DEM
   - Test snap-to-trail routing
   - Verify elevation profiles

### Phase 2: Data Pipeline
1. **Automated Data Import**
   - Schedule Kartverket data updates
   - Process DNT trail updates
   - Merge community GPS tracks
   - Validate network connectivity

### Phase 3: Production Deployment
1. **API Development**
   - RESTful endpoints for routing
   - Elevation profile service
   - Trail difficulty calculation
   - Multi-modal routing (hiking + ferry)

### Phase 4: International Extension
1. **Multi-Country Support**
   - Abstract data source interface
   - Country-specific routing profiles
   - Internationalization
   - Cross-border routing

## Cost Analysis

| Solution | License | Infrastructure | Development | Maintenance |
|----------|---------|---------------|-------------|-------------|
| GraphHopper | Apache 2.0 (Free) | VPS/Cloud ($20-100/mo) | Medium | Low |
| QGIS/pgRouting | GPL (Free) | VPS + PostGIS ($30-150/mo) | High | Medium |
| BRouter | MIT (Free) | Minimal ($10-50/mo) | Low | Low |

## Conclusion

For snap-to-trail route planning with Norwegian data and international extensibility:

1. **Choose GraphHopper if**:
   - API is primary interface
   - Need production scalability
   - Want fastest implementation

2. **Choose QGIS/pgRouting if**:
   - Need advanced GIS analysis
   - Have complex data workflows
   - Want maximum flexibility

3. **Choose BRouter if**:
   - Offline operation is critical
   - Resource constraints exist
   - Simplicity is valued

All three solutions support the core requirements and can work with Kartverket/Geonorge data effectively.

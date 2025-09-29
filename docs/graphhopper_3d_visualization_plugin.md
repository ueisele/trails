# GraphHopper 3D Visualization Plugin

## Overview

While GraphHopper's core doesn't include 3D visualization, you can create a plugin that adds 3D capabilities to the web interface or API responses. This involves modifying the web bundle and creating custom endpoints.

## Architecture Options

### Option 1: Web Bundle Extension Plugin

```java
package com.yourcompany.graphhopper.plugins;

import com.graphhopper.http.GraphHopperBundle;
import com.graphhopper.http.GraphHopperServerConfiguration;
import io.dropwizard.setup.Environment;

public class Visualization3DPlugin implements GraphHopperPlugin {

    @Override
    public void init(GraphHopperConfig config) {
        // Initialize 3D visualization configuration
        this.terrainExaggeration = config.getDouble("3d.terrain_exaggeration", 1.5);
        this.demProvider = config.getString("3d.dem_provider", "kartverket");
    }

    @Override
    public void registerResources(Environment environment) {
        // Register 3D visualization endpoints
        environment.jersey().register(new Terrain3DResource());
        environment.jersey().register(new Route3DResource());

        // Serve custom 3D web interface
        environment.jersey().register(new Static3DAssetsResource());
    }

    @Override
    public void modifyWebBundle(GraphHopperBundle bundle) {
        // Replace default map with 3D-capable version
        bundle.setMapProvider(new MapboxGL3DProvider());

        // Add 3D controls to UI
        bundle.addUIComponent(new Elevation3DControl());
        bundle.addUIComponent(new TerrainControl());
    }
}
```

### Option 2: Custom 3D API Endpoints

```java
@Path("/3d")
@Produces(MediaType.APPLICATION_JSON)
public class Route3DResource {
    private final GraphHopper graphHopper;
    private final Terrain3DService terrainService;

    @POST
    @Path("/route")
    public Response calculate3DRoute(Route3DRequest request) {
        // Calculate standard route
        GHResponse ghResponse = graphHopper.route(request.toGHRequest());

        // Enhance with 3D data
        Route3DResponse response = new Route3DResponse();
        response.setPath(ghResponse.getBest());

        // Add terrain mesh along route
        TerrainMesh mesh = terrainService.generateTerrainMesh(
            ghResponse.getBest().getPoints(),
            request.getTerrainResolution()
        );
        response.setTerrainMesh(mesh);

        // Add 3D visualization hints
        response.setVisualizationHints(create3DHints(ghResponse));

        return Response.ok(response).build();
    }

    @GET
    @Path("/terrain/{z}/{x}/{y}.terrain")
    @Produces("application/vnd.quantized-mesh")
    public Response getTerrainTile(@PathParam("z") int z,
                                  @PathParam("x") int x,
                                  @PathParam("y") int y) {
        // Serve quantized mesh terrain tiles for Cesium
        byte[] terrainData = terrainService.getQuantizedMeshTile(z, x, y);
        return Response.ok(terrainData)
            .header("Content-Encoding", "gzip")
            .build();
    }

    @GET
    @Path("/elevation/curtain")
    public Response getElevationCurtain(@QueryParam("path") String encodedPath) {
        // Generate elevation curtain (vertical profile wall)
        PointList points = WebHelper.decodePolyline(encodedPath);

        ElevationCurtain curtain = new ElevationCurtain();
        for (int i = 0; i < points.size(); i++) {
            double elevation = elevationProvider.getEle(points.getLat(i), points.getLon(i));
            curtain.addPoint(points.getLon(i), points.getLat(i), elevation);
        }

        return Response.ok(curtain.toGeoJSON()).build();
    }
}
```

## Enhanced Web Interface with 3D

### Custom Map Component

```java
public class MapboxGL3DProvider implements MapProvider {

    @Override
    public String getMapHTML() {
        return """
            <div id="map-3d"></div>
            <div id="elevation-profile-3d"></div>
            <script src="/js/mapbox-gl.js"></script>
            <script src="/js/mapbox-gl-terrain.js"></script>
            <script src="/js/graphhopper-3d.js"></script>
        """;
    }

    @Override
    public String getMapInitScript() {
        return """
            // Initialize 3D map
            const map = new mapboxgl.Map({
                container: 'map-3d',
                style: 'mapbox://styles/mapbox/satellite-v9',
                center: [10.7522, 59.9139],
                zoom: 12,
                pitch: 60,
                bearing: -17.6,
                antialias: true
            });

            // Add Norwegian terrain
            map.on('load', () => {
                map.addSource('norway-dem', {
                    type: 'raster-dem',
                    url: '/3d/terrain/tiles.json',
                    tileSize: 256,
                    maxzoom: 14
                });

                map.setTerrain({
                    source: 'norway-dem',
                    exaggeration: %f
                });

                // Add sky for better 3D effect
                map.addLayer({
                    'id': 'sky',
                    'type': 'sky',
                    'paint': {
                        'sky-type': 'atmosphere',
                        'sky-atmosphere-sun': [0.0, 90.0],
                        'sky-atmosphere-sun-intensity': 15
                    }
                });
            });

            // Hook into GraphHopper routing
            GraphHopper3D.initialize(map);
        """.formatted(terrainExaggeration);
    }
}
```

### JavaScript 3D Enhancement

```javascript
// graphhopper-3d.js - Client-side 3D enhancement
class GraphHopper3D {
    static initialize(map) {
        this.map = map;
        this.originalRoute = GH.route;

        // Override default routing to add 3D
        GH.route = async (request) => {
            // Call original routing
            const response = await this.originalRoute.call(GH, request);

            // Enhance with 3D visualization
            if (response.paths && response.paths.length > 0) {
                await this.visualize3D(response.paths[0]);
            }

            return response;
        };
    }

    static async visualize3D(path) {
        // Add route with elevation coloring
        this.map.addSource('route-3d', {
            type: 'geojson',
            lineMetrics: true,
            data: {
                type: 'Feature',
                geometry: path.points,
                properties: {
                    elevation: path.ascend,
                    difficulty: path.details.sac_scale
                }
            }
        });

        // Color by elevation
        this.map.addLayer({
            id: 'route-3d-line',
            type: 'line',
            source: 'route-3d',
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': [
                    'interpolate',
                    ['linear'],
                    ['line-progress'],
                    0, this.getElevationColor(path.points.coordinates[0][2]),
                    1, this.getElevationColor(path.points.coordinates.slice(-1)[0][2])
                ],
                'line-width': 5,
                'line-opacity': 0.8
            }
        });

        // Add 3D waypoint markers
        this.add3DMarkers(path.snapped_waypoints);

        // Create elevation curtain
        await this.createElevationCurtain(path);

        // Fly to route in 3D
        this.flyToRoute3D(path.bbox);
    }

    static async createElevationCurtain(path) {
        // Fetch elevation curtain from server
        const response = await fetch(`/3d/elevation/curtain?path=${path.points_encoded}`);
        const curtainData = await response.json();

        // Add as 3D extrusion
        this.map.addLayer({
            id: 'elevation-curtain',
            type: 'fill-extrusion',
            source: {
                type: 'geojson',
                data: curtainData
            },
            paint: {
                'fill-extrusion-color': [
                    'interpolate',
                    ['linear'],
                    ['get', 'elevation'],
                    0, '#00ff00',
                    1000, '#ffff00',
                    2000, '#ff0000'
                ],
                'fill-extrusion-height': ['get', 'elevation'],
                'fill-extrusion-base': 0,
                'fill-extrusion-opacity': 0.6
            }
        });
    }

    static flyToRoute3D(bbox) {
        this.map.fitBounds(bbox, {
            padding: 50,
            pitch: 60,
            bearing: this.calculateOptimalBearing(bbox),
            duration: 2000
        });
    }
}
```

## Terrain Service Implementation

```java
@Component
public class Terrain3DService {
    private final ElevationProvider elevationProvider;
    private final Cache<TileKey, byte[]> tileCache;

    public byte[] getQuantizedMeshTile(int z, int x, int y) {
        TileKey key = new TileKey(z, x, y);

        return tileCache.get(key, k -> {
            // Generate quantized mesh from DEM
            BoundingBox bbox = tileToBounds(z, x, y);

            // Sample elevation grid
            int resolution = getResolutionForZoom(z);
            float[][] elevations = sampleElevations(bbox, resolution);

            // Create quantized mesh (Cesium format)
            QuantizedMeshBuilder builder = new QuantizedMeshBuilder();
            builder.setElevations(elevations);
            builder.computeNormals();
            builder.computeEdgeIndices();

            // Compress
            return gzip(builder.build());
        });
    }

    public TerrainMesh generateTerrainMesh(PointList route, int resolution) {
        // Create terrain mesh along route corridor
        TerrainMesh mesh = new TerrainMesh();

        // Buffer route by 500m each side
        Geometry buffer = createBuffer(route, 500);

        // Sample elevation grid
        for (int i = 0; i < resolution; i++) {
            for (int j = 0; j < resolution; j++) {
                Point p = getGridPoint(buffer, i, j, resolution);
                double elevation = elevationProvider.getEle(p.lat, p.lon);

                mesh.addVertex(p.lon, p.lat, elevation);
            }
        }

        // Generate triangles
        mesh.triangulate();

        // Add texture coordinates
        mesh.generateTextureCoords();

        return mesh;
    }
}
```

## Custom 3D Response Format

```java
public class Route3DResponse extends RouteResponse {
    private TerrainMesh terrainMesh;
    private List<Viewpoint3D> viewpoints;
    private AnimationPath flythroughPath;
    private ElevationCurtain elevationCurtain;

    // Enhanced response with 3D data
    public static class TerrainMesh {
        private float[] vertices;      // [x,y,z,x,y,z,...]
        private int[] triangles;        // Triangle indices
        private float[] normals;        // Vertex normals
        private float[] textureCoords;  // UV coordinates
        private String textureUrl;      // Satellite imagery URL
    }

    public static class Viewpoint3D {
        private double lon, lat, elevation;
        private double heading, tilt, range;
        private String name;
        private String description;
    }

    public static class AnimationPath {
        private List<Keyframe> keyframes;
        private double duration;

        public static class Keyframe {
            private double time;
            private double lon, lat, elevation;
            private double heading, tilt;
        }
    }
}
```

## Configuration

```yaml
# config.yml with 3D plugin
graphhopper:
  plugins:
    - com.yourcompany.graphhopper.plugins.Visualization3DPlugin

  # 3D visualization settings
  3d:
    enabled: true
    terrain_exaggeration: 1.5
    dem_provider: kartverket
    dem_cache_size: 1000

    # Terrain tile generation
    terrain_tiles:
      min_zoom: 8
      max_zoom: 15
      tile_size: 256

    # 3D route options
    route:
      corridor_width: 1000  # meters
      mesh_resolution: 100   # vertices
      include_viewpoints: true
      generate_flythrough: true

    # Client options
    client:
      default_pitch: 60
      default_bearing: -17.6
      animation_duration: 10000
```

## Building and Deploying

```xml
<!-- pom.xml additions -->
<dependencies>
    <!-- 3D geometry -->
    <dependency>
        <groupId>org.locationtech.jts</groupId>
        <artifactId>jts-core</artifactId>
        <version>1.19.0</version>
    </dependency>

    <!-- Terrain mesh generation -->
    <dependency>
        <groupId>org.geotools</groupId>
        <artifactId>gt-coverage</artifactId>
        <version>29.2</version>
    </dependency>
</dependencies>
```

```bash
# Build with 3D plugin
mvn clean package -P3d-plugin

# Run with 3D enabled
java -jar graphhopper-3d.jar server config-3d.yml
```

## API Usage

```javascript
// Client requesting 3D route
const response = await fetch('http://localhost:8989/3d/route', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        points: [[10.7522, 59.9139], [10.7389, 59.9275]],
        profile: 'hiking',
        elevation: true,
        // 3D specific options
        terrain_mesh: true,
        mesh_resolution: 100,
        include_viewpoints: true,
        generate_flythrough: true,
        terrain_corridor_width: 500
    })
});

const route3d = await response.json();

// Use in Cesium
viewer.scene.primitives.add(new Cesium.Primitive({
    geometryInstances: new Cesium.GeometryInstance({
        geometry: new Cesium.Geometry({
            attributes: {
                position: new Cesium.VertexArray({
                    values: route3d.terrainMesh.vertices
                })
            },
            indices: route3d.terrainMesh.triangles
        })
    })
}));
```

## Limitations and Considerations

### What's Possible ✅
- Serve terrain tiles alongside routing
- Generate 3D mesh corridors along routes
- Provide elevation curtains
- Enhanced API responses with 3D data
- Custom web interface with 3D map
- Integration with Cesium/Mapbox GL

### What's Challenging ⚠️
- Real-time 3D rendering (client-side responsibility)
- Large terrain datasets (needs caching)
- Performance impact on routing
- Mobile 3D support varies

### What's Not Possible ❌
- Native 3D rendering in GraphHopper core
- Modifying core routing for 3D paths
- Direct WebGL rendering server-side

## Conclusion

While GraphHopper doesn't natively support 3D visualization, you can create a comprehensive plugin that:
1. Serves terrain data alongside routes
2. Generates 3D mesh corridors
3. Provides enhanced API responses
4. Replaces the web interface with 3D-capable maps
5. Integrates with modern 3D mapping libraries

This gives you a complete 3D trail planning system while maintaining GraphHopper's routing capabilities!

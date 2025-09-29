# GraphHopper Customization Guide

## Overview

GraphHopper is highly customizable through multiple mechanisms: custom profiles, plugins, extensions, and direct code modifications. It's designed as a modular system where almost every component can be replaced or extended.

## Customization Levels

### 1. Configuration Level (No Code)

#### Custom Profiles (YAML/JSON)
```yaml
# config.yml - Custom hiking profile for Norwegian trails
profiles:
  - name: norwegian_hiking
    vehicle: foot
    weighting: custom
    custom_model:
      distance_influence: 30
      speed:
        - if: trail_class == T1
          limit_to: 5
        - else_if: trail_class == T2
          limit_to: 4
        - else_if: trail_class == T3
          limit_to: 3
        - else_if: trail_class == T4
          limit_to: 2
        - else:
          limit_to: 1
      priority:
        - if: operator == DNT
          multiply_by: 1.5
        - if: marked_trail == yes
          multiply_by: 1.3
        - if: surface == rock
          multiply_by: 0.5
        - if: ford == yes
          multiply_by: 0.1
```

#### Elevation Influence
```yaml
# Elevation-aware routing
profiles:
  - name: alpine_hiking
    vehicle: foot
    weighting: custom
    custom_model:
      distance_influence: 20
      elevation_influence: 70  # Heavy elevation penalty
      # Custom elevation costs
      uphill_cost: 80
      downhill_cost: 40
      max_slope: 35  # Avoid slopes > 35%
```

### 2. Plugin System (Java Extensions)

GraphHopper supports plugins through its modular architecture:

#### Creating a Custom Plugin
```java
// MyCustomPlugin.java
package com.yourcompany.graphhopper.plugins;

import com.graphhopper.GraphHopperConfig;
import com.graphhopper.routing.util.FlagEncoder;
import com.graphhopper.storage.GraphHopperStorage;
import com.graphhopper.util.PMap;

public class NorwegianTrailPlugin implements GraphHopperPlugin {

    @Override
    public void init(GraphHopperConfig config) {
        // Initialize plugin with config
    }

    @Override
    public void createPreProcessingHandlers(GraphHopperStorage graph) {
        // Add preprocessing steps
        graph.addPreprocessingHandler(new TrailDifficultyAnalyzer());
        graph.addPreprocessingHandler(new ElevationProfileEnhancer());
    }

    @Override
    public List<FlagEncoder> createFlagEncoders(PMap properties) {
        // Create custom encoders for trail attributes
        return Arrays.asList(
            new TrailDifficultyEncoder(),
            new SurfaceQualityEncoder(),
            new SeasonalAccessEncoder()
        );
    }
}
```

#### Registering Plugins
```java
// In your main GraphHopper setup
GraphHopper hopper = new GraphHopper()
    .registerPlugin(new NorwegianTrailPlugin())
    .registerPlugin(new WeatherAwareRoutingPlugin())
    .registerPlugin(new AvoidAvalancheZonesPlugin());
```

### 3. Core Customizations (Java Development)

#### Custom Weighting Implementation
```java
package com.yourcompany.routing;

import com.graphhopper.routing.weighting.Weighting;
import com.graphhopper.util.EdgeIteratorState;
import com.graphhopper.util.FetchMode;

public class TrailDifficultyWeighting implements Weighting {
    private final Weighting baseWeighting;
    private final Map<String, Double> difficultyMultipliers;

    public TrailDifficultyWeighting(Weighting baseWeighting) {
        this.baseWeighting = baseWeighting;
        this.difficultyMultipliers = Map.of(
            "T1", 1.0,
            "T2", 1.3,
            "T3", 1.8,
            "T4", 2.5,
            "T5", 4.0,
            "T6", 8.0
        );
    }

    @Override
    public double calcEdgeWeight(EdgeIteratorState edge, boolean reverse) {
        double baseWeight = baseWeighting.calcEdgeWeight(edge, reverse);

        // Get trail difficulty from edge properties
        String difficulty = edge.get(trailDifficultyEnc);
        double multiplier = difficultyMultipliers.getOrDefault(difficulty, 1.5);

        // Consider elevation
        double elevationGain = getElevationGain(edge);
        double elevationPenalty = 1.0 + (elevationGain / 100.0) * 0.3;

        // Consider surface
        String surface = edge.get(surfaceEnc);
        double surfacePenalty = getSurfacePenalty(surface);

        return baseWeight * multiplier * elevationPenalty * surfacePenalty;
    }

    @Override
    public double getMinWeight(double distance) {
        return baseWeighting.getMinWeight(distance);
    }

    @Override
    public String getName() {
        return "trail_difficulty";
    }
}
```

#### Custom Routing Algorithm
```java
public class ScenicRouteAlgorithm extends AbstractRoutingAlgorithm {
    private final ScenicScoreCalculator scenicCalculator;

    @Override
    public Path calcPath(int from, int to) {
        // Custom A* implementation that considers scenic value
        PriorityQueue<AStarEntry> openSet = new PriorityQueue<>();
        Map<Integer, Double> gScore = new HashMap<>();

        gScore.put(from, 0.0);
        openSet.add(new AStarEntry(from, 0, heuristic(from, to)));

        while (!openSet.isEmpty()) {
            AStarEntry current = openSet.poll();

            if (current.node == to) {
                return reconstructPath(current);
            }

            EdgeIterator iter = graph.createEdgeExplorer().setBaseNode(current.node);
            while (iter.next()) {
                double edgeCost = calculateCost(iter);
                double scenicBonus = scenicCalculator.getBonus(iter);
                double tentativeScore = gScore.get(current.node) + edgeCost - scenicBonus;

                if (tentativeScore < gScore.getOrDefault(iter.getAdjNode(), Double.MAX_VALUE)) {
                    gScore.put(iter.getAdjNode(), tentativeScore);
                    openSet.add(new AStarEntry(
                        iter.getAdjNode(),
                        tentativeScore,
                        tentativeScore + heuristic(iter.getAdjNode(), to)
                    ));
                }
            }
        }

        return createEmptyPath();
    }
}
```

#### Custom Data Import
```java
public class NorwegianTrailImporter extends DataReader {

    @Override
    public void readGraph() {
        // Read custom data sources
        GeoJsonReader reader = new GeoJsonReader();
        FeatureCollection trails = reader.read("norwegian_trails.geojson");

        for (Feature trail : trails) {
            LineString geometry = (LineString) trail.getGeometry();
            Map<String, Object> props = trail.getProperties();

            // Create GraphHopper edges
            for (int i = 0; i < geometry.getNumPoints() - 1; i++) {
                Coordinate start = geometry.getCoordinateN(i);
                Coordinate end = geometry.getCoordinateN(i + 1);

                int fromNode = getOrCreateNode(start.y, start.x);
                int toNode = getOrCreateNode(end.y, end.x);

                EdgeIteratorState edge = graph.edge(fromNode, toNode);

                // Set custom properties
                edge.set(trailClassEnc, props.get("difficulty"));
                edge.set(surfaceEnc, props.get("surface"));
                edge.set(operatorEnc, props.get("operator"));
                edge.set(seasonalEnc, props.get("seasonal"));
                edge.setDistance(calculateDistance(start, end));

                // Add elevation data
                double[] elevations = getElevations(start, end);
                edge.set(elevationEnc, elevations);
            }
        }
    }
}
```

### 4. Storage Customization

#### Custom Edge Properties
```java
public class TrailEncodingManager extends EncodingManager {

    @Override
    public void createEncodedValues() {
        super.createEncodedValues();

        // Add custom encoded values for trail properties
        registerEncodedValue(new StringEncodedValue("trail_class", 3));
        registerEncodedValue(new StringEncodedValue("operator", 20));
        registerEncodedValue(new DecimalEncodedValue("scenic_score", 5, 0.1, false));
        registerEncodedValue(new BooleanEncodedValue("winter_accessible"));
        registerEncodedValue(new IntEncodedValue("avalanche_risk", 3));
        registerEncodedValue(new StringEncodedValue("maintenance_status", 10));
    }
}
```

#### Custom Graph Storage
```java
public class TrailGraphStorage extends GraphHopperStorage {
    private final DataAccess trailMetadata;

    public TrailGraphStorage(Directory dir, EncodingManager encodingManager) {
        super(dir, encodingManager);
        this.trailMetadata = dir.create("trail_metadata");
    }

    public void setTrailInfo(int edgeId, TrailInfo info) {
        int pointer = edgeId * TRAIL_INFO_BYTES;
        trailMetadata.ensureCapacity(pointer + TRAIL_INFO_BYTES);

        trailMetadata.setBytes(pointer, info.serialize());
    }

    public TrailInfo getTrailInfo(int edgeId) {
        int pointer = edgeId * TRAIL_INFO_BYTES;
        byte[] data = new byte[TRAIL_INFO_BYTES];
        trailMetadata.getBytes(pointer, data);
        return TrailInfo.deserialize(data);
    }
}
```

### 5. Extension Points

#### Custom Request Parameters
```java
@Path("/route")
public class CustomRouteResource extends RouteResource {

    @POST
    @Override
    public Response doPost(RouteRequest request) {
        // Add custom parameters
        String avoidDifficulties = request.getHints().getString("avoid_difficulties", "");
        boolean preferScenic = request.getHints().getBool("prefer_scenic", false);
        boolean winterOnly = request.getHints().getBool("winter_accessible", false);

        // Modify routing based on custom parameters
        if (!avoidDifficulties.isEmpty()) {
            request.getHints().putObject(
                "custom_model.priority",
                createDifficultyAvoidance(avoidDifficulties)
            );
        }

        if (preferScenic) {
            request.setWeighting("scenic_route");
        }

        return super.doPost(request);
    }
}
```

#### Custom Response Format
```java
public class TrailResponseBuilder extends ResponsePathBuilder {

    @Override
    public Map<String, Object> build(ResponsePath path) {
        Map<String, Object> response = super.build(path);

        // Add custom trail information
        List<TrailSegment> segments = new ArrayList<>();
        for (PathDetail detail : path.getPathDetails().get("trail_info")) {
            TrailSegment segment = new TrailSegment();
            segment.setTrailName(detail.getValue().get("name"));
            segment.setDifficulty(detail.getValue().get("difficulty"));
            segment.setOperator(detail.getValue().get("operator"));
            segment.setScenicScore(detail.getValue().get("scenic_score"));
            segment.setWarnings(getWarnings(detail));
            segments.add(segment);
        }

        response.put("trail_segments", segments);
        response.put("total_scenic_score", calculateTotalScenicScore(segments));
        response.put("difficulty_summary", createDifficultySummary(segments));

        return response;
    }
}
```

### 6. Elevation Provider Customization

#### Custom DEM Provider for Kartverket
```java
public class KartverketElevationProvider extends TileBasedElevationProvider {
    private static final String BASE_URL = "https://hoydedata.no/LaserInnsyn/";

    @Override
    public double getEle(double lat, double lon) {
        // Custom implementation for Norwegian elevation data
        Tile tile = getTile(lat, lon);

        if (!tile.isLoaded()) {
            downloadTile(tile);
        }

        return tile.getElevation(lat, lon);
    }

    private void downloadTile(Tile tile) {
        String url = String.format(
            "%s/rest/services/Elevation/ImageServer/exportImage?" +
            "bbox=%f,%f,%f,%f&format=tiff&pixelType=F32",
            BASE_URL,
            tile.getMinLon(), tile.getMinLat(),
            tile.getMaxLon(), tile.getMaxLat()
        );

        // Download and cache the elevation tile
        byte[] data = httpClient.get(url);
        tile.loadFromGeoTiff(data);
        cache.put(tile.getId(), tile);
    }
}
```

### 7. Machine Learning Integration

#### Trail Difficulty Prediction
```java
public class MLDifficultyPredictor implements EdgePreprocessor {
    private final ONNXModel model;

    public MLDifficultyPredictor(String modelPath) {
        this.model = new ONNXModel(modelPath);
    }

    @Override
    public void processEdge(EdgeIteratorState edge) {
        // Extract features
        float[] features = new float[]{
            edge.getDistance(),
            getElevationGain(edge),
            getElevationLoss(edge),
            getSurfaceRoughness(edge),
            getAverageSlope(edge),
            getMaxSlope(edge),
            getPathWidth(edge)
        };

        // Predict difficulty
        float[] prediction = model.predict(features);
        String difficulty = mapPredictionToDifficulty(prediction);

        // Store prediction
        edge.set(predictedDifficultyEnc, difficulty);
    }
}
```

### 8. Real-time Data Integration

#### Weather-Aware Routing
```java
public class WeatherAwareWeighting extends AbstractWeighting {
    private final WeatherService weatherService;

    @Override
    public double calcEdgeWeight(EdgeIteratorState edge, boolean reverse) {
        double baseWeight = super.calcEdgeWeight(edge, reverse);

        // Get current weather conditions
        WeatherConditions weather = weatherService.getConditions(
            edge.fetchWayGeometry(FetchMode.ALL)
        );

        // Apply weather penalties
        if (weather.getPrecipitation() > 10) {
            baseWeight *= 1.5; // Heavy rain penalty
        }

        if (weather.getWindSpeed() > 50) {
            if (isExposed(edge)) {
                baseWeight *= 2.0; // High wind on exposed trails
            }
        }

        if (weather.getTemperature() < -10) {
            baseWeight *= 1.8; // Extreme cold penalty
        }

        return baseWeight;
    }
}
```

## Plugin Architecture

### Plugin Lifecycle

```java
public interface GraphHopperPlugin {
    // Called during initialization
    void init(GraphHopperConfig config);

    // Called before graph import
    void beforeImport();

    // Called after graph import
    void afterImport(GraphHopperStorage storage);

    // Register custom components
    void registerComponents(ComponentRegistry registry);

    // Create custom request handlers
    List<RequestHandler> createRequestHandlers();

    // Cleanup on shutdown
    void close();
}
```

### Example: Complete Trail Analysis Plugin

```java
public class TrailAnalysisPlugin implements GraphHopperPlugin {
    private TrailDifficultyAnalyzer difficultyAnalyzer;
    private ScenicScoreCalculator scenicCalculator;
    private SeasonalAccessChecker seasonalChecker;

    @Override
    public void init(GraphHopperConfig config) {
        this.difficultyAnalyzer = new TrailDifficultyAnalyzer(
            config.getString("trail.difficulty.model", "default")
        );
        this.scenicCalculator = new ScenicScoreCalculator(
            config.getDouble("scenic.weight", 0.3)
        );
        this.seasonalChecker = new SeasonalAccessChecker();
    }

    @Override
    public void afterImport(GraphHopperStorage storage) {
        // Analyze all edges after import
        AllEdgesIterator iter = storage.getAllEdges();
        while (iter.next()) {
            // Calculate and store difficulty
            String difficulty = difficultyAnalyzer.analyze(iter);
            iter.set(difficultyEnc, difficulty);

            // Calculate scenic score
            double score = scenicCalculator.calculate(iter);
            iter.set(scenicEnc, score);

            // Check seasonal access
            boolean winterAccess = seasonalChecker.isWinterAccessible(iter);
            iter.set(winterAccessEnc, winterAccess);
        }
    }

    @Override
    public List<RequestHandler> createRequestHandlers() {
        return Arrays.asList(
            new TrailAnalysisHandler(),
            new ScenicRouteHandler(),
            new SeasonalRouteHandler()
        );
    }
}
```

## Building and Deployment

### Maven Configuration for Plugins
```xml
<!-- pom.xml -->
<project>
    <groupId>com.yourcompany</groupId>
    <artifactId>graphhopper-norwegian-trails</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <dependency>
            <groupId>com.graphhopper</groupId>
            <artifactId>graphhopper-core</artifactId>
            <version>8.0</version>
        </dependency>
        <dependency>
            <groupId>com.graphhopper</groupId>
            <artifactId>graphhopper-web-bundle</artifactId>
            <version>8.0</version>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-shade-plugin</artifactId>
                <version>3.2.4</version>
                <configuration>
                    <transformers>
                        <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                            <mainClass>com.yourcompany.CustomGraphHopperServer</mainClass>
                        </transformer>
                    </transformers>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

### Running with Custom Plugins
```bash
# Build your custom GraphHopper
mvn clean package

# Run with plugins
java -Xmx4g -jar target/graphhopper-norwegian-trails.jar \
  --config config.yml \
  --graph-location ./graph-cache \
  --profiles norwegian_hiking,scenic_route
```

## Limitations and Considerations

### What Can Be Customized
✅ Routing algorithms
✅ Edge weights and costs
✅ Import process
✅ Storage format
✅ API endpoints
✅ Response format
✅ Elevation handling
✅ Preprocessing steps
✅ Caching strategies

### What Cannot Be Easily Customized
❌ Core graph structure (without forking)
❌ Coordinate system (WGS84 is hardcoded in places)
❌ Some internal optimizations
❌ License restrictions on commercial use

### Performance Impact of Customizations
- Custom weightings: 10-30% overhead
- Additional edge properties: Increases storage by ~4 bytes per property
- ML integration: 50-200% overhead depending on model
- Real-time data: Network latency dependent

## Comparison with Other Tools

| Feature | GraphHopper | OSRM | Valhalla | pgRouting |
|---------|------------|------|----------|-----------|
| Custom Profiles | ✅ Excellent | ⚠️ Limited | ✅ Good | ✅ SQL-based |
| Plugin System | ✅ Java plugins | ❌ | ⚠️ Limited | ✅ PostgreSQL |
| Algorithm Customization | ✅ Full control | ❌ | ⚠️ Some | ✅ Full control |
| Storage Customization | ✅ Extensible | ❌ | ⚠️ Limited | ✅ Full control |
| Real-time Integration | ✅ Possible | ❌ | ⚠️ Basic | ✅ Via triggers |
| ML Integration | ✅ Possible | ❌ | ❌ | ✅ Via Python |

## Conclusion

GraphHopper offers extensive customization capabilities through:
1. **Configuration files** for non-developers
2. **Plugin system** for modular extensions
3. **Core customization** for complete control
4. **Storage extension** for custom data
5. **Algorithm replacement** for specialized routing

For Norwegian trail routing, you can customize:
- Trail difficulty assessment
- Seasonal accessibility
- Scenic route preferences
- Weather-aware routing
- Custom elevation handling
- DNT trail prioritization

The main limitation is that deep customizations require Java development skills, but the plugin architecture makes it possible to extend GraphHopper significantly without forking the entire project.

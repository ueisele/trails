# GraphHopper Custom Snapping Plugin Guide

## Overview

GraphHopper allows custom snapping logic through its plugin system and custom LocationIndex implementations. You can prefer specific trail types, apply seasonal rules, or implement complex snapping strategies.

## Implementation Approaches

### Approach 1: Custom EdgeFilter (Simplest)

```java
package com.yourcompany.graphhopper.snapping;

import com.graphhopper.routing.util.EdgeFilter;
import com.graphhopper.storage.Graph;
import com.graphhopper.util.EdgeIteratorState;

/**
 * Prefer DNT trails, fallback to other trails if none found
 */
public class PreferredTrailEdgeFilter implements EdgeFilter {
    private final Graph graph;
    private final String preferredOperator;
    private final double maxDistance;
    private final EdgeFilter fallbackFilter;

    public PreferredTrailEdgeFilter(Graph graph, String operator, double maxDistance) {
        this.graph = graph;
        this.preferredOperator = operator;
        this.maxDistance = maxDistance;
        this.fallbackFilter = EdgeFilter.ALL_EDGES;
    }

    @Override
    public boolean accept(EdgeIteratorState edge) {
        // First pass: Only accept preferred trails
        String operator = edge.get(operatorEnc);
        if (preferredOperator.equals(operator)) {
            return true;
        }

        // For second pass (handled by custom location index)
        return false;
    }
}
```

### Approach 2: Custom LocationIndex with Multi-Tier Snapping

```java
package com.yourcompany.graphhopper.snapping;

import com.graphhopper.storage.index.LocationIndex;
import com.graphhopper.storage.index.Snap;
import com.graphhopper.util.EdgeFilter;
import com.graphhopper.util.shapes.GHPoint;

/**
 * Multi-tier snapping: Try preferred trails first, then fallback
 */
public class TieredTrailLocationIndex implements LocationIndex {
    private final LocationIndex delegate;
    private final Graph graph;

    // Snapping tiers in order of preference
    private final List<SnapTier> snapTiers = Arrays.asList(
        new SnapTier("DNT trails", 100, edge -> "DNT".equals(edge.get(operatorEnc))),
        new SnapTier("Marked trails", 200, edge -> edge.get(markedEnc)),
        new SnapTier("Any trail", 500, edge -> isTrail(edge)),
        new SnapTier("Any path", 1000, EdgeFilter.ALL_EDGES)
    );

    @Override
    public Snap findClosest(double lat, double lon, EdgeFilter filter) {
        GHPoint point = new GHPoint(lat, lon);

        // Try each tier in order
        for (SnapTier tier : snapTiers) {
            // Combine tier filter with request filter
            EdgeFilter combinedFilter = edge ->
                tier.filter.accept(edge) && filter.accept(edge);

            Snap snap = delegate.findClosest(lat, lon, combinedFilter);

            // Check if we found a valid snap within tier distance
            if (snap.isValid() && snap.getDistance() <= tier.maxDistance) {
                // Add metadata about which tier was used
                snap.setMetadata("snap_tier", tier.name);
                snap.setMetadata("snap_distance", snap.getDistance());
                return snap;
            }
        }

        // No valid snap found
        return Snap.INVALID;
    }

    private static class SnapTier {
        final String name;
        final double maxDistance;
        final EdgeFilter filter;

        SnapTier(String name, double maxDistance, EdgeFilter filter) {
            this.name = name;
            this.maxDistance = maxDistance;
            this.filter = filter;
        }
    }
}
```

### Approach 3: Complete Snapping Plugin

```java
package com.yourcompany.graphhopper.plugins;

import com.graphhopper.GraphHopper;
import com.graphhopper.GraphHopperConfig;
import com.graphhopper.routing.util.EncodingManager;
import com.graphhopper.storage.GraphHopperStorage;
import com.graphhopper.storage.index.LocationIndex;
import com.graphhopper.util.Parameters;

/**
 * Plugin for Norwegian trail-specific snapping preferences
 */
public class NorwegianTrailSnappingPlugin implements GraphHopperPlugin {

    private SnapConfig snapConfig;

    @Override
    public void init(GraphHopperConfig config) {
        // Load configuration
        this.snapConfig = new SnapConfig();
        snapConfig.preferredOperators = config.getStringList(
            "snapping.preferred_operators",
            Arrays.asList("DNT", "Den Norske Turistforening")
        );
        snapConfig.seasonalMode = config.getBool("snapping.seasonal", false);
        snapConfig.difficultyLimit = config.getString("snapping.max_difficulty", "T4");
        snapConfig.avoidUnmarked = config.getBool("snapping.avoid_unmarked", false);
    }

    @Override
    public void afterGraphBuild(GraphHopperStorage graph) {
        // Replace the default location index with our custom one
        LocationIndex defaultIndex = graph.getLocationIndex();
        LocationIndex customIndex = new SmartTrailLocationIndex(
            defaultIndex,
            graph,
            snapConfig
        );
        graph.setLocationIndex(customIndex);
    }

    /**
     * Smart snapping with multiple strategies
     */
    private class SmartTrailLocationIndex implements LocationIndex {
        private final LocationIndex delegate;
        private final GraphHopperStorage graph;
        private final SnapConfig config;

        @Override
        public Snap findClosest(double lat, double lon, EdgeFilter requestFilter) {
            // Extract hints from request
            SnapHints hints = extractSnapHints();

            // Build snap strategy based on context
            SnapStrategy strategy = buildStrategy(hints);

            // Execute multi-phase snapping
            return strategy.snap(lat, lon, requestFilter);
        }

        private SnapStrategy buildStrategy(SnapHints hints) {
            // Seasonal considerations
            if (config.seasonalMode && isWinter()) {
                return new WinterSnapStrategy();
            }

            // User preferences
            if (hints.preferScenic) {
                return new ScenicSnapStrategy();
            }

            // Safety mode
            if (hints.avoidDifficult) {
                return new SafetySnapStrategy(hints.maxDifficulty);
            }

            // Default tiered strategy
            return new TieredSnapStrategy();
        }
    }

    /**
     * Winter-specific snapping
     */
    private class WinterSnapStrategy implements SnapStrategy {
        @Override
        public Snap snap(double lat, double lon, EdgeFilter filter) {
            // Only snap to winter-accessible trails
            EdgeFilter winterFilter = edge -> {
                if (!filter.accept(edge)) return false;

                // Check winter accessibility
                boolean winterAccessible = edge.get(winterAccessEnc);
                if (!winterAccessible) return false;

                // Avoid avalanche zones
                int avalancheRisk = edge.get(avalancheRiskEnc);
                if (avalancheRisk > 2) return false;

                // Prefer groomed trails
                boolean groomed = edge.get(groomedEnc);
                return groomed || edge.get(markedEnc);
            };

            // Try close winter trails first (50m)
            Snap snap = delegate.findClosest(lat, lon, winterFilter);
            if (snap.isValid() && snap.getDistance() < 50) {
                return snap;
            }

            // Fallback to any safe winter trail (200m)
            return delegate.findClosest(lat, lon,
                edge -> winterFilter.accept(edge) && edge.get(difficultyEnc).compareTo("T3") <= 0
            );
        }
    }

    /**
     * Scenic route snapping
     */
    private class ScenicSnapStrategy implements SnapStrategy {
        @Override
        public Snap snap(double lat, double lon, EdgeFilter filter) {
            // Score edges by scenic value and distance
            List<ScoredSnap> candidates = new ArrayList<>();

            // Get all edges within 500m
            Collection<Snap> nearbySnaps = delegate.findNClosest(lat, lon, filter, 10);

            for (Snap snap : nearbySnaps) {
                if (snap.getDistance() > 500) continue;

                EdgeIteratorState edge = snap.getClosestEdge();
                double scenicScore = edge.get(scenicScoreEnc);
                double distancePenalty = snap.getDistance() / 100.0;
                double totalScore = scenicScore - distancePenalty;

                candidates.add(new ScoredSnap(snap, totalScore));
            }

            // Return highest scoring snap
            return candidates.stream()
                .max(Comparator.comparing(s -> s.score))
                .map(s -> s.snap)
                .orElse(Snap.INVALID);
        }
    }

    /**
     * Safety-first snapping for beginners
     */
    private class SafetySnapStrategy implements SnapStrategy {
        private final String maxDifficulty;

        @Override
        public Snap snap(double lat, double lon, EdgeFilter filter) {
            EdgeFilter safeFilter = edge -> {
                if (!filter.accept(edge)) return false;

                // Check difficulty
                String difficulty = edge.get(difficultyEnc);
                if (difficulty.compareTo(maxDifficulty) > 0) return false;

                // Must be marked
                if (!edge.get(markedEnc)) return false;

                // Avoid dangerous conditions
                String surface = edge.get(surfaceEnc);
                if ("rock".equals(surface) || "scree".equals(surface)) return false;

                return true;
            };

            // Prefer very safe trails close by
            EdgeFilter verySafeFilter = edge ->
                safeFilter.accept(edge) && "T1".equals(edge.get(difficultyEnc));

            Snap snap = delegate.findClosest(lat, lon, verySafeFilter);
            if (snap.isValid() && snap.getDistance() < 100) {
                return snap;
            }

            // Fallback to any safe trail
            return delegate.findClosest(lat, lon, safeFilter);
        }
    }
}
```

### Approach 4: Dynamic Snapping Based on User Profile

```java
/**
 * User profile-aware snapping
 */
public class UserAwareSnappingPlugin implements GraphHopperPlugin {

    private UserService userService;

    @Override
    public LocationIndex createLocationIndex(GraphHopperStorage storage) {
        return new UserAwareLocationIndex(storage);
    }

    private class UserAwareLocationIndex implements LocationIndex {
        @Override
        public Snap findClosest(double lat, double lon, EdgeFilter filter) {
            // Get user from request context
            User user = RequestContext.getCurrentUser();
            UserProfile profile = userService.getProfile(user);

            // Build personalized snapping strategy
            return new PersonalizedSnapStrategy(profile).snap(lat, lon, filter);
        }
    }

    private class PersonalizedSnapStrategy {
        private final UserProfile profile;

        public Snap snap(double lat, double lon, EdgeFilter filter) {
            // Beginner: Snap only to easy, well-marked trails
            if (profile.experienceLevel == ExperienceLevel.BEGINNER) {
                return snapToEasyTrails(lat, lon, filter);
            }

            // Expert: Allow technical trails, prefer challenging
            if (profile.experienceLevel == ExperienceLevel.EXPERT) {
                return snapToChallengingTrails(lat, lon, filter);
            }

            // Family: Prefer wide, accessible trails
            if (profile.groupType == GroupType.FAMILY) {
                return snapToFamilyTrails(lat, lon, filter);
            }

            // History-based: Prefer trail types user has done before
            if (profile.hasHistory()) {
                return snapBasedOnHistory(lat, lon, filter, profile.getTrailHistory());
            }

            // Default
            return defaultSnap(lat, lon, filter);
        }

        private Snap snapToFamilyTrails(double lat, double lon, EdgeFilter filter) {
            EdgeFilter familyFilter = edge -> {
                if (!filter.accept(edge)) return false;

                // Must be easy
                String difficulty = edge.get(difficultyEnc);
                if (!"T1".equals(difficulty)) return false;

                // Must be wide enough
                double width = edge.get(widthEnc);
                if (width < 1.5) return false;  // meters

                // Should have facilities nearby
                boolean hasFacilities = checkNearbyFacilities(edge);

                return hasFacilities;
            };

            return delegate.findClosest(lat, lon, familyFilter);
        }
    }
}
```

## Configuration Examples

### YAML Configuration
```yaml
# config.yml
graphhopper:
  plugins:
    - com.yourcompany.graphhopper.plugins.NorwegianTrailSnappingPlugin

snapping:
  # Preferred trail operators in order
  preferred_operators:
    - DNT
    - "Den Norske Turistforening"
    - Kommune

  # Seasonal mode
  seasonal: true
  winter_months: [11, 12, 1, 2, 3, 4]

  # Difficulty limits
  max_difficulty: T4
  beginner_max: T2

  # Snap distances by tier (meters)
  distances:
    preferred: 50
    marked: 100
    unmarked: 200
    fallback: 500

  # Special rules
  avoid_unmarked: false
  require_maintenance: true
  scenic_preference: 0.3
```

### Request-Level Configuration

```java
// API endpoint modification
@POST
@Path("/route")
public Response calculateRoute(RouteRequest request) {
    // Extract snapping preferences from request
    PMap hints = request.getHints();

    // Set snapping preferences
    hints.putObject("snapping.prefer_operator", "DNT");
    hints.putObject("snapping.max_difficulty", "T3");
    hints.putObject("snapping.scenic_mode", true);
    hints.putObject("snapping.avoid_types", Arrays.asList("scramble", "ford"));

    // These hints are available in the LocationIndex
    return routingService.route(request);
}
```

## Integration with Existing GraphHopper

### 1. Build and Package Plugin
```xml
<!-- pom.xml -->
<project>
    <groupId>com.yourcompany</groupId>
    <artifactId>graphhopper-trail-snapping</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <dependency>
            <groupId>com.graphhopper</groupId>
            <artifactId>graphhopper-core</artifactId>
            <version>8.0</version>
            <scope>provided</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-jar-plugin</artifactId>
                <configuration>
                    <archive>
                        <manifestEntries>
                            <GraphHopper-Plugin>true</GraphHopper-Plugin>
                        </manifestEntries>
                    </archive>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

### 2. Deploy Plugin
```bash
# Build plugin
mvn clean package

# Copy to GraphHopper plugins directory
cp target/graphhopper-trail-snapping-1.0.0.jar /path/to/graphhopper/plugins/

# Run GraphHopper with plugin
java -jar graphhopper.jar \
  --config config.yml \
  --graph-location ./graph-cache \
  --plugins ./plugins
```

## Testing the Plugin

```java
@Test
public void testPreferredTrailSnapping() {
    // Setup
    GraphHopper hopper = new GraphHopper()
        .registerPlugin(new NorwegianTrailSnappingPlugin());

    // Test DNT trail preference
    GHRequest request = new GHRequest(59.9139, 10.7522, 59.9275, 10.7389);
    request.getHints().putObject("snapping.prefer_operator", "DNT");

    GHResponse response = hopper.route(request);

    // Verify snapped to DNT trail
    Path path = response.getBest();
    EdgeIteratorState firstEdge = path.getEdges().get(0);
    assertEquals("DNT", firstEdge.get(operatorEnc));
}

@Test
public void testSeasonalSnapping() {
    // Winter mode
    request.getHints().putObject("snapping.winter_mode", true);

    GHResponse response = hopper.route(request);

    // Verify snapped to winter-accessible trail
    Path path = response.getBest();
    for (EdgeIteratorState edge : path.getEdges()) {
        assertTrue(edge.get(winterAccessEnc));
        assertTrue(edge.get(avalancheRiskEnc) <= 2);
    }
}
```

## Performance Considerations

```java
// Cache snapping decisions
public class CachedSnappingLocationIndex implements LocationIndex {
    private final Cache<SnapKey, Snap> cache = Caffeine.newBuilder()
        .maximumSize(10_000)
        .expireAfterWrite(5, TimeUnit.MINUTES)
        .build();

    @Override
    public Snap findClosest(double lat, double lon, EdgeFilter filter) {
        SnapKey key = new SnapKey(lat, lon, filter.hashCode());

        return cache.get(key, k ->
            delegate.findClosest(lat, lon, filter)
        );
    }
}
```

## Advanced Features

### Machine Learning-Based Snapping
```java
public class MLSnapPredictor {
    private final ONNXModel model;

    public Snap predictBestSnap(double lat, double lon, List<Snap> candidates) {
        // Features: distance, trail quality, user history, weather, time of day
        float[][] features = extractFeatures(candidates);

        // Predict best snap
        float[] scores = model.predict(features);

        int bestIndex = argmax(scores);
        return candidates.get(bestIndex);
    }
}
```

### Real-Time Conditions
```java
public class RealtimeSnapStrategy implements SnapStrategy {
    @Override
    public Snap snap(double lat, double lon, EdgeFilter filter) {
        // Check real-time trail conditions
        EdgeFilter realtimeFilter = edge -> {
            if (!filter.accept(edge)) return false;

            // Check if trail is currently open
            TrailStatus status = trailStatusService.getStatus(edge.getId());
            if (status == TrailStatus.CLOSED) return false;

            // Check current weather
            Weather weather = weatherService.getCurrent(edge.getGeometry());
            if (weather.hasWarning()) return false;

            return true;
        };

        return delegate.findClosest(lat, lon, realtimeFilter);
    }
}
```

## Conclusion

GraphHopper's plugin system allows sophisticated custom snapping logic including:
- Multi-tier snapping with fallbacks
- User profile-based preferences
- Seasonal and weather-aware snapping
- Trail type preferences (DNT, marked, difficulty)
- Real-time condition checking
- Machine learning integration

The key is combining EdgeFilters, custom LocationIndex implementations, and the plugin system to create intelligent snapping behavior tailored to your specific needs.

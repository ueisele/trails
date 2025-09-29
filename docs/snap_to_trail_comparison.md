# Snap-to-Trail Comparison: GraphHopper vs QGIS/pgRouting vs BRouter

## Overview

Snap-to-trail is the ability to automatically route along existing trail networks rather than straight-line or road routing. Each tool implements this differently with varying levels of sophistication.

## How Each Tool Implements Snap-to-Trail

### 1. GraphHopper - Network-Based Snapping

**Method**: Pre-processed routing graph with spatial index

```java
// GraphHopper's approach
public class GraphHopperSnapping {
    // Uses a LocationIndex (QuadTree) for fast spatial queries
    private LocationIndex locationIndex;

    public Snap findClosestEdge(double lat, double lon) {
        // 1. Query spatial index for nearby edges
        // 2. Project point onto edges
        // 3. Return closest valid snap point
        return locationIndex.findClosest(lat, lon, EdgeFilter.ALL_EDGES);
    }
}
```

**Key Characteristics:**
- **Snap Distance**: Configurable (default 200m, can be set per request)
- **Snap Method**: Perpendicular projection onto nearest edge
- **Multiple Candidates**: Considers multiple edges, picks best based on heading
- **Performance**: Very fast (< 5ms typically)

**Configuration:**
```yaml
# config.yml
routing:
  snap_max_distance: 500  # meters
  snap_preventions: [ferry, motorway]  # Don't snap to these
  heading_penalty: 120  # Penalty for wrong direction
```

**API Request:**
```json
{
  "points": [[10.7522, 59.9139], [10.7389, 59.9275]],
  "snap_preventions": ["trunk", "ferry"],
  "point_hints": ["trail", "path"],
  "headings": [45, 90],
  "heading_penalty": 120
}
```

### 2. QGIS/pgRouting - Topology-Based Snapping

**Method**: PostGIS spatial operations with network topology

```sql
-- pgRouting's approach
CREATE OR REPLACE FUNCTION snap_to_trail(
    point geometry,
    max_distance float DEFAULT 50
) RETURNS integer AS $$
DECLARE
    closest_node integer;
BEGIN
    -- Find closest node in network topology
    SELECT id INTO closest_node
    FROM trail_nodes
    WHERE ST_DWithin(geom, point, max_distance)
    ORDER BY ST_Distance(geom, point)
    LIMIT 1;

    -- If no node found, create virtual node
    IF closest_node IS NULL THEN
        -- Find closest edge and split it
        WITH closest_edge AS (
            SELECT id, geom
            FROM trail_network
            WHERE ST_DWithin(geom, point, max_distance)
            ORDER BY ST_Distance(geom, point)
            LIMIT 1
        )
        -- Split edge at closest point
        SELECT create_virtual_node(point, closest_edge.id)
        INTO closest_node
        FROM closest_edge;
    END IF;

    RETURN closest_node;
END;
$$ LANGUAGE plpgsql;
```

**Key Characteristics:**
- **Snap Distance**: Fully customizable via SQL
- **Snap Method**: Can snap to nodes, edges, or create virtual nodes
- **Topology Aware**: Maintains network connectivity
- **Performance**: Slower (10-50ms with spatial index)

**Python/QGIS Processing:**
```python
def snap_to_network(point, network_layer, tolerance=50):
    """QGIS processing approach"""
    # Use QGIS native algorithms
    result = processing.run("native:snapgeometries", {
        'INPUT': point_layer,
        'REFERENCE_LAYER': network_layer,
        'TOLERANCE': tolerance,
        'BEHAVIOR': 1,  # Prefer nodes, then edges
        'OUTPUT': 'memory:snapped'
    })

    # Optional: Create virtual nodes for routing
    if need_virtual_node:
        result = processing.run("native:splitlinesbylayer", {
            'INPUT': network_layer,
            'LINES': snapped_points,
            'OUTPUT': 'memory:split_network'
        })

    return result['OUTPUT']
```

### 3. BRouter - Profile-Based Snapping

**Method**: Profile-driven with configurable snap behavior

```ini
# BRouter profile configuration
---context:global
assign consider_snapping = true
assign max_snap_distance = 100  # meters
assign snap_buffer = 20  # additional buffer

---context:node
# Node snapping preferences
assign node_snap_bonus =
    switch junction=yes 50
    switch trail_junction=yes 100
    0

---context:way
# Way snapping preferences
assign way_snap_priority =
    switch highway=path 1.0
    switch highway=footway 0.9
    switch highway=track 0.8
    switch highway=unclassified 0.5
    0.1  # Avoid snapping to non-trail ways
```

**Key Characteristics:**
- **Snap Distance**: Profile-configurable
- **Snap Method**: Cost-based (prefers certain way types)
- **Profile Integration**: Snapping rules part of routing profile
- **Performance**: Fast (< 10ms)

**Java Implementation:**
```java
// BRouter's internal snapping
public class BRouterSnapping {
    public MatchedWaypoint snapToNetwork(OsmNodeNamed point) {
        // 1. Load nearby segments from RD5 files
        List<OsmPath> nearbyPaths = loadNearbySegments(point, maxSnapDistance);

        // 2. Apply profile-based filtering
        nearbyPaths = filterByProfile(nearbyPaths, routingProfile);

        // 3. Find best match based on distance and profile cost
        OsmPath bestPath = null;
        double bestCost = Double.MAX_VALUE;

        for (OsmPath path : nearbyPaths) {
            double distance = calculateDistance(point, path);
            double profileCost = routingProfile.getSnapCost(path);
            double totalCost = distance + profileCost;

            if (totalCost < bestCost) {
                bestCost = totalCost;
                bestPath = path;
            }
        }

        return createMatchedWaypoint(point, bestPath);
    }
}
```

## Comparison Matrix

| Feature | GraphHopper | QGIS/pgRouting | BRouter |
|---------|------------|----------------|---------|
| **Snapping Method** |
| Approach | Spatial index (QuadTree) | PostGIS spatial queries | Profile-based cost |
| Default Distance | 200m | User-defined | 100m |
| Max Distance | Unlimited (configurable) | Unlimited | Profile-limited |
| Virtual Nodes | ✅ Automatic | ✅ Can create | ✅ Automatic |
| **Snapping Quality** |
| Edge Projection | ✅ Perpendicular | ✅ Nearest point | ✅ Along edge |
| Node Preference | ⚠️ Optional | ✅ Configurable | ✅ Profile-based |
| Direction Aware | ✅ Heading penalty | ⚠️ Via custom SQL | ❌ No |
| Multi-Point | ✅ Batch processing | ⚠️ Sequential | ✅ Batch |
| **Customization** |
| Custom Rules | Java code | SQL functions | Profile DSL |
| Way Type Filter | ✅ EdgeFilter | ✅ WHERE clause | ✅ Profile rules |
| Dynamic Adjustment | ✅ Per request | ✅ Per query | ❌ Fixed in profile |
| **Performance** |
| Single Point | ~5ms | 10-50ms | ~10ms |
| Batch (100 points) | ~50ms | 500-2000ms | ~100ms |
| Index Type | QuadTree | R-Tree (GIST) | Grid-based |
| **Network Handling** |
| Disconnected Networks | Handles gracefully | Can detect | May fail |
| Islands | Detects | SQL analyzable | Profile-dependent |
| One-way Awareness | ✅ Full | ✅ Full | ✅ Full |
| Turn Restrictions | ✅ Considered | ✅ Considered | ⚠️ Limited |

## Real-World Examples

### Example 1: Snapping to Norwegian DNT Trails

**GraphHopper:**
```java
// Custom edge filter for DNT trails only
EdgeFilter dntFilter = new EdgeFilter() {
    @Override
    public boolean accept(EdgeIteratorState edge) {
        return "DNT".equals(edge.get(operatorEnc));
    }
};

QueryResult snap = locationIndex.findClosest(lat, lon, dntFilter);
```

**QGIS/pgRouting:**
```sql
-- Snap only to DNT trails
SELECT ST_ClosestPoint(geom, point) as snap_point, id
FROM trails
WHERE operator = 'DNT'
  AND ST_DWithin(geom, point, 200)
ORDER BY ST_Distance(geom, point)
LIMIT 1;
```

**BRouter:**
```ini
# Profile prefers DNT trails for snapping
assign way_snap_priority =
    switch operator=DNT 2.0
    switch operator="Den Norske Turistforening" 2.0
    1.0
```

### Example 2: Multi-Point Route with Different Snap Distances

**GraphHopper:**
```json
{
  "points": [
    {"lat": 59.9139, "lon": 10.7522, "snap_distance": 500},
    {"lat": 60.1285, "lon": 10.6631, "snap_distance": 100},
    {"lat": 60.3507, "lon": 10.4853, "snap_distance": 200}
  ]
}
```

**QGIS/pgRouting:**
```python
# Variable snap distances
snap_configs = [
    (point1, 500),  # Trailhead - larger snap
    (point2, 100),  # On trail - small snap
    (point3, 200),  # Near trail - medium snap
]

snapped_points = []
for point, distance in snap_configs:
    snapped = snap_to_trail(point, max_distance=distance)
    snapped_points.append(snapped)
```

**BRouter:**
```ini
# Fixed in profile, but can use different profiles
assign max_snap_distance =
    switch is_trailhead 500
    switch is_waypoint 100
    200  # default
```

## Handling Edge Cases

### Disconnected Networks

**GraphHopper:**
```java
// Detects and reports disconnected networks
if (!snap.isValid()) {
    // Try increasing snap distance or different filter
    snap = locationIndex.findClosest(lat, lon,
        EdgeFilter.ALL_EDGES, 1000);  // 1km radius
}
```

**QGIS/pgRouting:**
```sql
-- Check network connectivity
WITH RECURSIVE connected AS (
    SELECT id, source, target FROM trail_network WHERE id = 1
    UNION
    SELECT n.id, n.source, n.target
    FROM trail_network n
    JOIN connected c ON n.source = c.target OR n.target = c.source
)
SELECT COUNT(DISTINCT id) as connected_edges,
       (SELECT COUNT(*) FROM trail_network) as total_edges;
```

**BRouter:**
- Limited handling, may route around disconnected segments

### No Trail Within Snap Distance

**GraphHopper:**
- Returns error with closest trail distance
- Can fallback to direct routing

**QGIS/pgRouting:**
- Can create direct line to nearest trail
- Or return null/error

**BRouter:**
- Typically fails
- No automatic fallback

## Performance Optimization Tips

### GraphHopper
```java
// Pre-warm location index
locationIndex.prepareIndex();

// Use bounded queries
QueryResult snap = locationIndex.findClosest(
    lat, lon, EdgeFilter.ALL_EDGES,
    maxDistance  // Limit search radius
);
```

### QGIS/pgRouting
```sql
-- Ensure spatial indexes exist
CREATE INDEX idx_trails_geom ON trails USING GIST (geom);

-- Use ST_DWithin for bounded search
WHERE ST_DWithin(geom, point, 200)  -- Uses index
-- Instead of
WHERE ST_Distance(geom, point) < 200  -- Full scan
```

### BRouter
```ini
# Reduce search radius in profile
assign max_snap_distance = 50  # Smaller = faster

# Limit way types considered
assign validForFoot =
    switch highway=path|footway|track 1
    0  # Ignore others
```

## Recommendations

### When to Use Each Tool's Snapping

**GraphHopper** - Best for:
- High-performance API applications
- Dynamic snap distances per request
- Custom snap filters (e.g., seasonal trails)
- Large-scale routing services

**QGIS/pgRouting** - Best for:
- Complex spatial analysis alongside routing
- Custom snapping logic via SQL
- Integration with existing GIS workflows
- Debugging network topology issues

**BRouter** - Best for:
- Consistent snap behavior across routes
- Offline applications
- Simple profile-based rules
- Mobile/embedded systems

### Hybrid Approach

For maximum flexibility, you could:
1. Use QGIS to prepare and validate network topology
2. Export to GraphHopper for production routing API
3. Generate BRouter segments for offline mobile apps

```python
# Example workflow
# 1. QGIS: Prepare network
clean_network = clean_topology(raw_trails)
validate_connectivity(clean_network)

# 2. Export for GraphHopper
export_to_osm(clean_network, "trails.osm")
os.system("java -jar graphhopper.jar import trails.osm")

# 3. Generate BRouter files
export_to_rd5(clean_network, "segments/")
```

## Conclusion

- **GraphHopper**: Most sophisticated and performant snapping, best for production APIs
- **QGIS/pgRouting**: Most flexible with SQL control, best for analysis and custom logic
- **BRouter**: Simplest but effective, best for offline and profile-based snapping

All three handle snap-to-trail well, but GraphHopper offers the best balance of performance and features for most routing applications.

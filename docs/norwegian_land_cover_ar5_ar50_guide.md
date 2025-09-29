# Norwegian Land Cover Data: AR5/AR50 Guide for Trail Planning

## Overview

Land cover data is essential for trail planning, providing information about the physical surface of the terrain. In Norway, the AR5 and AR50 (Arealressurskart) systems provide comprehensive land resource mapping that can significantly enhance trail routing algorithms.

## What is Land Cover?

Land cover refers to the physical material at the surface of the Earth, including:
- **Natural vegetation** (forests, grasslands, heathlands)
- **Water bodies** (lakes, rivers, wetlands)
- **Bare surfaces** (rock, sand, soil, snow)
- **Cultivated areas** (agriculture, managed forests)
- **Built environments** (urban areas, infrastructure)

### Why Land Cover Matters for Trails

Land cover directly affects:
- **Trail difficulty**: Rock fields vs forest paths vs wetlands
- **Seasonal accessibility**: Wetlands frozen in winter vs impassable in summer
- **Surface conditions**: Predicting mud, water, rock, vegetation
- **Route planning**: Avoiding difficult terrain, finding optimal paths
- **Safety considerations**: Identifying hazardous areas (bogs, scree slopes)
- **Environmental impact**: Avoiding sensitive ecosystems

## Norwegian AR5/AR50 Systems

### AR5 (Arealressurskart 1:5000)

**Detailed Land Resource Map**
- **Scale**: 1:5,000 (high detail)
- **Coverage**: ~180,000 km² (agricultural and forest areas)
- **Minimum mapping unit**: 0.5 dekar (urban), 1.5 dekar (agriculture), 2 dekar (forest)
- **Accuracy**: ±2-5 meters positional accuracy
- **Updates**: Continuous updates in priority areas

### AR50 (Arealressurskart 1:50000)

**Overview Land Resource Map**
- **Scale**: 1:50,000 (medium detail)
- **Coverage**: Entire Norwegian mainland (323,000 km²)
- **Minimum mapping unit**: 15 dekar (agriculture), 25 dekar (forest/mountain)
- **Accuracy**: ±10-20 meters positional accuracy
- **Purpose**: Regional planning, overview analysis

## AR5/AR50 Classification System

### Main Categories with Trail Relevance

```python
# AR5 Land Cover Types for Trail Planning
AR5_TRAIL_CATEGORIES = {
    # Built-up Areas (10-series)
    "11": {"name": "Residential", "trail_impact": "Avoid/urban paths only"},
    "12": {"name": "Industrial", "trail_impact": "Generally avoid"},
    "13": {"name": "Roads/railways", "trail_impact": "Crossing points only"},

    # Agricultural Land (20-series)
    "21": {"name": "Cultivated land", "trail_impact": "Edge routing only"},
    "22": {"name": "Pasture", "trail_impact": "Possible with permission"},
    "23": {"name": "Meadow", "trail_impact": "Good for trails"},

    # Forest (30-series)
    "30": {"name": "Forest - high productivity", "trail_impact": "Excellent trails"},
    "31": {"name": "Forest - medium productivity", "trail_impact": "Good trails"},
    "32": {"name": "Forest - low productivity", "trail_impact": "Moderate trails"},
    "33": {"name": "Forest - impediment", "trail_impact": "Difficult terrain"},

    # Open Land (50-series)
    "50": {"name": "Open firm ground", "trail_impact": "Easy walking"},
    "51": {"name": "Grassland", "trail_impact": "Good trails"},
    "52": {"name": "Heath", "trail_impact": "Variable conditions"},
    "53": {"name": "Open wetland", "trail_impact": "Seasonal/difficult"},

    # Wetlands (60-series)
    "60": {"name": "Mire/bog", "trail_impact": "Very difficult/avoid"},
    "61": {"name": "Forested mire", "trail_impact": "Difficult/seasonal"},

    # Bare Ground (70-series)
    "70": {"name": "Rock and blockfields", "trail_impact": "Technical terrain"},
    "71": {"name": "Exposed bedrock", "trail_impact": "Rock scrambling"},
    "72": {"name": "Gravel and sand", "trail_impact": "Loose surface"},

    # Water (80-series)
    "80": {"name": "Freshwater", "trail_impact": "Impassable"},
    "81": {"name": "Ocean", "trail_impact": "Coastal paths only"},
    "82": {"name": "Glacier", "trail_impact": "Special equipment needed"},

    # Other
    "99": {"name": "Not mapped", "trail_impact": "Unknown conditions"}
}
```

### Detailed Forest Classifications

```python
# Forest subtypes (important for trail conditions)
FOREST_DETAILS = {
    "Treslag (Tree species)": {
        "31": "Spruce dominated",      # Dense canopy, needle floor
        "32": "Pine dominated",        # Open canopy, good visibility
        "33": "Deciduous dominated",   # Seasonal changes, leaf litter
        "39": "Mixed forest"           # Variable conditions
    },

    "Skogbonitet (Productivity)": {
        "6-8": "Very low - rocky/thin soil",    # Difficult terrain
        "11-14": "Medium - normal forest",      # Good for trails
        "17-20": "High - dense vegetation",     # May be overgrown
        "23-26": "Very high - thick understory" # Difficult passage
    }
}
```

## Integration with Trail Systems

### 1. GraphHopper Integration

```java
// Custom AR5 Land Cover Encoder
public class AR5LandCoverEncoder extends StringEncodedValue {
    public AR5LandCoverEncoder() {
        super("ar5_landcover", 5);  // 5 bits for AR5 codes
    }
}

// Land Cover Weighting
public class NorwegianLandCoverWeighting extends AbstractWeighting {

    private static final Map<String, Double> LAND_COVER_COSTS = Map.of(
        "30", 1.0,   // High productivity forest - baseline
        "31", 1.1,   // Medium forest - slightly slower
        "32", 1.3,   // Low forest - rougher terrain
        "33", 1.8,   // Impediment forest - difficult
        "50", 0.9,   // Open ground - faster
        "52", 1.2,   // Heath - uneven
        "53", 2.5,   // Open wetland - very slow
        "60", 5.0,   // Bog - avoid if possible
        "70", 3.0    // Rock fields - technical
    );

    @Override
    public double calcEdgeWeight(EdgeIteratorState edge, boolean reverse) {
        String landCover = edge.get(ar5Enc);
        double baseCost = super.calcEdgeWeight(edge, reverse);

        // Apply land cover multiplier
        double multiplier = LAND_COVER_COSTS.getOrDefault(landCover, 1.5);

        // Seasonal adjustments
        if (isWinter()) {
            if ("53".equals(landCover) || "60".equals(landCover)) {
                multiplier *= 0.5;  // Frozen wetlands are easier
            } else if ("70".equals(landCover)) {
                multiplier *= 1.5;  // Icy rocks are dangerous
            }
        }

        return baseCost * multiplier;
    }
}
```

### 2. PostGIS/pgRouting Integration

```sql
-- Create AR5 land cover table
CREATE TABLE ar5_landcover (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(POLYGON, 25833),  -- UTM 33N
    artype INTEGER,                  -- Land cover type
    artreslag INTEGER,               -- Tree species
    arskogbon INTEGER,               -- Forest productivity
    argrunnf VARCHAR(2),             -- Soil conditions
    areal_m2 FLOAT
);

-- Import AR5 data
ogr2ogr -f PostgreSQL \
  PG:"dbname=trails user=postgres" \
  AR5_data.gml \
  -nln ar5_landcover \
  -t_srs EPSG:25833

-- Spatial index
CREATE INDEX idx_ar5_geom ON ar5_landcover USING GIST(geom);

-- Analyze trail segments by land cover
CREATE VIEW trail_land_cover AS
WITH trail_segments AS (
    SELECT
        t.id,
        t.geom,
        ST_Length(t.geom) as segment_length
    FROM trails t
)
SELECT
    ts.id as trail_id,
    ar.artype as land_cover_type,
    CASE
        WHEN ar.artype = 30 THEN 'High forest'
        WHEN ar.artype = 31 THEN 'Medium forest'
        WHEN ar.artype = 32 THEN 'Low forest'
        WHEN ar.artype = 33 THEN 'Impediment forest'
        WHEN ar.artype = 50 THEN 'Open ground'
        WHEN ar.artype = 52 THEN 'Heath'
        WHEN ar.artype = 53 THEN 'Open wetland'
        WHEN ar.artype = 60 THEN 'Bog/mire'
        WHEN ar.artype = 70 THEN 'Rock/scree'
        ELSE 'Other'
    END as terrain_type,
    ST_Length(ST_Intersection(ts.geom, ar.geom)) as length_in_terrain,
    ST_Length(ST_Intersection(ts.geom, ar.geom)) / ts.segment_length * 100 as percent_of_trail
FROM trail_segments ts
JOIN ar5_landcover ar ON ST_Intersects(ts.geom, ar.geom)
ORDER BY ts.id, length_in_terrain DESC;

-- Calculate trail difficulty based on land cover
CREATE OR REPLACE FUNCTION calculate_trail_difficulty_from_landcover(trail_id INTEGER)
RETURNS TEXT AS $$
DECLARE
    difficulty_score FLOAT := 0;
    total_length FLOAT;
    land_cover_cursor CURSOR FOR
        SELECT land_cover_type, SUM(length_in_terrain) as total
        FROM trail_land_cover
        WHERE trail_id = $1
        GROUP BY land_cover_type;
BEGIN
    SELECT SUM(length_in_terrain) INTO total_length
    FROM trail_land_cover
    WHERE trail_id = $1;

    FOR record IN land_cover_cursor LOOP
        difficulty_score := difficulty_score +
            CASE record.land_cover_type
                WHEN 30 THEN 1.0  -- Forest high
                WHEN 31 THEN 1.2  -- Forest medium
                WHEN 32 THEN 1.5  -- Forest low
                WHEN 33 THEN 2.0  -- Impediment
                WHEN 50 THEN 0.8  -- Open ground
                WHEN 52 THEN 1.3  -- Heath
                WHEN 53 THEN 2.5  -- Wetland
                WHEN 60 THEN 3.0  -- Bog
                WHEN 70 THEN 2.8  -- Rock
                ELSE 1.5
            END * (record.total / total_length);
    END LOOP;

    RETURN CASE
        WHEN difficulty_score < 1.2 THEN 'T1 - Easy'
        WHEN difficulty_score < 1.5 THEN 'T2 - Moderate'
        WHEN difficulty_score < 2.0 THEN 'T3 - Demanding'
        WHEN difficulty_score < 2.5 THEN 'T4 - Challenging'
        ELSE 'T5 - Difficult'
    END;
END;
$$ LANGUAGE plpgsql;
```

### 3. Python Processing

```python
import geopandas as gpd
import rasterio
from shapely.geometry import LineString
import numpy as np

class LandCoverAnalyzer:
    """Analyze trails using AR5/AR50 land cover data"""

    def __init__(self, ar5_path, ar50_path=None):
        self.ar5 = gpd.read_file(ar5_path)
        self.ar50 = gpd.read_file(ar50_path) if ar50_path else None

        # Land cover difficulty weights
        self.difficulty_weights = {
            30: 1.0,   # Forest high - baseline
            31: 1.2,   # Forest medium
            32: 1.5,   # Forest low
            33: 2.0,   # Impediment
            50: 0.8,   # Open ground
            51: 0.9,   # Grassland
            52: 1.3,   # Heath
            53: 2.5,   # Open wetland
            60: 4.0,   # Mire/bog
            61: 3.5,   # Forested mire
            70: 3.0,   # Rock fields
            71: 3.5,   # Exposed bedrock
            72: 2.0,   # Gravel/sand
        }

    def analyze_trail(self, trail_geometry):
        """Analyze trail conditions based on land cover"""

        # Find intersecting land cover polygons
        intersections = self.ar5[self.ar5.intersects(trail_geometry)]

        results = []
        total_length = trail_geometry.length

        for _, land_cover in intersections.iterrows():
            # Calculate intersection
            intersection = trail_geometry.intersection(land_cover.geometry)
            if intersection.is_empty:
                continue

            segment_length = intersection.length
            percentage = (segment_length / total_length) * 100

            results.append({
                'land_cover_type': land_cover['artype'],
                'description': self.get_description(land_cover['artype']),
                'length_m': segment_length,
                'percentage': percentage,
                'difficulty_weight': self.difficulty_weights.get(land_cover['artype'], 1.5),
                'seasonal_notes': self.get_seasonal_notes(land_cover['artype'])
            })

        return self.summarize_results(results)

    def get_seasonal_notes(self, artype):
        """Get seasonal considerations for land cover type"""
        seasonal_notes = {
            53: "Very wet in spring/summer, better when frozen in winter",
            60: "Impassable in summer, possible when frozen",
            61: "Difficult year-round, worst in spring thaw",
            70: "Ice hazard in winter, loose rocks in summer",
            52: "Can be boggy in wet weather, good when dry",
            33: "Dense undergrowth in summer, easier in winter"
        }
        return seasonal_notes.get(artype, "Conditions vary by season")

    def predict_trail_surface(self, land_cover_type):
        """Predict likely trail surface from land cover"""
        surface_prediction = {
            30: "forest_floor",     # Needles, roots, firm soil
            31: "forest_floor",
            32: "rough_forest",     # Roots, rocks, uneven
            33: "very_rough",       # Boulders, fallen trees
            50: "grass_earth",      # Firm ground
            52: "heath_terrain",    # Uneven, heather
            53: "wet_bog",          # Wet, soft ground
            60: "bog",              # Very wet, dangerous
            70: "rock_scree",       # Loose rocks
            71: "bedrock",          # Solid rock
            72: "gravel"            # Loose gravel/sand
        }
        return surface_prediction.get(land_cover_type, "unknown")

    def calculate_seasonal_difficulty(self, trail_geometry, season='summer'):
        """Calculate difficulty adjusted for season"""

        base_analysis = self.analyze_trail(trail_geometry)

        # Seasonal multipliers
        if season == 'winter':
            # Frozen wetlands are easier, rocks are harder
            adjustments = {53: 0.5, 60: 0.4, 61: 0.6, 70: 1.5, 71: 1.8}
        elif season == 'spring':
            # Thaw makes everything muddy
            adjustments = {53: 1.5, 60: 2.0, 30: 1.2, 31: 1.2}
        elif season == 'autumn':
            # Wet leaves, early frost
            adjustments = {30: 1.1, 31: 1.1, 71: 1.2}
        else:  # summer
            adjustments = {}

        adjusted_difficulty = base_analysis['average_difficulty']
        for land_type, multiplier in adjustments.items():
            if land_type in base_analysis['land_cover_types']:
                adjusted_difficulty *= multiplier

        return adjusted_difficulty
```

## Data Access and APIs

### Downloading AR5/AR50 Data

```python
import requests
import zipfile
import os

def download_ar5_data(kommune_nr, output_dir):
    """Download AR5 data for a specific municipality"""

    base_url = "https://nedlasting.geonorge.no/geonorge/Basisdata/ArealressursAR5/FGDB/"
    filename = f"Basisdata_{kommune_nr}_Halden_25833_ArealressursAR5_FGDB.zip"

    # Download
    response = requests.get(f"{base_url}{filename}")

    # Save and extract
    zip_path = os.path.join(output_dir, filename)
    with open(zip_path, 'wb') as f:
        f.write(response.content)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(output_dir)

    return os.path.join(output_dir, "ArealressursAR5.gdb")
```

### WMS/WFS Services

```python
# Access AR5 via WMS
AR5_WMS = "https://wms.geonorge.no/skwms1/wms.ar5"

# Access AR50 via WFS
AR50_WFS = "https://wfs.geonorge.no/skwms1/wfs.ar50"

# Example WFS query
def get_ar50_landcover(bbox):
    """Get AR50 data for bounding box"""

    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'ar50:ArealressursFlate',
        'bbox': f'{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:25833',
        'outputFormat': 'application/json'
    }

    response = requests.get(AR50_WFS, params=params)
    return response.json()
```

## Practical Applications

### 1. Automatic Trail Classification

```python
def classify_trail_from_landcover(trail_gdf, ar5_gdf):
    """Automatically classify trail difficulty from land cover"""

    classifications = []

    for _, trail in trail_gdf.iterrows():
        # Get land cover composition
        land_cover = analyze_land_cover(trail.geometry, ar5_gdf)

        # Calculate metrics
        wetland_percentage = land_cover.get(53, 0) + land_cover.get(60, 0)
        rock_percentage = land_cover.get(70, 0) + land_cover.get(71, 0)
        forest_percentage = sum(land_cover.get(i, 0) for i in [30, 31, 32, 33])

        # Classify
        if wetland_percentage > 30:
            classification = "Wetland trail - seasonal access"
        elif rock_percentage > 40:
            classification = "Technical rock trail"
        elif forest_percentage > 70:
            classification = "Forest trail"
        else:
            classification = "Mixed terrain trail"

        classifications.append(classification)

    trail_gdf['auto_classification'] = classifications
    return trail_gdf
```

### 2. Seasonal Route Planning

```python
def find_season_appropriate_route(start, end, season, network, ar5_data):
    """Find best route for current season"""

    if season == 'winter':
        # Prefer open areas (better visibility in snow)
        # Avoid steep rocks (ice danger)
        preferred_landcover = [50, 51, 52]
        avoid_landcover = [70, 71]
        wetland_passable = True

    elif season == 'spring':
        # Avoid all wetlands (maximum water)
        # Prefer high ground
        preferred_landcover = [30, 31, 70, 71]
        avoid_landcover = [53, 60, 61]
        wetland_passable = False

    elif season == 'summer':
        # All terrain possible but prefer forest (shade)
        preferred_landcover = [30, 31, 32]
        avoid_landcover = [60]  # Still avoid deep bogs
        wetland_passable = False

    else:  # autumn
        # Avoid slippery rocks and wet leaves
        preferred_landcover = [50, 51, 52]
        avoid_landcover = [71]  # Wet rock is dangerous
        wetland_passable = False

    # Adjust network weights based on land cover
    adjusted_network = adjust_network_weights(
        network, ar5_data, preferred_landcover,
        avoid_landcover, wetland_passable
    )

    # Calculate route on adjusted network
    return calculate_route(start, end, adjusted_network)
```

### 3. Trail Maintenance Planning

```python
def identify_maintenance_priorities(trails_gdf, ar5_gdf):
    """Identify trail sections needing special maintenance"""

    maintenance_needs = []

    for _, trail in trails_gdf.iterrows():
        land_cover = analyze_land_cover(trail.geometry, ar5_gdf)

        # Check for problematic land covers
        if land_cover.get(53, 0) > 20:  # Open wetland
            maintenance_needs.append({
                'trail_id': trail['id'],
                'issue': 'Wetland crossing',
                'solution': 'Install boardwalk',
                'priority': 'high',
                'length_m': land_cover[53] * trail.geometry.length
            })

        if land_cover.get(60, 0) > 10:  # Bog
            maintenance_needs.append({
                'trail_id': trail['id'],
                'issue': 'Bog section',
                'solution': 'Reroute or extensive boardwalk',
                'priority': 'critical',
                'length_m': land_cover[60] * trail.geometry.length
            })

        if land_cover.get(70, 0) > 30:  # Rock fields
            maintenance_needs.append({
                'trail_id': trail['id'],
                'issue': 'Technical rock section',
                'solution': 'Install cairns and paint markers',
                'priority': 'medium',
                'length_m': land_cover[70] * trail.geometry.length
            })

    return pd.DataFrame(maintenance_needs)
```

## Best Practices

### 1. Data Resolution Considerations

- Use **AR5** for detailed local trail planning (< 10 km trails)
- Use **AR50** for regional route planning and overview analysis
- Combine both for multi-scale applications

### 2. Validation

Always validate land cover predictions with:
- Field observations
- Aerial imagery
- User reports
- Seasonal variations

### 3. Update Frequency

- AR5: Updated continuously in priority areas
- AR50: Less frequent updates
- Consider data age when making decisions

### 4. Limitations

- Land cover != trail surface (trail might have boardwalk over bog)
- Seasonal changes not captured in static data
- Human modifications may not be reflected
- Minimum mapping units may miss small features

## Conclusion

AR5/AR50 land cover data provides valuable context for trail planning in Norway:
- Automatic difficulty assessment
- Seasonal accessibility prediction
- Surface condition estimation
- Maintenance planning
- Safety considerations

When integrated with trail routing systems like GraphHopper or pgRouting, land cover data enables intelligent, context-aware route planning that considers terrain conditions, seasonal variations, and user safety.

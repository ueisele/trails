# Land Cover Integration Design

## Overview

This document describes the integration of land cover data into the GraphHopper routing pipeline to enable terrain-aware routing that considers vegetation, forest density, and surface conditions.

## Why Land Cover Data?

Land cover information enables:
- **Forest trail preferences**: Prefer shaded forest paths in summer
- **Open terrain routing**: Avoid dense forest in winter (avalanche risk)
- **Surface type inference**: Infer likely trail conditions from vegetation
- **Scenic route planning**: Route through varied landscapes
- **Weather-appropriate routing**: Avoid exposed areas in bad weather

## Data Source Options

### Option 1: AR5 (Norwegian Official Data)

**Source**: Kartverket / NIBIO
**Resolution**: 1:5,000 (very high quality)
**License**: ⚠️ **Restricted** - Requires "Norge digitalt" agreement

**Pros:**
- ✅ High quality official data
- ✅ 104 detailed land cover classes
- ✅ Maintained and updated regularly
- ✅ Includes forest types, soil conditions, land use

**Cons:**
- ❌ Requires special agreement/license
- ❌ Not freely downloadable without permission
- ❌ Complex licensing for public projects
- ❌ May have usage restrictions

**Verdict**: ❌ **Not suitable** for open-source pipeline

### Option 2: ESA WorldCover (Recommended)

**Source**: European Space Agency (ESA)
**Resolution**: 10 meters
**License**: ✅ **CC BY 4.0** (Free and open)
**URL**: https://worldcover2021.esa.int/

**Pros:**
- ✅ Free and open (CC BY 4.0)
- ✅ Global coverage (works everywhere)
- ✅ 10m resolution (excellent quality)
- ✅ 11 standardized land cover classes
- ✅ Based on Sentinel-1 and Sentinel-2 data
- ✅ Annual updates (2020, 2021, onwards)
- ✅ ~75% global accuracy

**Classes:**
1. Tree cover
2. Shrubland
3. Grassland
4. Cropland
5. Built-up
6. Bare / sparse vegetation
7. Snow and ice
8. Permanent water bodies
9. Herbaceous wetland
10. Mangroves
11. Moss and lichen

**Cons:**
- ⚠️ Only 11 classes (vs 104 in AR5)
- ⚠️ Global product (may be less accurate than national data)

**Verdict**: ✅ **Recommended** - Perfect balance of quality, license, and simplicity

### Option 3: Dynamic World (Alternative)

**Source**: Google / World Resources Institute
**Resolution**: 10 meters
**License**: ✅ **CC BY 4.0** (Free and open)
**URL**: https://www.dynamicworld.app/

**Pros:**
- ✅ Near real-time updates
- ✅ 10m resolution
- ✅ Free and open
- ✅ 9 land cover classes
- ✅ Probability layers (useful for confidence)

**Cons:**
- ⚠️ Requires Google Earth Engine access for bulk download
- ⚠️ More complex to work with
- ⚠️ Fewer classes than WorldCover

**Verdict**: ⏳ **Alternative option** if WorldCover insufficient

### Option 4: OpenStreetMap Tags (Already Available!)

**Source**: OpenStreetMap
**Resolution**: Varies (vector data)
**License**: ✅ **ODbL** (Open Database License)

**Pros:**
- ✅ Already in OSM data we're using
- ✅ No additional download needed
- ✅ Detailed tagging (natural=*, landuse=*, surface=*)
- ✅ Local knowledge from mappers
- ✅ Zero implementation effort

**Available Tags:**
- `natural=wood` - Forested areas
- `natural=scrub` - Shrubland
- `landuse=forest` - Managed forest
- `surface=*` - Trail surface type
- `smoothness=*` - Trail condition

**Cons:**
- ⚠️ Incomplete coverage (depends on mapper activity)
- ⚠️ Inconsistent tagging standards
- ⚠️ Not available for all trail areas

**Verdict**: ✅ **Use first** - Leverage existing OSM data before adding external datasets

## Recommended Approach: Hybrid Strategy

### Phase 1: OpenStreetMap Land Cover (Immediate)

**Status**: ✅ **Already available** (no implementation needed)

GraphHopper already reads OSM tags like:
- `surface=*` (paved, unpaved, gravel, dirt, grass, etc.)
- `smoothness=*` (excellent, good, intermediate, bad, etc.)
- `natural=wood` (forest areas adjacent to trails)

**Action**: Create custom routing models that use these tags.

**Implementation:**
```yaml
# In GraphHopper config
profiles:
  - name: hiking_forest
    vehicle: foot
    weighting: custom
    custom_model:
      priority:
        # Prefer forest trails (natural=wood nearby)
        - if: "road_environment == FOREST"
          multiply_by: 1.2

        # Prefer good surfaces
        - if: "surface == PAVED || surface == GRAVEL"
          multiply_by: 1.1

        # Avoid poor surfaces
        - if: "surface == DIRT && smoothness == BAD"
          multiply_by: 0.7

        # Prefer shaded paths in summer
        - if: "natural == WOOD"
          multiply_by: 1.15
```

**Effort**: 1-2 hours (configuration only)
**Benefit**: Immediate terrain-aware routing with zero additional data

### Phase 2: ESA WorldCover Integration (Future Enhancement)

**Status**: ⏳ **Future** (if OSM coverage insufficient)

Add ESA WorldCover 10m data for comprehensive land cover:

**Architecture:**
```
Pipeline Steps:
1. Fetch trails (existing)
2. Validate trails (existing)
3. *** NEW: Fetch land cover data ***
   - Calculate bounding box from trail data
   - Download WorldCover 10m tiles for area
   - Convert to GeoJSON/vector format
   - Spatial join with trails
   - Add land cover attributes to OSM output
4. Transform to OSM (modified)
   - Include land cover tags from WorldCover
   - Map WorldCover classes to OSM tags
5. Build GraphHopper graph (existing)
6. Release (existing)
```

**Mapping WorldCover to OSM:**
| WorldCover Class | OSM Tag | Custom Model Use |
|------------------|---------|------------------|
| Tree cover | natural=wood | Prefer in summer |
| Shrubland | natural=scrub | Neutral |
| Grassland | surface=grass | Slow in wet weather |
| Bare/sparse | natural=bare_rock | Avoid if difficult |
| Snow/ice | natural=glacier | Avoid in winter |

**Effort**: 3-5 days
**Benefit**: Comprehensive land cover for all Norway

### Phase 3: Custom Routing Profiles (Advanced)

Create specialized routing profiles based on land cover:

```yaml
# Summer forest hiking
hiking_forest_summer:
  priority:
    - if: "land_cover == TREE_COVER"
      multiply_by: 1.3  # Strong preference for shade

# Winter open terrain
hiking_winter:
  priority:
    - if: "land_cover == TREE_COVER && tree_density > 70"
      multiply_by: 0.5  # Avoid dense forest (avalanche risk in nearby slopes)
    - if: "land_cover == GRASSLAND || land_cover == SHRUBLAND"
      multiply_by: 1.2  # Prefer open terrain

# Scenic variety routing
hiking_scenic:
  priority:
    - if: "land_cover_diversity > 3"  # Many land cover types along route
      multiply_by: 1.4  # Prefer varied landscapes
```

## Implementation Details

### Phase 1: OSM-Based Land Cover (Recommended Start)

**No new code required** - just configuration:

1. **Update GraphHopper config** to enable custom models:
```yaml
profiles:
  - name: hiking
    vehicle: foot
    weighting: custom
    custom_model_files:
      - hiking_forest.yml
      - hiking_summer.yml
      - hiking_winter.yml
```

2. **Create custom model files** (e.g., `hiking_forest.yml`):
```yaml
priority:
  # Prefer trails through/near forests
  - if: "road_environment == FOREST"
    multiply_by: 1.2

  # Good surfaces
  - if: "surface IN [PAVED, COMPACTED, GRAVEL]"
    multiply_by: 1.1

  # Poor surfaces
  - if: "surface IN [DIRT, SAND] && smoothness IN [BAD, VERY_BAD]"
    multiply_by: 0.6

  # Avoid very steep in difficult terrain
  - if: "average_slope > 15 && surface != PAVED"
    multiply_by: 0.7
```

3. **Test with existing data** - No new downloads needed!

### Phase 2: WorldCover Integration (If Needed)

#### Step 1: Download WorldCover Tiles

```python
import requests
from pathlib import Path

def download_worldcover_tile(
    tile_name: str,  # e.g., "N60E005"
    output_dir: Path,
    version: str = "v200"  # 2021 version
) -> Path:
    """Download ESA WorldCover 10m tile.

    Tiles are 3°x3° GeoTIFF files.
    """
    base_url = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/{version}/map/"
    url = f"{base_url}{tile_name}_Map.tif"

    output_file = output_dir / f"{tile_name}_WorldCover.tif"

    if output_file.exists():
        print(f"Tile {tile_name} already cached")
        return output_file

    print(f"Downloading WorldCover tile: {tile_name}")
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()

    with open(output_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_file
```

#### Step 2: Extract Land Cover for Trails

```python
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import box

def extract_land_cover_for_trails(
    trails_gdf: gpd.GeoDataFrame,
    worldcover_tif: Path,
    buffer_meters: int = 50  # Sample land cover within 50m of trail
) -> gpd.GeoDataFrame:
    """Extract dominant land cover type for each trail segment."""

    with rasterio.open(worldcover_tif) as src:
        # Buffer trails to sample nearby land cover
        trails_buffered = trails_gdf.copy()
        trails_buffered["geometry"] = trails_buffered.geometry.buffer(buffer_meters)

        land_cover_values = []

        for idx, trail in trails_buffered.iterrows():
            try:
                # Mask raster to trail buffer
                out_image, out_transform = mask(src, [trail.geometry], crop=True)

                # Get most common land cover value
                unique, counts = np.unique(out_image, return_counts=True)
                dominant_class = unique[counts.argmax()]

                land_cover_values.append(dominant_class)
            except Exception as e:
                print(f"Error processing trail {idx}: {e}")
                land_cover_values.append(0)  # Unknown

        trails_gdf["land_cover"] = land_cover_values
        return trails_gdf
```

#### Step 3: Map to OSM Tags

```python
# WorldCover class mapping
WORLDCOVER_TO_OSM = {
    10: {"natural": "wood", "description": "Tree cover"},
    20: {"natural": "scrub", "description": "Shrubland"},
    30: {"surface": "grass", "description": "Grassland"},
    40: {"landuse": "farmland", "description": "Cropland"},
    50: {"landuse": "residential", "description": "Built-up"},
    60: {"natural": "bare_rock", "description": "Bare / sparse vegetation"},
    70: {"natural": "glacier", "description": "Snow and ice"},
    80: {"natural": "water", "description": "Permanent water bodies"},
    90: {"natural": "wetland", "description": "Herbaceous wetland"},
    95: {"natural": "wetland", "wetland": "mangrove", "description": "Mangroves"},
    100: {"natural": "heath", "description": "Moss and lichen"},
}

def add_worldcover_tags_to_osm(trails_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add WorldCover-derived tags to trail data."""

    for idx, trail in trails_gdf.iterrows():
        land_cover_class = trail.get("land_cover", 0)

        if land_cover_class in WORLDCOVER_TO_OSM:
            tags = WORLDCOVER_TO_OSM[land_cover_class]
            for key, value in tags.items():
                if key != "description":
                    trails_gdf.at[idx, f"land_cover_{key}"] = value

    return trails_gdf
```

## File Size and Feasibility

### WorldCover Tile Sizes

| Coverage | Tiles Needed | Size per Tile | Total Size |
|----------|--------------|---------------|------------|
| Norway (bounding box) | ~15-20 tiles | ~100-200 MB | **~2-3 GB** |
| Trail area only (buffered) | ~10-15 tiles | ~100-200 MB | **~1-2 GB** |

### GitHub Actions Feasibility

**Available disk space**: ~25-29 GB
**With WorldCover (~2GB)**: ✅ **Feasible** (8-10% of available space)

**Comparison:**
- DTM10: 20 GB (not feasible)
- WorldCover: 2-3 GB (✅ feasible)
- SRTM: 500 MB (✅ feasible)

### GitHub Release Feasibility

WorldCover data would not be included in releases (too large).
Only the processed land cover attributes added to trails would be released.

## Custom Routing Model Examples

### Example 1: Forest Preference (Summer)

```yaml
# hiking_forest_summer.yml
priority:
  # Strong preference for shaded forest trails
  - if: "land_cover == TREE_COVER || natural == WOOD"
    multiply_by: 1.3

  # Avoid exposed open terrain in hot weather
  - if: "land_cover == GRASSLAND && elevation < 800"
    multiply_by: 0.8

  # Prefer good trail conditions
  - if: "surface IN [PAVED, GRAVEL] && smoothness IN [EXCELLENT, GOOD]"
    multiply_by: 1.2
```

### Example 2: Open Terrain (Winter Safety)

```yaml
# hiking_winter_safe.yml
priority:
  # Avoid dense forest near steep slopes (avalanche terrain)
  - if: "land_cover == TREE_COVER && average_slope > 25"
    multiply_by: 0.4

  # Prefer open terrain below treeline
  - if: "land_cover IN [GRASSLAND, SHRUBLAND] && elevation < 1200"
    multiply_by: 1.3

  # Avoid glacier/snow areas in winter
  - if: "land_cover == SNOW_ICE || natural == GLACIER"
    multiply_by: 0.3
```

### Example 3: Scenic Variety

```yaml
# hiking_scenic.yml
priority:
  # Calculate variety by checking surrounding land cover
  # (requires custom implementation)

  # Prefer routes through mixed terrain
  - if: "land_cover_diversity > 3"  # 3+ different types along route
    multiply_by: 1.4

  # Bonus for water views
  - if: "land_cover == WATER || natural == WATER"
    multiply_by: 1.2
```

## Testing Strategy

### Phase 1 Testing (OSM-based)

1. **Verify custom model loading**
   - Test GraphHopper starts with custom models
   - Verify profiles accessible via API

2. **Routing tests**
   - Compare routes with/without land cover preferences
   - Verify forest trails preferred when configured

3. **Performance tests**
   - Measure routing time with custom models
   - Should be <5% overhead

### Phase 2 Testing (WorldCover)

1. **Data download tests**
   - Test tile download for Norway
   - Verify GeoTIFF format correct

2. **Land cover extraction tests**
   - Test raster sampling for trails
   - Verify classification accuracy

3. **Integration tests**
   - End-to-end: WorldCover → OSM tags → GraphHopper
   - Verify tags present in graph

## Recommendations

### Immediate Action: Phase 1 (OSM-Based)

**Implementation time**: 1-2 hours
**Effort**: Configuration only
**Benefits**:
- ✅ Terrain-aware routing with existing data
- ✅ Zero additional downloads
- ✅ Works within GitHub Actions
- ✅ Multiple routing profiles (summer, winter, scenic)

**Action items**:
1. Create custom model YAML files
2. Update GraphHopper config to load models
3. Test routing with different profiles
4. Document usage in README

### Future Enhancement: Phase 2 (WorldCover)

**Implementation time**: 3-5 days
**When to implement**: If user feedback indicates OSM coverage insufficient
**Benefits**:
- ✅ Comprehensive land cover for all Norway
- ✅ Consistent global data
- ✅ Better than sparse OSM tagging

**Blockers**:
- Need user feedback on OSM-based routing first
- Requires 2-3 GB download (but feasible in GitHub Actions)

## Next Steps

1. ✅ Research completed
2. ✅ Design documented
3. ⏭️ Implement Phase 1 (OSM-based custom models)
4. ⏭️ Test with sample trails
5. ⏭️ Document custom routing profiles
6. ⏭️ (Optional) Implement Phase 2 if needed

## References

- [ESA WorldCover](https://worldcover2021.esa.int/)
- [Dynamic World](https://www.dynamicworld.app/)
- [GraphHopper Custom Models](https://github.com/graphhopper/graphhopper/blob/master/docs/core/custom-models.md)
- [OpenStreetMap Land Cover Tagging](https://wiki.openstreetmap.org/wiki/Landcover)
- [OSM Natural Tags](https://wiki.openstreetmap.org/wiki/Key:natural)

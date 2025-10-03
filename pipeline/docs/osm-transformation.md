# OSM Transformation Requirements

This document describes the complex transformation from Turrutebasen data to OSM format for GraphHopper.

## Overview

The transformation step must convert Norwegian trail data (Turrutebasen from Geonorge) into OSM PBF format that GraphHopper can consume for routing.

## High-Level Steps

1. **Join Data**: Merge spatial geometries with attribute table
2. **Map Attributes**: Convert Turrutebasen fields to OSM tags
3. **Infer Missing Data**: Use inference rules for incomplete attributes
4. **Generate OSM XML**: Create valid OSM XML structure
5. **Convert to PBF**: Use osmium/osmconvert to create binary format

## Data Structure

### Input
- **Spatial Layer**: GeoDataFrame with trail geometries (LineStrings in EPSG:4326)
  - `local_id`: Unique identifier per segment
  - `geometry`: Trail linestring
  - Basic attributes (marking, signage, lighting, etc.)

- **Attribute Table**: DataFrame with trail metadata
  - `hiking_trail_fk`: Foreign key to spatial layer
  - Rich attributes (trail_name, trail_number, difficulty, etc.)
  - **Note**: Many-to-one relationship (multiple rows per geometry)

### Output
- **OSM PBF File**: Binary format with:
  - Nodes: Points along trail paths
  - Ways: Trail segments with tags
  - Relations: (Optional) For trail networks

## Attribute Mapping

See `pipeline/config/countries/norway.toml` for complete mapping rules.

### Essential Mappings (Tier 1 - High Completeness)

| Turrutebasen | Completeness | OSM Tag | Example |
|--------------|--------------|---------|---------|
| objtype | 100% | highway | footway, path |
| rutefolger | 94% | highway refinement | path, track |
| merking | 100% | trail_marking | yes, no |
| rutenavn | 95.4% | name | "Pilegrimsleden" |
| rutenummer | 100% | ref | "1" |

### Recommended Mappings (Tier 2 - With Inference)

| Turrutebasen | Completeness | OSM Tag | Inference |
|--------------|--------------|---------|-----------|
| gradering | 36.2% | sac_scale | Infer from rutefolger |
| rutebetydning | 29.5% | importance | Local/regional/national |
| vedlikeholdsansvarlig | 57.2% | operator | DNT, Kommune, etc. |

### Optional Mappings (Tier 3)

| Turrutebasen | Completeness | OSM Tag | Notes |
|--------------|--------------|---------|-------|
| rutetype | 3.5% | trail_type | Very sparse |
| sesong | 100% | seasonal | Summer/winter |
| belysning | 100% | lit | yes/no |
| trafikkbelastning | 13.4% | trail_visibility | Good/poor |

## Inference Rules

### Difficulty (gradering → sac_scale)

Based on rutefolger (trail type):
- `ST` (Sti/Path) → `hiking` (T1: Easy)
- `TI` (Tilrettelagt/Adapted) → `hiking` (T1: Easy, well-maintained)
- `VE` (Veg/Road) → `mountain_hiking` (T2: Moderate)
- `LE` (Leden/Cairned) → `demanding_mountain_hiking` (T3: Challenging)

Reference: [SAC Scale](https://wiki.openstreetmap.org/wiki/Key:sac_scale)

### Surface Type (rutefolger → surface)

- `ST` → `ground` (natural path)
- `TI` → `paved` or `compacted` (adapted trail)
- `VE` → `unpaved` (road/track)
- `LE` → `rock` (cairned route)

## OSM Structure

### Node Generation

OSM requires nodes (points) that make up ways (lines). We need to:

1. Extract all unique coordinate pairs from LineString geometries
2. Assign sequential OSM node IDs
3. Track coordinate → node_id mapping to avoid duplicates

```xml
<node id="1" lat="59.9139" lon="10.7522"/>
<node id="2" lat="59.9150" lon="10.7530"/>
```

### Way Generation

Each trail segment becomes an OSM way:

```xml
<way id="1000" version="1">
  <nd ref="1"/>
  <nd ref="2"/>
  <nd ref="3"/>
  <tag k="highway" v="path"/>
  <tag k="name" v="Pilegrimsleden"/>
  <tag k="ref" v="1"/>
  <tag k="sac_scale" v="hiking"/>
  <tag k="trail_marking" v="yes"/>
  <tag k="operator" v="DNT"/>
  <tag k="source" v="Kartverket Turrutebasen"/>
  <tag k="ref:geonorge" v="unique-id-here"/>
</way>
```

## Many-to-One Relationship Challenge

**Problem**: Trail segments can belong to multiple named trails.

**Example**: A single segment might be part of:
- "Pilegrimsleden" (national trail)
- "Gudbrandsdalsleden" (regional trail)
- "Topptur til Besseggen" (local trail)

**Solutions**:

### Option 1: Create Multiple Ways (Recommended)
- Create one OSM way per (geometry, trail_name) combination
- Pros: Preserves all trail names
- Cons: Duplicates geometry, larger file size
- GraphHopper handles this well (routing works on combined network)

### Option 2: Concatenate Names
- Single way with `name="Trail A; Trail B; Trail C"`
- Pros: Smaller file, no duplication
- Cons: Loses individual trail metadata, harder to query

### Option 3: OSM Relations
- Create route relations for named trails
- Pros: Proper OSM structure, preserves relationships
- Cons: More complex, larger file, GraphHopper may not use relations

**Recommendation**: Use Option 1 for MVP (multiple ways), consider Option 3 for future enhancement.

## Implementation Steps

### Step 1: Join Data
```python
# Join spatial and attribute data
joined = spatial_gdf.merge(
    attributes_df,
    left_on="local_id",
    right_on="hiking_trail_fk",
    how="inner"
)
# Result: Multiple rows per geometry (one per trail name)
```

### Step 2: Apply Mapping
```python
def map_to_osm_tags(row, config):
    tags = {}

    # Direct mappings
    tags["highway"] = map_objtype(row["objtype"])
    tags["name"] = row["trail_name"]
    tags["ref"] = row["trail_number"]

    # Inference
    if pd.isna(row["difficulty"]):
        tags["sac_scale"] = infer_difficulty(row["rutefolger"])
    else:
        tags["sac_scale"] = map_difficulty(row["difficulty"])

    return tags
```

### Step 3: Generate OSM XML
```python
def generate_osm_xml(joined_gdf, output_path):
    # Create root element
    root = ET.Element("osm", version="0.6")

    # Track nodes
    node_id = 1
    coord_to_node = {}

    # Generate nodes from geometries
    for idx, row in joined_gdf.iterrows():
        geom = row.geometry
        for coord in geom.coords:
            if coord not in coord_to_node:
                node = ET.SubElement(root, "node",
                    id=str(node_id),
                    lat=str(coord[1]),
                    lon=str(coord[0])
                )
                coord_to_node[coord] = node_id
                node_id += 1

    # Generate ways
    way_id = 1000000
    for idx, row in joined_gdf.iterrows():
        way = ET.SubElement(root, "way", id=str(way_id))

        # Add node references
        for coord in row.geometry.coords:
            nd = ET.SubElement(way, "nd", ref=str(coord_to_node[coord]))

        # Add tags
        tags = map_to_osm_tags(row)
        for k, v in tags.items():
            ET.SubElement(way, "tag", k=k, v=v)

        way_id += 1

    # Write XML
    tree = ET.ElementTree(root)
    tree.write(output_path)
```

### Step 4: Convert to PBF
```bash
# Use osmium (preferred) or osmconvert
osmium cat trails.osm.xml -o trails.osm.pbf
```

## Tools & Libraries

### Python Libraries
- `geopandas` - Spatial data manipulation ✅ (already used)
- `pandas` - Data manipulation ✅ (already used)
- `lxml` - XML generation (add to dependencies)
- `shapely` - Geometry operations ✅ (via geopandas)

### Command-Line Tools
- **osmium-tool** (recommended)
  - Fast, reliable, well-maintained
  - Install: `apt install osmium-tool` or `brew install osmium-tool`

- **osmconvert** (alternative)
  - Part of osmctools
  - Simpler but less features

## Testing Strategy

### Unit Tests
- Test attribute mapping functions
- Test inference rules
- Test OSM tag generation

### Integration Tests
- Generate OSM XML from sample data
- Validate OSM XML structure
- Convert to PBF and verify

### End-to-End Tests
- Process full Turrutebasen dataset
- Load into GraphHopper
- Test routing queries

## Performance Considerations

### Data Volume
- Norway: ~134,000 trail segments
- With duplicates for multiple names: ~163,000 ways
- Estimated nodes: ~1-2 million
- File size: ~50-100 MB (PBF compressed)

### Optimization
- Use efficient XML writing (streaming if needed)
- Pre-allocate node IDs
- Batch processing for large datasets
- Consider parallel processing for segments

## Future Enhancements

1. **Relations**: Create OSM relations for trail networks
2. **Multi-country**: Support Sweden, Denmark, etc.
3. **Elevation**: Integrate DTM data into ways
4. **Land Cover**: Use AR5 for surface type inference
5. **Incremental Updates**: Only rebuild changed trails

## References

- [OSM XML Format](https://wiki.openstreetmap.org/wiki/OSM_XML)
- [OSM Tags for Hiking](https://wiki.openstreetmap.org/wiki/Hiking)
- [SAC Scale](https://wiki.openstreetmap.org/wiki/Key:sac_scale)
- [GraphHopper OSM Import](https://github.com/graphhopper/graphhopper/blob/master/docs/core/quickstart-from-source.md)
- [osmium Tool](https://osmcode.org/osmium-tool/)

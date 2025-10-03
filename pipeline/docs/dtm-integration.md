# DTM (Elevation Data) Integration Design

## Overview

This document describes the integration of Norwegian DTM (Digital Terrain Model) elevation data into the GraphHopper routing pipeline. Adding elevation data enables more accurate routing with realistic elevation profiles, slope calculations, and distance adjustments.

## Data Sources

### Primary: Kartverket Høydedata

**Source**: https://hoydedata.no/
**Provider**: Kartverket (Norwegian Mapping Authority)
**License**: CC BY 4.0 (Free to use with attribution)

**Available Resolutions:**
- **DTM1**: 1-meter resolution (high precision, large file sizes)
- **DTM10**: 10-meter resolution (good balance, nationwide coverage)
- **DTM50**: 50-meter resolution (lower precision, smaller files)

**API Access:**
- REST API: https://hoydedata.no/arcgis/rest/services/DTM/ImageServer
- Format: GeoTIFF, USGS DEM
- CRS: EPSG:25833 (EUREF89 UTM Zone 33N)
- Coverage: All of Norway

### Fallback: SRTM (Shuttle Radar Topography Mission)

**Source**: Global coverage
**Resolution**: ~30 meters (1 arc-second)
**License**: Public domain
**Access**: Automatic download via GraphHopper

## Integration Strategy

### Approach: Hybrid Model

Use both Norwegian DTM (primary) and SRTM (fallback):

1. **DTM10 for Norway**: High-quality 10m resolution for Norwegian trails
2. **SRTM for borders**: Automatic fallback for areas outside DTM coverage
3. **Pre-processing**: Download and prepare DTM tiles covering trail areas
4. **GraphHopper integration**: Configure to use local DTM first, SRTM as fallback

### Why Hybrid?

- **Quality**: DTM10 (10m) is higher resolution than SRTM (30m)
- **Coverage**: Some trails may cross into Sweden/Finland
- **Reliability**: SRTM provides consistent global fallback
- **Simplicity**: GraphHopper already supports SRTM out-of-the-box

## Implementation Design

### Architecture

```
Pipeline Steps:
1. Fetch trails (existing)
2. Validate trails (existing)
3. *** NEW: Fetch DTM data ***
   - Calculate bounding box from trail data
   - Download DTM tiles from Høydedata API
   - Convert to GraphHopper-compatible format
   - Store in cache directory
4. Transform to OSM (existing)
5. Build GraphHopper graph (modified)
   - Configure elevation provider
   - Point to cached DTM data
   - Enable slope/elevation features
6. Release (existing)
```

### New Component: DTM Fetch Step

```python
class FetchDTMStep(PipelineStep[gpd.GeoDataFrame, Path]):
    """Fetch DTM elevation data for trail area.

    Downloads Norwegian DTM10 data from Høydedata API,
    covering the bounding box of all trails with a buffer.
    """

    def execute(self, context, trail_gdf):
        # 1. Calculate bounding box from trails
        bounds = calculate_buffered_bounds(trail_gdf, buffer_km=5)

        # 2. Download DTM tiles
        dtm_files = download_dtm_tiles(bounds, resolution="DTM10")

        # 3. Merge and convert to GeoTIFF
        merged_dtm = merge_dtm_tiles(dtm_files)

        # 4. Convert CRS if needed (EPSG:25833 -> EPSG:4326)
        output_dtm = convert_dtm_to_wgs84(merged_dtm)

        # 5. Cache for GraphHopper
        cached_path = cache_dtm(output_dtm, context.cache_dir)

        return StepResult(output=cached_path, ...)
```

### Modified Component: Build Step

Update `BuildGraphHopperStep` to configure elevation:

```python
def _generate_config_with_elevation(
    self,
    dtm_path: Path | None,
    ...
) -> Path:
    """Generate GraphHopper config with elevation enabled."""

    config = {
        "graphhopper": {
            # ... existing config ...

            # Elevation configuration
            "graph.elevation.provider": "multi",  # Try custom first, SRTM fallback
            "graph.elevation.cache_dir": str(cache_dir / "elevation"),
            "graph.elevation.base_url": dtm_path if dtm_path else None,
            "graph.elevation.interpolate": "bilinear",
            "graph.elevation.edge_smoothing": "ramer",
        }
    }
```

## DTM Data Format

### Høydedata API Request

```http
GET https://hoydedata.no/arcgis/rest/services/DTM/ImageServer/exportImage
Parameters:
  - bbox: <minx>,<miny>,<maxx>,<maxy>
  - bboxSR: 25833  (EPSG:25833)
  - size: <width>,<height>
  - imageSR: 25833
  - format: tiff
  - f: image
  - pixelType: F32  (32-bit float)
```

### Response

- **Format**: GeoTIFF
- **Pixel Type**: Float32 (elevation in meters)
- **CRS**: EPSG:25833 (UTM Zone 33N)
- **NoData Value**: -9999 or similar

### Conversion for GraphHopper

GraphHopper expects:
- **CRS**: EPSG:4326 (WGS84 lat/lon) preferred
- **Format**: GeoTIFF or similar raster format
- **File naming**: `N<lat>E<lon>.tif` or similar tile structure

## Implementation Details

### 1. Bounding Box Calculation

```python
def calculate_buffered_bounds(
    gdf: gpd.GeoDataFrame,
    buffer_km: float = 5.0
) -> tuple[float, float, float, float]:
    """Calculate bounding box with buffer.

    Args:
        gdf: GeoDataFrame with trail geometries
        buffer_km: Buffer distance in kilometers

    Returns:
        (minx, miny, maxx, maxy) in EPSG:25833
    """
    # Get bounds in CRS of data (EPSG:25833)
    bounds = gdf.total_bounds

    # Add buffer (km to meters)
    buffer_m = buffer_km * 1000
    buffered = (
        bounds[0] - buffer_m,  # minx
        bounds[1] - buffer_m,  # miny
        bounds[2] + buffer_m,  # maxx
        bounds[3] + buffer_m,  # maxy
    )

    return buffered
```

### 2. DTM Download

```python
import requests
from pathlib import Path

def download_dtm_tile(
    bounds: tuple[float, float, float, float],
    output_path: Path,
    resolution: int = 10  # meters per pixel
) -> Path:
    """Download DTM tile from Høydedata API.

    Args:
        bounds: (minx, miny, maxx, maxy) in EPSG:25833
        output_path: Where to save GeoTIFF
        resolution: Desired resolution in meters

    Returns:
        Path to downloaded GeoTIFF
    """
    minx, miny, maxx, maxy = bounds

    # Calculate image size based on desired resolution
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)

    # Høydedata API endpoint
    url = "https://hoydedata.no/arcgis/rest/services/DTM/ImageServer/exportImage"

    params = {
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": "25833",
        "size": f"{width},{height}",
        "imageSR": "25833",
        "format": "tiff",
        "pixelType": "F32",
        "f": "image",
    }

    response = requests.get(url, params=params, stream=True, timeout=300)
    response.raise_for_status()

    # Save to file
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path
```

### 3. CRS Conversion

```python
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

def convert_dtm_to_wgs84(
    input_tif: Path,
    output_tif: Path
) -> Path:
    """Convert DTM from EPSG:25833 to EPSG:4326.

    Args:
        input_tif: Input GeoTIFF in EPSG:25833
        output_tif: Output GeoTIFF in EPSG:4326

    Returns:
        Path to converted GeoTIFF
    """
    with rasterio.open(input_tif) as src:
        # Calculate transform and dimensions for EPSG:4326
        transform, width, height = calculate_default_transform(
            src.crs,
            "EPSG:4326",
            src.width,
            src.height,
            *src.bounds
        )

        # Output metadata
        kwargs = src.meta.copy()
        kwargs.update({
            "crs": "EPSG:4326",
            "transform": transform,
            "width": width,
            "height": height
        })

        # Reproject
        with rasterio.open(output_tif, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:4326",
                    resampling=Resampling.bilinear
                )

    return output_tif
```

### 4. GraphHopper Configuration

Update build step configuration:

```yaml
graphhopper:
  # ... existing config ...

  # Elevation configuration
  graph.elevation.provider: srtm  # Start with SRTM for simplicity
  graph.elevation.cache_dir: .cache/elevation
  graph.elevation.interpolate: bilinear
  graph.elevation.edge_smoothing: ramer

  # Future: Custom provider for DTM
  # graph.elevation.provider: multi
  # graph.elevation.custom_dtm_dir: .cache/dtm
```

## Testing Strategy

### Unit Tests

1. **Bounding box calculation**
   - Test with sample trail data
   - Verify buffer application
   - Check CRS handling

2. **DTM download**
   - Mock Høydedata API
   - Test error handling
   - Verify file format

3. **CRS conversion**
   - Test EPSG:25833 -> EPSG:4326
   - Verify elevation values preserved
   - Check raster dimensions

4. **GraphHopper integration**
   - Test configuration generation
   - Verify elevation provider setup
   - Mock graph building

### Integration Tests

1. **End-to-end DTM fetch**
   - Download small test area
   - Verify GeoTIFF created
   - Check elevation values reasonable

2. **GraphHopper with DTM**
   - Build graph with elevation
   - Verify slope calculations
   - Test routing with elevation

## Performance Considerations

### DTM File Sizes

For Norway (bounding box ~1000km x 2000km):
- **DTM1 (1m)**: ~2 TB (too large)
- **DTM10 (10m)**: ~20 GB (manageable)
- **DTM50 (50m)**: ~800 MB (small)

**Recommendation**: Use DTM10 (10m) for balance of quality and size.

### Download Time

- **DTM10 for all Norway**: ~2-6 hours (depending on connection)
- **DTM10 for trail bbox only**: ~10-30 minutes
- **Optimization**: Cache downloaded tiles, reuse between builds

### Memory Usage

- **Loading full DTM**: ~20 GB RAM (infeasible)
- **Tiled approach**: <1 GB RAM per tile
- **GraphHopper**: Caches elevation in graph structure (~5-10% overhead)

### Optimization Strategies

1. **Spatial tiling**: Download only tiles covering trails
2. **Caching**: Store downloaded DTM, reuse if bounds unchanged
3. **Compression**: Use LZW or DEFLATE compression in GeoTIFF
4. **Resolution**: Use DTM10 (not DTM1) for reasonable file sizes

## Implementation Phases

### Phase 1: SRTM Integration (Quick Win)

**Effort**: 1-2 hours
**Benefit**: Global elevation coverage, low effort

Simply enable SRTM in GraphHopper config:

```yaml
graph.elevation.provider: srtm
graph.elevation.cache_dir: .cache/elevation
```

This provides:
- ✅ Automatic elevation for all of Norway (~30m resolution)
- ✅ No additional code needed
- ✅ Works globally (not just Norway)
- ❌ Lower resolution than DTM10 (30m vs 10m)

### Phase 2: DTM Fetch Step (Better Quality)

**Effort**: 1-2 days
**Benefit**: Higher resolution (10m), better accuracy

Implement FetchDTMStep:
- Download DTM10 from Høydedata
- Convert to GeoTIFF
- Cache locally
- Configure GraphHopper to use custom DTM

This provides:
- ✅ 10m resolution (3x better than SRTM)
- ✅ Higher quality elevation data
- ✅ Cached for reuse
- ❌ Requires implementation effort
- ❌ Norway-specific (needs fallback)

### Phase 3: Hybrid Provider (Best of Both)

**Effort**: 2-3 days
**Benefit**: DTM quality for Norway, SRTM fallback elsewhere

Implement custom elevation provider:
- Try DTM first (if available)
- Fall back to SRTM
- Seamless boundary handling

This provides:
- ✅ Best quality where available
- ✅ Global coverage
- ✅ Automatic fallback
- ❌ Most complex to implement

## Recommendation

**Start with Phase 1 (SRTM)** for immediate elevation support, then implement Phase 2 (DTM) for better quality if needed.

SRTM provides:
- Good enough resolution for most routing needs
- Zero implementation effort
- Reliable global coverage
- Proven integration with GraphHopper

DTM10 can be added later if higher resolution is required for:
- Technical hiking trails
- Steep terrain analysis
- Precise elevation profiles

## Dependencies

### New Python Packages

```toml
[project]
dependencies = [
    # ... existing ...
    "rasterio>=1.3.0",      # GeoTIFF manipulation
    "requests>=2.31.0",     # Already added for build step
]
```

### System Requirements

- **rasterio** requires GDAL
- Install on Fedora: `sudo dnf install gdal gdal-devel`
- Install on Ubuntu: `sudo apt-get install libgdal-dev`

## References

- [Kartverket Høydedata](https://www.kartverket.no/api-og-data/terrengdata)
- [Høydedata API](https://hoydedata.no/arcgis/rest/services/DTM/ImageServer)
- [GraphHopper Elevation Docs](https://github.com/graphhopper/graphhopper/blob/master/docs/core/elevation.md)
- [SRTM Data](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission-srtm-1)
- [Rasterio Documentation](https://rasterio.readthedocs.io/)

## Next Steps

1. ✅ Research completed
2. ✅ Design documented
3. ⏭️ Implement Phase 1 (SRTM integration)
4. ⏭️ Test with sample trail data
5. ⏭️ Update pipeline documentation
6. ⏭️ (Optional) Implement Phase 2 (DTM fetch step)

# GraphHopper Build Step Design

## Overview

The GraphHopper build step takes the generated OSM file and creates a routing graph that can be used for trail routing. This step integrates with GraphHopper's command-line tools to build an optimized graph structure.

## Requirements

### Input
- OSM XML or PBF file from transform step (`trails.osm.pbf` or `trails.osm.xml`)
- GraphHopper configuration (from `config/pipeline.toml`)
- Country-specific routing profiles (from `config/countries/*.toml`)

### Output
- GraphHopper graph directory (`graphhopper-data/`)
- Routing configuration file (`graphhopper-config.yml`)
- Build metadata (nodes, ways, graph size, build time)

### Dependencies
- GraphHopper Java library (via Maven/direct JAR download)
- Java Runtime Environment (JRE 11+)
- Sufficient memory for graph building (~2-4GB for Norway)

## Implementation Options

### Option 1: Direct JAR Execution (Recommended for MVP)

**Pros:**
- Simple to implement
- No Java code required
- Uses stable GraphHopper CLI
- Easy to debug

**Cons:**
- Requires GraphHopper JAR download
- Less control over build process
- Harder to customize

**Implementation:**
```python
import subprocess
from pathlib import Path

def build_graphhopper_graph(
    osm_file: Path,
    graph_dir: Path,
    config_file: Path,
    graphhopper_jar: Path
) -> BuildResult:
    """Build GraphHopper graph using CLI."""

    cmd = [
        "java",
        "-Xmx4g",  # 4GB heap
        "-jar", str(graphhopper_jar),
        "import",
        str(osm_file),
        "--config", str(config_file)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600  # 1 hour timeout
    )

    if result.returncode != 0:
        raise BuildError(f"GraphHopper build failed: {result.stderr}")

    return parse_build_output(result.stdout)
```

### Option 2: Python Library Integration

**Pros:**
- Better integration with pipeline
- More control over build process
- Can add custom processors

**Cons:**
- Requires Java-Python bridge (py4j)
- More complex setup
- Potential version compatibility issues

**Note:** Defer to post-MVP - not needed for initial implementation.

## GraphHopper Configuration

### Generate Configuration File

```yaml
# graphhopper-config.yml (generated from pipeline config)
graphhopper:
  datareader.file: trails.osm.pbf
  graph.location: graphhopper-data

  # Routing profiles from config
  profiles:
    - name: hiking
      vehicle: foot
      weighting: shortest

  # Encoded values for Norwegian trails
  graph.encoded_values: |
    car_access, bike_access, foot_access,
    sac_scale, trail_visibility, operator,
    surface, width, smoothness

  # Elevation provider
  graph.elevation.provider: srtm
  graph.elevation.cache_dir: .cache/elevation

  # Import settings
  import.osm.ignored_highways: |
    motorway, motorway_link,
    trunk, trunk_link,
    primary, primary_link

  # Snap to closest trail (not road)
  routing.snap_max_distance: 500
```

### Profile Configuration

Norwegian hiking profiles should consider:
- **sac_scale**: Difficulty rating (T1-T6)
- **trail_visibility**: How well marked
- **surface**: Ground, rock, paved, etc.
- **operator**: DNT, Kommune, etc.

```yaml
# profiles/hiking.yml (custom weighting)
priority:
  - if: sac_scale > T3
    multiply_by: 0.5  # Prefer easier trails

  - if: trail_visibility == excellent
    multiply_by: 1.2  # Prefer well-marked

  - if: operator == DNT
    multiply_by: 1.1  # Slight DNT preference

  - if: surface == rock
    multiply_by: 0.8  # Avoid rocky sections
```

## Build Step Implementation

### Step Class Structure

```python
from datetime import datetime
from pathlib import Path
from trails.pipeline import PipelineStep, PipelineContext, StepResult, StepStatus

class BuildGraphHopperStep(PipelineStep[Path, Path]):
    """Build GraphHopper routing graph from OSM data."""

    def __init__(
        self,
        country_code: str = "NO",
        graphhopper_version: str = "8.0"
    ) -> None:
        self.country_code = country_code
        self.graphhopper_version = graphhopper_version

    @property
    def name(self) -> str:
        return f"build-graph-{self.country_code.lower()}"

    @property
    def description(self) -> str:
        return f"Build GraphHopper routing graph for {self.country_code}"

    def execute(
        self,
        context: PipelineContext,
        input_data: Path
    ) -> StepResult[Path]:
        """Execute GraphHopper build."""

        started_at = datetime.now()

        # 1. Setup directories
        graph_dir = context.work_dir / "graphhopper-data"
        graph_dir.mkdir(parents=True, exist_ok=True)

        # 2. Download GraphHopper if needed
        graphhopper_jar = self._ensure_graphhopper_jar(context)

        # 3. Generate configuration
        config_file = self._generate_config(context, input_data, graph_dir)

        # 4. Build graph
        try:
            build_stats = self._build_graph(
                graphhopper_jar,
                input_data,
                config_file,
                context.dry_run
            )
        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Graph build failed: {str(e)}",
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now()
            )

        # 5. Validate graph
        if not self._validate_graph(graph_dir):
            return StepResult(
                status=StepStatus.FAILED,
                error="Graph validation failed",
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now()
            )

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return StepResult(
            status=StepStatus.SUCCESS,
            output=graph_dir,
            metadata={
                "graph_size_mb": self._get_dir_size_mb(graph_dir),
                "node_count": build_stats.get("nodes", 0),
                "edge_count": build_stats.get("edges", 0),
                "build_time_seconds": duration,
                "graphhopper_version": self.graphhopper_version,
            },
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at
        )

    def _ensure_graphhopper_jar(self, context: PipelineContext) -> Path:
        """Download GraphHopper JAR if not cached."""
        jar_path = context.cache_dir / f"graphhopper-{self.graphhopper_version}.jar"

        if jar_path.exists():
            return jar_path

        # Download from Maven Central
        url = (
            f"https://repo1.maven.org/maven2/com/graphhopper/"
            f"graphhopper-web/{self.graphhopper_version}/"
            f"graphhopper-web-{self.graphhopper_version}.jar"
        )

        # TODO: Implement download with progress
        # download_file(url, jar_path)

        return jar_path

    def _generate_config(
        self,
        context: PipelineContext,
        osm_file: Path,
        graph_dir: Path
    ) -> Path:
        """Generate GraphHopper configuration file."""
        pipeline_config = context.config.get("pipeline", {})
        gh_config = pipeline_config.graphhopper

        config_content = f"""
graphhopper:
  datareader.file: {osm_file}
  graph.location: {graph_dir}

  profiles:
"""
        for profile in gh_config.profiles:
            config_content += f"""    - name: {profile}
      vehicle: foot
      weighting: shortest
"""

        config_content += f"""
  graph.encoded_values: |
    foot_access, sac_scale, trail_visibility,
    operator, surface, smoothness

  graph.elevation.provider: srtm
  graph.elevation.cache_dir: {context.cache_dir / 'elevation'}
"""

        config_file = context.work_dir / "graphhopper-config.yml"
        config_file.write_text(config_content)

        return config_file

    def _build_graph(
        self,
        jar_path: Path,
        osm_file: Path,
        config_file: Path,
        dry_run: bool
    ) -> dict:
        """Execute GraphHopper build command."""
        if dry_run:
            return {"nodes": 0, "edges": 0, "note": "dry-run"}

        cmd = [
            "java",
            "-Xmx4g",
            "-jar", str(jar_path),
            "import",
            str(osm_file),
            "--config", str(config_file)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )

        if result.returncode != 0:
            raise RuntimeError(f"Build failed: {result.stderr}")

        # Parse output for statistics
        return self._parse_build_output(result.stdout)

    def _parse_build_output(self, output: str) -> dict:
        """Parse GraphHopper build output for statistics."""
        stats = {}

        # Look for patterns like:
        # "graph ... nodes=134047, edges=163558"
        # "took 45.2s"

        import re

        if match := re.search(r'nodes[=\s]+(\d+)', output):
            stats["nodes"] = int(match.group(1))

        if match := re.search(r'edges[=\s]+(\d+)', output):
            stats["edges"] = int(match.group(1))

        if match := re.search(r'took\s+([\d.]+)s', output):
            stats["import_time"] = float(match.group(1))

        return stats

    def _validate_graph(self, graph_dir: Path) -> bool:
        """Validate that graph was built successfully."""
        # Check for required files
        required_files = [
            "nodes",
            "edges",
            "location_index",
            "properties"
        ]

        for file in required_files:
            if not (graph_dir / file).exists():
                return False

        # Check minimum size (should be > 1MB for Norway)
        if self._get_dir_size_mb(graph_dir) < 1:
            return False

        return True

    def _get_dir_size_mb(self, path: Path) -> float:
        """Calculate directory size in MB."""
        total = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return total / (1024 * 1024)
```

## Testing Strategy

### Unit Tests

```python
def test_build_step_validates_input():
    """Test that build step validates OSM input."""
    step = BuildGraphHopperStep(country_code="NO")

    # Missing OSM file should fail
    with pytest.raises(FileNotFoundError):
        step.execute(context, Path("nonexistent.osm.pbf"))

def test_build_step_creates_graph_directory():
    """Test that graph directory is created."""
    step = BuildGraphHopperStep(country_code="NO")
    result = step.execute(context, sample_osm_file)

    assert result.output.exists()
    assert result.output.is_dir()
    assert (result.output / "nodes").exists()

def test_dry_run_skips_build():
    """Test that dry-run mode skips actual build."""
    context.dry_run = True
    step = BuildGraphHopperStep(country_code="NO")

    result = step.execute(context, sample_osm_file)

    assert result.status == StepStatus.SUCCESS
    assert "dry-run" in result.metadata
```

### Integration Tests

- Build graph from real OSM file (small sample)
- Verify graph can be loaded by GraphHopper
- Test routing with built graph

## Performance Considerations

### Memory Requirements

| Data Size | Heap Size | Build Time | Graph Size |
|-----------|-----------|------------|------------|
| Small (1k trails) | 1GB | ~30s | ~10MB |
| Medium (10k trails) | 2GB | ~2min | ~50MB |
| Large (134k trails) | 4GB | ~5min | ~200MB |

### Optimization Strategies

1. **Parallel Processing**: GraphHopper supports multi-threaded import
2. **Incremental Builds**: Only rebuild if OSM data changed
3. **Graph Caching**: Cache completed graphs, only rebuild on data change
4. **Memory Tuning**: Adjust `-Xmx` based on data size

## Error Handling

### Common Errors

1. **OutOfMemoryError**: Increase `-Xmx` heap size
2. **Invalid OSM**: Check transform step output
3. **Missing Elevation**: Elevation data download failed
4. **Timeout**: Build took >1 hour (increase timeout)

### Recovery Strategies

- **Retry with more memory**: Increase heap size on failure
- **Fall back to simpler profile**: Skip elevation if unavailable
- **Incremental retry**: Try building subsets if full build fails

## Next Steps

1. Implement `BuildGraphHopperStep` class
2. Add GraphHopper JAR download logic
3. Create configuration generation
4. Write comprehensive tests
5. Integrate into main pipeline
6. Add build validation step
7. Document GraphHopper setup for developers

## References

- [GraphHopper Documentation](https://github.com/graphhopper/graphhopper/blob/master/docs/core/quickstart-from-source.md)
- [GraphHopper Import Guide](https://github.com/graphhopper/graphhopper/blob/master/docs/core/routing.md)
- [Custom Models](https://github.com/graphhopper/graphhopper/blob/master/docs/core/custom-models.md)

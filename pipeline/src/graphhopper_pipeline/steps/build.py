"""Build step: Create GraphHopper routing graph from OSM data."""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm
from trails.pipeline import PipelineContext, PipelineStep, StepResult, StepStatus

from graphhopper_pipeline.config import CountryConfig, load_country_config


class BuildGraphHopperStep(PipelineStep[Path, Path]):
    """Build GraphHopper routing graph from OSM data.

    Takes an OSM PBF/XML file from the transform step and builds a
    GraphHopper routing graph that can be used for trail routing.

    Steps:
    1. Download GraphHopper JAR if not cached
    2. Generate GraphHopper configuration file
    3. Execute graph build via Java CLI
    4. Validate generated graph
    5. Return graph directory path
    """

    def __init__(self, country_code: str = "NO", graphhopper_version: str = "8.0") -> None:
        """Initialize build step.

        Args:
            country_code: ISO country code
            graphhopper_version: GraphHopper version to use
        """
        self.country_code = country_code
        self.graphhopper_version = graphhopper_version

    @property
    def name(self) -> str:
        """Step name."""
        return f"build-graph-{self.country_code.lower()}"

    @property
    def description(self) -> str:
        """Step description."""
        return f"Build GraphHopper routing graph for {self.country_code}"

    def execute(self, context: PipelineContext, input_data: Path) -> StepResult[Path]:
        """Execute GraphHopper build.

        Args:
            context: Pipeline context
            input_data: Path to OSM file (PBF or XML)

        Returns:
            StepResult with graph directory path
        """
        started_at = datetime.now()

        # Validate input
        if not input_data.exists():
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Input OSM file not found: {input_data}",
                duration_seconds=0,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Setup directories
        graph_dir = context.work_dir / "graphhopper-data"
        graph_dir.mkdir(parents=True, exist_ok=True)

        # Load country config
        country_config = load_country_config(self.country_code)

        try:
            # Download GraphHopper if needed
            graphhopper_jar = self._ensure_graphhopper_jar(context)

            # Generate configuration
            config_file = self._generate_config(context, input_data, graph_dir, country_config)

            # Build graph
            if context.dry_run:
                build_stats = {"nodes": 0, "edges": 0, "note": "dry-run"}
            else:
                build_stats = self._build_graph(graphhopper_jar, config_file)

                # Validate graph
                if not self._validate_graph(graph_dir):
                    return StepResult(
                        status=StepStatus.FAILED,
                        error="Graph validation failed - required files missing or too small",
                        duration_seconds=(datetime.now() - started_at).total_seconds(),
                        started_at=started_at,
                        completed_at=datetime.now(),
                    )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=f"Graph build failed: {str(e)}",
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
            )

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        metadata: dict[str, Any] = {
            "graph_dir": str(graph_dir),
            "graph_size_mb": self._get_dir_size_mb(graph_dir) if not context.dry_run else 0,
            "node_count": build_stats.get("nodes", 0),
            "edge_count": build_stats.get("edges", 0),
            "graphhopper_version": self.graphhopper_version,
        }

        if "import_time" in build_stats:
            metadata["import_time_seconds"] = build_stats["import_time"]

        return StepResult(
            status=StepStatus.SUCCESS,
            output=graph_dir,
            metadata=metadata,
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _ensure_graphhopper_jar(self, context: PipelineContext) -> Path:
        """Download GraphHopper JAR if not cached.

        Args:
            context: Pipeline context

        Returns:
            Path to GraphHopper JAR file
        """
        cache_dir = context.cache_dir or Path(".cache")
        jar_path = cache_dir / "downloads" / f"graphhopper-web-{self.graphhopper_version}.jar"

        if jar_path.exists():
            return jar_path

        # Create cache directory
        jar_path.parent.mkdir(parents=True, exist_ok=True)

        # Download from Maven Central
        url = (
            f"https://repo1.maven.org/maven2/com/graphhopper/"
            f"graphhopper-web/{self.graphhopper_version}/"
            f"graphhopper-web-{self.graphhopper_version}.jar"
        )

        print(f"Downloading GraphHopper {self.graphhopper_version}...")
        print(f"URL: {url}")

        # Download with progress bar
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192

        with (
            open(jar_path, "wb") as f,
            tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc="Downloading",
            ) as pbar,
        ):
            for chunk in response.iter_content(chunk_size=block_size):
                f.write(chunk)
                pbar.update(len(chunk))

        print(f"Downloaded to {jar_path}")
        return jar_path

    def _generate_config(
        self,
        context: PipelineContext,
        osm_file: Path,
        graph_dir: Path,
        country_config: CountryConfig,
    ) -> Path:
        """Generate GraphHopper configuration file.

        Args:
            context: Pipeline context
            osm_file: Path to OSM file
            graph_dir: Path to graph directory
            country_config: Country configuration

        Returns:
            Path to generated config file
        """
        pipeline_config = context.config.get("pipeline", {})

        # Generate YAML configuration
        config_content = f"""graphhopper:
  datareader.file: {osm_file.absolute()}
  graph.location: {graph_dir.absolute()}

  profiles:
"""

        # Add configured profiles
        for profile in pipeline_config.graphhopper_profiles:
            config_content += f"""    - name: {profile}
      vehicle: foot
      weighting: shortest
"""

        # Add encoded values for trail attributes
        config_content += """
  graph.encoded_values: |
    foot_access, sac_scale, trail_visibility,
    operator, surface, smoothness, width

  # Elevation data (SRTM ~30m resolution)
  graph.elevation.provider: srtm
  graph.elevation.cache_dir: {elevation_cache}
  graph.elevation.interpolate: bilinear
  graph.elevation.calc_mean_elevation: true

  # Import settings - ignore highways
  import.osm.ignored_highways: |
    motorway, motorway_link,
    trunk, trunk_link,
    primary, primary_link

  # Snap to trails (not roads)
  routing.snap_max_distance: 500
  routing.snap_preventions: [motorway, trunk]
""".format(elevation_cache=(context.cache_dir or Path(".cache")) / "elevation")

        # Write configuration
        config_file = context.work_dir / "graphhopper-config.yml"
        config_file.write_text(config_content)

        print(f"Generated GraphHopper config: {config_file}")
        return config_file

    def _build_graph(self, jar_path: Path, config_file: Path) -> dict[str, Any]:
        """Execute GraphHopper build command.

        Args:
            jar_path: Path to GraphHopper JAR
            config_file: Path to config file

        Returns:
            Build statistics dict

        Raises:
            RuntimeError: If build fails
        """
        print("Building GraphHopper graph...")
        print(f"JAR: {jar_path}")
        print(f"Config: {config_file}")

        cmd = [
            "java",
            "-Xmx4g",  # 4GB heap
            "-Xms2g",  # 2GB initial heap
            "-jar",
            str(jar_path),
            "import",
            str(config_file),
        ]

        print(f"Command: {' '.join(cmd)}")

        # Execute with streaming output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines: list[str] = []

        # Stream output in real-time
        if process.stdout:
            for line in process.stdout:
                line = line.rstrip()
                print(f"  {line}")
                output_lines.append(line)

        # Wait for completion
        return_code = process.wait(timeout=3600)  # 1 hour timeout

        if return_code != 0:
            raise RuntimeError(f"GraphHopper build failed with exit code {return_code}")

        # Parse output for statistics
        output = "\n".join(output_lines)
        return self._parse_build_output(output)

    def _parse_build_output(self, output: str) -> dict[str, Any]:
        """Parse GraphHopper build output for statistics.

        Args:
            output: Build output text

        Returns:
            Statistics dict with nodes, edges, import_time
        """
        stats: dict[str, Any] = {}

        # Look for patterns like:
        # "graph ... nodes=134047, edges=163558"
        # "took 45.2s"

        if match := re.search(r"nodes[=:\s]+(\d+)", output, re.IGNORECASE):
            stats["nodes"] = int(match.group(1))

        if match := re.search(r"edges[=:\s]+(\d+)", output, re.IGNORECASE):
            stats["edges"] = int(match.group(1))

        if match := re.search(r"took\s+([\d.]+)\s*s", output, re.IGNORECASE):
            stats["import_time"] = float(match.group(1))

        return stats

    def _validate_graph(self, graph_dir: Path) -> bool:
        """Validate that graph was built successfully.

        Args:
            graph_dir: Path to graph directory

        Returns:
            True if valid, False otherwise
        """
        # Check if at least some core files exist
        # GraphHopper creates various files depending on version and config:
        # - nodes_ch_*, edges_ch_* (contraction hierarchy)
        # - properties (graph metadata)
        # Exact file names vary, so we just check for reasonable file count
        core_files = list(graph_dir.rglob("*"))
        if len(core_files) < 3:
            print(f"Graph validation failed: only {len(core_files)} files found")
            return False

        # Check minimum size (should be > 1MB for any real trail network)
        size_mb = self._get_dir_size_mb(graph_dir)
        if size_mb < 1:
            print(f"Graph validation failed: size {size_mb:.1f}MB too small")
            return False

        print(f"Graph validated: {len(core_files)} files, {size_mb:.1f}MB")
        return True

    def _get_dir_size_mb(self, path: Path) -> float:
        """Calculate directory size in MB.

        Args:
            path: Directory path

        Returns:
            Size in megabytes
        """
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / (1024 * 1024)

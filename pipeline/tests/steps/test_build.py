"""Tests for GraphHopper build step."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from trails.pipeline import PipelineContext, StepStatus

from graphhopper_pipeline.config import CountryConfig, PipelineConfig
from graphhopper_pipeline.steps import BuildGraphHopperStep


@pytest.fixture
def mock_context(tmp_path: Path) -> PipelineContext:
    """Create a mock pipeline context."""
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"
    cache_dir = tmp_path / ".cache"

    work_dir.mkdir()
    output_dir.mkdir()
    cache_dir.mkdir()

    pipeline_config = PipelineConfig(
        name="test-pipeline",
        version="1.0.0",
        schedule_cron="0 6 * * 6",
        output_dir=Path("output"),
        work_dir=Path("work"),
        cache_dir=Path(".cache"),
        retention_count=2,
        max_trail_count_drop_percent=20.0,
        retry_max_attempts=5,
        retry_initial_backoff_minutes=5,
        retry_backoff_multiplier=2.0,
        retry_max_backoff_minutes=60,
        graphhopper_version="8.0",
        graphhopper_profiles=["hiking"],
    )

    country_config = CountryConfig(
        name="Norway",
        code="NO",
        crs="EPSG:25833",
        bounds={"min_lon": 4.0, "max_lon": 32.0, "min_lat": 57.0, "max_lat": 72.0},
        data_sources=[],
        osm_mappings={},
        inference_rules={},
    )

    return PipelineContext(
        config={"pipeline": pipeline_config, "country": country_config},
        work_dir=work_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        dry_run=False,
    )


@pytest.fixture
def sample_osm_file(tmp_path: Path) -> Path:
    """Create a sample OSM file."""
    osm_file = tmp_path / "trails.osm.pbf"
    osm_file.write_text("mock OSM data")
    return osm_file


def test_build_step_initialization():
    """Test that build step initializes correctly."""
    step = BuildGraphHopperStep(country_code="NO", graphhopper_version="8.0")

    assert step.country_code == "NO"
    assert step.graphhopper_version == "8.0"
    assert step.name == "build-graph-no"
    assert "GraphHopper" in step.description


def test_build_step_validates_input_file(mock_context: PipelineContext):
    """Test that build step validates input file exists."""
    step = BuildGraphHopperStep(country_code="NO")

    # Non-existent file should fail
    result = step.execute(mock_context, Path("/nonexistent/file.osm.pbf"))

    assert result.status == StepStatus.FAILED
    assert "not found" in result.error


def test_build_step_dry_run(mock_context: PipelineContext, sample_osm_file: Path):
    """Test that dry-run mode skips actual build."""
    mock_context.dry_run = True
    step = BuildGraphHopperStep(country_code="NO")

    with patch.object(step, "_ensure_graphhopper_jar", return_value=Path("/fake/jar")):
        with patch.object(step, "_generate_config", return_value=Path("/fake/config")):
            result = step.execute(mock_context, sample_osm_file)

    assert result.status == StepStatus.SUCCESS
    # In dry-run, build stats include note="dry-run" but metadata is built from stats
    assert result.metadata["node_count"] == 0
    assert result.metadata["edge_count"] == 0
    assert result.metadata["graph_size_mb"] == 0


def test_generate_config(mock_context: PipelineContext, sample_osm_file: Path):
    """Test configuration file generation."""
    step = BuildGraphHopperStep(country_code="NO")

    graph_dir = mock_context.work_dir / "graphhopper-data"
    graph_dir.mkdir()

    country_config = mock_context.config["country"]

    config_file = step._generate_config(mock_context, sample_osm_file, graph_dir, country_config)

    assert config_file.exists()
    assert config_file.name == "graphhopper-config.yml"

    content = config_file.read_text()
    assert "graphhopper:" in content
    assert str(sample_osm_file.absolute()) in content
    assert str(graph_dir.absolute()) in content
    assert "hiking" in content
    assert "foot_access" in content
    assert "sac_scale" in content


def test_parse_build_output():
    """Test parsing GraphHopper build output."""
    step = BuildGraphHopperStep(country_code="NO")

    # Mock GraphHopper output - use "took" instead of "in"
    output = """
    Loading graph from disk...
    Graph nodes=134047, edges=163558
    Import took 45.2s
    """

    stats = step._parse_build_output(output)

    assert stats["nodes"] == 134047
    assert stats["edges"] == 163558
    assert stats["import_time"] == 45.2


def test_parse_build_output_alternative_format():
    """Test parsing alternative GraphHopper output formats."""
    step = BuildGraphHopperStep(country_code="NO")

    # Alternative format with colons
    output = """
    Graph summary:
      nodes: 50000
      edges: 75000
    Import took 30.5 s
    """

    stats = step._parse_build_output(output)

    assert stats["nodes"] == 50000
    assert stats["edges"] == 75000
    assert stats["import_time"] == 30.5


def test_validate_graph_success(tmp_path: Path):
    """Test successful graph validation."""
    step = BuildGraphHopperStep(country_code="NO")

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    # Create mock graph files
    (graph_dir / "nodes_ch_fastest").write_bytes(b"x" * 1024 * 1024)  # 1MB
    (graph_dir / "edges_ch_fastest").write_bytes(b"x" * 1024 * 1024)
    (graph_dir / "properties").write_text("version=8.0")

    assert step._validate_graph(graph_dir) is True


def test_validate_graph_too_few_files(tmp_path: Path):
    """Test graph validation fails with too few files."""
    step = BuildGraphHopperStep(country_code="NO")

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    # Only 1 file - should fail
    (graph_dir / "nodes").write_text("test")

    assert step._validate_graph(graph_dir) is False


def test_validate_graph_too_small(tmp_path: Path):
    """Test graph validation fails if size too small."""
    step = BuildGraphHopperStep(country_code="NO")

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()

    # Multiple files but total < 1MB
    for i in range(5):
        (graph_dir / f"file{i}").write_bytes(b"x" * 100)  # 500 bytes total

    assert step._validate_graph(graph_dir) is False


def test_get_dir_size_mb(tmp_path: Path):
    """Test directory size calculation."""
    step = BuildGraphHopperStep(country_code="NO")

    test_dir = tmp_path / "test"
    test_dir.mkdir()

    # Create 2MB of files
    (test_dir / "file1").write_bytes(b"x" * 1024 * 1024)  # 1MB
    (test_dir / "file2").write_bytes(b"x" * 1024 * 1024)  # 1MB

    size_mb = step._get_dir_size_mb(test_dir)

    assert 1.9 < size_mb < 2.1  # Allow small rounding


def test_ensure_graphhopper_jar_cached(mock_context: PipelineContext):
    """Test that cached JAR is reused."""
    step = BuildGraphHopperStep(country_code="NO", graphhopper_version="8.0")

    # Create fake cached JAR
    jar_path = mock_context.cache_dir / "downloads" / "graphhopper-web-8.0.jar"
    jar_path.parent.mkdir(parents=True)
    jar_path.write_text("fake jar")

    result_jar = step._ensure_graphhopper_jar(mock_context)

    assert result_jar == jar_path
    assert result_jar.exists()


def test_ensure_graphhopper_jar_downloads(mock_context: PipelineContext):
    """Test that JAR is downloaded if not cached."""
    step = BuildGraphHopperStep(country_code="NO", graphhopper_version="8.0")

    # Mock requests.get
    mock_response = MagicMock()
    mock_response.headers = {"content-length": "1000"}
    mock_response.iter_content.return_value = [b"x" * 100 for _ in range(10)]

    with patch("graphhopper_pipeline.steps.build.requests.get", return_value=mock_response):
        with patch("graphhopper_pipeline.steps.build.tqdm"):  # Suppress progress bar
            result_jar = step._ensure_graphhopper_jar(mock_context)

    assert result_jar.exists()
    assert result_jar.name == "graphhopper-web-8.0.jar"


def test_build_graph_error_handling(mock_context: PipelineContext, sample_osm_file: Path):
    """Test error handling during graph build."""
    step = BuildGraphHopperStep(country_code="NO")

    with patch.object(step, "_ensure_graphhopper_jar", return_value=Path("/fake/jar")):
        with patch.object(step, "_generate_config", return_value=Path("/fake/config")):
            with patch.object(step, "_build_graph", side_effect=RuntimeError("Build failed")):
                result = step.execute(mock_context, sample_osm_file)

    assert result.status == StepStatus.FAILED
    assert "Build failed" in result.error


def test_build_graph_validation_failure(mock_context: PipelineContext, sample_osm_file: Path):
    """Test handling of graph validation failure."""
    step = BuildGraphHopperStep(country_code="NO")

    with patch.object(step, "_ensure_graphhopper_jar", return_value=Path("/fake/jar")):
        with patch.object(step, "_generate_config", return_value=Path("/fake/config")):
            with patch.object(step, "_build_graph", return_value={"nodes": 1000, "edges": 2000}):
                with patch.object(step, "_validate_graph", return_value=False):
                    result = step.execute(mock_context, sample_osm_file)

    assert result.status == StepStatus.FAILED
    assert "validation failed" in result.error


def test_build_step_success_integration(mock_context: PipelineContext, sample_osm_file: Path):
    """Test successful build step execution (mocked)."""
    step = BuildGraphHopperStep(country_code="NO")

    graph_dir = mock_context.work_dir / "graphhopper-data"

    with patch.object(step, "_ensure_graphhopper_jar", return_value=Path("/fake/jar")):
        with patch.object(step, "_generate_config", return_value=Path("/fake/config")):
            with patch.object(step, "_build_graph", return_value={"nodes": 134047, "edges": 163558, "import_time": 45.2}):
                with patch.object(step, "_validate_graph", return_value=True):
                    with patch.object(step, "_get_dir_size_mb", return_value=150.5):
                        result = step.execute(mock_context, sample_osm_file)

    assert result.status == StepStatus.SUCCESS
    assert result.output == graph_dir
    assert result.metadata["node_count"] == 134047
    assert result.metadata["edge_count"] == 163558
    assert result.metadata["import_time_seconds"] == 45.2
    assert result.metadata["graph_size_mb"] == 150.5
    assert result.metadata["graphhopper_version"] == "8.0"

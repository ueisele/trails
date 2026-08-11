"""Tests for release step."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from graphhopper_pipeline.config import CountryConfig, PipelineConfig
from graphhopper_pipeline.steps import CreateReleaseStep, ReleaseArtifacts
from trails.pipeline import PipelineContext, StepStatus


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
def sample_artifacts(tmp_path: Path) -> ReleaseArtifacts:
    """Create sample release artifacts."""
    # Create OSM file
    osm_file = tmp_path / "trails.osm.pbf"
    osm_file.write_bytes(b"mock OSM data" * 1000)  # ~13KB

    # Create graph directory with files
    graph_dir = tmp_path / "graphhopper-data"
    graph_dir.mkdir()
    (graph_dir / "nodes").write_bytes(b"x" * 1024 * 100)  # 100KB
    (graph_dir / "edges").write_bytes(b"x" * 1024 * 100)  # 100KB
    (graph_dir / "properties").write_text("version=8.0")

    # Build stats
    build_stats = {
        "trail_count": 134047,
        "way_count": 163558,
        "node_count": 150000,
        "edge_count": 200000,
        "version": "20251001",
        "updated_at": "2025-10-01T04:21:03",
    }

    return ReleaseArtifacts(
        osm_file=osm_file,
        graph_dir=graph_dir,
        build_stats=build_stats,
    )


def test_release_step_initialization():
    """Test that release step initializes correctly."""
    step = CreateReleaseStep(country_code="NO", retention_count=2)

    assert step.country_code == "NO"
    assert step.retention_count == 2
    assert step.name == "create-release-no"
    assert "GitHub Release" in step.description


def test_release_step_validates_osm_file(mock_context: PipelineContext, sample_artifacts: ReleaseArtifacts):
    """Test that release step validates OSM file exists."""
    step = CreateReleaseStep(country_code="NO")

    # Non-existent OSM file should fail
    bad_artifacts = ReleaseArtifacts(
        osm_file=Path("/nonexistent/file.osm.pbf"),
        graph_dir=sample_artifacts.graph_dir,
        build_stats=sample_artifacts.build_stats,
    )

    result = step.execute(mock_context, bad_artifacts)

    assert result.status == StepStatus.FAILED
    assert "OSM file not found" in result.error


def test_release_step_validates_graph_dir(mock_context: PipelineContext, sample_artifacts: ReleaseArtifacts):
    """Test that release step validates graph directory exists."""
    step = CreateReleaseStep(country_code="NO")

    # Non-existent graph dir should fail
    bad_artifacts = ReleaseArtifacts(
        osm_file=sample_artifacts.osm_file,
        graph_dir=Path("/nonexistent/graph"),
        build_stats=sample_artifacts.build_stats,
    )

    result = step.execute(mock_context, bad_artifacts)

    assert result.status == StepStatus.FAILED
    assert "Graph directory not found" in result.error


def test_check_gh_cli_available():
    """Test checking for gh CLI availability."""
    step = CreateReleaseStep(country_code="NO")

    # Mock successful gh --version
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0)
        assert step._check_gh_cli() is True

    # Mock failed gh --version
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=1)
        assert step._check_gh_cli() is False

    # Mock gh not found
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert step._check_gh_cli() is False


def test_generate_version(sample_artifacts: ReleaseArtifacts):
    """Test version generation."""
    step = CreateReleaseStep(country_code="NO")

    version = step._generate_version(sample_artifacts)

    # The date comes from the clock, so pin the shape rather than a fixed year.
    assert version.startswith(f"v{datetime.now():%Y-%m-%d}-")
    assert "geonorge" in version
    assert "20251001" in version


def test_calculate_file_hash(tmp_path: Path):
    """Test file hash calculation."""
    step = CreateReleaseStep(country_code="NO")

    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    hash1 = step._calculate_file_hash(test_file)
    hash2 = step._calculate_file_hash(test_file)

    # Same file should have same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest length

    # Different content should have different hash
    test_file.write_text("different content")
    hash3 = step._calculate_file_hash(test_file)
    assert hash1 != hash3


def test_should_create_release_dry_run(sample_artifacts: ReleaseArtifacts):
    """Test that dry-run always creates release."""
    step = CreateReleaseStep(country_code="NO")

    assert step._should_create_release(sample_artifacts, dry_run=True) is True


def test_should_create_release_no_previous(sample_artifacts: ReleaseArtifacts):
    """Test release creation when no previous release exists."""
    step = CreateReleaseStep(country_code="NO")

    # Mock no previous release (command fails)
    with patch.object(step, "_get_latest_release_info", side_effect=RuntimeError("No previous release")):
        assert step._should_create_release(sample_artifacts, dry_run=False) is True


def test_should_create_release_data_changed(sample_artifacts: ReleaseArtifacts):
    """Test release creation when data has changed."""
    step = CreateReleaseStep(country_code="NO")

    # Mock previous release with different hash
    with patch.object(step, "_get_latest_release_info", return_value={"osm_hash": "old_hash_abc123"}):
        assert step._should_create_release(sample_artifacts, dry_run=False) is True


def test_should_create_release_no_changes(sample_artifacts: ReleaseArtifacts):
    """Test release skipped when no data changes."""
    step = CreateReleaseStep(country_code="NO")

    # Calculate actual hash
    actual_hash = step._calculate_file_hash(sample_artifacts.osm_file)

    # Mock previous release with same hash
    with patch.object(step, "_get_latest_release_info", return_value={"osm_hash": actual_hash}):
        assert step._should_create_release(sample_artifacts, dry_run=False) is False


def test_package_artifacts(mock_context: PipelineContext, sample_artifacts: ReleaseArtifacts):
    """Test artifact packaging."""
    step = CreateReleaseStep(country_code="NO")

    version = "v2025-10-03-geonorge-20251001"
    packaged = step._package_artifacts(mock_context, sample_artifacts, version)

    assert len(packaged) == 3  # OSM, graph tarball, metadata
    assert packaged[0].suffix == ".pbf"
    assert packaged[1].suffix == ".gz"
    assert packaged[2].suffix == ".json"

    # Check files exist
    for file in packaged:
        assert file.exists()

    # Check metadata content
    import json

    metadata = json.loads(packaged[2].read_text())
    assert metadata["country"] == "NO"
    assert metadata["version"] == version
    assert "osm_hash" in metadata
    assert "statistics" in metadata


def test_create_tarball(tmp_path: Path):
    """Test tarball creation."""
    step = CreateReleaseStep(country_code="NO")

    # Create source directory
    source_dir = tmp_path / "graph"
    source_dir.mkdir()
    (source_dir / "file1").write_text("content1")
    (source_dir / "file2").write_text("content2")

    # Create tarball
    tarball = tmp_path / "output.tar.gz"
    step._create_tarball(source_dir, tarball)

    assert tarball.exists()
    assert tarball.stat().st_size > 0

    # Verify can extract
    import tarfile

    with tarfile.open(tarball, "r:gz") as tar:
        members = tar.getnames()
        assert "graph/file1" in members
        assert "graph/file2" in members


def test_generate_release_notes(sample_artifacts: ReleaseArtifacts):
    """Test release notes generation."""
    step = CreateReleaseStep(country_code="NO")

    version = "v2025-10-03-geonorge-20251001"
    notes = step._generate_release_notes(sample_artifacts, version)

    # Check structure
    assert "# NO Trail Data Release" in notes
    assert "## Summary" in notes
    assert "## Statistics" in notes
    assert "## Files" in notes
    assert "## Usage" in notes
    assert "## Data Source" in notes

    # Check statistics
    assert "134,047" in notes  # trail_count
    assert "163,558" in notes  # way_count
    assert "150,000" in notes  # node_count
    assert "200,000" in notes  # edge_count

    # Check data source info
    assert "CC0 1.0" in notes
    assert "Kartverket" in notes
    assert "20251001" in notes  # version


def test_create_github_release_dry_run(sample_artifacts: ReleaseArtifacts):
    """Test GitHub release creation in dry-run mode."""
    step = CreateReleaseStep(country_code="NO")

    version = "v2025-10-03-geonorge-20251001"
    title = "NO Trail Data v2025-10-03-geonorge-20251001"
    notes = "Test notes"
    assets = [Path("/tmp/test1.pbf"), Path("/tmp/test2.tar.gz")]

    release_url = step._create_github_release(
        tag=version,
        title=title,
        notes=notes,
        assets=assets,
        dry_run=True,
    )

    assert version in release_url
    assert "github.com" in release_url


def test_create_github_release_success(sample_artifacts: ReleaseArtifacts, tmp_path: Path):
    """Test successful GitHub release creation."""
    step = CreateReleaseStep(country_code="NO")

    # Create temp assets
    asset1 = tmp_path / "test.pbf"
    asset1.write_text("test")
    asset2 = tmp_path / "test.tar.gz"
    asset2.write_text("test")

    version = "v2025-10-03-geonorge-20251001"
    title = "Test Release"
    notes = "Test notes"
    assets = [asset1, asset2]

    # Mock subprocess
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "https://github.com/user/repo/releases/tag/v2025-10-03"

    with patch("subprocess.run", return_value=mock_result):
        release_url = step._create_github_release(
            tag=version,
            title=title,
            notes=notes,
            assets=assets,
            dry_run=False,
        )

    assert "github.com" in release_url
    assert "releases" in release_url


def test_create_github_release_failure(sample_artifacts: ReleaseArtifacts, tmp_path: Path):
    """Test GitHub release creation failure."""
    step = CreateReleaseStep(country_code="NO")

    asset = tmp_path / "test.pbf"
    asset.write_text("test")

    version = "v2025-10-03-geonorge-20251001"
    title = "Test Release"
    notes = "Test notes"
    assets = [asset]

    # Mock failed subprocess
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "Error: unauthorized"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="gh release create failed"):
            step._create_github_release(
                tag=version,
                title=title,
                notes=notes,
                assets=assets,
                dry_run=False,
            )


def test_cleanup_old_releases():
    """Test cleanup of old releases."""
    step = CreateReleaseStep(country_code="NO")

    # Mock gh release list output
    mock_list_output = """v2025-10-03-geonorge-20251001\tRelease 1\tLatest\t2025-10-03
v2025-09-26-geonorge-20250924\tRelease 2\tLatest\t2025-09-26
v2025-09-19-geonorge-20250917\tRelease 3\tLatest\t2025-09-19
v2025-09-12-geonorge-20250910\tRelease 4\tLatest\t2025-09-12"""

    mock_list_result = Mock()
    mock_list_result.returncode = 0
    mock_list_result.stdout = mock_list_output

    mock_delete_result = Mock()
    mock_delete_result.returncode = 0

    with patch("subprocess.run") as mock_run:
        # First call: list releases
        # Subsequent calls: delete releases
        mock_run.side_effect = [mock_list_result, mock_delete_result, mock_delete_result]

        step._cleanup_old_releases(keep_count=2)

        # Should delete 2 oldest releases
        assert mock_run.call_count == 3  # 1 list + 2 deletes


def test_cleanup_spans_years():
    """Releases from an earlier year must still be cleaned up."""
    step = CreateReleaseStep(country_code="NO")

    mock_list_result = Mock()
    mock_list_result.returncode = 0
    mock_list_result.stdout = (
        "v2026-01-10-geonorge-20260108\tRelease 1\tLatest\t2026-01-10\n"
        "v2025-12-27-geonorge-20251225\tRelease 2\t\t2025-12-27\n"
        "v2025-12-20-geonorge-20251218\tRelease 3\t\t2025-12-20"
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [mock_list_result, Mock(returncode=0)]
        step._cleanup_old_releases(keep_count=2)

    # 1 list + 1 delete: the oldest goes even though it predates the current year.
    assert mock_run.call_count == 2


def test_cleanup_leaves_foreign_releases_alone():
    """Tags this pipeline did not create must never be deleted."""
    step = CreateReleaseStep(country_code="NO")

    mock_list_result = Mock()
    mock_list_result.returncode = 0
    mock_list_result.stdout = (
        "v1.2.0\tHand-made release\tLatest\t2026-02-01\nnightly\tNightly build\t\t2026-01-31\nv2026-01-10-geonorge-20260108\tRelease 1\t\t2026-01-10"
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [mock_list_result, Mock(returncode=0)]
        step._cleanup_old_releases(keep_count=0)

    # Only this pipeline's own tag is eligible; the hand-made ones are untouched.
    deleted = [call.args[0][3] for call in mock_run.call_args_list[1:]]
    assert deleted == ["v2026-01-10-geonorge-20260108"]


def test_execute_dry_run(mock_context: PipelineContext, sample_artifacts: ReleaseArtifacts):
    """Test release step execution in dry-run mode."""
    mock_context.dry_run = True
    step = CreateReleaseStep(country_code="NO")

    with patch.object(step, "_check_gh_cli", return_value=True):
        result = step.execute(mock_context, sample_artifacts)

    assert result.status == StepStatus.SUCCESS
    assert result.output is not None
    assert "github.com" in result.output
    assert "version" in result.metadata


def test_execute_skipped_no_changes(mock_context: PipelineContext, sample_artifacts: ReleaseArtifacts):
    """Test release step skipped when no changes."""
    step = CreateReleaseStep(country_code="NO")

    actual_hash = step._calculate_file_hash(sample_artifacts.osm_file)

    with patch.object(step, "_check_gh_cli", return_value=True):
        with patch.object(step, "_get_latest_release_info", return_value={"osm_hash": actual_hash}):
            result = step.execute(mock_context, sample_artifacts)

    assert result.status == StepStatus.SKIPPED
    assert "No data changes" in result.metadata["reason"]


def test_execute_gh_cli_missing(mock_context: PipelineContext, sample_artifacts: ReleaseArtifacts):
    """Test release step fails if gh CLI is missing."""
    step = CreateReleaseStep(country_code="NO")

    with patch.object(step, "_check_gh_cli", return_value=False):
        result = step.execute(mock_context, sample_artifacts)

    assert result.status == StepStatus.FAILED
    assert "GitHub CLI" in result.error
    assert "cli.github.com" in result.error


def test_execute_success_integration(mock_context: PipelineContext, sample_artifacts: ReleaseArtifacts):
    """Test successful release step execution (mocked)."""
    step = CreateReleaseStep(country_code="NO")

    with patch.object(step, "_check_gh_cli", return_value=True):
        with patch.object(step, "_should_create_release", return_value=True):
            with patch.object(step, "_create_github_release", return_value="https://github.com/repo/releases/tag/v2025"):
                with patch.object(step, "_cleanup_old_releases"):
                    result = step.execute(mock_context, sample_artifacts)

    assert result.status == StepStatus.SUCCESS
    assert result.output == "https://github.com/repo/releases/tag/v2025"
    assert "version" in result.metadata
    assert "release_url" in result.metadata
    assert result.metadata["asset_count"] == 3
    assert result.metadata["osm_size_mb"] > 0
    assert result.metadata["graph_size_mb"] > 0

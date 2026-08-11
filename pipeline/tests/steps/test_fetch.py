"""Tests for the fetch step."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
import pytest
from graphhopper_pipeline.steps.fetch import FetchTrailsStep
from shapely.geometry import LineString
from trails.pipeline import PipelineContext, StepStatus


@pytest.fixture
def mock_context(tmp_path: Path) -> PipelineContext:
    """Create a mock pipeline context."""
    return PipelineContext(
        config={},
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
        cache_dir=tmp_path / ".cache",
        dry_run=False,
    )


@pytest.fixture
def mock_trail_data() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Create mock trail data."""
    # Create spatial layer
    spatial_data = {
        "local_id": ["id1", "id2", "id3"],
        "geometry": [
            LineString([(10.0, 60.0), (10.1, 60.1)]),
            LineString([(10.2, 60.2), (10.3, 60.3)]),
            LineString([(10.4, 60.4), (10.5, 60.5)]),
        ],
    }
    spatial_gdf = gpd.GeoDataFrame(spatial_data, crs="EPSG:4326")

    # Create attribute table
    attribute_data = {
        "hiking_trail_fk": ["id1", "id1", "id2", "id3"],
        "trail_name": ["Trail A", "Trail B", "Trail C", "Trail D"],
        "trail_number": ["1", "2", "3", "4"],
    }
    attributes_df = pd.DataFrame(attribute_data)

    return spatial_gdf, attributes_df


def test_fetch_step_name() -> None:
    """Test fetch step name generation."""
    step = FetchTrailsStep(country_code="NO")
    assert step.name == "fetch-trails-no"

    step_se = FetchTrailsStep(country_code="SE")
    assert step_se.name == "fetch-trails-se"


def test_fetch_step_description() -> None:
    """Test fetch step description."""
    step = FetchTrailsStep(country_code="NO")
    assert "NO" in step.description
    assert "trail data" in step.description.lower()


def test_should_skip_no_cache(mock_context: PipelineContext) -> None:
    """Test should_skip when no cache exists."""
    step = FetchTrailsStep(country_code="NO")
    should_skip, reason = step.should_skip(mock_context, None)

    assert should_skip is False
    assert reason is None


def test_should_skip_recent_cache(mock_context: PipelineContext) -> None:
    """Test should_skip with recent cache."""
    step = FetchTrailsStep(country_code="NO")

    # Create cache marker
    cache_dir = mock_context.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_marker = cache_dir / "turrutebasen_no_downloaded.txt"
    cache_marker.write_text(f"Downloaded at {datetime.now().isoformat()}")

    should_skip, reason = step.should_skip(mock_context, None)

    assert should_skip is True
    assert reason is not None
    assert "cached" in reason.lower()


def test_should_skip_old_cache(mock_context: PipelineContext) -> None:
    """Test should_skip with old cache (>7 days)."""
    import time

    step = FetchTrailsStep(country_code="NO")

    # Create old cache marker
    cache_dir = mock_context.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_marker = cache_dir / "turrutebasen_no_downloaded.txt"
    cache_marker.write_text("Downloaded at 2020-01-01T00:00:00")

    # Set the file modification time to 8 days ago
    import os

    old_time = time.time() - (8 * 24 * 60 * 60)
    os.utime(cache_marker, (old_time, old_time))

    should_skip, reason = step.should_skip(mock_context, None)

    assert should_skip is False
    assert reason is None


@patch("graphhopper_pipeline.steps.fetch.GeonorgeSource")
def test_execute_success(
    mock_source_class: MagicMock,
    mock_context: PipelineContext,
    mock_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test successful execution of fetch step."""
    spatial_gdf, attributes_df = mock_trail_data

    # Mock the Geonorge source
    mock_source = MagicMock()
    mock_source_class.return_value = mock_source

    mock_trail_dataset = MagicMock()
    mock_trail_dataset.version = "2024-01-01"
    mock_trail_dataset.crs = "EPSG:25833"
    mock_trail_dataset.spatial_layers = {"hiking_trail_centerline": spatial_gdf}
    mock_trail_dataset.attribute_tables = {"hiking_trail_info_table": attributes_df}

    mock_source.load_turrutebasen.return_value = mock_trail_dataset

    # Execute step
    step = FetchTrailsStep(country_code="NO")
    result = step.execute(mock_context, None)

    # Verify result
    assert result.status == StepStatus.SUCCESS
    assert result.output is not None
    assert result.error is None

    output_spatial, output_attributes = result.output
    assert isinstance(output_spatial, gpd.GeoDataFrame)
    assert isinstance(output_attributes, pd.DataFrame)
    assert len(output_spatial) == 3
    assert len(output_attributes) == 4

    # Verify metadata
    assert result.metadata is not None
    assert result.metadata["source"] == "Geonorge Turrutebasen"
    assert result.metadata["version"] == "2024-01-01"
    assert result.metadata["trail_count"] == 3
    assert result.metadata["attribute_count"] == 4
    assert result.metadata["output_crs"] == "EPSG:4326"

    # Verify duration
    assert result.duration_seconds is not None
    assert result.duration_seconds >= 0


@patch("graphhopper_pipeline.steps.fetch.GeonorgeSource")
def test_execute_missing_spatial_layer(
    mock_source_class: MagicMock,
    mock_context: PipelineContext,
) -> None:
    """Test execution with missing spatial layer."""
    mock_source = MagicMock()
    mock_source_class.return_value = mock_source

    mock_trail_dataset = MagicMock()
    mock_trail_dataset.spatial_layers = {}  # Missing expected layer
    mock_trail_dataset.attribute_tables = {"hiking_trail_info_table": pd.DataFrame()}

    mock_source.load_turrutebasen.return_value = mock_trail_dataset

    step = FetchTrailsStep(country_code="NO")
    result = step.execute(mock_context, None)

    assert result.status == StepStatus.FAILED
    assert result.error is not None
    assert "hiking_trail_centerline" in result.error


@patch("graphhopper_pipeline.steps.fetch.GeonorgeSource")
def test_execute_missing_attribute_table(
    mock_source_class: MagicMock,
    mock_context: PipelineContext,
    mock_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test execution with missing attribute table."""
    spatial_gdf, _ = mock_trail_data

    mock_source = MagicMock()
    mock_source_class.return_value = mock_source

    mock_trail_dataset = MagicMock()
    mock_trail_dataset.spatial_layers = {"hiking_trail_centerline": spatial_gdf}
    mock_trail_dataset.attribute_tables = {}  # Missing expected table

    mock_source.load_turrutebasen.return_value = mock_trail_dataset

    step = FetchTrailsStep(country_code="NO")
    result = step.execute(mock_context, None)

    assert result.status == StepStatus.FAILED
    assert result.error is not None
    assert "hiking_trail_info_table" in result.error


@patch("graphhopper_pipeline.steps.fetch.GeonorgeSource")
def test_execute_crs_conversion(
    mock_source_class: MagicMock,
    mock_context: PipelineContext,
    mock_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test CRS conversion from UTM to WGS84."""
    spatial_gdf, attributes_df = mock_trail_data

    # Convert to UTM (EPSG:25833)
    spatial_gdf_utm = spatial_gdf.to_crs("EPSG:25833")

    mock_source = MagicMock()
    mock_source_class.return_value = mock_source

    mock_trail_dataset = MagicMock()
    mock_trail_dataset.version = "2024-01-01"
    mock_trail_dataset.crs = "EPSG:25833"
    mock_trail_dataset.spatial_layers = {"hiking_trail_centerline": spatial_gdf_utm}
    mock_trail_dataset.attribute_tables = {"hiking_trail_info_table": attributes_df}

    mock_source.load_turrutebasen.return_value = mock_trail_dataset

    step = FetchTrailsStep(country_code="NO")
    result = step.execute(mock_context, None)

    assert result.status == StepStatus.SUCCESS
    output_spatial, _ = result.output

    # Verify CRS was converted to WGS84
    assert output_spatial.crs.to_epsg() == 4326


@patch("graphhopper_pipeline.steps.fetch.GeonorgeSource")
def test_execute_creates_cache_marker(
    mock_source_class: MagicMock,
    mock_context: PipelineContext,
    mock_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test that execution creates cache marker file."""
    spatial_gdf, attributes_df = mock_trail_data

    mock_source = MagicMock()
    mock_source_class.return_value = mock_source

    mock_trail_dataset = MagicMock()
    mock_trail_dataset.version = "2024-01-01"
    mock_trail_dataset.crs = "EPSG:25833"
    mock_trail_dataset.spatial_layers = {"hiking_trail_centerline": spatial_gdf}
    mock_trail_dataset.attribute_tables = {"hiking_trail_info_table": attributes_df}

    mock_source.load_turrutebasen.return_value = mock_trail_dataset

    step = FetchTrailsStep(country_code="NO")
    result = step.execute(mock_context, None)

    assert result.status == StepStatus.SUCCESS

    # Verify cache marker was created
    cache_marker = mock_context.cache_dir / "turrutebasen_no_downloaded.txt"
    assert cache_marker.exists()
    assert "Downloaded at" in cache_marker.read_text()


@patch("graphhopper_pipeline.steps.fetch.GeonorgeSource")
def test_execute_exception_handling(
    mock_source_class: MagicMock,
    mock_context: PipelineContext,
) -> None:
    """Test exception handling during execution."""
    mock_source = MagicMock()
    mock_source_class.return_value = mock_source
    mock_source.load_turrutebasen.side_effect = Exception("Network error")

    step = FetchTrailsStep(country_code="NO")
    result = step.execute(mock_context, None)

    assert result.status == StepStatus.FAILED
    assert result.error is not None
    assert "Network error" in result.error
    assert result.duration_seconds is not None

"""Tests for the transform step."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
import pytest
from graphhopper_pipeline.config import CountryConfig, OSMMapping
from graphhopper_pipeline.steps.transform import TransformToOSMStep
from lxml import etree
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
def sample_trail_data() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Create sample trail data for testing."""
    # Create spatial layer
    spatial_data = {
        "local_id": ["trail1", "trail2", "trail3"],
        "geometry": [
            LineString([(10.0, 60.0), (10.1, 60.1), (10.2, 60.2)]),
            LineString([(11.0, 61.0), (11.1, 61.1)]),
            LineString([(12.0, 62.0), (12.1, 62.1), (12.2, 62.2), (12.3, 62.3)]),
        ],
        "objtype": ["TurrStrekningEnkel", "TurrStrekningEnkel", "TurrStrekningEnkel"],
        "rutefolger": ["ST", "TI", "LE"],
        "merking": ["1", "1", "0"],
    }
    spatial_gdf = gpd.GeoDataFrame(spatial_data, crs="EPSG:4326")

    # Create attribute table with some many-to-one relationships
    # Note: gradering is NOT included here to test inference
    attribute_data = {
        "hiking_trail_fk": ["trail1", "trail1", "trail2", "trail3"],
        "trail_name": ["Pilegrimsleden", "Gudbrandsdalsleden", "Besseggen", "Galdhøpiggen"],
        "trail_number": ["1", "2", "3", "4"],
    }
    attributes_df = pd.DataFrame(attribute_data)

    return spatial_gdf, attributes_df


@pytest.fixture
def mock_country_config() -> CountryConfig:
    """Create a mock country configuration."""
    # Create OSM mappings
    osm_mappings = {
        "objtype": OSMMapping(
            turrutebasen_field="objtype",
            osm_tag="highway",
            tier=1,
            completeness=100.0,
            required=True,
            values={"TurrStrekningEnkel": "path"},
        ),
        "rutefolger": OSMMapping(
            turrutebasen_field="rutefolger",
            osm_tag="highway",
            tier=1,
            completeness=94.0,
            required=False,
            values={"ST": "path", "TI": "path", "LE": "path"},
        ),
        "merking": OSMMapping(
            turrutebasen_field="merking",
            osm_tag="trail_marking",
            tier=1,
            completeness=100.0,
            required=False,
            values={"1": "yes", "0": "no"},
        ),
        "trail_name": OSMMapping(
            turrutebasen_field="trail_name",
            osm_tag="name",
            tier=1,
            completeness=95.0,
            required=False,
        ),
        "trail_number": OSMMapping(
            turrutebasen_field="trail_number",
            osm_tag="ref",
            tier=1,
            completeness=100.0,
            required=False,
        ),
    }

    # Create inference rules (matches the structure from no.toml)
    inference_rules = {
        "gradering": {
            "ST": "hiking",
            "TI": "hiking",
            "LE": "demanding_mountain_hiking",
        },
        "surface": {
            "ST": "ground",
            "TI": "paved",
            "LE": "rock",
        },
    }

    return CountryConfig(
        name="Norway",
        code="NO",
        crs="EPSG:25833",
        bounds={"min_lon": 4.0, "max_lon": 32.0, "min_lat": 57.0, "max_lat": 72.0},
        data_sources=[],
        osm_mappings=osm_mappings,
        inference_rules=inference_rules,
    )


def test_transform_step_name() -> None:
    """Test transform step name generation."""
    step = TransformToOSMStep(country_code="NO")
    assert step.name == "transform-to-osm-no"

    step_se = TransformToOSMStep(country_code="SE")
    assert step_se.name == "transform-to-osm-se"


def test_transform_step_description() -> None:
    """Test transform step description."""
    step = TransformToOSMStep(country_code="NO")
    assert "NO" in step.description
    assert "transform" in step.description.lower()


def test_validate_input_valid_data(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test input validation with valid data."""
    step = TransformToOSMStep(country_code="NO")
    errors = step.validate_input(sample_trail_data)
    assert errors == []


def test_validate_input_empty_spatial() -> None:
    """Test validation with empty spatial data."""
    step = TransformToOSMStep(country_code="NO")
    spatial_gdf = gpd.GeoDataFrame()
    attributes_df = pd.DataFrame({"hiking_trail_fk": ["id1"]})

    errors = step.validate_input((spatial_gdf, attributes_df))
    assert len(errors) > 0
    assert any("empty" in e.lower() for e in errors)


def test_validate_input_missing_columns() -> None:
    """Test validation with missing required columns."""
    step = TransformToOSMStep(country_code="NO")

    # Missing local_id
    spatial_gdf = gpd.GeoDataFrame({"geometry": [LineString([(0, 0), (1, 1)])]})
    attributes_df = pd.DataFrame({"hiking_trail_fk": ["id1"]})

    errors = step.validate_input((spatial_gdf, attributes_df))
    assert any("local_id" in e.lower() for e in errors)


def test_validate_input_orphaned_fks(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test validation with orphaned foreign keys."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    # Add orphaned FK
    new_row = pd.DataFrame({"hiking_trail_fk": ["nonexistent"], "trail_name": ["Orphan"]})
    attributes_df = pd.concat([attributes_df, new_row], ignore_index=True)

    errors = step.validate_input((spatial_gdf, attributes_df))
    assert len(errors) > 0
    assert any("non-existent" in e.lower() for e in errors)


def test_join_data(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test data joining creates correct number of rows."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)

    # Should have 4 rows (trail1 appears twice in attributes)
    assert len(joined) == 4
    assert "local_id" in joined.columns
    assert "hiking_trail_fk" in joined.columns
    assert "trail_name" in joined.columns
    assert "geometry" in joined.columns


def test_join_data_preserves_geometry(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
) -> None:
    """Test that geometry is preserved after join."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)

    # Check that geometries are LineStrings
    assert all(joined.geometry.geom_type == "LineString")


def test_map_to_osm_tags_basic(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
) -> None:
    """Test basic OSM tag mapping."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)
    row = joined.iloc[0]

    tags = step._map_to_osm_tags(row, mock_country_config)

    # Check essential tags
    assert "highway" in tags
    assert tags["highway"] == "path"
    assert "trail_marking" in tags
    assert tags["trail_marking"] == "yes"
    assert "source" in tags
    assert tags["source"] == "Kartverket Turrutebasen"
    assert "ref:geonorge" in tags


def test_map_to_osm_tags_with_inference(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
) -> None:
    """Test OSM tag mapping with inference rules."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)

    # First row has gradering=None, should infer from rutefolger="ST"
    row = joined.iloc[0]
    tags = step._map_to_osm_tags(row, mock_country_config)
    assert "sac_scale" in tags
    assert tags["sac_scale"] == "hiking"
    assert "surface" in tags
    assert tags["surface"] == "ground"


def test_map_to_osm_tags_different_route_types(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
) -> None:
    """Test inference for different route types."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)

    # Trail3 has rutefolger="LE" (cairned route)
    trail3_row = joined[joined["local_id"] == "trail3"].iloc[0]
    tags = step._map_to_osm_tags(trail3_row, mock_country_config)

    assert tags["sac_scale"] == "demanding_mountain_hiking"
    assert tags["surface"] == "rock"


def test_generate_osm_xml_structure(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
    tmp_path: Path,
) -> None:
    """Test that OSM XML has correct structure."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)
    output_path = tmp_path / "test.osm"

    way_count = step._generate_osm_xml(joined, output_path, mock_country_config)

    # Should generate 4 ways (one per joined row)
    assert way_count == 4
    assert output_path.exists()

    # Parse and validate XML
    tree = etree.parse(str(output_path))
    root = tree.getroot()

    assert root.tag == "osm"
    assert root.get("version") == "0.6"


def test_generate_osm_xml_nodes(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
    tmp_path: Path,
) -> None:
    """Test that OSM XML generates correct nodes."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)
    output_path = tmp_path / "test.osm"

    step._generate_osm_xml(joined, output_path, mock_country_config)

    tree = etree.parse(str(output_path))
    root = tree.getroot()

    nodes = root.findall("node")
    # Should have unique nodes (9 total coordinates across 3 trails)
    assert len(nodes) == 9

    # Check node has required attributes
    assert nodes[0].get("id") is not None
    assert nodes[0].get("lat") is not None
    assert nodes[0].get("lon") is not None


def test_generate_osm_xml_ways(
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
    tmp_path: Path,
) -> None:
    """Test that OSM XML generates correct ways."""
    spatial_gdf, attributes_df = sample_trail_data
    step = TransformToOSMStep(country_code="NO")

    joined = step._join_data(spatial_gdf, attributes_df)
    output_path = tmp_path / "test.osm"

    step._generate_osm_xml(joined, output_path, mock_country_config)

    tree = etree.parse(str(output_path))
    root = tree.getroot()

    ways = root.findall("way")
    assert len(ways) == 4

    # Check first way
    way = ways[0]
    assert way.get("id") is not None
    assert way.get("version") == "1"

    # Check way has node references
    nds = way.findall("nd")
    assert len(nds) == 3  # First trail has 3 points

    # Check way has tags
    tags = way.findall("tag")
    assert len(tags) > 0

    # Find specific tags
    tag_dict = {tag.get("k"): tag.get("v") for tag in tags}
    assert "highway" in tag_dict
    assert "source" in tag_dict


@patch("graphhopper_pipeline.steps.transform.load_country_config")
def test_execute_success(
    mock_load_config: MagicMock,
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
    mock_context: PipelineContext,
) -> None:
    """Test successful transformation execution."""
    mock_load_config.return_value = mock_country_config

    step = TransformToOSMStep(country_code="NO")
    result = step.execute(mock_context, sample_trail_data)

    assert result.status == StepStatus.SUCCESS
    assert result.output is not None
    assert result.error is None

    # Check metadata
    assert result.metadata is not None
    assert result.metadata["input_trail_count"] == 3
    assert result.metadata["input_attribute_count"] == 4
    assert result.metadata["joined_count"] == 4
    assert result.metadata["way_count"] == 4
    assert result.metadata["output_format"] in ["xml", "pbf"]

    # Check output file exists
    output_path = result.output
    assert output_path.exists()


@patch("graphhopper_pipeline.steps.transform.load_country_config")
def test_execute_creates_xml_file(
    mock_load_config: MagicMock,
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
    mock_context: PipelineContext,
) -> None:
    """Test that execution creates valid OSM XML file."""
    mock_load_config.return_value = mock_country_config

    step = TransformToOSMStep(country_code="NO")
    result = step.execute(mock_context, sample_trail_data)

    assert result.status == StepStatus.SUCCESS

    # Check OSM XML file exists
    osm_xml = mock_context.work_dir / "trails.osm"
    assert osm_xml.exists()

    # Validate it's valid XML
    tree = etree.parse(str(osm_xml))
    root = tree.getroot()
    assert root.tag == "osm"


@patch("graphhopper_pipeline.steps.transform.load_country_config")
def test_execute_validation_fails(
    mock_load_config: MagicMock,
    mock_context: PipelineContext,
) -> None:
    """Test that execution fails on invalid input."""
    mock_load_config.return_value = MagicMock()

    # Empty data
    spatial_gdf = gpd.GeoDataFrame()
    attributes_df = pd.DataFrame()

    step = TransformToOSMStep(country_code="NO")
    result = step.execute(mock_context, (spatial_gdf, attributes_df))

    assert result.status == StepStatus.FAILED
    assert result.error is not None
    assert "validation failed" in result.error.lower()


def test_convert_to_pbf_osmium_not_available(tmp_path: Path) -> None:
    """Test PBF conversion when osmium is not available."""
    step = TransformToOSMStep(country_code="NO")

    osm_xml = tmp_path / "test.osm"
    osm_xml.write_text('<?xml version="1.0"?><osm version="0.6"></osm>')
    osm_pbf = tmp_path / "test.pbf"

    # Should return False if osmium not available, but not raise exception
    result = step._convert_to_pbf(osm_xml, osm_pbf)

    # Result depends on whether osmium is installed
    assert isinstance(result, bool)


@patch("graphhopper_pipeline.steps.transform.load_country_config")
def test_execute_duration_tracking(
    mock_load_config: MagicMock,
    sample_trail_data: tuple[gpd.GeoDataFrame, pd.DataFrame],
    mock_country_config: CountryConfig,
    mock_context: PipelineContext,
) -> None:
    """Test that execution duration is tracked."""
    mock_load_config.return_value = mock_country_config

    step = TransformToOSMStep(country_code="NO")
    result = step.execute(mock_context, sample_trail_data)

    assert result.duration_seconds is not None
    assert result.duration_seconds >= 0
    assert result.started_at is not None
    assert result.completed_at is not None
    assert result.completed_at >= result.started_at

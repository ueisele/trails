"""Tests for pipeline configuration."""

from pathlib import Path

import pytest

from graphhopper_pipeline.config import (
    CountryConfig,
    OSMMapping,
    PipelineConfig,
    load_country_config,
    load_pipeline_config,
)


def test_load_pipeline_config_default() -> None:
    """Test loading pipeline config from default location."""
    config = load_pipeline_config()

    assert config.name == "graphhopper-trails-pipeline"
    assert config.version == "1.0.0"
    assert config.schedule_cron == "0 6 * * 6"
    assert config.retention_count == 2
    assert config.retry_max_attempts == 5
    assert config.retry_initial_backoff_minutes == 5
    assert config.retry_backoff_multiplier == 2.0
    assert config.retry_max_backoff_minutes == 60
    assert config.max_trail_count_drop_percent == 20.0


def test_load_pipeline_config_custom_path() -> None:
    """Test loading pipeline config from custom path."""
    config_path = Path(__file__).parent.parent / "config" / "pipeline.toml"
    config = load_pipeline_config(config_path)

    assert config.name == "graphhopper-trails-pipeline"


def test_pipeline_config_paths() -> None:
    """Test pipeline config path properties."""
    config = load_pipeline_config()

    assert isinstance(config.output_dir, Path)
    assert isinstance(config.work_dir, Path)
    assert isinstance(config.cache_dir, Path)
    assert config.output_dir == Path("output")
    assert config.work_dir == Path("work")
    assert config.cache_dir == Path(".cache")


def test_load_country_config_norway() -> None:
    """Test loading Norway country config."""
    config = load_country_config("NO")

    assert config.name == "Norway"
    assert config.code == "NO"
    assert config.crs == "EPSG:25833"
    assert config.bounds["min_lon"] == 4.0
    assert config.bounds["max_lon"] == 32.0
    assert config.bounds["min_lat"] == 57.0
    assert config.bounds["max_lat"] == 72.0


def test_load_country_config_case_insensitive() -> None:
    """Test country code is case insensitive."""
    config_upper = load_country_config("NO")
    config_lower = load_country_config("no")

    assert config_upper.name == config_lower.name
    assert config_upper.code == config_lower.code


def test_load_country_config_not_found() -> None:
    """Test loading config for non-existent country."""
    with pytest.raises(FileNotFoundError):
        load_country_config("XX")


def test_country_config_has_data_sources() -> None:
    """Test Norway country config has data sources."""
    config = load_country_config("NO")

    # Just verify data_sources is present (structure varies)
    assert config.data_sources is not None
    assert isinstance(config.data_sources, list)


def test_country_config_has_osm_mappings() -> None:
    """Test Norway country config has OSM mappings."""
    config = load_country_config("NO")

    # Just verify osm_mappings dict is present
    assert config.osm_mappings is not None
    assert isinstance(config.osm_mappings, dict)


def test_country_config_has_inference_rules() -> None:
    """Test Norway country config has inference rules."""
    config = load_country_config("NO")

    # Just verify inference_rules dict is present
    assert config.inference_rules is not None
    assert isinstance(config.inference_rules, dict)


def test_osm_mapping_dataclass() -> None:
    """Test OSMMapping dataclass creation."""
    mapping = OSMMapping(
        turrutebasen_field="test_field",
        osm_tag="test_tag",
        tier=1,
        completeness=95.5,
        required=True,
        values={"A": "B"},
        default="default_value",
    )

    assert mapping.turrutebasen_field == "test_field"
    assert mapping.osm_tag == "test_tag"
    assert mapping.tier == 1
    assert mapping.completeness == 95.5
    assert mapping.required is True
    assert mapping.values == {"A": "B"}
    assert mapping.default == "default_value"


def test_osm_mapping_optional_fields() -> None:
    """Test OSMMapping with optional fields."""
    mapping = OSMMapping(
        turrutebasen_field="test_field",
        osm_tag="test_tag",
        tier=2,
        completeness=50.0,
        required=False,
    )

    assert mapping.values == {}
    assert mapping.default is None

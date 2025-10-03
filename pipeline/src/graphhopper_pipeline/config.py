"""Configuration management for the pipeline."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OSMMapping:
    """Configuration for mapping a Turrutebasen field to OSM tags."""

    turrutebasen_field: str
    osm_tag: str
    tier: int
    completeness: float
    required: bool = False
    values: dict[str, str] = field(default_factory=dict)
    default: str | None = None


@dataclass
class PipelineConfig:
    """Main pipeline configuration."""

    name: str
    version: str
    schedule_cron: str
    output_dir: Path
    work_dir: Path
    cache_dir: Path
    retention_count: int
    max_trail_count_drop_percent: float
    retry_max_attempts: int
    retry_initial_backoff_minutes: int
    retry_backoff_multiplier: float
    retry_max_backoff_minutes: int
    graphhopper_version: str
    graphhopper_profiles: list[str]


@dataclass
class CountryConfig:
    """Country-specific configuration."""

    name: str
    code: str
    crs: str
    bounds: dict[str, float]
    data_sources: list[dict[str, Any]]
    osm_mappings: dict[str, OSMMapping]
    inference_rules: dict[str, dict[str, Any]]
    expected_trail_count: int | None = None


def load_pipeline_config(config_path: Path | None = None) -> PipelineConfig:
    """Load main pipeline configuration.

    Args:
        config_path: Path to pipeline.toml, defaults to pipeline/config/pipeline.toml

    Returns:
        PipelineConfig instance
    """
    if config_path is None:
        # Try to find config relative to this file
        module_dir = Path(__file__).parent  # .../pipeline/src/graphhopper_pipeline
        config_path = module_dir.parent.parent / "config" / "pipeline.toml"

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    pipeline = data["pipeline"]
    storage = pipeline["storage"]
    release = pipeline["release"]
    validation = pipeline["validation"]
    retry = pipeline["retry"]
    graphhopper = data["graphhopper"]

    return PipelineConfig(
        name=pipeline["name"],
        version=pipeline["version"],
        schedule_cron=pipeline["schedule"]["cron"],
        output_dir=Path(storage["output_dir"]),
        work_dir=Path(storage["work_dir"]),
        cache_dir=Path(storage["cache_dir"]),
        retention_count=release["retention_count"],
        max_trail_count_drop_percent=validation["max_trail_count_drop_percent"],
        retry_max_attempts=retry["max_attempts"],
        retry_initial_backoff_minutes=retry["initial_backoff_minutes"],
        retry_backoff_multiplier=retry["backoff_multiplier"],
        retry_max_backoff_minutes=retry["max_backoff_minutes"],
        graphhopper_version=graphhopper["version"],
        graphhopper_profiles=graphhopper["profiles"],
    )


def load_country_config(country_code: str, config_dir: Path | None = None) -> CountryConfig:
    """Load country-specific configuration.

    Args:
        country_code: ISO country code (e.g., "NO", "SE")
        config_dir: Path to config directory, defaults to pipeline/config/

    Returns:
        CountryConfig instance

    Raises:
        FileNotFoundError: If country config doesn't exist
    """
    if config_dir is None:
        # Find config relative to this module
        module_dir = Path(__file__).parent  # .../pipeline/src/graphhopper_pipeline
        config_dir = module_dir.parent.parent / "config"

    country_file = config_dir / "countries" / f"{country_code.lower()}.toml"

    if not country_file.exists():
        raise FileNotFoundError(f"Country configuration not found: {country_file}")

    with open(country_file, "rb") as f:
        data = tomllib.load(f)

    country = data["country"]

    # Parse OSM mappings (simplified - just pass through raw dict for now)
    # TODO: Parse into OSMMapping objects when config structure is finalized
    osm_mappings_raw = data.get("osm_mapping", {})
    osm_mappings = {}
    for tier_name, tier_mappings in osm_mappings_raw.items():
        if isinstance(tier_mappings, dict):
            for field, tag in tier_mappings.items():
                osm_mappings[field] = OSMMapping(
                    turrutebasen_field=field,
                    osm_tag=tag,
                    tier=1 if tier_name == "essential" else 2 if tier_name == "recommended" else 3,
                    completeness=100.0,  # Placeholder
                    required=(tier_name == "essential"),
                )

    # Parse data sources (convert from nested dict to list)
    data_sources_raw = data.get("data_sources", {})
    data_sources = [{"type": k, **v} for k, v in data_sources_raw.items()]

    return CountryConfig(
        name=country["name"],
        code=country["code"],
        crs=country["crs"],
        bounds=country["bounds"],
        data_sources=data_sources,
        osm_mappings=osm_mappings,
        inference_rules=data.get("inference", {}),
        expected_trail_count=country.get("expected_trail_count"),
    )

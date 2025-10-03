"""Configuration management for the pipeline."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    data_sources: dict[str, Any]
    osm_mapping: dict[str, Any]
    inference: dict[str, Any]


def load_pipeline_config(config_path: Path | None = None) -> PipelineConfig:
    """Load main pipeline configuration.

    Args:
        config_path: Path to pipeline.toml, defaults to pipeline/config/pipeline.toml

    Returns:
        PipelineConfig instance
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "pipeline.toml"

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
        config_dir = Path(__file__).parent.parent.parent / "config"

    country_file = config_dir / "countries" / f"{country_code.lower()}.toml"

    if not country_file.exists():
        raise FileNotFoundError(f"Country configuration not found: {country_file}")

    with open(country_file, "rb") as f:
        data = tomllib.load(f)

    country = data["country"]

    return CountryConfig(
        name=country["name"],
        code=country["code"],
        crs=country["crs"],
        bounds=country["bounds"],
        data_sources=data.get("data_sources", {}),
        osm_mapping=data.get("osm_mapping", {}),
        inference=data.get("inference", {}),
    )

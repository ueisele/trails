"""Abstract base classes for trail data sources.

This module defines the interfaces that all trail data sources must implement,
enabling consistent data access across different countries and providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd


@dataclass(frozen=True)
class SourceMetadata:
    """Metadata about a trail data source.

    Attributes:
        name: Human-readable name of the source
        provider: Organization providing the data
        country: ISO 3166-1 alpha-2 country code (e.g., "NO", "SE")
        url: Base URL for the data source
        license: License information
        update_frequency: How often data is updated (e.g., "weekly", "monthly")
        description: Brief description of the data source
    """

    name: str
    provider: str
    country: str
    url: str
    license: str
    update_frequency: str
    description: str


@dataclass(frozen=True)
class DatasetInfo:
    """Information about a specific dataset version.

    Attributes:
        version: Version identifier (e.g., date, version number)
        released: Release date of this dataset version
        checksum: MD5/SHA256 checksum if available
        size_bytes: Size of the dataset in bytes
        format: Data format (e.g., "GeoPackage", "Shapefile", "GeoJSON")
        download_url: URL to download this specific version
    """

    version: str
    released: datetime
    checksum: str | None = None
    size_bytes: int | None = None
    format: str | None = None
    download_url: str | None = None


class TrailDataSource(ABC):
    """Abstract base class for trail data sources.

    All trail data sources (Geonorge, Lantmäteriet, OpenStreetMap, etc.)
    should inherit from this class and implement its methods.

    This enables the pipeline to work with different data sources
    in a consistent way.
    """

    @property
    @abstractmethod
    def metadata(self) -> SourceMetadata:
        """Get metadata about this data source.

        Returns:
            SourceMetadata describing the source
        """
        pass

    @abstractmethod
    def check_for_updates(self) -> DatasetInfo | None:
        """Check if a new version of the dataset is available.

        Returns:
            DatasetInfo for the latest version, or None if unavailable
        """
        pass

    @abstractmethod
    def download(self, output_path: Path, version: str | None = None) -> Path:
        """Download trail data to a local path.

        Args:
            output_path: Where to save the downloaded data
            version: Specific version to download, or None for latest

        Returns:
            Path to the downloaded file

        Raises:
            ValueError: If the version doesn't exist
            IOError: If download fails
        """
        pass

    @abstractmethod
    def load_trails(self, data_path: Path) -> gpd.GeoDataFrame:
        """Load trail geometries from downloaded data.

        Args:
            data_path: Path to the downloaded data file

        Returns:
            GeoDataFrame with trail geometries and standardized columns:
                - geometry: Trail linestrings (EPSG:4326)
                - trail_id: Unique identifier for each trail segment
                - trail_name: Name of the trail (if available)
                - Additional source-specific columns

        Raises:
            FileNotFoundError: If data_path doesn't exist
            ValueError: If data format is invalid
        """
        pass

    @abstractmethod
    def load_attributes(self, data_path: Path) -> pd.DataFrame:
        """Load trail attributes from downloaded data.

        Args:
            data_path: Path to the downloaded data file

        Returns:
            DataFrame with trail attributes indexed by trail_id

        Raises:
            FileNotFoundError: If data_path doesn't exist
            ValueError: If data format is invalid
        """
        pass

    def validate_data(self, trails: gpd.GeoDataFrame, attributes: pd.DataFrame) -> list[str]:
        """Validate loaded data for common issues.

        Args:
            trails: GeoDataFrame from load_trails()
            attributes: DataFrame from load_attributes()

        Returns:
            List of validation warnings/errors (empty if no issues)
        """
        issues: list[str] = []

        # Check for required columns
        if "trail_id" not in trails.columns:
            issues.append("Missing required column: trail_id")
        if "geometry" not in trails.columns:
            issues.append("Missing required column: geometry")

        # Check for null geometries
        null_geoms = trails.geometry.isna().sum()
        if null_geoms > 0:
            issues.append(f"{null_geoms} trails have null geometries")

        # Check for invalid geometries
        invalid_geoms = (~trails.geometry.is_valid).sum()
        if invalid_geoms > 0:
            issues.append(f"{invalid_geoms} trails have invalid geometries")

        # Check CRS
        if trails.crs is None:
            issues.append("GeoDataFrame has no CRS defined")
        elif trails.crs.to_epsg() != 4326:
            issues.append(f"Expected EPSG:4326, got {trails.crs.to_epsg()}")

        # Check for duplicate IDs
        if "trail_id" in trails.columns:
            duplicate_ids = trails["trail_id"].duplicated().sum()
            if duplicate_ids > 0:
                issues.append(f"{duplicate_ids} duplicate trail_ids found")

        return issues


class CachedTrailDataSource(TrailDataSource):
    """Base class for data sources with caching support.

    Provides common caching functionality that can be reused
    by concrete implementations.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize cached data source.

        Args:
            cache_dir: Directory for caching downloaded data.
                      Defaults to .cache/{source_name}/
        """
        self._cache_dir = cache_dir or Path(".cache") / self.metadata.name.lower().replace(" ", "_")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_dir(self) -> Path:
        """Get the cache directory path."""
        return self._cache_dir

    def get_cached_path(self, version: str) -> Path:
        """Get the expected path for a cached version.

        Args:
            version: Dataset version identifier

        Returns:
            Path where this version should be cached
        """
        return self.cache_dir / f"data_{version}.gpkg"

    def is_cached(self, version: str) -> bool:
        """Check if a version is already cached.

        Args:
            version: Dataset version identifier

        Returns:
            True if this version exists in cache
        """
        return self.get_cached_path(version).exists()

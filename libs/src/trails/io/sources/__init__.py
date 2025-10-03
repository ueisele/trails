"""Trail data sources (Geonorge, OpenStreetMap, etc.)."""

from . import geonorge
from .base import CachedTrailDataSource, DatasetInfo, SourceMetadata, TrailDataSource

__all__ = [
    "geonorge",
    "TrailDataSource",
    "CachedTrailDataSource",
    "SourceMetadata",
    "DatasetInfo",
]

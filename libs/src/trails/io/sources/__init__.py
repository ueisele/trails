"""Trail data sources (Geonorge, Naturbase, OpenStreetMap, etc.)."""

from . import geonorge, geonorge_order, kommuneinfo, n50, naturbase, overpass, stedsnavn, traktorvegsti
from .base import CachedTrailDataSource, DatasetInfo, SourceMetadata, TrailDataSource

__all__ = [
    "geonorge",
    "geonorge_order",
    "kommuneinfo",
    "n50",
    "naturbase",
    "overpass",
    "stedsnavn",
    "traktorvegsti",
    "TrailDataSource",
    "CachedTrailDataSource",
    "SourceMetadata",
    "DatasetInfo",
]

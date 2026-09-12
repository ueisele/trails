"""Trail data sources (Geonorge, Naturbase, OpenStreetMap, etc.)."""

from . import (
    geonorge,
    geonorge_order,
    hoydedata,
    kommuneinfo,
    lantmateriet,
    markhojd,
    n50,
    naturbase,
    naturkartan,
    naturvardsregistret,
    ortnamn,
    overpass,
    stedsnavn,
    topografi50,
    traktorvegsti,
    ut,
)
from .base import CachedTrailDataSource, DatasetInfo, SourceMetadata, TrailDataSource

__all__ = [
    "geonorge",
    "geonorge_order",
    "hoydedata",
    "kommuneinfo",
    "lantmateriet",
    "markhojd",
    "n50",
    "naturbase",
    "naturkartan",
    "naturvardsregistret",
    "ortnamn",
    "overpass",
    "stedsnavn",
    "topografi50",
    "traktorvegsti",
    "ut",
    "TrailDataSource",
    "CachedTrailDataSource",
    "SourceMetadata",
    "DatasetInfo",
]

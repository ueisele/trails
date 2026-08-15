"""Assembling a routable network out of the national datasets.

:mod:`trails.routing` is the algorithm and knows nothing about where lines come
from; this package is the composition, and knows which datasets go in. Keeping
them apart is what lets the pipeline drive the same graph builder from its own
sources, and what lets the map and the graph report share one cached build.

    >>> from trails.network.norway import Params, build, load_sources, masks_from, zone_around
"""

from trails.network.norway import (
    COST_FACTORS,
    FERRIES,
    FKB,
    MARKED_M,
    METRIC_CRS,
    MIN_SHARE,
    N50_PATHS,
    N50_ROADS,
    OSM,
    PLACEHOLDER_IDENTITIES,
    RECORDED_M,
    RECORDED_SOURCES,
    ROUTE_REGISTERS,
    SOURCE_NAMES,
    SURVEY_FIELD,
    SURVEYED_FIELD,
    TURRUTEBASEN,
    UT,
    Loaded,
    Masks,
    Params,
    build,
    derive,
    fingerprint,
    load_sources,
    masks_from,
    zone_around,
)

__all__ = [
    "COST_FACTORS",
    "FERRIES",
    "FKB",
    "MARKED_M",
    "METRIC_CRS",
    "MIN_SHARE",
    "N50_PATHS",
    "N50_ROADS",
    "OSM",
    "PLACEHOLDER_IDENTITIES",
    "RECORDED_M",
    "RECORDED_SOURCES",
    "ROUTE_REGISTERS",
    "SOURCE_NAMES",
    "SURVEYED_FIELD",
    "SURVEY_FIELD",
    "TURRUTEBASEN",
    "UT",
    "Loaded",
    "Masks",
    "Params",
    "build",
    "derive",
    "fingerprint",
    "load_sources",
    "masks_from",
    "zone_around",
]

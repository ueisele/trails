"""Build a routable network out of several line datasets.

Free of any one park, of Folium and of the browser: it takes named
GeoDataFrames and a clipping geometry, and returns chains and edges. Choosing
the extent, loading the sources and drawing anything stay with the caller, which
is what lets both the map and the pipeline build on the same network.

    >>> from trails.routing import NetworkSource, build_network
    >>> network = build_network([NetworkSource("FKB", paths), NetworkSource("N50", roads, cost_factor=1.3)], clip=zone)
    >>> len(network.chains), len(network.edges)
"""

from trails.routing.chains import (
    DEFAULT_PROBE_M,
    DEFAULT_STROKE_ANGLE_DEG,
    ChainRule,
    build_chains,
    chains_of,
    split_source,
)
from trails.routing.coverage import (
    DEFAULT_MARKED_M,
    DEFAULT_MIN_SHARE,
    DEFAULT_RECORDED_M,
    MARKED,
    UNKNOWN,
    UNMARKED,
    no_path_recorded,
    share_within,
    waymarked,
)
from trails.routing.graph import (
    DEFAULT_BRIDGE_COST_FACTOR,
    DEFAULT_BRIDGE_M,
    DEFAULT_FERRY_COST_M,
    Network,
    build_network,
    label_components,
)
from trails.routing.noding import DEFAULT_METRIC_CRS, NODE_TOLERANCE_M
from trails.routing.sources import BRIDGE, FERRY, PATH, NetworkSource

__all__ = [
    "BRIDGE",
    "DEFAULT_BRIDGE_COST_FACTOR",
    "DEFAULT_BRIDGE_M",
    "DEFAULT_FERRY_COST_M",
    "DEFAULT_MARKED_M",
    "DEFAULT_METRIC_CRS",
    "DEFAULT_MIN_SHARE",
    "DEFAULT_PROBE_M",
    "DEFAULT_RECORDED_M",
    "DEFAULT_STROKE_ANGLE_DEG",
    "FERRY",
    "MARKED",
    "NODE_TOLERANCE_M",
    "PATH",
    "UNKNOWN",
    "UNMARKED",
    "ChainRule",
    "Network",
    "NetworkSource",
    "build_chains",
    "build_network",
    "chains_of",
    "label_components",
    "no_path_recorded",
    "share_within",
    "split_source",
    "waymarked",
]

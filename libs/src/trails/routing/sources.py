"""What the routing module needs to know about one line dataset.

A source is a GeoDataFrame plus the handful of decisions that cannot be read off
the geometry: what a route costs on it, whether its features are already the unit
a reader selects, and which column, if any, says that two lines are the same way.
"""

from dataclasses import dataclass, field

import geopandas as gpd

#: An ordinary walkable line: path, track or road.
PATH = "path"

#: A crossing by boat. Routable, but never walked, so it is weighted and reported
#: apart from everything else and carries no elevation.
FERRY = "ferry"

#: A connector inferred between two loose ends that lie close together. It has no
#: chain, because no source ever drew it.
BRIDGE = "bridge"


@dataclass(frozen=True)
class NetworkSource:
    """One dataset going into the network.

    Attributes:
        name: Short tag carried on every chain and edge built from this dataset,
            e.g. ``"FKB"``. Also the prefix of its chain ids, so keep it stable.
        gdf: The lines themselves. All sources of one build must share a CRS.
        cost_factor: Multiplies an edge's length to give its cost, so a route
            prefers a better-surveyed line where the detour is small. Keep close
            to 1.0: a large factor buys real detours.
        kind: :data:`PATH` or :data:`FERRY`.
        identity_field: Column saying that two lines are the same named or
            registered way — a road id, a route name. Several identities in one
            value are separated by ``" / "``, as the road and trail layers
            already write them.
        attributes: Columns carried through onto the chain. A value constant
            along the chain passes through; values that differ are joined.
        keep_whole: The source publishes whole routes, and a route is already
            linear. Its features become chains untouched, rather than being cut
            at every crossing and chained back together.
        node_simplify_m: Tolerance for a simplified copy used **only** when
            noding this source against the others. Raw GPS density otherwise
            shatters every line such a track runs along. The chain and the edges
            keep the full geometry.
    """

    name: str
    gdf: gpd.GeoDataFrame
    cost_factor: float = 1.0
    kind: str = PATH
    identity_field: str | None = None
    attributes: tuple[str, ...] = field(default=())
    keep_whole: bool = False
    node_simplify_m: float = 0.0

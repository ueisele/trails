"""Short, path-priced carries from a road or path to the paddle shore."""

from typing import TYPE_CHECKING, Any

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString, Point

from trails.routing.graph import Network
from trails.routing.noding import NODE_TOLERANCE_M
from trails.routing.sources import LAUNCH, PATH, NetworkSource

if TYPE_CHECKING:
    from trails.network.water import Access

LAUNCHES = "Launches"
LAUNCH_M = 30.0
#: The three-map sweep finds 74% as many new access points as 50 m spacing with 28% fewer ties.
SHORE_SPACING_M = 100.0


def launches(sources: list[NetworkSource], walking: Network, access: Access, *, spacing_m: float = SHORE_SPACING_M) -> NetworkSource:
    """Join dead ends and nearby passing paths to the shore over land only.

    Dead ends have priority over passing paths. Passing candidates are ordered
    by gap, then geometry, so overlapping road sources cannot decide which
    landing survives. Spacing follows the shore, including around closed rings.

    Args:
        sources: Walking and paddle sources, before inferred launch ties
        walking: Noded walking network, in a metric CRS
        access: Unsimplified source water and dam points
        spacing_m: Minimum shore distance between a passing landing and prior access

    Returns:
        Kayak-only lines with their origin recorded for the build measurements
    """
    from trails.network.water import DAM_CUT_M, SHORE

    crs = walking.edges.crs
    if crs is None or not crs.is_projected:
        raise ValueError("launches need a projected walking network")
    if spacing_m <= 0:
        raise ValueError("launch spacing must be positive")
    shore_arrays = [s.gdf.to_crs(crs).geometry.to_numpy() for s in sources if s.name == SHORE]
    shore = np.concatenate(shore_arrays) if shore_arrays else np.empty(0, dtype=object)
    banks = shapely.get_parts(shapely.line_merge(shapely.union_all(shore)))
    banks = np.array([line for line in banks if isinstance(line, LineString)], dtype=object)
    segments, bank_ids = [], []
    for bank, line in enumerate(banks):
        # A long straight bank still needs passing access along its length.
        # Subdivision chooses candidates without changing the shore geometry.
        coords = list(shapely.segmentize(line, spacing_m).coords)
        for one, other in zip(coords[:-1], coords[1:], strict=True):
            segments.append(LineString([one, other]))
            bank_ids.append(bank)
    shores = shapely.STRtree(segments)
    # The same centimetre grid closes delivery seams in the paddle builder.
    water = shapely.set_precision(shapely.force_2d(access.surfaces.to_crs(crs).geometry.to_numpy()), NODE_TOLERANCE_M)
    obstacles = shapely.STRtree(water)
    dam_points = access.dams.to_crs(crs).geometry.to_numpy() if access.dams is not None else np.empty(0, dtype=object)
    dams = shapely.STRtree(dam_points)
    drawn = walking.edges[walking.edges["kind"].eq(PATH)]
    path_nodes = set(drawn[["from_node", "to_node"]].to_numpy().ravel())
    ends = sorted(node for node in path_nodes if walking.nodes["degree"].iloc[node] == 1)
    candidates: list[tuple[str, LineString, int]] = []
    for node in ends:
        point = walking.nodes.geometry.iloc[node]
        nearest = shores.query_nearest(point, max_distance=LAUNCH_M, all_matches=False)
        if len(nearest):
            segment = int(nearest[0])
            candidates.append(("dead end", shapely.shortest_line(point, segments[segment]), bank_ids[segment]))
    # One gap per shore segment and road edge also finds a road running beside
    # a long bank; one nearest point for the whole lake would miss that access.
    road_lines = drawn.geometry.to_numpy()
    pairs = shores.query(road_lines, predicate="dwithin", distance=LAUNCH_M)
    for road, segment in pairs.T:
        candidates.append(("passing", shapely.shortest_line(road_lines[road], segments[segment]), bank_ids[segment]))
    candidates.sort(key=lambda item: (item[0] != "dead end", item[1].length, tuple(item[1].coords), item[2]))
    occupied: dict[int, list[float]] = {}
    # A road already meeting this bank needs no new landing beside its junction.
    for road, segment in pairs.T:
        crossing = road_lines[road].intersection(segments[segment])
        for point in shapely.get_parts(crossing):
            if isinstance(point, Point):
                bank = bank_ids[segment]
                occupied.setdefault(bank, []).append(float(banks[bank].project(point)))
    kept: list[dict[str, Any]] = []
    seen: set[bytes] = set()
    rejected_water = rejected_dam = spaced = 0
    for origin, tie, bank in candidates:
        if tie.length <= NODE_TOLERANCE_M or tie.length > LAUNCH_M:
            continue
        key = shapely.normalize(tie).wkb
        if key in seen:
            continue
        seen.add(key)
        foot = Point(tie.coords[0])
        nearest_segment = shores.nearest(foot)
        if nearest_segment is None or foot.distance(segments[int(nearest_segment)]) + NODE_TOLERANCE_M < tie.length:
            continue
        end = Point(tie.coords[-1])
        along = float(banks[bank].project(end))
        distances = [abs(along - previous) for previous in occupied.get(bank, [])]
        if banks[bank].is_ring:
            distances = [min(distance, banks[bank].length - distance) for distance in distances]
        if distances and min(distances) < (spacing_m if origin == "passing" else NODE_TOLERANCE_M):
            spaced += 1
            continue
        if len(dams.query(tie, predicate="dwithin", distance=DAM_CUT_M)):
            rejected_dam += 1
            continue
        hits = obstacles.query(tie, predicate="intersects")
        # Reprojection can put the shore end a fraction of the noding quantum
        # inside its original polygon. No resolvable wet interval is a launch.
        if len(hits) and tie.intersection(shapely.union_all(water[hits])).length > NODE_TOLERANCE_M:
            rejected_water += 1
            continue
        kept.append({"origin": origin, "shore": bank, "shore_m": along, "geometry": tie})
        occupied.setdefault(bank, []).append(along)
    frame = gpd.GeoDataFrame(kept, columns=["origin", "shore", "shore_m", "geometry"], crs=crs)
    lengths = frame.length
    print(
        f"  Launches: {len(frame):,}; {sum(frame['origin'].eq('dead end')):,} dead ends, "
        f"{sum(frame['origin'].eq('passing')):,} passing; {lengths.sum():.3f} m; "
        f"{spaced:,} spaced, {rejected_water:,} wet, {rejected_dam:,} at dams"
    )
    if len(frame):
        print(f"  Launch metres min/median/p95/max: {lengths.min():.3f}/{lengths.median():.3f}/{lengths.quantile(0.95):.3f}/{lengths.max():.3f}")
    return NetworkSource(LAUNCHES, frame, kind=LAUNCH, keep_whole=True)

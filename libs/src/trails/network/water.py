"""The shore, open water, streams and the ground joining separate water bodies."""

import re
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import substring

from trails.network import graphs
from trails.routing.coverage import CHAIN_COVERAGE_COLUMNS, chain_coverage
from trails.routing.elevation import PROFILE_COLUMNS, chain_profiles
from trails.routing.graph import DEFAULT_BRIDGE_COST_FACTOR, Network, build_network
from trails.routing.noding import lines_of, working_lines
from trails.routing.sources import BRIDGE, PADDLE, PATH, PORTAGE, NetworkSource

SHORE = "Shore"
OPEN_WATER = "Open water"
STREAMS = "Streams"
PORTAGES = "Portages"
PORTAGE_PATHS = "Portage paths"
WATER_SOURCES = (SHORE, OPEN_WATER, STREAMS)
#: Phase 9's 5 m tolerance sweep: shore p95 deviation 3.4–3.5 m, page growth 0.37–0.81 MB Brotli.
#: Review accepted the sweep’s 8.4–32.5 % p95 search growth after phase 8.
SHORE_SIMPLIFY_M = 5.0
#: Ponds stay in the pricing grid; their shores are not places to plan a kayak trip.
MIN_PADDLE_HA = 1.0
#: Phase 2 measured 1.5: the bay is cut and the lake keeps its shore; the graph is rebuilt in phase 5.
OPEN_WATER_FACTOR = 1.5
PORTAGE_M = 1000.0
PATH_JOIN_M = 150.0
DAM_CUT_M = 25.0
DAM_NEAR_M = 25.0
#: Phase 7's chain measurement opens 173 level chains / 282 edges / 46.9 km
#: in Malingsbo-Kloten and 35 / 44 / 2.2 km in Abisko. Whole chains keep
#: noding from opening locally flat pieces of a falling stream.
#: Rising chains also open; the sampled heights do not establish opposite flow.
LEVEL_FALL_M = 0.3
LEVEL_GRADIENT = 0.001
LAKE_BODY = "lake_body"
LAKE_LEVEL = "lake_level"
SURFACE_CLASS = "water_class"


def _registered_level(value: Any) -> float:
    """A register's interval takes its lower level, like conflicting sheets."""
    if pd.isna(value):
        return np.nan
    text = str(value).strip().replace(",", ".")
    interval = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)", text)
    return min(float(interval[1]), float(interval[2])) if interval else float(text)


def sources(
    surfaces: gpd.GeoDataFrame,
    *,
    metric_crs: str,
    class_field: str | None = None,
    lake_classes: tuple[str, ...] = (),
    level_field: str | None = None,
    streams: gpd.GeoDataFrame | None = None,
    dams: gpd.GeoDataFrame | None = None,
    extent: gpd.GeoDataFrame | None = None,
) -> list[NetworkSource]:
    """Turn water outlines and classed stream lines into paddled sources.

    Args:
        surfaces: Water polygons, with delivery pieces retained until dissolution
        metric_crs: Projection in which the tolerances are metres
        class_field: Surface classification column, or None when all surfaces are lakes
        lake_classes: Values of that column identifying lakes, including regulated lakes
        level_field: Registered height column, or None when no levels are supplied
        streams: Stream lines carrying ``storleksklass``, or None
        dams: Dam points and lock gates, or None where streams are absent
        extent: Map boundary, cut after dissolution so it cannot become shore

    Returns:
        Shore and open-water sources, and directed streams when supplied
    """
    if surfaces.crs is None:
        raise ValueError("water surfaces need a coordinate reference system")
    source_crs = surfaces.crs
    started = time.perf_counter()
    shore: list[dict[str, Any]] = []
    chords: list[dict[str, Any]] = []
    lake_interfaces: list[LineString] = []
    groups, boundary = _dissolved(surfaces.to_crs(metric_crs), class_field, lake_classes, level_field)
    window = extent.to_crs(metric_crs).union_all() if extent is not None else None
    for attributes, whole in groups:
        clipped = whole.intersection(window) if window is not None else whole
        for original in shapely.get_parts(clipped):
            if not isinstance(original, Polygon) or original.is_empty:
                continue
            # The lake/river interface still carries a change of height
            # semantics, but neither that interface nor a map crop is shore.
            banks = _boundary_lines(original.boundary.intersection(boundary))
            seams = _boundary_lines(original.boundary.difference(boundary))
            simplified = list(shapely.get_parts(shapely.MultiLineString([*banks, *seams]).simplify(SHORE_SIMPLIFY_M)))
            banks, seams = simplified[: len(banks)], simplified[len(banks) :]
            surface = shapely.build_area(shapely.union_all([*banks, *seams]))
            if surface.is_empty:
                raise ValueError("simplified water boundary encloses no surface")
            shore.extend({**attributes, "geometry": line} for line in banks)
            bank_edges = {
                tuple(sorted((one[:2], other[:2])))
                for line in banks
                for one, other in zip(list(line.coords)[:-1], list(line.coords)[1:], strict=True)
            }
            candidates = shapely.get_parts(shapely.delaunay_triangles(surface, only_edges=True))
            shapely.prepare(surface)
            emitted = set()
            for line in candidates[shapely.covers(surface, candidates)]:
                key = tuple(sorted(line.coords))
                if key not in bank_edges:
                    chords.append({**attributes, "geometry": line})
                    emitted.add(key)
            if attributes[LAKE_BODY] is not None:
                # An unconstrained triangulation need not retain every
                # concave boundary segment. The mouth must survive once
                # its coincident river copy is removed below.
                for seam in seams:
                    for one, other in zip(list(seam.coords)[:-1], list(seam.coords)[1:], strict=True):
                        if tuple(sorted((one, other))) not in emitted:
                            chords.append({**attributes, "geometry": LineString((one, other))})
                lake_interfaces.extend(seams)
    # Both polygons triangulate their shared mouth. Its lake copy carries
    # the lake plane; retaining the river copy makes the profile depend on
    # which equally priced edge the search happens to choose.
    interfaces = shapely.STRtree(lake_interfaces)
    owned: list[dict[str, Any]] = []
    for row in chords:
        line = row["geometry"]
        hits = interfaces.query(line, predicate="intersects") if row[LAKE_BODY] is None else np.empty(0, dtype=int)
        if len(hits):
            line = line.difference(shapely.union_all(interfaces.geometries[hits]))
        owned.extend({**row, "geometry": piece} for piece in _boundary_lines(line))
    chords = owned
    cut = None
    if streams is not None:
        if dams is None:
            raise ValueError("stream lines need the dam and lock-gate layer")
        cut = cut_streams(streams, dams, metric_crs=metric_crs)
        _join_streams(cut, shore, chords, groups)
    if dams is not None and len(dams):
        # Cut the finished lines, not the polygon before triangulation: an
        # artificial bank around a structure must not become a paddled shore.
        tree = shapely.STRtree(dams.to_crs(metric_crs).geometry.to_numpy())
        counts = []
        for rows in (shore, chords):
            kept: list[dict[str, Any]] = []
            changed = 0
            for row in rows:
                line = row["geometry"]
                pieces = _outside_dams(line, tree)
                changed += int(len(pieces) != 1 or not pieces[0].equals(line))
                kept.extend({**row, "geometry": piece} for piece in pieces)
            rows[:] = kept
            counts.append(changed)
        print(f"  Dam discs: {len(tree.geometries):,}; cut {counts[0]:,} shore lines and {counts[1]:,} open-water chords")
    result = [
        NetworkSource(
            name,
            gpd.GeoDataFrame(rows, columns=[LAKE_BODY, LAKE_LEVEL, SURFACE_CLASS, "geometry"], crs=metric_crs).to_crs(source_crs),
            kind=PADDLE,
            cost_factor=factor,
            keep_whole=True,
            attributes=(LAKE_BODY, LAKE_LEVEL, SURFACE_CLASS),
        )
        for name, rows, factor in ((SHORE, shore, 1.0), (OPEN_WATER, chords, OPEN_WATER_FACTOR))
    ]
    print(
        f"  Water outlines and triangulation: {time.perf_counter() - started:.3f} s; "
        f"{len(chords):,} open-water chords, {sum(row['geometry'].length for row in chords) / 1000:.3f} km"
    )
    if cut is not None:
        result.append(NetworkSource(STREAMS, cut.to_crs(source_crs), kind=PADDLE, directed=True, keep_whole=True))
    return result


def _outside_dams(line: LineString, tree: shapely.STRtree) -> list[LineString]:
    """Clip at analytic circle intersections without a polygon's inset chords."""
    hits = tree.query(line, predicate="dwithin", distance=DAM_CUT_M)
    if not len(hits):
        return [line]
    coordinates = np.asarray(line.coords)[:, :2]
    intervals = []
    along = 0.0
    for one, other in zip(coordinates[:-1], coordinates[1:], strict=True):
        delta = other - one
        squared = float(delta @ delta)
        length = np.sqrt(squared)
        if not length:
            continue
        for point in tree.geometries[hits]:
            offset = one - np.array(point.coords[0][:2])
            b = float(offset @ delta)
            discriminant = b * b - squared * (float(offset @ offset) - DAM_CUT_M**2)
            if discriminant <= 0:
                continue
            root = np.sqrt(discriminant)
            start, end = max(0.0, (-b - root) / squared), min(1.0, (-b + root) / squared)
            if start < end:
                intervals.append((along + start * length, along + end * length))
        along += length
    kept = []
    previous = 0.0
    for start, end in sorted(intervals):
        if start > previous:
            piece = substring(line, previous, start)
            assert isinstance(piece, LineString)
            kept.append(piece)
        previous = max(previous, end)
    if previous < line.length:
        piece = substring(line, previous, line.length)
        assert isinstance(piece, LineString)
        kept.append(piece)
    return kept


def _join_streams(
    streams: gpd.GeoDataFrame,
    shore: list[dict[str, Any]],
    chords: list[dict[str, Any]],
    groups: list[tuple[dict[str, Any], BaseGeometry]],
) -> None:
    """Join stream pieces enclosed by finer water but missed by its chords."""
    rows = shore + chords
    if not rows or streams.empty:
        return
    tree = shapely.STRtree([row["geometry"] for row in rows])
    surfaces = shapely.STRtree([surface for _, surface in groups])
    added = 0
    for line in streams.geometry:
        if len(tree.query(line, predicate="intersects")):
            continue
        for point in (Point(line.coords[0]), Point(line.coords[-1])):
            bodies = surfaces.query(point, predicate="intersects")
            if not len(bodies):
                continue
            nearest = int(tree.nearest(point))
            join = shapely.shortest_line(point, tree.geometries[nearest])
            if join.length and shapely.union_all(surfaces.geometries[bodies]).covers(join):
                # A projected point on a segment need not lie exactly on that
                # segment after both are reprojected. Give both sources the
                # same vertex so this is a junction, not a tiny inferred carry.
                target = rows[nearest]["geometry"]
                meeting = Point(join.coords[-1])
                along = target.project(meeting)
                if 0 < along < target.length:
                    head, tail = substring(target, 0, along), substring(target, along, target.length)
                    rows[nearest]["geometry"] = LineString([*head.coords[:-1], meeting.coords[0], *tail.coords[1:]])
                chords.append({**rows[nearest], "geometry": join})
                added += 1
    print(f"  Stream ends inside surface water: {added:,} open-water joins")


def _boundary_lines(geometry: BaseGeometry) -> list[LineString]:
    """Keep adjoining boundary pieces together before simplifying their banks."""
    parts = [part for part in shapely.get_parts(geometry) if isinstance(part, LineString) and part.length > 0]
    return [part for part in shapely.get_parts(shapely.line_merge(shapely.MultiLineString(parts))) if isinstance(part, LineString)]


def _dissolved(
    metric: gpd.GeoDataFrame, class_field: str | None, lake_classes: tuple[str, ...], level_field: str | None
) -> tuple[list[tuple[dict[str, Any], BaseGeometry]], BaseGeometry]:
    """Dissolve deliveries without merging the lake planes through river surfaces."""
    # The shore investigation used a centimetre grid to close reprojection
    # cracks between deliveries; it is finer than the page's coordinate quantum.
    polygons, parents = shapely.get_parts(shapely.set_precision(shapely.force_2d(metric.geometry.to_numpy()), 0.01), return_index=True)
    valid = np.array([isinstance(p, Polygon) and not p.is_empty for p in polygons], dtype=bool)
    polygons, parents = polygons[valid], parents[valid]
    labels = _components(len(polygons), shapely.STRtree(polygons).query(polygons, predicate="intersects"))
    eligible = {label for label in np.unique(labels) if shapely.union_all(polygons[labels == label]).area >= MIN_PADDLE_HA * 10_000}
    keep = np.isin(labels, list(eligible))
    polygons, parents = polygons[keep], parents[keep]
    if not len(polygons):
        return [], LineString()
    # The delivery grid closes seams; subsequent clipping must keep its exact
    # intersection points rather than round the two sides of a cut separately.
    polygons = shapely.set_precision(polygons, 0)
    boundary = shapely.union_all(polygons).boundary
    classes = metric[class_field].to_numpy()[parents] if class_field else np.full(len(polygons), None, dtype=object)
    is_lake = np.ones(len(polygons), dtype=bool) if class_field is None else np.isin(classes, lake_classes)
    levels = metric[level_field].map(_registered_level).to_numpy(dtype=float)[parents] if level_field else np.full(len(polygons), np.nan)
    lakes = polygons[is_lake]
    lake_labels = _components(len(lakes), shapely.STRtree(lakes).query(lakes, predicate="intersects"))
    groups: list[tuple[dict[str, Any], BaseGeometry]] = []
    for label in np.unique(lake_labels):
        own = lake_labels == label
        registered = levels[is_lake][own]
        finite = registered[np.isfinite(registered)]
        groups.append(
            (
                {LAKE_BODY: f"lake-{label}", LAKE_LEVEL: float(finite.min()) if len(finite) else np.nan, SURFACE_CLASS: classes[is_lake][own][0]},
                shapely.union_all(lakes[own]),
            )
        )
    for kind in pd.unique(classes[~is_lake]):
        groups.append(({LAKE_BODY: None, LAKE_LEVEL: np.nan, SURFACE_CLASS: kind}, shapely.union_all(polygons[(classes == kind) & ~is_lake])))
    return groups, boundary


def cut_streams(streams: gpd.GeoDataFrame, dams: gpd.GeoDataFrame, *, metric_crs: str) -> gpd.GeoDataFrame:
    """Cut class-2 streams around dams, retaining their digitised direction.

    Args:
        streams: Lines with Topografi 50's text ``storleksklass`` column
        dams: Dam and lock-gate points
        metric_crs: Projection in which the cuts are metres

    Returns:
        Stream pieces outside the merged dam intervals, in the metric CRS
    """
    lines = working_lines(streams[streams["storleksklass"].astype(str) == "2"], None, metric_crs)
    points = dams.to_crs(metric_crs).geometry.to_numpy()
    tree = shapely.STRtree(points)
    kept: list[LineString] = []
    for line in lines_of(lines.geometry):
        intervals = sorted(
            (max(0.0, line.project(points[i]) - DAM_CUT_M), min(line.length, line.project(points[i]) + DAM_CUT_M))
            for i in tree.query(line, predicate="dwithin", distance=DAM_NEAR_M)
        )
        previous = 0.0
        for start, end in intervals:
            if start > previous:
                piece = substring(line, previous, start)
                assert isinstance(piece, LineString)
                kept.append(piece)
            previous = max(previous, end)
        if previous < line.length:
            piece = substring(line, previous, line.length)
            assert isinstance(piece, LineString)
            kept.append(piece)
    if len(points):
        kept = [piece for line in kept for piece in _outside_dams(line, tree)]
    return gpd.GeoDataFrame(geometry=kept, crs=metric_crs)


def _components(count: int, pairs: np.ndarray) -> np.ndarray:
    """Label the connected sets without an unbounded walk through parents."""
    parent = list(range(count))

    def root(item: int) -> int:
        for _ in range(count):
            if parent[item] == item:
                return item
            parent[item] = parent[parent[item]]
            item = parent[item]
        raise RuntimeError("a water component's parent chain contains a cycle")

    for one, other in pairs.T:
        left, right = root(int(one)), root(int(other))
        parent[max(left, right)] = min(left, right)
    return np.unique([root(i) for i in range(count)], return_inverse=True)[1]


def portages(water_sources: list[NetworkSource], walking: Network, *, distance_m: float = PORTAGE_M) -> list[NetworkSource]:
    """Join nearby connected water pieces and tie the feet to walking nodes.

    Args:
        water_sources: Paddled lines after dam cuts
        walking: The noded walking network, in a metric CRS
        distance_m: Largest inferred carry between connected water pieces

    Returns:
        Inferred chords and their walking-network ties, both kind PORTAGE
    """
    if walking.edges.crs is None or not walking.edges.crs.is_projected:
        raise ValueError("portages need a projected walking network")
    metric_crs = walking.edges.crs
    arrays = [source.gdf.to_crs(metric_crs).geometry.to_numpy() for source in water_sources]
    lines = np.concatenate(arrays) if arrays else np.empty(0, dtype=object)
    chords: list[LineString] = []
    ties: dict[bytes, LineString] = {}
    if len(lines):
        # These are the connected pieces before portages: adding a carry must
        # not erase another pair that the reader may prefer to carry between.
        pairs = shapely.STRtree(lines).query(lines, predicate="intersects")
        labels = _components(len(lines), pairs)
        count = int(labels.max()) + 1
        groups = [shapely.union_all(lines[labels == i]) for i in range(count)]
        # A point on the shore nearest its own box centre remains on its piece,
        # even around islands, and is independent of the density of its chords.
        shores = np.concatenate([np.full(len(array), source.name != OPEN_WATER) for source, array in zip(water_sources, arrays, strict=True)])
        rings = np.concatenate([np.full(len(array), source.name == SHORE) for source, array in zip(water_sources, arrays, strict=True)])
        representatives = []
        obstacles = []
        for i, group in enumerate(groups):
            outline = shapely.union_all(lines[(labels == i) & shores])
            if outline.is_empty:
                outline = group
            west, south, east, north = outline.bounds
            representatives.append(shapely.get_point(shapely.shortest_line(outline, Point((west + east) / 2, (south + north) / 2)), 0))
            # Closed shore rings also bar chords wholly inside a third lake;
            # checking line crossings alone would miss water around an island.
            surface = shapely.build_area(shapely.union_all(lines[(labels == i) & rings]))
            obstacles.append(shapely.union_all([group, surface]))
        identities = {tuple(point.coords[0]): i for i, point in enumerate(representatives)}
        neighbours = shapely.get_parts(shapely.delaunay_triangles(shapely.MultiPoint(representatives), only_edges=True))
        group_tree = shapely.STRtree(obstacles)
        paths = walking.edges[walking.edges["kind"].isin((PATH, BRIDGE))]
        ids = np.unique(paths[["from_node", "to_node"]].to_numpy(dtype=int))
        nodes = walking.nodes.geometry.to_numpy()[ids]
        node_tree = shapely.STRtree(nodes)
        for neighbour in neighbours:
            one, other = (identities[tuple(coord)] for coord in neighbour.coords)
            chord = shapely.shortest_line(groups[one], groups[other])
            if chord.length == 0 or chord.length > distance_m:
                continue
            if any(int(hit) not in (one, other) for hit in group_tree.query(chord, predicate="intersects")):
                continue
            chords.append(chord)
            for foot in (Point(chord.coords[0]), Point(chord.coords[-1])):
                nearest = node_tree.query_nearest(foot, max_distance=PATH_JOIN_M, all_matches=False)
                if len(nearest):
                    tie = LineString([foot, nodes[int(nearest[0])]])
                    if tie.length > 0:
                        ties[shapely.normalize(tie).wkb] = tie
        print(
            f"  {count:,} connected water pieces; {len(chords):,} portage chords, "
            f"{sum(line.length for line in chords) / 1000:.3f} km; {len(ties):,} walking ties"
        )
    return [
        NetworkSource(
            name, gpd.GeoDataFrame(geometry=geometries, crs=walking.edges.crs), kind=PORTAGE, cost_factor=DEFAULT_BRIDGE_COST_FACTOR, keep_whole=True
        )
        for name, geometries in ((PORTAGES, chords), (PORTAGE_PATHS, list(ties.values())))
    ]


def build(
    sources: list[NetworkSource],
    masks: graphs.Masks,
    clip: gpd.GeoDataFrame,
    params: graphs.Params,
    rules: graphs.Rules,
    *,
    protected: gpd.GeoDataFrame,
    measure: Callable[[Network], Network],
) -> tuple[Network, pd.DataFrame]:
    """Build the combined network without writing into the shared input cache.

    Args:
        sources: Walking and paddled sources; receives the inferred portages
        masks: The walking records used to describe ground
        clip: Map extent
        params: Graph construction parameters
        rules: Country's projection and coverage rules
        protected: Protected areas
        measure: Country's height reader

    Returns:
        Measured combined network and per-source chain counts
    """

    def node(items: list[NetworkSource]) -> Network:
        return build_network(
            items,
            clip,
            metric_crs=rules.metric_crs,
            stroke_angle_deg=params.stroke_deg,
            probe_m=params.probe_m,
            bridge_m=params.bridge_m,
            ferry_cost_m=params.ferry_cost_km * 1000,
        )

    walking_sources = [source for source in sources if source.kind != PADDLE and source.name not in (PORTAGES, PORTAGE_PATHS)]
    started = time.perf_counter()
    walking = node(walking_sources)
    print(f"  Walking graph build before water: {time.perf_counter() - started:.3f} s; {len(walking.edges):,} edges")
    started = time.perf_counter()
    added = portages([source for source in sources if source.kind == PADDLE], walking)
    sources[:] = [source for source in sources if source.name not in (PORTAGES, PORTAGE_PATHS)] + added
    network = node(sources)
    print(f"  Combined graph build with portages: {time.perf_counter() - started:.3f} s; {len(network.edges):,} edges")
    report(network)
    network = replace(network, edges=graphs.derive(network.edges, masks, protected, rules))
    covered = chain_coverage(network.chains, network.edges)
    network = replace(network, chains=network.chains.assign(**{column: covered[column] for column in CHAIN_COVERAGE_COLUMNS}))
    network, levels = level_lakes(measure(network), threshold_m=params.ascent_threshold_m)
    network = open_level_streams(network)
    differences = (levels["registered"] - levels["percentile"]).abs().dropna()
    print(
        f"  Lake levels: {len(levels):,} bodies; {levels['registered'].notna().sum():,} registered, "
        f"{levels['registered'].isna().sum():,} shore percentile"
    )
    if len(differences):
        print(
            f"  Register against shore p10: {len(differences):,} bodies; "
            f"median absolute difference {differences.median():.6f} m, largest {differences.max():.6f} m"
        )
    else:
        print("  Register against shore p10: no bodies with both readings")
    # Walking sources retain the existing report's comparisons. The generated
    # water geometry already defines its units; a stroke comparison adds no evidence.
    counts = graphs.chain_report(walking_sources, clip, params, rules)
    rows: list[dict[str, Any]] = []
    for source in sources:
        if source.name in {item.name for item in walking_sources}:
            continue
        chains = network.chains[network.chains["source"] == source.name]
        rows.append(
            {
                "source": source.name,
                "features": len(source.gdf),
                "at every junction": len(chains),
                "angle only": len(chains),
                "with identity": len(chains),
                "whole": source.keep_whole,
                "km": chains["length_m"].sum() / 1000,
                "mean chain m": chains["length_m"].mean() if len(chains) else 0.0,
            }
        )
    return network, pd.concat([counts, pd.DataFrame(rows)], ignore_index=True)


def report(network: Network) -> None:
    """Print water edge counts and metres separately from the walking sources.

    Args:
        network: The combined graph
    """
    print("\nWater in the routing graph:")
    for name in (*WATER_SOURCES, PORTAGES, PORTAGE_PATHS):
        edges = network.edges[network.edges["source"] == name]
        print(f"  {name}: {len(edges):,} edges, {edges['length_m'].sum() / 1000:.3f} km")


def open_level_streams(network: Network) -> Network:
    """Allow both directions on level and rising stream chains.

    Args:
        network: Combined network after height sampling and lake levelling

    Returns:
        A copied network with direction cleared on every edge of each opened chain

    Raises:
        ValueError: If a stream has no chain or fewer than two finite height samples
    """
    streams = network.edges[network.edges["source"] == STREAMS]
    if streams["chain_id"].isna().any():
        raise ValueError("a stream needs a chain before its fall can be read")
    edges = network.edges.copy()
    opened: dict[str, list[tuple[int, float]]] = {"level": [], "rising": []}
    for chain, parts in streams.groupby("chain_id", sort=False):
        fall = 0.0
        for values in parts["elevations"]:
            heights = np.asarray(values, dtype=float)
            if heights.ndim != 1 or len(heights) < 2 or not np.isfinite(heights).all():
                raise ValueError(f"{chain} needs at least two finite heights on every stream edge")
            quarter = (len(heights) + 3) // 4
            fall += float(np.median(heights[:quarter]) - np.median(heights[-quarter:]))
        length = float(parts["length_m"].sum())
        threshold = max(LEVEL_FALL_M, LEVEL_GRADIENT * length)
        # Noding must not open short pieces of a steep stream. All samples
        # already follow flow, even where the chain's canonical order does not.
        if fall < threshold:
            edges.loc[parts.index, "one_way"] = False
            opened["rising" if fall < -threshold else "level"].append((len(parts), length))
    for label, chains in opened.items():
        print(
            f"  Streams opened ({label}): {len(chains):,} chains, "
            f"{sum(count for count, _ in chains):,} edges, {sum(length for _, length in chains) / 1000:.3f} km"
        )
    return replace(network, edges=edges)


def level_lakes(network: Network, *, threshold_m: float) -> tuple[Network, pd.DataFrame]:
    """Replace only lake-edge heights with one level per connected body.

    Args:
        network: Network after the country's height reader has sampled its edges
        threshold_m: The same ascent threshold used by that reader

    Returns:
        A copied network with lake profiles updated, and each body's registered,
        shore-percentile and chosen levels. Rivers, sea and portages retain their
        sampled profiles.

    Raises:
        ValueError: If a lake has neither a registered level nor a finite shore sample
    """
    chains = network.chains
    lakes = chains[chains[LAKE_BODY].notna() & chains["source"].isin((SHORE, OPEN_WATER))]
    bodies = network.edges["chain_id"].map(lakes.set_index("chain_id")[LAKE_BODY])
    edges = network.edges.copy()
    elevations = list(edges["elevations"])
    rows: list[dict[str, Any]] = []
    for body, parts in lakes.groupby(LAKE_BODY, sort=True):
        registered = pd.to_numeric(parts[LAKE_LEVEL], errors="raise").min()
        positions = np.flatnonzero((bodies == body).to_numpy())
        shore = edges.iloc[positions]
        series = [np.asarray(values, dtype=float) for values in shore.loc[shore["source"] == SHORE, "elevations"]]
        samples = np.concatenate(series) if series else np.empty(0)
        finite = samples[np.isfinite(samples)]
        percentile = float(np.percentile(finite, 10)) if len(finite) else np.nan
        level = float(registered) if pd.notna(registered) else percentile
        if not np.isfinite(level):
            raise ValueError(f"{body} has no registered level and no finite shore heights")
        rows.append({"body": body, "registered": registered, "percentile": percentile, "level": level})
        for position in positions:
            elevations[position] = np.full(len(elevations[position]), level)
    edges["elevations"] = pd.Series(elevations, index=edges.index, dtype=object)
    edges.loc[bodies.notna(), ["ascent", "descent"]] = 0.0
    # Recompute only lake chains; walking profiles retain their original figures.
    measured = chains.copy()
    if len(lakes):
        profiles = chain_profiles(lakes, edges[bodies.notna()], threshold_m=threshold_m)
        for column in PROFILE_COLUMNS:
            measured.loc[lakes.index, column] = profiles[column]
    return replace(network, edges=edges, chains=measured), pd.DataFrame(rows, columns=["body", "registered", "percentile", "level"])

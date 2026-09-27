"""The line off the bank as a routable network: sources, chords, noding and the checks after them (phase 12e).

:mod:`trails.network.paddle_geometry` draws the 15 m contour, the middle of
narrow water and the last metres from every bank contact to them, and proves
them; nothing there is a graph. This module turns them into the paddled sources
of a build and nothing else changes: carries and launches still measure to the
bank of :func:`water.paddle` (12d-1), which stays the build's :class:`water.Bank`.

It runs only behind the build setting ``paddle_offset``, off by default, so a
build without it is byte for byte the build before it. With it on, the build
first nodes today's network as it always has — the carries, launches and every
bridge it infers are that build's — and reads from it what the line must keep
reaching (:func:`contacts`). It then draws the line from the water loaded with a
halo of ``OFFSET_HALO_M`` round the map and replaces the bank-following sources:

- **Shore**: the contour, factor 1; **Narrow water**: the middle and its
  transitions, factor 1; **Landing water**: the spurs from bank anchors and
  stream mouths, factor 1; **Open water**: caps held by two shoulders, the
  chords, the exact lake-owned interfaces, the links into an interface's other
  side, open-water spurs from contacts far out, and lake crop seams, factor 1.5;
  **Streams** as they were. Each carries a role for the page (``sources.WATER_ROLES``).
- **Chords** follow today's rule on the new lines: the Delaunay edges between the
  written contour's vertices that the water at least d from the bank covers,
  less the contour's own segments, per height owner, and never along or across
  an interface or crop seam. The lake owns the seams once.
- **Bridges** are the earlier build's, every one, carried over as settled lines;
  the new build infers none. A bridge that reached the old bank now reaches its
  anchor, where its Landing water spur starts; one joining two banks is dropped.
- **Stream directions** are decided on the earlier build's stream edges (phase
  7's gate sums per-edge falls, so a finer cut would move it) and carried to the
  new edges by chain; lake planes read the earlier build's bank samples.
- **A spur leading nowhere is left out**: one whose bank end no other line of the
  build reaches, the anchor's only land side having been a bridge between two banks
  of one body or the crop (12e-2).

Review's decisions of 2026-09-27 (not Uwe's) fixed the last four and the halo.
"""

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, cast

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from trails.network import paddle_geometry as pg
from trails.network.water import (
    DAM_CUT_M,
    LAKE_BODY,
    LAKE_LEVEL,
    LANDING_WATER,
    NARROW_WATER,
    OPEN_WATER,
    OPEN_WATER_FACTOR,
    PORTAGES,
    SHORE,
    STREAMS,
    SURFACE_CLASS,
    Access,
    Bodies,
    _outside_dams,
    eligible_bodies,
)
from trails.routing.graph import DEFAULT_BRIDGE_COST_FACTOR, Network
from trails.routing.noding import NODE_TOLERANCE_M
from trails.routing.sources import BRIDGE, FERRY, LANDING, LAUNCH, OPEN, PADDLE, PATH, PORTAGE, STREAM, TRAVEL, NetworkSource

#: The water feeding the contour is loaded this far beyond the map: the offset plus its deviation
#: (12b found the contour held 15 m inside the box by features the box did not load).
OFFSET_HALO_M = pg.PADDLE_OFFSET_M + pg.CONTOUR_DEVIATION_M
#: Where a contact lies on the map's crop: the page's grid moves a point by at most 0.07 m (12d).
CROP_NEAR_M = 1.0
#: Contact roles an anchor is kept for (12c): every arrival at the water, not a line merely passing.
ANCHOR_ROLES = frozenset(
    {"launch", "portage", "walking_bank", "walking_in_water", "bridge_water", "bridge_land", "crop", "mouth", "stream_end", "dam_side"}
)
#: A written piece end found on an interface or crop seam within this: the grid's largest move and some.
MEET_M = 0.2
#: The chords' cover of the offset region: the written contour's vertices lie up to a grid move off it.
REGION_SLACK_M = 0.1
#: Two generated lines sharing both ends within this are one line.
SAME_END_M = 0.01
#: Unresolved kinds of :func:`paddle_geometry.landings` that stop a build.
UNRESOLVED = ("unresolved", "no body", "no line", "interface side without line")
OWNER_COLUMNS = [LAKE_BODY, LAKE_LEVEL, SURFACE_CLASS]
PADDLED = (SHORE, NARROW_WATER, LANDING_WATER, OPEN_WATER)


@dataclass(frozen=True)
class Offset:
    """What the line off the bank is drawn from, besides the bank.

    Attributes:
        surfaces: The water, whole features, loaded at least ``OFFSET_HALO_M`` beyond the extent
        window: EPSG:4326 polygon they were loaded over: where the source is complete
        extent: The map extent, as the bank was cut to it
        class_field: Surface classification column, or None when all are lakes
        lake_classes: Values of that column identifying lakes
        level_field: Registered height column, or None
    """

    surfaces: gpd.GeoDataFrame
    window: BaseGeometry
    extent: gpd.GeoDataFrame
    class_field: str | None = None
    lake_classes: tuple[str, ...] = ()
    level_field: str | None = None


def halo_bounds(zone: gpd.GeoDataFrame, metric_crs: str) -> tuple[float, float, float, float]:
    """The box, in EPSG:4326, holding the zone and ``OFFSET_HALO_M`` round it."""
    grown = zone.to_crs(metric_crs).buffer(OFFSET_HALO_M).to_crs("EPSG:4326")
    west, south, east, north = (float(value) for value in grown.total_bounds)
    return west, south, east, north


@dataclass
class Assembled:
    """The new sources of a build and what its later steps and checks read.

    Attributes:
        sources: Every source of the build, walking and land access unchanged
        probes: Edges of the earlier build to be measured beside the new ones:
            its Shore (``probe_body``, for lake planes) and its Streams
            (``probe_chain``, for phase 7's gate), metric
        contours: :func:`paddle_geometry.contours`' result
        landings: :func:`paddle_geometry.landings`' result
        contacts: What the line keeps reaching, from the earlier build
        dams: Dam points, metric
        water: The eligible bodies the line was drawn from, metric
        evidence: Counts and timings by step
    """

    sources: list[NetworkSource]
    probes: gpd.GeoDataFrame
    contours: pg.Contours
    landings: pg.Landings
    contacts: gpd.GeoDataFrame
    dams: np.ndarray
    water: Bodies
    evidence: dict[str, Any] = field(default_factory=dict)


def contacts(old: Network, *, dams: np.ndarray, extent: BaseGeometry | None) -> gpd.GeoDataFrame:
    """Every node of the earlier build where land access, a stream or a crop meets its paddled water.

    Phase 12a's inventory, read off the build instead of the published graph: a
    launch or carry end, a mapped way noded onto Shore (``walking_bank``) or onto
    Open water or a stream only (``walking_in_water``), a bridge (``bridge_water``
    where its other end is paddled, ``crop`` where that joins a line the extent
    cut, else ``bridge_land``), a stream meeting Shore (``mouth``) or ending on Open
    water (``stream_end``; ``stream_crossing`` where it passes), and a paddled dead
    end at a dam's disc (``dam_side``).

    Args:
        old: The earlier build's network, metric
        dams: Dam and lock-gate points, metric
        extent: The map extent, metric

    Returns:
        One row per contact: ``node``, ``roles`` (comma-separated), ``surface``,
        ``anchor`` (index among the anchors, or -1), ``through`` (the walking lines
        through a crossing contact) and the point
    """
    edges = old.edges
    ends = np.c_[edges["from_node"].to_numpy(dtype=int), edges["to_node"].to_numpy(dtype=int)]
    source = edges["source"].to_numpy()
    kind = edges["kind"].to_numpy()
    count = len(old.nodes)
    sources_at: list[set[str]] = [set() for _ in range(count)]
    kinds_at: list[set[str]] = [set() for _ in range(count)]
    for (one, other), name, what in zip(ends.tolist(), source.tolist(), kind.tolist(), strict=True):
        for node in (one, other):
            sources_at[node].add(name)
            kinds_at[node].add(what)
    paddled = kind == PADDLE
    paddle_degree = np.bincount(ends[paddled].ravel(), minlength=count)
    stream_degree = np.bincount(ends[source == STREAMS].ravel(), minlength=count)
    points = old.nodes.geometry.to_numpy()
    outline = extent.boundary if extent is not None else None
    bridge_roles: dict[int, set[str]] = defaultdict(set)
    for position in np.flatnonzero(kind == BRIDGE):
        one, other = (int(n) for n in ends[position])
        line = edges.geometry.iloc[position]
        at_crop = outline is not None and any(shapely.distance(shapely.get_point(line, i), outline) < CROP_NEAR_M for i in (0, -1))
        for here, there in ((one, other), (other, one)):
            if PADDLE in kinds_at[there]:
                bridge_roles[here].add("crop" if at_crop else "bridge_water")
            else:
                bridge_roles[here].add("bridge_land")
    dam_tree = shapely.STRtree(dams) if len(dams) else None
    rows: list[dict[str, Any]] = []
    for node in np.flatnonzero(paddle_degree > 0).tolist():
        at, what = sources_at[node], kinds_at[node]
        roles: list[str] = []
        if LAUNCH in what:
            roles.append("launch")
        if PORTAGES in at:
            roles.append("portage")
        if what & {PATH, FERRY}:
            roles.append("walking_bank" if SHORE in at else "walking_in_water")
        if BRIDGE in what:
            roles.extend(sorted(bridge_roles[node]))
        if STREAMS in at:
            if SHORE in at:
                roles.append("mouth")
            elif OPEN_WATER in at:
                roles.append("stream_end" if stream_degree[node] == 1 else "stream_crossing")
        if dam_tree is not None and paddle_degree[node] == 1 and len(dam_tree.query(points[node], predicate="dwithin", distance=DAM_CUT_M + 0.5)):
            roles.append("dam_side")
        if roles:
            rows.append({"node": node, "roles": ",".join(roles), "surface": bool(at & {SHORE, OPEN_WATER}), "geometry": points[node]})
    frame = gpd.GeoDataFrame(pd.DataFrame(rows, columns=["node", "roles", "surface", "geometry"]), geometry="geometry", crs=edges.crs)
    anchored = frame["roles"].map(lambda value: bool(set(value.split(",")) & ANCHOR_ROLES)).to_numpy(dtype=bool)
    frame["anchor"] = np.where(anchored, np.cumsum(anchored) - 1, -1)
    frame["through"] = pd.Series(_through(old, frame), index=frame.index, dtype=object)
    return frame


def _through(old: Network, frame: gpd.GeoDataFrame) -> list[BaseGeometry | None]:
    """The whole walking chains passing through each crossing contact, as 12d read them."""
    crossing = {int(n) for n, roles in zip(frame["node"], frame["roles"], strict=True) if "walking_in_water" in roles.split(",")}
    out: list[BaseGeometry | None] = [None] * len(frame)
    if not crossing:
        return out
    walked = old.edges[old.edges["kind"].isin((PATH, FERRY))]
    chains_at: dict[int, set[str]] = defaultdict(set)
    for one, other, chain in zip(walked["from_node"], walked["to_node"], walked["chain_id"], strict=True):
        for node in (int(one), int(other)):
            if node in crossing and isinstance(chain, str):
                chains_at[node].add(chain)
    geometry_of = dict(zip(old.chains["chain_id"], old.chains.geometry, strict=True))
    for position, node in enumerate(frame["node"].tolist()):
        if node in chains_at:
            out[position] = shapely.union_all([geometry_of[c] for c in sorted(chains_at[node]) if c in geometry_of])
    return out


def _relabelled(wide: Bodies, wide_keys: np.ndarray, today: Bodies, today_keys: np.ndarray) -> tuple[Bodies, dict[str, int]]:
    """Give each lake owner of the halo-loaded water the label and register level the bank's owner has.

    The labels number connected lake groups, so loading more water renumbers them;
    the bank's are what its chains and levels carry. A lake whose delivery rows the
    map's load holds takes that lake's label and level; one wholly in the halo gets a
    label of its own. Rows are matched by their exact geometry.
    """
    row_of = {key: row for row, key in enumerate(today_keys)}
    owner_of_row: dict[int, int] = {}
    for parent, owner in zip(today.parents.tolist(), today.owner.tolist(), strict=True):
        owner_of_row.setdefault(int(parent), int(owner))
    owners = [dict(attributes) for attributes in wide.owners]
    counts: Counter[str] = Counter()
    for index, attributes in enumerate(wide.owners):
        if attributes[LAKE_BODY] is None:
            continue
        found: Counter[int] = Counter()
        for parent in wide.parents[wide.owner == index].tolist():
            row = row_of.get(wide_keys[parent])
            if row is not None and row in owner_of_row and today.owners[owner_of_row[row]][LAKE_BODY] is not None:
                found[owner_of_row[row]] += 1
        if found:
            match = today.owners[found.most_common(1)[0][0]]
            owners[index] = {LAKE_BODY: match[LAKE_BODY], LAKE_LEVEL: match[LAKE_LEVEL], SURFACE_CLASS: attributes[SURFACE_CLASS]}
            counts["matched"] += 1
            counts["merged by the halo"] += int(len(found) > 1)
        else:
            owners[index] = {**attributes, LAKE_BODY: f"halo-{attributes[LAKE_BODY]}"}
            counts["halo only"] += 1
    return replace(wide, owners=owners), dict(counts)


def _insert(line: LineString, point: np.ndarray) -> LineString:
    """The line with ``point`` inserted as a vertex into the segment nearest it, unless it is a vertex already."""
    coords = shapely.get_coordinates(line)
    if (np.abs(coords - point).max(axis=1) == 0).any():
        return line
    distances = pg._distance_pairs(np.repeat(point[None, :], len(coords) - 1, axis=0), coords[:-1], coords[1:])
    segment = int(np.argmin(distances))
    return LineString(np.vstack([coords[: segment + 1], point[None, :], coords[segment + 1 :]]))


def _foot(target: BaseGeometry, point: np.ndarray) -> np.ndarray:
    """The point of ``target`` nearest ``point``: exactly on it, up to rounding."""
    return np.asarray(shapely.get_coordinates(target.interpolate(target.project(Point(point))))[0])


def _owner(row: pd.Series) -> dict[str, Any]:
    return {LAKE_BODY: row[LAKE_BODY], LAKE_LEVEL: row[LAKE_LEVEL], SURFACE_CLASS: row[SURFACE_CLASS]}


def _chords(
    result: pg.Contours, water: Bodies, boundaries: dict[int, list[BaseGeometry]], seams: dict[int, list[BaseGeometry]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Today's open-water rule on the new lines, body by body.

    The candidates are the Delaunay edges between the written contour's vertices
    (Shore and cap pieces). An edge is a chord where the water at least d from the
    bank of one height owner covers it (within the grid's slack), it is not a
    segment of the contour, it lies along no interface or crop seam and it meets
    no contour, interface or seam except at its own two ends. Delaunay is n log n
    in the vertices; nothing here is pairwise over them.
    """
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    if result.regions is None or not len(result.regions):
        return rows, dict(counts)
    for body, region in zip(result.regions["body"].tolist(), result.regions.geometry.tolist(), strict=True):
        pieces = result.lines[result.lines["body"] == body]
        if not len(pieces) or region.is_empty:
            continue
        runs = [shapely.get_coordinates(line) for line in pieces.geometry]
        vertices = np.unique(np.vstack(runs), axis=0)
        if len(vertices) < 3:
            continue
        own = {tuple(sorted((tuple(a), tuple(b)))) for run in runs for a, b in zip(run[:-1].tolist(), run[1:].tolist(), strict=True)}
        candidates = shapely.get_parts(shapely.delaunay_triangles(shapely.multipoints(vertices), only_edges=True))
        counts["delaunay"] += len(candidates)
        ends = shapely.get_coordinates(candidates).reshape(-1, 2, 2)
        keys = [tuple(sorted((tuple(a), tuple(b)))) for a, b in ends.tolist()]
        kept = np.array([key not in own for key in keys], dtype=bool)
        counts["contour segments"] += int((~kept).sum())
        members = np.flatnonzero(water.body == body)
        owned = sorted({int(o) for o in water.owner[members]})
        cover = np.full(len(candidates), -1, dtype=int)
        for owner in owned:
            part = (
                region if len(owned) == 1 else shapely.intersection(region, shapely.union_all(water.polygons[members[water.owner[members] == owner]]))
            )
            grown = shapely.buffer(part, REGION_SLACK_M)
            shapely.prepare(grown)
            inside = kept & shapely.covers(grown, candidates)
            # Covered by two owners' water within the slack: it runs along their interface, which is a line of its own.
            cover[inside & (cover >= 0)] = -2
            cover[inside & (cover == -1)] = owner
        counts["outside the water d from the bank"] += int((kept & (cover == -1)).sum())
        counts["along an interface"] += int((cover == -2).sum())
        chosen = np.flatnonzero(cover >= 0)
        lines = [*pieces.geometry, *boundaries.get(body, []), *seams.get(body, [])]
        if len(chosen) and lines:
            along = (
                shapely.buffer(shapely.union_all([*boundaries.get(body, []), *seams.get(body, [])]), pg.JOIN_SNAP_M)
                if len(lines) > len(pieces)
                else None
            )
            tree = shapely.STRtree(lines)
            left, right = tree.query(candidates[chosen], predicate="intersects")
            bad = np.zeros(len(chosen), dtype=bool)
            if len(left):
                met = shapely.intersection(candidates[chosen][left], np.asarray(lines, dtype=object)[right])
                tips = shapely.multipoints(ends[chosen][left])
                bad[np.unique(left[~shapely.is_empty(shapely.difference(met, tips))])] = True
            if along is not None:
                bad |= shapely.covers(along, candidates[chosen])
            counts["meeting a line between its ends"] += int(bad.sum())
            chosen = chosen[~bad]
        for index in chosen.tolist():
            rows.append({**water.owners[int(cover[index])], "geometry": candidates[index]})
        counts["chords"] += len(chosen)
    return rows, dict(counts)


def _crop_seams(result: pg.Contours, water: Bodies, extent: BaseGeometry | None) -> dict[int, list[tuple[LineString, dict[str, Any]]]]:
    """Where the extent cuts a lake's water at least d from the bank: the lake keeps that seam, as today, with its owner."""
    out: dict[int, list[tuple[LineString, dict[str, Any]]]] = defaultdict(list)
    if extent is None or result.regions is None:
        return out
    outline = extent.boundary
    for body, region in zip(result.regions["body"].tolist(), result.regions.geometry.tolist(), strict=True):
        pieces = result.lines[(result.lines["body"] == body) & ((result.lines["start"] == pg.CROP) | (result.lines["end"] == pg.CROP))]
        if not len(pieces):
            continue
        crop_ends = []
        for line, start, end in zip(pieces.geometry, pieces["start"], pieces["end"], strict=True):
            coords = shapely.get_coordinates(line)
            if start == pg.CROP:
                crop_ends.append(coords[0])
            if end == pg.CROP:
                crop_ends.append(coords[-1])
        tips = np.asarray(crop_ends)
        members = np.flatnonzero(water.body == body)
        for owner in sorted({int(o) for o in water.owner[members]}):
            if water.owners[owner][LAKE_BODY] is None:
                continue
            part = shapely.intersection(region, shapely.union_all(water.polygons[members[water.owner[members] == owner]]))
            for seam in shapely.get_parts(shapely.line_merge(shapely.intersection(part.boundary, outline))):
                if not isinstance(seam, LineString) or seam.length <= 0:
                    continue
                coords = shapely.get_coordinates(seam)
                for index in (0, -1):
                    gaps = np.hypot(*(tips - coords[index]).T)
                    if len(gaps) and gaps.min() <= MEET_M:
                        coords[index] = tips[int(np.argmin(gaps))]
                out[body].append((LineString(coords), dict(water.owners[owner])))
    return out


def assemble(old: Network, sources: list[NetworkSource], access: Access, *, metric_crs: str) -> Assembled:
    """Replace the bank-following paddled sources with the line off the bank.

    Args:
        old: The earlier build's network of these sources, metric
        sources: The build's sources, carries and launches included
        access: Its bank, dams and the halo-loaded water (``access.offset``)
        metric_crs: The build's metric CRS

    Returns:
        The new sources and what the later steps read

    Raises:
        ValueError: If a contact, stream mouth or interface finds no way to the line
    """
    offset = access.offset
    if offset is None or access.bank is None:
        raise ValueError("the line off the bank needs the halo-loaded water and the bank")
    timings: dict[str, float] = {}
    started = time.perf_counter()
    source_crs = sources[0].gdf.crs
    if source_crs is None:
        raise ValueError("the sources need a coordinate reference system")
    extent = offset.extent.to_crs(metric_crs).union_all()
    window = gpd.GeoSeries([offset.window], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    dams = access.dams.to_crs(metric_crs).geometry.to_numpy() if access.dams is not None and len(access.dams) else np.empty(0, dtype=object)
    streams_frame = access.bank.streams
    streams = streams_frame.to_crs(metric_crs).geometry.to_numpy() if streams_frame is not None else np.empty(0, dtype=object)
    found = contacts(old, dams=dams, extent=extent)
    anchors = found.geometry.to_numpy()[found["anchor"].to_numpy() >= 0]
    timings["contacts_s"] = time.perf_counter() - started

    started = time.perf_counter()
    wide_metric = offset.surfaces.to_crs(metric_crs)
    today_metric = access.surfaces.to_crs(metric_crs)
    wide = eligible_bodies(wide_metric, offset.class_field, offset.lake_classes, offset.level_field)
    today = eligible_bodies(today_metric, offset.class_field, offset.lake_classes, offset.level_field)
    wide, relabelled = _relabelled(
        wide, shapely.to_wkb(offset.surfaces.geometry.to_numpy()), today, shapely.to_wkb(access.surfaces.geometry.to_numpy())
    )
    timings["bodies_s"] = time.perf_counter() - started

    started = time.perf_counter()
    result = pg.contours(wide, crs=metric_crs, extent=extent, source_window=window, dams=dams if len(dams) else None, anchors=anchors)
    timings["contours_s"] = time.perf_counter() - started
    started = time.perf_counter()
    landed = pg.landings(result, wide, found, crs=metric_crs, dams=dams if len(dams) else None, streams=streams, extent=extent)
    timings["landings_s"] = time.perf_counter() - started
    unresolved = landed.failures[landed.failures["kind"].isin(UNRESOLVED)]
    if len(unresolved):
        places = [
            f"{kind} {detail} at {xy[0]:.1f} {xy[1]:.1f}"
            for kind, detail, xy in zip(
                unresolved["kind"], unresolved["detail"], shapely.get_coordinates(unresolved.geometry.to_numpy()), strict=True
            )
        ]
        raise ValueError(f"{len(unresolved)} contacts reach no line: {'; '.join(places[:5])}")

    started = time.perf_counter()
    evidence: dict[str, Any] = {"relabelled owners": relabelled, "contacts": len(found), "anchors": len(anchors)}
    lines = result.lines.copy()
    centre = result.centre.copy()
    evidence["contact crossings"] = _contacts_written(result, lines, centre)
    interfaces, meets = _interfaces(landed, lines, centre)
    seams = _crop_seams(result, wide, extent)
    boundaries: dict[int, list[BaseGeometry]] = defaultdict(list)
    for body, line in zip(landed.interfaces["body"].tolist(), interfaces, strict=True):
        boundaries[int(body)].append(line)
    chord_rows, chord_counts = _chords(result, wide, boundaries, {body: [seam for seam, _ in found_seams] for body, found_seams in seams.items()})
    evidence["chords"] = chord_counts
    evidence["interface meets"] = meets
    timings["chords_s"] = time.perf_counter() - started

    started = time.perf_counter()
    targets = {"contour": lines, "centre": centre}
    landing_rows: list[dict[str, Any]] = []
    open_rows: list[dict[str, Any]] = []
    start_of: dict[int, np.ndarray] = {}
    body_of: dict[int, int] = {}
    moved: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    contact_xy = shapely.get_coordinates(found.geometry.to_numpy())
    for spur in landed.spurs.to_dict("records"):
        node = int(found["node"].iloc[spur["contact"]])
        if spur["route"] == pg.ON_LINE:
            start_of[node] = contact_xy[spur["contact"]]
            body_of[node] = int(spur["body"])
        if not isinstance(spur["source"], str):
            continue
        coords = shapely.get_coordinates(spur["geometry"]).copy()
        if spur["anchor_moved_m"] > 0:
            # 12c's rule moved the written anchor out of a dam's disc: the land side ends there too.
            moved[node] = (contact_xy[spur["contact"]], coords[0].copy())
        else:
            coords[0] = contact_xy[spur["contact"]]
        target = _target(targets, spur["target"], spur["target_row"], coords[-1], int(spur["body"]))
        coords[-1] = _foot(target.geometry, coords[-1])
        start_of[node] = coords[0]
        body_of[node] = int(spur["body"])
        row = {**_owner(target), "geometry": LineString(coords), "contact": node}
        (landing_rows if spur["source"] == LANDING_WATER else open_rows).append(row)
    for mouth in landed.mouths.to_dict("records"):
        if not isinstance(mouth["source"], str):
            continue
        coords = shapely.get_coordinates(mouth["geometry"]).copy()
        coords[0] = shapely.get_coordinates(mouth["at"])[0]
        target = _target(targets, mouth["target"], mouth["target_row"], coords[-1], int(mouth["body"]))
        coords[-1] = _foot(target.geometry, coords[-1])
        row = {**_owner(target), "geometry": LineString(coords), "contact": -1}
        (landing_rows if mouth["source"] == LANDING_WATER else open_rows).append(row)
    for link in landed.links.to_dict("records"):
        coords = shapely.get_coordinates(link["geometry"]).copy()
        coords[0] = _foot(interfaces[int(link["interface"])], coords[0])
        target = _target(targets, link["target"], link["target_row"], coords[-1], int(landed.interfaces["body"].iloc[int(link["interface"])]))
        coords[-1] = _foot(target.geometry, coords[-1])
        open_rows.append({**_owner(target), "geometry": LineString(coords), "contact": -1})
    landing_rows, landing_duplicates = _without_duplicates(landing_rows)
    open_rows, open_duplicates = _without_duplicates(open_rows)
    evidence["duplicates removed"] = {"landing water": landing_duplicates, "open-water spurs and links": open_duplicates}
    evidence["dam anchors moved"] = len(moved)

    dam_tree = shapely.STRtree(dams) if len(dams) else None

    def cut(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if dam_tree is None:
            return rows
        return [{**row, "geometry": piece} for row in rows for piece in _outside_dams(row["geometry"], dam_tree)]

    route_of = {int(found["node"].iloc[c]): str(r) for c, r in zip(landed.spurs["contact"], landed.spurs["route"], strict=True)}
    bridges, bridge_counts = _bridges(old, start_of, body_of, route_of)
    evidence["bridges"] = bridge_counts
    kept: list[NetworkSource] = []
    stream_source = None
    for source in sources:
        if source.kind == PADDLE:
            if source.name == STREAMS:
                stream_source = replace(source, role=STREAM)
            continue
        kept.append(_moved_ends(source, moved, metric_crs) if moved and source.kind in (LAUNCH, PORTAGE) else source)

    columns = [*OWNER_COLUMNS, "geometry"]
    open_water: list[dict[Any, Any]] = [
        *lines.loc[lines["source"] == OPEN_WATER, columns].to_dict("records"),
        *cut(chord_rows),
        *({**row, "geometry": line} for row, line in zip(landed.interfaces[OWNER_COLUMNS].to_dict("records"), interfaces, strict=True)),
        *cut([{**owners, "geometry": seam} for found_seams in seams.values() for seam, owners in found_seams]),
        *({key: value for key, value in row.items() if key != "contact"} for row in open_rows),
    ]
    shore = lines.loc[lines["source"] == SHORE, columns].to_dict("records")
    narrow = centre[columns].to_dict("records")
    # A spur whose bank end nothing else reaches, the anchor having no land side, stream or other
    # water left (mostly a bridge between two banks of one body, dropped above), leads nowhere.
    others = [
        *(row["geometry"] for rows in (shore, narrow, open_water) for row in rows),
        *bridges,
        *streams,
        *(line for source in kept for line in source.gdf.to_crs(metric_crs).geometry),
    ]
    landing_rows, evidence["dead-end spurs left out"] = _without_dead_ends(landing_rows, others)
    frames: dict[str, list[dict[Any, Any]]] = {
        SHORE: shore,
        NARROW_WATER: narrow,
        LANDING_WATER: [{key: value for key, value in row.items() if key != "contact"} for row in landing_rows],
        OPEN_WATER: open_water,
    }
    roles = {SHORE: TRAVEL, NARROW_WATER: TRAVEL, LANDING_WATER: LANDING, OPEN_WATER: OPEN}
    factors = {SHORE: 1.0, NARROW_WATER: 1.0, LANDING_WATER: 1.0, OPEN_WATER: OPEN_WATER_FACTOR}
    paddled = [
        NetworkSource(
            name,
            gpd.GeoDataFrame(pd.DataFrame(rows, columns=[*OWNER_COLUMNS, "geometry"]), geometry="geometry", crs=metric_crs).to_crs(source_crs),
            kind=PADDLE,
            cost_factor=factors[name],
            keep_whole=True,
            attributes=tuple(OWNER_COLUMNS),
            role=roles[name],
            settled=True,
        )
        for name, rows in frames.items()
    ]
    paddled.append(
        NetworkSource(
            BRIDGE,
            gpd.GeoDataFrame(geometry=bridges, crs=metric_crs).to_crs(source_crs),
            kind=BRIDGE,
            cost_factor=DEFAULT_BRIDGE_COST_FACTOR,
            keep_whole=True,
            settled=True,
        )
    )
    if stream_source is not None:
        paddled.insert(len(frames), stream_source)
    evidence["sources"] = {source.name: len(source.gdf) for source in paddled}
    timings["assembly_s"] = time.perf_counter() - started
    evidence["timings"] = timings
    return Assembled(
        sources=kept + paddled,
        probes=_probes(old),
        contours=result,
        landings=landed,
        contacts=found,
        dams=dams,
        water=wide,
        evidence=evidence,
    )


def _target(targets: dict[str, gpd.GeoDataFrame], kind: str, row: int, near: np.ndarray, body: int) -> pd.Series:
    """The contour or centre row a spur ends on; 12c's anchor node is the end of a centre piece of its body."""
    if kind in targets and int(row) >= 0:
        return cast(pd.Series, targets[kind].loc[int(row)])
    own = targets["centre"][targets["centre"]["body"] == body]
    if not len(own):
        own = targets["contour"][targets["contour"]["body"] == body]
    return own.iloc[int(np.argmin(shapely.distance(own.geometry.to_numpy(), Point(near))))]


def _contacts_written(result: pg.Contours, lines: gpd.GeoDataFrame, centre: gpd.GeoDataFrame) -> dict[str, int]:
    """12b's and 12c's contacts: two written lines within the grid's reach that cross once written.

    Where the written lines cross, the build nodes them at the crossing. Where they
    only come within the reach, a shared vertex midway is inserted into both.
    """
    counts: Counter[str] = Counter()
    places = result.failures[result.failures["kind"] == "contact"]
    if not len(places):
        return dict(counts)
    frames = [("contour", lines), ("centre", centre)]
    geometries = np.array([frame.loc[index].geometry for name, frame in frames for index in frame.index], dtype=object)
    tree = shapely.STRtree(geometries)
    for where in places.geometry:
        x, y = shapely.get_coordinates(where)[0]
        near = tree.query(where, predicate="dwithin", distance=pg.CONTACT_M + pg.GRID_MOVE_M)
        box = shapely.box(x - 1, y - 1, x + 1, y + 1)
        best: tuple[float, int, int] | None = None
        for i in near.tolist():
            for j in near.tolist():
                if i < j:
                    gap = float(shapely.distance(shapely.clip_by_rect(geometries[i], *box.bounds), shapely.clip_by_rect(geometries[j], *box.bounds)))
                    if best is None or gap < best[0]:
                        best = (gap, i, j)
        if best is None:
            counts["one line only"] += 1
            continue
        gap, i, j = best
        if gap == 0:
            counts["crossing, noded by the build"] += 1
            continue
        pair = shapely.get_coordinates(
            shapely.shortest_line(shapely.clip_by_rect(geometries[i], *box.bounds), shapely.clip_by_rect(geometries[j], *box.bounds))
        )
        middle = pair.mean(axis=0)
        for k in (i, j):
            geometries[k] = _insert(cast(LineString, geometries[k]), middle)
        counts["apart, given a shared vertex"] += 1
    first = 0
    for _, frame in frames:
        frame["geometry"] = gpd.GeoSeries(geometries[first : first + len(frame)], index=frame.index, crs=frame.crs)
        first += len(frame)
    return dict(counts)


def _interfaces(landed: pg.Landings, lines: gpd.GeoDataFrame, centre: gpd.GeoDataFrame) -> tuple[list[LineString], int]:
    """Each exact interface with the written ends of the pieces cut at it inserted, so both share them."""
    out: list[LineString] = []
    inserted = 0
    for body, exact in zip(landed.interfaces["body"].tolist(), landed.interfaces.geometry.tolist(), strict=True):
        line = cast(LineString, exact)
        for frame in (lines, centre):
            own = frame[(frame["body"] == body) & ((frame["start"] == pg.INTERFACE) | (frame["end"] == pg.INTERFACE))]
            for written, start, end in zip(own.geometry, own["start"], own["end"], strict=True):
                coords = shapely.get_coordinates(written)
                for kind, tip in ((start, coords[0]), (end, coords[-1])):
                    if kind == pg.INTERFACE and shapely.distance(Point(tip), line) <= MEET_M:
                        line = _insert(line, tip)
                        inserted += 1
        out.append(line)
    return out, inserted


def _without_duplicates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Drop a generated line whose two ends another already has, as a stream end joined twice would be."""
    kept: list[dict[str, Any]] = []
    # Ends by the cell of side SAME_END_M holding their first point; a match lies in that cell or one beside it.
    seen: dict[tuple[int, int], list[np.ndarray]] = defaultdict(list)
    dropped = 0
    for row in rows:
        coords = shapely.get_coordinates(row["geometry"])
        ends = np.r_[coords[0], coords[-1]]
        found = False
        for first in (ends, ends[[2, 3, 0, 1]]):
            cell = (int(first[0] // SAME_END_M), int(first[1] // SAME_END_M))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if any(np.abs(first - other).max() <= SAME_END_M for other in seen.get((cell[0] + dx, cell[1] + dy), [])):
                        found = True
        if found:
            dropped += 1
            continue
        seen[(int(ends[0] // SAME_END_M), int(ends[1] // SAME_END_M))].append(ends)
        kept.append(row)
    return kept, dropped


def _without_dead_ends(rows: list[dict[str, Any]], others: list[BaseGeometry]) -> tuple[list[dict[str, Any]], int]:
    """Drop a contact's spur whose bank end no other line of the build reaches within the node tolerance.

    Such an end would be a node of degree one after noding: nothing on land, no stream,
    no other water. A stream mouth's join (``contact`` -1) starts on its stream and stays.
    Another spur from the same point counts as a line reaching it, so both stay.
    """
    spurs = [index for index, row in enumerate(rows) if row["contact"] >= 0]
    if not spurs:
        return rows, 0
    tips = shapely.points([shapely.get_coordinates(rows[index]["geometry"])[0] for index in spurs])
    lines = np.asarray([*others, *(row["geometry"] for row in rows)], dtype=object)
    near, found = shapely.STRtree(lines).query(tips, predicate="dwithin", distance=NODE_TOLERANCE_M)
    own = np.asarray(spurs)[near] + len(others)
    reached = np.zeros(len(spurs), dtype=bool)
    reached[near[found != own]] = True
    dead = {index for index, hit in zip(spurs, reached.tolist(), strict=True) if not hit}
    return [row for index, row in enumerate(rows) if index not in dead], len(dead)


def _bridges(
    old: Network, start_of: dict[int, np.ndarray], body_of: dict[int, int], route_of: dict[int, str]
) -> tuple[list[LineString], dict[str, int]]:
    """Every bridge of the earlier build, each end that reached the old bank now at its anchor's spur.

    A bridge between two banks of one body joined lines the new network joins through
    the water, or lines the extent cut: it is dropped. Between two bodies it is the
    only way across and runs between their two anchors. One whose bank end has no
    spur (a crop, a line far out in open water) has nothing to reach and is dropped.
    """
    edges = old.edges
    surface_at = np.zeros(len(old.nodes), dtype=bool)
    on_bank = edges["source"].isin((SHORE, OPEN_WATER)).to_numpy()
    for column in ("from_node", "to_node"):
        surface_at[edges.loc[on_bank, column].to_numpy(dtype=int)] = True
    counts: Counter[str] = Counter()
    out: list[LineString] = []
    bridges = edges[edges["kind"] == BRIDGE]
    for one, other, line in zip(bridges["from_node"].tolist(), bridges["to_node"].tolist(), bridges.geometry.tolist(), strict=True):
        banks = (surface_at[int(one)], surface_at[int(other)])
        if not any(banks):
            out.append(cast(LineString, line))
            counts["kept as they were"] += 1
            continue
        ends = [(index, int(node)) for index, node in ((0, one), (-1, other)) if surface_at[int(node)]]
        missing = [node for _, node in ends if node not in start_of]
        if missing:
            counts[f"bank end without a spur ({route_of.get(missing[0], 'no contact')}), dropped"] += 1
            continue
        if len(ends) == 2 and body_of.get(ends[0][1]) == body_of.get(ends[1][1]):
            counts["between two banks of one body, dropped"] += 1
            continue
        coords = shapely.get_coordinates(line).copy()
        for index, node in ends:
            coords[index] = start_of[node]
        out.append(LineString(coords))
        counts["between two bodies, to both anchors" if len(ends) == 2 else "to the anchor"] += 1
    return out, dict(counts)


def _moved_ends(source: NetworkSource, moved: dict[int, tuple[np.ndarray, np.ndarray]], metric_crs: str) -> NetworkSource:
    """A carry or launch ending at a dam anchor 12c's rule moved out of the disc ends at the moved point."""
    frame = source.gdf.to_crs(metric_crs)
    pairs = list(moved.values())
    exact = np.array([one for one, _ in pairs])
    lines = []
    for line in frame.geometry:
        coords = shapely.get_coordinates(line).copy()
        for index in (0, -1):
            gaps = np.hypot(*(exact - coords[index]).T)
            if gaps.min() <= SAME_END_M:
                coords[index] = pairs[int(np.argmin(gaps))][1]
        lines.append(LineString(coords))
    crs = source.gdf.crs
    if crs is None:
        raise ValueError(f"{source.name} needs a coordinate reference system")
    return replace(source, gdf=frame.set_geometry(lines).to_crs(crs))


def _probes(old: Network) -> gpd.GeoDataFrame:
    """The earlier build's Shore and Streams edges, to be measured with the new network and then set apart."""
    wanted = old.edges[old.edges["source"].isin((SHORE, STREAMS))]
    body_of = dict(zip(old.chains["chain_id"], old.chains[LAKE_BODY], strict=True)) if LAKE_BODY in old.chains else {}
    return gpd.GeoDataFrame(
        {
            "from_node": 0,
            "to_node": 0,
            "source": wanted["source"].to_numpy(),
            "kind": PADDLE,
            "chain_id": None,
            "probe_chain": wanted["chain_id"].to_numpy(),
            "probe_body": [body_of.get(chain) for chain in wanted["chain_id"]],
            "length_m": wanted["length_m"].to_numpy(),
        },
        geometry=wanted.geometry.to_numpy(),
        crs=old.edges.crs,
    )


def measured_with(network: Network, probes: gpd.GeoDataFrame, measure: Any) -> tuple[Network, gpd.GeoDataFrame]:
    """Measure the network and the probes in one pass of the height model, and set the probes apart.

    A probe names no chain, so it lies on no chain's profile; its samples are laid
    exactly as the earlier build laid them on the same edge.
    """
    count = len(network.edges)
    joined = pd.concat([network.edges, probes], ignore_index=True)
    together = measure(replace(network, edges=gpd.GeoDataFrame(joined, geometry="geometry", crs=network.edges.crs)))
    edges = together.edges
    kept = edges.iloc[:count].drop(columns=[c for c in probes.columns if c not in network.edges.columns])
    # The probes' empty cells must not leave the network's own columns widened.
    for column in network.edges.columns:
        if column != "geometry":
            kept[column] = kept[column].astype(network.edges[column].dtype)
    kept.index = network.edges.index
    return replace(together, edges=gpd.GeoDataFrame(kept, geometry="geometry", crs=network.edges.crs)), edges.iloc[count:].reset_index(drop=True)


def shore_samples(probed: gpd.GeoDataFrame) -> dict[str, np.ndarray]:
    """The earlier build's bank heights per lake body: phase 9's plane where no level is registered."""
    shore = probed[(probed["source"] == SHORE) & probed["probe_body"].notna()]
    return {str(body): np.concatenate([np.asarray(v, dtype=float) for v in group["elevations"]]) for body, group in shore.groupby("probe_body")}


def stream_edges(probed: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """The earlier build's measured stream edges under their chain ids: what phase 7's gate decides on."""
    streams = probed[probed["source"] == STREAMS].copy()
    streams["chain_id"] = streams["probe_chain"]
    return streams


def validate(network: Network, assembled: Assembled) -> dict[str, Any]:
    """The gates again on the built network, as the page will write it.

    Every new paddled edge is written through the page's grid and read back.
    Shore: its least distance from the unsimplified bank (at least 12 m). Every
    new paddled edge: its least distance from a dam point (at least the disc,
    save the step off a disc a dam anchor's spur begins with) and its length
    outside the water beyond a Landing water spur's bank step.

    Returns:
        The figures, by source; failing edges are counted, not repaired
    """
    edges = network.edges
    to_page, from_page = pg._page_round_trip(edges.crs)
    out: dict[str, Any] = {}
    water = assembled.water
    rings = (
        [
            np.asarray(ring.coords)[:, :2]
            for polygon in shapely.get_parts(shapely.union_all(water.polygons))
            for ring in (polygon.exterior, *polygon.interiors)
        ]
        if len(water.polygons)
        else []
    )
    bank_tree = shapely.STRtree(np.concatenate([pg._edges(ring) for ring in rings])) if rings else None
    water_tree = shapely.STRtree(water.polygons) if len(water.polygons) else None
    locals_: dict[int, Any] = {}
    dam_xy = shapely.get_coordinates(assembled.dams) if len(assembled.dams) else np.empty((0, 2))
    degree = np.bincount(edges[["from_node", "to_node"]].to_numpy(dtype=int).ravel(), minlength=len(network.nodes))
    for name in PADDLED:
        own = edges[edges["source"] == name]
        if not len(own):
            continue
        counts = shapely.get_num_coordinates(own.geometry.to_numpy())
        read = pg.decoded(shapely.get_coordinates(own.geometry.to_numpy()), to_page, from_page)
        runs = np.split(read, np.cumsum(counts)[:-1])
        written = np.asarray(shapely.linestrings(read, indices=np.repeat(np.arange(len(own)), counts)), dtype=object)
        figures: dict[str, Any] = {"edges": len(own), "km": round(float(own["length_m"].sum()) / 1000, 3)}
        # An end nothing else meets: a spur's bank end where the anchor has no land side left, or a
        # line end the noding missed, which would be a break no route can cross.
        figures["loose ends"] = int((degree[own[["from_node", "to_node"]].to_numpy(dtype=int)] == 1).sum())
        if name == SHORE and bank_tree is not None:
            _, clearance = bank_tree.query_nearest(np.concatenate([pg._edges(run) for run in runs]), return_distance=True, all_matches=False)
            figures["least clearance m"] = round(float(clearance.min()), 4)
            figures["segments under 12 m"] = int((clearance < pg.CONTOUR_CLEARANCE_M).sum())
        if len(dam_xy):
            near = [pg._dam_clearance(run, dam_xy) for run in runs]
            figures["least dam clearance m"] = round(float(min(near)), 4)
            figures["edges inside a disc"] = int(sum(value < DAM_CUT_M - pg.DRY_NOISE_M for value in near))
        if water_tree is not None and bank_tree is not None:
            touching = np.unique(bank_tree.query(written, predicate="dwithin", distance=REGION_SLACK_M)[0])
            dry = 0.0
            for index in touching.tolist():
                line = written[index]
                hits = water_tree.query(line, predicate="intersects")
                if not len(hits):
                    dry += float(line.length)
                    continue
                body = int(water.body[hits[0]])
                if body not in locals_:
                    locals_[body] = pg._local(water.union(body))
                dry += float(shapely.difference(line, locals_[body].near(line)).length)
            figures["near the bank"] = len(touching)
            figures["dry m, bank steps included"] = round(dry, 3)
        out[name] = figures
    return out

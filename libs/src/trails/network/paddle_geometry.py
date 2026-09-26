"""The line off the bank: validated offset contours of the eligible water.

Uwe's decision of 2026-09-25 moves the bank-following kayak line 15 m out into
the water. This module draws that line and proves it; nothing in the build uses
it yet. It offsets each connected eligible body whole, before any map cut, so a
lake/river interface, a delivery seam or the map edge is never a bank. Bodies
never touch one another, so offsetting them one at a time is the offset of the
whole union, and it bounds the memory by the largest body.

The contour is then cut, never re-drawn, at the places that are not a bank:

- **the lake/river interface**, where the height owner changes; both sides stay
  offset line, and the cut is a pinned vertex so the lake keeps its plane;
- **a bay cap**, where the offset closes a bay or passage it cannot enter: the
  stretch of contour that the bay's mouth, not a bank, holds at the offset
  distance, which later phases price as open water;
- **a dam disc** and **the map crop**, cut with the production rules.

Each remaining piece is simplified at 2 m with its ends pinned, written through
the page's coordinate grid and read back, and checked against two gates: every
decoded segment at least 12 m from the unsimplified bank, and the decoded piece
within 2.1 m of the raw contour. A segment that fails either, or that crosses
another piece where the raw contours do not meet, gets the raw vertex farthest
from it back, until it passes or no raw vertex is left to give.

What the gates or the water cannot settle is returned with a place rather than
repaired: bodies the offset removes whole, specks of offset under a square
metre, and contour held by a bank outside the window the source was loaded in.
"""

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from trails.network.water import DAM_CUT_M, LAKE_BODY, LAKE_LEVEL, SHORE_SIMPLIFY_M, SURFACE_CLASS, Bodies, _outside_dams

#: Uwe, 2026-09-25: one fixed distance on all three maps.
PADDLE_OFFSET_M = 15.0
#: The approved starting tolerance; refinement only ever keeps more vertices.
CONTOUR_SIMPLIFY_M = 2.0
#: The approved gates: decoded deviation from the raw contour, and clearance from the source bank.
CONTOUR_DEVIATION_M = 2.1
CONTOUR_CLEARANCE_M = 12.0
#: Implementation choice (phase 12b): a quarter circle in 32 chords. GEOS rounds a
#: fillet to whole chords, so a chord spans at most 1.5 quanta and the raw contour
#: can sit ``d * (1 - cos(3 * pi / (8 * 32)))`` = 0.010 m inside d at a headland;
#: with 8 chords it was 0.162 m (phase 12a).
CONTOUR_QUAD_SEGS = 32
#: The plan's scale for a bay worth its own branch (2d); smaller indentations are smoothed over.
BAY_REACH_M = 2 * PADDLE_OFFSET_M
#: Phase 12a's cut-off for offset parts and closed-off water: anything smaller is rounding.
RESIDUE_MIN_M2 = 1.0
#: A reach is read on the outline every metre, so it is short by at most half of that.
REACH_SAMPLE_M = 1.0
#: How much farther than d from a bay's water a contour point may be and still be held by its mouth.
CAP_TOLERANCE_M = 0.1
#: Deviation is proved on samples: a coarse pass, then a fine one wherever the
#: coarse samples cannot bound the gap between them. Distance is 1-Lipschitz,
#: so between two samples it is at most the mean of theirs plus half the gap.
COARSE_SAMPLE_M = 1.0
FINE_SAMPLE_M = 0.05
#: The page's 1e-6 degree grid moves a vertex by at most 0.062 m at these latitudes
#: (measured 0.0617 m in Malingsbo-Kloten); two raw pieces closer than twice that may
#: cross once written, whatever vertices they keep.
CONTACT_M = 0.13
#: Refinement gives back at most one raw vertex per failing segment and round.
MAX_REFINE_ROUNDS = 64

SHORE_ROLE = "shore"
CAP_ROLE = "cap"
#: What ends a piece: a closed ring has no end; the rest are the cuts above.
RING, INTERFACE, CAP, DAM, CROP = "ring", "interface", "cap", "dam", "crop"


@dataclass
class Contours:
    """The offset contours of one run and everything needed to check them.

    Attributes:
        lines: One row per piece: ``body``, ``role`` (shore or cap), the owner's
            ``LAKE_BODY``, ``LAKE_LEVEL`` and ``SURFACE_CLASS``, the ``start``
            and ``end`` cut kinds, the bank it follows (``bank_ring``,
            ``bank_from_m``, ``bank_to_m``), vertex counts, the gates' figures,
            the simplified ``geometry`` and the unsimplified ``raw``
        caps: Water the offset closes off and whose mouth becomes a cap: ``kind``
            (terminal, loop or passage), ``reach_m``, ``anchored`` and the piece
        vanished: Bodies whose whole water lies within d of a bank
        bodies: One row per body: parts, vertices, timings
        failures: Anything the gates or the water could not settle, with a location:
            ``gate``, ``crossing``, ``contact``, ``speck``, ``source edge`` or ``invalid water``
    """

    lines: gpd.GeoDataFrame
    caps: gpd.GeoDataFrame
    vanished: gpd.GeoDataFrame
    bodies: pd.DataFrame
    failures: gpd.GeoDataFrame
    crs: Any = field(default=None)


@dataclass
class _Piece:
    coords: np.ndarray
    owner: int
    role: str
    start: str = ""
    end: str = ""
    #: Raw vertices given back to settle a crossing with another piece.
    pinned: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=int))


def contours(
    bodies: Bodies,
    *,
    crs: Any,
    offset_m: float = PADDLE_OFFSET_M,
    extent: BaseGeometry | None = None,
    source_window: BaseGeometry | None = None,
    dams: np.ndarray | None = None,
    anchors: np.ndarray | None = None,
    quad_segs: int = CONTOUR_QUAD_SEGS,
    tolerance_m: float = CONTOUR_SIMPLIFY_M,
) -> Contours:
    """Offset every eligible body, cut the contour where it is not a bank, simplify and validate it.

    Args:
        bodies: The eligible water of :func:`water.eligible_bodies`, in ``crs``
        crs: A metric CRS
        offset_m: Distance of the line from the bank
        extent: Map extent in ``crs``; the contour is cut to it after offsetting
        source_window: Where the source water is known complete; a contour inside
            the extent held by a bank outside it is reported, since that bank may
            be the edge of a delivery rather than of the water
        dams: Dam and lock-gate points in ``crs``; their discs cut the contour
        anchors: Access points in ``crs`` as shapely points; a bay holding one gets a cap however small
        quad_segs: Chords per quarter circle of the reference contour
        tolerance_m: Starting simplification tolerance

    Returns:
        The contours and their checks
    """
    if offset_m <= 0:
        raise ValueError("the offset must be a positive distance")
    lines: list[dict[str, Any]] = []
    caps: list[dict[str, Any]] = []
    vanished: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    dam_tree = shapely.STRtree(dams) if dams is not None and len(dams) else None
    anchor_tree = shapely.STRtree(anchors) if anchors is not None and len(anchors) else None
    to_page, from_page = _page_round_trip(crs)
    count = int(bodies.body.max()) + 1 if len(bodies.body) else 0
    for body in range(count):
        members = bodies.body == body
        water = bodies.union(body)
        if extent is not None and not water.intersects(extent):
            continue
        summary = _body(
            body,
            water,
            bodies.polygons[members],
            bodies.owner[members],
            offset_m=offset_m,
            quad_segs=quad_segs,
            tolerance_m=tolerance_m,
            extent=extent,
            source_window=source_window,
            dam_tree=dam_tree,
            anchors=anchor_tree,
            to_page=to_page,
            from_page=from_page,
            lines=lines,
            caps=caps,
            vanished=vanished,
            failures=failures,
        )
        summary["parents"] = sorted({int(p) for p in bodies.parents[members]})
        summaries.append(summary)
    for row in vanished:
        row["classes"] = ", ".join(sorted({str(bodies.owners[o][SURFACE_CLASS]) for o in row["classes"] if o >= 0}))
    for row in lines:
        owner = row.pop("owner")
        row.update(bodies.owners[owner] if owner >= 0 else {LAKE_BODY: None, LAKE_LEVEL: np.nan, SURFACE_CLASS: None})
    line_columns = [
        "body",
        "role",
        LAKE_BODY,
        LAKE_LEVEL,
        SURFACE_CLASS,
        "start",
        "end",
        "bank_ring",
        "bank_from_m",
        "bank_to_m",
        "raw_vertices",
        "vertices",
        "refined",
        "min_clearance_m",
        "max_deviation_m",
        "deviation_bound_m",
        "raw_min_clearance_m",
        "passes",
        "segment_clearance_m",
        "segment_deviation_m",
        "raw",
        "geometry",
    ]
    frame = gpd.GeoDataFrame(pd.DataFrame(lines, columns=line_columns), geometry="geometry", crs=crs)
    frame["raw"] = gpd.GeoSeries(frame["raw"], crs=crs)
    return Contours(
        lines=frame,
        caps=gpd.GeoDataFrame(
            pd.DataFrame(caps, columns=["body", "kind", "reach_m", "anchored", "mouths", "cap_m", "geometry"]), geometry="geometry", crs=crs
        ),
        vanished=gpd.GeoDataFrame(pd.DataFrame(vanished, columns=["body", "area_ha", "classes", "geometry"]), geometry="geometry", crs=crs),
        bodies=pd.DataFrame(summaries),
        failures=gpd.GeoDataFrame(pd.DataFrame(failures, columns=["body", "kind", "detail", "geometry"]), geometry="geometry", crs=crs),
        crs=crs,
    )


def _body(
    body: int,
    water: BaseGeometry,
    polygons: np.ndarray,
    owner: np.ndarray,
    *,
    offset_m: float,
    quad_segs: int,
    tolerance_m: float,
    extent: BaseGeometry | None,
    source_window: BaseGeometry | None,
    dam_tree: shapely.STRtree | None,
    anchors: shapely.STRtree | None,
    to_page: Transformer,
    from_page: Transformer,
    lines: list[dict[str, Any]],
    caps: list[dict[str, Any]],
    vanished: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    """One connected body: offset, cut, simplify, validate; rows are appended to the lists given."""
    started = time.perf_counter()
    summary: dict[str, Any] = {"body": body, "area_ha": round(water.area / 10_000, 3), "input_vertices": int(shapely.get_num_coordinates(water))}
    if not water.is_valid:
        failures.append({"body": body, "kind": "invalid water", "detail": shapely.is_valid_reason(water), "geometry": water.representative_point()})
        return {**summary, "parts": None, "wall_s": time.perf_counter() - started}
    eroded = shapely.buffer(water, -offset_m, quad_segs=quad_segs)
    parts = [p for p in shapely.get_parts(eroded) if isinstance(p, Polygon) and not p.is_empty]
    for pool in (p for p in parts if p.area < RESIDUE_MIN_M2):
        # Where a disc of radius d only just fits, the offset leaves a speck no line can follow.
        failures.append(
            {"body": body, "kind": "speck", "detail": f"offset part of {pool.area:.4f} m² left out", "geometry": pool.representative_point()}
        )
    parts = [p for p in parts if p.area >= RESIDUE_MIN_M2]
    summary["parts"] = len(parts)
    if not parts:
        vanished.append(
            {
                "body": body,
                "area_ha": round(water.area / 10_000, 3),
                "classes": sorted({int(o) for o in owner}),  # owner indices until contours() names them
                "geometry": water.representative_point(),
            }
        )
        return {**summary, "raw_vertices": 0, "vertices": 0, "wall_s": time.perf_counter() - started}
    bank = _segments(water)
    bank_tree = shapely.STRtree(bank.lines)
    first_cap = len(caps)
    residue = _caps(body, water, parts, offset_m=offset_m, quad_segs=quad_segs, anchors=anchors, caps=caps)
    owners = _owners(polygons, owner)
    pieces: list[_Piece] = []
    for part in parts:
        for ring in (part.exterior, *part.interiors):
            coords = np.asarray(ring.coords)[:, :2]
            pieces.extend(_cut(coords, owners, residue, offset_m=offset_m))
    pieces = _cut_artificial(pieces, dam_tree=dam_tree, extent=extent)
    summary["raw_vertices"] = int(sum(len(p.coords) for p in pieces))
    if residue:
        # Each cap piece belongs to the closed-off water nearest it.
        tree = shapely.STRtree(residue)
        for piece in pieces:
            if piece.role == CAP_ROLE:
                row = caps[first_cap + int(tree.nearest(LineString(piece.coords)))]
                row["mouths"] += 1
                row["cap_m"] = round(row["cap_m"] + LineString(piece.coords).length, 3)
    rows = [_validated(piece, bank, bank_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page) for piece in pieces]
    raw_lines = [LineString(piece.coords) for piece in pieces]
    for _ in range(MAX_REFINE_ROUNDS):
        crossings = _crossings([line for _, line in rows], raw_lines)
        if not crossings:
            break
        # Two pieces simplified apart may cross; each gives back the raw vertex its crossing segment dropped farthest.
        touched = set()
        for one, other, where in crossings:
            for index in (one, other):
                keep = rows[index][0]["keep"]
                segment = int(np.argmin(shapely.distance(where, _edges(shapely.get_coordinates(rows[index][1])))))
                first, last = keep[segment], keep[segment + 1]
                if last - first < 2:
                    continue
                raw = pieces[index].coords
                farthest = first + 1 + int(np.argmax(_distance_to_segment(raw[first + 1 : last], raw[first], raw[last])))
                pieces[index].pinned = np.union1d(np.union1d(pieces[index].pinned, keep), [farthest])
                touched.add(index)
        if not touched:
            break
        for index in touched:
            rows[index] = _validated(pieces[index], bank, bank_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page)
    for _, _, where in _crossings([line for _, line in rows], raw_lines):
        failures.append({"body": body, "kind": "crossing", "detail": "simplified pieces cross where the raw contour does not", "geometry": where})
    for _, _, where in _crossings([line for _, line in rows], raw_lines, contacts=True):
        # Two parts of the offset all but touch: the water there is barely wider than 2d.
        failures.append({"body": body, "kind": "contact", "detail": f"raw pieces within {CONTACT_M} m cross on the page's grid", "geometry": where})
    decoded_lines = [line for _, line in rows]
    for piece, (row, _) in zip(pieces, rows, strict=True):
        row["body"] = body
        if not row["passes"]:
            failures.append(
                {
                    "body": body,
                    "kind": "gate",
                    "detail": f"clearance {row['min_clearance_m']:.3f} m, deviation bound {row['deviation_bound_m']:.3f} m",
                    "geometry": row["worst"],
                }
            )
        del row["worst"], row["keep"]
        if source_window is not None:
            held = _held_outside(piece.coords, bank, bank_tree, source_window, extent)
            if held is not None:
                failures.append({"body": body, "kind": "source edge", "detail": "contour held by a bank outside the source window", "geometry": held})
        lines.append(row)
    summary["pieces"] = len(pieces)
    summary["vertices"] = int(sum(shapely.get_num_coordinates(line) for line in decoded_lines))
    summary["wall_s"] = time.perf_counter() - started
    return summary


@dataclass
class _Bank:
    lines: np.ndarray
    ring: np.ndarray
    station: np.ndarray


def _segments(water: BaseGeometry) -> _Bank:
    """Every bank segment of a body with its ring and the station of its start along that ring."""
    lines, rings, stations = [], [], []
    ring_id = 0
    for polygon in shapely.get_parts(water):
        for ring in (polygon.exterior, *polygon.interiors):
            coords = np.asarray(ring.coords)[:, :2]
            lengths = np.hypot(*np.diff(coords, axis=0).T)
            lines.append(_edges(coords))
            rings.append(np.full(len(coords) - 1, ring_id))
            stations.append(np.concatenate(([0.0], np.cumsum(lengths)[:-1])))
            ring_id += 1
    return _Bank(np.concatenate(lines), np.concatenate(rings), np.concatenate(stations))


def _edges(coords: np.ndarray) -> np.ndarray:
    """The segments of a vertex run as separate lines."""
    return np.asarray(shapely.linestrings(np.stack([coords[:-1], coords[1:]], axis=1)), dtype=object)


def _generators(points: np.ndarray, bank: _Bank, tree: shapely.STRtree) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The nearest bank point of each point: its ring, its station along the ring, and the point."""
    geometries = shapely.points(points)
    (_, index), _ = tree.query_nearest(geometries, return_distance=True, all_matches=False)
    along = shapely.line_locate_point(bank.lines[index], geometries)
    nearest = shapely.line_interpolate_point(bank.lines[index], along)
    return bank.ring[index], bank.station[index] + along, nearest


@dataclass
class _Owners:
    polygons: np.ndarray
    owner: np.ndarray
    tree: shapely.STRtree


def _owners(polygons: np.ndarray, owner: np.ndarray) -> _Owners:
    return _Owners(polygons, owner, shapely.STRtree(polygons))


def _owner_at(points: np.ndarray, owners: _Owners) -> np.ndarray:
    """The height owner of each point; where two delivery polygons overlap the lake, listed first, wins."""
    found = np.full(len(points), -1, dtype=int)
    point_index, polygon_index = owners.tree.query(shapely.points(points), predicate="intersects")
    candidates = owners.owner[polygon_index]
    order = np.lexsort((np.where(candidates < 0, np.iinfo(int).max, candidates), point_index))
    point_index, candidates = point_index[order], candidates[order]
    first = np.unique(point_index, return_index=True)[1]
    found[point_index[first]] = candidates[first]
    return found


def _caps(
    body: int,
    water: BaseGeometry,
    parts: list[Polygon],
    *,
    offset_m: float,
    quad_segs: int,
    anchors: shapely.STRtree | None,
    caps: list[dict[str, Any]],
) -> list[BaseGeometry]:
    """The water the offset closes off and whose mouth must not become shore.

    A disc of radius d rolled through the surviving water reaches everything
    but bays narrower than 2d, closed island passages and the like. Such a
    piece is a bay worth its own branch when it reaches ``BAY_REACH_M`` beyond
    the reachable water or holds an access anchor; the contour its mouth holds
    at distance d is then a cap. Smaller indentations are smoothed over and
    their contour stays shore.
    """
    opened_parts = [shapely.buffer(part, offset_m, quad_segs=quad_segs) for part in parts]
    opened = shapely.union_all(opened_parts)
    residue = [p for p in shapely.get_parts(shapely.difference(water, opened)) if isinstance(p, Polygon) and p.area >= RESIDUE_MIN_M2]
    if not residue:
        return []
    tree = shapely.STRtree(opened_parts)
    # Distances to a large polygon are linear in its vertices; to its indexed edges they are not.
    edges = _edge_tree(opened_parts)
    kept: list[BaseGeometry] = []
    for piece in residue:
        # The farthest water is often mid-passage, between vertices: sample the outline.
        outline = shapely.points(shapely.get_coordinates(shapely.segmentize(piece.boundary, REACH_SAMPLE_M)))
        _, distances = edges.query_nearest(outline, return_distance=True, all_matches=False)
        reach = float(distances.max())
        anchored = False
        if anchors is not None:
            # Graph anchors sit on the 5 m-simplified shore, up to that far off the source bank; one
            # belongs to the closed-off water when it is nearer to it than to the reachable water.
            near_anchors = anchors.geometries[anchors.query(piece, predicate="dwithin", distance=SHORE_SIMPLIFY_M)]
            anchored = bool(len(near_anchors) and (shapely.distance(near_anchors, piece) < shapely.distance(near_anchors, opened)).any())
        if reach < BAY_REACH_M and not anchored:
            continue
        near = tree.query(piece, predicate="dwithin", distance=0.05)
        if len(near) >= 2:
            kind = "passage"
        else:
            contact = None
            if len(near):
                # Grow only the reachable water around this piece: growing a whole sea costs minutes per piece.
                local = shapely.intersection(opened_parts[int(near[0])], shapely.buffer(shapely.envelope(piece), 1.0))
                contact = shapely.line_merge(shapely.intersection(piece.boundary, shapely.buffer(local, 0.05)))
            arcs = [a for a in shapely.get_parts(contact) if a.length > 0.1] if contact is not None else []
            kind = "loop" if len(arcs) >= 2 else "terminal"
        caps.append({"body": body, "kind": kind, "reach_m": round(reach, 3), "anchored": anchored, "mouths": 0, "cap_m": 0.0, "geometry": piece})
        kept.append(piece)
    return kept


def _edge_tree(polygons: Sequence[BaseGeometry]) -> shapely.STRtree:
    """Every edge of the polygons' outlines, for distances from points outside them."""
    rings = shapely.get_parts(shapely.boundary(np.asarray(polygons, dtype=object)))
    return shapely.STRtree(np.concatenate([_edges(shapely.get_coordinates(r)) for r in rings]))


def _cut(coords: np.ndarray, owners: _Owners, residue: list[BaseGeometry], *, offset_m: float) -> list[_Piece]:
    """Cut one closed raw ring where its height owner or its role changes.

    Owner changes fall inside segments and get an exact interface vertex; role
    changes fall on raw vertices, which are dense on the arcs a cap is made of.
    """
    coords = _with_interfaces(coords, owners)
    points = shapely.points(coords)
    if residue:
        _, distances = _edge_tree(residue).query_nearest(points, return_distance=True, all_matches=False)
        held = distances <= offset_m + CAP_TOLERANCE_M
    else:
        held = np.zeros(len(coords), dtype=bool)
    middles = (coords[:-1] + coords[1:]) / 2
    segment_owner = _owner_at(middles, owners)
    segment_role = np.where(held[:-1] & held[1:], CAP_ROLE, SHORE_ROLE)
    labels = list(zip(segment_owner.tolist(), segment_role.tolist(), strict=True))
    changes = [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]
    if labels[0] != labels[-1]:
        changes = [0, *changes]
    if not changes:
        return [_Piece(coords, segment_owner[0], str(segment_role[0]), RING, RING)]
    # Start the ring at a change so that no piece wraps round its closing vertex.
    first = changes[0]
    order = np.r_[np.arange(first, len(coords) - 1), np.arange(0, first + 1)]
    ring = coords[order]
    starts = [c - first if c >= first else c - first + len(coords) - 1 for c in changes]
    starts.append(len(coords) - 1)
    pieces = []
    for one, other in zip(starts[:-1], starts[1:], strict=True):
        label = labels[(one + first) % (len(coords) - 1)]
        pieces.append(_Piece(ring[one : other + 1], label[0], label[1]))
    for index, piece in enumerate(pieces):
        before, after = pieces[index - 1], pieces[(index + 1) % len(pieces)]
        piece.start = INTERFACE if before.owner != piece.owner else CAP
        piece.end = INTERFACE if after.owner != piece.owner else CAP
    return pieces


def _with_interfaces(coords: np.ndarray, owners: _Owners) -> np.ndarray:
    """Insert the exact point where the ring crosses from one height owner to another."""
    vertex_owner = _owner_at(coords, owners)
    crossing = np.flatnonzero(vertex_owner[:-1] != vertex_owner[1:])
    if not len(crossing):
        return coords
    inserted: dict[int, list[np.ndarray]] = {}
    for i in crossing:
        segment = LineString(coords[i : i + 2])
        cuts: list[np.ndarray] = []
        for polygon in owners.polygons[owners.tree.query(segment, predicate="intersects")]:
            boundary = shapely.intersection(segment, polygon.boundary)
            cuts.extend(shapely.get_coordinates(boundary)[:, :2])
        if not cuts:
            continue
        cuts_array = np.unique(np.asarray(cuts), axis=0)
        along = np.hypot(*(cuts_array - coords[i]).T)
        inside = (along > 0) & (along < np.hypot(*(coords[i + 1] - coords[i])))
        inserted[int(i)] = list(cuts_array[inside][np.argsort(along[inside])])
    out: list[np.ndarray] = []
    for index in range(len(coords)):
        out.append(coords[index])
        out.extend(inserted.get(index, []))
    return np.asarray(out)


def _cut_artificial(pieces: list[_Piece], *, dam_tree: shapely.STRtree | None, extent: BaseGeometry | None) -> list[_Piece]:
    """Cut the pieces at dam discs and the map extent, marking each new end with what made it."""
    boundary = extent.boundary if extent is not None else None
    out = []
    for piece in pieces:
        line = LineString(piece.coords)
        kept = _outside_dams(line, dam_tree) if dam_tree is not None else [line]
        if extent is not None:
            kept = [g for part in kept for g in shapely.get_parts(shapely.intersection(part, extent)) if isinstance(g, LineString)]
        if len(kept) > 1 and piece.start == RING:
            # A ring cut elsewhere is still one line through its closing vertex.
            kept = [g for g in shapely.get_parts(shapely.line_merge(shapely.MultiLineString(kept))) if isinstance(g, LineString)]
        for part in kept:
            if part.length <= 0:
                continue
            coords = np.asarray(part.coords)[:, :2]
            if part.is_closed and piece.start == RING:
                out.append(_Piece(coords, piece.owner, piece.role, RING, RING))
                continue
            ends = []
            for point, inherited, source in ((coords[0], piece.start, piece.coords[0]), (coords[-1], piece.end, piece.coords[-1])):
                if boundary is not None and shapely.distance(Point(point), boundary) < 1e-6:
                    ends.append(CROP)
                elif dam_tree is not None and abs(_nearest_distance(dam_tree, point) - DAM_CUT_M) < 1e-6:
                    ends.append(DAM)
                elif inherited != RING and np.array_equal(point, source):
                    ends.append(inherited)
                else:
                    ends.append("unknown")
            out.append(_Piece(coords, piece.owner, piece.role, ends[0], ends[1]))
    return out


def _nearest_distance(tree: shapely.STRtree, point: np.ndarray) -> float:
    _, distance = tree.query_nearest([Point(point)], return_distance=True, all_matches=False)
    return float(distance[0])


def simplify_pinned(coords: np.ndarray, tolerance: float) -> np.ndarray:
    """Douglas–Peucker with both ends kept; a closed ring keeps three vertices so it cannot collapse.

    Args:
        coords: ``(n, 2)`` vertices; a ring repeats its first vertex at the end
        tolerance: Largest distance of a dropped vertex from the kept segment spanning it

    Returns:
        Sorted indices of the vertices kept
    """
    n = len(coords)
    keep = np.zeros(n, dtype=bool)
    keep[[0, n - 1]] = True
    if n > 3 and np.array_equal(coords[0], coords[-1]):
        # A ring's Douglas–Peucker has no segment to measure from; pin the vertex
        # farthest from its start and the one farthest from that chord.
        far = int(np.argmax(np.hypot(*(coords - coords[0]).T)))
        keep[far] = True
        rest = np.setdiff1d(np.arange(1, n - 1), [far])
        if len(rest):
            keep[int(rest[np.argmax(_distance_to_segment(coords[rest], coords[0], coords[far]))])] = True
    anchors = np.flatnonzero(keep)
    stack = list(zip(anchors[:-1].tolist(), anchors[1:].tolist(), strict=True))
    for _ in range(2 * n):
        if not stack:
            break
        one, other = stack.pop()
        if other - one < 2:
            continue
        inner = coords[one + 1 : other]
        distances = _distance_to_segment(inner, coords[one], coords[other])
        worst = int(np.argmax(distances))
        if distances[worst] > tolerance:
            middle = one + 1 + worst
            keep[middle] = True
            stack.extend(((one, middle), (middle, other)))
    else:
        raise RuntimeError("simplification did not finish within its bound")
    return np.flatnonzero(keep)


def _distance_to_segment(points: np.ndarray, one: np.ndarray, other: np.ndarray) -> np.ndarray:
    delta = other - one
    squared = float(delta @ delta)
    if squared == 0:
        return np.asarray(np.hypot(*(points - one).T))
    t = np.clip(((points - one) @ delta) / squared, 0.0, 1.0)
    return np.asarray(np.hypot(*(points - (one + t[:, None] * delta)).T))


def _page_round_trip(crs: Any) -> tuple[Transformer, Transformer]:
    return Transformer.from_crs(crs, "EPSG:4326", always_xy=True), Transformer.from_crs("EPSG:4326", crs, always_xy=True)


def decoded(coords: np.ndarray, to_page: Transformer, from_page: Transformer) -> np.ndarray:
    """Write metric vertices on the page's degree grid and read them back, as the browser will see them."""
    from trails.visualization.encoding import DEFAULT_COORDINATE_QUANTUM

    lon, lat = to_page.transform(coords[:, 0], coords[:, 1])
    grid = np.rint(np.c_[lon, lat] / DEFAULT_COORDINATE_QUANTUM) * DEFAULT_COORDINATE_QUANTUM
    x, y = from_page.transform(grid[:, 0], grid[:, 1])
    return np.column_stack([x, y])


def _validated(
    piece: _Piece,
    bank: _Bank,
    bank_tree: shapely.STRtree,
    *,
    tolerance_m: float,
    to_page: Transformer,
    from_page: Transformer,
) -> tuple[dict[str, Any], LineString]:
    """Simplify one piece, then give back raw vertices until its decoded form passes both gates."""
    raw = piece.coords
    raw_line = LineString(raw)
    raw_segments = _edges(raw)
    raw_tree = shapely.STRtree(raw_segments)
    (_, _), raw_gaps = bank_tree.query_nearest(raw_segments, return_distance=True, all_matches=False)
    keep = simplify_pinned(raw, tolerance_m)
    initial = len(keep)
    if len(piece.pinned):
        keep = np.union1d(keep, piece.pinned)
    for _ in range(MAX_REFINE_ROUNDS):
        coords = decoded(raw[keep], to_page, from_page)
        segments = _edges(coords)
        (_, _), clearance = bank_tree.query_nearest(segments, return_distance=True, all_matches=False)
        forward, forward_at = _deviation_bound(coords, raw_tree)
        backward, backward_at = _deviation_bound(raw, shapely.STRtree(segments))
        # A raw segment's bound belongs to the simplified segment spanning it.
        span = np.searchsorted(keep, np.arange(len(raw) - 1), side="right") - 1
        backward_by_segment = np.zeros(len(keep) - 1)
        np.maximum.at(backward_by_segment, span, backward)
        failing = (clearance < CONTOUR_CLEARANCE_M) | (forward > CONTOUR_DEVIATION_M) | (backward_by_segment > CONTOUR_DEVIATION_M)
        if not failing.any():
            break
        added = []
        for k in np.flatnonzero(failing):
            one, other = keep[k], keep[k + 1]
            if other - one < 2:
                continue
            distances = _distance_to_segment(raw[one + 1 : other], raw[one], raw[other])
            added.append(one + 1 + int(np.argmax(distances)))
        if not added:
            break
        keep = np.union1d(keep, added)
    worst_segment = int(np.argmax(np.maximum(forward, backward_by_segment) - np.minimum(clearance - CONTOUR_CLEARANCE_M, 0)))
    ring, station, _ = _generators(raw[[0, -1]], bank, bank_tree)
    decoded_line = LineString(coords)
    row = {
        "owner": piece.owner,
        "role": piece.role,
        "start": piece.start,
        "end": piece.end,
        "bank_ring": int(ring[0]) if ring[0] == ring[1] else -1,
        "bank_from_m": round(float(station[0]), 2),
        "bank_to_m": round(float(station[1]), 2),
        "raw_vertices": len(raw),
        "vertices": len(keep),
        "refined": len(keep) - initial,
        "min_clearance_m": float(clearance.min()),
        "max_deviation_m": float(max(forward_at.max(), backward_at.max())),
        "deviation_bound_m": float(max(forward.max(), backward.max())),
        "raw_min_clearance_m": float(raw_gaps.min()),
        "passes": not failing.any(),
        "segment_clearance_m": clearance,
        "segment_deviation_m": np.maximum(forward, backward_by_segment),
        "worst": Point(coords[worst_segment : worst_segment + 2].mean(axis=0)),
        "keep": keep,
        "raw": raw_line,
        "geometry": decoded_line,
    }
    return row, decoded_line


def _deviation_bound(coords: np.ndarray, tree: shapely.STRtree) -> tuple[np.ndarray, np.ndarray]:
    """Per segment of ``coords``: a proven upper bound on its distance from the tree's line, and the largest sample.

    Samples every ``COARSE_SAMPLE_M``; a gap whose bound, the mean of its ends
    plus half its length, exceeds the gate is sampled again every
    ``FINE_SAMPLE_M``.
    """
    lengths = np.hypot(*np.diff(coords, axis=0).T)
    bounds = np.zeros(len(lengths))
    sampled = np.zeros(len(lengths))
    for step in (COARSE_SAMPLE_M, FINE_SAMPLE_M):
        todo = np.flatnonzero(bounds > CONTOUR_DEVIATION_M) if step == FINE_SAMPLE_M else np.arange(len(lengths))
        if not len(todo):
            break
        counts = np.maximum(np.ceil(lengths[todo] / step).astype(int), 1)
        owner = np.repeat(todo, counts + 1)
        t = np.concatenate([np.linspace(0.0, 1.0, c + 1) for c in counts])
        points = coords[owner] + t[:, None] * (coords[owner + 1] - coords[owner])
        (_, _), distance = tree.query_nearest(shapely.points(points), return_distance=True, all_matches=False)
        gap = lengths[owner] / np.repeat(counts, counts + 1)
        pair = np.r_[owner[1:] == owner[:-1], False]
        between = np.where(pair, (distance + np.r_[distance[1:], 0.0] + gap) / 2, 0.0)
        segment_bound = np.zeros(len(lengths))
        segment_max = np.zeros(len(lengths))
        np.maximum.at(segment_bound, owner, np.maximum(between, distance))
        np.maximum.at(segment_max, owner, distance)
        bounds[todo] = segment_bound[todo]
        sampled[todo] = segment_max[todo]
    return bounds, sampled


def _held_outside(coords: np.ndarray, bank: _Bank, tree: shapely.STRtree, window: BaseGeometry, extent: BaseGeometry | None) -> Point | None:
    """The first raw vertex inside the extent whose nearest bank lies outside the source window, if any."""
    _, _, nearest = _generators(coords, bank, tree)
    outside = ~shapely.intersects(window, nearest)
    if extent is not None:
        outside &= shapely.intersects(extent, shapely.points(coords))
    hits = np.flatnonzero(outside)
    return Point(coords[hits[0]]) if len(hits) else None


def _crossings(decoded_lines: list[LineString], raw_lines: list[LineString], *, contacts: bool = False) -> list[tuple[int, int, Point]]:
    """Where two simplified pieces meet other than at a shared end or where their raw pieces meet too.

    Raw pieces that pass within ``CONTACT_M`` of each other without meeting may
    cross once written on the page's grid, and no vertex can undo that. Those
    are contacts: returned instead of crossings when ``contacts`` is set.
    """
    if len(decoded_lines) < 2:
        return []
    tree = shapely.STRtree(decoded_lines)
    left, right = tree.query(decoded_lines, predicate="intersects")
    found = []
    for one, other in zip(left.tolist(), right.tolist(), strict=True):
        if one >= other:
            continue
        meet = shapely.intersection(decoded_lines[one], decoded_lines[other])
        ends = shapely.union(decoded_lines[one].boundary, decoded_lines[other].boundary)
        raw_meet = shapely.intersection(raw_lines[one], raw_lines[other])
        for point in shapely.get_parts(meet):
            if point.is_empty:
                continue
            if not ends.is_empty and shapely.dwithin(point, ends, 1e-6):
                continue
            if not raw_meet.is_empty and shapely.dwithin(point, raw_meet, CONTOUR_DEVIATION_M):
                continue
            around = shapely.buffer(point, CONTOUR_DEVIATION_M)
            touching = shapely.distance(shapely.intersection(raw_lines[one], around), shapely.intersection(raw_lines[other], around)) <= CONTACT_M
            if touching == contacts:
                found.append((one, other, shapely.centroid(point)))
    return found


def offset_error_m(offset_m: float, quad_segs: int) -> float:
    """How far inside d a GEOS fillet chord can lie: at most 1.5 angle quanta per chord."""
    return offset_m * (1 - math.cos(0.75 * (math.pi / 2) / quad_segs))

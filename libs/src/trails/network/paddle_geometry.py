"""The line off the bank: validated offset contours of the eligible water, and the middle where they cannot go.

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

Where the offset does not carry the water — narrows under 2d, closed-off bays
and passages, island gaps and bodies it removes whole — the line runs down the
middle instead (phase 12c). The middle is the medial axis of the water with a
radius below d, approximated by the Voronoi diagram of the bank sampled every
metre, and it meets the contour exactly where its radius reaches d. It is kept
through every passage and round every island, and into a bay when its branch
reaches 2d from the contour or holds an access anchor; the rest is pruned and
reported. A contour stretch held by two shoulders of kept closed-off water is
an open-water crossing, not shore.
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

from trails.network.water import (
    DAM_CUT_M,
    LAKE_BODY,
    LAKE_LEVEL,
    OPEN_WATER,
    SHORE,
    SHORE_SIMPLIFY_M,
    SURFACE_CLASS,
    Bodies,
    _outside_dams,
)

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
GRID_MOVE_M = 0.062
CONTACT_M = 0.13
#: A segment ending on a bank vertex can graze the outline by floating-point noise (1.2e-10 m
#: measured); dry length up to this counts as none, and the exact figure is still reported.
DRY_NOISE_M = 1e-6
#: Refinement gives back at most one raw vertex per failing segment and round.
MAX_REFINE_ROUNDS = 64

#: The plan's source for the centre line and its transitions (§1.5), paddled at factor 1.
NARROW_WATER = "Narrow water"
#: The approved middle gate: at most this far from the true middle, and at most this share of the local width.
MIDDLE_LIMIT_M = 1.0
MIDDLE_SHARE = 0.1
#: Implementation choice (phase 12c): the bank is sampled at most every metre,
#: symmetrically about each vertex, and the Voronoi diagram of the samples stands
#: in for the segments'. Between parallel banks w apart it errs by at most
#: step² / (8w); where the middle gate fails anyway, the bank around the failing
#: node is sampled at half its step, up to this many times.
CENTRE_SAMPLE_M = 1.0
CENTRE_HALVINGS = 7
#: Implementation choice: the medial construction runs in square tiles, so no
#: triangulation holds a whole large body; each tile owns the edges whose middle
#: it contains and recomputes those within this band of its border as a witness.
TILE_M = 1000.0
TILE_BAND_M = 2.0
#: A contour vertex whose nearest bank point moves more than the vertex does, by
#: this much, is where the medial axis leaves the contour.
JUMP_M = 0.5
#: Implementation choice: a jump between bank points closer than this along their
#: ring seeds no centre line of its own. The branch behind it is at most about
#: d plus half that bank, 25 m, short of the 2d a bay needs; wider jumps, jumps
#: between two rings and all closed-off water seed the construction.
JUMP_SEPARATION_M = 20.0
#: Implementation choice: an anchor is on the kept network when a kept line passes within its own
#: radius there plus this, so its disc all but reaches the anchor; the step-dependent stub a
#: convex corner casts then keeps no branch of its own.
ANCHOR_BALL_M = 1.0
#: Implementation choice: an end no contour holds is tied through the speck beside it, or to
#: another piece of the middle, this near.
FALSE_JOIN_REACH_M = 2.0
#: Implementation choice: an end farther than ``JOIN_SNAP_M`` from the raw contour but within
#: this gets a straight transition to it; beside a speck of offset, or where the offset's chords
#: part two pieces a disc only just joins, the middle meets radius d up to a couple of metres off.
TRANSITION_M = 2.0
#: A join is where the medial axis meets the raw contour; within this it is moved onto it.
JOIN_SNAP_M = 0.1
#: A sample id is its segment times this plus its index in the segment; no segment is sampled this often.
SAMPLE_STRIDE = 1 << 24
#: The most a vertex's distance to its samples may exceed its distance to the bank and still be a
#: sampling error: step² / (8r) is 0.008 m at a 1 m step and r = 15 m; this leaves room for corners.
OVERSTATEMENT_M = 0.1
#: Implementation choice: at most this many local halvings for an edge cut at the water's edge; a
#: pinch it does not resolve is tied through instead.
BANK_END_HALVINGS = 3
#: The growth of the medial windows when a kept branch runs out of them.
MAX_GROWTH_ROUNDS = 3

SHORE_ROLE = "shore"
CAP_ROLE = "cap"
NARROW_ROLE = "narrow"
#: What ends a piece: a closed ring has no end; the rest are the cuts above.
RING, INTERFACE, CAP, DAM, CROP = "ring", "interface", "cap", "dam", "crop"
#: What ends a centre piece besides those: a join with the contour, a junction of
#: three or more centre lines, a branch end at the bank, an access anchor.
JOIN, JUNCTION, END, ANCHOR = "join", "junction", "end", "anchor"
#: Why a centre edge is kept: a through passage between two joins, a loop round an
#: island, the whole of a vanished body, a bay of at least 2d, the way to an anchor.
PASSAGE, LOOP, VANISHED, BAY, ANCHORED, ISOLATED = "passage", "loop", "vanished", "bay", "anchor", "isolated"


@dataclass
class Contours:
    """The offset contours and centre lines of one run and everything needed to check them.

    Attributes:
        lines: One row per contour piece: ``body``, ``role`` (shore or cap),
            ``source`` (Shore, or Open water for a cap held by two shoulders),
            the owner's ``LAKE_BODY``, ``LAKE_LEVEL`` and ``SURFACE_CLASS``, the
            ``start`` and ``end`` cut kinds, the bank it follows (``bank_ring``,
            ``bank_from_m``, ``bank_to_m``), vertex counts, the gates' figures,
            the simplified ``geometry`` and the unsimplified ``raw``
        caps: Kept closed-off water whose mouth becomes a cap: ``kind``
            (terminal, loop or passage), ``reach_m``, ``anchored``, ``kept_by``
            (the centre category that keeps it), ``closed`` (its index among the
            body's closed-off pieces, as ``anchors`` counts them) and the piece
        vanished: Bodies whose whole water lies within d of a bank
        bodies: One row per body: parts, vertices, timings, the medial construction's figures
        failures: Anything the gates or the water could not settle, with a location.
            Gates: ``gate`` (contour), ``middle``, ``dry``, ``dam``, ``crossing``,
            ``join``, ``isolated``, ``window``, ``cap not kept``, ``invalid water``.
            Reported for later phases: ``contact`` (two written lines within the
            grid's reach of each other), ``speck``, ``source edge``, ``anchor
            without branch``, ``cap dropped`` (a phase-12b anchored cap no kept
            branch enters)
        centre: One row per centre piece, all Narrow water: ``body``, ``category``
            (passage, loop, vanished, bay, anchor), the owner's columns, ``start``
            and ``end`` kinds, vertex counts, ``transition_m`` (the part outside
            closed-off water), the middle and containment figures, ``raw`` and ``geometry``
        nodes: The kept network's joins with the contour, junctions, branch ends and
            anchor nodes: ``body``, ``kind``, ``radius_m``, ``middle_m``, ``geometry``
        pruned: One row per pruned branch: ``body``, ``category`` (bay, off a join;
            side, off the centre), ``longest_m``, ``total_m``, and the way from its
            attachment to its farthest end as ``geometry``
        anchors: The access anchors pruning read, one row per anchor in closed-off
            water: ``anchor`` (index into the anchors given), ``body``, ``closed``
            (its piece), ``node_m`` (distance to its centre node), ``kept`` and the node
    """

    lines: gpd.GeoDataFrame
    caps: gpd.GeoDataFrame
    vanished: gpd.GeoDataFrame
    bodies: pd.DataFrame
    failures: gpd.GeoDataFrame
    centre: gpd.GeoDataFrame
    nodes: gpd.GeoDataFrame
    pruned: gpd.GeoDataFrame
    anchors: gpd.GeoDataFrame
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


@dataclass
class _Rows:
    lines: list[dict[str, Any]] = field(default_factory=list)
    caps: list[dict[str, Any]] = field(default_factory=list)
    vanished: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    centre: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    pruned: list[dict[str, Any]] = field(default_factory=list)
    anchors: list[dict[str, Any]] = field(default_factory=list)


LINE_COLUMNS = [
    "body",
    "role",
    "source",
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
CENTRE_COLUMNS = [
    "body",
    "role",
    "source",
    "category",
    LAKE_BODY,
    LAKE_LEVEL,
    SURFACE_CLASS,
    "start",
    "end",
    "raw_vertices",
    "plain_vertices",
    "vertices",
    "refined",
    "transition_m",
    "raw_middle_max_m",
    "middle_max_m",
    "middle_share_max",
    "decoded_middle_share_max",
    "sub_metre",
    "sub_metre_grid_excess_m",
    "dry_m",
    "decoded_dry_m",
    "decoded_excursion_m",
    "dam_clearance_m",
    "passes",
    "raw",
    "geometry",
]


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
    sample_m: float = CENTRE_SAMPLE_M,
    tile_m: float = TILE_M,
) -> Contours:
    """Offset every eligible body, run the middle where the offset cannot go, cut, simplify and validate both.

    Args:
        bodies: The eligible water of :func:`water.eligible_bodies`, in ``crs``
        crs: A metric CRS
        offset_m: Distance of the line from the bank
        extent: Map extent in ``crs``; the lines are cut to it after offsetting
        source_window: Where the source water is known complete; a contour inside
            the extent held by a bank outside it is reported, since that bank may
            be the edge of a delivery rather than of the water
        dams: Dam and lock-gate points in ``crs``; their discs cut both lines
        anchors: Access points in ``crs`` as shapely points; closed-off water holding
            one gets its centre branch and its cap however small
        quad_segs: Chords per quarter circle of the reference contour
        tolerance_m: Starting simplification tolerance
        sample_m: Starting bank sampling step of the medial construction
        tile_m: Side of the medial construction's tiles

    Returns:
        The contours, the centre lines and their checks
    """
    if offset_m <= 0:
        raise ValueError("the offset must be a positive distance")
    rows = _Rows()
    summaries: list[dict[str, Any]] = []
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
            sample_m=sample_m,
            tile_m=tile_m,
            extent=extent,
            source_window=source_window,
            dam_tree=dam_tree,
            anchors=anchor_tree,
            to_page=to_page,
            from_page=from_page,
            rows=rows,
        )
        summary["parents"] = sorted({int(p) for p in bodies.parents[members]})
        summaries.append(summary)
    for row in rows.vanished:
        row["classes"] = ", ".join(sorted({str(bodies.owners[o][SURFACE_CLASS]) for o in row["classes"] if o >= 0}))
    for row in (*rows.lines, *rows.centre):
        owner = row.pop("owner")
        row.update(bodies.owners[owner] if owner >= 0 else {LAKE_BODY: None, LAKE_LEVEL: np.nan, SURFACE_CLASS: None})

    def frame(records: list[dict[str, Any]], columns: list[str]) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(pd.DataFrame(records, columns=columns), geometry="geometry", crs=crs)

    lines = frame(rows.lines, LINE_COLUMNS)
    lines["raw"] = gpd.GeoSeries(lines["raw"], crs=crs)
    centre = frame(rows.centre, CENTRE_COLUMNS)
    centre["raw"] = gpd.GeoSeries(centre["raw"], crs=crs)
    return Contours(
        lines=lines,
        caps=frame(rows.caps, ["body", "kind", "reach_m", "anchored", "kept_by", "closed", "mouths", "cap_m", "geometry"]),
        vanished=frame(rows.vanished, ["body", "area_ha", "classes", "geometry"]),
        bodies=pd.DataFrame(summaries),
        failures=frame(rows.failures, ["body", "kind", "detail", "geometry"]),
        centre=centre,
        nodes=frame(rows.nodes, ["body", "kind", "degree", "radius_m", "middle_m", "geometry"]),
        pruned=frame(rows.pruned, ["body", "category", "longest_m", "total_m", "geometry"]),
        anchors=frame(rows.anchors, ["anchor", "body", "closed", "node_m", "kept", "geometry"]),
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
    sample_m: float,
    tile_m: float,
    extent: BaseGeometry | None,
    source_window: BaseGeometry | None,
    dam_tree: shapely.STRtree | None,
    anchors: shapely.STRtree | None,
    to_page: Transformer,
    from_page: Transformer,
    rows: _Rows,
) -> dict[str, Any]:
    """One connected body: offset, centre lines, cut, simplify, validate; rows are appended to ``rows``."""
    started = time.perf_counter()
    summary: dict[str, Any] = {"body": body, "area_ha": round(water.area / 10_000, 3), "input_vertices": int(shapely.get_num_coordinates(water))}
    failures = rows.failures
    if not water.is_valid:
        failures.append({"body": body, "kind": "invalid water", "detail": shapely.is_valid_reason(water), "geometry": water.representative_point()})
        return {**summary, "parts": None, "wall_s": time.perf_counter() - started}
    eroded = shapely.buffer(water, -offset_m, quad_segs=quad_segs)
    found = [p for p in shapely.get_parts(eroded) if isinstance(p, Polygon) and not p.is_empty]
    specks = [p for p in found if p.area < RESIDUE_MIN_M2]
    for pool in specks:
        # Where a disc of radius d only just fits, the offset leaves a speck no line can follow.
        failures.append(
            {"body": body, "kind": "speck", "detail": f"offset part of {pool.area:.4f} m² left out", "geometry": pool.representative_point()}
        )
    parts = [p for p in found if p.area >= RESIDUE_MIN_M2]
    summary["parts"] = len(parts)
    bank = _segments(water)
    bank_tree = shapely.STRtree(bank.lines)
    owners = _owners(polygons, owner)
    shapely.prepare(water)
    rings = [np.asarray(ring.coords)[:, :2] for part in parts for ring in (part.exterior, *part.interiors)]
    if parts:
        closed = _residue(water, parts, offset_m=offset_m, quad_segs=quad_segs, anchors=anchors)
        seeds = [*closed.pieces, *_jumps(rings, bank, bank_tree)]
    else:
        rows.vanished.append(
            {
                "body": body,
                "area_ha": round(water.area / 10_000, 3),
                "classes": sorted({int(o) for o in owner}),  # owner indices until contours() names them
                "geometry": water.representative_point(),
            }
        )
        # The whole body is closed off: every anchor at its bank belongs to it.
        near = anchors.query(water, predicate="dwithin", distance=SHORE_SIMPLIFY_M) if anchors is not None else np.empty(0, dtype=int)
        closed = _Closed([water], np.array([np.nan]), [np.asarray(near, dtype=int)], [])
        seeds = [water]
    centre_started = time.perf_counter()
    network = _network(
        body, water, bank, bank_tree, seeds, specks, closed, anchors, rings, offset_m=offset_m, step=sample_m, tile_m=tile_m, failures=failures
    )
    summary.update(network.summary)
    rows.anchors.extend(network.anchor_rows)
    rows.pruned.extend(network.pruned_rows)
    kept_pieces = [closed.pieces[i] for i in np.flatnonzero(network.kept_closed)]
    first_cap = len(rows.caps)
    if kept_pieces and parts:
        opened_tree = shapely.STRtree(closed.opened_parts)
        for i in np.flatnonzero(network.kept_closed):
            anchored = bool(len(closed.anchors[i]))
            rows.caps.append(
                {
                    "body": body,
                    "kind": _kind(closed.pieces[i], closed.opened_parts, opened_tree),
                    "reach_m": round(float(closed.reach[i]), 3),
                    "anchored": anchored,
                    "kept_by": network.kept_by[i],
                    "closed": int(i),
                    "mouths": 0,
                    "cap_m": 0.0,
                    "geometry": closed.pieces[i],
                }
            )
    # Phase 12b capped closed-off water that reaches 2d or holds an anchor; its branch must still be kept.
    anchored_only = (closed.reach < BAY_REACH_M) & np.array([len(a) > 0 for a in closed.anchors], dtype=bool)
    for i in np.flatnonzero(anchored_only & ~network.kept_closed if parts else np.zeros(0, dtype=bool)):
        # Phase 12b capped it for its anchor; no kept branch runs into it, so its mouth stays shore.
        failures.append(
            {
                "body": body,
                "kind": "cap dropped",
                "detail": f"anchored closed-off water reaching {closed.reach[i]:.1f} m",
                "geometry": closed.pieces[i].representative_point(),
            }
        )
    # Water reaching 2d beyond the rest has a branch longer than 2d: phase 12b's cap must stay a cap.
    for i in np.flatnonzero((closed.reach >= BAY_REACH_M) & ~network.kept_closed if parts else np.zeros(0, dtype=bool)):
        failures.append(
            {
                "body": body,
                "kind": "cap not kept",
                "detail": f"closed-off water reaching {closed.reach[i]:.1f} m has no kept centre",
                "geometry": closed.pieces[i].representative_point(),
            }
        )
    summary["centre_s"] = time.perf_counter() - centre_started
    decoded_lines: list[LineString] = []
    raw_lines: list[LineString] = []
    if parts:
        pieces: list[_Piece] = []
        for coords in _with_joins(rings, network.join_xy, network.join_ring, network.join_segment):
            pieces.extend(_cut(coords, owners, kept_pieces, offset_m=offset_m))
        pieces = _cut_artificial(pieces, dam_tree=dam_tree, extent=extent)
        _pin(pieces, network.join_xy)
        summary["raw_vertices"] = int(sum(len(p.coords) for p in pieces))
        if kept_pieces:
            # Each cap piece belongs to the closed-off water nearest it.
            tree = shapely.STRtree(kept_pieces)
            for piece in pieces:
                if piece.role == CAP_ROLE:
                    row = rows.caps[first_cap + int(tree.nearest(LineString(piece.coords)))]
                    row["mouths"] += 1
                    row["cap_m"] = round(row["cap_m"] + LineString(piece.coords).length, 3)
        validated = [_validated(piece, bank, bank_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page) for piece in pieces]
        raw_lines = [LineString(piece.coords) for piece in pieces]
        for _ in range(MAX_REFINE_ROUNDS):
            crossings = _crossings([line for _, line in validated], raw_lines)
            if not crossings:
                break
            # Two pieces simplified apart may cross; each gives back the raw vertex its crossing segment dropped farthest.
            touched = set()
            for one, other, where in crossings:
                for index in (one, other):
                    keep = validated[index][0]["keep"]
                    segment = int(np.argmin(shapely.distance(where, _edges(shapely.get_coordinates(validated[index][1])))))
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
                validated[index] = _validated(pieces[index], bank, bank_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page)
        for _, _, where in _crossings([line for _, line in validated], raw_lines):
            failures.append({"body": body, "kind": "crossing", "detail": "simplified pieces cross where the raw contour does not", "geometry": where})
        for _, _, where in _crossings([line for _, line in validated], raw_lines, contacts=True):
            # Two parts of the offset all but touch: the water there is barely wider than 2d.
            failures.append(
                {"body": body, "kind": "contact", "detail": f"raw pieces within {CONTACT_M} m cross on the page's grid", "geometry": where}
            )
        decoded_lines = [line for _, line in validated]
        for piece, (row, _) in zip(pieces, validated, strict=True):
            row["body"] = body
            row["source"] = _cap_source(piece.coords, bank, bank_tree, network.join_xy) if piece.role == CAP_ROLE else SHORE
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
                    failures.append(
                        {"body": body, "kind": "source edge", "detail": "contour held by a bank outside the source window", "geometry": held}
                    )
            rows.lines.append(row)
        summary["pieces"] = len(pieces)
        summary["vertices"] = int(sum(shapely.get_num_coordinates(line) for line in decoded_lines))
    else:
        summary.update(raw_vertices=0, vertices=0, pieces=0)
    centre_rows, nodes = _centre_pieces(
        body,
        network,
        water,
        owners,
        closed,
        dam_tree=dam_tree,
        extent=extent,
        tolerance_m=tolerance_m,
        to_page=to_page,
        from_page=from_page,
        contour_decoded=decoded_lines,
        contour_raw=raw_lines,
        failures=failures,
    )
    rows.centre.extend(centre_rows)
    rows.nodes.extend(nodes)
    summary["centre_pieces"] = len(centre_rows)
    summary["centre_vertices"] = int(sum(shapely.get_num_coordinates(row["geometry"]) for row in centre_rows))
    summary["wall_s"] = time.perf_counter() - started
    return summary


@dataclass
class _Bank:
    lines: np.ndarray
    ring: np.ndarray
    station: np.ndarray
    start: np.ndarray
    end: np.ndarray
    #: Per ring: its first segment, its segment count and its length.
    ring_first: np.ndarray
    ring_count: np.ndarray
    ring_length: np.ndarray


def _segments(water: BaseGeometry) -> _Bank:
    """Every bank segment of a body with its ring and the station of its start along that ring."""
    coordinates: list[np.ndarray] = []
    rings: list[np.ndarray] = []
    stations: list[np.ndarray] = []
    firsts: list[int] = []
    counts: list[int] = []
    lengths: list[float] = []
    total = 0
    for polygon in shapely.get_parts(water):
        for ring in (polygon.exterior, *polygon.interiors):
            coords = np.asarray(ring.coords)[:, :2]
            steps = np.hypot(*np.diff(coords, axis=0).T)
            coordinates.append(coords)
            rings.append(np.full(len(coords) - 1, len(firsts)))
            stations.append(np.concatenate(([0.0], np.cumsum(steps)[:-1])))
            firsts.append(total)
            counts.append(len(coords) - 1)
            lengths.append(float(steps.sum()))
            total += len(coords) - 1
    start = np.concatenate([c[:-1] for c in coordinates])
    end = np.concatenate([c[1:] for c in coordinates])
    return _Bank(
        np.concatenate([_edges(c) for c in coordinates]),
        np.concatenate(rings),
        np.concatenate(stations),
        start,
        end,
        np.asarray(firsts, dtype=int),
        np.asarray(counts, dtype=int),
        np.asarray(lengths),
    )


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


@dataclass
class _Closed:
    """The water the offset closes off: every piece of a square metre or more, with what pruning needs of it."""

    pieces: list[BaseGeometry]
    reach: np.ndarray
    #: Per piece, the indices of the access anchors that belong to it.
    anchors: list[np.ndarray]
    opened_parts: list[BaseGeometry]


def _residue(
    water: BaseGeometry,
    parts: list[Polygon],
    *,
    offset_m: float,
    quad_segs: int,
    anchors: shapely.STRtree | None,
) -> _Closed:
    """The water the offset closes off, how far each piece reaches beyond the rest, and its anchors.

    A disc of radius d rolled through the surviving water reaches everything
    but bays narrower than 2d, closed island passages and the like. Phase 12b
    capped such a piece when it reaches ``BAY_REACH_M`` beyond the reachable
    water or holds an access anchor; phase 12c keeps its centre branch by the
    branch's own length, so every piece is returned with its reach.
    """
    opened_parts: list[BaseGeometry] = [shapely.buffer(part, offset_m, quad_segs=quad_segs) for part in parts]
    opened = shapely.union_all(opened_parts)
    residue: list[BaseGeometry] = [
        p for p in shapely.get_parts(shapely.difference(water, opened)) if isinstance(p, Polygon) and p.area >= RESIDUE_MIN_M2
    ]
    if not residue:
        return _Closed([], np.empty(0), [], opened_parts)
    # Distances to a large polygon are linear in its vertices; to its indexed edges they are not.
    edges = _edge_tree(opened_parts)
    reach = np.empty(len(residue))
    held: list[np.ndarray] = []
    for index, piece in enumerate(residue):
        # The farthest water is often mid-passage, between vertices: sample the outline.
        outline = shapely.points(shapely.get_coordinates(shapely.segmentize(piece.boundary, REACH_SAMPLE_M)))
        _, distances = edges.query_nearest(outline, return_distance=True, all_matches=False)
        reach[index] = float(distances.max())
        own = np.empty(0, dtype=int)
        if anchors is not None:
            # Graph anchors sit on the 5 m-simplified shore, up to that far off the source bank; one
            # belongs to the closed-off water when it is nearer to it than to the reachable water.
            near = anchors.query(piece, predicate="dwithin", distance=SHORE_SIMPLIFY_M)
            if len(near):
                points = anchors.geometries[near]
                own = near[shapely.distance(points, piece) < shapely.distance(points, opened)]
        held.append(own)
    return _Closed(residue, reach, held, opened_parts)


def _kind(piece: BaseGeometry, opened_parts: list[BaseGeometry], tree: shapely.STRtree) -> str:
    """Passage between two parts of the offset, loop meeting one part twice, or terminal."""
    near = tree.query(piece, predicate="dwithin", distance=0.05)
    if len(near) >= 2:
        return "passage"
    contact = None
    if len(near):
        # Grow only the reachable water around this piece: growing a whole sea costs minutes per piece,
        # and even overlaying it with a box is slow; a rectangle clip gives the same water near the piece.
        x0, y0, x1, y1 = shapely.bounds(piece)
        local = shapely.clip_by_rect(opened_parts[int(near[0])], x0 - 1.0, y0 - 1.0, x1 + 1.0, y1 + 1.0)
        contact = shapely.line_merge(shapely.intersection(piece.boundary, shapely.buffer(local, 0.05)))
    arcs = [a for a in shapely.get_parts(contact) if a.length > 0.1] if contact is not None else []
    return "loop" if len(arcs) >= 2 else "terminal"


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
    if extent is not None:
        shapely.prepare(extent)
    out = []
    for piece in pieces:
        line = LineString(piece.coords)
        kept = _outside_dams(line, dam_tree) if dam_tree is not None else [line]
        if extent is not None:
            # Most lines lie well inside the map; only those that reach its edge are cut.
            kept = [
                g
                for part in kept
                for g in ([part] if extent.contains(part) else shapely.get_parts(shapely.intersection(part, extent)))
                if isinstance(g, LineString)
            ]
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


def _distance_pairs(points: np.ndarray, one: np.ndarray, other: np.ndarray) -> np.ndarray:
    """Distance of each point from its own segment."""
    delta = other - one
    squared = (delta**2).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.clip(np.where(squared > 0, ((points - one) * delta).sum(axis=1) / squared, 0.0), 0.0, 1.0)
    return np.asarray(np.hypot(*(points - (one + t[:, None] * delta)).T))


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


def _deviation_bound(coords: np.ndarray, tree: shapely.STRtree, gate: np.ndarray | float = CONTOUR_DEVIATION_M) -> tuple[np.ndarray, np.ndarray]:
    """Per segment of ``coords``: a proven upper bound on its distance from the tree's line, and the largest sample.

    Samples every ``COARSE_SAMPLE_M``; a gap whose bound, the mean of its ends
    plus half its length, exceeds the gate (one figure, or one per segment) is
    sampled again every ``FINE_SAMPLE_M``.
    """
    lengths = np.hypot(*np.diff(coords, axis=0).T)
    bounds = np.zeros(len(lengths))
    sampled = np.zeros(len(lengths))
    for step in (COARSE_SAMPLE_M, FINE_SAMPLE_M):
        # A segment whose gate is infinite is not judged at all.
        todo = np.flatnonzero(bounds > gate) if step == FINE_SAMPLE_M else np.flatnonzero(np.isfinite(np.broadcast_to(gate, len(lengths))))
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


def _crossings(
    decoded_lines: list[LineString], raw_lines: list[LineString], *, contacts: bool = False, only: np.ndarray | None = None
) -> list[tuple[int, int, Point]]:
    """Where two simplified pieces meet other than at a shared end or where their raw pieces meet too.

    Raw pieces that pass within ``CONTACT_M`` of each other without meeting may
    cross once written on the page's grid, and no vertex can undo that. Those
    are contacts: returned instead of crossings when ``contacts`` is set. With
    ``only``, just the pairs that involve one of those pieces are looked at.
    """
    if len(decoded_lines) < 2:
        return []
    tree = shapely.STRtree(decoded_lines)
    queries = np.arange(len(decoded_lines)) if only is None else np.asarray(only, dtype=int)
    if not len(queries):
        return []
    lines = np.asarray(decoded_lines, dtype=object)
    left, right = tree.query(lines[queries], predicate="intersects")
    left = queries[left]
    # Pieces that meet only at their ends, as the centre lines do at every join and junction, cannot
    # cross: dropping them first is the end test below done at once, and it keeps the loop short.
    apart = (left != right) & ~shapely.touches(lines[left], lines[right])
    pairs = sorted({(min(a, b), max(a, b)) for a, b in zip(left[apart].tolist(), right[apart].tolist(), strict=True)})
    found = []
    for one, other in pairs:
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


def _jumps(rings: list[np.ndarray], bank: _Bank, tree: shapely.STRtree) -> list[BaseGeometry]:
    """Where the medial axis leaves the raw contour for water worth a look: seeds for the centre construction.

    Along a contour that follows a bank, the nearest bank point moves no farther
    than the contour does. Where it jumps, the contour passes from one stretch of
    bank to another, and the medial axis runs off between them. A jump between
    two rings (an island gap) or across at least ``JUMP_SEPARATION_M`` of bank
    seeds the construction; a smaller one is a corner of the water.
    """
    if not rings:
        return []
    points = np.concatenate([coords[:-1] for coords in rings])
    sizes = np.array([len(coords) - 1 for coords in rings])
    starts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    index = np.arange(len(points))
    ring_of = np.repeat(np.arange(len(rings)), sizes)
    following = np.where(index + 1 < starts[ring_of] + sizes[ring_of], index + 1, starts[ring_of])
    ring, station, nearest = _generators(points, bank, tree)
    held = shapely.get_coordinates(nearest)
    step = np.hypot(*(points[following] - points).T)
    move = np.hypot(*(held[following] - held).T)
    along = np.abs(station[following] - station)
    separation = np.where(ring[following] == ring, np.minimum(along, bank.ring_length[ring] - along), np.inf)
    chosen = np.flatnonzero((move > step + JUMP_M) & (separation >= JUMP_SEPARATION_M))
    return list(np.asarray(shapely.buffer(shapely.linestrings(np.stack([points[chosen], points[following[chosen]]], axis=1)), 1.0), dtype=object))


@dataclass
class _Sampler:
    """Every bank segment of a body sampled at most every step, symmetrically about its vertices.

    Samples lie at whole steps from each end of a segment, with its middle added
    where the gap left would exceed a step; a corner is then seen alike from both
    sides. Each segment has its own step, finer where the middle gate asked for
    it. A sample's id follows its ring, so two samples are neighbours on the bank
    exactly when their ids differ by one in a ring or they close it. The samples
    are a pure function of the bank and the steps: two tiles that need the same
    sample compute the same coordinates.
    """

    bank: _Bank
    step: float
    steps: np.ndarray
    origin: np.ndarray
    length: np.ndarray
    ends: np.ndarray
    middle: np.ndarray
    count: np.ndarray
    first: np.ndarray
    ring_first_id: np.ndarray
    ring_last_id: np.ndarray

    def ids(self, segments: np.ndarray) -> np.ndarray:
        """All sample ids of the given segments: segment and index within it, so refining one segment renumbers no other."""
        counts = self.count[segments]
        offsets = np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts)
        return np.asarray(np.repeat(segments.astype(np.int64) * SAMPLE_STRIDE, counts) + offsets)

    def segment(self, ids: np.ndarray) -> np.ndarray:
        return np.asarray(ids // SAMPLE_STRIDE)

    def order(self, ids: np.ndarray) -> np.ndarray:
        """A sample's place along the bank in the current sampling."""
        return np.asarray(self.first[self.segment(ids)] + ids % SAMPLE_STRIDE)

    def local(self, ids: np.ndarray) -> np.ndarray:
        """Sample coordinates relative to ``origin``."""
        segment = self.segment(ids)
        j = ids % SAMPLE_STRIDE
        length, ends, count = self.length[segment], self.ends[segment], self.count[segment]
        position = np.where(
            j <= ends,
            j * self.steps[segment],
            np.where(self.middle[segment] & (j == ends + 1), length / 2, length - (count - j) * self.steps[segment]),
        )
        start = self.bank.start[segment] - self.origin
        return np.asarray(start + (position / length)[:, None] * (self.bank.end[segment] - self.bank.start[segment]))

    def neighbours(self, one: np.ndarray, other: np.ndarray, reach: int = 1) -> np.ndarray:
        """Whether two samples lie within ``reach`` steps of each other along the same ring."""
        ring_one, ring_other = self.bank.ring[self.segment(one)], self.bank.ring[self.segment(other)]
        size = self.ring_last_id[ring_one] - self.ring_first_id[ring_one] + 1
        apart = np.abs(self.order(other) - self.order(one))
        return np.asarray((ring_one == ring_other) & (np.minimum(apart, size - apart) <= reach))


def _sampler(bank: _Bank, steps: np.ndarray, origin: np.ndarray) -> _Sampler:
    length = np.hypot(*(bank.end - bank.start).T)
    ends = np.floor(length / (2 * steps)).astype(int)
    gap = length - 2 * ends * steps
    tail = np.maximum(ends - (gap <= 1e-9).astype(int), 0)
    middle = gap > steps + 1e-9
    count = np.where(length > 0, 1 + ends + middle.astype(int) + tail, 0)
    first = np.concatenate(([0], np.cumsum(count)))
    return _Sampler(
        bank,
        float(steps.max()) if len(steps) else 0.0,
        steps,
        origin,
        length,
        ends,
        middle,
        count,
        first,
        first[bank.ring_first],
        first[bank.ring_first + bank.ring_count] - 1,
    )


@dataclass
class _Medial:
    """The medial axis of a body's water where its radius is below d, near the seeds, as a graph.

    Attributes:
        step: The bank sampling step it was built with
        sampler: Its samples
        xy: Node coordinates
        gens: Up to three sample ids generating each node, -1 where fewer
        rim: The node is where the radius reaches d: a join with the contour
        u, v: Edge ends
        a, b: The two samples an edge lies between
        length: Edge lengths
        component: Connected component of each node
        diagnostics: Tiles, samples, triangles, witnesses, growth
    """

    step: float
    sampler: _Sampler
    xy: np.ndarray
    gens: np.ndarray
    rim: np.ndarray
    u: np.ndarray
    v: np.ndarray
    a: np.ndarray
    b: np.ndarray
    length: np.ndarray
    component: np.ndarray
    diagnostics: dict[str, Any]
    #: Nodes placed rather than found: the one a speck's false ends are tied to. No middle is measured there.
    made: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    #: Nodes where an edge was cut at the water's edge: the samples there are too far apart for the water.
    bank_end: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))


def _medial(
    water: BaseGeometry,
    bank: _Bank,
    bank_tree: shapely.STRtree,
    seeds: list[BaseGeometry],
    *,
    offset_m: float,
    steps: np.ndarray,
    tile_m: float,
    cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, dict[str, Any]]],
    feet: tuple[np.ndarray, np.ndarray] = (np.empty(0, dtype=int), np.empty((0, 2))),
) -> _Medial:
    """The medial graph of every component that meets a seed, grown until no kept branch leaves its window.

    ``cache`` keeps each tile's edges with the segments and steps they came
    from; a later call with finer steps elsewhere reuses a tile whose own
    segments and steps did not change. Growing the windows clears it. ``feet``
    are the bank points of the access anchors in closed-off water, by segment:
    a component their samples face is kept too, since at a shallow corner the
    sampled branch starts a few steps from the bank and can miss a small piece.
    """
    origin = np.floor(np.asarray(shapely.bounds(water)[:2]) / tile_m) * tile_m
    sampler = _sampler(bank, steps, origin)
    grown: list[BaseGeometry] = []
    for rounds in range(MAX_GROWTH_ROUNDS + 1):
        if rounds:
            cache.clear()
        medial, outside = _medial_tiles(
            water,
            bank_tree,
            sampler,
            [*seeds, *grown],
            offset_m=offset_m,
            tile_m=tile_m,
            cache=cache,
            faced=_nearest_samples(sampler, bank, *feet),
        )
        medial.diagnostics["growth_rounds"] = rounds
        medial.diagnostics["window_open"] = len(outside)
        if not len(outside):
            return medial
        grown.extend(np.asarray(shapely.buffer(shapely.points(outside), offset_m), dtype=object))
    return medial


def _medial_tiles(
    water: BaseGeometry,
    bank_tree: shapely.STRtree,
    sampler: _Sampler,
    seeds: list[BaseGeometry],
    *,
    offset_m: float,
    tile_m: float,
    cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, dict[str, Any]]],
    faced: np.ndarray,
) -> tuple[_Medial, np.ndarray]:
    """One pass over the tiles; returns the graph and where a kept component runs out of its window.

    A medial point of radius r is right when every sample within r of it was
    triangulated. Each tile samples the bank within ``2d`` plus a margin of its
    cell, and within ``3d`` of the seeds; it keeps the edges whose middle it
    contains and lies within ``2d`` of a seed. It also recomputes the edges just
    across its border; they must equal those the neighbour keeps.
    """
    step, origin, d = sampler.step, sampler.origin, offset_m
    seed_array = np.asarray(seeds, dtype=object)
    seed_tree = shapely.STRtree(seed_array)
    keep_region = shapely.union_all(shapely.buffer(seed_array, 2 * d))
    seed_reach = shapely.buffer(seed_array, 3 * d + 3 * step + 1.0)
    shapely.prepare(keep_region)
    sample_reach = 3 * d + 3 * step + 1.0
    tile_margin = 2 * d + TILE_BAND_M + 3 * step + 2.0
    x0, y0, x1, y1 = shapely.bounds(keep_region)
    columns = range(int(np.floor((x0 - origin[0]) / tile_m)), int(np.floor((x1 - origin[0]) / tile_m)) + 1)
    rows_range = range(int(np.floor((y0 - origin[1]) / tile_m)), int(np.floor((y1 - origin[1]) / tile_m)) + 1)
    owned: list[dict[str, np.ndarray]] = []
    band: list[dict[str, np.ndarray]] = []
    outer: list[dict[str, np.ndarray]] = []
    diagnostics: dict[str, Any] = {
        "step_m": float(sampler.steps.min()) if len(sampler.steps) else step,
        "tiles": 0,
        "tiles_reused": 0,
        "samples": 0,
        "triangles": 0,
        "voronoi_edges": 0,
        "outside_water_edges": 0,
        "not_empty_edges": 0,
    }
    for column in columns:
        for row in rows_range:
            left, bottom = origin[0] + column * tile_m, origin[1] + row * tile_m
            cell = shapely.box(left, bottom, left + tile_m, bottom + tile_m)
            if not keep_region.intersects(cell):
                continue
            window = shapely.buffer(cell, tile_margin, join_style="mitre")
            near = seed_tree.query(window, predicate="dwithin", distance=sample_reach)
            if not len(near):
                continue
            # A rectangle clip first: a river's buffered seed runs for kilometres past the tile.
            region = shapely.intersection(window, shapely.union_all(shapely.clip_by_rect(seed_reach[near], *shapely.bounds(window))))
            shapely.prepare(region)
            segments = np.sort(bank_tree.query(region))
            cached = cache.get((column, row))
            if cached is not None and np.array_equal(cached[0], segments) and np.array_equal(cached[1], sampler.steps[segments]):
                found = dict(cached[2])
                diagnostics["tiles_reused"] = diagnostics.get("tiles_reused", 0) + 1
            else:
                computed = _tile_samples(water, bank_tree, sampler, segments, region, keep_region, (left, bottom), tile_m=tile_m, offset_m=d)
                if computed is None:
                    continue
                found = computed
                cache[(column, row)] = (segments, sampler.steps[segments].copy(), dict(found))
            diagnostics["tiles"] += 1
            for key in ("samples", "triangles", "voronoi_edges", "outside_water_edges", "not_empty_edges"):
                diagnostics[key] += found.pop(key)
            owned.append(found["owned"])
            band.append(found["band"])
            outer.append(found["outer"])
    edges = _stack(owned)
    medial, keys = _graph(sampler, edges, seed_tree, water, faced)
    # The witness: an edge computed across a border must be the one its owner kept.
    witness = _stack(band)
    kept_keys = set(zip(*_edge_keys(edges), strict=True))
    by_samples = {(lo, hi): (one, other) for lo, hi, one, other in zip(*_edge_keys(edges), strict=True)}
    compared = [key for key in zip(*_edge_keys(witness), strict=True) if key[2] != key[3]]
    diagnostics["overlap_edges"] = len(compared)
    mismatched = [key for key in compared if key not in kept_keys]
    diagnostics["overlap_mismatches"] = len(mismatched)
    # A mismatch between the same two samples is a clip point computed from a differently ended edge.
    apart = [max(abs(key[2] - by_samples[key[:2]][0]), abs(key[3] - by_samples[key[:2]][1])) / 1e6 for key in mismatched if key[:2] in by_samples]
    diagnostics["overlap_missing"] = len(mismatched) - len(apart)
    diagnostics["overlap_largest_difference_m"] = float(max(apart)) if apart else 0.0
    medial.diagnostics.update(diagnostics)
    # Where a kept component meets an edge outside the windows, the windows were too small.
    far = _stack(outer)
    outside = np.empty((0, 2))
    if len(far["lo"]):
        ends = np.concatenate([_node_keys(far["q0"]), _node_keys(far["q1"])])
        hits = np.isin(ends, keys)
        if hits.any():
            middles = (far["q0"] + far["q1"]) / 2 + origin
            outside = np.concatenate([middles, middles])[hits]
    return medial, outside


def _tile_samples(
    water: BaseGeometry,
    bank_tree: shapely.STRtree,
    sampler: _Sampler,
    segments: np.ndarray,
    region: BaseGeometry,
    keep_region: BaseGeometry,
    corner: tuple[float, float],
    *,
    tile_m: float,
    offset_m: float,
) -> dict[str, Any] | None:
    """The samples of one tile's region and the edges they give, or None where there are too few to triangulate."""
    origin = sampler.origin
    ids = sampler.ids(segments)
    points = sampler.local(ids)
    inside = shapely.contains_xy(region, points[:, 0] + origin[0], points[:, 1] + origin[1])
    ids, points = ids[inside], points[inside]
    # Rings touching at a point share a sample; keep one.
    _, unique = np.unique(points, axis=0, return_index=True)
    unique.sort()
    ids, points = ids[unique], points[unique]
    if len(ids) < 4:
        return None
    found = _tile_edges(water, bank_tree, sampler, ids, points, keep_region, corner, tile_m=tile_m, offset_m=offset_m)
    found["samples"] = len(ids)
    return found


def _tile_edges(
    water: BaseGeometry,
    bank_tree: shapely.STRtree,
    sampler: _Sampler,
    ids: np.ndarray,
    points: np.ndarray,
    keep_region: BaseGeometry,
    corner: tuple[float, float],
    *,
    tile_m: float,
    offset_m: float,
) -> dict[str, Any]:
    """The Voronoi edges of one tile's samples that lie in the water between non-neighbouring samples, clipped to radius d."""
    origin = sampler.origin
    triangles = shapely.get_parts(shapely.delaunay_triangles(shapely.multipoints(points)))
    corners = shapely.get_coordinates(triangles).reshape(-1, 4, 2)[:, :3]
    # Map each triangle corner back to its sample; GEOS keeps the input coordinates.
    keys = points[:, 0] + 1j * points[:, 1]
    order = np.argsort(keys)
    found = np.searchsorted(keys[order], corners[..., 0] + 1j * corners[..., 1])
    position = order[np.minimum(found, len(order) - 1)]
    if not np.array_equal(points[position], corners):
        raise RuntimeError("a Delaunay corner is not one of the samples")
    # Order each triangle by sample id, so a tile beside it computes the same circumcentre.
    position = np.take_along_axis(position, np.argsort(ids[position], axis=1), axis=1)
    tri_ids = ids[position]
    first, second, third = points[position[:, 0]], points[position[:, 1]], points[position[:, 2]]
    b, c = second - first, third - first
    with np.errstate(divide="ignore", invalid="ignore"):
        denominator = 2 * (b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0])
        bb, cc = (b**2).sum(axis=1), (c**2).sum(axis=1)
        centre = first + np.c_[(c[:, 1] * bb - b[:, 1] * cc) / denominator, (b[:, 0] * cc - c[:, 0] * bb) / denominator]
    # Voronoi edges are the duals of Delaunay edges shared by two triangles. Samples are in id order,
    # so positions order like ids and a pair keys on its positions.
    pairs = np.concatenate([position[:, [0, 1]], position[:, [1, 2]], position[:, [0, 2]]])
    owner = np.tile(np.arange(len(tri_ids)), 3)
    key = pairs[:, 0].astype(np.int64) * len(points) + pairs[:, 1]
    order = np.argsort(key, kind="stable")
    key, owner, pairs = key[order], owner[order], pairs[order]
    repeated = key[1:] == key[:-1]
    shared = np.flatnonzero(repeated)
    # A Delaunay edge on the hull of the tile's samples has one triangle: its Voronoi edge is a ray
    # outward from the circumcentre. Where the tile holds every sample near it, its part within d
    # is as right as any; a narrow's way out to a far lake needs it when the tile is small.
    alone = np.flatnonzero(~np.r_[False, repeated] & ~np.r_[repeated, False]) if len(key) else np.empty(0, dtype=int)
    t1 = np.concatenate([owner[shared], owner[alone]])
    t2 = np.concatenate([owner[shared + 1], np.full(len(alone), -1)])
    pair_positions = np.concatenate([pairs[shared], pairs[alone]])
    lo, hi = ids[pair_positions[:, 0]], ids[pair_positions[:, 1]]
    p0 = centre[t1]
    p1 = np.where((t2 >= 0)[:, None], centre[np.maximum(t2, 0)], np.nan)
    if len(alone):
        ray = np.arange(len(shared), len(t1))
        one, other = points[pair_positions[ray, 0]], points[pair_positions[ray, 1]]
        third = points[position[t1[ray]].sum(axis=1) - pair_positions[ray].sum(axis=1)]
        middle_of = (one + other) / 2
        normal = np.c_[-(other - one)[:, 1], (other - one)[:, 0]]
        normal *= np.where(((third - middle_of) * normal).sum(axis=1) > 0, -1.0, 1.0)[:, None]
        normal /= np.maximum(np.hypot(*normal.T), 1e-12)[:, None]
        # Far enough out that its end is more than d from both samples, so the clip below always ends it.
        reach = offset_m + np.hypot(*(p0[ray] - middle_of).T) + np.hypot(*(other - one).T) / 2 + 1.0
        with np.errstate(invalid="ignore"):
            p1[ray] = p0[ray] + normal * reach[:, None]
    # A rib between two neighbouring samples runs from the bank to the middle; it is not the middle.
    medial = ~sampler.neighbours(lo, hi) & np.isfinite(p0).all(axis=1) & np.isfinite(p1).all(axis=1)
    out: dict[str, Any] = {"triangles": len(tri_ids), "voronoi_edges": int(medial.sum())}
    t1, t2, lo, hi, p0, p1 = t1[medial], t2[medial], lo[medial], hi[medial], p0[medial], p1[medial]
    # Keep the part within d of the bank. The distance to the two samples overstates the distance to
    # the bank by up to about step² / (8r); where the water is a hair under 2d wide that is enough to
    # cut the middle where no contour is. The overstatement is known exactly at the vertices and
    # interpolated between them: the clip solves |p(t) - sample| = d + overstatement(t).
    generator = points[np.searchsorted(ids, lo)]
    direction, offset = p1 - p0, p0 - generator
    # Only an edge whose radius passes between d and d plus the largest overstatement can be clipped
    # differently by it; the others need no exact distance.
    radius0, radius1 = np.hypot(*(p0 - generator).T), np.hypot(*(p1 - generator).T)
    with np.errstate(divide="ignore", invalid="ignore"):
        along = np.clip(-(offset * direction).sum(axis=1) / (direction**2).sum(axis=1), 0.0, 1.0)
    closest = np.hypot(*(offset + np.nan_to_num(along)[:, None] * direction).T)
    near_d = (closest <= offset_m + OVERSTATEMENT_M) & (np.maximum(radius0, radius1) >= offset_m)
    over = [np.zeros(len(p0)), np.zeros(len(p0))]
    for which, (end, radius) in enumerate(((p0, radius0), (p1, radius1))):
        if near_d.any():
            (_, _), exact = bank_tree.query_nearest(shapely.points(end[near_d] + origin), return_distance=True, all_matches=False)
            over[which][near_d] = np.maximum(radius[near_d] - exact, 0.0)
    # More than a sampling error means the vertex lies where other bank is nearer than the samples
    # it was built from: the far end of a ray, or a vertex outside the part the tile can trust.
    trusted0, trusted1 = over[0] <= OVERSTATEMENT_M, (over[1] <= OVERSTATEMENT_M) & (t2 >= 0)
    over0 = np.where(trusted0, over[0], np.where(trusted1, over[1], 0.0))
    over1 = np.where(trusted1, over[1], over0)
    reach0, change = offset_m + over0, over1 - over0
    qa = (direction**2).sum(axis=1) - change**2
    qb = 2 * ((offset * direction).sum(axis=1) - reach0 * change)
    qc = (offset**2).sum(axis=1) - reach0**2
    with np.errstate(divide="ignore", invalid="ignore"):
        root = np.sqrt(np.maximum(qb**2 - 4 * qa * qc, 0.0))
        start = np.where(qa > 0, (-qb - root) / (2 * qa), np.where(qc <= 0, 0.0, np.inf))
        stop = np.where(qa > 0, (-qb + root) / (2 * qa), np.where(qc <= 0, 1.0, -np.inf))
    start, stop = np.maximum(start, 0.0), np.minimum(stop, 1.0)
    start = np.where(qb**2 - 4 * qa * qc < 0, np.inf, start)
    keep = start < stop
    start, stop = start[keep], stop[keep]
    p0, p1, lo, hi, t1, t2 = p0[keep], p1[keep], lo[keep], hi[keep], t1[keep], t2[keep]
    q0 = p0 + start[:, None] * (p1 - p0)
    q1 = p0 + stop[:, None] * (p1 - p0)
    # In the water after the clip: an edge that leaves it does so only where the bank passes between two samples.
    wet0 = shapely.contains_xy(water, q0[:, 0] + origin[0], q0[:, 1] + origin[1])
    wet1 = shapely.contains_xy(water, q1[:, 0] + origin[0], q1[:, 1] + origin[1])
    out["outside_water_edges"] = int((wet0 != wet1).sum())
    wet = wet0 & wet1
    for index in np.flatnonzero(wet0 != wet1):
        inside, outside = (q0[index], q1[index]) if wet0[index] else (q1[index], q0[index])
        part = shapely.intersection(LineString([inside + origin, outside + origin]), water)
        piece = next((g for g in shapely.get_parts(part) if isinstance(g, LineString) and g.distance(Point(inside + origin)) < 1e-9), None)
        if piece is None:
            continue
        wet[index] = True
        ends = np.asarray(piece.coords)[[0, -1]] - origin
        bank_end = ends[np.argmax(np.hypot(*(ends - inside).T))]
        if wet0[index]:
            q1[index], stop[index] = bank_end, 0.0
        else:
            q0[index], start[index] = bank_end, 1.0
    # An edge of the middle is nearer its two samples than any other. GEOS triangulates exactly
    # collinear samples into flat triangles whose huge circles pass for empty in floating point
    # (2.8e10 m measured); the bisector of two samples nine apart on one segment then crosses the
    # river. The middle of each kept part must have no sample nearer than its two.
    if wet.any():
        middle_kept = (q0[wet] + q1[wet]) / 2
        (_, _), nearest = shapely.STRtree(np.asarray(shapely.points(points), dtype=object)).query_nearest(
            shapely.points(middle_kept), return_distance=True, all_matches=False
        )
        own = np.hypot(*(middle_kept - generator[keep][wet]).T)
        empty = nearest >= own - 1e-6 * np.maximum(own, 1.0)
        out["not_empty_edges"] = int((~empty).sum())
        wet[np.flatnonzero(wet)[~empty]] = False
    else:
        out["not_empty_edges"] = 0
    # The end moved to the bank is neither a join nor a circumcentre: it takes the edge's two samples.
    start, stop, lo, hi, t1, t2, q0, q1 = start[wet], stop[wet], lo[wet], hi[wet], t1[wet], t2[wet], q0[wet], q1[wet]
    at_bank0, at_bank1 = start >= 1.0, stop <= 0.0
    start, stop = np.where(at_bank0, 0.0, start), np.where(at_bank1, 1.0, stop)
    rim0, rim1 = (start > 0) & ~at_bank0, (stop < 1) & ~at_bank1
    pair = np.c_[lo, hi, np.full(len(lo), -1)]
    # A clipped end, a bank end and a ray's end take the edge's two samples; a circumcentre its triangle's three.
    edges = {
        "q0": q0,
        "q1": q1,
        "lo": lo,
        "hi": hi,
        "g0": np.where((rim0 | at_bank0)[:, None], pair, tri_ids[t1]),
        "g1": np.where((rim1 | at_bank1 | (t2 < 0))[:, None], pair, tri_ids[np.maximum(t2, 0)]),
        "rim0": rim0,
        "rim1": rim1,
        "bank0": at_bank0,
        "bank1": at_bank1,
    }
    middle = (q0 + q1) / 2
    in_cell = (middle[:, 0] >= corner[0] - origin[0]) & (middle[:, 0] < corner[0] - origin[0] + tile_m)
    in_cell &= (middle[:, 1] >= corner[1] - origin[1]) & (middle[:, 1] < corner[1] - origin[1] + tile_m)
    near_cell = (np.abs(middle[:, 0] - (corner[0] - origin[0] + tile_m / 2)) < tile_m / 2 + TILE_BAND_M) & (
        np.abs(middle[:, 1] - (corner[1] - origin[1] + tile_m / 2)) < tile_m / 2 + TILE_BAND_M
    )
    kept = shapely.contains_xy(keep_region, middle[:, 0] + origin[0], middle[:, 1] + origin[1])
    out["owned"] = {k: v[in_cell & kept] for k, v in edges.items()}
    out["band"] = {k: v[near_cell & ~in_cell & kept] for k, v in edges.items()}
    out["outer"] = {k: v[in_cell & ~kept] for k, v in edges.items()}
    return out


def _stack(parts: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    names = ("q0", "q1", "lo", "hi", "g0", "g1", "rim0", "rim1", "bank0", "bank1")
    if not parts:
        empty = {"q0": np.empty((0, 2)), "q1": np.empty((0, 2)), "g0": np.empty((0, 3), dtype=int), "g1": np.empty((0, 3), dtype=int)}
        return {k: empty.get(k, np.empty(0, dtype=bool if k.startswith(("rim", "bank")) else int)) for k in names}
    return {k: np.concatenate([p[k] for p in parts]) for k in names}


def _node_keys(points: np.ndarray) -> np.ndarray:
    """A node's identity: its local coordinates on a micrometre grid, as one complex number."""
    rounded = np.round(points * 1e6)
    return np.asarray(rounded[:, 0] + 1j * rounded[:, 1])


def _edge_keys(edges: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """An edge's identity whichever way round a tile found it: its two samples and its two nodes in order."""
    one, other = _node_keys(edges["q0"]), _node_keys(edges["q1"])
    swap = (one.real > other.real) | ((one.real == other.real) & (one.imag > other.imag))
    return edges["lo"], edges["hi"], np.where(swap, other, one), np.where(swap, one, other)


def _graph(
    sampler: _Sampler,
    edges: dict[str, np.ndarray],
    seed_tree: shapely.STRtree,
    water: BaseGeometry,
    faced: np.ndarray,
) -> tuple[_Medial, np.ndarray]:
    """Nodes shared by coordinates, the components that meet a seed or an anchor's samples, and the node keys of those components."""
    keys = np.concatenate([_node_keys(edges["q0"]), _node_keys(edges["q1"])])
    unique, first, inverse = np.unique(keys, return_index=True, return_inverse=True)
    count = len(edges["lo"])
    u, v = inverse[:count], inverse[count:]
    xy = np.concatenate([edges["q0"], edges["q1"]])[first] + sampler.origin
    gens = np.concatenate([edges["g0"], edges["g1"]])[first]
    rim = np.zeros(len(unique), dtype=bool)
    np.logical_or.at(rim, inverse, np.concatenate([edges["rim0"], edges["rim1"]]))
    bank_end = np.zeros(len(unique), dtype=bool)
    np.logical_or.at(bank_end, inverse, np.concatenate([edges["bank0"], edges["bank1"]]))
    # One edge per pair of nodes; a degenerate edge of cocircular samples joins nothing.
    lo_node, hi_node = np.minimum(u, v), np.maximum(u, v)
    distinct = lo_node != hi_node
    _, single = np.unique(lo_node[distinct] * len(unique) + hi_node[distinct], return_index=True)
    chosen = np.flatnonzero(distinct)[single]
    u, v, a, b = u[chosen], v[chosen], edges["lo"][chosen], edges["hi"][chosen]
    found = len(xy)
    xy, gens, rim, unique, u, v, a, b = _corners(sampler, water, xy, gens, rim, unique, u, v, a, b)
    bank_end = np.concatenate([bank_end, np.zeros(len(xy) - found, dtype=bool)])
    component = _label(len(unique), u, v)
    touched = np.unique(seed_tree.query(shapely.points(xy), predicate="intersects")[0]) if len(xy) else np.empty(0, dtype=int)
    anchored = np.isin(a, faced) | np.isin(b, faced)
    selected = np.isin(component, np.concatenate([component[touched], component[u[anchored]]]))
    renumber = np.cumsum(selected) - 1
    keep_edge = selected[u]
    medial = _Medial(
        step=sampler.step,
        sampler=sampler,
        xy=xy[selected],
        gens=gens[selected],
        rim=rim[selected],
        u=renumber[u[keep_edge]],
        v=renumber[v[keep_edge]],
        a=a[keep_edge],
        b=b[keep_edge],
        length=np.hypot(*(xy[u[keep_edge]] - xy[v[keep_edge]]).T),
        component=np.unique(component[selected], return_inverse=True)[1],
        diagnostics={
            "components": int(len(np.unique(component[selected]))),
            "components_not_seeded": int(len(np.unique(component)) - len(np.unique(component[selected]))),
        },
        made=np.zeros(int(selected.sum()), dtype=bool),
        bank_end=bank_end[selected],
    )
    return medial, unique[selected]


def _corners(
    sampler: _Sampler,
    water: BaseGeometry,
    xy: np.ndarray,
    gens: np.ndarray,
    rim: np.ndarray,
    keys: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Run each corner's branch on into its corner.

    The middle of a convex corner of the bank runs down its bisector into the
    vertex. The sampled branch stops at the circumcentre of the vertex and its
    two neighbouring samples, about 0.7 of a step short; a bay's branch judged
    against 2d would be judged short by that much. A leaf generated by a bank
    vertex and the samples either side of it gets the edge on to the vertex.
    """
    degree = np.bincount(np.concatenate([u, v]), minlength=len(xy))
    leaf = np.flatnonzero((degree == 1) & (gens >= 0).all(axis=1))
    if not len(leaf):
        return xy, gens, rim, keys, u, v, a, b
    trio = gens[leaf]
    vertex = np.full(len(leaf), -1, dtype=np.int64)
    others = np.zeros((len(leaf), 2), dtype=np.int64)
    for k, (i, j) in enumerate(((1, 2), (0, 2), (0, 1))):
        middle, one, other = trio[:, k], trio[:, i], trio[:, j]
        fits = (middle % SAMPLE_STRIDE == 0) & sampler.neighbours(middle, one) & sampler.neighbours(middle, other) & (vertex < 0)
        vertex[fits] = middle[fits]
        others[fits] = np.c_[one[fits], other[fits]]
    found = vertex >= 0
    if not found.any():
        return xy, gens, rim, keys, u, v, a, b
    leaf, vertex, others = leaf[found], vertex[found], others[found]
    corner = sampler.local(vertex) + sampler.origin
    # Only a convex corner: the way on to it lies in the water.
    convex = shapely.covers(water, shapely.linestrings(np.stack([xy[leaf], corner], axis=1)))
    leaf, vertex, others, corner = leaf[convex], vertex[convex], others[convex], corner[convex]
    added = np.arange(len(xy), len(xy) + len(leaf))
    return (
        np.concatenate([xy, corner]),
        np.concatenate([gens, gens[leaf]]),
        np.concatenate([rim, np.zeros(len(leaf), dtype=bool)]),
        np.concatenate([keys, _node_keys(corner - sampler.origin)]),
        np.concatenate([u, leaf]),
        np.concatenate([v, added]),
        np.concatenate([a, others.min(axis=1)]),
        np.concatenate([b, others.max(axis=1)]),
    )


def _label(count: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Connected components by hooking roots to the smaller label and jumping pointers, with a bound on both."""
    parent = np.arange(count)
    for _ in range(4 * max(int(np.log2(count + 1)), 1) + 64):
        roots_u, roots_v = parent[u], parent[v]
        if np.array_equal(roots_u, roots_v):
            return np.asarray(np.unique(parent, return_inverse=True)[1])
        low = np.minimum(roots_u, roots_v)
        np.minimum.at(parent, roots_u, low)
        np.minimum.at(parent, roots_v, low)
        for _ in range(64):
            grand = parent[parent]
            if np.array_equal(grand, parent):
                break
            parent = grand
        else:
            raise RuntimeError("pointer jumping did not settle within its bound")
    raise RuntimeError("component labelling did not settle within its bound")


@dataclass
class _Kept:
    edge: np.ndarray
    category: np.ndarray
    pruned: list[dict[str, Any]]
    #: The node each anchor was mapped to, -1 where its piece has none.
    anchor_node: np.ndarray


def _adjacency(count: int, u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ends = np.concatenate([u, v])
    others = np.concatenate([v, u])
    edge = np.concatenate([np.arange(len(u)), np.arange(len(u))])
    order = np.argsort(ends, kind="stable")
    pointer = np.concatenate(([0], np.cumsum(np.bincount(ends, minlength=count))))
    return pointer, others[order], edge[order]


def _retain(medial: _Medial, anchors: list[tuple[np.ndarray, np.ndarray, Point]], *, vanished: bool, bay_m: float = BAY_REACH_M) -> _Kept:
    """Keep every passage and loop, bays of at least ``bay_m`` from where they hang, and the way to each anchor.

    Leaves that are not joins are peeled until only the paths between joins and
    the loops remain: that core is kept whole. A component with no join is a
    body the offset removed; its longest path is its core. Every peeled branch
    is then judged from the node it hangs on: its longest way at least
    ``bay_m`` keeps that way, and the branches off it are judged in turn. An
    anchor keeps the way from its edge to the kept network, however short. It
    is on the kept network already when a kept line passes within its own
    radius there, plus ``ANCHOR_BALL_M``: the line's disc reaches the anchor's
    bank, whatever stub the anchor's corner casts. Otherwise its candidates are
    the edges its bank point faces, a kept one first.
    """
    count = len(medial.xy)
    u, v, length = medial.u, medial.v, medial.length
    pointer, neighbour, via = _adjacency(count, u, v)
    joins = medial.rim
    component = medial.component
    components = int(component.max()) + 1 if count else 0
    nodes = np.bincount(component, minlength=components)
    edges = np.bincount(component[u], minlength=components)
    joined = np.bincount(component, weights=joins.astype(float), minlength=components)
    protected = joins.copy()
    # A body the offset removed has no join: the longest way of its longest piece is its core, and
    # that of any other piece at least ``bay_m`` long; a shorter piece, cut off at a pinch, is a
    # fragment. Elsewhere a component without a join has no way to the contour and keeps nothing
    # but what an anchor asks for.
    total_length = np.bincount(component[u], weights=length, minlength=components)
    longest = int(np.argmax(total_length)) if components else -1
    fragment = np.zeros(components, dtype=bool)
    if vanished:
        fragment = (joined == 0) & (total_length < bay_m) & (np.arange(components) != longest)
    for c in np.flatnonzero((joined == 0) & (edges == nodes - 1) & ~fragment) if vanished else []:
        start = int(np.flatnonzero(component == c)[0])
        far = _farthest(start, pointer, neighbour, via, length)[0]
        protected[[far, _farthest(far, pointer, neighbour, via, length)[0]]] = True
    degree = np.diff(pointer).copy()
    parent = np.full(count, -1)
    parent_edge = np.full(count, -1)
    peeled = np.zeros(count, dtype=bool)
    order: list[int] = []
    stack = [int(i) for i in np.flatnonzero((degree == 1) & ~protected)]
    for _ in range(2 * count + 1):
        if not stack:
            break
        x = int(stack.pop())
        if peeled[x]:
            continue
        peeled[x] = True
        order.append(x)
        for k in range(pointer[x], pointer[x + 1]):
            y = neighbour[k]
            if peeled[y]:
                continue
            parent[x], parent_edge[x] = y, via[k]
            degree[y] -= 1
            if degree[y] == 1 and not protected[y]:
                stack.append(int(y))
            break
    else:
        raise RuntimeError("peeling did not finish within its bound")
    kept = np.zeros(len(u), dtype=bool)
    category = np.full(len(u), "", dtype=object)
    core_edge = ~peeled[u] & ~peeled[v]
    kept[core_edge] = True
    core_kind = np.where(joined >= 2, PASSAGE, np.where(joined == 1, LOOP, VANISHED if vanished else ISOLATED))
    category[core_edge] = core_kind[component[u[core_edge]]]
    height = np.zeros(count)
    best = np.full(count, -1)
    total = np.zeros(count)
    children: dict[int, list[int]] = {}
    for x in order:
        p = parent[x]
        if p < 0:
            continue
        children.setdefault(int(p), []).append(x)
        reach = height[x] + length[parent_edge[x]]
        total[p] += total[x] + length[parent_edge[x]]
        if reach > height[p]:
            height[p], best[p] = reach, x
    pending = [x for x in order if parent[x] >= 0 and not peeled[parent[x]]]
    for _ in range(count + 1):
        if not pending:
            break
        x = int(pending.pop())
        if height[x] + length[parent_edge[x]] < bay_m:
            continue
        node = x
        for _ in range(count + 1):
            kept[parent_edge[node]] = True
            category[parent_edge[node]] = BAY
            pending.extend(y for y in children.get(int(node), []) if y != best[node])
            if best[node] < 0:
                break
            node = int(best[node])
    chosen = np.full(len(anchors), -1)
    kept_ids = np.flatnonzero(kept)
    kept_lines = np.asarray(shapely.linestrings(np.stack([medial.xy[u[kept_ids]], medial.xy[v[kept_ids]]], axis=1)), dtype=object)
    kept_tree = shapely.STRtree(kept_lines) if len(kept_ids) else None
    # No kept line's disc is wider than its radius, which the clip bounds by d plus a sampling error.
    medial_reach = (
        float(np.hypot(*(medial.xy[u[kept_ids]] - medial.sampler.local(medial.a[kept_ids]) - medial.sampler.origin).T).max())
        if len(kept_ids)
        else 0.0
    )
    for index, (candidates, distances, point) in enumerate(anchors):
        if kept_tree is not None:
            # Any kept line whose disc all but reaches the anchor, not only the nearest one.
            reachable = kept_tree.query(point, predicate="dwithin", distance=medial_reach + ANCHOR_BALL_M)
            if len(reachable):
                edges_near = kept_ids[reachable]
                gaps = np.asarray(shapely.distance(kept_lines[reachable], point))
                generator = medial.sampler.local(medial.a[edges_near]) + medial.sampler.origin
                radius = np.maximum(np.hypot(*(medial.xy[u[edges_near]] - generator).T), np.hypot(*(medial.xy[v[edges_near]] - generator).T))
                inside = gaps <= radius + ANCHOR_BALL_M
                if inside.any():
                    chosen[index] = u[edges_near[np.flatnonzero(inside)[np.argmin((gaps - radius)[inside])]]]
                    continue
        if not len(candidates):
            continue
        near = kept[candidates]
        edge = candidates[np.flatnonzero(near)[np.argmin(distances[near])] if near.any() else int(np.argmin(distances))]
        # The end that hangs from this edge keeps it; a core edge is kept already.
        chosen[index] = u[edge] if parent_edge[u[edge]] == edge else v[edge]
    for anchor in chosen[chosen >= 0]:
        node = int(anchor)
        for _ in range(count + 1):
            if not peeled[node] or parent_edge[node] < 0 or kept[parent_edge[node]]:
                break
            kept[parent_edge[node]] = True
            category[parent_edge[node]] = ANCHORED
            node = int(parent[node])
    pruned = []
    for c in np.flatnonzero(fragment):
        members = np.flatnonzero(component[u] == c)
        if kept[members].any():
            continue
        pruned.append(
            {
                "category": "fragment",
                "longest_m": float(total_length[c]),
                "total_m": float(total_length[c]),
                "geometry": shapely.union_all(shapely.linestrings(np.stack([medial.xy[u[members]], medial.xy[v[members]]], axis=1))),
            }
        )
    for x in order:
        p = parent[x]
        if p < 0 or kept[parent_edge[x]] or (peeled[p] and (parent_edge[p] < 0 or not kept[parent_edge[p]])):
            continue
        path = [int(p), int(x)]
        for _ in range(count + 1):
            if best[path[-1]] < 0:
                break
            path.append(int(best[path[-1]]))
        pruned.append(
            {
                "category": BAY if joins[p] else "side",
                "longest_m": float(height[x] + length[parent_edge[x]]),
                "total_m": float(total[x] + length[parent_edge[x]]),
                "geometry": LineString(medial.xy[path]),
            }
        )
    return _Kept(kept, category, pruned, chosen)


def _farthest(start: int, pointer: np.ndarray, neighbour: np.ndarray, via: np.ndarray, length: np.ndarray) -> tuple[int, float]:
    """The node of a tree farthest from ``start`` along its edges."""
    distance = {start: 0.0}
    stack = [start]
    for _ in range(len(pointer)):
        if not stack:
            break
        x = stack.pop()
        for k in range(pointer[x], pointer[x + 1]):
            y = int(neighbour[k])
            if y not in distance:
                distance[y] = distance[x] + float(length[via[k]])
                stack.append(y)
    far = max(distance, key=lambda node: distance[node])
    return far, distance[far]


@dataclass
class _Middle:
    """How far each node is from the true middle between the exact bank segments, and what the gate allows there."""

    error: np.ndarray
    allowance: np.ndarray
    width: np.ndarray
    radius: np.ndarray
    sides: np.ndarray


def _middle(medial: _Medial, bank: _Bank, subset: np.ndarray, chunk: int = 100_000) -> _Middle:
    """The middle figures of the nodes in ``subset``, a chunk at a time; other nodes read zero error and no allowance."""
    count = len(medial.xy)
    out = _Middle(np.zeros(count), np.zeros(count), np.zeros(count), np.zeros(count), np.zeros(count, dtype=int))
    for start in range(0, len(subset), chunk):
        nodes = subset[start : start + chunk]
        part = _middle_of(medial.xy[nodes], medial.gens[nodes], medial.sampler, bank)
        for name in ("error", "allowance", "width", "radius", "sides"):
            getattr(out, name)[nodes] = getattr(part, name)
    if medial.made.any():
        # A node placed in a speck carries the line through it: a transition, not a middle.
        out.error[medial.made] = 0.0
        out.sides[medial.made] = 1
    return out


def _middle_of(xy: np.ndarray, gens: np.ndarray, sampler: _Sampler, bank: _Bank) -> _Middle:
    """Measure each node against the bank segments its samples lie on, not against the samples.

    A node's samples fall into sides: samples within two steps of each other on
    a ring are one side. The exact distance to each side is the least distance
    to the bank segments of its samples and their neighbours. Between two sides
    the true middle is where the two distances agree; the node is off it by
    their difference over the rate at which it changes, ``|u_A - u_B|``. Where
    three sides meet, the displacement that equalises all three is solved for.
    """
    count = len(xy)
    present = gens >= 0
    safe = np.where(present, gens, 0)
    segment = sampler.segment(safe)
    ring = bank.ring[segment]
    first, size = bank.ring_first[ring], bank.ring_count[ring]
    candidates = np.stack(
        [segment, np.where(segment == first, first + size - 1, segment - 1), np.where(segment == first + size - 1, first, segment + 1)], axis=-1
    )
    x = xy[:, None, None, :]
    one, other = bank.start[candidates], bank.end[candidates]
    delta = other - one
    squared = (delta**2).sum(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.clip(np.where(squared > 0, ((x - one) * delta).sum(axis=-1) / squared, 0.0), 0.0, 1.0)
    foot = one + t[..., None] * delta
    distance = np.hypot(*np.moveaxis(x - foot, -1, 0))
    nearest = np.argmin(distance, axis=-1)
    f = np.take_along_axis(distance, nearest[..., None], axis=-1)[..., 0]
    foot = np.take_along_axis(foot, nearest[..., None, None], axis=-2)[..., 0, :]
    f = np.where(present, f, np.inf)
    same = np.zeros((count, 3, 3), dtype=bool)
    for i, j in ((0, 1), (0, 2), (1, 2)):
        both = present[:, i] & present[:, j]
        near = np.zeros(count, dtype=bool)
        near[both] = sampler.neighbours(gens[both, i], gens[both, j], reach=2)
        same[:, i, j] = same[:, j, i] = near
    # Merge each generator into the side of an earlier one it neighbours.
    side = np.tile(np.arange(3), (count, 1))
    for j in (1, 2):
        for i in range(j):
            joined = same[:, i, j] & (side[:, j] == j)
            side[joined, j] = side[joined, i]
    side = np.where(present, side, -1)
    best_f = np.full((count, 3), np.inf)
    best_foot = np.zeros((count, 3, 2))
    for j in range(3):
        for s in range(3):
            better = (side[:, j] == s) & (f[:, j] < best_f[:, s])
            best_f[better, s] = f[better, j]
            best_foot[better, s] = foot[better, j]
    sides = np.isfinite(best_f).sum(axis=1)
    radius = best_f.min(axis=1)
    # A node on the bank, where an edge was cut at the water's edge, has no middle to be measured from.
    sides = np.where(radius < 1e-6, 1, sides)
    order = np.argsort(best_f, axis=1)
    fs = np.take_along_axis(best_f, order, axis=1)
    feet = np.take_along_axis(best_foot, order[..., None], axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        units = (xy[:, None, :] - feet) / fs[..., None]
    error = np.zeros(count)
    width = 2 * radius
    two = sides == 2
    with np.errstate(invalid="ignore"):
        pull = np.hypot(*(units[two, 0] - units[two, 1]).T)
    error[two] = np.abs(fs[two, 0] - fs[two, 1]) / np.maximum(pull, 1e-9)
    width[two] = fs[two, 0] + fs[two, 1]
    three = np.flatnonzero(sides == 3)
    if len(three):
        matrix = np.stack([units[three, 0] - units[three, 1], units[three, 0] - units[three, 2]], axis=1)
        rhs = -np.stack([fs[three, 0] - fs[three, 1], fs[three, 0] - fs[three, 2]], axis=1)
        solvable = np.abs(np.linalg.det(matrix)) > 1e-9
        shift = np.zeros((len(three), 2))
        shift[solvable] = np.linalg.solve(matrix[solvable], rhs[solvable][..., None])[..., 0]
        error[three] = np.where(solvable, np.hypot(*shift.T), np.abs(fs[three, 0] - fs[three, 2]))
        width[three] = 2 * fs[three, 0]
    allowance = np.minimum(MIDDLE_LIMIT_M, MIDDLE_SHARE * width)
    return _Middle(error, allowance, width, radius, sides)


@dataclass
class _Network:
    medial: _Medial
    kept: _Kept
    middle: _Middle
    #: Kept nodes that join the contour, with their snapped coordinates, raw ring, segment.
    join_node: np.ndarray
    join_xy: np.ndarray
    join_ring: np.ndarray
    join_segment: np.ndarray
    anchor_node: np.ndarray
    in_closed: np.ndarray
    kept_closed: np.ndarray
    kept_by: list[str]
    anchor_rows: list[dict[str, Any]]
    pruned_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _network(
    body: int,
    water: BaseGeometry,
    bank: _Bank,
    bank_tree: shapely.STRtree,
    seeds: list[BaseGeometry],
    specks: list[Polygon],
    closed: _Closed,
    anchors: shapely.STRtree | None,
    rings: list[np.ndarray],
    *,
    offset_m: float,
    step: float,
    tile_m: float,
    failures: list[dict[str, Any]],
) -> _Network:
    """Build, prune and measure the centre network of one body, halving the sampling step where the middle gate fails.

    The halving is local: the bank segments within twice a failing node's
    radius, plus two steps, are sampled at half their step, and only the tiles
    that read them are triangulated again.
    """
    vanished = not rings
    feet = _anchor_feet(bank, bank_tree, closed, anchors)
    # An anchor's own corner may cast a branch that no closed-off piece touches: seed it too.
    seeds = [*seeds, *np.asarray(shapely.buffer(shapely.points(feet[1]), 1.0), dtype=object)] if len(feet[1]) else seeds
    level = np.zeros(len(bank.lines), dtype=int)
    cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, dict[str, Any]]] = {}
    halvings = 0
    for halvings in range(CENTRE_HALVINGS + 1):
        medial = _medial(water, bank, bank_tree, seeds, offset_m=offset_m, steps=step / 2.0**level, tile_m=tile_m, cache=cache, feet=feet)
        false_joins = _false_joins(medial, rings, specks)
        pinches = _tie_pinches(medial, water)
        candidates, anchor_rows = _anchor_edges(body, medial, bank, bank_tree, closed, anchors)
        kept = _retain(medial, candidates, vanished=vanished)
        anchor_node = kept.anchor_node
        on_kept = np.zeros(len(medial.xy), dtype=bool)
        on_kept[medial.u[kept.edge]] = on_kept[medial.v[kept.edge]] = True
        middle = _middle(medial, bank, np.flatnonzero(on_kept))
        failing = on_kept & (middle.sides >= 2) & (middle.error > middle.allowance)
        # Where an edge was cut at the water's edge the middle breaks into pieces, as at a pinch
        # narrower than a step: the samples there are too sparse, like a node off the middle.
        coarse = failing | (medial.bank_end & (halvings < BANK_END_HALVINGS))
        if not coarse.any() or halvings == CENTRE_HALVINGS:
            break
        reach = np.where(failing, 2 * middle.radius + 2 * step, 3 * step)[coarse]
        near = bank_tree.query(shapely.points(medial.xy[coarse]), predicate="dwithin", distance=reach)[1]
        if not len(near) or (level[near] >= CENTRE_HALVINGS).all():
            break
        level[near] = np.minimum(level[near] + 1, CENTRE_HALVINGS)
    for where in np.flatnonzero(failing):
        failures.append(
            {
                "body": body,
                "kind": "middle",
                "detail": f"{middle.error[where]:.3f} m from the middle of {middle.width[where]:.2f} m of water after {halvings} local halvings",
                "geometry": Point(medial.xy[where]),
            }
        )
    isolated = kept.edge & (kept.category == ISOLATED)
    anchored_alone = kept.edge & ~np.isin(medial.component[medial.u], medial.component[medial.rim]) & ~np.full(len(medial.u), vanished)
    for where in np.unique(medial.component[medial.u[isolated | anchored_alone]]):
        at_node = int(np.flatnonzero(medial.component == where)[0])
        failures.append(
            {"body": body, "kind": "isolated", "detail": "kept centre with no join to the contour", "geometry": Point(medial.xy[at_node])}
        )
    if medial.diagnostics["window_open"]:
        failures.append({"body": body, "kind": "window", "detail": "a kept component still runs out of its window", "geometry": Point(medial.xy[0])})
    join_node = np.flatnonzero(medial.rim & on_kept)
    join_xy, join_ring, join_segment, gap = _snap_joins(body, medial.xy[join_node], rings, failures)
    close = gap <= JOIN_SNAP_M
    medial.xy[join_node[close]] = join_xy[close]
    far = np.flatnonzero(~close)
    if len(far):
        # A join up to ``TRANSITION_M`` off the contour reaches it on a straight transition, Narrow water.
        ends = join_node[far]
        added = np.arange(len(medial.xy), len(medial.xy) + len(far))
        edge_of = np.array([int(np.flatnonzero(kept.edge & ((medial.u == e) | (medial.v == e)))[0]) for e in ends])
        medial.xy = np.concatenate([medial.xy, join_xy[far]])
        medial.made = np.concatenate([medial.made, np.ones(len(far), dtype=bool)])
        medial.bank_end = np.concatenate([medial.bank_end, np.zeros(len(far), dtype=bool)])
        medial.gens = np.concatenate([medial.gens, medial.gens[ends]])
        medial.rim = np.concatenate([medial.rim, np.ones(len(far), dtype=bool)])
        medial.rim[ends] = False
        medial.component = np.concatenate([medial.component, medial.component[ends]])
        medial.u = np.concatenate([medial.u, ends])
        medial.v = np.concatenate([medial.v, added])
        medial.a = np.concatenate([medial.a, medial.a[edge_of]])
        medial.b = np.concatenate([medial.b, medial.b[edge_of]])
        medial.length = np.concatenate([medial.length, gap[far]])
        kept.edge = np.concatenate([kept.edge, np.ones(len(far), dtype=bool)])
        kept.category = np.concatenate([kept.category, kept.category[edge_of]])
        on_kept = np.concatenate([on_kept, np.ones(len(far), dtype=bool)])
        for name in ("error", "allowance", "width", "radius"):
            setattr(middle, name, np.concatenate([getattr(middle, name), getattr(middle, name)[ends]]))
        # The transition's far end lies on the contour: no middle is measured there.
        middle.error[added] = 0.0
        middle.sides = np.concatenate([middle.sides, np.ones(len(far), dtype=int)])
        join_node = join_node.copy()
        join_node[far] = added
    # Anchors are recorded where their nodes finally lie: a join moves onto the contour.
    for row, node in zip(anchor_rows, anchor_node, strict=True):
        if node < 0:
            # Its bank faces open water or no medial edge of radius under d: no branch holds it; 12d gives it a spur.
            failures.append(
                {"body": body, "kind": "anchor without branch", "detail": "the anchor's bank faces no centre edge", "geometry": row["at"]}
            )
        else:
            row["node_m"] = float(shapely.distance(Point(medial.xy[node]), row["at"]))
            row["geometry"] = Point(medial.xy[node])
        row["kept"] = bool(node >= 0 and on_kept[node])
        del row["at"]
    middles = (medial.xy[medial.u] + medial.xy[medial.v]) / 2
    in_closed = np.zeros(len(medial.u), dtype=bool)
    kept_closed = np.zeros(len(closed.pieces), dtype=bool)
    kept_by = [""] * len(closed.pieces)
    if vanished:
        in_closed[:] = True
    elif closed.pieces and len(middles):
        edge, _ = shapely.STRtree(closed.pieces).query(shapely.points(middles), predicate="within")
        in_closed[edge] = True
        # A piece is kept when a kept edge runs into it, not when one grazes its outline: the edges are
        # short, and one whose middle lies in the piece runs into it.
        kept_ids = np.flatnonzero(kept.edge)
        hit, piece = shapely.STRtree(closed.pieces).query(shapely.points(middles[kept_ids]), predicate="within")
        for e, p in zip(kept_ids[hit], piece, strict=True):
            kept_closed[p] = True
            kept_by[p] = kept_by[p] or str(kept.category[e])
    for row in anchor_rows:
        if row["kept"] and not kept_closed[row["closed"]]:
            # Its anchor's branch is kept, though it may end where the offset's discs still reach.
            kept_closed[row["closed"]] = True
            kept_by[row["closed"]] = ANCHORED
    pruned_rows = [{"body": body, **row} for row in kept.pruned]
    lengths = pd.Series(medial.length[kept.edge]).groupby(kept.category[kept.edge]).sum()
    summary = {
        **{f"medial_{k}": v for k, v in medial.diagnostics.items()},
        "false_joins": false_joins,
        "bank_ends": int(medial.bank_end.sum()),
        "pinches_tied": pinches,
        "halvings": halvings,
        "kept_m": {str(k): round(float(v), 1) for k, v in lengths.items()},
        "joins": len(join_node),
        "pruned": len(pruned_rows),
        "pruned_m": round(float(sum(r["longest_m"] for r in pruned_rows)), 1),
    }
    return _Network(
        medial,
        kept,
        middle,
        join_node,
        join_xy,
        join_ring,
        join_segment,
        anchor_node,
        in_closed,
        kept_closed,
        kept_by,
        anchor_rows,
        pruned_rows,
        summary,
    )


def _false_joins(medial: _Medial, rings: list[np.ndarray], specks: list[Polygon]) -> int:
    """Clear the join mark from ends no contour holds, and tie each through or across the gap it was cut at.

    The clip at radius d is where the middle meets the contour. Beside a speck
    of offset, which the contour leaves out, the middle meets radius d where no
    contour is: 3.6 m from the nearest at Kloten. An end farther than
    ``TRANSITION_M`` from the contour is no join. Two or more such ends beside
    one speck are tied to a node in it, so the middle runs through; any other is
    tied to the nearest node of another piece of the middle within
    ``FALSE_JOIN_REACH_M``. Returns how many ends were cleared.
    """
    ends = np.flatnonzero(medial.rim)
    if not len(ends):
        return 0
    if rings:
        lines = np.concatenate([_edges(coords) for coords in rings])
        _, gap = shapely.STRtree(lines).query_nearest(shapely.points(medial.xy[ends]), return_distance=True, all_matches=False)
    else:
        gap = np.full(len(ends), np.inf)
    false = ends[gap > TRANSITION_M]
    if not len(false):
        return 0
    medial.rim[false] = False
    new_xy: list[np.ndarray] = []
    added: list[tuple[int, int]] = []
    tied = np.zeros(len(medial.xy), dtype=bool)
    if specks:
        speck_tree = shapely.STRtree(np.asarray(specks, dtype=object))
        near, speck = speck_tree.query(shapely.points(medial.xy[false]), predicate="dwithin", distance=FALSE_JOIN_REACH_M)
        for which in np.unique(speck):
            members = np.unique(false[near[speck == which]])
            if len(members) < 2:
                continue
            node = len(medial.xy) + len(new_xy)
            new_xy.append(np.asarray(shapely.get_coordinates(specks[which].representative_point())[0]))
            added.extend((int(m), node) for m in members)
            tied[members] = True
    node_tree = shapely.STRtree(np.asarray(shapely.points(medial.xy), dtype=object))
    for end in false[~tied[false]]:
        near_nodes = node_tree.query(Point(medial.xy[end]), predicate="dwithin", distance=FALSE_JOIN_REACH_M)
        near_nodes = near_nodes[medial.component[near_nodes] != medial.component[end]]
        if len(near_nodes):
            added.append((int(end), int(near_nodes[np.argmin(np.hypot(*(medial.xy[near_nodes] - medial.xy[end]).T))])))
    if added:
        one, other = np.asarray(added).T
        if new_xy:
            first = np.array([one[np.flatnonzero(other == len(medial.xy) + k)[0]] for k in range(len(new_xy))])
            medial.made = np.concatenate([medial.made, np.ones(len(new_xy), dtype=bool)])
            medial.bank_end = np.concatenate([medial.bank_end, np.zeros(len(new_xy), dtype=bool)])
            medial.xy = np.concatenate([medial.xy, np.asarray(new_xy)])
            medial.gens = np.concatenate([medial.gens, medial.gens[first]])
            medial.rim = np.concatenate([medial.rim, np.zeros(len(new_xy), dtype=bool)])
        medial.u = np.concatenate([medial.u, one.astype(medial.u.dtype)])
        medial.v = np.concatenate([medial.v, other.astype(medial.v.dtype)])
        medial.a = np.concatenate([medial.a, medial.gens[one, 0].astype(medial.a.dtype)])
        medial.b = np.concatenate([medial.b, medial.gens[one, 1].astype(medial.b.dtype)])
        medial.length = np.hypot(*(medial.xy[medial.u] - medial.xy[medial.v]).T)
        medial.component = _label(len(medial.xy), medial.u, medial.v)
    return int(len(false))


def _tie_pinches(medial: _Medial, water: BaseGeometry) -> int:
    """Tie the middle through a pinch it was cut at: an edge cut at the water's edge, to the nearest other piece.

    Where the water narrows below a step the samples' diagram crosses the bank
    and is cut there, and the middle falls apart at a pinch the bank's own
    ring passes through (0.11 m of water in an Abisko river). A cut end of a
    piece at least 2d long is tied to the nearest node of another such piece
    within ``FALSE_JOIN_REACH_M`` when the straight tie lies in the water; a
    shorter scrap by the bank is left to pruning. Returns how many were tied.
    """
    ends = np.flatnonzero(medial.bank_end)
    if not len(ends):
        return 0
    # Only a middle broken in two: a scrap the diagram leaves by the bank is no side of a pinch.
    size = np.bincount(medial.component[medial.u], weights=medial.length, minlength=int(medial.component.max()) + 1)
    ends = ends[size[medial.component[ends]] >= BAY_REACH_M]
    node_tree = shapely.STRtree(np.asarray(shapely.points(medial.xy), dtype=object))
    added: list[tuple[int, int]] = []
    for end in ends:
        near = node_tree.query(Point(medial.xy[end]), predicate="dwithin", distance=FALSE_JOIN_REACH_M)
        near = near[(medial.component[near] != medial.component[end]) & (size[medial.component[near]] >= BAY_REACH_M)]
        if not len(near):
            continue
        target = int(near[np.argmin(np.hypot(*(medial.xy[near] - medial.xy[end]).T))])
        if shapely.covers(water, LineString([medial.xy[end], medial.xy[target]])):
            added.append((int(end), target))
    if added:
        one, other = np.asarray(added).T
        medial.u = np.concatenate([medial.u, one.astype(medial.u.dtype)])
        medial.v = np.concatenate([medial.v, other.astype(medial.v.dtype)])
        medial.a = np.concatenate([medial.a, medial.gens[one, 0].astype(medial.a.dtype)])
        medial.b = np.concatenate([medial.b, medial.gens[one, 1].astype(medial.b.dtype)])
        medial.length = np.hypot(*(medial.xy[medial.u] - medial.xy[medial.v]).T)
        medial.component = _label(len(medial.xy), medial.u, medial.v)
    return len(added)


def _anchor_feet(bank: _Bank, bank_tree: shapely.STRtree, closed: _Closed, anchors: shapely.STRtree | None) -> tuple[np.ndarray, np.ndarray]:
    """The nearest bank segment and bank point of each access anchor in closed-off water, in the order of the pieces."""
    points = [anchors.geometries[a] for i in range(len(closed.pieces)) for a in closed.anchors[i]] if anchors is not None else []
    if not points:
        return np.empty(0, dtype=int), np.empty((0, 2))
    (_, segment), _ = bank_tree.query_nearest(points, return_distance=True, all_matches=False)
    feet = shapely.get_coordinates(shapely.line_interpolate_point(bank.lines[segment], shapely.line_locate_point(bank.lines[segment], points)))
    return segment, feet


def _nearest_samples(sampler: _Sampler, bank: _Bank, segments: np.ndarray, feet: np.ndarray, count: int = 3) -> np.ndarray:
    """The ``count`` samples nearest each foot on its segment and the two beside it, one row per foot."""
    out = np.full((len(segments), count), -1, dtype=np.int64)
    for index, (segment, foot) in enumerate(zip(segments, feet, strict=True)):
        ring = bank.ring[segment]
        first, size = bank.ring_first[ring], bank.ring_count[ring]
        ids = sampler.ids(first + (segment - first + np.array([-1, 0, 1])) % size)
        chosen = ids[np.argsort(np.hypot(*(sampler.local(ids) + sampler.origin - foot).T))[:count]]
        out[index, : len(chosen)] = chosen
    return out


def _anchor_edges(
    body: int, medial: _Medial, bank: _Bank, bank_tree: shapely.STRtree, closed: _Closed, anchors: shapely.STRtree | None
) -> tuple[list[tuple[np.ndarray, np.ndarray, Point]], list[dict[str, Any]]]:
    """Each anchor in closed-off water with the medial edges its bank point faces, their distances to it, and the anchor.

    The medial edges the samples nearest the anchor's bank point generate bound
    their Voronoi cells on the water side, where the bank's normal there meets
    the middle: the branch whose water holds the anchor, however the samples near
    it fall. Edges across the water are preferred to a corner's stub; at a convex
    corner the stub is the corner's own branch. An anchor whose bank faces no
    edge within d faces open water and belongs to no branch.
    """
    rows: list[dict[str, Any]] = []
    candidates: list[tuple[np.ndarray, np.ndarray, Point]] = []
    if anchors is None or not len(medial.u):
        return candidates, rows
    lines = np.asarray(shapely.linestrings(np.stack([medial.xy[medial.u], medial.xy[medial.v]], axis=1)), dtype=object)
    generator = np.concatenate([medial.a, medial.b])
    order = np.argsort(generator, kind="stable")
    generator, edge_of = generator[order], np.concatenate([np.arange(len(medial.a)), np.arange(len(medial.a))])[order]
    sampler = medial.sampler
    nearest = _nearest_samples(sampler, bank, *_anchor_feet(bank, bank_tree, closed, anchors))
    row = 0
    for index in range(len(closed.pieces)):
        for anchor in closed.anchors[index]:
            point = anchors.geometries[anchor]
            wanted = nearest[row][nearest[row] >= 0]
            row += 1
            lo, hi = np.searchsorted(generator, wanted, side="left"), np.searchsorted(generator, wanted, side="right")
            faced = np.unique(np.concatenate([edge_of[a:b] for a, b in zip(lo, hi, strict=True)])) if len(wanted) else np.empty(0, dtype=int)
            if len(faced):
                # Across the water, the two samples seen well apart; not a corner's stub, whose two are nearly in line.
                middle = (medial.xy[medial.u[faced]] + medial.xy[medial.v[faced]]) / 2
                one = sampler.local(medial.a[faced]) + sampler.origin - middle
                other = sampler.local(medial.b[faced]) + sampler.origin - middle
                cosine = (one * other).sum(axis=1) / np.maximum(np.hypot(*one.T) * np.hypot(*other.T), 1e-12)
                opposing = cosine <= np.cos(np.radians(120))
                faced = faced[opposing] if opposing.any() else faced
            candidates.append((faced, np.asarray(shapely.distance(lines[faced], point)) if len(faced) else np.empty(0), point))
            rows.append({"anchor": int(anchor), "body": body, "closed": index, "node_m": np.nan, "kept": False, "at": point, "geometry": point})
    return candidates, rows


def _snap_joins(
    body: int, points: np.ndarray, rings: list[np.ndarray], failures: list[dict[str, Any]]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Each join's nearest point on the raw contour, as the ring and segment it will be inserted into, and its distance."""
    if not len(points):
        return np.empty((0, 2)), np.empty(0, dtype=int), np.empty(0, dtype=int), np.empty(0)
    lines = np.concatenate([_edges(coords) for coords in rings])
    ring_of = np.concatenate([np.full(len(coords) - 1, i) for i, coords in enumerate(rings)])
    segment_of = np.concatenate([np.arange(len(coords) - 1) for coords in rings])
    (_, nearest), distance = shapely.STRtree(lines).query_nearest(shapely.points(points), return_distance=True, all_matches=False)
    snapped = shapely.get_coordinates(
        shapely.line_interpolate_point(lines[nearest], shapely.line_locate_point(lines[nearest], shapely.points(points)))
    )
    ring, segment = ring_of[nearest], segment_of[nearest]
    for index in np.flatnonzero(distance > TRANSITION_M):
        failures.append(
            {
                "body": body,
                "kind": "join",
                "detail": f"the middle meets the contour {distance[index]:.3f} m from it",
                "geometry": Point(points[index]),
            }
        )
    # A join on a vertex is that vertex, so the contour keeps its coordinates exactly.
    for which in range(len(snapped)):
        coords = rings[ring[which]]
        for vertex in (segment[which], segment[which] + 1):
            if np.hypot(*(coords[vertex] - snapped[which])) < 1e-6:
                snapped[which] = coords[vertex]
    return snapped, ring, segment, distance


def _with_joins(rings: list[np.ndarray], join_xy: np.ndarray, join_ring: np.ndarray, join_segment: np.ndarray) -> list[np.ndarray]:
    """The raw rings with every join inserted as a vertex of the segment it lies on."""
    out = []
    for index, coords in enumerate(rings):
        own = np.flatnonzero(join_ring == index)
        if not len(own):
            out.append(coords)
            continue
        inserted: dict[int, list[np.ndarray]] = {}
        for j in own:
            point = join_xy[j]
            s = int(join_segment[j])
            if any(np.array_equal(point, coords[k]) for k in (s, s + 1)):
                continue
            inserted.setdefault(s, []).append(point)
        result: list[np.ndarray] = []
        for s in range(len(coords)):
            result.append(coords[s])
            if s in inserted:
                along = [float(np.hypot(*(point - coords[s]))) for point in inserted[s]]
                result.extend(inserted[s][k] for k in np.argsort(along))
        out.append(np.asarray(result))
    return out


def _pin(pieces: list[_Piece], join_xy: np.ndarray) -> None:
    """Pin every join a piece carries, so simplification keeps the vertex the centre line ends on."""
    if not len(join_xy):
        return
    keys = join_xy[:, 0] + 1j * join_xy[:, 1]
    for piece in pieces:
        found = np.flatnonzero(np.isin(piece.coords[:, 0] + 1j * piece.coords[:, 1], keys))
        if len(found):
            piece.pinned = np.union1d(piece.pinned, found)


def _cap_source(coords: np.ndarray, bank: _Bank, tree: shapely.STRtree, joins: np.ndarray) -> str:
    """Open water where the nearest bank point jumps within the cap, from one shoulder to another; shore where one shoulder holds it.

    A join sits where two stretches of bank are equally near, so its own nearest
    bank point says nothing; its vertices are left out of the test.
    """
    if len(joins):
        keys = joins[:, 0] + 1j * joins[:, 1]
        coords = coords[~np.isin(coords[:, 0] + 1j * coords[:, 1], keys)]
    if len(coords) < 2:
        return SHORE
    _, _, nearest = _generators(coords, bank, tree)
    held = shapely.get_coordinates(nearest)
    step = np.hypot(*np.diff(coords, axis=0).T)
    move = np.hypot(*np.diff(held, axis=0).T)
    return OPEN_WATER if bool((move > step + JUMP_M).any()) else SHORE


def _centre_pieces(
    body: int,
    network: _Network,
    water: BaseGeometry,
    owners: _Owners,
    closed: _Closed,
    *,
    dam_tree: shapely.STRtree | None,
    extent: BaseGeometry | None,
    tolerance_m: float,
    to_page: Transformer,
    from_page: Transformer,
    contour_decoded: list[LineString],
    contour_raw: list[LineString],
    failures: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Cut the kept network into pieces, split them by height owner, dams and crop, simplify and validate each."""
    medial, kept, middle = network.medial, network.kept, network.middle
    if not kept.edge.any():
        return [], []
    count = len(medial.xy)
    edges = np.flatnonzero(kept.edge)
    u, v = medial.u[edges], medial.v[edges]
    pointer, neighbour, via = _adjacency(count, u, v)
    degree = np.diff(pointer)
    anchor = np.zeros(count, dtype=bool)
    anchor[network.anchor_node[network.anchor_node >= 0]] = True
    breaks = (degree > 0) & ((degree != 2) | medial.rim | anchor)
    kind = np.where(medial.rim, JOIN, np.where(anchor, ANCHOR, np.where(degree >= 3, JUNCTION, END)))
    used = np.zeros(len(edges), dtype=bool)
    walks: list[tuple[list[int], list[int], str, str]] = []

    def walk(start: int, first: int) -> tuple[list[int], list[int]]:
        path, along = [start], []
        edge, node = first, start
        for _ in range(len(edges) + 1):
            used[edge] = True
            along.append(edge)
            node = int(u[edge] if v[edge] == node else v[edge])
            path.append(node)
            if breaks[node] or node == start:
                break
            nexts = [via[k] for k in range(pointer[node], pointer[node + 1]) if not used[via[k]]]
            if not nexts:
                break
            edge = int(nexts[0])
        return path, along

    for start in np.flatnonzero(breaks):
        for k in range(pointer[start], pointer[start + 1]):
            if not used[via[k]]:
                path, along = walk(int(start), int(via[k]))
                walks.append((path, along, str(kind[path[0]]), str(kind[path[-1]])))
    for edge in np.flatnonzero(~used):
        if not used[edge]:
            path, along = walk(int(u[edge]), int(edge))
            walks.append((path, along, RING, RING))
    rows: list[dict[str, Any]] = []
    decoded_lines: list[LineString] = []
    raw_lines: list[LineString] = []
    keeps: list[np.ndarray] = []
    values: list[np.ndarray] = []
    pieces: list[_Piece] = []
    categories: list[str] = []
    transitions: list[float] = []
    for path, along, start_kind, end_kind in walks:
        coords = medial.xy[path]
        # Error, allowance and width travel with the vertices through every cut below.
        carried = np.c_[middle.error[path], middle.allowance[path], middle.width[path]]
        category = pd.Series(kept.category[edges[along]]).mode().iloc[0]
        transition_by_edge = np.where(network.in_closed[edges[along]], 0.0, medial.length[edges[along]])
        for piece, piece_values in _split_centre(coords, carried, owners, start_kind, end_kind, dam_tree=dam_tree, extent=extent):
            pieces.append(piece)
            values.append(piece_values)
            categories.append(category)
            # The part outside closed-off water, by the share of the walk this piece keeps.
            share = LineString(piece.coords).length / max(float(medial.length[edges[along]].sum()), 1e-9)
            transitions.append(float(transition_by_edge.sum()) * min(share, 1.0))
    for piece, piece_values in zip(pieces, values, strict=True):
        row, line, keep = _validated_centre(
            piece, piece_values, water, dam_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page, joins=network.join_xy
        )
        rows.append(row)
        decoded_lines.append(line)
        raw_lines.append(LineString(piece.coords))
        keeps.append(keep)
    # A centre piece simplified apart may cross a contour or another centre piece; it gives back vertices, the contour does not.
    all_decoded, all_raw = [*contour_decoded, *decoded_lines], [*contour_raw, *raw_lines]
    offset = len(contour_decoded)
    for _ in range(MAX_REFINE_ROUNDS):
        crossings = _crossings(all_decoded, all_raw, only=np.arange(offset, len(all_decoded)))
        touched = set()
        for one, other, where in crossings:
            for index in (one, other):
                if index < offset:
                    continue
                i = index - offset
                keep = keeps[i]
                segment = int(np.argmin(shapely.distance(where, _edges(shapely.get_coordinates(decoded_lines[i])))))
                first, last = keep[segment], keep[segment + 1]
                if last - first < 2:
                    continue
                raw = pieces[i].coords
                farthest = first + 1 + int(np.argmax(_distance_to_segment(raw[first + 1 : last], raw[first], raw[last])))
                pieces[i].pinned = np.union1d(np.union1d(pieces[i].pinned, keep), [farthest])
                touched.add(i)
        if not touched:
            break
        for i in touched:
            rows[i], decoded_lines[i], keeps[i] = _validated_centre(
                pieces[i], values[i], water, dam_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page, joins=network.join_xy
            )
            all_decoded[offset + i] = decoded_lines[i]
    for _, _, where in _crossings(all_decoded, all_raw, only=np.arange(offset, len(all_decoded))):
        failures.append(
            {"body": body, "kind": "crossing", "detail": "a centre piece crosses another line where the raw lines do not", "geometry": where}
        )
    for _, _, where in _crossings(all_decoded, all_raw, contacts=True, only=np.arange(offset, len(all_decoded))):
        failures.append({"body": body, "kind": "contact", "detail": f"a centre piece passes within {CONTACT_M} m of another line", "geometry": where})
    for row, category, transition in zip(rows, categories, transitions, strict=True):
        row["body"] = body
        row["category"] = category
        row["transition_m"] = round(transition, 3)
        if not row["passes"]:
            failures.append({"body": body, "kind": row["failure"], "detail": row["failure_detail"], "geometry": row["worst"]})
        del row["worst"], row["failure"], row["failure_detail"]
    nodes = []
    for node in np.flatnonzero(breaks):
        nodes.append(
            {
                "body": body,
                "kind": str(kind[node]),
                "degree": int(degree[node]),
                "radius_m": float(middle.radius[node]),
                "middle_m": float(middle.error[node]),
                "geometry": Point(medial.xy[node]),
            }
        )
    return rows, nodes


def _split_centre(
    coords: np.ndarray,
    carried: np.ndarray,
    owners: _Owners,
    start: str,
    end: str,
    *,
    dam_tree: shapely.STRtree | None,
    extent: BaseGeometry | None,
) -> list[tuple[_Piece, np.ndarray]]:
    """Cut one walk of the network where its height owner changes, then at dam discs and the crop."""
    closed_walk = start == RING
    with_cuts = _with_interfaces(coords, owners)
    carried = _carry(coords, carried, with_cuts)
    owner = _owner_at((with_cuts[:-1] + with_cuts[1:]) / 2, owners)
    changes = np.flatnonzero(owner[1:] != owner[:-1]) + 1
    pieces: list[_Piece] = []
    if closed_walk and len(changes):
        # Start the loop at a change so that no piece wraps round its closing vertex.
        first = int(changes[0])
        order = np.r_[np.arange(first, len(with_cuts) - 1), np.arange(0, first + 1)]
        with_cuts, carried = with_cuts[order], carried[order]
        owner = _owner_at((with_cuts[:-1] + with_cuts[1:]) / 2, owners)
        changes = np.flatnonzero(owner[1:] != owner[:-1]) + 1
        start = end = INTERFACE
    bounds = [0, *changes.tolist(), len(with_cuts) - 1]
    for index, (one, other) in enumerate(zip(bounds[:-1], bounds[1:], strict=True)):
        piece_start = start if index == 0 else INTERFACE
        piece_end = end if index == len(bounds) - 2 else INTERFACE
        pieces.append(_Piece(with_cuts[one : other + 1], int(owner[one]), NARROW_ROLE, piece_start, piece_end))
    out = []
    for piece in _cut_artificial(pieces, dam_tree=dam_tree, extent=extent):
        out.append((piece, _carry(with_cuts, carried, piece.coords)))
    return out


def _carry(source: np.ndarray, values: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Values of a vertex run carried to another run of the same line.

    A vertex found exactly keeps its values; a new one takes the stricter of its segment's ends.
    """
    keys = source[:, 0] + 1j * source[:, 1]
    order = np.argsort(keys)
    wanted = target[:, 0] + 1j * target[:, 1]
    found = np.minimum(np.searchsorted(keys[order], wanted), len(keys) - 1)
    exact = keys[order][found] == wanted
    out = np.empty((len(target), values.shape[1]))
    out[exact] = values[order[found[exact]]]
    if (~exact).any():
        segments = _edges(source)
        (_, nearest), _ = shapely.STRtree(segments).query_nearest(shapely.points(target[~exact]), return_distance=True, all_matches=False)
        # Error is kept at its worst, allowance and width at their least.
        ends = np.stack([values[nearest], values[nearest + 1]])
        out[~exact] = np.c_[ends[:, :, 0].max(axis=0), ends[:, :, 1:].min(axis=0)]
    return out


def simplify_within(coords: np.ndarray, room: np.ndarray) -> np.ndarray:
    """Douglas–Peucker where each vertex may be dropped only by its own room; both ends are kept.

    Args:
        coords: ``(n, 2)`` vertices; a ring repeats its first vertex at the end
        room: ``(n,)`` largest distance each vertex may lie from the kept segment spanning it

    Returns:
        Sorted indices of the vertices kept
    """
    n = len(coords)
    keep = np.zeros(n, dtype=bool)
    keep[[0, n - 1]] = True
    if n > 3 and np.array_equal(coords[0], coords[-1]):
        far = int(np.argmax(np.hypot(*(coords - coords[0]).T)))
        keep[far] = True
    anchors = np.flatnonzero(keep)
    stack = list(zip(anchors[:-1].tolist(), anchors[1:].tolist(), strict=True))
    for _ in range(2 * n):
        if not stack:
            break
        one, other = stack.pop()
        if other - one < 2:
            continue
        excess = _distance_to_segment(coords[one + 1 : other], coords[one], coords[other]) - room[one + 1 : other]
        worst = int(np.argmax(excess))
        if excess[worst] > 0:
            middle = one + 1 + worst
            keep[middle] = True
            stack.extend(((one, middle), (middle, other)))
    else:
        raise RuntimeError("simplification did not finish within its bound")
    return np.flatnonzero(keep)


def _validated_centre(
    piece: _Piece,
    carried: np.ndarray,
    water: BaseGeometry,
    dam_tree: shapely.STRtree | None,
    *,
    tolerance_m: float,
    to_page: Transformer,
    from_page: Transformer,
    joins: np.ndarray | None = None,
) -> tuple[dict[str, Any], LineString, np.ndarray]:
    """Simplify a centre piece within the middle gate, write it on the page's grid and check it stays in the middle and in the water.

    A raw vertex's error is how far it lies from the true middle, measured
    exactly. The delivered line may move a vertex by what the gate leaves,
    ``min(1 m, 10 % of width)`` less that error, and at most the starting
    tolerance. After the round trip every raw vertex's distance from the
    delivered line plus its error, and every delivered segment's proved distance
    from the raw line, must stay within that; a failing segment gets the raw
    vertex that breaks it most back.

    Where the gate leaves a vertex less than one and a half times the grid's
    own move, ``GRID_MOVE_M``, beyond its error, the written line cannot be
    proved within it (about a metre and a quarter of water and less). There the
    gate is held on the line before encoding and what the grid adds is reported;
    the plan allows such sub-metre narrows up to 0.1 m of encoding excursion out
    of the water.
    """
    raw = piece.coords
    error, allowance, width = carried[:, 0], carried[:, 1], carried[:, 2]
    # Written, a vertex moves by up to the grid's move: the room it may be moved in before that is
    # what the gate leaves beyond its own error and the grid's. Where that is under half a grid
    # move the written line cannot be proved within the gate.
    narrow = allowance - error < 1.5 * GRID_MOVE_M
    room = np.clip(np.where(narrow, allowance - error, allowance - error - GRID_MOVE_M), 0.0, tolerance_m)
    plain = simplify_pinned(raw, tolerance_m)
    keep = simplify_within(raw, room)
    initial = len(keep)
    if len(piece.pinned):
        keep = np.union1d(keep, piece.pinned)
    raw_tree = shapely.STRtree(_edges(raw))
    points = shapely.points(raw)
    for _ in range(MAX_REFINE_ROUNDS):
        coords = decoded(raw[keep], to_page, from_page)
        coords = _off_dams(raw[keep], coords, dam_tree, to_page, from_page, joins)
        kept_vertex = np.isin(np.arange(len(raw)), keep)
        span = np.clip(np.searchsorted(keep, np.arange(len(raw)), side="right") - 1, 0, len(keep) - 2)
        segment_room = np.full(len(keep) - 1, np.inf)
        np.minimum.at(segment_room, span, allowance - error)
        # A raw vertex that closes a span belongs to both segments it ends.
        np.minimum.at(segment_room, np.clip(span - 1, 0, None)[kept_vertex], (allowance - error)[kept_vertex])
        segment_narrow = np.zeros(len(keep) - 1, dtype=bool)
        np.logical_or.at(segment_narrow, span, narrow)
        np.logical_or.at(segment_narrow, np.clip(span - 1, 0, None)[kept_vertex], narrow[kept_vertex])
        failing = np.zeros(len(keep) - 1, dtype=bool)
        measured = {}
        for name, line in (("decoded", coords), ("before", raw[keep])):
            judged = segment_narrow if name == "before" else ~segment_narrow
            (_, _), back = shapely.STRtree(_edges(line)).query_nearest(points, return_distance=True, all_matches=False)
            if not judged.any():
                measured[name] = back
                continue
            forward, _ = _deviation_bound(line, raw_tree, gate=np.where(judged, np.maximum(segment_room, 0.0), np.inf))
            # A span of one raw segment: distance to it is convex along the segment, so its ends bound it exactly.
            single = np.flatnonzero(np.diff(keep) == 1)
            if len(single):
                ends = np.stack(
                    [
                        _distance_pairs(line[single], raw[keep[single]], raw[keep[single] + 1]),
                        _distance_pairs(line[single + 1], raw[keep[single]], raw[keep[single] + 1]),
                    ]
                )
                forward[single] = ends.max(axis=0)
            worst_back = np.full(len(keep) - 1, -np.inf)
            np.maximum.at(worst_back, span, back + error - allowance)
            bad = (forward > segment_room + 1e-9) | (worst_back > 1e-9)
            failing |= bad & (segment_narrow if name == "before" else ~segment_narrow)
            measured[name] = back
        dam_failing = np.zeros(len(keep) - 1, dtype=bool)
        if dam_tree is not None:
            # The raw line is cut at the disc; a simplified chord past it must not cut into it.
            _, reach = dam_tree.query_nearest(_edges(coords), return_distance=True, all_matches=False)
            dam_failing = reach < DAM_CUT_M - 1e-9
            failing |= dam_failing
        if not failing.any():
            break
        added = []
        for k in np.flatnonzero(failing):
            one, other = keep[k], keep[k + 1]
            if other - one < 2:
                continue
            added.append(one + 1 + int(np.argmax(_distance_to_segment(raw[one + 1 : other], raw[one], raw[other]) - room[one + 1 : other])))
        if not added:
            break
        keep = np.union1d(keep, added)
    delivered = measured["decoded"] + error
    held = np.where(narrow, measured["before"] + error, delivered)
    share = delivered / np.maximum(width, 1e-9)
    worst = int(np.argmax(held - allowance))
    simplified_segments = _edges(raw[keep])
    decoded_segments = _edges(coords)
    dry = _dry(simplified_segments, water)
    decoded_dry = _dry(decoded_segments, water)
    dam_clearance = float("inf")
    if dam_tree is not None:
        _, gaps = dam_tree.query_nearest(decoded_segments, return_distance=True, all_matches=False)
        dam_clearance = float(gaps.min()) if len(gaps) else dam_clearance
    middle_ok = not (failing & ~dam_failing).any()
    # Dry after encoding only by the grid's move, and only in a sub-metre narrow or at a branch end on the bank.
    excused = decoded_dry[1] <= 0.1 and (narrow.any() or END in (piece.start, piece.end))
    wet = dry[0] <= DRY_NOISE_M and (decoded_dry[0] <= DRY_NOISE_M or excused)
    clear = dam_clearance >= DAM_CUT_M - 1e-9
    failure, detail = "", ""
    if not middle_ok:
        failure, detail = "middle", f"{held[worst]:.3f} m from the middle of {width[worst]:.2f} m of water, allowed {allowance[worst]:.3f} m"
    elif not wet:
        failure, detail = "dry", f"{dry[0]:.3e} m dry before encoding, {decoded_dry[0]:.3e} m after, {decoded_dry[1]:.3e} m out"
    elif not clear:
        failure, detail = "dam", f"{dam_clearance:.3f} m from a dam"
    row = {
        "owner": piece.owner,
        "role": NARROW_ROLE,
        "source": NARROW_WATER,
        "start": piece.start,
        "end": piece.end,
        "raw_vertices": len(raw),
        "plain_vertices": len(plain),
        "vertices": len(keep),
        "refined": len(keep) - initial,
        "raw_middle_max_m": float(error.max()),
        "middle_max_m": float(held.max()),
        "middle_share_max": float((held / np.maximum(width, 1e-9)).max()),
        "decoded_middle_share_max": float(share.max()),
        "sub_metre": int(narrow.sum()),
        "sub_metre_grid_excess_m": float(np.maximum(delivered - allowance, 0.0)[narrow].max()) if narrow.any() else 0.0,
        "dry_m": dry[0],
        "decoded_dry_m": decoded_dry[0],
        "decoded_excursion_m": decoded_dry[1],
        "dam_clearance_m": dam_clearance,
        "passes": middle_ok and wet and clear,
        "failure": failure,
        "failure_detail": detail,
        "worst": Point(raw[worst]),
        "raw": LineString(raw),
        "geometry": LineString(coords),
    }
    return row, LineString(coords), keep


def _dry(segments: np.ndarray, water: BaseGeometry) -> tuple[float, float]:
    """The length of the segments outside the water, and the farthest any of it lies from the water."""
    wet = shapely.covers(water, segments)
    if wet.all():
        return 0.0, 0.0
    length, far = 0.0, 0.0
    for segment in segments[~wet]:
        # A whole sea is slow to subtract from; the water round the segment is all that matters.
        x0, y0, x1, y1 = shapely.bounds(segment)
        local = shapely.clip_by_rect(water, x0 - 1, y0 - 1, x1 + 1, y1 + 1)
        outside = shapely.difference(segment, local)
        length += float(outside.length)
        coordinates = shapely.get_coordinates(outside)
        if len(coordinates):
            far = max(far, float(shapely.distance(shapely.points(coordinates), local).max()))
    return length, far


def _off_dams(
    raw: np.ndarray, coords: np.ndarray, dam_tree: shapely.STRtree | None, to_page: Transformer, from_page: Transformer, joins: np.ndarray | None
) -> np.ndarray:
    """Move a written vertex the grid pulled into a dam disc to the nearest grid point outside it.

    The raw line lies outside every disc; a vertex within the grid's move of a
    disc's edge can be written inside it (0.024 m at Holmtjärnen, where an
    anchor's node lies on the edge). The move depends on the raw vertex alone,
    so every piece that shares a node writes it the same. A join keeps its
    place: the contour shares it and writes it unmoved.
    """
    if dam_tree is None or not len(coords):
        return coords
    from trails.visualization.encoding import DEFAULT_COORDINATE_QUANTUM

    _, reach = dam_tree.query_nearest(shapely.points(coords), return_distance=True, all_matches=False)
    inside = np.flatnonzero(reach < DAM_CUT_M)
    if joins is not None and len(joins) and len(inside):
        inside = inside[~np.isin(raw[inside, 0] + 1j * raw[inside, 1], joins[:, 0] + 1j * joins[:, 1])]
    if not len(inside):
        return coords
    out = coords.copy()
    steps = np.array([(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j])
    for index in inside:
        lon, lat = to_page.transform(raw[index][0], raw[index][1])
        grid = (np.rint(np.array([lon, lat]) / DEFAULT_COORDINATE_QUANTUM) + steps) * DEFAULT_COORDINATE_QUANTUM
        x, y = from_page.transform(grid[:, 0], grid[:, 1])
        candidates = np.c_[x, y]
        _, clear = dam_tree.query_nearest(shapely.points(candidates), return_distance=True, all_matches=False)
        ok = np.flatnonzero(clear >= DAM_CUT_M)
        if len(ok):
            out[index] = candidates[ok[np.argmin(np.hypot(*(candidates[ok] - raw[index]).T))]]
    return out

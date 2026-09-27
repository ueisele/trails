"""The line off the bank: validated offset contours of the eligible water, and the middle where they cannot go.

Uwe's decision of 2026-09-25 moves the bank-following kayak line 15 m out into
the water. This module draws that line and proves it;
:mod:`trails.network.paddle_network` wires it into a build behind the
``paddle_offset`` setting. It offsets each connected eligible body whole, before any map cut, so a
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

Every place where land meets the water today keeps its point on the bank, and
a short paddled spur of Landing water runs from it to the line (phase 12d):
straight where that lies in the body's own water clear of every dam disc, bent
round the bank where it does not, to the centre node phase 12c gave an anchor
in closed-off water. Class-2 streams are joined where they actually meet the
water, and each exact lake/river interface is kept once and joined to the line
on both sides. Nothing here changes a carry or a launch: they are measured to
the bank, which stays where it is.
"""

import math
import time
from collections import OrderedDict
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
    LANDING_WATER,
    NARROW_WATER,
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
#: Implementation choice (phase 12c-2): predicates on short lines at the bank read the water of a
#: cell of this side, plus this margin, cut from blocks of this many cells a side; see ``_Local``.
LOCAL_CELL_M = 1000.0
LOCAL_MARGIN_M = 100.0
LOCAL_BLOCK_CELLS = 8
#: Below this many vertices a polygon is asked whole: cutting it into cells would cost more than it saves.
LOCAL_MIN_VERTICES = 20_000
#: The most prepared cells kept at once; a cell is cut again from its block when it is needed after that.
LOCAL_CELLS_KEPT = 64
#: The most medial layouts a body keeps between passes. A sea's keep region is 834,000 vertices, prepared;
#: a layout met again is rebuilt from the kept buffers and regions, which is the cheap part of it.
LAYOUTS_KEPT = 1
#: Seeds with fewer vertices are tested unprepared: a sea has 39,000 of them, mostly small discs.
PREPARED_SEED_VERTICES = 256

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
            ``join``, ``isolated``, ``window``, ``cap not kept``, ``invalid water``,
            ``seam`` (two tiles disagree about the middle beside a kept line).
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
        regions: The unsimplified offset of each body with any, cut to the extent: the water
            at least d from its bank, which the contour encloses and open-water chords cross
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
    regions: gpd.GeoDataFrame | None = None
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
    regions: list[dict[str, Any]] = field(default_factory=list)


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
    prove_deviation: bool = True,
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
        prove_deviation: Take the contour's deviation bound from Douglas–Peucker and the
            grid's move wherever the simplifier alone chose a segment, and sample only the
            rest; False samples every segment, as the evidence that the proof holds

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
            prove_deviation=prove_deviation,
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
        regions=frame(rows.regions, ["body", "geometry"]),
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
    prove_deviation: bool = True,
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
    if parts:
        region = shapely.multipolygons(parts)
        rows.regions.append({"body": body, "geometry": shapely.intersection(region, extent) if extent is not None else region})
    bank = _segments(water)
    bank_tree = shapely.STRtree(bank.lines)
    owners = _owners(polygons, owner)
    shapely.prepare(water)
    local = _local(water)
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
        body,
        water,
        bank,
        bank_tree,
        seeds,
        specks,
        closed,
        anchors,
        rings,
        offset_m=offset_m,
        step=sample_m,
        tile_m=tile_m,
        local=local,
        failures=failures,
    )
    summary.update(network.summary)
    rows.anchors.extend(network.anchor_rows)
    rows.pruned.extend(network.pruned_rows)
    kept_pieces = [closed.pieces[i] for i in np.flatnonzero(network.kept_closed)]
    first_cap = len(rows.caps)
    if kept_pieces and parts:
        opened_tree = shapely.STRtree(closed.opened_parts)
        opened_cells: dict[int, _Local] = {}
        for i in np.flatnonzero(network.kept_closed):
            anchored = bool(len(closed.anchors[i]))
            rows.caps.append(
                {
                    "body": body,
                    "kind": _kind(closed.pieces[i], closed.opened_parts, opened_tree, opened_cells),
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
        # One index of the kept closed-off water's outline serves every ring of the body.
        kept_edges = _edge_tree(kept_pieces) if kept_pieces else None
        for coords in _with_joins(rings, network.join_xy, network.join_ring, network.join_segment):
            pieces.extend(_cut(coords, owners, kept_edges, offset_m=offset_m))
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
        validated = [
            _validated(piece, bank, bank_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page, prove=prove_deviation)
            for piece in pieces
        ]
        raw_lines = [LineString(piece.coords) for piece in pieces]
        # Crossings and contacts come from one pass; it is repeated only after a piece changed.
        crossings, contacts = _crossings([line for _, line in validated], raw_lines)
        for _ in range(MAX_REFINE_ROUNDS):
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
                validated[index] = _validated(
                    pieces[index], bank, bank_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page, prove=prove_deviation
                )
            crossings, contacts = _crossings([line for _, line in validated], raw_lines)
        for _, _, where in crossings:
            failures.append({"body": body, "kind": "crossing", "detail": "simplified pieces cross where the raw contour does not", "geometry": where})
        for _, _, where in contacts:
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
                held = _held_outside(piece.coords, bank, bank_tree, source_window, extent, offset_m=offset_m)
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
        local,
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
    # The delivery polygons were prepared for this body only.
    shapely.destroy_prepared(polygons)
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
class _Local:
    """A body's water cut into square cells with a margin, for predicates on short lines at its bank.

    GEOS answers ``covers`` for a line that touches a polygon's outline by relating the whole
    polygon: 2.6 ms a line against a 200,000-vertex ring, measured, against 2 µs for a line
    inside it, and every corner branch ends on the bank. A line within a cell's margin lies in
    the water exactly when it lies in the water of the cell, whose outline near the line is the
    body's own, vertex for vertex; so the cell gives the same answer at the cost of its own size.
    Cells are cut from blocks of cells, so no cut reads the whole body more than once a block.
    """

    water: BaseGeometry
    origin: np.ndarray
    #: Whether the body's outer rings run clockwise, as GEOS writes them; its holes run the other way.
    exterior_cw: bool
    #: The prepared cells used last, at most ``LOCAL_CELLS_KEPT``; a sea has more than memory should hold at once.
    cells: OrderedDict[tuple[int, int], BaseGeometry] = field(default_factory=OrderedDict)
    blocks: dict[tuple[int, int], BaseGeometry] = field(default_factory=dict)

    def _clipped(self, source: BaseGeometry, left: float, bottom: float, side: float, reach: float) -> BaseGeometry:
        cut = shapely.intersection(source, shapely.box(left - reach, bottom - reach, left + side + reach, bottom + side + reach))
        # A cut can leave lines or points where the box grazes the bank; they lie on the box, far from any line asked about.
        polygons = [g for g in shapely.get_parts(cut) if isinstance(g, Polygon) and not g.is_empty]
        if not polygons:
            return Polygon()
        # Each edge runs the way it runs in the body: GEOS measures a distance from a segment's first
        # vertex, so the same edge reversed gives a figure a bit apart.
        return shapely.orient_polygons(shapely.multipolygons(polygons), exterior_cw=self.exterior_cw)

    def cell(self, key: tuple[int, int]) -> BaseGeometry:
        found = self.cells.get(key)
        if found is not None:
            self.cells.move_to_end(key)
        else:
            block_key = (key[0] // LOCAL_BLOCK_CELLS, key[1] // LOCAL_BLOCK_CELLS)
            block = self.blocks.get(block_key)
            if block is None:
                side = LOCAL_CELL_M * LOCAL_BLOCK_CELLS
                corner = self.origin + np.asarray(block_key) * side
                block = self._clipped(self.water, float(corner[0]), float(corner[1]), side, LOCAL_MARGIN_M + 2.0)
                self.blocks[block_key] = block
            corner = self.origin + np.asarray(key) * LOCAL_CELL_M
            found = self._clipped(block, float(corner[0]), float(corner[1]), LOCAL_CELL_M, LOCAL_MARGIN_M + 1.0)
            shapely.prepare(found)
            self.cells[key] = found
            if len(self.cells) > LOCAL_CELLS_KEPT:
                self.cells.popitem(last=False)
        return found

    def _placed(self, lines: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Each line's cell, and whether it lies within that cell's margin."""
        bounds = shapely.bounds(lines).reshape(-1, 4)
        key = np.floor((bounds[:, :2] - self.origin) / LOCAL_CELL_M).astype(np.int64)
        limit = self.origin + (key + 1) * LOCAL_CELL_M + LOCAL_MARGIN_M
        return key, (bounds[:, 2] <= limit[:, 0]) & (bounds[:, 3] <= limit[:, 1])

    def near(self, geometry: BaseGeometry) -> BaseGeometry:
        """The water round one geometry: its cell's, or the whole body's where it leaves the cell's margin."""
        key, fits = self._placed(np.asarray([geometry], dtype=object))
        return self.cell((int(key[0, 0]), int(key[0, 1]))) if fits[0] else self.water

    def distance(self, points: np.ndarray) -> np.ndarray:
        """``shapely.distance(points, water)``, each read in its cell where the answer lies within the cell's margin.

        A cell holds the water within its margin exactly, so a distance under the margin found
        there is the distance to the whole water; a larger one is asked of the whole.
        """
        points = np.asarray(points, dtype=object)
        out = np.full(len(points), np.nan)
        if not len(points):
            return out
        key, fits = self._placed(points)
        members = np.flatnonzero(fits)
        cells, which = np.unique(key[members], axis=0, return_inverse=True)
        for k, cell in enumerate(cells):
            chosen = members[which.ravel() == k]
            out[chosen] = shapely.distance(points[chosen], self.cell((int(cell[0]), int(cell[1]))))
        rest = ~(out < LOCAL_MARGIN_M)
        if rest.any():
            out[rest] = shapely.distance(points[rest], self.water)
        return out

    def covers(self, lines: np.ndarray) -> np.ndarray:
        """``shapely.covers(water, lines)``, each asked of its cell's water."""
        lines = np.asarray(lines, dtype=object)
        out = np.zeros(len(lines), dtype=bool)
        if not len(lines):
            return out
        key, fits = self._placed(lines)
        if (~fits).any():
            out[~fits] = shapely.covers(self.water, lines[~fits])
        members = np.flatnonzero(fits)
        cells, which = np.unique(key[members], axis=0, return_inverse=True)
        for k, cell in enumerate(cells):
            chosen = members[which.ravel() == k]
            out[chosen] = shapely.covers(self.cell((int(cell[0]), int(cell[1]))), lines[chosen])
        return out


def _local(water: BaseGeometry) -> _Local:
    first = shapely.get_parts(water)[0]
    return _Local(water, np.floor(np.asarray(shapely.bounds(water)[:2]) / LOCAL_CELL_M) * LOCAL_CELL_M, not bool(shapely.is_ccw(first.exterior)))


@dataclass
class _Owners:
    polygons: np.ndarray
    owner: np.ndarray
    tree: shapely.STRtree


def _owners(polygons: np.ndarray, owner: np.ndarray) -> _Owners:
    # Prepared, a point is located in a large delivery polygon through its index rather than by walking every edge.
    shapely.prepare(polygons)
    return _Owners(polygons, owner, shapely.STRtree(polygons))


def _owner_at(points: np.ndarray, owners: _Owners) -> np.ndarray:
    """The height owner of each point; where two delivery polygons overlap the lake, listed first, wins."""
    found = np.full(len(points), -1, dtype=int)
    # The tree's own predicate tests a point against an unprepared polygon edge by edge; the same test
    # against the prepared polygon gives the same answer through its index.
    point_index, polygon_index = owners.tree.query(shapely.points(points))
    inside = shapely.intersects_xy(owners.polygons[polygon_index], points[point_index, 0], points[point_index, 1])
    point_index, polygon_index = point_index[inside], polygon_index[inside]
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
    opened_cells = _local(opened) if shapely.get_num_coordinates(opened) >= LOCAL_MIN_VERTICES else None
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
                to_opened = opened_cells.distance(points) if opened_cells is not None else shapely.distance(points, opened)
                own = near[shapely.distance(points, piece) < to_opened]
        held.append(own)
    return _Closed(residue, reach, held, opened_parts)


def _kind(piece: BaseGeometry, opened_parts: list[BaseGeometry], tree: shapely.STRtree, cells: dict[int, _Local]) -> str:
    """Passage between two parts of the offset, loop meeting one part twice, or terminal.

    A large part is asked through the cell round the piece (``cells`` keeps them by part): distance
    and a rectangle clip there read a sea's reachable water in cells, not a million vertices a piece.
    """

    def around(index: int) -> BaseGeometry:
        part = opened_parts[index]
        if shapely.get_num_coordinates(part) < LOCAL_MIN_VERTICES:
            return part
        if index not in cells:
            cells[index] = _local(part)
        return cells[index].near(piece)

    # The tree's own dwithin: the parts whose envelopes come that near, in the tree's order, then the distance.
    x0, y0, x1, y1 = shapely.bounds(piece)
    candidates = tree.query(shapely.box(x0 - 0.05, y0 - 0.05, x1 + 0.05, y1 + 0.05))
    near = [int(i) for i in candidates if shapely.dwithin(piece, around(int(i)), 0.05)]
    if len(near) >= 2:
        return "passage"
    contact = None
    if len(near):
        # Grow only the reachable water around this piece: growing a whole sea costs minutes per piece,
        # and even overlaying it with a box is slow; a rectangle clip gives the same water near the piece.
        local = shapely.clip_by_rect(around(near[0]), x0 - 1.0, y0 - 1.0, x1 + 1.0, y1 + 1.0)
        contact = shapely.line_merge(shapely.intersection(piece.boundary, shapely.buffer(local, 0.05)))
    arcs = [a for a in shapely.get_parts(contact) if a.length > 0.1] if contact is not None else []
    return "loop" if len(arcs) >= 2 else "terminal"


def _edge_tree(polygons: Sequence[BaseGeometry]) -> shapely.STRtree:
    """Every edge of the polygons' outlines, for distances from points outside them."""
    rings = shapely.get_parts(shapely.boundary(np.asarray(polygons, dtype=object)))
    return shapely.STRtree(np.concatenate([_edges(shapely.get_coordinates(r)) for r in rings]))


def _cut(coords: np.ndarray, owners: _Owners, residue: shapely.STRtree | None, *, offset_m: float) -> list[_Piece]:
    """Cut one closed raw ring where its height owner or its role changes.

    Owner changes fall inside segments and get an exact interface vertex; role
    changes fall on raw vertices, which are dense on the arcs a cap is made of.
    ``residue`` indexes the edges of the kept closed-off water's outlines.
    """
    coords = _with_interfaces(coords, owners)
    points = shapely.points(coords)
    if residue is not None:
        # Whether any outline edge lies that near, as the nearest distance compared with it would say.
        held = np.zeros(len(coords), dtype=bool)
        held[residue.query(points, predicate="dwithin", distance=offset_m + CAP_TOLERANCE_M)[0]] = True
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


def _segment_distance(points: np.ndarray, one: np.ndarray, other: np.ndarray) -> np.ndarray:
    """Each point's distance from its own segment, GEOS's ``pointToSegment`` written out operation for operation.

    ``STRtree.query_nearest`` computes exactly this for a point and a
    two-vertex line: the two agreed bit for bit on 200,000 test points, on
    vertices, on segments and beside repeated vertices (phase 12c-2).
    """
    abx, aby = other[:, 0] - one[:, 0], other[:, 1] - one[:, 1]
    apx, apy = points[:, 0] - one[:, 0], points[:, 1] - one[:, 1]
    bpx, bpy = points[:, 0] - other[:, 0], points[:, 1] - other[:, 1]
    squared = abx * abx + aby * aby
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (apx * abx + apy * aby) / squared
        s = ((one[:, 1] - points[:, 1]) * abx - (one[:, 0] - points[:, 0]) * aby) / squared
    to_one = np.sqrt(apx * apx + apy * apy)
    to_other = np.sqrt(bpx * bpx + bpy * bpy)
    same = (one[:, 0] == other[:, 0]) & (one[:, 1] == other[:, 1])
    return np.asarray(np.where(same | (r <= 0.0), to_one, np.where(r >= 1.0, to_other, np.abs(s) * np.sqrt(squared))))


@dataclass
class _SegmentIndex:
    """Segments by their envelopes, for the distance of many points from all of them at once."""

    one: np.ndarray
    other: np.ndarray
    tree: shapely.STRtree

    @classmethod
    def of(cls, coords: np.ndarray) -> _SegmentIndex:
        """The segments of a vertex run."""
        return cls.between(coords[:-1], coords[1:])

    @classmethod
    def between(cls, one: np.ndarray, other: np.ndarray) -> _SegmentIndex:
        low, high = np.minimum(one, other), np.maximum(one, other)
        return cls(one, other, shapely.STRtree(shapely.box(low[:, 0], low[:, 1], high[:, 0], high[:, 1])))

    def distance(self, points: np.ndarray, hint: np.ndarray) -> np.ndarray:
        """Each point's distance from the nearest segment, as an STRtree of them as lines returns it with ``query_nearest``.

        ``hint`` names a segment near each point. Its distance bounds the answer,
        so only segments whose envelopes come within it can be nearer; the least
        over them is the tree's answer, found without its per-candidate calls.
        """
        bound = _segment_distance(points, self.one[hint], self.other[hint])
        which, segment = self.tree.query(shapely.box(points[:, 0] - bound, points[:, 1] - bound, points[:, 0] + bound, points[:, 1] + bound))
        out = bound.copy()
        np.minimum.at(out, which, _segment_distance(points[which], self.one[segment], self.other[segment]))
        return out


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
    prove: bool = True,
) -> tuple[dict[str, Any], LineString]:
    """Simplify one piece, then give back raw vertices until its decoded form passes both gates.

    The deviation gate is proved rather than sampled on every segment Douglas–Peucker chose
    alone (``prove``): each raw vertex it dropped lies within the tolerance of the kept
    segment spanning it, so every raw point between the segment's ends does (distance to a
    segment is convex), and every point p of the segment lies within the tolerance of the raw
    run too: the run joins the segment's two ends, so it crosses the perpendicular through p,
    and it crosses it at most the tolerance from the segment, which on that perpendicular is
    the distance from p. The page's grid moves each end by a measured amount and a segment
    by no more than the larger. The bound is that largest dropped distance, at most the tolerance,
    plus the move. Segments a pinned or given-back vertex split are sampled.
    """
    raw = piece.coords
    raw_line = LineString(raw)
    raw_segments = _edges(raw)
    raw_index = _SegmentIndex.of(raw)
    (_, _), raw_gaps = bank_tree.query_nearest(raw_segments, return_distance=True, all_matches=False)
    keep = simplify_pinned(raw, tolerance_m)
    initial = len(keep)
    simplified = keep
    if len(piece.pinned):
        keep = np.union1d(keep, piece.pinned)
    for _ in range(MAX_REFINE_ROUNDS):
        coords = decoded(raw[keep], to_page, from_page)
        segments = _edges(coords)
        (_, _), clearance = bank_tree.query_nearest(segments, return_distance=True, all_matches=False)
        # A decoded segment follows the raw segments between its two kept vertices; a raw segment's
        # bound belongs to the simplified segment spanning it.
        span = np.searchsorted(keep, np.arange(len(raw) - 1), side="right") - 1
        proven = _simplifier_segments(keep, simplified) if prove else np.zeros(len(keep) - 1, dtype=bool)
        gate = np.where(proven, np.inf, CONTOUR_DEVIATION_M)
        forward, forward_at = _deviation_bound(coords, raw_index, keep[:-1], keep[1:] - 1, gate)
        backward, backward_at = _deviation_bound(raw, _SegmentIndex.of(coords), span, span, gate[span])
        moved = np.hypot(*(coords - raw[keep]).T)
        forward[proven] = (_dropped(raw, keep) + np.maximum(moved[:-1], moved[1:]))[proven]
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


def _dropped(raw: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Per kept segment, the largest distance of a raw vertex it dropped from it; 0 where it dropped none."""
    inner = np.setdiff1d(np.arange(len(raw)), keep)
    out = np.zeros(len(keep) - 1)
    if len(inner):
        segment = np.searchsorted(keep, inner, side="right") - 1
        np.maximum.at(out, segment, _distance_pairs(raw[inner], raw[keep[segment]], raw[keep[segment + 1]]))
    return out


def _simplifier_segments(keep: np.ndarray, simplified: np.ndarray) -> np.ndarray:
    """Which segments of ``keep`` join two vertices consecutive in the simplifier's own choice ``simplified``."""
    position = np.searchsorted(simplified, keep)
    found = (position < len(simplified)) & (simplified[np.minimum(position, len(simplified) - 1)] == keep)
    return np.asarray(found[:-1] & found[1:] & (position[1:] == position[:-1] + 1), dtype=bool)


def _deviation_bound(
    coords: np.ndarray, target: _SegmentIndex, first: np.ndarray, last: np.ndarray, gate: np.ndarray | float = CONTOUR_DEVIATION_M
) -> tuple[np.ndarray, np.ndarray]:
    """Per segment of ``coords``: a proven upper bound on its distance from the target line, and the largest sample.

    Samples every ``COARSE_SAMPLE_M``; a gap whose bound, the mean of its ends
    plus half its length, exceeds the gate (one figure, or one per segment) is
    sampled again every ``FINE_SAMPLE_M``. Segment k of ``coords`` runs beside
    the target's segments ``first[k]`` to ``last[k]``; they only point the
    search, the distance is to the whole target.
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
        # np.linspace(0, 1, c + 1) segment by segment, at once: k times 1/c, the last exactly 1, bit for bit.
        k = np.arange(int((counts + 1).sum())) - np.repeat(np.cumsum(counts + 1) - (counts + 1), counts + 1)
        t = k * np.repeat(1.0 / counts, counts + 1)
        t[np.cumsum(counts + 1) - 1] = 1.0
        points = coords[owner] + t[:, None] * (coords[owner + 1] - coords[owner])
        hint = np.clip(first[owner] + np.rint(t * (last[owner] - first[owner])).astype(np.int64), 0, len(target.one) - 1)
        distance = target.distance(points, hint)
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


def _held_outside(
    coords: np.ndarray, bank: _Bank, tree: shapely.STRtree, window: BaseGeometry, extent: BaseGeometry | None, *, offset_m: float
) -> Point | None:
    """The first raw vertex inside the extent whose nearest bank lies outside the source window, if any.

    A raw contour vertex lies the offset from its nearest bank point (the buffer's own
    vertices, and points on its chords a centimetre nearer). One deeper than that inside
    the window has that point inside it too, so only the vertices near the window's edge
    or beyond it are looked up.
    """
    points = np.asarray(shapely.points(coords), dtype=object)
    deep = shapely.contains_xy(window, coords[:, 0], coords[:, 1]) & (shapely.distance(points, shapely.boundary(window)) > offset_m + 1.0)
    candidates = np.flatnonzero(~deep)
    if not len(candidates):
        return None
    _, _, nearest = _generators(coords[candidates], bank, tree)
    outside = ~shapely.intersects(window, nearest)
    if extent is not None:
        outside &= shapely.intersects(extent, points[candidates])
    hits = candidates[outside]
    return Point(coords[hits[0]]) if len(hits) else None


def _crossings(
    decoded_lines: list[LineString], raw_lines: list[LineString], *, only: np.ndarray | None = None
) -> tuple[list[tuple[int, int, Point]], list[tuple[int, int, Point]]]:
    """Where two simplified pieces meet other than at a shared end or where their raw pieces meet too.

    Raw pieces that pass within ``CONTACT_M`` of each other without meeting may
    cross once written on the page's grid, and no vertex can undo that. Those
    are contacts, returned apart: crossings first, then contacts. With
    ``only``, just the pairs that involve one of those pieces are looked at.
    """
    if len(decoded_lines) < 2:
        return [], []
    tree = shapely.STRtree(decoded_lines)
    queries = np.arange(len(decoded_lines)) if only is None else np.asarray(only, dtype=int)
    if not len(queries):
        return [], []
    lines = np.asarray(decoded_lines, dtype=object)
    left, right = tree.query(lines[queries], predicate="intersects")
    left = queries[left]
    # Pieces that meet only at their ends, as the centre lines do at every join and junction, cannot
    # cross: dropping them first is the end test below done at once, and it keeps the loop short.
    apart = (left != right) & ~shapely.touches(lines[left], lines[right])
    pairs = sorted({(min(a, b), max(a, b)) for a, b in zip(left[apart].tolist(), right[apart].tolist(), strict=True)})
    found: tuple[list[tuple[int, int, Point]], list[tuple[int, int, Point]]] = ([], [])
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
            found[1 if touching else 0].append((one, other, shapely.centroid(point)))
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
    #: The middles of the witness edges a tile's neighbour computed otherwise than the tile that owns them.
    seams: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))


@dataclass
class _Layout:
    """Where the medial construction looks for a given set of seeds and a coarsest step.

    Attributes:
        seed_tree: The seeds, prepared
        keep_region: Within 2d of a seed: an edge whose middle lies here is kept
        tiles: Per tile that meets the keep region and has a seed near: its
            column, row, the region its samples are taken from, the sorted bank
            segments that region reads and the seeds near it, by identity
    """

    seed_tree: shapely.STRtree
    keep_region: BaseGeometry
    tiles: list[tuple[int, int, BaseGeometry, np.ndarray, frozenset[int]]]


@dataclass
class _TileCache:
    """What one body's medial construction keeps between its halving rounds and window growths.

    ``tiles`` holds each tile's edges with the segments, steps and nearby
    seeds they came from. A halving round reuses a tile whose own segments and
    steps did not change. A growth adds seeds and recomputes every tile; a tile
    no added seed comes near, with the same segments and steps, would come out
    the same, so it is kept instead (see ``_medial_tiles``). ``layouts``,
    ``grown``, ``buffers`` and ``regions`` keep what a layout is made of, so a
    growth met again in a later round, or a tile whose seeds did not change,
    is not built again.
    """

    tiles: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, frozenset[int], dict[str, Any]]] = field(default_factory=dict)
    layouts: list[tuple[list[BaseGeometry], float, _Layout]] = field(default_factory=list)
    grown: dict[bytes, BaseGeometry] = field(default_factory=dict)
    buffers: dict[tuple[int, float], tuple[BaseGeometry, BaseGeometry]] = field(default_factory=dict)
    regions: dict[tuple[int, int, float], tuple[frozenset[int], BaseGeometry, np.ndarray]] = field(default_factory=dict)

    def layout(self, seeds: list[BaseGeometry], step: float) -> _Layout | None:
        for index, (known, known_step, layout) in enumerate(self.layouts):
            if known_step == step and len(known) == len(seeds) and all(a is b for a, b in zip(known, seeds, strict=True)):
                self.layouts.append(self.layouts.pop(index))
                return layout
        return None

    def keep(self, seeds: list[BaseGeometry], step: float, layout: _Layout) -> None:
        """Keep a layout, and only the few used last: each holds its keep region prepared, a sea's in hundreds of megabytes."""
        self.layouts.append((list(seeds), step, layout))
        while len(self.layouts) > LAYOUTS_KEPT:
            shapely.destroy_prepared(self.layouts.pop(0)[2].keep_region)

    def grow(self, points: np.ndarray, offset_m: float) -> list[BaseGeometry]:
        """The disc round each point, the same object whenever the same point is grown again."""
        out = []
        for point in np.asarray(points, dtype=np.float64):
            key = point.tobytes()
            if key not in self.grown:
                self.grown[key] = shapely.buffer(shapely.Point(point), offset_m)
            out.append(self.grown[key])
        return out


def _layout(
    bank_tree: shapely.STRtree, seeds: list[BaseGeometry], origin: np.ndarray, *, offset_m: float, step: float, tile_m: float, cache: _TileCache
) -> _Layout:
    """The tiles the seeds call for, each with the region its samples come from and the bank segments that region reads.

    A seed's two buffers, and a tile's region when the seeds near it are the
    same ones, are taken from ``cache``: they are the same computation.
    """
    d = offset_m
    seed_array = np.asarray(seeds, dtype=object)
    # Prepared, a node is placed in a large closed-off piece through its index (see ``_graph``).
    shapely.prepare(seed_array[shapely.get_num_coordinates(seed_array) >= PREPARED_SEED_VERTICES])
    seed_tree = shapely.STRtree(seed_array)
    missing = [i for i, seed in enumerate(seeds) if (id(seed), step) not in cache.buffers]
    if missing:
        fresh = seed_array[missing]
        for i, keep, reach in zip(missing, shapely.buffer(fresh, 2 * d), shapely.buffer(fresh, 3 * d + 3 * step + 1.0), strict=True):
            cache.buffers[(id(seeds[i]), step)] = (keep, reach)
    buffers = [cache.buffers[(id(seed), step)] for seed in seeds]
    keep_region = shapely.union_all(np.asarray([keep for keep, _ in buffers], dtype=object))
    seed_reach = np.asarray([reach for _, reach in buffers], dtype=object)
    shapely.prepare(keep_region)
    sample_reach = 3 * d + 3 * step + 1.0
    tile_margin = 2 * d + TILE_BAND_M + 3 * step + 2.0
    if keep_region.is_empty:
        # A body the offset carries everywhere, a round lake without corners, calls for no middle.
        return _Layout(seed_tree, keep_region, [])
    x0, y0, x1, y1 = shapely.bounds(keep_region)
    columns = range(int(np.floor((x0 - origin[0]) / tile_m)), int(np.floor((x1 - origin[0]) / tile_m)) + 1)
    rows_range = range(int(np.floor((y0 - origin[1]) / tile_m)), int(np.floor((y1 - origin[1]) / tile_m)) + 1)
    tiles: list[tuple[int, int, BaseGeometry, np.ndarray, frozenset[int]]] = []
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
            near_ids = frozenset(id(seeds[i]) for i in near)
            known = cache.regions.get((column, row, step))
            if known is not None and known[0] == near_ids:
                region, segments = known[1], known[2]
            else:
                # A rectangle clip first: a river's buffered seed runs for kilometres past the tile.
                region = shapely.intersection(window, shapely.union_all(shapely.clip_by_rect(seed_reach[near], *shapely.bounds(window))))
                # Kept unprepared: a sea's tiles would hold every region's index between rounds.
                segments = np.sort(bank_tree.query(region))
                cache.regions[(column, row, step)] = (near_ids, region, segments)
            tiles.append((column, row, region, segments, near_ids))
    return _Layout(seed_tree, keep_region, tiles)


def _medial(
    water: BaseGeometry,
    bank: _Bank,
    bank_tree: shapely.STRtree,
    seeds: list[BaseGeometry],
    *,
    offset_m: float,
    steps: np.ndarray,
    tile_m: float,
    cache: _TileCache,
    local: _Local,
    feet: tuple[np.ndarray, np.ndarray] = (np.empty(0, dtype=int), np.empty((0, 2))),
) -> _Medial:
    """The medial graph of every component that meets a seed, grown until no kept branch leaves its window.

    ``cache`` keeps each tile's edges with the segments and steps they came
    from; a later call with finer steps elsewhere reuses a tile whose own
    segments and steps did not change. Growing the windows recomputes the
    tiles, all but those the growth leaves as they were. ``feet``
    are the bank points of the access anchors in closed-off water, by segment:
    a component their samples face is kept too, since at a shallow corner the
    sampled branch starts a few steps from the bank and can miss a small piece.
    """
    origin = np.floor(np.asarray(shapely.bounds(water)[:2]) / tile_m) * tile_m
    sampler = _sampler(bank, steps, origin)
    grown: list[BaseGeometry] = []
    for rounds in range(MAX_GROWTH_ROUNDS + 1):
        medial, outside = _medial_tiles(
            water,
            bank_tree,
            sampler,
            [*seeds, *grown],
            offset_m=offset_m,
            tile_m=tile_m,
            cache=cache,
            local=local,
            faced=_nearest_samples(sampler, bank, *feet),
            growing=rounds > 0,
        )
        medial.diagnostics["growth_rounds"] = rounds
        medial.diagnostics["window_open"] = len(outside)
        if not len(outside):
            return medial
        grown.extend(cache.grow(outside, offset_m))
    return medial


def _medial_tiles(
    water: BaseGeometry,
    bank_tree: shapely.STRtree,
    sampler: _Sampler,
    seeds: list[BaseGeometry],
    *,
    offset_m: float,
    tile_m: float,
    cache: _TileCache,
    local: _Local,
    faced: np.ndarray,
    growing: bool = False,
) -> tuple[_Medial, np.ndarray]:
    """One pass over the tiles; returns the graph and where a kept component runs out of its window.

    A medial point of radius r is right when every sample within r of it was
    triangulated. Each tile samples the bank within ``2d`` plus a margin of its
    cell, and within ``3d`` of the seeds; it keeps the edges whose middle it
    contains and lies within ``2d`` of a seed. It also recomputes the edges just
    across its border; they must equal those the neighbour keeps.

    A pass that grows the windows stands for recomputing every tile (phase 12c
    cleared the cache for it). A tile no added seed comes near reads the same
    samples, the same region and the same keep region round its cell, so its
    cached edges are what recomputing would give: it keeps them. Afterwards the
    cache holds exactly this pass's tiles, as the cleared one did.
    """
    step, origin, d = sampler.step, sampler.origin, offset_m
    layout = cache.layout(seeds, step)
    if layout is None:
        layout = _layout(bank_tree, seeds, origin, offset_m=d, step=step, tile_m=tile_m, cache=cache)
        cache.keep(seeds, step, layout)
    seed_tree, keep_region = layout.seed_tree, layout.keep_region
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
    visited: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, frozenset[int], dict[str, Any]]] = {}
    for column, row, region, segments, near_ids in layout.tiles:
        left, bottom = origin[0] + column * tile_m, origin[1] + row * tile_m
        cached = cache.tiles.get((column, row))
        if (
            cached is not None
            and np.array_equal(cached[0], segments)
            and np.array_equal(cached[1], sampler.steps[segments])
            and (not growing or cached[2] == near_ids)
        ):
            found = dict(cached[3])
            visited[(column, row)] = cached
            diagnostics["tiles_reused"] = diagnostics.get("tiles_reused", 0) + 1
        else:
            shapely.prepare(region)
            computed = _tile_samples(local, bank_tree, sampler, segments, region, keep_region, (left, bottom), tile_m=tile_m, offset_m=d)
            shapely.destroy_prepared(region)
            if computed is None:
                continue
            found = computed
            cache.tiles[(column, row)] = visited[(column, row)] = (segments, sampler.steps[segments].copy(), near_ids, dict(found))
        diagnostics["tiles"] += 1
        for key in ("samples", "triangles", "voronoi_edges", "outside_water_edges", "not_empty_edges"):
            diagnostics[key] += found.pop(key)
        owned.append(found["owned"])
        band.append(found["band"])
        outer.append(found["outer"])
    if growing:
        cache.tiles = visited
    edges = _stack(owned)
    medial, keys = _graph(sampler, edges, seed_tree, local, faced)
    # The witness: an edge computed across a border must be the one its owner kept.
    figures, medial.seams = _overlap(edges, _stack(band))
    medial.seams = medial.seams + origin
    diagnostics.update(figures)
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
    local: _Local,
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
    found = _tile_edges(local, bank_tree, sampler, ids, points, keep_region, corner, tile_m=tile_m, offset_m=offset_m)
    found["samples"] = len(ids)
    return found


def _tile_edges(
    local: _Local,
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
    water = local.water
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
        # The whole water, not the cell's: cut in a cell, the far end moved by a nanometre once in the
        # Lomsdal-Visten sea (phase 12c-2), and the few thousand cuts a sea makes cost seconds.
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


def _overlap(edges: dict[str, np.ndarray], witness: dict[str, np.ndarray]) -> tuple[dict[str, Any], np.ndarray]:
    """The overlap witness: each edge a tile computed just across its border against the edges the tiles own.

    Returns its figures and the middle of every witness edge that could part the network at the
    border: one between two samples its owner joins by no edge at all, or one whose owned
    counterpart ends at another node where the witness's end is a node the middle runs on
    through. An end at radius d or at the bank is a leaf; a clip computed a millimetre apart there
    parts nothing.

    Keys are compared as rows of numbers rather than Python tuples, which a sea's millions of
    edges would hold in gigabytes; ``+ 0.0`` makes a rounded -0 the 0 a tuple compares equal to.
    """

    def rows(*columns: np.ndarray) -> np.ndarray:
        table = np.ascontiguousarray(np.column_stack([np.asarray(c, dtype=np.float64) + 0.0 for c in columns]))
        return table.view(np.dtype((np.void, table.dtype.itemsize * table.shape[1]))).ravel()

    lo, hi, one, other = _edge_keys(edges)
    w_lo, w_hi, w_one, w_other = _edge_keys(witness)
    # Which of the witness's ends, in the order its key puts them, is a leaf: cut at radius d or at the bank.
    first_key, second_key = _node_keys(witness["q0"]), _node_keys(witness["q1"])
    swap = (first_key.real > second_key.real) | ((first_key.real == second_key.real) & (first_key.imag > second_key.imag))
    leaf0, leaf1 = witness["rim0"] | witness["bank0"], witness["rim1"] | witness["bank1"]
    leaf_one, leaf_other = np.where(swap, leaf1, leaf0), np.where(swap, leaf0, leaf1)
    compared = w_one != w_other
    w_lo, w_hi, w_one, w_other = w_lo[compared], w_hi[compared], w_one[compared], w_other[compared]
    mismatched = ~np.isin(
        rows(w_lo, w_hi, w_one.real, w_one.imag, w_other.real, w_other.imag), rows(lo, hi, one.real, one.imag, other.real, other.imag)
    )
    # A mismatch between the same two samples is a clip point computed from a differently ended edge; the
    # owned edge between them that counts is the last one stacked.
    pairs = rows(lo, hi)[::-1]
    known, first = np.unique(pairs, return_index=True)
    asked = rows(w_lo[mismatched], w_hi[mismatched])
    place = np.minimum(np.searchsorted(known, asked), max(len(known) - 1, 0))
    found = (known[place] == asked) if len(known) else np.zeros(len(asked), dtype=bool)
    owned = len(lo) - 1 - first[place[found]]
    first_gap, second_gap = w_one[mismatched][found] - one[owned], w_other[mismatched][found] - other[owned]
    # C's hypot, as Python's abs of a complex number takes it.
    apart = np.maximum(np.hypot(first_gap.real, first_gap.imag), np.hypot(second_gap.real, second_gap.imag)) / 1e6
    figures = {
        "overlap_edges": int(compared.sum()),
        "overlap_mismatches": int(mismatched.sum()),
        "overlap_missing": int(mismatched.sum() - found.sum()),
        "overlap_largest_difference_m": float(apart.max()) if len(apart) else 0.0,
    }
    parting = ~found.copy()
    parting[np.flatnonzero(found)] = ((first_gap != 0) & ~leaf_one[compared][mismatched][found]) | (
        (second_gap != 0) & ~leaf_other[compared][mismatched][found]
    )
    middles = (witness["q0"][compared][mismatched] + witness["q1"][compared][mismatched]) / 2
    return figures, middles[parting]


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
    local: _Local,
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
    xy, gens, rim, unique, u, v, a, b = _corners(sampler, local, xy, gens, rim, unique, u, v, a, b)
    bank_end = np.concatenate([bank_end, np.zeros(len(xy) - found, dtype=bool)])
    component = _label(len(unique), u, v)
    touched = np.empty(0, dtype=int)
    if len(xy):
        # The tree's own predicate would test each node against an unprepared seed edge by edge.
        node, seed = seed_tree.query(shapely.points(xy))
        touched = np.unique(node[shapely.intersects_xy(seed_tree.geometries[seed], xy[node, 0], xy[node, 1])])
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
    local: _Local,
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
    convex = local.covers(np.asarray(shapely.linestrings(np.stack([xy[leaf], corner], axis=1)), dtype=object))
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
    # The walks below run in Python over plain lists: a numpy scalar read per step costs several times
    # a list's, and the arithmetic is the same double arithmetic either way.
    pointer_list, neighbour_list, via_list, length_list = pointer.tolist(), neighbour.tolist(), via.tolist(), length.tolist()
    protected_list = protected.tolist()
    degree_list = np.diff(pointer).tolist()
    parent_list = [-1] * count
    parent_edge_list = [-1] * count
    peeled_list = [False] * count
    order: list[int] = []
    stack = [int(i) for i in np.flatnonzero((np.diff(pointer) == 1) & ~protected)]
    for _ in range(2 * count + 1):
        if not stack:
            break
        x = stack.pop()
        if peeled_list[x]:
            continue
        peeled_list[x] = True
        order.append(x)
        for k in range(pointer_list[x], pointer_list[x + 1]):
            y = neighbour_list[k]
            if peeled_list[y]:
                continue
            parent_list[x], parent_edge_list[x] = y, via_list[k]
            degree_list[y] -= 1
            if degree_list[y] == 1 and not protected_list[y]:
                stack.append(y)
            break
    else:
        raise RuntimeError("peeling did not finish within its bound")
    parent = np.asarray(parent_list, dtype=int)
    parent_edge = np.asarray(parent_edge_list, dtype=int)
    peeled = np.asarray(peeled_list, dtype=bool)
    kept = np.zeros(len(u), dtype=bool)
    category = np.full(len(u), "", dtype=object)
    core_edge = ~peeled[u] & ~peeled[v]
    kept[core_edge] = True
    core_kind = np.where(joined >= 2, PASSAGE, np.where(joined == 1, LOOP, VANISHED if vanished else ISOLATED))
    category[core_edge] = core_kind[component[u[core_edge]]]
    height_list = [0.0] * count
    best_list = [-1] * count
    total_list = [0.0] * count
    children: dict[int, list[int]] = {}
    for x in order:
        p = parent_list[x]
        if p < 0:
            continue
        children.setdefault(p, []).append(x)
        reach = height_list[x] + length_list[parent_edge_list[x]]
        total_list[p] += total_list[x] + length_list[parent_edge_list[x]]
        if reach > height_list[p]:
            height_list[p], best_list[p] = reach, x
    height = np.asarray(height_list)
    best = np.asarray(best_list, dtype=int)
    total = np.asarray(total_list)
    kept_list = kept.tolist()
    category_list = category.tolist()
    pending = [x for x in order if parent_list[x] >= 0 and not peeled_list[parent_list[x]]]
    for _ in range(count + 1):
        if not pending:
            break
        x = pending.pop()
        if height_list[x] + length_list[parent_edge_list[x]] < bay_m:
            continue
        node = x
        for _ in range(count + 1):
            kept_list[parent_edge_list[node]] = True
            category_list[parent_edge_list[node]] = BAY
            pending.extend(y for y in children.get(node, []) if y != best_list[node])
            if best_list[node] < 0:
                break
            node = best_list[node]
    kept = np.asarray(kept_list, dtype=bool)
    category = np.asarray(category_list, dtype=object)
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
    local: _Local,
    failures: list[dict[str, Any]],
) -> _Network:
    """Build, prune and measure the centre network of one body, halving the sampling step where the middle gate fails.

    The halving is local: the bank segments within twice a failing node's
    radius, plus two steps, are sampled at half their step, and only the tiles
    that read them are triangulated again.
    """
    vanished = not rings
    # The raw contour's segments, the same in every halving round.
    ring_tree = shapely.STRtree(np.concatenate([_edges(coords) for coords in rings])) if rings else None
    feet = _anchor_feet(bank, bank_tree, closed, anchors)
    # An anchor's own corner may cast a branch that no closed-off piece touches: seed it too.
    seeds = [*seeds, *np.asarray(shapely.buffer(shapely.points(feet[1]), 1.0), dtype=object)] if len(feet[1]) else seeds
    level = np.zeros(len(bank.lines), dtype=int)
    cache = _TileCache()
    halvings = 0
    for halvings in range(CENTRE_HALVINGS + 1):
        medial = _medial(
            water, bank, bank_tree, seeds, offset_m=offset_m, steps=step / 2.0**level, tile_m=tile_m, cache=cache, local=local, feet=feet
        )
        false_joins = _false_joins(medial, ring_tree, specks)
        pinches = _tie_pinches(medial, local)
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
    if len(medial.seams) and kept.edge.any():
        # Two tiles that triangulate a border differently (near-cocircular samples leave GEOS's Delaunay to the
        # rest of each tile's samples) can end their edges at different nodes and cut a kept line there.
        kept_ids = np.flatnonzero(kept.edge)
        kept_lines = np.asarray(shapely.linestrings(np.stack([medial.xy[medial.u[kept_ids]], medial.xy[medial.v[kept_ids]]], axis=1)), dtype=object)
        near = np.unique(shapely.STRtree(kept_lines).query(shapely.points(medial.seams), predicate="dwithin", distance=TILE_BAND_M)[0])
        for where in near:
            failures.append(
                {
                    "body": body,
                    "kind": "seam",
                    "detail": "two tiles disagree about the middle beside a kept line",
                    "geometry": Point(medial.seams[where]),
                }
            )
    join_node = np.flatnonzero(medial.rim & on_kept)
    join_xy, join_ring, join_segment, gap = _snap_joins(body, medial.xy[join_node], rings, ring_tree, failures)
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


def _false_joins(medial: _Medial, ring_tree: shapely.STRtree | None, specks: list[Polygon]) -> int:
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
    if ring_tree is not None:
        _, gap = ring_tree.query_nearest(shapely.points(medial.xy[ends]), return_distance=True, all_matches=False)
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


def _tie_pinches(medial: _Medial, local: _Local) -> int:
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
        if local.covers(np.asarray([LineString([medial.xy[end], medial.xy[target]])], dtype=object))[0]:
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
    body: int, points: np.ndarray, rings: list[np.ndarray], ring_tree: shapely.STRtree | None, failures: list[dict[str, Any]]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Each join's nearest point on the raw contour, as the ring and segment it will be inserted into, and its distance."""
    if not len(points):
        return np.empty((0, 2)), np.empty(0, dtype=int), np.empty(0, dtype=int), np.empty(0)
    if ring_tree is None:
        raise ValueError("joins with no contour to snap to")
    lines = ring_tree.geometries
    ring_of = np.concatenate([np.full(len(coords) - 1, i) for i, coords in enumerate(rings)])
    segment_of = np.concatenate([np.arange(len(coords) - 1) for coords in rings])
    (_, nearest), distance = ring_tree.query_nearest(shapely.points(points), return_distance=True, all_matches=False)
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
    local: _Local,
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
            piece, piece_values, local, dam_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page, joins=network.join_xy
        )
        rows.append(row)
        decoded_lines.append(line)
        raw_lines.append(LineString(piece.coords))
        keeps.append(keep)
    # A centre piece simplified apart may cross a contour or another centre piece; it gives back vertices, the contour does not.
    all_decoded, all_raw = [*contour_decoded, *decoded_lines], [*contour_raw, *raw_lines]
    offset = len(contour_decoded)
    crossings, contacts = _crossings(all_decoded, all_raw, only=np.arange(offset, len(all_decoded)))
    for _ in range(MAX_REFINE_ROUNDS):
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
                pieces[i], values[i], local, dam_tree, tolerance_m=tolerance_m, to_page=to_page, from_page=from_page, joins=network.join_xy
            )
            all_decoded[offset + i] = decoded_lines[i]
        crossings, contacts = _crossings(all_decoded, all_raw, only=np.arange(offset, len(all_decoded)))
    for _, _, where in crossings:
        failures.append(
            {"body": body, "kind": "crossing", "detail": "a centre piece crosses another line where the raw lines do not", "geometry": where}
        )
    for _, _, where in contacts:
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
    local: _Local,
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
    raw_index = _SegmentIndex.of(raw)
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
            back = _SegmentIndex.of(line).distance(raw, span)
            if not judged.any():
                measured[name] = back
                continue
            forward, _ = _deviation_bound(line, raw_index, keep[:-1], keep[1:] - 1, gate=np.where(judged, np.maximum(segment_room, 0.0), np.inf))
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
    dry = _dry(simplified_segments, local)
    decoded_dry = _dry(decoded_segments, local)
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


def _dry(segments: np.ndarray, local: _Local) -> tuple[float, float]:
    """The length of the segments outside the water, and the farthest any of it lies from the water."""
    water = local.water
    wet = local.covers(segments)
    if wet.all():
        return 0.0, 0.0
    length, far = 0.0, 0.0
    for segment in segments[~wet]:
        # A whole sea is slow to subtract from; the water round the segment is all that matters.
        x0, y0, x1, y1 = shapely.bounds(segment)
        around = shapely.clip_by_rect(water, x0 - 1, y0 - 1, x1 + 1, y1 + 1)
        outside = shapely.difference(segment, around)
        length += float(outside.length)
        coordinates = shapely.get_coordinates(outside)
        if len(coordinates):
            far = max(far, float(shapely.distance(shapely.points(coordinates), around).max()))
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


#: Phase 9's bank is the water's outline simplified at 5 m, so an anchor on it lies at most that
#: far off the water; a spur's run from its anchor up to the water stays within that band.
BANK_STEP_M = SHORE_SIMPLIFY_M + 0.1
#: Implementation choice (12d): the windows round an anchor a bent spur is sought in, smallest first.
SPUR_WINDOWS_M = (60.0, 250.0, 1000.0)
#: Implementation choice (12d): a bent spur turns this far into the water off the bank corner it rounds.
TURN_OFFSET_M = 0.5
#: How far a spur may stray off the water beyond its bank step: the page's grid at a bank end or in
#: grid-narrow water, where its written target lies (§4.4's 0.1 m).
EXCURSION_M = 0.1
#: A dam disc as a polygon for the bent search, drawn round the analytic circle so no chord cuts into it.
DISC_QUAD_SEGS = 32
#: It is drawn a grid move wider still, so that no written vertex of a way round it falls inside the circle.
DISC_POLYGON_M = DAM_CUT_M / math.cos(math.pi / (4 * DISC_QUAD_SEGS)) + GRID_MOVE_M + 0.01
#: How far short of a target's foot the bent search tests the water: a line ending on a dam's circle
#: ends inside that polygon, and the analytic test in _valid reads the last stretch instead.
FOOT_SLACK_M = 0.1
#: Where an anchor on a disc's circle steps out to, straight away from the dam: just beyond the polygon.
DISC_OUTSIDE_M = DISC_POLYGON_M + 0.01
#: Beyond the line, 15 m and its approved 2.1 m deviation off the bank, a contact is in open water.
OPEN_BEYOND_M = PADDLE_OFFSET_M + CONTOUR_DEVIATION_M
#: Where along its stream a phase-9 mouth anchor may lie from the stream's actual mouth: the 5 m bank
#: crosses a stream up to 5 m off the water, farther along a stream that meets the bank at a slant.
MOUTH_MATCH_M = 25.0
#: Contact roles that are a line passing over the water rather than an arrival at its bank (12a's inventory).
CROSSING_ROLES = frozenset({"walking_in_water", "stream_crossing"})
MOUTH_ROLE = "mouth"
STREAM_CROSSING_ROLE = "stream_crossing"
#: A contact that is the map's crop rather than a way to the water: a line cut at the extent and
#: bridged to its neighbour. Phase 9 kept such ends out of the landing audit, and so does this.
CROP_ROLE = "crop"
#: How a contact reaches the line: by a spur of its own, straight or bent; by its own line crossing
#: the new lines; along its stream, which is not surface geometry and stays; at its stream's mouth
#: join; on the line itself, where a centre branch ends at the bank corner the anchor stands on; or
#: not at all, where the contact is the map's crop, or a way crossing open water far from any bank.
STRAIGHT, BENT, CROSSES, ON_STREAM, AT_MOUTH, ON_LINE, AT_CROP = "straight", "bent", "crossing", "stream", "mouth", "on line", "crop"
OVER_WATER = "over water"
#: Where a class-2 stream meets its body's water: across the outline, or ending inside it.
MOUTH_KIND, END_KIND = "mouth", "end"

SPUR_COLUMNS = [
    "contact",
    "roles",
    "body",
    "route",
    "source",
    "target",
    "target_row",
    "node",
    "length_m",
    "bank_step_m",
    "bank_step_inland_m",
    "dry_m",
    "stray_m",
    "decoded_dry_m",
    "decoded_stray_m",
    "dam_clearance_m",
    "anchor_moved_m",
    "geometry",
]


@dataclass
class Landings:
    """How every retained contact reaches the line, the stream mouths, and the lake-owned interfaces.

    :mod:`trails.network.paddle_network` nodes these lines into the network (12e).

    Attributes:
        spurs: One row per contact: ``contact`` (its row in the contacts given), ``roles``, ``body``,
            ``route`` (straight, bent, crossing, stream, mouth, on line, crop, over water), ``source`` (Landing water
            where a line is added from the bank, Open water from a contact out beyond the line),
            ``target`` (contour, centre or node) and ``target_row``, ``node``
            (12c's anchor node, where reused), ``length_m``, ``bank_step_m`` and
            ``bank_step_inland_m`` (the run from the anchor up to the water, and how far off the
            water it reaches), ``dry_m`` and ``stray_m`` (outside the water beyond that run, and how
            far off it), ``decoded_dry_m``, ``decoded_stray_m`` and ``dam_clearance_m`` (after the
            page's grid), ``anchor_moved_m`` (how far the grid rule of 12c moved a written vertex
            out of a dam disc) and the spur as ``geometry``; the anchor where no line is added
        mouths: One row per class-2 stream mouth or stream end inside the water: ``stream`` (its
            row), ``body``, ``kind``, the same route and check columns, and the join as ``geometry``
        interfaces: One row per exact lake-owned interface: ``body``, the lake's owner columns,
            ``lake_side`` and ``other_side`` (the pieces ending on it on each side), ``meets``
            (those ends, the points 12e nodes it at) and the interface as ``geometry``
        links: Open water from an interface into a side where no piece ends on it: ``interface``,
            ``side``, the route and check columns and ``geometry``
        failures: What no route could settle: ``kind``, ``detail``, the place, and ``candidate``,
            the straight line that was tried
    """

    spurs: gpd.GeoDataFrame
    mouths: gpd.GeoDataFrame
    interfaces: gpd.GeoDataFrame
    links: gpd.GeoDataFrame
    failures: gpd.GeoDataFrame


@dataclass
class _Reach:
    """One body's water, its lines and the dam points near it, for routing a spur."""

    local: _Local
    targets: np.ndarray
    labels: list[tuple[str, int]]
    tree: shapely.STRtree | None
    dam_xy: np.ndarray
    discs: BaseGeometry | None
    #: The page's grid, and the dams whose discs a written vertex is moved out of.
    dam_tree: shapely.STRtree | None = None
    to_page: Transformer | None = None
    from_page: Transformer | None = None


def _dam_clearance(coords: np.ndarray, dam_xy: np.ndarray) -> float:
    """The least distance of a polyline from the dam points: the analytic disc test of every segment."""
    if not len(dam_xy) or not len(coords):
        return math.inf
    if len(coords) == 1:
        return float(np.hypot(*(dam_xy - coords[0]).T).min())
    return float(min(_distance_to_segment(dam_xy, one, other).min() for one, other in zip(coords[:-1], coords[1:], strict=True)))


def _dry_after_step(line: LineString, water: BaseGeometry) -> tuple[float, float, float, float]:
    """A spur's runs outside the water: the one from its anchor up to the water, its farthest reach off
    the water, the rest's length, and how far the rest strays."""
    dry = [g for g in shapely.get_parts(shapely.difference(line, water)) if isinstance(g, LineString) and g.length > DRY_NOISE_M]
    start = Point(line.coords[0])
    # The piece holding the anchor, whichever way round the difference returns it; a written anchor
    # on the water's edge may land a grid move inside it.
    first = [g for g in dry if g.distance(start) <= GRID_MOVE_M]
    rest = [g for g in dry if g.distance(start) > GRID_MOVE_M]
    return float(sum(g.length for g in first)), _off_water(first, water), float(sum(g.length for g in rest)), _off_water(rest, water)


def _off_water(pieces: list[LineString], water: BaseGeometry) -> float:
    """How far off the water the pieces reach, read along them: distance is 1-Lipschitz, so samples
    every FINE_SAMPLE_M bound it within half of that."""
    if not pieces:
        return 0.0
    coordinates = shapely.get_coordinates(shapely.segmentize(np.asarray(pieces, dtype=object), FINE_SAMPLE_M))
    return float(shapely.distance(shapely.points(coordinates), water).max()) + FINE_SAMPLE_M / 2


def _valid(coords: np.ndarray, reach: _Reach, lead: int = 0) -> bool:
    """Whether a spur lies in its body's water after at most the bank step, and clear of every dam disc.

    A spur ends on a written target, and a written line in grid-narrow water or at a bank end may
    lie a few centimetres off it: the rest may stray by the plan's 0.1 m, no more. An anchor on a
    disc's circle keeps its place; its first ``lead`` segments, the step straight away from the dam,
    may be as near the dam as it is, and nothing after them nearer than the disc.
    """
    line = LineString(coords)
    water = reach.local.near(line)
    step, inland, _, stray = _dry_after_step(line, water)
    # The run up to the water is the anchor's own way to it: no longer than its distance from the
    # water and a turn's offset, so it never cuts a headland beside an anchor at the water's edge.
    # Where a dam's disc covers the nearest water, it may go round the disc, within the band
    # phase 9's 5 m bank already lies in.
    off = float(shapely.distance(Point(coords[0]), water))
    round_a_disc = _dam_clearance(coords[:1], reach.dam_xy) < DAM_CUT_M + 2 * BANK_STEP_M
    if step > (2 * BANK_STEP_M if round_a_disc else off + TURN_OFFSET_M) or inland > BANK_STEP_M or stray > EXCURSION_M:
        return False
    if not len(reach.dam_xy):
        return True
    near = min(DAM_CUT_M, _dam_clearance(coords[:1], reach.dam_xy)) - DRY_NOISE_M
    if _dam_clearance(coords[: lead + 1], reach.dam_xy) < near or _dam_clearance(coords[lead:], reach.dam_xy) < DAM_CUT_M - DRY_NOISE_M:
        return False
    if reach.to_page is None or reach.from_page is None:
        return True
    # Written on the page's grid, with 12c's rule moving a vertex out of a disc, it must stay out too.
    written = _off_dams(coords, decoded(coords, reach.to_page, reach.from_page), reach.dam_tree, reach.to_page, reach.from_page, None)
    return _dam_clearance(written, reach.dam_xy) >= DAM_CUT_M - DRY_NOISE_M


def _turns(water: BaseGeometry) -> np.ndarray:
    """The water's reflex corners, each moved ``TURN_OFFSET_M`` into the water: where a shortest way through it bends."""
    out: list[np.ndarray] = []
    for polygon in shapely.get_parts(water):
        if not isinstance(polygon, Polygon):
            continue
        for ring in (polygon.exterior, *polygon.interiors):
            coords = np.asarray(ring.coords)[:-1, :2]
            if len(coords) < 3:
                continue
            before, after = coords - np.roll(coords, 1, axis=0), np.roll(coords, -1, axis=0) - coords
            # Oriented with the water on the left of every ring, a right turn is a corner of land.
            reflex = before[:, 0] * after[:, 1] - before[:, 1] * after[:, 0] < 0
            if not reflex.any():
                continue
            one = before[reflex] / np.maximum(np.hypot(*before[reflex].T), 1e-12)[:, None]
            other = after[reflex] / np.maximum(np.hypot(*after[reflex].T), 1e-12)[:, None]
            normal = np.c_[-one[:, 1], one[:, 0]] + np.c_[-other[:, 1], other[:, 0]]
            length = np.hypot(*normal.T)
            usable = length > 1e-9
            out.append(coords[reflex][usable] + TURN_OFFSET_M * normal[usable] / length[usable][:, None])
    if not out:
        return np.empty((0, 2))
    turns = np.vstack(out)
    return turns[shapely.covers(water, shapely.points(turns))]


def _bent(point: np.ndarray, reach: _Reach, targets: np.ndarray, tree: shapely.STRtree, lead: np.ndarray) -> tuple[np.ndarray, int] | None:
    """The shortest way found through the water round the bank's corners, in growing windows round the point."""
    for half in SPUR_WINDOWS_M:
        window = shapely.box(point[0] - half, point[1] - half, point[0] + half, point[1] + half)
        chosen = tree.query(window)
        if not len(chosen):
            continue
        water = shapely.clip_by_rect(reach.local.near(window), *window.bounds)
        if reach.discs is not None:
            water = shapely.difference(water, reach.discs)
        # The nearest water clear of the discs that holds a line: a speck between a disc and the bank leads nowhere.
        held = [g for g in shapely.get_parts(water) if shapely.intersects(g, targets[chosen]).any()]
        if not held:
            continue
        inland = float(shapely.distance(Point(point), shapely.multipolygons(held) if len(held) > 1 else held[0]))
        if inland > 2 * BANK_STEP_M:
            continue
        if inland > 0:
            # An anchor on the bank crosses just that much land to it, round a disc where it must; _valid
            # measures how far off the real water that run reaches, and refuses any other dry run.
            reach_in: BaseGeometry = shapely.buffer(Point(point), inland + FOOT_SLACK_M, quad_segs=DISC_QUAD_SEGS)
            if reach.discs is not None:
                reach_in = shapely.difference(reach_in, reach.discs)
            water = shapely.union(water, reach_in)
        water = shapely.orient_polygons(water, exterior_cw=False)
        if water.is_empty or not water.covers(Point(point)):
            continue
        shapely.prepare(water)
        found = _visible_way(point, _turns(water), water, targets[chosen])
        if found is not None:
            path, target = found
            coords = np.array([*lead, *path])
            if _valid(coords, reach, len(lead)):
                return coords, int(chosen[target])
    return None


def _visible_way(origin: np.ndarray, turns: np.ndarray, water: BaseGeometry, targets: np.ndarray) -> tuple[list[np.ndarray], int] | None:
    """Dijkstra over the visibility of corners, ending at the nearest point of a target line seen from a corner."""
    import heapq

    xy = np.vstack([origin[None, :], turns])
    count = len(xy)
    distance = np.full(count, math.inf)
    previous = np.full(count, -1, dtype=int)
    settled = np.zeros(count, dtype=bool)
    distance[0] = 0.0
    heap = [(0.0, 0)]
    best: tuple[float, int, np.ndarray, int] = (math.inf, -1, origin, -1)
    # Each corner settles once; a stale heap entry is skipped. The bound is the pushes a settle can make.
    for _ in range(count * count + 1):
        if not heap:
            break
        reached, node = heapq.heappop(heap)
        if settled[node]:
            continue
        settled[node] = True
        if reached >= best[0]:
            break
        here = Point(xy[node])
        feet = shapely.get_coordinates(shapely.shortest_line(here, targets))[1::2]
        lengths = np.hypot(*(feet - xy[node]).T)
        for index in np.argsort(lengths)[:4]:
            total = reached + float(lengths[index])
            if total >= best[0]:
                break
            # A target can end on a dam's circle, inside the polygon drawn round it; the analytic test follows.
            short = feet[index] - (feet[index] - xy[node]) * min(1.0, FOOT_SLACK_M / max(float(lengths[index]), 1e-12))
            if shapely.covers(water, LineString([xy[node], short])):
                best = (total, node, feet[index], int(index))
                break
        open_nodes = np.flatnonzero(~settled)
        steps = np.hypot(*(xy[open_nodes] - xy[node]).T)
        better = reached + steps < np.minimum(distance[open_nodes], best[0])
        open_nodes, steps = open_nodes[better], steps[better]
        if not len(open_nodes):
            continue
        seen = shapely.covers(water, shapely.linestrings(np.stack([np.repeat(xy[node][None, :], len(open_nodes), axis=0), xy[open_nodes]], axis=1)))
        for other, step in zip(open_nodes[seen], steps[seen], strict=True):
            distance[other] = reached + float(step)
            previous[other] = node
            heapq.heappush(heap, (distance[other], int(other)))
    else:
        raise RuntimeError("the corner search exceeded its bound")
    if best[1] < 0:
        return None
    path = [best[2]]
    node = best[1]
    for _ in range(count):
        path.append(xy[node])
        if node == 0:
            break
        node = int(previous[node])
    return path[::-1], best[3]


def _route(point: np.ndarray, reach: _Reach, targets: np.ndarray, tree: shapely.STRtree) -> tuple[np.ndarray | None, str, int, LineString]:
    """A straight spur to the nearest target point if it is valid, else the shortest bent way found.

    Returns the spur's coordinates (None where no way was found), its route, the target's index,
    and the straight line tried first.
    """
    prefix = np.empty((0, 2))
    start = point
    if len(reach.dam_xy):
        away = reach.dam_xy[int(np.argmin(np.hypot(*(reach.dam_xy - point).T)))]
        radius = float(np.hypot(*(point - away)))
        if radius < DISC_OUTSIDE_M:
            # An anchor on a disc's circle (a portage landing at a dam) leaves it straight away from the dam.
            if radius < DAM_CUT_M - GRID_MOVE_M or radius == 0:
                return None, "", -1, LineString([point, point])
            start = away + (point - away) * DISC_OUTSIDE_M / radius
            prefix = point[None, :]
    here = Point(start)
    index = int(tree.nearest(here))
    tried = shapely.shortest_line(here, targets[index])
    coords = np.vstack([prefix, shapely.get_coordinates(tried)])
    if _valid(coords, reach, len(prefix)):
        return coords, STRAIGHT, index, tried
    found = _bent(start, reach, targets, tree, prefix)
    if found is None:
        return None, "", index, tried
    return found[0], BENT, found[1], tried


def _checked(coords: np.ndarray, reach: _Reach, to_page: Transformer, from_page: Transformer, dam_tree: shapely.STRtree | None) -> dict[str, Any]:
    """A spur's figures before and after the page's grid; a written vertex the grid put in a dam disc is moved out as 12c does."""
    line = LineString(coords)
    step, inland, dry, stray = _dry_after_step(line, reach.local.near(line))
    written = decoded(coords, to_page, from_page)
    moved = _off_dams(coords, written, dam_tree, to_page, from_page, None)
    shift = float(np.hypot(*(moved - written).T).max()) if len(coords) else 0.0
    decoded_line = LineString(moved)
    _, _, decoded_dry, decoded_stray = _dry_after_step(decoded_line, reach.local.near(decoded_line))
    return {
        "length_m": float(line.length),
        "bank_step_m": step,
        "bank_step_inland_m": inland,
        "dry_m": dry,
        "stray_m": stray,
        "decoded_dry_m": decoded_dry,
        "decoded_stray_m": decoded_stray,
        "dam_clearance_m": _dam_clearance(moved, reach.dam_xy),
        "anchor_moved_m": shift,
        "geometry": decoded_line,
    }


def _unjoined(route: str, length_m: float, at: np.ndarray) -> dict[str, Any]:
    """The figures of a mouth that needs no line of its own."""
    return {
        "route": route,
        "source": None,
        "target": None,
        "target_row": -1,
        "length_m": length_m,
        "bank_step_m": 0.0,
        "bank_step_inland_m": 0.0,
        "dry_m": 0.0,
        "stray_m": 0.0,
        "decoded_dry_m": 0.0,
        "decoded_stray_m": 0.0,
        "dam_clearance_m": math.inf,
        "anchor_moved_m": 0.0,
        "geometry": Point(at),
    }


def _run_to_line(stream: LineString, at: np.ndarray, reach: _Reach) -> float | None:
    """How far along the stream, inside its water, from a mouth or end to the first crossing of the line; None where it does not reach it."""
    if reach.tree is None:
        return None
    water = reach.local.near(stream)
    runs = [g for g in shapely.get_parts(shapely.intersection(stream, water)) if isinstance(g, LineString) and g.length > 0]
    here = Point(at)
    for run in runs:
        start, end = Point(run.coords[0]), Point(run.coords[-1])
        if min(start.distance(here), end.distance(here)) > 1e-6:
            continue
        hits = reach.tree.query(run, predicate="intersects")
        if not len(hits):
            return None
        crossing = shapely.get_coordinates(shapely.intersection(run, shapely.union_all(reach.targets[hits])))
        if not len(crossing):
            return None
        along = np.array([run.project(Point(xy)) for xy in crossing])
        return float((along if start.distance(here) <= end.distance(here) else run.length - along).min())
    return None


def _stream_mouths(streams: np.ndarray, bodies: Bodies, body_tree: shapely.STRtree, locals_: dict[int, _Local]) -> list[dict[str, Any]]:
    """Where each class-2 stream piece crosses its body's outline, and its ends that lie inside the water."""
    rows: list[dict[str, Any]] = []
    hits = body_tree.query(streams, predicate="intersects")
    for stream_index in np.unique(hits[0]):
        line = streams[stream_index]
        found: dict[tuple[float, float], tuple[int, str]] = {}
        for body in np.unique(bodies.body[hits[1][hits[0] == stream_index]]):
            local = locals_[int(body)]
            water = local.near(line)
            crossing = shapely.intersection(line, water.boundary)
            for xy in shapely.get_coordinates(crossing):
                found.setdefault((float(xy[0]), float(xy[1])), (int(body), MOUTH_KIND))
            for xy in (np.asarray(line.coords[0])[:2], np.asarray(line.coords[-1])[:2]):
                end = Point(xy)
                if shapely.contains(water, end):
                    found.setdefault((float(xy[0]), float(xy[1])), (int(body), END_KIND))
        for (x, y), (body, kind) in found.items():
            rows.append({"stream": int(stream_index), "body": body, "kind": kind, "at": np.array([x, y])})
    return rows


def _interface_lines(body: int, bodies: Bodies, extent: BaseGeometry | None, dam_tree: shapely.STRtree | None) -> list[dict[str, Any]]:
    """The exact interfaces between a body's lake groups and its other water, once each, cut to the map and the dams."""
    members = np.flatnonzero(bodies.body == body)
    owners = bodies.owner[members]
    lake = np.array([bodies.owners[o][LAKE_BODY] is not None for o in owners], dtype=bool)
    if lake.all() or not lake.any():
        return []
    rows: list[dict[str, Any]] = []
    other = shapely.union_all(bodies.polygons[members[~lake]])
    for owner in np.unique(owners[lake]):
        own = shapely.union_all(bodies.polygons[members[owners == owner]])
        shared = shapely.intersection(own.boundary, other.boundary)
        parts = [
            g
            for g in shapely.get_parts(shapely.line_merge(shapely.union_all([p for p in shapely.get_parts(shared) if isinstance(p, LineString)])))
            if isinstance(g, LineString)
        ]
        for part in parts:
            pieces = [part]
            if extent is not None:
                pieces = [g for g in shapely.get_parts(shapely.intersection(part, extent)) if isinstance(g, LineString) and g.length > 0]
            if dam_tree is not None:
                pieces = [g for piece in pieces for g in _outside_dams(piece, dam_tree)]
            for piece in pieces:
                rows.append({"body": body, "owner": int(owner), **bodies.owners[int(owner)], "geometry": piece})
    return rows


def landings(
    result: Contours,
    bodies: Bodies,
    contacts: gpd.GeoDataFrame,
    *,
    crs: Any,
    dams: np.ndarray | None = None,
    streams: np.ndarray | None = None,
    extent: BaseGeometry | None = None,
) -> Landings:
    """Join every retained contact, stream mouth and lake-owned interface to the line through the water.

    Args:
        result: The contours and centre network of :func:`contours`, in ``crs``
        bodies: The eligible water they were built from, in ``crs``
        contacts: Points where land access meets today's water, in ``crs``: ``roles`` (comma-separated,
            as 12a's inventory names them), ``surface`` (whether the point lies on today's Shore or
            Open water rather than on a stream alone), ``anchor`` (its index among the anchors
            given to :func:`contours`, or -1) and optionally ``through``, the line passing through a
            crossing contact
        crs: A metric CRS
        dams: Dam and lock-gate points in ``crs``
        streams: Class-2 stream pieces in ``crs``, cut at the dams
        extent: Map extent in ``crs``

    Returns:
        The spurs, the mouth joins, the interfaces and their links, and every failure
    """
    to_page, from_page = _page_round_trip(crs)
    dam_points = np.asarray(dams if dams is not None else [], dtype=object)
    dam_tree = shapely.STRtree(dam_points) if len(dam_points) else None
    dam_xy = shapely.get_coordinates(dam_points) if len(dam_points) else np.empty((0, 2))
    body_tree = shapely.STRtree(bodies.polygons)
    points = contacts.geometry.to_numpy()
    xy = shapely.get_coordinates(points)
    # The body of each contact: the nearest water within the bank step, 12c's body where it gave a node.
    which, polygon = body_tree.query_nearest(points, max_distance=BANK_STEP_M, all_matches=False)
    body_of = np.full(len(points), -1, dtype=int)
    body_of[which] = bodies.body[polygon]
    node_of: dict[int, np.ndarray] = {}
    if len(result.anchors):
        kept = result.anchors[result.anchors["kept"].astype(bool)]
        by_anchor = {int(a): (int(b), shapely.get_coordinates(g)[0]) for a, b, g in zip(kept["anchor"], kept["body"], kept.geometry, strict=True)}
        for item, anchor in enumerate(contacts["anchor"].to_numpy(dtype=int)):
            if anchor in by_anchor:
                body_of[item], node_of[item] = by_anchor[anchor]
    wanted = set(body_of[body_of >= 0].tolist())
    stream_rows: list[dict[str, Any]] = []
    locals_: dict[int, _Local] = {}
    if streams is not None and len(streams):
        near_streams = np.unique(body_tree.query(streams, predicate="intersects")[1])
        wanted |= set(bodies.body[near_streams].tolist())
    for body in sorted(wanted):
        locals_[body] = _local(bodies.union(body))
    if streams is not None and len(streams):
        stream_rows = _stream_mouths(np.asarray(streams, dtype=object), bodies, body_tree, locals_)
    drawn_bodies = sorted({int(b) for b in result.lines["body"]} | {int(b) for b in result.centre["body"]})
    interface_rows = [row for body in drawn_bodies for row in _interface_lines(body, bodies, extent, dam_tree)]
    wanted |= {row["body"] for row in interface_rows}
    for body in sorted(wanted - set(locals_)):
        locals_[body] = _local(bodies.union(body))
    stream_lines = np.asarray(streams if streams is not None else [], dtype=object)
    failures: list[dict[str, Any]] = []
    spur_rows: list[dict[str, Any]] = []
    mouth_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []

    def reach_of(body: int, lines: gpd.GeoDataFrame, centre: gpd.GeoDataFrame) -> _Reach:
        targets = np.array([*lines.geometry, *centre.geometry], dtype=object)
        labels = [*(("contour", int(i)) for i in lines.index), *(("centre", int(i)) for i in centre.index)]
        water = locals_[body].water
        near = dam_tree.query(water, predicate="dwithin", distance=DAM_CUT_M) if dam_tree is not None else np.empty(0, dtype=int)
        discs = shapely.union_all(shapely.buffer(dam_points[near], DISC_POLYGON_M, quad_segs=DISC_QUAD_SEGS)) if len(near) else None
        tree = shapely.STRtree(targets) if len(targets) else None
        return _Reach(locals_[body], targets, labels, tree, dam_xy[near], discs, dam_tree, to_page, from_page)

    def spur(point: np.ndarray, reach: _Reach, node: np.ndarray | None, detail: str) -> dict[str, Any] | None:
        if node is not None and _dam_clearance(node[None, :], reach.dam_xy) < DAM_CUT_M:
            # 12c's node lies on a branch a dam disc cut away: the anchor reaches the body's lines instead.
            failures.append({"kind": "node in a dam disc", "detail": detail, "geometry": Point(node), "candidate": None})
            node = None
        if node is not None:
            targets = np.array([Point(node)], dtype=object)
            tree = shapely.STRtree(targets)
            labels: list[tuple[str, int]] = [("node", -1)]
        elif reach.tree is not None:
            targets, tree, labels = reach.targets, reach.tree, reach.labels
        elif extent is not None and shapely.distance(Point(point), extent.boundary) <= BANK_STEP_M:
            # Water the map's crop leaves no line of inside the map: the crop, as phase 9 counted such ends.
            return _unjoined(AT_CROP, 0.0, point)
        else:
            failures.append({"kind": "no line", "detail": detail, "geometry": Point(point), "candidate": None})
            return None
        index = int(tree.nearest(Point(point)))
        if shapely.distance(Point(point), targets[index]) <= DRY_NOISE_M:
            # The line already runs through the anchor: a centre branch ending at the bank corner it stands on.
            target, target_row = labels[index]
            return {**_unjoined(ON_LINE, 0.0, point), "target": target, "target_row": target_row}
        coords, route, index, tried = _route(point, reach, targets, tree)
        if coords is None and node is not None and reach.tree is not None:
            # 12c chose the node without the dams: it can lie beyond a disc from its anchor.
            failures.append({"kind": "node beyond a dam disc", "detail": detail, "geometry": Point(node), "candidate": tried})
            targets, tree, labels = reach.targets, reach.tree, reach.labels
            coords, route, index, tried = _route(point, reach, targets, tree)
        if coords is None:
            failures.append({"kind": "unresolved", "detail": detail, "geometry": Point(point), "candidate": tried})
            return None
        target, target_row = labels[index]
        # Landing water is the last metres from a bank. A contact out beyond the line, where a way ends
        # on a skerry the water does not cut out or crosses a lake, reaches it across open water.
        here = Point(point)
        open_water = reach.local.water.covers(here) and shapely.distance(here, reach.local.near(here).boundary) > OPEN_BEYOND_M
        return {
            "route": route,
            "source": OPEN_WATER if open_water else LANDING_WATER,
            "target": target,
            "target_row": target_row,
            **_checked(coords, reach, to_page, from_page, dam_tree),
        }

    reaches: dict[int, _Reach] = {}
    for body in sorted(wanted):
        reaches[body] = reach_of(body, result.lines[result.lines["body"] == body], result.centre[result.centre["body"] == body])
    # Stream mouths first: a phase-9 mouth anchor is mapped to its stream's actual mouth.
    for row in stream_rows:
        reach = reaches[row["body"]]
        along = _run_to_line(stream_lines[row["stream"]], row["at"], reach)
        if along is not None and along <= BAY_REACH_M:
            # The stream itself runs on through the water to the line: 12e nodes it where it crosses.
            mouth_rows.append(
                {"stream": row["stream"], "body": row["body"], "kind": row["kind"], "at": Point(row["at"]), **_unjoined(CROSSES, along, row["at"])}
            )
            continue
        joined = spur(row["at"], reach, None, f"stream {row['stream']} {row['kind']}")
        if joined is not None:
            mouth_rows.append({"stream": row["stream"], "body": row["body"], "kind": row["kind"], "at": Point(row["at"]), **joined})
    mouth_tree = shapely.STRtree([row["at"] for row in mouth_rows]) if mouth_rows else None
    roles_of = contacts["roles"].astype(str).to_numpy()
    surface = contacts["surface"].to_numpy(dtype=bool)
    through = contacts["through"].to_numpy() if "through" in contacts else np.full(len(contacts), None, dtype=object)
    for item in range(len(contacts)):
        roles = set(roles_of[item].split(","))
        base = {"contact": item, "roles": roles_of[item], "body": int(body_of[item]), "node": None}
        blank = {"route": None, "source": None, "target": None, "target_row": -1, "length_m": 0.0, "bank_step_m": 0.0, "bank_step_inland_m": 0.0}
        blank["dry_m"] = 0.0
        blank |= {"stray_m": 0.0, "decoded_dry_m": 0.0, "decoded_stray_m": 0.0, "dam_clearance_m": math.inf, "anchor_moved_m": 0.0}
        blank["geometry"] = points[item]
        if not surface[item] or roles == {STREAM_CROSSING_ROLE}:
            # A stream's own line is not surface geometry: it stays as it is, joined at its mouths, and so does this contact.
            spur_rows.append({**base, **blank, "route": ON_STREAM})
            continue
        if roles == {CROP_ROLE}:
            spur_rows.append({**base, **blank, "route": AT_CROP})
            continue
        if body_of[item] < 0:
            failures.append({"kind": "no body", "detail": f"contact {item} ({roles_of[item]})", "geometry": points[item], "candidate": None})
            continue
        reach = reaches[int(body_of[item])]
        if roles <= CROSSING_ROLES:
            if through[item] is not None and reach.tree is not None and len(reach.tree.query(through[item], predicate="intersects")):
                spur_rows.append({**base, **blank, "route": CROSSES})
                continue
            here = Point(xy[item])
            if reach.local.water.covers(here) and shapely.distance(here, reach.local.near(here).boundary) > OPEN_BEYOND_M:
                # A ferry or way over open water crossed an old chord here, far from any bank: not a way
                # to the water but over it, which 12e's open-water chords will cross in their turn.
                spur_rows.append({**base, **blank, "route": OVER_WATER})
                continue
        if roles == {MOUTH_ROLE} and mouth_tree is not None:
            nearest, gap_m = mouth_tree.query_nearest(points[item], max_distance=MOUTH_MATCH_M, return_distance=True, all_matches=False)
            if len(nearest) and mouth_rows[int(nearest[0])]["body"] == body_of[item]:
                # The distance to the mouth, along no line: the stream carries the anchor there.
                spur_rows.append({**base, **blank, "route": AT_MOUTH, "target": "mouth", "target_row": int(nearest[0]), "length_m": float(gap_m[0])})
                continue
        node = node_of.get(item)
        joined = spur(xy[item], reach, node, f"contact {item} ({roles_of[item]})")
        if joined is not None:
            spur_rows.append({**base, **joined, "node": None if node is None else Point(node)})
    # Interfaces: kept once, lake-owned; the pieces ending on them meet them, a side none meets gets a link.
    interfaces: list[dict[str, Any]] = []
    for index, row in enumerate(interface_rows):
        body = row["body"]
        line = row["geometry"]
        ends: list[tuple[np.ndarray, bool]] = []
        for drawn in (result.lines, result.centre):
            own = drawn[(drawn["body"] == body) & ((drawn["start"] == INTERFACE) | (drawn["end"] == INTERFACE))]
            for raw, start, end, lake_body in zip(own["raw"], own["start"], own["end"], own[LAKE_BODY], strict=True):
                coords = shapely.get_coordinates(raw)
                for kind, xy_end in ((start, coords[0]), (end, coords[-1])):
                    if kind == INTERFACE and shapely.distance(Point(xy_end), line) < 1e-6:
                        ends.append((xy_end, lake_body == row[LAKE_BODY]))
        lake_side = sum(1 for _, is_lake in ends if is_lake)
        other_side = len(ends) - lake_side
        interfaces.append(
            {
                "body": body,
                LAKE_BODY: row[LAKE_BODY],
                LAKE_LEVEL: row[LAKE_LEVEL],
                SURFACE_CLASS: row[SURFACE_CLASS],
                "lake_side": lake_side,
                "other_side": other_side,
                "meets": shapely.multipoints([xy_end for xy_end, _ in ends]) if ends else None,
                "geometry": line,
            }
        )
        reach = reaches[body]
        for side, met in (("lake", lake_side), ("other", other_side)):
            if met:
                continue
            is_lake = side == "lake"
            chosen = [
                i
                for i, (kind, frame_row) in enumerate(reach.labels)
                if ((result.lines if kind == "contour" else result.centre).loc[frame_row, LAKE_BODY] == row[LAKE_BODY]) == is_lake
            ]
            if not chosen:
                failures.append(
                    {
                        "kind": "interface side without line",
                        "detail": f"interface {index}, {side} side",
                        "geometry": line.interpolate(0.5, normalized=True),
                        "candidate": None,
                    }
                )
                continue
            targets = reach.targets[chosen]
            tree = shapely.STRtree(targets)
            start = shapely.get_coordinates(shapely.shortest_line(line, targets[int(tree.nearest(line))]))[0]
            way, route, target, tried = _route(start, reach, targets, tree)
            if way is None:
                failures.append({"kind": "unresolved", "detail": f"interface {index}, {side} side", "geometry": Point(start), "candidate": tried})
                continue
            kind, frame_row = reach.labels[chosen[target]]
            link = {"interface": index, "side": side, "route": route, "source": OPEN_WATER, "target": kind, "target_row": frame_row}
            link_rows.append({**link, **_checked(way, reach, to_page, from_page, dam_tree)})

    def frame(records: list[dict[str, Any]], columns: list[str]) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(pd.DataFrame(records, columns=columns), geometry="geometry", crs=crs)

    checks = [
        "route",
        "source",
        "target",
        "target_row",
        "length_m",
        "bank_step_m",
        "bank_step_inland_m",
        "dry_m",
        "stray_m",
        "decoded_dry_m",
        "decoded_stray_m",
        "dam_clearance_m",
        "anchor_moved_m",
        "geometry",
    ]
    mouths = frame(mouth_rows, ["stream", "body", "kind", "at", *checks])
    mouths["at"] = gpd.GeoSeries(mouths["at"], crs=crs)
    faults = frame(failures, ["kind", "detail", "candidate", "geometry"])
    faults["candidate"] = gpd.GeoSeries(faults["candidate"], crs=crs)
    return Landings(
        spurs=frame(spur_rows, SPUR_COLUMNS),
        mouths=mouths,
        interfaces=frame(interfaces, ["body", LAKE_BODY, LAKE_LEVEL, SURFACE_CLASS, "lake_side", "other_side", "meets", "geometry"]),
        links=frame(link_rows, ["interface", "side", *checks]),
        failures=faults,
    )

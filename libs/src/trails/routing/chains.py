"""Chains: the linear units a source's lines fall into.

A chain is what a reader selects, profiles and exports, so the one property it
must have is that it is **linear**. A branching selection has no single sequence
to lay an elevation profile along, and nothing downstream can cope with it.

Chains are built within one source, never across sources. The moment sources
compete over geometry the network falls apart, and there is nothing here that
needs them to.
"""

import hashlib
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from enum import StrEnum
from itertools import groupby
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from trails.routing.noding import (
    DEFAULT_METRIC_CRS,
    NODE_TOLERANCE_M,
    ClipGeometry,
    carry_positions,
    cut_line,
    cut_positions,
    intersection_points,
    lines_of,
    working_lines,
)
from trails.routing.sources import NetworkSource
from trails.routing.topology import cluster_points

#: At a junction, an arm deflecting by more than this is not a plausible
#: continuation of the one arriving. Measured across the three network sources:
#: below it chains stay needlessly short, above it almost nothing is won.
DEFAULT_STROKE_ANGLE_DEG = 45.0

#: How far either side of a junction a direction is read. Long enough to ignore
#: the wobble of a single vertex, short enough that it says nothing about how the
#: way bends further along.
DEFAULT_PROBE_M = 5.0

#: Separator between several identities in one value, as the road and trail
#: layers already write them.
IDENTITY_SEPARATOR = " / "

#: Columns every chain frame carries, before the source's own attributes.
CHAIN_COLUMNS = ("chain_id", "source", "kind", "identity", "length_m")

#: One position of a line. Shapely hands these back with whatever dimensions the
#: source recorded, which is not always two.
Coordinate = tuple[float, ...]


class ChainRule(StrEnum):
    """How a source's noded pieces are joined back into chains.

    Attributes:
        JUNCTION: Break wherever more than two pieces meet. This is what
            ``linemerge`` alone gives, and it is here as the baseline the stroke
            rule is measured against, not as a way to build a map.
        STROKE: Carry on through a junction where identity says the way
            continues, and where it cannot, through the arms that continue each
            other straightest.
    """

    JUNCTION = "junction"
    STROKE = "stroke"


def _carried(source: NetworkSource) -> list[str]:
    """Columns of a source that travel with its geometry.

    Args:
        source: Dataset being read

    Returns:
        Its identity column, if any, followed by its attributes, without repeats
    """
    return [column for column in dict.fromkeys((source.identity_field, *source.attributes)) if column]


def _prepare(source: NetworkSource, clip: ClipGeometry | None, metric_crs: str) -> gpd.GeoDataFrame:
    """Project and clip a source, checking it carries what it promised.

    Args:
        source: Dataset to read
        clip: Extent to cut it to
        metric_crs: Working CRS

    Returns:
        One LineString per row, in ``metric_crs``

    Raises:
        KeyError: If the source names a column it does not have
    """
    missing = [column for column in _carried(source) if column not in source.gdf.columns]
    if missing:
        raise KeyError(f"{source.name} has no column {', '.join(missing)}")
    return working_lines(source.gdf, clip, metric_crs)


def split_source(
    source: NetworkSource,
    clip: ClipGeometry | None = None,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
    tolerance_m: float = NODE_TOLERANCE_M,
) -> gpd.GeoDataFrame:
    """Cut one source's lines wherever they meet each other.

    Args:
        source: Dataset to node
        clip: Extent to cut it to
        metric_crs: Working CRS
        tolerance_m: Distance below which two cut positions are one position

    Returns:
        The pieces, in ``metric_crs``, carrying the source's identity column and
        attributes. Every junction of the source is a piece end, and every piece
        keeps the geometry the source drew, whatever it was noded by.
    """
    lines = _prepare(source, clip, metric_crs)
    keep = _carried(source)

    simplify = source.node_simplify_m > 0
    noding = lines.geometry.simplify(source.node_simplify_m) if simplify else lines.geometry

    geometries: list[LineString] = []
    rows: list[int] = []
    for position, (full, noded, points) in enumerate(zip(lines_of(lines.geometry), lines_of(noding), intersection_points(noding), strict=True)):
        positions = cut_positions(noded, points, tolerance_m)
        for piece in cut_line(full, carry_positions(full, noded, positions) if simplify else positions):
            if piece is not None:
                geometries.append(piece)
                rows.append(position)

    pieces = gpd.GeoDataFrame(lines.iloc[rows][keep].reset_index(drop=True), geometry=geometries, crs=metric_crs)
    pieces.insert(0, "source", source.name)
    return pieces


def chains_of(
    source: NetworkSource,
    clip: ClipGeometry | None = None,
    *,
    rule: ChainRule = ChainRule.STROKE,
    stroke_angle_deg: float = DEFAULT_STROKE_ANGLE_DEG,
    probe_m: float = DEFAULT_PROBE_M,
    metric_crs: str = DEFAULT_METRIC_CRS,
    tolerance_m: float = NODE_TOLERANCE_M,
) -> gpd.GeoDataFrame:
    """Build one source's chains.

    Args:
        source: Dataset to decompose
        clip: Extent to cut it to
        rule: How pieces are joined back together
        stroke_angle_deg: Largest deflection accepted as a continuation
        probe_m: How far either side of a junction a direction is read
        metric_crs: Working CRS
        tolerance_m: Distance below which two coordinates are the same point

    Returns:
        Chains in ``metric_crs``, described by :data:`CHAIN_COLUMNS` and the
        source's own attributes. A source published as whole routes skips the
        decomposition: its features are already linear and already the unit a
        reader means.
    """
    if source.keep_whole:
        lines = _prepare(source, clip, metric_crs)
        identities = _identity_values(lines, source.identity_field)
        coordinates: list[list[Coordinate]] = [list(geometry.coords) for geometry in lines.geometry]
        return _assemble(source, coordinates, [[row] for row in range(len(lines))], lines, identities, tolerance_m)

    pieces = split_source(source, clip, metric_crs=metric_crs, tolerance_m=tolerance_m)
    return build_chains(
        pieces,
        source,
        rule=rule,
        stroke_angle_deg=stroke_angle_deg,
        probe_m=probe_m,
        tolerance_m=tolerance_m,
    )


def build_chains(
    pieces: gpd.GeoDataFrame,
    source: NetworkSource,
    *,
    rule: ChainRule = ChainRule.STROKE,
    stroke_angle_deg: float = DEFAULT_STROKE_ANGLE_DEG,
    probe_m: float = DEFAULT_PROBE_M,
    tolerance_m: float = NODE_TOLERANCE_M,
) -> gpd.GeoDataFrame:
    """Join noded pieces into chains.

    Args:
        pieces: Output of :func:`split_source`
        source: Dataset the pieces came from, for its name and identity column
        rule: How pieces are joined at a junction
        stroke_angle_deg: Largest deflection accepted as a continuation
        probe_m: How far either side of a junction a direction is read
        tolerance_m: Distance below which two coordinates are the same point

    Returns:
        Chains described by :data:`CHAIN_COLUMNS` and the source's attributes
    """
    geometries = lines_of(pieces.geometry)
    identities = _identity_values(pieces, source.identity_field)
    if not geometries:
        return _assemble(source, [], [], pieces, identities, tolerance_m)

    # An arm is one end of one piece: piece i arrives at the node as arm 2i and
    # leaves it as arm 2i+1.
    ends = np.array([coordinate for geometry in geometries for coordinate in (geometry.coords[0], geometry.coords[-1])], dtype=float)
    node_of_arm = cluster_points(ends, tolerance_m)

    partners = _pair_arms(geometries, node_of_arm, identities, rule, stroke_angle_deg, probe_m)
    sequences = _sequences(len(geometries), partners)

    coordinates = [_join(sequence, geometries) for sequence in sequences]
    members = [[piece for piece, _ in sequence] for sequence in sequences]
    return _assemble(source, coordinates, members, pieces, identities, tolerance_m)


def _missing(value: Any) -> bool:
    """Say whether a value is one of the ways a frame writes nothing.

    A frame has several. ``None`` and a float ``nan`` are what an object column
    uses; a column in one of pandas' nullable dtypes writes ``pd.NA``, which is
    neither, and a source that reads its text as ``string`` produces those
    throughout. Missed, ``pd.NA`` survives every check and lands on the chain as
    the literal text ``<NA>`` — which as an identity makes every unnamed line
    the same way as every other unnamed line, and as an attribute fills a column
    that is empty.

    A register with nothing to say also writes an empty string, which is how a
    set of FKB's fields once read as fully populated when they hold 3-6 %. Taken
    for a value it joins the ones beside it, and a chain running from a piece
    that says nothing into a piece that says ``sti`` reads ``" / sti"``.

    Args:
        value: One value out of a column

    Returns:
        Whether it says nothing
    """
    if isinstance(value, str):
        return not value.strip()
    missing = pd.isna(value)
    # Anything that is not a scalar — a list of route numbers, say — answers
    # elementwise, and something present is not missing whatever it holds.
    return bool(missing) if isinstance(missing, bool | np.bool_) else False


def _identity_values(frame: gpd.GeoDataFrame, identity_field: str | None) -> list[frozenset[str]]:
    """Read each row's identities.

    Args:
        frame: Pieces or lines
        identity_field: Column holding them, if the source has one

    Returns:
        One set per row; empty where the source names nothing
    """
    if not identity_field or identity_field not in frame.columns:
        return [frozenset() for _ in range(len(frame))]

    values: list[frozenset[str]] = []
    for value in frame[identity_field]:
        if _missing(value):
            values.append(frozenset())
            continue
        parts = {part.strip() for part in str(value).split(IDENTITY_SEPARATOR)}
        values.append(frozenset(part for part in parts if part))
    return values


def _pair_arms(
    geometries: Sequence[LineString],
    node_of_arm: np.ndarray,
    identities: Sequence[frozenset[str]],
    rule: ChainRule,
    stroke_angle_deg: float,
    probe_m: float,
) -> dict[int, int]:
    """Decide, at every node, which arm continues which.

    Args:
        geometries: The pieces
        node_of_arm: Node each arm meets at
        identities: Identities of each piece
        rule: How a junction is resolved
        stroke_angle_deg: Largest deflection accepted as a continuation
        probe_m: How far either side of a junction a direction is read

    Returns:
        Symmetric mapping of arm to the arm it continues into. An arm absent
        from it ends its chain.
    """
    partners: dict[int, int] = {}
    order = sorted(range(len(node_of_arm)), key=lambda arm: (node_of_arm[arm], arm))

    for _, grouped in groupby(order, key=lambda arm: node_of_arm[arm]):
        arms = list(grouped)
        if len(arms) < 2:
            continue
        if len(arms) == 2:
            # Two arms meeting is not a junction, it is a continuation, whatever
            # the angle. This is what linemerge already does.
            _link(partners, arms[0], arms[1])
            continue
        if rule is ChainRule.JUNCTION:
            continue

        undecided = _pair_by_identity(partners, arms, identities)
        _pair_by_angle(partners, undecided, geometries, stroke_angle_deg, probe_m)
    return partners


def _link(partners: dict[int, int], one: int, other: int) -> None:
    """Record that two arms continue each other.

    Args:
        partners: Mapping being built
        one: One arm
        other: The other
    """
    partners[one] = other
    partners[other] = one


def _pair_by_identity(partners: dict[int, int], arms: Sequence[int], identities: Sequence[frozenset[str]]) -> list[int]:
    """Carry a named or registered way through a junction.

    A crossing is not a branch: where the way arriving reappears in exactly one
    other arm, the chain runs on into it whatever the angle — a hairpin that
    keeps its name is still the same road. Where it reappears in two or more,
    the way itself divides and the chain ends.

    A pairing takes both arms agreeing, and one may not: an arm carrying two
    route names is the single candidate of each of them and the continuation of
    neither, because it divides. The arms it leaves without a partner have no
    identity left to follow, so they fall through to the geometry rather than
    ending on a decision that was never made about them.

    Args:
        partners: Mapping being extended
        arms: Arms meeting at this node
        identities: Identities of each piece

    Returns:
        The arms identity could not decide, left to the geometry
    """
    candidates = {arm: [other for other in arms if other != arm and identities[other // 2] & identities[arm // 2]] for arm in arms}

    undecided: list[int] = []
    for arm in arms:
        found = candidates[arm]
        if len(found) > 1:
            # The way itself divides here, whatever the angles say.
            continue
        if found and len(candidates[found[0]]) == 1:
            _link(partners, arm, found[0])
        else:
            undecided.append(arm)
    return undecided


def _pair_by_angle(
    partners: dict[int, int],
    arms: Sequence[int],
    geometries: Sequence[LineString],
    stroke_angle_deg: float,
    probe_m: float,
) -> None:
    """Pair the arms that continue each other straightest.

    Args:
        partners: Mapping being extended
        arms: Arms still to decide
        geometries: The pieces
        stroke_angle_deg: Largest deflection accepted as a continuation
        probe_m: How far either side of the node a direction is read
    """
    directions = {arm: _direction(geometries[arm // 2], arm % 2, probe_m) for arm in arms}

    candidates = []
    for position, one in enumerate(arms):
        for other in arms[position + 1 :]:
            first, second = directions[one], directions[other]
            if first is None or second is None:
                continue
            # Both directions point away from the node, so two arms continuing
            # each other point in opposite directions: deflection 0.
            deflection = 180.0 - math.degrees(math.acos(min(1.0, max(-1.0, float(np.dot(first, second))))))
            if deflection <= stroke_angle_deg:
                candidates.append((deflection, one, other))

    for _, one, other in sorted(candidates):
        if one not in partners and other not in partners:
            _link(partners, one, other)


def _direction(geometry: LineString, end: int, probe_m: float) -> np.ndarray | None:
    """Read the direction a piece leaves one of its ends in.

    Args:
        geometry: The piece
        end: 0 for its start, 1 for its end
        probe_m: How far along it to look, or its whole length where it is
            shorter than that

    Returns:
        Unit vector in the plane, or None where the piece is too degenerate to
        have one. A source that records a height keeps it on its geometry, and
        a deflection measured through it would not be the angle anyone sees on
        the map, so only the first two dimensions are read.
    """
    coords = np.asarray(geometry.coords, dtype=float)[:, :2]
    if end == 1:
        coords = coords[::-1]

    steps = np.hypot(*np.diff(coords, axis=0).T)
    reach = np.cumsum(steps)
    within = int(np.searchsorted(reach, probe_m))

    if within >= len(steps):
        target = coords[-1]
    else:
        walked = reach[within - 1] if within else 0.0
        share = (probe_m - walked) / steps[within]
        target = coords[within] + share * (coords[within + 1] - coords[within])

    vector = target - coords[0]
    length = float(np.hypot(*vector))
    return vector / length if length > 0 else None


def _sequences(count: int, partners: dict[int, int]) -> list[list[tuple[int, bool]]]:
    """Follow the pairings into runs of pieces.

    Args:
        count: Number of pieces
        partners: Mapping from :func:`_pair_arms`

    Returns:
        One list per chain, of ``(piece, reversed)`` in the order they are walked
    """
    walked: set[int] = set()
    sequences: list[list[tuple[int, bool]]] = []

    # Open chains first, each seeded from a loose end.
    for arm in range(2 * count):
        if arm in partners or arm // 2 in walked:
            continue
        sequences.append(_walk(arm // 2, arm % 2 == 1, partners, walked))

    # What is left has every arm paired, so it closes on itself.
    for piece in range(count):
        if piece not in walked:
            sequences.append(_walk(piece, False, partners, walked))
    return sequences


def _walk(piece: int, reversed_: bool, partners: dict[int, int], walked: set[int]) -> list[tuple[int, bool]]:
    """Follow one chain from a piece to its end.

    Args:
        piece: Piece to start from
        reversed_: Whether it is entered at its end rather than its start
        partners: Mapping from :func:`_pair_arms`
        walked: Pieces already placed in a chain, extended in place

    Returns:
        ``(piece, reversed)`` in the order they are walked
    """
    sequence: list[tuple[int, bool]] = []
    while piece not in walked:
        walked.add(piece)
        sequence.append((piece, reversed_))

        leaving = partners.get(2 * piece + (0 if reversed_ else 1))
        if leaving is None:
            break
        piece, reversed_ = leaving // 2, leaving % 2 == 1
    return sequence


def _join(sequence: Sequence[tuple[int, bool]], geometries: Sequence[LineString]) -> list[Coordinate]:
    """Lay a run of pieces end to end.

    Args:
        sequence: ``(piece, reversed)`` in walking order
        geometries: The pieces

    Returns:
        The chain's coordinates
    """
    coordinates: list[Coordinate] = []
    for piece, reversed_ in sequence:
        coords = list(geometries[piece].coords)
        if reversed_:
            coords.reverse()
        # Pieces meeting at a node hold that node twice, once per piece, and the
        # two copies can differ by a fraction of the node tolerance.
        coordinates.extend(coords[1:] if coordinates else coords)
    return coordinates


def _canonical(coordinates: Sequence[Coordinate], tolerance_m: float) -> list[Coordinate]:
    """Orient a chain so it comes out the same way on every build.

    The direction a chain is walked in depends on which piece the traversal
    happened to start from, and the chain's id is derived from its first point.
    Left alone, an unrelated edit elsewhere would rename half the chains.

    Args:
        coordinates: The chain's coordinates
        tolerance_m: Distance below which two coordinates are the same point

    Returns:
        The same coordinates, possibly reversed and — for a chain that closes on
        itself, which has no ends to compare — cut at its lowest coordinate
    """
    points = list(coordinates)
    if len(points) < 3 or math.dist(points[0], points[-1]) > tolerance_m:
        return points if points[0] <= points[-1] else points[::-1]

    # A ring assembled from several pieces holds two copies of the node it
    # closes at, a fraction of the tolerance apart. Close it exactly.
    points[-1] = points[0]
    ring = points[:-1]
    start = min(range(len(ring)), key=lambda index: ring[index])
    forward = ring[start:] + ring[:start]
    backward = [forward[0], *reversed(forward[1:])]
    return (forward if forward <= backward else backward) + [forward[0]]


def _combine(values: Iterable[object]) -> object:
    """Reduce the values a chain spans to one.

    A chain runs across several source features and their values need not agree.
    Both are true and both are useful, so a run that changes character reads
    ``sti / traktorveg`` rather than picking a side.

    Args:
        values: One value per piece of the chain

    Returns:
        The value where they agree, the sorted values joined where they do not,
        None where there are none
    """
    present = sorted({str(value) for value in values if not _missing(value)})
    if not present:
        return None
    return present[0] if len(present) == 1 else IDENTITY_SEPARATOR.join(present)


def _assemble(
    source: NetworkSource,
    coordinates: Sequence[Sequence[Coordinate]],
    members: Sequence[Sequence[int]],
    pieces: gpd.GeoDataFrame,
    identities: Sequence[frozenset[str]],
    tolerance_m: float,
) -> gpd.GeoDataFrame:
    """Turn runs of pieces into the chain frame.

    Args:
        source: Dataset the pieces came from
        coordinates: Coordinates of each chain
        members: Rows of ``pieces`` each chain is made of
        pieces: Pieces the chains were built from
        identities: Identities of each piece
        tolerance_m: Distance below which two coordinates are the same point

    Returns:
        Chains described by :data:`CHAIN_COLUMNS` and the source's attributes
    """
    columns: dict[str, list[object]] = {name: [] for name in CHAIN_COLUMNS}
    values = {attribute: pieces[attribute].to_numpy() for attribute in source.attributes}
    for attribute in source.attributes:
        columns[attribute] = []

    geometries: list[LineString] = []
    for points, rows in zip(coordinates, members, strict=True):
        geometry = LineString(_canonical(points, tolerance_m))
        geometries.append(geometry)

        columns["source"].append(source.name)
        columns["kind"].append(source.kind)
        columns["length_m"].append(geometry.length)
        columns["identity"].append(_combine(sorted({value for row in rows for value in identities[row]})))
        for attribute in source.attributes:
            columns[attribute].append(_combine(values[attribute][list(rows)]))

    columns["chain_id"] = _chain_ids(source.name, geometries)
    return gpd.GeoDataFrame(columns, geometry=geometries, crs=pieces.crs)


def _chain_ids(source: str, geometries: Sequence[LineString]) -> list[object]:
    """Name each chain after something the geometry owns.

    The id keys the elevation cache, the click highlight and the search, so it
    has to survive a source being re-downloaded unchanged. Position and length
    do; the order chains come out in does not.

    Args:
        source: Source tag, keeping two sources' ids apart
        geometries: The chains, already canonically oriented

    Returns:
        One id per chain
    """
    if not geometries:
        return []

    tag = "".join(character if character.isalnum() else "-" for character in source.lower()).strip("-")
    ids = [f"{tag}-{round(geometry.coords[0][0])}-{round(geometry.coords[0][1])}-{round(geometry.length)}" for geometry in geometries]

    # Two chains can start at one rounded point and run the same rounded
    # distance in different directions — 24 of them in this park's network, all
    # sub-metre scraps. What tells them apart has to be something the geometry
    # owns as well: numbering them in the order they came out would put the
    # traversal order back into the id, which is the one thing it must not carry.
    clashing = {name for name, repeats in Counter(ids).items() if repeats > 1}
    ids = [f"{name}-{_shape_digest(geometry)}" if name in clashing else name for name, geometry in zip(ids, geometries, strict=True)]

    # What still repeats after that is a source holding one line twice, and two
    # copies of one line have nothing left to tell them apart. Numbering them is
    # arbitrary, but it is arbitrary between things that are identical.
    seen: Counter[str] = Counter()
    numbered: list[object] = []
    for name in ids:
        seen[name] += 1
        numbered.append(name if seen[name] == 1 else f"{name}-{seen[name]}")
    return numbered


def _shape_digest(geometry: LineString) -> str:
    """Summarise a line's course as a short, stable string.

    Args:
        geometry: The chain

    Returns:
        Digest of its coordinates rounded to a centimetre
    """
    coordinates = ";".join(f"{x:.2f},{y:.2f}" for x, y, *_ in geometry.coords)
    return hashlib.sha256(coordinates.encode()).hexdigest()[:8]

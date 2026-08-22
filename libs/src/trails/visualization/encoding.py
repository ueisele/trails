"""The routing graph, small enough to put in a page.

The map draws chains as GeoJSON, simplified for rendering. This builds the
**second** representation beside it: the routing graph at full source precision,
which is never drawn. Drawing and routing are different units — that is the
whole point of the chain/edge split — and one copy cannot serve both without
losing either the accuracy or the render budget.

**The table is encoded, not serialised.** Written as JSON the edge table alone
is 1.98 MB and puts the payload over its allowance; delta-encoded it is a
seventh of that. The same holds for the geometry: 948,465 vertices as JSON
coordinate arrays are 22.4 MB, and as zigzag varints over the delta between
consecutive points, gzipped, about a tenth of it.

**Quantised at 1e-6 degrees**, which is 0.11 m — an order of magnitude finer
than the best source in the set, so nothing measurable is lost. Do not coarsen
it to save space: 1e-5 saves 0.7 MB and costs 1.11 m, which is worse than FKB's
own survey accuracy and would undo what the graph was careful about.

**What a route sums, beside its length.** The two derived edge fields ride
in one byte: whether the sources state the ground is waymarked, and whether
none of them records a path along it. Both are summed in kilometres by a
planned route, which is why they are here rather than left in Python, and
the second carries a sentence that has to travel with it — it is ground *no
source records a path along*, which is not ground with no path.

**Three things are deliberately absent.** ``cost``, because it is
``length x source factor`` and the browser has the geometry and the factors —
the ferry crossings are the exception and their flat cost is in the header. The
**per-edge ascent**, whose only consumer is elevation-aware routing, which is
not decided. And the four **per-chain** figures, which belong beside the drawn
chains rather than in here: the map writes them as polylines carrying a
``trail-group-<chain_id>`` class, so a table keyed by that class reaches them —
the same way the search box already ships the text its lines are found by.

**The edges are laid out in chain order**, not in the frame's, because the
frame's order is not the order they lie in — see :mod:`trails.routing.order`.
Laid out that way a chain's edges are one contiguous run, so the link from a
chain to its edges costs one count per chain instead of an index per edge, and
the node columns cost no more: consecutive edges share a node, so one of their
two deltas is zero. Sorting by ``from_node`` was the arrangement first measured,
at 0.27 MB for the two node columns; it needs an index per edge on top to say
which chain the edge lies on, which this arrangement does not.

The binary stream, after gzip and base64, holds the sections of
:data:`STREAM_SECTIONS` in that order. Every count a section needs is either in
the header or in a section before it, so a decoder reads the whole thing with a
single cursor and never has to seek::

    chains        M x (varint length, UTF-8 bytes)   chain ids, in chain order
    chainEdges    M x varint          edges lying on each chain; the rest are connectors
    flags         N x byte            bit 0 runs against its chain, bit 1 begins a new stretch
    nodes         2N x zigzag varint  head against the last edge's tail, then tail against head
    sources       N x byte            index into the header's source table
    derived       N x byte            bits 0-1 index the header's waymarked table, bit 2 no path recorded
    vertexCounts  N x varint          vertices per edge
    coordinates   2V x zigzag varint  longitude and latitude, delta against the vertex before
    sampleCounts  N x varint          height samples per edge; none at all on a crossing
    heights       S x varint          0 where nothing was read, else zigzag(delta) + 1
"""

import base64
import gzip
from collections import Counter
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from trails.routing.coverage import MARKED, UNKNOWN, UNMARKED
from trails.routing.order import CHAIN_ORDER_COLUMNS

#: What the decoder in the page expects. Bump it when the layout changes, so a
#: stale decoder says so rather than reading nonsense confidently.
PAYLOAD_VERSION = 2

#: The coordinate reference system the payload is written in. Degrees rather
#: than the metric CRS the graph is built in, because everything that reads it —
#: Leaflet, a click, a drawn line — speaks longitude and latitude, and the
#: quantisation below is chosen against a degree.
PAYLOAD_EPSG = 4326
PAYLOAD_CRS = f"EPSG:{PAYLOAD_EPSG}"

#: The binary stream, in the order it is written and read.
STREAM_SECTIONS = ("chains", "chainEdges", "flags", "nodes", "sources", "derived", "vertexCounts", "coordinates", "sampleCounts", "heights")

#: What the low two bits of the derived byte mean, in the order the header
#: lists them so that a page reads a name rather than a number. ``None`` is
#: first and is not the same as *unknown*: a crossing and an inferred
#: connector were never asked, where an edge that came back ``unknown`` was
#: asked and no source answered. Collapsing the two would be the same mistake
#: this codebase has made three times already, with ``pd.NA``, with an empty
#: string and with a register writing the word for *nothing* into a name.
WAYMARKED_CODES: tuple[str | None, ...] = (None, UNKNOWN, MARKED, UNMARKED)

#: Bit of the derived byte saying no source records a path along the edge.
NO_PATH_BIT = 0x04

#: How finely a coordinate is written down, in degrees. 1e-6 is 0.11 m of
#: latitude. Every source here is coarser than that by an order of magnitude:
#: FKB is surveyed to a metre or two, N50 is a 1:50,000 product, and UT.no's
#: tracks are consumer GPS.
DEFAULT_COORDINATE_QUANTUM = 1e-6

#: How finely a height is written down, in metres. **This is the resolution the
#: height service answers at, not a choice about accuracy**: 99.87 % of the
#: 1,352,455 readings in this park's store lie exactly on a centimetre and none
#: lies between two, so there is nothing finer to keep and nothing here is
#: rounded away.
#:
#: It used to be a decimetre, on the argument that the model's real vertical
#: uncertainty is around half a metre under forest canopy and a decimetre
#: already asserts more than that. True about the ground, and beside the point:
#: what a *file* must do is agree with itself. A GPX written from this payload
#: states the chain's ascent and carries the heights it was read from, and with
#: the last digit gone the reader recomputing it got a different number — up to
#: 10.5 m, and 9.2 % on a short climb, on 43 % of the chains. Writing the digit
#: we already have costs 0.8 MB and makes every exported file reproduce its own
#: figure exactly.
DEFAULT_ELEVATION_QUANTUM = 0.01

#: What a sample nothing could be read at contributes to the height checksum.
#: The stream marks it with a code of its own; this is only so that a consumer
#: checking its decode has a number to fold in for it.
GAP_CHECKSUM_VALUE = 0x7FFFFFFF

#: Modulus of the two checksum accumulators. Fletcher's shape rather than a
#: cryptographic digest, for one reason: it has to be computed identically in
#: Python over a whole array and in JavaScript one value at a time, and every
#: intermediate has to stay exact in a double. Both accumulators stay under
#: 2**32, and a double holds an integer to 2**53.
_CHECKSUM_MODULUS = 1 << 32

#: Number of seven-bit groups a varint may take. Nine covers everything a
#: 63-bit value can hold, which is more than anything encoded here.
_VARINT_GROUPS = 9


@dataclass(frozen=True)
class Payload:
    """An encoded graph, and what it cost.

    Attributes:
        header: Everything the decoder needs before it starts, JSON-safe
        data: The binary stream, gzipped and base64-encoded
        sections: Bytes each section took before compression, in stream order,
            so a report can say where the payload actually went rather than
            quoting one total
    """

    header: dict[str, Any]
    data: str
    sections: dict[str, int]

    @property
    def size_mb(self) -> float:
        """Megabytes the encoded data adds to a page, the header aside."""
        return len(self.data) / 1e6

    @property
    def raw_mb(self) -> float:
        """Megabytes the binary stream came to before it was compressed."""
        return sum(self.sections.values()) / 1e6


def zigzag(values: np.ndarray) -> np.ndarray:
    """Map signed integers onto unsigned ones, small values staying small.

    A delta is as often negative as positive, and a varint is only short for a
    small *unsigned* number: -1 in two's complement takes ten bytes.

    Args:
        values: Signed integers

    Returns:
        Unsigned integers, ``0, -1, 1, -2, 2`` becoming ``0, 1, 2, 3, 4``
    """
    signed = np.asarray(values, dtype=np.int64)
    return ((signed << np.int64(1)) ^ (signed >> np.int64(63))).astype(np.uint64)


def varints(values: np.ndarray) -> bytes:
    """Write unsigned integers as base-128 varints, seven bits to a byte.

    Written across the whole array at once rather than one value at a time: the
    payload holds some three million of these, and a Python loop over them costs
    more than everything else in the build together.

    Args:
        values: Unsigned integers, each under 2**63

    Returns:
        The concatenated varints

    Raises:
        ValueError: If the values are not whole numbers, or one is negative.
            Both would otherwise be cast into a large unsigned value and written
            out without complaint.
    """
    given = np.asarray(values)
    if not len(given):
        return b""
    if given.dtype.kind not in "iu":
        raise ValueError(f"a varint holds whole numbers, not {given.dtype}")
    if given.dtype.kind == "i" and given.min() < 0:
        raise ValueError(f"a varint holds unsigned values; zigzag a signed one first, smallest was {given.min()}")

    unsigned = given.astype(np.uint64)
    # How many seven-bit groups each value needs: one, plus one for every
    # threshold it reaches.
    thresholds = np.array([1 << (7 * group) for group in range(1, _VARINT_GROUPS)], dtype=np.uint64)
    groups = 1 + np.searchsorted(thresholds, unsigned, side="right").astype(np.int64)

    offsets = np.concatenate(([0], np.cumsum(groups)))
    out = np.zeros(int(offsets[-1]), dtype=np.uint8)
    for group in range(int(groups.max())):
        writing = groups > group
        chunk = ((unsigned[writing] >> np.uint64(7 * group)) & np.uint64(0x7F)).astype(np.uint8)
        # The high bit says another byte follows, so it is set on every group of
        # a value but its last.
        out[offsets[:-1][writing] + group] = chunk | np.where(groups[writing] > group + 1, np.uint8(0x80), np.uint8(0))
    return out.tobytes()


def checksum(values: np.ndarray) -> tuple[int, int]:
    """Summarise a stream of integers in a way a browser can reproduce.

    This is what makes the round trip testable over the *whole* graph rather
    than over a sample. The page cannot compare its decode against the source
    coordinates, because it does not have them; what it can do is fold its own
    decoded values together and say whether the answer is the one the encoder
    got. A decoder correct for 99.9 % of runs has a bug in the long ones, and
    only a check that touches every value finds it.

    Two accumulators rather than one, in Fletcher's arrangement: the second sums
    the first, so it notices two values exchanged where a plain sum would not.

    Args:
        values: The integers as they should decode, signed or not

    Returns:
        The two accumulators, each under 2**32
    """
    # Negative values fold to the same 32-bit pattern JavaScript's `>>> 0` gives
    # them, so the two sides agree about a height below sea level. Flattened
    # first: the page folds one long run of values, and a stream that arrived
    # here shaped would otherwise be counted by its rows.
    folded = (np.asarray(values, dtype=np.int64).reshape(-1) & 0xFFFFFFFF).astype(np.uint64)
    if not len(folded):
        return 1, 0
    # Both cumulative sums stay far under 2**63: three million values under
    # 2**32 come to about 2**54.
    running = np.cumsum(folded) % _CHECKSUM_MODULUS
    return int((running[-1] + 1) % _CHECKSUM_MODULUS), int((int(running.sum()) + len(folded)) % _CHECKSUM_MODULUS)


def encode_graph(
    chains: gpd.GeoDataFrame,
    edges: gpd.GeoDataFrame,
    order: pd.DataFrame,
    *,
    costs: dict[str, dict[str, Any]],
    coordinate_quantum: float = DEFAULT_COORDINATE_QUANTUM,
    elevation_quantum: float = DEFAULT_ELEVATION_QUANTUM,
) -> Payload:
    """Encode the routing graph and its elevation series for a page.

    Args:
        chains: The chains, carrying ``chain_id``. Only their ids travel: what a
            chain is and what it says about itself is already in the page, as
            properties on the line the map draws.
        edges: The graph's edges in :data:`PAYLOAD_CRS`, carrying ``from_node``,
            ``to_node``, ``source``, ``kind``, ``chain_id``, ``waymarked``,
            ``no_path_recorded``, ``elevations`` and their geometry
        order: :data:`~trails.routing.order.CHAIN_ORDER_COLUMNS` per edge, from
            :func:`~trails.routing.order.chain_order`
        costs: What a metre on each source costs a route, by source name, taken
            verbatim into the header. The weighting stays with the caller who
            chose it; this module only carries it across.
        coordinate_quantum: Grid a coordinate is rounded onto, in degrees
        elevation_quantum: Grid a height is rounded onto, in metres

    Returns:
        The payload, ready to be handed to the page

    Raises:
        ValueError: If the edges are not in :data:`PAYLOAD_CRS`, if the order
            does not describe these edges, or if a source has no cost
    """
    if edges.crs is not None and edges.crs.to_epsg() != PAYLOAD_EPSG:
        raise ValueError(f"the payload is written in {PAYLOAD_CRS}, the edges are in {edges.crs}")
    if len(order) != len(edges) or tuple(order.columns) != CHAIN_ORDER_COLUMNS:
        raise ValueError(
            f"the order has to describe these {len(edges):,} edges by {CHAIN_ORDER_COLUMNS}, got {len(order):,} rows of {tuple(order.columns)}"
        )
    # And describe *these* edges rather than a differently ordered frame of the
    # same size. Everything below reads the two by position, so a misalignment
    # would put each edge's neighbour's order on it and raise nothing.
    if not order.index.equals(edges.index):
        raise ValueError("the order is indexed differently from the edges, so the two cannot be read side by side")

    chain_ids = [str(chain_id) for chain_id in chains["chain_id"].tolist()]
    names = _chain_names(edges)
    laid_out = _payload_order(names, order, chain_ids)
    laid, placed = edges.iloc[laid_out], order.iloc[laid_out]
    flipped = placed["flipped"].to_numpy(dtype=bool)
    table, code_of = _source_table(laid, costs)

    coordinates, vertices = _coordinates(laid, coordinate_quantum)
    heights, samples = _heights(laid, elevation_quantum)

    sections = {
        "chains": _strings(chain_ids),
        "chainEdges": varints(_edges_per_chain(names, chain_ids)),
        "flags": (flipped.astype(np.uint8) | (placed["run_start"].to_numpy(dtype=bool).astype(np.uint8) << 1)).tobytes(),
        "nodes": _nodes(laid, flipped),
        "sources": np.array([code_of[name] for name in laid["source"].tolist()], dtype=np.uint8).tobytes(),
        "derived": _derived(laid),
        "vertexCounts": varints(vertices),
        "coordinates": varints(zigzag(np.diff(coordinates, axis=0, prepend=0).reshape(-1))),
        "sampleCounts": varints(samples),
        "heights": varints(_height_codes(heights)),
    }
    stream = b"".join(sections[name] for name in STREAM_SECTIONS)

    ends = np.concatenate([laid["from_node"].to_numpy(dtype=np.int64), laid["to_node"].to_numpy(dtype=np.int64)])
    header = {
        "version": PAYLOAD_VERSION,
        "crs": PAYLOAD_CRS,
        "edges": len(laid),
        "chains": len(chain_ids),
        "nodes": int(ends.max()) + 1 if len(ends) else 0,
        "vertices": int(vertices.sum()),
        "samples": int(samples.sum()),
        "coordinateQuantum": coordinate_quantum,
        "elevationQuantum": elevation_quantum,
        "sources": table,
        "waymarked": list(WAYMARKED_CODES),
        "noPathBit": NO_PATH_BIT,
        # Not decoration: this is what lets a page say whether it decoded every
        # one of two million values correctly, having nothing to compare them
        # against.
        "checksum": {
            "coordinates": checksum(coordinates.reshape(-1)),
            "heights": checksum(np.where(np.isnan(heights), GAP_CHECKSUM_VALUE, heights)),
        },
    }
    # A fixed timestamp, so that two builds of the same graph produce the same
    # page rather than two that differ in a byte nobody chose.
    encoded = base64.b64encode(gzip.compress(stream, compresslevel=9, mtime=0)).decode("ascii")
    return Payload(header=header, data=encoded, sections={name: len(sections[name]) for name in STREAM_SECTIONS})


def _chain_names(edges: gpd.GeoDataFrame) -> list[str | None]:
    """Read the chain each edge lies on, spelled as the payload spells it.

    One reading, used by everything that groups edges by chain. Two readings is
    how a chain and its edges come to disagree about which chain they are: an id
    that is not already a string would stringify on the chain's side and fall
    through as *nothing* on the edge's, and every edge of that chain would be
    filed under the connectors — a scrambled graph rather than a broken one.

    Args:
        edges: The graph's edges, carrying ``chain_id``

    Returns:
        The chain per edge, None for an inferred connector, which lies on none.
        ``pd.isna`` is the test rather than a comparison: a column in a nullable
        dtype holds ``pd.NA``, which is neither None nor a float NaN and which
        ``str()`` happily turns into the text ``<NA>``.
    """
    return [None if pd.isna(chain_id) else str(chain_id) for chain_id in edges["chain_id"].tolist()]


def _payload_order(names: list[str | None], order: pd.DataFrame, chain_ids: list[str]) -> np.ndarray:
    """Lay the edges out chain by chain, each chain's own edges in order.

    Args:
        names: The chain each edge lies on, from :func:`_chain_names`
        order: :data:`~trails.routing.order.CHAIN_ORDER_COLUMNS` per edge
        chain_ids: The chains, in the order the payload lists them

    Returns:
        Positions in the edges: first every chain's edges in the chain's own
        order, then the connectors, which lie on no chain

    Raises:
        ValueError: If an edge names a chain the payload does not carry, or an
            edge that lies on a chain was given no position within it
    """
    rank = {chain_id: position for position, chain_id in enumerate(chain_ids)}
    unknown = {chain_id for chain_id in names if chain_id is not None and chain_id not in rank}
    if unknown:
        raise ValueError(f"{len(unknown):,} edges name a chain the payload does not carry, the first {sorted(unknown)[0]}")

    sequence = order["chain_seq"].to_numpy()
    lost = [position for position, chain_id in enumerate(names) if chain_id is not None and sequence[position] < 0]
    if lost:
        raise ValueError(f"{len(lost):,} edges lie on a chain but were given no position within it, the first at {lost[0]}")

    # A connector belongs to no chain, so it sorts after every chain rather than
    # into one. Their order among themselves does not matter and is left alone.
    def key(position: int) -> tuple[int, int]:
        chain_id = names[position]
        return (len(rank), position) if chain_id is None else (rank[chain_id], int(sequence[position]))

    return np.array(sorted(range(len(names)), key=key), dtype=np.int64)


def _edges_per_chain(names: list[str | None], chain_ids: list[str]) -> np.ndarray:
    """Count what lies on each chain, in the order the payload lists them.

    Args:
        names: The chain each edge lies on, from :func:`_chain_names`
        chain_ids: The chains, in the order the payload lists them

    Returns:
        One count per chain, which may be zero
    """
    counted = Counter(chain_id for chain_id in names if chain_id is not None)
    return np.array([counted[chain_id] for chain_id in chain_ids], dtype=np.uint64)


def _source_table(edges: gpd.GeoDataFrame, costs: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List the datasets the edges came from, and what each costs a route.

    Args:
        edges: The graph's edges, carrying ``source`` and ``kind``
        costs: What a metre on each source costs, by source name

    Returns:
        The table for the header, and the byte code per source name

    Raises:
        ValueError: If a source has no cost, if one carries more than one kind,
            or if there are more sources than a byte holds
    """
    pairs = list(dict.fromkeys(zip(edges["source"].tolist(), edges["kind"].tolist(), strict=True)))
    # A source is named once in the table and its edges point at it by name, so
    # a source appearing under two kinds would write two rows and send every one
    # of its edges to the second — a path read as a crossing, silently, and a
    # crossing is not something a route may be wrong about. Nothing produces
    # that today; every source here carries exactly one kind, and
    # :func:`~trails.network.norway.edge_costs` prices by name alone, which
    # assumes the same thing. Say so rather than encode it.
    two_kinds = sorted({name for name, _ in pairs if sum(name == other for other, _ in pairs) > 1})
    if two_kinds:
        raise ValueError(f"a source is one row of the table and one cost, so it carries one kind; {two_kinds} carry several")
    missing = sorted({name for name, _ in pairs} - set(costs))
    if missing:
        raise ValueError(f"no cost given for {missing}")
    if len(pairs) > 256:
        raise ValueError(f"a source code is one byte and there are {len(pairs)} sources")
    table = [{"name": name, "kind": kind, **costs[name]} for name, kind in pairs]
    return table, {name: position for position, (name, _) in enumerate(pairs)}


def _derived(edges: gpd.GeoDataFrame) -> bytes:
    """Write the two fields a planned route sums, one byte to an edge.

    Args:
        edges: The graph's edges, in payload order, carrying ``waymarked`` and
            ``no_path_recorded``

    Returns:
        One byte per edge: the low two bits index :data:`WAYMARKED_CODES` and
        :data:`NO_PATH_BIT` says no source records a path along it

    Raises:
        ValueError: If ``waymarked`` holds a state the payload cannot name.
            Silently writing it as code 0 would turn an unrecognised answer into
            *never asked*, which is the one distinction this byte exists to keep.
    """
    stated = edges["waymarked"]
    codes = np.zeros(len(edges), dtype=np.uint8)
    named = pd.isna(stated).to_numpy(dtype=bool, copy=True)
    for code, state in enumerate(WAYMARKED_CODES):
        if state is None:
            continue
        matches = (stated == state).fillna(False).to_numpy(dtype=bool)
        codes[matches] = code
        named |= matches
    if not named.all():
        unnamed = sorted({str(value) for value, known in zip(stated.tolist(), named.tolist(), strict=True) if not known})
        raise ValueError(f"the payload names {[state for state in WAYMARKED_CODES if state]}, the edges also say {unnamed}")

    recorded = edges["no_path_recorded"].fillna(False).to_numpy(dtype=bool)
    return (codes | (recorded.astype(np.uint8) * NO_PATH_BIT)).tobytes()


def _strings(values: list[str]) -> bytes:
    """Write strings as their lengths and then their bytes.

    Args:
        values: The strings

    Returns:
        Every length, then every string, so that the lengths compress as the
        run of near-identical small numbers they are
    """
    encoded = [value.encode("utf-8") for value in values]
    return varints(np.array([len(item) for item in encoded], dtype=np.uint64)) + b"".join(encoded)


def _nodes(edges: gpd.GeoDataFrame, flipped: np.ndarray) -> bytes:
    """Write the two node columns as deltas.

    An edge is written by the node it starts at *along its chain* and the one it
    ends at, rather than by ``from_node`` and ``to_node``, because that is what
    makes the first delta zero: consecutive edges of a chain share a node, and
    which of the two columns holds it depends on which way round the edge runs.
    Only nine edges here run against their chain, so the distinction buys almost
    nothing today — but it buys it by construction rather than by luck, and the
    decoder puts the two columns back with the same flag.

    Args:
        edges: The graph's edges, in payload order
        flipped: Whether each of them runs against its chain

    Returns:
        Head and tail, interleaved, as zigzag varints
    """
    from_node = edges["from_node"].to_numpy(dtype=np.int64)
    to_node = edges["to_node"].to_numpy(dtype=np.int64)
    head = np.where(flipped, to_node, from_node)
    tail = np.where(flipped, from_node, to_node)
    deltas = np.stack([head - np.concatenate(([0], tail[:-1])), tail - head], axis=1)
    return varints(zigzag(deltas.reshape(-1)))


def _coordinates(edges: gpd.GeoDataFrame, quantum: float) -> tuple[np.ndarray, np.ndarray]:
    """Quantise every vertex of every edge, in payload order.

    Args:
        edges: The graph's edges, in payload order
        quantum: Grid a coordinate is rounded onto, in degrees

    Returns:
        The vertices as ``(v, 2)`` grid positions, and how many each edge has
    """
    geometries = edges.geometry.to_numpy()
    counts = np.asarray(shapely.get_num_coordinates(geometries), dtype=np.uint64)
    return np.rint(shapely.get_coordinates(geometries) / quantum).astype(np.int64), counts


def _heights(edges: gpd.GeoDataFrame, quantum: float) -> tuple[np.ndarray, np.ndarray]:
    """Quantise every height sample of every edge, in payload order.

    Args:
        edges: The graph's edges, in payload order, carrying ``elevations``
        quantum: Grid a height is rounded onto, in metres

    Returns:
        The samples as grid positions, NaN staying NaN, and how many each edge
        has — none at all on a crossing, which was never sampled
    """
    series = list(edges["elevations"])
    counts = np.array([len(values) for values in series], dtype=np.uint64)
    if not counts.sum():
        return np.empty(0, dtype=float), counts
    return np.rint(np.concatenate([np.asarray(part, dtype=float) for part in series if len(part)]) / quantum), counts


def _height_codes(heights: np.ndarray) -> np.ndarray:
    """Write the height stream so that a gap survives it.

    Where nothing could be read the series holds no number, and it must not
    become one: a profile that fills a gap with the height beside it invents
    ground, and an ascent counted across it invents a climb. So a sample is
    written as ``0`` where nothing was read, and every reading as its distance
    from the reading before it, shifted by one to leave that code free.

    Args:
        heights: Grid positions, NaN where nothing was read

    Returns:
        One code per sample
    """
    codes = np.zeros(len(heights), dtype=np.uint64)
    known = ~np.isnan(heights)
    if not known.any():
        return codes
    # A gap breaks the run of readings but not the chain of deltas: the next
    # reading is written against the last one there was, so a gap costs one byte
    # and no accuracy.
    codes[known] = zigzag(np.diff(heights[known].astype(np.int64), prepend=0)) + np.uint64(1)
    return codes

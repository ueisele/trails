"""Tests for the routing graph the page carries.

The decoder here is a second implementation, written against the same layout as
the one in the page, and it exists so that a round trip can be asserted in a
test rather than only in a browser. It is not a substitute for driving the real
one: two decoders agreeing prove nothing about the third. What connects them is
the checksum — the browser has to reproduce the number this encoder wrote.
"""

import base64
import gzip
import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString
from trails.routing.coverage import MARKED, UNKNOWN, UNMARKED
from trails.routing.order import chain_order
from trails.visualization.encoding import (
    GAP_CHECKSUM_VALUE,
    PAYLOAD_CRS,
    PROTECTED_SHARE_UNITS,
    STREAM_SECTIONS,
    Payload,
    checksum,
    encode_graph,
    varint,
    varints,
    zigzag,
)


def _kind(source: str) -> str:
    """Say what a source's edges are, the way the build names them.

    Args:
        source: Dataset name

    Returns:
        ``ferry``, ``bridge`` or ``path``
    """
    return "ferry" if source == "Ferries" else "bridge" if source == "bridge" else "path"


COSTS = {"FKB": {"factor": 1.05}, "Ferries": {"flatM": 5000.0}, "bridge": {"factor": 1.3}}

#: A protected area, in the shape the header carries one. The outline is carried
#: verbatim and never read by the encoder; what it checks is the id, which is
#: what an edge names its area by.
AREAS = [
    {"id": "VV0001", "name": "Somewhere", "form": "naturreservat", "bounds": [0.0, 0.0, 1.0, 1.0], "rings": [[[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]]},
    {"id": "VV0002", "name": "Elsewhere", "form": "nasjonalpark", "bounds": [1.0, 1.0, 2.0, 2.0], "rings": [[[1.0, 1.0], [2.0, 1.0], [1.0, 1.0]]]},
]


class Cursor:
    """Reads the stream the way the page does, one value at a time."""

    def __init__(self, data: bytes) -> None:
        """Start at the beginning.

        Args:
            data: The inflated stream
        """
        self.data, self.at = data, 0

    def varint(self) -> int:
        """Read one base-128 varint.

        Returns:
            Its value
        """
        value, scale = 0, 1
        while True:
            byte = self.data[self.at]
            self.at += 1
            value += (byte & 0x7F) * scale
            scale *= 128
            if not byte & 0x80:
                return value

    def zigzag(self) -> int:
        """Read one zigzagged varint.

        Returns:
            Its signed value
        """
        value = self.varint()
        return value // 2 if value % 2 == 0 else -(value + 1) // 2

    def take(self, count: int) -> bytes:
        """Read a run of raw bytes.

        Args:
            count: How many

        Returns:
            The bytes
        """
        out = self.data[self.at : self.at + count]
        self.at += count
        return out


def decode(payload: Payload) -> dict[str, object]:
    """Read a payload back, as the page does.

    Args:
        payload: What :func:`encode_graph` produced

    Returns:
        The chains, the edges, their geometry and their heights
    """
    header = payload.header
    cursor = Cursor(gzip.decompress(base64.b64decode(payload.data)))
    edges, count = header["edges"], header["chains"]

    lengths = [cursor.varint() for _ in range(count)]
    chain_ids = [cursor.take(length).decode("utf-8") for length in lengths]
    chain_at = np.cumsum([0, *(cursor.varint() for _ in range(count))])

    flags = cursor.take(edges)
    from_node, to_node, tail = [], [], 0
    for edge in range(edges):
        head = tail + cursor.zigzag()
        tail = head + cursor.zigzag()
        from_node.append(tail if flags[edge] & 1 else head)
        to_node.append(head if flags[edge] & 1 else tail)

    sources = list(cursor.take(edges))
    derived = list(cursor.take(edges))
    protected = []
    for _ in range(edges):
        meets = cursor.varint()
        protected.append([(header["protected"][cursor.take(1)[0]]["id"], cursor.varint() * header["protectedShareQuantum"]) for _ in range(meets)])
    vertex_at = np.cumsum([0, *(cursor.varint() for _ in range(edges))])
    quantum = header["coordinateQuantum"]
    geometries, longitude, latitude = [], 0, 0
    for edge in range(edges):
        points = []
        for _ in range(int(vertex_at[edge + 1] - vertex_at[edge])):
            longitude += cursor.zigzag()
            latitude += cursor.zigzag()
            points.append((longitude * quantum, latitude * quantum))
        geometries.append(points)

    sample_at = np.cumsum([0, *(cursor.varint() for _ in range(edges))])
    heights, height = [], 0
    for edge in range(edges):
        series = []
        for _ in range(int(sample_at[edge + 1] - sample_at[edge])):
            code = cursor.varint()
            if code == 0:
                series.append(math.nan)
                continue
            code -= 1
            height += code // 2 if code % 2 == 0 else -(code + 1) // 2
            series.append(height * header["elevationQuantum"])
        heights.append(series)

    assert cursor.at == len(cursor.data), "the stream held more than the layout accounts for"
    return {
        "chain_ids": chain_ids,
        "chain_at": chain_at,
        "flags": list(flags),
        "from_node": from_node,
        "to_node": to_node,
        "sources": sources,
        "waymarked": [header["waymarked"][code & 0x03] for code in derived],
        "no_path_recorded": [bool(code & header["noPathBit"]) for code in derived],
        "protected": protected,
        "geometries": geometries,
        "heights": heights,
    }


def graph(
    *items: tuple[LineString, object, int, int, str, list[float]],
    waymarked: list[str | None] | None = None,
    no_path: list[bool | None] | None = None,
    protected: list[object] | None = None,
    lengths: list[float] | None = None,
) -> gpd.GeoDataFrame:
    """Build an edge frame from bare parts.

    Args:
        *items: ``(geometry, chain_id, from_node, to_node, source, elevations)``
        waymarked: What the sources state per edge, defaulting the way a real
            build leaves it — asked and nothing stated on a walked edge, and
            never asked on a crossing or a connector
        no_path: Whether no source records a path per edge, defaulting the same
            way
        protected: The areas each edge lies in and its metres in each,
            defaulting to none on a walked edge and never-asked on a crossing
        lengths: What each edge is in metres, defaulting to a hundred. The
            geometry here is in degrees, so a length has to be given rather than
            measured; a real build carries it from the metric CRS it was
            measured in.

    Returns:
        The edges, in the payload's own CRS
    """
    kinds = [_kind(source) for _, _, _, _, source, _ in items]
    return gpd.GeoDataFrame(
        {
            "chain_id": [chain for _, chain, _, _, _, _ in items],
            "from_node": [one for _, _, one, _, _, _ in items],
            "to_node": [other for _, _, _, other, _, _ in items],
            "source": [source for _, _, _, _, source, _ in items],
            "kind": kinds,
            "elevations": [np.asarray(values, dtype=float) for _, _, _, _, _, values in items],
            "waymarked": pd.array(
                waymarked if waymarked is not None else [UNKNOWN if kind == "path" else None for kind in kinds],
                dtype="string",
            ),
            "no_path_recorded": pd.array(
                no_path if no_path is not None else [False if kind == "path" else None for kind in kinds],
                dtype="boolean",
            ),
            "protected": pd.Series(
                protected if protected is not None else [() if kind != "ferry" else None for kind in kinds],
                dtype=object,
            ),
            "length_m": lengths if lengths is not None else [100.0] * len(kinds),
        },
        geometry=[geometry for geometry, _, _, _, _, _ in items],
        crs=PAYLOAD_CRS,
    )


def chains(*items: tuple[LineString, str]) -> gpd.GeoDataFrame:
    """Build a chain frame from bare parts.

    Args:
        *items: ``(geometry, chain_id)`` per chain

    Returns:
        The chains
    """
    return gpd.GeoDataFrame({"chain_id": [chain for _, chain in items]}, geometry=[geometry for geometry, _ in items], crs=PAYLOAD_CRS)


def encoded(chain_frame: gpd.GeoDataFrame, edge_frame: gpd.GeoDataFrame, **kwargs: object) -> Payload:
    """Encode a small graph, working out its edge order first.

    Args:
        chain_frame: The chains
        edge_frame: The edges
        **kwargs: Passed through to :func:`encode_graph`

    Returns:
        The payload
    """
    kwargs.setdefault("areas", AREAS)
    return encode_graph(chain_frame, edge_frame, chain_order(chain_frame, edge_frame), costs=COSTS, **kwargs)  # type: ignore[arg-type]


def test_zigzag_keeps_small_negatives_small() -> None:
    assert zigzag(np.array([0, -1, 1, -2, 2])).tolist() == [0, 1, 2, 3, 4]


def test_a_varint_is_seven_bits_to_a_byte() -> None:
    assert varints(np.array([0, 1, 127, 128, 300], dtype=np.uint64)) == bytes([0, 1, 127, 0x80, 0x01, 0xAC, 0x02])


def test_varints_refuse_a_negative_rather_than_writing_ten_bytes_for_it() -> None:
    with pytest.raises(ValueError, match="zigzag"):
        varints(np.array([-1], dtype=np.int64))


def test_varints_refuse_something_that_is_not_a_whole_number() -> None:
    # Cast rather than refused, 2.7 would be written as 2 and -1.0 as 2**64 - 1.
    with pytest.raises(ValueError, match="whole numbers"):
        varints(np.array([2.7]))


def test_the_checksum_notices_two_values_exchanged() -> None:
    # A plain sum would not, and two values exchanged is exactly what a decoder
    # reading a stream one value out of step produces.
    assert checksum(np.array([3, 7, 11])) != checksum(np.array([3, 11, 7]))


def test_the_checksum_of_nothing_is_where_a_reader_starts() -> None:
    assert checksum(np.array([], dtype=np.int64)) == (1, 0)


def test_a_height_below_sea_level_checksums_the_way_a_browser_folds_it() -> None:
    # -4,390 centimetres is a real reading here: an N50 road descending into a
    # quarry. Python and JavaScript have to agree about its 32-bit pattern.
    assert checksum(np.array([-439])) == ((1 + (-439 & 0xFFFFFFFF)) % (1 << 32), (1 + (-439 & 0xFFFFFFFF)) % (1 << 32))


def test_every_coordinate_comes_back_within_the_quantisation() -> None:
    line = LineString([(13.0, 65.6), (13.000_001_4, 65.600_000_6), (13.1234567, 65.7654321)])
    payload = encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, 11.0])))

    read = decode(payload)["geometries"][0]  # type: ignore[index]
    for (want_x, want_y), (got_x, got_y) in zip(line.coords, read, strict=True):
        assert abs(want_x - got_x) <= 0.5e-6
        assert abs(want_y - got_y) <= 0.5e-6


def test_the_stream_says_how_many_of_everything_there_are() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    payload = encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, 15.0, 20.0])))

    assert payload.header["edges"] == 1
    assert payload.header["chains"] == 1
    assert payload.header["nodes"] == 2
    assert payload.header["vertices"] == 2
    assert payload.header["samples"] == 3
    assert set(payload.sections) == set(STREAM_SECTIONS)


def test_a_chain_s_edges_come_back_in_order_however_the_frame_held_them() -> None:
    # The order is the whole point: every sample of a scrambled chain is still
    # present and still correct, so nothing but this notices.
    chain = LineString([(13.0, 65.6), (13.002, 65.6)])
    edges = graph(
        (LineString([(13.001, 65.6), (13.002, 65.6)]), "a", 1, 2, "FKB", [20.0, 30.0]),
        (LineString([(13.0, 65.6), (13.001, 65.6)]), "a", 0, 1, "FKB", [10.0, 20.0]),
    )
    read = decode(encoded(chains((chain, "a")), edges))

    assert read["chain_at"].tolist() == [0, 2]  # type: ignore[union-attr]
    assert read["heights"] == [[10.0, 20.0], [20.0, 30.0]]
    assert read["from_node"] == [0, 1]


def test_a_chain_walked_against_its_own_direction_comes_back_flagged() -> None:
    chain = LineString([(13.0, 65.6), (13.002, 65.6)])
    edges = graph(
        (LineString([(13.002, 65.6), (13.001, 65.6)]), "a", 2, 1, "FKB", [30.0, 20.0]),
        (LineString([(13.001, 65.6), (13.0, 65.6)]), "a", 1, 0, "FKB", [20.0, 10.0]),
    )
    read = decode(encoded(chains((chain, "a")), edges))

    # Both run against the chain, and the flag says so; the geometry itself is
    # left exactly as the source drew it.
    assert [flag & 1 for flag in read["flags"]] == [1, 1]  # type: ignore[union-attr]
    assert read["from_node"] == [1, 2]
    assert read["heights"] == [[20.0, 10.0], [30.0, 20.0]]


def test_a_gap_stays_a_gap() -> None:
    # Over water and outside the height model's coverage nothing was read, and
    # a profile that fills that in invents ground.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    payload = encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, math.nan, 12.5])))

    series = decode(payload)["heights"][0]  # type: ignore[index]
    assert series[0] == pytest.approx(10.0)
    assert math.isnan(series[1])
    assert series[2] == pytest.approx(12.5)


def test_a_crossing_carries_no_heights_at_all() -> None:
    line = LineString([(13.0, 65.6), (13.05, 65.65)])
    payload = encoded(chains((line, "f")), graph((line, "f", 0, 1, "Ferries", [])))

    assert payload.header["samples"] == 0
    assert decode(payload)["heights"] == [[]]


def test_a_connector_lies_on_no_chain_and_sorts_after_every_one() -> None:
    chain = LineString([(13.0, 65.6), (13.001, 65.6)])
    edges = graph(
        (LineString([(13.001, 65.6), (13.001, 65.6005)]), None, 1, 2, "bridge", [10.0, 11.0]),
        (chain, "a", 0, 1, "FKB", [10.0, 10.0]),
    )
    read = decode(encoded(chains((chain, "a")), edges))

    assert read["chain_at"].tolist() == [0, 1]  # type: ignore[union-attr]
    assert read["sources"] == [0, 1]
    assert read["from_node"] == [0, 1]


def test_the_source_table_says_what_a_route_costs_and_the_edges_only_name_it() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.6)])
    crossing = LineString([(13.0, 65.7), (13.05, 65.75)])
    payload = encoded(
        chains((line, "a"), (crossing, "f")),
        graph((line, "a", 0, 1, "FKB", [10.0, 10.0]), (crossing, "f", 2, 3, "Ferries", [])),
    )

    assert payload.header["sources"] == [
        {"name": "FKB", "kind": "path", "factor": 1.05},
        {"name": "Ferries", "kind": "ferry", "flatM": 5000.0},
    ]
    # And no cost anywhere on an edge: it is length times a factor, and the
    # length is in the geometry already.
    assert "cost" not in payload.header


def test_the_checksums_are_over_what_the_page_should_decode() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    payload = encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, math.nan])))

    assert payload.header["checksum"]["coordinates"] == checksum(np.array([13_000_000, 65_600_000, 13_001_000, 65_601_000]))
    # 10.0 m on the centimetre grid the height service answers at, which is
    # what the payload carries.
    assert payload.header["checksum"]["heights"] == checksum(np.array([1_000, GAP_CHECKSUM_VALUE]))


def test_two_encodings_of_one_graph_are_the_same_bytes() -> None:
    # gzip writes a timestamp unless told not to, and a page that differs
    # between builds cannot be compared between builds.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    arguments = (chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, 11.0])))

    assert encoded(*arguments).data == encoded(*arguments).data


def test_edges_in_the_wrong_crs_are_refused() -> None:
    # The graph is built in a metric CRS and the payload is written in degrees.
    # Encoding the metric one would quantise metres onto a grid of 1e-6.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    metric = graph((line, "a", 0, 1, "FKB", [10.0, 11.0])).to_crs("EPSG:25833")
    metric_chains = chains((line, "a")).to_crs("EPSG:25833")

    with pytest.raises(ValueError, match="EPSG:4326"):
        encode_graph(metric_chains, metric, chain_order(metric_chains, metric), costs=COSTS, areas=AREAS)


def test_a_source_with_no_cost_is_refused() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, "a", 0, 1, "OSM", [10.0, 11.0]))

    with pytest.raises(ValueError, match="no cost given"):
        encoded(chains((line, "a")), edges)


def test_a_source_carrying_two_kinds_is_refused_rather_than_filed_under_the_last() -> None:
    # The table has a row per (source, kind) and an edge points at it by source
    # alone, so a source under two kinds would send every one of its edges to
    # whichever came last — a path read as a crossing, and nothing raised.
    one = LineString([(13.0, 65.6), (13.001, 65.601)])
    other = LineString([(13.0, 65.7), (13.05, 65.75)])
    edges = graph((one, "a", 0, 1, "FKB", [10.0, 11.0]), (other, "b", 2, 3, "FKB", []))
    edges.loc[edges.index[1], "kind"] = "ferry"

    with pytest.raises(ValueError, match="one kind"):
        encoded(chains((one, "a"), (other, "b")), edges)


def test_an_order_that_does_not_describe_these_edges_is_refused() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    frame = graph((line, "a", 0, 1, "FKB", [10.0, 11.0]))
    chain_frame = chains((line, "a"))

    with pytest.raises(ValueError, match="describe"):
        encode_graph(chain_frame, frame, chain_order(chain_frame, frame).iloc[:0], costs=COSTS, areas=AREAS)


def test_an_order_belonging_to_a_differently_indexed_frame_is_refused() -> None:
    # The right length and the right columns, read alongside the edges by
    # position. Left to itself it puts each edge's neighbour's order on it.
    chain = LineString([(13.0, 65.6), (13.002, 65.6)])
    edges = graph(
        (LineString([(13.0, 65.6), (13.001, 65.6)]), "a", 0, 1, "FKB", [10.0, 20.0]),
        (LineString([(13.001, 65.6), (13.002, 65.6)]), "a", 1, 2, "FKB", [20.0, 30.0]),
    )
    chain_frame = chains((chain, "a"))
    order = chain_order(chain_frame, edges).set_axis([7, 9])

    with pytest.raises(ValueError, match="indexed differently"):
        encode_graph(chain_frame, edges, order, costs=COSTS, areas=AREAS)


def test_a_chain_id_that_is_not_already_a_string_still_finds_its_chain() -> None:
    # The chain and its edges are read by two different pieces of code. Reading
    # the id one way on the chain and another on the edge files every edge of
    # that chain under the connectors and raises nothing at all — a scrambled
    # graph rather than a broken one, which is the failure this phase is most
    # exposed to.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, np.int64(7), 0, 1, "FKB", [10.0, 11.0]))
    chain_frame = chains((line, np.int64(7)))  # type: ignore[arg-type]
    read = decode(encode_graph(chain_frame, edges, chain_order(chain_frame, edges), costs=COSTS, areas=AREAS))

    assert read["chain_ids"] == ["7"]
    assert read["chain_at"].tolist() == [0, 1]  # type: ignore[union-attr]


def test_an_edge_naming_a_chain_the_payload_does_not_carry_is_refused() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    frame = graph((line, "b", 0, 1, "FKB", [10.0, 11.0]))

    with pytest.raises(ValueError, match="does not carry"):
        encode_graph(chains((line, "a")), frame, chain_order(chains((line, "a")), frame), costs=COSTS, areas=AREAS)


def test_an_empty_graph_encodes_to_an_empty_graph() -> None:
    payload = encoded(chains(), graph())

    assert payload.header["edges"] == 0
    assert payload.header["vertices"] == 0
    assert payload.header["nodes"] == 0
    assert decode(payload)["geometries"] == []


def test_the_derived_byte_carries_what_a_route_sums() -> None:
    one = LineString([(13.0, 65.6), (13.001, 65.601)])
    other = LineString([(13.001, 65.601), (13.002, 65.602)])
    read = decode(
        encoded(
            chains((one, "a"), (other, "b")),
            graph(
                (one, "a", 0, 1, "FKB", [10.0, 11.0]),
                (other, "b", 1, 2, "FKB", [11.0, 12.0]),
                waymarked=[MARKED, UNMARKED],
                no_path=[False, True],
            ),
        )
    )

    assert read["waymarked"] == [MARKED, UNMARKED]
    assert read["no_path_recorded"] == [False, True]


def test_never_asked_is_not_the_same_as_nothing_stated() -> None:
    # A crossing was never asked either question; a walked edge that came back
    # "unknown" was asked and no source answered. Summed together they would say
    # a ferry is ground of unknown marking.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    crossing = LineString([(13.0, 65.7), (13.05, 65.75)])
    read = decode(
        encoded(
            chains((line, "a"), (crossing, "f")),
            graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), (crossing, "f", 2, 3, "Ferries", [])),
        )
    )

    assert read["waymarked"] == [UNKNOWN, None]
    assert read["no_path_recorded"] == [False, False]


def test_a_marking_state_the_payload_cannot_name_is_refused() -> None:
    # Writing it as code 0 would file it under "never asked", which is the one
    # distinction the byte exists to keep.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), waymarked=["signposted"])

    with pytest.raises(ValueError, match="signposted"):
        encoded(chains((line, "a")), edges)


def test_the_scalar_varint_writes_what_the_array_one_writes() -> None:
    # One section interleaves single numbers with single bytes and cannot be
    # written column by column. A stream written by one writer and read as if
    # written by the other is unrecoverable, so the two are pinned together.
    for value in (0, 1, 127, 128, 300, 16_383, 16_384, 1 << 20, 1 << 40):
        assert varint(value) == varints(np.array([value], dtype=np.uint64))


def test_a_scalar_varint_refuses_a_negative() -> None:
    with pytest.raises(ValueError, match="zigzag"):
        varint(-1)


def test_an_edge_inside_an_area_carries_its_share_of_it() -> None:
    # A share and not a length: Python measures those metres in the projection
    # the graph is built in and the page measures its own from the ellipsoid, so
    # a route lying wholly inside one area would otherwise state more ground
    # inside it than it walked altogether.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), protected=[(("VV0002", 40.0),)], lengths=[100.0])
    read = decode(encoded(chains((line, "a")), edges))

    assert read["protected"] == [[("VV0002", pytest.approx(0.4))]]


def test_an_edge_in_two_areas_carries_both_in_the_table_s_own_order() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), protected=[(("VV0002", 25.0), ("VV0001", 100.0))], lengths=[100.0])
    read = decode(encoded(chains((line, "a")), edges))

    assert read["protected"] == [[("VV0001", pytest.approx(1.0)), ("VV0002", pytest.approx(0.25))]]


def test_an_edge_in_nothing_costs_one_byte() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    payload = encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, 11.0])))

    assert payload.sections["protected"] == 1
    assert decode(payload)["protected"] == [[]]


def test_a_crossing_is_written_as_lying_in_nothing() -> None:
    # It means something else — a ferry was never asked — and nothing in the
    # page may read this section for one. The kind is what tells them apart.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    crossing = LineString([(13.0, 65.7), (13.05, 65.75)])
    payload = encoded(
        chains((line, "a"), (crossing, "f")),
        graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), (crossing, "f", 2, 3, "Ferries", [])),
    )

    assert decode(payload)["protected"] == [[], []]


def test_a_walked_edge_that_was_never_measured_is_refused() -> None:
    # Travelling as a zero it would read as an answer.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), protected=[None])

    with pytest.raises(ValueError, match="never measured"):
        encoded(chains((line, "a")), edges)


def test_a_crossing_that_was_measured_is_refused() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    crossing = LineString([(13.0, 65.7), (13.05, 65.75)])
    edges = graph(
        (line, "a", 0, 1, "FKB", [10.0, 11.0]),
        (crossing, "f", 2, 3, "Ferries", []),
        protected=[(), (("VV0001", 10.0),)],
    )

    with pytest.raises(ValueError, match="carries 1 protected"):
        encoded(chains((line, "a"), (crossing, "f")), edges)


def test_an_edge_naming_an_area_the_table_does_not_carry_is_refused() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), protected=[(("VV9999", 10.0),)])

    with pytest.raises(ValueError, match="VV9999"):
        encoded(chains((line, "a")), edges)


def test_more_of_an_edge_inside_an_area_than_the_edge_is_long_is_refused() -> None:
    # Not a rounding: it is an edge measured against a boundary in one CRS and a
    # length taken in another, and the share would travel as a plausible number.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    edges = graph((line, "a", 0, 1, "FKB", [10.0, 11.0]), protected=[(("VV0001", 120.0),)], lengths=[100.0])

    with pytest.raises(ValueError, match="100.000 m long and 120.000"):
        encoded(chains((line, "a")), edges)


def test_the_areas_travel_in_the_header_with_their_outlines() -> None:
    # One list, so a code on an edge and a polygon the page tests a click
    # against cannot come to mean two different areas.
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    header = encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, 11.0]))).header

    assert [area["id"] for area in header["protected"]] == ["VV0001", "VV0002"]
    assert header["protected"][0]["rings"] == AREAS[0]["rings"]
    assert header["protectedShareQuantum"] == pytest.approx(1.0 / PROTECTED_SHARE_UNITS)


def test_an_area_short_of_a_field_the_page_needs_is_refused() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    incomplete = [{"id": "VV0001", "name": "Somewhere", "form": "naturreservat"}]

    with pytest.raises(ValueError, match="short of bounds, rings"):
        encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, 11.0])), areas=incomplete)


def test_two_areas_with_one_id_are_refused() -> None:
    line = LineString([(13.0, 65.6), (13.001, 65.601)])
    twice = [AREAS[0], dict(AREAS[1], id="VV0001")]

    with pytest.raises(ValueError, match="more than once"):
        encoded(chains((line, "a")), graph((line, "a", 0, 1, "FKB", [10.0, 11.0])), areas=twice)

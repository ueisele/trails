"""Tests for putting a chain's edges back into the order they lie in."""

import geopandas as gpd
from shapely.geometry import LineString
from trails.routing.order import CHAIN_ORDER_COLUMNS, chain_order

CRS = "EPSG:25833"


def edges(*items: tuple[LineString, object, int, int]) -> gpd.GeoDataFrame:
    """Build an edge frame from bare parts.

    Args:
        *items: ``(geometry, chain_id, from_node, to_node)`` per edge

    Returns:
        The edges, carrying what the ordering reads
    """
    return gpd.GeoDataFrame(
        {
            "chain_id": [chain for _, chain, _, _ in items],
            "from_node": [one for _, _, one, _ in items],
            "to_node": [other for _, _, _, other in items],
        },
        geometry=[geometry for geometry, _, _, _ in items],
        crs=CRS,
    )


def chains(*items: tuple[LineString, str]) -> gpd.GeoDataFrame:
    """Build a chain frame from bare parts.

    Args:
        *items: ``(geometry, chain_id)`` per chain

    Returns:
        The chains
    """
    return gpd.GeoDataFrame({"chain_id": [chain for _, chain in items]}, geometry=[geometry for geometry, _ in items], crs=CRS)


def test_it_reports_the_three_columns_for_every_edge() -> None:
    frame = edges((LineString([(0, 0), (10, 0)]), "a", 0, 1))
    order = chain_order(chains((LineString([(0, 0), (10, 0)]), "a")), frame)

    assert tuple(order.columns) == CHAIN_ORDER_COLUMNS
    assert list(order.index) == list(frame.index)


def test_a_chain_whose_edges_arrive_shuffled_comes_back_in_order() -> None:
    # The frame order is what the build happened to produce; the bridging pass
    # moves every edge it splits to the end of it, so this is the normal case
    # rather than a contrived one.
    frame = edges(
        (LineString([(20, 0), (30, 0)]), "a", 2, 3),
        (LineString([(0, 0), (10, 0)]), "a", 0, 1),
        (LineString([(10, 0), (20, 0)]), "a", 1, 2),
    )
    order = chain_order(chains((LineString([(0, 0), (30, 0)]), "a")), frame)

    assert order["chain_seq"].tolist() == [2, 0, 1]
    assert order["flipped"].tolist() == [False, False, False]
    assert order["run_start"].tolist() == [False, True, False]


def test_the_order_runs_the_chain_s_way_and_not_the_walk_s() -> None:
    # The walk reaches this chain's far end first and comes back along it right
    # to left. The chain runs left to right and its ascent was read that way, so
    # the run turns round whole — the order and every edge in it. A series laid
    # out the walk's way would report the chain's descent as its ascent.
    frame = edges(
        (LineString([(20, 0), (10, 0)]), "a", 2, 1),
        (LineString([(10, 0), (0, 0)]), "a", 1, 0),
    )
    order = chain_order(chains((LineString([(0, 0), (20, 0)]), "a")), frame)

    assert order["chain_seq"].tolist() == [1, 0]
    assert order["flipped"].tolist() == [True, True]


def test_an_edge_that_runs_against_its_chain_is_marked() -> None:
    frame = edges(
        (LineString([(0, 0), (10, 0)]), "a", 0, 1),
        (LineString([(20, 0), (10, 0)]), "a", 2, 1),
    )
    order = chain_order(chains((LineString([(0, 0), (20, 0)]), "a")), frame)

    assert order["chain_seq"].tolist() == [0, 1]
    assert order["flipped"].tolist() == [False, True]


def test_a_stretch_the_walk_cannot_reach_starts_again_rather_than_joining() -> None:
    # Two pieces of one chain with nothing between them. Laid end to end they
    # would report a climb over ground nobody measured.
    frame = edges(
        (LineString([(0, 0), (10, 0)]), "a", 0, 1),
        (LineString([(50, 0), (60, 0)]), "a", 5, 6),
    )
    order = chain_order(chains((LineString([(0, 0), (60, 0)]), "a")), frame)

    assert order["chain_seq"].tolist() == [0, 1]
    assert order["run_start"].tolist() == [True, True]


def test_a_ring_comes_back_as_one_run() -> None:
    ring = LineString([(0, 0), (10, 0), (10, 10), (0, 0)])
    frame = edges(
        (LineString([(0, 0), (10, 0)]), "a", 0, 1),
        (LineString([(10, 0), (10, 10)]), "a", 1, 2),
        (LineString([(10, 10), (0, 0)]), "a", 2, 0),
    )
    order = chain_order(chains((ring, "a")), frame)

    assert sorted(order["chain_seq"].tolist()) == [0, 1, 2]
    assert order["run_start"].sum() == 1


def test_a_connector_lies_on_no_chain_and_has_no_position() -> None:
    frame = edges(
        (LineString([(0, 0), (10, 0)]), "a", 0, 1),
        (LineString([(10, 0), (10, 3)]), None, 1, 9),
    )
    order = chain_order(chains((LineString([(0, 0), (10, 0)]), "a")), frame)

    assert order["chain_seq"].tolist() == [0, -1]
    assert order["run_start"].tolist() == [True, False]


def test_chains_do_not_borrow_each_other_s_edges() -> None:
    frame = edges(
        (LineString([(0, 0), (10, 0)]), "a", 0, 1),
        (LineString([(10, 0), (20, 0)]), "b", 1, 2),
    )
    order = chain_order(chains((LineString([(0, 0), (10, 0)]), "a"), (LineString([(10, 0), (20, 0)]), "b")), frame)

    assert order["chain_seq"].tolist() == [0, 0]


def test_a_chain_with_no_edges_left_is_not_an_error() -> None:
    frame = edges((LineString([(0, 0), (10, 0)]), "a", 0, 1))
    order = chain_order(chains((LineString([(0, 0), (10, 0)]), "a"), (LineString([(0, 5), (10, 5)]), "b")), frame)

    assert order["chain_seq"].tolist() == [0]


def test_no_edges_at_all_is_not_an_error() -> None:
    frame = edges()
    order = chain_order(chains(), frame)

    assert order.empty
    assert tuple(order.columns) == CHAIN_ORDER_COLUMNS

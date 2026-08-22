"""Tests for the dense, height-carrying line an export writes.

The rule these exist to hold: **every vertex the chain has, every sample the
height model gave, and a point wherever two of those are still further apart
than 5 m.** Resampling every 5 m instead drops the source's own vertices and
rounds off every corner between two samples; keeping the vertices alone and
interpolating between them loses the readings, and with them the ascent the file
states about itself. Both read as the same thing on a chart and neither is the
same track.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString, MultiLineString
from trails.routing.elevation import ascent
from trails.routing.order import chain_order
from trails.routing.track import DEFAULT_GAP_M, chain_tracks

#: Metric, so a metre in the fixtures is a metre in the assertions.
CRS = "EPSG:25833"


def edges(*items: tuple[LineString, object, int, int, list[float] | None]) -> gpd.GeoDataFrame:
    """Build an edge frame from bare parts.

    Args:
        *items: ``(geometry, chain_id, from_node, to_node, heights)`` per edge

    Returns:
        The edges, carrying what the track composition reads
    """
    return gpd.GeoDataFrame(
        {
            "chain_id": [chain for _, chain, _, _, _ in items],
            "from_node": [one for _, _, one, _, _ in items],
            "to_node": [other for _, _, _, other, _ in items],
            "elevations": [None if heights is None else np.array(heights, dtype=float) for *_, heights in items],
        },
        geometry=[geometry for geometry, _, _, _, _ in items],
        crs=CRS,
    )


def chains(*items: tuple[LineString, str]) -> gpd.GeoDataFrame:
    """Build a chain frame from bare parts.

    Args:
        *items: ``(geometry, chain_id)`` per chain

    Returns:
        The chains, carrying the length they say they are
    """
    return gpd.GeoDataFrame(
        {"chain_id": [chain for _, chain in items], "length_m": [geometry.length for geometry, _ in items]},
        geometry=[geometry for geometry, _ in items],
        crs=CRS,
    )


def laid(chain: gpd.GeoDataFrame, edge: gpd.GeoDataFrame, **kwargs: object) -> gpd.GeoSeries:
    """Compose the tracks of a fixture, in its own CRS.

    Args:
        chain: The chains
        edge: Their edges
        **kwargs: Passed to :func:`~trails.routing.track.chain_tracks`

    Returns:
        One track per chain, in :data:`CRS` so a metre reads as a metre
    """
    return chain_tracks(chain, edge, chain_order(chain, edge), crs=CRS, **kwargs)  # type: ignore[arg-type]


def points(track: LineString | MultiLineString) -> np.ndarray:
    """Every coordinate of a track, x, y and height.

    Args:
        track: One composed track

    Returns:
        ``(n, 3)``
    """
    return shapely.get_coordinates(track, include_z=True)


def test_a_line_shorter_than_the_gap_keeps_its_own_two_points() -> None:
    track = laid(
        chains((LineString([(0, 0), (4, 0)]), "a")),
        edges((LineString([(0, 0), (4, 0)]), "a", 0, 1, [10.0, 14.0])),
    ).iloc[0]

    assert points(track)[:, :2].tolist() == [[0.0, 0.0], [4.0, 0.0]]


def test_a_gap_of_exactly_the_step_is_not_a_gap_that_exceeds_it() -> None:
    # 5.000 m does not exceed 5 m, and a rule written the other way puts a point
    # into the middle of every FKB segment that happens to land on the number.
    track = laid(
        chains((LineString([(0, 0), (5, 0)]), "a")),
        edges((LineString([(0, 0), (5, 0)]), "a", 0, 1, [10.0, 15.0])),
    ).iloc[0]

    assert len(points(track)) == 2


def test_a_long_leg_is_filled_so_no_step_is_wider_than_the_gap() -> None:
    track = laid(
        chains((LineString([(0, 0), (17, 0)]), "a")),
        edges((LineString([(0, 0), (17, 0)]), "a", 0, 1, [0.0, 17.0])),
    ).iloc[0]
    laid_out = points(track)
    steps = np.hypot(*(np.diff(laid_out[:, :2], axis=0).T))

    # Four intervals of 4.25 m rather than three of 5 and one of 2: an even
    # spread, and every one of them at or under the gap.
    assert len(laid_out) == 5
    assert steps.max() <= DEFAULT_GAP_M + 1e-9
    assert np.allclose(steps, 4.25)


def test_every_vertex_survives_the_fill_exactly() -> None:
    # The whole reason not to resample: a corner the surveyor recorded has to
    # come out at the coordinate they recorded it at, not near it.
    corner = LineString([(0, 0), (20, 0), (20, 7)])
    track = laid(chains((corner, "a")), edges((corner, "a", 0, 1, [0.0, 10.0, 20.0]))).iloc[0]
    laid_out = points(track)[:, :2]

    for vertex in corner.coords:
        assert any(np.allclose(vertex, position) for position in laid_out)
    assert laid_out[0].tolist() == [0.0, 0.0]
    assert laid_out[-1].tolist() == [20.0, 7.0]


def test_every_sample_lands_in_the_track_as_the_reading_it_is() -> None:
    # Not interpolated between its neighbours: the ascent stated in a file has
    # to be readable off the file's own values, and the vertices alone lost 47 m
    # of the 42 km Rundtur's 1,722.
    line = LineString([(0, 0), (40, 0)])
    heights = [0.0, 12.0, 3.0, 15.0, 6.0]
    track = laid(chains((line, "a")), edges((line, "a", 0, 1, heights))).iloc[0]
    laid_out = points(track)

    for at, height in zip(np.linspace(0.0, 40.0, len(heights)), heights, strict=True):
        landed = np.isclose(laid_out[:, 0], at)
        assert landed.any()
        assert laid_out[landed, 2][0] == height


def test_the_ascent_read_back_off_the_track_is_the_ascent_of_the_samples() -> None:
    # What check 5 of the phase asks of a real chain, held here against a
    # fixture: a file whose points do not reproduce the number printed in it is
    # a file that has to be believed rather than read.
    line = LineString([(0, 0), (60, 0)])
    heights = [100.0, 130.0, 110.0, 145.0, 120.0, 160.0, 150.0]
    track = laid(chains((line, "a")), edges((line, "a", 0, 1, heights))).iloc[0]

    assert ascent(points(track)[:, 2], threshold_m=5.0) == ascent(np.array(heights), threshold_m=5.0)


def test_a_height_is_read_off_the_samples_rather_than_off_the_vertices() -> None:
    # The samples lie every 5 m along the edge and the vertices lie where the
    # surveyor turned. A point half way between two samples takes half their
    # difference, whatever the vertices happen to be doing.
    line = LineString([(0, 0), (20, 0)])
    track = laid(chains((line, "a")), edges((line, "a", 0, 1, [0.0, 10.0, 20.0, 30.0, 40.0]))).iloc[0]
    laid_out = points(track)

    assert np.allclose(laid_out[:, 0] * 2.0, laid_out[:, 2])


def test_a_stretch_the_model_never_answered_for_carries_no_height() -> None:
    # NaN and not zero, and not the height of the sample beside it: a height
    # interpolated across a gap is invented ground, and nothing downstream can
    # tell an invented one from a read one.
    line = LineString([(0, 0), (20, 0)])
    track = laid(chains((line, "a")), edges((line, "a", 0, 1, [0.0, 10.0, np.nan, 30.0, 40.0]))).iloc[0]
    laid_out = points(track)

    between = (laid_out[:, 0] > 5.0) & (laid_out[:, 0] < 15.0)
    assert np.isnan(laid_out[between, 2]).all()
    assert not np.isnan(laid_out[laid_out[:, 0] <= 5.0, 2]).any()


def test_a_chain_nothing_was_read_along_is_neither_filled_nor_heighted() -> None:
    # A ferry crossing. The fill exists to carry heights, and a point every 5 m
    # across a fjord says nothing its two ends do not already say — 29,414 of
    # them over this park's crossings.
    crossing = LineString([(0, 0), (3000, 0)])
    track = laid(chains((crossing, "x")), edges((crossing, "x", 0, 1, None))).iloc[0]
    laid_out = points(track)

    assert len(laid_out) == 2
    assert np.isnan(laid_out[:, 2]).all()


def test_the_node_two_edges_share_is_laid_down_once() -> None:
    # Both edges sample it and both draw it, and a track holding it twice is a
    # track with a zero-length step in it.
    track = laid(
        chains((LineString([(0, 0), (16, 0)]), "a")),
        edges(
            (LineString([(0, 0), (8, 0)]), "a", 0, 1, [0.0, 8.0]),
            (LineString([(8, 0), (16, 0)]), "a", 1, 2, [8.0, 16.0]),
        ),
    ).iloc[0]
    laid_out = points(track)
    steps = np.hypot(*(np.diff(laid_out[:, :2], axis=0).T))

    assert (steps > 0).all()
    assert np.allclose(laid_out[:, 0], laid_out[:, 2])


def test_an_edge_running_against_its_chain_is_turned_round_with_its_heights() -> None:
    # 9 edges in this park run against the chain they lie on. A series laid out
    # the wrong way reports the chain's descent as its ascent, and a track laid
    # out the wrong way doubles back on itself.
    track = laid(
        chains((LineString([(0, 0), (16, 0)]), "a")),
        edges(
            (LineString([(0, 0), (8, 0)]), "a", 0, 1, [0.0, 8.0]),
            (LineString([(16, 0), (8, 0)]), "a", 2, 1, [16.0, 8.0]),
        ),
    ).iloc[0]
    laid_out = points(track)

    assert (np.diff(laid_out[:, 0]) > 0).all()
    assert np.allclose(laid_out[:, 0], laid_out[:, 2])


def test_two_stretches_that_do_not_join_are_two_parts_and_not_one_line() -> None:
    # A track drawn straight across the step between them is a route nobody can
    # walk. No chain in this park has such a step; the case is held against a
    # fixture rather than against the map.
    apart = MultiLineString([[(0, 0), (10, 0)], [(100, 0), (110, 0)]])
    frame = chains((apart, "a"))
    parts = edges(
        (LineString([(0, 0), (10, 0)]), "a", 0, 1, [0.0, 10.0]),
        (LineString([(100, 0), (110, 0)]), "a", 2, 3, [100.0, 110.0]),
    )
    track = laid(frame, parts).iloc[0]

    assert isinstance(track, MultiLineString)
    assert len(track.geoms) == 2
    assert points(track.geoms[0])[-1][0] == 10.0
    assert points(track.geoms[1])[0][0] == 100.0


def test_a_chain_with_no_edges_at_all_has_no_track() -> None:
    tracks = laid(chains((LineString([(0, 0), (10, 0)]), "a")), edges((LineString([(0, 0), (10, 0)]), "b", 0, 1, [0.0, 10.0])))

    assert tracks.iloc[0] is None
    assert len(tracks) == 1


def test_the_track_is_written_in_the_crs_it_was_asked_for() -> None:
    line = LineString([(400000.0, 7280000.0), (400020.0, 7280000.0)])
    tracks = chain_tracks(
        chains((line, "a")),
        edges((line, "a", 0, 1, [10.0, 30.0])),
        chain_order(chains((line, "a")), edges((line, "a", 0, 1, [10.0, 30.0]))),
    )
    laid_out = points(tracks.iloc[0])

    assert tracks.crs is not None
    assert tracks.crs.to_epsg() == 4326
    # Degrees, and the heights came through the reprojection unharmed. pyproj
    # answers a NaN third ordinate with a NaN *coordinate*, so a track carrying
    # its heights as a Z through to_crs loses its longitude with them.
    assert 12.0 < laid_out[0][0] < 14.0
    assert 65.0 < laid_out[0][1] < 66.0
    assert laid_out[0][2] == 10.0


def test_the_walk_is_stretched_onto_the_length_the_chain_carries() -> None:
    # One length, so a profile's axis, a popup's figure and an exported file all
    # end on the same number — and so the page, which measures degrees flat, and
    # this, which measures a projected metre, agree on where a 5 m gap is.
    line = LineString([(0, 0), (100, 0)])
    frame = chains((line, "a"))
    frame["length_m"] = [50.0]
    track = laid(frame, edges((line, "a", 0, 1, [0.0, 100.0]))).iloc[0]
    laid_out = points(track)
    steps = np.hypot(*(np.diff(laid_out[:, :2], axis=0).T))

    # 50 carried metres over 100 drawn ones: the gap falls where 10 drawn metres
    # do, so the fill puts in half as many points as the geometry alone asks for.
    assert steps.max() <= 2 * DEFAULT_GAP_M + 1e-9
    assert len(laid_out) == 11


def test_chains_and_edges_in_different_projections_are_refused() -> None:
    # The points are composed out of the edges and reprojected out of the
    # chains' CRS. If those ever differ, every exported track lands somewhere
    # else on the earth and nothing about the file says so.
    line = LineString([(400000.0, 7280000.0), (400020.0, 7280000.0)])
    frame, theirs = chains((line, "a")), edges((line, "a", 0, 1, [10.0, 30.0]))
    theirs = theirs.set_crs("EPSG:32633", allow_override=True)

    with pytest.raises(ValueError, match="composed from both"):
        chain_tracks(frame, theirs, chain_order(frame, theirs))


def test_an_order_for_other_edges_is_refused() -> None:
    frame = chains((LineString([(0, 0), (10, 0)]), "a"))
    theirs = edges((LineString([(0, 0), (10, 0)]), "a", 0, 1, [0.0, 10.0]))
    mine = pd.DataFrame({"chain_seq": [0, 0], "flipped": [False, False], "run_start": [True, True]})

    try:
        chain_tracks(frame, theirs, mine)
    except ValueError as error:
        assert "1 edges" in str(error)
    else:
        raise AssertionError("an order describing two edges was accepted for a frame holding one")

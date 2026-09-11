"""Tests for the water grid the page prices a straight walk by."""

import base64
import gzip
import math

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon
from trails.visualization.water import (
    METRES_PER_DEGREE,
    RIVER_FIELDS,
    RIVER_QUANTUM,
    WATER_FIELDS,
    check_rivers,
    check_water,
    river_table,
    water_mask,
)


def unpacked(mask: dict) -> np.ndarray:
    """Read the grid back the way the page does: rows from the south, the
    westernmost cell of a byte in its high bit."""
    packed = np.frombuffer(gzip.decompress(base64.b64decode(mask["bits"])), dtype=np.uint8)
    stride = (mask["cols"] + 7) // 8
    return np.unpackbits(packed.reshape(mask["rows"], stride), axis=1)[:, : mask["cols"]].astype(bool)


def a_lake(west: float, south: float, east: float, north: float) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[Polygon([(west, south), (east, south), (east, north), (west, north)])], crs="EPSG:4326")


def test_a_cell_is_water_when_its_middle_is() -> None:
    # A 100 m box at 25 m cells is four cells square; a lake over its eastern
    # half is the eastern two columns of every row and nothing else.
    d_lat = 25.0 / METRES_PER_DEGREE
    d_lon = 25.0 / (METRES_PER_DEGREE * math.cos(math.radians(65.0)))
    west, south = 13.0, 65.0
    mask = water_mask(a_lake(west + 2 * d_lon, south, west + 4 * d_lon, south + 4 * d_lat), (west, south, west + 4 * d_lon, south + 4 * d_lat), 25.0)

    assert (mask["cols"], mask["rows"]) == (4, 4)
    assert unpacked(mask).tolist() == [[False, False, True, True]] * 4
    assert mask["set"] == 8


def test_the_grid_is_laid_out_from_the_south_west() -> None:
    # A lake in the south-west corner is the first cell of the first row --
    # and the high bit of the first byte, which is where the page looks.
    d_lat = 25.0 / METRES_PER_DEGREE
    d_lon = 25.0 / (METRES_PER_DEGREE * math.cos(math.radians(65.0)))
    mask = water_mask(a_lake(13.0, 65.0, 13.0 + d_lon, 65.0 + d_lat), (13.0, 65.0, 13.0 + 9 * d_lon, 65.0 + 2 * d_lat), 25.0)

    packed = gzip.decompress(base64.b64decode(mask["bits"]))
    assert (mask["cols"], mask["rows"]) == (9, 2)
    assert len(packed) == 2 * 2
    assert packed[0] == 0x80
    assert sum(packed[1:]) == 0


def test_water_outside_the_box_is_not_counted() -> None:
    mask = water_mask(a_lake(14.0, 66.0, 14.1, 66.1), (13.0, 65.0, 13.01, 65.01), 25.0)

    assert mask["set"] == 0


def test_the_entry_carries_every_field_the_page_reads() -> None:
    mask = water_mask(a_lake(13.0, 65.0, 13.01, 65.01), (13.0, 65.0, 13.02, 65.02), 25.0)

    assert set(mask) == set(WATER_FIELDS)
    assert mask["cellM"] == 25.0
    assert mask["dLat"] == pytest.approx(25.0 / METRES_PER_DEGREE)
    assert check_water(mask) is mask


def test_an_empty_box_is_refused() -> None:
    with pytest.raises(ValueError, match="no area"):
        water_mask(a_lake(13.0, 65.0, 13.01, 65.01), (13.0, 65.0, 13.0, 65.01), 25.0)


def test_a_cell_of_no_size_is_refused() -> None:
    with pytest.raises(ValueError, match="positive size"):
        water_mask(a_lake(13.0, 65.0, 13.01, 65.01), (13.0, 65.0, 13.01, 65.01), 0.0)


def test_bits_that_do_not_fit_the_rows_are_refused() -> None:
    # The size the page would refuse it for, caught before the page sees it.
    mask = water_mask(a_lake(13.0, 65.0, 13.01, 65.01), (13.0, 65.0, 13.02, 65.02), 25.0)
    short = dict(mask, rows=mask["rows"] + 1)

    with pytest.raises(ValueError, match="rows of"):
        check_water(short)


def unpacked_ring(steps: list[int]) -> list[tuple[float, float]]:
    """Read a ring back the way the page does: the first pair absolute, every
    pair after it a step from the one before."""
    out, lon, lat = [], 0, 0
    for i in range(0, len(steps), 2):
        lon += steps[i]
        lat += steps[i + 1]
        out.append((lon * RIVER_QUANTUM, lat * RIVER_QUANTUM))
    return out


def a_river(west: float, south: float, east: float, north: float, name: str | None) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"name": [name]}, geometry=[Polygon([(west, south), (east, south), (east, north), (west, north)])], crs="EPSG:4326")


def test_a_river_travels_as_its_outline_named_and_packed() -> None:
    # A 20 m band of river running east-west: four corners, one ring, and the
    # width the page will measure across it is what the outline says.
    d_lat = 20.0 / METRES_PER_DEGREE
    table = river_table(a_river(13.0, 65.0, 13.01, 65.0 + d_lat, "Krutåga"), (12.9, 64.9, 13.1, 65.1), 3.0)

    assert table["quantum"] == RIVER_QUANTUM
    assert len(table["rivers"]) == 1
    river = table["rivers"][0]
    assert set(river) == set(RIVER_FIELDS)
    assert river["name"] == "Krutåga"
    assert [round(value, 5) for value in river["bounds"]] == [13.0, 65.0, 13.01, round(65.0 + d_lat, 5)]
    ring = unpacked_ring(river["rings"][0])
    assert len(ring) == 4
    assert max(lat for _, lat in ring) - min(lat for _, lat in ring) == pytest.approx(d_lat, abs=RIVER_QUANTUM)


def test_a_river_outside_the_box_is_left_out_and_one_across_its_edge_is_clipped() -> None:
    table = river_table(
        gpd.GeoDataFrame(
            {"name": ["far", None]},
            geometry=[
                Polygon([(14.0, 66.0), (14.01, 66.0), (14.01, 66.001), (14.0, 66.001)]),
                Polygon([(13.05, 65.0), (13.2, 65.0), (13.2, 65.001), (13.05, 65.001)]),
            ],
            crs="EPSG:4326",
        ),
        (13.0, 64.9, 13.1, 65.1),
        0.0,
    )

    assert [river["name"] for river in table["rivers"]] == [None]
    assert table["rivers"][0]["bounds"][2] == pytest.approx(13.1)


def test_a_river_table_is_checked_over() -> None:
    good = river_table(a_river(13.0, 65.0, 13.01, 65.001, None), (12.9, 64.9, 13.1, 65.1))
    assert check_rivers(good) is good
    assert check_rivers({"quantum": RIVER_QUANTUM, "rivers": []})["rivers"] == []

    with pytest.raises(ValueError, match="quantum"):
        check_rivers({"quantum": 0, "rivers": []})
    with pytest.raises(ValueError, match="short of"):
        check_rivers({"quantum": RIVER_QUANTUM, "rivers": [{"name": None, "rings": [[0, 0, 1, 0, 0, 1]]}]})
    with pytest.raises(ValueError, match="three or more vertices"):
        check_rivers({"quantum": RIVER_QUANTUM, "rivers": [{"name": None, "bounds": [0, 0, 1, 1], "rings": [[0, 0, 1, 0]]}]})
    with pytest.raises(ValueError, match="has no area"):
        river_table(a_river(13.0, 65.0, 13.01, 65.001, None), (13.0, 65.0, 13.0, 65.1))

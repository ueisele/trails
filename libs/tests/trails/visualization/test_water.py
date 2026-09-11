"""Tests for the water grid the page prices a straight walk by."""

import base64
import gzip
import math

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon
from trails.visualization.water import METRES_PER_DEGREE, WATER_FIELDS, check_water, water_mask


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

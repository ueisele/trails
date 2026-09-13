"""The XYZ grid arithmetic, against figures computed independently."""

import math

from trails.utils import tiles

ABISKO = (18.15, 68.139, 19.10, 68.46)
#: The box as first cut, 2026-09-12: the figures below were computed independently for it.
FIRST_BOX = (18.15, 68.17, 19.00, 68.46)


def test_abisko_at_z13():
    assert tiles.tile_range(FIRST_BOX, 13) == (4509, 1932, 4528, 1950)


def test_abisko_at_z17():
    assert tiles.tile_range(FIRST_BOX, 17) == (72144, 30915, 72453, 31201)


def test_the_world_at_z0():
    assert tiles.tile_range((-180, -85, 180, 85), 0) == (0, 0, 1, 0)


def test_count_over_zooms():
    assert tiles.tile_count(FIRST_BOX, [13]) == 380
    assert tiles.tile_count(FIRST_BOX, range(8, 18)) == 118_967
    assert tiles.tile_count(FIRST_BOX, range(8, 14)) == 540
    # Widened 2026-09-13 (decisions §9.24): 27,681 more, and 610 height tiles instead of 540.
    assert tiles.tile_count(ABISKO, [13]) == 440
    assert tiles.tile_count(ABISKO, range(8, 18)) == 146_995
    assert tiles.tile_count(ABISKO, range(8, 14)) == 610


def test_tile_zero_is_the_world():
    assert tiles.tile_bounds(0, 0, 0) == (-tiles.HALF_WORLD_M, -tiles.HALF_WORLD_M, tiles.HALF_WORLD_M, tiles.HALF_WORLD_M)


def test_tiles_abut_and_rows_count_from_the_top():
    a = tiles.tile_bounds(3, 4, 1)
    right = tiles.tile_bounds(3, 5, 1)
    below = tiles.tile_bounds(3, 4, 2)
    assert math.isclose(a[2], right[0])
    assert math.isclose(a[1], below[3])
    assert a[3] > below[3], "a larger y is further south"


def test_a_z13_pixel_at_abisko_is_seven_metres():
    assert math.isclose(tiles.tile_resolution(13, 68.3), 7.07, abs_tol=0.01)
    assert math.isclose(tiles.tile_resolution(0, 0.0), 156543.03, abs_tol=0.01)

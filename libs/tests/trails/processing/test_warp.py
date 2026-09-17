"""A tile warped out of a window of the model, against the same tile warped out of all of it.

The windowing exists for speed alone (:mod:`trails.processing.warp`), so the
only thing worth testing about it is that it changes nothing: every assertion
here is *the same numbers*, not *close enough*.
"""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject
from trails.processing import warp
from trails.utils.tiles import TILE_PX, tile_bounds, tile_range

#: A model over the Lomsdal-Visten box's south-west corner, 4 m posts, big
#: enough that a tile's window is a small part of it.
POSTS_M = 4.0
ORIGIN = (362_000.0, 7_320_000.0)
SHAPE = (4000, 4000)
SRC_CRS = CRS.from_user_input("EPSG:25833")
BOX = (12.0, 65.15, 13.75, 65.95)


@pytest.fixture(scope="module")
def model():
    """Ground with structure in it: a smooth ramp plus noise, so a resampling
    difference of one post shows up as a difference in the numbers."""
    rows, cols = SHAPE
    y, x = np.mgrid[0:rows, 0:cols]
    ramp = 200.0 + 0.05 * x + 0.03 * y + 60.0 * np.sin(x / 40.0) * np.cos(y / 55.0)
    noise = np.random.default_rng(11).normal(0.0, 3.0, size=SHAPE)
    heights = (ramp + noise).astype(np.float32)
    transform = Affine(POSTS_M, 0.0, ORIGIN[0], 0.0, -POSTS_M, ORIGIN[1])
    return heights, transform


def _warped(source, transform, bounds, side, how):
    out = np.full((side, side), np.nan, dtype=np.float32)
    reproject(
        source=source,
        destination=out,
        src_transform=transform,
        src_crs=SRC_CRS,
        src_nodata=-9999.0,
        dst_transform=from_bounds(*bounds, side, side),
        dst_crs="EPSG:3857",
        dst_nodata=np.nan,
        resampling=how,
    )
    return out


def _ground(model):
    """Where the model is, as a Web Mercator box, so a test can pick tiles on it."""
    from rasterio.warp import transform_bounds

    heights, transform = model
    rows, cols = heights.shape
    east = transform.c + cols * POSTS_M
    south = transform.f - rows * POSTS_M
    return transform_bounds(SRC_CRS, "EPSG:4326", transform.c, south, east, transform.f)


class TestWindow:
    @pytest.mark.parametrize("zoom", [11, 12, 13, 14, 15])
    @pytest.mark.parametrize("how", [Resampling.bilinear, Resampling.average])
    def test_a_windowed_warp_is_the_same_warp(self, model, zoom, how):
        heights, transform = model
        x0, y0, x1, y1 = tile_range(_ground(model), zoom)
        # The middle of the model and its four corner tiles: the corners are
        # where the window is clipped, and where a tile can miss the model
        # altogether -- the model is a rectangle in the metric grid and the box
        # round it in degrees is larger than it.
        checked = 0
        for x, y in (((x0 + x1) // 2, (y0 + y1) // 2), (x0, y0), (x1, y1), (x0, y1), (x1, y0)):
            bounds = tile_bounds(zoom, x, y)
            whole = _warped(heights, transform, bounds, TILE_PX, how)
            near = warp.window(heights, transform, SRC_CRS, bounds, TILE_PX)
            if near is None:
                assert np.isnan(whole).all(), f"z{zoom} {x}/{y}: no window, but the model reaches it"
                continue
            checked += 1
            windowed = _warped(near[0], near[1], bounds, TILE_PX, how)
            assert np.array_equal(np.isnan(whole), np.isnan(windowed)), f"z{zoom} {x}/{y}: different ground is covered"
            assert np.array_equal(whole[~np.isnan(whole)], windowed[~np.isnan(windowed)]), f"z{zoom} {x}/{y}: different numbers"
        assert checked, f"z{zoom}: no tile of this zoom touched the model at all"

    def test_a_patch_with_a_margin_is_the_same_too(self, model):
        """What `shade_tiles.cut` asks for: the tile grown by its margin."""
        heights, transform = model
        x0, y0, x1, y1 = tile_range(_ground(model), 14)
        x, y = (x0 + x1) // 2, (y0 + y1) // 2
        west, south, east, north = tile_bounds(14, x, y)
        grown = (east - west) / TILE_PX * 12
        wide = (west - grown, south - grown, east + grown, north + grown)
        side = TILE_PX + 24
        whole = _warped(heights, transform, wide, side, Resampling.bilinear)
        near = warp.window(heights, transform, SRC_CRS, wide, side)
        assert near is not None
        windowed = _warped(near[0], near[1], wide, side, Resampling.bilinear)
        assert np.array_equal(np.isnan(whole), np.isnan(windowed))
        assert np.array_equal(whole[~np.isnan(whole)], windowed[~np.isnan(windowed)])

    def test_a_fine_tile_takes_a_small_part_of_the_model(self, model):
        """The point of the whole thing: a z15 window is a rounding error of a
        25,000-post mosaic, which is why the warp stops costing what it costs."""
        heights, transform = model
        x0, y0, x1, y1 = tile_range(_ground(model), 15)
        near = warp.window(heights, transform, SRC_CRS, tile_bounds(15, (x0 + x1) // 2, (y0 + y1) // 2), TILE_PX)
        assert near is not None
        assert near[0].size < heights.size / 100

    def test_ground_the_model_does_not_reach_has_no_window(self, model):
        """And the caller then warps nothing, rather than warping nothing slowly."""
        heights, transform = model
        # A tile on the far side of the box from the model's corner.
        x0, y0, x1, y1 = tile_range(BOX, 13)
        assert warp.window(heights, transform, SRC_CRS, tile_bounds(13, x1, y0), TILE_PX) is None

    def test_a_window_that_is_most_of_the_model_is_the_model(self, model):
        """No slice, no copy, where a coarse tile covers all of it: the saving
        is nothing and the bookkeeping would still be there to get wrong."""
        from rasterio.warp import transform_bounds

        heights, transform = model
        rows, cols = heights.shape
        east = transform.c + cols * POSTS_M
        south = transform.f - rows * POSTS_M
        # The model's own ground, in the tile grid's projection, grown a little.
        west, low, far, high = transform_bounds(SRC_CRS, "EPSG:3857", transform.c, south, east, transform.f)
        near = warp.window(heights, transform, SRC_CRS, (west - 1000, low - 1000, far + 1000, high + 1000), TILE_PX)
        assert near is not None
        assert near[0] is heights and near[1] is transform

    def test_a_tile_hanging_over_the_edge_is_warped_from_the_whole_model(self, model):
        """Measured, and the reason the rule exists: where a destination reaches
        past its source, the numbers depend on how far past -- so a window that
        would be clipped is not taken at all."""
        heights, transform = model
        x0, y0, x1, y1 = tile_range(_ground(model), 13)
        clipped = 0
        for x, y in ((x0, y0), (x1, y1), (x0, y1), (x1, y0)):
            near = warp.window(heights, transform, SRC_CRS, tile_bounds(13, x, y), TILE_PX)
            if near is None:
                continue
            clipped += 1
            assert near[0] is heights and near[1] is transform
        assert clipped, "no corner tile of this model hangs over its edge, so this proves nothing"

    def test_the_slice_is_contiguous(self, model):
        """A non-contiguous view reaches GDAL as a copy it makes itself, or not
        at all; either way the caller should not have to know."""
        heights, transform = model
        x0, y0, x1, y1 = tile_range(_ground(model), 14)
        near = warp.window(heights, transform, SRC_CRS, tile_bounds(14, (x0 + x1) // 2, (y0 + y1) // 2), TILE_PX)
        assert near is not None
        assert near[0].flags["C_CONTIGUOUS"]

"""Cut a height model down to what one tile needs, before warping it.

**Measured 2026-09-17, and it is the whole reason this module exists.** The same
256 × 256 tile, warped out of models of three sizes with `rasterio.warp.reproject`:

| model | one warp |
|---|---|
| 2,500 × 2,500 (25 MB) | 12 ms |
| 10,000 × 8,750 (350 MB), the Abisko mosaic | 51 ms |
| 25,000 × 25,000 (2.5 GB), the Lomsdal-Visten mosaic | **346 ms** |

The destination is identical in all three; the cost is the *source*. Packing the
PNG afterwards is 2–15 ms, so the warp is the whole of it. Over the 37,915 tiles
of one ground tree that is four hours against a few minutes, and
analysis/docs/abisko-decisions.md §6.3 predicted exactly this -- "a box four
times the size would want the squares warped one at a time instead".

So a tile is warped out of a **view of the model over its own ground** rather
than out of the model. The view is a slice, so it costs nothing to take, and the
numbers that come out are the same ones.

**They are the same ones only while the tile's ground lies wholly inside the
model, and that is why this function refuses to window when it does not.**
Measured, because it is not obvious and it was found the hard way: shrinking the
source from 4,000 × 4,000 to 2,000 × 2,000 changes nothing at all about a tile
that sits inside both, bilinear or averaged. Shrink it until the tile hangs over
the edge and the numbers move -- by up to 4.4 m on the ground this was measured
over, over *every* pixel of the tile and not only the ones near the edge, and by
less and less as the window is padded further, without ever settling. So what a
warp does where its destination reaches past its source is not something a
window may quietly change, and a window that would have to be clipped is not
taken: the whole model goes in, as it did before, and the tile costs what it
used to cost. Those are the tiles at the very edge of a tree and there are a few
hundred of them against thirty-seven thousand.

That the two agree exactly everywhere else is what ``test_warp.py`` checks, tile
by tile, at every zoom a tree is cut over and in both resamplings -- and what was
then checked again on the ground rather than on a fixture: over the cached Abisko
mosaic, 210 height tiles from z8 to z13 came out **byte-identical as PNGs**, and
240 relief patches from z8 to z15, margin and all, came out identical as numbers.
A tile tree is not a thing to make faster on an argument.
"""

import numpy as np
from affine import Affine
from rasterio.crs import CRS
from rasterio.warp import transform_bounds

#: Posts left round the envelope, on top of the reach below. This is the margin
#: for the rounding that put the envelope on whole posts.
PAD_POSTS = 4

#: How many destination pixels' worth of source a warp may reach past its
#: destination, as a multiple of the posts under one destination pixel.
#:
#: **Measured, and four posts was not enough.** A warp does not read only the
#: posts under the pixel it is filling: over the Abisko mosaic, a z10 tile --
#: fifteen posts to the pixel -- came out with fourteen of its 65,536 pixels
#: different, by up to 0.57 m, when the source was cut to the envelope plus four
#: posts. The fine levels, where a pixel is one or two posts, were identical at
#: every sample. So the margin is in *destination pixels* and not in posts, and
#: two of them costs nothing: at z15 it is six posts on a window of a hundred
#: and forty, at z10 thirty-four on nearly four thousand.
PAD_PIXELS = 2

#: How much of the model a window may cover before it is not worth taking. Above
#: this the slice is the model and the saving is nothing, while the bookkeeping
#: is still there to be got wrong.
WHOLE_ABOVE = 0.8


def window(
    model: np.ndarray,
    transform: Affine,
    src_crs: CRS,
    bounds: tuple[float, float, float, float],
    side: int,
    dst_crs: str | CRS = "EPSG:3857",
) -> tuple[np.ndarray, Affine] | None:
    """The part of a model one tile is warped from, and that part's own georeferencing.

    Args:
        model: The model, ``(rows, cols)``, north up
        transform: Its georeferencing, which must be axis-aligned and north up
        src_crs: Its projection
        bounds: The ground the tile covers, ``(west, south, east, north)`` in ``dst_crs``
        side: Pixels across the destination, which is what says how many posts
            sit under one of them and therefore how far the warp may reach
        dst_crs: What ``bounds`` are in; the tile grid's projection

    Returns:
        A view of the model and its transform -- or the model itself, where the
        window would be most of it or would have to be clipped to fit, which
        are the two cases a window is not worth taking in -- or None where the
        tile's ground lies outside the model altogether and nothing should be
        warped at all
    """
    west, south, east, north = transform_bounds(dst_crs, src_crs, *bounds, densify_pts=32)
    posts_x, posts_y = transform.a, -transform.e
    across = max((east - west) / posts_x, (north - south) / posts_y)
    pad = PAD_POSTS + int(np.ceil(PAD_PIXELS * across / max(side, 1)))
    left = int(np.floor((west - transform.c) / posts_x)) - pad
    right = int(np.ceil((east - transform.c) / posts_x)) + pad
    top = int(np.floor((transform.f - north) / posts_y)) - pad
    bottom = int(np.ceil((transform.f - south) / posts_y)) + pad
    tall, wide = model.shape
    if right <= 0 or bottom <= 0 or left >= wide or top >= tall:
        return None
    # **Clipped means the tile hangs over the model's edge**, and there a warp
    # off a window is not the warp off the model -- see the module docstring.
    # The model goes in whole, which is what happened before this existed.
    if left < 0 or top < 0 or right > wide or bottom > tall:
        return model, transform
    if (right - left) * (bottom - top) > WHOLE_ABOVE * tall * wide:
        return model, transform
    cut = model[top:bottom, left:right]
    moved = Affine(transform.a, 0.0, transform.c + left * posts_x, 0.0, transform.e, transform.f - top * posts_y)
    return np.ascontiguousarray(cut), moved

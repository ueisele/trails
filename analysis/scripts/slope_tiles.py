"""Build the slope-class tiles for one box out of Lantmäteriet's height model.

The page colours how steep the ground is, in the classes the avalanche services publish, from tiles addressed
like the map's, served from our own bucket and kept in the same offline store
-- analysis/docs/abisko-decisions.md §6.7. This reads the same cached mosaic
the height tiles are cut from (``.cache/elevation/``, built by ``make dem``
with the Geotorget login) and writes ``{z}/{x}/{y}.png`` under the output
directory, resuming where it left off.

**It needs no login of its own once the mosaic is there.** ``make dem`` caches
it; this reads that file. Only a first build on a clean box, or one with
``--force-download``, wants ``GEOTORGET_USERNAME`` and ``GEOTORGET_PASSWORD``.

Run with::

    command make slope                              # the Abisko box, z8 to z15
    command make slope ARGS="--max-zoom 13"         # a quick look at the coarse levels

``command make deploy ARGS="--tree slope"`` uploads the tree.
"""

import argparse
import sys
from pathlib import Path

from trails.io.sources import markhojd
from trails.processing import slope_tiles
from trails.utils.tiles import Bounds, tile_count

#: The Abisko box, as in ``lantmateriet_tiles.py`` and the decisions doc §2.
ABISKO: Bounds = (18.15, 68.139, 19.10, 68.46)

#: The finest level built, the relief's: the classes are read off the same
#: smoothed heights, so past it a tile would draw the same ground on a finer
#: grid (§6.7).
MAX_ZOOM = 15

#: The coarsest: at z8 the box is two tiles.
MIN_ZOOM = 8

#: Post spacing the model is read at, the same as the height tiles use.
POSTS_M = 4.0

#: Where the tiles go, under analysis/output/: the bucket prefix the page will
#: fetch them from, with the version segment.
DEFAULT_OUTPUT = Path("analysis") / "output" / "slope" / "lantmateriet" / "1"


def main() -> int:
    """Build the tiles.

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"), default=list(ABISKO))
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM)
    parser.add_argument("--posts-m", type=float, default=POSTS_M, help="Post spacing the model is read at: 1, 2, 4 or 8")
    parser.add_argument("--smooth-posts", type=float, default=slope_tiles.SMOOTH_POSTS, help="How far the heights are smoothed first, in posts")
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Where the assembled mosaic is kept")
    parser.add_argument("--output-dir", type=Path, default=repo_root / DEFAULT_OUTPUT)
    parser.add_argument("--force-download", action="store_true", help="Read the squares again even if the mosaic is cached")
    args = parser.parse_args()

    bounds: Bounds = (args.bounds[0], args.bounds[1], args.bounds[2], args.bounds[3])
    zooms = range(args.min_zoom, args.max_zoom + 1)
    if args.min_zoom > args.max_zoom:
        print("--min-zoom is above --max-zoom", file=sys.stderr)
        return 2
    print(f"Box {bounds}, {tile_count(bounds, zooms):,} tiles over z{args.min_zoom}–z{args.max_zoom}, into {args.output_dir}")
    heights, transform = markhojd.Source(cache_dir=args.cache_dir).mosaic(bounds, posts_m=args.posts_m, force_download=args.force_download)
    slope_tiles.build_tiles(
        heights,
        transform,
        markhojd.CRS,
        bounds,
        zooms,
        args.output_dir,
        nodata=markhojd.NODATA,
        smooth_posts=args.smooth_posts,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

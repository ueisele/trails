"""Build the hillshade tiles for one map out of its country's height model.

The page draws a relief shadow under the map's contours, from tiles addressed
like the map's, served from our own bucket and kept in the same offline store
-- analysis/docs/abisko-decisions.md §6.6 for Abisko and §6.10 for
Lomsdal-Visten. Which box, which model and how deep is
:data:`trails.processing.trees.TREES`; this reads the same cached mosaic the
height tiles are cut from (``.cache/elevation/``, which ``make dem`` fills) and
writes ``{z}/{x}/{y}.png`` under the output directory, resuming where it left
off.

**It needs no login of its own once the mosaic is there**, and the Norwegian
model needs none at all. ``make dem`` caches it; this reads that file. Only a
first build on a clean box, or one with ``--force-download``, wants Sweden's
``GEOTORGET_USERNAME`` and ``GEOTORGET_PASSWORD``.

Run with::

    command make shade                              # Lomsdal-Visten, z8 to z15
    command make shade PARK=abisko                  # the other map
    command make shade ARGS="--max-zoom 13"         # a quick look at the coarse levels

``command make deploy ARGS="--tree shade"`` uploads the tree.
"""

import argparse
import dataclasses
import sys
from pathlib import Path

from trails.processing import shade_tiles, trees
from trails.utils.tiles import tile_count


def main() -> int:
    """Build the tiles.

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--park", default="lomsdal-visten", choices=sorted(trees.TREES), help="Which map's relief to cut")
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"), default=None)
    parser.add_argument("--min-zoom", type=int, default=None)
    parser.add_argument("--max-zoom", type=int, default=None)
    parser.add_argument("--posts-m", type=float, default=None, help="Post spacing the model is read at, in metres")
    parser.add_argument("--azimuth", type=float, default=shade_tiles.AZIMUTH, help="Where the light comes from, degrees clockwise from north")
    parser.add_argument("--altitude", type=float, default=shade_tiles.ALTITUDE, help="How high the light stands, in degrees")
    parser.add_argument("--smooth-posts", type=float, default=shade_tiles.SMOOTH_POSTS, help="How far the heights are smoothed first, in posts")
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Where the assembled mosaic is kept")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--force-download", action="store_true", help="Read the model again even if it is cached")
    args = parser.parse_args()

    tree = trees.TREES[args.park]
    if args.bounds or args.posts_m:
        box = (args.bounds[0], args.bounds[1], args.bounds[2], args.bounds[3]) if args.bounds else tree.box
        tree = dataclasses.replace(tree, box=box, posts_m=args.posts_m or tree.posts_m)
    levels = tree.zooms("shade")
    zooms = range(args.min_zoom if args.min_zoom is not None else levels.start, (args.max_zoom if args.max_zoom is not None else levels.stop - 1) + 1)
    if zooms.start > zooms.stop - 1:
        print("--min-zoom is above --max-zoom", file=sys.stderr)
        return 2
    out_dir = args.output_dir or repo_root / "analysis" / "output" / tree.prefix("shade").strip("/")
    print(f"Box {tree.box}, {tile_count(tree.box, zooms):,} tiles over z{zooms.start}–z{zooms.stop - 1}, into {out_dir}")
    heights, transform, crs, nodata = trees.read_model(tree, args.cache_dir, force_download=args.force_download)
    shade_tiles.build_tiles(
        heights,
        transform,
        crs,
        tree.box,
        zooms,
        out_dir,
        nodata=nodata,
        azimuth=args.azimuth,
        altitude=args.altitude,
        smooth_posts=args.smooth_posts,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

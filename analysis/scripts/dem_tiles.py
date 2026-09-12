"""Build the height tiles for one box out of Lantmäteriet's height model.

The page reads heights from tiles addressed like the map's, served from our
own bucket and kept in the same offline store -- analysis/docs/abisko-decisions.md
§6.3. This finds the model's 2.5 km squares over the box through the keyless
STAC API, reads each at the overview a z13 tile needs with the Geotorget login
(``GEOTORGET_USERNAME`` and ``GEOTORGET_PASSWORD`` in the environment; the
mosaic is cached under ``.cache/elevation/`` so a second build reads nothing),
and writes ``{z}/{x}/{y}.png`` under the output directory, resuming where it
left off. ``command make deploy ARGS="--tree dem"`` uploads the tree.

Run with::

    command make dem                                # the Abisko box, z8 to z13
    command make dem ARGS="--max-zoom 11"           # a quick look at the coarse levels

From ``home/trails-map``, where the login is::

    sops exec-env secrets.sops.env 'cd ../../trails && command make dem'
"""

import argparse
import sys
from pathlib import Path

from trails.io.sources import markhojd
from trails.processing import dem_tiles
from trails.utils.tiles import Bounds, tile_count

#: The Abisko box, as in ``lantmateriet_tiles.py`` and the decisions doc §2.
ABISKO: Bounds = (18.15, 68.17, 19.00, 68.46)

#: The finest level built: at 68° N a z13 pixel is 7 m, and the tiles would
#: only repeat the model's posts beyond it (§6.3).
MAX_ZOOM = 13

#: The coarsest: at z8 the box is two tiles.
MIN_ZOOM = 8

#: Post spacing the model is read at. The model carries 1, 2, 4 and 8 m; 4 m
#: is the first level finer than a z13 pixel, so the bilinear tile never
#: averages posts it does not have.
POSTS_M = 4.0

#: Where the tiles go, under analysis/output/: the bucket prefix the page will
#: fetch them from, with the version segment (§6.2 of the decisions).
DEFAULT_OUTPUT = Path("analysis") / "output" / "dem" / "lantmateriet" / "1"


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
    dem_tiles.build_tiles(heights, transform, markhojd.CRS, bounds, zooms, args.output_dir, nodata=markhojd.NODATA)
    return 0


if __name__ == "__main__":
    sys.exit(main())

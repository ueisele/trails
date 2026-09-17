"""Build the height tiles for one map out of its country's height model.

The page reads heights from tiles addressed like the map's, served from our
own bucket and kept in the same offline store -- analysis/docs/abisko-decisions.md
§6.3 for Abisko and §6.10 for Lomsdal-Visten. Which box, which model and how
deep is :data:`trails.processing.trees.TREES`; this writes
``{z}/{x}/{y}.png`` under the output directory, resuming where it left off.
``command make deploy ARGS="--tree dem"`` uploads the tree.

**Sweden needs a login, Norway does not.** Lantmäteriet's *Markhöjdmodell*
finds its 2.5 km squares through a keyless STAC API but reads them with the
Geotorget login (``GEOTORGET_USERNAME`` and ``GEOTORGET_PASSWORD`` in the
environment); Kartverket's national model answers ``hoydedata.no``'s image
service with nothing at all. Either way the mosaic is cached under
``.cache/elevation/``, so a second build reads nothing over the network.

Run with::

    command make dem                                # Lomsdal-Visten, z8 to z13
    command make dem PARK=abisko                    # the other map
    command make dem ARGS="--max-zoom 11"           # a quick look at the coarse levels

From ``home/trails-map``, where the Swedish login is::

    sops exec-env secrets.sops.env 'cd ../../trails && command make dem PARK=abisko'
"""

import argparse
import dataclasses
import sys
from pathlib import Path

from trails.processing import dem_tiles, trees
from trails.utils.tiles import tile_count


def main() -> int:
    """Build the tiles.

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--park", default="lomsdal-visten", choices=sorted(trees.TREES), help="Which map's heights to cut")
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"), default=None)
    parser.add_argument("--min-zoom", type=int, default=None)
    parser.add_argument("--max-zoom", type=int, default=None)
    parser.add_argument("--posts-m", type=float, default=None, help="Post spacing the model is read at, in metres")
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Where the assembled mosaic is kept")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--force-download", action="store_true", help="Read the model again even if it is cached")
    args = parser.parse_args()

    tree = trees.TREES[args.park]
    if args.bounds or args.posts_m:
        box = (args.bounds[0], args.bounds[1], args.bounds[2], args.bounds[3]) if args.bounds else tree.box
        tree = dataclasses.replace(tree, box=box, posts_m=args.posts_m or tree.posts_m)
    levels = tree.zooms("dem")
    zooms = range(args.min_zoom if args.min_zoom is not None else levels.start, (args.max_zoom if args.max_zoom is not None else levels.stop - 1) + 1)
    if zooms.start > zooms.stop - 1:
        print("--min-zoom is above --max-zoom", file=sys.stderr)
        return 2
    out_dir = args.output_dir or repo_root / "analysis" / "output" / tree.prefix("dem").strip("/")
    print(f"Box {tree.box}, {tile_count(tree.box, zooms):,} tiles over z{zooms.start}–z{zooms.stop - 1}, into {out_dir}")
    heights, transform, crs, nodata = trees.read_model(tree, args.cache_dir, force_download=args.force_download)
    dem_tiles.build_tiles(heights, transform, crs, tree.box, zooms, out_dir, nodata=nodata)
    return 0


if __name__ == "__main__":
    sys.exit(main())

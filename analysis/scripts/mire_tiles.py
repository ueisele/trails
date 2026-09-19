"""Build the mire tiles for one map out of its country's surveys.

The page colours where the ground is bog and marsh, and whether it carries a
boot, from tiles addressed like the map's, served from our own bucket and
kept in the same offline store -- analysis/docs/abisko-decisions.md §6.13.
Which box and which source is :data:`trails.processing.trees.TREES`:
Sweden's off Lantmäteriet's wetland outlines (Marktäcke, through the vector
STAC API with the Geotorget login, once the product is ordered) and SLU's
soil-moisture mosaic (8.4 GB off Skogsstyrelsen's FTPS, fetched once into
``.cache/moisture/`` with the login their download page publishes); Norway's
off N50's bogs, which the map's own loaders already hold. The class grid is
cut once per box into ``.cache/mire/`` and the tree written under the output
directory as ``{z}/{x}/{y}.png``, resuming where it left off.

Run with::

    command make mire                         # Lomsdal-Visten, z8 to z15
    command make mire PARK=abisko             # the other map, needs the two logins on a cold cache
    command make mire ARGS="--max-zoom 12"    # a quick look at the coarse levels

``command make packs`` packs it with the other trees; ``just deploy --tree packs`` uploads them.
"""

import argparse
import dataclasses
import sys
from pathlib import Path

from trails.processing import mire_tiles, trees
from trails.utils.tiles import tile_count


def main() -> int:
    """Build the tiles.

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--park", default="lomsdal-visten", choices=sorted(trees.TREES), help="Which map's mire to cut")
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"), default=None)
    parser.add_argument("--min-zoom", type=int, default=None)
    parser.add_argument("--max-zoom", type=int, default=None)
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Where the sources' caches live")
    parser.add_argument("--output-dir", type=Path, default=None, help="Root of the tree")
    parser.add_argument("--force-download", action="store_true", help="Read the sources again even if the cut is cached")
    args = parser.parse_args()

    tree = trees.TREES[args.park]
    if args.bounds:
        tree = dataclasses.replace(tree, box=(args.bounds[0], args.bounds[1], args.bounds[2], args.bounds[3]))
    if tree.mire is None:
        print(f"{args.park} names no mire source", file=sys.stderr)
        return 2
    levels = tree.zooms(mire_tiles.KIND)
    zooms = range(args.min_zoom if args.min_zoom is not None else levels.start, (args.max_zoom if args.max_zoom is not None else levels.stop - 1) + 1)
    if zooms.start > zooms.stop - 1:
        print("--min-zoom is above --max-zoom", file=sys.stderr)
        return 2
    print(f"Box {tree.box}, {tile_count(tree.box, zooms):,} tiles over z{zooms.start}–z{zooms.stop - 1}")
    classes, transform, crs = trees.read_mire(tree, args.cache_dir, force_download=args.force_download)
    out_dir = args.output_dir if args.output_dir else repo_root / "analysis" / "output" / tree.prefix(mire_tiles.KIND).strip("/")
    print(f"{mire_tiles.KIND}: into {out_dir}")
    mire_tiles.build_tiles(classes, transform, crs, tree.box, zooms, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

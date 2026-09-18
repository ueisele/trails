"""Build the vegetation and forest tiles for one map out of its country's laser survey.

The page colours how much stands between knee and head height, and where the
trees are, from tiles addressed like the map's, served from our own bucket and
kept in the same offline store -- analysis/docs/abisko-decisions.md §6.11.
Which box and which source is :data:`trails.processing.trees.TREES`: Sweden's
NMD 2018 classes off Naturvårdsverket's nationwide rasters, converted once
into ``.cache/vegetation/nmd2018/`` (``make nmd`` does that ahead of time);
Norway's computed from Kartverket's surface and terrain models square by square
into ``.cache/vegetation/hoydedata/``. Neither needs a login. Both trees are
cut from the one set of codes and written under the output directory as
``{z}/{x}/{y}.png``, resuming where they left off.

Run with::

    command make vegetation                         # Lomsdal-Visten, both trees, z8 to z15
    command make vegetation PARK=abisko             # the other map
    command make vegetation ARGS="--tree forest"    # one of the two
    command make vegetation ARGS="--max-zoom 12"    # a quick look at the coarse levels

``command make deploy ARGS="--tree vegetation --tree forest"`` uploads them.
"""

import argparse
import dataclasses
import sys
from pathlib import Path

from trails.processing import trees, vegetation_tiles
from trails.utils.tiles import tile_count


def main() -> int:
    """Build the tiles.

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--park", default="lomsdal-visten", choices=sorted(trees.TREES), help="Which map's vegetation to cut")
    parser.add_argument("--tree", action="append", choices=vegetation_tiles.KINDS, default=None, help="Which of the two trees; both by default")
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"), default=None)
    parser.add_argument("--min-zoom", type=int, default=None)
    parser.add_argument("--max-zoom", type=int, default=None)
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Where the sources' caches live")
    parser.add_argument("--output-dir", type=Path, default=None, help="Root of the trees; the tree's own name is appended")
    parser.add_argument("--force-download", action="store_true", help="Read the source again even if it is cached")
    args = parser.parse_args()

    tree = trees.TREES[args.park]
    if args.bounds:
        tree = dataclasses.replace(tree, box=(args.bounds[0], args.bounds[1], args.bounds[2], args.bounds[3]))
    if tree.structure is None:
        print(f"{args.park} names no vegetation source", file=sys.stderr)
        return 2
    kinds = tuple(args.tree) if args.tree else vegetation_tiles.KINDS
    levels = tree.zooms("vegetation")
    zooms = range(args.min_zoom if args.min_zoom is not None else levels.start, (args.max_zoom if args.max_zoom is not None else levels.stop - 1) + 1)
    if zooms.start > zooms.stop - 1:
        print("--min-zoom is above --max-zoom", file=sys.stderr)
        return 2
    print(f"Box {tree.box}, {tile_count(tree.box, zooms):,} tiles per tree over z{zooms.start}–z{zooms.stop - 1}")
    codes, transform, crs = trees.read_structure(tree, args.cache_dir, force_download=args.force_download)
    for kind in kinds:
        out_dir = (args.output_dir / kind) if args.output_dir else repo_root / "analysis" / "output" / tree.prefix(kind).strip("/")
        print(f"{kind}: into {out_dir}")
        vegetation_tiles.build_tiles(codes, transform, crs, tree.box, zooms, out_dir, kind=kind)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Copy Lantmäteriet's map tiles for one box out of the open download into a tile tree.

The tiles are the base map of each Swedish page, served from our own bucket
rather than from Lantmäteriet's paid service — see
analysis/docs/abisko-decisions.md §3 and §6.1. This reads the whole-Sweden
GeoPackage over FTP by byte range and writes ``{z}/{x}/{y}.png`` under the
output directory, resuming where it left off. The deploy uploads the tree.

Run with::

    command make tiles PARK=abisko                  # the Abisko box, z8 to z17
    command make tiles PARK=malingsbo-kloten ARGS="--max-zoom 13"
"""

import argparse
import sys
from pathlib import Path

from trails.io.sources import lantmateriet
from trails.processing.trees import TREES


def main(argv: list[str] | None = None) -> int:
    """Copy the tiles.

    Args:
        argv: CLI arguments; None reads the process arguments

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--park", choices=[key for key, tree in TREES.items() if tree.provider.startswith("lantmateriet")], default="abisko")
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    parser.add_argument("--min-zoom", type=int, default=lantmateriet.MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=lantmateriet.MAX_ZOOM)
    parser.add_argument("--tree-root", type=Path, help="The tree's root; the version directory is chosen under it")
    args = parser.parse_args(argv)
    tree = TREES[args.park]
    if args.bounds is None:
        args.bounds = tree.box
    if args.tree_root is None:
        args.tree_root = repo_root / "analysis/output/tiles" / tree.provider / "topowebb"

    bounds: lantmateriet.Bounds = (args.bounds[0], args.bounds[1], args.bounds[2], args.bounds[3])
    zooms = range(args.min_zoom, args.max_zoom + 1)
    if args.min_zoom > args.max_zoom:
        print("--min-zoom is above --max-zoom", file=sys.stderr)
        return 2
    source = lantmateriet.Source()
    modified = source.reader.modified if isinstance(source.reader, lantmateriet.FtpFile) else None
    if modified is None:
        print("the reader does not say when the file was modified, so no version can be chosen", file=sys.stderr)
        return 2
    version, fresh = lantmateriet.version_for(args.tree_root, modified)
    stand = f"{modified[:4]}-{modified[4:6]}-{modified[6:8]} {modified[8:10]}:{modified[10:12]}"
    print(f"The file on the server is the stand of {stand}: version {version} " + ("(new — a full copy)" if fresh else "(resumed)"))
    out_dir = args.tree_root / str(version)
    print(f"Box {bounds}, {lantmateriet.tile_count(bounds, zooms):,} tiles over z{args.min_zoom}–z{args.max_zoom}, into {out_dir}")
    source.copy_tiles(bounds, zooms, out_dir)
    print(f"✅ {out_dir}/ — the next page build draws version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

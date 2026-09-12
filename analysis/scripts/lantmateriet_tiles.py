"""Copy Lantmäteriet's map tiles for one box out of the open download into a tile tree.

The tiles are the base map of the Abisko page, served from our own bucket
rather than from Lantmäteriet's paid service — see
analysis/docs/abisko-decisions.md §3 and §6.1. This reads the whole-Sweden
GeoPackage over FTP by byte range and writes ``{z}/{x}/{y}.png`` under the
output directory, resuming where it left off. The deploy uploads the tree.

Run with::

    command make tiles                              # the Abisko box, z8 to z17
    command make tiles ARGS="--max-zoom 13"         # a quick look at the coarse levels
"""

import argparse
import sys
from pathlib import Path

from trails.io.sources import lantmateriet

#: The Abisko box: west on the border at 18.15 E, south so that Áhpparjávri is
#: whole, east at the western tip of Rautasjaure, north with the E10 inside.
#: Its reasons are in analysis/docs/abisko-decisions.md §2.
ABISKO: lantmateriet.Bounds = (18.15, 68.17, 19.00, 68.46)

#: Where the tiles go, under analysis/output/: the bucket prefix the page will
#: fetch them from. The version segment is chosen per run: the stand of the
#: file on the server names it, a new stand gets the next number and the
#: page built afterwards draws that one (§6.1, §9.20 of the decisions).
DEFAULT_ROOT = Path("analysis") / "output" / "tiles" / "lantmateriet" / "topowebb"


def main() -> int:
    """Copy the tiles.

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"), default=list(ABISKO))
    parser.add_argument("--min-zoom", type=int, default=lantmateriet.MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=lantmateriet.MAX_ZOOM)
    parser.add_argument("--tree-root", type=Path, default=repo_root / DEFAULT_ROOT, help="The tree's root; the version directory is chosen under it")
    args = parser.parse_args()

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

"""Cut Kartverket's flat topo sheet to a versioned palette PNG tree.

    command make tiles PARK=lomsdal-visten ARGS="--max-zoom 16"
    command make tiles PARK=lomsdal-visten             # resume and extend to z17
    command make tiles PARK=lomsdal-visten ARGS="--new-version"
    uv run python analysis/scripts/kartverket_tiles.py --weights-from analysis/output/tiles/kartverket/topo/1/index.json

The stand identifies the configuration; --new-version explicitly starts a
fresh snapshot of the continuously updated map. A normal run resumes the
latest directory, keeping its start date. No map-data change is detected.
The weights command reads only the inventory and makes no service requests.

``make tiles`` dispatches here on Tree.provider; Abisko invokes the existing
Lantmäteriet script with its arguments unchanged.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from trails.io.sources import kartverket_wms
from trails.processing.trees import TREES
from trails.utils.tiles import Bounds, tile_count


def main(argv: list[str] | None = None) -> int:
    """Dispatch the provider, render a snapshot, or read its measured weights.

    Args:
        argv: CLI arguments; None reads the process arguments.

    Returns:
        Process exit status.
    """
    dispatch = argparse.ArgumentParser(add_help=False)
    dispatch.add_argument("--park", choices=TREES, default="lomsdal-visten")
    selection, remaining = dispatch.parse_known_args(argv)
    tree = TREES[selection.park]
    if tree.provider == "lantmateriet":
        return subprocess.run([sys.executable, str(Path(__file__).with_name("lantmateriet_tiles.py")), *remaining], check=False).returncode
    if tree.provider != "kartverket":
        dispatch.error(f"no base tile cutter for provider {tree.provider}")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[dispatch])
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"), default=tree.box)
    parser.add_argument("--min-zoom", type=int, default=kartverket_wms.MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=kartverket_wms.MAX_ZOOM)
    parser.add_argument("--tree-root", type=Path, default=Path(__file__).resolve().parents[2] / "analysis/output/tiles/kartverket/topo")
    parser.add_argument("--new-version", action="store_true", help="Start a fresh snapshot even when the rendering configuration is unchanged")
    parser.add_argument(
        "--weights-from", type=Path, metavar="INDEX", help="Print rounded mean bytes per tile from a completed index, without rendering"
    )
    args = parser.parse_args(argv)
    if args.weights_from:
        print(kartverket_wms.weights_from_index(args.weights_from))
        return 0
    if not kartverket_wms.MIN_ZOOM <= args.min_zoom <= args.max_zoom <= kartverket_wms.MAX_ZOOM:
        parser.error(f"require {kartverket_wms.MIN_ZOOM} <= --min-zoom <= --max-zoom <= {kartverket_wms.MAX_ZOOM}")
    bounds: Bounds = (args.bounds[0], args.bounds[1], args.bounds[2], args.bounds[3])
    source = kartverket_wms.Source()
    version, fresh = kartverket_wms.version_for(args.tree_root, source.stand, new_version=args.new_version)
    out_dir = args.tree_root / str(version)
    zooms = range(args.min_zoom, args.max_zoom + 1)
    print(f"Configuration {source.stand}: version {version} " + ("(new snapshot)" if fresh else "(resumed)"), flush=True)
    print(f"Box {bounds}, {tile_count(bounds, zooms):,} tiles over z{args.min_zoom}–z{args.max_zoom}, into {out_dir}", flush=True)
    source.copy_tiles(bounds, zooms, out_dir)
    print(f"Weights (mean bytes per tile): {kartverket_wms.weights_from_index(out_dir / kartverket_wms.INDEX_FILE)}")
    print(f"✅ {out_dir}/ — snapshot complete; publication and provider changes are separate steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())

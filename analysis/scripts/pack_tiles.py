"""Pack every finished tile tree of a map without changing the source PNGs.

    command make packs PARK=abisko
    uv run python analysis/scripts/pack_tiles.py --park abisko --tree dem --output-dir /tmp/phase-6a/out

--input-dir names the source analysis/output; --output-dir receives packs/.
--parent Z X Y builds a single pack for a smoke run and marks its index incomplete.
"""

import argparse
import sys
import time
from pathlib import Path

from trails.processing import packs, trees

LAYERS = ("tiles", "dem", "shade", "slope", "vegetation", "forest", "mire")


def main(argv: list[str] | None = None) -> int:
    """Build the selected map's packs and report counts, bytes and elapsed time."""
    default = Path(__file__).resolve().parents[2] / "analysis/output"
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--park", choices=sorted(trees.TREES), default="lomsdal-visten")
    parser.add_argument("--input-dir", type=Path, default=default)
    parser.add_argument("--output-dir", type=Path, default=default)
    parser.add_argument("--tree", choices=LAYERS, action="append", help="Only this tree; repeatable, default all seven")
    parser.add_argument("--parent", nargs=3, type=int, metavar=("Z", "X", "Y"))
    args = parser.parse_args(argv)
    selected = list(dict.fromkeys(args.tree or LAYERS))
    if args.parent and len(selected) != 1:
        parser.error("--parent requires exactly one --tree")
    tree = trees.TREES[args.park]
    sources = []
    try:
        for layer in selected:
            if layer == "tiles":
                sheet = {"lantmateriet": "topowebb", "lantmateriet-malingsbo-kloten": "topowebb", "kartverket": "topo"}[tree.provider]
                root = args.input_dir / layer / tree.provider / sheet
                versions = [int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit()]
                if not versions:
                    raise ValueError(f"{root}: no source versions")
                # Use the latest version, refusing an unfinished render rather than silently
                # packing an older snapshot under a different address.
                source = root / str(max(versions))
            else:
                source = args.input_dir / tree.prefix(layer).strip("/")
            packs.read_index(source / "index.json")  # preflight all seven before writing any
            sources.append(source)
        for source in sources:
            relative = source.relative_to(args.input_dir)
            started = time.perf_counter()
            parent = tuple(args.parent) if args.parent else None
            index = packs.build_tree(
                source,
                args.output_dir / "packs" / relative,
                source_index=(relative / "index.json").as_posix(),
                parent=parent,
            )
            for level, row in index["per_level"].items():
                print(f"{relative} z{level}: {row['packs']} packs, {row['written']} written, {row['skipped']} skipped, {row['bytes']} bytes")
            count = sum(row["packs"] for row in index["per_level"].values())
            size = sum(row["bytes"] for row in index["per_level"].values())
            print(f"{relative}: {count} packs, {index['tiles']} tiles, {size} bytes, {time.perf_counter() - started:.3f} s", flush=True)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Fetch and convert Naturvårdsverket's NMD 2018 object rasters into the cache, once.

The five nationwide rasters :mod:`trails.io.sources.nmd` reads are 10 GB each
unpacked and take a while to convert; this does that ahead of a build, so
``make vegetation PARK=abisko`` finds them ready. Every layer already converted
is skipped, so it is safe to run again. A zip that is still arriving under
another process's ``.part`` name is waited for rather than fetched twice.

Run with::

    command make nmd
"""

import sys
import time
from pathlib import Path

from trails.io.sources import nmd


def main() -> int:
    """Convert every layer.

    Returns:
        Process exit status
    """
    repo_root = Path(__file__).resolve().parents[2]
    source = nmd.Source(cache_dir=repo_root / ".cache")
    for layer in nmd.LAYERS:
        partial = source.cache_dir / f"{layer.zip_stem}.zip.part"
        while partial.exists():
            print(f"Waiting for {partial.name} to finish arriving...", flush=True)
            time.sleep(30)
        started = time.time()
        file = source.layer_file(layer)
        print(f"{file.name} ready ({time.time() - started:,.0f} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

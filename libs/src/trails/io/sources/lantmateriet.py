"""Lantmäteriet's topographic web map, as tiles copied out of its open download.

The tiles Lantmäteriet serves live are a paid product. The same cartography is
published free of charge, with attribution, as *Topografisk webbkarta
Nedladdning, raster*: one GeoPackage per sheet and projection covering the whole
of Sweden, on an anonymous FTP server. The Web Mercator file is a plain XYZ
pyramid — tile matrix set EPSG:3857, 256 px, z0 to z17, ``tile_row`` counted
from the top — so its rows are Leaflet's ``{z}/{x}/{y}`` addresses and copy out
without reprojection or resampling. Measured 2026-09-12: the box's centre tile
at z13 against the same address from the live service differs by a mean of
0.77 of 255 in luminance and not at all in position; the file's PNG is indexed
and less than half the size.

**The file is 156 GB and is never downloaded.** It is opened as an SQLite
database over FTP byte ranges (:mod:`trails.io.remote_sqlite`) and only the
rows for the wanted box are read — 0.048 s a tile when read in order, because
the rows sit in spatial chunks and a 1 MB block holds many neighbours::

    source = lantmateriet.Source()
    written = source.copy_tiles((18.15, 68.17, 19.00, 68.46), zooms=range(8, 18), out_dir=Path("tiles"))

Tiles are written as ``{out_dir}/{z}/{x}/{y}.png`` and a run resumes: a tile
already on disk is not read again.
"""

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ...utils.tiles import Bounds, tile_count, tile_range
from ..remote_sqlite import FtpFile, RangeReader, RemoteDatabase

#: Lantmäteriet's open-data FTP server; anonymous.
FTP_HOST = "download-opendata.lantmateriet.se"

#: The colour sheet in Web Mercator. The grey sheet (``Nedtonad_05m_mercator``)
#: and the two SWEREF 99 TM files sit beside it and are not used.
FTP_PATH = "Topografisk_webbkarta_raster/Farg_05m_mercator/1159000_7377433.gpkg"

#: The tile table inside the GeoPackage, and its one sheet.
TILE_TABLE = "topowebb"

#: Finest level in the file. Kartverket's cache goes one further; at 68° N a
#: z17 pixel is 0.44 m, and z18 would be the same strokes scaled up.
MAX_ZOOM = 17

#: Coarsest level worth copying for a map of one area: at z8 the box is two tiles.
MIN_ZOOM = 8

#: Where the copy records what it did, beside the tiles.
INDEX_FILE = "index.json"

__all__ = ["Bounds", "tile_count", "tile_range", "Source", "SourceMetadata", "METADATA"]


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the tiles."""

    name: str = "Topografisk webbkarta Nedladdning, raster"
    provider: str = "Lantmäteriet"
    country: str = "SE"
    url: str = f"ftp://{FTP_HOST}/{FTP_PATH.rsplit('/', 2)[0]}/"
    license: str = "Användningsvillkor för värdefulla datamängder"
    attribution: str = "© Lantmäteriet"


METADATA = SourceMetadata()


class Source:
    """The tile file, read over FTP."""

    def __init__(self, reader: RangeReader | None = None):
        """Point at the file.

        Args:
            reader: Where the GeoPackage's bytes come from; the FTP file by
                default, anything else in a test
        """
        self.reader: RangeReader = reader if reader is not None else FtpFile(FTP_HOST, FTP_PATH)

    def copy_tiles(self, bounds: Bounds, zooms: Iterable[int], out_dir: Path) -> dict[str, object]:
        """Copy every tile of a box into ``out_dir`` as ``{z}/{x}/{y}.png``.

        Reads column by column within each zoom, which follows the file's own
        order closely enough that most tiles come out of a block already
        fetched. Tiles already on disk are skipped, so a run can be stopped and
        resumed. What was done is written to ``index.json`` beside the tiles.

        Args:
            bounds: The box, WGS 84
            zooms: Zoom levels to copy, each between :data:`MIN_ZOOM` and :data:`MAX_ZOOM`
            out_dir: Root of the tile tree

        Returns:
            The index that was written: bounds, zooms, per-zoom counts, the bytes
            on disk for every tile of the box whether written now or earlier,
            and the source file's modification time

        Raises:
            ValueError: If a zoom lies outside the file's levels
        """
        levels = sorted(set(zooms))
        for zoom in levels:
            if not 0 <= zoom <= MAX_ZOOM:
                raise ValueError(f"zoom {zoom} is not in the file; it holds z0 to z{MAX_ZOOM}")
        out_dir.mkdir(parents=True, exist_ok=True)
        modified = self.reader.modified if isinstance(self.reader, FtpFile) else None
        per_zoom: dict[str, dict[str, int]] = {}
        started = time.time()
        total = tile_count(bounds, levels)
        done = 0
        # flush=True throughout: under systemd there is no terminal, and a buffered
        # progress line is one nobody reads until the run is over.
        print(f"Copying {total:,} tiles for z{levels[0]}–z{levels[-1]} from {FTP_HOST}...", flush=True)
        with RemoteDatabase(self.reader) as db:
            for zoom in levels:
                x0, y0, x1, y1 = tile_range(bounds, zoom)
                wanted = (x1 - x0 + 1) * (y1 - y0 + 1)
                written = skipped = missing = 0
                size = 0
                level_started = time.time()
                for x in range(x0, x1 + 1):
                    column_dir = out_dir / str(zoom) / str(x)
                    column_dir.mkdir(parents=True, exist_ok=True)
                    present: dict[int, int] = {}
                    for kept in column_dir.glob("*.png"):
                        held = kept.stat().st_size
                        if held > 0:
                            present[int(kept.stem)] = held
                    ys = [y for y in range(y0, y1 + 1) if y not in present]
                    for y in range(y0, y1 + 1):
                        if y in present:
                            skipped += 1
                            size += present[y]  # the index is an inventory of the tree, not of one run
                    if not ys:
                        continue
                    found: dict[int, bytes] = {}
                    rows = db.execute(
                        f"SELECT tile_row, tile_data FROM {TILE_TABLE} WHERE zoom_level = ? AND tile_column = ? AND tile_row BETWEEN ? AND ?",
                        (zoom, x, min(ys), max(ys)),
                    )
                    for y, data in rows:
                        if y in ys:
                            found[y] = data
                    for y in ys:
                        data = found.get(y)
                        if data is None:
                            missing += 1
                            continue
                        target = column_dir / f"{y}.png"
                        partial = target.with_suffix(".part")
                        partial.write_bytes(data)
                        partial.replace(target)
                        written += 1
                        size += len(data)
                done += wanted
                elapsed = time.time() - level_started
                rate = written / elapsed if elapsed > 0 and written else 0.0
                print(
                    f"  z{zoom}: {written:,} written, {skipped:,} already there, {missing:,} missing of {wanted:,}"
                    f" — {size / 1e6:,.1f} MB, {elapsed:,.0f} s, {rate:,.1f} tiles/s; {done:,}/{total:,} overall",
                    flush=True,
                )
                per_zoom[str(zoom)] = {"tiles": wanted, "written": written, "skipped": skipped, "missing": missing, "bytes": size}
        index: dict[str, object] = {
            "source": f"ftp://{FTP_HOST}/{FTP_PATH}",
            "source_modified": modified,
            "bounds": list(bounds),
            "zooms": levels,
            "tiles": total,
            "per_zoom": per_zoom,
            "seconds": round(time.time() - started, 1),
            "transfer": str(self.reader.stats) if isinstance(self.reader, FtpFile) else None,
        }
        (out_dir / INDEX_FILE).write_text(json.dumps(index, indent=2), encoding="utf-8")
        print(f"Done in {index['seconds']:,} s; index written to {out_dir / INDEX_FILE}", flush=True)
        return index

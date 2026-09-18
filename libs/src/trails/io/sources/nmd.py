"""Naturvårdsverket's *Nationella marktäckedata 2018*: the laser-measured height and cover of low vegetation.

**What the map cannot say about the ground, this does.** The sheet draws forest,
open land and water; it does not say whether the open land is knee-high
dwarf birch or head-high willow, and that is the difference between a valley
crossed in an hour and one crossed in a day. NMD's supplementary layer
*Objekthöjd och objekttäckning* answers it from Lantmäteriet's laser scanning
of 2009–2017 at 10 m: for every cell, the height class of what stands between
0.5 and 5 m, how much of the cell it covers, and the same pair for what stands
above 5 m. Measured over the Abisko box (analysis/docs/abisko-decisions.md
§6.11): 26 % of the ground carries something between 0.5 and 5 m, 8 % has trees
above it, and the rest is bare, water, or rock.

**Nationwide rasters, converted once and read by window.** The object files
are Erdas Imagine, 65,520 × 153,936 cells of 10 m in SWEREF 99 TM, some 10 GB
each unpacked and almost all of it nothing; the base land cover is a GeoTIFF
of 71,273 × 157,992 on a grid of its own. They are fetched, converted to a
deflate GeoTIFF of a tenth the size, and thrown away; every later box is a
window read of the converted file, so the second map in Sweden costs nothing
over the network and a map anywhere in the country is the same call.

**Three kinds of nothing.** NMD writes 255 both where the laser found no
object and where it has no word at all, and the delivery's own metadata
raster names the flight strip of every cell it has one for, 0 elsewhere. What
that 0 covers was measured over the Abisko box on 2026-09-18 rather than
assumed: 13 % of the cells, two thirds of them Torneträsk, the rest the
smaller lakes, the river network and the strip past the Norwegian border --
not, as first read, an unflown corner; Riksgränsen itself is classed. The
laser gets nothing back off water, and NMD computes no object over it. So
this module reads a fifth raster, the base land cover, and tells three
things apart: 0 for *no object* where the strips are, 0 again for water
(:data:`WATER_CLASSES`) where they are not -- known and empty, as the
Norwegian source treats its fjords -- and :data:`UNKNOWN` only where the
laser has no word and the ground is not water: past the border, or a gap in
the scanning. The tiles draw that last one as a class of its own
(:mod:`trails.processing.vegetation_tiles`), so a blank means *nothing there*
and grey means *nobody looked*.

**A hole smaller than three cells across is not a gap.** With the water
taken out, what had no strip over the Abisko box was 30,109 patches, and
27,429 of them one or two cells: a cell the laser got too little back from
to class -- a pond the base layer does not list, a wet mire, a snow patch --
scattered through ground that was flown. Drawn grey they would be a speckle
over the whole map, and they are not what a walker means by *unsurveyed*.
So the gap is opened with a 3 × 3 window, :data:`GAP_CELLS`, and a hole
narrower than that is bare like the water round it; what survives over
Abisko is 53 patches on 0.17 % of the box -- the 2.5 km strip past the
Norwegian border, a 10 ha island in Torneträsk the strips did not cross,
and small ones -- which is the grey, and the honest one.

::

    source = nmd.Source(cache_dir=".cache")
    codes, transform = source.structure((18.15, 68.139, 19.10, 68.46))

``codes`` is three bands of ``uint8`` at 10 m: the low height class
(:data:`LOW_HEIGHT_CODES`), the low cover class and the tall cover class
(:data:`COVER_CODES`) -- NMD's own codes, which
:mod:`trails.io.sources.hoydedata_vegetation` computes for Norway so the tiles
are cut from one vocabulary.
"""

import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import rasterio.windows
from affine import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from ...utils.tiles import Bounds

#: Where the delivery is published, one zip per raster, no login.
BASE_URL = "https://geodata.naturvardsverket.se/nedladdning/marktacke/NMD2018/"

#: The rasters' projection: SWEREF 99 TM.
CRS = "EPSG:3006"

#: Cell size, in metres.
CELL_M = 10.0

#: What the codes carry where the laser has not been: told apart from 0, which
#: is *scanned and nothing there*, or water.
UNKNOWN = 255

#: The base land cover's water classes: 61 *sjö och vattendrag* (lake and
#: watercourse), 62 *hav* (sea). No object is computed over either.
WATER_CLASSES = (61, 62)

#: The narrowest gap in the flight strips kept as unknown, in cells a side:
#: a hole the 3 × 3 opening closes is bare. See the module docstring.
GAP_CELLS = 3

#: NMD's height classes for objects between 0.5 and 5 m: the code is the class's
#: upper bound in metres, and 0 is no object.
LOW_HEIGHT_CODES = {1: (0.5, 1.0), 3: (1.0, 3.0), 5: (3.0, 5.0)}

#: NMD's cover classes, for either height band: the code is the class's upper
#: bound in per cent, and 0 is no object. Cover is what share of a 10 m cell
#: the objects of the band stand on.
COVER_CODES = (5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)

#: The three bands of what :meth:`Source.structure` answers, in order.
BANDS = ("low_height", "low_cover", "tall_cover")

#: Seconds an HTTP request may take: a zip is up to 1.8 GB.
TIMEOUT_S = 3600

#: Rows converted at a time. A stripe of the full width is 67 MB of ``uint8``.
STRIPE_ROWS = 1024


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the codes."""

    name: str = "Nationella marktäckedata 2018, tilläggsskikt objekthöjd och objekttäckning"
    provider: str = "Naturvårdsverket"
    country: str = "SE"
    url: str = BASE_URL
    license: str = "CC0"
    attribution: str = "© Naturvårdsverket (NMD 2018)"
    #: When the laser flew: the class of a cell is the ground as it was then.
    surveyed: str = "2009–2017"


METADATA = SourceMetadata()


@dataclass(frozen=True)
class Layer:
    """One of the delivery's rasters, and what it becomes in the cache."""

    #: The zip's stem on the server.
    zip_stem: str
    #: The raster's stem inside it: an Erdas ``.img`` for the object layers,
    #: a GeoTIFF for the base land cover, and either is read the same way.
    img_stem: str
    #: What the converted file is called.
    cached: str
    #: Whether the raster is converted to a 0/1 mask rather than kept as codes.
    as_mask: bool = False
    #: If given, the raster is converted to a 0/1 mask of these values instead.
    values: tuple[int, ...] = ()


#: The five rasters, in the order they are read: three of codes, the flight
#: strips as a mask, and the base land cover as a mask of its water.
LAYERS = (
    Layer("Objekt_hojd_intervall_0_5_till_5_v1_3", "objekt_hojd_intervall_0_5_till_5_v1_3", "low_height.tif"),
    Layer("Objekt_tackning_hojdintervall_0_5_till_5_v1_3", "objekt_tackning_hojdintervall_0_5_till_5_v1_3", "low_cover.tif"),
    Layer("Objekt_tackning_hojdintervall_5_till_45_v1_3", "objekt_tackning_hojdintervall_5_till_45_v1_3", "tall_cover.tif"),
    Layer("Objekt_metadata_flygstraksdatum_v1_3", "objekt_metadata_flygstraksdatum_v1_3", "scanned.tif", as_mask=True),
    Layer("NMD2018_basskikt_ogeneraliserad_Sverige_v1_1", "nmd2018bas_ogeneraliserad_v1_1", "water.tif", values=WATER_CLASSES),
)


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "trails-analysis/0.1 (+https://github.com/ueisele/trails)"})
    partial = target.with_name(target.name + ".part")
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer, partial.open("wb") as out:
        while True:
            chunk = answer.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    partial.replace(target)


def convert(img: Path, target: Path, as_mask: bool = False, values: tuple[int, ...] = ()) -> None:
    """Rewrite one Erdas raster as a tiled, deflated GeoTIFF, stripe by stripe.

    Args:
        img: The ``.img`` file, with its ``.ige`` beside it
        target: The GeoTIFF to write
        as_mask: Whether to write 1 where the raster is non-zero and 0
            elsewhere, rather than the raster's own values
        values: If given, write 1 where the raster is one of these and 0
            elsewhere
    """
    as_mask = as_mask or bool(values)
    partial = target.with_suffix(".part.tif")
    with rasterio.open(img) as src:
        profile = {
            "driver": "GTiff", "width": src.width, "height": src.height, "count": 1, "dtype": "uint8", "crs": src.crs or CRS,
            "transform": src.transform, "compress": "deflate", "tiled": True, "blockxsize": 512, "blockysize": 512, "predictor": 2,
            "nodata": None if as_mask else UNKNOWN, "BIGTIFF": "IF_SAFER",
        }  # fmt: skip
        started = time.time()
        with rasterio.open(partial, "w", **profile) as out:
            for row in range(0, src.height, STRIPE_ROWS):
                rows = min(STRIPE_ROWS, src.height - row)
                window = Window(0, row, src.width, rows)
                stripe = src.read(1, window=window)
                if values:
                    stripe = np.isin(stripe, values).astype(np.uint8)
                elif as_mask:
                    stripe = (stripe != 0).astype(np.uint8)
                else:
                    stripe = stripe.astype(np.uint8)
                out.write(stripe, 1, window=window)
                if (row // STRIPE_ROWS) % 25 == 0:
                    print(f"  {row + rows:,}/{src.height:,} rows of {img.name}, {time.time() - started:,.0f} s", flush=True)
    partial.replace(target)


def opened(mask: np.ndarray, cells: int = GAP_CELLS) -> np.ndarray:
    """The mask with every patch narrower than ``cells`` a side taken out: a morphological opening with a square window.

    Erosion then dilation, each the ``cells`` × ``cells`` neighbourhood, in
    numpy alone: the raster's edge counts as outside, so a patch touching it
    survives only if it is wide enough within.

    Args:
        mask: A boolean image
        cells: Side of the square window, odd

    Returns:
        A boolean image of the same shape
    """
    reach = cells // 2
    padded = np.pad(mask, reach, constant_values=False)
    rows, cols = mask.shape
    shifts = [padded[r : r + rows, c : c + cols] for r in range(cells) for c in range(cells)]
    eroded = np.logical_and.reduce(shifts)
    padded = np.pad(eroded, reach, constant_values=False)
    shifts = [padded[r : r + rows, c : c + cols] for r in range(cells) for c in range(cells)]
    result: np.ndarray = np.logical_or.reduce(shifts)
    return result


class Source:
    """The delivery, converted once and read by window."""

    def __init__(self, cache_dir: str | Path = ".cache", fetch: Callable[[str, Path], None] = _download):
        """Point at the delivery.

        Args:
            cache_dir: Where the converted rasters and each box's cut are kept
            fetch: How a zip is downloaded to a file; the server by default
        """
        self.cache_dir = Path(cache_dir) / "vegetation" / "nmd2018"
        self.fetch = fetch

    def layer_file(self, layer: Layer) -> Path:
        """Where one converted raster lives, fetching and converting it if it does not yet.

        Args:
            layer: The raster

        Returns:
            The GeoTIFF
        """
        target = self.cache_dir / layer.cached
        if target.exists():
            return target
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        archive = self.cache_dir / f"{layer.zip_stem}.zip"
        if not archive.exists():
            print(f"Fetching {archive.name} from {METADATA.provider}...", flush=True)
            self.fetch(BASE_URL + archive.name, archive)
        unpacked = self.cache_dir / layer.zip_stem
        print(f"Unpacking {archive.name} ({archive.stat().st_size / 1e9:,.1f} GB)...", flush=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(unpacked)
        images = sorted(image for image in unpacked.rglob("*") if image.suffix in (".img", ".tif"))
        img = next((image for image in images if image.stem == layer.img_stem), images[0] if len(images) == 1 else None)
        if img is None:
            raise FileNotFoundError(f"{archive.name} holds no {layer.img_stem}.img or .tif; it holds {[image.name for image in images]}")
        print(f"Converting {img.name} to {target.name}...", flush=True)
        convert(img, target, as_mask=layer.as_mask, values=layer.values)
        for file in sorted(unpacked.rglob("*")):
            if file.is_file():
                file.unlink()
        for folder in sorted(unpacked.rglob("*"), reverse=True):
            folder.rmdir()
        unpacked.rmdir()
        archive.unlink()
        print(f"  {target.name}: {target.stat().st_size / 1e6:,.0f} MB", flush=True)
        return target

    def _structure_file(self, bounds: Bounds) -> Path:
        stem = "_".join(f"{value:.2f}" for value in bounds).replace(".", "p").replace("-", "m")
        return self.cache_dir / f"structure_{stem}.tif"

    def structure(self, bounds: Bounds, force_download: bool = False) -> tuple[np.ndarray, Affine]:
        """The three code bands over a box, cut from the national rasters.

        Args:
            bounds: The box, WGS 84; the cut is the cells whose grid covers it
            force_download: Cut the box again even if its cut is cached

        Returns:
            ``(3, rows, cols)`` ``uint8`` in :data:`BANDS` order, and the
            georeferencing in :data:`CRS`
        """
        cached = self._structure_file(bounds)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                return kept.read(), kept.transform
        files = {layer.cached: self.layer_file(layer) for layer in LAYERS}
        west, south, east, north = transform_bounds("EPSG:4326", CRS, *bounds, densify_pts=64)
        # **The rasters do not share one grid.** The low rasters are 153,936
        # rows, the tall-cover raster 154,001 and the flight-strip raster
        # 153,903 (measured 2026-09-18), so a window is not a window: the cut
        # is fixed on the ground, in metres, off the first raster's cells, and
        # each file is read over that same ground on its own grid.
        with rasterio.open(files["low_height.tif"]) as first:
            window = from_bounds(west, south, east, north, first.transform).round_offsets().round_lengths()
            window = Window(max(0, int(window.col_off)), max(0, int(window.row_off)), int(window.width) + 1, int(window.height) + 1)
            transform = first.window_transform(window)
            ground = rasterio.windows.bounds(window, first.transform)
            low_height = first.read(1, window=window, boundless=True, fill_value=UNKNOWN)
        shape = (int(window.height), int(window.width))

        def read_over(name: str, fill: int) -> np.ndarray:
            with rasterio.open(files[name]) as file:
                own = from_bounds(*ground, file.transform).round_offsets().round_lengths()
                own = Window(int(own.col_off), int(own.row_off), shape[1], shape[0])
                read: np.ndarray = file.read(1, window=own, boundless=True, fill_value=fill)
            return read

        low_cover = read_over("low_cover.tif", UNKNOWN)
        tall_cover = read_over("tall_cover.tif", UNKNOWN)
        scanned = read_over("scanned.tif", 0) != 0
        water = read_over("water.tif", 0) != 0
        codes = np.stack([low_height, low_cover, tall_cover]).astype(np.uint8)
        # NMD's 255 is *nothing here* wherever the laser flew, band by band --
        # a cell with trees and no bush is 255 in the low bands and a code in
        # the tall one. Past the flight strips a band is unknown only over a
        # gap wide enough to mean it: water and holes narrower than the
        # opening's window are bare -- see the module docstring.
        for band in range(codes.shape[0]):
            codes[band][scanned & (codes[band] == UNKNOWN)] = 0
        gap = opened(~scanned & ~water)
        codes[:, ~scanned] = 0
        codes[:, gap] = UNKNOWN
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        with rasterio.open(
            partial, "w", driver="GTiff", height=codes.shape[1], width=codes.shape[2], count=3, dtype="uint8", crs=CRS, transform=transform,
            nodata=UNKNOWN, compress="deflate", tiled=True, blockxsize=512, blockysize=512,
        ) as out:  # fmt: skip
            out.write(codes)
            out.descriptions = BANDS
        partial.replace(cached)
        print(
            f"  structure over {bounds} cached at {cached}: {codes.shape[2]:,} × {codes.shape[1]:,} cells,"
            f" {100 * float(scanned.mean()):.1f} % scanned, {100 * float((~scanned & water).mean()):.1f} % water past the strips,"
            f" {100 * float((~scanned & ~water & ~gap).mean()):.2f} % holes taken as bare, {100 * float(gap.mean()):.2f} % unknown",
            flush=True,
        )
        return codes, transform

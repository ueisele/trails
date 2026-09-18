"""Kartverket's surface model less its terrain model: the height and cover of what stands on Norwegian ground.

Sweden publishes the laser's reading of low vegetation as classes
(:mod:`trails.io.sources.nmd`). Norway publishes the two models the classes
are computed from -- the digital surface model DOM1, every laser return that
is not noise binned by its highest, and the terrain model DTM1 under it --
and nothing derived. So this module derives it: the difference of the two is
how high whatever stands on a cell reaches, and over a 10 m cell that gives
NMD's own three numbers -- the height class of what is between 0.5 and 5 m,
the share of the cell it stands on, and the share the trees above 5 m stand
on -- in NMD's own codes, so the tiles are cut from one vocabulary on both
sides of the border (analysis/docs/abisko-decisions.md §6.11).

**Both models come off ``hoydedata.no``'s image services, the way the height
tiles already do** (:mod:`trails.io.sources.hoydedata_dtm`): a 5 km square
at 2 m posts is 26 MB and eight seconds, measured 2026-09-18, and the DOM
service answers exactly as the DTM one does. Two metres rather than one
because NMD itself rasterises the point cloud at 2 m before it classes
(its product description, §3.1), and because a metre would be four times
the bytes for a class that is decided over twenty-five samples anyway.

**The laser covers the whole Lomsdal-Visten box.** Over it at 100 m the two
models are nowhere identical and 39 % of the ground reads more than half a
metre of something on it -- measured 2026-09-17 before this was built, since a
box the laser had not flown would come back as two copies of one model and
class every cell as bare.

**And what it leaves empty is water, so the box carries no unknown.** The
surface model has no post over a lake or a fjord -- the laser gets nothing
back off still water -- and the terrain model marks the same ground as sea
(:mod:`trails.io.sources.hoydedata_dtm`). Measured 2026-09-18 over the
assembled Lomsdal-Visten box: 11 % of its cells had no post in either model,
and 5,000 of them drawn at random all sit at exactly 0.0 m in the cached
terrain mosaic, against 15 % of the cells that do have a post. So
:func:`codes_from` answers :data:`~trails.io.sources.nmd.UNKNOWN` for a cell
with no post, as it should for a cell it cannot see, and :meth:`Source.structure`
turns that into 0 -- *known, nothing there* -- before the box is cached: over
Norway the model's silence is water, and water is not ground a walker pushes
through. The Swedish source keeps 255 for the ground nobody has flown, which
the tiles draw as their own class (:mod:`trails.processing.vegetation_tiles`);
a Norwegian box gets no such patch. **The one thing this cannot tell apart is
the border**: past Norway's edge both models are empty too, so a box that
crosses into Sweden would call the Swedish side bare. Keep a Norwegian box in
Norway, or read the Swedish side from its own source.

::

    source = hoydedata_vegetation.Source(cache_dir=".cache")
    codes, transform = source.structure((12.0, 65.15, 13.75, 65.95))

The squares' codes are cached as they are computed, 500 × 500 cells each, so a
run that is stopped costs only the square it was on; the assembled codes over
the box are cached beside them.
"""

import http.client
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.io import MemoryFile

from ...utils.tiles import Bounds
from . import hoydedata_dtm
from .hoydedata_dtm import CRS, NODATA, RETRIES, TIFF_MAGIC, USER_AGENT, RefusedError, Square, request_url, squares_over
from .nmd import BANDS, CELL_M, COVER_CODES, UNKNOWN

#: The surface model's service, beside the terrain model's.
DOM_URL = "https://hoydedata.no/arcgis/rest/services/DOM/ImageServer/exportImage"

#: The terrain model's, as the height tiles read it.
DTM_URL = hoydedata_dtm.SERVICE_URL

#: Post spacing both models are read at, in metres. See the module docstring.
POSTS_M = 2.0

#: Side of one request, in metres: 2,500 posts a side at :data:`POSTS_M`,
#: 26 MB, eight seconds. A whole number of 10 m cells.
CHUNK_M = 5_000.0

#: Posts of one model along one side of a 10 m cell.
PER_CELL = int(round(CELL_M / POSTS_M))

#: Below this an object is ground, and above :data:`TALL_M` it is a tree:
#: NMD's own bands, so the codes mean the same thing on either map.
LOW_M = 0.5
TALL_M = 5.0

#: Seconds one request may take.
TIMEOUT_S = 300

#: Waited between tries, times the attempt.
BACKOFF_S = 5.0


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the codes."""

    name: str = "Nasjonal høydemodell DOM1 − DTM1"
    provider: str = "Kartverket"
    country: str = "NO"
    url: str = DOM_URL
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"
    surveyed: str = "2010–2022"


METADATA = SourceMetadata()


def _get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/tiff"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
        body: bytes = answer.read()
    return body


def cover_code(share: np.ndarray) -> np.ndarray:
    """NMD's cover class for a share of a cell, 0 where nothing stands.

    The code is the class's upper bound in per cent: a cell three tenths
    covered is 30, one covered exactly a fifth is 20, one covered by anything
    at all is at least 5.

    Args:
        share: Fraction of the cell covered, 0 to 1

    Returns:
        ``uint8`` codes, same shape
    """
    percent = np.asarray(share, dtype=np.float32) * 100.0
    edges = np.asarray(COVER_CODES, dtype=np.float32)
    # `digitize` with right=True: a value equal to an edge belongs to the class
    # that edge bounds from above, so exactly 20 % is code 20, not 30.
    index = np.digitize(percent, edges, right=True)
    codes = edges[np.minimum(index, len(edges) - 1)].astype(np.uint8)
    codes[percent <= 0.0] = 0
    return codes


def height_code(top_m: np.ndarray, present: np.ndarray) -> np.ndarray:
    """NMD's height class for the tallest low object of a cell, 0 where there is none.

    Args:
        top_m: The tallest reach of what is between :data:`LOW_M` and :data:`TALL_M`
        present: Whether anything is

    Returns:
        ``uint8`` codes 1, 3 or 5, same shape
    """
    codes = np.where(top_m <= 1.0, 1, np.where(top_m <= 3.0, 3, 5)).astype(np.uint8)
    codes[~present] = 0
    return codes


def codes_from(surface: np.ndarray, terrain: np.ndarray, nodata: float = NODATA) -> np.ndarray:
    """NMD's three codes over 10 m cells, from the two models at :data:`POSTS_M`.

    Each cell is the :data:`PER_CELL` × :data:`PER_CELL` posts under it. A post
    either model has nothing for is left out of the cell's count; a cell with
    no post at all is :data:`UNKNOWN` in every band.

    Args:
        surface: The surface model, rows from the north, a whole number of cells each way
        terrain: The terrain model, the same grid
        nodata: What either writes where it has nothing

    Returns:
        ``(3, rows, cols)`` ``uint8`` in :data:`~trails.io.sources.nmd.BANDS` order

    Raises:
        ValueError: If the models differ in shape or are not whole cells
    """
    if surface.shape != terrain.shape:
        raise ValueError(f"surface is {surface.shape} but terrain is {terrain.shape}")
    rows, cols = surface.shape
    if rows % PER_CELL or cols % PER_CELL:
        raise ValueError(f"{cols} × {rows} posts is not a whole number of {PER_CELL}-post cells")
    known = (surface != nodata) & (terrain != nodata)
    reach = np.where(known, surface - terrain, 0.0).astype(np.float32)
    low = known & (reach >= LOW_M) & (reach < TALL_M)
    tall = known & (reach >= TALL_M)
    blocks = (rows // PER_CELL, PER_CELL, cols // PER_CELL, PER_CELL)
    counted = known.reshape(blocks).sum(axis=(1, 3)).astype(np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        low_share = np.where(counted > 0, low.reshape(blocks).sum(axis=(1, 3)) / counted, 0.0)
        tall_share = np.where(counted > 0, tall.reshape(blocks).sum(axis=(1, 3)) / counted, 0.0)
    top = np.where(low, reach, 0.0).reshape(blocks).max(axis=(1, 3))
    codes = np.stack([height_code(top, low_share > 0.0), cover_code(low_share), cover_code(tall_share)])
    codes[:, counted == 0] = UNKNOWN
    return codes


class Source:
    """The two models over a box, read as squares, differenced and classed."""

    def __init__(self, cache_dir: str | Path = ".cache", fetch: object | None = None):
        """Point at the models.

        Args:
            cache_dir: Where the squares' codes and the assembled box are kept
            fetch: How one square's bytes are read; the services by default, a
                stand-in in a test
        """
        self.cache_dir = Path(cache_dir) / "vegetation" / "hoydedata"
        self.fetch = fetch if fetch is not None else _get_bytes

    def _square_file(self, square: Square) -> Path:
        return self.cache_dir / f"codes_{square.name}.tif"

    def _structure_file(self, bounds: Bounds) -> Path:
        stem = "_".join(f"{value:.2f}" for value in bounds).replace(".", "p").replace("-", "m")
        return self.cache_dir / f"structure_{stem}.tif"

    def _read_model(self, square: Square, service: str) -> np.ndarray:
        url = request_url(square, service)
        for attempt in range(1, RETRIES + 1):
            try:
                body = self.fetch(url)  # type: ignore[operator]
                if not body.startswith(TIFF_MAGIC):
                    raise RefusedError(f"not a TIFF: {body[:200]!r}")
                with MemoryFile(body) as held, held.open() as arrived:
                    posts: np.ndarray = arrived.read(1)
                if posts.shape != (square.height, square.width):
                    raise RefusedError(f"came back {posts.shape[1]} × {posts.shape[0]}, not {square.width} × {square.height}")
                return posts
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, RefusedError) as refused:
                if attempt == RETRIES:
                    raise RuntimeError(f"{METADATA.name} did not answer for {square.name} after {RETRIES} tries: {refused}") from refused
                time.sleep(BACKOFF_S * attempt)
        raise AssertionError("unreachable")

    def read_square(self, square: Square, force_download: bool = False) -> np.ndarray:
        """One square's codes, off the cache or computed from the two models.

        Args:
            square: The square, at :data:`POSTS_M`
            force_download: Read the models again even if the codes are cached

        Returns:
            ``(3, cells, cells)`` ``uint8``
        """
        cached = self._square_file(square)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                read: np.ndarray = kept.read()
            return read
        codes = codes_from(self._read_model(square, DOM_URL), self._read_model(square, DTM_URL))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        west, _south, _east, north = square.bounds
        with rasterio.open(
            partial, "w", driver="GTiff", height=codes.shape[1], width=codes.shape[2], count=3, dtype="uint8", crs=CRS,
            transform=Affine(CELL_M, 0.0, west, 0.0, -CELL_M, north), nodata=UNKNOWN, compress="deflate", tiled=True,
            blockxsize=256, blockysize=256,
        ) as out:  # fmt: skip
            out.write(codes)
            out.descriptions = BANDS
        partial.replace(cached)
        return codes

    def structure(self, bounds: Bounds, force_download: bool = False) -> tuple[np.ndarray, Affine]:
        """The three code bands over a box, one square at a time.

        Args:
            bounds: The box, WGS 84. Every square touching it is read.
            force_download: Read the models again even if the codes are cached

        Returns:
            ``(3, rows, cols)`` ``uint8`` in :data:`~trails.io.sources.nmd.BANDS`
            order, and the georeferencing in :data:`CRS`. No cell is
            :data:`~trails.io.sources.nmd.UNKNOWN`: where the models have no
            post the ground is water, and it is 0 (see the module docstring).
        """
        cached = self._structure_file(bounds)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                return kept.read(), kept.transform
        squares, posts, across, down = squares_over(bounds, POSTS_M, CHUNK_M)
        cols, rows = across // PER_CELL, down // PER_CELL
        transform = Affine(CELL_M, 0.0, posts.c, 0.0, -CELL_M, posts.f)
        codes = np.full((3, rows, cols), UNKNOWN, dtype=np.uint8)
        started = time.time()
        print(f"Reading {len(squares)} squares of {METADATA.name} at {POSTS_M:g} m into {cols:,} × {rows:,} cells of {CELL_M:g} m...", flush=True)
        for number, square in enumerate(squares, start=1):
            patch = self.read_square(square, force_download=force_download)
            row = int(round((posts.f - square.bounds[3]) / CELL_M))
            col = int(round((square.bounds[0] - posts.c) / CELL_M))
            codes[:, row : row + patch.shape[1], col : col + patch.shape[2]] = patch
            if number % 10 == 0 or number == len(squares):
                print(f"  {number}/{len(squares)} squares, {time.time() - started:,.0f} s", flush=True)
        # A cell no model has a post for is water, not unflown ground: see
        # the module docstring for the measurement. Known and empty, then.
        water = codes[0] == UNKNOWN
        codes[:, water] = 0
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        with rasterio.open(
            partial, "w", driver="GTiff", height=rows, width=cols, count=3, dtype="uint8", crs=CRS, transform=transform,
            nodata=UNKNOWN, compress="deflate", tiled=True, blockxsize=512, blockysize=512,
        ) as out:  # fmt: skip
            out.write(codes)
            out.descriptions = BANDS
        partial.replace(cached)
        print(
            f"  structure cached at {cached}: {100 * float(water.mean()):.1f} % of cells water or past the model's edge, taken as bare,"
            f" {100 * float((codes[0] > 0).mean()):.1f} % with something 0.5–5 m",
            flush=True,
        )
        return codes, transform

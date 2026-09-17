"""Kartverket's national height model as a raster, read square by square over HTTP.

:mod:`trails.io.sources.hoydedata` asks the same model for *points* -- fifty at
a time, which is the cheap way to thread heights along a line. This is the other
question: the ground over an *area*, which is what a tile tree is cut from
(analysis/docs/abisko-decisions.md §6.10). Sweden's side of that is
:mod:`trails.io.sources.markhojd`, and this module answers with the same two
things -- an array of heights and its georeferencing -- so
:mod:`trails.processing.dem_tiles`, :mod:`~trails.processing.shade_tiles` and
:mod:`~trails.processing.slope_tiles` cut a Norwegian tree exactly as they cut a
Swedish one::

    source = hoydedata_dtm.Source(cache_dir=".cache")
    heights, transform = source.mosaic((12.0, 65.15, 13.75, 65.95), posts_m=4.0)

**No login and no order.** ``hoydedata.no``'s ArcGIS *ImageServer* serves the
mosaic behind høydedata.no and answers ``exportImage`` with a georeferenced
float32 GeoTIFF at whatever pixel size is asked for, up to :data:`MAX_PX` a
side. Measured 2026-09-17 over Lomsdal-Visten: 10 × 10 km at 4 m posts is 26 MB
in 13 s, at 8 m posts 6.6 MB in 2.7 s, and the answer's transform is exactly the
grid that was asked for.

**It is the same model the point service reads.** 182 posts of an 8 m read,
asked of ``ws.geonorge.no/hoydedata/v1/punkt`` at their own coordinates, agree
to a median of **0.10 m**, p95 0.47 m, worst 1.02 m -- so a height off these
tiles and a height off that service are one surface, which is what §6.8 requires
of the profile and the picker.

**The sea is 0 m, and the model says so itself.** Over the fjords the raster
carries a flat 0.0 rather than a hole: sampled, every one of those cells comes
back from the point service as ``terreng: "Havflate"``. Past the model's own
edge -- the open sea west of the coast -- it carries :data:`NODATA` instead, and
those cells sample as ``Havflate`` too (98 of 100; the other two are ``dtm1``
on the shoreline itself). So what the model leaves empty is sea, and
:meth:`Source.mosaic` fills it with :data:`SEA_M` rather than carrying it as a
gap. A hole left in place would be worse than wrong: the relief fills a blank
patch with the median of its neighbours, which would draw a cliff along every
kilometre of coastline and class it as the steepest ground on the map.

The squares are cached as they arrive, under ``cache_dir/elevation/hoydedata/``,
and the assembled mosaic beside them, so a second build over the same box reads
nothing over the network and a build over part of it reads nothing new.
"""

import http.client
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.warp import transform_bounds

from ...utils.tiles import Bounds

#: The service, keyless. ``hoydedata.no`` is Kartverket's own height portal and
#: this is the mosaic behind it.
SERVICE_URL = "https://hoydedata.no/arcgis/rest/services/DTM/ImageServer/exportImage"

#: The squares' projection, and the mosaic's: EUREF89 UTM 33N, which is the
#: metric grid the Norwegian network is already built in, so nothing on this
#: path reprojects anything.
CRS = "EPSG:25833"

#: What the service writes where it has nothing, and what the cached mosaic
#: declares. The mosaic itself holds none of it: see :data:`SEA_M`.
NODATA = -9999.0

#: What an empty cell is filled with. The model stops at the coast and the sea
#: beyond it is sea, which is at nought metres; see the module docstring for how
#: that was established rather than assumed.
SEA_M = 0.0

#: Side of one request, in metres. At 4 m posts that is 2,500 px a side, a sixth
#: of what the service allows, and about 26 MB and 13 s -- small enough that a
#: failed square is cheap to ask for again and big enough that the box is ninety
#: requests rather than nine hundred.
CHUNK_M = 10_000.0

#: Pixels the service allows per side, its own ``maxImageWidth``/``maxImageHeight``.
MAX_PX = 15_000

#: Seconds one request may take. A 4 m square is 26 MB.
TIMEOUT_S = 300

#: How many times a square is asked for before the build gives up, and how long
#: it waits between tries. This is somebody else's public service: a failure is
#: waited out rather than hammered.
RETRIES = 4
BACKOFF_S = 5.0

#: Sent so the service's operators can identify the client, as
#: :mod:`trails.io.sources.hoydedata` and :mod:`~trails.io.sources.overpass` do.
USER_AGENT = "trails-analysis/0.1 (+https://github.com/ueisele/trails)"

#: What a TIFF starts with, little- or big-endian. Checked because the service
#: answers a refusal with a 200 and a JSON body (see :meth:`Source.read_square`).
TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


class RefusedError(Exception):
    """The service answered, and what it answered is not a square of the model."""


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the heights."""

    name: str = "Nasjonal høydemodell DTM"
    provider: str = "Kartverket"
    country: str = "NO"
    url: str = SERVICE_URL
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"
    datum: str = "NN2000"


METADATA = SourceMetadata()


@dataclass(frozen=True)
class Square:
    """One request's worth of the model."""

    #: ``(min_east, min_north, max_east, max_north)`` in :data:`CRS`, on the post grid.
    bounds: tuple[float, float, float, float]
    #: Posts across and down.
    width: int
    height: int

    @property
    def name(self) -> str:
        """What the square is cached as: its own south-west corner, in metres."""
        return f"{int(round(self.bounds[0]))}_{int(round(self.bounds[1]))}"


def _snap(value: float, step: float, up: bool) -> float:
    """Move a coordinate onto a grid of ``step``, outwards.

    Args:
        value: The coordinate, in metres
        step: The grid spacing, in metres
        up: Whether to move it up rather than down

    Returns:
        The nearest multiple of ``step`` at or beyond ``value``
    """
    return (math.ceil(value / step) if up else math.floor(value / step)) * step


def squares_over(bounds: Bounds, posts_m: float, chunk_m: float = CHUNK_M) -> tuple[list[Square], Affine, int, int]:
    """Cut a box into the squares the service is asked for, and say where they land.

    The box is projected into :data:`CRS` and snapped outwards to the chunk
    grid, so a second box that overlaps this one asks for the same squares and
    reads them out of the cache rather than over the network.

    Args:
        bounds: The box, WGS 84
        posts_m: Post spacing wanted, in metres
        chunk_m: Side of one request, in metres; a whole number of posts

    Returns:
        The squares, the mosaic's transform, and its width and height in posts

    Raises:
        ValueError: If a square would be larger than the service allows, or
            the chunk is not a whole number of posts
    """
    side = chunk_m / posts_m
    if abs(side - round(side)) > 1e-9:
        raise ValueError(f"a {chunk_m:g} m square is not a whole number of {posts_m:g} m posts")
    if round(side) > MAX_PX:
        raise ValueError(f"a {chunk_m:g} m square at {posts_m:g} m posts is {round(side):,} px, past the service's {MAX_PX:,}")
    west, south, east, north = transform_bounds("EPSG:4326", CRS, *bounds, densify_pts=64)
    min_east, min_north = _snap(west, chunk_m, up=False), _snap(south, chunk_m, up=False)
    max_east, max_north = _snap(east, chunk_m, up=True), _snap(north, chunk_m, up=True)
    across = int(round((max_east - min_east) / posts_m))
    down = int(round((max_north - min_north) / posts_m))
    step = int(round(side))
    found = [
        Square(bounds=(one_east, one_north, one_east + chunk_m, one_north + chunk_m), width=step, height=step)
        for one_east in (min_east + column * chunk_m for column in range(int(round((max_east - min_east) / chunk_m))))
        for one_north in (min_north + row * chunk_m for row in range(int(round((max_north - min_north) / chunk_m))))
    ]
    transform = Affine(posts_m, 0.0, min_east, 0.0, -posts_m, max_north)
    return sorted(found, key=lambda square: (square.bounds[1], square.bounds[0])), transform, across, down


def request_url(square: Square) -> str:
    """The address one square is read from.

    Args:
        square: The square

    Returns:
        The ``exportImage`` call, asking for exactly the square's post grid
    """
    west, south, east, north = square.bounds
    query = urllib.parse.urlencode(
        {
            "bbox": f"{west:.3f},{south:.3f},{east:.3f},{north:.3f}",
            "bboxSR": 25833,
            "imageSR": 25833,
            "size": f"{square.width},{square.height}",
            "format": "tiff",
            "pixelType": "F32",
            "noData": f"{NODATA:g}",
            # Averaged rather than nearest: a post of the answer stands for
            # everything under it, which is what a tile built from it wants.
            "interpolation": "RSP_BilinearInterpolation",
            "f": "image",
        }
    )
    return f"{SERVICE_URL}?{query}"


class Source:
    """The model over a box, read as squares and laid into one array."""

    def __init__(self, cache_dir: str | Path = ".cache", fetch: object | None = None):
        """Point at the model.

        Args:
            cache_dir: Where the squares and the assembled mosaic are kept
            fetch: How one square's bytes are read; the service by default, a
                stand-in in a test
        """
        self.cache_dir = Path(cache_dir) / "elevation" / "hoydedata"
        self.fetch = fetch if fetch is not None else _get_bytes

    def _square_file(self, square: Square, posts_m: float) -> Path:
        return self.cache_dir / f"dtm_{posts_m:g}m_{square.name}.tif"

    def _mosaic_file(self, bounds: Bounds, posts_m: float) -> Path:
        stem = "_".join(f"{value:.2f}" for value in bounds).replace(".", "p").replace("-", "m")
        return self.cache_dir / f"mosaic_{stem}_{posts_m:g}m.tif"

    def read_square(self, square: Square, posts_m: float, force_download: bool = False) -> np.ndarray:
        """One square of the model, off the cache or off the service.

        Args:
            square: The square
            posts_m: Post spacing, which names the cached file
            force_download: Read it again even if it is cached

        Returns:
            Its heights, ``(height, width)`` float32, with :data:`NODATA` where
            the model has nothing

        Raises:
            RuntimeError: If the service does not answer after :data:`RETRIES` tries
        """
        cached = self._square_file(square, posts_m)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                read: np.ndarray = kept.read(1)
            return read
        url = request_url(square)
        body = b""
        for attempt in range(1, RETRIES + 1):
            try:
                body = self.fetch(url)  # type: ignore[operator]
                # **A refusal arrives with a 200 and a JSON body.** ArcGIS
                # answers `{"error": …}` at image endpoints rather than a status,
                # and handing that to rasterio raises about a file format, which
                # reads as a broken build rather than as the service saying no.
                if not body.startswith(TIFF_MAGIC):
                    raise RefusedError(f"not a TIFF: {body[:200]!r}")
                break
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, RefusedError) as refused:
                if attempt == RETRIES:
                    raise RuntimeError(f"{METADATA.name} did not answer for {square.name} after {RETRIES} tries: {refused}") from refused
                time.sleep(BACKOFF_S * attempt)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        partial.write_bytes(body)
        with rasterio.open(partial) as arrived:
            heights: np.ndarray = arrived.read(1)
            if heights.shape != (square.height, square.width):
                raise RuntimeError(f"{square.name} came back {heights.shape[1]} × {heights.shape[0]}, not {square.width} × {square.height}")
        partial.replace(cached)
        return heights

    def mosaic(self, bounds: Bounds, posts_m: float = 4.0, force_download: bool = False) -> tuple[np.ndarray, Affine]:
        """The model over a box, as one array at the given post spacing.

        The box is cut into :data:`CHUNK_M` squares, each read at exactly the
        posts the mosaic wants, and every empty cell is filled with
        :data:`SEA_M` -- see the module docstring for why that is the sea and
        not a guess. The squares are cached as they arrive, so a run that is
        stopped costs only the square it was reading; the assembled mosaic is
        cached too, so a later build reads one file.

        Args:
            bounds: The box, WGS 84. Every square touching it is read.
            posts_m: Post spacing wanted, in metres
            force_download: Read the squares again even if they are cached

        Returns:
            The heights (rows from the north) and their georeferencing in :data:`CRS`
        """
        cached = self._mosaic_file(bounds, posts_m)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                return kept.read(1), kept.transform
        squares, transform, across, down = squares_over(bounds, posts_m)
        heights = np.full((down, across), SEA_M, dtype=np.float32)
        max_north = transform.f
        min_east = transform.c
        started = time.time()
        print(f"Reading {len(squares)} squares of {METADATA.name} at {posts_m:g} m into a {across:,} × {down:,} mosaic...", flush=True)
        empty = 0
        for number, square in enumerate(squares, start=1):
            patch = self.read_square(square, posts_m, force_download=force_download)
            blank = patch == NODATA
            empty += int(blank.sum())
            if blank.any():
                patch = np.where(blank, np.float32(SEA_M), patch)
            row = int(round((max_north - square.bounds[3]) / posts_m))
            column = int(round((square.bounds[0] - min_east) / posts_m))
            heights[row : row + square.height, column : column + square.width] = patch
            if number % 10 == 0 or number == len(squares):
                print(f"  {number}/{len(squares)} squares, {time.time() - started:,.0f} s", flush=True)
        print(f"  {empty:,} posts the model leaves empty ({100.0 * empty / heights.size:.1f} %), filled with {SEA_M:g} m — open sea", flush=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        with rasterio.open(
            partial, "w", driver="GTiff", height=down, width=across, count=1, dtype="float32", crs=CRS, transform=transform, nodata=NODATA,
            compress="deflate", tiled=True, blockxsize=512, blockysize=512,
        ) as out:  # fmt: skip
            out.write(heights, 1)
        partial.replace(cached)
        print(f"  mosaic cached at {cached} ({cached.stat().st_size / 1e6:,.1f} MB)", flush=True)
        return heights, transform


def _get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/tiff"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
        body: bytes = answer.read()
    return body

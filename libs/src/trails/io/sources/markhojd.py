"""Lantmäteriet's *Markhöjdmodell Nedladdning*: the 1 m height model, read by range.

The model is published as one cloud-optimised GeoTIFF per 2.5 km square in
SWEREF 99 TM with RH 2000 heights (EPSG:5845), 2,500 × 2,500 float32 posts,
deflate, 512-px blocks, overviews at 2, 4 and 8 -- measured 2026-09-12,
analysis/docs/abisko-decisions.md §6.3. A keyless STAC API says which squares
cover a box; the files themselves sit behind HTTP basic auth with the
Geotorget login, which the environment carries as :data:`USERNAME_VAR` and
:data:`PASSWORD_VAR`, and answer byte ranges, so a square is read at the
overview a tile needs and never fetched whole.

**Water is a flat surface, not nodata**: a square on Torneträsk reads 341.85 m
at every post. The model's nodata is −9999 and the squares over Abisko hold
none of it.

::

    source = markhojd.Source(cache_dir=".cache")
    heights, transform = source.mosaic((18.15, 68.17, 19.00, 68.46), posts_m=4.0)

The mosaic is cached as a GeoTIFF under ``cache_dir/elevation/``, so a second
build reads nothing over the network.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.enums import Resampling

from ...utils.tiles import Bounds

#: The STAC API, keyless: search by bbox needs no login.
STAC_URL = "https://api.lantmateriet.se/stac-hojd/v1"

#: The collection the 1 m model is in.
COLLECTION = "mhm-75_6"

#: Environment variables carrying the Geotorget login. They live in
#: ``home/trails-map``'s sops file and reach the build through ``sops exec-env``.
USERNAME_VAR = "GEOTORGET_USERNAME"
PASSWORD_VAR = "GEOTORGET_PASSWORD"

#: The squares' projection: SWEREF 99 TM, heights in RH 2000.
CRS = "EPSG:5845"

#: The model's no-data value.
NODATA = -9999.0

#: Post spacing of the model itself, in metres.
POST_M = 1.0

#: Side of one square, in metres.
SQUARE_M = 2500.0

#: Items asked for per STAC page.
PAGE_SIZE = 500

#: Seconds an HTTP request may take.
TIMEOUT_S = 120


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the heights."""

    name: str = "Markhöjdmodell Nedladdning, grid 1+"
    provider: str = "Lantmäteriet"
    country: str = "SE"
    url: str = STAC_URL
    license: str = "CC BY 4.0"
    attribution: str = "© Lantmäteriet"
    datum: str = "RH 2000"


METADATA = SourceMetadata()


@dataclass(frozen=True)
class Square:
    """One 2.5 km square of the model."""

    id: str
    href: str
    #: ``(min_east, min_north, max_east, max_north)`` in :data:`CRS`.
    bounds: tuple[float, float, float, float]


def _get_json(url: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"Accept": "application/geo+json, application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
        data: dict[str, object] = json.load(answer)
    return data


def squares_from(page: dict[str, object]) -> list[Square]:
    """Read the squares out of one STAC page.

    Args:
        page: The page, as the API answers it

    Returns:
        The squares, in the page's order
    """
    found = []
    features = page.get("features", [])
    assert isinstance(features, list)
    for feature in features:
        properties = feature["properties"]
        bbox = properties["proj:bbox"]
        found.append(Square(id=feature["id"], href=feature["assets"]["data"]["href"], bounds=(bbox[0], bbox[1], bbox[2], bbox[3])))
    return found


def search(bounds: Bounds, fetch: Callable[[str], dict[str, object]] = _get_json) -> list[Square]:
    """Which squares cover a box.

    Args:
        bounds: The box, WGS 84
        fetch: How a page is read; the API by default, a stand-in in a test

    Returns:
        The squares, sorted by id, every page followed
    """
    query = urllib.parse.urlencode({"bbox": ",".join(f"{value:.6f}" for value in bounds), "limit": PAGE_SIZE}, safe=",")
    url: str | None = f"{STAC_URL}/collections/{COLLECTION}/items?{query}"
    found: list[Square] = []
    while url:
        page = fetch(url)
        found.extend(squares_from(page))
        links = page.get("links", [])
        assert isinstance(links, list)
        url = next((link["href"] for link in links if link.get("rel") == "next"), None)
    return sorted(found, key=lambda square: square.id)


class Source:
    """The model, read square by square at the overview a build needs."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache",
        username: str | None = None,
        password: str | None = None,
        fetch: Callable[[str], dict[str, object]] = _get_json,
    ):
        """Point at the model.

        Args:
            cache_dir: Where the assembled mosaic is kept between builds
            username: Geotorget login; :data:`USERNAME_VAR` by default
            password: Geotorget password; :data:`PASSWORD_VAR` by default
            fetch: How a STAC page is read
        """
        self.cache_dir = Path(cache_dir) / "elevation"
        self.username = username if username is not None else os.environ.get(USERNAME_VAR, "")
        self.password = password if password is not None else os.environ.get(PASSWORD_VAR, "")
        self.fetch = fetch

    def _cache_file(self, bounds: Bounds, posts_m: float) -> Path:
        stem = "_".join(f"{value:.2f}" for value in bounds).replace(".", "p").replace("-", "m")
        return self.cache_dir / f"markhojd_{stem}_{posts_m:g}m.tif"

    def mosaic(self, bounds: Bounds, posts_m: float = 4.0, force_download: bool = False) -> tuple[np.ndarray, Affine]:
        """The model over a box, as one array at the given post spacing.

        Each square is read at the overview that matches ``posts_m`` -- the
        model carries 1, 2, 4 and 8 m -- by range requests against the file,
        and laid into a grid aligned to the squares. The result is cached as a
        GeoTIFF; a later call reads that.

        Args:
            bounds: The box, WGS 84. Every square touching it is read.
            posts_m: Post spacing wanted; one of the model's overview levels
            force_download: Read the squares again even if the mosaic is cached

        Returns:
            The heights (rows from the north) and their georeferencing in :data:`CRS`

        Raises:
            ValueError: If ``posts_m`` is not a level the files carry
            RuntimeError: If the box has no squares, or the login is missing
        """
        if posts_m not in (1.0, 2.0, 4.0, 8.0):
            raise ValueError(f"posts_m must be 1, 2, 4 or 8 (the model's overviews); got {posts_m}")
        cached = self._cache_file(bounds, posts_m)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                return kept.read(1), kept.transform
        squares = search(bounds, self.fetch)
        if not squares:
            raise RuntimeError(f"no squares of {COLLECTION} cover {bounds}")
        if not (self.username and self.password):
            raise RuntimeError(f"the files need the Geotorget login; set {USERNAME_VAR} and {PASSWORD_VAR}")
        min_east = min(square.bounds[0] for square in squares)
        min_north = min(square.bounds[1] for square in squares)
        max_east = max(square.bounds[2] for square in squares)
        max_north = max(square.bounds[3] for square in squares)
        side = int(round(SQUARE_M / posts_m))
        cols = int(round((max_east - min_east) / posts_m))
        rows = int(round((max_north - min_north) / posts_m))
        heights = np.full((rows, cols), NODATA, dtype=np.float32)
        transform = Affine(posts_m, 0.0, min_east, 0.0, -posts_m, max_north)
        started = time.time()
        print(f"Reading {len(squares)} squares of {METADATA.name} at {posts_m:g} m into a {cols:,} × {rows:,} mosaic...", flush=True)
        # The login goes to GDAL through its own setting, never onto a URL. No
        # directory listing: the file is named, and dl1 has no listing to give.
        with rasterio.Env(GDAL_HTTP_USERPWD=f"{self.username}:{self.password}", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            for number, square in enumerate(squares, start=1):
                with rasterio.open(self.read_path(square)) as file:
                    tile = file.read(1, out_shape=(side, side), resampling=Resampling.nearest)
                row = int(round((max_north - square.bounds[3]) / posts_m))
                col = int(round((square.bounds[0] - min_east) / posts_m))
                heights[row : row + side, col : col + side] = tile
                if number % 25 == 0 or number == len(squares):
                    print(f"  {number}/{len(squares)} squares, {time.time() - started:,.0f} s", flush=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        with rasterio.open(
            partial, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32", crs=CRS, transform=transform, nodata=NODATA,
            compress="deflate", tiled=True, blockxsize=512, blockysize=512,
        ) as out:  # fmt: skip
            out.write(heights, 1)
        partial.replace(cached)
        print(f"  mosaic cached at {cached} ({cached.stat().st_size / 1e6:,.1f} MB)", flush=True)
        return heights, transform

    def read_path(self, square: Square) -> str:
        """What rasterio opens for a square: the file over HTTP, by range.

        Args:
            square: The square

        Returns:
            A GDAL path
        """
        if square.href.startswith(("http://", "https://")):
            return "/vsicurl/" + square.href
        return square.href

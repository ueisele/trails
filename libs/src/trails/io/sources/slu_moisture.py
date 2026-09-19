"""SLU's soil-moisture map: how wet the ground is in the year's mean, modelled at 2 m off the laser.

**What it is.** *SLU Markfuktighetskarta*, made by the agricultural university
for the forest agency, Skogsstyrelsen, which publishes it as open data: the
national laser scan's terrain model run through a hydrological model (depth
to water, flow accumulation and twenty-two more maps) and a machine-learning
classifier trained on 20,000 field plots of the national forest inventory,
answering per 2 × 2 m cell how likely the ground is to be wet. The classed
variant read here folds that into three: *torr-frisk* (dry to fresh),
*frisk-fuktig* (fresh to moist) and *fuktig-blöt* (moist to wet), with open
water as a fourth. Kappa 0.69 against the plots held back, by the product
description; version 1.0 of 2020-10-07, and nothing newer since.

**Why it is read at all.** The sheet's wetlands (:mod:`.marktacke`) are the
surveyors' word and cover 0.63 % of the Abisko box's land; this map calls
3.4 % of it wet, and 87 % of that lies outside the surveyed outlines --
seepage lines, brook banks, the small mires under the sheet's threshold.
Around the Stordalen palsa mire it reads 27 % wet against 4 % on the dry
Nuolja slope (measured 2026-09-18), so it sees what a walker meets. It is a
model of the year's mean and not a survey, and the product description says
the mountains had few training plots; that is why its cells are drawn as a
class of their own, *wet ground*, and never as a mire.

**How it is read.** Skogsstyrelsen serves it two ways: an ArcGIS image
service behind an account of their own, and an FTPS server behind a login
they publish on the download page. The whole classed mosaic is one 8.4 GB
GeoTIFF there -- 325,000 × 770,000 cells, tiled 128 × 128, LZW -- and a
window read over FTPS turned out to be slower than fetching the file
(1,800 s against 800 s at 10 MB/s, 2026-09-18), so the file is fetched once
into the cache and every box is a window read of it after that. The login is
read from the environment, :data:`USERNAME_VAR` and :data:`PASSWORD_VAR`,
and is on the page :data:`METADATA` links to; it is not written here.
"""

import dataclasses
import ftplib
import os
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.windows import from_bounds


@dataclasses.dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the moisture classes."""

    name: str = "SLU Markfuktighetskarta, klassad"
    provider: str = "Skogsstyrelsen / Sveriges lantbruksuniversitet"
    country: str = "SE"
    url: str = "https://www.skogsstyrelsen.se/e-tjanster-och-kartor/karttjanster/geodatatjanster/ftp/"
    license: str = "Skogsstyrelsen's terms for its geodata: open, with attribution"
    attribution: str = "© Skogsstyrelsen, SLU"
    #: The version the mosaic is, and the laser it was modelled off.
    version: str = "1.0, 2020-10-07, off the national laser scan of 2009–2019"


METADATA = SourceMetadata()

#: The server the mosaic is on, and the file's path there.
FTP_HOST = "ftpsks.skogsstyrelsen.se"
FTP_PATH = "/SLUMarkfuktighet/SLUMarkfuktighetskartaKlassad/SLUMarkfuktighetKlassad.tif"

#: Where the login comes from. The values are on the download page.
USERNAME_VAR = "SKOGSSTYRELSEN_FTP_USERNAME"
PASSWORD_VAR = "SKOGSSTYRELSEN_FTP_PASSWORD"

#: What the mosaic is called in the cache.
MOSAIC = "SLUMarkfuktighetKlassad.tif"

#: The mosaic's projection: SWEREF 99 TM.
CRS = "EPSG:3006"

#: Cell size, in metres.
CELL_M = 2.0

#: The classes, as the file has them.
DRY_FRESH = 1
FRESH_MOIST = 2
MOIST_WET = 3
WATER = 4
NODATA = 255

#: How many bytes the file is, so a partial fetch is told from a whole one.
MOSAIC_BYTES = 8_440_050_454


class Source:
    """The classed mosaic, fetched once and read by window."""

    def __init__(self, cache_dir: str | Path = ".cache", username: str | None = None, password: str | None = None):
        """Point at the mosaic.

        Args:
            cache_dir: Where the mosaic is kept
            username: The FTPS login; :data:`USERNAME_VAR` by default
            password: Its password; :data:`PASSWORD_VAR` by default
        """
        self.cache_dir = Path(cache_dir) / "moisture"
        self.username = username if username is not None else os.environ.get(USERNAME_VAR, "")
        self.password = password if password is not None else os.environ.get(PASSWORD_VAR, "")

    @property
    def mosaic(self) -> Path:
        """Where the mosaic is, or would be."""
        return self.cache_dir / MOSAIC

    def fetch(self) -> Path:
        """The mosaic, fetched whole if it is not in the cache.

        Returns:
            The file

        Raises:
            RuntimeError: If it has to be fetched and the login is missing
        """
        if self.mosaic.exists():
            return self.mosaic
        if not (self.username and self.password):
            raise RuntimeError(f"{METADATA.name} needs the FTPS login from {METADATA.url}; set {USERNAME_VAR} and {PASSWORD_VAR}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = self.mosaic.with_suffix(".part")
        print(f"Fetching {METADATA.name}, {MOSAIC_BYTES / 1e9:.1f} GB, from {FTP_HOST}...", flush=True)
        with ftplib.FTP_TLS(FTP_HOST, timeout=600) as server:
            server.login(self.username, self.password)
            server.prot_p()
            with partial.open("wb") as out:
                server.retrbinary(f"RETR {FTP_PATH}", out.write, blocksize=1 << 20)
        if partial.stat().st_size != MOSAIC_BYTES:
            raise RuntimeError(f"{partial} is {partial.stat().st_size:,} bytes; expected {MOSAIC_BYTES:,}")
        partial.replace(self.mosaic)
        return self.mosaic

    def classes(self, bounds: tuple[float, float, float, float]) -> tuple[np.ndarray, Affine]:
        """The classes over a box, at the mosaic's own 2 m.

        Args:
            bounds: The box in :data:`CRS`, ``(west, south, east, north)`` in metres

        Returns:
            The classes (rows from the north), ``uint8``, :data:`NODATA` past
            the mosaic's edge, and their georeferencing
        """
        with rasterio.open(self.fetch()) as mosaic:
            window = from_bounds(*bounds, transform=mosaic.transform).round_offsets().round_lengths()
            read = mosaic.read(1, window=window, boundless=True, fill_value=NODATA)
            return read, mosaic.window_transform(window)

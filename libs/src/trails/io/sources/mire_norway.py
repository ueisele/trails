"""The mire classes over a Norwegian box: N50's bogs, every one of them firm mire.

Kartverket's sheet draws the bogs as outlines -- ``Myr`` in N50's land-cover
layer (:mod:`.n50`) -- and says nothing of whether one carries a boot, so
every cell inside one is :data:`~trails.io.sources.mire.FIRM_MIRE` and the
other two classes are empty over Norway: a distinction the data does not
make is not drawn. Measured over the Lomsdal-Visten box (2026-09-19): 11,598
bogs of 207 km², 3.6 % of the land, half of them under 0.7 ha, the largest
3.8 km². The soil-moisture model is Swedish and has no Norwegian
counterpart; a wetness index could be computed off the terrain model this
map already reads, but that would be a model of ours and not a survey, and
it is not done.

The municipalities are found the way the map's own loaders find them,
through Kartverket's municipality register (:mod:`.kommuneinfo`), and the
land cover of each is the same whole, cached file the map's water and rivers
are read from.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from shapely.geometry import box as box_of

from ...utils.tiles import Bounds
from . import kommuneinfo, mire, n50

#: The grid's projection: UTM 33 N on EUREF 89, which N50 is delivered in.
CRS = "EPSG:25833"

#: The counties whose municipalities are searched: Nordland and Trøndelag,
#: which is where the Norwegian map is and what its band could grow into.
COUNTIES = ("18", "50")


class Source:
    """The mire classes over a box, cut once and kept."""

    def __init__(self, cache_dir: str | Path = ".cache", land_cover: n50.Source | None = None, register: kommuneinfo.Source | None = None):
        """Point at the sheet.

        Args:
            cache_dir: Where the cut is kept, and where the sources keep theirs
            land_cover: N50; read from ``cache_dir`` by default
            register: The municipality register; likewise
        """
        self.cache_dir = Path(cache_dir) / "mire"
        self.land_cover = land_cover if land_cover is not None else n50.Source(cache_dir=str(cache_dir))
        self.register = register if register is not None else kommuneinfo.Source(cache_dir=str(cache_dir))

    def _cut_file(self, bounds: Bounds) -> Path:
        stem = "_".join(f"{value:.2f}" for value in bounds).replace(".", "p").replace("-", "m")
        return self.cache_dir / f"norway_{stem}.tif"

    def mire(self, bounds: Bounds, force_download: bool = False) -> tuple[np.ndarray, Affine]:
        """The mire classes over a box.

        Args:
            bounds: The box, WGS 84
            force_download: Cut the box again, fetching the sheet again, even if its cut is cached

        Returns:
            The classes (rows from the north), ``uint8``, 0 where nothing is
            drawn, and their georeferencing in :data:`CRS`
        """
        cached = self._cut_file(bounds)
        if cached.exists() and not force_download:
            with rasterio.open(cached) as kept:
                return kept.read(1), kept.transform
        area = gpd.GeoDataFrame(geometry=[box_of(*bounds)], crs="EPSG:4326")
        codes = self.register.intersecting(area, fylke=COUNTIES)
        bogs = self.land_cover.load_mire(codes, force_download=force_download).to_crs(CRS)
        shape, transform = mire.grid(bounds, CRS)
        classes = np.zeros(shape, dtype=np.uint8)
        mire.burn(classes, transform, bogs.geometry, mire.FIRM_MIRE)
        covered = (classes != 0).mean() * 100
        print(f"Mire over {bounds}: N50's bogs cover {covered:.2f} % of the box, {len(bogs):,} loaded over its municipalities", flush=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part.tif")
        with rasterio.open(
            partial, "w", driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="uint8", crs=CRS, transform=transform,
            nodata=None, compress="deflate", tiled=True, blockxsize=512, blockysize=512,
        ) as out:  # fmt: skip
            out.write(classes, 1)
        partial.replace(cached)
        return classes, transform

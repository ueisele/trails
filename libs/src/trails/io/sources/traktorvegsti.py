"""Detailed terrain paths from Kartverket's "Traktorveg og Skogsbilveg" WFS.

This serves the FKB-derived ``traktorveg_sti`` feature type: the path and
tractor-road network Kartverket's topographic map draws at large scales. It is
considerably denser than the generalised N50 version of the same network, and
unlike the FKB-TraktorvegSti file download it needs no Geonorge account.

Features are delivered in short pieces, so :func:`Source.fetch_paths` returns
many small lines; merge them if you need whole routes::

    paths = Source().fetch_paths(bounds)
"""

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd
import requests

from ..cache import Object as ObjectCache

SERVICE_URL = "https://wms.geonorge.no/skwms1/wms.traktorveg_skogsbilveger"

TYPE_NAME = "ms:traktorveg_sti"

#: Projection used for requests; the service also advertises EPSG:4326.
REQUEST_CRS = "EPSG:25833"

#: ``typeveg`` values a walker can use.
WALKABLE_ROAD_TYPES = ("sti", "traktorveg")

#: Bounding box as (min_lon, min_lat, max_lon, max_lat), matching GeoPandas.
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the path data."""

    name: str = "Traktorveg og Skogsbilveg"
    provider: str = "Kartverket"
    country: str = "NO"
    url: str = SERVICE_URL
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"


METADATA = SourceMetadata()


class Source:
    """Loader for detailed paths and tractor roads via WFS."""

    def __init__(self, cache_dir: str = ".cache", timeout: int = 300, page_size: int = 5000):
        """Initialize the source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds per request
            page_size: Features requested per page
        """
        self.cache = ObjectCache(f"{cache_dir}/objects")
        self.timeout = timeout
        self.page_size = page_size
        #: When the answer this source last served was read, ISO, or None
        #: before it has served one. An exported file records the version of
        #: every source it draws on, and this service publishes none.
        self.loaded_at: str | None = None

    def _bbox_parameter(self, bounds: Bounds) -> str:
        """Build the WFS bbox parameter for a WGS84 extent.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84

        Returns:
            Comma-separated bbox in the request projection, with CRS suffix
        """
        extent = gpd.GeoSeries.from_wkt(
            [f"POLYGON(({bounds[0]} {bounds[1]},{bounds[2]} {bounds[1]},{bounds[2]} {bounds[3]},{bounds[0]} {bounds[3]},{bounds[0]} {bounds[1]}))"],
            crs="EPSG:4326",
        ).to_crs(REQUEST_CRS)
        min_x, min_y, max_x, max_y = extent.total_bounds
        return f"{min_x},{min_y},{max_x},{max_y},urn:ogc:def:crs:EPSG::25833"

    def count(self, bounds: Bounds) -> int:
        """Count the features available in an extent.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84

        Returns:
            Number of matching features

        Raises:
            ValueError: If the service response carries no feature count
        """
        response = requests.get(
            SERVICE_URL,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typenames": TYPE_NAME,
                "resultType": "hits",
                "bbox": self._bbox_parameter(bounds),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        import re

        match = re.search(r'numberMatched="(\d+)"', response.text)
        if not match:
            raise ValueError(f"WFS hits response carried no numberMatched: {response.text[:200]}")
        return int(match.group(1))

    def fetch_paths(
        self,
        bounds: Bounds,
        road_types: tuple[str, ...] = WALKABLE_ROAD_TYPES,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Fetch paths and tractor roads within an extent.

        The service caps how much it returns per request, so results are paged
        until the advertised feature count is reached.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            road_types: ``typeveg`` values to keep
            force_download: Bypass the cache and re-query the service

        Returns:
            GeoDataFrame in EPSG:4326 with the columns ``typeveg``,
            ``kommunenummer`` and ``objtype``. Empty if nothing matched.
        """
        key_bounds = "_".join(f"{value:.4f}" for value in bounds)
        cache_key = f"traktorvegsti_{key_bounds}_{'-'.join(road_types)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading detailed paths from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            self.loaded_at = self.cache.cached_at(cache_key)
            return cached

        bbox = self._bbox_parameter(bounds)
        total = self.count(bounds)
        print(f"Fetching {total:,} path features from {METADATA.name} WFS...")

        pages = []
        start = 0
        while start < total:
            params: dict[str, str | int] = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typenames": TYPE_NAME,
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "urn:ogc:def:crs:EPSG::25833",
                "bbox": bbox,
                "count": self.page_size,
                "startIndex": start,
            }
            response = requests.get(SERVICE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            features = response.json().get("features", [])
            if not features:
                break

            pages.append(gpd.GeoDataFrame.from_features(features, crs=REQUEST_CRS))
            start += len(features)
            print(f"  {min(start, total):,}/{total:,}")

        if not pages:
            return gpd.GeoDataFrame({"typeveg": [], "kommunenummer": [], "objtype": []}, geometry=[], crs="EPSG:4326")

        merged = gpd.GeoDataFrame(pd.concat(pages, ignore_index=True), crs=REQUEST_CRS).to_crs("EPSG:4326")
        walkable = merged[merged["typeveg"].isin(road_types)].reset_index(drop=True)
        result = gpd.GeoDataFrame(walkable, geometry="geometry", crs="EPSG:4326")
        print(f"  kept {len(result):,} walkable ({', '.join(road_types)})")

        self.cache.save(cache_key, result, metadata={"bounds": list(bounds), "road_types": list(road_types), "count": len(result)})
        self.loaded_at = self.cache.cached_at(cache_key)
        return result

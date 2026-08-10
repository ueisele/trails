"""Protected area boundaries from Naturbase (Miljødirektoratet).

Provides access to Norwegian protected areas (national parks, nature reserves,
landscape protection areas) via the Miljødirektoratet ArcGIS REST service.

Typical use is clipping trail data to a park boundary::

    source = Source()
    park = source.find_one("Lomsdal-Visten", layer=Layer.NATIONAL_PARK)
    trails_in_park = trails.clip(park.geometry.iloc[0])
"""

from dataclasses import dataclass
from enum import IntEnum

import geopandas as gpd
import requests

from ..cache import Object as ObjectCache

SERVICE_URL = "https://kart.miljodirektoratet.no/arcgis/rest/services/vern_hovedtyper/MapServer"

#: Fields requested from the service. Kept explicit so the schema is stable.
OUTPUT_FIELDS = (
    "naturvernId",
    "navn",
    "offisieltNavn",
    "verneform",
    "kommune",
    "forvaltningsmyndighet",
    "iucn",
    "vernedato",
    "faktaark",
    "verneforskrift",
)


class Layer(IntEnum):
    """Layer IDs of the ``vern_hovedtyper`` map service."""

    ALL = 0
    NATIONAL_PARK = 1
    NATURE_RESERVE = 2
    LANDSCAPE_PROTECTION = 3
    OTHER_PROTECTION = 4
    MARINE = 5


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the protected area data."""

    name: str = "Naturvernområder"
    provider: str = "Miljødirektoratet"
    country: str = "NO"
    url: str = SERVICE_URL
    license: str = "NLOD (Norsk lisens for offentlige data)"
    attribution: str = "© Miljødirektoratet / Naturbase"


METADATA = SourceMetadata()


def _escape_sql_literal(value: str) -> str:
    """Escape a value for use inside a single-quoted SQL string literal.

    Args:
        value: Raw value to embed in a ``where`` clause

    Returns:
        Value with single quotes doubled
    """
    return value.replace("'", "''")


class Source:
    """Loader for Norwegian protected area boundaries from Naturbase."""

    def __init__(self, cache_dir: str = ".cache", timeout: int = 120):
        """Initialize the Naturbase source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds
        """
        self.cache = ObjectCache(f"{cache_dir}/objects")
        self.timeout = timeout

    def find(
        self,
        name: str,
        layer: Layer = Layer.ALL,
        exact: bool = False,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Find protected areas by name.

        Args:
            name: Area name, matched case-insensitively as a substring unless
                ``exact`` is set (e.g. "Lomsdal-Visten")
            layer: Which protection type to search
            exact: Require an exact name match instead of a substring match
            force_download: Bypass the cache and re-query the service

        Returns:
            GeoDataFrame in EPSG:4326 with one row per matching area. Empty if
            nothing matched.

        Raises:
            requests.HTTPError: If the service returns an error status
            ValueError: If the service returns a payload that is not GeoJSON
        """
        cache_key = f"naturbase_{layer.name.lower()}_{name.lower().replace(' ', '_')}_{int(exact)}"

        if not force_download and self.cache.exists(cache_key):
            print(f"Loading protected area '{name}' from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        escaped = _escape_sql_literal(name)
        where = f"navn = '{escaped}'" if exact else f"UPPER(navn) LIKE UPPER('%{escaped}%')"

        print(f"Querying Naturbase for '{name}' ({layer.name})...")
        response = requests.get(
            f"{SERVICE_URL}/{int(layer)}/query",
            params={
                "where": where,
                "outFields": ",".join(OUTPUT_FIELDS),
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        # ArcGIS reports failures as HTTP 200 with an "error" body.
        if "error" in payload:
            raise ValueError(f"Naturbase query failed: {payload['error']}")
        if "features" not in payload:
            raise ValueError(f"Unexpected Naturbase response: {sorted(payload)}")

        features = payload["features"]
        if features:
            gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        else:
            # from_features cannot infer a geometry column from an empty list.
            gdf = gpd.GeoDataFrame({field: [] for field in OUTPUT_FIELDS}, geometry=[], crs="EPSG:4326")
        print(f"Found {len(gdf)} protected area(s)")

        self.cache.save(cache_key, gdf, metadata={"name": name, "layer": layer.name, "where": where, "count": len(gdf)})
        return gdf

    def find_one(
        self,
        name: str,
        layer: Layer = Layer.ALL,
        exact: bool = False,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Find exactly one protected area by name.

        Args:
            name: Area name to search for
            layer: Which protection type to search
            exact: Require an exact name match instead of a substring match
            force_download: Bypass the cache and re-query the service

        Returns:
            GeoDataFrame with a single row

        Raises:
            LookupError: If the query matched no areas or more than one
        """
        gdf = self.find(name, layer=layer, exact=exact, force_download=force_download)

        if len(gdf) == 0:
            raise LookupError(f"No protected area matches '{name}' in layer {layer.name}")
        if len(gdf) > 1:
            matches = ", ".join(str(n) for n in gdf["navn"].tolist())
            raise LookupError(f"'{name}' is ambiguous in layer {layer.name}, matched {len(gdf)}: {matches}")

        return gdf

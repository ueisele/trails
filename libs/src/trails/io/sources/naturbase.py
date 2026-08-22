"""Protected area boundaries from Naturbase (Miljødirektoratet).

Provides access to Norwegian protected areas (national parks, nature reserves,
landscape protection areas) via the Miljødirektoratet ArcGIS REST service.

Typical use is clipping trail data to a park boundary::

    source = Source()
    park = source.find_one("Lomsdal-Visten", layer=Layer.NATIONAL_PARK)
    trails_in_park = trails.clip(park.geometry.iloc[0])

And asking what is protected over an extent rather than under a name, which is
the question a route has to answer::

    areas = source.within(zone.total_bounds)
"""

import json
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


#: What the register writes in ``verneform``, and the Norwegian words for it.
#: The register spells its own values without the letters they are said with —
#: ``Landskapsvernomraade``, not *landskapsvernområde* — so a figure that showed
#: the raw value would name a form no Norwegian sign does.
#:
#: **This is the service's own coded-value domain, not a table written here.**
#: Every layer of ``vern_hovedtyper`` publishes the same ``Kode_Verneform``
#: domain under ``{layer}?f=json``, and these are its twenty-four codes with the
#: names it gives them, taken verbatim — parentheses, capitals and all. An
#: earlier version of this was seven entries written from memory: three of them
#: (*AnnetVern*, and two names invented for codes that exist) were wrong, and it
#: was missing the fourteen compound forms the register actually answers with,
#: of which *Dyrefredningsomrade* and two ``Landskapsvernomraade…`` variants lie
#: within a day's drive of this park. Read the domain rather than guessing at it:
#: it is one request and it is the register's own list.
#:
#: A code outside it falls through as it was written rather than being renamed to
#: the nearest one: a protection type this does not know is not a nature reserve.
VERNEFORM_LABELS = {
    "Biotopvern": "biotopvern",
    "BiotopvernSvalbard": "biotopvern (Svalbardmiljøloven)",
    "BiotopvernVilt": "biotopvern etter viltloven",
    "Dyrefredningsomrade": "dyrefredningsområde",
    "Dyrelivsfredning": "dyrelivsfredning",
    "GeotopvernSvalbard": "geotopvern (Svalbardmiljøloven)",
    "Landskapsvernomraade": "landskapsvernområde",
    "LandskapsvernomraadeBiotopvern": "landskapsvernområde med biotopvern",
    "LandskapsvernomraadeDyrelivsfredning": "landskapsvernområde med dyrelivsfredning",
    "LandskapsvernomraadePlanteOgDyrelivsfredning": "landskapsvernområde med plante- og dyrelivsfredning",
    "LandskapsvernomraadePlantelivsfredning": "landskapsvernområde med plantelivsfredning",
    "MarintVerneomraade": "marint verneområde (naturmangfoldloven)",
    "MarintVerneomraadeAnnet": "marint verneområde (annet lovverk)",
    "MidlertidigVernaOmraade": "midlertidig verna område/objekt",
    "Nasjonalpark": "nasjonalpark",
    "NasjonalparkSvalbard": "nasjonalpark (Svalbardmiljøloven)",
    "Naturminne": "naturminne",
    "Naturreservat": "naturreservat",
    "NaturreservatJanMayen": "Naturreservat (Jan Mayen)",
    "NaturreservatSvalbard": "naturreservat (Svalbardmiljøloven)",
    "PlanteOgDyrefredningsomraade": "plante- og dyrefredningsområde",
    "PlanteOgDyrelivsfredning": "plante- og dyrelivsfredning",
    "Plantefredningsomraade": "plantefredningsområde",
    "Plantelivsfredning": "plantelivsfredning",
}


def verneform_label(value: object) -> str:
    """Say a protection form in the words a sign in the terrain uses.

    Args:
        value: The register's own ``verneform``

    Returns:
        The Norwegian words for it, or the raw value where this does not know it
    """
    text = str(value)
    return VERNEFORM_LABELS.get(text, text)


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

    def within(
        self,
        bounds: tuple[float, float, float, float],
        layer: Layer = Layer.ALL,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Find every protected area meeting a rectangle.

        The other way into the same endpoint: :meth:`find` asks *which area is
        called this*, and a route has to ask *what is protected where I am
        going*. One request answers for a whole extent — the same query with a
        ``geometry`` instead of a ``where`` clause.

        The rectangle is a *box*, so an area whose box overlaps and whose
        outline does not comes back too. Clip to the shape that matters if that
        difference matters: over Lomsdal-Visten's approach zone the box returns
        44 areas and 31 of them actually meet the zone.

        Args:
            bounds: ``(min_lon, min_lat, max_lon, max_lat)`` in EPSG:4326, as
                ``GeoDataFrame.total_bounds`` gives them
            layer: Which protection type to search
            force_download: Bypass the cache and re-query the service

        Returns:
            GeoDataFrame in EPSG:4326 with one row per area meeting the box.
            Empty if nothing did.

        Raises:
            requests.HTTPError: If the service returns an error status
            ValueError: If the service returns a payload that is not GeoJSON, or
                if it answered with only as much as it was willing to send
        """
        west, south, east, north = (float(value) for value in bounds)
        # Six places is a tenth of a metre, finer than any boundary here is
        # surveyed, and it keeps the key from changing on a float's last bit.
        cache_key = f"naturbase_{layer.name.lower()}_within_{west:.6f}_{south:.6f}_{east:.6f}_{north:.6f}"

        if not force_download and self.cache.exists(cache_key):
            print(f"Loading the protected areas over {west:.3f},{south:.3f} {east:.3f},{north:.3f} from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        envelope = {"xmin": west, "ymin": south, "xmax": east, "ymax": north, "spatialReference": {"wkid": 4326}}
        print(f"Querying Naturbase over {west:.3f},{south:.3f} {east:.3f},{north:.3f} ({layer.name})...")
        response = requests.get(
            f"{SERVICE_URL}/{int(layer)}/query",
            params={
                "geometry": json.dumps(envelope),
                "geometryType": "esriGeometryEnvelope",
                # The box is in degrees; without this the service reads it in
                # the layer's own projection and answers about somewhere else.
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
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
        # And it reports a *truncated* answer as a successful one with a flag.
        # Silently taking the first page would build a network that knows about
        # some of the protected ground it runs over and not the rest, which is
        # worse than knowing about none of it.
        if payload.get("exceededTransferLimit") or (payload.get("properties") or {}).get("exceededTransferLimit"):
            raise ValueError("Naturbase sent only as many areas as it was willing to; ask over a smaller box")

        features = payload["features"]
        if features:
            gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        else:
            # from_features cannot infer a geometry column from an empty list.
            gdf = gpd.GeoDataFrame({field: [] for field in OUTPUT_FIELDS}, geometry=[], crs="EPSG:4326")
        print(f"Found {len(gdf)} protected area(s)")

        self.cache.save(cache_key, gdf, metadata={"bounds": [west, south, east, north], "layer": layer.name, "count": len(gdf)})
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

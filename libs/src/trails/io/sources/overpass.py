"""OpenStreetMap data via the Overpass API.

Complements official trail databases with community-mapped paths, tracks and
shelters. Queries are bounded by a bounding box, so this is suited to single
regions rather than country-wide extracts (use a Geofabrik PBF for those).

Public Overpass instances are rate limited and frequently return HTTP 429 or 504
under load, so requests cycle across several mirrors with exponential backoff.
"""

import hashlib
import time
from dataclasses import dataclass

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point

from ..cache import Object as ObjectCache

#: Public Overpass endpoints, tried in order until one answers.
MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    # Answered for Sweden on 2026-09-20 when the first two mirrors were busy.
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

#: Sent so Overpass operators can identify the client, as their usage policy asks.
USER_AGENT = "trails-analysis/0.1 (+https://github.com/ueisele/trails)"

#: Highway values that carry foot traffic on trails.
HIKING_HIGHWAY_TYPES = ("path", "footway", "track", "bridleway", "steps")

#: Tag selectors for overnight shelters and huts relevant to hiking. Both nodes
#: and building outlines are requested, since huts are mapped either way.
#:
#: Deliberately excludes ``building=cabin``: in Norway that tags private holiday
#: cabins, of which this region alone holds well over a thousand.
SHELTER_SELECTORS = (
    'node["tourism"~"^(alpine_hut|wilderness_hut)$"]',
    'way["tourism"~"^(alpine_hut|wilderness_hut)$"]',
    'node["amenity"="shelter"]',
    'way["amenity"="shelter"]',
)

#: ``shelter_type`` values that are neither a night's roof nor a place to wait
#: out weather. Measured 2026-09-17 over the two parks' boxes: of 76
#: ``amenity=shelter``, ten were bus-stop roofs, seven picnic roofs and one a
#: wildlife hide -- and every one was drawn as a hut. A shelter with no type is
#: kept: over Abisko that is the Länsstyrelsen's Vássivágge hut.
NOT_A_SHELTER_TYPES = ("public_transport", "picnic_shelter", "gazebo", "sun_shelter", "wildlife_hide", "field_shelter", "changing_rooms")

#: Settlement types useful for orientation. Farms and localities are excluded
#: because Norwegian map data carries them in the hundreds per region.
SETTLEMENT_PLACE_TYPES = ("town", "village", "hamlet")

#: Tag selectors for where the way in ends: a railway station or halt, a bus
#: stop. Abisko is reached by train and its six stations were on no layer.
STOP_SELECTORS = (
    'node["railway"~"^(station|halt)$"]',
    'node["highway"="bus_stop"]',
)

#: Tag selectors for camp sites, a marked pitch in the fell as much as a
#: campground by the road. Both nodes and areas, since they are mapped either way.
CAMP_SITE_SELECTORS = (
    'node["tourism"="camp_site"]',
    'way["tourism"="camp_site"]',
)

#: Tag selectors for ferry and express-boat quays. Quays are mapped both as
#: nodes and as pier ways, so both are requested.
FERRY_TERMINAL_SELECTORS = (
    'node["amenity"="ferry_terminal"]',
    'way["amenity"="ferry_terminal"]',
)

#: Bounding box as (min_lon, min_lat, max_lon, max_lat), matching GeoPandas.
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the OpenStreetMap data."""

    name: str = "OpenStreetMap"
    provider: str = "OpenStreetMap contributors"
    url: str = "https://www.openstreetmap.org"
    license: str = "ODbL 1.0"
    attribution: str = "© OpenStreetMap contributors"


METADATA = SourceMetadata()


def _selector_digest(selectors: tuple[str, ...]) -> str:
    """Build a short, filename-safe fingerprint of a selector set.

    Args:
        selectors: Overpass element selectors

    Returns:
        Hex digest identifying this exact selector set
    """
    return hashlib.md5("|".join(selectors).encode("utf-8")).hexdigest()[:8]


def _position(element: dict) -> Point | None:
    """Where an element is: a node's own position, or a way's centre.

    Args:
        element: One entry of an Overpass ``elements`` list, asked for with
            ``out center``

    Returns:
        The point, or None where the element carries no position at all.
    """
    lon, lat = element.get("lon"), element.get("lat")
    if lon is None or lat is None:
        center = element.get("center") or {}
        lon, lat = center.get("lon"), center.get("lat")
    if lon is None or lat is None:
        return None
    return Point(lon, lat)


def _to_overpass_bbox(bounds: Bounds) -> str:
    """Convert GeoPandas-style bounds to an Overpass bbox filter.

    Args:
        bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84

    Returns:
        Overpass bbox string in (south, west, north, east) order
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    return f"{min_lat},{min_lon},{max_lat},{max_lon}"


class OverpassError(RuntimeError):
    """Raised when no Overpass mirror could serve the query."""


class Source:
    """Loader for OpenStreetMap features via the Overpass API."""

    def __init__(
        self,
        cache_dir: str = ".cache",
        mirrors: tuple[str, ...] = MIRRORS,
        timeout: int = 300,
        max_rounds: int = 4,
        initial_backoff: float = 20.0,
    ):
        """Initialize the Overpass source.

        Args:
            cache_dir: Root directory for caching data
            mirrors: Overpass endpoints to try, in order
            timeout: HTTP timeout in seconds per mirror
            max_rounds: How many times to cycle through all mirrors
            initial_backoff: Seconds to wait after the first failed round,
                doubled after each subsequent round
        """
        self.cache = ObjectCache(f"{cache_dir}/objects")
        #: When the answer this source last served was read, ISO, or None
        #: before it has served one. An exported file records the version of
        #: every source it draws on, and this service publishes none.
        self.loaded_at: str | None = None
        self.mirrors = mirrors
        self.timeout = timeout
        self.max_rounds = max_rounds
        self.initial_backoff = initial_backoff

    def query(self, overpass_ql: str) -> dict:
        """Run a raw Overpass QL query, cycling mirrors until one answers.

        Public instances routinely reject requests with HTTP 429 (rate limit) or
        504 (server busy) that succeed moments later, so every mirror is retried
        across several rounds with exponential backoff.

        Args:
            overpass_ql: Complete Overpass QL query including output statement

        Returns:
            Parsed JSON response

        Raises:
            OverpassError: If every mirror failed in every round
        """
        headers = {"User-Agent": USER_AGENT}
        failures: list[str] = []
        backoff = self.initial_backoff

        for round_number in range(1, self.max_rounds + 1):
            for mirror in self.mirrors:
                try:
                    response = requests.post(mirror, data=overpass_ql.encode("utf-8"), headers=headers, timeout=self.timeout)
                    response.raise_for_status()
                    payload: dict = response.json()
                    if "elements" not in payload:
                        failures.append(f"{mirror}: response without 'elements'")
                        continue
                    return payload
                except (requests.RequestException, ValueError) as e:
                    print(f"  Overpass {mirror} failed (round {round_number}/{self.max_rounds}): {e}")
                    failures.append(f"round {round_number} {mirror}: {e}")

            if round_number < self.max_rounds:
                print(f"  All mirrors busy, retrying in {backoff:.0f}s...")
                time.sleep(backoff)
                backoff *= 2

        raise OverpassError("All Overpass mirrors failed:\n  " + "\n  ".join(failures))

    def fetch_paths(
        self,
        bounds: Bounds,
        highway_types: tuple[str, ...] = HIKING_HIGHWAY_TYPES,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Fetch walkable ways within a bounding box.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            highway_types: OSM ``highway`` values to include
            force_download: Bypass the cache and re-query Overpass

        Returns:
            GeoDataFrame in EPSG:4326 with LineString geometries and the
            columns ``osm_id``, ``highway``, ``name``, ``surface``, ``sac_scale``,
            ``trail_visibility`` and ``operator``. Empty if nothing matched.
        """
        bbox = _to_overpass_bbox(bounds)
        cache_key = f"osm_paths_{bbox.replace(',', '_')}_{'-'.join(highway_types)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading OSM paths from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            self.loaded_at = self.cache.cached_at(cache_key)
            return cached

        pattern = "|".join(highway_types)
        ql = f'[out:json][timeout:180];way["highway"~"^({pattern})$"]({bbox});out geom;'

        print(f"Querying Overpass for paths in {bbox}...")
        payload = self.query(ql)

        records = []
        for element in payload["elements"]:
            if element.get("type") != "way":
                continue
            geometry = element.get("geometry") or []
            if len(geometry) < 2:
                continue
            tags = element.get("tags", {})
            records.append(
                {
                    "osm_id": element["id"],
                    "highway": tags.get("highway"),
                    "name": tags.get("name"),
                    "surface": tags.get("surface"),
                    "sac_scale": tags.get("sac_scale"),
                    "trail_visibility": tags.get("trail_visibility"),
                    "operator": tags.get("operator"),
                    "geometry": LineString([(p["lon"], p["lat"]) for p in geometry]),
                }
            )

        gdf = gpd.GeoDataFrame(
            records, columns=["osm_id", "highway", "name", "surface", "sac_scale", "trail_visibility", "operator", "geometry"], crs="EPSG:4326"
        )
        print(f"Fetched {len(gdf)} OSM ways")

        self.cache.save(cache_key, gdf, metadata={"bbox": bbox, "highway_types": list(highway_types), "count": len(gdf)})
        self.loaded_at = self.cache.cached_at(cache_key)
        return gdf

    def fetch_hiking_relations(self, bounds: Bounds, force_download: bool = False) -> pd.DataFrame:
        """Fetch hiking routes and the ways that belong to them.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            force_download: Bypass the cache and re-query Overpass

        Returns:
            One row per relation, with ``osm_id``, ``way_ids`` and the tags
            ``name``, ``ref``, ``from``, ``to``, ``website`` and ``operator``.
            Members are way ids only; unnamed relations are kept.
        """
        bbox = _to_overpass_bbox(bounds)
        cache_key = f"osm_relations_{bbox.replace(',', '_')}_hiking"
        if not force_download and self.cache.exists(cache_key):
            print("Loading OSM hiking relations from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, pd.DataFrame)
            self.loaded_at = self.cache.cached_at(cache_key)
            return cached

        ql = f'[out:json][timeout:180];relation["route"="hiking"]({bbox});out body;'
        print(f"Querying Overpass for hiking relations in {bbox}...")
        payload = self.query(ql)
        fields = ("name", "ref", "from", "to", "website", "operator")
        records = []
        for element in payload["elements"]:
            if element.get("type") != "relation":
                continue
            tags = element.get("tags", {})
            records.append(
                {
                    "osm_id": element["id"],
                    "way_ids": tuple(dict.fromkeys(member["ref"] for member in element.get("members", []) if member.get("type") == "way")),
                    **{field: tags.get(field) for field in fields},
                }
            )
        relations = pd.DataFrame(records, columns=["osm_id", "way_ids", *fields])
        print(f"Fetched {len(relations)} OSM hiking relations")
        self.cache.save(cache_key, relations, metadata={"bbox": bbox, "route": "hiking", "count": len(relations)})
        self.loaded_at = self.cache.cached_at(cache_key)
        return relations

    def fetch_shelters(
        self,
        bounds: Bounds,
        selectors: tuple[str, ...] = SHELTER_SELECTORS,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Fetch huts and shelters within a bounding box.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            selectors: Overpass element selectors without the bbox filter
            force_download: Bypass the cache and re-query Overpass

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``osm_id``, ``name``, ``kind``, ``shelter_type`` and ``operator``.
            Empty if nothing matched. A shelter whose type is one of
            :data:`NOT_A_SHELTER_TYPES` is dropped.
        """
        bbox = _to_overpass_bbox(bounds)
        # The selectors belong in the key: widening them must not hit a stale
        # entry -- and so does the shape, which is why the key changed with the
        # ``shelter_type`` column: an entry without it is not this frame.
        cache_key = f"osm_shelters_{bbox.replace(',', '_')}_{_selector_digest(selectors)}_typed"

        if not force_download and self.cache.exists(cache_key):
            print("Loading OSM shelters from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        body = "".join(f"{selector}({bbox});" for selector in selectors)
        ql = f"[out:json][timeout:180];({body});out center;"

        print(f"Querying Overpass for shelters in {bbox}...")
        payload = self.query(ql)

        records = []
        roofs = 0
        for element in payload["elements"]:
            tags = element.get("tags", {})
            point = _position(element)
            if point is None:
                continue
            if tags.get("shelter_type") in NOT_A_SHELTER_TYPES:
                roofs += 1
                continue
            records.append(
                {
                    "osm_id": element["id"],
                    "name": tags.get("name"),
                    "kind": tags.get("tourism") or tags.get("amenity") or tags.get("building"),
                    "shelter_type": tags.get("shelter_type"),
                    "operator": tags.get("operator"),
                    "geometry": point,
                }
            )

        gdf = gpd.GeoDataFrame(records, columns=["osm_id", "name", "kind", "shelter_type", "operator", "geometry"], crs="EPSG:4326")
        print(f"Fetched {len(gdf)} OSM shelters ({roofs} bus-stop, picnic and other roofs left out)")

        self.cache.save(cache_key, gdf, metadata={"bbox": bbox, "count": len(gdf)})
        return gdf

    def fetch_ferry_terminals(
        self,
        bounds: Bounds,
        selectors: tuple[str, ...] = FERRY_TERMINAL_SELECTORS,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Fetch ferry and express-boat quays within a bounding box.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            selectors: Overpass element selectors without the bbox filter
            force_download: Bypass the cache and re-query Overpass

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``osm_id``, ``name`` and ``operator``. Unnamed quays are dropped,
            since an unlabelled one is useless for planning a crossing.
        """
        bbox = _to_overpass_bbox(bounds)
        cache_key = f"osm_ferry_terminals_{bbox.replace(',', '_')}_{_selector_digest(selectors)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading OSM ferry terminals from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        body = "".join(f"{selector}({bbox});" for selector in selectors)
        ql = f"[out:json][timeout:180];({body});out center;"

        print(f"Querying Overpass for ferry terminals in {bbox}...")
        payload = self.query(ql)

        records = []
        seen: set[str] = set()
        for element in payload["elements"]:
            tags = element.get("tags", {})
            name = tags.get("name")
            if not name:
                continue

            lon, lat = element.get("lon"), element.get("lat")
            if lon is None or lat is None:
                center = element.get("center") or {}
                lon, lat = center.get("lon"), center.get("lat")
            if lon is None or lat is None:
                continue

            # A quay mapped as both a node and a pier way would appear twice.
            key = f"{name}@{round(lon, 3)},{round(lat, 3)}"
            if key in seen:
                continue
            seen.add(key)

            records.append({"osm_id": element["id"], "name": name, "operator": tags.get("operator"), "geometry": Point(lon, lat)})

        gdf = gpd.GeoDataFrame(records, columns=["osm_id", "name", "operator", "geometry"], crs="EPSG:4326")
        print(f"Fetched {len(gdf)} OSM ferry terminals")

        self.cache.save(cache_key, gdf, metadata={"bbox": bbox, "count": len(gdf)})
        return gdf

    def fetch_stops(
        self,
        bounds: Bounds,
        selectors: tuple[str, ...] = STOP_SELECTORS,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Fetch railway stations, halts and bus stops within a bounding box.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            selectors: Overpass element selectors without the bbox filter
            force_download: Bypass the cache and re-query Overpass

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``osm_id``, ``name``, ``kind`` (``station``, ``halt`` or
            ``bus_stop``) and ``operator``. Unnamed stops are dropped: a stop
            is somewhere a timetable names, and one without a name is not.
        """
        bbox = _to_overpass_bbox(bounds)
        cache_key = f"osm_stops_{bbox.replace(',', '_')}_{_selector_digest(selectors)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading OSM stops from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        body = "".join(f"{selector}({bbox});" for selector in selectors)
        ql = f"[out:json][timeout:180];({body});out center;"

        print(f"Querying Overpass for stations and bus stops in {bbox}...")
        payload = self.query(ql)

        records = []
        for element in payload["elements"]:
            tags = element.get("tags", {})
            point = _position(element)
            if point is None or not tags.get("name"):
                continue
            records.append(
                {
                    "osm_id": element["id"],
                    "name": tags["name"],
                    "kind": tags.get("railway") or tags.get("highway"),
                    "operator": tags.get("operator"),
                    "geometry": point,
                }
            )

        gdf = gpd.GeoDataFrame(records, columns=["osm_id", "name", "kind", "operator", "geometry"], crs="EPSG:4326")
        print(f"Fetched {len(gdf)} OSM stations and bus stops")

        self.cache.save(cache_key, gdf, metadata={"bbox": bbox, "count": len(gdf)})
        return gdf

    def fetch_camp_sites(
        self,
        bounds: Bounds,
        selectors: tuple[str, ...] = CAMP_SITE_SELECTORS,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Fetch camp sites within a bounding box.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            selectors: Overpass element selectors without the bbox filter
            force_download: Bypass the cache and re-query Overpass

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``osm_id``, ``name``, ``kind`` (always ``camp_site``) and
            ``operator``. Unnamed sites are kept: in the fell a pitch is mapped
            without a name, and it is still the place to put a tent.
        """
        bbox = _to_overpass_bbox(bounds)
        cache_key = f"osm_camp_sites_{bbox.replace(',', '_')}_{_selector_digest(selectors)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading OSM camp sites from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        body = "".join(f"{selector}({bbox});" for selector in selectors)
        ql = f"[out:json][timeout:180];({body});out center;"

        print(f"Querying Overpass for camp sites in {bbox}...")
        payload = self.query(ql)

        records = []
        for element in payload["elements"]:
            tags = element.get("tags", {})
            point = _position(element)
            if point is None:
                continue
            records.append(
                {"osm_id": element["id"], "name": tags.get("name"), "kind": tags.get("tourism"), "operator": tags.get("operator"), "geometry": point}
            )

        gdf = gpd.GeoDataFrame(records, columns=["osm_id", "name", "kind", "operator", "geometry"], crs="EPSG:4326")
        print(f"Fetched {len(gdf)} OSM camp sites")

        self.cache.save(cache_key, gdf, metadata={"bbox": bbox, "count": len(gdf)})
        return gdf

    def fetch_places(
        self,
        bounds: Bounds,
        place_types: tuple[str, ...] = SETTLEMENT_PLACE_TYPES,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Fetch named settlements within a bounding box.

        Useful as an orientation layer: trailheads and approach routes are
        usually described relative to the nearest village.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            place_types: OSM ``place`` values to include
            force_download: Bypass the cache and re-query Overpass

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``osm_id``, ``name`` and ``kind``. Unnamed places are dropped, since
            an unlabelled marker carries no orientation value.
        """
        bbox = _to_overpass_bbox(bounds)
        cache_key = f"osm_places_{bbox.replace(',', '_')}_{'-'.join(place_types)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading OSM places from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        pattern = "|".join(place_types)
        ql = f'[out:json][timeout:180];node["place"~"^({pattern})$"]["name"]({bbox});out;'

        print(f"Querying Overpass for places in {bbox}...")
        payload = self.query(ql)

        records = []
        for element in payload["elements"]:
            tags = element.get("tags", {})
            if not tags.get("name") or element.get("lon") is None or element.get("lat") is None:
                continue
            records.append(
                {
                    "osm_id": element["id"],
                    "name": tags["name"],
                    "kind": tags.get("place"),
                    "geometry": Point(element["lon"], element["lat"]),
                }
            )

        gdf = gpd.GeoDataFrame(records, columns=["osm_id", "name", "kind", "geometry"], crs="EPSG:4326")
        print(f"Fetched {len(gdf)} OSM places")

        self.cache.save(cache_key, gdf, metadata={"bbox": bbox, "place_types": list(place_types), "count": len(gdf)})
        return gdf

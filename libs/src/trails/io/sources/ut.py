"""Curated UT.no hiking routes, loaded from a catalogue file.

UT.no is Den Norske Turistforening's route portal. Its underlying API, Nasjonal
Turbase, needs a DNT key that is no longer issued, so routes cannot be discovered
programmatically. What *is* open is the per-trip GPX export, one URL per route::

    https://ut.no/api/gpx/trip/<id>

So an area's routes are researched once by hand and recorded in a TOML
catalogue; this module turns that catalogue into geometries::

    routes = load_catalogue("analysis/data/lomsdal-visten-ut-routes.toml")
    gdf = Source().load_routes(routes)

Licence: the GPX files carry ``CC BY-NC 4.0`` in their own metadata, attributed
to UT.no. That is *non-commercial* — unlike the Kartverket sources, this data
cannot go into a published routing graph without checking terms first.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from lxml import etree
from shapely.geometry import LineString, MultiLineString
from shapely.geometry.base import BaseGeometry

from ..cache import Download as DownloadCache

#: GPX export endpoint. The trip id is the only variable part.
GPX_URL_TEMPLATE = "https://ut.no/api/gpx/trip/{trip_id}"

#: Metric CRS for Norway, used only to measure route length.
METRIC_CRS = "EPSG:25833"

#: Catalogue values for ``category``.
CATEGORIES = ("core", "access")

#: Only these are accepted for the URL fields, so a catalogue cannot smuggle a
#: ``javascript:`` link into a map popup.
URL_SCHEMES = ("http://", "https://")


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the route data."""

    name: str = "UT.no"
    provider: str = "Den Norske Turistforening"
    country: str = "NO"
    url: str = "https://ut.no"
    license: str = "CC BY-NC 4.0"
    attribution: str = "© UT.no / DNT"


METADATA = SourceMetadata()


@dataclass(frozen=True)
class Route:
    """One catalogued UT.no route.

    Attributes:
        trip_id: UT.no trip identifier
        name: Route name as shown on UT.no
        category: One of :data:`CATEGORIES`
        ut_url: Link to the route page
        guide_url_no: Norwegian description on the park's own site, if any
        guide_url_en: English description on the park's own site, if any
        ut_summary: Distance, duration and ascent as UT states them, if recorded
    """

    trip_id: int
    name: str
    category: str
    ut_url: str
    guide_url_no: str | None = None
    guide_url_en: str | None = None
    ut_summary: str | None = None

    @property
    def gpx_url(self) -> str:
        """URL of this route's GPX export."""
        return GPX_URL_TEMPLATE.format(trip_id=self.trip_id)


def _check_url(value: object, field: str, trip_id: object) -> str:
    """Validate that a catalogue value is an http(s) URL.

    Args:
        value: Raw value from the catalogue
        field: Field name, for the error message
        trip_id: Route the value belongs to, for the error message

    Returns:
        The URL unchanged

    Raises:
        ValueError: If the value is not a string or not an http(s) URL
    """
    if not isinstance(value, str) or not value.startswith(URL_SCHEMES):
        raise ValueError(f"route {trip_id}: {field} must be an http(s) URL, got {value!r}")
    return value


def load_catalogue(path: str | Path) -> list[Route]:
    """Read a route catalogue.

    Args:
        path: Path to the TOML catalogue

    Returns:
        The routes in catalogue order

    Raises:
        ValueError: If an entry is missing a required field, carries an unknown
            category, or repeats a trip id
    """
    with open(path, "rb") as handle:
        document = tomllib.load(handle)

    routes = []
    seen: set[int] = set()
    for entry in document.get("route", []):
        trip_id = entry.get("id")
        if not isinstance(trip_id, int):
            raise ValueError(f"route entry has no integer id: {entry!r}")
        if trip_id in seen:
            raise ValueError(f"route {trip_id} appears twice in {path}")
        seen.add(trip_id)

        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"route {trip_id}: name is required")

        category = entry.get("category")
        if category not in CATEGORIES:
            raise ValueError(f"route {trip_id}: category must be one of {CATEGORIES}, got {category!r}")

        routes.append(
            Route(
                trip_id=trip_id,
                name=name,
                category=category,
                ut_url=_check_url(entry.get("ut_url"), "ut_url", trip_id),
                guide_url_no=_check_url(entry["guide_url_no"], "guide_url_no", trip_id) if "guide_url_no" in entry else None,
                guide_url_en=_check_url(entry["guide_url_en"], "guide_url_en", trip_id) if "guide_url_en" in entry else None,
                ut_summary=entry.get("ut_summary"),
            )
        )

    return routes


def parse_gpx(path: str | Path) -> BaseGeometry:
    """Read the track of a GPX file as a geometry.

    Only ``trk/trkseg/trkpt`` is read. Elevation and timestamps are dropped: the
    ``<time>`` UT.no writes is the moment of export, not of a survey, and a third
    coordinate would break every consumer that unpacks ``(lon, lat)``.

    Args:
        path: Path to a GPX file

    Returns:
        A LineString for a single segment, a MultiLineString for several

    Raises:
        ValueError: If the file holds no track point
    """
    # Third-party XML: no entity resolution and no network access, so the file
    # cannot pull in local files or remote content while being parsed.
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    tree = etree.parse(str(path), parser)

    segments = []
    for segment in tree.getroot().iterfind(".//{*}trkseg"):
        coordinates = [(float(point.get("lon")), float(point.get("lat"))) for point in segment.iterfind("{*}trkpt")]
        # A single point is a position, not a line; shapely rejects it anyway.
        if len(coordinates) >= 2:
            segments.append(LineString(coordinates))

    if not segments:
        raise ValueError(f"{path} holds no track segment with at least two points")
    return segments[0] if len(segments) == 1 else MultiLineString(segments)


class Source:
    """Loader for catalogued UT.no routes."""

    def __init__(self, cache_dir: str = ".cache", timeout: int = 60):
        """Initialize the source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds per request
        """
        self.downloads = DownloadCache(f"{cache_dir}/downloads/ut", timeout=timeout)
        #: When the routes this source last served were downloaded, ISO, or None
        #: before it has served any. The **oldest** of them: a catalogue fetched
        #: over several days is only as current as the trip nobody re-fetched,
        #: and an exported file has to say what it was built from.
        self.loaded_at: str | None = None

    def fetch_gpx(self, route: Route, force_download: bool = False) -> Path:
        """Download a route's GPX export, or return the cached copy.

        Args:
            route: Route to fetch
            force_download: Re-download even when cached

        Returns:
            Path to the cached GPX file
        """
        result = self.downloads.download(route.gpx_url, filename=f"trip_{route.trip_id}.gpx", force=force_download)
        return result.path

    def load_routes(self, routes: list[Route], force_download: bool = False) -> gpd.GeoDataFrame:
        """Load the geometries of a set of routes.

        Args:
            routes: Routes to load, typically from :func:`load_catalogue`
            force_download: Re-download every GPX instead of using the cache

        Returns:
            GeoDataFrame in EPSG:4326 with one row per route, carrying the
            catalogue fields plus ``gpx_url``, ``points`` and ``length_km``.
            Empty if ``routes`` is empty.
        """
        columns = ["trip_id", "name", "category", "ut_url", "guide_url_no", "guide_url_en", "ut_summary", "gpx_url", "points"]
        if not routes:
            return gpd.GeoDataFrame({column: [] for column in columns} | {"length_km": []}, geometry=[], crs="EPSG:4326")

        records = []
        geometries = []
        for route in routes:
            geometry = parse_gpx(self.fetch_gpx(route, force_download=force_download))
            records.append(
                {
                    "trip_id": route.trip_id,
                    "name": route.name,
                    "category": route.category,
                    "ut_url": route.ut_url,
                    "guide_url_no": route.guide_url_no,
                    "guide_url_en": route.guide_url_en,
                    "ut_summary": route.ut_summary,
                    "gpx_url": route.gpx_url,
                    "points": sum(len(part.coords) for part in getattr(geometry, "geoms", [geometry])),
                }
            )
            geometries.append(geometry)

        fetched = sorted(date for date in (self.downloads.downloaded_at(f"trip_{route.trip_id}.gpx") for route in routes) if date)
        self.loaded_at = fetched[0] if fetched else None

        gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
        # UT.no records a track as walked, so its length is the walked distance
        # rather than a map measurement — worth showing next to the route.
        gdf["length_km"] = (gdf.to_crs(METRIC_CRS).length / 1000).round(2)
        return gdf

"""Scheduled public transport in Sweden, from Samtrafiken's national GTFS feed.

**What this answers is which lines call at a stop, and where the stop is.**
Both other sources place Swedish stops and neither says what calls there: OSM
tags a pole, the place-name register names a hamlet. Entur knows the lines --
but only where a service reaches Norway, which is why it has all six stations
of the Abisko box and nothing at Nikkaluokta, Kvikkjokk or Ritsem.

Trafiklab is the data portal of Samtrafiken, the body the Swedish transport
authorities and operators own. ``GTFS Sverige 2`` is its whole-country feed:
every operator, every mode, CC0, updated at most once a day.

**Measured over the Abisko box on 2026-09-17**, against the two sources this
replaces there: 13 stops to OSM's 10 and Entur's 6. Every OSM stop stands
within **231 m** of one of these, so nothing is lost -- and the five it adds are
all roadside stops on the E10, where a walker actually gets off: Stordalen,
Katterjåkk E10, Låktatjåkka E10, Vassijaure E10 and Björkliden Hotell Fjället.
Stordalen is **9.65 km** from the nearest stop the map drew before.

**The key is a build-time credential and never reaches a page.** The feed is one
zip fetched once and cached; the published map is a static document that asks
nothing of anybody. Trafiklab's own guidance points the same way: *"if you need
to make more than 10 requests in order to get the data you need, you should be
using GTFS"*.
"""

import csv
import io
import os
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import Point

from ..cache import Object as ObjectCache

#: Where the whole-country feed is fetched from. The key is substituted in at
#: request time and is never logged, printed or cached.
DATASET_URL = "https://api.resrobot.se/gtfs/sweden.zip?key={key}"

#: The environment variable the key is read from. A build-time credential: it
#: lives in ``trails/.env``, which ``.gitignore`` covers, and this repository is
#: public.
KEY_VARIABLE = "TRAFIKLAB_API_KEY"

#: How many calls a Bronze key may make. One download is one call, and the zip
#: is cached, so an ordinary build makes none.
MONTHLY_CALLS = 50

#: The modes read, in the vocabulary :mod:`trails.io.sources.entur` uses, so a
#: map can draw either country's stops through the same layers.
MODES = {"rail": "train", "air": "flight", "water": "boat", "bus": "bus"}

#: GTFS ``route_type`` to that vocabulary, and to the word a line is labelled
#: with. **Both halves matter**: the mode decides which layer a stop is drawn
#: in, and the word keeps a shared taxi from being read as a bus that simply
#: turns up. The extended types (three digits) are what Samtrafiken publishes.
ROUTE_TYPES = {
    "0": ("rail", "tram"),
    "1": ("rail", "metro"),
    "2": ("rail", "train"),
    "3": ("bus", "bus"),
    "4": ("water", "ferry"),
    "100": ("rail", "train"),
    "101": ("rail", "high-speed train"),
    "102": ("rail", "long-distance train"),
    "105": ("rail", "sleeper train"),
    "106": ("rail", "regional train"),
    "109": ("rail", "commuter train"),
    "400": ("rail", "metro"),
    "401": ("rail", "metro"),
    "402": ("rail", "metro"),
    "700": ("bus", "bus"),
    "701": ("bus", "regional bus"),
    "702": ("bus", "express bus"),
    "704": ("bus", "local bus"),
    "715": ("bus", "on-demand bus"),
    "900": ("rail", "tram"),
    "1000": ("water", "ferry"),
    "1100": ("air", "flight"),
    "1200": ("water", "ferry"),
    "1501": ("bus", "shared taxi"),
    "1700": ("bus", "other"),
}

#: What joins several lines, or several modes, into one field: the same
#: separator :mod:`trails.io.sources.entur` uses, so a popup reads the same
#: whichever country it describes.
SEPARATOR = " / "


def line_order(label: str) -> tuple[int, int, str]:
    """Sort key putting a line list in an order a reader expects, and a stable one.

    **The lines arrive in a set and a set has no order.** Left as they came, the
    same feed wrote *91 bus / 957 shared taxi* one build and *957 shared taxi /
    91 bus* the next, because Python salts string hashes per process. A popup
    that reads differently each time it is built is a popup nobody can diff, and
    the test that caught it had passed once by luck.

    Args:
        label: A line as :meth:`Source.stops` writes it, ``code word``

    Returns:
        Numbered lines first and in numeric order -- 91 before 950 before 60098,
        which is how they are spoken of -- then the rest alphabetically.
    """
    code = label.split(" ", 1)[0]
    return (0, int(code), label) if code.isdigit() else (1, 0, label)


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the timetable data."""

    name: str = "GTFS Sverige 2"
    provider: str = "Samtrafiken (Trafiklab)"
    country: str = "SE"
    url: str = "https://www.trafiklab.se/api/gtfs-datasets/gtfs-sverige-2/"
    license: str = "CC0 1.0"
    attribution: str = "Trafiklab (Samtrafiken)"


METADATA = SourceMetadata()

#: Bounding box as (min_lon, min_lat, max_lon, max_lat), matching GeoPandas.
Bounds = tuple[float, float, float, float]


class TrafiklabError(RuntimeError):
    """Raised when the feed could not be fetched, or the key is missing."""


def lines_column(mode: str) -> str:
    """The column a mode's lines are returned under.

    Args:
        mode: One of :data:`MODES`

    Returns:
        The column name, e.g. ``bus_lines``.
    """
    return f"{mode}_lines"


#: The columns :meth:`Source.stops` returns, in order. The same shape
#: :mod:`trails.io.sources.entur` returns, less its link: a Swedish board is
#: somebody else's page and is built from ``stop_id`` by the caller.
COLUMNS = ["stop_id", "name", "modes", *(lines_column(mode) for mode in MODES), "operator", "geometry"]


class Source:
    """Loader for the stops a scheduled service calls at, anywhere in Sweden."""

    def __init__(self, cache_dir: str = ".cache", api_key: str | None = None, timeout: int = 600):
        """Initialize the Trafiklab source.

        Args:
            cache_dir: Where the object cache and the feed itself live
            api_key: The Trafiklab key, or None to read :data:`KEY_VARIABLE`
            timeout: Seconds the download may take
        """
        self.cache = ObjectCache(cache_dir=f"{cache_dir}/objects")
        self.archive = Path(cache_dir) / "gtfs" / "sweden.zip"
        self.api_key = api_key
        self.timeout = timeout

    def dataset(self, force_download: bool = False) -> Path:
        """The feed itself, downloaded once and kept.

        **Not re-fetched on every build.** It is 44 MB, a Bronze key allows
        fifty calls a month, and the data changes at most daily; a build that
        re-downloaded would spend the quota on a file it already has.

        Args:
            force_download: Fetch it again even if it is already here

        Returns:
            Where the zip is.

        Raises:
            TrafiklabError: If it must be fetched and no key was given, or the
                download failed. **The key is never in the message**: it is
                substituted into the URL at the last moment and the URL is not
                reported.
        """
        if self.archive.exists() and not force_download:
            return self.archive

        key = self.api_key or os.environ.get(KEY_VARIABLE, "")
        if not key:
            raise TrafiklabError(f"no Trafiklab key: set {KEY_VARIABLE} in the environment or in trails/.env")

        print(f"Downloading GTFS Sverige 2 (one of {MONTHLY_CALLS} calls a month)...")
        self.archive.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = requests.get(DATASET_URL.format(key=key), timeout=self.timeout, stream=True)
            response.raise_for_status()
            with self.archive.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    out.write(chunk)
        except requests.RequestException as e:
            raise TrafiklabError(f"could not fetch GTFS Sverige 2: {type(e).__name__}") from None

        print(f"  {self.archive.stat().st_size / 1e6:.1f} MB")
        return self.archive

    def stops(self, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        """Fetch the stops within a box and the lines that call at them.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            force_download: Fetch the feed again and rebuild the frame

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns in
            :data:`COLUMNS`: ``stop_id`` (the national stop id, e.g.
            ``740000114``, which is also what a Resrobot board is asked for),
            ``name``, ``modes`` (the English words of :data:`MODES` it is served
            under), one ``<mode>_lines`` column per mode holding the lines of
            that mode as ``code word``, and ``operator``.

            **A stop no line calls at is left out**, as it is in Norway:
            registered is not served.
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        cache_key = f"trafiklab_stops_{min_lat}_{min_lon}_{max_lat}_{max_lon}_{'-'.join(MODES)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading Trafiklab stops from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        archive = self.dataset(force_download=force_download)
        print(f"Reading GTFS Sverige 2 for stops in {min_lat},{min_lon},{max_lat},{max_lon}...")
        with zipfile.ZipFile(archive) as feed:
            inside = self._stops_inside(feed, bounds)
            print(f"  {len(inside)} stops in the box")
            calling = self._lines_at(feed, set(inside))

        records = []
        for stop_id, stop in inside.items():
            lines = calling.get(stop_id)
            if not lines:
                continue
            record: dict[str, object] = {
                "stop_id": stop_id,
                "name": stop["name"],
                "modes": SEPARATOR.join(MODES[mode] for mode in MODES if mode in lines),
                "operator": SEPARATOR.join(sorted({agency for by_mode in lines.values() for _, agency in by_mode if agency})) or None,
                "geometry": Point(stop["lon"], stop["lat"]),
            }
            for mode in MODES:
                labels = sorted({label for label, _ in lines.get(mode, ())}, key=line_order)
                record[lines_column(mode)] = SEPARATOR.join(labels) if labels else None
            records.append(record)

        unserved = [stop["name"] for stop_id, stop in inside.items() if not calling.get(stop_id)]
        if unserved:
            print(f"  in the feed but with no line calling, left out: {', '.join(sorted(unserved))}")

        gdf = gpd.GeoDataFrame(records, columns=COLUMNS, crs="EPSG:4326")
        self.cache.save(cache_key, gdf, metadata={"bounds": list(bounds), "count": len(gdf)})
        return gdf

    @staticmethod
    def _stops_inside(feed: zipfile.ZipFile, bounds: Bounds) -> dict[str, dict]:
        """The stops of ``stops.txt`` that fall inside the box.

        Args:
            feed: The opened GTFS archive
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84

        Returns:
            Per stop id, its name and position.
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        inside: dict[str, dict] = {}
        for row in _rows(feed, "stops.txt"):
            try:
                lat, lon = float(row["stop_lat"]), float(row["stop_lon"])
            except KeyError, TypeError, ValueError:
                continue
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                inside[row["stop_id"]] = {"name": row["stop_name"], "lat": lat, "lon": lon}
        return inside

    @staticmethod
    def _lines_at(feed: zipfile.ZipFile, wanted: set[str]) -> dict[str, dict[str, set[tuple[str, str]]]]:
        """Which lines call at each of those stops, by mode.

        **``stop_times.txt`` is read as a stream and never held.** It is 374 MB
        unzipped and 7.5 million rows for Sweden; only the rows naming a stop in
        the box are kept, so what this costs in memory is the box and not the
        country.

        Args:
            feed: The opened GTFS archive
            wanted: The stop ids to keep rows for

        Returns:
            Per stop id, per mode, the ``(label, agency)`` pairs calling there.
        """
        touching: dict[str, set[str]] = defaultdict(set)
        for row in _rows(feed, "stop_times.txt"):
            if row["stop_id"] in wanted:
                touching[row["trip_id"]].add(row["stop_id"])

        of_trip = {row["trip_id"]: row["route_id"] for row in _rows(feed, "trips.txt") if row["trip_id"] in touching}
        routes = {row["route_id"]: row for row in _rows(feed, "routes.txt")}
        agencies = {row["agency_id"]: row["agency_name"] for row in _rows(feed, "agency.txt")}

        calling: dict[str, dict[str, set[tuple[str, str]]]] = defaultdict(lambda: defaultdict(set))
        unknown: set[str] = set()
        for trip, stop_ids in touching.items():
            route = routes.get(of_trip.get(trip, ""))
            if route is None:
                continue
            kind = route.get("route_type", "")
            if kind not in ROUTE_TYPES:
                unknown.add(kind)
                continue
            mode, word = ROUTE_TYPES[kind]
            code = route.get("route_short_name") or route.get("route_long_name") or ""
            label = f"{code} {word}".strip()
            agency = agencies.get(route.get("agency_id", ""), "")
            for stop_id in stop_ids:
                calling[stop_id][mode].add((label, agency))
        if unknown:
            # Said rather than guessed: a route type nobody mapped would
            # otherwise vanish, and the stop would read as one nothing calls at.
            print(f"  route types this map does not know, left out: {', '.join(sorted(unknown))}")
        return calling


def _rows(feed: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    """Stream one table of the archive as dictionaries.

    Args:
        feed: The opened GTFS archive
        name: The table, e.g. ``stops.txt``

    Yields:
        One mapping per row, decoded as UTF-8 with any byte-order mark removed.
    """
    with feed.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))

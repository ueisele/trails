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
import xml.etree.ElementTree as ElementTree
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

#: Where the national stop register is fetched from, and the key it wants --
#: **a second one**, because Trafiklab issues a key per dataset.
#:
#: **GTFS Sverige 2 puts a station where its bus stop is.** Measured over the
#: Abisko box on 2026-09-17: of the six railway stations, five stand up to
#: **249 m** from where they are, and Abisko Östra carries the same coordinate
#: as *Abisko Östra E10* down to the last digit -- so the two drew as one pin
#: and the station was missing from the map. The seven bus stops are right to
#: the metre. Trafiklab says as much itself: the feed is *"correct but lacking
#: the detailed information found in the GTFS Regional dataset"*, and its
#: ``stops.txt`` carries five columns with no parent and no platform.
#:
#: The register has the position, and ``rikshallplats`` is the same number as
#: the feed's ``stop_id`` -- all 13 stops of that box matched on it. What it has
#: not got is a timetable: not one ``Line``, ``ServiceJourney``, ``Operator`` or
#: ``Authority`` element in 331 MB. So it says where a stop is and the feed says
#: what calls there, and neither can be dropped.
REGISTER_URL = "https://opendata.samtrafiken.se/stopsregister-netex-sweden/sweden.zip?key={key}"
REGISTER_KEY_VARIABLE = "TRAFIKLAB_STOPS_API_KEY"

#: **The register refuses a request that does not ask for compression**, with
#: 406 and a JSON body saying so -- which reads exactly like a rejected key and
#: cost an evening to tell apart. requests sends this by default; it is written
#: out here so that nobody removes it by tidying.
REGISTER_HEADERS = {"Accept-Encoding": "gzip, deflate"}

#: The one file in the register archive, and the NeTEx namespace its elements
#: carry.
REGISTER_MEMBER = "_stops.xml"
NETEX = "{http://www.netex.org.uk/netex}"

#: The key under which a register entry carries the national stop number that
#: the feed calls ``stop_id``.
REGISTER_JOIN_KEY = "rikshallplats"

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

#: The projection distances are measured in. SWEREF 99 TM covers Sweden and is
#: metric, which is all this asks of it.
METRIC_CRS = "EPSG:3006"

#: How far the register may move a stop before the build says so. Under this it
#: is the same spot written to a different number of decimals; over it, somebody
#: should know which stop moved and by how much.
MOVED_M = 25.0

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

#: The stop register is a dataset of its own, named separately because the page
#: carries data from both: the feed says what calls, the register says where.
REGISTER_METADATA = SourceMetadata(
    name="Stops data",
    url="https://www.trafiklab.se/api/netex-datasets/stops-data/",
)

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

    def __init__(self, cache_dir: str = ".cache", api_key: str | None = None, register_key: str | None = None, timeout: int = 600):
        """Initialize the Trafiklab source.

        Args:
            cache_dir: Where the object cache and the two archives live
            api_key: The GTFS key, or None to read :data:`KEY_VARIABLE`
            register_key: The stop register's key, a different one, or None to
                read :data:`REGISTER_KEY_VARIABLE`
            timeout: Seconds a download may take
        """
        self.cache = ObjectCache(cache_dir=f"{cache_dir}/objects")
        self.archive = Path(cache_dir) / "gtfs" / "sweden.zip"
        self.register_archive = Path(cache_dir) / "gtfs" / "stops-netex.zip"
        self.api_key = api_key
        self.register_key = register_key
        self.timeout = timeout

    def dataset(self, force_download: bool = False) -> Path:
        """The timetable feed, downloaded once and kept.

        **Not re-fetched on every build.** It is 44 MB, a Bronze key allows
        fifty calls a month, and the data changes at most daily; a build that
        re-downloaded would spend the quota on a file it already has.

        Args:
            force_download: Fetch it again even if it is already here

        Returns:
            Where the zip is.
        """
        return self._fetch(self.archive, DATASET_URL, self.api_key, KEY_VARIABLE, "GTFS Sverige 2", force_download)

    def register(self, force_download: bool = False) -> Path:
        """The national stop register, downloaded once and kept.

        Args:
            force_download: Fetch it again even if it is already here

        Returns:
            Where the zip is. 11 MB, holding one 331 MB NeTEx document.
        """
        return self._fetch(self.register_archive, REGISTER_URL, self.register_key, REGISTER_KEY_VARIABLE, "the stop register", force_download)

    def _fetch(self, into: Path, url: str, given: str | None, variable: str, what: str, force_download: bool) -> Path:
        """Download one of the two archives, unless it is already here.

        Args:
            into: Where to keep it
            url: The address, with a ``{key}`` to substitute
            given: The key passed to the constructor, or None
            variable: The environment variable to read instead
            what: What to call it when saying something about it
            force_download: Fetch it again even if it is already here

        Returns:
            Where the archive is.

        Raises:
            TrafiklabError: If it must be fetched and no key was given, or the
                download failed. **The key is never in the message**: it is
                substituted into the URL at the last moment and the URL is not
                reported.
        """
        if into.exists() and not force_download:
            return into

        key = given or os.environ.get(variable, "")
        if not key:
            raise TrafiklabError(f"no key for {what}: set {variable} in the environment or in trails/.env")

        print(f"Downloading {what} (one of {MONTHLY_CALLS} calls a month)...")
        into.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = requests.get(url.format(key=key), timeout=self.timeout, stream=True, headers=REGISTER_HEADERS)
            response.raise_for_status()
            with into.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    out.write(chunk)
        except requests.RequestException as e:
            raise TrafiklabError(f"could not fetch {what}: {type(e).__name__}") from None

        print(f"  {into.stat().st_size / 1e6:.1f} MB")
        return into

    def placed(self, wanted: set[str], force_download: bool = False) -> dict[str, Point]:
        """Where the register says each of those stops is.

        **Read as a stream and only the wanted stops kept.** The document is
        331 MB; what this costs in memory is the box, not the country.

        **One entry per stop, and the parent is the one taken.** The register
        splits a place by type -- ``SE:050:StopPlace:59149`` alongside
        ``59149_1`` for its bus side and ``59149_2`` for its rail side -- and
        all of them carry the same centroid, so the unsuffixed one is enough
        and the suffixed ones are skipped.

        Args:
            wanted: National stop numbers, as the feed's ``stop_id`` gives them
            force_download: Fetch the register again

        Returns:
            A point per stop number the register knows. A stop it does not know
            is absent rather than guessed at.
        """
        archive = self.register(force_download=force_download)
        found: dict[str, Point] = {}
        with zipfile.ZipFile(archive) as register, register.open(REGISTER_MEMBER) as raw:
            for _, element in ElementTree.iterparse(raw, events=("end",)):
                if element.tag != f"{NETEX}StopPlace":
                    continue
                identity = element.get("id") or ""
                if not identity.rsplit(":", 1)[-1].isdigit():
                    element.clear()
                    continue
                number = next(
                    (
                        pair.findtext(f"{NETEX}Value")
                        for pair in element.findall(f"{NETEX}keyList/{NETEX}KeyValue")
                        if pair.findtext(f"{NETEX}Key") == REGISTER_JOIN_KEY
                    ),
                    None,
                )
                where = element.find(f"{NETEX}Centroid/{NETEX}Location")
                if number in wanted and where is not None:
                    latitude, longitude = where.findtext(f"{NETEX}Latitude"), where.findtext(f"{NETEX}Longitude")
                    if latitude and longitude and number is not None:
                        found[number] = Point(float(longitude), float(latitude))
                element.clear()
        return found

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
        # ``placed`` in the key: an entry written before the register said where
        # the stations are is not this frame.
        cache_key = f"trafiklab_stops_{min_lat}_{min_lon}_{max_lat}_{max_lon}_{'-'.join(MODES)}_placed"

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
        gdf = self._placed_by_the_register(gdf, force_download=force_download)
        self.cache.save(cache_key, gdf, metadata={"bounds": list(bounds), "count": len(gdf)})
        return gdf

    def _placed_by_the_register(self, gdf: gpd.GeoDataFrame, force_download: bool) -> gpd.GeoDataFrame:
        """Move each stop to where the national register says it is.

        Args:
            gdf: The stops as the feed placed them
            force_download: Fetch the register again

        Returns:
            The same frame with its geometry replaced wherever the register
            knows the stop, and the moves reported.

        Raises:
            TrafiklabError: If the register names a stop the feed did not, which
                cannot happen while the join is on the feed's own ids and would
                mean the two datasets had drifted apart.
        """
        if not len(gdf):
            return gdf
        where = self.placed(set(gdf["stop_id"]), force_download=force_download)
        if unknown := set(where) - set(gdf["stop_id"]):
            raise TrafiklabError(f"the register answered about stops nobody asked after: {sorted(unknown)[:3]}")

        metres = gdf.to_crs(METRIC_CRS).geometry
        moved: list[tuple[float, str]] = []
        points = []
        for (_, row), before in zip(gdf.iterrows(), metres, strict=True):
            after = where.get(row["stop_id"])
            points.append(after if after is not None else row.geometry)
            if after is not None:
                gap = before.distance(gpd.GeoSeries([after], crs=gdf.crs).to_crs(METRIC_CRS).iloc[0])
                if gap > MOVED_M:
                    moved.append((gap, str(row["name"])))
        placed = gdf.set_geometry(gpd.GeoSeries(points, crs=gdf.crs))

        missing = [str(name) for name, stop in zip(gdf["name"], gdf["stop_id"], strict=True) if stop not in where]
        print(f"  placed by the register: {len(where)} of {len(gdf)}" + (f"; left where the feed had them: {sorted(missing)}" if missing else ""))
        if moved:
            print(f"  moved more than {MOVED_M:g} m: " + ", ".join(f"{name} {gap:.0f} m" for gap, name in sorted(moved, reverse=True)))
        return placed

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

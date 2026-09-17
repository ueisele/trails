"""Scheduled public transport in Norway, from Entur's national journey planner.

**What this answers is whether anything calls at a place, and under which
line.** Both map sources place quays and stops -- the place-name register names
them, OSM tags them -- and neither says whether anything sails or drives. The
difference matters on this coast: measured over Lomsdal-Visten on 2026-09-17,
four of the register's seventeen quays have no scheduled call at all, and the
three quays that reach the park (Bønå, Visten, Visthus) are served by a single
express-boat line.

Entur is the national data hub for Norwegian public transport. The journey
planner's GraphQL API needs no key; it asks only that a client identify itself
with an ``ET-Client-Name`` header, which :data:`CLIENT_NAME` is.

**The lines are read off the stop place rather than off its departures.** A
departure window answers *what sails this week*, which makes a build depend on
the day it ran and loses a seasonal line out of season. ``quays { lines }`` is
the structural answer, and it is the one that found both Hurtigruten and Havila
at Brønnøysund kystrutekai, which share the coastal route and alternate.

**One stop place is one place, which is why this draws the buses and not OSM.**
Measured over the same box on 2026-09-17: OSM holds 628 stops there against
Entur's 430, because OSM tags a pole per direction and only 414 of its 628 names
are distinct. Every one of the 628 stands within **136 m** of an Entur stop
place and 618 of them carry the same name -- so nothing is lost by drawing the
register instead, and what is gained is the line, the authority and a link to
the board.
"""

import json
import time
from dataclasses import dataclass

import geopandas as gpd
import requests
from shapely.geometry import Point

from ..cache import Object as ObjectCache

#: The journey planner's GraphQL endpoint. Keyless.
ENDPOINT = "https://api.entur.io/journey-planner/v3/graphql"

#: What this client calls itself, as Entur's terms of use require: a header
#: ``ET-Client-Name`` of the form ``<organisation>-<application>``.
CLIENT_NAME = "uweeisele-trails-atlas"

#: Where a reader is sent for the live departure board of one stop place.
#:
#: **This form and not the shorter ``/nearby/<id>``**, which answers 200 and
#: renders *Dead end*. Measured 2026-09-17 in Firefox: this one renders the
#: stop's name and its board, and the short one does not. An id Entur does not
#: know renders an empty board rather than an error, which is why only ids that
#: came from Entur itself are ever written into a link.
STOP_PAGE = "https://entur.no/nearby-stop-place-detail?id={stop_id}"

#: The transport modes read, in Entur's vocabulary, and the English word each is
#: shown under. Ferries and express boats share ``water``; what tells them apart
#: is the line, not the mode.
MODES = {"rail": "train", "air": "flight", "water": "boat", "bus": "bus"}

#: The mode a boat calls under, named because the quays ask for it by itself.
WATER_MODE = "water"

#: What joins several lines, or several modes, into one field. The same
#: separator the chains are named by, so a popup reads the same either way.
SEPARATOR = " / "

#: How many stop places one batched query asks about. The whole Lomsdal-Visten
#: box is 457, so this is ten round trips there.
BATCH = 50


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the timetable data."""

    name: str = "Entur, the national stop register and timetables"
    provider: str = "Entur AS"
    country: str = "NO"
    url: str = "https://developer.entur.org/"
    license: str = "NLOD 2.0"
    attribution: str = "Contains data from Entur under NLOD 2.0"


METADATA = SourceMetadata()

#: Bounding box as (min_lon, min_lat, max_lon, max_lat), matching GeoPandas.
Bounds = tuple[float, float, float, float]

#: Every stop place of a box, with the modes it is registered under.
_BY_BBOX = """
{{
  stopPlacesByBbox(
    minimumLatitude: {min_lat}, maximumLatitude: {max_lat},
    minimumLongitude: {min_lon}, maximumLongitude: {max_lon}
  ) {{ id name latitude longitude transportMode }}
}}
"""


class EnturError(RuntimeError):
    """Raised when Entur could not be reached, or answered with errors."""


def lines_column(mode: str) -> str:
    """The column a mode's lines are returned under.

    Args:
        mode: One of :data:`MODES`

    Returns:
        The column name, e.g. ``bus_lines``.
    """
    return f"{mode}_lines"


#: The columns :meth:`Source.scheduled_stops` returns, in order.
COLUMNS = ["stop_id", "name", "modes", *(lines_column(mode) for mode in MODES), "operator", "entur_url", "geometry"]


class Source:
    """Loader for the stop places a scheduled service calls at."""

    def __init__(
        self,
        cache_dir: str = ".cache",
        endpoint: str = ENDPOINT,
        client_name: str = CLIENT_NAME,
        timeout: int = 120,
        max_rounds: int = 3,
        initial_backoff: float = 10.0,
    ):
        """Initialize the Entur source.

        Args:
            cache_dir: Where the object cache lives
            endpoint: The GraphQL endpoint to post to
            client_name: What to send as ``ET-Client-Name``
            timeout: Seconds one request may take
            max_rounds: How often to retry the endpoint before giving up
            initial_backoff: Seconds to wait after the first failure, doubled
                on each round after it
        """
        self.cache = ObjectCache(cache_dir=f"{cache_dir}/objects")
        self.endpoint = endpoint
        self.client_name = client_name
        self.timeout = timeout
        self.max_rounds = max_rounds
        self.initial_backoff = initial_backoff

    def query(self, document: str) -> dict:
        """Run one GraphQL document, retrying the endpoint with backoff.

        Args:
            document: The GraphQL document to post

        Returns:
            The ``data`` object of the response

        Raises:
            EnturError: If every round failed, or the response carries errors.
                **A GraphQL error is a failure here and not a warning**: the
                response still carries HTTP 200 and a ``data`` of nulls, and a
                build that read those would quietly draw every quay as unserved.
        """
        headers = {"Content-Type": "application/json", "ET-Client-Name": self.client_name}
        payload = json.dumps({"query": document}).encode("utf-8")
        failures: list[str] = []
        backoff = self.initial_backoff

        for round_number in range(1, self.max_rounds + 1):
            try:
                response = requests.post(self.endpoint, data=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                answered = response.json()
                if answered.get("errors"):
                    raise EnturError(f"Entur answered with errors: {answered['errors'][:2]}")
                data: dict = answered["data"]
                return data
            except (requests.RequestException, ValueError, KeyError) as e:
                print(f"  Entur failed (round {round_number}/{self.max_rounds}): {e}")
                failures.append(f"round {round_number}: {e}")

            if round_number < self.max_rounds:
                print(f"  Retrying Entur in {backoff:.0f}s...")
                time.sleep(backoff)
                backoff *= 2

        raise EnturError("Entur could not be reached:\n  " + "\n  ".join(failures))

    def scheduled_stops(self, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        """Fetch the stop places within a box that a scheduled service calls at.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            force_download: Bypass the cache and ask Entur again

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns in
            :data:`COLUMNS`: ``stop_id`` (the national register's, e.g.
            ``NSR:StopPlace:48932``), ``name``, ``modes`` (the English words of
            :data:`MODES` it is actually served under), one ``<mode>_lines``
            column per mode holding the lines of that mode as ``code name``,
            ``operator`` (the authorities behind them) and ``entur_url`` (its
            live departure board).

            **A stop place registered under a mode but carrying no line of it is
            left out of that mode**, because being registered is not being
            served, and one carrying no line at all is left out altogether.
            Measured over Lomsdal-Visten on 2026-09-17: two of the box's 37
            water stops, Vikdal ferjekai and Toftsundet hurtigbåtkai, neither
            with a single departure in a sixty-day window; and 32 of its 430 bus
            and rail stops, among them both airports, which are registered for a
            bus that no longer calls and are drawn for their flights instead.
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        # The modes in the key: an entry written for water alone is not this frame.
        cache_key = f"entur_stops_{min_lat}_{min_lon}_{max_lat}_{max_lon}_{'-'.join(MODES)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading Entur stops from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        print(f"Querying Entur for scheduled stops in {min_lat},{min_lon},{max_lat},{max_lon}...")
        places = self.query(_BY_BBOX.format(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon))
        registered = [place for place in places["stopPlacesByBbox"] if place.get("id") and set(place.get("transportMode") or ()) & set(MODES)]
        print(f"  {len(places['stopPlacesByBbox'])} stop places, {len(registered)} registered under a mode this map draws")

        serving = self._lines_of([place["id"] for place in registered])
        records, unserved = [], []
        for place in registered:
            lines, authorities = serving.get(place["id"], ({}, ()))
            if not lines:
                unserved.append(place["name"])
                continue
            record = {
                "stop_id": place["id"],
                "name": place["name"],
                "modes": SEPARATOR.join(MODES[mode] for mode in MODES if mode in lines),
                "operator": SEPARATOR.join(authorities) or None,
                "entur_url": STOP_PAGE.format(stop_id=place["id"]),
                "geometry": Point(place["longitude"], place["latitude"]),
            }
            for mode in MODES:
                record[lines_column(mode)] = SEPARATOR.join(lines[mode]) if mode in lines else None
            records.append(record)
        if unserved:
            print(f"  registered but with no line calling, left out: {', '.join(sorted(unserved))}")

        gdf = gpd.GeoDataFrame(records, columns=COLUMNS, crs="EPSG:4326")
        self.cache.save(cache_key, gdf, metadata={"bounds": list(bounds), "count": len(gdf)})
        return gdf

    def _lines_of(self, stop_ids: list[str]) -> dict[str, tuple[dict[str, tuple[str, ...]], tuple[str, ...]]]:
        """The lines serving each stop place, by mode, and whose they are.

        **One query per batch rather than one per stop**, with an alias per stop:
        a national register id holds colons and cannot itself be an alias, so the
        stops are named ``s0``, ``s1`` and read back by that number.

        Args:
            stop_ids: National register ids, e.g. ``NSR:StopPlace:48932``

        Returns:
            Per id, the lines of each mode of :data:`MODES` that has any --
            written ``code name``, or whichever of the two the line carries --
            and the distinct authorities behind them, each in the order Entur
            listed them. A mode nothing calls under is absent rather than empty.
        """
        found: dict[str, tuple[dict[str, tuple[str, ...]], tuple[str, ...]]] = {}
        for start in range(0, len(stop_ids), BATCH):
            batch = stop_ids[start : start + BATCH]
            fields = " ".join(
                f's{index}: stopPlace(id: "{stop_id}") {{ id quays {{ lines {{ publicCode name transportMode authority {{ name }} }} }} }}'
                for index, stop_id in enumerate(batch)
            )
            answered = self.query(f"{{ {fields} }}")
            for index, stop_id in enumerate(batch):
                place = answered.get(f"s{index}")
                if not place:
                    continue
                by_mode: dict[str, dict[str, None]] = {}
                authorities: dict[str, None] = {}
                for quay in place.get("quays") or []:
                    for line in quay.get("lines") or []:
                        mode = line.get("transportMode")
                        if mode not in MODES:
                            continue
                        label = " ".join(part for part in (line.get("publicCode"), line.get("name")) if part)
                        if label:
                            by_mode.setdefault(mode, {})[label] = None
                        authority = (line.get("authority") or {}).get("name")
                        if authority:
                            authorities[authority] = None
                found[stop_id] = ({mode: tuple(labels) for mode, labels in by_mode.items()}, tuple(authorities))
        return found

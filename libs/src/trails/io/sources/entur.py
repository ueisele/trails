"""Scheduled public transport in Norway, from Entur's national journey planner.

**What this answers is whether a boat calls at a quay, and under which line.**
Both map sources place quays -- the place-name register names them, OSM tags
them ``amenity=ferry_terminal`` -- and neither says whether anything sails. The
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

#: The transport mode a boat calls under, in Entur's vocabulary. Ferries and
#: express boats share it; what tells them apart is the line, not the mode.
WATER_MODE = "water"

#: How many stop places one batched query asks about. The whole Lomsdal-Visten
#: box is 37, so this is one round trip there; the chunking is for the next box.
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

#: Every stop place of a box, with the modes it is served under.
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


class Source:
    """Loader for the stop places a scheduled boat calls at."""

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

    def water_stops(self, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        """Fetch the stop places within a box that a scheduled boat calls at.

        Args:
            bounds: (min_lon, min_lat, max_lon, max_lat) in WGS84
            force_download: Bypass the cache and ask Entur again

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``stop_id`` (the national register's, e.g. ``NSR:StopPlace:48932``),
            ``name``, ``lines`` (the public codes serving it, joined), ``operator``
            (the authorities behind them, joined) and ``entur_url`` (its live
            departure board). Empty if nothing in the box is served by water.

            **A stop place carrying the water mode but no water line is left
            out**, because being registered is not being served. Measured over
            Lomsdal-Visten on 2026-09-17: two of the box's 37, Vikdal ferjekai
            and Toftsundet hurtigbåtkai, and neither has a single departure in a
            sixty-day window. They are what this loader exists to tell apart
            from a quay a boat actually calls at.
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        # ``_served`` in the key: an entry written when this kept the
        # registered-but-unserved stops is not this frame.
        cache_key = f"entur_water_stops_{min_lat}_{min_lon}_{max_lat}_{max_lon}_served"

        if not force_download and self.cache.exists(cache_key):
            print("Loading Entur water stops from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        print(f"Querying Entur for scheduled stops in {min_lat},{min_lon},{max_lat},{max_lon}...")
        places = self.query(_BY_BBOX.format(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon))
        water = [
            place for place in places["stopPlacesByBbox"] if place.get("transportMode") and WATER_MODE in place["transportMode"] and place.get("id")
        ]
        print(f"  {len(places['stopPlacesByBbox'])} stop places, {len(water)} of them served by boat")

        serving = self._lines_of([place["id"] for place in water])
        records, unserved = [], []
        for place in water:
            lines, authorities = serving.get(place["id"], ((), ()))
            if not lines:
                unserved.append(place["name"])
                continue
            records.append(
                {
                    "stop_id": place["id"],
                    "name": place["name"],
                    "lines": " / ".join(lines),
                    "operator": " / ".join(authorities) or None,
                    "entur_url": STOP_PAGE.format(stop_id=place["id"]),
                    "geometry": Point(place["longitude"], place["latitude"]),
                }
            )
        if unserved:
            print(f"  registered but with no boat line, left out: {', '.join(sorted(unserved))}")

        gdf = gpd.GeoDataFrame(records, columns=["stop_id", "name", "lines", "operator", "entur_url", "geometry"], crs="EPSG:4326")
        self.cache.save(cache_key, gdf, metadata={"bounds": list(bounds), "count": len(gdf)})
        return gdf

    def _lines_of(self, stop_ids: list[str]) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
        """The lines serving each stop place, and whose they are.

        **One query per batch rather than one per stop**, with an alias per stop:
        a national register id holds colons and cannot itself be an alias, so the
        stops are named ``s0``, ``s1`` and read back by that number.

        Args:
            stop_ids: National register ids, e.g. ``NSR:StopPlace:48932``

        Returns:
            Per id, the distinct public codes of the water lines calling there
            and the distinct authorities behind them, each in the order Entur
            listed them.
        """
        found: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
        for start in range(0, len(stop_ids), BATCH):
            batch = stop_ids[start : start + BATCH]
            fields = " ".join(
                f's{index}: stopPlace(id: "{stop_id}") {{ id quays {{ lines {{ publicCode transportMode authority {{ name }} }} }} }}'
                for index, stop_id in enumerate(batch)
            )
            answered = self.query(f"{{ {fields} }}")
            for index, stop_id in enumerate(batch):
                place = answered.get(f"s{index}")
                if not place:
                    continue
                codes: dict[str, None] = {}
                authorities: dict[str, None] = {}
                for quay in place.get("quays") or []:
                    for line in quay.get("lines") or []:
                        if line.get("transportMode") != WATER_MODE:
                            continue
                        if line.get("publicCode"):
                            codes[line["publicCode"]] = None
                        authority = (line.get("authority") or {}).get("name")
                        if authority:
                            authorities[authority] = None
                found[stop_id] = (tuple(codes), tuple(authorities))
        return found

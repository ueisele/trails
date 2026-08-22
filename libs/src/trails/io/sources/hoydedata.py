"""Ground heights from Kartverket's national height model.

``ws.geonorge.no/hoydedata/v1/punkt`` answers with the height of up to fifty
points per request, read out of the same DTM1 the WCS coverage serves — sampled
at 1 m the two agree to a median of 0.00 m. For points strung along a line the
point endpoint is far the cheaper of the two: this network's samples cost about
110 MB through it against 7.8 GB of raster tiles for the same numbers.

**Two of its answers are not heights, and both look like one.** Over water it
returns a depth from the depth-contour model — ``datakilde: "dybdekurver"`` and
a negative ``z``, which is how a coastal path comes back at -276 m — and outside
its coverage it returns ``z: null``. So ``datakilde`` is checked on every point
and anything that is not a terrain model is carried as a gap rather than as a
number.

**The point store is the part of this that matters.** Without it every build
asks again: the map was rebuilt about fifteen times in one afternoon of work on
it, which would have been 300,000 requests against a public service. With it,
the second build asks nothing, and a source update re-fetches only the ground
that actually moved. It deduplicates within one run as well as between runs —
over this network 28 % of the samples are a coordinate already asked about,
mostly edge ends meeting at a node.

Doing this once is fair use; doing it on every build is not, and the same
restraint sets the concurrency. Six parallel requests put a run of twenty
thousand at about sixteen minutes. Twelve measured faster and this is somebody
else's endpoint.
"""

import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SERVICE_URL = "https://ws.geonorge.no/hoydedata/v1/punkt"

#: Points the endpoint accepts in one request. Its own documented cap.
MAX_POINTS = 50

#: Requests in flight at once. Not a performance setting: twelve is faster and
#: this is a bulk run against a public service, where restraint counts for more
#: than speed.
DEFAULT_WORKERS = 6

#: Coordinate system requests are made in, and the one the heights come back
#: keyed to. It is the metric CRS the network is built in, so no reprojection
#: happens anywhere in this path.
COORDINATE_SYSTEM = 25833
REQUEST_CRS = f"EPSG:{COORDINATE_SYSTEM}"

#: What a ``datakilde`` naming a terrain model starts with. Anything else — the
#: depth contours over water, or nothing at all outside the coverage — is not a
#: ground height, and is read as no reading rather than as a number.
TERRAIN_MODEL = "dtm"

#: What the service calls open sea in its ``terreng`` field. It is a different
#: question from :data:`TERRAIN_MODEL` and answers a different one: that says
#: whether the number is a ground height, this says what the point is *on*, and
#: it is what tells a line drawn across a fjord that it is a crossing rather
#: than a walk. **Tested for by name and never by exclusion**: measured, a
#: perfectly good ``dtm1`` reading comes back with no ``terreng`` at all, and a
#: lake answers ``InnsjøRegulert`` from a lake model — walked ground with
#: nothing read along it, which is neither sea nor a height.
SEA_TERRAIN = "Havflate"

#: The other coordinate system the service is asked in. It answers to longitude
#: and latitude as readily as to :data:`COORDINATE_SYSTEM` — measured, not
#: assumed — which is what lets a consumer holding only degrees, such as a map
#: page, ask it without reprojecting anything. Nothing in this module uses it:
#: the network is built in the metric grid and asking in it costs no conversion.
WGS84_COORDINATE_SYSTEM = 4326

#: Sent so the service's operators can identify the client, as
#: :mod:`trails.io.sources.overpass` already does for the same reason. Said
#: twice rather than shared, so neither module's politeness depends on the other
#: still existing.
USER_AGENT = "trails-analysis/0.1 (+https://github.com/ueisele/trails)"

#: What the store keys on, in centimetres: a coordinate rounded finer than
#: anything that matters and coarser than floating-point noise. Deliberately not
#: a coarser grid — in steep ground half a metre sideways is half a metre of
#: height, and the whole reason for sampling at all is to avoid errors of that
#: size.
KEY_UNITS_PER_M = 100

#: Half the range an axis may span in key units. The two halves of a coordinate
#: are packed into one integer so that a lookup is a binary search rather than a
#: dictionary of a million tuples; that holds for any coordinate a metric
#: national grid produces, and is checked rather than assumed.
_AXIS_LIMIT = 2**31


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the height data."""

    name: str = "Høydedata DTM1"
    provider: str = "Kartverket"
    country: str = "NO"
    url: str = SERVICE_URL
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"


METADATA = SourceMetadata()


def _pack(east: np.ndarray, north: np.ndarray) -> np.ndarray:
    """Fold a pair of key coordinates into one integer.

    Args:
        east: Eastings in key units
        north: Northings in key units

    Returns:
        One int64 per coordinate

    Raises:
        ValueError: If a coordinate is too far from the origin to pack, which
            means these are not the coordinates this was built for
    """
    if len(east) and (np.abs(east).max() >= _AXIS_LIMIT or np.abs(north).max() >= _AXIS_LIMIT):
        raise ValueError(f"a coordinate lies outside +/-{_AXIS_LIMIT / KEY_UNITS_PER_M:,.0f} m of the origin; is this {REQUEST_CRS}?")
    return (east << 32) | (north & 0xFFFFFFFF)


def _unpack(packed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Read a packed key back as a pair of coordinates.

    Args:
        packed: Keys from :func:`_pack`

    Returns:
        Eastings and northings in key units
    """
    north = packed & 0xFFFFFFFF
    return packed >> 32, np.where(north >= _AXIS_LIMIT, north - 2**32, north)


def keys_of(coordinates: np.ndarray) -> np.ndarray:
    """Turn coordinates into the keys the store is written in.

    Args:
        coordinates: ``(n, 2)`` in :data:`REQUEST_CRS`

    Returns:
        One int64 key per coordinate
    """
    rounded = np.rint(np.asarray(coordinates, dtype=float).reshape(-1, 2) * KEY_UNITS_PER_M).astype(np.int64)
    return _pack(rounded[:, 0], rounded[:, 1])


class PointStore:
    """Every coordinate this project has ever asked the endpoint about.

    **A point with no height is still a row.** Over water and outside the
    model's coverage the answer is not a height, and a store that recorded only
    the successes would ask again about exactly the points that can never
    answer — on every build, for as long as the network touches a coast.

    Held in parquet, as the project holds every other table, and rewritten
    atomically: a store half-written by an interrupted run would be served as a
    cache hit by the next one.
    """

    def __init__(self, path: Path | str):
        """Open a store, reading back whatever is already in it.

        Args:
            path: Parquet file holding the table
        """
        self.path = Path(path)
        self._keys = np.empty(0, dtype=np.int64)
        self._heights = np.empty(0, dtype=float)
        if self.path.exists():
            stored = pd.read_parquet(self.path)
            self._replace(_pack(stored["east"].to_numpy(dtype=np.int64), stored["north"].to_numpy(dtype=np.int64)), stored["z"].to_numpy(dtype=float))

    def __len__(self) -> int:
        """How many coordinates the store holds."""
        return len(self._keys)

    def _replace(self, keys: np.ndarray, heights: np.ndarray) -> None:
        """Take a new table, sorted so a lookup can bisect it.

        Args:
            keys: Packed coordinates
            heights: Their heights, NaN where nothing could be read
        """
        order = np.argsort(keys, kind="stable")
        self._keys, self._heights = keys[order], heights[order]

    def lookup(self, keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Read back what is already known about a set of coordinates.

        Args:
            keys: Packed coordinates

        Returns:
            Their heights, and whether each one was in the store at all. The two
            are not the same question: a height of NaN that *is* in the store is
            a point the endpoint has already answered about and cannot answer
            better.
        """
        heights = np.full(len(keys), math.nan)
        if not len(self._keys) or not len(keys):
            return heights, np.zeros(len(keys), dtype=bool)

        position = np.searchsorted(self._keys, keys)
        found = (position < len(self._keys)) & (self._keys[np.minimum(position, len(self._keys) - 1)] == keys)
        heights[found] = self._heights[position[found]]
        return heights, found

    def add(self, keys: np.ndarray, heights: np.ndarray) -> None:
        """Record what the endpoint answered.

        Args:
            keys: Packed coordinates, without repeats
            heights: Their heights, NaN where nothing could be read
        """
        if not len(keys):
            return
        combined = np.concatenate([self._keys, keys])
        values = np.concatenate([self._heights, heights])
        # A coordinate asked about twice keeps its first answer: the ground has
        # not moved, and letting the second win would make the store depend on
        # the order requests happened to come back in.
        unique, first = np.unique(combined, return_index=True)
        self._replace(unique, values[first])

    def save(self) -> None:
        """Write the store out, atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        east, north = _unpack(self._keys)
        partial = self.path.with_suffix(self.path.suffix + ".part")
        pd.DataFrame({"east": east, "north": north, "z": self._heights}).to_parquet(partial, index=False)
        partial.replace(self.path)


class Source:
    """Loader for ground heights, backed by a store of every point ever asked."""

    def __init__(
        self,
        cache_dir: str = ".cache",
        timeout: int = 60,
        workers: int = DEFAULT_WORKERS,
        max_attempts: int = 4,
        initial_backoff: float = 2.0,
        flush_seconds: float = 60.0,
    ):
        """Initialize the source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds per request
            workers: Requests in flight at once. Leave it at
                :data:`DEFAULT_WORKERS`; see this module's docstring.
            max_attempts: Tries per request before giving up on the run
            initial_backoff: Seconds before the second try, doubled after each
            flush_seconds: How often the store is written out mid-run. A run of
                twenty thousand requests takes a quarter of an hour, and one
                that is interrupted must not have to start again.
        """
        self.store = PointStore(Path(cache_dir) / "elevation" / f"hoydedata_{COORDINATE_SYSTEM}.parquet")
        self.timeout = timeout
        self.workers = workers
        self.max_attempts = max_attempts
        self.initial_backoff = initial_backoff
        self.flush_seconds = flush_seconds
        self._local = threading.local()

    def elevations(self, coordinates: np.ndarray) -> np.ndarray:
        """Read the ground height at each of a set of coordinates.

        Args:
            coordinates: ``(n, 2)`` in :data:`REQUEST_CRS`, repeats and all

        Returns:
            One height per coordinate, in input order, NaN where the endpoint
            has nothing to say about that ground

        Raises:
            requests.RequestException: If a request could not be completed after
                ``max_attempts`` tries. Whatever had been answered by then is in
                the store, so a second run resumes rather than starting again.
        """
        keys = keys_of(coordinates)
        unique, inverse = np.unique(keys, return_inverse=True)
        heights, known = self.store.lookup(unique)

        missing = np.flatnonzero(~known)
        print(f"  {len(keys):,} samples, {len(unique):,} distinct coordinates, {len(unique) - len(missing):,} of them already in the store")
        if len(missing):
            heights[missing] = self._fetch(unique[missing])
            self.store.save()
        return heights[inverse]

    def _fetch(self, keys: np.ndarray) -> np.ndarray:
        """Ask the endpoint about every coordinate it has not been asked about.

        Args:
            keys: Packed coordinates, without repeats

        Returns:
            Their heights, NaN where the answer was not a ground height
        """
        east, north = _unpack(keys)
        points = np.stack([east / KEY_UNITS_PER_M, north / KEY_UNITS_PER_M], axis=1)
        batches = [points[start : start + MAX_POINTS] for start in range(0, len(points), MAX_POINTS)]
        print(f"  asking {METADATA.name} about {len(points):,} of them, {MAX_POINTS} at a time, {self.workers} requests at once...")

        heights = np.full(len(points), math.nan)
        started = last_flush = time.monotonic()
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            # `map` hands the answers back in the order they were asked for
            # however they came in, which is what lets a batch be put back where
            # it belongs by its position and what makes everything before the
            # one in hand complete.
            for index, values in enumerate(pool.map(self._batch, batches)):
                heights[index * MAX_POINTS : index * MAX_POINTS + len(values)] = values

                now = time.monotonic()
                if now - last_flush >= self.flush_seconds:
                    # Everything answered so far, so an interrupted run resumes.
                    self.store.add(keys[: (index + 1) * MAX_POINTS], heights[: (index + 1) * MAX_POINTS])
                    self.store.save()
                    last_flush = now
                    done = index + 1
                    rate = done / (now - started)
                    print(f"    {done:,}/{len(batches):,} requests, {rate:.1f}/s, about {(len(batches) - done) / rate / 60:.0f} min left")

        self.store.add(keys, heights)
        unanswered = int(np.count_nonzero(np.isnan(heights)))
        print(f"    {len(batches):,} requests in {(time.monotonic() - started) / 60:.1f} min; {unanswered:,} points had no ground height")
        return heights

    def _session(self) -> requests.Session:
        """Get this thread's HTTP session.

        One connection per worker, kept open across its requests: twenty
        thousand fresh TLS handshakes would be both slower and ruder than the
        six connections this holds.

        Returns:
            A session belonging to the calling thread alone
        """
        session: requests.Session | None = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            self._local.session = session
        return session

    def _batch(self, points: np.ndarray) -> np.ndarray:
        """Ask about up to :data:`MAX_POINTS` coordinates, retrying failures.

        Args:
            points: ``(n, 2)`` in :data:`REQUEST_CRS`

        Returns:
            Their heights, NaN where the answer was not a ground height

        Raises:
            requests.RequestException: If every attempt failed
            ValueError: If the answer does not line up with the question
        """
        asked = json.dumps([[round(east, 2), round(north, 2)] for east, north in points.tolist()])
        parameters: dict[str, str | int] = {"punkter": asked, "koordsys": COORDINATE_SYSTEM}

        backoff = self.initial_backoff
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._session().get(SERVICE_URL, params=parameters, timeout=self.timeout)
                response.raise_for_status()
                return _readings(response.json(), len(points))
            except (requests.RequestException, ValueError) as failure:
                # A malformed answer is worth retrying for the same reason a
                # refused connection is: this endpoint is shared, and a busy
                # server here has been seen to answer moments later.
                if attempt == self.max_attempts:
                    raise
                print(f"  {METADATA.name} failed (try {attempt}/{self.max_attempts}): {failure}")
                time.sleep(backoff)
                backoff *= 2
        raise AssertionError("unreachable")


def _readings(payload: dict, expected: int) -> np.ndarray:
    """Read the heights out of one answer.

    Args:
        payload: Parsed response
        expected: How many points were asked about

    Returns:
        One height per point, in the order they were asked about, NaN where the
        answer was not a ground height

    Raises:
        ValueError: If the answer does not hold one point per question
    """
    points = payload.get("punkter")
    if not isinstance(points, list) or len(points) != expected:
        raise ValueError(f"asked about {expected} points and got {len(points) if isinstance(points, list) else payload}")
    return np.array([_reading(point) for point in points], dtype=float)


def _reading(point: dict) -> float:
    """Read one point's answer, rejecting what is not a ground height.

    Args:
        point: One entry of the response

    Returns:
        Its height, or NaN where the answer came from something that is not a
        terrain model — the depth contours over water, or nothing at all
    """
    source = point.get("datakilde")
    height = point.get("z")
    if height is None or not isinstance(source, str) or not source.lower().startswith(TERRAIN_MODEL):
        return math.nan
    return float(height)

"""Lantmäteriet's *Topografi 50 Nedladdning, vektor*, through the Geotorget delivery API.

The N50 of Sweden: paths, roads, water, land cover, buildings, names and
protected areas in one product, a GeoPackage per theme in SWEREF 99 TM, CC0.
It is not fetched by area. A subscription ordered for the whole country stands
in Geotorget, Lantmäteriet produces a *delivery* of it — fourteen zipped
GeoPackages, 5.4 GB, a week's edition — and the API below says what the
latest delivery holds and hands the files out:

    GET  {API_URL}/{order}/leverans/latest         status and size
    GET  {API_URL}/{order}/leverans/latest/files   one entry per file, each
                                                   with a signed path
    GET  {API_URL}/{order}{path}                   the file

Basic auth with the Geotorget login on every call. The order id is the one
*Mitt konto – Ärenden* shows on the order line; it is an identifier and not a
credential, but it names an account, so it arrives through the environment
like the login does. The API also has to be *ordered*, as the free product
*Geotorget Nedladdning*: without that the same login answers **403**.

The cache is a directory per delivery, named by the day the files were
produced, holding the zips and the GeoPackages unpacked beside them. A build
reads the newest delivery on disk and asks the API only when there is none, or
when told to — so a box is cut out of the country file with a bbox over its
spatial index, in the time it takes to read that box, and the API is not in
the path of an ordinary build at all.
"""

import base64
import json
import os
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import geopandas as gpd
import pyogrio

from trails.utils.geo import project_bounds
from trails.utils.tiles import Bounds

#: The delivery API.
API_URL = "https://api.lantmateriet.se/geotorget/nedladdning/v1"

#: Environment variables the order id and the login are read from. The login
#: is the one the height model uses too.
ORDER_VAR = "GEOTORGET_TOPOGRAFI50_ORDER"
USERNAME_VAR = "GEOTORGET_USERNAME"
PASSWORD_VAR = "GEOTORGET_PASSWORD"

#: What the GeoPackages are delivered in: SWEREF 99 TM.
CRS = "EPSG:3006"

#: The themes a delivery holds, each ``{theme}_sverige.zip`` with
#: ``{theme}_sverige.gpkg`` inside.
THEMES = (
    "administrativindelning",
    "anlaggningsomrade",
    "byggnadsverk",
    "hojd",
    "hydrografi",
    "kommunikation",
    "kulturhistorisklamning",
    "ledningar",
    "mark",
    "militartomrade",
    "naturvard",
    "norrapolcirkeln",
    "text",
)

#: The layers a walking map reads, by theme.
KOMMUNIKATION, HYDROGRAFI, BYGGNADSVERK, TEXT, NATURVARD, MARK = "kommunikation", "hydrografi", "byggnadsverk", "text", "naturvard", "mark"
LAYER_PATHS = "ovrig_vag"
LAYER_ROADS = "vaglinje"
LAYER_FERRIES = "farjeled"
LAYER_MOUNTAIN_WAYS = "transportled_fjall"
LAYER_TRAIL_POINTS = "ledintressepunkt_fjall"
LAYER_ROAD_POINTS = "vagpunkt"
LAYER_BUILDING_POINTS = "byggnadspunkt"
LAYER_TEXT_POINTS = "textpunkt"
LAYER_PROTECTED = "skyddadnatur"
LAYER_STREAMS = "hydrolinje"
LAYER_LAND = "mark"

#: The column every layer classifies itself by, and its stable id.
TYPE, ID, CREATED = "objekttyp", "objektidentitet", "skapad"

#: Seconds an API call may take.
TIMEOUT_S = 120

#: What a delivery directory is called: the day its files were produced.
DELIVERY_FILE = "delivery.json"
UNPACKED = "gpkg"

#: A delivery the API says can be downloaded.
READY = "LYCKAD"


@dataclass(frozen=True)
class File:
    """One file of a delivery, as the API lists it."""

    title: str
    #: Signed, relative to ``{API_URL}/{order}``; valid for a while.
    path: str
    length: int
    #: When the file was produced, ISO.
    updated: str

    @property
    def day(self) -> str:
        """The day the file was produced, which names the delivery."""
        return self.updated[:10]


@dataclass(frozen=True)
class Delivery:
    """What the API says about the latest delivery of an order."""

    id: str
    status: str
    files: tuple[File, ...]

    @property
    def day(self) -> str:
        """The day the delivery was produced."""
        return max(file.day for file in self.files)

    def file(self, title: str) -> File:
        """The file of that name.

        Raises:
            KeyError: If the delivery holds no such file
        """
        for file in self.files:
            if file.title == title:
                return file
        raise KeyError(f"the delivery of {self.day} holds no {title}")


def _auth_header(username: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


def _get_json(url: str, auth: str) -> object:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "Authorization": auth})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
        return json.load(answer)


def _download(url: str, auth: str, target: Path) -> None:
    """Fetch one file whole, to a part file first.

    Args:
        url: What to fetch
        auth: The ``Authorization`` header
        target: Where it goes once complete
    """
    partial = target.with_name(target.name + ".part")
    request = urllib.request.Request(url, headers={"Authorization": auth})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer, open(partial, "wb") as out:
        while chunk := answer.read(1 << 20):
            out.write(chunk)
    partial.replace(target)


def delivery_from(latest: object, listed: object) -> Delivery:
    """Read a delivery out of the API's two answers.

    Args:
        latest: ``GET …/leverans/latest``
        listed: ``GET …/leverans/latest/files``

    Returns:
        The delivery
    """
    assert isinstance(latest, dict) and isinstance(listed, list)
    files = tuple(
        File(title=str(entry["title"]), path=str(entry["path"]), length=int(entry["length"]), updated=str(entry["updated"]))
        for entry in listed
        if entry.get("type") == "application/octet-stream"
    )
    return Delivery(id=str(latest["objektidentitet"]), status=str(latest["status"]), files=files)


def zip_name(theme: str) -> str:
    """What a theme's archive is called."""
    return f"{theme}_sverige.zip"


def geopackage_name(theme: str) -> str:
    """What a theme's GeoPackage is called, inside its archive."""
    return f"{theme}_sverige.gpkg"


class Source:
    """The country file, one delivery on disk, read by box."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache",
        order: str | None = None,
        username: str | None = None,
        password: str | None = None,
        fetch: Callable[[str, str], object] = _get_json,
        download: Callable[[str, str, Path], None] = _download,
    ):
        """Point at the deliveries.

        Args:
            cache_dir: Root cache directory; deliveries go under ``topografi50``
            order: The order's id in Geotorget; :data:`ORDER_VAR` by default
            username: Geotorget login; :data:`USERNAME_VAR` by default
            password: Geotorget password; :data:`PASSWORD_VAR` by default
            fetch: How an API answer is read
            download: How a file is fetched
        """
        self.cache_dir = Path(cache_dir) / "topografi50"
        self.order = order if order is not None else os.environ.get(ORDER_VAR, "")
        self.username = username if username is not None else os.environ.get(USERNAME_VAR, "")
        self.password = password if password is not None else os.environ.get(PASSWORD_VAR, "")
        self.fetch = fetch
        self.download = download
        #: The delivery a read came from, once one has: its day.
        self.version: str | None = None

    @property
    def can_ask(self) -> bool:
        """Whether the API can be asked at all: an order and a login are set."""
        return bool(self.order and self.username and self.password)

    def on_disk(self) -> list[Path]:
        """The deliveries held, oldest first."""
        if not self.cache_dir.exists():
            return []
        return sorted(path for path in self.cache_dir.iterdir() if path.is_dir() and (path / DELIVERY_FILE).exists())

    def ask(self) -> Delivery:
        """Ask the API what the latest delivery holds.

        Returns:
            The delivery

        Raises:
            RuntimeError: Without an order and a login, or while the delivery
                is not ready
        """
        if not self.can_ask:
            raise RuntimeError(f"Topografi 50 needs {ORDER_VAR}, {USERNAME_VAR} and {PASSWORD_VAR} in the environment to ask the API")
        auth = _auth_header(self.username, self.password)
        base = f"{API_URL}/{urllib.parse.quote(self.order)}"
        delivery = delivery_from(self.fetch(f"{base}/leverans/latest", auth), self.fetch(f"{base}/leverans/latest/files", auth))
        if delivery.status != READY:
            raise RuntimeError(f"the latest Topografi 50 delivery is {delivery.status}, not {READY}")
        return delivery

    def _record(self, delivery: Delivery) -> Path:
        """Make the delivery's directory and write what it holds, unsigned."""
        directory = self.cache_dir / delivery.day
        directory.mkdir(parents=True, exist_ok=True)
        listed = [{**asdict(file), "path": file.path.split("?", 1)[0]} for file in delivery.files]
        (directory / DELIVERY_FILE).write_text(json.dumps({"id": delivery.id, "status": delivery.status, "files": listed}, indent=1))
        return directory

    def delivery(self, force_download: bool = False) -> Path:
        """The delivery a build reads: the newest on disk, or the API's.

        Args:
            force_download: Ask the API even when a delivery is on disk

        Returns:
            Its directory

        Raises:
            RuntimeError: With nothing on disk and no way to ask
        """
        held = self.on_disk()
        if held and not force_download:
            return held[-1]
        if not self.can_ask:
            raise RuntimeError(
                f"no Topografi 50 delivery under {self.cache_dir}, and no {ORDER_VAR}/{USERNAME_VAR}/{PASSWORD_VAR} in the environment to fetch one"
            )
        return self._record(self.ask())

    def geopackage(self, theme: str, force_download: bool = False) -> Path:
        """A theme's GeoPackage, fetched and unpacked if it is not there yet.

        Args:
            theme: One of :data:`THEMES`
            force_download: Ask the API for the newest delivery first

        Returns:
            The GeoPackage

        Raises:
            RuntimeError: If the archive has to be fetched and cannot be
        """
        directory = self.delivery(force_download)
        self.version = directory.name
        unpacked = directory / UNPACKED / geopackage_name(theme)
        if unpacked.exists():
            return unpacked
        archive = directory / zip_name(theme)
        if not archive.exists():
            if not self.can_ask:
                raise RuntimeError(f"{archive.name} is not in the delivery of {directory.name}, and there is no login to fetch it with")
            file = self.ask().file(archive.name)
            self.download(f"{API_URL}/{urllib.parse.quote(self.order)}{file.path}", _auth_header(self.username, self.password), archive)
            if archive.stat().st_size != file.length:
                archive.unlink()
                raise RuntimeError(f"{archive.name} came back {archive.stat().st_size} bytes long, the API said {file.length}")
        unpacked.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as opened:
            opened.extract(geopackage_name(theme), unpacked.parent)
        return unpacked

    def read(self, theme: str, layer: str, bounds: Bounds, force_download: bool = False) -> gpd.GeoDataFrame:
        """Read one layer over a box.

        Args:
            theme: One of :data:`THEMES`
            layer: A layer of that theme's GeoPackage
            bounds: The box, WGS 84
            force_download: Ask the API for the newest delivery first

        Returns:
            Every feature meeting the box, whole, in :data:`CRS`
        """
        path = self.geopackage(theme, force_download)
        box = project_bounds(bounds, "EPSG:4326", CRS)
        read: gpd.GeoDataFrame = pyogrio.read_dataframe(path, layer=layer, bbox=box)
        return read

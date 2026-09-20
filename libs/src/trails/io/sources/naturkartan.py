"""Naturkartan's pages for named routes, as links and nothing more.

Naturkartan is Outdoormap AB's platform, on which Länsstyrelsen Norrbotten
publishes each of its state trails -- *BD 21*, Abisko to Abiskojaure -- with
text and photos. Its terms allow downloading for private use only, the pages
offer no GPX, and the API answers 401 without the app's token
(``analysis/docs/abisko-decisions.md`` §5). Nothing of it enters the map.

What the map *can* carry is a link: a state trail's number from Naturvårdsverket
or a hiking relation's name from OSM tells a chain which page describes it.
The page slugs are not derivable from that identity, and a short URL by site id answers 404 (measured
2026-09-12), so an area's pages are researched once by hand and recorded in a
TOML catalogue::

    pages = load_catalogue("analysis/routes/abisko-naturkartan.toml")
    pages["BD 21"]  # -> "https://www.naturkartan.se/sv/norrbottens-lan/..."
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

#: Only these are accepted, so a catalogue cannot smuggle a ``javascript:``
#: link into a map popup.
URL_SCHEMES = ("http://", "https://")


@dataclass(frozen=True)
class SourceMetadata:
    """Where the links point, and why nothing else is taken from there."""

    name: str = "Naturkartan"
    provider: str = "Outdoormap AB, pages by the route publishers"
    country: str = "SE"
    url: str = "https://www.naturkartan.se"
    #: Private use only; the map links to the pages and copies nothing.
    license: str = "links only"
    attribution: str = "Naturkartan"


METADATA = SourceMetadata()


def load_catalogue(path: str | Path) -> dict[str, str]:
    """Read a catalogue of route identities and their Naturkartan pages.

    Args:
        path: Path to the TOML catalogue, with one ``[[trail]]`` per route
            carrying ``id`` (a register number or relation name) and ``url``

    Returns:
        The page URL by route identity, in catalogue order

    Raises:
        ValueError: If an entry lacks an id or a URL, the URL is not http(s),
            or an identity appears twice
    """
    with open(path, "rb") as handle:
        document = tomllib.load(handle)

    pages: dict[str, str] = {}
    for entry in document.get("trail", []):
        identity = entry.get("id")
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError(f"trail entry has no id: {entry!r}")
        if identity in pages:
            raise ValueError(f"trail {identity} appears twice in {path}")
        url = entry.get("url")
        if not isinstance(url, str) or not url.startswith(URL_SCHEMES):
            raise ValueError(f"trail {identity}: url must be an http(s) URL, got {url!r}")
        pages[identity] = url
    return pages

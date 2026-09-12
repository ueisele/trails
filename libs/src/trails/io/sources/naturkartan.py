"""Naturkartan's pages for the county's state trails, as links and nothing more.

Naturkartan is Outdoormap AB's platform, on which Länsstyrelsen Norrbotten
publishes each of its state trails -- *BD 21*, Abisko to Abiskojaure -- with
text and photos. Its terms allow downloading for private use only, the pages
offer no GPX, and the API answers 401 without the app's token
(``analysis/docs/abisko-decisions.md`` §5). Nothing of it enters the map.

What the map *can* carry is a link: the line itself is the county's state trail,
which Naturvårdsverket's register draws under the same *BD* number, so a chain
of the register knows which Naturkartan page describes it. The page slugs are
not derivable from the number and a short URL by site id answers 404 (measured
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
    provider: str = "Outdoormap AB, pages by Länsstyrelsen Norrbotten"
    country: str = "SE"
    url: str = "https://www.naturkartan.se"
    #: Private use only; the map links to the pages and copies nothing.
    license: str = "links only"
    attribution: str = "Naturkartan"


METADATA = SourceMetadata()


def load_catalogue(path: str | Path) -> dict[str, str]:
    """Read a catalogue of state trails and their Naturkartan pages.

    Args:
        path: Path to the TOML catalogue, with one ``[[trail]]`` per state
            trail carrying ``id`` (the register's number, as ``BD 21``) and
            ``url``

    Returns:
        The page URL by state trail number, in catalogue order

    Raises:
        ValueError: If an entry lacks an id or a URL, the URL is not http(s),
            or a number appears twice
    """
    with open(path, "rb") as handle:
        document = tomllib.load(handle)

    pages: dict[str, str] = {}
    for entry in document.get("trail", []):
        number = entry.get("id")
        if not isinstance(number, str) or not number.strip():
            raise ValueError(f"trail entry has no id: {entry!r}")
        if number in pages:
            raise ValueError(f"trail {number} appears twice in {path}")
        url = entry.get("url")
        if not isinstance(url, str) or not url.startswith(URL_SCHEMES):
            raise ValueError(f"trail {number}: url must be an http(s) URL, got {url!r}")
        pages[number] = url
    return pages

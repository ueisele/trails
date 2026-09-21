"""Interactive Folium maps for trail data.

Builds layered maps that combine trail geometries, area boundaries and points of
interest. Every layer is toggleable so several data sources can be compared
visually::

    fmap = create_map(bounds=park.total_bounds, base=BaseMap.KARTVERKET_TOPO)
    add_boundary(fmap, park, name="National park")
    add_trails(fmap, trails, name="Turrutebasen", color="#1b5e20")
    save_map(fmap, pathlib.Path("map.html"))
"""

import dataclasses
import hashlib
import json
import pathlib
import re
from dataclasses import dataclass
from enum import Enum
from html import escape
from importlib.resources import files
from typing import Any

import folium
import geopandas as gpd
import pandas as pd
from branca.element import Element, Figure, MacroElement
from jinja2 import Template

from trails.io.sources import mire
from trails.processing import mire_tiles, slope_tiles, trees, vegetation_tiles
from trails.processing.dem_tiles import TERRARIUM_OFFSET, TERRARIUM_STEP
from trails.routing import elevation

#: Bounding box as (min_lon, min_lat, max_lon, max_lat), matching GeoPandas.
Bounds = tuple[float, float, float, float]

#: Where :func:`create_map` records the ground it fitted the view to, for
#: anything later that needs to know what this map actually draws. The same
#: pattern as :data:`CHAIN_FIGURES_ATTR` on a feature group: a fact about the
#: object, carried on the object, rather than a second argument every caller
#: would have to repeat.
MAP_BOUNDS_ATTR = "_trails_bounds"

#: Where :func:`create_map` records the names this map's companion files,
#: database and caches go by (:class:`Companions`), for the panels added later.
MAP_COMPANIONS_ATTR = "_trails_companions"

#: Where :func:`create_map` records whose tiles the primary base layer draws
#: (:class:`Provider`), for the offline panel and the chrome added later.
MAP_PROVIDER_ATTR = "_trails_provider"

#: Where :func:`create_map` records the hillshade overlay it added, where the
#: provider has one -- so the legend can give it a row and its checkbox, which
#: is the only way a reader turns it off.
MAP_SHADE_ATTR = "_trails_shade"

#: Where :func:`create_map` records the slope-class overlay it added, where the
#: provider has one -- for the legend's checkbox under the relief's, and the
#: class rows it explains the colours with.
MAP_SLOPE_ATTR = "_trails_slope"

#: And the vegetation and forest overlays' (§6.11), for the same reason.
MAP_VEGETATION_ATTR = "_trails_vegetation"
MAP_FOREST_ATTR = "_trails_forest"

#: And the mire overlay's (§6.13), and where that layer carries the legend
#: rows of the classes its tree draws, since the legend meets the layer and
#: not the provider.
MAP_MIRE_ATTR = "_trails_mire"
MAP_MIRE_CLASSES_ATTR = "_trails_mire_classes"


@dataclasses.dataclass(frozen=True)
class Companions:
    """The names one map's files, database and caches go by.

    **Two maps on one origin must not share any of these.** The service worker,
    the manifest and the icons are objects beside the page; the database and the
    caches are per origin, so a second map with the same names would install
    over the first's worker, open the first's database and sweep the first's
    kept ground as cast-offs. Named per map, each is its own app.

    :data:`ROOT` is the first map's set -- ``sw.js``, ``manifest.webmanifest``,
    ``icon-*.png``, the database ``trails`` -- and is never renamed: installed
    copies hold those names, and a worker whose address starts answering 404 is
    a registration the browser may drop. Every later map takes :meth:`named`.
    """

    worker: str = "sw.js"
    manifest: str = "manifest.webmanifest"
    #: With ``{side}`` for the pixel size.
    icon: str = "icon-{side}.png"
    #: Which drawing in :data:`ICON_DIR` the icons are copies of. **A map of
    #: its own wears a mark of its own**: two maps with one icon are two tiles
    #: on a Home Screen nobody can tell apart.
    mark: str = "atlas"
    #: The IndexedDB database the worker and the page share.
    database: str = "trails"
    #: What the cache names and the offline switch's storage key start with.
    cache: str = "trails"
    #: The worker's and the manifest's scope, relative to the page.
    scope: str = "./"

    @classmethod
    def named(cls, stem: str) -> Companions:
        """The set for a map whose page is ``<stem>.html``, served at ``/<stem>``.

        Args:
            stem: The map's name, as in its object key.

        Returns:
            Names that carry the stem: ``<stem>-sw.js``, ``<stem>.webmanifest``,
            ``<stem>-icon-*.png`` copied from the drawing ``atlas-<stem>``, the
            database and caches ``trails-<stem>``, and the scope ``./<stem>`` --
            which the browser matches as a prefix, so it covers the page and
            nothing beside it.
        """
        return cls(
            worker=f"{stem}-sw.js",
            manifest=f"{stem}.webmanifest",
            icon=f"{stem}-icon-{{side}}.png",
            mark=f"atlas-{stem}",
            database=f"trails-{stem}",
            cache=f"trails-{stem}",
            scope=f"./{stem}",
        )

    @classmethod
    def of(cls, stem: str) -> Companions:
        """The set a map goes by, decided by its stem alone.

        The one rule, kept here so the build and the deploy cannot disagree:
        :data:`FIRST_MAP` keeps :data:`ROOT`, every other map is :meth:`named`.

        Args:
            stem: The map's name, as in its object key.

        Returns:
            The set.
        """
        return ROOT if stem == FIRST_MAP else cls.named(stem)

    def icon_named(self, side: int) -> str:
        """The icon file for one size."""
        return self.icon.format(side=side)

    def files(self) -> tuple[str, ...]:
        """Every object beside the page: the worker, the manifest, the icons."""
        return (self.worker, self.manifest, *(self.icon_named(side) for side in ICON_SIZES))


#: The first map's names. See :class:`Companions`.
ROOT = Companions()

#: The map whose companions are :data:`ROOT`. Installed copies of it hold those
#: names, which is why it is the stem and not a flag that decides.
FIRST_MAP = "lomsdal-visten"


@dataclasses.dataclass(frozen=True)
class HeightTiles:
    """Height tiles beside a provider's map tiles: where they are, how deep they go, what they weigh.

    Terrarium-packed PNGs cut by :mod:`trails.processing.dem_tiles`
    (analysis/docs/abisko-decisions.md §6.3), addressed like the map tiles and
    kept like them. The page reads them for the legs of a planned route the
    network cannot carry, and for a tap anywhere on the map; the
    worker keeps them beside the map tiles, under the same switch, so a leg
    planned offline over kept ground has a profile.
    """

    #: What every height tile's address starts with, root-relative.
    tiles: str
    #: The finest zoom cut, which is the one the page reads: a tile there is
    #: the model at the tile's own resolution, and the coarser levels are the
    #: same numbers averaged.
    top: int
    #: Mean bytes per tile, retained beside the pack estimate weights.
    weight: dict[int, int]
    #: Mean bytes per pack at each parent level, measured from the pack index.
    pack_weight: dict[int, int] = dataclasses.field(default_factory=dict)

    @property
    def template(self) -> str:
        """The address of a tile, with ``{z}``, ``{x}`` and ``{y}`` to fill."""
        return f"{self.tiles}{{z}}/{{x}}/{{y}}.png"

    def as_settings(self) -> dict[str, object]:
        """What the page is handed: where the tiles are, which zoom to read, and how a pixel unpacks.

        Returns:
            ``url``, ``zoom``, ``offset`` and ``step`` -- the last two the
            Terrarium packing, so the page and :func:`dem_tiles.unpack` read
            one formula -- and ``weight`` per zoom for the offline panel.
        """
        return {
            "url": self.template,
            "zoom": self.top,
            "offset": TERRARIUM_OFFSET,
            "step": TERRARIUM_STEP,
            "weight": {str(zoom): bytes_ for zoom, bytes_ in self.weight.items()},
            "pack_weight": {str(level): size for level, size in self.pack_weight.items()},
        }


@dataclasses.dataclass(frozen=True)
class ShadeTiles:
    """Hillshade tiles beside a provider's map tiles: where they are, how deep they go, what they weigh.

    Black-with-alpha PNGs cut by :mod:`trails.processing.shade_tiles`
    (analysis/docs/abisko-decisions.md §6.6), addressed like the map tiles and
    kept like them. The page draws them as an overlay over the base map and
    under everything it draws itself, so the contours keep their colour and the
    ground beneath them reads as terrain.

    **A layer the reader can switch off, and on by default.** It is a drawing
    decision rather than data, and the one case it gets in the way -- a screen
    read in full sun, where every extra bit of dark costs -- is the reader's to
    judge, not the build's.
    """

    #: What every hillshade tile's address starts with, root-relative.
    tiles: str
    #: The finest zoom cut. Past it Leaflet draws the same tile magnified,
    #: which is what the ceiling is chosen to be invisible at.
    top: int
    #: Mean bytes per tile, retained beside the pack estimate weights.
    weight: dict[int, int]
    #: Mean bytes per pack at each parent level, measured from the pack index.
    pack_weight: dict[int, int] = dataclasses.field(default_factory=dict)
    #: How dark the shadow is drawn, 0 to 1. The tiles carry the full range, so
    #: this is the one number that tunes the look and it costs no rebuild.
    #:
    #: **0.55 was measured, not chosen.** Legibility of the contours is not what
    #: bounds it: the shadow multiplies line and ground alike, so their contrast
    #: holds at 1.49:1 at 35 % and 1.42:1 at 80 %. What bounds it is absolute
    #: darkness -- at 70 % a steep flank goes near-black and the water and
    #: forest colours go with it. At 55 % shaded ground is 68 % darker than
    #: unshaded, which is the paper map's plasticity without its ink.
    opacity: float = 0.55

    @property
    def template(self) -> str:
        """The address of a tile, with ``{z}``, ``{x}`` and ``{y}`` to fill."""
        return f"{self.tiles}{{z}}/{{x}}/{{y}}.png"

    def as_settings(self) -> dict[str, object]:
        """What the page is handed: where the tiles are, how deep they go, what they weigh.

        Returns:
            ``url``, ``top`` and ``weight`` per zoom, for the offline panel.
        """
        return {
            "url": self.template,
            "top": self.top,
            "weight": {str(zoom): bytes_ for zoom, bytes_ in self.weight.items()},
            "pack_weight": {str(level): size for level, size in self.pack_weight.items()},
        }


@dataclasses.dataclass(frozen=True)
class SlopeTiles:
    """Slope-class tiles beside a provider's map tiles: where they are, how deep they go, what they weigh.

    Palette PNGs cut by :mod:`trails.processing.slope_tiles`
    (analysis/docs/abisko-decisions.md §6.7): how steep the ground is, in the
    SLF's avalanche classes with one of ours at 25° below them and one over
    55° above, one colour each with the alpha in the palette. Drawn over the
    relief shadow and under everything the page draws itself, and **drawn
    multiplied** -- ``mix-blend-mode: multiply`` on the layer -- so the
    sheet's lettering and lines stay their own black under every class, as ink
    overprinted on a printed map does. Drawn opaquely the names fell to 3:1
    against their ground; multiplied, none falls below 10:1 (§6.7).

    **A layer the reader switches on, and off by default.** It answers a
    question the paths do not ask -- how steep is it *here*, off them -- and
    an eighth of the ground coloured is a lot of colour for a reader who is
    following a marked trail. The profile grades the *path*, in per cent along
    it; this grades the ground, in degrees down the fall line, and the two
    are not the same measure even where they share a colour.
    """

    #: What every slope tile's address starts with, root-relative.
    tiles: str
    #: The finest zoom cut: the relief's, since the classes are read off the
    #: same smoothed heights and the model has no more to give past it.
    top: int
    #: Mean bytes per tile, retained beside the pack estimate weights.
    weight: dict[int, int]
    #: Mean bytes per pack at each parent level, measured from the pack index.
    pack_weight: dict[int, int] = dataclasses.field(default_factory=dict)

    @property
    def template(self) -> str:
        """The address of a tile, with ``{z}``, ``{x}`` and ``{y}`` to fill."""
        return f"{self.tiles}{{z}}/{{x}}/{{y}}.png"

    def as_settings(self) -> dict[str, object]:
        """What the page is handed: where the tiles are, how deep they go, what they weigh.

        Returns:
            ``url``, ``top`` and ``weight`` per zoom, for the offline panel.
        """
        return {
            "url": self.template,
            "top": self.top,
            "weight": {str(zoom): bytes_ for zoom, bytes_ in self.weight.items()},
            "pack_weight": {str(level): size for level, size in self.pack_weight.items()},
        }

    @staticmethod
    def classes() -> list[dict[str, object]]:
        """The legend's rows: each class's lower bound, colour and who set the bound.

        Returns:
            One row per class, lowest first, ``from``, ``to`` (``None`` for the
            last), ``colour`` and ``source``
        """
        edges = slope_tiles.EDGES
        return [
            {
                "from": edges[at],
                "to": edges[at + 1] if at + 1 < len(edges) else None,
                "colour": slope_tiles.COLOURS[at],
                "source": slope_tiles.SOURCES[at],
            }
            for at in range(len(edges))
        ]


@dataclasses.dataclass(frozen=True)
class VegetationTiles:
    """Vegetation tiles beside a provider's map tiles: how much stands between knee and head height.

    Palette PNGs cut by :mod:`trails.processing.vegetation_tiles`
    (analysis/docs/abisko-decisions.md §6.11): the laser's reading of what
    stands between 0.5 and 5 m -- dwarf birch, willow, young mountain birch
    -- as the share of each 10 m cell it covers, in six steps of one teal,
    and the ground the laser has not flown in a light grey, drawn multiplied
    over the sheet like the slope classes and off until the reader asks. It
    answers the question the sheet does not: whether the open ground off the
    path is walked across or pushed through -- and, since the grey, whether
    a blank means nothing there or nobody looked.
    """

    #: What every vegetation tile's address starts with, root-relative.
    tiles: str
    #: The finest zoom cut: the relief's, since a 10 m cell has no more to give past it.
    top: int
    #: Mean bytes per tile, retained beside the pack estimate weights.
    weight: dict[int, int]
    #: Mean bytes per pack at each parent level, measured from the pack index.
    pack_weight: dict[int, int] = dataclasses.field(default_factory=dict)

    @property
    def template(self) -> str:
        """The address of a tile, with ``{z}``, ``{x}`` and ``{y}`` to fill."""
        return f"{self.tiles}{{z}}/{{x}}/{{y}}.png"

    def as_settings(self) -> dict[str, object]:
        """What the page is handed: where the tiles are, how deep they go, what they weigh.

        Returns:
            ``url``, ``top`` and ``weight`` per zoom, for the offline panel.
        """
        return {
            "url": self.template,
            "top": self.top,
            "weight": {str(zoom): bytes_ for zoom, bytes_ in self.weight.items()},
            "pack_weight": {str(level): size for level, size in self.pack_weight.items()},
        }

    @staticmethod
    def classes() -> list[dict[str, object]]:
        """The legend's rows: each class's span of the cell in per cent and its colour, then the unsurveyed grey.

        Returns:
            One row per class, sparsest first, ``label`` and ``colour``; the
            density rows carry ``from`` and ``to`` as well
        """
        rows: list[dict[str, object]] = [
            {"from": span[0], "to": span[1], "colour": colour, "label": f"{span[0]}–{span[1]} % of the ground"}
            for span, colour in zip(vegetation_tiles.DENSITY_SPANS, vegetation_tiles.COLOURS, strict=True)
        ]
        rows.append({"colour": vegetation_tiles.UNSURVEYED_COLOUR, "label": "not surveyed by the laser"})
        return rows


@dataclasses.dataclass(frozen=True)
class ForestTiles:
    """Forest tiles beside a provider's map tiles: where trees over 5 m stand on a third of the ground or more.

    The other tree :mod:`trails.processing.vegetation_tiles` cuts (§6.11), one
    class in a sepia, switched on its own: high forest is a different thing
    from willow, usually easy ground, and the sheet draws its own idea of it,
    so this is the laser's word on where the sheet is right.
    """

    #: What every forest tile's address starts with, root-relative.
    tiles: str
    #: The finest zoom cut.
    top: int
    #: Mean bytes per tile, retained beside the pack estimate weights.
    weight: dict[int, int]
    #: Mean bytes per pack at each parent level, measured from the pack index.
    pack_weight: dict[int, int] = dataclasses.field(default_factory=dict)

    @property
    def template(self) -> str:
        """The address of a tile, with ``{z}``, ``{x}`` and ``{y}`` to fill."""
        return f"{self.tiles}{{z}}/{{x}}/{{y}}.png"

    def as_settings(self) -> dict[str, object]:
        """What the page is handed: where the tiles are, how deep they go, what they weigh.

        Returns:
            ``url``, ``top`` and ``weight`` per zoom, for the offline panel.
        """
        return {
            "url": self.template,
            "top": self.top,
            "weight": {str(zoom): bytes_ for zoom, bytes_ in self.weight.items()},
            "pack_weight": {str(level): size for level, size in self.pack_weight.items()},
        }

    @staticmethod
    def colour() -> str:
        """The one colour the forest is drawn in.

        Returns:
            ``#rrggbb``
        """
        return vegetation_tiles.FOREST_COLOUR


@dataclasses.dataclass(frozen=True)
class MireTiles:
    """Mire tiles beside a provider's map tiles: where the ground is bog and marsh, and whether it carries a boot.

    Palette PNGs cut by :mod:`trails.processing.mire_tiles`
    (analysis/docs/abisko-decisions.md §6.13): the sheet's mires, the ones
    its survey calls wet apart, and over Sweden the wet and moist ground the
    soil-moisture model finds beyond them, one violet in two steps and two
    hatches, drawn multiplied over the sheet like the vegetation and off
    until the reader asks. A class is the same statement in the same colour
    and hatch on every map, and a map's legend lists the classes its tree
    carries: all four over Sweden, the mire alone over Norway, whose sheet
    draws one kind of bog and has no model behind it.
    """

    #: What every mire tile's address starts with, root-relative.
    tiles: str
    #: The finest zoom cut: the relief's, since a 10 m cell has no more to give past it.
    top: int
    #: Mean bytes per tile, retained beside the pack estimate weights.
    weight: dict[int, int]
    #: Mean bytes per pack at each parent level, measured from the pack index.
    pack_weight: dict[int, int] = dataclasses.field(default_factory=dict)
    #: Which classes the tree carries, in class order: all four over Sweden,
    #: the mire alone over Norway. The legend lists these and no other.
    drawn: tuple[int, ...] = mire.CLASSES

    @property
    def template(self) -> str:
        """The address of a tile, with ``{z}``, ``{x}`` and ``{y}`` to fill."""
        return f"{self.tiles}{{z}}/{{x}}/{{y}}.png"

    def as_settings(self) -> dict[str, object]:
        """What the page is handed: where the tiles are, how deep they go, what they weigh.

        Returns:
            ``url``, ``top`` and ``weight`` per zoom, for the offline panel.
        """
        return {
            "url": self.template,
            "top": self.top,
            "weight": {str(zoom): bytes_ for zoom, bytes_ in self.weight.items()},
            "pack_weight": {str(level): size for level, size in self.pack_weight.items()},
        }

    def classes(self) -> list[dict[str, object]]:
        """The legend's rows: each drawn class's colour, its hatch if any, and what it is, wettest first.

        Returns:
            One row per class the tree carries: ``label``, ``colour`` and
            ``hatch`` as ``[line, gap]`` in pixels or None for a solid fill
        """
        return [
            {
                "colour": mire_tiles.COLOURS[index - 1],
                "hatch": list(mire_tiles.HATCHED[index]) if index in mire_tiles.HATCHED else None,
                "label": mire_tiles.LABELS[index - 1],
            }
            for index in mire.CLASSES
            if index in self.drawn
        ]


@dataclasses.dataclass(frozen=True)
class Provider:
    """Whose tiles a map draws, and the three things the page needs to know about them.

    Everything on the offline panel that is about the source rather than the
    reader -- which addresses are tiles, how deep the pyramid goes, what a tile
    weighs -- comes from here, one entry per provider, injected into the page
    and the worker rather than written into their JavaScript.
    """

    key: str
    #: How the picker's hint names the sheets: "Which Kartverket sheet ...".
    label: str
    #: What every tile address starts with. Absolute for a third party's
    #: server; root-relative for our own bucket, so the page carries no host
    #: and the same page works served locally over the same tree.
    tiles: str
    #: The finest tile zoom in the provider's tree.
    top: int
    #: The whole map is offered to z17 on both providers. Packs reduce the
    #: larger box to 9,162 rows, below the phone's phase-1b measured pack load;
    #: the old per-tile row limit no longer requires a z16 cap.
    cap: int
    #: Mean bytes per tile, retained beside the pack estimate weights.
    weight: dict[int, int]
    #: Mean bytes per pack at each parent level, measured from the pack index.
    pack_weight: dict[int, int] = dataclasses.field(default_factory=dict)
    #: Height tiles cut beside the map tiles, where the map has them. None for
    #: a map that asks a point service for its heights instead -- which since
    #: §6.10 is neither of them.
    heights: HeightTiles | None = None
    #: Hillshade tiles cut beside the map tiles, where the map has them. None
    #: for a sheet with no height model behind it, and then the page draws no
    #: relief overlay at all.
    shade: ShadeTiles | None = None
    #: Slope-class tiles cut beside the map tiles, where the map has them
    #: (§6.7): the same condition as the relief's, and None with it.
    slope: SlopeTiles | None = None
    #: Vegetation and forest tiles cut beside the map tiles, where the map's
    #: country has a laser survey to cut them from (§6.11); None where not.
    vegetation: VegetationTiles | None = None
    forest: ForestTiles | None = None
    #: Mire tiles cut beside the map tiles, where the map's country draws its
    #: mires (§6.13); None where not.
    mire: MireTiles | None = None
    #: The finite tree box, west, south, east, north in degrees.
    extent: tuple[float, float, float, float] = dataclasses.field(kw_only=True)


#: What a tile of each of Lomsdal-Visten's three trees weighs, per zoom, for
#: every size estimate on the offline panel: the mean over the whole tree of
#: the first build, 2026-09-17 (§6.10). Measured rather than sampled, because
#: unlike a provider's cache these are ours and every one of them is on disk.
#: Kartverket's national model as tiles, z8 to z13: 2,475 tiles, 224.0 MB.
_WEIGHT_LV_DEM = {8: 48907, 9: 88226, 10: 93729, 11: 101108, 12: 95688, 13: 88436}
#: The relief shadow, z8 to z15: 37,915 tiles, 477.1 MB.
_WEIGHT_LV_SHADE = {8: 13071, 9: 22789, 10: 24516, 11: 26800, 12: 26208, 13: 22598, 14: 16377, 15: 10672}
#: The slope classes, z8 to z15: 37,915 tiles, 141.8 MB.
_WEIGHT_LV_SLOPE = {8: 2453, 9: 4296, 10: 5038, 11: 5849, 12: 6186, 13: 5764, 14: 4604, 15: 3339}
#: The vegetation and forest trees (§6.11), z8 to z15, 37,915 tiles each:
#: 128.3 MB and 24.1 MB, the mean per zoom of the second vegetation build
#: (the grey class, unused over Norway, is four bytes a tile) and the first
#: forest build, 2026-09-18.
_WEIGHT_LV_VEGETATION = {8: 3595, 9: 6885, 10: 8200, 11: 10905, 12: 14148, 13: 11072, 14: 5124, 15: 2231}
_WEIGHT_LV_FOREST = {8: 1037, 9: 1770, 10: 1803, 11: 1962, 12: 2153, 13: 1683, 14: 914, 15: 467}
#: The same two over the Abisko box, 9,330 tiles each: 19.8 MB with the
#: ground past the border drawn grey and 2.6 MB, the mean per zoom of the
#: second vegetation build and the first forest build, 2026-09-18.
_WEIGHT_AB_VEGETATION = {8: 1173, 9: 1605, 10: 3284, 11: 5653, 12: 7559, 13: 6096, 14: 3045, 15: 1525}
_WEIGHT_AB_FOREST = {8: 262, 9: 312, 10: 486, 11: 625, 12: 718, 13: 581, 14: 358, 15: 232}
#: The mire trees (§6.13), z8 to z15, the mean per zoom of the third build,
#: 2026-09-19: Lomsdal-Visten's 37,915 tiles off N50's bogs, 11.4 MB, and
#: Abisko's 9,330 off Lantmäteriet's wetlands and SLU's wet and moist ground
#: hatched from z13, 8.5 MB (4.0 unhatched and without the moist ground; a
#: hatch is what a PNG's filters pack worst).
_WEIGHT_LV_MIRE = {8: 408, 9: 897, 10: 1186, 11: 1295, 12: 1004, 13: 651, 14: 366, 15: 243}
_WEIGHT_AB_MIRE = {8: 360, 9: 544, 10: 1127, 11: 1742, 12: 1703, 13: 1566, 14: 1172, 15: 793}

#: Malingsbo-Kloten's version 1 trees, measured 2026-09-20 in the main
#: checkout's analysis/output/: every PNG's size checked against index.json,
#: then per_zoom bytes / tiles rounded to whole bytes, as for Abisko.
#: The pack_weight tables below use packs.weights_from_index: per_level
#: bytes / packs, rounded, also checked against every PMTiles file on disk.
_WEIGHT_MK_SHEET = {8: 37065, 9: 33160, 10: 22169, 11: 27258, 12: 21040, 13: 21829, 14: 18300, 15: 11295, 16: 6466, 17: 3671}
_WEIGHT_MK_DEM = {8: 33548, 9: 62254, 10: 76892, 11: 93195, 12: 92259, 13: 88029}
_WEIGHT_MK_SHADE = {8: 6628, 9: 11282, 10: 14593, 11: 18482, 12: 19926, 13: 20248, 14: 14086, 15: 9469}
_WEIGHT_MK_SLOPE = {8: 1189, 9: 1194, 10: 1238, 11: 1265, 12: 1309, 13: 1390, 14: 1332, 15: 1282}
_WEIGHT_MK_VEGETATION = {8: 862, 9: 2764, 10: 5126, 11: 8283, 12: 13430, 13: 12290, 14: 5925, 15: 2312}
_WEIGHT_MK_FOREST = {8: 2150, 9: 3509, 10: 3947, 11: 4403, 12: 4779, 13: 4049, 14: 2104, 15: 910}
_WEIGHT_MK_MIRE = {8: 820, 9: 1826, 10: 2544, 11: 2795, 12: 2075, 13: 3603, 14: 2707, 15: 1876}


#: Where each map's own trees are cut, written once and read here so the page,
#: its worker, the offline panel and the three build scripts all name one box.
_LOMSDAL_VISTEN = trees.TREES["lomsdal-visten"]
_ABISKO = trees.TREES["abisko"]
_MALINGSBO_KLOTEN = trees.TREES["malingsbo-kloten"]


PROVIDERS: dict[str, Provider] = {
    "kartverket": Provider(
        key="kartverket",
        label="Kartverket",
        tiles="/tiles/kartverket/topo/1/",
        top=17,
        cap=17,
        # Mean PNG bytes per zoom of the finished flat WMS tree, phase 5.
        weight={8: 11417, 9: 15036, 10: 18338, 11: 19503, 12: 14311, 13: 12905, 14: 13584, 15: 8107, 16: 11135, 17: 6567},
        pack_weight={6: 249162, 10: 797726, 14: 637947},
        extent=_LOMSDAL_VISTEN.box,
        # Kartverket's national height model as tiles (§6.10), z8 to z13; the
        # weights are the mean per zoom of the first build's 2,475 tiles,
        # 2026-09-17.
        heights=HeightTiles(
            tiles=_LOMSDAL_VISTEN.prefix("dem"),
            top=_LOMSDAL_VISTEN.dem_max_zoom,
            weight=_WEIGHT_LV_DEM,
            pack_weight={6: 1352412, 10: 5302544},
        ),
        # The relief shadow the page draws under the contours (§6.6, §6.10),
        # z8 to z15, off the same mosaic.
        shade=ShadeTiles(
            tiles=_LOMSDAL_VISTEN.prefix("shade"),
            top=_LOMSDAL_VISTEN.ground_max_zoom,
            weight=_WEIGHT_LV_SHADE,
            pack_weight={8: 820241, 12: 978170},
        ),
        # And the slope classes over it (§6.7, §6.10), cut exactly as the
        # relief is. Version 1: this tree has no earlier stand to be told from.
        slope=SlopeTiles(
            tiles=_LOMSDAL_VISTEN.prefix("slope"),
            top=_LOMSDAL_VISTEN.ground_max_zoom,
            weight=_WEIGHT_LV_SLOPE,
            pack_weight={8: 175384, 12: 291936},
        ),
        # And what stands on the ground, off Kartverket's surface model less
        # its terrain model (§6.11), z8 to z15, cut as the slope classes are.
        vegetation=VegetationTiles(
            tiles=_LOMSDAL_VISTEN.prefix("vegetation"),
            top=_LOMSDAL_VISTEN.ground_max_zoom,
            weight=_WEIGHT_LV_VEGETATION,
            pack_weight={8: 315133, 12: 262436},
        ),
        forest=ForestTiles(
            tiles=_LOMSDAL_VISTEN.prefix("forest"),
            top=_LOMSDAL_VISTEN.ground_max_zoom,
            weight=_WEIGHT_LV_FOREST,
            pack_weight={8: 60763, 12: 49852},
        ),
        # And where the ground is bog, off N50's outlines (§6.13): the sheet
        # draws one kind of bog, so one class is drawn and one row shown.
        mire=MireTiles(
            tiles=_LOMSDAL_VISTEN.prefix("mire"),
            top=_LOMSDAL_VISTEN.ground_max_zoom,
            weight=_WEIGHT_LV_MIRE,
            pack_weight={8: 39477, 12: 23765},
            drawn=(mire.FIRM_MIRE,),
        ),
    ),
    "lantmateriet": Provider(
        key="lantmateriet",
        label="Lantmäteriet",
        tiles="/tiles/lantmateriet/topowebb/1/",
        top=17,
        # The whole box at z17 is the whole copy, 700 MB: asked for by Uwe.
        cap=17,
        # The mean over every tile of the Abisko box, read off the copy of
        # 2026-09-12 (analysis/docs/abisko-decisions.md §3): indexed PNG, and
        # a box that is mountain and lake rather than sea, so the whole-box
        # mean is close to what a route crosses.
        # z8–z10: the same per_zoom bytes / tiles from index.json, read
        # 2026-09-18 and rounded to whole bytes.
        weight={8: 16066, 9: 14279, 10: 12273, 11: 31747, 12: 22166, 13: 25719, 14: 15290, 15: 13783, 16: 7958, 17: 4587},
        pack_weight={6: 117982, 10: 1249660, 14: 483317},
        # The box the tree was cut to, as `index.json` beside it records
        # (§2 of the decisions): the copy holds every tile of the box at
        # every zoom and not one outside it.
        extent=_ABISKO.box,
        # The 1 m height model as tiles (§6.3), z8 to z13; the weights are
        # the mean per zoom of the first build's 540 tiles, 2026-09-12.
        heights=HeightTiles(
            tiles=_ABISKO.prefix("dem"),
            top=_ABISKO.dem_max_zoom,
            weight={8: 29019, 9: 35677, 10: 65806, 11: 93498, 12: 93117, 13: 92693},
            pack_weight={6: 272299, 10: 4621156},
        ),
        # The relief shadow the page draws under the contours (§6.6), z8 to
        # z15; the weights are the mean per zoom of the first build's 9,330
        # tiles, 104.0 MB, 2026-09-16. They fall with the zoom because a tile
        # holds less relief the closer in it is, and the whole tree weighs less
        # than the height tiles' 55 MB twice over.
        shade=ShadeTiles(
            tiles=_ABISKO.prefix("shade"),
            top=_ABISKO.ground_max_zoom,
            weight={8: 9528, 9: 10633, 10: 18582, 11: 26043, 12: 25044, 13: 20474, 14: 14404, 15: 9415},
            pack_weight={8: 543912, 12: 858106},
        ),
        # The slope classes the page colours over the relief (§6.7), z8 to
        # z15. Version 2 since the seven classes and the light palette drawn
        # multiplied, 2026-09-17; the weights are the mean per zoom of that
        # build's 9,330 tiles. Flat colour in a palette: a quarter of the
        # relief's 104 MB.
        slope=SlopeTiles(
            tiles=_ABISKO.prefix("slope"),
            top=_ABISKO.ground_max_zoom,
            weight={8: 2328, 9: 2547, 10: 3646, 11: 4586, 12: 4470, 13: 4010, 14: 3213, 15: 2424},
            pack_weight={8: 100986, 12: 207487},
        ),
        # And what stands on the ground, off NMD 2018's laser classes (§6.11),
        # z8 to z15, cut as the slope classes are.
        vegetation=VegetationTiles(
            tiles=_ABISKO.prefix("vegetation"),
            top=_ABISKO.ground_max_zoom,
            weight=_WEIGHT_AB_VEGETATION,
            pack_weight={8: 110916, 12: 163661},
        ),
        forest=ForestTiles(
            tiles=_ABISKO.prefix("forest"),
            top=_ABISKO.ground_max_zoom,
            weight=_WEIGHT_AB_FOREST,
            pack_weight={8: 13850, 12: 22138},
        ),
        # And where the ground is mire, wet or firm off Lantmäteriet's
        # wetlands and wet ground beyond them off SLU's model (§6.13).
        mire=MireTiles(
            tiles=_ABISKO.prefix("mire"),
            top=_ABISKO.ground_max_zoom,
            weight=_WEIGHT_AB_MIRE,
            pack_weight={8: 35327, 12: 71315},
        ),
    ),
}


_ABISKO_PROVIDER = PROVIDERS["lantmateriet"]
assert _ABISKO_PROVIDER.heights is not None
assert _ABISKO_PROVIDER.shade is not None
assert _ABISKO_PROVIDER.slope is not None
assert _ABISKO_PROVIDER.vegetation is not None
assert _ABISKO_PROVIDER.forest is not None
assert _ABISKO_PROVIDER.mire is not None

PROVIDERS["lantmateriet-malingsbo-kloten"] = dataclasses.replace(
    PROVIDERS["lantmateriet"],
    key="lantmateriet-malingsbo-kloten",
    extent=_MALINGSBO_KLOTEN.box,
    tiles="/tiles/lantmateriet-malingsbo-kloten/topowebb/1/",
    weight=_WEIGHT_MK_SHEET,
    pack_weight={6: 206942, 10: 1256316, 14: 388767},
    heights=dataclasses.replace(
        _ABISKO_PROVIDER.heights, tiles=_MALINGSBO_KLOTEN.prefix("dem"), weight=_WEIGHT_MK_DEM, pack_weight={6: 316305, 10: 5083724}
    ),
    shade=dataclasses.replace(
        _ABISKO_PROVIDER.shade, tiles=_MALINGSBO_KLOTEN.prefix("shade"), weight=_WEIGHT_MK_SHADE, pack_weight={8: 449768, 12: 812973}
    ),
    slope=dataclasses.replace(
        _ABISKO_PROVIDER.slope, tiles=_MALINGSBO_KLOTEN.prefix("slope"), weight=_WEIGHT_MK_SLOPE, pack_weight={8: 34142, 12: 95986}
    ),
    vegetation=dataclasses.replace(
        _ABISKO_PROVIDER.vegetation, tiles=_MALINGSBO_KLOTEN.prefix("vegetation"), weight=_WEIGHT_MK_VEGETATION, pack_weight={8: 186682, 12: 270567}
    ),
    forest=dataclasses.replace(
        _ABISKO_PROVIDER.forest, tiles=_MALINGSBO_KLOTEN.prefix("forest"), weight=_WEIGHT_MK_FOREST, pack_weight={8: 112488, 12: 100157}
    ),
    mire=dataclasses.replace(
        _ABISKO_PROVIDER.mire, tiles=_MALINGSBO_KLOTEN.prefix("mire"), weight=_WEIGHT_MK_MIRE, pack_weight={8: 70510, 12: 157050}
    ),
)


#: The glyphs the markers ask for, as Font Awesome's own outlines.
#:
#: **252 kB of stylesheet and webfont bought exactly four of them.** Measured
#: on the built page, `house-chimney` is asked for 113 times, `campground` 36,
#: `ship` 32, `anchor` 17, and nothing else is asked for at all -- so the page
#: linked `all.min.css` and pulled `fa-solid-900.woff2` from a third host to
#: draw four shapes. These are the same outlines, so the markers are unchanged
#: to the pixel, and awesome-markers still writes the same `<i class="fa fa-">`.
#:
#: **Then thirteen more, at about a kilobyte of path each.** Reviewed on
#: 2026-09-17: one house stood for a staffed STF cabin, a reindeer herder's
#: kåta and a private koie alike, and the one thing a planner asks of a hut --
#: can I sleep there -- sat in the popup. So the glyph now says what a place is
#: for: `bed` where there is a bed (staffed or self-service), `house` for an
#: unstaffed hut, `person-shelter` for a gapahuk or a vindskydd, `tent` for a
#: camp site, `train`, `bus` and `plane` for the way in, `bridge` and `water` for a
#: footbridge and a ford, `phone`, `square-parking`, `restroom`, `fire` and
#: `circle-info` for what the registers place along a trail. The colour keeps
#: saying which source placed the pin.
#:
#: Font Awesome Free 6.2.0 by @fontawesome, https://fontawesome.com --
#: Icons: CC BY 4.0. Copyright 2022 Fonticons, Inc. The notice travels with the
#: outlines into every built page, as it does in the stylesheet this replaces.
MARKER_ICONS: dict[str, tuple[str, str]] = {
    # **A house with a crack through it, for a place people left.** The
    # register's *gammelBosettingsplass* -- a former settlement place -- and a
    # farm the national park boundary now encloses are drawn with it: what
    # the glyph asserts is that a homestead stood here and is not lived in,
    # which is the one fact a planner reads off it (§9.39).
    "house-chimney-crack": (
        "0 0 576 512",
        "M575.8 255.5c0 18-15 32.1-32 32.1h-32l.7 160.2c.2 35.5-28.5 64.3-64 64.3H326.4L288 448l80.8-67.3c7.8-6.5 7.6-18.6"
        "-.4-24.9L250.6 263.2c-14.6-11.5-33.8 7-22.8 22L288 368l-85.5 71.2c-6.1 5-7.5 13.8-3.5 20.5L230.4 512H128.1"
        "c-35.3 0-64-28.7-64-64V287.6H32c-18 0-32-14-32-32.1c0-9 3-17 10-24L266.4 8c7-7 15-8 22-8s15 2 21 7L416 100.7V64"
        "c0-17.7 14.3-32 32-32h32c17.7 0 32 14.3 32 32V185l52.8 46.4c8 7 12 15 11 24z",
    ),
    "house-chimney": (
        "0 0 576 512",
        "M543.8 287.6c17 0 32-14 32-32.1c1-9-3-17-11-24L512 185V64c0-17.7-14.3-32-32-32H448c-17.7 0-32 14.3-32 32"
        "v36.7L309.5 7c-6-5-14-7-21-7s-15 1-22 8L10 231.5c-7 7-10 15-10 24c0 18 14 32.1 32 32.1h32v69.7c-.1 .9-.1 1.8"
        "-.1 2.8V472c0 22.1 17.9 40 40 40h16c1.2 0 2.4-.1 3.6-.2c1.5 .1 3 .2 4.5 .2H160h24c22.1 0 40-17.9 40-40V448 384"
        "c0-17.7 14.3-32 32-32h64c17.7 0 32 14.3 32 32v64 24c0 22.1 17.9 40 40 40h24 32.5c1.4 0 2.8 0 4.2-.1c1.1 .1 2.2 .1 3.3 .1"
        "h16c22.1 0 40-17.9 40-40V455.8c.3-2.6 .5-5.3 .5-8.1l-.7-160.2h32z",
    ),
    "campground": (
        "0 0 576 512",
        "M377 52c11-13.8 8.8-33.9-5-45s-33.9-8.8-45 5L288 60.8 249 12c-11-13.8-31.2-16-45-5s-16 31.2-5 45l48 60L12.3 405.4"
        "C4.3 415.4 0 427.7 0 440.4V464c0 26.5 21.5 48 48 48H288 528c26.5 0 48-21.5 48-48V440.4c0-12.7-4.3-25.1"
        "-12.3-35L329 112l48-60zM288 448H168.5L288 291.7 407.5 448H288z",
    ),
    "ship": (
        "0 0 576 512",
        "M192 32c0-17.7 14.3-32 32-32H352c17.7 0 32 14.3 32 32V64h48c26.5 0 48 21.5 48 48V240l44.4 14.8c23.1 7.7 29.5 37.5 11.5 53.9"
        "l-101 92.6c-16.2 9.4-34.7 15.1-50.9 15.1c-19.6 0-40.8-7.7-59.2-20.3c-22.1-15.5-51.6-15.5-73.7 0c-17.1 11.8"
        "-38 20.3-59.2 20.3c-16.2 0-34.7-5.7-50.9-15.1l-101-92.6c-18-16.5-11.6-46.2 11.5-53.9L96 240V112c0-26.5 21.5"
        "-48 48-48h48V32zM160 218.7l107.8-35.9c13.1-4.4 27.3-4.4 40.5 0L416 218.7V128H160v90.7zM306.5 421.9C329 437.4 356.5 448 384 448"
        "c26.9 0 55.4-10.8 77.4-26.1l0 0c11.9-8.5 28.1-7.8 39.2 1.7c14.4 11.9 32.5 21 50.6 25.2c17.2 4 27.9 21.2 23.9 38.4"
        "s-21.2 27.9-38.4 23.9c-24.5-5.7-44.9-16.5-58.2-25C449.5 501.7 417 512 384 512c-31.9 0-60.6-9.9-80.4-18.9"
        "c-5.8-2.7-11.1-5.3-15.6-7.7c-4.5 2.4-9.7 5.1-15.6 7.7c-19.8 9-48.5 18.9-80.4 18.9c-33 0-65.5-10.3-94.5"
        "-25.8c-13.4 8.4-33.7 19.3-58.2 25c-17.2 4-34.4-6.7-38.4-23.9s6.7-34.4 23.9-38.4c18.1-4.2 36.2-13.3 50.6"
        "-25.2c11.1-9.4 27.3-10.1 39.2-1.7l0 0C136.7 437.2 165.1 448 192 448c27.5 0 55-10.6 77.5-26.1c11.1-7.9 25.9"
        "-7.9 37 0z",
    ),
    "anchor": (
        "0 0 576 512",
        "M256 96c0-17.7 14.3-32 32-32s32 14.3 32 32s-14.3 32-32 32s-32-14.3-32-32zm85.1 80C367 158.8 384 129.4 384 96"
        "c0-53-43-96-96-96s-96 43-96 96c0 33.4 17 62.8 42.9 80H224c-17.7 0-32 14.3-32 32s14.3 32 32 32h32V448H208"
        "c-53 0-96-43-96-96v-6.1l7 7c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9L97 263c-9.4-9.4-24.6-9.4-33.9 0L7 319"
        "c-9.4 9.4-9.4 24.6 0 33.9s24.6 9.4 33.9 0l7-7V352c0 88.4 71.6 160 160 160h80 80c88.4 0 160-71.6 160-160v"
        "-6.1l7 7c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-56-56c-9.4-9.4-24.6-9.4-33.9 0l-56 56c-9.4 9.4-9.4 24.6 0 33.9"
        "s24.6 9.4 33.9 0l7-7V352c0 53-43 96-96 96H320V240h32c17.7 0 32-14.3 32-32s-14.3-32-32-32H341.1z",
    ),
    "bed": (
        "0 0 640 512",
        "M32 32c17.7 0 32 14.3 32 32V320H288V160c0-17.7 14.3-32 32-32H544c53 0 96 43 96 96V448c0 17.7-14.3 32-32 "
        "32s-32-14.3-32-32V416H352 320 64v32c0 17.7-14.3 32-32 32s-32-14.3-32-32V64C0 46.3 14.3 32 32 32zM176 288c-44.2 "
        "0-80-35.8-80-80s35.8-80 80-80s80 35.8 80 80s-35.8 80-80 80z",
    ),
    "house": (
        "0 0 576 512",
        "M575.8 255.5c0 18-15 32.1-32 32.1h-32l.7 160.2c0 2.7-.2 5.4-.5 8.1V472c0 22.1-17.9 40-40 40H456c-1.1 0-2.2 "
        "0-3.3-.1c-1.4 .1-2.8 .1-4.2 .1H416 392c-22.1 0-40-17.9-40-40V448 384c0-17.7-14.3-32-32-32H256c-17.7 0-32 14.3-32 32v64"
        " 24c0 22.1-17.9 40-40 40H160 128.1c-1.5 0-3-.1-4.5-.2c-1.2 .1-2.4 .2-3.6 .2H104c-22.1 0-40-17.9-40-40V360c0-.9 0-1.9 "
        ".1-2.8V287.6H32c-18 0-32-14-32-32.1c0-9 3-17 10-24L266.4 8c7-7 15-8 22-8s15 2 21 7L564.8 231.5c8 7 12 15 11 24z",
    ),
    "person-shelter": (
        "0 0 512 512",
        "M271.9 4.2c-9.8-5.6-21.9-5.6-31.8 0l-224 128C6.2 137.9 0 148.5 0 160V480c0 17.7 14.3 32 32 32s32-14.3 32-32V178.6L256 "
        "68.9 448 178.6V480c0 17.7 14.3 32 32 32s32-14.3 32-32V160c0-11.5-6.2-22.1-16.1-27.8l-224-128zM256 208c22.1 0 40-17.9 "
        "40-40s-17.9-40-40-40s-40 17.9-40 40s17.9 40 40 40zm-8 280V400h16v88c0 13.3 10.7 24 24 24s24-10.7 24-24V313.5l26.9 "
        "49.9c6.3 11.7 20.8 16 32.5 9.8s16-20.8 9.8-32.5l-37.9-70.3c-15.3-28.5-45.1-46.3-77.5-46.3H246.2c-32.4 0-62.1 17.8-77.5"
        " 46.3l-37.9 70.3c-6.3 11.7-1.9 26.2 9.8 32.5s26.2 1.9 32.5-9.8L200 313.5V488c0 13.3 10.7 24 24 24s24-10.7 24-24z",
    ),
    "tent": (
        "0 0 576 512",
        "M269.4 6C280.5-2 295.5-2 306.6 6l224 160c7.4 5.3 12.2 13.5 13.2 22.5l32 288c1 9-1.9 18.1-8 24.9s-14.7 10.7-23.8 "
        "10.7H416L288 288V512H32c-9.1 0-17.8-3.9-23.8-10.7s-9-15.8-8-24.9l32-288c1-9 5.8-17.2 13.2-22.5L269.4 6z",
    ),
    "train": (
        "0 0 448 512",
        "M96 0C43 0 0 43 0 96V352c0 48 35.2 87.7 81.1 94.9l-46 46C28.1 499.9 33.1 512 43 512H82.7c8.5 0 16.6-3.4 22.6-9.4L160 "
        "448H288l54.6 54.6c6 6 14.1 9.4 22.6 9.4H405c10 0 15-12.1 7.9-19.1l-46-46c46-7.1 81.1-46.9 "
        "81.1-94.9V96c0-53-43-96-96-96H96zM64 96c0-17.7 14.3-32 32-32H352c17.7 0 32 14.3 32 32v96c0 17.7-14.3 32-32 32H96c-17.7"
        " 0-32-14.3-32-32V96zM224 384c-26.5 0-48-21.5-48-48s21.5-48 48-48s48 21.5 48 48s-21.5 48-48 48z",
    ),
    "bus": (
        "0 0 512 512",
        "M256 0C390.4 0 480 35.2 480 80V96l0 32c17.7 0 32 14.3 32 32v64c0 17.7-14.3 32-32 32l0 160c0 17.7-14.3 32-32 32v32c0 "
        "17.7-14.3 32-32 32H384c-17.7 0-32-14.3-32-32V448H160v32c0 17.7-14.3 32-32 32H96c-17.7 0-32-14.3-32-32l0-32c-17.7 "
        "0-32-14.3-32-32l0-160c-17.7 0-32-14.3-32-32V160c0-17.7 14.3-32 32-32h0V96h0V80C32 35.2 121.6 0 256 0zM96 160v96c0 17.7"
        " 14.3 32 32 32H240V128H128c-17.7 0-32 14.3-32 32zM272 288H384c17.7 0 32-14.3 "
        "32-32V160c0-17.7-14.3-32-32-32H272V288zM112 400c17.7 0 32-14.3 32-32s-14.3-32-32-32s-32 14.3-32 32s14.3 32 32 32zm288 "
        "0c17.7 0 32-14.3 32-32s-14.3-32-32-32s-32 14.3-32 32s14.3 32 32 32zM352 80c0-8.8-7.2-16-16-16H176c-8.8 0-16 7.2-16 "
        "16s7.2 16 16 16H336c8.8 0 16-7.2 16-16z",
    ),
    "plane": (
        "0 0 576 512",
        "M482.3 192c34.2 0 93.7 29 93.7 64c0 36-59.5 64-93.7 64l-116.6 0L265.2 495.9c-5.7 10-16.3 16.1-27.8 16.1l-56.2 0"
        "c-10.6 0-18.3-10.2-15.4-20.4l49-171.6L112 320 68.8 377.6c-3 4-7.8 6.4-12.8 6.4l-42 0c-7.8 0-14-6.3-14-14"
        "c0-1.3 .2-2.6 .5-3.9L32 256 .5 145.9c-.4-1.3-.5-2.6-.5-3.9c0-7.8 6.3-14 14-14l42 0c5 0 9.8 2.4 12.8 6.4L112 192"
        "l102.9 0-49-171.6C162.9 10.2 170.6 0 181.2 0l56.2 0c11.5 0 22.1 6.2 27.8 16.1L365.7 192l116.6 0z",
    ),
    "bridge": (
        "0 0 576 512",
        "M32 32C14.3 32 0 46.3 0 64S14.3 96 32 96H72v64H0V288c53 0 96 43 96 96v64c0 17.7 14.3 32 32 32h32c17.7 0 32-14.3 "
        "32-32V384c0-53 43-96 96-96s96 43 96 96v64c0 17.7 14.3 32 32 32h32c17.7 0 32-14.3 32-32V384c0-53 43-96 "
        "96-96V160H504V96h40c17.7 0 32-14.3 32-32s-14.3-32-32-32H32zM456 96v64H376V96h80zM328 96v64H248V96h80zM200 "
        "96v64H120V96h80z",
    ),
    "water": (
        "0 0 576 512",
        "M269.5 69.9c11.1-7.9 25.9-7.9 37 0C329 85.4 356.5 96 384 96c26.9 0 55.4-10.8 77.4-26.1l0 0c11.9-8.5 28.1-7.8 39.2 "
        "1.7c14.4 11.9 32.5 21 50.6 25.2c17.2 4 27.9 21.2 23.9 38.4s-21.2 27.9-38.4 23.9c-24.5-5.7-44.9-16.5-58.2-25C449.5 "
        "149.7 417 160 384 160c-31.9 0-60.6-9.9-80.4-18.9c-5.8-2.7-11.1-5.3-15.6-7.7c-4.5 2.4-9.7 5.1-15.6 7.7c-19.8 9-48.5 "
        "18.9-80.4 18.9c-33 0-65.5-10.3-94.5-25.8c-13.4 8.4-33.7 19.3-58.2 25c-17.2 4-34.4-6.7-38.4-23.9s6.7-34.4 "
        "23.9-38.4C42.8 92.6 61 83.5 75.3 71.6c11.1-9.5 27.3-10.1 39.2-1.7l0 0C136.7 85.2 165.1 96 192 96c27.5 0 55-10.6 "
        "77.5-26.1zm37 288C329 373.4 356.5 384 384 384c26.9 0 55.4-10.8 77.4-26.1l0 0c11.9-8.5 28.1-7.8 39.2 1.7c14.4 11.9 32.5"
        " 21 50.6 25.2c17.2 4 27.9 21.2 23.9 38.4s-21.2 27.9-38.4 23.9c-24.5-5.7-44.9-16.5-58.2-25C449.5 437.7 417 448 384 "
        "448c-31.9 0-60.6-9.9-80.4-18.9c-5.8-2.7-11.1-5.3-15.6-7.7c-4.5 2.4-9.7 5.1-15.6 7.7c-19.8 9-48.5 18.9-80.4 18.9c-33 "
        "0-65.5-10.3-94.5-25.8c-13.4 8.4-33.7 19.3-58.2 25c-17.2 4-34.4-6.7-38.4-23.9s6.7-34.4 23.9-38.4c18.1-4.2 36.2-13.3 "
        "50.6-25.2c11.1-9.4 27.3-10.1 39.2-1.7l0 0C136.7 373.2 165.1 384 192 384c27.5 0 55-10.6 77.5-26.1c11.1-7.9 25.9-7.9 37 "
        "0zm0-144C329 229.4 356.5 240 384 240c26.9 0 55.4-10.8 77.4-26.1l0 0c11.9-8.5 28.1-7.8 39.2 1.7c14.4 11.9 32.5 21 50.6 "
        "25.2c17.2 4 27.9 21.2 23.9 38.4s-21.2 27.9-38.4 23.9c-24.5-5.7-44.9-16.5-58.2-25C449.5 293.7 417 304 384 304c-31.9 "
        "0-60.6-9.9-80.4-18.9c-5.8-2.7-11.1-5.3-15.6-7.7c-4.5 2.4-9.7 5.1-15.6 7.7c-19.8 9-48.5 18.9-80.4 18.9c-33 "
        "0-65.5-10.3-94.5-25.8c-13.4 8.4-33.7 19.3-58.2 25c-17.2 4-34.4-6.7-38.4-23.9s6.7-34.4 23.9-38.4c18.1-4.2 36.2-13.3 "
        "50.6-25.2c11.1-9.5 27.3-10.1 39.2-1.7l0 0C136.7 229.2 165.1 240 192 240c27.5 0 55-10.6 77.5-26.1c11.1-7.9 25.9-7.9 37 "
        "0z",
    ),
    "phone": (
        "0 0 512 512",
        "M164.9 24.6c-7.7-18.6-28-28.5-47.4-23.2l-88 24C12.1 30.2 0 46 0 64C0 311.4 200.6 512 448 512c18 0 33.8-12.1 "
        "38.6-29.5l24-88c5.3-19.4-4.6-39.7-23.2-47.4l-96-40c-16.3-6.8-35.2-2.1-46.3 11.6L304.7 368C234.3 334.7 177.3 277.7 144 "
        "207.3L193.3 167c13.7-11.2 18.4-30 11.6-46.3l-40-96z",
    ),
    "square-parking": (
        "0 0 448 512",
        "M64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64zM192 "
        "256h48c17.7 0 32-14.3 32-32s-14.3-32-32-32H192v64zm48 64H192v32c0 17.7-14.3 32-32 32s-32-14.3-32-32V288 168c0-22.1 "
        "17.9-40 40-40h72c53 0 96 43 96 96s-43 96-96 96z",
    ),
    "restroom": (
        "0 0 640 512",
        "M176 48c0 26.5-21.5 48-48 48s-48-21.5-48-48s21.5-48 48-48s48 21.5 48 48zM120 352V480c0 17.7-14.3 32-32 "
        "32s-32-14.3-32-32V325.2c-8.1 9.2-21.1 13.2-33.5 9.4c-16.9-5.3-26.3-23.2-21-40.1l30.9-99.1C44.9 155.3 82 128 124 "
        "128h8c42 0 79.1 27.3 91.6 67.4l30.9 99.1c5.3 16.9-4.1 34.8-21 40.1c-12.4 3.9-25.4-.2-33.5-9.4V480c0 17.7-14.3 32-32 "
        "32s-32-14.3-32-32V352H120zM320 0c13.3 0 24 10.7 24 24V488c0 13.3-10.7 24-24 24s-24-10.7-24-24V24c0-13.3 10.7-24 "
        "24-24zM560 48c0 26.5-21.5 48-48 48s-48-21.5-48-48s21.5-48 48-48s48 21.5 48 48zM440 480V384H422.2c-10.9 "
        "0-18.6-10.7-15.2-21.1l9-26.9c-3.2 0-6.4-.5-9.5-1.5c-16.9-5.3-26.3-23.2-21-40.1l29.7-95.2C428.4 156.9 467.6 128 512 "
        "128s83.6 28.9 96.8 71.2l29.7 95.2c5.3 16.9-4.1 34.8-21 40.1c-3.2 1-6.4 1.5-9.5 1.5l9 26.9c3.5 10.4-4.3 21.1-15.2 "
        "21.1H584v96c0 17.7-14.3 32-32 32s-32-14.3-32-32V384H504v96c0 17.7-14.3 32-32 32s-32-14.3-32-32z",
    ),
    "fire": (
        "0 0 448 512",
        "M159.3 5.4c7.8-7.3 19.9-7.2 27.7 .1c27.6 25.9 53.5 53.8 77.7 84c11-14.4 23.5-30.1 37-42.9c7.9-7.4 20.1-7.4 28 .1c34.6 "
        "33 63.9 76.6 84.5 118c20.3 40.8 33.8 82.5 33.8 111.9C448 404.2 348.2 512 224 512C98.4 512 0 404.1 0 276.5c0-38.4 "
        "17.8-85.3 45.4-131.7C73.3 97.7 112.7 48.6 159.3 5.4zM225.7 416c25.3 0 47.7-7 68.8-21c42.1-29.4 53.4-88.2 "
        "28.1-134.4c-2.8-5.6-5.6-11.2-9.8-16.8l-50.6 58.8s-81.4-103.6-87.1-110.6C133.1 243.8 112 273.2 112 306.8C112 375.4 "
        "162.6 416 225.7 416z",
    ),
    "circle-info": (
        "0 0 512 512",
        "M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM216 336h24V272H216c-13.3 "
        "0-24-10.7-24-24s10.7-24 24-24h48c13.3 0 24 10.7 24 24v88h8c13.3 0 24 10.7 24 24s-10.7 24-24 24H216c-13.3 "
        "0-24-10.7-24-24s10.7-24 24-24zm40-144c-17.7 0-32-14.3-32-32s14.3-32 32-32s32 14.3 32 32s-14.3 32-32 32z",
    ),
}


#: The heading names its two lengths with the same outlines as the pins.
#: Font Awesome Free 6.2.0 by @fontawesome, https://fontawesome.com --
#: Icons: CC BY 4.0. Copyright 2022 Fonticons, Inc.
LENGTH_ICONS: dict[str, tuple[str, str]] = {
    "person-walking": (
        "0 0 320 512",
        "M256 48c0 26.5-21.5 48-48 48s-48-21.5-48-48s21.5-48 48-48s48 21.5 48 48zM126.5 199.3c-1 .4-1.9 .8-2.9 1.2l-8 3.5c-16.4 7.3-29 21.2"
        "-34.7 38.2l-2.6 7.8c-5.6 16.8-23.7 25.8-40.5 20.2s-25.8-23.7-20.2-40.5l2.6-7.8c11.4-34.1 36.6-61.9 69.4-76.5l8-3.5c20.8-9.2 43.3-1"
        "4 66.1-14c44.6 0 84.8 26.8 101.9 67.9L281 232.7l21.4 10.7c15.8 7.9 22.2 27.1 14.3 42.9s-27.1 22.2-42.9 14.3L247 287.3c-10.3-5.2-18"
        ".4-13.8-22.8-24.5l-9.6-23-19.3 65.5 49.5 54c5.4 5.9 9.2 13 11.2 20.8l23 92.1c4.3 17.1-6.1 34.5-23.3 38.8s-34.5-6.1-38.8-23.3l-22-8"
        "8.1-70.7-77.1c-14.8-16.1-20.3-38.6-14.7-59.7l16.9-63.5zM68.7 398l25-62.4c2.1 3 4.5 5.8 7 8.6l40.7 44.4-14.5 36.2c-2.4 6-6 11.5-10."
        "6 16.1L54.6 502.6c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L68.7 398z",
    ),
    "water": MARKER_ICONS["water"],
}


#: What awesome-markers called each colour, as the colour it drew.
#:
#: **The whole palette and not the five this map uses.** `add_points` takes a
#: colour by name and always has; narrowing it to what one caller happens to ask
#: for turns a working argument into a `KeyError` for the next one, which is
#: what five tests said the moment it was tried.
#:
#: The five in use were sampled off the built page rather than looked up, and
#: four of the five agree with the palette the library documents to within the
#: gradient its sprite is drawn with. The fifth sample landed on an overlapping
#: neighbour, which is why the documented values are what is written here.
PIN_COLOURS: dict[str, str] = {
    "red": "#d33d2a",
    "darkred": "#a23336",
    "lightred": "#ff8e7f",
    "orange": "#f69730",
    "beige": "#ffcb92",
    "green": "#70af00",
    "darkgreen": "#728224",
    "lightgreen": "#bbf970",
    "blue": "#38aadd",
    "darkblue": "#0067a3",
    "cadetblue": "#436978",
    "lightblue": "#8adaff",
    "purple": "#d152b8",
    "darkpurple": "#5b396b",
    "pink": "#ff91ea",
    "white": "#fbfbfb",
    "gray": "#575757",
    "lightgray": "#a3a3a3",
    "black": "#303030",
}

#: How large a pin is drawn, before the zoom has its say. awesome-markers drew
#: 35 x 45 at every zoom; reported from a phone, that is too much of the map at
#: the zoom this park opens at, where 198 of them stand over the terrain.
PIN_WIDTH = 28
PIN_HEIGHT = 36

#: The bulb and the tip that sits on the position, as one path -- so a pin is one
#: element, and the shadow awesome-markers drew is gone with its sprite.
PIN_SHAPE = (
    "M14 0C6.3 0 0 6.3 0 14c0 3.6 1.6 7.4 4 11 2.4 3.6 5.4 7 8.1 9.9"
    "a2.6 2.6 0 0 0 3.8 0C18.6 32 21.6 28.6 24 25c2.4-3.6 4-7.4 4-11 0-7.7-6.3-14-14-14z"
)

#: Attribute a pin layer carries listing the glyphs it drew, in the order they
#: first appeared, so the legend's row can show the pins rather than a bar.
PIN_GLYPHS_ATTR = "_trails_pin_glyphs"


#: How many decimals a drawn coordinate is written with.
#:
#: **The page carries the precision it can draw, not the precision it was
#: given.** A projected metre answered as a float comes out as
#: ``65.44107796402518`` -- seventeen digits, of which the eighth is already
#: eleven centimetres at this latitude and the ninth is a millimetre. Nothing on
#: this map reads a drawn coordinate back; they are handed to Leaflet, which
#: rounds them to the pixel. Measured on the built page, the eleven thousand
#: location arrays weigh 3.21 MB and 2.03 at six decimals.
#:
#: Six is 11.1 cm of latitude and 4.6 cm of longitude at 65.4 deg N -- below the
#: metre the sources themselves are surveyed to, and the same rule
#: :func:`add_points` already applies to the named-point table.
DRAWN_DECIMALS = 6

#: What Leaflet already believes about a path, which folium writes out for every
#: feature regardless.
#:
#: **Folium names every Leaflet option in its own signature**, so
#: ``path_options`` returns all fourteen of them whether or not a caller said
#: anything, and each one is written into the page once per feature. Measured on
#: the built page: 12,700 option objects, **4.59 MB**, of which the varying part
#: -- the class, the colour, the width, the opacity -- is under a quarter.
#:
#: **Only what nothing reads is dropped.** ``color``, ``weight`` and ``opacity``
#: stay whatever they are, because :class:`_ClickHighlight` captures those three
#: off ``layer.options`` before it restyles anything and hands them back to
#: ``setStyle`` afterwards; dropping one that happened to equal Leaflet's
#: default would restore it as ``undefined``. The rest are decoration nothing in
#: this page ever asks about.
_LEAFLET_PATH_DEFAULTS: dict[str, Any] = {
    "bubblingMouseEvents": True,
    "dashArray": None,
    "dashOffset": None,
    "fillOpacity": 0.2,
    "fillRule": "evenodd",
    "lineCap": "round",
    "lineJoin": "round",
    "noClip": False,
    "smoothFactor": 1.0,
    "stroke": True,
}


def _lean(options: dict[str, Any], *, filled: bool) -> dict[str, Any]:
    """Drop from a Leaflet options object what Leaflet would have assumed anyway.

    See :data:`_LEAFLET_PATH_DEFAULTS` for what is dropped and what is kept on
    purpose.

    Args:
        options: What folium built, as it will be written into the page.
        filled: Whether the shape fills by default -- ``L.Polyline`` does not
            and ``L.CircleMarker`` does, and that is the one default that
            differs between the two.

    Returns:
        The same options with the assumable ones removed.
    """
    lean = {}
    for key, value in options.items():
        if key in _LEAFLET_PATH_DEFAULTS and value == _LEAFLET_PATH_DEFAULTS[key]:
            continue
        # Leaflet paints the fill with ``fillColor || color``, so a fill colour
        # that repeats the stroke colour is the same drawing said twice.
        if key == "fillColor" and value == options.get("color"):
            continue
        if key == "fill" and value is filled:
            continue
        lean[key] = value
    return lean


PACK_IO = files("trails.visualization").joinpath("js", "pack_io.js").read_text(encoding="utf-8")
SERVICE_WORKER = files("trails.visualization").joinpath("js", "worker.js").read_text(encoding="utf-8").replace("__PACK_IO__", PACK_IO)

#: Where a third party's file is kept once it has been fetched. A build needs
#: the network for it exactly once, and after that never again -- the same
#: bargain every other download in this project makes.
VENDOR_CACHE = pathlib.Path(".cache/vendor")


def vendored(url: str) -> str:
    """Fetch a third-party file once, keep it, and return its text.

    **Written into the page rather than linked from a CDN.** Measured on the
    published map, the four hosts it linked to cost 832 kB and, more to the
    point on a slow connection, four DNS lookups and four TLS handshakes before
    a single byte of any of them arrives -- some 2.8 seconds at a 200 ms round
    trip, spent before the map can draw. Inlined they arrive in the stream the
    reader is already downloading.

    Kept under ``.cache/`` and keyed by the whole URL, so a version folium
    changes is a different key and not a stale file. Nothing is committed: this
    is somebody else's code and the repository does not carry it.

    Args:
        url: What to fetch, once.

    Returns:
        The file's text.
    """
    VENDOR_CACHE.mkdir(parents=True, exist_ok=True)
    kept = VENDOR_CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + "-" + url.rsplit("/", 1)[-1])
    if not kept.exists():
        import requests

        answer = requests.get(url, timeout=60)
        answer.raise_for_status()
        kept.write_bytes(answer.content)
    return kept.read_text(encoding="utf-8")


def write_service_worker(beside: pathlib.Path, provider: Provider = PROVIDERS["kartverket"], companions: Companions = ROOT) -> pathlib.Path:
    """Write the map's service worker next to the page it belongs to.

    **Stamped with the page's own digest**, because a browser installs a worker
    only when its bytes change. A deploy that changes the map therefore changes
    the worker, which changes the cache name, which drops the old map -- and a
    rebuild that changes nothing changes nothing.

    Args:
        beside: The built page.
        provider: Whose tiles the worker intercepts and keeps.
        companions: The names the worker, its database and its caches go by --
            the same set the page was built with.

    Returns:
        Where the worker was written.
    """
    stamp = hashlib.sha256(beside.read_bytes()).hexdigest()[:16]
    written = beside.with_name(companions.worker)
    script = (
        SERVICE_WORKER.replace("__VERSION__", stamp)
        .replace("__TILE_PREFIX__", provider.tiles)
        .replace("__TILE_TOP__", str(provider.top))
        .replace("__HEIGHT_PREFIX__", provider.heights.tiles if provider.heights else "")
        .replace("__HEIGHT_TOP__", str(provider.heights.top if provider.heights else 0))
        .replace("__SHADE_PREFIX__", provider.shade.tiles if provider.shade else "")
        .replace("__SHADE_TOP__", str(provider.shade.top if provider.shade else 0))
        .replace("__SLOPE_PREFIX__", provider.slope.tiles if provider.slope else "")
        .replace("__SLOPE_TOP__", str(provider.slope.top if provider.slope else 0))
        .replace("__VEGETATION_PREFIX__", provider.vegetation.tiles if provider.vegetation else "")
        .replace("__VEGETATION_TOP__", str(provider.vegetation.top if provider.vegetation else 0))
        .replace("__FOREST_PREFIX__", provider.forest.tiles if provider.forest else "")
        .replace("__FOREST_TOP__", str(provider.forest.top if provider.forest else 0))
        .replace("__MIRE_PREFIX__", provider.mire.tiles if provider.mire else "")
        .replace("__MIRE_TOP__", str(provider.mire.top if provider.mire else 0))
        .replace("__DB__", companions.database)
        .replace("__CACHE__", companions.cache)
    )
    written.write_text(script, encoding="utf-8")
    return written


#: The mark, as three flat colours: the ground the panels use, a near peak and a
#: far one. Drawn rather than committed, because a repository that carries a PNG
#: carries it for ever and this one is eleven lines of arithmetic.
_ICON_GROUND = (0x1D, 0x28, 0x2C)
_ICON_FAR = (0x7D, 0x8F, 0x96)
_ICON_NEAR = (0xF2, 0xF0, 0xEB)

#: Two peaks, as fractions of the icon's side: (apex x, apex y, left x, right x).
#: The baseline is shared, which is what makes them one range rather than two
#: triangles that happen to be near each other.
_ICON_PEAKS = (((0.30, 0.40), 0.02, 0.58, _ICON_FAR), ((0.58, 0.24), 0.20, 0.98, _ICON_NEAR))
_ICON_BASE = 0.80


#: Where the mark lives. One of a pair, drawn beside the almanac icon that
#: ``weather-cards`` publishes at ``almanac.cairn.zone``: the same stack of five
#: unequal stones -- a cairn, which is what marks a route in these mountains --
#: with a path below it here and an arc above it there. The stones are ellipses
#: rather than rounded rectangles, because rounded rectangles stack into a set of
#: teacups with a seam at every corner, and they are unequal and set off one
#: another, because evenly centred a cairn reads as a wedding cake. The drawing
#: script is in ``docs/draw.ts``. **A second map is a variant of the same
#: mark**: ``atlas-abisko`` is the cairn on the same path, standing in the
#: U-shaped gate of Lapporten, which is what tells Abisko from anywhere else --
#: not the national parks' gold star, which is Naturvårdsverket's own mark and
#: not ours to redraw. Each :class:`Companions` names the drawing it copies.
ICON_DIR = pathlib.Path(__file__).parent / "icons"

#: The sizes written beside the page, and what each is for. 180 is the one iOS
#: reads off ``apple-touch-icon``; 32 is the tab; 192 and 512 are what the
#: manifest offers a launcher. They are shipped rather than drawn: this module
#: used to rasterise a triangle into a ``data:`` URI, which is how a page ends up
#: with a touch-icon link Safari will not fetch.
ICON_SIZES = (32, 180, 192, 512)


def write_icons(beside: pathlib.Path, companions: Companions = ROOT) -> list[pathlib.Path]:
    """Write the mark beside the built page, one file per size.

    **Files, because a ``data:`` URI does not work for the one link that
    matters.** iOS reads ``apple-touch-icon`` from the document rather than the
    manifest's icons, and it will not fetch a ``data:`` URI for it -- so an
    inline mark is a link that is present and does nothing, and the home screen
    falls back to a screenshot of the page.

    The names are the page's, not the source's: ``icon-180.png`` beside the map,
    copied from the drawing the companions name in :data:`ICON_DIR`. The deploy
    uploads whatever this wrote.

    Args:
        beside: The built page. The icons are written into its directory.
        companions: The names the files take; the page links to the same.

    Returns:
        The files written, in the order of :data:`ICON_SIZES`.

    Raises:
        FileNotFoundError: If a size is missing from :data:`ICON_DIR`, which
            means the page would ship a link to an object that is not there.
    """
    written = []
    for side in ICON_SIZES:
        source = ICON_DIR / f"{companions.mark}-{side}.png"
        if not source.is_file():
            raise FileNotFoundError(f"no icon at {source} — the page links to {companions.icon_named(side)}; draw it with docs/draw.ts")
        target = beside.with_name(companions.icon_named(side))
        target.write_bytes(source.read_bytes())
        written.append(target)
    return written


def write_manifest(beside: pathlib.Path, name: str, companions: Companions = ROOT) -> pathlib.Path:
    """Write the manifest that makes the map installable.

    **Which is not decoration: it is what makes an offline map survive.** WebKit
    deletes storage a script created once an origin has gone seven days without
    a visit -- exactly the walk somebody keeps the terrain for a fortnight
    before -- and the exemptions are persisted storage and a home-screen install.
    Asking for the first is a line of JavaScript; offering the second needs this.

    **Its icons are the files :func:`write_icons` wrote**, named relatively, the
    way ``start_url`` is and for the same reason: nothing about the account or
    the host may be written into this repository, and the object is ``X.html``
    served at ``/X``. They used to be ``data:`` URIs, which cost the deploy no
    binaries and cost the home screen its icon -- see :class:`_Head`.

    ``purpose`` is ``any maskable``: the mark is a full square with the cairn
    well inside it, so a launcher may crop it to a circle, a squircle or a
    rounded square without cutting a stone off.

    ``id`` is the page's own address, which is what a browser takes for it when
    none is given; said out loud, two maps on one origin are two apps and not
    one app that changed its start page.

    Args:
        beside: The built page, whose name is the address the app opens at.
        name: What the installed map is called.
        companions: The names the manifest and the icons go by, and the scope.

    Returns:
        Where the manifest was written.
    """
    manifest = {
        "id": "./" + beside.stem,
        "name": name,
        "short_name": name,
        "start_url": "./" + beside.stem,
        "scope": companions.scope,
        "display": "standalone",
        "orientation": "any",
        "background_color": "#1d282c",
        "theme_color": "#1d282c",
        "icons": [
            {"src": "./" + companions.icon_named(192), "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "./" + companions.icon_named(512), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    written = beside.with_name(companions.manifest)
    written.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    return written


class _Head(Element):
    """The page's name, its mark, and where the manifest is.

    Folium writes no ``<title>`` at all, so the tab and a home-screen icon were
    both labelled with the URL.

    **The mark is a file and not a ``data:`` URI, and that is the whole of a bug
    this page carried.** iOS reads ``apple-touch-icon`` from the document and
    ignores the manifest's icons -- which this file knew, and answered by putting
    the mark inline, on the reasoning that a second object to deploy for 700
    bytes was not a trade. It is: Safari will not fetch a ``data:`` URI for a
    touch icon, so the link was present, well-formed, and dead. Added to a home
    screen, atlas got a screenshot of the map. Reported from a phone, and the
    same defect the sibling site had.

    **An `Element` and not a `MacroElement`, for the reason `_Inlined` records
    above it**: a macro's ``header`` block adds a child to the figure's header
    while the figure is rendering that very header, and branca raises
    ``OrderedDict mutated during iteration``. It cost this file a build twice.

    **There is no viewport meta here, and that is not an omission.** Folium's own
    map template writes one -- ``width=device-width, initial-scale=1.0,
    maximum-scale=1.0, user-scalable=no`` -- and it renders *after* this, so a
    second one here is dead weight that merely looks authoritative. It was added
    once, on a search that had reported none: the tag is written across **two
    lines**, and ``grep -o '<meta[^>]*>'`` is line-based and cannot see a tag
    with a newline in it. Search this page's head with something that is not.
    """

    _template = Template("""{{ this.body }}""")

    def __init__(self, title: str, companions: Companions = ROOT) -> None:
        """Hold the head.

        Args:
            title: What the page and an installed copy of it are called.
            companions: The names the icons and the manifest are linked by.
        """
        super().__init__()
        named = escape(title, quote=True)
        # **The path is put right before the links below are read.** The edge
        # draws this map for `/abisko/` as well as `/abisko` -- a copied link
        # ends in a slash often enough that the rewrite rule exists for it --
        # but every companion here is linked relatively, and under `/abisko/`
        # the worker, the manifest and the icons resolve to addresses that hold
        # nothing (decisions §8.2). Dropping the slash from the document's URL
        # changes what the links resolve against and what the address bar
        # shows, and nothing else; the root and a file on disk are left alone.
        trimmed = (
            "<script>(function () {\n"
            "  var path = location.pathname;\n"
            "  if (path.length > 1 && path.charAt(path.length - 1) === '/' && history.replaceState) {\n"
            "    history.replaceState(history.state, '', path.slice(0, -1) + location.search + location.hash);\n"
            "  }\n"
            "})();</script>\n"
        )
        self.body = (
            trimmed + f"<title>{named}</title>\n"
            '<meta name="apple-mobile-web-app-capable" content="yes">\n'
            '<meta name="mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
            f'<meta name="apple-mobile-web-app-title" content="{named}">\n'
            f'<link rel="apple-touch-icon" href="{companions.icon_named(180)}">\n'
            f'<link rel="icon" type="image/png" sizes="32x32" href="{companions.icon_named(32)}">\n'
            f'<link rel="manifest" href="{companions.manifest}">'
        )


def _squeezed(html: str) -> str:
    """Take the indentation out of a rendered page.

    **Folium's templates are indented for the template**, not for the document:
    every feature arrives inside four nested macros and comes out under twelve
    to sixteen spaces, with three or four empty lines between one feature and
    the next. Measured on the built page, 340,856 lines carried 163,377 blank
    ones and 2.78 MB of leading whitespace -- **2.88 MB** in all, none of which
    any reader or any browser has a use for.

    **It is worth almost nothing on the wire and something on the clock.** The
    deploy compresses at brotli 11, where whitespace is nearly free; what it
    saves is bytes the browser's parser has to walk, and the page's cost is
    parse and not network -- 241 ms of transfer against 2,473 ms to
    ``domInteractive``.

    **A template literal is left exactly as it was.** A newline inside backticks
    is part of the string, and folium's tooltip is written across three lines,
    so lines between an opening backtick and its closing one are copied
    untouched. Everything else is JavaScript or markup, where a run of
    whitespace outside a string means nothing -- and only whole-line whitespace
    is removed, so a newline still stands between any two tags that had one.

    **Which lines those are is read the way a JavaScript parser reads them**,
    not by counting backticks: inside a ``<script>`` block the walk knows a
    quoted string, a comment and a template literal with its ``${...}``
    expressions from one another, so a backtick that is *data* -- an OSM path
    named ``EkMalm`sStig`` stopped the first Malingsbo-Kloten build, 2026-09-20,
    when the walk was a parity count -- is a character in a string and opens
    nothing. Any text may stand in a name. Outside a script block nothing is
    lexed at all: markup carries apostrophes in prose and no template literal.
    A regular-expression literal is told from a division the way every
    lexer without a parser does it, by the character before the slash: after
    an operand (a name, a number, a closing bracket) it divides, after anything
    else it opens a pattern, which runs to its closing slash with a character
    class read whole -- the page's own ``/[&<>"']/g`` would otherwise leave a
    quote open (it did, 2026-09-20). A block left open stops the build loudly
    below rather than guessing. The vendored files -- Leaflet, jQuery and the rest, between the
    ``<!-- vendored:name -->`` fences -- do carry such regular expressions
    (Leaflet's left a quote open for the walk), and they are minified with
    nothing to squeeze, so a fenced block is copied whole and not read.

    Args:
        html: The rendered page.

    Returns:
        The same page with its whitespace taken out.

    Raises:
        AssertionError: If a script block ends inside a string, a comment or a
            template literal, which means the walk lost its place and nothing
            was safe to remove.
    """
    walk = _ScriptWalk()
    out: list[str] = []
    for line in html.split("\n"):
        in_template = walk.in_template
        opaque = walk.opaque
        walk.feed(line)
        if opaque or walk.opaque:
            # Somebody else's file, minified and fenced: copied as it is, since
            # its regular expressions are not ours to read (Leaflet's leave a
            # quote open for this walk) and it holds nothing worth squeezing.
            out.append(line)
        elif in_template:
            # Inside the string: every character of the line is the string's.
            out.append(line)
        elif walk.in_template:
            # The indentation is still the document's; the tail is the string's.
            out.append(line.lstrip())
        else:
            stripped = line.strip()
            if stripped:
                out.append(stripped)
    assert walk.settled, "a script block is still open inside a string, a comment or a template literal, so nothing was safe to remove"
    return "\n".join(out)


class _ScriptWalk:
    """Where a JavaScript parser would be after reading a page line by line.

    Markup until ``<script``; inside the block, code, a single- or double-quoted
    string, a line or block comment, a regular expression, or a template
    literal -- the last with a stack, since ``${...}`` re-enters code and may
    hold strings and templates of its own. Only ``in_template`` matters to the
    squeezer; the rest is tracked so that a backtick inside a string, a comment
    or a pattern counts for nothing.
    """

    #: What may stand before a slash that divides: the end of an operand. After
    #: anything else -- an operator, a bracket, a comma, the start of a
    #: statement -- a slash opens a regular expression.
    _OPERAND_END = re.compile(r"[\w$)\]]$")
    #: Words that end in a word character and are not operands: a slash after
    #: ``return`` opens a pattern.
    _KEYWORDS = frozenset({"return", "typeof", "case", "in", "of", "do", "else", "instanceof", "void", "delete", "throw", "new", "await", "yield"})

    _OPEN = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
    _CLOSE = "</script>"
    _FENCE_OPEN = "<!-- vendored:"
    _FENCE_CLOSE = "<!-- /vendored:"

    def __init__(self) -> None:
        self.in_script = False
        #: Between the fences of a vendored file, which is not read at all.
        self.opaque = False
        #: The last character of code seen, for telling a division from a
        #: pattern; whitespace and comments do not count.
        self.last_code = ""
        #: The word that character ends, if it is a word character.
        self.word = ""
        # The stack of open constructs inside a script block: "'", '"', "`",
        # "//", "/*", or "{" for a template expression. Empty means code.
        self.stack: list[str] = []

    @property
    def in_template(self) -> bool:
        return bool(self.stack) and self.stack[-1] == "`"

    @property
    def settled(self) -> bool:
        """True while no script block is open inside anything."""
        return not (self.in_script and self.stack)

    def feed(self, line: str) -> None:
        """Advance over one line (its newline implied at the end)."""
        if self.opaque:
            if self._FENCE_CLOSE in line:
                self.opaque = False
            return
        if not self.in_script and self._FENCE_OPEN in line:
            self.opaque = self._FENCE_CLOSE not in line
            return
        i = 0
        n = len(line)
        while i < n:
            if not self.in_script:
                found = self._OPEN.search(line, i)
                if found is None:
                    return
                self.in_script = True
                i = found.end()
                continue
            top = self.stack[-1] if self.stack else None
            if top is None or top == "{":
                # Code. A closing script tag ends the block; nothing inside a
                # string can spell one, since _script_json escapes the bracket.
                if line.startswith(self._CLOSE, i) and top is None:
                    self.in_script = False
                    i += len(self._CLOSE)
                    continue
                ch = line[i]
                if line.startswith("//", i):
                    self.stack.append("//")
                    i += 2
                elif line.startswith("/*", i):
                    self.stack.append("/*")
                    i += 2
                elif ch == "/" and (not self._OPERAND_END.search(self.last_code) or self.word in self._KEYWORDS):
                    i = self._over_pattern(line, i + 1)
                    self.last_code = ")"
                    self.word = ""
                elif ch in ("'", '"', "`"):
                    self.stack.append(ch)
                    i += 1
                elif ch == "{" and top == "{":
                    # Braces inside a template expression nest; count them so the
                    # matching close does not end the expression early.
                    self.stack.append("{")
                    self.last_code = ch
                    self.word = ""
                    i += 1
                elif ch == "}" and top == "{":
                    self.stack.pop()
                    self.last_code = ch
                    self.word = ""
                    i += 1
                else:
                    if not ch.isspace():
                        self.last_code = ch
                        self.word = self.word + ch if ch.isalnum() or ch in "_$" else ""
                    i += 1
            elif top == "//":
                # To the end of the line, and the newline ends it.
                break
            elif top == "/*":
                close = line.find("*/", i)
                if close < 0:
                    return
                self.stack.pop()
                i = close + 2
            elif top in ("'", '"'):
                ch = line[i]
                if ch == "\\":
                    i += 2
                elif ch == top:
                    self.stack.pop()
                    # A string is an operand: a slash after it divides.
                    self.last_code = ")"
                    i += 1
                else:
                    i += 1
            else:  # a template literal
                ch = line[i]
                if ch == "\\":
                    i += 2
                elif ch == "`":
                    self.stack.pop()
                    self.last_code = ")"
                    i += 1
                elif line.startswith("${", i):
                    self.stack.append("{")
                    i += 2
                else:
                    i += 1
        if self.stack and self.stack[-1] == "//":
            self.stack.pop()

    @staticmethod
    def _over_pattern(line: str, i: int) -> int:
        """Where a regular expression that opened before ``i`` ends on this line.

        Args:
            line: The line
            i: The index after the opening slash

        Returns:
            The index after the closing slash and its flags; the line's end if
            the pattern is not closed, which a parser would refuse too
        """
        in_class = False
        n = len(line)
        while i < n:
            ch = line[i]
            if ch == "\\":
                i += 2
                continue
            if in_class:
                in_class = ch != "]"
            elif ch == "[":
                in_class = True
            elif ch == "/":
                i += 1
                while i < n and line[i].isalpha():
                    i += 1
                return i
            i += 1
        return n


#: Folium's own map template, which is where the page's viewport meta comes from.
#: Matched rather than compared, because it is written across two lines and the
#: indentation is gone by the time this runs.
_VIEWPORT = re.compile(r'<meta\s+name="viewport"[^>]*>')


def _viewport(html: str) -> str:
    """Give the browser its own zoom back, and tell it the screen has corners.

    **Folium hardcodes ``maximum-scale=1.0, user-scalable=no``** into every map
    it writes, and nothing in this project chose that: it takes the browser's
    pinch and double-tap zoom away from the whole document, which is a thing to
    decide rather than to inherit.

    **What it does not do, which is most of it.** Leaflet sets
    ``touch-action: none`` on ``.leaflet-container`` for a touch device, and this
    page's furniture -- the dock, the sheet, every panel -- is appended *inside*
    that container, which fills the screen. A descendant cannot re-grant what an
    ancestor took away, so removing the meta restores no gesture here today. And
    on iOS it never mattered either way: Safari has disregarded ``user-scalable``
    since iOS 10. This removes a restriction the page was making without meaning
    to; it does not make the panels zoomable, and saying otherwise would be a
    claim about ground nobody has walked.

    **And ``viewport-fit=cover``, which is what makes the insets exist.** The head
    asks for ``apple-mobile-web-app-status-bar-style: black-translucent``, so an
    installed app is drawn edge to edge -- under the status bar and over the home
    indicator. Without this the page is never told which part of that is covered:
    measured on the device, ``standalone true`` with ``safe-area-inset-top`` and
    ``-bottom`` both ``0px``, while the scale in the corner was being cut in half
    by the indicator sitting on it. The page asked for the whole screen and had no
    way to learn where the edges were.

    With it, ``env(safe-area-inset-*)`` reports the real numbers and the
    stylesheet keeps the controls out of them. It is one word here and a handful
    of rules there, and neither can be checked on this machine: every browser in
    this project runs on Linux, where the insets are zero whatever this says.

    Asserted rather than replaced quietly. If a folium release stops writing the
    tag, writes two, or drops ``user-scalable`` of its own accord, this says so
    at build time instead of leaving a stale rewrite in place for a year.

    Args:
        html: The rendered page.

    Returns:
        The page, with the viewport meta saying only what it needs to.
    """
    found = _VIEWPORT.findall(html)
    assert len(found) == 1, f"expected one viewport meta from folium, found {len(found)}"
    assert "user-scalable=no" in found[0], f"folium no longer writes user-scalable=no ({found[0]!r}) -- is this still needed?"
    return _VIEWPORT.sub(
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />',
        html,
        count=1,
    )


def save_map(fmap: folium.Map, path: pathlib.Path) -> pathlib.Path:
    """Render a map and write it, without the whitespace it renders with.

    Stands in for :meth:`folium.Map.save`, which renders and writes in one step
    and leaves nowhere to put :func:`_squeezed`.

    Args:
        fmap: The map to write.
        path: Where to write it.

    Returns:
        Where it was written.
    """
    path.write_text(_viewport(_squeezed(fmap.get_root().render())), encoding="utf-8")
    return path


def _tooltip(text: str, **options: Any) -> folium.Tooltip:
    """A hover tooltip carrying any text at all.

    **Folium writes the tooltip's text raw into a JavaScript template literal**
    (``bindTooltip(`<div>{{ this.text }}</div>`)``), so a name holding a
    backtick, a ``${`` or a closing script tag would end the literal, the
    expression or the block and break the page -- measured with a hostile name
    through the whole page, 2026-09-20, after an OSM path named ``EkMalm`sStig``
    stopped a build. The text is the tooltip's markup, so it is HTML-escaped,
    and the two characters that mean something to a template literal go as
    character references too: the browser reads ``&#96;`` and ``&#36;`` back as
    the characters, and the parser never sees them.

    Args:
        text: The text as the data has it
        options: Passed on to :class:`folium.Tooltip`

    Returns:
        The tooltip, safe to bind
    """
    return folium.Tooltip(escape(text).replace("`", "&#96;").replace("$", "&#36;"), **options)


def _pin(colour: str, icon: str) -> str:
    """Draw one map pin, bulb and glyph, as a single SVG.

    **The last third-party host, drawn instead of fetched.** awesome-markers is
    3,789 bytes of script, 2,225 of stylesheet, 36,669 of rotation rules and four
    sprite images fetched by relative path from `cdnjs.cloudflare.com` -- and all
    it draws is a coloured teardrop with a glyph in it. This page already speaks
    in inline SVG twice over, in the rail and in the plan control.

    The glyph is a nested ``<svg>`` with its own viewBox, so Font Awesome's
    outline scales into the bulb without a number being worked out by hand.

    Args:
        colour: What awesome-markers called the colour, e.g. ``darkred``.
        icon: Which of :data:`MARKER_ICONS` to draw in it.

    Returns:
        The pin, wrapped in the element the zoom scales.

    Raises:
        ValueError: If the colour or the icon is one this page does not draw. A
            marker with no glyph is a marker that says nothing, and a page that
            drew it silently would be worse than one that refuses to build.
    """
    # **Said, and not a KeyError with one word in it.** This page carries the
    # outlines it draws and nothing else -- a webfont for the whole of Font
    # Awesome was 252 kB for four glyphs -- so asking for a fifth is a thing to
    # be told about at build time, by name, with the answer in the message.
    if colour not in PIN_COLOURS:
        raise ValueError(f"no pin colour called {colour!r}; there is " + ", ".join(sorted(PIN_COLOURS)))
    if icon not in MARKER_ICONS:
        raise ValueError(f"no outline for {icon!r}; this page draws " + ", ".join(sorted(MARKER_ICONS)))
    fill = PIN_COLOURS[colour]
    box, path = MARKER_ICONS[icon]
    glyph = f"<svg x='{PIN_WIDTH / 2 - 6.5:.1f}' y='7' width='13' height='13' viewBox='{box}'><path fill='white' d='{path}'/></svg>"
    return (
        f'<span class="trails-pin"><svg width="{PIN_WIDTH}" height="{PIN_HEIGHT}" '
        f'viewBox="0 0 {PIN_WIDTH} {PIN_HEIGHT}" xmlns="http://www.w3.org/2000/svg">'
        f'<path fill="{fill}" d="{PIN_SHAPE}"/>{glyph}</svg></span>'
    )


class _TileRetention(MacroElement):
    """Keep loaded children across a three-level zoom out, using Leaflet's pruning."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "tile_retention.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self) -> None:
        """Initialize the retention override."""
        super().__init__()
        self._name = "TileRetention"


class _TileRing(MacroElement):
    """Load one tile beyond each viewport edge at the layer's tile scale."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "tile_ring.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self) -> None:
        """Initialize the bounds override."""
        super().__init__()
        self._name = "TileRing"


class _PinchDraw(MacroElement):
    """Draw canvas geometry during a pinch with constant screen-sized strokes."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "pinch_draw.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self) -> None:
        """Initialize the canvas zoom override."""
        super().__init__()
        self._name = "PinchDraw"


class _TileStart(MacroElement):
    """Wait briefly for control before adding the pack-backed tile layers."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "tile_start.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self) -> None:
        """Initialize the first-control gate."""
        super().__init__()
        self._name = "TileStart"


class _PinSize(MacroElement):
    """How large the pins are drawn, which depends on how far out the reader is.

    **Reported: they are too big, and most of all zoomed out.** 198 of them at
    35 x 45 stand over the terrain at the zoom this park opens at, which is the
    one view where a reader is looking at the ground rather than at a hut.

    Scaled rather than resized, and about the **tip**: Leaflet positions the icon
    element with a transform of its own, so the scale goes on an element inside
    it, and ``transform-origin: bottom center`` keeps the point of the pin on the
    position it marks whatever the scale is.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "pin_size.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self) -> None:
        """Initialize the sizing."""
        super().__init__()
        self._name = "PinSize"


class _ScaleZoom(MacroElement):
    """The scale bar itself, and a second line under it saying which zoom this is.

    **It owns the bar because of one option.** folium's ``control_scale=True``
    emits a bare ``L.control.scale()``, and a bare Leaflet scale draws two bars,
    metric and imperial. Stacked in that corner with this line under them, the
    three read as the same control drawn twice -- reported from a phone in
    exactly those words -- and the mile is for nobody who walks in Norway.

    **Because the offline chooser asks for one.** A reader picking *z16* out of
    a list has no way to see what z16 looks like unless the map says what it is
    showing, and a number you never meet again is a number you cannot choose
    between. It also makes a screenshot readable back to a zoom, which every
    report about this page has so far had to reconstruct from the bar.

    The pairing is exact, and worth stating because it is arithmetic and not a
    lookup: ``L.control.scale`` uses ``maxWidth: 100`` and rounds down to the
    nearest 1, 2, 3 or 5 times a power of ten, and the ground resolution is
    ``156543.03392 * cos(lat) / 2 ** z`` -- 64,917 / 2^z at this latitude. So the
    bar reads 500 m at z13, 300 m at z14, 100 m at z15, 50 m at z16, 30 m at z17
    and 20 m at z18, and none of those readings is shared with another zoom.

    It is drawn in the scale control's own box rather than beside it, and takes
    no measuring bar: a line with a rule under it in that corner claims to be a
    distance, and this one is not. Layer additions and removals redraw it only
    for tile layers: scanning the map for each path made construction quadratic.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "scale_zoom.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self) -> None:
        """Initialize the zoom line."""
        super().__init__()
        self._name = "ScaleZoom"


class _ServiceWorker(MacroElement):
    """Register the worker, and say when it is holding a newer map.

    **Only where there is one to register.** A worker needs a secure origin, so
    a page opened off the disk gets none -- which is also why the suite has to
    serve the built page over HTTP to drive any of this, and does.

    The reader is told when the worker has fetched a newer map, because
    stale-first means the fix they are waiting for arrives one visit late. The
    line is a plain one in the corner with a way to dismiss it, not a sheet: a
    panel that opens itself is a panel that interrupts.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "service_worker.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, companions: Companions = ROOT) -> None:
        """Hold the names.

        Args:
            companions: Which worker to register, and at what scope. The first
                map's worker registers at the default scope, which is the
                script's own directory; a later map's asks for its own page as
                the scope, so the two do not answer for each other.
        """
        super().__init__()
        self._name = "ServiceWorker"
        self.worker = companions.worker
        self.scope_arg = "" if companions.scope == "./" else f", {{scope: '{companions.scope}'}}"


class _Inlined(Element):
    """A third party's script or stylesheet, written into the page itself.

    The body goes through a variable rather than into the template, because a
    minified library is full of ``{{`` and ``{%`` by accident and Jinja would
    read them as its own.

    **An `Element` and not a `MacroElement`, which cost a build.** A macro's
    `header` block is rendered with the map's *children*, and folium adds its own
    `<script src>` links while rendering the map itself -- so an inlined Leaflet
    landed **after** the script that uses it and the page came up with
    `L is not defined`. Added straight to the figure's header instead, it is
    first because nothing has been added there yet.
    """

    _template = Template("""{{ this.body }}""")

    def __init__(self, body: str, css: bool, name: str) -> None:
        """Hold the file.

        **Fenced by a comment naming it**, for two reasons. A reader looking at
        the source can see where somebody else's code begins and ends, which is
        the least a page owes a library it carries; and a check asking what
        *this* page says can cut them out. Both were wanted the moment Leaflet
        went inline: its own source carries `http://` addresses and defines a
        `disableScrollPropagation`, and two tests about this page's behaviour
        began reading Leaflet's instead.

        Args:
            body: The file's text.
            css: Whether it is a stylesheet rather than a script.
            name: What the file is, for the fence.
        """
        super().__init__()
        wrapped = ("<style>" + body + "</style>") if css else ("<script>" + body + "</script>")
        self.body = f"<!-- vendored:{name} -->\n{wrapped}\n<!-- /vendored:{name} -->"


class _Theme(MacroElement):
    """The colours every panel on this page is drawn from, in two sets.

    **The tiles stay as they are and only the furniture turns.** A Kartverket
    sheet arrives as a finished raster and cannot be darkened without lying
    about the terrain: an inverted slope is not a dark slope, it is a wrong one.
    So dark here means dark panels over a light map, which is the state a reader
    wants at dusk with the phone in their hand and is the only one honestly
    available.

    **Named colours and not a second set of literals.** Every panel on this page
    carried its colours as inline styles -- some fifty of them, `#333` and `#555`
    and `#666` scattered across six controls -- and an inline style beats a
    stylesheet, so nothing outside the element could ever have changed one. They
    are `var(--trails-...)` now, which an inline style resolves against whatever
    the document says, and this says it once.

    **Three blocks and not two**, for the same reason a web page needs three: an
    explicit choice stamps ``data-theme`` on the root, and the default setting
    stamps nothing at all -- so ``prefers-color-scheme`` alone separates light
    from dark for most readers, while a stamped choice has to beat it in both
    directions.

    **And the switch that uses them lives here too**, as ``window.trailsTheme``
    -- in the head, so the stamp is on the root before the first paint rather
    than corrected in front of the reader. The chrome's *Theme* panel is a view
    onto this and holds nothing of its own; anything else that needs to know
    listens for the ``trails:theme`` event, which is how the elevation curve --
    the one thing here painted with attributes rather than CSS -- redraws when
    the reader turns the page over.

    **What does not turn: the data.** The four gradient bands, the route's own
    black and the colours the legend gives each source are statements about the
    ground, not furniture. Green meaning *gentle* in the morning and something
    else at night would be the drawing lying to keep up with the panels.
    """

    _template = Template(
        """
        {% macro header(this, kwargs) %}
        <style>
        /* The slope classes overprint the sheet rather than cover it: black
           lettering multiplied by any colour is still black. The layer's
           own alpha keeps the darkening partial -- see SlopeTiles. */
        .leaflet-layer.trails-slope-tiles, .leaflet-layer.trails-vegetation-tiles,
        .leaflet-layer.trails-forest-tiles, .leaflet-layer.trails-mire-tiles { mix-blend-mode: multiply; }
        :root {
            color-scheme: light;
            --trails-panel: rgba(255,255,255,0.94);
            --trails-solid: #ffffff;
            --trails-sunk: #f2f4f4;
            --trails-edge: #999999;
            --trails-rule: #dddddd;
            --trails-rule-soft: #eeeeee;
            --trails-ink: #1d282c;
            --trails-ink-2: #333333;
            --trails-ink-3: #555555;
            --trails-ink-4: #777777;
            --trails-ink-5: #8a9a9e;
            --trails-accent: #0d47a1;
            --trails-on-accent: #ffffff;
            --trails-strong: #111111;
            --trails-on-strong: #ffffff;
            --trails-warn: #8a5000;
            --trails-grip: #c4c4c4;
            --trails-grip-held: #8a8a8a;
        }
        @media (prefers-color-scheme: dark) {
            :root:not([data-theme="light"]) {
                color-scheme: dark;
                --trails-panel: rgba(20,25,28,0.97);
                --trails-solid: #1b2124;
                --trails-sunk: #232a2d;
                --trails-edge: #4b5457;
                --trails-rule: #333c3f;
                --trails-rule-soft: #2b3235;
                --trails-ink: #e9e6de;
                --trails-ink-2: #d5dad9;
                --trails-ink-3: #b4bcbc;
                --trails-ink-4: #96a0a1;
                --trails-ink-5: #7f8a8c;
                --trails-accent: #7fb0f0;
                --trails-on-accent: #10192a;
                --trails-strong: #e9e6de;
                --trails-on-strong: #14191b;
                --trails-warn: #e6a75e;
                --trails-grip: #414a4d;
                --trails-grip-held: #6b7679;
            }
        }
        :root[data-theme="dark"] {
            color-scheme: dark;
            --trails-panel: rgba(20,25,28,0.97);
            --trails-solid: #1b2124;
            --trails-sunk: #232a2d;
            --trails-edge: #4b5457;
            --trails-rule: #333c3f;
            --trails-rule-soft: #2b3235;
            --trails-ink: #e9e6de;
            --trails-ink-2: #d5dad9;
            --trails-ink-3: #b4bcbc;
            --trails-ink-4: #96a0a1;
            --trails-ink-5: #7f8a8c;
            --trails-accent: #7fb0f0;
            --trails-on-accent: #10192a;
            --trails-strong: #e9e6de;
            --trails-on-strong: #14191b;
            --trails-warn: #e6a75e;
            --trails-grip: #414a4d;
            --trails-grip-held: #6b7679;
        }

        /* Leaflet's own furniture, which arrives from its stylesheet already
           painted. `!important` because that is a third party's rule and this
           is the page overriding it -- the one place where it is the honest
           tool rather than a shortcut. */
        .leaflet-bar, .leaflet-bar a, .leaflet-touch .leaflet-bar a {
            background-color: var(--trails-solid) !important;
            color: var(--trails-ink) !important;
            border-bottom-color: var(--trails-rule) !important;
        }
        .leaflet-bar { border-color: var(--trails-edge) !important; }
        .leaflet-bar a:hover { background-color: var(--trails-sunk) !important; }
        /* **What Bootstrap was actually providing, in three rules.** Two
           stylesheets and a script came to 288 kB and one whole host for a
           border-box reset, a font stack and the attribution's size -- measured
           by removing each from a built page on its own and driving it. */
        *, *::before, *::after { box-sizing: border-box; }
        body { margin: 0; font-family: system-ui, -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; }
        .leaflet-control-attribution {
            background: var(--trails-panel) !important;
            color: var(--trails-ink-4) !important;
            /* 10 px and a 14 px line, which is what the glyphicons sheet was
               holding it at. The panel above leaves it 16 px of map; a credit
               that grew to 22 would be taking some of that back. */
            font-size: 10px !important;
            line-height: 14px !important;
        }
        .leaflet-control-attribution a { color: var(--trails-accent) !important; }
        /* **The page is as tall as the screen, not as tall as the safe part of
           it.** folium writes `html, body { height: 100% }`, and with
           `viewport-fit=cover` on iOS that resolves to the viewport *inside* the
           insets -- so the map stopped above the home indicator and what showed
           there was the browser's own background. Reported as a black band under
           the map, with the scale sitting on top of it.

           `dvh` is the viewport including the insets. A browser that does not
           know the unit drops this declaration and keeps folium's, which is the
           behaviour that was correct before any of this. */
        html, body { width: 100dvw; height: 100dvh; }
        /* **The strip the phone keeps for itself.** With `viewport-fit=cover` the
           map is drawn to the physical edges, which is what the head asked for --
           and the home indicator then sits on whatever is in the bottom corners.
           Reported from an installed app: the scale bar's second line was cut
           off, and worse in life than in a screenshot, because a screenshot does
           not draw the indicator.

           On the four corner containers rather than on each control, so anything
           Leaflet or this page puts in a corner is covered by having been put
           there. Zero everywhere but a phone, so nothing else moves. */
        .leaflet-top { padding-top: env(safe-area-inset-top); }
        .leaflet-bottom { padding-bottom: env(safe-area-inset-bottom); }
        .leaflet-left { padding-left: env(safe-area-inset-left); }
        .leaflet-right { padding-right: env(safe-area-inset-right); }
        /* The rail, the burger and every panel are children of `.trails-chrome`,
           which is itself held inside the safe area -- so none of them needs a
           rule here, and one would be the inset applied twice. */
        .leaflet-control-scale-line {
            background: var(--trails-panel) !important;
            color: var(--trails-ink-2) !important;
            border-color: var(--trails-ink-4) !important;
            /* **Leaflet draws these figures twice.** Its own rule is
               `text-shadow: 1px 1px #fff` -- a white copy a pixel down and
               right, which is how you keep a number legible over a *translucent*
               box with the map showing through it. This box is not translucent:
               the rule above gives it the panel's own background, so the second
               copy has nothing to do but smear the first. Reported from a phone
               as `20 km` looking blurred, "doubled about half a millimetre
               apart", which is exactly what it is.

               It was wrong in both sets and worse in one. Dark ink under a white
               ghost is a smudge; the light ink of the dark theme under a white
               ghost is very nearly a double exposure. */
            text-shadow: none !important;
        }
        /* **The same box, and deliberately not the same line.** Leaflet's scale
           lines carry a rule along the bottom that *is* the measured distance;
           this one says a zoom, so it gets the box and no bar. Anything else in
           that corner with a rule under it is claiming to be a length. */
        .trails-grayscale { filter: grayscale(1); }
        .trails-scale-zoom {
            padding: 2px 5px 1px;
            font-size: 11px;
            line-height: 1.1;
            border: 1px solid var(--trails-ink-4);
            border-top: none;
            background: var(--trails-panel);
            color: var(--trails-ink-3);
            white-space: nowrap;
            font-variant-numeric: tabular-nums;
        }
        .leaflet-popup-content-wrapper, .leaflet-popup-tip {
            background: var(--trails-solid) !important;
            color: var(--trails-ink) !important;
        }
        .leaflet-container a { color: var(--trails-accent); }

        /* **The panels say their own ink.** Not one of them set a `color`: they
           inherited the document's black, which is right on a white panel and is
           1.4:1 on a dark one — measured, and the reason this rule exists. Said
           on the panels themselves rather than on the map container, because
           what a text label on the terrain is coloured is the label's business
           and not the furniture's. */
        .trails-profile-panel, .trails-plan-control, .trails-legend, .trails-search,
        .trails-basemap, .trails-chrome, .leaflet-popup-content {
            color: var(--trails-ink);
        }
        {{ this.icons }}
        /* **Scaled about the tip.** Leaflet puts its own transform on the icon
           element to place it, so the scale lives on a span inside, and the
           point of the pin stays on the position it marks at every zoom. */
        /* `line-height: 0`, because an inline `<svg>` in a block gets a
           descender's worth of space under it -- measured, the span came out
           30 px tall around a 36 px drawing at 0.7, which scaled about the
           bottom would lift the pin's tip off the position it marks. */
        .trails-pin { display: block; line-height: 0; transform-origin: bottom center; transform: scale(var(--trails-pin, 1)); }
        .trails-pin svg { display: block; }
        </style>
        <script>
"""
        + files("trails.visualization").joinpath("js", "theme.js").read_text(encoding="utf-8")
        + """        </script>
        {% endmacro %}
    """
    )

    def __init__(self) -> None:
        """Initialize the theme."""
        super().__init__()
        self._name = "Theme"
        # **The marker glyphs, drawn from their outlines rather than from a
        # webfont.** Written here because this is the one stylesheet every page
        # gets, and built from :data:`MARKER_ICONS` rather than written out a
        # second time: one derivation, and a name that is wrong is wrong once.
        rules = [
            '.awesome-marker i[class*="fa-"] { width: 14px; height: 14px; background-repeat: no-repeat;'
            " background-position: center; background-size: contain; }"
        ]
        for name, (box, path) in MARKER_ICONS.items():
            drawing = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='{box}'><path fill='white' d='{path}'/></svg>"
            encoded = drawing.replace("<", "%3C").replace(">", "%3E").replace("#", "%23")
            rules.append(f'.awesome-marker i.fa-{name} {{ background-image: url("data:image/svg+xml,{encoded}"); }}')
        self.icons = "\n        ".join(rules)


class BaseMap(Enum):
    """Available base layers.

    ``KARTVERKET_TOPO`` is the Norwegian national topographic map and is the
    most useful backdrop for hiking.

    ``OPENSTREETMAP`` only works when the page is served over http(s):
    OSM's tile usage policy requires a Referer header, which browsers omit for
    ``file://`` URLs, so every tile comes back as an "Access blocked" image.
    """

    KARTVERKET_TOPO = "kartverket_topo"
    KARTVERKET_GRAYSCALE = "kartverket_grayscale"
    #: Lantmäteriet's *Topografisk webbkarta*, the colour sheet, copied out of
    #: its open download into our own bucket (analysis/docs/abisko-decisions.md
    #: §3, §6.1). Root-relative, so the page names no host.
    LANTMATERIET_TOPO = "lantmateriet_topo"
    LANTMATERIET_TOPO_MALINGSBO_KLOTEN = "lantmateriet_topo_malingsbo_kloten"
    OPENSTREETMAP = "openstreetmap"


#: A missing tile shows the map's background, without another network request.
_ERROR_TILE_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="

_KARTVERKET_ATTRIBUTION = '&copy; <a href="https://www.kartverket.no/">Kartverket</a>'

_LANTMATERIET_ATTRIBUTION = '&copy; <a href="https://www.lantmateriet.se/">Lantmäteriet</a>'

#: Each base layer's tiles, credit and name, and the :data:`PROVIDERS` key its
#: tiles come from -- ``None`` for one the offline panel does not keep.
_BASE_LAYERS: dict[BaseMap, dict[str, str | None]] = {
    BaseMap.KARTVERKET_TOPO: {
        "tiles": "/tiles/kartverket/topo/1/{z}/{x}/{y}.png",
        "attr": _KARTVERKET_ATTRIBUTION,
        "name": "Kartverket Topo",
        "provider": "kartverket",
    },
    BaseMap.KARTVERKET_GRAYSCALE: {
        "tiles": "/tiles/kartverket/topo/1/{z}/{x}/{y}.png",
        "attr": _KARTVERKET_ATTRIBUTION,
        "name": "Kartverket Grayscale",
        "provider": "kartverket",
    },
    BaseMap.LANTMATERIET_TOPO: {
        "tiles": "/tiles/lantmateriet/topowebb/1/{z}/{x}/{y}.png",
        "attr": _LANTMATERIET_ATTRIBUTION,
        "name": "Lantmäteriet Topo",
        "provider": "lantmateriet",
    },
    BaseMap.OPENSTREETMAP: {
        "tiles": "OpenStreetMap",
        "attr": "&copy; OpenStreetMap contributors",
        "name": "OpenStreetMap",
        "provider": None,
    },
    BaseMap.LANTMATERIET_TOPO_MALINGSBO_KLOTEN: {
        "tiles": "/tiles/lantmateriet-malingsbo-kloten/topowebb/1/{z}/{x}/{y}.png",
        "attr": _LANTMATERIET_ATTRIBUTION,
        "name": "Lantmäteriet Topo",
        "provider": "lantmateriet-malingsbo-kloten",
    },
}


def tile_tree_version(key: str, version: int) -> Provider:
    """Point a provider, and every base layer drawn on it, at a version of its tree.

    **A new stand of the tiles is a new version segment, never a changed
    object** (decisions §6.1): the copy chooses the segment from the file's
    date and the build asks which is complete, then calls this so the page,
    its worker and the offline panel all name that one.

    Args:
        key: The provider, ``lantmateriet``
        version: The version directory the page should draw

    Returns:
        The provider as it now stands in :data:`PROVIDERS`

    Raises:
        ValueError: If the provider's prefix carries no version segment
    """
    provider = PROVIDERS[key]
    if not re.search(r"/\d+/$", provider.tiles):
        raise ValueError(f"{key}'s tiles at {provider.tiles} carry no version segment to change")
    prefix = re.sub(r"/\d+/$", f"/{version}/", provider.tiles)
    PROVIDERS[key] = dataclasses.replace(provider, tiles=prefix)
    for layer in _BASE_LAYERS.values():
        if layer["provider"] == key:
            layer["tiles"] = f"{prefix}{{z}}/{{x}}/{{y}}.png"
    return PROVIDERS[key]


def provider_of(base: BaseMap) -> Provider | None:
    """Whose tiles a base layer draws.

    Args:
        base: The layer.

    Returns:
        The provider, or None for a layer no provider table describes.
    """
    key = _BASE_LAYERS[base]["provider"]
    return None if key is None else PROVIDERS[key]


def provider_of_map(fmap: folium.Map) -> Provider:
    """The provider :func:`create_map` built a map on.

    Args:
        fmap: The map.

    Returns:
        The provider of its primary base layer.

    Raises:
        KeyError: If the map was not made by :func:`create_map`, or its base
            layer has no provider entry.
    """
    provider = getattr(fmap, MAP_PROVIDER_ATTR, None)
    if provider is None:
        raise KeyError("the map records no tile provider — its base layer is one the offline panel cannot keep tiles from")
    assert isinstance(provider, Provider)
    return provider


def companions_of_map(fmap: folium.Map) -> Companions:
    """The names :func:`create_map` gave a map's companions.

    Args:
        fmap: The map.

    Returns:
        The set, :data:`ROOT` for a map made without one.
    """
    companions = getattr(fmap, MAP_COMPANIONS_ATTR, ROOT)
    assert isinstance(companions, Companions)
    return companions


#: How far from a line's paint a finger may land and still count as having hit
#: it, in CSS pixels.
#:
#: **Leaflet's own answer is half the stroke, and that is the whole defect.**
#: The map draws into a canvas, so hit-testing is Leaflet's arithmetic rather
#: than the browser's, and `Path._clickTolerance` is `weight / 2` plus the
#: renderer's `tolerance` option — which is `0` by default. A 3 px line has to
#: be hit **within 1.5 px of its centre**. Read in leaflet 1.9.4, not inferred:
#: a fingertip is nowhere near that accurate, and being off by two pixels is
#: indistinguishable from having tapped empty ground.
#:
#: The number itself is a judgement rather than a measurement. With the paint's
#: own half-width on top it makes a corridor about 27 px wide where there were
#: 3, which is close to what the eye reads as *on that line* — and it is only
#: safe that wide because the nearest line wins rather than the topmost one.
#: See :class:`_TouchReach`.
FINGER_PX = 12

#: How far a finger may roll between press and release and still be a tap,
#: in CSS pixels, as ``|dx| + |dy|``.
#:
#: **The second half of the same defect, and the half that makes a tap fail
#: rather than land somewhere else.** `Draggable.options.clickTolerance` is 3,
#: and once `|dx| + |dy|` reaches it the map is dragging: `Canvas._onClick`
#: then asks `_draggableMoved` and throws the hit away entirely. So a finger
#: that rolls two pixels while pressing does not select the line it is resting
#: on — it selects nothing at all, which is exactly "you have to tap several
#: times". A mouse does not roll and keeps Leaflet's 3.
#:
#: Raising it costs a jump: when the drag finally starts it applies the whole
#: offset at once, so the map moves ten pixels rather than three at the moment
#: a pan begins. That is the trade, taken deliberately — a pan that starts a
#: touch late is a pan; a tap that is eaten is a reader tapping again.
TAP_SLOP_PX = 10


class _TouchReach(MacroElement):
    """What counts as a finger having hit a line, and as having held still.

    **Added before any layer, because Leaflet bakes the reach into a bounding
    box.** `Path._updateBounds` pads `_pxBounds` with whatever
    `_clickTolerance()` said at projection time, and `_containsPoint` refuses
    anything outside that box before it measures a single segment. Nothing here
    relies on that padding — the hit test below carries its own — but the
    ordering is what keeps the two answers the same, and `create_map` adds this
    where `_PopupText` is added and for the same reason.

    Three things, all of them one cause seen from different sides:

    - **Leaflet's drag threshold**, raised for a finger. Nothing else changes:
      a mouse keeps the 3 px it has always had, and a pointer that stops being
      coarse gets it back.
    - **A halo around every drawn line**, :data:`FINGER_PX` wide, measured from
      the paint rather than from the centre so a 4 px line and a 2 px line both
      reach the same distance beyond what a reader can see.
    - **The nearest line wins, not the topmost.** Leaflet's `_onClick` keeps
      the *last* layer in draw order that contains the point, which is right at
      1.5 px and wrong at 13: where six sources run through one valley a tap
      would land on whichever was drawn last regardless of which line it was
      aimed at. Worse, `_ClickHighlight` calls `bringToFront` on the route it
      selects, so the last selection would go on winning every nearby tap
      afterwards. Ranking by distance makes the widening safe; exact ties still
      go to the later layer, which is what keeps "UT.no last, therefore on top"
      true where two sources draw the same line.

    Only under a coarse pointer. Under a fine one Leaflet's own handler runs
    untouched, so nothing about a mouse — including which line a hover names —
    moves at all.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "touch_reach.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, finger_px: float, tap_slop_px: float) -> None:
        """Widen what a finger has to hit.

        Args:
            finger_px: Halo around a line's paint that still counts as a hit
            tap_slop_px: How far a finger may roll and still be a tap
        """
        super().__init__()
        self._name = "TouchReach"
        self.finger_px = finger_px
        self.tap_slop_px = tap_slop_px


def create_map(
    bounds: Bounds | None = None,
    center: tuple[float, float] | None = None,
    zoom: int = 10,
    base: BaseMap = BaseMap.KARTVERKET_TOPO,
    # No second sheet unless one is asked for. Kartverket's grey one stood here
    # from the first build and neither map offers it now (§6.10): a default that
    # puts a sheet in the picker is a default that decides what the picker is for.
    extra_bases: tuple[BaseMap, ...] = (),
    title: str | None = None,
    companions: Companions = ROOT,
) -> folium.Map:
    """Create a Folium map focused on an area.

    Args:
        bounds: (min_lon, min_lat, max_lon, max_lat) to fit the view to
        center: (lat, lon) fallback when no bounds are given
        zoom: Initial zoom level, used only when fitting to bounds is skipped
        base: Base layer shown by default
        extra_bases: Additional base layers offered in the layer control. They
            are registered but not displayed until selected, otherwise Leaflet
            stacks them all and the last one wins.
        title: What the page and an installed copy of it are called. Folium
            writes no title at all, so without one the tab and a home-screen
            icon are both labelled with the URL.
        companions: The names this map's worker, manifest, icons, database and
            caches go by. :data:`ROOT` for the first map; :meth:`Companions.named`
            for any other on the same origin.

    Returns:
        Folium map with base layers attached; call :func:`add_legend` when done
        adding overlays, which is what lists and switches them.

    Raises:
        ValueError: If neither bounds nor center is given
    """
    if bounds is None and center is None:
        raise ValueError("Either bounds or center must be provided")
    # None for a base no provider table describes (OpenStreetMap); such a map
    # can be drawn but not given the offline panel, which `add_chrome` says.
    provider = provider_of(base)

    if center is None:
        assert bounds is not None
        min_lon, min_lat, max_lon, max_lat = bounds
        center = ((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)

    # Base layers are attached explicitly rather than via Map(tiles=...), which
    # would label the layer control with the raw tile URL instead of the name.
    # **Drawn into a canvas rather than into twelve thousand SVG elements.**
    # Leaflet writes a `d` attribute per path on every move, and with 11,589 of
    # them that write is the largest single cost of a pan. Measured on a built
    # page at 390 x 844 with a coarse pointer, the median of six `setView`
    # steps: **51 ms with SVG against 34 with canvas**, a third off every
    # gesture, and 12,472 DOM elements down to 882.
    #
    # **The saving is flat, not proportional**, which is worth knowing before
    # anybody spends it: at four times the drawn detail the same measurement
    # reads 91 ms against 74. Canvas removes the DOM write; the projection and
    # the per-zoom simplification are unchanged and grow with the vertices.
    # `control_scale=False`, and the bar is added by `_ScaleZoom` instead. folium
    # emits a bare `L.control.scale()`, and Leaflet's bare scale draws **two**
    # bars -- metric and imperial, one above the other. In that corner, under a
    # third line saying the zoom, it reads as the same control drawn twice; and
    # the mile is for nobody who walks in Norway. See `_ScaleZoom`.
    fmap = folium.Map(location=list(center), zoom_start=zoom, tiles=None, control_scale=False, prefer_canvas=True)
    # **Three of folium's defaults, dropped after being measured rather than
    # after being reasoned about.** They cost 288 kB uncompressed and, between
    # them, a whole host: `netdna.bootstrapcdn.com` served one file and nothing
    # else. Each was taken out of a built page on its own and the page driven:
    #
    # - `bootstrap.min.css` (194,901 B) -- **no measurable effect at all**, once
    #   the two rules it was really providing are said here: the border-box
    #   reset, without which the zoom control measures 65 px instead of 64, and
    #   a font family for the document outside the map.
    # - `bootstrap.bundle.min.js` (80,496 B) -- **no measurable effect.** Nothing
    #   on this page is a Bootstrap component.
    # - `bootstrap-glyphicons.css` (13,018 B) -- its one effect is the
    #   attribution's size, 10 px against 16 without it. `glyphicon` appears
    #   once in the built page and that occurrence is this link; the markers ask
    #   for `prefix="fa"`.
    #
    # What stays is what the map is made of: Leaflet, jQuery (folium builds
    # every popup with it) and awesome-markers with the font its icons come from.
    fmap.default_js = [(name, url) for name, url in fmap.default_js if "bootstrap" not in name and name != "awesome_markers"]
    dropped = {"bootstrap_css", "glyphicons_css", "awesome_markers_font_css", "awesome_markers_css", "awesome_rotate_css"}
    fmap.default_css = [(name, url) for name, url in fmap.default_css if name not in dropped]
    # **And what is left of them goes into the page rather than over a wire.**
    # Two whole hosts fall away with these four -- `cdn.jsdelivr.net` and
    # `code.jquery.com` -- which on a slow link is worth more than the 80 kB
    # they add to the stream: a handshake cannot be pipelined and a download can.
    # awesome-markers stays linked for now, because its stylesheet reaches for
    # four sprite images by relative path and inlining it would break them.
    inline = {"leaflet", "jquery"}
    fmap.default_js, remote_js = (
        [(name, url) for name, url in fmap.default_js if name not in inline],
        [(name, url) for name, url in fmap.default_js if name in inline],
    )
    fmap.default_css, remote_css = (
        [(name, url) for name, url in fmap.default_css if name != "leaflet_css"],
        [(name, url) for name, url in fmap.default_css if name == "leaflet_css"],
    )
    # `get_root` is typed as returning any `Element`; for a map it is the
    # `Figure` that owns the document, and the header is where a page's scripts
    # and stylesheets go. Asserted rather than cast, so a folium that ever
    # returns something else says so here instead of failing in a browser.
    figure = fmap.get_root()
    assert isinstance(figure, Figure), "a map's root should be the figure that carries the document"
    header = figure.header
    for name, url in remote_js:
        header.add_child(_Inlined(vendored(url), css=False, name=name), name=name)
    for name, url in remote_css:
        header.add_child(_Inlined(vendored(url), css=True, name=name), name=name)
    if title is not None:
        header.add_child(_Head(title, companions), name="head")

    _TileRetention().add_to(fmap)
    _TileRing().add_to(fmap)
    _PinchDraw().add_to(fmap)
    if provider is not None:
        _TileStart().add_to(fmap)

    for index, source in enumerate((base, *(extra for extra in extra_bases if extra is not base))):
        layer = _BASE_LAYERS[source]
        own = provider_of(source)
        folium.TileLayer(
            tiles=layer["tiles"] or "",
            attr=layer["attr"] or "",
            name=layer["name"] or "",
            overlay=False,
            control=True,
            show=index == 0,
            retain_ground=True,
            # **Held to the source's finest level.** Leaflet asks for the real
            # tile at every zoom up to `maxNativeZoom` and scales past it, so a
            # sheet that ends at z17 is drawn magnified at z18 rather than
            # requested and answered 404.
            max_zoom=18 if provider is not None else None,
            max_native_zoom=own.top if own is not None else None,
            # **Asked for across origins, so a cache can hold them plainly.**
            # An `<img>` without this fetches no-cors and the answer is opaque:
            # storable, unreadable, and charged against the origin's quota at a
            # padded size rather than its own. Kartverket answers
            # `access-control-allow-origin: *` -- measured, not assumed.
            cross_origin=True,
            class_name="trails-grayscale" if source is BaseMap.KARTVERKET_GRAYSCALE else "",
            update_when_zooming=False,
            update_when_idle=False,
            keep_buffer=4,
            error_tile_url=_ERROR_TILE_URL,
            # The same index.json box as the overlays, for both countries.
            bounds=[[own.extent[1], own.extent[0]], [own.extent[3], own.extent[2]]] if own is not None else None,
        ).add_to(fmap)

    # **The relief shadow, where the provider has one.** It is a tile layer like
    # the base and sits directly on top of it, so everything this map draws
    # itself -- paths, markers, the plan -- is drawn over it and keeps its
    # colour, while the ground beneath the contours reads as terrain
    # (analysis/docs/abisko-decisions.md §6.6).
    #
    # **It credits the same body the sheet under it does, and that draws once.**
    # The shadow is cut from Lantmäteriet's height model and laid over
    # Lantmäteriet's map, so the honest credit is the one already there --
    # and Leaflet keeps its attributions in an object keyed by the string, so
    # naming it twice adds a count rather than a second line. Folium refuses an
    # empty attribution outright, which is the right refusal: a tile layer
    # nobody is credited for is how a licence gets dropped by accident.
    if provider is not None and provider.shade is not None:
        shade = folium.TileLayer(
            tiles=provider.shade.template,
            attr=_BASE_LAYERS[base]["attr"] or "",
            name="Relief",
            overlay=True,
            # The legend is this map's layer control and is given the row
            # explicitly, by the caller that knows what to call it.
            control=False,
            show=True,
            opacity=provider.shade.opacity,
            max_zoom=18,
            max_native_zoom=provider.shade.top,
            cross_origin=True,
            update_when_zooming=False,
            update_when_idle=False,
            keep_buffer=4,
            error_tile_url=_ERROR_TILE_URL,
            # **Named, so the offline panel does not take it for the base map.**
            # That panel finds the sheet by walking the map's layers for the
            # first one with tiles, and a reader who switches the base off and on
            # again puts it back *after* this one -- at which point the download
            # would fetch the shadow and call it the map.
            trails_shade=True,
            # Above every base layer whatever order they are switched in: a
            # reader changing the sheet would otherwise draw the new base over
            # the shadow, and Leaflet stacks equal z-indices by insertion.
            z_index=250,
            # **Held to the box the tree was cut to.** Outside it every tile is
            # a 404, and the offline panel reads a run of those as the
            # connection giving out (§8.2) -- so the layer is told where the
            # ground ends rather than finding out one refusal at a time.
            bounds=[[provider.extent[1], provider.extent[0]], [provider.extent[3], provider.extent[2]]],
        )
        shade.add_to(fmap)
        setattr(fmap, MAP_SHADE_ATTR, shade)

    # **The slope classes, where the provider has them.** Tiles like the relief
    # and directly over it, so a class keeps its hue and the shadow only
    # darkens it; off until the reader asks, because it answers a question
    # off the paths and an eighth of the ground coloured is a lot of colour
    # for a reader following one (§6.7).
    if provider is not None and provider.slope is not None:
        slope = folium.TileLayer(
            tiles=provider.slope.template,
            attr=_BASE_LAYERS[base]["attr"] or "",
            name="Slope",
            overlay=True,
            control=False,
            show=False,
            # Full strength: the alpha is in the palette, chosen on the mockup.
            opacity=1.0,
            max_zoom=18,
            max_native_zoom=provider.slope.top,
            cross_origin=True,
            update_when_zooming=False,
            update_when_idle=False,
            keep_buffer=4,
            error_tile_url=_ERROR_TILE_URL,
            # Named for the same reason the relief is: the offline panel must
            # never take it for the sheet, and the drive counts it apart.
            trails_slope=True,
            # **Multiplied over the sheet, not laid on it.** The class is
            # `_Theme`'s `mix-blend-mode: multiply` by this class name, so the
            # lettering under a class keeps its black -- opaque, the names
            # went to 3:1 against their ground and were the first thing lost.
            class_name="trails-slope-tiles",
            # Over the relief, whatever order they are switched in.
            z_index=260,
            bounds=[[provider.extent[1], provider.extent[0]], [provider.extent[3], provider.extent[2]]],
        )
        slope.add_to(fmap)
        setattr(fmap, MAP_SLOPE_ATTR, slope)

    # **What stands on the ground, where the map's country has a laser survey
    # to say.** Two layers cut the same way as the slope classes and drawn the
    # same way -- multiplied, off until asked -- one for the vegetation between
    # knee and head height and one for the trees above it, switched apart
    # because they answer different questions (§6.11).
    if provider is not None and provider.vegetation is not None:
        vegetation = folium.TileLayer(
            tiles=provider.vegetation.template,
            attr=_BASE_LAYERS[base]["attr"] or "",
            name="Vegetation",
            overlay=True,
            control=False,
            show=False,
            opacity=1.0,
            max_zoom=18,
            max_native_zoom=provider.vegetation.top,
            cross_origin=True,
            update_when_zooming=False,
            update_when_idle=False,
            keep_buffer=4,
            error_tile_url=_ERROR_TILE_URL,
            trails_vegetation=True,
            class_name="trails-vegetation-tiles",
            z_index=262,
            bounds=[[provider.extent[1], provider.extent[0]], [provider.extent[3], provider.extent[2]]],
        )
        vegetation.add_to(fmap)
        setattr(fmap, MAP_VEGETATION_ATTR, vegetation)
    if provider is not None and provider.forest is not None:
        forest = folium.TileLayer(
            tiles=provider.forest.template,
            attr=_BASE_LAYERS[base]["attr"] or "",
            name="Forest",
            overlay=True,
            control=False,
            show=False,
            opacity=1.0,
            max_zoom=18,
            max_native_zoom=provider.forest.top,
            cross_origin=True,
            update_when_zooming=False,
            update_when_idle=False,
            keep_buffer=4,
            error_tile_url=_ERROR_TILE_URL,
            trails_forest=True,
            class_name="trails-forest-tiles",
            z_index=264,
            bounds=[[provider.extent[1], provider.extent[0]], [provider.extent[3], provider.extent[2]]],
        )
        forest.add_to(fmap)
        setattr(fmap, MAP_FOREST_ATTR, forest)
    # And where the ground is mire (§6.13), cut and drawn the same way, its
    # own switch since a bog is neither willow nor forest.
    if provider is not None and provider.mire is not None:
        mire_layer = folium.TileLayer(
            tiles=provider.mire.template,
            attr=_BASE_LAYERS[base]["attr"] or "",
            name="Mire",
            overlay=True,
            control=False,
            show=False,
            opacity=1.0,
            max_zoom=18,
            max_native_zoom=provider.mire.top,
            cross_origin=True,
            update_when_zooming=False,
            update_when_idle=False,
            keep_buffer=4,
            error_tile_url=_ERROR_TILE_URL,
            trails_mire=True,
            class_name="trails-mire-tiles",
            z_index=266,
            bounds=[[provider.extent[1], provider.extent[0]], [provider.extent[3], provider.extent[2]]],
        )
        mire_layer.add_to(fmap)
        setattr(mire_layer, MAP_MIRE_CLASSES_ATTR, provider.mire.classes())
        setattr(fmap, MAP_MIRE_ATTR, mire_layer)

    # Every page gets the colours, chrome or no chrome: the panels carry them
    # as inline styles, and an inline style resolves its variables against the
    # document — so the document has to have said them.
    _Theme().add_to(fmap)
    _PinSize().add_to(fmap)
    _ScaleZoom().add_to(fmap)
    _ServiceWorker(companions).add_to(fmap)
    setattr(fmap, MAP_PROVIDER_ATTR, provider)
    setattr(fmap, MAP_COMPANIONS_ATTR, companions)
    # Before any layer for a second reason, said where `_TouchReach` is written:
    # Leaflet pads a path's bounding box with the reach that was in force when
    # the path was projected.
    _TouchReach(FINGER_PX, TAP_SLOP_PX).add_to(fmap)
    # Before any layer, because every layer's own script calls it: folium
    # renders a map's children in the order they were added, and the layers are
    # added by the caller after this returns.
    _PopupText().add_to(fmap)

    if bounds is not None:
        min_lon, min_lat, max_lon, max_lat = bounds
        fmap.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
        setattr(fmap, MAP_BOUNDS_ATTR, bounds)

    return fmap


#: Schemes a popup link may use. Anything else — ``javascript:`` above all —
#: would execute in the page as soon as a reader clicks a trail.
_LINK_SCHEMES = ("http://", "https://")

#: Prefix of the CSS class identifying which route a line belongs to.
_GROUP_CLASS_PREFIX = "trail-group-"

#: Anything outside this becomes a dash, so a route name or id always yields a
#: single valid CSS class token.
_CLASS_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _group_class(value: object) -> str:
    """Build the CSS class marking every line of one route.

    Args:
        value: Identifying value, typically a route id or name

    Returns:
        A single CSS class token, distinct for distinct values
    """
    # A single null anywhere in an id column makes pandas store it as float, and
    # 1113860.0 would otherwise yield a different class than 1113860 — the same
    # route named differently depending on an unrelated row.
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    text = str(value)
    token = _CLASS_SAFE.sub("-", text)
    if token != text:
        # "Bønå" and "Bønö" both flatten to "B-n-", which would silently merge two
        # routes into one selection, so anything reshaped keeps a digest of the
        # original. Plain ids pass through untouched.
        token = f"{token}-{hashlib.md5(text.encode()).hexdigest()[:6]}"
    return f"{_GROUP_CLASS_PREFIX}{token}"


#: Attribute under which a feature group carries the text its lines can be found
#: by. Leaflet path options accept no custom keys, so the names travel beside the
#: layer rather than on it, keyed by the class each path already carries.
SEARCH_NAMES_ATTR = "search_names"


def _record_search_names(group: folium.FeatureGroup, names: dict[str, str]) -> None:
    """Attach the searchable names of a layer to its feature group.

    Args:
        group: Feature group the names belong to
        names: Mapping of CSS class to the text it can be found by
    """
    setattr(group, SEARCH_NAMES_ATTR, names)


#: Attribute under which a feature group carries the named things it draws, as
#: a table rather than as popup HTML. The same mechanism as
#: :data:`SEARCH_NAMES_ATTR` and :data:`CHAIN_FIGURES_ATTR`, and needed for the
#: same reason: a Leaflet marker's name lives in the popup it was given, which
#: is a string of markup and not a lookup. Over two thousand points are drawn
#: here — huts, quays, trailheads, farms, settlements — and until this existed
#: nothing in the page could answer *what is at this position*.
#:
#: Opt-in per layer, through the ``point_type`` a caller passes: a place name
#: drawn as text rather than as a marker asserts no single position — a valley
#: has none — and a waypoint must not be named after one.
NAMED_POINTS_ATTR = "named_points"


def _record_named_points(group: folium.FeatureGroup, points: list[dict[str, object]]) -> None:
    """Attach the named things a layer draws to its feature group.

    Args:
        group: Feature group the points belong to
        points: One entry per point, with its name, type and position
    """
    setattr(group, NAMED_POINTS_ATTR, points)


#: Attribute under which a feature group carries the figures its lines are
#: described by. The same mechanism as :data:`SEARCH_NAMES_ATTR`, for the same
#: reason: a Leaflet polyline has no ``feature.properties`` and its path options
#: drop unknown keys, so a number reaches the browser beside the layer, keyed by
#: the class every path already carries.
CHAIN_FIGURES_ATTR = "chain_figures"

#: Key under which the figures of a line name the thing they describe. The class
#: is what the table is keyed by, but a class is not an id — :func:`_group_class`
#: reshapes anything that is not a CSS token — so what the figures are *about*
#: travels as a value rather than being read back out of the key.
FIGURE_ID_KEY = "id"

#: Decimals a carried figure keeps. A tenth of a metre is ten times finer than
#: the height model resolves and a hundred times finer than anything shown, and
#: a tenth of a degree turns an arrow by less than its own stroke width. Written
#: at full float precision instead, this table costs a third of a megabyte more
#: for digits nothing can use.
FIGURE_DECIMALS = 1

#: The gradient rule, taken from :mod:`trails.routing.elevation` rather than
#: kept here as well. The panel colours by it and a chain's popup states the
#: steepest it reaches, so the page and the build have to be reading one rule:
#: two copies of a threshold drift, and this project has paid for that twice.
GRADIENT_WINDOW_M = elevation.GRADIENT_WINDOW_M
GRADIENT_MIN_RUN_M = elevation.GRADIENT_MIN_RUN_M

#: How a gradient is banded on the profile: the lower bound in per cent, the
#: name, the colour and the stroke width. The width escalates with the colour so
#: the reading survives a red-green confusion.
#:
#: **The lowest boundary was chosen against the model's own noise, not by taste.**
#: On chains that rise under three metres end to end — level ground — the height
#: model reads a median of 1.0 % over this window, a 99th percentile of 5.8 % and
#: a worst case of 9.2 %. Not one level stretch reaches 15 %. So a coloured
#: stretch is a statement about the hill and never about the data. Measured over
#: the network the bands hold 81.9 %, 11.5 %, 5.1 % and 1.5 % of the ground.
#: The width, in CSS pixels of the map itself, under which the page lays out for
#: a hand rather than for a desk. **Derived rather than chosen**: the legend
#: measures 380 px and a popup 367, so below their sum plus margins the two
#: cannot stand side by side and something has to cover something. The axis is
#: the map's width and not the device — a desktop window dragged to 390 px has
#: exactly the same problem, and a phone held sideways no longer has it.
NARROW_PX = 760

#: The height, in CSS pixels of the map, under which a panel at the foot has to
#: give room back rather than take it. **Derived**: the tallest phone held
#: sideways is about 430 and the shortest laptop about 600, so anything under
#: this is a phone on its side and nothing else. It is a separate question from
#: :data:`NARROW_PX` because room at the foot is about height and standing side
#: by side is about width — measured, a phone upright is 390 x 844 and a desktop
#: 1400 x 900, which one number cannot tell apart.
SHORT_PX = 500

GRADIENT_BANDS = (
    (0.0, "gentle", "#33691e", 1.6),
    (15.0, "steep", "#f9a825", 2.1),
    (25.0, "very steep", "#ef6c00", 2.6),
    (40.0, "extreme", "#c62828", 3.2),
)

#: Everything the page has to be handed before it can write a GPX file. There is
#: no default for any of it and none may be missing: a licence, a version or a
#: field name the browser had to invent would be a claim nobody made, written
#: into the one file that leaves this machine. :func:`add_profile_panel` refuses
#: an ``export`` that is short of any of them rather than building a page that
#: writes ``undefined`` into a source's terms.
EXPORT_SETTINGS = (
    "credits",
    "heights",
    "protected",
    "fields",
    "creditFields",
    "sourceLength",
    "route",
    "waypoint",
    "gapM",
    "decimals",
    "elevationDecimals",
    "coordinateDecimals",
    "namespace",
    "prefix",
    "creator",
    "description",
    "ascentMethod",
    "identitySeparator",
    "filePrefix",
)


#: What ``route`` holds, which is every name a planned route's own file is
#: written with. Checked as its own list rather than by the presence of the key
#: above it: a ``route`` short of ``partLength`` builds without a word and the
#: page writes ``<trails:part kind="routed" undefined="2027.0"/>``, and one short
#: of ``kindField`` writes an element called ``undefined`` — a file that fails
#: the schema, out of a check whose whole point is that it does not happen.
EXPORT_ROUTE_SETTINGS = (
    "name",
    "description",
    "fileStem",
    "kindField",
    "kind",
    "fields",
    "legs",
    "leg",
    "part",
    "partKind",
    "partLength",
    "areas",
    "area",
    "areaId",
    "areaName",
    "areaForm",
    "areaLength",
)

#: What ``waypoint`` holds, checked for the same reason as
#: :data:`EXPORT_ROUTE_SETTINGS`.
#:
#: ``generated`` is the other value ``origin`` takes, and the three words after
#: it are what a marker the map placed says it is: a boundary crossing names the
#: area it enters or leaves, and ``area`` is the field its id travels under, so
#: a reader loading the file back can tell which boundary was meant without
#: parsing a sentence.
EXPORT_WAYPOINT_SETTINGS = ("name", "origin", "set", "generated", "enters", "leaves", "area", "stage")


#: Everything the page has to be handed before it can plan a route. As with
#: :data:`EXPORT_SETTINGS` there is no default for any of it: a sampling step,
#: an ascent threshold or the name of the answer that means *sea* are all things
#: the build already decided, and a page that quietly picked its own would draw
#: a profile that disagrees with every other figure on the map without anything
#: looking wrong. :func:`add_plan_mode` refuses a ``plan`` short of any of them.
PLAN_SETTINGS = (
    "heightsUrl",
    "heightsCrs",
    "heightsBatch",
    "heightsWorkers",
    "heightsTimeoutMs",
    # The height tiles, where the map carries them (:class:`HeightTiles`),
    # and then the service above is not asked; None where it is.
    "heightsTiles",
    "routeWidth",
    "terrainModel",
    "seaTerrain",
    "sampleStepM",
    "ascentThresholdM",
    "snapM",
    "snapPx",
    "maxStraightM",
    "offPathFactor",
    "waterFactor",
    "crossingKind",
    "connectorKind",
    "paddleKind",
    "portageFactor",
    "touchedM",
    "namedM",
    "gpx",
    "indexCellM",
    "matchToleranceM",
    "matchMinOverlap",
    "matchMinRunM",
    "matchMaxTurnDeg",
    "matchAnchorM",
)


#: What ``gpx`` holds: every name phase 8's reader needs to recognise a file
#: this map wrote and to read back what it says. Checked as its own list for the
#: reason :data:`EXPORT_ROUTE_SETTINGS` is — a missing key here is a page that
#: looks for an element called ``undefined``, finds none, and reports a route
#: export as a foreign track without a word.
#:
#: **This is the one place in the project where a reader and a writer of the
#: same file are in one phase**, and every name below is also in
#: :data:`EXPORT_ROUTE_SETTINGS` or :data:`EXPORT_WAYPOINT_SETTINGS` — handed
#: over twice, out of one Python constant each, so the two vocabularies cannot
#: drift. ``trackKind`` is the exception and travels only here: it is the fifth
#: part kind, and plan mode both writes it and reads it.
PLAN_GPX_SETTINGS = (
    "namespace",
    "kindField",
    "kind",
    "chainField",
    "legs",
    "leg",
    "part",
    "partKind",
    "partLength",
    "origin",
    "set",
    "generated",
    "trackKind",
    "stage",
)


def _record_chain_figures(group: folium.FeatureGroup, figures: dict[str, dict[str, object]]) -> None:
    """Attach the per-line figures of a layer to its feature group.

    Args:
        group: Feature group the figures belong to
        figures: Mapping of CSS class to the figures of the line carrying it
    """
    setattr(group, CHAIN_FIGURES_ATTR, figures)


def _figure_values(row: pd.Series, fields: dict[str, str]) -> dict[str, object]:
    """Read the figures of one feature, in the shape the page reads them.

    Args:
        row: Row of a GeoDataFrame
        fields: Mapping of column name to the key it travels under

    Returns:
        One entry per field. A missing value travels as None and reaches the
        page as ``null``, which is what a ferry crossing's ascent is and what a
        ring's bearing is: not zero, and not a number to be drawn. A number is
        rounded to :data:`FIGURE_DECIMALS`, which is finer than anything shown
        and ten times finer than the height model resolves — the alternative is
        writing ``17.339999999999996`` eleven thousand times.
    """
    values: dict[str, object] = {}
    for column, key in fields.items():
        value = row[column] if column in row else None
        if value is None or pd.isna(value):
            values[key] = None
        elif isinstance(value, str):
            # Anything already decided here travels as it is. A label must not
            # be re-derived in the page: that is a second implementation of a
            # rounding rule, and a rounding rule is a threshold.
            values[key] = value
        else:
            values[key] = round(float(value), FIGURE_DECIMALS)
    return values


def _packed_figures(figures: dict[str, dict[str, object]]) -> dict[str, object]:
    """Lay a chain-figures table out positionally, so its field names travel once.

    **Every figure has the same twelve fields** -- :func:`_figure_values` writes
    one entry per field whether the row said anything or not -- and written as
    objects that is twelve field names per chain. Measured on the built page:
    11,290 chains, 2.84 MB, of which **1.26 MB is the word `ascent` and its
    eleven siblings**, said 11,290 times each.

    The page puts the objects back together on load (:class:`_ProfilePanel`), so
    everything that reads a figure reads it by name as it always did. What is
    saved is source the browser's parser has to walk, which is where this page's
    seconds are.

    Args:
        figures: Mapping of CSS class to the figures of the line carrying it

    Returns:
        The field names once, and one list of values per chain in that order
    """
    fields = list(dict.fromkeys(key for figure in figures.values() for key in figure))
    return {
        "fields": fields,
        "rows": {name: [figure.get(key) for key in fields] for name, figure in figures.items()},
    }


def _popup_shape(
    gdf: gpd.GeoDataFrame,
    fields: dict[str, str],
    link_fields: dict[str, str] | None = None,
    source: str | None = None,
    link_heading: str | None = None,
    published_fields: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Work out the part of a popup that is the same for a whole layer.

    **A popup used to be built at load, once per feature, as markup.** Measured
    on the built page that was 12,898 popups, **16.62 MB** of ``$(`<div>...`)``
    handed to jQuery before the map drew anything, and 187 MB of the 590 MB the
    page settles at -- to show one of them at a time. Of that HTML, **1.28 MB
    was the values**: a popup was eight per cent information and the rest was
    the same eleven labels and the same inline styles written out again.

    So the labels, the link texts, the heading and the source travel **once per
    layer** and the values travel per feature (:func:`_popup_values`), and the
    page builds the table when somebody opens one -- see :class:`_PopupText`.

    **Which columns count is settled here rather than per row**, because a
    column the frame does not have is missing from every row of it, and the
    values are positional against these labels.

    Args:
        gdf: The layer, for the columns it actually has
        fields: Mapping of column name to display label
        link_fields: Mapping of a column holding a URL to the link text to show
            for it. Rendered below the table rows, one link per line. Values that
            are not http(s) URLs are dropped. A column may instead hold a list
            of ``(text, url)`` pairs, for a feature that answers to several
            pages; then each pair is a link of its own, with its own text.
        source: Dataset the feature came from, shown as a footer. A map that
            stacks seven sources is unreadable without it, so it is worth a line
            even where nothing else about the feature is known.
        link_heading: Line set above the links, saying whose pages they are.
            Without one, a link offering a GPX reads as this map's export of the
            line rather than as the recording somebody else published.
        published_fields: Mapping of column name to label for rows that belong
            **under** that heading rather than above it: what somebody else
            states about this line, as against what this map worked out. A
            route's own site saying *23,4 km, 2 d, +1088 m* is a claim of theirs
            and sat in the middle of ours, where it read as a figure this map
            had measured and disagreed with itself by a kilometre.

    Returns:
        The layer's popup shape, or None if no feature of it could show anything
    """
    columns = [column for column in fields if column in gdf.columns]
    stated = [column for column in (published_fields or {}) if column in gdf.columns]
    links = [column for column in (link_fields or {}) if column in gdf.columns]
    if not columns and not stated and not links and not source:
        return None
    shape: dict[str, Any] = {
        "labels": [str(fields[column]) for column in columns],
        "published": [str((published_fields or {})[column]) for column in stated],
        "links": [str((link_fields or {})[column]) for column in links],
        "columns": columns,
        "publishedColumns": stated,
        "linkColumns": links,
    }
    if link_heading:
        shape["heading"] = str(link_heading)
    if source:
        shape["source"] = str(source)
    return shape


#: One slot of a feature's popup values: text for a label, a URL for a link --
#: or, for a link column, a list of ``[text, url]`` pairs where one feature
#: answers to several pages at once.
PopupValue = str | list[list[str]]


def _link_value(value: object) -> PopupValue | None:
    """Pick a link column's value out of a row, dropping what is not a link.

    **A chain may answer to several pages.** The register's state trails are
    joined into one chain where they run on into each other, so *BD 21 / BD 92
    / BD 16 / BD 91* is one line with four pages describing it. One link text
    per column cannot name four pages, so such a column carries a list of
    ``(text, url)`` pairs and the page writes one link per pair, each with its
    own text; a plain URL still travels as the string it always was, under the
    column's text.

    Args:
        value: The cell: a URL, a list of ``(text, url)`` pairs, or nothing

    Returns:
        The URL, the pairs whose URL is http(s) as lists, or None if nothing
        of it is a link
    """
    if isinstance(value, list | tuple):
        pairs = [[str(text), str(url)] for text, url in value if str(url).startswith(_LINK_SCHEMES)]
        return pairs or None
    if value is None or (isinstance(value, float) and pd.isna(value)) or not str(value).startswith(_LINK_SCHEMES):
        return None
    return str(value)


def _popup_values(row: pd.Series, shape: dict[str, Any]) -> list[PopupValue | None] | None:
    """Pick one feature's popup values out of its row.

    **Everything travels as text**, including numbers: that is what
    :class:`_PopupText` writes and what the page has always shown, and a numpy
    scalar is not JSON anyway.

    Args:
        row: Row of a GeoDataFrame
        shape: What :func:`_popup_shape` worked out for the layer

    Returns:
        One entry per label, then one per published label, then one per link,
        ``None`` where the row says nothing -- or None altogether if the row
        fills no slot and the layer has no source line to fall back on
    """
    values: list[PopupValue | None] = []
    for column in shape["columns"] + shape.get("publishedColumns", []):
        value = row[column]
        values.append(None if pd.isna(value) or value == "" else str(value))
    for column in shape["linkColumns"]:
        values.append(_link_value(row[column]))
    if not any(value is not None for value in values) and "source" not in shape:
        return None
    # Trailing empties say nothing the builder cannot assume, and there are a lot
    # of them: a positional list is read against the labels, so a short one is
    # read exactly as a padded one.
    while values and values[-1] is None:
        values.pop()
    return values


def add_trails(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "#1b5e20",
    weight: float = 3.0,
    opacity: float = 0.85,
    popup_fields: dict[str, str] | None = None,
    published_fields: dict[str, str] | None = None,
    link_fields: dict[str, str] | None = None,
    link_heading: str | None = None,
    tooltip_field: str | None = None,
    group_field: str | None = None,
    search_field: str | None = None,
    figure_fields: dict[str, str] | None = None,
    source: str | None = None,
    dash_array: str | None = None,
    show: bool = True,
) -> folium.FeatureGroup:
    """Add trail geometries as a toggleable layer.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with line geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Line color
        weight: Line width in pixels
        opacity: Line opacity between 0 and 1
        popup_fields: Mapping of column name to popup label
        published_fields: Mapping of column name to popup label for what
            somebody else states about the line, shown under the link heading
            rather than among the figures this map worked out
        link_fields: Mapping of a column holding a URL to its link text, for
            trails that have a description page elsewhere
        link_heading: Line set above those links, saying whose pages they are
        tooltip_field: Column shown on hover, so a line can be identified before
            it is clicked
        group_field: Column whose value ties the parts of one route together, so
            :func:`add_click_highlight` can pick out all of it at once. A route
            split into several lines shares one value.
        search_field: Column holding the text :func:`add_search` matches against
        figure_fields: Mapping of a column to the key it travels under, for what
            :func:`add_profile_panel` shows and writes. Recorded per
            ``group_field`` value, beside the layer rather than on it, alongside
            the value itself under :data:`FIGURE_ID_KEY`. A number is rounded on
            the way (see :func:`_figure_values`); a string travels as it is,
            which is what carries a chain's name and its source into a page that
            has to write both into an exported file.
        source: Dataset the lines came from, shown at the foot of every popup
        dash_array: SVG dash pattern, e.g. ``"8,6"``. Use for connections that
            are not walked, such as ferry crossings.
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    search_names: dict[str, str] = {}
    figures: dict[str, dict[str, object]] = {}
    shape = (
        _popup_shape(gdf, popup_fields or {}, link_fields, source, link_heading, published_fields)
        if (popup_fields or published_fields or link_fields or source)
        else None
    )

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue

        lines = list(geometry.geoms) if geometry.geom_type == "MultiLineString" else [geometry]
        popup = _popup_values(row, shape) if shape else None

        tooltip = None
        if tooltip_field and tooltip_field in row and pd.notna(row[tooltip_field]):
            tooltip = str(row[tooltip_field])

        # Leaflet writes className straight onto the SVG path, which makes it the
        # natural place to carry the route identity into the browser. Path options
        # drop unknown keys, so the searchable text cannot ride along the same way
        # and is handed to the browser as a lookup keyed by this class instead.
        class_name = None
        key_field = group_field or search_field
        if key_field and key_field in row and pd.notna(row[key_field]):
            class_name = _group_class(row[key_field])
        if class_name and search_field and search_field in row and pd.notna(row[search_field]):
            search_names[class_name] = str(row[search_field])
        # Keyed by the class and not by the group value, because that is what a
        # click hands back: a path knows the class it was drawn with and nothing
        # else about the feature it came from.
        if class_name and figure_fields and key_field:
            figures[class_name] = {FIGURE_ID_KEY: str(row[key_field]), **_figure_values(row, figure_fields)}

        for line in lines:
            polyline = folium.PolyLine(
                locations=[(round(lat, DRAWN_DECIMALS), round(lon, DRAWN_DECIMALS)) for lon, lat in line.coords],
                color=color,
                weight=weight,
                opacity=opacity,
                dash_array=dash_array,
                tooltip=_tooltip(tooltip) if tooltip else None,
                class_name=class_name,
            )
            polyline.options = _lean(polyline.options, filled=False)
            if popup is not None:
                polyline.options["popup"] = popup
            polyline.add_to(group)

    if shape:
        group.add_child(_LazyPopups(shape))
    _record_search_names(group, search_names)
    _record_chain_figures(group, figures)
    group.add_to(fmap)
    return group


class _PopupText(MacroElement):
    """The one place a popup's table is written, and it runs in the browser.

    **The markup used to be built in Python, per feature, at build time**, and
    every one of the 12,898 tables was written into the page whole -- the same
    eleven labels, the same eight inline styles, the same source line, over and
    over, and handed to jQuery on load. This is that function, once, in the
    language that has a reader in front of it.

    It is handed the layer's shape (:func:`_popup_shape`) and the feature's
    values (:func:`_popup_values`) and puts them together the way the build did,
    down to the styles: the page looks the same and weighs 17 MB less.

    **The escaping came across with it.** Values are third-party data and must
    not be able to inject markup, which was ``html.escape`` and is now the same
    five characters by hand -- ``&#x27;`` for an apostrophe included, so a name
    escaped here and one escaped in an exported file read alike.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "popup_text.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )


class _LazyPopups(MacroElement):
    """Give a layer's features a popup that is built when one is opened.

    Rendered as the last child of the feature group it belongs to, so every
    feature of that group already exists when it runs -- the same rule as
    :class:`_ClickHighlight`, one level down.

    **Leaflet takes a function as popup content** and calls it on open, handing
    it the layer, which is the whole mechanism: the shape is captured once in
    this closure, the values ride on the layer, and no table is built until
    somebody asks for one.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "lazy_popups.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, shape: dict[str, Any]) -> None:
        """Bind a layer's popups.

        Args:
            shape: What :func:`_popup_shape` worked out for this layer. Only the
                labels, links, heading and source travel: the columns they were
                read from are the build's business.
        """
        super().__init__()
        self._name = "LazyPopups"
        self.shape_json = json.dumps({key: value for key, value in shape.items() if key not in ("columns", "linkColumns", "publishedColumns")})


class _ClickHighlight(MacroElement):
    """Leaflet behaviour that lifts the clicked route out of the tangle.

    Rendered after the layers it operates on, so their JavaScript variables
    already exist by the time this runs.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "click_highlight.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, groups: list[folium.FeatureGroup], weight_boost: float, dim_opacity: float) -> None:
        """Initialize the behaviour.

        Args:
            groups: Feature groups whose lines take part
            weight_boost: Pixels added to the selected route's width
            dim_opacity: Opacity the unselected routes fall back to
        """
        super().__init__()
        self._name = "ClickHighlight"
        self.group_names = [group.get_name() for group in groups]
        self.weight_boost = weight_boost
        self.dim_opacity = dim_opacity


def add_click_highlight(
    fmap: folium.Map,
    groups: list[folium.FeatureGroup],
    weight_boost: float = 4.0,
    dim_opacity: float = 0.15,
) -> None:
    """Make a clicked route stand out from the ones it overlaps.

    Where several sources map the same valley, none of their lines can be
    followed by eye. Clicking one widens it, draws it in front of everything
    else and fades every other line on the map, so a single trip reads end to
    end. Clicking it again, or clicking empty terrain, puts everything back.

    Only lines carrying a ``group_field`` take part, and all lines sharing that
    value are selected together, so a route split into several pieces — or
    across two layers — still highlights as one.

    Call after the layers have been added, and before :func:`add_legend`.

    Args:
        fmap: Map holding the layers
        groups: Feature groups returned by :func:`add_trails`
        weight_boost: Pixels added to the selected route's width
        dim_opacity: Opacity the unselected routes fall back to
    """
    if not groups:
        return
    _ClickHighlight(groups, weight_boost=weight_boost, dim_opacity=dim_opacity).add_to(fmap)


def _script_json(value: object) -> str:
    """Serialise a value for embedding inside a ``<script>`` block.

    ``json.dumps`` leaves ``<`` alone, so a string holding ``</script>`` would
    close the block and everything after it would be parsed as markup. Escaping
    the one character shuts that door; a JavaScript parser reads ``\\u003c``
    back as ``<``, so any HTML carried in the value survives intact.

    **A backtick goes the same way.** :func:`_squeezed` walks the page by
    backtick parity to keep out of the JavaScript's template literals, and a
    raw backtick inside a JSON string throws that count off -- the first
    Malingsbo-Kloten build stopped on an OSM path named ``EkMalm`sStig``
    (2026-09-20). ``\\u0060`` reads back as the same character.

    Args:
        value: Anything JSON can represent

    Returns:
        A JavaScript literal safe to paste into a script block
    """
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace("`", "\\u0060")


def _layer_label(group: folium.FeatureGroup) -> str:
    """What a layer is called, short enough to stand under a search result.

    Every overlay here is named for the legend, where there is room to say
    everything: ``Paths (12,263)``, or ``Name ⌂ settlements, cabins and
    facilities — settlement or building, facility [Ortnamn]``. A row of a search
    list has one ellipsised line for the same question, and the answer it wants
    is *what kind of thing is this, and who says so*: the count belongs to the
    legend, and so does the list of subtypes after the dash. The source in
    brackets is kept wherever it was, because two layers of one kind from two
    registers are told apart by nothing else.

    Args:
        group: The feature group, named as the legend names it

    Returns:
        The name without its count and without the detail after an em dash, with
        the bracketed source kept
    """
    name = re.sub(r"\s*\([\d,\s]+\)$", "", str(getattr(group, "layer_name", "") or ""))
    head = re.split(r"\s+—\s+", name)[0].strip()
    source = re.search(r"\[[^\]]+\]$", name)
    if source and source.group() not in head:
        return f"{head} {source.group()}"
    return head


class _NameSearch(MacroElement):
    """A box that lists what matches what is typed, and marks a typed position.

    Deliberately separate from :class:`_ClickHighlight`: this one decides what is
    *listed*, that one decides what is *emphasised*. Two independent properties,
    so the two can be used together without either undoing the other.

    **It used to hide.** Typing cleared ``display`` on every feature that did not
    match, and cleared ``interactive`` with it, so the map was reduced to the
    answer -- which is one way to find a name among twelve thousand features, and
    it costs the reader everything else on the ground: what the match is near,
    what it lies between, which of the six lines through that valley it is. A
    list of the matches answers the same question and takes nothing away, so the
    map stays whole while a search runs and the list is what narrows.

    **And what is typed need not be a name.** The position picker copies
    ``68.39275, 18.68033`` to the clipboard; typed back in here the same string
    is read as the position it names, offered as the first row, and marked on the
    map when that row is taken -- carrying the *Set as goal* button a place's
    popup carries, because a position a reader typed is a place they meant.

    The script lives in js/name_search.js, with its regular expressions unchanged.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "name_search.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, groups: list[folium.FeatureGroup], names: dict[str, str], placeholder: str) -> None:
        """Initialize the search box.

        Args:
            groups: Feature groups to search across
            names: Mapping of CSS class to searchable text, for path layers
            placeholder: Hint shown in the empty input
        """
        super().__init__()
        self._name = "NameSearch"
        self.group_names = [group.get_name() for group in groups]
        self.names_json = _script_json(names)
        self.labels_json = _script_json([_layer_label(group) for group in groups])
        self.placeholder_json = _script_json(placeholder)


def add_search(
    fmap: folium.Map,
    groups: list[folium.FeatureGroup],
    placeholder: str = "A name, or a position…",
) -> None:
    """Add a box that lists what matches what is typed.

    On a map carrying several thousand features from seven sources, finding the
    one place named in a brochure is otherwise hopeless. Typing lists the matches
    — across trails, roads, huts and place names alike — nearest first, one row
    per thing, saying which layer each was drawn in and how far off it is. A row
    taken does what tapping that thing on the map does, and the map goes to it.
    Enter takes the first row, Escape clears the field.

    **The map stays whole.** This box used to hide everything that did not match;
    a list answers the same question without taking the ground around the answer
    away with it.

    Matching ignores case and folds Norwegian and Sámi letters, so ``tveravegen``
    finds ``Tveråvegen`` from a keyboard that cannot type å.

    **A position is a name here too.** ``68.39275, 18.68033`` — the form the
    picker at the foot copies — is read as the place it names and offered as the
    first row, with degrees and minutes and seconds understood as well; taking
    that row marks the spot, which can then be set as a goal like any other.

    Only features given a searchable name take part. A layer that is switched off
    is still searched, and taking one of its rows switches it on, so a name
    cannot hide behind an unticked box.

    Call after the layers have been added, and before :func:`add_legend`.

    Args:
        fmap: Map holding the layers
        groups: Feature groups to search across, of any layer type
        placeholder: Hint shown in the empty input
    """
    if not groups:
        return

    names: dict[str, str] = {}
    for group in groups:
        names.update(getattr(group, SEARCH_NAMES_ATTR, {}))

    _NameSearch(groups, names, placeholder).add_to(fmap)


def add_points(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "red",
    icon: str = "house-chimney",
    icon_field: str | None = None,
    popup_fields: dict[str, str] | None = None,
    link_fields: dict[str, str] | None = None,
    link_heading: str | None = None,
    label_field: str | None = "name",
    search_field: str | None = None,
    source: str | None = None,
    point_type: str | None = None,
    show: bool = True,
) -> folium.FeatureGroup:
    """Add point features (huts, shelters, info points) as a toggleable layer.

    **The glyph says what a place is for; the colour says who placed it.** One
    layer is one source, and a source places huts of several kinds -- a staffed
    cabin, an open shelter, a private koie -- so the glyph is read per row where
    ``icon_field`` names a column, and ``icon`` is what a row without one gets.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with point geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Marker colour; one of :data:`PIN_COLOURS`, which is the palette
            awesome-markers named
            (e.g. "red", "darkblue", "green"), not a CSS hex value
        icon: Glyph name, one of :data:`MARKER_ICONS`; the glyph of every row
            unless ``icon_field`` says otherwise
        icon_field: Column holding a glyph name per row. A row whose value is
            empty falls back to ``icon``; a name this page does not draw is
            refused at build time, by name, as ``icon`` is. **A column the frame
            does not have at all is refused too**, because that is a caller that
            meant to say something per row and said nothing: measured once, 49
            quays that should have been ships and anchors were drawn as the
            layer's default and the build went on without a word.
        popup_fields: Mapping of column name to popup label
        link_fields: Mapping of a column holding a URL to the link text to show
            for it, as :func:`add_trails` takes. A quay says where its timetable
            is; a line has always been able to, and a point could not.
        link_heading: Line set above the links, saying whose pages they are
        label_field: Column used for the hover tooltip
        search_field: Column holding the text :func:`add_search` matches against;
            defaults to ``label_field``
        source: Dataset the points came from, shown at the foot of every popup
        point_type: What these points are — a hut, a quay, a trailhead. Given
            one, the layer carries a table of what it draws and where, which is
            how a waypoint set beside one of them comes to be named after it.
            Left out, the layer draws itself and answers no questions.
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Said at build time, and about the layer rather than about a row: a missing
    # column is missing from every row, so every pin would quietly take ``icon``.
    if icon_field and len(gdf) and icon_field not in gdf.columns:
        raise ValueError(f"layer {name!r} asks for its glyph from {icon_field!r}, which it does not carry; it has " + ", ".join(sorted(gdf.columns)))

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    named: list[dict[str, object]] = []
    glyphs: list[str] = []
    shape = (
        _popup_shape(gdf, popup_fields or {}, link_fields=link_fields, source=source, link_heading=link_heading)
        if (popup_fields or link_fields or source)
        else None
    )

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue

        tooltip = None
        if label_field and label_field in row and pd.notna(row[label_field]):
            tooltip = str(row[label_field])

        glyph = icon
        if icon_field and icon_field in row and pd.notna(row[icon_field]) and row[icon_field] != "":
            glyph = str(row[icon_field])
        if glyph not in glyphs:
            glyphs.append(glyph)

        popup = _popup_values(row, shape) if shape else None
        # Unlike a path, a marker keeps whatever options it is handed, so the
        # searchable text can travel on the layer itself.
        found_by = search_field or label_field
        options: dict[str, Any] = {}
        if found_by and found_by in row and pd.notna(row[found_by]):
            options["searchName"] = str(row[found_by])

        marker = folium.Marker(
            location=(round(geometry.y, DRAWN_DECIMALS), round(geometry.x, DRAWN_DECIMALS)),
            tooltip=_tooltip(tooltip) if tooltip else None,
            icon=folium.DivIcon(html=_pin(color, glyph), icon_size=(PIN_WIDTH, PIN_HEIGHT), icon_anchor=(PIN_WIDTH // 2, PIN_HEIGHT)),
            **options,
        )
        if popup is not None:
            marker.options["popup"] = popup
        marker.add_to(group)

        if point_type and tooltip:
            named.append({"name": tooltip, "type": point_type, "lat": round(geometry.y, DRAWN_DECIMALS), "lon": round(geometry.x, DRAWN_DECIMALS)})

    if shape:
        group.add_child(_LazyPopups(shape))
    _record_named_points(group, named)
    setattr(group, PIN_GLYPHS_ATTR, glyphs)
    group.add_to(fmap)
    return group


def add_labelled_points(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "#37474f",
    radius: float = 6.0,
    label_field: str = "name",
    always_label: tuple[str, ...] = (),
    kind_field: str = "kind",
    popup_fields: dict[str, str] | None = None,
    source: str | None = None,
    point_type: str | None = None,
    searchable: bool = True,
    show: bool = True,
) -> folium.FeatureGroup:
    """Add place markers as small labelled circles.

    Lighter than :func:`add_points` for orientation layers with many features:
    pin icons would dominate the map, so these render as dots. Labels for the
    most important kinds stay permanently visible, the rest appear on hover.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with point geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Circle fill and outline color
        radius: Circle radius in pixels. Doubles as the click target, so a dot
            small enough to look tidy is often too small to hit.
        label_field: Column holding the label text
        always_label: Values of ``kind_field`` whose labels are always shown
        kind_field: Column consulted for ``always_label``
        popup_fields: Mapping of column name to popup label. Without it a marker
            only names itself on hover, which reads as a dead click.
        source: Dataset the points came from, shown at the foot of every popup
        point_type: What these points are — a trailhead, a farm, a settlement.
            See :func:`add_points`; the same table, for the same reason.
        searchable: Whether :func:`add_search` can find these by their label
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    search_names: dict[str, str] = {}
    named: list[dict[str, object]] = []
    shape = _popup_shape(gdf, popup_fields or {}, source=source) if (popup_fields or source) else None

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        if label_field not in row or pd.isna(row[label_field]):
            continue

        label = str(row[label_field])
        permanent = kind_field in row and row[kind_field] in always_label

        class_name = None
        if searchable:
            class_name = _group_class(label)
            search_names[class_name] = label

        marker = folium.CircleMarker(
            location=(round(geometry.y, DRAWN_DECIMALS), round(geometry.x, DRAWN_DECIMALS)),
            radius=radius,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            class_name=class_name,
            tooltip=_tooltip(label, permanent=permanent, direction="right"),
        )
        marker.options = _lean(marker.options, filled=True)

        popup = _popup_values(row, shape) if shape else None
        if popup is not None:
            marker.options["popup"] = popup
        marker.add_to(group)

        if point_type:
            named.append({"name": label, "type": point_type, "lat": round(geometry.y, DRAWN_DECIMALS), "lon": round(geometry.x, DRAWN_DECIMALS)})

    if shape:
        group.add_child(_LazyPopups(shape))
    _record_search_names(group, search_names)
    _record_named_points(group, named)
    group.add_to(fmap)
    return group


def add_text_labels(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    label_field: str = "name",
    size_field: str | None = None,
    default_size: float = 11.0,
    color: str = "#37474f",
    color_field: str | None = None,
    symbol_field: str | None = None,
    halo: str = "#ffffff",
    show: bool = True,
) -> folium.FeatureGroup:
    """Add place names as plain text, without a marker symbol.

    For terrain features a dot would assert a precision the data does not have —
    a valley has no single position. Drawing only the text, repeated wherever the
    name applies, is the topographic convention and stays honest about that.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with point geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        label_field: Column holding the text to draw
        size_field: Column holding a per-label font size in pixels
        default_size: Font size used when ``size_field`` is absent or empty
        color: Text colour used when no per-label colour is given
        color_field: Column holding a per-label CSS colour, e.g. to distinguish
            rivers from valleys
        symbol_field: Column holding a short glyph drawn before the label, so the
            feature type reads without relying on colour alone
        halo: Outline colour drawn around the glyphs for legibility over the map
        show: Whether the layer starts visible

    Returns:
        The feature group that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    group = folium.FeatureGroup(name=f"{name} ({len(gdf)})", show=show)
    shadow = f"-1px -1px 0 {halo}, 1px -1px 0 {halo}, -1px 1px 0 {halo}, 1px 1px 0 {halo}"

    for _, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        if label_field not in row or pd.isna(row[label_field]):
            continue

        size = default_size
        if size_field and size_field in row and pd.notna(row[size_field]):
            size = float(row[size_field])

        text_color = color
        if color_field and color_field in row and pd.notna(row[color_field]):
            text_color = str(row[color_field])

        text = escape(str(row[label_field]))
        if symbol_field and symbol_field in row and pd.notna(row[symbol_field]):
            text = f"{escape(str(row[symbol_field]))}\u2009{text}"

        html = (
            f'<div style="font-family:sans-serif;font-size:{size:g}px;color:{text_color};'
            f'text-shadow:{shadow};white-space:nowrap;transform:translate(-50%,-50%)">{text}</div>'
        )
        # A zero-sized icon keeps Leaflet from reserving a box around the text.
        folium.Marker(
            location=(round(geometry.y, DRAWN_DECIMALS), round(geometry.x, DRAWN_DECIMALS)),
            icon=folium.DivIcon(icon_size=(0, 0), icon_anchor=(0, 0), html=html),
            searchName=str(row[label_field]),
        ).add_to(group)

    group.add_to(fmap)
    return group


def add_boundary(
    fmap: folium.Map,
    gdf: gpd.GeoDataFrame,
    name: str,
    color: str = "#0d47a1",
    fill_opacity: float = 0.06,
    weight: float = 2.5,
    show: bool = True,
) -> folium.GeoJson:
    """Add an area boundary as a toggleable outline.

    Args:
        fmap: Map to add the layer to
        gdf: GeoDataFrame with polygon geometries; reprojected to WGS84 if needed
        name: Layer name shown in the layer control
        color: Outline color
        fill_opacity: Fill opacity between 0 and 1
        weight: Outline width in pixels
        show: Whether the layer starts visible

    Returns:
        The GeoJson layer that was added
    """
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    def style(_: Any) -> dict[str, Any]:
        return {"color": color, "weight": weight, "fillColor": color, "fillOpacity": fill_opacity}

    # A boundary is drawn last so its outline stays legible over every trail, which
    # also puts its fill on top of them for hit-testing — and a faint fill still
    # swallows clicks. Since the outline carries no popup, it opts out of pointer
    # events entirely and lets clicks reach the trails underneath.
    # The same two escapes as _script_json, for the same two reasons: folium
    # pastes this text into a script block as it is.
    layer = folium.GeoJson(
        gdf.to_json().replace("<", "\\u003c").replace("`", "\\u0060"), name=name, style_function=style, show=show, interactive=False
    )
    layer.add_to(fmap)
    return layer


class _RoutingGraph(MacroElement):
    """The routing graph, decoded in the page and never drawn.

    Hand-written, like the legend, the search and the click-highlight, and for
    the same reason: a script pulled from a CDN does not load on a ``file://``
    page and fails silently, the way the OpenStreetMap tiles once did.

    The decode runs off the load rather than during it. It is a megabyte or two
    of arithmetic, and nothing on the map waits for it — a reader who never
    plans a route never notices it happened.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "routing_graph.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, header: dict[str, Any], data: str) -> None:
        """Initialize the payload.

        Args:
            header: Everything the decoder needs before it starts
            data: The binary stream, gzipped and base64-encoded
        """
        super().__init__()
        self._name = "RoutingGraph"
        self.header_json = _script_json(header)
        self.data_json = _script_json(data)


def add_routing_graph(fmap: folium.Map, header: dict[str, Any], data: str) -> None:
    """Put the routing graph in the page, at full source precision.

    A second representation beside the drawn one, and the two must not be
    unified: what the map draws is chains, simplified for rendering, and what a
    route is found over is the merged graph at the resolution its sources
    recorded. One copy cannot serve both without losing either the accuracy or
    the render budget.

    Nothing draws it and nothing yet reads it. It arrives as
    ``window.trailsGraph``, whose ``ready`` promise resolves once the stream has
    been inflated and decoded, and whose ``decodeMs`` says what that cost.

    Args:
        fmap: Map to attach the payload to
        header: Everything the decoder needs before it starts
        data: The binary stream, gzipped and base64-encoded
    """
    _RoutingGraph(header, data).add_to(fmap)


class _ProfilePanel(MacroElement):
    """The selected chain's profile, drawn by hand at the foot of the map.

    Hand-written SVG, like the legend, the search and the click-highlight: a
    charting library pulled from a CDN does not load on a ``file://`` page and
    fails silently, the way the OpenStreetMap tiles once did.

    **Nothing here recomputes a figure.** The ascent, the descent, the high and
    low point and the bearing are read off the table this is handed, which the
    build put beside the layers. The panel decodes the chain's series for one
    thing only — the curve, and the distance under it — because a number that
    exists in two languages ends up with two values, and a popup and a panel
    disagreeing by a few metres about the same chain is worse than either of
    them being wrong.

    A control rather than a box over the page, and with only
    ``disableClickPropagation``: a wheel turned over it still has to reach the
    map, or the map reads as frozen the moment the panel is open. The **curve**
    is the one exception, and only where it has detail to give — see the zoom
    below.

    **And the crosshair marks the ground it is reading.** Wherever the pointer
    stands on the curve, a dot stands at that position on the map, so the hill
    under the pointer and the hill on the map are visibly the same hill. It works
    for a chain and for a planned route alike, because both reach this panel as
    one series. Finding the position is not the sample's index: the heights are
    sampled every 5 m and the line is drawn through the vertices somebody
    surveyed, so the two axes are different lengths and only a distance is shared
    between them. The dot travels in the same pane as the direction arrow and for
    the same reason — the map's path count is what phase 3 was accepted against.

    **And a reader can zoom into the curve**, which is a feature of the long
    chain and of a planned route rather than of the map's lines. Measured over
    the built graph: the median chain is drawn at 0.16 metres a pixel against a
    series carrying a height every 5.12 m, so the panel already magnifies every
    reading it holds some thirty times, and only 126 chains of 11,264 are drawn
    coarser than their own samples. The wheel is therefore taken over the curve
    exactly where zooming would show something and passed to the map everywhere
    else. The ceiling is the data's — one reading per pixel, 7.1x on the 42 km
    chain — and the scale stays true in both axes at every step, so zooming
    changes how much of the chain is on the panel and never its angle. Dragging
    moves the window, double-clicking returns the whole chain, and a new
    selection starts over.

    **It also writes the chain out as GPX**, from the same composed series it
    draws the curve from — which is the reason the two live in one closure
    rather than in two controls. A second composition in the page would be a
    third implementation of the same walk, and the file would eventually
    disagree with the profile drawn above the button that produced it.

    **And it takes a second way in**, for a series composed rather than read off
    one chain. A planned route has no chain and no row in the figures table, so
    ``window.trailsProfilePanel.series`` is handed the series and the figures
    already read from it; the gradient bands, the crosshair and the reduction
    all apply unchanged, and a stretch drawn straight across unrecorded ground
    is dashed in the curve as it is dashed on the map. The same object carries
    ``suspend``, for while something else owns the map's clicks, and the two
    things a second consumer must not write again: the walk that lays a run of
    edges end to end, and the metre this page measures distance with.

    **A route composed that way is written out here too**, from the same series
    the curve was drawn from, and it is a second kind of file rather than the
    same file with different numbers in it. What is different about it:

    - Its points travel as ``<wpt>`` elements before the track, each saying
      whether a reader set it or the map generated it. A waypoint is a GPX 1.1
      top-level element and not an extension, so it goes in its own place.
    - Its legs are listed on the track, each with its parts in order. **They
      cannot go on a ``<trkseg>``**: a segment is a stretch and a stretch breaks
      only where the ground stops, so four routed legs laid end to end are one
      segment.
    - Its track breaks at every crossing and nowhere else, because a crossing
      ends the stretch it was in and a crossing's own line is never written —
      there is no way in GPX to say a segment is a boat, and every reader would
      import one as a walked line across a fjord.
    - Its sources are as many as it runs over, each with the length it
      contributed and the licence that comes with it.
    - It says how much of it is waymarked in three buckets, and how much runs
      where no source records a path.

    The series a composed route arrives with carries both kinds of nothing —
    ground with no reading of it, and no ground at all — and they must not be
    confused: the first only drops an ``<ele>``, the second breaks the track.
    They are told apart by the stretch boundaries the composer records, never by
    inference from the series.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "profile_panel.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(
        self,
        groups: list[folium.FeatureGroup],
        figures: dict[str, dict[str, object]],
        title: str,
        chart_height: int,
        collapsed: bool,
        export: dict[str, Any] | None,
    ) -> None:
        """Initialize the panel.

        Args:
            groups: Feature groups whose lines can be selected
            figures: Mapping of CSS class to the figures of the line carrying it
            title: Panel heading, doubling as the fold handle
            chart_height: Height of the drawing area in pixels
            collapsed: Whether it starts folded away
            export: What the page needs to write a GPX file, or None for a panel
                that only draws. See :func:`add_profile_panel`.
        """
        super().__init__()
        self._name = "ProfilePanel"
        self.group_names = [group.get_name() for group in groups]
        self.figures_json = _script_json(_packed_figures(figures))
        self.length_icons_json = _script_json(
            {
                **LENGTH_ICONS,
                "licence": "Font Awesome Free 6.2.0 by @fontawesome, https://fontawesome.com -- Icons: CC BY 4.0. Copyright 2022 Fonticons, Inc.",
            }
        )
        self.title_json = _script_json(title)
        self.chart_height = int(chart_height)
        self.narrow_px = NARROW_PX
        self.short_px = SHORT_PX
        self.collapsed = collapsed
        # Through _script_json like everything else that lands inside a script
        # block: a licence or a source name carrying a '<' would otherwise close
        # it, and json.dumps leaves that character alone.
        self.export_json = _script_json(export)
        # The bands travel rather than being written into the template, so the
        # measurement that chose them and the colours that show them sit in one
        # documented place.
        self.gradient_json = _script_json(
            {
                "window": GRADIENT_WINDOW_M,
                "minRun": GRADIENT_MIN_RUN_M,
                "bands": [{"from": lower, "label": label, "colour": colour, "width": width} for lower, label, colour, width in GRADIENT_BANDS],
            }
        )


def add_profile_panel(
    fmap: folium.Map,
    groups: list[folium.FeatureGroup],
    title: str = "Elevation profile",
    #: Raised from 150 when the panel's five rows above the chart became two.
    #: Not decoration: the scale is the coarser of length-per-width and
    #: relief-per-height, so on a chain steep enough for the height to bind, a
    #: row given back is resolution. Measured on a 3 km chain dropping 807 m,
    #: these 55 px take it from 6.96 to 4.72 metres a pixel — its readings are
    #: 4.5 m apart, so that is as fine as the data goes. On a long gentle route
    #: the width binds and this changes nothing.
    chart_height: int = 205,
    collapsed: bool = True,
    export: dict[str, Any] | None = None,
) -> None:
    """Draw the selected chain's profile at the foot of the map, and offer it.

    Clicking a line opens the panel on its profile: distance against elevation,
    with the ascent, descent, high and low point the chain carries, and an arrow
    on the map pointing the way those figures were read. Clicking it again, or
    clicking empty terrain, closes it. The heading folds it away.

    **Every figure it shows is read, not computed.** They travel with the layers
    as :data:`CHAIN_FIGURES_ATTR`, put there by :func:`add_trails`; the elevation
    series is decoded from the payload :func:`add_routing_graph` put in the page,
    and only the curve and the distance under it come out of that. A chain whose
    series holds no reading at all — a ferry crossing, or a stretch outside the
    height model — says so instead of drawing a flat line at zero.

    **The crosshair marks its position on the map.** Hovering the curve puts a
    dot on the ground the reading came from, which is what makes a profile worth
    planning against: the climb in the panel and the climb on the map become one
    thing. A chain and a planned route both get it. It is taken back whenever the
    pointer leaves, the curve is redrawn or the window is dragged, so it can never
    name a place nobody is pointing at.

    **The curve can be zoomed into, where there is anything to see.** A wheel
    over it takes the window down to one height reading per pixel and no
    further; past that the panel would be magnifying the straight lines drawn
    between samples. On this map that is worth doing on 126 chains of 11,264 —
    the rest are already drawn finer than the ground under them was measured —
    and on every route long enough to be worth planning. Everywhere it is not
    worth doing the wheel goes to the map, as it always has. The scale stays
    true in both axes throughout, dragging moves the window, and a double click
    puts the whole chain back.

    **And it writes the chain out.** Given ``export``, the panel offers the
    selected chain as a GPX file — every vertex, a point wherever two are
    further apart than ``gapM``, an ``<ele>`` on each and no ``<time>`` on any —
    and says what the file will contain before the button is pressed rather than
    after: how many points, what it climbs, and which licence each source it
    draws on carries. The browser is the only thing that can write that file, so
    everything in it has to be in the page: the sources, their licences and
    their versions come through here, because nothing in a page can invent them.

    Call after the layers and after :func:`add_routing_graph`, whose payload it
    reads. It shares the bottom left with the legend and the scale bar and puts
    itself under both, so the order it is added in does not matter.

    Args:
        fmap: Map holding the layers
        groups: Feature groups returned by :func:`add_trails`
        title: Panel heading, which doubles as the fold handle
        chart_height: Height of the drawing area in pixels
        collapsed: Whether it starts folded away
        export: What the page needs to write a GPX file, or None for a panel
            that only draws one. It carries ``credits`` — the sources a chain of
            each dataset draws on, each with its licence and the version it was
            read at — ``heights``, the same for the height model every ``<ele>``
            comes from, ``fields``, the figure keys a track's ``<extensions>``
            are written from and the names they travel under,
            ``sourceLength``, the credit field a route states each source's
            contributed metres in, ``route`` and ``waypoint``, the names a
            planned route's own file is written with, and the writer's
            own settings: ``gapM``, ``decimals``, ``elevationDecimals``,
            ``coordinateDecimals``,
            ``namespace``, ``prefix``, ``creator``, ``description``,
            ``ascentMethod``, ``identitySeparator`` and ``filePrefix``. The
            names come from :mod:`trails.io.export.gpx`, which writes the same
            file from Python; that module's docstring says what the two agree
            on, how closely, and where the difference comes from.

    Raises:
        ValueError: If ``export`` leaves out something the page cannot write the
            file without. A page that quietly wrote ``undefined`` into a licence
            is worse than one that was never built.
    """
    if not groups:
        return

    figures: dict[str, dict[str, object]] = {}
    for group in groups:
        figures.update(getattr(group, CHAIN_FIGURES_ATTR, {}))
    if not figures:
        return

    if export is not None:
        missing = sorted(set(EXPORT_SETTINGS) - set(export))
        # And into the two that are dicts of names rather than single values.
        # Reported under the key they sit in, so a caller is told where to look
        # rather than that something called "partLength" is missing.
        for key, wanted in (("route", EXPORT_ROUTE_SETTINGS), ("waypoint", EXPORT_WAYPOINT_SETTINGS)):
            inside = export.get(key)
            if isinstance(inside, dict):
                missing += sorted(f"{key}.{name}" for name in set(wanted) - set(inside))
        if missing:
            raise ValueError(f"the page cannot write a GPX file without {', '.join(sorted(missing))}")

    _ProfilePanel(groups, figures, title, chart_height, collapsed, export).add_to(fmap)


class _PlanMode(MacroElement):
    """Plan mode: clicking a route together, leg by leg, and then working on it.

    Switch it on and every click appends a waypoint and works out the way from
    the one before, so a route grows as far as a reader cares to take it. Four
    edits then make it something to work on rather than to restart: **insert**
    into the middle, which splits a leg; **remove**, which merges two; **move a
    point earlier or later**, which changes which legs there are at all; and
    **drag**, which moves one where it stands.

    **The legs follow from the waypoints rather than being edited beside them.**
    Every edit rewrites the list of points and nothing else; a leg survives
    exactly when it still runs between the same two waypoints, and a waypoint
    that has moved is a new object rather than a mutated one. What each edit
    costs falls out of that, and so does the cancellation: a reply about ground
    a waypoint has since left arrives to find its leg no longer on the route.

    **One click, three meanings, decided in one place.** A click on a pin selects
    it, a click within a few pixels of the drawn route puts a point into that
    leg, and a click on anything else puts one on the end. Nothing the route
    draws is interactive — the leg a click landed on is found by hit-testing the
    geometry the page already holds — because a line that catches clicks would
    have to stop catching them the moment plan mode is switched off, which is the
    mistake the park boundary made for a fortnight.

    **A drag is throttled and asks the height service nothing until it ends.**
    Placing a point costs 19-76 ms including its Dijkstra, so the two legs a
    dragged waypoint moves are 40 to 160 ms and are settled every 120 ms rather
    than at the rate a pointer reports. A leg the network cannot carry is carried
    at its own straight length with no heights while the pointer is down: its
    ground is new at every position, the endpoint cache answers only for ends
    already visited, and asking anyway is an uncapped stream of requests to
    somebody else's service.

    **A leg has four kinds and they are parts of a leg, not legs.** That is what
    they are on the ground: a routed leg that takes a ferry is walked, then
    crossed, then walked again, and a leg drawn straight across a strait splits
    at the shoreline into the same two things. A model that knew only whole legs
    would have to be widened the first time either happened, and both happen
    here.

    ======= ==================== ==============================
    kind    distance counts as   profile
    ======= ==================== ==============================
    routed  on foot              read off the payload
    land    on foot              sampled on demand
    water   a **crossing**       none
    ferry   a **crossing**       none
    ======= ==================== ==============================

    **A crossing is never added to the walking distance and never to an ascent.**
    It is reported beside them — *42 km on foot · 2 crossings, 31 km* — and it
    contributes no curve at all, because a flat line at zero is a claim about
    ground that is not there.

    **Nothing here is drawn into the overlay pane.** The route, its waypoints and
    everything else this adds live in a pane of their own: what goes into the
    overlay pane is counted among the map's paths for ever after, and that count
    is an acceptance figure for every phase from the third.

    Hand-written, like the panel, the legend and the search: a routing library
    pulled from a CDN does not load on a ``file://`` page and fails silently, the
    way the OpenStreetMap tiles once did. So the heap, the search and the
    adjacency are all here, and they are cheap — the adjacency is derived from
    the payload's own columns rather than shipped beside them.

    **The route's series is laid out in one walk, not two.** The profile wants
    heights against distance and the exported file wants coordinates, and
    composing those separately would be two walks over one route that could
    disagree — each still looking like a route. So ``composeRoute`` produces the
    shape a chain's series has, which is what the panel's writer already knows
    how to read, and the geometry that existed per part but was never composed
    is what made this more than wiring.

    **What a route is made of is summed per edge**, where the edges are still in
    hand: which dataset drew each metre, whether anything says it is waymarked,
    and whether any source records a path along it. A part keeps its geometry
    and its heights and nothing downstream can get back to the edge a metre came
    from. Unknown is its own bucket and is never folded into unmarked, and a
    connector nobody drew was never asked rather than asked and unanswered.

    It arrives as ``window.trailsPlan``, whose ``state()`` says what the route is
    and whose ``place()`` is the entry a click uses, so a browser check can drive
    it and read it rather than screenshot it.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "plan_mode.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, plan: dict[str, Any], points: list[dict[str, object]]) -> None:
        """Initialize plan mode.

        Args:
            plan: What the page needs to route and to sample. See
                :func:`add_plan_mode`.
            points: The named things the map draws, as name, type and position
        """
        super().__init__()
        self._name = "PlanMode"
        # Through _script_json like everything else that lands inside a script
        # block: a service URL or a terrain name carrying a '<' would otherwise
        # close it, and json.dumps leaves that character alone.
        self.plan_json = _script_json(plan)
        # And these especially: every one of them is a name out of somebody
        # else's register, and one of them holding '</script>' would end the
        # page's whole script block.
        self.points_json = _script_json(points)


def add_plan_mode(fmap: folium.Map, plan: dict[str, Any], points: list[folium.FeatureGroup] | None = None) -> None:
    """Let a reader click a route together over the graph in the page.

    Switch it on and every click appends a waypoint, snapping to the network
    where one is within ``snapM`` and keeping the raw point beyond that. A
    waypoint can then be selected, removed, moved a place earlier or later in the
    sequence, dragged where it stands, or put into the middle of a leg by
    clicking the route; the route, its figures and its profile follow. The way
    from the point before is found with Dijkstra over the weighted graph — the
    cost of an edge is its length times its source's factor, both out of the
    payload's header, and a crossing costs the header's flat figure instead.
    Where no way exists the leg is drawn straight, its heights fetched from the
    height service on demand and cached by its two ends.

    **The four kinds of leg are parts of a leg, not legs.** A routed leg that
    takes a ferry is walked, then crossed, then walked; a straight leg over a
    strait splits at the shoreline into the same two things, and the samples are
    what split it. Walking and crossing are reported apart, always, and a
    crossing carries no profile at all.

    The route's profile goes to the panel :func:`add_profile_panel` put in the
    page, through the second way in that panel offers — so call this after both
    that and :func:`add_routing_graph`. The route is drawn into a pane of its
    own rather than the overlay pane, because what goes in there is counted among
    the map's paths for ever after. **A waypoint is a marker and does go into the
    marker pane**: a circle marker cannot be dragged — added to the map its
    ``dragging`` is undefined and ``draggable`` is ignored — so a five-point
    route costs five markers there and, drawing no path, gives eight back in its
    own pane.

    Args:
        fmap: Map holding the graph and the panel
        plan: What the page needs, none of it invented here.
            ``heightsUrl``, ``heightsCrs``, ``heightsBatch`` and
            ``heightsWorkers`` are the height service, the coordinates it is
            asked in, its own cap on points per request and the concurrency the
            build settled on; ``heightsTiles`` is :meth:`HeightTiles.as_settings`
            where the map carries height tiles instead, and then the service
            is not asked at all -- one of the two has to be there;
            ``terrainModel`` and ``seaTerrain`` are the two
            answers that classify a sample — what makes it a ground height, and
            what makes it sea rather than ground; ``sampleStepM`` and
            ``ascentThresholdM`` are the build's own sampling step and ascent
            threshold, which a leg sampled on demand has to be read under or the
            two halves of one profile answer differently; ``snapM`` is how near
            a click has to land to be taken as a node, and ``snapPx`` the same
            thing measured on the screen — a gesture snaps within whichever is
            the smaller, so that pinching in makes a tap mean the line under it
            and not a line a finger away, while a waypoint read out of a file
            uses ``snapM`` alone and answers the same at every zoom; ``maxStraightM`` is how
            far a leg may be drawn straight before it is refused, which bounds
            what one misclick can ask of a public service; ``offPathFactor``
            is what a metre of open ground costs against a metre of path, in
            the same currency the edge costs are in, and it is what decides
            whether a way to somewhere off the network goes round by the paths
            or straight across; ``waterFactor`` is the same for a metre of
            open ground that the graph's water grid says is sea or lake,
            which is what sends a way to a headland round by the road rather
            than across the sound in front of it -- and a page whose graph
            carries no grid prices every metre as ground; ``crossingKind`` and
            ``connectorKind`` are what the payload's header calls a crossing and
            an inferred connector, which the page tests every edge it routes over
            against — spelled in the page instead, a rename would leave it
            reading a ferry as walked ground; ``paddleKind`` identifies water edges,
            reachable only in kayak mode; ``portageFactor`` multiplies walking
            prices in that mode, while paddled edges keep their source factor
            and ferries keep their flat price; ``touchedM`` is how much of a
            route has to lie inside a protected area before it says so, and
            ``namedM`` how near a waypoint has to land to a named thing to be
            called after it. The names come from
            :mod:`trails.io.sources.hoydedata`, :mod:`trails.routing.elevation`,
            :mod:`trails.routing.protection` and :mod:`trails.routing.sources`.
        points: Feature groups whose named points a waypoint may be called
            after, from :func:`add_points` and :func:`add_labelled_points` given
            a ``point_type``. Without them a route's waypoints are numbered,
            which is what they were before this existed.

    Raises:
        ValueError: If ``plan`` leaves out something the page cannot route or
            sample without. A page that quietly sampled every 50 m, or read a
            climb at no threshold at all, would look exactly like one that did
            neither.
    """
    missing = sorted(set(PLAN_SETTINGS) - set(plan))
    if missing:
        raise ValueError(f"the page cannot plan a route without {', '.join(missing)}")
    if plan["heightsTiles"] is None and not plan["heightsUrl"]:
        raise ValueError("the page cannot sample a straight leg without either heightsUrl or heightsTiles")
    absent = sorted(set(PLAN_GPX_SETTINGS) - set(plan.get("gpx") or {}))
    if absent:
        raise ValueError(f"the page cannot read a GPX back without gpx.{', gpx.'.join(absent)}")

    named: list[dict[str, object]] = []
    for group in points or []:
        named.extend(getattr(group, NAMED_POINTS_ATTR, []))
    _PlanMode(plan, named).add_to(fmap)


@dataclass(frozen=True)
class LegendRow:
    """One row of the legend, and the layer its checkbox switches.

    Attributes:
        label: The row's text. Written as text and never as markup, so a label
            holding ``<15 km`` stays a label rather than becoming a tag.
        colour: CSS colour of the swatch drawn before the label
        layer: The layer the checkbox adds to and removes from the map, or
            ``None`` for a row that only explains a colour
        glyphs: The glyphs a pin layer drew, by name in :data:`MARKER_ICONS`.
            Given any, the row's key is those pins in the row's colour rather
            than a bar -- a bar never said whether the layer's pins were houses
            or tents, and once one layer draws both, it cannot.
    """

    label: str
    colour: str
    layer: Any = None
    glyphs: tuple[str, ...] = ()


def _legend_pin(colour: str, icon: str) -> str:
    """Draw one pin at legend size: the bulb in the row's colour, the glyph in it.

    Half the size a pin is drawn at on the map, and the same two paths, so the
    key looks like the thing it explains.

    Args:
        colour: CSS colour of the bulb -- a hex value here, as the legend's rows
            carry, not a name from :data:`PIN_COLOURS`
        icon: Which of :data:`MARKER_ICONS` to draw in it

    Returns:
        An inline ``<svg>``.

    Raises:
        ValueError: If the glyph is one this page does not draw.
    """
    if icon not in MARKER_ICONS:
        raise ValueError(f"no outline for {icon!r}; this page draws " + ", ".join(sorted(MARKER_ICONS)))
    box, path = MARKER_ICONS[icon]
    return (
        f'<svg width="{PIN_WIDTH // 2}" height="{PIN_HEIGHT // 2}" viewBox="0 0 {PIN_WIDTH} {PIN_HEIGHT}" xmlns="http://www.w3.org/2000/svg">'
        f'<path fill="{colour}" d="{PIN_SHAPE}"/>'
        f"<svg x='{PIN_WIDTH / 2 - 6.5:.1f}' y='7' width='13' height='13' viewBox='{box}'><path fill='white' d='{path}'/></svg></svg>"
    )


class _PackIO(MacroElement):
    """The pack codec and row ledger shared with the service worker."""

    _template = Template("{% macro script(this, kwargs) %}" + PACK_IO + "{% endmacro %}")


class _OfflinePanel(MacroElement):
    """The terrain a reader asked to keep, the switch that proves they have it,
    and the way to get the space back.

    **Everything but the ground already worked with the network off.** Selecting
    a chain and reading its whole elevation profile costs zero requests, routing
    costs zero, the search and the exports are in the document, and the worker
    keeps the page itself. What was left was Kartverket's tiles, kept
    opportunistically -- whatever the reader happened to pan over, capped at 500
    and trimmed oldest-first. That is not a map somebody can walk with, and
    nothing on the page ever said so.

    **Four things, and the first is the one that matters most.**

    - *Whether this browser can keep anything at all.* The page has computed
      ``window.trailsWorker.why`` since the worker was added and showed it
      nowhere. On iOS a service worker exists in Safari and in a home-screen web
      app and in no third-party browser, so for some readers every other feature
      here is already dead and the page was silent about it.
    - *A switch.* On, the worker answers tiles from the cache and never touches
      the network, which is what makes coverage checkable at home rather than
      discoverable in a valley.
    - *A chooser*, because a switch that silently gives a blank map is a switch
      that lied. Turning it on with nothing kept opens it.
    - *Delete*, because a gigabyte somebody cannot get rid of from inside the
      thing that took it is a gigabyte taken without asking.

    **Four scopes, all counted in packs.** The whole map is the finite tree box,
    offered to z17 on both providers: 9,162 packs for Lomsdal-Visten and 2,274 for
    Abisko. The phone's phase-1b pack readings remove the old per-tile row cap.
    The other scopes are a band along the route, a turned rectangle round it,
    and an area the reader draws. Each includes the whole box's z8–z11 overview.

    The estimate uses per-level mean pack bytes from the built indexes. The
    whole box at z17 sets the budget. A lazy parent iterator resolves each
    layer's selected tiles into packs, visits each parent once, and supplies
    both the estimate and the six concurrent downloaders. No pack address list
    is retained. The store holds ArrayBuffers; its count and actual byte total
    commit with each new row. A scalar ledger per tree/stand lets an old stand
    be deleted without walking the store.

    **The selection is drawn on the map, and drawing it is where two obvious
    implementations are wrong.** It is a ``GridLayer`` whose tiles are canvases,
    so Leaflet only ever makes the tiles in view and the preview costs the same
    at 131,000 kept tiles as at 400. Inside one of those canvases: testing only
    the screen tile's centre paints nothing at all when zoomed out, and filling
    the whole screen tile when it holds *any* kept tile turns a valley into a
    county -- reported from a phone, where an area a few kilometres across was
    painted a hundred kilometres wide. What is right is drawing the kept tiles as
    sub-rectangles of the screen tile, and drawing nothing at all once they are
    under a pixel rather than rounding a speck up to the whole tile.

    **The set is computed once at the chosen zoom and halved down to z11.** A
    tile at z-1 is the tile at z with both coordinates shifted right, so one pass
    answers every level below it. Each level gets its own one-tile margin, but
    what is passed downwards is the **unpadded** set -- otherwise the margin
    compounds on the way down and z11 ends up several tiles wider than it was
    asked for. ``FLOOR`` is the coarsest zoom a reader may *pick*; it is not the
    floor of the pyramid, which is z11, because a map that cannot be zoomed out
    of is not a map anybody navigates with.

    **The download does not go through the worker**, and the reason is a defect
    it would otherwise have. Requests are made with ``cache: 'reload'``, which
    the worker passes through untouched; without that a download started while
    the switch was on would be answered by the worker's own blank tile and the
    reader would be told their park was kept.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "offline_panel.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, provider: Provider = PROVIDERS["kartverket"], companions: Companions = ROOT) -> None:
        """Initialize the panel.

        Args:
            provider: Whose tiles are kept: how deep they go and what they weigh.
            companions: The database and the cache names, which are the
                worker's too.
        """
        super().__init__()
        self._name = "OfflinePanel"
        self.top = provider.top
        self.cap = provider.cap
        self.pack_weight_json = _script_json({str(level): size for level, size in provider.pack_weight.items()})
        self.heights_json = _script_json(provider.heights.as_settings() if provider.heights else None)
        self.shade_json = _script_json(provider.shade.as_settings() if provider.shade else None)
        self.slope_json = _script_json(provider.slope.as_settings() if provider.slope else None)
        self.vegetation_json = _script_json(provider.vegetation.as_settings() if provider.vegetation else None)
        self.forest_json = _script_json(provider.forest.as_settings() if provider.forest else None)
        self.mire_json = _script_json(provider.mire.as_settings() if provider.mire else None)
        self.tile_prefix_json = _script_json(provider.tiles)
        extent = provider.extent
        self.extent_json = _script_json({"w": extent[0], "s": extent[1], "e": extent[2], "n": extent[3]})
        self.database = companions.database
        self.cache = companions.cache


class _Legend(MacroElement):
    """The legend, which is also the layer control.

    **One panel rather than two.** They said very nearly the same thing: of the
    30 rows the legend drew, 23 named a layer the control also listed, one named
    the same layer under a different name, and six were kinds inside a single
    layer. Two panels of the same list is two places to look and two places to
    drift, and measured on this map they cost a 297 x 557 box and a 441 x 737
    one for the privilege.

    So the legend keeps its colours and gains the checkbox, and folium's
    ``LayerControl`` goes. **What has to come with it is the part that control
    did quietly**: a layer added with ``show=False`` is on the map like any other
    until that control's template takes it off again. Without this the two layers
    this map starts with switched off would arrive switched on.

    A control rather than a box floating over the page, for the reason the search
    is one: a panel outside the map container swallows the wheel. It takes the
    wheel itself only where it has somewhere left to scroll, and lets it through
    to the map otherwise.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "legend.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(self, title: str, rows: list[LegendRow], collapsed: bool) -> None:
        """Initialize the legend.

        Args:
            title: Legend heading, doubling as the fold handle
            rows: The rows, in the order they are drawn
            collapsed: Whether it starts folded away
        """
        super().__init__()
        self._name = "Legend"
        self.title_json = _script_json(title)
        self.collapsed = collapsed
        self.layer_names = [row.layer.get_name() if row.layer is not None else "null" for row in rows]
        self.rows_json = _script_json(
            [
                {
                    "label": row.label,
                    "colour": row.colour,
                    "shown": bool(getattr(row.layer, "show", True)),
                    "glyphs": [_legend_pin(row.colour, glyph) for glyph in row.glyphs],
                }
                for row in rows
            ]
        )
        self.base_names: list[str] = []
        self.base_labels_json = "[]"
        self.base_shown_json = "[]"
        # The relief overlay's variable in the page, or `null`: filled in at
        # render, beside the base layers, since it is drawn in their panel.
        self.relief_name = "null"
        # And the slope overlay's, with the rows that explain its colours.
        self.slope_name = "null"
        self.slope_classes_json = "[]"
        # And the vegetation and forest overlays' (§6.11), likewise.
        self.vegetation_name = "null"
        self.vegetation_classes_json = "[]"
        self.forest_name = "null"
        self.forest_colour_json = _script_json(ForestTiles.colour())
        # And the mire overlay's (§6.13), with the rows for the classes its
        # tree carries.
        self.mire_name = "null"
        self.mire_classes_json = "[]"
        # What the two switches above the layers remember themselves under,
        # filled in at render from the map's own companions: the same name the
        # caches and the offline switch carry, so two maps on one origin do not
        # answer for each other.
        self.ground_key_json = _script_json(f"{ROOT.cache}-ground-")

    def render(self, **kwargs: Any) -> Any:
        """Collect the base layers, then render.

        They are whatever base layers the map holds when this renders, which is
        why the legend has to be added after them. Folium's own control walks the
        same children for the same reason.

        Args:
            **kwargs: Passed through to the parent

        Returns:
            Whatever branca's own render returns, which it does not document
        """
        labels: list[str] = []
        shown: list[bool] = []
        self.base_names = []
        for child in self._parent._children.values() if self._parent is not None else ():
            if isinstance(child, folium.TileLayer) and child.control and not child.overlay:
                self.base_names.append(child.get_name())
                labels.append(str(child.layer_name))
                shown.append(bool(child.show))
        self.base_labels_json = _script_json(labels)
        self.base_shown_json = _script_json(shown)
        relief = getattr(self._parent, MAP_SHADE_ATTR, None) if self._parent is not None else None
        self.relief_name = relief.get_name() if relief is not None else "null"
        slope = getattr(self._parent, MAP_SLOPE_ATTR, None) if self._parent is not None else None
        self.slope_name = slope.get_name() if slope is not None else "null"
        self.slope_classes_json = _script_json(SlopeTiles.classes()) if slope is not None else "[]"
        vegetation = getattr(self._parent, MAP_VEGETATION_ATTR, None) if self._parent is not None else None
        self.vegetation_name = vegetation.get_name() if vegetation is not None else "null"
        self.vegetation_classes_json = _script_json(VegetationTiles.classes()) if vegetation is not None else "[]"
        forest = getattr(self._parent, MAP_FOREST_ATTR, None) if self._parent is not None else None
        self.forest_name = forest.get_name() if forest is not None else "null"
        mire_layer = getattr(self._parent, MAP_MIRE_ATTR, None) if self._parent is not None else None
        self.mire_name = mire_layer.get_name() if mire_layer is not None else "null"
        drawn = getattr(mire_layer, MAP_MIRE_CLASSES_ATTR, None) if mire_layer is not None else None
        self.mire_classes_json = _script_json(drawn) if drawn is not None else "[]"
        companions = getattr(self._parent, MAP_COMPANIONS_ATTR, ROOT) if self._parent is not None else ROOT
        self.ground_key_json = _script_json(f"{companions.cache}-ground-")
        return super().render(**kwargs)


def add_legend(fmap: folium.Map, title: str, entries: dict[str, str] | list[LegendRow], collapsed: bool = False) -> None:
    """Add the legend, which is also the map's layer control.

    Every row explains a colour, and a row given a layer also switches it. The
    base maps sit above them as radio buttons. **There is no separate layer
    control**: this replaces it, so nothing else may add one, and this has to be
    added after every layer it is to list.

    Enough sources make it tall enough to hide the terrain behind it, so it folds
    away at a click on its heading and scrolls within 70 % of the window.

    Args:
        fmap: Map to add the legend to
        title: Legend heading, which doubles as the fold handle
        entries: The rows in the order they are drawn. A mapping of label to
            colour gives a legend that only explains colours; a list of
            :class:`LegendRow` gives one that switches layers too.
        collapsed: Whether it starts folded away
    """
    rows = [LegendRow(label, colour) for label, colour in entries.items()] if isinstance(entries, dict) else list(entries)
    _Legend(title, rows, collapsed).add_to(fmap)


class _Chrome(MacroElement):
    """The one way into everything this map can do, and the panel that tells the others where to stand.

    **The map opens showing a map.** Everything else is reached for. On a wide
    screen the reach is a rail of icons down the left edge and a panel that docks
    beside it; on a narrow one it is a burger and a panel over the whole screen.
    One layout decided by one number, because the axis is the width of the map
    and not the kind of device: a desktop window dragged to 390 px has exactly
    the problem a phone has, and a phone held sideways no longer has it.

    **It adopts the controls rather than replacing them.** The search, the
    legend, the base-map picker and the plan control keep every line of their own
    behaviour and lose only their frame and their corner; this moves their
    containers into a dock it owns and shows one at a time. Nothing about what
    they do had to be rewritten to make them share a screen, which is the whole
    reason it is built this way.

    **And every popup docks.** Measured on the built page at 390 x 844, a tap on
    a trail put a 367 x 386 popup and a 393 px profile panel on an 844 px screen
    and left 6.9 % of the map visible — with 113,036 px² of that popup *behind*
    the legend, because Leaflet's popup pane is z-index 700 and a control corner
    is 1000. A popup that docks cannot be behind anything, so the fix and the
    layout are one change rather than two.

    The dock is appended to the map container and not to a control corner,
    deliberately: on a narrow screen a panel has to be able to cover the corners,
    and a control cannot cover its own siblings.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
"""
        + files("trails.visualization").joinpath("js", "chrome.js").read_text(encoding="utf-8")
        + """        {% endmacro %}
    """
    )

    def __init__(
        self,
        credits: dict[str, list[dict[str, str]]] | None,
        extent: Bounds | None = None,
        provider: Provider = PROVIDERS["kartverket"],
        untranslated: list[str] | None = None,
    ) -> None:
        """Initialize the chrome.

        Args:
            credits: What each dataset is called, licensed under and read at, as
                :func:`source_credits` composes it. Rendered into the *Sources*
                panel. ``None`` leaves that panel saying it was handed nothing,
                which is truthful and is not the same as an empty list.
            extent: The ground this map draws, as (min_lon, min_lat, max_lon,
                max_lat), or None where the caller did not say. A reader whose
                own position falls outside it is told so rather than shown a dot
                on a blank.
            provider: Whose sheets the base-map picker offers, for its hint, and
                what a tile's address starts with, for the timing readout.
            untranslated: The values the build's label tables did not know,
                handed to the page as ``window.trailsUntranslated`` so a check
                can count them.
        """
        super().__init__()
        self._name = "Chrome"
        self.narrow_px = NARROW_PX
        self.provider_label = provider.label
        self.tile_prefix_json = _script_json(provider.tiles)
        self.credits_json = _script_json(credits or {})
        # **The words the build's label tables did not know**, handed to the
        # page so a browser check can count them. A register that renames a
        # type puts its own word on the map -- visibly, by design -- and this
        # is how that becomes a reading rather than something a reader notices.
        self.untranslated_json = _script_json(sorted(untranslated or []))
        # What this map draws, so the page can tell a reader standing outside it
        # that there is nothing here to show them. `null` where nobody said.
        self.extent_json = _script_json(None if extent is None else [[extent[1], extent[0]], [extent[3], extent[2]]])


def add_chrome(fmap: folium.Map, credits: dict[str, list[dict[str, str]]] | None = None, untranslated: list[str] | None = None) -> None:
    """Put every control behind one way in, and let the map open showing a map.

    **Add this last.** It adopts the containers of the search, the legend, the
    base-map picker and the plan control, so all four have to exist by the time
    it runs — and it hides the profile panel until something is selected, which
    means the panel has to have been added too.

    Args:
        fmap: Map to add it to
        credits: What to put in the *Sources* panel, keyed by source, as
            :func:`source_credits` composes it
    """
    # Before the dock, because the dock reads `window.trailsOffline.holder`:
    # folium renders a map's children in the order they were added.
    provider = provider_of_map(fmap)
    _PackIO().add_to(fmap)
    _OfflinePanel(provider, companions_of_map(fmap)).add_to(fmap)
    _Chrome(credits, getattr(fmap, MAP_BOUNDS_ATTR, None), provider, untranslated).add_to(fmap)

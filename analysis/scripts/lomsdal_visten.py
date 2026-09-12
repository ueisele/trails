"""Build an interactive hiking map for a national park: Lomsdal-Visten, or Abisko.

Every line on this map is a **chain** out of the routing graph
(:mod:`trails.network.norway` or :mod:`trails.network.sweden`), so a drawn line
and a selectable track are the same object. Each source still draws its own
layer in its own colour, and where several of them describe one valley their
lines still lie over each other as separate objects — the merged graph stays
underneath, with every edge naming the chain it lies on.

For Lomsdal-Visten it combines seven sources:
  * Turrutebasen (Kartverket/Geonorge) - official marked routes, with DNT-maintained
    segments highlighted separately
  * UT.no - hand-researched DNT route suggestions for this park, read from
    ``analysis/routes/lomsdal-visten-ut-routes.toml``
  * Traktorveg og Skogsbilveg WFS (Kartverket) - the detailed FKB path network the
    topographic base map draws at high zoom; by far the richest source here
  * N50 Kartdata (Kartverket) - the generalised path network the base map draws at
    lower zoom, kept as a cross-check
  * OpenStreetMap via Overpass - community-mapped paths, tracks and shelters
  * Stedsnavn/SSR (Kartverket) - terrain names, and the road names N50 lacks
  * Naturbase (Miljødirektoratet) - the national park boundary used for clipping

Which sources go in is not a choice: a graph missing one is not smaller, it is
wrong. The layer control does the visual job instead, per layer and without a
rebuild.

For Abisko, five (``analysis/docs/abisko-decisions.md`` §5):
  * Naturvårdsverket's trail register (*Leder*) - the marked state trails with
    their names, marking and description; also the park boundary, every
    protected area and the facilities along the trails
  * Topografi 50 (Lantmäteriet) - the marked trails, the worn paths, the roads,
    the ferries, the cabins, the water, and the size the map letters a name at
  * Ortnamn (Lantmäteriet) - every place name, typed and in its language
  * OpenStreetMap via Overpass - community-mapped paths and shelters
  * Markhöjdmodell (Lantmäteriet) - the 1 m height model, read off a mosaic
    in the build and off the height tiles in the page

Produces an HTML map and GPX exports under ``analysis/output/``.

**Which park is an option, and the park decides the rest**: what the page and
its files are called, whose tiles are drawn, which names its worker, manifest,
icons and database go by (``--park lomsdal-visten`` keeps every name the first
map has always had), the box or the register lookup the ground comes from,
and -- through the country -- which registers are read, what a popup says
and what an exported file credits. See :data:`PARKS` and :data:`BUILDS`.

Usage::

    uv run python analysis/scripts/lomsdal_visten.py
    uv run python analysis/scripts/lomsdal_visten.py --approach-km 10
    uv run python analysis/scripts/lomsdal_visten.py --park abisko
"""

import argparse
import dataclasses
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Protocol

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import box
from trails.io.export.gpx import (
    AREA_ELEMENT,
    AREA_FORM_ATTR,
    AREA_ID_ATTR,
    AREA_LENGTH_ATTR,
    AREA_NAME_ATTR,
    AREAS_ELEMENT,
    DEFAULT_EXTENSION_FIELDS,
    ELEVATION_DECIMALS,
    EXTENSION_DECIMALS,
    LEG_ELEMENT,
    LEGS_ELEMENT,
    PART_ELEMENT,
    PART_KIND_ATTR,
    PART_KIND_TRACK,
    PART_LENGTH_ATTR,
    ROUTE_EXTENSION_FIELDS,
    ROUTE_KIND,
    ROUTE_KIND_FIELD,
    SOURCE_CREDIT_FIELDS,
    SOURCE_LENGTH_FIELD,
    TRAILS_NAMESPACE,
    TRAILS_PREFIX,
    WAYPOINT_AREA_FIELD,
    WAYPOINT_ENTERS,
    WAYPOINT_GENERATED,
    WAYPOINT_LEAVES,
    WAYPOINT_ORIGIN_FIELD,
    WAYPOINT_SET,
    WAYPOINT_STAGE_FIELD,
    export_to_gpx,
)
from trails.io.sources import (
    geonorge,
    hoydedata,
    markhojd,
    n50,
    naturbase,
    naturvardsregistret,
    ortnamn,
    overpass,
    stedsnavn,
    topografi50,
    traktorvegsti,
    ut,
)
from trails.network import graphs, norway, sweden
from trails.network.norway import (
    FERRIES,
    FKB,
    N50_PATHS,
    N50_ROADS,
    OSM,
    PLACEHOLDER_IDENTITIES,
    TURRUTEBASEN,
    UT,
)
from trails.network.sweden import LEDER, T50_PATHS, T50_ROADS, T50_TRAILS
from trails.routing import (
    BRIDGE,
    DEFAULT_GAP_M,
    DEFAULT_TOUCHED_M,
    FERRY,
    IDENTITY_SEPARATOR,
    Network,
    chain_order,
    chain_tracks,
    elevation,
    parts_of,
    translate_joined,
    whole_way_length,
)
from trails.utils.geo import attach_nearest, compass_points, endpoint_bearings, thin_points
from trails.visualization import maps
from trails.visualization.encoding import PAYLOAD_CRS, Payload, encode_graph
from trails.visualization.water import river_table, water_mask


@dataclass(frozen=True)
class Park:
    """One map: what it is called, where it is, and whose ground it draws."""

    #: The park, as written into legends, exported files and their titles.
    name: str
    #: The page's object key without ``.html``, and the prefix of every file
    #: this script writes for it.
    stem: str
    #: ISO 3166 country, which decides the source set and everything read
    #: off it: :data:`BUILDS`.
    country: str
    #: The word after the name in the legend's title: what the place is, in the
    #: language of the map it is drawn on.
    kind: str
    #: The sheet drawn underneath, and with it the tile provider.
    base: maps.BaseMap
    #: Sheets offered beside it in the picker.
    extras: tuple[maps.BaseMap, ...]
    #: The names of the worker, the manifest, the icons, the database and the
    #: caches. :data:`maps.ROOT` for the first map, never renamed; a named set
    #: for every other map on the same origin.
    companions: maps.Companions
    #: The ground, as (min_lon, min_lat, max_lon, max_lat) -- or None, and the
    #: boundary is looked up by name in the country's protected-area register.
    bounds: maps.Bounds | None
    #: The catalogue of UT.no routes under ``analysis/routes``, if there is one.
    ut_routes: str | None

    @property
    def app_name(self) -> str:
        """What the map is called as a thing rather than as a place: the page's
        title, the label under a home-screen icon, and both names in the manifest.

        **Separate from the park's name on purpose.** That one is the park, and it
        is written into legends, exported files and the titles of the other pages
        this script builds, where "Atlas" would be wrong. This one names the
        application.
        """
        return f"{self.name} Atlas"


#: The maps this script can be asked for. The first keeps every name it has
#: always had; the second is what analysis/docs/abisko-decisions.md decided
#: (§2 the box, §6.2 the names).
PARKS: dict[str, Park] = {
    "lomsdal-visten": Park(
        name="Lomsdal-Visten",
        stem="lomsdal-visten",
        country="NO",
        kind="nasjonalpark",
        base=maps.BaseMap.KARTVERKET_TOPO,
        extras=(maps.BaseMap.KARTVERKET_GRAYSCALE,),
        companions=maps.Companions.of("lomsdal-visten"),
        bounds=None,
        ut_routes="lomsdal-visten-ut-routes.toml",
    ),
    "abisko": Park(
        name="Abisko",
        stem="abisko",
        country="SE",
        kind="nationalpark",
        base=maps.BaseMap.LANTMATERIET_TOPO,
        # The colour sheet only: the grey one was never used on the first map.
        extras=(),
        companions=maps.Companions.of("abisko"),
        # West on the Norwegian border, south past Áhpparjávri, east at the
        # western tip of Rautasjaure, north with the whole E10 inside. **The
        # box is the extent**, not a band round the park: it is what the
        # tiles were copied for and the height mosaic was read over, and the
        # graph, the water grid and the page all cover exactly it.
        bounds=(18.15, 68.17, 19.00, 68.46),
        ut_routes=None,
    ),
}

#: Substrings identifying DNT (Den Norske Turistforening) as maintainer.
DNT_PATTERN = "DNT|Turistforening"

#: Share of its own length a chain must have inside the park to be drawn as a
#: park layer rather than an approach one. A chain is never cut at the boundary,
#: so it goes whole into whichever layer holds the greater part of it.
IN_PARK_SHARE = 0.5

#: Place types that act as trailheads around this park, as opposed to settlements.
TRAILHEAD_PLACE_TYPES = ("farm", "isolated_dwelling")

#: Label colour per terrain feature type. The topographic backdrop is uniformly
#: pale (luminance 0.77-0.98, its water a washed-out #e0fefe), so these are dark,
#: saturated versions of the expected hue: readable everywhere, and far enough
#: from the map's own colours that a river label never merges into a river.
TERRAIN_NAME_COLORS = {
    "elv": "#0288d1",  # running water, lighter blue
    "bekk": "#0288d1",
    "foss": "#0288d1",
    "vann": "#01579b",  # standing water and ice, dark navy
    "tjern": "#01579b",
    "isbre": "#01579b",
    "dal": "#6d4c41",  # valleys and passes, brown
    "skar": "#6d4c41",
    "fjell": "#263238",  # rock and slopes, near-black slate
    "fjellområde": "#263238",
    "li": "#263238",
    "bakke": "#263238",
    "myr": "#2e7d32",  # marsh, dark green
    "mo": "#8d6e63",  # sandy flats, pale brown
    "seter": "#7b1fa2",  # summer farms are cultural, not terrain
}

#: Used for any type without an entry above.
TERRAIN_NAME_DEFAULT_COLOR = "#455a64"

#: Glyph drawn before each terrain name, so the feature type reads without
#: relying on colour alone. Deliberately plain Unicode from widely supported
#: blocks rather than Font Awesome, which has no valley, lake or marsh icon and
#: would tie the labels to a CDN.
TERRAIN_NAME_SYMBOLS = {
    "elv": "≈",  # wavy lines, running water
    "bekk": "≈",
    "foss": "≈",
    "vann": "●",  # a filled body of standing water
    "tjern": "●",
    "isbre": "◇",  # open diamond, ice
    "dal": "∨",  # V, the classic valley cross-section
    "skar": "∨",
    "fjell": "▲",  # a peak
    "fjellområde": "▲",
    "li": "◢",  # a slope
    "bakke": "◢",
    "myr": "≋",  # wet ground hatching
    "mo": "▭",  # flat open ground
    "seter": "⌂",  # a hut
}

#: Used for any type without a glyph above.
TERRAIN_NAME_DEFAULT_SYMBOL = "·"

#: Groups of types sharing one colour, for the legend.
TERRAIN_NAME_LEGEND = (
    ("running water", {"elv", "bekk", "foss"}),
    ("lakes and ice", {"vann", "tjern", "isbre"}),
    ("valleys and passes", {"dal", "skar"}),
    ("mountains and slopes", {"fjell", "fjellområde", "li", "bakke"}),
    ("marsh", {"myr"}),
    ("sandy flats", {"mo"}),
    ("summer farms", {"seter"}),
)

FKB_POPUP_FIELDS = {
    "typeveg": "Road type",
    "length_km": "Length (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

FERRY_POPUP_FIELDS = {
    "typeveg": "Ferry type",
    "length_km": "Crossing (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "survey_method": "Captured",
    "surveyed": "Captured on",
}

CABIN_POPUP_FIELDS = {
    "navn": "Name",
    "kind": "Type",
    "betjeningsgrad": "Service level",
    "hytteeier": "Owner code",
    "kommune": "Municipality",
}

TERMINAL_POPUP_FIELDS = {
    "name": "Quay",
    "operator": "Operator",
    "osm_id": "OSM ID",
}

#: A click now selects the arm of the road under the cursor rather than every
#: arm sharing its name, so both figures are needed and neither alone is true:
#: 3.2 km of Tveråvegen's 15.6.
ROAD_POPUP_FIELDS = {
    "road_name": "Road",
    "road_category": "Category",
    "length_km": "This stretch (km)",
    "whole_km": "Road in total (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "survey_method": "Captured",
    "surveyed": "Captured on",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

N50_POPUP_FIELDS = {
    "typeveg": "Road type",
    "rutemerking": "Waymarked",
    "vedlikeholdsansvarlig": "Maintained by",
    "medium": "Medium",
    "length_km": "Length (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "survey_method": "Captured",
    "surveyed": "Captured on",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

#: How N50's ``malemetode`` code reads in a popup. The code is the difference
#: between a path somebody saw and a line inherited off an older map, and in this
#: zone 47 % of N50's paths are the latter — some captured in the 1960s, at
#: accuracies as coarse as 50 m. Without it a popup asserts a path with no way to
#: judge the assertion. Turrutebasen writes the same thing out in words already.
SURVEY_METHOD_LABELS = {
    "fot": "Photogrammetry — seen in aerial imagery",
    "sat": "Satellite positioning — measured on the ground",
    "dig": "Digitised from a map",
    "pla": "From a plan",
    "gen": "Generated from other geometry",
    "ukj": "Unknown",
}

#: How the cross-source marking summary reads in a popup, per class. Distinct
#: from N50's ``rutemerking`` and Turrutebasen's ``marking``, which are what one
#: register says about its own lines: this is what *any* source says about the
#: ground under the line, and a popup showing both must not label them alike.
MARKING_LABELS = {
    "marked_m": "marked",
    "unmarked_m": "stated unmarked",
    "unknown_m": "not stated",
}

#: How a catalogue category reads in a popup.
UT_CATEGORY_LABELS = {
    "core": "Route in or through the park",
    "access": "Access or connection",
}

UT_POPUP_FIELDS = {
    "name": "Route",
    "category_label": "Kind",
    "length_km": "Track length (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

#: What UT.no states about the route, which is **their** claim and not this
#: map's measurement: it stood among the figures above and read as one of them,
#: disagreeing with the length by a kilometre and with the climb by 200 m. It
#: belongs under the same heading as their pages -- *published elsewhere, not by
#: this map* -- which is where the two can be compared without either pretending
#: to be the other.
UT_PUBLISHED_FIELDS = {"ut_summary": "UT.no states"}

#: Set above the UT.no links. Two of the four point at the park's own site
#: rather than at UT.no, so the heading names what they have in common instead
#: of naming a publisher: none of them comes from this map. The GPX among them
#: is the one that matters: it is UT.no's own recording, and the profile panel
#: offers this map's export of the same line a click away. The two disagree.
#: Measured on the 42 km Rundtur, theirs holds 1,330 points and states
#: +1,460 / -1,622 m where this map's holds 16,415 and states +1,722 / -1,867 —
#: a sparser series under the same 5 m threshold simply misses climbs. Theirs
#: also carries a timestamp on every point, which is what this map's writer
#: refuses so that a plan does not read as a walk somebody took. Two files of
#: one route, and only the words tell them apart.
UT_LINK_HEADING = "Published elsewhere, not by this map"

#: Clickable links in the UT.no popup. The route page and the park's own
#: description carry everything the geometry cannot: season, difficulty, the
#: state of the river crossings.
UT_LINK_FIELDS = {
    "ut_url": "→ Route page on ut.no",
    "guide_url_no": "→ Beskrivelse på lomsdalvisten.no",
    "guide_url_en": "→ Description on lomsdalvisten.no",
    "gpx_url": "→ UT.no's own GPX recording",
}

TRAIL_POPUP_FIELDS = {
    "trail_name": "Route",
    "trail_number": "Number",
    "difficulty": "Difficulty",
    "marking": "Marking",
    "trail_follows": "Follows",
    "special_hiking_trail_type": "Special type",
    "trail_significance": "Significance",
    "maintenance_responsible": "Maintained by",
    "length_km": "Length (km)",
    "whole_km": "Route in total (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "survey_method": "Captured",
    "surveyed": "Captured on",
    # 80 % of this register's geometry here is "Rett i kartet" — entered by the
    # people who maintain the route — and only 1 % each from FKB and N50. It is
    # the one line source in this map that is not a Kartverket derivative.
    "origin": "Geometry from",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

OSM_POPUP_FIELDS = {
    "name": "Name",
    "highway": "Type",
    "surface": "Surface",
    "sac_scale": "SAC scale",
    "trail_visibility": "Visibility",
    "length_km": "Length (km)",
    "whole_km": "Way in total (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    # Plural, and it is not pedantry: 64 % of these chains span more than one
    # OSM way — median 2, worst 33 — so a single id would be wrong for most of
    # them. The value is joined like every other multi-valued field.
    "osm_id": "OSM IDs",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

#: Popup for the OSM place layers, which carry only these three.
PLACE_POPUP_FIELDS = {
    "name": "Name",
    "kind": "Type",
    "osm_id": "OSM ID",
}

#: Popup for anything read straight out of the place-name register.
SSR_POINT_POPUP_FIELDS = {
    "name": "Name",
    "kind": "Type",
    "importance": "Importance",
    "kommune": "Municipality",
}

SHELTER_POPUP_FIELDS = {
    "name": "Name",
    "kind": "Type",
    "operator": "Operator",
    "osm_id": "OSM ID",
}

# ---- Sweden --------------------------------------------------------------------
# What the Swedish registers say, in a popup's words. The register's own
# columns are its spelling of a trail; Topografi 50's classes are Lantmäteriet's
# spelling of a path or a road, and are translated here, class by class, so a
# popup reads *footpath* where the product says *Gångstig*.

#: How Topografi 50's path and trail classes read. Every class the network
#: takes is here; one it does not know passes through in Swedish.
PATH_CLASS_LABELS = {
    "Gångstig": "footpath",
    "Vandringsled": "marked trail",
    "Vandrings- och vinterled": "marked trail, summer and winter",
    "Vinterled": "winter trail",
    "Traktorväg": "tractor road",
    "Cykelväg": "cycle path",
    "Elljusspår": "lit track",
    "Lämplig färdväg": "suitable route across the fell",
    "Svårorienterad gångstig": "path hard to follow",
}

#: How its road classes read. The product grades roads by width and surface
#: rather than by who may drive them, so there is no public/private split
#: here as there is in N50.
ROAD_CLASS_LABELS = {
    "Motorväg": "motorway",
    "Motortrafikled": "expressway",
    "Landsväg": "main road",
    "Landsväg liten": "minor main road",
    "Småväg": "small road",
    "Småväg enkel standard": "small road, simple standard",
    "Lokalgata stor": "local street",
    "Lokalgata liten": "local street, small",
    "Gata": "street",
}

#: What ``vagutforande`` says about the ground a path runs over. *Normal* is
#: the ground itself and says nothing worth a row.
BRIDGE_LABELS = {"Bro": "a bridge", "Underfart": "an underpass", "Normal": ""}

#: What ``skoterkorning_tillaten`` says. No information is no row.
SNOWMOBILE_LABELS = {"Ja": "allowed", "Nej": "not allowed", "Påbjuden": "designated snowmobile route", "Ingen information": ""}

#: What ``ruskmarkering`` says: brush marks, the winter marking of a trail.
BRUSH_LABELS = {"Ja": "brush-marked", "Nej": "", "Ingen information": ""}

#: The register's trails: what the register says about the trail, then the
#: figures this map measured on the chain. ``whole_km`` is the state trail's
#: whole length, because the state trail is the chain's identity.
LEDER_POPUP_FIELDS = {
    "trail_name": "Trail",
    "route": "State trail",
    "route_id": "Number",
    "trail_type": "Type",
    "marking": "Marking",
    "description": "Description",
    "protected_area": "Protected area",
    "length_km": "This stretch (km)",
    "whole_km": "State trail in total (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

#: Topografi 50's marked trails: named from the register where they lie on a
#: state trail, classed by Lantmäteriet, and dated by when Lantmäteriet last
#: wrote the line.
T50_TRAIL_POPUP_FIELDS = {
    "route_name": "State trail",
    "path_class": "Class",
    "over": "Over",
    "snowmobiles": "Snowmobiles",
    "brush": "Winter marking",
    "length_km": "This stretch (km)",
    "whole_km": "Trail in total (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "surveyed": "Written on",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

T50_PATH_POPUP_FIELDS = {
    "path_class": "Class",
    "over": "Over",
    "snowmobiles": "Snowmobiles",
    "brush": "Winter marking",
    "length_km": "Length (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "surveyed": "Written on",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

#: A road's identity is its number -- ``E10`` is one road across the box --
#: so ``whole_km`` is the numbered road's whole length. Street names exist in
#: the product and none of the 170 fragments over Abisko carries one.
T50_ROAD_POPUP_FIELDS = {
    "road_class": "Class",
    "road_name": "Road",
    "road_number": "Number",
    "length_km": "This stretch (km)",
    "whole_km": "Road in total (km)",
    "climb": "Ascent / descent",
    "high_low": "High / low point",
    "steepness": "Steepest",
    "surveyed": "Written on",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

T50_FERRY_POPUP_FIELDS = {
    "destination": "Destination",
    "length_km": "Crossing (km)",
    "surveyed": "Written on",
}

#: The winter-only lines, which are not chains and carry no figures: a legend
#: row that is off by default (decisions §6.5) and says what the line is.
WINTER_POPUP_FIELDS = {
    "kind": "Type",
    "name": "State trail",
}

#: Topografi 50's cabins carry no name of their own; the name comes off the
#: place-name register or OSM, and the row says which.
T50_CABIN_POPUP_FIELDS = {
    "name": "Name",
    "kind": "Type",
    "named_from": "Name from",
}

#: The register's facilities: bridges, shelters, privies, fireplaces.
FACILITY_POPUP_FIELDS = {
    "name": "Name",
    "kind": "Type",
    "subtype": "Kind",
    "description": "Description",
    "route": "State trail",
}

#: Footbridges, fords, telephones and car parks off the mountain-trail layer.
TRAIL_POINT_POPUP_FIELDS = {
    "kind": "Type",
}

#: Label colour per type of the place-name register, in the Norwegian
#: palette: running water lighter than standing, terrain near-black, marsh
#: green, ice navy, the built purple.
ORTNAMN_COLORS = {
    "TERRTX": "#263238",
    "GLACIÄRTX": "#01579b",
    "SANKTX": "#2e7d32",
    "VATTTX": "#01579b",
    "VATTDELTX": "#01579b",
    "VATTDRTX": "#0288d1",
    "BEBTX": "#7b1fa2",
    "BEBTÄTTX": "#7b1fa2",
    "ANLTX": "#7b1fa2",
}

#: And the glyph. The register does not say whether a terrain name is a
#: peak or a valley -- the name does, *-čohkka* a peak, *-vággi* a valley --
#: so terrain gets one glyph where SSR's types get four.
ORTNAMN_SYMBOLS = {
    "TERRTX": "▲",
    "GLACIÄRTX": "◇",
    "SANKTX": "≋",
    "VATTTX": "●",
    "VATTDELTX": "●",
    "VATTDRTX": "≈",
    "BEBTX": "⌂",
    "BEBTÄTTX": "⌂",
    "ANLTX": "⌂",
}

#: Groups of types sharing a legend row, in the register's own order.
ORTNAMN_LEGEND = (
    ("terrain, glaciers and marsh", ortnamn.TERRAIN_TYPES),
    ("lakes and rivers", ortnamn.WATER_TYPES),
    ("settlements, cabins and facilities", ortnamn.SETTLEMENT_TYPES),
)

#: The register ranks nothing, so a name is drawn at the size the map's own
#: lettering draws it, where the lettering has it (seven size classes, 1 the
#: smallest; a pixel per class on top of the smallest size the Norwegian
#: names are drawn at), and at the smallest size otherwise.
T50_LABEL_BASE_PX = 9.0

#: How far a register name may look for its lettering, by the same name. The
#: lettering sits where the word is drawn rather than where the place is.
LETTERING_M = 500.0

#: How the register's facility types read.
FACILITY_LABELS = {
    "Bro": "bridge",
    "Hängbro": "suspension bridge",
    "Dass": "privy",
    "Rastskydd": "rest shelter",
    "Vindskydd": "wind shelter",
    "Eldstad": "fireplace",
    "Ramp": "ramp",
    "Information": "information",
    "Karta": "map board",
}

#: Column identifying which chain a drawn line belongs to. A chain is linear by
#: construction, so a click can never select a branching network.
CHAIN_KEY = "chain_id"

#: What the profile panel reads off a chain, and the keys the figures travel
#: under. A Leaflet polyline has no ``feature.properties``, so these ride beside
#: the layer keyed by the class every path already carries — the same mechanism
#: the search box uses for its names.
#:
#: Not one of them is computed in the browser, and that includes the compass
#: point: it is a rounded label, which makes it a threshold. The four figures
#: come off the chain, where phase 2 put them; the bearing is measured once
#: here, in the metric CRS, and named once;
#: and the length is carried so the panel's distance axis ends where the popup
#: says the chain does rather than a few metres off it.
#: The three the browser needs in order to *write* a file rather than to draw
#: one, and none of them was in this table before phase 5: the name and the
#: source go into the track's ``<extensions>`` and decide which sources the file
#: names, and ``no_path_m`` is the one figure about a route that changes the
#: character of a day more than any other. All three are strings or metres the
#: chain already carries — nothing here is computed twice.
CHAIN_FIGURE_FIELDS = {
    "ascent": "ascent",
    "descent": "descent",
    "high_m": "high",
    "low_m": "low",
    # The steepest the chain gets over a 25 m window, absolute. Carried rather
    # than worked out in the page, so the panel's heading and the chain's own
    # popup cannot come to say two different numbers about one chain.
    "steepest_pct": "steepest",
    "compass": "point",
    # Only the arrow reads this, and it turns by it — a tenth of a degree is
    # less than the arrow's own stroke. The words come from "point" above.
    "bearing_deg": "bearing",
    "length_m": "length",
    "track_name": "name",
    "source": "source",
    "no_path_m": "noPath",
}

#: Trailing bracket of a layer label, which by convention holds its dataset.
SOURCE_IN_LABEL = re.compile(r"\[([^\]]+)\]\s*$")

#: Per dataset: its licence, the one word saying what it asks of a reader
#: passing the file on, and how to read the date recorded beside it — because
#: those dates are not the same kind of fact. Turrutebasen publishes a version
#: and takes no word; N50 arrives as an order and carries the day it was placed;
#: the rest answer a query, and what is recorded is when the answer was read.
#:
#: **The licences are out of the decisions document's own table, not off the
#: source modules' metadata**: those carry a class default, and
#: ``geonorge.Metadata.license`` says CC BY 4.0 for Turrutebasen where that
#: table and this script's own console line both say CC0. Two of the three
#: agree and the third is a default nobody set — but a licence is not a thing
#: to settle by majority in passing. It is written down here, where an export
#: reads it, and the disagreement is worth closing at the source.
NORWAY_SOURCE_TERMS = {
    UT: ("CC BY-NC 4.0", "non-commercial", "downloaded"),
    TURRUTEBASEN: ("CC0", "", ""),
    FKB: ("CC BY 4.0", "", "read"),
    N50_PATHS: ("CC BY 4.0", "", "ordered"),
    N50_ROADS: ("CC BY 4.0", "", "ordered"),
    OSM: ("ODbL 1.0", "share-alike", "read"),
    FERRIES: ("CC BY 4.0", "", "ordered"),
}

#: The Swedish set, out of the decisions document's table (§5): the register
#: and Topografi 50 are both CC0 and ask nothing; the register's date is the
#: night its file was written and Topografi 50's the day Lantmäteriet produced
#: the delivery.
SWEDEN_SOURCE_TERMS = {
    LEDER: ("CC0 1.0", "", "file of"),
    T50_TRAILS: ("CC0 1.0", "", "delivery of"),
    T50_PATHS: ("CC0 1.0", "", "delivery of"),
    T50_ROADS: ("CC0 1.0", "", "delivery of"),
    OSM: ("ODbL 1.0", "share-alike", "read"),
    sweden.FERRIES: ("CC0 1.0", "", "delivery of"),
}


class Described(Protocol):
    """What every source module says about the dataset it loads.

    Each of them declares its own frozen ``SourceMetadata`` rather than sharing
    one, so the four fields an exported file needs are a shape rather than a
    type. Naming that shape here is what lets one table hold all of them.
    """

    @property
    def name(self) -> str:
        """Human-readable name of the dataset."""

    @property
    def url(self) -> str:
        """Where it is described or served from."""

    @property
    def license(self) -> str:
        """Its terms, as the module states them."""

    @property
    def attribution(self) -> str:
        """Whom to credit."""


class Dataset(NamedTuple):
    """A dataset described here rather than by its module, in the same four words."""

    name: str
    url: str
    license: str
    attribution: str


#: Where each dataset says what it is. Turrutebasen is the odd one: it arrives
#: through the Geonorge order API, whose metadata object names a dataset rather
#: than a service, so it is spelled out here instead of reached for.
NORWAY_SOURCE_METADATA: dict[str, Described] = {
    UT: ut.METADATA,
    TURRUTEBASEN: Dataset(
        geonorge.TURRUTEBASEN_METADATA.dataset_name,
        geonorge.TURRUTEBASEN_METADATA.catalog_url,
        NORWAY_SOURCE_TERMS[TURRUTEBASEN][0],
        geonorge.TURRUTEBASEN_METADATA.attribution,
    ),
    FKB: traktorvegsti.METADATA,
    N50_PATHS: n50.METADATA,
    N50_ROADS: n50.METADATA,
    OSM: overpass.METADATA,
    FERRIES: n50.METADATA,
}

SWEDEN_SOURCE_METADATA: dict[str, Described] = {
    LEDER: naturvardsregistret.METADATA,
    T50_TRAILS: topografi50.METADATA,
    T50_PATHS: topografi50.METADATA,
    T50_ROADS: topografi50.METADATA,
    OSM: overpass.METADATA,
    sweden.FERRIES: topografi50.METADATA,
}

#: What a chain's own name was taken from, per source. Named here only to say
#: that **it costs the exported file nothing**: FKB's names come from
#: Turrutebasen, which is CC0 and asks for nothing, and a road's name comes from
#: SSR, which is Kartverket's own CC BY 4.0 under the same attribution N50
#: already carries. So a file naming its geometry's source and the height model
#: names every party with a claim on it, and naming a register a particular
#: track took no name from would be a statement nobody can check.
IDENTITY_REGISTERS = {FKB: "Turrutebasen", N50_ROADS: "Stedsnavn (SSR)"}

#: What every exported file says it was written by.
EXPORT_CREATOR = "trails-analysis"

#: The line an exported file opens its description with, before it lists what it
#: draws on. It says which map wrote the file, because that is what makes the
#: chain id in the track's extensions mean anything at all. ``{park}`` is the
#: park's name; these three are filled in by :func:`export_settings`.
EXPORT_DESCRIPTION = "One chain of the {park} routing network"

#: What a planned route's file calls itself, in ``<metadata>`` and on its track.
ROUTE_NAME = "Planned route in {park}"

#: The line a planned route's file opens its description with. It names the map
#: rather than the route, for the same reason a chain's does: what the legs and
#: the waypoints in its extensions mean is a property of the map that wrote them.
ROUTE_DESCRIPTION = "A route planned on the {park} map"

#: What a planned route's file is called, after the map's own prefix. Not a
#: chain id, because a plan has none — a plan is coordinates and nothing else,
#: which is what makes it survive the next rebuild of the graph.
ROUTE_FILE_STEM = "route"

#: What the points of a route are called in the file, before the number they are
#: in the order they were placed — where there is nothing named within reach to
#: call them after.
WAYPOINT_NAME = "Point"


class TrailLayer(NamedTuple):
    """One line layer of the map, in draw order.

    Attributes:
        gdf: Chains to draw
        label: Layer name in the control and legend, ending in its source
        color: Line colour
        weight: Line width in pixels
        popup_fields: Mapping of column name to popup label
        link_fields: Mapping of a column holding a URL to its link text
        link_heading: Line set above those links, saying whose pages they are
        published_fields: Mapping of column name to label for what somebody else
            states about the line, shown under that heading rather than among
            the figures this map worked out
        tooltip_field: Column shown on hover. Nothing sets it here any more:
            on a phone a hover label opens on a tap and stays there, and the row
            at the foot already names the line under the same name
        search_field: Column the search box matches against. Not the chain id:
            what a reader types is a name, and a road's identity is a register
            id because names repeat across the county.
        dash: SVG dash pattern, for connections that are not walked
        chains: Whether the lines are chains of the graph
        show: Whether the layer starts switched on
    """

    gdf: gpd.GeoDataFrame
    label: str
    color: str
    weight: float
    popup_fields: dict[str, str]
    link_fields: dict[str, str] | None = None
    tooltip_field: str | None = None
    search_field: str | None = None
    dash: str | None = None
    link_heading: str | None = None
    published_fields: dict[str, str] | None = None
    #: Whether the lines are chains of the graph, with figures to show and a
    #: chain to select. False for the winter lines, which are drawn and no more.
    chains: bool = True
    #: Whether the layer starts switched on.
    show: bool = True


def source_of(label: str) -> str | None:
    """Read the dataset out of a layer label.

    Every label here ends with its dataset in brackets, so the popups can name
    their source without a second list that could drift out of step with the
    legend and the layer control.

    Args:
        label: Layer label, e.g. ``"Paths in park [FKB]"``

    Returns:
        The dataset, or None if the label does not name one
    """
    match = SOURCE_IN_LABEL.search(label)
    return match.group(1) if match else None


def credit(name: str, licence: str, note: str, attribution: str, url: str, version: str | None) -> dict[str, str]:
    """Say what one dataset is, what it is licensed under and what was read.

    Args:
        name: What the map calls the dataset, so a file, a popup and a legend
            entry all name it the same way
        licence: Its terms
        note: The one word saying what those terms ask of a reader passing the
            file on, or empty where they ask nothing
        attribution: Whom to credit
        url: Where the dataset is described
        version: Its published version, or the date it was read at, or None
            where it can say neither

    Returns:
        One entry of an export's source list. A field with nothing in it is left
        empty rather than filled with a placeholder: both writers drop an empty
        field, and a version nobody published must not read as one that was.
    """
    return {"name": name, "licence": licence, "note": note, "attribution": attribution, "url": url, "version": version or ""}


def source_credits(
    versions: dict[str, str | None], terms: dict[str, tuple[str, str, str]], metadata: dict[str, Described]
) -> dict[str, list[dict[str, str]]]:
    """Say what a file drawn from each dataset has to name.

    Args:
        versions: The version or the date read, per source, from the country
            module's ``load_sources``
        terms: The licence, the word and how to read the date, per source:
            :data:`NORWAY_SOURCE_TERMS` or :data:`SWEDEN_SOURCE_TERMS`
        metadata: Where each dataset says what it is

    Returns:
        The sources a chain of each dataset draws on, keyed by the value the
        chain carries in its ``source`` column — which is what a click hands
        back and all the page has to go on
    """
    credits: dict[str, list[dict[str, str]]] = {}
    for name, (licence, note, word) in terms.items():
        described = metadata[name]
        version = versions.get(name)
        credits[name] = [
            credit(
                name if described.name == name else f"{name} ({described.name})",
                licence,
                note,
                described.attribution,
                described.url,
                f"{word} {version[:10]}".strip() if version and word else version,
            )
        ]
    return credits


def height_credit(model: Described) -> list[dict[str, str]]:
    """Say what the ``<ele>`` on every trackpoint came from.

    In every exported file that carries a height and in none that does not: a
    ferry crossing has no ground under it, and naming the height model in a file
    holding no height would be a claim about nothing.

    Args:
        model: The height model: Kartverket's point service, or Lantmäteriet's
            downloaded model

    Returns:
        A single entry for the height model, and **it carries no version**. The
        Norwegian endpoint publishes none and is not ordered — it answers point
        by point, and the answers reach a file through the graph rather than
        through a dated download; the Swedish model is read square by square
        off a STAC search that names each square's own date and no edition —
        so the field is left empty rather than filled with a date that would
        describe something else. What a reader needs in order to compare the
        ascent figure with another platform's is not a version but the rule it
        was read under, and every track carries that in its own ``ascentMethod``.
    """
    return [credit(model.name, model.license, "", model.attribution, model.url, None)]


def protected_credit(register: Described) -> list[dict[str, str]]:
    """Say where a route's protected-area figures came from.

    In every file that states one and in none that does not, exactly as the
    height model is named. Neither register publishes a version — one is
    queried over an extent, the other rewritten every night — and the answer
    reaches a file through the graph, so the field is left empty rather than
    filled with a date that would describe the download and not the data.

    Args:
        register: Naturbase, or Naturvårdsregistret

    Returns:
        A single entry for the register
    """
    return [credit(register.name, register.license, "", register.attribution, register.url, None)]


def ascent_method(params: graphs.Params, model: str) -> str:
    """Say how the heights and the ascent figure were reached.

    The figure without it asserts nothing: the same route here reads anywhere
    between 965 and 1,214 m depending on the rule, and it is also what explains
    why the number Komoot computes from its own model will not match.

    Args:
        params: What decided the build
        model: The model the ground was read off, in a word: ``DTM1`` for
            Kartverket's service, the mosaic's posts for Lantmäteriet's

    Returns:
        The rule, in the words the popup and the panel use for it
    """
    return f"{model}, sampled every {params.elevation_step_m:g} m, gains under {params.ascent_threshold_m:g} m ignored"


#: The word the Norwegian ascent rule opens with.
NORWAY_HEIGHT_MODEL = "DTM1"

#: And the Swedish: the 1 m model read at the mosaic's posts, which are the
#: posts the height tiles were cut from (:data:`sweden.HEIGHT_POSTS_M`).
SWEDEN_HEIGHT_MODEL = f"Markhöjdmodell 1 m at {sweden.HEIGHT_POSTS_M:g} m posts"


#: How near a click has to land to be taken as a point on the network. The
#: phase's figure, and it is a judgement rather than a measurement: near enough
#: that a reader aiming at a path gets the path, far enough that a click on open
#: ground stays on open ground. Beyond it the raw point stands and the leg is
#: drawn straight.
#: How long the page waits for one height request before giving up on it. See
#: ``heightsTimeoutMs`` in :func:`plan_settings` for why it is not the build's
#: own minute.
PLAN_HEIGHTS_TIMEOUT_MS = 5_000

SNAP_M = 150.0

#: The same question asked of the screen: how near a gesture has to land, in
#: pixels, to be taken as the line under it. A gesture snaps within whichever of
#: the two is smaller, so pinching in makes a tap mean the path it is touching
#: and not one a finger away; at 150 m alone the same tap meant the same thing
#: at every zoom, which is right only at about z12 and progressively wrong
#: below it. Taken from the halo every other line on this page is hit by, so
#: that *near enough to tap* means one thing on this map and not two.
SNAP_PX = maps.FINGER_PX

#: How far a single leg may be drawn straight before the page refuses to sample
#: it. A leg drawn straight is sampled at the build's own 5 m and fifty points
#: to a request, so its cost to Kartverket's height service is its length: a
#: 1 km leg is four requests, a 10 km one forty. This map is 45 km across, so
#: two clicks in opposite corners would be some 180 — from one misclick, at a
#: click's notice, against a public service the build is careful with.
#:
#: **Twenty kilometres, and the leg says so rather than being coarsened.**
#: Sampling further apart would make the two halves of one profile answer
#: differently and nothing would look wrong; refusing is visible. It is well
#: clear of anything real here: the longest stretch of UT.no's own routes that
#: no source records a path along is 10.3 km, and that is spread over a 42 km
#: trip rather than being one leg.
MAX_STRAIGHT_M = 20_000.0

#: What a metre of open ground costs against a metre of path, in the currency
#: the edge costs are already in -- an edge costs its length times its source's
#: factor, 1.00 for a marked route up to 1.30 for a connector nobody drew. It is
#: the whole of the rule that decides where a way to somewhere off the network
#: joins the paths and whether it bothers: a path is taken exactly while it is
#: cheaper in these metres than walking straight, so a route is never more than
#: this many times the line it could have flown.
#:
#: **Three, and the figure was driven rather than reasoned.** Four goals were
#: set in a browser at 2, 3, 4 and 6, and the answers part company in one place
#: only. At two, a goal 7.2 km away with 15.9 km of marked path leading to it
#: was answered with a straight line across the mountain, and so was a goal 2 km
#: past the end of the network -- both of which throw the reader's own question
#: away, because *routed* is a request for the paths. At three the first becomes
#: the path and the second becomes 18.4 km of path with 1.3 km of open ground at
#: the end, which is the answer that was asked for. Four gives the same five
#: answers as three. Six buys 0.6 km less open ground for 4 km more walking,
#: which is nobody's preference.
#:
#: It has to be above 1.30 whatever else it is, or a route would rather cross
#: open ground than take a line somebody surveyed.
OFF_PATH_FACTOR = 3.0

#: What a metre of a straight walk that lies over water costs, in the same
#: currency. Reported from the phone with a screenshot: a goal on the headland
#: across a 1.2 km sound from the end of the path was reached by a dotted line
#: over the water, because a connector was priced by its length alone and the
#: road round the head of the sound is longer. A walker cannot take the line;
#: the price has to say so.
#:
#: **A price and not a rule**, so that a goal on an island with no path to it
#: still gets an answer: every connector there crosses water, and the one that
#: crosses least wins. The headland in the screenshot turned out to be exactly
#: that -- 0.86 km2 of land in N50 with no path on it -- so what the price
#: buys there is the next best thing: the road round the head of the sound as
#: far as it goes, then the narrowest crossing.
#:
#: What the figure decides is how far round a route will go by land to avoid
#: a crossing. Swept at 10, 30, 100 and 300 against that leg, in a browser:
#: at 10 the way went west instead and crossed 566 m of water for 327 m of
#: path, which is a worse crossing bought cheaply; 30, 100 and 300 gave one
#: answer, 2.0 km of road and 390 m of water where the line across would have
#: been 960 m. The figure also bounds the search -- everything cheaper than
#: the priced line is explored -- and the search took 65 ms at 30, 1.0 s at
#: 100 and 4.3 s at 300 on the same leg. So thirty: the first figure that
#: gives the road-and-narrowest answer, at a cost a drag can carry.
#:
#: Above ``OFF_PATH_FACTOR``, or water would be no dearer than ground and the
#: page would be carrying the grid for nothing.
WATER_FACTOR = 30.0

#: How finely the page is told where the water is. A cell is priced as a whole,
#: so this is how far off a shoreline a connector's price can be: a connector
#: that touches one cell of sea because the reader tapped 25 m from the water
#: costs one cell more than it should, and every connector from that point
#: pays the same, so nothing between them is decided by it. Measured for this
#: build: 3,230 by 3,589 cells, 146 kB gzipped into the page. At 15 m it would
#: be 274 kB, at 50 m the sound in the screenshot would be a cell wide.
WATER_CELL_M = 25.0

#: How far a river's outline may stray from N50's when it is simplified for the
#: page, in metres. It decides one figure: how wide the water is where a straight
#: line meets it. Measured over the box: at 3 m the outlines are 39,700 vertices
#: and a third of a megabyte before gzip; at 0 m they are 133,000 and 2.5 MB;
#: at 10 m a 19 m river can be said to be 9 or 29.
RIVER_TOLERANCE_M = 3.0

#: ``navneobjekttype`` of a river's name in the register, and how far from the
#: outline the point carrying it may stand. The register puts a river's name on
#: the water, so 60 m is generous; measured over this build's 589 outlines,
#: 189 are named at 60 m and 198 at 100 m -- the rest have no point at all.
RIVER_NAME_TYPE = "elv"
RIVER_NAME_M = 60.0

#: How near a waypoint has to land to something the map draws by name before it
#: is called after it. The same fifty metres ``--hut-name-m`` already joins N50's
#: cabins to the place-name register by, and for the same reason: two registers
#: recording one hut put it within that of each other, and a reader clicking a
#: hut aims at the symbol rather than at the building.
#:
#: It is a judgement and not a measurement, and it is one that shows: a waypoint
#: named after the wrong hut is worse than one called *Point 3*, so the nearest
#: named thing wins and only that one, rather than everything within reach.
NAMED_POINT_M = 50.0

#: How wide one cell of the page's index over the edge geometry is.
#:
#: **The first work of phase 8 is this index and not the matcher**, and the
#: measurement is why. ``nearestNode`` is a linear scan over 116,967 nodes at
#: 0.135 ms and over the *edge* geometry the page had nothing at all: one pass
#: over its 948,465 vertices costs 2 ms, so a foreign track matched a point at a
#: time is 2.9 s of frozen main thread at the corpus median and 10 s at its
#: largest, before a single overlap test. Measured in the built page at three
#: sizes, over the 714,107 segments of the network:
#:
#: ======= ========= ========= ============== =================
#: cell    build     entries   per lookup     segments looked at
#: ======= ========= ========= ============== =================
#: 50 m    49 ms     902,548   1.4 µs         119
#: 100 m   29 ms     799,863   0.7 µs         159
#: 200 m   31 ms     754,842   0.7 µs         242
#: ======= ========= ========= ============== =================
#:
#: A hundred metres is the cheapest to build and ties the fastest to ask, and
#: the middle column is why the smaller cell does not win: halving the cell
#: quadruples the cell count and the extra entries cost more to lay down than
#: the shorter scan saves. Against the 2 ms linear pass a lookup is some 2,800
#: times cheaper, which is the whole of what makes matching a 5,147-point track
#: something that happens between two frames.
INDEX_CELL_M = 100.0

#: How far from an edge a recorded point may lie and still be taken as running
#: along it.
#:
#: Consumer GPS under tree cover and against a mountainside is the error this
#: has to absorb, and the sources' own disagreement is the other half: the same
#: path drawn by FKB and by Turrutebasen sits metres apart, and a recording of
#: it can be nearer either. Twenty-five metres takes both without reaching the
#: next path over. It is a judgement; the two below are what keep it from being
#: the *only* test.
MATCH_TOLERANCE_M = 25.0

#: The least share of a matched stretch that must actually lie along the edges
#: matched to it, between 0 and 1.
#:
#: **This is the rule ``trails.utils.geo.attach_nearest`` learned and it is the
#: most important one in this phase.** Proximity alone is a weak test for lines:
#: at a junction the first metres of a side road lie well within tolerance of
#: the main road, and 23 % of that function's matches followed their road for
#: under half its length until ``min_overlap`` was added. A recording beside a
#: parallel path snaps to the wrong one on distance alone, and this map is full
#: of parallel paths — UT.no, Turrutebasen and FKB all draw Sjøbergmarsjruta,
#: all 20.48 km of it, over the same ground.
MATCH_MIN_OVERLAP = 0.6

#: The least a matched stretch may be, in metres. Below it the match is dropped
#: and the recording is kept as it was recorded.
#:
#: A stretch shorter than this is the junction case: a recording crossing a path
#: touches a few of its metres and would take them. Edges here average 25 m, so
#: this is some four of them, and it is the length below which *running along*
#: something and *touching* it cannot be told apart.
MATCH_MIN_RUN_M = 100.0

#: How far a recording's heading may differ from an edge's before the edge is
#: not a candidate at all, in degrees.
#:
#: The cheap half of the overlap rule and the one that runs per point: a side
#: road leaving a junction points somewhere else, and a parallel path walked the
#: other way is not the path being walked. Sixty degrees is loose enough for a
#: recording that wanders and tight enough that a crossing path is never a
#: candidate. Undirected — a recording may walk an edge either way round.
MATCH_MAX_TURN_DEG = 60.0

#: How far apart the points a recording is anchored to the network by are, along
#: the recording, in metres.
#:
#: The matcher anchors and then routes between the anchors, so this is the unit
#: it decides in: a stretch this long is taken onto the network or kept as it was
#: recorded, whole. It is also what the matching costs — one Dijkstra per anchor,
#: and a search between two nodes this far apart settles a handful of nodes
#: against the three 116,967-long arrays it has to clear first, which is the
#: floor and the reason the anchors are spaced rather than taken at every
#: recorded point.
#:
#: Two hundred and fifty metres is ten of this network's edges and, at the
#: corpus's 5 m point spacing, some fifty recorded points to test each stretch
#: against — enough for the overlap test to mean something, and fine enough that
#: a recording leaving the path is followed off it within a quarter of a
#: kilometre.
MATCH_ANCHOR_M = 250.0


#: Where a straight leg's heights come from, per country. Norway asks
#: Kartverket's point service, in degrees, at the service's own cap on points
#: per request and the build's own concurrency -- somebody else's endpoint,
#: and one number rather than two -- and reads each answer by the two rules
#: the build reads it by. Sweden reads the height tiles the build cut
#: (decisions §6.3) and asks no service at all; the service's settings are
#: then handed over empty, because the page insists on the keys and reads
#: none of them once it has tiles.
NORWAY_PLAN_HEIGHTS: dict[str, object] = {
    "heightsUrl": hoydedata.SERVICE_URL,
    "heightsCrs": hoydedata.WGS84_COORDINATE_SYSTEM,
    "heightsBatch": hoydedata.MAX_POINTS,
    "heightsWorkers": hoydedata.DEFAULT_WORKERS,
    "heightsTiles": None,
    "terrainModel": hoydedata.TERRAIN_MODEL,
    "seaTerrain": hoydedata.SEA_TERRAIN,
}


def sweden_plan_heights(base: maps.BaseMap) -> dict[str, object]:
    """The Swedish page's height source: the tiles beside the sheet it draws.

    Args:
        base: The sheet, whose provider carries the height tiles

    Returns:
        The height entries of the ``plan`` argument

    Raises:
        ValueError: If the sheet's provider carries no height tiles, since the
            page would then have nothing to read a straight leg's profile off
    """
    provider = maps.provider_of(base)
    if provider is None or provider.heights is None:
        raise ValueError(f"{base.value} carries no height tiles, and the page has no service to ask instead")
    return {
        "heightsUrl": None,
        "heightsCrs": None,
        "heightsBatch": None,
        "heightsWorkers": None,
        "heightsTiles": provider.heights.as_settings(),
        "terrainModel": None,
        "seaTerrain": None,
    }


def plan_settings(params: graphs.Params, layers: list[TrailLayer], heights: dict[str, object]) -> dict[str, object]:
    """Hand the page what it needs to plan a route over the graph it carries.

    Everything here is a fact the build already settled, and the page must not
    settle any of it again: the two rules an answer from the height service is
    read by, the step the whole network was sampled at, and the threshold every
    ascent on this map was read under. A page sampling every 50 m, or counting a
    climb at no threshold at all, would draw a profile that disagrees with every
    other figure on the map without anything looking wrong.

    Args:
        params: What decided the build
        layers: The line layers this map draws, which is what the route's own
            width is measured against
        heights: Where a straight leg's heights come from:
            :data:`NORWAY_PLAN_HEIGHTS` or :func:`sweden_plan_heights`

    Returns:
        The ``plan`` argument of :func:`~trails.visualization.maps.add_plan_mode`
    """
    return {
        **heights,
        # **And a deadline, which the build does not need and a reader does.**
        # `fetch` has none of its own: a server that accepts a connection and
        # then says nothing leaves a leg outstanding for ever, and plan mode
        # says *working…* with nothing left that will ever finish it. The build
        # waits a minute per request because nothing is waiting on the build; a
        # finger on a map is. Five seconds, three attempts and the backoff
        # between them is about eighteen before the leg says it has no heights
        # and draws itself straight — which is a thing a reader can act on.
        # Measured with the endpoint taken away: 27 s at eight seconds an
        # attempt, and half a minute of *working…* is most of the way back to
        # the fault this cures.
        "heightsTimeoutMs": PLAN_HEIGHTS_TIMEOUT_MS,
        # **As wide as the widest line it can be planned along.** Reported from
        # the device: the route reads thinner than a UT.no route under it, and
        # it does — 2.6 px of colour against 4.0, however wide the white casing
        # around it makes the whole mark. Taken from the layer weights rather
        # than written down again, so a layer drawn wider tomorrow takes the
        # route with it instead of quietly overtaking it.
        "routeWidth": max(layer.weight for layer in layers),
        "sampleStepM": params.elevation_step_m,
        "ascentThresholdM": params.ascent_threshold_m,
        "snapM": SNAP_M,
        "snapPx": SNAP_PX,
        "maxStraightM": MAX_STRAIGHT_M,
        "offPathFactor": OFF_PATH_FACTOR,
        "waterFactor": WATER_FACTOR,
        # What the payload's header calls a crossing and an inferred connector.
        # The page reads both off the header for every edge it routes over, and
        # renaming either here without telling it would leave it counting every
        # ferry as walked ground with nothing looking wrong.
        "crossingKind": FERRY,
        "connectorKind": BRIDGE,
        # How much of a route has to lie inside a protected area before it says
        # so. Handed over rather than spelled in the page, so that the figure
        # this build prints and the sentence the page writes cannot come to
        # disagree about what counts as passing through somewhere.
        "touchedM": DEFAULT_TOUCHED_M,
        "namedM": NAMED_POINT_M,
        # What it takes to index the edge geometry and to match a recording
        # against it. Every one is a judgement this build made and printed, and
        # a page that picked its own would match differently from run to run
        # with nothing in the file saying which rule it was matched under.
        "indexCellM": INDEX_CELL_M,
        "matchToleranceM": MATCH_TOLERANCE_M,
        "matchMinOverlap": MATCH_MIN_OVERLAP,
        "matchMinRunM": MATCH_MIN_RUN_M,
        "matchAnchorM": MATCH_ANCHOR_M,
        "matchMaxTurnDeg": MATCH_MAX_TURN_DEG,
        # And the vocabulary of the file the page both writes and reads. Every
        # name here is one of the constants export_settings hands the writer,
        # out of trails.io.export.gpx — handed over twice rather than agreed on
        # by convention, because a reader and a writer of one file are in one
        # phase here for the only time in this project, and a page that read
        # `origin` while writing `Origin` would load its own routes as foreign
        # tracks and say nothing.
        "gpx": {
            "namespace": TRAILS_NAMESPACE,
            "kindField": ROUTE_KIND_FIELD,
            "kind": ROUTE_KIND,
            "chainField": DEFAULT_EXTENSION_FIELDS[CHAIN_KEY],
            "legs": LEGS_ELEMENT,
            "leg": LEG_ELEMENT,
            "part": PART_ELEMENT,
            "partKind": PART_KIND_ATTR,
            "partLength": PART_LENGTH_ATTR,
            "origin": WAYPOINT_ORIGIN_FIELD,
            "set": WAYPOINT_SET,
            "generated": WAYPOINT_GENERATED,
            "trackKind": PART_KIND_TRACK,
            "stage": WAYPOINT_STAGE_FIELD,
        },
    }


def export_settings(credits: Credits, park: Park) -> dict[str, object]:
    """Hand the page everything it needs to write a GPX file.

    The browser writes that file, so every last thing in it has to be in the
    page — the licences, the versions, the field names and the rule the heights
    were read under. Measured before this phase: ``CC BY 4.0``, ``ODbL`` and
    ``CC BY-NC`` appeared **zero times** in the built page, and so did any
    source version. They existed only in what this script prints to its console,
    and a browser cannot invent them.

    Args:
        credits: What every file names: the sources, the height model, the
            protected-area register and the rule the ascent was read under
        park: Whose map wrote the file, for its name, its description and its prefix

    Returns:
        The ``export`` argument of :func:`~trails.visualization.maps.add_profile_panel`

    Raises:
        KeyError: If a chain figure the file is written from is not in
            :data:`CHAIN_FIGURE_FIELDS`, which would leave the browser writing a
            field it was never given
    """
    keys = {CHAIN_KEY: maps.FIGURE_ID_KEY, **CHAIN_FIGURE_FIELDS}
    return {
        "credits": credits.sources,
        "heights": credits.heights,
        # The one list, in the one order, that both writers work from: the
        # column the Python writer reads, the key the page carries it under, and
        # the name it is written down as.
        "fields": [[keys[column], written] for column, written in DEFAULT_EXTENSION_FIELDS.items()],
        "creditFields": list(SOURCE_CREDIT_FIELDS),
        "gapM": DEFAULT_GAP_M,
        "decimals": EXTENSION_DECIMALS,
        "elevationDecimals": ELEVATION_DECIMALS,
        # A millionth of a degree is what the payload is quantised at and 11 cm
        # of latitude; a seventh place says the page is not rounding further.
        "coordinateDecimals": 7,
        "namespace": TRAILS_NAMESPACE,
        "prefix": TRAILS_PREFIX,
        "creator": EXPORT_CREATOR,
        "description": EXPORT_DESCRIPTION.format(park=park.name),
        "ascentMethod": credits.ascent,
        "identitySeparator": IDENTITY_SEPARATOR,
        "filePrefix": park.stem,
        "sourceLength": SOURCE_LENGTH_FIELD,
        # What a planned route's file is made of, and every name in it comes
        # from the writer's own module rather than being spelled in the page:
        # nothing here can import that module across the browser boundary, so
        # the constants travelling through this dict are the whole of what keeps
        # the two files' vocabularies from drifting apart.
        "route": {
            "name": ROUTE_NAME.format(park=park.name),
            "description": ROUTE_DESCRIPTION.format(park=park.name),
            "fileStem": ROUTE_FILE_STEM,
            "kindField": ROUTE_KIND_FIELD,
            "kind": ROUTE_KIND,
            "fields": [[key, written] for key, written in ROUTE_EXTENSION_FIELDS.items()],
            "legs": LEGS_ELEMENT,
            "leg": LEG_ELEMENT,
            "part": PART_ELEMENT,
            "partKind": PART_KIND_ATTR,
            "partLength": PART_LENGTH_ATTR,
            "areas": AREAS_ELEMENT,
            "area": AREA_ELEMENT,
            "areaId": AREA_ID_ATTR,
            "areaName": AREA_NAME_ATTR,
            "areaForm": AREA_FORM_ATTR,
            "areaLength": AREA_LENGTH_ATTR,
        },
        "waypoint": {
            "name": WAYPOINT_NAME,
            "origin": WAYPOINT_ORIGIN_FIELD,
            "set": WAYPOINT_SET,
            "generated": WAYPOINT_GENERATED,
            "enters": WAYPOINT_ENTERS,
            "leaves": WAYPOINT_LEAVES,
            "area": WAYPOINT_AREA_FIELD,
            "stage": WAYPOINT_STAGE_FIELD,
        },
        # Named wherever a file states how far the route runs inside a protected
        # area, and in no file that does not — the same rule the height model is
        # credited by. That figure came from the register, and a file that
        # reports it without saying so names every party with a claim on it but one.
        "protected": credits.protected,
    }


class Credits(NamedTuple):
    """What every exported file names, worked out once per build.

    Attributes:
        sources: The sources a chain of each dataset draws on, by source name
        heights: The height model, named in every file carrying a height
        protected: The protected-area register, named in a route's file
        ascent: The rule the ascent was read under, in the file's words
    """

    sources: dict[str, list[dict[str, str]]]
    heights: list[dict[str, str]]
    protected: list[dict[str, str]]
    ascent: str


def load_park_boundary(park: Park, cache_dir: str) -> gpd.GeoDataFrame:
    """Load a national park's boundary from Naturbase, by name.

    Args:
        park: Which park
        cache_dir: Root cache directory

    Returns:
        Single-row GeoDataFrame in EPSG:4326
    """
    source = naturbase.Source(cache_dir=cache_dir)
    found = source.find_one(park.name, layer=naturbase.Layer.NATIONAL_PARK)

    area_km2 = found.to_crs(norway.METRIC_CRS).area.iloc[0] / 1e6
    print(f"Park: {found['offisieltNavn'].iloc[0]}")
    print(f"  Area: {area_km2:,.0f} km2")
    print(f"  Municipalities: {found['kommune'].iloc[0]}")
    return found


def load_swedish_boundary(park: Park, register: naturvardsregistret.Source) -> gpd.GeoDataFrame:
    """Load a national park's boundary from Naturvårdsregistret, by name.

    Args:
        park: Which park
        register: The register, open

    Returns:
        Single-row GeoDataFrame in EPSG:4326
    """
    found = register.find_one(park.name)
    area_km2 = found.to_crs(sweden.METRIC_CRS).area.iloc[0] / 1e6
    print(f"Park: {found[naturvardsregistret.AREA_NAME].iloc[0]} ({naturvardsregistret.form_label(found[naturvardsregistret.AREA_FORM].iloc[0])})")
    print(f"  Area: {area_km2:,.0f} km2 (the register says {float(found['AREA_HA'].iloc[0]) / 100:,.0f})")
    print(f"  County and municipality: {found['LAN'].iloc[0]}, {found['KOMMUN'].iloc[0]}")
    # The three columns the page and the report read, and not the decision
    # date beside them: a timestamp does not serialise into the boundary's
    # GeoJSON, and nothing downstream asks for it.
    kept: gpd.GeoDataFrame = found[[naturvardsregistret.AREA_ID, naturvardsregistret.AREA_NAME, naturvardsregistret.AREA_FORM, "geometry"]]
    return kept


def only_the_wider_way(chains: gpd.GeoDataFrame, placeholders: frozenset[str]) -> pd.Series:
    """Say how long the whole named way is, where that is more than the chain.

    :func:`whole_way_length` answers for every chain that has an identity, and
    for most of them the answer is the chain's own length — a way that does not
    divide is one chain. Showing the same number twice under two labels is
    noise, so those are left empty and the popup drops the row.

    Args:
        chains: Chains carrying ``source``, ``identity`` and ``length_m``
        placeholders: Identities that are a register's word for *no name*,
            which must not be summed as though they named one way

    Returns:
        Kilometres, empty where the chain is the whole way, has no identity, or
        is identified only by a placeholder — a 16 m stub named *Ukjent* would
        otherwise report the total of every other stretch the register also had
        no name for
    """
    whole = whole_way_length(chains, ignore=placeholders)
    # A metre of slack: the same lengths summed in a different order need not
    # come out bit for bit equal.
    return (whole / 1000).round(2).where(whole > chains["length_m"] + 1.0)


def share_inside(chains: gpd.GeoDataFrame, area: gpd.GeoDataFrame) -> pd.Series:
    """Measure how much of each chain lies inside an area.

    Args:
        chains: Chains carrying ``length_m``, in :data:`METRIC_CRS`
        area: Boundary to measure against

    Returns:
        Share of each chain's length inside it, between 0 and 1
    """
    inside = chains.geometry.intersection(area.to_crs(str(chains.crs)).union_all()).length
    return inside / chains["length_m"]


def describe_marking(chains: gpd.GeoDataFrame) -> pd.Series:
    """Say how much of each chain the sources between them call waymarked.

    Kilometres per class rather than one verdict, because 467 chains here are
    marked along part of their run and not along the rest, and a line labelled
    "marked" that is marked for a third of its length is worse than no answer
    at all.

    ``not stated`` is a class of its own and is never folded into unmarked. FKB
    carries no marking information whatever and is 90 % of this network's path
    evidence, so most of what a reader sees is honestly unknown — 3,711 km of
    5,853. A summary that hid that would read as a survey and is not one.

    Args:
        chains: Chains carrying :data:`CHAIN_COVERAGE_COLUMNS`

    Returns:
        One line per chain, empty where neither question was asked — a crossing
        has no ground to be marked, and an empty popup row is dropped
    """
    lines = []
    for row in chains[list(MARKING_LABELS)].itertuples(index=False):
        pieces = [f"{metres / 1000:.2f} km {label}" for metres, label in zip(row, MARKING_LABELS.values(), strict=True) if metres > 0]
        lines.append(" \u00b7 ".join(pieces))
    return pd.Series(lines, index=chains.index, dtype="string")


def describe_climb(chains: gpd.GeoDataFrame, points: pd.Series) -> pd.Series:
    """Say what a chain climbs and falls, and which way round it was read.

    A chain is oriented so that its id stays stable across builds, not because a
    walker is obliged to take it that way, so its ascent and descent are true in
    a direction the reader cannot see. This is one of the three places that make
    it visible — the arrow on the selected chain and the profile's own left-to-
    right sense are the other two — and all three read the same carried bearing,
    so none of them can say something different from the others.

    Args:
        chains: Chains carrying ``ascent`` and ``descent``
        points: Compass point each of them runs towards, None for a ring, which
            has no direction and needs none: it climbs the same either way round

    Returns:
        One line per chain, empty where nothing was read along it — every ferry
        crossing, and the two stubs outside the height model. An empty popup row
        is dropped rather than shown as a claim about ground nobody measured.
    """
    lines = []
    for ascent, descent, point in zip(chains["ascent"], chains["descent"], points, strict=True):
        if pd.isna(ascent) or pd.isna(descent):
            lines.append("")
            continue
        climbed = f"+{_metres(ascent)} / −{_metres(descent)} m"
        lines.append(climbed if point is None else f"{climbed} towards {point}")
    return pd.Series(lines, index=chains.index, dtype="string")


def describe_steepness(chains: gpd.GeoDataFrame) -> pd.Series:
    """Say the steepest ground a chain covers, over two lengths of it.

    **Absolute, and two figures rather than one.** Absolute because the hard
    part of a mountain path is as often the way down — the steepest chain in
    this park climbs 9 m and drops 816, so a signed maximum would report it as
    flat. Two figures because one invites the confusion this row exists to end:
    on that same chain the steepest 25 m is 74 % and it is *ten metres long*,
    while the steepest 100 m is 62 % and the whole descent averages 27 %. The
    first is what surprises a walker once; the second is what their legs are in
    for.

    Args:
        chains: Chains carrying ``steepest_pct`` and ``sustained_pct``

    Returns:
        One line per chain, empty where no slope could be read along it — a
        ferry crossing, or a stretch too short for the window to open in
    """
    lines = []
    for steepest, sustained in zip(chains["steepest_pct"], chains["sustained_pct"], strict=True):
        if pd.isna(steepest):
            lines.append("")
            continue
        # ``floor(x + 0.5)`` for the same reason :func:`_metres` uses it, and
        # caught the same way: the crosshair on the panel reads this chain at
        # 73 % where a plain format wrote 72, because the figure is 72.5 and
        # Python rounds a half to even while JavaScript's ``Math.round`` takes
        # it up. Two places asking one question, two answers.
        said = f"{_percent(steepest)} % over {int(elevation.GRADIENT_WINDOW_M)} m"
        if not pd.isna(sustained):
            said += f" · {_percent(sustained)} % over {int(elevation.SUSTAINED_WINDOW_M)} m"
        lines.append(said)
    return pd.Series(lines, index=chains.index, dtype="string")


def _percent(value: float) -> str:
    """Round a gradient the way the profile panel rounds it.

    The same ``floor(x + 0.5)`` as :func:`_metres` and for the same reason: the
    panel's crosshair reads a slope with ``Math.round``, and the steepest a
    chain reaches is stated in two places that must not disagree.

    Args:
        value: Per cent

    Returns:
        The rounded figure
    """
    return f"{math.floor(value + 0.5):,}"


def _metres(value: float) -> str:
    """Round a height to whole metres, the way the panel in the page rounds it.

    ``floor(x + 0.5)`` and not a plain format, because that is how JavaScript's
    ``Math.round`` is defined and the panel renders the same figures from the
    same numbers. Python rounds a half to even; disagreeing about that is how a
    popup and a panel come to differ by a metre on one chain, which is exactly
    the kind of doubt this phase exists to remove.

    Args:
        value: Metres

    Returns:
        The rounded figure, grouped in thousands
    """
    return f"{math.floor(value + 0.5):,}"


def describe_unrecorded(chains: gpd.GeoDataFrame) -> pd.Series:
    """Say how much of each chain no source records a path along.

    **The silence is the whole of the statement**, and the wording has to keep
    saying so. This is ground that no register draws anything on — not ground
    with no path. All four recording sources draw liberally and three of them
    are Kartverket, so a line beside something is evidence of nothing; only
    their saying nothing at all carries information.

    Args:
        chains: Chains carrying ``no_path_m``

    Returns:
        One line per chain, empty wherever every metre of it is recorded, which
        is all but 20.3 km of the network
    """
    return pd.Series(
        [f"{metres / 1000:.2f} km where no source records a path" if metres > 0 else "" for metres in chains["no_path_m"]],
        index=chains.index,
        dtype="string",
    )


def describe(
    chains: gpd.GeoDataFrame,
    park: gpd.GeoDataFrame,
    sources: tuple[str, ...],
    placeholders: frozenset[str] = frozenset(),
) -> dict[str, gpd.GeoDataFrame]:
    """Give every chain the columns a popup, a search box and a layer need.

    Everything here is read off what the chain already carries. Nothing is
    joined, looked up or clipped: the graph is the only place the geometry and
    the attributes come from, so the map cannot disagree with the router about
    what a line is. What one country's registers say beyond this is added by
    :func:`describe_norway` and :func:`describe_sweden`.

    Args:
        chains: Every chain of the network, in the country's metric CRS
        park: Park boundary
        sources: Every source of the network, in draw order
        placeholders: Identities that are a register's word for no name

    Returns:
        One frame per source, keyed by source name. Every source has an entry,
        empty where a small extent left it with no chains at all: a layer with
        nothing in it is drawn as nothing, and a missing key is a crash.
    """
    metric_crs = str(chains.crs)
    described = chains.copy()
    described["length_km"] = (described["length_m"] / 1000).round(2)
    described["whole_km"] = only_the_wider_way(described, placeholders)
    described["in_park"] = share_inside(described, park) >= IN_PARK_SHARE
    described["marking_all"] = describe_marking(described)
    described["unrecorded"] = describe_unrecorded(described)
    # In the metric CRS the graph is built in, and once: taken flat from
    # longitude and latitude the same endpoints give a different bearing, and at
    # this latitude two chains in five would be labelled with a different one of
    # the eight points. Every chain here comes out running eastward — never W,
    # SW or NW — because a chain is canonicalised by coordinate order. That looks
    # like a bug and is not.
    described["bearing_deg"] = endpoint_bearings(described, metric_crs=metric_crs)
    # Named once, here, and carried. The panel must not name it a second time
    # from the degrees: 241 chains lie within half a degree of a boundary
    # between two points, and two roundings that disagree by a hair would put
    # the panel and the popup on different sides of one.
    described["compass"] = compass_points(described["bearing_deg"])
    described["climb"] = describe_climb(described, described["compass"])
    described["steepness"] = describe_steepness(described)
    # The name a track is written under, in one column for every source, because
    # an exported file asks the same question of all of them. It is the chain's
    # identity everywhere but the roads, where the identity is the register id
    # that reunites two fragments of one road and the *name* is a separate
    # column — a road id is not a thing to write into a <trk><name> — and each
    # country's own description says which column that is.
    described["track_name"] = described["identity"]
    # **The two ends of the climb on one line, under it.** They are one fact
    # about a walk -- how high it gets and how low -- and read as two rows two
    # rows apart, with the low one arriving from a different place entirely. The
    # metre is `_metres` for the same reason it always was: the panel and the
    # popup must round one number the same way.
    described["high_low"] = pd.Series(
        [
            "" if pd.isna(high) else (f"{_metres(high)} m" if pd.isna(low) else f"{_metres(high)} / {_metres(low)} m")
            for high, low in zip(described["high_m"], described["low_m"], strict=True)
        ],
        index=described.index,
        dtype="string",
    )

    return {name: gpd.GeoDataFrame(described[described["source"] == name].copy(), geometry="geometry", crs=described.crs) for name in sources}


def describe_norway(frames: dict[str, gpd.GeoDataFrame]) -> dict[str, gpd.GeoDataFrame]:
    """Add what the Norwegian registers say about their own chains.

    Args:
        frames: One frame per source, from :func:`describe`

    Returns:
        The same frames, with the per-source columns the popups read
    """
    routes = frames[UT]
    routes["name"] = routes["identity"]
    routes["category_label"] = translate_joined(routes["category"], UT_CATEGORY_LABELS)

    trails = frames[TURRUTEBASEN]
    trails["trail_name"] = trails["identity"]
    # This register writes its capture method out in words already.
    trails["survey_method"] = trails["measurement_method"]
    # A chain runs across segments different clubs look after, and 113 of the
    # 245 carry more than one maintainer — three of them, 9.4 km, a DNT club
    # and a local one together. A chain has to go wholly into one layer, so
    # touching DNT anywhere counts: the layer is called "DNT routes", not
    # "maintained solely by DNT". `_combine` has already merged away which club
    # held which stretch, so weighting by length is not available to ask.
    trails["is_dnt"] = trails["maintenance_responsible"].str.contains(DNT_PATTERN, case=False, na=False)

    paths = frames[N50_PATHS]
    paths["survey_method"] = translate_joined(paths["malemetode"], SURVEY_METHOD_LABELS)

    roads = frames[N50_ROADS]
    roads["road_category"] = translate_joined(roads["vegkategori"], n50.ROAD_CATEGORIES)
    roads["survey_method"] = translate_joined(roads["malemetode"], SURVEY_METHOD_LABELS)
    # Private only where the whole chain is: the colour encodes who may drive
    # it, and a road that is public for half its run is not a private road. The
    # popup's category line names both wherever a chain spans the two.
    roads["is_private"] = roads["vegkategori"] == n50.PRIVATE_ROAD_CATEGORY
    # The name SSR gave the road, not the register id the chain is built on.
    roads["track_name"] = roads["road_name"]

    frames[OSM]["name"] = frames[OSM]["identity"]

    ferries = frames[FERRIES]
    ferries["survey_method"] = translate_joined(ferries["malemetode"], SURVEY_METHOD_LABELS)

    return frames


def describe_sweden(frames: dict[str, gpd.GeoDataFrame]) -> dict[str, gpd.GeoDataFrame]:
    """Add what the Swedish registers say about their own chains.

    Args:
        frames: One frame per source, from :func:`describe`

    Returns:
        The same frames, with the per-source columns the popups read
    """
    leder = frames[LEDER]
    # The identity is the state trail; the name is the register's name for
    # the trail where it has one -- 37 of 47 segments over Abisko -- and the
    # state trail otherwise, so a track is never written nameless where the
    # register knows which trail it is.
    leder["route"] = leder["identity"]
    leder["route_id"] = leder[naturvardsregistret.TRAIL_ROUTE_ID]
    leder["trail_name"] = leder[naturvardsregistret.TRAIL_NAME].fillna(leder["identity"])
    leder["track_name"] = leder["trail_name"]
    leder["trail_type"] = leder[naturvardsregistret.TRAIL_TYPE]
    leder["marking"] = leder[naturvardsregistret.TRAIL_MARKING]
    leder["description"] = leder[naturvardsregistret.TRAIL_DESCRIPTION]
    leder["protected_area"] = leder[naturvardsregistret.TRAIL_PROTECTED]

    for name in (T50_TRAILS, T50_PATHS):
        frame = frames[name]
        frame["path_class"] = translate_joined(frame[topografi50.TYPE], PATH_CLASS_LABELS)
        frame["over"] = translate_joined(frame["vagutforande"], BRIDGE_LABELS)
        frame["snowmobiles"] = translate_joined(frame["skoterkorning_tillaten"], SNOWMOBILE_LABELS)
        frame["brush"] = translate_joined(frame["ruskmarkering"], BRUSH_LABELS)
    frames[T50_TRAILS]["route_name"] = frames[T50_TRAILS]["identity"]

    roads = frames[T50_ROADS]
    roads["road_class"] = translate_joined(roads[topografi50.TYPE], ROAD_CLASS_LABELS)
    roads["road_number"] = roads["identity"]
    # A street name where the product has one, the number otherwise: the
    # track is written under whichever the road is known by.
    roads["road_name"] = roads["gatunamn"].where(roads["gatunamn"].notna(), roads["identity"])
    roads["track_name"] = roads["road_name"]

    frames[OSM]["name"] = frames[OSM]["identity"]
    return frames


def simplify_for_display(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    """Thin out vertices for map rendering.

    The drawn copy is a separate thing from the geometry that is exported and
    routed, and always has been. Folium writes drawn geometry into the page as
    JSON coordinate arrays, and the network's half-million vertices cost 22 MB
    written that way; at these zoom levels a few metres of tolerance is
    invisible. The chain's own geometry, which the GPX and the router read, is
    untouched.

    Args:
        gdf: Features to simplify
        tolerance_m: Douglas-Peucker tolerance in metres

    Returns:
        Copy of the input with simplified geometries, in EPSG:4326 — or the
        input untouched, in whatever CRS it arrived in, where there is nothing
        to do. The map layer reprojects either way.
    """
    if not len(gdf) or tolerance_m <= 0:
        return gdf

    # In the metres the lines are already in -- a chain frame arrives in the
    # country's metric CRS -- and in the nearest UTM zone for a frame that
    # arrives in degrees, which the winter lines do.
    simplified = gdf.to_crs(gdf.estimate_utm_crs()) if gdf.crs is not None and gdf.crs.is_geographic else gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(tolerance_m, preserve_topology=True)
    return simplified.to_crs("EPSG:4326")


def bounds_of(gdf: gpd.GeoDataFrame) -> maps.Bounds:
    """Return a GeoDataFrame's extent as plain floats.

    ``total_bounds`` yields NumPy scalars, which the source and map APIs do not
    accept.

    Args:
        gdf: Features to measure

    Returns:
        (min_lon, min_lat, max_lon, max_lat)
    """
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in gdf.total_bounds)
    return min_lon, min_lat, max_lon, max_lat


def summarize(name: str, gdf: gpd.GeoDataFrame) -> None:
    """Print a one-line summary of a line layer.

    Args:
        name: Label for the layer
        gdf: Chains carrying a ``length_km`` column
    """
    total_km = gdf["length_km"].sum() if len(gdf) else 0.0
    print(f"  {name}: {len(gdf):,} chains, {total_km:,.1f} km")


def encode_for_the_page(
    network: Network,
    order: pd.DataFrame,
    costs: dict[str, dict[str, float]],
    areas: list[dict[str, object]],
    water: gpd.GeoDataFrame,
    rivers: gpd.GeoDataFrame,
    bounds: maps.Bounds,
) -> Payload:
    """Encode the routing graph and its heights into the page's second payload.

    Two representations of the same ground, and they must not be unified. What
    is *drawn* is chains, thinned by ``--simplify-m`` because folium writes
    geometry into the page as JSON coordinate arrays and the network's vertices
    cost 22 MB written that way. What will be *routed over* is the merged graph
    at the resolution its sources recorded it, encoded rather than serialised,
    and never drawn at all. Serving both from one copy loses either the accuracy
    or the render budget.

    Args:
        network: The finished graph, in the country's metric CRS
        order: Which of a chain's edges comes first and which way round each of
            them runs. Handed in rather than rebuilt here, because the exported
            tracks are laid out of the same walk and the two writers of a GPX
            file agree only for as long as they compose from one order.
        costs: What a metre on each dataset costs a route, from the country
            module's ``edge_costs``
        areas: The protected areas every edge was measured against, whose
            outlines go into the page as well as their names: a leg drawn
            straight across ground no edge covers has to answer the same
            question, and only the polygons can answer it there. From the
            country module's ``protected_table``.
        water: The sea and the lakes as outlines. Rasterised here at
            ``WATER_CELL_M`` and carried in the header, because a straight walk
            is priced by what it crosses and the page prices thousands of them
            in one search.
        rivers: The rivers as outlines, carrying ``name``
        bounds: The box the grid covers, which is the zone: a leg laid outside
            it is priced as ground, and there is no network outside it to lay
            one to.

    Returns:
        The payload, and its size
    """
    return encode_graph(
        network.chains,
        network.edges.to_crs(PAYLOAD_CRS),
        # The frame's own order is not the order a chain's edges lie in — one
        # chain in five does not even join up in it — and the browser has no
        # chain geometry to project them onto, so it has to be told.
        order,
        costs=costs,
        areas=areas,
        water=water_mask(water, bounds, WATER_CELL_M),
        # Outlines and not bits, for a sentence and not a price: see
        # ``RIVER_TOLERANCE_M``.
        rivers=river_table(rivers, bounds, RIVER_TOLERANCE_M),
    )


class PointLayer(NamedTuple):
    """One point layer of the map, and its row in the legend.

    Attributes:
        gdf: Points to draw
        label: Layer name in the control and legend, ending in its source
        legend_color: The colour its legend row is keyed with -- a pin carries
            an icon colour by name, so the row needs a value of its own
        popup_fields: Mapping of column name to popup label
        point_type: What a waypoint set beside one of these is called after
        source: Dataset the points came from
        pin: True for a pin with an icon, False for a labelled dot
        color: The pin's colour, one of the names awesome-markers knows, or the
            dot's CSS colour
        icon: The pin's glyph
        radius: The dot's radius
        label_field: Column the pin's hover label reads
        show: Whether the layer starts switched on
    """

    gdf: gpd.GeoDataFrame
    label: str
    legend_color: str
    popup_fields: dict[str, str]
    point_type: str
    source: str
    pin: bool = True
    color: str = "darkred"
    icon: str = "house-chimney"
    radius: float = 6.0
    label_field: str | None = "name"
    show: bool = True


class NameLayer(NamedTuple):
    """One layer of names drawn as text, and its row in the legend.

    Attributes:
        gdf: Labels carrying ``name``, ``font_size``, ``color`` and ``symbol``
        heading: Layer name, which the legend row also carries
        color: The colour the legend row is keyed with
    """

    gdf: gpd.GeoDataFrame
    heading: str
    color: str


class Export(NamedTuple):
    """One GPX file of one source's chains.

    Attributes:
        filename: What the file is called, after the map's own prefix
        source: Whose chains it holds
        chains: The chains, described
        name_field: Column a track is named from
        desc_fields: Columns written into a track's description
    """

    filename: str
    source: str
    chains: gpd.GeoDataFrame
    name_field: str
    desc_fields: list[str]


class Built(NamedTuple):
    """Everything one country's registers put on the map, ready to be assembled.

    What :func:`assemble` needs and nothing about where it came from: the
    graph, what is drawn over it, what the page is told, and what the files
    say about themselves.

    Attributes:
        park: The park boundary, in EPSG:4326
        zone: The ground the graph covers, in EPSG:4326
        params: What decided the build
        network: The finished graph, in the country's metric CRS
        order: Which of a chain's edges comes first, and which way round
        tracks: The dense, height-carrying line of every chain, for the files
        layers: The line layers, back to front
        points: The point layers, in the order they are added
        names: The name layers, drawn as text and off by default
        highlighted: Positions of a name asked for with ``--highlight``
        water: The sea and the lakes as outlines, over the zone's box
        rivers: The rivers as outlines, carrying ``name``
        costs: What a metre on each dataset costs a route
        areas: The protected areas, for the page
        credits: What every exported file names
        heights: Where a straight leg's heights come from, for plan mode
        boundary_label: What the boundary's legend row says
        exports: The GPX files to write
    """

    park: gpd.GeoDataFrame
    zone: gpd.GeoDataFrame
    params: graphs.Params
    network: Network
    order: pd.DataFrame
    tracks: gpd.GeoSeries
    layers: list[TrailLayer]
    points: list[PointLayer]
    names: list[NameLayer]
    highlighted: gpd.GeoDataFrame
    water: gpd.GeoDataFrame
    rivers: gpd.GeoDataFrame
    costs: dict[str, dict[str, float]]
    areas: list[dict[str, object]]
    credits: Credits
    heights: dict[str, object]
    boundary_label: str
    exports: list[Export]


def laid_out(network: Network) -> tuple[pd.DataFrame, gpd.GeoSeries]:
    """Lay every chain out as the line an export writes.

    A third thing beside the one the map draws and the one a route is found
    over: every vertex, a point wherever two are more than 5 m apart, and a
    height on each. Laid out once, off the same edge order the page's payload
    is encoded from — the browser writes the same file, and the two agree only
    because they walk the same walk.

    Args:
        network: The finished graph

    Returns:
        The edge order, and the track of every chain
    """
    order = chain_order(network.chains, network.edges)
    tracks = chain_tracks(network.chains, network.edges, order)
    print(f"\nExport tracks: {int(tracks.count_coordinates().sum()):,} points over {int(network.chains['length_m'].sum() / 1000):,} km")
    print(f"\nChains from the graph: {len(network.chains):,} drawn, over {len(network.edges):,} routing edges")
    return order, tracks


def split_at_the_boundary(by_source: dict[str, gpd.GeoDataFrame], sources: tuple[tuple[str, str], ...]) -> dict[str, gpd.GeoDataFrame]:
    """Put each source's chains into a park layer and an approach layer, and say how many.

    Args:
        by_source: One frame per source, described
        sources: Each source with the word its labels use for it

    Returns:
        The frames keyed ``{source}/park`` and ``{source}/approach``
    """
    layer_of: dict[str, gpd.GeoDataFrame] = {}
    for source, word in sources:
        frame = by_source[source]
        layer_of[f"{source}/park"] = frame[frame["in_park"]]
        layer_of[f"{source}/approach"] = frame[~frame["in_park"]]
        summarize(f"{word} inside park", layer_of[f"{source}/park"])
        summarize(f"{word} in approach zone", layer_of[f"{source}/approach"])
    return layer_of


def styled_names(names: gpd.GeoDataFrame, spacing_m: float, metric_crs: str) -> gpd.GeoDataFrame:
    """Thin a set of names and give each the size, colour and glyph it is drawn with.

    Args:
        names: Names carrying ``name``, ``rank`` (lower is more prominent),
            ``color`` and ``symbol``
        spacing_m: Minimum distance between two labels of the same name
        metric_crs: The CRS the spacing is measured in

    Returns:
        The names kept, with ``font_size``
    """
    if not len(names):
        return names
    # A name repeated along a feature only reads as a repetition when the
    # copies are far enough apart; closer than this they collide.
    before = len(names)
    thinned = thin_points(names, spacing_m, group_by="name", priority="rank", metric_crs=metric_crs).copy()
    # The register ranks importance itself; use it for label size rather
    # than drawing every name at the same weight.
    thinned["font_size"] = (15.0 - thinned["rank"] * 0.5).clip(lower=10.0).round(1)
    repeated = int(thinned["name"].duplicated(keep=False).sum())
    print(f"  names: {len(thinned)} labels ({before - len(thinned)} thinned out)")
    print(f"    {repeated} of them are repeats of an extended feature")
    print(f"    {thinned['kind'].value_counts().head(6).to_dict()}")
    return thinned


def highlight(names: gpd.GeoDataFrame, wanted: str | None) -> gpd.GeoDataFrame:
    """Pick out every position the register holds for one name, numbered.

    Args:
        names: Names carrying ``name`` and ``kind``
        wanted: The name asked for, or None

    Returns:
        Its positions with a ``marker_label``, empty where nothing was asked for
    """
    if not wanted:
        return gpd.GeoDataFrame()
    found = names[names["name"].str.casefold() == wanted.casefold()].copy()
    print(f"  highlighting '{wanted}': {len(found)} position(s) before thinning")
    for number, (_, row) in enumerate(found.iterrows(), start=1):
        print(f"    {number}: {row.geometry.y:.5f} / {row.geometry.x:.5f}  kind={row['kind']}")
    found["marker_label"] = [f"{i}. {n}" for i, n in enumerate(found["name"], start=1)]
    return found


# ---- Norway ------------------------------------------------------------------


def build_norway(which: Park, args: argparse.Namespace, repo_root: Path) -> Built:
    """Read the Norwegian registers and put everything they say on the map.

    Args:
        which: The park
        args: The command line
        repo_root: The checkout, for the UT.no catalogue

    Returns:
        What :func:`assemble` needs
    """
    if args.ut_routes is None:
        args.ut_routes = str(repo_root / "analysis" / "routes" / which.ut_routes) if which.ut_routes else ""

    park = load_park_boundary(which, args.cache_dir)
    params = norway.Params.from_args(args)
    # Park and approach zone as one polygon. Nothing here is split at the
    # boundary; where a layer is, it is decided per chain further down.
    zone = norway.zone_around(park, params.approach_km)

    loaded = norway.load_sources(params, zone)
    network, _ = norway.build(loaded.sources, norway.masks_from(loaded.sources), zone, params, name=which.stem, protected=loaded.protected)
    by_source = describe_norway(describe(network.chains, park, norway.SOURCE_NAMES, PLACEHOLDER_IDENTITIES))
    order, tracks = laid_out(network)

    routes = by_source[UT]
    ut_core = routes[routes["category"] == "core"]
    ut_access = routes[routes["category"] == "access"]
    trails = by_source[TURRUTEBASEN]
    roads = by_source[N50_ROADS]
    ferries = by_source[FERRIES]

    layer_of = split_at_the_boundary(by_source, ((FKB, "FKB paths"), (N50_PATHS, "N50 paths"), (OSM, "OSM paths")))

    in_park, in_approach = trails[trails["in_park"]], trails[~trails["in_park"]]
    summarize("Turrutebasen inside park", in_park)
    summarize("  of which DNT-maintained", in_park[in_park["is_dnt"]])
    summarize("Turrutebasen in approach zone", in_approach)
    summarize("  of which DNT-maintained", in_approach[in_approach["is_dnt"]])
    summarize("UT.no core and park routes", ut_core)
    summarize("UT.no access routes", ut_access)
    print(f"  {routes['guide_url_no'].notna().sum()} of {len(routes)} also described on lomsdalvisten.no")

    roads_private, roads_public = roads[roads["is_private"]], roads[~roads["is_private"]]
    summarize("Private roads (forest and farm tracks)", roads_private)
    summarize("Public roads", roads_public)
    named = roads["road_name"].notna()
    named_km, total_km = roads.loc[named, "length_km"].sum(), roads["length_km"].sum()
    print(f"  named from SSR: {int(named.sum()):,} of {len(roads):,} chains, {named_km:,.0f} of {total_km:,.0f} km")
    # A chain that changes category along its run reads as both, and it is
    # drawn public: the colour encodes who may drive it, and a road public for
    # half its length is not a private road. Worth printing, because it is the
    # one place a chain has to answer a question its pieces disagreed on.
    mixed = roads["road_category"].map(lambda value: len(parts_of(value)) > 1)
    print(f"  {int(mixed.sum()):,} chains change category along their run ({roads.loc[mixed, 'length_km'].sum():,.0f} km), and are drawn public")
    print(f"    {roads['road_category'].value_counts().head(6).to_dict()}")
    summarize("Ferry crossings", ferries)

    codes = loaded.municipalities

    print("\nLoading place names (SSR)...")
    names_source = stedsnavn.Source(cache_dir=args.cache_dir)
    # Read the register once, in full, and split it here. The terrain names
    # are a map layer; the rest answer "where is the place the brochure named",
    # which is a different job and a different extent.
    all_names = names_source.load_places(codes, name_types=None, force_download=args.force_download)

    def of_kind(types: tuple[str, ...], where: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Names of certain feature types, clipped to an area."""
        return gpd.clip(all_names[all_names["kind"].isin(types)], where)

    terrain_names = of_kind(stedsnavn.TERRAIN_NAME_TYPES, norway.zone_around(park, args.names_km))
    settlements = of_kind(stedsnavn.SETTLEMENT_NAME_TYPES, zone)
    farms = of_kind(stedsnavn.FARM_NAME_TYPES, zone)
    ssr_huts = of_kind(stedsnavn.HUT_NAME_TYPES, zone)
    ssr_quays = of_kind(stedsnavn.QUAY_NAME_TYPES, zone)
    hut_names = all_names[all_names["kind"].isin(stedsnavn.HUT_NAME_TYPES)]
    print(f"  settlements: {len(settlements)} | farms and holdings: {len(farms)}")
    print(f"  named huts: {len(ssr_huts)} | quays: {len(ssr_quays)}")

    highlighted = highlight(terrain_names, args.highlight)

    if len(terrain_names):
        terrain_names = terrain_names.copy()
        terrain_names["color"] = terrain_names["kind"].map(TERRAIN_NAME_COLORS).fillna(TERRAIN_NAME_DEFAULT_COLOR)
        terrain_names["symbol"] = terrain_names["kind"].map(TERRAIN_NAME_SYMBOLS).fillna(TERRAIN_NAME_DEFAULT_SYMBOL)
        print(f"  terrain names (<{args.names_km:g} km):", end="")
        terrain_names = styled_names(terrain_names, args.names_spacing_m, norway.METRIC_CRS)

    print("\nLoading N50 cabins...")
    n50_source = n50.Source(cache_dir=args.cache_dir)
    # N50 names cabins that OSM and the place-name register often miss.
    cabins = gpd.clip(n50_source.load_cabins(codes, force_download=args.force_download), zone)
    if len(cabins) and len(hut_names):
        # N50 has the buildings but names few of them; the register names the
        # huts but is missing some as buildings. Joined, Sæterskaret skogstue —
        # the hut from the park brochure — finally carries its name.
        before = int(cabins["navn"].notna().sum())
        cabins = attach_nearest(cabins, hut_names, {"name": "ssr_name"}, max_distance_m=args.hut_name_m, metric_crs=norway.METRIC_CRS)
        cabins["navn"] = cabins["navn"].fillna(cabins["ssr_name"])
        print(f"  named from SSR: {int(cabins['navn'].notna().sum()) - before} cabin(s) that N50 leaves unnamed")
    print(f"  N50 cabins and wilderness huts: {len(cabins)} ({cabins['navn'].notna().sum() if len(cabins) else 0} named)")

    print("\nLoading N50 water...")
    # The sea and the lakes, for pricing a straight walk by what it crosses.
    # Clipped to the zone's box and not to the zone: the box is what the page's
    # grid covers, and a sound in its corner is water whether or not the zone's
    # outline reaches it.
    water = gpd.clip(n50_source.load_water(codes, force_download=args.force_download), box(*bounds_of(zone)))
    print(f"  {len(water):,} outlines: {water['objtype'].value_counts().to_dict() if len(water) else {}}")
    # The rivers N50 draws as outlines, for what a straight walk wades through
    # and how wide it is there. Not priced: see ``RIVER_COVER_TYPES``.
    rivers = gpd.clip(n50_source.load_rivers(codes, force_download=args.force_download), box(*bounds_of(zone)))
    # N50's own ``navn`` is empty for every river outline in this build
    # (measured: 0 of 413), so the names come from the register, from the
    # points it places on the water: one outline in three gets one within
    # 60 m. The rest are said as *a river*, which is true.
    river_names = all_names[all_names["kind"] == RIVER_NAME_TYPE]
    rivers["name"] = attach_nearest(rivers.drop(columns=["name"]), river_names, {"name": "name"}, RIVER_NAME_M, metric_crs=norway.METRIC_CRS)["name"]
    print(f"  {len(rivers):,} rivers as outlines, {int(rivers['name'].notna().sum()):,} of them named from the register")
    if len(cabins):
        print(f"    {cabins['kind'].value_counts().to_dict()}")

    print("\nLoading OpenStreetMap points...")
    osm_source = overpass.Source(cache_dir=args.cache_dir)
    search_bounds = bounds_of(zone)
    # Shelters and settlements matter inside the park and along the way in.
    shelters = gpd.clip(osm_source.fetch_shelters(search_bounds, force_download=args.force_download), zone)
    places = gpd.clip(osm_source.fetch_places(search_bounds, force_download=args.force_download), zone)
    terminals = gpd.clip(osm_source.fetch_ferry_terminals(search_bounds, force_download=args.force_download), zone)

    # Farms and sæters are the actual starting points here (Bønnåa, Strompdalen,
    # Stavassgården), but the region has over a thousand of them, so they are
    # limited to a narrow band around the boundary.
    trailheads = gpd.clip(
        osm_source.fetch_places(search_bounds, place_types=TRAILHEAD_PLACE_TYPES, force_download=args.force_download),
        norway.zone_around(park, args.trailhead_km),
    )
    print(f"  Shelters and huts: {len(shelters)}")
    print(f"  Settlements: {len(places)}")
    print(f"  Trailheads (<{args.trailhead_km:g} km from boundary): {len(trailheads)}")
    print(f"  Ferry and express-boat quays: {len(terminals)}")

    approach_label = f"≤{args.approach_km:g} km"
    # Layers are added back-to-front so official routes draw on top of OSM,
    # and only non-empty ones appear in the control and legend. Everything is on
    # by default except the terrain names, which the topo backdrop already draws.
    # Every label ends with its dataset in brackets, so the legend and the layer
    # control always say where a line or a name came from.
    layers = [
        # Roads first, so they sit under the walking network: they are how you get
        # to the start, not part of the walk. Muted for the same reason.
        TrailLayer(roads_public, "Roads, public [N50+SSR]", "#b0bec5", 2.0, ROAD_POPUP_FIELDS, search_field="road_name"),
        TrailLayer(roads_private, "Roads, private [N50+SSR]", "#a1887f", 2.0, ROAD_POPUP_FIELDS, search_field="road_name"),
        TrailLayer(ferries, "Ferry crossings [N50]", "#0277bd", 2.5, FERRY_POPUP_FIELDS, dash="10,7"),
        TrailLayer(layer_of[f"{OSM}/approach"], f"Paths, approach {approach_label} [OSM]", "#ce93d8", 1.5, OSM_POPUP_FIELDS, search_field="name"),
        TrailLayer(layer_of[f"{N50_PATHS}/approach"], f"Paths, approach {approach_label} [N50]", "#80cbc4", 1.5, N50_POPUP_FIELDS),
        TrailLayer(layer_of[f"{FKB}/approach"], f"Paths, approach {approach_label} [FKB]", "#5c6bc0", 1.8, FKB_POPUP_FIELDS),
        TrailLayer(
            in_approach[~in_approach["is_dnt"]],
            f"Marked routes, approach {approach_label} [Turrutebasen]",
            "#f9a825",
            2.5,
            TRAIL_POPUP_FIELDS,
            search_field="trail_name",
        ),
        TrailLayer(
            in_approach[in_approach["is_dnt"]],
            f"DNT routes, approach {approach_label} [Turrutebasen]",
            "#ef6c00",
            3.5,
            TRAIL_POPUP_FIELDS,
            search_field="trail_name",
        ),
        TrailLayer(layer_of[f"{OSM}/park"], "Paths in park [OSM]", "#8e24aa", 2.5, OSM_POPUP_FIELDS, search_field="name"),
        TrailLayer(layer_of[f"{N50_PATHS}/park"], "Paths in park [N50]", "#00796b", 2.5, N50_POPUP_FIELDS),
        TrailLayer(layer_of[f"{FKB}/park"], "Paths in park [FKB]", "#283593", 3.0, FKB_POPUP_FIELDS),
        TrailLayer(
            in_park[~in_park["is_dnt"]], "Marked routes in park [Turrutebasen]", "#1b5e20", 3.5, TRAIL_POPUP_FIELDS, search_field="trail_name"
        ),
        TrailLayer(in_park[in_park["is_dnt"]], "DNT routes in park [Turrutebasen]", "#c62828", 4.0, TRAIL_POPUP_FIELDS, search_field="trail_name"),
        # UT.no last, and therefore on top: these are the only lines that come
        # with a written description, so they should win wherever they share a
        # path with a Turrutebasen or FKB line. They also carry links, which no
        # other layer does.
        # **No hover label on either of these.** They are the only layers that
        # ever had one, and on a phone a label opens on a tap and stays there:
        # a second heading over the ground, saying what the row at the foot
        # already says under the same name. The name is carried as a figure and
        # read from there — by the panel's heading and by a docked popup's
        # title alike — so nothing is lost by not drawing it.
        TrailLayer(
            ut_core,
            "Routes [UT.no]",
            "#d81b60",
            4.0,
            UT_POPUP_FIELDS,
            UT_LINK_FIELDS,
            search_field="name",
            link_heading=UT_LINK_HEADING,
            published_fields=UT_PUBLISHED_FIELDS,
        ),
        TrailLayer(
            ut_access,
            "Access routes [UT.no]",
            "#f48fb1",
            3.0,
            UT_POPUP_FIELDS,
            UT_LINK_FIELDS,
            search_field="name",
            link_heading=UT_LINK_HEADING,
            published_fields=UT_PUBLISHED_FIELDS,
        ),
    ]

    # Point layers, in the order they are added. Each carries the colour its
    # legend row is keyed with, since a pin carries an icon colour by name.
    points = [
        PointLayer(terminals, "Ferry quays [OSM]", "#5f9ea0", TERMINAL_POPUP_FIELDS, "ferry quay", "OSM", color="cadetblue", icon="ship"),
        PointLayer(cabins, "Cabins and wilderness huts [N50]", "#8b0000", CABIN_POPUP_FIELDS, "cabin", "N50", label_field="navn"),
    ]
    # **One layer per kind of name rather than one for all of them.** They are
    # different questions — where the water runs, where the passes are — and a
    # planner usually wants one of them and not the other five. Split after the
    # thinning above, so each keeps the labels that survived it.
    names: list[NameLayer] = []
    if len(terrain_names):
        drawn_kinds = set(terrain_names["kind"])
        for label, kinds in TERRAIN_NAME_LEGEND:
            present = sorted(kinds & drawn_kinds)
            if not present:
                continue
            part = terrain_names[terrain_names["kind"].isin(present)]
            # Types can share a colour but differ in glyph (fjell vs li), so
            # show every glyph the group actually draws.
            glyphs = dict.fromkeys(TERRAIN_NAME_SYMBOLS.get(kind, TERRAIN_NAME_DEFAULT_SYMBOL) for kind in present)
            names.append(NameLayer(part, f"Name {' '.join(glyphs)} {label} — {', '.join(present)} [SSR]", TERRAIN_NAME_COLORS[present[0]]))
    points.extend(
        [
            # Two of these have no N50 building at all, so the join above cannot
            # reach them; as their own layer none of the register's huts is lost.
            PointLayer(ssr_huts, "Named huts [SSR]", "#800080", SSR_POINT_POPUP_FIELDS, "hut", "SSR", color="purple"),
            PointLayer(ssr_quays, "Quays [SSR]", "#0000cd", SSR_POINT_POPUP_FIELDS, "quay", "SSR", color="blue", icon="anchor"),
            PointLayer(shelters, "Huts and shelters [OSM]", "#00008b", SHELTER_POPUP_FIELDS, "shelter", "OSM", color="darkblue", icon="campground"),
            PointLayer(
                trailheads,
                "Trailheads, farms and sæters [OSM]",
                "#6d4c41",
                PLACE_POPUP_FIELDS,
                "trailhead",
                "OSM",
                pin=False,
                color="#6d4c41",
                radius=5.5,
            ),
            # Names appear on hover only, like every other point layer. Drawing
            # 165 settlement names permanently competes with the topo backdrop,
            # which already labels them.
            PointLayer(places, "Towns and villages [OSM]", "#37474f", PLACE_POPUP_FIELDS, "settlement", "OSM", pin=False, color="#37474f"),
            PointLayer(settlements, "Towns and villages [SSR]", "#263238", SSR_POINT_POPUP_FIELDS, "settlement", "SSR", pin=False, color="#263238"),
            # Over a thousand of them: drawn they would bury the map, so the
            # layer starts off. The search switches it on by itself when a name
            # matches, which is the point of carrying them at all.
            PointLayer(
                farms,
                "Farms and holdings [SSR]",
                "#8d6e63",
                SSR_POINT_POPUP_FIELDS,
                "farm",
                "SSR",
                pin=False,
                color="#8d6e63",
                radius=4.5,
                show=False,
            ),
        ]
    )

    credits = Credits(
        sources=source_credits(loaded.versions, NORWAY_SOURCE_TERMS, NORWAY_SOURCE_METADATA),
        heights=height_credit(hoydedata.METADATA),
        protected=protected_credit(naturbase.METADATA),
        ascent=ascent_method(params, NORWAY_HEIGHT_MODEL),
    )
    exports = [
        Export(
            f"{which.stem}-turrutebasen.gpx", TURRUTEBASEN, trails, "trail_name", ["maintenance_responsible", "difficulty", "marking", "length_km"]
        ),
        Export(f"{which.stem}-fkb.gpx", FKB, by_source[FKB], "typeveg", ["typeveg", "length_km"]),
        Export(f"{which.stem}-n50.gpx", N50_PATHS, by_source[N50_PATHS], "typeveg", ["typeveg", "rutemerking", "length_km"]),
        Export(f"{which.stem}-osm.gpx", OSM, by_source[OSM], "name", ["highway", "surface", "sac_scale", "length_km"]),
        # One file with all catalogued routes, named, instead of 35 downloads.
        Export(f"{which.stem}-ut.gpx", UT, routes, "name", ["category_label", "length_km", "ut_url"]),
        # The chain's own length, not the whole road's: a track in this file
        # *is* one chain, and a figure about other tracks would not describe it.
        Export(f"{which.stem}-roads.gpx", N50_ROADS, roads, "road_name", ["road_category", "length_km"]),
    ]
    return Built(
        park=park,
        zone=zone,
        params=params,
        network=network,
        order=order,
        tracks=tracks,
        layers=layers,
        points=points,
        names=names,
        highlighted=highlighted,
        water=water,
        rivers=rivers,
        costs=norway.edge_costs(loaded.sources, params),
        areas=norway.protected_table(loaded.protected),
        credits=credits,
        heights=NORWAY_PLAN_HEIGHTS,
        boundary_label="National park boundary [Naturbase]",
        exports=exports,
    )


# ---- Sweden ------------------------------------------------------------------

#: How far a Topografi 50 cabin may look for its name in the place-name
#: register. The register's point stands for the place and a cabin group is
#: several buildings, so this is wider than the 50 m a Norwegian cabin looks
#: for a register point.
CABIN_LABEL_M = 150.0

#: How far a river surface may look for its name among the register's
#: watercourse names.
T50_RIVER_NAME_M = 60.0


def lettered_size(names: gpd.GeoDataFrame, lettered: gpd.GeoDataFrame, within_m: float, metric_crs: str) -> pd.Series:
    """The map's lettering size for each place: the nearest label within reach that carries one of the place's names.

    **One of its names, and the nearest of those -- not the nearest label,
    which then had to carry the name.** Asked the second way, a place whose own
    label is 300 m off lost its size to a tarn's label 100 m off, and a river
    whose Sámi name the map letters nearer than its Swedish one lost it to
    itself: 7 of 210 lettered places over Abisko, Kungsleden and Kårsajåkka
    among them (decisions §8.2). A place's names are its first and every
    ``also`` the pairing gave it.

    Args:
        names: Places with ``name`` and ``also`` (comma-joined) columns
        lettered: Labels with ``lettered`` and ``size`` columns
        within_m: How far a label may stand from its place
        metric_crs: Where metres are metres

    Returns:
        The size per place, aligned to ``names``, NaN where no label of its name is in reach
    """
    places = names.to_crs(metric_crs)
    labels = lettered.to_crs(metric_crs).reset_index(drop=True)
    reach = gpd.GeoDataFrame({"place": places.index}, geometry=places.geometry.buffer(within_m).to_numpy(), crs=metric_crs)
    hits = gpd.sjoin(reach, labels, how="inner", predicate="intersects")
    if hits.empty:
        return pd.Series(float("nan"), index=names.index, dtype=float)
    called = {
        at: {str(name).casefold(), *(each.strip().casefold() for each in str(also).split(",") if each.strip())}
        for at, name, also in zip(names.index, names["name"], names["also"], strict=True)
    }
    hits = hits[[str(text).casefold() in called[at] for at, text in zip(hits["place"], hits["lettered"], strict=True)]].copy()
    at_place = places.index.get_indexer(pd.Index(hits["place"]))
    hits["away"] = shapely.distance(places.geometry.to_numpy()[at_place], labels.geometry.to_numpy()[hits["index_right"].to_numpy()])
    hits = hits.sort_values("away").drop_duplicates("place")
    return pd.Series(hits["size"].to_numpy(), index=hits["place"]).reindex(names.index).astype(float)


def build_sweden(which: Park, args: argparse.Namespace, repo_root: Path) -> Built:
    """Read the Swedish registers and put everything they say on the map.

    Args:
        which: The park
        args: The command line
        repo_root: The checkout; unused here, and in the signature so the two
            builds are one shape

    Returns:
        What :func:`assemble` needs
    """
    del repo_root
    if which.bounds is None:
        raise ValueError(f"{which.name} declares no box, and the Swedish build is over a box (decisions §2)")

    register = naturvardsregistret.Source(cache_dir=args.cache_dir)
    park = load_swedish_boundary(which, register)
    # **The box takes no approach zone, so the fingerprint takes none either.**
    # `approach_km` shapes the Norwegian band and nothing here; left in the
    # key it forced a full rebuild, height pass and all, of an identical graph
    # whenever the docstring's own `--approach-km 5` was typed (§8.2).
    params = dataclasses.replace(sweden.Params.from_args(args), approach_km=0.0)
    # **The box, not a band round the park.** The tiles were copied for it and
    # the height mosaic was read over it, and the mosaic's cache is named by
    # the bounds it was read over, so the graph is cut to exactly the box or
    # the mosaic is read again. What --approach-km would widen is not here.
    zone = gpd.GeoDataFrame(geometry=[box(*which.bounds)], crs="EPSG:4326")
    width_km = zone.to_crs(sweden.METRIC_CRS).geometry.iloc[0].bounds
    print(f"  Box: {which.bounds}, {(width_km[2] - width_km[0]) / 1000:,.0f} x {(width_km[3] - width_km[1]) / 1000:,.0f} km")

    loaded = sweden.load_sources(params, zone)
    network, _ = sweden.build(loaded.sources, sweden.masks_from(loaded.sources), zone, params, name=which.stem, protected=loaded.protected)
    by_source = describe_sweden(describe(network.chains, park, sweden.SOURCE_NAMES))
    order, tracks = laid_out(network)

    leder = by_source[LEDER]
    roads = by_source[T50_ROADS]
    ferries = by_source[sweden.FERRIES]
    layer_of = split_at_the_boundary(
        by_source, ((LEDER, "State trails"), (T50_TRAILS, "Topografi 50 marked trails"), (T50_PATHS, "Topografi 50 paths"), (OSM, "OSM paths"))
    )
    named = leder[naturvardsregistret.TRAIL_NAME].notna()
    print(f"  state trails named by the register: {int(named.sum()):,} of {len(leder):,} chains")
    print(f"    {leder['route'].value_counts().head(8).to_dict()}")
    summarize("Roads", roads)
    print(f"    {roads['road_class'].value_counts().head(6).to_dict()}")
    print(f"    numbered: {int(roads['road_number'].notna().sum()):,} of {len(roads):,} chains ({roads['road_number'].dropna().unique().tolist()})")
    summarize("Ferry crossings", ferries)
    winter = loaded.winter
    print(f"  winter-only lines kept apart: {len(winter):,} ({winter['kind'].value_counts().to_dict()})")

    bounds = bounds_of(zone)
    country = topografi50.Source(cache_dir=args.cache_dir)

    print("\nLoading place names (Ortnamn)...")
    # **Clipped to the box, as every point layer below is.** The register is
    # read over the SWEREF envelope of the box, which bows 60 m past its
    # north and south edges; 26 of 391 names stood on ground the map has no
    # tiles for (decisions §8.2), and the cabins, facilities and trail points
    # went the same way.
    inside = box(*bounds)
    register_names = gpd.clip(ortnamn.Source(cache_dir=args.cache_dir).names(bounds, force_download=args.force_download), inside).reset_index(
        drop=True
    )
    print(f"  {len(register_names):,} names: {register_names['kind_label'].value_counts().to_dict()}")
    print(f"    {register_names['language'].value_counts().to_dict()}")
    # **One place, one label, Swedish first.** The register carries each
    # language as a point of its own; joined, a place with two names reads
    # *Abiskojåkka (Ábeskoeatnu)* -- the name on the signs first, the Sámi one
    # in brackets -- and a river is named by the place and not by whichever
    # point lies nearer (decisions §9.12).
    names = ortnamn.paired(register_names)
    with_another = names["also"].astype("string").str.len().gt(0)
    print(f"  {len(names):,} places once the languages are joined within {ortnamn.PAIR_M:g} m; {int(with_another.sum())} carry a second name")
    # The map's own lettering, for the size: the register ranks nothing, and
    # the lettering is what says *Torneträsk* is written large and a tarn
    # small. Joined by the same name within reach, since the word sits beside
    # the place rather than on it.
    labels = country.labels(bounds, force_download=args.force_download)
    lettered = labels[["name", "size", "geometry"]].rename(columns={"name": "lettered"})
    sizes = lettered_size(names, lettered, LETTERING_M, sweden.METRIC_CRS)
    names["size"] = sizes.fillna(1).astype(int)
    print(f"  {int(sizes.notna().sum()):,} of them lettered on the map within {LETTERING_M:g} m, and drawn at that size")
    # Matched on the first name above; labelled with both from here on.
    names["name"] = [ortnamn.label(name, also) for name, also in zip(names["name"], names["also"], strict=True)]
    names["rank"] = 8 - names["size"]
    names["color"] = names["kind"].map(ORTNAMN_COLORS).fillna(TERRAIN_NAME_DEFAULT_COLOR)
    names["symbol"] = names["kind"].map(ORTNAMN_SYMBOLS).fillna(TERRAIN_NAME_DEFAULT_SYMBOL)
    highlighted = highlight(names, args.highlight)
    drawn_names = styled_names(names, args.names_spacing_m, sweden.METRIC_CRS)
    # A pixel per size class, so *Torneträsk* is drawn at 16 px and a name
    # the map does not letter at 10.
    drawn_names["font_size"] = (T50_LABEL_BASE_PX + drawn_names["size"]).astype(float)

    print("\nLoading OpenStreetMap points...")
    osm_source = overpass.Source(cache_dir=args.cache_dir)
    shelters = gpd.clip(osm_source.fetch_shelters(bounds, force_download=args.force_download), zone)
    places = gpd.clip(osm_source.fetch_places(bounds, force_download=args.force_download), zone)
    terminals = gpd.clip(osm_source.fetch_ferry_terminals(bounds, force_download=args.force_download), zone)
    print(f"  Shelters and huts: {len(shelters)}")
    print(f"  Settlements: {len(places)}")
    print(f"  Ferry and express-boat quays: {len(terminals)}")

    print("\nLoading Topografi 50 cabins...")
    cabins = gpd.clip(country.cabins(bounds, force_download=args.force_download), inside).reset_index(drop=True)
    settlement_names = names[names["kind"].isin(ortnamn.SETTLEMENT_TYPES)]
    if len(cabins) and len(settlement_names):
        # The product draws the building and the register names the place,
        # so the two are joined here by distance.
        cabins = attach_nearest(cabins, settlement_names, {"name": "register_name"}, max_distance_m=CABIN_LABEL_M, metric_crs=sweden.METRIC_CRS)
        cabins["name"] = cabins["register_name"]
        cabins["named_from"] = cabins["name"].map(lambda value: "Ortnamn" if isinstance(value, str) else None)
    from_register = int(cabins["name"].notna().sum()) if len(cabins) else 0
    if len(cabins) and len(shelters):
        # And where the register says nothing, OSM: it names the STF huts and
        # most shelters, and stands on the building rather than beside it.
        cabins = attach_nearest(
            cabins, shelters[shelters["name"].notna()], {"name": "osm_name"}, max_distance_m=args.hut_name_m, metric_crs=sweden.METRIC_CRS
        )
        from_osm = cabins["name"].isna() & cabins["osm_name"].notna()
        cabins.loc[from_osm, "name"] = cabins.loc[from_osm, "osm_name"]
        cabins.loc[from_osm, "named_from"] = "OpenStreetMap"
    named_cabins = int(cabins["name"].notna().sum()) if len(cabins) else 0
    print(
        f"  {len(cabins):,} cabins and huts, {from_register} named from the register within {CABIN_LABEL_M:g} m, "
        f"{named_cabins - from_register} more from OSM within {args.hut_name_m:g} m"
    )
    if len(cabins):
        print(f"    {cabins['kind'].value_counts().to_dict()}")

    print("\nLoading the register's facilities (Leder)...")
    facilities = gpd.clip(register.facilities(bounds, force_download=args.force_download), inside).reset_index(drop=True)
    facilities["name"] = facilities[naturvardsregistret.FACILITY_NAME]
    facilities["kind"] = translate_joined(facilities[naturvardsregistret.FACILITY_TYPE], FACILITY_LABELS)
    facilities["subtype"] = translate_joined(facilities[naturvardsregistret.FACILITY_SUBTYPE], FACILITY_LABELS)
    facilities["description"] = facilities[naturvardsregistret.TRAIL_DESCRIPTION]
    facilities["route"] = facilities[naturvardsregistret.TRAIL_ROUTE]
    print(f"  {len(facilities):,} facilities: {facilities['kind'].value_counts().to_dict()}")

    print("\nLoading Topografi 50 trail points...")
    trail_points = gpd.clip(country.trail_points(bounds, force_download=args.force_download), inside).reset_index(drop=True)
    print(f"  {len(trail_points):,}: {trail_points['kind'].value_counts().to_dict()}")

    print("\nLoading Topografi 50 water...")
    # The lakes and the river surfaces, for pricing a straight walk by what it
    # crosses; over the box, which is the zone here.
    water = gpd.clip(country.water(bounds, force_download=args.force_download), box(*bounds))
    print(f"  {len(water):,} outlines: {water[topografi50.TYPE].value_counts().to_dict() if len(water) else {}}")
    # The rivers drawn as a surface, for what a straight walk wades through
    # and how wide it is there; named from the register's watercourse names
    # where one lies within reach, said as *a river* otherwise.
    rivers = gpd.clip(country.rivers(bounds, force_download=args.force_download), box(*bounds))
    river_names = names[names["kind"] == "VATTDRTX"]
    rivers["name"] = attach_nearest(rivers.drop(columns=["name"]), river_names, {"name": "name"}, T50_RIVER_NAME_M, metric_crs=sweden.METRIC_CRS)[
        "name"
    ]
    print(f"  {len(rivers):,} rivers as outlines, {int(rivers['name'].notna().sum()):,} of them named from the register")

    layers = [
        # Roads first and muted, as in Norway: how you get to the start.
        TrailLayer(roads, "Roads [Topografi 50]", "#b0bec5", 2.0, T50_ROAD_POPUP_FIELDS, search_field="road_name"),
        TrailLayer(ferries, "Ferry crossings [Topografi 50]", "#0277bd", 2.5, T50_FERRY_POPUP_FIELDS, dash="10,7"),
        # The winter lines: not chains, off by default, and never routed over
        # (decisions §6.5). Drawn dashed and pale, so switched on they read as
        # what they are, a line over a frozen lake.
        TrailLayer(
            winter, "Winter trails, not routable [Leder+Topografi 50]", "#90caf9", 2.0, WINTER_POPUP_FIELDS, dash="6,6", chains=False, show=False
        ),
        TrailLayer(layer_of[f"{OSM}/approach"], "Paths, outside park [OSM]", "#ce93d8", 1.5, OSM_POPUP_FIELDS, search_field="name"),
        TrailLayer(layer_of[f"{T50_PATHS}/approach"], "Paths, outside park [Topografi 50]", "#80cbc4", 1.5, T50_PATH_POPUP_FIELDS),
        TrailLayer(
            layer_of[f"{T50_TRAILS}/approach"],
            "Marked trails, outside park [Topografi 50]",
            "#f9a825",
            2.5,
            T50_TRAIL_POPUP_FIELDS,
            search_field="route_name",
        ),
        TrailLayer(
            layer_of[f"{LEDER}/approach"], "State trails, outside park [Leder]", "#ef6c00", 3.5, LEDER_POPUP_FIELDS, search_field="trail_name"
        ),
        TrailLayer(layer_of[f"{OSM}/park"], "Paths in park [OSM]", "#8e24aa", 2.5, OSM_POPUP_FIELDS, search_field="name"),
        TrailLayer(layer_of[f"{T50_PATHS}/park"], "Paths in park [Topografi 50]", "#00796b", 2.5, T50_PATH_POPUP_FIELDS),
        TrailLayer(
            layer_of[f"{T50_TRAILS}/park"], "Marked trails in park [Topografi 50]", "#1b5e20", 3.5, T50_TRAIL_POPUP_FIELDS, search_field="route_name"
        ),
        # The register's state trails last and on top: the one source that
        # describes a trail rather than draws it, and the identity the marked
        # trails under it were named from.
        TrailLayer(layer_of[f"{LEDER}/park"], "State trails in park [Leder]", "#c62828", 4.0, LEDER_POPUP_FIELDS, search_field="trail_name"),
    ]
    points = [
        PointLayer(terminals, "Ferry quays [OSM]", "#5f9ea0", TERMINAL_POPUP_FIELDS, "ferry quay", "OSM", color="cadetblue", icon="ship"),
        PointLayer(cabins, "Cabins and huts [Topografi 50]", "#8b0000", T50_CABIN_POPUP_FIELDS, "cabin", "Topografi 50"),
        PointLayer(shelters, "Huts and shelters [OSM]", "#00008b", SHELTER_POPUP_FIELDS, "shelter", "OSM", color="darkblue", icon="campground"),
        PointLayer(
            facilities, "Bridges, shelters and privies [Leder]", "#6d4c41", FACILITY_POPUP_FIELDS, "facility", "Leder", pin=False, color="#6d4c41"
        ),
        PointLayer(
            trail_points,
            "Footbridges, fords and car parks [Topografi 50]",
            "#0277bd",
            TRAIL_POINT_POPUP_FIELDS,
            "trail point",
            "Topografi 50",
            pin=False,
            color="#0277bd",
            radius=4.5,
            label_field="kind",
        ),
        PointLayer(places, "Towns and villages [OSM]", "#37474f", PLACE_POPUP_FIELDS, "settlement", "OSM", pin=False, color="#37474f"),
    ]
    name_layers: list[NameLayer] = []
    if len(drawn_names):
        drawn_kinds = set(drawn_names["kind"])
        for label, kinds in ORTNAMN_LEGEND:
            present = [kind for kind in kinds if kind in drawn_kinds]
            if not present:
                continue
            part = drawn_names[drawn_names["kind"].isin(present)]
            glyphs = dict.fromkeys(ORTNAMN_SYMBOLS.get(kind, TERRAIN_NAME_DEFAULT_SYMBOL) for kind in present)
            heading = f"Name {' '.join(glyphs)} {label} — {', '.join(ortnamn.type_label(kind) for kind in present)} [Ortnamn]"
            name_layers.append(NameLayer(part, heading, ORTNAMN_COLORS[present[0]]))

    credits = Credits(
        sources=source_credits(loaded.versions, SWEDEN_SOURCE_TERMS, SWEDEN_SOURCE_METADATA),
        heights=height_credit(markhojd.METADATA),
        protected=protected_credit(naturvardsregistret.METADATA),
        ascent=ascent_method(params, SWEDEN_HEIGHT_MODEL),
    )
    exports = [
        Export(f"{which.stem}-leder.gpx", LEDER, leder, "trail_name", ["route", "trail_type", "marking", "length_km"]),
        Export(f"{which.stem}-topografi50-trails.gpx", T50_TRAILS, by_source[T50_TRAILS], "route_name", ["path_class", "length_km"]),
        Export(f"{which.stem}-topografi50-paths.gpx", T50_PATHS, by_source[T50_PATHS], "path_class", ["path_class", "length_km"]),
        Export(f"{which.stem}-osm.gpx", OSM, by_source[OSM], "name", ["highway", "surface", "sac_scale", "length_km"]),
        Export(f"{which.stem}-roads.gpx", T50_ROADS, roads, "road_name", ["road_class", "length_km"]),
    ]
    return Built(
        park=park,
        zone=zone,
        params=params,
        network=network,
        order=order,
        tracks=tracks,
        layers=layers,
        points=points,
        names=name_layers,
        highlighted=highlighted,
        water=water,
        rivers=rivers,
        costs=sweden.edge_costs(loaded.sources, params),
        areas=sweden.protected_table(loaded.protected),
        credits=credits,
        heights=sweden_plan_heights(which.base),
        boundary_label="National park boundary [Naturvårdsregistret]",
        exports=exports,
    )


#: How each country's map is built, by ISO 3166 code.
BUILDS = {"NO": build_norway, "SE": build_sweden}


# ---- the page, for either --------------------------------------------------------


def assemble(built: Built, which: Park, args: argparse.Namespace, output_dir: Path) -> None:
    """Put what a country's build produced onto the page, and write it and its files.

    Args:
        built: What the registers said
        which: The park
        args: The command line
        output_dir: Where the page, its companions and the GPX files go
    """
    network, layers = built.network, built.layers
    print("\nBuilding map...")
    # Fit to the full approach zone, not just the park, so trailhead towns are visible.
    fmap = maps.create_map(bounds=bounds_of(built.zone), base=which.base, extra_bases=which.extras, title=which.app_name, companions=which.companions)

    # **The legend is the layer control now**, so a row carries the layer it
    # switches and not only the colour it explains. A row that cannot reach its
    # layer would draw and switch nothing, which is worse than the two panels it
    # replaced, so every lookup below fails loudly rather than quietly.
    legend: list[maps.LegendRow] = []
    highlightable = []
    for layer in layers:
        if not len(layer.gdf):
            continue
        group = maps.add_trails(
            fmap,
            simplify_for_display(layer.gdf, args.simplify_m),
            name=layer.label,
            color=layer.color,
            weight=layer.weight,
            popup_fields=layer.popup_fields,
            published_fields=layer.published_fields,
            link_fields=layer.link_fields,
            link_heading=layer.link_heading,
            tooltip_field=layer.tooltip_field,
            dash_array=layer.dash,
            group_field=CHAIN_KEY if layer.chains else None,
            search_field=layer.search_field,
            figure_fields=CHAIN_FIGURE_FIELDS if layer.chains else None,
            source=source_of(layer.label),
            show=layer.show,
        )
        # A layer that is not chains -- the winter lines -- has no figures to
        # show and no chain to select, so it is drawn and listed and no more.
        if layer.chains:
            highlightable.append(group)
        legend.append(maps.LegendRow(f"{layer.label} ({len(layer.gdf)})", layer.color, group))

    # Six sources through the same handful of valleys are impossible to follow by
    # eye where they run together, so a click picks one chain out of the bundle.
    maps.add_click_highlight(fmap, highlightable)

    # Everything a name can be typed at, lines and points alike.
    searchable = list(highlightable)
    point_rows: list[tuple[str, int, str]] = []
    for point in built.points:
        if not len(point.gdf):
            continue
        if point.pin:
            group = maps.add_points(
                fmap,
                point.gdf,
                name=point.label,
                color=point.color,
                icon=point.icon,
                popup_fields=point.popup_fields,
                label_field=point.label_field,
                source=point.source,
                point_type=point.point_type,
                show=point.show,
            )
        else:
            group = maps.add_labelled_points(
                fmap,
                point.gdf,
                name=point.label,
                color=point.color,
                radius=point.radius,
                popup_fields=point.popup_fields,
                source=point.source,
                point_type=point.point_type,
                show=point.show,
            )
        searchable.append(group)
        point_rows.append((point.label, len(point.gdf), point.legend_color))
    name_rows: list[maps.LegendRow] = []
    for named in built.names:
        if not len(named.gdf):
            continue
        group = maps.add_text_labels(
            fmap,
            named.gdf,
            name=named.heading,
            label_field="name",
            size_field="font_size",
            color_field="color",
            symbol_field="symbol",
            show=False,
        )
        searchable.append(group)
        name_rows.append(maps.LegendRow(f"{named.heading} ({len(named.gdf)})", named.color, group))

    # One box over every named thing on the map: a brochure names a place, and
    # this is what turns that name into a position.
    maps.add_search(fmap, searchable)

    # Added last so the boundary outline stays legible on top of every trail layer.
    boundary = maps.add_boundary(fmap, built.park, name=built.boundary_label, weight=3.5)

    # And the graph itself, which nothing draws and nothing yet reads: phase 4
    # takes the profile off it and phase 6 routes over it, and both of those live
    # in Python until it is in the page.
    print("\nEncoding the routing graph for the page...")
    payload = encode_for_the_page(network, built.order, built.costs, built.areas, built.water, built.rivers, bounds_of(built.zone))
    counted = payload.header
    grid = counted["water"]
    wet, weight = 100 * grid["set"] / (grid["cols"] * grid["rows"]), len(grid["bits"]) / 1e3
    print(f"  water grid: {grid['cols']:,} x {grid['rows']:,} cells of {grid['cellM']:g} m, {wet:.1f} % water, {weight:.0f} kB in the page")
    laid = counted["rivers"]["rivers"]
    river_vertices = sum(len(ring) // 2 for river in laid for ring in river["rings"])
    print(f"  {len(laid):,} rivers as outlines, {river_vertices:,} vertices at {RIVER_TOLERANCE_M:g} m")
    print(f"  {counted['edges']:,} edges on {counted['nodes']:,} nodes, {counted['vertices']:,} vertices at full source precision")
    print(f"  {counted['samples']:,} height samples, quantised at {counted['coordinateQuantum']:g}° and {counted['elevationQuantum']:g} m")
    print(f"  {payload.raw_mb:.2f} MB encoded, {payload.size_mb:.2f} MB gzipped and base64 in the page")
    print(f"    before compression: {' · '.join(f'{name} {size / 1e6:.2f}' for name, size in payload.sections.items())}")
    maps.add_routing_graph(fmap, payload.header, payload.data)

    if len(built.highlighted):
        # Diagnostic layer: a ring plus a numbered label at every position the
        # register holds for one name, so it is obvious which ones actually draw.
        maps.add_labelled_points(fmap, built.highlighted, name=f"HIGHLIGHT: {args.highlight}", color="#e00000", radius=14)
        maps.add_text_labels(
            fmap, built.highlighted, name=f"HIGHLIGHT labels: {args.highlight}", label_field="marker_label", default_size=20, color="#e00000"
        )

    # It carried two names in one page until the legend and the layer control
    # became one panel — "Park boundary" here and "National park boundary" in the
    # control — which nothing noticed because nothing ever compared them.
    legend.append(maps.LegendRow(built.boundary_label, "#0d47a1", boundary))

    # Name colours are only decodable with a key, and each kind now switches.
    legend.extend(name_rows)

    # Every layer that reached the map, under the name it carries. The legend's
    # own label is built the same way — the layer's name and its count — so a
    # row that cannot find its layer means the two have drifted apart, and that
    # is worth a traceback rather than a row that silently switches nothing.
    drawn = {getattr(layer, "layer_name", None): layer for layer in searchable}

    def switched(label: str) -> object:
        """The layer a legend row switches.

        Args:
            label: The row's label, which is the layer's own name

        Returns:
            The layer that name belongs to

        Raises:
            KeyError: If no layer on the map carries that name
        """
        found = drawn.get(label)
        if found is None:
            raise KeyError(f"the legend row {label!r} names no layer on the map")
        return found

    # Point layers carry an icon rather than a line colour, so they are listed
    # here only to record their source alongside everything else.
    for label, count, color in point_rows:
        legend.append(maps.LegendRow(f"{label} ({count})", color, switched(f"{label} ({count})")))

    maps.add_legend(fmap, f"{which.name} {which.kind}", legend)

    # It shares the bottom left with the legend and the scale bar, and puts
    # itself under both: the panel takes the width, the legend keeps its corner
    # above it.
    with_profile = int(network.chains["ascent"].notna().sum())
    print(f"\nProfile panel: {with_profile:,} of {len(network.chains):,} chains carry one, {len(network.chains) - with_profile} say they have none")
    # And the panel writes the selected chain out. Everything the file says
    # about itself travels with it: the browser is what produces that file, and
    # a licence, a version or a field name it was not given is one it would have
    # to invent.
    maps.add_profile_panel(fmap, highlightable, export=export_settings(built.credits, which))

    # And a route can now be clicked together over the graph, leg by leg, with
    # its profile drawn in the same panel. After the panel, whose walk it lays
    # its route out with, and after the graph it routes over.
    # And the named points every one of these layers draws, so a waypoint set
    # beside a hut comes back called after the hut. The line layers go in too
    # and carry nothing: only a layer given a point_type has a table, and a
    # place name drawn as text asserts no single position to be named after.
    maps.add_plan_mode(fmap, plan_settings(built.params, [layer for layer in layers if layer.chains], built.heights), searchable)

    # And the one way into all of it, which is why it goes last: it adopts the
    # search, the legend, the base-map picker and the plan control, so every one
    # of them has to exist by the time it runs. What it buys is a map that opens
    # showing a map — measured on the built page, the legend alone left 23 % of
    # a 390 px screen and 74 % of a desktop one before anything was clicked.
    maps.add_chrome(fmap, credits=built.credits.sources)

    map_path = output_dir / f"{which.stem}.html"
    # Not `fmap.save`: that renders and writes in one step, and the page is
    # written without the indentation folium's templates render with.
    maps.save_map(fmap, map_path)
    print(f"  Map: {map_path} ({map_path.stat().st_size / 1e6:.1f} MB)")

    # **Written after the page and stamped with it.** A browser installs a
    # worker only when its bytes change, so the stamp is the page's own digest:
    # a deploy that changes the map changes the worker and drops the old copy,
    # and a rebuild that changes nothing changes nothing.
    worker = maps.write_service_worker(map_path, maps.provider_of_map(fmap), which.companions)
    print(f"  Worker: {worker} ({worker.stat().st_size / 1e3:.1f} kB)")

    # **What makes an offline copy survive being left alone.** WebKit deletes
    # storage a script created once an origin has gone seven days without a
    # visit -- exactly the walk somebody keeps the terrain for a fortnight
    # before -- and a home-screen install is one of the two exemptions.
    manifest = maps.write_manifest(map_path, which.app_name, which.companions)
    print(f"  Manifest: {manifest} ({manifest.stat().st_size / 1e3:.1f} kB)")

    # **The mark, as files.** The page links to `icon-180.png` rather than
    # carrying the drawing inline, because iOS reads `apple-touch-icon` off the
    # document and will not fetch a `data:` URI for it -- inline, the link is
    # well-formed and dead, and the home screen falls back to a screenshot.
    icons = maps.write_icons(map_path, which.companions)
    print(f"  Icons: {', '.join(icon.name for icon in icons)}")

    # Built from the chains, not from the raw sources, so one geometry serves
    # the map, the exports and the router. At full source precision: the
    # simplified copy above is the drawn one and goes nowhere near this.
    print("\nExporting GPX...")
    credits_of, heights = built.credits.sources, built.credits.heights
    for export in built.exports:
        if not len(export.chains):
            continue
        path, stats = export_to_gpx(
            # The dense, height-carrying line rather than the chain's own: the
            # heights were sampled along the edges and not at the vertices, and
            # the geometry a file is written from is the one the two were laid
            # against each other on.
            export.chains.assign(track=built.tracks),
            output_dir / export.filename,
            name_field=export.name_field,
            desc_fields=export.desc_fields,
            title=f"{which.name}: {export.source}",
            description=f"Every {export.source} chain of the {which.name} routing network",
            # The height model only where the file actually carries a height,
            # which is the rule the page follows chain by chain. A file of
            # crossings would name a source it never read a value from.
            sources=credits_of[export.source] + (heights if bool(export.chains["ascent"].notna().any()) else []),
            extension_fields=DEFAULT_EXTENSION_FIELDS,
            ascent_method=built.credits.ascent,
            track_field="track",
        )
        print(f"  {path.name}: {stats['total_trails']} tracks, {stats['total_points']:,} points, {stats['file_size_mb']:.2f} MB")

    print("\n" + "=" * 70)
    # What every exported file now carries in its own <metadata>, printed here
    # as well because a build's own log is where a discrepancy gets noticed.
    for entries in credits_of.values():
        for entry in entries:
            print(f"Source: {entry['name']} — {entry['licence']}{', ' + entry['note'] if entry['note'] else ''} — {entry['version'] or 'no version'}")
    print(f"Heights: {heights[0]['name']} — {heights[0]['licence']} — {built.credits.ascent}")
    entry = built.credits.protected[0]
    # It is in a route's file and in none of the chain files: a route states how
    # far it runs inside each protected area and a chain states nothing of the
    # kind, so the register has a claim on one and not the other.
    print(f"Protected: {entry['name']} — {entry['licence']} — in a planned route's file, in no chain's, and in the boundary drawn")
    print("=" * 70)


def main() -> int:
    """Build the map and GPX exports.

    Returns:
        Process exit code
    """
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--park", default="lomsdal-visten", choices=sorted(PARKS), help="Which map to build; see PARKS")
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Cache directory for downloaded data")
    parser.add_argument("--output-dir", default=str(repo_root / "analysis" / "output"), help="Directory for the map and GPX files")
    # 15 km reaches every realistic trailhead town: Tosbotn 2.6 km, Trofors 5.5 km,
    # Mosjøen 9.8 km, Vevelstad 10.3 km, Brønnøysund 11.2 km from the boundary.
    # A park declared with a box (Abisko) is built over the box and ignores this.
    parser.add_argument(
        "--approach-km", type=float, default=15.0, help="Width of the approach zone around the park (km); not for a park built over a box"
    )
    parser.add_argument("--trailhead-km", type=float, default=2.0, help="Band around the park in which farms and sæters are shown as trailheads (km)")
    parser.add_argument("--names-km", type=float, default=2.0, help="Band around the park covered by the terrain-name layer (valleys, passes, peaks)")
    parser.add_argument(
        "--ut-routes",
        default=None,
        help="Catalogue of UT.no routes to draw, one GPX downloaded per entry; the park's own by default",
    )
    parser.add_argument("--highlight", help="Mark every position of this place name in red, numbered, for checking what the register holds")
    parser.add_argument(
        "--names-spacing-m", type=float, default=1000.0, help="Minimum distance between two labels of the same name; closer copies are dropped"
    )
    parser.add_argument("--simplify-m", type=float, default=8.0, help="Vertex tolerance for map rendering in metres; GPX keeps full detail")
    parser.add_argument("--hut-name-m", type=float, default=50.0, help="How far a cabin may look for its name in a point register (m)")
    parser.add_argument("--force-download", action="store_true", help="Re-download source data instead of using the cache")
    args = parser.parse_args()

    which = PARKS[args.park]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"{which.name.upper()} TRAIL MAP")
    print("=" * 70)

    built = BUILDS[which.country](which, args, repo_root)
    assemble(built, which, args, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

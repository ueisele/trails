"""Build an interactive hiking map for Lomsdal-Visten national park.

Every line on this map is a **chain** out of the routing graph
(:mod:`trails.network.norway`), so a drawn line and a selectable track are the
same object. Each source still draws its own layer in its own colour, and where
several of them describe one valley their lines still lie over each other as
separate objects — the merged graph stays underneath, with every edge naming the
chain it lies on.

Combines seven sources:
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

Produces an HTML map and GPX exports under ``analysis/output/``.

Usage::

    uv run python analysis/scripts/lomsdal_visten.py
    uv run python analysis/scripts/lomsdal_visten.py --approach-km 10
"""

import argparse
import math
import re
from pathlib import Path
from typing import NamedTuple, Protocol

import geopandas as gpd
import pandas as pd
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
    export_to_gpx,
)
from trails.io.sources import geonorge, hoydedata, n50, naturbase, overpass, stedsnavn, traktorvegsti, ut
from trails.network.norway import (
    FERRIES,
    FKB,
    METRIC_CRS,
    N50_PATHS,
    N50_ROADS,
    OSM,
    PLACEHOLDER_IDENTITIES,
    SOURCE_NAMES,
    TURRUTEBASEN,
    UT,
    Params,
    build,
    edge_costs,
    load_sources,
    masks_from,
    protected_table,
    zone_around,
)
from trails.routing import (
    BRIDGE,
    DEFAULT_GAP_M,
    DEFAULT_TOUCHED_M,
    FERRY,
    IDENTITY_SEPARATOR,
    Network,
    NetworkSource,
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

PARK_NAME = "Lomsdal-Visten"

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
    "steepness": "Steepest",
    "high_point": "High point",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

FERRY_POPUP_FIELDS = {
    "typeveg": "Ferry type",
    "length_km": "Crossing (km)",
    "climb": "Ascent / descent",
    "steepness": "Steepest",
    "high_point": "High point",
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
    "steepness": "Steepest",
    "high_point": "High point",
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
    "steepness": "Steepest",
    "high_point": "High point",
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
    "steepness": "Steepest",
    "high_point": "High point",
    "ut_summary": "UT.no states",
    "marking_all": "Marking, all sources",
    "unrecorded": "Unrecorded ground",
}

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
    "steepness": "Steepest",
    "high_point": "High point",
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
    "steepness": "Steepest",
    "high_point": "High point",
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
SOURCE_TERMS = {
    UT: ("CC BY-NC 4.0", "non-commercial", "downloaded"),
    TURRUTEBASEN: ("CC0", "", ""),
    FKB: ("CC BY 4.0", "", "read"),
    N50_PATHS: ("CC BY 4.0", "", "ordered"),
    N50_ROADS: ("CC BY 4.0", "", "ordered"),
    OSM: ("ODbL 1.0", "share-alike", "read"),
    FERRIES: ("CC BY 4.0", "", "ordered"),
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


#: Where each dataset says what it is. Turrutebasen is the odd one: it arrives
#: through the Geonorge order API, whose metadata object names a dataset rather
#: than a service, so it is spelled out here instead of reached for.
SOURCE_METADATA: dict[str, Described] = {
    UT: ut.METADATA,
    FKB: traktorvegsti.METADATA,
    N50_PATHS: n50.METADATA,
    N50_ROADS: n50.METADATA,
    OSM: overpass.METADATA,
    FERRIES: n50.METADATA,
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
#: chain id in the track's extensions mean anything at all.
EXPORT_DESCRIPTION = f"One chain of the {PARK_NAME} routing network"

#: What a planned route's file calls itself, in ``<metadata>`` and on its track.
ROUTE_NAME = f"Planned route in {PARK_NAME}"

#: The line a planned route's file opens its description with. It names the map
#: rather than the route, for the same reason a chain's does: what the legs and
#: the waypoints in its extensions mean is a property of the map that wrote them.
ROUTE_DESCRIPTION = f"A route planned on the {PARK_NAME} map"

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
        tooltip_field: Column shown on hover
        search_field: Column the search box matches against. Not the chain id:
            what a reader types is a name, and a road's identity is a register
            id because names repeat across the county.
        dash: SVG dash pattern, for connections that are not walked
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


def source_credits(versions: dict[str, str | None]) -> dict[str, list[dict[str, str]]]:
    """Say what a file drawn from each dataset has to name.

    Args:
        versions: The version or the date read, per source, from
            :func:`~trails.network.norway.load_sources`

    Returns:
        The sources a chain of each dataset draws on, keyed by the value the
        chain carries in its ``source`` column — which is what a click hands
        back and all the page has to go on
    """
    credits: dict[str, list[dict[str, str]]] = {}
    for name, (licence, note, word) in SOURCE_TERMS.items():
        metadata = SOURCE_METADATA.get(name)
        described = metadata.name if metadata else geonorge.TURRUTEBASEN_METADATA.dataset_name
        version = versions.get(name)
        credits[name] = [
            credit(
                name if described == name else f"{name} ({described})",
                licence,
                note,
                metadata.attribution if metadata else geonorge.TURRUTEBASEN_METADATA.attribution,
                metadata.url if metadata else geonorge.TURRUTEBASEN_METADATA.catalog_url,
                f"{word} {version[:10]}".strip() if version and word else version,
            )
        ]
    return credits


def height_credit() -> list[dict[str, str]]:
    """Say what the ``<ele>`` on every trackpoint came from.

    In every exported file that carries a height and in none that does not: a
    ferry crossing has no ground under it, and naming the height model in a file
    holding no height would be a claim about nothing.

    Returns:
        A single entry for the height model, and **it carries no version**. The
        endpoint publishes none and is not ordered — it answers point by point,
        and the answers reach a file through the graph rather than through a
        dated download — so the field is left empty rather than filled with a
        date that would describe something else. What a reader needs in order to
        compare the ascent figure with another platform's is not a version but
        the rule it was read under, and every track carries that in its own
        ``ascentMethod``.
    """
    return [
        credit(
            hoydedata.METADATA.name,
            hoydedata.METADATA.license,
            "",
            hoydedata.METADATA.attribution,
            hoydedata.METADATA.url,
            None,
        )
    ]


def protected_credit() -> list[dict[str, str]]:
    """Say where a route's protected-area figures came from.

    In every file that states one and in none that does not, exactly as the
    height model is named. The register publishes no version and is not ordered
    — it is queried over an extent, and the answer reaches a file through the
    graph — so the field is left empty rather than filled with a date that would
    describe the download and not the data.

    Returns:
        A single entry for Naturbase
    """
    return [
        credit(
            naturbase.METADATA.name,
            naturbase.METADATA.license,
            "",
            naturbase.METADATA.attribution,
            naturbase.METADATA.url,
            None,
        )
    ]


def ascent_method(params: Params) -> str:
    """Say how the heights and the ascent figure were reached.

    The figure without it asserts nothing: the same route here reads anywhere
    between 965 and 1,214 m depending on the rule, and it is also what explains
    why the number Komoot computes from its own model will not match.

    Args:
        params: What decided the build

    Returns:
        The rule, in the words the popup and the panel use for it
    """
    return f"DTM1, sampled every {params.elevation_step_m:g} m, gains under {params.ascent_threshold_m:g} m ignored"


#: How near a click has to land to be taken as a point on the network. The
#: phase's figure, and it is a judgement rather than a measurement: near enough
#: that a reader aiming at a path gets the path, far enough that a click on open
#: ground stays on open ground. Beyond it the raw point stands and the leg is
#: drawn straight.
SNAP_M = 150.0

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


def plan_settings(params: Params) -> dict[str, object]:
    """Hand the page what it needs to plan a route over the graph it carries.

    Everything here is a fact the build already settled, and the page must not
    settle any of it again: the two rules an answer from the height service is
    read by, the step the whole network was sampled at, and the threshold every
    ascent on this map was read under. A page sampling every 50 m, or counting a
    climb at no threshold at all, would draw a profile that disagrees with every
    other figure on the map without anything looking wrong.

    Args:
        params: What decided the build

    Returns:
        The ``plan`` argument of :func:`~trails.visualization.maps.add_plan_mode`
    """
    return {
        "heightsUrl": hoydedata.SERVICE_URL,
        # Degrees, not the metric grid the build asks in: the page holds
        # longitude and latitude and the service takes either.
        "heightsCrs": hoydedata.WGS84_COORDINATE_SYSTEM,
        "heightsBatch": hoydedata.MAX_POINTS,
        # The build's concurrency and for the build's reason: this is somebody
        # else's endpoint, and one number rather than two.
        "heightsWorkers": hoydedata.DEFAULT_WORKERS,
        "terrainModel": hoydedata.TERRAIN_MODEL,
        "seaTerrain": hoydedata.SEA_TERRAIN,
        "sampleStepM": params.elevation_step_m,
        "ascentThresholdM": params.ascent_threshold_m,
        "snapM": SNAP_M,
        "maxStraightM": MAX_STRAIGHT_M,
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
        },
    }


def export_settings(versions: dict[str, str | None], params: Params) -> dict[str, object]:
    """Hand the page everything it needs to write a GPX file.

    The browser writes that file, so every last thing in it has to be in the
    page — the licences, the versions, the field names and the rule the heights
    were read under. Measured before this phase: ``CC BY 4.0``, ``ODbL`` and
    ``CC BY-NC`` appeared **zero times** in the built page, and so did any
    source version. They existed only in what this script prints to its console,
    and a browser cannot invent them.

    Args:
        versions: The version or the date read, per source
        params: What decided the build

    Returns:
        The ``export`` argument of :func:`~trails.visualization.maps.add_profile_panel`

    Raises:
        KeyError: If a chain figure the file is written from is not in
            :data:`CHAIN_FIGURE_FIELDS`, which would leave the browser writing a
            field it was never given
    """
    keys = {CHAIN_KEY: maps.FIGURE_ID_KEY, **CHAIN_FIGURE_FIELDS}
    return {
        "credits": source_credits(versions),
        "heights": height_credit(),
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
        "description": EXPORT_DESCRIPTION,
        "ascentMethod": ascent_method(params),
        "identitySeparator": IDENTITY_SEPARATOR,
        "filePrefix": PARK_NAME.lower(),
        "sourceLength": SOURCE_LENGTH_FIELD,
        # What a planned route's file is made of, and every name in it comes
        # from the writer's own module rather than being spelled in the page:
        # nothing here can import that module across the browser boundary, so
        # the constants travelling through this dict are the whole of what keeps
        # the two files' vocabularies from drifting apart.
        "route": {
            "name": ROUTE_NAME,
            "description": ROUTE_DESCRIPTION,
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
        },
        # Named wherever a file states how far the route runs inside a protected
        # area, and in no file that does not — the same rule the height model is
        # credited by. That figure came from Naturbase, and a file that reports
        # it without saying so names every party with a claim on it but one.
        "protected": protected_credit(),
    }


def load_park_boundary(cache_dir: str) -> gpd.GeoDataFrame:
    """Load the Lomsdal-Visten national park boundary.

    Args:
        cache_dir: Root cache directory

    Returns:
        Single-row GeoDataFrame in EPSG:4326
    """
    source = naturbase.Source(cache_dir=cache_dir)
    park = source.find_one(PARK_NAME, layer=naturbase.Layer.NATIONAL_PARK)

    area_km2 = park.to_crs(METRIC_CRS).area.iloc[0] / 1e6
    print(f"Park: {park['offisieltNavn'].iloc[0]}")
    print(f"  Area: {area_km2:,.0f} km2")
    print(f"  Municipalities: {park['kommune'].iloc[0]}")
    return park


def only_the_wider_way(chains: gpd.GeoDataFrame) -> pd.Series:
    """Say how long the whole named way is, where that is more than the chain.

    :func:`whole_way_length` answers for every chain that has an identity, and
    for most of them the answer is the chain's own length — a way that does not
    divide is one chain. Showing the same number twice under two labels is
    noise, so those are left empty and the popup drops the row.

    Args:
        chains: Chains carrying ``source``, ``identity`` and ``length_m``

    Returns:
        Kilometres, empty where the chain is the whole way, has no identity, or
        is identified only by a placeholder — a 16 m stub named *Ukjent* would
        otherwise report the total of every other stretch the register also had
        no name for
    """
    whole = whole_way_length(chains, ignore=PLACEHOLDER_IDENTITIES)
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
    inside = chains.geometry.intersection(area.to_crs(METRIC_CRS).union_all()).length
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


def describe(chains: gpd.GeoDataFrame, park: gpd.GeoDataFrame) -> dict[str, gpd.GeoDataFrame]:
    """Give every chain the columns a popup, a search box and a layer need.

    Everything here is read off what the chain already carries. Nothing is
    joined, looked up or clipped: the graph is the only place the geometry and
    the attributes come from, so the map cannot disagree with the router about
    what a line is.

    Args:
        chains: Every chain of the network, in a metric CRS
        park: Park boundary

    Returns:
        One frame per source, keyed by source name. Every source has an entry,
        empty where a small extent left it with no chains at all: a layer with
        nothing in it is drawn as nothing, and a missing key is a crash.
    """
    described = chains.copy()
    described["length_km"] = (described["length_m"] / 1000).round(2)
    described["whole_km"] = only_the_wider_way(described)
    described["in_park"] = share_inside(described, park) >= IN_PARK_SHARE
    described["marking_all"] = describe_marking(described)
    described["unrecorded"] = describe_unrecorded(described)
    # In the metric CRS the graph is built in, and once: taken flat from
    # longitude and latitude the same endpoints give a different bearing, and at
    # this latitude two chains in five would be labelled with a different one of
    # the eight points. Every chain here comes out running eastward — never W,
    # SW or NW — because a chain is canonicalised by coordinate order. That looks
    # like a bug and is not.
    described["bearing_deg"] = endpoint_bearings(described, metric_crs=METRIC_CRS)
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
    # column — a road id is not a thing to write into a <trk><name>.
    described["track_name"] = described["identity"].where(described["source"] != N50_ROADS, described["road_name"])
    described["high_point"] = pd.Series(
        [f"{_metres(value)} m" if pd.notna(value) else "" for value in described["high_m"]],
        index=described.index,
        dtype="string",
    )

    frames = {name: gpd.GeoDataFrame(described[described["source"] == name].copy(), geometry="geometry", crs=described.crs) for name in SOURCE_NAMES}

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

    frames[OSM]["name"] = frames[OSM]["identity"]

    ferries = frames[FERRIES]
    ferries["survey_method"] = translate_joined(ferries["malemetode"], SURVEY_METHOD_LABELS)

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

    simplified = gdf.to_crs(METRIC_CRS)
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


def encode_for_the_page(network: Network, sources: list[NetworkSource], params: Params, order: pd.DataFrame, protected: gpd.GeoDataFrame) -> Payload:
    """Encode the routing graph and its heights into the page's second payload.

    Two representations of the same ground, and they must not be unified. What
    is *drawn* is chains, thinned by ``--simplify-m`` because folium writes
    geometry into the page as JSON coordinate arrays and the network's vertices
    cost 22 MB written that way. What will be *routed over* is the merged graph
    at the resolution its sources recorded it, encoded rather than serialised,
    and never drawn at all. Serving both from one copy loses either the accuracy
    or the render budget.

    Args:
        network: The finished graph, in :data:`METRIC_CRS`
        sources: The datasets it was built from, which say what a route costs
        params: What decided the build
        order: Which of a chain's edges comes first and which way round each of
            them runs. Handed in rather than rebuilt here, because the exported
            tracks are laid out of the same walk and the two writers of a GPX
            file agree only for as long as they compose from one order.
        protected: The areas every edge was measured against, whose outlines go
            into the page as well as their names: a leg drawn straight across
            ground no edge covers has to answer the same question, and only the
            polygons can answer it there.

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
        costs=edge_costs(sources, params),
        areas=protected_table(protected),
    )


def main() -> int:
    """Build the map and GPX exports.

    Returns:
        Process exit code
    """
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-dir", default=str(repo_root / ".cache"), help="Cache directory for downloaded data")
    parser.add_argument("--output-dir", default=str(repo_root / "analysis" / "output"), help="Directory for the map and GPX files")
    # 15 km reaches every realistic trailhead town: Tosbotn 2.6 km, Trofors 5.5 km,
    # Mosjøen 9.8 km, Vevelstad 10.3 km, Brønnøysund 11.2 km from the boundary.
    parser.add_argument("--approach-km", type=float, default=15.0, help="Width of the approach zone around the park (km)")
    parser.add_argument("--trailhead-km", type=float, default=2.0, help="Band around the park in which farms and sæters are shown as trailheads (km)")
    parser.add_argument("--names-km", type=float, default=2.0, help="Band around the park covered by the terrain-name layer (valleys, passes, peaks)")
    parser.add_argument(
        "--ut-routes",
        default=str(repo_root / "analysis" / "routes" / "lomsdal-visten-ut-routes.toml"),
        help="Catalogue of UT.no routes to draw; one GPX is downloaded per entry",
    )
    parser.add_argument("--highlight", help="Mark every position of this place name in red, numbered, for checking what the register holds")
    parser.add_argument(
        "--names-spacing-m", type=float, default=1000.0, help="Minimum distance between two labels of the same name; closer copies are dropped"
    )
    parser.add_argument("--simplify-m", type=float, default=8.0, help="Vertex tolerance for map rendering in metres; GPX keeps full detail")
    parser.add_argument("--hut-name-m", type=float, default=50.0, help="How far an N50 cabin may look for its name in the place-name register (m)")
    parser.add_argument("--force-download", action="store_true", help="Re-download source data instead of using the cache")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("LOMSDAL-VISTEN TRAIL MAP")
    print("=" * 70)

    park = load_park_boundary(args.cache_dir)
    params = Params.from_args(args)
    # Park and approach zone as one polygon. Nothing here is split at the
    # boundary; where a layer is, it is decided per chain further down.
    zone = zone_around(park, params.approach_km)

    loaded = load_sources(params, zone)
    network, _ = build(loaded.sources, masks_from(loaded.sources), zone, params, name=PARK_NAME.lower(), protected=loaded.protected)
    by_source = describe(network.chains, park)

    # The line an export writes, which is a third thing beside the one the map
    # draws and the one a route is found over: every vertex, a point wherever
    # two are more than 5 m apart, and a height on each. Laid out once, off the
    # same edge order the page's payload is encoded from — the browser writes
    # the same file, and the two agree only because they walk the same walk.
    order = chain_order(network.chains, network.edges)
    tracks = chain_tracks(network.chains, network.edges, order)
    print(f"\nExport tracks: {int(tracks.count_coordinates().sum()):,} points over {int(network.chains['length_m'].sum() / 1000):,} km")

    print(f"\nChains from the graph: {len(network.chains):,} drawn, over {len(network.edges):,} routing edges")
    routes = by_source[UT]
    ut_core = routes[routes["category"] == "core"]
    ut_access = routes[routes["category"] == "access"]
    trails = by_source[TURRUTEBASEN]
    roads = by_source[N50_ROADS]
    ferries = by_source[FERRIES]

    layer_of: dict[str, gpd.GeoDataFrame] = {}
    for source, in_park_label, approach_label in (
        (FKB, "FKB paths inside park", "FKB paths in approach zone"),
        (N50_PATHS, "N50 paths inside park", "N50 paths in approach zone"),
        (OSM, "OSM paths inside park", "OSM paths in approach zone"),
    ):
        frame = by_source[source]
        layer_of[f"{source}/park"] = frame[frame["in_park"]]
        layer_of[f"{source}/approach"] = frame[~frame["in_park"]]
        summarize(in_park_label, layer_of[f"{source}/park"])
        summarize(approach_label, layer_of[f"{source}/approach"])

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

    terrain_names = of_kind(stedsnavn.TERRAIN_NAME_TYPES, zone_around(park, args.names_km))
    settlements = of_kind(stedsnavn.SETTLEMENT_NAME_TYPES, zone)
    farms = of_kind(stedsnavn.FARM_NAME_TYPES, zone)
    ssr_huts = of_kind(stedsnavn.HUT_NAME_TYPES, zone)
    ssr_quays = of_kind(stedsnavn.QUAY_NAME_TYPES, zone)
    hut_names = all_names[all_names["kind"].isin(stedsnavn.HUT_NAME_TYPES)]
    print(f"  settlements: {len(settlements)} | farms and holdings: {len(farms)}")
    print(f"  named huts: {len(ssr_huts)} | quays: {len(ssr_quays)}")

    highlighted = gpd.GeoDataFrame()
    if args.highlight:
        highlighted = terrain_names[terrain_names["name"].str.casefold() == args.highlight.casefold()].copy()
        print(f"  highlighting '{args.highlight}': {len(highlighted)} position(s) before thinning")
        for number, (_, row) in enumerate(highlighted.iterrows(), start=1):
            print(f"    {number}: {row.geometry.y:.5f} / {row.geometry.x:.5f}  kind={row['kind']} importance={row['importance']}")
        highlighted["marker_label"] = [f"{i}. {n}" for i, n in enumerate(highlighted["name"], start=1)]

    if len(terrain_names):
        # A name repeated along a feature only reads as a repetition when the
        # copies are far enough apart; closer than this they collide.
        before = len(terrain_names)
        terrain_names = thin_points(terrain_names, args.names_spacing_m, group_by="name", priority="rank")

        # The register ranks importance itself; use it for label size rather
        # than drawing every name at the same weight.
        terrain_names = terrain_names.copy()
        terrain_names["font_size"] = (15.0 - terrain_names["rank"] * 0.5).clip(lower=10.0).round(1)
        terrain_names["color"] = terrain_names["kind"].map(TERRAIN_NAME_COLORS).fillna(TERRAIN_NAME_DEFAULT_COLOR)
        terrain_names["symbol"] = terrain_names["kind"].map(TERRAIN_NAME_SYMBOLS).fillna(TERRAIN_NAME_DEFAULT_SYMBOL)
        repeated = int(terrain_names["name"].duplicated(keep=False).sum())
        print(f"  terrain names (<{args.names_km:g} km): {len(terrain_names)} labels ({before - len(terrain_names)} thinned out)")
        print(f"    {repeated} of them are repeats of an extended feature")
        print(f"    {terrain_names['kind'].value_counts().head(6).to_dict()}")

    print("\nLoading N50 cabins...")
    n50_source = n50.Source(cache_dir=args.cache_dir)
    # N50 names cabins that OSM and the place-name register often miss.
    cabins = gpd.clip(n50_source.load_cabins(codes, force_download=args.force_download), zone)
    if len(cabins) and len(hut_names):
        # N50 has the buildings but names few of them; the register names the
        # huts but is missing some as buildings. Joined, Sæterskaret skogstue —
        # the hut from the park brochure — finally carries its name.
        before = int(cabins["navn"].notna().sum())
        cabins = attach_nearest(cabins, hut_names, {"name": "ssr_name"}, max_distance_m=args.hut_name_m, metric_crs=METRIC_CRS)
        cabins["navn"] = cabins["navn"].fillna(cabins["ssr_name"])
        print(f"  named from SSR: {int(cabins['navn'].notna().sum()) - before} cabin(s) that N50 leaves unnamed")
    print(f"  N50 cabins and wilderness huts: {len(cabins)} ({cabins['navn'].notna().sum() if len(cabins) else 0} named)")
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
        zone_around(park, args.trailhead_km),
    )
    print(f"  Shelters and huts: {len(shelters)}")
    print(f"  Settlements: {len(places)}")
    print(f"  Trailheads (<{args.trailhead_km:g} km from boundary): {len(trailheads)}")
    print(f"  Ferry and express-boat quays: {len(terminals)}")

    print("\nBuilding map...")
    approach_label = f"≤{args.approach_km:g} km"
    # Fit to the full approach zone, not just the park, so trailhead towns are visible.
    fmap = maps.create_map(bounds=bounds_of(zone), base=maps.BaseMap.KARTVERKET_TOPO)

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
        TrailLayer(ut_core, "Routes [UT.no]", "#d81b60", 4.0, UT_POPUP_FIELDS, UT_LINK_FIELDS, "name", "name", None, UT_LINK_HEADING),
        TrailLayer(ut_access, "Access routes [UT.no]", "#f48fb1", 3.0, UT_POPUP_FIELDS, UT_LINK_FIELDS, "name", "name", None, UT_LINK_HEADING),
    ]

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
            link_fields=layer.link_fields,
            link_heading=layer.link_heading,
            tooltip_field=layer.tooltip_field,
            dash_array=layer.dash,
            group_field=CHAIN_KEY,
            search_field=layer.search_field,
            figure_fields=CHAIN_FIGURE_FIELDS,
            source=source_of(layer.label),
        )
        highlightable.append(group)
        legend.append(maps.LegendRow(f"{layer.label} ({len(layer.gdf)})", layer.color, group))

    # Six sources through the same handful of valleys are impossible to follow by
    # eye where they run together, so a click picks one chain out of the bundle.
    maps.add_click_highlight(fmap, highlightable)

    # Everything a name can be typed at, lines and points alike.
    searchable = list(highlightable)
    if len(terminals):
        searchable.append(
            maps.add_points(
                fmap,
                terminals,
                name="Ferry quays [OSM]",
                color="cadetblue",
                icon="ship",
                popup_fields=TERMINAL_POPUP_FIELDS,
                source="OSM",
                point_type="ferry quay",
            )
        )
    if len(cabins):
        searchable.append(
            maps.add_points(
                fmap,
                cabins,
                name="Cabins and wilderness huts [N50]",
                color="darkred",
                icon="house-chimney",
                popup_fields=CABIN_POPUP_FIELDS,
                label_field="navn",
                source="N50",
                point_type="cabin",
            )
        )
    # **One layer per kind of name rather than one for all of them.** They are
    # different questions — where the water runs, where the passes are — and a
    # planner usually wants one of them and not the other five. Split after the
    # thinning above, so each keeps the labels that survived it.
    name_rows: list[maps.LegendRow] = []
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
            heading = f"Name {' '.join(glyphs)} {label} — {', '.join(present)} [SSR]"
            group = maps.add_text_labels(
                fmap,
                part,
                name=heading,
                label_field="name",
                size_field="font_size",
                color_field="color",
                symbol_field="symbol",
                show=False,
            )
            searchable.append(group)
            name_rows.append(maps.LegendRow(f"{heading} ({len(part)})", TERRAIN_NAME_COLORS[present[0]], group))
    if len(ssr_huts):
        # Two of these have no N50 building at all, so the join above cannot reach
        # them; as their own layer none of the register's huts is lost.
        searchable.append(
            maps.add_points(
                fmap,
                ssr_huts,
                name="Named huts [SSR]",
                color="purple",
                icon="house-chimney",
                popup_fields=SSR_POINT_POPUP_FIELDS,
                source="SSR",
                point_type="hut",
            )
        )
    if len(ssr_quays):
        searchable.append(
            maps.add_points(
                fmap,
                ssr_quays,
                name="Quays [SSR]",
                color="blue",
                icon="anchor",
                popup_fields=SSR_POINT_POPUP_FIELDS,
                source="SSR",
                point_type="quay",
            )
        )
    if len(shelters):
        searchable.append(
            maps.add_points(
                fmap,
                shelters,
                name="Huts and shelters [OSM]",
                color="darkblue",
                icon="campground",
                popup_fields=SHELTER_POPUP_FIELDS,
                source="OSM",
                point_type="shelter",
            )
        )
    if len(trailheads):
        searchable.append(
            maps.add_labelled_points(
                fmap,
                trailheads,
                name="Trailheads, farms and sæters [OSM]",
                color="#6d4c41",
                radius=5.5,
                popup_fields=PLACE_POPUP_FIELDS,
                source="OSM",
                point_type="trailhead",
            )
        )
    if len(places):
        # Names appear on hover only, like every other point layer. Drawing 165
        # settlement names permanently competes with the topo backdrop, which
        # already labels them.
        searchable.append(
            maps.add_labelled_points(
                fmap, places, name="Towns and villages [OSM]", popup_fields=PLACE_POPUP_FIELDS, source="OSM", point_type="settlement"
            )
        )
    if len(settlements):
        searchable.append(
            maps.add_labelled_points(
                fmap,
                settlements,
                name="Towns and villages [SSR]",
                color="#263238",
                popup_fields=SSR_POINT_POPUP_FIELDS,
                source="SSR",
                point_type="settlement",
            )
        )
    if len(farms):
        # Over a thousand of them: drawn they would bury the map, so the layer
        # starts off. The search switches it on by itself when a name matches,
        # which is the point of carrying them at all.
        searchable.append(
            maps.add_labelled_points(
                fmap,
                farms,
                name="Farms and holdings [SSR]",
                color="#8d6e63",
                radius=4.5,
                popup_fields=SSR_POINT_POPUP_FIELDS,
                source="SSR",
                point_type="farm",
                show=False,
            )
        )

    # One box over every named thing on the map: a brochure names a place, and
    # this is what turns that name into a position.
    maps.add_search(fmap, searchable)

    # Added last so the boundary outline stays legible on top of every trail layer.
    boundary = maps.add_boundary(fmap, park, name="National park boundary [Naturbase]", weight=3.5)

    # And the graph itself, which nothing draws and nothing yet reads: phase 4
    # takes the profile off it and phase 6 routes over it, and both of those live
    # in Python until it is in the page.
    print("\nEncoding the routing graph for the page...")
    payload = encode_for_the_page(network, loaded.sources, params, order, loaded.protected)
    counted = payload.header
    print(f"  {counted['edges']:,} edges on {counted['nodes']:,} nodes, {counted['vertices']:,} vertices at full source precision")
    print(f"  {counted['samples']:,} height samples, quantised at {counted['coordinateQuantum']:g}° and {counted['elevationQuantum']:g} m")
    print(f"  {payload.raw_mb:.2f} MB encoded, {payload.size_mb:.2f} MB gzipped and base64 in the page")
    print(f"    before compression: {' · '.join(f'{name} {size / 1e6:.2f}' for name, size in payload.sections.items())}")
    maps.add_routing_graph(fmap, payload.header, payload.data)

    if len(highlighted):
        # Diagnostic layer: a ring plus a numbered label at every position the
        # register holds for one name, so it is obvious which ones actually draw.
        maps.add_labelled_points(fmap, highlighted, name=f"HIGHLIGHT: {args.highlight}", color="#e00000", radius=14)
        maps.add_text_labels(
            fmap, highlighted, name=f"HIGHLIGHT labels: {args.highlight}", label_field="marker_label", default_size=20, color="#e00000"
        )

    # It carried two names in one page until the legend and the layer control
    # became one panel — "Park boundary" here and "National park boundary" in the
    # control — which nothing noticed because nothing ever compared them.
    legend.append(maps.LegendRow("National park boundary [Naturbase]", "#0d47a1", boundary))

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
    for label, count, color in (
        ("Quays [SSR]", len(ssr_quays), "#0000cd"),
        ("Ferry quays [OSM]", len(terminals), "#5f9ea0"),
        ("Named huts [SSR]", len(ssr_huts), "#800080"),
        ("Cabins and wilderness huts [N50]", len(cabins), "#8b0000"),
        ("Huts and shelters [OSM]", len(shelters), "#00008b"),
        ("Trailheads, farms and sæters [OSM]", len(trailheads), "#6d4c41"),
        ("Farms and holdings [SSR]", len(farms), "#8d6e63"),
        ("Towns and villages [OSM]", len(places), "#37474f"),
        ("Towns and villages [SSR]", len(settlements), "#263238"),
    ):
        if count:
            legend.append(maps.LegendRow(f"{label} ({count})", color, switched(f"{label} ({count})")))

    maps.add_legend(fmap, f"{PARK_NAME} nasjonalpark", legend)

    # It shares the bottom left with the legend and the scale bar, and puts
    # itself under both: the panel takes the width, the legend keeps its corner
    # above it.
    with_profile = int(network.chains["ascent"].notna().sum())
    print(f"\nProfile panel: {with_profile:,} of {len(network.chains):,} chains carry one, {len(network.chains) - with_profile} say they have none")
    # And the panel writes the selected chain out. Everything the file says
    # about itself travels with it: the browser is what produces that file, and
    # a licence, a version or a field name it was not given is one it would have
    # to invent.
    maps.add_profile_panel(fmap, highlightable, export=export_settings(loaded.versions, params))

    # And a route can now be clicked together over the graph, leg by leg, with
    # its profile drawn in the same panel. After the panel, whose walk it lays
    # its route out with, and after the graph it routes over.
    # And the named points every one of these layers draws, so a waypoint set
    # beside a hut comes back called after the hut. The line layers go in too
    # and carry nothing: only a layer given a point_type has a table, and a
    # place name drawn as text asserts no single position to be named after.
    maps.add_plan_mode(fmap, plan_settings(params), searchable)

    map_path = output_dir / "lomsdal-visten.html"
    fmap.save(str(map_path))
    print(f"  Map: {map_path} ({map_path.stat().st_size / 1e6:.1f} MB)")

    # Built from the chains, not from the raw sources, so one geometry serves
    # the map, the exports and the router. At full source precision: the
    # simplified copy above is the drawn one and goes nowhere near this.
    print("\nExporting GPX...")
    exports = [
        ("lomsdal-visten-turrutebasen.gpx", TURRUTEBASEN, trails, "trail_name", ["maintenance_responsible", "difficulty", "marking", "length_km"]),
        ("lomsdal-visten-fkb.gpx", FKB, by_source[FKB], "typeveg", ["typeveg", "length_km"]),
        ("lomsdal-visten-n50.gpx", N50_PATHS, by_source[N50_PATHS], "typeveg", ["typeveg", "rutemerking", "length_km"]),
        ("lomsdal-visten-osm.gpx", OSM, by_source[OSM], "name", ["highway", "surface", "sac_scale", "length_km"]),
        # One file with all catalogued routes, named, instead of 35 downloads.
        ("lomsdal-visten-ut.gpx", UT, routes, "name", ["category_label", "length_km", "ut_url"]),
        # The chain's own length, not the whole road's: a track in this file
        # *is* one chain, and a figure about other tracks would not describe it.
        ("lomsdal-visten-roads.gpx", N50_ROADS, roads, "road_name", ["road_category", "length_km"]),
    ]
    credits_of = source_credits(loaded.versions)
    heights = height_credit()
    for filename, source, chains, name_field, desc_fields in exports:
        if not len(chains):
            continue
        path, stats = export_to_gpx(
            # The dense, height-carrying line rather than the chain's own: the
            # heights were sampled along the edges and not at the vertices, and
            # the geometry a file is written from is the one the two were laid
            # against each other on.
            chains.assign(track=tracks),
            output_dir / filename,
            name_field=name_field,
            desc_fields=desc_fields,
            title=f"{PARK_NAME}: {source}",
            description=f"Every {source} chain of the {PARK_NAME} routing network",
            # The height model only where the file actually carries a height,
            # which is the rule the page follows chain by chain. A file of
            # crossings would name a source it never read a value from.
            sources=credits_of[source] + (heights if bool(chains["ascent"].notna().any()) else []),
            extension_fields=DEFAULT_EXTENSION_FIELDS,
            ascent_method=ascent_method(params),
            track_field="track",
        )
        print(f"  {path.name}: {stats['total_trails']} tracks, {stats['total_points']:,} points, {stats['file_size_mb']:.2f} MB")

    print("\n" + "=" * 70)
    # What every exported file now carries in its own <metadata>, printed here
    # as well because a build's own log is where a discrepancy gets noticed.
    for entries in credits_of.values():
        for entry in entries:
            print(f"Source: {entry['name']} — {entry['licence']}{', ' + entry['note'] if entry['note'] else ''} — {entry['version'] or 'no version'}")
    print(f"Heights: {heights[0]['name']} — {heights[0]['licence']} — {ascent_method(params)}")
    entry = protected_credit()[0]
    # It is in a route's file and in none of the six above: a route states how
    # far it runs inside each protected area and a chain states nothing of the
    # kind, so the register has a claim on one and not the other.
    print(f"Protected: {entry['name']} — {entry['licence']} — in a planned route's file, in no chain's, and in the boundary drawn")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

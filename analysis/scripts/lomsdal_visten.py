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
import re
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
import pandas as pd
from trails.io.export.gpx import export_to_gpx
from trails.io.sources import n50, naturbase, overpass, stedsnavn, ut
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
    load_sources,
    masks_from,
    zone_around,
)
from trails.routing import parts_of, translate_joined, whole_way_length
from trails.utils.geo import attach_nearest, thin_points
from trails.visualization import maps

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
    "myr": "#2e7d32",  # marsh, dark green
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
    "myr": "≋",  # wet ground hatching
    "seter": "⌂",  # a hut
}

#: Used for any type without a glyph above.
TERRAIN_NAME_DEFAULT_SYMBOL = "·"

#: Groups of types sharing one colour, for the legend.
TERRAIN_NAME_LEGEND = (
    ("running water", {"elv", "bekk", "foss"}),
    ("lakes and ice", {"vann", "tjern", "isbre"}),
    ("valleys and passes", {"dal", "skar"}),
    ("mountains and slopes", {"fjell", "fjellområde", "li"}),
    ("marsh", {"myr"}),
    ("summer farms", {"seter"}),
)

FKB_POPUP_FIELDS = {
    "typeveg": "Road type",
    "length_km": "Length (km)",
}

FERRY_POPUP_FIELDS = {
    "typeveg": "Ferry type",
    "length_km": "Crossing (km)",
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
    "survey_method": "Captured",
    "surveyed": "Captured on",
}

N50_POPUP_FIELDS = {
    "typeveg": "Road type",
    "rutemerking": "Waymarked",
    "vedlikeholdsansvarlig": "Maintained by",
    "medium": "Medium",
    "length_km": "Length (km)",
    "survey_method": "Captured",
    "surveyed": "Captured on",
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

#: How a catalogue category reads in a popup.
UT_CATEGORY_LABELS = {
    "core": "Route in or through the park",
    "access": "Access or connection",
}

UT_POPUP_FIELDS = {
    "name": "Route",
    "category_label": "Kind",
    "length_km": "Track length (km)",
    "ut_summary": "UT.no states",
}

#: Clickable links in the UT.no popup. The route page and the park's own
#: description carry everything the geometry cannot: season, difficulty, the
#: state of the river crossings.
UT_LINK_FIELDS = {
    "ut_url": "→ Route on ut.no",
    "guide_url_no": "→ Beskrivelse på lomsdalvisten.no",
    "guide_url_en": "→ Description on lomsdalvisten.no",
    "gpx_url": "→ Download GPX",
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
    "survey_method": "Captured",
    "surveyed": "Captured on",
    # 80 % of this register's geometry here is "Rett i kartet" — entered by the
    # people who maintain the route — and only 1 % each from FKB and N50. It is
    # the one line source in this map that is not a Kartverket derivative.
    "origin": "Geometry from",
}

OSM_POPUP_FIELDS = {
    "name": "Name",
    "highway": "Type",
    "surface": "Surface",
    "sac_scale": "SAC scale",
    "trail_visibility": "Visibility",
    "length_km": "Length (km)",
    "whole_km": "Way in total (km)",
    # Plural, and it is not pedantry: 64 % of these chains span more than one
    # OSM way — median 2, worst 33 — so a single id would be wrong for most of
    # them. The value is joined like every other multi-valued field.
    "osm_id": "OSM IDs",
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

#: Trailing bracket of a layer label, which by convention holds its dataset.
SOURCE_IN_LABEL = re.compile(r"\[([^\]]+)\]\s*$")


class TrailLayer(NamedTuple):
    """One line layer of the map, in draw order.

    Attributes:
        gdf: Chains to draw
        label: Layer name in the control and legend, ending in its source
        color: Line colour
        weight: Line width in pixels
        popup_fields: Mapping of column name to popup label
        link_fields: Mapping of a column holding a URL to its link text
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
    network, _ = build(loaded.sources, masks_from(loaded.sources), zone, params, name=PARK_NAME.lower())
    by_source = describe(network.chains, park)

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
        TrailLayer(ut_core, "Routes [UT.no]", "#d81b60", 4.0, UT_POPUP_FIELDS, UT_LINK_FIELDS, "name", "name"),
        TrailLayer(ut_access, "Access routes [UT.no]", "#f48fb1", 3.0, UT_POPUP_FIELDS, UT_LINK_FIELDS, "name", "name"),
    ]

    legend: dict[str, str] = {}
    highlightable = []
    for layer in layers:
        if not len(layer.gdf):
            continue
        highlightable.append(
            maps.add_trails(
                fmap,
                simplify_for_display(layer.gdf, args.simplify_m),
                name=layer.label,
                color=layer.color,
                weight=layer.weight,
                popup_fields=layer.popup_fields,
                link_fields=layer.link_fields,
                tooltip_field=layer.tooltip_field,
                dash_array=layer.dash,
                group_field=CHAIN_KEY,
                search_field=layer.search_field,
                source=source_of(layer.label),
            )
        )
        legend[f"{layer.label} ({len(layer.gdf)})"] = layer.color

    # Six sources through the same handful of valleys are impossible to follow by
    # eye where they run together, so a click picks one chain out of the bundle.
    maps.add_click_highlight(fmap, highlightable)

    # Everything a name can be typed at, lines and points alike.
    searchable = list(highlightable)
    if len(terminals):
        searchable.append(
            maps.add_points(
                fmap, terminals, name="Ferry quays [OSM]", color="cadetblue", icon="ship", popup_fields=TERMINAL_POPUP_FIELDS, source="OSM"
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
            )
        )
    if len(terrain_names):
        searchable.append(
            maps.add_text_labels(
                fmap,
                terrain_names,
                name="Terrain names [SSR]",
                label_field="name",
                size_field="font_size",
                color_field="color",
                symbol_field="symbol",
                show=False,
            )
        )
    if len(ssr_huts):
        # Two of these have no N50 building at all, so the join above cannot reach
        # them; as their own layer none of the register's huts is lost.
        searchable.append(
            maps.add_points(
                fmap, ssr_huts, name="Named huts [SSR]", color="purple", icon="house-chimney", popup_fields=SSR_POINT_POPUP_FIELDS, source="SSR"
            )
        )
    if len(ssr_quays):
        searchable.append(
            maps.add_points(fmap, ssr_quays, name="Quays [SSR]", color="blue", icon="anchor", popup_fields=SSR_POINT_POPUP_FIELDS, source="SSR")
        )
    if len(shelters):
        searchable.append(
            maps.add_points(
                fmap, shelters, name="Huts and shelters [OSM]", color="darkblue", icon="campground", popup_fields=SHELTER_POPUP_FIELDS, source="OSM"
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
            )
        )
    if len(places):
        # Names appear on hover only, like every other point layer. Drawing 165
        # settlement names permanently competes with the topo backdrop, which
        # already labels them.
        searchable.append(maps.add_labelled_points(fmap, places, name="Towns and villages [OSM]", popup_fields=PLACE_POPUP_FIELDS, source="OSM"))
    if len(settlements):
        searchable.append(
            maps.add_labelled_points(
                fmap, settlements, name="Towns and villages [SSR]", color="#263238", popup_fields=SSR_POINT_POPUP_FIELDS, source="SSR"
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
                show=False,
            )
        )

    # One box over every named thing on the map: a brochure names a place, and
    # this is what turns that name into a position.
    maps.add_search(fmap, searchable)

    # Added last so the boundary outline stays legible on top of every trail layer.
    maps.add_boundary(fmap, park, name="National park boundary [Naturbase]", weight=3.5)

    if len(highlighted):
        # Diagnostic layer: a ring plus a numbered label at every position the
        # register holds for one name, so it is obvious which ones actually draw.
        maps.add_labelled_points(fmap, highlighted, name=f"HIGHLIGHT: {args.highlight}", color="#e00000", radius=14)
        maps.add_text_labels(
            fmap, highlighted, name=f"HIGHLIGHT labels: {args.highlight}", label_field="marker_label", default_size=20, color="#e00000"
        )

    legend["Park boundary [Naturbase]"] = "#0d47a1"

    # Name colours are only decodable with a key, so list the types actually drawn.
    if len(terrain_names):
        drawn_kinds = set(terrain_names["kind"])
        for label, kinds in TERRAIN_NAME_LEGEND:
            present = sorted(kinds & drawn_kinds)
            if present:
                # Types can share a colour but differ in glyph (fjell vs li), so
                # show every glyph the group actually draws.
                glyphs = dict.fromkeys(TERRAIN_NAME_SYMBOLS.get(kind, TERRAIN_NAME_DEFAULT_SYMBOL) for kind in present)
                legend[f"Name {' '.join(glyphs)} {label} — {', '.join(present)} [SSR]"] = TERRAIN_NAME_COLORS[present[0]]

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
            legend[f"{label} ({count})"] = color

    maps.add_legend(fmap, f"{PARK_NAME} nasjonalpark", legend)
    maps.finalize(fmap)

    map_path = output_dir / "lomsdal-visten.html"
    fmap.save(str(map_path))
    print(f"  Map: {map_path} ({map_path.stat().st_size / 1e6:.1f} MB)")

    # Built from the chains, not from the raw sources, so one geometry serves
    # the map, the exports and the router. At full source precision: the
    # simplified copy above is the drawn one and goes nowhere near this.
    print("\nExporting GPX...")
    exports = [
        ("lomsdal-visten-turrutebasen.gpx", trails, "trail_name", ["maintenance_responsible", "difficulty", "marking", "length_km"]),
        ("lomsdal-visten-fkb.gpx", by_source[FKB], "typeveg", ["typeveg", "length_km"]),
        ("lomsdal-visten-n50.gpx", by_source[N50_PATHS], "typeveg", ["typeveg", "rutemerking", "length_km"]),
        ("lomsdal-visten-osm.gpx", by_source[OSM], "name", ["highway", "surface", "sac_scale", "length_km"]),
        # One file with all catalogued routes, named, instead of 35 downloads.
        ("lomsdal-visten-ut.gpx", routes, "name", ["category_label", "length_km", "ut_url"]),
        # The chain's own length, not the whole road's: a track in this file
        # *is* one chain, and a figure about other tracks would not describe it.
        ("lomsdal-visten-roads.gpx", roads, "road_name", ["road_category", "length_km"]),
    ]
    for filename, chains, name_field, desc_fields in exports:
        if not len(chains):
            continue
        path, stats = export_to_gpx(chains, output_dir / filename, name_field=name_field, desc_fields=desc_fields)
        print(f"  {path.name}: {stats['total_trails']} tracks, {stats['total_points']:,} points, {stats['file_size_mb']:.2f} MB")

    print("\n" + "=" * 70)
    print(f"Sources: Turrutebasen {loaded.turrutebasen_version} (CC0) | N50 Kartdata (CC BY 4.0) | Traktorveg og Skogsbilveg (CC BY 4.0)")
    print("         all Kartverket | Naturbase (NLOD, Miljødirektoratet) | OpenStreetMap (ODbL)")
    print(f"         {ut.METADATA.attribution} ({ut.METADATA.license}) — non-commercial, unlike the rest")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

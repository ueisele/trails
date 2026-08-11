"""Build an interactive hiking map for Lomsdal-Visten national park.

Combines four sources:
  * Turrutebasen (Kartverket/Geonorge) - official marked routes, with DNT-maintained
    segments highlighted separately
  * Traktorveg og Skogsbilveg WFS (Kartverket) - the detailed FKB path network the
    topographic base map draws at high zoom; by far the richest source here
  * N50 Kartdata (Kartverket) - the generalised path network the base map draws at
    lower zoom, kept as a cross-check
  * OpenStreetMap via Overpass - community-mapped paths, tracks and shelters
  * Naturbase (Miljødirektoratet) - the national park boundary used for clipping

Produces an HTML map and GPX exports under ``analysis/output/``.

Usage::

    uv run python analysis/scripts/lomsdal_visten.py
    uv run python analysis/scripts/lomsdal_visten.py --approach-km 10 --no-osm
"""

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from trails.io.export.gpx import export_to_gpx
from trails.io.sources import kommuneinfo, n50, naturbase, overpass, stedsnavn, traktorvegsti
from trails.io.sources.geonorge import Source as GeonorgeSource
from trails.io.sources.language import Language
from trails.utils.geo import merge_lines, thin_points
from trails.visualization import maps

PARK_NAME = "Lomsdal-Visten"

#: Metric CRS for Norway, used for buffering and length calculations.
METRIC_CRS = "EPSG:25833"

#: Substrings identifying DNT (Den Norske Turistforening) as maintainer.
DNT_PATTERN = "DNT|Turistforening"

#: Place types that act as trailheads around this park, as opposed to settlements.
TRAILHEAD_PLACE_TYPES = ("farm", "isolated_dwelling")

#: County prefix searched when resolving which municipalities the area covers.
FYLKE_PREFIXES = ("18",)

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
    "elv": "\u2248",  # wavy lines, running water
    "bekk": "\u2248",
    "foss": "\u2248",
    "vann": "\u25cf",  # a filled body of standing water
    "tjern": "\u25cf",
    "isbre": "\u25c7",  # open diamond, ice
    "dal": "\u2228",  # V, the classic valley cross-section
    "skar": "\u2228",
    "fjell": "\u25b2",  # a peak
    "fjellomr\u00e5de": "\u25b2",
    "li": "\u25e2",  # a slope
    "myr": "\u224b",  # wet ground hatching
    "seter": "\u2302",  # a hut
}

#: Used for any type without a glyph above.
TERRAIN_NAME_DEFAULT_SYMBOL = "\u00b7"

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

N50_POPUP_FIELDS = {
    "typeveg": "Road type",
    "rutemerking": "Waymarked",
    "vedlikeholdsansvarlig": "Maintained by",
    "medium": "Medium",
    "length_km": "Length (km)",
}

TRAIL_POPUP_FIELDS = {
    "trail_name": "Route",
    "trail_number": "Number",
    "difficulty": "Difficulty",
    "marking": "Marking",
    "trail_follows": "Follows",
    "maintenance_responsible": "Maintained by",
    "length_km": "Length (km)",
}

OSM_POPUP_FIELDS = {
    "name": "Name",
    "highway": "Type",
    "surface": "Surface",
    "sac_scale": "SAC scale",
    "trail_visibility": "Visibility",
    "osm_id": "OSM ID",
}

SHELTER_POPUP_FIELDS = {
    "name": "Name",
    "kind": "Type",
    "operator": "Operator",
    "osm_id": "OSM ID",
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


def aggregate_trail_info(info: pd.DataFrame) -> pd.DataFrame:
    """Collapse the trail info table to one row per geometry segment.

    A segment can belong to several named routes, so the info table holds
    multiple rows per ``hiking_trail_fk``. Names are concatenated; the remaining
    attributes take the first populated value.

    Args:
        info: Hiking trail info table

    Returns:
        DataFrame indexed by segment id with one row per segment
    """

    def join_names(values: pd.Series) -> str | None:
        names = sorted({str(v) for v in values.dropna().unique()})
        return " / ".join(names) if names else None

    def first_value(values: pd.Series) -> object:
        populated = values.dropna()
        return populated.iloc[0] if len(populated) else None

    aggregations: dict[str, Callable[[pd.Series], Any]] = {"trail_name": join_names}
    for column in ("trail_number", "difficulty", "trail_significance", "maintenance_responsible", "season"):
        if column in info.columns:
            aggregations[column] = first_value

    grouped = info.groupby("hiking_trail_fk").agg(aggregations)

    # Flag DNT across all rows of a segment, not just the first one.
    is_dnt = info["maintenance_responsible"].str.contains(DNT_PATTERN, case=False, na=False)
    grouped["is_dnt"] = is_dnt.groupby(info["hiking_trail_fk"]).any()

    return grouped


def load_official_trails(cache_dir: str, force_download: bool = False) -> tuple[gpd.GeoDataFrame, str]:
    """Load Turrutebasen hiking trails joined with their attributes.

    Args:
        cache_dir: Root cache directory
        force_download: Re-download the source dataset

    Returns:
        Tuple of (trails in EPSG:4326 with attributes attached, dataset version)
    """
    source = GeonorgeSource(cache_dir=cache_dir)
    data = source.load_turrutebasen(target_crs="EPSG:4326", language=Language.EN, force_download=force_download)

    trails = data.spatial_layers["hiking_trail_centerline"]
    info = data.attribute_tables["hiking_trail_info_table"]

    merged = trails.merge(aggregate_trail_info(info), left_on="local_id", right_index=True, how="left")
    merged["is_dnt"] = merged["is_dnt"].fillna(False).astype(bool)

    print(f"Turrutebasen version {data.version}: {len(merged):,} hiking segments nationwide")
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=trails.crs), data.version


def clip_to(gdf: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clip features to a boundary and recompute their length.

    Args:
        gdf: Features to clip, in EPSG:4326
        boundary: Clipping polygon(s), in EPSG:4326

    Returns:
        Clipped GeoDataFrame with a ``length_km`` column
    """
    clipped = gpd.clip(gdf, boundary).copy()
    if len(clipped):
        clipped["length_km"] = (clipped.to_crs(METRIC_CRS).length / 1000).round(2)
    else:
        clipped["length_km"] = pd.Series(dtype=float)
    return clipped


def buffer_area(park: gpd.GeoDataFrame, distance_km: float) -> gpd.GeoDataFrame:
    """Grow the park outline by a distance, keeping the interior.

    Args:
        park: Park boundary in EPSG:4326
        distance_km: Buffer distance in kilometers

    Returns:
        GeoDataFrame in EPSG:4326 holding the buffered area
    """
    metric = park.to_crs(METRIC_CRS)
    return gpd.GeoDataFrame(geometry=metric.buffer(distance_km * 1000), crs=METRIC_CRS).to_crs("EPSG:4326")


def build_approach_zone(park: gpd.GeoDataFrame, distance_km: float) -> gpd.GeoDataFrame:
    """Build a ring around the park covering approach routes.

    The park interior is cut out so approach features can be styled separately
    from what lies inside the boundary.

    Args:
        park: Park boundary in EPSG:4326
        distance_km: Width of the ring in kilometers

    Returns:
        GeoDataFrame in EPSG:4326 holding the ring geometry
    """
    metric = park.to_crs(METRIC_CRS)
    ring = metric.buffer(distance_km * 1000).difference(metric.union_all())
    return gpd.GeoDataFrame(geometry=ring, crs=METRIC_CRS).to_crs("EPSG:4326")


def simplify_for_display(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    """Thin out vertices for map rendering.

    N50 and OSM geometries carry far more detail than a browser map needs; at
    these zoom levels a few metres of tolerance is invisible but removes most of
    the coordinates. GPX exports keep the full geometry.

    Args:
        gdf: Features to simplify, in EPSG:4326
        tolerance_m: Douglas-Peucker tolerance in metres

    Returns:
        Copy of the input with simplified geometries
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
    """Print a one-line summary of a trail layer.

    Args:
        name: Label for the layer
        gdf: Clipped trail features carrying a ``length_km`` column
    """
    total_km = gdf["length_km"].sum() if len(gdf) else 0.0
    print(f"  {name}: {len(gdf):,} segments, {total_km:,.1f} km")


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
    parser.add_argument("--no-names", action="store_true", help="Skip the place-name layer")
    parser.add_argument("--highlight", help="Mark every position of this place name in red, numbered, for checking what the register holds")
    parser.add_argument(
        "--names-spacing-m", type=float, default=1000.0, help="Minimum distance between two labels of the same name; closer copies are dropped"
    )
    parser.add_argument("--simplify-m", type=float, default=8.0, help="Vertex tolerance for map rendering in metres; GPX keeps full detail")
    parser.add_argument("--no-osm", action="store_true", help="Skip OpenStreetMap layers")
    # N50 is not a subset of FKB: it is maintained separately and holds stretches
    # FKB lacks (~51 km within 5 km of this park). It also covers the whole approach
    # zone, where FKB is limited to --fkb-km. Worth its ~3 MB.
    parser.add_argument("--no-n50", action="store_true", help="Skip N50 Kartdata paths, the generalised base map network")
    parser.add_argument("--no-fkb", action="store_true", help="Skip the detailed FKB path network")
    parser.add_argument("--fkb-km", type=float, default=5.0, help="How far beyond the park to load detailed FKB paths (km); they are dense")
    parser.add_argument("--force-download", action="store_true", help="Re-download source data instead of using the cache")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("LOMSDAL-VISTEN TRAIL MAP")
    print("=" * 70)

    park = load_park_boundary(args.cache_dir)
    approach = build_approach_zone(park, args.approach_km)

    print("\nLoading Turrutebasen...")
    trails, version = load_official_trails(args.cache_dir, force_download=args.force_download)

    print("\nClipping to park...")
    in_park = clip_to(trails, park)
    in_approach = clip_to(trails, approach)
    dnt_in_park = in_park[in_park["is_dnt"]]
    summarize("Inside park", in_park)
    summarize("  of which DNT-maintained", dnt_in_park)
    summarize(f"Approach zone (<{args.approach_km:g} km)", in_approach)

    dnt_in_approach = in_approach[in_approach["is_dnt"]]
    summarize("  of which DNT-maintained", dnt_in_approach)

    # Everything within reach of the park, used for features that make no sense
    # to split at the boundary, such as ferries and quays.
    approach_and_park = gpd.GeoDataFrame(geometry=[approach.union_all().union(park.union_all())], crs="EPSG:4326")

    # Every per-municipality Geonorge dataset needs this, so resolve it once.
    codes = kommuneinfo.Source(cache_dir=args.cache_dir).intersecting(approach, fylke=FYLKE_PREFIXES)

    terrain_names = gpd.GeoDataFrame()
    highlighted = gpd.GeoDataFrame()
    if not args.no_names:
        print("\nLoading place names (SSR)...")
        names_source = stedsnavn.Source(cache_dir=args.cache_dir)
        terrain_names = gpd.clip(names_source.load_places(codes, force_download=args.force_download), buffer_area(park, args.names_km))

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

    ferries = gpd.GeoDataFrame()
    cabins = gpd.GeoDataFrame()
    fkb_in_park = gpd.GeoDataFrame()
    fkb_in_approach = gpd.GeoDataFrame()
    if not args.no_fkb:
        print("\nLoading detailed FKB paths (what the base map draws at high zoom)...")
        fkb_zone = buffer_area(park, args.fkb_km)
        fkb_paths = traktorvegsti.Source(cache_dir=args.cache_dir).fetch_paths(bounds_of(fkb_zone), force_download=args.force_download)

        # The service delivers paths in short pieces; merging keeps the geometry
        # but cuts the feature count roughly in a third.
        fkb_in_park = clip_to(merge_lines(gpd.clip(fkb_paths, park), group_by="typeveg"), park)
        fkb_ring = build_approach_zone(park, args.fkb_km)
        fkb_in_approach = clip_to(merge_lines(gpd.clip(fkb_paths, fkb_ring), group_by="typeveg"), fkb_ring)
        summarize("FKB paths inside park", fkb_in_park)
        summarize(f"FKB paths within {args.fkb_km:g} km", fkb_in_approach)

    n50_in_park = gpd.GeoDataFrame()
    n50_in_approach = gpd.GeoDataFrame()
    if not args.no_n50:
        print("\nLoading N50 Kartdata (topographic base map paths)...")
        n50_paths = n50.Source(cache_dir=args.cache_dir).load_paths(codes, force_download=args.force_download)
        n50_in_park = clip_to(n50_paths, park)
        n50_in_approach = clip_to(n50_paths, approach)
        summarize("N50 paths inside park", n50_in_park)
        summarize("N50 paths in approach zone", n50_in_approach)

        # rutemerking says whether a path is waymarked; the unmarked ones are
        # exactly what Turrutebasen leaves out.
        if len(n50_in_park):
            marked = (n50_in_park["rutemerking"] == "JA").sum()
            print(f"    waymarked: {marked}, unmarked: {len(n50_in_park) - marked}")

        # On this coast a ferry is often the only way to reach a trailhead.
        n50_source = n50.Source(cache_dir=args.cache_dir)
        ferries = clip_to(n50_source.load_ferries(codes, force_download=args.force_download), approach_and_park)
        summarize("Ferry crossings", ferries)
        if len(ferries):
            print(f"    {ferries['typeveg'].value_counts().to_dict()}")

        # N50 names cabins that OSM and the place-name register often miss.
        cabins = gpd.clip(n50_source.load_cabins(codes, force_download=args.force_download), approach_and_park)
        print(f"  N50 cabins and wilderness huts: {len(cabins)} ({cabins['navn'].notna().sum() if len(cabins) else 0} named)")
        if len(cabins):
            print(f"    {cabins['kind'].value_counts().to_dict()}")

    osm_in_park = gpd.GeoDataFrame()
    osm_in_approach = gpd.GeoDataFrame()
    shelters = gpd.GeoDataFrame()
    places = gpd.GeoDataFrame()
    trailheads = gpd.GeoDataFrame()
    terminals = gpd.GeoDataFrame()
    if not args.no_osm:
        print("\nLoading OpenStreetMap...")
        osm_source = overpass.Source(cache_dir=args.cache_dir)
        search_bounds = bounds_of(approach)
        osm_paths = osm_source.fetch_paths(search_bounds, force_download=args.force_download)
        osm_in_park = clip_to(osm_paths, park)
        osm_in_approach = clip_to(osm_paths, approach)

        # Shelters and settlements matter inside the park and along the way in.
        shelters = gpd.clip(osm_source.fetch_shelters(search_bounds, force_download=args.force_download), approach_and_park)
        places = gpd.clip(osm_source.fetch_places(search_bounds, force_download=args.force_download), approach_and_park)
        terminals = gpd.clip(osm_source.fetch_ferry_terminals(search_bounds, force_download=args.force_download), approach_and_park)

        # Farms and sæters are the actual starting points here (Bønnåa, Strompdalen,
        # Stavassgården), but the region has over a thousand of them, so they are
        # limited to a narrow band around the boundary.
        trailheads = gpd.clip(
            osm_source.fetch_places(search_bounds, place_types=TRAILHEAD_PLACE_TYPES, force_download=args.force_download),
            buffer_area(park, args.trailhead_km),
        )
        summarize("OSM paths inside park", osm_in_park)
        summarize("OSM paths in approach zone", osm_in_approach)
        print(f"  Shelters and huts: {len(shelters)}")
        print(f"  Settlements: {len(places)}")
        print(f"  Trailheads (<{args.trailhead_km:g} km from boundary): {len(trailheads)}")
        print(f"  Ferry and express-boat quays: {len(terminals)}")

    print("\nBuilding map...")
    approach_label = f"\u2264{args.approach_km:g} km"
    # Fit to the full approach zone, not just the park, so trailhead towns are visible.
    fmap = maps.create_map(bounds=bounds_of(approach), base=maps.BaseMap.KARTVERKET_TOPO)

    # Layers are added back-to-front so official routes draw on top of OSM,
    # and only non-empty ones appear in the control and legend. Everything is on
    # by default except the terrain names, which the topo backdrop already draws.
    fkb_label = f"\u2264{args.fkb_km:g} km"
    # Every label ends with its dataset in brackets, so the legend and the layer
    # control always say where a line or a name came from.
    layers = [
        # gdf, label, colour, weight, popup fields, dash pattern, visible
        (ferries, "Ferry crossings [N50]", "#0277bd", 2.5, FERRY_POPUP_FIELDS, "10,7", True),
        (osm_in_approach, f"Paths, approach {approach_label} [OSM]", "#ce93d8", 1.5, OSM_POPUP_FIELDS, None, True),
        (n50_in_approach, f"Paths, approach {approach_label} [N50]", "#80cbc4", 1.5, N50_POPUP_FIELDS, None, True),
        (fkb_in_approach, f"Paths, approach {fkb_label} [FKB]", "#5c6bc0", 1.8, FKB_POPUP_FIELDS, None, True),
        (
            in_approach[~in_approach["is_dnt"]],
            f"Marked routes, approach {approach_label} [Turrutebasen]",
            "#f9a825",
            2.5,
            TRAIL_POPUP_FIELDS,
            None,
            True,
        ),
        (dnt_in_approach, f"DNT routes, approach {approach_label} [Turrutebasen]", "#ef6c00", 3.5, TRAIL_POPUP_FIELDS, None, True),
        (osm_in_park, "Paths in park [OSM]", "#8e24aa", 2.5, OSM_POPUP_FIELDS, None, True),
        (n50_in_park, "Paths in park [N50]", "#00796b", 2.5, N50_POPUP_FIELDS, None, True),
        (fkb_in_park, "Paths in park [FKB]", "#283593", 3.0, FKB_POPUP_FIELDS, None, True),
        (in_park[~in_park["is_dnt"]], "Marked routes in park [Turrutebasen]", "#1b5e20", 3.5, TRAIL_POPUP_FIELDS, None, True),
        (dnt_in_park, "DNT routes in park [Turrutebasen]", "#c62828", 4.0, TRAIL_POPUP_FIELDS, None, True),
    ]

    legend: dict[str, str] = {}
    for gdf, label, color, weight, popup_fields, dash, show in layers:
        if not len(gdf):
            continue
        drawn = simplify_for_display(gdf, args.simplify_m)
        maps.add_trails(fmap, drawn, name=label, color=color, weight=weight, popup_fields=popup_fields, dash_array=dash, show=show)
        legend[f"{label} ({len(gdf)})"] = color

    if len(terminals):
        maps.add_points(fmap, terminals, name="Ferry quays [OSM]", color="cadetblue", icon="ship", popup_fields=TERMINAL_POPUP_FIELDS)
    if len(cabins):
        maps.add_points(
            fmap,
            cabins,
            name="Cabins and wilderness huts [N50]",
            color="darkred",
            icon="house-chimney",
            popup_fields=CABIN_POPUP_FIELDS,
            label_field="navn",
        )
    if len(terrain_names):
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
    if len(shelters):
        maps.add_points(fmap, shelters, name="Huts and shelters [OSM]", color="darkblue", icon="campground", popup_fields=SHELTER_POPUP_FIELDS)
    if len(trailheads):
        maps.add_labelled_points(fmap, trailheads, name="Trailheads, farms and sæters [OSM]", color="#6d4c41", radius=3.5)
    if len(places):
        # Names appear on hover only, like every other point layer. Drawing 165
        # settlement names permanently competes with the topo backdrop, which
        # already labels them.
        maps.add_labelled_points(fmap, places, name="Towns and villages [OSM]")

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
        ("Ferry quays [OSM]", len(terminals), "#5f9ea0"),
        ("Cabins and wilderness huts [N50]", len(cabins), "#8b0000"),
        ("Huts and shelters [OSM]", len(shelters), "#00008b"),
        ("Trailheads, farms and sæters [OSM]", len(trailheads), "#6d4c41"),
        ("Towns and villages [OSM]", len(places), "#37474f"),
    ):
        if count:
            legend[f"{label} ({count})"] = color

    maps.add_legend(fmap, f"{PARK_NAME} nasjonalpark", legend)
    maps.finalize(fmap)

    map_path = output_dir / "lomsdal-visten.html"
    fmap.save(str(map_path))
    print(f"  Map: {map_path} ({map_path.stat().st_size / 1e6:.1f} MB)")

    # GPX exports cover the park plus the approach zone, since the park itself
    # has no road access and every trip starts outside it.
    print("\nExporting GPX...")
    exports = [
        ("lomsdal-visten-turrutebasen.gpx", [in_park, in_approach], "trail_name", ["maintenance_responsible", "difficulty", "marking", "length_km"]),
        ("lomsdal-visten-fkb.gpx", [fkb_in_park, fkb_in_approach], "typeveg", ["typeveg", "length_km"]),
        ("lomsdal-visten-n50.gpx", [n50_in_park, n50_in_approach], "typeveg", ["typeveg", "rutemerking", "length_km"]),
        ("lomsdal-visten-osm.gpx", [osm_in_park, osm_in_approach], "name", ["highway", "surface", "sac_scale", "length_km"]),
    ]
    for filename, parts, name_field, desc_fields in exports:
        populated = [part for part in parts if len(part)]
        if not populated:
            continue
        combined = gpd.GeoDataFrame(pd.concat(populated, ignore_index=True), crs="EPSG:4326")
        path, stats = export_to_gpx(combined, output_dir / filename, name_field=name_field, desc_fields=desc_fields)
        print(f"  {path.name}: {stats['total_trails']} tracks, {stats['total_points']:,} points, {stats['file_size_mb']:.2f} MB")

    print("\n" + "=" * 70)
    print(f"Sources: Turrutebasen {version} (CC0) | N50 Kartdata (CC BY 4.0) | Traktorveg og Skogsbilveg (CC BY 4.0)")
    print("         all Kartverket | Naturbase (NLOD, Miljødirektoratet) | OpenStreetMap (ODbL)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

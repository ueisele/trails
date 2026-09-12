"""What building a walking network is, whichever country's registers go in.

:mod:`trails.routing` turns named GeoDataFrames into chains and edges and has
never heard of a register. A country module — :mod:`trails.network.norway`,
:mod:`trails.network.sweden` — says which datasets go in, what a route costs
on each, what a chain carries and which lines make the marking masks. Between
the two sits everything that is the same for both and must stay the same: the
parameters that decide a build, the fingerprint that says whether a cached
graph answers for these inputs, the derivation of the three edge fields, the
protected-area table a page carries, and the build itself.

It is parametrised by :class:`Rules` — the metric CRS the country is built in,
how its protected-area register names things — and by a country's own
:class:`Params`. A country module wraps each function with its rules, so a
caller reads ``norway.build`` and ``sweden.build`` and nothing between them.

**The fingerprint is a contract with every graph already in a cache.** Its
text is built here exactly as the Norwegian module built it before this module
existed, so that Lomsdal-Visten's cached graph is still recognised; a change to
its shape is a rebuild of every graph, and should be one on purpose.
"""

import argparse
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NamedTuple, Self

import geopandas as gpd
import pandas as pd

from trails.io import cache as cache_module
from trails.routing import (
    CHAIN_COVERAGE_COLUMNS,
    DEFAULT_ASCENT_THRESHOLD_M,
    DEFAULT_MARKED_M,
    DEFAULT_MIN_SHARE,
    DEFAULT_RECORDED_M,
    DEFAULT_STEP_M,
    PROTECTED_COLUMN,
    ChainRule,
    Network,
    NetworkSource,
    build_chains,
    build_network,
    chain_coverage,
    chains_of,
    no_path_recorded,
    protected_within,
    split_source,
    waymarked,
)
from trails.routing.graph import DEFAULT_BRIDGE_COST_FACTOR
from trails.routing.sources import BRIDGE, FERRY

#: When a line was captured, as a date rather than the timestamp every register
#: stores. See :func:`with_capture_date` for why the rendering happens before
#: the chains rather than after them.
SURVEYED_FIELD = "surveyed"

#: How finely the outlines the page carries are drawn, in metres.
#:
#: The page needs them for ground no edge covers — a leg drawn straight across
#: open terrain, whose share is decided at its own height samples — and for
#: saying where a route crosses a boundary. Neither wants the register's full
#: precision: measured over Lomsdal-Visten the 31 areas come to 30,105 vertices
#: and 0.66 MB of coordinates, and at five metres to 4,195 and 0.09 MB against
#: a 37.5 MB page.
#:
#: **Five and not ten.** Ten was the figure this arrived with, on the argument
#: that it lies inside the ±5 m the sampling already accepts at each crossing.
#: Measured, it does not: Douglas-Peucker at 10 m moves that register's
#: boundaries by up to 16.1 m, and at 5 m by 5.9 m. The saving between the two
#: is 0.02 MB. So the tolerance is set where the claim about it is true.
PROTECTED_SIMPLIFY_M = 5.0


@dataclass(frozen=True)
class Rules:
    """What a country's build does the same way every time.

    Attributes:
        metric_crs: The CRS the network is built in; every length below is in
            its metres
        layout: What a stored graph holds, bumped whenever a build starts
            producing something a cached one does not carry
        protected_id: What names a protected area, on every edge in one
        protected_name: What an area is called
        protected_form: Which of the register's forms it is
        form_label: The words a sign uses for a form
        marked_m: How close counts as running along a marking mask
        recorded_m: How close counts as recorded at all
        min_share: How much of an edge has to lie that close
    """

    metric_crs: str
    layout: str
    protected_id: str
    protected_name: str
    protected_form: str
    form_label: Callable[[object], str]
    marked_m: float = DEFAULT_MARKED_M
    recorded_m: float = DEFAULT_RECORDED_M
    min_share: float = DEFAULT_MIN_SHARE


@dataclass(frozen=True, kw_only=True)
class Params:
    """Everything that decides what a network comes out as, in any country.

    Every field here except ``force_download`` and ``rebuild`` goes into the
    cache key, so two callers agreeing on these agree on the graph — which is
    the point of the class. Anything that would change the result and is *not*
    here is a cache that answers for a build it did not come from. A country
    adds what only it needs.

    Attributes:
        cache_dir: Root cache directory
        approach_km: Width of the approach zone around the area
        stroke_deg: Largest deflection accepted as a way continuing through a
            junction
        probe_m: How far either side of a junction the direction is read
        bridge_m: How far a loose end may reach for another node
        ferry_cost_km: What a crossing costs, as kilometres walked
        route_noding_m: Tolerance for the simplified copy the published route
            datasets are noded by; their own geometry is kept either way. Off,
            because it was measured and buys nothing that is missing.
        road_name_m: How far a road fragment may look for its name in a
            place-name register
        trail_name_m: How far a recorded path may look for a route name
        elevation_step_m: How far apart the height samples are laid along an
            edge. A parameter only so that the invariance the ascent threshold
            exists for can be checked: the same route has to read the same
            climb at 5, 10 and 15 m.
        ascent_threshold_m: Gains under this are not counted as climb
        force_download: Re-download source data instead of using the cache
        rebuild: Rebuild the graph even if a cached one matches
    """

    cache_dir: str
    approach_km: float = 15.0
    stroke_deg: float = 45.0
    probe_m: float = 5.0
    bridge_m: float = 25.0
    ferry_cost_km: float = 5.0
    route_noding_m: float = 0.0
    road_name_m: float = 25.0
    trail_name_m: float = 25.0
    elevation_step_m: float = DEFAULT_STEP_M
    ascent_threshold_m: float = DEFAULT_ASCENT_THRESHOLD_M
    force_download: bool = False
    rebuild: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace, **overrides: Any) -> Self:
        """Read whichever of these a command line happens to offer.

        The scripts expose different subsets — the map has no reason to offer
        a noding tolerance — and what a script leaves out has to fall to the
        default rather than to whatever that script felt like, or two scripts
        would build different graphs from the same ground.

        Args:
            args: Parsed command line
            **overrides: Values to use in preference to both

        Returns:
            The parameters
        """
        taken = {name: getattr(args, name) for name in cls.__dataclass_fields__ if hasattr(args, name)}
        return cls(**{**taken, **overrides})


class Masks(NamedTuple):
    """Raw source geometry the two derived edge fields are decided against.

    Built out of the sources rather than read off the edges, and that is not a
    detail. A marking flag reaches an edge only through the chain it lies on,
    where a run that changes character has already been merged into an
    ambiguous ``JA / NEI`` — over Lomsdal-Visten 38 chains and 158 km of it,
    exactly where the answer matters. A mask has no such problem and it treats
    every source alike: a route register's edge lies on its own feature and
    comes out marked without a special case.

    Attributes:
        marked: Every line a register says is waymarked
        unmarked: Every line a register says is not
        recorded: Every line from the sources whose lines record that
            something is drawn on this ground
    """

    marked: gpd.GeoSeries
    unmarked: gpd.GeoSeries
    recorded: gpd.GeoSeries


def zone_around(area: gpd.GeoDataFrame, distance_km: float, metric_crs: str) -> gpd.GeoDataFrame:
    """Grow an outline by a distance, keeping the interior.

    Args:
        area: Boundary in EPSG:4326
        distance_km: Width of the approach zone in kilometres
        metric_crs: What to measure the distance in

    Returns:
        The area and its approach zone as one polygon, in EPSG:4326
    """
    metric = area.to_crs(metric_crs)
    return gpd.GeoDataFrame(geometry=metric.buffer(distance_km * 1000), crs=metric_crs).to_crs("EPSG:4326")


def with_capture_date(gdf: gpd.GeoDataFrame, field: str) -> gpd.GeoDataFrame:
    """Render a capture timestamp as the date a popup shows.

    Rendered here rather than after chaining, and that is the whole reason the
    function exists: a chain spans several features and joins the values they
    disagree on, so a timestamp reaching the chain arrives as
    ``1984-03-01 00:00:00+00:00 / 2005-06-06 00:00:00+00:00`` and no parser
    reads it back. As dates the same chain reads ``1984-03-01 / 2005-06-06``,
    which is both true and legible.

    Args:
        gdf: Features carrying the source's own capture timestamp
        field: Column holding it

    Returns:
        Copy carrying :data:`SURVEYED_FIELD` as ``YYYY-MM-DD``
    """
    captured = pd.to_datetime(gdf[field], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    return gdf.assign(**{SURVEYED_FIELD: captured})


def edge_costs(sources: list[NetworkSource], params: Params) -> dict[str, dict[str, float]]:
    """Say what a metre on each dataset costs a route.

    For a consumer that has the geometry but not the cost column, which is the
    position a browser is in. The cost of a walked edge is its length times its
    source's factor, and the length is in the geometry already — so what has to
    travel is one number per source rather than one per edge.

    A crossing is the exception, and travels as a whole crossing's cost: it is
    the same decision whether it is 2 km or 20, so its cost is not its length
    and cannot be recovered from one.

    Args:
        sources: The datasets, as loaded
        params: What decides the build, for the crossing cost

    Returns:
        What each source costs, by source name, including the connectors that
        belong to no source at all
    """
    costs: dict[str, dict[str, float]] = {}
    for source in sources:
        costs[source.name] = {"flatM": params.ferry_cost_km * 1000} if source.kind == FERRY else {"factor": source.cost_factor}
    # Nobody drew a connector, and :func:`build` leaves its factor at the
    # default, so this is the same number the edges were weighted with.
    costs[BRIDGE] = {"factor": DEFAULT_BRIDGE_COST_FACTOR}
    return costs


def protected_table(protected: gpd.GeoDataFrame, rules: Rules, *, simplify_m: float = PROTECTED_SIMPLIFY_M) -> list[dict[str, Any]]:
    """Say what each protected area is and where its boundary runs, for a page.

    The sibling of :func:`edge_costs`: what a consumer needs that has the edges
    but not the polygons the edges were measured against, which is the position
    a browser is in. It travels as **one** list, because the codes on the edges
    and the outlines a click is tested against must not be able to mean two
    different areas.

    Every ring of an area goes in one flat list, its holes among them, and a
    point is inside where it is enclosed by an odd number of them. That is exact
    for a valid multipolygon and needs no outer-and-inner structure to keep in
    step with itself.

    Args:
        protected: The areas, whole, in EPSG:4326
        rules: How the register names things
        simplify_m: Vertex tolerance for the outlines, in metres

    Returns:
        One entry per area, in the order the edges name them, each with its id,
        its name, the words for its form, its bounding box and its rings
    """
    simplified = protected.to_crs(rules.metric_crs).geometry.simplify(simplify_m).to_crs("EPSG:4326") if len(protected) else protected.geometry
    table: list[dict[str, Any]] = []
    for (_, area), shape in zip(protected.iterrows(), simplified, strict=True):
        rings = []
        # A MultiPolygon is what a register hands back for most areas, even the
        # ones drawn in one piece, and a Polygon has no `geoms`.
        outline: Any = shape
        parts: list[Any] = list(outline.geoms) if outline.geom_type == "MultiPolygon" else [outline]
        for polygon in parts:
            for ring in (polygon.exterior, *polygon.interiors):
                # Six places is 0.11 m of latitude, the grid the payload's own
                # coordinates are written on, and a third of what the outline
                # was just simplified by.
                rings.append([[round(x, 6), round(y, 6)] for x, y in ring.coords])
        west, south, east, north = shape.bounds
        table.append(
            {
                "id": str(area[rules.protected_id]),
                "name": str(area[rules.protected_name]),
                "form": rules.form_label(area[rules.protected_form]),
                # Tested before the rings are, so a point out on the coast is
                # thirty cheap comparisons rather than four thousand.
                "bounds": [round(west, 6), round(south, 6), round(east, 6), round(north, 6)],
                "rings": rings,
            }
        )
    return table


def fingerprint(sources: list[NetworkSource], masks: Masks, params: Params, protected: gpd.GeoDataFrame, rules: Rules) -> str:
    """Summarise what went into a build, so a cached one can be recognised.

    Args:
        sources: The datasets
        masks: What the derived edge fields were decided against
        params: What shaped the result
        protected: The protected areas every edge is measured against
        rules: The country's rules, which shape it too

    Returns:
        Short hash naming this build
    """
    # Every parameter that shapes the graph, including the two join distances:
    # they change no geometry, only which chains carry which identity, so a row
    # count and a total length cannot tell two of these builds apart.
    parts = [
        rules.layout,
        f"{params.approach_km}|{params.stroke_deg}|{params.probe_m}|{params.bridge_m}"
        f"|{params.ferry_cost_km}|{params.route_noding_m}|{params.road_name_m}|{params.trail_name_m}"
        # And how the ground under the edges was read. Neither moves a line, but
        # a graph sampled every 15 m must not be served to a caller asking for
        # every 5 m — that is precisely the comparison the threshold is checked
        # by, and it would compare a cache against itself.
        f"|{params.elevation_step_m}|{params.ascent_threshold_m}",
        # And the masks with the rule they are read by. A mask is a filtered
        # subset of its sources, so a change in which features go into one shows
        # up in no source's row count or length.
        f"{mask_digest(masks.marked)}|{mask_digest(masks.unmarked)}|{mask_digest(masks.recorded)}|{rules.marked_m}|{rules.recorded_m}|{rules.min_share}",
        # And the protected areas, which are not a mask and not a source: they
        # sit in neither of the digests above, and a boundary moved by a
        # revision changes what every edge under it says without changing a
        # line of the network.
        protected_digest(protected, rules),
    ]
    for source in sources:
        length = source.gdf.to_crs(rules.metric_crs).length.sum() if len(source.gdf) else 0.0
        # And the values the chains are built from, not only the geometry they
        # are built along. Names arrive from other registers, so they show up
        # in no source's own row count or length — yet a change in one moves
        # where a chain ends.
        parts.append(f"{source.name}:{len(source.gdf)}:{length:.0f}:{source.cost_factor}:{source.keep_whole}:{values_digest(source)}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def mask_digest(mask: gpd.GeoSeries) -> str:
    """Summarise a mask, so a graph is not read back for a different one.

    Args:
        mask: Lines the derived fields are decided against

    Returns:
        Its size and total length
    """
    return f"{len(mask)}:{mask.length.sum():.0f}"


def protected_digest(protected: gpd.GeoDataFrame, rules: Rules) -> str:
    """Summarise the protected areas, so a graph is not read back for others.

    Args:
        protected: The areas every edge is measured against
        rules: What names an area, and what to measure it in

    Returns:
        Their ids and their outlines, as one short digest
    """
    if not len(protected):
        return "0"
    metric = protected.to_crs(rules.metric_crs)
    digest = hashlib.sha256()
    for identity, shape in zip(protected[rules.protected_id].astype(str).tolist(), metric.geometry.tolist(), strict=True):
        # Its area and its outline together: an area redrawn keeping its size
        # would move every boundary an edge is measured against and leave one
        # of the two figures standing.
        digest.update(f"{identity}:{shape.area:.0f}:{shape.length:.0f}\n".encode())
    return f"{len(protected)}:{digest.hexdigest()[:12]}"


def values_digest(source: NetworkSource) -> str:
    """Summarise the non-geometric values a source contributes to its chains.

    Args:
        source: Dataset going into the build

    Returns:
        Short digest of its identity column and attributes, or ``-`` where it
        has neither
    """
    columns = [name for name in dict.fromkeys((source.identity_field, *source.attributes)) if name]
    if not columns:
        return "-"

    digest = hashlib.sha256()
    for column in columns:
        digest.update(f"\n{column}\n".encode())
        # `na_rep` is what keeps a missing value visible here. Without it
        # `str.cat` drops one entirely rather than writing a placeholder, so a
        # road that loses its name and a road that never had one hash the same,
        # and this digest exists precisely because a name arriving from another
        # register changes neither the row count nor the length of the source
        # it lands in. Under pandas 2 `astype(str)` wrote "None" and hid the
        # gap; pandas 3 stopped, which is what exposed it.
        digest.update(source.gdf[column].astype(str).str.cat(sep="\x00", na_rep="\x01").encode())
    return digest.hexdigest()[:12]


def chain_report(sources: list[NetworkSource], clip: gpd.GeoDataFrame, params: Params, rules: Rules) -> pd.DataFrame:
    """Count each source's chains under both rules.

    Breaking at every junction is the baseline: it is what ``linemerge`` alone
    gives, and it cuts a road into a scrap at every side turning. The stroke rule
    is what makes a chain something worth clicking.

    Args:
        sources: The datasets
        clip: Extent to cut them to
        params: What decides the build
        rules: What to measure in

    Returns:
        One row per source
    """
    rows = []
    for source in sources:
        # The baseline is reported for every source, a published one included:
        # it is what noding that source against itself would have cost it.
        pieces = split_source(source, clip, metric_crs=rules.metric_crs)
        baseline = build_chains(pieces, source, rule=ChainRule.JUNCTION)

        # The angle alone, without the identity rule, is what the decisions
        # document measured. Reported next to it because the two differ by more
        # than the rounding: identity ends a chain wherever a way divides, and
        # a named road divides at most of its junctions.
        anonymous = replace(source, identity_field=None)
        angle_only = build_chains(pieces, anonymous, rule=ChainRule.STROKE, stroke_angle_deg=params.stroke_deg, probe_m=params.probe_m)

        chains = chains_of(
            source, clip, rule=ChainRule.STROKE, stroke_angle_deg=params.stroke_deg, probe_m=params.probe_m, metric_crs=rules.metric_crs
        )
        rows.append(
            {
                "source": source.name,
                "features": len(source.gdf),
                "at every junction": len(baseline),
                "angle only": len(angle_only),
                "with identity": len(chains),
                "whole": source.keep_whole,
                "km": chains["length_m"].sum() / 1000,
                "mean chain m": chains["length_m"].mean() if len(chains) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build(
    sources: list[NetworkSource],
    masks: Masks,
    clip: gpd.GeoDataFrame,
    params: Params,
    rules: Rules,
    *,
    name: str,
    protected: gpd.GeoDataFrame,
    measure: Callable[[Network], Network],
) -> tuple[Network, pd.DataFrame]:
    """Build the network, or read back the last build of the same inputs.

    Reading the ground height along every edge is what makes this expensive —
    in Norway twenty thousand requests against a public service, a quarter of
    an hour once. Two caches stand between that and a rebuild: this one, which
    serves an unchanged graph whole, and whatever the country's height reader
    keeps underneath it.

    Args:
        sources: The datasets
        masks: What the derived edge fields are decided against
        clip: Extent to cut them to
        params: What decides the build
        rules: The country's rules
        name: Area the graph is of, which names its cache entry
        protected: The protected areas every walked edge is measured against
        measure: How the ground height is put on the finished network

    Returns:
        The network and the per-source chain counts
    """
    store = cache_module.Object(cache_dir=str(Path(params.cache_dir) / "objects"))
    key = f"route_graph_{name}_{fingerprint(sources, masks, params, protected, rules)}"

    if not params.rebuild and store.exists(key):
        print(f"\nReading the graph back from the cache ({key})...")
        cached: dict[str, Any] = store.load(key)
        return cached["network"], cached["chains"]

    print("\nBuilding chains per source...")
    chains = chain_report(sources, clip, params, rules)

    print("Noding every source against every other...")
    network = build_network(
        sources,
        clip,
        metric_crs=rules.metric_crs,
        stroke_angle_deg=params.stroke_deg,
        probe_m=params.probe_m,
        bridge_m=params.bridge_m,
        ferry_cost_m=params.ferry_cost_km * 1000,
    )

    print("Asking every edge what the ground it runs over is recorded as, and what protects it...")
    network = replace(network, edges=derive(network.edges, masks, protected, rules))

    # And summed along the chains, because a chain is what gets selected and
    # shown while an edge is only what a mask can be tested against.
    covered = chain_coverage(network.chains, network.edges)
    network = replace(network, chains=network.chains.assign(**{column: covered[column] for column in CHAIN_COVERAGE_COLUMNS}))

    print(f"Reading the ground height every {params.elevation_step_m:g} m along every edge but the crossings...")
    network = measure(network)

    store.save(key, {"network": network, "chains": chains}, metadata={"area": name, "approach_km": params.approach_km})
    return network, chains


def derive(edges: gpd.GeoDataFrame, masks: Masks, protected: gpd.GeoDataFrame, rules: Rules) -> gpd.GeoDataFrame:
    """Add the three fields an edge cannot read off the chain it lies on.

    All three are summed in kilometres by a planned route, which is what earns
    them a place on the edge rather than on the chain: a chain takes one value
    along its whole length, and every one of these changes along it.

    The third is decided differently from the first two, and deliberately. A
    mask answers *how near* — how much of an edge runs along something a
    register drew — because two datasets disagreeing about where a path lies is
    the subject. A protected boundary is a legal line with a published geometry,
    so the answer is a length rather than a share, and an edge that lies ten
    metres inside one says ten metres.

    Args:
        edges: The graph's edges
        masks: Raw source geometry to decide the first two against
        protected: The protected areas to measure the third against, in
            EPSG:4326 or in the CRS of the edges
        rules: How near counts, and what names an area

    Returns:
        The edges carrying ``waymarked``, ``no_path_recorded`` and
        :data:`~trails.routing.protection.PROTECTED_COLUMN`. The first two are
        empty on a crossing and on an inferred connector; the third is empty on
        a crossing alone, because a walker covers a connector's ground and that
        ground lies inside a boundary or outside it.
    """
    # Reprojected whether or not it holds anything. An *empty* frame left in the
    # register's own degrees still states a CRS, and the measurement refuses a
    # mismatch — so a build over ground nothing protects would fail after every
    # source had been loaded, on the one path this is written to support.
    areas = protected.to_crs(edges.crs) if edges.crs is not None else protected
    return edges.assign(
        waymarked=waymarked(edges, masks.marked, masks.unmarked, distance_m=rules.marked_m, min_share=rules.min_share),
        no_path_recorded=no_path_recorded(edges, masks.recorded, distance_m=rules.recorded_m, min_share=rules.min_share),
        **{PROTECTED_COLUMN: protected_within(edges, areas, id_field=rules.protected_id)},
    )

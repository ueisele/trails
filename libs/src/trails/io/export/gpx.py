"""GPX export functionality for trail data.

**An exported file is the only thing that leaves this machine**, so it is also
the only place the sources and their licences have to be recorded. It says what
it draws on, what each of those is licensed under and what version of it was
read; it carries a height on every trackpoint and the rule that height figure
was reached under; and it says which chain it is, so a file this map wrote can
be recognised on being loaded again rather than matched against the network.

**A route is a second kind of thing this file can be**, and it is described
rather than merely drawn: the points a reader put down travel as ``<wpt>``
elements before the track, each saying whether it was set or generated, and the
legs between them are listed on the track with the kind and length of every part
— because a segment breaks where the ground stops and four routed legs laid end
to end are one segment, so a segment cannot say which leg it belongs to.

**A browser writes the same file from the same graph**, and the two cannot share
a line of code across that boundary. What holds them together is that every name
a field travels under is a constant here rather than a literal in two places —
:data:`TRAILS_NAMESPACE`, :data:`DEFAULT_EXTENSION_FIELDS` and
:data:`EXTENSION_DECIMALS` are what
:class:`~trails.visualization.maps._ProfilePanel` writes against — and that the
two are exported on a real chain and compared whenever the work is accepted.

**That comparison has a tolerance, and it is the page's payload rather than
either writer.** Measured on a 3.78 km chain: the same extension fields exactly,
every point of each file within 5.6 cm of the other's line, and no height apart
at all over the points both put in one place — the payload carries the same
centimetres the service answered with, so the page loses nothing on the way. The
counts differ by nine (see :mod:`trails.routing.track`). None of that is checked
by the test suite, which cannot run the page's JavaScript; it is checked in a
browser, and the constants are what keep the two from drifting between those
runs.
"""

import math
from datetime import UTC, datetime
from numbers import Real
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from lxml import etree
from shapely.geometry import LineString, MultiLineString

#: Namespace of everything this map puts in an ``<extensions>`` block. GPX 1.1
#: allows an extension from **any namespace but its own**, and reads what it
#: does not know leniently, so Komoot and Outdooractive ignore all of this
#: rather than refusing the file.
TRAILS_NAMESPACE = "https://github.com/ueisele/trails/gpx/1"

#: Prefix that namespace is written under.
TRAILS_PREFIX = "trails"

#: What a track's ``<extensions>`` carry, as column to the name it travels
#: under. Enough to recognise a file as one of this map's own — the chain id is
#: stable across builds — and enough for a reader to know what the ascent figure
#: means, which is the point of carrying the method beside it.
DEFAULT_EXTENSION_FIELDS = {
    "chain_id": "chain",
    "track_name": "name",
    "source": "source",
    "ascent": "ascent",
    "descent": "descent",
    "no_path_m": "unrecorded",
}

#: Decimals a number written into ``<extensions>`` keeps, and it is written to
#: exactly that many whether it needs them or not. The page carries its figures
#: already rounded to the same place, and ``500`` there against ``500.0`` here
#: would be two files disagreeing about a number both of them got right.
EXTENSION_DECIMALS = 1

#: Decimals an ``<ele>`` keeps. **Not the same question as the figures above**,
#: and they were one constant until a written file disagreed with itself. A
#: figure like an ascent is read to a decimetre and shown as whole metres, so one
#: place is generous. A height is what the *figure was computed from*, and the
#: height service answers in centimetres: written to one place, a reader
#: recomputing the ascent off the file's own values got a number up to 10.5 m —
#: 9.2 % on a short climb — away from the one the same file states. Two places,
#: which is what the service gives and what
#: :data:`~trails.visualization.encoding.DEFAULT_ELEVATION_QUANTUM` carries.
ELEVATION_DECIMALS = 2

#: How many metres *this file states* were drawn from one source, and it is
#: written only where a caller worked them out. A chain has one source and
#: leaves it unset, because the length is the track's; a planned route runs over
#: several and states each, so that *3.20 km OSM (ODbL)* is readable before the
#: file is passed on rather than a blanket warning nobody reads.
#:
#: **Stated, not written**, and the two come apart in exactly one place: a
#: crossing's own line is never laid into the track, but its length is a figure
#: in the file and that figure came from somebody's geometry. So a route over a
#: ferry credits the ferry dataset for metres no ``<trkpt>`` holds, and the
#: credited kilometres do not sum to the track's length. Crediting a source
#: whose measurement the file repeats is the point; summing to the track was
#: never the claim.
SOURCE_LENGTH_FIELD = "metres"

#: What each entry of ``sources`` says. ``licence`` is spelled the way the rest
#: of this codebase spells it; the source modules it is read from call the same
#: field ``license``, and the translation happens where they are read. A field
#: with nothing in it is left out, which is what lets a chain and a route share
#: one list.
SOURCE_CREDIT_FIELDS = ("name", "licence", "version", "attribution", "url", SOURCE_LENGTH_FIELD)

#: What one clicked or generated point of a route travels under. ``origin`` is
#: the field that matters and it is not decoration: phase 8 loads a file back
#: and must never read a marker *the map* placed — at a park boundary, at a hut
#: — as a station somebody chose, or a loaded route gains points nobody placed
#: and starts routing through them. Nothing generates one yet; the field goes in
#: now because a file written before its description existed can never be
#: restored exactly, only matched.
WAYPOINT_ORIGIN_FIELD = "origin"

#: What ``origin`` says of a point a reader put down.
WAYPOINT_SET = "set"

#: What ``origin`` says of a point the map placed by itself.
WAYPOINT_GENERATED = "generated"

#: What a planned route's track ``<extensions>`` carry beyond
#: :data:`DEFAULT_EXTENSION_FIELDS`, as the key the page holds a figure under to
#: the name it is written down as. Every one is a scalar of the whole route,
#: which is what the extensions mechanism is for; the per-leg detail is
#: :data:`LEGS_ELEMENT` below, because it is a list and not a scalar.
#:
#: **Unknown is its own bucket and is never folded into unmarked.** Measured
#: over the walked network without its inferred connectors, 63.4 % of the length
#: is unknown and FKB — the largest source at 33.8 % — carries no marking
#: information at all. Calling that unmarked asserts what no source says.
#: ``undrawn`` is a fourth thing again: ground on a connector nobody drew, which
#: was never asked rather than asked and unanswered.
ROUTE_EXTENSION_FIELDS = {
    "ascent": "ascent",
    "descent": "descent",
    "walked": "walked",
    "crossed": "crossed",
    "straight": "straight",
    "unrecorded": "unrecorded",
    "marked": "marked",
    "unmarked": "unmarked",
    "unknown": "unknown",
    "undrawn": "undrawn",
}

#: The element saying what kind of thing a track is, and the value a planned
#: route writes into it. A file that says what it is can be recognised on being
#: loaded rather than matched against the network, which is what phase 8 reads.
ROUTE_KIND_FIELD = "kind"

#: What :data:`ROUTE_KIND_FIELD` holds on a planned route.
ROUTE_KIND = "route"

#: Where a route's legs are listed, in order.
#:
#: **A leg's mode cannot go on a ``<trkseg>``, and that is a fact about the
#: geometry rather than a preference.** A segment is a stretch of track and a
#: stretch breaks only where the ground stops, so four routed legs laid end to
#: end are **one** segment and a segment-level extension could carry one mode
#: for all four. The legs are therefore listed on the track, in the order they
#: were clicked, each holding its parts in the order they are walked — which is
#: also the form phase 8 needs, since a leg runs between two waypoints and a
#: waypoint is what a reader put down.
LEGS_ELEMENT = "legs"

#: One leg of a route, holding :data:`PART_ELEMENT` children in order.
LEG_ELEMENT = "leg"

#: One part of a leg: a run of one kind. A routed leg that takes a ferry is
#: walked, then crossed, then walked, and those are three parts of one leg.
PART_ELEMENT = "part"

#: What a part says it is — ``routed``, ``land``, ``water`` or ``ferry``.
PART_KIND_ATTR = "kind"

#: How long a part is, in metres.
PART_LENGTH_ATTR = "m"


def create_gpx_document(
    name: str = "Norwegian Trails Export",
    description: str | None = "Trail data from Geonorge",
    sources: list[dict[str, str]] | None = None,
) -> etree.Element:
    """Create a GPX document with proper namespace and schema.

    **No ``<copyright>``, deliberately.** It holds exactly one licence and a
    route across this network has no single one to put there: Turrutebasen is
    CC0, FKB and N50 are CC BY 4.0, OpenStreetMap is ODbL and share-alike, UT.no
    is CC BY-NC and non-commercial. ODbL and NC compose badly and the strictest
    terms govern the mixture, so filling that element in would mean inventing an
    answer that does not exist. Listing what is actually there is both honest and
    more useful.

    Args:
        name: What the file calls itself
        description: A line about what is in it, or None to leave it out
        sources: What the file draws on, each entry carrying
            :data:`SOURCE_CREDIT_FIELDS`. Recorded twice: as text in ``<desc>``,
            which is what a person opening the file sees, and as one element per
            source in ``<extensions>``, which is what a program can read.

    Returns:
        GPX document element
    """
    gpx = etree.Element(
        "gpx",
        attrib={
            "version": "1.1",
            "creator": "trails-analysis",
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": (
                "http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"
            ),
        },
        nsmap={
            None: "http://www.topografix.com/GPX/1/1",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            TRAILS_PREFIX: TRAILS_NAMESPACE,
        },
    )

    # Add metadata
    metadata = etree.SubElement(gpx, "metadata")
    etree.SubElement(metadata, "name").text = name
    described = [description] if description else []
    if sources:
        described.append("Sources: " + " · ".join(_credit_line(credit) for credit in sources))
    if described:
        etree.SubElement(metadata, "desc").text = ". ".join(described)
    time_elem = etree.SubElement(metadata, "time")
    # Timezone-aware: utcnow() returns a naive datetime that claims to be UTC
    # and is deprecated for exactly that reason, and this value is written
    # into a file with a Z on the end.
    time_elem.text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    if sources:
        # After <time>, because GPX 1.1 fixes the order of what <metadata>
        # holds and <extensions> is last in it. Written anywhere else the file
        # parses and fails the schema.
        block = etree.SubElement(metadata, "extensions")
        for credit in sources:
            entry = etree.SubElement(block, f"{{{TRAILS_NAMESPACE}}}source")
            for field in SOURCE_CREDIT_FIELDS:
                if credit.get(field):
                    entry.set(field, str(credit[field]))

    return gpx


def _credit_line(credit: dict[str, str]) -> str:
    """Say what one source is and what may be done with it, in a phrase.

    The ``<desc>`` and the ``<extensions>`` below it record the same list twice,
    once for a person and once for a program, so a field carried in one and left
    out of the other would be two recordings of one thing that disagree. The
    page's own ``creditLine`` writes this phrase the same way, length first.

    Args:
        credit: One entry of ``sources``, carrying :data:`SOURCE_CREDIT_FIELDS`

    Returns:
        The source's name, its licence and the version it was read at, after the
        kilometres it contributed where a caller worked them out
    """
    inside = [str(credit[field]) for field in ("licence", "version", "attribution") if credit.get(field)]
    named = f"{credit.get('name', 'unknown')} ({', '.join(inside)})" if inside else str(credit.get("name", "unknown"))
    metres = credit.get(SOURCE_LENGTH_FIELD)
    return f"{float(metres) / 1000:.2f} km {named}" if metres else named


def waypoint_element(waypoint: dict[str, Any]) -> etree.Element:
    """Write one point of a route down as a GPX waypoint.

    **A waypoint is not part of the ``<extensions>`` mechanism.** It is a GPX
    1.1 top-level element in its own right, written *before* the first ``<trk>``
    — the extensions are a block inside it — and a file that puts it anywhere
    else parses and fails the schema.

    **No ``<ele>``, deliberately.** The track carries every height that was read
    and the file states the rule they were read under; a height on the waypoint
    as well would be the same number in a fourth place, and where the route
    happens to break at that point there is no reading to put there at all. What
    a waypoint is for is *where* a reader chose to go.

    Args:
        waypoint: ``lat`` and ``lon``, an optional ``name``, and
            :data:`WAYPOINT_ORIGIN_FIELD` saying whether a reader put the point
            down (:data:`WAYPOINT_SET`) or the map did (:data:`WAYPOINT_GENERATED`)

    Returns:
        GPX waypoint element

    Raises:
        KeyError: If the point has no position. A waypoint at no place is not a
            waypoint, and writing one at 0/0 would put it in the Gulf of Guinea.
    """
    element = etree.Element("wpt", attrib={"lat": str(waypoint["lat"]), "lon": str(waypoint["lon"])})
    # The order GPX 1.1 fixes for what a <wpt> holds: <name> well before
    # <extensions>, which is last of the twenty-odd it allows.
    if waypoint.get("name"):
        etree.SubElement(element, "name").text = str(waypoint["name"])
    origin = waypoint.get(WAYPOINT_ORIGIN_FIELD)
    if origin:
        block = etree.SubElement(element, "extensions")
        etree.SubElement(block, f"{{{TRAILS_NAMESPACE}}}{WAYPOINT_ORIGIN_FIELD}").text = str(origin)
    return element


def linestring_to_track_segment(geometry: LineString, simplify_tolerance: float | None = None) -> etree.Element:
    """Convert a LineString to a GPX track segment.

    **An elevation is written from the geometry's own third ordinate**, where it
    has one and it is a number. A line whose Z is NaN was laid over ground the
    height model has no reading for — every ferry crossing, and two stubs beyond
    its edge — and the point is written without an ``<ele>`` rather than with an
    invented one. Nothing downstream can tell an invented height from a read one.

    **No ``<time>``, ever.** Komoot and Outdooractive read a track carrying
    timestamps as a *recorded activity* rather than a plan, and inventing them
    would turn a route being considered into a walk nobody took.

    Args:
        geometry: LineString geometry in WGS84, carrying a height per point in
            its Z ordinate where one was read
        simplify_tolerance: Optional tolerance for simplification (degrees)

    Returns:
        GPX track segment element
    """
    trkseg = etree.Element("trkseg")

    # Optionally simplify geometry
    if simplify_tolerance:
        geometry = geometry.simplify(simplify_tolerance, preserve_topology=True)  # type: ignore[assignment]

    # Extract coordinates
    coords = list(geometry.coords)

    for position in coords:
        lon, lat = position[0], position[1]
        trkpt = etree.SubElement(trkseg, "trkpt", attrib={"lat": str(lat), "lon": str(lon)})
        height = position[2] if len(position) > 2 else None
        # A centimetre, which is what the height service answers at and what
        # the page's own copy of these values carries. Fewer places and the file
        # stops agreeing with the ascent it states; more would be digits nobody
        # measured.
        if height is not None and not math.isnan(height):
            etree.SubElement(trkpt, "ele").text = _figure(height, ELEVATION_DECIMALS)

    return trkseg


def _figure(value: float, decimals: int = EXTENSION_DECIMALS) -> str:
    """Write a number down the way both writers of this file write it.

    **Rounded first, then formatted, and the order is the whole of it.** The
    page formats with ``toFixed``, which rounds a half *up*, where this formats
    with Python, which rounds a half *to even*: given ``17.25`` the two would
    write ``17.3`` and ``17.2``. They never are given it. Every figure the page
    carries has already been through
    :func:`~trails.visualization.maps._figure_values`, which applies this same
    ``round`` before the value leaves Python, so what ``toFixed`` receives is a
    value already on the grid and no longer a half. Rounding here as well is
    what puts this writer on that same grid — take it out and the two rules stop
    agreeing on every chain whose ascent lands on a half.

    Args:
        value: The number
        decimals: Places to keep

    Returns:
        The number, rounded and then written to exactly that many places, so
        that the same value never comes out as ``500`` in one file and ``500.0``
        in another
    """
    return f"{round(float(value), decimals):.{decimals}f}"


def trail_to_track(
    trail: pd.Series,
    name_field: str = "trail_name",
    desc_fields: list[str] | None = None,
    simplify_tolerance: float | None = None,
    extension_fields: dict[str, str] | None = None,
    ascent_method: str | None = None,
    geometry: LineString | MultiLineString | None = None,
) -> etree.Element:
    """Convert a trail (GeoDataFrame row) to a GPX track.

    Args:
        trail: Single row from a GeoDataFrame
        name_field: Field to use for track name
        desc_fields: Fields to include in description
        simplify_tolerance: Optional tolerance for geometry simplification
        extension_fields: Mapping of column name to the name it travels under in
            ``<extensions>``, e.g. :data:`DEFAULT_EXTENSION_FIELDS`
        ascent_method: How the heights and the ascent figure were reached. The
            figure without it asserts nothing — the same route reads anywhere
            between 965 and 1,214 m depending on the rule — and it is also what
            explains why another platform's own model will disagree.
        geometry: Geometry to write instead of the row's own, for a caller
            holding a denser copy of the same line than the frame does

    Returns:
        GPX track element
    """
    trk = etree.Element("trk")

    # Add name
    name = trail.get(name_field, f"Trail {trail.name if hasattr(trail, 'name') else 'Unknown'}")
    if pd.notna(name):
        etree.SubElement(trk, "name").text = str(name)

    # Add description
    if desc_fields:
        desc_parts = []
        for field in desc_fields:
            if field in trail and pd.notna(trail[field]):
                desc_parts.append(f"{field}: {trail[field]}")
        if desc_parts:
            etree.SubElement(trk, "desc").text = " | ".join(desc_parts)

    # Add type if available
    if "type" in trail and pd.notna(trail["type"]):
        etree.SubElement(trk, "type").text = str(trail["type"])

    # Handle geometry
    geometry = trail.geometry if geometry is None else geometry

    # Before the segments and after everything else: GPX 1.1 fixes the order of
    # what a <trk> holds, and <extensions> is the last thing before them. The
    # sampling rule goes in only where the track carries a height to describe:
    # on a crossing it would state how a measurement was taken that was never
    # taken, and the page — which writes it under the same condition — would not.
    _add_extensions(trk, trail, extension_fields, ascent_method if _carries_height(geometry) else None)

    if isinstance(geometry, LineString):
        trkseg = linestring_to_track_segment(geometry, simplify_tolerance)
        trk.append(trkseg)
    elif isinstance(geometry, MultiLineString):
        # One segment per part, which is what a break in a track means: the two
        # stretches do not join, and a line drawn across the step between them
        # would be a route nobody can walk.
        for linestring in geometry.geoms:
            trkseg = linestring_to_track_segment(linestring, simplify_tolerance)
            trk.append(trkseg)

    return trk


def _carries_height(geometry: LineString | MultiLineString | None) -> bool:
    """Say whether anything was read along a line.

    Args:
        geometry: The line about to be written

    Returns:
        Whether any of its points carries a height. A Z of NaN is ground the
        model has no reading for, and a line made only of those says nothing
        about elevation however many ordinates it has.
    """
    if geometry is None or geometry.is_empty or not geometry.has_z:
        return False
    return bool(np.isfinite(shapely.get_coordinates(geometry, include_z=True)[:, 2]).any())


def _add_extensions(trk: etree.Element, trail: pd.Series, fields: dict[str, str] | None, ascent_method: str | None) -> None:
    """Say what this track is, in a namespace of this map's own.

    Args:
        trk: Track element to add the block to
        trail: The row the track was built from
        fields: Mapping of column name to the name it travels under
        ascent_method: How the heights and the ascent figure were reached
    """
    carried = {name: trail[column] for column, name in (fields or {}).items() if column in trail and pd.notna(trail[column])}
    if not carried and not ascent_method:
        return

    block = etree.SubElement(trk, "extensions")
    for name, value in carried.items():
        element = etree.SubElement(block, f"{{{TRAILS_NAMESPACE}}}{name}")
        # ``Real`` and not ``float``: a figure off a numpy array is an
        # ``np.float64``, which is a float, but one off an integer column is
        # an ``np.int64``, which is not — and would be written unrounded.
        element.text = _figure(float(value)) if isinstance(value, Real) and not isinstance(value, bool) else str(value)
    if ascent_method:
        etree.SubElement(block, f"{{{TRAILS_NAMESPACE}}}ascentMethod").text = ascent_method


def export_to_gpx(
    gdf: gpd.GeoDataFrame,
    output_path: Path,
    name_field: str = "trail_name",
    desc_fields: list[str] | None = None,
    simplify_tolerance: float | None = None,
    max_trails: int | None = None,
    *,
    title: str = "Norwegian Trails Export",
    description: str | None = "Trail data from Geonorge",
    sources: list[dict[str, str]] | None = None,
    extension_fields: dict[str, str] | None = None,
    ascent_method: str | None = None,
    track_field: str | None = None,
    waypoints: list[dict[str, Any]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Export GeoDataFrame of trails to GPX file.

    **Nothing is thinned unless a caller asks for it.** An exported track is the
    one thing that leaves this machine, and it carries the resolution its source
    recorded — that is a decision, not an oversight, and it is the opposite of
    what the map does with the copy it draws. The default used to be 1e-5
    degrees, about 1.1 m, which is under the survey accuracy of the best source
    here and still dropped 62 % of FKB's vertices and 65 % of UT.no's. On a path
    that matters: the target platforms do not know these ways and cannot rebuild
    a line between points they were not given.

    Args:
        gdf: GeoDataFrame with trail data
        output_path: Path for output GPX file
        name_field: Field to use for track names
        desc_fields: Fields to include in track descriptions
        simplify_tolerance: Tolerance for geometry simplification, in degrees.
            None keeps every vertex, which is what an export is for.
        max_trails: Maximum number of trails to export
        title: What the file calls itself
        description: A line about what is in it, or None to leave it out
        sources: What the file draws on, each entry carrying
            :data:`SOURCE_CREDIT_FIELDS`
        extension_fields: Mapping of column name to the name it travels under in
            each track's ``<extensions>``, e.g. :data:`DEFAULT_EXTENSION_FIELDS`
        ascent_method: How the heights and the ascent figure were reached
        track_field: Column holding the line to write instead of the frame's own
            geometry, from :func:`~trails.routing.track.chain_tracks`. It is
            already in WGS84 and carries a height per point, which the frame's
            geometry does not: the heights were sampled along the edges rather
            than at the vertices, and laying the two against each other is not
            this module's job.
        waypoints: Points to write before the tracks, each as
            :func:`waypoint_element` takes them. A chain export has none: a
            waypoint is a place somebody chose, and nobody chose anything about
            a line read out of a register.

    Returns:
        Tuple of (output_path, statistics_dict)

    Raises:
        KeyError: If ``track_field`` names a column the frame does not have.
            Falling back to the frame's own geometry would write a file of the
            right size holding no ``<ele>`` at all, while ``<metadata>`` went on
            crediting the height model and every track went on stating the rule
            its heights were read under — a plausible file, and wrong in the one
            way nothing downstream could detect.
    """
    if track_field and track_field not in gdf.columns:
        raise KeyError(f"the track to write is in no column called {track_field!r}; the frame has {list(gdf.columns)}")

    # Ensure we're in WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Default description fields
    if desc_fields is None:
        desc_fields = ["maintenance_responsible", "difficulty", "marking"]

    # Limit trails if specified
    export_gdf = gdf.head(max_trails) if max_trails else gdf

    # Create GPX document
    gpx = create_gpx_document(name=title, description=description, sources=sources)

    # Before every track and after the metadata, which is the order GPX 1.1
    # fixes for what a <gpx> holds. Written here rather than by the caller so
    # that the one place that knows the order is the one that writes it.
    for waypoint in waypoints or ():
        gpx.append(waypoint_element(waypoint))

    # Statistics
    stats: dict[str, Any] = {
        "total_trails": len(export_gdf),
        "total_points": 0,
        "skipped_trails": 0,
    }

    # Add each trail as a track
    for idx, trail in export_gdf.iterrows():
        try:
            written = trail[track_field] if track_field and track_field in trail else trail.geometry
            if written is None or written.is_empty:
                stats["skipped_trails"] += 1
                continue

            track = trail_to_track(
                trail,
                name_field=name_field,
                desc_fields=desc_fields,
                simplify_tolerance=simplify_tolerance,
                extension_fields=extension_fields,
                ascent_method=ascent_method,
                geometry=written,
            )
            gpx.append(track)

            # Counted off the written element, not off the geometry that went
            # in. Counting the input reports what the file would have held if
            # nothing thinned it — this file said 305,248 points while holding
            # 115,655, and the figure is one a reader is meant to trust.
            stats["total_points"] += len(track.findall("trkseg/trkpt"))

        except Exception as e:
            print(f"Warning: Failed to export trail {idx}: {e}")
            stats["skipped_trails"] += 1

    # Write to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tree = etree.ElementTree(gpx)
    tree.write(
        str(output_path),
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )

    # Millions of bytes, which is what "MB" says and what a file manager
    # shows. Dividing by 1024**2 and calling it MB reported 7.72 for a file
    # of 8.09.
    stats["file_size_mb"] = float(output_path.stat().st_size) / 1e6

    return output_path, stats

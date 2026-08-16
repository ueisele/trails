"""Tests for the parts of the build that do not need the network itself.

Loading the seven datasets needs eight municipality downloads and two web
services, so what is tested here is everything around that: the parameters that
decide a build, the masks the derived fields are read against, the fingerprint
that says whether a cached graph answers for these inputs, and the one
transformation applied to a source before it becomes chains.
"""

import argparse

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon
from trails.network.norway import (
    METRIC_CRS,
    SURVEYED_FIELD,
    Masks,
    Params,
    _join_values,
    _with_capture_date,
    edge_costs,
    fingerprint,
    masks_from,
    zone_around,
)
from trails.routing import DEFAULT_BRIDGE_COST_FACTOR, FERRY, IDENTITY_SEPARATOR, NetworkSource
from trails.routing.sources import BRIDGE

CATALOGUE = "routes.toml"


def lines(*offsets: float, marking: tuple[str | None, ...] = ()) -> gpd.GeoDataFrame:
    """Build a small path dataset, one east-west line per offset.

    Args:
        *offsets: Northing of each line
        marking: ``rutemerking`` per line, defaulting to nothing said

    Returns:
        The lines, in :data:`METRIC_CRS`
    """
    stated = marking or (None,) * len(offsets)
    return gpd.GeoDataFrame(
        {"rutemerking": list(stated)},
        geometry=[LineString([(0, offset), (100, offset)]) for offset in offsets],
        crs=METRIC_CRS,
    )


def network(**overrides: gpd.GeoDataFrame) -> list[NetworkSource]:
    """Build the seven sources a mask needs to exist, with empty ones by default.

    Args:
        **overrides: Datasets to use in place of an empty one, by source name
            with spaces as underscores

    Returns:
        The sources
    """
    empty = gpd.GeoDataFrame({"rutemerking": pd.Series(dtype="object")}, geometry=[], crs=METRIC_CRS)
    names = {"Turrutebasen": "Turrutebasen", "N50_paths": "N50 paths", "FKB": "FKB", "N50_roads": "N50 roads", "OSM": "OSM"}
    return [NetworkSource(name, overrides.get(key, empty)) for key, name in names.items()]


class TestParams:
    """Test Params."""

    def test_a_script_offering_a_parameter_decides_it(self):
        """Test the ordinary case: a command line value reaches the build."""
        args = argparse.Namespace(cache_dir=".cache", ut_routes=CATALOGUE, approach_km=5.0)
        assert Params.from_args(args).approach_km == 5.0

    def test_a_script_leaving_one_out_falls_to_the_default(self):
        """Test that what a script does not offer is not left to that script.

        The map and the graph report expose different subsets, and they have to
        agree on the build or they hit different caches and draw different
        graphs of the same ground.
        """
        args = argparse.Namespace(cache_dir=".cache", ut_routes=CATALOGUE)
        assert Params.from_args(args).stroke_deg == Params(cache_dir=".cache", ut_routes=CATALOGUE).stroke_deg

    def test_something_the_command_line_never_had_is_ignored(self):
        """Test that an unrelated argument does not reach the constructor."""
        args = argparse.Namespace(cache_dir=".cache", ut_routes=CATALOGUE, simplify_m=8.0, output_dir="out")
        assert Params.from_args(args).cache_dir == ".cache"

    def test_an_override_wins_over_both(self):
        """Test that a caller can state a value the command line does not."""
        args = argparse.Namespace(cache_dir=".cache", ut_routes=CATALOGUE, approach_km=5.0)
        assert Params.from_args(args, approach_km=15.0).approach_km == 15.0


class TestJoinValues:
    """Test _join_values."""

    def test_one_route_passes_through(self):
        """Test the ordinary case: a segment belonging to one named route."""
        assert _join_values(pd.Series(["Sjøbergmarsjruta"])) == "Sjøbergmarsjruta"

    def test_a_segment_shared_by_two_routes_carries_both(self):
        """Test what the info table's several rows per segment mean.

        Both are true, and the chain rule reads several identities out of the
        one value it is given.
        """
        assert _join_values(pd.Series(["B", "A"])) == "A / B"

    def test_a_segment_named_twice_is_not_named_twice(self):
        """Test that repeats collapse rather than accumulating."""
        assert _join_values(pd.Series(["A", "A"])) == "A"

    def test_the_separator_is_the_one_the_chain_rule_reads_back(self):
        """Test the agreement two literals could quietly lose.

        Written by hand, a change to the chain rule's separator would leave
        these values unsplittable and silently move where every chain ends.
        """
        joined = _join_values(pd.Series(["A", "B"]))
        assert joined is not None
        assert joined.split(IDENTITY_SEPARATOR) == ["A", "B"]

    def test_an_empty_string_is_not_a_value(self):
        """Test the second way these registers say nothing.

        Taken for a value it joins the ones beside it, so a segment on an easy
        route and one the register said nothing about reads ``" / Easy"``.
        """
        assert _join_values(pd.Series(["", "Easy"])) == "Easy"

    def test_a_segment_belonging_to_no_named_route_says_nothing(self):
        """Test that a chain does not gain an empty identity."""
        assert _join_values(pd.Series([None, pd.NA], dtype="object")) is None


class TestZoneAround:
    """Test zone_around."""

    def test_the_zone_holds_the_area_it_grew_from(self):
        """Test that the interior is kept rather than cut out."""
        area = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (0, 1000), (1000, 1000), (1000, 0)])], crs=METRIC_CRS).to_crs("EPSG:4326")
        zone = zone_around(area, 1.0)
        assert zone.to_crs(METRIC_CRS).geometry.iloc[0].contains(area.to_crs(METRIC_CRS).geometry.iloc[0])

    def test_it_reaches_the_stated_distance(self):
        """Test that the width is the distance asked for, in kilometres."""
        area = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (0, 1000), (1000, 1000), (1000, 0)])], crs=METRIC_CRS).to_crs("EPSG:4326")
        grown = zone_around(area, 2.0).to_crs(METRIC_CRS).total_bounds
        assert grown[0] == pytest.approx(-2000, abs=10)


class TestWithCaptureDate:
    """Test _with_capture_date."""

    def test_a_timestamp_becomes_the_date_a_popup_shows(self):
        """Test the rendering that has to happen before the chains, not after."""
        gdf = gpd.GeoDataFrame({"datafangstdato": pd.to_datetime(["1984-03-01T00:00:00Z"])}, geometry=[LineString([(0, 0), (1, 1)])], crs=METRIC_CRS)
        assert _with_capture_date(gdf, "datafangstdato")[SURVEYED_FIELD].iloc[0] == "1984-03-01"

    def test_a_missing_timestamp_stays_missing(self):
        """Test that nothing is invented where the register recorded nothing."""
        gdf = gpd.GeoDataFrame({"datafangstdato": pd.to_datetime([None])}, geometry=[LineString([(0, 0), (1, 1)])], crs=METRIC_CRS)
        assert pd.isna(_with_capture_date(gdf, "datafangstdato")[SURVEYED_FIELD].iloc[0])

    def test_the_source_column_is_left_alone(self):
        """Test that the register's own value is not overwritten by its rendering."""
        gdf = gpd.GeoDataFrame({"datafangstdato": pd.to_datetime(["1984-03-01T00:00:00Z"])}, geometry=[LineString([(0, 0), (1, 1)])], crs=METRIC_CRS)
        described = _with_capture_date(gdf, "datafangstdato")
        assert pd.api.types.is_datetime64_any_dtype(described["datafangstdato"])


class TestMasksFrom:
    """Test masks_from."""

    def test_every_marked_route_is_in_the_marked_mask(self):
        """Test that membership of Turrutebasen is itself the statement."""
        masks = masks_from(network(Turrutebasen=lines(0, 10)))
        assert len(masks.marked) == 2

    def test_a_path_the_register_calls_waymarked_joins_them(self):
        """Test the second half of the marked mask."""
        masks = masks_from(network(N50_paths=lines(0, 10, marking=("JA", "NEI"))))
        assert len(masks.marked) == 1
        assert len(masks.unmarked) == 1

    def test_a_path_saying_nothing_is_in_neither(self):
        """Test that silence is not a statement either way."""
        masks = masks_from(network(N50_paths=lines(0, marking=(None,))))
        assert len(masks.marked) == 0
        assert len(masks.unmarked) == 0

    def test_the_marking_is_read_however_the_register_spaces_it(self):
        """Test that a stray case or space does not empty the mask silently."""
        masks = masks_from(network(N50_paths=lines(0, 10, marking=(" ja ", "nei"))))
        assert len(masks.marked) == 1
        assert len(masks.unmarked) == 1

    def test_every_recording_source_is_in_the_recorded_mask(self):
        """Test what no_path_recorded is measured against."""
        masks = masks_from(network(FKB=lines(0), N50_paths=lines(10), N50_roads=lines(20), OSM=lines(30)))
        assert len(masks.recorded) == 4

    def test_turrutebasen_is_not_a_record_that_a_path_exists(self):
        """Test that a route register stays out of the recorded mask.

        It suggests a way rather than recording one, and the whole of what
        ``no_path_recorded`` says rests on that distinction.
        """
        assert len(masks_from(network(Turrutebasen=lines(0, 10))).recorded) == 0

    def test_a_marking_that_stopped_being_a_code_is_an_error(self):
        """Test the case that would otherwise empty both masks in silence.

        Every walked edge would come back unknown, and a report full of unknown
        is what this park looks like anyway, so nothing would say so.
        """
        with pytest.raises(ValueError, match="not as JA/NEI"):
            masks_from(network(N50_paths=lines(0, 10, marking=("Merket", "Umerket"))))


class TestEdgeCosts:
    """Test edge_costs."""

    def test_a_walked_source_travels_as_its_factor(self):
        """Test what a browser needs instead of a cost per edge.

        The cost is length times the factor and the length is in the geometry
        already, so what has to travel is six numbers rather than 234,358.
        """
        sources = [NetworkSource("FKB", gpd.GeoDataFrame(geometry=[], crs=METRIC_CRS), cost_factor=1.05)]
        assert edge_costs(sources, params())["FKB"] == {"factor": 1.05}

    def test_a_crossing_travels_as_a_whole_crossing(self):
        """Test the one cost that is not length times anything.

        A crossing is the same decision whether it is 2 km or 20, so nothing
        about its cost can be recovered from its geometry.
        """
        sources = [NetworkSource("Ferries", gpd.GeoDataFrame(geometry=[], crs=METRIC_CRS), kind=FERRY)]
        costs = edge_costs(sources, params(ferry_cost_km=5.0))

        assert costs["Ferries"] == {"flatM": 5000.0}
        assert "factor" not in costs["Ferries"]

    def test_the_connectors_nobody_drew_are_costed_too(self):
        """Test that a bridged edge is not left without a weight."""
        assert edge_costs([], params())[BRIDGE] == {"factor": DEFAULT_BRIDGE_COST_FACTOR}


def params(**overrides: object) -> Params:
    """Build parameters for a build that is never run.

    Args:
        **overrides: Fields to set

    Returns:
        The parameters
    """
    return Params(cache_dir=".cache", ut_routes=CATALOGUE, **overrides)  # type: ignore[arg-type]


def masks() -> Masks:
    """Build a set of masks to fingerprint against.

    Returns:
        Three small masks
    """
    return masks_from(network(Turrutebasen=lines(0), N50_paths=lines(10, marking=("JA",)), FKB=lines(20)))


def source(name: str = "FKB", identity: str | None = "route_name", values: tuple[str | None, ...] = ("A", None)) -> NetworkSource:
    """Build a source whose identity column can be varied.

    Args:
        name: Source name
        identity: Column naming the way, or None
        values: What that column holds

    Returns:
        The source
    """
    gdf = gpd.GeoDataFrame(
        {"route_name": list(values)},
        geometry=[LineString([(0, offset), (100, offset)]) for offset in range(len(values))],
        crs=METRIC_CRS,
    )
    return NetworkSource(name, gdf, identity_field=identity)


class TestFingerprint:
    """Test fingerprint."""

    def test_the_same_inputs_give_the_same_key(self):
        """Test that an unchanged rebuild reads its own cache back."""
        params = Params(cache_dir=".cache", ut_routes=CATALOGUE)
        assert fingerprint([source()], masks(), params) == fingerprint([source()], masks(), params)

    def test_a_parameter_that_shapes_the_graph_moves_it(self):
        """Test that a cached graph cannot answer for other parameters."""
        one = Params(cache_dir=".cache", ut_routes=CATALOGUE)
        other = Params(cache_dir=".cache", ut_routes=CATALOGUE, stroke_deg=30.0)
        assert fingerprint([source()], masks(), one) != fingerprint([source()], masks(), other)

    def test_a_name_arriving_from_another_register_moves_it(self):
        """Test the case the values digest exists for.

        Road names come from SSR and route names from Turrutebasen, so a change
        in either shows up in no source's row count, length or geometry — yet
        it moves where a chain ends.
        """
        params = Params(cache_dir=".cache", ut_routes=CATALOGUE)
        assert fingerprint([source(values=("A", None))], masks(), params) != fingerprint([source(values=("A", "B"))], masks(), params)

    def test_a_name_moving_between_two_rows_moves_it(self):
        """Test that the digest sees position, not only which values are there.

        Dropping a missing value rather than writing a placeholder makes
        ``['A', None]`` and ``[None, 'A']`` hash alike, which is a false cache
        *hit*: the graph is replayed for identities it was not built from.
        """
        params = Params(cache_dir=".cache", ut_routes=CATALOGUE)
        assert fingerprint([source(values=("A", None))], masks(), params) != fingerprint([source(values=(None, "A"))], masks(), params)

    def test_a_source_carrying_nothing_still_has_a_key(self):
        """Test that a source with neither identity nor attributes is handled."""
        params = Params(cache_dir=".cache", ut_routes=CATALOGUE)
        assert fingerprint([source(identity=None)], masks(), params)

    def test_reading_the_ground_differently_moves_it(self):
        """Test that a graph sampled at one step cannot answer for another.

        The invariance the ascent threshold exists for is checked by rebuilding
        at 10 and 15 m and comparing, so a cached 5 m graph served to that
        comparison would have it compare a cache against itself.
        """
        one = Params(cache_dir=".cache", ut_routes=CATALOGUE)
        coarse = Params(cache_dir=".cache", ut_routes=CATALOGUE, elevation_step_m=15.0)
        louder = Params(cache_dir=".cache", ut_routes=CATALOGUE, ascent_threshold_m=10.0)
        assert fingerprint([source()], masks(), one) != fingerprint([source()], masks(), coarse)
        assert fingerprint([source()], masks(), one) != fingerprint([source()], masks(), louder)

"""Tests for grouping a source's lines into chains.

The invariant every one of these protects: a chain is linear. Anything that
would produce a branching selection is a bug, because a branch has no single
sequence to lay an elevation profile along.
"""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, box
from trails.routing.chains import CHAIN_COLUMNS, ChainRule, build_chains, chains_of, split_source
from trails.routing.sources import FERRY, NetworkSource

CRS = "EPSG:25833"


def source(*lines: LineString, name: str = "S", **fields: list[object]) -> NetworkSource:
    """Build a one-off source from bare lines.

    Args:
        *lines: Geometries
        name: Source tag
        **fields: Columns and the network source options they belong to; every
            keyword that is not a column name goes to :class:`NetworkSource`

    Returns:
        The source
    """
    options = {key: value for key, value in fields.items() if not isinstance(value, list)}
    columns = {key: value for key, value in fields.items() if isinstance(value, list)}
    return NetworkSource(name, gpd.GeoDataFrame(columns, geometry=list(lines), crs=CRS), **options)  # type: ignore[arg-type]


class TestSplitSource:
    """Test split_source."""

    def test_lines_crossing_are_cut_at_the_crossing(self):
        """Test that a crossing becomes a piece end on both lines."""
        pieces = split_source(source(LineString([(0, 0), (100, 0)]), LineString([(50, -50), (50, 50)])))
        assert len(pieces) == 4
        assert sorted(pieces.geometry.length) == [50.0] * 4

    def test_lines_that_only_touch_end_to_end_are_not_cut(self):
        """Test that meeting at an end costs nothing."""
        assert len(split_source(source(LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)])))) == 2

    def test_attributes_travel_with_the_pieces(self):
        """Test that a piece knows which feature it came from."""
        pieces = split_source(
            source(LineString([(0, 0), (100, 0)]), LineString([(50, -50), (50, 50)]), typeveg=["sti", "traktorveg"], attributes=("typeveg",))
        )
        assert sorted(pieces["typeveg"]) == ["sti", "sti", "traktorveg", "traktorveg"]

    def test_clipping_happens_before_noding(self):
        """Test that the extent is respected."""
        pieces = split_source(source(LineString([(0, 0), (500, 0)])), box(0, -10, 100, 10))
        assert pieces.geometry.length.sum() == pytest.approx(100.0)

    def test_a_source_naming_a_column_it_does_not_have(self):
        """Test that a mistyped column is caught rather than silently ignored."""
        with pytest.raises(KeyError, match="road_id"):
            split_source(source(LineString([(0, 0), (10, 0)]), identity_field="road_id"))

    def test_pieces_keep_the_geometry_the_source_drew(self):
        """Test that a source noded by a simplified copy still holds its detail."""
        wiggly = LineString([(0, 0), (25, 3), (50, 0), (75, 3), (100, 0), (200, 0)])
        pieces = split_source(source(wiggly, LineString([(50, -50), (50, 50)]), node_simplify_m=10.0))
        assert pieces.geometry.length.sum() == pytest.approx(wiggly.length + 100.0)


class TestChainRules:
    """Test how pieces are joined back together at a junction."""

    def test_a_crossing_is_not_a_branch(self):
        """Test that two lines crossing stay two lines."""
        crossing = source(LineString([(0, 0), (100, 0)]), LineString([(50, -50), (50, 50)]))
        assert sorted(chains_of(crossing)["length_m"]) == [100.0, 100.0]

    def test_breaking_at_every_junction_is_the_baseline(self):
        """Test that the junction rule is what linemerge alone would give."""
        crossing = source(LineString([(0, 0), (100, 0)]), LineString([(50, -50), (50, 50)]))
        assert len(chains_of(crossing, rule=ChainRule.JUNCTION)) == 4

    def test_a_side_arm_starts_its_own_chain(self):
        """Test that the way carries on and what joins it does not."""
        tee = source(LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)]), LineString([(50, 0), (50, 50)]))
        assert sorted(chains_of(tee)["length_m"]) == [50.0, 100.0]

    def test_nothing_within_the_angle_ends_every_arm(self):
        """Test that arms meeting at a wide angle are not joined by force."""
        # Three arms 120 degrees apart: every pairing deflects by 60.
        star = source(LineString([(0, 0), (0, 50)]), LineString([(0, 0), (-43, -25)]), LineString([(0, 0), (43, -25)]))
        assert len(chains_of(star, stroke_angle_deg=45.0)) == 3
        assert len(chains_of(star, stroke_angle_deg=60.0)) == 2

    def test_the_angle_is_read_only_at_the_junction(self):
        """Test that a way bending along its own course stays one chain.

        A road can climb a hillside in hairpins and remain one road: there is no
        junction there, so there is nothing to decide.
        """
        hairpins = source(LineString([(0, 0), (100, 0), (0, 20), (100, 40)]))
        assert len(chains_of(hairpins)) == 1

    def test_two_arms_meeting_are_joined_whatever_the_angle(self):
        """Test that a sharp bend between two pieces is not a junction."""
        bend = source(LineString([(0, 0), (50, 0)]), LineString([(50, 0), (55, 50)]))
        assert len(chains_of(bend)) == 1

    def test_a_source_that_records_a_height_is_read_in_the_plane(self):
        """Test that a third dimension neither crashes nor bends the angle.

        A GPX track carries its elevation on the geometry, and a deflection
        measured through it is not the angle anyone sees on the map.
        """
        tee = source(
            LineString([(0, 0, 100), (50, 0, 400)]),
            LineString([(50, 0, 400), (100, 0, 100)]),
            LineString([(50, 0, 400), (50, 50, 400)]),
        )
        assert sorted(round(length) for length in chains_of(tee)["length_m"]) == [50, 100]


class TestIdentity:
    """Test the rule that decides before the geometry does."""

    def test_a_named_way_turns_where_its_name_turns(self):
        """Test the case the angle rule gets wrong on its own.

        A road turning ninety degrees at a junction while a different road runs
        straight on: the angle follows the wrong one, the name turns correctly.
        """
        crossroads = source(
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (50, 50)]),
            LineString([(50, 0), (100, 0)]),
            LineString([(50, 0), (50, -50)]),
            road=["R1", "R1", "R2", "R2"],
            identity_field="road",
        )
        chains = chains_of(crossroads)
        assert sorted(chains["identity"]) == ["R1", "R2"]
        assert sorted(chains["length_m"]) == [100.0, 100.0]

    def test_a_way_that_divides_ends_there(self):
        """Test that three arms of one road have no single continuation."""
        fork = source(
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
            LineString([(50, 0), (50, 50)]),
            road=["R", "R", "R"],
            identity_field="road",
        )
        assert len(chains_of(fork)) == 3

    def test_an_arm_with_no_counterpart_falls_through_to_the_geometry(self):
        """Test that a name nothing else carries does not end a chain."""
        named = source(
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
            LineString([(50, 0), (50, 50)]),
            road=["R", None, None],
            identity_field="road",
        )
        assert sorted(chains_of(named)["length_m"]) == [50.0, 100.0]

    def test_a_column_that_says_nothing_the_nullable_way_still_says_nothing(self):
        """Test the one missing value that is neither None nor a nan.

        A source that reads its text as pandas' ``string`` dtype — Turrutebasen
        does, throughout — writes ``pd.NA`` where it has no name. Taken for a
        value it becomes the text ``<NA>``, and then every unnamed line in the
        source shares one identity: measured on this network, that turned three
        arms of nothing-in-particular into a way that divides and put 2,713
        chains onto FKB that are not there.
        """
        lines = [LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)]), LineString([(50, 0), (50, 50)])]
        frame = gpd.GeoDataFrame({"road": pd.array(["R", None, None], dtype="string")}, geometry=lines, crs=CRS)
        named = NetworkSource("S", frame, identity_field="road")

        assert frame["road"].isna().sum() == 2, "the fixture has to hold the value it is about"
        assert sorted(chains_of(named)["length_m"]) == [50.0, 100.0]

    def test_several_identities_in_one_value_are_read_apart(self):
        """Test a segment belonging to two routes, as the layers write them."""
        shared = source(
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
            LineString([(50, 0), (50, 50)]),
            route=["A / B", "A", "B"],
            identity_field="route",
        )
        # The arriving segment carries both routes and each continues into a
        # different arm: it divides, so its chain ends. The other two are left
        # to the geometry, and at right angles it joins neither.
        assert len(chains_of(shared)) == 3

    def test_an_arm_whose_only_candidate_divides_falls_through_to_the_geometry(self):
        """Test that a decision about one arm does not silently end another.

        The arm carrying two route names is the only candidate of each of them
        and the continuation of neither. What it leaves without a partner has no
        identity left to follow, so the angle decides it — rather than it
        inheriting a verdict reached about a different arm.
        """
        junction = source(
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
            LineString([(50, 0), (50, 50)]),
            route=["X", "Y", "X / Y"],
            identity_field="route",
        )
        # X and Y run straight through each other; the arm that divides is not
        # part of either chain.
        assert sorted(chains_of(junction)["length_m"]) == [50.0, 100.0]


class TestChainGeometry:
    """Test what a finished chain looks like."""

    def test_a_chain_that_closes_on_itself_is_still_one_chain(self):
        """Test a loop road, which has no two ends to speak of."""
        ring = source(LineString([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]))
        chains = chains_of(ring)
        assert len(chains) == 1
        assert chains.geometry.iloc[0].is_closed
        assert chains["length_m"].iloc[0] == pytest.approx(400.0)

    def test_a_chain_spans_the_pieces_it_was_built_from(self):
        """Test that joining loses no length."""
        run = source(LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)]), LineString([(100, 0), (100, 100)]))
        assert chains_of(run)["length_m"].sum() == pytest.approx(200.0)

    def test_values_that_differ_along_a_chain_are_both_kept(self):
        """Test that a run changing character says so rather than picking one."""
        mixed = source(
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
            typeveg=["traktorveg", "sti"],
            attributes=("typeveg",),
        )
        assert chains_of(mixed)["typeveg"].tolist() == ["sti / traktorveg"]

    def test_a_value_constant_along_a_chain_passes_through(self):
        """Test that agreement is not turned into a list."""
        same = source(LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)]), typeveg=["sti", "sti"], attributes=("typeveg",))
        assert same.gdf is not None and chains_of(same)["typeveg"].tolist() == ["sti"]

    def test_a_register_writing_nothing_as_an_empty_string_is_read_as_nothing(self):
        """Test the other way these sources say nothing.

        A blank is not a value: joined with the piece beside it a chain would
        read ``" / sti"``, and the column would report itself populated where it
        holds 3-6 %, which is how FKB's sparse fields once read as complete.
        """
        blank = source(
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
            typeveg=["", "sti"],
            attributes=("typeveg",),
        )
        assert chains_of(blank)["typeveg"].tolist() == ["sti"]

    def test_an_attribute_the_source_leaves_empty_stays_empty(self):
        """Test that a column of nothing is not filled with the word for nothing.

        Turrutebasen writes ``pd.NA`` on the 88 % of its segments that record no
        signage. Read as a value it becomes the text ``<NA>``, and the column
        then reports itself fully populated while saying nothing at all.
        """
        frame = gpd.GeoDataFrame({"signage": pd.array([None], dtype="string")}, geometry=[LineString([(0, 0), (50, 0)])], crs=CRS)
        chains = chains_of(NetworkSource("S", frame, attributes=("signage",)))
        assert chains["signage"].isna().tolist() == [True]

    def test_the_frame_carries_the_columns_it_promises(self):
        """Test the shape of the result."""
        chains = chains_of(source(LineString([(0, 0), (50, 0)]), typeveg=["sti"], attributes=("typeveg",)))
        assert list(chains.columns) == [*CHAIN_COLUMNS, "typeveg", "geometry"]

    def test_the_source_and_kind_are_recorded(self):
        """Test that a chain knows what it came from."""
        chains = chains_of(source(LineString([(0, 0), (50, 0)]), name="N50", kind=FERRY))
        assert chains["source"].tolist() == ["N50"] and chains["kind"].tolist() == [FERRY]


class TestChainIds:
    """Test the ids that key the elevation cache, the highlight and the search."""

    def test_ids_are_unique(self):
        """Test that two chains never share an id."""
        chains = chains_of(source(LineString([(0, 0), (100, 0)]), LineString([(0, 50), (100, 50)]), LineString([(0, 90), (100, 90)])))
        assert len(set(chains["chain_id"])) == len(chains)

    def test_ids_do_not_depend_on_the_order_the_source_arrives_in(self):
        """Test what the whole canonical orientation exists for.

        A re-downloaded source can deliver the same lines in a different order.
        An id that shifted with it would churn the elevation cache, the
        highlight and the search for work that did not change.
        """
        lines = [LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)]), LineString([(50, 0), (50, 50)])]
        forwards = chains_of(source(*lines))
        backwards = chains_of(source(*reversed(lines)))
        assert sorted(forwards["chain_id"]) == sorted(backwards["chain_id"])

    def test_ids_do_not_depend_on_the_direction_a_line_was_drawn_in(self):
        """Test that reversing a source's geometry renames nothing."""
        forwards = chains_of(source(LineString([(0, 0), (30, 40)])))
        backwards = chains_of(source(LineString([(30, 40), (0, 0)])))
        assert forwards["chain_id"].tolist() == backwards["chain_id"].tolist()

    def test_a_collision_is_broken_by_the_shape_and_not_by_the_order(self):
        """Test the ids of two chains that agree on everything the id records.

        They start at one rounded point and run the same rounded distance, so
        the id has to reach for something else the geometry owns. Numbering them
        as they came out would put the traversal order straight back into the id.
        """
        one = LineString([(0, 0), (30, 40)])
        other = LineString([(0, 0), (30, -40)])
        forwards = chains_of(source(one, other))
        backwards = chains_of(source(other, one))

        assert forwards["chain_id"].is_unique
        assert sorted(forwards["chain_id"]) == sorted(backwards["chain_id"])
        assert dict(zip(forwards.geometry.apply(str), forwards["chain_id"], strict=True)) == dict(
            zip(backwards.geometry.apply(str), backwards["chain_id"], strict=True)
        )

    def test_ids_of_two_sources_do_not_collide(self):
        """Test that the source tag keeps two datasets apart."""
        line = LineString([(0, 0), (100, 0)])
        assert chains_of(source(line, name="FKB"))["chain_id"].iloc[0] != chains_of(source(line, name="N50"))["chain_id"].iloc[0]

    def test_an_unrelated_edit_elsewhere_leaves_an_id_alone(self):
        """Test that a chain survives a change to a different part of the map."""
        untouched = LineString([(0, 0), (100, 0)])
        before = chains_of(source(untouched, LineString([(0, 500), (100, 500)])))
        after = chains_of(source(untouched, LineString([(0, 500), (100, 500), (100, 600)])))
        assert before["chain_id"].iloc[0] in set(after["chain_id"])


class TestKeepWhole:
    """Test the sources that publish whole routes."""

    def test_published_routes_are_not_decomposed(self):
        """Test that overlapping trips stay trips.

        Noding UT.no's 35 routes against each other shatters them into 2,411
        scraps, because they share long stretches. A trip is already linear and
        already the unit a reader means.
        """
        overlapping = source(
            LineString([(0, 0), (100, 0), (200, 0)]),
            LineString([(50, 0), (150, 0)]),
            keep_whole=True,
        )
        assert sorted(chains_of(overlapping)["length_m"]) == [100.0, 200.0]

    def test_a_published_route_is_still_cut_to_the_extent(self):
        """Test that keeping a route whole does not mean keeping all of it."""
        trip = source(LineString([(0, 0), (500, 0)]), keep_whole=True)
        assert chains_of(trip, box(0, -10, 100, 10))["length_m"].tolist() == [100.0]

    def test_a_published_route_carries_its_attributes(self):
        """Test that the columns survive the shortcut."""
        trip = source(LineString([(0, 0), (100, 0)]), keep_whole=True, route=["Sjøbergmarsjruta"], identity_field="route")
        assert chains_of(trip)["identity"].tolist() == ["Sjøbergmarsjruta"]


class TestEmptySource:
    """Test a source with nothing in it."""

    def test_no_lines_at_all(self):
        """Test that an empty source is not an error."""
        empty = NetworkSource("S", gpd.GeoDataFrame({"typeveg": []}, geometry=[], crs=CRS), attributes=("typeveg",))
        chains = chains_of(empty)
        assert chains.empty
        assert list(chains.columns) == [*CHAIN_COLUMNS, "typeveg", "geometry"]

    def test_nothing_inside_the_extent(self):
        """Test that clipping everything away is not an error."""
        assert chains_of(source(LineString([(0, 0), (10, 0)])), box(500, 500, 600, 600)).empty


class TestBuildChains:
    """Test the pure step, over pieces someone else noded."""

    def test_pieces_can_be_chained_twice_under_different_rules(self):
        """Test that the two rules can be compared without noding twice."""
        crossing = source(LineString([(0, 0), (100, 0)]), LineString([(50, -50), (50, 50)]))
        pieces = split_source(crossing)
        assert len(build_chains(pieces, crossing, rule=ChainRule.JUNCTION)) == 4
        assert len(build_chains(pieces, crossing, rule=ChainRule.STROKE)) == 2

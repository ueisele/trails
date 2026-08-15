"""Tests for the merged routing graph."""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, box
from trails.routing.graph import EDGE_COLUMNS, build_network, label_components
from trails.routing.sources import BRIDGE, FERRY, PATH, NetworkSource

CRS = "EPSG:25833"


def source(*lines: LineString, name: str = "S", **options: object) -> NetworkSource:
    """Build a one-off source from bare lines.

    Args:
        *lines: Geometries
        name: Source tag
        **options: Passed to :class:`NetworkSource`

    Returns:
        The source
    """
    return NetworkSource(name, gpd.GeoDataFrame(geometry=list(lines), crs=CRS), **options)  # type: ignore[arg-type]


class TestEdges:
    """Test what the graph is cut into."""

    def test_two_sources_crossing_meet_at_one_node(self):
        """Test the point of merging: a crossing is routable in both directions."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), name="A"), source(LineString([(50, -50), (50, 50)]), name="B")])

        assert len(network.edges) == 4
        shared = set(network.edges["from_node"]) & set(network.edges["to_node"])
        assert len(shared) == 1

    def test_every_edge_names_the_chain_it_lies_on(self):
        """Test the link between the drawn unit and the routable one."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), name="A"), source(LineString([(50, -50), (50, 50)]), name="B")])
        walkable = network.edges[network.edges["kind"] != BRIDGE]
        assert set(walkable["chain_id"]) <= set(network.chains["chain_id"])

    def test_edges_cover_the_chains_they_came_from(self):
        """Test that cutting the network loses nothing."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), name="A"), source(LineString([(50, -50), (50, 50)]), name="B")])
        assert network.edges["length_m"].sum() == pytest.approx(network.chains["length_m"].sum())

    def test_the_frame_carries_the_columns_it_promises(self):
        """Test the shape of the result."""
        network = build_network([source(LineString([(0, 0), (100, 0)]))])
        assert list(network.edges.columns) == [*EDGE_COLUMNS, "geometry", "component"]

    def test_nodes_know_their_degree(self):
        """Test that a junction is visible as one."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), name="A"), source(LineString([(50, -50), (50, 50)]), name="B")])
        assert sorted(network.nodes["degree"]) == [1, 1, 1, 1, 4]

    def test_a_clip_applies_to_every_source(self):
        """Test that the extent is the caller's to choose."""
        network = build_network([source(LineString([(0, 0), (500, 0)]))], box(0, -10, 100, 10))
        assert network.edges["length_m"].sum() == pytest.approx(100.0)

    def test_sources_must_be_named_apart(self):
        """Test that two sources of one name are refused rather than merged."""
        with pytest.raises(ValueError, match="unique"):
            build_network([source(LineString([(0, 0), (10, 0)]), name="A"), source(LineString([(0, 5), (10, 5)]), name="A")])

    def test_a_network_needs_a_source(self):
        """Test that an empty build is an error, not an empty graph."""
        with pytest.raises(ValueError, match="at least one"):
            build_network([])


class TestCost:
    """Test the weights a route is found over."""

    def test_cost_is_length_times_the_source_factor(self):
        """Test where priority lives: in the weight, not in the geometry."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), cost_factor=1.3)])
        assert network.edges["cost"].iloc[0] == pytest.approx(130.0)

    def test_a_better_source_is_cheaper_over_the_same_ground(self):
        """Test that a route prefers the better-surveyed of two parallel lines."""
        network = build_network(
            [
                source(LineString([(0, 0), (100, 0)]), name="UT.no", cost_factor=1.00),
                source(LineString([(0, 8), (100, 8)]), name="N50", cost_factor=1.30),
            ]
        )
        costs = network.edges.groupby("source")["cost"].sum()
        assert costs["UT.no"] < costs["N50"]

    def test_no_line_is_cut_away_for_a_better_one(self):
        """Test the decision the whole design rests on.

        Merging the sources by priority was measured and is wrong: cutting the
        lower-priority line away removes the redundancy that carries the network
        across the gaps in any one dataset.
        """
        network = build_network(
            [
                source(LineString([(0, 0), (100, 0)]), name="UT.no", cost_factor=1.00),
                source(LineString([(0, 8), (100, 8)]), name="N50", cost_factor=1.30),
            ],
            bridge_m=0.0,
        )
        assert set(network.edges["source"]) == {"UT.no", "N50"}
        assert network.edges["length_m"].sum() == pytest.approx(200.0)


class TestFerries:
    """Test the edges nobody walks."""

    def test_a_crossing_costs_the_same_whatever_its_length(self):
        """Test that a crossing is one decision, not a distance."""
        short = build_network([source(LineString([(0, 0), (2000, 0)]), kind=FERRY)], ferry_cost_m=5000.0)
        long = build_network([source(LineString([(0, 0), (20000, 0)]), kind=FERRY)], ferry_cost_m=5000.0)
        assert short.edges["cost"].sum() == pytest.approx(long.edges["cost"].sum()) == pytest.approx(5000.0)

    def test_a_crossing_cut_in_two_still_costs_one_crossing(self):
        """Test that the flat cost survives the crossing being noded."""
        network = build_network(
            [
                source(LineString([(0, 0), (2000, 0)]), name="F", kind=FERRY),
                source(LineString([(1000, -50), (1000, 50)]), name="P"),
            ],
            ferry_cost_m=5000.0,
        )
        assert network.edges.loc[network.edges["kind"] == FERRY, "cost"].sum() == pytest.approx(5000.0)

    def test_a_ferry_edge_is_marked_as_one_from_the_start(self):
        """Test that everything downstream can keep it out of a walking figure."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), name="P"), source(LineString([(100, 0), (2000, 0)]), name="F", kind=FERRY)])
        walking = network.edges[network.edges["kind"] == PATH]
        assert walking["length_m"].sum() == pytest.approx(100.0)

    def test_a_ferry_is_what_makes_the_far_side_reachable(self):
        """Test the measured reason they are in the graph at all."""
        west = LineString([(0, 0), (100, 0)])
        east = LineString([(3000, 0), (3100, 0)])
        crossing = LineString([(100, 0), (3000, 0)])

        land = build_network([source(west, east, name="L")])
        with_ferry = build_network([source(west, east, name="L"), source(crossing, name="F", kind=FERRY)])

        assert land.edges["component"].nunique() == 2
        assert with_ferry.edges["component"].nunique() == 1


class TestBridging:
    """Test what happens where the sources disagree about where a way stops."""

    def test_a_gap_within_reach_is_joined(self):
        """Test that a few metres of disagreement is not a dead end."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), LineString([(110, 0), (200, 0)]))], bridge_m=25.0)
        assert network.edges["component"].nunique() == 1

    def test_a_gap_beyond_reach_is_left_alone(self):
        """Test that the network is not joined up on speculation."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), LineString([(110, 0), (200, 0)]))], bridge_m=5.0)
        assert network.edges["component"].nunique() == 2

    def test_a_loose_end_reaches_the_middle_of_an_edge(self):
        """Test the case that decides the component count.

        A path rarely stops at a road's *node*. It stops beside its middle, and
        a connector that could only reach nodes left a thousand of them
        stranded here.
        """
        network = build_network(
            [
                source(LineString([(0, 0), (200, 0)]), name="Road"),
                source(LineString([(100, 10), (100, 80)]), name="Path"),
            ],
            bridge_m=25.0,
        )
        assert network.edges["component"].nunique() == 1
        assert network.edges.loc[network.edges["source"] == "Road", "length_m"].tolist() == [100.0, 100.0]

    def test_a_dead_end_two_sources_both_draw_is_still_a_dead_end(self):
        """Test the case counting edges at a node passes over.

        Where two sources draw the same dead end, their chains stop at one node
        and it carries two edges — but nothing continues through it, and the
        path 10 m further on is as unreachable as if only one source had drawn
        it.
        """
        stub = LineString([(0, 0), (100, 0)])
        network = build_network(
            [
                source(stub, name="FKB"),
                source(LineString([(0, 0), (50, 1), (100, 0)]), name="N50"),
                source(LineString([(110, 0), (200, 0)]), name="OSM"),
            ],
            bridge_m=25.0,
        )
        assert network.edges["component"].nunique() == 1

    def test_a_connector_belongs_to_no_chain(self):
        """Test that nothing drawn is invented: no source drew this."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), LineString([(110, 0), (200, 0)]))], bridge_m=25.0)
        bridges = network.edges[network.edges["kind"] == BRIDGE]
        assert len(bridges) == 1
        assert bridges["chain_id"].isna().all()

    def test_a_connector_is_not_the_cheapest_way_round(self):
        """Test that a route does not seek out a connection nobody surveyed."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), LineString([(110, 0), (200, 0)]))], bridge_m=25.0, bridge_cost_factor=1.3)
        bridge = network.edges[network.edges["kind"] == BRIDGE].iloc[0]
        assert bridge["cost"] > bridge["length_m"]

    def test_splitting_an_edge_keeps_its_chain_and_its_cost(self):
        """Test that a bridged edge is still the chain it was."""
        network = build_network(
            [
                source(LineString([(0, 0), (200, 0)]), name="Road", cost_factor=1.3),
                source(LineString([(100, 10), (100, 80)]), name="Path"),
            ],
            bridge_m=25.0,
        )
        road = network.edges[network.edges["source"] == "Road"]
        assert road["chain_id"].nunique() == 1
        assert road["cost"].sum() == pytest.approx(260.0)


class TestComponents:
    """Test what hangs together with what."""

    def test_the_longest_component_comes_first(self):
        """Test that component 0 is the one a traverse can be planned over."""
        network = build_network([source(LineString([(0, 0), (1000, 0)]), LineString([(0, 500), (100, 500)]))], bridge_m=0.0)
        longest = network.edges[network.edges["component"] == 0]
        assert longest["length_m"].sum() == pytest.approx(1000.0)

    def test_components_can_be_counted_over_a_subset(self):
        """Test asking what the network looks like without the crossings."""
        network = build_network(
            [
                source(LineString([(0, 0), (100, 0)]), LineString([(3000, 0), (3100, 0)]), name="L"),
                source(LineString([(100, 0), (3000, 0)]), name="F", kind=FERRY),
            ]
        )
        walking = network.edges[network.edges["kind"] != FERRY]
        assert network.edges["component"].nunique() == 1
        assert label_components(walking).nunique() == 2

    def test_a_node_carries_the_component_of_its_edges(self):
        """Test that the nodes can be asked the same question as the edges."""
        network = build_network([source(LineString([(0, 0), (100, 0)]), LineString([(0, 500), (100, 500)]))], bridge_m=0.0)
        assert set(network.nodes["component"]) == {0, 1}

    def test_no_edges_at_all(self):
        """Test that an empty subset is not an error."""
        empty = gpd.GeoDataFrame({"from_node": [], "to_node": [], "length_m": []}, geometry=[], crs=CRS)
        assert label_components(empty).empty


class TestNodingGeometry:
    """Test noding a dense track by a simplified copy of it."""

    def test_the_edge_keeps_the_geometry_the_source_drew(self):
        """Test that simplifying for the noding does not simplify the result."""
        wiggly = LineString([(0, 0), (25, 4), (50, 0), (75, 4), (100, 0), (200, 0)])
        network = build_network(
            [
                source(wiggly, name="UT.no", node_simplify_m=10.0),
                source(LineString([(150, -50), (150, 50)]), name="P"),
            ]
        )
        drawn = network.edges[network.edges["source"] == "UT.no"]
        assert drawn["length_m"].sum() == pytest.approx(wiggly.length)

    def test_a_track_that_doubles_back_is_cut_where_it_should_be(self):
        """Test the trap in mapping positions back onto the full geometry.

        Projecting a position found on the simplified copy reports the *first*
        of the two times the track passes it, so every cut on the return leg
        used to land on the outbound one — up to ninety metres away.
        """
        out_and_back = LineString([(0, 0), (100, 0), (200, 0), (200, 1), (100, 1), (0, 1)])
        network = build_network(
            [
                source(out_and_back, name="UT.no", node_simplify_m=5.0),
                source(LineString([(100, -50), (100, 50)]), name="P"),
            ],
            bridge_m=0.0,
        )

        track = network.edges[network.edges["source"] == "UT.no"]
        assert track["length_m"].sum() == pytest.approx(out_and_back.length)
        # Both passes are cut, and each piece starts near where its node sits —
        # not at the far end of the track, which is what projecting back gave.
        for edge in track.itertuples():
            start = network.nodes.geometry.iloc[edge.from_node]
            assert edge.geometry.distance(start) < 1.0

    def test_a_node_sits_where_one_of_its_edges_begins(self):
        """Test that a node is somewhere on the network, not beside it.

        Its identity comes from the simplified copy the chains were noded by,
        which wanders either side of the line the source drew. Its position must
        not, or anything snapping to it lands off the path.
        """
        # The crossing has to fall on a wiggle, where the simplified copy and the
        # line the source drew genuinely part company. Put it on the straight
        # tail instead and the two coincide there, the displacement is zero, and
        # the bound below passes while testing nothing.
        wiggly = LineString([(0, 0), (25, 6), (50, 0), (75, 6), (100, 0), (200, 0)])
        network = build_network(
            [
                source(wiggly, name="UT.no", node_simplify_m=10.0),
                source(LineString([(37, -50), (37, 50)]), name="P"),
            ],
            bridge_m=0.0,
        )

        # The tolerance a chain was noded at bounds how far its node may sit from
        # it, and nothing may exceed it. Exempting the simplified source instead
        # would leave the one number this costs entirely untested.
        bound = {"UT.no": 10.0, "P": 1e-6}
        worst = 0.0
        for edge in network.edges.itertuples():
            for node, end in ((edge.from_node, 0.0), (edge.to_node, edge.length_m)):
                displacement = network.nodes.geometry.iloc[node].distance(edge.geometry.interpolate(end))
                assert displacement <= bound[edge.source]
                worst = max(worst, displacement)

        # And the case is real, so the bound cannot quietly go vacuous again.
        assert worst > 1.0

        # The crossing itself is exact: the node lands on the path that was
        # noded as it was drawn.
        crossing = network.edges[network.edges["source"] == "P"]
        for edge in crossing.itertuples():
            assert network.nodes.geometry.iloc[edge.from_node].distance(edge.geometry) < 1e-6

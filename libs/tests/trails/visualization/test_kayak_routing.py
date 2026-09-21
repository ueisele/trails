"""Execute the page's searches on small graphs with known alternatives."""

import json
import re
import shutil
import subprocess
from importlib.resources import files

import pytest


@pytest.fixture(scope="module")
def readings():
    """Read production JavaScript in Node, with only the page and geometry supplied."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the routing checks")
    source = files("trails.visualization").joinpath("js", "plan_mode.js").read_text()
    names = (
        "kayak",
        "paddle",
        "router",
        "allowed",
        "endsOf",
        "flipCut",
        "routeBetween",
        "joinedRoute",
        "leavingAt",
        "priced",
        "cheapestMetre",
        "openWaterFactor",
        "edgeIndex",
        "nearestOnNetwork",
        "snapped",
        "blankTally",
        "addProtected",
        "tallyEdge",
    )
    functions = []
    for name in names:
        match = re.search(rf"^            function {name}\([^\n]*\) \{{(?:[^\n]*\}}$|.*?^            \}})", source, re.M | re.S)
        assert match is not None, name
        functions.append(match[0])
    heap = source[source.index("            function Heap()") : source.index("            // Dijkstra over the weighted graph")]
    script = (
        r"""
        var routing = null, gridded = null, paddling = true, paths = false;
        var points = [], goalAt = null, refreshes = 0;
        const storage = new Map();
        const window = {localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}};
        function keptKey() { return 'fixture'; }
        function refresh() { refreshes++; }
        function refreshGoal() {}
        var CROSSING = 'ferry', CONNECTOR = 'bridge', PADDLE = 'paddle', NODE_FIRST_M = 2;
        var PLAN = {portageFactor:4, offPathFactor:3, waterFactor:30, indexCellM:100, snapM:150};
        var MARKING = ['marked', 'unmarked', 'unknown'];
        var TALLIED = MARKING.concat(['undrawn', 'recorded', 'unrecorded']);
        function offPath() { return paths ? 10 : PLAN.offPathFactor; }
        function panel() { return {metresBetween:(x,y,a,b) => Math.hypot(x-a,y-b)*100000}; }
        function graph(kind, directed) {
            routing = null; gridded = null;
            return {header:{edges:1,nodes:2,chains:1,sources:[{name:'Open water',kind:'paddle',factor:1.5},
                {name:'test',kind:kind,factor:1, ...(kind==='ferry'?{flatM:5000}:{})}]},
                coordinates:new Float64Array([0,0,0.0002,0]), vertexAt:[0,2], chainAt:[0,1],
                fromNode:[0],toNode:[1],sources:[1],oneWay:[directed?1:0],
                nodeLon:[0,0.0002],nodeLat:[0,0], water:{cellM:1},waterAt:()=>true,
                nearestNode:()=>0};
        }
    """
        + "\n".join(functions)
        + heap
        + r"""
        var g = graph('paddle', true), out = {};
        const at = (node) => ({node,lon:g.nodeLon[node],lat:g.nodeLat[node]});
        out.forward = routeBetween(g,at(0),at(1));
        const originalTable = router(g);
        paddle(false);
        out.dropped = routing === null;
        out.walkTableDifferent = router(g) !== originalTable;
        paddle(true);
        out.persisted = storage.get('fixture.kayak');
        out.reverse = routeBetween(g,at(1),at(0));
        out.joinedForward = joinedRoute(g,at(0),at(1));
        out.joinedReverse = joinedRoute(g,at(1),at(0));
        const middle = {node:-1,edge:0,along:10,lon:0.0001,lat:0};
        out.exits = endsOf(g,middle);
        out.entries = endsOf(g,middle,true);
        out.halfForward = routeBetween(g,middle,at(1));
        out.halfReverse = routeBetween(g,middle,at(0));
        out.cutForward = routeBetween(g,{...middle,along:5},{...middle,along:15});
        out.cutReverse = routeBetween(g,{...middle,along:15},{...middle,along:5});
        out.walking = [];
        for (const staying of [false,true]) {
            paddle(false); paths = staying; routing = null;
            out.walking.push({reachable:Number.isFinite(router(g).cost[0]),
                route:routeBetween(g,at(0),at(1)),ends:endsOf(g,middle),
                line:nearestOnNetwork(g,0,0.0001,1),tap:snapped(g,0,0,1)});
        }
        paddle(true); paths = false; routing = null;
        out.kayakLine = nearestOnNetwork(g,0,0.0001,1);
        out.kayakTap = snapped(g,0,0,1);
        g = graph('path',false);
        out.portage = router(g).cost[0];
        g = graph('ferry',false);
        out.ferryKayak = router(g).cost[0];
        paddle(false); routing = null;
        out.ferryWalk = router(g).cost[0];
        paddle(true);
        g = graph('paddle',false);
        const from = {node:-1,lon:-0.0001,lat:0}, to = {node:-1,lon:0.0003,lat:0};
        out.floorRoute = joinedRoute(g,from,to);
        out.floorCost = router(g).best[0] + priced(g,from.lon,0,0,0);
        out.directCost = priced(g,from.lon,0,to.lon,0);
        const correctFloor = cheapestMetre;
        cheapestMetre = () => offPath();
        out.oldFloorRoute = joinedRoute(g,from,to);
        cheapestMetre = correctFloor;
        out.floor = cheapestMetre(g);
        g.header.sources[0].factor = 2;
        out.patchedFloor = cheapestMetre(g);
        out.patchedWater = priced(g,0,0,0.0002,0);
        out.tallies = {};
        for (const kind of ['paddle', 'ferry', 'path']) {
            g = graph(kind, false);
            g.header.protected = [{id:'reserve'}];
            g.protectedAt = [0,1]; g.protectedArea = [0]; g.protectedShare = [1];
            g.header.waymarked = [null]; g.waymarked = [0];
            const tally = blankTally();
            try { tallyEdge(tally,g,0,router(g).length[0]); out.tallies[kind] = tally; }
            catch (error) { out.tallies[kind] = {error:error.message}; }
        }
        console.log(JSON.stringify(out));
    """
    )
    result = subprocess.run([node, "-"], input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_both_searches_obey_journey_direction(readings):
    assert readings["forward"]["edges"] == [0]
    assert readings["joinedForward"]["over"]["edges"] == [0]
    assert readings["reverse"] is None
    assert readings["joinedReverse"] is None


def test_paddling_counts_its_source_and_protection_without_waymarking(readings):
    paddle = readings["tallies"]["paddle"]
    ferry = readings["tallies"]["ferry"]
    assert paddle["sources"] == ferry["sources"] == {"test": readings["forward"]["cost"]}
    assert paddle["protected"] == {"reserve": readings["forward"]["cost"]}
    assert ferry["protected"] == {}
    for kind in (paddle, ferry):
        assert all(kind[field] == 0 for field in ("marked", "unmarked", "unknown", "undrawn", "recorded", "unrecorded"))
    assert "never asked about" in readings["tallies"]["path"]["error"]


def test_an_interior_point_does_not_turn_a_stream_into_a_junction(readings):
    assert [end["node"] for end in readings["exits"]] == [1]
    assert [end["node"] for end in readings["entries"]] == [0]
    assert readings["halfForward"]["cost"] == readings["forward"]["cost"] / 2
    assert readings["cutForward"]["cost"] == readings["forward"]["cost"] / 2
    assert readings["halfReverse"] is None
    assert readings["cutReverse"] is None


def test_walking_cannot_route_or_snap_to_water(readings):
    for walk in readings["walking"]:
        assert walk["reachable"] is False
        assert walk["route"] is None
        assert walk["ends"] == []
        assert walk["line"] is None
        assert walk["tap"]["node"] == -1
        assert "edge" not in walk["tap"]
    assert readings["kayakLine"]["edge"] == 0
    assert readings["kayakTap"]["node"] == 0


def test_portage_scales_walking_and_leaves_the_flat_ferry_alone(readings):
    assert readings["portage"] == readings["forward"]["cost"] * 4
    assert readings["ferryKayak"] == readings["ferryWalk"]


def test_a_water_connector_is_not_pruned_as_ground(readings):
    assert readings["floorRoute"]["over"]["edges"] == [0]
    assert readings["oldFloorRoute"] is None
    assert readings["floorCost"] < readings["directCost"]
    assert readings["patchedFloor"] > readings["floor"]


def test_switching_rebuilds_prices_and_remembers_the_mode(readings):
    assert readings["dropped"] is True
    assert readings["walkTableDifferent"] is True
    assert readings["persisted"] == "yes"

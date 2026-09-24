"""Keep paddled metres in the profile and track, and out of the foot total."""

import json
import re
import shutil
import subprocess
from importlib.resources import files

import pytest


@pytest.fixture(scope="module")
def parts():
    """Execute the production composers with a small shoreline and river."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the part checks")
    source = files("trails.visualization").joinpath("js", "plan_mode.js").read_text()
    names = ("routedParts", "cutPart", "straightParts", "composeRoute", "blankTally", "addTally")
    functions = []
    for name in names:
        match = re.search(rf"^            function {name}\([^\n]*\) \{{.*?^            \}}", source, re.M | re.S)
        assert match is not None, name
        functions.append(match[0])
    script = (
        r"""
        var paddling = true, CROSSING = 'ferry', PADDLE = 'paddle';
        var PLAN = {gpx:{trackKind:'track'}}, TALLIED = ['unmarked'];
        var points = [], legs = [];
        function kayak() { return paddling; }
        function reportedAreas() { return []; }
        function riverCrossings() { return [{width:20}]; }
        function tallyOf() { return blankTally(); }
        function tallyEdge() {}
        function router() { return {length:[20,20,20]}; }
        function straightTally(g,laid,standing,first,last,began,ended) {
            var tally = blankTally(); tally.unmarked = ended - began; return tally;
        }
        function panel() { return {
            metresBetween:(x,y,a,b)=>Math.hypot(x-a,y-b),
            layEdges:(g,edges)=>({lon:[0,20*edges.length],lat:[0,0],along:[0,20*edges.length],
                total:20*edges.length,height:[7,7],distance:[0,20*edges.length],read:true})
        }; }
        const graph = {header:{sources:[{kind:'path'},{kind:'paddle'},{kind:'ferry'}]},sources:[0,1,2],
            coordinates:[0,0,20,0,0,0,20,0,0,0,20,0],vertexAt:[0,2,4,6],sampleAt:[0,3,6,9],
            heights:[7,7,7,7,7,7,7,7,7],areasAt:()=>[],waterAt:x=>x>=10,riverAt:()=>[]};
    """
        + "\n".join(functions)
        + r"""
        (async()=>{
            const out = {};
            out.routed = routedParts(graph,{edges:[0,1,2,1],reversed:[false,false,false,false]});
            graph.header.sources[0].kind = 'portage';
            out.portage = routedParts(graph,{edges:[0],reversed:[false]});
            out.portageCut = cutPart(graph,{edge:0,from:15,to:5});
            graph.header.sources[0].kind = 'path';
            out.cut = cutPart(graph,{edge:1,from:15,to:5});
            const answered = {laid:{lon:[0,10,20],lat:[0,0,0],along:[0,10,20],length:20},
                points:[{height:12},{height:12},{height:12}]};
            const from = {lon:0,lat:0}, to = {lon:20,lat:0};
            out.straight = straightParts(graph,from,to,answered);
            graph.riverAt = ()=>[0];
            out.kayakRiver = straightParts(graph,from,to,answered);
            paddling = false;
            out.walkRouted = routedParts(graph,{edges:[0,2],reversed:[false,false]});
            out.walkRiver = straightParts(graph,from,to,answered);
            graph.riverAt = ()=>[];
            out.walkLake = straightParts(graph,from,to,answered);
            graph.damAt = ()=>true;
            out.walkDam = straightParts(graph,from,to,answered);
            paddling = true;
            out.kayakDam = straightParts(graph,from,to,answered);
            delete graph.damAt;
            paddling = true;
            const bankHeights = [220.52169826134383,220.43769955002008,220.21550943697486,
                219.83460552285453,219.62490274449033,219.55653747171286];
            const bank = {laid:{lon:[10,15,20,25,30,35],lat:[0,0,0,0,0,0],along:[0,5,10,15,20,25],length:25},
                points:bankHeights.map(height=>({height}))};
            out.bank = straightParts(graph,{lon:10,lat:0},{lon:35,lat:0},bank);
            graph.riverAt = ()=>[0];
            out.fallingRiver = straightParts(graph,{lon:10,lat:0},{lon:35,lat:0},bank);
            graph.riverAt = x=>x>=25?[0]:[];
            out.lakeIntoRiver = straightParts(graph,{lon:10,lat:0},{lon:35,lat:0},bank);
            graph.riverAt = ()=>[];
            bank.points = bankHeights.map(()=>({height:NaN}));
            out.unread = straightParts(graph,{lon:10,lat:0},{lon:35,lat:0},bank);
            const land = out.straight[0], water = out.straight[1];
            out.mixed = composeRoute(null,null,[{parts:[land,water,land]}]);
            out.onlyWater = composeRoute(null,null,[{parts:[water]},{parts:[water]}]);
            out.ferry = composeRoute(null,null,[{parts:[land,out.routed[2],land]}]);
            console.log(JSON.stringify(out));
        })().catch(error=>{console.error(error);process.exitCode=1;});
    """
    )
    result = subprocess.run([node, "-"], input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_water_runs_and_partial_edges_have_their_own_kind(parts):
    assert [part["kind"] for part in parts["routed"]] == ["routed", "paddled", "ferry", "paddled"]
    assert parts["cut"]["kind"] == "paddled"
    assert parts["cut"]["height"] == [7, 7, 7]
    assert parts["cut"]["lon"] == [15, 5]


def test_the_measured_bank_is_one_level_and_a_river_keeps_its_fall(parts):
    assert parts["bank"][0]["kind"] == "paddled"
    assert parts["bank"][0]["height"] == [219.55653747171286] * 6
    assert parts["fallingRiver"][0]["height"][0] == 220.52169826134383
    assert parts["fallingRiver"][0]["height"][-1] == 219.55653747171286
    lake, river = parts["lakeIntoRiver"]
    assert lake["kind"] == river["kind"] == "paddled"
    assert len(set(lake["height"])) == 1
    assert river["height"][0] > river["height"][-1]
    assert parts["unread"][0]["read"] is False
    assert parts["unread"][0]["height"] == [None] * 6


def test_a_river_is_waded_only_in_walking_modes(parts):
    assert [part["kind"] for part in parts["walkRouted"]] == ["routed", "ferry"]
    assert [part["kind"] for part in parts["kayakRiver"]] == ["land", "paddled"]
    assert [part["kind"] for part in parts["walkRiver"]] == ["land"]
    assert [part["kind"] for part in parts["walkLake"]] == ["land", "water"]
    assert parts["walkLake"][1]["height"] is None
    assert parts["straight"][1]["tally"]["unmarked"] == 0


def test_paddling_keeps_a_continuous_profile_with_two_totals(parts):
    shape = parts["mixed"]
    assert shape["total"] == 10
    assert shape["crossed"] == 15
    assert shape["profileLength"] == 25
    assert shape["straight"] == 10
    assert shape["crossings"] == 0
    assert shape["stations"] == [0, 25]
    assert len(shape["stretches"]) == 1
    assert shape["gaps"] == []
    assert None not in shape["height"]
    assert shape["along"] == [0, 5, 20, 25]


def test_a_station_on_water_has_a_profile_distance(parts):
    shape = parts["onlyWater"]
    assert shape["total"] == 0
    assert shape["crossed"] == shape["profileLength"] == 30
    assert shape["stations"] == [0, 15, 30]
    assert len(shape["stretches"]) == 1
    assert shape["read"] is True


def test_a_ferry_still_breaks_the_track(parts):
    shape = parts["ferry"]
    assert shape["crossings"] == 1
    assert len(shape["stretches"]) == 2
    assert len(shape["gaps"]) == 1
    assert None in shape["height"]
    assert shape["profileLength"] == shape["total"] == 10
    assert shape["crossed"] == 20


def test_a_portage_keeps_its_routed_land_profile_including_partial_edges(parts):
    part = parts["portage"][0]
    assert part["kind"] == parts["portageCut"]["kind"] == "routed"
    assert part["height"] == parts["routed"][0]["height"]
    assert part["distance"] == parts["routed"][0]["distance"]
    assert parts["portageCut"]["height"] == [7, 7, 7]
    assert parts["portageCut"]["lon"] == [15, 5]


def test_dam_samples_change_the_kayak_tally_only(parts):
    assert parts["walkDam"] == parts["walkLake"]
    assert all(part["kind"] == "land" for part in parts["kayakDam"])
    assert sum(part["length"] for part in parts["kayakDam"]) == 20

"""Execute the page's searches on small graphs with known alternatives."""

import json
import re
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

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
        "staying",
        "stayOnPaths",
        "paddle",
        "router",
        "allowed",
        "endsOf",
        "flipCut",
        "routeBetween",
        "joinedRoute",
        "leavingAt",
        "priced",
        "connectorPrice",
        "connectorRadii",
        "connectorScan",
        "entryLandFloors",
        "connectorRunPrice",
        "connectorDryPrefix",
        "dryConnectorBox",
        "connectorBoxLand",
        "cheaper",
        "worthRouting",
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
        var routing = null, gridded = null, paddling = true, stayingOnPaths = false;
        var points = [], goalAt = null, refreshes = 0;
        const storage = new Map();
        const window = {localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}};
        function keptKey() { return 'fixture'; }
        function refresh() { refreshes++; }
        function refreshGoal() {}
        var CROSSING = 'ferry', CONNECTOR = 'bridge', PADDLE = 'paddle', PORTAGE = 'portage', NODE_FIRST_M = 2;
        var PLAN = {portageFactor:4, offPathFactor:3, waterFactor:30, indexCellM:100, snapM:150, maxStraightM:50000};
        var MARKING = ['marked', 'unmarked', 'unknown'];
        var TALLIED = MARKING.concat(['undrawn', 'recorded', 'unrecorded']);
        function offPath() { return staying() ? 10 : PLAN.offPathFactor; }
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
        + Path(__file__).with_name("kayak_reference.js").read_text()
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
            paddle(false); stayingOnPaths = staying; routing = null;
            out.walking.push({reachable:Number.isFinite(router(g).cost[0]),
                route:routeBetween(g,at(0),at(1)),ends:endsOf(g,middle),
                line:nearestOnNetwork(g,0,0.0001,1),tap:snapped(g,0,0,1)});
        }
        paddle(true); stayingOnPaths = false; routing = null;
        out.kayakLine = nearestOnNetwork(g,0,0.0001,1);
        out.kayakTap = snapped(g,0,0,1);
        g = graph('path',false);
        out.portage = router(g).cost[0];
        out.inferred = [];
        for (const kind of ['bridge', 'portage']) {
            g = graph(kind,false);
            g.header.sources[1].factor = 1.3;
            for (const mode of [false,true]) {
                paddle(mode);
                for (const staying of [false,true]) {
                    stayOnPaths(staying);
                    out.inferred.push({kind,mode,staying,length:router(g).length[0],cost:router(g).cost[0],
                        allowed:allowed(g,0,true),route:routeBetween(g,at(0),at(1)),
                        cut:routeBetween(g,{...middle,along:5},{...middle,along:15}),
                        ends:endsOf(g,middle),nodeEnds:endsOf(g,{...middle,node:0}),
                        line:nearestOnNetwork(g,0,0.0001,1),tap:snapped(g,0,0,1)});
                }
            }
        }
        stayOnPaths(false);
        g = graph('ferry',false);
        out.ferryKayak = router(g).cost[0];
        out.ferryLand = router(g).land[0];
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
        for (const kind of ['paddle', 'ferry', 'path', 'bridge', 'portage']) {
            g = graph(kind, false);
            g.header.protected = [{id:'reserve'}];
            g.protectedAt = [0,1]; g.protectedArea = [0]; g.protectedShare = [1];
            g.header.waymarked = [null]; g.waymarked = [0];
            const tally = blankTally();
            try { tallyEdge(tally,g,0,router(g).length[0]); out.tallies[kind] = tally; }
            catch (error) { out.tallies[kind] = {error:error.message}; }
        }

        function alternatives(sources, edges, positions) {
            routing = null;
            return {header:{edges:edges.length,nodes:positions.length,chains:edges.length,sources},
                coordinates:new Float64Array(edges.flatMap(e=>[...positions[e[0]],...positions[e[1]]])),
                vertexAt:Array.from({length:edges.length+1},(_,i)=>2*i),
                chainAt:Array.from({length:edges.length+1},(_,i)=>i),
                fromNode:edges.map(e=>e[0]),toNode:edges.map(e=>e[1]),sources:edges.map(e=>e[2]),
                oneWay:edges.map(()=>0),nodeLon:positions.map(p=>p[0]),nodeLat:positions.map(p=>p[1]),
                water:{cellM:1},waterAt:()=>false};
        }
        paddle(true);
        g = alternatives([{name:'Open water',kind:'paddle',factor:1.5},{name:'path',kind:'path',factor:1}],
            [[0,1,0],[1,2,0],[0,2,1]],[[0,0],[0,0.01],[0.001,0]]);
        out.waterFirst = routeBetween(g,at(0),at(2));
        out.waterWorth = worthRouting(g,at(0),at(2),out.waterFirst.cost,out.waterFirst.land);
        out.waterJoined = joinedRoute(g,at(0),at(2));
        out.groundConnectors = joinedRoute(g,{node:-1,lon:-0.0001,lat:0},{node:-1,lon:0.0011,lat:0});
        out.groundPrimary = router(g).bestLand[out.groundConnectors.head] +
            connectorPrice(g,-0.0001,0,g.nodeLon[out.groundConnectors.head],g.nodeLat[out.groundConnectors.head]).land;
        out.landPoint = routeBetween(g,at(0),{node:-1,edge:2,along:50,lon:0.0005,lat:0});
        out.landCut = routeBetween(g,{node:-1,edge:2,along:25},{node:-1,edge:2,along:75});
        out.walkShortcut = [];
        for(const staying of [false,true]) {
            paddle(false); stayOnPaths(staying);
            out.walkShortcut.push(routeBetween(g,at(0),at(2)));
        }
        paddle(true); stayOnPaths(false);
        // A longer path must lose to less ground even at a cheaper old price.
        g = alternatives([{name:'Open water',kind:'paddle',factor:1.5},
            {name:'path',kind:'path',factor:1},{name:'ground',kind:'portage',factor:1.3}],
            [[0,1,1],[1,2,1],[0,2,2]],[[0,0],[0.0005,0.0005],[0.001,0]]);
        out.lessLand = routeBetween(g,at(0),at(2));
        // Equal land lengths retain the path's lower price.
        g = alternatives(g.header.sources,[[0,1,2],[0,1,1]],[[0,0],[0.001,0]]);
        out.landTie = routeBetween(g,at(0),at(1));
        // No subtraction of rounded lengths may make water negative land.
        g.waterAt = () => true;
        out.allWaterPrimary = connectorPrice(g,0,0,0.001234567,0).land;
        // Off-network water taps face a dry peninsula. Remote dry nodes must
        // not force full connector pricing once a zero-land detour is known.
        const positions = [[0,0],[0,0.01],[0.001,0.01],[0.001,0]];
        for(let i=0;i<128;i++)positions.push([1+i*0.01,0]);
        g = alternatives([{name:'Open water',kind:'paddle',factor:1.5}],
            [[0,1,0],[1,2,0],[2,3,0]],positions);
        g.waterAt = (x,y) => (x<=0 || x>=0.001 || y>=0.01) && x<0.1;
        const waterFrom={node:-1,lon:-0.002,lat:0},waterTo={node:-1,lon:0.003,lat:0};
        const originalPrice=connectorPrice,originalPop=Heap.prototype.pop;
        let prices=0,pops=0;
        connectorPrice=function(...args){prices++;return originalPrice(...args);};
        Heap.prototype.pop=function(){pops++;return originalPop.call(this);};
        const around=joinedRoute(g,waterFrom,waterTo);
        const searched={prices,pops};
        connectorPrice=originalPrice;Heap.prototype.pop=originalPop;
        out.offNetwork={...searched,nodes:g.header.nodes,stepBound:2*g.header.nodes+2*g.header.edges+1,
            route:around,land:router(g).bestLand[around.head]+
                connectorPrice(g,waterFrom.lon,waterFrom.lat,g.nodeLon[around.head],g.nodeLat[around.head]).land,
            cost:router(g).best[around.head]+priced(g,waterFrom.lon,waterFrom.lat,g.nodeLon[around.head],g.nodeLat[around.head]),
            direct:connectorPrice(g,waterFrom.lon,waterFrom.lat,waterTo.lon,waterTo.lat)};
        // A ceiling may stop only after the sampled dry subtotal exceeds it;
        // equality must preserve the secondary-price comparison.
        const full=connectorPrice(g,-0.002,0,0.003,0);
        out.ceilingEqual=connectorPrice(g,-0.002,0,0.003,0,full.land);
        out.ceilingExceeded=connectorPrice(g,-0.002,0,0.003,0,full.land/2).cost===Infinity;
        out.ceilingAccrued=connectorPrice(g,-0.002,0,0.003,0,full.land+100,100);
        // Enumerating every entry/exit pair on a small graph gives an eager
        // reference independent of joinedRoute's queues and pruning.
        out.eager = [];
        g = alternatives([{name:'Open water',kind:'paddle',factor:1.5},{name:'path',kind:'path',factor:1}],
            [[0,1,0],[1,2,0],[2,3,0],[0,3,1]],positions.slice(0,4));
        for(const terrain of [()=>true,()=>false,(x,y)=>x<=0||x>=0.001||y>=0.01,
                (x,y)=>x>=0&&!(x>0.0003&&x<0.0007&&y<0.005)]) {
            const spec={west:-1,south:-1,dLon:0.00001,dLat:0.00001};
            g.water.spec=spec;
            g.waterAt=(x,y)=>terrain(spec.west+(Math.floor((x-spec.west)/spec.dLon)+0.5)*spec.dLon,
                spec.south+(Math.floor((y-spec.south)/spec.dLat)+0.5)*spec.dLat);
            const direct=connectorPrice(g,waterFrom.lon,waterFrom.lat,waterTo.lon,waterTo.lat);
            const chosen=joinedRoute(g,waterFrom,waterTo);
            const entry=chosen?connectorPrice(g,waterFrom.lon,waterFrom.lat,g.nodeLon[chosen.head],g.nodeLat[chosen.head]):null;
            const actual=chosen?{land:entry.land+router(g).bestLand[chosen.head],cost:entry.cost+router(g).best[chosen.head]}:direct;
            let expected=direct;
            for(let a=0;a<g.header.nodes;a++)for(let b=0;b<g.header.nodes;b++) {
                const over=routeBetween(g,at(a),at(b));if(!over)continue;
                const head=connectorPrice(g,waterFrom.lon,waterFrom.lat,g.nodeLon[a],g.nodeLat[a]);
                const tail=connectorPrice(g,g.nodeLon[b],g.nodeLat[b],waterTo.lon,waterTo.lat);
                const candidate={land:head.land+over.land+tail.land,cost:head.cost+over.cost+tail.cost};
                if(candidate.land<expected.land||(candidate.land===expected.land&&candidate.cost<expected.cost))expected=candidate;
            }
            out.eager.push({actual,expected});
        }
        const resumedGraph=g;
        // A fixed stream exercises the full reference on disconnected nodes,
        // directed arcs, shore slivers, dry entries and partial network edges.
        let seed=20260923;
        const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
        out.differential=[];
        for(let terrain=0;terrain<4;terrain++) {
            const nodes=Array.from({length:12},()=>[random()*0.01,random()*0.01]);
            const sources=[{name:'Open water',kind:'paddle',factor:1.5},
                {name:'Shore',kind:'paddle',factor:1},{name:'path',kind:'path',factor:1},
                {name:'carry',kind:'portage',factor:3},{name:'ferry',kind:'ferry',flatM:5000}];
            const arcs=Array.from({length:18},()=>[Math.floor(random()*10),Math.floor(random()*10),Math.floor(random()*sources.length)]);
            arcs[2][2]=2;
            g=alternatives(sources,arcs,nodes);
            g.oneWay=arcs.map(()=>random()<0.3?1:0);
            g.water.cellM=10;
            const spec={west:-0.01,south:-0.01,dLon:0.0001,dLat:0.0001,cols:300,rows:300};
            g.water.spec=spec;
            g.waterAt=(x,y)=>{
                const col=Math.floor((x-spec.west)/spec.dLon),row=Math.floor((y-spec.south)/spec.dLat);
                if(terrain===0)return true;
                if(terrain===1)return false;
                if(terrain===2)return col<130||col>160||row>170;
                return (col%23)<8||(row%31)<9;
            };
            // Use the page's packed grid too, so the reference checks the
            // accelerated sampler together with the search bounds.
            const classify=g.waterAt,stride=(spec.cols+7)>>3,bits=new Uint8Array(stride*spec.rows);
            for(let y=0;y<spec.rows;y++)for(let x=0;x<spec.cols;x++) {
                if(classify(spec.west+(x+0.5)*spec.dLon,spec.south+(y+0.5)*spec.dLat))bits[y*stride+(x>>3)]|=0x80>>(x&7);
            }
            g.water.stride=stride;g.water.bits=bits;
            g.waterAt=(lon,lat)=>{
                const x=Math.floor((lon-spec.west)/spec.dLon),y=Math.floor((lat-spec.south)/spec.dLat);
                return x>=0&&y>=0&&x<spec.cols&&y<spec.rows&&!!(bits[y*stride+(x>>3)]&(0x80>>(x&7)));
            };
            for(let pair=0;pair<8;pair++) {
                let from={node:-1,lon:random()*0.014-0.002,lat:random()*0.014-0.002};
                let to={node:-1,lon:random()*0.014-0.002,lat:random()*0.014-0.002};
                if(pair%4===1)from={node:Math.floor(random()*nodes.length)};
                if(pair%4===2) {
                    const edge=2,ratio=0.2+random()*0.6,a=g.fromNode[edge],b=g.toNode[edge];
                    to={node:-1,edge,along:router(g).length[edge]*ratio,
                        lon:nodes[a][0]+ratio*(nodes[b][0]-nodes[a][0]),
                        lat:nodes[a][1]+ratio*(nodes[b][1]-nodes[a][1])};
                }
                for(const p of [from,to])if(p.node>=0){p.lon=g.nodeLon[p.node];p.lat=g.nodeLat[p.node];}
                if(pair>=4)[from,to]=[to,from];
                const chosen=joinedRoute(g,from,to),actual=chosenLabel(g,from,to,chosen);
                const expected=referenceJoined(g,from,to);
                out.differential.push({terrain,pair,actual,expected});
            }
        }
        g=resumedGraph;routing=null;
        g.waterAt=()=>false;
        const dryLength=panel().metresBetween(0,0,0.001,0),dryPieces=Math.ceil(dryLength/g.water.cellM);
        const dryPrefix=connectorDryPrefix(g,0,0,0.001,0,dryLength,dryPieces,Infinity);
        out.resumed={prefix:dryPrefix,pieces:dryPieces,
            full:connectorPrice(g,0,0,0.001,0),
            resumed:connectorPrice(g,0,0,0.001,0,Infinity,0,{length:dryLength,dry:dryPrefix})};
        g.water={cellM:25,spec:{west:-0.01,south:-0.01,dLon:0.00025,dLat:0.00025}};
        g.waterAt=(x,y)=>{
            const col=Math.floor((x+0.01)/0.00025),row=Math.floor((y+0.01)/0.00025);
            return !(col>=35&&col<=45&&row>=34&&row<=46);
        };
        const dryPoint={lon:0.000037,lat:0.000064},box=dryConnectorBox(g,dryPoint);
        out.boxFloors=[];
        for(let x=-12;x<=12;x++)for(let y=-12;y<=12;y++){
            const lon=dryPoint.lon+x*0.00025*0.83,lat=dryPoint.lat+y*0.00025*0.87;
            const length=panel().metresBetween(dryPoint.lon,dryPoint.lat,lon,lat);
            out.boxFloors.push({floor:connectorBoxLand(g,dryPoint,lon,lat,length,box),
                land:connectorPrice(g,dryPoint.lon,dryPoint.lat,lon,lat).land});
        }
        // Scalar midpoint prices check uniform-square skips independently, including
        // partial grid boundaries, reversed lines and reused dry prefixes.
        out.connectorRuns={checked:0,failures:[]};
        seed=20260923;
        for(let terrain=0;terrain<6;terrain++) {
            const spec={west:0.02,south:0.03,dLon:0.00001,dLat:0.000015,cols:63,rows:49};
            const stride=(spec.cols+7)>>3,bits=new Uint8Array(stride*spec.rows);
            for(let y=0;y<spec.rows;y++)for(let x=0;x<spec.cols;x++) {
                const wet=terrain===0||terrain===2&&x+y>40||terrain===3&&x%17<8||
                    terrain===4&&random()<0.5||terrain===5&&x>16&&x<48&&y>16&&y<48;
                if(wet)bits[y*stride+(x>>3)]|=0x80>>(x&7);
            }
            g.water={spec,stride,bits,cellM:1};
            g.waterAt=(lon,lat)=>{
                const x=Math.floor((lon-spec.west)/spec.dLon),y=Math.floor((lat-spec.south)/spec.dLat);
                return x>=0&&y>=0&&x<spec.cols&&y<spec.rows&&!!(bits[y*stride+(x>>3)]&(0x80>>(x&7)));
            };
            for(let pair=0;pair<1000;pair++) {
                const pos=()=>[spec.west+(random()*83-10)*spec.dLon,spec.south+(random()*69-10)*spec.dLat];
                let [ax,ay]=pos(),[bx,by]=pos();
                if(pair%10===0){ax=spec.west+16*spec.dLon;bx=spec.west+48*spec.dLon;ay=by=spec.south+16*spec.dLat;}
                const expected=referenceConnectorPrice(g,ax,ay,bx,by);
                const length=panel().metresBetween(ax,ay,bx,by),pieces=Math.max(1,Math.ceil(length/g.water.cellM));
                const dry=connectorDryPrefix(g,ax,ay,bx,by,length,pieces,Infinity,32);
                const actual=connectorPrice(g,ax,ay,bx,by,undefined,0,{length,dry});
                const equal=connectorPrice(g,ax,ay,bx,by,expected.land,0);
                const cheaperLimit=expected.land/2,limited=connectorPrice(g,ax,ay,bx,by,cheaperLimit,0);
                if(actual.land!==expected.land||actual.cost!==expected.cost||equal.land!==expected.land||equal.cost!==expected.cost||
                    (expected.land>cheaperLimit?isFinite(limited.cost):limited.cost!==expected.cost)) {
                    out.connectorRuns.failures.push({terrain,pair,from:[ax,ay],to:[bx,by],expected,actual,equal,limited,dry});
                }
                out.connectorRuns.checked++;
            }
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
    assert readings["ferryLand"] == 0


def test_a_water_connector_is_not_pruned_as_ground(readings):
    assert readings["floorRoute"]["over"]["edges"] == [0]
    assert readings["oldFloorRoute"] is None
    assert readings["floorCost"] < readings["directCost"]
    assert readings["patchedFloor"] > readings["floor"]


def test_switching_rebuilds_prices_and_remembers_the_mode(readings):
    assert readings["dropped"] is True
    assert readings["walkTableDifferent"] is True
    assert readings["persisted"] == "yes"


def test_portages_are_unreachable_and_unsnappable_in_both_walking_settings(readings):
    for row in readings["inferred"]:
        if row["kind"] != "portage" or row["mode"]:
            continue
        assert row["cost"] is None
        assert row["allowed"] is False
        assert row["route"] is row["cut"] is row["line"] is None
        assert row["ends"] == row["nodeEnds"] == []
        assert row["tap"]["node"] == -1
        assert "edge" not in row["tap"]


def test_carrying_an_inferred_portage_pays_ground_and_reprices_with_the_switch(readings):
    for row in readings["inferred"]:
        if row["kind"] != "portage" or not row["mode"]:
            continue
        ground = 10 if row["staying"] else 3
        assert row["cost"] == row["length"] * ground * 4
        assert row["route"]["cost"] == row["cost"]
        assert row["cut"]["cost"] == row["cost"] / 2
        assert row["allowed"] is True
        assert len(row["ends"]) == 2
        assert row["line"]["edge"] == 0
        assert row["tap"]["node"] == 0


def test_ordinary_bridges_keep_their_prices_and_walking_access(readings):
    for row in readings["inferred"]:
        if row["kind"] != "bridge":
            continue
        assert row["cost"] == row["length"] * 1.3 * (4 if row["mode"] else 1)
        assert row["allowed"] is True
        assert row["route"]["edges"] == [0]
        assert row["line"] is None


def test_a_portage_counts_undrawn_ground_and_protection_without_source_or_marking(readings):
    tally = readings["tallies"]["portage"]
    assert tally == readings["tallies"]["bridge"]
    assert tally["undrawn"] == readings["forward"]["cost"]
    assert tally["protected"] == {"reserve": tally["undrawn"]}
    assert tally["sources"] == {}
    assert all(tally[field] == 0 for field in ("marked", "unmarked", "unknown", "recorded", "unrecorded"))


def test_water_wins_before_price_in_both_searches(readings):
    assert readings["waterFirst"]["edges"] == [0, 1]
    assert readings["waterFirst"]["land"] == 0
    assert readings["waterWorth"]
    assert readings["waterJoined"]["over"]["edges"] == [0, 1]
    assert readings["groundConnectors"]["over"]["edges"] == [0, 1]
    assert readings["groundPrimary"] == pytest.approx(20)
    assert readings["allWaterPrimary"] == 0


def test_a_land_point_is_reached_and_walking_keeps_its_shortcut(readings):
    assert readings["landPoint"]["land"] == pytest.approx(50)
    assert readings["landPoint"]["tail"] == {"edge": 2, "from": 0, "to": 50}
    assert readings["landCut"]["land"] == pytest.approx(50)
    assert all(route["edges"] == [2] for route in readings["walkShortcut"])


def test_land_metres_win_before_the_path_discount(readings):
    assert readings["lessLand"]["edges"] == [2]
    assert readings["lessLand"]["land"] == pytest.approx(100)
    assert readings["landTie"]["edges"] == [1]


def test_off_network_water_detour_bounds_connector_work(readings):
    got = readings["offNetwork"]
    assert got["direct"]["land"] > 0
    assert got["land"] == 0
    assert got["cost"] > got["direct"]["cost"]
    assert got["route"]["over"]["edges"] == [1]
    assert got["pops"] < got["stepBound"]
    assert got["prices"] < got["nodes"]


def test_connector_ceiling_preserves_equal_land_prices(readings):
    assert readings["ceilingEqual"] == readings["offNetwork"]["direct"]
    assert readings["ceilingAccrued"] == readings["ceilingEqual"]
    assert readings["ceilingExceeded"]


def test_joined_bound_matches_every_entry_exit_pair(readings):
    for case in readings["eager"]:
        assert case["actual"] == pytest.approx(case["expected"])


def test_connector_resumes_after_its_dry_prefix(readings):
    got = readings["resumed"]
    assert 0 < got["prefix"] < got["pieces"]
    assert got["resumed"] == got["full"]


def test_dry_box_never_overstates_sampled_entry_land(readings):
    assert any(pair["floor"] > 0 for pair in readings["boxFloors"])
    assert all(0 <= pair["floor"] <= pair["land"] for pair in readings["boxFloors"])


def test_seeded_joined_search_matches_the_unpruned_reference(readings):
    for case in readings["differential"]:
        for component in ("land", "cost"):
            actual, expected = case["actual"][component], case["expected"][component]
            assert actual == pytest.approx(expected, abs=1e-8, rel=1e-12), (case["terrain"], case["pair"], component, case)


def test_uniform_squares_preserve_scalar_midpoint_prices(readings):
    assert readings["connectorRuns"]["checked"] == 6000
    assert readings["connectorRuns"]["failures"] == []

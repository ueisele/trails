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
        "entryGeometry",
        "entryContext",
        "entrySegment",
        "entrySegments",
        "nearestEntryDistance",
        "middleEntries",
        "middlePrice",
        "middleDirect",
        "leavingAt",
        "priced",
        "connectorPrice",
        "connectorWaterAt",
        "connectorRadii",
        "connectorScan",
        "entryLandFloors",
        "connectorRunPrice",
        "connectorDryPrefix",
        "dryConnectorBox",
        "connectorBoxLand",
        "cheaper",
        "worthRouting",
        "waterRoles",
        "nearestByRole",
        "roleSnapped",
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
        var CROSSING = 'ferry', CONNECTOR = 'bridge', PADDLE = 'paddle', PORTAGE = 'portage', LAUNCH = 'launch', NODE_FIRST_M = 2;
        var SAME_SPOT_M = 1;
        var ENTRY_MARGIN = 250;
        var PLAN = {portageFactor:4, offPathFactor:3, waterFactor:30, indexCellM:100, snapM:150, waterSnapM:17.1, maxStraightM:50000};
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
        for (const kind of ['bridge', 'portage', 'launch']) {
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
        for (const kind of ['paddle', 'ferry', 'path', 'bridge', 'portage', 'launch']) {
            g = graph(kind, false);
            g.header.protected = [{id:'reserve'}];
            g.protectedAt = [0,1]; g.protectedArea = [0]; g.protectedShare = [1];
            g.header.waymarked = [null]; g.waymarked = [0];
            const tally = blankTally();
            try { tallyEdge(tally,g,0,router(g).length[0]); out.tallies[kind] = tally; }
            catch (error) { out.tallies[kind] = {error:error.message}; }
        }

        function alternatives(sources, edges, positions) {
            routing = null; gridded = null;
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
        // A longer path beats the shorter carry over ground by walking price.
        g = alternatives([{name:'Open water',kind:'paddle',factor:1.5},
            {name:'path',kind:'path',factor:1},{name:'ground',kind:'portage',factor:1.3}],
            [[0,1,1],[1,2,1],[0,2,2]],[[0,0],[0.0005,0.0005],[0.001,0]]);
        out.lessLand = routeBetween(g,at(0),at(2));
        // The primary price prefers path to ground at equal lengths.
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
                {name:'carry',kind:'portage',factor:3},{name:'ferry',kind:'ferry',flatM:5000},
                {name:'launch',kind:'launch',factor:1}];
            const arcs=Array.from({length:18},()=>[Math.floor(random()*10),Math.floor(random()*10),Math.floor(random()*sources.length)]);
            arcs[2][2]=2;
            arcs[3][2]=5;
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
                for(const staying of [false,true]) {
                    stayOnPaths(staying);
                    const chosen=joinedRoute(g,from,to),actual=chosenLabel(g,from,to,chosen);
                    const expected=referenceJoined(g,from,to);
                    out.differential.push({terrain,pair,staying,actual,expected});
                }
            }
        }
        stayOnPaths(false);
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
        out.walkingRuns={checked:0,wetMismatches:0,maxPriceDifference:0};
        seed=20260923;
        for(let terrain=0;terrain<7;terrain++) {
            const spec={west:0.02,south:0.03,dLon:0.00001,dLat:0.000015,cols:63,rows:49};
            const stride=(spec.cols+7)>>3,bits=new Uint8Array(stride*spec.rows);
            for(let y=0;y<spec.rows;y++)for(let x=0;x<spec.cols;x++) {
                const wet=terrain===0||terrain===6||terrain===2&&x+y>40||terrain===3&&x%17<8||
                    terrain===4&&random()<0.5||terrain===5&&x>16&&x<48&&y>16&&y<48;
                if(wet)bits[y*stride+(x>>3)]|=0x80>>(x&7);
            }
            g.water={spec,stride,bits,cellM:1};
            g.waterAt=(lon,lat)=>{
                const x=Math.floor((lon-spec.west)/spec.dLon),y=Math.floor((lat-spec.south)/spec.dLat);
                return x>=0&&y>=0&&x<spec.cols&&y<spec.rows&&!!(bits[y*stride+(x>>3)]&(0x80>>(x&7)));
            };
            g.damAt=terrain===6?(lon,lat)=>Math.hypot((lon-spec.west)/spec.dLon-32.3,(lat-spec.south)/spec.dLat-24.2)<4.7:()=>false;
            if(terrain===6) {
                g.water.damCells=new Set();
                for(let y=19;y<=29;y++)for(let x=27;x<=37;x++)g.water.damCells.add(y*spec.cols+x);
            }
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
                paddling=false;
                let wet=0;
                for(let sample=0;sample<pieces;sample++) {
                    const t=(sample+.5)/pieces;
                    if(g.waterAt(ax+t*(bx-ax),ay+t*(by-ay)))wet++;
                }
                const batched=connectorScan({water:g.water},ax,ay,bx,by,pieces,0,pieces,1,length,undefined,undefined,0);
                if(batched!==wet)out.walkingRuns.wetMismatches++;
                out.walkingRuns.maxPriceDifference=Math.max(out.walkingRuns.maxPriceDifference,
                    Math.abs(connectorPrice(g,ax,ay,bx,by).cost-referenceConnectorPrice(g,ax,ay,bx,by).cost));
                out.walkingRuns.checked++;
                paddling=true;
            }
        }
        paddling=false;
        const ax=g.water.spec.west,ay=g.water.spec.south,bx=ax+0.0004,by=ay+0.0004;
        g.damAt=()=>true;
        const blocked=connectorPrice(g,ax,ay,bx,by);
        g.damAt=()=>false;
        out.walkingDams={blocked,clear:connectorPrice(g,ax,ay,bx,by)};
        out.middleWalking=[];
        for(const height of [8,400])for(const paths of [false,true]) {
            paddling=false; stayingOnPaths=paths;
            g=alternatives([{name:'road',kind:'path',factor:1.3}],[[0,1,0]],[[0,0],[0.02,0]]);
            g.water=null;
            const from={node:-1,lon:0.004,lat:height/100000},to={node:-1,lon:0.018,lat:height/100000};
            const chosen=joinedRoute(g,from,to),expected=referenceJoined(g,from,to);
            out.middleWalking.push({height,paths,nearest:nearestEntryDistance(g,entryContext(g,from)),
                chosen,expected,direct:connectorPrice(g,from.lon,from.lat,to.lon,to.lat)});
        }
        g=alternatives([{name:'road',kind:'path',factor:1.3}],[[0,1,0],[1,2,0]],[[0,0],[0.02,0],[0.02,0.02]]);
        g.water=null; g.oneWay=[1,1];
        const beside={node:-1,lon:0.01,lat:0.00008},beyond={node:-1,lon:0.02008,lat:0.01};
        out.meetingEdges={chosen:joinedRoute(g,beside,beyond),expected:referenceJoined(g,beside,beyond)};
        // The line off the bank: each role is paddled at its own source's price, in
        // whole and in part, credited to its own name, and on foot neither routed
        // nor snapped to in either setting.
        const offsetSources=[{name:'Shore',kind:'paddle',factor:1,role:'travel'},
            {name:'Narrow water',kind:'paddle',factor:1,role:'travel'},
            {name:'Landing water',kind:'paddle',factor:1,role:'landing'},
            {name:'Open water',kind:'paddle',factor:1.5,role:'open'},
            {name:'Streams',kind:'paddle',factor:1,role:'stream'}];
        out.offsetRoles=[];
        for(let s=0;s<offsetSources.length;s++) {
            paddle(true); stayOnPaths(false);
            g=alternatives(offsetSources,[[0,1,s]],[[0,0],[0.001,0]]);
            g.water=null; g.oneWay=[offsetSources[s].role==='stream'?1:0]; g.nearestNode=()=>0;
            g.header.protected=[]; g.protectedAt=[0,0]; g.protectedArea=[]; g.protectedShare=[];
            g.header.waymarked=[null]; g.waymarked=[0];
            const length=router(g).length[0];
            const row={name:offsetSources[s].name,factor:offsetSources[s].factor,length,
                whole:routeBetween(g,at(0),at(1)),back:routeBetween(g,at(1),at(0)),
                part:routeBetween(g,{node:-1,edge:0,along:length/4,lon:0.00025,lat:0},{node:-1,edge:0,along:3*length/4,lon:0.00075,lat:0})};
            const tally=blankTally(); tallyEdge(tally,g,0,length); row.tally=tally;
            row.walking=[];
            for(const staying of [false,true]) {
                paddle(false); stayOnPaths(staying); routing=null;
                row.walking.push({reachable:Number.isFinite(router(g).cost[0]),route:routeBetween(g,at(0),at(1)),
                    line:nearestOnNetwork(g,0,0.0001,1),tap:snapped(g,0,0,1)});
            }
            out.offsetRoles.push(row);
        }
        paddle(true); stayOnPaths(false);
        // Phase 12f: the tap and the entries where the line runs off the bank.
        // Positions in metres; the page's metre is the index's here, so a node's
        // distance and a line's agree.
        const pagePanel=panel;
        panel=()=>({metresBetween:(x,y,a,b)=>Math.hypot(x-a,y-b)*111320});
        const M=1/111320, xy=(x,y)=>[x*M,y*M];
        const roleSources=[{name:'Shore',kind:'paddle',factor:1,role:'travel'},
            {name:'Narrow water',kind:'paddle',factor:1,role:'travel'},
            {name:'Landing water',kind:'paddle',factor:1,role:'landing'},
            {name:'Open water',kind:'paddle',factor:1.5,role:'open'},
            {name:'Streams',kind:'paddle',factor:1,role:'stream'},
            {name:'road',kind:'path',factor:1},{name:'launch',kind:'launch',factor:1}];
        // A bank along y = 0, land below it; the Shore line 15 m out, cut where
        // two landings meet it. Node 2 is a bank anchor with nothing else; node 4
        // is where a launch from the road meets the bank; node 10 is the bank end
        // of an open-water link. A chord runs out into the lake from node 0. A
        // stream runs downhill from 12 to 13. Two islands' lines at y = 15 and
        // y = 40 further east, and the middle of a 20 m channel beyond them.
        const places=[xy(0,15),xy(400,15),xy(100,0),xy(100,15),xy(200,0),xy(200,15),xy(300,15),
            xy(200,-20),xy(0,-30),xy(400,-30),xy(300,0),xy(400,215),xy(500,200),xy(500,15),
            xy(1000,15),xy(1400,15),xy(1000,40),xy(1400,40),xy(2000,10),xy(2400,10)];
        const roleEdges=[[0,3,0],[3,5,0],[5,6,0],[6,1,0],[2,3,2],[4,5,2],[7,4,6],[8,9,5],[10,6,3],[0,11,3],
            [12,13,4],[14,15,0],[16,17,0],[18,19,1]];
        function roleGraph(withRoles) {
            const sources=withRoles?roleSources:roleSources.map(({role,...rest})=>rest);
            const built=alternatives(sources,roleEdges,places);
            built.oneWay=roleEdges.map((e,i)=>i===10?1:0);
            built.roleOf=sources.map(s=>s.role||null);
            built.nearestNode=(lat,lon,reach)=>{let best=-1,near=reach;
                for(let n=0;n<places.length;n++){const m=panel().metresBetween(lon,lat,places[n][0],places[n][1]);if(m<near){near=m;best=n;}}
                return best;};
            return built;
        }
        g=roleGraph(true);
        const tap=(x,y,reach)=>{const p=snapped(g,y*M,x*M,reach);
            return {node:p.node,edge:p.edge===undefined?-1:p.edge,along:p.along,x:p.lon/M,y:p.lat/M};};
        paddle(true); stayOnPaths(false); routing=null; gridded=null;
        out.roleTaps={
            nearBank:tap(150,1,6), besideAnchor:tap(101,1,24), atLaunch:tap(201,1,24), besideOpenLink:tap(300,2,24),
            offshoreChord:tap(150,100,24), offshoreRaw:tap(300,60,24), offshoreFar:tap(150,100,150),
            onRoad:tap(150,-28,24), landCloser:tap(150,-12,40), exactRaw:tap(150,1,1), exactOnLanding:tap(100,5,1),
            exactOnShore:tap(150,15,1), beyondBand:tap(150,-2.5,6), islandA:tap(1200,1,24), islandB:tap(1200,54,24),
            nearerB:tap(1200,28.5,24), narrow:tap(2200,2,6), stream:tap(501,100,24)};
        const onStream={node:-1,edge:10,along:out.roleTaps.stream.along,lon:out.roleTaps.stream.x*M,lat:out.roleTaps.stream.y*M};
        out.streamEnds={leaving:endsOf(g,onStream).map(e=>e.node),entering:endsOf(g,onStream,true).map(e=>e.node)};
        out.roleWalking=[];
        for(const staying of [false,true]) {
            paddle(false); stayOnPaths(staying); routing=null;
            const near=tap(150,1,24),far=tap(150,1,150);
            out.roleWalking.push({near,far,farKind:far.edge>=0?g.header.sources[g.sources[far.edge]].kind:null,
                snapKinds:far.node>=0?g.fromNode.map((f,i)=>f===far.node||g.toNode[i]===far.node?
                    g.header.sources[g.sources[i]].kind:null).filter(Boolean):[]});
        }
        paddle(true); stayOnPaths(false);
        g=roleGraph(false); routing=null; gridded=null;
        out.roleless={roles:waterRoles(g),onLanding:tap(100,5,24)};
        // Entries: a raw point beside a landing enters no landing's middle, and
        // its d is measured to the lines that remain.
        g=roleGraph(true); routing=null; gridded=null;
        {
            const spec={west:-0.01,south:-0.01,dLon:0.00005,dLat:0.00005,cols:1000,rows:1000};
            const stride=(spec.cols+7)>>3,bits=new Uint8Array(stride*spec.rows);
            for(let y=0;y<spec.rows;y++)for(let x=0;x<spec.cols;x++) {
                const lat=spec.south+(y+0.5)*spec.dLat;
                if(lat>0)bits[y*stride+(x>>3)]|=0x80>>(x&7);
            }
            g.water={spec,stride,bits,cellM:5};
            g.waterAt=(lon,lat)=>{const x=Math.floor((lon-spec.west)/spec.dLon),y=Math.floor((lat-spec.south)/spec.dLat);
                return x>=0&&y>=0&&x<spec.cols&&y<spec.rows&&!!(bits[y*stride+(x>>3)]&(0x80>>(x&7)));};
        }
        out.roleEntries=[];
        for(const staying of [false,true]) {
            stayOnPaths(staying); routing=null;
            const beside={node:-1,lon:100.5*M,lat:6*M},target={node:1,lon:places[1][0],lat:places[1][1]};
            const entries=middleEntries(g,beside,false);
            const chosen=joinedRoute(g,beside,target);
            out.roleEntries.push({staying,nearest:nearestEntryDistance(g,entryContext(g,beside)),
                edges:Object.keys(entries.byEdge).map(Number),actual:chosenLabel(g,beside,target,chosen),
                expected:referenceJoined(g,beside,target),referenceEdges:[...new Set(referenceMiddle(g,beside,false).map(p=>p.edge))]});
        }
        stayOnPaths(false);
        // The seeded differential again, on graphs whose paddled lines carry
        // roles, landings among them: the reference reads the role off the
        // header and shares none of production's candidates or pruning.
        seed=20260927;
        out.roleDifferential=[];
        for(let terrain=0;terrain<4;terrain++) {
            const nodes=Array.from({length:12},()=>[random()*0.01,random()*0.01]);
            const sources=[{name:'Open water',kind:'paddle',factor:1.5,role:'open'},
                {name:'Shore',kind:'paddle',factor:1,role:'travel'},{name:'Landing water',kind:'paddle',factor:1,role:'landing'},
                {name:'Streams',kind:'paddle',factor:1,role:'stream'},{name:'path',kind:'path',factor:1},
                {name:'carry',kind:'portage',factor:3},{name:'launch',kind:'launch',factor:1}];
            const arcs=Array.from({length:18},()=>[Math.floor(random()*10),Math.floor(random()*10),Math.floor(random()*sources.length)]);
            arcs[2][2]=2; arcs[3][2]=2; arcs[4][2]=4;
            g=alternatives(sources,arcs,nodes);
            g.roleOf=sources.map(s=>s.role||null);
            g.oneWay=arcs.map(a=>a[2]===3?1:0);
            g.water.cellM=10;
            const spec={west:-0.01,south:-0.01,dLon:0.0001,dLat:0.0001,cols:300,rows:300};
            g.water.spec=spec;
            const stride=(spec.cols+7)>>3,bits=new Uint8Array(stride*spec.rows);
            for(let y=0;y<spec.rows;y++)for(let x=0;x<spec.cols;x++) {
                const wet=terrain===0||terrain===2&&(x<130||x>160||y>170)||terrain===3&&((x%23)<8||(y%31)<9);
                if(wet)bits[y*stride+(x>>3)]|=0x80>>(x&7);
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
                    // Beside a landing, so its middle is the nearest line.
                    const edge=2,ratio=0.2+random()*0.6,a=g.fromNode[edge],b=g.toNode[edge];
                    to={node:-1,lon:nodes[a][0]+ratio*(nodes[b][0]-nodes[a][0])+0.00003,
                        lat:nodes[a][1]+ratio*(nodes[b][1]-nodes[a][1])+0.00003};
                }
                for(const p of [from,to])if(p.node>=0){p.lon=g.nodeLon[p.node];p.lat=g.nodeLat[p.node];}
                if(pair>=4)[from,to]=[to,from];
                for(const staying of [false,true]) {
                    stayOnPaths(staying);
                    const chosen=joinedRoute(g,from,to),actual=chosenLabel(g,from,to,chosen);
                    const expected=referenceJoined(g,from,to);
                    out.roleDifferential.push({terrain,pair,staying,actual,expected});
                }
            }
        }
        stayOnPaths(false);
        // Phase 13: on foot a walk turns only where there is a way. The straight
        // line from F to T crosses a lake 40 m wide; a node W on the far side of
        // it lies only on a Shore line, and two straight lines over dry ground
        // by way of W beat the one across the water. A road runs north of both.
        function walkGraph(withRoad) {
            const sources=[{name:'Shore',kind:'paddle',factor:1,role:'travel'},{name:'road',kind:'path',factor:1},
                {name:'Open water',kind:'paddle',factor:1.5,role:'open'}];
            const where=[xy(100,70),xy(100,120),xy(40,150),xy(160,150)];
            const built=alternatives(sources,withRoad?[[0,1,0],[2,3,1]]:[[0,1,0]],withRoad?where:where.slice(0,2));
            built.roleOf=sources.map(s=>s.role||null);
            const spec={west:-0.01,south:-0.01,dLon:0.00005,dLat:0.00005,cols:1000,rows:1000};
            const stride=(spec.cols+7)>>3,bits=new Uint8Array(stride*spec.rows);
            for(let y=0;y<spec.rows;y++)for(let x=0;x<spec.cols;x++) {
                const lon=(spec.west+(x+0.5)*spec.dLon)/M,lat=(spec.south+(y+0.5)*spec.dLat)/M;
                if(lon>=80&&lon<=120&&lat<=50)bits[y*stride+(x>>3)]|=0x80>>(x&7);
            }
            built.water={spec,stride,bits,cellM:5};
            built.waterAt=(lon,lat)=>{const x=Math.floor((lon-spec.west)/spec.dLon),y=Math.floor((lat-spec.south)/spec.dLat);
                return x>=0&&y>=0&&x<spec.cols&&y<spec.rows&&!!(bits[y*stride+(x>>3)]&(0x80>>(x&7)));};
            return built;
        }
        const shape=(chosen)=>!chosen?'straight':chosen.middleOnly?'along a way':
            (chosen.over?'via '+chosen.over.edges.map(e=>g.header.sources[g.sources[e]].name).join(','):'pivot at '+chosen.head);
        const F={node:-1,lon:0,lat:0},T={node:-1,lon:200*M,lat:0},T2={node:-1,lon:30*M,lat:5*M};
        out.walkingTurns=[];
        for(const road of [false,true])for(const staying of [false,true]) {
            g=walkGraph(road); paddle(false); stayOnPaths(staying); routing=null;
            const row={road,staying,walkNodes:Array.from(router(g).walkNodes)};
            let chosen=joinedRoute(g,F,T);
            row.shape=shape(chosen); row.actual=chosenLabel(g,F,T,chosen); row.expected=referenceJoined(g,F,T);
            row.direct=connectorPrice(g,F.lon,F.lat,T.lon,T.lat);
            row.shortShape=shape(joinedRoute(g,F,T2));
            // Main's rule, every node a place to turn: the same search then pivots at W.
            router(g).walkNodes.fill(1);
            chosen=joinedRoute(g,F,T);
            row.everyNode={shape:shape(chosen),label:chosenLabel(g,F,T,chosen)};
            routing=null;
            // The kayak's land legs end at water, and the walking table is not read there.
            paddle(true); routing=null;
            const kayakChosen=joinedRoute(g,F,T),kayakLabel=chosenLabel(g,F,T,kayakChosen);
            router(g).walkNodes.fill(0);
            const kayakAgain=joinedRoute(g,F,T);
            row.kayak={shape:shape(kayakChosen),label:kayakLabel,again:chosenLabel(g,F,T,kayakAgain),
                againShape:shape(kayakAgain),expected:referenceJoined(g,F,T)};
            out.walkingTurns.push(row);
        }
        paddle(true); stayOnPaths(false);
        // The seeded differential on foot, on graphs where some nodes lie only on
        // water, carries or launches: production against the reference's own rule.
        seed=20260928;
        out.walkingDifferential=[];
        for(let terrain=0;terrain<4;terrain++) {
            const nodes=Array.from({length:14},()=>[random()*0.01,random()*0.01]);
            const sources=[{name:'Open water',kind:'paddle',factor:1.5,role:'open'},
                {name:'Shore',kind:'paddle',factor:1,role:'travel'},{name:'path',kind:'path',factor:1},
                {name:'carry',kind:'portage',factor:3},{name:'launch',kind:'launch',factor:1},
                {name:'ferry',kind:'ferry',flatM:5000},{name:'bridge',kind:'bridge',factor:1.3}];
            const arcs=Array.from({length:18},()=>[Math.floor(random()*12),Math.floor(random()*12),Math.floor(random()*sources.length)]);
            arcs[2][2]=2; arcs[3][2]=1; arcs[4][2]=1;
            g=alternatives(sources,arcs,nodes);
            g.roleOf=sources.map(s=>s.role||null);
            g.water.cellM=10;
            const spec={west:-0.01,south:-0.01,dLon:0.0001,dLat:0.0001,cols:300,rows:300};
            g.water.spec=spec;
            const stride=(spec.cols+7)>>3,bits=new Uint8Array(stride*spec.rows);
            for(let y=0;y<spec.rows;y++)for(let x=0;x<spec.cols;x++) {
                const wet=terrain===0||terrain===2&&(x<130||x>160||y>170)||terrain===3&&((x%23)<8||(y%31)<9);
                if(wet)bits[y*stride+(x>>3)]|=0x80>>(x&7);
            }
            g.water.stride=stride;g.water.bits=bits;
            g.waterAt=(lon,lat)=>{
                const x=Math.floor((lon-spec.west)/spec.dLon),y=Math.floor((lat-spec.south)/spec.dLat);
                return x>=0&&y>=0&&x<spec.cols&&y<spec.rows&&!!(bits[y*stride+(x>>3)]&(0x80>>(x&7)));
            };
            for(let pair=0;pair<8;pair++) {
                let from={node:-1,lon:random()*0.014-0.002,lat:random()*0.014-0.002};
                let to={node:-1,lon:random()*0.014-0.002,lat:random()*0.014-0.002};
                if(pair%4===1)from={node:g.fromNode[2]};
                if(pair%4===2) {
                    const edge=2,ratio=0.2+random()*0.6,a=g.fromNode[edge],b=g.toNode[edge];
                    to={node:-1,edge,along:0,lon:nodes[a][0]+ratio*(nodes[b][0]-nodes[a][0]),lat:nodes[a][1]+ratio*(nodes[b][1]-nodes[a][1])};
                }
                for(const p of [from,to])if(p.node>=0){p.lon=g.nodeLon[p.node];p.lat=g.nodeLat[p.node];}
                if(pair>=4)[from,to]=[to,from];
                for(const staying of [false,true]) {
                    paddle(false); stayOnPaths(staying); routing=null;
                    if(to.edge>=0)to.along=router(g).length[to.edge]*0.5;
                    const chosen=joinedRoute(g,from,to),actual=chosenLabel(g,from,to,chosen);
                    const expected=referenceJoined(g,from,to);
                    const turnedAt=chosen&&!chosen.middleOnly?[chosen.head,chosen.tail]:[];
                    out.walkingDifferential.push({terrain,pair,staying,actual,expected,
                        turnsOnWay:turnedAt.every(n=>router(g).walkNodes[n]===1),
                        waterOnly:Array.from(router(g).walkNodes).filter(v=>v===0).length});
                }
            }
        }
        paddle(true); stayOnPaths(false);
        panel=pagePanel;
        paddle(true); stayOnPaths(false);
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


def test_walking_enters_and_exits_a_road_between_nodes_even_beyond_250_metres(readings):
    for row in readings["middleWalking"]:
        chosen = row["chosen"]
        assert row["nearest"] == pytest.approx(row["height"])
        assert chosen["middleOnly"] is True
        assert 0 < chosen["headCut"]["from"] < chosen["headCut"]["to"] < 2000
        assert chosen["headPoint"]["lat"] == chosen["tailPoint"]["lat"] == 0
        assert chosen["cost"] == pytest.approx(row["expected"]["cost"], abs=1e-8)
        assert chosen["cost"] < row["direct"]["cost"]


def test_interior_pieces_meet_at_a_junction_in_the_permitted_direction(readings):
    chosen = readings["meetingEdges"]["chosen"]
    assert chosen["head"] == chosen["tail"] == 1
    assert chosen["headCut"]["edge"] == 0
    assert chosen["tailCut"]["edge"] == 1
    assert chosen["cost"] == pytest.approx(readings["meetingEdges"]["expected"]["cost"], abs=1e-8)


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


def test_portages_and_launches_are_unreachable_and_unsnappable_in_both_walking_settings(readings):
    for row in readings["inferred"]:
        if row["kind"] not in ("portage", "launch") or row["mode"]:
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
        assert row["route"]["land"] == row["length"] * ground
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
        assert row["route"]["land"] == (row["length"] * 1.3 if row["mode"] else 0)
        assert row["allowed"] is True
        assert row["route"]["edges"] == [0]
        assert row["line"] is None


def test_a_portage_counts_undrawn_ground_and_protection_without_source_or_marking(readings):
    tally = readings["tallies"]["portage"]
    assert tally == readings["tallies"]["bridge"]
    assert tally == readings["tallies"]["launch"]
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
    assert readings["groundPrimary"] == pytest.approx(20 * 3)
    assert readings["allWaterPrimary"] == 0


def test_a_land_point_is_reached_and_walking_keeps_its_shortcut(readings):
    assert readings["landPoint"]["land"] == pytest.approx(50)
    assert readings["landPoint"]["tail"] == {"edge": 2, "from": 0, "to": 50}
    assert readings["landCut"]["land"] == pytest.approx(50)
    assert all(route["edges"] == [2] for route in readings["walkShortcut"])


def test_land_price_keeps_the_longer_path(readings):
    assert readings["lessLand"]["edges"] == [0, 1]
    assert readings["lessLand"]["land"] == pytest.approx(2 * (50**2 + 50**2) ** 0.5)
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
            assert actual == pytest.approx(expected, abs=1e-8, rel=1e-12), (case["terrain"], case["pair"], case["staying"], component, case)


def test_uniform_squares_preserve_scalar_midpoint_prices(readings):
    assert readings["connectorRuns"]["checked"] == 7000
    assert readings["connectorRuns"]["failures"] == []


def test_walking_batches_count_the_same_midpoints_without_dam_discs(readings):
    assert readings["walkingRuns"] == {"checked": 7000, "wetMismatches": 0, "maxPriceDifference": 0}


def test_dam_discs_do_not_change_walking_prices(readings):
    assert readings["walkingDams"]["blocked"] == readings["walkingDams"]["clear"]


def test_page_dam_disc_uses_the_decided_radius():
    from pyproj import Transformer

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the dam reading")
    source = files("trails.visualization").joinpath("js", "routing_graph.js").read_text()
    start = source.index("            var dams =")
    end = source.index("            var grid = header.water", start)
    # Korslång's source point, tested on either side of the metric cut.
    lon, lat = 15.255897764963516, 59.9476443049001
    forward = Transformer.from_crs(4326, 3006, always_xy=True)
    backward = Transformer.from_crs(3006, 4326, always_xy=True)
    x, y = forward.transform(lon, lat)
    positions = [backward.transform(x + dx * radius, y + dy * radius) for radius in (24.9, 25.1) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    script = "const graph={}, header=" + json.dumps({"dams": [[lon, lat]], "damRadiusM": 25}) + ";\n" + source[start:end]
    script += "console.log(JSON.stringify(" + json.dumps(positions) + ".map(p=>graph.damAt(...p))));"
    result = subprocess.run([node, "-"], input=script, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [True] * 4 + [False] * 4


def test_launches_keep_path_price_in_both_objectives_and_switch_settings(readings):
    for row in readings["inferred"]:
        if row["kind"] != "launch" or not row["mode"]:
            continue
        assert row["cost"] == row["length"]
        assert row["route"]["land"] == row["length"]
        assert row["allowed"] is True


def test_kloten_interior_entries_match_the_virtual_table_and_attached_rows_stay_put():
    """Replay measured Kloten geometry and prices without a page or cached nationwide inputs."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute the routing checks")
    source = files("trails.visualization").joinpath("js", "plan_mode.js").read_text()
    names = (
        "router",
        "allowed",
        "endsOf",
        "flipCut",
        "routeBetween",
        "joinedRoute",
        "leavingAt",
        "connectorPrice",
        "connectorWaterAt",
        "connectorRadii",
        "connectorScan",
        "entryLandFloors",
        "connectorRunPrice",
        "connectorDryPrefix",
        "dryConnectorBox",
        "connectorBoxLand",
        "cheaper",
        "worthRouting",
        "waterRoles",
        "cheapestMetre",
        "openWaterFactor",
        "edgeIndex",
        "entryGeometry",
        "entryContext",
        "entrySegment",
        "entrySegments",
        "nearestEntryDistance",
        "middleEntries",
        "middlePrice",
        "middleDirect",
    )
    functions = []
    for name in names:
        match = re.search(rf"^            function {name}\([^\n]*\) \{{(?:[^\n]*\}}$|.*?^            \}})", source, re.M | re.S)
        assert match is not None, name
        functions.append(match[0])
    heap = source[source.index("            function Heap()") : source.index("            // Dijkstra over the weighted graph")]
    fixture = Path(__file__).with_name("kloten_phase11.json").read_text()
    script = (
        "const fixture="
        + fixture
        + ";\n"
        + r"""
        var routing=null, gridded=null, stayingOnPaths=false, ENTRY_MARGIN=250, PLAN=fixture.plan;
        var CROSSING='ferry',CONNECTOR='bridge',PADDLE='paddle',PORTAGE='portage',LAUNCH='launch';
        function kayak(){return true;}
        function offPath(){return stayingOnPaths?10:PLAN.offPathFactor;}
        function metres(x,y,a,b){
            const phi=(y+b)*Math.PI/360;
            const sy=111132.92-559.82*Math.cos(2*phi)+1.175*Math.cos(4*phi)-.0023*Math.cos(6*phi);
            const sx=111412.84*Math.cos(phi)-93.5*Math.cos(3*phi)+.118*Math.cos(5*phi);
            return Math.sqrt(((a-x)*sx)**2+((b-y)*sy)**2);
        }
        function panel(){return {metresBetween:metres};}
    """
        + "\n".join(functions)
        + heap
        + r"""
        const g=fixture.graph, crop=fixture.crop, wet=new Set(crop.wet), spec=g.water.spec;
        g.waterAt=(lon,lat)=>{
            const x=Math.floor((lon-spec.west)/spec.dLon)-crop.col,y=Math.floor((lat-spec.south)/spec.dLat)-crop.row;
            if(x<0||y<0||x>=crop.cols||y>=crop.rows)throw Error('connector left the measured water crop');
            return wet.has(y*crop.cols+x);
        };
        const dams=g.header.dams.map(p=>{
            const phi=p[1]*Math.PI/180;
            return [...p,111412.84*Math.cos(phi)-93.5*Math.cos(3*phi)+.118*Math.cos(5*phi),
                111132.92-559.82*Math.cos(2*phi)+1.175*Math.cos(4*phi)-.0023*Math.cos(6*phi)];
        });
        g.damAt=(x,y)=>dams.some(p=>((x-p[0])*p[2])**2+((y-p[1])*p[3])**2<=g.header.damRadiusM**2);
        const rows=[];
        for(const c of fixture.cases){
            stayingOnPaths=c.case.stay;routing=null;
            const j=c.attached?routeBetween(g,c.from,c.to):joinedRoute(g,c.from,c.to),w=router(g);
            if(!j)throw Error('Kloten route disappeared');
            if(c.attached&&!worthRouting(g,c.from,c.to,j.cost,j.land))throw Error('attached whole-leg fallback changed');
            let carry=0;
            const add=(e,m)=>{if(![PADDLE,CROSSING].includes(g.header.sources[g.sources[e]].kind))carry+=m;};
            const cuts=c.attached?[j.head,j.tail]:[j.headCut,j.tailCut];
            for(const cut of cuts)if(cut)add(cut.edge,Math.abs(cut.to-cut.from));
            for(const e of (c.attached?j.edges:j.over?.edges||[]))add(e,w.length[e]);
            if(j.headPoint)carry+=connectorPrice(g,c.from.lon,c.from.lat,j.headPoint.lon,j.headPoint.lat).land/offPath();
            if(j.tailPoint)carry+=connectorPrice(g,j.tailPoint.lon,j.tailPoint.lat,c.to.lon,c.to.lat).land/offPath();
            rows.push({case:c.case,attached:c.attached,land:j.land,cost:j.cost,carry,expected:c.expected,
                northern:(c.attached?j.edges:j.over?.edges||[]).some(e=>fixture.originalEdges[e]===284183)});
        }
        console.log(JSON.stringify(rows));
    """
    )
    result = subprocess.run([node, "-"], input=script, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert sum(row["attached"] for row in rows) == 24
    assert sum(not row["attached"] for row in rows) == 24
    for row in rows:
        assert row["northern"], row["case"]
        assert row["land"] == pytest.approx(row["expected"]["land"], abs=1e-8, rel=1e-12), row["case"]
        assert row["cost"] == pytest.approx(row["expected"]["cost"], abs=1e-8, rel=1e-12), row["case"]
        # The analytic construction and the earlier refined virtual point
        # differ by at most 0.000029 m across the 24 measured off-network rows.
        assert row["carry"] == pytest.approx(row["expected"]["carry"], abs=0.000029, rel=1e-12), row["case"]


def test_every_source_of_the_line_off_the_bank_is_paddled_at_its_price_and_credited_to_its_name(readings):
    rows = {row["name"]: row for row in readings["offsetRoles"]}
    assert set(rows) == {"Shore", "Narrow water", "Landing water", "Open water", "Streams"}
    for name, row in rows.items():
        assert row["whole"]["cost"] == pytest.approx(row["length"] * row["factor"])
        assert row["whole"]["land"] == 0
        # A partial edge pays for the part it runs along, entered and left between the nodes.
        assert row["part"]["cost"] == pytest.approx(row["length"] * row["factor"] / 2)
        assert row["tally"]["sources"] == {name: pytest.approx(row["length"])}
        # Only the stream keeps its digitised direction.
        assert (row["back"] is None) is (name == "Streams")


def test_walking_neither_routes_nor_snaps_to_any_source_of_the_line_off_the_bank(readings):
    for row in readings["offsetRoles"]:
        for walk in row["walking"]:
            assert walk["reachable"] is False
            assert walk["route"] is None
            assert walk["line"] is None
            assert walk["tap"]["node"] == -1
            assert "edge" not in walk["tap"]


def _raw(tap, x, y):
    return tap["node"] == -1 and tap["edge"] == -1 and (tap["x"], tap["y"]) == pytest.approx((x, y))


def test_a_kayak_tap_near_the_bank_takes_the_line_off_the_bank(readings):
    taps = readings["roleTaps"]
    # z17's 6 m finger on the bank still reaches the Shore line 14 m out.
    assert taps["nearBank"]["edge"] == 1
    assert taps["nearBank"]["y"] == pytest.approx(15)
    # Beside a bank anchor and its landing, and beside an open-water link that ends
    # on the bank: the travel line, never the landing, the anchor or the link.
    assert taps["besideAnchor"]["node"] == 3
    assert taps["besideOpenLink"]["node"] == 6
    # Past d + 2.1 m of the line and with no land in reach, the point stays where it was put.
    assert _raw(taps["beyondBand"], 150, -2.5)


def test_a_kayak_tap_keeps_land_launches_and_open_water(readings):
    taps = readings["roleTaps"]
    # The launch's bank end is land (the launch), nearer than the line: the start stays there.
    assert taps["atLaunch"]["node"] == 4
    assert taps["onRoad"]["edge"] == 7
    assert taps["landCloser"]["edge"] == 7
    # Out on the lake the chord under the finger, at z15 and at z12 alike.
    assert taps["offshoreChord"]["edge"] == taps["offshoreFar"]["edge"] == 9
    assert _raw(taps["offshoreRaw"], 300, 60)


def test_an_exact_position_is_not_a_finger(readings):
    taps = readings["roleTaps"]
    assert _raw(taps["exactRaw"], 150, 1)
    assert _raw(taps["exactOnLanding"], 100, 5)
    assert taps["exactOnShore"]["edge"] == 1
    assert taps["exactOnShore"]["y"] == pytest.approx(15)


def test_a_kayak_tap_takes_its_own_island_and_the_middle_of_a_channel(readings):
    taps = readings["roleTaps"]
    assert taps["islandA"]["edge"] == 11
    assert taps["islandB"]["edge"] == 12
    assert taps["nearerB"]["edge"] == 12
    assert taps["narrow"]["edge"] == 13
    assert taps["narrow"]["y"] == pytest.approx(10)


def test_a_tap_on_a_stream_stays_on_it_and_keeps_its_direction(readings):
    tap = readings["roleTaps"]["stream"]
    assert tap["edge"] == 10
    assert tap["along"] == pytest.approx(100)
    assert readings["streamEnds"] == {"leaving": [13], "entering": [12]}


def test_walking_and_a_graph_without_roles_snap_as_before(readings):
    for walk in readings["roleWalking"]:
        assert _raw(walk["near"], 150, 1)
        assert walk["far"]["edge"] == 7
        assert walk["farKind"] == "path"
    assert readings["roleless"]["roles"] is False
    # Without roles every paddled line is a line to snap to, the landing included.
    assert readings["roleless"]["onLanding"]["edge"] == 4


def test_a_raw_kayak_point_enters_no_landing_in_its_middle(readings):
    for row in readings["roleEntries"]:
        # d is measured to the Shore line 9 m away, not to the landing 0.5 m away.
        assert row["nearest"] == pytest.approx(9)
        assert not {4, 5} & set(row["edges"])
        assert sorted(row["edges"]) == sorted(row["referenceEdges"])
        for label in ("land", "cost"):
            assert row["actual"][label] == pytest.approx(row["expected"][label], abs=1e-8, rel=1e-12)


def test_seeded_joined_search_with_roles_matches_the_unpruned_reference(readings):
    rows = readings["roleDifferential"]
    assert len(rows) == 64
    assert any(row["expected"]["edges"] for row in rows)
    for row in rows:
        for label in ("land", "cost"):
            expected = row["expected"][label]
            assert abs(row["actual"][label] - expected) <= 1e-8 + 1e-12 * abs(expected), row


def _same(actual, expected):
    for key in ("land", "cost"):
        assert actual[key] == pytest.approx(expected[key], rel=1e-12, abs=1e-8)


def test_a_walk_does_not_turn_at_a_node_that_lies_only_on_water(readings):
    for row in readings["walkingTurns"]:
        # Main's rule turned at W, the Shore line's node beyond the lake, in both settings.
        assert row["everyNode"]["shape"] == "pivot at 0"
        assert row["walkNodes"][:2] == [0, 0]
        assert row["shape"] != "pivot at 0" and "Shore" not in row["shape"]
        _same(row["actual"], row["expected"])
        if not row["road"]:
            # With nothing else to turn at, the straight line across the water is the answer.
            assert row["shape"] == "straight"
            _same(row["actual"], row["direct"])


def test_a_walk_takes_a_way_nearby_instead_of_the_water_node(readings):
    rows = {(r["road"], r["staying"]): r for r in readings["walkingTurns"]}
    assert rows[True, False]["shape"] in ("via road", "along a way")
    assert rows[True, False]["actual"]["cost"] < rows[True, False]["direct"]["cost"]
    assert rows[True, False]["actual"]["cost"] > rows[True, False]["everyNode"]["label"]["cost"]


def test_the_straight_line_stays_where_it_is_cheapest(readings):
    for row in readings["walkingTurns"]:
        assert row["shortShape"] == "straight"


def test_the_kayak_does_not_read_the_walking_rule(readings):
    for row in readings["walkingTurns"]:
        kayak = row["kayak"]
        assert kayak["label"] == kayak["again"] and kayak["shape"] == kayak["againShape"]
        _same(kayak["label"], kayak["expected"])


def test_seeded_walking_search_matches_the_reference_and_turns_only_on_ways(readings):
    rows = readings["walkingDifferential"]
    assert len(rows) == 64 and all(r["waterOnly"] > 0 for r in rows)
    for row in rows:
        _same(row["actual"], row["expected"])
        assert row["turnsOnWay"]

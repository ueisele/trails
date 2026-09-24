        (function () {
            var map = {{ this._parent.get_name() }};
            var PLAN = {{ this.plan_json }};

            // **Stay on paths: the reader's own price for open ground.** The
            // build prices a metre off the paths at `offPathFactor` metres of
            // path -- three, here -- and that is a judgement about ground
            // nobody has looked at. Measured at Krutåga: 740 m straight from
            // the last junction to a goal 100 m off a road counted 2.2 km, and
            // the road round, 2.6 km with a bridge, lost to it. At ten to one
            // the road wins by three kilometres. A switch and not a better
            // number, because there is no better number: which of the two a
            // reader wants depends on what they can see from where they stand.
            // Wherever no network reaches, a straight line stays the answer --
            // this changes the trade, not what is possible.
            var PATHS_FACTOR = 10;
            // Read when first asked and not when this runs: the key is the
            // panel's prefix, and the panel is not always there yet.
            var stayingOnPaths = null;
            function staying() {
                if (stayingOnPaths === null) {
                    try { stayingOnPaths = window.localStorage.getItem(keptKey() + '.paths') === 'yes'; }
                    catch (blocked) { stayingOnPaths = false; }
                }
                return stayingOnPaths;
            }
            function offPath() { return staying() ? PATHS_FACTOR : PLAN.offPathFactor; }
            function stayOnPaths(want) {
                if (want === undefined) { return staying(); }
                want = !!want;
                if (want === staying()) { return stayingOnPaths; }
                stayingOnPaths = want;
                try {
                    if (want) { window.localStorage.setItem(keptKey() + '.paths', 'yes'); }
                    else { window.localStorage.removeItem(keptKey() + '.paths'); }
                } catch (blocked) { /* remembered for this visit only */ }
                // **Everything priced is priced again.** The legs follow from
                // the points and are made afresh under the new price; the way
                // to a goal is asked for from where the reader stands, as any
                // fix would ask for it.
                routing = null;
                if (points.length > 1) {
                    legs.forEach(function (leg) { if (leg) { undraw(leg.layers); } });
                    legs = [];
                    withGraph(function (graph) { relink(graph, true); }, function () { refresh(); });
                }
                if (goalAt) { goalToken = null; routeToGoal(goalHere()); }
                return stayingOnPaths;
            }

            var paddling = null;
            function kayak() {
                if (paddling === null) {
                    try { paddling = window.localStorage.getItem(keptKey() + '.kayak') === 'yes'; }
                    catch (blocked) { paddling = false; }
                }
                return paddling;
            }
            function paddle(want) {
                if (want === undefined) { return kayak(); }
                want = !!want;
                if (want === kayak()) { return paddling; }
                paddling = want;
                try {
                    if (want) { window.localStorage.setItem(keptKey() + '.kayak', 'yes'); }
                    else { window.localStorage.removeItem(keptKey() + '.kayak'); }
                } catch (blocked) { /* remembered for this visit only */ }
                routing = null;
                if (points.length > 1) {
                    legs.forEach(function (leg) { if (leg) { undraw(leg.layers); } });
                    legs = [];
                    withGraph(function (graph) { relink(graph, true); }, function () { refresh(); });
                }
                if (goalAt) { goalToken = null; routeToGoal(goalHere()); }
                refreshGoal();
                refresh();
                return paddling;
            }

            // Everything named that the map draws at a position, as a table:
            // name, what it is and where. The markers themselves cannot answer
            // this — their names are inside popup HTML — and a route's file
            // reading 'Lavasshytta -> Sæterskaret skogstue -> Bønå ferjekai'
            // rather than three coordinates is the whole of what it buys.
            var NAMED = {{ this.points_json }};

            // The route's own colours. Near-black over the pale topo backdrop,
            // which nothing else on this map uses: a plan is the reader's own
            // and should not read as another dataset. A pale wide stroke under
            // a dark narrow one, or it disappears over a dark line.
            var ROUTE = '#111111', CASING = '#ffffff', WAITING = '#9e9e9e';
            //: How far the casing stands out beyond the line on each side. The
            //: pair used to be 6 and 2.6 written down; the line is the build's
            //: to decide now -- it is drawn as wide as the widest line it can be
            //: planned along -- and this is what is left of that pair, which is
            //: what makes the route legible over a dark line rather than what
            //: makes it thick.
            var HALO_PX = 1.7;

            // What the payload's own header calls a crossing and an inferred
            // connector, handed in rather than spelled here: renaming either in
            // trails.routing.sources would otherwise leave this page reading
            // every ferry as walked ground, and nothing would look wrong.
            var CROSSING = PLAN.crossingKind, CONNECTOR = PLAN.connectorKind, PADDLE = PLAN.paddleKind, PORTAGE = PLAN.portageKind;

            // How each kind is drawn. Routed is a line; ground drawn straight
            // across is dashed exactly as the profile dashes it; a crossing is a
            // wider gap still, because it is not walked at all. A leg not yet
            // worked out is neither, and says so by being grey.
            //
            // **The crossing's key is the name that arrived, not the word
            // 'ferry'.** Spelled out, a rename in trails.routing.sources would
            // leave this table without an entry for the kind routedParts emits,
            // and an undefined dashArray draws a fjord crossing as a solid line
            // indistinguishable from walked ground — which is the one thing this
            // page must never draw, and nothing about it would look wrong.
            var DASH = {routed: null, paddled: null, land: '5,4', water: '2,8', waiting: '1,6'};
            DASH[CROSSING] = '2,8';

            // ---- what the panel owns and this must not write again ----------
            // Laying a run of edges end to end and the metre this page measures
            // distance with both live in the profile panel. A second walk here
            // would eventually disagree with the one the panel draws and the
            // export writes, and a route composed by the wrong walk still looks
            // like a route. Read late rather than at load, so the two scripts
            // need no order between them beyond the one the builder gives.
            var owned = null;

            function panel() {
                if (!owned) { owned = window.trailsProfilePanel || null; }
                return owned;
            }

            // ---- the router --------------------------------------------------
            // Built on the first route asked for and then kept. The payload
            // carries edges, nodes and geometry and nothing else — no cost
            // column, deliberately, because a cost is length times the source's
            // factor and the page has both. Deriving it here is a pass over the
            // geometry; shipping it would be a megabyte of numbers the browser
            // can work out for itself.
            var routing = null;

            function router(graph) {
                if (routing) { return routing; }
                var edges = graph.header.edges, nodes = graph.header.nodes, i;
                // Hoisted out of a loop that runs once per vertex, of which
                // there are 948,465.
                var between = panel().metresBetween;

                var length = new Float64Array(edges), cost = new Float64Array(edges), land = new Float64Array(edges), snapNodes = new Uint8Array(nodes);
                for (i = 0; i < edges; i += 1) {
                    var run = 0;
                    for (var v = graph.vertexAt[i] + 1; v < graph.vertexAt[i + 1]; v += 1) {
                        run += between(graph.coordinates[2 * v - 2], graph.coordinates[2 * v - 1],
                                       graph.coordinates[2 * v], graph.coordinates[2 * v + 1]);
                    }
                    length[i] = run;
                }

                // How long the chain each edge lies on is, which only a crossing
                // needs. The payload lays a chain's edges out as one contiguous
                // run, so this is one pass and no index.
                var whole = new Float64Array(edges);
                for (var chain = 0; chain < graph.header.chains; chain += 1) {
                    var first = graph.chainAt[chain], last = graph.chainAt[chain + 1], along = 0;
                    for (i = first; i < last; i += 1) { along += length[i]; }
                    for (i = first; i < last; i += 1) { whole[i] = along; }
                }

                for (i = 0; i < edges; i += 1) {
                    var source = graph.header.sources[graph.sources[i]];
                    // Ferries cross water too: paddle and ferry edges count no
                    // land; every other kind counts its metres in a kayak.
                    // The ferry's flat secondary price remains below.
                    land[i] = kayak() && source.kind !== PADDLE && source.kind !== CROSSING ? length[i] : 0;
                    if (source.kind !== CROSSING && source.kind !== CONNECTOR && (kayak() || (source.kind !== PADDLE && source.kind !== PORTAGE))) {
                        snapNodes[graph.fromNode[i]] = 1; snapNodes[graph.toNode[i]] = 1;
                    }
                    if ((source.kind === PADDLE || source.kind === PORTAGE) && !kayak()) { cost[i] = Infinity; }
                    else if (source.kind === PORTAGE) { cost[i] = length[i] * offPath() * PLAN.portageFactor; }
                    else if (source.flatM === undefined) {
                        cost[i] = length[i] * source.factor * (kayak() && source.kind !== PADDLE && source.kind !== CROSSING
                            ? PLAN.portageFactor : 1);
                    }
                    // A crossing costs the header's flat figure rather than its
                    // length: taking a ferry is the same decision whether it is
                    // 2 km or 20, so weighting it by distance means nothing and
                    // would send a route across a fjord to save two hundred
                    // metres.
                    //
                    // **And the flat figure is the whole crossing's, not each
                    // piece's.** A crossing is a chain, and noding cuts it
                    // wherever something meets it: 15 of the 21 ferry chains
                    // here are in several pieces and the longest is in seven.
                    // Charging the flat cost per edge priced that one at 35 km
                    // of walking instead of 5, and a page that does so refuses
                    // crossings the build priced as affordable — the route the
                    // reader is shown would then disagree with the network the
                    // rest of the map was measured on. Split in proportion, as
                    // trails.routing.graph._cost splits it.
                    else { cost[i] = source.flatM * (whole[i] > 0 ? length[i] / whole[i] : 1); }
                }

                // Compressed adjacency: count what meets each node, prefix-sum,
                // then fill. An array of arrays over 116,967 nodes costs more in
                // allocation alone than every search a reader will ever run.
                var at = new Int32Array(nodes + 2);
                for (i = 0; i < edges; i += 1) { at[graph.fromNode[i] + 2] += 1; at[graph.toNode[i] + 2] += 1; }
                for (i = 2; i < at.length; i += 1) { at[i] += at[i - 1]; }
                var arc = new Int32Array(2 * edges);
                for (i = 0; i < edges; i += 1) {
                    arc[at[graph.fromNode[i] + 1]] = i; at[graph.fromNode[i] + 1] += 1;
                    arc[at[graph.toNode[i] + 1]] = i; at[graph.toNode[i] + 1] += 1;
                }
                // Filling leaves at[v + 1] at the end of node v's arcs, which is
                // where node v + 1's begin, so afterwards node v owns
                // arc[at[v] .. at[v + 1]).
                routing = {length: length, cost: cost, land: land, at: at, arc: arc, snapNodes: snapNodes,
                           best: new Float64Array(nodes), bestLand: new Float64Array(nodes), viaEdge: new Int32Array(nodes), viaNode: new Int32Array(nodes)};
                return routing;
            }

            // A binary heap over parallel arrays. Entries are never removed
            // when a node is reached more cheaply — the stale one is popped and
            // recognised by its lexicographic label. Keeping stale entries is
            // cheaper here than finding and removing them.
            // In a kayak, any saving on land wins before the old price is read.
            // Walking supplies zero land throughout, retaining its old ordering.
            function cheaper(land, cost, otherLand, otherCost) {
                return cost < Infinity && (land < otherLand || (land === otherLand && cost < otherCost));
            }

            function Heap() { this.node = []; this.cost = []; this.land = []; }

            Heap.prototype.swap = function (a, b) {
                var node = this.node[a], cost = this.cost[a], land = this.land[a];
                this.node[a] = this.node[b]; this.cost[a] = this.cost[b]; this.land[a] = this.land[b];
                this.node[b] = node; this.cost[b] = cost; this.land[b] = land;
            };

            Heap.prototype.push = function (node, cost, land) {
                var at = this.node.length;
                this.node.push(node); this.cost.push(cost); this.land.push(land || 0);
                while (at > 0) {
                    var parent = (at - 1) >> 1;
                    if (!cheaper(this.land[at], this.cost[at], this.land[parent], this.cost[parent])) { break; }
                    this.swap(parent, at); at = parent;
                }
            };

            // Sifting down ends because the position it moves to is always a
            // child of the one it was at, so it strictly increases and the loop
            // runs at most as deep as the heap. That is a property of the array
            // and not of the graph, which is why it carries no bound.
            Heap.prototype.pop = function () {
                var top = {node: this.node[0], cost: this.cost[0], land: this.land[0]}, last = this.node.length - 1;
                this.node[0] = this.node[last]; this.cost[0] = this.cost[last]; this.land[0] = this.land[last];
                this.node.pop(); this.cost.pop(); this.land.pop();
                var at = 0, size = this.node.length;
                while (true) {
                    var left = 2 * at + 1, right = left + 1, least = at;
                    if (left < size && cheaper(this.land[left], this.cost[left], this.land[least], this.cost[least])) { least = left; }
                    if (right < size && cheaper(this.land[right], this.cost[right], this.land[least], this.cost[least])) { least = right; }
                    if (least === at) { break; }
                    this.swap(least, at); at = least;
                }
                return top;
            };

            // Dijkstra over the weighted graph, once per new leg. Nothing but
            // the source factors weighs an edge: elevation-aware routing is a
            // decision nobody has taken, and the per-edge ascent it would need
            // is deliberately not in the payload.
            // Whether a point is somewhere the router can start from or end
            // at: on a node, or on an edge at some distance along it.
            function onNetwork(point) { return point.node >= 0 || point.edge >= 0; }

            // **How a point gets on to the network, and what that costs.** A
            // node is on it for nothing. A point on an edge is on it at either
            // end of that edge, for the metres between at the edge's own price
            // -- and the piece walked to get there travels along as a *cut*,
            // so the leg draws it as the path it is rather than as a line
            // across to the junction. A point on neither has no ends here;
            // `joinedRoute` prices its way in over the ground. A cut runs from
            // the point to the node; `flipCut` turns it round for the far end.
            // Both searches keep both arcs; it is the journey's direction that
            // matters, even when the search works back from its destination.
            function allowed(graph, edge, downstream) {
                var kind = graph.header.sources[graph.sources[edge]].kind;
                return (kayak() || (kind !== PADDLE && kind !== PORTAGE)) &&
                    (!graph.oneWay[edge] || downstream);
            }

            function endsOf(graph, point, entering) {
                if (point.edge >= 0) {
                    var kind = graph.header.sources[graph.sources[point.edge]].kind;
                    if (kind === CROSSING || ((kind === PADDLE || kind === PORTAGE) && !kayak())) { return []; }
                }
                if (point.node >= 0) { return [{node: point.node, cost: 0, land: 0, cut: null}]; }
                if (!(point.edge >= 0)) { return []; }
                var work = router(graph), edge = point.edge;
                var length = work.length[edge], rate = length > 0 ? work.cost[edge] / length : 0;
                var along = Math.max(0, Math.min(length, point.along || 0)), landRate = length > 0 ? work.land[edge] / length : 0;
                return [{node: graph.fromNode[edge], cost: along * rate, land: along * landRate, cut: {edge: edge, from: along, to: 0}},
                        {node: graph.toNode[edge], cost: (length - along) * rate, land: (length - along) * landRate, cut: {edge: edge, from: along, to: length}}].filter(function (end) {
                            return allowed(graph, edge, entering ? end.cut.from >= end.cut.to : end.cut.to >= end.cut.from);
                        });
            }

            function flipCut(cut) { return cut ? {edge: cut.edge, from: cut.to, to: cut.from} : null; }

            function route(graph, from, to) { return routeBetween(graph, {node: from}, {node: to}); }

            // **Dijkstra from every end of one point to every end of the
            // other.** Seeded with each way on to the network and what it
            // costs, and stopped when nothing left in the heap can beat the
            // cheapest way off it already found -- so a point on an edge is
            // routed from whichever end of that edge the way actually goes,
            // rather than from the nearer one and back. Two points on one
            // edge are joined by the piece of it between them, unless some
            // way round is cheaper, which on a loop it can be.
            function routeBetween(graph, from, to) {
                var work = router(graph);
                var best = work.best, bestLand = work.bestLand, viaEdge = work.viaEdge, viaNode = work.viaNode;
                var seeds = endsOf(graph, from), targets = endsOf(graph, to, true), i;
                if (!seeds.length || !targets.length) { return null; }
                var direct = null;
                if (from.edge >= 0 && from.edge === to.edge &&
                        allowed(graph, from.edge, (to.along || 0) >= (from.along || 0))) {
                    var rate = work.length[from.edge] > 0 ? work.cost[from.edge] / work.length[from.edge] : 0;
                    direct = {edges: [], reversed: [], cost: Math.abs((to.along || 0) - (from.along || 0)) * rate,
                              land: work.length[from.edge] > 0 ? Math.abs((to.along || 0) - (from.along || 0)) * work.land[from.edge] / work.length[from.edge] : 0,
                              head: {edge: from.edge, from: from.along || 0, to: to.along || 0}, tail: null};
                }
                best.fill(Infinity); bestLand.fill(Infinity); viaEdge.fill(-1); viaNode.fill(-1);
                var seedAt = {};
                var heap = new Heap();
                for (i = 0; i < seeds.length; i += 1) {
                    if (!cheaper(seeds[i].land, seeds[i].cost, bestLand[seeds[i].node], best[seeds[i].node])) { continue; }
                    best[seeds[i].node] = seeds[i].cost; bestLand[seeds[i].node] = seeds[i].land; seedAt[seeds[i].node] = seeds[i];
                    heap.push(seeds[i].node, seeds[i].cost, seeds[i].land);
                }
                // The cheapest whole way found so far, read off the targets:
                // what a target's node was reached for plus its own way off.
                var found = null;
                function arrivedAt(node) {
                    for (var t = 0; t < targets.length; t += 1) {
                        if (targets[t].node !== node) { continue; }
                        var whole = best[node] + targets[t].cost, wholeLand = bestLand[node] + targets[t].land;
                        if (cheaper(wholeLand, whole, found ? found.land : Infinity, found ? found.cost : Infinity)) {
                            found = {target: targets[t], cost: whole, land: wholeLand};
                        }
                    }
                }
                for (i = 0; i < seeds.length; i += 1) { arrivedAt(seeds[i].node); }

                // Every loop over this graph is bounded and throws when it
                // reaches the bound. A settled node is never settled twice and
                // every stale entry was pushed by a relaxation, so the pops
                // cannot exceed one per node plus one per arc; anything past
                // that is a defect, and a defect that runs for ever in a page
                // is indistinguishable from a page that has hung.
                var pops = 0, mostPops = graph.header.nodes + 2 * graph.header.edges + 1;
                while (heap.node.length) {
                    pops += 1;
                    if (pops > mostPops) { throw new Error('the search took more than ' + mostPops + ' steps'); }
                    var taken = heap.pop();
                    if (cheaper(bestLand[taken.node], best[taken.node], taken.land, taken.cost)) { continue; }
                    // Popped in lexicographic order, so once the top is no cheaper
                    // than a whole way already in hand, no later one can be.
                    if (found && !cheaper(taken.land, taken.cost, found.land, found.cost)) { break; }
                    for (var a = work.at[taken.node]; a < work.at[taken.node + 1]; a += 1) {
                        var edge = work.arc[a];
                        if (!allowed(graph, edge, graph.fromNode[edge] === taken.node)) { continue; }
                        var other = graph.fromNode[edge] === taken.node ? graph.toNode[edge] : graph.fromNode[edge];
                        var reached = taken.cost + work.cost[edge], reachedLand = taken.land + work.land[edge];
                        if (cheaper(reachedLand, reached, bestLand[other], best[other])) {
                            best[other] = reached; bestLand[other] = reachedLand; viaEdge[other] = edge; viaNode[other] = taken.node;
                            heap.push(other, reached, reachedLand);
                            arrivedAt(other);
                        }
                    }
                }
                if (direct && (!found || !cheaper(found.land, found.cost, direct.land, direct.cost))) { return direct; }
                if (!found) { return null; }

                // Walking the path back out. **Bounded, and the sentinel is
                // tested for rather than indexed with**: a typed array answers
                // a negative index with undefined rather than raising, so an
                // unset predecessor would put undefined into the geometry and
                // carry on, and a walk that never reached its start would
                // append for ever. The Python sibling of this loop, written
                // without either guard, took 42 GB and the kernel killed it.
                // It stops at a seed -- the node nothing relaxed -- which is
                // the end the way came on to the network by.
                var edges = [], reversed = [], walk = found.target.node, steps = 0;
                while (viaEdge[walk] >= 0) {
                    steps += 1;
                    if (steps > graph.header.edges) { throw new Error('the way back is longer than the graph'); }
                    var used = viaEdge[walk], before = viaNode[walk];
                    if (before < 0) { throw new Error('node ' + walk + ' was reached by nothing'); }
                    edges.push(used);
                    // An edge's geometry and its heights run from its own
                    // from-node to its own to-node, and the walk can arrive at
                    // it from either end. Read off the predecessor rather than
                    // off the edge's own ends, which say nothing about
                    // direction on the fourteen edges here that begin and end
                    // at the same node.
                    reversed.push(graph.fromNode[used] !== before);
                    walk = before;
                }
                var seed = seedAt[walk];
                if (!seed) { throw new Error('the way back ended at node ' + walk + ', which is no seed'); }
                edges.reverse(); reversed.reverse();
                return {edges: edges, reversed: reversed, cost: found.cost, land: found.land,
                        head: seed.cut, tail: flipCut(found.target.cut)};
            }

            // Optimistic land distances from the start include travel over the
            // network, not just a globally cheapest entry. Whole-metre floors
            // add exactly and stay below floating-point sums in either order.
            function entryLandFloors(graph, starts, limit) {
                var work = router(graph), nodes = graph.header.nodes;
                var bounds = work.entryBounds || (work.entryBounds = new Float64Array(nodes));
                bounds.fill(Infinity);
                var heap = new Heap(), ceiling = Math.floor(limit), i;
                if (!Number.isSafeInteger(ceiling)) { throw new Error('the entry land ceiling is not a safe integer'); }
                function seed(node, value) {
                    value = Math.floor(value);
                    if (value <= ceiling && value < bounds[node]) {
                        bounds[node] = value; heap.push(node, 0, value);
                    }
                }
                for (i = 0; i < starts.length; i += 1) { seed(starts[i].node, starts[i].land); }
                var pops = 0, most = nodes + 2 * graph.header.edges;
                while (heap.node.length) {
                    if (++pops > most) { throw new Error('the entry floor search exceeds the graph'); }
                    var taken = heap.pop();
                    if (taken.land > bounds[taken.node]) { continue; }
                    for (var a = work.at[taken.node]; a < work.at[taken.node + 1]; a += 1) {
                        var edge = work.arc[a];
                        if (!allowed(graph, edge, graph.fromNode[edge] === taken.node)) { continue; }
                        var other = graph.fromNode[edge] === taken.node ? graph.toNode[edge] : graph.fromNode[edge];
                        seed(other, taken.land + Math.floor(work.land[edge]));
                    }
                }
                return bounds;
            }

            // ---- a way to somewhere that is not on the network ----------------
            // **A layer of connectors over the graph, and not a point moved on
            // to it.** Reported from the phone: a goal with stops on the way
            // came out as a 138 km walk between places 20 km apart, and one of
            // the stops stood visibly beside the line instead of on it. Both
            // are the same defect and both were measured here. A stop was
            // *snapped* -- replaced by the nearest node within `snapM` -- so the
            // mark stayed where the reader put it while the way ran from
            // somewhere else; and having replaced it, the router was asked for
            // the way between two node numbers and took whatever it found,
            // which for a node on a fragment of path in the next valley was a
            // 66 km loop. Neither step ever asked whether the answer was worth
            // having.
            //
            // **Nothing is snapped here, and there is no second graph either.**
            // Every node is joined to each end of the leg by a connector -- the
            // straight walk to it, priced at `offPathFactor` -- and the leg's
            // own straight line is one more connector between the two ends.
            // The cheapest way through that is the answer, and the three
            // readings a leg could have stop being three cases: walking
            // straight is the direct connector winning, a routed leg is two
            // connectors with the network between them, and *most of the way is
            // a path* is the same thing with one long connector on the end. No
            // threshold and no reach anywhere in it, because the comparison is
            // the rule.
            //
            // **One entry and one exit**, which is what makes this a walk to
            // the network rather than a shortcut across it: a route free to
            // leave the paths wherever they bend would cut every corner on the
            // map.
            //
            // Held together by the cost being in metres throughout. An edge
            // costs its length times its source's factor -- 1.00 for a marked
            // route up to 1.30 for an inferred connector -- so a connector
            // priced at `offPathFactor` metres to the metre is the same
            // currency, and the comparison between walking and routing is one
            // subtraction rather than two units.
            //
            // Which also puts a ceiling on an answer, and it is the one thing
            // the rule this replaced could not promise. A leg costs at least
            // its own metres, every factor here being at least one, and it may
            // not cost more than the direct connector or the direct connector
            // would have won -- so no leg can ever be longer than the straight
            // line's price. Over ground that is `offPathFactor` times the
            // line it could have flown. The 66 km answer to a 2.15 km question
            // was not a near miss; it was a sum nobody was doing.
            //
            // **And a connector is priced by what it crosses**, which is where
            // the water comes in. Reported from the phone with a screenshot: a
            // goal on the headland across a 1.2 km sound from the end of the
            // path was reached by a dotted line over the water, because the
            // road round the head of the sound is longer than 3.6 km and
            // nothing priced the sound. A metre of a connector that the
            // graph's water grid says is sea or lake costs `waterFactor`
            // instead of `offPathFactor`, and the rest follows from the same
            // comparison: the road wins where there is one, and where there is
            // none -- an island with no path -- every connector crosses water
            // and the one that crosses least wins. **A price, not a rule**, so
            // the second case needs no case of its own.
            //
            // **Walking and zero-land kayak ways price exits lazily.** A
            // node is seeded at the cheapest connector metre in the mode,
            // plus a sampled dry-prefix land floor in a kayak. Both halves
            // are lower bounds. The true price is worked out when that floor
            // reaches the top of the queue. It is the
            // ordinary trick for an edge whose weight is dear to compute, and
            // it is what keeps the grid from being asked about 117,000
            // connectors on every tick of a drag. The bound and the pruning
            // are unchanged, because a floor is all either of them needs.
            // With a dry end and positive kayak land ceiling most floors remain eligible;
            // pricing those exits directly avoids a queue that cannot prune.
            //
            // **A floor is not a label.** The first version wrote the floor
            // into `best` and priced it for real when the node was popped.
            // Measured against an eagerly priced search on seven legs to one
            // headland, three disagreed -- one of them by a straight walk of
            // 2.1 km where the road was there to take. The fault: a settled
            // node offers its neighbour a way in, the neighbour's floor is
            // cheaper and the offer is refused, and then the floor turns out
            // to be a fjord and is raised -- but the neighbour that offered
            // is settled and never offers again. So floors live in a queue of
            // their own and `best` holds only prices that are exact: a
            // relaxation is refused by nothing that can later be withdrawn.
            function joinedRoute(graph, from, to) {
                var nodes = graph.header.nodes;
                if (!nodes) { return null; }
                var far = panel().metresBetween;
                var off = cheapestMetre(graph);
                var work = router(graph);
                var best = work.best, bestLand = work.bestLand, viaEdge = work.viaEdge, viaNode = work.viaNode;
                var leaveLengths = null, leaveDry = null;
                if (kayak()) {
                    leaveLengths = work.leaveLengths || (work.leaveLengths = new Float64Array(nodes));
                    leaveDry = work.leaveDry || (work.leaveDry = new Uint8Array(nodes));
                }
                viaEdge.fill(-1); viaNode.fill(-1);
                // The direct connector: the line the reader would walk if the
                // network were not there at all. It is what every other answer
                // has to beat, and it is why no case below needs a threshold --
                // two sides of a triangle are never shorter than the third, so
                // an entry that leads nowhere loses to it by itself. Priced by
                // what it crosses, like every connector: over a sound it is
                // dear, and that is what lets the road round beat it.
                var plainPrice = connectorPrice(graph, from.lon, from.lat, to.lon, to.lat);
                var plain = plainPrice.cost, plainLand = plainPrice.land;
                // Two queues: the floors, and the prices that are exact.
                var floors = new Heap(), heap = new Heap(), i;
                // **Seeded at every node at once, from the far end.** That is
                // the connector layer itself and not a trick: `best[n]` starts
                // at what it costs to leave the network at n and walk the rest,
                // so what the search settles at n is the whole cost of getting
                // from n to where the leg ends -- and the entry can then be
                // chosen knowing it, which is the thing the old two searches
                // could not do.
                //
                // **Initially bounded by the direct connector, lexicographically.**
                // A node whose suffix already reaches its pair cannot be part of an answer
                // that beats it -- the entry walk on top can only add -- and
                // every node on an optimal way out is cheaper still than the one
                // before it, so nothing that matters is pruned. Measured on
                // one 13.6 km leg, routed and redrawn: 157 ms seeding and
                // exhausting the whole graph, 64 ms bounded. Seeded with the
                // cheapest connector price, which is a floor on the true one -- and
                // into the floors' own queue, not into `best`.
                best.fill(Infinity); bestLand.fill(Infinity);
                // **A far end standing on the network leaves it by its own
                // edge.** Its two ends are seeded with the metres along that
                // edge at the edge's own price -- exact, so straight into the
                // heap -- and no node is seeded with a walk over the ground: a
                // point on a line is reached along the line, which is the
                // whole of what a tap in the middle of a long trail means.
                var tailCuts = {};
                var toEnds = endsOf(graph, to, true);
                for (i = 0; i < toEnds.length; i += 1) {
                    if (!cheaper(toEnds[i].land, toEnds[i].cost, plainLand, plain) ||
                            !cheaper(toEnds[i].land, toEnds[i].cost, bestLand[toEnds[i].node], best[toEnds[i].node])) { continue; }
                    best[toEnds[i].node] = toEnds[i].cost; bestLand[toEnds[i].node] = toEnds[i].land;
                    tailCuts[toEnds[i].node] = flipCut(toEnds[i].cut);
                    heap.push(toEnds[i].node, toEnds[i].cost, toEnds[i].land);
                }
                var head = -1, headCut = null, cheapest = plain, leastLand = plainLand, prefixSamples = 16;
                var fromEnds = endsOf(graph, from);
                var entryBox = kayak() && !fromEnds.length ? dryConnectorBox(graph, from) : null, entryLand = 0;
                // Every network way needs an entry connector. A dry box around
                // the tap bounds all of them without sampling every long line.
                // Add only their smallest land floor to a suffix's bound.
                if (entryBox) {
                    entryLand = Infinity;
                    for (i = 0; i < nodes; i += 1) {
                        var entryLength = far(from.lon, from.lat, graph.nodeLon[i], graph.nodeLat[i]);
                        entryLand = Math.min(entryLand, connectorBoxLand(graph, from, graph.nodeLon[i], graph.nodeLat[i], entryLength, entryBox));
                        if (entryLand === 0) { break; }
                    }
                }
                // A wet node near the dry tap offers a cheap initial whole
                // way, when both ends are off-network. Price both connectors
                // exactly: this only tightens the bound if the way is better,
                // and every other entry remains eligible to beat it.
                if (kayak() && !fromEnds.length && !toEnds.length) {
                    var dryPoint = !connectorWaterAt(graph, from.lon, from.lat) ? from : (!connectorWaterAt(graph, to.lon, to.lat) ? to : null);
                    var wetNode = -1, nearestWet = Infinity;
                    if (dryPoint && !work.wetNodes) {
                        work.wetNodes = new Uint8Array(nodes);
                        for (i = 0; i < nodes; i += 1) {
                            work.wetNodes[i] = connectorWaterAt(graph, graph.nodeLon[i], graph.nodeLat[i]) ? 1 : 0;
                        }
                    }
                    // Only the two exact connector prices make an incumbent.
                    // Approximate nearness chooses a candidate, never a bound.
                    var lonScale = dryPoint ? Math.cos(dryPoint.lat * Math.PI / 180) : 1;
                    for (i = 0; dryPoint && i < nodes; i += 1) {
                        if (!work.wetNodes[i]) { continue; }
                        var dx = (dryPoint.lon - graph.nodeLon[i]) * lonScale, dy = dryPoint.lat - graph.nodeLat[i];
                        var away = dx * dx + dy * dy;
                        if (away < nearestWet) { nearestWet = away; wetNode = i; }
                    }
                    if (wetNode >= 0) {
                        var wetHead = connectorPrice(graph, from.lon, from.lat, graph.nodeLon[wetNode], graph.nodeLat[wetNode]);
                        var wetTail = connectorPrice(graph, graph.nodeLon[wetNode], graph.nodeLat[wetNode], to.lon, to.lat);
                        // This estimate controls work only. The floor still
                        // counts actual samples; no distance to water is
                        // treated as land without reading the connector.
                        if (graph.water) {
                            var dryMetres = dryPoint === from ? wetHead.land : wetTail.land;
                            prefixSamples = Math.min(32, Math.max(16, 1 + Math.ceil(dryMetres / graph.water.cellM)));
                        }
                        if (cheaper(wetHead.land + wetTail.land, wetHead.cost + wetTail.cost, leastLand, cheapest)) {
                            head = wetNode; leastLand = wetHead.land + wetTail.land; cheapest = wetHead.cost + wetTail.cost;
                            best[wetNode] = wetTail.cost; bestLand[wetNode] = wetTail.land;
                            heap.push(wetNode, wetTail.cost, wetTail.land);
                        }
                    }
                }
                var entryBounds = kayak() && fromEnds.length && leastLand > 0 ? entryLandFloors(graph, fromEnds, leastLand) : null;
                var eager = kayak() && leastLand > 0 && (!connectorWaterAt(graph, from.lon, from.lat) || !connectorWaterAt(graph, to.lon, to.lat));
                for (i = 0; i < nodes && !toEnds.length; i += 1) {
                    if (entryBounds && entryBounds[i] > leastLand) { continue; }
                    var leaveM = far(graph.nodeLon[i], graph.nodeLat[i], to.lon, to.lat), leave = leaveM * off;
                    var leaveLand = 0;
                    // A dry end and positive land ceiling otherwise leave
                    // almost every floor eligible. Price exits in this linear
                    // pass; the exact queue settles the same suffix labels.
                    // Wet ends retain the lazy queue's useful water-way bound.
                    if (eager) {
                        // The integer prefix floor plus floor(suffix land)
                        // bounds a whole way. Subtract one metre when comparing
                        // it with an unrounded connector's land instead.
                        var requiredIn = entryBounds ? Math.max(entryLand, entryBounds[i] - 1) : entryLand;
                        if (!cheaper(requiredIn, leave, leastLand, cheapest)) { continue; }
                        var localBound = bestLand[i] + requiredIn < leastLand;
                        var exact = connectorPrice(graph, graph.nodeLon[i], graph.nodeLat[i], to.lon, to.lat,
                            localBound ? bestLand[i] : leastLand, localBound ? 0 : requiredIn,
                            {length: leaveM, dry: 0});
                        if (cheaper(exact.land, exact.cost, bestLand[i], best[i])) {
                            best[i] = exact.cost; bestLand[i] = exact.land;
                            heap.push(i, exact.cost, exact.land);
                        }
                        continue;
                    }
                    if (kayak()) {
                        var pieces = graph.water ? Math.max(1, Math.ceil(leaveM / graph.water.cellM)) : 1;
                        var dry = connectorDryPrefix(graph, graph.nodeLon[i], graph.nodeLat[i], to.lon, to.lat, leaveM, pieces, Math.max(0, leastLand - entryLand), prefixSamples);
                        leaveLengths[i] = leaveM; leaveDry[i] = dry;
                        leaveLand = leaveM * dry / pieces;
                    }
                    if (!cheaper(entryLand + leaveLand, leave, leastLand, cheapest) ||
                            (entryBounds && !cheaper(entryBounds[i] + Math.floor(leaveLand), leave, leastLand, cheapest))) { continue; }
                    floors.push(i, leave, leaveLand);
                }
                // An exact suffix plus an exact entry is a whole way. In a
                // kayak it tightens the lexicographic bound immediately: once
                // zero land is found, dearer zero-land floors cannot win.
                // A positive-land incumbent never caps a zero-land price.
                function enter(node, cost, land) {
                    if (fromEnds.length) {
                        for (var k = 0; k < fromEnds.length; k += 1) {
                            var end = fromEnds[k];
                            if (end.node !== node) { continue; }
                            if (cheaper(land + end.land, cost + end.cost, leastLand, cheapest)) {
                                leastLand = land + end.land; cheapest = cost + end.cost; head = node; headCut = end.cut;
                            }
                        }
                        return;
                    }
                    var entryM = far(from.lon, from.lat, graph.nodeLon[node], graph.nodeLat[node]);
                    var entryFloor = entryBox ? connectorBoxLand(graph, from, graph.nodeLon[node], graph.nodeLat[node], entryM, entryBox) : 0;
                    if (!cheaper(land + entryFloor, cost + entryM * off, leastLand, cheapest)) { return; }
                    var entry = connectorPrice(graph, from.lon, from.lat, graph.nodeLon[node], graph.nodeLat[node],
                        leastLand, land, {length: entryM, dry: 0});
                    if (cheaper(land + entry.land, cost + entry.cost, leastLand, cheapest)) {
                        leastLand = land + entry.land; cheapest = cost + entry.cost; head = node;
                    }
                }
                // Bounded and thrown for, as every loop over this graph is: a
                // settled node is never settled twice and every stale entry was
                // pushed by a relaxation, so the pops cannot exceed one per node
                // plus one per arc. A defect that runs for ever in a page is
                // indistinguishable from a page that has hung.
                // One pop per floor, one per seed priced, one per arc relaxed.
                var pops = 0, mostPops = 2 * nodes + 2 * graph.header.edges + 1;
                while (floors.node.length || heap.node.length) {
                    pops += 1;
                    if (pops > mostPops) { throw new Error('the search took more than ' + mostPops + ' steps'); }
                    // **The cheaper of the two tops goes first.** A floor is
                    // never above the price it stands for, so by the time an
                    // exact price is taken every seed that could undercut it
                    // has been priced and is in the queue beside it -- which
                    // is what keeps the exact prices coming out in order.
                    var floorTop = floors.node.length ? floors.cost[0] : Infinity;
                    var exactTop = heap.node.length ? heap.cost[0] : Infinity;
                    // Both queues answer in lexicographic order. Every entry
                    // costs at least entryLand; adding that common floor to
                    // the cheaper top still bounds every whole way left.
                    var floorLand = floors.node.length ? floors.land[0] : Infinity;
                    var exactLand = heap.node.length ? heap.land[0] : Infinity;
                    var floorFirst = !cheaper(exactLand, exactTop, floorLand, floorTop);
                    if (!cheaper(entryLand + (floorFirst ? floorLand : exactLand), floorFirst ? floorTop : exactTop, leastLand, cheapest)) { break; }
                    if (floorFirst) {
                        var seed = floors.pop();
                        if (entryBounds && !cheaper(entryBounds[seed.node] + Math.floor(seed.land), seed.cost, leastLand, cheapest)) { continue; }
                        // A node already reached over the network for no more
                        // than its floor cannot be undercut by its connector,
                        // which costs at least the floor -- so the grid is not
                        // asked. Measured on a 13 km leg: 480 ms with every
                        // floor priced, 200 ms with these skipped.
                        if (!cheaper(seed.land, seed.cost, bestLand[seed.node], best[seed.node])) { continue; }
                        // The connector must beat both this node's exact
                        // suffix and the whole-way bound, including the entry
                        // nobody can avoid. Keep the sum for the latter rather
                        // than subtracting rounded land metres from its limit.
                        var required = entryBounds ? Math.max(entryLand, entryBounds[seed.node] - 1) : entryLand;
                        var nodeBound = bestLand[seed.node] + required < leastLand;
                        var truly = connectorPrice(graph, graph.nodeLon[seed.node], graph.nodeLat[seed.node], to.lon, to.lat,
                            kayak() ? (nodeBound ? bestLand[seed.node] : leastLand) : undefined, nodeBound ? 0 : required,
                            kayak() ? {length: leaveLengths[seed.node], dry: leaveDry[seed.node]} : undefined);
                        // Cheaper than any way in over the network found so
                        // far, so the connector is this node's way out. A way
                        // in found later and cheaper still overwrites it, as
                        // any relaxation does.
                        if (cheaper(truly.land, truly.cost, bestLand[seed.node], best[seed.node])) {
                            best[seed.node] = truly.cost; bestLand[seed.node] = truly.land; viaEdge[seed.node] = -1; viaNode[seed.node] = -1;
                            heap.push(seed.node, truly.cost, truly.land);
                        }
                        continue;
                    }
                    var taken = heap.pop();
                    if (cheaper(bestLand[taken.node], best[taken.node], taken.land, taken.cost)) { continue; }
                    if (entryBounds && !cheaper(entryBounds[taken.node] + Math.floor(taken.land), taken.cost, leastLand, cheapest)) { continue; }
                    if (kayak()) { enter(taken.node, taken.cost, taken.land); }
                    for (var a = work.at[taken.node]; a < work.at[taken.node + 1]; a += 1) {
                        var edge = work.arc[a];
                        if (!allowed(graph, edge, graph.toNode[edge] === taken.node)) { continue; }
                        var other = graph.fromNode[edge] === taken.node ? graph.toNode[edge] : graph.fromNode[edge];
                        var reached = taken.cost + work.cost[edge], reachedLand = taken.land + work.land[edge];
                        if (cheaper(reachedLand, reached, bestLand[other], best[other])) {
                            best[other] = reached; bestLand[other] = reachedLand; viaEdge[other] = edge; viaNode[other] = taken.node;
                            heap.push(other, reached, reachedLand);
                        }
                    }
                }
                // Walking retains its separate entry search. The kayak has
                // already tested entries as exact suffixes settled. A near end
                // on the network enters by its own edge in either mode.
                for (i = 0; i < fromEnds.length; i += 1) {
                    var wholeIn = fromEnds[i].cost + best[fromEnds[i].node], landIn = fromEnds[i].land + bestLand[fromEnds[i].node];
                    if (cheaper(landIn, wholeIn, leastLand, cheapest)) {
                        cheapest = wholeIn; leastLand = landIn; head = fromEnds[i].node; headCut = fromEnds[i].cut;
                    }
                }
                var entries = new Heap();
                for (i = 0; i < nodes && !fromEnds.length && !kayak(); i += 1) {
                    if (!isFinite(best[i])) { continue; }
                    var floor = far(graph.nodeLon[i], graph.nodeLat[i], from.lon, from.lat) * off + best[i];
                    if (cheaper(bestLand[i], floor, plainLand, plain)) { entries.push(i, floor, bestLand[i]); }
                }
                while (entries.node.length) {
                    var next = entries.pop();
                    if (!cheaper(next.land, next.cost, leastLand, cheapest)) { break; }
                    var entry = connectorPrice(graph, from.lon, from.lat, graph.nodeLon[next.node], graph.nodeLat[next.node]);
                    var whole = entry.cost + best[next.node], wholeLand = entry.land + bestLand[next.node];
                    if (cheaper(wholeLand, whole, leastLand, cheapest)) { cheapest = whole; leastLand = wholeLand; head = next.node; }
                }
                if (head < 0) { return null; }
                var joined = leavingAt(graph, head);
                joined.headCut = headCut;
                joined.tailCut = tailCuts[joined.tail] || null;
                return joined;
            }

            function openWaterFactor(graph) {
                var source = graph.header.sources.find(function (each) { return each.name === 'Open water' && each.kind === PADDLE; });
                if (!source) { throw new Error('the kayak mode needs the Open water source'); }
                return source.factor;
            }

            // The price half of a connector floor uses the cheapest possible
            // metre. The land half may count only samples already read dry.
            function cheapestMetre(graph) {
                return kayak() ? Math.min(openWaterFactor(graph), offPath() * PLAN.portageFactor) : offPath();
            }

            // Whole dry cells around an off-network tap give a rectangle
            // every entry must leave, unless its node lies inside it. The
            // bounded expansion only trades a stronger floor for more work.
            function dryConnectorBox(graph, point) {
                var spec = graph.water && graph.water.spec;
                if (!spec || graph.waterAt(point.lon, point.lat)) { return null; }
                var col = Math.floor((point.lon - spec.west) / spec.dLon), row = Math.floor((point.lat - spec.south) / spec.dLat), radius = 0;
                for (var r = 1; r <= 16; r += 1) {
                    var wet = false;
                    for (var d = -r; d <= r && !wet; d += 1) {
                        wet = graph.waterAt(spec.west + (col + d + 0.5) * spec.dLon, spec.south + (row - r + 0.5) * spec.dLat)
                            || graph.waterAt(spec.west + (col + d + 0.5) * spec.dLon, spec.south + (row + r + 0.5) * spec.dLat)
                            || graph.waterAt(spec.west + (col - r + 0.5) * spec.dLon, spec.south + (row + d + 0.5) * spec.dLat)
                            || graph.waterAt(spec.west + (col + r + 0.5) * spec.dLon, spec.south + (row + d + 0.5) * spec.dLat);
                    }
                    if (wet) { break; }
                    radius = r;
                }
                return {west: spec.west + (col - radius) * spec.dLon, east: spec.west + (col + radius + 1) * spec.dLon,
                        south: spec.south + (row - radius) * spec.dLat, north: spec.south + (row + radius + 1) * spec.dLat};
            }

            function connectorBoxLand(graph, point, lon, lat, length, box) {
                var dx = lon - point.lon, dy = lat - point.lat, t = 1;
                if (dx > 0) { t = Math.min(t, (box.east - point.lon) / dx); }
                else if (dx < 0) { t = Math.min(t, (box.west - point.lon) / dx); }
                if (dy > 0) { t = Math.min(t, (box.north - point.lat) / dy); }
                else if (dy < 0) { t = Math.min(t, (box.south - point.lat) / dy); }
                var pieces = Math.max(1, Math.ceil(length / graph.water.cellM));
                // Leave a whole sample behind the boundary. Every counted
                // midpoint is strictly inside known dry cells, including when
                // the node is inside the box; rounding at a cell edge cannot
                // turn a possibly wet midpoint into a compulsory land metre.
                return length * Math.max(0, Math.floor(t * pieces) - 1) / pieces;
            }

            // A square stopping before the nearest opposite-kind cell is
            // uniform. Two chessboard-distance sweeps find those squares once
            // per grid; dry space outside the grid also bounds wet squares.
            // The low bit stores wet/dry and the other bits store a saturated
            // distance. Saturating only shrinks a square, never enlarges it.
            function connectorRadii(grid) {
                if (grid.connectorRadii) { return grid.connectorRadii; }
                var spec = grid.spec, cols = spec.cols, rows = spec.rows, field = new Uint16Array(cols * rows);
                var x, y, at, wet, distance, value;
                function offer(index) {
                    value = index < 0 ? 65534 : field[index];
                    distance = Math.min(distance, (value & 1) !== wet ? 1 : (value >> 1) + 1);
                }
                for (y = 0; y < rows; y += 1) {
                    for (x = 0; x < cols; x += 1) {
                        at = y * cols + x;
                        wet = (grid.bits[y * grid.stride + (x >> 3)] & (0x80 >> (x & 7))) ? 1 : 0;
                        distance = grid.damCells && grid.damCells.has(at) ? 0 : 32767;
                        offer(x ? at - 1 : -1);
                        offer(y ? at - cols : -1);
                        offer(y && x ? at - cols - 1 : -1);
                        offer(y && x + 1 < cols ? at - cols + 1 : -1);
                        field[at] = (distance << 1) | wet;
                    }
                }
                for (y = rows - 1; y >= 0; y -= 1) {
                    for (x = cols - 1; x >= 0; x -= 1) {
                        at = y * cols + x; wet = field[at] & 1; distance = field[at] >> 1;
                        offer(x + 1 < cols ? at + 1 : -1);
                        offer(y + 1 < rows ? at + cols : -1);
                        offer(y + 1 < rows && x ? at + cols - 1 : -1);
                        offer(y + 1 < rows && x + 1 < cols ? at + cols + 1 : -1);
                        field[at] = (distance << 1) | wet;
                    }
                }
                grid.connectorRadii = field;
                return field;
            }

            // Count the original midpoints in uniform squares together. The
            // last midpoint is checked using the original arithmetic: monotone
            // coordinates then keep every intervening sample in that square.
            // Every iteration consumes at least one sample and stops at end.
            function connectorScan(graph, ax, ay, bx, by, pieces, start, end, direction, length, landLimit, precedingLand, dryKnown) {
                var grid = graph.water, spec = grid.spec, field = connectorRadii(grid);
                var cols = spec.cols, rows = spec.rows, west = spec.west, south = spec.south, dLon = spec.dLon, dLat = spec.dLat;
                var deltaX = bx - ax, deltaY = by - ay, stepX = direction * deltaX / pieces, stepY = direction * deltaY / pieces;
                var inverseX = stepX ? 1 / stepX : 0, inverseY = stepY ? 1 / stepY : 0;
                var wet = 0, read = 0;
                for (var sample = start; direction > 0 ? sample < end : sample > end;) {
                    var t = (sample + 0.5) / pieces;
                    var lon = ax + t * deltaX, lat = ay + t * deltaY;
                    var col = Math.floor((lon - west) / dLon), row = Math.floor((lat - south) / dLat);
                    var value = col < 0 || row < 0 || col >= cols || row >= rows ? 0 : field[row * cols + col];
                    var isWet = (value & 1) && !(graph.damAt && graph.damAt(lon, lat));
                    var radius = (value >> 1) - 1, count = 1;
                    if (radius > 0) {
                        var left = col - radius, right = col + radius + 1, bottom = row - radius, top = row + radius + 1;
                        var across = stepX ? (west + (stepX > 0 ? right : left) * dLon - lon) * inverseX : Infinity;
                        var up = stepY ? (south + (stepY > 0 ? top : bottom) * dLat - lat) * inverseY : Infinity;
                        count = Math.max(1, Math.min(Math.abs(end - sample), Math.ceil(Math.min(across, up))));
                        var last = (sample + direction * (count - 1) + 0.5) / pieces;
                        var endCol = Math.floor((ax + last * deltaX - west) / dLon), endRow = Math.floor((ay + last * deltaY - south) / dLat);
                        if (endCol < left || endCol >= right || endRow < bottom || endRow >= top) { count = 1; }
                    }
                    read += count;
                    if (isWet) { wet += count; }
                    else if (landLimit !== undefined && (precedingLand || 0) + length * (read + dryKnown - wet) / pieces > landLimit) {
                        return -1;
                    }
                    sample += direction * count;
                }
                return wet;
            }

            // The connector's exact sampling positions also give a cheap land
            // floor. Count only an initial dry prefix: water ends cost one grid
            // lookup, and inland nodes need not be queued as possible water.
            // The measured prefix cap bounds preliminary work. Truncating it
            // only weakens the floor, never changes the answer. The exact
            // price resumes after these samples instead of reading them twice.
            function connectorWaterAt(graph, lon, lat) {
                return graph.waterAt(lon, lat) && !(kayak() && graph.damAt && graph.damAt(lon, lat));
            }

            function connectorDryPrefix(graph, aLon, aLat, bLon, bLat, length, pieces, landLimit, limit) {
                if (!graph.water) { return 1; }
                var dry = 0;
                for (var i = 0; i < Math.min(limit || 16, pieces); i += 1) {
                    var t = (i + 0.5) / pieces;
                    if (connectorWaterAt(graph, aLon + t * (bLon - aLon), aLat + t * (bLat - aLat))) { break; }
                    dry += 1;
                    if (length * dry / pieces > landLimit) { break; }
                }
                return dry;
            }

            // Reordering or batching grid reads preserves the integer wet
            // count. A wholly dry batch can pass the land ceiling by several
            // samples; the first excess sample would reject the same way.
            function connectorRunPrice(graph, aLon, aLat, bLon, bLat, length, landLimit, precedingLand, known) {
                var pieces = Math.max(1, Math.ceil(length / graph.water.cellM)), dry = known && known.dry || 0;
                var backwards = landLimit !== undefined && !dry && connectorWaterAt(graph, aLon + 0.5 / pieces * (bLon - aLon), aLat + 0.5 / pieces * (bLat - aLat));
                var wet = connectorScan(graph, aLon, aLat, bLon, bLat, pieces, backwards ? pieces - 1 : dry, backwards ? dry - 1 : pieces,
                    backwards ? -1 : 1, length, landLimit, precedingLand, dry);
                if (wet < 0) { return {cost: Infinity, land: Infinity}; }
                // Rejected connectors need no secondary price at all.
                var ground = offPath() * PLAN.portageFactor, waterPrice = openWaterFactor(graph);
                var water = length * wet / pieces;
                return {cost: (length - water) * ground + water * waterPrice, land: length * (pieces - wet) / pieces};
            }

            // The grid prices each piece at its midpoint. A map without a grid
            // can only price a connector as ground.
            function connectorPrice(graph, aLon, aLat, bLon, bLat, landLimit, precedingLand, known) {
                var length = known ? known.length : panel().metresBetween(aLon, aLat, bLon, bLat);
                var grid = graph.water;
                if (kayak() && grid && grid.bits && grid.spec) {
                    return connectorRunPrice(graph, aLon, aLat, bLon, bLat, length, landLimit, precedingLand, known);
                }
                var ground = offPath() * (kayak() ? PLAN.portageFactor : 1);
                var waterPrice = kayak() ? openWaterFactor(graph) : PLAN.waterFactor;
                if (!grid || (!kayak() && !(waterPrice > ground))) { return {cost: length * ground, land: kayak() ? length : 0}; }
                var pieces = Math.max(1, Math.ceil(length / grid.cellM)), wet = 0, backwards = false;
                for (var i = known ? known.dry : 0; i < pieces; i += 1) {
                    // A dry first sample makes this end useful for reaching
                    // the land ceiling quickly; otherwise try the other end.
                    // The same midpoints are counted in either order.
                    var sample = backwards && i ? pieces - i : i;
                    var t = (sample + 0.5) / pieces;
                    if (connectorWaterAt(graph, aLon + t * (bLon - aLon), aLat + t * (bLat - aLat))) { wet += 1; }
                    else if (landLimit !== undefined && (precedingLand || 0) + length * (i + 1 - wet) / pieces > landLimit) {
                        return {cost: Infinity, land: Infinity};
                    }
                    if (landLimit !== undefined && i === 0 && wet) { backwards = true; }
                }
                var water = length * wet / pieces;
                // Count dry pieces directly: subtracting two rounded lengths
                // could give an all-water connector a negative land cost.
                return {cost: (length - water) * ground + water * waterPrice, land: kayak() ? length * (pieces - wet) / pieces : 0};
            }

            function priced(graph, aLon, aLat, bLon, bLat) {
                return connectorPrice(graph, aLon, aLat, bLon, bLat).cost;
            }

            // **The way out of an entry node, read off the search that settled
            // it.** `viaNode` there points at the *next* node on the way to the
            // leg's far end rather than at the one before, because the search
            // ran from that end -- so this walks forwards along the journey and
            // the edges come out in the order they are walked, with no reverse
            // at the end. It stops at the node nothing relaxed, which is where
            // the walker leaves the network: the search reached it by its own
            // connector and not over an edge, and that *is* the exit.
            //
            // Reading the route out of the same search is also what keeps the
            // two halves of the answer in step. The buffers are one shared set,
            // so a second search would overwrite the costs this one was chosen
            // from -- and every other caller here is careful to finish with them
            // before the next leg starts.
            function leavingAt(graph, head) {
                var work = router(graph);
                var edges = [], reversed = [], walk = head, steps = 0;
                while (work.viaEdge[walk] >= 0) {
                    steps += 1;
                    if (steps > graph.header.edges) { throw new Error('the way out is longer than the graph'); }
                    var used = work.viaEdge[walk];
                    edges.push(used);
                    // The edge's geometry runs from its own from-node to its own
                    // to-node and the walk can take it either way round. Read off
                    // the node being left rather than off the edge's ends, which
                    // say nothing about direction on the fourteen edges here
                    // that begin and end at the same node.
                    reversed.push(graph.fromNode[used] !== walk);
                    walk = work.viaNode[walk];
                }
                return {head: head, tail: walk,
                        over: edges.length ? {edges: edges, reversed: reversed, cost: work.best[head], land: work.bestLand[head]} : null};
            }

            // ---- what a route's metres are made of ----------------------------
            // Summed per edge while the edges are still in hand. A part keeps
            // its geometry and its heights and nothing downstream can get back
            // to which edge a metre came from, so anything to be reported by
            // length has to be counted here.
            // The three buckets an edge's own sources answer with, and then the
            // two that are not answers at all: ground on a connector nobody drew
            // and so never asked about, and ground no source records a path
            // along. Kept apart, because a bucket that quietly absorbed one of
            // the others would be a claim nothing supports.
            var MARKING = ['marked', 'unmarked', 'unknown'];
            // And the two that are not answers at all, now three: ground on a
            // connector nobody drew, ground kept exactly as some file recorded
            // it, and ground no source records a path along. `recorded` is
            // phase 8's, and it is its own bucket for the reason `undrawn` is —
            // no register was asked about it, so folding it into `unmarked`
            // would turn a question nobody put into an answer.
            var TALLIED = MARKING.concat(['undrawn', 'recorded', 'unrecorded']);

            // Two things counted by name rather than into a fixed bucket: which
            // dataset drew each metre, and which protected areas the metres lie
            // in. Both are keyed without a prototype, so a register that names
            // an area "constructor" answers about that area rather than about
            // Object's own member.
            function blankTally() {
                var out = {sources: Object.create(null), protected: Object.create(null)};
                TALLIED.forEach(function (field) { out[field] = 0; });
                return out;
            }

            function addTally(into, from) {
                if (!from) { return; }
                ['sources', 'protected'].forEach(function (kind) {
                    Object.keys(from[kind]).forEach(function (name) {
                        into[kind][name] = (into[kind][name] || 0) + from[kind][name];
                    });
                });
                TALLIED.forEach(function (field) { into[field] += from[field]; });
            }

            // What protects the ground under one edge, added to a tally. **The
            // payload carries a share and this multiplies it by the length this
            // page measured**, so a route can never state more ground inside an
            // area than it walked altogether: Python measured those metres in
            // the projection the graph is built in, and 0.03 % of a long route
            // is enough for a subtotal to overtake its own total.
            function addProtected(out, graph, edge, metres) {
                var areas = graph.header.protected;
                for (var p = graph.protectedAt[edge]; p < graph.protectedAt[edge + 1]; p += 1) {
                    var area = areas[graph.protectedArea[p]];
                    if (!area) { throw new Error('edge ' + edge + ' lies in an area the page has no entry for'); }
                    out.protected[area.id] = (out.protected[area.id] || 0) + graph.protectedShare[p] * metres;
                }
            }

            // Which dataset drew each edge, whether anything says it is
            // waymarked, and whether any source records a path along it. All
            // three are on the payload per edge since it was first put in the
            // page, put there for exactly this.
            function tallyOf(graph, list) {
                var work = router(graph), out = blankTally();
                for (var i = 0; i < list.length; i += 1) { tallyEdge(out, graph, list[i], work.length[list[i]]); }
                return out;
            }

            // One edge's metres into a tally -- the whole edge for a routed
            // one, the piece walked for a cut (`cutPart`).
            function tallyEdge(out, graph, edge, metres) {
                var source = graph.header.sources[graph.sources[edge]];
                // Before the two lines below take a connector and a crossing
                // out, because the three questions have different answers
                // for them. A connector was never drawn, so no register says
                // whether it is waymarked — but a walker covers its ground,
                // and that ground lies inside a boundary or outside it. A
                // crossing is the other way round: there is no walking
                // distance under a ferry, so it is asked neither.
                if (source.kind !== CROSSING) { addProtected(out, graph, edge, metres); }
                // An inferred connector is not a dataset — nobody drew it,
                // which is what a connector is — so it names no source and
                // answers nothing about marking. Its ground is walked and
                // counted, apart, under its own name.
                if (source.kind === CONNECTOR || source.kind === PORTAGE) { out.undrawn += metres; return; }
                out.sources[source.name] = (out.sources[source.name] || 0) + metres;
                // No register marks water. Both kinds keep their source
                // credit without a marking bucket; paddling, unlike a ferry,
                // also counts the protected area already tallied above.
                if (source.kind === CROSSING || source.kind === PADDLE) { return; }
                // header.waymarked[0] is null and means the edge was never
                // asked. That is not 'unknown', which means it was asked and
                // no source answered, and the two must not be added together.
                // Every edge left here is walked ground the build asked
                // about, so it has an answer. One that did not would be
                // reported as ground on a connector *and* credited to a
                // named dataset — two contradictory claims about one edge —
                // so it is a defect rather than a fourth bucket.
                var state = graph.header.waymarked[graph.waymarked[edge]];
                if (state === null || state === undefined) {
                    throw new Error('edge ' + edge + ' is walked ground on ' + source.name + ' that was never asked about');
                }
                if (MARKING.indexOf(state) < 0) {
                    throw new Error('the payload names a marking state this page has no bucket for: ' + state);
                }
                out[state] += metres;
                // Recorded, never fact: the sources over-record, so their
                // silence is evidence and their lines are not.
                if (graph.noPathRecorded[edge]) { out.unrecorded += metres; }
            }

            // A leg drawn straight is unmarked by construction rather than
            // unknown — nobody marks a line you drew across open ground — and it
            // asserts nothing about whether a path is recorded there: that rule
            // is a spatial test against every source's lines, which the page
            // cannot run. Its length is reported as drawn straight instead.
            //
            // **What protects it, it can answer**, and this is the one figure
            // on a straight leg that is measured rather than asserted. The
            // boundaries are in the page and the leg has a height sample every
            // few metres, so each sample says what it is standing in and a
            // sample's own stretch runs half way to each of its neighbours —
            // the same halfway rule the shoreline split above is decided by, and
            // there is no second rule to disagree with it.
            function straightTally(graph, laid, standing, first, last, began, ended) {
                var out = blankTally();
                out.unmarked = ended - began;
                spreadProtected(out, graph, standing, laid.along, first, last, began, ended);
                return out;
            }


            // ---- the index over the edge geometry ---------------------------------
            // **The first work of this phase, and it is not the matcher.** The
            // page could already find the nearest node — a linear scan over
            // 116,967 of them, 0.135 ms — and over the *edge* geometry it had
            // nothing whatever. One pass over the 948,465 vertices costs 2 ms,
            // so a recording matched a point at a time is 2.9 s of frozen main
            // thread at the corpus median and 10 s at its largest, before a
            // single overlap test. Written the other way round the matcher
            // works, on a map that has stopped answering, and the cause is
            // looked for in the matcher.
            //
            // A uniform grid in scaled degrees, laid out the way the adjacency
            // is: count per cell, prefix-sum, fill. One entry per *segment* per
            // cell its bounding box touches, rather than one per edge: 21 of
            // this network's chains are ferries and the longest runs kilometres
            // end to end, and an edge indexed by its own box would be in every
            // cell between them.
            //
            // Measured in the built page over the network's 714,107 segments:
            // **29 ms to build**, 799,863 entries, 8.4 MB, and **0.7
            // microseconds a lookup** looking at 159 segments. Against the 2 ms
            // pass that is some 2,800 times cheaper, and it is what makes a
            // 5,147-point recording something matched between two frames.
            //
            // Built once, on the first thing that asks — a reader who never
            // loads a file never pays for it.
            var gridded = null;

            function edgeIndex(graph) {
                if (gridded) { return gridded; }
                var began = performance.now();
                var co = graph.coordinates, vertexAt = graph.vertexAt, edges = graph.header.edges, i, v, r, c;
                var minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
                for (i = 0; i < co.length; i += 2) {
                    if (co[i] < minLon) { minLon = co[i]; }
                    if (co[i] > maxLon) { maxLon = co[i]; }
                    if (co[i + 1] < minLat) { minLat = co[i + 1]; }
                    if (co[i + 1] > maxLat) { maxLat = co[i + 1]; }
                }
                // One cosine for the whole grid, taken at its middle. The zone
                // is 80 km of latitude and the cosine moves 1.4 % across it,
                // which is a metre in seventy on a cell edge and nothing at all
                // against a tolerance of twenty-five metres.
                var lonScale = Math.cos((minLat + maxLat) / 2 * Math.PI / 180);
                var dLat = PLAN.indexCellM / 111320, dLon = dLat / lonScale;
                var cols = Math.floor((maxLon - minLon) / dLon) + 1;
                var rows = Math.floor((maxLat - minLat) / dLat) + 1;
                var at = new Int32Array(cols * rows + 1), entries = 0;

                // Both passes walk the same segments in the same order and have
                // to agree exactly on how many cells each one touches, or the
                // fill writes past a cell's own run and the index is quietly
                // wrong wherever two cells meet. So the box is worked out in
                // one place and each pass reads it out of the same four slots
                // rather than deriving it again.
                var box = new Int32Array(4);

                function boxOf(vertex) {
                    var ax = co[2 * vertex], ay = co[2 * vertex + 1];
                    var bx = co[2 * vertex + 2], by = co[2 * vertex + 3];
                    box[0] = Math.floor(((ax < bx ? ax : bx) - minLon) / dLon);
                    box[1] = Math.floor(((ax > bx ? ax : bx) - minLon) / dLon);
                    box[2] = Math.floor(((ay < by ? ay : by) - minLat) / dLat);
                    box[3] = Math.floor(((ay > by ? ay : by) - minLat) / dLat);
                }

                for (i = 0; i < edges; i += 1) {
                    for (v = vertexAt[i]; v + 1 < vertexAt[i + 1]; v += 1) {
                        boxOf(v);
                        for (r = box[2]; r <= box[3]; r += 1) {
                            for (c = box[0]; c <= box[1]; c += 1) { at[r * cols + c + 1] += 1; entries += 1; }
                        }
                    }
                }
                for (i = 1; i < at.length; i += 1) { at[i] += at[i - 1]; }
                var cursor = new Int32Array(cols * rows);
                var item = new Int32Array(entries), vert = new Int32Array(entries);
                for (i = 0; i < edges; i += 1) {
                    for (v = vertexAt[i]; v + 1 < vertexAt[i + 1]; v += 1) {
                        boxOf(v);
                        for (r = box[2]; r <= box[3]; r += 1) {
                            for (c = box[0]; c <= box[1]; c += 1) {
                                var cell = r * cols + c, put = at[cell] + cursor[cell];
                                cursor[cell] += 1;
                                item[put] = i; vert[put] = v;
                            }
                        }
                    }
                }
                // Filling leaves cursor[cell] at that cell's own count, so
                // at[cell] + cursor[cell] is where the next cell begins — the
                // invariant the node adjacency above is filled under too.
                gridded = {at: at, item: item, vert: vert, cols: cols, rows: rows,
                           dLon: dLon, dLat: dLat, minLon: minLon, minLat: minLat, lonScale: lonScale,
                           entries: entries, cells: cols * rows, buildMs: performance.now() - began,
                           bytes: (at.length + item.length + vert.length) * 4};
                return gridded;
            }

            // The nearest edge to a position, or nothing within the tolerance.
            //
            // **The heading is tested here, and it is the cheap half of what
            // keeps a recording off the wrong line.** At a junction the first
            // metres of a side path lie well inside any tolerance of the path
            // being walked, and a test asking only how far away something is
            // takes it: that is what put 23 % of `attach_nearest`'s matches on
            // a road they followed for under half its length. Undirected,
            // because a recording may walk an edge either way round — what is
            // compared is the line's direction and not its arrow. Where the
            // recording has no heading at all, which consumer GPS produces
            // whenever somebody stands still, every candidate passes it and the
            // distance decides.
            function nearestEdge(graph, index, lon, lat, hx, hy) {
                var co = graph.coordinates, lonScale = index.lonScale;
                var reach = PLAN.matchToleranceM / 111320;
                var c0 = Math.floor((lon - reach / lonScale - index.minLon) / index.dLon);
                var c1 = Math.floor((lon + reach / lonScale - index.minLon) / index.dLon);
                var r0 = Math.floor((lat - reach - index.minLat) / index.dLat);
                var r1 = Math.floor((lat + reach - index.minLat) / index.dLat);
                if (c0 < 0) { c0 = 0; }
                if (r0 < 0) { r0 = 0; }
                if (c1 > index.cols - 1) { c1 = index.cols - 1; }
                if (r1 > index.rows - 1) { r1 = index.rows - 1; }
                var turning = Math.cos(PLAN.matchMaxTurnDeg * Math.PI / 180);
                var heading = Math.sqrt(hx * hx + hy * hy);
                var closest = reach * reach, best = -1;
                for (var r = r0; r <= r1; r += 1) {
                    for (var c = c0; c <= c1; c += 1) {
                        var cell = r * index.cols + c;
                        for (var s = index.at[cell]; s < index.at[cell + 1]; s += 1) {
                            var v = index.vert[s];
                            var ax = co[2 * v], ay = co[2 * v + 1];
                            var ex = (co[2 * v + 2] - ax) * lonScale, ey = co[2 * v + 3] - ay;
                            var span = ex * ex + ey * ey;
                            if (heading > 0 && span > 0 &&
                                Math.abs(hx * ex + hy * ey) < turning * heading * Math.sqrt(span)) { continue; }
                            var px = (lon - ax) * lonScale, py = lat - ay;
                            var t = span > 0 ? (px * ex + py * ey) / span : 0;
                            t = t < 0 ? 0 : (t > 1 ? 1 : t);
                            var qx = px - t * ex, qy = py - t * ey;
                            var away = qx * qx + qy * qy;
                            if (away < closest) { closest = away; best = index.item[s]; }
                        }
                    }
                }
                return best < 0 ? null : {edge: best, m: Math.sqrt(closest) * 111320};
            }

            // **The nearest place on the network itself, and not its nearest
            // junction.** `nearestNode` answers over the nodes, and a node is
            // where edges meet or a chain ends -- so a tap in the middle of a
            // long stretch of trail found nothing within a finger's width and
            // was taken as open ground, and every leg from it was drawn
            // straight. Reported from the phone as *once one straight line is
            // drawn, every tap after it is one, until I tap a path further
            // on* -- the path further on being the next junction. Measured on
            // the two graphs: an edge is 15 m at the median and 13 km at the
            // longest on Abisko, and 37 % of Abisko's network by length (32 %
            // of Lomsdal's) lies more than 21 m -- a finger at z15 -- from any
            // node; 13 % lies more than 150 m from one.
            //
            // Over the grid the match mode builds, so a lookup reads a few
            // cells rather than 948,465 vertices; it is built once, when plan
            // mode is switched on or at the first tap that asks. A crossing
            // and a connector are not ground to stand on and are skipped:
            // nobody drew the connector, and the ferry is water.
            //
            // What comes back is the foot on the line and how far along its
            // edge that is, from the edge's own from-node -- which is what the
            // router needs to reach the point along the edge (`endsOf`).
            function nearestOnNetwork(graph, lat, lon, withinM) {
                if (!(withinM > 0) || !graph.header.edges) { return null; }
                var index = edgeIndex(graph);
                var co = graph.coordinates, lonScale = index.lonScale;
                var reach = withinM / 111320;
                var c0 = Math.floor((lon - reach / lonScale - index.minLon) / index.dLon);
                var c1 = Math.floor((lon + reach / lonScale - index.minLon) / index.dLon);
                var r0 = Math.floor((lat - reach - index.minLat) / index.dLat);
                var r1 = Math.floor((lat + reach - index.minLat) / index.dLat);
                if (c0 < 0) { c0 = 0; }
                if (r0 < 0) { r0 = 0; }
                if (c1 > index.cols - 1) { c1 = index.cols - 1; }
                if (r1 > index.rows - 1) { r1 = index.rows - 1; }
                var closest = reach * reach, best = -1, bestVertex = -1, bestT = 0;
                for (var r = r0; r <= r1; r += 1) {
                    for (var c = c0; c <= c1; c += 1) {
                        var cell = r * index.cols + c;
                        for (var e = index.at[cell]; e < index.at[cell + 1]; e += 1) {
                            var edge = index.item[e];
                            var kind = graph.header.sources[graph.sources[edge]].kind;
                            if (kind === CROSSING || kind === CONNECTOR || ((kind === PADDLE || kind === PORTAGE) && !kayak())) { continue; }
                            var v = index.vert[e];
                            var ax = co[2 * v], ay = co[2 * v + 1];
                            var ex = (co[2 * v + 2] - ax) * lonScale, ey = co[2 * v + 3] - ay;
                            var span = ex * ex + ey * ey;
                            var px = (lon - ax) * lonScale, py = lat - ay;
                            var t = span > 0 ? (px * ex + py * ey) / span : 0;
                            t = t < 0 ? 0 : (t > 1 ? 1 : t);
                            var qx = px - t * ex, qy = py - t * ey;
                            var away = qx * qx + qy * qy;
                            if (away < closest) { closest = away; best = edge; bestVertex = v; bestT = t; }
                        }
                    }
                }
                if (best < 0) { return null; }
                var fx = co[2 * bestVertex], fy = co[2 * bestVertex + 1];
                var foot = {lon: fx + bestT * (co[2 * bestVertex + 2] - fx), lat: fy + bestT * (co[2 * bestVertex + 3] - fy)};
                var between = panel().metresBetween, along = 0;
                for (var w = graph.vertexAt[best]; w < bestVertex; w += 1) {
                    along += between(co[2 * w], co[2 * w + 1], co[2 * w + 2], co[2 * w + 3]);
                }
                along += between(fx, fy, foot.lon, foot.lat);
                return {edge: best, along: along, lon: foot.lon, lat: foot.lat, m: Math.sqrt(closest) * 111320};
            }

            // How far a position lies from a run of coordinates, in metres. It
            // stops as soon as it is inside the tolerance: the overlap test asks
            // it once per recorded point against a laid path, and all it wants
            // to know is whether that point is near the path at all.
            function awayFromRun(lon, lat, xs, ys, lonScale, withinM) {
                var reach = withinM / 111320, inside = reach * reach, closest = Infinity;
                for (var i = 0; i + 1 < xs.length; i += 1) {
                    var ax = xs[i], ay = ys[i];
                    var ex = (xs[i + 1] - ax) * lonScale, ey = ys[i + 1] - ay;
                    var px = (lon - ax) * lonScale, py = lat - ay;
                    var span = ex * ex + ey * ey;
                    var t = span > 0 ? (px * ex + py * ey) / span : 0;
                    t = t < 0 ? 0 : (t > 1 ? 1 : t);
                    var qx = px - t * ex, qy = py - t * ey, away = qx * qx + qy * qy;
                    if (away < closest) { closest = away; }
                    if (closest <= inside) { return Math.sqrt(closest) * 111320; }
                }
                return Math.sqrt(closest) * 111320;
            }

            // ---- the recording, and the parts cut out of it ------------------------
            // The one recording the page is working from, or nothing. Loading a
            // second replaces the first, and every waypoint that came out of the
            // first names it by id — so a waypoint left over from a file that is
            // no longer loaded is recognised rather than read against the wrong
            // coordinates.
            var loaded = null;

            // A file that has been read and not yet taken, and null the rest of
            // the time — which is how everything else knows whether a question
            // is on the screen. **It is deliberately not `loaded`**: nothing
            // anchored to a recording may see a file the reader has not
            // accepted, or an edit made while the question stands would look its
            // points up in the wrong track.
            var pendingFile = null;

            // What the last file turned out to be, in full. Shown behind the
            // panel's mark rather than in it.
            var loadDetail = '';

            // Set when a file is taken and cleared by the fit itself, so the map
            // is moved once per load and not once per refresh.
            var fitWanted = false;

            // What the reader calls this tour, or empty where they have called
            // it nothing. It travels in <metadata><name> and <trk><name>, which
            // is where GPX puts a name, so it comes back out of a file this map
            // wrote without a field of its own.
            var tourName = '';
            var loadedCount = 0;

            // A waypoint anchored to a recorded point. **It keeps the
            // recording's own position and does not snap to the network**: the
            // mode that takes a track as it is has to leave it where it was
            // recorded, and a waypoint that jumped to a node 100 m away would
            // drag the first and last hundred metres of the track with it.
            function anchored(graph, at) {
                // **And it carries a node where the recording reached one**,
                // which is not the same as snapping to it. Its position stays
                // the recording's, because a mode that takes a track as it is
                // has to leave it where it was recorded; the node is what lets
                // the *other* legs beside it route. Without it a leg joining an
                // anchored waypoint to an ordinary one falls past the routing
                // test — which wants a node at both ends — and is drawn straight
                // over the terrain: extending a loaded track by clicking would
                // draw a line rather than follow a path, and a mixed route
                // reloaded would come back with every leg beside a recorded one
                // turned into a straight line.
                //
                // Within the match tolerance rather than `snapM`. A routed leg
                // is laid from the node, so whatever the two are apart is a step
                // in the track at that waypoint, and 25 m is the same seam the
                // matcher already leaves where a recorded stretch meets a
                // routed one. A hundred and fifty would be a visible jump.
                var node = graph ? graph.nearestNode(loaded.lat[at], loaded.lon[at], PLAN.matchToleranceM) : -1;
                return {lat: loaded.lat[at], lon: loaded.lon[at], node: node, track: loaded.id, at: at};
            }

            // Which protected areas a run of ground lies in, spread over it by
            // the halfway rule: a point's own stretch runs half way to each of
            // its neighbours. **One rule, in one place**, called by the leg
            // drawn straight and by the stretch kept as recorded — two spellings
            // of a halfway rule would eventually disagree about a boundary and
            // both would look right.
            function spreadProtected(out, graph, standing, along, first, last, began, ended) {
                for (var s = first; s < last; s += 1) {
                    var here = standing[s];
                    if (!here || !here.length) { continue; }
                    var low = s === first ? began : (along[s - 1] + along[s]) / 2;
                    var high = s === last - 1 ? ended : (along[s] + along[s + 1]) / 2;
                    for (var a = 0; a < here.length; a += 1) {
                        var id = graph.header.protected[here[a]].id;
                        out.protected[id] = (out.protected[id] || 0) + (high - low);
                    }
                }
            }

            // One stretch of the recording, kept as it was recorded: the fifth
            // kind, and the one this phase adds.
            //
            // **Its metres go in a bucket of their own and in none of the four.**
            // No register was asked about this ground, which rules out marked,
            // unmarked and unknown; it is not a connector, which rules out
            // undrawn. It is the same shape of answer as a connector's — never
            // asked, reported under its own name — and folding it into unmarked
            // would turn a question nobody put into an answer.
            //
            // What protects it, it can say, and by the same halfway rule as a
            // leg drawn straight: the boundaries are in the page and the
            // recording has a point every few metres.
            //
            // ``firstLon``/``firstLat`` and ``lastLon``/``lastLat`` move the two
            // ends onto whatever they join, which is a node where a matched
            // stretch begins or ends. The displacement is bounded by the match
            // tolerance and it is what keeps the route one continuous line
            // instead of a run of stretches with 20 m holes between them.
            //
            // ``kind`` is what the span is, where something knows: a restored
            // plan's own leg list says whether a stretch was recorded or drawn
            // straight, and the two are different ground. Left out it is a
            // recording, which is what every other caller has.
            function trackPart(graph, first, last, firstLon, firstLat, lastLon, lastLat, kind) {
                // **A typed array answers an index outside it with undefined
                // rather than raising**, so an anchor left over from a file that
                // is no longer loaded would put NaN coordinates into the route
                // and draw nothing, silently. The Python sibling of this rule is
                // that a numpy array is never indexed with a sentinel; here the
                // sentinel would be an index into the wrong recording.
                if (first < 0 || last < 0 || first >= loaded.n || last >= loaded.n) {
                    throw new Error('a waypoint points at ' + first + '..' + last +
                                    ' of a recording that has ' + loaded.n + ' points');
                }
                var step = last >= first ? 1 : -1, count = Math.abs(last - first) + 1;
                var lon = new Array(count), lat = new Array(count), height = new Array(count);
                var along = new Array(count), i, at;
                for (i = 0, at = first; i < count; i += 1, at += step) {
                    lon[i] = loaded.lon[at]; lat[i] = loaded.lat[at]; height[i] = loaded.ele[at];
                }
                if (firstLon !== undefined) { lon[0] = firstLon; lat[0] = firstLat; }
                if (lastLon !== undefined) { lon[count - 1] = lastLon; lat[count - 1] = lastLat; }
                var run = 0;
                along[0] = 0;
                for (i = 1; i < count; i += 1) {
                    run += panel().metresBetween(lon[i - 1], lat[i - 1], lon[i], lat[i]);
                    along[i] = run;
                }
                var tally = blankTally();
                // **A stretch the reader drew across open ground is unmarked by
                // construction and not recorded**: nobody marks a line you drew,
                // and nobody recorded it either. The decisions document settles
                // that distinction, and restoring a plan is the first thing that
                // ever had to apply it to a span of somebody's file.
                if (kind === 'land') { tally.unmarked = run; }
                else if (kind !== 'paddled') { tally.recorded = run; }
                var standing = new Array(count);
                for (i = 0; i < count; i += 1) { standing[i] = graph.areasAt(lon[i], lat[i]); }
                spreadProtected(tally, graph, standing, along, 0, count, 0, run);
                var read = false;
                for (i = 0; i < count; i += 1) { if (!isNaN(height[i])) { read = true; break; } }
                // The vertices and the samples are one series here, which they
                // are for no other kind: a recording's points are both what the
                // file writes and what the profile is drawn from, and there is
                // nothing to sample between them that was ever measured.
                return {kind: kind || PLAN.gpx.trackKind, lon: lon, lat: lat, along: along, length: run,
                        height: height, distance: along, read: read, tally: tally,
                        index: {from: first, step: step, count: count}};
            }

            // ---- matching a recording onto the network ----------------------------
            // **Anchor, then route, then test the result against the recording.**
            // Every point of the recording could be assigned an edge instead,
            // and the runs of like assignment chained into paths — that was the
            // first design and it spends its life on cases the graph answers for
            // free: an edge here averages 25 m, a recording wobbles between two
            // of them at every junction, and reconstructing which way round each
            // one is walked is arithmetic with four ways to be wrong. Routing
            // between two anchors cannot produce a path that is not a path, and
            // the 14 edges here whose two ends are the same node are the
            // router's problem rather than this function's.
            //
            // What it costs: one Dijkstra per anchor, and a search between two
            // nodes a few hundred metres apart settles a handful of nodes. The
            // three arrays it clears are the floor — 116,967 each — which is
            // why the anchors are spaced rather than taken at every point.
            //
            // **And the test is `attach_nearest`'s rule, with the recording as
            // the line and the routed path as its counterpart**: what share of
            // the recorded stretch actually lies along the path offered to
            // replace it. Proximity alone is a weak test for lines, and this is
            // the phase where that lesson is either applied or paid for.
            function anchorsOf(graph, index, first, last) {
                var out = [], since = -Infinity;
                for (var i = first; i <= last; i += 1) {
                    if (i > first && i < last && loaded.along[i] - since < PLAN.matchAnchorM) { continue; }
                    since = loaded.along[i];
                    var before = i > first ? i - 1 : i, after = i < last ? i + 1 : i;
                    var hx = (loaded.lon[after] - loaded.lon[before]) * index.lonScale;
                    var hy = loaded.lat[after] - loaded.lat[before];
                    var found = nearestEdge(graph, index, loaded.lon[i], loaded.lat[i], hx, hy);
                    if (!found) { continue; }
                    // The nearer of the matched edge's own two ends, **and
                    // only if the recording actually reached it**.
                    //
                    // That second half is not a refinement, it is what keeps
                    // the matcher from stating a walk nobody took. Noding cuts
                    // a line only where something meets it, so a recording out
                    // in the terrain that nothing crosses is *one edge*: the
                    // median edge here is 6.9 m and the 90th percentile 49 m,
                    // but **1,142 of the 234,358 are over 500 m and 79 over
                    // 2 km, the longest 18.5 km**. Anchoring to the far end of
                    // one of those and routing to it hands back the whole edge
                    // — measured on trip 1113935, an out-and-back that turns
                    // round 332 m short of the end of its own 4,729 m edge, and
                    // the route came back 332 m longer than the walk.
                    //
                    // A node the recording passed within the tolerance of is a
                    // place it demonstrably stood, so a routed stretch between
                    // two of them is ground that was walked. Where there is no
                    // such node the stretch is kept as it was recorded, which
                    // is the honest answer while a part is a whole edge: what
                    // it would take to say more is in the phase's write-up.
                    var a = graph.fromNode[found.edge], b = graph.toNode[found.edge];
                    var toA = panel().metresBetween(loaded.lon[i], loaded.lat[i], graph.nodeLon[a], graph.nodeLat[a]);
                    var toB = panel().metresBetween(loaded.lon[i], loaded.lat[i], graph.nodeLon[b], graph.nodeLat[b]);
                    if (toA > PLAN.matchToleranceM && toB > PLAN.matchToleranceM) { continue; }
                    var node = toA <= toB ? a : b;
                    // Never the node the last anchor already stands on. Two
                    // anchors at one node have nothing to route between, and the
                    // stretch between them would be dropped rather than tested —
                    // so the recording would keep ground the network carries
                    // perfectly well, for no reason a reader could see.
                    if (out.length && out[out.length - 1].node === node) { continue; }
                    out.push({at: i, node: node, away: found.m});
                }
                return out;
            }

            // What share of the recorded points between two anchors lies within
            // the tolerance of the path offered to replace them.
            function overlapWith(laid, first, last, lonScale) {
                var inside = 0, count = 0;
                for (var i = first; i <= last; i += 1) {
                    count += 1;
                    if (awayFromRun(loaded.lon[i], loaded.lat[i], laid.lon, laid.lat,
                                    lonScale, PLAN.matchToleranceM) <= PLAN.matchToleranceM) { inside += 1; }
                }
                return count ? inside / count : 0;
            }

            // The recording cut into stretches: the ones the network carries and
            // the ones it does not, in the order they are walked. Every stretch
            // between ``first`` and ``last`` is covered exactly once.
            function matchedSpans(graph, first, last) {
                var index = edgeIndex(graph);
                var anchors = anchorsOf(graph, index, first, last);
                var spans = [], at = first, k;
                for (k = 0; k + 1 < anchors.length; k += 1) {
                    var a = anchors[k], b = anchors[k + 1];
                    if (a.node === b.node || b.at <= a.at) { continue; }
                    var found = route(graph, a.node, b.node);
                    if (!found || !found.edges.length) { continue; }
                    var breaks = found.edges.map(function () { return false; });
                    var laid = panel().layEdges(graph, found.edges, found.reversed, breaks);
                    // **The overlap test's other half, and it is not optional.**
                    // Overlap asks what share of the *recording* lies along the
                    // path offered to replace it, which is `attach_nearest`'s
                    // rule and is one-directional: a path that runs along the
                    // whole recording and then goes somewhere else as well
                    // passes it. Measured before this line existed, the 42.44 km
                    // Rundtur came back as **48.2 km** — 5.7 km of ground the
                    // walker never covered, on a round trip whose own line
                    // crosses itself and where the router took the wrong branch
                    // at the crossing while still lying along the recording
                    // everywhere it was asked about.
                    //
                    // A route may not claim more ground than was walked. Both
                    // anchors lie within the tolerance of a recorded point, so
                    // the tolerance at each end is the whole of the slack there
                    // is: anything beyond it is a different way round.
                    var covered = loaded.along[b.at] - loaded.along[a.at];
                    if (laid.total > covered + 2 * PLAN.matchToleranceM) { continue; }
                    if (overlapWith(laid, a.at, b.at, index.lonScale) < PLAN.matchMinOverlap) { continue; }
                    if (at < a.at) { spans.push({routed: false, from: at, to: a.at}); }
                    // Two accepted stretches meeting at one anchor are one path
                    // and not two: the second begins at the node the first ended
                    // at, so their edge lists lay end to end with nothing
                    // between them.
                    var back = spans.length ? spans[spans.length - 1] : null;
                    if (back && back.routed && back.to === a.at) {
                        back.edges = back.edges.concat(found.edges);
                        back.reversed = back.reversed.concat(found.reversed);
                        back.to = b.at; back.length += laid.total;
                    } else {
                        spans.push({routed: true, from: a.at, to: b.at, node: a.node,
                                    edges: found.edges, reversed: found.reversed, length: laid.total});
                    }
                    at = b.at;
                }
                if (at < last) { spans.push({routed: false, from: at, to: last}); }
                if (!spans.length) { spans.push({routed: false, from: first, to: last}); }

                // **A floor under what counts as running along something.** A
                // matched stretch shorter than this is the junction case — a
                // recording crossing a path takes a few of its metres — and
                // below it *running along* a path and *touching* it cannot be
                // told apart. Reverted rather than dropped: the ground is still
                // walked, and what changes is only whose line says so.
                var kept = [];
                spans.forEach(function (span) {
                    var back = kept.length ? kept[kept.length - 1] : null;
                    var verbatim = !span.routed || span.length < PLAN.matchMinRunM;
                    if (verbatim && back && !back.routed) { back.to = span.to; return; }
                    kept.push(verbatim ? {routed: false, from: span.from, to: span.to} : span);
                });
                return kept;
            }

            // The stretches as parts of one leg: what the network carries laid
            // out of its own edges, and what it does not kept exactly as it was
            // recorded, with the two ends of every recorded stretch moved onto
            // the nodes it joins.
            function matchedParts(graph, first, last) {
                var spans = matchedSpans(graph, first, last), parts = [];
                spans.forEach(function (span, i) {
                    if (span.routed) {
                        parts.push.apply(parts, routedParts(graph, {edges: span.edges, reversed: span.reversed}));
                        return;
                    }
                    var before = i > 0 ? spans[i - 1] : null, after = i + 1 < spans.length ? spans[i + 1] : null;
                    var lead = before && before.routed ? endOf(parts) : null;
                    var trail = after && after.routed ? startOf(graph, after) : null;
                    parts.push(trackPart(graph, span.from, span.to,
                                         lead ? lead.lon : undefined, lead ? lead.lat : undefined,
                                         trail ? trail.lon : undefined, trail ? trail.lat : undefined));
                });
                return parts;
            }

            function endOf(parts) {
                for (var i = parts.length - 1; i >= 0; i -= 1) {
                    var part = parts[i];
                    if (part.lon && part.lon.length) {
                        return {lon: part.lon[part.lon.length - 1], lat: part.lat[part.lat.length - 1]};
                    }
                }
                return null;
            }

            function startOf(graph, span) {
                return {lon: graph.nodeLon[span.node], lat: graph.nodeLat[span.node]};
            }

            // ---- the parts of a leg ------------------------------------------
            // Split where the way changes: walking, paddling, or a ferry whose
            // metres have no profile and must leave a gap in the track.
            function routedParts(graph, found) {
                var parts = [], run = [], reversed = [], kind = null;

                function flush() {
                    if (!run.length) { return; }
                    var breaks = run.map(function () { return false; });
                    var laid = panel().layEdges(graph, run, reversed, breaks);
                    var tally = tallyOf(graph, run);
                    // `along` travels with the part because the file is written
                    // from the vertices and the profile from the samples, and
                    // the two are different series over the same ground.
                    parts.push(kind === CROSSING
                        ? {kind: CROSSING, lon: laid.lon, lat: laid.lat, along: laid.along, length: laid.total,
                           height: null, distance: null, read: false, tally: tally}
                        : {kind: kind, lon: laid.lon, lat: laid.lat, along: laid.along, length: laid.total,
                           height: laid.height, distance: laid.distance, read: laid.read, tally: tally});
                    run = []; reversed = [];
                }

                // The pieces of the edges the way begins and ends on, where
                // it begins or ends part way along one: path, laid the way the
                // whole edges are.
                var head = found.head ? cutPart(graph, found.head) : null;
                if (head) { parts.push(head); }
                for (var i = 0; i < found.edges.length; i += 1) {
                    var sourceKind = graph.header.sources[graph.sources[found.edges[i]]].kind;
                    var here = sourceKind === CROSSING ? CROSSING : (kayak() && sourceKind === PADDLE ? 'paddled' : 'routed');
                    if (here !== kind) { flush(); kind = here; }
                    run.push(found.edges[i]); reversed.push(found.reversed[i]);
                }
                flush();
                var tail = found.tail ? cutPart(graph, found.tail) : null;
                if (tail) { parts.push(tail); }
                return parts;
            }

            // **A piece of one edge, from one distance along it to another.**
            // What a leg walks between a point standing on the edge and the
            // node it leaves by, laid out the way `layEdges` lays a whole
            // edge: the vertices between, the samples between with the two
            // ends read off their neighbours, and the ground tallied by the
            // metres walked. Nothing where the two distances are the same
            // place, which is a point standing on the node itself.
            function cutPart(graph, cut) {
                var lo = Math.min(cut.from, cut.to), hi = Math.max(cut.from, cut.to);
                if (!(hi - lo >= 0.5)) { return null; }
                var edge = cut.edge, forward = cut.to >= cut.from;
                var co = graph.coordinates, between = panel().metresBetween;
                var v0 = graph.vertexAt[edge], v1 = graph.vertexAt[edge + 1];
                var lon = [], lat = [], along = [];
                function put(x, y, d) { lon.push(x); lat.push(y); along.push(d - lo); }
                var run = 0, began = false, ended = false;
                for (var v = v0; v + 1 < v1; v += 1) {
                    var ax = co[2 * v], ay = co[2 * v + 1], bx = co[2 * v + 2], by = co[2 * v + 3];
                    var seg = between(ax, ay, bx, by), end = run + seg, last = v + 2 >= v1;
                    if (!began && (lo <= end || last)) {
                        var t = seg > 0 ? Math.max(0, Math.min(1, (lo - run) / seg)) : 0;
                        put(ax + t * (bx - ax), ay + t * (by - ay), lo);
                        began = true;
                    }
                    if (began && (hi <= end || last)) {
                        var u = seg > 0 ? Math.max(0, Math.min(1, (hi - run) / seg)) : 1;
                        put(ax + u * (bx - ax), ay + u * (by - ay), hi);
                        ended = true;
                        break;
                    }
                    if (began) { put(bx, by, end); }
                    run = end;
                }
                if (!began || !ended || lon.length < 2) { return null; }
                var total = router(graph).length[edge];
                // The samples lie evenly along the edge, the last on its far
                // end: the sth at total * s / (n - 1). The two ends of the
                // piece take a height between their neighbours, or none where
                // either neighbour has none.
                var s0 = graph.sampleAt[edge], n = graph.sampleAt[edge + 1] - s0;
                var height = [], distance = [];
                function heightAt(d) {
                    var pos = total > 0 ? d / total * (n - 1) : 0, k = Math.floor(pos), f = pos - k;
                    if (k >= n - 1) { return graph.heights[s0 + n - 1]; }
                    var a = graph.heights[s0 + k], b = graph.heights[s0 + k + 1];
                    if (f === 0) { return a; }
                    return (isNaN(a) || isNaN(b)) ? NaN : a + f * (b - a);
                }
                if (n >= 2) {
                    height.push(heightAt(lo)); distance.push(0);
                    for (var k = 0; k < n; k += 1) {
                        var d = total * k / (n - 1);
                        if (d > lo && d < hi) { height.push(graph.heights[s0 + k]); distance.push(d - lo); }
                    }
                    height.push(heightAt(hi)); distance.push(hi - lo);
                }
                if (!forward) {
                    lon.reverse(); lat.reverse();
                    along = along.map(function (d) { return (hi - lo) - d; }).reverse();
                    height.reverse();
                    distance = distance.map(function (d) { return (hi - lo) - d; }).reverse();
                }
                var read = height.some(function (h) { return !isNaN(h); });
                var tally = blankTally();
                tallyEdge(tally, graph, edge, hi - lo);
                var paddled = kayak() && graph.header.sources[graph.sources[edge]].kind === PADDLE;
                return {kind: paddled ? 'paddled' : 'routed', lon: lon, lat: lat, along: along, length: hi - lo,
                        height: height, distance: distance, read: read, tally: tally};
            }

            // ---- heights for a leg the network cannot carry -------------------
            // Sampled by the build's own rule: floor(length / step) + 1 samples,
            // never fewer than two, spread evenly between the two ends. Two
            // halves of one profile read under two rules answer differently, and
            // nothing about the answer looks wrong.
            // **Refused rather than quietly coarsened.** Sampling is fixed at
            // the build's step, so the only way to bound the work is to bound
            // the leg: at 5 m and fifty points a request, the width of this map
            // is some 180 requests to somebody else's service, from one misclick
            // out to sea. Coarsening instead would make the two halves of a
            // profile answer differently and nothing would look wrong, so the
            // leg says what it will not do.
            //
            // Asked here rather than inside the sampling, because a leg carried
            // through a drag without heights is refused for its length too — and
            // a ceiling that only applied where the samples are laid out would
            // let a drag draw across the whole map and refuse it on release.
            function refuseLong(length) {
                if (length > PLAN.maxStraightM) {
                    throw new Error((length / 1000).toFixed(1) + ' km is further than a leg may be drawn straight (' +
                                    (PLAN.maxStraightM / 1000).toFixed(1) + ' km)');
                }
            }

            function straightSamples(from, to) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                refuseLong(length);
                var count = Math.max(2, Math.floor(length / PLAN.sampleStepM) + 1);
                var lon = [], lat = [], along = [];
                for (var i = 0; i < count; i += 1) {
                    var t = i / (count - 1);
                    lon.push(from.lon + t * (to.lon - from.lon));
                    lat.push(from.lat + t * (to.lat - from.lat));
                    along.push(t * length);
                }
                return {lon: lon, lat: lat, along: along, length: length};
            }

            // The same two rules the build reads an answer by, and they are two
            // rules rather than one. `datakilde` says whether the number is a
            // ground height at all: over water the service answers with a depth
            // from the depth contours — a metre offshore reads -276 m — and
            // outside its coverage with nothing. `terreng` says what the point
            // is *on*, and that is what tells a straight leg whether it is
            // walking or crossing. A lake answers with neither: a real height
            // from a lake model, which is not a terrain model, so it is walked
            // ground with nothing read along it.
            function reading(point) {
                var from = point.datakilde;
                var ground = typeof from === 'string' && from.toLowerCase().indexOf(PLAN.terrainModel) === 0;
                var height = point.z;
                return {
                    height: (ground && height !== null && height !== undefined) ? Number(height) : NaN,
                    sea: point.terreng === PLAN.seaTerrain
                };
            }

            // **A request that never answers is not a request that failed**, and
            // that is the whole of this. `fetch` has no deadline of its own: a
            // server that accepts a connection and then says nothing leaves a
            // promise that neither resolves nor rejects, the retry below never
            // sees a refusal to retry, and the leg it belongs to stays
            // outstanding for ever -- plan mode saying *working...* with nothing
            // left that will ever finish it. Reported as exactly that, and
            // reproduced on the build before it.
            //
            // Aborted rather than merely raced, so the connection goes with the
            // wait: a page that gave up on the answer and left the socket open
            // would be leaning on somebody else's service on the way out.
            function askOnce(points) {
                var stop = window.AbortController ? new AbortController() : null;
                var giveUp = stop
                    ? window.setTimeout(function () { stop.abort(); }, PLAN.heightsTimeoutMs)
                    : null;
                function letGo() { if (giveUp !== null) { window.clearTimeout(giveUp); giveUp = null; } }
                var asking = fetch(PLAN.heightsUrl + '?punkter=' + encodeURIComponent(JSON.stringify(points)) +
                                   '&koordsys=' + encodeURIComponent(PLAN.heightsCrs),
                                   stop ? {signal: stop.signal} : undefined)
                    .then(function (response) {
                        if (!response.ok) { throw new Error('the height model answered ' + response.status); }
                        return response.json();
                    })
                    .then(function (body) {
                        var answered = body && body.punkter;
                        // The answer is read by position, so one that does not
                        // line up with the question would put each point's
                        // neighbour's height on it and raise nothing.
                        if (!answered || answered.length !== points.length) {
                            throw new Error('asked about ' + points.length + ' points and got ' +
                                            (answered ? answered.length : 'no list'));
                        }
                        return answered.map(reading);
                    });
                // The timer is let go of only when the whole exchange is over,
                // body and all: a header that arrives and a body that never
                // finishes is the same hang one step later.
                return asking.then(function (answers) {
                    letGo();
                    return answers;
                }, function (failure) {
                    letGo();
                    if (stop && stop.signal.aborted) {
                        throw new Error('the height model did not answer within ' +
                                        Math.round(PLAN.heightsTimeoutMs / 1000) + ' s');
                    }
                    throw failure;
                });
            }

            // Retried the way the build retries: this endpoint is shared and a
            // busy server has been seen to answer moments later. After that the
            // leg says it has no heights rather than drawing flat ground.
            var ATTEMPTS = 3;

            function ask(points, attempt) {
                return askOnce(points).catch(function (failure) {
                    if (attempt >= ATTEMPTS) { throw failure; }
                    return new Promise(function (resolve) { setTimeout(resolve, 500 * attempt); })
                        .then(function () { return ask(points, attempt + 1); });
                });
            }

            // The build's concurrency, not a faster one: this is somebody else's
            // endpoint and restraint counts for more than speed.
            function inWaves(batches) {
                var out = new Array(batches.length), next = 0, stopped = false;

                function pull() {
                    // Once one batch has given up, the leg has no heights and
                    // nothing the others fetch will be used. Without this the
                    // reader is told the leg failed while the page carries on
                    // asking the service for the rest of it — the opposite of
                    // the restraint the concurrency is set for.
                    if (stopped || next >= batches.length) { return Promise.resolve(); }
                    var mine = next;
                    next += 1;
                    return ask(batches[mine], 1).then(function (answers) { out[mine] = answers; return pull(); },
                        function (failure) { stopped = true; throw failure; });
                }

                var running = [];
                for (var i = 0; i < Math.min(PLAN.heightsWorkers, batches.length); i += 1) { running.push(pull()); }
                return Promise.all(running).then(function () {
                    var flat = [];
                    out.forEach(function (part) { part.forEach(function (one) { flat.push(one); }); });
                    return flat;
                });
            }

            // Cached by the leg's two ends, so taking a point back and putting
            // it down in the same place does not ask the service twice.
            //
            // **Keyed on the pair and not on the order it was given in.** Moving
            // a waypoint one place past its neighbour turns exactly one leg
            // round — it is what a reorder always does — and a cache that
            // treated A to B and B to A as different ground would fetch a leg
            // the page is already holding. The samples run one way and are read
            // back the other by ``mirrored``, so nothing downstream knows or
            // needs to.
            var asked = Object.create(null);
            var askedKeys = [];
            // And bounded, which it did not have to be while a leg could only be
            // added and taken back: a drag leaves one leg's samples behind every
            // time the pointer is let go, and a leg is up to twenty kilometres
            // of them. Oldest out first — the ends a reader is working between
            // are the ones they come back to.
            var ASKED_MOST = 64;

            function endKey(point) { return point.lon.toFixed(7) + ',' + point.lat.toFixed(7); }

            // Which way round the pair is asked for. Any consistent order does,
            // and this one is a comparison of the very strings the key is built
            // from, so the order and the key cannot come apart.
            function forwards(from, to) { return endKey(from) <= endKey(to); }

            // The same ground read from the other end: the coordinates reversed
            // and every distance measured from the far end instead. What comes
            // out is what the service would have answered had it been asked this
            // way round.
            function mirrored(answered) {
                var laid = answered.laid, count = laid.lon.length;
                var lon = [], lat = [], along = [], points = [];
                for (var i = count - 1; i >= 0; i -= 1) {
                    lon.push(laid.lon[i]); lat.push(laid.lat[i]);
                    along.push(laid.length - laid.along[i]);
                    points.push(answered.points[i]);
                }
                return {laid: {lon: lon, lat: lat, along: along, length: laid.length}, points: points};
            }

            // ---- heights off the tiles, where the map carries them ----------
            // Both maps carry them and neither asks a service: Abisko has none
            // to ask, and Lomsdal-Visten stopped asking Geonorge's when it got
            // a tree of its own (decisions §6.10). What they read is
            // the height tiles the build cut (decisions §6.3): Terrarium-packed
            // PNGs at `PLAN.heightsTiles.url`, addressed like the map tiles and
            // kept like them by the worker, so a straight leg planned offline
            // over kept ground reads the same surface the build read. Each
            // sample is read bilinearly between the four pixel centres round
            // it, at the finest zoom cut -- the rule the build reads its own
            // mosaic by -- and a tile that is not there is ground the model
            // does not cover, which every sample on it says with NaN.
            var HEIGHT_TILE_PX = 256;
            // Decoded tiles, bounded: a z13 tile is 256 kB of floats, and a
            // reader working between two ends comes back to the same few.
            var decoded = Object.create(null), decodedKeys = [];
            var DECODED_MOST = 24;

            function heightTileUrl(x, y, z) {
                return PLAN.heightsTiles.url.replace('{z}', z).replace('{x}', x).replace('{y}', y);
            }

            // The pixels of one tile as heights, through a canvas: the browser
            // decodes the PNG, the canvas hands the bytes back, and the three
            // channels unpack the way `dem_tiles.unpack` does. Asked for
            // without colour management, because a byte that has been through
            // a colour profile is no longer a height.
            function heightsOf(blob) {
                function into(image, width, height) {
                    var canvas = document.createElement('canvas');
                    canvas.width = width; canvas.height = height;
                    var context = canvas.getContext('2d', {willReadFrequently: true});
                    context.drawImage(image, 0, 0);
                    var bytes = context.getImageData(0, 0, width, height).data;
                    var out = new Float32Array(width * height), tiles = PLAN.heightsTiles;
                    for (var i = 0, k = 0; i < out.length; i += 1, k += 4) {
                        var r = bytes[k], g = bytes[k + 1], b = bytes[k + 2];
                        // (0, 0, 0) is the tile's own word for no height.
                        out[i] = (r === 0 && g === 0 && b === 0) ? NaN : r * 256 + g + b / tiles.step - tiles.offset;
                    }
                    return {width: width, height: height, heights: out};
                }
                if (window.createImageBitmap) {
                    return createImageBitmap(blob, {colorSpaceConversion: 'none', premultiplyAlpha: 'none'}).then(function (bitmap) {
                        var read = into(bitmap, bitmap.width, bitmap.height);
                        if (bitmap.close) { bitmap.close(); }
                        return read;
                    });
                }
                return new Promise(function (resolve, reject) {
                    var url = URL.createObjectURL(blob), image = new Image();
                    image.onload = function () {
                        URL.revokeObjectURL(url);
                        resolve(into(image, image.naturalWidth, image.naturalHeight));
                    };
                    image.onerror = function () {
                        URL.revokeObjectURL(url);
                        reject(new Error('a height tile could not be decoded'));
                    };
                    image.src = url;
                });
            }

            // One tile, fetched and decoded once, with the same deadline the
            // service gets: through the worker, so the switch on answers it
            // from what was kept -- or with the worker's blank tile, which is
            // 1 x 1 and is read here as a tile that is not there.
            function fetchHeightTile(x, y, z) {
                var key = z + '/' + x + '/' + y;
                if (decoded[key]) { return decoded[key]; }
                var stop = window.AbortController ? new AbortController() : null;
                var giveUp = stop
                    ? window.setTimeout(function () { stop.abort(); }, PLAN.heightsTimeoutMs)
                    : null;
                function letGo() { if (giveUp !== null) { window.clearTimeout(giveUp); giveUp = null; } }
                var fetching = fetch(heightTileUrl(x, y, z), stop ? {signal: stop.signal} : undefined)
                    .then(function (response) {
                        // Off the edge of what was cut: ground the model does
                        // not cover, and not a failure to retry.
                        if (response.status === 404) { return null; }
                        if (!response.ok) { throw new Error('the height tiles answered ' + response.status); }
                        return response.blob().then(heightsOf);
                    })
                    .then(function (read) {
                        letGo();
                        return read && read.width === HEIGHT_TILE_PX && read.height === HEIGHT_TILE_PX ? read : null;
                    }, function (failure) {
                        letGo();
                        if (stop && stop.signal.aborted) {
                            throw new Error('a height tile did not arrive within ' +
                                            Math.round(PLAN.heightsTimeoutMs / 1000) + ' s');
                        }
                        throw failure;
                    });
                decoded[key] = fetching;
                decodedKeys.push(key);
                while (decodedKeys.length > DECODED_MOST) { delete decoded[decodedKeys.shift()]; }
                fetching.then(null, function () { if (decoded[key] === fetching) { delete decoded[key]; } });
                return fetching;
            }

            // **How many attempts at a height were actually made.** The retry
            // policy is a claim about this page, and a check that reads it off
            // a clock is reading the machine instead -- so the page counts, and
            // counts where the retrying is: these tiles are served beside the
            // page and are what a leg's profile is read from. The height
            // *model* over the wire is asked for by `ask` and is a different
            // road, which is where this counter sat first and read zero.
            //
            // And counted here rather than at the far end: an attempt that
            // times out need never have reached a server at all. Driven with
            // every connection held open, the later attempts sit behind the
            // browser's own limit per host and expire where they queue -- the
            // server saw one of three, and a check counting its log called a
            // working retry a failure.
            var heightAsks = 0;

            function heightTile(x, y, z, attempt) {
                heightAsks += 1;
                return fetchHeightTile(x, y, z).catch(function (failure) {
                    if (attempt >= ATTEMPTS) { throw failure; }
                    return new Promise(function (resolve) { setTimeout(resolve, 500 * attempt); })
                        .then(function () { return heightTile(x, y, z, attempt + 1); });
                });
            }

            // Web Mercator pixel coordinates at the tiles' zoom, fractional.
            function pixelAt(lon, lat, z) {
                var n = Math.pow(2, z) * HEIGHT_TILE_PX;
                var s = Math.sin(lat * Math.PI / 180);
                return {x: (lon + 180) / 360 * n, y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n};
            }

            // `once` is the picker's: a tap is cheap to repeat and a retry
            // chain is not, so a tap asks each tile exactly once and takes a
            // refusal as an answer. A leg keeps the three attempts, because a
            // leg is asked for once and its profile is the whole point of it.
            function tileHeights(laid, once) {
                var z = PLAN.heightsTiles.zoom, count = laid.lon.length;
                // A pixel's centre is half a pixel in from its corner, so a
                // position less a half names the centre to its north-west and
                // the fraction left over is the weight of the one beyond it.
                var px = new Array(count), py = new Array(count), wanted = Object.create(null);
                for (var i = 0; i < count; i += 1) {
                    var at = pixelAt(laid.lon[i], laid.lat[i], z);
                    px[i] = at.x - 0.5; py[i] = at.y - 0.5;
                    var x0 = Math.floor(px[i]), y0 = Math.floor(py[i]);
                    [[x0, y0], [x0 + 1, y0], [x0, y0 + 1], [x0 + 1, y0 + 1]].forEach(function (corner) {
                        var tx = Math.floor(corner[0] / HEIGHT_TILE_PX), ty = Math.floor(corner[1] / HEIGHT_TILE_PX);
                        wanted[tx + ',' + ty] = [tx, ty];
                    });
                }
                var keys = Object.keys(wanted);
                return Promise.all(keys.map(function (k) {
                    return once ? fetchHeightTile(wanted[k][0], wanted[k][1], z)
                                : heightTile(wanted[k][0], wanted[k][1], z, 1);
                }))
                    .then(function (tiles) {
                        var held = Object.create(null);
                        keys.forEach(function (k, n) { held[k] = tiles[n]; });
                        function at(gx, gy) {
                            var tx = Math.floor(gx / HEIGHT_TILE_PX), ty = Math.floor(gy / HEIGHT_TILE_PX);
                            var tile = held[tx + ',' + ty];
                            if (!tile) { return NaN; }
                            return tile.heights[(gy - ty * HEIGHT_TILE_PX) * tile.width + (gx - tx * HEIGHT_TILE_PX)];
                        }
                        var points = [];
                        for (var i = 0; i < count; i += 1) {
                            var x0 = Math.floor(px[i]), y0 = Math.floor(py[i]), fx = px[i] - x0, fy = py[i] - y0;
                            var h00 = at(x0, y0), h10 = at(x0 + 1, y0), h01 = at(x0, y0 + 1), h11 = at(x0 + 1, y0 + 1);
                            // A missing corner makes the sample missing: the
                            // arithmetic carries NaN through on its own.
                            var height = (h00 * (1 - fx) + h10 * fx) * (1 - fy) + (h01 * (1 - fx) + h11 * fx) * fy;
                            // No sea in a model of the ground: a lake is a flat
                            // reading at its level, walked as the build walks it.
                            points.push({height: height, sea: false});
                        }
                        return points;
                    });
            }

            function beginHeights(from, to) {
                var laid;
                // A leg refused for its length is a leg with no heights, which
                // the route already knows how to say. Thrown from here it would
                // escape the click instead.
                try {
                    laid = straightSamples(from, to);
                } catch (refused) {
                    return Promise.reject(refused);
                }
                if (PLAN.heightsTiles) {
                    return tileHeights(laid).then(function (points) { return {laid: laid, points: points}; });
                }
                var batches = [];
                for (var i = 0; i < laid.lon.length; i += PLAN.heightsBatch) {
                    var slice = [];
                    for (var k = i; k < Math.min(i + PLAN.heightsBatch, laid.lon.length); k += 1) {
                        // Asked in the page's own coordinates. The service takes
                        // longitude and latitude as readily as the metric grid
                        // the build uses — measured, not assumed — so nothing
                        // here reprojects anything.
                        slice.push([Number(laid.lon[k].toFixed(7)), Number(laid.lat[k].toFixed(7))]);
                    }
                    batches.push(slice);
                }
                return inWaves(batches).then(function (points) { return {laid: laid, points: points}; });
            }

            function remember(key, answering) {
                asked[key] = answering;
                askedKeys.push(key);
                while (askedKeys.length > ASKED_MOST) { delete asked[askedKeys.shift()]; }
                // A refusal must not be remembered as one for ever: the next
                // click on the same ground should ask again. Two handlers rather
                // than a catch, so that this one sees only the refusal.
                answering.then(null, function () { if (asked[key] === answering) { forget(key); } });
            }

            function forget(key) {
                delete asked[key];
                var at = askedKeys.indexOf(key);
                if (at >= 0) { askedKeys.splice(at, 1); }
            }

            // The heights for a leg drawn straight: out of the cache if this
            // ground is already in hand, and otherwise out of the service —
            // unless nothing may be asked, which is what a live drag says, and
            // then there are none.
            function heightsFor(from, to, mayAsk) {
                var forward = forwards(from, to);
                var a = forward ? from : to, b = forward ? to : from;
                var key = endKey(a) + '|' + endKey(b);
                var answering = asked[key];
                if (!answering) {
                    if (!mayAsk) { return null; }
                    answering = beginHeights(a, b);
                    remember(key, answering);
                }
                return forward ? answering : answering.then(mirrored);
            }

            // The samples classify the ground and the split falls out of them:
            // where two neighbours disagree the shoreline lies between, and half
            // way between is as near as sampling every few metres can put it. No
            // coastline is consulted and none is needed.
            // **Which rivers a straight line wades through, and how wide the
            // water is there.** Every place the line cuts a ring of an outline,
            // in order along the line; between one cut and the next the line is
            // inside the water or out of it, and which is settled once, at the
            // start, by the same even-odd test the protected areas use. The
            // width is the length of the run inside. A line that starts or ends
            // in the water has a run with only one cut, and that run is counted
            // too: the reader is standing in it.
            //
            // A sentence and not a price. Measured over this build's rivers:
            // half are under 17 m across and five in six under 30 m, which a
            // walker fords or does not by depth and current, and no layer
            // records either. The figure is what they weigh it by.
            function riverCrossings(graph, from, to) {
                var rivers = graph.rivers || [];
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                if (!rivers.length || !(length > 0)) { return []; }
                var west = Math.min(from.lon, to.lon), east = Math.max(from.lon, to.lon);
                var south = Math.min(from.lat, to.lat), north = Math.max(from.lat, to.lat);
                var dx = to.lon - from.lon, dy = to.lat - from.lat;
                var found = [];
                rivers.forEach(function (river, which) {
                    var box = river.bounds;
                    if (box[2] < west || box[0] > east || box[3] < south || box[1] > north) { return; }
                    var cuts = [];
                    river.rings.forEach(function (ring) {
                        for (var i = 0, k = ring.length - 1; i < ring.length; k = i, i += 1) {
                            var ax = ring[k][0], ay = ring[k][1], ex = ring[i][0] - ax, ey = ring[i][1] - ay;
                            var den = dx * ey - dy * ex;
                            if (den === 0) { continue; }
                            var t = ((ax - from.lon) * ey - (ay - from.lat) * ex) / den;
                            var u = ((ax - from.lon) * dy - (ay - from.lat) * dx) / den;
                            if (t < 0 || t > 1 || u < 0 || u >= 1) { continue; }
                            cuts.push(t);
                        }
                    });
                    var inside = graph.riverAt(from.lon, from.lat).indexOf(which) >= 0;
                    if (!cuts.length && !inside) { return; }
                    cuts.sort(function (a, b) { return a - b; });
                    var began = inside ? 0 : null;
                    for (var c = 0; c < cuts.length; c += 1) {
                        if (began === null) { began = cuts[c]; continue; }
                        found.push({name: river.name, width: (cuts[c] - began) * length, at: began * length});
                        began = null;
                    }
                    if (began !== null) { found.push({name: river.name, width: (1 - began) * length, at: began * length}); }
                });
                return found.sort(function (a, b) { return a.at - b.at; });
            }

            function straightParts(graph, from, to, answered) {
                var laid = answered.laid, points = answered.points, count = points.length;
                // What each sample is standing in, worked out once: a leg is
                // classified here and its shoreline split is read off the same
                // list, and asking the polygons twice for one position is the
                // shape a disagreement takes.
                var standing = new Array(count);
                for (var s = 0; s < count; s += 1) { standing[s] = graph.areasAt(laid.lon[s], laid.lat[s]); }
                // **Whether a sample is on water is the graph's water grid's
                // answer, not the height source's.** It used to be the point
                // service's `terreng` field, which is where it came from rather
                // than where it belonged — and when both maps moved to height
                // tiles (§6.10) that field went with the service, so a leg over
                // a fjord came back as walked ground with a profile along it.
                // The grid is a better answer in three ways: it is what the
                // *router* already prices this leg by, so the way drawn and the
                // way described stop being two opinions; it holds lakes as well
                // as sea, because a straight leg across a tarn is as much a
                // fiction as one across a fjord; and it is in the page, so it
                // answers with no network. `points[i].sea` is still honoured,
                // for a page whose heights do come from a service.
                //
                // **A walking river is waded, so it is not wet here.** In kayak
                // mode the grid's water includes river surfaces too.
                // Lantmäteriet draws a watercourse wide enough to have
                // two banks as a water surface, so Abiskojåkka is in the grid
                // exactly as Torneträsk is, and classifying by the grid alone
                // cut the leg in two at the bank. That is wrong twice over: a
                // ford leaves the walked distance and the profile to be
                // reported as a crossing, which reads as a boat; and the width
                // sentence, which is measured per land part, then measures a
                // run the grid truncated rather than the river — Abiskojåkka
                // came back 14 m wide where the outline says 22. The outlines
                // are carried for this question and answer it to the metre
                // (`riverCrossings` below), so the grid's say is dropped where
                // they apply. Measured: Abisko 14 m → 22 m, Lomsdal-Visten's
                // Storelva unchanged at 27, since no Norwegian river of this
                // build is in the grid at all.
                var wet = new Array(count), river = new Array(count);
                for (var w = 0; w < count; w += 1) {
                    river[w] = !!graph.riverAt(laid.lon[w], laid.lat[w]).length;
                    wet[w] = (!!points[w].sea
                        || (!!graph.waterAt(laid.lon[w], laid.lat[w]) && (kayak() || !river[w])))
                        && !(kayak() && graph.damAt && graph.damAt(laid.lon[w], laid.lat[w]));
                }
                // Where the samples change their mind about what is under them.
                // Named for what it is: in this file `edges` means edges of the
                // graph, and these are the ends of the runs.
                var changes = [0];
                for (var i = 1; i < count; i += 1) {
                    if (wet[i] !== wet[i - 1] || (kayak() && wet[i] && river[i] !== river[i - 1])) { changes.push(i); }
                }
                changes.push(count);

                function positionAt(distance) {
                    var t = laid.length > 0 ? distance / laid.length : 0;
                    return {lon: from.lon + t * (to.lon - from.lon), lat: from.lat + t * (to.lat - from.lat)};
                }

                var parts = [];
                for (var run = 0; run + 1 < changes.length; run += 1) {
                    var first = changes[run], last = changes[run + 1];
                    var began = run === 0 ? 0 : (laid.along[first - 1] + laid.along[first]) / 2;
                    var ended = last === count ? laid.length : (laid.along[last - 1] + laid.along[last]) / 2;
                    var head = positionAt(began), tail = positionAt(ended);
                    if (wet[first] && !kayak()) {
                        parts.push({kind: 'water', lon: [head.lon, tail.lon], lat: [head.lat, tail.lat],
                                    along: [0, ended - began], length: ended - began,
                                    height: null, distance: null, read: false, tally: blankTally()});
                        continue;
                    }
                    var height = [], distance = [], read = false;
                    for (var s = first; s < last; s += 1) {
                        height.push(points[s].height);
                        distance.push(laid.along[s] - began);
                        if (!isNaN(points[s].height)) { read = true; }
                    }
                    // Shore pixels can include the bank. One water run takes
                    // its lowest finite reading. River parts keep their fall;
                    // a run with no finite reading stays unread.
                    if (wet[first] && kayak() && !river[first]) {
                        var level = Infinity;
                        height.forEach(function (h) { if (isFinite(h) && h < level) { level = h; } });
                        if (isFinite(level)) { height = height.map(function () { return level; }); }
                    }
                    // Two vertices and no more: the reader drew a straight line,
                    // so the two ends are every corner it has. The file's 5 m
                    // fill lays its points along it from these.
                    var tally = straightTally(graph, laid, standing, first, last, began, ended);
                    if (wet[first]) { tally.unmarked = 0; }
                    parts.push({kind: wet[first] ? 'paddled' : 'land', lon: [head.lon, tail.lon], lat: [head.lat, tail.lat],
                                along: [0, ended - began], length: ended - began,
                                height: height, distance: distance, read: read,
                                rivers: wet[first] ? [] : riverCrossings(graph, head, tail),
                                tally: tally});
                }
                return parts;
            }

            // A route that may only follow recorded ways is not a plan for this
            // park: 19.9 km of UT.no's own routes run where no source records
            // anything. So where the network cannot carry a leg it is drawn
            // straight rather than refused.
            // **A leg the network cannot carry is not fetched while a drag is
            // live.** Its heights are seconds of somebody else's service, the
            // ground under a waypoint being dragged is new at every position,
            // and the endpoint cache answers only for ends already visited — so
            // asking at the rate a pointer moves is the uncapped request stream
            // this phase exists not to build. It is carried at its own straight
            // length with nothing read along it instead: the walked distance
            // under the reader's hand stays right, the route says the leg is
            // still being worked out, and the one request goes out when the
            // pointer is let go. Ground already in hand is used either way,
            // which is what makes dragging a point back where it came from cost
            // nothing at all.
            // `partly` asks for the honest answer where there is no continuous
            // way: **what is walkable, walked, and only the rest crossed.**
            // Reported from the phone -- a goal with no path to it was answered
            // with *no way there*, because the fallback is one straight line
            // from end to end and a line that long is refused outright. Nearly
            // all of such a journey is on paths and the part that is not is
            // usually its last stretch, so this routes to the reachable node
            // nearest the goal and draws the remainder straight from there.
            //
            // Asked for by the goal and not by the plan, for now: a plan's legs
            // are what its file is written from, and changing what a leg is
            // made of changes every figure and every file that comes out of one.
            // The mechanism is here rather than beside the goal so that plan
            // mode can take it up by passing a flag.
            function resolve(graph, from, to, mayAsk, partly) {
                // **A leg the file described is laid out the way it described
                // it**, before anything else is tried. It has to come first for
                // the same reason the recorded test does and one more: both ends
                // may well sit on a node, so routing would quietly replace a
                // recorded stretch, and the seam this restores is *inside* the
                // leg where the recorded test cannot see it at all.
                // Only for the far point the file put it with: a point that
                // was dragged is a new object, a point taken out leaves its
                // neighbour facing another, and both are legs the file never
                // described (see `pointsForLoaded`).
                if (from.restore && from.restoreTo === to) {
                    var laid = restoredParts(graph, from, to, from.restore);
                    if (laid) { return Promise.resolve(laid); }
                }
                // **A leg between two points of the loaded recording is the
                // recording's**, whichever of the two modes put them there.
                // Tested before the network is, because both of its ends may
                // well sit on a node — a recording of a path this map already
                // draws is on the network at every point — and routing between
                // them would silently replace what was recorded with whatever
                // the router prefers.
                if (loaded && from.track === loaded.id && to.track === loaded.id && from.at !== to.at) {
                    return Promise.resolve(recordedParts(graph, from, to));
                }
                if (onNetwork(from) && onNetwork(to)) {
                    var found = routeBetween(graph, from, to);
                    if (found && worthRouting(graph, from, to, found.cost, found.land)) {
                        return Promise.resolve(routedParts(graph, found));
                    }
                }
                if (partly) {
                    // **Both ends, and neither of them need be on a path.** The
                    // reader is as likely to be off the network as the goal is
                    // -- somebody standing in a bog is exactly the person asking
                    // which way -- and `snapped` gives up beyond its own reach,
                    // which is right for placing a waypoint and wrong here. So
                    // neither end is snapped at all: they are joined to the
                    // graph by connectors and the cheapest way through wins.
                    var joined = joinedRoute(graph, from, to);
                    if (joined) {
                        return partlyRouted(graph, from, to, joined, mayAsk);
                    }
                    // The direct connector won, which in this reading is an
                    // answer and not a failure -- and it is drawn the way every
                    // other straight leg is, below. **Not by `walkTo`, which
                    // swallows a refusal from the height service.** A plan's leg
                    // that could not get its heights has to say so: *there are
                    // no heights here* and *the service did not answer* are
                    // different facts and only one of them is worth trying
                    // again, and a leg drawn quietly with a hole in it conflates
                    // them. A goal wants the tolerant reading and takes it where
                    // it belongs, in `oneLeg`.
                }
                var answering = heightsFor(from, to, mayAsk);
                if (!answering) { return Promise.resolve(waitingParts(from, to)); }
                return answering.then(function (answered) { return straightParts(graph, from, to, answered); });
            }

            // **A way round has to beat walking, and until this nothing asked.**
            // A leg between two points that both sit on the network took
            // whatever the router found, however long. Reported from the phone
            // for a goal and measured again here for a plan, with the same
            // three taps: 77.20 km for 10.00 km flown, one leg of it 66.73 km
            // for a straight 2.15 km. Both points had been snapped, one of them
            // on to a fragment of path in the next valley, and the way between
            // those two nodes genuinely is a loop round half the park -- it is
            // the answer to a question nobody asked.
            //
            // The same comparison `joinedRoute` makes and in the same metres:
            // an edge costs its length times its source's factor, so the
            // straight line priced at `offPathFactor` is the thing to beat.
            // Which also means a leg here can never be more than that many
            // times the line it could have flown. **Priced by what it crosses**,
            // like every connector: two waypoints on paths either side of a
            // sound, and the road round it, would otherwise be thrown away
            // for a dotted line over the water because the road is more than
            // three times the line.
            //
            // **Only where there is something to draw instead.** A leg longer
            // than `maxStraightM` cannot be drawn straight at all -- it is
            // refused for its sampling -- and refusing a long way round in
            // favour of nothing at all is the worse of the two answers. So past
            // that length the route stands, whatever it costs.
            function worthRouting(graph, from, to, cost, land) {
                var flown = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                if (flown > PLAN.maxStraightM) { return true; }
                var direct = connectorPrice(graph, from.lon, from.lat, to.lon, to.lat);
                return !cheaper(direct.land, direct.cost, land || 0, cost);
            }

            // **The three pieces of a way that is only partly a path**: what the
            // reader walks to reach the network, the network itself, and what
            // they walk at the far end. Either straight piece is left out where
            // it has no length, which is every end that was standing on a node
            // already -- and it is a piece a metre long where the reader is a
            // metre off one, because nothing here moves them on to it.
            function partlyRouted(graph, from, to, joined, mayAsk) {
                var head = joined.head, tail = joined.tail, over = joined.over;
                var enter = {lat: graph.nodeLat[head], lon: graph.nodeLon[head], node: head};
                var leave = {lat: graph.nodeLat[tail], lon: graph.nodeLon[tail], node: tail};
                // **Whether this was worth doing at all was settled before it
                // was asked for**, by `joinedRoute`, which weighed the whole of
                // it -- both walks *and* the path between them -- against the
                // straight line. It used to be settled here and only half of it
                // was: the two walks were compared with the straight line and
                // the routed part was not, so a reader 100 m off a path was
                // sent along 66 km of it to reach a stop 2 km away, and the sum
                // that would have caught it had already returned yes. This
                // assembles the three pieces and judges nothing.
                var middle = over ? routedParts(graph, over) : [];
                // **An end standing on the network walks its own edge**, as
                // the piece of it between the point and the node -- path, and
                // drawn as path. Only an end off the network walks over the
                // ground to reach it.
                function pieceOf(cut) {
                    var part = cutPart(graph, cut);
                    return Promise.resolve(part ? [part] : []);
                }
                return Promise.all([joined.headCut ? pieceOf(joined.headCut) : walkTo(graph, from, enter, mayAsk),
                                    joined.tailCut ? pieceOf(joined.tailCut) : walkTo(graph, leave, to, mayAsk)])
                    .then(function (ends) { return ends[0].concat(middle, ends[1]); });
            }

            //: A stretch nobody routed, drawn straight and classified by its own
            //: height samples the way any other straight leg is -- which is what
            //: splits the last kilometre into the land it crosses and the water
            //: it does not.
            function walkTo(graph, from, to, mayAsk) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                if (length < 1) { return Promise.resolve([]); }
                // **Too long to sample is not too long to walk.** Reported from
                // the phone, 112 km from the goal: the way *was* routed, the
                // approach to the network came out at ninety-odd kilometres, and
                // the height service refuses a straight stretch past
                // `maxStraightM` -- which sank the whole answer and reported *no
                // way there* with a route in hand. That refusal is a fact about
                // sampling and not about the ground. The stretch is drawn for
                // what it is and the profile shows a hole in it, which is what a
                // hole in what is known looks like everywhere else on this page.
                if (length > PLAN.maxStraightM) { return Promise.resolve(plainParts(from, to, length)); }
                var answering = heightsFor(from, to, mayAsk);
                // Nothing may be asked -- a live drag -- so it is drawn straight
                // with no heights, which the route already knows how to say.
                if (!answering) { return Promise.resolve(waitingParts(from, to)); }
                return answering.then(
                    function (answered) { return straightParts(graph, from, to, answered); },
                    // And a service that refused for any other reason does not
                    // get to take the route down with it either.
                    function () { return plainParts(from, to, length); }
                );
            }

            //: A stretch drawn straight with nothing claimed about its heights,
            //: and not marked provisional: nothing is still being worked out
            //: here, this *is* the answer. `waitingParts` below is the other
            //: one, for a leg whose answer has not arrived yet, and it refuses a
            //: length this one has to accept.
            function plainParts(from, to, length) {
                var tally = blankTally();
                tally.unmarked = length;
                return [{kind: 'land', lon: [from.lon, to.lon], lat: [from.lat, to.lat],
                         along: [0, length], length: length, height: [NaN, NaN], distance: [0, length],
                         read: false, tally: tally}];
            }

            // What such a leg is in the meantime: its own straight line, its own
            // length, and no heights. **It counts as walked and as drawn
            // straight**, which is what keeps the distance honest under the
            // hand, and it counts as unsettled, which is what keeps the file
            // from being written out of it. What it does not carry is a
            // protected-area tally: that is read off the height samples at the
            // same halfway rule the shoreline split uses, and there are no
            // samples yet. Under-reporting it for as long as the panel says the
            // leg is still being worked out is the honest half of that; making
            // one up at a coarser spacing would be a second rule to disagree
            // with the first.
            function waitingParts(from, to) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                refuseLong(length);
                var tally = blankTally();
                tally.unmarked = length;
                return [{kind: 'land', lon: [from.lon, to.lon], lat: [from.lat, to.lat],
                         along: [0, length], length: length, height: [NaN, NaN], distance: [0, length],
                         read: false, tally: tally, provisional: true}];
            }


            // ---- reading a GPX back ------------------------------------------------
            // **This is the only place in the project where a reader and a
            // writer of the same file sit in one phase.** Every name the reader
            // looks for arrives in PLAN.gpx out of the same Python constant the
            // writer's own name comes from, so the two cannot drift: a page
            // reading `origin` while writing `Origin` would take every route it
            // ever wrote for a foreign track and say nothing about it.
            //
            // Addressed by namespace and local name rather than by tag, because
            // a prefix is the writer's choice and not the format's: a file that
            // spells this map's namespace `t:` instead of `trails:` says exactly
            // the same thing, and getElementsByTagName would miss all of it. The
            // GPX elements are looked up under any namespace at all, since a
            // consumer device that leaves the default namespace off writes a
            // file every other reader still accepts.
            function ours(parent, name) {
                return parent ? parent.getElementsByTagNameNS(PLAN.gpx.namespace, name) : [];
            }

            function firstText(parent, name) {
                var found = parent ? parent.getElementsByTagNameNS('*', name) : [];
                for (var i = 0; i < found.length; i += 1) {
                    // Only a child of this element, never a grandchild: a <trk>
                    // holds a <name> of its own and so does every <wpt> before
                    // it, and a search that went deep would give the track the
                    // first waypoint's name.
                    if (found[i].parentNode === parent) { return found[i].textContent; }
                }
                return null;
            }

            // Everything one loaded file says about itself, read once. Nothing
            // here decides anything: what the three modes do with it is below,
            // and a reader that also chose would have to be read twice to find
            // out what a file became.
            function parseGpx(text) {
                var doc = new DOMParser().parseFromString(text, 'application/xml');
                if (doc.getElementsByTagName('parsererror').length) {
                    throw new Error('this file is not XML that a browser can read');
                }
                var root = doc.documentElement;
                if (!root || root.localName !== 'gpx') {
                    throw new Error('this file is not GPX: its outermost element is <' + (root ? root.nodeName : 'nothing') + '>');
                }

                var segments = root.getElementsByTagNameNS('*', 'trkseg');
                var lon = [], lat = [], ele = [], ends = [], along = [], run = 0, s, p;
                for (s = 0; s < segments.length; s += 1) {
                    var points = segments[s].getElementsByTagNameNS('*', 'trkpt');
                    for (p = 0; p < points.length; p += 1) {
                        var x = parseFloat(points[p].getAttribute('lon')), y = parseFloat(points[p].getAttribute('lat'));
                        if (!isFinite(x) || !isFinite(y)) { continue; }
                        if (lon.length && !ends[lon.length - 1]) {
                            run += panel().metresBetween(lon[lon.length - 1], lat[lat.length - 1], x, y);
                        }
                        var height = firstText(points[p], 'ele');
                        lon.push(x); lat.push(y); along.push(run);
                        // A point with no <ele> keeps its place and loses only
                        // its height, which is the same distinction the writer
                        // keeps: there is ground here and no reading of it.
                        ele.push(height === null || height === '' ? NaN : parseFloat(height));
                        ends.push(false);
                    }
                    if (lon.length) { ends[lon.length - 1] = true; }
                }
                var breaks = 0;
                for (s = 0; s + 1 < lon.length; s += 1) { if (ends[s]) { breaks += 1; } }
                if (lon.length < 2) {
                    throw new Error('this file has ' + lon.length + ' trackpoints, and a route needs two');
                }

                // The track's own extensions, which is where a file this map
                // wrote says what it is. A chain export says its chain id and
                // has no waypoints at all; a planned route says its kind and
                // carries the points somebody clicked.
                var tracks = root.getElementsByTagNameNS('*', 'trk');
                var extensions = tracks.length ? firstChildNamed(tracks[0], 'extensions') : null;
                var kind = textOf(ours(extensions, PLAN.gpx.kindField));
                var chainId = textOf(ours(extensions, PLAN.gpx.chainField));

                var legs = [], unknown = Object.create(null);
                // Without a prototype, like every other table this page keys on
                // somebody else's words: `known['constructor']` on an object
                // literal is a function and reads as a kind this page knows.
                var known = Object.create(null);
                known.routed = true; known.land = true; known.water = true; known.paddled = true;
                known[CROSSING] = true;
                known[PLAN.gpx.trackKind] = true;
                var lists = ours(extensions, PLAN.gpx.legs);
                if (lists.length) {
                    var each = lists[0].getElementsByTagNameNS(PLAN.gpx.namespace, PLAN.gpx.leg);
                    for (s = 0; s < each.length; s += 1) {
                        var parts = each[s].getElementsByTagNameNS(PLAN.gpx.namespace, PLAN.gpx.part), made = [];
                        for (p = 0; p < parts.length; p += 1) {
                            // A part with no kind at all is named as that
                            // rather than as a kind called 'null', which is what
                            // an absent attribute reads as once it is a key.
                            var said = parts[p].getAttribute(PLAN.gpx.partKind);
                            if (said === null) { said = 'no kind at all'; }
                            if (!known[said]) { unknown[said] = (unknown[said] || 0) + 1; }
                            made.push({kind: said, m: parseFloat(parts[p].getAttribute(PLAN.gpx.partLength))});
                        }
                        legs.push(made);
                    }
                }

                // **The generated markers are skipped here and nowhere else.**
                // 6B marks every one the map placed by itself — at a park
                // boundary, at a hut — and a reader that took them for stations
                // somebody chose would give the route points nobody put down and
                // then route through them. Skipped rather than counted and
                // dropped later: one place to get it wrong is enough.
                var carried = root.getElementsByTagNameNS('*', 'wpt'), waypoints = [];
                var generated = 0, strange = 0;
                for (p = 0; p < carried.length; p += 1) {
                    var block = firstChildNamed(carried[p], 'extensions');
                    var origin = textOf(ours(block, PLAN.gpx.origin));
                    // What says `set`, and what says nothing at all — a file
                    // from anywhere else has no origin on its waypoints, and
                    // every one of those is a station somebody chose. Anything
                    // else is skipped, which is the conservative way round: a
                    // value this page has never heard of is likelier a later
                    // writer's second kind of marker than a station, and taking
                    // it would put a point on the route that nobody placed.
                    //
                    // The two reasons for skipping are counted apart because
                    // they mean different things to a reader: a marker this map
                    // placed is expected and a word this page does not know is a
                    // file from a later build, and one of those is worth saying.
                    if (origin === PLAN.gpx.generated) { generated += 1; continue; }
                    if (origin !== null && origin !== PLAN.gpx.set) { strange += 1; continue; }
                    waypoints.push({lat: parseFloat(carried[p].getAttribute('lat')),
                                    lon: parseFloat(carried[p].getAttribute('lon')),
                                    name: firstText(carried[p], 'name'),
                                    kind: firstText(carried[p], 'type'),
                                    // Null where the element is absent and a
                                    // string where it stands, empty included:
                                    // an unnamed cut is a cut.
                                    stage: textOf(ours(block, PLAN.gpx.stage))});
                }

                loadedCount += 1;
                return {
                    id: 'loaded-' + loadedCount,
                    name: (tracks.length ? firstText(tracks[0], 'name') : null) ||
                          firstText(firstChildNamed(root, 'metadata'), 'name') || 'the loaded file',
                    isRoute: kind === PLAN.gpx.kind,
                    chainId: chainId,
                    waypoints: waypoints, generated: generated, strange: strange, legs: legs,
                    unknown: Object.keys(unknown),
                    lon: Float64Array.from(lon), lat: Float64Array.from(lat),
                    ele: Float64Array.from(ele), along: Float64Array.from(along),
                    // **Counted, not taken off the element list.** An empty
                    // <trkseg>, or one whose points are all unreadable, is a
                    // segment that leaves no break behind, and a page reporting
                    // '2 breaks, which are crossings' where the route has one
                    // has miscounted the thing this file is most careful about.
                    ends: ends, n: lon.length, breaks: breaks, mode: null
                };
            }

            function firstChildNamed(parent, name) {
                if (!parent) { return null; }
                for (var i = 0; i < parent.childNodes.length; i += 1) {
                    if (parent.childNodes[i].localName === name) { return parent.childNodes[i]; }
                }
                return null;
            }

            function textOf(list) {
                return list && list.length ? list[0].textContent : null;
            }

            // Which recorded point a written position stands at. A waypoint of
            // this map's own is exact to seven decimals, which is 11 cm, so this
            // is a lookup and not a match — but it is written as a search over
            // the whole recording because a file may have been edited by hand,
            // and a waypoint that landed on the wrong point would move a leg
            // rather than fail.
            function recordedAt(lon, lat) {
                var best = -1, closest = Infinity;
                for (var i = 0; i < loaded.n; i += 1) {
                    var away = panel().metresBetween(lon, lat, loaded.lon[i], loaded.lat[i]);
                    if (away < closest) { closest = away; best = i; }
                }
                return {at: best, away: closest};
            }

            // ---- the three modes ---------------------------------------------------
            // What a loaded file may become. The names travel with the control
            // and with window.trailsPlan.load, so a browser check drives the
            // same three things a reader picks from.
            //
            // **The middle one is not routing a foreign track**, and the table
            // reads oddly until that is said: re-routing between waypoints
            // throws the recorded shape away, which is exactly right for one of
            // this map's own plans — a plan *is* a handful of waypoints, and the
            // track under it was drawn from them — and useless for a recording
            // of thousands of points and no waypoints at all. Given one of
            // those it routes between its two ends, which is a thing somebody
            // may well want and is never a surprise, because the status line
            // says the file had no waypoints in it.
            var MODES = [
                {key: 'asis', label: 'Take it as it is'},
                {key: 'align', label: 'Align to the network'},
                {key: 'match', label: 'Match where a path exists'}
            ];

            // ---- what a mode does to *this* file ------------------------------------
            // **Three names cannot be true of two kinds of file at once**, and
            // that is what the mode picker asked of them for as long as it stood
            // beside the button: it had to be answered before anybody knew what
            // was in the file. Read as a plan, 'take it as it is' means the
            // route as it was planned; read as a recording it means the line as
            // it was walked. Both readings are reasonable and the picker offered
            // one word for them.
            //
            // So the question is asked once the file has been read, in terms of
            // the file: what it turned out to be, what each mode would do to it,
            // and which one is offered first. **One table, keyed by both** —
            // the wording and the default are one decision, and two recordings
            // of one decision drifting apart is the failure this page has found
            // three times.
            //
            // Nothing is withheld. Routing between the two ends of a recording
            // is rarely what anybody wants and is occasionally exactly it, so it
            // is named rather than taken away: a mode that works and is refused
            // is a capability lost, where a mode that says what it will do is a
            // reader who chose.
            var READINGS = {
                route: {
                    first: 'asis',
                    asis: 'Restore the plan: its points, its legs, and the stretches it kept as recorded.',
                    align: 'Keep its points and plan between them again, over the network as it now stands.',
                    match: 'Keep its line and attach it to the network again wherever a path exists.'
                },
                chain: {
                    first: 'asis',
                    asis: 'Take the line as it is \u2014 it came off this map and is already exact.',
                    align: 'Route between its two ends only \u2014 the line itself is not kept.',
                    match: 'Lay it on the network again wherever a path exists.'
                },
                track: {
                    first: 'match',
                    asis: 'Take the recorded line exactly as it was walked.',
                    align: 'Route between its two ends only \u2014 the recording is not kept.',
                    match: 'Put it on the network wherever a path exists, and keep the rest as recorded.'
                }
            };

            // Which of the three kinds a read file is. The same three questions
            // describeFile asks, in the same order, because a file that says it
            // is one of this map's routes is that whatever else it carries.
            function kindOf(read) {
                if (read.isRoute) { return 'route'; }
                if (read.chainId) { return 'chain'; }
                return 'track';
            }

            // A break between two segments is a crossing and is never walked.
            // **This is the one reading of a loaded file that must not be got
            // wrong quietly**: GPX has no way to say a segment is a boat, so a
            // break is all a crossing leaves behind, and a page that joined the
            // two ends with a walked line would draw somebody a route across a
            // fjord. It counts as a crossing, adds nothing to the walking
            // distance and carries no profile — the same as every other
            // crossing on this map.
            // **The kind is handed in where one is known.** A crossing is a
            // crossing whichever of the two it is, and both are dashed the same
            // — but a route restored from a file that said `ferry` and written
            // out again saying `water` has quietly changed what it claims about
            // a fjord somebody has to get across.
            function crossingPart(from, to, kind) {
                var length = panel().metresBetween(from.lon, from.lat, to.lon, to.lat);
                return {kind: kind || 'water', lon: [from.lon, to.lon], lat: [from.lat, to.lat],
                        along: [0, length], length: length, height: null, distance: null,
                        read: false, tally: blankTally()};
            }

            // The same ground, walked the other way. A route whose two ends are
            // swapped is phase 7's third edit and it reaches a matched leg like
            // any other, so the parts are turned round rather than matched
            // again — matching backwards would anchor from the far end and could
            // answer differently, and a route that changed when it was reversed
            // would be a route measured twice.
            function turnedRound(part) {
                var made = {kind: part.kind, length: part.length, tally: part.tally, read: part.read};
                made.lon = part.lon.slice().reverse();
                made.lat = part.lat.slice().reverse();
                made.along = part.along.map(function (value) { return part.length - value; }).reverse();
                if (part.index) {
                    made.index = {from: part.index.from + (part.index.count - 1) * part.index.step,
                                  step: -part.index.step, count: part.index.count};
                }
                if (part.height === null) { made.height = null; made.distance = null; return made; }
                made.height = part.height.slice().reverse();
                made.distance = part.distance.map(function (value) { return part.length - value; }).reverse();
                return made;
            }

            function walkedBackwards(parts) {
                var out = [];
                for (var i = parts.length - 1; i >= 0; i -= 1) { out.push(turnedRound(parts[i])); }
                return out;
            }

            // What a leg between two waypoints of the loaded recording is, which
            // is the whole of what the modes change. Anything not anchored to the
            // recording falls through to the routing and the sampling that were
            // already here, so a waypoint dragged off the track needs no case of
            // its own: it stops being anchored and its legs become ordinary ones.
            function recordedParts(graph, from, to) {
                var low = from.at < to.at ? from.at : to.at, high = from.at < to.at ? to.at : from.at;
                var parts = [], at = low, i;
                // **Every break inside the stretch, not only a stretch that is
                // nothing but a break.** Take one of the two waypoints either
                // side of a break out — which phase 7's Remove does in one
                // click, and which merges the two legs that met there — and the
                // leg left behind spans the gap. Walked straight across, that is
                // a line drawn over a fjord and counted as ground, which is the
                // one thing this distinction exists to prevent. It is also why
                // `loaded.along` does not advance across a break and this must
                // not either.
                for (i = low; i < high; i += 1) {
                    if (!loaded.ends[i]) { continue; }
                    parts.push.apply(parts, walkedBetween(graph, at, i));
                    parts.push(crossingPart({lon: loaded.lon[i], lat: loaded.lat[i]},
                                            {lon: loaded.lon[i + 1], lat: loaded.lat[i + 1]}));
                    at = i + 1;
                }
                parts.push.apply(parts, walkedBetween(graph, at, high));
                return from.at < to.at ? parts : walkedBackwards(parts);
            }

            // ---- restoring a plan ---------------------------------------------------
            // **Take it as it is, read as what the file describes.** For
            // somebody's recording that is the line as it was walked, and it
            // always was. For a route this map wrote it is the *plan* — the
            // stations, the legs, and what each leg is made of — and until this
            // it was not: the stations were rebuilt out of the track's ends and
            // its breaks, which is right for a file that carries no waypoints
            // and wrong for one that carries its own. Measured, six points went
            // out and two came back, with the walked distance right to a
            // decimetre so that nothing looked wrong.
            //
            // Whether there is a plan in the file to restore. Every part of the
            // test is load-bearing: without the leg list there is nothing saying
            // what a leg was made of, and where the waypoints and the legs do
            // not count up the file was written by something this page does not
            // understand and the old reading is the safe one.
            function restoring() {
                return !!loaded && loaded.mode === 'asis' && loaded.isRoute &&
                    loaded.legs.length > 0 && loaded.waypoints.length === loaded.legs.length + 1;
            }

            // The track point a walked distance falls on, searched forward from
            // where the last part ended. **Forward, and not a binary search.**
            // `along` is the *walking* axis, so it stands still across a break —
            // a crossing advances the walk by nothing — and one distance
            // therefore names two points either side of it. Which of them a part
            // means depends on where the part started, and only a walk knows
            // that. On a tie the earlier wins, because a walked part ends *at*
            // the break and the stretch after it is begun deliberately.
            function alongIndex(distance, from) {
                var best = from, i;
                for (i = from; i < loaded.n; i += 1) {
                    if (Math.abs(loaded.along[i] - distance) < Math.abs(loaded.along[best] - distance)) { best = i; }
                    if (loaded.along[i] > distance) { break; }
                }
                return best;
            }

            // The break standing at a walked distance, for the one case that
            // cannot be reached by walking forward: a leg whose first part is a
            // crossing, because its own waypoint is out on the water and is in
            // no <trkseg> at all. Half a metre, because the two sides of a break
            // carry the same distance exactly and nothing else is near it.
            function breakAt(distance) {
                for (var i = 0; i + 1 < loaded.n; i += 1) {
                    if (loaded.ends[i] && Math.abs(loaded.along[i] - distance) < 0.5) { return i; }
                }
                return -1;
            }

            // One walked part of a restored leg. **A routed part is routed
            // again rather than copied**, and that is the decision this rests
            // on: the file holds a line and the network holds the edges under
            // it, and only the edges can say which dataset drew each metre,
            // whether anything calls it waymarked, and where no source records a
            // path at all. Copied, a restored plan would state 32 km of
            // recorded ground — the same loss this is fixing, better hidden.
            //
            // Where the network can no longer carry it, the recording is what is
            // left and is kept, rather than a straight line over the terrain.
            // That is said afterwards rather than swallowed.
            function restoredWalked(graph, kind, first, last, metres) {
                if (kind !== 'routed') {
                    return [trackPart(graph, first, last, undefined, undefined, undefined, undefined,
                                      kind === 'land' ? 'land' : (kind === 'paddled' && kayak() ? 'paddled' : undefined))];
                }
                // **Routed between its own two ends first, and checked against
                // the length the file states.** For a leg the reader clicked
                // that is the whole of it: the router is deterministic and the
                // weights have not moved, so it comes back to the centimetre.
                var a = graph.nearestNode(loaded.lat[first], loaded.lon[first], PLAN.matchToleranceM);
                var b = graph.nearestNode(loaded.lat[last], loaded.lon[last], PLAN.matchToleranceM);
                if (a >= 0 && b >= 0 && a !== b) {
                    var found = route(graph, a, b);
                    if (found && found.edges.length) {
                        var laid = routedParts(graph, found), run = 0;
                        laid.forEach(function (part) { run += part.length; });
                        if (agrees(run, metres)) { return laid; }
                    }
                }
                // **And where it does not agree, the part is matched rather
                // than routed.** A routed part of a *matched* route is a run of
                // spans between anchors that were merged into one, and the
                // cheapest path between its two ends is not the concatenation of
                // the cheapest paths between the anchors along it — the same
                // thing this document already records about align on a matched
                // route, at 7,266 m against 7,307. Measured here at 2,899
                // against 3,142. The anchors are not in the file, but the
                // geometry they were derived from is, so the matcher recovers
                // them from the very line it produced.
                var matched = matchedParts(graph, first, last), total = 0;
                matched.forEach(function (part) { total += part.length; });
                if (agrees(total, metres)) { return matched; }
                // Neither reproduced it, so the file's own line is what is left.
                // It is exact and it is honest, and what it costs is the edges
                // underneath — which is what `drifted` then says out loud.
                return [trackPart(graph, first, last)];
            }

            // Two lengths of one stretch, one stated by the file and one worked
            // out again. A metre, or a thousandth, whichever is the larger: the
            // file rounds what it writes and the page recomputes its distances
            // from written coordinates, so exact equality is not on offer.
            function agrees(got, said) {
                if (!isFinite(said) || said <= 0) { return false; }
                return Math.abs(got - said) <= Math.max(1, said / 1000);
            }

            // A leg laid out the way its own part list says, instead of by
            // guessing where the seams are. **The seam is inside the leg**,
            // which is why nothing before this restored one: a matched leg is
            // `routed + track + routed`, so anchorRecordedLegs — which asks
            // whether a leg is *wholly* recorded — never fires on the very legs
            // that need it. Measured, align routed 1,038 recorded metres away
            // and came back 353 m short without a word.
            //
            // Null where the file and the track do not line up, which puts the
            // leg back on the ordinary machinery rather than on a guess.
            function restoredParts(graph, from, to, wanted) {
                var parts = [], i;
                var cursor = (from.at === undefined || from.at === null) ? -1 : from.at;
                var reached = cursor >= 0 ? loaded.along[cursor] : (from.station || 0);
                for (i = 0; i < wanted.length; i += 1) {
                    var kind = wanted[i].kind, metres = wanted[i].m;
                    if (kind === 'water' || kind === CROSSING) {
                        // A crossing carries no track and advances the walk by
                        // nothing; all it left behind is the break, and its two
                        // ends are the points either side of that — except where
                        // one of them is a waypoint out on the water, which is in
                        // the <wpt> list and nowhere else.
                        var gap = cursor >= 0 ? cursor : breakAt(reached);
                        var head = cursor >= 0 ? {lon: loaded.lon[cursor], lat: loaded.lat[cursor]} : from;
                        var more = i + 1 < wanted.length;
                        var resumes = (gap >= 0 && gap + 1 < loaded.n) ? gap + 1 : -1;
                        var tail = (more && resumes >= 0)
                            ? {lon: loaded.lon[resumes], lat: loaded.lat[resumes]} : to;
                        parts.push(crossingPart(head, tail, kind));
                        if (more) {
                            if (resumes < 0) { return null; }
                            cursor = resumes;
                            reached = loaded.along[cursor];
                        }
                        continue;
                    }
                    if (cursor < 0 || !isFinite(metres)) { return null; }
                    var end = alongIndex(reached + metres, cursor);
                    if (end <= cursor) { return null; }
                    parts.push.apply(parts, restoredWalked(graph, kind, cursor, end, metres));
                    cursor = end;
                    reached = loaded.along[cursor];
                }
                return parts.length ? parts : null;
            }

            // One stretch of walked recording, in whichever way the mode asks
            // for it. Nothing at all where the stretch is a single point: a
            // <trkseg> holding one trackpoint ends where it begins, and a leg of
            // no length is a leg the height service would be asked about.
            function walkedBetween(graph, first, last) {
                if (first >= last) { return []; }
                return loaded.mode === 'match'
                    ? matchedParts(graph, first, last) : [trackPart(graph, first, last)];
            }

            // Where the waypoints of a loaded file come from, per mode.
            function pointsForLoaded(graph) {
                var made = [], wanted = [], i;
                if (restoring()) {
                    // **Where each station sits along the walk**, summed off the
                    // leg list rather than measured off the track: a crossing has
                    // a length and contributes none of it to the walking, so the
                    // two are different sums and only one of them is the axis the
                    // track carries.
                    var reached = 0, stations = [0];
                    loaded.legs.forEach(function (parts) {
                        parts.forEach(function (part) {
                            if (part.kind !== 'water' && part.kind !== CROSSING && isFinite(part.m)) {
                                reached += part.m;
                            }
                        });
                        stations.push(reached);
                    });
                    var cursor = 0;
                    for (i = 0; i < loaded.waypoints.length; i += 1) {
                        var wp = loaded.waypoints[i];
                        var at = alongIndex(stations[i], cursor);
                        cursor = at;
                        // **A station is anchored to the track only where the
                        // track is actually under it.** A waypoint set on open
                        // water is in the <wpt> list and in no <trkseg> at all,
                        // because the crossing either side of it writes nothing
                        // — so anchoring it to the nearest trackpoint would move
                        // it to the shore, which is the very point that went
                        // missing. A metre, because a waypoint is written at the
                        // position the track passes through and the two agree to
                        // seven decimals or not at all.
                        //
                        // **And where it is not, the written position stands.**
                        // It used to be snapped, which moves it up to `snapM`
                        // -- so a plan whose waypoints were not on the network
                        // came back somewhere else and was routed between the
                        // somewhere elses. Measured by the reload check the day
                        // gestures stopped snapping at 150 m: 19.1 km saved,
                        // 68.3 km restored, and nothing about the drawing looked
                        // wrong. A file says where the reader put a point; there
                        // is nothing to improve on that, and a leg from a point
                        // off the network reaches it by a connector anyway.
                        var here = panel().metresBetween(wp.lon, wp.lat, loaded.lon[at], loaded.lat[at]) <= 1.0
                            ? anchored(graph, at) : {lat: wp.lat, lon: wp.lon, node: -1};
                        here.station = stations[i];
                        // The cuts come back with the points they were made on,
                        // which is the whole reason they live on a waypoint: a
                        // tour is planned whole, walked in pieces, and read back
                        // in the pieces it was planned in.
                        if (typeof wp.stage === 'string') { here.stage = wp.stage; }
                        if (loaded.legs[i]) { here.restore = loaded.legs[i]; }
                        made.push(here);
                    }
                    // **A restored leg belongs to a pair of points, not to
                    // one.** The file's leg i runs from its point i to its
                    // point i + 1, and the description lives on the first of
                    // them -- so with nothing saying which point it ran *to*,
                    // a leg made after an edit was laid out from the file
                    // whatever its far end had become. Reported from the phone
                    // with the file: point 5 of eight taken out, and the new
                    // leg from 4 to 6 came back as the file's leg from 4 to 5,
                    // ending in the open 8 km short of its own far point --
                    // the walk shorter by exactly the leg that was dropped,
                    // and a line that stopped in the middle of nowhere.
                    for (i = 0; i + 1 < made.length; i += 1) { made[i].restoreTo = made[i + 1]; }
                    return made;
                }
                if (loaded.mode === 'align') {
                    if (loaded.waypoints.length) {
                        loaded.waypoints.forEach(function (point) {
                            var here = snapped(graph, point.lat, point.lon);
                            if (typeof point.stage === 'string') { here.stage = point.stage; }
                            made.push(here);
                        });
                    } else {
                        made.push(snapped(graph, loaded.lat[0], loaded.lon[0]));
                        made.push(snapped(graph, loaded.lat[loaded.n - 1], loaded.lon[loaded.n - 1]));
                    }
                    anchorRecordedLegs(graph, made);
                    return made;
                }
                // As it is, and matched: the recording's own ends, and both
                // sides of every break. A break is where a segment stopped, so
                // the point before it and the point after it are two stations
                // with a crossing between them.
                //
                // **Collected as indices first and never two of one point.** A
                // <trkseg> holding a single trackpoint ends where it begins, so
                // it flags two ends in a row and would put two waypoints on one
                // position — a leg of no length, an extra pin, and a request to
                // the height service about nothing.
                wanted.push(0);
                for (i = 0; i + 1 < loaded.n; i += 1) {
                    if (loaded.ends[i]) { wanted.push(i); wanted.push(i + 1); }
                }
                wanted.push(loaded.n - 1);
                wanted.forEach(function (at) {
                    if (made.length && made[made.length - 1].at === at) { return; }
                    made.push(anchored(graph, at));
                });
                return made;
            }

            // **A leg the file says was kept as recorded is restored as that**,
            // not routed. Align mode rebuilds a plan from its waypoints, and
            // for four of the five kinds that is exact — the router is
            // deterministic and the weights have not moved — but the fifth came
            // out of a file rather than out of the network, and re-routing it
            // would quietly replace it with whatever path happens to lie there.
            function anchorRecordedLegs(graph, made) {
                // **Looked up from what the file wrote, not from where the page
                // has since snapped it.** `made[i]` has already been through
                // `snapped`, which moves a waypoint up to `snapM` — 150 m — onto
                // the network, and asking which recorded point is nearest *that*
                // can land on a different pass of a switchback and move the
                // whole leg. The written position is what the writer put down.
                var written = loaded.waypoints.length ? loaded.waypoints : null;
                for (var k = 0; k + 1 < made.length && k < loaded.legs.length; k += 1) {
                    var parts = loaded.legs[k];
                    if (!parts.length) { continue; }
                    var recorded = true;
                    for (var p = 0; p < parts.length; p += 1) {
                        if (parts[p].kind !== PLAN.gpx.trackKind) { recorded = false; break; }
                    }
                    if (!recorded) { continue; }
                    [k, k + 1].forEach(function (i) {
                        var from = written && written[i] ? written[i] : made[i];
                        var found = recordedAt(from.lon, from.lat);
                        // And it may decline. A waypoint of a recorded leg was
                        // written either at the recorded point itself — exact to
                        // seven decimals, 11 cm — or at a named thing within
                        // `namedM` of it, which is the whole of how far a
                        // waypoint is ever moved from the route it belongs to.
                        // Past that the file is not describing this recording,
                        // and the leg is routed rather than anchored to a point
                        // that happens to be nearest.
                        if (found.at >= 0 && found.away <= PLAN.namedM) { made[i] = anchored(graph, found.at); }
                    });
                }
            }

            // What the file turned out to be, said before anything is done with
            // it. A chain export is recognised and *not* treated as a plan: it
            // has no waypoints to route between and no legs to rebuild, so it
            // becomes one recorded leg like any other track — recognised, named
            // after itself, and immediately something to work on, which is what
            // this phase is for. Drawing it as the chain it already is was the
            // alternative and is phase 4's job: a chain is one click away on the
            // map, and a chain id out of an older build names nothing here.
            // **It takes the file rather than reading the one in hand**, because
            // it is now said twice and the first time is before anything has
            // been taken: the offer names what the file turned out to be so the
            // mode can be chosen against it, and the status line says the same
            // afterwards. One sentence, written once, or the two would
            // eventually describe the same file differently.
            function describeFile(read) {
                var said = [];
                if (read.isRoute) {
                    said.push('a route this map wrote: ' + read.waypoints.length +
                              (read.waypoints.length === 1 ? ' waypoint' : ' waypoints') +
                              ', ' + read.legs.length + (read.legs.length === 1 ? ' leg' : ' legs'));
                } else if (read.chainId) {
                    said.push('a chain export: ' + read.name + ' (' + read.chainId + ')');
                } else {
                    said.push('a track from somewhere else: no waypoints and no legs');
                }
                said.push(read.n.toLocaleString('en-GB') + ' recorded points');
                if (read.breaks) {
                    said.push(read.breaks + (read.breaks === 1 ? ' break, which is a crossing' : ' breaks, which are crossings'));
                }
                if (read.generated) {
                    said.push(read.generated + (read.generated === 1 ? ' marker' : ' markers') + ' this map placed, skipped');
                }
                if (read.strange) {
                    said.push(read.strange + (read.strange === 1 ? ' waypoint' : ' waypoints') +
                              ' whose origin this page does not know, skipped');
                }
                // Never fatal and never silent. A part naming a kind this page
                // has no case for cannot be restored, so its leg is routed
                // between its two waypoints instead — which is a route that came
                // back different, and a reader who is not told has no way to know.
                if (read.unknown.length) {
                    said.push('a kind this page does not know (' + read.unknown.join(', ') + '), so those legs are routed instead');
                }
                return said.join(' · ');
            }

            // ---- loading ------------------------------------------------------------
            // **Reading a file and taking it are two steps now**, and the seam
            // is where the reader is asked. Everything that can refuse the file
            // happens in the first — a document that is not XML, a GPX with no
            // track — so what is on the map is still untouched while the
            // question is on the screen, and a cancelled offer costs nothing but
            // the parse.
            function readGpx(text) {
                var began = performance.now();
                var read = parseGpx(text);
                read.parseMs = performance.now() - began;
                read.began = began;
                return read;
            }

            // **The clock is restarted here and not kept from the read.** What
            // `settleMs` is worth saying about is the wait between choosing a
            // mode and a route being drawn; the seconds a reader spent looking
            // at the question are not the page's to report.
            function takeGpx(read, mode) {
                var known = false;
                MODES.forEach(function (offered) { known = known || offered.key === mode; });
                if (!known) {
                    throw new Error(mode + ' is not one of ' +
                                    MODES.map(function (offered) { return offered.key; }).join(', '));
                }
                read.began = performance.now();
                // Filled in by refresh() once every leg has settled, which is
                // the figure worth having: from the mode being chosen to a route
                // drawn on the map. It is null while that is still happening
                // rather than 0, because a load that is still working and one
                // that took no time are not the same thing.
                read.settleMs = null;
                read.mode = mode;
                loaded = read;
                applyEdit(function (graph) {
                    // The index is built here rather than inside the first leg
                    // that needs it, so that what a matched load costs is one
                    // figure and not one figure with a surprise buried in it.
                    if (mode === 'match') { edgeIndex(graph); }
                    points = pointsForLoaded(graph);
                    chosen = -1;
                });
                // Loading a file is a plan, so plan mode comes on with it: a
                // route drawn on a map that will not let it be touched is the
                // state this phase exists to avoid.
                if (!on) { switchTo(true); }
                // **A file's own title becomes the tour's**, unless it is the
                // one every unnamed file carries — adopting that would turn a
                // default into a choice the first time anything was saved again.
                var standard = panel() ? panel().routeName() : null;
                tourName = (read.name && read.name !== standard) ? read.name : '';
                fitWanted = true;
                // **What the file was goes behind the mark, not into the
                // panel.** `loadSaid` is for the short sentence a reader needs
                // now — an error, a drift warning, *back as you left it* — and
                // `loadDetail` is the description, which is five lines and is
                // wanted about once.
                loadDetail = describeFile(loaded);
                loadSaid = '';
                pendingFile = null;
                refresh();
            }

            // Reading and taking in one, which is what every check and every
            // test drives and what the picker did before the question existed.
            // Kept exactly as it was: a phase that moves an entry point moves
            // every acceptance figure taken through it.
            function loadGpx(text, mode) {
                takeGpx(readGpx(text), mode);
            }

            // **What the file said it was, against what came back.** A restored
            // plan's routed stretches are routed again rather than copied, which
            // is what brings the edges back and with them everything the route
            // says about the ground it covers -- and it means that where a
            // source has moved since the export the route is a different one.
            // Correctly different, and silently so unless something looks.
            //
            // Two figures are worth comparing and both come out of the file
            // itself: the walking it states, and the ground it says was kept as
            // recorded. The second moves on its own where a stretch the network
            // once carried can no longer be routed and the recording is what is
            // left -- which is the right answer and not one to keep quiet about.
            function drifted() {
                if (!restoring()) { return ''; }
                var walked = 0, recorded = 0, said = [];
                loaded.legs.forEach(function (parts) {
                    parts.forEach(function (part) {
                        if (!isFinite(part.m)) { return; }
                        if (part.kind === 'water' || part.kind === CROSSING || (kayak() && part.kind === 'paddled')) { return; }
                        walked += part.m;
                        if (part.kind === PLAN.gpx.trackKind) { recorded += part.m; }
                    });
                });
                var shape = composeRoute();
                if (walked && Math.abs(shape.total - walked) > 1) {
                    said.push('the network has moved under this plan: ' + Math.round(shape.total) +
                              ' m walked against the ' + Math.round(walked) + ' the file states');
                }
                if (shape.tally.recorded - recorded > 1) {
                    said.push(Math.round(shape.tally.recorded - recorded) +
                              ' m the network no longer carries, kept as recorded');
                }
                return said.length ? ' \u00b7 ' + said.join(' \u00b7 ') : '';
            }

            // ---- showing what was loaded -------------------------------------------
            // **A loaded route is somewhere else.** The map stands wherever the
            // reader left it and a file may describe ground fifty kilometres
            // away, so a load that changes nothing on the screen reads as a load
            // that did nothing. It is fitted once, when the route has settled,
            // and never again: the map is the reader's from that moment and a
            // control that moves it twice is one that fights the hand.
            //
            // Far enough in to read the route and no further. A two-hundred
            // metre route fitted to the pixel would put the reader at street
            // level with nothing around it to say where in the park they are.
            var SHOW_MAX_ZOOM = 15;

            function showRoute() {
                var shape = composeRoute();
                var bounds = L.latLngBounds([]), i;
                for (i = 0; i < shape.lon.length; i += 1) { bounds.extend([shape.lat[i], shape.lon[i]]); }
                // **And the points, which are not all in the line.** A waypoint
                // set on open water lies inside a crossing, and a crossing draws
                // nothing — so a route fitted to its drawn geometry alone would
                // put that point outside the window it is a station of.
                points.forEach(function (point) { bounds.extend([point.lat, point.lon]); });
                if (!bounds.isValid()) { return; }
                // The room the route may not be fitted into, because something
                // is standing in it: the profile panel takes the foot of the map
                // at whatever height the reader dragged it to, and the plan
                // control takes the top right. Measured rather than assumed —
                // both are the reader's to resize.
                var panelBox = document.querySelector('.trails-profile-panel');
                var planBox = document.querySelector('.trails-plan-control');
                var below = panelBox ? Math.round(panelBox.getBoundingClientRect().height) : 0;
                var beside = planBox ? Math.round(planBox.getBoundingClientRect().width) : 0;
                map.fitBounds(bounds, {
                    paddingTopLeft: [20, 20],
                    paddingBottomRight: [beside + 20, below + 20],
                    maxZoom: SHOW_MAX_ZOOM
                });
            }

            // ---- the offer ----------------------------------------------------------
            // A file is read, described, and only taken once a mode has been
            // chosen against what it turned out to be.
            function offerFile(text, name) {
                var read = readGpx(text);
                pendingFile = {read: read, name: name, kind: kindOf(read),
                               mode: READINGS[kindOf(read)].first};
                loadSaid = '';
                refresh();
            }

            // Reading a file costs a parse and nothing else, so an offer taken
            // back leaves the map exactly as it was.
            function dismissFile() {
                pendingFile = null;
                refresh();
            }

            // ---- the route's own series ---------------------------------------
            // Laid out of the parts, with the walking distance as its axis: a
            // crossing has no ground under it, advances nothing and leaves a
            // break behind — the same break the panel already draws wherever
            // nothing was read. Two walked parts meeting at a waypoint both
            // sample it, so the second copy is dropped, exactly as two edges
            // meeting at a node are.
            //
            // **The coordinates are laid here too, in the same walk.** The
            // profile is drawn from heights against distance and the file is
            // written from vertices, and composing those in two passes would be
            // two walks over one route that could disagree — each still looking
            // like a route. What comes out is the shape a chain's series has:
            // lon, lat, along, height, distance and stretches, which is what the
            // writer's runsOf and denseOf already know how to read. That the
            // geometry existed per part and was never composed is the whole
            // reason this phase is not wiring.
            //
            // **The two kinds of NaN are carried apart rather than told apart
            // afterwards.** A crossing pushes one because there is no ground
            // under it; an unread sample is one because the model had no reading
            // for ground that is there. The first has to break the track and the
            // second may only drop an <ele>, and in this series both are a NaN
            // in `height` — distinguishable, if at all, by a distance that
            // repeats. So the boundary is recorded where it happens, as a
            // stretch that ends: getting it wrong draws a line across a fjord or
            // cuts a route into dozens of pieces, and both look right on a chart.
            // **A range of the same walk, and never a slice of its figures.**
            // A stage is legs `first` up to but not including `last`, and what
            // it states about itself has to be composed rather than subtracted:
            // an ascent is not the difference of two ascents, a steepest is a
            // maximum over its own window, and a marking bucket is a sum over
            // its own edges. Given no range this is the whole route, which is
            // every call that existed before stages did.
            // **Over a list of legs and not only over the route's own.** The
            // goal's way is one leg composed by exactly this walk -- the heights
            // laid end to end, the holes left as holes, the crossings counted --
            // and a second copy of it would be a second answer to *how long is
            // this and how much does it climb*.
            function composeRoute(fromLeg, toLeg, over) {
                var walking = over || legs;
                var first = fromLeg === undefined || fromLeg === null ? 0 : fromLeg;
                var last = toLeg === undefined || toLeg === null ? walking.length : toLeg;
                var lon = [], lat = [], along = [], height = [], distance = [], free = [];
                var stretches = [], stretch = null, tally = blankTally(), gaps = [];
                var walked = 0, paddled = 0, crossings = 0, crossed = 0, straight = 0, read = false, joined = false;
                var rivers = [];
                // **Where the heights came from, carried apart from whether
                // there are any.** A routed part's are the build's DTM1 samples
                // and a straight leg's come from the same service on demand; a
                // stretch kept as it was recorded carries whatever the loaded
                // file had on its trackpoints, which this map never asked
                // anybody about. A file crediting Kartverket for a consumer GPS
                // reading, and saying it was sampled every 5 m, states two
                // things that are not so.
                var modelled = false, fromFile = false;

                function close() {
                    if (!stretch) { return; }
                    stretch.to = lon.length;
                    stretch.sampleTo = height.length;
                    stretches.push(stretch);
                    stretch = null;
                }

                // A crossing, a leg still being worked out and a leg the height
                // service refused all leave the same hole: ground the route does
                // not connect. A curve drawn through it would count a climb
                // across it and a track drawn through it would assert a way
                // across, and neither was measured. The NaN pushed here sits
                // between two stretches and inside neither, so nothing writes it
                // as a point.
                function breakHere() {
                    close();
                    if (height.length) { height.push(NaN); distance.push(walked + paddled); free.push(0); }
                    joined = false;
                }

                // **Where the reader's own points sit, in profile metres.**
                // Recorded as the walk happens and not summed from the legs
                // afterwards: a crossing contributes no walking distance and a
                // leg still being worked out contributes none either, so a sum
                // over the legs' own lengths would put every later point too far
                // along. Leg i runs from point i to point i + 1, so the distance
                // at the head of leg i is point i's, and the walk's end is the
                // last point's. Paddling has a track and advances this axis;
                // its length still belongs to water in the two totals.
                var stations = [];
                walking.slice(first, last).forEach(function (leg) {
                    stations.push(walked + paddled);
                    if (!leg.parts) { breakHere(); return; }
                    leg.parts.forEach(function (part) {
                        addTally(tally, part.tally);
                        if (part.height === null) {
                            crossings += 1;
                            crossed += part.length;
                            breakHere();
                            // **The ground under a crossing is known and only
                            // the track cannot say it.** A routed ferry carries
                            // N50's own line and a water leg the reader's two
                            // points; either way the boundary it crosses is as
                            // computable as one on land. It is dropped from the
                            // written points because GPX cannot call a segment a
                            // boat -- and `crossingsOf` used to read only those,
                            // so a route that ferried out of a reserve entered
                            // it in the file and never left. Kept apart, in
                            // order, and walked for what it passes through and
                            // for nothing else.
                            gaps.push({before: stretches.length, lon: part.lon, lat: part.lat});
                            return;
                        }
                        if (part.kind === 'land') {
                            straight += part.length;
                            if (part.rivers) { rivers = rivers.concat(part.rivers); }
                        }
                        if (!stretch) { stretch = {from: lon.length, sampleFrom: height.length}; }
                        var mark = part.kind === 'land' ? 1 : 0, at;
                        for (at = (joined ? 1 : 0); at < part.lon.length; at += 1) {
                            lon.push(part.lon[at]); lat.push(part.lat[at]); along.push(walked + paddled + part.along[at]);
                        }
                        for (at = (joined ? 1 : 0); at < part.height.length; at += 1) {
                            height.push(part.height[at]);
                            distance.push(walked + paddled + part.distance[at]);
                            free.push(mark);
                            if (!isNaN(part.height[at])) { read = true; }
                        }
                        if (part.read) {
                            if (part.kind === PLAN.gpx.trackKind) { fromFile = true; } else { modelled = true; }
                        }
                        joined = part.height.length > 0 && part.lon.length > 0;
                        if (part.kind === 'paddled') { paddled += part.length; crossed += part.length; }
                        else { walked += part.length; }
                    });
                });
                close();
                // One per point, never one per leg: with no points down there is
                // nothing to mark, and the guard is what says so. A range of one
                // leg has two stations, which is the same rule counted from the
                // other end.
                if (last > first || points.length) { stations.push(walked + paddled); }
                return {lon: lon, lat: lat, along: along, height: height, distance: distance, free: free,
                        stations: stations, gaps: gaps,
                        stretches: stretches, tally: tally, total: walked, read: read,
                        profileLength: walked + paddled, kayak: kayak(),
                        modelled: modelled, fromFile: fromFile,
                        // Filtered once, here, and read by the sentence above
                        // the button, by the file's description and by the
                        // markers the file carries. Three readings of one list,
                        // rather than three places applying one threshold.
                        protected: reportedAreas(tally),
                        crossing: crossings > 0, crossings: crossings, crossed: crossed, straight: straight,
                        rivers: rivers};
            }

            // Which protected areas the route actually passes through, in the
            // order a reader wants them: the most ground first.
            //
            // **The threshold is the decision this makes, and it is a decision
            // rather than a measurement.** Under it a route that clips the
            // corner of a boundary would report an area it never entered and
            // generate a pair of waypoints for it, metres apart, in the file
            // somebody takes into the terrain. Why it is where it is, and what
            // it is measured against, is in trails.routing.protection; it
            // arrives here rather than being spelled, so that the report the
            // build prints and the sentence this page writes cannot come to
            // disagree about what counts as passing through somewhere.
            function reportedAreas(tally) {
                var table = graphAreas(), out = [];
                Object.keys(tally.protected).forEach(function (id) {
                    var metres = tally.protected[id];
                    if (metres < PLAN.touchedM) { return; }
                    var area = table[id];
                    if (!area) { throw new Error('the route lies in ' + id + ', which the page has no entry for'); }
                    out.push({id: id, name: area.name, form: area.form, metres: metres});
                });
                return out.sort(function (a, b) { return b.metres - a.metres; });
            }

            // The areas by their own id rather than by their place in the
            // header's list, built once. The tally counts by id because an id
            // is what an edge names and what outlives the list it was read from.
            //
            // **Built once there is something to build it from, not once.** The
            // guard used to be `if (!areasById)`, and an empty lookup is an
            // object like any other: asked before the graph's own block had run
            // — which `state()` alone can do, since it composes the route
            // whether or not a point is down — it would stay empty for the life
            // of the page, and every route through an area would then throw
            // about an id the page 'has no entry for'. It is not reachable in
            // the page this builds, where `protectedAreas` is assigned in the
            // graph's block before its stream is even inflated. The count is
            // what the guard tests, rather than a flag beside the table: the
            // keys here are somebody else's register names, and a register that
            // names an area 'built' would answer about the flag.
            var areasById = null, areasFrom = -1;

            function graphAreas() {
                var table = (window.trailsGraph && window.trailsGraph.protectedAreas) || [];
                if (!areasById || areasFrom !== table.length) {
                    areasById = Object.create(null);
                    table.forEach(function (area) { areasById[area.id] = area; });
                    areasFrom = table.length;
                }
                return areasById;
            }

            // Read off the composed series by the build's own rule: a climb
            // counts once the series has turned away from its low point by the
            // threshold, and a gain smaller than that is noise the sampling
            // invented. The same rule in Python is trails.routing.elevation, and
            // two halves of one profile read under two rules would answer
            // differently without either looking wrong. Never summed off the
            // parts: the threshold restarts at every boundary, and over this
            // network summing gives two thirds of the figure.
            function climbOf(values, threshold) {
                var total = 0, at = 0;
                while (at < values.length) {
                    if (isNaN(values[at])) { at += 1; continue; }
                    var first = at;
                    while (at < values.length && !isNaN(values[at])) { at += 1; }
                    total += runClimb(values, first, at, threshold);
                }
                return total;
            }

            function runClimb(values, first, last, threshold) {
                var total = 0, anchor = values[first], extreme = values[first];
                for (var at = first + 1; at < last; at += 1) {
                    var height = values[at];
                    if (extreme >= anchor) {
                        if (height > extreme) { extreme = height; }
                        else if (extreme - height >= threshold) { total += extreme - anchor; anchor = extreme; extreme = height; }
                    } else if (height < extreme) { extreme = height; }
                    else if (height - extreme >= threshold) { anchor = extreme; extreme = height; }
                }
                // The run the series ends on is judged by the same threshold as
                // any other, or a metre of noise lands on the end of every one.
                if (extreme - anchor >= threshold) { total += extreme - anchor; }
                return total;
            }

            function figuresOf(shape) {
                var high = -Infinity, low = Infinity, upside = new Array(shape.height.length);
                for (var i = 0; i < shape.height.length; i += 1) {
                    var value = shape.height[i];
                    upside[i] = -value;
                    if (isNaN(value)) { continue; }
                    if (value > high) { high = value; }
                    if (value < low) { low = value; }
                }
                // Nothing read is not a climb of zero, the same distinction
                // the Python side keeps: a figure of zero is a statement about
                // flat ground.
                return {
                    ascent: shape.read ? climbOf(shape.height, PLAN.ascentThresholdM) : NaN,
                    descent: shape.read ? climbOf(upside, PLAN.ascentThresholdM) : NaN,
                    high: shape.read ? high : NaN,
                    low: shape.read ? low : NaN,
                    // A route has no single direction to name and no ascent that
                    // is true both ways round, so it names neither.
                    bearing: null, point: null
                };
            }

            // The two groups reported apart, never folded into the walking
            // total. A crossing is not walking and a stretch drawn straight is
            // not a path, and the reader is told both rather than shown one
            // number that quietly holds all three.
            function told(shape) {
                var said = [];
                if (shape.crossings) {
                    said.push(shape.crossings + (shape.crossings === 1 ? ' crossing, ' : ' crossings, ') +
                              (shape.crossed / 1000).toFixed(2) + ' km');
                }
                if (shape.straight > 0) {
                    said.push((shape.straight / 1000).toFixed(2) + ' km drawn straight, not a path');
                }
                // **What the straight parts wade through, by name and width.**
                // Said and not priced: whether 19 m of river can be forded is
                // depth and current, which nobody has data for. The name as N50
                // gives it, without an article -- Krutåga carries its own.
                (shape.rivers || []).forEach(function (river) {
                    said.push(riverSaid(river));
                });
                // Said wherever it is true, because the climb above it was read
                // under a different rule from every other climb on this map and
                // the figure alone cannot say so.
                if (shape.fromFile) {
                    said.push(shape.modelled ? 'part of the climb is the loaded file’s own heights, not the model'
                        : 'the climb is the loaded file’s own heights, not the model');
                }
                var outstanding = unsettled();
                if (outstanding.waiting) {
                    said.push(outstanding.waiting + (outstanding.waiting === 1 ? ' leg' : ' legs') + ' still being worked out');
                }
                if (outstanding.refused.length) {
                    said.push(outstanding.refused.length + (outstanding.refused.length === 1 ? ' leg' : ' legs') +
                              ' with no heights: ' + outstanding.refused[0].failed);
                }
                return said;
            }

            // What the route is still missing. One count, read by the sentence
            // the reader sees and by the refusal that keeps the file from being
            // written: two counts of the same thing would eventually disagree
            // about whether a route is finished.
            function riverSaid(river) {
                return 'crosses ' + (river.name || 'a river') + ', ' + Math.round(river.width) + ' m wide there';
            }

            function unsettled() {
                return {
                    // A leg carried through a live drag without its heights
                    // counts here too. Its length is real and is walked, so the
                    // distance under the reader's hand is right; its profile and
                    // what protects it are not there yet, and a file written
                    // from it would state ground nothing had been read along.
                    waiting: legs.filter(function (leg) {
                        return leg.provisional || (!leg.parts && !leg.failed);
                    }).length,
                    refused: legs.filter(function (leg) { return leg.failed; })
                };
            }

            // ---- drawing --------------------------------------------------------
            // Not the overlay pane, and not the marker pane either: what goes
            // into either is counted for ever, and both counts are acceptance
            // figures. A pane of its own also keeps the route above every trail
            // layer without depending on the order the layers were added in.
            var pane = map.createPane('trailsPlanRoute');
            pane.style.zIndex = 460;
            // **Nothing the route draws is ever a click target, and phase 7 did
            // not change that.** Clicking the route means one thing now — put a
            // waypoint into that leg — and it is decided by hit-testing the
            // geometry this page is already holding, in the one handler every
            // click goes through. An interactive line would have to be turned
            // off again the moment plan mode is, or the route would stand
            // between a reader and the trail underneath it: that is the mistake
            // the park boundary made for a fortnight, and one switch is one
            // switch too many to have to remember.
            pane.style.pointerEvents = 'none';

            // `into` is the goal's, which draws the same shapes in its own
            // colour and its own pane: the width, the casing and the dashes are
            // what say *this is a route*, and they are not the goal's to differ
            // in -- only which route it is.
            function draw(parts, waiting, into) {
                var layers = [];
                var pane = into ? into.pane : 'trailsPlanRoute';
                parts.forEach(function (part) {
                    var corners = [];
                    for (var i = 0; i < part.lon.length; i += 1) { corners.push([part.lat[i], part.lon[i]]); }
                    if (corners.length < 2) { return; }
                    var ink = into ? into.colour : ROUTE;
                    var colour = (waiting || part.kind === 'waiting') ? WAITING : ink;
                    // The casing first, so it lies under. Dashed identically, or
                    // white would show through every gap.
                    [[CASING, PLAN.routeWidth + HALO_PX * 2], [colour, PLAN.routeWidth]].forEach(function (stroke) {
                        layers.push(L.polyline(corners, {
                            pane: pane, color: stroke[0], weight: stroke[1], opacity: 0.95,
                            dashArray: DASH[part.kind], interactive: false
                        }).addTo(map));
                    });
                });
                return layers;
            }

            function undraw(layers) {
                layers.forEach(function (layer) { if (layer) { map.removeLayer(layer); } });
            }

            function straightAcross(from, to) {
                return [{kind: 'waiting', lon: [from.lon, to.lon], lat: [from.lat, to.lat]}];
            }

            // ---- the route ------------------------------------------------------
            var on = false;
            var points = [];
            var legs = [];
            var pins = [];
            var settling = 0;
            // Which waypoint the reader has hold of, as an index into points.
            // **A click on a pin selects it; it does not delete it.** The same
            // click is a few pixels away from one that places a point, there is
            // no way back from a deletion, and everything a selection makes
            // possible — take this one out, move it one place earlier or later —
            // has to be somewhere a reader can find it whatever the gesture is.
            var chosen = -1;
            // The graph once it has arrived, because a drag settles inside a
            // pointer event and cannot wait a microtask for a payload that has
            // been in the page since it loaded.
            var held = null;
            var dragging = null;

            // ---- the pins ---------------------------------------------------------
            // **A waypoint is an L.marker and no longer an L.circleMarker, and
            // that is what this phase costs in figures every review checks
            // first.** Measured before it was built: a circle marker added to
            // this map has no `dragging` at all and `draggable: true` on one is
            // silently ignored, while a marker gets a live handler. So a
            // waypoint that can be dragged is a marker — which draws no path and
            // lives in the marker pane — and a five-point route's plan pane goes
            // from 13 paths to 8 while the marker pane goes from 198 to 203.
            // `.leaflet-marker-icon` moves with them, from 0 to 5: folium
            // overwrites that class on its own markers and these are Leaflet's
            // own, so the probe that has always read 0 is reading the same fact
            // as the 203 through a second lens.
            //
            // Drawn as a div rather than an image so that its number is the
            // element's own text and selecting it is one attribute: a route
            // whose points can be reordered cannot be read without the numbers,
            // and rewriting five spans is a write nothing can feel.
            var PIN_PX = 18;

            // **A second ring where a stage changes hands**, and a ring rather
            // than a colour or a size: a pin already says two things — which
            // number it is and whether it is picked — and a third meaning has to
            // be readable beside both rather than instead of one. Drawn as a
            // shadow, so the icon keeps its size and its anchor and nothing
            // about where a click lands moves.
            function pinStyle(picked, ends) {
                return 'display:block;width:100%;height:100%;box-sizing:border-box;border-radius:50%;' +
                    'border:2px solid ' + ROUTE + ';background:' + (picked ? ROUTE : CASING) + ';' +
                    'color:' + (picked ? CASING : ROUTE) + ';text-align:center;' +
                    (ends ? 'box-shadow:0 0 0 2px ' + CASING + ',0 0 0 4px ' + ROUTE + ';' : '') +
                    'font:bold 10px/' + (PIN_PX - 4) + 'px sans-serif';
            }

            function pin(point) {
                var marker = L.marker([point.lat, point.lon], {
                    icon: L.divIcon({className: 'trails-plan-pin', iconSize: [PIN_PX, PIN_PX],
                                     iconAnchor: [PIN_PX / 2, PIN_PX / 2],
                                     html: '<span style="' + pinStyle(false) + '"></span>'}),
                    draggable: true, keyboard: false,
                    // Above every other marker on the map. Leaflet stacks
                    // markers within the pane by latitude, so a hut drawn at
                    // the same place as a waypoint covers it — measured: at the
                    // first waypoint of a route along a chain, the topmost
                    // element was folium's own `awesome-marker`, which would
                    // take the click that was meant for the pin and be read as
                    // a click on the route under it. The offset is far larger
                    // than the pixel spread of this map's markers at any zoom,
                    // because the term it is added to is a pixel position.
                    zIndexOffset: 100000
                }).addTo(map);
                marker.on('dragstart', beginDrag);
                marker.on('drag', overDrag);
                marker.on('dragend', endDrag);
                // What was last written to it, kept here rather than read back
                // off the element: a style set to '#111111' reads back as
                // 'rgb(17, 17, 17)', so an element cannot be asked whether it
                // already says what is about to be written to it.
                return {marker: marker, label: null, picked: null, ends: null, live: null};
            }

            function pinAt(marker) {
                for (var i = 0; i < pins.length; i += 1) { if (pins[i].marker === marker) { return i; } }
                return -1;
            }

            function pinFor(element) {
                for (var i = 0; i < pins.length; i += 1) {
                    if (pins[i].marker.getElement() === element) { return i; }
                }
                return -1;
            }

            // **The points belong to the route, and are drawn while the route
            // is.** Reported from the phone: after plan mode was left the
            // numbered discs stayed on the map, standing over every other line a
            // reader chose afterwards -- a route's own furniture over somebody
            // else's reading. Shown while it is being planned and while it is
            // what the panel is showing; the line itself stays either way, which
            // is what says the plan has not gone anywhere.
            //
            // The same test the row at the foot lights the route's chip by, and
            // it has to be that one: `composed` alone is true of the way to a
            // goal as well, and a goal's points are not these.
            function planShowing() {
                var said = window.trailsProfile;
                return !!(said && said.composed && !said.goal);
            }

            // Applied as differences, never rewritten wholesale. This runs on
            // every edit and, while a waypoint is being dragged, several times a
            // second — and writing a style that is already set is one of the two
            // things that have frozen this map outright.
            function dressPins() {
                var most = Math.min(pins.length, points.length);
                var shown = on || planShowing();
                for (var i = 0; i < most; i += 1) {
                    var record = pins[i], element = record.marker.getElement();
                    if (element && record.shown !== shown) {
                        element.style.display = shown ? '' : 'none';
                        record.shown = shown;
                    }
                    var label = String(i + 1), picked = i === chosen;
                    var ends = i > 0 && i + 1 < points.length && typeof points[i].stage === 'string';
                    if (element && record.label !== label) {
                        element.firstChild.textContent = label;
                        record.label = label;
                    }
                    if (element && (record.picked !== picked || record.ends !== ends)) {
                        element.firstChild.setAttribute('style', pinStyle(picked, ends));
                        record.picked = picked;
                        record.ends = ends;
                    }
                    // Out of plan mode a pin must no more stand between a reader
                    // and the line underneath than the route does, so it stops
                    // taking pointer events at all — and stops being draggable
                    // with them.
                    if (element && record.live !== on) {
                        element.style.pointerEvents = on ? 'auto' : 'none';
                        record.live = on;
                    }
                    if (record.marker.dragging) {
                        if (on) { record.marker.dragging.enable(); } else { record.marker.dragging.disable(); }
                    }
                    // The marker the pointer is holding is where the pointer put
                    // it. Writing a snapped position under it mid-drag would
                    // make it fight the hand moving it.
                    if (dragging && dragging.at === i) { continue; }
                    var where = record.marker.getLatLng();
                    if (where.lat !== points[i].lat || where.lng !== points[i].lon) {
                        record.marker.setLatLng([points[i].lat, points[i].lon]);
                    }
                }
            }

            function syncPins() {
                while (pins.length > points.length) { map.removeLayer(pins.pop().marker); }
                while (pins.length < points.length) { pins.push(pin(points[pins.length])); }
                dressPins();
            }

            // ---- stages -------------------------------------------------------------
            // **A tour is planned whole and walked in pieces.** A point can be
            // marked as the end of one, and what falls out is a run of stages
            // covering the route end to end. The first point and the last are
            // boundaries whether anybody says so, so only the ones between are
            // ever marked -- and a tour nobody has cut is one stage, which is
            // the same as no stages and is treated as none.
            //
            // **The mark lives on the point object**, which is what makes it
            // survive an edit: phase 7's model keeps a leg exactly while it runs
            // between the same two waypoint *objects*, so reordering and
            // inserting carry the mark along without a case of their own. A drag
            // is the exception and the trap -- it replaces the point with a new
            // object on purpose -- so `dragTo` copies it across, and so does
            // every other place that rebuilds a point from a position.
            //
            // `stage` is null where a point ends nothing, and a string where it
            // ends a stage: the text is the name, and empty means a stage with
            // no name of its own rather than no stage. One field for the mark
            // and the name together, because they are one decision and two
            // fields would be two ways to disagree.
            // Where the reader cut the tour, as point indices. **The ends are
            // not among them**: a tour begins and ends whether anybody says so,
            // and a pin at the finish marked as a transition would claim the
            // walk carries on past it.
            function cutsOf() {
                var out = [];
                for (var i = 1; i + 1 < points.length; i += 1) {
                    if (typeof points[i].stage === 'string') { out.push(i); }
                }
                return out;
            }

            function stagesOf() {
                if (points.length < 2) { return []; }
                var cuts = [0].concat(cutsOf());
                var i;
                cuts.push(points.length - 1);
                var out = [];
                for (i = 0; i + 1 < cuts.length; i += 1) {
                    out.push({from: cuts[i], to: cuts[i + 1], at: i,
                              name: points[cuts[i + 1]].stage || null});
                }
                return out;
            }

            // What a stage is called where nobody has named it: the two points
            // it runs between, in the numbers the list and the pins already
            // carry. Not its kilometres, which move whenever a point does.
            function stageName(stage) {
                return stage.name || (stage.from + 1) + '–' + (stage.to + 1);
            }

            // What its own file calls it: the tour and then the stage, where the
            // tour has a name, so a device listing several says which walk they
            // belong to as well as which piece of it.
            function stageTitle(stage) {
                var mine = stageName(stage);
                var whole = tourName || (panel() ? panel().routeName() : null);
                return whole ? whole + ' · ' + mine : mine;
            }

            // Marking a point, and unmarking it. The ends are not offered: a
            // tour that ends where it ends needs nobody to say so, and a mark
            // there would make a stage of no legs.
            function cutAt(at, wanted) {
                if (at < 1 || at + 1 >= points.length) { return; }
                // Remembered like any other change: it does not re-route, so it
                // never went through `applyEdit`, and an undo that stepped over
                // it would take a point away instead — which is the very defect
                // the history exists to end.
                rememberChange();
                points[at].stage = wanted ? (points[at].stage || '') : null;
                refresh();
            }

            // Naming one, which is the same field. A name on the last point is
            // allowed and marks nothing -- the tour already ends there.
            function nameStage(at, name) {
                if (at < 0 || at >= points.length) { return; }
                // **An empty box over a point that ends nothing changes
                // nothing.** Clicking into the last stage's name and out of it
                // again wrote the empty string, which is a *string* and so a
                // mark — invisible until the route grew a point past it and a
                // stage boundary nobody had asked for appeared. Measured: two
                // stages became three.
                //
                // Naming the last stage and then walking further does keep the
                // boundary, and that is a decision rather than the defect: a
                // stage somebody named ends where they said it ended, and the
                // ground added after it is the next stage.
                if (name === '' && typeof points[at].stage !== 'string') { return; }
                if (points[at].stage === name) { return; }
                // On blur, so one name is one change and not one per keystroke.
                rememberChange();
                points[at].stage = name;
                refresh();
            }

            // What only this side knows about a *stage*, in the shape the writer
            // reads for a whole tour. It is the same two lists narrowed to the
            // stage's own legs and its own points -- and the points are
            // renumbered from one, because a stage's file is a route in its own
            // right and not an extract with holes in its numbering.
            function writableRange(from, to, title) {
                return {
                    why: '',
                    // Named as the stage it is, so a device listing four tracks
                    // shows four names and not the tour four times. The file
                    // name is the tour's, which is what `stem` is for.
                    name: title,
                    stem: tourName || null,
                    // Named one at a time rather than handed to `map`, which
                    // would pass the array as a reach: see `nameOf`.
                    waypoints: points.slice(from, to + 1).map(function (point, at) {
                        return nameOf(point, at);
                    }),
                    legs: legs.slice(from, to).map(function (leg) {
                        return (leg.parts || []).map(function (part) {
                            return {kind: part.kind, length: part.length};
                        });
                    })
                };
            }

            // One stage as its own file. **Composed, never sliced**: its
            // crossings are read off its own shape, or a stage would carry an
            // `Enters` for a boundary it never reaches, in a file somebody takes
            // into the terrain.
            // Every stage on its own, and the whole tour with its cuts in it,
            // as one archive. **The tour goes in too**: the stages are what a
            // reader takes into the terrain and the tour is what they come back
            // to and edit, and an archive holding only the pieces would be a
            // set of files nothing can put together again.
            // **Never fatal and never silent.** Writing an archive is the one
            // thing here that finishes after the click that asked for it, so a
            // failure arrives as a rejected promise with nobody listening —
            // which is a button that does nothing and says nothing about it.
            function fileFailed(failure) {
                loadSaid = 'That file could not be written: ' +
                    (failure && failure.message ? failure.message : String(failure));
                refresh();
            }

            function saveStages() {
                var made = [];
                stagesOf().forEach(function (stage) {
                    var shape = composeRoute(stage.from, stage.to);
                    var figure = figuresOf(shape), extra = told(shape);
                    var plan = writableRange(stage.from, stage.to, stageTitle(stage)), suffix = stageName(stage);
                    made.push(panel().routeFile(figure, shape, extra, plan, suffix));
                    made.push(panel().garminFile(figure, shape, extra, plan, suffix));
                });
                var whole = composeRoute(), figure = figuresOf(whole), extra = told(whole), plan = writable();
                made.push(panel().routeFile(figure, whole, extra, plan));
                made.push(panel().garminFile(figure, whole, extra, plan));
                return panel().saveZip(made, plan).catch(fileFailed);
            }

            // Both files use the same composer, for a whole tour or a stage.
            function saveWhole(garmin) {
                var shape = composeRoute();
                var writer = garmin ? panel().garminFile : panel().routeFile;
                var made = writer(figuresOf(shape), shape, told(shape), writable());
                panel().save(made.name, made.text);
            }

            function saveStage(stage, garmin) {
                var shape = composeRoute(stage.from, stage.to);
                var writer = garmin ? panel().garminFile : panel().routeFile;
                var made = writer(figuresOf(shape), shape, told(shape),
                                  writableRange(stage.from, stage.to, stageTitle(stage)), stageName(stage));
                panel().save(made.name, made.text);
            }

            // ---- the legs ---------------------------------------------------------
            function newLeg(graph, from, to, mayAsk) {
                var leg = {from: from, to: to, parts: null, failed: null, provisional: false, layers: []};
                // Something on the map the instant the gesture lands, replaced
                // when the leg is worked out. **Only this leg is drawn**, then
                // and later: rebuilding the whole route on every change is what
                // froze this map twice already, on a layer rather than on a
                // route, and a drag would do it eight times a second.
                leg.layers = draw(straightAcross(from, to));
                settling += 1;
                // Wrapped, so that a fault thrown on the way *into* the work
                // is a rejection like any other rather than an exception that
                // leaves the count of outstanding legs standing for ever.
                // **The connector layer, and only when the pointer is up.**
                // A waypoint that did not snap is no longer a leg drawn
                // straight and nothing else: it reaches the network the way a
                // goal does, by a short walk to it. Under a live drag it is
                // not, and for the reason the height service is not either --
                // the search is 64 ms on a long leg, a drag settles every
                // `DRAG_EVERY_MS` with two legs to redo, and the two together
                // are a route that cannot keep up with the finger holding it.
                // What the reader sees while dragging is the leg at its own
                // straight length, saying it is still being worked out; the
                // search runs once, when the finger lifts.
                Promise.resolve().then(function () { return resolve(graph, from, to, mayAsk, mayAsk); }).then(function (parts) {
                    leg.parts = parts;
                    leg.provisional = parts.some(function (part) { return part.provisional; });
                }, function (failure) {
                    leg.failed = String(failure && failure.message ? failure.message : failure);
                // A third handler rather than a catch over the two above: a
                // fault while *drawing* is not a leg that could not be worked
                // out, and reporting it as one sends the next reader to the
                // wrong place. It belongs in the console, loudly.
                }).then(function () {
                    settling -= 1;
                    // **This one line is the whole of the cancellation.** Every
                    // edit that changes what a leg runs between replaces it with
                    // a new object, so a reply about ground a waypoint has since
                    // left arrives here and finds itself off the route — and no
                    // leg is ever drawn from an answer that is no longer wanted.
                    // A drag settling eight times a second leans on it hardest.
                    if (legs.indexOf(leg) < 0) { return; }
                    undraw(leg.layers);
                    leg.layers = draw(leg.parts || straightAcross(from, to), leg.provisional);
                    refresh();
                });
                return leg;
            }

            // **The legs follow from the waypoints rather than being edited
            // beside them.** Insert, remove, reorder and drag each rewrite the
            // list of points and nothing else; a leg survives exactly when it
            // still runs between the same two waypoints it already ran between,
            // and what an edit costs falls out of that — two legs for an insert,
            // one for a removal, the three that touch a point for a move.
            // Nothing here has to work out which legs an edit invalidated, which
            // is the arithmetic all four of them would otherwise get wrong in
            // four different ways.
            //
            // A waypoint that has moved is a *new* object rather than a mutated
            // one, so a drag needs no case of its own: the legs beside it stop
            // matching and are rebuilt, and everything beyond them is untouched.
            function relink(graph, mayAsk) {
                var kept = legs, i, k;
                legs = [];
                for (i = 0; i + 1 < points.length; i += 1) { legs.push(null); }
                for (i = 0; i < legs.length; i += 1) {
                    for (k = 0; k < kept.length; k += 1) {
                        if (kept[k] && kept[k].from === points[i] && kept[k].to === points[i + 1]) {
                            legs[i] = kept[k]; kept[k] = null; break;
                        }
                    }
                }
                kept.forEach(function (leg) { if (leg) { undraw(leg.layers); } });
                for (i = 0; i < legs.length; i += 1) {
                    if (!legs[i]) { legs[i] = newLeg(graph, points[i], points[i + 1], mayAsk); }
                }
            }

            function withGraph(run, always) {
                if (!window.trailsGraph) {
                    say('There is no routing graph in this page, so nothing can be routed.');
                    always();
                    return;
                }
                // Two handlers rather than a catch, for the reason above. The
                // release is a finally rather than a line after the call: the
                // work must be counted as over whether it succeeded or threw,
                // and a throw still reaches the console, loudly.
                window.trailsGraph.ready.then(function (graph) {
                    held = graph;
                    try { run(graph); } finally { always(); }
                }, function () {
                    say('The routing graph did not arrive, so nothing can be routed.');
                    always();
                });
            }

            // ---- the five edits ---------------------------------------------------
            // Every one of them runs through here. The graph is what turns a
            // position into a waypoint and a pair of waypoints into a leg, and a
            // route half-edited while it arrives would be a second state to keep
            // in step with this one.
            // **A history, because "the last point" stopped being "the last
            // thing you did" the moment inserting existed.** Until phase 7 every
            // edit was an append and `points.pop()` *was* an undo; phase 7 added
            // inserting, removing, reordering and dragging, and this was never
            // revisited. Reported by a reader and reproduced: on a six-point
            // route, a point placed between 5 and 6 becomes point 6 — and taking
            // back "the last point" removed point **7**, which is the one that
            // had been 6. The button did the opposite of undoing.
            //
            // A snapshot is the plan and nothing derived from it: the legs are
            // rebuilt from the points, which is what `applyEdit` does anyway.
            // **The point objects are kept rather than copied**, because a leg
            // survives exactly while it runs between the same two waypoint
            // objects — copying them would re-route the whole route on every
            // undo. Their `stage` is copied beside them, because that one is
            // written in place.
            var HISTORY_MAX = 50;
            var history = [];

            // **Named apart from the height cache's `remember`, which had the
            // name first and is in this same scope.** Two function declarations
            // of one name in one scope is not a shadow, it is a replacement: the
            // later one wins outright, so calling this `remember` silently
            // stopped the freehand-leg height cache from caching and made every
            // arriving answer push a history entry instead. Found because an
            // undo restored a state that already held the point just placed.
            function rememberChange() {
                history.push({
                    points: points.map(function (point) { return {point: point, stage: point.stage}; }),
                    tourName: tourName,
                    loaded: loaded
                });
                if (history.length > HISTORY_MAX) { history.shift(); }
            }

            function applyEdit(change, remembering) {
                if (remembering !== false) { rememberChange(); }
                // Counted as outstanding from the gesture, not from the moment
                // the graph answers. A reader who has clicked is waiting, and a
                // state that reads 'nothing in hand' for the microtask in
                // between is one a check would believe.
                settling += 1;
                refresh();
                withGraph(function (graph) {
                    change(graph);
                    relink(graph, true);
                    syncPins();
                }, function () { settling -= 1; refresh(); });
            }

            // Snapped to the network where there is any within reach, so a route
            // can start from where the reader meant rather than from a metre
            // beside it; beyond that the raw point stands, and the leg reaches
            // the network by a connector instead of being moved on to it.
            //
            // **The reach is handed in, because two callers mean different
            // things by it.** A finger over the map means *the line I am
            // touching*, which is a question about the screen; a waypoint read
            // out of a file means *was this recorded on the network*, which is
            // a question about the ground and must answer the same whatever the
            // map happens to be showing. A single reach served both only for as
            // long as nobody asked what it was for.
            //
            // **On to the line, and not only on to its junctions.** A node is
            // where edges meet or a chain ends, and a tap in the middle of a
            // long stretch found none within reach and stood as open ground
            // (`nearestOnNetwork` has the figures). The line itself is asked
            // as well, and the point put on it remembers which edge and how
            // far along, which is what lets the router start from there. A
            // junction within reach is taken over the line beside it when it
            // is as near, give or take `NODE_FIRST_M`: at a junction the line
            // *is* the node, and a tap meant for a junction is meant for it.
            var NODE_FIRST_M = 2;

            function snapped(graph, lat, lon, within) {
                var reach = within === undefined ? PLAN.snapM : within;
                var node = graph.nearestNode(lat, lon, reach);
                // The nearest node may belong only to water and its portage
                // ties. Skipping water edges alone would still snap to it.
                if (node >= 0 && !router(graph).snapNodes[node]) {
                    var eligible = router(graph).snapNodes, nearest = reach;
                    node = -1;
                    for (var n = 0; n < graph.header.nodes; n += 1) {
                        if (!eligible[n]) { continue; }
                        var away = panel().metresBetween(lon, lat, graph.nodeLon[n], graph.nodeLat[n]);
                        if (away < nearest) { nearest = away; node = n; }
                    }
                }
                var line = nearestOnNetwork(graph, lat, lon, reach);
                if (node >= 0) {
                    var nodeM = panel().metresBetween(lon, lat, graph.nodeLon[node], graph.nodeLat[node]);
                    if (!line || nodeM <= line.m + NODE_FIRST_M) {
                        return {lat: graph.nodeLat[node], lon: graph.nodeLon[node], node: node};
                    }
                }
                if (line) { return {lat: line.lat, lon: line.lon, node: -1, edge: line.edge, along: line.along}; }
                return {lat: lat, lon: lon, node: -1};
            }

            // **A tap means the line it lands on, and landing on it is
            // something that happens on a screen.** At a fixed 150 m the same
            // tap meant the same thing at every zoom: pinched right in, with
            // two paths drawn a finger apart, a point put down on one of them
            // could be taken as the other -- and the further out the reader
            // was, the more nearly right the figure became. A finger's width
            // is the reach every other line on this page is hit by, and it is
            // the one that moves with the view:
            //
            //     z12  191 m -> held at 150     z15   24 m
            //     z13   96 m                    z16   12 m
            //     z14   48 m                    z17    6 m
            //
            // Capped at `snapM`, because zoomed far enough out a finger covers
            // a valley and *the line I am touching* stops meaning anything.
            function fingerReach(lat) {
                var across = PLAN.snapPx * 40075016.686 * Math.cos(lat * Math.PI / 180) /
                    Math.pow(2, map.getZoom() + 8);
                return Math.min(PLAN.snapM, across);
            }

            // **The same question about a named thing, and it narrows only.**
            // A tap is taken as the hut it lands on, and at a fixed `namedM` it
            // was taken as one from 50 m away however far in the reader had
            // pinched -- so a goal deliberately set beside a hut became the hut,
            // and there was no zoom at which it did not. Held at `namedM`
            // rather than at `snapM` where a finger is the wider of the two:
            // that figure is the build's judgement about *naming*, not about
            // pointing, and a waypoint called after something 150 m away would
            // disagree with every other name on this map.
            function namedReach(lat) {
                return Math.min(PLAN.namedM, fingerReach(lat));
            }

            //: The reach that pulls a point nowhere and still recognises the
            //: node it is already standing on. Zero will not do: `nearestNode`
            //: takes its limit strictly, so a point sitting *exactly* on a node
            //: -- which is what a tap that snapped leaves behind -- would be
            //: refused that node and treated as open ground.
            var SAME_SPOT_M = 1;

            // **`exact` is a caller saying it is not a finger.** A tap is taken
            // as the line it lands on, which is what `fingerReach` is for; a
            // place pressed on a page is where that place is -- a hut, or the
            // five decimals somebody typed -- and pulling it twenty metres on to
            // the nearest path would be this page guessing at something that was
            // already said exactly.
            function place(lat, lon, exact) {
                // **The mode is left as it is found.** A place's page offers
                // this while the plan's mode is off -- that is the only time a
                // place can be selected at all, since with the mode on every
                // tap is a waypoint -- and switching the mode on here would
                // take the next place away again. A loaded file brings the
                // mode on; a place added to a standing plan does not.
                applyEdit(function (graph) {
                    points.push(snapped(graph, lat, lon, exact ? SAME_SPOT_M : fingerReach(lat)));
                    chosen = points.length - 1;
                });
            }

            // **A way somebody has already laid out, handed to the plan.** A
            // goal answers *how do I get there from where I am*; a plan answers
            // *what shall the walk be* -- and the places are the same places, so
            // between the two halves of this page there was one thing missing:
            // the way from the first to the second. The goal's stops become the
            // plan's points, in the order they were to be walked.
            //
            // **Not snapped.** Every one of them was put where it is already --
            // by a tap that snapped it to the line under the finger, or by a
            // coordinate typed exactly -- and snapping a second time, at
            // whatever zoom happens to be showing, would move what the reader
            // placed. `0` and not `fingerReach`, for that reason and no other.
            //
            // **And this is not a loaded file**, so everything a file left
            // behind goes with the points it described: a route that came from
            // a goal has no recording in it and no name of its own.
            function planFromPlaces(places) {
                if (!places || !places.length) { return 0; }
                applyEdit(function (graph) {
                    points = places.map(function (each) { return snapped(graph, each.lat, each.lon, SAME_SPOT_M); });
                    chosen = -1;
                });
                loaded = null;
                tourName = '';
                loadDetail = '';
                loadSaid = '';
                pendingFile = null;
                // Plan mode comes on with it, for the reason a loaded file
                // brings it on: a route drawn on a map that will not let it be
                // touched is the state this is the way out of.
                if (!on) { switchTo(true); }
                fitWanted = true;
                refresh();
                return places.length;
            }

            // **Everywhere the journey goes, in the order it is walked**, with
            // the reader's own position in front of it where the page knows it:
            // the way being looked at starts there, and a plan that began at the
            // first stop would be a different walk.
            //
            // **And the goal goes, because it has become the plan.** Two routes
            // over the same places, one of them editable and one of them not, is
            // a page that cannot say which is being walked.
            //
            // Here rather than in the panel that offers it, because both halves
            // of it are here -- the goal and the plan share this closure -- and
            // because it is offered from two places: the goal's own page, and
            // the page the flag opens where there is no way to show.
            function planFromGoal() {
                var said = goalState();
                var places = (said.stops || []).map(function (stop) {
                    return {lat: stop.lat, lon: stop.lon};
                });
                if (!places.length) { return false; }
                var here = goalHere();
                if (here) { places.unshift({lat: here.lat, lon: here.lon}); }
                // **Asked only where there is something to lose.** A plan with
                // points in it is somebody's work; an empty one is not, and a
                // question about nothing teaches people to press through
                // questions.
                if (points.length && !window.confirm('Replace the ' + points.length +
                        (points.length === 1 ? ' point' : ' points') + ' of the plan with the ' +
                        places.length + ' places of this way?')) { return false; }
                planFromPlaces(places);
                clearGoal();
                return true;
            }

            // **Inserting is this phase's own addition and not one of the
            // numbered requirements**, which say only that waypoints can be
            // reordered and removed. Without it a route can be corrected only
            // from the end, which is how a fifteen-point plan gets thrown away
            // over a mistake at point three.
            //
            // **The index is checked inside the edit and not before it.** An
            // edit runs when the graph answers, which is a microtask later, so
            // two asked for in one turn would both be checked against the route
            // as it was before either — and the second would splice against a
            // list that had already moved under it.
            // ``trackAt`` is which point of the loaded recording the click
            // landed on, where it landed on a stretch kept as recorded. Passed
            // through rather than worked out again here: **without it a point
            // put into the middle of a recorded leg would split it into two legs
            // that are no longer the recording**, and the whole track would be
            // replaced by a routed line the moment a reader corrected one point
            // of it. With it both halves stay what they were.
            function insert(at, lat, lon, trackAt) {
                applyEdit(function (graph) {
                    if (at < 1 || at > points.length - 1) { return; }
                    points.splice(at, 0, trackAt === undefined || trackAt === null || !loaded
                        ? snapped(graph, lat, lon, fingerReach(lat)) : anchored(graph, trackAt));
                    chosen = at;
                });
            }

            // And removing merges the two legs that met at the point, which
            // falls out of the rule above rather than being arranged here.
            function remove(at) {
                applyEdit(function () {
                    if (at < 0 || at >= points.length) { return; }
                    points.splice(at, 1);
                    chosen = -1;
                });
            }

            // Reordering, one place at a time. The requirement is that the
            // points can be reordered and the route follows; a point moved past
            // its neighbour is the smallest gesture that does that, it composes
            // into any order at all, and it needs no second way of pointing at a
            // waypoint — the reader is already holding one.
            function moveBy(at, step) {
                applyEdit(function () {
                    var to = at + step;
                    if (at < 0 || at >= points.length || to < 0 || to >= points.length) { return; }
                    var moved = points[at];
                    points[at] = points[to];
                    points[to] = moved;
                    chosen = to;
                });
            }

            // **And to any place at all, which a list can ask for and a pin
            // cannot.** A splice rather than a run of swaps: a swap is a full
            // re-route of the two legs it touches, so dragging a point four
            // places up a list would route eight legs to arrive at the two that
            // actually changed. It is also a different gesture's meaning —
            // dropping a row between two others takes it out and puts it back
            // in, where a run of swaps would drag every point it passed one
            // place the other way.
            function moveTo(at, to) {
                applyEdit(function () {
                    if (at < 0 || at >= points.length || to < 0 || to >= points.length || at === to) { return; }
                    points.splice(to, 0, points.splice(at, 1)[0]);
                    chosen = to;
                });
            }

            // One misclick should not cost a route, and taking the last point
            // back is the gesture a reader reaches for before they know the rest
            // of these are there.
            function undo() {
                if (!history.length) { return; }
                var was = history.pop();
                applyEdit(function () {
                    // The array is emptied and refilled rather than replaced:
                    // a load reassigns `points`, so anything holding the old one
                    // is already stale, and this way nothing else has to know.
                    points.length = 0;
                    was.points.forEach(function (each) {
                        if (each.stage === undefined) { delete each.point.stage; }
                        else { each.point.stage = each.stage; }
                        points.push(each.point);
                    });
                    if (chosen >= points.length) { chosen = points.length - 1; }
                }, false);
                tourName = was.tourName;
                loaded = was.loaded;
            }

            // ---- dragging ---------------------------------------------------------
            // **Throttled, because a drag is not a click.** Placing a point
            // costs 19-76 ms including its Dijkstra and composing the whole
            // route another 3, so the two legs a dragged waypoint moves are 40
            // to 160 ms of work; run at the rate a pointer reports its position
            // that is three of them queued per frame and a map that has stopped
            // answering. Every 120 ms it is six or eight settles a second, which
            // is the route following the hand. There was no throttle and no
            // cancellation anywhere in plan mode before this: the only
            // setTimeout near it belonged to the search box.
            var DRAG_EVERY_MS = 120;

            function beginDrag(event) {
                var at = pinAt(event.target);
                if (at < 0) { return; }
                dragging = {at: at, ran: 0, timer: null};
                chosen = at;
                refresh();
            }

            function overDrag(event) {
                if (!dragging || !held) { return; }
                var now = performance.now();
                var due = dragging.ran + DRAG_EVERY_MS - now;
                if (due > 0) {
                    // The trailing settle, so the position the pointer came to
                    // rest at is worked out even if it stops between two ticks.
                    if (dragging.timer === null) {
                        dragging.timer = setTimeout(function () {
                            dragging.timer = null;
                            overDrag(event);
                        }, due);
                    }
                    return;
                }
                dragging.ran = now;
                // The index was taken when the pointer went down and the array
                // is not shortened under a live drag, but a waypoint written
                // past the end of the list would be a route with a hole in it
                // that nothing raised about.
                if (dragging.at >= points.length) { return; }
                var where = event.target.getLatLng();
                points[dragging.at] = snapped(held, where.lat, where.lng, fingerReach(where.lat));
                // Nothing may be asked of the height service while the pointer
                // is down: see `resolve`.
                relink(held, false);
                refresh();
            }

            function endDrag(event) {
                if (!dragging) { return; }
                if (dragging.timer !== null) { clearTimeout(dragging.timer); dragging.timer = null; }
                var at = dragging.at, where = event.target.getLatLng();
                dragging = null;
                // The same path every other edit takes, which is what makes a
                // drag that began before the payload arrived say so rather than
                // leave a pin somewhere its waypoint is not.
                applyEdit(function (graph) {
                    if (at >= points.length) { return; }
                    points[at] = snapped(graph, where.lat, where.lng, fingerReach(where.lat));
                });
            }

            // ---- where a click lands ----------------------------------------------
            // How near a click has to fall to the drawn route to be taken as a
            // point going into it rather than one going on the end. Read as
            // pixels and turned into metres at the zoom the reader is looking
            // at, so it means near the line *as drawn* wherever the map is.
            var ON_ROUTE_PX = 8;

            // The distance from a position to a segment, and the point on that
            // segment nearest to it. Flat and local: a degree of latitude is
            // 111,320 m and a degree of longitude that times the cosine, which
            // is the approximation nearestNode is already written with and is
            // exact to well under a metre over the tens of metres this is ever
            // asked about.
            function nearSegment(lat, lon, cosine, aLat, aLon, bLat, bLon) {
                var ax = (aLon - lon) * cosine, ay = aLat - lat;
                var bx = (bLon - lon) * cosine, by = bLat - lat;
                var dx = bx - ax, dy = by - ay, span = dx * dx + dy * dy;
                var t = span > 0 ? -(ax * dx + ay * dy) / span : 0;
                t = t < 0 ? 0 : (t > 1 ? 1 : t);
                var cx = ax + t * dx, cy = ay + t * dy;
                return {away: Math.sqrt(cx * cx + cy * cy) * 111320,
                        lat: aLat + t * (bLat - aLat), lon: aLon + t * (bLon - aLon)};
            }

            // Which leg a click landed on, and where along it — or nothing.
            // Every vertex of the route is walked, which is thousands of them
            // over a long one and a millisecond or two against the 19 to 76 a
            // click already costs. A leg still being worked out is hit-tested
            // as the straight line it is drawn as, so a point can be put into
            // one before it settles.
            function onRoute(lat, lon, withinPx) {
                var cosine = Math.cos(lat * Math.PI / 180);
                // **Two reaches, because two questions.** Putting a point into a
                // leg is aiming at a line and takes the tighter one; asking
                // whether a tap *meant* the route is the same question the panel
                // asks of every other line under the finger, and it has to be
                // asked at the same distance or the route would be the one
                // candidate a reader had to hit twice as accurately.
                var reach = withinPx || ON_ROUTE_PX;
                var withinM = reach * 40075016.686 * cosine / Math.pow(2, map.getZoom() + 8);
                var best = null;
                for (var i = 0; i < legs.length; i += 1) {
                    var parts = legs[i].parts || straightAcross(legs[i].from, legs[i].to);
                    for (var p = 0; p < parts.length; p += 1) {
                        var part = parts[p];
                        for (var v = 0; v + 1 < part.lon.length; v += 1) {
                            var near = nearSegment(lat, lon, cosine, part.lat[v], part.lon[v],
                                                   part.lat[v + 1], part.lon[v + 1]);
                            if (near.away > withinM) { continue; }
                            if (best && near.away >= best.away) { continue; }
                            best = {leg: i, away: near.away, lat: near.lat, lon: near.lon, trackAt: null};
                            // Which point of the loaded recording the click
                            // landed on, where the part came out of one. The
                            // nearer of the segment's two ends rather than the
                            // position between them: a recorded point is
                            // something that was measured, and half way between
                            // two of them is not — and a waypoint standing
                            // where nothing was recorded cannot anchor the two
                            // halves of a stretch that has to stay recorded.
                            if (part.index) {
                                var onward = panel().metresBetween(near.lon, near.lat, part.lon[v], part.lat[v]);
                                var back = panel().metresBetween(near.lon, near.lat, part.lon[v + 1], part.lat[v + 1]);
                                best.trackAt = part.index.from + part.index.step * (onward <= back ? v : v + 1);
                            }
                        }
                    }
                }
                return best;
            }

            // **Every segment of the route, handed out rather than copied.**
            // `geometry()` hands the whole shape back as two arrays and
            // `state()` composes the route to answer anything at all -- 45 ms
            // over a 37 km one. A mark that is worked out on every fix can
            // afford neither, and it does not want the shape: it wants to
            // measure one point against every segment and keep three numbers.
            //
            // The legs are walked exactly as `onRoute` walks them, one leg at a
            // time and in order, and every segment says which leg it came from
            // -- which is what lets a caller ask for *the next waypoint ahead*
            // without knowing anything else about how a route is put together.
            // **Every segment of a list of legs, leg by leg, in the order they
            // are walked** -- with the leg's index, because which leg a segment
            // belongs to is what says which place lies at the end of it, and the
            // composed shape has that boundary nowhere in it.
            //
            // One walker and two callers. The plan and the goal kept a copy each
            // of this triple loop, differing in one expression: what a leg still
            // being worked out counts as. `over` is that expression.
            function segmentsOf(list, over, visit) {
                for (var i = 0; i < list.length; i += 1) {
                    var parts = list[i].parts || over(list[i]);
                    for (var p = 0; p < parts.length; p += 1) {
                        var part = parts[p];
                        for (var v = 0; v + 1 < part.lon.length; v += 1) {
                            visit(part.lat[v], part.lon[v], part.lat[v + 1], part.lon[v + 1], i);
                        }
                    }
                }
            }

            //: A leg of the plan that has not settled is walked as the straight
            //: line it is drawn as, so a point can be put into one before it is
            //: worked out.
            function eachSegment(visit) {
                segmentsOf(legs, function (leg) { return straightAcross(leg.from, leg.to); }, visit);
            }

            // The place at one end of a leg. **Every waypoint is a goal**, and
            // that is not a rule about waypoints but about this route: the
            // bends between them belong to the router, so the points are
            // exactly the places the reader chose to walk by. The ones standing
            // beside something this map already names take that name; the rest
            // are numbered, which is what the list beside them does too.
            function placeAt(leg, forward) {
                var at = forward > 0 ? leg + 1 : leg;
                if (at < 0 || at >= points.length) { return null; }
                var said = nameOf(points[at], at);
                return {lat: points[at].lat, lon: points[at].lon,
                        name: said.name || ('Waypoint ' + said.number)};
            }

            // What a waypoint is called, and where the file puts it. Where the
            // map already draws something named within reach — a hut, a quay, a
            // trailhead, a farm — the waypoint takes that thing's name, what it
            // is and **its position**, while the route itself stays on the
            // network: the file's track runs where a walker can walk and its
            // marker sits on the hut.
            //
            // Nearest wins rather than first, so two registers naming the same
            // hut a few metres apart cannot make the answer depend on the order
            // the layers were added in. Beyond reach the point keeps its own
            // position and is numbered, which is what it did before this
            // existed.
            // **The reach is handed in for the reason `snapped`'s is.** Asked
            // of a finger on the map it is a question about what the reader
            // could have been pointing at; asked of a waypoint already down --
            // to fill the list, or to name the place a leg ends at for the mark
            // -- it is a question about the ground, and one that has to answer
            // the same whatever the map happens to be showing. A name that
            // changed with the zoom would put a different word in the list every
            // time the reader pinched, and a different one again in the file.
            //
            // **A number or nothing, and `undefined` is not the test.** This
            // function is handed to `Array.prototype.map` in two places, which
            // calls it with three arguments -- the value, the index and *the
            // array*. So the day a third parameter was added, every waypoint in
            // every file was named after the nearest thing at any distance
            // whatever: `closest > []` coerces to `closest > NaN`, which is
            // false, so the reach stopped rejecting anything. Measured in the
            // file it wrote: a waypoint called *Steinbua, Tosenfjellet* 2,419 m
            // away and one called *Gamme* 9,196 m away. The call sites are named
            // properly below; this is the belt.
            function nameOf(point, index, within) {
                var reach = typeof within === 'number' ? within : PLAN.namedM;
                var best = null, closest = Infinity;
                for (var i = 0; i < NAMED.length; i += 1) {
                    var away = panel().metresBetween(point.lon, point.lat, NAMED[i].lon, NAMED[i].lat);
                    if (away < closest) { closest = away; best = NAMED[i]; }
                }
                // The stage mark rides along, because the writer is handed
                // this and not the point: a cut the reader made would otherwise
                // be in the plan and in no file it writes.
                var cut = typeof point.stage === 'string' ? point.stage : null;
                if (!best || closest > reach) {
                    return {lat: point.lat, lon: point.lon, name: null, kind: null,
                            away: null, number: index + 1, stage: cut};
                }
                return {lat: best.lat, lon: best.lon, name: best.name, kind: best.type,
                        away: closest, number: index + 1, stage: cut};
            }

            // ---- the control ------------------------------------------------------
            // **The panel spoke in words where the rest of the page uses
            // marks.** Measured on a seven-point route: 234 px of a 471 px panel
            // gone before the first waypoint, twelve buttons carrying words —
            // *Undo the last change* is twenty characters — and 468 characters
            // of text above a list. One word is kept, the one that ends the
            // work; the rest are tools and get a mark, with a title and an
            // `aria-label`, exactly as the rail beside them does.
            var PLAN_ICONS = {
                undo: '<path d="M4 8.5h7.2a3.3 3.3 0 0 1 0 6.6H7"/><path d="M6.8 5.3 3.6 8.5l3.2 3.2"/>',
                again: '<path d="M14.6 7.4A6 6 0 1 0 15 11"/><path d="M15.4 3.6v3.9h-3.9"/>',
                load: '<path d="M9 12.4V3.2"/><path d="M5.6 6.6 9 3.2l3.4 3.4"/><path d="M3.4 11.6v2.6a1 1 0 0 0 1 1h9.2a1 1 0 0 0 1-1v-2.6"/>',
                save: '<path d="M9 3.2v9.2"/><path d="M5.6 9 9 12.4 12.4 9"/><path d="M3.4 11.6v2.6a1 1 0 0 0 1 1h9.2a1 1 0 0 0 1-1v-2.6"/>'
            };
            function planIcon(name) {
                return '<svg width="17" height="17" viewBox="0 0 18 18" fill="none" stroke="currentColor" ' +
                    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
                    PLAN_ICONS[name] + '</svg>';
            }
            var TOOL_STYLE = 'flex:none;width:34px;height:34px;display:flex;align-items:center;' +
                'justify-content:center;border:1px solid var(--trails-rule);border-radius:7px;' +
                'background:var(--trails-solid);color:var(--trails-ink-3);cursor:pointer;padding:0';
            function asTool(button, name, explains) {
                button.innerHTML = planIcon(name);
                button.title = explains;
                button.setAttribute('aria-label', explains);
                button.style.cssText = TOOL_STYLE;
                return button;
            }

            var toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'trails-plan-toggle';
            toggle.style.cssText = 'flex:none;height:34px;padding:0 14px;border-radius:7px;' +
                'border:1px solid var(--trails-strong);background:var(--trails-strong);' +
                'color:var(--trails-on-strong);font:inherit;font-size:12.5px;font-weight:600;cursor:pointer';
            var back = document.createElement('button');
            back.type = 'button';
            asTool(back, 'undo', 'Undo the last change');
            // **The way out of a plan that comes back on its own.** A kept plan
            // is restored on every load until there is nothing to restore, and
            // emptying a twenty-point route one point at a time is not a way
            // out. It goes through the same edit funnel as everything else, so
            // undo brings it back — which is what makes a button that clears the
            // map safe to offer.
            var fresh = document.createElement('button');
            fresh.type = 'button';
            fresh.className = 'trails-plan-fresh';
            asTool(fresh, 'again', 'Start again — take every point off the map');
            var status = document.createElement('div');
            status.style.cssText = 'margin-top:6px;color:var(--trails-ink-2);font-size:13px;' +
                'display:flex;align-items:center;gap:8px';
            var statusText = document.createElement('span');
            statusText.style.cssText = 'flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;' +
                'white-space:nowrap;font-variant-numeric:tabular-nums';
            // **What the last file turned out to be, behind a mark.** It stood in
            // the panel as five lines of prose above the buttons: *a route this
            // map wrote: 7 waypoints, 6 legs · 23,379 recorded points · 1 break,
            // which is a crossing · 4 markers this map placed, skipped*. True,
            // occasionally wanted, and never worth five lines of a panel that is
            // trying to show a route.
            var about = document.createElement('button');
            about.type = 'button';
            about.className = 'trails-plan-about';
            about.textContent = 'ⓘ';
            about.title = 'What this route is, and what the last file turned out to be';
            about.setAttribute('aria-label', 'What this route is');
            about.style.cssText = 'flex:none;font:inherit;font-size:14px;line-height:1;padding:0 4px;' +
                'border:0;background:none;color:var(--trails-accent);cursor:pointer;display:none';
            about.addEventListener('click', function (event) {
                event.stopPropagation();
                if (!window.trailsChrome || !window.trailsChrome.detail) { return; }
                var standing = window.trailsChrome.state();
                if (standing.detail && standing.detailKey === 'plan') {
                    window.trailsChrome.closeDetail();
                    return;
                }
                var told = document.createElement('div');
                told.style.cssText = 'font-size:13px;line-height:1.65;color:var(--trails-ink-2)';
                loadDetail.split(' · ').forEach(function (line, at) {
                    var row = document.createElement('div');
                    row.style.cssText = 'padding:4px 0' + (at ? ';border-top:1px solid var(--trails-rule)' : '');
                    row.textContent = line;
                    told.appendChild(row);
                });
                var kept = document.createElement('div');
                kept.style.cssText = 'margin-top:12px;font-size:12px;color:var(--trails-ink-4)';
                kept.textContent = 'This plan is kept in this browser only — no account, no other device.';
                told.appendChild(kept);
                window.trailsChrome.detail('This route', told, 'plan');
            });
            status.appendChild(statusText);
            status.appendChild(about);

            // What can be done to the waypoint the reader has hold of, and only
            // while they have hold of one: a row of buttons that is always there
            // and usually does nothing is a row a reader stops reading. It is
            // also where reordering lives — dragging a pin moves it on the
            // ground and says nothing about where it comes in the sequence, so
            // the two need different gestures and only one of them can be a
            // drag.
            var edits = document.createElement('div');
            edits.style.cssText = 'margin-top:4px;display:none';
            var holding = document.createElement('div');
            holding.style.cssText = 'margin-bottom:2px;color:var(--trails-ink-2)';
            var buttons = document.createElement('div');
            edits.appendChild(holding);
            edits.appendChild(buttons);

            function button(label, explains, act) {
                var made = document.createElement('button');
                made.type = 'button';
                made.textContent = label;
                made.title = explains;
                made.style.cssText = 'font:inherit;font-size:12px;padding:2px 6px;margin-right:4px;cursor:pointer';
                made.addEventListener('click', act);
                return made;
            }

            var earlier = button('◀', 'Move this point one place earlier in the route',
                                 function () { moveBy(chosen, -1); });
            var later = button('▶', 'Move this point one place later in the route',
                               function () { moveBy(chosen, 1); });
            var drop = button('Remove', 'Take this point out and join the two legs that met at it',
                              function () { remove(chosen); });
            buttons.appendChild(earlier);
            buttons.appendChild(later);
            buttons.appendChild(drop);

            // ---- the points, listed --------------------------------------
            // **A route is a sequence, and a map cannot show a sequence.** The
            // pins carry numbers, but reading eleven of them off a map to find
            // out that point 7 comes before point 8 is not reading, it is
            // searching. The list is the sequence itself: one row a point, in
            // order, with what it is called and how far into the walk it comes.
            //
            // It folds away behind the count, which was already saying "5
            // points" and is now the handle for the five. A second heading
            // saying the same number would be the two-panel mistake the legend
            // was just cured of.
            var listOpen = false, listStations = [], heldRow = null;

            // **Whether the list is showing at all.** It used to be one flag,
            // set by the count that is the list's handle inside this control.
            // The list is lent to the profile panel now, where it stands whether
            // or not anything here has been folded open -- and everything drawn
            // *because* the list is showing was still asking the old flag: the
            // stage headings, with the name of each stage and its own file
            // button, and both entries of the save menu. Driven: a route cut
            // into two stages drew neither heading, and the save menu opened
            // empty.
            function listShowing() { return lentOut || listOpen; }

            // Which stage heading is being typed into, or null. The list is not
            // rebuilt while one is, for the reason it is not rebuilt while a row
            // is in the air.
            var namingRow = null;
            var listBox = document.createElement('div');
            // Named, like the picker and the mode beside it: its height is
            // computed now, so nothing can find it by the cap it used to carry.
            listBox.className = 'trails-plan-points';
            listBox.style.cssText = 'margin-top:4px;max-height:220px;overflow-y:auto;display:none';
            // **Lent to the profile panel, which is where a reader planning a
            // route is looking.** Seeing the sequence used to mean opening a
            // full-screen tool over the map being planned on -- the same defect
            // as a popup taking the screen, one panel further along. The node is
            // moved rather than copied: the rows a reader drags and the rows
            // this shows are one list, and a second rendering of a sequence is
            // how two of them come to disagree about the order.
            //
            // Whoever holds it owns its height. Lent, the page bounds it; kept,
            // the cap below does.
            var lentOut = false;
            // The wheel is the map's except where this has somewhere left to
            // scroll, the same bargain the legend strikes: a list that will not
            // scroll is as useless as a map that will not zoom, and only one of
            // them can have any one turn.
            listBox.addEventListener('wheel', function (event) {
                var room = listBox.scrollHeight - listBox.clientHeight;
                if (room <= 0) { return; }
                if (event.deltaY < 0 ? listBox.scrollTop > 0 : listBox.scrollTop < room - 1) {
                    event.stopPropagation();
                }
            }, {passive: true});

            // **How much room there is above the profile panel.** That panel
            // is anchored to the foot of the map, takes its full width and is the
            // reader's own to drag taller; measured, twelve points with the
            // profile pulled to 725 px put 315 px of this control underneath it,
            // and the two corners share a z-index so whichever is written later
            // wins. Rather than fight over which covers which, this asks what is
            // left and stays inside it.
            function roomAbove() {
                if (!box) { return 0; }
                var mine = box.getBoundingClientRect().top;
                var below = map.getContainer().getBoundingClientRect().bottom;
                var profile = document.querySelector('.trails-profile-panel');
                if (profile) {
                    var seen = profile.getBoundingClientRect();
                    if (seen.height > 0) { below = Math.min(below, seen.top); }
                }
                // Eight, not twelve: the profile panel keeps 80 px of map
                // clear of itself, and this control's own floor plus its top
                // margin have to come out of that 80 or the two overlap at the
                // one place it matters — the panel dragged as tall as it goes.
                return Math.max(0, below - mine - 8);
            }

            function fitList() {
                if (!box) { return; }
                var room = roomAbove();
                // Everything but the list, and **off the scroll height** rather
                // than the offset: the box is capped below, so its offset height
                // is the cap and subtracting the list from that would measure the
                // cap instead of the buttons. The fixed part is measured rather
                // than assumed, because the buttons wrap differently in every
                // browser and the load status comes and goes.
                var fixed = box.scrollHeight - listBox.offsetHeight;
                // The floor is deliberate: under it the list is not worth showing
                // and the box's own overflow takes over. A scrollbar on the whole
                // control beats a control holding rows that cannot be reached.
                // **The room there is, and not a constant.** It was capped at
                // 220 px whatever the screen: on a 900 px window a twelve-point
                // route showed a 220 px scroller inside a 552 px panel with 350
                // px of room under it, and a reader scrolling the rows ran off
                // the end of a list that had no reason to end. The cap that
                // matters is the one measured — how much room stands above the
                // profile panel — and that is `room`.
                if (lentOut) { return; }
                listBox.style.maxHeight = Math.max(40, room - fixed) + 'px';
                box.style.maxHeight = Math.max(40, room) + 'px';
            }

            // **What a row says where nothing near it is named.** It said the
            // point's own coordinates -- sixteen characters answering a question
            // nobody asks of a list. Measured on a seven-point route in this
            // park, *seven of seven* rows said a coordinate, because out here
            // there is rarely anything named within reach. What a reader wants
            // of a row is what the walk into it is made of, and the legs already
            // know: the coordinate moves into the row's own menu, where it can
            // be looked up and is not in the way.
            function groundInto(index) {
                if (index === 0) { return 'start'; }
                var leg = legs[index - 1];
                if (!leg) { return ''; }
                if (leg.failed) { return 'no way found'; }
                if (!leg.parts) { return 'working…'; }
                var crossing = false, recorded = false, straight = 0, walked = 0;
                leg.parts.forEach(function (part) {
                    if (part.kind === CROSSING || part.kind === 'water' || part.height === null) {
                        crossing = true;
                        return;
                    }
                    walked += part.length || 0;
                    if (part.kind === 'land') {
                        straight += part.length || 0;
                    } else if (part.kind === PLAN.gpx.trackKind) {
                        recorded = true;
                    }
                });
                if (crossing) { return 'over a crossing'; }
                // **By the greater part.** A hut stands a few metres off the
                // path and the walk to it is a straight piece of a leg that is
                // otherwise all path; a row calling that leg *drawn straight*
                // said what the map plainly did not show. Reported from the
                // phone beside a leg of 5.4 km with 63 m of it off the path.
                if (straight > 0 && straight >= walked / 2) { return 'drawn straight'; }
                if (recorded) { return 'as recorded'; }
                return 'along a path';
            }

            // The list can be lent to the profile, outside `box`. Close menus
            // wherever they are shown, including the profile's tour menu.
            var PLAN_MENUS = '.trails-plan-rowmenu, .trails-plan-savemenu, .trails-plan-stagemenu, .trails-profile-savemenu';
            function shutMenus(keep) {
                var open = document.querySelectorAll(PLAN_MENUS);
                for (var at = 0; at < open.length; at += 1) {
                    if (open[at] !== keep) { open[at].style.display = 'none'; }
                }
            }
            // Capture outside taps before Leaflet or a row stops propagation.
            // Preserve a trigger's own menu until its handler decides whether
            // to toggle it shut; every other menu closes first.
            document.addEventListener('click', function (event) {
                var target = event.target;
                if (!target || !target.closest) { shutMenus(); return; }
                var trigger = target.closest('.trails-plan-more, .trails-plan-save, .trails-plan-stage-file, .trails-profile-gpx');
                var keep = trigger ? trigger.parentNode.querySelector(PLAN_MENUS) : target.closest(PLAN_MENUS);
                shutMenus(keep);
            }, true);

            function drawList(stations) {
                listStations = stations || [];
                // Never while a row is in the air. A leg settling mid-drag would
                // otherwise rebuild the rows under the pointer and the drop
                // would land on nothing.
                //
                // **And never under a name being typed**, which is the same rule
                // for the same reason and was missing: measured, typing a stage
                // name and letting a point settle rebuilt the heading and threw
                // the half-typed name away with it, with the caret going to the
                // document. A leg settles a few hundred milliseconds after a
                // click, which is well inside the time it takes to type a word.
                if (heldRow !== null || namingRow !== null) { return; }
                while (listBox.firstChild) { listBox.removeChild(listBox.firstChild); }
                // **A tour nobody has cut gets no headings.** One stage is the
                // whole route, and a heading over it would offer the same file
                // the button already offers, under a second name -- which is the
                // two-panel mistake the legend was cured of.
                //
                // **And only while the list is open.** Each heading composes its
                // own stage to state its kilometres and its climb, so building
                // them behind a shut box is a walk over the route per stage that
                // nobody is looking at: measured with two stages, a refresh cost
                // 9.65 ms shut against 10.20 open, which is to say shutting the
                // list saved almost nothing. During a drag that is eight of them
                // a second.
                // **Whether this list can be edited at all.** Outside plan
                // mode it is an overview of a route somebody is reading: the
                // grip promises a drag that would change the route, the menu
                // offers four edits, and the stage name is a field. None of them
                // is drawn there. What stays is what a route says about itself
                // -- the order, the names, how far in each point comes -- and
                // the stage files, because writing one changes nothing.
                var editable = on;
                var stages = (listShowing() && points.length) ? stagesOf() : [];
                var heads = Object.create(null);
                if (stages.length > 1) {
                    stages.forEach(function (stage) { heads[stage.from] = stage; });
                }
                points.forEach(function (point, index) {
                    if (heads[index]) { listBox.appendChild(stageHead(heads[index])); }
                    // **One shape for all four, because all four are now a
                    // line in a menu.** They were four bare glyphs in the row —
                    // an em dash that cut a stage, a cross that removed a point,
                    // and two arrows that only appeared under a coarse pointer.
                    // Four unlabelled marks is four things to learn; a menu says
                    // what each one does, and the row keeps its width for the
                    // thing it is about.
                    function rowStep(label, explains, may, act) {
                        var made = document.createElement('button');
                        made.type = 'button';
                        made.draggable = false;
                        made.textContent = label;
                        made.title = explains;
                        made.style.cssText = 'display:' + (may ? 'block' : 'none') + ';width:100%;' +
                            'text-align:left;font:inherit;font-size:12px;padding:7px 10px;border:0;' +
                            'background:none;color:var(--trails-ink-2);cursor:pointer;white-space:nowrap';
                        made.addEventListener('click', function (event) {
                            // Or the row's own click would take hold of the
                            // point this one is moving.
                            event.stopPropagation();
                            shutMenus();
                            act();
                        });
                        return made;
                    }
                    var called = nameOf(point, index);
                    var row = document.createElement('div');
                    row.draggable = editable;
                    row.style.cssText = 'display:flex;align-items:center;gap:6px;padding:2px 3px;' +
                        'border-radius:3px;cursor:pointer;' +
                        // Painted only where it can be changed: outside plan
                        // mode the chosen row is where the *last* edit aimed,
                        // and a lit row nobody can move is a selection offered
                        // to a reader who cannot make one.
                        (editable && index === chosen
                            ? 'background:color-mix(in srgb, var(--trails-accent) 14%, transparent)' : '');
                    var grip = document.createElement('span');
                    grip.className = 'trails-plan-grip';
                    grip.textContent = '≡';
                    grip.title = 'Drag to move this point in the route';
                    grip.style.cssText = 'cursor:grab;color:var(--trails-ink-5);flex:none;' +
                        'display:' + (editable ? '' : 'none');
                    var number = document.createElement('span');
                    number.textContent = String(index + 1);
                    number.style.cssText = 'flex:none;min-width:14px;text-align:right;font-weight:600;color:' + ROUTE;
                    // What it is called where anything nearby is named, and its
                    // position where nothing is. A row that said only "3" would
                    // be the map's numbers again, in a column.
                    var says = document.createElement('span');
                    var ground = called.name ? null : groundInto(index);
                    says.textContent = called.name || ground;
                    says.style.cssText = 'flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;' +
                        'white-space:nowrap;color:' + (called.name ? 'var(--trails-ink-2)' : 'var(--trails-ink-4)');
                    says.title = called.name
                        ? called.name + (called.kind ? ' · ' + called.kind : '')
                        : point.lat.toFixed(4) + ', ' + point.lon.toFixed(4);
                    // How far into the walk it comes, which is the one thing the
                    // profile beside it and the map above it both leave out.
                    var far = document.createElement('span');
                    far.style.cssText = 'flex:none;color:var(--trails-ink-4);font-variant-numeric:tabular-nums';
                    far.textContent = listStations.length > index
                        ? (listStations[index] / 1000).toFixed(2) + ' km' : '';
                    // **Where a stage ends**, on the point it ends at. Not
                    // offered on the first or the last: a tour ends where it
                    // ends and a mark there would make a stage of no legs.
                    var cut = document.createElement('button');
                    cut.type = 'button';
                    cut.className = 'trails-plan-cut';
                    cut.draggable = false;
                    var isCut = typeof point.stage === 'string';
                    var mayCut = index > 0 && index + 1 < points.length;
                    cut.textContent = isCut ? 'Join to the next stage' : 'End a stage here';
                    cut.title = cut.textContent;
                    cut.style.cssText = 'display:' + (mayCut ? 'block' : 'none') + ';width:100%;' +
                        'text-align:left;font:inherit;font-size:12px;padding:7px 10px;border:0;' +
                        'background:none;cursor:pointer;white-space:nowrap;color:' +
                        (isCut ? 'var(--trails-accent)' : 'var(--trails-ink-2)');
                    cut.addEventListener('click', function (event) {
                        event.stopPropagation();
                        shutMenus();
                        cutAt(index, !isCut);
                    });

                    // **Named, because a row now holds two buttons.** A check
                    // taking `row.querySelector('button')` got the cut where it
                    // meant the removal the moment a second one appeared — which
                    // is the same trap as aiming a click by position, one level
                    // up. Both are addressed by what they are.
                    var out = document.createElement('button');
                    out.type = 'button';
                    out.className = 'trails-plan-out';
                    out.draggable = false;
                    out.textContent = 'Remove this point';
                    out.title = 'Take this point out and join the two legs that met at it';
                    out.style.cssText = 'display:block;width:100%;text-align:left;font:inherit;' +
                        'font-size:12px;padding:7px 10px;border:0;background:none;cursor:pointer;' +
                        'white-space:nowrap;color:var(--trails-extreme, #c62828)';
                    out.addEventListener('click', function (event) {
                        // Or the row's own click would take hold of the point
                        // this one is removing.
                        event.stopPropagation();
                        shutMenus();
                        remove(index);
                    });
                    row.addEventListener('click', function () {
                        // Choosing a point is where the next one goes in, which
                        // is an edit's aim rather than a reading.
                        if (!editable) { return; }
                        shutMenus();
                        chosen = chosen === index ? -1 : index;
                        refresh();
                    });
                    row.addEventListener('dragstart', function (event) {
                        heldRow = index;
                        event.dataTransfer.effectAllowed = 'move';
                        // Firefox starts no drag at all without something in the
                        // transfer, whatever the handlers say.
                        event.dataTransfer.setData('text/plain', String(index));
                        row.style.opacity = '0.4';
                    });
                    row.addEventListener('dragover', function (event) {
                        if (heldRow === null || heldRow === index) { return; }
                        event.preventDefault();
                        event.dataTransfer.dropEffect = 'move';
                        // An inset rather than a border, which would move every
                        // row below it by two pixels as the pointer passes.
                        row.style.boxShadow = 'inset 0 ' + (index < heldRow ? '2px' : '-2px') + ' 0 ' + ROUTE;
                    });
                    row.addEventListener('dragleave', function () { row.style.boxShadow = ''; });
                    row.addEventListener('drop', function (event) {
                        event.preventDefault();
                        row.style.boxShadow = '';
                        var from = heldRow;
                        heldRow = null;
                        if (from !== null && from !== index) { moveTo(from, index); }
                    });
                    row.addEventListener('dragend', function () {
                        heldRow = null;
                        row.style.opacity = '';
                        row.style.boxShadow = '';
                    });
                    // **Up and down, for the pointer that cannot drag.** HTML5
                    // dragging is not implemented by mobile browsers at all, so
                    // on a finger the grip promises something that cannot
                    // happen. These call `moveBy`, which is the pin's own
                    // gesture and already here — a swap with a neighbour, which
                    // is exactly what one step up or down means. **No new
                    // model, two buttons.** They are drawn only under a coarse
                    // pointer, so a row keeps its 21 px where a mouse is.
                    var up = rowStep('↑  One place earlier', 'Move this point one place earlier in the route',
                                     index > 0, function () { moveBy(index, -1); });
                    up.className = 'trails-plan-up';
                    var down = rowStep('↓  One place later', 'Move this point one place later in the route',
                                       index + 1 < points.length, function () { moveBy(index, 1); });
                    down.className = 'trails-plan-down';

                    // **Everything a row can do, in one place a reader can
                    // open.** The menu is built into the row rather than shared,
                    // so it scrolls with the row it belongs to and nothing has
                    // to work out where to put it.
                    var menu = document.createElement('div');
                    menu.className = 'trails-plan-rowmenu';
                    // **In the row and not over it.** Floated above, it was cut
                    // off by the list's own scroller on every row near the foot
                    // — seen in a screenshot, with *Remove this point* half
                    // drawn. Opened inside the row, the row grows, the list
                    // scrolls to it, and there is nothing to clip.
                    menu.style.cssText = 'display:none;width:100%;margin:4px 0 2px;' +
                        'background:var(--trails-sunk);border:1px solid var(--trails-rule);' +
                        'border-radius:7px;padding:3px';
                    L.DomEvent.disableClickPropagation(menu);
                    menu.appendChild(cut);
                    menu.appendChild(up);
                    menu.appendChild(down);
                    menu.appendChild(out);
                    // The coordinate, which is what the row used to say: kept,
                    // because it is occasionally exactly what somebody wants, and
                    // out of the way, because it usually is not.
                    var where = document.createElement('div');
                    where.style.cssText = 'padding:6px 10px;margin-top:2px;border-top:1px solid var(--trails-rule);' +
                        'color:var(--trails-ink-4);font-size:11px;font-variant-numeric:tabular-nums';
                    where.textContent = point.lat.toFixed(4) + ', ' + point.lon.toFixed(4);
                    menu.appendChild(where);

                    var more = document.createElement('button');
                    more.type = 'button';
                    more.className = 'trails-plan-more';
                    more.draggable = false;
                    more.textContent = '⋯';
                    more.title = 'What can be done with this point';
                    more.setAttribute('aria-label', 'What can be done with this point');
                    more.style.cssText = 'flex:none;font:inherit;font-size:15px;line-height:1;padding:0 5px;' +
                        'border:0;background:none;color:var(--trails-ink-4);cursor:pointer;' +
                        'display:' + (editable ? '' : 'none');
                    more.addEventListener('click', function (event) {
                        event.stopPropagation();
                        var wasOpen = menu.style.display !== 'none';
                        shutMenus();
                        if (!wasOpen) { menu.style.display = 'block'; }
                    });

                    row.style.flexWrap = 'wrap';
                    row.appendChild(grip);
                    row.appendChild(number);
                    row.appendChild(says);
                    row.appendChild(far);
                    row.appendChild(more);
                    row.appendChild(menu);
                    listBox.appendChild(row);
                });
            }

            // The heading over a stage: what it is called, what it comes to, and
            // its own file. **Its figures are composed and never sliced** -- an
            // ascent is not the difference of two ascents -- so this is the same
            // walk the whole tour uses, narrowed to the legs of this stage.
            function stageHead(stage) {
                var shape = composeRoute(stage.from, stage.to);
                var figure = figuresOf(shape);
                var head = document.createElement('div');
                head.className = 'trails-plan-stage';
                head.style.cssText = 'display:flex;align-items:center;gap:6px;margin-top:4px;' +
                    'padding:2px 3px;border-top:1px solid var(--trails-rule);color:var(--trails-ink-3)';

                // The name, and the two points it runs between where nobody has
                // given it one. A placeholder rather than a value, so that a
                // stage nobody named writes its own numbers and a stage somebody
                // named keeps the name through every edit that does not move it.
                var called = document.createElement('input');
                called.type = 'text';
                called.className = 'trails-plan-stage-name';
                called.value = stage.name || '';
                called.placeholder = stageName(stage);
                called.title = 'What this stage is called in its own file';
                called.style.cssText = 'flex:1 1 auto;min-width:0;font:inherit;font-size:12px;' +
                    'padding:1px 3px;border:1px solid transparent;background:none;color:var(--trails-ink-2)';
                called.addEventListener('focus', function () {
                    called.style.borderColor = 'var(--trails-edge)';
                    namingRow = stage.at;
                });
                called.addEventListener('blur', function () {
                    called.style.borderColor = 'transparent';
                    namingRow = null;
                    nameStage(stage.to, called.value);
                });
                // Leaflet binds its own shortcuts to the container, so a typed
                // '+' would zoom the map mid-word.
                L.DomEvent.on(called, 'keydown keypress keyup', L.DomEvent.stopPropagation);

                var says = document.createElement('span');
                says.style.cssText = 'flex:none;font-variant-numeric:tabular-nums';
                says.textContent = (shape.total / 1000).toFixed(2) + ' km' +
                    (shape.read && isFinite(figure.ascent) ? ' · ↑' + Math.round(figure.ascent) + ' m' : '');

                var file = document.createElement('button');
                file.type = 'button';
                file.className = 'trails-plan-stage-file';
                file.innerHTML = planIcon('save');
                file.title = 'Download this stage on its own';
                file.setAttribute('aria-label', 'Download this stage on its own');
                file.style.cssText = 'flex:none;width:26px;height:22px;align-items:center;' +
                    'justify-content:center;border:1px solid var(--trails-rule);border-radius:5px;' +
                    'background:none;color:var(--trails-ink-4);cursor:pointer;padding:0;display:' +
                    ((panel() && panel().writes()) ? 'flex' : 'none');
                // Refused while any leg of the route is unsettled, for the
                // reason the whole tour's is: a file that states it breaks its
                // track only at crossings must not be written over a hole.
                file.disabled = !!writable().why;
                var menu = document.createElement('div');
                menu.className = 'trails-plan-stagemenu';
                menu.style.cssText = saveMenu.style.cssText;
                menu.style.display = 'none';
                L.DomEvent.disableClickPropagation(menu);
                function stageFileEntry(label, explains, garmin) {
                    var made = oneFile.cloneNode(false);
                    made.textContent = label;
                    made.title = explains;
                    made.style.display = 'block';
                    made.disabled = file.disabled;
                    made.addEventListener('click', function (event) {
                        event.stopPropagation();
                        shutMenus();
                        try { saveStage(stage, garmin); } catch (failure) { fileFailed(failure); }
                    });
                    return made;
                }
                var ordinary = stageFileEntry('This stage (GPX)', 'Download this stage on its own', false);
                ordinary.className = 'trails-plan-stage-gpx';
                var garmin = stageFileEntry('For Garmin (course)',
                    'One line of at most 200 points; Garmin Explore imports it as a course that syncs to the watch', true);
                garmin.className = 'trails-plan-stage-garmin';
                menu.appendChild(ordinary);
                menu.appendChild(garmin);
                file.addEventListener('click', function (event) {
                    event.stopPropagation();
                    var wasOpen = menu.style.display !== 'none';
                    shutMenus();
                    if (!wasOpen) {
                        menu.style.top = '100%';
                        menu.style.bottom = 'auto';
                        menu.style.display = 'block';
                        // Keep the last stage's choices inside the scroller,
                        // without moving the icon under the reader's finger.
                        var iconBox = file.getBoundingClientRect();
                        var menuBox = menu.getBoundingClientRect();
                        var listRect = listBox.getBoundingClientRect();
                        var below = listRect.top + listBox.clientTop + listBox.clientHeight - iconBox.bottom;
                        var upward = below < menuBox.height;
                        menu.style.top = upward ? 'auto' : '100%';
                        menu.style.bottom = upward ? '100%' : 'auto';
                        menu.style.boxShadow = '0 ' + (upward ? '-2px' : '2px') + ' 10px rgba(0,0,0,0.22)';
                    }
                });
                var fileWrap = document.createElement('div');
                fileWrap.className = 'trails-plan-stage-save';
                fileWrap.style.cssText = 'position:relative;flex:none';
                fileWrap.appendChild(file);
                fileWrap.appendChild(menu);

                // **A field where it can be typed in, and text where it cannot.**
                // A read-only input still looks like something to type into, and
                // a stage a reader cannot rename should not offer a caret. The
                // placeholder is what a stage is called when nobody named it, so
                // the text says the same thing the empty field would have.
                if (on) {
                    head.appendChild(called);
                } else {
                    var named = document.createElement('span');
                    named.className = 'trails-plan-stage-named';
                    named.textContent = stage.name || stageName(stage);
                    named.style.cssText = 'flex:1 1 auto;min-width:0;overflow:hidden;' +
                        'text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:var(--trails-ink-2)';
                    head.appendChild(named);
                }
                head.appendChild(says);
                head.appendChild(fileWrap);
                return head;
            }

            // **What the tour is called**, above the list because that is what
            // the list is a list of. A placeholder rather than a value where
            // nobody has typed one: a tour with no name of its own writes the
            // one every file carries by default, and showing that as a value
            // would turn a default into a choice the moment anything is saved.
            var titleRow = document.createElement('div');
            titleRow.style.cssText = 'margin-top:4px';
            var title = document.createElement('input');
            title.type = 'text';
            title.className = 'trails-plan-title';
            title.title = 'What this tour is called, in its files and in their names';
            title.style.cssText = 'width:100%;box-sizing:border-box;font:inherit;font-size:12px;' +
                'padding:1px 3px;border:1px solid var(--trails-rule);border-radius:3px;background:none;color:var(--trails-ink-2)';
            title.addEventListener('blur', function () {
                tourName = title.value.trim();
                refresh();
            });
            // Leaflet binds its own shortcuts to the container, so a typed '+'
            // would zoom the map mid-word.
            L.DomEvent.on(title, 'keydown keypress keyup', L.DomEvent.stopPropagation);
            // **The whole tour as one file, where a reader planning one can
            // reach it.** The panel over the profile writes exactly this file
            // and has always offered it — but on a narrow screen that panel is
            // not on the screen by default, so a reader planning on a phone had
            // no way to the one file they came for without first going to look
            // for the profile. The same file from the same writer, offered in
            // the place the route is being made.
            var oneFile = document.createElement('button');
            oneFile.type = 'button';
            oneFile.className = 'trails-plan-gpx';
            oneFile.textContent = 'Whole tour (GPX)';
            oneFile.title = 'The whole route as one GPX file, its stage marks and all';
            oneFile.style.cssText = 'display:block;width:100%;text-align:left;font:inherit;font-size:12px;' +
                'padding:7px 10px;border:0;background:none;color:var(--trails-ink-2);cursor:pointer;white-space:nowrap';
            oneFile.addEventListener('click', function () {
                try {
                    saveWhole();
                } catch (failure) {
                    fileFailed(failure);
                }
            });
            var garminFile = oneFile.cloneNode(false);
            garminFile.className = 'trails-plan-garmin';
            garminFile.textContent = 'For Garmin (course)';
            garminFile.title = 'One line of at most 200 points; Garmin Explore imports it as a course that syncs to the watch';
            garminFile.addEventListener('click', function () {
                try { saveWhole(true); } catch (failure) { fileFailed(failure); }
            });
            // Offered only where there are stages to gather. With one stage it
            // would hand over the same file the button already offers, twice,
            // under two names.
            var everything = document.createElement('button');
            everything.type = 'button';
            everything.className = 'trails-plan-zip';
            everything.textContent = 'All stages (zip)';
            everything.title = 'Every stage and the whole tour, as ordinary GPX and Garmin courses, in one archive';
            everything.style.cssText = 'display:block;width:100%;text-align:left;font:inherit;font-size:12px;' +
                'padding:7px 10px;border:0;background:none;color:var(--trails-ink-2);cursor:pointer;white-space:nowrap';
            everything.addEventListener('click', function () {
                try {
                    saveStages();
                } catch (failure) {
                    fileFailed(failure);
                }
            });

            titleRow.appendChild(title);

            // One mark opens the file choices. The archive leads where there
            // are multiple stages; ordinary GPX and Garmin are always offered.
            var saveMenu = document.createElement('div');
            saveMenu.className = 'trails-plan-savemenu';
            saveMenu.style.cssText = 'display:none;position:absolute;right:0;top:100%;z-index:6;' +
                'min-width:170px;background:var(--trails-solid);border:1px solid var(--trails-edge);' +
                'border-radius:7px;padding:3px;box-shadow:0 2px 10px rgba(0,0,0,0.22)';
            L.DomEvent.disableClickPropagation(saveMenu);
            saveMenu.appendChild(everything);
            saveMenu.appendChild(oneFile);
            saveMenu.appendChild(garminFile);

            var save = document.createElement('button');
            save.type = 'button';
            save.className = 'trails-plan-save';
            asTool(save, 'save', 'Save this route as a file');
            var saveWrap = document.createElement('div');
            saveWrap.style.cssText = 'position:relative;flex:none';
            saveWrap.appendChild(save);
            saveWrap.appendChild(saveMenu);
            save.addEventListener('click', function (event) {
                event.stopPropagation();
                var wasOpen = saveMenu.style.display !== 'none';
                shutMenus();
                if (!wasOpen) { saveMenu.style.display = 'block'; }
            });


            // Said rather than discovered. Three gestures share one click here
            // and none of them is guessable from a map that has never had more
            // than one.

            // What the last load turned out to be, or what went wrong with it.
            var loadSaid = '';

            // ---- the file control ---------------------------------------------------
            // **A page served from the disk may read a file the reader picks**,
            // and that single fact is what this phase rests on. Checked before
            // any of it was built: <input type="file"> plus FileReader returned
            // all 1,197,976 bytes of a chain export and DOMParser found its
            // trackpoints. Nothing else here would have mattered if it had
            // failed.
            //
            // The input is hidden behind a button of its own rather than shown:
            // a bare file input is a browser widget in the middle of a control
            // that is otherwise this map's, and it cannot be made to say what it
            // does. Hidden is not unreachable — it is still an input and still
            // takes a file from a driven check.
            var picker = document.createElement('input');
            picker.type = 'file';
            picker.accept = '.gpx,application/gpx+xml,application/xml,text/xml';
            picker.style.display = 'none';
            picker.className = 'trails-plan-file';

            var chooser = document.createElement('button');
            chooser.type = 'button';
            chooser.className = 'trails-plan-load';
            asTool(chooser, 'load', 'Load a GPX — a route or a recorded track, and carry on from it');

            // **The row of tools**, in the order a reader meets them: finish,
            // step back, start over, bring a file in, take one out.
            var tools = document.createElement('div');
            tools.className = 'trails-plan-tools';
            tools.style.cssText = 'display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:8px 0 2px';
            tools.appendChild(toggle);
            tools.appendChild(back);
            tools.appendChild(fresh);
            tools.appendChild(chooser);
            tools.appendChild(saveWrap);

            var modes = document.createElement('select');
            modes.className = 'trails-plan-mode';
            modes.style.cssText = 'font:inherit;font-size:12px;margin-left:4px;max-width:12em';
            MODES.forEach(function (mode) {
                var option = document.createElement('option');
                option.value = mode.key;
                option.textContent = mode.label;
                modes.appendChild(option);
            });

            // The button has moved into the row of tools; this holds the file
            // input, which is invisible and has to stay in the document.
            var loading = document.createElement('div');
            loading.style.cssText = 'margin:0';
            loading.appendChild(picker);

            // ---- the question ------------------------------------------------------
            // Shown between the file being read and anything being done with
            // it, and it is the only moment at which the plan on the map still
            // exists: taking a file replaces it and there is no way back, since
            // undo takes a point off the end and a load has no history. So this
            // is where the loss is said, and it is said as a count rather than
            // as a warning about files in general.
            var offerBox = document.createElement('div');
            offerBox.className = 'trails-plan-offer';
            offerBox.style.cssText = 'margin-top:4px;padding-top:4px;border-top:1px solid var(--trails-rule);max-width:22em';

            var offerSaid = document.createElement('div');
            offerSaid.style.cssText = 'color:var(--trails-ink-3)';

            var offerRow = document.createElement('div');
            offerRow.style.cssText = 'margin-top:4px';
            var offerAsks = document.createElement('span');
            offerAsks.textContent = 'Read it as';
            offerRow.appendChild(offerAsks);
            offerRow.appendChild(modes);

            // What the chosen mode would do *to this file*, under the selector
            // rather than inside it: an option list is where a name goes and a
            // sentence does not fit in one.
            var offerMeans = document.createElement('div');
            offerMeans.style.cssText = 'margin-top:4px';

            var offerCosts = document.createElement('div');
            offerCosts.style.cssText = 'margin-top:4px;color:var(--trails-warn)';

            var offerButtons = document.createElement('div');
            offerButtons.style.cssText = 'margin-top:4px';
            var take = document.createElement('button');
            take.type = 'button';
            take.className = 'trails-plan-take';
            take.textContent = 'Load it';
            take.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;margin-right:6px;cursor:pointer';
            var drop = document.createElement('button');
            drop.type = 'button';
            drop.className = 'trails-plan-drop';
            drop.textContent = 'Cancel';
            drop.style.cssText = 'font:inherit;font-size:12px;padding:2px 8px;cursor:pointer';
            offerButtons.appendChild(take);
            offerButtons.appendChild(drop);

            offerBox.appendChild(offerSaid);
            offerBox.appendChild(offerRow);
            offerBox.appendChild(offerMeans);
            offerBox.appendChild(offerCosts);
            offerBox.appendChild(offerButtons);

            modes.addEventListener('change', function () {
                if (!pendingFile) { return; }
                pendingFile.mode = modes.value;
                refresh();
            });

            take.addEventListener('click', function () {
                if (!pendingFile) { return; }
                var ready = pendingFile;
                try {
                    takeGpx(ready.read, ready.mode);
                } catch (failure) {
                    // The same rule the read already follows: what is on the map
                    // stays. A mode that threw has not replaced anything, and
                    // the offer is dropped rather than left standing over a file
                    // that cannot be taken the way it was asked for.
                    pendingFile = null;
                    loadSaid = 'That file could not be loaded: ' +
                        (failure && failure.message ? failure.message : String(failure));
                    refresh();
                }
            });

            drop.addEventListener('click', function () { dismissFile(); });

            var loadStatus = document.createElement('div');
            loadStatus.style.cssText = 'margin-top:4px;color:var(--trails-ink-3);max-width:22em';

            chooser.addEventListener('click', function () { picker.click(); });

            picker.addEventListener('change', function () {
                var file = picker.files && picker.files[0];
                if (!file) { return; }
                var reader = new FileReader();
                // **Two handlers and not one catch over both.** The wait for the
                // disk and the work on what came back fail for different reasons
                // and a handler spanning them blames the wait: the panel spent
                // two runs looking for a payload that had arrived perfectly well
                // because a fault while drawing it was reported as one.
                reader.onerror = function () {
                    loadSaid = 'That file could not be read off the disk.';
                    picker.value = '';
                    refresh();
                };
                reader.onload = function () {
                    try {
                        // Read and described, not taken: the mode is asked for
                        // once there is something to ask it about.
                        offerFile(String(reader.result), file.name);
                    } catch (failure) {
                        // **What was already on the map stays.** `readGpx`
                        // refuses before anything is touched, so the recording
                        // that is loaded is still the one every waypoint is
                        // anchored to — and dropping it here would leave those
                        // anchors pointing at nothing, so the next edit would
                        // quietly turn a recorded stretch into a straight line.
                        loadSaid = 'That file could not be loaded: ' +
                            (failure && failure.message ? failure.message : String(failure));
                        refresh();
                    }
                    // Cleared, or picking the same file twice is not a change
                    // and the second pick does nothing at all.
                    picker.value = '';
                };
                reader.readAsText(file);
            });

            var control = L.control({position: 'topright'});
            var box = null;
            control.onAdd = function () {
                box = L.DomUtil.create('div', 'trails-plan-control');
                box.style.cssText = 'background:var(--trails-panel);padding:6px 8px;border:1px solid var(--trails-edge);' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4';
                // **The name and the numbers first**, because that is what a
                // route is; then the tools; then the list, which is the panel's
                // actual content. It used to open with five stacked word buttons
                // and a paragraph, and the first waypoint came 234 px down.
                // **The name goes where the list goes.** It stands above the
                // list because that is what the list is a list of, and lending
                // the list away without it left a reader planning on a phone
                // with no way to call the tour anything -- the field was two
                // panels behind a burger, in a control that no longer holds
                // what it names.
                if (!lentOut) { box.appendChild(titleRow); }
                box.appendChild(tools);
                // Loading is how a plan starts from a file, so it is offered
                // whether or not plan mode is already on — and switching it on
                // is what loading does.
                //
                // **The mode is asked after the file has been read, not before
                // it.** It stood beside the button for as long as the answer was
                // thought to be a decision about the file rather than about what
                // is in it; it is not. Three mode names had to be true of a
                // planned route and of somebody's GPS recording at once, and a
                // reader picking the first of them lost the points their route
                // was planned with, with the page naming the number it was about
                // to discard. Asked here, the question can say what this file
                // turned out to be, what each answer would do to it, and what
                // taking it costs.
                box.appendChild(loading);
                box.appendChild(offerBox);
                box.appendChild(loadStatus);
                box.appendChild(status);
                // Only where nothing has borrowed it. The panel takes it on the
                // first refresh; before that it belongs here, and on a page
                // built without a profile panel it stays here for good.
                if (!lentOut) { box.appendChild(listBox); }
                box.style.overflowY = 'auto';
                // The wheel is the map's except where this has somewhere left to
                // scroll, the same bargain the legend and the list strike. The
                // list's own handler runs first and takes the turn while it can,
                // so the two nest rather than fight.
                box.addEventListener('wheel', function (event) {
                    var spare = box.scrollHeight - box.clientHeight;
                    if (spare > 0 && (event.deltaY < 0 ? box.scrollTop > 0 : box.scrollTop < spare - 1)) {
                        event.stopPropagation();
                        return;
                    }
                    // **Nothing left to scroll here, and the map is still not
                    // next.** Reported: scrolling over the waypoints zoomed the
                    // map. Where the chrome holds this panel the chrome is the
                    // boundary and gets its turn at the rows below; where there
                    // is no chrome, the boundary is this box. Either way a wheel
                    // that started over a panel does not end in a zoom.
                    if (!box.closest || !box.closest('.trails-chrome')) { event.stopPropagation(); }
                }, {passive: true});
                // Clicking inside the control must not reach the map, and the
                // wheel must, or the map reads as frozen under it.
                L.DomEvent.disableClickPropagation(box);
                return box;
            };
            control.addTo(map);

            // Leaflet appends to a top corner, and this one is reached for
            // before anything else in it, so it goes to the front. It had the
            // layer control for company here until the legend took that job over
            // and the corner emptied.
            var corner = control.getContainer().parentNode;
            corner.insertBefore(control.getContainer(), corner.firstChild);

            // The profile panel's height is a reader's to drag, and nothing
            // announces that. Watching the element is the one way to hear about
            // it that does not reach into the other control's own state.
            map.on('resize', fitList);
            if (typeof ResizeObserver !== 'undefined') {
                var watched = document.querySelector('.trails-profile-panel');
                if (watched) { new ResizeObserver(fitList).observe(watched); }
            }
            fitList();

            function say(message) {
                statusText.textContent = message;
            }

            // **What a route is, in one line.** Distance, climb, how many points
            // and how many stages -- the first two being the same figures the
            // profile's own heading carries, in the same order, because a page
            // should say one thing one way. Pushed from `present()`, which has
            // just composed the route: asking for it here would compose it
            // again, and that is 45 ms over a 37 km route on every refresh.
            var lastFigures = null;
            function paintFigures() {
                var listable = on && points.length > 0;
                // The caret is the handle for a list this control still holds.
                // Lent away, it would be a handle for nothing: the figures are
                // then a count and not a fold.
                var mark = (listable && !lentOut) ? (listOpen ? '\u25be ' : '\u25b8 ') : '';
                if (!points.length) {
                    say(mark + 'Click the map to place the first point.');
                    return;
                }
                var said = [];
                if (lastFigures) {
                    said.push((lastFigures.metres / 1000).toFixed(2) + ' km');
                    if (isFinite(lastFigures.ascent)) {
                        said.push('\u2191' + Math.round(lastFigures.ascent) + ' m');
                    }
                }
                said.push(points.length + (points.length === 1 ? ' point' : ' points'));
                var stages = stagesOf().length;
                if (stages > 1) { said.push(stages + ' stages'); }
                if (settling) { said.push('working\u2026'); }
                say(mark + said.join(' \u00b7 '));
            }

            function refresh() {
                // **One word, and it is the one that ends the work.** The rest
                // of the row are tools and carry marks.
                toggle.textContent = on ? 'Done' : 'Plan a route';
                back.disabled = !history.length;
                back.style.opacity = history.length ? '' : '0.4';
                fresh.disabled = !points.length;
                fresh.style.opacity = points.length ? '' : '0.4';
                back.style.display = on ? '' : 'none';
                fresh.style.display = on ? '' : 'none';
                saveWrap.style.display = on ? '' : 'none';
                // **The profile switch is not here.** It was, and it did
                // nothing: it called `trailsChrome.profile()` with no argument,
                // which is the *reading* of that state and not the setting of
                // it. Rather than fix a third switch, it is gone — the rail
                // carries it on a wide screen and the row at the foot of the
                // panel on every screen, which is where a reader planning a
                // route already is.
                // **Nor is there a row of edits any more.** *Move earlier*,
                // *move later* and *Remove* stood in a box of their own that
                // appeared when a point was picked and was empty the rest of the
                // time. They are lines in the row's own menu now, beside the
                // stage mark and the coordinate, which is where a reader looks
                // when the question is about *that* point.
                status.style.display = on ? '' : 'none';
                // The figures are the list's handle. They were a bare count and
                // are now what a route is.
                var listable = on && points.length > 0;
                status.style.cursor = listable ? 'pointer' : '';
                status.title = listable ? 'Show or hide the points, one to a row' : '';
                listBox.style.display = (listShowing() && (lentOut || listable)) ? '' : 'none';
                // The name stands with the route, above the tools, and only
                // where there is a route: a box asking what to call nothing is a
                // row of the control spent on nothing.
                titleRow.style.display = listable ? '' : 'none';
                if (document.activeElement !== title) {
                    title.value = tourName;
                    title.placeholder = (panel() && panel().routeName()) || 'This tour';
                }
                // Offered only where there is more than one stage to gather and
                // where the panel can write a file at all.
                var writes = !!(panel() && panel().writes());
                var gathered = writes && listShowing() && stagesOf().length > 1;
                // A route of one point is not a file, and the reason the button
                // is not merely disabled there is the same one the profile panel
                // gives: an offer over nothing is furniture.
                var refusing = writable().why;
                oneFile.style.display = (writes && listShowing() && points.length > 1) ? '' : 'none';
                oneFile.disabled = !!refusing;
                garminFile.style.display = oneFile.style.display;
                garminFile.disabled = oneFile.disabled;
                // Why it is refused, where it is: 'still working out 2 legs' is
                // the difference between a button that is waiting and one that
                // is broken.
                oneFile.title = refusing || 'The whole route as one GPX file, its stage marks and all';
                everything.style.display = gathered ? '' : 'none';
                everything.disabled = !!refusing;
                if (on) { paintFigures(); }
                // What the last load turned out to be, and what it cost once
                // every leg of it has settled. **Stamped here rather than where
                // the file was read**: the legs settle a microtask or more after
                // the load returns, so a figure taken at the end of loadGpx
                // would time the parsing and call it the load.
                if (loaded && loaded.settleMs === null && !settling) {
                    loaded.settleMs = performance.now() - loaded.began;
                    // Said here for the same reason the figure is: the route is
                    // only comparable with the file once every leg of it has
                    // settled, and before that the two disagree about ground
                    // that is still being worked out.
                    loadSaid += drifted();
                    // And shown, for the same reason again: a route half worked
                    // out has half a shape, and fitting the map to it would
                    // leave the reader looking at the wrong window.
                    if (fitWanted) { fitWanted = false; showRoute(); }
                }
                about.style.display = (loadDetail && window.trailsChrome && window.trailsChrome.detail) ? '' : 'none';
                loadStatus.textContent = loadSaid + (keptSaid ? (loadSaid ? ' · ' : '') + keptSaid : '');
                loadStatus.style.display = (loadSaid || keptSaid) ? '' : 'none';
                // The question, wherever one stands. **Its wording comes out of
                // the one table** rather than being assembled here: the sentence
                // under the selector and the mode it describes are one decision,
                // and writing either of them twice is how the two come apart.
                offerBox.style.display = pendingFile ? '' : 'none';
                if (pendingFile) {
                    offerSaid.textContent = pendingFile.name + ' — ' + describeFile(pendingFile.read);
                    modes.value = pendingFile.mode;
                    offerMeans.textContent = READINGS[pendingFile.kind][pendingFile.mode];
                    // Said as a count and only where there is something to lose.
                    // 'This replaces your plan' over an empty map is a warning
                    // about nothing, and a reader who is warned about nothing
                    // stops reading warnings.
                    // **"There is no way back" was true and is not any more.**
                    // The history covers a load, so undo restores the plan the
                    // file replaced — points, tour name and all. The question is
                    // still worth asking: it says what the file turned out to be
                    // and what each mode would do to it, which is the half that
                    // was never about the way back.
                    offerCosts.textContent = points.length
                        ? 'This replaces the ' + points.length +
                          (points.length === 1 ? ' point' : ' points') +
                          ' on the map. Undo brings them back.'
                        : '';
                    offerCosts.style.display = points.length ? '' : 'none';
                }
                // The pins say which point is which and which one is held, and
                // both change with every edit. Applied here as differences, so
                // that a refresh in the middle of a drag writes nothing.
                dressPins();
                present();
                // Last, because everything above it can change how tall this is.
                fitList();
                // And after all of it, because what is kept is what the reader
                // is now looking at.
                keepLater();
            }

            // What only this side knows and the file cannot be written without:
            // where the reader put its points down, what each leg is made of,
            // and whether there is a hole in the route.
            //
            // **A hole refuses the file rather than being written into it.** The
            // file says it breaks its track only at crossings, and a leg still
            // being worked out or one the height service refused would break it
            // somewhere else with nothing in the file to say so.
            function writable() {
                var outstanding = unsettled(), waiting = outstanding.waiting, refused = outstanding.refused.length;
                return {
                    why: points.length < 2 ? 'Place a second point and there is a route to write.'
                        : waiting ? 'Still working out ' + waiting + (waiting === 1 ? ' leg.' : ' legs.')
                        : refused ? refused + (refused === 1 ? ' leg has' : ' legs have') +
                            ' no way and no heights, so the route has a gap that is not a crossing.'
                        : '',
                    name: tourName || null,
                    // Said outright rather than left to a fallback: what the
                    // file is called and what the track is called are two
                    // decisions, and here they happen to agree.
                    stem: tourName || null,
                    waypoints: points.map(function (point, at) { return nameOf(point, at); }),
                    legs: legs.map(function (leg) {
                        return (leg.parts || []).map(function (part) { return {kind: part.kind, length: part.length}; });
                    })
                };
            }

            // ---- keeping a plan across a reload -----------------------------------
            // **A reload threw the plan away**, and that is the one thing a
            // reader cannot get back by clicking again: the route is theirs, and
            // the page was the only place it existed. So it is kept in this
            // browser and comes back on the next load as it was left.
            //
            // **What is kept is the file this page writes**, and not a second
            // description of the plan beside it. The route already has a
            // serialised form -- the GPX the download button offers -- and that
            // form already has a reader: the picker's, which restores the
            // points, the stage marks, the tour's name and the stretches a load
            // kept as recorded. A shorter payload of its own would be a second
            // recording of one decision, and two recordings of one decision
            // drifting apart is the failure this page has found three times.
            //
            // It costs bytes. A restored plan's routed stretches are routed
            // again rather than copied, so every `<trkpt>` in the kept copy is
            // weight nothing reads -- 27 km of route is about 800 kB. That is
            // the price of one writer and one reader, and the quota is caught
            // and said rather than guessed at.
            //
            // **In this browser only**, and the sentence a reader is shown says
            // so. Nothing leaves the page: no account, no sync, and another
            // device knows nothing about it. iOS clears script-written storage
            // for a site nobody has visited in seven days, which is a further
            // reason the panel says a tour worth keeping is worth downloading.
            var KEEP_AFTER_MS = 1200;
            var keptWhen = null;
            var keptSaid = '';
            var keptMs = null;
            var keptBytes = 0;

            // Resolved every time rather than once: the profile panel's script
            // may not have run when this one does, and a key of 'map' written
            // in that instant would be a plan kept where nothing looks for it.
            function keptKey() {
                var prefix = panel() ? panel().prefix() : null;
                return 'trails.plan.' + (prefix || 'map');
            }

            function forgetKept() {
                try {
                    window.localStorage.removeItem(keptKey());
                    window.localStorage.removeItem(keptKey() + '.on');
                } catch (blocked) { return; }
                keptBytes = 0;
            }

            // **Written when the editing stops, not while it happens.** A drag
            // refreshes at the rate the pointer reports and composing the route
            // and writing the file is the most expensive thing on this page that
            // nobody asked for.
            function keepLater() {
                if (keptWhen) { clearTimeout(keptWhen); }
                keptWhen = setTimeout(writeKept, KEEP_AFTER_MS);
            }

            function writeKept() {
                if (keptWhen) { clearTimeout(keptWhen); }
                keptWhen = null;
                var was = keptSaid;
                try {
                    // Nothing on the map is nothing to keep, and it is also how
                    // a reader throws a plan away: take the points out and the
                    // kept copy goes with them.
                    if (!points.length || !panel() || !panel().writes()) { forgetKept(); keptSaid = ''; return; }
                    var plan = writable();
                    // **A route with a hole refuses to be written to a file**,
                    // and the kept copy is that file. A plan still working out
                    // its legs keeps the copy it had until it has.
                    if (plan.why) { return; }
                    var began = performance.now();
                    var shape = composeRoute();
                    var made = panel().routeFile(figuresOf(shape), shape, told(shape), plan);
                    window.localStorage.setItem(keptKey(), made.text);
                    window.localStorage.setItem(keptKey() + '.on', on ? '1' : '0');
                    keptMs = performance.now() - began;
                    keptBytes = made.text.length;
                    keptSaid = '';
                } catch (refused) {
                    // **Said and not swallowed.** A quota that is quietly full is
                    // a reader who believes their plan is being kept.
                    forgetKept();
                    keptSaid = (refused && refused.name === 'QuotaExceededError')
                        ? 'This tour is too large to keep in this browser — download it to keep it.'
                        : 'This browser is not keeping the plan: ' +
                          (refused && refused.message ? refused.message : String(refused));
                } finally {
                    // Only where the sentence changed, or the refresh this asks
                    // for would schedule the write that asked for the refresh.
                    if (keptSaid !== was) { refresh(); }
                }
            }

            // **The last event a discarded tab is given.** A phone closes tabs
            // without asking and iOS delivers no `beforeunload` at all, so a
            // plan edited and left is written here or not at all.
            window.addEventListener('pagehide', function () { if (keptWhen) { writeKept(); } });

            function restoreKept() {
                var text = null, was = null;
                try {
                    text = window.localStorage.getItem(keptKey());
                    was = window.localStorage.getItem(keptKey() + '.on');
                } catch (blocked) { return; }
                if (!text) { return; }
                keptBytes = text.length;
                try {
                    loadGpx(text, 'asis');
                } catch (unreadable) {
                    // **A payload that cannot be read is let go of, once.**
                    // Anything else is a page that fails the same way on every
                    // load with no way for a reader to clear it.
                    forgetKept();
                    loadSaid = 'The plan kept in this browser could not be read, so it has been let go.';
                    refresh();
                    return;
                }
                // Ahead of what the loader said rather than instead of it: the
                // file's own description and the drift the panel reports when
                // the network has moved under a plan are both worth keeping.
                // **Its own sentence, not a prefix.** Glued in front of the
                // file's description it read "…kept in this browser only. a
                // route this map wrote: …" — a lower-case word after a full
                // stop, which is what gluing two sentences written apart always
                // gives you. The description is behind the mark now.
                loadSaid = 'Back as you left it.';
                // **Including whether they were still planning.** A reader who
                // pressed Done and reloaded should not find every tap placing a
                // point again; the route stays drawn either way.
                if (was === '0') { switchTo(false); }
                refresh();
            }

            // What the panel is shown. The route's series is composed here and
            // handed over; the panel draws the curve, the bands, the crosshair
            // and the reduction exactly as it does for a chain, and writes the
            // file from the same series it drew.
            // **Pushed, not polled.** The chrome draws a bar at the foot of a
            // narrow screen while a route is being planned, and everything on it
            // comes from here — reading it the other way round would mean
            // `state()`, which composes the whole route, on a timer. The same
            // seam the profile panel already uses to say what is selected.
            function sayPlanning(shape) {
                var figure = shape && points.length > 1 ? figuresOf(shape) : null;
                lastFigures = shape ? {metres: shape.total, ascent: figure ? figure.ascent : NaN} : null;
                paintFigures();
                // Handed over once, on the first refresh there is a panel for:
                // by then everything that draws into it exists, and asking again
                // afterwards would move a node a reader may be scrolling.
                if (!lentOut && panel() && panel().list) { lentOut = !!panel().list(listBox, titleRow); }
                if (!window.trailsChrome || !window.trailsChrome.planning) { return; }
                window.trailsChrome.planning({
                    on: on,
                    points: points.length,
                    metres: shape ? shape.total : 0,
                    ascent: figure ? figure.ascent : null,
                    undoable: history.length,
                    working: settling > 0
                });
            }

            // **The panel is one panel and two routes can be offered.** While
            // it is drawing the way to a goal, a refresh of the plan is still a
            // refresh -- the list, the bar, the figures -- but it is not a
            // reason to take the panel back from a route the reader chose. Plan
            // mode being switched on is: there the panel is what planning is
            // read in.
            function feedPanel(spec) {
                var showing = panel();
                if (!showing) { return; }
                if (goalShowing && !on) { return; }
                showing.series(spec);
            }

            function present() {
                var showing = panel();
                if (!points.length) {
                    // The list is drawn from the same walk the panel is fed, and
                    // for the same reason the panel is: how far along a point
                    // comes is the walk's answer, not a sum of the legs'.
                    drawList([]);
                    sayPlanning(null);
                    feedPanel(null);
                    return;
                }
                var shape = composeRoute();
                drawList(shape.stations || []);
                sayPlanning(shape);
                if (!showing) { return; }
                // **A route of one point has no legs and nothing to draw.**
                // Measured on a phone: the panel opened at 355 px for it, 42 %
                // of the screen for an empty chart, and the ground the reader
                // was trying to tap went with it. Not a narrow-screen rule —
                // there is nothing to draw on any screen — so the panel is told
                // there is nothing rather than told to be small.
                if (points.length < 2) { feedPanel(null); return; }
                feedPanel({label: 'planned route', figure: figuresOf(shape), shape: shape,
                                told: told(shape), plan: writable(),
                                // Which of the marks below the curve are where a
                                // stage changes hands. The panel draws the
                                // points; only the plan knows what they mean.
                              stages: cutsOf()});
            }

            function switchTo(want) {
                if (want === on) { return; }
                on = want;
                // Planning is read in this panel, so switching it on is the one
                // thing that takes the panel back from a goal's route.
                if (on) { goalShowing = false; }
                toggle.setAttribute('aria-pressed', on ? 'true' : 'false');
                var showing = panel();
                // While plan mode is on the map's clicks are its own, so the
                // panel stops answering them; the route is left drawn either
                // way, because switching off to look at something is not
                // throwing a plan away.
                if (showing) { showing.suspend(on); }
                // And the click-highlight lets go, for a harder reason than
                // tidiness: its only two ways out are a click on the line and a
                // click on empty ground, and from here on this handler owns
                // both. Left standing it would dim every line on the map for as
                // long as plan mode is on, with nothing a reader could do about
                // it. Not restored on the way out — it was a selection made by
                // clicking, and it is given up by planning.
                if (on && window.trailsHighlight) { window.trailsHighlight.clear(); }
                // Warmed here rather than at the first drag: a drag settles
                // inside a pointer event and cannot wait a microtask for a
                // payload that has been in the page since it loaded. Quietly,
                // because switching plan mode on is not yet a request to route
                // anything, and a page without a graph says so at the click.
                if (on && !held && window.trailsGraph) {
                    window.trailsGraph.ready.then(function (graph) {
                        held = graph;
                        // And the index a tap snaps to the line by, so the
                        // first tap pays for nothing but itself.
                        edgeIndex(graph);
                    }, function () { held = null; });
                }
                refresh();
            }

            status.addEventListener('click', function () {
                if (!on || !points.length) { return; }
                listOpen = !listOpen;
                refresh();
            });

            toggle.addEventListener('click', function () { switchTo(!on); });
            back.addEventListener('click', undo);
            fresh.addEventListener('click', function () {
                if (!points.length) { return; }
                // The legs are not touched: they follow from the points, and
                // relink is what works out that none of them is on the route any
                // more. The recording goes too — a waypoint anchored to a file
                // nobody is working from is a point looked up in the wrong
                // track — and the kept copy goes with the last point, because
                // nothing on the map is nothing to keep.
                applyEdit(function () {
                    points.length = 0;
                    chosen = -1;
                    loaded = null;
                    tourName = '';
                    loadSaid = '';
                });
            });

            // ---- the clicks --------------------------------------------------------
            // One handler for every click on the map, whatever it lands on.
            // Leaflet fires a layer's click for a line and the map's click only
            // for empty ground, so listening to either alone would miss half the
            // map — and a click reaching a line would open its popup as well.
            // Taken in the capture phase on the container and stopped there:
            // Leaflet's own listener sits on the same element in the bubble
            // phase and never runs.
            var pressed = null;
            var container = map.getContainer();

            // Whether a click landed on something that is not the ground.
            //
            // **A popup is not in the control container.** It lives in a pane
            // inside the map, so a handler that only steps around the controls
            // walks straight over it: measured, clicking the close button of a
            // chain's popup placed a waypoint behind it and left the popup open.
            // Everything inside a popup is the same case — a link, a name, the
            // text a reader is trying to select — because a popup is something
            // to read and not terrain to plan over.
            function overFurniture(event) {
                if (!event.target || !event.target.closest) { return false; }
                // **The chrome belongs in this list for the same reason the
                // popup did.** A handler that owns every click has to enumerate
                // everything that is not terrain, and the chrome is not in the
                // control container: it is appended to the map container itself,
                // so that a panel can cover the corners on a narrow screen.
                return !!event.target.closest('.leaflet-control-container, .leaflet-popup, .trails-chrome');
            }

            // **`pointerdown` and not `mousedown`.** A finger fires no
            // `mousedown` of its own: a browser may send a compatibility one
            // after the gesture ends, and may not — after a pan it usually does
            // not, which is the only reason a pan never placed a point. That is
            // an assumption about a browser rather than a rule this page keeps,
            // and it cannot be driven here: a synthetic `TouchEvent` produces no
            // compatibility events at all, so the very mechanism in question is
            // the one a check cannot reproduce.
            //
            // A pointer event fires for finger, mouse and pen alike, **at the
            // start of the gesture and before any compatibility event**, so the
            // three-pixel test below compares where the gesture began with where
            // it ended, whatever began it. The assumption is replaced rather
            // than tested.
            var pressEvent = window.PointerEvent ? 'pointerdown' : 'mousedown';
            container.addEventListener(pressEvent, function (event) {
                pressed = {x: event.clientX, y: event.clientY};
            }, true);

            container.addEventListener('click', function (event) {
                if (!on || overFurniture(event)) { return; }
                // **And not while a position is being picked or a goal set.**
                // Either switch owns
                // the next tap whatever else does -- it is the one thing on this
                // map that is meant to work in every mode -- so this yields
                // rather than stopping the click, and the chrome's own handler,
                // which is the next one in the capture phase, takes it.
                if (window.trailsChrome && window.trailsChrome.state &&
                        (window.trailsChrome.state().picking ||
                         window.trailsChrome.state().aiming)) { return; }
                // A pan ends in a click too. Leaflet drops that one for its own
                // listeners; this one is not Leaflet's, so how far the pointer
                // travelled is what tells the two apart.
                //
                // **`window.trailsReach`'s number and its arithmetic, not three
                // pixels and a different sum.** Leaflet starts dragging when
                // `|dx| + |dy|` reaches its threshold, and a finger is allowed
                // more of that than a mouse; keeping a separate 3 here would
                // mean a five-pixel roll moved nothing and was thrown away as a
                // pan all the same -- a tap that does nothing at all, which is
                // the defect `_TouchReach` exists to end.
                var slop = window.trailsReach ? window.trailsReach.slop() : 3;
                if (pressed && Math.abs(event.clientX - pressed.x) + Math.abs(event.clientY - pressed.y) >= slop) { return; }
                event.stopPropagation();
                // **Three things one click can mean, and they are told apart
                // here because nothing else ever sees the click.** The handler
                // is on the container in the capture phase and stops it there,
                // so a pin's own Leaflet click would never run and a mode or a
                // modifier would be a second thing for a reader to hold in mind.
                //
                // A pin first, because a pin sits on the route and the route
                // runs under it; then the route itself, within a few pixels of
                // the line as drawn; and anything else is a point on the end,
                // which is what a click has meant here since plan mode existed.
                var element = event.target && event.target.closest
                    ? event.target.closest('.trails-plan-pin') : null;
                var at = element ? pinFor(element) : -1;
                if (at >= 0) {
                    // Clicking the one already held lets go of it, so there is a
                    // way out that is not an edit.
                    chosen = chosen === at ? -1 : at;
                    refresh();
                    return;
                }
                var where = map.mouseEventToLatLng(event);
                var hit = onRoute(where.lat, where.lng);
                if (hit) { insert(hit.leg + 1, hit.lat, hit.lon, hit.trackAt); return; }
                place(where.lat, where.lng);
            }, true);

            // Two clicks place two points, which the button takes back one at a
            // time; zooming as well would leave the reader somewhere else too.
            container.addEventListener('dblclick', function (event) {
                if (!on || overFurniture(event)) { return; }
                if (window.trailsChrome && window.trailsChrome.state &&
                        (window.trailsChrome.state().picking ||
                         window.trailsChrome.state().aiming)) { return; }
                event.stopPropagation();
            }, true);

            // What the plan is, and the entry a click uses, the way the graph
            // arrives as window.trailsGraph and the panel's selection as
            // window.trailsProfile: so a browser check can drive it and read it
            // rather than screenshot it.
            // ---- the goal ---------------------------------------------------------
            // **A goal is not a plan.** A plan is a tour made beforehand, at a
            // table; a goal is a point set while walking, and the two stand side
            // by side -- setting one never touches the other, and a reader on a
            // planned route may still say *but first I want to get to that hut*.
            //
            // It lives in this control because the router does. The graph, the
            // snapping and `resolve` are all here, and a second copy of any of
            // them would be a second answer to the same question -- the rule
            // `layEdges` is exposed under, and the reason nothing else on this
            // page walks a route for itself.
            //
            // Two readings of one point, and not two modes: *direct* is the
            // bearing to it and *routed* is a way there over the network. The
            // point is the same either way, because which of the two a reader
            // wants changes on the ground -- routed in fog, direct with the
            // slope in front of them -- and having to set the goal again to say
            // so would be the page asking them to repeat themselves.
            var GOAL_COLOUR = '#00a152';
            //: How far off the line the reader has to have got before routing
            //: again is worth it, and how much of that is their own uncertainty:
            //: a fix that is 40 m vague reads as 40 m off a line it is standing
            //: on. Never under the floor, because a line drawn along a path is
            //: not the path to the metre.
            var GOAL_ASTRAY_M = 50;
            var GOAL_ASTRAY_SPREADS = 3;
            //: And at most this often. A fix arrives about once a second and
            //: each route is a search over the network; a line rebuilt whenever
            //: the fix shivered would shiver with it, and the distance left
            //: would stop counting down and start jittering.
            var GOAL_AGAIN_MS = 30000;
            //: How near counts as arrived: the circle the map is already drawing
            //: round the reader. Inside it there is no direction to give, which
            //: is the same rule the goal mark follows on a route.
            //: Whether this way to the goal has been shown yet. Set when a
            //: goal is *set*, and not on the routing that happens on its own as
            //: the reader walks: taking the panel from under somebody every half
            //: minute is not an answer, it is an interruption.
            var goalFresh = false;
            var goalAt = null, goalWay = 'direct';
            //: The stops the reader put between themselves and the goal, in the
            //: order they are to be walked. The goal is the last of them and is
            //: kept apart, because it is the one that can stand alone.
            var goalVia = [];
            var goalLegs = [], goalShape = null, goalLayers = [], goalMark = null;
            var goalPins = [];
            var goalFrom = null, goalWhen = 0, goalWorking = 0, goalToken = null;
            //: Whether the panel is showing the way to the goal rather than the
            //: plan. Both can be offered at once and only one of them is drawn.
            var goalShowing = false;

            function goalPane() {
                if (!map.getPane('trailsGoalRoute')) {
                    var made = map.createPane('trailsGoalRoute');
                    // Over the planned route at 460: a goal is the more
                    // particular of the two and the one the reader set last.
                    made.style.zIndex = 462;
                    // For the reason the plan's own pane gives: a line that took
                    // clicks would stand between a reader and the trail under it.
                    made.style.pointerEvents = 'none';
                }
                return 'trailsGoalRoute';
            }

            //: A target and not a pin: the waypoints are numbered discs because
            //: a route has an order, and a goal has nothing to be third of.
            function goalIcon() {
                return '<span style="display:block;width:100%;height:100%;box-sizing:border-box;' +
                    'border-radius:50%;border:3px solid ' + GOAL_COLOUR + ';background:' + CASING +
                    ';box-shadow:0 0 0 2px ' + CASING + ',0 0 0 4px ' + GOAL_COLOUR + '"></span>';
            }

            function paintGoalMark() {
                if (!goalAt) {
                    if (goalMark) { map.removeLayer(goalMark); goalMark = null; }
                    return;
                }
                if (!goalMark) {
                    goalMark = L.marker([goalAt.lat, goalAt.lon], {
                        icon: L.divIcon({className: 'trails-goal-mark', iconSize: [16, 16],
                                         iconAnchor: [8, 8], html: goalIcon()}),
                        keyboard: false, interactive: false, zIndexOffset: 1200
                    }).addTo(map);
                    return;
                }
                goalMark.setLatLng([goalAt.lat, goalAt.lon]);
            }

            function dropGoalLine() {
                undraw(goalLayers);
                goalLayers = [];
                goalLegs = [];
                goalShape = null;
            }

            //: Everywhere the reader has said they want to be, in order. The
            //: goal is the last of them; the ones before it are stops.
            function stopsOf() {
                return goalAt ? goalVia.concat([goalAt]) : [];
            }

            //: What a stop is called on the mark and in the row. A stop the map
            //: names is named; the rest are numbered, and the last of them is
            //: not a stop at all.
            function stopSaid(at) {
                var stops = stopsOf();
                if (at + 1 >= stops.length) { return stops[at] ? (stops[at].name || 'the goal') : 'the goal'; }
                return stops[at].name || ('Stop ' + (at + 1));
            }

            //: A small disc in the goal's own colour, numbered. Not the plan's
            //: pin, which is black and belongs to a route somebody is editing,
            //: and not the goal's target ring: a stop is on the way to
            //: something, which is what being numbered says.
            function stopIcon(at) {
                return '<span style="display:block;width:100%;height:100%;box-sizing:border-box;' +
                    'border-radius:50%;border:2px solid ' + GOAL_COLOUR + ';background:' + CASING +
                    ';color:' + GOAL_COLOUR + ';text-align:center;font:bold 9px/12px sans-serif">' +
                    (at + 1) + '</span>';
            }

            function paintStops() {
                while (goalPins.length > goalVia.length) { map.removeLayer(goalPins.pop()); }
                for (var at = 0; at < goalVia.length; at += 1) {
                    if (goalPins[at]) {
                        goalPins[at].setLatLng([goalVia[at].lat, goalVia[at].lon]);
                        goalPins[at].setIcon(L.divIcon({className: 'trails-goal-stop', iconSize: [16, 16],
                                                        iconAnchor: [8, 8], html: stopIcon(at)}));
                        continue;
                    }
                    goalPins.push(L.marker([goalVia[at].lat, goalVia[at].lon], {
                        icon: L.divIcon({className: 'trails-goal-stop', iconSize: [16, 16],
                                         iconAnchor: [8, 8], html: stopIcon(at)}),
                        keyboard: false, interactive: false, zIndexOffset: 1150
                    }).addTo(map));
                }
            }

            // **One leg between two places the reader named**, made the way the
            // reading they chose says. That is the whole of the difference
            // between the two now: *routed* is a way over the network and
            // *direct* is the straight line, and both are legs -- so the shape,
            // the profile, the row of choices and the mark all work on one
            // thing and not on two. Which also gives the straight reading a
            // profile it never had: a line across a mountainside is a climb
            // whether or not anybody laid a path along it.
            //
            // Not snapped where it is straight: a straight leg runs between the
            // places the reader put down, and moving one of them onto the
            // network would be routing without saying so.
            function goalLegBetween(graph, head, tail) {
                if (goalWay !== 'routed') { return walkTo(graph, head, tail, true); }
                // **Partly, which is the whole of the difference between a goal
                // and a plan's leg.** A leg is between two points a reader chose
                // and its file is written from what it is made of; a goal is
                // somewhere they want to get to, and *most of the way is a path*
                // is a better answer than *there is no way*.
                //
                // **And handed over raw.** A stop used to be snapped on the way
                // in, which moved the end of the way up to `snapM` from the mark
                // standing for it -- 67 m, measured, with the disc sitting in
                // open ground beside the line. A stop is a place the reader
                // chose; the walk from it to the path is part of the answer and
                // is drawn as what it is.
                return resolve(graph, placed(graph, head), placed(graph, tail), true, true);
            }

            // **Raw, and then asked once whether it stands on the line.** A
            // tap was moved on to the line by `onTheLine` and a place taken
            // from a popup was not, and the difference matters here: a point
            // standing on an edge is reached along that edge, one beside it
            // walks to it. Asked at `SAME_SPOT_M`, which finds the line under
            // a point put on it and nothing under one that was not -- the
            // position stays the reader's own either way.
            function placed(graph, point) {
                var at = snapped(graph, point.lat, point.lon, SAME_SPOT_M);
                return {lat: point.lat, lon: point.lon, node: at.node, edge: at.edge, along: at.along};
            }

            // **Worked out from where the reader is, which is the whole of what
            // a way to a goal means.** Not from the goal outwards and not from
            // where it was set: a way to somewhere starts where you are. The
            // stops between are theirs and do not move, so only the first leg
            // depends on the position -- but all of them are made together,
            // because a chain half rebuilt is two answers about one walk.
            function routeToGoal(from) {
                if (!goalAt || !from) { return; }
                goalFrom = {lat: from.lat, lon: from.lon};
                goalWhen = Date.now();
                goalWorking += 1;
                refreshGoal();
                var mine = {};
                // **One token and not a queue.** A reply about a way from ground
                // the reader has since left is not a shorter answer to the same
                // question, it is an answer to a question nobody asked -- and
                // this is the same one line that cancels a plan's leg.
                goalToken = mine;
                withGraph(function (graph) {
                    var chain = [{lat: from.lat, lon: from.lon}].concat(stopsOf());
                    var making = [];
                    for (var at = 0; at + 1 < chain.length; at += 1) {
                        making.push(oneLeg(graph, chain[at], chain[at + 1]));
                    }
                    Promise.all(making).then(function (legs) {
                        goalWorking -= 1;
                        if (goalToken !== mine) { return; }
                        undraw(goalLayers);
                        goalLegs = legs;
                        goalLayers = [];
                        legs.forEach(function (leg) {
                            if (!leg.parts) { return; }
                            goalLayers = goalLayers.concat(
                                draw(leg.parts, leg.provisional, {pane: goalPane(), colour: GOAL_COLOUR}));
                        });
                        var whole = legs.filter(function (leg) { return !!leg.parts; });
                        goalShape = whole.length === legs.length && legs.length
                            ? composeRoute(null, null, legs) : null;
                        // **A goal just worked out is what the reader is looking
                        // at.** They asked for it a second ago; a panel still
                        // showing whatever they were reading before is a page
                        // answering a question nobody has any more.
                        if (goalShape && goalFresh) { goalFresh = false; showGoalProfile(); }
                        refreshGoal();
                    });
                }, function () {});
            }

            //: A leg, and a refusal turned into a leg that says it failed --
            //: `Promise.all` would otherwise throw the whole chain away because
            //: one stop of five could not be reached.
            function oneLeg(graph, head, tail) {
                return Promise.resolve().then(function () {
                    return goalLegBetween(graph, head, tail);
                }).then(function (parts) {
                    return {from: head, to: tail, parts: parts, failed: null,
                            provisional: parts.some(function (part) { return part.provisional; })};
                }, function (failure) {
                    // **A leg that could not be worked out is still ground the
                    // reader has to cross.** Drawn straight with nothing claimed
                    // about it, which is what `plainParts` is, and still marked
                    // failed so the row says why -- where this used to hand back
                    // nothing at all, the way there had a hole in it and a stop
                    // was left standing in the middle of it. The plan wants the
                    // other reading and keeps it: see `resolve`.
                    var length = panel().metresBetween(head.lon, head.lat, tail.lon, tail.lat);
                    return {from: head, to: tail, parts: plainParts(head, tail, length),
                            provisional: false,
                            failed: String(failure && failure.message ? failure.message : failure)};
                });
            }

            // Whether the way there is worth working out again, asked on every
            // fix. **Only when the reader has left it**, because a route that is
            // still under their feet is still the answer -- and their own circle
            // is part of how far off they look, so a vague fix does not send
            // this off routing the same way twice.
            function goalStood(lat, lon, spread) {
                // **Whichever reading is standing.** A straight leg starts where
                // the reader was as surely as a routed one does, so it goes just
                // as stale when they walk -- and it is worked out again under
                // the same rule, at the same cost.
                if (!goalAt) { return false; }
                if (goalWorking > 0) { return false; }
                if (!goalShape) { return goalAgain({lat: lat, lon: lon}); }
                if (Date.now() - goalWhen < GOAL_AGAIN_MS) { return false; }
                var astray = Math.max(GOAL_ASTRAY_M, GOAL_ASTRAY_SPREADS * (spread || 0));
                var cosine = Math.cos(lat * Math.PI / 180);
                var away = Infinity;
                for (var i = 0; i + 1 < goalShape.lon.length; i += 1) {
                    if (goalShape.lon[i] === null || goalShape.lon[i + 1] === null) { continue; }
                    var near = goalNear(lat, lon, cosine, i);
                    if (near < away) { away = near; }
                }
                return away > astray ? goalAgain({lat: lat, lon: lon}) : false;
            }

            //: The gap to one segment of the composed way, flat, in the metre
            //: this page measures with. `onRoute` does the same sum over the
            //: plan's legs and answers a different question with it.
            function goalNear(lat, lon, cosine, at) {
                return awayFromLine(lat, lon, cosine, goalShape.lat[at], goalShape.lon[at],
                                    goalShape.lat[at + 1], goalShape.lon[at + 1]);
            }

            function goalAgain(from) {
                routeToGoal(from);
                return true;
            }

            //: Where the reader is, asked of the one thing on this page that
            //: knows -- the same figure the position ring is drawn at, which is
            //: not always the last fix that arrived.
            function goalHere() {
                var said = window.trailsChrome && window.trailsChrome.position
                    ? window.trailsChrome.position() : null;
                return said ? {lat: said.lat, lon: said.lon} : null;
            }

            // **A tap snaps, and nothing that is not a tap does.**
            //
            // The reach is a finger's width on the screen, which is the finest
            // a reader can point at the zoom they are looking at -- so a line
            // inside it is the line they were pointing at, and taking it as one
            // is not a guess. Zooming in is how they say otherwise: 48 m of
            // ground at z14, 12 m at z16, 3 m at z18, and the tiles here go to
            // 18. A hut beside a path is a choice a reader can make by
            // pinching, and one they cannot make while the two are eight pixels
            // apart.
            //
            // The same rule the plan's waypoints follow, and it is the same
            // `snapped` and the same `fingerReach` -- the goal lives in this
            // closure exactly so that there is one of each.
            //
            // **Third in a ladder of three**, not first. A named thing within
            // `namedM` wins, because a hut is a place and not a position; then
            // a line within a finger; then the tap as it fell. And a goal taken
            // from a place's popup is not a finger on the map at all -- the
            // reader pressed a button on something they were reading -- so it
            // arrives already named and snaps to nothing, as does one restored
            // from the last visit, which was snapped when it was set.
            //
            // Asked of the graph, so it lands a microtask after the tap rather
            // than in it. Where the graph never arrives the tap stands: a goal
            // set in a page that cannot route is still a goal, and this is the
            // only part of setting one that needs a graph.
            function onTheLine(lat, lon, then) {
                var asked = false;
                withGraph(function (graph) {
                    var at = snapped(graph, lat, lon, fingerReach(lat));
                    asked = true;
                    then(at.lat, at.lon);
                }, function () { if (!asked) { then(lat, lon); } });
            }

            // **A new goal is a new journey, so the stops go with the old
            // one.** They were put down on the way to somewhere; kept across a
            // change of destination they would be a detour nobody asked for,
            // and the reader would have to find and remove each of them.
            function setGoal(lat, lon, name, tapped) {
                if (tapped) {
                    onTheLine(lat, lon, function (at, on) { setGoal(at, on, name); });
                    return;
                }
                goalAt = {lat: lat, lon: lon, name: name || null};
                goalVia = [];
                goalFresh = true;
                dropGoalLine();
                goalToken = null;
                paintGoalMark();
                paintStops();
                routeToGoal(goalHere());
                keepGoal();
                refreshGoal();
            }

            // **A stop goes into the leg it is nearest, and there is always
            // one.** A reader putting a stop down means *and by way of here*,
            // and where in the order that falls is a fact about the ground
            // rather than something to be asked: the leg it lands nearest to is
            // the leg it belongs in. No reach and no threshold -- every point
            // has a nearest leg, which is what makes the answer always defined.
            function addStop(lat, lon, name, tapped) {
                if (!goalAt) { return false; }
                if (tapped) {
                    onTheLine(lat, lon, function (at, on) { addStop(at, on, name); });
                    return true;
                }
                goalVia.splice(legNearest(lat, lon), 0, {lat: lat, lon: lon, name: name || null});
                goalFresh = true;
                goalToken = null;
                paintStops();
                routeToGoal(goalHere());
                keepGoal();
                refreshGoal();
                return true;
            }

            //: Which leg of the way a position falls nearest to, as an index
            //: into the stops: leg *i* ends at stop *i*, so a stop inserted at
            //: *i* is walked before whatever was there.
            function legNearest(lat, lon) {
                if (!goalLegs.length) { return goalVia.length; }
                var cosine = Math.cos(lat * Math.PI / 180);
                var best = goalVia.length, closest = Infinity;
                for (var at = 0; at < goalLegs.length; at += 1) {
                    var parts = goalLegs[at].parts || [];
                    for (var p = 0; p < parts.length; p += 1) {
                        var part = parts[p];
                        for (var v = 0; v + 1 < part.lon.length; v += 1) {
                            var gap = awayFromLine(lat, lon, cosine, part.lat[v], part.lon[v],
                                                   part.lat[v + 1], part.lon[v + 1]);
                            if (gap < closest) { closest = gap; best = at; }
                        }
                    }
                }
                return Math.min(best, goalVia.length);
            }

            //: The gap from a position to one segment, flat, in the metre this
            //: page measures with. **The same sum `nearSegment` does**, which
            //: hands back the foot of the perpendicular as well -- only putting
            //: a point into a leg needs that, and three copies of one piece of
            //: arithmetic is three places for it to stop agreeing.
            function awayFromLine(lat, lon, cosine, aLat, aLon, bLat, bLon) {
                return nearSegment(lat, lon, cosine, aLat, aLon, bLat, bLon).away;
            }

            //: Which stop a position is standing on, or -1. The same reach a tap
            //: is judged by everywhere else on this page.
            function stopAt(lat, lon, withinPx) {
                var cosine = Math.cos(lat * Math.PI / 180);
                var reach = (withinPx || ON_ROUTE_PX) * 40075016.686 * cosine /
                    Math.pow(2, map.getZoom() + 8);
                for (var at = 0; at < goalVia.length; at += 1) {
                    var dx = (goalVia[at].lon - lon) * cosine, dy = goalVia[at].lat - lat;
                    if (Math.sqrt(dx * dx + dy * dy) * 111320 <= reach) { return at; }
                }
                return -1;
            }

            function dropStop(at) {
                if (at < 0 || at >= goalVia.length) { return false; }
                goalVia.splice(at, 1);
                goalToken = null;
                paintStops();
                routeToGoal(goalHere());
                keepGoal();
                refreshGoal();
                return true;
            }

            // **A stop put somewhere else is the same stop.** It keeps its
            // place in the order: the reader chose where it falls among the
            // others when they put it down, and a stop nudged fifty metres to
            // the far side of a stream has not changed which hut it is walked
            // to before. Which is what tells this apart from dropping one and
            // adding one, where `legNearest` would decide the order afresh.
            function moveStop(at, lat, lon, name, tapped) {
                if (at < 0 || at >= goalVia.length) { return false; }
                if (tapped) {
                    onTheLine(lat, lon, function (on, along) { moveStop(at, on, along, name); });
                    return true;
                }
                goalVia[at] = {lat: lat, lon: lon, name: name || null};
                goalToken = null;
                paintStops();
                routeToGoal(goalHere());
                keepGoal();
                refreshGoal();
                return true;
            }

            // **One place earlier or later, the way the plan's list does it.**
            // The order was worked out from the ground when the stop went
            // down, and the ground is sometimes wrong about which of two huts
            // a reader means to reach first. A swap with a neighbour is the
            // smallest gesture that changes it and composes into any order.
            function stepStop(at, step) {
                var to = at + step;
                if (at < 0 || at >= goalVia.length || to < 0 || to >= goalVia.length) { return false; }
                var moved = goalVia[at];
                goalVia[at] = goalVia[to];
                goalVia[to] = moved;
                goalToken = null;
                paintStops();
                routeToGoal(goalHere());
                keepGoal();
                refreshGoal();
                return true;
            }

            // **The goal put somewhere else, and the stops stay.** `setGoal`
            // is a new journey and clears them, which is right for a reader
            // who has changed their mind about where they are going; this is
            // for the one who has not, and wants the end of the same journey a
            // little further along the shore. Reported from the phone: with
            // stops on the way there was no way to nudge the goal without
            // finding and putting every one of them down again.
            function moveGoal(lat, lon, name, tapped) {
                if (!goalAt) { return false; }
                if (tapped) {
                    onTheLine(lat, lon, function (at, on) { moveGoal(at, on, name); });
                    return true;
                }
                goalAt = {lat: lat, lon: lon, name: name || null};
                goalToken = null;
                paintGoalMark();
                paintStops();
                routeToGoal(goalHere());
                keepGoal();
                refreshGoal();
                return true;
            }

            //: How far into the way each place comes, in the metre this page
            //: measures with: the sum of the legs up to it. Leg *i* ends at
            //: stop *i*, so the figure for a stop is the legs before and
            //: including its own. `null` where a leg is not made yet, because
            //: a partial sum said as a distance is a distance nobody walked.
            function metresInto() {
                var into = [], walked = 0;
                for (var at = 0; at < goalLegs.length; at += 1) {
                    var parts = goalLegs[at].parts;
                    if (walked === null || !parts) { walked = null; into.push(null); continue; }
                    for (var p = 0; p < parts.length; p += 1) {
                        var part = parts[p];
                        for (var v = 0; v + 1 < part.lon.length; v += 1) {
                            walked += panel().metresBetween(part.lon[v], part.lat[v], part.lon[v + 1], part.lat[v + 1]);
                        }
                    }
                    into.push(walked);
                }
                return into;
            }

            function clearGoal() {
                goalAt = null;
                goalVia = [];
                paintStops();
                goalToken = null;
                goalFrom = null;
                goalWhen = 0;
                dropGoalLine();
                paintGoalMark();
                if (goalShowing) { goalShowing = false; if (panel()) { panel().series(null); } }
                keepGoal();
                refreshGoal();
            }

            function setGoalWay(want) {
                var wanted = want === 'routed' ? 'routed' : 'direct';
                if (wanted === goalWay) { return goalWay; }
                goalWay = wanted;
                // **Both readings are worked out, because both are legs now.**
                // Straight used to mean *no line at all*, so switching to it
                // threw the way away and took the panel with it; it is the same
                // walk read a second way, and a reader switching wants to see
                // what that comes to.
                goalFresh = true;
                goalToken = null;
                routeToGoal(goalHere());
                keepGoal();
                refreshGoal();
                return goalWay;
            }

            // The way to the goal on the panel, which is the same call the plan
            // makes with its own route. **Not marked `plan`**: what that field
            // carries is a route a reader can write to a file with the points
            // they put down, and a goal has one point that is not theirs.
            function showGoal() {
                var showing = panel();
                if (!showing || !goalShape) { return false; }
                goalShowing = true;
                // **Named like a route, because it is drawn like one.** The
                // row of switches used to say the name and how many places the
                // way goes by; that row is a page now, and the heading is where
                // every other route on this panel says what it is. Two stops
                // turn a line into a journey, and a reader looking at 19 km
                // has to know whether that is the way there or the way there
                // by way of two huts.
                var byStops = goalVia.length ? ' \u00b7 by ' + goalVia.length + (goalVia.length === 1 ? ' stop' : ' stops') : '';
                showing.series({label: 'To ' + (goalAt.name || 'the goal') + byStops,
                                figure: figuresOf(goalShape), shape: goalShape,
                                told: told(goalShape), goal: true,
                                // The stations as the map marks them: a dot
                                // where the reader stands, the stops by their
                                // numbers, the goal as its ring.
                                marks: [{kind: 'start'}].concat(goalVia.map(function (stop, at) {
                                    return {kind: 'numbered', label: String(at + 1)};
                                }), [{kind: 'goal'}])});
                return true;
            }

            // The way there, on its own page, opened at the curve: the reader
            // asked *how do I get there*, and the profile is the half of that
            // answer the map cannot draw.
            function showGoalProfile() {
                if (!showGoal()) { return false; }
                var showing = panel();
                if (!showing || !showing.page) { return false; }
                showing.page(true);
                return showing.page('profile') === 'profile';
            }

            function refreshGoal() {
                if (goalShowing && goalShape) { showGoal(); }
                if (window.trailsChrome && window.trailsChrome.goal) {
                    window.trailsChrome.goal(goalState());
                }
            }

            function goalState() {
                return {at: goalAt ? {lat: goalAt.lat, lon: goalAt.lon} : null,
                        name: goalAt ? goalAt.name : null, way: goalWay,
                        working: goalWorking > 0,
                        // Whether there is a way there to point along, which is a
                        // different question from whether one was asked for: a
                        // routed goal off the network has none.
                        line: !!goalShape,
                        // Where the reader wants to be on the way, in order,
                        // with the goal last -- the same list the row at the
                        // foot counts and a check reads.
                        stops: (function () {
                            var into = metresInto(), all = stopsOf();
                            return all.map(function (stop, at) {
                                return {lat: stop.lat, lon: stop.lon, name: stopSaid(at),
                                        goal: at + 1 === all.length,
                                        // How far into the way it comes, which
                                        // is the one figure the list beside the
                                        // marks can say and the marks cannot.
                                        into: at < into.length ? into[at] : null};
                            });
                        })(),
                        // The first leg that could not be made, if any: one stop
                        // of five being unreachable is a fact about that stop
                        // and not about the journey.
                        failed: (goalLegs.filter(function (leg) { return leg.failed; })[0] || {}).failed || null,
                        from: goalFrom, metres: goalShape ? goalShape.total : null,
                        waterMetres: goalShape ? goalShape.crossed : null,
                        ascent: goalShape ? figuresOf(goalShape).ascent : null,
                        // **How much of it is not a path.** Where the network
                        // does not reach the goal, the way is routed as far as
                        // it does and drawn straight from there -- and a reader
                        // has to be told which part of what they are looking at
                        // was never a way. A line on a map is a promise, and
                        // this one is a promise only for the part that came off
                        // the network.
                        straight: goalShape ? (goalShape.straight + goalShape.crossed) : null,
                        // What the straight parts wade through, and the worst
                        // gradient on them alone: the path's own gradient is
                        // known ground, the line's is the question.
                        rivers: goalShape ? goalShape.rivers.map(riverSaid) : [],
                        steepest: (function () {
                            if (!goalShape || !panel()) { return null; }
                            var worst = panel().steepestOf(goalShape, true);
                            return isNaN(worst) ? null : Math.round(worst);
                        })()};
            }

            // **Whether a tap could have meant the way to the goal**, at the
            // same reach the panel asks of every other line under the finger --
            // the question `onRoute` answers for the plan, asked of this.
            //
            // Reported from the phone: without it the goal took *every* tap on
            // the map, wherever it landed, because the row offers it wherever it
            // runs and the row's own rule is that a line the reader made takes
            // the tap. A way tapped in order to be read was answered with the
            // goal, and the panel then said so under the wrong name.
            function nearGoal(lat, lon, withinPx) {
                if (!goalShape) { return false; }
                var cosine = Math.cos(lat * Math.PI / 180);
                var reach = (withinPx || ON_ROUTE_PX) * 40075016.686 * cosine /
                    Math.pow(2, map.getZoom() + 8);
                for (var i = 0; i + 1 < goalShape.lon.length; i += 1) {
                    if (goalShape.lon[i] === null || goalShape.lon[i + 1] === null) { continue; }
                    if (goalNear(lat, lon, cosine, i) <= reach) { return true; }
                }
                return false;
            }

            // **Every segment of the way there, leg by leg**, in the shape the
            // planned route hands its own out in -- and walked over the legs
            // rather than over the composed shape, because which leg a segment
            // belongs to is what says which stop lies at the end of it. The
            // composed shape has that boundary nowhere in it.
            //: And a leg of the way to a goal is never unsettled for long
            //: enough to matter: one that could not be worked out is drawn plain
            //: rather than handed back empty, so the fallback here is the empty
            //: list it used to need.
            function goalSegments(visit) {
                segmentsOf(goalLegs, function () { return []; }, visit);
            }

            //: And what lies at the end of one: leg *i* ends at stop *i*, and
            //: the last stop is the goal. Walking it the wrong way round is the
            //: only thing this has to answer differently, and then everything is
            //: behind you -- but a way to a goal has one direction, so the mark
            //: never asks.
            function goalEnd(leg, forward) {
                var stops = stopsOf();
                if (forward < 0 || leg < 0 || leg >= stops.length) { return null; }
                return {lat: stops[leg].lat, lon: stops[leg].lon, name: stopSaid(leg)};
            }

            function goalKeptKey() { return keptKey() + '.goal'; }

            function keepGoal() {
                try {
                    if (!goalAt) { window.localStorage.removeItem(goalKeptKey()); return; }
                    window.localStorage.setItem(goalKeptKey(), JSON.stringify(
                        {lat: goalAt.lat, lon: goalAt.lon, name: goalAt.name, way: goalWay,
                         // The stops with it, because a journey with stops in it
                         // is the journey: kept without them, a page rebuilt in
                         // a valley would quietly straighten the way out.
                         via: goalVia.map(function (stop) {
                             return {lat: stop.lat, lon: stop.lon, name: stop.name};
                         })}));
                } catch (blocked) { return; }
            }

            // **Kept, because a goal outlives the page it was set on.** A reader
            // sets one in a hut with a signal and reads it in the fog an hour
            // later, by which time the tab has been thrown away and rebuilt at
            // least once. Its own key beside the plan's, so restoring one cannot
            // touch the other.
            function restoreGoal() {
                var text = null;
                try { text = window.localStorage.getItem(goalKeptKey()); } catch (blocked) { return; }
                if (!text) { return; }
                var said = null;
                try { said = JSON.parse(text); } catch (broken) { return; }
                if (!said || typeof said.lat !== 'number' || typeof said.lon !== 'number') { return; }
                goalWay = said.way === 'routed' ? 'routed' : 'direct';
                setGoal(said.lat, said.lon, said.name || null);
                // After the goal, because setting one is what clears them: a new
                // destination is a new journey and the old stops go with it.
                (said.via || []).forEach(function (stop) {
                    if (typeof stop.lat === 'number' && typeof stop.lon === 'number') {
                        goalVia.push({lat: stop.lat, lon: stop.lon, name: stop.name || null});
                    }
                });
                if (goalVia.length) { paintStops(); routeToGoal(goalHere()); refreshGoal(); }
            }

            window.trailsGoal = {
                set: setGoal,
                clear: clearGoal,
                // A stop on the way, put into the leg it is nearest; and one
                // taken away again, by where it stands.
                addStop: addStop,
                dropStop: dropStop,
                // One put somewhere else, keeping its place in the order; one
                // swapped with a neighbour; and the goal put somewhere else
                // with the stops kept, which `set` deliberately does not do.
                moveStop: moveStop,
                stepStop: stepStop,
                move: moveGoal,
                stopAt: stopAt,
                stops: function () {
                    return goalVia.map(function (stop) {
                        return {lat: stop.lat, lon: stop.lon, name: stop.name};
                    });
                },
                // Read with no argument, set with one. The same shape the
                // profile's own scale switch answers in.
                way: function (want) { return want === undefined ? goalWay : setGoalWay(want); },
                // Routed again now, whatever the rule above would have said.
                again: function () { routeToGoal(goalHere()); return goalWorking > 0; },
                // Where the reader is standing, handed in by whoever has the
                // fix. Answers whether it set anything going, so a check can
                // wait for it rather than sleeping.
                stood: goalStood,
                state: goalState,
                segments: goalSegments,
                goal: goalEnd,
                near: nearGoal,
                // The way there as a shape, which `state()` deliberately does
                // not carry for the same reason the plan's own does not: it is
                // read on every check and by the chrome, and a route is not a
                // status. Handed out for whoever has to put a finger on it.
                line: function () {
                    return goalShape ? {lon: goalShape.lon, lat: goalShape.lat} : null;
                },
                show: showGoal,
                // And opened at the curve, which is what pressing the flag
                // with a goal standing does now.
                showProfile: showGoalProfile,
                showing: function () { return goalShowing; },
                //: Let go of the panel without clearing the goal: another line
                //: was chosen and this route is no longer what is drawn.
                letGo: function () { goalShowing = false; },
                restore: restoreGoal
            };

            window.trailsPlan = {
                place: place,
                // A whole route at once, from places somebody already put down;
                // and the way to the goal as one of those, which is what the
                // goal's page and the flag's own page hand over.
                fromPlaces: planFromPlaces,
                fromGoal: planFromGoal,
                undo: undo,
                // Read with no argument, set with one: the price of open
                // ground, ten to one or the build's three.
                stayOnPaths: stayOnPaths,
                kayak: paddle,
                // **What the row at the foot offers, and how it knows whether to
                // offer a choice.** The panel's own button writes the whole tour
                // -- one writer, asked from three places, as `saveWhole` says --
                // and an archive of stages is this one's to write; how many
                // stages there are is what decides whether asking is worth a
                // menu at all.
                saveStages: function () { return saveStages(); },
                stages: function () { return stagesOf().length; },
                // The route's own line, which is what a corridor of terrain is
                // kept along. `state()` answers everything else about a route
                // and deliberately not this: it is read on every check and by
                // the chrome, and two million coordinates is not a status.
                geometry: function () {
                    var shape = composeRoute();
                    return {lon: shape.lon, lat: shape.lat};
                },
                // Reading a file, which is the whole of phase 8's way in. It
                // takes the text rather than a File, so a browser check drives
                // exactly what the picker drives one step further on — the
                // FileReader is what turns one into the other and it was proved
                // before any of this was built.
                load: loadGpx,
                modes: MODES.map(function (mode) { return mode.key; }),
                // Reading a file without taking it, and the three steps the
                // picker drives: what it turned out to be and which mode is
                // offered first, then taking it or dropping it. A check reads
                // the answer rather than the screen, the way everything else on
                // this page is checked.
                offer: offerFile,
                take: function () {
                    if (!pendingFile) { throw new Error('no file is waiting to be taken'); }
                    takeGpx(pendingFile.read, pendingFile.mode);
                },
                choose: function (mode) {
                    if (!pendingFile) { throw new Error('no file is waiting to be taken'); }
                    if (!READINGS[pendingFile.kind][mode]) {
                        throw new Error(mode + ' is not one of ' +
                                        MODES.map(function (each) { return each.key; }).join(', '));
                    }
                    pendingFile.mode = mode;
                    refresh();
                },
                dismiss: dismissFile,
                readings: READINGS,
                // The four edits, each as the entry the gesture uses, so a
                // browser check can drive them and read what came out rather
                // than screenshot it. `dragTo` is what a drag does once the
                // pointer has been let go; that a waypoint can be dragged at all
                // is a thing only a real pointer over the icon proves, and the
                // check does both.
                insert: insert,
                remove: remove,
                moveTo: moveTo,
                moveBy: moveBy,
                dragTo: function (at, lat, lon) {
                    applyEdit(function (graph) {
                        if (at < 0 || at >= points.length) { return; }
                        // **A dragged waypoint is a new object on purpose** —
                        // that is what tells the legs beside it to rebuild — so
                        // anything the reader put on the old one has to be
                        // carried over by hand. Today that is the stage mark,
                        // and a mark lost by dragging a point would be lost
                        // silently, which is the worst way to lose one.
                        var was = points[at].stage;
                        points[at] = snapped(graph, lat, lon, fingerReach(lat));
                        if (was !== undefined) { points[at].stage = was; }
                        chosen = at;
                    });
                },
                select: function (at) {
                    chosen = (at === null || at === undefined || at < 0 || at >= points.length) ? -1 : at;
                    refresh();
                },
                // **The pins drawn again without the route being composed.**
                // Whether they are drawn depends on something outside this
                // control -- which route the panel is showing -- and `repaint`
                // would compose the whole route to find that out, 45 ms over a
                // long one, on every tap that changes a selection.
                dress: dressPins,
                // Which leg a position falls on, and where along it — the same
                // answer the click uses to decide that it means an insertion.
                onRoute: onRoute,
                // **How high one place is, off the same tiles a straight leg
                // reads.** The picker at the foot asks this. It could not ask
                // anything before: the only heights the page carried were the
                // ones sampled along the network, so a tap on open ground got
                // no number at all — and the height model is right here, cut
                // to the same grid as the map, kept by the same switch and
                // already decoded by this panel. One reader, one cache, one
                // surface; a second decoder on this page would be a second
                // answer to *how high is that*.
                //
                // `null` where the map has no raster of its own and a service
                // is asked per leg instead: a tap is not a leg, and a point
                // query over the network answers nothing at all offline.
                // Measured over 3,925 places in the Abisko box, the tiles
                // against the 4 m mosaic the build samples for the profile:
                // half agree within 0.07 m, 99 in 100 within 0.9 m, worst
                // 8.6 m on a cliff, where seven metres of pixel is the whole
                // difference. Two renderings of one surface, as §6.8 says.
                heightAt: PLAN.heightsTiles ? function (lat, lon) {
                    return tileHeights({lon: [lon], lat: [lat]}, true).then(function (points) {
                        var metres = points[0].height;
                        return isNaN(metres) ? null : metres;
                    });
                } : null,
                // **What this map already calls the ground under a point**, for
                // whoever is putting something there. A waypoint standing beside
                // a hut takes the hut's name and the hut's position; a goal set
                // by tapping one is the same question asked by somebody else,
                // and two answers to it would differ the day the register does.
                named: function (lat, lon) {
                    var said = nameOf({lat: lat, lon: lon}, 0, namedReach(lat));
                    return said.name ? {name: said.name, lat: said.lat, lon: said.lon,
                                        kind: said.kind, away: said.away} : null;
                },
                // **What the position mark measures itself against**, without
                // asking for the route as a shape. `segments` walks it and
                // `goal` names either end of a leg; together they are enough to
                // work out which way a reader has to walk and what lies that
                // way, and neither costs anything that is not walked anyway.
                segments: eachSegment,
                goal: placeAt,
                toggle: function (want) { switchTo(want === undefined ? !on : !!want); },
                // **Whether anything is still being worked out, cheaply.**
                // `state()` answers it too, but composing the whole route to
                // ask costs 45 ms over a 37 km one — and the one thing that
                // wants to ask is a check polling until it can carry on.
                busy: function () { return settling > 0; },
                // Drawn again without anything in the route having changed. The
                // chrome owns whether the profile is standing and this panel
                // draws that state, so the chrome has to be able to say so.
                repaint: refresh,
                // **Back onto the panel without going through plan mode.**
                // Reported: leaving plan mode leaves the route drawn and on the
                // panel, which is right -- and then one tap on any other line
                // took the panel for good, because this route's line is in a
                // pane that takes no clicks. The panel's row of choices offers
                // it wherever it runs and this is what that press calls;
                // switching plan mode on and off again was the only way back,
                // and it is a mode change to look at something.
                show: function () { present(); },
                // What is kept in this browser, so a check can read it without
                // knowing the key, and what writing it cost.
                kept: function () {
                    var text = null;
                    try { text = window.localStorage.getItem(keptKey()); } catch (blocked) { return null; }
                    if (text === null) { return null; }
                    return {key: keptKey(), bytes: text.length, ms: keptMs,
                            on: window.localStorage.getItem(keptKey() + '.on') === '1',
                            said: keptSaid};
                },
                keep: function () { writeKept(); },
                restore: restoreKept,
                forget: forgetKept,
                // The count is the list's handle inside this control, and the
                // panel's own row is its handle from outside one -- the list is
                // lent to that panel and read there. Both ask for the same thing
                // rather than each carrying their own idea of it.
                showList: function (want) {
                    listOpen = want === undefined ? !listOpen : !!want;
                    refresh();
                    return listShowing() && points.length > 0;
                },
                state: function () {
                    var shape = composeRoute();
                    return {
                        on: on, working: settling > 0, chosen: chosen, dragging: !!dragging,
                        // Every attempt at the height model since the page
                        // opened, the retries included: a check subtracts.
                        heightAsks: heightAsks,
                        // How many changes there are to step back through, so a
                        // check reads it rather than pressing the button to find
                        // out what pressing the button would do.
                        undoable: history.length,
                        // A file read and not yet taken, with what it turned out
                        // to be and which mode is standing. Null while no
                        // question is on the screen, which is the same thing the
                        // control reads to decide whether to draw one.
                        pending: pendingFile === null ? null : {
                            name: pendingFile.name, kind: pendingFile.kind, mode: pendingFile.mode,
                            waypoints: pendingFile.read.waypoints.length,
                            legs: pendingFile.read.legs.length,
                            says: READINGS[pendingFile.kind][pendingFile.mode]
                        },
                        // **With its stage mark**, which was left out and is
                        // part of what a point is: whether a stage ends here is
                        // the one thing about a waypoint that no position says,
                        // and a check reading this could not see it at all.
                        points: points.map(function (point) {
                            return {lat: point.lat, lon: point.lon, node: point.node, stage: point.stage,
                                    // The edge a point stands on part way
                                    // along, or -1: a tap on a long stretch
                                    // of trail is on the network without
                                    // being on a node.
                                    edge: point.edge === undefined ? -1 : point.edge,
                                    along: point.along === undefined ? null : point.along};
                        }),
                        // What the index over the edges cost to build, or null
                        // while nothing has asked for it.
                        indexMs: gridded ? gridded.buildMs : null,
                        legs: legs.map(function (leg) {
                            return {
                                settled: !!leg.parts, failed: leg.failed, provisional: leg.provisional,
                                // How many layers the leg has on the map. A
                                // leg that has settled and draws nothing is a
                                // hole in the route, and this is where a check
                                // sees one.
                                drawn: leg.layers.length,
                                parts: (leg.parts || []).map(function (part) {
                                    return {kind: part.kind, length: part.length, read: !!part.read,
                                            samples: part.height ? part.height.length : 0};
                                })
                            };
                        }),
                        walked: shape.total, crossings: shape.crossings, crossed: shape.crossed,
                        straight: shape.straight, read: shape.read, figure: figuresOf(shape),
                        // What the file states about the ground it covers, and
                        // the shape it is written from: a check can read these
                        // rather than parsing the file back, and then read the
                        // file to see that it says the same.
                        tally: shape.tally, stretches: shape.stretches.length,
                        vertices: shape.lon.length, samples: shape.height.length,
                        // Where each point the reader put down sits along the
                        // walk, which is what the profile marks them at.
                        stations: shape.stations,
                        writable: writable(),
                        // What was loaded and what it cost, so a check reads the
                        // figures rather than the status line they are written
                        // into. `index` is null until something asks for it,
                        // which is what says the index is built on demand and
                        // not at load.
                        loaded: loaded === null ? null : {
                            name: loaded.name, isRoute: loaded.isRoute, chain: loaded.chainId,
                            mode: loaded.mode, points: loaded.n, breaks: loaded.breaks,
                            waypoints: loaded.waypoints.length, generated: loaded.generated,
                            strange: loaded.strange,
                            legs: loaded.legs.length, unknown: loaded.unknown,
                            parseMs: loaded.parseMs, settleMs: loaded.settleMs,
                            said: loadSaid
                        },
                        index: gridded === null ? null : {
                            cellM: PLAN.indexCellM, buildMs: gridded.buildMs, entries: gridded.entries,
                            cells: gridded.cells, bytes: gridded.bytes
                        }
                    };
                }
            };

            // Plan mode lays its route out with the walk the profile panel
            // owns, so a page carrying one and not the other can plan nothing.
            // Said once, loudly, rather than thrown at the first click.
            if (panel()) {
                refresh();
                // **After the graph and not before it.** Reading the kept file
                // is parsing, and every leg of the plan is routed again on the
                // way in; both belong after the payload the page already waits
                // for rather than in front of a reader watching it load.
                if (window.trailsGraph) {
                    window.trailsGraph.ready.then(function () { restoreKept(); restoreGoal(); refreshGoal(); },
                                                  function () {});
                } else {
                    restoreKept();
                    restoreGoal();
                    refreshGoal();
                }
            } else {
                console.error('plan mode: there is no profile panel in this page, so nothing can be planned');
                toggle.disabled = true;
                toggle.textContent = 'Plan a route';
                back.style.display = 'none';
                edits.style.display = 'none';
                hint.style.display = 'none';
                status.style.display = '';
                say('There is no profile panel in this page, so nothing can be planned.');
            }
        })();

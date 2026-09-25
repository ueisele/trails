// Scalar original midpoints, independent of production uniform-square skips.
function referenceConnectorPrice(graph, aLon, aLat, bLon, bLat) {
    const length = panel().metresBetween(aLon, aLat, bLon, bLat);
    const ground = offPath() * (kayak() ? PLAN.portageFactor : 1);
    const waterPrice = kayak() ? openWaterFactor(graph) : PLAN.waterFactor;
    if (!graph.water || (!kayak() && !(waterPrice > ground))) return {cost: length * ground, land: kayak() ? length * offPath() : 0};
    const pieces = Math.max(1, Math.ceil(length / graph.water.cellM));
    let wet = 0;
    for (let i = 0; i < pieces; i++) {
        const t = (i + 0.5) / pieces;
        const lon = aLon + t * (bLon - aLon), lat = aLat + t * (bLat - aLat);
        if (graph.waterAt(lon, lat) && !(kayak() && graph.damAt && graph.damAt(lon, lat))) wet++;
    }
    const water = length * wet / pieces;
    return {cost: (length - water) * ground + water * waterPrice, land: kayak() ? length * (pieces - wet) / pieces * offPath() : 0};
}
// Eager exit prices, an exhaustive reverse Dijkstra, then a separate exhaustive
// entry scan. No direct-way ceiling, dry floor or incumbent cuts off work.
function referenceJoined(graph, from, to) {
    const work = router(graph), n = graph.header.nodes;
    const cost = new Float64Array(n).fill(Infinity), land = new Float64Array(n).fill(Infinity);
    const via = new Int32Array(n).fill(-1), next = new Int32Array(n).fill(-1);
    const heap = new Heap(), targets = endsOf(graph, to, true);
    let exitPrices = 0, entryPrices = 0;
    function seed(node, price) {
        if (cheaper(price.land, price.cost, land[node], cost[node])) {
            land[node] = price.land; cost[node] = price.cost;
            heap.push(node, price.cost, price.land);
        }
    }
    if (targets.length) {
        for (const target of targets) seed(target.node, target);
    } else {
        for (let node = 0; node < n; node++) {
            exitPrices++;
            seed(node, referenceConnectorPrice(graph, graph.nodeLon[node], graph.nodeLat[node], to.lon, to.lat));
        }
    }
    let pops = 0;
    const bound = 2 * n + 2 * graph.header.edges + 1;
    while (heap.node.length) {
        if (++pops > bound) throw new Error('reference search exceeds its graph bound');
        const taken = heap.pop();
        if (cheaper(land[taken.node], cost[taken.node], taken.land, taken.cost)) continue;
        for (let arc = work.at[taken.node]; arc < work.at[taken.node + 1]; arc++) {
            const edge = work.arc[arc];
            if (!allowed(graph, edge, graph.toNode[edge] === taken.node)) continue;
            const other = graph.fromNode[edge] === taken.node ? graph.toNode[edge] : graph.fromNode[edge];
            const c = taken.cost + work.cost[edge], l = taken.land + work.land[edge];
            if (cheaper(l, c, land[other], cost[other])) {
                cost[other] = c; land[other] = l; via[other] = edge; next[other] = taken.node;
                heap.push(other, c, l);
            }
        }
    }
    const direct = referenceConnectorPrice(graph, from.lon, from.lat, to.lon, to.lat);
    let answer = {...direct, head: -1};
    function enter(node, price) {
        const l = price.land + land[node], c = price.cost + cost[node];
        if (cheaper(l, c, answer.land, answer.cost)) answer = {land: l, cost: c, head: node};
    }
    const starts = endsOf(graph, from);
    if (starts.length) {
        for (const start of starts) enter(start.node, start);
    } else {
        for (let node = 0; node < n; node++) {
            entryPrices++;
            enter(node, referenceConnectorPrice(graph, from.lon, from.lat, graph.nodeLon[node], graph.nodeLat[node]));
        }
    }
    const edges = [];
    let tail = answer.head;
    for (let step = 0; tail >= 0 && via[tail] >= 0; step++) {
        if (step >= graph.header.edges) throw new Error('reference route exceeds its graph bound');
        edges.push(via[tail]); tail = next[tail];
    }
    return {...answer, tail, edges, exitPrices, entryPrices, pops};
}
function chosenLabel(graph, from, to, chosen) {
    if (!chosen) return {...connectorPrice(graph, from.lon, from.lat, to.lon, to.lat), head: -1, tail: -1, edges: []};
    const work = router(graph);
    const entry = endsOf(graph, from).find(end => end.node === chosen.head &&
        (!chosen.headCut || (end.cut && end.cut.edge === chosen.headCut.edge &&
            end.cut.from === chosen.headCut.from && end.cut.to === chosen.headCut.to)))
        || connectorPrice(graph, from.lon, from.lat, graph.nodeLon[chosen.head], graph.nodeLat[chosen.head]);
    return {land: entry.land + work.bestLand[chosen.head], cost: entry.cost + work.best[chosen.head],
        head: chosen.head, tail: chosen.tail, edges: chosen.over ? chosen.over.edges : []};
}

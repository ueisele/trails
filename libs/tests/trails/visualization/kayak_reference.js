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
// An independent, exhaustive geometry scan. No production index, nearest
// bracket, candidate array, dry floor or incumbent is used here.
function referenceSegments(graph, point) {
    const w = router(graph), far = panel().metresBetween, segments = [];
    let nearest = Infinity;
    // Each edge's vertices are visited once. The conservative coordinate box
    // only avoids minimising segments already farther than a known point;
    // it cannot exclude a closer point or a segment within d + 250 m.
    let maxLat = Math.abs(point.lat);
    for (let v = 1; v < graph.coordinates.length; v += 2) maxLat = Math.max(maxLat, Math.abs(graph.coordinates[v]));
    const sx = far(0, maxLat, 1, maxLat), sy = far(0, -0.001, 0, 0.001) / 0.002;
    function distance(a, b) {
        const dx = b[0] - a[0], dy = b[1] - a[1];
        const at = t => far(point.lon, point.lat, a[0] + t * dx, a[1] + t * dy);
        // Golden-section minimisation, independently of production's ternary
        // bracket. Both endpoints are retained for the clamped minimum.
        const ratio = (Math.sqrt(5) - 1) / 2;
        let lo = 0, hi = 1, l = 1 - ratio, r = ratio, dl = at(l), dr = at(r);
        for (let step = 0; step < 64; step++) {
            if (dl < dr) { hi = r; r = l; dr = dl; l = hi - ratio * (hi - lo); dl = at(l); }
            else { lo = l; l = r; dl = dr; r = lo + ratio * (hi - lo); dr = at(r); }
        }
        return Math.min(at(0), at(1), dl, dr);
    }
    for (let e = 0; e < graph.header.edges; e++) {
        if (!Number.isFinite(w.cost[e]) || !w.length[e]) continue;
        let along = 0;
        for (let v = graph.vertexAt[e]; v + 1 < graph.vertexAt[e + 1]; v++) {
            const a = [graph.coordinates[2 * v], graph.coordinates[2 * v+1]];
            const b = [graph.coordinates[2 * v+2], graph.coordinates[2 * v+3]];
            const x = Math.max(0, Math.min(a[0], b[0]) - point.lon, point.lon - Math.max(a[0], b[0]));
            const y = Math.max(0, Math.min(a[1], b[1]) - point.lat, point.lat - Math.max(a[1], b[1]));
            const lower = Math.hypot(x * sx, y * sy);
            const segment = {e, v, a, b, along, lower};
            if (lower <= nearest) { segment.distance = distance(a, b); nearest = Math.min(nearest, segment.distance); }
            // The final nearest distance can only decrease. A segment whose
            // box is already beyond this radius cannot enter the final set.
            if (lower <= nearest + 250) segments.push(segment);
            along += far(...a, ...b);
        }
    }
    const radius = nearest + 250;
    return segments.filter(s => s.lower <= radius && (s.distance === undefined ? distance(s.a, s.b) : s.distance) <= radius);
}

function referenceMiddle(graph, point, exit) {
    const w = router(graph), far = panel().metresBetween, g = offPath(), out = [];
    const scale = [far(point.lon, point.lat, point.lon + .001, point.lat) / .001,
        far(point.lon, point.lat, point.lon, point.lat + .001) / .001];
    for (const segment of referenceSegments(graph, point)) {
        const {e, v, a, b, along} = segment, f = (kayak() ? w.land[e] : w.cost[e]) / w.length[e];
        const dx = (b[0] - a[0]) * scale[0], dy = (b[1] - a[1]) * scale[1], span = Math.hypot(dx, dy);
        if (!span) continue;
        const px = (point.lon - a[0]) * scale[0], py = (point.lat - a[1]) * scale[1];
        const foot = (px * dx + py * dy) / span, gap = Math.abs(px * dy - py * dx) / span;
        let previous = null;
        for (const sign of [-1, 1]) {
            if (!allowed(graph, e, exit ? sign < 0 : sign > 0)) continue;
            const t = f < g ? Math.max(0, Math.min(1, (foot + sign * gap * f / Math.sqrt(g * g - f * f)) / span)) : (sign > 0 ? 1 : 0);
            const lon = a[0] + t * (b[0] - a[0]), lat = a[1] + t * (b[1] - a[1]);
            const distance = along + far(a[0], a[1], lon, lat);
            if (distance === 0 || distance === w.length[e]) continue;
            if (previous && previous.lon === lon && previous.lat === lat && previous.along === distance) continue;
            previous = {lon, lat, along: distance};
            const price = exit ? referenceConnectorPrice(graph, lon, lat, point.lon, point.lat)
                : referenceConnectorPrice(graph, point.lon, point.lat, lon, lat);
            out.push({edge: e, vertex: v, along: distance, lon, lat, price});
        }
    }
    return out;
}

// The browser audit may memoise midpoint counts between switch settings;
// the standalone tests price every node connector with the scalar loop.
function referenceNodePrice(graph, point, node, exiting) {
    return exiting
        ? referenceConnectorPrice(graph, graph.nodeLon[node], graph.nodeLat[node], point.lon, point.lat)
        : referenceConnectorPrice(graph, point.lon, point.lat, graph.nodeLon[node], graph.nodeLat[node]);
}

// Eager exit prices, an exhaustive reverse Dijkstra, then a separate exhaustive
// entry scan. No direct-way ceiling, dry floor or incumbent cuts off work.
function referenceJoined(graph, from, to) {
    const work = router(graph), n = graph.header.nodes;
    const cost = new Float64Array(n).fill(Infinity), land = new Float64Array(n).fill(Infinity);
    const via = new Int32Array(n).fill(-1), next = new Int32Array(n).fill(-1);
    const carry = new Float64Array(n), tails = new Array(n);
    const dryEdge = (edge, length) => {
        const kind = graph.header.sources[graph.sources[edge]].kind;
        return kind === PADDLE || kind === CROSSING ? 0 : length;
    };
    const dryConnector = (a, b, price) => kayak() ? price.land / offPath() : panel().metresBetween(a.lon, a.lat, b.lon, b.lat);
    const heap = new Heap(), targets = endsOf(graph, to, true);
    let exitPrices = 0, entryPrices = 0;
    const starts = endsOf(graph, from);
    const entries = starts.length ? [] : referenceMiddle(graph, from, false);
    const exits = targets.length ? [] : referenceMiddle(graph, to, true);
    function seed(node, price, metres, point = null) {
        if (cheaper(price.land, price.cost, land[node], cost[node])) {
            land[node] = price.land; cost[node] = price.cost; carry[node] = metres; tails[node] = point;
            heap.push(node, price.cost, price.land);
        }
    }
    if (targets.length) {
        for (const target of targets) {
            seed(target.node, target, target.cut ? dryEdge(target.cut.edge, Math.abs(target.cut.to - target.cut.from)) : 0);
        }
    } else {
        for (let node = 0; node < n; node++) {
            exitPrices++;
            const at = {lon: graph.nodeLon[node], lat: graph.nodeLat[node]}, price = referenceNodePrice(graph, to, node, true);
            seed(node, price, dryConnector(at, to, price));
        }
    }
    for (const point of exits) {
        for (const side of [0, 1]) {
            if (!allowed(graph, point.edge, side === 0)) continue;
            const length = wLength(point), partial = side ? length - point.along : point.along;
            seed(side ? graph.toNode[point.edge] : graph.fromNode[point.edge], {
                land: point.price.land + partial * work.land[point.edge] / length,
                cost: point.price.cost + partial * work.cost[point.edge] / length},
                dryConnector(point, to, point.price) + dryEdge(point.edge, partial), point);
        }
    }
    function wLength(point) { return work.length[point.edge]; }
    let pops = 0;
    // Each seed pushes at most once, each directed arc relaxes at most
    // once after its origin settles. This counts the full candidate set,
    // independently of the production queues and incumbent.
    const bound = n + targets.length + 2 * exits.length + 2 * graph.header.edges + 1;
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
                carry[other] = carry[taken.node] + dryEdge(edge, work.length[edge]); tails[other] = tails[taken.node];
                heap.push(other, c, l);
            }
        }
    }
    const direct = referenceConnectorPrice(graph, from.lon, from.lat, to.lon, to.lat);
    let answer = {...direct, head: -1, carry: dryConnector(from, to, direct), entry: null, exit: null};
    function enter(node, price, metres, point = null) {
        const l = price.land + land[node], c = price.cost + cost[node];
        if (cheaper(l, c, answer.land, answer.cost)) {
            answer = {land: l, cost: c, head: node, carry: metres + carry[node], entry: point, exit: tails[node]};
        }
    }
    if (starts.length) {
        for (const start of starts) {
            enter(start.node, start, start.cut ? dryEdge(start.cut.edge, Math.abs(start.cut.to - start.cut.from)) : 0);
        }
    } else {
        for (let node = 0; node < n; node++) {
            entryPrices++;
            const at = {lon: graph.nodeLon[node], lat: graph.nodeLat[node]}, price = referenceNodePrice(graph, from, node, false);
            enter(node, price, dryConnector(from, at, price));
        }
    }
    for (const point of entries) {
        for (const side of [0, 1]) {
            if (!allowed(graph, point.edge, side === 1)) continue;
            const length = wLength(point), partial = side ? length - point.along : point.along;
            enter(side ? graph.toNode[point.edge] : graph.fromNode[point.edge], {
                land: point.price.land + partial * work.land[point.edge] / length,
                cost: point.price.cost + partial * work.cost[point.edge] / length},
                dryConnector(from, point, point.price) + dryEdge(point.edge, partial), point);
        }
    }
    // Brute-force pairs on a shared edge cover the piece that never visits a
    // real node. This deliberately does not use production's ordered sweep.
    const sourcePoints = starts.length ? (from.edge >= 0 ? [{...from, price: {land: 0, cost: 0}}] : []) : entries;
    const targetPoints = targets.length ? (to.edge >= 0 ? [{...to, price: {land: 0, cost: 0}}] : []) : exits;
    const byEdge = new Map();
    for (const point of targetPoints) {
        if (!byEdge.has(point.edge)) byEdge.set(point.edge, []);
        byEdge.get(point.edge).push(point);
    }
    for (const start of sourcePoints) for (const end of byEdge.get(start.edge) || []) {
        if (!allowed(graph, start.edge, end.along >= start.along)) continue;
        const partial = Math.abs(end.along - start.along), length = work.length[start.edge];
        const l = start.price.land + partial * work.land[start.edge] / length + end.price.land;
        const c = start.price.cost + partial * work.cost[start.edge] / length + end.price.cost;
        if (cheaper(l, c, answer.land, answer.cost)) {
            answer = {land: l, cost: c, head: -1,
                carry: (starts.length ? 0 : dryConnector(from, start, start.price)) + dryEdge(start.edge, partial) +
                    (targets.length ? 0 : dryConnector(end, to, end.price)),
                entry: starts.length ? null : start, exit: targets.length ? null : end};
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
    if (chosen.land !== undefined) return {...chosen, edges: chosen.over ? chosen.over.edges : []};
    const work = router(graph);
    const entry = endsOf(graph, from).find(end => end.node === chosen.head &&
        (!chosen.headCut || (end.cut && end.cut.edge === chosen.headCut.edge &&
            end.cut.from === chosen.headCut.from && end.cut.to === chosen.headCut.to)))
        || connectorPrice(graph, from.lon, from.lat, graph.nodeLon[chosen.head], graph.nodeLat[chosen.head]);
    return {land: entry.land + work.bestLand[chosen.head], cost: entry.cost + work.best[chosen.head],
        head: chosen.head, tail: chosen.tail, edges: chosen.over ? chosen.over.edges : []};
}

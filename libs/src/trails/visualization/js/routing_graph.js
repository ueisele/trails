        (function () {
            var header = {{ this.header_json }};
            var encoded = {{ this.data_json }};

            // A cursor over the inflated stream. Every count it needs is either
            // in the header or in a section it has already read, so it runs
            // straight through and never seeks.
            function Cursor(bytes) { this.bytes = bytes; this.at = 0; }

            // Deliberately arithmetic rather than bitwise: JavaScript's shifts
            // truncate to 32 bits, and a value that overflowed that would come
            // back quietly wrong instead of loudly.
            Cursor.prototype.varint = function () {
                var value = 0, scale = 1, byte;
                do {
                    byte = this.bytes[this.at]; this.at += 1;
                    value += (byte & 0x7f) * scale;
                    scale *= 128;
                } while (byte & 0x80);
                return value;
            };

            Cursor.prototype.zigzag = function () {
                var value = this.varint();
                return value % 2 === 0 ? value / 2 : -(value + 1) / 2;
            };

            Cursor.prototype.take = function (count) {
                var out = this.bytes.slice(this.at, this.at + count);
                this.at += count;
                return out;
            };

            function bytesOf(text) {
                var binary = atob(text);
                var out = new Uint8Array(binary.length);
                for (var i = 0; i < binary.length; i += 1) { out[i] = binary.charCodeAt(i); }
                return out;
            }

            function inflate(bytes) {
                if (typeof DecompressionStream === 'undefined') {
                    return Promise.reject(new Error('this browser cannot inflate gzip'));
                }
                var stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
                return new Response(stream).arrayBuffer().then(function (buffer) { return new Uint8Array(buffer); });
            }

            function decode(bytes) {
                var cursor = new Cursor(bytes);
                var edges = header.edges, chains = header.chains, i;

                var lengths = new Int32Array(chains);
                for (i = 0; i < chains; i += 1) { lengths[i] = cursor.varint(); }
                var text = new TextDecoder('utf-8');
                var chainIds = new Array(chains);
                // Without a prototype, so that a lookup answers for the chain
                // ids and for nothing else. A plain object would hand back
                // Object's own members for names like "constructor".
                var chainOf = Object.create(null);
                for (i = 0; i < chains; i += 1) {
                    chainIds[i] = text.decode(cursor.take(lengths[i]));
                    chainOf[chainIds[i]] = i;
                }

                // Where each chain's edges begin. They are contiguous and in the
                // chain's own order, which is the whole reason the payload is
                // laid out this way: the frame order the graph is built in is
                // not the order the edges lie in, and one chain in five does not
                // even join up in it.
                var chainAt = new Int32Array(chains + 1);
                for (i = 0; i < chains; i += 1) { chainAt[i + 1] = chainAt[i] + cursor.varint(); }

                var flags = cursor.take(edges);
                var oneWay = header.oneWay ? cursor.take(edges) : new Uint8Array(edges);
                var fromNode = new Int32Array(edges), toNode = new Int32Array(edges);
                var tail = 0;
                for (i = 0; i < edges; i += 1) {
                    // The node an edge starts at along its chain, then the one it
                    // ends at. Which of from and to holds which depends on the
                    // way round the edge runs, so the flag puts them back.
                    var head = tail + cursor.zigzag();
                    tail = head + cursor.zigzag();
                    fromNode[i] = (flags[i] & 1) ? tail : head;
                    toNode[i] = (flags[i] & 1) ? head : tail;
                }

                var sources = cursor.take(edges);

                // What a planned route sums beside its length. waymarked
                // indexes header.waymarked, whose first entry is null and means
                // the edge was never asked — a crossing, or a connector nobody
                // drew. That is not the same as 'unknown', which means it was
                // asked and no source answered, and the two must not be added
                // together. noPathRecorded says no source records a path along
                // the edge; it does NOT say there is no path, and any text
                // showing it has to say the same.
                var derived = cursor.take(edges);
                var waymarked = new Uint8Array(edges), noPathRecorded = new Uint8Array(edges);
                for (i = 0; i < edges; i += 1) {
                    waymarked[i] = derived[i] & 0x03;
                    noPathRecorded[i] = (derived[i] & header.noPathBit) ? 1 : 0;
                }

                // The third field, which is a length and not a flag: how much of
                // the edge lies inside each protected area it meets, in the
                // order header.protected lists them. Most edges say 'none' in
                // one byte. **A crossing says 'none' as well and means
                // something else** — there is no walking distance under a
                // ferry, so it was never asked — and nothing here may read this
                // for one; the kind is what tells them apart, as it does for
                // waymarked, where the payload can afford a code of its own and
                // here it cannot.
                var protectedAt = new Int32Array(edges + 1);
                var areaOf = [], areaShare = [];
                var shareStep = header.protectedShareQuantum;
                for (i = 0; i < edges; i += 1) {
                    var meets = cursor.varint();
                    for (var a = 0; a < meets; a += 1) {
                        areaOf.push(cursor.take(1)[0]);
                        // A share of the edge, not a length. Python measured
                        // these metres in the projection the graph is built in
                        // and this page measures its own from the ellipsoid;
                        // multiplied by the length measured here, a route can
                        // never state more ground inside an area than it walked.
                        areaShare.push(cursor.varint() * shareStep);
                    }
                    protectedAt[i + 1] = protectedAt[i] + meets;
                }
                var protectedArea = Uint8Array.from(areaOf), protectedShare = Float64Array.from(areaShare);

                var vertexAt = new Int32Array(edges + 1);
                for (i = 0; i < edges; i += 1) { vertexAt[i + 1] = vertexAt[i] + cursor.varint(); }
                var coordinates = new Float64Array(2 * header.vertices);
                var quantum = header.coordinateQuantum, lon = 0, lat = 0;
                for (i = 0; i < header.vertices; i += 1) {
                    lon += cursor.zigzag();
                    lat += cursor.zigzag();
                    coordinates[2 * i] = lon * quantum;
                    coordinates[2 * i + 1] = lat * quantum;
                }

                var sampleAt = new Int32Array(edges + 1);
                for (i = 0; i < edges; i += 1) { sampleAt[i + 1] = sampleAt[i] + cursor.varint(); }
                // Single precision, and the bound is worth stating because the
                // grid is a centimetre: a float32 near v is wrong by at most
                // v / 2**24, so a centimetre stays recoverable up to 83 km of
                // altitude — four orders of magnitude above this ground. That
                // halves what the series costs in memory. The coordinates get
                // double precision, where a millionth of a degree needs it.
                var heights = new Float32Array(header.samples);
                var step = header.elevationQuantum, height = 0;
                for (i = 0; i < header.samples; i += 1) {
                    var code = cursor.varint();
                    if (code === 0) {
                        // Nothing was read here, and it must not become a number:
                        // a profile that fills a gap invents ground, and a climb
                        // counted across one invents a hill.
                        heights[i] = NaN;
                        continue;
                    }
                    code -= 1;
                    height += code % 2 === 0 ? code / 2 : -(code + 1) / 2;
                    heights[i] = height * step;
                }

                // Reading past the end of the stream yields undefined, which
                // masks to zero and ends a varint quietly, so a truncated
                // payload decodes to plausible numbers rather than to an error.
                // The layout accounts for every byte, so this says the whole of
                // it was read and nothing beyond it.
                if (cursor.at !== bytes.length) {
                    throw new Error('read ' + cursor.at + ' of ' + bytes.length + ' bytes');
                }

                // Node positions come off the edge endpoints rather than a table
                // of their own, so they cannot disagree with the geometry and
                // cost nothing in the payload.
                var nodeLon = new Float64Array(header.nodes), nodeLat = new Float64Array(header.nodes);
                for (i = 0; i < edges; i += 1) {
                    var first = 2 * vertexAt[i], last = 2 * (vertexAt[i + 1] - 1);
                    nodeLon[fromNode[i]] = coordinates[first];
                    nodeLat[fromNode[i]] = coordinates[first + 1];
                    nodeLon[toNode[i]] = coordinates[last];
                    nodeLat[toNode[i]] = coordinates[last + 1];
                }

                return {
                    header: header,
                    // Composing a chain runs its edges from chainAt[c] to
                    // chainAt[c + 1], reversing the geometry and the heights of
                    // any edge whose flag bit 0 is set, dropping the first
                    // sample and vertex of every edge but the first — the node
                    // between two edges is sampled by both — and breaking rather
                    // than joining wherever bit 1 says a new stretch begins.
                    chainIds: chainIds, chainOf: chainOf, chainAt: chainAt, flags: flags,
                    fromNode: fromNode, toNode: toNode, sources: sources, oneWay: oneWay,
                    waymarked: waymarked, noPathRecorded: noPathRecorded,
                    protectedAt: protectedAt, protectedArea: protectedArea, protectedShare: protectedShare,
                    vertexAt: vertexAt, coordinates: coordinates,
                    sampleAt: sampleAt, heights: heights,
                    nodeLon: nodeLon, nodeLat: nodeLat,
                    nearestNode: nearestNode.bind(null, nodeLon, nodeLat)
                };
            }

            // Nothing lies in a protected area far more often than something
            // does, so the answer for that case is one shared array rather than
            // a new one per position: this is asked once per height sample
            // along a leg drawn straight, and once per point of an exported
            // track.
            var NOWHERE = [];

            // Which protected areas a position lies in, by their place in
            // header.protected. **Even-odd over every ring of an area, its
            // holes among them**: in a valid multipolygon a point inside a hole
            // is enclosed by an even number of rings and so comes out outside,
            // and a point in any of several disjoint parts comes out inside. So
            // there is no outer-and-inner structure here to keep in step with
            // itself, and a boundary that gains an island needs no new case.
            //
            // The box first, because it settles thirty of the thirty-one areas
            // in four comparisons, and only then the four thousand vertices.
            function areasAt(areas, lon, lat) {
                var found = null;
                for (var a = 0; a < areas.length; a += 1) {
                    var box = areas[a].bounds;
                    if (lon < box[0] || lon > box[2] || lat < box[1] || lat > box[3]) { continue; }
                    var rings = areas[a].rings, crossings = 0;
                    for (var r = 0; r < rings.length; r += 1) {
                        var ring = rings[r];
                        for (var i = 0, k = ring.length - 1; i < ring.length; k = i, i += 1) {
                            var yi = ring[i][1], yk = ring[k][1];
                            // The half-open rule: a vertex exactly at this
                            // latitude is counted by the segment below it and
                            // not by the one above, so a ray through a corner
                            // is counted once rather than twice or not at all.
                            if ((yi > lat) === (yk > lat)) { continue; }
                            var t = (lat - yi) / (yk - yi);
                            if (lon < ring[i][0] + t * (ring[k][0] - ring[i][0])) { crossings += 1; }
                        }
                    }
                    if (crossings % 2 === 1) { (found = found || []).push(a); }
                }
                return found || NOWHERE;
            }

            // A linear scan, and it needs no spatial index: a hundred thousand
            // nodes is a few milliseconds, once per click. Anything cleverer
            // here would be a structure to keep in step with the geometry for no
            // gain a reader could perceive.
            // The rivers as the page's own table: each ring a list of [lon, lat],
            // unpacked from the differences the header carries them as (the
            // first pair absolute, every pair after it a step from the one
            // before, in `quantum` degrees). Unpacked once, here, because a
            // line is tested against a ring's vertices and not its steps.
            function riversOf(table) {
                if (!table || !table.rivers) { return []; }
                var quantum = table.quantum;
                return table.rivers.map(function (river) {
                    return {name: river.name || null, bounds: river.bounds,
                            rings: river.rings.map(function (steps) {
                                var ring = [], lon = 0, lat = 0;
                                for (var i = 0; i + 1 < steps.length; i += 2) {
                                    lon += steps[i]; lat += steps[i + 1];
                                    ring.push([lon * quantum, lat * quantum]);
                                }
                                return ring;
                            })};
                });
            }

            function nearestNode(nodeLon, nodeLat, lat, lon, withinM) {
                var scale = Math.cos(lat * Math.PI / 180);
                var limit = withinM === undefined ? Infinity : Math.pow(withinM / 111320, 2);
                var best = -1, closest = limit;
                for (var i = 0; i < nodeLon.length; i += 1) {
                    var dx = (nodeLon[i] - lon) * scale, dy = nodeLat[i] - lat;
                    var distance = dx * dx + dy * dy;
                    if (distance < closest) { closest = distance; best = i; }
                }
                return best;
            }

            var began = performance.now();
            var graph = {header: header, inflateMs: null, decodeMs: null, totalMs: null, error: null};
            // Bound to the graph before the stream is inflated rather than
            // inside the decode, because it needs nothing from the stream: the
            // outlines travel in the header, and a caller asking what protects
            // a position should not have to wait for two million coordinates
            // it is not going to look at.
            graph.protectedAreas = header.protected || [];
            graph.areasAt = areasAt.bind(null, graph.protectedAreas);
            // **And the rivers, as outlines.** Not priced -- see the water
            // grid below for what is -- but asked, of the straight parts a leg
            // ends up with: which river a line wades through and how wide the
            // water is there. The same `bounds` and `rings` shape as an area,
            // so the same even-odd test says whether a point is in one.
            graph.rivers = riversOf(header.rivers);
            graph.riverAt = areasAt.bind(null, graph.rivers);

            // **Where the water is, as bits.** A straight walk is priced by
            // what it crosses, and the search that prices it asks about
            // thousands of walks at once -- so the answer has to be one
            // subtraction, one division and one bit, and it is: cells of
            // `cellM` laid out in degrees from the south-west corner, eight to
            // a byte with the westernmost in the high bit, row-major. Ground
            // outside the grid answers *not water*, and so does a page whose
            // header carries no grid; both price every walk as ground, which
            // is what every page did before the grid existed.
            var POPCOUNT = new Uint8Array(256);
            for (var b = 1; b < 256; b += 1) { POPCOUNT[b] = POPCOUNT[b >> 1] + (b & 1); }

            // Checked the way the stream is: the header says how many cells
            // are water, and a grid that inflated to a different number is
            // refused rather than used. A grid that came out short would
            // price fjords as ground with nothing looking wrong.
            function waterGrid(spec, packed) {
                var stride = (spec.cols + 7) >> 3;
                if (packed.length !== spec.rows * stride) {
                    throw new Error('the water grid is ' + packed.length + ' bytes for ' + spec.rows + ' rows of ' + stride);
                }
                var set = 0;
                for (var i = 0; i < packed.length; i += 1) { set += POPCOUNT[packed[i]]; }
                if (set !== spec.set) {
                    throw new Error('the water grid inflated to ' + set + ' cells of water and was written with ' + spec.set);
                }
                return {spec: spec, bits: packed, stride: stride, cellM: spec.cellM};
            }

            function waterAt(grid, lon, lat) {
                if (!grid) { return false; }
                var spec = grid.spec;
                var col = Math.floor((lon - spec.west) / spec.dLon), row = Math.floor((lat - spec.south) / spec.dLat);
                if (col < 0 || row < 0 || col >= spec.cols || row >= spec.rows) { return false; }
                return (grid.bits[row * grid.stride + (col >> 3)] & (0x80 >> (col & 7))) !== 0;
            }

            graph.water = null;
            graph.waterAt = function (lon, lat) { return waterAt(graph.water, lon, lat); };
            var grid = header.water
                ? inflate(bytesOf(header.water.bits)).then(function (packed) { return waterGrid(header.water, packed); })
                : Promise.resolve(null);
            // Both inflated before either is used, so that nothing can route
            // over a graph whose water has not arrived: a search run in that
            // gap would price every connector as ground and the answer would
            // change under the reader when the grid landed.
            graph.ready = Promise.all([inflate(bytesOf(encoded)), grid]).then(function (both) {
                var bytes = both[0];
                graph.water = both[1];
                var inflated = performance.now();
                var decoded = decode(bytes);
                graph.inflateMs = inflated - began;
                graph.decodeMs = performance.now() - inflated;
                graph.totalMs = performance.now() - began;
                Object.keys(decoded).forEach(function (key) { graph[key] = decoded[key]; });
                return graph;
            }).catch(function (error) {
                // Loudly, in the one place a reader might look: a graph that
                // silently failed to arrive looks exactly like one that was
                // never asked for.
                graph.error = String(error);
                console.error('routing graph: ' + error);
                throw error;
            });
            window.trailsGraph = graph;
        })();

        (function () {
            var map = {{ this._parent.get_name() }};
            var groups = [{{ this.group_names|join(', ') }}];
            // Put back together from the positional table the build writes;
            // see `_packed_figures` for why it is written that way. Everything
            // below reads a figure by name, as it always has.
            var figures = (function (packed) {
                var out = {}, fields = packed.fields, name, values, figure, i;
                for (name in packed.rows) {
                    values = packed.rows[name];
                    figure = {};
                    for (i = 0; i < fields.length; i++) { figure[fields[i]] = values[i]; }
                    out[name] = figure;
                }
                return out;
            })({{ this.figures_json }});
            var title = {{ this.title_json }};
            var startingChartHeight = {{ this.chart_height }};
            var chartHeight = startingChartHeight;
            var GRADE = {{ this.gradient_json }};
            var NARROW = {{ this.narrow_px }};
            var SHORT = {{ this.short_px }};
            var open = {{ 'false' if this.collapsed else 'true' }};

            // **The size of the map, read rather than remembered.** Everything
            // here used to ask `map.getSize()`, which is a cache and not a
            // measurement: Leaflet re-reads the container only when
            // `invalidateSize()` has set `_sizeChanged`, and that runs from one
            // `window` `resize`, inside one `requestAnimationFrame`. See the
            // chrome's own note -- it is the same stale number, and it is why
            // this panel was drawn to a landscape width on an upright phone and
            // hung off the right edge.
            function mapRoom() {
                var box = map.getContainer();
                return {x: box.clientWidth || 0, y: box.clientHeight || 0};
            }

            var SVG = 'http://www.w3.org/2000/svg';
            // Room for the axes: the left margin holds a four-digit height, the
            // bottom one a distance.
            var PAD = {left: 52, right: 16, top: 12, bottom: 22};
            // Blue, deliberately: the steepest gradient band is red, and a red rule
            // over a red stretch of curve reads as part of the data.
            // **Read from the document rather than written here**, because
            // this is the one part of the panel that draws with SVG attributes,
            // and `var()` is a CSS value: `setAttribute('fill', 'var(--x)')`
            // paints nothing at all. The starting values are the light set and
            // the fallback if a page is ever built without the theme.
            var AXIS = '#9e9e9e', TEXT = '#555', CROSS = '#1565c0';
            var PAPER = '#ffffff', GRID = '#eceff1', MARK = '#111111', FAINT = '#9e9e9e';
            function refreshInk() {
                if (!window.getComputedStyle) { return; }
                var css = getComputedStyle(map.getContainer());
                function token(name, fallback) {
                    var got = css.getPropertyValue('--trails-' + name);
                    return (got && got.trim()) || fallback;
                }
                AXIS = token('ink-5', '#9e9e9e');
                TEXT = token('ink-3', '#555');
                CROSS = token('accent', '#1565c0');
                PAPER = token('solid', '#ffffff');
                GRID = token('rule-soft', '#eceff1');
                MARK = token('ink', '#111111');
                FAINT = token('ink-5', '#9e9e9e');
                STATION = MARK;
                STATION_UNREAD = FAINT;
            }
            // Sea level, which is the one height on this panel that is not a
            // choice: every other line is drawn where the data happens to be.
            var SEA = '#4fa3c7';
            // The dash a stretch nobody recorded a way along is drawn with,
            // here and on the map. One pattern, so the two read as one thing.
            var FREE_DASH = '5,4';

            // ---- what a number reads as ------------------------------------
            // Math.round is floor(x + 0.5), which is exactly what the popup's
            // formatter does. Anything else here — a toFixed, a rint — rounds a
            // half the other way, and the panel and the popup then disagree by
            // a metre on the chains that land on one.
            function metres(value) {
                return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            }

            // There is deliberately no rule here for naming a compass point.
            // It is decided once, in Python, and carried as figure.point.
            // Deriving it in the page from figure.bearing would be a second
            // implementation of a rounding rule — and a rounded label IS a
            // threshold: measured on this network, 241 chains lie within half a
            // degree of a boundary between two points, and two rules that
            // disagree by a hair name a different direction in the panel from
            // the one in the popup.

            // The one phrase that says which way the figures run. The popup
            // renders the same words from the same numbers in Python; a ring
            // gets no direction, because it has none and needs none.
            function climb(figure) {
                var words = '+' + metres(figure.ascent) + ' / \u2212' + metres(figure.descent) + ' m';
                return figure.point ? words + ' towards ' + figure.point : words;
            }

            // ---- the chain's own series, laid out of its edges --------------
            // Metres between two positions, from the metres-per-degree of the
            // ellipsoid at the latitude between them.
            //
            // **This used to be a sphere and it read 0.56 % short.** Measured
            // over 4,000 real edges against the projection the graph is built
            // in: 110,309 m where the projection says 110,933, because
            // 110,574 m to a degree of latitude is the figure at the *equator*
            // and this park sits at 65.6 N, where it is 111,500. That did not
            // matter while the only consumer was a chain, whose series is
            // scaled onto the length the chain carries before anything is
            // shown — a uniform factor cancels exactly. It matters the moment a
            // planned route states its own distance, because there is no
            // carried length to scale onto and nothing in the payload to read
            // one from: 0.56 % is 900 m on a 160 km traverse, against a map
            // whose every popup was measured in the projection.
            //
            // The series below is the standard one for WGS84 and reads +0.034 %
            // over the same 4,000 edges, sixteen times nearer. A degree of
            // longitude carries its own series rather than a bare cosine of the
            // equatorial radius, which is the other half of the old error.
            function metresBetween(lon1, lat1, lon2, lat2) {
                var phi = ((lat1 + lat2) / 2) * Math.PI / 180;
                var perLat = 111132.92 - 559.82 * Math.cos(2 * phi) + 1.175 * Math.cos(4 * phi) - 0.0023 * Math.cos(6 * phi);
                var perLon = 111412.84 * Math.cos(phi) - 93.5 * Math.cos(3 * phi) + 0.118 * Math.cos(5 * phi);
                var dx = (lon2 - lon1) * perLon;
                var dy = (lat2 - lat1) * perLat;
                return Math.sqrt(dx * dx + dy * dy);
            }

            // Lay a run of edges end to end, in the order and the directions
            // given. **One walk, and every consumer in the page uses it**: the
            // panel lays a chain's edges out of the payload's own order, plan
            // mode lays a route's out of what the router returned. Two walks
            // would eventually disagree, and each would still look like a
            // profile — which is the reason the Python side keeps its one in
            // trails.routing.order rather than one per caller.
            //
            // Two joined edges both sample the node between them, so the second
            // copy of it is dropped; where `breaks` says an edge does not join
            // what came before, the series is broken rather than joined.
            function layEdges(graph, list, reversed, breaks) {
                var lon = [], lat = [], along = [], height = [], distance = [];
                var reached = 0, read = false, crossing = false, joined = false;
                // Where each stretch that joins up begins, in both series. The
                // profile does not need them — it reads the NaN the break
                // leaves behind — but an export writes one track segment per
                // stretch, and a segment drawn across the step between two of
                // them is a route nobody can walk.
                var stretches = [];
                for (var index = 0; index < list.length; index += 1) {
                    var edge = list[index];
                    var flipped = reversed[index];
                    var apart = breaks[index] && lon.length > 0;
                    var v0 = graph.vertexAt[edge], v1 = graph.vertexAt[edge + 1];
                    var s0 = graph.sampleAt[edge], s1 = graph.sampleAt[edge + 1], samples = s1 - s0;
                    var began = reached;
                    crossing = crossing || graph.header.sources[graph.sources[edge]].kind === 'ferry';

                    if (apart || !lon.length) {
                        // The separator pushed below closes the stretch that
                        // ended; it is not the first sample of this one.
                        var separated = !!(samples && height.length && apart);
                        stretches.push({from: lon.length, sampleFrom: height.length + (separated ? 1 : 0), separated: separated});
                    }

                    for (var v = 0; v < v1 - v0; v += 1) {
                        var at = flipped ? v1 - 1 - v : v0 + v;
                        var x = graph.coordinates[2 * at], y = graph.coordinates[2 * at + 1];
                        if (v === 0) {
                            // The node this edge is joined on is already laid
                            // down. Where it is not joined, the step across is
                            // ground nothing was measured along, so it starts
                            // where it starts and adds no distance.
                            if (lon.length && !apart) { continue; }
                            began = reached;
                        } else {
                            reached += metresBetween(lon[lon.length - 1], lat[lat.length - 1], x, y);
                        }
                        lon.push(x); lat.push(y); along.push(reached);
                    }

                    var length = reached - began;
                    if (samples && height.length && apart) {
                        // A break rather than a join: a climb counted across a
                        // step nothing was measured along is invented.
                        height.push(NaN); distance.push(began);
                    }
                    for (var s = (joined && !apart) ? 1 : 0; s < samples; s += 1) {
                        var sample = flipped ? s1 - 1 - s : s0 + s;
                        var value = graph.heights[sample];
                        height.push(value);
                        // Every 5 m along the edge means samples spread evenly
                        // between its two ends, so this is where the sth of them
                        // lies rather than s * 5 — and the last of them sits on
                        // the edge's far end, which is a vertex, so it takes
                        // that vertex's own distance rather than one a hair
                        // away: began + (reached - began) is not reached, and
                        // an export merging the two writes a pair of points at
                        // a single position.
                        distance.push(samples < 2 ? began : (s === samples - 1 ? reached : began + (length * s) / (samples - 1)));
                        if (!isNaN(value)) { read = true; }
                    }
                    joined = samples > 0;
                }
                for (var s = 0; s < stretches.length; s += 1) {
                    var next = stretches[s + 1];
                    stretches[s].to = next ? next.from : lon.length;
                    stretches[s].sampleTo = next ? next.sampleFrom - (next.separated ? 1 : 0) : height.length;
                }
                return {lon: lon, lat: lat, along: along, height: height, distance: distance,
                        stretches: stretches, total: reached, read: read, crossing: crossing};
            }

            // The payload holds a chain's edges as one contiguous run in the
            // chain's own order; bit 0 of an edge's flag says it runs against
            // the chain, bit 1 that it begins a stretch which does not join
            // what came before.
            function compose(graph, index) {
                var list = [], reversed = [], breaks = [];
                for (var edge = graph.chainAt[index]; edge < graph.chainAt[index + 1]; edge += 1) {
                    list.push(edge);
                    reversed.push(!!(graph.flags[edge] & 1));
                    breaks.push(!!(graph.flags[edge] & 2));
                }
                return layEdges(graph, list, reversed, breaks);
            }

            // The chain's length as the chain carries it, distributed over the
            // series by the geometry. One length, so the axis, the crosshair and
            // the popup all end on the same number.
            function scale(shape, carried) {
                var factor = (carried > 0 && shape.total > 0) ? carried / shape.total : 1;
                var i;
                for (i = 0; i < shape.along.length; i += 1) { shape.along[i] *= factor; }
                for (i = 0; i < shape.distance.length; i += 1) { shape.distance[i] *= factor; }
                shape.total = carried > 0 ? carried : shape.total;
                return shape;
            }

            // Which point of the drawn line lies this far along it.
            //
            // **A series has two axes and they are not the same length.** The
            // heights are sampled every 5 m; the line is drawn through the
            // vertices somebody surveyed, which fall wherever they fall. So a
            // sample's index says nothing about a vertex's, and the only thing
            // the two share is a distance. ``along`` is the vertices' own.
            function positionAt(shape, metres) {
                if (!shape.along || !shape.along.length) { return null; }
                var low = 0, high = shape.along.length - 1;
                while (low < high) {
                    var middle = (low + high) >> 1;
                    if (shape.along[middle] < metres) { low = middle + 1; } else { high = middle; }
                }
                if (low < 1) { return L.latLng(shape.lat[0], shape.lon[0]); }
                var span = shape.along[low] - shape.along[low - 1];
                var t = span > 0 ? Math.min(1, Math.max(0, (metres - shape.along[low - 1]) / span)) : 0;
                return L.latLng(shape.lat[low - 1] + t * (shape.lat[low] - shape.lat[low - 1]),
                                shape.lon[low - 1] + t * (shape.lon[low] - shape.lon[low - 1]));
            }

            // Where to put the arrow: half way along, by distance.
            function midpoint(shape) {
                return positionAt(shape, shape.total / 2);
            }

            // ---- the file this panel writes ---------------------------------
            // Hand-written, like everything else here: a library from a CDN
            // does not load on a page opened off the disk. It writes what
            // libs/src/trails/io/export/gpx.py writes, from the same graph and
            // the same edge order. Nothing here can import that module and no
            // test can run this, so the two are exported on a real chain and
            // compared in a browser whenever the work is accepted — to a
            // tolerance the payload sets rather than to equality. What they
            // agree on exactly is the field names, and those are handed in.
            var EXPORT = {{ this.export_json }};

            function escaped(value) {
                return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;').replace(/'/g, '&apos;');
            }

            // Written to as many places as the page's own figures carry, and to
            // exactly that many: '500' in one file against '500.0' in the other
            // is two writers disagreeing about a number both of them got right.
            function fixed(value) {
                return Number(value).toFixed(EXPORT.decimals);
            }

            // A height keeps more places than a figure does: it is what the
            // figure was computed from, and a file whose <ele> values do not
            // reproduce the ascent it states has no use for stating one.
            function fixedEle(value) {
                return Number(value).toFixed(EXPORT.elevationDecimals);
            }

            // The height model read at a set of distances along one stretch.
            // Both series only ever move forward, so one pointer serves the
            // whole of it. A position *between* two samples one of which says
            // nothing gets nothing — a height interpolated across a gap is
            // invented ground, and nothing downstream can tell the two apart —
            // while a position landing on a sample takes that sample and asks
            // nothing of its neighbour.
            function heightsAt(positions, shape, from, to) {
                var out = new Array(positions.length), below = from, i;
                for (i = 0; i < positions.length; i += 1) { out[i] = NaN; }
                if (to - from < 2) { return out; }
                for (i = 0; i < positions.length; i += 1) {
                    while (below < to - 2 && shape.distance[below + 1] <= positions[i]) { below += 1; }
                    var span = shape.distance[below + 1] - shape.distance[below];
                    var t = span > 0 ? (positions[i] - shape.distance[below]) / span : 0;
                    t = t < 0 ? 0 : (t > 1 ? 1 : t);
                    var low = shape.height[below], high = shape.height[below + 1];
                    out[i] = t <= 0 ? low : (t >= 1 ? high : (isNaN(low) || isNaN(high)) ? NaN : low + t * (high - low));
                }
                return out;
            }

            // Every vertex the chain has, every sample the height model gave,
            // and a point wherever two of those are still further apart than
            // the gap. **Not** a resampling every 5 m: that drops the source's
            // own vertices and rounds off every corner between two samples, and
            // those vertices are the whole reason the geometry is carried at
            // full precision. And **not** the vertices alone with the heights
            // interpolated between them: measured that way, the ascent read
            // back off the file's own values came out 47 m under the figure the
            // same file states for the 42 km Rundtur. Where nothing was read
            // along the stretch there is nothing to fill it for either — a
            // point every 5 m across a fjord says nothing its two ends do not.
            function denseOf(shape, stretch) {
                var lon = [], lat = [], read = false, i, k;
                for (i = stretch.sampleFrom; i < stretch.sampleTo; i += 1) {
                    if (!isNaN(shape.height[i])) { read = true; break; }
                }
                var along = shape.along, first = stretch.from, last = stretch.to;
                if (!read || last - first < 2) {
                    for (i = first; i < last; i += 1) { lon.push(shape.lon[i]); lat.push(shape.lat[i]); }
                    return {lon: lon, lat: lat, ele: lon.map(function () { return NaN; })};
                }

                // The two lists merged, each distance once. An edge's first and
                // last sample sit on its end vertices and are the same number
                // here, so the merge drops the copy rather than writing a step
                // of no length.
                var merged = [], sample = stretch.sampleFrom;
                function keep(value) {
                    if (!merged.length || merged[merged.length - 1] !== value) { merged.push(value); }
                }
                while (sample < stretch.sampleTo && shape.distance[sample] <= along[first]) { sample += 1; }
                for (i = first; i < last; i += 1) {
                    while (sample < stretch.sampleTo && shape.distance[sample] < along[i]) { keep(shape.distance[sample]); sample += 1; }
                    if (sample < stretch.sampleTo && shape.distance[sample] === along[i]) { sample += 1; }
                    keep(along[i]);
                }

                // And the samples are not as close together as their step
                // suggests: an edge of 12 m gets three of them, 6 m apart.
                var positions = [merged[0]];
                for (i = 1; i < merged.length; i += 1) {
                    var step = merged[i] - merged[i - 1];
                    var intervals = Math.max(Math.ceil(step / EXPORT.gapM), 1);
                    for (k = 1; k < intervals; k += 1) { positions.push(merged[i - 1] + (k / intervals) * step); }
                    // A position already in the list is written as itself and
                    // never as a fraction of the way to itself: a + 1 * (b - a)
                    // is not b, and a sample that misses its own distance by an
                    // ulp is interpolated instead of read.
                    positions.push(merged[i]);
                }

                var below = first;
                for (i = 0; i < positions.length; i += 1) {
                    while (below < last - 2 && along[below + 1] <= positions[i]) { below += 1; }
                    var span = along[below + 1] - along[below];
                    var t = span > 0 ? (positions[i] - along[below]) / span : 0;
                    t = t < 0 ? 0 : (t > 1 ? 1 : t);
                    // A vertex is the coordinate the surveyor recorded, not a
                    // point computed between it and its neighbour.
                    var at = t >= 1 ? below + 1 : below;
                    if (t <= 0 || t >= 1) {
                        lon.push(shape.lon[at]); lat.push(shape.lat[at]);
                    } else {
                        lon.push(shape.lon[below] + t * (shape.lon[below + 1] - shape.lon[below]));
                        lat.push(shape.lat[below] + t * (shape.lat[below + 1] - shape.lat[below]));
                    }
                }
                return {lon: lon, lat: lat, ele: heightsAt(positions, shape, stretch.sampleFrom, stretch.sampleTo)};
            }

            function runsOf(shape) {
                return shape.stretches.map(function (stretch) { return denseOf(shape, stretch); });
            }

            // Where the selection crosses a protected boundary, worked out the
            // first time something asks and then kept against that selection.
            //
            // **Asked for rather than computed on every refresh, and measured.**
            // The walk below is 45 ms of a 50 ms panel refresh over a 37 km
            // route and it grows with the route, while the only thing that needs
            // it is the button — which a reader may never press. Cached, so the
            // file and any check that reads them get one answer rather than two
            // walks that could differ. The cache dies with the selection, which
            // is a fresh object on every change.
            function crossings() {
                if (!selected || !selected.composed || !selected.shape || !selected.runs) { return []; }
                if (!selected.crossings) { selected.crossings = crossingsOf(selected.shape, selected.runs); }
                return selected.crossings;
            }

            // Where the route crosses into a protected area and where it leaves
            // one again, as the markers the file carries. **Read off the runs
            // the file is written from**, which is the one series in this page
            // with a point every few metres over the whole route — the vertices
            // alone are a source's own corners and a leg drawn straight has two
            // of them for twenty kilometres.
            //
            // Two things this deliberately does not do. It puts no marker where
            // the route *begins* inside an area or ends inside one: that is not
            // a crossing and there is nothing there to see. And it looks only
            // for the areas the route already reports — the threshold is
            // applied once, where the figures are — so a boundary grazed for
            // ten metres cannot bring a pair of markers in through this door
            // after the sentence above declined to mention it.
            //
            // The boundary this walks is the page's own copy, simplified to
            // five metres, so a marker sits within that of the line the
            // register draws. The *lengths* beside it are not measured here:
            // they come from the build, which measured them against the
            // register's full precision.
            //
            // **A crossing is walked with the rest of the route.** It writes no
            // track points -- GPX cannot say a segment is a boat -- but it is
            // ground the route passes over, and its boundary crossings are as
            // computable as any. Walking only the written runs, and starting
            // each of them with an empty list, lost every crossing that
            // happened inside a break in both directions: walk into a reserve,
            // ferry out of it, carry on outside, and the file said *Enters
            // Sirijorda naturreservat* and never that the route left.
            //
            // **The gap's own line is sampled, because its vertices are not a
            // series.** A ferry from N50 has a source's corners and a water leg
            // the reader's two points, so a boundary between two of them would
            // put the marker at their midpoint -- hundreds of metres out, where
            // the runs are accurate to a few. Stepped at the height model's own
            // 5 m, so a marker on water is placed exactly as one on land is.
            // How finely a crossing's own line is stepped, in metres. The
            // height model samples at 5 and the runs inherit that spacing, so
            // this is the runs' own accuracy rather than a number of its own.
            var CROSSING_STEP_M = 5;

            function crossingsOf(shape, runs) {
                var graph = window.trailsGraph;
                if (!graph || !graph.areasAt) { return []; }
                var reported = Object.create(null);
                (shape.protected || []).forEach(function (area) { reported[area.id] = area; });

                var out = [];
                function mark(area, entering, first, second) {
                    out.push({id: area.id, name: area.name, form: area.form, entering: entering,
                              lat: (first.lat + second.lat) / 2, lon: (first.lon + second.lon) / 2});
                }
                function named(indices) {
                    var ids = [];
                    for (var i = 0; i < indices.length; i += 1) { ids.push(graph.protectedAreas[indices[i]].id); }
                    return ids;
                }

                function stepped(gap) {
                    var lon = [], lat = [], i, k, steps;
                    for (i = 0; i < gap.lon.length; i += 1) {
                        if (i > 0) {
                            steps = Math.ceil(metresBetween(gap.lon[i - 1], gap.lat[i - 1], gap.lon[i], gap.lat[i]) / CROSSING_STEP_M);
                            for (k = 1; k < steps; k += 1) {
                                lon.push(gap.lon[i - 1] + (gap.lon[i] - gap.lon[i - 1]) * k / steps);
                                lat.push(gap.lat[i - 1] + (gap.lat[i] - gap.lat[i - 1]) * k / steps);
                            }
                        }
                        lon.push(gap.lon[i]); lat.push(gap.lat[i]);
                    }
                    return {lon: lon, lat: lat};
                }

                // One walk over the whole route, gaps in their place, and a
                // single list of what it is inside that is never restarted.
                var series = [];
                var gaps = shape.gaps || [];
                for (var r = 0; r <= runs.length; r += 1) {
                    gaps.forEach(function (gap) { if (gap.before === r) { series.push(stepped(gap)); } });
                    if (r < runs.length) { series.push(runs[r]); }
                }

                var before = [], last = null, started = false;
                series.forEach(function (part) {
                    for (var i = 0; i < part.lon.length; i += 1) {
                        var here = named(graph.areasAt(part.lon[i], part.lat[i]));
                        // The route's own first point sets what it began inside
                        // and marks nothing, which is the rule above: beginning
                        // inside an area is not a crossing.
                        if (started) {
                            var from = {lon: last.lon, lat: last.lat};
                            var to = {lon: part.lon[i], lat: part.lat[i]};
                            here.forEach(function (id) {
                                if (reported[id] && before.indexOf(id) < 0) { mark(reported[id], true, from, to); }
                            });
                            before.forEach(function (id) {
                                if (reported[id] && here.indexOf(id) < 0) { mark(reported[id], false, from, to); }
                            });
                        }
                        before = here;
                        last = {lon: part.lon[i], lat: part.lat[i]};
                        started = true;
                    }
                });
                return out;
            }

            function pointsIn(runs) {
                return runs.reduce(function (total, run) { return total + run.lon.length; }, 0);
            }

            function heightsWritten(runs) {
                return runs.some(function (run) { return run.ele.some(function (value) { return !isNaN(value); }); });
            }

            // Whether the height model is behind any of the numbers in this
            // file, which is a different question from whether the file carries
            // heights at all.
            //
            // **A stretch kept as it was recorded carries the heights that came
            // with the loaded file, and this map never asked the model about
            // it.** Crediting Kartverket for a consumer GPS reading, and
            // stating it was sampled from DTM1 every 5 m, is a false claim in a
            // file somebody takes into the terrain — and it is the exact claim
            // this file was given an `ascentMethod` to avoid making by
            // accident. A chain's series is nothing but the model and says
            // nothing about itself, so an absent answer means the model.
            function modelBehind(shape) {
                return !shape || shape.modelled === undefined ? true : !!shape.modelled;
            }

            // What a chain's file draws on: the chain's own source, and the
            // height model wherever the file carries a height. Naming a source a
            // file does not draw on is exactly as wrong as leaving one out.
            function creditsOf(figure, runs) {
                return (EXPORT.credits[figure.source] || []).concat(heightsWritten(runs) ? EXPORT.heights : []);
            }

            // And a route's, each with the length it contributed. **The terms
            // are not the same for every route**: one running on FKB and
            // Turrutebasen alone is unencumbered, one that picks up a kilometre
            // of OSM is share-alike and one that picks up UT.no is
            // non-commercial, so the figure belongs beside the licence rather
            // than in a blanket warning nobody reads.
            function routeCredits(shape, runs) {
                var metres = shape.tally.sources;
                var names = Object.keys(metres).sort(function (a, b) { return metres[b] - metres[a]; });
                var out = [];
                names.forEach(function (name) {
                    (EXPORT.credits[name] || []).forEach(function (credit) {
                        // A copy. EXPORT.credits is the page's one description of
                        // each dataset, and writing a length onto it would leave
                        // this route's metres on the next route's file.
                        var carried = {};
                        Object.keys(credit).forEach(function (field) { carried[field] = credit[field]; });
                        carried[EXPORT.sourceLength] = fixed(metres[name]);
                        out.push(carried);
                    });
                });
                // And the register the protected figures come from, wherever
                // the file states one. A file naming a source it did not draw on
                // is exactly as wrong as one leaving a source out, and this
                // route's description carries a number that came from Naturbase.
                return out.concat(heightsWritten(runs) && modelBehind(shape) ? EXPORT.heights : [])
                    .concat((shape.protected || []).length ? EXPORT.protected : []);
            }

            function creditLine(credit) {
                var inside = ['licence', 'version', 'attribution'].filter(function (field) { return credit[field]; })
                    .map(function (field) { return credit[field]; });
                var named = inside.length ? credit.name + ' (' + inside.join(', ') + ')' : credit.name;
                // The height model contributes no metres of line, so it carries
                // none and is named without one rather than with a zero.
                var metres = credit[EXPORT.sourceLength];
                return metres ? (Number(metres) / 1000).toFixed(2) + ' km ' + named : named;
            }

            // The same entry as the reader sees it before pressing the button.
            function licenceLine(credit) {
                var metres = credit[EXPORT.sourceLength];
                return (metres ? (Number(metres) / 1000).toFixed(2) + ' km ' : '') +
                    credit.name + ' \u2014 ' + credit.licence + (credit.note ? ', ' + credit.note : '');
            }

            // A length in the unit it can be read in. The three buckets below
            // are always in kilometres because they are read against one
            // another; the two beside them are not, and a connector run of a
            // quarter of a metre written as '0.00 km' reads as a figure that is
            // not there.
            function span(value) {
                return value >= 1000 ? (value / 1000).toFixed(2) + ' km' : (Math.round(value * 10) / 10) + ' m';
            }

            // How much of the route is waymarked, in length and in three
            // buckets. **Unknown is its own bucket and is never folded into
            // unmarked**: measured over the walked network without its inferred
            // connectors, 63.4 % of the length is unknown, and FKB — the largest
            // source at 33.8 % — carries no marking field at all, so calling it
            // unmarked would assert what no source says. All three are shown
            // even at zero, because which of them a route avoids is the reading.
            //
            // Two more only where there is any: ground on a connector nobody
            // drew, which was never asked rather than asked and unanswered, and
            // ground no source records a path along — **recorded, not fact**.
            // The sources over-record, so their silence is evidence and their
            // lines are not.
            function markingLine(tally) {
                var said = ['marked', 'unmarked', 'unknown'].map(function (bucket) {
                    return bucket + ' ' + (tally[bucket] / 1000).toFixed(2) + ' km';
                });
                if (tally.undrawn > 0) {
                    said.push(span(tally.undrawn) + ' on connectors nobody drew');
                }
                // The fifth bucket, and it is reported for the same reason the
                // fourth is: no register was asked about ground that came off a
                // loaded recording, and folding it into 'unmarked' would turn a
                // question nobody put into an answer.
                if (tally.recorded > 0) {
                    said.push(span(tally.recorded) + ' kept as it was recorded');
                }
                if (tally.unrecorded > 0) {
                    said.push(span(tally.unrecorded) + ' where no source records a path');
                }
                return said.join(' \u00b7 ');
            }

            // The named ways the track follows. A chain running over several of
            // them carries them joined, and that is its own identity: 'via
            // Tveråvegen, Gamle Stavassveg' is how a person describes a route.
            function waysOf(figure) {
                if (!figure.name) { return ''; }
                return 'via ' + String(figure.name).split(EXPORT.identitySeparator).map(function (part) { return part.trim(); })
                    .filter(function (part) { return part; }).join(', ');
            }

            // The silence is the whole of the statement, and the wording has to
            // keep saying so: this is ground no register draws anything on, not
            // ground with no path. The popup's own words, off the same field.
            function unrecordedOf(figure) {
                return figure.noPath > 0 ? (figure.noPath / 1000).toFixed(2) + ' km where no source records a path' : '';
            }

            function fileNameOf(stem, extension) {
                return (EXPORT.filePrefix + '-' + (stem || 'track')).replace(/[^A-Za-z0-9._-]+/g, '-') +
                    (extension || '.gpx');
            }

            function element(name, value) {
                return '<' + EXPORT.prefix + ':' + name + '>' + escaped(value) + '</' + EXPORT.prefix + ':' + name + '>';
            }

            function openGpx(out) {
                out.push('<?xml version="1.0" encoding="UTF-8"?>');
                out.push('<gpx version="1.1" creator="' + escaped(EXPORT.creator) + '"' +
                    ' xmlns="http://www.topografix.com/GPX/1/1"' +
                    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' +
                    ' xmlns:' + EXPORT.prefix + '="' + escaped(EXPORT.namespace) + '"' +
                    ' xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">');
            }

            // The order GPX 1.1 fixes for what <metadata> holds, and there is
            // deliberately no <copyright>: it takes exactly one licence, and a
            // file mixing CC0, CC BY, ODbL and CC BY-NC has no single one to put
            // there. Listing what is present is the honest form.
            function metadataOf(out, name, described, credits) {
                out.push('  <metadata>');
                out.push('    <name>' + escaped(name) + '</name>');
                // The phrase goes in with the list and not before it. A route
                // made entirely of a loaded recording draws on nothing this map
                // holds — its ground came out of the reader's file and its
                // heights with it — and `Sources: ` followed by nothing reads
                // like a list that failed to be written rather than one there
                // was nothing to put in.
                out.push('    <desc>' + escaped(credits.length
                    ? described + '. Sources: ' + credits.map(creditLine).join(' \u00b7 ')
                    : described) + '</desc>');
                out.push('    <time>' + new Date().toISOString().replace(/\.\d+Z$/, 'Z') + '</time>');
                out.push('    <extensions>');
                credits.forEach(function (credit) {
                    var written = EXPORT.creditFields.filter(function (field) { return credit[field]; })
                        .map(function (field) { return ' ' + field + '="' + escaped(credit[field]) + '"'; });
                    out.push('      <' + EXPORT.prefix + ':source' + written.join('') + '/>');
                });
                out.push('    </extensions>');
                out.push('  </metadata>');
            }

            // One segment per stretch that joins up. A track drawn straight
            // across the step between two of them is a route nobody can walk:
            // no chain in this park has such a step and a plan has one at every
            // crossing, and the file says which by where it breaks rather than
            // by asserting anything.
            function segmentsOf(out, runs) {
                runs.forEach(function (run) {
                    out.push('    <trkseg>');
                    for (var i = 0; i < run.lon.length; i += 1) {
                        var point = '      <trkpt lat="' + run.lat[i].toFixed(EXPORT.coordinateDecimals) +
                            '" lon="' + run.lon[i].toFixed(EXPORT.coordinateDecimals) + '">';
                        // No <time> on a trackpoint, ever: a track carrying
                        // timestamps reads as a recorded activity rather than a
                        // plan, and the rest would be guesses dressed as data.
                        //
                        // And a point the height model was never read at keeps
                        // its place and loses only its <ele>. That is the second
                        // of the two kinds of nothing this file has to tell
                        // apart: there is ground here and no reading of it,
                        // where a crossing is no ground at all and ended the
                        // segment above.
                        out.push(point + (isNaN(run.ele[i]) ? '</trkpt>' : '<ele>' + fixedEle(run.ele[i]) + '</ele></trkpt>'));
                    }
                    out.push('    </trkseg>');
                });
            }

            function gpxOf(figure, shape, runs) {
                var credits = creditsOf(figure, runs);
                var told = [waysOf(figure), shape.read ? climb(figure) : '', unrecordedOf(figure)]
                    .filter(function (part) { return part; });

                var out = [];
                openGpx(out);
                metadataOf(out, figure.name || figure.id, EXPORT.description, credits);

                out.push('  <trk>');
                out.push('    <name>' + escaped(figure.name || figure.id) + '</name>');
                if (told.length) { out.push('    <desc>' + escaped(told.join(' \u00b7 ')) + '</desc>'); }
                out.push('    <extensions>');
                EXPORT.fields.forEach(function (pair) {
                    var value = figure[pair[0]];
                    if (value === null || value === undefined || value === '') { return; }
                    out.push('      ' + element(pair[1], typeof value === 'number' ? fixed(value) : value));
                });
                if (heightsWritten(runs) && EXPORT.ascentMethod) {
                    out.push('      ' + element('ascentMethod', EXPORT.ascentMethod));
                }
                out.push('    </extensions>');
                segmentsOf(out, runs);
                out.push('  </trk>');
                out.push('</gpx>');
                return out.join('\n') + '\n';
            }

            // Everything a planned route states about itself as one number.
            // Read off the composed series and the figures already read from
            // it, never recomputed here: the panel above the button and the file
            // under it have to be the same claim.
            function routeFigures(figure, shape) {
                return {
                    ascent: shape.read ? figure.ascent : null,
                    descent: shape.read ? figure.descent : null,
                    walked: shape.total,
                    crossed: shape.crossed,
                    straight: shape.straight,
                    recorded: shape.tally.recorded,
                    unrecorded: shape.tally.unrecorded,
                    marked: shape.tally.marked,
                    unmarked: shape.tally.unmarked,
                    unknown: shape.tally.unknown,
                    undrawn: shape.tally.undrawn
                };
            }

            // `extra` is what the panel was told about the route beside its own
            // series — its crossings, its stretches drawn straight — and it is
            // handed in for the same reason `planned` takes it: the sentence
            // above the button and the one in the file are one sentence.
            function routeGpxOf(figure, shape, runs, plan, extra, crossings) {
                var credits = routeCredits(shape, runs);
                var told = planned(figure, shape, extra).concat([markingLine(shape.tally)]);
                var figures = routeFigures(figure, shape);

                // **What the reader called it, where they called it anything.**
                // A tour goes into <metadata><name> and <trk><name>, which is
                // where GPX already puts a name and what every other reader
                // shows — so it needs no field of its own, and a second
                // recording of one title is a second thing to disagree.
                var titled = (plan && plan.name) ? plan.name : EXPORT.route.name;

                var out = [];
                openGpx(out);
                metadataOf(out, titled, EXPORT.route.description, credits);

                // After the metadata and before the track, which is where GPX
                // 1.1 puts a waypoint: it is a top-level element of its own and
                // **not** part of the extensions mechanism, and a file placing
                // it anywhere else parses and fails the schema.
                // The order GPX 1.1 fixes inside a <wpt> as well: name, then
                // desc, then type, then the extensions. A file that writes them
                // in the order they were thought of parses and fails the schema,
                // which is the whole reason phase 6B's file is checked against
                // one.
                function waypoint(point, name, described, kind, origin, area, stage) {
                    out.push('  <wpt lat="' + point.lat.toFixed(EXPORT.coordinateDecimals) +
                        '" lon="' + point.lon.toFixed(EXPORT.coordinateDecimals) + '">');
                    out.push('    <name>' + escaped(name) + '</name>');
                    if (described) { out.push('    <desc>' + escaped(described) + '</desc>'); }
                    if (kind) { out.push('    <type>' + escaped(kind) + '</type>'); }
                    // Set or generated, on every one: a reader loading this file
                    // back must never take a marker the map placed for a station
                    // somebody chose, or the route would gain stations nobody
                    // put down and start routing through them.
                    out.push('    <extensions>');
                    out.push('      ' + element(EXPORT.waypoint.origin, origin));
                    if (area) { out.push('      ' + element(EXPORT.waypoint.area, area)); }
                    // **Present and empty is not absent.** The element standing
                    // there is what says a stage ends at this point; its text is
                    // only the name. Written on a falsy test every unnamed cut
                    // would be dropped, and a tour would come back in one piece
                    // with nothing saying it had ever been in more.
                    if (stage !== null && stage !== undefined) {
                        out.push('      ' + element(EXPORT.waypoint.stage, stage));
                    }
                    out.push('    </extensions>');
                    out.push('  </wpt>');
                }

                plan.waypoints.forEach(function (point, index) {
                    // Named after what is there where the map draws something
                    // named within reach, and after its number otherwise. The
                    // naming is decided where the points are, not here, so that
                    // what the panel reports and what the file says are one
                    // answer.
                    waypoint(point, point.name || (EXPORT.waypoint.name + ' ' + (index + 1)),
                             null, point.kind || null, EXPORT.waypoint.set, null,
                             point.stage === undefined ? null : point.stage);
                });

                // And the boundaries, which are the only way GPX can carry one
                // at all: it holds waypoints, routes and tracks, and no
                // polygons. **After the points the reader placed rather than
                // among them.** Their order in the file says nothing — every
                // one of them names its origin — and interleaving them would
                // make the sequence of set points depend on where the route
                // happens to run, which is a decision phase 7 owns.
                (crossings || []).forEach(function (crossing) {
                    var verb = crossing.entering ? EXPORT.waypoint.enters : EXPORT.waypoint.leaves;
                    waypoint(crossing, verb + ' ' + crossing.name + ' ' + crossing.form,
                             null, crossing.form, EXPORT.waypoint.generated, crossing.id);
                });

                out.push('  <trk>');
                out.push('    <name>' + escaped(titled) + '</name>');
                out.push('    <desc>' + escaped(told.join(' \u00b7 ')) + '</desc>');
                out.push('    <extensions>');
                out.push('      ' + element(EXPORT.route.kindField, EXPORT.route.kind));
                EXPORT.route.fields.forEach(function (pair) {
                    var value = figures[pair[0]];
                    if (value === null || value === undefined || isNaN(value)) { return; }
                    out.push('      ' + element(pair[1], fixed(value)));
                });
                if (heightsWritten(runs) && modelBehind(shape) && EXPORT.ascentMethod) {
                    out.push('      ' + element('ascentMethod', EXPORT.ascentMethod));
                }
                // The legs, in the order they were clicked, each holding its
                // parts in the order they are walked. **This cannot go on a
                // <trkseg>**: a segment is a stretch and a stretch breaks only
                // where the ground stops, so four routed legs laid end to end
                // are one segment and could carry one mode between them. Leg n
                // runs from waypoint n to waypoint n + 1, which is what makes
                // the list readable without an index on either.
                out.push('      <' + EXPORT.prefix + ':' + EXPORT.route.legs + '>');
                plan.legs.forEach(function (parts) {
                    out.push('        <' + EXPORT.prefix + ':' + EXPORT.route.leg + '>');
                    parts.forEach(function (part) {
                        out.push('          <' + EXPORT.prefix + ':' + EXPORT.route.part +
                            ' ' + EXPORT.route.partKind + '="' + escaped(part.kind) + '"' +
                            ' ' + EXPORT.route.partLength + '="' + fixed(part.length) + '"/>');
                    });
                    out.push('        </' + EXPORT.prefix + ':' + EXPORT.route.leg + '>');
                });
                out.push('      </' + EXPORT.prefix + ':' + EXPORT.route.legs + '>');
                // And what protects the ground it covers, as figures rather
                // than as a sentence to be parsed back: which areas, in which
                // form, and how much of the route lies in each. **Nothing here
                // says what may be done in one.** That is in each area's
                // verneforskrift, none has been read, and a file that guessed
                // would be read as advice.
                if ((shape.protected || []).length) {
                    out.push('      <' + EXPORT.prefix + ':' + EXPORT.route.areas + '>');
                    shape.protected.forEach(function (area) {
                        out.push('        <' + EXPORT.prefix + ':' + EXPORT.route.area +
                            ' ' + EXPORT.route.areaId + '="' + escaped(area.id) + '"' +
                            ' ' + EXPORT.route.areaName + '="' + escaped(area.name) + '"' +
                            ' ' + EXPORT.route.areaForm + '="' + escaped(area.form) + '"' +
                            ' ' + EXPORT.route.areaLength + '="' + fixed(area.metres) + '"/>');
                    });
                    out.push('      </' + EXPORT.prefix + ':' + EXPORT.route.areas + '>');
                }
                out.push('    </extensions>');
                segmentsOf(out, runs);
                out.push('  </trk>');
                out.push('</gpx>');
                return out.join('\n') + '\n';
            }

            // Garmin Explore caps a course at 200 points; see garmin-decisions
            // §3. Simplify the joined runs in metres, retaining original vertices
            // and their heights. A crossing joins the line rather than breaking it.
            function garminPoints(runs) {
                var points = [];
                runs.forEach(function (run) {
                    for (var i = 0; i < run.lon.length; i += 1) {
                        points.push({lon: run.lon[i], lat: run.lat[i], ele: run.ele[i]});
                    }
                });
                var cap = 200;
                if (points.length <= cap) { return points; }
                var mean = points.reduce(function (sum, point) { return sum + point.lat; }, 0) / points.length;
                var perLon = metresBetween(0, mean, 1, mean);
                var perLat = metresBetween(0, mean - 0.5, 0, mean + 0.5);
                var xy = points.map(function (point) {
                    return [(point.lon - points[0].lon) * perLon, (point.lat - mean) * perLat];
                });
                function simplified(tolerance) {
                    var kept = new Uint8Array(points.length), last = points.length - 1;
                    kept[0] = 1; kept[last] = 1;
                    var stack = [[0, last]], limit = tolerance * tolerance, count = 2;
                    // Each split consumes an interior vertex; avoid recursive
                    // calls so a long route cannot exhaust the browser's stack.
                    for (var step = 0; stack.length && step < 2 * points.length; step += 1) {
                        var range = stack.pop(), a = range[0], b = range[1];
                        var dx = xy[b][0] - xy[a][0], dy = xy[b][1] - xy[a][1];
                        var length = dx * dx + dy * dy, farthest = limit, at = null;
                        for (var i = a + 1; i < b; i += 1) {
                            var x = xy[i][0] - xy[a][0], y = xy[i][1] - xy[a][1];
                            var t = length ? Math.max(0, Math.min(1, (x * dx + y * dy) / length)) : 0;
                            var distance = (x - t * dx) * (x - t * dx) + (y - t * dy) * (y - t * dy);
                            if (distance > farthest) { farthest = distance; at = i; }
                        }
                        if (at !== null) {
                            kept[at] = 1;
                            // Once too many vertices are essential, this
                            // tolerance cannot fit; do not finish a long walk
                            // whose result the search would discard anyway.
                            count += 1;
                            if (count > cap) { return null; }
                            stack.push([a, at], [at, b]);
                        }
                    }
                    if (stack.length) { throw new Error('course simplification exceeded its vertex bound'); }
                    return points.filter(function (point, index) { return kept[index]; });
                }
                var exact = simplified(0);
                if (exact) { return exact; }
                // Twice the furthest radius bounds every point-to-segment
                // distance, including a closed line whose ends coincide.
                var high = 2 * xy.reduce(function (radius, point) {
                    return Math.max(radius, Math.hypot(point[0], point[1]));
                }, 0);
                var low = 0, fitting = simplified(high);
                for (var search = 0; search < 40; search += 1) {
                    var middle = (low + high) / 2, candidate = simplified(middle);
                    if (!candidate) { low = middle; }
                    else { high = middle; fitting = candidate; }
                }
                return fitting;
            }

            function garminGpxOf(figure, shape, runs, plan, extra) {
                var titled = (plan && plan.name) ? plan.name : EXPORT.route.name;
                var told = planned(figure, shape, extra).concat([markingLine(shape.tally)]);
                var out = [];
                openGpx(out);
                metadataOf(out, titled, EXPORT.route.description, routeCredits(shape, runs));
                out.push('  <rte>');
                out.push('    <name>' + escaped(titled) + '</name>');
                out.push('    <desc>' + escaped(told.join(' \u00b7 ')) + '</desc>');
                garminPoints(runs).forEach(function (point) {
                    out.push('    <rtept lat="' + point.lat.toFixed(EXPORT.coordinateDecimals) +
                        '" lon="' + point.lon.toFixed(EXPORT.coordinateDecimals) + '">' +
                        (isNaN(point.ele) ? '' : '<ele>' + fixedEle(point.ele) + '</ele>') + '</rtept>');
                });
                out.push('  </rte>');
                out.push('</gpx>');
                return out.join('\n') + '\n';
            }

            // **The name is the point, and an anchor does not always carry
            // one.** `a.download` names the file on a desktop browser. On iOS
            // Safari a `blob:` URL is saved under the blob's own identifier and
            // the attribute is ignored, so a reader gets a line of hex where the
            // tour and the stage should be — reported from the device, on a
            // file this page had already named correctly.
            //
            // So the name travels two further ways, neither of which is that
            // attribute. It goes on a `File` rather than a `Blob`, riding with
            // the bytes instead of sitting on an element; and where the browser
            // offers a share sheet for files and the pointer is a finger, the
            // file goes through the sheet, which is how a phone saves anything,
            // reads `file.name`, and hands the route to a walking app in the
            // same gesture.
            //
            // **`canShare` decides that and not a user agent string.** Chrome on
            // Android refuses a `.gpx` there and falls through to the anchor,
            // which on Android names the file correctly; nothing here had to
            // know that in advance, and nothing has to be corrected when it
            // changes.
            function saveFile(name, body) {
                // A body already made into a blob keeps its own type: an archive
                // is not XML and relabelling it would say it was.
                var type = (body instanceof Blob) ? (body.type || 'application/octet-stream')
                    : 'application/gpx+xml';
                var file = (typeof File === 'function')
                    ? new File([body], name, {type: type})
                    : ((body instanceof Blob) ? body : new Blob([body], {type: type}));
                if (shareable(file)) {
                    navigator.share({files: [file]}).catch(function (failure) {
                        // **A closed sheet is not a failure**, and saving the
                        // file anyway would be doing something nobody asked for.
                        // Anything else falls back to the anchor: a wrongly named
                        // file beats a button that does nothing.
                        if (failure && failure.name === 'AbortError') { return; }
                        anchorFile(name, file);
                    });
                    return;
                }
                anchorFile(name, file);
            }

            // Whether this file should go through a sheet rather than a
            // download. The pointer is asked the same way everything else here
            // asks it — the class the chrome sets, so a check can drive it —
            // falling back to the query for a map built without a chrome.
            function shareable(file) {
                if (!window.navigator || !navigator.share || !navigator.canShare) { return false; }
                if (!map.getContainer().classList.contains('trails-coarse') &&
                        !(window.matchMedia && window.matchMedia('(pointer: coarse)').matches)) { return false; }
                try { return navigator.canShare({files: [file]}); } catch (refused) { return false; }
            }

            function anchorFile(name, file) {
                var url = URL.createObjectURL(file);
                var anchor = document.createElement('a');
                anchor.href = url;
                anchor.download = name;
                // Firefox saves a blob offered by a page opened off the disk
                // under the name given, and raises nothing — measured before
                // this was written rather than assumed. The anchor has to be in
                // the document for the click to count as one.
                document.body.appendChild(anchor);
                anchor.click();
                document.body.removeChild(anchor);
                setTimeout(function () { URL.revokeObjectURL(url); }, 0);
            }

            // ---- a zip, written here because nothing may be added to this page ----
            // **A tour cut into stages is several files and one download.** The
            // alternative was several downloads in a row, which rests on an
            // assumption about what a browser lets a page opened off the disk do
            // unattended; a zip rests on arithmetic. Measured before this was
            // written: a hand-made archive downloads from this page, keeps its
            // offered name, opens in Python with a clean `testzip()`, and every
            // member reads back byte for byte.
            //
            // Deflated where the browser can, stored where it cannot, and the
            // choice is not a guess: `CompressionStream('deflate-raw')` is the
            // twin of the `DecompressionStream` this page already inflates its
            // graph with, so anything that can read the payload can pack this.
            // Measured, 20,016 bytes to 55 and back unchanged.
            //
            // **Stamped with the time it was written, and that is a correction.**
            // Every entry went in at zero first, on the rule that no trackpoint
            // carries a time — and that rule is about the *route*: a time on a
            // trackpoint claims somebody walked there at that hour. When an
            // archive was written claims nothing about the walk, and the two are
            // different sentences about the word 'time'. Worse, zero is not
            // absent: the DOS field counts from 1980, so every member showed
            // **1980-01-01**, which is a wrong answer stated confidently rather
            // than no answer at all.
            //
            // One stamp for the whole archive, taken once: the members were
            // written in one act and dating them apart would say otherwise.
            function dosStamp(when) {
                var year = Math.max(1980, when.getFullYear());
                return {
                    // Seconds are stored halved, in the five bits that leaves.
                    time: (when.getHours() << 11) | (when.getMinutes() << 5) | (when.getSeconds() >> 1),
                    date: ((year - 1980) << 9) | ((when.getMonth() + 1) << 5) | when.getDate()
                };
            }

            function crc32(bytes) {
                var table = crc32.table, n, k, c, i;
                if (!table) {
                    table = crc32.table = new Uint32Array(256);
                    for (n = 0; n < 256; n += 1) {
                        c = n;
                        for (k = 0; k < 8; k += 1) { c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); }
                        table[n] = c >>> 0;
                    }
                }
                c = 0xFFFFFFFF;
                for (i = 0; i < bytes.length; i += 1) { c = table[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8); }
                return (c ^ 0xFFFFFFFF) >>> 0;
            }

            function packed(bytes) {
                if (typeof CompressionStream !== 'function') { return Promise.resolve(null); }
                try {
                    var stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate-raw'));
                    return new Response(stream).arrayBuffer().then(function (buffer) {
                        return new Uint8Array(buffer);
                    }, function () { return null; });
                } catch (failure) {
                    return Promise.resolve(null);
                }
            }

            function zipOf(files) {
                var encoder = new TextEncoder();
                var members = files.map(function (file) {
                    return {name: encoder.encode(file.name), body: encoder.encode(file.text)};
                });
                var stamp = dosStamp(new Date());
                return Promise.all(members.map(function (member) { return packed(member.body); }))
                    .then(function (compressed) {
                        var chunks = [], directory = [], at = 0;
                        function u16(v) { return [v & 0xFF, (v >>> 8) & 0xFF]; }
                        function u32(v) { return [v & 0xFF, (v >>> 8) & 0xFF, (v >>> 16) & 0xFF, (v >>> 24) & 0xFF]; }
                        members.forEach(function (member, index) {
                            // Only where it is actually smaller: a short file
                            // deflates to more than it was, and a zip that grew
                            // its own members is a bad advertisement for itself.
                            var small = compressed[index];
                            var deflated = !!small && small.length < member.body.length;
                            var stored = deflated ? small : member.body;
                            var sum = crc32(member.body);
                            var header = [].concat(u32(0x04034b50), u16(20), u16(0x0800), u16(deflated ? 8 : 0),
                                                   u16(stamp.time), u16(stamp.date), u32(sum), u32(stored.length),
                                                   u32(member.body.length), u16(member.name.length), u16(0));
                            chunks.push(new Uint8Array(header), member.name, stored);
                            directory.push(new Uint8Array(
                                [].concat(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(deflated ? 8 : 0),
                                          u16(stamp.time), u16(stamp.date), u32(sum), u32(stored.length),
                                          u32(member.body.length),
                                          u16(member.name.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(at))),
                                member.name);
                            at += header.length + member.name.length + stored.length;
                        });
                        var directoryAt = at, directoryLength = 0;
                        directory.forEach(function (piece) { chunks.push(piece); directoryLength += piece.length; });
                        chunks.push(new Uint8Array([].concat(u32(0x06054b50), u16(0), u16(0),
                                                             u16(members.length), u16(members.length),
                                                             u32(directoryLength), u32(directoryAt), u16(0))));
                        return new Blob(chunks, {type: 'application/zip'});
                    });
            }

            // ---- the panel -------------------------------------------------
            // **Two rows above the chart rather than five.** The panel is a
            // control over the map and every row it takes is map a reader
            // cannot see — and on a steep chain the rows cost more than space:
            // the scale is the coarser of length-per-width and relief-per-
            // height, so where the height binds, a row given back is resolution.
            // Measured on the 3 km chain below, 55 px of freed height take it
            // from 6.96 to 4.72 metres a pixel, which is where its readings
            // already are. Where the width binds — a long gentle route — it
            // changes nothing, and only zooming would.
            // **One row at the foot, whatever is going on.** A selected line
            // and a route being planned used to have a bar each -- this panel's
            // heading and plan mode's own -- standing one above the other while
            // both were true and saying two versions of *what you are looking
            // at*. This is that row, written once: what it is on the left, the
            // pages as one mark each in the middle, the file and the way out on
            // the right.
            //
            // **Under the pages and not over them.** It is the part that is
            // always there, and a control that is always there should not move
            // when something opens above it: the thumb that reaches the foot of
            // a phone finds it in the same place whether a page is open or not.
            var header = document.createElement('div');
            header.className = 'trails-profile-head';
            header.style.cssText = 'display:flex;gap:8px;align-items:center;user-select:none';

            // The name over the figures, which is the order plan mode's bar
            // already used for the same two kinds of sentence: what this is,
            // and how far it goes.
            var said = document.createElement('div');
            said.className = 'trails-profile-said';
            said.style.cssText = 'flex:1 1 auto;min-width:0;cursor:pointer';
            var name = document.createElement('b');
            name.className = 'trails-profile-name';
            name.style.cssText = 'display:block;font-size:14px;line-height:1.15;white-space:nowrap;' +
                'overflow:hidden;text-overflow:ellipsis';
            // **A way back that can be found.** Double-clicking the curve has
            // put the whole chain back since the zoom was built, and nothing
            // says so — an undiscoverable gesture is a gesture most readers do
            // not have. It shows only while there is something to go back from,
            // so the heading is one line again the moment there is not.
            var whole = document.createElement('button');
            whole.type = 'button';
            whole.className = 'trails-profile-whole';
            whole.textContent = 'whole chain';
            whole.title = 'Draw the whole of it again';
            whole.style.cssText = 'font:inherit;font-weight:400;font-size:11px;padding:2px 8px;flex:none;' +
                'border:1px solid var(--trails-rule);border-radius:10px;background:var(--trails-solid);' +
                'color:var(--trails-ink-2);cursor:pointer;display:none';
            var body = document.createElement('div');
            // **What scale the heights are drawn at, said where they are drawn
            // and switched there.** A picture at two possible scales has to say
            // which one it is at, and the place to say it is over the picture:
            // in the menu it would be a setting nobody connects to the shape
            // they are looking at, and in the row at the foot it would cost a
            // mark on a row that has none to spare.
            var lift = document.createElement('button');
            lift.type = 'button';
            lift.className = 'trails-profile-lift';
            lift.style.cssText = 'font:inherit;font-weight:400;font-size:11px;padding:2px 8px;flex:none;' +
                'border:1px solid var(--trails-rule);border-radius:10px;background:var(--trails-solid);' +
                'color:var(--trails-ink-2);cursor:pointer';
            // Under the name, not beside it. A line of 10.5 px carries about
            // forty characters beside three marks and a name, which is what the
            // plan bar has been measuring with all along; the figures that do
            // not fit are on the page the name opens.
            var summary = document.createElement('span');
            // **One line, and it ends in an ellipsis rather than wrapping.**
            // The three figures are 47 characters and a 390 px heading holds
            // about 40 of them beside a caret and three marks; wrapping would
            // put the head back at two rows, which is the defect this panel is
            // being cured of. What is cut off is one tap away, whole, and the
            // list it is cut from is the same list the sheet renders entire.
            summary.className = 'trails-profile-figures';
            summary.style.cssText = 'display:block;font-size:10.5px;line-height:1.15;font-weight:400;' +
                'color:var(--trails-ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis';
            said.appendChild(name);
            said.appendChild(summary);

            // **One mark per page, and the lit one is where you are.** It is the
            // same fact the dots over the page show and the same fact a swipe
            // changes: three renderings of one number, which is the only way a
            // reader who swiped and a reader who pressed end up in the same
            // place.
            // ---- what else the tap reached ----------------------------------
            // **Six sources can map one valley, and the tap takes the nearest
            // paint.** That is the right rule -- `_TouchReach` says why -- but
            // it is not an answer the reader gave: two lines a pixel apart are
            // a coin toss, and until now the coin was the whole of the choice.
            //
            // So a tap keeps what else it was within reach of, nearest first,
            // and this row offers them by the name of the source they came
            // from. **Only where there was a choice**: a row that is always
            // there costs a line of a 390 px panel for the ordinary tap that
            // hit one line and meant it.
            //
            // The planned route is in this row and can be in no other: its line
            // is drawn in a pane that takes no clicks at all -- deliberately, so
            // that it never stands between a reader and the trail under it --
            // so once a reader has chosen a line, this is the only way back to
            // it that is not switching plan mode on and off again.
            var choices = [];
            var picks = document.createElement('div');
            picks.className = 'trails-profile-picks';
            picks.style.cssText = 'display:none;gap:4px;align-items:center;padding:0 0 5px;' +
                // Scrolled rather than wrapped, for the reason the heading is:
                // a second row is the defect this panel was cured of, and six
                // sources will not fit on 390 px however short their names are.
                'overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none';

            // ---- the goal, on a page of its own -----------------------------------
            // **The way to a goal is a thing this panel shows, and it is drawn
            // like one.** Its row of switches used to stand above the heading
            // whenever a goal stood at all -- over every trail the reader tapped
            // to read, with the list of places under it -- because it was keyed
            // to *a goal stands* rather than to *the goal is what is showing*.
            // Reported from the phone: the goal's controls over a day walk's
            // figures. They are a page now, beside the profile, the way the
            // plan's points are a page beside the plan's profile: there when
            // the way to the goal is on the panel and gone with it. What the
            // row used to say -- the name, how many places it goes by, the
            // figures -- is the heading's, like every other route's.
            //
            // The switch that *sets* a goal stays in the rail, because arming
            // the next tap is what the rail does; what there is to do with one
            // once it is set -- which way to read it, add a stop, work it out
            // again -- heads this page. Being rid of it is in the goal's own
            // row of the list, behind its menu, where a reader looks for what
            // can be done with a thing and cannot press by accident.
            var goalNow = null;
            var goalRow = document.createElement('div');
            goalRow.className = 'trails-profile-goal';
            goalRow.style.cssText = 'display:none;gap:6px;align-items:center;padding:0 0 6px;font-size:11px';

            function goalButton(className, text, title, act) {
                var made = document.createElement('button');
                made.type = 'button';
                made.className = className;
                made.innerHTML = text;
                made.title = title;
                made.setAttribute('aria-label', title);
                made.style.cssText = 'font:inherit;font-size:11px;padding:2px 8px;flex:none;' +
                    'border:1px solid var(--trails-rule);border-radius:9px;cursor:pointer;' +
                    'background:var(--trails-solid);color:var(--trails-ink-2)';
                made.addEventListener('click', function (event) {
                    event.stopPropagation();
                    act();
                });
                return made;
            }

            // **Two readings of one point and not two goals.** Which of them a
            // reader wants changes on the ground -- routed in fog, straight at
            // it with the slope in front of them -- and having to set the goal
            // again to say so would be the page asking them to repeat
            // themselves.
            var goalStraight = goalButton('trails-profile-goal-way', 'Direct', 'Straight at the goal',
                                          function () { if (window.trailsGoal) { window.trailsGoal.way('direct'); } });
            var goalRouted = goalButton('trails-profile-goal-way', 'Routed', 'A way there over the network',
                                        function () { if (window.trailsGoal) { window.trailsGoal.way('routed'); } });
            // **Routed again now.** It happens on its own when the reader has
            // left the line; this is for the other case, where they have not
            // left it and know something the rule does not.
            var goalAgain = goalButton('trails-profile-goal-again', '\u21bb', 'Work the way out again',
                                       function () { if (window.trailsGoal) { window.trailsGoal.again(); } });
            // **A stop on the way, and its button is here rather than in the
            // rail.** The rail arms a tap for the one thing a reader does with
            // nothing set; a stop is something they add to a journey that
            // already exists, and this row is that journey.
            var goalStop = goalButton('trails-profile-goal-stop', '+', 'Add a stop on the way',
                                      function () {
                                          if (window.trailsChrome) { window.trailsChrome.aiming('stop'); }
                                      });
            // The two readings first and the two acts after a gap: a switch
            // between two states and a button that does something are not the
            // same kind of control, and the row says so by keeping them apart.
            var goalGap = document.createElement('span');
            goalGap.style.cssText = 'flex:1 1 auto';
            goalRow.appendChild(goalStraight);
            goalRow.appendChild(goalRouted);
            goalRow.appendChild(goalGap);
            goalRow.appendChild(goalStop);
            goalRow.appendChild(goalAgain);
            // **What the heading has no room for, said over the list.** The
            // heading shows three lines of figures and a goal's are the length,
            // the climb and the steepest; how much of the way was never a path
            // came fourth and went unsaid -- and a reader being shown a line
            // has to know which part of it is a promise and which a bearing
            // before they set off along it. Said here, on the page about the
            // way, where the reader is choosing how to read it.
            // **Stay on paths, as a switch with its state on its face.** It
            // was a tool in the menu with a lamp on the rail, and from the
            // phone: *I cannot see whether it is on*. It belongs where the way
            // it changes is read, under the Direct/Routed pair, and it is an
            // on/off switch and not a button -- a reader glancing at the page
            // sees the knob, not a colour they would have to remember. The
            // price it sets is the plan's as well as the goal's; the plan
            // reads it from the same closure.
            var goalPaths = document.createElement('button');
            goalPaths.type = 'button';
            goalPaths.className = 'trails-profile-goal-paths';
            goalPaths.setAttribute('role', 'switch');
            goalPaths.setAttribute('aria-checked', 'false');
            goalPaths.title = 'Open ground counts ten times a path, not three: the way keeps to the network wherever one reaches';
            goalPaths.style.cssText = 'display:flex;align-items:center;gap:10px;width:100%;margin:0 0 6px;padding:2px 3px;' +
                'border:0;background:none;font:inherit;font-size:11px;color:var(--trails-ink-2);cursor:pointer;text-align:left';
            goalPaths.innerHTML = '<span class="trails-profile-goal-paths-said" style="flex:1 1 auto">Stay on paths' +
                '<span style="display:block;font-size:10px;color:var(--trails-ink-3)">open ground counts ten times a path</span></span>' +
                '<span class="trails-profile-goal-paths-track" style="flex:none;position:relative;width:34px;height:20px;' +
                'border-radius:10px;background:var(--trails-rule);transition:background .15s">' +
                '<span class="trails-profile-goal-paths-knob" style="position:absolute;top:2px;left:2px;width:16px;height:16px;' +
                'border-radius:50%;background:var(--trails-solid);box-shadow:0 1px 2px rgba(0,0,0,0.3);transition:transform .15s"></span></span>';
            goalPaths.addEventListener('click', function (event) {
                event.stopPropagation();
                if (!window.trailsPlan || !window.trailsPlan.stayOnPaths) { return; }
                window.trailsPlan.stayOnPaths(!window.trailsPlan.stayOnPaths());
                paintGoal();
            });
            function paintPaths() {
                var on = !!(window.trailsPlan && window.trailsPlan.stayOnPaths && window.trailsPlan.stayOnPaths());
                goalPaths.setAttribute('aria-checked', String(on));
                var track = goalPaths.querySelector('.trails-profile-goal-paths-track');
                var knob = goalPaths.querySelector('.trails-profile-goal-paths-knob');
                track.style.background = on ? 'var(--trails-accent)' : 'var(--trails-rule)';
                knob.style.transform = on ? 'translateX(14px)' : 'none';
            }
            // **The way there, handed to the plan.** Asked for from the phone,
            // and it is the one road between the two halves of this page that
            // was missing: a goal is set in a moment and walked at once, a plan
            // is edited -- reordered, cut into stages, written to a file -- and
            // a reader who has set a goal with three stops on the way has laid
            // out exactly the thing the plan is for.
            //
            // A line in words at the foot of the places, not a glyph in the row
            // above them: the row is what is done *to* the goal while it stands,
            // and this ends it.
            var goalToPlan = document.createElement('button');
            goalToPlan.type = 'button';
            goalToPlan.className = 'trails-profile-goal-plan';
            goalToPlan.textContent = 'Make a plan of this way';
            goalToPlan.title = 'The places become the plan’s points, in order, and the goal comes off the map';
            goalToPlan.style.cssText = 'display:none;width:100%;text-align:left;font:inherit;font-size:12px;' +
                'margin-top:6px;padding:7px 10px;border:1px solid var(--trails-rule);border-radius:9px;' +
                'background:var(--trails-solid);color:var(--trails-ink-2);cursor:pointer';
            goalToPlan.addEventListener('click', function (event) {
                event.stopPropagation();
                if (window.trailsPlan && window.trailsPlan.fromGoal) { window.trailsPlan.fromGoal(); }
            });

            // **Everywhere the journey goes, in the order it is walked**, and
            // the reader's own position in front of it where the page knows it:
            // the way being looked at starts there, and a plan that began at the
            // first stop would be a different walk. Where it is not known the
            // plan starts at the first place, which is what a plan does anyway.
            //
            // **And the goal goes, because it has become the plan.** Two routes
            // over the same places, one of them editable and one of them not, is
            // a page that cannot say which is being walked.
            var goalNote = document.createElement('div');
            goalNote.className = 'trails-profile-goal-note';
            goalNote.style.cssText = 'display:none;padding:0 3px 5px;font-size:11px;color:var(--trails-ink-3);white-space:pre-line';

            // ---- the places on the way, as a list -------------------------------
            // **Every place the journey goes by, in order, and what can be done
            // with each.** Reported from the phone: with stops on the way the
            // only edit left was adding another. A stop could be taken away by
            // a tap the hint used to explain and nothing explains now; it could
            // not be moved at all; and the goal could not be moved without
            // every stop going with it. The marks on the map cannot carry any
            // of that -- a 16 px disc that took taps would take the taps meant
            // for the ground under it -- so it is said here, in words, the way
            // the plan's list says it about a route's points.
            //
            // The plan's rows and not the plan's list: that list is one node
            // lent between two owners and reordered by dragging; this is drawn
            // from what the goal control last said and edits through its
            // entry, so the two never hold a copy of each other's order.
            var goalList = document.createElement('div');
            goalList.className = 'trails-profile-stops';
            // No height and no scroller of its own: it is on a page, and a page
            // is as tall as the drawing and scrolls, which is what a page is
            // for.
            goalList.style.cssText = 'display:none;font-size:11px';
            //: Which row's menu is open, or -1. Kept across a repaint, because
            //: the goal control repaints this on every position fix and a menu
            //: that shut itself while a reader was reading it is a menu nobody
            //: can use while walking.
            var stopMenuAt = -1;

            //: One line of a row's menu, in the shape the plan's rows use: a
            //: labelled button and not a glyph, because four marks is four
            //: things to learn and a line says what it does.
            function stopStep(className, label, explains, may, act) {
                var made = document.createElement('button');
                made.type = 'button';
                made.className = className;
                made.textContent = label;
                made.title = explains;
                made.style.cssText = 'display:' + (may ? 'block' : 'none') + ';width:100%;' +
                    'text-align:left;font:inherit;font-size:12px;padding:7px 10px;border:0;' +
                    'background:none;color:var(--trails-ink-2);cursor:pointer;white-space:nowrap';
                made.addEventListener('click', function (event) {
                    event.stopPropagation();
                    stopMenuAt = -1;
                    act();
                });
                return made;
            }

            function paintStopList() {
                var stops = (goalNow && goalNow.at && goalNow.stops) ? goalNow.stops : [];
                goalList.style.display = stops.length ? '' : 'none';
                while (goalList.firstChild) { goalList.removeChild(goalList.firstChild); }
                if (!stops.length) { stopMenuAt = -1; return; }
                if (stopMenuAt >= stops.length) { stopMenuAt = -1; }
                var chrome = window.trailsChrome;
                var moving = chrome && chrome.aimingFor && chrome.aimingFor() === 'move' && chrome.aimingAt
                    ? chrome.aimingAt() : -1;
                stops.forEach(function (stop, at) {
                    var last = at + 1 === stops.length;
                    var row = document.createElement('div');
                    row.className = 'trails-profile-stop';
                    row.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:6px;' +
                        'padding:2px 3px;border-radius:3px;' +
                        // Lit while the next tap moves this one, the way the +
                        // lights while it adds one: the crosshair says a tap is
                        // armed and the row says what for.
                        (at === moving ? 'background:color-mix(in srgb, var(--trails-accent) 14%, transparent)' : '');
                    var number = document.createElement('span');
                    // The goal is the ring on the map and the ring here, not a
                    // number one past the last stop.
                    number.textContent = last ? '◎' : String(at + 1);
                    number.style.cssText = 'flex:none;min-width:14px;text-align:right;font-weight:600;color:#00a152';
                    var says = document.createElement('span');
                    says.className = 'trails-profile-stop-said';
                    says.textContent = stop.name;
                    says.title = stop.lat.toFixed(4) + ', ' + stop.lon.toFixed(4);
                    says.style.cssText = 'flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;' +
                        'white-space:nowrap;color:var(--trails-ink-2)';
                    // How far into the way it comes, which the marks cannot say
                    // and the row at the foot says only for the whole.
                    var far = document.createElement('span');
                    far.className = 'trails-profile-stop-far';
                    far.style.cssText = 'flex:none;color:var(--trails-ink-4);font-variant-numeric:tabular-nums';
                    far.textContent = typeof stop.into === 'number' ? (stop.into / 1000).toFixed(2) + ' km' : '';

                    var menu = document.createElement('div');
                    menu.className = 'trails-profile-stopmenu';
                    // In the row and not over it, for the reason the plan's is:
                    // floated, it was clipped by the scroller on every row near
                    // the foot.
                    menu.style.cssText = 'display:' + (at === stopMenuAt ? 'block' : 'none') + ';width:100%;' +
                        'margin:4px 0 2px;background:var(--trails-sunk);border:1px solid var(--trails-rule);' +
                        'border-radius:7px;padding:3px';
                    // **Moved by the next tap, which is the gesture that set
                    // it.** Not dragged: HTML5 dragging does not exist under a
                    // finger and a 16 px disc on a map is no handle. Arming a
                    // tap costs one press and works wherever setting one does.
                    menu.appendChild(stopStep('trails-profile-stop-move',
                        last ? '⌖  Move the goal' : '⌖  Move this stop',
                        last ? 'The next tap on the map puts the goal there and keeps the stops'
                             : 'The next tap on the map puts this stop there', true,
                        function () { if (window.trailsChrome) { window.trailsChrome.aiming('move', at); } }));
                    menu.appendChild(stopStep('trails-profile-stop-up', '↑  One place earlier',
                        'Walk to this stop one place earlier', !last && at > 0,
                        function () { if (window.trailsGoal) { window.trailsGoal.stepStop(at, -1); } }));
                    menu.appendChild(stopStep('trails-profile-stop-down', '↓  One place later',
                        'Walk to this stop one place later', !last && at + 2 < stops.length,
                        function () { if (window.trailsGoal) { window.trailsGoal.stepStop(at, 1); } }));
                    var out = stopStep('trails-profile-stop-out', 'Remove this stop',
                        'Take this stop out and walk straight on to the next', !last,
                        function () { if (window.trailsGoal) { window.trailsGoal.dropStop(at); } });
                    out.style.color = 'var(--trails-extreme, #c62828)';
                    menu.appendChild(out);
                    // **Not *drop the goal*.** That was here for a while, in
                    // words, and was asked for from the phone as *how do I
                    // leave this now*: two taps down a page is where nobody
                    // looks for the way out. It is the panel's own button now,
                    // drawn as a struck flag while the way is what it shows.

                    var more = document.createElement('button');
                    more.type = 'button';
                    more.className = 'trails-profile-stop-more';
                    more.textContent = '⋯';
                    more.title = last ? 'What can be done with the goal' : 'What can be done with this stop';
                    more.setAttribute('aria-label', more.title);
                    more.setAttribute('aria-expanded', String(at === stopMenuAt));
                    more.style.cssText = 'flex:none;font:inherit;font-size:15px;line-height:1;padding:0 5px;' +
                        'border:0;background:none;color:var(--trails-ink-4);cursor:pointer';
                    more.addEventListener('click', function (event) {
                        event.stopPropagation();
                        stopMenuAt = stopMenuAt === at ? -1 : at;
                        paintStopList();
                    });
                    row.appendChild(number);
                    row.appendChild(says);
                    row.appendChild(far);
                    row.appendChild(more);
                    row.appendChild(menu);
                    goalList.appendChild(row);
                });
            }

            function paintGoal() {
                var standing = !!(goalNow && goalNow.at);
                goalRow.style.display = standing ? 'flex' : 'none';
                // Offered while there is a way to hand over, which is whenever a
                // goal stands: the places are places whether or not the page
                // has worked out a line between them yet.
                goalToPlan.style.display = standing ? 'block' : 'none';
                paintStopList();
                if (!standing) { return; }
                var routed = goalNow.way === 'routed';
                paintPaths();
                // What the row used to say here -- the name, how many places
                // the way goes by, the kilometres, the climb -- the heading
                // says now, from the series the goal control hands over: its
                // label carries the name and the stops, its lines carry the
                // figures. One derivation, and the goal reads like every other
                // route on this panel. What is left for this page is the one
                // line the heading cannot fit.
                var notes = [];
                if (goalNow.working) { notes.push('Working out the way\u2026'); }
                else if (goalNow.line && goalNow.straight > 1) {
                    notes.push((goalNow.straight / 1000).toFixed(2) + ' km of it drawn straight, not a path');
                    // **And what that straight part does**, one line each:
                    // the rivers it wades through with their width, and the
                    // worst gradient on it. Both are what a reader decides a
                    // straight line by, and neither is priced -- see the
                    // river table for why.
                    notes = notes.concat(goalNow.rivers || []);
                    if (goalNow.steepest !== null && goalNow.steepest !== undefined) {
                        notes.push('steepest ' + goalNow.steepest + ' % on the straight part');
                    }
                // **Said, and not silently fallen back on.** A routed goal off
                // the network is drawn straight at, which is the right thing to
                // draw and the wrong thing to leave unexplained: a reader would
                // read the line as a way somebody had checked.
                } else if (!goalNow.line && routed) { notes.push('No way there \u2014 drawn straight'); }
                var note = notes.join('\n');
                goalNote.textContent = note;
                goalNote.style.display = note ? '' : 'none';
                var arming = (window.trailsChrome && window.trailsChrome.aimingFor)
                    ? window.trailsChrome.aimingFor() : null;
                goalStop.style.background = arming === 'stop' ? 'var(--trails-accent)' : 'var(--trails-solid)';
                goalStop.style.borderColor = arming === 'stop' ? 'var(--trails-accent)' : 'var(--trails-rule)';
                goalStop.style.color = arming === 'stop' ? 'var(--trails-on-accent)' : 'var(--trails-ink-2)';
                goalStop.setAttribute('aria-pressed', String(arming === 'stop'));
                [[goalStraight, !routed], [goalRouted, routed]].forEach(function (each) {
                    var lit = each[1];
                    each[0].style.background = lit ? 'var(--trails-accent)' : 'var(--trails-solid)';
                    each[0].style.borderColor = lit ? 'var(--trails-accent)' : 'var(--trails-rule)';
                    each[0].style.color = lit ? 'var(--trails-on-accent)' : 'var(--trails-ink-2)';
                    each[0].setAttribute('aria-pressed', String(lit));
                });
                // Both readings are worked out from where the reader is, so both
                // can be out of date and both can be asked for again.
                goalAgain.style.display = 'flex';
                goalAgain.disabled = !!goalNow.working;
            }

            var pill = document.createElement('div');
            pill.className = 'trails-profile-pages';
            pill.style.cssText = 'flex:none;display:none;border:1px solid var(--trails-rule);' +
                'border-radius:9px;overflow:hidden;background:var(--trails-solid)';
            // **Two switches at the end of the heading, and they are not the
            // same switch.** The heading itself folds: the drawing goes and the
            // line of figures stays, which is what a reader wants who is coming
            // straight back. The × puts the panel away altogether. Running them
            // together would mean one gesture for two intentions, and the fold
            // was already the wrong answer for *put this away* — it leaves a
            // 35 px bar of nothing over the map.
            var tools = document.createElement('span');
            tools.style.cssText = 'flex:none;display:flex;gap:2px;align-items:center';
            // **The way out, and it is the selection that goes.** It used to put
            // the panel away and leave the line selected underneath, which meant
            // a reader who wanted the map back had to press this and then find
            // the line again to undo the highlight. Folding the pages is what
            // the lit mark does; this is *done with this thing*. While a route
            // is being planned it is plan mode that is done with, and the mark
            // says so.
            var hide = document.createElement('button');
            hide.type = 'button';
            hide.className = 'trails-profile-hide';
            hide.innerHTML = '\u00d7';
            hide.title = 'Put this away';
            hide.setAttribute('aria-label', 'Put this away');
            hide.style.cssText = 'font:inherit;font-size:16px;line-height:1;border:1px solid var(--trails-rule);' +
                'border-radius:8px;background:var(--trails-solid);color:var(--trails-ink-3);cursor:pointer;' +
                'width:40px;height:40px;display:none;align-items:center;justify-content:center';
            // **The same flag the lit switch on the map carries, struck
            // through.** While the panel is drawing the way to a goal this
            // button is done with the goal, and it has to look like it: it sits
            // where a thumb goes to put a panel away, and a × there would be
            // read as one. Drawn in place rather than through the chrome's icon
            // set, which is another function's scope.
            var GOAL_STRUCK = '<svg width="17" height="17" viewBox="0 0 18 18" fill="none" ' +
                'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" ' +
                'aria-hidden="true"><path d="M5 16.2V2.6"/><path d="M5 3.4h8.3l-2.1 3.1 2.1 3.1H5Z"/>' +
                '<path d="M2.4 15.6 15.6 2.4"/></svg>';
            hide.addEventListener('click', function (event) {
                event.stopPropagation();
                // Planning is the thing being finished where one is running;
                // otherwise it is the selection, and clearing that is what the
                // click-highlight and this panel already agree means *nothing is
                // chosen* -- so it goes through the one entry both of them have.
                if (planNow && window.trailsPlan) { window.trailsPlan.toggle(false); return; }
                // **And the way to a goal is the goal.** It used to be a line
                // in the goal's own menu, two taps down a page, and was asked
                // for from the phone as *how do I leave this now*. Dropping the
                // goal takes every stop with it, and stops are work: asked
                // about once where there are any, and not for a goal alone,
                // which is a tap to set again. The same question the offline
                // panel asks before deleting the terrain it keeps.
                if (selected && selected.goal && window.trailsGoal) {
                    var stops = window.trailsGoal.state().stops.length - 1;
                    if (stops > 0 && !window.confirm('Drop the goal and ' + stops +
                            (stops === 1 ? ' stop?' : ' stops?'))) { return; }
                    window.trailsGoal.clear();
                    return;
                }
                if (window.trailsHighlight) { window.trailsHighlight.clear(); }
                // **And the goal's own note that this panel is drawing it.** A
                // stale yes would let the next fix put the way back on a panel
                // the reader just put away -- the goal stands, the flag stays
                // lit, and a tap on empty ground is what puts the page away
                // while keeping it.
                if (window.trailsGoal) { window.trailsGoal.letGo(); }
                present(null);
            });
            header.appendChild(said);
            header.appendChild(pill);
            header.appendChild(tools);
            var chart = document.createElementNS(SVG, 'svg');
            // **Named, because it is no longer the only `<svg>` in the panel.**
            // The download mark carries one now, and it stands in the heading --
            // ahead of the chart in document order -- so `panel svg` quietly
            // began meaning a 17 px icon. Driven, a drag aimed at the curve
            // landed on the mark, pressed it, and folded the panel: the same
            // family as addressing a button by which comes first, and it took
            // one run to appear.
            chart.setAttribute('class', 'trails-profile-chart');
            chart.setAttribute('height', chartHeight);
            chart.style.cssText = 'display:block;width:100%;height:' + chartHeight + 'px;cursor:crosshair';
            // What the colours mean, once, beside the figures. A curve that
            // changes colour is unreadable without it.
            // **One derivation, two renderings.** The key is drawn in the sheet
            // the *i* opens and, on a page built without a chrome, in the panel
            // itself. A second wording of *gentle under 15 %* would be the
            // two-panel mistake in miniature, and this map has made it twice.
            function bandLabel(at) {
                var band = GRADE.bands[at];
                if (!at) { return band.label + ' under ' + GRADE.bands[1].from + ' %'; }
                return band.label + (GRADE.bands[at + 1]
                    ? ' ' + band.from + '–' + GRADE.bands[at + 1].from + ' %'
                    : ' over ' + band.from + ' %');
            }
            function bandSwatch(width, colour, dashed) {
                var swatch = document.createElement('span');
                swatch.style.cssText = 'display:inline-block;width:14px;height:0;vertical-align:middle;' +
                    'margin:0 6px 0 0;border-top:' + width + 'px ' + (dashed ? 'dashed ' : 'solid ') + colour;
                return swatch;
            }
            var key = document.createElement('div');
            key.style.cssText = 'margin:0 0 2px;color:var(--trails-ink-4);font-size:11px';
            GRADE.bands.forEach(function (band, index) {
                var swatch = bandSwatch(band.width, band.colour, false);
                if (index) { swatch.style.marginLeft = '12px'; }
                var caption = document.createElement('span');
                caption.textContent = bandLabel(index);
                key.appendChild(swatch);
                key.appendChild(caption);
            });
            // And what the dash means, shown only while something in the panel
            // is dashed. A chain is never drawn straight across anything, so on
            // the phase-4 panel this row never appears.
            var freeKey = document.createElement('span');
            freeKey.style.display = 'none';
            var freeSwatch = document.createElement('span');
            freeSwatch.style.cssText = 'display:inline-block;width:14px;height:0;vertical-align:middle;margin:0 4px 0 12px;' +
                'border-top:1.6px dashed ' + GRADE.bands[0].colour;
            var freeCaption = document.createElement('span');
            freeCaption.textContent = 'drawn straight, not a path';
            freeKey.appendChild(freeSwatch);
            freeKey.appendChild(freeCaption);
            key.appendChild(freeKey);
            // The download, and beside it what the file will actually contain
            // rather than a generic notice: a stretch of FKB is unproblematic, a
            // stretch of OSM is share-alike and a stretch of UT.no is
            // non-commercial, and the reader should know which before pressing
            // the button rather than afterwards.
            // **Text, not a row of boxes.** As flex items the button, the
            // count and the licences were three things that either fitted on one
            // line or did not: a route drawing on seven sources names them in
            // some 300 characters, so the whole list moved to a line of its own
            // and left the count sitting alone beside the button. Laid out as a
            // sentence it starts where the count ends and wraps mid-list, which
            // is what a chain has always looked like — the chain's list is just
            // short enough that flex never had to choose.
            var offer = document.createElement('div');
            offer.style.cssText = 'margin:4px 0 2px;display:none';
            // **A mark, like every other tool on this page.** The plan control
            // gave up its words a fortnight ago and this was the last panel
            // speaking in them. The same glyph the plan control's save carries,
            // written here rather than reached for across a scope: two controls
            // agreeing today is not one derivation.
            var download = document.createElement('button');
            download.type = 'button';
            download.className = 'trails-profile-gpx';
            download.innerHTML = '<svg width="17" height="17" viewBox="0 0 18 18" fill="none" ' +
                'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" ' +
                'aria-hidden="true"><path d="M9 3.2v9.2"/><path d="M5.6 9 9 12.4 12.4 9"/>' +
                '<path d="M3.4 11.6v2.6a1 1 0 0 0 1 1h9.2a1 1 0 0 0 1-1v-2.6"/></svg>';
            download.title = 'Download this as a GPX file';
            download.setAttribute('aria-label', 'Download this as a GPX file');
            // A box the size of the mark beside it: the row at the foot is what
            // a thumb meets, and 40 px is what the coarse-pointer rules on this
            // page already give every other control in it.
            download.style.cssText = 'font:inherit;line-height:0;border:1px solid var(--trails-rule);' +
                'border-radius:8px;background:var(--trails-solid);color:var(--trails-accent);' +
                'cursor:pointer;width:40px;height:40px;display:none;align-items:center;' +
                'justify-content:center';
            var carries = document.createElement('span');
            // Named so a check can read what a selection put there rather than
            // the whole row it sits in: this one is the only part of it that is
            // about the file and not about the ground.
            carries.className = 'trails-profile-carries';
            carries.style.cssText = 'color:var(--trails-ink-2);margin-right:8px';
            var licensed = document.createElement('span');
            licensed.className = 'trails-profile-licences';
            licensed.style.cssText = 'color:var(--trails-ink-4);font-size:11px';
            // What kind of ground the file covers, which only a route states:
            // its three marking buckets, and the length no source records a path
            // along. A chain leaves this row empty. A line of its own and
            // deliberately so: the licences say who may be asked about the file,
            // this says what ground it covers, and run together the two read as
            // one longer list of sources.
            var noted = document.createElement('span');
            noted.className = 'trails-profile-ground';
            noted.style.cssText = 'color:var(--trails-ink-4);font-size:11px;display:block;margin-top:2px';
            // The button and its menu travel together, so the menu can be
            // placed against the button rather than against the row.
            var saveWrap = document.createElement('span');
            saveWrap.style.cssText = 'position:relative;display:flex';
            var saveMenu = document.createElement('div');
            saveMenu.className = 'trails-profile-savemenu';
            saveMenu.style.cssText = 'display:none;position:absolute;right:0;bottom:100%;z-index:6;' +
                'min-width:180px;margin-bottom:6px;background:var(--trails-solid);' +
                'border:1px solid var(--trails-edge);border-radius:7px;padding:3px;' +
                'box-shadow:0 2px 10px rgba(0,0,0,0.22)';
            function saveEntry(label, explains, act) {
                var made = document.createElement('button');
                made.type = 'button';
                made.textContent = label;
                made.title = explains;
                made.style.cssText = 'display:block;width:100%;text-align:left;font:inherit;font-size:12px;' +
                    'padding:9px 10px;border:0;background:none;color:var(--trails-ink-2);cursor:pointer;' +
                    'white-space:nowrap';
                made.addEventListener('click', function (event) {
                    event.stopPropagation();
                    saveMenu.style.display = 'none';
                    act();
                });
                return made;
            }
            saveWrap.appendChild(download);
            saveWrap.appendChild(saveMenu);
            tools.appendChild(saveWrap);
            tools.appendChild(hide);
            // **The *i* is a page now, not a button beside the curve.** It used
            // to open the chrome's full-screen sheet, which is the defect this
            // panel is being cured of: a reader who asked what the curve was
            // drawn from lost the curve, the map and the line they had tapped
            // to get there. Everything it showed is on the second page, which
            // stands where the first one stands.
            //
            // What is left here is the row at the foot of the profile page --
            // the colour key, the count, the licences, the ground -- which is
            // below the drawing rather than above it and therefore costs the
            // curve nothing. It was hidden entirely while a sheet existed to
            // hold it; there is no sheet, so it is back where it can be scrolled
            // to.
            function showLicences() {
                meta.style.display = '';
                licensed.style.display = '';
                noted.style.display = noted.textContent ? 'block' : 'none';
            }
            function detailFigures(withFigures) {
                var box = document.createElement('div');
                box.style.cssText = 'font-size:13px;line-height:1.65;color:var(--trails-ink-2)';
                // The same lines the heading shows the first three of, in the
                // same order. One derivation, two renderings.
                // The figures, and after them what the file would hold -- a count
                // that used to sit beside the button and is about the file
                // rather than about the walk, which is why it reads better at
                // the end of this list than in a heading nobody asked.
                var figures = withFigures
                    ? saidLines.concat(carries.textContent ? [carries.textContent] : []) : [];
                figures.forEach(function (line, at) {
                    var row = document.createElement('div');
                    row.style.cssText = 'padding:3px 0' +
                        (at < 3 ? ';font-weight:600' : ';color:var(--trails-ink-3)') +
                        (at ? ';border-top:1px solid var(--trails-rule-soft)' : '');
                    row.textContent = line;
                    box.appendChild(row);
                });
                // **Nothing below this belongs to a thing with no curve.** A
                // quay was told which sources the *route* drew on and how a
                // gradient is coloured -- both read off rows the panel had
                // filled in for whatever was selected before it.
                if (!(selected && selected.shape)) { return box; }
                // **The ground before the sources.** What a walk covers is about
                // this route; who may be asked about it is about the file. The
                // nearer question first.
                [[noted.textContent, 'The ground this covers'],
                 [licensed.textContent, 'Sources and licences']].forEach(function (part) {
                    if (!part[0]) { return; }
                    var head = document.createElement('div');
                    head.style.cssText = 'margin-top:14px;font-weight:600;font-size:12px;color:var(--trails-ink-3)';
                    head.textContent = part[1];
                    var said = document.createElement('div');
                    said.style.cssText = 'margin-top:3px;font-size:12px;color:var(--trails-ink-3);line-height:1.6';
                    // Read off the element that shows it rather than composed
                    // again: one sentence, in two places, from one derivation.
                    said.textContent = part[0];
                    box.appendChild(head);
                    box.appendChild(said);
                });
                // **And the colour key last, because it is the only thing here
                // that says nothing about this route.** Every line above it is a
                // measurement of the walk in hand; this explains a drawing rule
                // that holds for every walk there will ever be. It used to stand
                // permanently in the panel, two rows of it on a phone, for a
                // question a reader asks once.
                var colours = document.createElement('div');
                colours.className = 'trails-profile-key';
                colours.style.cssText = 'margin-top:3px;font-size:12px;line-height:1.9;color:var(--trails-ink-3)';
                GRADE.bands.forEach(function (band, at) {
                    var row = document.createElement('div');
                    row.appendChild(bandSwatch(band.width, band.colour, false));
                    row.appendChild(document.createTextNode(bandLabel(at)));
                    colours.appendChild(row);
                });
                // Shown only where something in the panel is dashed, which is
                // the rule the panel's own key already kept: a chain is never
                // drawn straight across anything.
                if (freeKey.style.display !== 'none') {
                    var free = document.createElement('div');
                    free.appendChild(bandSwatch(1.6, GRADE.bands[0].colour, true));
                    free.appendChild(document.createTextNode('drawn straight, not a path'));
                    colours.appendChild(free);
                }
                var coloured = document.createElement('div');
                coloured.style.cssText = 'margin-top:14px;font-weight:600;font-size:12px;color:var(--trails-ink-3)';
                coloured.textContent = 'How the curve is coloured';
                box.appendChild(coloured);
                box.appendChild(colours);
                return box;
            }

            offer.appendChild(carries);
            offer.appendChild(licensed);
            offer.appendChild(noted);
            // The button and what the file carries on the left, the colour key
            // on the right: one row of things about the drawing rather than
            // three stacked above it. `key` keeps its own margins, so it is
            // pushed rather than padded apart.
            var meta = document.createElement('div');
            // Named, because a check that addressed it by its place in the box
            // was measuring whichever child happened to be second -- and the box
            // has just gained two.
            meta.className = 'trails-profile-meta';
            meta.style.cssText = 'display:flex;gap:16px;align-items:baseline;justify-content:space-between;flex-wrap:wrap';
            key.style.marginLeft = 'auto';
            meta.appendChild(offer);
            meta.appendChild(key);

            // The drawing first and what it was drawn from under it. `meta`
            // stood above the chart while it was hidden on every chromed page
            // and its position was nobody's business; it is visible again, and
            // a licence line over a curve is a licence line in the way.
            body.appendChild(chart);
            body.appendChild(meta);
            // The way back to the whole chain sits over the drawing's own
            // corner rather than in the row at the foot: that row is 40 px of
            // marks on a phone and has nothing to spare, and this belongs to
            // the picture it undoes.
            body.style.position = 'relative';
            whole.style.position = 'absolute';
            whole.style.top = '2px';
            whole.style.right = '2px';
            whole.style.zIndex = '2';
            body.appendChild(whole);
            // The opposite corner from the way back, because both can stand at
            // once. Over the axis rather than over the curve: the top left of a
            // profile is the one corner the drawing itself never reaches, since
            // the band is centred in the box and the labels are outside it.
            lift.style.position = 'absolute';
            lift.style.top = '2px';
            lift.style.left = '2px';
            lift.style.zIndex = '2';
            lift.addEventListener('click', function (event) {
                event.stopPropagation();
                setLift(!lifted);
            });
            body.appendChild(lift);

            // **Kept, because it is a decision about reading and not about this
            // route.** A reader who wants the ground's own scale wants it for
            // the next line they tap as well, and for tomorrow.
            function setLift(want) {
                lifted = !!want;
                try {
                    if (lifted) { window.localStorage.removeItem(SCALE_KEY); }
                    else { window.localStorage.setItem(SCALE_KEY, 'true'); }
                } catch (blocked) { /* a browser that keeps nothing still draws */ }
                render();
                paintLift();
            }

            function paintLift() {
                // Only over a drawing: there is nothing to say about the scale
                // of a table.
                var drawing = !!(selected && selected.shape && !selected.detail);
                lift.style.display = drawing ? '' : 'none';
                if (!drawing) { return; }
                var factor = liftNow >= 1.05 ? '×' + (liftNow >= 9.95 ? Math.round(liftNow) : liftNow.toFixed(1)) : '1:1';
                lift.textContent = lifted ? factor : '1:1';
                lift.title = lifted
                    ? 'Heights are drawn ' + factor + ' the scale of the distance, so a long route has a shape. Tap for the ground’s own scale.'
                    : 'Heights and distances are drawn at one scale, so the angle drawn is the angle on the ground. Tap to lift the heights.';
                lift.setAttribute('aria-label', lift.title);
                lift.setAttribute('aria-pressed', String(!lifted));
            }

            // ---- the pages ---------------------------------------------------
            // **Everything about the thing in hand, side by side, in the panel
            // it is already looking at.** A tapped line used to answer in a
            // sheet over the whole screen -- the line gone, the curve gone, the
            // map gone -- and the *i* under the curve answered in the same sheet
            // about something else, with no way back to the first. Both are
            // pages here: the same box, the same width, one swipe apart, and the
            // row at the foot says which one is showing.
            //
            // **What a page is worth is what it costs the map**, so a page is as
            // tall as it needs and never taller than 46 % of the map. The
            // profile is the exception and keeps the height the reader dragged
            // it to: on a steep chain that height is resolution, which is the
            // one thing on this panel a reader may want more of.
            var pagesBox = document.createElement('div');
            pagesBox.className = 'trails-profile-pagesbox';
            pagesBox.style.cssText = 'overflow:hidden;position:relative';
            var track = document.createElement('div');
            track.className = 'trails-profile-track';
            track.style.cssText = 'display:flex;height:100%;align-items:stretch';
            pagesBox.appendChild(track);
            // Three renderings of one number -- the dots, the lit mark in the
            // row below, and the page itself -- because a reader who swiped and
            // a reader who pressed a mark have to end up believing the same
            // thing about where they are.
            // **The page takes a wheel it can use and passes on the rest.**
            // The same bargain the legend and the point list strike: a list that
            // will not scroll is as useless as a map that will not zoom, and
            // only one of them can have any one turn. The curve is not in it --
            // it has a bargain of its own about zooming into the readings.
            pagesBox.addEventListener('wheel', function (event) {
                var page = pages[pageAt];
                if (!page || page.kind === 'profile') { return; }
                var room = page.node.scrollHeight - page.node.clientHeight;
                if (room <= 0) { return; }
                if (event.deltaY < 0 ? page.node.scrollTop > 0 : page.node.scrollTop < room - 1) {
                    event.stopPropagation();
                }
            }, {passive: true});

            var pips = document.createElement('div');
            pips.className = 'trails-profile-pips';
            pips.style.cssText = 'display:none;justify-content:center;gap:5px;padding:3px 0 5px';

            var pages = [], pageAt = 0;
            //: What the pages are about, so that the same thing arriving twice
            //: is not treated as a second thing. See `present`.
            var showingWhat = null;
            //: The popup of whatever is selected, handed over by the chrome:
            //: markup, because that is what a popup is made of.
            var detailHtml = null;
            //: What plan mode is doing, pushed in by the chrome. Null while none
            //: is running -- and a running plan with no points is still a plan,
            //: which is why this is not counted in points.
            var planNow = null;
            //: Whether the pages are showing at all. The row at the foot stands
            //: whether they are or not; this is the one the reader folds.
            var pagesOpen = true;

            function markNode(kind) {
                if (kind === 'details') { return document.createTextNode('\u24d8'); }
                if (kind === 'list') { return document.createTextNode('\u2630'); }
                var svg = document.createElementNS(SVG, 'svg');
                svg.setAttribute('viewBox', '0 0 16 16');
                svg.setAttribute('width', '17');
                svg.setAttribute('height', '17');
                var line = document.createElementNS(SVG, 'polyline');
                line.setAttribute('points', '1,13 5,7 8,10 12,3 15,8');
                line.setAttribute('fill', 'none');
                line.setAttribute('stroke', 'currentColor');
                line.setAttribute('stroke-width', '1.7');
                line.setAttribute('stroke-linejoin', 'round');
                svg.appendChild(line);
                return svg;
            }

            // The details, built when the page is made rather than when the
            // popup arrives: the figures change under it as the selection does.
            var detailBox = document.createElement('div');
            detailBox.className = 'trails-profile-detail';
            detailBox.style.cssText = 'padding:0 0 6px';
            // Two rows into a table somebody else built, in that table's own
            // hand: the popup writes `<td>` for a label and `<td><b>` for a
            // value, and a row added here that looked like anything else would
            // read as a second list rather than as the end of the first.
            function addRow(table, label, value) {
                if (!table || !value) { return; }
                // **Before the first row that spans the table**, which is the
                // heading over what somebody else published: these two are this
                // map's own figures and belong with the rest of them. Written as
                // a search for that row rather than as a count of the ones above
                // it, because a line with no links has neither.
                var rows = table.rows, at = null;
                for (var i = 0; i < rows.length && at === null; i += 1) {
                    if (rows[i].cells.length < 2 || rows[i].cells[0].colSpan > 1) { at = rows[i]; }
                }
                var row = document.createElement('tr');
                var said = document.createElement('td');
                said.style.cssText = 'padding:2px 8px 2px 0;color:var(--trails-ink-3)';
                said.textContent = label;
                var shown = document.createElement('td');
                shown.style.cssText = 'padding:2px 0';
                var bold = document.createElement('b');
                bold.textContent = value;
                shown.appendChild(bold);
                row.appendChild(said);
                row.appendChild(shown);
                if (at) { at.parentNode.insertBefore(row, at); } else { table.appendChild(row); }
            }

            function fillDetail() {
                detailBox.innerHTML = '';
                var table = null;
                if (detailHtml) {
                    var held = document.createElement('div');
                    held.innerHTML = detailHtml;
                    detailBox.appendChild(held);
                    table = held.querySelector('table');
                }
                // **The figures are said once.** The popup's own table already
                // carries the length, the climb, the steepest and the high
                // point; the list underneath said all four again and added two.
                // Those two go into the table instead, and the list is only
                // drawn where there is no table -- a planned route, which has no
                // popup at all.
                if (table && selected && selected.shape) {
                    // **The low point is not one of these any more.** It came in
                    // here because the popup had only the high one; the two ends
                    // of a climb are one fact and are written as one row where
                    // the rest of the figures are written. What is left is the
                    // count, which is about the file rather than about the walk
                    // and exists nowhere but here -- so a place, which has no
                    // file, gets neither.
                    var counted = carries.textContent || '';
                    addRow(table, 'Points read',
                           counted.indexOf(' points') > 0 ? counted.replace(' points', '') : '');
                }
                var figures = detailFigures(!table);
                if (detailHtml && figures.firstChild) {
                    figures.style.marginTop = '10px';
                    figures.style.paddingTop = '8px';
                    figures.style.borderTop = '1px solid var(--trails-rule)';
                }
                detailBox.appendChild(figures);
            }

            // Plan mode's own list, which is the same node the plan control
            // built: adopted rather than drawn again, so the rows a reader
            // reorders and the rows this page shows cannot come apart. What is
            // added here is the one edit that belongs beside a list of changes
            // -- taking the last one back. Starting over does not: it is not an
            // edit, it undoes the lot, and a control that can do that should
            // take some finding. It stays in the plan panel behind the menu.
            var pointsPage = document.createElement('div');
            pointsPage.className = 'trails-profile-list';
            pointsPage.style.cssText = 'padding:0 0 6px';
            // **The name and the way back on one line.** They were two rows for
            // one row's worth of content -- a field across the width and a
            // button alone under it -- and on a phone every row here is a
            // waypoint a reader cannot see. The name takes what is left when
            // the button has what it needs.
            var undoRow = document.createElement('div');
            undoRow.style.cssText = 'display:flex;align-items:center;gap:8px;padding:0 0 4px';
            var undoOne = document.createElement('button');
            undoOne.type = 'button';
            undoOne.className = 'trails-profile-undo';
            undoOne.innerHTML = '\u21b6 undo';
            undoOne.title = 'Undo the last change';
            undoOne.setAttribute('aria-label', 'Undo the last change');
            undoOne.style.cssText = 'font:inherit;font-size:11px;padding:6px 10px;cursor:pointer;' +
                'border:1px solid var(--trails-rule);border-radius:10px;background:var(--trails-solid);' +
                'color:var(--trails-ink-2)';
            undoOne.addEventListener('click', function (event) {
                event.stopPropagation();
                if (window.trailsPlan) { window.trailsPlan.undo(); }
            });
            undoRow.appendChild(undoOne);
            pointsPage.appendChild(undoRow);

            // **The way to the goal's own page: the switches over the places.**
            // Built here beside the plan's list page and put into the track
            // with it; what is on it is drawn by `paintGoal`, from what the
            // goal control last said, and the page is wanted exactly while the
            // panel is showing the goal's series.
            var placesPage = document.createElement('div');
            placesPage.className = 'trails-profile-places';
            placesPage.style.cssText = 'padding:0 0 6px';
            placesPage.appendChild(goalRow);
            placesPage.appendChild(goalPaths);
            placesPage.appendChild(goalNote);
            placesPage.appendChild(goalList);
            placesPage.appendChild(goalToPlan);

            function wantedPages() {
                var made = [];
                if (selected && (selected.shape || selected.missing)) {
                    made.push({key: 'profile', kind: 'profile', node: body,
                               label: 'Elevation profile'});
                }
                // **The way to a goal has its places where the plan has its
                // points.** Wanted while the goal is what the panel shows and
                // not while a goal merely stands: a reader who tapped a trail
                // to read it is reading that trail, and the goal's controls
                // over its figures were the defect reported from the phone.
                if (selected && selected.goal) {
                    made.push({key: 'places', kind: 'list', node: placesPage,
                               label: 'Places on the way'});
                }
                // **And after plan mode has been left**, for a route still on
                // the panel: the points and the stages are what that route *is*,
                // and going back into plan mode to read them is a mode change to
                // look at something. Read-only there -- the list draws itself
                // without its grips, its menus and its name fields, and the
                // stage files stay, because writing one changes nothing.
                if ((planNow && planNow.on) ||
                        (selected && selected.composed && selected.plan &&
                         selected.plan.waypoints && selected.plan.waypoints.length)) {
                    made.push({key: 'list', kind: 'list', node: pointsPage,
                               label: 'Points and stages'});
                }
                // A popup handed over is a page whether or not a route is being
                // planned. It cannot normally happen while one is -- plan mode
                // owns every click on the map, so nothing opens a popup -- but a
                // page that holds a popup it will not show would be holding it
                // where nobody can read it.
                if (detailHtml || (!(planNow && planNow.on) && saidLines.length)) {
                    made.push({key: 'details', kind: 'details', node: detailBox,
                               label: 'Details'});
                }
                return made;
            }

            // **Every page is as tall as the drawing, and the drawing is as
            // tall as the reader dragged it.** Pages of their own heights meant
            // a panel that jumped as it was turned and a row at the foot that
            // moved with it -- and a grip that governed one page of three. One
            // height means one control for it, and a page with more to say than
            // fits scrolls, which is what a page is for.
            //: The strip's height as last drawn: rows of stations under the axis.
            var stripNow = 0;
            function sizePages() {
                if (!pages.length) { return; }
                // **A selection with a curve is as tall as the curve; one
                // without is as tall as it is.** Both halves matter: pages of
                // their own heights meant a panel that jumped as it was turned,
                // and a quay with three rows in it drawn as tall as a chart is
                // 110 px of empty panel over the map.
                var curved = false;
                pages.forEach(function (page) { if (page.kind === 'profile') { curved = true; } });
                if (curved) { pagesBox.style.height = (chartHeight + stripNow) + 'px'; return; }
                // Measured with the box let go, because a page stretched to fill
                // it reports the height it was given and never a smaller one.
                pagesBox.style.height = 'auto';
                var needs = pages[pageAt].node.scrollHeight || 0;
                pagesBox.style.height = Math.max(60, Math.min(chartHeight, needs + 6)) + 'px';
            }

            // **Every page is in the track from the start and the ones that do
            // not apply are hidden.** They were appended and removed as the set
            // changed, which detaches a node -- and the curve is one of them.
            // Driven, a drag on the chart between two selections found no chart
            // at all: it was in a variable and not in the document, which is the
            // detached-DOM trap this suite has met one level up.
            [body, detailBox, pointsPage, placesPage].forEach(function (node) {
                node.classList.add('trails-profile-page');
                node.style.flex = 'none';
                node.style.overflowY = 'auto';
                node.style.display = 'none';
                track.appendChild(node);
            });

            //: What order the track's children were last put in, so they are
            //: only moved when that changes: appending a node moves it, and a
            //: moved node loses where it was scrolled to.
            var laidPages = '';

            function paintPages(moved) {
                pages = wantedPages();
                if (pageAt >= pages.length) { pageAt = 0; }
                var wanted = pages.map(function (page) { return page.node; });
                [body, detailBox, pointsPage, placesPage].forEach(function (node) {
                    node.style.display = wanted.indexOf(node) >= 0 ? '' : 'none';
                });
                // **The track's order is the pages' order.** They were appended
                // once, in the order they were written in, and the marks were
                // drawn in the order the pages come -- so with a route being
                // planned the mark for *points and stages* slid the box to the
                // details of whatever line had been chosen before it, and the
                // *i* showed the points. Two lists of the same three things,
                // agreeing until the day one of them was conditional.
                var order = pages.map(function (page) { return page.key; }).join(',');
                if (order !== laidPages) {
                    laidPages = order;
                    // The wanted ones in their order and the rest behind them,
                    // so that the document's order is the reader's order: the
                    // first `.trails-profile-page` is the first page, and not
                    // whichever one happens to be put away.
                    wanted.forEach(function (node) { track.appendChild(node); });
                    [body, detailBox, pointsPage, placesPage].forEach(function (node) {
                        if (wanted.indexOf(node) < 0) { track.appendChild(node); }
                    });
                }
                if (!pages.length) {
                    pagesBox.style.display = 'none';
                    pips.style.display = 'none';
                    pill.style.display = 'none';
                    return;
                }
                // **Filled whether or not it is the page being shown.** The
                // pages lie side by side in one track and the track slides, so
                // the page a reader is swiping *towards* is on the screen before
                // it arrives -- and one filled only on arrival showed the last
                // selection's table for the length of the slide, which is
                // exactly long enough to read the wrong name.
                pages.forEach(function (page) { if (page.kind === 'details') { fillDetail(); } });
                pagesBox.style.display = pagesOpen ? '' : 'none';
                pips.style.display = (pagesOpen && pages.length > 1) ? 'flex' : 'none';
                track.style.width = (pages.length * 100) + '%';
                pages.forEach(function (page) { page.node.style.width = (100 / pages.length) + '%'; });
                track.style.transition = moved === false ? 'none' : 'transform .18s ease';
                track.style.transform = 'translateX(-' + (pageAt * (100 / pages.length)) + '%)';
                sizePages();

                pips.innerHTML = '';
                pill.innerHTML = '';
                pill.style.display = (pages.length > 1) ? 'flex' : 'none';
                // The name of the tour and the way back sit in this row, and
                // both are edits: away with them where nothing can be edited.
                undoRow.style.display = (planNow && planNow.on) ? 'flex' : 'none';
                if (planNow) {
                    undoOne.disabled = !planNow.undoable;
                    undoOne.style.opacity = planNow.undoable ? '' : '0.35';
                }
                pages.forEach(function (page, at) {
                    var pip = document.createElement('i');
                    pip.style.cssText = 'width:5px;height:5px;border-radius:50%;background:' +
                        (at === pageAt && pagesOpen ? 'var(--trails-ink-4)' : 'var(--trails-grip)');
                    pips.appendChild(pip);

                    var mark = document.createElement('button');
                    mark.type = 'button';
                    mark.className = 'trails-profile-mark' +
                        (at === pageAt && pagesOpen ? ' trails-profile-mark-on' : '');
                    var lit = at === pageAt && pagesOpen;
                    mark.style.cssText = 'width:38px;height:40px;border:0;font:inherit;font-size:15px;' +
                        'display:flex;align-items:center;justify-content:center;cursor:pointer;' +
                        'border-left:' + (at ? '1px solid var(--trails-rule)' : '0') + ';' +
                        'background:' + (lit ? 'var(--trails-accent)' : 'transparent') + ';' +
                        'color:' + (lit ? 'var(--trails-on-accent)' : 'var(--trails-ink-3)');
                    mark.title = page.label;
                    mark.setAttribute('aria-label', page.label);
                    mark.appendChild(markNode(page.kind));
                    mark.addEventListener('click', function (event) {
                        event.stopPropagation();
                        // A second press on the lit mark folds the pages away
                        // and leaves the row -- which is what a mark that opened
                        // something is expected to do, and the only way back to
                        // a whole map without giving up the selection.
                        if (lit) { showPages(false); return; }
                        goPage(at);
                    });
                    pill.appendChild(mark);
                });
            }

            function goPage(at) {
                // Turning the page is leaving the curve, and a reading of a
                // place on it is about the curve.
                forget();
                pageAt = Math.max(0, Math.min(pages.length - 1, at));
                if (!pagesOpen) { showPages(true); return; }
                paintPages();
                if (pages[pageAt] && pages[pageAt].kind === 'profile') { render(); }
            }

            // **Whether the pages are open is the reader's answer, and the
            // reader's answer is the chrome's to keep.** Every other switch for
            // it -- the rail's mark, the plan control -- sets it there, and one
            // that set only this closed itself again the moment anything
            // repainted: while planning on a narrow screen the chrome's default
            // is *shut*, so it asked for shut back, half a frame after a reader
            // had asked for open. Driven: the list page opened and was gone
            // before it could be read.
            function showPages(want) {
                want = !!want;
                if (window.trailsChrome && window.trailsChrome.profile &&
                        window.trailsChrome.profile() !== want) {
                    // The chrome answers by asking this back, which is where the
                    // work below gets done. One handshake, not two.
                    window.trailsChrome.profile(want);
                    return;
                }
                if (pagesOpen === want) { return; }
                pagesOpen = want;
                paintPages();
                if (pagesOpen) { render(); }
                if (window.trailsChrome && window.trailsChrome.placed) { window.trailsChrome.placed(); }
            }

            // **Swiping, everywhere in the panel except across the drawing.**
            // One finger on the curve reads it -- distance, height, gradient --
            // and that gesture is both older and worth more than this one: it is
            // the only way to ask a phone what is under a place. So the swipe is
            // taken on the row at the foot and on any page that is not the
            // curve, and the marks are what move a reader off the profile.
            var swiping = null;
            function swipeFrom(node) {
                node.addEventListener('touchstart', function (event) {
                    if (pages.length < 2 || event.touches.length !== 1) { swiping = null; return; }
                    swiping = {x: event.touches[0].clientX, y: event.touches[0].clientY, took: false};
                }, {passive: true});
                node.addEventListener('touchmove', function (event) {
                    if (!swiping || event.touches.length !== 1) { return; }
                    var dx = event.touches[0].clientX - swiping.x;
                    var dy = event.touches[0].clientY - swiping.y;
                    if (!swiping.took && Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy)) {
                        swiping.took = true;
                    }
                    if (!swiping.took) { return; }
                    event.preventDefault();
                    track.style.transition = 'none';
                    track.style.transform = 'translateX(calc(-' + (pageAt * (100 / pages.length)) +
                        '% + ' + (dx / pages.length) + 'px))';
                }, {passive: false});
                node.addEventListener('touchend', function (event) {
                    if (!swiping) { return; }
                    var took = swiping.took;
                    var from = swiping.x;
                    swiping = null;
                    if (!took) { return; }
                    var wide = pagesBox.clientWidth || 1;
                    var dx = (event.changedTouches && event.changedTouches.length)
                        ? event.changedTouches[0].clientX - from : 0;
                    if (dx < -wide * 0.18 && pageAt < pages.length - 1) { goPage(pageAt + 1); return; }
                    if (dx > wide * 0.18 && pageAt > 0) { goPage(pageAt - 1); return; }
                    paintPages();
                });
                node.addEventListener('touchcancel', function () { swiping = null; paintPages(); });
            }
            swipeFrom(header);
            swipeFrom(detailBox);
            swipeFrom(pointsPage);

            // **A press on what it says opens what it says more about**, which
            // is the page the second line has been pointing at all along: the
            // points of a route being planned, the details of a line. Plan
            // mode's bar said *tap for the list* and meant it; this is that tap,
            // and pressing it again on the page it opened folds it away.
            said.addEventListener('click', function () {
                if (!pages.length) { return; }
                // **Open it, or put it away.** It used to walk to the page it
                // names first and fold only from there, so a reader who wanted
                // the map back got the table they had not asked for and then had
                // to press again. What is open goes; what is shut comes up on
                // the page this line has been pointing at all along.
                if (pagesOpen) { showPages(false); return; }
                var wanted = planning() ? 'list' : 'details';
                var at = 0;
                pages.forEach(function (page, i) { if (page.key === wanted) { at = i; } });
                goPage(at);
            });

            // ---- the height, which a reader owns ----------------------------
            // **Dragging this taller is not decoration.** The chart's scale is
            // the coarser of length-per-width and relief-per-height, so on a
            // chain steep enough for the height to bind, every pixel given here
            // is a finer scale: 55 px took the 3 km path off Øyfjellet from
            // 6.96 to 4.72 metres a pixel. On a long gentle route the width
            // binds and dragging changes the picture's size and nothing else,
            // which is honest — there is no detail there to uncover.
            // **The whole strip above the pages is the handle, not the bar.**
            // The bar is 7 px and the page under it scrolls, so a finger that
            // missed by four pixels scrolled the page instead of resizing the
            // panel -- reported as a height that could hardly be set at all.
            // What is drawn stays a 38 x 3 bar; what can be pressed is the strip
            // it sits in, the dots below it included, and `touch-action: none`
            // is what stops the browser reading the drag as a scroll before the
            // handler ever sees it.
            var hold = document.createElement('div');
            hold.className = 'trails-profile-hold';
            hold.title = 'Drag to change the height of the panel';
            hold.style.cssText = 'cursor:ns-resize;touch-action:none;padding:3px 0 1px;' +
                'margin:-4px -10px 0';
            var grip = document.createElement('div');
            grip.className = 'trails-profile-grip';
            grip.style.cssText = 'height:7px;display:flex;align-items:center;justify-content:center';
            var grabbed = document.createElement('div');
            grabbed.style.cssText = 'width:38px;height:3px;border-radius:2px;background:var(--trails-grip)';
            grip.appendChild(grabbed);
            // The chart height the panel was last **laid out** with, which
            // is not the same as the height it has been asked for: a redraw is
            // coalesced to the next frame, so between the ask and the frame the
            // box on the page still measures the old one.
            var laidOut = chartHeight;
            var stretching = null, awaiting = false;
            hold.appendChild(grip);
            hold.addEventListener('mouseenter', function () { grabbed.style.background = 'var(--trails-grip-held)'; });
            hold.addEventListener('mouseleave', function () { if (!stretching) { grabbed.style.background = 'var(--trails-grip)'; } });

            function stretchTo(pixels) {
                // **Only while the panel is open**, and that is not tidiness.
                // Folded, the box is one line with no chart in it, so the
                // overhead below measures as negative — 35 px of panel against
                // a 205 px chart, an overhead of minus 170 — and the ceiling
                // comes out taller than the map instead of shorter. A click on
                // the map folds the panel, and a click can land in the middle of
                // a drag: measured, that reopened the panel at 705 px with the
                // ceiling reading 990.
                if (!open) { return; }
                // Room for a curve at all, and never so tall that the panel is
                // the map. The overhead is measured rather than assumed: the two
                // rows above the chart are a different height in every browser.
                //
                // **Against the height the panel was laid out with, not the one
                // it was last asked for.** Two moves inside one frame otherwise
                // measure a fresh chart against a stale box: the second reads an
                // overhead of minus 620, a ceiling of 1,440, and hands out a
                // panel taller than the map. It is not a corner — Firefox
                // reports clientY as -86 the moment the pointer leaves the foot
                // of the window, so a drag that runs off the bottom delivers
                // three of them at once, and the panel opens at 900 px on a
                // 900 px map.
                var least = 60;
                var most = Math.max(least, mapRoom().y - (box.offsetHeight - laidOut) - 80);
                var wanted = Math.round(Math.min(most, Math.max(least, pixels)));
                if (wanted === chartHeight) { return; }
                chartHeight = wanted;
                // Coalesced to one draw a frame. A redraw per mouse move is the
                // mistake that froze this map twice, and a chain of eight
                // thousand samples is four hundred separate strokes.
                if (!awaiting) {
                    awaiting = true;
                    window.requestAnimationFrame(function () {
                        awaiting = false;
                        // The box first, because a drag that started on the list
                        // is asking for a taller list and would otherwise wait
                        // for the reader to turn back to the curve.
                        sizePages();
                        render();
                    });
                }
            }

            // **Whether the height on this panel is anybody's decision.**
            // Until a reader drags it, it is a default and may be recomputed
            // when the window changes shape; after that it is theirs and a
            // rotation must not take it back. The flag is set on the grab and
            // never cleared, which is the whole rule.
            var readerSized = false;

            // A share of the map rather than a constant. Measured on the built
            // page, the panel opened at 393 px whatever it opened on: 47 % of an
            // 844 px screen and 61 % of a 640 px one, decided by a build-time
            // number that never saw the screen.
            function defaultChartHeight() {
                var size = mapRoom();
                var wanted = startingChartHeight;
                // **Two caps, because one number cannot tell these screens
                // apart.** A phone held upright is 390 x 844 and a desktop is
                // 1400 x 900: near enough the same height, so a share of the
                // height alone treats them the same and a share of the width
                // says nothing about a panel at the foot. Narrow is what makes
                // the first a phone; short is what makes a phone turned
                // sideways one.
                if (size.x < NARROW) { wanted = Math.min(wanted, Math.round(size.y * 0.22)); }
                // Under 500 is a phone on its side and nothing else: the tallest
                // phone in landscape is about 430, the shortest laptop about 600.
                //
                // **0.28 and not 0.20, and the number moved for a reason.** The
                // share is on the *drawing* while the panel's own furniture is
                // what it costs, so shrinking the furniture without moving this
                // handed the freed pixels to the map rather than to the curve —
                // measured, the row went 66 to 31 px and the drawing stayed at
                // 78. Folded, the overhead is 87 px, so 0.28 of a 390 px screen
                // puts the panel at 196: about half, which is where it was, with
                // **40 % more drawing in it**.
                if (size.y < SHORT) { wanted = Math.min(wanted, Math.round(size.y * 0.28)); }
                return Math.max(60, wanted);
            }

            hold.addEventListener('mousedown', function (event) {
                if (!open) { return; }
                readerSized = true;
                // The panel is anchored to the bottom of the map, so it grows
                // upwards and a pointer moving up asks for more.
                stretching = {from: event.clientY, height: chartHeight};
                grabbed.style.background = 'var(--trails-grip-held)';
                event.preventDefault();
            });
            document.addEventListener('mousemove', function (event) {
                if (!stretching) { return; }
                stretchTo(stretching.height + (stretching.from - event.clientY));
            });
            document.addEventListener('mouseup', function () {
                if (!stretching) { return; }
                stretching = null;
                grabbed.style.background = 'var(--trails-grip)';
            });

            // And with a finger, because the height is resolution on a steep
            // chain and a grip only a mouse can reach hands that to one kind of
            // reader. The move listener preventDefaults only while something is
            // actually being stretched, or it would take the scroll away from
            // every panel on the page.
            hold.addEventListener('touchstart', function (event) {
                if (!open || event.touches.length !== 1) { return; }
                readerSized = true;
                stretching = {from: event.touches[0].clientY, height: chartHeight};
                grabbed.style.background = 'var(--trails-grip-held)';
                event.preventDefault();
            }, {passive: false});
            document.addEventListener('touchmove', function (event) {
                if (!stretching || event.touches.length !== 1) { return; }
                stretchTo(stretching.height + (stretching.from - event.touches[0].clientY));
                event.preventDefault();
            }, {passive: false});
            document.addEventListener('touchend', function () {
                if (!stretching) { return; }
                stretching = null;
                grabbed.style.background = 'var(--trails-grip)';
            });

            var control = L.control({position: 'bottomleft'});
            var box = null;
            control.onAdd = function () {
                box = L.DomUtil.create('div', 'trails-profile-panel');
                box.style.cssText = 'background:var(--trails-panel);padding:6px 10px;border:1px solid var(--trails-edge);' +
                    'border-radius:4px;font-family:sans-serif;font-size:12px;line-height:1.4;' +
                    // Clear of the attribution, which sits in the corner opposite
                    // and would otherwise be covered by a panel this wide.
                    'margin-bottom:22px';
                hold.appendChild(pips);
                box.appendChild(hold);
                box.appendChild(pagesBox);
                // Over the row at the foot and under the pages: the row is the
                // part that never moves, and what a tap found is about the
                // selection that row names.
                box.appendChild(picks);
                // Under the chips and over the heading: the chips are about the
                // tap that just happened and this is about a thing that is still
                // standing, so it sits nearer the name it is not part of.
                box.appendChild(header);
                // Clicking and dragging inside the panel must not reach the map;
                // scrolling must, or the map freezes under an open panel.
                L.DomEvent.disableClickPropagation(box);
                return box;
            };
            control.addTo(map);

            // Leaflet inserts into a *bottom* corner rather than appending, so
            // the control added last ends up highest — the opposite of the top
            // corners, and the opposite of what this one wants. It takes the
            // foot of the map; the legend and the scale keep the corner above
            // it, whichever order they were added in.
            var corner = control.getContainer().parentNode;
            corner.appendChild(control.getContainer());

            function fold() {
                // **And the height is held to a ceiling that moves.** It was
                // clamped only where it was asked for, so a window made shorter
                // afterwards left the panel taller than the map: measured, a
                // 725 px panel in a 620 px window put its own grip at −127, off
                // the top of the map and out of a reader's reach for good.
                // Asking for the height it already has is what re-clamps it.
                if (open) { stretchTo(chartHeight); }
                // A drag does not survive the panel folding under it: the grip
                // it started on is no longer above a chart, and picking the drag
                // up again on reopening would jump the height by however far the
                // pointer travelled in between.
                if (!open && stretching) { stretching = null; grabbed.style.background = 'var(--trails-grip)'; }
                // **The row stands whenever there is something to stand for**,
                // and the pages are the part that folds. Something is a selected
                // line, a route being planned -- with no points down yet as much
                // as with four -- or a place whose popup has been handed over.
                paintPages();
                // `open` is *something is selected*, and while plan mode owns
                // the map nothing is -- so a popup's page, which is the one
                // thing a reader can ask for there, needs saying separately.
                hold.style.display = ((open || (suspended && detailHtml)) && pagesOpen) ? 'block' : 'none';
                header.style.marginTop = (open && pagesOpen) ? '4px' : '0';
                // **Folded, the row is the whole panel and pays a row's price.**
                // Plan mode's bar was 44 px; this was 63 with the panel's own
                // padding around it, and those 19 px are map a reader planning
                // is tapping on.
                box.style.padding = (open && pagesOpen) ? '6px 10px' : '2px 10px';
                // **Edge to edge where the screen is narrow**, and inset where
                // it is not. Leaflet gives every control a 10 px margin, which
                // on a 390 px screen is 5 % of the width spent on a gutter
                // beside a chart whose whole value is metres per pixel.
                // The 16 px that stay below it are not decoration: the
                // attribution sits in the corner underneath, and a panel that
                // covered it would be taking a credit off the page.
                // **Asked of the chrome, which owns the answer.** It used to
                // work this out again from the width, and the two have just
                // stopped agreeing: a phone held sideways is wide enough for the
                // rail and too short for it, so the chrome shows the burger while
                // this still believed there was a rail to leave room for.
                var said = window.trailsChrome && window.trailsChrome.state();
                var narrow = said ? said.narrow : mapRoom().x < NARROW;
                box.style.margin = narrow ? '0 0 16px 0' : '';
                box.style.borderRadius = narrow ? '0' : '';
                box.style.borderLeftWidth = narrow ? '0' : '';
                box.style.borderRightWidth = narrow ? '0' : '';
                // **The room it has, not the width of the map.** This took the
                // whole map minus 20 px, which was true while the map ended
                // where the screen's usable part did. It does not any more: the
                // page reaches the physical edges, so on a phone held sideways
                // the panel ran into the inset on the right *and* under the rail
                // -- reported as the profile sticking out to the right.
                //
                // The rail is 46 px and stands 10 px off the edge; 66 leaves it
                // its own width and a gap. On a narrow screen there is no rail,
                // only the burger, and that sits above this.
                var railRoom = narrow ? 0 : 66;
                box.style.width = (open || planning())
                    ? 'calc(' + mapRoom().x + 'px - env(safe-area-inset-left) - ' +
                      'env(safe-area-inset-right) - ' + (railRoom + (narrow ? 0 : 20)) + 'px)'
                    : '';
            }

            // ---- the arrow, in a container of its own -----------------------
            // Not a layer and not a path on the map: the count of those is what
            // phase 3 was accepted against, and anything drawn into the overlay
            // pane joins it for ever.
            var pane = map.createPane('trailsProfileDirection');
            pane.style.zIndex = 450;
            pane.style.pointerEvents = 'none';
            // Leaflet scales the panes it animates a zoom with; this one is
            // hidden for the duration and put back where it belongs afterwards.
            L.DomUtil.addClass(pane, 'leaflet-zoom-hide');
            var arrow = document.createElementNS(SVG, 'svg');
            arrow.setAttribute('width', '96');
            arrow.setAttribute('height', '96');
            arrow.style.cssText = 'position:absolute;margin:-48px 0 0 -48px;overflow:visible;display:none';
            // Drawn pointing north and turned to the bearing, so it says the
            // same thing the words do rather than following the line's local
            // wanderings. Twice: a pale wide stroke under a dark narrow one, or
            // it disappears over a dark line.
            var SHAFT = 'M48 76 L48 28 M38 41 L48 24 L58 41';
            // The gentlest band's colour: the arrow says which way, not how
            // steep, so it takes the curve's base colour rather than a band.
            [PAPER, GRADE.bands[0].colour].forEach(function (colour, index) {
                var stroke = document.createElementNS(SVG, 'path');
                stroke.setAttribute('d', SHAFT);
                stroke.setAttribute('fill', 'none');
                stroke.setAttribute('stroke', colour);
                stroke.setAttribute('stroke-width', index ? '3' : '6');
                stroke.setAttribute('stroke-linecap', 'round');
                stroke.setAttribute('stroke-linejoin', 'round');
                arrow.appendChild(stroke);
            });
            pane.appendChild(arrow);

            // **And where the reader's pointer is, on the ground.** The panel
            // already knows which sample the crosshair sits on and the map wants
            // that sample's position: a profile is far easier to plan against
            // when the hill under the pointer and the hill on the map are the
            // same hill. It takes the arrow's pane for the arrow's reason — the
            // map's path count is what phase 3 was accepted against, and nothing
            // this panel draws may join it — and the crosshair's colour, because
            // the two are one thing shown in two places.
            // **Above the planned route, in a pane of its own.** It shared the
            // arrow's, at z-index 450, and plan mode's route pane is 460 — so
            // the one mark whose whole job is to say *where on this route you
            // are* was drawn underneath the route. Not the arrow's pane raised
            // instead: the arrow belongs under a route it can only ever point
            // along, and the two never show together anyway. Under the markers
            // at 600, so a waypoint's pin still covers it where they coincide,
            // which is the pin saying the same place.
            var over = map.createPane('trailsProfileHere');
            over.style.zIndex = 470;
            over.style.pointerEvents = 'none';
            L.DomUtil.addClass(over, 'leaflet-zoom-hide');
            var here = document.createElementNS(SVG, 'svg');
            here.setAttribute('width', '22');
            here.setAttribute('height', '22');
            here.style.cssText = 'position:absolute;margin:-11px 0 0 -11px;overflow:visible;display:none';
            // A pale disc under a dark one, like the arrow: over a dark line, or
            // over the dark green of a forest, a bare dot disappears.
            [PAPER, CROSS].forEach(function (colour, index) {
                var ring = document.createElementNS(SVG, 'circle');
                ring.setAttribute('cx', '11'); ring.setAttribute('cy', '11');
                ring.setAttribute('r', index ? '4' : '6.5');
                ring.setAttribute('fill', colour);
                here.appendChild(ring);
            });
            over.appendChild(here);

            // The position under the crosshair, in ground rather than in pixels,
            // so a pan or a zoom moves the mark with the map rather than leaving
            // it where the map used to be.
            var standing = null;

            function placeHere() {
                if (!standing) { here.style.display = 'none'; return; }
                here.style.display = '';
                L.DomUtil.setPosition(here, map.latLngToLayerPoint(standing));
            }
            map.on('zoomend viewreset moveend resize', placeHere);

            function placeArrow() {
                // Nothing is drawn for a chain with no profile — a crossing has
                // no figures for an arrow to point the way of, and an arrow
                // along it would be the only mark on the map claiming otherwise.
                var showing = selected && selected.shape && selected.shape.read && selected.mid;
                var bearing = showing ? selected.figure.bearing : null;
                if (bearing === null || bearing === undefined) { arrow.style.display = 'none'; return; }
                arrow.style.display = '';
                arrow.childNodes.forEach(function (stroke) { stroke.setAttribute('transform', 'rotate(' + bearing + ' 48 48)'); });
                L.DomUtil.setPosition(arrow, map.latLngToLayerPoint(selected.mid));
            }
            map.on('zoomend viewreset moveend resize', placeArrow);

            // ---- drawing ----------------------------------------------------
            function text(x, y, value, anchor) {
                var node = document.createElementNS(SVG, 'text');
                node.setAttribute('x', x); node.setAttribute('y', y);
                node.setAttribute('font-size', '10'); node.setAttribute('fill', TEXT);
                node.setAttribute('text-anchor', anchor || 'start');
                node.textContent = value;
                return node;
            }

            function line(x1, y1, x2, y2, colour, width) {
                var node = document.createElementNS(SVG, 'line');
                node.setAttribute('x1', x1); node.setAttribute('y1', y1);
                node.setAttribute('x2', x2); node.setAttribute('y2', y2);
                node.setAttribute('stroke', colour); node.setAttribute('stroke-width', width || 1);
                return node;
            }

            // Round numbers an axis can be read off: 1, 2 or 5 times a power of
            // ten, whichever first gives about as many steps as asked for.
            function ticks(low, high, wanted) {
                if (!(high > low)) { return [low]; }
                var rough = (high - low) / wanted;
                var power = Math.pow(10, Math.floor(Math.log(rough) / Math.LN10));
                var step = 10 * power;
                [1, 2, 5].some(function (multiple) { if (multiple * power >= rough) { step = multiple * power; return true; } return false; });
                var out = [];
                for (var value = Math.ceil(low / step) * step; value <= high + step * 1e-6; value += step) { out.push(value); }
                return out;
            }

            // ---- how much of the chain is on the panel, and at what scale ---
            // **Zoom belongs to the long chain and to a planned route, and to
            // almost nothing else.** Measured over the built graph: the median
            // chain is drawn at 0.16 metres a pixel against a series carrying a
            // height every 5.12 m, so the panel already magnifies every reading
            // it holds some thirty times over. Only 126 chains of 11,264 are
            // drawn coarser than their own samples — the 42 km Rundtur is one of
            // them, at 36.28 m/px, and a route planned here is that long by
            // nature. So this is for the route, and the chain is the exception.
            //
            // The ceiling is the data's rather than a taste: **one reading per
            // pixel**. Past it the panel magnifies the straight lines drawn
            // between samples, which claims a resolution nothing supports. It
            // works out at 7.1x on that chain and 3 to 5x on the next longest.
            //
            // ``at`` is the distance at the left edge and ``centre`` the height
            // at the middle, both in metres, because pixels change under a drag
            // of the grip and metres do not. ``centre`` is null until a window
            // turns out to be steeper than the panel — see render().
            var view = {zoom: 1, at: 0, centre: null};

            //: Where the reader's answer to *which scale* is kept, and the key
            //: it is kept under. The theme is kept the same way and for the same
            //: reason: it is a decision about how this page is read, not about
            //: what is on it, and it should survive the next visit.
            var SCALE_KEY = 'trails:profile-scale';
            //: **How far the readable scale may lift the heights.** Measured on
            //: this map's own longest route: 44 km across a phone's panel is
            //: 119 metres to the pixel, so 691 m of relief draws as six pixels
            //: at the ground's own scale -- a straight line with a colour on it.
            //: Ten times that is 58 px, which has a shape.
            //:
            //: **And a cap rather than *fill the box*, because a molehill blown
            //: up to a mountain is a lie a picture tells better than words can
            //: correct it.** A 20 m rise over 40 km filling the panel would be
            //: an exaggeration of two hundred; at ten it stays the ribbon it is.
            var LIFT_MAX = 10;
            //: How much of the box the lifted band may fill. The rest is room
            //: over the summit and under the low point, so a curve at the
            //: readable scale is not jammed against the ceiling.
            var LIFT_FILL = 0.86;

            function keptScale() {
                try { return window.localStorage.getItem(SCALE_KEY); } catch (blocked) { return null; }
            }

            //: **Lifted unless the reader said otherwise**, which is the answer
            //: to *I cannot see anything on a long tour*. What is given up is
            //: that the drawn angle is the angle on the ground -- so the factor
            //: is written over the drawing, and the colours, which are the truth
            //: about steepness, do not move with it: they are read off the
            //: ground and not off the picture.
            var lifted = keptScale() !== 'true';
            //: What the last render worked out, for the mark that says so and
            //: for a check that reads it.
            var liftNow = 1;

            // The waypoint pins' own ink. Plan mode names it ROUTE and draws
            // its pins with it; a station on this panel is the same point seen
            // from the side, and two colours for one point would be two points.
            var STATION_R = 6;
            // **The stations stand under the axis, not on the curve.** They
            // sat at their own height, which put the goal's ring over the end
            // of the curve and stacked a plan's close points on top of each
            // other -- reported from the phone, both. A strip of STRIP px per
            // row under the axis holds them now, the kilometres move down by
            // as much, and each station keeps a dashed rule up to its place on
            // the curve. A station that would overlap one already in its row
            // goes to the next row; the chart grows by the rows it needs and
            // the page with it, so the curve keeps its height.
            var STRIP = 16;
            // The waypoint marks on the curve: panel ink, not the route's own
            // black, which is drawn on the map and stays as it is.
            var STATION = '#111111', STATION_UNREAD = '#9e9e9e';


            var crosshair = null;

            // How steep the ground is at each sample, read over GRADE.window
            // rather than between neighbours. Two pointers rather than a search:
            // both ends only ever move forward, so the whole series costs one
            // pass however long it is.
            function gradients(shape) {
                var n = shape.height.length, out = new Float64Array(n);
                var half = GRADE.window / 2, lo = 0, hi = 0, i;
                for (i = 0; i < n; i += 1) {
                    out[i] = NaN;
                    if (isNaN(shape.height[i])) { continue; }
                    while (lo < i && shape.distance[i] - shape.distance[lo] > half) { lo += 1; }
                    if (hi < i) { hi = i; }
                    while (hi < n - 1 && shape.distance[hi] - shape.distance[i] < half) { hi += 1; }
                    // Pull both ends in off any ground nothing was read along:
                    // a difference across a gap is a difference across invented
                    // ground.
                    var a = lo, b = hi;
                    while (a < i && isNaN(shape.height[a])) { a += 1; }
                    while (b > i && isNaN(shape.height[b])) { b -= 1; }
                    var run = shape.distance[b] - shape.distance[a];
                    if (run >= GRADE.minRun && !isNaN(shape.height[a]) && !isNaN(shape.height[b])) {
                        out[i] = 100 * (shape.height[b] - shape.height[a]) / run;
                    }
                }
                return out;
            }

            // The steepest the ground gets along a series, absolute, over the
            // same 25 m window the curve is banded by.
            //
            // **Absolute, because a signed maximum would call this park's
            // steepest chain flat**: it climbs 9 m and drops 816. The same
            // reasoning the popups were given, and the same window, so the
            // heading, the colours and the crosshair cannot come to disagree
            // about how steep the same ground is.
            //
            // Computed here only for a **composed route**, which nothing else
            // has measured. A chain's is carried from the build, where it was
            // read off the samples at arc length rather than off the chords this
            // page sums — the two differ by about one part in a thousand, and
            // one page showing both would be showing two answers.
            // `freeOnly` reads the samples marked free -- the straight parts of a
            // composed route -- and nothing else: what a line over open ground
            // climbs is a question the path's own gradient does not answer.
            function steepestOf(shape, freeOnly) {
                var slope = gradients(shape), worst = NaN;
                for (var i = 0; i < slope.length; i += 1) {
                    if (isNaN(slope[i])) { continue; }
                    if (freeOnly && !(shape.free && shape.free[i])) { continue; }
                    var magnitude = Math.abs(slope[i]);
                    if (isNaN(worst) || magnitude > worst) { worst = magnitude; }
                }
                return worst;
            }

            // Which band a gradient falls in. Anything unmeasurable comes back
            // as the gentlest — a stretch too short to read a slope along is not
            // thereby steep, and colouring it would be an assertion nothing
            // supports.
            function bandOf(slope) {
                if (isNaN(slope)) { return 0; }
                var magnitude = Math.abs(slope), band = 0;
                for (var i = 0; i < GRADE.bands.length; i += 1) {
                    if (magnitude >= GRADE.bands[i].from) { band = i; }
                }
                return band;
            }

            // The points the curve is drawn through, in runs that must not be
            // joined across, each carrying the sample it came from so its band
            // can be looked up in the full series. ``from`` and ``to`` are the
            // window on the chain, which is the whole of it until something
            // zooms in.
            function drawPoints(shape, columns, from, to) {
                var runs = [], run = [], i;
                var reach = to - from;
                if (!(reach > 0)) { return runs; }
                // Samples are laid in order, so a window is a slice and not a
                // filter. Held to a hair either side, or the sample sitting
                // exactly on the end of the chain falls outside its own chain.
                var lo = 0, hi = shape.distance.length - 1;
                while (lo <= hi && shape.distance[lo] < from - 1e-6) { lo += 1; }
                while (hi >= lo && shape.distance[hi] > to + 1e-6) { hi -= 1; }
                if (hi < lo) { return runs; }
                if (hi - lo + 1 <= columns) {
                    // The common case, and it has to be: the median chain here
                    // holds 36 samples and a third of them fewer than twenty.
                    // Bucketing those into 900 columns leaves 864 empty and the
                    // curve full of holes it has no business having.
                    //
                    // One sample beyond each edge as well, and only here: zoomed
                    // into a sparse stretch the nearest reading can lie a long
                    // way outside the window, and without it the curve stops
                    // short of the edge and says nothing about why. What that
                    // draws outside the box is clipped away below.
                    var a = lo > 0 ? lo - 1 : lo, b = hi < shape.distance.length - 1 ? hi + 1 : hi;
                    for (i = a; i <= b; i += 1) {
                        if (isNaN(shape.height[i])) {
                            if (run.length) { runs.push(run); run = []; }
                            continue;
                        }
                        run.push({d: shape.distance[i], h: shape.height[i], at: i});
                    }
                    if (run.length) { runs.push(run); }
                    return runs;
                }
                // One point per pixel column for the long ones, keeping that
                // column's own lowest and highest reading, in the order they
                // occur, so no spike is lost to the reduction. The crosshair
                // still reads the full series.
                var low = new Float64Array(columns), high = new Float64Array(columns);
                var lowAt = new Int32Array(columns), highAt = new Int32Array(columns), filled = new Uint8Array(columns);
                var firstAt = new Int32Array(columns), lastAt = new Int32Array(columns);
                // How many samples up to here the model had no reading for, so
                // the question "was anything missed between these two columns"
                // is one subtraction rather than a scan. Over the whole series
                // rather than the window: the indices it is asked about are the
                // series' own, and a window does not renumber them.
                var missed = new Int32Array(shape.height.length + 1);
                for (i = 0; i < shape.height.length; i += 1) {
                    missed[i + 1] = missed[i] + (isNaN(shape.height[i]) ? 1 : 0);
                }
                for (i = lo; i <= hi; i += 1) {
                    var value = shape.height[i];
                    if (isNaN(value)) { continue; }
                    var column = Math.max(0, Math.min(columns - 1, Math.floor(((shape.distance[i] - from) / reach) * columns)));
                    if (!filled[column] || value < low[column]) { low[column] = value; lowAt[column] = i; }
                    if (!filled[column] || value > high[column]) { high[column] = value; highAt[column] = i; }
                    if (!filled[column]) { firstAt[column] = i; }
                    lastAt[column] = i;
                    filled[column] = 1;
                }
                var previous = -1;
                for (var c = 0; c < columns; c += 1) {
                    // An empty column is NOT a gap. It only says no sample landed
                    // in that pixel, and the walk carries straight through it —
                    // which is routine here, because samples are laid per edge
                    // and a chain of short edges clumps them: 2,532 samples over
                    // 1,977 columns leave 285 columns empty. Lifting the pen for
                    // those drew one gapless 6.5 km chain as 222 separate
                    // strokes. Only ground nothing was read along lifts it.
                    if (!filled[c]) { continue; }
                    if (previous >= 0 && missed[firstAt[c]] > missed[lastAt[previous] + 1]) {
                        if (run.length) { runs.push(run); run = []; }
                    }
                    var at = from + ((c + 0.5) / columns) * reach;
                    var lowFirst = lowAt[c] <= highAt[c];
                    run.push({d: at, h: lowFirst ? low[c] : high[c], at: firstAt[c]});
                    if (low[c] !== high[c]) { run.push({d: at, h: lowFirst ? high[c] : low[c], at: lastAt[c]}); }
                    previous = c;
                }
                if (run.length) { runs.push(run); }
                return runs;
            }

            // Whether a sample lies on ground the route was drawn straight
            // across rather than routed over a recorded way. A chain is never
            // any of it and carries no such series at all.
            function freeAt(shape, sample) {
                return shape.free && shape.free[sample] ? 1 : 0;
            }

            function drawCurve(shape, plot, x, y, slope, from, to) {
                // One stroke per run of segments sharing a band, so the curve is
                // its own legend: where it turns amber the ground turned steep.
                // And per run sharing a *drawing*, so a stretch the plan drew
                // straight is dashed here as it is dashed on the map — the
                // profile has to say the same thing the map does about the same
                // ground.
                var strokes = [], current;
                drawPoints(shape, Math.max(1, Math.floor(plot.width)), from, to).forEach(function (points) {
                    current = null;
                    for (var i = 1; i < points.length; i += 1) {
                        var band = bandOf(slope[points[i - 1].at]), free = freeAt(shape, points[i - 1].at);
                        if (!current || current.band !== band || current.free !== free) {
                            current = {band: band, free: free, parts: ['M' + x(points[i - 1].d).toFixed(1) + ' ' + y(points[i - 1].h).toFixed(1)]};
                            strokes.push(current);
                        }
                        current.parts.push('L' + x(points[i].d).toFixed(1) + ' ' + y(points[i].h).toFixed(1));
                    }
                });
                return strokes.map(function (stroke) { return {band: stroke.band, free: stroke.free, d: stroke.parts.join(' ')}; });
            }

            function render() {
                // **The box follows the drawing's height.** The chart's height
                // is the reader's own -- the grip above it is what sets it --
                // and the box it sits in has to follow, or a drag moves a
                // drawing inside a window that stays where it was. Driven: the
                // grip did nothing at all, because the only thing that resized
                // the window was a repaint of the page set.
                sizePages();
                // Before anything is drawn, because the reader may have turned
                // their whole machine dark since the last stroke.
                refreshInk();
                while (chart.firstChild) { chart.removeChild(chart.firstChild); }
                whole.style.display = view.zoom > 1.001 ? '' : 'none';
                crosshair = null;
                // The mark goes with the crosshair that put it there. A wheel or
                // a drag redraws the curve without the pointer moving, and a mark
                // left behind would point at whatever is now under that pixel.
                if (standing) { standing = null; placeHere(); }
                // Cleared before every early return below, so the row never
                // outlives the curve that explained it.
                freeKey.style.display = 'none';
                if (!open) { return; }

                var width = Math.max(240, body.clientWidth || (mapRoom().x - 40));
                // The height is set here and nowhere else. It is no longer a
                // constant — a reader drags it — and a viewBox that disagreed
                // with the element it is drawn in scales the whole chart by the
                // ratio between them, which reads as a wrong slope on a panel
                // whose whole point is that the slope is right.
                chart.setAttribute('height', chartHeight);
                chart.style.height = chartHeight + 'px';
                laidOut = chartHeight;
                chart.setAttribute('viewBox', '0 0 ' + width + ' ' + chartHeight);
                chart.setAttribute('width', width);
                if (!selected || !selected.shape || !selected.shape.read) { return; }

                var shape = selected.shape;
                if (!(shape.total > 0)) { return; }
                var box = {left: PAD.left, right: width - PAD.right, top: PAD.top, bottom: chartHeight - PAD.bottom};
                var wide = box.right - box.left, tall = box.bottom - box.top;
                var lowest = Infinity, highest = -Infinity, readable = 0, i;
                for (i = 0; i < shape.height.length; i += 1) {
                    if (isNaN(shape.height[i])) { continue; }
                    readable += 1;
                    if (shape.height[i] < lowest) { lowest = shape.height[i]; }
                    if (shape.height[i] > highest) { highest = shape.height[i]; }
                }
                // A stretch of flat ground is flat ground, not a mountain: give
                // it a range of its own rather than letting the height model's
                // centimetre wobble fill the panel. Under the scale below it no
                // longer changes any angle — one metres-per-pixel serves both
                // axes — but it still caps how far a metre of wobble is blown up.
                if (highest - lowest < 20) {
                    var middle = (highest + lowest) / 2;
                    lowest = middle - 10; highest = middle + 10;
                }

                // **One metres-per-pixel for both axes, so the angle drawn is
                // the angle on the ground.** Fitting each axis to its own range
                // is what an elevation profile usually does, and it is why a
                // 73 % descent read as 18 degrees here: measured on this panel,
                // the vertical was 2.2 times coarser than the horizontal on a
                // 3 km chain and 7.5 times on a 42 km one, so the shape said
                // gentle where the crosshair said extreme. Taking the coarser of
                // the two fits the whole chain in the box at a single scale. A
                // steep chain then leaves width unused — 561 px of 1,238 for the
                // 3 km one — and a long gentle chain draws as the ribbon it is,
                // 20 px tall over 42 km. Both are the truth about the ground.
                var base = Math.max(shape.total / wide, (highest - lowest) / tall);

                // **How far in the readings let anyone go.** One per pixel, and
                // the mean spacing is the honest measure of that: the series is
                // laid per edge, so a chain does not sample evenly and a median
                // per render would cost a sort. Where a chain is already drawn
                // finer than it was measured this is 1 and nothing zooms, which
                // is 99 % of them.
                var spacing = readable > 1 ? shape.total / (readable - 1) : shape.total;
                var closest = spacing > 0 ? Math.max(1, base / spacing) : 1;
                view.zoom = Math.min(closest, Math.max(1, view.zoom));
                var metresPerPixel = base / view.zoom;
                var holds = wide * metresPerPixel;
                var shown = Math.min(shape.total, holds);
                view.at = Math.min(Math.max(0, view.at), Math.max(0, shape.total - holds));
                var from = view.at, to = view.at + shown;

                // The band is the **window's** own range and not the chain's.
                // Zoomed into a col, a panel scaled to a summit ten kilometres
                // away would draw the col as a flat line along the foot of the
                // box. At zoom 1 the window is the chain and the two are one.
                var seenLow = Infinity, seenHigh = -Infinity;
                for (i = 0; i < shape.height.length; i += 1) {
                    if (isNaN(shape.height[i])) { continue; }
                    if (shape.distance[i] < from - 1e-6 || shape.distance[i] > to + 1e-6) { continue; }
                    if (shape.height[i] < seenLow) { seenLow = shape.height[i]; }
                    if (shape.height[i] > seenHigh) { seenHigh = shape.height[i]; }
                }
                if (!(seenHigh >= seenLow)) { seenLow = lowest; seenHigh = highest; }
                if (seenHigh - seenLow < 20) {
                    var centre = (seenHigh + seenLow) / 2;
                    seenLow = centre - 10; seenHigh = centre + 10;
                }

                // **The panel's own shape is a gradient** — 171 px over 1,170,
                // or 14.6 % — and it does not move with the zoom. At a true
                // scale a window fits top to bottom exactly when the ground
                // across it averages gentler than that, so zooming in far enough
                // on steep ground must eventually overflow. Measured over the
                // six longest chains: everything fits to 4x, and at 8x three of
                // them stand 108 to 163 m over, which at that scale is 24 to
                // 36 px — the grip above the chart is where those come from.
                // Where it does stand over, the reader drags the window up and
                // down as well, and this is the only case where that does
                // anything: below it the middle is pinned and a vertical drag
                // cannot take the curve off the panel.
                // **The vertical scale, which is the reader's to choose.** At
                // the ground's own scale a long route is a ribbon: 44 km across
                // a phone's panel is 119 m to the pixel, and 691 m of relief is
                // six pixels of it. Lifted, the band is drawn to fill the box --
                // never more than `LIFT_MAX`, so a flat route stays flat -- and
                // the factor is written over the drawing, because a picture at
                // two scales that does not say so is a picture that lies.
                //
                // Only the heights move. The colours are read off the ground and
                // not off the drawing, so what is steep is still steep here, and
                // the crosshair's own reading is a gradient rather than an
                // angle. That is what makes the lift honest rather than merely
                // labelled.
                var liftBy = 1;
                if (lifted) {
                    var relief = Math.max(1e-6, seenHigh - seenLow);
                    liftBy = Math.min(LIFT_MAX, Math.max(1, tall * metresPerPixel * LIFT_FILL / relief));
                }
                liftNow = liftBy;
                var metresPerY = metresPerPixel / liftBy;
                var carries = tall * metresPerY;
                if (seenHigh - seenLow > carries) {
                    if (view.centre === null) { view.centre = (seenLow + seenHigh) / 2; }
                    view.centre = Math.min(Math.max(view.centre, seenLow + carries / 2), seenHigh - carries / 2);
                } else {
                    // **Sea level on the floor wherever it fits.** At a true
                    // scale a long route leaves most of the height unused — 39 km
                    // across this panel is 30 m to the pixel, so the box carries
                    // 5,168 m of it and a route with 658 m of relief draws as a
                    // 22 px ribbon. Centred in that surplus the ribbon sat where
                    // nothing put it, and a point standing at 0 m came out just
                    // under the middle of the box, which reads as half way up
                    // something. Anchored, the floor of the box means sea level
                    // and the ribbon's height above it is the reader's own.
                    //
                    // Clamped both ways, and both bounds are real: below sea
                    // level the lowest reading has to stay in the box, and where
                    // the height binds there is no surplus to spend, so this
                    // comes out at the midpoint and nothing moves.
                    // **Sea level stands clear of the floor rather than on
                    // it.** A waypoint resting at 0 m is a disc, and a disc on
                    // the floor is half a disc; the label had the km numbers
                    // immediately under it as well. The clearance is a layout
                    // margin and not a claim about height, so it is counted in
                    // pixels — and capped against the panel's own height, or a
                    // reader who drags it short spends a quarter of what is left
                    // on empty water.
                    var spare = Math.min(18, tall / 4) * metresPerY;
                    // Where the floor would have to stand for that, and how low
                    // it may go at all without pushing the high point out of the
                    // box. Where sea level cannot be reached the old midpoint is
                    // the answer: pinning the floor as low as it will go instead
                    // would jam the curve against the ceiling, which is the same
                    // arbitrariness the other way up.
                    var wanted = -spare, lowest = seenHigh - carries;
                    var floorM = wanted < lowest ? (seenLow + seenHigh - carries) / 2
                                                 : Math.min(wanted, seenLow);
                    view.centre = floorM + carries / 2;
                }

                var middleY = (box.top + box.bottom) / 2;
                var x = function (value) { return box.left + (value - from) / metresPerPixel; };
                var y = function (value) { return middleY - (value - view.centre) / metresPerY; };

                // **Where each station goes in the strip, decided before the
                // kilometres are drawn**, because the kilometres stand below
                // the strip and the strip is as tall as its rows. Left to
                // right; a station too close to one already in a row takes
                // the next row down.
                var laidStations = [], rows = 0;
                (shape.stations || []).forEach(function (metres, index) {
                    var here = x(metres);
                    if (here < box.left - 1 || here > box.right + 1) { return; }
                    var row = 0;
                    while (laidStations.some(function (other) {
                        return other.row === row && Math.abs(other.here - here) < 2 * STATION_R + 2;
                    })) { row += 1; }
                    rows = Math.max(rows, row + 1);
                    laidStations.push({index: index, metres: metres, here: here, row: row});
                });
                var stripHeight = rows ? STRIP + (rows - 1) * (2 * STATION_R + 3) : 0;
                if (stripHeight !== stripNow) { stripNow = stripHeight; sizePages(); }
                chart.setAttribute('height', chartHeight + stripHeight);
                chart.style.height = (chartHeight + stripHeight) + 'px';
                chart.setAttribute('viewBox', '0 0 ' + width + ' ' + (chartHeight + stripHeight));
                var plot = {left: box.left, right: box.left + shown / metresPerPixel,
                            top: Math.max(box.top, y(seenHigh)), bottom: Math.min(box.bottom, y(seenLow))};
                plot.width = plot.right - plot.left;

                // As many labels as the drawn band can hold rather than a fixed
                // four: a gentle chain is twenty pixels tall at a true scale,
                // and four heights stacked in twenty pixels is one smear. Over
                // what the box shows rather than what the window holds, so a
                // window taller than the panel is not labelled off its own edge.
                var heights = Math.max(2, Math.min(4, Math.round((plot.bottom - plot.top) / 34)));
                // **And none of them closer together than they can be read.**
                // Asking for a number of labels is not the same as having room
                // for them: a 100 m relief over 39 km draws as a three-pixel
                // ribbon, and the two this asked for landed 1.7 px apart and
                // came out as one smear. The count above says how many to aim
                // for; this says which of them there is room to draw.
                var drawnHeights = [], lastY = null;
                ticks(Math.max(seenLow, view.centre - carries / 2),
                      Math.min(seenHigh, view.centre + carries / 2), heights).forEach(function (value) {
                    var at = y(value);
                    if (lastY !== null && Math.abs(at - lastY) < 12) { return; }
                    lastY = at;
                    drawnHeights.push(value);
                    chart.appendChild(line(plot.left, at, plot.right, at, GRID));
                    chart.appendChild(text(plot.left - 6, at + 3, metres(value) + ' m', 'end'));
                });
                // One number of decimals for the whole axis, decided by how far
                // the window runs: 0.00 beside 1.0 reads as two different
                // scales. The gridlines run the box's full height rather than
                // the band's, so a twenty-pixel ribbon still has something to be
                // read against.
                // **And sea level itself, wherever the box holds it.** Every
                // other line on this axis is drawn where the data happens to
                // be; this one is the only height that means the same thing on
                // every profile, and without it the floor of the box is a number
                // a reader has to look up rather than a place they know.
                if (0 >= view.centre - carries / 2 && 0 <= view.centre + carries / 2) {
                    var sea = line(plot.left, y(0), plot.right, y(0), SEA);
                    chart.appendChild(sea);
                    // Not a second time: anchored to the floor, 0 is usually a
                    // tick already, and two labels at one height read as two
                    // heights.
                    if (!drawnHeights.some(function (value) { return Math.abs(value) < 0.5; })) {
                        var label = text(plot.left - 6, y(0) + 3, '0 m', 'end');
                        label.setAttribute('fill', SEA);
                        chart.appendChild(label);
                    }
                }

                var decimals = shown < 2000 ? 2 : 1;
                var alongs = Math.max(2, Math.min(6, Math.round(plot.width / 110)));
                ticks(from, to, alongs).forEach(function (value) {
                    chart.appendChild(line(x(value), box.top, x(value), box.bottom, GRID));
                    chart.appendChild(text(x(value), box.bottom + stripHeight + 14, (value / 1000).toFixed(decimals), 'middle'));
                });
                chart.appendChild(text(plot.right, box.bottom + stripHeight + 14, 'km', 'end'));
                chart.appendChild(line(plot.left, box.top, plot.left, box.bottom, AXIS));
                chart.appendChild(line(plot.left, box.bottom, plot.right, box.bottom, AXIS));

                // Everything that can leave the box goes in here. A window
                // steeper than the panel draws past the top and the bottom, and
                // unclipped that runs over the height labels and out of the
                // panel into the map.
                var framed = function (id, spare) {
                    var frame = document.createElementNS(SVG, 'clipPath');
                    frame.setAttribute('id', id);
                    var shield = document.createElementNS(SVG, 'rect');
                    shield.setAttribute('x', box.left - spare); shield.setAttribute('y', box.top - spare);
                    shield.setAttribute('width', Math.max(0, wide + 2 * spare));
                    shield.setAttribute('height', Math.max(0, tall + 2 * spare));
                    frame.appendChild(shield);
                    chart.appendChild(frame);
                    var group = document.createElementNS(SVG, 'g');
                    group.setAttribute('clip-path', 'url(#' + id + ')');
                    chart.appendChild(group);
                    return group;
                };
                var inside = framed('trails-profile-frame-{{ this.get_name() }}', 0);
                // **Not framed.** The stations stand under the axis, outside
                // the plot the curve is clipped to -- a second frame used to
                // hold them, roomier by a radius, when they sat on the curve.
                // Their rules run up into the plot from the curve's own height
                // and need no clip either.
                var marks = document.createElementNS(SVG, 'g');
                marks.setAttribute('class', 'trails-profile-stations');
                chart.appendChild(marks);

                var slope = gradients(shape);
                var strokes = drawCurve(shape, plot, x, y, slope, from, to);
                if (strokes.some(function (stroke) { return stroke.free; })) { freeKey.style.display = ''; }
                strokes.forEach(function (stroke) {
                    var band = GRADE.bands[stroke.band];
                    var curve = document.createElementNS(SVG, 'path');
                    curve.setAttribute('d', stroke.d);
                    curve.setAttribute('fill', 'none');
                    curve.setAttribute('stroke', band.colour);
                    // Width escalates with the colour, so which stretch is the
                    // steep one survives a red-green confusion.
                    curve.setAttribute('stroke-width', String(band.width));
                    curve.setAttribute('stroke-linejoin', 'round');
                    curve.setAttribute('stroke-linecap', 'round');
                    // Dashed where the ground was crossed rather than followed.
                    // The gradient still bands it: the hill is real even where
                    // the line across it is a straight one somebody drew.
                    if (stroke.free) { curve.setAttribute('stroke-dasharray', FREE_DASH); }
                    inside.appendChild(curve);
                });

                // **The reader's own points, on the profile.** A route is
                // planned by putting points down on the map, and "where is the
                // climb" is only half an answer until the profile says which two
                // points the climb lies between. Drawn as the pin is drawn — a
                // pale disc, a dark ring, the same number — because they are the
                // same point seen from above and from the side, and a reader
                // should not have to work that out. Clipped with the curve: at a
                // zoom most of them are off the panel.
                laidStations.forEach(function (station) {
                    var here = station.here, index = station.index;
                    var sample = nearest(shape.distance, station.metres);
                    var value = shape.height[sample];
                    var read = !isNaN(value);
                    // One the model has no reading for has no height to point
                    // at; its rule is the axis itself.
                    var level = read ? y(value) : box.bottom;
                    var ink = read ? STATION : STATION_UNREAD;
                    // **Drawn as the map draws the same place.** A plan's points
                    // are numbered from its first, and so were these -- which
                    // for the way to a goal put a 1 on where the reader stands,
                    // a place the map marks with no number at all, and a 2 on
                    // the stop the map calls 1. Reported from the phone. The
                    // series now says what each station is: the start is a
                    // dot, the goal is the ring-in-a-ring the map's mark is,
                    // and only the stops between carry the numbers the map
                    // gives them.
                    var mark = selected && selected.marks ? selected.marks[index] : null;
                    var kind = mark && mark.kind ? mark.kind : 'numbered';
                    var radius = kind === 'start' ? STATION_R - 3 : STATION_R;
                    var at = box.bottom + STRIP / 2 + 1 + station.row * (2 * STATION_R + 3);
                    var rule = line(here, level, here, at - radius, ink);
                    rule.setAttribute('stroke-dasharray', '2 2');
                    marks.appendChild(rule);
                    if (kind === 'start') {
                        var dot = document.createElementNS(SVG, 'circle');
                        dot.setAttribute('cx', here); dot.setAttribute('cy', at);
                        dot.setAttribute('r', String(radius));
                        dot.setAttribute('fill', ink);
                        marks.appendChild(dot);
                        return;
                    }
                    if (kind === 'goal' || (selected && selected.stages && selected.stages.indexOf(index) >= 0)) {
                        var ring = document.createElementNS(SVG, 'circle');
                        ring.setAttribute('cx', here); ring.setAttribute('cy', at);
                        ring.setAttribute('r', String(STATION_R + 2.5));
                        ring.setAttribute('fill', 'none');
                        ring.setAttribute('stroke', ink);
                        ring.setAttribute('stroke-width', kind === 'goal' ? '1.5' : '1');
                        marks.appendChild(ring);
                    }
                    var disc = document.createElementNS(SVG, 'circle');
                    disc.setAttribute('cx', here); disc.setAttribute('cy', at);
                    disc.setAttribute('r', String(STATION_R));
                    disc.setAttribute('fill', PAPER);
                    disc.setAttribute('stroke', ink);
                    disc.setAttribute('stroke-width', kind === 'goal' ? '2.5' : '1.5');
                    marks.appendChild(disc);
                    if (kind === 'goal') { return; }
                    var number = text(here, at + 3, mark && mark.label ? mark.label : String(index + 1), 'middle');
                    number.setAttribute('font-size', '9');
                    number.setAttribute('font-weight', 'bold');
                    number.setAttribute('fill', ink);
                    marks.appendChild(number);
                });

                // What the reader is looking at, and only where that is less
                // than all of it. On the 99 % of chains already drawn finer than
                // their own readings neither line ever appears: there is nothing
                // under the drawing to reach, and offering it would be a claim
                // to detail that does not exist.
                // **Said in the pointer's own words.** The gestures are not
                // the same ones, so a line telling a reader to shift-drag is a
                // line telling them to do something they cannot.
                // **What is left here is state, not instruction.** Both hint
                // lines are gone. Reported from a phone: the one anchored at
                // `box.left` and the reading anchored at `box.right` are written
                // to the same `box.top + 8`, and on 390 px the reading lay
                // wholly inside the hint -- 61 to 443 against 253 to 365, with
                // the hint running 53 px off the screen. Taken out on a wide
                // screen too, where the two never meet and it was still a line
                // of prose inside a drawing.
                //
                // **Nothing replaces them, here or in the sheet.** A gesture
                // that has to be described is not discovered by describing it.
                // What a reader sees instead is state: the *whole chain* button,
                // which stands exactly while there is something to go back from.
                //
                // The window stays, because *12.34 km of 42.44* is not a hint --
                // it says which stretch is drawn, which nothing else says once
                // the whole chain is no longer on the panel.
                if (view.zoom > 1.001) {
                    chart.appendChild(text(box.left, box.top + 8, (shown / 1000).toFixed(2) + ' km of '
                        + (shape.total / 1000).toFixed(2), 'start'));
                }

                // The crosshair's own parts, made once and moved afterwards.
                // Rebuilding them per mouse move is the mistake that froze this
                // map twice already, on a layer rather than on a chart. The rule
                // and the dot are clipped with the curve — the dot sits on it,
                // and on an overflowing window that is off the panel.
                var rule = line(plot.left, box.top, plot.left, box.bottom, CROSS);
                var dot = document.createElementNS(SVG, 'circle');
                dot.setAttribute('r', '2.5'); dot.setAttribute('fill', CROSS);
                // **The reading is not drawn in the plot at all any more.** It
                // stood at `box.right` on the same line the hint stood at from
                // `box.left`, which is a collision waiting for a narrow enough
                // screen -- and 390 px is narrow enough. It goes into the
                // heading now: one row, one place, and no text inside the
                // drawing to run into anything.
                [rule, dot].forEach(function (node) { node.style.display = 'none'; inside.appendChild(node); });
                crosshair = {rule: rule, dot: dot, plot: plot, width: width, x: x, y: y, at: -1,
                             slope: slope, box: box, from: from, shown: shown, mpp: metresPerPixel,
                             lift: liftBy, base: base, closest: closest};
                // The mark says what this render worked out, so the two cannot
                // say different factors.
                paintLift();
            }

            // The nearest sample to a distance, over the full series: the
            // reduction above exists so the browser draws 900 points instead of
            // eight thousand, not so a reader hovering over a spike is told the
            // column's height instead of the spike's.
            function nearest(distance, value) {
                var low = 0, high = distance.length - 1;
                while (low < high) {
                    var middle = (low + high) >> 1;
                    if (distance[middle] < value) { low = middle + 1; } else { high = middle; }
                }
                if (low > 0 && Math.abs(distance[low - 1] - value) <= Math.abs(distance[low] - value)) { return low - 1; }
                return low;
            }

            // **What is under a pointer, whatever kind of pointer it is.** A
            // finger never fires a `mousemove`, so on a phone the reading, the
            // rule and the mark on the map did not exist at all — the one thing
            // this panel is for was mouse-only. Taken out of the handler so a
            // touch can ask for the same answer rather than a second version.
            function readAt(clientX) {
                // Not while the window is being moved or a stretch picked: the
                // pointer is moving the curve then, and a reading that chased it
                // would name a different place every frame without the pointer
                // leaving the ground it started on.
                if (dragging || brushing || pinching) { return; }
                if (!crosshair || !selected || !selected.shape) { return; }
                var shape = selected.shape;
                // The drawing is scaled to whatever width the panel ended up
                // with, so a pointer position has to go back through the
                // viewBox before it means anything in the chart's own units.
                var rect = chart.getBoundingClientRect();
                var px = ((clientX - rect.left) / rect.width) * crosshair.width;
                // At a true scale a steep chain leaves width unused — 433 px of
                // 1,238 on the 3 km one — and there is no ground out there to
                // report. Before this the curve always filled the box, so the
                // pointer could not be past its end; now it can, and clamping
                // would pin the reading to the last sample while the pointer
                // sits a third of a panel away from it.
                if (px < crosshair.plot.left - 1 || px > crosshair.plot.right + 1) {
                    forget();
                    return;
                }
                // Through the window rather than through the chain: at zoom
                // 1 the two are the same arithmetic, and past it only this one
                // is right.
                var at = nearest(shape.distance, crosshair.from + (px - crosshair.plot.left) * crosshair.mpp);
                if (at === crosshair.at) { return; }
                crosshair.at = at;
                // The mark on the map, before anything is written: a reader
                // following a climb wants to see where it is, and the sentence
                // beside it is the slower half of the answer.
                standing = positionAt(shape, shape.distance[at]);
                placeHere();
                var here = crosshair.x(shape.distance[at]);
                crosshair.rule.setAttribute('x1', here); crosshair.rule.setAttribute('x2', here);
                crosshair.rule.style.display = '';
                var value = shape.height[at];
                var read = !isNaN(value);
                crosshair.dot.style.display = read ? '' : 'none';
                if (read) {
                    crosshair.dot.setAttribute('cx', here);
                    crosshair.dot.setAttribute('cy', crosshair.y(value));
                }
                var steep = crosshair.slope[at];
                var gradient = '';
                if (!isNaN(steep)) {
                    var band = GRADE.bands[bandOf(steep)];
                    gradient = ' \u00b7 ' + (steep < 0 ? '\u2212' : '+') + Math.round(Math.abs(steep)) + ' %'
                        + (bandOf(steep) ? ', ' + band.label : '');
                }
                readingNow = (shape.distance[at] / 1000).toFixed(2) + ' km \u00b7 '
                    + (read ? metres(value) + ' m' : 'not read') + gradient;
                paintSummary();
            }

            chart.addEventListener('mousemove', function (event) { readAt(event.clientX); });

            // Everything the crosshair is showing, taken back: the rule, the
            // reading, and the mark on the map. In one place because they have to
            // go together — a dot left on the map after the pointer has gone
            // claims a position nobody is pointing at.
            function forget() {
                if (crosshair && crosshair.at !== -1) {
                    crosshair.at = -1;
                    [crosshair.rule, crosshair.dot].forEach(function (node) { node.style.display = 'none'; });
                    readingNow = '';
                    paintSummary();
                }
                if (standing) { standing = null; placeHere(); }
            }

            chart.addEventListener('mouseleave', forget);

            // ---- picking a stretch to look at --------------------------------
            // Press, drag, let go, and the panel draws what lay between the two.
            // One meaning at every zoom: at the whole chain a reader picks where
            // to look, and zoomed in they pick again and go deeper.
            var brushing = null;
            var brush = document.createElementNS(SVG, 'rect');
            brush.setAttribute('fill', 'rgba(21,101,192,0.14)');
            brush.setAttribute('stroke', CROSS);
            brush.setAttribute('stroke-width', '1');
            // Or the rectangle would take the pointer off the chart it is drawn
            // over, and the drag would end the moment it began.
            brush.setAttribute('pointer-events', 'none');

            // Client pixels are not the drawing's: the chart is laid out at
            // whatever width the panel ended up and drawn in its own viewBox.
            // The wheel converts the same way, off the same two numbers.
            function chartX(clientX) {
                var seen = chart.getBoundingClientRect();
                if (!seen.width || !crosshair) { return 0; }
                return ((clientX - seen.left) / seen.width) * crosshair.width;
            }

            function drawBrush(to) {
                var box = brushing.box;
                var began = Math.max(box.left, Math.min(box.right, brushing.from));
                var here = Math.max(box.left, Math.min(box.right, to));
                brush.setAttribute('x', Math.min(began, here));
                brush.setAttribute('width', Math.abs(here - began));
                brush.setAttribute('y', box.top);
                brush.setAttribute('height', Math.max(0, box.bottom - box.top));
            }

            // ---- the window on the chain, which a reader moves ---------------
            // One redraw a frame, for the reason the grip has one: a redraw per
            // event is the mistake that froze this map twice, and a long chain
            // is four hundred separate strokes.
            var settling = false;
            function redraw() {
                if (settling) { return; }
                settling = true;
                window.requestAnimationFrame(function () { settling = false; render(); });
            }

            // **The wheel stays the map's, except over a curve that can use it.**
            // A panel that swallows a wheel and does nothing with it reads as
            // the map having frozen the moment the panel opened — which is why
            // this panel has only ever taken clicks, and why the map's own
            // 9 to 11 is unchanged everywhere else on it. So the chart takes the
            // wheel exactly where there is detail under the drawing to reach,
            // and lets it through where there is not: 126 chains of 11,264, and
            // every route long enough to be worth planning.
            chart.addEventListener('wheel', function (event) {
                if (!crosshair || !(crosshair.closest > 1.001)) { return; }
                event.preventDefault();
                event.stopPropagation();
                // A wheel says its delta in pixels, lines or pages, and a line
                // is not a pixel. Four notches of a mouse double the scale.
                var step = event.deltaY * (event.deltaMode === 1 ? 20 : (event.deltaMode === 2 ? 400 : 1));
                var wanted = Math.min(crosshair.closest, Math.max(1, view.zoom * Math.pow(2, -step / 400)));
                if (wanted === view.zoom) { return; }
                var rect = chart.getBoundingClientRect();
                var px = ((event.clientX - rect.left) / rect.width) * crosshair.width;
                // The ground under the pointer stays under the pointer, which is
                // what makes a wheel read as a lens rather than as a slider.
                var under = crosshair.from + (px - crosshair.box.left) * crosshair.mpp;
                view.zoom = wanted;
                view.at = under - (px - crosshair.box.left) * (crosshair.base / wanted);
                redraw();
            }, {passive: false});

            // Dragging moves the window, in both directions: along the chain,
            // and up and down where the window is steeper than the panel and so
            // does not all fit. render() pins the second whenever it does fit,
            // so there is no way to drag the curve off its own panel.
            var dragging = null;
            chart.addEventListener('mousedown', function (event) {
                if (!crosshair) { return; }
                // **Shift moves the window; a plain drag picks a stretch.** The
                // pointer was free for it — a plain drag did nothing at all at
                // the whole chain, and moved the window only once a wheel had
                // already zoomed into something. Moving is not taken away for
                // it: taking a working gesture off a reader to avoid an overlap
                // is not an improvement, which this document says already about
                // a row of buttons.
                if (event.shiftKey) {
                    if (!(view.zoom > 1.001)) { return; }
                    forget();
                    dragging = {x: event.clientX, y: event.clientY, at: view.at, centre: view.centre, mpp: crosshair.mpp};
                    chart.style.cursor = 'grabbing';
                    event.preventDefault();
                    return;
                }
                // The wheel's own proviso: where there is nothing under the
                // drawing to reach there is no stretch worth picking either, and
                // a rectangle that zoomed to nothing would be a claim to detail
                // that does not exist.
                if (!(crosshair.closest > 1.001)) { return; }
                forget();
                brushing = {from: chartX(event.clientX), box: crosshair.box,
                            at: crosshair.from, mpp: crosshair.mpp, base: crosshair.base};
                drawBrush(brushing.from);
                chart.appendChild(brush);
                event.preventDefault();
            });
            document.addEventListener('mousemove', function (event) {
                if (!dragging) { return; }
                view.at = dragging.at - (event.clientX - dragging.x) * dragging.mpp;
                view.centre = dragging.centre + (event.clientY - dragging.y) * dragging.mpp;
                redraw();
            });
            document.addEventListener('mouseup', function () {
                if (!dragging) { return; }
                dragging = null;
                chart.style.cursor = 'crosshair';
            });

            document.addEventListener('mousemove', function (event) {
                if (!brushing) { return; }
                drawBrush(chartX(event.clientX));
            });
            document.addEventListener('mouseup', function (event) {
                if (!brushing) { return; }
                var picked = brushing;
                brushing = null;
                if (brush.parentNode) { brush.parentNode.removeChild(brush); }
                if (!crosshair) { return; }
                var box = picked.box;
                var began = Math.max(box.left, Math.min(box.right, picked.from));
                var here = Math.max(box.left, Math.min(box.right, chartX(event.clientX)));
                // **Six pixels, because a click is a drag of nothing.** Under
                // that the reader meant to click, and zooming to a stretch a few
                // metres wide would lose the chain to a slip of the hand.
                if (Math.abs(here - began) < 6) { return; }
                var wide = box.right - box.left;
                var span = Math.abs(here - began) * picked.mpp;
                if (!(span > 0) || !(wide > 0)) { return; }
                // Metres a pixel is `base / zoom`, which is the wheel's own
                // arithmetic read the other way: the stretch picked is the one
                // that has to fill the plot.
                view.zoom = Math.min(crosshair.closest, Math.max(1, picked.base * wide / span));
                view.at = picked.at + (Math.min(began, here) - box.left) * picked.mpp;
                // The height fits itself to what was picked, the way it does for
                // a fresh selection: a vertical a reader set over one stretch is
                // not a claim about another.
                view.centre = null;
                redraw();
            });

            // Back to the whole chain. The map never sees this — the panel stops
            // clicks at its own edge — and the header's own click, which folds
            // the panel away, is a different element.
            chart.addEventListener('dblclick', function (event) {
                if (!(view.zoom > 1.001)) { return; }
                event.preventDefault();
                view.zoom = 1; view.at = 0; view.centre = null;
                redraw();
            });

            // ---- and the same two gestures with a finger --------------------
            // **Two fingers apart is in and together is out**, which is the one
            // gesture every map on a phone already answers, and this curve is a
            // map of a walk. One finger moves the window, the way a press and a
            // drag do with a mouse.
            //
            // **The wheel's rule is kept exactly**: where there is no detail
            // under the drawing to reach, the gesture is not taken and Leaflet's
            // own pinch gets it. A panel that swallowed a pinch and did nothing
            // with it would read as the map having frozen the moment the panel
            // opened, which is the reason the wheel behaves that way.
            function spanOf(touches) {
                var dx = touches[0].clientX - touches[1].clientX;
                var dy = touches[0].clientY - touches[1].clientY;
                return Math.max(1, Math.sqrt(dx * dx + dy * dy));
            }

            function midOf(touches) {
                return {x: (touches[0].clientX + touches[1].clientX) / 2,
                        y: (touches[0].clientY + touches[1].clientY) / 2};
            }

            var pinching = null;
            chart.addEventListener('touchstart', function (event) {
                if (!crosshair) { return; }
                if (event.touches.length === 2) {
                    // The pinch keeps the wheel's proviso: where there is nothing
                    // under the drawing to reach, the gesture is not taken and
                    // Leaflet's own gets it.
                    if (!(crosshair.closest > 1.001)) { return; }
                    forget();
                    var rect = chart.getBoundingClientRect();
                    var mid = midOf(event.touches);
                    var px = ((mid.x - rect.left) / rect.width) * crosshair.width;
                    // The ground between the two fingers stays between them,
                    // which is what makes a pinch a lens rather than a slider.
                    // The wheel's own rule, written once more for the other
                    // pointer, off the same three numbers.
                    pinching = {span: spanOf(event.touches), zoom: view.zoom, px: px, mid: mid,
                                centre: view.centre, scale: crosshair.width / rect.width,
                                under: crosshair.from + (px - crosshair.box.left) * crosshair.mpp};
                    dragging = null;
                    event.preventDefault();
                    return;
                }
                if (event.touches.length === 1) {
                    // **One finger reads.** There is no hover on a phone, so the
                    // only way to ask what is under a place is to touch it — and
                    // this is what the panel is *for*. It used to move the
                    // window instead, which meant a reader with a finger could
                    // never get the reading at all, and on the 99 % of chains
                    // with nothing to zoom into it did not even do that.
                    // Moving went to two fingers, beside the zoom, which is
                    // where a map puts it.
                    pinching = null;
                    dragging = null;
                    readAt(event.touches[0].clientX);
                    event.preventDefault();
                }
            }, {passive: false});

            chart.addEventListener('touchmove', function (event) {
                if (pinching && event.touches.length === 2) {
                    var wanted = Math.min(crosshair.closest,
                        Math.max(1, pinching.zoom * (spanOf(event.touches) / pinching.span)));
                    var mid = midOf(event.touches);
                    // **Zoom about the fingers and move with them, in one
                    // gesture.** Two fingers are the map's own way of doing
                    // both, and separating them here would leave a zoomed
                    // window with no way to walk along it.
                    var mpp = crosshair.base / wanted;
                    var carried = (mid.x - pinching.mid.x) * pinching.scale;
                    view.zoom = wanted;
                    view.at = pinching.under - (pinching.px - crosshair.box.left) * mpp - carried * mpp;
                    if (pinching.centre !== null) {
                        view.centre = pinching.centre + (mid.y - pinching.mid.y) * pinching.scale * mpp;
                    }
                    event.preventDefault();
                    redraw();
                    return;
                }
                if (event.touches.length === 1) {
                    readAt(event.touches[0].clientX);
                    event.preventDefault();
                }
            }, {passive: false});

            function fingersUp(event) {
                if (event.touches.length < 2) { pinching = null; }
                if (event.touches.length === 0) {
                    dragging = null;
                    chart.style.cursor = 'crosshair';
                    // **The reading goes with the finger that made it.** A mouse
                    // leaving the chart has always taken the rule, the dot and
                    // the reading with it; a finger lifted left all three
                    // standing, so the row went on saying *612 m at 8.42 km*
                    // over a page about something else entirely.
                    forget();
                }
            }
            chart.addEventListener('touchend', fingersUp);
            chart.addEventListener('touchcancel', fingersUp);

            function backToWhole() {
                if (!(view.zoom > 1.001)) { return; }
                view.zoom = 1; view.at = 0; view.centre = null;
                redraw();
            }
            // The header's own click folds the panel away; this is a different
            // thing standing in the same row.
            whole.addEventListener('click', function (event) { event.stopPropagation(); backToWhole(); });

            // **A double click is the mouse's and does not reach a finger.**
            // The position is checked as well as the interval: two taps 300 ms
            // apart at opposite ends of the chart are two readings and not one
            // gesture, and a reader who has just dragged the window would
            // otherwise lose it.
            var lastTap = 0, lastTapAt = null;
            chart.addEventListener('touchend', function (event) {
                if (event.touches.length > 0 || pinching) { return; }
                var finger = event.changedTouches && event.changedTouches[0];
                if (!finger) { return; }
                var now = Date.now();
                var near = lastTapAt && Math.abs(finger.clientX - lastTapAt.x) < 30 &&
                    Math.abs(finger.clientY - lastTapAt.y) < 30;
                if (now - lastTap < 300 && near) {
                    lastTap = 0; lastTapAt = null;
                    backToWhole();
                    return;
                }
                lastTap = now;
                lastTapAt = {x: finger.clientX, y: finger.clientY};
            });

            // ---- what is selected -------------------------------------------
            var selected = null;
            // Whether something else owns the map's clicks. Plan mode does
            // while it is on: a click there places a waypoint, and a panel that
            // also answered it would select a chain out from under the route.
            var suspended = false;

            // **What to call the selected line, asked of what the line carries.**
            // It used to be read off the line's own hover label, which is how
            // the name came to be drawn on the map at all — and a label that
            // opens on a tap and stays there is a second heading over the
            // ground, saying what the row at the foot already says. The name
            // travels with the figures, is the same string the file writer
            // uses, and needs nothing drawn to be readable.
            //
            // The hover label is still read where there is one, so a page built
            // with labels and without carried names still names its lines. A
            // tooltip is markup — folium wraps the name in a div — and this is
            // written into a heading as text, so the tags come out rather than
            // being rendered.
            function labelOf(layer, className) {
                var figure = figures[className] || {};
                if (figure.name) { return figure.name; }
                var tooltip = layer && layer.getTooltip && layer.getTooltip();
                var content = tooltip && tooltip.getContent();
                if (typeof content === 'string') { return content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim(); }
                if (content && content.textContent) { return content.textContent.trim(); }
                return figure.id;
            }

            //: How many chips the row may hold. Four fit across 390 px and
            //: the rest are scrolled to; past six a reader is reading a list
            //: rather than making a choice, and the ones cut off are the
            //: furthest from the finger.
            var CHOICES_MAX = 6;

            // What a line is *one of*, which is the question a bundle raises.
            // The figures carry it; a line whose source went missing stands for
            // itself, and its own name is then the key as well as the label.
            function sourceKey(className) {
                var figure = className ? figures[className] : null;
                if (!figure) { return null; }
                return figure.source || figure.name || className;
            }

            // **Everything that tap could have meant**, in the order the reach
            // ranks them: the same measurement that picked the winner, asked
            // for the whole list. A line with no figures is not offered --
            // there would be nothing to show for it.
            //
            // **One chip per source and not one per line.** Measured at the
            // busiest crossing on this map: thirteen lines within one finger,
            // eight of them FKB fragments of the same path, and a row of
            // thirteen chips reading `fkb-373967-7264149-8` is not a choice
            // anybody can make. *Which source* is the question that was asked;
            // the nearest line of each is the answer, and it is the line the tap
            // would have taken anyway.
            function gather(at) {
                choices = [];
                if (!at || !window.trailsReach || !window.trailsReach.near) { return; }
                var seen = {};
                window.trailsReach.near(map.latLngToLayerPoint(at)).forEach(function (found) {
                    var className = found.layer.options.className;
                    var key = sourceKey(className);
                    if (!key || seen[key]) { return; }
                    seen[key] = true;
                    choices.push({gap: found.gap, key: key, className: className, layer: found.layer,
                                  label: labelOf(found.layer, className),
                                  source: figures[className].source || ''});
                });
                // **The planned route last, however near it ran.** It is not one
                // of this map's sources, and it lies on them by construction --
                // it was routed along them -- so ranking it by distance dropped
                // it into the middle of the row and moved the sources a reader
                // was choosing between. Its place is a fact about what it is and
                // not about where the finger landed.
                //
                // Not offered while plan mode is on: there the panel is showing
                // it already, and a tap means *put a point here*.
                var reach = (window.trailsReach && window.trailsReach.finger) || undefined;
                var route = (!planNow && window.trailsPlan && window.trailsPlan.onRoute)
                    ? window.trailsPlan.onRoute(at.lat, at.lng, reach) : null;
                var mine = [];
                if (route) {
                    mine.push({gap: Infinity, mine: 'plan', key: 'plan', className: null,
                               label: 'Planned route', source: 'Planned route'});
                }
                // **And the way to a goal, after it and by the same rule.** It
                // is the reader's own line too and lies on the sources by
                // construction, so ranking it by distance would move the sources
                // about; and it goes last of the two because it is the more
                // recent of the two things they made, which is the one a tap
                // takes. Wherever it runs, not only where the finger landed --
                // its line takes no clicks either.
                var wayThere = (!planNow && window.trailsGoal) ? window.trailsGoal.state() : null;
                // **And only where it runs**, which is the rule the planned
                // route follows and the one this was missing: offered wherever
                // the tap landed, it took every tap on the map, and a way tapped
                // in order to be read was answered with the goal.
                if (wayThere && wayThere.line && window.trailsGoal.near(at.lat, at.lng, reach)) {
                    mine.push({gap: Infinity, mine: 'goal', key: 'goal', className: null,
                               label: 'To the goal', source: 'To the goal'});
                }
                choices.sort(function (a, b) { return a.gap - b.gap; });
                choices = choices.slice(0, Math.max(1, CHOICES_MAX - mine.length)).concat(mine);
            }

            // The source, because that is what the row is asking about. A line
            // whose source went missing says whatever it can about itself.
            function choiceName(entry) {
                return entry.source || entry.label || 'this line';
            }

            // Which chip is the one being shown. **By source and not by line**:
            // the chip stands for a source, and the fragment of it the reader is
            // looking at may not be the fragment the chip would select -- one
            // path drawn in eight pieces is eight class names and one answer.
            function litChoice(entry) {
                if (!selected) { return false; }
                // The two composed routes are told apart by which one it is and
                // not by `composed`, which both of them are.
                if (entry.mine === 'goal') { return !!selected.goal; }
                if (entry.mine === 'plan') { return !!(selected.composed && !selected.goal); }
                return sourceKey(selected.className) === entry.key;
            }

            // **The reader's own line among what the tap reached**, if either
            // is there: the way to a goal before the planned route, because it
            // is the more particular of the two and the one they set last.
            // Neither line takes a click, so this is the only way either can be
            // part of what a tap meant.
            function planChoice() {
                var found = null;
                for (var at = 0; at < choices.length; at += 1) {
                    if (choices[at].mine === 'goal') { return choices[at]; }
                    if (choices[at].mine === 'plan' && !found) { found = choices[at]; }
                }
                return found;
            }

            function takeChoice(entry) {
                // **The route first, and before the question of whether it is
                // already showing.** A tap in reach of it lands on a line as
                // well, and that line's own handler lights it up: measured, a
                // tap on the route while the route was already on the panel
                // left the trail under it widened, because this returned early
                // and never told the highlight to let go.
                if (entry.mine) {
                    // **The line that was chosen has to let go.** Reported: the
                    // panel changed to the route and the trail underneath it
                    // stayed widened and the rest of the map stayed faded --
                    // and worse, the two were then out of step, so pressing
                    // that trail's chip again cleared the highlight instead of
                    // taking it and every other press marked nothing. The
                    // highlight is a selection made by clicking and this is a
                    // selection; one of them has to go.
                    // `hold` and not `clear`: on a tap this runs before the
                    // highlight's own handler, so clearing would be undone by
                    // the line that was tapped a moment later.
                    if (window.trailsHighlight) {
                        if (window.trailsHighlight.hold) { window.trailsHighlight.hold(); }
                        else { window.trailsHighlight.clear(); }
                    }
                    // And so does the other composed route, which is not
                    // highlighted on the map and therefore not covered by the
                    // line above: two of them can be offered and one of them is
                    // what the panel is drawing.
                    if (!litChoice(entry)) {
                        if (entry.mine === 'goal' && window.trailsGoal) {
                            window.trailsGoal.show();
                        } else if (window.trailsPlan && window.trailsPlan.show) {
                            if (window.trailsGoal) { window.trailsGoal.letGo(); }
                            window.trailsPlan.show();
                        }
                    }
                    // **Painted even where nothing changes.** The row belongs to
                    // the tap that gathered it, and a tap that selects what is
                    // already selected still gathered a new row -- driven, that
                    // row came out empty, because only a repaint draws it.
                    paintChoices();
                    return;
                }
                if (litChoice(entry)) { paintChoices(); return; }
                // **Fired as the click it stands for.** Everything a click on
                // that line does -- the highlight widening it, its own details
                // arriving, this panel selecting it -- is already wired to that
                // event, and a second path through them is a second set of
                // rules to keep in step.
                //
                // **And without the point it was tapped at**, which is what
                // keeps the row still. The list came from a measurement to the
                // paint, and selecting a line widens it by four pixels and
                // brings it to the front: measured, re-asking after the press
                // moved the pressed chip to the head of the row, under the
                // reader's finger, every single time. The row belongs to the
                // tap that made it and not to what is selected now.
                if (window.trailsGoal) { window.trailsGoal.letGo(); }
                entry.layer.fire('click', {layer: entry.layer});
            }

            function paintChoices() {
                var wanted = selected && choices.length > 1;
                var was = picks.style.display;
                picks.innerHTML = '';
                picks.style.display = wanted ? 'flex' : 'none';
                if (wanted) {
                    choices.forEach(function (entry) {
                        var lit = litChoice(entry);
                        var chip = document.createElement('button');
                        chip.type = 'button';
                        chip.className = 'trails-profile-pick' + (lit ? ' trails-profile-pick-on' : '');
                        chip.textContent = choiceName(entry);
                        chip.title = entry.label || entry.source;
                        chip.setAttribute('aria-pressed', String(lit));
                        chip.style.cssText = 'font:inherit;font-size:11px;padding:3px 9px;flex:none;' +
                            'max-width:44%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;' +
                            'border:1px solid var(--trails-rule);border-radius:10px;cursor:pointer;' +
                            'background:' + (lit ? 'var(--trails-accent)' : 'var(--trails-solid)') + ';' +
                            'color:' + (lit ? 'var(--trails-on-accent)' : 'var(--trails-ink-2)');
                        chip.addEventListener('click', function (event) {
                            event.stopPropagation();
                            takeChoice(entry);
                        });
                        picks.appendChild(chip);
                    });
                }
                // The panel is a different height with this row than without it,
                // and two things measure that height: the pages cap themselves
                // against it and the chrome places everything else around it.
                // Only when it actually appears or goes, or every repaint would
                // ask the chrome to lay the page out again.
                if (was !== picks.style.display) {
                    sizePages();
                    if (window.trailsChrome && window.trailsChrome.placed) { window.trailsChrome.placed(); }
                }
            }

            // **What the heading says and what the sheet says are one list.**
            // The heading takes the first three -- how far, how much climb, how
            // steep at worst, which is what a walk is decided on -- and the
            // sheet takes all of them in the same order. A second list for the
            // second rendering is how a page comes to tell two stories about one
            // route, which this one has managed three times.
            var saidLines = [];

            // **The heading says one of two things, and only one at a time.**
            // At rest it is the first three figures; while a pointer is on the
            // curve it *is* the reading, in the crosshair's own colour. That is
            // what makes the collision impossible rather than merely fixed:
            // there is no second place for a reading to be drawn.
            var saidText = '';
            var readingNow = '';
            // **What the row says while a route is being made.** Plan mode's own
            // bar said this and stood above this panel's heading saying
            // something else about the same route; there is one row now, so the
            // wording moved here whole rather than being written a second time.
            function planSays() {
                var count = planNow ? planNow.points : 0;
                if (!count) { return 'Tap the map to place the first point'; }
                // **`isFinite` and not a null check.** A route whose legs are
                // all crossings has no walked distance and no climb, and the
                // ascent comes back NaN rather than null.
                var told = count + (count === 1 ? ' point' : ' points');
                if (count > 1 && isFinite(planNow.metres)) {
                    told += ' \u00b7 ' + (planNow.metres / 1000).toFixed(2) + ' km';
                }
                if (isFinite(planNow.ascent)) { told += ' \u00b7 +' + Math.round(planNow.ascent) + ' m'; }
                return told;
            }
            function planHint() {
                if (!planNow || !planNow.points) { return 'Plan mode is on'; }
                return planNow.working ? 'working\u2026' : 'tap for the points';
            }
            function planning() { return !!(planNow && planNow.on); }
            function paintSummary() {
                summary.textContent = readingNow || (planning() ? planHint() : saidText);
                summary.style.color = readingNow ? 'var(--trails-accent)' : 'var(--trails-ink-2)';
                // **Which of the two it is saying, as a fact and not as a
                // colour.** A probe comparing a computed `rgb()` against the
                // token's hex never matches -- and a state that can only be read
                // back off a colour is a state recorded twice, once for the eye
                // and once for nobody.
                summary.classList.toggle('trails-profile-reading', !!readingNow);
                // The name above it, from the same call: the two lines are one
                // sentence about one thing and must never be about two.
                name.textContent = planning()
                    ? planSays()
                    : ((selected && selected.label) || '');
                var goalShown = !!(!planning() && selected && selected.goal);
                hide.innerHTML = planning() ? '\u2713' : goalShown ? GOAL_STRUCK : '\u00d7';
                hide.title = planning() ? 'Finish planning' : goalShown ? 'Drop the goal' : 'Put this away';
                hide.classList.toggle('trails-profile-hide-goal', goalShown);
                hide.setAttribute('aria-label', hide.title);
                // Only where there is something to be done with: a page that
                // has nothing selected and nothing being planned says so in the
                // line above, and a way out of nothing is not a control.
                hide.style.display = (open || planning()) ? 'flex' : 'none';
            }

            function sayLines(lines) {
                saidLines = lines;
                saidText = lines.slice(0, 3).join(' \u00b7 ');
                readingNow = '';
                paintSummary();
                showLicences();
                paintPages();
                paintChoices();
                paintLift();
            }

            function say(message) {
                saidLines = [];
                saidText = message;
                readingNow = '';
                paintSummary();
                showLicences();
                paintPages();
                paintChoices();
                paintLift();
            }

            // What a composed series says about itself. The distance is the
            // **walking** distance and says so: a crossing is never counted
            // into it, and whatever composed the series reports the crossings
            // beside it in `told`. A flat line at zero would be a claim about
            // ground that is not there, and so would a total that swallowed a
            // crossing.
            // `extra` is handed in rather than read off the selection: the
            // panel says this above the button and the file says it in the
            // track's <desc>, and the two must be one sentence written once.
            // **The first three are the ones a walk is decided on**, and that
            // order is load-bearing now rather than cosmetic: the panel's heading
            // shows `slice(0, 3)` of exactly this list. The file's own
            // description is written from it too, so the two cannot drift.
            function planned(figure, shape, extra) {
                var told = [];
                told.push((shape.total / 1000).toFixed(2) + ' km on foot');
                if (shape.read) {
                    told.push(climb(figure));
                    var worst = steepestOf(shape);
                    if (!isNaN(worst)) { told.push('steepest ' + Math.round(worst) + ' %'); }
                    told.push('high ' + metres(figure.high) + ' m', 'low ' + metres(figure.low) + ' m');
                }
                told = told.concat(extra || []).concat(protectedIn(shape));
                if (!shape.read) {
                    told.push(shape.total > 0 ? 'no height was read along it' : 'no ground under any of it');
                }
                return told;
            }

            // Which protected areas the route runs through and how far through
            // each. Read off the list whatever composed the route already
            // filtered, never re-filtered here: the sentence above the button,
            // the sentence in the file and the markers the file carries have to
            // name the same areas, and a second application of a threshold is a
            // second threshold.
            //
            // **It says where the route is and nothing about what may be done
            // there.** The rules inside a Norwegian protected area differ from
            // outside, but how they differ is in each area's verneforskrift and
            // not one has been read. This is a fact about the route.
            function protectedIn(shape) {
                return (shape.protected || []).map(function (area) {
                    return (area.metres / 1000).toFixed(2) + ' km in ' + area.name + ' ' + area.form;
                });
            }

            // **And the pages are drawn from the description**, because what
            // there is to read changes when it arrives rather than when it is
            // asked for: a chain's series is composed a megabyte of arithmetic
            // after the click, and a page set worked out at the click has no
            // profile in it. Every path through here ends at `sayLines` or
            // `say`, and both of those repaint.
            function describe() {
                if (!selected) { say(suspended ? 'Plan mode: click the map to place a point.' : 'Click a line to see its profile.'); return; }
                // **A place has nothing under its name.** It said *click a line
                // to see its profile* -- the sentence for an empty panel, under
                // the name of the thing the reader had just chosen, telling them
                // to do what they had done.
                if (selected.detail) { say(''); return; }
                var figure = selected.figure, shape = selected.shape;
                if (!shape) { say(selected.saying || 'Decoding the network\u2026'); return; }
                if (selected.composed) { sayLines(planned(figure, shape, selected.told)); return; }
                if (!shape.read) {
                    // Two kinds of nothing, and they are not the same nothing.
                    // A flat line at zero would be a claim about ground that was
                    // never asked about.
                    say(shape.crossing
                        ? 'No profile: there is no ground under a crossing.'
                        : 'No profile: the height model has no reading along this stretch.');
                    return;
                }
                // The chain's steepest is the **build's**, the same number its
                // popup carries, and not one worked out here from the drawn
                // series: those two agree to about a part in a thousand and
                // disagree in the third decimal, which is one number too many
                // for one chain in one page.
                var steepest = figure.steepest;
                var lines = [(shape.total / 1000).toFixed(2) + ' km', climb(figure)];
                if (!(steepest === null || steepest === undefined || isNaN(steepest))) {
                    lines.push('steepest ' + Math.round(Math.abs(steepest)) + ' %');
                }
                lines.push('high ' + metres(figure.high) + ' m', 'low ' + metres(figure.low) + ' m');
                if (figure.bearing === null) { lines.push('a loop, so it climbs the same either way'); }
                sayLines(lines);
            }

            // What pressing the button would get you, worked out from the same
            // series the file is written from rather than estimated beside it.
            // The points are counted here and written there, so the figure a
            // reader is shown is the one the file holds.
            function offered() {
                if (!EXPORT) { return; }
                // A series composed by something that offered no description of
                // what it composed cannot be written out: the file has to say
                // what its legs are and where its waypoints went, and a button
                // this panel could not honour is worse than no button at all.
                var writable = !!(selected && !selected.detail && (!selected.composed || selected.plan));
                offer.style.display = writable ? 'block' : 'none';
                // The mark now stands in the heading rather than in that row, so
                // it needs the condition said to it as well: a panel showing a
                // series nobody described cannot write a file, and a mark that
                // does nothing is worse than no mark.
                download.style.display = writable ? 'flex' : 'none';
                if (garminDownload) { garminDownload.disabled = true; }
                noted.textContent = '';
                // A place has no walk to write out and no sources of its own --
                // its popup names them itself -- so the row underneath the
                // drawing is about a drawing that is not there.
                if (selected && selected.detail) { carries.textContent = ''; licensed.textContent = ''; return; }
                if (!selected) { return; }
                if (!selected.shape) {
                    download.disabled = true;
                    // Whatever went wrong with the graph is said once, above,
                    // by the line that knows what it was. Saying 'decoding' here
                    // as well would contradict it — and a reader believes the
                    // thing next to the button they were about to press.
                    carries.textContent = selected.missing ? '' : 'Decoding the network\u2026';
                    licensed.textContent = '';
                    return;
                }
                selected.runs = runsOf(selected.shape);
                var points = pointsIn(selected.runs);
                if (selected.composed) {
                    // **A composed route without a plan is the way to a goal**,
                    // and it has figures of its own like any other. This used to
                    // return before reaching them, on the grounds that only a
                    // plan is composed -- so a goal's page kept whatever the
                    // line read before it had said: its point count, its
                    // licences, its marking. Reported from the phone as *the
                    // info is from another way*, and it was.
                    var plan = selected.plan;
                    // **Refused while any leg is unsettled, and said.** The file
                    // states that it breaks only at crossings; a leg still being
                    // worked out, or one the height service refused, is a hole
                    // that would break it somewhere else and nothing in the file
                    // would say so. A goal is not written out at all -- the
                    // button is already hidden above -- so there is nothing to
                    // refuse and nothing to say about refusing it.
                    download.disabled = !plan || points < 2 || !!plan.why;
                    if (garminDownload) { garminDownload.disabled = download.disabled; }
                    // Only what the header does not already say. It carried
                    // the climb, the crossings and the distance a second time,
                    // word for word, in the row underneath the row that said
                    // them — five rows where two will do.
                    carries.textContent = (plan && plan.why) ? plan.why
                        : points.toLocaleString('en-GB') + ' points';
                    licensed.textContent = routeCredits(selected.shape, selected.runs).map(licenceLine).join(' \u00b7 ');
                    noted.textContent = markingLine(selected.shape.tally);
                    return;
                }
                download.disabled = points < 2;
                // The climb and the distance are in the header. What belongs
                // here is what only the file has — how many points it holds —
                // and the one case the header cannot show, a stretch the height
                // model never read, because then the header says so instead.
                carries.textContent = points.toLocaleString('en-GB') + ' points';
                licensed.textContent = creditsOf(selected.figure, selected.runs).map(licenceLine).join(' \u00b7 ');
            }

            if (EXPORT) {
                function saveGarminNow() {
                    if (!selected || !selected.composed || !selected.runs ||
                        !selected.plan || selected.plan.why || pointsIn(selected.runs) < 2) { return; }
                    saveFile(fileNameOf((selected.plan.stem || EXPORT.route.fileStem) + '-garmin'),
                             garminGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told));
                }
                function saveNow() {
                    if (!selected || !selected.runs) { return; }
                    if (selected.composed) {
                        if (!selected.plan || selected.plan.why) { return; }
                        // **The tour's name, where it has one.** This is the
                        // button most routes are downloaded with, and it was the
                        // one place that never asked the plan what the file is
                        // called: every route came off it as `-route.gpx`
                        // however carefully the tour had been named, while the
                        // stage buttons two panels away got it right. Same rule
                        // as `routeFile` — `stem` is the file's name, and the
                        // export's own stem is what a tour nobody named falls
                        // back to.
                        saveFile(fileNameOf((selected.plan.stem) || EXPORT.route.fileStem),
                                 routeGpxOf(selected.figure, selected.shape, selected.runs, selected.plan, selected.told, crossings()));
                        return;
                    }
                    saveFile(fileNameOf(selected.figure.id), gpxOf(selected.figure, selected.shape, selected.runs));
                }
                download.addEventListener('click', function (event) {
                    event.stopPropagation();
                    // Every composed route has a choice: the ordinary GPX or
                    // a Garmin course. Only the archive needs multiple stages;
                    // a chain still saves directly from this mark.
                    if (selected && selected.composed) {
                        var cut = planning() && window.trailsPlan && window.trailsPlan.stages
                            ? window.trailsPlan.stages() : 0;
                        stagesDownload.style.display = cut > 1 ? 'block' : 'none';
                        saveMenu.style.display = saveMenu.style.display === 'block' ? 'none' : 'block';
                        return;
                    }
                    saveMenu.style.display = 'none';
                    saveNow();
                });
                // The same choices and order as the plan panel's save menu,
                // using the existing writers for both files and the archive.
                var stagesDownload = saveEntry('All stages (zip)',
                    'Every stage and the whole tour, as ordinary GPX and Garmin courses, in one archive',
                    function () { if (window.trailsPlan && window.trailsPlan.saveStages) { window.trailsPlan.saveStages(); } });
                saveMenu.appendChild(stagesDownload);
                saveMenu.appendChild(saveEntry('Whole tour (GPX)',
                    'The whole route as one GPX file, its stage marks and all',
                    function () { saveNow(); }));
                var garminDownload = saveEntry('For Garmin (course)',
                    'One line of at most 200 points; Garmin Explore imports it as a course that syncs to the watch',
                    function () { saveGarminNow(); });
                garminDownload.className = 'trails-profile-garmin';
                saveMenu.appendChild(garminDownload);
            }

            // Everything that happens whatever is selected. Two things reach
            // the panel — a chain, whose figures are read off the table this
            // was handed, and a series composed elsewhere — and they differ
            // only in how they arrive.
            function present(given) {
                // **A popup belongs to the thing it came off.** Cleared when the
                // selection goes and not when it changes: a line's own popup
                // arrives *before* the click that selects the line -- Leaflet
                // fires the popup's handler first -- so clearing on every change
                // would throw away the page that had just arrived. Driven, plan
                // mode showed the table of whatever line had been chosen before
                // it, on the page where the points belong.
                // **Except while plan mode owns the map.** Nothing else can
                // open a popup there -- every click on the map is a waypoint --
                // so the only way one exists is that the reader asked for it,
                // out of the search. Cleared on the plan's next refresh, and
                // the plan refreshes on every edit, it was held exactly where
                // `wantedPages` says it must not be: in a page nobody can read.
                if (given === null) { if (!suspended) { detailHtml = null; } choices = []; }
                // **And a composed route has no popup of its own.** Reported:
                // taking the planned route from the row of choices left the
                // ⓘ page showing the table of the line chosen before it --
                // because a popup is cleared when the selection *goes* and this
                // is a selection changing. Nothing ever hands a popup for a
                // route somebody planned, so the page is the route's own
                // figures, which is what it has to say about itself.
                if (given && given.composed && !suspended) { detailHtml = null; }
                selected = given;
                // A window belongs to the chain it was opened on. Carried over,
                // it would open the panel somewhere in the middle of whatever
                // the reader just clicked, at a scale chosen for something else.
                view.zoom = 1; view.at = 0; view.centre = null;
                // Open on a selection and folded away again the moment there is
                // none: a panel this wide takes a strip of the map with it, and
                // it may only do that while it has something to show there.
                open = selected !== null;
                // What the panel is showing, the way the graph itself arrives as
                // window.trailsGraph: the series it laid out and the figures it
                // was handed, so a browser check can read them rather than a
                // screenshot.
                window.trailsProfile = selected;
                // The chrome hides this panel while nothing is selected — a map
                // that opens showing only a map is the whole point of it — and
                // it cannot know that from the DOM, because a folded panel and
                // an empty one look the same from outside.
                if (window.trailsChrome && window.trailsChrome.selected) { window.trailsChrome.selected(selected); }
                // **A new thing to look at opens on the first of its pages** --
                // a reader who taps a second line while reading the first one's
                // table means *this line now*, not *the same page about
                // something else*.
                //
                // **A new thing, and not the same one handed over again.** A
                // planned route arrives here on every refresh, and plan mode
                // refreshes when the panel opens: resetting on each of those put
                // a reader who pressed *the points* on the curve instead, half a
                // frame later. Driven, that was one press reaching the list and
                // the list not being what came up.
                var showing = selected ? (selected.className || selected.label || 'composed') : null;
                if (showing !== showingWhat) { pageAt = 0; showingWhat = showing; }
                fold();
                describe();
                offered();
                render();
                placeArrow();
            }

            // The panel's second way in. A planned route has no chain and no
            // row in the figures table, so what arrives is the composed series
            // itself and the figures already read off it; the bands, the
            // crosshair and the reduction all apply unchanged.
            window.trailsProfilePanel = {
                steepestOf: steepestOf,
                // **A popup, taken in as a page rather than shown over the
                // map.** Every popup on this page used to dock into the chrome's
                // full-screen sheet, which put the answer to *what did I just
                // tap* over the thing that had been tapped. The chrome hands the
                // markup here instead, and it becomes the second page of the
                // panel -- beside the curve where there is one, and alone where
                // there is not, which is what a place gets.
                //: A place's page, shown and turned to. Pressing the panel's
                //: heading folds the pages away, which is what a reader who
                //: wanted the map back has just done -- and with them folded,
                //: tapping a place brought the panel back as a 46 px strip
                //: carrying its name and nothing else. Reported from the phone
                //: about the search's own mark: *I have no way of selecting the
                //: point I set again.*
                showDetails: function () {
                    if (!detailHtml) { return false; }
                    showPages(true);
                    for (var turn = 0; turn < pages.length; turn += 1) {
                        if (pages[turn].key === 'details') { goPage(turn); break; }
                    }
                    return true;
                },
                detail: function (label, html, isPoint) {
                    detailHtml = html || null;
                    // **While plan mode owns the map, a popup is a page and not
                    // a selection.** The panel is suspended then -- a click
                    // places a waypoint and must not also choose a line -- so
                    // what arrives is read where it stands and changes nothing
                    // about what the row says.
                    if (isPoint && !suspended) {
                        // **A place takes the panel over whole.** Tapping one
                        // while a line was chosen left the line's curve standing
                        // with the place's table beside it: two things in one
                        // panel, and the row naming the second while the first
                        // was drawn. The line is let go of on the map as well,
                        // or it stays lifted out of a tangle nobody is reading.
                        if (window.trailsHighlight) { window.trailsHighlight.clear(); }
                        present({detail: true, label: label, figure: null,
                                 shape: null, told: [], mid: null});
                        this.showDetails();
                        return;
                    }
                    if (label && !suspended && (!selected || !selected.label)) {
                        selected = selected || {detail: true, label: label, figure: null,
                                                shape: null, told: [], mid: null};
                        selected.label = selected.label || label;
                        open = true;
                        window.trailsProfile = selected;
                        if (window.trailsChrome && window.trailsChrome.selected) {
                            window.trailsChrome.selected(selected);
                        }
                    }
                    pageAt = 0;
                    fold();
                    // **A place's page shows itself.** Reported from the phone
                    // about the search's own mark, and true of every place: with
                    // the pages folded away -- which is what pressing the
                    // heading leaves behind, and what a reader who wanted the
                    // map back has just done -- tapping a place brought the
                    // panel back as a 46 px strip with the name in it and
                    // nothing else. Asking to read a place is asking.
                    //
                    // **While planning, for the same reason and one more**: the
                    // panel does not open by itself there, because on a narrow
                    // screen the map is what is being tapped -- and the page the
                    // reader asked for is not the plan's point list.
                    if (detailHtml && (isPoint || suspended)) { this.showDetails(); }
                    paintSummary();
                },
                // What the goal control is doing, pushed by the chrome the way
                // plan mode's summary is. The row at the foot draws itself from
                // this and asks the goal nothing.
                goal: function (summary) {
                    goalNow = summary && summary.at ? summary : null;
                    paintGoal();
                    paintChoices();
                    fold();
                },
                // What plan mode is doing, pushed by the chrome on every refresh
                // -- the same summary its bar used to draw itself from. A plan
                // with no points down is still a plan, and the row says so.
                planning: function (summary) {
                    planNow = summary && summary.on ? summary : null;
                    fold();
                    paintSummary();
                },
                // Which pages there are, which one is showing, and whether they
                // are showing at all: read by a check rather than measured off
                // the screen, the way the series and the view already are.
                pages: function () {
                    return {keys: pages.map(function (page) { return page.key; }),
                            at: pageAt, open: pagesOpen && pages.length > 0};
                },
                // Plan mode's list of points, lent rather than copied. It is
                // given back when planning stops, which is what keeps the plan
                // panel whole on a page that never opens this one.
                list: function (node, named) {
                    if (!node) { return false; }
                    // The name beside the way back rather than above it: it is
                    // still over the list, which is what it is the name of, and
                    // it costs one row instead of two.
                    if (named) {
                        named.style.flex = '1 1 auto';
                        named.style.minWidth = '0';
                        named.style.marginTop = '0';
                        undoRow.insertBefore(named, undoOne);
                    }
                    node.style.display = '';
                    node.style.maxHeight = 'none';
                    node.style.marginTop = '0';
                    pointsPage.appendChild(node);
                    return true;
                },
                page: function (key) {
                    if (key === undefined) { return pages[pageAt] ? pages[pageAt].key : null; }
                    if (key === false) { showPages(false); return null; }
                    if (key === true) { showPages(true); return pages[pageAt] ? pages[pageAt].key : null; }
                    for (var at = 0; at < pages.length; at += 1) {
                        if (pages[at].key === key) { goPage(at); return key; }
                    }
                    return null;
                },
                series: function (spec) {
                    present(spec === null ? null : {
                        composed: true, label: spec.label, figure: spec.figure, shape: spec.shape,
                        told: spec.told || [], saying: spec.saying, mid: null,
                        // Which of the points below the curve are where one
                        // stage hands over to the next. The panel draws every
                        // point the same; what a point *means* belongs to
                        // whatever composed the series.
                        stages: spec.stages || null,
                        // What each station is, where the series says: the
                        // way to a goal starts where the reader stands and ends
                        // at the goal, and neither is a numbered stop.
                        marks: spec.marks || null,
                        // **Whose composed route this is.** Two of them can be
                        // offered at once -- the plan and the way to a goal --
                        // and the row at the foot has to light the right chip.
                        // `composed` alone said only *not a trail*.
                        goal: !!spec.goal,
                        // What the panel cannot work out from a series alone and
                        // the file cannot be written without: where the reader
                        // put its points down, what each leg is made of, and
                        // whether the route has a hole in it. Absent, the series
                        // still draws and is not offered as a file.
                        plan: spec.plan || null});
                },
                suspend: function (taken) {
                    var was = suspended;
                    suspended = !!taken;
                    if (suspended) { present(null); return; }
                    // A place read while planning is read while planning: it
                    // outlives the plan's own refreshes, above, and not plan
                    // mode itself.
                    if (was) { detailHtml = null; fold(); }
                },
                // What a line is called, for whoever holds the class and not the
                // line: the chrome heads a docked popup with it, and it used to
                // read the map's own label for that. One table, one name.
                nameOf: function (className) { return (figures[className] || {}).name || null; },
                // Which scale the heights are drawn at, and the way to say
                // which: `'true'` for the ground's own and `'readable'` for the
                // lifted one. Read with no argument, and it answers with the
                // factor the last render used as well -- which is worked out
                // from the route and the panel's height and is therefore not a
                // thing a caller could know.
                scale: function (want) {
                    if (want !== undefined) { setLift(want !== 'true'); }
                    return {mode: lifted ? 'readable' : 'true', lift: liftNow};
                },
                // The two things a second consumer must not write for itself:
                // the walk that lays edges end to end, and the metre this page
                // measures distance with. A route composed by a second walk
                // would still look like a route.
                layEdges: layEdges,
                metresBetween: metresBetween,
                // And where the selection crosses a protected boundary, which
                // is a method rather than a field because asking costs 45 ms
                // over a 37 km route. The file is written from what this
                // returns, so a check reads the same list the file carries.
                crossings: crossings,
                // And which part of the chain is on the panel, at what scale,
                // and how much finer the readings would let it go. A window is
                // a thing to be read rather than screenshotted, the same as the
                // series and the figures above it; ``closest`` is 1 wherever the
                // panel is already drawn finer than the ground was measured,
                // which is 99 % of the chains here.
                view: function () {
                    return {zoom: view.zoom, at: view.at, centre: view.centre,
                            metresPerPixel: crosshair ? crosshair.mpp : null,
                            // What the height axis is drawn at, as a factor on
                            // the one above: the two are the same number at the
                            // ground's own scale and this is what the other
                            // scale is *for*, so anything working in metres up
                            // the box has to ask for it.
                            lift: crosshair ? crosshair.lift : 1,
                            shown: crosshair ? crosshair.shown : null,
                            closest: crosshair ? crosshair.closest : null};
                },
                // **Writing a route the panel is not showing.** A stage of a
                // plan is a range of one walk, and the file it becomes has to
                // come out of the same writer as the whole tour's: a second
                // writer would eventually disagree with the first about a route
                // it was handed the same way, which is the failure this project
                // keeps finding. So composing stays with the plan, which is the
                // only thing that knows where a stage begins, and writing stays
                // here, which is the only thing that knows what a file says.
                //
                // Its runs and its crossings are worked out from the shape it is
                // given and never sliced from the whole tour's — a stage that
                // inherited an `Enters` from ground it never covers would be a
                // file stating something about somewhere else.
                routeFile: function (figure, shape, told, plan, suffix) {
                    if (!EXPORT) { throw new Error('this panel was given nothing to write a file with'); }
                    var runs = runsOf(shape);
                    // **The title and the file name come apart for a stage.**
                    // What a device shows is the track's name, so a stage has to
                    // be named as one or four files read as four copies of the
                    // tour; what goes in the file name is the tour, with the
                    // stage as its suffix, or the stage's own name lands in it
                    // twice.
                    // **`stem` and never `name`.** The comment above says the
                    // stage's own name must not land in the file name twice, and
                    // falling back from `stem` to `name` is how it did: an
                    // unnamed tour leaves `stem` null, `name` is the title —
                    // which already ends in the stage — and the suffix goes on
                    // after it. Driven, that wrote
                    // `lomsdal-visten-Planned-route-in-Lomsdal-Visten-1-2-1-2.gpx`.
                    // `stem` is the file's name and `name` is the track's; the
                    // two are never each other's fallback.
                    var stem = (plan && plan.stem) || EXPORT.route.fileStem;
                    return {name: fileNameOf(stem + (suffix ? '-' + suffix : '')),
                            text: routeGpxOf(figure, shape, runs, plan, told || [],
                                             crossingsOf(shape, runs))};
                },
                garminFile: function (figure, shape, told, plan, suffix) {
                    if (!EXPORT) { throw new Error('this panel was given nothing to write a file with'); }
                    var runs = runsOf(shape);
                    var stem = (plan && plan.stem) || EXPORT.route.fileStem;
                    return {name: fileNameOf(stem + (suffix ? '-' + suffix : '') + '-garmin'),
                            text: garminGpxOf(figure, shape, runs, plan, told || [])};
                },
                // What a tour is called where nobody has called it anything, so
                // the plan can offer it as a placeholder and tell a name a
                // reader chose apart from the one every file carries by default.
                routeName: function () { return EXPORT ? EXPORT.route.name : null; },
                // What this map is called where a name has to outlive a build.
                // **Not the container's id**, which folium hashes afresh every
                // time the page is written: anything keyed on that would be
                // thrown away on every deploy, which is the one moment a reader
                // would least expect to lose something.
                prefix: function () { return EXPORT ? EXPORT.filePrefix : null; },
                // **Drawn again without anything having changed in the data.**
                // What the panel *says* can go stale on its own: the hint names
                // the gestures, and a pointer becoming coarse renames every one
                // of them. Nothing else would redraw it, because nothing about
                // the chain moved.
                repaint: function () { showLicences(); render(); },
                // Whether this panel was given what a file needs at all. A page
                // may have a profile and no export — the panel hides its own
                // button for exactly that — and anything else offering files off
                // the back of it has to ask rather than assume.
                writes: function () { return !!EXPORT; },
                // Handing a name and a body to the browser, which is one
                // place and not two: an anchor, or a share sheet where the
                // pointer is a finger and the browser offers one, because iOS
                // Safari drops the anchor's name and a phone saves through a
                // sheet anyway.
                save: saveFile,
                // Several files as one download. The plan says which files,
                // because it is the only thing that knows what a stage is.
                saveZip: function (files, plan) {
                    if (!EXPORT) { throw new Error('this panel was given nothing to write a file with'); }
                    // **The title and the file name come apart for a stage.**
                    // What a device shows is the track's name, so a stage has to
                    // be named as one or four files read as four copies of the
                    // tour; what goes in the file name is the tour, with the
                    // stage as its suffix, or the stage's own name lands in it
                    // twice.
                    // **`stem` and never `name`.** The comment above says the
                    // stage's own name must not land in the file name twice, and
                    // falling back from `stem` to `name` is how it did: an
                    // unnamed tour leaves `stem` null, `name` is the title —
                    // which already ends in the stage — and the suffix goes on
                    // after it. Driven, that wrote
                    // `lomsdal-visten-Planned-route-in-Lomsdal-Visten-1-2-1-2.gpx`.
                    // `stem` is the file's name and `name` is the track's; the
                    // two are never each other's fallback.
                    var stem = (plan && plan.stem) || EXPORT.route.fileStem;
                    return zipOf(files).then(function (blob) { saveFile(fileNameOf(stem, '.zip'), blob); });
                }
            };

            function show(className, label) {
                // **Whatever is chosen here, the way to a goal is not it.** The
                // goal control keeps its own note of whether this panel is
                // drawing its route, and a stale yes would let its next refresh
                // take the panel back from the line the reader just tapped.
                if (window.trailsGoal) { window.trailsGoal.letGo(); }
                var chosen = className === null ? null : {className: className, figure: figures[className], label: label, shape: null, mid: null};
                if (chosen && !chosen.figure) { chosen = null; }
                present(chosen);
                if (!selected) { return; }
                if (!window.trailsGraph) {
                    selected.missing = true;
                    say('There is no routing graph in this page, so there is no profile to draw.');
                    offered();
                    return;
                }
                var wanted = selected.className;
                window.trailsGraph.ready.then(function (graph) {
                    // The reader may well have clicked something else while a
                    // megabyte of arithmetic was going on.
                    if (!selected || selected.className !== wanted) { return; }
                    var index = graph.chainOf[selected.figure.id];
                    if (index === undefined) {
                        selected.missing = true;
                        say('This line is not in the routing graph.');
                        offered();
                        return;
                    }
                    selected.shape = scale(compose(graph, index), selected.figure.length);
                    selected.mid = midpoint(selected.shape);
                    describe();
                    offered();
                    render();
                    placeArrow();
                // Two handlers rather than a .catch: a catch would also swallow
                // anything thrown while drawing and report it as a graph that
                // never arrived, which is the wrong cause and sends the next
                // reader looking in the wrong place. A drawing fault belongs in
                // the console, loudly.
                }, function () {
                    if (selected && selected.className === wanted) { selected.missing = true; }
                    say('The routing graph did not arrive, so there is no profile to draw.');
                    offered();
                });
            }

            groups.forEach(function (group) {
                group.eachLayer(function (layer) {
                    if (!layer.setStyle || !layer.options.className) { return; }
                    layer.on('click', function (event) {
                        if (suspended) { return; }
                        var className = layer.options.className;
                        // Where the tap landed decides what else it could have
                        // meant, so the list is taken before anything is shown.
                        // A click fired without one -- a chip pressing the line
                        // it stands for -- leaves the list alone, which is what
                        // keeps the row still under a reader's finger.
                        if (event && event.latlng) { gather(event.latlng); }
                        // **A planned route takes the tap wherever it runs.**
                        // It is the one line on this map the reader made, and
                        // it lies on the others by construction -- it was routed
                        // along them -- so a tap in reach of it that chose the
                        // trail underneath answered a question nobody asked.
                        // The row of choices still holds those trails, one press
                        // away, and the route stands last in it.
                        var mine = event && event.latlng ? planChoice() : null;
                        if (mine) { takeChoice(mine); return; }
                        show(selected && selected.className === className ? null : className, labelOf(layer, className));
                    });
                });
            });
            // Leaflet only fires a map click where the click hit no layer, which
            // is what clears the selection on empty terrain — the same rule the
            // click-highlight follows, so the two cannot drift apart.
            //
            // **Except where the planned route runs there.** A leg over
            // trackless ground has no line under it to carry the tap, and the
            // route's own takes none, so a tap on the route out there used to be
            // a tap on nothing and put the panel away — with the route drawn
            // under the finger that did it.
            map.on('click', function (event) {
                if (suspended) { return; }
                if (event && event.latlng) {
                    gather(event.latlng);
                    var mine = planChoice();
                    if (mine) { takeChoice(mine); return; }
                }
                show(null);
            });
            // **The machine can turn dark under a drawing that is already on
            // the screen.** Everything painted through CSS follows on its own;
            // the curve does not, because it is drawn with attributes read at
            // stroke time.
            if (window.matchMedia) {
                var scheme = window.matchMedia('(prefers-color-scheme: dark)');
                if (scheme.addEventListener) {
                    scheme.addEventListener('change', function () { render(); });
                }
            }
            // **And so can the reader, which the query above cannot see.** A
            // theme picked in the menu stamps the root and never touches
            // `prefers-color-scheme`, so on this panel -- the only one that
            // paints with attributes rather than CSS -- the switch would have
            // moved every other surface and left the curve behind in the old
            // set. Both ways in end at the same redraw.
            document.addEventListener('trails:theme', function () { render(); });

            // A panel this wide is sized against the map, so a resized window
            // has to size it again before anything is drawn into it.
            map.on('resize', function () {
                if (!readerSized) { chartHeight = defaultChartHeight(); }
                showLicences();
                fold(); render(); placeArrow();
            });

            if (!readerSized) { chartHeight = defaultChartHeight(); }
            showLicences();
            fold();
            describe();
            offered();
            render();
        })();

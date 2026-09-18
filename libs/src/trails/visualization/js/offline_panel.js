            (function () {
                var map = {{ this._parent.get_name() }};

                // Where a deliberate download goes. The worker reads this one
                // first and never trims it; `trails-tiles` beside it is what
                // panning happened to leave behind and is capped at 500.
                var TERRAIN = '{{ this.cache }}-terrain';
                var TILES = '{{ this.cache }}-tiles';
                var KEY = '{{ this.cache }}-offline';
                // The finest tile zoom in the provider's tree.
                var TOP = {{ this.top }};
                // The coarsest zoom a reader may *pick*.
                var FLOOR = 14;
                // **And the floor of the pyramid, which is a different number.**
                // Whatever is kept is carried down to z11 as well, because a map
                // that cannot be zoomed out of is not a map anybody navigates
                // with, and the coarse levels are almost free: the whole box at
                // z11 is 168 tiles against 97,000 at z16.
                var BOTTOM = 11;
                // The whole box is always kept below the scope's fine ground.
                var OVERVIEW = 8;
                // Where the whole map stops being a download and starts being an
                // archive -- and with it the budget every other scope is held to.
                // Both trees are offered to z17 (see `Provider.cap`).
                var CAP_ZOOM = {{ this.cap }};
                // Mean pack bytes at each parent level, measured from index.json.
                var PACK_WEIGHT = {{ this.pack_weight_json }};
                // Heights use the same pack iterator as the other layers. Their
                // z10 overview packs also carry z13, the level the page reads.
                var HEIGHTS = {{ this.heights_json }};
                // The relief overlay's tiles, kept with the map's. Null where
                // no height model has been cut over the map's ground.
                var SHADE = {{ this.shade_json }};
                // And the slope classes' tiles, kept with them, on the same
                // condition.
                var SLOPE = {{ this.slope_json }};
                // And the vegetation and forest tiles' (§6.11), on the same
                // condition, kept with the rest whether or not they are on.
                var VEGETATION = {{ this.vegetation_json }};
                var FOREST = {{ this.forest_json }};
                // Every layer ends at this tree box. Both scope and margin are clipped.
                var EXTENT = {{ this.extent_json }};

                // **Four scopes, and only one of them follows the paths.** In
                // this park one walks off them, so a band along everything drawn
                // -- which is what the third scope used to be -- hands a white
                // tile to anybody who leaves one. `pad` is the margin in tiles
                // laid on every level, which is why the band is about 2 km wide
                // at z14 and 250 m at z18: coarse ground far out and fine ground
                // underfoot, which is the right shape rather than a compromise.
                var SCOPES = [
                    {key: 'all', label: 'The whole map', pad: 1, ceiling: CAP_ZOOM,
                     hint: 'Every pack in the map’s tree box, including the ground no path crosses.'},
                    {key: 'band', label: 'Along the route', pad: 2, ceiling: TOP,
                     hint: 'A band along the line, wider at the coarse zooms and narrow underfoot.'},
                    {key: 'rect', label: 'A box round it', pad: 1, ceiling: TOP,
                     hint: 'The smallest rectangle round the line, turned so it lies close, with room to leave it by.'},
                    {key: 'draw', label: 'Draw it myself', pad: 1, ceiling: TOP,
                     hint: 'Tap the corners on the map. Three of them make an area.'}
                ];

                var scope = 'band', zoom = 16, chooser = false, margin = 1000;
                var drawn = [], picked = -1, handles = [];
                var counted = null, working = null, snapshot = null, lastRun = null;
                var holder = null, said = {};

                function scopeOf(which) {
                    return SCOPES.filter(function (each) { return each.key === which; })[0] || SCOPES[0];
                }

                // ---- tiles ---------------------------------------------------

                function fracTile(lat, lon, z) {
                    var n = Math.pow(2, z);
                    var s = Math.sin(lat * Math.PI / 180);
                    return {x: (lon + 180) / 360 * n,
                            y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n};
                }

                // The way back, which the preview needs: a screen tile knows its
                // own coordinates and has to ask what is kept under them.
                function lonAt(x, z) { return x / Math.pow(2, z) * 360 - 180; }

                function latAt(y, z) {
                    var n = Math.PI - 2 * Math.PI * y / Math.pow(2, z);
                    return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
                }

                // **Walked, not sampled at the ends.** The drawn geometry is
                // simplified at 8 m, so a straight run across a plateau can be
                // hundreds of metres between two vertices -- and a tile at z18
                // is 63 m. Taking only the endpoints would leave holes along
                // every straight, which is exactly the ground somebody walks
                // fastest and looks at least.
                function walk(a, b, z, into) {
                    var from = fracTile(a[0], a[1], z), to = fracTile(b[0], b[1], z);
                    var dx = to.x - from.x, dy = to.y - from.y;
                    var steps = Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) * 2);
                    var i;
                    if (!isFinite(steps) || steps < 1) { steps = 1; }
                    for (i = 0; i <= steps; i += 1) {
                        into(Math.floor(from.x + dx * i / steps), Math.floor(from.y + dy * i / steps));
                    }
                }

                // **One number a tile, in a `Set`.** This was a string key
                // `"x,y"` into an object whose value was an `[x, y]` array: three
                // allocations a tile, about 150 bytes, and the whole map at z16
                // is 131,033 tiles. `Set.size` also replaces
                // `Object.keys(set).length`, which built a 131,033-element array
                // to ask how many there were -- on every repaint of the zoom row.
                //
                // `SPAN` is 2^18, the finest level Kartverket answers, so one
                // constant packs every level and the arithmetic is exact: the
                // largest value here is 2^36, far inside what a double holds
                // whole.
                var SPAN = 262144;
                function key(x, y) { return x * SPAN + y; }
                function keyX(v) { return Math.floor(v / SPAN); }
                function keyY(v) { return v - Math.floor(v / SPAN) * SPAN; }

                function bandAt(line, z) {
                    var out = new Set(), i;
                    for (i = 0; i + 1 < line.length; i += 1) {
                        walk(line[i], line[i + 1], z, function (x, y) { out.add(key(x, y)); });
                    }
                    return out;
                }

                // A filled rectangle in tile space, which is what a north-up box
                // is. Not a band round its edge and not a walk along anything:
                // every tile between the corners, which is the whole point of
                // this scope.
                function boxAt(box, z) {
                    var a = fracTile(box.n, box.w, z), b = fracTile(box.s, box.e, z);
                    var out = new Set(), x, y;
                    for (x = Math.floor(a.x); x <= Math.floor(b.x); x += 1) {
                        for (y = Math.floor(a.y); y <= Math.floor(b.y); y += 1) { out.add(key(x, y)); }
                    }
                    return out;
                }

                function inside(lat, lon, ring) {
                    var hit = false, i, j;
                    for (i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
                        var yi = ring[i][0], xi = ring[i][1], yj = ring[j][0], xj = ring[j][1];
                        if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) { hit = !hit; }
                    }
                    return hit;
                }

                // Any ring, tested tile by tile over its own bounding box. A tile
                // is in if its centre or any corner is: the margin below covers
                // the sliver that misses at the edge, and an exact clip would be
                // a lot of code for tiles that are kept either way.
                function ringAt(ring, z) {
                    var n = -90, s = 90, e = -180, w = 180, out = new Set(), i, x, y;
                    for (i = 0; i < ring.length; i += 1) {
                        n = Math.max(n, ring[i][0]); s = Math.min(s, ring[i][0]);
                        e = Math.max(e, ring[i][1]); w = Math.min(w, ring[i][1]);
                    }
                    var a = fracTile(Math.min(n, EXTENT.n), Math.max(w, EXTENT.w), z);
                    var b = fracTile(Math.max(s, EXTENT.s), Math.min(e, EXTENT.e), z);
                    for (x = Math.floor(a.x); x <= Math.floor(b.x); x += 1) {
                        for (y = Math.floor(a.y); y <= Math.floor(b.y); y += 1) {
                            var probes = [[x + 0.5, y + 0.5], [x, y], [x + 1, y], [x, y + 1], [x + 1, y + 1]], p;
                            for (p = 0; p < probes.length; p += 1) {
                                if (inside(latAt(probes[p][1], z), lonAt(probes[p][0], z), ring)) {
                                    out.add(key(x, y));
                                    break;
                                }
                            }
                        }
                    }
                    return out;
                }

                // ---- the turned rectangle -------------------------------------
                // **Convex hull, then rotating calipers.** The minimum-area
                // enclosing rectangle always has one side flush with a hull edge,
                // so trying each edge in turn is the whole algorithm. Worked in
                // local metres about the line's own centre, because an angle in
                // degrees of latitude and longitude is not an angle on the
                // ground -- at 65 degrees north a degree of longitude is 46 km
                // and a degree of latitude 111.

                function convex(points) {
                    var sorted = points.slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
                    var cross = function (o, a, b) {
                        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
                    };
                    var lower = [], upper = [], i;
                    for (i = 0; i < sorted.length; i += 1) {
                        while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], sorted[i]) <= 0) { lower.pop(); }
                        lower.push(sorted[i]);
                    }
                    for (i = sorted.length - 1; i >= 0; i -= 1) {
                        while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], sorted[i]) <= 0) { upper.pop(); }
                        upper.push(sorted[i]);
                    }
                    return lower.slice(0, -1).concat(upper.slice(0, -1));
                }

                // The rectangle as four lat/lon corners, grown by `by` metres on
                // every side.
                function rectRing(points, by) {
                    if (!points || points.length < 3) { return null; }
                    var mid = points.reduce(function (sum, at) { return [sum[0] + at[0], sum[1] + at[1]]; }, [0, 0]);
                    mid = [mid[0] / points.length, mid[1] / points.length];
                    var kx = 111320 * Math.cos(mid[0] * Math.PI / 180), ky = 111320;
                    var hull = convex(points.map(function (at) {
                        return [(at[1] - mid[1]) * kx, (at[0] - mid[0]) * ky];
                    }));
                    if (hull.length < 3) { return null; }
                    var best = null, i, j;
                    for (i = 0; i < hull.length; i += 1) {
                        var a = hull[i], b = hull[(i + 1) % hull.length];
                        var ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
                        var c = Math.cos(-ang), s = Math.sin(-ang);
                        var lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
                        for (j = 0; j < hull.length; j += 1) {
                            var u = hull[j][0] * c - hull[j][1] * s, v = hull[j][0] * s + hull[j][1] * c;
                            lo[0] = Math.min(lo[0], u); hi[0] = Math.max(hi[0], u);
                            lo[1] = Math.min(lo[1], v); hi[1] = Math.max(hi[1], v);
                        }
                        var area = (hi[0] - lo[0]) * (hi[1] - lo[1]);
                        if (!best || area < best.area) { best = {area: area, ang: ang, lo: lo, hi: hi}; }
                    }
                    var cs = Math.cos(best.ang), sn = Math.sin(best.ang), out = [];
                    var low = [best.lo[0] - by, best.lo[1] - by], high = [best.hi[0] + by, best.hi[1] + by];
                    [[low[0], low[1]], [high[0], low[1]], [high[0], high[1]], [low[0], high[1]]].forEach(function (at) {
                        var x = at[0] * cs - at[1] * sn, y = at[0] * sn + at[1] * cs;
                        out.push([mid[0] + y / ky, mid[1] + x / kx]);
                    });
                    return out;
                }

                // ---- what the shapes are drawn round ---------------------------

                // The route as the plan panel composes it, which is the same
                // geometry the exported file is written from.
                function routeLine() {
                    if (!window.trailsPlan || !window.trailsPlan.geometry) { return []; }
                    var shape = window.trailsPlan.geometry(), out = [], i;
                    for (i = 0; i < shape.lon.length; i += 1) {
                        if (shape.lon[i] === null || shape.lat[i] === null) { continue; }
                        out.push([shape.lat[i], shape.lon[i]]);
                    }
                    return out.length > 1 ? [out] : [];
                }

                // **What the band and the box are drawn round, and it is said
                // out loud on the panel.** A planned route first, because a
                // reader who has planned one is keeping ground for that; the
                // track they have selected otherwise. Neither, and both scopes
                // are simply not offered -- the same rule the route scope has
                // always followed, rather than a button that answers nothing.
                function source() {
                    var planned = routeLine();
                    if (planned.length) { return {line: planned[0], from: 'the route you planned'}; }
                    var showing = window.trailsProfile, shape = showing && showing.shape;
                    if (!shape || !shape.lat || !shape.lon) { return null; }
                    var out = [], i;
                    for (i = 0; i < shape.lon.length; i += 1) {
                        if (shape.lon[i] === null || shape.lat[i] === null) { continue; }
                        out.push([shape.lat[i], shape.lon[i]]);
                    }
                    return out.length > 1 ? {line: out, from: 'the track you have selected'} : null;
                }

                // Every chain drawn on this map. `eachLayer` is flat -- a group
                // hands each of its children to the map as well as holding it --
                // so this must not recurse or every line is counted twice.
                function ringsOf(value, into) {
                    if (!value || !value.length) { return; }
                    if (value[0].lat !== undefined) { into(value); return; }
                    value.forEach(function (each) { ringsOf(each, into); });
                }

                function drawnLines() {
                    var out = [];
                    map.eachLayer(function (layer) {
                        if (!layer.getLatLngs || layer.getRadius) { return; }
                        // The outline this panel draws is a layer on this map
                        // like any other, and counting it would let the selection
                        // move the box the selection is measured against.
                        if (layer.options && layer.options.trailsOffline) { return; }
                        // **Down to whatever depth the geometry had.** A
                        // polyline answers a list of points, a polygon a list of
                        // rings and a multipolygon a list of those; taking the
                        // first level and hoping puts `undefined` into the
                        // arithmetic and every tile it touches comes out NaN.
                        ringsOf(layer.getLatLngs(), function (ring) {
                            var line = [], i;
                            for (i = 0; i < ring.length; i += 1) { line.push([ring[i].lat, ring[i].lng]); }
                            if (line.length > 1) { out.push(line); }
                        });
                    });
                    return out;
                }

                // **The box this map draws paths in, asked of the map itself.**
                // Written down here it would be a number that goes stale the
                // first time the sources move; read off the layers it is
                // whatever this build actually drew -- 65.175 to 65.921 N and
                // 12.094 to 13.694 E as this one stands, about 74 by 83 km.
                // Held after the first ask, because it walks every line on the
                // page and the answer cannot change while the page is open.
                var box = null;
                function mapBox() {
                    if (box) { return box; }
                    var n = -90, s = 90, e = -180, w = 180, any = false;
                    drawnLines().forEach(function (line) {
                        line.forEach(function (at) {
                            any = true;
                            n = Math.max(n, at[0]); s = Math.min(s, at[0]);
                            e = Math.max(e, at[1]); w = Math.min(w, at[1]);
                        });
                    });
                    // A map with nothing drawn on it is not one this panel has
                    // an opinion about; the view is the only honest answer, and
                    // it is not remembered because it moves.
                    if (!any) {
                        var seen = map.getBounds();
                        return {n: seen.getNorth(), s: seen.getSouth(), e: seen.getEast(), w: seen.getWest()};
                    }
                    box = {n: n, s: s, e: e, w: w};
                    return box;
                }

                // **Kept until the drawing changes, and not a moment longer.**
                // Walking 11,303 rings for a bounding box on every repaint is
                // what the memo above is for, but the legend can take a layer off
                // the map -- and if the outermost line was on it, the box the
                // reader is being offered is no longer the box this map draws.
                // The old band scope had no such gap because it re-read the
                // layers every time; measured then, switching five layers off
                // moved it from 5,561 tiles to 5,326.
                map.on('layeradd layerremove', function () { box = null; });

                function ringFor(which) {
                    if (which === 'rect') {
                        var from = source();
                        return from ? rectRing(from.line, margin) : null;
                    }
                    if (which === 'draw') { return drawn.length >= 3 ? drawn.slice() : null; }
                    return null;
                }

                // The one function that says what a scope *is*, handed to
                // `levelsFor` to be asked once at the finest zoom.
                function coreOf(which) {
                    if (which === 'all') { return null; }
                    return function (z) {
                        if (which === 'band') {
                            var from = source();
                            return from ? bandAt(from.line, z) : new Set();
                        }
                        var ring = ringFor(which);
                        return ring ? ringAt(ring, z) : new Set();
                    };
                }

                // **The margin ends where the tiles do.** A ring laid past the
                // source's extent is a ring of tiles that are not there: against
                // our own tree, cut exactly to its box, *the whole map* asked
                // for the box plus one tile round it, met twelve 404s in a row
                // in its first sixty tiles and gave up on a connection that was
                // fine. Both the core and its margin stop at the tree box.
                function edgeAt(z) {
                    var a = fracTile(EXTENT.n, EXTENT.w, z), b = fracTile(EXTENT.s, EXTENT.e, z);
                    return {x0: Math.floor(a.x), y0: Math.floor(a.y), x1: Math.floor(b.x), y1: Math.floor(b.y)};
                }

                function padded(core, pad, z) {
                    if (!pad) { return core; }
                    var out = new Set(), edge = edgeAt(z);
                    core.forEach(function (v) {
                        var cx = keyX(v), cy = keyY(v), dx, dy;
                        for (dx = -pad; dx <= pad; dx += 1) {
                            for (dy = -pad; dy <= pad; dy += 1) {
                                var x = cx + dx, y = cy + dy;
                                if (x < 0 || y < 0) { continue; }
                                if (x < edge.x0 || x > edge.x1 || y < edge.y0 || y > edge.y1) { continue; }
                                out.add(key(x, y));
                            }
                        }
                    });
                    return out;
                }

                // Four rectangles, not a tile list. The scope may also reach
                // outside the box at z11; keep that ground once, and price the
                // overlap once. Each iterator holds only its current position.
                function overviewAt(z, core) {
                    var box = EXTENT;
                    var a = fracTile(box.n, box.w, z), b = fracTile(box.s, box.e, z);
                    var x0 = Math.floor(a.x), y0 = Math.floor(a.y);
                    var x1 = Math.floor(b.x), y1 = Math.floor(b.y);
                    function inside(v) {
                        return keyX(v) >= x0 && keyX(v) <= x1 && keyY(v) >= y0 && keyY(v) <= y1;
                    }
                    var size = (x1 - x0 + 1) * (y1 - y0 + 1);
                    if (core) { core.forEach(function (v) { if (!inside(v)) { size += 1; } }); }
                    return {
                        size: size,
                        has: function (v) { return inside(v) || !!(core && core.has(v)); },
                        values: function () {
                            var x = x0, y = y0, it = core ? core.values() : null;
                            return {next: function () {
                                if (it) {
                                    var step = it.next();
                                    if (!step.done) { return step; }
                                    it = null;
                                }
                                while (x <= x1) {
                                    var v = key(x, y);
                                    y += 1;
                                    if (y > y1) { y = y0; x += 1; }
                                    if (!core || !core.has(v)) { return {value: v, done: false}; }
                                }
                                return {done: true};
                            }};
                        }
                    };
                }

                function overviewCost() {
                    var levels = {}, z;
                    for (z = OVERVIEW; z <= BOTTOM; z += 1) { levels[z] = overviewAt(z); }
                    return weigh(levels);
                }

                // **Computed once at the finest zoom and halved down.** A tile
                // at z-1 is the tile at z with both coordinates shifted right,
                // so one pass answers every level below it as well; walking the
                // whole network five times over would be five times the work for
                // a set that is already implied.
                //
                // **The margin is laid on every level and the unpadded set is
                // what goes down.** Padding first and halving the padded set
                // compounds the margin all the way to z11, where the box came
                // out several tiles wider on each side than the ground it was
                // asked for -- which at z11 is 8 km a tile.
                function levelsFor(coreAt, top, pad) {
                    var out = {}, z;
                    if (!coreAt) {
                        for (z = OVERVIEW; z <= top; z += 1) { out[z] = overviewAt(z); }
                        return out;
                    }
                    var below = coreAt(top);
                    out[top] = padded(below, pad, top);
                    for (z = top - 1; z >= BOTTOM; z -= 1) {
                        var up = new Set();
                        below.forEach(function (v) {
                            up.add(key(keyX(v) >> 1, keyY(v) >> 1));
                        });
                        out[z] = padded(up, pad, z);
                        below = up;
                    }
                    for (z = OVERVIEW; z <= BOTTOM; z += 1) { out[z] = overviewAt(z, out[z]); }
                    return out;
                }

                // Mirrored exactly in worker.js, with a test over every layer's
                // levels. Zooms remain tile zooms; addresses use the parent level.
                function packLevel(top, z) {
                    return Math.max(0, top - 3 - 4 * Math.floor((top - z) / 4));
                }

                function packPrefix(prefix) {
                    if (!prefix) { return null; }
                    var url = new URL(prefix, location.href);
                    url.pathname = '/packs' + url.pathname;
                    return url.href;
                }

                function packLayers() {
                    return [{kind: 'map', top: TOP, weight: PACK_WEIGHT, prefix: TILE_PREFIX}].concat(
                        [[HEIGHTS, 'height'], [SHADE, 'shade'], [SLOPE, 'slope'],
                         [VEGETATION, 'vegetation'], [FOREST, 'forest']].filter(function (pair) { return pair[0]; })
                        .map(function (pair) {
                            var layer = pair[0];
                            return {kind: pair[1], top: layer.top || layer.zoom,
                                    weight: layer.pack_weight, prefix: layer.url.split('{z}')[0]};
                        }));
                }

                // Scan parents, testing their children against the selection.
                // Only the current rectangle position survives a next(): no set
                // of parents, addresses or requests grows with the download.
                function parentsAt(levels, top, level) {
                    var edge = edgeAt(level);
                    var first = Math.max(OVERVIEW, level), last = Math.min(top, level + 3);
                    function wanted(x, y) {
                        for (var z = first; z <= last; z += 1) {
                            if (!levels[z]) { continue; }
                            var side = Math.pow(2, z - level);
                            for (var dx = 0; dx < side; dx += 1) {
                                for (var dy = 0; dy < side; dy += 1) {
                                    if (levels[z].has(key(x * side + dx, y * side + dy))) { return true; }
                                }
                            }
                        }
                        return false;
                    }
                    var x = edge.x0, y = edge.y0;
                    return {next: function () {
                        while (x <= edge.x1) {
                            var cx = x, cy = y;
                            y += 1;
                            if (y > edge.y1) { y = edge.y0; x += 1; }
                            if (wanted(cx, cy)) { return {x: cx, y: cy}; }
                        }
                        return null;
                    }};
                }

                function packWalk(levels) {
                    var layers = packLayers(), at = 0, z = OVERVIEW, parents = null, level;
                    return {next: function () {
                        while (at < layers.length) {
                            var layer = layers[at];
                            if (z > layer.top) { at += 1; z = OVERVIEW; continue; }
                            if (!parents) {
                                level = packLevel(layer.top, z);
                                parents = parentsAt(levels, layer.top, level);
                            }
                            var parent = parents.next();
                            if (parent) {
                                return {url: packPrefix(layer.prefix) + level + '/' + parent.x + '/' + parent.y + '.pmtiles',
                                        z: level, kind: layer.kind, bytes: layer.weight[level]};
                            }
                            parents = null;
                            z = level + 4;
                        }
                        return null;
                    }};
                }

                function weigh(levels) {
                    var walk = packWalk(levels), next, packs = 0, bytes = 0;
                    while ((next = walk.next())) { packs += 1; bytes += next.bytes; }
                    return {packs: packs, bytes: bytes};
                }

                // **Buffered, because the zoom row prices every level it draws.**
                // Without this a repaint recomputes z17 and z18 for a turned
                // rectangle -- a few hundred thousand point-in-polygon tests --
                // on every tap of anything on the panel.
                //
                // **And the key carries every corner, not their number and the
                // last one.** Dragging a handle moves a point in the middle and
                // leaves both of those alone; the panel would answer out of the
                // buffer with the area the shape used to have.
                function sig(which, level) {
                    if (which === 'rect') { return 'rect|' + level + '|' + margin; }
                    if (which === 'draw') {
                        return 'draw|' + level + '|' + drawn.map(function (at) {
                            return at[0].toFixed(5) + ',' + at[1].toFixed(5);
                        }).join(';');
                    }
                    return which + '|' + level;
                }

                // The buffer holds figures and never tile sets: the zoom row
                // prices every level it offers, and holding the whole map at z14,
                // z15 and z16 at once is 173,000 tiles of arrays kept alive for
                // two lines of text.
                var memo = {};
                function cost(which, level) {
                    var at = sig(which, level);
                    if (!memo[at]) {
                        memo[at] = weigh(levelsFor(coreOf(which), level, scopeOf(which).pad));
                    }
                    return memo[at];
                }

                // **The budget is measured, not written down.** It is what the
                // whole map costs at z17, using measured pack weights,
                // and every other scope is held to it, so no
                // choice on this panel can quietly cost more than the one that
                // keeps everything.
                var cap = null;
                function budget() {
                    if (cap === null) { cap = cost('all', CAP_ZOOM).bytes; }
                    return cap;
                }

                // The one selection that is drawn and downloaded. Its tiles are
                // kept, unlike the buffer's, because the preview and the download
                // both read them.
                var chosen = null;
                function recount() {
                    // **The same refusal the buttons make, held here too.**
                    // Switching scope keeps the zoom, and a zoom that was
                    // affordable for a band along a line need not be for an area
                    // drawn round a county.
                    while (zoom > FLOOR && cost(scope, zoom).bytes > budget()) { zoom -= 1; }
                    var at = sig(scope, zoom);
                    if (chosen && chosen.at === at) { return chosen; }
                    var levels = levelsFor(coreOf(scope), zoom, scopeOf(scope).pad);
                    var sum = weigh(levels);
                    memo[at] = sum;
                    chosen = {at: at, levels: levels, top: zoom, scope: scope, zoom: zoom,
                              packs: sum.packs, bytes: sum.bytes, overview: overviewCost()};
                    return chosen;
                }

                // The base layer that is actually showing. Only one is fetched:
                // topo and grayscale share a host, and keeping both would
                // silently double every figure on this panel.
                function baseName() {
                    var layer = base();
                    return layer && layer.options && layer.options.name ? layer.options.name : 'current';
                }

                function base() {
                    var found = null;
                    map.eachLayer(function (layer) {
                        if (found || !layer.getTileUrl || !layer._url) { return; }
                        // Not the relief overlay, which is tiles like the sheet
                        // and is not the sheet. Switching the base map off and
                        // on again re-adds it behind this one in the map's own
                        // order, so "the first tile layer" is not enough.
                        if (layer.options && (layer.options.trailsShade || layer.options.trailsSlope
                                || layer.options.trailsVegetation || layer.options.trailsForest)) { return; }
                        found = layer;
                    });
                    return found;
                }

                // The sheet's address without the token `restamp` may have put
                // on it. Everything that goes into a cache is keyed on this, so
                // moving the token never orphans a tile.
                function plainUrl(layer) {
                    if (layer.options.trailsUrl === undefined) {
                        layer.options.trailsUrl = layer._url.split('?')[0];
                    }
                    return layer.options.trailsUrl;
                }

                function walker(picked) {
                    picked = picked || recount();
                    var layer = base(), walk = packWalk(picked.levels);
                    return {total: layer ? picked.packs : 0, bytes: picked.bytes,
                            next: function () { return layer ? walk.next() : null; }};
                }

                // ---- what it would keep, drawn on the map ----------------------

                // The accent this page is painted in, read rather than repeated,
                // so the preview follows the theme the reader picked instead of
                // being a blue that is right in one of the two.
                function accent(alpha) {
                    var said = '';
                    if (window.getComputedStyle) {
                        said = (getComputedStyle(document.documentElement).getPropertyValue('--trails-accent') || '').trim();
                    }
                    if (!/^#[0-9a-fA-F]{6}$/.test(said)) { said = '#7fb0f0'; }
                    if (alpha === undefined) { return said; }
                    return 'rgba(' + parseInt(said.slice(1, 3), 16) + ',' + parseInt(said.slice(3, 5), 16) +
                        ',' + parseInt(said.slice(5, 7), 16) + ',' + alpha + ')';
                }

                // Between the terrain and the paths: the selection tints the
                // ground it would keep, and the lines somebody is choosing it
                // for stay on top of the tint rather than under it.
                if (!map.getPane('trailsOffline')) {
                    map.createPane('trailsOffline');
                    map.getPane('trailsOffline').style.zIndex = 350;
                    map.getPane('trailsOffline').style.pointerEvents = 'none';
                }

                // **A grid layer and not 131,000 rectangles.** Leaflet only ever
                // creates the tiles in view, so the preview costs what the screen
                // costs however large the selection is -- and it is exact,
                // because it asks the same set the download would use rather than
                // an outline standing in for it.
                var Preview = L.GridLayer.extend({
                    // **A canvas, because a screen tile is not a kept tile.**
                    // Two ways of drawing this are wrong and both were built:
                    // testing only the screen tile's centre against the selection
                    // paints nothing at all once you are zoomed out, because the
                    // centre almost never lands in a kept tile; and filling the
                    // whole screen tile whenever it holds *any* kept one turns a
                    // valley into a county -- reported from a phone, where a
                    // hand-drawn area a few kilometres across was painted as a
                    // block a hundred kilometres wide.
                    //
                    // What is right is drawing the kept tiles as sub-rectangles
                    // *inside* the screen tile. Same information, no lie, and one
                    // canvas per tile on screen.
                    createTile: function (coords) {
                        var side = 256;
                        var canvas = document.createElement('canvas');
                        canvas.width = side;
                        canvas.height = side;
                        if (!chooser || !chosen) { return canvas; }
                        var z = Math.min(chosen.top, Math.max(OVERVIEW, coords.z));
                        var set = chosen.levels[z];
                        if (!set) { return canvas; }
                        var ink = canvas.getContext('2d');
                        ink.fillStyle = accent(0.42);
                        var step = Math.pow(2, z - coords.z);
                        if (step <= 1) {
                            // The screen is the finer of the two: this tile is
                            // inside a kept one or it is not.
                            var at = fracTile(latAt(coords.y + 0.5, coords.z), lonAt(coords.x + 0.5, coords.z), z);
                            if (set.has(key(Math.floor(at.x), Math.floor(at.y)))) { ink.fillRect(0, 0, side, side); }
                            return canvas;
                        }
                        // Coarser screen: this tile covers step by step kept
                        // tiles, each of them side/step pixels across. Past 256
                        // they are under a pixel and the fill would be invisible
                        // anyway, so it draws nothing rather than rounding a
                        // speck up to the whole tile.
                        if (step > side) { return canvas; }
                        var px = side / step, x0 = coords.x * step, y0 = coords.y * step, i, j;
                        for (i = 0; i < step; i += 1) {
                            for (j = 0; j < step; j += 1) {
                                if (set.has(key(x0 + i, y0 + j))) { ink.fillRect(i * px, j * px, px, px); }
                            }
                        }
                        return canvas;
                    }
                });

                var preview = null, outline = null;

                function paint() {
                    if (outline) { map.removeLayer(outline); outline = null; }
                    if (!chooser) {
                        if (preview && map.hasLayer(preview)) { map.removeLayer(preview); }
                        return;
                    }
                    if (!preview) { preview = new Preview({pane: 'trailsOffline'}); }
                    if (!map.hasLayer(preview)) { preview.addTo(map); }
                    // `trailsOffline` on the options is what keeps this line out
                    // of `drawnLines`, and so out of the box it is drawn from.
                    var edge = {color: accent(), weight: 2, fill: false, interactive: false, trailsOffline: true};
                    if (scope === 'all') {
                        var seen = mapBox();
                        outline = L.rectangle([[seen.s, seen.w], [seen.n, seen.e]], edge);
                    } else if (scope === 'band') {
                        var from = source();
                        if (from) { outline = L.polyline(from.line, edge); }
                    } else {
                        var ring = ringFor(scope);
                        if (ring) { outline = L.polygon(ring, edge); }
                    }
                    if (outline) { outline.addTo(map); }
                    preview.redraw();
                }

                // ---- the corners a reader places -------------------------------

                function handleIcon(lit) {
                    // 44 px of transparent target around a 15 px dot: the dot is
                    // what a finger aims at and the target is what it hits.
                    return L.divIcon({
                        className: 'trails-offline-handle', iconSize: [44, 44], iconAnchor: [22, 22],
                        html: '<div style="width:44px;height:44px;display:flex;align-items:center;justify-content:center">' +
                            '<span style="width:' + (lit ? 19 : 15) + 'px;height:' + (lit ? 19 : 15) + 'px;' +
                            'border-radius:50%;background:' + (lit ? 'var(--trails-strong)' : accent()) + ';' +
                            'border:2px solid var(--trails-panel);box-shadow:0 0 0 1.5px ' +
                            (lit ? 'var(--trails-strong)' : accent()) + '"></span></div>'
                    });
                }

                function syncHandles() {
                    handles.forEach(function (each) { map.removeLayer(each); });
                    handles = [];
                    if (!chooser || scope !== 'draw') { return; }
                    drawn.forEach(function (at, index) {
                        var handle = L.marker(at, {draggable: true, icon: handleIcon(index === picked),
                                                   zIndexOffset: 1000, trailsOffline: true}).addTo(map);
                        handle.on('click', function (event) {
                            // Or the map's own click would place a new corner
                            // directly on top of the one just tapped.
                            L.DomEvent.stopPropagation(event);
                            picked = (picked === index ? -1 : index);
                            // The whole chooser, because which corner is picked
                            // is on the panel as well as under the finger.
                            drawChooser();
                        });
                        // **Outline while dragging, tiles when it lands.**
                        // Re-counting on every drag frame is a point-in-polygon
                        // pass over the whole bounding box, dozens of times a
                        // second, on a phone.
                        handle.on('drag', function () {
                            var to = handle.getLatLng();
                            drawn[index] = [to.lat, to.lng];
                            if (outline && outline.setLatLngs && drawn.length >= 3) { outline.setLatLngs(drawn); }
                        });
                        handle.on('dragend', function () {
                            var to = handle.getLatLng();
                            drawn[index] = [to.lat, to.lng];
                            picked = index;
                            again();
                        });
                        handles.push(handle);
                    });
                }

                // **Corners are joined in the order they were tapped.** Tapped
                // across each other they make a tangled shape, and it is drawn
                // and counted as tangled rather than quietly straightened into a
                // convex hull -- which would keep ground nobody asked for and
                // give no way of saying so.
                map.on('click', function (event) {
                    if (!chooser || scope !== 'draw' || working) { return; }
                    drawn.push([event.latlng.lat, event.latlng.lng]);
                    picked = drawn.length - 1;
                    again();
                });

                // What every change to the selection does: throw the count away
                // and let the panel work it out again off the paint.
                function again() {
                    counted = null;
                    chosen = null;
                    return refresh();
                }

                // ---- what is kept ----------------------------------------------

                // **Where the figure lives, and why not in a cache at all.**
                // It was in the terrain cache, which reads well: storage cleared
                // under the page would take both. Then it was in a small cache of
                // its own, which read better and helped not at all -- measured on
                // an installed app, the first `caches.open()` of *any* cache costs
                // 23.2 s once the terrain holds tens of thousands of tiles, and
                // 11 ms with the store empty. The first touch pays for the whole
                // origin.
                //
                // So it is a row in the same database the worker keeps the
                // document and the switch in. `forget` clears it, which is the
                // property the first place was chosen for.
                var HELD = 'held';
                var TIMING = 'timing';
                // The two tile stores, named as the worker names them.
                var KEPT = 'packs';
                var SEEN = 'browse';
                // Tile prefixes identify the stand; Keep derives pack prefixes
                // from them when a completed run removes an older stand.
                var STAND = 'stand';
                var TILE_PREFIX = new URL({{ this.tile_prefix_json }}, location.href).href;

                function db() {
                    if (!window.indexedDB) { return Promise.reject(new Error('no database')); }
                    if (!db.open) {
                        db.open = new Promise(function (done, fail) {
                            // **The same number the worker opens with**, written
                            // out because the two are separate scripts. They may
                            // not disagree: a connection held at an older version
                            // blocks the other's upgrade, and without `onblocked`
                            // the wait never ends. Measured here -- the page held
                            // 1 while the worker asked for 2, and the map stopped
                            // opening altogether.
                            var ask = window.indexedDB.open('{{ this.database }}', 4);
                            ask.onblocked = function () { fail(new Error('blocked')); };
                            ask.onupgradeneeded = function () {
                                var made = ask.result;
                                if (!made.objectStoreNames.contains('pages')) { made.createObjectStore('pages'); }
                                if (!made.objectStoreNames.contains('flags')) { made.createObjectStore('flags'); }
                                if (made.objectStoreNames.contains('tiles')) {
                                    made.deleteObjectStore('tiles');
                                    ask.transaction.objectStore('flags').delete(HELD);
                                }
                                if (!made.objectStoreNames.contains('packs')) { made.createObjectStore('packs'); }
                                if (!made.objectStoreNames.contains('bench')) { made.createObjectStore('bench'); }
                                if (!made.objectStoreNames.contains(KEPT)) { made.createObjectStore(KEPT); }
                                if (!made.objectStoreNames.contains(SEEN)) {
                                    made.createObjectStore(SEEN).createIndex('at', 'at');
                                }
                            };
                            ask.onsuccess = function () {
                                var open = ask.result;
                                open.onversionchange = function () { open.close(); db.open = null; };
                                done(open);
                            };
                            ask.onerror = function () { fail(ask.error); };
                        });
                    }
                    return db.open;
                }

                function dbRead(store, key) {
                    return db().then(function (open) {
                        return new Promise(function (done, fail) {
                            var ask = open.transaction(store, 'readonly').objectStore(store).get(key);
                            ask.onsuccess = function () { done(ask.result === undefined ? null : ask.result); };
                            ask.onerror = function () { fail(ask.error); };
                        });
                    }).catch(function () { return null; });
                }

                function dbClear(store) {
                    return db().then(function (open) {
                        return new Promise(function (done) {
                            var deal = open.transaction(store, 'readwrite');
                            deal.objectStore(store).clear();
                            deal.oncomplete = function () { done(true); };
                            deal.onerror = function () { done(false); };
                        });
                    }).catch(function () { return false; });
                }

                function dbWrite(store, key, value) {
                    return db().then(function (open) {
                        return new Promise(function (done, fail) {
                            var deal = open.transaction(store, 'readwrite');
                            deal.objectStore(store).put(value, key);
                            deal.oncomplete = function () { done(true); };
                            deal.onerror = function () { fail(deal.error); };
                        });
                    }).catch(function () { return false; });
                }

                // Every key under a prefix, gone: what is left of an older
                // stand once a run has replaced the tiles it wanted.
                function dbSweep(store, prefix) {
                    if (!prefix) { return Promise.resolve(); }
                    return db().then(function (open) {
                        return new Promise(function (done, fail) {
                            var tx = open.transaction([store, 'flags'], 'readwrite');
                            var flags = tx.objectStore('flags'), held = flags.get(HELD);
                            held.onsuccess = function () {
                                var was = held.result, part = was && was.layers && was.layers[prefix];
                                tx.objectStore(store).delete(IDBKeyRange.bound(prefix, prefix + '￿', false, true));
                                if (part) {
                                    was.packs -= part.packs; was.bytes -= part.bytes;
                                    delete was.layers[prefix];
                                    flags.put(was, HELD);
                                }
                            };
                            tx.oncomplete = done;
                            tx.onerror = function () { fail(tx.error); };
                            tx.onabort = function () { fail(tx.error); };
                        });
                    });
                }

                // The prefixes the page names now, one per kind of tile.
                // **Keyed by the walker's own words for the four trees**, so
                // a tile fetched as `shade` is replaced under `shade` without
                // anything having to map one name onto the other.
                function prefixes() {
                    return {
                        map: TILE_PREFIX,
                        tiles: TILE_PREFIX,
                        height: HEIGHTS ? new URL(HEIGHTS.url.split('{z}')[0], location.href).href : null,
                        heights: HEIGHTS ? new URL(HEIGHTS.url.split('{z}')[0], location.href).href : null,
                        shade: SHADE ? new URL(SHADE.url.split('{z}')[0], location.href).href : null,
                        slope: SLOPE ? new URL(SLOPE.url.split('{z}')[0], location.href).href : null,
                        vegetation: VEGETATION ? new URL(VEGETATION.url.split('{z}')[0], location.href).href : null,
                        forest: FOREST ? new URL(FOREST.url.split('{z}')[0], location.href).href : null
                    };
                }

                // Which kept prefixes are not the page's any more, or null.
                function staleOf(stand) {
                    if (!stand) { return null; }
                    var now = prefixes(), out = null;
                    function moved(mine, theirs) {
                        return mine && theirs && theirs !== mine ? theirs : null;
                    }
                    var was = {map: moved(now.map, stand.tiles), tiles: moved(now.tiles, stand.tiles),
                               height: moved(now.height, stand.heights), heights: moved(now.heights, stand.heights),
                               shade: moved(now.shade, stand.shade), slope: moved(now.slope, stand.slope),
                               vegetation: moved(now.vegetation, stand.vegetation), forest: moved(now.forest, stand.forest)};
                    if (was.tiles || was.heights || was.shade || was.slope || was.vegetation || was.forest) { out = was; }
                    return out;
                }

                // **Written down, not counted out.** This was `cache.keys()` over
                // the whole terrain cache -- one `Request` object per tile -- on
                // every `refresh`: on load, on the switch, and every time the
                // panel is opened. Measured in Firefox: 1,000 entries 25 ms,
                // 10,000 202 ms, 40,000 920 ms. The whole map at z16 is 131,033
                // tiles, so about three seconds and 131,033 objects, each time,
                // on a phone already holding a 15.7 MB document. That is what
                // made an installed app hang and take the rest of the phone with
                // it, and it is why this asks for one entry instead.
                //
                // **`known` is false rather than zero when there is no record.**
                // The old code turned every failure into *nothing kept*, which is
                // the one wrong answer that costs bytes: it invites a reader with
                // a full cache to download it again.
                function kept() {
                    var none = {packs: 0, bytes: 0, top: 0, known: false, stale: null};
                    if (!window.caches) { return Promise.resolve(none); }
                    return Promise.all([dbRead('flags', HELD), dbRead('flags', STAND)]).then(function (both) {
                        var held = both[0], stand = both[1];
                        if (!held) { return none; }
                        // **Kept before stands were written down**: the tiles
                        // are the page's own stand, which is written down now so
                        // a later stand can tell them apart.
                        if (!stand) { stand = prefixes(); dbWrite('flags', STAND, stand); }
                        return {packs: held.packs || 0, bytes: held.bytes || 0,
                                top: held.top || 0, known: true, stale: staleOf(stand)};
                    }).catch(function () { return none; });
                }

                // A pack and its count commit together. A stopped run, overlapping
                // scopes and a repeated Keep all leave the same exact held figure.
                function putPack(url, body, top, prefix) {
                    return db().then(function (open) {
                        return new Promise(function (done, fail) {
                            var tx = open.transaction([KEPT, 'flags'], 'readwrite');
                            var store = tx.objectStore(KEPT), flags = tx.objectStore('flags');
                            var old = store.get(url), held = flags.get(HELD);
                            held.onsuccess = function () {
                                var was = held.result || {packs: 0, bytes: 0, top: 0};
                                store.put(body, url);
                                var count = old.result ? 0 : 1;
                                var bytes = body.byteLength - (old.result ? old.result.byteLength : 0);
                                // One scalar per tree/stand, never one per pack.
                                var layers = was.layers || {}, part = layers[prefix] || {packs: 0, bytes: 0};
                                part.packs += count; part.bytes += bytes; layers[prefix] = part;
                                flags.put({packs: was.packs + count, bytes: was.bytes + bytes,
                                           top: Math.max(was.top, top), layers: layers}, HELD);
                            };
                            tx.oncomplete = function () { done(); };
                            tx.onerror = function () { fail(tx.error); };
                            tx.onabort = function () { fail(tx.error); };
                        });
                    });
                }

                function room() {
                    if (!navigator.storage || !navigator.storage.estimate) {
                        return Promise.resolve({usage: null, quota: null, persisted: null});
                    }
                    return navigator.storage.estimate().then(function (guess) {
                        var persisted = navigator.storage.persisted ? navigator.storage.persisted() : Promise.resolve(null);
                        return persisted.then(function (held) {
                            return {usage: guess.usage, quota: guess.quota, persisted: held};
                        });
                    }).catch(function () { return {usage: null, quota: null, persisted: null}; });
                }

                function on() {
                    try { return window.localStorage.getItem(KEY) === 'on'; } catch (blocked) { return false; }
                }

                function remember(want) {
                    try { window.localStorage.setItem(KEY, want ? 'on' : 'off'); } catch (blocked) { return; }
                }

                // **Told to the worker on every load, not only when it moves.**
                // A worker is started and stopped around single fetches, so it
                // reads the flag out of its own cache; this keeps the two from
                // drifting when storage was cleared under the page.
                //
                // **And waited for, not merely posted.** Writing the flag is
                // asynchronous -- it goes into the worker's own cache -- while
                // the refresh that follows every call here redraws the sheets at
                // once. Posted and not waited for, those tiles were answered by a
                // worker still holding the old flag, and switching offline mode
                // off left the ground blank until something else made Leaflet ask
                // again: on a phone, noticing and panning. Measured, and the
                // reading is in the driven suite.
                //
                // The worker has always answered `{trails: 'offline'}` when the
                // flag is written. Nothing listened to it.
                //
                // **Two seconds, and then on regardless.** A panel that never
                // finishes refreshing is worse than one that refreshes a moment
                // early, and the flag is written either way -- what is lost is
                // only the redraw landing on the right side of it.
                function tellWorker(want) {
                    if (!navigator.serviceWorker || !navigator.serviceWorker.controller) { return Promise.resolve(false); }
                    return new Promise(function (settled) {
                        var over = false;
                        function done(answered) {
                            if (over) { return; }
                            over = true;
                            navigator.serviceWorker.removeEventListener('message', heard);
                            settled(answered);
                        }
                        function heard(event) {
                            if (!event.data || event.data.trails !== 'offline') { return; }
                            done(true);
                        }
                        navigator.serviceWorker.addEventListener('message', heard);
                        window.setTimeout(function () { done(false); }, 2000);
                        navigator.serviceWorker.controller.postMessage({trails: 'offline', on: !!want});
                    });
                }

                // Which scopes have something to be drawn round. A band and a box
                // with neither a planned route nor a selected track are two
                // buttons that answer nothing, so they are not offered at all.
                function offered() {
                    var from = source();
                    return SCOPES.filter(function (each) {
                        return from || (each.key !== 'band' && each.key !== 'rect');
                    });
                }

                // **Magnified rather than blank, past the finest level kept.**
                // Leaflet asks for the real tile at every zoom -- both sheets
                // carry `maxNativeZoom: 18` -- so one level past what is on the
                // device the worker answers a blank, and a blank is a valid 200,
                // so Leaflet counts it as loaded and prunes the coarse ground the
                // reader *does* own along with it. Measured on the same ground
                // one level apart: 24 tiles drawn at z15 and 0 at z16.
                //
                // Which is the worst way for it to fail. The data is on the
                // phone, the screen is empty, and nothing on it says that
                // zooming out would bring the map back -- in a valley, with no
                // second opinion available.
                //
                // Held to the finest level actually kept, and never below what
                // the sheet was built with. With one uniform level -- the whole
                // map at z16, which is what the budget is drawn around -- z17
                // becomes that level doubled: blurry, and navigable. With mixed
                // levels, a box at z16 under a band at z18, the ceiling is 18
                // and nothing changes at all. So it is never worse than leaving
                // it alone, which is what makes it worth doing without a switch
                // of its own.
                //
                // **Only while offline mode is on.** With it off the reader
                // wants the real z17 from Kartverket and can have it.
                function fitNativeZoom(top) {
                    map.eachLayer(function (layer) {
                        // A tile layer with a URL, so the chooser's own preview
                        // grid -- which paints its tiles and fetches none -- is
                        // not counted as one.
                        if (!layer.getTileUrl || !layer.options) { return; }
                        if (layer.options.trailsNative === undefined) {
                            layer.options.trailsNative = layer.options.maxNativeZoom;
                        }
                        // **Never above the level the tree was cut to.** The
                        // sheet goes deeper than the relief does, so holding
                        // every layer to the kept depth would ask the shadow for
                        // a z16 tile that was never built and blank it.
                        var want = (on() && top) ? Math.min(top, layer.options.trailsNative) : layer.options.trailsNative;
                        if (layer.options.maxNativeZoom === want) { return; }
                        layer.options.maxNativeZoom = want;
                        layer.redraw();
                    });
                    map.fire('trailsnativezoom');
                }

                // **A token on the sheet's URL, moved whenever what the worker
                // would answer has changed.** A browser holds an image by its
                // address, so a tile the reader saw as blank stays blank on that
                // address for the life of the document -- Leaflet rebuilding the
                // `<img>` does not help, because the memory cache answers and no
                // request reaches the worker at all.
                //
                // Measured, after two cheaper ideas failed. With the switch newly
                // off, `fetch` of a blanked tile returned 89,757 bytes of
                // Kartverket while an `<img>` on the same address still loaded
                // 1 x 1; the same tile with a query appended loaded at 256.
                // `cache-control: no-store` on the blank changed nothing.
                //
                // It costs no bytes where it matters. The token is moved after a
                // download and when the switch is thrown -- never on an ordinary
                // refresh -- and the worker strips it before looking, so a tile
                // that is kept is answered from the cache under its new address
                // exactly as it was under the old one.
                var stamp = 0;

                function stampOn(layer) {
                    if (!stamp) { return; }
                    layer.setUrl(plainUrl(layer) + '?trails=' + stamp);
                }

                function eachSheet(what) {
                    map.eachLayer(function (layer) {
                        // A tile layer with an address of its own, so the
                        // chooser's preview grid -- which paints its tiles and
                        // fetches none -- is not one.
                        if (!layer.getTileUrl || !layer.setUrl || !layer._url) { return; }
                        what(layer);
                    });
                }

                function restamp() {
                    stamp += 1;
                    eachSheet(stampOn);
                }

                // A sheet switched under the reader arrives with its own ceiling
                // of 18 and with no token, and neither the switch nor the count
                // moves when it does.
                map.on('baselayerchange', function () {
                    fitNativeZoom(snapshot && snapshot.kept ? snapshot.kept.top : 0);
                    eachSheet(stampOn);
                });

                function refresh() {
                    // Held here rather than only on the buttons: a route can be
                    // cleared while the panel is open, and the scope it was
                    // drawn round has to stop being the selection at that moment
                    // and not the next time somebody looks.
                    var still = offered().filter(function (each) { return each.key === scope; });
                    if (!still.length) { scope = 'all'; counted = null; chosen = null; }
                    return Promise.all([kept(), room()]).then(function (both) {
                        snapshot = {
                            available: !!(window.trailsWorker && window.trailsWorker.kept),
                            why: window.trailsWorker ? window.trailsWorker.why : 'the page has not asked yet',
                            on: on(), kept: both[0], storage: both[1],
                            busy: working !== null,
                            // **The progress, and not only that there is some.**
                            // A resumed run opens at what is already kept rather
                            // than at zero, and until this the only place that
                            // figure existed was one line of the panel — which
                            // is detached until the dock shows it, and gone again
                            // a second later. A claim nothing can read is a claim
                            // nothing can check.
                            done: working && working.counted ? working.done : null,
                            total: working ? working.total : null,
                            // **What the last run found against what it
                            // fetched.** The claim a resumed run has to keep is
                            // that it downloads nothing it already holds, and
                            // that is two numbers rather than a figure on a
                            // panel which is detached until the dock shows it.
                            run: lastRun,
                            chooser: chooser, scope: scope, zoom: zoom,
                            corners: drawn.length, counted: counted
                        };
                        fitNativeZoom(both[0].top);
                        draw();
                        // **Said out loud, because the switch shows outside this
                        // panel now.** The chrome draws the tool's row with one
                        // of two icons depending on whether the ground is here,
                        // and the panel is the only thing that knows. Announced
                        // on every refresh rather than only on the toggle: the
                        // worker settles after load and a download finishing
                        // changes the answer too, neither of which is a click.
                        var event;
                        try {
                            event = new CustomEvent('trails:offline', {detail: snapshot});
                        } catch (old) {
                            event = document.createEvent('CustomEvent');
                            event.initCustomEvent('trails:offline', false, false, snapshot);
                        }
                        document.dispatchEvent(event);
                        return snapshot;
                    });
                }

                // ---- keeping it ------------------------------------------------

                // **Six at a time, and never through the worker.** `cache:
                // 'reload'` is what the worker passes through untouched: without
                // it a download started while the switch was on would be
                // answered by the worker's own blank tile, and the reader would
                // be told their park was kept.
                // **The screen stays awake for the length of the run.** The
                // download is six `fetch` calls from this page and nothing else:
                // no Background Fetch, no worker doing it out of sight. A phone
                // that locks freezes the JavaScript, and 130,000 tiles is not a
                // run anybody watches to the end holding the thing.
                //
                // Every branch of it is optional. The API is absent on older
                // iOS and refused off a secure origin, and a run without it is
                // slower to babysit rather than broken -- so nothing here is
                // allowed to throw or to hold the run up waiting for an answer.
                var awake = null;

                function keepAwake() {
                    if (awake || !navigator.wakeLock || !navigator.wakeLock.request) { return; }
                    navigator.wakeLock.request('screen').then(function (held) {
                        // The run can end while the request is still in flight,
                        // and a lock nobody releases keeps the screen on for as
                        // long as the tab lives.
                        if (!working) { held.release(); return; }
                        awake = held;
                        held.addEventListener('release', function () { awake = null; });
                    }).catch(function () { awake = null; });
                }

                function letSleep() {
                    if (!awake) { return; }
                    try { awake.release(); } catch (gone) { /* already released */ }
                    awake = null;
                }

                // **Taken again when the reader comes back.** The browser drops
                // the lock whenever the page is hidden, and does not return it:
                // without this, one glance at a message leaves the rest of the
                // download to a screen that will lock again.
                document.addEventListener('visibilitychange', function () {
                    if (document.visibilityState !== 'visible') { return; }
                    if (working) { keepAwake(); }
                    // **And the age is recomputed, which is all that happens on
                    // a resume.** An app reopened on the fourth day of a walk
                    // should not still say *built 2 h ago*. It costs a
                    // `Date.parse` and a redraw of one line: no timer to keep it
                    // true, and no request behind it.
                    drawFresh();
                    draw();
                });

                // **Asked once, and never in front of the reader.** `caches.has`
                // touches Cache Storage, which is the twenty-three seconds this
                // whole change is about. So it is asked after the panel has
                // drawn, and once the answer is no it is written down and never
                // asked again.

                // **Three tries a tile, and only where a second one can change
                // the answer.** A scatter of refusals is a hole in the map at the
                // zoom the reader was standing at, and the run had no way to ask
                // again -- but asking again about *any* refusal would be two more
                // radio wakes for the same answer, which is the bill this map
                // spent the afternoon reducing.
                //
                // So: a network error is worth waiting out, and so are 429 and
                // the 5xx family, which are the server saying *not now*. A 400 or
                // a 404 is Kartverket saying the tile is not there -- z19 and z20
                // answer 400, measured -- and no amount of asking makes one.
                //
                // The wait grows with the attempt, because the case this exists
                // for is a server briefly out of patience, and coming straight
                // back is what made it so.
                var TRIES = 3;
                // A hard stop on waiting for the app to come back, so a run left
                // in the background cannot spin for ever on one tile.
                var WAITS = 8;

                function later(ms) {
                    return new Promise(function (done) { window.setTimeout(done, ms); });
                }

                // **How often this app has been put away.** Reported from a real
                // download: the refusals came *when the app had been briefly
                // inactive*. They are not Kartverket saying no -- iOS freezes a
                // web app that is not in front, in-flight requests are cut, and
                // the radio is not back the instant the reader is. Retrying into
                // that spends all three tries on the one situation where none of
                // them can work.
                var putAway = 0;
                document.addEventListener('visibilitychange', function () {
                    if (document.hidden) { putAway += 1; }
                });

                // Nothing is asked for while the app is away. A tile fetched into
                // a frozen radio is a refusal invented by this page.
                function whenInFront() {
                    if (!document.hidden) { return Promise.resolve(); }
                    return new Promise(function (done) {
                        var over = false;
                        function go() {
                            if (over || document.hidden) { return; }
                            over = true;
                            document.removeEventListener('visibilitychange', go);
                            window.clearInterval(poll);
                            // A moment after the app is in front again, because
                            // being visible and having a network are not the same
                            // instant.
                            later(250).then(done);
                        }
                        // **The event, and a poll behind it.** Whether
                        // `visibilitychange` fires for a standalone home-screen
                        // app on iOS is written down here as an open question and
                        // has never been measured -- and if it does not, waiting
                        // on it alone would park the run for ever after the first
                        // interruption. The poll costs a tick a second and only
                        // while the app is away, where nothing else is running
                        // anyway; a run that resumes a second late is not a
                        // failure, and one that never resumes is.
                        var poll = window.setInterval(go, 1000);
                        document.addEventListener('visibilitychange', go);
                    });
                }

                function fetchTile(url, attempt, waited) {
                    var away = putAway;
                    function again(answer) {
                        // **A failure across a suspension costs no try.** The app
                        // went away mid-request; that says nothing about the tile
                        // or the connection, and counting it would turn one
                        // glance at a message into a hole in the map.
                        if (putAway !== away || document.hidden) {
                            if (waited >= WAITS) { return null; }
                            return whenInFront().then(function () {
                                return fetchTile(url, attempt, waited + 1);
                            });
                        }
                        var worth = !answer || answer.status === 429 || answer.status >= 500;
                        // `false` for a tile the source says is not there, `null`
                        // for one it would not or could not give: the run below
                        // counts the second towards the connection giving out
                        // and not the first.
                        if (!worth || attempt >= TRIES) { return answer && answer.status === 404 ? false : null; }
                        return later(400 * attempt).then(function () {
                            return fetchTile(url, attempt + 1, waited);
                        });
                    }
                    return whenInFront().then(function () {
                        away = putAway;
                        // **The screen is asked for again here, and not only on
                        // `visibilitychange`.** The browser drops the lock every
                        // time the page is hidden and does not hand it back, and
                        // whether that event fires for a standalone home-screen
                        // app on iOS is written down in this file as an open
                        // question that has never been measured. It is the last
                        // thing that rode on the answer: the run itself resumes
                        // on the poll behind `whenInFront`, so hanging the lock
                        // on the same return is what makes the question stop
                        // mattering. A no-op while the lock is held, which is
                        // every tile but the first after a glance elsewhere.
                        keepAwake();
                        return fetch(url, {cache: 'reload', mode: 'cors'});
                    }).then(function (answer) {
                        if (answer && answer.ok) { return answer; }
                        return again(answer);
                    }).catch(function () { return again(null); });
                }

                function keep() {
                    if (working) { return working.done_; }
                    if (!window.caches) { return Promise.resolve(); }
                    // **Not begun at all without a connection.**
                    // `navigator.onLine` lies in one direction only -- it says
                    // online for any live interface, so it is wrong in a valley
                    // with one bar and no route -- but when it says false there
                    // is genuinely nothing, and beginning is then a hundred
                    // thousand fetches into a radio with nobody to talk to, in
                    // the one situation where the battery is the whole question.
                    // The stall guard below is what catches the case this gets
                    // wrong.
                    if (!navigator.onLine) {
                        lastRun = {total: 0, kept: 0, failed: 0, offline: true};
                        return refresh();
                    }
                    var walk = walker();
                    lastRun = null;
                    // **Every tile is either checked or fetched, and the counter
                    // counts both.** It used to pre-scan with `cache.keys()` so
                    // that a resumed run could open at the figure it had reached
                    // -- one `Request` object per tile, 131,033 of them, at the
                    // one moment the page is least able to afford it. What is
                    // asked instead is one `match` per tile, inside the loop that
                    // was already checking, so nothing here grows with the size
                    // of the download. The cost is that a resumed run climbs fast
                    // through what it already has rather than starting at the
                    // number: it is the same figure arriving a few seconds later,
                    // and it is not a re-download.
                    var state = {total: walk.total, done: 0, counted: true, failed: 0, absent: 0,
                                 held: 0, added: 0, bytes: 0, top: 0, requested: zoom,
                                 stop: false, done_: null, stale: null};
                    working = state;
                    state.done_ = kept().then(function (had) {
                        state.stale = had.stale;
                        // How many have refused in a row. Shared by all six
                        // runners on purpose: it is the connection being
                        // measured, not any one of them.
                        var missed = 0;
                        function one() {
                            if (state.stop) { return Promise.resolve(); }
                            var next = walk.next();
                            if (!next) { return Promise.resolve(); }
                            var kept = false, size = 0;
                            return dbRead(KEPT, next.url).then(function (there) {
                                if (there) { missed = 0; state.held += 1; kept = true; size = there.byteLength; return null; }
                                return fetchTile(next.url, 1, 0).then(function (answer) {
                                    if (answer) {
                                        missed = 0;
                                        return answer.arrayBuffer().then(function (body) {
                                            return putPack(next.url, body, next.kind === 'map' ? Math.min(state.requested, next.z + 3) : 0,
                                                packPrefix(prefixes()[next.kind])).then(function () {
                                                state.added += 1; kept = true; size = body.byteLength;
                                            });
                                        });
                                    }
                                    // **Not there is not refused.** A 404 is the
                                    // source's answer, given at once and the same
                                    // tomorrow; it says nothing about the
                                    // connection and does not count towards it
                                    // giving out. The margin is clipped to the
                                    // source's extent above, so this is the odd
                                    // hole rather than a whole edge.
                                    if (answer === false) { state.absent += 1; return null; }
                                    // Refused now means refused three times, so
                                    // the stall guard below still counts tiles
                                    // and not attempts.
                                    state.failed += 1;
                                    missed += 1;
                                    return null;
                                }).catch(function () {
                                    state.failed += 1;
                                    missed += 1;
                                    return null;
                                });
                            }).then(function () {
                                state.done += 1;
                                // Only what is on the device weighs and counts
                                // towards the depth kept: a refused tile charged
                                // as a kept one made a stalled run's figure
                                // overstate what it had.
                                if (kept) {
                                    if (next.kind === 'map') { state.top = Math.max(state.top, Math.min(state.requested, next.z + 3)); }
                                    state.bytes += size;
                                }
                                // **Give up on the connection, not on the tile.**
                                // One tile that will not come is a tile, and the
                                // other hundred thousand are still worth having;
                                // twelve in a row is not a tile, it is the signal
                                // -- and grinding on is a hundred thousand more
                                // attempts to wake a radio that has nothing to
                                // answer. Twelve rather than three because six run
                                // at once, so a healthy run's last rounds can
                                // carry a scatter of refusals. `missed` resets on
                                // every success, so bad tiles arriving in ones
                                // and twos never trip it.
                                if (missed >= 12) { state.stop = true; state.stalled = true; }
                                if (state.done % 25 === 0) { draw(); }
                                // **Written down as it goes**, so a run the phone
                                // interrupts still leaves a figure behind -- which
                                // is exactly the run that used to leave the panel
                                // saying nothing was kept.
                                return one();
                            });
                        }
                        var runners = [], i;
                        for (i = 0; i < 6; i += 1) { runners.push(one()); }
                        return Promise.all(runners).then(function () {
                            return dbRead('flags', HELD).then(function (held) {
                                if (!held) { return; }
                                held.top = state.stale && !state.stop ? state.top : Math.max(held.top, state.top);
                                return dbWrite('flags', HELD, held);
                            });
                        }).then(function () {
                            // Completed, not stopped: the kept tiles are the
                            // page's stand now, and what the old stand still
                            // holds beyond this selection goes with it. A run
                            // that stopped leaves the old stand written down
                            // so the next Keep can finish removing it.
                            if (state.stop || !state.stale) { return null; }
                            return Promise.all(['tiles', 'heights', 'shade', 'slope', 'vegetation', 'forest'].map(function (kind) {
                                return dbSweep(KEPT, packPrefix(state.stale[kind]));
                            })).then(function () { return dbWrite('flags', STAND, prefixes()); });
                        });
                    }).then(function () {
                        working = null;
                        letSleep();
                        // A run that was stopped leaves the chooser where it
                        // was: what the reader wants next is almost always to
                        // pick a coarser zoom, not to find the panel again.
                        // A run the reader stopped leaves the chooser where
                        // it was; a run the connection stopped goes on to the
                        // branch below, because ninety per cent of the ground is
                        // worth switching on for.
                        if (state.stop && !state.stalled) { return refresh(); }
                        // **And a run that kept nothing switches nothing on.**
                        // Every fetch failing is almost always the network, and
                        // turning the switch on then hands over exactly the blank
                        // map this chooser exists to prevent -- while saying it is
                        // what the reader asked for.
                        //
                        // Counted as tiles found plus tiles fetched, which is what
                        // this selection now has on the device: the two the loop
                        // could only get by asking the cache, one tile at a time,
                        // for every one of them.
                        lastRun = {
                            total: state.total, kept: state.held + state.added,
                            held: state.held, added: state.added,
                            failed: state.failed, stalled: !!state.stalled
                        };
                        if (!lastRun.kept) { return refresh(); }
                        chooser = false;
                        remember(true);
                        return tellWorker(true).then(function () {
                            // Ground that was blank a moment ago is kept now.
                            restamp();
                            return refresh();
                        });
                    });
                    keepAwake();
                    // Once, so the Stop button appears; `draw` leaves the
                    // chooser alone for the rest of the run.
                    drawChooser();
                    draw();
                    return state.done_;
                }

                function forget() {
                    if (!window.caches) { return Promise.resolve(); }
                    return Promise.all([
                        dbClear(KEPT), dbClear(SEEN), dbWrite('flags', HELD, null),
                        // What earlier versions wrote, in case the ground was
                        // never moved across. Deleting a cache that is not there
                        // is not an error.
                        caches.delete(TERRAIN), caches.delete(TILES)
                    ]).then(function () {
                        remember(false);
                        return tellWorker(false);
                    }).then(refresh);
                }

                // ---- the panel --------------------------------------------------

                // **The map's age, from the document's own header.** Read
                // rather than stamped into the page: a build time written into
                // the HTML changes the page's bytes on every rebuild, which
                // changes the worker's digest, which drops the cached page --
                // so recording the age would itself become a reason to download
                // the map again. `document.lastModified` is the `Last-Modified`
                // the copy in front of the reader arrived with, cache or
                // network, and the published object carries one -- measured, and
                // it is the same header the worker compares.
                //
                // **No timer behind it.** A displayed age wants one to stay
                // true, and a tick behind a locked screen is a wake-up to redraw
                // a string nobody is reading. It is recomputed when the panel
                // draws and when the app comes back, both of which are free.
                function age() {
                    var when = Date.parse(document.lastModified);
                    if (!when) { return null; }
                    var hours = (Date.now() - when) / 3600000;
                    if (hours < 0) { return null; }
                    if (hours < 1) { return 'This map was built less than an hour ago.'; }
                    if (hours < 48) { return 'This map was built ' + Math.round(hours) + ' h ago.'; }
                    return 'This map was built ' + Math.round(hours / 24) + ' d ago.';
                }

                // What the last check answered, so the row can say something
                // when the answer is *nothing to do* -- which is most of the
                // time, and is not a reason to leave the button looking unread.
                var checkSaid = '';

                // **And a way out of *Checking…*.** The answer comes back as a
                // message from a worker, and a worker can be stopped between the
                // question and the answer -- which would leave the one button
                // that asks disabled for the rest of the session, on the page
                // somebody is carrying up a valley. One shot, cleared by the
                // answer, and no timer running at any other time.
                var asking = null;

                // **How old this map is, and the only thing that asks for a
                // newer one.** Nothing on a timer and nothing on resume: being
                // out of date is made visible instead, and acting on it is one
                // tap. Both halves are needed -- a manual check nobody knows to
                // press is the same as no check, and an age with no way to act
                // on it is a complaint.
                //
                // **Handed out rather than built here, because it is not about
                // this panel.** A map goes stale because a home-screen app
                // resumes instead of navigating, and that is true of a reader
                // who never turns offline mode on at all -- for whom this panel
                // is a feature they do not use and would never open. The
                // arithmetic and the worker's ear live here; `Sources` asks for
                // a row of its own, and both stay in step because there is one
                // set of facts behind them.
                var freshRows = [];

                function freshRow() {
                    var wrap = document.createElement('div');
                    wrap.className = 'trails-offline-fresh';
                    wrap.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;' +
                        'margin:0 0 10px';
                    var when = document.createElement('p');
                    when.className = 'trails-offline-age';
                    when.style.cssText = 'margin:0;color:var(--trails-ink-5);font-size:11px';
                    var check = small(button('Check for a newer map', false));
                    check.className = 'trails-offline-check';
                    check.addEventListener('click', ask);
                    wrap.appendChild(when);
                    wrap.appendChild(check);
                    freshRows.push({age: when, check: check});
                    drawFresh();
                    return wrap;
                }

                // Drawn apart from the panel, and deliberately not behind its
                // `holder` guard: a row handed to `Sources` has to stay true
                // whether or not anybody has opened the offline tool.
                function drawFresh() {
                    var old = age();
                    var waiting = !!(window.trailsWorker && window.trailsWorker.checking);
                    var askable = !!(window.trailsWorker && window.trailsWorker.ask) && navigator.onLine;
                    freshRows.forEach(function (row) {
                        row.age.textContent = [old, checkSaid].filter(Boolean).join(' ');
                        row.check.disabled = waiting || !askable;
                        row.check.style.opacity = row.check.disabled ? '0.5' : '1';
                        row.check.textContent = waiting ? 'Checking…' : 'Check for a newer map';
                    });
                }

                function ask() {
                    if (!window.trailsWorker || !window.trailsWorker.ask) { return; }
                    checkSaid = '';
                    if (!window.trailsWorker.ask()) {
                        checkSaid = 'No connection — nothing was asked.';
                    } else {
                        if (asking) { window.clearTimeout(asking); }
                        asking = window.setTimeout(function () {
                            if (!window.trailsWorker.checking) { return; }
                            window.trailsWorker.checking = false;
                            checkSaid = 'No answer — try again.';
                            drawFresh();
                            draw();
                        }, 20000);
                    }
                    drawFresh();
                    draw();
                }

                document.addEventListener('trails:checked', function (event) {
                    var answer = event.detail || {};
                    if (asking) { window.clearTimeout(asking); asking = null; }
                    checkSaid = answer.failed
                        ? 'The map could not be reached.'
                        : (answer.newer ? '' : 'This is the newest one.');
                    drawFresh();
                    draw();
                });

                function megabytes(bytes) {
                    if (bytes === null || bytes === undefined) { return '\u2014'; }
                    if (bytes >= 1e9) { return (bytes / 1e9).toFixed(2) + ' GB'; }
                    return Math.round(bytes / 1e6) + ' MB';
                }

                function count(n) { return Number(n).toLocaleString('en-US'); }

                // **The fill, as something that can be repainted.** It used to
                // be written once when the button was made, which is right for
                // every button here except the one that is also an indicator: the
                // offline switch was filled whether it was on or off, so the only
                // thing saying which was the word inside it. A switch that looks
                // the same in both positions is not a switch.
                function fillFor(made, strong) {
                    made.style.cssText = 'font:inherit;font-size:13px;font-weight:600;padding:8px 14px;' +
                        'border-radius:7px;cursor:pointer;border:1px solid ' +
                        (strong ? 'var(--trails-strong);background:var(--trails-strong);color:var(--trails-on-strong)'
                                : 'var(--trails-rule);background:transparent;color:var(--trails-ink-2)');
                    return made;
                }

                function button(label, strong) {
                    var made = document.createElement('button');
                    made.type = 'button';
                    made.textContent = label;
                    return fillFor(made, strong);
                }

                function small(made) {
                    made.style.fontSize = '12px';
                    made.style.padding = '6px 10px';
                    return made;
                }

                function label(text) {
                    var made = document.createElement('p');
                    made.textContent = text;
                    made.style.cssText = 'margin:0 0 4px;color:var(--trails-ink-5);font-size:11px;' +
                        'text-transform:uppercase;letter-spacing:.04em';
                    return made;
                }

                function row() {
                    var made = document.createElement('div');
                    made.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px';
                    return made;
                }

                function build() {
                    holder = document.createElement('div');
                    holder.className = 'trails-offline';
                    said.state = document.createElement('p');
                    said.state.className = 'trails-offline-state';
                    said.state.style.cssText = 'margin:0 0 10px;color:var(--trails-ink-3)';
                    said.switchRow = document.createElement('div');
                    said.switchRow.style.cssText = 'display:flex;align-items:center;gap:10px;margin:0 0 10px';
                    said.toggle = button('Offline mode', true);
                    said.toggle.className = 'trails-offline-toggle';
                    said.toggle.addEventListener('click', function () { toggle(!on()); });
                    said.switchRow.appendChild(said.toggle);
                    said.figures = document.createElement('p');
                    said.figures.className = 'trails-offline-figures';
                    said.figures.style.cssText = 'margin:0 0 6px;color:var(--trails-ink-3);font-size:12px';
                    said.fresh = freshRow();
                    said.sheet = document.createElement('p');
                    said.sheet.className = 'trails-offline-sheet';
                    said.sheet.style.cssText = 'margin:0 0 10px;color:var(--trails-ink-5);font-size:11px';

                    // **The chooser is built once and filled, not rebuilt.** The
                    // margin slider is a control somebody drags, and a drag on an
                    // element that is thrown away and made again on every count
                    // ends the moment the first figure arrives.
                    said.chooser = document.createElement('div');
                    said.chooser.className = 'trails-offline-chooser';
                    said.chooser.style.cssText = 'margin:0 0 10px;padding:10px;border:1px solid var(--trails-rule);' +
                        'border-radius:8px;display:none';
                    said.which = row();
                    said.which.className = 'trails-offline-scopes';
                    said.chooser.appendChild(said.which);

                    said.drawWrap = document.createElement('div');
                    said.drawWrap.style.display = 'none';
                    said.drawSaid = label('Corners');
                    said.drawSaid.className = 'trails-offline-corners';
                    said.drawWrap.appendChild(said.drawSaid);
                    var tools = row();
                    said.undo = small(button('Corner back', false));
                    said.undo.className = 'trails-offline-undo';
                    said.undo.addEventListener('click', function () {
                        if (!drawn.length) { return; }
                        drawn.pop();
                        picked = -1;
                        again();
                    });
                    said.drop = small(button('Remove the one picked', false));
                    said.drop.className = 'trails-offline-drop';
                    said.drop.addEventListener('click', function () {
                        if (picked < 0 || picked >= drawn.length) { return; }
                        drawn.splice(picked, 1);
                        picked = -1;
                        again();
                    });
                    said.clear = small(button('Clear', false));
                    said.clear.className = 'trails-offline-clear';
                    said.clear.addEventListener('click', function () {
                        drawn = [];
                        picked = -1;
                        again();
                    });
                    tools.appendChild(said.undo);
                    tools.appendChild(said.drop);
                    tools.appendChild(said.clear);
                    said.drawWrap.appendChild(tools);
                    said.chooser.appendChild(said.drawWrap);

                    said.marginWrap = document.createElement('div');
                    said.marginWrap.style.cssText = 'display:none;margin:0 0 8px';
                    said.marginSaid = label('Room round the line');
                    said.marginSaid.className = 'trails-offline-margin-said';
                    said.margin = document.createElement('input');
                    said.margin.type = 'range';
                    said.margin.className = 'trails-offline-margin';
                    said.margin.min = '0';
                    said.margin.max = '5000';
                    said.margin.step = '250';
                    said.margin.value = String(margin);
                    said.margin.style.width = '100%';
                    said.margin.addEventListener('input', function () {
                        margin = Number(said.margin.value);
                        again();
                    });
                    said.marginWrap.appendChild(said.marginSaid);
                    said.marginWrap.appendChild(said.margin);
                    said.chooser.appendChild(said.marginWrap);

                    said.chooser.appendChild(label('Finest zoom'));
                    said.fine = row();
                    said.fine.className = 'trails-offline-zooms';
                    said.chooser.appendChild(said.fine);

                    said.says = document.createElement('p');
                    said.says.className = 'trails-offline-needed';
                    said.says.style.cssText = 'margin:0 0 6px;color:var(--trails-ink-3);font-size:12px';
                    said.chooser.appendChild(said.says);

                    said.overview = document.createElement('p');
                    said.overview.className = 'trails-offline-overview';
                    said.overview.style.cssText = 'margin:0 0 6px;color:var(--trails-ink-3);font-size:12px';
                    said.chooser.appendChild(said.overview);

                    said.bar = document.createElement('div');
                    said.bar.className = 'trails-offline-bar';
                    said.bar.style.cssText = 'height:8px;border-radius:4px;background:var(--trails-rule);' +
                        'overflow:hidden;margin:0 0 4px';
                    said.fill = document.createElement('i');
                    said.fill.style.cssText = 'display:block;height:100%;width:0;background:var(--trails-accent)';
                    said.bar.appendChild(said.fill);
                    said.chooser.appendChild(said.bar);

                    said.budget = document.createElement('p');
                    said.budget.className = 'trails-offline-budget';
                    said.budget.style.cssText = 'margin:0 0 6px;color:var(--trails-ink-5);font-size:11px';
                    said.chooser.appendChild(said.budget);

                    said.layer = document.createElement('p');
                    said.layer.className = 'trails-offline-layer';
                    said.layer.style.cssText = 'margin:0 0 8px;color:var(--trails-ink-5);font-size:11px';
                    said.chooser.appendChild(said.layer);

                    said.refused = document.createElement('p');
                    said.refused.className = 'trails-offline-refused';
                    said.refused.style.cssText = 'margin:0 0 8px;color:var(--trails-ink-2);font-size:12px;display:none';
                    said.chooser.appendChild(said.refused);

                    said.go = button('Keep it', true);
                    said.go.className = 'trails-offline-go';
                    said.go.addEventListener('click', function () {
                        if (working) { working.stop = true; return; }
                        if (said.go.disabled) { return; }
                        // Asked from the press and not at load, because that is
                        // when a browser will grant it: an origin nobody has
                        // touched asking to be kept for ever is what the rule
                        // about user gestures exists to refuse.
                        if (navigator.storage && navigator.storage.persist) { navigator.storage.persist(); }
                        keep();
                    });
                    said.chooser.appendChild(said.go);

                    said.tools = document.createElement('div');
                    said.tools.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap';
                    said.keep = button('Keep terrain\u2026', false);
                    said.keep.className = 'trails-offline-keep';
                    said.keep.addEventListener('click', function () { chooser = !chooser; refresh(); });
                    said.forget = button('Delete', false);
                    said.forget.className = 'trails-offline-forget';
                    said.forget.addEventListener('click', function () {
                        if (!window.confirm('Delete the terrain kept on this device?')) { return; }
                        forget();
                    });
                    said.tools.appendChild(said.keep);
                    said.tools.appendChild(said.forget);
                    holder.appendChild(said.state);
                    holder.appendChild(said.switchRow);
                    holder.appendChild(said.figures);
                    holder.appendChild(said.sheet);
                    holder.appendChild(said.fresh);
                    holder.appendChild(said.chooser);
                    holder.appendChild(said.tools);
                    // **Left detached on purpose.** The dock is what puts a
                    // panel on the screen, and a holder appended to the map
                    // container would sit over the terrain until it got there.
                    // This is the same seam `Where I am` and `Sources` use.
                }

                // **Which of the levels is the one being coloured in, and how
                // much ground it covers.** Every level carries its own one-tile
                // margin, so the same selection is 223 km2 at z15 and 1,712 km2
                // at z11, where a tile is eight kilometres across. The preview
                // draws the level matching the map's zoom, which is honest and,
                // without this line, unreadable: the shape looks as though it
                // grew when the reader zoomed out.
                function sayLayer() {
                    if (!chosen || !chooser) { said.layer.textContent = ''; return; }
                    var z = Math.min(chosen.top, Math.max(OVERVIEW, map.getZoom()));
                    var set = chosen.levels[z];
                    if (!set) { said.layer.textContent = ''; return; }
                    var seen = mapBox();
                    var side = 156543.03392 * Math.cos((seen.n + seen.s) / 2 * Math.PI / 180) /
                        Math.pow(2, z) * 256 / 1000;
                    var n = set.size;
                    said.layer.textContent = 'Coloured in: level z' + z + ' \u2014 ' + count(n) +
                        ' tiles of ' + side.toFixed(2) + ' km, about ' + count(Math.round(n * side * side)) + ' km2. ' +
                        (z < chosen.top ? 'Zooming in shows the finer levels, which lie closer.'
                                        : 'This is the finest level chosen.');
                }

                function drawChooser() {
                    said.chooser.style.display = chooser ? '' : 'none';
                    if (!chooser) { paint(); syncHandles(); return; }

                    var here = scopeOf(scope);
                    said.which.innerHTML = '';
                    offered().forEach(function (each) {
                        var pick = small(button(each.label, each.key === scope));
                        pick.className = 'trails-offline-scope';
                        pick.setAttribute('data-scope', each.key);
                        // Chosen is a background colour and nothing else here,
                        // which a screen reader cannot see. Five other controls
                        // on this page already say it out loud; these two were
                        // the ones that never learned to.
                        pick.setAttribute('aria-pressed', String(each.key === scope));
                        pick.title = each.hint;
                        pick.addEventListener('click', function () {
                            scope = each.key;
                            if (zoom > each.ceiling) { zoom = each.ceiling; }
                            again();
                        });
                        said.which.appendChild(pick);
                    });

                    said.drawWrap.style.display = scope === 'draw' ? '' : 'none';
                    if (scope === 'draw') {
                        said.drawSaid.textContent = 'Corners \u2014 ' + drawn.length +
                            (picked >= 0 ? ', no. ' + (picked + 1) + ' picked' : ', none picked');
                        // Greyed as well as disabled: nothing else on this
                        // panel refuses a press without looking as though it
                        // will, and *Remove the one picked* with nothing picked
                        // is the one somebody presses first.
                        [[said.undo, !drawn.length], [said.drop, picked < 0], [said.clear, !drawn.length]]
                            .forEach(function (each) {
                                each[0].disabled = each[1];
                                each[0].style.opacity = each[1] ? '0.4' : '1';
                                each[0].style.cursor = each[1] ? 'default' : 'pointer';
                            });
                    }

                    said.marginWrap.style.display = scope === 'rect' ? '' : 'none';
                    if (scope === 'rect') {
                        said.marginSaid.textContent = 'Room round the line \u2014 ' + (margin / 1000).toFixed(2) + ' km';
                    }

                    // **Every level that would go over the budget is refused,
                    // and it says why.** The buffer is read rather than filled
                    // here: pricing five levels of a turned rectangle on the way
                    // to painting a row of buttons is what makes a panel feel
                    // broken. Whatever is not in it yet is worked out on the tick
                    // below, and this row is drawn again straight after.
                    said.fine.innerHTML = '';
                    var z;
                    for (z = FLOOR; z <= TOP; z += 1) {
                        (function (level) {
                            var pick = small(button('z' + level, level === zoom));
                            pick.className = 'trails-offline-zoom';
                            pick.setAttribute('data-zoom', String(level));
                            pick.setAttribute('aria-pressed', String(level === zoom));
                            var known = memo[sig(scope, level)];
                            var why = null;
                            if (level > here.ceiling) {
                                why = 'Too much ground at this zoom \u2014 that is an archive, not a download.';
                            } else if (cap !== null && known && known.bytes > cap) {
                                why = 'Over the budget: ' + megabytes(known.bytes) + ' against ' + megabytes(cap) +
                                    ', which is what the whole map costs at z' + CAP_ZOOM + '.';
                            }
                            if (why) {
                                pick.disabled = true;
                                pick.style.opacity = '0.4';
                                pick.style.cursor = 'default';
                                pick.title = why;
                            } else {
                                pick.addEventListener('click', function () {
                                    // Held here as well, because a button drawn
                                    // before its level had been priced is a
                                    // button that is enabled and should not be.
                                    if (cost(scope, level).bytes > budget()) { drawChooser(); return; }
                                    zoom = level;
                                    again();
                                });
                            }
                            said.fine.appendChild(pick);
                        })(z);
                    }

                    var from = scope === 'band' || scope === 'rect' ? source() : null;
                    var hint = here.hint + (from ? ' Drawn round ' + from.from + '.' : '');
                    if (counted === null) {
                        said.says.textContent = 'Working out how much that is\u2026';
                        said.overview.textContent = '';
                        said.fill.style.width = '0';
                        said.budget.textContent = '';
                        // **Off the paint, and every level of the row with it.**
                        // The whole map at z16 is 131,000 tiles and about half a
                        // second of arithmetic; done inline, the panel would open
                        // frozen and the reader would have been given no reason.
                        window.setTimeout(function () {
                            if (counted !== null || !chooser) { return; }
                            var picking = recount();
                            // `at` is the selection's own signature -- scope,
                            // zoom and every corner -- so it says *which* count
                            // this is and not merely that there is one. What
                            // reads it is a check that has to tell a figure from
                            // before a drag from the figure after it.
                            counted = {packs: picking.packs, bytes: picking.bytes,
                                       scope: scope, zoom: zoom, at: picking.at, overview: picking.overview};
                            budget();
                            var level;
                            for (level = FLOOR; level <= here.ceiling; level += 1) { cost(scope, level); }
                            refresh();
                        }, 0);
                    } else {
                        said.says.textContent = count(counted.packs - counted.overview.packs) + ' packs \u00b7 about ' +
                            megabytes(counted.bytes - counted.overview.bytes) + ' \u00b7 ' + hint;
                        said.overview.textContent = 'overview, ' + count(counted.overview.packs) + ' packs, ' +
                            megabytes(counted.overview.bytes) + ' \u00b7 the whole box at z8\u2013z11';
                        var share = cap ? counted.bytes / cap : 0;
                        said.fill.style.width = Math.min(100, share * 100) + '%';
                        said.fill.style.background = share > 1 ? 'var(--trails-bad, #e07a6a)' : 'var(--trails-accent)';
                        said.budget.textContent = Math.round(share * 100) + '% of the budget (' + megabytes(cap) +
                            ', which is what the whole map costs at z' + CAP_ZOOM + ')';
                    }

                    // **Refused against the room there actually is, not against
                    // a number written here.** A ceiling per scope catches the
                    // whole map above z16; it does not catch a phone that has
                    // 3 GB free and a selection that fits the budget twice over.
                    // This is measured on the device: a Firefox profile answered
                    // 3.3 GB, and a phone will answer something else again.
                    var free = null, space = (snapshot || {}).storage;
                    if (space && space.quota !== null && space.usage !== null) { free = space.quota - space.usage; }
                    var tooMuch = counted !== null && free !== null && counted.bytes > free * 0.9;
                    said.refused.style.display = tooMuch ? '' : 'none';
                    if (tooMuch) {
                        said.refused.textContent = 'That is more than this device will hold \u2014 ' +
                            megabytes(free) + ' free. Pick a coarser zoom or a smaller piece of ground.';
                    }

                    said.go.textContent = working ? 'Stop' : 'Keep it';
                    said.go.className = working ? 'trails-offline-stop' : 'trails-offline-go';
                    said.go.disabled = !working && (counted === null || counted.packs === counted.overview.packs || tooMuch);
                    said.go.style.opacity = said.go.disabled ? '0.5' : '1';

                    paint();
                    syncHandles();
                    sayLayer();
                }

                function draw() {
                    if (!holder) { return; }
                    // **The three fields a run moves are refreshed here, because
                    // `refresh` does not run during one.** The snapshot is built
                    // once when something settles; progress arrives every 25
                    // tiles and goes only to the panel's own text. So
                    // `state().busy` was answering from before the run started —
                    // true by the time anything waited on it, but stale in the
                    // window that matters, and `done` would have been null
                    // throughout the one thing it exists to report.
                    if (snapshot) {
                        snapshot.busy = working !== null;
                        snapshot.done = working && working.counted ? working.done : null;
                        snapshot.total = working ? working.total : null;
                    }
                    var have = snapshot || {};
                    if (have.available) {
                        said.state.textContent = 'This map is kept on your device. Terrain is what is left, ' +
                            'and it is what you choose to keep.';
                    } else if (have.why) {
                        // **Two different refusals, and only one of them is
                        // about the browser.** An origin that is not secure
                        // gets no worker whatever the browser is, and telling
                        // that reader to use Safari sends them after the wrong
                        // thing entirely.
                        //
                        // The insecure origin comes in two kinds and they want
                        // different advice: a map opened off the disk has no
                        // address to fix, and a map opened over http:// has
                        // exactly one, so the sentence hands it over ready to
                        // tap rather than describing it.
                        said.state.textContent = have.why.indexOf('secure') === -1
                            ? 'Not available in this browser \u2014 ' + have.why +
                              '. On iOS a worker exists in Safari and in this map added to the Home Screen, ' +
                              'and in no other browser.'
                            : location.protocol === 'file:'
                                ? 'Not available here \u2014 ' + have.why +
                                  '. This is the map opened from a file rather than from a web address.'
                                : 'Not available here \u2014 ' + have.why +
                                  '. The address is http, not https \u2014 open https://' +
                                  location.host + location.pathname + ' and offline mode is there.';
                    } else {
                        // Neither kept nor refused: the registration has not
                        // settled. Saying *not available* here would be a wrong
                        // answer rather than a slow one.
                        said.state.textContent = 'Asking this browser whether it can keep the map\u2026';
                    }
                    drawFresh();
                    said.toggle.textContent = have.on ? 'Offline mode is on' : 'Offline mode is off';
                    said.toggle.setAttribute('aria-pressed', have.on ? 'true' : 'false');
                    // Filled when it is on, outlined when it is off -- the same
                    // two shapes every other button here uses for *this is the
                    // one* and *this is available*.
                    fillFor(said.toggle, !!have.on);
                    said.toggle.disabled = !have.available;
                    said.toggle.style.opacity = have.available ? '1' : '0.5';
                    if (working) {
                        said.figures.textContent = working.counted
                            ? 'Keeping ' + count(working.done) + ' of ' + count(working.total) +
                              (working.failed ? ' \u00b7 ' + working.failed + ' refused' : '')
                            : 'Checking what is already kept\u2026';
                    } else if (have.kept && have.kept.stale) {
                        // **Said before the figures, because the figures are of
                        // the old stand.** Keep brings the current ground in.
                        said.figures.textContent = 'Kept from an older stand of the map \u2014 Keep loads the new packs and drops the old when it completes.';
                    } else if (lastRun && lastRun.offline) {
                        said.figures.textContent = 'No connection \u2014 nothing was tried, and nothing ' +
                            'was spent looking. Try again where there is signal.';
                    } else if (lastRun && lastRun.stalled) {
                        // **Told, rather than read off a count that stopped
                        // moving.** A run that gave up on the connection looks
                        // exactly like a run somebody stopped, and the
                        // difference is whether pressing Keep again is worth
                        // anything.
                        said.figures.textContent = 'The connection gave out \u2014 ' + count(lastRun.kept) +
                            ' packs are kept and nothing further was tried. Keep again picks up where it stopped.';
                    } else if (lastRun && !lastRun.kept && lastRun.total) {
                        // **Said, rather than left to be discovered.** A run
                        // where nothing arrived looks exactly like a run that
                        // was never started, and the switch being still off is
                        // the only other evidence there is.
                        said.figures.textContent = 'Nothing arrived \u2014 all ' + count(lastRun.total) +
                            ' were refused three times over, so offline mode is still off. ' +
                            'Check the connection and try again.';
                    } else {
                        // **Not counted rather than none, when there is no
                        // record.** A cache from before this map kept a figure
                        // has ground and no number, and answering *0 tiles kept*
                        // is the one wrong answer that costs bytes -- it invites
                        // a reader with everything to download it again. The
                        // space used is exact either way; it comes from the
                        // browser and not from a count.
                        var lines = [have.kept && have.kept.known
                            ? count(have.kept.packs) + ' packs kept'
                            : 'kept packs not counted \u2014 the next download says how many'];
                        if (lastRun && lastRun.failed) { lines.push(count(lastRun.failed) + ' refused'); }
                        if (have.storage && have.storage.usage !== null) {
                            lines.push(megabytes(have.storage.usage) + ' of ' + megabytes(have.storage.quota) + ' used');
                        }
                        if (have.storage && have.storage.persisted) { lines.push('storage is persistent'); }
                        said.figures.textContent = lines.join(' \u00b7 ');
                    }
                    // Offered whenever there may be something to delete, which
                    // includes not knowing: a reader who cannot count what they
                    // hold is the one most likely to want it gone.
                    var maybe = have.kept && (have.kept.packs || !have.kept.known);
                    said.forget.disabled = !maybe;
                    said.forget.style.opacity = maybe ? '1' : '0.5';
                    // **Said, because otherwise it is found the hard way.** Only
                    // the sheet that is showing is kept -- topo and grayscale
                    // share a host and keeping both would double every figure
                    // here -- so switching sheets with no signal gives a blank
                    // map, and nothing else on the page would explain why.
                    // **What a reader cannot work out from a progress bar.**
                    // That the run needs this page in front is a property of
                    // where it runs, and that stopping is free is a property of
                    // the cache being checked before every tile -- neither is
                    // visible, and guessing either one wrong costs an evening.
                    said.sheet.textContent = working
                        ? 'Keep this page in front — the run pauses when the phone locks or you switch ' +
                          'app, and picks up when you come back. Stopping costs nothing either.'
                        : (maybe
                            ? 'Kept for the ' + baseName() + ' sheet. Switching sheets with no signal shows nothing.'
                            : '');
                    // **Not while a run is going.** Progress arrives every 25
                    // tiles, and rebuilding the chooser that often rebuilds ten
                    // buttons, re-reads the plan's whole route to decide which
                    // scopes to offer, and takes the focus off whatever the
                    // reader was on -- including the Stop button.
                    if (!working) { drawChooser(); }
                }

                // Only the one line moves, because the level being coloured in is
                // the only thing a zoom changes: the selection is the same set at
                // z11 as at z16, which is exactly what this line exists to say.
                map.on('zoomend', function () { if (chooser) { sayLayer(); } });
                // A theme picked in the menu never touches `prefers-color-scheme`,
                // and a canvas keeps the colour it was painted with.
                document.addEventListener('trails:theme', function () { if (chooser) { paint(); } });

                // **On, with nothing kept, opens the chooser instead.** A switch
                // that answers with a blank map is a switch that lied.
                // **A tile, not a count, when there is no record.** The guard
                // exists to stop the switch handing over a blank map, and a reader
                // whose cache predates the record has ground but no figure. One
                // `match` answers whether this selection has anything at all,
                // which is what the guard is actually asking.
                function anyKept() {
                    return kept().then(function (there) {
                        if (there.known) { return there.packs > 0; }
                        var first = walker().next();
                        if (!first) { return false; }
                        return dbRead(KEPT, first.url).then(function (one) { return !!one; })
                            .catch(function () { return false; });
                    });
                }

                function toggle(want) {
                    return anyKept().then(function (any) {
                        if (want && !any) {
                            chooser = true;
                            return refresh();
                        }
                        remember(want);
                        return tellWorker(want).then(function () {
                            restamp();
                            return refresh();
                        });
                    });
                }

                build();
                if (navigator.serviceWorker) {
                    // **Registration finishes after the page does.** Reading
                    // `window.trailsWorker.kept` once, at load, is reading it
                    // before the promise it is set in has settled -- the panel
                    // said *not available in this browser* on a browser that had
                    // one, which is the one sentence here that must not be wrong.
                    navigator.serviceWorker.ready.then(function () {
                        return tellWorker(on());
                    }).then(refresh, refresh);
                }

                window.trailsOffline = {
                    holder: holder,
                    // The chrome reads the worker's own timings out of the same
                    // database; one opener, so the page has one connection.
                    dbRead: dbRead,
                    // A row of its own for any panel that wants one. `Sources`
                    // takes one; see `freshRow`.
                    freshness: freshRow,
                    refresh: refresh,
                    state: function () { return snapshot; },
                    // The finite tree box. Return fresh corners to keep it ours.
                    bounds: function () {
                        var box = EXTENT;
                        return [[box.s, box.w], [box.n, box.e]];
                    },
                    scopes: SCOPES.map(function (each) { return each.key; }),
                    open: function (want) { chooser = want === undefined ? true : !!want; return refresh(); },
                    choose: function (which, level) {
                        if (which) { scope = which; }
                        if (level) { zoom = level; }
                        // Clamped here and not only on the button, so the
                        // ceiling is a property of the scope rather than a
                        // thing the screen happens to draw.
                        var here = scopeOf(scope);
                        if (zoom > here.ceiling) { zoom = here.ceiling; }
                        if (zoom > TOP) { zoom = TOP; }
                        if (zoom < FLOOR) { zoom = FLOOR; }
                        // **And against the budget, for the same reason.** A
                        // disabled button is what the screen does; it is not
                        // what is true, and something asking for a level nobody
                        // may have has to come back holding one they may.
                        while (zoom > FLOOR && cost(scope, zoom).bytes > budget()) { zoom -= 1; }
                        return again();
                    },
                    // **Setting the drawn area from outside**, because there is
                    // no way to tap four corners from a script and have the map
                    // believe it -- and the check that this panel keeps what it
                    // says it will keep has to ask for a piece of ground small
                    // enough to be a check rather than a bulk download.
                    area: function (ring) {
                        drawn = (ring || []).map(function (at) { return [at[0], at[1]]; });
                        picked = -1;
                        return again();
                    },
                    // What the chooser would fetch, computed rather than
                    // estimated, so a check reads the figure the panel shows.
                    // Counted, not listed: `weigh` already has the figure and
                    // building 131,033 strings to call `.length` on them was the
                    // most expensive way to ask.
                    needed: function () {
                        var picked = recount();
                        return {packs: base() ? picked.packs : 0, bytes: picked.bytes};
                    },
                    toggle: toggle,
                    keep: keep,
                    stop: function () { if (working) { working.stop = true; } },
                    forget: forget,
                    // The prefixes the page names, for a check that stages an
                    // older stand of the kept tiles.
                    prefixes: prefixes
                };

                window.setTimeout(refresh, 0);
            })();

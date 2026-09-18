// Shared by the worker and Keep: one uncompressed PMTiles subset, one row ledger.
var PackIO = (function () {
function tileId(z, x, y) {
    if (!Number.isInteger(z) || z < 0 || z > 26 || !Number.isInteger(x) || !Number.isInteger(y) ||
            x < 0 || y < 0 || x >= 2 ** z || y >= 2 ** z) { throw Error("invalid tile address"); }
    var result = (4 ** z - 1) / 3;
    for (var bit = z - 1; bit >= 0; bit--) {
        var side = 2 ** bit, rx = !!(x & side), ry = !!(y & side);
        result += side * side * ((3 * rx) ^ ry);
        if (!ry) {
            if (rx) { x = side - 1 - x; y = side - 1 - y; }
            var swap = x; x = y; y = swap;
        }
    }
    return result;
}
function packHeader(body) {
    var bytes = new Uint8Array(body), view = new DataView(body);
    function u64(at) {
        var value = Number(view.getBigUint64(at, true));
        if (!Number.isSafeInteger(value)) { throw Error("unsafe pack offset"); }
        return value;
    }
    if (bytes.length < 127 || String.fromCharCode.apply(null, bytes.subarray(0, 8)) !== 'PMTiles\x03') {
        throw Error("invalid PMTiles v3 header");
    }
    var h = {root: u64(8), rootLen: u64(16), data: u64(56), size: u64(64), count: u64(80), low: bytes[100], high: bytes[101]};
    if (bytes[96] !== 1 || bytes[97] !== 1 || bytes[98] !== 1 || bytes[99] !== 2 ||
            h.low > h.high || h.high > 26 || h.count < 1 || h.count > 85 || u64(72) !== h.count || u64(88) !== h.count ||
            h.root !== 127 || h.rootLen <= 0 || h.rootLen > 16384 || u64(24) !== h.root + h.rootLen ||
            u64(32) < 2 || u64(32) > 16384 || h.data !== u64(24) + u64(32) || u64(40) !== h.data || u64(48) !== 0) {
        throw Error("unsupported pack header");
    }
    return h;
}
function packDirectory(h, body) {
    var bytes = new Uint8Array(body), cursor = 0;
    function varint() {
        var value = 0;
        for (var shift = 0; shift < 56; shift += 7) {
            if (cursor >= bytes.length) { break; }
            var byte = bytes[cursor++];
            value += (byte & 127) * 2 ** shift;
            if (!Number.isSafeInteger(value)) { break; }
            if (byte < 128) { return value; }
        }
        throw Error("invalid directory varint");
    }
    if (varint() !== h.count) { throw Error("directory count mismatch"); }
    var ids = [], lengths = [], id = 0, entries = new Map(), end = 0;
    for (var i = 0; i < h.count; i++) {
        var delta = varint();
        if (i && !delta) { throw Error("duplicate tile ID"); }
        id += delta; ids.push(id);
    }
    for (i = 0; i < h.count; i++) { if (varint() !== 1) { throw Error("unsupported run length"); } }
    for (i = 0; i < h.count; i++) { lengths.push(varint()); }
    for (i = 0; i < h.count; i++) {
        var encoded = varint(), offset = encoded === 0 && i > 0 ? end : encoded - 1, length = lengths[i];
        if (length <= 0 || offset !== end || offset + length > h.size) { throw Error("invalid tile offset"); }
        entries.set(ids[i], {offset: h.data + offset, length: length}); end = offset + length;
    }
    if (cursor !== bytes.length || end !== h.size || ids[0] < (4 ** h.low - 1) / 3 || ids[ids.length - 1] >= (4 ** (h.high + 1) - 1) / 3) {
        throw Error("directory length or zoom mismatch");
    }
    return entries;
}

function unpack(body) {
    if (!(body instanceof ArrayBuffer)) { throw Error("pack is not an ArrayBuffer"); }
    var h = packHeader(body);
    if (body.byteLength !== h.data + h.size) { throw Error("truncated pack"); }
    return {body: body, entries: packDirectory(h, body.slice(h.root, h.root + h.rootLen))};
}
function sliceTile(pack, id) {
    var entry = pack.entries.get(id);
    return entry ? pack.body.slice(entry.offset, entry.offset + entry.length) : null;
}
// Invert Hilbert IDs to reproduce the Python writer's geographic header too.
function xyz(id) {
    if (!Number.isSafeInteger(id) || id < 0) { throw Error("invalid tile ID"); }
    var z = 0;
    for (; z < 26 && id >= (4 ** (z + 1) - 1) / 3; z++) {}
    var t = id - (4 ** z - 1) / 3, x = 0, y = 0;
    if (t >= 4 ** z) { throw Error("invalid tile ID"); }
    for (var side = 1; side < 2 ** z; side *= 2) {
        var rx = Math.floor(t / 2) & 1, ry = (t % 2) ^ rx;
        if (!ry) {
            if (rx) { x = side - 1 - x; y = side - 1 - y; }
            var swap = x; x = y; y = swap;
        }
        x += side * rx; y += side * ry; t = Math.floor(t / 4);
    }
    return [z, x, y];
}
function writePack(tiles) {
    var ids = Array.from(tiles.keys()).sort(function (a, b) { return a - b; });
    if (!ids.length || ids.length > 85) { throw Error("a pack needs 1–85 tiles"); }
    var dir = [], previous = 0, size = 0, low = 26, high = 0;
    var west = 180, east = -180, south = 90, north = -90;
    function vint(value) {
        for (; value >= 128; value = Math.floor(value / 128)) { dir.push((value % 128) | 128); }
        dir.push(value);
    }
    function lat(y, z) { return Math.atan(Math.sinh(Math.PI * (1 - 2 * y / 2 ** z))) * 180 / Math.PI; }
    // Python round uses ties to even, including negative coordinates.
    function rounded(v) { var n = Math.floor(v); return v - n === 0.5 ? n + (n % 2 !== 0 ? 1 : 0) : Math.round(v); }
    vint(ids.length);
    ids.forEach(function (id) {
        var tile = xyz(id), z = tile[0], x = tile[1], y = tile[2], body = tiles.get(id);
        if (!(body instanceof ArrayBuffer) || body.byteLength < 8) { throw Error("invalid tile bytes"); }
        vint(id - previous); previous = id; size += body.byteLength;
        low = Math.min(low, z); high = Math.max(high, z);
        west = Math.min(west, x / 2 ** z * 360 - 180); east = Math.max(east, (x + 1) / 2 ** z * 360 - 180);
        north = Math.max(north, lat(y, z)); south = Math.min(south, lat(y + 1, z));
    });
    ids.forEach(function () { vint(1); });
    ids.forEach(function (id) { vint(tiles.get(id).byteLength); });
    ids.forEach(function (_, i) { vint(i ? 0 : 1); });
    var data = 129 + dir.length, bytes = new Uint8Array(data + size), view = new DataView(bytes.buffer);
    bytes.set([80, 77, 84, 105, 108, 101, 115, 3]);
    [127, dir.length, 127 + dir.length, 2, data, 0, data, size, ids.length, ids.length, ids.length].forEach(function (v, i) {
        view.setBigUint64(8 + i * 8, BigInt(v), true);
    });
    bytes.set([1, 1, 1, 2, low, high], 96);
    [west, south, east, north].forEach(function (v, i) { view.setInt32(102 + i * 4, rounded(v * 1e7), true); });
    bytes[118] = low;
    view.setInt32(119, rounded((west + east) * 5e6), true); view.setInt32(123, rounded((south + north) * 5e6), true);
    bytes.set(dir, 127); bytes.set([123, 125], 127 + dir.length);
    ids.forEach(function (id) { var body = new Uint8Array(tiles.get(id)); bytes.set(body, data); data += body.length; });
    return bytes.buffer;
}
function merge(body, added) {
    var tiles = new Map();
    if (body) {
        var pack = unpack(body);
        pack.entries.forEach(function (_, id) { tiles.set(id, sliceTile(pack, id)); });
    }
    added.forEach(function (bytes, id) { tiles.set(id, bytes); });
    return writePack(tiles);
}
function row(body, kept, complete, url) {
    var at = Date.now(), result = {pack: body, kept: kept, complete: complete, at: at, size: body.byteLength};
    // Index keys carry bytes: deletion never reads the archive or a side row.
    if (kept) { result.keptAt = [url, result.size]; }
    else { result.browsedAt = [at, result.size]; }
    return result;
}
function upgrade(db, tx) {
    if (db.objectStoreNames.contains('browse')) { db.deleteObjectStore('browse'); }
    if (db.objectStoreNames.contains('packs')) { db.deleteObjectStore('packs'); }
    var store = db.createObjectStore('packs');
    store.createIndex('browsed-at', 'browsedAt'); store.createIndex('kept', 'keptAt');
    var flags = tx.objectStore('flags');
    flags.delete('held'); flags.delete('stand'); flags.delete('browse-bytes');
    flags.delete(IDBKeyRange.bound('browse-size:', 'browse-size:\uffff'));
}
function prefix(url) { return url.replace(/\d+\/\d+\/\d+\.pmtiles$/, ''); }
function account(held, browse, url, old, made) {
    var partKey = prefix(url), layers = held.layers || (held.layers = {});
    var part = layers[partKey] || {packs: 0, bytes: 0};
    [old, made].forEach(function (r, i) {
        if (!r) { return; }
        var sign = i ? 1 : -1;
        if (r.kept) { held.packs += sign; held.bytes += sign * r.size; part.packs += sign; part.bytes += sign * r.size; }
        else { browse.bytes += sign * r.size; }
    });
    if (part.packs) { layers[partKey] = part; } else { delete layers[partKey]; }
    if (!held.packs) { held.top = 0; }
}
function totals(tx, done) {
    var flags = tx.objectStore('flags'), held = flags.get('held'), browse = flags.get('browse-bytes');
    browse.onsuccess = function () { done(held.result || {packs: 0, bytes: 0, top: 0}, browse.result || {bytes: 0, writes: 0}); };
}
function saveTotals(tx, held, browse) {
    tx.objectStore('flags').put(held, 'held'); tx.objectStore('flags').put(browse, 'browse-bytes');
}
function put(open, url, body, top) {
    unpack(body);
    return new Promise(function (done, fail) {
        var tx = open.transaction(['packs', 'flags'], 'readwrite'), store = tx.objectStore('packs');
        totals(tx, function (held, browse) {
            var ask = store.get(url);
            ask.onsuccess = function () {
                var made = row(body, true, true, url);
                account(held, browse, url, ask.result, made); held.top = Math.max(held.top, top);
                store.put(made, url); saveTotals(tx, held, browse);
            };
        });
        tx.oncomplete = function () { done(); }; tx.onabort = tx.onerror = function () { fail(tx.error); };
    });
}
// Explicit Forget (or an old stand) visits only kept index keys, fifty per transaction.
async function forget(open, tree) {
    var more = true;
    for (; more;) {
        more = await new Promise(function (done, fail) {
            var tx = open.transaction(['packs', 'flags'], 'readwrite'), store = tx.objectStore('packs'), removed = 0;
            totals(tx, function (held, browse) {
                var bounds = tree ? IDBKeyRange.bound([tree], [tree + '\uffff']) : null;
                var ask = store.index('kept').openKeyCursor(bounds);
                ask.onsuccess = function () {
                    var cursor = ask.result;
                    if (!cursor || removed === 50) { saveTotals(tx, held, browse); return; }
                    account(held, browse, cursor.primaryKey, {kept: true, size: cursor.key[1]}, null);
                    store.delete(cursor.primaryKey); removed++;
                    if (removed === 50) { saveTotals(tx, held, browse); } else { cursor.continue(); }
                };
            });
            tx.oncomplete = function () { done(removed === 50); };
            tx.onabort = tx.onerror = function () { fail(tx.error); };
        });
    }
}
// Keep replaces incomplete archives; the worker alone reads tile ranges.
async function complete(row, request) {
    if (row && row.complete) { return row.pack; }
    var answer = await request();
    if (!answer) { return answer; }
    if (!answer.ok || answer.status !== 200) { throw Error('whole pack request failed'); }
    var body = await answer.arrayBuffer();
    unpack(body);
    return body;
}
return {tileId: tileId, header: packHeader, directory: packDirectory, unpack: unpack, slice: sliceTile,
    write: writePack, merge: merge, row: row, upgrade: upgrade, account: account, totals: totals,
    saveTotals: saveTotals, put: put, forget: forget, complete: complete};
})();

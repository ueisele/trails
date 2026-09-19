__PACK_IO__
// The map's service worker. Written by the build, stamped with the page it was
// built beside, so a deploy is a new worker and an unchanged page is not.
//
// **What it is for.** The document is served with `max-age=300`, so five minutes
// after a visit the browser must revalidate -- and offline a revalidation fails,
// which means the map does not open at all. Everything else it needs is already
// in it: measured, selecting a chain and reading its whole elevation profile
// costs zero requests, and so does routing, because the Dijkstra is in the page.
var VERSION = "__VERSION__";

// **The document and the switch live in a database, not in a cache.** Measured
// on an installed app: the first `caches.open()` of *any* cache costs 23.2 s once
// the terrain cache holds tens of thousands of tiles, and 11 ms with the store
// empty -- same device, same page, one variable. The first touch pays for the
// whole origin, and answering a navigation needs exactly two things, the page and
// the flag, both of which used to be in there.
//
// So they are here instead: one file rather than a hundred thousand. The tiles
// stay in the cache for now, which means the first tile still pays -- but it
// pays after the map is on the screen rather than in front of a black one.
//
// The digest still names the worker, which is what makes a deploy install one --
// it is no longer a cache name, and `sweepOldCaches` takes the caches that were.
var DB = "__DB__";
// **One number, and the page carries the same one written out.** They are two
// scripts and cannot share a constant; what they must not do is disagree. A
// connection held at an older version blocks an upgrade, and with no `onblocked`
// the other side waits for ever -- measured on this suite, the page opened the
// database at 1 while the worker asked for 2 and a navigation never answered at
// all. The app would not have opened. There is a test that the two literals
// match, because nothing else would notice.
var DB_AT = 6;
var PAGES = "pages";
var FLAGS = "flags";
// One archive row per address. Its kept flag makes the storage promise;
// only browse rows carry the eviction index key.
var KEPT = "packs";

var opened = null;

function base() {
    if (opened) { return opened; }
    opened = new Promise(function (done, fail) {
        var ask = indexedDB.open(DB, DB_AT);
        // Said rather than waited on: blocked means somebody else is holding an
        // older connection, and hanging is the one answer that helps nobody.
        ask.onblocked = function () { fail(new Error("the database is blocked")); };
        ask.onupgradeneeded = function (event) {
            var made = ask.result;
            if (event.oldVersion < 5) {
                if (!made.objectStoreNames.contains(PAGES)) { made.createObjectStore(PAGES); }
                if (!made.objectStoreNames.contains(FLAGS)) { made.createObjectStore(FLAGS); }
                if (made.objectStoreNames.contains("tiles")) {
                    made.deleteObjectStore("tiles");
                    ask.transaction.objectStore(FLAGS).delete("held");
                }
                PackIO.upgrade(made, ask.transaction);
            }
            if (made.objectStoreNames.contains("bench")) { made.deleteObjectStore("bench"); }
        };
        ask.onsuccess = function () {
            var open = ask.result;
            // **Let go when the other side wants to upgrade.** This is what keeps
            // the deadlock above from being possible at all rather than merely
            // reported: a connection that steps aside cannot block anything.
            open.onversionchange = function () { open.close(); opened = null; };
            done(open);
        };
        ask.onerror = function () { fail(ask.error); };
    });
    return opened;
}

function read(store, key) {
    return base().then(function (open) {
        return new Promise(function (done, fail) {
            var ask = open.transaction(store, "readonly").objectStore(store).get(key);
            ask.onsuccess = function () { done(ask.result === undefined ? null : ask.result); };
            ask.onerror = function () { fail(ask.error); };
        });
    }).catch(function () { return null; });
}

function write(store, key, value) {
    return base().then(function (open) {
        return new Promise(function (done, fail) {
            var deal = open.transaction(store, "readwrite");
            deal.objectStore(store).put(value, key);
            deal.oncomplete = function () { done(true); };
            deal.onerror = function () { fail(deal.error); };
        });
    }).catch(function () { return false; });
}

// **The headers travel with the body.** A cache kept the whole `Response`; a row
// keeps a blob, so what the response said about itself has to be written down
// beside it. `last-modified` is not decoration here: it is the entire basis on
// which a newer map is recognised.
function rowFor(answer) {
    return answer.clone().blob().then(function (body) {
        var headers = [];
        answer.headers.forEach(function (value, name) { headers.push([name, value]); });
        return {version: VERSION, body: body, headers: headers, at: Date.now()};
    });
}

function responseFrom(row) {
    return new Response(row.body, {headers: row.headers});
}

function headerOf(row, name) {
    var found = null;
    (row.headers || []).forEach(function (pair) {
        if (pair[0].toLowerCase() === name) { found = pair[1]; }
    });
    return found;
}

// **Two tile caches, because they are two different promises.** `TILES` is what
// the reader happened to look at, kept opportunistically and trimmed to the last
// `TILE_CAP`. `TERRAIN` is what they *asked* to keep, and is never trimmed: a
// deliberate nine-hundred-tile download into an LRU of five hundred would evict
// itself on the way in, and the reader would be told it had worked.
var TILES = "__CACHE__-tiles";
var TERRAIN = "__CACHE__-terrain";

// Bytes, not rows: coarse and fine tiles have very different weights.
var TILE_CAP = 150 * 1000 * 1000;
// What a tile's address starts with -- the provider's server, or our own
// bucket's prefix resolved against this worker's origin. Injected per map.
var TILE_PREFIX = new URL("__TILE_PREFIX__", self.location.href).href;
// And what a height tile's starts with, where the map has them: Lantmäteriet's
// map does, Kartverket's does not. Kept beside the map tiles, under the same
// switch, because a route planned offline reads its straight legs off them.
// Empty where there are none, and then nothing here matches.
var HEIGHT_PREFIX = "__HEIGHT_PREFIX__" ? new URL("__HEIGHT_PREFIX__", self.location.href).href : null;
// And what a hillshade tile's address starts with, where the map has them. The
// relief overlay is kept with the map tiles and under the same switch, because
// a sheet answered from the store with no shadow over it would look like the
// download had half failed.
var SHADE_PREFIX = "__SHADE_PREFIX__" ? new URL("__SHADE_PREFIX__", self.location.href).href : null;
// And a slope-class tile's, kept with the others for the same reason: a
// reader who switched the classes on and then lost the connection would
// otherwise see them stop at the edge of the last view.
var SLOPE_PREFIX = "__SLOPE_PREFIX__" ? new URL("__SLOPE_PREFIX__", self.location.href).href : null;
// And the vegetation and forest tiles', kept with the others on the same terms.
var VEGETATION_PREFIX = "__VEGETATION_PREFIX__" ? new URL("__VEGETATION_PREFIX__", self.location.href).href : null;
var FOREST_PREFIX = "__FOREST_PREFIX__" ? new URL("__FOREST_PREFIX__", self.location.href).href : null;
// And the mire tiles' (§6.13), likewise.
var MIRE_PREFIX = "__MIRE_PREFIX__" ? new URL("__MIRE_PREFIX__", self.location.href).href : null;

// **Where the offline switch is kept, and why it is kept at all.** A service
// worker is not a process that stays alive: the browser starts it for a fetch
// and stops it again, and every variable it held goes with it. A flag that lived
// only in this scope would be true on the first tile of a walk and false on the
// second. So it is one entry in a cache, read once and memoised, and the memo is
// dropped when the page says the switch has moved.
//
// **In a cache of its own, holding two small entries and nothing else.** It used
// to live beside the tiles, which reads well and cost twenty seconds. Measured on
// an installed app with the ground kept: the worker held the navigation for
// **20.8 s** before the response began, and every tile after it was quick -- 22
// of them, 2.1 s in all, worst 162 ms. Reading the flag is the first thing
// `pageFor` does, so it paid the cold open of a Cache Storage holding tens of
// thousands of entries and several gigabytes, once, in front of the reader; by
// the time tiles were asked for it was warm.
//
// So nothing on the way to answering a navigation may open `TERRAIN` any more.
// The panel's own record of what is kept lives here for the same reason.
var STATE = "offline";
var TIMING = "timing";
var TILES_SAID = "tiles-said";
var switched = null;

// A tile that is not kept, while the switch is on: a 1x1 transparent PNG,
// answered 200 rather than refused, so Leaflet draws the page's own ground
// instead of a broken image over it.
var BLANK = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII=";

self.addEventListener("install", function () {
    // Nothing is precached from a list. The worker does not know what the map is
    // called: the object is `lomsdal-visten.html` in the bucket and is served at
    // `/lomsdal-visten`, and a cache keyed on the wrong one of those two answers
    // nothing. What is open is what is kept -- see `keepWhatIsOpen`.
    self.skipWaiting();
});

// **Filled first, and swept only once it can stand alone.** This ran the other
// way round: delete every superseded page cache, then fetch the open page into
// this worker's own. Both halves of that are allowed to fail, and on a dying
// signal the failing half is the second -- so it deleted the copy the reader was
// standing on and put nothing back, leaving a worker holding nothing over a map
// that had been there a minute earlier.
//
// A half-done update now leaves two page caches instead of none. That is
// bounded -- each is one superseded copy of one document, and the next good
// activation takes both -- and it is much the cheaper mistake.
self.addEventListener("activate", function (event) {
    event.waitUntil(
        self.clients.claim().then(keepWhatIsOpen).then(sweepOldCaches)
    );
});

// **Everything earlier versions wrote to a cache, which is now all of it.** A
// deploy used to mint a cache named after the page's digest and hold 15.7 MB in
// it, and the ground was kept in two more. Nothing here reads a cache any longer,
// so what is left is unreachable -- gigabytes on a phone that no code can answer
// from, which is worse than deleting them.
//
// **Swept on activation, which is after the navigation has been answered.** The
// one thing this must not do is happen in front of somebody: `caches.keys()` is
// the call measured at 23 seconds on a phone with the ground kept.
var CAST_OFF = new RegExp("^__CACHE__-(page-|state$|terrain$|tiles$)");
function sweepOldCaches() {
    return caches.keys().then(function (names) {
        return Promise.all(names.map(function (name) {
            return CAST_OFF.test(name) ? caches.delete(name) : null;
        }));
    }).catch(function () { return null; });
}


// **Keep the page that is open, by the address it was opened at.**
//
// Without this the map is not in the cache until the *second* visit -- the first
// registers a worker that was not there to intercept it -- and offline would
// therefore work from the third. Asking for it again is very nearly free: it was
// loaded seconds ago and is served `max-age=300`, so the browser's own cache
// answers. If it does not, one extra fetch buys a map that opens without a
// network, which is the whole point.
function keepWhatIsOpen() {
    return self.clients.matchAll({type: "window"}).then(function (open) {
        return Promise.all(open.map(function (client) {
            return read(PAGES, client.url).then(function (row) {
                if (row) { return null; }
                return fetch(client.url).then(function (answer) {
                    if (!answer || !answer.ok) { return null; }
                    return rowFor(answer).then(function (made) {
                        return write(PAGES, client.url, made);
                    });
                }).catch(function () { return null; });
            });
        }));
    }).catch(function () { return null; });
}

function tell(what, more) {
    return self.clients.matchAll().then(function (open) {
        open.forEach(function (client) {
            var said = {trails: what}, key;
            for (key in more || {}) {
                if (Object.prototype.hasOwnProperty.call(more, key)) { said[key] = more[key]; }
            }
            client.postMessage(said);
        });
    });
}

// Whether the switch is on, from the cache the first time and from the memo
// after that. It answers false for every failure, because a worker that cannot
// read its own flag should go to the network rather than draw a blank park.
function offlineNow() {
    if (switched === null) {
        switched = read(FLAGS, STATE).then(function (kept) {
            return kept === "on";
        }).catch(function () { return false; });
    }
    return switched;
}

function setOffline(on) {
    switched = Promise.resolve(!!on);
    return write(FLAGS, STATE, on ? "on" : "off");
}

self.addEventListener("message", function (event) {
    var said = event.data || {};
    if (said.trails === "check") {
        event.waitUntil(askForNewer(said.mark));
        return;
    }
    if (said.trails === "take") {
        event.waitUntil(takeNewer());
        return;
    }
    if (said.trails === "packs-changed") {
        clearPacks();
        if (event.ports[0]) { event.ports[0].postMessage(true); }
        return;
    }
    if (said.trails !== "offline") { return; }
    event.waitUntil(setOffline(said.on).then(function () {
        if (event.source) { event.source.postMessage({trails: "offline", on: !!said.on}); }
    }));
});

// The page as it is held, and the address it was kept under. A row keyed by
// that address, so this is one read where it used to be a listing and a match.
function heldPage() {
    return self.clients.matchAll({type: "window"}).then(function (open) {
        var url = open.length ? open[0].url : null;
        if (!url) { return null; }
        return read(PAGES, url).then(function (row) {
            return row ? {url: url, row: row} : null;
        });
    }).catch(function () { return null; });
}

// **Asked for, and only when asked.** The only other thing that notices a new
// map is `pageFor`, and it runs on a navigation -- so a reader learns there is
// one by reloading, which is the very thing they were going to be told to do.
// Installed to a home screen there is no reload control at all. And with the
// switch on `pageFor` does not go to the network, so the reader most likely to
// be carrying a stale map is the one who can never hear about a new one.
//
// **Nothing here runs on its own any more.** This was wired to
// `visibilitychange`, and a rule nobody invoked that spends bytes on a phone in
// a tent is the thing the offline switch exists to prevent. What replaced it is
// a panel that says how old the map is and a button that asks -- so the page in
// the foreground touches the network never, which is a property that can be
// measured rather than a budget one hopes to have stayed inside.
//
// **A HEAD, and nothing else.** The page is 5.2 MB over the wire, and the body
// is now the reader's decision: what comes back from this is a size to quote
// them before they spend it.
function askForNewer(mark) {
    return heldPage().then(function (both) {
        if (!both) { return null; }
        return fetch(both.url, {method: "HEAD", cache: "reload"}).then(function (head) {
            if (!head || !head.ok) { return tell("checked", {failed: true, newer: false, bytes: null}); }
            return tell("checked", {
                failed: false,
                newer: newerThanShown(mark, both.row, head),
                bytes: Number(head.headers.get("content-length")) || null
            });
        });
    }).catch(function () { return tell("checked", {failed: true, newer: false, bytes: null}); });
}

// **The question is about the page on the screen and not about the cache.**
// Reported from the phone: *check for a newer map* answered that the map was up
// to date while the reader was looking at the old one -- and it was telling the
// truth about the wrong thing. `pageFor` writes the fresh body *behind* the
// answer it serves, so one visit after a publish leaves the cache holding the
// new map and the screen showing the old, and a comparison made against the
// cache then says there is nothing to do. There was: reload.
//
// The page hands in its own identity, which is `document.lastModified` and is
// exact through the worker -- measured on the published page, where it carries
// the header and not the moment it was drawn. Compared as instants rather than
// as strings, because one of the two is an HTTP date and the other is whatever
// the browser writes locally.
//
// The cache is still compared where the page cannot say: a worker woken with no
// page to ask, or a server that sends an etag and no `last-modified`.
function newerThanShown(mark, row, head) {
    var said = Date.parse(head.headers.get("last-modified"));
    if (mark && said && !isNaN(said)) { return said > mark; }
    return movedFrom(row, head);
}

// **The body, because the reader asked for it.** The HEAD runs again rather
// than being trusted from a minute ago: with the switch off `pageFor` may have
// taken the new page in between, and the reload would then have spent 5.2 MB
// arriving at what was already in the cache.
function takeNewer() {
    return heldPage().then(function (both) {
        if (!both) { return tell("taken"); }
        return fetch(both.url, {method: "HEAD", cache: "reload"}).then(function (head) {
            if (!head || !head.ok) { return tell("stuck"); }
            if (!movedFrom(both.row, head)) { return tell("taken"); }
            return fetch(both.url, {cache: "reload"}).then(function (answer) {
                if (!answer || !answer.ok) { return tell("stuck"); }
                return rowFor(answer).then(function (made) {
                    return write(PAGES, both.url, made);
                }).then(function () { return tell("taken"); });
            });
        });
    }).catch(function () { return tell("stuck"); });
}

function blank() {
    var raw = atob(BLANK), bytes = new Uint8Array(raw.length), i;
    for (i = 0; i < raw.length; i += 1) { bytes[i] = raw.charCodeAt(i); }
    // **A 200 and not a refusal**, so Leaflet draws the page's own ground rather
    // than a broken image over it. `cache-control: no-store` was tried here and
    // does not keep the browser's image cache from holding it -- measured -- so
    // what makes a blank tile askable again is the token on the sheet's URL.
    return new Response(bytes, {status: 200, headers: {"content-type": "image/png"}});
}

// Whether two answers are the same map. The object carries `last-modified` and
// no etag -- measured on the published page -- so that is what is compared, and
// an answer carrying neither is treated as unchanged rather than as news.
function moved(was, now) {
    return !!(was && now && was !== now);
}

function movedFrom(row, fresh) {
    return moved(
        headerOf(row, "last-modified") || headerOf(row, "etag"),
        fresh.headers.get("last-modified") || fresh.headers.get("etag")
    );
}

// **Stale first, and the network behind it.** The reader gets the map they
// already have, immediately and at no bytes; the new one lands in the cache for
// the next visit and the page is told there is one. With the switch on there is
// no network behind it at all: a reader who asked for offline did not ask for a
// request that will hang until it times out.
// **Timed from the inside, because the outside could not see it.** The page's
// own account said `worker 20.8 s` and could say no more: `workerStart` to
// `responseStart` is one number covering everything this function does. These
// three say which part, and they are written to the small cache rather than
// posted, because a navigation is answered before any page is listening.
function pageFor(request) {
    var began = Date.now(), open = 0, matched = 0;
    return base().then(function () {
        open = Date.now() - began;
        return read(PAGES, request.url);
    }).then(function (row) {
        matched = Date.now() - began - open;
        return offlineNow().then(function (off) {
            var flag = Date.now() - began - open - matched;
            write(FLAGS, TIMING, {open: open, match: matched, flag: flag, total: Date.now() - began});
            var kept = row ? responseFrom(row) : null;
            if (off && kept) { return kept; }
            var fresh = fetch(request).then(function (answer) {
                if (answer && answer.ok) {
                    // **Written before anything is thrown away**, which here is
                    // free: a row keyed by address is replaced in place, so there
                    // is no window in which the reader has neither copy. That was
                    // a whole dance when this was a cache named after a digest.
                    rowFor(answer).then(function (made) { return write(PAGES, request.url, made); });
                    if (row && movedFrom(row, answer)) { tell("newer"); }
                }
                return answer;
            }).catch(function (failure) {
                if (kept) { return kept; }
                throw failure;
            });
            return kept || fresh;
        });
    });
}

// **What the tiles did, because a blank says nothing about why.** Every path
// out of `tileFor` ends in an image, and three of the four are indistinguishable
// on the screen: a tile from the database, one from the old cache and one from
// the network all just appear, and a blank just does not. Shipped without this,
// the ground stopped appearing at all and there was no way to ask where it had
// gone. Written to the same small row the navigation timings use, at most once a
// second, so a hundred thousand tiles do not become a hundred thousand writes.
var told = {mem: 0, db: 0, seen: 0, legacy: 0, net: 0, blank: 0, why: null, at: 0};
told.time = {
    mem: {total: 0, worst: 0},
    db: {total: 0, worst: 0}, seen: {total: 0, worst: 0},
    net: {total: 0, worst: 0}, blank: {total: 0, worst: 0}
};
told.deadlines = 0;
told.peak = 0;
var inFlight = 0;

var telling = null;

function tally(which, why, began) {
    told[which] += 1;
    var spent = performance.now() - began;
    told.time[which].total += spent;
    told.time[which].worst = Math.max(told.time[which].worst, spent);
    if (why && !told.why) { told.why = String(why).slice(0, 120); }
    // **And a trailing write, or the last second is never reported.** Throttled
    // alone, the row held whatever was true a second before the tiles stopped
    // arriving: a view of fifteen tiles was read back as one. The timer is only
    // ever armed while tiles are being answered.
    if (telling) { clearTimeout(telling); }
    telling = setTimeout(function () {
        telling = null;
        told.at = Date.now();
        write(FLAGS, TILES_SAID, told);
    }, 400);
    if (Date.now() - told.at < 1000) { return; }
    told.at = Date.now();
    write(FLAGS, TILES_SAID, told);
}

// **Never hangs, whatever the database does.** A read that does not answer used
// to leave `respondWith` unresolved, and an unresolved tile is one Leaflet waits
// on for ever -- which is the difference between a slow map and a blank one.
function within(ms, work, fallback, late) {
    return new Promise(function (done, fail) {
        var timer = setTimeout(function () { late(); done(fallback); }, ms);
        work.then(function (value) { clearTimeout(timer); done(value); },
            function (error) { clearTimeout(timer); fail(error); });
    });
}

// Zoom-then-Hilbert, the same integer algorithm as processing.packs.tile_id.
var tileId = PackIO.tileId;

var LAYERS = [[TILE_PREFIX, __TILE_TOP__], [HEIGHT_PREFIX, __HEIGHT_TOP__],
    [SHADE_PREFIX, __SHADE_TOP__], [SLOPE_PREFIX, __SLOPE_TOP__],
    [VEGETATION_PREFIX, __VEGETATION_TOP__], [FOREST_PREFIX, __FOREST_TOP__], [MIRE_PREFIX, __MIRE_TOP__]];
function packLevel(top, z) {
    return Math.max(0, top - 3 - 4 * Math.floor((top - z) / 4));
}

function packFor(plain) {
    var layer = LAYERS.find(function (entry) { return entry[0] && plain.indexOf(entry[0]) === 0; });
    if (!layer) { throw Error("unknown tile tree"); }
    var match = /^(\d+)\/(\d+)\/(\d+)\.png$/.exec(plain.slice(layer[0].length));
    if (!match) { throw Error("invalid tile path"); }
    var z = Number(match[1]), x = Number(match[2]), y = Number(match[3]), id = tileId(z, x, y);
    if (z > layer[1]) { throw Error("tile above layer top"); }
    var level = packLevel(layer[1], z);
    var prefix = new URL(layer[0]);
    prefix.pathname = '/packs' + prefix.pathname;
    return {url: prefix.href + level + '/' + (x >> (z - level)) + '/' + (y >> (z - level)) + '.pmtiles', id: id, tile: plain, height: layer[0] === HEIGHT_PREFIX};
}

// 48 directories are small (85 entries at most); bodies have a byte budget.
// Requests stay on ranges; idle time fills the recent screen whole.
// The phone may tune SETTLE_MS; all address and body caches stay bounded.
var DIRECTORY_LIMIT = 48, PACK_BYTES = 48 * 1000 * 1000, SETTLE_MS = 2000, FILL_LIMIT = 2;
var packBytes = 0, warmTransaction = null;
var directories = new Map(), packs = new Map(), opening = new Map(), filling = new Map();
function recent(cache, key) {
    var value = cache.get(key);
    if (value !== undefined) { cache.delete(key); cache.set(key, value); }
    return value;
}
function remember(cache, key, value, limit) {
    cache.delete(key); cache.set(key, value);
    if (cache.size > limit) { cache.delete(cache.keys().next().value); }
    return value;
}
function dropPack(url) {
    var held = packs.get(url);
    if (held) { packBytes -= held.body.byteLength; packs.delete(url); }
}
function clearPacks() { packs.clear(); packBytes = 0; }
var packHeader = PackIO.header, packDirectory = PackIO.directory;
function holdPack(url, body, network = true, complete = network) {
    var held = PackIO.unpack(body);
    held.complete = complete;
    if (network) { remember(directories, url, {entries: held.entries}, DIRECTORY_LIMIT); }
    dropPack(url);
    if (body.byteLength > PACK_BYTES) { return held; }
    for (; packs.size && packBytes + body.byteLength > PACK_BYTES;) { dropPack(packs.keys().next().value); }
    packs.set(url, held); packBytes += body.byteLength;
    return held;
}
var sliceTile = PackIO.slice;
function png(body) { return new Response(body, {headers: {'content-type': 'image/png'}}); }

// A 200 to a Range request is a whole pack, never bytes at the requested offset.
async function range(url, start, end) {
    var answer = await fetch(url, {headers: {Range: 'bytes=' + start + '-' + end}});
    if (!answer.ok || (answer.status !== 200 && answer.status !== 206)) { throw Error("pack HTTP " + answer.status); }
    var body = await answer.arrayBuffer();
    if (answer.status === 200) { return {whole: body}; }
    var match = /^bytes (\d+)-(\d+)\/(\d+)$/.exec(answer.headers.get('content-range') || '');
    if (!match || Number(match[1]) !== start || Number(match[2]) !== Math.min(end, Number(match[3]) - 1) ||
            body.byteLength !== Number(match[2]) - start + 1) { throw Error("invalid pack range"); }
    return {body: body};
}
function keepNetworkPack(url, body, event) {
    var pack = holdPack(url, body), kept = browsePut(url, body);
    if (event) { event.waitUntil(kept); }
    return pack;
}
// One resettable timer, and at most 48 addresses rather than one item per tile.
// Its promise is attached during the fetch event, keeping the worker alive through
// the idle window and the writes. A new request also stops an old fill queue.
var askedPacks = new Map(), settleTimer = null, settleWait = null, settleDone = null, requestGeneration = 0;
function notePack(address, event) {
    var asked = Date.now(), generation = ++requestGeneration;
    if (warmTransaction) { warmTransaction.abort(); warmTransaction = null; }
    remember(askedPacks, address.url, asked, DIRECTORY_LIMIT);
    if (settleTimer !== null) { clearTimeout(settleTimer); }
    if (!settleWait) { settleWait = new Promise(function (done) { settleDone = done; }); }
    if (event) { event.waitUntil(settleWait); }
    settleTimer = setTimeout(function () {
        var done = settleDone;
        settleTimer = null; settleWait = null; settleDone = null;
        fillRecent(asked, generation).catch(function () {}).finally(done);
    }, SETTLE_MS);
}
function packPriority(url) {
    var layer = LAYERS.findIndex(function (entry) {
        if (!entry[0]) { return false; }
        var prefix = new URL(entry[0]); prefix.pathname = '/packs' + prefix.pathname;
        return url.indexOf(prefix.href) === 0;
    });
    return layer === 1 ? -1 : layer;
}
async function fillRecent(asked, generation) {
    // A previous window may still have bodies in flight. Never start a second
    // pair alongside it, and never delay a tile's own range behind these bodies.
    await Promise.allSettled(Array.from(filling.values()));
    var urls = Array.from(askedPacks).filter(function (entry) {
        return entry[1] >= asked - SETTLE_MS && packPriority(entry[0]) >= 0;
    }).map(function (entry) { return entry[0]; }).sort(function (a, b) { return packPriority(a) - packPriority(b); });
    async function next(queue) {
        for (; queue.length && generation === requestGeneration;) {
            var url = queue.shift(), held = recent(packs, url);
            if (held && held.complete) { continue; }
            if (self.navigator.onLine === false || await offlineNow()) { return; }
            var row = await read(KEPT, url);
            if (row && row.complete) { continue; }
            if (self.navigator.onLine === false || await offlineNow() || generation !== requestGeneration) { return; }
            try { await wholePack(url); } catch (_) { /* A failed fill leaves its ranges available. */ }
        }
    }
    var sheet = urls.filter(function (url) { return packPriority(url) === 0; });
    var overlays = urls.filter(function (url) { return packPriority(url) > 0; });
    await Promise.all([next(sheet), next(sheet)]);
    await Promise.all([next(overlays), next(overlays)]);
    // Finish the screen's whole online packs before reading neighbours. Offline
    // next() does nothing, and this is the only work the settle undertakes.
    await warmRecent(urls, generation);
}
async function warmRecent(urls, generation) {
    if (generation !== requestGeneration) { return; }
    var open = await base();
    if (generation !== requestGeneration) { return; }
    // At most 48 windows of nine addresses; deduplicate overlapping windows.
    var neighbours = new Set();
    urls.forEach(function (url) {
        var match = /^(.*\/)(\d+)\/(\d+)\/(\d+)\.pmtiles$/.exec(url);
        if (!match || packPriority(url) < 0) { return; }
        var z = Number(match[2]), x = Number(match[3]), y = Number(match[4]);
        neighbours.add(url);
        for (var dy = -1; dy <= 1; dy += 1) {
            for (var dx = -1; dx <= 1; dx += 1) {
                if (x + dx >= 0 && y + dy >= 0 && x + dx < Math.pow(2, z) && y + dy < Math.pow(2, z)) {
                    neighbours.add(match[1] + z + '/' + (x + dx) + '/' + (y + dy) + '.pmtiles');
                }
            }
        }
    });
    if (!neighbours.size) { return; }
    return new Promise(function (done) {
        var tx = open.transaction(KEPT, 'readonly'), store = tx.objectStore(KEPT);
        warmTransaction = tx;
        var queue = neighbours.values(), reads = 0;
        function next() {
            for (var step = queue.next(); !step.done && reads < 32 && generation === requestGeneration; step = queue.next()) {
                // Already complete neighbours are part of this warm working set.
                // Refresh their LRU position before later gets can evict them.
                var url = step.value, held = recent(packs, url);
                if (held && held.complete) { continue; }
                reads += 1;
                var ask = store.get(url);
                ask.onsuccess = function () {
                    if (generation !== requestGeneration) { return; }
                    var row = ask.result;
                    if (row) { holdPack(url, row.pack, false, row.complete); }
                    next();
                };
                return;
            }
        }
        tx.oncomplete = tx.onabort = tx.onerror = function () {
            if (warmTransaction === tx) { warmTransaction = null; }
            done();
        };
        next();
    });
}
function wholePack(url) {
    if (!filling.has(url)) {
        if (filling.size >= FILL_LIMIT) { return null; }
        var work = fetch(url).then(function (answer) {
            if (!answer.ok) { throw Error("pack HTTP " + answer.status); }
            return answer.arrayBuffer();
        }).then(async function (body) {
            holdPack(url, body);
            await browsePut(url, body);
        }).finally(function () { filling.delete(url); });
        filling.set(url, work);
    }
    return filling.get(url);
}
function directoryFor(url, event) {
    var held = recent(directories, url);
    if (held) { return Promise.resolve(held.entries); }
    if (!opening.has(url)) {
        var work = range(url, 0, 16383).then(async function (part) {
            if (part.whole) { return keepNetworkPack(url, part.whole, event).entries; }
            var h = packHeader(part.body), root;
            if (h.root + h.rootLen <= part.body.byteLength) { root = part.body.slice(h.root, h.root + h.rootLen); }
            else {
                var more = await range(url, h.root, h.root + h.rootLen - 1);
                if (more.whole) { return keepNetworkPack(url, more.whole, event).entries; }
                root = more.body;
            }
            var entries = packDirectory(h, root);
            remember(directories, url, {entries: entries}, DIRECTORY_LIMIT);
            return entries;
        }).finally(function () { opening.delete(url); });
        opening.set(url, work);
    }
    return opening.get(url);
}
async function networkTile(address, event) {
    var url = address.url, held = recent(packs, url);
    if (held && held.entries.has(address.id)) { return sliceTile(held, address.id); }
    var entries = await directoryFor(url, event), pack = recent(packs, url);
    if (pack && pack.entries.has(address.id)) { return sliceTile(pack, address.id); }
    var entry = entries.get(address.id);
    if (!entry) { return null; }
    var part = await range(url, entry.offset, entry.offset + entry.length - 1);
    if (part.whole) { return sliceTile(keepNetworkPack(url, part.whole, event), address.id); }
    // Merge only the bytes bought by this range into the partial archive.
    // The first screen survives a cold visit without promoting any pack.
    var kept = browsePut(address.url, part.body, address.id);
    if (event) { event.waitUntil(kept); }
    return part.body;
}

var lookups = [], lookupTick = null;
function lookup(plain, state, tile) {
    return new Promise(function (done) {
        lookups.push({plain: plain, tile: tile, state: state, done: done});
        if (lookupTick === null) { lookupTick = setTimeout(flushLookups, 0); }
    });
}
function flushLookups() {
    var batch = lookups;
    lookups = []; lookupTick = null;
    base().then(function (open) {
        batch = batch.filter(function (item) { return !item.state.expired; });
        if (!batch.length) { return; }
        function readBatch(tx) {
            var pending = new Map();
            batch.forEach(function (item) {
                if (!pending.has(item.plain)) { pending.set(item.plain, []); }
                pending.get(item.plain).push(item);
            });
            pending.forEach(function (items, plain) {
                var ask = tx.objectStore(KEPT).get(plain);
                function answer(value) {
                    off.then(function (on) { items.forEach(function (item) { item.state.off = on; item.done(value); }); });
                }
                ask.onsuccess = function () {
                    if (items.every(function (item) { return item.state.expired; })) { return; }
                    var row = ask.result;
                    answer(row ? {body: row.pack, complete: row.complete, path: row.kept ? "db" : "seen"} : null);
                };
            });
            tx.onabort = tx.onerror = function () { batch.forEach(function (item) { item.done(null); }); };
        }
        var deal = open.transaction([KEPT, FLAGS], "readonly");
        var off = switched;
        if (!off) {
            switched = off = new Promise(function (done) {
                var ask = deal.objectStore(FLAGS).get(STATE);
                ask.onsuccess = function () { done(ask.result === "on"); };
                ask.onerror = function () { done(false); };
            });
        }
        // Start gets synchronously, before WebKit can commit an empty transaction.
        readBatch(deal);
        off.then(function (value) { batch.forEach(function (item) { item.state.off = value; }); });
    }).catch(function () { batch.forEach(function (item) { item.done(null); }); });
}

function tileFor(request, event) {
    var began = performance.now(), missed = false;
    inFlight += 1;
    told.peak = Math.max(told.peak, inFlight);
    var state = {expired: false, off: false};
    function late() {
        state.expired = true;
        if (!missed) { missed = true; told.deadlines += 1; }
    }
    function answered(which, why) { tally(which, why, began); }
    var plain = request.url.split("?")[0];
    var address;
    try { address = packFor(plain); }
    catch (error) { answered("blank", error); inFlight -= 1; return Promise.resolve(blank()); }
    notePack(address, event);
    if (switched) { switched.then(function (off) { state.off = off; }); }
    return Promise.resolve().then(function () {
        var held = recent(packs, address.url);
        if (held) {
            var body = sliceTile(held, address.id);
            if (body) { answered("mem"); return png(body); }
        }
        // The deadline bounds the store only; even a slow network answer is awaited below.
        return within(2500, lookup(address.url, state, plain), null, late).then(async function (found) {
            if (found) {
                var cached = recent(packs, address.url);
                var body = cached && sliceTile(cached, address.id);
                if (body) { answered("db"); return png(body); }
                // A locally completed archive has {} metadata; its offsets need not
                // match the bucket. Only network bodies seed the range directory.
                body = sliceTile(holdPack(address.url, found.body, false, found.complete), address.id);
                if (body) { answered(found.path); return png(body); }
            }
            // A concurrent request may have filled memory while this get ran.
            var cached = recent(packs, address.url), body = cached && sliceTile(cached, address.id);
            if (body) { answered("db"); return png(body); }
            var off = state.off;
            if (off) { answered("blank"); return blank(); }
            var body = await networkTile(address, event);
            answered(body ? "net" : "blank"); return body ? png(body) : blank();
        });
    }).catch(function (gone) { answered("blank", gone); return blank(); })
        .finally(function () { inFlight -= 1; });
}

var BROWSE_BYTES = "browse-bytes";
var puts = [], putTick = null;
function browsePut(plain, body, id) {
    return new Promise(function (done) {
        puts.push({plain: plain, body: body, id: id, done: done});
        if (putTick === null) { putTick = setTimeout(flushPuts, 0); }
    });
}
function flushPuts() {
    var batch = puts, grouped = new Map(), committed = new Map(), pruning = false;
    puts = []; putTick = null;
    batch.forEach(function (item) {
        var group = grouped.get(item.plain);
        if (!group) { group = {tiles: new Map(), body: null}; grouped.set(item.plain, group); }
        if (item.id === undefined) { group.body = item.body; }
        else { group.tiles.set(item.id, item.body); }
    });
    return base().then(function (open) {
        return new Promise(function (done, fail) {
            var deal = open.transaction([KEPT, FLAGS], "readwrite"), store = deal.objectStore(KEPT);
            PackIO.totals(deal, function (held, total) {
                var entries = grouped.entries();
                function next() {
                    var step = entries.next();
                    if (step.done) { PackIO.saveTotals(deal, held, total); return; }
                    var url = step.value[0], group = step.value[1], ask = store.get(url);
                    ask.onsuccess = function () {
                        try {
                            var old = ask.result, body = group.body || PackIO.merge(old && old.pack, group.tiles);
                            var made = PackIO.row(body, !!(old && old.kept), !!(group.body || (old && old.complete)), url);
                            PackIO.account(held, total, url, old, made); store.put(made, url);
                            remember(committed, url, made, 8);
                            if (!made.kept) { total.writes += 1; }
                            if (!made.kept && total.writes % 50 === 0) {
                                pruning = true;
                                trim(store, total, next, function (key) { committed.delete(key); });
                            }
                            else { next(); }
                        } catch (error) { deal.abort(); }
                    };
                }
                next();
            });
            deal.oncomplete = function () {
                committed.forEach(function (row, url) { holdPack(url, row.pack, false, row.complete); }); done();
            };
            deal.onabort = deal.onerror = function () { fail(deal.error); };
        }).then(function () { return pruning ? trimBrowse(open) : null; });
    }).catch(function () {}).finally(function () { batch.forEach(function (item) { item.done(); }); });
}
// Index keys contain [at, size] only for browse rows. At most fifty per transaction.
function trim(store, total, done, removedKey) {
    if (total.bytes <= TILE_CAP) { done(); return; }
    var removed = 0, walk = store.index("browsed-at").openKeyCursor();
    walk.onsuccess = function () {
        var at = walk.result;
        if (!at) { done(); return; }
        total.bytes -= at.key[1]; store.delete(at.primaryKey); dropPack(at.primaryKey);
        if (removedKey) { removedKey(at.primaryKey); }
        removed += 1;
        if (removed >= 50 || total.bytes <= TILE_CAP) { done(); }
        else { at.continue(); }
    };
}

// A large excess takes several short transactions, each bounded at fifty keys.
// Re-read totals between batches so concurrent Keep and browse commits are included.
async function trimBrowse(open) {
    var more = true;
    for (; more;) {
        more = await new Promise(function (done, fail) {
            var tx = open.transaction([KEPT, FLAGS], "readwrite"), again = false;
            PackIO.totals(tx, function (held, total) {
                var before = total.bytes;
                trim(tx.objectStore(KEPT), total, function () {
                    again = total.bytes > TILE_CAP && total.bytes < before;
                    PackIO.saveTotals(tx, held, total);
                });
            });
            tx.oncomplete = function () { done(again); };
            tx.onabort = tx.onerror = function () { fail(tx.error); };
        });
    }
}

self.addEventListener("fetch", function (event) {
    var request = event.request;
    if (request.method !== "GET") { return; }
    // The document, and only the document: `sw.js` is the one other thing at
    // this origin and the browser has its own rules about that one.
    if (request.mode === "navigate") {
        event.respondWith(pageFor(request));
        return;
    }
    // **A deliberate download passes straight through**, and this branch is not
    // an optimisation. The panel fetches what the reader asked to keep with
    // `cache: "reload"`; without this, a download begun while the switch was on
    // would be answered by the blank tile below and every one of those blanks
    // would be written into the terrain cache as terrain. The reader would be
    // told their park was kept, and it would be white.
    if (request.cache === "reload") { return; }
    if (request.url.indexOf(TILE_PREFIX) === 0 || (HEIGHT_PREFIX && request.url.indexOf(HEIGHT_PREFIX) === 0)
            || (SHADE_PREFIX && request.url.indexOf(SHADE_PREFIX) === 0)
            || (SLOPE_PREFIX && request.url.indexOf(SLOPE_PREFIX) === 0)
            || (VEGETATION_PREFIX && request.url.indexOf(VEGETATION_PREFIX) === 0)
            || (FOREST_PREFIX && request.url.indexOf(FOREST_PREFIX) === 0)
            || (MIRE_PREFIX && request.url.indexOf(MIRE_PREFIX) === 0)) {
        event.respondWith(tileFor(request, event));
    }
});

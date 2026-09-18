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
var DB_AT = 3;
var PAGES = "pages";
var FLAGS = "flags";
// **The ground, and what was merely looked at.** Two stores because they are two
// different promises: `KEPT` is what the reader asked for and is never trimmed,
// `SEEN` is what panning left behind and is held to `TILE_CAP`. A deliberate
// nine-hundred-tile download into an LRU of five hundred would evict itself on
// the way in and report success.
var KEPT = "tiles";
var SEEN = "browse";
// The stand is migrated once, not consulted after every kept-store miss.
var STAND = "stand";
var opened = null;

function base() {
    if (opened) { return opened; }
    opened = new Promise(function (done, fail) {
        var ask = indexedDB.open(DB, DB_AT);
        // Said rather than waited on: blocked means somebody else is holding an
        // older connection, and hanging is the one answer that helps nobody.
        ask.onblocked = function () { fail(new Error("the database is blocked")); };
        ask.onupgradeneeded = function () {
            var made = ask.result;
            if (!made.objectStoreNames.contains(PAGES)) { made.createObjectStore(PAGES); }
            if (!made.objectStoreNames.contains(FLAGS)) { made.createObjectStore(FLAGS); }
            if (!made.objectStoreNames.contains(KEPT)) { made.createObjectStore(KEPT); }
            if (!made.objectStoreNames.contains("bench")) { made.createObjectStore("bench"); }
            if (!made.objectStoreNames.contains(SEEN)) {
                // The index is what makes the trim cheap: oldest first, without
                // reading a row to find out how old it is.
                made.createObjectStore(SEEN).createIndex("at", "at");
            }
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
        self.clients.claim().then(function () {
            // Only the check is awaited; a kept-store walk continues in batches.
            stood = base().then(migrateStand);
            return stood;
        }).then(keepWhatIsOpen).then(sweepOldCaches)
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

// **Cache first, because terrain does not change while somebody walks over it.**
// What was asked for is looked at before what was merely seen, and with the
// switch on the network is not reached for at all -- which is what makes the
// switch worth having indoors: a reader can see exactly what they kept, instead
// of finding out in a valley.
// **Looked up without the query, and stored without it.** The page appends a
// token to the sheet's URL whenever the answer here would change -- see
// `restamp` -- because a browser holds an image by its address and will not ask
// again for one it has. Everything on this side is keyed on the tile itself, so
// a token that moves costs one lookup and no bytes: what was kept is still kept.
//
// Stripped rather than matched with `ignoreSearch`, which would turn every one of
// a hundred thousand keys into a comparison instead of a lookup.
// **Whether the old cache is still there, asked once and remembered.** Touching
// Cache Storage at all is what costs 23 seconds on a phone with the ground kept,
// so this is read from a row and not from `caches.has` -- and once the migration
// has run, nothing here goes near a cache again.
var legacy = null;

// **What the tiles did, because a blank says nothing about why.** Every path
// out of `tileFor` ends in an image, and three of the four are indistinguishable
// on the screen: a tile from the database, one from the old cache and one from
// the network all just appear, and a blank just does not. Shipped without this,
// the ground stopped appearing at all and there was no way to ask where it had
// gone. Written to the same small row the navigation timings use, at most once a
// second, so a hundred thousand tiles do not become a hundred thousand writes.
var told = {db: 0, seen: 0, legacy: 0, net: 0, blank: 0, why: null, at: 0};
told.time = {
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

function prefixOf(plain) {
    if (plain.indexOf(TILE_PREFIX) === 0) { return TILE_PREFIX; }
    if (HEIGHT_PREFIX && plain.indexOf(HEIGHT_PREFIX) === 0) { return HEIGHT_PREFIX; }
    if (SHADE_PREFIX && plain.indexOf(SHADE_PREFIX) === 0) { return SHADE_PREFIX; }
    if (SLOPE_PREFIX && plain.indexOf(SLOPE_PREFIX) === 0) { return SLOPE_PREFIX; }
    if (VEGETATION_PREFIX && plain.indexOf(VEGETATION_PREFIX) === 0) { return VEGETATION_PREFIX; }
    if (FOREST_PREFIX && plain.indexOf(FOREST_PREFIX) === 0) { return FOREST_PREFIX; }
    return null;
}

// The aliases match the page's stand and its kept-count record.
function prefixes() {
    return {map: TILE_PREFIX, tiles: TILE_PREFIX, height: HEIGHT_PREFIX, heights: HEIGHT_PREFIX,
        shade: SHADE_PREFIX, slope: SLOPE_PREFIX, vegetation: VEGETATION_PREFIX, forest: FOREST_PREFIX};
}

var stood = null, standCurrent = false, migrating = null;
var STAND_WALK = "stand-walk";
function sameStand(stand) {
    var now = prefixes();
    return !!stand && Object.keys(now).every(function (kind) { return Object.prototype.hasOwnProperty.call(stand, kind); }) &&
        Object.keys(Object.assign({}, stand, now)).every(function (kind) {
            return (stand[kind] || null) === (now[kind] || null);
        });
}

// Resolves after the stand check or its small flags-only update. The walk is
// deliberately detached: neither activation nor a tile waits for all the ground.
function migrateStand(open, was) {
    if (was === undefined) {
        return new Promise(function (done, fail) {
            var ask = open.transaction(FLAGS, "readonly").objectStore(FLAGS).get(STAND);
            ask.onsuccess = function () { migrateStand(open, ask.result || {}).then(done, fail); };
            ask.onerror = function () { fail(ask.error); };
        });
    }
    var now = prefixes();
    var moved = Object.keys(was).filter(function (kind) { return was[kind] && was[kind] !== now[kind]; });
    if (!moved.length) {
        return new Promise(function (done, fail) {
            var deal = open.transaction(FLAGS, "readwrite");
            deal.objectStore(FLAGS).put(now, STAND);
            deal.objectStore(FLAGS).delete(STAND_WALK);
            deal.oncomplete = function () { standCurrent = true; done(true); };
            deal.onabort = deal.onerror = function () { fail(deal.error || new Error("stand update aborted")); };
        });
    }
    if (!migrating) {
        migrating = walkStand(open, was, now, moved);
        migrating.then(function () { migrating = null; }, function () {
            migrating = null; stood = null; standCurrent = false;
        });
    }
    // Here current means checked this life: reads use the keys as they stand.
    standCurrent = true;
    return Promise.resolve(true);
}

// Each commit checkpoints at most 500 keys, also yielding after 50 ms of work
// on slow devices. No transaction is held between batches. A killed life resumes
// after its last committed key; an aborted batch retries its idempotent moves.
// Only renamed rows read blobs, and current ground wins every collision.
function walkStand(open, was, now, moved) {
    return new Promise(function (done, fail) {
        var lastKey = null;
        function batch() {
            var deal = open.transaction([KEPT, FLAGS], "readwrite");
            var store = deal.objectStore(KEPT), flags = deal.objectStore(FLAGS);
            var finished = false, visited = 0, began = performance.now();
            function walkFrom() {
                var walk = store.openKeyCursor(lastKey === null ? null : IDBKeyRange.lowerBound(lastKey, true));
                walk.onsuccess = function () {
                    var at = walk.result;
                    if (!at) {
                        finished = true;
                        var count = store.count();
                        count.onsuccess = function () {
                            var held = flags.get("held");
                            held.onsuccess = function () {
                                // Preserve the page's byte estimate, correct the count.
                                var value = held.result || {bytes: 0, top: 0};
                                value.tiles = count.result;
                                flags.put(value, "held");
                                flags.put(now, STAND);
                                flags.delete(STAND_WALK);
                            };
                        };
                        return;
                    }
                    var key = at.key;
                    visited += 1;
                    function next() {
                        lastKey = key;
                        if (visited >= 500 || performance.now() - began >= 50) {
                            flags.put({was: was, now: now, last: lastKey}, STAND_WALK);
                        } else { at.continue(); }
                    }
                    var kind = moved.find(function (name) { return key.indexOf(was[name]) === 0; });
                    var current = prefixOf(key);
                    if (!kind || (current && current.length >= was[kind].length)) { next(); return; }
                    if (!now[kind]) { store.delete(key); next(); return; }
                    var target = now[kind] + key.slice(was[kind].length);
                    var exists = store.getKey(target);
                    exists.onsuccess = function () {
                        if (exists.result !== undefined) { store.delete(key); next(); return; }
                        var body = store.get(key);
                        body.onsuccess = function () {
                            store.put(body.result, target);
                            store.delete(key);
                            next();
                        };
                    };
                };
            }
            if (lastKey === null) {
                var checkpoint = flags.get(STAND_WALK);
                checkpoint.onsuccess = function () {
                    var saved = checkpoint.result;
                    if (saved && JSON.stringify(saved.was) === JSON.stringify(was) && JSON.stringify(saved.now) === JSON.stringify(now)) {
                        lastKey = saved.last;
                    }
                    walkFrom();
                };
            } else { walkFrom(); }
            deal.oncomplete = function () {
                if (finished) { done(true); }
                else { setTimeout(batch, 0); }
            };
            deal.onabort = deal.onerror = function () { fail(deal.error || new Error("stand migration aborted")); };
        }
        setTimeout(batch, 0);
    });
}

var lookups = [], lookupTick = null;
function lookup(plain, state) {
    return new Promise(function (done) {
        lookups.push({plain: plain, state: state, done: done});
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
                if (item.state.expired) { return; }
                if (!pending.has(item.plain)) { pending.set(item.plain, []); }
                pending.get(item.plain).push(item);
            });
            pending.forEach(function (items, plain) {
                var ask = tx.objectStore(KEPT).get(plain);
                function answer(value) {
                    off.then(function () { items.forEach(function (item) { item.done(value); }); });
                }
                ask.onsuccess = function () {
                    if (ask.result) { answer({body: ask.result, path: "db"}); return; }
                    if (items.every(function (item) { return item.state.expired; })) { return; }
                    // Do not speculatively read a browse blob on a kept hit.
                    var seen = tx.objectStore(SEEN).get(plain);
                    seen.onsuccess = function () {
                        answer(seen.result && seen.result.body ? {body: seen.result.body, path: "seen"} : null);
                    };
                };
            });
            tx.onabort = tx.onerror = function () { batch.forEach(function (item) { item.done(null); }); };
        }
        // On iOS a life may be one fetch. Cold flags join this transaction,
        // rather than turning "once per life" into another transaction per tile.
        var deal = open.transaction([KEPT, SEEN, FLAGS], "readonly");
        var flags = deal.objectStore(FLAGS), ready = stood, off = switched, active = true;
        var currentInDeal = standCurrent && !!ready;
        deal.addEventListener("complete", function () { active = false; });
        deal.addEventListener("abort", function () { active = false; });
        // WebKit may commit an empty transaction before a promise callback,
        // before its complete event can clear active. Warm reads must start in
        // the task that created the transaction, with no promise in between.
        if (standCurrent && ready && off) {
            readBatch(deal);
        } else {
            if (!ready) {
                standCurrent = false;
                stood = ready = new Promise(function (done, fail) {
                    var ask = flags.get(STAND);
                    ask.onsuccess = function () {
                        if (sameStand(ask.result)) { standCurrent = currentInDeal = true; done(true); }
                        else { migrateStand(open, ask.result || {}).then(done, fail); }
                    };
                    ask.onerror = function () { fail(ask.error); };
                });
                // Only the check and flags-only update precede a lookup.
                // A walk runs in the background with the old stand still written.
                ready.catch(function () { stood = null; standCurrent = false; });
            }
            if (!off) {
                switched = off = new Promise(function (done) {
                    var ask = flags.get(STATE);
                    ask.onsuccess = function () { done(ask.result === "on"); };
                    ask.onerror = function () { done(false); };
                });
            }
            // Promise continuations from IDB request callbacks run before this
            // transaction becomes inactive. After a stand update, use a new one.
            ready.then(function () {
                // A checked stand from another transaction needs a fresh one.
                readBatch(currentInDeal && active ? deal : open.transaction([KEPT, SEEN], "readonly"));
            }).catch(function () { batch.forEach(function (item) { item.done(null); }); });
        }
        off.then(function (value) { batch.forEach(function (item) { item.state.off = value; }); });
    }).catch(function () { batch.forEach(function (item) { item.done(null); }); });
}

function tileFor(request, event) {
    var began = performance.now(), missed = false;
    inFlight += 1;
    told.peak = Math.max(told.peak, inFlight);
    var state = {expired: false, off: false};
    // Count a tile once over the entire lookup, including open and stand check.
    function late() {
        state.expired = true;
        if (!missed) { missed = true; told.deadlines += 1; }
    }
    function answered(which, why) { tally(which, why, began); }
    var plain = request.url.split("?")[0];
    // An already-known switch still governs a lookup whose database is stuck.
    if (switched) { switched.then(function (off) { state.off = off; }); }
    return within(2500, lookup(plain, state), null, late).then(function (found) {
        if (found) { answered(found.path); return new Response(found.body); }
        var off = state.off;
        if (off) { answered("blank"); return blank(); }
        return fetch(request).then(function (answer) {
            if (answer && answer.ok) {
                answered("net");
                var keeping = answer.clone().blob().then(function (body) { return browsePut(plain, body); });
                // iOS may stop us after answering this single fetch.
                if (event) { event.waitUntil(keeping); }
            }
            return answer;
        }).catch(function (gone) { answered("blank", gone); return blank(); });
    }).catch(function (gone) { answered("blank", gone); return blank(); })
        .finally(function () { inFlight -= 1; });
}

var BROWSE_BYTES = "browse-bytes", BROWSE_SIZE = "browse-size:";
var puts = [], putTick = null;
function browsePut(plain, body) {
    return new Promise(function (done) {
        puts.push({plain: plain, body: body, done: done});
        if (putTick === null) { putTick = setTimeout(flushPuts, 0); }
    });
}

function flushPuts() {
    var batch = puts;
    puts = []; putTick = null;
    base().then(function (open) {
        var deal = open.transaction([SEEN, FLAGS], "readwrite");
        var store = deal.objectStore(SEEN), flags = deal.objectStore(FLAGS);
        var ask = flags.get(BROWSE_BYTES);
        ask.onsuccess = function () {
            function put(total) {
                var i = 0;
                function next() {
                    if (i === batch.length) { flags.put(total, BROWSE_BYTES); return; }
                    var item = batch[i++], key = BROWSE_SIZE + item.plain;
                    // Metadata only, including on overwrite: no browse blob get.
                    var size = flags.get(key);
                    size.onsuccess = function () {
                        // The panel can clear browse; stale metadata must not
                        // subtract bytes for a row it has already removed.
                        var exists = store.getKey(item.plain);
                        exists.onsuccess = function () {
                            total.bytes += item.body.size - (exists.result === undefined ? 0 : (size.result || 0));
                            store.put({body: item.body, at: Date.now(), size: item.body.size}, item.plain);
                            flags.put(item.body.size, key);
                            total.writes += 1;
                            if (total.writes % 50 === 0) { trim(store, flags, total, next); }
                            else { next(); }
                        };
                    };
                }
                next();
            }
            var sizes = IDBKeyRange.bound(BROWSE_SIZE, BROWSE_SIZE + "\uffff");
            function reset() {
                // Browse is disposable. Rewriting old blobs can hold this
                // transaction past an iOS worker's life and repeat forever.
                store.clear();
                flags.delete(sizes);
                put({bytes: 0, writes: 0});
            }
            if (!ask.result) { reset(); return; }
            // All browse keys are URLs. Ask only whether one exists, never
            // count the store on a write. A page-side clear leaves flags.
            var first = store.getKey(IDBKeyRange.lowerBound(""));
            first.onsuccess = function () {
                if (first.result === undefined) {
                    flags.delete(sizes);
                    put({bytes: 0, writes: 0});
                    return;
                }
                var size = flags.getKey(sizes);
                size.onsuccess = function () {
                    if (size.result === undefined) { reset(); }
                    else { put(ask.result); }
                };
            };
        };
        deal.oncomplete = deal.onabort = deal.onerror = function () { batch.forEach(function (item) { item.done(); }); };
    }).catch(function () { batch.forEach(function (item) { item.done(); }); });
}

// Every fiftieth write above the byte budget, remove at most fifty oldest keys.
// Only index keys and small size records are read, never tile bodies.
function trim(store, flags, total, done) {
    if (total.bytes <= TILE_CAP) { done(); return; }
    var removed = 0, walk = store.index("at").openKeyCursor();
    walk.onsuccess = function () {
        var at = walk.result;
        if (!at) { total.bytes = 0; done(); return; }
        var key = BROWSE_SIZE + at.primaryKey, size = flags.get(key);
        size.onsuccess = function () {
            total.bytes -= size.result || 0;
            store.delete(at.primaryKey);
            flags.delete(key);
            removed += 1;
            if (removed >= 50) { done(); }
            else { at.continue(); }
        };
    };
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
            || (FOREST_PREFIX && request.url.indexOf(FOREST_PREFIX) === 0)) {
        event.respondWith(tileFor(request, event));
    }
});

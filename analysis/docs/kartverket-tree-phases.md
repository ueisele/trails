# Tiles that arrive fast, and Norway on our own tree: the phases

Written 2026-09-18 from a session that measured rather than changed. Nothing here is built
yet. The decisions it rests on are in §1; the figures they rest on are in §3, and every one
of them was measured on this box or on the published services on that date, so do not
re-derive them — re-measure them if they look wrong.

The complaint that started it: zooming *out* on the phone takes ten to twenty seconds before
the coarse tiles appear, while zooming in is quick, and the tiles are kept offline. The answer
turned out to be several things stacked, and fixing them properly leads to Norway leaving
Kartverket's cache for a tree of our own — which is what makes the two maps one case.

## 1. Decided

- **Every tile the page draws comes from our bucket.** Kartverket's cache is not addressed by
  the published page any more. Norway becomes what Sweden already is: a tree per sheet under
  `tiles/<provider>/<sheet>/<version>/{z}/{x}/{y}.png`, an `index.json` beside it, a stand, a
  `Provider.extent`, `bounds` on the sheet, and the same panel, worker, deploy and update path.
- **The edge keeps a tree tile as long as the object says.** Today the zone's cache rule
  throws every tile away after five minutes and asks R2 again (§3.6); the objects say a year.
  A rule for the tree paths respects them, Smart Tiered Cache and 0-RTT go on, and nothing is
  pre-warmed. Phase 0, in `home/trails-map`.
- **Norway is drawn without Kartverket's hillshade.** The relief is ours (§6.6 of the Abisko
  decisions) and today lies on top of a base that already carries a shadow — Lomsdal-Visten is
  shaded twice. The WMS behind the same map exposes the shadow as its own layer, `fjellskygge`,
  and drawing every other leaf layer without it gives the same cartography flat.
- **Palette PNG, 8-bit, for every base tile.** The same format Lantmäteriet ships and every
  other tree already uses. Not WebP: lossless WebP saves 10–25 %, lossy saves 30–40 % but is a
  quality change on line work and text, and either is a second format through the pipeline,
  the deploy, the worker and the page for a saving that does not change any decision.
- **z17 is the top for both countries.** z18 on Norway adds 1 m contours, spot heights and the
  smallest class of place names, at four times the tiles (24 GB of a 31 GB tree).
- **Both maps zoom to z18 on z17 tiles, and say so.** Today Abisko stops at z17 and
  Lomsdal-Visten draws real z18 tiles from the cache. After this both sheets carry
  `maxZoom: 18` with `maxNativeZoom: 17`: the last level is the z17 tiles drawn at twice the
  size, no new tile, no request — the same thing `fitNativeZoom` already does offline past
  the finest level kept. Uwe, 2026-09-18: it must be visible that this is no longer native
  zoom. The scale's zoom line keeps describing the *view* (it says `z18 · 0.25 m/px`, which is
  what the screen shows), and gains a mark whenever the view is above the sheet's native
  level — offline included, where today it is silent. The form is phase 6's to settle; the
  requirement is that a reader looking at magnified ground can tell.
- **The whole map may be kept to z17 on both maps**, once the store has been measured at the
  row count that implies (phase 1). Band, box and drawn scopes already go to the top.
- **Coarse ground is always kept.** The download floor stays a floor, but the whole box from
  z8 to z11 is part of every run, whatever the scope — a map that cannot be zoomed out of is
  not a map anybody navigates with, and it is a few megabytes.
- **Outside the box, nothing is asked for.** Every sheet carries `bounds` — the tree's box —
  so Leaflet never creates a tile there: no request, no worker lookup, no network, no 404.
  That is the fix for the 404 ring on both maps, and it is cheaper than any answer, including
  a transparent one, which would still cost a request through the worker and a round trip to
  the bucket on every first view of the ring in a session. Where a 404 can still happen — a
  tile missing inside the box, a tree half uploaded — the page sets `errorTileUrl` to a
  transparent 1 × 1 PNG so Leaflet draws the map's own background and not a broken image,
  and the worker keeps treating a 404 as *not there*: not written, not counted as refused
  (§9.13). Uwe, 2026-09-18: the default outside the box is a transparent tile — met here by
  not asking, and by the transparent error tile where asking was unavoidable.
- **The normal path is one lookup.** A tile the reader has kept, or has seen, is answered from
  one IndexedDB transaction; the network is reached only on a miss; what the network answers
  is written. That is what the worker means today; the phases below make it true.
- **No overlay is recut.** Relief, slope, vegetation and forest are cut from the height model
  and the laser, not from the base map. On the flat base the relief becomes what §6.6 measured
  it at, and the three multiplied overlays lighten to what Abisko shows.

## 2. How to work through them

The rules of `route-planning-phases.md` apply unchanged: one phase at a time, a review over
each, `command make hooks-run` green, anything touching the browser driven in one — and stop
at the end of a phase rather than starting the next. Phases 2–4 touch the page and the
worker; phases 5–7 touch the pipeline and the provider; the two halves do not overlap in the
files they edit and may be worked by different sessions, but each half in order.

**Nothing here changes the published maps until phase 6.** Phases 2–4 are improvements the
page can ship on their own, each measured before and after with the probe in §3.1.

**Phase S comes before phase 1 and shares a window with nothing.** It moves the JavaScript
out of `maps.py` without changing a byte of the built page, and it is what turns the two
streams above into more than two — after it, phases 1–4 sit in different files. It must not
run while another session is editing `maps.py`; the file changes in more than half of all
commits, and a rebase over a 20,000-line move is not a thing to attempt.

**Phase 0 is not in `trails` at all.** It is three settings in `home/trails-map`, laptop work
through `just plan-out` and `just apply-plan` (this box cannot apply there, and should not:
the bucket one can mistake is the one the maps come from). It touches no code and can go
first, alone, on any day.

**Order and parallelism, in one line.** 0 (laptop, any time) ∥ S → { 1 → 2 → 3 → 4 } ∥ 5 →
render and deploy → 6 → 7. After S, phases 1–4 may also overlap where they sit in different
files (1 and 3 in `worker.js`, 2 in the layer emitters, 4 in `offline_panel.js`), but each
is reviewed and landed on its own. Phase 1 stops for the phone: the two readings are Uwe's to
take, and phases 3 and 6 wait for them; phase 5 does not.

**How a phase is run when an agent runs it.** One `codex exec --worktree` per phase, as a
transient unit so it outlives the session that started it, with the phase's text and the
files it may touch in the prompt, and the rule that `maps.py` is read by region and never
whole. The worktree's branch exists only until review: rebased onto `main` and fast-forwarded,
so the history stays linear as the repository rule asks; parallel work is the reason for the
branch, and it is gone when the phase lands. Two files are off limits to any phase while
another session holds them dirty in the checkout — on 2026-09-18 that was
`analysis/docs/abisko-decisions.md` and `analysis/scripts/drive_map.py`. Review, hooks, the
drive and the landing are done by the reviewing session, not the building one. The agent's
model is on trial for cost (memory note of 2026-09-10); a run that begins to circle is stopped,
not paid for.

## 3. What was measured, and with what

### 3.1 Requests per zoom

Playwright Firefox, viewport 430 × 932, over the built page served locally, counting
`tileloadstart` per layer (`/tmp/zoomprobe/probe.py`, which will not survive a reboot; the
method is: `map._move(center, z, {pinch: true})` in steps of 0.1 from z15 to z10, then
`_moveEnd`, against `map.setZoom(10, {animate: false})`).

| Abisko | base sheet | relief |
|---|---|---|
| pinch z15 → z10 | 52 requests over five levels | 46 |
| direct jump z15 → z10 | 15 (6 of them 404, outside the box) | 9 |
| direct jump z10 → z15 | 10 | 10 |

Lomsdal-Visten: 49 against 15 on the sheet. The cause is Leaflet's `updateWhenZooming: true`
(`_setView` calls `_abortLoading` and `_update` at every integer level a pinch crosses), and
an aborted image does not stop the worker, whose `fetch` handler runs to completion. After a
zoom out of three levels or more nothing old stays on screen: `_pruneTiles` retains parents
five levels up and children two levels down, so a zoom *in* shows the old ground magnified
while a zoom *out* shows grey until the coarse tiles land.

### 3.2 What a tile costs in the worker today

From `abisko-sw.js` as built. A kept tile: one transaction. A tile that is not kept: a read
of the kept store, a read of the stand flag, a second read of the kept store under the old
prefix, a read of the browse store — then the network, and on an answer a write to the
browse store and a `trim` (a count and a cursor in a read-write transaction, which blocks
every read of that store in flight). Two deadlines of 4 s sit in front of that, and a read
that runs past one is not cancelled — it stays in the queue behind everything after it.
Zoomed out, most of the screen is outside the kept box, so the miss path is the common one.
The download floor is `BOTTOM = 11`; below it every tile is a miss by construction.

Not measured: what one WebKit transaction costs on the phone with 147,000 rows in the store.
The Sources panel counts tiles per path and records no time. Phase 1 adds the time.

### 3.3 The box, per zoom

Lomsdal-Visten's tree box, `TREES["lomsdal-visten"].box`, 12.0–13.75 E, 65.15–65.95 N:

| zoom | tiles | WMS palette PNG, per tile | per level | cumulative |
|---|---|---|---|---|
| z8–z15 | 37,915 | ~12 kB | 0.45 GB | 0.45 GB |
| z16 | 112,960 | ~9 kB | 1.0 GB | 1.5 GB |
| z17 | 449,790 | ~10.5 kB | 4.7 GB | 6.2 GB |
| z18 | 1,796,475 | ~13.6 kB | 24 GB | 31 GB |

Today's cache tiles weigh 3 to 9 times that (z10: 102 kB against 24 kB; z13: 68 kB against
15 kB), because the baked hillshade gives each tile 3,500–11,000 colours in 32-bit RGBA that
PNG cannot pack. The whole map to z16 from the cache is 6.76 GB; the same box to z17 from the
tree is about the same.

### 3.4 The WMS

`https://wms.geonorge.no/skwms1/wms.topo`, WMS 1.3.0, EPSG:3857, formats `image/png`,
`image/png8`, `image/jpeg`. The group `topo` holds 60 layers, 189 leaves; `fjellskygge` is the
hillshade and the only shadow-like layer. Rendering the 188 other leaves in capabilities
order gives the map without it. Scale-dependent visibility, computed from the WMS scale
denominator (projected metres per pixel over 0.28 mm): z17 switches on building outlines and
`tiltak`; z18 alone switches on `hoydekurver_1m`, `hoydepunkt`, `stedsnavn1punkt` and
`stedsnavn1linje`, and switches off the 5 m contours and the stedsnavn5 names. Looked at
side by side at Trofors, z17 and z18 carry the same houses, roads, names and forest.

The server's `image/png8` against its own RGBA render, same tile, z13/z17/z18: 7–10 % of
pixels differ, 0.02–0.56 % of them by more than 8 of 255 steps, the largest step 48 of 255 —
edge pixels of lines and lettering, nothing else. Unmeasured: whether the WMS rate-limits a
pull of 600,000 tiles; how labels fall at metatile edges. Phase 5 finds both out on z8–z16.

### 3.5 What the coarse levels weigh, whole country

For later, when maps stop being boxes: Norway's mainland outline (about half of it land)
z8–z10 on the flat palette tiles is 220 MB, z11 another 470 MB; Sweden z8–z10 60 MB, z11
another 420 MB. Not part of this plan; recorded so the numbers are not taken again.

### 3.6 What the bucket answers in

From forge, `atlas.cairn.zone`, Cloudflare colo Prague, HTTP/2, `curl` timings and
`cf-cache-status`, 2026-09-18:

| the edge | time to first byte | 20 tiles in parallel |
|---|---|---|
| has never seen the tile (MISS, body from R2) | 205 ms median, 273 ms p90 | 0.51 s |
| saw it more than five minutes ago (REVALIDATED, a conditional round trip to R2) | 100–120 ms | — |
| saw it in the last five minutes (HIT) | 40 ms median | 0.07 s |

**The edge keeps a tile for five minutes.** A tile fetched at 09:44:49 answered `REVALIDATED`
at 09:51:29. The cause is the zone's one cache rule, read live from the API:
`override_origin`, edge and browser TTL 300 s, for every path but `/`. It was written for the
page, which may be five minutes stale; it also governs the six tree paths, whose objects are
versioned, never purged (the deploy purges pages only) and uploaded with
`public, max-age=31536000, immutable`. So every tile not seen at that colo in the last five
minutes pays a round trip to R2 — and R2 itself does not get faster: the 200 ms is the way
from the edge to one EU-jurisdiction store, and no setting moves it. The edge in front of it
is the whole answer.

Also seen: the browser *does* receive the year on tiles and `immutable` with it, while the
worker script's `no-cache` becomes `max-age=300` — the override shortens and never lengthens
the browser header, which is not what `home/trails-map/known-issues.md` says. At the edge it
applies to everything. A 404 from the bucket is a 27 kB HTML page, `max-age=300`, 115 ms.
Zone settings read live: HTTP/3 on, Brotli on, 0-RTT off, Early Hints off, Smart Tiered Cache
off, Cache Reserve not on this plan.

## 4. The phases

### Phase 0 — The edge keeps what it is given

`home/trails-map` only. No line of `trails` changes; the maps get faster the day it is applied.

1. **A second cache rule for the trees**, ahead of the existing one: `http.host` is the map's
   host and the path starts with `/tiles/`, `/dem/`, `/shade/`, `/slope/`, `/vegetation/` or
   `/forest/`; `edge_ttl` and `browser_ttl` both `respect_origin`. The objects already say a
   year and `immutable`; the rule just stops overriding them. The page, the worker script, the
   manifest and the icons stay under the 300 s rule. Nothing to purge, ever: a tree version is
   never rewritten in place.
2. **Smart Tiered Cache on.** A miss at the phone's colo goes to an upper-tier colo near the
   bucket instead of to R2, and a hit there serves every colo under it — one cold start for
   the region rather than one per colo the phone wanders through. Free on this plan.
3. **0-RTT on.** One round trip fewer when a mobile connection is resumed. Free.
4. **Measure after apply**, from forge with the same `curl` lines as §3.6: a tile fetched, then
   fetched again after ten minutes, must answer `HIT` with an `age` past 600. Write the two
   lines into `known-issues.md`, and correct what it says about the browser TTL (§3.6).

Not done: pre-warming the edge. Six hundred thousand tiles into every colo is nonsense; what
is looked at warms on first sight and stays warm for a year.

**Applied 2026-09-18 from forge** (`just plan-out`, `just apply-plan` in `home/trails-map`), with two
corrections to the text above. The tree rule sits *after* the general one, not ahead of it: when
several cache rules match, the later rule's settings win, so a tree rule placed first would have
been overridden back to 300 s for every tile. And Smart Tiered Cache did not apply — the token
refuses the Smart-topology endpoint. **Resolved 20:40 the same day:** the `argo/tiered_caching`
switch takes the token, and on this plan Smart is the only topology, so that switch is the whole
setting — `cloudflare_argo_tiered_caching` replaces the resource, applied, Tiered Cache on
(`home` `4510865`). Phase 0 is complete; the measurements are in `home/trails-map/known-issues.md`.

### Phase S — The JavaScript leaves `maps.py`

Before phase 1, alone, as one commit, in a window when nobody else is in the file. Measured
2026-09-18: `maps.py` is 24,677 lines, 83 % of its bytes JavaScript inside 17 Jinja
templates; `_PlanMode` 7,112 lines, `_ProfilePanel` 4,967, `_Chrome` 3,544, `_OfflinePanel`
2,561. The JavaScript is static text: 74 `{{ }}` insertions across 14 macros and not one
`{% if %}` or `{% for %}`. 187 of the last 30 days' 326 commits touched the file.

**What moves, and what does not.** Each template's script macro becomes a file under
`libs/src/trails/visualization/js/` — `plan_mode.js`, `profile_panel.js`, `chrome.js`,
`offline_panel.js`, `worker.js`, and so on, one per template, named after the class. The
text moves unchanged. The Python class reads its file at build time (`importlib.resources`,
so an installed package finds it) and fills the insertions. The 74 insertions are the one
thing allowed to change shape: where a macro reads `{{ this.x }}` in several places, it may
instead open with one `var SETTINGS = {{ this.settings_json }};` block and read `SETTINGS.x`
below — but that is a choice per file, not a requirement, and a file may keep its
insertions as `{{ }}` rendered by Jinja from the loaded text if that is the smaller diff.
The Python side is not reorganised: no new modules, no class moves, no renames, nothing
inside the JavaScript rewritten.

**The acceptance test is the output, not the source.** Build both maps before and after
(`make abisko`, `make lomsdal-visten`) and diff the two HTML files and the two workers.
They will not be byte-identical as built: branca gives every element a fresh `uuid4` name
on every build (`map_95dc…`, `tile_layer_19f2…`), so the comparison first rewrites every
32-hex element id in each file to its ordinal of first appearance, then diffs. After that
rewrite: identical, or the phase is not done. That is the whole review; a source diff of
20,000 moved lines cannot be read, and does not need to be. The normaliser is a dozen lines
and stays in `analysis/scripts/` for the next such move. `make hooks-run` green, the 577
tests in `test_maps.py` unchanged (most of them read the rendered page, which is why they
need no edit), the drive over both pages once as a formality.

**What it buys the phases after it.** A phase reads one file of 30–150 kB instead of one of
1.1 MB — an agent with a 272k window can hold the offline panel whole and never sees the
rest. Phases 1 and 3 live in `worker.js` and the Sources panel, phase 2 in the Python that
emits the layers, phase 4 in `offline_panel.js`: different files, so streams that were
serial for one file's sake become parallel. And the JavaScript gets tooling it never had as
a string — a syntax check in the hook at least, a linter if one is cheap.

Not in this phase: splitting the Python into modules per panel, or any change inside the
JavaScript. Both have their own value and their own risk, and nothing after this needs them.

### Phase 1 — Measure on the phone

No behaviour changes. Two figures this plan needs and does not have.

1. **Time in the worker's tally.** `tiles-said` gains, per path (store, seen, network,
   blank): count, total milliseconds, worst milliseconds; plus how many lookups ran past a
   deadline and the deepest the in-flight count got. Written on the same throttle as today.
   The Sources panel reads it out beside the counts it already shows. The page test that
   checks the tally's shape is extended, not replaced.
2. **The store at 600,000 rows.** A page-side helper, behind the Sources panel and not in
   the offline panel, that fills a scratch store with N synthetic rows and reports
   `indexedDB.open`, one `get`, a batch of fifty `get`s in one transaction, and the time to
   answer a full screen of tiles through the worker. Not the browse store — `trim` would cut
   it back to 500 on the next network tile — and not the kept store, which is the reader's
   ground and its count: a store of its own, `bench`, which means `DB_AT` goes from 2 to 3 in
   the worker *and* in the page (the test at `test_maps.py:1535` is what notices if only one
   moves), and the helper clears the store when it is done. Clears, not deletes: IndexedDB drops a
   store only inside another version upgrade, so the empty store stays at version 3 and costs
   nothing (found 2026-09-18 when the phase was built). Bodies of 1 kB, because it is
   the row count under test and not the bytes — 600,000 realistic rows would be 6 GB of
   synthetic ground on the phone. Run on the phone at 150,000 and 600,000 rows. This is what
   decides whether `cap` goes to 17 on Norway in phase 6. The helper stays; it is how the next
   such question gets answered.

Report both numbers in the decisions document before phase 2 starts.

**Measured 2026-09-18 on the phone** (iPhone, Safari, the Lomsdal-Visten page over LTE, Sources
→ *Measure this device's tile store*), Firefox on forge at 2,000 rows beside it for shape:

| rows | open | one get | fifty gets | screen through the worker |
|---:|---:|---:|---:|---:|
| 2,000 (Firefox) | 1 ms | 2 ms | 7 ms | 461 ms, 27 tiles |
| 150,000 | 0 ms | 257 ms | 832 ms (17 ms a get) | 515 ms, 14 tiles |
| 600,000 | 1 ms | 363 ms | 2,989 ms (60 ms a get) | 1,765 ms, 14 tiles |

The open is free because WebKit opens lazily; the first transaction pays it, which is what
"one get" shows. The figure that decides: a get inside one transaction costs 3.5× more at
600,000 rows than at 150,000, and a screen through the worker 3.4× — the cost is per get and
grows with the store, so more transactions per lookup (phase 3) cannot buy it back. **Decision
for phase 6: `cap` stays 16 on Norway** (the box at z16 is 150,875 tiles, exactly the 150,000
measured); z17 remains a scope for a route or a view, and the whole box at z17 is not offered.

### Phase 1b — Which row shape keeps a get cheap at 600,000 tiles

Added 2026-09-18 after phase 1's phone readings, and Uwe's word that the box at z17 and, later,
whole countries must stay possible: the read cost has to become independent of the number of
tiles kept. A row per tile cannot give that on WebKit — the measured cost is per get and grows
with the store, the primary key's B-tree is not the part that grows, and IndexedDB offers no
hash index. What can: fewer, bigger rows, or a direct offset into one big blob.

The measurement helper behind Sources gains a second select, the row shape, and one run
measures one of four at the same tile equivalent (150,000 or 600,000 tiles of 1 kB):

1. `blob-url` — today's row: one `Blob` per tile, a URL-shaped key. The baseline.
2. `blob-number` — the same, with an integer tile id as key. How much the long key costs.
3. `pack` — one row per 85 tiles (a parent with its three levels of children: 1 + 4 + 16 +
   64), an `ArrayBuffer` with a fixed 85-entry offset table in front, the parent's id as key.
   600,000 tiles are 7,059 rows. A get is get + slice.
4. `archive` — one big `Blob` in one row standing in for a PMTiles-style archive, a get is
   `blob.slice()` to an `ArrayBuffer`. Filled from 8 MB chunk rows without holding it in
   memory; a phone that cannot write it reports that as the result.

Each reports fill time, open, one get, fifty gets in one transaction, the screen through the
worker, and bytes on disk. Uwe runs the four at 600,000 on the phone, `blob-url` first.

**How this meets the successor's design** (`atlas/docs/decisions.md` §3.1, §3.6): atlas puts
tile packs as PMTiles on R2, one file per country, range-requested online, tiles extracted into
the offline store — and says nothing about the store's row shape or its read cost on the phone,
which is exactly what this measures. A pack can itself be a valid small PMTiles archive: a z10
parent with z11–z13, or a z14 parent with z15–z17, is 85 tiles either way, about 800 kB, one
immutable object addressed by the parent's `z/x/y`. The unit on R2 and in the store is then the
pack, and the format and the single addressing scheme survive.

**One archive per country cannot be served through the edge — measured 2026-09-18.** Two
random objects uploaded to the bucket and range-requested through `atlas.cairn.zone`:

| object | first range request | second and later | middle range |
|---|---|---|---|
| 100 MB | `MISS`, 341 ms | `HIT`, 46–65 ms | `HIT` |
| 600 MB | `BYPASS`, 21.4 s (answered 200, not 206) | `BYPASS`, 119–133 ms | `BYPASS` |

Cloudflare's cacheable object size on this plan is 512 MB; above it every byte range goes to R2
at 120 ms and a class B operation, below it the edge holds the whole object and answers ranges
from it. So whatever the row shape, objects on R2 stay well under 512 MB — packs do; a country
archive does not. Both objects were deleted after the reading.

**The four readings, 2026-09-18 18:31–18:59 on the phone** (Lomsdal-Visten, 600,000 tiles of
1 kB each, the kept ground of about 2.4 GB beside them; the worker of phase 3 with its fixes):

| row shape | rows | fill | one get | per get in fifty | screen, 16 tiles |
|---|---:|---:|---:|---:|---:|
| blob-url | 600,000 | 536 s | 464 ms | 41 ms | 696 ms |
| blob-number | 600,000 | 598 s | 1,032 ms | 54 ms | 1,018 ms |
| pack | 7,059 | 73 s | 226 ms | 64 ms | 1,041 ms |
| archive | 1 | 186 s | 68 ms | 70 ms | 1,255 ms |

**What it says.** On this device every IndexedDB request costs 40–70 ms whatever the row: the
count of rows, the key, the row's size and even a `slice()` of one blob make no difference. What
grew across the four runs was the database itself, 2.48 → 3.03 GB (WebKit reclaims deleted
blobs late), and the price per request with it; at 150,000 rows in the afternoon a get was
17 ms. So the price follows the size of the database — the kept ground with its hundred
thousand-odd blob files — and not the scratch store. The row shape alone buys nothing; the
archive buys nothing over packs and costs the awkward download.

**Decided for phase 6b (Uwe, 19:00):** packs, as `ArrayBuffer` rows (no blob file per row), a
cache of a few packs in the worker's memory, and lookups bundled per screen — a screen is one to
four packs, so one to four requests instead of sixteen, and panning inside a pack none. The
second lever the conversion itself will show: a store of ~9,500 pack rows instead of 150,000
blob files should make the database smaller and every request cheaper. Kept ground is fetched
once more after the conversion, because the format changes.

### Phase 2 — Fewer requests, page only

1. `updateWhenZooming: false` on every tile layer, in the Python that emits them, so a
   pinch asks for the level it lands on and no other. Measured target with the §3.1 probe:
   the pinch column equals the direct column.
2. `bounds` on the Abisko base sheet, from the tree's `index.json` box, the same box the four
   overlays carry, and `errorTileUrl` set to a transparent 1 × 1 PNG on every tile layer of
   both maps (§1, *outside the box*). Target: zero `tileerror` at z10 in the probe on Abisko,
   and no request at all for a tile outside the box. Lomsdal-Visten's sheet gets its `bounds`
   in phase 6, when it has a box; until then it draws Kartverket's cache everywhere as today.
3. Retain children three levels down instead of two — an `L.GridLayer.include` override of
   `_pruneTiles`, or of the `z + 2` alone. Nothing new is created; existing tiles are dropped
   later. Target: after a three-level zoom out, the z15 tiles are still in `_tiles` until the
   coarse ones load.

Drive both pages. The drive has no zoom-out reading today (it pinches the profile curve and
sets z12 once for a tap check, nothing more), so this phase adds one: from z15 over the box,
the §3.1 pinch to z10, counting `tileloadstart` per layer and `tileerror` on the sheet, with
the pinch count equal to the direct count and the error count zero as the claim. Publish if
the offline cache is not touched, which it is not.

### Phase 3 — The store path in the worker

All in `worker.js` (the worker template, before phase S), with the page's copy of the
constants where they are shared.

1. **One transaction per lookup.** Kept and seen read in one `readonly` transaction over both
   stores; the stand flag read once per worker life and memoised; the old-prefix fallback
   replaced by a one-time migration when the stand changes: keys under the old prefix of a
   sheet the map still draws are renamed to the new one, and rows under a prefix that no
   sheet of the map names any more are deleted, with the kept count corrected. Phase 6
   leans on the second half. The miss path becomes one transaction; the hit path stays one.
2. **Coalesce.** Lookups that arrive in the same tick go into one transaction — one `get` per
   tile, one commit. A pinch over five layers becomes a handful of transactions.
3. **One deadline.** A single limit over the whole lookup (start at 2.5 s and let phase 1's
   figure move it). Past it: blank with the switch on, network with it off — never one
   deadline behind another.
4. **What is fetched stays.** The browse store capped in bytes (a `size` on the row, 150 MB to
   begin with) rather than at 500 tiles; the trim runs every fiftieth write and removes the
   oldest fifty by the `at` index, keys only, never a blob. Read-write transactions on the
   browse store become rare, which is what unblocks the reads.

The tally from phase 1 is the acceptance test: worst-case store time on a full screen of
tiles, before and after, on the phone. The Firefox probe cannot see this.

### Phase 4 — The overview is always kept

1. Every run keeps the whole box z8–z11 in addition to its scope, on both maps. The panel's
   estimate shows it as its own line ("overview, N tiles, M MB") so the reader sees what the
   scope costs and what the floor costs. `BOTTOM` stays 11 for the scope's own pyramid.
2. `WEIGHT` tables gain z8, z9 and z10 — today they start at z11 and fall back to 45 kB, which
   is four times what a Lantmäteriet coarse tile weighs.
3. A reader who kept ground before this phase gets the overview on their next run; the run
   already skips what it holds, so a repeat of the same scope is the overview alone.

### Phase 5 — The Kartverket tree, cut from the WMS

Pipeline only; the published page does not change.

1. `trails.io.sources.kartverket_wms`: a `Source` with `copy_tiles(bounds, zooms, out_dir)`
   like Lantmäteriet's, that renders metatiles (2048 px plus a margin of one tile on each side,
   cropped to the inner 8 × 8) with `LAYERS` = the 188 leaves without `fjellskygge` in
   capabilities order, `FORMAT=image/png8`, `CRS=EPSG:3857`, then quantises to a palette and
   writes optimised PNG, one file per tile, resumable per tile, with the same `index.json`
   shape (`bounds`, `zooms`, `per_zoom` with tiles/written/skipped/missing/bytes, `source`, and
   `source_modified`). **The stand is the configuration, not the data** (decided 2026-09-18
   when the phase was built: the capabilities carry no update date, no `updateSequence`, no
   `Last-Modified`): the stand is a hash of the service URL, WMS version, CRS, format and the
   ordered layer list, `source_modified` is the UTC date the copy was started, a new version
   directory opens when the stand differs or the operator asks, and a re-render for new map
   content is a decision, never detected.
2. `analysis/scripts/kartverket_tiles.py` and `make tiles PARK=lomsdal-visten`, `tiles`
   taking `PARK` the way `dem`, `shade` and `slope` do, dispatching on `Tree.provider`.
3. **First run z8–z16 as a transient unit** (`systemd-run --user`, `/usr/bin/mise exec --`,
   absolute working directory — see the box's `CLAUDE.md`). Read the labels along a metatile
   seam, note the WMS's throughput and any 429 or 5xx, and write both into the decisions
   document. Then z17, which is 450,000 tiles and the bulk of the night.
4. **Deploy with `--tree tiles`** to `tiles/kartverket/topo/1/`. Check first how the deploy
   lists a tree: at 600,000 objects a listing-based sync may take longer than the upload, and
   a diff against the inventory may have to replace it. That is a change to `deploy_map.py`
   and gets its own review.
5. Weights per zoom from the tree's `per_zoom`, as Lantmäteriet's were.

**Run 2026-09-18, z8–z16 as unit `kartverket-tiles`:** 150,875 tiles in 2,030 s — about 4,450
tiles a minute at two requests in flight, one 2560 px metatile in 1–2 s — with no 429 and no
5xx in the whole run. Sizes, mean bytes a tile: z8 11.4 k, z9 15.0 k, z10 18.3 k, z11 19.5 k,
z12 14.3 k, z13 12.9 k, z14 13.6 k, z15 8.1 k, z16 11.1 k; z16 alone 1.26 GB, z8–z16 1.62 GB.
Seams: at z14 the mean absolute difference between the touching columns of adjacent tiles is
5.8 across a metatile boundary (130 pairs) against 4.8 inside one (897 pairs) — continuous to
the pixel; a four-tile look across a seam shows depth contours and soundings running through.
Labels are placed per metatile, so a name near a seam can appear once on each side or on one
only; none was seen cut. z17 started the same afternoon, resuming the tree (about 450,000
tiles at the rate above, under two hours). Stand `7544749480db8ba3`, 189 leaves (the plan's
188 was one short).
**z17 done the same day**, 449,790 tiles, 2.95 GB, 6.6 kB a tile, mean weight 6,567; the tree
is complete at 4.57 GB over z8–z17 (5.5 GB on disk). One run died on a dropped TLS connection
after 26 minutes — the request retried only HTTP statuses — and was resumed after the fix that
retries connection errors too (`3a2e621`); one 503 in the whole render, retried once. The tree
is not deployed tile by tile: phase 6a packs it and deploys the packs.

### Phase 6 — Both maps move to packs

Rewritten 2026-09-18 after phase 1's phone readings and Uwe's word: the box at z17 and, later,
whole countries must stay possible, so the unit on R2 and in the store becomes the **pack**, and
Norway's move to its own tree (the phase as first written, kept below as *6, as first written*)
happens as part of it rather than before it. Two halves: 6a is pipeline and deploy and can run
now; 6b is the worker and the page and waits for phase 1b's four readings on the phone.

**The pack.** One parent tile with its three levels of children — 1 + 4 + 16 + 64 = 85 tiles at
most — as a valid PMTiles archive: one root directory, no leaf directories, directory and tiles
uncompressed (the tiles are PNG already), tile type PNG, addressed by the parent's `z/x/y`. The
parent level follows the layer's top: a layer to z17 has packs at z14, z10 and z6; to z15 at z12
and z8; to z13 at z10 and z6. Each layer is its own archive series, because PMTiles carries one
tile type per archive and the overlays are switched and blended on their own. About 800 kB for
a base pack at z14, a few hundred kB for an overlay pack, well under the 512 MB the edge caches
(phase 1b). The Lomsdal-Visten box with every layer to its top is about 9,500 packs against
600,000 tiles for the base alone; the deploy's listing question from phase 5 disappears with it.

#### Phase 6a — Packs, pipeline and deploy

1. `trails.processing.packs`: from a finished tile tree under `analysis/output/<tree>/…/<version>/`
   write the packs under `analysis/output/packs/<tree>/<provider>[/<sheet>]/<version>/{z}/{x}/{y}.pmtiles`,
   one file per parent at every pack level of that layer, resumable per pack, with an
   `index.json` beside them (`bounds`, `levels` — the pack levels — `per_level` with
   packs/written/skipped/bytes, `tiles`, the source tree's `stand`/`source_modified`, and
   `source_index` naming the tree's own index). A writer for the PMTiles subset above and a
   reader that opens a pack and hands back one tile by `z/x/y`, both in Python, the reader
   used by the tests and later by the deploy's check. A test that a written pack is opened by
   an independent reader (the `pmtiles` package if it is already in `pyproject.toml`, else a
   second, minimal reader written from the spec, not from the writer).
2. `analysis/scripts/pack_tiles.py` and `make packs PARK=…`: every tree of the map (`tiles`,
   `dem`, `shade`, `slope`, `vegetation`, `forest`) in one run, each to its own levels.
3. `deploy_map.py`: `--tree packs` mirrors `packs/` with the same immutable cache header, and
   the check before upload opens every pack's directory rather than counting PNGs.
4. Weights per pack level from `per_level`, for phase 6b's panel.

Run over both maps once phase 5's z17 render is complete (it is being resumed today), deploy
`--tree packs`, and read the object count and the bytes.

**Run 2026-09-18, both maps, 3 minutes in all:** Lomsdal-Visten 9,162 packs, 5.57 GB — the base
7,163 packs (z14 7,120 at 638 kB mean, z10 42, z6 1; 600,665 tiles, 4.58 GB, 125 s), the four
overlays 489 each at z12 and z8 (relief 477 MB, slope 142, vegetation 129, forest 24), the
heights 43 packs at z10 and z6 (224 MB — a z10 height pack is 5.3 MB, the heaviest row there
will be). Abisko 2,274 packs, 1.07 GB (base 1,773 packs, 866 MB). 11,436 objects, 6.3 GB on
disk, every pack opened and counted by the deploy's check before upload (939,725 tile
entries). The Python `pmtiles` package cannot read them — it assumes gzip-compressed
directories regardless of the header — while the reference `pmtiles.js` reads header,
metadata and tiles byte-identical to the source PNGs; the subset is the spec's, the package
is not.

#### Phase 6b — Packs, worker and page

Waits for phase 1b's four readings. Then, in `worker.js`, `offline_panel.js`, `chrome.js` and
the Python that emits the layers:

0. **The store's row is an `ArrayBuffer`, never a `Blob`** (phase 1b: a blob file per row is what
   the kept ground's cost is made of), and the worker keeps the last few packs in memory so a
   screen costs one to four requests.
1. **The worker reads packs.** A tile request is resolved to its pack (parent at the layer's
   pack level) and an offset inside it: online a range request into the pack's object — the
   directory first, cached per pack in a bounded memory of a few packs, then the tile — or the
   whole pack when the reader is zooming into that ground (a heuristic of a few lines: the
   second tile asked from the same pack fetches the pack). Offline the pack is one row in the
   kept store and the tile is a slice of it. The minimal PMTiles reader in the worker is about
   sixty lines: header, one root directory, varints; no library.
2. **The store holds packs.** Kept rows are packs keyed by the pack's address; the browse
   store keeps what online reading fetched, by pack or by tile range, under the same byte cap.
   `DB_AT` moves if the row shape needs it. Ground kept before this phase is not the same
   picture and is dropped by the migration; one reader, Keep once (phase 7 writes that down).
3. **The panel counts packs.** Scope, overview and whole map are counted in parents at the
   pack levels per layer, weights are pack weights from 6a, the estimate line says packs and
   megabytes. `cap` goes if the readings say the rows hold at the box's pack count.
4. Everything of *6, as first written* below that is still true: Norway's provider names its
   pack tree, `bounds` on both sheets, `maxNativeZoom 17`/`maxZoom 18` on both, the magnified
   mark on the zoom line, the "answers everywhere" special cases removed, the drive on both
   pages, a look on the phone at the relief.

**Built 2026-09-18, 17:00–18:41, three commits by codex on `phase-6b`** (`f19d56f`, `14a4c43`,
`cca1e94`; one session crashed mid-way when `/tmp` ran out of quota and a fresh one picked the diff
up). What it is: the page keeps asking per tile; the worker maps a tile to its pack, reads the
pack's directory by one 16 kB range and the tile by a second, and fetches the whole pack when a
second tile of it is asked within two seconds — 48 directories and eight whole packs in memory,
least recently used out. The store has a `packs` store (`DB_AT` 4) of `ArrayBuffer` rows keyed by
the pack's address, the `tiles` store is dropped in the version-4 upgrade, the stand migration is
gone, the browse store holds whole packs under the same 150 MB cap. Keep fetches whole packs;
the estimate counts packs with `pack_weight` per level in `PROVIDERS`; `cap` is 17 on both
providers (the whole Lomsdal-Visten box 9,162 packs, 5.57 GB; Abisko 2,274, 1.07 GB); the
overview is the sheet and the four overlays, not the heights (Lomsdal-Visten 67 packs, 42 MB;
Abisko 21, 17 MB). Norway's provider names its own tree (`/tiles/kartverket/topo/1/`, top 17,
per-tile objects not in the bucket — only packs are). The zoom line says `· tiles z17` above the
sheet's native zoom. Tile layers wait up to three seconds for the worker to control the page on a
first visit. Driven in Firefox: a first z17 view is 6–14 pack requests, a second view in the same
packs none, no per-tile object request at all; full drives 827 readings a page, all green.

**Three fixes the phone asked for the same evening**, after the deploy of 19:15: the panel's
figures line said *kept packs not counted* for a missing record, a wording from before counts
were exact — a missing or null record is zero packs (`beb83d1`). The first screen fetched
whole packs because every tile of a burst counted as "the second tile within two seconds":
15–20 MB over 5G, 6.5 s a tile, 24 lookups past the deadline; now ranges first, a whole pack
only for a tile asked from a pack whose directory is older than two seconds, at most two in
flight, never a height pack — Lomsdal-Visten's first screen 2.3 MB → 205 kB (`57f25e2`). And
the page built in 8.3 s instead of 1.0 in Firefox (ten seconds on the phone): the magnified
mark's scale handler was registered on `layeradd`, so each of the 12,477 vector layers added at
construction rebuilt the scale line, 7.2 s in all; filtered to tile layers, 12 ms, and *map
built* is a recorded drive figure now, 1,228 ms Lomsdal-Visten / 263 ms Abisko on Firefox on
forge (`173b19a`). The lesson of the last one: a handler on a map-wide event runs once per
layer of a page with twelve thousand of them, and the drive did not record build time.

#### Phase 6g — One store, one row: the pack, kept or browsed

Decided 2026-09-18, 20:45 (Uwe): after 6b's fix `7a265e0` the browse store held tile rows for
range-fetched tiles and pack rows for whole packs, beside a kept store of packs — two stores
and two row shapes, and browsing let the row count grow with the tiles again, up to 15,000 at
the 150 MB cap. Instead, **one store, `packs`, one row shape**: a pack under its address, an
`ArrayBuffer` in PMTiles form that may be partial (its directory says which tiles are there),
with `kept` (yes/no), `complete` (yes/no — true when the whole pack came from the bucket or
Keep completed it against the remote directory, false for anything merged from ranges; the
bytes alone cannot tell, since a source pack may itself be sparse at the box's edge), `at` and
`size` beside it, and nothing else.

- **Browsing** merges a range-fetched tile into its pack's row — the tiles of one tick for one
  pack in one write — and a whole pack replaces the row. The worker gains a PMTiles writer
  for the subset it already reads (one root directory, uncompressed), about forty lines.
- **Keep** marks the scope's packs `kept` and completes what is partial, fetching only the
  missing tiles' ranges — or the whole pack when most is missing; a pack already whole costs
  nothing. `forget` deletes the kept rows (so it frees storage), and the browse rows stay.
- **Eviction** takes only rows without `kept`, oldest `at` first, until the browse bytes are
  under the 150 MB cap; kept bytes and browse bytes are two sums in the flags, no walk.
- **The lookup** is memory → the one row → blank offline or network online.
- **The row count is the pack count** whatever is browsed — the property the phone asked for.
- `DB_AT` 5 drops the `browse` store (a cache; nothing to migrate) and recreates `packs` empty,
  so no row without the fields exists afterwards — the reader keeps once more, which is what
  they were going to do after 6b anyway. The tally's `seen` path
  counts a tile out of a browse row, `db` out of a kept row, `mem` out of memory.

**Built 2026-09-18, 21:30 (codex, gpt-6-astra; `ea0f9b8`).** As specified, with these choices
made on the way: the row is `{pack, kept, complete, at, size}` plus one of two index keys —
`keptAt = [url, size]` for kept rows, `browsedAt = [at, size]` for browse rows — so the two
indexes (`kept`, `browsed-at`) are disjoint, the eviction cursor never meets a kept row, and
`forget` and the trim read the size off the index key and never open a row. The codec, the
row ledger, the upgrade and the two deletions live in one file, `js/pack_io.js`, embedded in
the worker and the page alike, so Keep and the worker write the same bytes. Keep completes a
partial row by fetching the missing tiles' ranges (or the whole pack when more than half is
missing), and a complete row costs no request. After Keep and after Forget the page tells the
worker `packs-changed` and the worker drops its memory copies. A locally merged archive has
its own offsets, so only bodies from the bucket seed the range directory cache. Measured on
Firefox on forge: the first z17 screen stores two rows — 53,655 bytes on Abisko, 172,210 on
Lomsdal-Visten, 86,095 / 204,646 bytes transferred, no whole pack; the first Keep 246 packs /
143.9 MB (Abisko) and 247 / 192.8 MB (Lomsdal-Visten); Forget leaves the browse rows (15 /
377 kB and 24 / 688 kB); the trim probe holds under 148.1 MB across several fifty-key batches;
the worker's writer and Python's agree on all 6,251 bytes of an 85-tile pack. 853 readings a
page, hooks 1,783 + 97 tests. Reviewed: the `DB_AT` 5 upgrade recreates `packs` empty, as
decided — the phone keeps once more.

#### Phase 6h — After 6g: the measurement helper goes, and packs arrive in the background

Decided 2026-09-18, 21:00 (Uwe). Two things, both in the worker's and the panel's files, after
6g lands:

1. **The measurement helper is removed** — from Sources, from the drive, from the tests — and
   the `bench` store with it (the version-5 upgrade of 6g drops it). Its question is answered
   in phase 1b; the question after 6g, whether a request costs less with 9,500 rows, is read
   from the Sources tally of real use (store total and worst per path), which is the better
   instrument and needs no scratch rows.
2. **Live by range, whole in the background.** The view stays on ranges. Once the reader has
   stayed two seconds on the same ground, the worker fetches the packs under the screen whole
   in the background — the sheet first, then the overlays, at most two in flight, never the
   heights — into the one store as browse rows. Panning through fetches nothing whole; staying
   makes the ground free to pan and zoom afterwards. The two seconds are the one figure the
   phone may move. The promotion rule of `57f25e2` ("a further tile after the window") becomes
   this, rather than living beside it.

3. **Keep replaces.** Decided 2026-09-18, 22:00 (Uwe): 6g's rule that Keep completes a partial
   row by fetching the missing tiles' ranges goes. A row that is not `complete` is fetched
   whole and replaces the row, `kept` set; a complete row costs no request. Keep fetches every
   pack of its scope whole anyway, and a range path beside that is a second code path for a few
   kilobytes. Built in 6h, in the same run.

#### 6, as first written — Norway moves to the tree

1. `PROVIDERS["kartverket"]`: `tiles="/tiles/kartverket/topo/1/"`, `top=17`, `cap=17` if
   phase 1 allowed it and 16 otherwise, `weight` from phase 5. The sheet gets `bounds` and
   `maxNativeZoom: 17` with `maxZoom: 18`; Abisko's sheet, at `maxZoom: 17` today, gets the
   same pair so the two maps end alike. `extent` is already the tree box.
2. **Magnified ground says it is magnified.** Whenever the map's zoom is above the base
   sheet's current `maxNativeZoom` — z18 on either map, or any level past the kept top with the
   offline switch on — the scale's zoom line carries a mark beside the view figures, for
   example `z18 · 0.25 m/px · tiles z17`. It reads the sheet's `maxNativeZoom` at the time,
   which is what `fitNativeZoom` moves, so one rule covers both cases. The line stays a
   description of the view; the mark is the one thing added. Driven in the browser at z18
   and, with the switch on over ground kept to z16, at z17.
3. Everything that special-cases a sheet that "answers everywhere" goes: the null branch of
   `EXTENT` in the panel (no provider is null once both have trees; Kartverket's `extent` is
   already the box), the Provider docstrings and `Provider.extent`'s comment about a sheet
   that answers the world, the three references to `cache.kartverket.no` in `maps.py`, the one
   in `test_maps.py`. The worker's prefixes are injected per map and follow on their own.
4. **Kept tiles across the move.** The stand record holds the old prefix, and §9.21's rule
   would go on drawing the shaded cache tiles under the new address until Keep runs again.
   That rule is for a new stand of the *same* sheet; this is a different sheet, and the old
   rows are not the same picture. So the old-prefix fallback does not apply across a sheet
   change: rows kept under a prefix no sheet of the map names any more are dropped by phase 3's
   one-time migration, and the kept count with them. Nothing is said on the panel — there is
   one reader, and the thing to do is run Keep once after the deploy, which the decisions
   document says in phase 7.
5. Drive both pages; the whole-map count on Lomsdal at the cap is a new number and the drive
   reads it. Publish.
6. A look on the phone: the relief at 55 % over the flat base, the slope colours, the forest —
   Lomsdal should now read like Abisko. If the relief reads wrong, the one knob is the 0.55 of
   §6.6, and it is shared.

### Phase 7 — Write it down

1. The Abisko decisions document gains a section for the tree (own tree, no shadow, palette,
   z17 as top, the z18 figures, the WMS layer list and the two things phase 5 found out, and
   the note that the tiles kept from the cache went with the sheet and Keep was run once), and
   settled entries for the zoom-out cause, the overview floor, the worker's store path and
   the whole-map cap, each with the figure that settled it. §9.23 is amended, not rewritten.
2. `pipeline/docs` and the README lines that describe Norway as drawn from Kartverket's cache.
   `home/trails-map/known-issues.md` gets phase 0's measurements if phase 0 did not write them
   already.
3. The `CLAUDE.md` trip section is unaffected; the map memory note on this box that says the
   two maps carry relief, slope and height tiles should add that both now draw from our own
   trees.

## 5. Not in this plan

- Country-wide overview trees and one database per provider rather than per map (§3.5).
- z18 for any box. It can be cut later for a box without changing the shape of anything.
- Rendering Norway ourselves from N50 and FKB vectors. The honest alternative if the WMS turns
  out to refuse a pull of this size; it is a project of its own.

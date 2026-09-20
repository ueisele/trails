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

**Built 2026-09-18, 22:20 and 22:38 (codex, gpt-6-astra; `746c16c`, `1376a41`).** The helper
is gone from Sources, the drive and the tests, and `bench` with it: `DB_AT` 6, whose upgrade
deletes that store and nothing else — the version-5 rows, ledgers, page and switch survive,
pinned by a test. The idle fill: one timer reset by every tile request, a bounded map of the
48 pack addresses last asked, and two seconds after the last request the packs asked in that
window that are not complete, the sheet's first and then the overlays', at most two in
flight, never a height pack, never offline; a new request stops a fill under way. The
directory-age promotion of `57f25e2` is gone. Keep replaces (item 3): an incomplete row is
fetched whole and replaces the row; a complete one costs no request. Measured on Firefox on
forge: the first z17 screen is 14 ranges — two directories of 16 kB and twelve tiles — 86,095
bytes on Abisko and 204,646 on Lomsdal-Visten; after the two seconds the sheet's pack arrives
first (437 kB / 830 kB) and the relief's second (1.25 MB / 1.48 MB), two complete browse rows
of 1.69 MB / 2.31 MB; with the switch on no request before or after; twelve moving views fetch
nothing whole; the first Keep is 70 / 109 whole requests, seven complete rows reused on
Lomsdal-Visten. 840 readings a page, hooks 1,789 + 97 tests.

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

### Phase 8 — The pan with everything kept

Decided 2026-09-19, 08:30 (Uwe): with the whole map kept, a pan or a zoom still shows the
tiles arriving — much better than before, but visible. Sources on the phone after a session of
panning over Abisko, everything kept, the switch on:

| path | tiles | total | mean | worst |
|---|---|---|---|---|
| memory | 439 | 21,646 ms | 49 ms | 390 ms |
| store | 161 | 13,376 ms | 83 ms | 380 ms |
| network, seen, blank | 0 | | | |

Peak in flight 54; at open 52 tiles in 4.5 s, worst 339 ms; the worker's own opening 3 + 2 + 1 ms.

**What the figures say.** A memory hit that costs 49 ms on average is not a memory hit. The
worker's memory holds eight packs, and a screen over three layers is more than eight, so
most requests start with the pack not in memory, go through the coalesced store lookup —
one `get` per pack, serial inside the transaction, 40–70 ms each on the device (phase 1b) —
and the tiles of one pack that arrive behind the first are tallied `mem` because the first
has filled memory by the time their own lookup returns. So 600 tiles paid for the store, and
the worst of 380–390 ms is a transaction of five or six gets. Two things sit on top: on a
phone Leaflet asks for tiles only when the drag has ended (`updateWhenIdle` defaults to true on
mobile) and keeps a buffer of two tiles past the edge, so nothing is asked for while the
finger moves; and iOS ends an idle worker after about thirty seconds, so the first pan after a
pause starts with an empty memory — the 3 + 2 + 1 ms of opening are cheap, the packs are not.

**Built as one codex run, in the worker and the tile options:**

1. **The tally tells the truth.** `mem` counts only a tile answered from memory without a
   store transaction; a tile answered from memory after waiting on the lookup counts as `db`
   with the time it waited. Nothing else about the tally changes.
2. **Memory is bounded in bytes, not in packs.** The pack cache holds up to 48 MB (a named
   constant; a z10 height pack is 5.3 MB, a sheet pack under 1 MB), least recently used out;
   the directory cache stays at 48 entries. Nothing else in the worker grows.
3. **The store warms memory while the reader stays.** On the same two-second settle as
   phase 6h, for every pack asked in the window: the pack itself and its eight neighbours
   at its pack level, in the same layer — the sheet's first, then the overlays', never the
   heights — read from the store into memory, one readonly transaction, one get at a time,
   only rows that are there, at most 32 rows a settle, and stopped by a new request like the
   fill. No network for these: online, the screen's own packs come whole through 6h's fill;
   the neighbours are warmed only if the store holds them. The next pan then finds its packs
   in memory, and the store is asked only for ground nobody has been near.
4. **Leaflet asks while the finger moves.** `updateWhenIdle: false` and `keepBuffer: 4` on
   every tile layer of both maps, where phase 2 set `updateWhenZooming: false`. Requests
   start during the drag, throttled by Leaflet's `updateInterval` of 200 ms, and two rings
   of tiles past the edge are held, so a pan of half a screen shows ground already there.
   The cost is more requests per pan, all of them answered from memory after 3.
5. **Drive.** Both pages, offline with the ground kept, as the suite already sets up: a pan
   of one screen after the settle reads every sheet tile as `mem` with no store transaction
   in the pan; the worker's memory stays under the byte bound after a pass over the box;
   the warm-up reads nothing from the network and stops on a new request; the tally's `mem`
   figure after a cold first screen is what it says (a first screen from the store is `db`).
   Readings wait for state and never compare wall-clock figures. Then hooks and the full
   drive on both pages in parallel.

What this cannot fix: the first pan after iOS has ended the worker pays the store once for
the screen; the warm-up then covers the neighbours. If the phone still shows the tiles
arriving after this, the next figure to read is the `db` worst after a pause, and the next
lever is the page reading kept packs itself, which is another design.

**Built 2026-09-19, 07:10 (codex, gpt-6-astra; `1375e76`).** As specified: a tile answered from
memory after waiting on the lookup counts as `db` with its wait; the pack cache is 48,000,000
bytes, least recently used out, the directory and address caches 48 entries; after 6h's fill
(online) or at once (offline) the settle warms memory from the store — the asked packs and
their eight neighbours per layer, sheet first, never heights, one readonly transaction, one
get at a time, at most 32 gets including misses, aborted by the next tile request; every tile
layer carries `updateWhenIdle: false` and `keepBuffer: 4` beside `updateWhenZooming: false`.
Measured on Firefox on forge, offline over kept ground: a cold first screen is 10 (Abisko) /
8 (Lomsdal-Visten) `db` answers, 53 / 96 ms in all; a pan of one screen after the settle is
10 / 8 `mem` answers in 3 / 1 ms with **no pack-store transaction**; a pass over the box
leaves 47.7 MB in memory, peak under 48 MB on both; a settle warms up to 27 rows on Abisko,
where the drive's kept ground is wide, and 0–5 on Lomsdal-Visten, where it is a small scope;
no network request from the warm-up, and a new request stops it. 854 readings a page, hooks
1,793 + 97 tests. What the phone will show is the first pan after iOS has ended the worker.

### Phase 8b — The figures fold away

Decided 2026-09-19, 09:15 (Uwe): the readings on Sources are useful, and they should not sit
in front of the sources. The two measurement paragraphs — *Opened in …* and the worker's tally
— fold behind one small symbol in the Sources header beside the title (a stopwatch), closed by
default, opened by a tap; not remembered. The line *This map was built … ago* with its check
button stays where it is, because it is an action, and the sources follow it as before. The
drive reads the fold closed on open, open after the tap, and the tally still readable inside
it; the readings that read the tally today keep working through the open fold.

**Built 2026-09-19, 07:57 (codex, gpt-6-astra; `7f5abb0`).** A stopwatch button beside the
Sources title, the size and colour of the close control, `aria-expanded` and `aria-controls`
on it; the two measurement paragraphs live in one hidden block it toggles, closed again every
time Sources opens; the build-age line, its button and the sources are where they were. Ten
readings a page (closed on open, open after the tap with the tally readable, keyboard, reset,
no such button on the other panels), the opening-cost reading opens the fold first; 864
readings a page, hooks 1,795 + 97 tests.

### Phase 8c — A ring of tiles past the edge

Decided 2026-09-19, 10:40 (Uwe): after 8 and 8b, clearly better, and still a pan shows tiles
arriving at the leading edge. The cause is what 8 could not do: Leaflet loads only the tiles
that cut the viewport (`_getTiledPixelBounds` is the map's own pixel bounds, no margin), and
`keepBuffer` keeps what is loaded, it loads nothing — so at the front of every pan each tile
is asked for as it comes into view, and each costs the worker round trip and a PNG decode
even from memory.

1. **A ring of one tile past the viewport is loaded**, on every tile layer: an
   `L.GridLayer.include` override of `_getTiledPixelBounds` that pads the bounds by one tile
   (256 px at the tile's scale) on every side, in the shape of `js/tile_retention.js` — one
   named constant, the ring's width in tiles, 1. On the phone's screen that is roughly 8–12
   visible tiles plus about 14 in the ring per layer, all of them memory answers after 8's
   warm-up. Two rings would be a multiple of the tiles per screen and are not built; the ring
   is the one figure the phone may move.
2. **Nothing else changes**: `updateWhenIdle: false`, `keepBuffer: 4`, `updateWhenZooming:
   false`, the retention override, the worker.
3. **Drive**, both pages, offline over kept ground: the tiles created for a view are the
   viewport's plus one ring (the count, read off `_tiles` against the viewport's tile range);
   after a pan of half a tile's width every tile that became visible was already loaded
   before the pan (its `el.complete` at the moment the pan ends), and what the pan asked for
   is the ring's new outer row or column only, answered from memory; the same after a pan of
   a full tile's width; the overview and whole-map counts on the panel are unchanged (they
   count the scope, not the view). Corrected 2026-09-19, 10:50, after codex read Leaflet's
   `_update`: the padded range moves with the viewport, so a pan always refills the ring —
   that is the point, and "no request" was the wrong claim; the right one is that nothing the
   reader sees is still loading. Readings wait for state and never compare wall-clock
   figures. Then the full drive on both pages in parallel and hooks.

**Built 2026-09-19, 09:19 (codex, gpt-6-astra; `308fbf2`, rebased `5fdc39f`).** The run first
stopped, rightly: the ring moves with the viewport, so the "no request" reading could not hold,
and item 3 was corrected before it went on. `js/tile_ring.js`, a separate override of
`_getTiledPixelBounds` beside the retention one, `TILE_RING = 1`, padding at the tile's own
scale so overzoom is covered; emitted before the tile layers. Measured at z15 on the phone's
430 × 932: a view loads 28 tiles a layer on Abisko (10 visible) and 24 on Lomsdal-Visten (8);
a pan of half a tile and of a full tile asks for 7 / 6 tiles — the ring's new outer column —
all from memory, no store transaction, and every tile that became visible (5 / 4) was
complete at `moveend`; the overview and whole-map counts are unchanged. Two older readings
that assumed one pack a layer were widened. 887 readings a page, hooks 1,799 + 97 tests. The reviewer's parallel drives then went red on Abisko in one run of three — two of the
pan's fourteen answers from the store — and the first suspect, a wait gap in the drive
between the settle timer and the warm-up's transaction, was closed (`7e24e55`) without being
the cause. A trace of the failing answers found it: **the warm-up evicted the next pan's
sheet pack**. A neighbour already complete in memory was skipped without touching its
least-recently-used position, so the overlays' reads later in the same warm-up pushed it out
of the 48 MB — a real worker fault that a phone would have paid as a store read on every ring
refill. Fixed by refreshing a skipped neighbour's position (`70471b0`, a regression test that
fails before it on both providers); three diagnostic runs beside a full drive reproduced the
failure once before and never after; hooks 1,803 + 97.

### Phase 8d — The blend is switched off while the map zooms

Reported 2026-09-19, 15:38 (Uwe, screenshot): Safari's *"A problem repeatedly occurred"* on
both pages — the page process ended twice in a row; the first time Safari reloads the page
quietly, which is the reset to the initial zoom Uwe saw before the message. **Only when every
overlay is on, and only when zooming in and out several times in a row**; any zoom level, any
pan, for any length of time, is fine. A sixth tile layer came the same day (mire, §6.13).

**What was ruled out, in order.** The page itself: JS heap and DOM do not grow (Chromium,
60 pans and zooms with the layers on: 13 MB after collection, 2,400 nodes, no console error).
The tile count: measured in Firefox and Chromium at 390 × 844 with six layers, a zoom cycle
12 ↔ 16 holds 210 tiles at z12 and 84 at z16 (the overlays end at z15 and are magnified),
against about 320 after a few pans at z12 — Leaflet drops the unloaded tiles of the left
level at every zoom change and keeps only the loaded ones until the new level is in, so a
zoom never holds more than a pan, and the ring and `keepBuffer` of 8 and 8c are not the
lever here. The phone's own records: no `JetsamEvent` and no `WebContent` crash in Analytics
Data that day, so it was WebKit's own limit, which writes none. Then four one-minute
experiments on the phone, all with the fast zoom cycle that kills it: six tile layers with
every vector layer off — dies; two tile layers with the vectors on — fine; slow cycles with
three seconds at each level — fine; airplane mode — dies, so not the online pack fill; over
ground that is not kept, where the tiles come back empty — fine, so not the requests but the
images. And the one that named it: **five layers with all four blended overlays on and the
relief off — dies; five layers with the mire off — fine.**

**The cause.** Four of the six tile layers are drawn with `mix-blend-mode: multiply` — slope,
vegetation, forest, mire (the theme's one blend rule in `maps.py`, §6.13's two are the new
ones). A blended layer is not composited straight from its images: WebKit renders it into a
buffer of its own and multiplies that with what is under it, on every frame the layer or its
ground changes. During a pinch the layer's container is scaled — up to 16× on a jump of four
levels — and after the finger lifts Leaflet keeps the old level's tiles scaled until the new
level has loaded, every arriving tile changing the group again. Four such buffers at that
size reach a limit three do not; two never did. That is why it is zoom-only, image-only,
and counts blended layers rather than layers. Not reproducible on `forge`: no WebKit here.

1. **A class on the map container for as long as the map is zooming**, in a small
   `js/zoom_blend.js` emitted like the other page scripts: set on `zoomstart` (Leaflet fires
   it at the start of every pinch; its own `leaflet-zoom-anim` class covers only the snap
   animation after the finger lifts, read in 1.9.3's `TouchZoom`, so it is not enough);
   removed after `zoomend` once every tile layer that started loading has fired `load`, or
   after 1,500 ms at most, whichever comes first — the waiting is for the magnified old
   ground Leaflet keeps while the new level arrives.
2. **One rule in the theme**: under that class the four overlays composite normally instead
   of multiplying. At rest the map is exactly what it is today; during a pinch the overlays
   lie a little lighter over the lettering.
3. Nothing else changes: the ring, `keepBuffer`, `updateWhenIdle`, the retention, the
   worker, the number of layers with a ring.
4. **Drive**, both pages, every overlay on: during a driven zoom the class is on the
   container; after the zoom it is off once the layers have loaded (read off state — the
   layers' `load` events or the tile loading counts — never a wall-clock comparison); the
   theme carries the rule and the four layers carry the class names it hangs on; a zoom
   with no tile still loading drops the class without waiting the full 1,500 ms. Then
   hooks and the full drive on both pages in parallel. Whether the phone holds is Uwe's
   reading, with the same fast cycle.

**Built 2026-09-19, 16:53 (codex, gpt-6-astra; `03a9944`, landed by fast-forward).** The first
run of this phase, under the earlier text that blamed the tile count, was stopped at Uwe's word
before it built anything ("erst klären"); its readings were discarded. `js/zoom_blend.js` and
`_ZoomBlend` in `maps.py`, a `trails-zoom-blend` class on the map container from `zoomstart`
until the last of the loading layers fires `load` or 1,500 ms, and the theme's second rule that
sets the four overlays to normal under it. Driven on both pages with every overlay on: the four
overlays multiply at rest and composite normally during the zoom; at `zoomend` six layers are
still loading and the class stays; every layer that started fires `load` and the last one sees
the class removed; a zoom with quick tiles cancels the 1,500 ms fallback without firing it; six
readings that fail before the change. 926 readings a page, hooks 1,841 + 97, the reviewer's own
hooks and parallel drives green. Whether the phone holds under the fast cycle is Uwe's reading.

### Phase 8e — The blend rests until the old ground is gone, and a switch to test it

8d did not hold: on the newest page (Uwe, the panel's build line under an hour old), the same
fast cycle with every overlay on still ends the page after two or three zooms. The mire's tiles
are ordinary — 256 px, a 4-bit palette, 500 bytes median at z15, smaller than the slope's — so
the fourth blended layer is what matters, not the mire. Where 8d stopped short: the class comes
off at the layers' `load`, but Leaflet keeps the left level's tiles, scaled, for 250 ms more
before `_pruneTiles` runs, and fades the new ones in over that time. The blend returns in that
window with two levels in every blended layer, one of them scaled up to 16×, and a blended
layer's group buffer follows the bounds of its content. Slow cycles free it in between; fast
ones stack four of them. This phase assumes that reading; item 2 exists to test it.

1. **The class stays until every blended layer holds tiles of its current zoom only** — read
   off the layer's `_tiles` (every `coords.z === _tileZoom`), checked after each `load` and
   then on a short poll until it holds, 3,000 ms at most. The `load` wait of 8d stays as the
   first gate.
2. **A switch in the address, for measuring only**: `?blend=never` draws the four overlays
   normally at all times; `?blend=always` multiplies at all times, as before 8d; without it
   the page behaves as item 1. Read once at page build from `location.search`, no panel, no
   hint. It is removed when the reading is taken — it is the bench store's kind of thing.
3. Nothing else changes.
4. **Drive**, both pages, every overlay on: the class stays after `load` while a blended
   layer still holds a tile of another zoom, and comes off once none does (state, not a
   clock); `?blend=never` shows no multiply at any point of a zoom, `?blend=always` shows
   multiply throughout; the plain page multiplies at rest. Then hooks and the full drive on
   both pages in parallel.

The phone's readings, in order: the plain page under the fast cycle; if it still dies,
`?blend=never` — dies too, and the blend is not the cause at all; holds, and the wait is the
part to look at again, with `?blend=always` as the control.

**Built 2026-09-19, 19:05 (codex, gpt-6-astra; `267d24c`, rebased `439133a`).** The wait ends
when no blended layer holds a tile of another zoom, polled every 50 ms after the last `load`,
3,000 ms at most; `?blend=never` and `?blend=always` read once from the address. Driven on both
pages with every overlay on: at `zoomend` six layers are loading and each blended layer holds
24–28 tiles of the left zoom; the last `load` still sees other-zoom tiles in three of the four
and the class stays; it leaves only once all four counts are zero; the plain page multiplies at
rest, `never` never does, `always` does throughout. Six readings that fail before the change.
942 readings a page, hooks 1,857 + 97, the reviewer's own hooks and parallel drives green.
Published 19:10. The phone's reading is open.

### Phase 8f — The pinch is drawn, not scaled

Reported 2026-09-19, 18:40 (Uwe), on the 8d page: while a pinch is held, the trails grow with
the zoom and are very wide by the time the finger lifts. Leaflet's canvas renderer has always
done this — `_onZoom` calls `_updateTransform`, which scales the canvas element by CSS, and
the paths are redrawn only at `zoomend`; nothing in the page changed it. It shows now because
the pinch runs smoothly since 8d; before, WebKit managed few frames under it and the jump hid
the widening. Markers are placed afresh at every `zoom` event and are not affected; the circle
markers on the canvas grow with the lines.

1. **During a pinch the canvas is redrawn each frame instead of being scaled.** The paths'
   projected geometry of the last integer zoom is drawn through the context's transform at
   the pinch's current scale and offset — exact in Web Mercator, since scaling at a fixed
   zoom is linear in pixel space — and every stroke width, dash and circle radius is divided
   by that scale, so on screen they keep their size. No reprojection during the pinch.
2. **Throttled to animation frames**, one draw per frame at most, of the visible part only
   (the renderer's own bounds test does that). Measured on `forge` (Firefox, 390 × 844):
   a full redraw is 61 ms for Lomsdal-Visten with the whole park in view at z8 and 1–5 ms
   inside the park; Abisko 12 / 1–3 ms.
3. **At `zoomend` nothing changes**: Leaflet's own reprojection and redraw as today. The
   override is confined to the zoom's duration and to `L.Canvas`; SVG renderers, if any, are
   untouched. A separate `js/pinch_draw.js` in the shape of `tile_ring.js`, one named
   constant if one is needed.
4. **Drive**, both pages: during a driven zoom step (a `zoom` event between `zoomstart` and
   `zoomend`, or a fractional `setZoom` with the animation held) the canvas element carries
   no CSS scale and a stroke measured on the canvas keeps its width; after `zoomend` the
   drawn width is the same as before the zoom; the redraw count during a held zoom does not
   exceed the frames (state, not a clock). Then hooks and the full drive on both pages in
   parallel.

**Built 2026-09-19, 19:47 (codex, gpt-6-astra; `e25862d`, rebased `1f115c9`).** `js/pinch_draw.js`,
an `L.Canvas.include` over `_updateTransform`, `_redraw`, `_fillStroke` and `_updateCircle`,
active between `zoomstart` and `_onZoomEnd`: the canvas is positioned over the viewport with
no CSS scale, the paths drawn through `setTransform` at the pinch's scale with widths, dashes
and radii divided by it, the visible rectangle inverted into the old projection so the
renderer's own bounds test skips the rest; `_PinchDraw` in `maps.py`. Driven on both pages at
a held 1.75× and 0.75×: unit CSS scale on every canvas, the reference stroke 3.004 px on the
canvas and on screen before, during and after, at most one draw per renderer per frame, no
idle draw, no reprojection; pinch tile requests equal the direct zoom's. 969 readings a page,
hooks 1,868 + 97; the reviewer's own hooks and parallel drives green (codex's Abisko run had
one intermittent failure in 8e's blend reading, its recheck 40 of 40; the reviewer's run none).

### Phase 8g — Two switches for the finger's release

8e did not hold either, and the reading that settles it came from `?blend=never`: the page
still ends under the fast cycle with the overlays never multiplied. **The blend is not the
cause**; 8d and 8e only made it rarer (Uwe: it now takes many more cycles), and two more
facts came with that: it happens **when the finger lifts**, not during the pinch, and it
still needs many tile layers with real images. At the release WebKit does what it defers
while a transform is moving: it re-rasterises the layers whose transform changed, at the new
scale. Leaflet holds each layer's old ground scaled — up to 16× on a four-level jump — until
the new level has loaded. If a visible old tile is rasterised at its displayed size, it costs
a screen's worth of pixels, about 12 MB at three device pixels a CSS pixel, and six layers'
worth of them is a few hundred MB a release, freed later than the next release comes. Two
layers stay under it. Whether tiles are rasterised rather than composited straight from the
image cannot be measured here; Leaflet's own `.leaflet-safari .leaflet-tile { image-rendering:
-webkit-optimize-contrast }` is the rule that could make it so. No third theory: two switches
in the address, read once like `?blend=`, so both levers are tested on the phone in one build.

1. **`?ground=drop`** — at a zoom change the old level's tiles are not retained: the
   retention override (`js/tile_retention.js`) keeps nothing across levels while the switch
   is on, and Leaflet's `_pruneTiles` removes them at once; the layers are blank until the
   new level loads. If the page holds under it, the scaled old ground is the cost, and the
   fix to design is retaining one level back instead of five (parents) and three (children).
2. **`?tiles=plain`** — the theme overrides Leaflet's Safari rule with `image-rendering:
   auto` on every tile. If the page holds under this one alone, the rule was the cost and
   the fix is that line, with the slight blur it may bring at fractional zoom to be looked at.
3. The blend switches of 8e stay for now. **If the reading shows the blend plays no part, the
   `_ZoomBlend` machinery of 8d/8e is removed in the phase that lands the fix**, so the page
   carries nothing that explains nothing.
4. **Drive**, both pages: under `?ground=drop` no tile of another zoom is in any layer after a
   driven zoom step at any moment (state, not a clock) and the new level loads as before;
   under `?tiles=plain` the computed `image-rendering` of a tile is `auto` where the map's
   container carries `leaflet-safari` (set the class in the drive, since no browser here is
   Safari); without switches nothing changes against 8f. Then hooks and the full drive on
   both pages in parallel.

The phone's readings, in order, all with every overlay on under the fast cycle: plain page
(the baseline, expected to die after many cycles), `?ground=drop`, `?tiles=plain`, and if
neither holds alone, both together.

**Built 2026-09-19, 20:40 (codex, gpt-6-astra; `61bd3c4`, rebased `7146d1c`).** `?ground=drop`
read once in `tile_retention.js` (no parent or child retained); `?tiles=plain` read once by
`_TileRendering`, a class on the container and one theme rule of higher specificity than
Leaflet's Safari rule. Driven on both pages, six layers, 15 → 12 → 15: without a switch each
layer holds 28 / 24 tiles of the left zoom at the peak, under `ground=drop` none, at every
moment; under `tiles=plain` with the `leaflet-safari` class forced, every tile computes
`image-rendering: auto`, read as an explicit rule so Firefox's ignorance of the Safari value
cannot pass for it; every level loads real images under every combination; without a switch
nothing changes. 1,003 readings a page, hooks 1,880 + 97; the reviewer's own hooks and
parallel drives green. Published 20:55. The four phone readings are open.

### Phase 8h — Old ground is the sheet's only

8g's readings on the phone (2026-09-20, 00:20, every overlay on, the fast cycle, online):
plain page dies; **`?ground=drop` holds**, with a flicker at every zoom; `?tiles=plain` dies.
So the ground Leaflet keeps scaled across a zoom change is the cost, Leaflet's Safari
`image-rendering` rule is not, and neither was the blend. What is kept today, per layer: on
a zoom in, the nearest loaded parent; on a zoom out, up to three levels of children — the
depth three is this plan's phase 2 (Leaflet keeps two) — each level a screen's worth of
pixels once WebKit rasterises it at the new scale when the finger lifts. Six layers, three
levels: eighteen screens of old ground at once. `drop` keeps none and flickers because the
sheet blanks too.

1. **The retention override keeps old ground for the sheet only.** `js/tile_retention.js`
   retains parents and children as today (parents to −5, children to +3) for the layer that
   carries the sheet — marked by an option set in `maps.py` (`retainGround: true` on the base
   tile layer, nothing on an overlay) — and retains nothing across levels for every other
   grid layer: their old level's tiles go at the zoom change and the new level fades in as
   it loads. Three screens of old ground instead of eighteen, the sheet never blank.
2. **The measuring switches go**: `?ground=`, `?tiles=` and `_TileRendering` (8g), and
   `?blend=` with the whole `_ZoomBlend` machinery and `js/zoom_blend.js` (8d, 8e) — the
   blend was not the cause, and the page carries nothing that explains nothing. The theme
   keeps its one multiply rule as before 8d. The drive's readings for those go with them.
3. Nothing else changes: the ring, `keepBuffer`, the pinch drawing (8f), the worker.
4. **Drive**, both pages, every overlay on: after a driven zoom out of three levels the sheet
   holds tiles of the left zoom while its new level loads and no overlay holds any (state,
   not a clock); after a zoom in the sheet holds its parent and the overlays none; once
   loaded no layer holds another zoom; the blend readings of 8d/8e and the switch readings
   of 8g are removed; the four overlays multiply at rest and during a zoom, as before 8d.
   Then hooks and the full drive on both pages in parallel.

If the phone still ends the page after this, the next step is the sheet's children depth
back to Leaflet's two, then one — each a number in `tile_retention.js`.

**Built 2026-09-20, 00:50 (codex, gpt-6-astra; `2ba9136`, landed by fast-forward).**
`retainGround` on the base tile layer, read by `tile_retention.js`; `_ZoomBlend`,
`_TileRendering`, `zoom_blend.js`, both theme rules, the three switches and their tests and
readings removed, 849 lines fewer. Driven on both pages with every overlay on: after 15 → 12
the sheet holds 28 (Abisko) / 24 (Lomsdal-Visten) tiles of the left zoom while its level
loads and every overlay none; after 12 → 15 the sheet holds 2 and the overlays none; once
loaded and faded every count is zero; the four overlays multiply at rest and during a zoom.
Sixteen readings that fail before the change. 965 readings a page, hooks 1,849 + 97; the
reviewer's own hooks and parallel drives green. Published 01:05. The phone's reading is open.

### Phase 8i — The snap is drawn too

Measured 2026-09-20, 11:00, in Chromium against the 8h build (`/tmp/vec-measure/snap.py`: a
pinch driven as TouchZoom drives it — `zoomstart`, fractional `_move` frames with `pinch`,
`_animateZoom(center, snapped, true, zoomSnap)` at the release): in the first frame after
the release every canvas is drawn at the snapped zoom (view scale 16 from z12) while the
tile levels still stand at the release's (the sheet's level at 1.57 of its 2.0), and the
levels glide there over 250 ms on Leaflet's `cubic-bezier(0,0,0.25,1)`. 8f's
`_updateTransform` draws whatever centre and zoom it is handed at once, and the snap hands
it the end. So the paths jump at every release, by up to √2, and the ground catches up a
quarter of a second later.

1. **During the zoom animation the canvas is drawn each frame along Leaflet's own curve.**
   In `pinch_draw.js`, an `_updateTransform` call while `map._animatingZoom` is set starts a
   snap rather than drawing the end: the start is the view drawn now (`_pinchView`, or when
   no pinch preceded — a double tap, the buttons, a wheel — the stock view of the map's centre
   and zoom before the animation), the end is the view of the centre and zoom handed in, and
   for 250 ms each frame draws the view whose scale and offset are interpolated linearly in
   the eased time, easing `cubic-bezier(0,0,0.25,1)` — the same interpolation the level
   containers' `transform` transition does on translate and scale. Leaflet's order at the
   end: after 250 ms `_onZoomTransitionEnd` clears `_animatingZoom`, then fires `zoom` (one
   more `_updateTransform` with the end, drawn as the end, which is where the curve stands
   by then), then `zoomend`, which cancels and resets as today, then `moveend`, which
   redraws in the new projection as today. During the animation itself `_move` runs with
   its events suppressed, so nothing but the curve draws.
   Strokes, dashes and radii keep their widths through the snap as through the pinch.
2. Nothing else changes: the pinch drawing itself, the retention, the ring, the worker.
3. **Drive**, both pages: after a driven release from a fractional zoom (as above), the canvas
   view in the first frame lies strictly between the release's scale and the snapped one; on
   each frame of the animation the zoom the canvas is drawn at (`_zoom + log2(view scale)`)
   agrees with the zoom the sheet's level stands at (`level.zoom + log2(its CSS scale)`)
   within a frame of the curve; every painted stroke keeps its width during the snap; the 8f
   readings after `zoomend` hold unchanged; an animated `setZoom` glides the same way.

## 5. Not in this plan

- Country-wide overview trees and one database per provider rather than per map (§3.5).
- z18 for any box. It can be cut later for a box without changing the shape of anything.
- Rendering Norway ourselves from N50 and FKB vectors. The honest alternative if the WMS turns
  out to refuse a pull of this size; it is a project of its own.

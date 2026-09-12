# Abisko: what has been decided, what is open, and what changed

Started 2026-09-12, out of one design conversation about a second map beside Lomsdal-Visten:
**Abisko national park and its surroundings, Sweden**, built with Lantmäteriet's tiles rather than
Kartverket's. It records **decisions and the figures behind them**, then the open points, and a
log at the end that says how each open point was settled and what changed on the way. Keep the
log; it is the part that is read later.

Where a figure was measured it says so and how. Nothing here is an estimate unless it is
labelled one. The predecessor documents are `route-planning-decisions.md` beside this one and
`atlas/docs/decisions.md` in the `atlas` repository, which this refers to by section number.

---

## 1. The decision in one paragraph

**Abisko is a second single-document map in `trails`, published as its own app.** On the current
architecture a map is one document, one manifest, one Home Screen icon, so a second area is a
second install. `atlas` would make it one app for every area, but `atlas` has no client yet
(`atlas/docs/decisions.md` §9.1.4), so it is not a candidate for a trip. The Swedish source set is
written as its own country module, `network/sweden.py`, beside `network/norway.py` — and that is
exactly the half `atlas` §2 says is *carried as code*. What is thrown away later is the document
build, and that already exists. Nothing written for Abisko is written twice.

**The one input this decision waits on: the date of the trip.** It decides how much of §7 must
be done before departure and how much may follow.

---

## 2. The area

Stated by Uwe, 2026-09-11, amended 2026-09-12: west to the Norwegian border, **and no Norwegian
ground is needed**; south to and including Áhpparjávri; north to Kedketjårro; east to where
Rautasjaure begins; Björkliden must be inside.

Geocoded 2026-09-11 through Nominatim (OSM) and Lantmäteriet's own place-name search
(`minkarta.lantmateriet.se/api/searchservice/searchinput?searchtext=…`, SWEREF99 TM, converted):

| edge | place | coordinate | edge value |
|---|---|---|---|
| west | Norway–Sweden border | between 68.15 N and 68.55 N the border runs at **18.10–18.15 E**, nearly north–south | **18.15 E**, the border's easternmost point in that range, so the box holds no Norway |
| south | Áhpparjávri (lake) | 68.200 N, 18.612 E | **68.17 N**, so the lake is whole |
| east | Rautasjaure (lake), its western tip | lake spans 68.074–68.169 N, **18.994**–19.378 E (OSM relation 1554525) | **19.00 E** |
| inside | Paddus (peak) | 68.319 N, 18.865 E | the earlier east marker; now 6 km inside the edge |
| north | Kedketjårro | **not found** — see §8.1 | **68.55 N assumed** |
| inside | Björkliden (station) | 68.407 N, 18.686 E | — |
| inside | Abisko (village) | 68.350 N, 18.830 E | — |
| inside | Abisko nationalpark | 68.327 N, 18.701 E | the park the build looks up by name |

The border trace comes from OSM relation 2978650 (the Norway–Sweden boundary), read at 0.05°
steps. It matters twice: it sets the west edge, and it is where the north edge stops being free.
**Between 68.15 N and 68.55 N the border never goes east of 18.15 E**, so a west edge at 18.15 E
puts the whole box in Sweden; what it costs is a sliver of Sweden west of that line, at most
about 1 km wide around 68.30 N, where the border sits at 18.12 E. **At 68.60 N the border has
turned east to 18.41 E**, and the north-west corner of the box would be Norwegian ground, where
Lantmäteriet paints opaque white (`atlas` §3.7). So a north edge at or below about 68.55 N is
what lets Abisko skip the two-provider stacking of `atlas` §3.5 entirely; a north edge above it
brings that mechanism back (§8.2), or costs a west edge moved east to keep Norway out.

Size, computed for the three candidate north edges, WebMercator tile counts over the box
18.15–19.00 E, 68.17 N to the north edge:

| north edge | area | tiles z11 | z14 | **z16** | z18 |
|---|---|---|---|---|---|
| 68.50 N | 1,280 km² | 36 | 1,638 | **25,265** | 404,240 |
| **68.55 N** | 1,473 km² | 42 | 1,872 | **29,140** | 466,240 |
| 68.60 N | 1,665 km² | 48 | 2,106 | **33,015** | 527,620 |

About a fifth of Lomsdal-Visten's box (131,033 tiles at z16, `atlas` §3.3). At Kartverket's
measured weight of about 50 KB a tile the whole map at z16 would be roughly 1.5 GB; Lantmäteriet's
PNGs measured smaller (20.7 KB inside Sweden at z13, `atlas` §3.7), so expect less. The `WEIGHT`
table has to be re-measured for the new provider anyway (§4.2).

---

## 3. What is known about Lantmäteriet's tiles

Measured 2026-09-11 and recorded in `atlas/docs/decisions.md` §3.7; repeated here only as far as
it drives decisions:

- WebMercator tile matrix set `3857`, **z0 to z18**, layers `topowebb` and `topowebb_nedtonad`,
  `image/png`, URL `…/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.png` — the same grid, the
  same ceiling, the same `{z}/{y}/{x}` order and the same two sheets as Kartverket. `TOP = 18`
  and `SPAN = 2^18` in the offline panel stay as they are.
- **Outside Sweden the tile is opaque white** (755 B, one colour, alpha 0 nowhere), not
  transparent as Kartverket's is outside Norway. This is what makes the north edge matter (§2).
- **What answered without a credential is `minkarta`**, the public viewer's proxy, not a
  published API. The documented endpoint at `maps.lantmateriet.se` answers **401** and wants a
  Geotorget registration. Nothing is built on `minkarta`.
- The product is *Topografisk webbkarta Visning, cache*, Lantmäteriet open data, **CC0**, key
  required. Unverified: whether the API terms say anything about bulk download, which an offline
  pack at z16 is, and whether CORS is set. Both are checked at registration (§8.3).
- A search result says *Topografisk webbkarta Visning, översiktlig* retires on 2026-12-31. That is
  the overview product, not this one — but check at registration which product the key rests on.

---

## 4. What in the code is Norway, and what is not

Read out of `libs/src/trails/visualization/maps.py` (21,271 lines) and the scripts on 2026-09-11.
The good news first: the bounding box is already a parameter of `create_map`, the tile URLs live
in one Python table (`_BASE_LAYERS`, `maps.py` ≈ line 1892), and configuration reaches the
JavaScript through JSON blobs (`_script_json`, `plan_json`, `export_json`). The rest is a list of
literals.

### 4.1 The park

All in `analysis/scripts/lomsdal_visten.py`: `PARK_NAME` (also duplicated in `route_graph.py`),
the output file `lomsdal-visten.html`, six literal GPX names, the UT catalogue path, the export
descriptions, the graph cache name, and the legend title with the Norwegian word `nasjonalpark`
in it. `drive_map.py` has the page path as a constant. The park is found **by name in Naturbase**,
which is the one Norway-specific part of how the extent is derived.

**Decided:** this becomes the `--park` option the Makefile comment at `Makefile:164` promises. A
park is a name, a box or a lookup, a country module and a base-map choice; everything above
derives from it.

### 4.2 The provider, inside the JavaScript

Hard-coded where a JSON blob should be: `TILE_HOST = "cache.kartverket.no"` in the service worker
(the worker intercepts only that host), a `'kartverket'` substring in the resource timing, the
panel hint *"Which Kartverket sheet is drawn underneath"*, and `WEIGHT`, the bytes-per-tile table
per zoom that every size estimate on the offline panel rests on — measured on Kartverket, along
the trail network.

**Decided:** hoist these into a provider blob injected from Python, one entry per base map, and
measure `WEIGHT` for Lantmäteriet the same way it was measured for Kartverket. `TOP` and `SPAN`
stay global because both providers end at z18 (§3).

### 4.3 The sources

Six of seven are Norwegian endpoints with no shared abstraction (`TrailDataSource` exists and
nothing subclasses it). `network/norway.py` is honest about it: free of the park, not of the
country. Only OSM through Overpass is portable, and it is bbox-based, not extract-based.

### 4.4 The heights

The page calls `ws.geonorge.no/hoydedata/v1/punkt` **live** for the legs of a planned route,
injected as `heightsUrl`; the build samples the same service for every graph vertex. Neither
answers in Sweden. This is the largest single item (§6.3).

### 4.5 The deploy, and why two maps collide today

`deploy_map.py` takes `--map` and uploads `<name>.html`; the rewrite in `home/trails-map` names no
map, so a second page is a second upload. **But the companions are not parametrised**: `sw.js`,
`manifest.webmanifest` and the four icons go to the bucket root by fixed name, so a second deploy
overwrites the first's. And the worker registers at scope `./` — one worker for both maps, one
IndexedDB (`DB = "trails"`), one terrain store whose tile keys are `z/x/y` without a provider, and
a `sweepOldCaches` that would treat the other map's caches as cast-offs. See §6.2.

### 4.6 The projection is not a problem

`EPSG:25833` is hard-coded in five places. **It stays.** SWEREF99 TM (EPSG:3006) is a transverse
Mercator on the 15° E meridian with scale 0.9996 — parameter-identical to UTM 33N, on a datum
that agrees with ETRS89 at centimetre level. Abisko lies at 18–19° E, 3.5° from the central
meridian, closer than Bergen, for which `atlas` §6.1 measured +0.2 %. Swedish sources arrive in
3006 and are reprojected to 25833, which is numerically a no-op.

---

## 5. The Swedish source set

| role | Norway today | Sweden | standing |
|---|---|---|---|
| base map | Kartverket cache | Lantmäteriet *Topografisk webbkarta Visning, cache*, CC0, key via Geotorget | grid measured identical (§3) |
| paths | OSM, Turrutebasen, N50, FKB | OSM, plus Naturvårdsverket *Leder och friluftsanordningar*: WFS `https://geodata.naturvardsverket.se/leder_friluftsliv/wfs?`, SWEREF99 TM | carries summer *and* winter trails and marking; winter-only trails must leave the summer network |
| cabins, shelters, bridges | N50, UT.no | the same service, `https://geodata.naturvardsverket.se/anordningar_friluftsliv/wfs?`, plus OSM `alpine_hut` / `wilderness_hut` | STF's cabins are in both |
| protected areas, and the park lookup | Naturbase | Naturvårdsverket's *naturvårdsregistret*, open WMS/WFS/REST | replaces `find_one(PARK_NAME, …)` |
| roads | N50 | OSM (E10, Rallarvägen, Björkliden's roads) | enough here; NVDB exists if it is not |
| water | N50 Arealdekke | OSM polygons, or Lantmäteriet Hydrografi (open) | Torneträsk and the lakes drive the straight-walk water cost |
| place names | Stedsnavn | Lantmäteriet Ortnamn (open, via Geotorget) or OSM | Swedish and Sami names; the search box reads this |
| heights | Geonorge point API, live | Lantmäteriet *Markhöjdmodell Nedladdning*, WCS, CC0, **RH 2000** — orthometric, so no datum jump (`atlas` §6.2) | §6.3 |
| land cover | not used | Naturvårdsverket NMD, 10 m raster, open | not needed; listed so nobody looks for AR50 |

Exact layer names, attribute names and the winter/summer field are read off the services when
the module is written, not guessed here.

Licences the credits will carry: Lantmäteriet CC0, Naturvårdsverket open data, OpenStreetMap
ODbL. UT.no's CC BY-NC does not enter this map.

---

## 6. Decided

### 6.1 The key stays out of the page

The page is public; a key in its HTML is a public key on Uwe's Geotorget account. **Decided:** a
Cloudflare Worker in `home/trails-map`, on its own hostname, that adds the key as a header on the
way to Lantmäteriet and caches at the edge. `TILE_HOST` becomes our own host, the key stays in
sops, and a product change at Lantmäteriet is one line in the Worker. The Worker sets CORS itself.

### 6.2 Two maps, two origins

**Decided:** a second instance of the `home/trails-map` module — its own bucket, its own hostname
(`abisko.cairn.zone` is the shape). Service worker, IndexedDB, storage quota and iOS's seven-day
eviction are all per origin, so every collision in §4.5 is avoided with **no code change**. The
alternative — a prefix per map in one bucket, a worker scope per map, a database name per map —
is what the module's *"more than one map from the start"* meant, and it is the better design; it
costs a rework of the service worker and the offline panel that a trip does not have time for.
Recorded so it can be picked up if a third map ever comes.

### 6.3 The heights ride in the document

Three ways were weighed: a Worker in front of Lantmäteriet's WCS that imitates the live point
query; a coarse height grid for the box inside the document; DEM tiles on R2, which is the `atlas`
§3.5 design. **Decided: the grid in the document.** At 50 m the box is about 600,000 cells,
estimated under 1 MB compressed — small against a 15.9 MB page — and it makes the heights of a
planned leg **available offline for the first time**, which the live query never was. The build
samples the same grid for the graph vertices, so build and page agree by construction. The datum
is asserted at import, as `atlas` §6.2 requires.

### 6.4 The box holds no Norway

Uwe, 2026-09-12: no Norwegian ground is needed. With the west edge at 18.15 E and the north edge
at or below 68.55 N (§2), the box is entirely Swedish, and Lantmäteriet draws all of it.
**Decided:** no blank-tile classification in the downloader and no second provider for this map.
Tiles that straddle the border at the west edge are drawn by Lantmäteriet with white beyond the
line, which is the provider's own rendering of the frontier and reads as such. The trigger that
reverses this is in §8.2.

### 6.5 Winter trails are not routable

The Naturvårdsverket trail data carries winter trails (over lakes and bogs) beside summer ones.
**Decided:** the summer network is built from summer trails only; winter-only lines may be drawn
as their own legend row, off by default, and never enter the graph. The August–September use of
this map is the reason.

---

## 7. The order of work

1. **Geotorget registration** — a person's agreement, Uwe's step, and the first one. Check at the
   same time: which product the key rests on, its retirement date, the terms on bulk download, and
   CORS. The key goes into `home/trails-map`'s sops file. With it, the seam measurement of
   `atlas` §9.2 becomes possible, and Abisko's north-west corner is the ideal test case.
2. **Infrastructure** — the second module instance (§6.2) and the tile proxy Worker (§6.1).
3. **`trails`, the plumbing** — `--park` (§4.1), the provider blob and `WEIGHT` for Lantmäteriet
   (§4.2), `drive_map.py` gains `--page`.
4. **`network/sweden.py`** — OSM, Naturvårdsverket trails and facilities, protected areas, water,
   names; winter trails excluded (§6.5).
5. **Heights** — the grid in the document (§6.3).
6. **Acceptance and publish** — the structural readings of `make drive` against the Abisko page,
   then `command make map --park abisko`, then the deploy through the new module instance.

Steps 2 and 3 do not depend on step 1 and can start before the key exists; step 4 needs the
Naturvårdsverket services only, which are keyless; step 5 needs the key for the WCS.

---

## 8. Open

Triggers, not deadlines — the convention `atlas` §9 and `pipeline/TODO.md` use. When an item is
settled, move it to §9 with the date and what settled it.

### 8.1 Where Kedketjårro is

Not in OSM (no `natural=peak` by that name in 68.38–68.75 N, 18.2–19.3 E; 51 named peaks
listed), not in Lantmäteriet's place-name search under `Kedketjårro`, `Kädketjårro`, `Kedke`,
nor under the North Sami form `Geađgečorru` (Sami *geađgi*, stone; *čorru*, ridge — the pattern
that turns `Lullehačorru` into `Lullehatjårro`). The only `-tjårro` hit near Abisko is
Adnjetjårro at 68.212 N, 18.655 E, which is south, not north. **Needs Uwe:** a coordinate, a
neighbour, or the map it was read from. Until then the north edge is 68.55 N by assumption, and
§2 says what changes if it is further north.

### 8.2 Whether two providers must be stacked after all

*Trigger: the north edge lands above about 68.55 N and the west edge is not moved east to keep
the box Swedish.* Then the `atlas` §3.5/§3.7 mechanism is needed here: classify every
downloaded tile, drop Lantmäteriet's white ones, and draw Kartverket beneath. The downloader
today stores anything that answers 200 (`maps.py` ≈ line 16963), so white would be kept as
terrain and reported as coverage; the classification is a byte-size threshold first and a decode
second.

### 8.3 What Lantmäteriet's terms say

*Trigger: the registration (§7.1).* Bulk download for an offline pack; CORS on the documented
endpoint; the product's retirement date; whether the key is a header, a query parameter or
both. The Worker of §6.1 absorbs the last of these whichever way it goes.

### 8.4 The date of the trip

Decides how much of §7 is before departure. Unknown as of 2026-09-12.

### 8.5 Which height product, at which resolution

*Trigger: step 5.* *Markhöjdmodell Nedladdning* is a 1 m WCS; the box at 1 m is 1.5 billion
cells, so the request resamples to 50 m or the build does. The older *grid 50+* product may or
may not still be served. Measure what one WCS request over the box returns before choosing.

### 8.6 `make drive` for a second page

*Trigger: step 6.* The 278 readings assert Lomsdal-Visten's figures. Which are structural and
hold for any page, and which are that park's numbers, is not yet separated.

---

## 9. Settled

*(empty — entries move here from §8 with the date and the measurement that settled them)*

---

## 10. Changes

A line per change to this document or to the decisions in it, newest first.

- **2026-09-12** — the area amended by Uwe: the east edge is the western tip of Rautasjaure,
  which lands on the same 19.00 E the Paddus-plus-a-few-km reading gave; and no Norwegian
  ground is needed, so the west edge moves from 18.10 E to 18.15 E and §6.4 changes from
  "white stays white" to "the box holds no Norway". Tile counts in §2 re-computed.
- **2026-09-12** — written, from the conversation of 2026-09-11. Decisions §6.1–6.5 recorded;
  §8.1–8.6 open.

---

## 11. How the figures here were obtained

| figure | how |
|---|---|
| place coordinates, and Rautasjaure's extent | Nominatim (`nominatim.openstreetmap.org`, `countrycodes=se,no`, the lake's bounding box from its OSM relation) and `minkarta.lantmateriet.se/api/searchservice/searchinput?searchtext=`, the latter answering in SWEREF99 TM and converted with an inverse transverse Mercator on GRS80 |
| the border trace | Overpass, `rel(2978650)` clipped to 68.10–68.70 N, 17.6–19.3 E, `out geom`, binned at 0.05° |
| named peaks north of Abisko | Overpass, `node["natural"="peak"]["name"]` over 68.38–68.75 N, 18.2–19.3 E |
| area and tile counts | spherical area of the box; WebMercator tile index at each zoom from the box's corners |
| bytes per Kartverket tile | 6.76 GB over 131,033 tiles, both from the offline panel at load (`atlas` §3.3) |
| what in the code is Norway | a read of `maps.py`, `lomsdal_visten.py`, `route_graph.py`, `deploy_map.py`, `drive_map.py` and `libs/src/trails/io/sources/` on 2026-09-11, with line numbers as they stood that day |
| Lantmäteriet's grid, layers, ceiling, and its white outside Sweden | `atlas/docs/decisions.md` §3.7, measured 2026-09-11 |
| Swedish service URLs | Naturvårdsverket's *Leder och friluftsanordningar, beskrivning av öppna data* (PDF), Lantmäteriet's and Naturvårdsverket's product pages, read 2026-09-11 |
| SWEREF99 TM against UTM 33N | the two projections' parameters: both TM, central meridian 15° E, scale 0.9996, false easting 500 km |

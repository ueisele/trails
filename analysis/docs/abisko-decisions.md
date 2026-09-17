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

**There is no deadline.** Uwe, 2026-09-12: the date of the trip plays no part, and the work is
done without trading quality for time. §7 is the order, not a schedule.

---

## 2. The area

Stated by Uwe, 2026-09-11, amended 2026-09-12: west to the Norwegian border, **and no Norwegian
ground is needed**; south to and including Áhpparjávri; north far enough that the E10 is inside
whole; east to where Rautasjaure begins; Björkliden must be inside.

Geocoded 2026-09-11 through Nominatim (OSM) and Lantmäteriet's own place-name search
(`minkarta.lantmateriet.se/api/searchservice/searchinput?searchtext=…`, SWEREF99 TM, converted):

| edge | place | coordinate | edge value |
|---|---|---|---|
| west | Norway–Sweden border | between 68.15 N and 68.55 N the border runs at **18.10–18.15 E**, nearly north–south | **18.15 E**, the border's easternmost point in that range, so the box holds no Norway |
| south | Áhpparjávri (lake) | 68.200 N, 18.612 E | **68.17 N**, so the lake is whole |
| east | Rautasjaure (lake), its western tip | lake spans 68.074–68.169 N, **18.994**–19.378 E (OSM relation 1554525) | **19.00 E** |
| inside | Paddus (peak) | 68.319 N, 18.865 E | the earlier east marker; now 6 km inside the edge |
| north | the E10, whole | its northernmost point inside the box is **68.443 N**, 18.609 E, on the Torneträsk shore; west of the box it climbs to 68.509 N on the Norwegian side | **68.46 N**, 1.9 km of margin above the road |
| inside | Björkliden (station) | 68.407 N, 18.686 E | — |
| inside | Abisko (village) | 68.350 N, 18.830 E | — |
| inside | Abisko nationalpark | 68.327 N, 18.701 E | the park the build looks up by name |

**Widened 2026-09-13 at Uwe's word to 18.15–19.10 E, 68.139–68.46 N** (§9.24). The east edge at
19.00 E cut the valley path through Lapporten, which runs south through the gate to 19.03 E;
19.10 E takes it whole, and nothing else lies between 19.03 and 19.17 E. The south edge moves
to the tile row's own edge: the row that held 68.17 N ends at 68.1389 N on z11, z12 and z13
alike, so 68.139 N costs no partial row and brings in Kårsavagge's hut at 68.14 N and the
south end of Abiskojaure with the Kungsleden on it. The west and north edges and their
reasons stand. The box is 146,648 tiles from z8 to z17, 27,681 more than before.

The border trace comes from OSM relation 2978650 (the Norway–Sweden boundary), read at 0.05°
steps. It matters twice: it sets the west edge, and it is where the north edge stops being free.
**Between 68.15 N and 68.55 N the border never goes east of 18.15 E**, so a west edge at 18.15 E
puts the whole box in Sweden; what it costs is a sliver of Sweden west of that line, at most
about 1 km wide around 68.30 N, where the border sits at 18.12 E. **At 68.60 N the border has
turned east to 18.41 E**, and the north-west corner of the box would be Norwegian ground, where
Lantmäteriet paints opaque white (`atlas` §3.7). So a north edge at or below about 68.55 N is
what lets Abisko skip the two-provider stacking of `atlas` §3.5 entirely; a north edge above it
would bring that mechanism back (§9.2), or cost a west edge moved east to keep Norway out.
With the north edge at 68.46 N this does not arise.

Size, computed for the north edge the E10 sets, and for two further north to show what a
larger box would cost, WebMercator tile counts over the box 18.15–19.00 E, 68.17 N to the north edge:

| north edge | area | tiles z11 | z14 | **z16** | z18 |
|---|---|---|---|---|---|
| **68.46 N** (the E10) | 1,126 km² | 30 | 1,443 | **22,320** | 355,260 |
| 68.50 N | 1,280 km² | 36 | 1,638 | **25,265** | 404,240 |
| 68.55 N | 1,473 km² | 42 | 1,872 | **29,140** | 466,240 |

About a sixth of Lomsdal-Visten's box (131,033 tiles at z16, `atlas` §3.3). At Kartverket's
measured weight of about 50 KB a tile the whole map at z16 would be roughly 1.5 GB; Lantmäteriet's
PNGs measured smaller (20.7 KB inside Sweden at z13, `atlas` §3.7), so expect less. The `WEIGHT`
table has to be re-measured for the new provider anyway (§4.2).

---

## 3. What is known about Lantmäteriet's tiles

Measured 2026-09-11 and 2026-09-12. The first day's findings are in `atlas/docs/decisions.md`
§3.7; the second day's overturn one of them and settle where the tiles come from.

**The grid is Kartverket's.** WebMercator tile matrix set `3857`, z0 upward, 256 px, layers
`topowebb` (colour) and `topowebb_nedtonad` (grey), `image/png`, `{z}/{y}/{x}` order. Outside
Sweden the tile is opaque white, not transparent.

**The live tile services cost money — every one of them.** Read off Geotorget's product pages on
2026-09-12, rendered in Firefox because the site is a single-page app:

| product | Avgift | terms | access |
|---|---|---|---|
| *Topografisk webbkarta Visning, cache* (WMTS, the one measured on 2026-09-11) | **Ja** | Avtalsvillkor | key; Uwe's order form quoted **10,375 kr/år** for private non-commercial use |
| *Topografisk webbkarta Visning* (WMS) | Ja | Avtalsvillkor | key |
| *Topografi Visning, vector tiles* | Ja | Avtalsvillkor | key |
| *Topografisk webbkarta Visning, översiktlig* (WMTS) | Nej | CC0 | key, and **3857 only to z14**; **retires 2026-12-31** |

So the search result of 2026-09-11 that called the cache product CC0 was wrong: it described
the *översiktlig* product, which is the one that retires. What answered keyless that day was
`minkarta`, the viewer's own proxy. **Neither is a thing to build on, and the paid one is not
bought.**

**What is free is the same cartography as files.** *Topografisk webbkarta Nedladdning, raster*
— Avgift **Nej**, terms *värdefulla datamängder* (attribution), format GeoPackage, delivered
over **anonymous FTP** at `ftp://download-opendata.lantmateriet.se/Topografisk_webbkarta_raster/`.
Four files, one per sheet and projection, whole of Sweden each:

| file | bytes |
|---|---|
| `Farg_05m_mercator/1159000_7377433.gpkg` | 156,252,565,504 |
| `Nedtonad_05m_mercator/1159000_7377433.gpkg` | 139,329,609,728 |
| `Farg_05m_sweref/6104864_234624.gpkg` | 175,288,979,456 |
| `Nedtonad_05m_sweref/6104864_234624.gpkg` | 157,673,115,648 |

**And the Mercator file is a plain XYZ pyramid.** Read 2026-09-12 out of the first 64 MB of the
colour file, fetched by FTP range request and opened after patching the SQLite page count:
one tile table `topowebb`, `gpkg_tile_matrix_set` in EPSG 3857 over the full Mercator square,
and `gpkg_tile_matrix` with **z0 to z17**, 256×256, pixel sizes 156,543.03 m down to 1.19 m —
the standard Google/OSM matrix to the metre. A GeoPackage tile row is `(zoom_level,
tile_column, tile_row)` with the origin top-left, which is `z/x/y` as Leaflet counts it. **No
reprojection, no resampling, no key**: the box's tiles are copied out and served from our own
bucket.

**The ceiling is z17, not z18.** Kartverket's cache ends at z18; this pyramid ends at z17
(nominal 1.19 m/px, 0.44 m/px at 68.3° N, far finer than anything a phone shows). So `TOP` is
per provider after all — 18 for Kartverket, 17 for Lantmäteriet — and Leaflet's
`maxNativeZoom` upsamples z17 where the chooser or the map asks for z18.

**Getting the box out of a 156 GB file.** The server speaks FTP only (no HTTP, no HTTPS —
probed 2026-09-12), FTP `REST` works so byte ranges can be read, and one range read costs
about **0.64 s** including the connection (five 64 KB reads, 3.2 s). The whole file does not
fit forge's disk. The build therefore reads the file as an SQLite database over FTP through a
page-fetching VFS, walking the `(zoom_level, tile_column, tile_row)` index for the box's tile
addresses and reading each tile's pages — with a persistent control connection and ranges
sized to the rows that sit together, not one connection per page.

**Measured 2026-09-12 with a prototype of exactly that** — `apsw` VFS, 1 MB blocks, LRU of
256 blocks, one persistent `ftplib` connection, `REST` + `RETR` per block:

| | |
|---|---|
| one range read on an open connection | 0.19 s for 4 KB, 0.26 s for 64 KB, 0.40 s for 1 MB — the cost is the request, not the bytes |
| the schema, from the first block | 1 read |
| **all 380 z13 tiles of the box** | **18.3 s, 0.048 s a tile**, 44 reads, 46.1 MB fetched for 9.8 MB of tiles |
| **the whole box, z8–z17, 118,967 tiles — the real run** | **916 s**, 2,170 reads, 2,275 MB fetched for **696 MB** of tiles, none missing, 1.2 GB peak memory; z16 at 107 tiles/s, z17 at 159 tiles/s, because the finer the level the more neighbours a 1 MB block holds |

The estimate above it — 95 minutes — was made from the z13 rate and was six times too
pessimistic. Measured 2026-09-12 as the unit `abisko-tiles`; the file's own modification
time, as the FTP server reports it, is **2026-06-23 11:05:09**, which is the stand the map
carries until a rebuild under a new version prefix.

**Bytes per tile, for the `WEIGHT` table of §4.2** — the means over every tile of the box,
read from the copy's `index.json`:

| z11 | z12 | z13 | z14 | z15 | z16 | z17 |
|---|---|---|---|---|---|---|
| 31,747 | 22,166 | 25,719 | 15,290 | 13,783 | 7,958 | 4,587 |

Against Kartverket's measured 73,914 at z11–z13, 51,295 at z16 and 37,037 at z18: Sweden's
tiles are a quarter to a half the weight, so every offline estimate on the panel would be
two to four times too high with Kartverket's numbers.

A sample of 600 of the written files, opened and verified with Pillow: every one a valid
256×256 PNG.

The rows are stored in small spatial chunks (a few tile rows by a few columns, column-major
inside a chunk), so a 1 MB block holds many neighbouring tiles and the box reads in runs. The
5× transfer overhead is the price of 1 MB blocks and is not worth tuning for a one-off.

**Orientation and cartography, both confirmed.** The uniform light-blue 103-byte tiles fall in
the box's north-east corner, where Torneträsk is — so `tile_row` counts from the top, as XYZ
does. The centre tile of the box at z13 against the same address from the public viewer (which
proxies the paid `topowebb/v1.1` service): mean luminance difference **0.77** of 255 at zero
shift, 7.6–10.5 at one pixel's shift — the same drawing to the pixel. What differs is the
encoding: the file's tile is an indexed PNG with 190 colours, 26.6 KB; the service's is RGB
with 2,684 colours, 60.5 KB. The file is the smaller of the two, with no visible cost.

**Storage.** z8–z17 over the box is 118,967 tiles; at the 20 KB a z13 Swedish tile measured
that was estimated at 2.4 GB before the copy and measured at 700 MB after it (§3), in the
bucket, once. **Colour only:**
Uwe, 2026-09-12 — the grey sheet was never used on Lomsdal-Visten, so Abisko does not carry
it; the copy and the storage halve, the base-map switch has one entry and can go for this map,
and `Nedtonad_05m_mercator` is never read. If grey is ever wanted it is a second prefix and a
second row in the provider table. R2 storage is cents a month and egress is free.

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

**Decided:** this becomes the `--park` option the Makefile's comment above `map` describes. A
park is a name, a box or a lookup, a country module and a base-map choice; everything above
derives from it.

**Done 2026-09-12:** `lomsdal_visten.py` has a `Park` table (`PARKS`) and `--park`; the name, the
stem of every file, the legend word, the base sheet and its extras, the companion names and the
UT catalogue all come off the entry. **And, the same evening, the country branch**: a `BUILDS`
table maps the park's country to `build_norway` or `build_sweden`, each of which reads its own
registers and hands one `Built` bundle — the graph, the line layers, the point layers, the name
layers, the water, the credits, where a straight leg's heights come from, the GPX exports — to
one `assemble` that puts it on the page. `describe` keeps what is read off a chain and lets
`describe_norway`/`describe_sweden` add what each register says. `route_graph.py` takes `--park`
off the same table and reports Abisko against its own landmarks (*Abisko* off the lettering,
no quays, the state trail *BD 21* as the check route). `drive_map.py` already had `--page`.

### 4.2 The provider, inside the JavaScript

Hard-coded where a JSON blob should be: `TILE_HOST = "cache.kartverket.no"` in the service worker
(the worker intercepts only that host), a `'kartverket'` substring in the resource timing, the
panel hint *"Which Kartverket sheet is drawn underneath"*, and `WEIGHT`, the bytes-per-tile table
per zoom that every size estimate on the offline panel rests on — measured on Kartverket, along
the trail network.

**Decided:** hoist these into a provider blob injected from Python, one entry per base map, and
measure `WEIGHT` for Lantmäteriet the same way it was measured for Kartverket. `SPAN` stays global;
`TOP` is per provider since the file ends at z17 (§3).

**Done 2026-09-12:** `maps.Provider` and `maps.PROVIDERS` (`kartverket`, `lantmateriet`), each
with a tile prefix, `top` and the `WEIGHT` table; `_BASE_LAYERS` names its provider and gains
`BaseMap.LANTMATERIET_TOPO` at the root-relative `/tiles/lantmateriet/topowebb/1/{z}/{x}/{y}.png`,
so the page carries no host and the same page served locally over the same tree draws the same
tiles. The worker's `TILE_HOST` became `TILE_PREFIX`, resolved against the worker's own address
and matched as a prefix; the timing readout and the picker's hint take the provider's label and
prefix; the tile layer is held to `top`, which caps the map itself: the Abisko map goes no
deeper than z17 (`map.getMaxZoom()` reads 17), rather than
requested. Lantmäteriet's `WEIGHT` is the whole-box mean of §3 rather than a trail-side sample —
the box is mountain and lake, not sea, so the two are close.

### 4.3 The sources

Six of seven are Norwegian endpoints with no shared abstraction (`TrailDataSource` exists and
nothing outside `base.py` subclasses it). `network/norway.py` is honest about it: free of the park, not of the
country. Only OSM through Overpass is portable, and it is bbox-based, not extract-based.

### 4.4 The heights

The page calls `ws.geonorge.no/hoydedata/v1/punkt` **live** for the legs of a planned route,
injected as `heightsUrl`; the build samples the same service for every graph vertex. Neither
answers in Sweden. This is the largest single item (§6.3).

**Done 2026-09-12:** `maps.HeightTiles` on the provider (`PROVIDERS["lantmateriet"].heights`,
None for Kartverket); `heightsTiles` in the plan settings, and then the service is not asked at
all — the page reads a straight leg's samples off the z13 tiles, bilinearly between the four
pixel centres round each sample, unpacking Terrarium by the same two numbers `dem_tiles` packed
with; the worker intercepts the `dem/` prefix beside the map tiles; the offline panel keeps the
z13 height tiles over the same set the map tiles are kept over. The Norwegian page is untouched:
its `heightsTiles` is null and every path it took before, it takes.

### 4.5 The deploy, and why two maps collide today

`deploy_map.py` takes `--map` and uploads `<name>.html`; the rewrite in `home/trails-map` names no
map, so a second page is a second upload. **But the companions are not parametrised**: `sw.js`,
`manifest.webmanifest` and the four icons go to the bucket root by fixed name, so a second deploy
overwrites the first's. And the worker registers at scope `./` — one worker for both maps, one
IndexedDB (`DB = "trails"`), one terrain store whose tile keys are `z/x/y` without a provider, and
a `sweepOldCaches` that would treat the other map's caches as cast-offs. See §6.2.

Since 2026-09-12 the script also mirrors the two tile trees: `deploy_map.py --tree tiles` (or
`--tree dem`) runs `aws s3 sync` from `analysis/output/<tree>/` to the same prefix in the bucket
with a year's `max-age` — the `/1/` version segment makes every object immutable — uploads only
what the listing lacks, deletes nothing and purges nothing; with `--tree` alone no page goes up.
Measured against the bucket with `--dry-run`, which lists it: 118,967 objects, 696 MB, found
missing in 27 s. The companions are still unparametrised; that is the `--park` step.

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
| base map | Kartverket cache, live | Lantmäteriet *Topografisk webbkarta Nedladdning, raster*, free with attribution, anonymous FTP, copied into our bucket at build time | z0–z17 XYZ pyramid, measured (§3) |
| **the N50 role: paths, roads, water, land cover, cabins, names, contours, protected areas in one product** | N50 Kartdata, per kommune | Lantmäteriet **Topografi 50 Nedladdning, vektor** — GeoPackage, SWEREF99 TM, updated weekly, ordered for the whole country through Geotorget as a free *Abonnemang*, **CC0, no legal review**. Topografi 10 is the finer sibling and is **not orderable for Uwe**: its terms cover personal data (buildings with addresses), Geotorget puts a *juridisk prövning* in front of it, and that form wants a Swedish *personnummer* (seen 2026-09-12) | read 2026-09-12 off the product documentation, see below |
| official marked trails with attributes | Turrutebasen | Naturvårdsverket *Leder och friluftsanordningar*, as the nightly files under `geodata.naturvardsverket.se/nedladdning/friluftsliv/` (`Leder_shp.zip`, `Anordningar_shp.zip`), SWEREF99 TM, CC0 — **not the WFS**, which was down a whole day (§9.6) | keyless; nationwide, not only in protected areas (34 of the 47 lines over the box lie outside one); `LKATEGORI` separates summer (*Barmarksled*) from winter (*Led på snö*), `STATLED` names the state trail (*Abisko - Abiskojaure (BD 21)*), `LMARKERING` the marking — the attribute source, as Turrutebasen is (`atlas` §7.2). Read by `io/sources/naturvardsregistret.py` |
| paths nobody else draws | OSM | OSM, through Overpass, unchanged | the one source that is the same in both countries |
| cabins, shelters, bridges | N50, UT.no | Topografi 50 `byggnadspunkt` — `Fjällstation`, `Turiststuga/övernattningsstuga`, `Raststuga` (*"alltid olåst"*), `Vindskydd`, `Kåta`, `Enslig stuga i fjällen`, `Naturum`, none of them named in the product; the names come off the map's lettering (`textpunkt`, *Bebyggelse*) within 150 m. Naturvårdsverket's `Anordningar_shp.zip` for the bridges, privies and shelters along the state trails; Topografi 50 `ledintressepunkt_fjall` for the footbridges, fords and car parks; OSM `alpine_hut` / `wilderness_hut` | wired 2026-09-12 (`topografi50.Source.cabins`, `.trail_points`, `naturvardsregistret.Source.facilities`) |
| protected areas, and the park lookup | Naturbase | Naturvårdsverket's *naturvårdsregistret* as nightly files (`nedladdning/naturvardsregistret/NP.zip`, `NR.zip`, … one per form, same columns: `NVRID`, `NAMN`, `SKYDDSTYP`) — Topografi 50's `skyddadnatur` draws the outlines too but carries **no name** | `naturvardsregistret.Source.find_one("Abisko")` is the park lookup: NVRID 2001225, 7,710 ha; eight forms read, every one with its outline |
| roads | N50 | Topografi 50 `vaglinje` (five classes over the box, by width and surface — no public/private split as in N50; `vardvagnummer` is the identity, *E10*) and `ovrig_vag` | OSM as the check |
| water | N50 Arealdekke | Topografi 50 *Tema Mark*: `mark` polygons of class `Sjö` (1,708 over the box) and `Vattendragsyta` (144) — the lakes and the rivers wide enough to draw as a surface; the narrower rivers are lines in `hydrolinje` (2,980) and carry no width. `mark_sverige.gpkg` is 5.8 GB unpacked and the box reads out of it in under a second | Torneträsk and the lakes drive the straight-walk water cost; the river surfaces are the page's river outlines, named from the lettering within 60 m (`topografi50.Source.water`, `.rivers`) |
| place names | Stedsnavn | Lantmäteriet **Ortnamn Nedladdning, vektor** — one 58 MB GeoPackage for the country (989,302 names on 2026-09-12) at `dl1.lantmateriet.se/namnsatt-plats/ortnamn_se.zip`, the address off the keyless vector STAC (`api.lantmateriet.se/stac-vektor/v1`, item `ortnamn_se`), CC BY 4.0, rewritten nightly; **behind the Geotorget login once the product is ordered** (§9.9). A point per name with `detaljtyp` (thirteen types: terrain, lake, watercourse, part of a water, glacier, marsh, settlement, built-up area, tract, facility, cultural site, church, conservation object) and `sprak` (Swedish, four Sámi languages, Meänkieli, Finnish); no importance rank. Over the box 402 names, 242 of them North Sámi. The size a name is drawn at comes off Topografi 50's *Tema Text*, the map's own lettering (325 labels in seven size classes), joined by the same name within 500 m: 218 of 391. **Each language is a point of its own**, so the reader joins them into places (§9.12): 391 names over the box are 345 places in the box, 9 with a second name, labelled *Abiskojåkka (Ábeskoeatnu)* | `io/sources/ortnamn.py`; the name layers, the search box, the cabins' and the rivers' names read it |
| heights | Geonorge point API, live | Lantmäteriet *Markhöjdmodell Nedladdning*: 1 m COGs through a keyless STAC API, downloads behind the Geotorget login, CC BY 4.0, **RH 2000** | §6.3 |
| land cover | not used | Topografi 10 *Tema Mark* (`sankmark`, `kalfjäll`, forest); NMD 10 m raster exists too | Tema Mark is enough if the water cost ever wants bog |

**Topografi 50 is the N50 of Sweden, and in the mountains it is more.** Read 2026-09-12 off
Geotorget's documentation (GEODOK/76, and GEODOK/51 for the Topografi 10 it is generalised
from), *Tema Kommunikation*, `Övrig väg` — every class below is in Topografi 50 as well:

- `Gångstig` — *"tydlig väl upptrampad stig"*, the worn path, which is the FKB-like detail N50
  lacks and Norway gets from a second source;
- `Vandringsled` — *"markerad led längs stig eller väg avsedd för vandring"*, the marked summer
  trail; in Topografi 50 kept from 10 km, *with exceptions in mountain areas*;
- `Vandrings- och vinterled` — the trail marked with red crosses for walking, skiing and
  snowmobiles, which is Kungsleden's kind; the attribute `skoterkorning_tillaten`
  (`Ja`/`Nej`/`Påbjuden`/`Ingen information`) is carried into the popup and decides nothing:
  what tells winter from summer (§6.5) is the class `Vinterled` and Naturvårdsverket's season
  field;
- `Transportled fjäll` — `Rennäringsled`, `Roddled`, `Båtdrag`, `Skidspår` and the like inside
  Lantmäteriet's mountain area, **not walking routes** and kept out of the graph — except
  `Svårorienterad gångstig` and `Lämplig färdväg`, which are ways on foot and go in, marked;
- `Ledintressepunkt fjäll` — **fords (`Vad`), `Hjälptelefon`, `Parkering`, `Gångbro, punkt`,
  `Stormklocka`.** A ford is exactly what the straight-walk water cost of the predecessor wants
  to know about, and no Norwegian source names them.

**What Topografi 50 loses against 10** is generalisation for 1:50,000: a `Gångstig` is kept only
from 100 m to a building and 250 m to another destination, a `Traktorväg` from 500 m, small
buildings are merged into size classes, and a line may be displaced by the width of a pen
stroke. In this ground — the paths are long, the buildings are few — none of it is a loss the
routing would notice, and OSM draws the short paths anyway.

So the Swedish set is smaller than Norway's seven and not poorer: Topografi 50 carries what N50,
FKB, Naturbase and Stedsnavn carry between them, Naturvårdsverket's trail register is the
Turrutebasen, and OSM is OSM. `network/sweden.py` is three loaders, not seven.

**The delivery, measured 2026-09-12.** Ordered for the country, it is fourteen zipped
GeoPackages, 5.37 GB: `mark` 2.5 GB, `hojd` 2.0 GB, `kommunikation` 519 MB (1.36 GB unpacked),
`hydrografi` 183 MB, `byggnadsverk` 116 MB, `text` 31 MB, the rest under 10 MB each. Produced
2026-09-08, kept fourteen days, refreshed on request. The box is cut out of the country file with
a bbox over the GeoPackage's R-tree in **under a second**, so the whole-country order costs
nothing at build time. `atlas` §3.2's cells read the same file. How it is fetched is a
documented API, *Geotorget Nedladdning* (§7.1); the loader is `io/sources/topografi50.py`, one
directory per delivery under `.cache/topografi50/`.

**What the box holds** (Topografi 50, bbox 18.15–19.00 E, 68.17–68.46 N): `Gångstig` 397 km,
`Vandringsled` 168 km, `Vandrings- och vinterled` 52 km, `Vinterled` 134 km, `Traktorväg`,
`Cykelväg` and `Elljusspår` under 4 km each; `Transportled fjäll`: `Lämplig färdväg` 56 km,
`Svårorienterad gångstig` 5 km, `Skidspår` 10 km, `Trafikerad båtled` 6 km; roads 71 km, of
which the E10 46 km; `ledintressepunkt_fjall`: 48 footbridges, **8 fords (`Vad`)**, 3 emergency
telephones, 3 car parks (62, as the loaders read them); `byggnadspunkt`: 17 `Kåta`, 10 `Enslig
stuga i fjällen`, 9 `Vindskydd`, 6 `Raststuga`, 4 `Turiststuga/övernattningsstuga`, 2
`Fjällstation`, 1 `Naturum` (49) — so the
staffed huts are `Turiststuga/övernattningsstuga` and `Fjällstation`, and a `Raststuga` is the
emergency kind. Naturvårdsverket's register over the same box, as first read on 2026-09-12:
47 lines, 365 km, 30 summer and 17 winter, all 47 on a named state trail (BD 16–BD 92), and 24
facilities (10 bridges, 5 privies, 4 rest shelters, 2 wind shelters); the nightly file moves
under this (48 lines, 30 and 18, by the evening's copy).

**Naturkartan is not a source** (asked by Uwe 2026-09-12, measured the same day). It is
Outdoormap AB's platform, on which counties and municipalities publish their trails with text and
photos — the Abisko page is Länsstyrelsen Norrbotten's trail *BD20*, Kuoblavagge–Kårsavagge–Abisko.
Its terms say material may be downloaded *"endast för enskilt bruk"* (private use only) and that
the protected material may not be copied, distributed or exploited without the author's leave —
stricter than UT.no's CC BY-NC, which `atlas` §3.6 already took out of the published graph. And
there is no way in anyway: the page offers no GPX, the map is an embedded Mapbox app, and
`api.naturkartan.se/v3/sites/12849` answers 401 without the app's token. What it would give is the
prose; the line itself is the county's state trail, which Naturvårdsverket's register and
Topografi 50's `Vandringsled` carry, and the *BD* number is the key to match it there. A
Naturkartan tour is what `atlas` §3.6 calls a personal input — downloaded for one's own use and
added to one's own copy — not a layer of this map. **What the map does carry, since the evening
of 2026-09-12, is the link**: a state trail's popup names the county's Naturkartan page for each
*BD* number on the chain, out of a hand-kept catalogue (§9.22). Measured that evening, Naturkartan's
Abisko tours *are* the state trails, one page per number, and fourteen of the seventeen the
register draws over the widened box have one (thirteen of fifteen before §9.24).

Licences the credits will carry: Lantmäteriet's *värdefulla datamängder* terms with attribution for
the tiles, CC0 for Topografi 50, CC BY 4.0 for the height model, Naturvårdsverket open data,
OpenStreetMap ODbL. Nothing NC. UT.no's CC BY-NC does not enter this map.

---

## 6. Decided

### 6.1 No key online: the tiles are ours

Written on 2026-09-12 in the morning as *"the key stays out of the page"* — a Cloudflare Worker
proxying Lantmäteriet's WMTS with the key as a header. **Withdrawn the same day**, because the
live services all carry a fee (§3) and the free product is the same tiles as files. The build
copies the box's tiles into the bucket (§6.2), the page fetches them from our own host like any
tile, and the offline downloader keeps them like any tile. There is no proxy, no key in
Cloudflare, no dependency on a Lantmäteriet service at run time, and no product retirement
that can take the map down. The attribution line is the whole obligation.

What it costs instead: bucket storage of a few gigabytes (§3), and a build step that must not be
re-run casually — the tiles carry a version segment in their address (§6.2), so a refresh is a
new prefix, not an overwrite under kept tiles.

### 6.2 Two maps, one origin, one bucket — companions named per map

Uwe, 2026-09-12: the same domain and bucket if it can be done; installing from the Abisko page
must install Abisko; Abisko is its own app with its own IndexedDB; and the Lomsdal-Visten
install's kept ground must survive. Both maps are interim — the `atlas` app replaces them — so
the cheapest arrangement that meets all four is the right one.

**What happens today.** There is one `manifest.webmanifest` at the root with
`start_url: ./lomsdal-visten`, and every page links it; iOS installs what the open page's manifest
says. So adding `/abisko` to the Home Screen today would install an app that opens
Lomsdal-Visten. The service worker, by contrast, is already map-agnostic: it keeps whichever page
is open, keyed by the page's own URL. What it does not separate is the database (`DB = "trails"`),
the offline switch, the kept-record and the *Delete* button, all of which act on that one
database, and it intercepts one tile host only.

**What iOS separates on its own.** Each Home Screen web app has its own storage, apart from
Safari's and from other installs of the same origin. The evidence is the measurement of
2026-09-02 recorded in the memory note on WebKit's Cache Storage: after re-adding the app its
store was empty although Safari held the tiles. So a second install gets its own IndexedDB on the
phone regardless. The separation in code is still needed, for Safari itself and for a desktop,
where one origin is one store.

**Decided:** same origin, same bucket, flat root, and every companion file named for its map.
Lomsdal-Visten keeps `sw.js`, `manifest.webmanifest`, the four `icon-*.png` and the database
`trails` — **nothing it has is renamed, so nothing the installed app holds is touched, and
`/sw.js` never answers 404**, which is the one thing a browser may punish by dropping the
registration. Abisko gets its own manifest with `start_url: ./abisko` and an `id`, its own
worker registered at scope `/abisko`, and its own database. Opening `/abisko` and adding it to
the Home Screen then installs Abisko.

The bucket, served at `atlas.cairn.zone`:

```
/                                   the index Worker, lists every *.html object as a map
lomsdal-visten.html                 served at /lomsdal-visten     unchanged
sw.js  manifest.webmanifest         Lomsdal-Visten's              unchanged
icon-32.png … icon-512.png          Lomsdal-Visten's              unchanged
abisko.html                         served at /abisko
abisko.webmanifest                  start_url ./abisko, id ./abisko, name "Abisko Atlas"
abisko-sw.js                        scope ./abisko (resolves to /abisko), DB trails-abisko
abisko-icon-32.png … abisko-icon-512.png   a variant of the cairn, so the two icons differ
tiles/lantmateriet/topowebb/1/{z}/{x}/{y}.png            the map, colour sheet only, §3 and §6.1
dem/lantmateriet/1/{z}/{x}/{y}.png                       the height tiles, §6.3
```

Checked against the hosting module, 2026-09-12: the rewrite rule leaves any path containing a
dot alone, so `tiles/…/{y}.png` and `dem/…/{y}.png` are served as objects untouched; the index Worker lists with
`delimiter: "/"` and keeps only keys ending in `.html`, so the `tiles/` and `dem/` prefixes never
appear as maps. **No change in `home/trails-map` is needed.**

What it costs in code: `write_manifest`, `write_service_worker`, `write_icons`, `_Head` and the
`register('sw.js')` call take the map's name; `KEPT`/`SEEN` stay but the database name carries
the map; `TILE_HOST` becomes our own host, since map and height tiles both come from it, and `TOP` is
per provider (17 here, §3);
`deploy_map.py`'s `BESIDE` table is keyed per map; the `tiles/` and `dem/` trees it already
mirrors with `--tree` (§4.5). All of it is Python-side naming; the worker's logic does not change.

**Done 2026-09-12, the library side:** `maps.Companions` — `ROOT` is the first map's set and is
never renamed; `Companions.named("abisko")` gives `abisko-sw.js`, `abisko.webmanifest`,
`abisko-icon-*.png`, database and cache prefix `trails-abisko`, scope `./abisko`. `create_map`
takes it and records it on the map; the head, the registration (`register('abisko-sw.js',
{scope: './abisko'})`), the offline panel (database, caches, the switch's storage key) and the
written worker all read it. The worker's `sweepOldCaches` pattern carries the prefix, so neither
map's sweep matches the other's caches — tested both ways. The manifest gains `id`, the page's own
address, which is what a browser takes for it anyway. `Companions.of(stem)` is the one rule —
`lomsdal-visten` keeps `ROOT`, anything else is named — and `deploy_map.py` uploads a map's
companions by it, so a second map's deploy never overwrites the first's. **The variant icon is
drawn, 2026-09-12**: the same cairn on the same moss path, standing in the U-shaped gate of
Lapporten in a deep blue-grey — `atlas-abisko-*.png` beside `atlas-*.png` in
`visualization/icons/`, drawn by the same `docs/draw.ts`, and `Companions.mark` names which
drawing a map's icons are copied from (`atlas` for the first map, `atlas-<stem>` for any other,
so a third map without a drawing of its own refuses to build rather than wearing the first's).
Chosen by Uwe from four candidates on the mockup host, the gate in blue over the gate in stone
grey because it still reads at 60 px. **Not the national parks' gold star**: what
sverigesnationalparker.se serves as *Abisko nationalpark logotyp* is Naturvårdsverket's shared
six-pointed gold star with the park's name as wordmark — every park wears the same star — and
the brand's own manual (*Logotyper*, v2.0, 2011) forbids own versions, reshaping, recolouring and
effects, with a special version for outside organisations. An app icon of it would be exactly
that, and it would dress a private map as an official one; Lomsdal-Visten does not wear Norway's
park mark for the same reason.

Two things easily overlooked: **two identical icons** on a Home Screen, hence the variant mark;
and, in Safari on the same origin, Lomsdal's root-scope worker also matches `/abisko` until
Abisko's own is registered — the first visit is answered by the root worker and cached in
`trails`, the second by the more specific scope. Harmless, and on iOS installs it does not arise.

Recorded as the alternatives: a directory per map (`/abisko/`) needs the rewrite and the index
Worker to understand prefixes and gains nothing over the flat root; a second origin per map
(`abisko.cairn.zone`, a second module instance) is full isolation with no code, and stays the
fallback if the flat root hits something unforeseen.

### 6.3 The heights are tiles in the bucket, built here

Three ways were weighed: a Worker in front of Lantmäteriet's WCS that imitates the live point
query; a coarse height grid for the box inside the document; and height tiles addressed `z/x/y`
like the map tiles, which is what `atlas` §3.6 decided for the offline pack. **Decided: the
tiles**, because they are the one of the three that `atlas` reuses as they are — same grid, same
addressing, same encoding, same bucket — while a grid inside the document is thrown away with
the document. Uwe, 2026-09-12: build them here and use them directly.

Shape, following `atlas` §3.6 where it has decided and choosing where it has not:

- **Source** Lantmäteriet *Markhöjdmodell Nedladdning*, Avgift Nej, CC BY 4.0, RH 2000 —
  measured 2026-09-12: a keyless STAC API at `https://api.lantmateriet.se/stac-hojd/v1`
  (search by bbox works without a login; the box returns items in collection `mhm-75_6`, 1 m
  GeoTIFF/COG per 2.5 km square, about 20 MB each, roughly 180 squares over the box), and the
  data URLs on `dl1.lantmateriet.se` answer **401** until authenticated with **HTTP basic auth
  and the Geotorget username and password**, after the product has been ordered (free) in
  Geotorget — that is Lantmäteriet's own guide, *Guide, Nedladdning av markhöjdmodell*, step 12.
  COG means the build reads the overview levels by range request and never fetches the 1 m
  data whole. Fallback if the login is a nuisance: *Markhöjdmodell Nedladdning, grid 50+* on the
  same anonymous FTP (`Hojddata_grid_50_plus/`, dated 2015), 50 m posts, coarser than z13 wants.
  The datum is asserted at import, as `atlas` §6.2 requires; RH 2000 and NN2000 are both EVRS
  realisations.
- **Ceiling z13.** At 68.3° N a z13 pixel is 7.1 m; `atlas` measured that z14 over a 10 m model
  is pure upsampling, and a 1 m model resampled to 7 m is still far finer than the 25 m window the
  profile smooths by. The COG overviews are read at the tile's resolution, so the 1 m grid
  never lands on forge whole.
- **Count** for the box, z8 to z13: 2 + 6 + 12 + 30 + 110 + 380 = **540 tiles**. At the
  100–200 KB a lossless 256×256 RGB elevation tile tends to weigh, that is 50–110 MB in the bucket
  — order of magnitude, to be measured on the first build.
- **Encoding** elevation packed into RGB, **PNG, lossless** — `atlas` §3.6's trap: a later
  "optimise the tiles" pass with lossy WebP or JPEG would leave the images looking identical and
  the heights ruined. The packing formula is the build's to choose; Terrarium's
  `(R·256 + G + B/256) − 32768` is the obvious one and gives 1/256 m. (What `atlas` rejected was
  Terrarium's *source*, not its packing.)
- **Address** `dem/lantmateriet/1/{z}/{x}/{y}.png` — a directory per source, because a second
  source (Kartverket DTM10 for Norway) is stacked, not mixed, exactly as the imagery is; and a
  version segment, because the offline store keys tiles by URL, so a rebuild that changes the
  resampling must change the address or kept tiles on a phone would silently mix two builds.
  Loose objects rather than a PMTiles container: the page is Leaflet without a PMTiles reader,
  and the worker intercepts tile URLs. A PMTiles file for `atlas` is assembled from the same tiles
  when `atlas` wants one.
- **Use** the build samples the 4 m mosaic the tiles were cut from for every graph vertex; the
  page fetches the z13 tiles for the legs of a planned route and reads them from the offline
  store when the switch is on. Build and page describe one surface, read at posts and at pixels
  that are 4 m and 7 m apart. **The offline chooser keeps the z13 height tiles over the same set
  the map tiles are kept over**, not the whole box: measured 2026-09-12, the whole box at z13 is
  380 tiles and 35 MB, which on a band along a day's walk is a third again on top of the map
  tiles — not the few per cent this line assumed — while the band's own z13 set is a dozen tiles.
  A straight leg planned offline over kept ground has its profile; one planned off it says it
  has none, which is what the page says anywhere a tile is missing.
- **Caching** long `max-age` on the tiles, since the address carries the version; the deploy
  uploads the directory with `aws s3 sync` and purges nothing for it — `deploy_map.py --tree
  dem`, §4.5.

**Measured 2026-09-12, with the login from sops** (the §8.1 questions about the COGs):

- The STAC search over the box returns **212 items** (not the ~180 guessed), ids `756_63_5000`
  to `759_66_7525`, `proj:code` **EPSG:5845** (SWEREF 99 TM with RH 2000 heights), each
  2,500 × 2,500 float32 posts at 1 m, `nodata` −9999, deflate, tiled **512 × 512**, overviews
  **2, 4, 8** with nearest resampling, `AREA_OR_POINT=Area`; `lagesosakerhethojd` 0.2 m,
  `lagesosakerhetplan` 1.0 m; the squares over the box were flown 2022-12 and created 2025-01.
- `dl1.lantmateriet.se` answers **401 without and 200 with** basic auth, and `Accept-Ranges:
  bytes`. GDAL's `/vsicurl/` with `GDAL_HTTP_USERPWD` opens a square in 0.2–0.4 s, reads a
  256 × 256 window in 0.1–0.3 s and the whole 1/8 overview in 0.1 s. Building z8–z13 from the
  1/8 overviews (8 m posts against 7.1 m z13 pixels) reads about 212 × 312² × 4 B ≈ **83 MB**;
  nothing is downloaded whole.
- **Water is a flat surface, not nodata.** A square on Torneträsk is **81 kB** and every post
  reads 341.85 m, the lake's level; a mountain square (`758_64_0000`, above Abiskojaure) is
  11.4 MB and spans 957–1,242 m. Neither holds a nodata cell, so the builder needs no water
  mask for the lakes and must not read a flat 341.85 as missing.
- `rasterio` is a dependency since the build exists (below).

**Built 2026-09-12** — `trails.io.sources.markhojd` (STAC search, the squares read at an overview
by range with the login, the mosaic cached as a GeoTIFF under `.cache/elevation/`),
`trails.processing.dem_tiles` (Terrarium packing, one bilinear warp per tile, resumable,
`index.json`), `trails.utils.tiles` (the grid, shared with the map-tile copy),
`analysis/scripts/dem_tiles.py`, `command make dem`. The first run, as the unit `abisko-dem`
under `sops exec-env`:

| | |
|---|---|
| squares read at 4 m posts | 212 in 45 s, into a 10,000 × 8,750 mosaic, cached as 175 MB |
| tiles z8–z13 | 540 in 62 s, **49.3 MB** |
| a z13 tile | **92.7 kB** mean (§8.1's open figure); a lake tile is 568 bytes |
| peak memory | 1 GB |
| checks | Abisko turiststation reads 385.9 m (385 m on the map), Torneträsk 341.85 m flat |

4 m posts rather than 8, because the overviews are nearest-decimated and a z13 pixel is 7.1 m:
reading the first level finer than the pixel means the bilinear tile never averages posts it
does not have. The 1 GB is the float32 mosaic plus its copy in the warp; fine on forge, and a
box four times the size would want the squares warped one at a time instead.

Uploaded 2026-09-12 with the publish (§7 step 6): `deploy_map.py --tree dem` put the 540 tiles
up in 11 s. The reader is done (§4.4): the Abisko page reads these tiles and the Swedish build reads the mosaic they
were cut from.

### 6.4 The box holds no Norway

Uwe, 2026-09-12: no Norwegian ground is needed. With the west edge at 18.15 E and the north edge
at or below 68.55 N (§2), the box is entirely Swedish, and Lantmäteriet draws all of it.
**Decided:** no blank-tile classification in the downloader and no second provider for this map.
Tiles that straddle the border at the west edge are drawn by Lantmäteriet with white beyond the
line, which is the provider's own rendering of the frontier and reads as such. What would reverse
it is recorded in §9.2, and cannot arise with the box as it stands.

### 6.5 Winter trails are not routable

The Naturvårdsverket trail data carries winter trails (over lakes and bogs) beside summer ones.
**Decided:** the summer network is built from summer trails only; winter-only lines may be drawn
as their own legend row, off by default, and never enter the graph. The August–September use of
this map is the reason.


### 6.6 The relief is shaded, from the model the profile already reads

Uwe, 2026-09-16, with two photographs of a Calazo 1:25 000 sheet of Latnjavággi: *"Gibt es eine
Möglichkeit die Höhenunterschiede auf der digitalen Karte deutlicher hervorzuheben? … Fast schon
ein 3D Effekt."*

**The paper sheet has shading and ours had none** — read off the tiles rather than assumed:
Lantmäteriet's *Topografisk webbkarta* at z14, z15 and z16 over Latnjajávri and Kartverket's
*Topo* at z14 over Lomsdal-Visten carry contours, water and lettering and no relief at all. So the
plasticity is not something to turn up in the sheet; it has to be drawn.

**Decided: cut it here, from the 1 m height model already cached for §6.3.** The mosaic is on
forge (`.cache/elevation/`, 4 m posts), which makes the whole thing a build step rather than a new
source, a new licence or a new login. `trails.processing.shade_tiles` does the cutting,
`analysis/scripts/shade_tiles.py` and `make shade` drive it, and the tree goes up with
`--tree shade` beside the other two.

**Black with an alpha channel, not a grey image multiplied over the sheet.** Both were built and
looked at over the same ground. A grey hillshade darkens level ground too — level ground shades to
`sin(altitude)`, not to white — and the whole map goes grey with it. With the shadow written as
`alpha = clip(1 − shade / sin(altitude), 0, 1)` the level and the lit are transparent, so the sheet
keeps its cream, its water and its forest, and only what is turned away from the light darkens.

**Light from the north-west at 45°.** North-west is what relief shading has used since it was drawn
by hand: a reader takes a lit south-east slope as convex, so lighting from the other quarter turns
every valley into a ridge. It is also the one thing here a unit test is worth — `np.gradient` hands
back rows first, and naming those two the other way round lights the map from the wrong side while
every number in it stays plausible.

**Drawn at 0.55, and that figure was measured rather than chosen.** What bounds it is not the
contours: the shadow multiplies line and ground alike, so their contrast in the darkest tenth of a
crop holds at **1.49:1 at 35 % and 1.42:1 at 80 %**. What bounds it is absolute darkness — at 70 %
a steep flank goes near-black and the water and forest colours go with it. At 55 % shaded ground is
**68 % darker** than unshaded. It touches little of the sheet: alpha is over 0.5 on **6 %** of a
z12 view of Kårsavagge and **14 %** of a z15 view of a steep flank. The number lives in
`ShadeTiles.opacity` and costs no rebuild.

**Cut to z15, and not for the usual reason.** A z14 tree and a z15 tree show the *same* ground: the
heights are smoothed by one post before they are differentiated, so neither resolves anything finer
than about 8 m. What the deeper tree buys is that the image is not blown up — compared over a steep
flank, z14 is visibly soft at z16 where z15 is not, and at z17 both are soft and neither is blocky.
z16 would only redraw z15's ground on a finer grid. The offline panel keeps to z16 by default,
which is where that difference is, so **z15**.

**Stored in 64 steps of transparency.** A shadow is a smooth ramp and PNG pays for every level of
it: at full precision a z14 tile is 24.7 kB, at 64 steps 14.4 kB. The cost in the picture is one
step of `255/63` in alpha, which over the sheet's cream at 0.55 is **2.2 levels of 255** — under
where banding is seen, and far under what a 4 m model can justify. 32 steps halves it again and
puts a 4.3-level step into a smooth slope. A palette PNG with `tRNS` was tried in place of RGBA and
came out slightly *larger*.

**Every tile is computed with a 12 px margin and cut back**, or the gradient at a tile's border has
no neighbour and every join in the tree draws as a line — over a whole map, a grid. The resampling
changes with the zoom for the same reason: bilinear while a tile pixel is finer than a post,
averaged once it is coarser, because bilinear downsampling takes one post of many and aliases the
shade into noise.

**Address** `shade/lantmateriet/1/{z}/{x}/{y}.png` — a directory per source and a version segment,
for the reason §6.3 gives: the offline store keys tiles by URL, so a rebuild that changes the
shading must change the address or a phone would silently mix two builds.

**On the page** it is a tile layer over the base and under everything the page draws itself,
`zIndex` 250 against the overlay pane's 400, with a checkbox under the sheet in the *Base map*
panel and **on when the page opens**. It had a row in the legend for a day. Uwe, 2026-09-16:
*"Gehört es wirklich da hin? Oder ist das nicht eine andere Art von Karten overlay?"* — and it is:
the legend's own hint is *every line and point drawn here, and what each one is*, while the base-map
panel's is *which sheet is drawn underneath*. The relief is neither a line nor a point, has no
colour to explain and no count, and answers the second question, so it sits beside the choice of
sheet — which on Abisko also gives that panel a choice to offer, where before it held one radio. It is a drawing decision rather than data, and the one case it gets in the way —
a screen read in full sun — is the reader's to judge. Two things had to be said explicitly for it:
the layer is held to the box the tree was cut to, or panning west of it collects the 404s §8.2
taught us to fear; and it carries a `trailsShade` flag, because the offline panel finds the sheet
by walking the map's layers for the first one with tiles, and a reader who switches the base map
off and on again puts it back *behind* the overlay.

**Offline it is kept at every level, unlike the heights.** The heights are read at one zoom and so
kept at one; the relief is drawn, so a reader who keeps ground to z16 and pans out to z12 wants it
there too. The worker takes a third prefix and the run walks each level three times — sheet, then
heights where that level carries them, then relief. An offline run also never asks a tree for a
level it does not have: holding every layer to the kept depth would ask the shadow for a z16 tile
nobody built and blank it, so the clamp is `min(kept, what the layer was built with)`.

**What it costs.** Measured on the built page against the published one, same selections:

| kept | sheet and heights | with the relief | added |
|---|---|---|---|
| a band along a track, z16 | 30.0 MB | 41.2 MB | +11.2 MB |
| a band along a track, z17 | 37.6 MB | 48.7 MB | +11.1 MB |
| the whole map, z16 | 398.7 MB | 502.4 MB | +103.7 MB |
| the whole map, z17 | 903.3 MB | 1,007.0 MB | +103.7 MB |

The addition is flat, because the relief stops at z15 and the two deep levels — where a band spends
most of what it spends — carry none. The whole tree in the bucket is **9,330 tiles and 104.0 MB**,
cut in 17 minutes; at full alpha precision it was 181 MB.

**Nothing a phone already holds is touched by this.** The sheet's addresses do not move, so kept
tiles still answer; the stand row gains a `shade` entry that is absent on an older device and reads
as *not moved* rather than as stale. A reader who keeps ground and does not run Keep again simply
has no relief while the switch is on — the worker answers a tile it does not hold with a 1 × 1
**transparent** PNG, which over a shadow layer draws nothing at all. The token the panel puts on a
sheet's URL to get past the browser's image cache is put on this layer too, so the shadow comes
back the moment the ground is kept.

### 6.7 The slope is classed over the relief, in the classes the avalanche services publish

Uwe, 2026-09-16, the evening the relief went up: *"Ließe sich ein ähnliches Overlay auch für die
Steigung bauen? Das sollte auch in Kombination mit dem Schatten-Overlay funktionieren."* Then,
with Outdooractive's *Slope angle* legend as a reference and not a template: *"Müssen wir nicht so
machen."*

**Two measures, not one.** The profile already grades steepness — the *path's*, in per cent along
it, over a 25 m window, in four bands whose lowest edge was set against the model's own noise
(§9, `GRADIENT_BANDS`: 15, 25 and 40 %, which is 8.5°, 14° and 22°). That is the wrong instrument
for the question a reader asks off the paths. The network stays under 22° on 98.5 % of its length
because paths were laid where the ground allows, while a fifth of the box's ground is over 20°: a
path crossing a 30° hillside in zigzags at 12 % is green on the profile and the ground under it is
orange here, and both are right. So the overlay reads the ground's slope down its fall line, in
degrees, and shares the profile's *colours* and nothing else — Uwe asked whether the two should
agree, and the answer is that they cannot, because 25° along a path is 47 %, a grade no path holds,
and 22° on the ground would colour a fifth of Abisko red. The legend says which it measures.

**The classes are documented ones, with one of ours below them.** Looked for and not found: no
hiking scale publishes a threshold in degrees. The SAC scale T1–T6 describes terrain in words
(*sehr steile Grashänge*, *Kletterstellen bis II*), the DNT's green-to-black grades in words plus
height and length, the Alpenverein's categories likewise; the one number the DAV gives for pathless
ground is that a fall becomes dangerous from about 30°. What is documented is the avalanche
practice: the SLF's recommendation of 30–35, 35–40, 40–45 and over 45, which swisstopo draws as
*Hangneigungsklassen ab 30 Grad* and extended in January 2026, agreed with the SLF and the SAC, by
a class over 50; the EAWS glossary's *moderately steep* under 30°, *steep* over it, *very steep,
extreme* over about 40°. Outdooractive, CalTopo and Gaia all build on those. Winter classes, chosen
where slabs release; summer walking is decided lower — from about 25° cross-country is laborious,
from 35° the hands come out — so one class of our own at 25° sits under the SLF's four, marked
*(ours)* in the legend, and the boundaries above it are nobody's taste.

**A class over 45 stays, and it names the angle rather than the walkability.** Uwe: *"Heißt 45
wirklich, ich kann nicht mehr gehen? … eine Art Stufen durch Felsen … geht das schon. Aber ja,
glatte Fläche geht nicht."* Right, and the model cannot see the difference: at 4 m a post a stepped
rock slope reads its mean angle exactly as a smooth slab does. So the legend carries degrees and no
words like *extreme*, and the reading is the reader's. Over 50° is a real class here because the
4 m model resolves it — swisstopo's is cut from 10 m — and it holds **0.7 %** of the ground, the
walls of Lapporten and the north face of Njulla.

**And one more over 55, ours, the morning after.** Uwe, from the published page over Latnjajávri:
*"Es gibt Wanderwege, die durch die aktuell höchste Klasse laufen."* They do — the marked trail
down to Kårsavaggestugan crosses ground the model reads as over 50° — so the top class was
splitting nothing: the steps a path takes and the walls no path crosses were one colour. A
boundary at 55° parts them. It is ours, like the 25° one, and the legend says so; it holds
**0.4 %** of the ground, the 50–55 class 0.3 %.

Measured over the whole model, 101 million posts, the slope read over an 8 m baseline after the
relief's own smoothing:

| class | source | share of the ground |
|---|---|---|
| 25–30° | ours | 5.2 % |
| 30–35° | SLF | 3.3 % |
| 35–40° | SLF | 1.9 % |
| 40–45° | SLF | 0.9 % |
| 45–50° | SLF | 0.5 % |
| 50–55° | swisstopo 2026 | 0.3 % |
| 55° and more | ours | 0.4 % |

An eighth of the ground coloured. Outdooractive's own scale from 30° would put six colours on 7 %
of it and three of them on one per cent, which is more legend than terrain.

**Cut exactly as the relief is.** `trails.processing.slope_tiles` reads the same mosaic through
the relief's own `plan()` and `cut()` — same smoothing, same margin, same resampling per level, same
z8–z15 — so a class boundary and a shadow's edge fall in the same place, and a unit test holds the
two trees to that. The slope is the magnitude of the gradient the shade already takes the normal
from. `make slope` drives it and the tree goes up with `--tree slope`, the fourth.

**A palette PNG with the alpha in it.** Flat colour compresses where a shadow's ramp does not: a
z15 tile is a few kilobytes against the relief's 9.4, and the whole tree **9,330 tiles** and about
a quarter of the relief's 104 MB — the first build, six classes, was 24.7 MB in 12 minutes. Index
0 is transparent and the classes follow, at an alpha of 150 (0.59), so a tile can be looked at on
its own and the page draws it at full strength.

**Multiplied over the sheet, not laid on it — the lettering was the first thing lost.** The first
build was drawn opaquely, and from the phone the same morning: *"Die Beschriftungen des Base
Layers liegen unter den Farben. Ließe sich die Beschriftung auch als eigenes Overlay bauen?"*
Looked for: Lantmäteriet's open download has no text-only sheet; the licensed layered WMS
(*Topografisk webbkarta Visning, skiktindelad*) has a `text` layer and a text-free base, at
125,000 kr a year or per request under that cap, and its images are for one's own application at
the service, not for a bucket; Topografi 50's `textpunkt` layer, already cached, carries the
sheet's 349 labels over the box with direction and spacing — but drawn over a sheet that keeps its
own lettering they would ghost. So no overlay. Instead the layer is drawn with
`mix-blend-mode: multiply`, as a printer overprints transparent ink: black multiplied by any
colour is black, and the ground under a class becomes `base × (1 − α + α · colour)` — the
layer's own alpha keeps the darkening partial. Black lettering on the sheet's cream, 16:1 with no
overlay, measured per class:

| class | drawn opaquely, first palette | multiplied, first palette | multiplied, this palette |
|---|---|---|---|
| 25–30° | 2.7:1 | 13.7:1 | 15.1:1 |
| 30–35° | 3.0:1 | 11.5:1 | 13.6:1 |
| 35–40° | 3.2:1 | 9.0:1 | 11.7:1 |
| 40–45° | 3.4:1 | 6.4:1 | 10.5:1 |
| 45–50° | 3.6:1 | 5.5:1 | 10.7:1 |
| 50–55° | 3.7:1 | 4.6:1 | 10.4:1 |
| 55° and more | — | 4.6:1 | 12.0:1 |

The first palette survived multiplying at the bottom and went marginal at the top, because
multiplying darkens the ground by the colour and its top three were dark on purpose. So the
palette is the light one: pale yellow, amber, orange, coral, pink, lilac, light blue — chosen on a
second mockup (`~/mockups/slope-multiply`, since deleted) over Latnjajávri and Kårsavaggestugan,
where the blend and the seven classes were looked at against the first palette. Uwe: *"Ja, setze
das so um."* The test holds every colour to 7:1 or better under the blend. The tree is **version 2**
(`slope/lantmateriet/2/`) for the reason §6.3 gives: the tiles changed, so the address changes,
and a phone that kept version 1 reads it as *moved* rather than mixing the two.

**On the page** it is a tile layer over the relief, `zIndex` 260 against the relief's 250 and the
overlay pane's 400, with the class name the theme's one blend rule hangs on. It carries a
`trailsSlope` flag for the reason the relief carries its own, and is held to the box for the same
reason. The blend was measured to be on the layer's container in Firefox and off again with the
mockup's switch; iOS Safari is Uwe's to confirm from the phone. Its checkbox sits under the relief's in the *Base
map* panel — it is the same kind of thing, how the ground is drawn — with the seven colour rows,
the two that are ours saying so, and the line *steepness of the ground down its fall line; the
profile grades the path* under it, shown only while it is on. **Off when the page opens**: it answers a question off the paths, and an
eighth of the ground coloured is a lot of colour for a reader following a marked trail.

**Offline it is kept whether or not it is on.** The switch is the reader's to flip in the field,
and a class that was never kept is a blank tile where a wall is. So the worker takes a fourth
prefix, the run walks each level a fourth time after the relief, the panel prices the tree at its
own weights, and the stand row gains a `slope` entry — absent on an older device and read as *not
moved*. Nothing a phone already holds is touched, exactly as for the relief; a tile the worker does
not hold is answered with the same transparent 1 × 1 PNG, which for a class layer draws nothing.

**What it costs.** Measured on the built page with the panel open, same selections as §6.6's
table, against the figures there:

| kept | with the relief | with the slope classes too | added |
|---|---|---|---|
| a band along a track, z16 | 41.2 MB | 43.6 MB | +2.4 MB |
| a band along a track, z17 | 48.7 MB | 51.2 MB | +2.5 MB |
| the whole map, z16 | 502.4 MB | 527.4 MB | +25.0 MB |
| the whole map, z17 | 1,007.0 MB | 1,031.9 MB | +24.9 MB |

Flat for the same reason the relief's was, and a quarter of it. The whole map at its cap is now
166,035 tiles: the sheet's 146,975, the 440 height tiles, and 9,310 each of relief and slope. The
figures are version 2's — **9,330 tiles, 25.0 MB, cut in 12 minutes**; version 1 with six classes
was 24.7 MB and priced 0.3 MB less.
---

## 7. The order of work

1. **Geotorget account** — done 2026-09-12 as a private person, `lantmateriet@uweeisele.eu`.
   What is ordered there, all free: *Markhöjdmodell Nedladdning* (§6.3) and *Topografi 50
   Nedladdning, vektor* (§5), the latter as *Abonnemang*, SWEREF 99 TM, GeoPackage, *Sverige*.
   Not Topografi 10 — its legal review wants a personnummer. **Both ordered 2026-09-12**: Topografi 50
   is Lantmäteriet's case LM2026/139831, the height model LM2026/139832; the deliveries are
   followed under *Mitt konto – Ärenden*. **Nothing with a fee**, and the tiles need no order at all — they
   come off the anonymous FTP (§3). The login goes into `home/trails-map`'s sops file as
   `GEOTORGET_USERNAME` / `GEOTORGET_PASSWORD`, the names its `secrets.sops.env.example`
   records; the build reads them from the environment for the STAC downloads and the download
   API (Ortnamn Nedladdning, vektor is free and unreviewed too, should the names want it).
   No API key exists in this design any more.
   **Both deliveries were there the same day** (measured 2026-09-12, 12:00): *Mitt konto –
   Ärenden* shows both as *Lyckad*, the height model as a *Behörighet* (the login may read the
   COGs, which §6.3 used), Topografi 50 as an *Abonnemang* with an order id and a delivery of
   fourteen files, 5.37 GB, produced 2026-09-08, available fourteen days, new deliveries on
   request. **The delivery is fetched through *Geotorget Nedladdning***, a documented API on
   `api.lantmateriet.se/geotorget/nedladdning/v1/{order}` with basic auth for private persons:
   read the order, read the latest delivery, list its files, download each by a signed path.
   **It has to be ordered too**, as its own free product in Geotorget — without that the same
   login answers `403 Scope validation failed` on every call (measured; `401` without the
   login, so the login itself is right). **Ordered by Uwe the same afternoon**, and the order
   id is in `home/trails-map`'s sops file as `GEOTORGET_TOPOGRAFI50_ORDER` (the id *Ärenden*
   shows on the Topografi 50 order line — an identifier, not a credential, but it names an
   account): the three calls answer 200, and the loader fetched a theme through the API (§9.7).
   The delivery on disk was fetched once through the browser session earlier that day.
2. *Fixed, §9.14.* **Infrastructure** — nothing. The bucket takes prefixes without a change (§6.2), and there
   is no Worker (§6.1).
3. *Fixed, §9.16.* **`trails`, the plumbing** — `--park` (§4.1), the provider blob with `TOP` and `WEIGHT` per
   provider (§4.2, §3), `drive_map.py` gains `--page`. And **the tile copy**, which is done as
   code since 2026-09-12: `trails.io.remote_sqlite` opens the FTP GeoPackage as an SQLite
   database through an `apsw` VFS with 1 MB blocks, `trails.io.sources.lantmateriet` copies the
   box column by column into `analysis/output/tiles/lantmateriet/topowebb/1/{z}/{x}/{y}.png`,
   resumable, with an `index.json` beside the tiles; `command make tiles` drives it, and the
   full z8–z17 run took 916 s. **And the upload**, also code since 2026-09-12: `deploy_map.py
   --tree tiles` mirrors the tree into the bucket by `aws s3 sync` (§4.5), which is `just deploy
   --tree tiles` from `home/trails-map`; run 2026-09-12 as the unit `abisko-tiles-upload` at
   Uwe's word: **118,967 objects, 700 MB, 3,400 s**, none failed, at 60 objects/s for the first
   40,000 and 25–35/s after — R2's pace, not forge's (12 min CPU in 57). A z13 tile fetched
   from the edge is byte-identical to the file, served `image/png` with the year-long header;
   a second `--dry-run` finds nothing left to upload. **`--park`, the provider blob and the companions per map are
   done** the same day (§4.1, §4.2, §6.2), in the library, the build and the deploy; what
   remains of this step is the variant icon — **drawn 2026-09-12** (§6.2); the step is done.
4. *Fixed, §9.15.* **`network/sweden.py`** — Topografi 50 for the ground, Naturvårdsverket's trail register
   for the attributes, OSM for what neither draws; winter trails and reindeer routes excluded
   (§6.5). **Done 2026-09-12.** What was shared with Norway moved into `network/graphs.py`
   (parameters, fingerprint, derived fields, the protected-area table, the build) and
   `norway.py` delegates to it with its cache keys byte-identical — three keys measured before
   the move are pinned in a test. The Swedish module is five sources, not three: the register
   (*Leder*, identity the state trail), **Topografi 50's marked trails as a source of their
   own**, its paths, its roads, OSM, and the empty ferries. The split was forced by the
   product: Topografi 50 draws the marked trail *and* the worn path under it as two objects on
   one geometry — 148 km shared over the box in 6,570 collinear segments — and noded as one
   source those cut each other at every vertex, where the identity rule, every arm carrying
   the same trail name, ended a chain: 9,136 path chains at 69 m. As two sources, meeting only
   in the merged graph as Turrutebasen and FKB do, the first build over the box reads:
   Leder 30 lines → 16 chains (11.6 km mean), Topografi 50 trails 151 → 72, paths 404 → 197,
   roads 170 → 69, OSM 850 → 459; **813 chains, 39,775 edges, 18,545 nodes, 457 bridged
   connectors**; 34,117 edges read marked, 3,405 unmarked, 1,796 unknown; 17 edges run where
   no source records a path. Heights: 317,417 samples off the cached 4 m mosaic, none outside
   it, 342–1,730 m. **44 s in all**, OSM cached, against Lomsdal's quarter of an hour: the
   ground is read off a file rather than asked of a service. The Swedish `measure` needs no
   point store. **The page, the same evening**: `lomsdal_visten.py --park abisko` builds
   `abisko.html` through `build_sweden` (§4.1) — 19 legend rows: roads, the winter lines off by
   default, OSM / Topografi 50 paths / Topografi 50 marked trails / the register's state
   trails each split at the park boundary, cabins (49, 13 named — 7 off the register's
   settlement names within 150 m, 6 off OSM), the register's 24 facilities, 62 footbridges,
   fords and car parks, 35 OSM
   shelters, and three name layers off the place-name register (§9.9): 391 names over the box,
   334 drawn after thinning at 1 km — 171 terrain, 114 lakes, 43 watercourses, 30 settlements,
   23 facilities, 5 glaciers — 218 of them at the size the map's lettering gives them, the
   rest at the smallest (198 of the 345 places in the box once the languages are paired and
   the lettering is matched on either name, §9.15); 10 rivers named off the register within 60 m.
   The water grid is 1,399 × 1,292 cells, 14.1 % water, 32 kB; 128 river surfaces at 9,441
   vertices once clipped to the box (144 over the envelope), 10 of them named; the graph payload 0.84 MB in a **3.3 MB page** (Lomsdal's is
   16.6). Five GPX files. `route_graph.py --park abisko` reports the same cached graph: the
   state trail *BD 21* resolves to one register chain of 30.7 km (+612 / −498 m) and two
   Topografi 50 chains named from it; the park shares a boundary with the research station's
   reserve and overlaps nothing. **Measured in Firefox on the built page**: plan mode over open
   fell south-west of Abiskojaure, a 3.65 km straight leg, 730 samples off five z13 tiles,
   +303 / −197 m, high 1,250.2 low 1,048.9; the build's mosaic along the same line reads
   +303 / −200, 1,250.5 / 1,048.4 — and over 2,000 random points of the box the page's tile
   reading and the build's mosaic reading differ by 0.07 m at the median, 0.47 m at the 95th
   percentile, 3.3 m at worst. No page errors. The graph itself: 22 components, the largest
   1,367 km and 95 % of the network, reaching 99 % of the park's 14.2 km north to south, with
   *Abisko* on it. **Driven by `make drive` the same evening** (§9.10).
5. *Fixed, §9.15.* **Heights** — the tile build (§6.3). **Done 2026-09-12**: `command make dem` writes
   `analysis/output/dem/lantmateriet/1/` from the STAC COGs with the login, 540 tiles, 49 MB,
   in a minute; uploaded with the publish in step 6. **The reader is done too** (§4.4): the page reads the tiles for
   a straight leg and the build reads the mosaic they were cut from, measured against each
   other in step 4.
6. *Fixed, §9.15.* **Acceptance and publish** — the structural readings of `make drive` against the Abisko page,
   then `command make map ARGS="--park abisko"`, then `deploy_map.py --map abisko --tree tiles --tree dem`,
   which mirrors the trees first and then uploads the page and its own companions. **The drive
   is done, 2026-09-12** (§9.10): `command make drive ARGS="--page analysis/output/abisko.html"`
   read **570 readings, none broken** that evening, the 22 figures the page's build gives
   recorded in its scene, and three checks skipped for ground nobody had measured on this box;
   two of those got their ground the same night (§9.11) and the suite its skip rule after the
   review (§9.14), and the last two their ground later that night (§9.19), so the drive reads
   **603 readings, none skipped, none broken**, and the Lomsdal-Visten drive **602 and none moved**. **Published 2026-09-12 at Uwe's word**: the page
   rebuilt (12 s, byte-identical, 3.3 MB → 1.12 MB brotli), `just deploy --map abisko --tree tiles
   --tree dem` from `home/trails-map` — the tile sync found nothing to upload in 103 s, the 540
   height tiles (49.3 MB) went up in 11 s, then the page, its worker, manifest and four icons, and
   the edge purged. Read back from the edge: a height tile, a map tile and the page byte-identical
   to the files. **https://atlas.cairn.zone/abisko**. The step is done; §7 is done.

Step 3's tile copy needs no credential and can start now; steps 4 and 5 need the login in sops.
**The whole chain is one target since 2026-09-12**: `command make abisko` runs tiles, dem, the
graph with its report and the page in order, and `just abisko` from `home/trails-map` runs it with
the login and the order id in the environment. Measured on a warm cache: the tile copy finds all 118,967 tiles there in 1.5 s, the height tiles all 540 in 0.0 s, the graph comes off the cache, the page builds in 12 s — **20 s from start to `abisko.html`**.

---

## 8. Open

Triggers, not deadlines — the convention `atlas` §9 and `pipeline/TODO.md` use. When an item is
settled, move it to §9 with the date and what settled it.

### 8.1 What the first builds measure

*Trigger: a second box.* The tile copy's cost and the cartography check are answered
(§3, §9.5), and so are the COG questions — overviews, nodata, water, the login — in §6.3.
The packed z13 tile weighs 92.7 kB (§6.3). Still open: whether Geotorget offers the tile
product cut to an area — worth asking only for a second box. How often the FTP files are
refreshed no longer matters: a new stand is picked up by the next `make` (§9.20). The WFS question of step 4 is settled (§9.6): the files replace it.


### 8.2 The review of 2026-09-12

*Trigger: now — fixed in this order, each moving to §9 as it lands.* The whole app was
reviewed on 2026-09-12 evening at Uwe's word: five readers (sources and build, the page in the
browser, deploy and operations, the drive suite, this document) plus the live site measured by
hand; every high and medium finding checked against the code or the bucket before it was
written here. What held: the two maps' worker scopes, databases, caches and manifests are
separate under measurement; the height reader decodes exactly; the deploy never deletes, the
tiles are immutable and byte-identical to the build; no credential reaches argv, a URL or the
journal; §6.5 is enforced; every CRS is explicit; the tile tree matches its inventory.

**High**

1. *Fixed, §9.13.* **The whole-map download stalls on Abisko at once.** The offline panel's `padded()` lays a
   ring of one tile round the box on every level; the tree is cut exactly to the box, so the
   ring is 404 on the bucket (measured live: `11/1126/485` 404, `11/1127/485` 200). Twelve
   refusals in a row read as *stalled*, and a stalled run switches offline **on** over some 34
   tiles. Lomsdal is untouched because Kartverket answers the ring. The fix is to clip the ring
   to the tree's extent and to stop counting the bucket's own 404 as a stall.
2. **The drive can shrink silently.** A `long_chain` the page no longer holds returns after one
   skip, some 520 readings vanish and the exit code is 0; skips never reach the exit code and a
   skip by choice looks like a skip by failure. An unrecorded figure that reads `None` or
   `False` passes instead of being NEW. Two readings in the stations check are not emitted at
   all when their control is missing.
3. **Status lines here contradict each other.** §6.3 and §7.5 still said *not uploaded*; §7.6
   still said 570 readings; §5's counts were from before the loaders (8 fords not 6, 49 cabins
   not 46, 128 river surfaces with 10 named, not 144/11 or 128/7) and its cabin and river names
   were described as coming off the lettering, which stopped being so with Ortnamn (§9.9);
   `make map --park abisko` is not a form `make` accepts.

**Medium**

4. `ortnamn.paired` joins a later-language point to the first same-type head the STRtree
   returns within 500 m, not the nearest; today's 13 joins are all right, by GEOS order only.
5. The lettering size takes the nearest label within 500 m and then asks for the same name; 7 of
   210 lettered places lose their size — Kungsleden twice, Dag Hammarskjöldsleden twice,
   Kårsajåkka (its own Sámi label *Gorsajohka* is nearer), Ábeskoeatnu, Skoabákti. Match on the
   place's names, both of them.
6. The search's `fold()` folds ø, æ, å and every combining mark, but ŋ, ŧ and đ decompose to
   nothing; seven names on this page carry ŋ (Hoŋgá, Gorsajiekŋa, Iŋggájávri, …) and *hongga*
   does not find Hoŋggá.
7. *Fixed, §9.17.* `/abisko/` with a slash is a real address (the trailing-slash rewrite) that draws the map,
   but the relative `abisko-sw.js`, manifest and icons resolve under `/abisko/` and answer 404;
   the registered scope becomes `/abisko/abisko`. The same for `/lomsdal-visten/`.
8. *Fixed, §9.18.* `copy_tiles` records the FTP file's modification time in `index.json` but never compares it
   with the tree already on disk, so a republished file could be mixed under the immutable `/1/`.
9. *Fixed, §9.18.* `just abisko` hands every value in the sops file to the build, the deploy key pair and the
   purge token included; the build needs the three `GEOTORGET_*` values.
10. *Fixed, §9.14.* Drive tolerances loosened for this page and weakened for both: the route bar from 30 % over
    the flight to 5 %; the crossed-water figures recorded as 0 (a dry bay by construction), so
    an `undefined` crossing passes here; the give-up timing at ±14 s cannot tell three attempts
    from one.
11. *Fixed, §9.18.* An interrupted `zipfile.extract` leaves a truncated GeoPackage at its final path that every
    later run accepts (`topografi50`, `ortnamn`); the downloads themselves go part-then-rename.

**Low**

12. *Fixed, §9.15.* The Swedish branch draws 26 of 391 names outside the box, and cabins, facilities and trail
    points are not clipped either; the Norwegian branch clips its names.
13. *Fixed, §9.18.* `force_download` reaches only the `ovrig_vag` read in `sweden.py`; `approach_km` sits in the
    graph fingerprint though the box build ignores it, so the docstring's own example rebuilds
    an identical graph; Topografi 50 `Vinterled` lines are stamped *Topografi 50 paths*;
    `--trail-name-m`'s help speaks of FKB.
14. *Fixed, §9.18.* Deploy: `check()` reads the first 15 bytes and cannot see a truncated page; the tree-only
    success line names `/tiles/`, which is 404; the index page shows the stored (brotli) size,
    1.1 MB for a 3.3 MB page; `README.md` there still says *No offline / PWA support* and
    *uploading `br` would break clients*, and links a heading that is not there.
15. *Fixed, §9.16.* `analysis/README.md` and the Makefile quote 278 readings, 400 s and *three objects*; the
    drive's docstring says a minute; §9.5's copy estimate predates the measured 916 s; §9.11
    says 22 m and then 49 m for the same river width; §9.12 and `ortnamn.py`'s comment disagree
    about Trollsjön/Geargejávri; §8.1's trigger names steps that are done.

### 8.3 Looking a place up while planning

*Trigger: somebody wanting a hut's page with plan mode on.* With plan mode on every tap on the map
is a waypoint, so no place can be selected until the mode is switched off — which is why *Add to
the plan* is offered with the mode off and leaves it off (§9.28). Uwe named the alternative when
that was settled: a switch in plan mode that stops a tap from placing a waypoint, so a place could
be read and added without leaving the mode. Today the mode switch is that switch, and the search
reaches a place either way; worth building only if the round trip through *Done* turns out to be
what people trip over.

---

## 9. Settled

### 9.1 Where Kedketjårro is — dropped, 2026-09-12

It was the north marker, and it was never found: not in OSM (no `natural=peak` by that name in
68.38–68.75 N, 18.2–19.3 E; 51 named peaks listed), not in Lantmäteriet's place-name search
under `Kedketjårro`, `Kädketjårro`, `Kedke`, nor under the North Sami form `Geađgečorru`
(Sami *geađgi*, stone; *čorru*, ridge — the pattern that turns `Lullehačorru` into
`Lullehatjårro`). The only `-tjårro` hit near Abisko is Adnjetjårro at 68.212 N, 18.655 E, which
is south. **Settled by Uwe:** the E10 sets the north edge (§2), and Kedketjårro plays no part
any more. Kept here so nobody searches for it again.

### 9.2 Whether two providers must be stacked — not for this box, 2026-09-12

The box holds no Norway (§6.4): west edge 18.15 E, north edge 68.46 N, well south of the
68.55 N where the border turns east. If the box ever grows past that, the `atlas` §3.5/§3.7
mechanism returns: classify every downloaded tile, drop Lantmäteriet's white ones, and draw
Kartverket beneath. The downloader today stores anything that answers 200 (`maps.py` ≈ line
16963), so white would be kept as terrain and reported as coverage; the classification is a
byte-size threshold first and a decode second.

### 9.3 What Lantmäteriet's terms say — measured, 2026-09-12

Every live tile service is paid; the free product is the tiles as files, with attribution; the
height model is free under CC BY 4.0 behind the Geotorget login; Topografi 10 is free with
attribution. All in §3, §5 and §6.3, with how each was read. The purchase Uwe was about to make
— 10,375 kr/år for the cache service — is not needed.

### 9.4 The date of the trip — does not matter, 2026-09-12

Uwe: no deadline, and no quality given up for one. Everything in §7 is done properly and in
order.

### 9.5 Whether the free file draws the same map as the paid service — yes, 2026-09-12

Pixel-aligned and indistinguishable, measured on the box's centre tile at z13 (§3); the file's
PNGs are indexed and less than half the size. And the copy was estimated at 0.048 s a tile
and measured at 916 s for the whole box (§3), once.

---

### 9.6 Whether Naturvårdsverket's WFS is needed — no, 2026-09-12

The WFS answered 503 all day (§8.1 as it stood). It is not needed: the same data is published
as nightly files under `geodata.naturvardsverket.se/nedladdning/` — `naturvardsregistret/` with
one zipped shapefile per protection form (`NP.zip`, `NR.zip`, `NVO.zip`, `DVO.zip`, `KR.zip`,
`NM.zip`, `LBSO.zip`, `OBO.zip`, all with `NVRID`, `NAMN`, `SKYDDSTYP`, rewritten 06:50 daily)
and `friluftsliv/` with `Leder_shp.zip` and `Anordningar_shp.zip` (rewritten 06:26 daily). No
login, no key, no server that goes away. `io/sources/naturvardsregistret.py` reads both, and the
file's own date is its version. Two things the catalogue record had left open are answered by
the file: the trail register is **nationwide** (34 of the 47 lines over the box lie outside any
protected area), and it separates the seasons by `LKATEGORI` (*Barmarksled* / *Led på snö*), so
§6.5 is a one-line filter.

---

### 9.7 Whether the delivery API works with a private login — yes, 2026-09-12

Once *Geotorget Nedladdning* was ordered as its own product, the same login that had answered
403 answers 200 on the order, the latest delivery and the file list. `topografi50.Source` run
against it: `delivery(force_download=True)` finds the same 2026-09-08 delivery and its directory,
a missing theme (`norrapolcirkeln`, 7 kB) is fetched by its signed path and unpacked in 1.3 s,
and `byggnadsverk` (116 MB) into an empty cache in 64 s — **1.8 MB/s** from
`api.lantmateriet.se`, so `kommunikation` is five minutes, `mark` twenty-five and the whole
delivery about fifty. A build from an empty cache is therefore an hour of Lantmäteriet downloads
on top of the fifteen minutes of tiles.

### 9.8 The offline panel's keys for a root-relative sheet — fixed, 2026-09-12

The panel keeps a tile in IndexedDB under the address it built from the sheet's template, and
the worker answers a request by looking up `request.url`, which a browser always makes
absolute. For Kartverket the template is absolute and the two agree; for our own bucket the
template is `/tiles/lantmateriet/…`, so every tile the Abisko panel kept would have been stored
under a name the worker never asks for — a whole download that reads as kept and answers
blank. Seen while wiring the height tiles (which have the same root-relative shape), fixed by
resolving the built address against the page's own before it is used as a key. Kartverket's
addresses pass through the same resolution unchanged, so the first map's kept tiles keep their
names.

### 9.9 Ortnamn, behind an order — ordered and read, 2026-09-12

The place-name file answered **403 with the login** in the afternoon, like the delivery API
before its product was ordered. Uwe ordered *Ortnamn Nedladdning, vektor* at 16:05 (case
LM2026/139881, type *Behörighet*, like the height model) and the same address answered **200**
minutes later; the file was fetched in 8 s. Until then the name layers read the map's own
lettering; since then they read the register, and the lettering is kept for the one thing the
register lacks, the size a name is drawn at. `io/sources/ortnamn.py` fetches the file once with
the login and reads the box out of it.

### 9.10 `make drive` for a second page — separated, 2026-09-12

**What was that park's, and where it went.** The suite carried Lomsdal-Visten in three
shapes: the recorded figures (26 of them, each a number in a `Reading`), the ground the checks
stand on and look at (one chain id, the reader's granted position, and fourteen coordinates
inside the checks — the spot on open water, the spot with no path near it, the walk, the kept
area, the fix off the route, the two taps beside a path, the three taps that made a loop, the
sound, the junction by Granlia and the goal across Krutåga), and the page's own names (the
icon files, the database `trails`, the height service's address, the name the search types).
All three now live in a **`Scene`** per page in `drive_map.py`, chosen by the page's stem;
a figure is a `stands(...)` reading that looks its number up in the scene and is reported as
**new** where the scene has none, so the first drive of a page is the run that fills its
scene in. Checks whose ground a scene lacks say they were skipped rather than pretending.
The Abisko page has to be **served**, not opened off the disk: its sheets and height tiles
are addressed from the root, and `file://` has no root — so the suite serves `analysis/output`
itself for that scene, as the offline check always did for every page.

**What the second page found in the suite itself**, none of it visible on the first page:

- Five evaluates handed Leaflet's map object back (`setView`, `setZoom`, `fire` as an
  arrow's whole body) and Playwright serialised it — silently on the Lomsdal page, and on
  the Abisko page a recursion overflow in the client, the map's object graph being deeper
  there. Every such call now returns nothing.
- A fix that lands exactly on the map's centre read as *not panned*: `panned or 1` took a
  distance of 0.0 for *no reading*.
- The archive zooms and *the sheet's own ceiling again* were written as Kartverket's 17–18
  and 18; both now come off the page (the chooser's own levels above 16; the layer's
  `maxNativeZoom` read before the switch holds it down).
- *Terrain it was shown is kept too* zoomed to 10, which is the level the Abisko page opens
  at, so nothing new was asked for; it now zooms a level in from wherever the page opened.
- *A route and not a line across the map* wanted 30 % over the flight; the Abisko valley's
  path gives 27 %, and a line across the map gives 0 % — the bar is 5 % now, which is what
  the reading was for.
- *The lifted band is worth looking at* assumed enough relief: Kungsleden along the valley
  floor is 150 m over 30 km, which the page's own cap (×10, so as not to blow a molehill
  up) keeps a ribbon. The reading accepts a band at the cap.
- *A leg whose heights never arrive* held the request in the browser, which never sees a
  request the page's own worker makes; for a served page the suite's server takes the
  connection and says nothing until the check lets go.
- The offline check's *unkept ground* view had a tile in it that an earlier check had
  browsed, and a browsed tile is served with the switch on by design; the Abisko scene
  looks at the box's south-west corner instead. And the offline visit waited for `> 11000`
  chains drawn — Lomsdal's count — where it now waits for as many as the online visit drew.

Measured: the Abisko page, 570 readings, 0 broken, 22 recorded, 3 skipped, about ten
minutes as a transient unit; the Lomsdal-Visten page after the same change, 596 readings, 0 broken, 0 moved, its figures now read out of its scene rather than out of the checks.

### 9.11 The two water checks on Abisko's ground — measured, 2026-09-12

Of the three checks the Abisko scene skipped (§9.10), the two about water were worth the
ground, because they read Abisko's *data* and not only the page's code: 14 % of the box is
water, the page carries 144 river surfaces, and the Kungsleden crosses the Abiskojåkka by
bridges. The two about taps beside a path are page logic alone, green on Lomsdal-Visten, and
stay skipped. Both cases were found by search over the cached graph and Topografi 50's water
polygons rather than by eye, with the page's own prices (a metre of open ground 3, of water 30,
of open ground with *stay on paths* 10) applied to every vertex of every edge within 1.5 km of
the goal, because that is where the page lets a way leave the network.

**The sound's stand-in is a bay of Torneträsk** east of Abisko Östra: two nodes of the network
1.17 km apart with 1.10 km of lake on the line, the road round the bay 3.36 km. Driven: the plan
walks the road, 3.36 km on paths and no water; the goal's way is the same road and walks nothing
straight; from the Kungsleden 7 km off the way is 7.21 km, 6.3 on paths, 0.9 straight, dry.

**The river is the Abiskojåkka below the canyon**: standing on the west-bank path, the goal a node of the Kungsleden
across the river, 721 m off with 24 m of river on the line, the way round by the bridge 5.1 km at
the page's edge costs. Driven: the routed way walks 387 m of path and then 481 m straight, wading
the river, and the page says *crosses Ábeskoeatnu, 22 m wide there* and *steepest 45 % on the
straight part*; *stay on paths* takes the bridge, 4.84 km and nothing straight, and the switch on
the goal's page turns it off again. Three spots were tried before this one held, and each miss
was a lesson about the page's rule rather than the ground: a departure may leave the network at
any **node** (not at any point of an edge, and not at a vertex), the way round is priced at the
**edge costs** (a road 1.3 to the metre, a marked trail 1.05), and the *stay on paths* price has
to beat the cheapest wading departure, not the nearest one. So the search prices every node
within 1.5 km of the goal both ways and keeps only cases with 2 km of margin on each side.

**What the check surfaced about the names.** Of the 144 river surfaces only 11 carry a name,
because a surface is named from the nearest watercourse name within 60 m (§5) and the register
puts most names on the line, not the surface. And the Abiskojåkka's surface is named
**Ábeskoeatnu**: the register carries the Sami and the Swedish name as two points, and the Sami
one lies nearer. So a goal across it says *crosses Ábeskoeatnu, 22 m wide there* — which is
correct, and is the name Lantmäteriet's own sheet prints beside it in the same size, but it is
not the name the trail signs and the guidebooks use. Whether the Swedish name should be preferred
where the register has both is a decision not taken here; the check pins the name the page says
today, so a change will be seen.

With both in the scene the Abisko drive reads **589 readings, none broken, two skipped**
(the two tap cases), and the Lomsdal-Visten page's scene is untouched. The name question is
settled in §9.12.

### 9.12 A place with two names — both shown, Swedish first, 2026-09-12

Uwe's decision on the question §9.11 raised: where the register has a place in two languages,
show both, the Swedish name first because it is what the signs carry, the Sámi one clearly an
alternative, in brackets — *Abiskojåkka (Ábeskoeatnu)*.

**What the register does**, measured over the box: each language is a point of its own, and
they do not coincide. The real pairs sit 46 m (Abiskojåkka / Ábeskoeatnu) to 412 m (Abisko /
Ábeskovvu) apart, Torneträsk / Duortnosjávri four times over the lake at 80–148 m; the first
nearest pair that is two different places is at 637 m, and one real pair, Gorsajökeln /
Gorsajiekŋa, sits at 619 m. Fourteen names are the same string in both languages (the Swedish
form *is* the Sámi one: Eahpárusluoppal, Geargejávri). And 42 of the 43 watercourse names are
Sámi only — the register has the Swedish form for one river in the box, the Abiskojåkka.

**The rule** (`ortnamn.paired`): within 500 m and of the same type, a point of a later language
joins an earlier one's place — Swedish first, then the Sámi languages, Meänkieli and Finnish as
the file lists them; two points of the *same* language are never joined, because two lakes
300 m apart are two lakes; a name spelt the same in both languages is one name. 500 m keeps
every real pair but one and crosses no wrong one; Gorsajökeln stays two names rather than risk
joining two lakes. What it gave over the box that night: 391 names become 369 places, 8 of
them with a second name (the Abiskojåkka, Lapporten, Abisko, Katterjåkk, and Torneträsk four
times), 14 one name in two languages, and Trollsjön stayed beside Geargejávri because the
register calls the lake Geargejávri in Swedish too. *Since the review (§9.15)*: the Sámi point
joins the nearest head, which for Geargejávri is Trollsjön at 240 m rather than the Swedish
Geargejávri, so the map says *Trollsjön (Geargejávri)* and the Swedish Geargejávri stands on
its own; clipped to the box, 365 names become 345 places, 9 with a second name. **Uwe,
2026-09-12: kept that way** — the bracketed name is what a reader wants beside the one on the
signs; the alternative, preferring a head of the same spelling, was offered and not taken.

**Where it shows**: the three name layers, the search box, the cabins' names and the rivers'
names all read the joined places, so a goal across the river now says *crosses Abiskojåkka
(Ábeskoeatnu), 22 m wide there*; the lettering match for a name's size is made on the first
name. The drive's river scene expects the two-language name, so a regression reads as one.

### 9.13 The whole-map download stalled on the box's edge — fixed, 2026-09-12

§8.2 item 1. The offline panel's `padded()` laid a ring of one tile round every scope on every
level and the tree is cut exactly to the box, so on Abisko *the whole map* asked for a row of
tiles that are not there, met twelve 404s in a row and read that as the connection giving
out; a stalled run then switched offline on over the 34 tiles it had. Three changes in
`maps.py`: `Provider` carries an `extent` (the Lantmäteriet tree's box, as `index.json`
records it; Kartverket's is `None` because its cache answers everywhere), the page's `padded`
clips what it adds to that extent and never the core, and a 404 from the source is now *not
there* rather than *refused* — counted apart, not towards the stall, and not weighed as kept
bytes, which a refused tile used to be. Measured on the rebuilt page over the tree served
locally, Playwright Firefox: `needed()` for the whole map at z14 says 2,343 tiles (was 2,735;
the tree plus its 380 height tiles is 2,343); *Keep* fetched 2,343, 0 refused, not stalled,
6.8 s; every one of the 2,373 requests answered 200. The Lomsdal page is unchanged in
behaviour: `EXTENT` is null there and the ring stays.

### 9.14 The drive names what it skips — fixed, 2026-09-12

§8.2 items 2 and 10. A `Scene` now lists the checks it skips by choice in `skips`; a skip the
page forces — a chain the page no longer holds, a control it no longer draws — is reported as
**GONE** and exits 1, and the long-chain skip says that every check past it went with it.
`Reading.passed` is false for an unrecorded figure whatever it read, so `None` and `False` are
NEW rather than ok. The stations check emits a failing reading where a row or its button
cannot be found instead of leaving the reading out. The route bar is a scene figure again,
`way_over_flight`: 1.3 for Lomsdal-Visten as it was, 1.2 for Abisko (27 % measured), instead of
5 % for both, which would pass a router that snaps to a node and draws one straight line. Two
invariants say the crossed-water figure *is* a number before the figure says it is 0, and one
says the give-up took more than 12 s, which two attempts cannot. Driven: Abisko 595 readings,
none broken, two skipped by the scene; Lomsdal-Visten 602, none broken, none skipped.

### 9.15 The names: nearest head, either name for the lettering, the box, the search — fixed, 2026-09-12

§8.2 items 4, 5, 6 and 12. `ortnamn.paired` measures every same-type head within 500 m that
lacks the point's language and joins the nearest (tested with three lakes 400 m apart and two
Sámi names; the old code joined the wrong one). The lettering size is the nearest label within
500 m that carries one of the place's names, first or `also` (`lettered_size` in
`lomsdal_visten.py`): 210 places lettered instead of 203 before the clip below, Kungsleden and
Kårsajåkka back at their size; 198 of the 345 places in the box after it. Joining the nearest
head gives Trollsjön its Sámi name (§9.12), nine places with two names. The register's names, the cabins, the facilities and the trail points are clipped to
the box like the water; the names still read over the SWEREF envelope, 26 of them stood on
ground with no tiles. The search's `fold()` maps ŋ, ŧ and đ to n, t and d beside ø, æ and å;
seven names on the page carry ŋ.

### 9.16 This document's status lines — fixed, 2026-09-12

§8.2 items 3 and 15. §5's counts are the loaders' (8 fords, 49 cabins, 128 river surfaces with
10 named), its cabin and river names come off the register as §9.9 says, §6.3 and §7.5 say
*uploaded*, §7.6 carries the current drive, §7.4 one answer per question, §9.5 the measured copy
time, §9.11 one river width, §8.1 a trigger that can fire, and `make map ARGS="--park abisko"`
is written the way `make` takes it. The two READMEs and the Makefile help say what the scripts
do today: some 600 readings and ten minutes a page, the page and its companions, `--park`.

### 9.17 A trailing slash — fixed in the page, 2026-09-12

§8.2 item 7. The edge draws the map at `/abisko/` and a redirect would be a third rule phase
(`home/trails-map/known-issues.md`), so the page puts its own path right: the first script in
its head drops a trailing slash from `location.pathname` with `history.replaceState`, before
the icon, manifest and worker links are read, so they resolve against `/abisko` wherever the
page was opened. The root and a file on disk are left alone. Tested on the built page (the
script precedes every link) and **measured at the edge after the publish**, Playwright Firefox
opening `https://atlas.cairn.zone/abisko/`: the path reads `/abisko`, the manifest and the icon
resolve at the root, the worker is registered at scope `/abisko` from `/abisko-sw.js`, and the
whole map at z14 counts 2,343 tiles (§9.13) against the bucket.

### 9.18 The tree's stand, the part files, the build's keys, and the small ones — fixed, 2026-09-12

§8.2 items 8, 9, 11, 13 and 14. `copy_tiles` reads the tree's own `index.json` first and refuses
a file whose modification time differs from the one the tree was copied from — a new stand goes
into a new version directory (tested). Both GeoPackages are unpacked through a `.part` file and
renamed, like the downloads (tested for Topografi 50). `just abisko` unsets the deploy key
pair, the provider token and the purge token before `make abisko`; the build sees the three
`GEOTORGET_*` values. `force_download` reaches all four Topografi 50 reads; `approach_km` is
pinned to 0 in the Swedish params so the fingerprint ignores what the box ignores; the winter
lines are stamped *Topografi 50 winter trails*; `--trail-name-m` speaks of the register. The
deploy checks that the page ends in `</html>`, checks it before listing the trees, and names
the bucket rather than the 404 `/tiles/` when only trees went up; the index says *to load*
beside the compressed size; the module's README says what the upload does.

### 9.19 The two tap checks on Abisko's ground — measured, 2026-09-12

The last two checks the Abisko scene skipped (§9.11, §9.14) have their ground, found over the
cached graph the way the water checks' was (§11). **A tap beside a path**: a node of the
Kungsleden chain in the Abiskojåkka valley as the start, and two taps 2.1 km along it that
stand 134.4 m and 162.3 m off the line — nothing nearer within 200 m, dry ground between, the
perpendicular off the chain's own direction. Driven: at z15 the waypoint stays where it fell
(0.0 m), its leg is 2.20 km with 0.14 km walked to the network, the tap 28 m further out
gives 2.23 km, and at z12 the same tap moves 134.4 m on to the line — now a figure of the
scene (`and how far it moves on to it`; Lomsdal's 135.5 was a literal in the check until
tonight). **A leg not worth routing**: two Topografi 50 trails along the Torneträsk shore,
601 m apart, whose way round costs 7.46 km — twelve times the line — with the first tap a
node 1.4 km along the first of them. Driven: 2.02 km walked against 1.83 km flown, 0.12 km of
it straight; without the rule the plan would have walked 8.9 km. Both pages now drive with
nothing skipped: the Abisko scene's `skips` is empty, and its drive reads 603 readings, none broken.

### 9.20 A new stand of the tiles is a new version, and `make` does it — settled, 2026-09-12

Uwe: *"I would expect that running make again loads new tiles when there are new ones."* So the
refusal of §9.18 was only half an answer; the other half is that the copy chooses the version
itself. `make tiles` asks the server when the file was modified (`MDTM`, the stand: 2026-06-23
11:05 today, the same the tree was copied from), looks for a version directory holding or
copying that stand and resumes it, and otherwise takes the next number and marks it with the
stand (`stand` beside the tiles, written first; `index.json` written last). The page build
draws the **newest complete** version — the highest with an index — through
`maps.tile_tree_version`, which points the provider, the base layer, the worker's prefix and
the offline panel at it; a copy under way has no index yet, so a page built meanwhile keeps
the version before. Nothing is ever written over: the old tree stays in the bucket for the
phones that kept it, the new page names the new one, and a reader's kept tiles are a new
download under the new name. `make abisko` runs `tiles` first, so on a new stand the whole
chain follows: copy (a quarter of an hour), page on the new version, `just deploy --map abisko
--tree tiles` puts the new tree beside the old. What is not automatic: deleting an old version
from the bucket, which is a decision (700 MB a stand) and a hand's work with `aws s3 rm`. §8.1's
FTP-cadence question is closed by this: whenever the stand moves, the next `make` follows it.

### 9.21 Kept tiles across a new stand, and dropping an old one — settled, 2026-09-12

Uwe's two questions after §9.20: *how do I update the tiles in the app when I have them
offline, and why must they stay online if I have them offline?* The first found a gap the
versioning had opened: the panel keeps tiles under their full address, so a page naming `/2/`
found nothing under it, drew the worker's blank offline, and its kept figure still said
everything was there. Now the panel writes down which prefixes the kept tiles came from
(`flags/stand`; a store from before is taken as the page's own stand and written down on the
first read), and **a miss under the page's prefix is answered by the worker with the tile of
the same place under the old one**, so the map goes on drawing offline with the old ground.
The panel says so — *kept from an older stand of the map; Keep loads the new tiles and drops
the old as it goes* — and a Keep run replaces the tiles one by one (each fetched tile deletes
its old counterpart, so the store never holds two stands of one place), sweeps what the old
stand held beyond the selection when it completes, and moves the flag; a run that stopped
leaves the flag on the old stand so the worker keeps answering from it. Measured on the built
page served locally, Firefox: 2,343 tiles kept at z14; every map tile moved to `/0/` and the
flag set to it; the page reads the stand as stale; offline, a fetch of a `/1/` address answered
26,042 bytes from the `/0/` entry; Keep again: 0 under `/0/`, 1,963 under `/1/`, flag on `/1/`.
The drive stages the same on every page it drives, on the tiles its offline check kept: moved
under a prefix the page does not name, the panel says so, a fetch offline answers from the old
stand (31,220 bytes on Abisko), a Keep over a triangle by the reader's position replaces them
(61 tiles) and leaves nothing of the old stand, and the flag is on the page's own prefix.

The second: they need not. Once every device has loaded the new page, the old tree serves
nobody; until then an installed page that has not refreshed still names it when browsing
online. Dropping it is a decision, so it is an option and not a step: `command make deploy
ARGS="--drop-tree tiles/lantmateriet/topowebb/1"` deletes that version from the bucket,
refuses anything that is not a version directory of a known tree, and refuses the version the
tree on disk calls current — the one the next page build draws. The directory on disk is left
to be removed by hand.

### 9.22 Naturkartan's pages, linked from the state trails — settled, 2026-09-12

Uwe asked whether Naturkartan's tours could join the map the way UT.no's join the first one, or
failing that whether the ways on a Naturkartan tour could be marked, linked and preferred.
Measured the same evening on naturkartan.se: **its Abisko tours are the county's state trails**,
one page per *BD* number — BD 16, 16A, 17, 18, 19, 20, 21, 22, 25, 26, 27, 28, 91, 92 — plus two
Rallarvägen articles describing the same ground. So two of the three were already done: the
state trails are a layer of their own, drawn last and on top with the register's name and number
(§7.4), and the register is the source a route prefers (cost 1.02 against 1.05 for Topografi 50's
line of the same trail, 1.10 for a path, 1.20 for OSM, 1.30 for a road — the same rank UT.no
holds in Norway). What was missing was the link, and a link is not a copy: nothing of
Naturkartan's enters the page, and its private-use terms (§5) are not touched.

**The catalogue** is `analysis/routes/abisko-naturkartan.toml`, read by
`io/sources/naturkartan.py`: number to URL, thirteen entries when written and fourteen since the box widened (§9.24), researched by hand through the
site's own search because the slugs are not derivable and a short URL by site id answers 404.
Every entry answered 200 with a site id of its own. Of the fifteen state trails the register
draws over the box as first cut, BD 23 and BD 29 have no page, searched by number and by every place in their
names. `Park.naturkartan` names the catalogue; Lomsdal has none.

**One chain, several pages.** The register's trails run on into each other, so the long chain is
*BD 21 / BD 92 / BD 16 / BD 91* and four pages describe it. A popup's link column carried one
URL under one fixed text; it may now carry a list of *(text, url)* pairs, and the page writes one
link per pair with the pair's own text — `→ BD 21 on Naturkartan` — under the heading the UT.no
popup already used, *Published elsewhere, not by this map*. A pair whose URL is not http(s) is
dropped as a bare one was. The build reports it: 14 of 16 state-trail chains link to a page — 14
of 17 since the box widened, and since §9.26 the same links ride on Lantmäteriet's drawing of those
trails as well, 36 of its 86 marked-trail chains. The
drive reads the links in the long chain's detail on both pages — 2 on Lomsdal (the Rundtur's page
and its GPX), 4 on Abisko — so a catalogue that stops matching the register's numbers is a
reading that moves, not a popup nobody opens.

### 9.23 The whole map to z17 — settled, 2026-09-13

Uwe asked to be able to keep the whole map at z17. *The whole map* on the offline panel was capped
at z16 for every page, and the cap is also the budget every other scope is held to — a figure
chosen on the first map, where Kartverket's box costs 6.76 GB at z16 and would cost four times
that at z17. The same zoom is not the same weight here: Lantmäteriet's tree over the Abisko box
is the copy of §3, 118,967 tiles from z8 to z17, about 700 MB by the panel's own weights (578 MB
of it z17), and it is all in the bucket already. So the cap is the source's figure now,
`Provider.cap`: 16 on Kartverket, 17 on Lantmäteriet, where it is the top of the copy and
nothing on the sheet is an archive. The drive takes it from the scene (`Scene.cap`), reads the
whole map's count at the cap — 119,327 tiles on Abisko, the tree from z11 plus the 380 height
tiles — and checks that every zoom from 14 to the cap is open and that asking for more comes
back with the cap.

**What it costs on the phone.** The rule of the memory budget stands: nothing in the panel grows
with the tile count, and 119,327 is fewer than the 131,033 the first map was measured at. The
tiles go where Lomsdal-Visten's go, IndexedDB — the `kept` store, keyed by address, which the
worker answers a request from by one lookup — and not Cache Storage; the 23 s that WebKit's first
`caches.open()` once cost (memory note of 2026-09-02) belongs to the time the tiles were kept
there, and the cache names left in the worker only clear that old store away. The move was
measured on the same phone: 59,092 rows in IndexedDB open in 107 ms and the app in 1.0 s,
against 23.6 s with the tiles in Cache Storage. First written here as a Cache Storage cost and
corrected at Uwe's word the same morning.

### 9.24 The box widened east past Lapporten and south to the tile row — settled, 2026-09-13

Uwe asked for the paths needed to walk through Lapporten and round back, which the east edge at
19.00 E cut. Measured against Topografi 50 and OSM over the strip out to 19.60 E: two Topografi
50 lines cross 19.00 E, both of the valley path through the gate, which reaches 19.03 E; south
of it BD 28 turns east round Nissuntjårro to Kaisepakte on the E10 at 19.30 E, and between
19.03 and 19.17 E there is nothing else. 19.35 E would have taken BD 28 whole for 49,000 more
tiles; Uwe did not want Kaisepakte, so **the east edge is 19.10 E**. **The south edge is
68.139 N**, at Uwe's word: the tile row that held 68.17 N ends at 68.1389 N on z11, z12 and z13
alike, so the box gains whole rows and no partial one, and with them Kårsavagge's hut at 68.14 N
and Abiskojaure's south end with the Kungsleden on it. §2 carries the box.

**What the widening cost, measured.** `just abisko` as one unit, 2026-09-13: the tile copy
resumed stand 1 of the same FTP file and wrote the new columns and rows only — 26,375 tiles
written, 120,620 already there, none missing, 552 s; the height mosaic was read afresh for the
new box, 259 squares in 54 s into 11,250 × 10,000 posts, and cut into 610 height tiles instead
of 540; the graph rebuilt under its new fingerprint to 866 chains over 44,393 edges (813 and
39,775 before), 353,777 height samples, none outside the mosaic; the page is 3.5 MB. The
register now draws seventeen state trails over the box, BD 31 and BD 32 new; Naturkartan has a
page for BD 31 (site 12865) and none for BD 32, so the catalogue holds fourteen and three
numbers go without. Overpass answered 429 once and the retry took it. The version of the tree
stays 1: the same stand, wider — a kept tile keeps its address, and the panel's `EXTENT` moves
with the provider's.

**The drive, and the river ground that moved.** Seven recorded figures moved with the box —
883 paths in the overlay pane, 866 chains, 16 drawn as circle markers, 86 things in the marker
pane, 16 hits for the search, the whole map 147,415 tiles and 903 MB at z17 — and are
re-recorded. Three readings broke: the river goal of §9.11 no longer waded at the end. Measured
on the page with the goal tool against the published page: the graphs are the same at the river
(the same nine edges cross it, the bridges among them), the water grid answers the same seven wet
samples along the old line, and yet the new page walks 385 m straight from the standing spot
south-east *over a meander* — two crossings, 42 m and 20 m by the outlines — and then paths to
the goal, with *stay on paths* changing nothing. The cause is the grid's arithmetic: the cell
width is set by the box's middle latitude, so widening the box south moved the columns by about
0.7 of a cell at the river, 17 m, and the page prices a straight walk by one sample per 25 m
piece against 25 m cells whose centre decides them, so a 20 m river can fall between the samples
where before it did not. That is a fragility of the page's water pricing, not of the ground, and
it is left as it is today: a narrow river is *said, not priced* by §9.11's own rule. The ground
was moved 70 m down the west-bank path instead, found by trying standing spots and goals from
the graph's own nodes on the page: standing 68.34038 N 18.75252 E, goal 68.34147 N 18.77090 E,
routed 893 m with 522 m straight over one crossing 23 m wide, *stay on paths* 4.90 km by the
bridge. The scene records it.

### 9.25 A fix that stops arriving keeps the watch — settled, 2026-09-13

Reported from the phone with a screenshot: *This device could not work out where it is*, and
"then I have to keep pressing until it works at some point". Worse, a mode that had been working
switched itself off the moment one fix failed — which Uwe called out as most annoying in goal
mode, and it is: the way to a goal is worked out from where the reader is standing, so every
failed fix took that place away and the goal had nothing to route from.

The cause was one line. `failedHere` called `stopHere` for every error the browser could give,
which clears the watch, drops the dot and the ring, and puts the lamp out. A device under a cliff
was treated exactly like a browser told never to share a position.

**Measured before deciding what to do about it**, because keeping the watch on is only worth
anything if the watch can still answer: in Firefox, once `watchPosition` has called back with
*position unavailable*, it never calls back again — not when a position becomes available, not
after 108 s of one being there to have (probe of 2026-09-13, geolocation withdrawn and restored
under Playwright). The watch is finished and says so only by silence. So *pressing again* was
never a habit of Uwe's; it was the only thing that worked.

**What the page does now.**

- **The watch stands** through anything that might still answer, and the mode with it. A
  refusal (`PERMISSION_DENIED`) is the one exception and still stops it: that one will not
  change its mind, and a lamp left burning for it would be the page claiming to wait for
  something that is not coming. It says so, in the line at the foot, and that message stays
  because it is the one a reader can act on.
- **It asks again by itself** — `askAgain`, a fresh watch with the same options, at once on the
  first failure of a drought and every 30 s after that. Thirty rather than twenty because the
  watch waits 20 s before giving up and a retry inside that window would keep throwing away the
  attempt about to answer. This is the press Uwe was making, made by the page.
- **What is drawn is where the reader was.** The dot stands and turns red, the ring turns red
  and dashed at the radius the last fix claimed. The radius is not grown: it is that fix's own
  claim and still true of it, and growing it by a guessed walking pace would be the map
  inventing the one figure it does not have.
- **The age is said in words under the dot** — *no fix*, *no fix for 4 min*, *no fix for 2 h*,
  redrawn on the same 30 s clock. This is the figure that makes a red dot worth anything: how
  far the reader may have walked from the place it is drawn at. Asked for by Uwe as "we
  probably don't know how inaccurate it is", and this is the honest answer to that.
- **The switch goes red**, both of them — the mark at the foot and the rail's lamp — whether or
  not a place is known, which is what Uwe asked for. Where no fix has ever arrived that red
  switch is all there is, and it is enough: it says *on, and getting nothing*. The title and the
  aria-label carry the reason in words.
- **The line at the foot says why once** and fades. A watch that times out every 20 s would
  otherwise put the same sentence over the map three times a minute.
- **`trailsChrome.position()` keeps answering**, with `stale` and `when` beside the place, so
  the goal still routes from the last place the device was sure of. That is the goal-mode half
  of the complaint.

Red is the compass rim's red and deliberately the same one: two reds would be two things to
learn, and between them they say *the instrument is talking*. They are told apart by shape — thin
arcs around the dot against the dot and its ring — which is how everything else at this position
is told apart.

Driven as *a fix that stops arriving* (20 readings) on both pages: blue while fixes arrive, red
and dashed and labelled when they stop, the watch still on, the place still answerable, and then
a position found again **with nothing pressed**. The drought is driven through `watchPosition`
itself — the check wraps it, keeps the error callback of the running watch and fires it — and not
by withdrawing the position with `set_geolocation(None)`. Withdrawing it works, and is how the
measurement above was made, but it leaves the context unable to push a position to any watch
already running for the rest of the run: driven that way the check passed and seven checks after
it failed on a map that had stopped hearing where it was.


### 9.26 A name stops where the register stops — settled, 2026-09-13

Reported from the phone with two photographs: the map's own panel, headed *State trail:
Låktatjåkka - Måndalen - Abisko (BD 18)*, and a trailhead sign for the same ground saying the
route is marked on **Fjällkartan BD6**. Two questions came with them — why a trail the panel
calls BD 18 offers no Naturkartan link, and why the sign says BD 6 where the map says BD 18.

**BD 6 is not a trail number.** It is a sheet of Lantmäteriet's printed *Fjällkartan* at
1:100 000 — the sign says *"Rödprickad på Lantmäteriets Fjällkarta BD6"* and, in English, *"On
Fjällkartan BD6 it is marked with red dots"*, beside the 1:50 000 sheet *Abisko, Björkliden,
Riksgränsen*. The BD numbers on this map are `STATLED_ID` out of Naturvårdsverket's trail
register, which is what the county's brochures, the waymarking and Naturkartan use (§5). Two
registers whose keys both begin *BD*, and nothing more than that. The sign's own trails —
Färdledarvägen and Sommarleden, Björkliden to Låktatjåkko — carry no state trail number at all:
the register's trails there are BD 19, BD 91 and BD 92.

**The other question was a defect, and the sign is the evidence for it.** The line under the
reader's finger was Topografi 50's marked trail, not the register's, and it ran from Låktatjåkka
to Björkliden as **one chain of 12.2 km** reading BD 18 along all of it. Measured against the
register every 500 m: the first four kilometres are BD 18 (0–100 m from it), and from there the
chain leaves the state trail and climbs to Björkliden, **4.3 km** away at worst. Its name was
Björkliden's trail wearing BD 18's, which is exactly the pair of ways the sign describes.

Nothing had gone wrong in the naming. Topografi 50 draws the marked trails and names none of
them; the register names them and lies on the same ground, so a Topografi 50 line takes the state
trail it runs along — but only where it runs **within 25 m of it for half its own length**
(`network/sweden.py`, `params.trail_name_m`). No line 4 km away can be named by that rule, and
none was. **It was the chaining.** A chain carries the union of its pieces' names, and where
exactly two arms meet, `_pair_arms` joined them whatever the angle — so the marked trail ran on
past the end of BD 18 into ground the register never named, and took the name with it.

**The rule now** (`routing/chains.py`, `_agree`): a piece its source names and a piece its source
does not name are two ways, whatever the angle between them. **Two different names are not**, and
that limit is deliberate and was measured: refusing those as well cut the register's own 17
chains over the box into 22, ending the chain from Abisko that is *BD 21 / BD 92 / BD 16 / BD 91*
and carries four Naturkartan pages (§9.22), for no defect at all. Every metre of that chain is
named by the register that drew it; nothing is claimed there that was not recorded.

What it cost and what it bought, over the box:

| | before | after |
|---|---|---|
| chains | 866 | 886 |
| — the register (*Leder*) | 17 | 17 |
| — Topografi 50 marked trails | 76 | 86 |
| — Topografi 50 paths | 215 | 215 |
| — Topografi 50 roads | 72 | 74 |
| — OSM | 486 | 494 |
| edges / nodes | 44,393 / 20,683 | 44,429 / 20,706 |
| network length | 1,604 km | 1,604 km |
| marked trail carrying a state trail's number | 170.5 km | 132.1 km |
| of that, further than 25 m from the trail it names | **38.0 km** | **2.6 km** |
| worst distance from it | **4,331 m** | **122 m** |

The 2.6 km that remain are the two sources drawing one trail slightly apart — 25 m is allowed per
line and a chain is many lines — which is a disagreement between Lantmäteriet and the register
and not a claim this map invented.

**Lomsdal has the same machinery and the same defect**: FKB's paths take their route from
Turrutebasen and N50's roads take their number and name from the register and from Stedsnavn,
both by nearness (`network/norway.py`). Its page goes from 11,302 chains to 11,964 — FKB 6,201 to
6,306, OSM 1,515 to 1,531, and **N50's roads 2,326 to 2,823**, which is the largest single effect
of this change anywhere and is a road number that used to run on into whatever unnumbered lane
left the junction straightest. The page grows from 16.7 to 17.1 MB for it.

**And the link Uwe was looking for.** It hung on the register's line alone, which near Låktatjåkka
lies under the marked trail and east of it does not exist. Now that a marked trail named after a
state trail *is* that state trail, it carries the same link: the register's number travels with
its name (`route_id`, taken in the same `attach_nearest` call), and the popup writes
*→ BD 18 on Naturkartan* under the same heading the register's own line uses. **36 of the 86
marked-trail chains** carry one, against 14 of the register's 17. Still links only — nothing of
Naturkartan's enters the page (§5, §9.22).

**Driven as *a borrowed name has its register under it***: the longest sixty chains of the
borrowing source, each one clicked to read the name the panel gives it — a chain the register
never named is headed by its own id, which is how the two are told apart — and then the longest
six named ones sampled at seven points, each point asking whether a line of the register is
within the tap's reach at z11, about 340 m on the ground. **42 of 42 on both pages** — nine of
Lomsdal's sixty longest FKB chains carry a Turrutebasen route, 32 of Abisko's carry a state
trail. The reach is read at z11 rather than z12 on purpose: the two sources are up to 122 m
apart, and a tighter reach would report *that* as this defect.

One reading elsewhere had to be freed of an accident while this was driven. *Setting it puts the
way there on the panel* expected the words **To the goal**, which is what a goal beside nothing
is called — but the goal it sets is 70 % along the long chain by index, the panel's series has a
sample more or less when the chains are rebuilt, and that moved the point from 46 m to 37 m from
the *Vindskydd Nissonjohka* shelter. A goal within a finger's reach of something named is that
thing (42 m at z14), so the panel rightly said *To Vindskydd Nissonjohka* and a check about the
panel failed over a shelter. It now expects the name the goal itself carries.

**A trap worth writing down**: the graph's cache key (`network/graphs.py`, `fingerprint`) is made
of the data and the parameters, not of the code, so a change to the chaining rule does not
invalidate it. Both graphs had to be rebuilt with `--rebuild`, and a build that had only been
`make graph`-ed would have served the old chains from the cache and looked like the change had
done nothing.

### 9.27 The search lists what it finds, and reads a position — settled, 2026-09-13

Asked for from the phone, in one message: *I want to be able to type coordinates like 68.39275,
18.68033 and have a position marker appear there. As with a place, I want to be able to set it as
a goal. How could the input be made? Through the search? … Could we do it that way for searching
by name too — results are listed and I can tap one, the one chosen is then selected and the map
has zoomed to it, and all the other places stay drawn instead of being hidden.*

**The first half was already half-built and facing the other way.** The *Copy a position* tool at
the foot writes `where.lat.toFixed(5) + ', ' + where.lng.toFixed(5)` to the clipboard — which is
`68.39275, 18.68033`, the string that was typed into that message. Nothing on the page could read
one back. The two together are a round trip: copy a position on one device, type it on another,
stand on the same spot.

**Two decisions, both Uwe's, taken before anything was written** (asked with what each would cost):
the list *replaces* the hiding — the map stays whole while a search runs — and the forms read are
decimal degrees **and** degrees, minutes and seconds, which is what a sign or an older map writes.

#### What the box did before

Typing cleared `display` on every feature that did not match, and on a canvas layer — which has no
element to hide — cleared `stroke` and `interactive` instead; a layer switched off was switched on
for as long as it held a match and put back afterwards. It found the name by removing the map it is
on: what the match lies near, what it lies between, which of six lines through that valley it is.
Enter fitted the view around every match at once.

#### What it does now

One row per named thing, nearest first, in `_NameSearch`:

- **Ranked** by how the name matched — the whole name, then a name starting with what was typed,
  then a word inside it starting with it, then anything holding it — and within a rank by distance
  from where the reader is if the page knows, and from the middle of the screen if it does not.
- **One row per thing, not per drawing.** The sources cut a named way into as many chains as they
  please and name every one: *Abiskojaure - Alesjaure (BD 26)* was four rows. A line's pieces are
  one row saying how many lines carry the name, pointing at the nearest of them. A *place* is kept
  apart by distance instead, 2 km: two waters of one name a valley apart are two answers, and the
  same hut in two registers is one hut twice, which is worth two rows because the registers differ.
  A name carrying two register numbers is another name and another row (§9.22).
- **What each row says**: the name, then the layer it was drawn in — without the legend's count and
  without the detail after the em dash, which is `_layer_label` — the number of lines where there
  is more than one, and how far off it is where the page knows where the reader is.
- **A row is the thing itself.** Taking one fires the click that thing's own handlers are already
  wired to: the highlight widens the line, the panel selects it and draws its profile, a place opens
  its popup. Without the point it was tapped at, which is the rule the panel's row of chips follows.
  A layer switched off is switched on by taking one of its rows. A name drawn on the map — the
  lettering — takes no tap on the ground either, so its row moves the map and does nothing else.
- **On a phone the panel steps aside.** The list stands in the chrome's dock there, over the map:
  at 390 × 844 the dock takes the top 500 px and the map's middle — where a row puts what it chose
  — is at 422, so the answer would land behind the question. A row taken closes the dock; the field
  keeps what was typed and one press has the list back.
- Enter takes the first row. Escape clears the field. **Nothing is hidden at any point**, which is
  the reading the drive takes to say so: the same 988 features are drawn on the Abisko page before
  and while a search runs, not one of them darkened by it, and the map has not moved either until a
  row is taken. Sixteen matches for *Abiskojaure* are twelve rows there; three for *Gåsvatnet* are
  two on Lomsdal-Visten.

#### A position is a name here too

`readCoordinate` reads both sides of a pair as an angle: an optional hemisphere letter in front,
degrees, optionally minutes and seconds behind a degree sign, an optional letter after. So all of
these are the same place, measured 0.1 m apart at worst (the seconds' own rounding):

```
68.39275, 18.68033      68.39275 18.68033       N 68.39275, E 18.68033
E 18.68033, N 68.39275  68°23'34"N 18°40'49"E   68° 23.565' N, 18° 40.82' E
```

- **N names the latitude wherever it stands**, so the order does not matter when the letters are
  there; without them the first side is the latitude, which is the order this map writes one in.
- **Minutes need the degree sign.** `68 23` with no symbol is two numbers and nothing can say
  whether they are a latitude and a longitude or 68 degrees and 23 minutes of one of them.
- **The decimal point is a point**, because the comma parts the two sides — the form the picker
  copies — and cannot be both without `68,39275, 18,68033` becoming four numbers.
- **Something has to part them.** Found while this was written: with the separator optional,
  `68.39275` alone read as a position — the second side has to match something, so the expression
  backed off and took `68.3927` and `5`. A comma or a space between the two, always. Twenty-two
  strings were put through the reader to settle its edges, the whole-name cases among them.

The row it makes is the first one, always. Taking it marks the spot — a ring in a third colour,
neither the goal's green nor the position's blue, one at a time — and opens the mark's own page,
which carries the *Set as goal* button a hut's popup carries, through the same markup and the same
listener on the document (`trailsChrome.goalOffer`), and a line to take the mark away again.

**A typed position snaps to nothing.** `trailsGoal.set(lat, lon, name)` without the fourth argument
is the path a goal taken from a popup already followed: a typed number is not a finger, so the
ladder of *a named thing within reach, then a line within a finger, then the tap as it fell* does
not apply to it. The mark and the goal both stand at the five decimals that were typed, 0.00 m off.

#### Two faults on the phone, within the hour

Uwe read the published page and found both at once, with a screenshot of the mark's page.

**The same button twice.** The mark's page carried *Set as goal*, and so did the page the chrome
built around it — the chrome appends that offer to every popup whose source has one position, which
is written in its own comment as the reason not to build it into a popup. The mark's own offer is
gone; `trailsChrome.goalOffer`, added an hour earlier for it, went with it. One place on this page
turns a thing into a goal.

**And a goal with nowhere to route from was a dead end.** Set from the mark with the position
switch off, the goal stood — a ring on the map, the flag lit — and pressing the flag did nothing
at all: no page, no way to be rid of it. The cause is neither the search nor the mark. The panel
draws the *way* to a goal, `showGoal` returns false without one, and there is no way until the page
knows where the reader is, because routing starts where they stand. So a goal taken from a hut's
popup with the position off had been as stuck since the goal was written; a typed position is just
the easiest way to reach that state, since nothing about it asks for a fix.

The flag says it now, and *Set as goal* says it at once where there is no position to route from —
a page of three lines in the chrome's sheet: **Where I am**, which switches the position on and is
the missing half; **Move the goal**, which arms the next tap; and **Drop the goal**, which asks
first where stops would go with it. Driven: `['Where I am', '⌖ Move the goal', 'Drop the goal']`,
and dropping it there takes the goal off the map.

#### What it cost, and where it is

`_NameSearch` in `visualization/maps.py`, with `_layer_label` beside it and `window.trailsSearch`
for whoever drives it; `trailsChrome.goalOffer` is the one new line in the chrome. One function
serves both pages, so Lomsdal-Visten has all of it too. Four tests that asserted the hiding are
rewritten to the new truth and five new ones stand beside them; the suite is 1,436 green. Two new
checks drive it — *the search lists what it finds* and *a position typed into the search*, sixteen
readings, and twenty-one with the two faults above — and both pages read **652 readings, 0 broken
invariants, 0 figures moved**, up from 633.

**And one lesson about the suite, paid for with seven runs.** The first drive of each page died in
*a goal the reader sets* — `stops[0]` out of range, which is a goal that was never set — while that
check passed when it was run alone, and so did the two new ones with it. Pinned down by bisection
and then by measuring the page at the moment of the tap: the new checks left **a place's page open
in the panel**, `paged: 'details'`, three checks earlier; when the goal check narrowed the window to
390 × 844 and asked for the profile, the panel opened **853 px tall over an 844 px screen** and the
tap that sets the goal landed on `trails-profile-page` instead of on the map. The panel's own clamp
is not at fault — a place opened at 1400 × 900 and carried down to 390 × 844 stays 240 px, and a
trail read upright is 189 px with the phone turned sideways, both measured — it is the state the
checks handed on.

So `LET_THE_SEARCH_GO` puts everything back: the field, the mark, the goal, the armed tap, the
chrome, **and a click on empty ground**, which is the one gesture that lets go of a selection, its
page and the highlight together. Two tools came out of the hunt and stay: `--only` takes a list of
names parted by commas, which is how a check that passes alone and fails in a run gets pinned down,
and the goal check reads its moved stop out of the list rather than off its first row, so a run that
set nothing reports that instead of throwing and taking every later reading with it.

### 9.28 A goal becomes a plan, and a place offers what can be done with it — settled, 2026-09-13

Asked for from the phone, three questions in one message: *can we add a button to turn a goal into a
plan? Can we, in plan mode, add geo coordinates directly as waypoints? Also for intermediate stops?*

They are one shape. **A goal answers *how do I get there from where I am*; a plan answers *what
shall the walk be*.** The first is set in a moment and walked at once; the second is edited —
reordered, cut into stages, written to a file. A reader who has set a goal with two stops on the way
has already laid out exactly the thing a plan is for, and there was no way from the one to the
other. And a position typed into the search (§9.27) is a place on the map by the time it has a mark,
so nothing new has to read coordinates for the other two: the page of a *place* is where this
belongs.

#### What a place offers

The chrome adds its offer to the page of every popup whose source has one position. It offered one
thing; it offers what can be done with that place **as the page stands now**:

| offer | when | what it does |
|---|---|---|
| *Set as goal* | always | that is what a place on a map is for |
| *Add a stop on the way* | while a goal stands | there is no way for a stop to be on otherwise |
| *Add to the plan* | while a plan stands — points on it, or its mode on | adding to a plan nobody is making would be a mode change hiding inside a button; and the press leaves the mode as it finds it (see below) |

A hut's page offers the same three; a typed position's page does because it is a place like any
other. **None of the three snaps.** A press on a page is not a finger on the map: the place is where
the popup says it is — the hut, or the five decimals somebody typed — so `place` takes an `exact`
flag and `addStop` is called the way a popup already called `set`.

And the place names what it becomes: a stop taken from a hut's page is that hut, and one taken from
a typed position is `68.40275, 18.69033`, which is what the list would otherwise call *Stop 1*.

#### The way to a goal, as the plan's points

`planFromGoal` lives with `planFromPlaces` in the plan control, because both halves of it are there
— the goal and the plan share that closure — and because it is offered from two places:

- **the goal's own page**, under the places it goes by: *Make a plan of this way*;
- **the page the flag opens where there is no way to show** (§9.27), which is where a reader without
  a position fix actually is. Measured: `showGoal` returns false without a line, so the goal's own
  page cannot be reached at all then — and the whole point of a plan is that it does not need to
  know where anybody is standing.

The reader's own position goes in front of the places where the page knows it, because the way being
looked at starts there; the stops follow in the order they are walked, the goal last. **The goal
goes with the conversion** — two routes over the same places, one editable and one not, is a page
that cannot say which is being walked — and a plan that already has points is asked about first,
which an empty one is not.

**`SAME_SPOT_M = 1`, and it is not decoration.** The places arrive as they were put down and are not
snapped a second time; but `nearestNode` takes its reach as a strict bound, so a reach of zero
refuses even the node a point is standing *on* — which is what a tap that snapped leaves behind.
Measured: a goal set by tap on node 10353 comes back as a plan point on node 10353, and a typed
position 1.1 km from anything comes back as open ground with the leg drawn `land, routed, land`.

#### The offer that only worked where nothing could be selected

The first version offered *Add a waypoint* while plan mode was **on** — and Uwe pointed out that this
is exactly when it is useless: with plan mode on every tap on the map *is* a waypoint, so no place
can be selected there at all, and the offer was reachable only through the search. The mode is
switched off to look a place up — switching it off leaves the route drawn, on purpose — and that is
the state in which a reader stands on a hut's page wanting it on the plan. So the offer is made
**while a plan stands, whether or not its mode is on**, under one name, *Add to the plan*.

And the press **leaves the mode as it finds it**. The draft brought plan mode back with the point,
the way a loaded file does; Uwe's objection: then the next place could not be selected either until
the mode was switched off again. A loaded file brings the mode on because a route that arrived
whole wants editing; a place added to a standing plan is an edit already made. Driven: with the
mode off and three points standing, a typed position's page offers *Set as goal* and *Add to the
plan*, and the press puts the point fourth with the mode still off.

He also named the alternative — a switch in plan mode that stops a tap from placing a waypoint — and
that stays open (§8) in case looking things up *while* planning turns out to be wanted; today the
mode switch is that switch.

#### And the offer nobody could reach

Asked the same evening, off the published page: *how do I add a coordinate as a waypoint in a plan?*
The answer was that you could not. The offer stood on the place's page, and the place's page is a
page of the panel — but **plan mode refreshes the panel on every edit**, and each refresh feeds it
either the composed route or a null. Both threw the popup's page away: `present(null)` clears
`detailHtml`, and so does `present(composed)`. Measured at 390 × 844 with one point down: the
button was in the document, `offsetParent` null, in a page the panel held and would not show — the
very state `wantedPages` says in its own comment must not happen.

**While plan mode owns the map, a popup's page is not a stale selection.** Nothing else can open one
there — every click on the map is a waypoint — so the only way one exists is that the reader asked
for it, out of the search. It now outlives the plan's refreshes, the panel unfolds at it and turns
to it (the pages are *Points and stages* and *Details*, either one press away), and it goes when
plan mode goes. Measured again: shown, inside the window, and the topmost thing at its own middle,
at y = 745 of an 844 px screen.

**And the check that missed it now reads what a finger could do.** It pressed the button through
`querySelector`, which works on a node nobody can see; it reads `offsetParent`, the window and
`elementFromPoint` first.

#### And the mark nobody could get back to

Reported next, with the mark standing alone on the map at z17: *I have no way of selecting the point
I set again.* Two causes, both measured, and the second is not about the search at all.

**The target was 18 px.** It is the one mark on this map that takes a tap — the goal's ring and the
position's dot take none and are reached through the row at the foot — so it is the one that has to
be a finger wide. It is 36 px now, with the same 18 px ring drawn in the middle of it. Not 44:
a transparent box over the map takes the taps meant for whatever runs under it, and 18 px of halo is
already more than the 12 px a line is hit by; pinching in is how a reader says they meant the trail.

**And its page came back folded.** Pressing the panel's heading folds the pages away — which is
exactly what a reader who wanted the map back has just done — and `pagesOpen` outlives the
selection, so tapping the mark brought the panel back as a 46 px strip carrying the name and nothing
else. **Asking to read a place is asking**: a place's page now shows itself and turns to itself,
through one `showDetails`, called from both branches of `detail` — the early return for a place was
the branch that needed it. True of every hut and quay on both maps, not only of the search's mark.

#### And the legend that did not follow the map

Reported next: *when I choose a place name in the search, the name layer is switched on
automatically, but the layer panel still shows it as off — and the only way to switch the names off
again is to tick that layer on and off.*

True, and not only of the search. The legend **is** the layer control on this map (§ its own
docstring), and it set each row's checkbox once, when it was drawn, and then followed nothing but
its own presses. Anything else that switched a layer — and a row taken switches its own layer on,
which is what it is for, or the row would move the map to a blank spot — left the box saying one
thing and the map drawing another.

It follows `layeradd` and `layerremove` now, which Leaflet fires for every add and remove whoever
asked, so what the panel says is what the map holds. **Collapsed into one repaint through a
timeout**, because a layer group adds its features one at a time and each of those is an event:
12,461 of them on the Lomsdal page for a single tick.

#### Driven

*A way to a goal becomes a plan*, nine readings on both pages, with the position switched off —
which is where the goal's own page cannot be reached and the state a reader who has just opened the
map is in. A position typed in, set as a goal; a second typed in and added as a stop, named after
itself; the flag's four lines; the two places as the plan's two points in order with the goal gone;
a third typed in as a waypoint, reachable by a finger on a phone, and landing on its five decimals.
And in *a position typed into the search*, two more: the mark is 36 px wide, and a real press at its
middle on a phone-sized screen brings its page back, open, with the offer on it. In *the search
lists what it finds*, two more again: with every layer switched off first, a row taken leaves
exactly one row ticked in the legend — its own — and every other row is put back as it was found.
665 readings a page.

### 9.29 A tap lands on the line, and not only on its junctions — settled, 2026-09-13

Reported from the phone, with two screenshots, in one message: *"I removed a waypoint and the
stretch between stayed open and was not re-routed"*, and *"once I have drawn one straight line, I
cannot select the path after it any more — only straight lines are drawn — until I mark a path
that comes after it, and then it routes over that path."*

**The second is a design defect, and it was measured before it was fixed.** `snapped` asked
`nearestNode` and nothing else, and a node is where edges meet or a chain ends. A tap in the
middle of a long stretch of trail therefore found nothing within a finger's width, stood as open
ground, and every leg from it was priced over the ground: a straight line at three times its
length against a path that had to be *walked back to the junction first* at the same price. The
"path further on" that made it work was the next junction. On the two graphs, sampled every 25 m
along every walked edge:

| | nodes | edges | median edge | longest edge | beyond 21 m of a node (z15) | beyond 150 m |
|---|---|---|---|---|---|---|
| Abisko | 20,706 | 44,429 | 15 m | 13,432 m (OSM) | **37 %** of the length | 13 % |
| Lomsdal-Visten | 117,437 | 235,141 | 7 m | 6,820 m (OSM) | **32 %** | 8 % |

So more than a third of the network could not be tapped on at the zoom a plan is made at. The
first version of the routing (`route-planning-phases.md`, *Routing*) chose *the nearest node
within about 150 m* because the decoder offered it and it cost 0.15 ms; nobody had asked what
share of the ground a node is near.

**The line itself is asked now.** `nearestOnNetwork` finds the nearest point on any walked edge
within reach, over the grid `edgeIndex` already built for the match mode (16 ms to build on
Abisko, 83 ms on Lomsdal; built once, when plan mode comes on), and skips crossings and
connectors, which are not ground to stand on. A point put on the line remembers its edge and how
far along it stands. A junction within reach still wins over the line beside it when it is as
near, give or take 2 m: at a junction the line *is* the node.

**And the router starts from there.** `endsOf` gives a point on an edge two ways on to the
network — either end of the edge, at the metres between times the edge's own price — with the
piece walked to that end carried along as a *cut*. `routeBetween` is one Dijkstra seeded with
every end of one point and stopped by the cheapest way off at the other, so a point mid-edge is
routed from whichever end the way actually goes rather than from the nearer one and back; two
points on one edge take the piece between them unless some way round is cheaper. `cutPart` lays
a cut the way `layEdges` lays a whole edge — the vertices between, the samples between with the
two ends read off their neighbours, the ground tallied by the metres walked — so it is path in
the file, in the profile and on the map. The joined way a goal is routed by (`joinedRoute`) takes
an end on the network by its edge too, and a goal's legs ask once (`placed`, at `SAME_SPOT_M`)
whether their ends stand on the line: a tap was put there by `onTheLine`, a hut from a popup was
not, and the position stays the reader's own either way.

Measured on the rebuilt pages, with the longest walked edge as the ground: a tap half way along
it stands on edge 43295 at 6,734 m (Abisko), its leg from the edge's own end is `routed` end to
end and 6,734 m long, a second tap at three quarters gives 3,366 m of path; on Lomsdal 3,418 and
1,709 m. A goal tapped half way along, with the reader standing 40 m off the edge's start, is
40 m straight and the rest path; a stop tapped at three quarters is walked to and back along the
edge. A tap costs 220–310 ms including the settle, as before. Driven as *a tap in the middle of
a long edge*, which takes its ground from the page's own graph, and reads as well that **every
leg that settled has something on the map** — the first report.

**The first report could not be reproduced from the screenshot** — the route was rebuilt to the
metre (Abisko, the cabin west of Njullá from its page, a tap on the trail, Kårsavagge) and every
leg drew, through removals, undo and every cabin in the box as point 2. Two things came out of
that hunt anyway: `state()` says how many layers each leg has on the map (`drawn`) and the drive
reads it, and the row's word goes by the greater part of the leg (5.4 km with 63 m walked to a hut
used to read *drawn straight*).

**Then it came back, an hour later, with the file** — and the file was the whole of the
difference. The plan had been **restored from its own GPX**, and a restored leg is laid out the
way the file described it (`from.restore`, §9.7-era), before any routing. The description lived
on the leg's *first* point and named nothing about its second, so after point 5 of eight was
taken out, the new leg from 4 to 6 was laid out as the file's leg from 4 to 5: a line ending in
the open, 8 km short of its far point, the walk shorter by exactly the 8,115 m of the leg that
was dropped (36,746 → 28,631 m, measured with the file), and every one of its layers drawn — which
is why the *drawn* reading could never have caught it. Not the router, not the canvas, not the
phone: a leg made after an edit that was never described by the file. The description now names
the point it ran to (`restoreTo`, set in `pointsForLoaded`), and `resolve` honours it only for
that pair — a dragged point is a new object and a removed one leaves its neighbour facing another,
and neither matches. Driven in *files written and read back*: a point taken out of the restored
plan leaves one leg fewer, every leg ends where its own far point stands, none is shorter than
the line between its ends, and all are drawn.

**Four figures moved with it, all the change's own doing.** Lomsdal: *the plan walks this far on
paths* 1.6 → 1.8 km (a tap that stood as open ground is on its line), *how far it moves on to it*
135.5 → 129.2 m (the line's own foot rather than the node beside it). Abisko: *from 10 km off, the
way is on paths for* 6.3 → 6.8 km and *straight for* 0.9 → 0.8 (the goal's tap is on its line, so
the way reaches it along the line rather than straight from a junction). The index costs 91 ms on
Lomsdal and 15 on Abisko, recorded. Both pages 677 readings, none broken.

---

### 9.30 The page asked for a newer worker on every load — done and undone the same evening, 2026-09-16

Uwe, 2026-09-16, with the relief: *"Aber mach beim Service worker das er bei mir beim Laden einmal
sofort aktualisiert wird."* Then, an hour later: *"Würde gerne unnötiges Laden vermeiden"* — and
whether that could be tested.

**What was built.** The worker already calls `self.skipWaiting()` on install and
`self.clients.claim()` on activate, so a new one takes over at once. The page gained
`registration.update()` after `register()`, on the reasoning that a browser checks for a newer
script only around a navigation and an installed app may not navigate for days. It was published
with the relief.

**What was measured, and it says the opposite.** Two one-page tests behind the tunnel — `c` calls
`register()` alone, `d` calls `register()` and then `update()`, the way the map did — against a
server that logs every request and marks the ones carrying the `Service-Worker: script` header,
which only the browser's own fetch of a worker script sends. Each page loaded three times, on
Firefox here and on Uwe's iPhone in Safari. (The first pair of paths had to be abandoned: one
`curl` of the script put it into Cloudflare's edge cache for four hours and the log went blind —
the zone rewrites the tunnel's `max-age`. The scripts are served `private` since, which the edge
does not cache.)

| | load 1 | load 2 | load 3 | script fetches a load |
|---|---|---|---|---|
| Safari, `register()` alone | 200 | 200 | 304 | **1** |
| Safari, `register()` + `update()` | 200 + 200 | 200 + 200 | 200 + 304 | **2** |
| Firefox, `register()` alone | 200 | 304 | 304 | 1 |
| Firefox, `register()` + `update()` | 200 + 304 | 304 | 304 | 1 after the first |

**Safari fetches the script on every `register()` already**, and `update()` on top of it fetched
it a second time on every load, uncoalesced. Firefox folded the two into one after the first
load. And Safari mostly sends no validator, so where Firefox pays a 304 with an empty body Safari
pays the whole file — 30 kB for the real worker, twice a load with the extra call.

**Decided: the call comes out.** The eager check cost nothing to leave out and doubled the one
request already being made. What remains is the browser's own check on every load plus the
worker's own takeover, which together are the whole mechanism — and are what delivered the relief
to the phone in the first place. The *newer* line and its Reload button stay the way a new
document is taken; nothing reloads under the reader.

**Two things learned on the way that were not the question.** The zone's cache rule sets edge and
browser TTL with `override_origin` on every path but `/`, so the `no-cache` the deploy puts on the
worker never reaches anyone (`home/trails-map/known-issues.md`); harmless, since the script is
fetched past the HTTP cache anyway and the deploy purges the edge. And a service worker's script
fetches do not surface in Playwright's request events, so counting them takes a server that logs.

---

## 10. Changes

A line per change to this document or to the decisions in it, newest first.

- **2026-09-17** — the slope classes are drawn multiplied, go to seven, and take a light palette
  (§6.7), on Uwe's finding from the phone over Latnjajávri that the sheet's lettering lay under
  the colours and that marked trails run through the class over 50°. A label overlay was looked
  for and not built: the open download has no text-only sheet, the licensed layered WMS with one
  costs 125,000 kr a year and is not for a bucket, and Topografi 50's own label points would ghost
  over the sheet's. `mix-blend-mode: multiply` on the layer keeps black lettering black; measured,
  the names had fallen to 3:1 under the opaque classes and stand at 10:1 or better under every
  class now. A class over 55°, ours, parts the walls no path crosses from the steps one does.
  Chosen on a mockup with both palettes and the blend switchable. The tree is **version 2**
  (`slope/lantmateriet/2/`, 9,330 tiles, 25.0 MB, 12 minutes); version 1 stays in the bucket for
  any phone that kept it, which reads the new address as *moved*. 708 readings on Abisko (two
  new: seven classes with ours at both ends, and the blend on the layer's container), 683 on
  Lomsdal-Visten. A band costs the same as before, the whole map 0.3 MB more. Not yet published.

- **2026-09-16, fifth of the day** — the slope is classed over the relief (§6.7), asked for from
  the phone the same evening: *"Ließe sich ein ähnliches Overlay auch für die Steigung bauen?"*
  Six classes — 25° ours, 30/35/40/45 the SLF's, 50 swisstopo's of this January — after a search
  for a hiking scale in degrees found none; a class above 45 kept on Uwe's point that stepped rock
  at that angle is walked and a smooth face is not, which the model cannot tell apart, so the
  legend names the angle. Colours continue the profile's bands, scheme A of two on a mockup;
  the profile's own per-cent bands stay, being a different measure. A fourth tree
  `slope/lantmateriet/1/` — 9,330 palette PNGs, 24.7 MB, 12 minutes — cut through the relief's
  own `plan()`/`cut()`, which were factored out of `shade_tiles` for it; a second checkbox under
  the relief's in the base-map panel with the colour rows under it, **off by default**; the
  worker's fourth prefix; kept offline whether on or off. A band costs 2.4 MB more, the whole map
  24.7. 706 readings on Abisko (fifteen new), 683 on Lomsdal-Visten (the check a declared skip
  there); the whole-map figure moves from 156,725 to 166,035 tiles.
  **Published** in the early hours of 2026-09-17, asked for after the worker's fourth prefix was
  said out loud: the tree first (9,330 objects, 24.7 MB, 139 s), then both pages —
  `abisko.html` 3,581,093 B and `lomsdal-visten.html` 17,137,364 B, byte-identical from the edge,
  and both workers with them (`abisko-sw.js` 30,214 B carrying `SLOPE_PREFIX`,
  `sw.js` 30,055 B carrying it empty). Four sampled class tiles from z10, z12, z14 and z15 came
  back byte-identical, the index names six classes at alpha 150, and a tile outside the box is a
  404 as it should be. Each worker's version stamp was checked against its page's hash before
  anything went up.

- **2026-09-16, fourth of the day** — the relief's checkbox moves from the legend to the base-map
  panel (§6.6), on Uwe's question whether it belonged among the layers. It is not a line or a
  point and has no colour or count; it is how the sheet underneath is drawn, which is that panel's
  question. The legend is back to 19 rows on Abisko; the drive reads the switch from the other
  panel. 691 readings on Abisko, 682 on Lomsdal-Visten. **Published**: `abisko.html` 3,576,572 B
  and `lomsdal-visten.html` 17,133,919 B, byte-identical from the edge, the checkbox under the
  sheet and no legend row.

- **2026-09-16, third of the day** — the `registration.update()` of the second entry is taken out
  again (§9.30), on a measurement from the phone: Safari fetches the worker script on every
  `register()` already, and the extra call fetched it a second time on every load, the whole 30 kB
  where Safari sends no validator. Firefox had folded the two into one, which is why the first
  measurement here did not show it. Test pages `c` and `d` behind the tunnel, three loads each,
  server-side log with the `Service-Worker: script` header as the mark. **Published**: both pages
  and both workers, `abisko.html` 3,575,518 B and `lomsdal-visten.html` 17,132,785 B,
  byte-identical from the edge, neither carrying the call; 690 and 682 readings before it.

- **2026-09-16, second of the day** — the page asks for a newer worker every time it loads (§9.30),
  asked for with the publish. The worker already skipped waiting and claimed its clients; nothing
  asked for the script, and a browser asks at most daily and only around a navigation. One
  conditional request on load, guarded by `navigator.onLine`, and no automatic reload — the
  document is still taken by the reader, through the *newer* line.
  **Published with the relief**: the tree first (9,330 objects, 104.0 MB, 250 s), then both pages —
  `abisko.html` 3,575,908 B and `lomsdal-visten.html` 17,133,175 B, byte-identical from the edge,
  and both workers with them. Checked live in Firefox against `atlas.cairn.zone/abisko`: the relief
  tiles are asked for and answer, the worker is active with nothing left waiting, and the panel
  names the new tree. The comparison mockup under `~/mockups/hillshade` is gone, its figures
  being in §6.6.

- **2026-09-16** — the relief is shaded (§6.6), asked for from the phone with two photographs of a
  Calazo sheet: *"Fast schon ein 3D Effekt."* Neither Lantmäteriet's sheet nor Kartverket's carries
  shading — read off the tiles — so the page draws its own, cut here from the 1 m height model
  already cached for §6.3. Black with an alpha channel rather than a grey image multiplied over the
  sheet, so level ground keeps the map's cream; light from the north-west at 45°; drawn at 0.55,
  which was measured against contrast in the darkest tenth (1.49:1 at 35 %, 1.42:1 at 80 % — so the
  contours are not what bounds it) and against absolute darkness (at 70 % a flank goes near-black);
  cut to z15, where a z14 tree is visibly soft at z16 and the model has nothing more to give past
  it; stored in 64 steps of alpha, which halves the tree for a 2.2-level step of 255 in the drawn
  sheet. A row and a checkbox in the legend, **on when the page opens**. The worker takes a third
  prefix, the offline run walks each level three times and never asks a tree for a level it does not
  have, and the panel is told not to take the overlay for the sheet. 9,330 tiles, 104.0 MB; a band
  costs 11 MB more and the whole map 104 MB more. `make shade`, `--tree shade`, and a check of eight
  readings in the drive — 690 a page on Abisko, 682 on Lomsdal-Visten, which declares the check a
  chosen skip because Kartverket's sheet has no model of ours behind it. `make drive` pinned to
  `playwright==1.62.0` on the way past: the newest release wants a Firefox build this box does not
  hold, and the failure reads like a missing browser.

- **2026-09-13, seventh of the day** — a tap lands on the line, and not only on its junctions
  (§9.29), reported from the phone as *once one straight line is drawn, every tap after it is one*.
  `snapped` asked only the nodes, and 37 % of Abisko's network (32 % of Lomsdal's) lies more than a
  finger's width at z15 from any node. The line is asked as well, over the match mode's edge index;
  a point on an edge is routed from either end of it at the edge's own price and the piece to the
  end is drawn as path — in a plan's leg and in the way to a goal. The row's word goes by the
  greater part of the leg, `state()` says what each leg has drawn, and a new check taps into the
  page's longest edge. 677 readings a page, republished at 3,570,634 and 17,128,756 bytes,
  byte-identical from the edge. Then the hole came back with its GPX: a plan restored from its
  file laid a leg made after an edit out as the file's leg from the same first point, whatever
  the far point had become (`restoreTo`). 681 readings a page, republished at 3,571,588 and
  17,129,710 bytes, byte-identical from the edge.

- **2026-09-13, sixth of the day** — a goal becomes a plan, and a place offers what can be done
  with it (§9.28), all three asked for from the phone in one message. *Make a plan of this way*
  stands on the goal's own page and on the page the flag opens without a position — which is where a
  reader without a fix actually is, since the goal's own page is the way there and there is none.
  The places become the plan's points in order, the reader's position in front of them where the
  page knows it, and the goal comes off the map. And the page of any place — a hut, or a position
  typed into the search — now offers a stop on the way while a goal stands and a waypoint while a
  plan is being made, so coordinates reach both without anything new reading them. Driven, 660
  readings a page, and published the same evening — byte-identical from the edge, page and
  companions only. Then the offer turned out to be unreachable in plan mode, which is what the next
  question from the phone was about: a popup's page kept its place against the plan's own refreshes,
  and the check learned to read what a finger could do. Then the mark itself could not be got back
  to: an 18 px target, and a page that came back folded. And the legend, which is this map's layer
  control, said *off* about a layer a search result had switched on — it followed its own presses
  and not the map. 665 readings a page, republished at 3,555,297 and 17,113,415 bytes. Then the
  waypoint offer turned out to be made only where nothing can be selected — with plan mode on
  every tap is a waypoint — so it is *Add to the plan* while a plan stands, mode on or off, and the
  press leaves the mode as it finds it (Uwe: switching it on would take the next place away again).
  667 readings a page, republished at 3,556,256 and 17,114,378 bytes, byte-identical from the edge.

- **2026-09-13, fifth of the day** — the search lists what it finds and reads a position
  (§9.27), asked for from the phone. Typing no longer hides the map: the matches are rows, one per
  named thing, nearest first, saying which layer each came from and how many lines carry the name;
  a row taken fires the click that thing's own handlers are wired to, and switches its layer on if
  it is off. And `68.39275, 18.68033` — the string the *Copy a position* tool copies — is read back
  as the place it names, in decimal or in degrees, minutes and seconds, marked on the map and set
  as a goal through the button a hut's popup carries. One function serves both pages. Both pages
  published the same evening — page and companions only, nothing in the tile trees — and
  byte-identical from the edge, 3,540,231 and 17,098,349 bytes. Uwe read the published page and
  found two faults within the hour, both fixed and republished the same evening (3,543,170 and
  17,101,288 bytes): *Set as goal* stood on the mark's page twice, and a goal set with the position
  switch off could be neither read nor dropped — the second one older than this change and reachable
  from any place's popup. §9.27 has both.

  **And a publish stops being a question.** Uwe's standing word, given with this one: publish
  directly, *as long as nothing breaks the offline cache*. So the condition to check before each
  one is the kept ground — the worker, the store it keeps tiles in, the addresses they are kept
  under, and the tile trees themselves. A change that leaves all four alone goes out; a change that
  touches any of them is asked about first, because what it costs is somebody's map in a valley
  with no signal. This one left all four alone: the diff is the search box, one line in the chrome
  and a comment.

- **2026-09-13, later still again** — a name stops where the register stops (§9.26), reported
  from the phone with a sign photographed at the trailhead. A chain took the union of its
  pieces' names, so Topografi 50's marked trail carried BD 18 for eight kilometres past the end
  of BD 18, to a Björkliden the register numbers differently; over the box 38.0 of 170.5 named
  kilometres were not the trail they claimed, 4.3 km off at worst. The chaining rule now refuses
  to run a named piece into an unnamed one — and deliberately still joins two *different* names,
  so the register's own BD 21 / BD 92 / BD 16 / BD 91 chain stands (§9.22). 2.6 km off now,
  122 m at worst; 866 chains become 886. Lantmäteriet's marked trails carry the Naturkartan link
  too, which is the other half of what was asked. And *BD 6* on the sign is a Fjällkartan sheet,
  not a trail number. Both pages published at Uwe's word the same afternoon, page and companions
  only — nothing in the tile trees changed — and byte-identical from the edge, carrying the
  2,436 m BD 18 chain where a 12,353 m one used to be and 57 Naturkartan links where there
  were 17.

- **2026-09-13, later still** — a fix that does not arrive no longer stops the watch (§9.25),
  asked for by Uwe from the phone. The mode stands, the page asks again by itself every 30 s
  because a watch that has answered *position unavailable* never calls back (measured, 108 s),
  and the last place is kept and drawn red — dot, dashed ring, both switches — with its age said
  under it. The goal keeps a place to route from. §10's own heading, lost when §9.24 was written
  in above it the same day, is back. Both pages published at Uwe's word the same afternoon, page
  and companions only, byte-identical from the edge.
- **2026-09-13, later** — the box widened to 18.15–19.10 E, 68.139–68.46 N at Uwe's word (§2,
  §9.24): the valley path through Lapporten whole, the south on the tile row's edge; tiles
  resumed into stand 1, heights and graph rebuilt, 866 chains; BD 31 joins the Naturkartan
  catalogue. Published at Uwe's word the same morning: the sync added 28,028 tile objects
  (165 MB, 749 s) and 70 height tiles, the page byte-identical from the edge, new tiles at the
  east and south edges answering 200, the index in the bucket carrying the new box.
- **2026-09-13** — the whole map to z17 on Abisko (§9.23): the offline panel's cap is the
  source's own figure, z16 on Kartverket and z17 on Lantmäteriet, where it is the whole copy;
  the drive reads the count at the cap. Both pages republished at Uwe's word the same morning.
- **2026-09-12, later still** — Naturkartan's pages linked from the state trails (§9.22, §5):
  its Abisko tours are the county's state trails, so the ways were already drawn and preferred;
  a hand-kept catalogue of thirteen pages, one link per *BD* number on a chain, under the
  *Published elsewhere* heading. The drive reads the links on both pages. Both pages
  republished at Uwe's word in the small hours of 2026-09-13, byte-identical from the edge.
- **2026-09-12, after that** — kept tiles survive a new stand (§9.21): the worker answers a
  miss from the old stand, Keep replaces and sweeps; `deploy --drop-tree` deletes an old
  version from the bucket, never the current one. Both pages republished at Uwe's word the
  same night, read back from the edge byte for byte.
- **2026-09-12, last of all** — a new stand of the tiles is a new version chosen by `make tiles`
  itself, and the page draws the newest complete one (§9.20); §8.1 loses its cadence question.
- **2026-09-12, last** — the two tap checks driven on Abisko's ground (§9.19): a tap beside the
  Kungsleden, a loop along the Torneträsk shore; nothing is skipped on either page now, and
  the z12 snap distance is a scene figure rather than a Lomsdal literal.
- **2026-09-12, republished** — both pages and their companions at Uwe's word (`just deploy
  --map abisko`, `just deploy`; the trees untouched), read back from the edge byte for byte,
  page and worker; the trailing-slash fix measured live (§9.17), the whole map counts 2,343
  tiles against the bucket (§9.13).
- **2026-09-12, the rest of the review** — §8.2 items 2–15 fixed (§9.14–§9.18): the drive names
  its skips and exits 1 on any other; the names join the nearest head and letter on either
  name; the page drops a trailing slash itself; the tree refuses another stand of the file; the
  build sees only its own keys; this document's status lines and the READMEs brought current.
  Both pages rebuilt and driven clean.
- **2026-09-12, first fix** — the whole-map download no longer stalls on the box's edge
  (§9.13): the margin is clipped to the tree's extent and a 404 is not a refusal.
- **2026-09-12, after the review** — the whole app reviewed (§8.2): fifteen findings, three of
  them high — the whole-map download stalls on the box's 404 ring, the drive exits 0 on a lost
  chain, and this document's own status lines — written down before any is fixed, and fixed in
  that order.
- **2026-09-12, last of all** — a place with two names shows both, Swedish first (§9.12):
  `ortnamn.paired` joins the register's per-language points into places; 8 places over the box
  carry a second name. Republished at Uwe's word, read back from the edge byte for byte.
- **2026-09-12, later still** — the two water checks driven on Abisko's ground (§9.11): a bay
  of Torneträsk for the sound, the Abiskojåkka for the river a goal wades to; the river's Sami
  name noted as a question.
- **2026-09-12, later** — `make abisko` (and `just abisko` from `home/trails-map`, which supplies
  the login): tiles → dem → graph and report → page in one run, every step resumable or
  cached; builds only, the deploy stays `just deploy --map abisko --tree tiles --tree dem`.
- **2026-09-12, later that night** — the variant icon (§6.2, §7 step 3): the cairn in Lapporten's gate,
  `Companions.mark`; the national parks' gold star looked at and not used. Republished the same
  hour at Uwe's word: page and companions, the trees untouched.
- **2026-09-12, night** — **the Abisko map is published** (§7 step 6): page, companions and the
  height tiles in the bucket, the tiles were there already; verified from the edge byte for byte.
- **2026-09-12, evening** — `make drive` drives both pages (§9.10, §7 step 6): a `Scene`
  per page in `drive_map.py` carries what was Lomsdal-Visten's; eight faults of the suite's
  own found by the second page and fixed. §8.2 settles into §9.10.
- **2026-09-12, later** — Ortnamn ordered by Uwe and read (§9.9): `io/sources/ortnamn.py`, the
  name layers, the search, the cabins' and the rivers' names off the register, the lettering
  kept for the size. §8.3 settles into §9.9.
- **2026-09-12** — the Swedish branch of the build (§4.1, §4.4, §7 step 4): `build_sweden`
  beside `build_norway` and one `assemble` for both; `topografi50.Source` gains cabins, water,
  rivers, lettering and trail points; `maps.HeightTiles` on the provider, read by the page for
  straight legs, kept by the worker and the offline panel — the panel keeps them over the kept
  set rather than the whole box, for a measured reason (§6.3); `route_graph.py --park`. The
  first Abisko page built, driven in Firefox, its tile reading measured against the mosaic. On
  the way: the offline panel keyed kept tiles by a root-relative address the worker never asks
  for (§9.8). Ortnamn answered 403 until ordered: the lettering stood in for an hour.
- **2026-09-12** — the download API ordered by Uwe and the order id in sops; the loader run
  against the real API, 1.8 MB/s measured (§9.7). §8.2 settles into §9.7; §8 renumbered.
- **2026-09-12** — §7 step 4 done: `network/sweden.py` on a shared `network/graphs.py`, with
  `io/sources/naturvardsregistret.py` (nightly files, not the WFS — §9.6), `io/sources/topografi50.py`
  (the Geotorget delivery API, tested against a stand-in, 403 until the API product is ordered —
  §7.1, §8.2) and a bilinear reader off the height mosaic in `markhojd.py`. The delivery was
  found ready and fetched once through the browser (§7.1); §5 carries what the box holds; the
  marked trails are a source of their own, for a measured reason (§7.4). First build over the
  box: 813 chains, 39,775 edges, 44 s. §8.1 loses the WFS item; §8.2 is new; §8 renumbered.
- **2026-09-12** — Naturkartan weighed as a source of curated tours and declined (§5): private-use
  terms, no GPX, API behind a token; the lines are the county's and come through the register.
- **2026-09-12** — the tiles are in the bucket: 118,967 objects, 700 MB, 57 minutes, verified
  from the edge (§7 step 3). Naturvårdsverket's WFS answered 503 today; noted in §8.1.
- **2026-09-12** — the height tiles are built (§6.3, §7 step 5): `markhojd.py`, `dem_tiles.py`,
  `utils/tiles.py`, `make dem`; 540 tiles, 49.3 MB, z13 at 92.7 kB, in 62 s from a cached 4 m
  mosaic. `rasterio` added. §8.1 loses the tile-weight question. Not uploaded.
- **2026-09-12** — the height COGs measured with the login (§6.3): 212 squares, EPSG:5845,
  512-px blocks, overviews 2/4/8, water flat at lake level rather than nodata, ~83 MB to read
  for z8–z13. §8.1 shrinks to the area cut, the FTP cadence and the packed tile's weight.
- **2026-09-12** — the plumbing of §7 step 3: `maps.Provider`/`PROVIDERS` with `TOP` and
  `WEIGHT` per provider and `BaseMap.LANTMATERIET_TOPO` on our own bucket; `maps.Companions`
  naming worker, manifest, icons, database and caches per map with `ROOT` untouched; `--park`
  and the `Park` table in `lomsdal_visten.py`, Abisko declared and refused until step 4;
  `deploy_map.py` uploads companions by `Companions.of`. The Lomsdal page rebuilt with the same
  names and the same ceilings. §4.1, §4.2, §6.2, §7 follow.
  And the tile upload was run — Uwe asked for it — as `abisko-tiles-upload`.
- **2026-09-12** — the tile upload is code: `deploy_map.py --tree tiles|dem` mirrors a tree by
  `aws s3 sync` with a year's `max-age`, the inventory apart with a short one; `--tree` alone
  publishes no page; the purge settings are demanded only when a page is purged, which
  `.env.example` had promised and the script had not kept. Dry-run against the bucket: 118,967
  objects found missing in 27 s. §4.5, §6.2 and §7 follow. Nothing uploaded.
- **2026-09-12** — the full copy is done: 118,967 tiles, 696 MB, 916 s, none missing; the
  per-zoom weights are in §3 for the `WEIGHT` table; the 95-minute estimate is corrected.
- **2026-09-12** — the tile copy is code: `remote_sqlite.py`, `sources/lantmateriet.py`,
  `lantmateriet_tiles.py`, `make tiles`, with tests against a local stand-in for the file. A
  z8–z12 run took 18 s for 160 tiles; the full run is under way as the unit `abisko-tiles`.
- **2026-09-12** — the FTP reader prototyped and measured: 0.048 s a tile, ~95 min for the box;
  orientation and cartography confirmed against the viewer. §3 carries the figures, §8.1 shrinks,
  §9.5 settles the cartography question.
- **2026-09-12** — the trip date is dropped as an input (§1, §9.4): no deadline, no shortcuts.
  §8 renumbered.
- **2026-09-12** — both Geotorget orders placed, Topografi 50 (Abonnemang, Sverige) and
  Markhöjdmodell Nedladdning, and the login is in `home/trails-map`'s sops file — written from
  forge over ssh with `sops set --value-stdin`, since forge can decrypt that module. Step 1 of §7
  is done; what remains of it is waiting for the deliveries.
- **2026-09-12, evening** — Topografi 10 gives way to Topografi 50. The order form for 10 ends in
  a *juridisk prövning* asking for a Swedish personnummer, because the product carries personal
  data; 50 is CC0, unreviewed, and keeps every mountain class 10 has (fords, emergency
  telephones, the worn path, the marked trails). §5 and §7 follow; the order is for all of Sweden
  as an Abonnemang.
- **2026-09-12, evening** — colour sheet only for Abisko; the grey sheet is dropped (Uwe: never
  used on Lomsdal-Visten). §3 and the bucket layout in §6.2 follow.
- **2026-09-12, evening** — §8.2 gains two checks for the first build: that the free file's
  cartography is the paid service's, and how often the file is refreshed. Asked by Uwe as
  "what does the free product lose": one zoom level (z18, upsampling at this latitude), the
  live freshness, and the build effort; it gains independence and terms that fit redistribution.
- **2026-09-12, evening** — the tile source changes. Uwe's Geotorget order form showed the
  cache service at 10,375 kr/år; measured on Geotorget, every live tile service is paid and the
  free WMTS is z14 only and retires 2026-12-31. The free product is the same tiles as a
  GeoPackage on anonymous FTP, a plain XYZ pyramid z0–z17 in 3857 (read from the file itself).
  §3 rewritten; §6.1 withdraws the proxy Worker; §6.2 gains `tiles/`; §6.3's heights move
  from WCS to the STAC COGs behind the Geotorget login; §7 and §8 follow; §8.1 (terms) settles
  into §9.3. The two `LANTMATERIET_*_KEY` sops entries are dropped again.
- **2026-09-12** — §7.1 names the sops entries for the Lantmäteriet credentials and the
  registration link.
- **2026-09-12** — §5 rewritten around Lantmäteriet's *Topografi 10 Nedladdning, vektor*, which
  Uwe asked about as the N50 of Sweden and which turns out to be that and more (fords, emergency
  telephones, the worn-path class); the Swedish module shrinks to three loaders. §7.4 follows.
- **2026-09-12** — §6.2 changes from two origins to one origin, one bucket, companions named per
  map, after Uwe asked for the same domain and bucket and accepted that both maps are interim;
  the bucket layout is written down and checked against the hosting module. §6.3 changes from a
  grid in the document to height tiles in the bucket, built here and reused by `atlas`.
  §7 and §8.3 follow.
- **2026-09-12** — Kedketjårro dropped as a marker (Uwe: the E10 makes it irrelevant); §8.1
  and §8.2 move to §9 as settled, the rest of §8 renumbered.
- **2026-09-12** — the north edge is set by the E10, which Uwe wants inside whole: its
  northernmost point in the box is 68.443 N, the edge is 68.46 N. Replaces the 68.55 N assumption;
  Kedketjårro now only matters if it lies further north. Tile counts re-computed.
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
| the E10's northernmost point | Overpass, `way["highway"]["ref"~"E ?10"]` over 68.10–68.70 N, 18.05–19.10 E, `out geom`, 40 ways and 1,598 points, filtered to the box's longitudes |
| area and tile counts | spherical area of the box; WebMercator tile index at each zoom from the box's corners |
| bytes per Kartverket tile | 6.76 GB over 131,033 tiles, both from the offline panel at load (`atlas` §3.3) |
| what in the code is Norway | a read of `maps.py`, `lomsdal_visten.py`, `route_graph.py`, `deploy_map.py`, `drive_map.py` and `libs/src/trails/io/sources/` on 2026-09-11, with line numbers as they stood that day |
| Lantmäteriet's grid, layers, ceiling, and its white outside Sweden | `atlas/docs/decisions.md` §3.7, measured 2026-09-11 |
| how much of the network lies beyond a finger's reach of a node | every walked edge of each built page's graph in Firefox, sampled every 25 m, the straight distance to the nearer of its two end nodes against 10.5 / 21 / 42 / 84 / 150 m; edge lengths summed from the vertices (`/tmp` script, 2026-09-13; the check *a tap in the middle of a long edge* reads the longest edge the same way) |
| how much of a named chain is the trail it names | every Topografi 50 marked-trail chain read off the built page in Firefox, its name from the packed figures, its line sampled every 50 m against the register's summer lines for that BD number in SWEREF 99 TM |
| the page's tile reading against the build's mosaic | the page's bilinear rule re-implemented in Python over the z13 tiles on disk, against `markhojd.sample` off the cached 4 m mosaic, at 2,000 uniform random points of the box and along the straight leg planned in Firefox |
| whether either sheet already carries shading | the tiles themselves: Lantmäteriet's `topowebb` at z14, z15 and z16 over Latnjajávri and Kartverket's `topo` at z14 over Lomsdal-Visten, opened and looked at — no relief in any of them |
| the strength the relief is drawn at | a 512 px crop of the z15 flank west of Latnjajávri composited at 35, 40, 45, 50, 55, 60, 70 and 80 %: WCAG contrast of contour pixels against ground in the darkest tenth, and the luminance of shaded ground against unshaded; the share of the crop with alpha over 0.5 and over 0.8 at z12 and z15 |
| z14 against z15 for the relief | one tree cut to z15 and drawn twice through Leaflet's `maxNativeZoom`, at z15, z16 and z17 over the same steep flank, side by side with the unshaded sheet |
| the steps a relief tile is stored in | forty z14 tiles re-encoded at 256, 128, 64 and 32 steps of alpha and at palette-with-`tRNS`, mean PNG bytes each; the worst step each puts into the drawn sheet computed as `250 × step/255 × 0.55` |
| what the relief costs a reader offline | `window.trailsOffline.choose()` then `state().counted` on the built page and on the published one, same scopes and zooms, in Playwright Firefox |
| whether the page's own update call is needed | two one-page tests behind the tunnel, `register()` alone and `register()` + `update()`, each loaded three times on Firefox here and on the iPhone in Safari; a Python server logging every request with its `Service-Worker` and conditional headers, the scripts served `private` so the edge cannot answer for them |
| the straight leg in Firefox | `analysis/output` served by `http.server`, `abisko.html` opened in Playwright Firefox, `window.trailsPlan.place()` twice over open fell, `state()` read back, the `dem/` requests counted |
| which Lantmäteriet products carry a fee | Geotorget product pages rendered in Playwright Firefox (the site is a single-page app): the `Avgift`, `Villkor`, `Åtkomst` fields of the cache, WMS, vector-tile, översiktlig, raster-download, Topografi 10 and Markhöjdmodell products |
| the FTP GeoPackage's tile matrix | `curl -r 0-67108863` off the anonymous FTP, the SQLite page count at byte 28 patched to the truncated size, then `gpkg_tile_matrix_set` and `gpkg_tile_matrix` read with `sqlite3` |
| FTP range-read cost | five 64 KB `curl -r` reads, 3.2 s in all; then `ftplib` on one connection, five reads each of 4 KB, 64 KB and 1 MB |
| the tile copy's cost and the row order | an `apsw` VFS over `ftplib` with 1 MB blocks, reading every z13 tile of the box and rowid runs at 1 and 20,000,000 |
| file against service | the z13 centre tile from the file and from `minkarta.lantmateriet.se/map/topowebbcache` (KVP GetTile), compared as luminance with Pillow and numpy at shifts of 0 and ±1 px |
| the STAC height API | `GET /stac-hojd/v1`, `/collections`, `/search?bbox=` without credentials; one COG opened with rasterio over `/vsicurl/`, which answered 401 |
| the översiktlig product's zoom range | its technical description PDF v1.0.3, text extracted |
| Topografi 10's and 50's themes, feature types and delivery | Geotorget documentation GEODOK/51 and GEODOK/76, the *Kommunikation*, *Byggnadsverk* and *Åtkomst och leverans* pages, read 2026-09-12 |
| which products face a legal review | the `Juridisk prövning` field on the Geotorget product pages, rendered in Firefox: Topografi 10 *Ja*, Hydrografi Nedladdning *Ja*, Topografi 50 / Ortnamn / Markhöjdmodell *Nej*; and the *Sökande* form Uwe reached on 2026-09-12, which asks for a personnummer |
| Swedish service URLs | Naturvårdsverket's *Leder och friluftsanordningar, beskrivning av öppna data* (PDF), Lantmäteriet's and Naturvårdsverket's product pages, read 2026-09-11 |
| DEM tile counts and pixel sizes | WebMercator tile index over the box at z8–z13; 156,543 m · cos(68.3°) / 2^z |
| Abisko's logotype and its terms | `sverigesnationalparker.se/park/abisko-nationalpark/` (the SVG `abisko-logotyp.svg`: the star as a clip path with a radial gold gradient, the name as outlined glyphs), Naturvårdsverket's *Sveriges nationalparker — bilaga logotyper* (PDF, v2.0 2011-06-01), pages 5, 16–18; the trademark register at PRV not consulted |
| the register's two languages | every Swedish name over the box against the nearest name of another language and the same type, in SWEREF 99 TM: the distances quoted, and the whole ranked list, read on 2026-09-12 |
| the water checks' ground | the cached Abisko graph as a `networkx` graph weighted by edge length, Topografi 50's lake polygons over 0.5 km² and the river surface nearest the name *Ábeskoeatnu*; node pairs 1.0–1.5 km apart with over 60 % of the line on a lake and a way round under 10 km; for the river, every vertex of every edge within 1.5 km of a far-bank node priced as the page prices a departure, one bounded Dijkstra per standing node |
| the Abisko drive | `drive_map.py --page analysis/output/abisko.html --json` as a transient unit on forge, Playwright Firefox 1400 × 900, the page served from `analysis/output` by the suite's own server; four runs on 2026-09-12 to get from a crash in the second check to a clean report, the Lomsdal page driven in between to hold |
| the tap checks' ground | the cached Abisko graph as a `networkx` graph weighted by edge cost; for the tap, every fifth node of the Kungsleden chain with the perpendicular to its two edges laid 135 m and 163 m out, kept where no edge is nearer than 100 m and the segment crosses no Topografi 50 water polygon, the start a chain node 1.9–2.1 km along; for the loop, every sixth marked-trail node in the park against every marked node 600–1,800 m off whose bounded Dijkstra cost is five times the line or more and whose line is dry, the first tap a marked node 1.5–2.5 lines along by cost that stands at least three quarters of that straight off |
| the review of 2026-09-12 | five readers over the code, each verifying its own findings with `uv run` snippets, Playwright Firefox against the built tree served locally, and `curl` against the edge; the high and medium findings re-read or re-measured by hand (`curl -sI` on the ring tiles, the pairing and lettering code, `drive()` and `report()`) before §8.2 was written |
| SWEREF99 TM against UTM 33N | the two projections' parameters: both TM, central meridian 15° E, scale 0.9996, false easting 500 km |
| Naturkartan's pages | `curl -sL` against `naturkartan.se/sv/search/sites?query=…` for every place and number in the register's state-trail names over the box, then each page fetched and its `data-naturkartan-preselected-site-id` read; the short forms `/sv/sites/<id>` and `/sv/norrbottens-lan/<id>` tried and 404; `api.naturkartan.se/v3/sites/12849` 401 |
| the river ground after the widening | Playwright Firefox against the built page served locally and the published one: `window.trailsGoal.set` from a located standing spot, `state()` read routed and with `stayOnPaths(true)`; `window.trailsGraph.waterAt` sampled 200 times along the old line and over a 41 × 41 window of cells; `window.trailsPlan.geometry()` walked with the distance to the nearest of `nodeLon`/`nodeLat` at every fifth point; then standing spots and goals taken from the cached graph's nodes within 800 m and 600 m of the old ones, 8 × 8 pairs tried on the page |
| that a failed watch never calls back | Playwright Firefox against a bare chrome page rendered from `maps.py` (no tiles, no data): `context.set_geolocation(None)` with the watch running, then a position restored and the page read at 3, 10, 20, 30 and 45 s — every reading still *no fix*, 108 s in all; the same probe with the retry in place recovered 15 s after the position came back, with nothing pressed |
| the coordinate forms the search reads | twenty-two strings through the page's own `readCoordinate`, rendered out of `maps.py` and run in node, then five of them through the built page in Playwright Firefox and measured against the position they name |
| the shares of the ground per slope class | the cached 4 m mosaic read in 2,048-post blocks with `rasterio`, smoothed by one post as the relief is, `np.gradient` over 4 m, `arctan(hypot)` in degrees, a histogram of 101,091,830 posts; the excerpt's shares from the mockup tree's own `index.json` at z15 |
| what a slope-class tile weighs | sixty random 113-post blocks of the mosaic classed under three schemes and written as palette PNGs at 256 px, then the whole box built with `make slope` and its `index.json` read per zoom |
| the documented slope classes | swisstopo's *Hangneigungsklassen ab 30 Grad* record on geocat and the Geomatik Schweiz note on the class over 50 (January 2026); the EAWS glossary; the SAC scale on Wikipedia and in the bergundsteigen article on its revision; the DNT's *Gradering: Vandring* PDF; the DAV's article on pathless walking — every one read for a number in degrees, and only the avalanche sources had one |
| what the slope classes cost offline | Playwright Firefox against the built page served locally, the panel opened with `window.trailsOffline.open(true)`, then `choose('all', z)` and, with the long chain selected, `choose('band', z)` at z16 and z17, `state().counted` read each time; the §6.6 figures as the baseline |
| lettering under the slope classes | WCAG relative luminance and contrast ratio computed in Python for black ink (20,20,20) and the sheet's cream (250,240,220) under each class colour, opaquely at α = 150/255 and multiplied as `base × (1 − α + α · colour)`; the same formula runs in the mockup's legend and in the unit test |
| that the blend is on the layer | Playwright Firefox against the mockup through the tunnel: `getComputedStyle` of every `.leaflet-layer` container read as `mixBlendMode`, once with the switch on and once off |
| the ground over 55° | the whole-model histogram of §6.7 read at 50, 55, 60 and 70 |
| the licensed text layer's price | Lantmäteriet's *Avgifter och leveransinformation för geodata* v2.31 (2026-05-29), the *Visning* rows and the transaction table, converted at 0.0885 EUR/SEK |

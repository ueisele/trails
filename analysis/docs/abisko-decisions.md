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
added to one's own copy — not a layer of this map.

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

The second: they need not. Once every device has loaded the new page, the old tree serves
nobody; until then an installed page that has not refreshed still names it when browsing
online. Dropping it is a decision, so it is an option and not a step: `command make deploy
ARGS="--drop-tree tiles/lantmateriet/topowebb/1"` deletes that version from the bucket,
refuses anything that is not a version directory of a known tree, and refuses the version the
tree on disk calls current — the one the next page build draws. The directory on disk is left
to be removed by hand.

---

## 10. Changes

A line per change to this document or to the decisions in it, newest first.

- **2026-09-12, after that** — kept tiles survive a new stand (§9.21): the worker answers a
  miss from the old stand, Keep replaces and sweeps; `deploy --drop-tree` deletes an old
  version from the bucket, never the current one. Republish pending Uwe's word.
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
| the page's tile reading against the build's mosaic | the page's bilinear rule re-implemented in Python over the z13 tiles on disk, against `markhojd.sample` off the cached 4 m mosaic, at 2,000 uniform random points of the box and along the straight leg planned in Firefox |
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

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
sized to the rows that sit together, not one connection per page. The order of magnitude is
hours for the ~119,000 tiles of z8–z17, and it is measured on the first build (§8.2). The
alternative, if Geotorget's order-by-area exists for this product as one search result
claimed, is a GeoPackage cut to the box; checked when the account is used.

**Storage.** z8–z17 over the box is 118,967 tiles; at the 20 KB a z13 Swedish tile measured
that is about 2.4 GB, at Kartverket's 50 KB about 6 GB, in the bucket, once, for each of the
two sheets. R2 storage is cents a month and egress is free.

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
| base map | Kartverket cache, live | Lantmäteriet *Topografisk webbkarta Nedladdning, raster*, free with attribution, anonymous FTP, copied into our bucket at build time | z0–z17 XYZ pyramid, measured (§3) |
| **the N50 role: paths, roads, water, land cover, cabins, names, contours, protected areas in one product** | N50 Kartdata, per kommune | Lantmäteriet **Topografi 10 Nedladdning, vektor** — GeoPackage, SWEREF99 TM, RH 2000, updated weekly, ordered by country, län or kommun through Geotorget and its download API; free since 2025-02-03 under the *värdefulla datamängder* terms (attribution), a Geotorget account needed. **Topografi 50** is the generalised sibling, CC0, same themes | read 2026-09-12 off the product documentation, see below |
| official marked trails with attributes | Turrutebasen | Naturvårdsverket *Leder och friluftsanordningar*: WFS `https://geodata.naturvardsverket.se/leder_friluftsliv/wfs?`, SWEREF99 TM | keyless; carries summer *and* winter trails, marking and manager — the attribute source, as Turrutebasen is (`atlas` §7.2) |
| paths nobody else draws | OSM | OSM, through Overpass, unchanged | the one source that is the same in both countries |
| cabins, shelters, bridges | N50, UT.no | Topografi 10 `Byggnadspunkt` — `Raststuga` (*"alltid olåst"*), `Vindskydd`, `Kåta`; Naturvårdsverket `anordningar_friluftsliv/wfs`; OSM `alpine_hut` / `wilderness_hut` | STF's cabins are in all three |
| protected areas, and the park lookup | Naturbase | Topografi 10 *Tema Naturvård*, or Naturvårdsverket's *naturvårdsregistret* WFS/REST | either replaces `find_one(PARK_NAME, …)` |
| roads | N50 | Topografi 10 `Väglinje` (Trafikverket's roads, 15 classes) and `Övrig väg` | OSM as the check |
| water | N50 Arealdekke | Topografi 10 *Tema Hydrografi* | Torneträsk and the lakes drive the straight-walk water cost |
| place names | Stedsnavn | Topografi 10 *Tema Text* — Lantmäteriet's established names, Swedish and Sami | the search box reads this |
| heights | Geonorge point API, live | Lantmäteriet *Markhöjdmodell Nedladdning*: 1 m COGs through a keyless STAC API, downloads behind the Geotorget login, CC BY 4.0, **RH 2000** | §6.3 |
| land cover | not used | Topografi 10 *Tema Mark* (`sankmark`, `kalfjäll`, forest); NMD 10 m raster exists too | Tema Mark is enough if the water cost ever wants bog |

**Topografi 10 is the N50 of Sweden, and in the mountains it is more.** Read 2026-09-12 off
Geotorget's documentation (GEODOK/51), *Tema Kommunikation*, `Övrig väg`:

- `Gångstig` — *"tydlig väl upptrampad stig"*, the worn path, which is the FKB-like detail N50
  lacks and Norway gets from a second source;
- `Vandringsled` — *"markerad led längs stig eller väg avsedd för vandring"*, the marked summer
  trail;
- `Vandrings- och vinterled` — the trail marked with red crosses for walking, skiing and
  snowmobiles, which is Kungsleden's kind; the attribute `skoterkorning_tillaten`
  (`Ja`/`Nej`/`Påbjuden`/`Ingen information`) is one of the fields that tells winter from summer
  (§6.5), together with Naturvårdsverket's season field;
- `Transportled fjäll` — reindeer-herding routes and boat passages inside Lantmäteriet's
  mountain area, **not walking routes**, and to be kept out of the graph;
- `Ledintressepunkt fjäll` — **fords (`vad`), emergency telephones, parking, navigation aids.**
  A ford is exactly what the straight-walk water cost of the predecessor wants to know about,
  and no Norwegian source names them.

So the Swedish set is smaller than Norway's seven and not poorer: Topografi 10 carries what N50,
FKB, Naturbase and Stedsnavn carry between them, Naturvårdsverket's trail register is the
Turrutebasen, and OSM is OSM. `network/sweden.py` is three loaders, not seven.

Two things to settle at the first download, not now: which of Topografi 10's `Byggnad` purposes
name STF's larger huts (a `Raststuga` is the unlocked emergency kind, not a staffed *fjällstuga*),
and how large the Kiruna kommun GeoPackage is — the kommun is about 19,000 km², so ordering by
kommun is the right grain, but the file has not been measured.

Exact layer names, attribute names and the winter/summer field are read off the services when
the module is written, not guessed here.

Licences the credits will carry: Lantmäteriet's *värdefulla datamängder* terms with attribution for
the tiles and Topografi 10, CC BY 4.0 for the height model, Naturvårdsverket open data,
OpenStreetMap ODbL. Nothing CC0 is left in the Swedish set, and nothing NC. UT.no's CC BY-NC does not enter this map.

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
abisko.webmanifest                  start_url ./abisko, id abisko, name "Abisko Atlas"
abisko-sw.js                        scope /abisko, DB trails-abisko
abisko-icon-32.png … abisko-icon-512.png   a variant of the cairn, so the two icons differ
tiles/lantmateriet/topowebb/1/{z}/{x}/{y}.png            the map, colour sheet, §3 and §6.1
tiles/lantmateriet/topowebb_nedtonad/1/{z}/{x}/{y}.png   the grey sheet
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
`deploy_map.py`'s `BESIDE` table is keyed per map and gains the `dem/` directory. All of it is
Python-side naming; the worker's logic does not change.

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
- **Use** the build samples the tiles for every graph vertex; the page fetches them for the legs
  of a planned route and reads them from the offline store when the switch is on. Build and page
  agree by construction, because they read the same tiles. The offline chooser keeps the whole
  box's height tiles with any scope — at z13 and below they are a few per cent of any pack.
- **Caching** long `max-age` on the tiles, since the address carries the version; the deploy
  uploads the directory with `aws s3 sync` and purges nothing for it.

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
   What is ordered there, all free: *Markhöjdmodell Nedladdning* (§6.3) and *Topografi 10
   Nedladdning, vektor* (§5). **Nothing with a fee**, and the tiles need no order at all — they
   come off the anonymous FTP (§3). The login goes into `home/trails-map`'s sops file as
   `GEOTORGET_USERNAME` / `GEOTORGET_PASSWORD`, the names its `secrets.sops.env.example`
   records; the build reads them from the environment for the STAC downloads and the download
   API. No API key exists in this design any more.
2. **Infrastructure** — nothing. The bucket takes prefixes without a change (§6.2), and there
   is no Worker (§6.1).
3. **`trails`, the plumbing** — `--park` (§4.1), the provider blob with `TOP` and `WEIGHT` per
   provider (§4.2, §3), `drive_map.py` gains `--page`. And **the tile copy**: the box's tiles out
   of the FTP GeoPackage into `tiles/` (§3), measured for time and bytes on the first run.
4. **`network/sweden.py`** — Topografi 10 for the ground, Naturvårdsverket's trail register
   for the attributes, OSM for what neither draws; winter trails and reindeer routes excluded
   (§6.5).
5. **Heights** — the tile build (§6.3): WCS over the box, resample, pack, write `dem/`.
6. **Acceptance and publish** — the structural readings of `make drive` against the Abisko page,
   then `command make map --park abisko`, then `deploy_map.py --map abisko`, which uploads the
   page, its own companions and `dem/`.

Step 3's tile copy needs no credential and can start now; steps 4 and 5 need the login in sops.

---

## 8. Open

Triggers, not deadlines — the convention `atlas` §9 and `pipeline/TODO.md` use. When an item is
settled, move it to §9 with the date and what settled it.

### 8.1 The date of the trip

Decides how much of §7 is before departure. Unknown as of 2026-09-12.

### 8.2 What the first builds measure

*Trigger: step 3 and step 5.* The tile copy: seconds per tile over FTP with a persistent
connection, bytes per zoom for the `WEIGHT` table, and whether Geotorget offers this product
cut to an area; and **whether the file's cartography is the service's**, one z13 tile from the
file beside the same address from the public viewer — Lantmäteriet describes both as the same
two sheets, and it has not been checked. Also how often the FTP files are refreshed (dated
2026-06-22 to 24 when first seen). The heights: one COG opened with the login, its overview
levels, nodata and water marking, and the weight of a packed z13 tile. All written back into
§3 and §6.3.

### 8.3 `make drive` for a second page

*Trigger: step 6.* The 278 readings assert Lomsdal-Visten's figures. Which are structural and
hold for any page, and which are that park's numbers, is not yet separated.

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

---

## 10. Changes

A line per change to this document or to the decisions in it, newest first.

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
| which Lantmäteriet products carry a fee | Geotorget product pages rendered in Playwright Firefox (the site is a single-page app): the `Avgift`, `Villkor`, `Åtkomst` fields of the cache, WMS, vector-tile, översiktlig, raster-download, Topografi 10 and Markhöjdmodell products |
| the FTP GeoPackage's tile matrix | `curl -r 0-67108863` off the anonymous FTP, the SQLite page count at byte 28 patched to the truncated size, then `gpkg_tile_matrix_set` and `gpkg_tile_matrix` read with `sqlite3` |
| FTP range-read cost | five 64 KB `curl -r` reads, 3.2 s in all |
| the STAC height API | `GET /stac-hojd/v1`, `/collections`, `/search?bbox=` without credentials; one COG opened with rasterio over `/vsicurl/`, which answered 401 |
| the översiktlig product's zoom range | its technical description PDF v1.0.3, text extracted |
| Topografi 10's themes, feature types and delivery | Geotorget documentation GEODOK/51, the *Kommunikation*, *Byggnadsverk* and *Åtkomst och leverans* pages, read 2026-09-12 |
| Swedish service URLs | Naturvårdsverket's *Leder och friluftsanordningar, beskrivning av öppna data* (PDF), Lantmäteriet's and Naturvårdsverket's product pages, read 2026-09-11 |
| DEM tile counts and pixel sizes | WebMercator tile index over the box at z8–z13; 156,543 m · cos(68.3°) / 2^z |
| SWEREF99 TM against UTM 33N | the two projections' parameters: both TM, central meridian 15° E, scale 0.9996, false easting 500 km |

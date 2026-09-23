# Malingsbo-Kloten: what has been decided, what is open, and what changed

*Opened 2026-09-20. The plan that produced it is `malingsbo-kloten-phases.md`; once a phase
lands, its built-note goes under §10 here, and this file is the record — the plan is not.*

## 1. The decision in one paragraph

A third map, the second Swedish one: the Malingsbo-Kloten protected area in Bergslagen with
the town of Kopparberg inside the box, built the way Abisko is built — Lantmäteriet's sheet
copied into a tree of our own, the heights, relief and slope off the 1 m model, the
vegetation off NMD 2018, the mire off the wetlands and SLU's moisture, Topografi 50 and the
register and OSM for the network, the place names, the heritage register, Trafiklab's stops —
with every layer and overlay the Abisko page has and nothing the Abisko page lacks. Decided by
Uwe 2026-09-20, the seven points of the plan's §1 as proposed.

## 2. The area

Not a naturreservat: a **Naturvårdsområde** of 1981, three objects in Naturvårdsverket's
register, one per county, read from the cached nightly file `NVO.zip` (SWEREF 99 TM):

| NVRID | Län | Kommun | ha |
|---|---|---|---|
| 2000023 | Örebro | Lindesberg, Ljusnarsberg | 14,157 |
| 2002595 | Västmanland | Fagersta, Skinnskatteberg | 8,413 |
| 2002711 | Dalarna | Smedjebacken | 26,464 |

Union 49,034 ha, bounding box `15.1511, 59.8231, 15.7349, 60.0836`, 32.4 × 28.8 km. The
boundary the page draws is the union of the three; `Park.kind` says `naturvårdsområde` and
the register's form is carried on the park so the lookup asks for it by name and form.

**The box** is Uwe's rule: the area's bounding box widened on all four sides by the distance
from Kopparberg to it. Kopparberg's built-up area (OSM, 2026-09-20: the town node and the
residential, industrial, retail and commercial land use within 2.5 km, 54 ha, no building
west of it) overhangs the area's box on the west alone, by **10,247 m**. So:

**`(14.967, 59.729, 15.922, 60.176)`** — EPSG:3006 `498223, 6621686, 551135, 6670977`,
52.9 × 49.3 km, rounded outward to three decimals as Abisko's is. Ställdalen's station is
1.3 km outside the west edge and stays out; Kopparberg, Grängesberg, Ludvika, Smedjebacken,
Skinnskatteberg and Fagersta C are inside, with the halts Fagersta Norra, Söderbärke and Vad.
The box touches three counties, Örebro (T), Dalarna (W) and Västmanland (U).

Tile counts by `trails.utils.tiles.tile_count`: 692 height tiles z8–13, 9,756 per overlay
z8–15, 152,055 for the sheet z8–17 — five per cent over Abisko's 610 / 9,330 / 146,995.

### 2.1 The county joins are not the area's boundary — decided, 2026-09-23

Uwe saw breaks in the blue conservation boundary after the pinch's clipping frame was
removed. The three county records do not quite meet. Their exact union has three components
and 85 holes: the records' 19 holes and **66 seam slivers**, together 58.212 m². The widest
closed seam measured 0.061 m. Exterior-connected slivers draw the same false double line
into the area. The cached Topografi 50 boundary and the sheet agree on the area; changing
which protected area is drawn is not the remedy.

The three places inspected were `59.9862421394, 15.2190511997`,
`60.0026959810, 15.1935788949` and `59.9565910619, 15.2584040710` (latitude, longitude).
They lie on the county join. The blue fragments there must disappear. The investigation
sampled the actual painted paths on all three published maps: 672,521 samples in 604 views,
zero missing, at rest and through pinch and snap. It found no missing canvas stroke to fix.

**Uwe's decision: union with a tolerance**, after being told it would first be for the
drawing. **Review's decision after the Lomsdal witness: close only an area dissolved from
several records.** Naturvårdsregistret returns its source-record count as a column; the loader
takes it out of the page's columns and carries it explicitly as `Built.boundary_records`.
The Naturbase loader returns 1. There is no default at the hand-off to `add_boundary`, where
`close_for_display` copies the area, projects it to the source's metric CRS, buffers out and back by
`BOUNDARY_TOLERANCE_M = 1.0`, with mitre joins and their default limit, and returns to the
page's CRS. Both outline and fill use this copy. Routing, coverage, exports and the graph
keep the exact analytical geometry, whose WKB must remain byte-identical.

A single record passes through without reprojection or closing. Abisko's one register
record and Lomsdal-Visten's one Naturbase object have no dissolved join; their page boundary
GeoJSON must be identical to the published page's. The rule is about record count, not map
names, so a future multi-record area gets the same closing. This also removes the unnecessary
Lomsdal candidate's mitre-limit trim: its sharp tip at `65.651849575, 12.690137518` moved
1.131681 m. Increasing the mitre limit or the tolerance to accommodate it was not taken.

**The accepted gates** are valid geometry, three components and the 19 source holes, each
retained hole within the tolerance of its counterpart; directed displayed → exact distance
at most the tolerance for every retained ring; and every piece of the symmetric difference
empty after a negative buffer of `BOUNDARY_TOLERANCE_M + FLOAT_SLACK_M`, with
`FLOAT_SLACK_M = 0.000001` for floating-point slack in the measurement. Symmetric outline
Hausdorff was the wrong gate: removing a seam hole or an exterior-connected seam deliberately
removes a long false line, whose distance back to the displayed outline says nothing about
the sliver's width. The displayed-to-exact direction bounds where the new line goes.

Measured in the native EPSG:3006 source coordinates: the closing is valid, with three
components and 19 holes. All 66 seam holes vanish. The retained holes move at most
0.004949 m; the largest absolute hole-area change is 0.254633 m². Sampling every displayed
ring at intervals no greater than 0.1 m gives a maximum directed distance of 0.366730 m,
with a certified upper bound of **0.416730 m** (distance to the exact ring is 1-Lipschitz,
so add half the sampling interval). All 22 rings pass. The 99 changed pieces total
**68.377692 m²** over 490.342 km², all empty under the negative-buffer gate. Width, measured
as twice the extinction radius under negative buffering, is at most **0.654426 m**.

The earlier location gate was dropped in review: changes narrower than the tolerance are
allowed away from joins too. Nine pieces with extent over 10 m were proved to leave the
county line and the shared-record edges; together they cover **3.413933 m²**, widest
**0.654426 m**. Piece 94 is the example: 1.839749 m² of record 2002711's own narrow outline,
0.65 m wide, reaching 36.899 m from the next record's edge. These off-join changes were
accepted in review because they are below the tolerance. Their location is not a gate.

The drive reading `the_boundary_has_no_seams` reads the page's GeoJSON at full precision,
checks components, the recorded hole count and that no hole disappears under a negative
1 m buffer. It samples the painted outline at rest at z10, z12, z14 and z16, after redraw,
through held pinches and the snap. At the three former fragments it requires no blue at
z14, held z12.25, during the snap to z12 and after settling. The fragment probes are
`59.992135, 15.213832`, `60.001683, 15.205503` and `59.960595, 15.252162`, on the false blue
lines within the three investigated places. The control run on the published page finds
blue there in every phase. Every reading restores its view.

Evidence, scripts, source and page comparisons, and drive logs are in
`/home/eiseleu/mockups/zoom-rectangle/boundary-gaps/`; the investigation report is
`/home/eiseleu/mockups/zoom-rectangle/boundary-gaps-report.md`. The figures above are native
source measurements; the rebuilt-page comparison also checks the round trip through WGS 84.

**Built 2026-09-23.** All three pages rebuilt here from the read-only cache, with networking
disabled. The built Malingsbo boundary matches the display calculation exactly: valid,
three components, 19 holes, analytical WKB unchanged. Its three exterior directed upper
bounds are 0.050001, 0.416730 and 0.378621 m, in built component order; all 19 retained holes
are within 0.004949 m of their counterparts. The round trip leaves 99 changed pieces,
68.377697 m² in total, widest at most 0.654426 m; every piece passes the negative-buffer
gate. Abisko's two rings and Lomsdal-Visten's one ring have zero displacement: their boundary
GeoJSON is identical to the published page's. All three embedded routing headers and payloads
are also identical to the published pages.

The three requested readings ran twice per page in Firefox, 390 × 844 for the boundary
probe, with networking disabled: 95 readings per Abisko and Lomsdal run, 103 per Malingsbo
run, all green. The painted-path samples were 170,588 / 168,305 for Abisko,
217,452 / 217,452 for Lomsdal-Visten and 208,985 / 209,954 for Malingsbo-Kloten:
**1,192,736 samples, zero missing**. Both Malingsbo runs found zero blue pixels at all three
former fragments at rest, held z12.25, throughout snap and after settling. The 8f and 8l
readings stay green. Unit tests cover closing several records, preserving a single record
byte-for-byte, retaining real holes and components, and leaving the analytical input alone.
`command make hooks-run` passed with networking enabled.

The explicit record-count hand-off added in review was checked through the actual loaders
and `add_boundary`: all three serialized boundary GeoJSONs are byte-identical to these
builds, with analytical WKB unchanged. No rebuild was needed; the comparison is recorded in
`boundary-gaps/review-boundary-bytes.json` beside the evidence above.

## 3. The sources

Nothing had to be ordered. Every Swedish source Abisko reads is national on disk or an
account-level *Behörighet* at Geotorget: Topografi 50 as the whole-country subscription
(`.cache/topografi50/2026-09-08/`), the height model and the wetlands by STAC over the box
with the login, the place names as one country file, NMD 2018 converted nationwide, SLU's
moisture as one mosaic, the register's forms and trails, the GTFS feed and the stop register.
New for this box: the height mosaic, the wetlands' municipal files, three county files of the
Kulturmiljöregistret (`örebro`, `dalarna`, `västmanland`, all answering 200), OSM, the placed
stops and the graph.

**The state-trail register is empty here** (`Statliga_Leder`: 0 rows in the box), so the
Naturkartan catalogue, which links state trails by their BD number, has nothing to key on and
the map carries none (`naturkartan=None`). The register's other trails are there — 98 rows,
60.1 km, 85 *Vandringsled* and 12 *Naturstig*, *Vandringsleder i Klackberg*, *Bruksleden genom
Jättåsarna* among them — and draw as the *Leder* layer. Topografi 50's `*_fjall` layers read
empty here and the Sámi name pairing is inert; neither needs a branch.

**The gateway is Kopparberg**, a tätort in the place-name register (`BEBTÄTTX`, Ljusnarsberg,
län 18, 500306 E 6637425 N) with its station inside the box. `gateway` and `check_route`
move from the country row onto the park, and `check_route` is `None` here: there is no state
trail to check a route against.

## 4. A tree per map

`maps.PROVIDERS` binds a box to a provider — the extent the offline panel rings, the tile
root, every tree prefix, the byte tables — so a second Swedish map on `lantmateriet` would
collide with Abisko on all of them. Decided: a provider entry of its own,
`lantmateriet-malingsbo-kloten`, derived from Lantmäteriet's by `dataclasses.replace` with
its own extent and roots (`tiles/lantmateriet-malingsbo-kloten/topowebb/1/`,
`dem/lantmateriet-malingsbo-kloten/1/`, …), and a `BaseMap` member for it. Nothing of
Abisko's moves, no bucket object is renamed, a version bump of one map never recuts the
other. The alternative — one shared Swedish tree with the box per map — is recorded in the
plan's §1.2 and not taken.

## 5. The names

Stem `malingsbo-kloten`: `--park malingsbo-kloten`, `malingsbo-kloten.html` served at
`/malingsbo-kloten`, companions by `Companions.of` — `malingsbo-kloten-sw.js`,
`malingsbo-kloten.webmanifest`, `malingsbo-kloten-icon-*.png`, database
`trails-malingsbo-kloten` — and the app name *Malingsbo-Kloten Atlas*. The index Worker lists
it unasked and titles it *Malingsbo-Kloten*.

**The icon** is a variant of the cairn, as Abisko's is: the same cairn on the same moss path,
between two spruce silhouettes with a lake's line behind — Bergslagen's forest and water
where Abisko has Lapporten's gate. Candidates are drawn by `docs/draw.ts` and Uwe picks; the
build refuses a map without a drawing of its own.

### 7.2 The Bergslagsleden is named off OSM's relations — decided, 2026-09-20

Uwe, on the plan's measurement: the Bergslagsleden's four stages through the area are OSM
`route=hiking` relations and nothing else names the way; the Swedish loader reads ways only.
Decided: read the relations, carry their name, stage and `website` onto the member chains,
link the stage's own page and Naturkartan's from a catalogue keyed by name, no layer of its
own. Plan phase 8, after the publish.

### 7.3 Any text may stand in a name — fixed, 2026-09-20

The third build stopped writing the page: *a template literal was left open, so the page's
backtick parity does not hold*. An OSM path in the box is named ``EkMalm`sStig``, and the
page's whitespace squeezer, which keeps out of the JavaScript's template literals, told them
apart by counting backticks per line — so a backtick in *data* opened one. Uwe: the page
cannot depend on which characters a name holds; any text must be carried and escaped.

Two faults, both fixed and both tested with a hostile name through the whole page
(backtick, both quotes, ``${x}``, a closing script tag, markup):

- **The squeezer now reads a script block the way a parser does** (`_ScriptWalk`): quoted
  strings, line and block comments, template literals with their ``${...}`` expressions. A
  backtick inside a string or a comment counts for nothing; outside a script block nothing is
  lexed at all. A pattern is told from a division by the character or keyword before the
  slash, the usual heuristic — the page's own ``/[&<>"']/g`` had left a quote open on the
  first try — and the vendored files between the ``<!-- vendored:… -->`` fences are copied
  whole and not read, since Leaflet's minified source does the same and holds nothing to
  squeeze. A block left open still stops the build loudly rather than guessing.
- **Folium writes a tooltip's text raw into a template literal** — so a name with a backtick,
  a ``${`` or a closing script tag did not merely trip the squeezer, it broke the page. Every
  tooltip the map binds now goes through `_tooltip`: HTML-escaped, with the backtick and the
  dollar as character references, which the browser reads back as the characters.

`_script_json` escapes the backtick as it escapes ``<``, so the page's own JSON carries none
raw either — not needed by the new squeezer, kept because it costs nothing.

### 7.4 A sign is not a place to go to — decided, 2026-09-20

Uwe, seeing *Kind: Områdesskyddsinformation* on a pin: what is it, and why is it drawn? It
is the register's facility type *Information* — the board at a reserve's entrance saying
what is protected and why, a map board, brochures, a QR code, audio — 77 of the 129
facilities over this box (every one a protected-area board), one of Abisko's 25 (a map
board). A pin for each says nothing a planner acts on. Decided: the type is dropped from
the facilities layer as a whole; a visitor centre (*Naturum*) or an information building
is a type of its own and stays. What remains over this box: 30 car parks, 6 fireplaces, 6
wind shelters, 6 rest areas, 3 bridges, a wood store. The label table keeps every word the
register uses nationwide — 61 types, 75 subtypes, read 2026-09-20 — so nothing reaches the
page as the register spelt it, drawn or not.

## 6. Open

- **A stop on water makes two totals of one way.** Found by the phase 5 drive, 2026-09-20,
  measured in the browser by codex: a goal's way with a stop that the water grid holds as
  water crosses 33 m of it on the way in and 33 m on the way out, as a straight leg. The
  drawn line and the rows at the foot of the profile count those metres (`metresInto`,
  23,514 m); the heading does not (`composeRoute` gives a water part no height and so no
  walking length, 23,449 m). Neither is wrong on its own — the water is not walked, and the
  way is that long — but a reader sees 23.51 km in one place and 23.45 km in the other. Not
  new with this map: Abisko's code is the same, its scene's stop merely stands on land.
  **Decided, Uwe 2026-09-20, built 2026-09-21 (`7434a44`, plan phase 9):** a way carries
  both lengths, on foot and over water; the heading shows them as inline outlines
  (*23.45 km 🚶 · 0.07 km 🛶*, the water only when there is any, the walking glyph always),
  the figures page and the GPX in words. The water stays out of the walking length, as it
  always was — a lake is crossed by boat, a river on foot — and the last row at the foot
  equals the heading's two lengths to the metre. A kayak mode, where the water is the way,
  comes after the map is finished (plan §5).
- ~~The phone readings, once published.~~ Uwe, 2026-09-21: *funktioniert korrekt*.
- ~~The icon.~~ Uwe, 2026-09-21: candidate A, the one published, is the pick.

## 7. Settled

### 7.0 The mark — settled, 2026-09-21

Candidate A of the four drawn (plan phase 2): the cairn on the moss path between two spruces
of 57 % and 49 % of the square's height in `#2d5741`, a lake as a 1.8 % line, open background.
Uwe's word after seeing it installed. The three others stay in `draw.ts` as parameters.

### 7.1 The height model is a collection per 100 km square — fixed, 2026-09-20

The build's first run ended in the height step: *no squares of mhm-75_6 cover
(14.967, 59.729, 15.922, 60.176)*. Lantmäteriet's STAC lists the 1 m model as **one
collection per 100 km index square** — `mhm-75_6` holds Abisko, and this box lies across
`mhm-66_4` and `mhm-66_5` — and `markhojd.search` had asked the one collection Abisko was
read from. Measured on the API: the same catalogue also lists `dtm-cog`, 10 km sheets of a
coarser product, and `dsm-skoglig-copc`, the point cloud, neither carrying `proj:bbox`.
Fixed: the search goes to `/search?bbox=` across every collection and keeps the items whose
collection begins `mhm-`; the others are passed over, tested. Over this box 462 squares out
of the two collections; over Abisko's, 259 out of `mhm-75_6` as before. Marktäcke is one
national collection and needs nothing.

## 10. Changes

- **2026-09-20** — Phase 0: this record opened (`20c3f49`). Phase 2: the mark drawn, four
  candidates, A in the repository (`c473d24`, `de63c09`). Phase 1: the plumbing (`682234d`);
  `Park` carries form, gateway and route check, the boundary lookup dissolves the three county
  objects, the provider entry `lantmateriet-malingsbo-kloten` stands beside Lantmäteriet's,
  `drive-all` drives every page with a scene. Phase 4: the nine stations named for
  Trafikverket's board (`f2c2dcb`). Phase 3, the build, started 17:03 as the unit
  `malingsbo-kloten-build`.

- **2026-09-20 — Phase 3, built.** The successful run in
  `~/mockups/malingsbo-kloten-box/runs/phase-3.build.log` ends `exit 0`. It is a resumed
  run: every tile and pack was already there, and the graph was read back from the cache.
  Its seconds are the cost of checking those trees, not of their first build. The sheet is
  version 1, Lantmäteriet's stand of 2026-06-23 11:05: **152,055 tiles, none missing**,
  checked in **1.9 s**. The height, relief and slope steps read a **13,750 × 13,125** model;
  the vegetation and forest read 5,371 × 5,015 cells, the mire 5,371 × 5,014. The six trees:

  | tree | tiles | resumed step, s | packs | pack bytes | resumed pack step, s |
  |---|---:|---:|---:|---:|---:|
  | sheet | 152,055 | 1.9 | 1,861 | 733,723,548 | 5.946 |
  | heights | 692 | 0.0 | 13 | 61,320,991 | 0.037 |
  | relief | 9,756 | 0.1 | 134 | 108,212,017 | 0.342 |
  | slope | 9,756 | 0.1 | 134 | 12,738,445 | 0.328 |
  | vegetation | 9,756 | 0.2 | 134 | 36,088,143 | 0.335 |
  | forest | 9,756 | 0.1 | 134 | 13,445,716 | 0.380 |
  | mire | 9,756 | 0.1 | 134 | 20,871,648 | 0.350 |

  **2,544 packs, 986,400,508 bytes**, summing the log's seven rows. No tile was reported
  without ground or blank. The log records no first-copy or first-cut times, mosaic file
  size, graph or page elapsed time, or total wall time — those were read off the first run
  as it went (the reviewing session's watch, 2026-09-20): the sheet **20 minutes** off the
  FTP for 152,055 tiles and 730 MB, z17 alone 113,774 tiles in 711 s at 160 tiles/s; the
  heights, relief, slope, vegetation, forest and mire some 25 minutes together after the
  mosaic; the graph and the page about a quarter of an hour on a cold cache, most of it
  Overpass and the three county files.

  **The graph:** Leder 96 lines → 78 chains, Topografi 50 marked trails 298 → 129,
  paths 3,837 → 2,387, roads 14,418 → 5,999, OSM 5,292 → 4,186; no ferries or winter
  lines. **12,779 chains, 153,447 edges, 84,177 nodes**, 684,292 vertices, 5,291 bridged
  loose ends, 9,705 km. **107 components**, with or without ferries; the largest is
  **9,659 km**, printed as **100 %** of the network, reaching **28.5 km, 99 %** of the
  area's 28.8 km. **Kopparberg sits on it**, 1.48 m away. Heights: **2,049,236 samples**
  every 5 m, all read, **65.8–408.3 m**, gains under 5 m ignored; every chain carries a
  profile. The route check is skipped because this map names no check route.

  **The page:** the log lists roads and the register's trails, Topografi 50 marked trails,
  Topografi 50 paths and OSM paths split inside and outside the area, but prints no
  legend-row total. Its place counts are **518 transport stops** (9 rail, 516 bus,
  overlapping modes; 9 with a Trafikverket board), **99 OSM shelters and huts**, 344
  settlements, no quays, 12 campsites, **31 Topografi 50 cabins and huts** (3 named from
  the register, 9 more from OSM), **376 dwelling remains**, **126 register facilities**
  and no Topografi 50 trail points. These are the loader's counts; the log gives no
  combined pin total. **6,375 names**, none paired with a second language, 2,771 matched
  to the sheet's lettering; **6,259 labels** after 116 were thinned, 1,951 repeated along
  extended features. The water grid is 2,130 × 1,991 cells of 25 m, 9.5 % water, 79 kB;
  109 river outlines at 5,074 vertices. The graph is 6.06 MB encoded, 5.21 MB gzipped and
  base64 in a **23.3 MB page**, with a 57.9 kB worker, a 0.5 kB manifest and four icons.
  Five GPX files, 78 / 129 / 2,387 / 4,186 / 5,999 tracks. The label report names one
  value it did not know: `Vandringsled / Vandringsled`.

- **2026-09-20 — Phase 6, measured.** The sheet and all six version 1 trees under the
  main checkout's `analysis/output/` were read without writing there. Every PNG's byte
  count agrees with its `index.json`; the weights are `per_zoom` bytes / tiles, rounded
  to whole bytes, as for Abisko. Every PMTiles file agrees with the pack inventory;
  `packs.weights_from_index` gives the rounded mean bytes per pack at each level.
  `maps.py` now carries those figures in the Malingsbo-Kloten provider instead of Abisko's:

  | tree | mean bytes per tile, min–max over zooms | mean bytes per pack, by level |
  |---|---:|---|
  | sheet | 3,671–37,065 | z6 206,942; z10 1,256,316; z14 388,767 |
  | heights | 33,548–93,195 | z6 316,305; z10 5,083,724 |
  | relief | 6,628–20,248 | z8 449,768; z12 812,973 |
  | slope | 1,189–1,390 | z8 34,142; z12 95,986 |
  | vegetation | 862–13,430 | z8 186,682; z12 270,567 |
  | forest | 910–4,779 | z8 112,488; z12 100,157 |
  | mire | 820–3,603 | z8 70,510; z12 157,050 |

  The pack count was recounted from the PNGs' parent addresses under `packs.pack_levels`
  and checked against the PMTiles addresses: **1,861 + 13 + 5 × 134 = 2,544**. Both
  parametrised tests already carried that figure from phase 1; it stands. The analysis
  README now names all three maps in the build, drive and publish instructions.

- **2026-09-20, 21:50 — Phase 5 and phase 7.** The scene measured and two drives green
  (`305de6f`; 1,329 readings, four named skips); `drive-all` over three pages, one reading
  broken by three browsers racing and green alone; published with
  `just deploy --map malingsbo-kloten --tree packs` — 2,544 packs, 986.4 MB, 57 s; the page
  6.22 MB brotli; read back byte-identical. **https://atlas.cairn.zone/malingsbo-kloten.**
  Open: the phone, the icon pick, phase 8 (the Bergslagsleden), phase 9 (two lengths).

- **2026-09-20, 23:30 — Phase 8 and the evening's decisions, all three maps republished.**
  The Bergslagsleden and every other named hiking relation off OSM (`1628d65`), the
  register's information boards dropped (§7.4, `9173796`), every facility word labelled
  (`bfe1d3e`), a trail type split on a slash (`0571f8e`). All three pages rebuilt on that
  code and driven together — 1,372 / 1,364 / 1,330 readings, none broken, none moved after
  the Swedish scenes' figures were re-recorded (`151b6e0`: Abisko two chains more where a
  route begins, one marker fewer, the search finding route names; here 75 markers fewer and
  the long edge renumbered) — then published one after the other, the packs' sync finding
  nothing new, each page read back byte-identical from the edge.

- **2026-09-21, 01:00 — Phase 9, the two lengths, all three maps republished** (`7434a44`,
  `e0c20af`): the walking and the water glyph in the heading, words on the figures page and
  in the GPX, the sum equal to the last row. The first `drive-all` after it found the goal
  check reading *routed* on all three pages — the new helper had left the goal's way set —
  fixed by putting the page back; then 1,381 / 1,384 / 1,350 readings, none broken but the
  three-browser race on Lomsdal-Visten's first fetch, green alone; published one after the
  other, read back byte-identical.

## 11. How the figures here were obtained

Scratch in `~/mockups/malingsbo-kloten-box/`: `reserve.py` reads the cached register forms
and writes `reserve_3006.gpkg`; `box.py` the overhang, the box and the counts; `counts.py`
the repository's own `tile_count`, the boundaries and the stations; `leder.py` the trail
register over the box through `naturvardsregistret.Source.trails`; the Overpass queries and
their answers beside them, `final.json` the result. Measured 2026-09-20.

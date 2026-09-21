# Malingsbo-Kloten: the third map, in phases

*Drafted 2026-09-20. Status: **§1 decided by Uwe the same day, as proposed.** The built-notes of each phase
are recorded under the phase; the decisions and the measurements live on in
`malingsbo-kloten-decisions.md`.*

The third map, and the second Swedish one: the Malingsbo-Kloten protected area in Bergslagen,
with the town of Kopparberg inside the box, carrying every layer and overlay the Abisko map
has. The record of what was decided for Abisko is `abisko-decisions.md`; this file is the plan
for the third map, and once it lands its decisions and built-notes go to
`malingsbo-kloten-decisions.md`, which phase 0 opens.

## 1. Decided

*All seven as proposed, Uwe's word 2026-09-20.*

1. **The box.** Uwe's rule: the protected area's bounding box, widened by the distance from
   Kopparberg to the area's boundary, on all four sides. Measured (§3.1):
   **`(14.967, 59.729, 15.922, 60.176)`**, 52.9 × 49.3 km. Ställdalen's station lies 1.3 km
   outside the west edge; the rule puts it out, and it stays out unless Uwe says otherwise.
2. **A tree per map, not per provider — recommended.** `maps.PROVIDERS` is keyed by provider
   and carries the `extent`, the tile paths, every tree prefix and the byte tables of *one* box.
   A second map on `lantmateriet` collides on all of them (§3.4). The cheapest cut, in §6.2's
   own spirit of "the cheapest arrangement that meets all four": a provider entry of its own
   for the new map, `dataclasses.replace(PROVIDERS["lantmateriet"], …)` with its own extent,
   tile root `tiles/lantmateriet-malingsbo-kloten/topowebb/1/`, tree prefixes
   `dem/lantmateriet-malingsbo-kloten/1/` and so on, and a `BaseMap` member for it. Nothing
   Abisko has moves, no bucket object is renamed, a version bump of one map never recuts the
   other, and `--delete-version` and the packs' sheet table stay per map. The alternative —
   one shared Swedish tree at `lantmateriet/…` with the box per map — needs the extent, the
   prefixes and the weights moved off `Provider` onto `Tree`, couples the two maps' versions,
   and leaves `lantmateriet_tiles.py`'s `index.json` recording only the last box copied.
3. **The gateway is Kopparberg.** The graph's report names the place the map is reached from;
   Abisko's is *Abisko*, and it sits on `COUNTRIES["SE"]` today, per country rather than per
   map, together with `check_route="BD 21"`. Both move onto `Park`. Kopparberg is in the
   place-name register as a tätort in Ljusnarsberg (`BEBTÄTTX`, län 18), and its station is
   inside the box. There is no state trail here to check a route against, so `check_route`
   is `None` for this map.
4. **The area is a *Naturvårdsområde*, not a naturreservat**, and it is three objects, one per
   county (§3.2). `Park.kind` says `naturvårdsområde`; the boundary is the union of the three.
   The page's wording wherever it says *park* is checked in phase 1 and follows `kind`.
5. **The icon.** The build refuses a map without a drawing of its own (§6.2 of the Abisko
   record), and the test asserts the art differs from the first map's. Proposed motif: the same
   cairn on the same moss path, standing between two spruce silhouettes with a lake's flat
   line behind — Bergslagen's forest and water where Abisko has Lapporten's gate. Three or
   four candidates on the mockup host, Uwe picks (phase 2).
6. **No Naturkartan catalogue at first.** The catalogue links the register's *state* trails by
   their BD number, and the box holds none (`Statliga_Leder`: 0 rows). The register's other
   trails are there — 98 rows, 60 km, *Vandringsleder i Klackberg*, *Bruksleden genom
   Jättåsarna*, nature trails — and draw as the *Leder* layer without a link.
   `Park.naturkartan=None`. Linking Bergslagsleden's stages or the reserve's own trails to their
   Naturkartan pages by name is a feature of its own, listed in §5.
7. **Stem and names.** `malingsbo-kloten` everywhere the stem goes: `--park`, the page
   `malingsbo-kloten.html` at `/malingsbo-kloten`, companions `malingsbo-kloten-sw.js`,
   `malingsbo-kloten.webmanifest`, database `trails-malingsbo-kloten`, app name
   *Malingsbo-Kloten Atlas*. The index Worker lists it on its own and titles it
   *Malingsbo-Kloten* (its `title()` capitalises each hyphenated part).

## 2. How to work through them

The rules of `kartverket-tree-phases.md` §2 apply unchanged: one phase at a time per worktree,
a review over each, `command make hooks-run` green, anything touching the browser driven,
stop at the end of a phase. A phase an agent runs is one `codex exec -C <worktree>` as a
transient unit (`systemd-run --user … /usr/bin/mise exec -- …`), the worktree's branch rebased
onto `main` and fast-forwarded at review, so the history stays linear. `maps.py` is read by
region and never whole. Review, hooks, the drive and the landing are the reviewing session's.

**Order and parallelism, in one line.**
0 → { 1 ∥ 2 ∥ 4 } → 3 → { 5 ∥ 6 } → 7 → 8 → 9.

- Phase 1 (plumbing), 2 (icon) and 4 (research) touch disjoint files and run at once.
- Phase 3 (the builds) needs phase 1 landed and phase 2's first candidate on disk; it is a
  `make` run on this box, hours long, in a transient unit, and no agent.
- Phases 5 and 6 need the built page and trees; they touch disjoint files
  (`drive_map.py` against `maps.py`'s weight tables, tests and docs) and run at once.
- Phase 7 publishes, after 5 and 6 and a green `drive-all`.

## 3. What was measured, and with what

Scratch in `~/mockups/malingsbo-kloten-box/` (`reserve.py`, `box.py`, `counts.py`, `leder.py`,
the Overpass queries and their answers, `final.json`). Nothing in the checkout was touched.

### 3.1 The box

The three objects named Malingsbo-Kloten, read from the cached nightly file
`.cache/naturvardsregistret/NVO.zip` (SWEREF 99 TM):

| NVRID | Län | Kommun | ha |
|---|---|---|---|
| 2000023 | Örebro | Lindesberg, Ljusnarsberg | 14,157 |
| 2002595 | Västmanland | Fagersta, Skinnskatteberg | 8,413 |
| 2002711 | Dalarna | Smedjebacken | 26,464 |

Union 49,034 ha; bounding box `15.1511, 59.8231, 15.7349, 60.0836` (32.4 × 28.8 km).

Kopparberg's built-up area, OSM via Overpass on 2026-09-20: the `place=town` node plus the
residential, industrial, retail and commercial land use within 2.5 km, 54 ha, bounding box
`14.9683, 59.8735, 15.0099, 59.885`; of 440 buildings within 2.5 km none lies west of that
land use's west edge (the nearest is 25 m inside it), so that edge is the town's far edge.

| quantity | value |
|---|---|
| town's overhang past the area's box, west | **10,247 m** (south, east, north: inside) |
| town's nearest edge to the area's polygon | 9,809 m |
| town's far edge to the area's polygon | 12,135 m |
| **d**, the rule's margin | **10,247 m** |
| final box, EPSG:3006 | `498223, 6621686, 551135, 6670977` |
| final box, WGS84, rounded outward | **`(14.967, 59.729, 15.922, 60.176)`** |
| width × height | 52.9 × 49.3 km (Abisko: 39 × 36) |

Tile counts with `trails.utils.tiles.tile_count`, against Abisko's current box:

| box | z8–13 (heights) | z8–15 (overlays) | z8–17 (sheet) |
|---|---|---|---|
| Malingsbo-Kloten | 692 | **9,756** | **152,055** |
| Abisko `(18.15, 68.139, 19.10, 68.46)` | 610 | 9,330 | 146,995 |

About five per cent more tiles than Abisko at every level, and more ground per tile at 60° N.
At Abisko's measured pace (118,967 tiles in 916 s off the FTP, 25–60 objects/s into R2), the
sheet copy is some twenty minutes and its upload about an hour and a half — though packs are
what is published since §6.12, and those are far fewer objects.

Administrative: the box touches **Örebro (T), Dalarna (W) and Västmanland (U)**, eight county
and four municipal boundary segments of `administrativindelning_sverige.gpkg` inside it.
Railway stations inside: Kopparberg, Grängesberg, Ludvika, Smedjebacken, Skinnskatteberg,
Fagersta C, and the halts Fagersta Norra, Söderbärke, Vad. Outside: Ställdalen (1.3 km west),
Skäret, Storå.

### 3.2 The sources, and what the new box needs of each

Nothing has to be ordered. Topografi 50 is a whole-country subscription on disk
(`.cache/topografi50/2026-09-08/gpkg/*_sverige.gpkg`, 11 GB); the height model, the place
names and the wetlands are account-level *Behörighet* orders already placed and read by box;
NMD 2018 is converted nationwide (`.cache/vegetation/nmd2018/`, 4.3 GB); SLU's moisture
mosaic is on disk whole (7.9 GB); the register's forms and trails, the GTFS feed and the stop
register are national files. The one Swedish thing that is per area by hand — the Naturkartan
catalogue — the box does not need (§1.6).

| source | what the new box costs |
|---|---|
| Lantmäteriet's sheet (FTP GeoPackage) | a fresh copy of 152,055 tiles into the map's own root |
| Markhöjd 1 m COGs | a fresh mosaic by range request, about twice Abisko's 175–215 MB |
| Marktäcke wetlands | STAC finds the municipalities itself; four to six files of some hundred MB each |
| Kulturmiljöregistret | **three county files** — `örebro` 71 MB, `dalarna` 105 MB, `västmanland` 71 MB, all answering 200 |
| OSM, Trafiklab's placed stops, the graph | per-box objects, fetched and cached as for Abisko |
| Topografi 50's `*_fjall` layers | empty here; `network/sweden.py` reads them into empty frames |
| Sámi name pairing in Ortnamn | inert here |

Credentials: Geotorget and Skogsstyrelsen come through `sops exec-env` from
`home/trails-map/secrets.sops.env`, which this box decrypts; Trafiklab's two keys come from
`trails/.env`, which `just abisko` does not supply and `make` reads on its own.

### 3.3 The gateway and the trails

`ortnamn_se.gpkg` holds *Kopparberg* as `BEBTÄTTX` at 500306 E, 6637425 N (Ljusnarsberg,
län 18), inside the box; a second *Kopparberg* row in the box is a `TRAKTTX`, and the
settlement-type match takes the first. The trail register over the box: 98 rows, 60.1 km,
85 *Vandringsled*, 12 *Naturstig*; `Statliga_Leder` 0.

### 3.4 Where the code knows a map, and what collides

The inventory of 2026-09-20, by file. Every JavaScript mention of either map is prose; every
name reaches the page by injection from `maps.py`.

- `maps.py:546-716` — `Provider.extent`, `tiles`, the six tree prefixes and the two byte
  tables are per provider; `PROVIDERS["lantmateriet"]` binds `_ABISKO.box`. **The collision.**
  `tile_tree_version` (2007-2033) mutates the provider globally. `Companions` (75-158) is per
  stem and just works. `ICON_DIR` (1136-1176) wants `atlas-malingsbo-kloten-{32,180,192,512}.png`.
  `BaseMap` (1949-2005) needs a member and a `_BASE_LAYERS` row.
- `trees.py:214-256` — `TREES` entry; `provider` doubles as the bucket directory (100).
- `lomsdal_visten.py:157-244` — `Park` and `PARKS`; `load_swedish_boundary` (2195-2207) calls
  `find_one(park.name)` with the *Nationalpark* default and refuses several matches;
  `county` is one string (190, used 3710) and three are needed; `TRAFIKVERKET_BOARD_NAMES`
  (875-882) is Abisko's six stations by hand, others fall back to the Resrobot link alone.
- `route_graph.py:82-110` — `gateway` and `check_route` on the country row; `graph_sweden`
  (604-616) repeats the `find_one` call.
- `lantmateriet_tiles.py:24,30` — `ABISKO` as the `--bounds` default and one `DEFAULT_ROOT`;
  `kartverket_tiles.py:40-43` dispatches on `provider == "lantmateriet"`;
  `pack_tiles.py:38` maps provider → sheet in a two-row table.
- `drive_map.py:243-571` — `SCENES`; 10781 finds the provider by tile prefix, so the extent
  follows the provider entry. A `Scene` is some forty measured figures and a dozen positions.
- `Makefile` — `abisko:` chain (270-278), `drive-both` hard-codes two pages (315-327), the
  help text.
- `home/trails-map` — `justfile:128-149` recipe `abisko` calls `make abisko` under sops;
  `worker/index.js` lists every `*.html` and needs nothing; `main.tf:96-102`'s cache rule
  names no `/mire/` prefix and needs none: the mire came after §6.12 and has only ever been
  published as packs, so no per-tile mire object exists in the bucket.
- Tests — `test_trees.py:12-44` pairwise assertions and `86-92` exact tile counts per map;
  `test_maps.py:2095` the marks that must exist on disk, `2805` the provider/park pairs, six
  `parametrize("provider", …)` suites at 10170-10886, and `10785/10798` measured pack counts.
- `analysis/README.md`, `abisko-decisions.md` — prose naming two maps.

## 4. The phases

### Phase 0 — Decide and open the record

Uwe's word on §1. Then, by the reviewing session and not an agent: `malingsbo-kloten-decisions.md`
opened with the area (§3.1), the decisions of §1 as decided, the source table (§3.2) and the
measurements' provenance; a *Changes* section left empty for the phases' built-notes.
Touches nothing but that file.

**Built 2026-09-20.** Uwe's word on §1, all seven as proposed; the record opened as
`malingsbo-kloten-decisions.md` (`20c3f49`). The `/mire/` cache-rule note that stood here was
wrong and is gone: the mire has only ever been published as packs.

### Phase 1 — The plumbing

*Agent, one worktree. Files: `trees.py`, `maps.py` (by region), `lomsdal_visten.py`,
`route_graph.py`, `naturvardsregistret.py`, `lantmateriet_tiles.py`, `kartverket_tiles.py`,
`pack_tiles.py`, `Makefile`, `test_trees.py`, `test_maps.py`, `test_kartverket_wms.py`.*

1. `TREES["malingsbo-kloten"]`: `provider="lantmateriet-malingsbo-kloten"`, the box of §3.1,
   `model="markhojd"`, `structure="nmd"`, `mire="marktacke-slu"`, every version 1.
2. `maps.py`: `_MALINGSBO_KLOTEN`, the provider entry by `dataclasses.replace` of Lantmäteriet's
   with its own extent, tile root and prefixes, the byte tables **borrowed from Abisko's** with
   a comment saying so until phase 6 measures them; `BaseMap.LANTMATERIET_TOPO_MALINGSBO_KLOTEN`
   (or a name the agent argues better) and its `_BASE_LAYERS` row; `tile_tree_version` keyed on
   the new provider works unchanged.
3. `Park`: a `form` field (the register's form: *Nationalpark* for Abisko,
   *Naturvårdsområde* here) threaded into `load_swedish_boundary` and `graph_sweden`;
   `find_one` gains a path that dissolves several rows of one name and form into one boundary;
   `county` becomes a tuple, the three files concatenated and de-duplicated by `uuid`;
   `gateway` and `check_route` move from `COUNTRIES["SE"]` onto `Park` (Abisko keeps
   *Abisko* and *BD 21*; Lomsdal-Visten's stay where Norway's row had them, moved the same
   way); the new `PARKS` entry per §1.7 with `naturkartan=None`; the page's wording checked
   for *park* / *national park* where `kind` should speak; Naturkartan's `SourceMetadata`
   provider text no longer names Norrbotten when the county is another.
4. `lantmateriet_tiles.py` takes `--park` and reads box and root off the tree; the dispatch
   in `kartverket_tiles.py` sends any `lantmateriet*` provider there; `pack_tiles.py`'s sheet
   table gains the row.
5. `Makefile`: `malingsbo-kloten:` chain target on `abisko:`'s pattern; `drive-both` becomes
   `drive-all` over every page in `analysis/output/*.html` whose stem is a scene, `drive-both`
   kept as an alias; help text and `.PHONY`.
6. Tests: the pairwise assertions in `test_trees.py` become n-way, tile counts gain
   `"malingsbo-kloten": 9_756` (the agent recounts), `test_maps.py:2095` and `2805` gain the
   third entry, the six parametrised suites the third provider, the pack count measured.
7. `command make hooks-run` green; `command make map ARGS="--park malingsbo-kloten"` is
   expected to run to the boundary and the sources and fail only where trees are absent —
   the agent reports where it stops, and does not build trees.

Stops if the agent finds the provider split needs more than `dataclasses.replace` — that is a
question for §1.2, not a thing to patch round.

**Built 2026-09-20** (`682234d`, one codex run and one correction; the run stopped once, rightly,
on the icon assertion that phase 2 owned). `Park` gained `form`, `gateway`, `check_route`, and
`county` became a tuple; `find_one` dissolves several objects of one name and form (`dissolve=True`),
and the two Swedish lookups are exact — measured against the cache: *Abisko* one object,
*Malingsbo-Kloten* three, 49,034 ha. `kind_label` gives the page's word for the area, so
Abisko's legend rows now read *national park* where they read *park*. The provider entry
`lantmateriet-malingsbo-kloten` is `dataclasses.replace` of Lantmäteriet's, weights borrowed
from Abisko until phase 6. `lantmateriet_tiles.py` takes `--park`; `drive-all` drives every
page with a scene, `drive-both` is its alias. Recounted: 692 / 9,756 / 152,055 tiles, 2,544
packs. A landing commit (`f2c2dcb`) added phase 4's nine stations and restored the reasoning
the drive recipe's comment had carried.

### Phase 2 — The icon

*Agent or the reviewing session. Files: `docs/draw.ts`, `libs/src/trails/visualization/icons/`,
`~/mockups/malingsbo-kloten-icon/`.*

Three or four candidates of the §1.5 motif at 512 and 60 px, drawn by `draw.ts` (it needs the
renderer from `weather-cards/scripts/lib/renderer`), served from the mockup host by the recipe
in the box's CLAUDE.md, Uwe picks. The chosen set lands as `atlas-malingsbo-kloten-{32,180,192,512}.png`,
the 32 scaled from the 512 as the Abisko set was. The first candidate is copied in before phase
3 starts so the build and `test_maps.py:2095` have files; the pick replaces PNGs only.

**Built 2026-09-20** (`c473d24`, `de63c09`). Four candidates A–D drawn by `draw.ts
--candidates`, varying the spruces' height and tone, the lake as a line or a band, and a
distant shore; on the mockup host at `forge-mockups.uweeisele.dev/malingsbo-kloten-icon/out/`.
Candidate A is in the repository; the cairn's clearance inside the maskable circle is 11.6 px
at 512. **Open: Uwe's pick.**

### Phase 3 — The builds

*This box, a transient unit, no agent. Needs phase 1 landed and a candidate icon on disk.*

A `malingsbo-kloten:` recipe in `home/trails-map/justfile` on `abisko`'s pattern (six lines,
the reviewing session), then:

```bash
systemd-run --user --unit=malingsbo-kloten-build \
  --working-directory=/home/eiseleu/repositories/home/trails-map \
  /usr/bin/mise exec -- just malingsbo-kloten
```

which runs `make malingsbo-kloten` under sops: the sheet copy (152,055 tiles, ~20 min), the
height mosaic and the 692 height tiles, relief and slope off the same mosaic, NMD's window,
the wetlands' municipal files and the moisture window into the mire, the packs off every tree,
the graph with its report (the register, Topografi 50, OSM, three KMR files, Trafiklab's stops
placed), and the page. Every step is resumable, so a step that dies is rerun, not restarted.
What the report says — chains, components, the gateway on the largest one, heights within the
mosaic — goes into the record. `/tmp` is a 7.7 GB tmpfs; the builds write under
`analysis/output/` and `.cache/`, not there.

**Built 2026-09-20, in five runs of the unit `malingsbo-kloten-build`**, each restart finding
the earlier steps in the cache. The sheet: 152,055 tiles, 730 MB, 20 minutes off the FTP
(z17 alone 113,774 tiles at 160 tiles/s). The heights: 462 squares of the 1 m model out of
two collections, a 13,750 × 13,125 mosaic at 4 m, 692 tiles; relief, slope, vegetation and
forest (9,756 each, from 5,371 × 5,015 NMD cells) and mire cut after it; the packs off every
tree. The graph: **12,779 chains over 153,447 edges on 84,177 nodes**, 107 components, the
largest 9,659 km and 100 % of the network, reaching 99 % of the area's 28.8 km north to
south, **Kopparberg 1.5 m from it**. The page: 518 stops (9 with a Trafikverket board), 376
remains of 7 dwelling types out of three county files, 2,771 names lettered, a water grid of
2,130 × 1,991 cells (9.5 % water, 79 kB), 109 rivers; the graph 6.06 MB encoded, 5.21 MB
gzipped in a **23.3 MB page** — seven times Abisko's, which is the network: Bergslagen's
forest roads and tracks against the fell's few paths. Four stops on the way, each a fault the
plan had not seen and each fixed on `main` before the next run: the height model is one STAC
collection per 100 km square (`1ad1ca1`, record §7.1); the counties' remains de-duplicated by
a column the reader does not hand out (`0f3ed01`); and an OSM path named ``EkMalm`sStig``,
which stopped the page twice and ended in the squeezer reading a script block as a parser does
and every tooltip escaped (`427e0fb`, `726b552`, record §7.3). One label the tables did not
know: *Vandringsled*, the register's trail type, which Abisko's fell never carried.

### Phase 4 — The stations, by hand

*Parallel with 1–3; an opencode research run or the reviewing session in Firefox.
File: `lomsdal_visten.py` (the one dict) — or, if phase 1 is still open, a note for it.*

`TRAFIKVERKET_BOARD_NAMES` gains the box's rail stops by Samtrafiken id with the name
Trafikverket's board knows them under: Kopparberg, Grängesberg, Ludvika, Smedjebacken,
Skinnskatteberg, Fagersta C, Fagersta Norra, Söderbärke, Vad — each opened and seen, as
Abisko's six were (§9.34). Without this the stops still draw and link Resrobot; with it the
train board links too.

**Built 2026-09-20** (`f2c2dcb`). Measured how the board resolves a name: the page POSTs a
`TrainStation` query to Trafikverket's API and matches `?Station=` against
`AdvertisedLocationName`, exact and case-sensitive; a miss draws neither heading nor error. The
box's nine rail stops — one stop id each, train and bus alike, no twins on one coordinate —
were each opened in Playwright Firefox and seen to draw the heading; *Fagersta C* is the board's
name, the register's *Fagersta Central* draws nothing. Fagersta Norra's feed point is 1 km off
the register's, which is the right one. Hedemora, Storå, Ställdalen and Ängelsberg, outside the
box, also draw, and are not in the dict. Scratch in `~/mockups/malingsbo-kloten-box/stations/`.

### Phase 5 — The scene, and the drive

*Agent, one worktree, after phase 3. File: `drive_map.py`.*

`SCENES["malingsbo-kloten"]` on Abisko's model: a long chain, positions on and off the
network, open water, a walk, a kept area of some 5 × 9 km, a place to search for, a typed
coordinate, the overlay paths, `borrowed_name` for a Swedish map, and the figures the build
reports — read off the built page and the build's own output, never guessed. Then
`command make drive ARGS="--page analysis/output/malingsbo-kloten.html"` to a file, read
whole; every reading green or its skip named; then `drive-all`, three pages, green.

**Built 2026-09-20** (`305de6f`, one codex run and five resumptions, each a precise stop).
The scene: road 233 as the long chain (45.885 km), positions at Kloten, a kept area of
5.01 × 8.96 km, Dammtjärnsbäcken as the river goal (357 m straight, 66 m of river, 2.343 km
staying on paths), edge 65792 for the long-edge readings, `way_over_flight=1.2`. Three
findings on the way, two of them the suite's and one the page's: the scale-bar check had
65.5° N hard-coded and now derives the bar from the page's own rule at the scene's latitude;
the profile-scale check rounded pixel bands before dividing and read 13 for a true 9.92 — the
fractional bands are kept now, and the three scenes read 9.93 / 10.04 / 9.92; and a stop on
water gave the way two totals (record §6, decided as phase 9). The pack-weight readings
disagreed until the page was rebuilt on phase 6's measured tables. **Two consecutive full
drives green: 1,329 readings, none broken, none moved, four named skips** (no tap pair
beside a path, no leg not worth routing, no sound, no named Topografi 50 trail to borrow).

### Phase 6 — The weights, the counts, the record

*Agent, one worktree, after phase 3, parallel with 5. Files: `maps.py` (weight tables only),
`test_maps.py` (pack counts), `malingsbo-kloten-decisions.md`, `analysis/README.md`,
`home/trails-map/README.md`.*

The byte-per-zoom tables of the six trees measured off `analysis/output/` as Abisko's were
and written in place of the borrowed ones; the pack count per provider in the test; the build's
figures and timings into the record's *Changes*; the READMEs' two-map prose made three-map.

**Built 2026-09-20** (`0d71d87`, one codex run, no correction). The seven byte tables measured
off the version 1 trees — every PNG against its `index.json`, every PMTiles file against the
pack inventory — replace the borrowed ones; the pack count 2,544 (1,861 sheet, 13 heights,
5 × 134 overlays) recounted and standing; the record's §10 carries the build's figures from
the log; the analysis README names three maps. The build log codex read was the resumed
run's, so its "no first-copy times" is right about the log and wrong about the build — the
cold costs are in phase 3's note above.

### Phase 7 — Publish

*The reviewing session, after 5 and 6.* `command make map ARGS="--park malingsbo-kloten"`,
then from `home/trails-map`: `just deploy --map malingsbo-kloten --tree packs` (and `--tree
dem` if the page reads heights per tile rather than from packs — as Abisko's last publish did
it). Read back from the edge: the page, a pack, a height tile, byte-identical. The index at
`atlas.cairn.zone` lists the third map on its own. Then Uwe's phone: install, keep an area,
walk the offline switch — the readings that are his to take.

**Published 2026-09-20, 21:50.** `drive-all` over the three pages first: Malingsbo-Kloten
1,326 readings and four named skips, Abisko 1,366, Lomsdal-Visten 1,368 with one broken —
*the first visit downloads the map once: 2* — which passed alone (`--only
the_map_opens_with_the_network_off`, 126 readings green): three browsers at once race the
worker's first fetch, a contention the suite's counted readings are not yet proof against.
Then `just deploy --map malingsbo-kloten --tree packs`: **2,544 of 14,591 packs uploaded,
986.4 MB in 57 s**, the page 23.3 → 6.22 MB at brotli 11, the worker, the manifest, the four
icons, the edge purged. Read back: the page byte-identical to the file, a height pack
byte-identical, manifest and worker 200, and the index at `atlas.cairn.zone` lists
`/malingsbo-kloten` beside the two. **https://atlas.cairn.zone/malingsbo-kloten**. Uwe's phone
readings are the open half: install, keep an area, the offline switch.

### Phase 8 — Named routes off OSM's relations: the Bergslagsleden

*Agent, one worktree, after phase 7. Uwe's word 2026-09-20, on the measurement below.*

The Bergslagsleden runs through the area from Kloten and stands in neither register the map
reads names from: Naturvårdsverket's Leder file has no row of that name in the box, Topografi
50 carries it in no name column. Both draw the way as a marked trail without knowing what it
is. OSM knows: four `route=hiking` relations in the box — *Bergslagsleden Etapp 1* Kloten →
Gillersklack, *Etapp 2* → Stjärnfors, *Etapp 3* → Nyberget, *Etapp 4* → Uskavi — each with
`ref`, `from`, `to` and a `website` on the stage's page at bergslagsleden.se (Region Örebro
län's own site), plus a connector relation at the county border. The Swedish loader reads
ways only, so no chain knows it is a member (measured 2026-09-20, Overpass and the cached
paths object). Naturkartan has a Bergslagsleden guide at `naturkartan.se/sv/bergslagsleden`;
its stage pages are linked by script only and are researched by hand as Abisko's were.

1. `io/sources/overpass.py` gains a reader for the box's hiking relations with their
   members' way ids and tags (`name`, `ref`, `from`, `to`, `website`, `operator`), cached
   like the paths are.
2. `network/sweden.py`: a way that is a member carries the relation's name, its `ref` and
   `from`–`to` on the OSM chains, as a route identity the way Turrutebasen's route name is
   one for Norway; a chain of several relations lists them joined by the identity separator.
   Measured before and after on the graph's report: **a chain is one identity, so a chain
   ends where a named route begins or ends** — 12,779 → 12,804 chains, 153,447 → 153,481
   edges, 107 components unchanged (codex, 2026-09-20); that is the rule's own answer, as
   Turrutebasen's route name ends a chain in Norway, and it is accepted. What must hold is
   the components, and that no chain breaks *inside* a route. The box holds 57 named
   hiking relations, not the Bergslagsleden's four alone: the reserve's marked loops among
   them, 11 with a website, naming 191 chains. `overpass.osm.ch` is a regional mirror and
   answers nothing for Sweden; `maps.mail.ru`'s instance answered when both listed mirrors
   were busy and is the third in `MIRRORS`.
3. The popup on such a chain links the relation's own `website` where it has one, headed as
   the source names it, and the Naturkartan pages from a catalogue keyed by the relation's
   name — `analysis/routes/malingsbo-kloten-naturkartan.toml`, the guide and the stage pages
   found — through `naturkartan_links` widened to take a name as well as a number. The search
   finds the chain under *Bergslagsleden*.
4. No layer of its own: the line is drawn already, as Topografi 50's marked trail and OSM's
   path; what was missing is the name and the link. The legend does not change.
5. The scene and the drive: `search_for` may move to *Bergslagsleden*; a reading that the
   popup carries the links. `drive-all` green, the page rebuilt and published as phase 7 did.

**Not for Norway.** Measured 2026-09-20: OSM has **no** `route=hiking` relation over the
Lomsdal-Visten box at all, and the Norwegian map names its routes off Turrutebasen's own
route name, which reaches FKB through the route-name join, with 35 UT.no pages in its
catalogue. There is nothing there for a relation reader to add.

**Built 2026-09-20** (one codex run, two precise stops: the Swiss mirror's empty answer, and
the chains that a route identity ends). The relation reader with the third mirror; the
membership on the chains as a route identity — 57 named relations name 191 chains, 11 with
a website on 72 of them, no chain broken inside a stage, the Bergslagsleden's four stages
on 2, 5, 5 and 2 chains; the popup's *Route page* from the relation's own `website` and
the Naturkartan pages from the catalogue by name, the guide and all four stage pages found
through the site's own search and answering 200 at 22:11 UTC; the search finding the chain
under *Bergslagsleden* (matches 9 → 29). The scene's moved figures re-recorded (+25 paths
and chains), road 233 unchanged, 48 readings green on the rebuilt page. Landed with the
facility labels and the information-board filter of the same evening (§7.4 of the record),
and republished with them.

**Republished 2026-09-20, 23:30, all three maps** on the code of phase 8, the facility labels
and the information-board filter: rebuilt, driven together (none broken, none moved once the
Swedish scenes' figures were re-recorded, `151b6e0`), published one after the other, read
back byte-identical. The `just` recipes need `sops`, which is trails-map's toolchain and not
trails': a unit that runs them starts with trails-map as its working directory.

### Phase 9 — A way's two lengths: on foot, and over water

*Agent, one worktree, after phase 8. Uwe's word 2026-09-20, on the measurement in the
record's §6.*

A lake is not walked, so its metres were never in the walking total — deliberately, since
what crosses it is a boat. The fault is that the page shows one figure with the water and
another without, in two places, without saying so. Decided: a way carries both lengths.

1. `composeRoute` keeps its rule — a water part has no height and no walking length — and
   the way records the water's length beside it, summed from the same parts; `goalState`
   hands both out, and `metresInto` counts along the whole way, as the drawn line is.
2. **The heading shows glyphs, the figures page shows words.** The heading is one line of
   forty characters at 390 px (§9.37) and holds no fourth word-pair. Two Font Awesome
   outlines join the four the page already carries inline — *person-walking* and *water* —
   and the first figure reads *23.45 km 🚶 · 0.07 km 🛶*, the water only when it is more
   than nought, so a way without water reads as it does today. The figures page, the GPX
   description and the SVG's `<desc>` say *on foot* and *over water* in words. Rivers are
   crossed on foot and stay in the walking length.
3. The drive: a reading that the goal's heading and the last row at the foot agree with the
   water in, on a way that crosses water — the stop on water of phase 5's first try, on this
   map, is that reading; and a reading that a way without water reads as before. All three
   pages green.

**Built 2026-09-21** (`7434a44`, one codex run, two precise stops on my own prompt: the dry
heading cannot both carry the glyph and stay byte-identical — the glyph always, decided; and
the profile's SVG has no `<desc>`, only the GPX has — nothing added). The heading's first
figure is `23.45 km 🚶`, and `· 0.07 km 🛶` follows only where the way crosses water; the
outlines are Font Awesome Free 6.2.0's *person-walking* (new) and *water* (already inline),
CC BY 4.0, 2,659 bytes with the licence, each figure carrying its words as an `aria-label`.
The figures page and the GPX description say *on foot* and *over water* in words and are
byte-identical on a dry way. Measured on the stop in the lake: 12,637.898 + 32.922 and
10,810.863 + 32.922 m, the unrounded sum 23,514.604 m equal to the last row to the metre.
Two readings, `a_way_counts_foot_and_water` and `a_dry_way_keeps_its_words`, 22 readings on
each of the three pages. All three rebuilt, driven together (once the helper put the goal's
way back, `e0c20af`) and republished 2026-09-21 01:00, read back byte-identical.

## 5. Not in this plan

- **A kayak mode**, where water is the way and land the portage: the costs reversed, the
  water grid a surface to cross rather than a bar, a profile flat at the lake's level (the
  height model has it: a lake is a plane with a value, not a hole), and the two sums *over
  water* and *portage on foot* by the mechanism of phase 9. Uwe, 2026-09-20: after the map
  is finished. A measurement over this map's lake chains first, and a section in the
  decisions before anyone builds; whether it lives here or in `atlas` is part of that.

- Linking the reserve's own trails (*Vandringsleder i Klackberg* and the like) to Naturkartan
  pages: the register names them, but no page for them is known; the Bergslagsleden is phase 8.
- Ställdalen, unless the box is widened by Uwe's word.
- Moving `extent` and the weights off `Provider` onto `Tree` for all three maps — the
  alternative in §1.2, worth doing only if a fourth Swedish map comes.
- Sweden's KMR terms and Statskog's feed — open on the Abisko record already.

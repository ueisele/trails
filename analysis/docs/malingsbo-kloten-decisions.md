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

## 6. Open

- The phone readings, once published: install, keep an area, the offline switch.
- The icon: Uwe's pick among candidates A–D (plan phase 2); A stands until then.

## 7. Settled

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

## 11. How the figures here were obtained

Scratch in `~/mockups/malingsbo-kloten-box/`: `reserve.py` reads the cached register forms
and writes `reserve_3006.gpkg`; `box.py` the overhang, the box and the counts; `counts.py`
the repository's own `tile_count`, the boundaries and the stations; `leder.py` the trail
register over the box through `naturvardsregistret.Source.trails`; the Overpass queries and
their answers beside them, `final.json` the result. Measured 2026-09-20.

# The kayak mode: what has been decided, what is open, and what changed

*Opened 2026-09-21. The plan that produced it is `kayak-mode-phases.md`; once a phase lands,
its built-note goes under §5 here, and this file is the record — the plan is not.*

## 1. The decision in one paragraph

A third way of planning beside walking and staying on paths, where the water is the way and
the land is the portage. Asked for by Uwe on 2026-09-20, taken up on 2026-09-21 after the
Malingsbo-Kloten map was called done, and decided the same day as the plan's §1 proposed: one
price rule (shore 1, open water k, land P times the walking price, a path P alone), the
narrow rivers as class-2 lines downstream only and cut at dams, k and P measured by a sweep,
the canoe trails researched before anything named is added; in `trails`, with the water
network in `libs`; the profile over water read off the height tiles, where a lake is a plane;
on all three maps.

## 2. Decided

The plan's §1, in full. What was Uwe's rule is quoted there; what was a proposal beside it
(the portage chords between neighbouring pieces of water, the tiles as the source of a lake's
level, all three maps) is settled with it and is not reopened without his word.

## 3. What was measured

The plan's §3: the water of the Malingsbo-Kloten box (1,332 lakes and 108 river surfaces,
31,987 ha, 2,701 km of shoreline), the lines the page lacks (6,709 `Vattendrag`, 118 km of
them class 2; 97 dam points, 11 lock gates, 2,121 flow arrows), how the water hangs together
(1,190 bodies by touch, 433 systems with the lines, the largest 754 surfaces over the whole
box), and OSM's silence on canoe trails (0 relations, 0 portages, 6 slipways). Measured
2026-09-21, scratch in `~/mockups/kayak-mode/`.

### 3.5 Where the canoe trails are — phase R, 2026-09-21

**Nobody publishes the canoe trails of this box as lines.** Searched: Naturkartan (its
search page answers 403 to a script; its entries found by web search), the three county
boards' pages for Malingsbo-Kloten (Dalarna, Västmanland, Örebro), Sveaskog's ecopark page
and its plan, Ljusnarsberg's and Lindesberg's visitor pages, Nordic Discovery (the canoe
centre at Kloten), opencanoe.se, and Naturvårdsverket's own register — the one open source
that has a canoe trail type at all.

| who | what they publish | lines | terms |
|---|---|---|---|
| Naturvårdsverket, *Leder* (`Leder_shp.zip`) | trail type `Kanotled` exists nationally; **0 in the box** (98 trails: 85 `Vandringsled`, 12 `Naturstig`, 1 both) | — | open data |
| Naturvårdsverket, *Anordningar* | 129 facilities in the box: 6 `Vindskydd`, 6 `Eldstad`, 6 `Rastplats`, 3 `Bro`, 30 car parks, 77 information boards, 1 wood store; named for their lakes (*Vindskydd Sågsjön*, *Rastplats med vindskydd vid Håvtjärnen*), none typed as a landing or a canoe rest place (`Kajakramp`, `Brygga` exist in the table, none here) | points, on the map already | open data |
| Nordic Discovery, Kloten | *Norra kanotleden* 50 km, *Södra kanotleden* 20 km, 70 km together, "plus 30 km in Malingsbo"; rest places with shelters and fire pits along them; an overview map as a raster PDF (`media.nordicdiscovery.se/2019/10/översiktskarta-2019-10-12.pdf`, 6 MB, one page) and a 1:50,000 waterproof map for rent | none; the PDF is a drawing, © Mikael Nilsson / Nordic Discovery | all rights reserved |
| Naturkartan | one entry, *Malingsbosjön paddling* (Smedjebacken kommun): a place with a kayak jetty, a rest place and a bathing place; no route, no GPX | — | Naturkartan's terms |
| Länsstyrelsen Dalarna / Västmanland / Örebro | "you can hike, paddle and fish"; the reservatskartan web map per county; nothing on the canoe trails | — | — |
| Sveaskog, Ekopark Malingsbo | "canoe waters"; the ecopark plan is a scanned PDF | — | — |
| opencanoe.se (Curt Svensson, 2008) | Hedströmmen, Gåsmossen to Skinnskatteberg, ~27 km, three portages, easy rapids, an embedded Google map | none | © 2008 |
| OSM | plan §3.3: nothing | — | ODbL |

**What follows.** There is no phase 6: no source offers a line under terms the map could
carry, and the register's canoe trail type, which would have been the Bergslagsleden of the
water, is empty here. What the map will have instead is the water network of phase 1 —
every shore, every crossing, the class-2 rivers — which is the whole of what a canoe trail
drawing adds, minus the drawing's choice of a line; and the register's shelters and fire
places, which are the canoe trails' rest places and are on the map already as facilities.
Nordic Discovery's names, *Norra* and *Södra kanotleden*, are a company's names for its
rentals' routes and are not carried. Should the county boards ever register a `Kanotled`
here, `naturvardsregistret.trail_type_label` already knows the word and the *Leder* layer
would draw it without a change.

## 4. Open

- **The flow's direction — closed by review, 2026-09-21.** Use the digitised direction of
  every class-2 line, including the single opposing-arrow case; the conclusion is below.
- **Preserving that direction through the graph — closed by review and implementation,
  2026-09-21.** Review extended the scope to the shared chain and edge builders. Directed
  sources record canonical reversal; their edges recover the supplied direction and keep
  it when split. The acceptance test covers a reversed line noded in the middle.
- **k and P — 1.5 and 2.** The three-leg browser sweep settles these prices; review accepted them. `OPEN_WATER_FACTOR` keeps 1.5 and `PORTAGE_FACTOR` supplies 2. Measurements and the phase 2 built note are under §5.
- **N50's river size class — closed for phase 1 after measurement, 2026-09-21.** The cached lines carry
  `vannbredde`, with codes 2 and 3; a correspondence to Topografi 50 class 2 is not
  established. Norway's streams remain out; adding them needs that correspondence.
- ~~Whether anybody publishes the canoe trails as lines~~ — phase R, 2026-09-21: nobody (§3.5).
- **The open-water chords' bytes — closed by review: 10 m stays.** With
  neighbouring portages and the 1 ha cutoff, Malingsbo-Kloten measures 7,117,583
  bytes brotli at 10 m and 6,921,335 at 25 m, against phase 1's 8,114,150 and the
  earlier 6,227,283. The coarser ring saves 196,248 bytes, but at k = 1.5, P = 2
  changes the bay from 1,066.143 to 1,049.992 m paddled and the portage leg from
  126.500 m paddled / 1,152.330 m foot to 51.555 / 1,220.934 m. The lake is
  unchanged. Review rejected those changed ways for a 2.76 % page saving: the
  chords remain on the 10 m shore ring, with no separate ring setting. The
  neighbour portages and 1 ha cutoff stand. The comparison remains under §5
  as the reason for retaining 10 m; the built-note gives the final figures.
- ~~Norway's heights over the sea~~ — phase 1b: the sea is 0 m, lakes their registered
  level, everything else the cached 4 m mosaic; the point service left the network build.
- **Uwe's phone reading of the kayak mode** on the three published maps: the switch, a bay,
  a portage.
- **One way only where it falls — phase 7, opened 2026-09-22.** From the phone at
  Korslångssmedja: the level channel from the small lake to the dam is a class-2 line and so
  one way downstream; upstream the route walked round it. The heights along its edges are
  flat (258.1–258.4 m), the fall is the dam. The plan's phase 7 gates the direction on the
  measured fall; the rising edges (107 / 24.5 km in Malingsbo-Kloten, 165 / 23 km in
  Abisko, by end posts) are classified before the gate is trusted. Uwe's word 2026-09-22:
  "Ja mache das."
- **Lomsdal-Visten has no stream edges at all** — not a defect: N50's `vannbredde` codes
  were never matched to Topografi 50's class 2 (above), so Norway's streams stayed out.

## 5. Changes

- 2026-09-22 — phase 7 opened: one way only where the water falls; the Korslångssmedja finding and its measurement (`~/mockups/kayak-mode/korslang/`) are in the plan's §4 Phase 7.
- 2026-09-21 — phase 2b built: inferred portages have their own kayak-only kind and undrawn-ground price. Both walking settings recover 22,957 m with zero portage; the kayak leg retains its mapped path. The built-note records the graph scope extension and the remaining phase 4 snapshot detail.

- 2026-09-21 — phase 1b built: review retains the 10 m chord ring after the 25 m sweep changed two ways. Ponds stay outside the paddle network, portages join Delaunay neighbours, and Norway reads cached 4 m ground. The final three graphs, Swedish page bytes and completed Norway memory measurement are in the built-note below.

- 2026-09-21 — phase 3 built: connected lakes levelled from the lowest register or shore p10; paddled parts, figures and tracks; dry artifacts byte-identical in both walking settings. The drive's two saved dry hashes already differ with the pre-phase-3 scripts on this graph; the built-note records that review item.

- 2026-09-21 — phase 3 resumed and stopped at surface identity: review settled how water is levelled, but two Topografi 50 water-body ids carry conflicting registered levels, and N50 leaves many water-body numbers empty. The resumed stop-note below; no build started and no runtime change made.
- 2026-09-21 — phase 3 stopped: the water grid and the height tiles do not guarantee a lake plane. One straight water part near the measured bay changes height by 0.96516 m in about 25 m; the stop-note below. No runtime change retained.
- 2026-09-21 — phase 0: the plan and this record opened.
- 2026-09-21 — phase R: the research in §3.5; there is no phase 6.
- 2026-09-21 — phase 6 (`8d864eb`): the two switches on the plan's *Points and stages* page as well, one state, hidden on read-only pages; a drive reading of 85 readings twice; the three pages rebuilt and republished after it.
- 2026-09-21 — phase 5: the three graphs and pages rebuilt on `be43818`'s code (Abisko 4.68 MB, 1.82 MB brotli, 1.26 before; Lomsdal-Visten 19.71 MB, 7.08 brotli, 5.71 before; Malingsbo-Kloten 24.50 MB, 7.12 brotli, 6.23 before); `drive-all` 1,447 / 1,452 / 1,415 readings, none broken (the one Lomsdal-Visten reading was the three-browser race and is green alone); all three published ~15:20 UTC with `just deploy --map <map>` and read back identical to the built pages after the edge's own brotli. Uwe's phone reading is open.
- 2026-09-21 — phase 4b (`aee7804`): Abisko's and Lomsdal-Visten's kayak triples (Torneträsk, Tosen), the long-edge check on walkable edges, the goal-stop invariant on foot plus water, the overview check reading after Keep, the dry hashes re-recorded for the noding's resampling and Lomsdal-Visten's mosaic; suites 1,452 / 1,454 / 1,418 readings, none broken.
- 2026-09-21 — phase 4 (`c766ceb`): the Malingsbo-Kloten scene's kayak triple (Storsjön's shore, Övre Skärsjön's bay, the portage west of Holmtjärnen to Rågåstjärnen) and five readings; the dry way 22,957 m, 2 mm longer from the noding; the suite 1,417 readings, none broken.
- 2026-09-21 — phase 2b (`b95d708`): a `PORTAGE` kind of its own, unreachable and unsnappable in the walking modes, priced as undrawn ground under a kayak, tallied as a connector; the dry scene's way reads 22,957 m on foot and no portage again in both walking settings; the sweep's portage leg 52 m paddled, 1,221 m on foot, 1,009 m of it mapped path.
- 2026-09-21 — phase 1b (`9bb67c0`): portage chords between Delaunay-neighbouring pieces only, never across water (567 / 807 / 1,192 chords on the three maps, none crossing); no paddle network under 1 ha; Norway's whole network off the cached 4 m DTM mosaic (600 walking samples against the point service: median 0.09 m, p95 0.72 m), lakes at N50's `hoyde`, the sea 0 m; the 10 m chord ring kept (25 m changed two of three sweep answers for 3 % of the page). Abisko 1.82 MB brotli, Malingsbo-Kloten 7.12 MB. Three stops.
- 2026-09-21 — phase 3 (`7f68137`): lakes levelled per connected body in the build (150 bodies from the register, 1,005 from the shore's 10th percentile; median difference 0.25 m, largest 2.82 m), paddled parts flat and continuous in the profile, the heading *2.47 km 🛶 · 3.51 km 🚶*, *by kayak* and *portage on foot* in words, paddled points in the GPX and the Garmin course; the dry way byte-identical in both walking settings. Two stops (the shore's tiles, the body's identity).
- 2026-09-21 — phase 2 (`bea479c`): the Kayak switch beside *Stay on paths*, the prices per mode, direction as a predicate on the step, the mode's cheapest metre as the floor, snapping by node eligibility, a paddled edge tallied like a ferry for marking but inside the reserve; the sweep settled **k = 1.5, P = 2**. Three stops on the way (the search's direction, where the settings come from, the tally); the built-note below.
- 2026-09-21 — phase 1 (`ac467b2`): the water network in the build — Shore, Open water, Streams of kind `PADDLE`, portage chords and their ties as `BRIDGE`, `NetworkSource.directed` carried to a per-edge `one_way`; the built-note below. Two stops on the way, both the plan's (the flow test, the layer of the direction).

### Phase 6 built — The switches in plan mode, 2026-09-21

`profile_panel.js` builds Stay on paths and Kayak through one factory, with
one paint function reading `trailsPlan.stayOnPaths()` and `.kayak()` for both
copies. The Points and stages page offers them below the name/undo row and
above the points. The Places on the way page keeps its order, wording and
appearance. On a route read after plan mode has been left, the points page
hides both switches. The panel's existing refresh suffices; `plan_mode.js`
needs no hook or change.

`drive_map.py` adds `the_plan_page_has_the_price_switches` beside the plan
checks. At phone width it lays the scene's shore pair, clicks both switches
on the plan page, reads the paddled parts, checks the goal page's copies,
then clicks Stay on paths there and reads the plan's copy again. It also
checks the read-only page and restores the plan, mode, path preference,
goal and its chosen way, stored stops, selected route, panel page, menu, viewport
and map view. The existing rendered-panel test in `test_maps.py` now checks
the factory, both placements and the read-only guard; its old assertion
against the single goal button was the first hook run's only failure.

**Measured on one warm-cache Malingsbo-Kloten build.**
`command make map ARGS="--park malingsbo-kloten"` succeeded under an 8 GiB
address-space limit, with 217,122 routing edges and a 24.50 MB page. No input
was fetched or rewritten and no tiles were built. The long part was the
existing Ortnamn pairing pass over 6,375 cached names, not the panel change.

The focused drive ran twice on this worktree's page, with
`--only the_plan_page_has_the_price_switches,a_kayak_way_follows_the_shore,a_bay_is_cut_and_a_lake_is_not,a_portage_takes_the_path,a_paddled_profile_is_flat,the_walking_modes_never_take_the_water`:
**85 readings each time, no broken invariants, moved figures or scene skips.**
At 390 × 844 the two switches are visible in the intended order. The walking
plan has no paddled part; clicking Kayak produces **2,122.780 m of paddled
parts** on the Storsjön pair. Both goal copies then read on, with the same
words and knob positions. Switching Stay on paths off there paints the plan
copy off. Both switches disappear on the read-only points page. Live state
and the stored goal compare equal after restoration. The new check took
2.0 s and 2.2 s. Its first attempt had the plan menu over the phone panel;
the reading now closes that menu for the clicks and puts its state back.

`command make hooks-run` passes: formatting, lint, mypy and pytest, plus the
remaining hooks. No other map was rebuilt or published in this worktree;
this phase commits the shared panel change and its reading only. No price,
routing or review decision remains for this change.

### Phase 2b built — A portage is not a path, 2026-09-21

**The inferred kind.** `routing/sources.py` gives carried ground its own
`PORTAGE` kind. In `network/water.py`, only the kind declared by Portages and
Portage paths changes; the geometry, source factors and ordinary bridges do
not. `encoding.py` already carries arbitrary source kinds, so it needs no
change. `maps.py` requires `portageKind`, supplied by
`lomsdal_visten.plan_settings()` beside `paddleKind`.

**The scope stop and its resolution.** The graph removed only `BRIDGE`
chains and cleared only their edge chain ids. Changing the source kind alone
would have turned the existing two-lake fixture's inferred geometry into
three selectable chains, with all five portage edges carrying chain ids;
the old kind had zero of each. Review extended this phase to the two places
in `routing/graph.py`: one `_inferred()` predicate now recognises both kinds.
`_with_bridges` is untouched. The regression tests cover both inferred kinds,
their noding against a path and the path's retained identity.

**The page.** In both walking settings, portage edges have infinite cost,
cannot be traversed in either search or as partial edges, and cannot supply
a snap segment or make a node eligible for snapping. In kayak mode they cost
length × `offPath()` × P. They count protected ground and `undrawn`, without
source credit or a marking bucket; their full and partial routed land parts
retain the payload's heights. Ordinary bridges keep their existing prices.

The new edge price depends on *Stay on paths*, so that switch must now drop
the cached cost table before recomputing a way. This small follow-on decision
stays within `plan_mode.js`; without it, the portage price would retain the
previous switch's ground factor. The executable page tests exercise both
switch positions without manually clearing that table. Further tests cover
walking exclusion, snapping, partial edges, unchanged bridge prices, tallying,
payload round trips and routed portage heights.

**One build, read offline.**
`command make map ARGS="--park malingsbo-kloten"` completed in **1,113.098 s**,
with **3,031,432 KiB** peak resident memory under an 8 GiB address-space limit.
An audit hook blocked network access and writes to the shared cache. No input
was fetched or rewritten and no tiles were built. The graph has **217,122
edges**, including **2,240 Portages and 1,163 Portage paths**; all **3,629,083**
height samples came from the cached 4 m mosaic. Its encoded stream remains
**9,884,753 raw bytes and 6,406,460 base64 bytes**, as in phase 1b.

The phase 3 Firefox harness serves that one page locally with external
requests blocked. Before uses the planner from `HEAD` and changes just the
two source-table kinds back to `BRIDGE`; after uses the final planner and
`PORTAGE`. Geometry, ordering, heights and prices in the payload are shared.
A scratch-only tally field counts metres on the two portage source names,
including partial edges, without changing any routing or public tally rule.

**The same dry journey, not a moving vertex index.** This checkout's
`SCENES["malingsbo-kloten"]` gives the stop, but `goal_lengths()` chooses its
two endpoints at vertex indices 0.1 and 0.7 along the long chain. Noding
changes those endpoints. The initial unadjusted harness therefore measured
a different journey: 22,975.089704 m before, 23,018.562799 m after. The scratch
harness now fixes the endpoints to those saved by phase 4 in
`phase4-dry-main.json` and `phase4-dry-fixed.json`; `drive_map.py` is unchanged.
In journey order, latitude and longitude:

- Start: **59.870408, 15.047954**.
- Scene's stop: **59.902132, 15.211080**.
- Goal: **59.901463, 15.379916**.

| setting | before: foot m / portage-edge m | after: foot m / portage-edge m |
|---|---:|---:|
| Walking | 22,913.954902 / 730.416712 | **22,957.427997 / 0** |
| Stay on paths | 22,913.954902 / 730.416712 | **22,957.427997 / 0** |

Water is zero in all four readings. Both final settings give the requested
**22,957 m on foot with 0 m of portage**. The saved published page reads
22,957.426099 m, a difference of 0.001899 m. The before value differs from
phase 4's 22,251.447685 m because that earlier combined graph predates the
phase 1b reduction of portage chords. This comparison measures phase 2b on
the accepted phase 1b graph, not the superseded chord set.

**The kayak leg still takes the path.** At **k = 1.5, P = 2**, with *Stay on
paths* off, the phase 2 portage leg runs from (59.821858, 15.502671) to
(59.824603, 15.518341). The new inferred-ground price is **6 per metre**,
instead of the old bridge price **2.6**.

| public assembled way | before | after |
|---|---:|---:|
| Paddled | 126.499682 m | **51.555412 m** |
| On foot | 1,152.330304 m | **1,220.934436 m** |
| Mapped paths | 315.869153 m | **1,009.380945 m** |
| Inferred portage edges | 663.166623 m | **0 m** |

The final path is OSM. Its routed land part has **198 height samples**, all
read; the other land parts are straight connectors. A dearer inferred carry
therefore sends more of this leg along the mapped path, as intended. The
inferred-edge tally and profile rules are separately covered by the tests.
Both browser runs restored and compared the mode, path setting, goal and
its persisted way, and plan state. Only spatial-index statistics and the
cumulative height-request counter are excluded, as in the phase 3 harness.

**The remaining phase 4 snapshot detail is now precise.** The final dry GPX
description matches the saved hash
`06ef1cf796a83eeccd0e12f85890064bd1c238ac193e55628f19ec8c32458969` in both
walking settings. The entire figures-page HTML differs from the published
capture only in its point count: **9,076 points instead of 9,084**. Replacing
that one text value reproduces the old HTML exactly. Its new hash is
`d3051c9e206aa2822e5e91206e1ad95f6fe254a8fcdd7739d04829a95ea00dd2`.
The unchanged dry check consequently reports 14 readings, zero broken
invariants and two moved figures (the same HTML hash in both settings),
returning 2. Review should carry the fixed endpoints and the measured point
count into phase 4's scene/snapshot work; neither is changed in this phase.

Scratch, the adapted harness, captures and restoration comparisons are in
`~/mockups/kayak-mode/phase2b/`. `map.log` and `map.time` record the only build;
`before-fixed.log` and `after-fixed.log` are the accepted browser runs, with
`before-portage.json` and `after-portage.json` for the kayak leg. The first
hooks invocation passed both mypy checks and the tests, but pre-commit marked
the type hook failed because the decision record was edited during that
hook. The final run, with all files held unchanged, is `hooks-final.log`.

### Phase 4 built — The scene and the drive, 2026-09-21

**The dry way stands after phases 1b and 2b.** One rebuilt Malingsbo-Kloten
page was compared with the main checkout's published page at the published
start (59.870408, 15.047954), stop (59.902132, 15.211080) and goal
(59.901463, 15.379916). Both walking settings read **22,957.427997 m on
foot**, against **22,957.426099 m** published: **0.001898 m longer** after
noding, with no water or inferred portage. The mapped way and its descriptions
stand. The figures HTML differs only in its point count, **9,076 instead of
9,084**; replacing that text reproduces the published HTML exactly. The scene
records its new hash, `d3051c9e206aa2822e5e91206e1ad95f6fe254a8fcdd7739d04829a95ea00dd2`.
The GPX-description hash remains
`06ef1cf796a83eeccd0e12f85890064bd1c238ac193e55628f19ec8c32458969`.
`goal_lengths()` uses those fixed endpoints on this scene and restores the
goal's previous way. A fractional vertex index would choose a different walk
when noding inserts vertices.

**Three measured legs in `drive_map.py`.** The positions are nodes read from
the page's decoded network; its 25 m water grid verifies the direct crossings.
Shore references are shortest paths using only the page's Shore edges.

| scene leg | positions, latitude and longitude | reading |
|---|---|---|
| Storsjön, Karl-Ersviken to the west bank below Hult-Pelles vik | (59.887213, 15.675327) → (59.895929, 15.650716) | 2,122.779 m, all Shore, round the northern end; the shore reference is the same |
| Övre Skärsjön, Fyrkantviken towards Hästviken | (59.844846, 15.546195) → (59.852644, 15.540811) | 1,066.143 m over water against 2,502.242 m round the shore; 720.934 m of Open water and 345.209 m of Shore |
| Unnamed lake west of Holmtjärnen to Rågåstjärnen | (59.906173, 15.465869) → (59.914508, 15.462779) | 1,274.726 m on mapped paths and 5.912 m of Shore; no straight or inferred land |

The carry uses **516.540 m of Topografi 50 roads, 503.685 m of Topografi 50
trails, 13.531 m of Topografi 50 paths and 240.970 m of Leder**. Storsjön's
direct crossing measures **1,685.596 m**, entirely wet by the grid, but the
chosen way follows the shore and takes no Open water edge. The water profiles
have **417 samples at 110 m** on Storsjön and **212 samples at 220 m** on
Övre Skärsjön: both ranges are **0 m**, and both profiles reach the leg's end.

In both walking settings, the Storsjön pair has **3,266.273552 m on foot,
8.023914 m over water and 70.878695 m of straight land**, exactly as on the
published page, with identical geometry. Neither way has a paddled part or a
water-network source credit; neither tap snaps to a paddle or portage edge.
The small existing water crossing belongs to the walking way, not the new
water network.

The five checks borrow and restore the mode, path preference, goal way, plan
and map view. Each checks its restoration. A separate drive also passed with
Kayak and Stay on paths already on, a routed goal preference and a selected
point in an existing plan. Abisko and Lomsdal-Visten have `None` for the new
fields and five named scene skips explaining the pending phase 5 rebuild and
measurement. Their pages were not rebuilt. The existing long-edge reading
retains its same 3.436 km Topografi 50 road at (59.883874, 15.740213): noding
renumbered it from edge 65812 to 66935; the old index now names a 72 m edge.

**The whole drive found one displaced pixel reading.** The first two focused
runs each passed **98 readings**, including the five kayak checks, the two
length checks and the long edge. The whole suite then ran once to
`drive-all.log`, read through: **1,417 readings, one broken invariant, no moved
or new figures, four expected scene skips**. Every kayak reading passed, as
did the later goal and offline checks. The failed chosen-line colour reading
also failed alone on the new page and passed on the published page.

Its middle-vertex sample moved from (59.896514, 15.230398) to
(59.896277, 15.231515) after noding. The published sample is opaque; the new
sample has **alpha 139**, with rounded RGB **(176, 188, 196)** instead of the
line's **(176, 190, 197)**. One pixel below it is opaque and has exactly the
line's colour, with the route opaque underneath. The driver now chooses the
nearest opaque shared pixel in a square as wide as the picked stroke, by
coverage alone. It asserts opacity and retains the exact colour comparison.
No renderer or colour changes were needed.

The final focused runs, `drive-3.log` and `drive-4.log`, include that corrected
reading beside the original eight checks: **108 readings green twice in a
row**, with no moved or new figures and no skips. Both read the opaque pixel
at offset (0, 1). The whole suite was not repeated. No phase 5 work or
publishing was done, and this phase leaves no decision for review.
`command make hooks-run` passed formatting, lint, mypy, pytest and all
remaining hooks; its report is `hooks.log` beside the drive logs.

The one warm-cache build has **217,122 edges, 113,013 nodes, 820,435 vertices,
43,700 chains and 3,629,083 height samples**. Its encoded graph matches the
accepted phase 1b graph; the source header carries phase 2b's portage kind.
No tiles were built, inputs fetched or shared cache files rewritten. Scratch,
captures and logs are in `~/mockups/kayak-mode/phase4-resumed/`.

**Phase 4b, the rebuilt Abisko and Lomsdal-Visten pages, 2026-09-21.** The
three pages and their trees in the main checkout were served by absolute path,
without rebuilding or writing there. Only `drive_map.py` and this built-note
change. Scratch and reports are in `~/mockups/kayak-mode/phase4b/`.

The long-edge helper now reads the source's kind from the graph header and
considers only `path` edges. A Shore edge cannot be the ground for a walking
tap. Abisko consequently reads **Topografi 50 paths, edge 30610, 7,795 m**,
instead of the 8,512 m Shore edge 57610. The rule also applies to the other
scenes, including Malingsbo-Kloten's explicitly chosen walking edge. The
goal-stop invariant compares its last row with **foot plus water**, because
the row counts along the drawn line. Its old 11.88 km expectation was computed
from foot metres alone, not a scene figure; nothing is re-recorded for it.

Abisko's overview check failed alone too: **67 requests, 8 complete rows** in
the snapshot taken before Keep. Waiting for network-idle did not change that.
The worker can finish browsing a pack between that snapshot and Keep's read.
The check now accounts for every expected key by a request or a complete row
read after Keep, still requires exactly the expected kept keys, and still
checks the repeat's exact missing overview and ledger. The focused drive of
the overview, long edge and goal passes **96 readings**. The final overview
drive alone passes **21 readings**, fetching all 81 packs, then exactly the
14 missing overview packs on the repeat. No worker code changes.

Readiness now awaits the graph's decode without returning its typed arrays to
Python. Restoring a kayak reading's map view also returns no Leaflet map:
serialising that layer tree caused a `RecursionError` in the first Abisko
measurement. Neither change alters page state or the values being checked.

The new scene positions come from the decoded network; the page's water grid
checks the direct crossings, and shortest paths using Shore alone give the
shore references. Both carries join separate water components, with neither
endpoint in the page's river outlines.

| scene leg | positions, latitude and longitude | reading |
|---|---|---|
| Torneträsk, northwest towards Björkliden | (68.393226, 18.715936) → (68.407071, 18.697511) | 2,116.110 m, all Shore; the direct crossing is 1,719.949 m, entirely wet |
| Torneträsk's bay east of Abisko Östra, west bank to the opposite headland | (68.355318, 18.836408) → (68.358208, 18.865112) | 1,408.028 m paddled against 2,988.742 m round the shore; 740.695 m Open water and 667.333 m Shore |
| The two lakes west of Valfojåkka shelter | (68.268452, 18.179781) → (68.271026, 18.180649) | 335.952 m carried: OSM 302.342 m and Leder 33.610 m |
| Tosen, southwest along the north shore from Bekkevoll | (65.330996, 12.938274) → (65.324721, 12.926333) | 932.128 m, all Shore; the direct line is 893.922 m, 794.597 m wet |
| The narrow inlet south of Bekkevoll | (65.330996, 12.938274) → (65.325983, 12.939154) | 715.252 m paddled against 2,028.373 m round; 378.876 m Open water and 336.376 m Shore |
| The two lakes south of Gardsjorda | (65.742431, 13.002636) → (65.734636, 13.004338) | 959.690 m carried: FKB 13.779 m, UT.no 858.280 m and N50 paths 87.631 m |

Neither carry includes straight or inferred ground. Abisko's shore and bay
profiles have **415 and 279 samples, all at 342 m**; Tosen's have **184 and 142,
all at 0 m**. Each spans the whole paddled leg. The five kayak checks pass
**71 readings twice in a row on each page**, including restoration of the mode,
path preference, goal way and plan. Their reports are `abisko-kayak-{1,2}.log`
and `lomsdal-kayak-{1,2}.log`.

At the chosen Abisko shore pair the two walking preferences retain their
published parts and source credits, their foot lengths each growing only
**0.000522 m**: ordinary walking **2,940.880 m foot / 15.273 m water /
514.362 m straight land**, Stay on paths **2,963.410 / 15.283 / 510.746 m**.
Tosen's walking figures are exactly the published ones: **1,074.646 / 0 /
747.568 m** and **1,593.360 / 0 / 496.858 m**. Neither setting credits a water
source or snaps to a paddle or portage edge.

**The dry hashes are re-recorded after review.** Published page
bytes were fetched once per map and served offline beside the existing trees.
Their figures and GPX-description hashes reproduce the scene's recorded hashes.
Using fractional vertex indices on the rebuilt pages chose different endpoints:
Abisko's dry walk became 16,836.258 m instead of 16,700.516 m, Lomsdal-Visten's
18,805.768 m instead of 19,101.251 m. The scene now fixes the published endpoints,
as Malingsbo-Kloten already did, so the check compares the same walk.

| fixed dry walk | published metres | rebuilt metres | change |
|---|---:|---:|---:|
| Abisko: (68.436158, 18.606154) → (68.327135, 18.753069) | 16,700.516116 | 16,700.517542 | +0.001427 m |
| Lomsdal-Visten: (65.327587, 13.129687) → (65.407534, 13.180339) | 19,101.251416 | 19,101.262608 | +0.011192 m |

All **1,122 / 2,271** published geometry vertices remain in the rebuilt walks,
which have **1,132 / 2,299** vertices. Their metric Hausdorff distances are
**0.064509 / 0.050511 m**. Abisko still has two routed parts, Lomsdal-Visten
three; both have zero water, and source-credit changes are confined to those
millimetres. The words also changed:

- Abisko: **+385 / −335 m → +382 / −332 m**, steepest **84 % → 76 %**,
  **6,425 → 6,420** profile points. The remaining figures HTML and the source
  description are identical.
- Lomsdal-Visten: **+636 / −771 m → +614 / −753 m**, steepest **54 % → 55 %**,
  high **926 → 925 m**, **7,647 → 7,639** points, and ground where no source
  draws a path **2,471.681429 → 2,395.321856 m**. The remaining figures HTML
  and source description are identical.

Review accepted the new hashes for these same horizontal ways: noding restarts
the profile's 5 m sampling at each new edge's start, shifting the samples and
therefore ascent, steepest and point count. Lomsdal-Visten also reads heights
from the decided 4 m mosaic rather than the point service (phase 1b, median
sample change 0.09 m), accounting for its +636 → +614 m ascent. The field's
docstring records these reasons. No height, coverage, router or page code was
changed to make the figures agree. `*-dry-before.json` and `*-dry-fixed.json`
retain the parts, geometry, sampled profile, exact HTML and descriptions.

The coverage change is the re-cut's per-edge answer, not a transfer from a
connector to a source: published UT.no edge **502, 2,471.681429 m**, all flagged
as having no recorded path, becomes edges **546–550, 2,471.681525 m** on the
same line; edge **546, 76.359670 m**, now has that flag clear, while the other
four retain it. `no_path_recorded` tests the share of each edge near a recorded
physical way, so splitting changes the extent each answer describes. Inferred
ground remains **0.257603 m**, and UT.no's credit grows only **0.011192 m**;
the net reduction in ground with no recorded path is **76.359573 m**.
`review/coverage.json` retains these edges and their flags.

One rejected Abisko shore pair is also a finding, rather than an accepted
new walking snapshot: **(68.400732, 18.698912) → (68.393226, 18.715936)**.
Ordinary walking grows 0.000496 m, but Stay on paths changes from
**1,967.052128 m foot / 7.539939 m water / 656.648381 m straight land** to
**2,262.415460 / 2.520330 / 590.308964 m**. The final scene uses the longer
shore pair above, whose walking ways stand. At identical prices (ground 10,
water 30 and the same walking-source factors), the page's routing cost falls
from **7,982.499022 to 7,739.278843 cost-metres**, so the new way is cheaper by
**243.220179**: the added nodes let Stay on paths enter with more path and less
straight ground. `review/abisko-{before,current}.json` records the router's
price alongside the reproduced walking lengths and restored page state.

**The whole suites, once per page, read through in full.** The reports are
`abisko-all.log`, `lomsdal-all.log` and `malingsbo-all.log`; their 1,806, 1,808
and 1,777 lines are also accounted for by check in the adjacent `.review.txt`
files. No whole suite was repeated.

| page | readings | broken | moved | new | scene skips |
|---|---:|---:|---:|---:|---:|
| Abisko | 1,452 | 0 | 2 | 0 | 0 |
| Lomsdal-Visten | 1,454 | 0 | 2 | 0 | 0 |
| Malingsbo-Kloten | 1,418 | 0 | 0 | 0 | 4 |

The four moved figures were precisely the dry hashes since accepted above. The
goal's 11.89 km row passes on Lomsdal-Visten; all three long edges and overview
checks pass. Each northern scene gains 66 kayak readings; Lomsdal-Visten also
captures three more snap frames than the supplied run, Malingsbo-Kloten one
more, which explains the small difference in totals. The four Malingsbo-Kloten
skips are its existing scene choices.

After re-recording, the dry check alone passes **12 readings on each northern
page, none broken or moved** (`review/abisko-dry.log` and
`review/lomsdal-visten-dry.log`, both read in full). The whole suites above
remain the single runs; these focused checks resolve their four moved hashes.

`command make hooks-run` passed formatting, lint, mypy, pytest and every
remaining hook (`hooks.log`, then `review/hooks.log` after these resolutions).
Nothing was rebuilt or published; no tile build
or shared-cache write was made.

### Phase 4 — Stopped at the dry walking way, 2026-09-21

**The inherited hashes cannot be re-recorded as a noding-only change.** The
published main-checkout page reproduces both stored hashes exactly. The new
worktree page reproduces phase 3's dry length, **22,435.423253 m**, but its
walking route has changed. Holding the published start, stop and goal fixed
makes the change larger: **705.978414 m shorter**, taking the new inferred
portages. These are measurements from the two pages, with kayak and Stay on
paths both off:

| dry way reading | published page | new page, helper's endpoints | new page, published endpoints |
|---|---:|---:|---:|
| on foot, m | 22,957.426099 | 22,435.423253 | 22,251.447685 |
| over water, m | 0 | 0 | 0 |
| inferred connectors, m | 0.459513 | 2,358.845478 | 2,358.845478 |
| Topografi 50 paths, m | 1,578.674083 | 0.963762 | 0.963762 |
| ascent, m | 283.160004 | 365.750015 | 365.750015 |

Both new-page journeys use **2,305.204001 m of Portages**, **53.418656 m of
Portage paths** and **0.222821 m of ordinary bridge connectors**. Source
counters added only to the served response's edge tally identify those metres;
they change no edge cost or route choice. The published and helper-endpoint
captures also retain the figures HTML and every GPX description. The new
build's ascent is 2.089996 m below the phase-3 capture; that additional
difference is recorded, not reconciled by changing an expectation at this stop.

There are two mechanisms to separate. `goal_lengths()` in `drive_map.py`
chooses its start and goal at 10 % and 70 % of the long chain's vertex count.
Noding changes that count, moving the chosen start from
(59.870408, 15.047954) to (59.871559, 15.049899), and the goal from
(59.901463, 15.379916) to (59.901394, 15.380159). The intermediate stop stays
at (59.902132, 15.211080). These are different journeys before routing begins.

Separately, `network/water.py:portages()` gives both Portages and Portage paths
kind `BRIDGE`. `plan_mode.js:router()` excludes PADDLE edges from walking,
but gives those inferred connectors finite walking costs. `tallyEdge()` counts
them as undrawn ground and omits their source names from the public credits.
Thus a dry way can acquire the new portage shortcuts without reporting any
water or naming a new source. The phase-3 before/after byte equality uses the
same combined graph and does not establish equality with the published
walking graph.

**Review must decide whether the new inferred portage connectors belong in
walking routes.** If the published walking way must stand, their availability
needs correcting outside this phase's permitted files. If the changed walking
route is intended, accepting it requires an explicit decision; it cannot be
recorded as noding alone. The dry scene also needs stable coordinates when it
is meant to compare the same journey across builds.

`drive_map.py` and its saved hashes remain untouched. The five kayak checks,
their two acceptance runs and the whole drive are deferred at this stop.

**Build and validation.** One `command make map ARGS="--park malingsbo-kloten"`
completed under an 8 GiB address-space limit: 247,210 edges, 3,960,895 height
samples and 1,155 levelled lakes, of which 150 have registered levels. Only
cached inputs were used; no tiles were built or shared cache files rewritten.
The existing main-checkout tiles and height tiles were made visible through
worktree-output symlinks. The long build delay was in the existing
`ortnamn.paired()` loop; a stack snapshot and stdout flush diagnosed it without
changing the build's calculations. No other map was built by this phase.

The browser measurements blocked external requests and restored the mode,
path setting and goal way. The unmodified `a_way_counts_foot_and_water` and
`a_dry_way_keeps_its_words` were then driven by the requested absolute-page
`command make drive` invocation: **22 readings, zero broken invariants, two
recorded figures moved, zero new figures and zero skips**, exit 2. The complete
report was read. Its figures hash is
`5767e9c27efdd484cb6bf3fc76bc23679c72b52cfca0b59836b5081be6706a30`
and its GPX-description hash is
`b8b52a1d5590a15aa8a55518ab2d2265f1810be4066781ab88dc2a0bebd59c5b`,
matching the instrumented capture. Neither has been accepted into the scene.
`command make hooks-run` passed formatting, lint, mypy, pytest and every
remaining hook. Scratch and logs are in
`~/mockups/kayak-mode/`: `phase4-map.log`, `phase4-dry.py`,
`phase4-dry-main.json`, `phase4-dry-current.json`, `phase4-dry-fixed.json`,
their logs, `phase4-dry-drive.log` and `phase4-hooks.log`.

### Phase 3 built — Lake levels and what a paddled way says, 2026-09-21

**Both stops resolved by review.** A body is a connected set of touching lake
polygons, regardless of sheet boundaries or missing and conflicting ids. Its
level is the lowest registered level among its polygons, otherwise the 10th
percentile of its own shore samples. Only lakes are levelled: river surfaces,
streams and the sea keep their sampled profiles, and a portage remains ground.
This replaces the earlier premise that shoreline tiles alone give a lake plane.

`network/water.py` groups the clipped polygons before shoreline simplification,
using intersection (including a shared point), so simplifying a bank cannot
separate a body. Generated Shore and Open water chains carry a local body label
and its registered level; source ids are not used. `water.build()` calls
`level_lakes()` immediately after the country's `measure()` has attached heights
through `routing.elevation.with_elevation()`. Every lake edge's sample is replaced,
including chord samples; ascent, descent and the lake chain's derived figures
are recomputed. Other edge and chain profiles are left alone. Percentiles use
all finite samples on the body's own Shore edges, including their shared ends;
chords and adjacent bodies do not contribute.

`network/sweden.py` passes `Sjö` and `hojd_over_havet`. Two cached lake entries
express their levels as intervals, `100-102` and `102-105`; their lower bounds
are used, for the same reason that review chose the lower of conflicting
sheet readings. The first build invocation stopped on those strings before
constructing a graph; the corrected invocation is the one completed build.
`network/norway.py` keeps `hoyde` from the full cached N50 area layer and levels
`Innsjø` and `InnsjøRegulert` by the same rule. N50 does carry registered levels:
the cached 1813 delivery has 4,528 ordinary lake polygons with one and all five
regulated lake polygons with one. Its absent body numbers are irrelevant now.
Norway's river source selection has not been expanded by this phase.

**Malingsbo-Kloten's levelled payload.** The combined graph retains 247,210
edges and samples 3,960,895 heights from the cached 4 m mosaic, none outside it.
It has **1,155 lake bodies: 150 registered, 1,005 shore percentile**. All 150
registered bodies also have a shore percentile; the **median absolute difference
is 0.254997 m and the largest is 2.820000 m**. The comparison is between the raw
sample percentile and register, before payload quantisation.

**Parts and words.** `plan_mode.js` makes routed PADDLE edges and straight water
runs `paddled` only in kayak mode. Routed parts read the levelled payload;
straight lake runs take their lowest finite tile sample. A straight run splits
at a lake/river boundary as well as at land, so the river keeps its fall and
cannot supply the lake's level. An entirely unread run stays unread. Paddled
metres go into `crossed`, not `total`, and advance the profile axis and stations
without a NaN break. `profile_panel.js` uses that axis, leads with the water
glyph, and says *by kayak* and *portage on foot* in the figures and shared file
description. The existing GPX and Garmin writers now receive a continuous
paddled track; the GPX reader recognises its part kind and includes those metres
when anchoring stations. Walking mode never creates that kind. `maps.py`'s
part table describes the distinction. Tests cover the body rules, unchanged
non-lake profiles, partial paddled edges, rivers, the measured bank samples,
the continuous axis and the ferry's existing gap.

**The page measurement.** One completed
`command make map ARGS="--park malingsbo-kloten"` used the warm cache under an
8 GiB address-space limit. No tiles were built or inputs fetched or rewritten.
The build captures its JavaScript at import time; the Firefox harness served
the final scripts against this one levelled payload, and the pre-phase-3 scripts
from `HEAD` against the same payload for comparison. It served only local files,
with external requests blocked. No second graph build was run.

The original six-sample bank case at latitude 59.84547894974684, longitude
15.54560276 to 15.546050339490117 still reads the six raw tile heights in the
first stop-note. Its single paddled part now reads **219.5565374717 m six times**,
range **0 m**. The bay-and-portage route used the phase-2 bay backwards, followed
by the portage pair: (59.852644, 15.540811), (59.844846, 15.546195),
(59.824603, 15.518341), (59.821858, 15.502671).

| public page reading | measured |
|---|---:|
| water (`trailsPlan.state().crossed`) | 2,469.230866 m |
| foot (`walked`) | 3,506.887899 m |
| profile span and final sample distance | 5,976.118765 m |
| bay part | 1,066.143381 m; 212 samples, all 220 m |
| every paddled part's height range | 0 m |
| GPX | one segment, 2,340 points |
| Garmin | 157 course points |
| profile breaks / unread samples | 0 / 0 |

The heading leads with **2.47 km by kayak · 3.51 km portage on foot** in its
accessible labels, water glyph before walking glyph. The figures page and both
file descriptions begin with those words. The GPX has 865 points at the bay's
220 m level and the Garmin course has 19. The three-station water check reads
1,632.535604 m paddled and 7.515625 m on foot, one GPX segment with 647 points,
and 16 Garmin course points. Its middle station is in the water grid; all three
stations lie on exported trackpoints to numerical precision and reload with
track indices **0, 357, 646**. Mode, path setting, goal way and plan state were
restored and compared after each run.

**The dry bytes stand, in both walking settings.** The unchanged
`goal_lengths()` reading selects the same dry way, 22,435.423253 m on foot and
zero water, with pre-phase-3 and final scripts. Complete artifacts, including
all GPX text rather than just its description, compare equal. The clock was
fixed for file timestamps; no output was normalised before comparison.

| artifact | bytes in each version | SHA-256, equal in both walking settings |
|---|---:|---|
| heading | 1,266 | `117f87a2f5e8c91f7324ac0d99e591b1b61477f063471c4855f8e60846288af2` |
| figures page | 3,377 | `3a8f9304faf12d6c10bf826f7e431f52cdcdbfd1c992ec6b095982286b42ef20` |
| GPX | 652,513 | `40905dbce9491435a48492dada345e2aa2951b93639ad79168a54c92e64ecf26` |
| Garmin | 17,185 | `bb29a31235431eb1414bf37d4f469d19c06e582c291e61158bf4cc5b8862c0e3` |
| profile SVG | 12,522 | `797ccb35c732b962016470c2712d3626c394d3143274df5b02c059ce62ee365d` |

**One inherited acceptance item remains for review.** The unedited
`a_way_counts_foot_and_water` and `a_dry_way_keeps_its_words` run in both walking
settings: 34 readings, **zero broken invariants**, but the drive returns **2**
for its two stored dry hashes, repeated in each setting. This happens with both
the pre-phase-3 and final scripts, identically. The scene expects figures hash
`3158990d95dd325fc211dee7c1a2473a12c38fd2f906b0c37f8e484d9d17d063`
and GPX-description hash
`06ef1cf796a83eeccd0e12f85890064bd1c238ac193e55628f19ec8c32458969`;
the readings are the figures hash above and description hash
`0da928dba1ec2fcfd501933abb4dff852a6d844371b38924ca9d1e4272767ee6`.
Thus the phase changes no dry byte, but cannot claim that those older recorded
figures are green. `drive_map.py` remains untouched as required. Review must
reconcile its saved scene with the combined graph in phase 4; changing that
scene or the earlier routing rules here would change this phase's scope.

Norway's map was not rebuilt: only Malingsbo-Kloten's build was authorised,
and a Norway build could need uncached height-service readings. Its shared
levelling rule is covered by the geometry and profile tests. Scratch is in
`~/mockups/kayak-mode/`: `phase3-levelled-map-final.log`,
`phase3-browser.py`, `phase3-measure.js`, `phase3-measure.json`, the
`phase3-before-*` and `phase3-after-*` captures and restoration checks.
The initial hooks run passed the tests but found typing errors in the new
pandas/geometry code; these were corrected. The final required run is recorded
in `phase3-built-hooks-final.log`.

### Phase 3 resumed — Registered levels and surface identity, 2026-09-21

**Review resolved the tile-height stop.** Shore and Open water are to carry
their surface's id and take one level per body after sampling: the registered
level where present, otherwise the 10th percentile of that body's shore
samples. Streams keep their sampled fall and portages remain ground. A straight
paddled part takes the lowest of its own tile samples; routed paddled parts use
the levelled payload. The six-sample case from the first stop must become one level
six times. The 0.5 m acceptance remains.

**The attachment point is `trails.network.water.build()`, after
`network = measure(network)`.** Sweden's `measure()` reads the cached mosaic;
Norway's reads the height service. Both call
`trails.routing.elevation.with_elevation()`, which attaches edge samples and
derives edge and chain figures. Surface attributes can travel on the generated
chains and be associated with the sampled edges through `chain_id`; no change
to the graph's fixed edge schema is needed for that association. Levelling must
also update the derived figures.

**Two bodies have no single registered level to use.** The cached Topografi 50
delivery of 2026-09-08 was read over `(14.967, 59.729, 15.922, 60.176)` and clipped
to that box. Two `vattenytaid` values each appear on two lake features with
different, nonempty `hojd_over_havet` values. All four features intersect the
box; these are not conflicting rows outside the map extent.

| water-body id (`vattenytaid`) | feature id (`objektidentitet`) | registered level m |
|---|---|---:|
| `40b2d64f-976b-424d-b487-e87c778bf61e` | `40dd5412-f8c9-4c34-904c-51f0d205ef0c` | 207 |
| `40b2d64f-976b-424d-b487-e87c778bf61e` | `5407e790-d0f5-4f83-aa78-2722aff825ec` | 208 |
| `f677b013-7477-43b0-bbfa-fe5f926ad355` | `9c370939-239a-49d4-8bf9-f37de82ec7dc` | 150 |
| `f677b013-7477-43b0-bbfa-fe5f926ad355` | `80e16336-9862-494c-91c5-4f77149e0809` | 149 |

The requested rule does not choose between these levels. Taking a minimum,
using the shore percentile despite a registered level, or separating the
features would each add a decision. **Review must choose how conflicting
registered levels on the same body are resolved.** No aggregation was added.

**Norway has levels, but not an identifier on every surface.** Read directly
from cached `n50_1813.zip`, layer `N50_Arealdekke_omrade`:

| kind | polygons | with `vatnlopenummer` | with `hoyde` | missing both |
|---|---:|---:|---:|---:|
| Havflate | 247 | 0 | 0 | 247 |
| Innsjø | 4,670 | 726 | 4,528 | 126 |
| InnsjøRegulert | 5 | 5 | 5 | 0 |

`vatnlopenummer` names 721 distinct ordinary lakes and five regulated lakes.
The reader `n50.Source.load_water()` currently discards both fields, returning
only `objtype`, `kommune` and geometry; the underlying `load_layers()` retains
them. Keeping those fields alone does not identify the 3,944 ordinary-lake
polygons and 247 sea polygons whose body number is absent. **Review must decide
what identifies a body there**, so that the shore percentile is grouped by
the intended body rather than all missing ids together or an invented split.

Only this record changed. The permitted map build was not started on this
resumption, preserving the single build for the resolved implementation. No
browser state changed, no tile build or download was started, and the cache was
read only. Consequently no surface-level totals, register/percentile difference
statistics, six-sample remeasurement, kayak exports or dry-byte comparisons are
claimed. Validation of this record-only change is in
`~/mockups/kayak-mode/phase3-identity-stop-hooks.log`.

The input summaries are `~/mockups/kayak-mode/phase3-sweden-fields.json` and
`phase3-n50-fields.json`; the four conflicting features, including their bounds
and clipped areas, are in `phase3-register-conflicts.json` in that directory.

### Phase 3 — Stopped at the water profile, 2026-09-21

**The premise that tile sampling makes a water part flat does not hold at the
shore.** Phase 3 step 1 calls for a paddled part sampled from the existing height
tiles, and the acceptance asks for water flat within 0.5 m. A straight part that
the page's grid holds entirely as water changes by **0.9651607896 m** in about
25 m. No rule for resolving that disagreement is in the plan.

The phase 2 worktree and its built page had been removed. The permitted
`command make map ARGS="--park malingsbo-kloten"` was started in this worktree
under an 8 GiB address-space limit. While it ran, the existing main-checkout
Malingsbo-Kloten page supplied its water grid and cached height tiles for a
read-only check in Firefox, with all external requests blocked. This did not
measure a new kayak route: it tested the water/height premise before completing
one. The in-memory build was stopped after the disagreement was found; no map
or tiles were published or built to completion.

The first probe sampled 101 positions along phase 2's bay pair, from
(59.844846, 15.546195) to (59.852644, 15.540811). Its 95 positions marked as water
range from 219.53125 to 220.4062229349 m. That alone is not a within-part test:
the grid splits this line with land. Repeating with the production
`heightsFor()` sampler gives 184 positions, 171 wet, and three water runs; each
individual run spans less than 0.5 m. A local probe beside the raised readings
then isolates the disagreement in **one continuous water part**, rather than
comparing water on opposite sides of a land part.

Both endpoints of that part have latitude **59.84547894974684**. The longitude
runs from **15.54560276** to **15.546050339490117**. Production `heightsFor()`
lays six samples along it; `trailsGraph.waterAt()` returns true at every one.
Their tile heights, in order, are:

| sample | height m |
|---|---:|
| 1 | 220.5216982613 |
| 2 | 220.4376995500 |
| 3 | 220.2155094370 |
| 4 | 219.8346055229 |
| 5 | 219.6249027445 |
| 6 | 219.5565374717 |

Under step 1's grid rule this is one paddled run. Retaining the tile heights
would retain that slope. The measurement establishes the disagreement; it does
not settle whether the water grid, shoreline position,
or height interpolation should change. **Review must decide how near-shore
water gets its level, or revise the flatness acceptance.** No flattening,
shoreline adjustment, or alternative sampling rule was added.

The draft changes to `plan_mode.js`, `profile_panel.js`, `maps.py`, and tests
were saved outside the repository as `~/mockups/kayak-mode/phase3-draft.patch`
and removed from the worktree. Its initial hooks run passed formatting, lint
and mypy; tests reported 1,968 passed and four assertions still expecting the
old source text. That draft is not an accepted implementation. Validation of
the retained record-only change is in `phase3-stop-hooks-final.log`. The kayak figures,
heading, GPX and Garmin files, station anchoring, dry byte comparison and the two
unchanged drive checks were not completed. No mode, goal or chosen way was
changed by the tile probes, and their fresh browser contexts were closed.

Scratch: `~/mockups/kayak-mode/phase3-bay-tiles.py`, `phase3-bay-exact-tiles.py`,
`phase3-bank-grid.py`, and `phase3-bank-straight.py`, with their JSON readings and
logs. The decisive six readings are in `phase3-bank-straight.json`; the stopped
build is `phase3-map.log`, and the discarded draft's hooks are `phase3-hooks.log`.

### Phase 1 — Stopped at the flow measurement, 2026-09-21

**No water network built.** Step 1 requires a stop when neither direction test is clean.
The cached heights and the nearby arrows disagree, so steps 2–7 have not been started.

The same Malingsbo-Kloten box as the plan, `(14.967, 59.729, 15.922, 60.176)`, read from
Topografi 50's cached 2026-09-08 delivery: **347 class-2 features, 118.376695 km**, each a
MultiLineString containing one line. `storleksklass` is text (`"2"`). Lines were clipped to
the projected EPSG:3006 box as in the original measurement, preserving their direction.

Heights were read bilinearly at each line's first and last vertex from the main checkout's
`analysis/output/dem/lantmateriet-malingsbo-kloten/1/13/` tiles, by absolute path. Terrarium
was decoded with `trails.processing.dem_tiles.unpack`, treating its missing value as
missing. These are the built tiles derived from the 1 m model, not native 1 m samples.
All **694 endpoints** had heights. No cache or main-checkout output was written.

| Endpoint fall, first height minus last | Lines |
|---|---:|
| positive | 286 |
| negative | 61 |
| exactly zero | 0 |
| absolute difference at most 0.1 m | 68 |
| absolute difference at most 0.5 m | 168 |
| absolute difference at most 1 m | 210 |

Thus **286/347 = 82.42%** run downhill in their digitized direction, below the plan's 95%.
The small differences above are a sensitivity count, not an adopted tolerance for deciding
flow. Reversing every negative difference would assign a direction to all lines, but does
not pass the independent arrow check.

The cached `hydropunkt` layer has **2,121 arrows**, 2,071 small and 50 large. For each line,
the nearest arrow was found by point-to-line distance; **63 lines** have one within 50 m.
The line bearing was measured on the tangent between positions 5 m before and after the
projected arrow position, bounded by the line's ends. Agreement means a bearing difference
strictly below 90 degrees. The same arrow can be nearest to more than one line.

The arrow's `rotation` convention was tested empirically: both signs and offsets 0, 90,
180 and 270 degrees against clockwise-from-north line bearings. The best fit is
`bearing = 90 - rotation`, consistent with rotation counterclockwise from east:
**62/63 = 98.41%** agree with digitization, but only **56/63 = 88.89%** agree with endpoint
fall. This is an inferred convention, not a documented guarantee. None of the eight
conventions reaches 95% agreement with endpoint fall.

The seven arrow/height disagreements, with the best-fitting convention:

| Topografi 50 object id | First minus last height (m) | Arrow distance (m) | Arrow vs digitized bearing (degrees) |
|---|---:|---:|---:|
| `1c0f0fb7-ab9d-4b0d-a570-8cc1db24fd75` | -0.013950 | 24.051 | 1.587 |
| `4770a504-8e77-49e7-939f-d3bdbb2f86e2` | -0.206819 | 19.468 | 0.742 |
| `4bb533b2-8c9d-411d-8088-e57789729100` | -0.113068 | 0.000 | 0.286 |
| `79c63f36-b672-4ab7-aa91-0a54adb7e01a` | -0.059158 | 34.499 | 9.140 |
| `8277a574-e586-42a2-bc01-9b0156c7ccde` | -0.212724 | 17.114 | 2.773 |
| `e861498e-c88f-4dcd-be3a-15bf2bef473c` | -0.304967 | 21.745 | 14.637 |
| `ff1bf090-d2c9-45f3-a255-774f646002e8` | 4.743805 | 37.952 | 108.296 |

Six have an uphill difference smaller than 0.305 m, while their arrows agree with the
line direction. The seventh has a 4.744 m fall and an arrow 37.952 m away whose bearing
opposes the local line. A nearest arrow is therefore not by itself a resolved flow rule.

The 61 lines whose endpoint heights oppose digitization are listed here so a review can
revisit the actual features rather than a count. Heights below are first minus last:

| Topografi 50 object id | Difference (m) |
|---|---:|
| `0838027e-45ab-4d35-b467-65972112f62e` | -0.275398 |
| `0916c147-8dfd-4e7a-a71a-a691553a11f5` | -0.018293 |
| `0e9dd12a-aec4-46ea-8a3f-a16b7883518f` | -0.285333 |
| `1033e83c-5977-476b-88b3-3e7aae5c5b65` | -0.199784 |
| `1c0f0fb7-ab9d-4b0d-a570-8cc1db24fd75` | -0.013950 |
| `217d06f2-72fd-4f37-8061-b6e8b59d4be5` | -0.313620 |
| `22de5712-c004-41c4-9167-c9f8cd1d862a` | -0.088698 |
| `25f4f53c-41d3-4bcd-b80f-595eaa896d9a` | -0.117252 |
| `263083e0-baad-44ff-b261-e8403cc96e59` | -0.063104 |
| `267ebe7a-e380-4335-ba63-2d9d57224645` | -0.177974 |
| `28c8ccba-e7a9-4318-9307-fa3e908cea81` | -0.153076 |
| `2a2d10bb-a7f1-4a96-ac7d-086e64274d00` | -0.107237 |
| `2d2ee1ee-2327-47ac-9eab-bd608390f0c0` | -0.012104 |
| `31c8c670-a48c-42c9-bc6c-fe9dc9cbcc1d` | -0.269726 |
| `3e703747-419a-4f7a-94c8-e3666f12318d` | -0.051767 |
| `3f8b4e94-4afc-4da5-8593-4512ed50adbd` | -0.036249 |
| `4770a504-8e77-49e7-939f-d3bdbb2f86e2` | -0.206819 |
| `4bb533b2-8c9d-411d-8088-e57789729100` | -0.113068 |
| `4d9cff14-7904-4265-a780-a70055907852` | -0.144904 |
| `4e682a2a-6916-46a5-a9b1-869bf7bd0dcc` | -0.158045 |
| `538a1799-34fc-4469-8c85-bb889fa1d1a2` | -0.116735 |
| `5c7e996d-eb4f-489c-9609-acdeca4a0026` | -0.087512 |
| `602c282f-3df6-40c0-9b30-724919df4f36` | -0.318147 |
| `694f4a35-443c-4537-835d-5080655528ca` | -0.207804 |
| `6b012e78-a1e9-449e-9282-6739f97abeed` | -0.020450 |
| `6b1c75b1-b748-4f8d-adc7-2443f222e6fa` | -2.153327 |
| `6d2375a4-071a-47a4-a73a-126016179c04` | -0.268547 |
| `79c63f36-b672-4ab7-aa91-0a54adb7e01a` | -0.059158 |
| `79c716df-6462-41ee-a395-69ac7cfec25c` | -0.001527 |
| `8277a574-e586-42a2-bc01-9b0156c7ccde` | -0.212724 |
| `85d6d672-a64f-403d-970e-6baf440dfcad` | -0.194356 |
| `864887aa-2614-4417-ba23-3112071bce99` | -0.138830 |
| `8e7d2309-b505-48f2-a64f-a8eb817de5b8` | -0.079467 |
| `90886918-edca-4c3c-b2f9-734986049d39` | -0.293569 |
| `94234e97-4cc1-4e9b-bd14-c2d0e2d178da` | -0.292616 |
| `ad60621e-58ca-46bd-ba96-cd7ab7bd58f5` | -0.050408 |
| `af52017e-bf99-4f27-a10e-838263acd25e` | -0.052850 |
| `b3e3d978-dcc9-456a-9d0a-857cd83305df` | -0.047402 |
| `b55831e0-5fae-483d-a79e-4f0210eb0696` | -0.002035 |
| `b5b40579-c7a8-432a-a6e8-45a5bdff1c26` | -0.766346 |
| `b867e94c-7094-4306-985a-c08001a415ae` | -0.019553 |
| `bf19f8d8-e10c-455d-aa19-f08adfc5cc4b` | -0.311317 |
| `c0346f5f-bdbb-412a-b1d4-3d92edc67daf` | -0.044523 |
| `c0683af9-2d9d-47e7-a156-e713e12c57c8` | -0.032932 |
| `c114c248-9c2a-40b9-818a-beb9701229f2` | -0.112159 |
| `c1802594-45b9-4733-8de6-d0c31bec3b24` | -0.197937 |
| `c5fb817b-426f-43f2-b99e-e7a33d1d4826` | -0.427180 |
| `c84719e4-24f5-4af0-a9dd-3dc1597699a4` | -1.270788 |
| `d46e991f-15c6-4339-bd6e-0d8fa3f7d6ad` | -0.098453 |
| `d5969d01-8647-4c8d-98a8-41db76922e9f` | -0.910108 |
| `d633a9ab-959f-482e-9731-aef2695d8b2c` | -0.567546 |
| `d6d4d62f-491a-4de0-adc7-097dea8a901d` | -0.104832 |
| `d737f502-7920-430e-a21c-d29f38be68b8` | -0.082585 |
| `deb9bb68-9f58-4834-b2d9-ea650269b675` | -0.015479 |
| `e27da202-a8e4-49b3-a359-ff2aaa007d0d` | -0.048008 |
| `e460b74d-20fe-4e63-b4a4-b7555d186c35` | -0.014372 |
| `e861498e-c88f-4dcd-be3a-15bf2bef473c` | -0.304967 |
| `ecd4fe26-1b43-49fb-984f-72b85538744f` | -0.012204 |
| `f10fac98-ea93-4fc1-8cda-24912aec4cb7` | -0.274060 |
| `f31c159c-f594-4b97-95b7-b6a89c49d206` | -0.266411 |
| `f71ebaac-ca31-40c9-a70b-b644b2f4bfeb` | -0.195319 |

**Review's conclusion, 2026-09-21: the digitised direction is the flow.** The evidence is
Lantmäteriet's own arrows: 62 of 63 agree under `bearing = 90 - rotation`, the ordinary
counterclockwise-from-east rotation of a map symbol. Review accepts the 98.41% fit among
the eight conventions as evidence for that direction. The endpoint-height test did not
resolve flow: it sampled the resampled z13 tiles, not native 1 m posts, and 210 of the 347
lines differ by at most a metre between their ends. A bilinear reading at that resolution
cannot settle which end of a 0.3 m fall is higher. Review reads the 61 apparent uphill
lines as a resolution effect, not contrary flow, and closes the direction question.

All class-2 lines are to run as digitised, without height-based reversals or exclusions.
This includes `ff1bf090-d2c9-45f3-a255-774f646002e8`, the one line with a 4.744 m fall and
an opposing arrow 37.952 m away. The figures above remain the measurement; this conclusion
supersedes the initial stop's interpretation of them.

**Code checked before the measurement.** `encoding._source_table` already writes the name
and kind together, as the plan says. The ferry sources, `graphs.edge_costs` and the inferred
connectors in `routing.graph._with_bridges` were read. Norway's current assembly adds N50
ferries; its page path loads N50 water and river surfaces before encoding. With this phase
stopped it would continue to do that, with no paddle sources or directed streams. N50's
stream size-class measurement belongs to the unstarted step 4 and remains open.

**Build figures:** shore/open-water/stream edge counts and km, portage chords, payload
bytes before/after and graph build seconds before/after were not measured. The requested
`command make graph ARGS="--park malingsbo-kloten"` and
`command make map ARGS="--park malingsbo-kloten"` are end-of-phase builds; neither was run
because step 1 stopped the phase. No other map was built and no browser state changed.
There is no demonstrated contradiction in the plan's source-table premise; the flow is the
unresolved measurement for which step 1 explicitly provides a stop.

Measurement scratch: `~/mockups/kayak-mode/phase1-flow.py` and `phase1-flow.json`. The JSON
holds every line's id, endpoints, heights, nearest arrow id, distance, rotation and local
bearing. It contains 347 rows, including all the disagreements above.

### Phase 1 resumed — The shared graph reverses digitised lines, 2026-09-21

With flow settled by review, inspection of the path a new source takes through the graph
found a separate obstacle to steps 4 and 6. `routing.chains.chains_of` sends even a
`keep_whole=True` source through `_assemble`, which calls `_canonical` on every line.
For an open chain, `_canonical` orders the endpoints lexicographically and reverses the
coordinates when necessary. Keeping a stream whole does not preserve its direction.

**Measured on the cached class-2 features:** 347 input features become 347 whole chains,
of which **101 have their coordinates reversed**. This check used the delivered features
over the same box in EPSG:3006, without clipping, and matched chains back to
`objektidentitet`. For example, `04ce645c-3a18-409c-a66c-388368d13c27` runs from
`(498572.5899963379, 6647589.303985596)` to `(498515.12899780273, 6647524.693969727)` in
the source; a single-source `build_network` with inferred bridges disabled returns an
edge with those endpoints reversed. The check read the cache and built in memory, under
an 8 GiB address-space limit; it saved no graph.

The edge's columns are `from_node`, `to_node`, `cost`, `source`, `kind`, `chain_id`,
`length_m`, `geometry` and `component`. `routing.graph._split_into_edges` constructs those
fields explicitly, and `_split_edges` constructs them again when an inferred connector
cuts an edge. Neither carries a one-way field or arbitrary chain attributes. Merely
marking every Streams edge one-way in `encoding.py` would make the reversed lines run
against the flow accepted by review.

**Stopped under the phase's wrong-premise rule.** The permitted files include neither
`libs/src/trails/routing/chains.py` nor `libs/src/trails/routing/graph.py`. Review must extend
the scope to preserve directed source geometry through chaining and carry direction
through both edge-splitting paths, or specify another intended integration. Recovering
discarded direction after graph construction was not substituted for that missing path.
The source table's existing kind encoding is correct; the obstacle is direction before
encoding. No water sources were added, and the end-of-phase graph and page builds remain
unrun. The earlier measurement and the review's flow decision are retained.

### Phase 1 built — The water sources and their direction, 2026-09-21

Review resolved the second stop by extending the scope to `routing/chains.py` and
`routing/graph.py`. `NetworkSource.directed` defaults to False and is True for Streams.
Canonicalisation still gives a chain its stable orientation; `flow_reversed` records
whether that opposes the supplied line. The edge builder restores the line's direction,
including its node endpoints, and sets `one_way=True`. Both noding and later connector
splits retain that direction. Undirected edges, including every walking source and
inferred connector, carry False. No change to `noding.py` or `topology.py` was needed.
The acceptance test supplies a reversed directed line crossed in the middle and asserts
both pieces' flags, geometry and node orientation; it runs with both whole-line and
junction-based chaining. Separate tests cover clipping and a later connector split.

**What the build adds.** `network/water.py` makes 10 m simplified exterior and interior
rings into Shore (PADDLE, factor 1), and contained, non-ring Delaunay edges into Open water
(PADDLE, starting factor 1.5 until phase 2). `topografi50.Source.streams()` and `dams()`
read the cached hydrography layers in the shape of `water()`. Class-2 streams keep their
digitised direction and lose the merged intervals 25 m either side of dam points or lock
gates within 25 m. The seventh opposing-arrow line stays directed as digitised too.

The source lists in `network/sweden.py` and `norway.py` add water beside the ferries.
Connected water pieces after the cuts receive one nearest-point chord per pair within
1,000 m, and their feet receive ties to the nearest walking node within 150 m. Both
Portages and Portage paths are BRIDGE sources at the existing inferred-connector factor
1.3. Their lines take part in shared noding, then leave the selectable chain table; their
edges have no chain id. The combined build stays in memory, reading the existing inputs
and height model without writing a graph into the shared cache. Ordinary cached walking
graphs acquire an all-False column when loaded.

`encoding.py` already carries each source's name and kind together; no second kind
column was added. It writes a byte per edge for direction, declared by the optional
`oneWay` header field. The decoder in `routing_graph.js` exposes `graph.oneWay`, and
supplies zeros for an older payload without the field. Its use by the router remains
phase 2. `route_graph.py` reports each generated source separately, and `lomsdal_visten.py`
prints the raw and base64 payload sizes. The browser's mode, routing and drawing code
have not changed in this phase.

**Malingsbo-Kloten, measured by the requested graph command.**

| source | edges after noding | km |
|---|---:|---:|
| Shore | 31,706 | 2,381.547 |
| Open water | 33,082 | 5,077.861 |
| Streams | 845 | 115.547 |
| Portages | 14,564 | 1,516.666 |
| Portage paths | 4,177 | 160.916 |

Before final clipping and noding there are 31,056 open-water chords, 5,082.673 km;
outlines and triangulation together take **2.509 s**. The water sources have **1,318
connected pieces**, joined by **2,942 portage chords**, 1,517.219 km, and **2,161 distinct
walking ties**. Final edge counts include cuts at every meeting with the other sources;
they are not counts of the original chords. The combined network holds **247,210 edges**
and **46,280 chains**, including 2,088 Shore, 31,043 Open water and 345 Streams chains.
All **3,960,895** height samples were read, with no missing values, at the existing 5 m
spacing from the 4 m height mosaic.

The same run builds the walking network first for the portage feet: **57.250 s and
153,481 edges**, compared with **96.217 s** for portages and combined noding. These times
measure graph construction; they exclude source loading, coverage, height sampling and
chain reporting. The combined measurement also excludes the separately timed 2.509 s
outline/triangulation step. The new build still needs the walking pass to locate the
portage feet: all three measured stages total **155.976 s**, compared with 57.250 s
for walking noding alone. The walking baseline is 12,804 chains and 153,481 edges,
matching the existing main-checkout page; the plan's 12,779 and 153,447 are an earlier
snapshot, not the baseline used for the byte comparison.

**Payload bytes, before and after.** The baseline is the already-built
`/home/eiseleu/repositories/trails/analysis/output/malingsbo-kloten.html`; the new page
comes from this worktree's successful map build. These are the graph stream's sizes,
excluding the JSON header and the rest of the page.

| representation | before | after | increase |
|---|---:|---:|---:|
| raw binary | 6,064,255 | 10,872,665 | 4,808,410 |
| gzip | 3,910,897 | 5,801,346 | 1,890,449 |
| base64 in the page | 5,214,532 | 7,735,128 | 2,520,596 |

For a map with no directed source, the sole binary change is the column of zeros.
Inserting 153,481 zeros into the old stream and recompressing at the encoder's gzip level
9 with timestamp 0 gives **5,215,540 base64 bytes**, an increase of **1,008 bytes**.
Recompressing the unchanged old stream reproduces its original bytes exactly. The
optional `,"oneWay":true` header marker adds **14 JSON bytes** separately. The complete
new HTML file is **25,823,174 bytes**.

**Validation and build conditions.** `command make graph ARGS="--park malingsbo-kloten"`
succeeded once. The first `command make map ARGS="--park malingsbo-kloten"` completed
its data work but stopped before encoding because this worktree had no tile-tree
manifest. A worktree-output symlink made the existing main-checkout `tiles/` tree visible;
the second map attempt succeeded. No tiles were built, no input was fetched, and neither
the shared input cache nor the main checkout's output tree was written. The second map
reproduced the report's counts; its walking and combined graph passes took 56.221 s and
93.687 s, with 2.255 s for water geometry. Both graph and map commands ran under an
8 GiB address-space limit. Most of the map's remaining time was the existing place-name
matching; it was not changed for this phase.

Firefox 153 decoded both payloads with the new decoder in fresh browser contexts with
network requests blocked. Every source flag was checked: **0 directed edges before,
845 after, all Streams**, and all other flags zero. All node references were valid, and
the full coordinate and height checksums matched in both cases. Decoder time was
**107 ms before, 198 ms after** in this run. No mode, goal or chosen way was changed.
`command make hooks-run` passed ruff formatting, ruff checking, mypy, the tests and the
remaining repository hooks. New tests cover the hydrography readers, shore and island
geometry, contained chords, dam cuts, portage distances and ties, directed splits,
boolean encoding and the combined build's reports without cache writes.

Abisko and Lomsdal-Visten were not built, as required. The earlier direction/scope
contradiction is resolved by review's extension; the different baseline counts and N50
sea-feature count are recorded here. No further phase-1 decision is pending. The N50
width correspondence and sea-height gaps remain prerequisites for later work on
Norwegian streams and water profiles; k and P remain phase 2's measurements.

Scratch and logs: `~/mockups/kayak-mode/phase1-graph.log`, `phase1-map.log` (the failed
attempt), `phase1-map-final.log`, `phase1-final-hooks.log`, `phase1-payload-before.py`
and its JSON, `phase1-payload-after.json`, `phase1-norway-sea.py` and its JSON, and
`phase1-decode.py` with `phase1-decode.json`. The flow scratch remains as recorded above.

**Norway, read and sampled without building its map.** The cached municipality 1813 N50
centreline layer contains 9,041 ElvBekk, 1,672 InnsjøMidtlinje, 461 ElvMidtlinje and 19
ElvelinjeFiktiv features. `vannbredde` is 2 on 8,086 lines, 3 on 955 and absent on 2,152.
The cached source and reader establish no equivalence to Topografi 50's class 2, so this
Sweden-only stream phase leaves Norwegian stream lines out. Its build path would add
Shore, Open water and inferred portages from the N50 surfaces. It would sample their
heights through the existing Høydedata point reader, which rejects bathymetric depths as
missing terrain heights; this phase has not measured the resulting sea-height gaps.
A full Norway build could request uncached height points and was not run.

The same delivery has **247 Havflate features**, rather than the plan's one sea polygon
per municipality. The most-vertex sea polygon has **12,440 vertices over 4.794716 km²**;
10 m simplification leaves **761 vertices**. Its triangulation has 2,115 edges, 1,523
contained edges including rings, and takes **0.050025 s** for simplification,
triangulation and containment. This sample gives no reason for extra chord-only thinning.
It is a sample of one cached municipality, not a Norway-wide performance claim.

### Phase 1b built — The 10 m ring stays, 2026-09-21

Review chose the 10 m shore ring. The rejected 25 m variant changed the bay by
16.152 m and the portage leg by 74.944 m paddled and 68.604 m on foot for
196,248 bytes brotli, 2.76 % of the page. `OPEN_WATER_SIMPLIFY_M`, the second
simplification and its experimental test are removed; triangulation again
uses the shore polygon directly. The comparison below remains the reason
for that decision, not an available build option. Neighbour portages, the
1 ha pond cutoff and the cached Norwegian mosaic remain as described below.

**Final graphs.** All three `command make graph ARGS="--park ..."` commands
completed from the final source files, offline and with the shared cache
protected against writes. These are noded, clipped edges and their lengths;
all use the 10 m ring and 1 ha cutoff.

| map | Shore: edges / km | Open water: edges / km | Streams: edges / km | Portages: edges / km | Portage paths: edges / km |
|---|---:|---:|---:|---:|---:|
| Abisko | 13,274 / 1,103.094 | 14,722 / 2,167.238 | 432 / 55.807 | 869 / 241.499 | 249 / 11.162 |
| Malingsbo-Kloten | 25,853 / 2,197.170 | 29,772 / 4,979.224 | 610 / 115.547 | 2,240 / 361.261 | 1,163 / 54.750 |
| Lomsdal-Visten | 42,872 / 3,893.366 | 53,952 / 9,523.616 | 0 / 0.000 | 1,473 / 477.587 | 440 / 18.863 |

Before noding and final clipping:

| map | connected pieces | open chords: count / km | portage chords: count / km | walking ties: count / km |
|---|---:|---:|---:|---:|
| Abisko | 455 | 14,366 / 2,171.915 | 567 / 241.577 | 136 / 11.162 |
| Malingsbo-Kloten | 728 | 29,178 / 4,984.034 | 807 / 361.683 | 793 / 54.811 |
| Lomsdal-Visten | 1,213 | 86,901 / 17,791.534 | 1,192 / 575.555 | 265 / 18.915 |

Portage-chord crossing pairs are **zero in all three maps**. Open-water
crossing pairs are 25, 0, 16, respectively, between the separate source surfaces.

The graph stream excludes the header and water grid:

| map | all edges | raw bytes | gzip bytes | base64 bytes |
|---|---:|---:|---:|---:|
| Abisko | 75,463 | 3,023,813 | 1,256,486 | 1,675,316 |
| Malingsbo-Kloten | 217,122 | 9,884,753 | 4,804,845 | 6,406,460 |
| Lomsdal-Visten | 339,136 | 13,240,036 | 5,085,146 | 6,780,196 |

**Final pages and sweep.** Abisko was rebuilt with `command make map`:
**4,680,792 HTML bytes, 1,817,282 brotli bytes**. Its water grid
has the same hash recorded below. Malingsbo-Kloten retains the completed 10 m
page: **24,500,988 HTML bytes, 7,117,583 brotli bytes**. Its fresh stand-alone
graph capture exactly matches that page build in every source count and km,
pre-noding chord count and km, crossing count, total edge count and payload-size
field. The removed branch already used this same shore polygon at 10 m; its
public sweep therefore remains the accepted measurement. At k = 1.5, P = 2,
bay and lake are 1,066.143 and 1,698.700 m paddled; the portage leg is 126.500 m
paddled and 1,152.330 m on foot, with mapped paths. That sweep restored all
page state, as recorded below. No page code changed and no Norway map was built.

**The final Norway build meets the memory limit.** It exited zero in
**793.010 s**, peaking at **4,402,920 KiB RSS (4.198952 GiB)**
under the inherited 8 GiB address-space limit. It read **4,251,682 samples**
from the cached 4 m mosaic, none outside it. No point-service request or cache
write occurred. As in the comparison, `/usr/bin/time` is absent, so the wrapper
uses `resource.getrusage(RUSAGE_CHILDREN)` for the kernel peak. The 982 lake
bodies comprise 980 registered and two shore-percentile levels; the independent
register/p10 absolute difference is median 0.334448 m and maximum 27.442316 m.
The earlier 600-point walking comparison still measures the same mosaic reader.

**Files and validation.** `network/water.py` bounds the paddle sources and
portages while preserving the original chord ring. `network/norway.py` and
`io/sources/hoydedata_dtm.py` read the whole network from cached ground, with
lake and sea levels applied afterwards. Their three test files cover the
geometry, pond boundary, shared reader, independent lake percentile and sea
zero. `command make hooks-run` is green after removing the variant: formatting,
lint, mypy, both test suites and repository hooks. Section 4 closes the byte
question with review's decision; no further decision remains for this phase.

Final logs, captures and timings are in `~/mockups/kayak-mode/phase1b/accepted/`:
`abisko-10`, `mk-10` and `norway-10` have `.log`, `.time` and `.graph.json`;
`abisko-10-map` also has `.html` and `.bytes.json`. `hooks.log` is the green
run. The Malingsbo-Kloten page, byte report and restored public sweep remain
in `final/mk-10-1.*`. These final figures supersede the experimental build
figures in the historical stop notes below. No tiles were built, no shared
inputs or main-checkout HTML were changed, and nothing was pushed.

### Phase 1b resumed — Measured, stopped at the changed 25 m ways, 2026-09-21

**Review settled the height reader and the smallest paddled water.** Norway's
whole network now reads the cached 4 m DTM, including walking and portage edges.
`hoydedata_dtm.heights_over()` holds one mosaic and samples every non-ferry edge
in one call, at the existing 5 m spacing. A missing square fails before assembly;
the reader neither fetches nor writes an assembled mosaic. The point reader
remains available to other callers. Norway's graph-cache layout changes with
its height source, so an old walking graph cannot silently retain point heights.
The temporary Terrarium reader described in the stop below was removed.

Registered lake levels still override the raw reading, and the shore's p10 is
again an independent comparison against that register. Unregistered lakes take
the p10; river surfaces retain their sampled profile; Havflate edges and chains
are flat at zero. `MIN_PADDLE_HA = 1.0` excludes each smaller input polygon part
before body grouping and simplification. It produces no shore, chord or portage
destination. The input water frame, and hence the water-pricing grid, is intact.

Portage neighbours are Delaunay neighbours of one point per connected piece:
the shore point nearest that piece's bounding-box centre, with stream lines for
a stream-only piece. It remains on the piece around islands and does not depend
on chord density. Chords join the nearest points within 1,000 m and refuse any
third piece; the existing walking ties are unchanged. Only closed **shore** rings
fill water for that rejection: a closed river loop does not turn its enclosed
land into a lake. Auditing that distinction changed zero portage geometries in
both Swedish maps, with and without the pond cutoff, and in the 10 m comparison.
Norway has no stream source. Open-water chords use retained vertices of a 25 m
simplification of the 10 m shore, so their ends already meet shore vertices.

**Walking heights against the cached point answers.** From 1,000 evenly spaced
walking edges in the cached graph, 996 midpoint samples had finite cached point
answers; 600 evenly spaced members of that set were compared at the point
store's exact rounded EPSG:25833 coordinates. They cover FKB (206), UT.no (120),
N50 paths (114), Turrutebasen (68), OSM (63) and N50 roads (29). No mosaic answer
is missing. Absolute differences have median **0.087187 m**, p95 **0.718050 m**
and maximum **4.898592 m**; signed median is +0.018642 m and RMSE 0.468174 m.
The largest difference is at E 415274.84, N 7255207.03: point 771.78 m, mosaic
766.881408 m. This supports close agreement for most samples, not byte-identical
walking profiles or a sub-metre bound everywhere. `final/agreement.json` retains
every reading and the cached graph's identity.

**All three graphs, with and without the pond cutoff.** These are normal
`command make graph ARGS="--park ..."` builds, using 25 m chord rings.
Edges and km below are after noding and final clipping; a zero cutoff retains
ponds. Streams keep their geometry: their changed edge counts reflect noding.

| map | source | no cutoff: edges / km | 1 ha: edges / km |
|---|---|---:|---:|
| Abisko | Shore | 14,772 / 1,414.461 | 8,420 / 1,103.094 |
| Abisko | Open water | 11,306 / 1,767.040 | 8,825 / 1,622.760 |
| Abisko | Streams | 462 / 55.807 | 433 / 55.807 |
| Abisko | Portages | 4,561 / 1,203.504 | 868 / 241.499 |
| Abisko | Portage paths | 1,128 / 45.509 | 242 / 11.162 |
| Malingsbo-Kloten | Shore | 19,631 / 2,381.547 | 16,073 / 2,197.170 |
| Malingsbo-Kloten | Open water | 19,511 / 3,718.293 | 17,901 / 3,631.696 |
| Malingsbo-Kloten | Streams | 646 / 115.547 | 609 / 115.547 |
| Malingsbo-Kloten | Portages | 4,694 / 781.635 | 2,241 / 361.264 |
| Malingsbo-Kloten | Portage paths | 2,616 / 118.795 | 1,176 / 54.750 |
| Lomsdal-Visten | Shore | 100,045 / 6,002.642 | 26,260 / 3,893.366 |
| Lomsdal-Visten | Open water | 46,763 / 7,341.739 | 30,579 / 6,734.736 |
| Lomsdal-Visten | Streams | 0 / 0.000 | 0 / 0.000 |
| Lomsdal-Visten | Portages | 52,729 / 12,312.100 | 1,473 / 477.587 |
| Lomsdal-Visten | Portage paths | 10,327 / 347.006 | 421 / 18.863 |

Before noding and final clipping, counts and km are:

| map | minimum ha | connected pieces | open chords: count / km | portage chords: count / km | walking ties: count / km |
|---|---:|---:|---:|---:|---:|
| Abisko | 0 | 1,639 | 10,657 / 1,770.263 | 3,279 / 1,206.736 | 577 / 45.591 |
| Abisko | 1 | 454 | 8,495 / 1,625.929 | 566 / 241.576 | 136 / 11.162 |
| Malingsbo-Kloten | 0 | 1,319 | 18,636 / 3,721.359 | 1,766 / 782.167 | 1,576 / 119.056 |
| Malingsbo-Kloten | 1 | 729 | 17,306 / 3,634.761 | 808 / 361.685 | 793 / 54.811 |
| Lomsdal-Visten | 0 | 21,507 | 67,558 / 13,787.514 | 55,401 / 15,280.647 | 4,715 / 348.057 |
| Lomsdal-Visten | 1 | 1,213 | 50,960 / 13,042.479 | 1,192 / 575.555 | 265 / 18.915 |

With ponds retained, portage-chord crossing pairs are 2, 4 and 47 respectively;
**with the cutoff they are zero in all three maps**. Open-water crossing pairs
are 10, 0 and 4 at either cutoff, from the separate input surfaces. The much
larger Norwegian pre-clipping chord totals must not be compared directly with
the clipped edge lengths above.

The graph stream, excluding the header and water grid, measures:

| map | minimum ha | all edges | raw bytes | gzip bytes | base64 bytes |
|---|---:|---:|---:|---:|---:|
| Abisko | 0 | 80,116 | 3,316,822 | 1,570,303 | 2,093,740 |
| Abisko | 1 | 64,652 | 2,570,362 | 1,145,012 | 1,526,684 |
| Malingsbo-Kloten | 0 | 206,660 | 9,350,969 | 4,837,168 | 6,449,560 |
| Malingsbo-Kloten | 1 | 195,430 | 8,913,341 | 4,607,785 | 6,143,716 |
| Lomsdal-Visten | 0 | 472,831 | 19,841,234 | 9,791,049 | 13,054,732 |
| Lomsdal-Visten | 1 | 298,571 | 11,338,484 | 4,709,783 | 6,279,712 |

**Norway completed offline under the memory limit.** The filtered graph command
exited zero in **721.919 s**, with peak **4,192,876 KiB RSS (3.998638 GiB)**.
It read **3,672,583 samples**, none outside the mosaic. Without the cutoff it
also exited zero: **1,075.367 s**, **5,151,628 KiB (4.912975 GiB)**, and
**6,791,639 samples**, none outside. Both ran with
`resource.setrlimit(RLIMIT_AS, (8 * 1024**3,) * 2)`, socket access blocked and
shared-cache writes blocked. `/usr/bin/time` is absent; `timed.py` records the
kernel's child peak through `resource.getrusage(RUSAGE_CHILDREN)`, rather than
claiming a `/usr/bin/time -v` run. Neither completed run needed a further
allocation-profile investigation.

The network box needs 90 of the 104 cached squares: a 22,500 × 25,000 float32
mosaic, 2.095476 GiB. Assembly fills the existing model's 38,356,989 NODATA posts
with sea zero, as the tile-build reader already did. With the cutoff, 982 lake
bodies are levelled: 980 registered and two from shore p10. Registered level
against independent raw shore p10 has median absolute difference 0.335685 m,
maximum 27.467468 m. Without the cutoff there are 17,035 bodies, 16,952 registered
and 83 p10; median difference 0.325567 m, maximum 40.171317 m. The registered
level keeps priority as decided; these are measured discrepancies, not silently
replaced register values. No Norway map was built.

**The two Swedish pages.** Each is a completed `command make map` build from
this worktree, with cached tiles and inputs. Brotli is quality 11 over the HTML.
The cutoff comparisons use the 25 m chord ring; the final row supplies the
10 m baseline with the same neighbour and pond rules.

| map | ring m | minimum ha | HTML bytes | brotli bytes |
|---|---:|---:|---:|---:|
| Abisko | 25 | 0 | 5,099,335 | 2,133,519 |
| Abisko | 25 | 1 | 4,532,159 | 1,707,346 |
| Malingsbo-Kloten | 25 | 0 | 24,544,246 | 7,150,276 |
| Malingsbo-Kloten | 25 | 1 | 24,238,249 | 6,921,335 |
| Malingsbo-Kloten | 10 | 1 | 24,500,988 | 7,117,583 |

The decoded water-grid JSON is byte-identical across each map's variants:
SHA-256 `2cbda1e3280bc020d6962f74e30ecf9431aaf771a757494733f8668115e1df54`
for Abisko and `7a5813a14e14fe372834095043c7f26cc864a6885921e17d88a2ed9ab2beccc7`
for Malingsbo-Kloten. Ponds therefore still price a straight leg as water.

**The 10 m / 25 m comparison.** Both have the 1 ha cutoff and the same shore
geometry. Counts below are open-water chords before noding and clipping;
bytes are the graph stream without its header or grid.

| ring m | open chords | km | all graph edges | raw bytes | gzip bytes | base64 bytes |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 29,178 | 4,984.034 | 217,122 | 9,884,753 | 4,804,845 | 6,406,460 |
| 25 | 17,306 | 3,634.761 | 195,430 | 8,913,341 | 4,607,785 | 6,143,716 |

At 10 m the noded sources are Shore 25,853 / 2,197.170 km, Open water
29,772 / 4,979.224 km, Streams 610 / 115.547 km, Portages 2,240 / 361.261 km,
and Portage paths 1,163 / 54.750 km. Before noding there are 728 connected
pieces, 807 portage chords / 361.683 km and 793 ties / 54.811 km; portage
crossing pairs are zero. The 25 m figures are in the tables above.

**The required stop: the three public answers are not all the same.** The
existing phase-2 public sweep and harness were adapted to these built pages,
using the recorded coordinates instead of obsolete graph node ids. The tally
reads phase 3's `crossed` figure directly, without adding source credits a
second time. All 36 ways settled at each spacing, and all path/no-path choices
agree. However, lengths change for every bay and portage case: 24 of 36 answers.
The lake's lengths agree in all 12 cases. At the accepted k = 1.5, P = 2:

| leg | 10 m: paddled / foot m | 25 m: paddled / foot m | mapped path, both |
|---|---:|---:|---|
| bay | 1,066.143 / 0 | 1,049.992 / 0 | no |
| lake | 1,698.700 / 0 | 1,698.700 / 0 | no |
| portage | 126.500 / 1,152.330 | 51.555 / 1,220.934 | yes |

The bay changes from 345.209 m Shore + 720.934 m Open water to 123.919 +
926.073 m. The portage leg's drawn-path credits change from 9.361 m Topografi
50 paths + 306.508 m OSM to 1,009.381 m OSM. These are different ways, not only
rounding differences. The 10 m portage also differs from phase 2's old all-pairs,
all-pond graph; that change belongs to the newly decided neighbour and pond
rules, which both ring comparisons share.

The instruction says to stop if those three answers differ. No tolerance or
permission to accept the changed 25 m ways has been inferred. Review must
choose whether to keep 10 m or accept these changed ways at 25 m. The current
worktree's 25 m constant is experimental and **uncommitted**; neither a silent
reversion nor a commit declaring it accepted was made.

**Validation and artifacts.** `command make hooks-run` is green after the last
code change: ruff format/check, mypy, both test suites and the standard hooks.
Tests cover neighbour selection, third-lake rejection without filling a river
loop, retained shore endpoints, the pond threshold, cache-only mosaic reads,
all network samples going to that mosaic, independent lake p10 and sea zero.
Both browser sweeps restored the prices, switches, plan, goal and chosen way;
the harness's before/after assertions passed. All external browser requests
were blocked. Shared inputs were read without writes; main-checkout HTML was
neither read nor written. No tiles were built or data fetched, and nothing was
pushed.

The files in `~/mockups/kayak-mode/phase1b/final/` retain the graph captures,
page snapshots, byte reports and sweeps. Prefixes are `abisko-25-{0,1}`,
`mk-25-{0,1}`, `mk-10-1` and `norway-25-{0,1}`; Swedish stand-alone graph captures
add `-graph`. `agreement.json` holds every walking-height comparison;
`chord-audit.log` confirms the river-loop correction leaves measured chords
unchanged; `hooks-final.log` is the green run. The original completed filtered
Norway timing is `norway-25-1.completed.time`: a scratch-runner edit inadvertently
restarted that command and its duplicate was cancelled after the original had
completed, truncating the original log. The original full graph capture and
completed timing are retained. The unfiltered Norway command's log and timing
are intact. `mk-25-0-graph.completed.time` likewise preserves its original
completed graph timing; its duplicate was cancelled. The page measurements
come from the completed, isolated output directories, never a main-checkout
page.

### Phase 1b — Stopped at Norway's non-water height samples, 2026-09-21

Review extended the phase after the graph command was found to invoke the same
height service as the map. The decision keeps Norway's walking reader and takes
water heights from the body's lowest registered N50 level, otherwise the built
DEM for lakes and river surfaces, and zero for the sea. The built tree is
`/home/eiseleu/repositories/trails/analysis/output/dem/kartverket/1/`, with zoom 13
as its finest level. It was inspected read-only; no Norway map was built.

**The implementation in the worktree.** `network/water.py` selects portage pairs
from a Delaunay triangulation, using the point on each piece's shore nearest
its own bounding-box centre. This point stays on its piece around islands and
its position does not depend on the density of open-water chords. Stream-only
pieces use their lines. Chords still join the nearest points within 1,000 m,
refuse a third water piece, and retain the existing walking-node ties. The
third-piece check includes areas enclosed by shore rings, with holes, so a
line wholly inside a third lake cannot escape a boundary-intersection test.

The open-water triangulation uses a further 25 m simplification of the 10 m
shore. Its vertices are retained shore vertices, so the chord ends already
meet the shore; no shore vertex is moved. The 10 m comparison uses the original
10 m ring directly. The 25 m setting is experimental until the public sweep
has completed and review accepts its answers.

Water chains retain their surface class. `network/norway.py` measures the
non-water and water subsets separately, preserving the original service reader
for the former. Registered lakes and the sea supply constant sample heights;
remaining water samples go to `processing/dem_tiles.sample()`, a bilinear reader
that handles tile boundaries, reads one decoded image at a time, and returns
NaN for absent tiles or missing posts. All use the existing sample-spacing
parameter, 5 m by default. The existing lake-body levelling then applies the
shore's 10th percentile to unregistered lakes. Registered shores are already
at their assigned level in this path, so their later percentile is not an
independent comparison with the register.

**The new stop, measured rather than inferred.**
`command make graph ARGS="--park lomsdal-visten"` ran under an 8 GiB address-space
limit with socket access and writes into the shared input cache blocked. Noding
completed, but the non-water height pass requested **4,040,910 samples at
3,558,126 distinct coordinates**. Only **883,391** coordinates were cached;
**2,674,735** were missing. `hoydedata.Source.elevations()` reached `_fetch()`
and the offline guard stopped its first connection attempt. No request was
sent and no cache write occurred. The water subset had not yet been measured.
These are non-PADDLE samples: inferred portages and walking edges belong to
this subset. The run does not establish the missing count for each source.

Review must decide how uncached non-water samples are read offline. Merely
removing water samples from the height service does not make the full graph
cache-complete. No fallback, fetch permission, or change to walking heights
has been inferred from the water-height decision.

Norway reached **472,831 edges**, with the following geometry figures before
heights:

| source | edges after noding | km |
|---|---:|---:|
| Shore | 100,045 | 6,002.642 |
| Open water | 46,763 | 7,341.739 |
| Streams | 0 | 0.000 |
| Portages | 52,729 | 12,312.100 |
| Portage paths | 10,327 | 347.006 |

Before final clipping and noding: **67,558 open-water chords / 13,787.514 km**,
**21,507 connected water pieces**, **55,401 portage chords / 15,280.647 km**,
and **4,715 walking ties**. Water geometry took 14.983 s, the walking graph
175.007 s, and portages plus combined noding 317.407 s. The stopped command ran
680.895 s and peaked at **2,146,932 KiB RSS (2.048 GiB)**. `/usr/bin/time` is
absent on this machine; the wrapper used `resource.getrusage(RUSAGE_CHILDREN)`
for peak RSS and `resource.setrlimit(RLIMIT_AS, (8 * 1024**3,) * 2)` for the
limit. This is a peak for the failed command, not a completed-build memory
acceptance measurement. No allocation-profile conclusion is claimed.

**Malingsbo-Kloten's completed 10 m graph within its interrupted map build.**
The neighbour rule gives **1,765 portage chords / 782.165 km**, with **four
crossing pairs** before noding, and **1,576 walking ties / 119.056 km**. Its
**31,056 open-water chords / 5,082.673 km** reproduce the phase-1 ring. The
combined graph has **229,532 edges** and the following source totals:

| source | edges after noding | km |
|---|---:|---:|
| Shore | 29,953 | 2,381.547 |
| Open water | 31,965 | 5,077.861 |
| Streams | 647 | 115.547 |
| Portages | 4,693 | 781.633 |
| Portage paths | 2,623 | 118.795 |

The graph stream measures **10,359,633 raw bytes**, **5,046,461 gzip bytes**,
and **6,728,616 base64 bytes**, excluding its header. The water geometry and
height pass completed; the map was still matching place names when Norway's
failure required the stop. Its page bytes and public sweep are unmeasured.
The separate 25 m Malingsbo-Kloten graph was stopped during combined noding.
Its water geometry took 1.713 s: 18,636 open-water chords / 3,721.359 km.
Its walking pass completed in 55.296 s; it had 1,319 connected water pieces,
1,766 portage chords / 782.167 km, and 1,576 walking ties. Abisko was not started. An earlier 10 m attempt was discarded
before completion after finding that simplifying the ring twice changed the
baseline; only the corrected run's figures are reported here.

**Validation and remaining work.** `command make hooks-run` is green: formatting,
lint, mypy, both test suites and the remaining repository hooks. Added tests
cover the coarser chord endpoints, neighbour pairs and third-lake rejection,
unchanged walking ties, tile-boundary interpolation and missing heights, and
a service spy that refuses every water coordinate. The page was never driven,
so no mode, goal or chosen way changed. No shared-cache file or main-checkout
HTML was written or read. The implementation remains uncommitted at this stop;
the 25 m sweep, both Swedish page-brotli measurements, Abisko's graph, Norway's
completed height pass and payload, and the phase commit remain outstanding.

Scratch, guards and logs are in `~/mockups/kayak-mode/phase1b/`:
`norway-graph.log`, `norway-graph.time`, `mk-10-map.log`, `mk-10-graph.json`,
`mk-25-graph.log`, `hooks.log`, `sitecustomize.py`, `timed.py`, and the prepared
`browser.py`, `sweep.js` and `bytes.py`. All build commands used the worktree's
source files; the browser harness has not run.

## 6. How the figures here were obtained

Scratch in `~/mockups/kayak-mode/`: `measure-water.py` reads the water surfaces through
`topografi50.Source.water` and the `hydrolinje` layer of the cached `hydrografi` GeoPackage
by box, counts them, simplifies the outlines at 5, 10 and 25 m, and joins them into bodies
and systems with an STRtree; `measure-water-2.py` the shoreline length, the size classes and
the largest lakes; `canoe-osm.py` the Overpass query and `canoe-osm.json` its answer; `register-canoe.py` the register's trails by type and its facilities by type and subtype over the box, through `naturvardsregistret.Source`; the overview map PDF beside them. Run
from the `trails` checkout with `mise exec -- uv run python <script>`.


### Phase 2 built — The switch and the prices, 2026-09-21

**The tally stop, resolved by review.** The first public `trailsPlan.fromPlaces()` checks
failed on all three legs: `tallyEdge()` required a walking waymarking state from PADDLE
edges, whose state is correctly null. The bay failed on Shore edge 159535, the lake on
160145 and the portage on 157030. Review decided that PADDLE keeps its source credit,
counts no marking bucket and is never asked about waymarking. Unlike a ferry, it counts
its protected area: paddling inside a reserve is inside the reserve. That rule now lets
all three public ways assemble. Parts, heights and words remain phase 3's; the current
`routedParts()` format is retained as review explicitly allowed.

**What changed.** `plan_mode.js` adds the persisted kayak setting, prices,
the shared direction predicate for both searches and partial edges, and the cheapest
connector metre. Both arcs remain. The cost table is dropped on a mode change. Snapping
also checks node eligibility: skipping water edges alone still left their nodes and
portage feet snappable. `profile_panel.js` adds the Kayak switch beside Stay on paths;
its face follows the API, clicks and a reload. The reload check caught and fixed a saved
mode whose face initially said off. `maps.py` requires and documents `paddleKind` and
`portageFactor`; `lomsdal_visten.py` supplies them, with `PORTAGE_FACTOR` beside
`WATER_FACTOR`, as review authorised after the settings-location stop. The comment on
`water.py`'s unchanged `OPEN_WATER_FACTOR = 1.5` records the sweep and phase 5 rebuild.
Tests cover direction, cuts, exclusion, the floor, price invalidation, the flat ferry
and the different protection and marking rules for paddling and ferries.

**One build, then Firefox 153, entirely offline.**
`command make map ARGS="--park malingsbo-kloten"` succeeded under an 8 GiB address-space
limit. The graph reproduces phase 1's 247,210 edges and all five water/portage counts;
its payload is 10,872,665 raw bytes and 7,735,128 base64 bytes. No input was fetched or
rewritten, and no tiles were built. The browser harness serves the current planner script
against that one built graph, including the switch repaint fixes made after the build.
It patches the Open water header factor, sets `PLAN.portageFactor`, and drops the cost
table for each pair of prices. The generated HTML still has the build's starting P = 4;
the source setting is now 2. No second graph or map build was run.

The scratch is `~/mockups/kayak-mode/phase2-browser.py`, `phase2-measure.js`,
`phase2-sweep.js` and `phase2-sweep.json`. Candidate searches and a water-grid drawing
(`phase2-shapes.png`) establish the three shapes. The sweep measures the production
`routeBetween()` search and `worthRouting()` comparison, classifying routed metres by
source kind and direct connectors by the water grid. The first run measured searches and exposed the tally failure above. After its
resolution, `phase2-public-sweep.js` reads each assembled way through `trailsPlan.state()`: water
is `crossed` plus the Shore, Open water and Streams source credits, and foot is
`walked + crossed - water`. This uses the public figures without assuming phase 3
part semantics: a paddled routed part still contributes to `walked` today. Five warm searches per leg and price
pair give the median time; Firefox returned whole milliseconds here, so `<1` means a
zero-millisecond reading. Cost-table construction is separate, 55–83 ms across the sweep.

Coordinates below are latitude, longitude (WGS84), in journey order:

- **Bay:** (59.844846, 15.546195) to (59.852644, 15.540811), across the mouth of a deep
  indentation (nodes 90942, 90853).
- **Lake:** (59.887213, 15.675327) to (59.893952, 15.653105), along opposite sides of a
  narrowing lake (nodes 91519, 91537).
- **Portage:** (59.821858, 15.502671) to (59.824603, 15.518341), two lake shores with a
  mapped OSM path beside the straight portage (nodes 88561, 88582).

Each cell is **water m / foot m / path taken / search ms**, rounded to whole metres.
The lengths and path choice are the public assembled figures for all 36 ways; the times
are the warm search medians above. All 36 settled without failures. Their total lengths
and path choices match the search sweep. At k = 1.2 the lake's direct line reports
1,438.043 m over water and 15.032 m on foot: `straightParts()` classifies its laid samples,
whereas `priced()` samples cell midpoints and prices the entire 1,453.075 m as water.
That existing sampling difference is retained for phase 3; the accepted k = 1.5 ways
agree in both classifications. `phase2-public-sweep.json` holds the public states.

| k | P | Bay | Lake | Portage |
|---:|---:|---|---|---|
| 1.2 | 2 | 1066 / 0 / no / <1 | 1438 / 15 / no / <1 | 43 / 929 / yes / <1 |
| 1.2 | 4 | 1066 / 0 / no / <1 | 1438 / 15 / no / <1 | 75 / 903 / yes / 1 |
| 1.2 | 8 | 1066 / 0 / no / <1 | 1438 / 15 / no / <1 | 1679 / 573 / no / <1 |
| 1.5 | 2 | 1066 / 0 / no / <1 | 1699 / 0 / no / <1 | 43 / 929 / yes / 1 |
| 1.5 | 4 | 1066 / 0 / no / <1 | 1699 / 0 / no / <1 | 75 / 903 / yes / 1 |
| 1.5 | 8 | 1066 / 0 / no / <1 | 1699 / 0 / no / <1 | 1831 / 573 / no / <1 |
| 2 | 2 | 1066 / 0 / no / <1 | 1699 / 0 / no / <1 | 43 / 929 / yes / 1 |
| 2 | 4 | 1066 / 0 / no / <1 | 1699 / 0 / no / <1 | 75 / 903 / yes / <1 |
| 2 | 8 | 1066 / 0 / no / <1 | 1699 / 0 / no / <1 | 1930 / 573 / no / <1 |
| 3 | 2 | 1883 / 0 / no / <1 | 2424 / 0 / no / <1 | 43 / 929 / yes / <1 |
| 3 | 4 | 1883 / 0 / no / <1 | 2424 / 0 / no / <1 | 75 / 903 / yes / 1 |
| 3 | 8 | 1883 / 0 / no / <1 | 2424 / 0 / no / <1 | 2218 / 573 / no / 1 |

**The figures the searches favour: k = 1.5, P = 2.** At 1.2 the lake leg takes the direct
1,453 m direct line (1,438 m water and 15 m foot in the assembled way). At 1.5 it takes 1,058 m of shore and 641 m of open water; at 2 the answer
is unchanged, while 3 sends it 2,424 m along the shore. The bay still cuts across at 1.5
(345 m of shore and 721 m of open water); 3 makes it 1,883 m. Two is the first tested
portage factor and keeps 222 m of mapped path in 929 m on foot, with 43 m over water.
Four saves 26 m on foot but leaves just 26 m of that path, replacing it with more undrawn
ground. Eight goes 1,831 m by water to carry 573 m and takes none of the path. The three
legs support 1.5 and 2; they are not a measurement over every lake or a published claim
about a usable landing.

A point placed out on the lake at (59.8905825, 15.664216), from the lake leg's first
point, stays unsnapped at a 1 m reach. The search takes 775.344 m of shore then a straight
138.196 m water connector to that point, 913.541 m altogether. It therefore reaches the
reader's point without forcing it onto a chord or the shore.

**The three amended mechanisms, measured at k = 1.5 and P = 2.**
`phase2-finalchecks.json` retains the initial readings and public failures;
`phase2-accepted.json` repeats the mechanisms and records the three assembled public ways.

- **Direction in both searches:** Streams edge 220673 goes from
  (59.894038, 15.589986) to (59.885045, 15.606262), 2,786.468 m. Both forward and backward
  searches take that edge downstream. Upstream, both refuse that traversal and find a
  legal alternative: 1,522.652 m on other Streams edges and 2,163.113 m on foot, with
  zero reversed one-way edges. Refused upstream does not mean the destination is
  unreachable by a portage.
- **An interior point:** at (59.887684686, 15.597335455), halfway along that edge, the only
  exit is node 118644 and the only entry is node 118645. The downstream half is
  1,393.234 m. The upstream half cannot be taken as a stream cut; the final comparison
  chooses an 818.723 m ground connector instead.
- **The connector floor:** from (59.961390, 15.2411587) to
  (59.973214, 15.2564763), both unsnapped water points, the corrected search finds
  1,652.945 m over water at a price of 1,959.099 equivalent metres. Restoring only the
  old `distance * offPath()` floor loses that answer and takes the 1,570.781 m direct
  crossing at a price of 2,356.172. The corrected search took 18 ms and the old one 12 ms
  in the final comparison; the old answer's lower elapsed time is incorrect pruning.

**Walking exclusion and state restoration.** In each walking setting, all **65,633**
PADDLE edges have infinite cost; midpoint segment queries produce **zero** PADDLE snaps,
and `endsOf()` produces **zero** water-edge ends. Ten additional taps exactly on nodes
ineligible for walking remain unsnapped in each setting. These are the decoded graph's
edges, not a fixture (`phase2-mechanisms.json`). API toggles, both switch clicks and reload
retain the correct mode and switch face (`phase2-ui.json`). The final scripts restore k,
P, both switches, the goal and its chosen way, and the empty plan. Public plans are undone
and plan mode is returned to its original state. The restoration comparison ignores only
the computed spatial-index statistics and the cumulative height-request counter; NaN
figure values are compared through JSON. The public sweep made two height requests and
its original comparison failed solely on that counter (0 to 2). Inspection of the saved
before/after states confirms all user state was restored; the harness now excludes that
counter as well.

**The plan's corrected premises.** Removing the reverse arc cannot serve the forward and
backward searches together. Direction therefore belongs to the step predicate, including
partial edges. A point on a stream supplies an entry and an exit, not a junction in both
directions. A ground-price floor can prune a cheaper water connector, so its floor and
water price now read the same Open water header factor. Settings live in
`lomsdal_visten.plan_settings()`, not as defaults in `maps.py`. Finally, phase 2 needed
the explicit tally rule above to assemble a way before phase 3 changes its parts.
Review resolved each of these; no further price or scope decision remains.

**Validation.** `command make hooks-run` is green: ruff format, ruff check, mypy,
both test suites and the standard repository hooks. All seven executable JavaScript
routing and tally regressions passed on the first run. One existing rendered-source
assertion still expected only the ferry and connector declaration; adding the new
PADDLE declaration to its expectation made the full rerun green. The phase stops here;
no phase 3 parts, heights or words were changed, and nothing was pushed.

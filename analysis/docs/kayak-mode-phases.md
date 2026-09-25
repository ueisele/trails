# The kayak mode, in phases

*Drafted 2026-09-21. Status: **§1 decided by Uwe the same day, as proposed.** The built-notes of
each phase are recorded under the phase; the decisions and the measurements live on in
`kayak-mode-decisions.md`.*

A third way of planning beside walking and staying on paths: the water is the way and the land
is the portage. Asked for by Uwe on 2026-09-20 while the third map was being built and taken up
on 2026-09-21 once he had called that map done (`malingsbo-kloten-phases.md` §5,
`malingsbo-kloten-decisions.md` §6). The three maps keep everything they have; a reader who
never switches the mode on sees nothing change, to the byte where the drive can read one.

## 1. Decided

*Uwe's word, 2026-09-21, the four points as proposed.*

1. **One price rule, not four cases.** Uwe's description — *follow the shore by default; cross
   where the crossing is shortest; straight across only where I put a point; over land the
   kayak is carried, so the shortest way, and the path where there is one* — is what falls out
   of the router the page already has once its prices are turned round. An edge costs its
   metres times a factor; a connector off the network costs what it crosses, by the water
   grid. In the kayak mode a metre along the shore costs 1, a metre of open water costs **k**
   (a little over 1), a metre of land costs the walking price times **P**, and a metre on a
   path costs P alone. So the shore is followed as long as no bay is deeper than its mouth is
   wide, a bay deeper than that is cut across, a point set out on the lake is reached by the
   straight connector, and a portage takes the path when the path is cheaper than the ground
   — exactly the trade the *Stay on paths* switch already makes at ten to one. Nothing of
   the walking modes is rebuilt; the kayak mode is the third setting of the same machinery.
2. **Rivers: the narrow ones as lines, class 2 only, downstream only, cut at dams and locks.**
   Lakes and the rivers wide enough to be drawn as a surface are the water grid's already.
   Topografi 50 draws the rest as lines in two size classes; class 2 is 347 lines and 118 km
   in the Malingsbo-Kloten box (Hedströmmen's kind), class 1 is 6,362 lines and 3,359 km of
   brooks and ditches. Class 2 goes in, as a way that runs one way: with the flow, which a
   kayak can take and against which it cannot. A dam or a lock gate on the line (Topografi
   50's `hydroanlaggningspunkt`: 97 dam points and 11 lock gates in the box) cuts the water
   way there; the metres either side are a portage.
3. **k and P are measured, not chosen.** Swept in a browser over three legs on the
   Malingsbo-Kloten page — a bay to cut or to follow, a lake to cross or to skirt, a portage
   between two lakes with a path beside the straight line — the way `WATER_FACTOR` was swept
   (`lomsdal_visten.py`, the comment above it). Starting figures 1.5 and 4. The record carries
   the sweep and the two figures it settles on.

   *Phase 8 superseded the measured P = 2 trade-off: land metres decide first. Uwe's
   phase-10 decision restores "the path where there is one" under water-first by
   minimizing land price. His revised decision makes ground follow Stay on paths:
   3 off, 10 on. P = 2 remains only in the secondary price. The phase-10 build
   and its measured launch spacing are recorded below.*
4. **Canoe routes, landings and portages are researched, not assumed.** OSM has none in the
   box (§3.3: no `route=canoe`, no `portage`, no `canoe=*`, six slipways). The county
   boards and Naturkartan publish canoe trails for this area; whether any of them comes with
   lines, and with landing places, is a research phase (§4, phase R) whose answer decides
   whether a phase 6 adds them as a named source, the way the Bergslagsleden came off OSM's
   relations.

And the three things that were not questions but are settled with them: **it lives in
`trails`**, because the trip map is a `trails` map and the atlas has no client, with the water
network in `libs` where the atlas takes it over; **the profile over water is the lake's
plane**, read from the height tiles the page already samples a straight leg from — the 1 m
model holds a lake as a plane at its level, so nothing has to carry a level of its own; and
**all three maps get it**, since the code is shared and each build already loads its water.

## 2. How to work through them

The rules of `malingsbo-kloten-phases.md` §2 apply unchanged: one phase at a time per
worktree, a review over each, `command make hooks-run` green, anything touching the browser
driven, stop at the end of a phase. A phase an agent runs is one `codex exec -C <worktree>` as
a transient unit; the worktree's branch is rebased onto `main` and fast-forwarded at review.
`maps.py` and `plan_mode.js` are read by region and never whole. Review, hooks, the drive and
the landing are the reviewing session's. The scratch for this plan is `~/mockups/kayak-mode/`.

**Order and parallelism, in one line.**
0 → { 1 ∥ R } → 2 → 3 → 1b → 2b → 4 → 5 (rebuild, drive) → 4b → 5 (publish). (R found no lines, so there is no 6; 1b came out of 5's first build, 2b out of 4's first drive.) Then 6 (the switches, from the phone) → 7 (one way only where it falls, from the phone) → 5 again.

- Phase 1 (the water network, Python) and phase R (research, no code) touch nothing in
  common and run at once.
- Phases 2, 3 and 4 each edit `plan_mode.js` or read a page built from the phase before, so
  they run one after another; phase 5 is a build on this box and a publish, no agent.

## 3. What was measured, and with what

Scratch in `~/mockups/kayak-mode/` (`measure-water.py`, `measure-water-2.py`, `canoe-osm.py`
and its answer `canoe-osm.json`). Measured 2026-09-21 over the Malingsbo-Kloten box
`(14.967, 59.729, 15.922, 60.176)`, 54 × 50 km, off the cached Topografi 50 delivery of
2026-09-08 through `topografi50.Source` and the `hydrografi` GeoPackage directly.

### 3.1 The water the page has

| | count | size |
|---|---|---|
| lakes (`Sjö`) | 1,332 | 31,715 ha |
| river surfaces (`Vattendragsyta`) | 108 | 272 ha |
| lakes of 10 ha and more / 100 ha / 1,000 ha | 272 / 56 / 4 | |
| lakes carrying a level (`hojd_over_havet`) | 236 of 1,332 | 68 to 304 m |
| shoreline, all outlines | | 2,701 km |
| shoreline vertices as delivered / at 5 m / 10 m / 25 m | 115,730 / 59,082 / 39,226 / 22,584 | |

The page carries these as the water grid, 25 m cells, priced and never drawn (`water.py`).
The eight largest lakes: 2,528 ha at 155 m, 2,431 at 77, 1,610 at 101, 1,123 at 101, 989 at
163, 906 at 155, 768 at 151, 701 at 258.

### 3.2 The water the page lacks: the lines, the dams, the flow

| layer | in the box |
|---|---|
| `hydrolinje` (`Vattendrag`) | 6,709 lines, 3,477 km; `storleksklass` 1: 6,362 lines, 3,359 km; 2: 347 lines, 118 km; `kanal`: 4 |
| `hydroanlaggningspunkt` | 97 *Dammbyggnad, punkt*, 11 *Slussport* |
| `hydroanlaggningslinje` | 6 *Dammbyggnad*, 19 *Vattentub/vattenränna* |
| `hydropunkt` | 2,071 small and 50 large *Strömriktningspil* (flow arrows) |

The lines stop at the shore: none of their length lies inside a water surface. Whether a
line's own direction is the flow's is not documented and is phase 1's first measurement,
against the height model at the two ends and the arrows.

**How the water hangs together.** By touching surfaces alone the box holds 1,190 separate
bodies; the largest chain is 33 surfaces and 6,606 ha. With the lines counted as joins it is
433 systems, and the largest is 754 surfaces, 666 of them lakes, 27,344 ha, levels 77 to
300 m, spanning the whole box. So without the lines the mode is a mode per lake; with them
it is a mode over the landscape, and the level steps between the lakes (77, 101, 155, 163 m
among the big ones) are the portages and the dams — which is what the profile will show.

### 3.3 What OSM knows

One Overpass query (`canoe-osm.py`, answered by `maps.mail.ru`; `overpass-api.de` refused
with 406): 89 elements. `route=canoe` relations: 0. Ways tagged `canoe=*` or
`waterway=portage` or `portage=*`: 0. Nodes `canoe=put_in`: 0. What there is: 39 dam
nodes and 29 dam ways, 2 weirs, 1 waterfall, 6 `leisure=slipway`, 6 canals, 5 rivers.
The canoe trails of this area are not in OSM; phase R looks where they are.

### 3.4 What the code already gives

- **An edge with no ground under it**: `FERRY` in `trails/routing/sources.py`, encoded with
  its kind in the payload's source table, priced flat by `router()` in `plan_mode.js`, cut
  out of snapping by `nearestOnNetwork`, and carried by `routedParts` as a `CROSSING` part
  with `height: null` that `composeRoute` counts as `crossed`.
- **A price switch the reader holds**: `staying()` / `stayOnPaths()` at the top of
  `plan_mode.js`, `PATHS_FACTOR = 10`, persisted under `keptKey() + '.paths'`, shown as a
  switch with its state on its face in `profile_panel.js` (line ~1348).
- **A connector priced by what it crosses**: `priced()` over the water grid, `waterFactor`
  30, `offPathFactor` 3; `joinedRoute` seeding every node with its connector's floor;
  `worthRouting` against the direct line.
- **Two lengths of one way**: `goalShape.total` and `goalShape.crossed`, the heading's
  glyphs from `maps.LENGTH_ICONS`, the words on the figures page and in the GPX (phase 9 of
  the third map, `7434a44`).
- **Heights for a straight leg**: `tileHeights` off the height tiles; the 1 m model holds a
  lake as a plane (Torneträsk reads 341.85 m at every post).
- **Inferred connectors**: `BRIDGE` edges from `_with_bridges` in `trails/routing/graph.py`,
  `DEFAULT_BRIDGE_M` 25, factor 1.3, reported by the page as undrawn ground.
- The graph today: Malingsbo-Kloten 12,779 drawn chains over 153,447 routing edges; the
  router is undirected (`router()` fills both arcs of every edge).

## 4. The phases

### Phase 0 — Decide and open the record

The measurements of §3, the decisions of §1, this plan and `kayak-mode-decisions.md` opened
with them. This session's, done at the first commit of the two files.

### Phase 1 — The water network in the build

*Python only. Files: a new `libs/src/trails/network/water.py`, `trails/routing/sources.py` (one
new kind), `trails/network/sweden.py` and `norway.py` (the sources added), `trails/visualization/encoding.py`
(a per-edge direction flag and the kind in the source table), their tests, and
`analysis/scripts/lomsdal_visten.py` where the sources are assembled and the graph's report
counts. Not `plan_mode.js`, not `maps.py`.*

1. **The flow's direction, measured first.** For the class-2 lines of the Malingsbo-Kloten box,
   the height at each line's first and last vertex off the cached 1 m model, and the nearest
   flow arrow's bearing against the line's bearing where one lies within 50 m. If the line's
   own direction agrees with the fall and the arrows in 95 of 100 cases, the line's direction
   is the flow's; otherwise the flow is read off the heights per line, the disagreeing ones
   listed in the record. Stop and say so if neither test is clean.
   *Measured 2026-09-21 (codex): the arrows agree with the digitised direction in 62 of 63
   lines under the one convention that fits; the z13 height tiles disagree in 61 of 347,
   210 of which fall less than a metre end to end — the resolution, not the water. Decided:
   the digitised direction is the flow. Record §5.*
2. **The shore.** Every water surface (lakes and river surfaces, as `water` is loaded today)
   simplified at 10 m, its exterior and interior rings as lines of one source, **`Shore`**,
   kind `PADDLE` (new in `sources.py`, beside `FERRY`; routable, never walked, carries the
   metres over water), cost factor 1.0.
3. **The open water.** Per surface, the Delaunay triangulation of its simplified ring
   vertices, keeping the edges that lie inside the surface and are not ring edges, as source
   **`Open water`**, kind `PADDLE`, cost factor **k** (`OPEN_WATER_FACTOR`, 1.5 until phase 2's
   sweep says otherwise; the comment says so). Measured and recorded: how many edges, how many
   metres, and the build time they add; if the triangulation of the largest surfaces (the sea
   in Norway is one polygon per municipality) is out of proportion, the ring is thinned for the
   chords alone and the record says at what tolerance.
4. **The streams.** The class-2 lines, directed with the flow, as source **`Streams`**, kind
   `PADDLE`, cost factor 1.0, cut 25 m either side of every dam point and lock gate that lies
   within 25 m of the line. Sweden only in this phase; N50's river lines carry no size class
   that is known — measure whether they carry a usable one, and if not, say so in the record
   and leave Norway's streams out.
5. **The portages nobody has to draw.** Between every two connected pieces of the water
   network (after the cuts) that lie within `PORTAGE_M` = 1,000 m of each other, one straight
   chord at their nearest points, kind `BRIDGE` (an inferred connector, priced and reported as
   undrawn ground), its two feet tied to the nearest node of the walking network within 150 m
   by a `BRIDGE` connector each, so the page can prefer the path over the chord. A dam's cut
   is such a pair and gets its chord the same way. Counted and recorded.
6. **Direction in the payload.** A source declares it is directed (`NetworkSource.directed`,
   the streams only); its lines keep their digitised direction through chaining, noding and
   edge building — `_canonical` in `chains.py` may orient a chain as it likes but records
   where it reversed a directed line, every edge carries `one_way` (True: `from_node` to
   `to_node` only), a split inherits it — and `encode_graph` writes the flag; the decoder in
   `routing_graph.js` reads it onto the graph. The router's use of it is phase 2's. Noded
   with the rest of the network by `graphs.py` as every source is, so a road bridge over a
   river surface and a path along a shore meet the water where they cross it.
   *Corrected 2026-09-21 after codex's stop: the first wording put the flag in the encoder
   alone, and `chains._canonical` reverses 101 of the 347 streams — the direction has to be
   a property the routing layer carries, not one the encoder invents.*
7. **The report.** The graph's report in the build log counts the water sources apart:
   shore, open water, streams, portages; km and edges each; and the page's payload before and
   after, in bytes. The graph is built and reported by `route_graph.py` (`command make graph
   ARGS="--park malingsbo-kloten"`) and built again and encoded by `lomsdal_visten.py`
   (`command make map ARGS="--park malingsbo-kloten"`, warm cache, minutes); run both once at
   the end and put the figures in the record under §5 with the phase's built-note.

*Built 2026-09-21 (codex, `ac467b2`): Malingsbo-Kloten's graph gains Shore 31,706 edges /
2,382 km, Open water 33,082 / 5,078 km, Streams 845 / 116 km (directed as digitised), Portages
14,564 / 1,517 km from 2,942 chords, Portage paths 4,177 / 161 km from 2,161 ties; 247,210
edges in all; the page 8.11 MB brotli against 6.23 (an open item in the record §4). Norway's
sources are assembled but its map is not built until phase 5.*

### Phase 1b — The portages and the chords, cut to size

*Added 2026-09-21 after the first rebuild of the other two maps on phase 3's code: Abisko's
graph took 10,042 portage chords for 1,640 pieces of water — 164,664 edges once noded, the
page 4.34 MB brotli against 1.26 published — and Lomsdal-Visten's graph build was OOM-killed
at 8.2 GB. Step 5's "one chord per pair within 1 km" is quadratic in tarn country.*

Portage chords only between Delaunay-neighbouring pieces, within `PORTAGE_M`, never across
a third piece of water; the open-water chords drawn on the ring thinned to 25 m if the three
sweep legs answer the same (record §4's chord-bytes item); Lomsdal-Visten's graph under an
8 GiB limit, the peak measured; all three graphs measured, two pages' brotli bytes. Codex,
in `water.py` and the record alone, in parallel with phase 4.

*Amended 2026-09-21, twice: Norway's water edges never go to the height service (the
first build ran thirteen minutes fetching before it died); then, since noding the water
into the walking network moves every walking sample too (2,674,735 uncached coordinates),
Norway's whole network reads its heights off the cached 4 m DTM mosaic as Sweden's does,
the lake's registered level and the sea's 0 m on top. And a pond is not kayak water: a
surface under 1 ha takes no part in the paddle network (Norway had 21,507 pieces and
55,401 chords, tarns nearly all), and stays in the grid for pricing alone.*

*Built 2026-09-21 (codex, `9bb67c0`): edges per map — Abisko 75,463 (Shore 13,274, Open water
14,722, Streams 432, Portages 869, ties 249), Malingsbo-Kloten 217,122, Lomsdal-Visten
339,136 (no streams); Lomsdal-Visten's graph offline under 8 GiB at a 4.2 GB peak; pages
1.82 MB and 7.12 MB brotli.*

### Phase 2b — A portage is not a path

*Added 2026-09-21 after phase 4's stop: the walking modes routed over the portage chords
(a `BRIDGE` is walked as undrawn ground at 1.3), and the dry scene's way fell from 22,957 m
to 22,251 m taking 2,359 m of them.* A kind of its own, `PORTAGE`, for the chords and their
ties: unreachable and unsnappable in the walking modes as a paddle edge is, and in the kayak
mode priced as undrawn ground under a kayak, `offPath() × P`, tallied as a connector. After
1b lands (both touch `water.py`); phase 4 resumes after it.

*Built 2026-09-21 (codex, `b95d708`): the kind, the exclusion, the price, the tally; the dry
way is 22,957 m on foot with no portage in both walking settings once more.*

### Phase R — Where the canoe trails are

*No code. Output: a section §3.5 in the record, and a `analysis/routes/malingsbo-kloten-canoe.toml`
only if lines were found.* Naturkartan (kanotled, kanot, paddling over Örebro, Dalarna and
Västmanland), the three county boards' pages for Malingsbo-Kloten, Sveaskog and the
municipalities of Ljusnarsberg, Smedjebacken, Skinnskatteberg and Lindesberg, and Länsstyrelsen's
open data. For each canoe trail or landing place found: its name, who publishes it, the URL,
whether a line or GPX is published and under what terms, and whether landing places, rest
places and portages are named. Nothing is guessed; a trail without a page is not a finding.
The report says what a phase 6 could add as a named source, or that nothing publishes lines.

*Built 2026-09-21, this session: nothing publishes lines — record §3.5. The register's
`Kanotled` type is empty in the box; Nordic Discovery's two trails are a raster map under
copyright; Naturkartan has one place. There is no phase 6.*

### Phase 2 — The switch and the prices in the page

*Files: `plan_mode.js`, `profile_panel.js` (the switch beside *Stay on paths*), `maps.py` by
region (`PLAN_SETTINGS`: `paddleKind`, `portageFactor`), `routing_graph.js` only if phase 1 left
the flag unread, tests. A page rebuilt once from phase 1's graph.*

1. **The mode.** `kayak()` / `paddle(want)` beside `staying()`, persisted under
   `keptKey() + '.kayak'`, handed out on `window.trailsPlan` as `stayOnPaths` is, with the
   switch in the panel next to the paths switch, its state on its face, worded *Kayak*.
2. **The prices.** `router()` prices an edge by mode: in the kayak mode a `PADDLE` edge costs
   its metres times its source's factor, a walked edge its metres times its factor times
   `portageFactor` (P), a ferry as today; in the walking modes a `PADDLE` edge is unreachable.
   The cost table is rebuilt when the mode changes (`routing` dropped), not on every search.
   `priced()` in the kayak mode charges a water cell at the open-water factor and a ground
   cell at `offPath()` times P. `worthRouting` is unchanged in form.
3. **Direction.** A predicate, not a missing arc: a step over a one-way edge is allowed
   only when the journey runs `from_node → to_node`, which `joinedRoute` (searching
   backwards from the destination) and `routeBetween` each ask with their own direction; a
   point on a one-way edge exits only downstream and is entered only from upstream, and the
   on-edge shortcut stands only downstream. And the search's floor is the cheapest metre
   the mode allows — `offPath()` walking, `min(k, offPath() × P)` paddling, k read off the
   *Open water* source's factor in the header — or the bound would prune the water.
   *Corrected 2026-09-21 after codex's stop: the first wording removed the reverse arc and
   left the floor at the walking price; the backward search would have followed streams
   upstream and pruned every answer cheaper than ground.*
4. **Snapping.** `nearestOnNetwork` and `endsOf` take `PADDLE` edges in the kayak mode and
   skip them in the walking modes, as they skip a ferry today, so a tap on a lake in the
   walking mode still means open ground and in the kayak mode means the shore.
5. **The sweep.** k and P on the Malingsbo-Kloten page over the three legs of §1.3, with the
   page driven (`command make drive` machinery or a Playwright script beside it in
   `~/mockups/kayak-mode/`), k at 1.2, 1.5, 2, 3 and P at 2, 4, 8, the answer per leg in
   metres over water and on foot and the time the search took. The figures that give Uwe's
   four sentences at a cost a drag can carry go into `OPEN_WATER_FACTOR` (with a note that the
   graph is rebuilt in phase 5) and `portageFactor`; the sweep goes into the record.

*Built 2026-09-21 (codex, `bea479c`): the switch, the prices, the predicate, the floor, the
snapping, the tally rule (a paddled edge is credited to its source, counted in no marking
bucket, and inside the reserve); the sweep over a bay, a lake and a portage at k ∈ {1.2, 1.5,
2, 3} × P ∈ {2, 4, 8} settled k = 1.5, P = 2 (record §5); all 65,633 paddle edges unreachable
and unsnappable in the walking modes; a stream taken downstream and refused upstream.*

### Phase 3 — What a paddled way says

*Files: `plan_mode.js`, `profile_panel.js`, `maps.py` by region (the words), tests. The dry
case is byte-identical: `a_dry_way_keeps_its_words` and the phase 9 readings stay green.*

1. **Parts.** A routed part over `PADDLE` edges and, in the kayak mode, a straight part the
   grid holds as water are parts of kind `paddled`: level over the water (the lake's plane,
   so the profile is flat over water and climbs on the portage), their
   metres counted into `crossed` and not into `total`, a leg over land in the kayak mode a
   land or routed part as today. Rivers waded stay on foot in the walking modes; in the kayak
   mode a class-2 river is paddled and a river surface is water.
2. **The heading and the figures page.** In the kayak mode the heading leads with the water,
   *12.30 km 🛶 · 0.80 km 🚶*, the figures page and the file's description say *by kayak* and
   *portage on foot*; in the walking modes the words of phase 9 stand.
3. **The files.** A paddled part is written into the GPX track and the Garmin course as the
   way it is, unlike a ferry, and the description says which metres were paddled. Stations
   on the water are anchored to the track, since now there is one under them.

*Corrected 2026-09-21 after codex's stop: the tiles blur the bank into the water, and a
straight part of six samples at a shore rose 0.97 m in 25 m. The level is one figure per
body, set in the build — Topografi 50's `hojd_over_havet` where a surface carries one, the
10th percentile of its shore edges' samples otherwise — and a straight paddled part in the
page is flat at the lowest of its own samples. §1's "read from the height tiles" was right
about the plane and wrong about the shore.*

*Built 2026-09-21 (codex, `7f68137`): lakes levelled per body in the build, paddled parts,
words and files; the bank case reads 219.56 m six times; dry artifacts byte-identical. The
scene's stored dry hashes moved with phase 1's noding — phase 4's to reconcile.*

### Phase 4 — The scene and the drive

*File: `analysis/scripts/drive_map.py`.* A kayak triple on each scene that has water the graph
knows — Malingsbo-Kloten first, Abisko (Torneträsk) and Lomsdal-Visten (the fjord) after
phase 5's rebuild — and the readings: *a kayak way follows the shore* (two points on one
shore, the way's water metres within a tenth of the shore's, no land), *a bay is cut and a
lake is not* (the bay leg's water metres less than the shore round it, the lake leg's along
the shore), *a portage takes the path* (two lakes with a path between them: the way's land
metres on the path, none straight), *a paddled profile is flat* (the heights over the water
within 0.5 m of one another), *the walking modes never take the water* (the same two shore
points in walking mode: no `paddled` part, the way as it was). The scene puts the mode back
at the end, as the goal helper does (`malingsbo-kloten-decisions.md` §10, phase 9's lesson).

*Built 2026-09-21 (codex, `c766ceb`): the kayak triple and five readings on Malingsbo-Kloten
— a shore of 2,123 m all paddled, a bay cut at 1,066 m against 2,502 m round, a portage of
1,275 m on mapped paths, water profiles flat, the walking modes unchanged; the dry way moved
2 mm with the noding; 1,417 readings, none broken.*

### Phase 4b — The other two scenes, on the rebuilt pages

*Added 2026-09-21 after phase 5's first drive over the three rebuilt pages: Malingsbo-Kloten
1,417 readings and none broken; Abisko 6 broken and 2 moved (the long-edge check took a
Shore edge as the graph's longest, the offline-scope race, the dry hashes moved by the
noding); Lomsdal-Visten 1 broken and 2 moved (a stop's distance 10 m on, the dry hashes).*
The long-edge check takes the longest walkable edge; the moved figures re-recorded where
the noding is the reason; the kayak triples on Torneträsk and the fjord. Codex, in
`drive_map.py` alone, driving the main checkout's rebuilt pages by path.

*Built 2026-09-21 (codex, `aee7804`): shore / bay / carry — Abisko 2,116 / 1,408 / 336 m,
Lomsdal-Visten 932 / 715 / 960 m, profiles flat at 342 m and 0 m; the dry ways the same to
6 cm, their words re-recorded (resampling after the noding; Lomsdal-Visten's mosaic); a
walking pair near Torneträsk finds a cheaper way in through the new nodes (7,982 → 7,739).*

### Phase 5 — Rebuild, drive, publish

The three graphs and pages rebuilt on this box (`make graph` and `make map` per map, the last
two steps of each map's chain in the Makefile — not the tiles), `drive-all` green, the three maps
published with `just deploy --map <map> --tree packs` from `home/trails-map`, read back
byte-identical, then Uwe's phone: the switch, a bay, a portage.

### Phase 6 — Named canoe trails (only if phase R found lines)

A source of `PADDLE` kind with names and links, like the Bergslagsleden off OSM's relations,
from whatever phase R found. Planned when R reports.

*Built 2026-09-21 (this session): the three graphs and pages rebuilt on `be43818` (pages
1.82 / 7.08 / 7.12 MB brotli against 1.26 / 5.71 / 6.23 published before), `drive-all` 1,447 /
1,452 / 1,415 readings and none broken, published ~15:20 UTC and read back identical.
Uwe's phone reading is the open item.*

### Phase 6 — The switches in plan mode

*Added 2026-09-21 from Uwe's phone: "Ich habe im Plan-Panel weder Stay on paths noch Kayak."
Both switches live on the profile panel's *Places on the way* page, which exists only while
the panel shows the way to a goal; a reader planning in plan mode never sees them. Uwe's
word: "Das soll auch gehen im Plan-Modus."* The same two switches, one state, on the plan's
*Points and stages* page as well — under its heading, above the list, in the same form —
painted from the same closure so that both places always show the same knob; a drive reading
that switches on one page and reads the other; the three pages rebuilt and published.

*Built 2026-09-21 (codex, `8d864eb`): shared switches on both pages, hidden when read-only;
switching Kayak on the plan's page re-priced the way (2,123 m paddled on the scene's shore
pair); 85 readings twice.*

### Phase 7 — One way only where it falls

*Added 2026-09-22 from Uwe's phone at Korslångssmedja (Malingsbo-Kloten). Upstream from the
small lake into Korslången the route left the water 232 m before the channel's mouth, walked
158 m of path and 174 m of road to the dam and put in there, instead of paddling the channel
to the dam and carrying the 108 m OSM path (`osm-514307-6645636-108`). Measured on the
published page with the search exposed (`~/mockups/kayak-mode/korslang/`): downstream the
page takes exactly that way; upstream the channel is closed, because Topografi 50 draws it as
a class-2 `Vattendrag` line, 229 m from the lake's tip to the dam, and phase 1 made every
class-2 line one way with its digitised direction. But the channel does not fall: the 1 m
height model along its two edges reads 258.1–258.4 m all the way to 25 m below the dam, the
5 m are the dam itself (263 m above, 258 m below). Uwe: "Bis zu der Stelle wo ich raus bin
aus dem Wasser war es noch kein Bach. Gab auch de facto kein Gefälle." Two-way, the channel
way costs 1,504 against the detour's 1,841.*

**The rule.** A stream edge is one way only where the water falls. The edges already carry
the height model's samples (`elevations`, in the edge's own direction, which for a directed
source is the digitised flow after `graph.py` reverses a canonical line back). In
`water.build`, after `level_lakes(measure(network))`, every `Streams` edge whose fall in its
flow direction is under `LEVEL_FALL_M` — the greater of 0.3 m and 0.1 % of its length,
starting values until measured — has `one_way` cleared: level water is paddled both ways at
the shore's price, and the direction stays only where the data and the heights agree. An
edge that *rises* in its flow direction by more than that is opened the same way, not
reversed: the two sources disagree and the restriction has no evidence. Nothing on the
page changes; the flag already travels per edge.

**Measured first, on the built networks of Malingsbo-Kloten and Abisko** (both have
streams; Lomsdal-Visten has none, §5). The published pages' payloads say: Malingsbo-Kloten
610 stream edges / 115 km, of which 164 edges / 34 km fall at most 0.1 % and 107 edges /
24.5 km *rise* by more than 0.3 m between first and last sample; Abisko 432 / 56 km, 26 /
1.5 km level, 165 / 23 km rising. Before the gate is trusted the rising edges are
classified: a bump in the middle with level ends (a bridge deck, trees over a gorge) is not
a rise; an edge whose ends sit on a levelled lake (phase 3 replaced lake heights, not
stream heights) is compared on its interior samples; what remains is either a monotone
rise — the digitised direction is not the flow there — or the model's noise. Read the fall
robustly, the median of the first and last quarter of the samples rather than two end
posts, and say how many edges and kilometres each class holds against the flow arrows
within 50 m (`hydropunkt`, `Strömriktningspil`, 2,121 in the Malingsbo-Kloten box, read
in phase 1). If the monotone rises are many, stop: whether to flip them is a decision.

*Corrected 2026-09-22 after codex's stop at the measurement: the baseline above was read with
the reviewing session's harness reversing an edge's samples by the chain-orientation flag,
which the payload does not mean — an edge's samples run in its own direction, and for a
directed source that is the flow. Read right, on the built graphs: Malingsbo-Kloten 44 edges /
7.4 km rise between end posts, 30 / 2.3 km by quarter medians, and not one of them has a flow
arrow against its digitised direction (74 edges with arrows agree, 1 opposes, none among the
rising); Abisko 4 / 0.2 km and 1 / 0.02 km. The rises are bumps and noise, the direction stands,
nothing is flipped. The gate as written above would open 359 edges / 53.6 km and 103 / 2.5 km —
but 92 and 67 of those are pieces under 300 m of streams falling more than 0.5 %, opened by the
0.3 m arm alone because noding cut them short: a steep mountain stream is not paddled up in
10 m pieces. So the gate reads the **chain**, not the edge: a `Streams` chain's fall is the sum
of its edges' quarter-median falls in flow direction, its threshold the greater of 0.3 m and
0.1 % of the chain's length, and a level chain has `one_way` cleared on all its edges. Measured
on codex's captures that opens 173 chains, 282 edges / 46.9 km in Malingsbo-Kloten (the
Korslång channel among them, 0.16 m over 203 m) and 35 chains, 44 edges / 2.2 km in Abisko,
and no short steep piece. A chain with a rapid in the middle stays one way whole, which is
the conservative side. The rising chains are opened the same way, as written.*

**A test** on a synthetic network: a falling, a level and a rising stream edge, only the
first stays one way; the thresholds' both arms exercised. **A drive reading** on the
Malingsbo-Kloten scene: the pair (59.9440, 15.2620) → (59.9525, 15.2500), small lake to
Korslången, in the kayak mode paddles the channel and carries the OSM path at the dam — say
the metres — and the reverse pair reads the same way; the three existing kayak triples'
figures are re-recorded where they move. Then phase 5 again: all three graphs and pages,
drive-all, publish.

*Built 2026-09-22 (codex, `a1c8ded`, one stop at the measurement): the chain gate in
`water.build`, the test, the Korslång reading (1,267.8 m paddled, 77.2 m carried, the whole
channel and 20.1 m of the dam's OSM path, both ways the same). Phase 5 again on `f25229a`:
Abisko opens 35 chains / 44 edges / 2.2 km, Malingsbo-Kloten 186 / 302 / 48.5 km,
Lomsdal-Visten none; `drive-all` 1,464 / 1,464 / 1,451 readings, none broken but the known
first-visit race on Lomsdal-Visten, green alone; published ~15:00 UTC and read back identical
on all three. Open: Uwe's phone reading at Korslångssmedja.*

### Phase 8 — Water first

*Added 2026-09-23 from Uwe's phone at Korslångssmedja. His words, translated:
"The kayak planner prefers long land ways to the water. I want a water way always to be
 taken when possible. Unless a point is explicitly set on the land way, I would always
 prefer the water way."*

The z14 screenshot selects `topografi-50-paths-514477-6645508-1136`, a 1,136.739 m path
across the peninsula towards the shore south of Skatholmen. Its exact taps are unknown.
The cached Ortnamn record puts Korslångssmedja at (59.946199, 15.259790); Lövudden and Skien
locate the northern part of the image. The reconstructed pair uses the nearest wet paddle
nodes beside that path's ends: **(59.945871, 15.258351) → (59.952097, 15.273234)**. The
nodes are 105.911 and 18.525 m from the path ends. Before changing prices this pair runs
125.031 m on water and **1,352.730 m on foot**, including 1,295.087 m of Topografi 50 paths.
With land edges excluded the existing directed network connects the same points over
**4,296.406 m of water**. No network repair is needed.

**The rule.** In kayak mode a way is chosen by the fewest metres on land first: walked
edges, portages, ground connectors and partial edges all count their actual lengths.
Paddle and ferry edges count no land; the ferry keeps its flat secondary price.
Between ways with equally few land metres, today's price decides: shore 1, open water
k = 1.5, path cheaper than ground. `plan_mode.js` carries a true lexicographic pair through
both searches, their heaps, cuts, connector floors and the comparison against a straight
way. Connector floors count only dry samples already proved by the grid; a dry tap's
compulsory entry is bounded conservatively as well. The secondary floor is length times
the cheapest connector metre. Exact labels stay apart from those floors; complete exact
ways tighten the lexicographic bound during the search.
Counting dry grid pieces directly prevents an all-water connector acquiring negative land
from rounded length subtraction. The direction rules, snapping, tally and words stand;
the walking modes supply zero primary cost and retain their original price ordering.

**The drive.** `a_kayak_uses_water_before_land` checks the reconstruction on Malingsbo-Kloten
and wet shore pairs on the other maps. A separate traversal of paddle arcs proves a water
way exists in the journey's direction; the planned way must carry no land. A point explicitly
set on a mapped land node must still be reached by the track. Every borrowed mode, goal
way and plan is put back. `a_portage_keeps_land_short` replaces the old assertion that every
carried metre uses a mapped path: the rule now paddles farther to carry less, and the drive
accounts for both mapped and inferred ground against the former mapped carry.

**Build scope, clarified after the stop.** The normal in-memory graph rebuilding inside
`command make map` is allowed. No graph source or content change, `make graph`, tile build,
shared-cache write, push or publication belongs to this phase.

**Built 2026-09-23.** True lexicographic costs, the executable routing tests and the new
water-first drive reading. The reconstructed Korslångssmedja pair above had **1,352.730 m
on foot before**; it now takes **4,296.406 m paddled and no land**. The Malingsbo-Kloten
scene portage changes from **5.912 / 1,274.726 → 1,414.654 / 513.463 m**, paddled / on foot:
the longer paddle that "always water" entails. The other scene portages change from
0 / 335.952 → 336.096 / 102.465 m on Abisko and 0 / 959.690 → 1,597.100 / 124.947 m on
Lomsdal-Visten. These are the three scenes' `kayak portage water, m` and
`kayak portage on foot, m` figures. `Korslång upstream on foot, m` and
`Korslång downstream on foot, m` each change from 77.190 to 77.105; the channel still
paddles 1,267.848 m both ways. New `Korslångssmedja water, m` / `Korslångssmedja on foot, m`
figures record 4,296.406 / 0. Shore and bay figures do not move. The phase-2 sweep's portage
changes from 51.555 / 1,220.934 to 1,902.419 / 598.441 m; its bay and lake stand.
No measured way gains land.

The long connected legs' median warm searches cost 57 → 95 ms on Malingsbo-Kloten,
15 → 25 ms on Abisko and 69 → 107 ms on Lomsdal-Visten; coordinates, length breakdowns,
ferry credit and timing ranges are in the record's phase-8 note. All three pages built;
their routing headers and inflated payloads are byte-identical to the baseline. The final
selected drives are green twice: 135 readings each on Malingsbo-Kloten and 110 each on the
other two, with only the existing channel skip there. Both walking settings' recorded
lengths and the dry figure/GPX hashes are byte-identical, with no walking snapshot changed.
The 14 routing tests and the full 2,017 library / 97 pipeline tests pass. Scratch and final
hook/drive logs are under `~/mockups/kayak-mode/phase8/`; nothing pushed or published.

**Review built 2026-09-23 — Off-network searches.** The zero-land floors in `812433e` let a
short leg with a dry direct line price connectors across the whole map. The amendment
uses sampled dry prefixes, a conservative floor for the unavoidable entry from dry
ground, and exact whole ways found during the search to tighten the lexicographic bound.
An exact connector resumes after its dry prefix and stops when its accumulated land can
no longer win. No positive-land way caps the secondary price of a way with less land.
The ferry still contributes zero land and keeps its flat secondary price.

Ten fixed Firefox cases cover off-network water pairs near 1 km and 10 km, ground-to-lake
taps on all three maps, and an additional Norwegian ground-to-fjord stress case. Five
warm searches per case retain exactly the same primary land and secondary price; the
record separates search-derived metres from the public tally. Ground-to-lake **median / worst ms** change from **3,430 / 3,547 → 118 / 121**
on Malingsbo-Kloten, **780 / 804 → 57 / 76** on Abisko, and
**6,087 / 6,225 → 194 / 199** on Lomsdal-Visten. The fjord case changes from
**6,827 / 7,024 → 259 / 275**; each of these ten fixed cases is below 300 ms. Coordinates,
water-pair timings, floor counts and completed connector prices are in the record's
review built-note. `a_kayak_rounds_land_from_open_water` defines the short pair on each
page; the executable tests require a more expensive zero-land detour to win within the
step bound and compare the pruned search with every entry/exit pair on small graphs.

**Sampling decision, retained by Uwe.** For
(59.9659281691193, 15.863781710359643) → (59.97490373192166, 15.850783875167386),
`connectorPrice()` reads zero land at its 25 m grid midpoints, but the public plan's
5 m profile posts produce **1,257.818 m paddled / 20.106 m on foot**. The same public
figures reproduce with `812433e`. Phase 2's retained sampling decision stands:
"fewest land metres first" means the router's measured land, and connector pricing
stays cell-based. The drive reads the search's own label through a probe in the served
built page; it requires zero router land, paddled network edges and a matching public
total length. The tally may differ by at most **one grid cell per connector end**:
four ends at 25 m give this pair a 100 m allowance, containing its 20.106 m shoreline
sliver. Exceeding that allowance fails. Search pops also stay within the step bound.
The profile tally, connector pricing samples and walking modes are unchanged.

All three pages rebuilt with unchanged routing headers and inflated payloads. The
selected drives pass twice per page: **152 / 127 / 127 readings**, Malingsbo-Kloten /
Abisko / Lomsdal-Visten, with only the existing channel scene skip on the latter two.
The new short pairs report router land **0 / 0 / 0 m**, tally land
**20.106 / 10.026 / 0 m**, all within their 100 m allowances. Their heap pops are
**169 / 71 / 277**, within the graph-derived step bounds recorded alongside them.
Every page's eight recorded walking values are byte-identical on both runs; no
recorded figure moved. The full `command make hooks-run` passes with networking
on, including the 19 executable routing readings. The record names the final logs
and payload comparisons. No push or publication.

**Differential built 2026-09-23.** All **600 / 600** seeded random pairs agree with
an exhaustive reference: 200 per map, 50 each of off-network water/water,
dry/water, dry/dry and network/off-network. Seed **20260923**, five length bands
from 100 m to each grid's width; the record gives actual spans and reproduction
details. The reference eagerly prices every exit, exhausts reverse Dijkstra and
separately prices every entry, with no dry box, entry floor, wet-node seed or
incumbent pruning. Worst label differences are **0 m land / 0 price** on all
three maps; two Lomsdal-Visten edge sequences differ with exact tied labels.

Warm Firefox **median / p95 / worst ms** are **38.5 / 717 / 1,340** on Abisko,
**205 / 4,633 / 6,464** on Malingsbo-Kloten and **203.5 / 9,663 / 17,241** on
Lomsdal-Visten. Respectively **41 / 92 / 92** pairs exceed 300 ms: the earlier
claim applies only to its ten fixed cases. Timing runs one map at a time after
the reference jobs, reproduces the seed and rechecks every label. The permanent
unit reading compares 32 fixed-seed synthetic pairs against the same full
reference, including dry entries, broken water, disconnected nodes, direction
rules and partial-edge endpoints. All 20 routing tests and
`command make hooks-run` with networking pass. Evidence is under
`~/mockups/kayak-mode/phase8/differential/`, especially `summary.json`.
No routing fix was needed; only tests and records change, so the unchanged
pages need no rebuild or drive. No push or publication.

**Performance review built 2026-09-23.** The same 600 pairs were replayed on
main's `d267de6` kayak planner (P = 2). Warm Firefox timings below are
**median / p95 / worst ms**; §5 of the decision record gives all pair-kind and
length-band tables, work counters, index costs and the admissibility argument.

| Map | Baseline ms | Phase 8 before ms | After ms |
|---|---:|---:|---:|
| Abisko | 5 / 851 / 1,024 | 38.5 / 717 / 1,340 | 18 / 174 / 271 |
| Malingsbo-Kloten | 21.5 / 4,135 / 5,979 | 205 / 4,633 / 6,464 | 75 / 1,103 / 1,466 |
| Lomsdal-Visten | 19 / 8,422 / 15,166 | 203.5 / 9,663 / 17,241 | 103.5 / 2,166 / 4,420 |

Every requested pair-kind and length-band group meets the larger of its
baseline figure or 300 ms for each statistic. The baseline already has slow
long legs. The final 600 answers agree with the exhaustive reference with
**0 m land / 0 secondary-price difference** on all maps. Dry-endpoint exits
use a linear exact-pricing pass; network starts have a directed whole-metre
entry floor. Uniform grid squares batch the original midpoint reads without
changing their wet count. Wet endpoints retain lazy floors. Walking prices,
phase 2's connector sampling and the recorded kayak figures are unchanged.
The independent scalar sampler checks 6,000 connectors, and the 32-case
network differential now uses packed grids. All 21 routing tests pass.
The one-time grid index costs 123 / 279 / 559 ms and 4,475,900 / 8,481,660 /
20,083,608 bytes (Abisko / Malingsbo-Kloten / Lomsdal-Visten); physical-phone
startup and memory use are unmeasured. Evidence is in
`~/mockups/kayak-mode/phase8/differential/performance/`.

`command make hooks-run` passes with networking enabled. Its first run found
one stale rendered-source assertion; updating the assertion required no runtime
change. The record names both logs.

All three pages rebuild from cached inputs with identical graph headers and
payload bytes. Kayak checks, switches, dry words and foot/water readings pass
twice per page: **137 / 162 / 137 readings per run** (Abisko / Malingsbo-Kloten /
Lomsdal-Visten); only the channel check outside Malingsbo-Kloten is skipped.
Every previous reading is unchanged on both runs, including kayak figures and
each page's eight byte-identical walking values. The record names the payload
comparison and full reports. No standalone graph or tile build, cache write,
push or publication.

### Phase 9 — A finer shore

**Review decision, 2026-09-24 — dam surfaces and replacement MK fixtures.**
Phase 7's dam/lock cut also excludes all network PADDLE geometry in the
25 m radius around each `hydroanlaggningspunkt` dam or lock-gate point.
The existing portage machinery joins the cut sides. Kayak connector samples
inside those discs count as land; a compact point list travels in the page.
Walking and the shared grid stay unchanged. Final kayak differentials use
the same disc rule in the unpruned reference. Measurements count affected
surfaces and edges and read Korslång's channel in both directions.

Review permits new Malingsbo-Kloten bank and routed-carry fixtures while
retaining the original taps in the reader comparison. Abisko's fixed pair
stays. The three identified MK stream pieces must rejoin the surface graph,
with direction-specific reachability checked after phase 7's direction pass.
These decisions resolve the dam/fixture stop below; final validation remains
required before phase 9 is built.

**Review decision, 2026-09-24 — inlet mouths and interface heights.**
The fixed shore pair stays. Its Open water pieces must all lie within 5.1 m
of unsimplified lake/river interfaces; none may cross the lake interior.
Its measured reference is the new graph restricted to Shore plus interface
edges, with the existing 10 % length band. The before/after report retains
Abisko's old 2,116.110 m shore reference, the new Shore-only 2,676.507 m,
and the chosen route. A shared lake/river interface is emitted once, at the
adjacent lake's level; river interiors retain sampled heights. These are
review's decisions, resolving the shore-reading stop below. Rebuilt edge
counts, profiles and joins, final differentials and drives must verify them.

**Production source and body rule.** Swedish paddle surfaces and the shared
25 m grid use cached Marktäcke `Sjö` and `Vattendragsyta`; Norway retains N50.
The complete intersecting delivery pieces are dissolved on a 1 cm precision
grid before taking rings or clipping to the map. The 1 ha test is on the
union area of each connected water body, so a small delivery piece survives
when its body qualifies. Ponds below that cutoff remain in the pricing grid.
Lake components retain their registered or shore-derived planes; connected
river surfaces do not merge those planes. Only the water union's external
boundary is Shore. Delivery seams disappear; lake/river interfaces and map
cuts carry Open water prices. Shared mouths have one lake-owned copy.
Stream directions and dam cuts still use the same Topografi 50 stream/dam
inputs; shoreline and portage intersections are derived again by the build.

The Swedish pages credit “Paddle water and water grid” to **Marktäcke
Nedladdning, vektor, © Lantmäteriet, CC BY 4.0**, and describe dissolution,
simplification and the shared grid. The grid continues to classify straight
connectors and the public tally under phase 2's semantics; it does not draw
the shore. No walking price or midpoint-sampling rule changes.

**Uwe’s decision, 2026-09-24 — “So wie vorgeschlagen” (as proposed).**
On the walking-rule report, Uwe chooses the shared Marktäcke water grid in
Sweden and N50 in Norway for both modes. Walking keeps `WATER_FACTOR = 30`
and its existing 25 m midpoint pricing. Uwe accepts the three material
recorded ordinary-walking changes: Across Dammtjärnsbäcken **356.595 →
2,343.036 m** (about 66 m of real river surface along the old line), the
Malingsbo-Kloten helper **9,287.861 → 9,590.349 m**, and Norway’s typed leg
**819.932 → 1,066.298 m** (the latter two are noding consequences).
Exact-width or finer-cell water pricing is a possible later improvement,
not part of phase 9. His earlier remark about a coarser walking grid was
a question; the interim grid choices were review’s, superseded here.

Review’s **5 m** tolerance and accepted p95 search growth stand: the sweep
measured page growth of 0.37 / 0.81 / 0.64 MB Brotli and p95 growth of
+32 / +32 / +8 % for Abisko / Malingsbo-Kloten / Lomsdal-Visten. Phase 8
took Malingsbo-Kloten’s p95 from 4.1 s to 1.1 s; 1.4 s remains below that
earlier figure. Final-graph timing is recorded separately below.
The inland gate samples used network PADDLE edges every 0.1 m against
unsimplified source water and permits at most **5.1 m** inland deviation.
Grid-classified straight connectors and longest land runs are information,
not gates. Final search labels must equal the unpruned reference for the
200 seeded pairs per map in kayak and both walking settings. Walking’s
recorded length bound remains, with the three exceptions accepted above.

*Uwe's decision, 2026-09-24, after the phone's z18 shore reading and the two
investigations in `~/mockups/kayak-mode/shore-line/report.md` (§A and §B.5) and
`~/mockups/kayak-mode/water-sources/report.md`: Sweden takes its paddle water
from Lantmäteriet Marktäcke, Norway keeps N50, and all three maps measure
5 / 3 / 2 m shore simplification. No offset or narrow-water centre lines in
this phase.*

Marktäcke's `Sjö` and `Vattendragsyta` are to be dissolved across delivery and
feature boundaries before rings are taken, with the 1 ha cutoff applied to
connected water bodies. Its cached municipal files need no new download.
The source investigation identifies Marktäcke as CC BY 4.0, © Lantmäteriet;
the page must credit it for paddle water and identify the modifications.
The price rule, stream directions and dam cuts, lake levels, portage rules
and walking modes stand. The page's 25 m water grid is to use the same finer
water as the network; the requested walking figures must remain unchanged.

**Stopped 2026-09-24 — The shared grid changes the walking figures.** The
page has one water grid for both modes. Replacing only that grid with one
built from cached Marktäcke changes Abisko's recorded shore-pair readings:

| Walking setting | On foot m, before → after | Water m, before → after | Straight land m, before → after |
|---|---:|---:|---:|
| Walking | 2,940.880 → 2,935.858 | 15.273 → 20.295 | 514.362 → 509.340 |
| Stay on paths | 2,963.410 → 2,948.288 | 15.283 → 30.405 | 510.746 → 495.624 |

The graph, routing code, river outlines, grid extent and 25 m cell size were
unchanged. Baseline readings reproduce the scene's recorded values; the
changed figures exceed the existing 0.01 m acceptance. Malingsbo-Kloten's
same six readings remain unchanged in this experiment. Every reading puts
back the plan, mode and goal way. The decision record's phase-9 stop gives
the reproduction and code locations.

**Review must choose:** keep Topografi 50 for walking and introduce a separate
Marktäcke kayak grid, or share Marktäcke and allow the walking figures to move.
Neither choice is made here. No production source or page was changed, no
graph/map/tile build was started, and no tolerance, payload, search-time or
shore-containment acceptance is claimed. Only this stop and its record are
committed; there is no phase-9 built-note yet.

**Review resolved the grid stop, 2026-09-24.** Share Marktäcke between kayak
and walking: one account of where the water is, without a second grid's
payload and memory. Walking still prices water at 30; its figures may move
where the finer source changes what a connector crosses. Measure every
walking reading and the phase-8 200 random pairs per map in both walking
settings before and after. Record every moved walking figure and name phase
9 beside its updated drive value. Stop if a walking route's length changes
by more than the larger of 2 % of its old length and 50 m. A changed
foot/water split at an edge alone is accepted. The remaining phase-9 scope
stands.

**Stopped again 2026-09-24 — A walking route exceeds the review bound.**
Abisko's phase-8 pair at index 71 (the 72nd pair), replayed in ordinary
walking, changes from **5,428.454 to 5,125.769 m** with only the shared grid
replaced. The **302.685 m / 5.576 %** change exceeds
`max(2 % × 5,428.454 m, 50 m)` = **108.569 m**. The public planner confirms
both lengths, with its state restored after each reading. This is a
different way off the network, not only a changed foot/water split.

The taps are (68.3661770595677, 18.788008393436556) →
(68.37383928183993, 18.833846517753347). Walking's own snapping leaves both
off the network. The final connector changes from 2,574.942 to 2,275.325 m;
the shorter connector has 45 of 92 wet pricing samples on Topografi 50 and
44 on Marktäcke. The water price remains 30. The record gives its exit
points, public foot/water figures and reproduction.

The replay stops on this first excess: 200 Abisko baseline pairs in each
walking setting, then 72 comparisons in ordinary walking. The other
walking comparisons, recorded-reading sweep, production source change,
tolerance sweep and builds remain pending. No drive snapshot is updated
for an unbuilt source change. **Review must decide whether this shorter
route is acceptable and how the bound applies on resumption.** The shared
grid decision is retained.

**Review resolved the random-pair bound, 2026-09-24.** Uwe accepts pair 72:
one changed wet sample can move a long connector's preferred exit under the
unchanged water price of 30. Random walking pairs in both settings have no
length-change stop. Report their changed count, longer/shorter counts and
median / p95 / maximum absolute and relative length changes; explain every
length increase above `max(0.02 × old length, 50 m)` with its taps. Re-price
each changed old way on the new grid: an old way cheaper than the new
answer is a defect and stops the phase. The length bound still applies to
the drive's recorded walking ways. Smaller recorded changes may be updated
with a phase-9 note. The shared grid and remaining phase scope stand.

**Stopped at the land-stretch reading, 2026-09-24.** The resolved walking
replay completes all 1,200 grid-only comparisons: 58 changed ways, none
more expensive than its old way re-priced on the new grid. The decision
record gives all distributions and every long-increase outlier with its
taps and explanation. Norway's 400 comparisons are unchanged.

Abisko trial pages built at all three proposed tolerances fail the new
requirement that no sampled paddled stretch longer than that tolerance lies
on the source's land. The recorded shore pair is
(68.393226, 18.715936) → (68.407071, 18.697511). All rows below are tested
against unsimplified Marktäcke water, including the Topografi 50 baseline.

| Water / tolerance | Paddled m | Longest sampled land run m | Longest exact land segment m | Maximum sampled inland deviation m |
|---|---:|---:|---:|---:|
| Topografi 50 / 10 m (before) | 2,116.110 | 114.000 | 115.524 | 9.328 |
| Marktäcke / 5 m | 2,167.118 | 96.000 | 96.258 | 4.741 |
| Marktäcke / 3 m | 2,182.974 | 80.000 | 80.693 | 2.754 |
| Marktäcke / 2 m | 2,192.258 | 76.000 | 78.765 | 1.846 |

The tolerance limits the line's deviation, not how long a shallow excursion
can run over land. The 2 m page has a continuous **78.765 m** land segment
near (68.397326, 18.703586) → (68.398027, 18.703811); its maximum inland
distance at 0.1 m sampling is **1.774 m**. This is not coordinate-rounding
noise. The existing `water.sources()` simplifies the surface before testing
chord containment; neither that test nor the simplified shore bounds a
longitudinal land run. The investigation already distinguishes reduced
leakage from guaranteed containment (shore report §A).

**Review must decide the acceptance measure:** bound inland deviation by the
chosen tolerance (with an explicit encoding allowance), or retain the
longitudinal land-run bound and decide the containment-preserving geometry
and boundary-rounding policy it requires. No offset, narrow-water centre
line, price adjustment or relaxed drive assertion has been introduced.

**Built 2026-09-24 — Abisko trials for this stop.** Three sequential,
cache-only `command make map` builds write to
`~/mockups/kayak-mode/phase9/{5,3,2}/abisko/`; their public scene readings
restore plan, mode, goal way and view. They are experimental pages, with no
accepted tolerance or phase-9 release. The source and test prototype is
saved as `production-prototype.patch` in that scratch directory and removed
from the worktree; only the two records are committed. The full three-map
payload/search sweep, final walking graph replay, remaining reader-facing
measurements, new drive reading, twice-green drives and final graph/map
builds remain pending. No shared-cache write, download, tile build, push
or publication.

**Review resolved the land gate, 2026-09-24.** Measure inland deviation at
every 0.1 m sample of the paddled scene routes against unsimplified source
water: Marktäcke in Sweden, N50 in Norway. The maximum must be at most the
chosen shore tolerance plus **0.1 m** for encoding; the page's 0.000001°
quantum moves a vertex by about 0.06 m, rounded up for this allowance.
Record the longest land run alongside it as information: a gently curved
bank can have a long, shallow excursion within the permitted deviation.
There is no longitudinal land-run gate and no containment-preserving
geometry in this phase. The full tolerance, performance, walking and
reader-facing measurements and the remaining build/drive requirements stand.

**Stopped at the walking price gate, 2026-09-24.** Abisko phase-8 pair 11,
ordinary walking, becomes more expensive on all three rebuilt trial graphs
than its old way priced on the new grid. The decision record's §5 gives the
taps, full prices and a witness priced entirely on the new graph.

| Shore tolerance | New route m | New walking price | Old way on new grid | Excess price |
|---|---:|---:|---:|---:|
| 5 m | 3,716.751661 | 6,558.902738 | 6,539.132686 | +19.770052 |
| 3 m | 3,717.334186 | 6,540.004731 | 6,539.132686 | +0.872045 |
| 2 m | 3,717.334030 | 6,540.004545 | 6,539.132686 | +0.871858 |

Prices are weighted metres. The old route is 3,717.395986 m. A rebuilt
portage intersection moves its walking entry node by 0.587740 m at 2 m;
the old entry remains on the OSM path but is no longer a node offered by the
search. The old way re-priced on the new grid costs 6,539.132686 against
the new answer's 6,540.004545. Even projecting the old entry onto the new
edge and pricing that partial-edge route costs only 6,539.146994. No wet
sample changes on these connectors. **Review must decide how to retain
that cheaper old walking way; phase 9 makes no entry-set/noding decision.**

**Built 2026-09-24 — Checks up to the price stop.** All 600 Abisko kayak
labels at 5 / 3 / 2 m match the unpruned reference. At 0.1 m sampling, the
2 m Abisko shore/bay/portage routes reach 1.865972 / 1.310619 / 1.693186 m
inland, below the 2.1 m gate. The final-graph walking replay stops after
400 Abisko baseline cases and 11 ordinary-walking comparisons; 3/5 m
repeat the failing pair. A Malingsbo-Kloten 5 m page build is terminated
after its graph and heights; the rest of the sweep, reader measurements,
permanent drive reading, final builds and twice-green drives remain
pending. The prototype and evidence stay in the phase-9 scratch directory;
only the records are committed, no tolerance is chosen, and nothing is
pushed or published.

**Review resolved the rebuilt-graph walking gate, 2026-09-24.** Uwe
accepts pair 11: changing graph noding changes the available entry nodes;
the former entry need not remain a candidate. On the final graphs, replay
the same 200 seeded phase-8 pairs per map in both walking settings and
require the pruned search's labels to equal the unpruned reference's.
Only a label mismatch stops this random walking check. Report the count
and largest old-way re-pricing excess as information, alongside the route
change distributions and long-increase explanations. The earlier re-pricing
gate applied to the grid-only comparison. The recorded walking scenes
retain their reviewed length bound; all other phase-9 work stands.

**Stopped after the full tolerance sweep, 2026-09-24.** None of 5 / 3 / 2 m meets both
budgets on all three maps. In particular, Abisko exceeds the 25 % p95-search allowance at
every tolerance. No tolerance is chosen and `SHORE_SIMPLIFY_M` remains 10 m in production.
This is the phase's explicit payload/search stop, not a walking re-pricing stop.

| Map | Tolerance m | Edges | Graph Brotli MB | Page Brotli MB | Page growth MB | p95 ms | p95 growth % | Reference pairs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| abisko | 5 | 105193 | 1.688 | 2.193 | 0.370 | 236.4 | 32.5 | 200/200 |
| abisko | 3 | 127433 | 1.922 | 2.427 | 0.604 | 289.3 | 62.2 | 200/200 |
| abisko | 2 | 148991 | 2.142 | 2.647 | 0.824 | 336.0 | 88.4 | 200/200 |
| malingsbo-kloten | 5 | 288791 | 5.711 | 7.929 | 0.813 | 1400.0 | 31.6 | 200/200 |
| malingsbo-kloten | 3 | 338048 | 6.207 | 8.424 | 1.308 | 1438.6 | 35.3 | 200/200 |
| malingsbo-kloten | 2 | 390280 | 6.712 | 8.931 | 1.814 | 1740.5 | 63.6 | 200/200 |
| lomsdal-visten | 5 | 398191 | 6.017 | 7.725 | 0.640 | 2495.2 | 8.4 | 200/200 |
| lomsdal-visten | 3 | 460768 | 6.653 | 8.361 | 1.276 | 2868.1 | 24.6 | 200/200 |
| lomsdal-visten | 2 | 526246 | 7.295 | 9.004 | 1.919 | 3203.1 | 39.1 | 200/200 |

MB are decimal; graph and page use Brotli quality 11. The graph figure compresses its
compact header/data JSON, including the shared water grid. The same 200 seeded phase-8
coordinates are re-snapped on each graph in Firefox 153.0, after four warm-up cases. The
reported timings are fresh, sequential runs on CPUs 6–7 with no concurrent heavy work. Each
candidate's 200 labels match the unchanged exhaustive reference. Individual timings and page
hashes are retained beside the report. The earlier concurrent timings are retained only as
history and are not used for this budget decision.

Shore deviation below is to the unsimplified source-water union after coordinate encoding,
length-weighted at samples no farther than 2 m apart. Chord dry length is exactly
intersected with that union, including arbitrarily shallow slivers; it describes the whole
candidate catalogue, not a paddled journey. Geometry uses Marktäcke in Sweden and N50 in
Norway.

| Map | m | Shore median / p95 / max m | Shore >1 m inland % | Chord total km | Dry chord km, original / encoded | Encoded longest dry chord segment m |
|---|---:|---:|---:|---:|---:|---:|
| abisko | 5 | 0.902 / 3.460 / 4.994 | 23.700 | 3049.113 | 22.018 / 22.848 | 81.366 |
| abisko | 3 | 0.496 / 2.082 / 3.021 | 14.201 | 3697.288 | 11.140 / 12.287 | 54.912 |
| abisko | 2 | 0.283 / 1.377 / 2.022 | 6.745 | 4257.345 | 6.404 / 7.922 | 45.308 |
| malingsbo-kloten | 5 | 0.911 / 3.446 / 5.012 | 22.609 | 7359.565 | 52.349 / 53.891 | 128.870 |
| malingsbo-kloten | 3 | 0.531 / 2.086 / 3.038 | 13.857 | 9027.674 | 34.784 / 37.433 | 44.499 |
| malingsbo-kloten | 2 | 0.323 / 1.390 / 2.022 | 6.859 | 10586.628 | 24.863 / 28.545 | 43.806 |
| lomsdal-visten | 5 | 0.884 / 3.424 / 5.002 | 23.651 | 12594.286 | 63.115 / 65.352 | 82.607 |
| lomsdal-visten | 3 | 0.520 / 2.073 / 3.021 | 14.247 | 15151.183 | 51.282 / 54.821 | 68.625 |
| lomsdal-visten | 2 | 0.327 / 1.371 / 2.031 | 6.986 | 17456.042 | 41.092 / 46.114 | 79.487 |

The source prototype dissolves delivery and feature pieces on a 1 cm precision grid, before
taking rings. The 1 ha cutoff applies to the area of each connected lake/river/sea union
before clipping to the map; a sub-hectare delivery piece survives when its connected body
qualifies. Lake components retain their separate register/shore-derived planes; river
interfaces and map crops do not become cheap shore. The page grid uses the same water
source, including ponds as before, in both modes. The Swedish trial pages credit “Paddle
water” to Marktäcke Nedladdning, vektor, © Lantmäteriet, CC BY 4.0, and describe
dissolution, simplification and the shared grid. N50 remains Norway's source.

**An independent inland-gate failure remains.** At all three tolerances, Malingsbo-Kloten's
portage scene has a grid-classified straight paddled piece reaching **5.558376 m** inland
near (59.914501001, 15.462782183). It has no graph source in its tally: the 25 m grid, not a
simplified shore edge, classifies this 2.500382 m piece as paddled. The new drive reading
reproduces the failure at 2 m; the same scene's shore and bay pass there at 1.755442 /
1.586538 m. Abisko's new 2 m reading passes all three scenes. No connector, tally,
containment, offset or price rule is changed to make this gate pass. The longest exact land
run is recorded as information, not as a gate, as review decided.

**The recorded walking bound also fails at 2 m.** The drive’s Across Dammtjärnsbäcken goal,
(59.826928, 15.173356) → (59.828695, 15.168055), changes from **356.594924 to 2,343.035623
m** in ordinary walking: **+1,986.440699 m / +557.058 %**, against a **50 m** allowance. The
old direct line has **2 of 15** wet pricing samples on the old grid and **4 of 15** on
Marktäcke. The road now wins by the unchanged walking rule; Stay on paths already took that
road. This is a recorded scene, so the retained length bound applies.
`recorded-river-stop.json` contains both walking settings, page hashes and state-restoration
checks. No replacement drive figure is installed for this unaccepted change.

Reader-facing before/after figures, the screenshot fallback taps, walking distributions and
long-increase explanations are in the decision record and
`~/mockups/kayak-mode/phase9/report.md`. The proposed source code, tests and permanent drive
reading are preserved in `production-prototype-current.patch` and `prototype-current/`
there.

**Build recovery.** The previous concurrent measurement queues exhausted memory; Norway’s
first 2 m build ended with exit 137 during GPX export. That candidate and its partial
measurements were set aside. Its complete rebuild and all subsequent measurements run one
heavy process at a time, with an 8 GiB address-space limit on each Python build and harness.
The timing sweep was repeated under that same sequential constraint.

**Built 2026-09-24 — Nine trial pages for the full sweep.** The three maps at 5 / 3 / 2 m
were built one at a time with `command make map`, which builds the graph before the page,
using cached inputs and a guard against downloads or shared-cache writes. They are
measurements, not accepted final pages. Only the two records are committed; production
source, tolerance and drive figures are restored. Final `command make graph` / `command make
map` builds, the completed join audit, recorded figure updates and twice-green kayak/shore
drives remain pending because no tolerance qualifies. No tile build, push or publication.

**Review must decide:** the payload/search budgets or the extra work allowed to meet them,
the recorded Dammtjärnsbäcken route change under its retained length bound, and how the
inland gate treats grid-classified connectors. The revised walking reference gate stands;
old-way re-pricing causes no stop.

**Validation, 2026-09-24.** `command make hooks-run` is green with network
access: ruff format/check, mypy, both test suites and the standard repository
hooks. This validates the restored production tree and the two records.

**Stopped 2026-09-24 — the walking rule is examined before the build.**
Uwe questioned review's interim choice to keep the coarser Swedish grid for
walking: *“Using a coarser grid for walking feels wrong. If it then no longer
fits, the problem is rather the rule.”* That was a question, not a decision;
review wrongly passed it on as one. Which grid walking uses stays open until
Uwe decides on the walking-rule report; the investigation below measures the
shared Marktäcke / N50 grid against the alternatives. Review's choice of **5 m** shore simplification, its accepted p95
search growth, and the **5.1 m inland gate on network PADDLE edges only**
stand. Grid-classified connectors remain informational. Final timing and
release validation remain pending; the interrupted Abisko build and final
measurement outputs are not evidence.

The rule investigation is `~/mockups/kayak-mode/phase9/walking-rule.md`, with
source, cell, node and browser measurements beside it in `walking-rule/`.
At Dammtjärnsbäcken both sources describe the same `Vattendragsyta`:
**66.651 → 65.975 m** of unsimplified water along the old line. One cell
centre changes sides of the bank, moving **2 / 15 → 4 / 15** wet connector
samples and **47.546 → 95.092 m** priced at 30. Ordinary walking changes
**356.595 → 2,343.036 m**. Exact-width pricing at 30 also chooses the road;
a 10 m width threshold does not make this roughly 66 m crossing narrow.

The frozen recorded inputs have two other material ordinary-walking moves:
Malingsbo-Kloten's helper input **9,287.861 → 9,590.349 m**, and Norway's
typed-coordinate leg **819.932 → 1,066.298 m**. No recorded input exceeds
`max(2 % of old length, 50 m)` with Stay on paths, and none does in Abisko.
The dry Malingsbo-Kloten entry was a portage-created OSM node; Norway’s
old bend was a paddle-only node, now 3.946 m from its nearest replacement,
with an identical water grid. The report lists all taps, separates source
and noding effects, and compares six alternatives with the retained rule
on all 200 seeded random pairs per map in both settings. Imported/restored geometry and helpers whose taps
move with noding are distinguished from fixed-input search comparisons.

**Review must decide:** retain factor 30 and accept the measured recorded
changes, as recommended, or explicitly change walking's water policy. A
smaller global factor also weakens the decided lake/sea avoidance; the
river-only and width-dependent controls are separate policy choices. No
production change or graph/map build is made in this turn. The prototype
is preserved in scratch, and only the records are committed. No push or
publication; there is no final phase-9 built-note.

**Validation of this stop, 2026-09-24.** `command make hooks-run` is green
with network access: ruff format/check, mypy, both test suites and the
standard hooks. Only the two records change.

**Stopped 2026-09-24 — The dissolved shore changes the shore reading.**
Uwe's shared-grid decision above is implemented in the restored prototype.
All three `command make graph` and `command make map` builds completed,
one at a time under the 8 GiB cap, from cached inputs. The final graphs have
105,193 / 288,791 / 398,191 edges (Abisko / Malingsbo-Kloten / Norway).
Abisko's full walking drive passes **327 readings in 21 checks**; its
network-only inland check passes, with shore / bay / portage maxima of
**4.769376 / 4.437900 / 3.930065 m**. Walking's accepted decisions and the
5.1 m inland gate cause no stop here.

Abisko's existing shore pair now paddles **2,167.118276 m**, comprising
**2,133.230886 m Shore + 33.887390 m Open water**, with no land. Its actual
shortest Shore-only reference is **2,676.507469 m**, not the old recorded
2,116.109666 m: the route is **19.031861 %** shorter, beyond the existing
10 % band. Dissolution removes the cheap lake/river interfaces; following
only Shore now traces river banks upstream and back. The drive's zero-chord
and all-Shore-credit assertions fail. Updating the reference also makes
its 10 % assertion fail. Nearest new Shore-node taps, only 0.333 / 0.386 m
away, reproduce the same route; no fixture has been moved to avoid it.

The same three interfaces have coincident Open water copies: the lake
copy belongs to `lake-12`, `Sjö`, level **342 m**; the river copy has no lake
body and retains sampled heights. The assembled profile reads
**342–342.700012 m** over 417 finite samples, failing the existing 0.5 m
whole-route flatness check. Individual lake edges retain their plane.
The plan does not choose which side owns this shared boundary's height.

The detailed report, source geometry audit, taps and raw readings are in
`~/mockups/kayak-mode/phase9/shore-reading-stop.md` and `final/abisko/`.
**Review must decide** how the shore reading treats these inlet-mouth
crossings, and whether an exactly shared lake/river boundary takes the
lake's plane once or retains the river-height copy. The recommendation is
to allow the measured inlet crossings in a lake-bank reading and use the
adjacent lake plane on the exact interface, leaving river interiors alone;
neither change has been made. Final differentials and p95 timing, the
remaining reader/join measurements and twice-green drives remain pending.
Production edits remain uncommitted for review; only the records are
amended at this stop. No push or publication; phase 9 is not complete.

**Validation of this shore-reading stop, 2026-09-24.** `command make hooks-run`
is green with network access, including ruff format/check, mypy, both test
suites and the standard hooks. The first run found a list/array variable-name
reuse in the new inland reading; renaming that local fixes mypy without
changing its measurement. Logs: `~/mockups/kayak-mode/phase9/shore-stop-hooks.log`
and `shore-stop-hooks-fixed.log`. This validates the uncommitted prototype;
it does not replace the incomplete final browser checks above.

**Stopped 2026-09-24 — The finer surface bypasses the dam and changes the MK scenes.**
All six graph/map builds completed sequentially under the 8 GiB cap. Shared
mouths now have one lake-level copy: graph edges change **105,193 → 105,062**
in Abisko and **288,791 → 288,600** in Malingsbo-Kloten; Norway's **398,191**
edges and encoded graph are unchanged. The source audit finds zero remaining
duplicate lake/river chord copies, removing **3,306.252 / 2,779.675 m**.
Abisko's fixed pair passes the revised behaviour: **2,116.110 m** old reference,
**2,676.507 m** new Shore-only reference, **2,167.118 m** new bank reference and
route; mouth deviation **0.050776 m**, all **417** profile samples at **342 m**.
Its full walking drive passes **327 readings / 21 checks**. All three maps'
scene triples pass the network inland gate; MK's carry has no network paddle
geometry, so its **5.558376 m** connector deviation remains information.

A genuinely new conflict is the mapped Korslång dam at **(59.947644305,
15.255897765)**. The unchanged channel pair now paddles **1,297.899 / 0 m**
paddled / on foot, both ways, instead of **1,267.848 / 77.105 m**. An Open water
edge passes **0.026292 m** from the dam point; **56.729230 m** of used network
water lies in its 25 m neighbourhood, versus zero before. Marktäcke covers the
dam point; Topografi 50 did not. The cut stream geometry is unchanged, but the
new surface supplies another paddled way through the structure. This also
happens before the interface-height fix. Preserving the carry needs a decision
on the surface barrier's extent and on kayak connectors, not just a stream cut.
No dam footprint or new connector rule has been invented here.

MK's fixed shore pair now gives **1,904.659 / 5.025 m** against a **4,335.576 m**
Shore-plus-interface reference, **56.069 %** shorter. Its **7.905 m** Open water
piece is within **2.619 m** of the bank but not an inlet interface; its long
connector reaches **251.918 m** from the bank. Even allowing bank-adjacent
chords gives a **4,327.860 m** reference. Moving the endpoint **22.215 m** to the
nearest Shore node still takes **833.338 m** of Open water. The old portage
scene becomes **27.504 / 917.640 m**, entirely classified straight geometry,
instead of **1,414.654 / 513.463 m** with a routed carry. These pairs no longer
exercise the assertions they were selected for. Review should permit new MK
bank/carry fixtures while retaining these original-tap before/after readings;
Abisko's fixed pair stays as decided. The prices remain unchanged.

The corrected join audit ran on the rebuilt graphs. Matching old stream joins
found one Abisko direct join whose stream still shares an undirected paddle
component with water, and three MK stream pieces that do not: near **(59.758503, 15.163257)**,
**(59.950575, 15.032432)** and **(59.984282, 15.005697)**. Their gaps to the surface
network are **4.615 / 0.462 / 0.574 m**; the latter two have only sub-metre
portages. Their water bodies exceed 1 ha. These joins still need re-derivation
under the existing phase requirement; re-running intersections alone did not
suffice. Direct same-stream join movements and portage landing measurements
are retained in the report, without claiming nearest features are identities.

The full report is `~/mockups/kayak-mode/phase9/mk-reading-stop.md`; the fixed
scene triples, Korslångssmedja, screenshot fallback and phase-2 legs are in
`final-reader-table.md`. The fixed Korslångssmedja pair changes **4,296.406 →
4,419.018 m** paddled, zero on foot. At the screenshot fallback, the whole
route's maximum inland distance changes **12.973199 → 4.913701 m**. Original
screenshot taps could not be recovered. The final measurement queue stopped
between jobs; final differentials, fresh p95 timing and twice-green release
drives remain incomplete. This is a records-only stop, with the production
prototype preserved in the worktree and scratch; no final phase-9 release,
push or publication.

**Validation of this stop, 2026-09-24.** `command make hooks-run` is green
with network access: ruff format/check, mypy, both test suites and all standard
hooks. The test suites passed 2,028 library tests and 97 pipeline tests. The
first hook run also passed the tests, but correctly rejected a concurrent
record edit; the clean rerun left all files unchanged. Logs are
`~/mockups/kayak-mode/phase9/hooks-mk-stop.log` and `hooks-mk-stop-green.log`.
This validates the preserved prototype, not the incomplete final browser
checks above.

**Built 2026-09-25 — Phase 9, finer water and carries at dams.**

Uwe’s shared-grid decision (“So wie vorgeschlagen”, 2026-09-24) and review’s 5 m tolerance,
mouth-interface rule and dam/fixture decisions are implemented. Sweden uses dissolved cached
Marktäcke for paddle surfaces and the shared grid, credited as © Lantmäteriet, CC BY 4.0;
Norway retains N50. The connected-body 1 ha rule is applied before map clipping. Walking
factor 30, midpoint pricing, kayak prices and phase 7’s height rule remain unchanged. No
offset or centre-line work is included.

The complete 5 / 3 / 2 m tolerance table above remains the sweep evidence. Review selected 5
m despite its original +32 / +32 / +8 % p95 growth, noting phase 8’s MK reduction from 4.1 s
to 1.1 s. These fresh final-graph figures include the shared grid, explicit stream joins and
kayak dam-disc sampling:

| Map | Edges | Graph Brotli MB, before → after | Page Brotli MB, before → after | Page growth MB | Kayak p95 ms, before → after | Growth | Reference pairs kayak / walking / paths |
|---|---:|---:|---:|---:|---:|---:|---:|
| abisko | 105088 | 1.320681 → 1.683781 | 1.822895 → 2.188990 | 0.366095 | 181.150 → 261.350 | +44.27% | 200 / 200 / 200 |
| malingsbo-kloten | 289548 | 4.897322 → 5.724069 | 7.116118 → 7.943361 | 0.827243 | 1016.850 → 1709.400 | +68.11% | 200 / 200 / 200 |
| lomsdal-visten | 398191 | 5.376381 → 6.016864 | 7.085092 → 7.727324 | 0.642232 | 2085.400 → 2772.950 | +32.97% | 200 / 200 / 200 |

MK has 108 dam/lock points and 98 discs meeting eligible water. Before the circular cut, 847
PADDLE edges entered discs; the final graph has none. Both Korslång channel directions now
paddle 1,184.863 m and carry 115.352 m on the existing OSM path and inferred ties (0 m of
PORTAGE-kind edges). The three identified MK stream pieces are attached and their directed
reachability is verified. Shared lake/river interfaces have one lake-level copy; Abisko’s
bank profile reads 342 m at all 417 samples.

The retained fixed reader pairs, screenshot fallback, scene triples and phase-2 legs are
tabulated in the decision record. MK’s replacement bank fixture paddles 831.576 m on Shore;
its new routed-carry fixture paddles 619.511 m and carries 46.348 m, with network paddle on
both sides. The original bank/carry taps remain in the before/after report and walking
retains its original shore taps. The screenshot’s maximum whole-route inland deviation falls
from 12.973199 to 4.913701 m. Abisko retains the old 2,116.110 m reference, the new
Shore-only 2,676.507 m reference and the actual 2,167.118 m route in that report.

All 1,200 random walking replays are reported: 542 change, 293 longer and 249 shorter, with
per-map/mode distributions and every material increase’s taps and explanation. Old-way
re-pricing is informational. Uwe’s three accepted intermediate walking changes remain
recorded; final dam noding brings the MK helper to 9,284.155 m, within 3.706 m of its
original length. Dammtjärnsbäcken remains 2,343.036 m and Norway’s typed leg 1,066.298 m.
Exact-width or finer-cell pricing remains a later improvement.

All 1,800 final search labels equal the unpruned reference. The 0.1 m sampled, 5.1 m
network-inland gate and existing kayak checks pass twice per page; connector inland
distances and longest land runs are recorded as information. Complete walking readings pass
with the measured figure updates and phase-9 notes. The final six builds and all harnesses
run one heavy process at a time under the 8 GiB cap. `command make hooks-run` is green with
network access. Full measurements, changed stored figures and evidence paths are in the
phase-9 built note of `kayak-mode-decisions.md` and `~/mockups/kayak-mode/phase9/`. These
results close the historical stops above. No tile build, source download, shared-cache
write, push or publication.

### Phase 10 — Carry on paths, launch at road ends

**Uwe's decisions, 2026-09-25, translated.** "Also with the kayak, paths are to be
preferred. Pathless is even harder with a kayak. I would rather follow a path for
200 m than drag 20 m over a bog. Only the last few metres are always fine."
"Can't we leave it exactly as for walking?" Ground factor **10**, last metres up
to **30 m**, and the compact panel figure fixed. The fixed 10 is superseded by
his subsequent switch decision below; the 30 m and panel decisions stand.

**Uwe's revised decision, 2026-09-25.** After asking what Kayak together with
Stay on paths means: *"Sollten wir das dann nicht doch so für Kajak machen?"*
— *"Ja"* ("Shouldn't we then do it that way for kayaking after all?" — "Yes").
Ground follows walking's `offPath()`: **3 with Stay on paths off,
10 with it on**. This replaces the phase brief's fixed 10. Stay on paths remains
visible in kayak mode; the interim idea of hiding it is dropped and is not built.

**Uwe's topology decision, 2026-09-25, superseding review.**
*"Ja ich finde das tatsächlich eine Verbesserung. Lasse Codex das so machen."*
— "Yes, I actually think that is an improvement. Let Codex do it that way."
Launches may split walking edges. The explanation was the **55.990 → 68.341 m**
walking case: a new entry offers about **25 m ground + 43 m road**, costing
**132 instead of 168** under the unchanged walking rule. Walking can use the
new junction; the launch itself remains kayak-only. This supersedes review's
existing-nodes-only restriction, not Uwe's 3/10 switch decision.

Walking differentials must match the exhaustive reference on the new graphs:
200 pairs per map in both settings. Random-pair changes are reported as a
distribution. Every moved recorded walking reading gets before/after figures
and a reason. A reading stops the phase only when its length moves beyond
max(2 %, 50 m) **and** its new way is not cheaper than the old way re-priced on
the new graph. Longer path carries are expected in kayak; p95 is reported in
both settings and stops only if it more than doubles.

**The rule.** The primary kayak objective becomes land price: walked metres times
the unchanged walking source factor, ground connectors and PORTAGE edges times
`offPath()` (3 or 10), paddle and ferry edges zero. The secondary price
stays as before, including P = 2, shore 1 and open water 1.5. No path discount or
additional price constant. Water still wins against any positive land price.
Walking prices remain unchanged; Uwe accepts the new walking entry nodes below.

Build launch ties at walking degree-1 road/path ends within 30 m of paddle water,
and at nearby passing roads where another tie does not already serve that shore.
Measure and justify the proposed 100 m shore spacing. Ties run over land, avoid
other water bodies and phase-9 dam discs, and join the shore. Uwe allows a passing-road launch to split the road at its nearest point;
the shore is re-noded where needed. They cost factor 1 in both objectives and are unreachable and unsnappable
on foot. A separate `Launches` source of kind `LAUNCH` keeps that price distinct
from `PORTAGE`: the old Portage paths are inferred ground, priced by `offPath()`.
Launches have no selectable chain and are tallied as undrawn carry. Measure
counts, lengths, dead-end/passing origin and new access within 500 m per map.
The compact kayak line must show the whole length and the paddle/foot split,
matching the heading's `2.47 km 🛶 · 3.51 km 🚶` form; walking keeps its plain figure.

Both switch settings must be measured for the Kloten start, phone-2, the scene
triples and all 200 seeded kayak pairs per map: changed answers, carry/paddle
totals, largest increases, pruned/reference equality and p95. The kayak drives
state and restore their switch setting. A measured ground-versus-path example
must show the switch changing the kayak route, if such a scene leg exists.

**Stopped 2026-09-25 — Shared launch noding changes walking.** The existing build
nodes every source together (`network/water.py:build`, `routing/graph.py:build_network`).
Making a tie kayak-only does not make its road junction kayak-only. Walking's
`joinedRoute` offers entry/exit connectors at every graph node; `snapped` also
prefers a nearby eligible junction over a point along an edge. A split road node
is eligible because it has walking edges, even when the launch itself is excluded.

A browser diagnostic on the existing Malingsbo-Kloten page splits road edge
45003 at **(59.897876698495, 15.288431594724)**, the nearest road foot opposite
shore node 93159. Their metric gap is **6.443628 m**. It changes only that road
split, first without a tie, then with a PORTAGE-kind diagnostic tie that is
unreachable on foot. Both variants give the same walking changes:

| Fixed input | Walking before → after m | Stay on paths before → after m |
|---|---:|---:|
| East of launch → phone-2 junction | 55.990099 → 68.341328 | 55.990099 → 68.341328 |
| Phone-2 1→2 | 175.288968 → 175.288968 | 175.288968 → 175.288968 |
| Phone-2 2→3, snapped in walking | 43.164309 → 43.153989 | 43.164309 → 43.153989 |

The first input is **(59.897876698495, 15.288881594724) →
(59.897507, 15.288204)**. Its start remains off-network at the investigation's
7.188 m snap reach. The new answer uses **25.187339 m** of ground and
**43.153989 m** of the road, with no launch edge. Ordinary walking's price falls
**167.970298 → 131.662202**; Stay on paths falls **559.900994 → 307.973575**.
The phone-2 2→3 change is a snap to the new road node instead of its former
partial-edge point. All **12** before/after labels in the tie variant match the
unpruned reference. This is a change in available walking ways and snaps, not
a pruning defect or a price change.

**Topology question at the first stop, resolved by review below.** Retaining byte-identical walking
requires preserving the pre-launch walking entry set, snapping and edge geometry
while exposing the new junctions to kayak routing. Merely excluding the launch
kind, or hiding its nodes from snapping, does not do that. The alternative is to
accept and measure walking changes from shared noding, which the phase currently
forbids. The recommendation is to retain the walking invariant and explicitly
include mode-specific routing topology; it is not a decision attributed to Uwe.

**Build status at the first stop, 2026-09-25.** Records only; phase 10 is not built. The diagnostic
is an in-memory split of an existing page, not a generated launch catalogue or
a validated production tie. No production prices, topology, panel or drive
figures have changed. Graph/map builds, per-map launch measurements, the full
reader/600-pair comparison, walking differentials, p95 timing, twice-green
selected drives and `command make drive-all` remain pending this stop. Scratch:
`~/mockups/kayak-mode/phase10/`, particularly `noding-summary.json`, `noding.js`
and `noding-with-tie.json`. Each browser harness is capped at 8 GiB, runs alone
and restores borrowed modes; no goal or saved plan is changed. No cache write,
source download, tile build, push or publication.

**Validation of this stop.** `command make hooks-run` is green with network
access: ruff format/check, mypy, tests and the standard repository hooks.
Log: `~/mockups/kayak-mode/phase10/hooks.log`. This checks the unchanged
production implementation and the records; it does not complete phase 10.

**Review decision after the stop, 2026-09-25 — Existing walking nodes only.**
Walking stays byte-identical. Dead ends already have nodes. A passing road uses
an existing walking node within 30 m of water; if none exists there, that place
gets no launch. No walking edge is split for a launch. Compare the lost passing
locations with the splitting prototype, and check phone-2 and the Kloten northern
shore first. If they do not get a launch this way, stop with the figures for Uwe
to decide whether walking may change. This is review's topology decision,
separate from Uwe's switch-price decision.

**Measured after review, 2026-09-25 — No launch at the original short landing.**
The nearest existing walking node to both original landings is road junction
**33831**, phone-2's point 2. It is **42.075943 m** from unsimplified source
water, outside 30 m. The next junction, **33832**, is **50.845958 m** away.
Neither is a degree-1 road end. The splitting diagnostic's road foot at
**(59.897876698495, 15.288431594724)** therefore cannot be retained as a launch
start. There was **one** investigated splitting site: **one original location
lost**, at the southern tip of Sågviken, shared by the phone-2 and Kloten
northern-shore examples. This is the comparison with that diagnostic, not a
map-wide launch count; no three-map splitting catalogue was built.

There is a **farther alternative on the same road**, which must not be reported
as an absence of all access to the bay. Existing junction **24433** at
**(59.899237772676, 15.289714526724)** is **19.968740 m** from source water and
**20.368276 m** from the simplified paddle shore. Its nearest existing shore
node is **93164**, displayed at **(59.899302, 15.289356)**. The encoded-node tie
is **21.320689 browser metres** (**21.312238 m** in EPSG:3006), intersects
**0 m** of cached unsimplified water and is over 4.4 km from the nearest dam
centre. No edge split or new node is needed for this alternative. It lands
**191.706571 browser metres along Shore** from phone-2's point 3. Thus the
original location is lost, while this road still has one confirmed farther
candidate; these are different counts.

A browser-only experiment adds that tie at factor 1 in both objectives and
uses the newly decided `offPath()` primary. The existing page, prices and graph
are restored afterwards. Figures below are physical carry/paddle lengths using
the router's connector samples, not the profile's finer displayed split.

| Pair | Before, carry / paddle m, either switch | New rule + farther tie, switch off | New rule + farther tie, switch on |
|---|---:|---:|---:|
| Kloten P1 → northern shore | 231.408 / 0 | 411.031 / 620.694 | 411.031 / 620.694 |
| Kloten P1 → P2 proxy | 411.031 / 7,088.969 | 411.031 / 7,088.969 | 411.031 / 7,088.969 |
| Off-road start → P2 proxy | 196.753 / 6,920.200 | 399.583 / 7,088.969 | 399.583 / 7,088.969 |
| Phone-2 1→2 | 173.877 / 0 | 175.289 / 0 | 175.289 / 0 |
| Phone-2 2→3 | 43.272 / 0 | 43.272 / 0 | 233.680 / 191.707 |

Phone-2's 1→2 follows the road in **both** switch settings. Its 2→3 supplies
a measured switch-sensitive example with the farther tie: off, the straight
connector has land price **129.814548** and wins; on, its price is
**432.715161**, so the road and launch at **297.388133** win. The carried
233.680 m includes the 21.321 m tie. The Kloten P1 routes and off-road start
still leave on the west; none uses this tie. For P1, the known road way via
the farther tie has land price **525.263792**, against the western way's
**482.156276**. The unchanged walking factors, not a failed connection, choose
the west. All **30** local labels match the unpruned reference within `1e-8`.

**Stopped at the requested landing check.** There is no qualifying existing
walking node at the original short-launch location. The farther tie is a real
alternative and helps phone-2 with Stay on paths, but does not change the
Kloten P1 departures. These figures are returned to Uwe to decide whether to
accept that relocated access or allow walking noding to change for the short
launch. The earlier topology question is resolved by review's existing-node
rule; no separate walking graph is proposed at this stop.

**Build status at the landing stop.** Records and scratch diagnostics only. The revised switch
rule and launch rule are not implemented in production. The three-map launch
catalogue, counts and spacing, full reader comparisons, both-setting seeded
kayak differentials and p95, walking-invariance checks, graph/map builds,
selected drives and `drive-all` remain pending. No panel figure or drive
snapshot changes. Evidence is under `~/mockups/kayak-mode/phase10/existing-nodes/`,
especially `audit.json`, `route-summary.json` and `routes-checked.json`.

**Validation of the landing stop.** `command make hooks-run` is green with
network access: ruff format/check, mypy, tests and the standard hooks. Log:
`~/mockups/kayak-mode/phase10/existing-nodes/hooks.log`. This validates the
records and unchanged production tree, not the unbuilt phase-10 changes.

**Built 2026-09-25 — Carry on paths, launch at road ends.** The primary
kayak label is now walking land price, with `offPath()` at 3 / 10 and zero
for paddle and ferry edges. P = 2 remains only in the secondary price.
Stay on paths stays visible. `Launches`, a separate `LAUNCH` kind, costs 1
in both labels; `PORTAGE` keeps its ground price. Walking cannot use or snap
to a launch, but can use the new road junctions Uwe accepted.

Launches use degree-1 walking ends and the nearest points of passing paths,
within 30 m of the shore. They reject source-water crossings and the existing
25 m dam discs. Projected endpoints are joined explicitly within the existing
centimetre noding tolerance, including to full path geometry: floating-point
overlay alone can leave a shortest-line endpoint disconnected. All retained
ties were audited from a walking node through launch edges to paddle shore.

The measured **100 m** shore spacing is retained. Across the three maps,
50 / 100 / 200 m produce **6,133 / 4,395 / 3,111 ties** and
**1,987 / 1,464 / 1,058 new access points**. The 100 m catalogue has 28% fewer
ties than 50 m and 74% as many new access points; 200 m reduces new access by
another 28%. These are separate catalogue counts, since candidate subdivision
follows the spacing. Distance is along the bank, with dead ends kept first;
existing road/shore junctions also occupy the bank. This spacing is an
implementation choice justified by the sweep, separate from Uwe's price and
topology decisions.

| Map | Launch ties | Dead ends / passing | New access within 500 m | Length min / median / p95 / max m |
|---|---:|---:|---:|---:|
| Malingsbo-Kloten | 2,220 | 269 / 1,951 | 808 | 0.059 / 12.514 / 27.792 / 29.997 |
| Abisko | 350 | 21 / 329 | 162 | 0.137 / 13.376 / 26.825 / 29.973 |
| Lomsdal-Visten | 1,825 | 404 / 1,421 | 494 | 0.013 / 11.167 / 27.601 / 29.973 |

New access means that the old land network, including inferred portages,
could not reach the same undirected paddle component within 500 m. It
excludes off-network connectors; it is not an upstream reachability claim.

The original short Kloten landing is now a **passing-road launch**: walking
node **141123**, **6.085713 m** from source water, joins shore node **94456**
over **6.413967 m** (**6.405672 browser metres**). Both phone-2's 2→3 and
P1→northern shore use it in both settings. Phone-2's 1→2 follows **175.289 m
of road** with the switch either off or on. Its 2→3 is **43.178 m road +
6.406 m launch**. P1→northern shore becomes **224.873 m carry + 28.514 m
paddle**. The nearby measured switch example trades **88.881 → 14.913 m**
of straight ground for **52.325 → 300.100 m** of road.

The compact kayak line now says the whole length and the split, in the
heading's form, for example `7.50 km · 7.10 km 🛶 · 0.40 km 🚶`. It wraps
between complete distance chunks on a phone. Walking keeps its plain figure.
The old shortest-carry drive is renamed `a_carry_uses_walking_prices`; the new
readings cover road launches, the switch-sensitive carry and the full compact
line. Each reading states and restores its switch setting and borrowed page
state.

The [phase-10 measurements](kayak-mode-phase10-measurements.md) contain both
settings of every scene triple, the Kloten starts, phone-2, the phase-2 sweep,
Korslångssmedja, all seeded-pair totals and distributions, the largest increases,
and every moved recorded walking way with its old-way price comparison.

All **1,200 kayak** and **1,200 walking** comparisons match the exhaustive
reference: 200 pairs per map in both settings. All **264 frozen recorded
walking readings** pass the old-way price gate; **103** change when rounded
to three decimals and are listed in the measurements. The two beyond the
distance threshold are cheaper under the unchanged rule. The additional
fixed reader legs pass that gate too. Walking random-pair changes are
reported as distributions, without a stop gate.

| Map | Kayak p95 ms, switch off, before → after | Switch on, before → after |
|---|---:|---:|
| Malingsbo-Kloten | 1,637.55 → 2,155.05 | 1,678.40 → 2,015.00 |
| Abisko | 239.60 → 347.30 | 235.30 → 357.55 |
| Lomsdal-Visten | 2,771.40 → 3,474.50 | 2,872.35 → 3,366.35 |

No p95 more than doubles. The largest carry increase is **36,995.003 m**
on Norway pair 198 with Stay on paths on, **41,946.522 → 78,941.525 m**.
Longer path carries are Uwe's accepted choice; the complete carry, paddle and
ferry totals and the largest whole-route increases are reported separately.

**Drive.** The selected readings are green twice per page: **310 / 210 / 214**
readings per run. The complete `command make drive-all` run is also green:
**1,708 / 1,634 / 1,641** readings, **4,983** in all, with no broken invariants,
moved figures, unrecorded figures or undeclared skips. Full-suite review
updated the dry-profile sample-count hashes, the renumbered long-road tap
fixture and the measured scene figures, with their before/after values in
the measurement record. The existing gates and tolerances stand.

**Validation.** `command make hooks-run` is green with network access:
ruff format/check, mypy, both pytest suites and the standard hooks. The
measurement record explains the corrected type annotations and scratch-harness
failures as well as the full-drive snapshot updates. All graph and map builds
ran one at a time with an 8 GiB address-space cap, using cached inputs. No tile
build, push or publish was made. Phase 10 is complete; no further decision is
required and no later phase is started.

### Phase 11 — Enter an edge in its middle

**Uwe's words, 2026-09-25, translated.** "Now it takes the way I wanted, but
only when the pin is right on the path. If it is only slightly beside the
path, the old roundabout way is chosen. Is that fixed by entries inside a
path?" Earlier: "What would it cost to allow arbitrary entries into a road?"
Then: "Yes, let's do the entries first." The approved offset-line work waits.

The report is `~/mockups/kayak-mode/kloten-start/report.md`, its final section,
"Phase 10 follow-up: a start just beside the rental road". All 56 old answers
match the nodes-only reference. Outside the finger reach, the nearby road's
interior is unavailable: P1 is 56.219 m from its southern node and 166.142 m
from its northern node along the road. The temporary entry goes north in all
24 distinct off-network cases. This is an entry-set limitation, not a price
or pruning defect on those inputs.

**Review's decision, not Uwe's.** The same entries apply to walking with
Stay on paths off and on. A separate walking rule would give one network two
models of entry. Walking changes are accepted when the new candidate is
strictly cheaper under its unchanged objective, and must be reported.

**The rule.** An off-network endpoint may enter any usable edge between
consecutive geometry vertices and leave in each direction `allowed` permits;
an off-network target has the mirrored exits. Keep all existing node
candidates. For each segment and allowed direction add the clamped dry-ground
optimum. With edge rate `f`, ground rate `g`, perpendicular foot `s₀` and gap
`d`, it satisfies `cos θ = f / g`:
`s = s₀ ± d × f / sqrt(g² − f²)`. If `f ≥ g`, use a segment end. These are
rates of the minimised objective: land price in a kayak, cost when walking.
Each candidate is priced exactly by the existing `connectorPrice` and its
25 m grid, including kayak dam discs. The analytic point is the **dry-ground
optimum**; a connector crossing water is priced correctly but may miss a
slightly better point on that segment. Include the piece between two middle
points on one edge and ways through edges that meet.

No new price constants, factors, objective, snap reach or grid. Attached
endpoints keep `endsOf`; `worthRouting` keeps its whole-leg fallback. Only
strict improvements may replace old answers. Draw and export the connector
and partial edge, including both in the panel's total and paddle/foot split.
Stored-plan restoration stays as it is; the measurement file explains it.

**Validation required.** Preserve the phase-10 sample and add a second,
documented off-network sample, using seed 20260923. The new sample needs
2,400 comparisons against independent unpruned references: 200 pairs per
map in kayak, kayak-paths, walking and paths. Report before/after p95 on
both samples in every map and setting. No p95 may more than double;
Lomsdal-Visten walking must not get slower. Profile its slowest pairs and
fix entry/connector costs here without changing answers. Pin all 24 new
Kloten answers and keep the 24 attached answers unchanged.

**Drive required, not yet run.** E8 at z17, as a raw tap in both settings,
must reach Q over the northern launch at road node 141123. Compare W8 at
z16 and z17, reporting the measured tolerance. Read a walking road-interior
entry, the drawn connector, panel split and export. Update moved scene
figures with a phase-11 note; selected kayak/entry checks must pass twice
per rebuilt page, then `command make drive-all` once. No graph or tile build.

**First prototype, stopped 2026-09-25 — history.** On Abisko's
unchanged 200 phase-10 pairs in kayak mode with Stay on paths off, warm
Firefox p95 changes **334.05 → 1,084.15 ms**, **3.245×**, above the permitted
2×. Median changes **34.5 → 237.5 ms**, worst **510 → 1,707 ms**. Baseline
and proposed searches alternate on the same decoded page, after warming
both; no other build or browser measurement runs beside them.

The prototype gives the northern launch in all 24 distinct off-network
Kloten cases. E8/off to Q carries **231.360461 m**, with land price
**313.813413** and secondary price **649.735444**. Across the 24 rows,
differences from the virtual table are at most **0.000029 m carry**,
**1.77×10⁻⁹ land price** and **3.55×10⁻⁹ secondary price**. This local result
does not establish the full reference gate.

**Build status at the stop.** Production source and tests are restored;
only the records change. The prototype, reference draft and browser evidence
are in `~/mockups/kayak-mode/phase11/`. The remaining settings/maps, second
sample, complete reference comparisons, pinned tests, builds and drives
are pending the failed speed gate. No scene figure changed. The
[phase-11 measurements](kayak-mode-phase11-measurements.md) give the timing
method, Norway profile, restoration behaviour and precise remaining work.
Review subsequently requested lazy candidate discovery, keeping the entry
rule and speed gate unchanged; that attempt is recorded below.

**Validation of the stop.** `command make hooks-run` is green with network
access: ruff format/check, mypy, both pytest suites and the standard hooks.
This validates the restored production tree and records, not the prototype.
Log: `~/mockups/kayak-mode/phase11/hooks.log`.

**Review's follow-up, 2026-09-25.** Generate entries as their permitted end
nodes settle; reject whole edges by a bounding-box floor before expanding
segments. Queue exits lazily by edge-box floors, preserving every seed that
can win. Check same-edge ways locally, restore a whole-network dry-box entry
floor, and permit walking midpoint batching only after equal wet counts and
unchanged answers are demonstrated. Measure Abisko kayak first, then stop
again with a profile if the unchanged gate fails.

**Second prototype, stopped 2026-09-25 — lazy discovery still exceeds the
gate.** Abisko kayak, the same 200 phase-10 pairs: p95 **338.30 → 1,671.20 ms**,
**4.940×**; median **33 → 294.5 ms**; worst **526 → 2,461 ms**. The prototype
caches geometry and an edge-box hierarchy in the router, uses sparse query
caches, defers exit expansion through the floors queue, and tests incident
entries at settled nodes. Its common entry floor includes segment interiors
and the dry box's midpoint-sampling allowance. The prototype also checks a
matching entry when an exit expands, because a winning interior-to-interior
route need not reach either real endpoint. This scheduling choice can
expand source candidates before any real node settles.

On each of the five slowest pairs, the lazy queue nevertheless expands all
**105,690** usable edges. Pair 78 expands **151,385 segments on each side**,
with **300,513 connector calls**. Its instrumented total is **3,123 ms**:
**2,113 ms** inside exit expansion, including **1,354 ms** in same-edge checks;
connector pricing across the search takes **1,812 ms**. These nested times
overlap. The weak box floors leave the full network eligible; deferring the
work has not eliminated it. The [measurements](kayak-mode-phase11-measurements.md#lazy-prototype-follow-up)
give the bounds and all five profiles.

**Build status after the second stop.** Not built. Production source and
tests remain unchanged. The frozen lazy prototype and evidence are under
`~/mockups/kayak-mode/phase11/lazy/`. The remaining timing cells, second
sample, reference comparisons, walking midpoint-count audit, regressions,
builds and drives were not started past the failed first gate. No candidate,
price or gate decision is changed; candidate discovery still needs work.

## 5. Not in this plan

- Sea kayaking's own concerns — wind, exposure, tides — nothing here prices them.
- Rapids as a grade; a class-2 river is paddleable in this plan wherever it is not a dam, and
  from phase 7 both ways wherever it does not fall.
- Class-1 streams; a canoe on a brook is the reader's own judgement, and 3,359 km of ditches
  would be a network of nothing.
- Norway's stream lines, unless phase 1 finds a size class.
- The atlas; the water network goes there with `libs`, the page does not.

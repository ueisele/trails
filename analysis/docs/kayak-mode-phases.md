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
0 → { 1 ∥ R } → 2 → 3 → 4 → 5. (R found no lines, so there is no 6.)

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
3. **Direction.** The arc table honours a one-way edge: the arc from `to_node` back is not
   filled for it. Nothing else in the search changes.
4. **Snapping.** `nearestOnNetwork` and `endsOf` take `PADDLE` edges in the kayak mode and
   skip them in the walking modes, as they skip a ferry today, so a tap on a lake in the
   walking mode still means open ground and in the kayak mode means the shore.
5. **The sweep.** k and P on the Malingsbo-Kloten page over the three legs of §1.3, with the
   page driven (`command make drive` machinery or a Playwright script beside it in
   `~/mockups/kayak-mode/`), k at 1.2, 1.5, 2, 3 and P at 2, 4, 8, the answer per leg in
   metres over water and on foot and the time the search took. The figures that give Uwe's
   four sentences at a cost a drag can carry go into `OPEN_WATER_FACTOR` (with a note that the
   graph is rebuilt in phase 5) and `portageFactor`; the sweep goes into the record.

### Phase 3 — What a paddled way says

*Files: `plan_mode.js`, `profile_panel.js`, `maps.py` by region (the words), tests. The dry
case is byte-identical: `a_dry_way_keeps_its_words` and the phase 9 readings stay green.*

1. **Parts.** A routed part over `PADDLE` edges and, in the kayak mode, a straight part the
   grid holds as water are parts of kind `paddled`: heights sampled from the tiles like a land
   part (the lake's plane, so the profile is flat over water and climbs on the portage), their
   metres counted into `crossed` and not into `total`, a leg over land in the kayak mode a
   land or routed part as today. Rivers waded stay on foot in the walking modes; in the kayak
   mode a class-2 river is paddled and a river surface is water.
2. **The heading and the figures page.** In the kayak mode the heading leads with the water,
   *12.30 km 🛶 · 0.80 km 🚶*, the figures page and the file's description say *by kayak* and
   *portage on foot*; in the walking modes the words of phase 9 stand.
3. **The files.** A paddled part is written into the GPX track and the Garmin course as the
   way it is, unlike a ferry, and the description says which metres were paddled. Stations
   on the water are anchored to the track, since now there is one under them.

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

### Phase 5 — Rebuild, drive, publish

The three graphs and pages rebuilt on this box (`make graph` and `make map` per map, the last
two steps of each map's chain in the Makefile — not the tiles), `drive-all` green, the three maps
published with `just deploy --map <map> --tree packs` from `home/trails-map`, read back
byte-identical, then Uwe's phone: the switch, a bay, a portage.

### Phase 6 — Named canoe trails (only if phase R found lines)

A source of `PADDLE` kind with names and links, like the Bergslagsleden off OSM's relations,
from whatever phase R found. Planned when R reports.

## 5. Not in this plan

- Sea kayaking's own concerns — wind, exposure, tides — nothing here prices them.
- Rapids as a grade; a class-2 river is paddleable in this plan wherever it is not a dam.
- Class-1 streams; a canoe on a brook is the reader's own judgement, and 3,359 km of ditches
  would be a network of nothing.
- Norway's stream lines, unless phase 1 finds a size class.
- The atlas; the water network goes there with `libs`, the page does not.

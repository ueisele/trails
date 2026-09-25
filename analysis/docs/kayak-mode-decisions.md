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
- **k and P — 1.5 and 2.** The three-leg browser sweep settles these prices; review accepted them. `OPEN_WATER_FACTOR` keeps 1.5 and `PORTAGE_FACTOR` supplies 2. Measurements and the phase 2 built note are under §5. Phase 8 supersedes their water-versus-land trade; phase 10 prices land by walking's rule. They remain secondary prices after land price.
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
  as the reason for retaining 10 m at that stage; phase 9 supersedes it with
  5 m after the finer-water sweep and review’s acceptance of the search growth.
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
  "Ja mache das." — **Built and published 2026-09-22**; the counts were the harness's
  error, the rises are few and unopposed by any arrow, the gate reads the chain (§5). Open:
  Uwe's phone reading of the channel.
- **Lomsdal-Visten has no stream edges at all** — not a defect: N50's `vannbredde` codes
  were never matched to Topografi 50's class 2 (above), so Norway's streams stayed out.

## 5. Changes

- 2026-09-25 — phase 10 is built: kayak land price follows walking, ground follows Stay on paths at 3 / 10, and 4,395 path-priced launches join nearby roads to shore. Uwe accepts the shared road noding. The compact line counts the whole way with its split. All 2,400 kayak/walking labels match in both settings; the largest kayak p95 increase is 52%. The measurements and build note are below.

- 2026-09-25 — Uwe accepts launch splits of walking edges: "Ja ich finde das tatsächlich eine Verbesserung. Lasse Codex das so machen." The new entry makes the 55.990 → 68.341 m example cheaper by the unchanged walking rule (132 against 168). This supersedes review's existing-node restriction; walking differentials remain gates, while cheaper new walking ways and the random-pair change distribution are reported.

- 2026-09-25 — Uwe replaces phase 10's fixed ground factor 10 with walking's `offPath()` (3 off, 10 on), keeping Stay on paths visible in kayak mode. Review limits launch starts to existing walking nodes. The original Kloten/phone-2 short landing has none within 30 m; a farther 21.321 m tie serves phone-2 with Stay on paths but leaves Kloten P1's western departure unchanged. The requested landing check stops with these figures; no production change is built.

- 2026-09-25 — Uwe decides phase 10: prefer walking source prices under water-first, ground at 10, launches within 30 m and a complete compact distance split. A local browser diagnostic stops on walking invariance: shared launch noding changes a walking way from 55.990099 to 68.341328 m in both settings without using a launch edge. The topology scope needs review; no production change is built.

- 2026-09-25 — phase 9 is built: dissolved Marktäcke paddle water and the shared Swedish grid, 5 m shores on all maps, 25 m dam exclusions for network and kayak connectors, reattached streams and measured replacement MK fixtures. All 1,800 final labels match the reference; kayak/inland drives pass twice per page, walking readings and hooks pass. Uwe’s 2026-09-24 walking decision stands; no push or publication.

- 2026-09-24 — review extends Uwe’s dam/lock cut to 25 m surface discs and kayak connector samples, keeping walking and the shared grid unchanged. It permits replacement MK bank/carry fixtures while retaining the original reader pairs, and requires the three stream reattachments and their directed reachability audit.

- 2026-09-24 — the one-copy lake-mouth fix is built and measured; Abisko’s revised shore reading passes. Phase 9 stops on a new Marktäcke surface route through Korslång’s dam, MK scene fixtures that no longer exercise their assertions, and stream joins still requiring reattachment. The shared grid, prices, 5 m tolerance and accepted walking changes stand.

- 2026-09-24 — review allows inlet mouths in the fixed lake-bank reading: Open water must stay within 5.1 m of lake/river interfaces, and the route stays within 10 % of the new Shore-plus-interface reference. Shared interfaces are emitted once at the adjacent lake’s level; river interiors retain sampled heights. The join audit and final validation are rerun after the fix.

- 2026-09-24 — Uwe: “So wie vorgeschlagen”; share Marktäcke / N50 water between both modes, retain walking factor 30 and midpoint pricing, and accept the three material recorded walking changes documented in phase 9. Exact-width or finer-cell pricing is deferred.

- 2026-09-24 — Uwe questions keeping the coarser grid for walking (a question, not a decision; the grid stays open) and phase 9 stops for a walking-rule decision before any final build. The 5 m tolerance and network-only inland gate stand. The investigation measures the three material recorded walking changes and six alternative rules on the recorded inputs and 200 random pairs per map in both settings. Only records change.

- 2026-09-24 — phase 9 completes the three-map 5 / 3 / 2 m sweep and stops: no tolerance meets both payload and p95-search budgets. All 1,800 kayak labels match the reference. The 2 m trial also exceeds the retained length bound for the recorded Dammtjärnsbäcken walking goal and the inland bound for the Malingsbo-Kloten portage connector. The interrupted Norway build was repeated successfully; new measurements run sequentially with an 8 GiB cap.

- 2026-09-24 — phase 9 review accepts changed walking entry nodes after rebuilding: final-graph walking acceptance is pruned/unpruned label equality for all 200 seeded pairs per map in both walking settings. Old-way re-pricing excesses are informational.

- 2026-09-24 — phase 9 stops on the resolved walking price gate: rebuilt portage noding removes a cheaper walking entry in Abisko pair 11. The excess reproduces at 5 / 3 / 2 m and survives pricing the old entry as a partial edge of the new graph. The revised inland-deviation gate passes the 2 m Abisko scenes; all 600 Abisko kayak labels match the unpruned reference.

- 2026-09-24 — phase 9 review replaces the longitudinal land-run gate with maximum inland deviation, sampled every 0.1 m, bounded by the chosen tolerance plus 0.1 m for encoding. Land-run length is informational; no containment-preserving geometry or offset is added.

- 2026-09-24 — phase 9 stops at the proposed longitudinal land bound: the recorded Abisko shore route still has long shallow land runs at every 5 / 3 / 2 m tolerance. Review must distinguish inland deviation from dry-run length, or decide containment-preserving geometry. The grid-only walking replay completes all 1,200 comparisons with no price defect.
- 2026-09-24 — phase 9 review accepts Abisko pair 72 and removes the random-pair length stop. Report change distributions and every large increase; stop for a new route more expensive than its old way re-priced on the new grid. Keep the length bound for recorded walking ways.

- 2026-09-24 — phase 9 stops at the agreed walking-route bound: Abisko's 72nd phase-8 pair shortens by 302.685 m (5.576 %) against a 108.569 m allowance. The public planner confirms the changed route; the shared-grid decision stands, with its effect on this route returned to review.
- 2026-09-24 — phase 9 review resolves the grid stop: share Marktäcke for both modes and retain walking's water price of 30. Walking figures may reflect the finer source; measure all walking readings and the 200 phase-8 pairs per map in both walking settings. Stop for a route-length change beyond the larger of 2 % and 50 m.
- 2026-09-24 — phase 9: Uwe chooses Marktäcke paddle water for Sweden, N50 for Norway, and a measured 5 / 3 / 2 m shore tolerance. Stopped before implementation: replacing the shared grid changes Abisko's walking figures. The stop below records the decision needed between separate mode grids and changed walking figures.
- 2026-09-23 — phase 8 differential review: all 600 seeded pairs match the exhaustive reference exactly in land and price. A permanent seeded unit reading checks the bounds; the built-note records the random sample's wider timing distribution.
- 2026-09-23 — phase 8 review: bound off-network searches; Uwe retains phase 2's cell-based connector prices. The drive requires zero router land and bounds the finer tally difference by one cell per connector end. The review built-note below records the measurements, retained sampling and green validation.
- 2026-09-23 — phase 8: Uwe chooses water first. True lexicographic costs minimise land metres before the former price; the Korslångssmedja reconstruction paddles 4,296.406 m instead of walking 1,352.730 m. Measurements and the build record are below.
- 2026-09-22 — phase 5 again after phase 7 (`f25229a`): the three graphs and pages rebuilt, `drive-all` 1,464 / 1,464 / 1,451 readings, published ~15:00 UTC and read back identical; the Korslång check is a scene skip on the two pages without a measured stream.
- 2026-09-22 — phase 7 built: whole stream chains open where their measured fall does not support a restriction. The Korslång pair paddles the channel both ways; the two drives pass and the previous kayak scene figures stand. The built-note separates level and rising chains.
- 2026-09-22 — phase 7 stopped at the measurement: the supplied fall harness reverses heights by chain orientation even though the payload keeps edge direction. Both warm-cache graphs were captured; the stop and rising-edge classes are below. No gate built.
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

### Phase 10 — Carry on paths, launch at road ends, 2026-09-25

Uwe, translated: *"Also with the kayak, paths are to be preferred. Pathless is
even harder with a kayak. I would rather follow a path for 200 m than drag 20 m
over a bog. Only the last few metres are always fine."* — *"Can't we leave it
exactly as for walking?"* He initially chooses ground factor 10, the last metres up to
30 m and the panel correction. The plan's phase 10 records the full rule and
required measurements. Land price replaces physical land metres as primary;
the walking source factors stay exact, PORTAGE and connector ground cost `offPath()`,
and water/ferries contribute zero. Existing secondary prices retain P = 2.
Launches cost 1 in both objectives and are excluded from walking. Walking
prices remain unchanged; the topology decision below accepts new entry nodes.
The initial fixed 10 is superseded as follows.

**Uwe's revised decision, 2026-09-25.** After asking what Kayak and Stay on
paths mean together, he asks *"Sollten wir das dann nicht doch so für Kajak machen?"*
— *"Ja"* ("Shouldn't we then do it that way for kayaking after all?" — "Yes"). Ground in the land-price primary
follows the walking switch exactly: `offPath()`, **3 off / 10 on**. This also
prices PORTAGE-kind edges; walking source factors, zero primary for paddle and
ferry, and launch price 1 stand. The secondary price is unchanged. Stay on paths
stays visible in kayak mode. The interim proposal to hide it is dropped, not
implemented. The phase-10 measurements, kayak reference comparisons and p95
now cover both switch settings; drives state and restore their setting and
demonstrate a route change where the ground/path trade produces one.

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

**Stopped — a kayak-only tie changes shared walking topology.**
`water.build` passes portages and walking sources through the same
`build_network` noding. A passing-road launch needs a road split. The browser's
walking search admits connectors to every node, not just nodes whose incident
edges are walkable, and its snap logic prefers junctions within `NODE_FIRST_M`
of the nearest edge distance. The new road node has walkable incident edges.
Excluding the launch kind therefore leaves both a new walking entry/exit and
a new walking snap target.

The read-only browser experiment uses the existing Malingsbo-Kloten page
(SHA-256 `fb4a454897e186533794b26903dc76501fd09fe439946f8b7b68128936005d4b`),
Firefox 153.0, and the investigation's 7.188 m z17 snap reach. Its router,
connector-price and snapping source regions match this checkout after
whitespace normalization. No kayak weighting is enabled in this experiment.
The nearest point on road edge **45003** to bay shore node **93159** is
**(59.897876698495, 15.288431594724)**, **6.443628 m** away in EPSG:3006.
In browser memory the existing road geometry is split at that point, giving
node **145558**. The same measurement is repeated with a diagnostic PORTAGE
tie to the shore; its walking price is infinite and none of the answers uses
it. This isolates noding rather than claiming a completed launch generator.

| Input / setting | Length before → after m | Price before → after |
|---|---:|---:|
| East of launch → junction / ordinary | 55.990099 → 68.341328 | 167.970298 → 131.662202 |
| East of launch → junction / paths | 55.990099 → 68.341328 | 559.900994 → 307.973575 |
| Phone-2 1→2 / either | 175.288968 → 175.288968 | 227.875659 → 227.875659 |
| Phone-2 2→3 / either | 43.164309 → 43.153989 | 56.113602 → 56.100185 |

The first pair is **(59.897876698495, 15.288881594724) →
(59.897507, 15.288204)**. Both versions retain an off-network start and the
same destination node 33831. Before noding, the whole direct line wins. After,
the new road node offers **25.187339 m** of ground followed by **43.153989 m**
on Topografi 50 roads at factor 1.3. The route gains **12.351228 m** while
becoming cheaper under the unchanged walking rule. The phone-2 input retains
the investigation's coordinates, including point 3 at **(59.897891, 15.288320)**;
walking snaps it to the road, then to the new road junction after the split.
That independent effect changes even the short road-to-road leg by **0.010320 m**.

The six cases' lengths and prices are identical between the split-only and
split-plus-tie variants. All **12** before/after search labels in the latter
match the exhaustive reference within `1e-10` price units. Neither price nor
pruning is faulty. No assertion about the 600 seeded pairs or the drive's
recorded walking scenes follows from this small diagnostic.

**Question at the first stop, resolved by review below:** include preservation of the pre-launch walking
topology, with separate kayak junctions/entry sets/snapping and unchanged
walking geometry, or accept walking changes from the shared noding. The
recommendation is the former, retaining Uwe's walking invariant. No such
topology choice has been implemented or attributed to Uwe. Hiding only launch
edges or only snap targets is insufficient; the available connector entries
also change. Phase 9's accepted noding changes do not grant an exception to
phase 10's explicit byte-identical walking requirement.

**Build status.** No production implementation, graph/map build or figure
update. The source/kind choice, spacing and access measurements, price/panel
changes, reader comparisons, all-map differentials and p95 measurement,
twice-green selected drives and full `command make drive-all` are pending.
The diagnostic preserves the page files, original graph and plan, restores
both modes, and does not set a goal. One harness at a time, each capped at
8 GiB. No shared-cache write, source download, tile build, push or publication.

Evidence: `~/mockups/kayak-mode/phase10/{launch-candidate.json,noding.js,
noding.json,noding-with-tie.json,noding-summary.json,harness.py,probe.js,reference.js}`.
From this checkout, reproduce with an 8 GiB address-space limit and
`uv run --offline --with playwright==1.62.0 python
/home/eiseleu/mockups/kayak-mode/phase10/harness.py malingsbo-kloten noding.js repeat.json`.
The harness reads the unchanged main checkout's built page; it does not fetch
remote assets or replace this worktree's unbuilt page.

**Validation of this stop.** `command make hooks-run` passes with network
access, including ruff format/check, mypy, tests and all standard hooks.
`~/mockups/kayak-mode/phase10/hooks.log` records the run. Only the two records
change; this validation does not claim a phase-10 production build.

**Review decision after the stop, 2026-09-25.** Launch starts are existing
walking-network nodes only; no walking edge may be split for a launch. A dead
end is already a node. A passing road needs an existing node within 30 m of
water, or it gets no launch there. Only the paddle shore may be re-noded.
Walking remains byte-identical. Measure the passing locations lost against
the splitting prototype and check the phone-2 and Kloten northern landings
first. If they do not get launches, stop with the figures so Uwe can decide
whether walking may change. This topology rule is review's decision; the
switch pricing above is Uwe's.

**Landing check after review — original location absent, farther access exists.**
The source graph saved by phase 9 has 289,548 edges. Its existing PATH/BRIDGE
nodes within 500 m of the northern-shore reconstruction were measured in
EPSG:3006 against the source lake and paddle Shore. The closest node to both
the original northern landing Q and phone-2's shore point is **33831**, at
**(59.897507124140, 15.288203668912)**. This is a road junction of walking
degree 3, not a dead end. Its nearest source water is **42.075943 m** away;
its nearest simplified Shore point is **42.534528 m** away. Node **33832**,
also degree 3, is **50.845958 m** from source water. Neither qualifies.

The published page's coordinate quantum gives node 33831 at
**(59.897507, 15.288204)**. With those encoded coordinates its distances are
**42.089910 m** to source water, **43.254364 m** to shore node **93159**,
and **58.834956 m** to Q. These are EPSG:3006 lengths; the browser's metre
calculation makes the point-2 → point-3 tie **43.271516 m**. The difference
between source and encoded coordinates is reported rather than mixed into
the 30 m test; both versions fail it.

The previous splitting prototype contained **one investigated site**, at
**(59.897876698495, 15.288431594724)**, opposite shore node 93159. That
original launch location is lost: **one site → zero retained there**. It was
a noding diagnostic, not a complete launch generator, and did not establish
map-wide counts or certify the tie's land-only geometry. There are no Abisko
or Norway prototype launch catalogues against which to invent loss totals.

However, **node 24433 on the same road qualifies farther north**. Its source
position is **(59.899237772676, 15.289714526724)**, walking degree 3, meeting
Topografi 50 roads and paths. It is **19.968740 m** from source water and
**20.368276 m** from the simplified shore. Its nearest existing shore node
is **93164**. On the page their coordinates are
**(59.899238, 15.289715) → (59.899302, 15.289356)**, with tie length
**21.320689 browser metres / 21.312238 EPSG:3006 metres**. The encoded origin
is **19.979110 m** from source water. The tie intersects **0 m** of the cached
Marktäcke water union; its origin is **4,454.072059 m** from the nearest dam
centre, leaving the whole short segment clear of the 25 m disc. It uses two
existing nodes and needs no noding. The Shore route from point 3 to this
landing is **191.706571 browser metres / 191.630581 metric metres**.
The road therefore retains **one confirmed farther candidate**, although
the original site has none. These counts distinguish relocation from loss.

**Local price experiment, both switch settings.** An in-memory graph clone
adds just the farther tie. Its diagnostic source uses PORTAGE's exclusion
on foot with an explicit factor-1 override in both kayak objectives; this
does not select a production source/kind. The existing investigation probe
supplies the new land-price rule at `offPath()`. It preserves connector
sampling, the secondary price and all original node positions. The unchanged
main checkout page has the same SHA-256 as at the first stop above.

The five inputs are the investigation's reconstructions, not recovered phone
taps: P1 **(59.895949196, 15.288015230)**, northern Q
**(59.898026273, 15.288010427)**, P2 proxy
**(59.952981501, 15.278743062)**, off-road start
**(59.895949196, 15.288465230)**, phone point 2
**(59.897507, 15.288204)** and point 3 **(59.897891, 15.288320)**.
Snap reach stays **14.377 m** for the original Kloten pairs and **7.188 m**
for phone-2. The plan's phase-10 table records physical carry/paddle totals
for the old rule and the new rule plus the farther tie in both settings.
`route-summary.json` also retains the new rule without any launch.

Phone-2 1→2 changes **173.877045 → 175.288968 m** on foot and takes the road
with either setting. Phone-2 2→3 stays the **43.271516 m** straight connector
with the switch off; its land price is **129.814548**. With the switch on,
the same line costs **432.715161** in the primary objective and loses to
**297.388133** for the road plus launch. That answer carries **233.680261 m**,
including the **21.320689 m** tie, and paddles **191.706571 m** back to point 3.
Its secondary price is **765.162149**. This provides a measured switch-sensitive
example for a future drive; no drive reading is installed at this stop.

Kloten P1 → Q instead changes **231.408313 / 0 → 411.030953 / 620.693615 m**
carried/paddled in both settings. It takes the western connection, as does
P1 → P2, unchanged at **411.030953 / 7,088.969083 m**. The off-road start
changes **196.752924 / 6,920.199608 → 399.583052 / 7,088.969083 m**, again
west, in both settings. These are the router-sampled physical lengths; the
public profile's more detailed shoreline split is a different measurement.
The road way from P1 via point 2 and the farther tie has primary
**525.263792**, whereas the western way costs **482.156276**. The road
factor 1.3 and western path factors account for this choice. The accepted
preference for walking source prices does not guarantee use of a nearby launch.

Five pairs × two settings × three variants (old rule, new rule, new rule plus
farther tie) give **30 labels**, all matching the unpruned reference within
`1e-8` for both objectives. No claim about the seeded suite or p95 follows
from these local comparisons. Each harness runs alone under an 8 GiB cap,
restores the modes and price wrapper, and never changes a goal, saved plan,
published page or the original graph. No production file is changed.

**Stopped at the requested landing check.** There is no existing-node launch
at the original short landing. The farther same-road candidate is reported
explicitly: it helps phone-2 with the switch on but does not change the
Kloten P1 departures. Uwe must decide whether that relocated access is
acceptable or whether walking may change to admit the original short tie.
The prior topology scope question is resolved by review's existing-node rule;
this stop does not reopen it or propose a separate walking graph.

**Build status after the landing check.** Records only. The revised price,
launch generation and panel change remain unbuilt, as do the three-map
catalogue/spacing/loss measurements, full reader sweep, both-setting seeded
kayak reference and timing runs, walking invariance, graph/map builds,
twice-green selected drives and full `drive-all`. No source download, shared
cache change, tile build, push or publication. Evidence is under
`~/mockups/kayak-mode/phase10/existing-nodes/`: `measure.py`, `local-nodes.json`,
`audit.py`, `audit.json`, `browser.json`, `routes-checked.json` and
`route-summary.json`. The browser scripts are `../existing-nodes.js` and
`../existing-node-routes.js`, using the retained `../harness.py`.

**Validation of the landing stop.** `command make hooks-run` passes with
network access: ruff format/check, mypy, tests and all standard hooks. The log
is `~/mockups/kayak-mode/phase10/existing-nodes/hooks.log`. Only the two records
change; the local route audit is not a substitute for the pending release checks.

**Built 2026-09-25 — Carry on paths, launch at road ends.** Uwe's revised
3 / 10 switch rule and shared road noding are implemented; the fixed 10 and
review's existing-node-only restriction remain superseded. `Launches` has its
own `LAUNCH` kind, priced at 1 in both objectives and excluded from walking
and walking snaps. P = 2 remains secondary. The compact kayak line gives the
whole distance, then paddle and foot; walking keeps its plain figure.

The measured 100 m shore spacing gives **2,220 Malingsbo-Kloten**, **350 Abisko**
and **1,825 Lomsdal-Visten** ties, all connected. **808 / 162 / 494** supply
new access within 500 m of old land-network travel to the same undirected
paddle component. The short Kloten tie is a passing-road launch, road node
**141123** to shore **94456**, **6.413967 m** long and **6.085713 m** from the
road foot to source water. It serves phone-2's 2→3 and P1's northern shore
in both settings; phone-2's 1→2 follows **175.289 m of road** in both.

All **1,200 kayak** and **1,200 walking** labels match the reference. Kayak
p95 increases **17–52%**, never doubling. All **264 frozen recorded walking
readings** pass the old-way price gate; the **103** whose metre figures move
at three decimals are listed. Longer carries are expected: the largest rises
**36,995.003 m**, on Norway pair 198 with Stay on paths on. The
[phase-10 measurements](kayak-mode-phase10-measurements.md) include both
settings, spacing and length distributions, Kloten and phone-2, scene triples,
the phase-2 sweep, Korslångssmedja, pair totals and all larger changes. The
[plan's build note](kayak-mode-phases.md#phase-10--carry-on-paths-launch-at-road-ends)
records the implementation choice separately from Uwe's decisions.

The selected kayak and new readings are green twice on each page. The complete
`command make drive-all` run is green too: **4,983 readings**, no broken
invariants or moved figures. The full suite's dry-profile sample counts and
renumbered road fixture are measured and recorded without weakening a gate.

`command make hooks-run` is green with network access: formatting, lint, mypy,
both pytest suites and the standard hooks. The three graph/map builds used
cached inputs, one at a time under 8 GiB. Phase 10 ends here, with no pending
price or topology decision, no push and no publish.

### Phase 9 — A finer shore, 2026-09-24

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

**Implemented source rule.** Marktäcke supplies Swedish paddle surfaces and
the shared 25 m water grid; N50 remains Norway's source. Whole intersecting
delivery pieces are dissolved on a 1 cm precision grid before clipping.
The 1 ha test applies to the connected water union, not to each feature;
smaller ponds remain in the grid. Lake planes remain separate through river
surfaces. Delivery seams disappear, and lake/river interfaces and map cuts
are Open water, with shared mouths emitted once at the lake plane. The
Swedish pages credit Marktäcke for both paddle water and the grid, with
© Lantmäteriet, CC BY 4.0 and the modifications described. Phase 2's grid
classification of connectors and tally, walking factor 30 and midpoint
pricing remain unchanged.

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

**The finer source and unchanged walking figures need a decision.** Phase 9
requires the page's water grid to use the same Marktäcke water as Sweden's
new paddle network. It also requires unchanged walking figures. The current
page has a single grid, used for both connector prices and the foot/water
tally in both walking settings as well as kayak mode.

The producer is `analysis/scripts/lomsdal_visten.py`: `build_sweden()` loads
Topografi 50 water and `encode_for_the_page()` passes `water_mask(water, bounds,
WATER_CELL_M)` into the routing payload. In `plan_mode.js`, the straight-leg
sample classification calls `graph.waterAt()` for walking too; only river
surfaces have a walking exception. `the_walking_modes_never_take_the_water()`
in `drive_map.py` asserts the scene's foot, water and straight-land figures
to within 0.01 m. Finer paddle edges cannot preserve a walking tally changed
by replacing this shared input.

**Measured with the graph and code held fixed.** On the existing `b3ee02f`
pages in the main checkout, a browser-only header substitution replaces
`header.water`. It uses the production `water_mask()` on `Sjö` and
`Vattendragsyta` read directly from the cached municipal GeoPackages, clipped
to each Swedish map's box. All seven grid-position/size fields are asserted
equal to the original. No simplified paddle outline is used for the grid,
and all ponds are retained. The source files, built pages and shared cache
are read only; all experiment outputs are in scratch. Browser requests are
served from local files or aborted.

The existing `read_water_leg()` reads the scene's shore pair in each walking
setting, then restores its plan, mode, goal way and view. Its restoration
comparison passes for all eight readings. The original pages reproduce
all recorded figures below before the mask is changed.

| Map / setting | On foot m, before → Marktäcke | Water m, before → Marktäcke | Straight land m, before → Marktäcke |
|---|---:|---:|---:|
| Abisko / walking | 2,940.880 → 2,935.858 | 15.273 → 20.295 | 514.362 → 509.340 |
| Abisko / stay on paths | 2,963.410 → 2,948.288 | 15.283 → 30.405 | 510.746 → 495.624 |
| Malingsbo-Kloten / walking | 3,266.274 → 3,266.274 | 8.024 → 8.024 | 70.879 → 70.879 |
| Malingsbo-Kloten / stay on paths | 3,266.274 → 3,266.274 | 8.024 → 8.024 | 70.879 → 70.879 |

Abisko's taps are (68.393226, 18.715936) → (68.407071, 18.697511);
Malingsbo-Kloten's are (59.887213, 15.675327) → (59.895929, 15.650716).
Each setting's total length remains unchanged; its foot/water split moves
on Abisko. The experiment does not claim that other walking routes would
keep their total length under different connector prices.

**Review must choose one of two scopes.** Preserve walking's Topografi 50
grid and introduce a separate Marktäcke grid for kayak pricing and tally;
or use the shared Marktäcke grid and permit walking figures to change.
The phase specifies neither a second grid nor an exception to unchanged
walking figures. Neither was silently added, and no walking snapshot was
updated.

Evidence: `~/mockups/kayak-mode/phase9/grid_preflight.py`,
`grid-preflight.log`, `grid-preflight.json` (page SHA-256, full leg states and
unrounded figures), and the two `*-marktacke-mask.json` files. The script
caps Python address space at 8 GiB. Reproduction from this worktree:

```bash
UV_PROJECT_ENVIRONMENT=/home/eiseleu/repositories/trails/.venv uv run --offline --no-sync \
  --with 'playwright==1.62.0' python -B /home/eiseleu/mockups/kayak-mode/phase9/grid_preflight.py
```

No production implementation, graph/map/tile build, download, cache write,
push or publication. The tolerance table, seam/join measurements, new
shore-containment drive and twice-green rebuilt pages remain unmeasured
pending this decision; there is no phase-9 built-note yet.

`command make hooks-run` passes with networking enabled, including formatting,
lint, type checking and both test suites. The full hook report is
`~/mockups/kayak-mode/phase9/hooks-stop.log`.

**Review resolved the grid stop, 2026-09-24.** Review chose the shared
Marktäcke grid (not Uwe; later reopened, see below): one truth about the water for both modes. Walking's water
price stays 30; only its water knowledge changes. A second grid would add
payload and memory without a reader benefit. The six moved Abisko figures
above are permitted in principle, subject to measuring every recorded
walking reading and replaying all 200 phase-8 pairs per map in both walking
settings. Record all changed figures before updating the drive and name
phase 9 beside them. Stop if a route's length changes by more than
`max(0.02 × old length, 50 m)`; a changed foot/water split at its edge alone
is accepted. No price adjustment is authorised to hide a changed route.

**Stopped again — The shared grid changes a walking route beyond that
bound.** The saved phase-8 pairs are replayed at the same coordinates, with
walking's own `snapped()` call rather than the former kayak node ids or
partial-edge cuts. Both walking settings use the existing production
`resolve()` and its searches. The first pass reads route geometry and
length without fetching connector heights; a separate public-planner
reading with the cached height tiles checks the failing case and its
foot/water split. Only `header.water` changes between pages: graph, routing
code, river outlines, pricing factors, grid extent and cell size stand.

A separate grid check dissolves the 2,625 selected Kiruna water features
in EPSG:3006 into 2,353 polygon parts before clipping and rasterising.
The resulting header mask is identical to the preflight mask: **zero
changed cells**. Dissolving the new source does not remove this failure;
`abisko-dissolved-grid-check.json` records the comparison.

**Abisko, index 71 (pair 72), ordinary walking.** The fixed-seed case was
`network-off`, distance band 2, in the kayak harness; both taps are
off-network when snapped for walking. No replacement random sample was
drawn. Coordinates, in journey order:

- (68.3661770595677, 18.788008393436556)
- (68.37383928183993, 18.833846517753347)

| Public planner reading | Topografi 50 grid | Marktäcke grid | Change |
|---|---:|---:|---:|
| Total length, m | 5,428.454 | 5,125.769 | −302.685 |
| On foot, m | 4,300.418 | 3,974.629 | −325.788 |
| Over water, m | 1,128.036 | 1,151.140 | +23.103 |
| Straight land, m | 1,716.439 | 1,393.719 | −322.720 |

Changes are computed before rounding. The total changes by **5.576 %**;
the review bound is **108.569 m**, the larger of 2 % of the old length and
50 m. Both public readings reproduce the geometry-only search length and
restore the plan, mode and goal way. The route is shorter, but the stated
bound applies to a change in either direction.

**Where the way changes.** Its entry connector remains 269.533 m, reaching
the same node at (68.364538, 18.792820). The network portion changes from
2,583.979 to 2,580.911 m and leaves at a different node:
(68.350814, 18.829341) before, (68.353527, 18.828753) after. The straight
exit to the fixed destination shortens from **2,574.942 to 2,275.325 m**.
That accounts for 299.617 m of the length change, with the network portion
accounting for the other 3.068 m. No finer shore edge has been built.

The old exit has 43 wet midpoint samples out of 103 on both grids. The new
exit has **45 / 92** on Topografi 50 and **44 / 92** on Marktäcke. This
one changed cell reduces its sampled water length from 1,112.931 to
1,088.199 m. At the unchanged walking prices (ground 3, water 30), that
connector's price falls from 36,875.106 to 36,207.348. The old exit's price
remains 36,749.172. These are connector prices, not whole-route prices;
the public tally uses its existing finer sampling and is recorded above.
The new data makes a different network exit competitive: this is not a
cosmetic reclassification of one unchanged route.

**Coverage at the stop.** All 200 Abisko baseline pairs were run in both
walking settings. The ordinary-walking Marktäcke replay completed 72
pairs and stopped at its first excess; the preceding 71 satisfy the length
bound. Eight of these 72 have a length change larger than 0.000001 m,
including the stopped pair. The Marktäcke path-preference pass and the
other maps were not started. These are not 1,200 completed before/after
comparisons, nor the requested complete sweep of recorded walking
readings. No scene snapshot was updated for this unbuilt source change.

**Review must decide whether this shorter route is acceptable and how the
bound applies on resumption.** Sharing the grid is already decided; no
second grid, altered walking price or exception to the bound is introduced
here. The production water change, tolerance and reader measurements,
source attribution update, builds and twice-green drives remain pending.

Evidence, all in `~/mockups/kayak-mode/phase9/`:

- `walking_pairs.py`, `abisko-walking-pairs.log` and
  `abisko-walking-pairs.jsonl`: the 472 completed search readings, including
  the before/after geometries. The script stops at the first exceeded bound.
- `walking-route-stop.json`: the saved case, both answers and the baseline
  page's SHA-256; `walking-stop-connectors.json`: the two exits sampled
  at the production 25 m midpoint spacing against both packed masks.
- `verify_walking_stop.py`, `walking-stop-public.log` and
  `walking-stop-public.json`: public-planner confirmation and successful
  restoration comparisons, using `drive_map.read_water_leg()`.

Both browser scripts cap address space at 8 GiB, serve only local files,
and put back mode and goal way in their cleanup. The public reading also
restores the borrowed plan and map view. Reproduction:

```bash
uv run --offline --with 'playwright==1.62.0' python -B \
  /home/eiseleu/mockups/kayak-mode/phase9/walking_pairs.py abisko
uv run --offline --with 'playwright==1.62.0' python -B \
  /home/eiseleu/mockups/kayak-mode/phase9/verify_walking_stop.py
```

The production code, built pages and shared cache remain unchanged. No
graph/map/tile build, new data download, push or publication.

Validation reports: `hooks-route-stop.log` and `hooks-route-stop-final.log`
in the same scratch directory. The first run passed all 2,024 library and
97 pipeline tests, but pre-commit rejected a concurrent documentation edit
that added the dissolved-grid result. The final `command make hooks-run`
with networking enabled passes every hook with the files fixed.

**Review resolved the random-pair bound, 2026-09-24.** Uwe accepts Abisko
pair 72 as finer water knowledge acting through the unchanged walking rule.
Random pairs in both walking settings no longer stop on length change.
Report how many change, how many lengthen or shorten, median / p95 / maximum
absolute and relative length changes, and the taps and explanation for each
increase above `max(0.02 × old length, 50 m)`. For every changed pair, price
its old way on the new grid and require the new answer to cost no more;
a worse new price is a defect and stops the phase. The length-change bound
still applies to the recorded walking ways in the drive. Smaller recorded
changes may be updated with a note naming phase 9 and the shared grid.

**Walking replay after review.** The grid-only comparison is complete:
200 saved phase-8 coordinate pairs per map, before and after, in ordinary
walking and Stay on paths — 1,200 comparisons and 2,400 searches. Each tap
is snapped for walking afresh. The production route choice is reconstructed
including partial edges, network prices and both connectors; its price is
checked against the router's chosen label. Each old way keeps its network
price and has its original connectors re-priced on the new grid. Every new
answer costs no more than that old way under the new grid, within
`1e-7 + 1e-12 × |old price|`. There is no walking price defect in this replay.

The table's quantiles include all 200 pairs in each row, including unchanged
ways. Relative change is absolute length change divided by the old length.
“Changed” compares the returned route parts and coordinates; longer/shorter
counts ignore floating differences below 0.00000001 m. The full distributions,
including quantiles restricted to changed ways, are saved in
`~/mockups/kayak-mode/phase9/walking-distribution.json`.

| Map | Walking setting | Changed / 200 | Longer / shorter | Absolute change m: median / p95 / max | Relative change %: median / p95 / max |
|---|---|---:|---:|---:|---:|
| abisko | Walking | 24 | 11 / 13 | 0.000 / 42.824 / 6,186.011 | 0.000 / 0.464 / 54.366 |
| abisko | Stay on paths | 14 | 5 / 9 | 0.000 / 10.644 / 616.979 | 0.000 / 0.073 / 4.905 |
| malingsbo-kloten | Walking | 14 | 8 / 6 | 0.000 / 29.551 / 574.182 | 0.000 / 0.301 / 291.322 |
| malingsbo-kloten | Stay on paths | 6 | 3 / 3 | 0.000 / 0.000 / 285.139 | 0.000 / 0.000 / 2.178 |
| lomsdal-visten | Walking | 0 | 0 / 0 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| lomsdal-visten | Stay on paths | 0 | 0 / 0 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |

**Every increase above the review bound.** Pair numbers below are one-based;
the saved case's `index` is one smaller. Prices are the unchanged walking
rule's units, not metres. Both price columns use the new grid.

| Map / pair | Setting | Length m, before → after | Old way price → new answer price | Taps (latitude, longitude) |
|---|---|---:|---:|---|
| abisko / 128 | Walking | 667.734 → 950.579 | 2,576.435 → 2,437.379 | (68.348361289413, 18.480686130367) → (68.346321040578, 18.492564790531) |
| abisko / 195 | Walking | 11,537.806 → 12,683.399 | 36,634.980 → 35,343.494 | (68.408037748363, 18.206584339389) → (68.304884992927, 18.221020839482) |
| abisko / 77 | Stay on paths | 28,422.168 → 29,039.147 | 127,226.119 → 127,007.337 | (68.197836621778, 18.608484135483) → (68.384029318153, 18.822435422676) |
| malingsbo-kloten / 34 | Walking | 10,897.505 → 11,133.698 | 30,109.998 → 29,504.092 | (60.169362209400, 15.058040370696) → (60.153091816969, 15.164405430597) |
| malingsbo-kloten / 42 | Walking | 204.564 → 778.746 | 2,454.769 → 2,336.237 | (60.063395062373, 15.323839510504) → (60.065192176865, 15.323086771306) |
| malingsbo-kloten / 62 | Walking | 196.972 → 770.795 | 2,585.258 → 2,312.385 | (60.065146038622, 15.323350740770) → (60.063395062373, 15.323839510504) |
| malingsbo-kloten / 133 | Walking | 6,220.053 → 6,452.331 | 26,610.313 → 25,813.840 | (60.151887531273, 15.166031856597) → (60.110091489692, 15.203019839460) |
| malingsbo-kloten / 34 | Stay on paths | 10,897.505 → 11,133.698 | 33,798.320 → 33,692.323 | (60.169362209400, 15.058040370696) → (60.153091816969, 15.164405430597) |
| malingsbo-kloten / 133 | Stay on paths | 6,314.768 → 6,452.331 | 27,284.388 → 27,018.649 | (60.151887531273, 15.166031856597) → (60.110091489692, 15.203019839460) |

- Abisko 128: the old 626.834 m connector gains one wet sample out of 26.
  A different exit uses 722.652 m of dry connector and more network, but
  costs less overall.
- Abisko 195: the old 8,260.953 m connector goes from one to three wet
  samples out of 331. The answer changes from two connectors meeting at
  one node to a network leg between two dry connectors, 8,721.855 and
  2,457.820 m long.
- Abisko 77, Stay on paths: the old entry goes from 39 to 40 wet samples
  out of 50. The new 1,283.630 m entry retains 37 wet samples out of 52.
  The exit is unchanged; both alternatives pay its change from 92 to 93
  wet samples out of 95. The longer network approach is cheaper overall.
- Malingsbo-Kloten 34, both settings: the new 679.312 m exit goes from
  24 to 22 wet samples out of 28. It replaces the old 642.645 m exit,
  whose 23 wet samples out of 26 do not change. The entry is unchanged.
- Malingsbo-Kloten 42 and 62: the old answers are direct connectors
  across water. A longer alternative bends through one network node,
  without traversing a network edge. One of its connectors loses its
  only wet sample, leaving both connectors dry. That beats the old
  direct way's three wet samples (out of nine and eight respectively).
- Malingsbo-Kloten 133, both settings: the new 517.845 m entry goes from
  17 to 15 wet samples out of 21. It replaces an entry of 483.962 m
  (ordinary walking, 17 / 20 wet) or 463.793 m (Stay on paths, 17 / 19 wet).
  The exit remains the same. The new entry and additional network are
  cheaper together.

The maps, source prices, graph, river description, 25 m grid geometry and
routing code are unchanged in this experiment; only Sweden's water bits
are replaced. Norway's grid is identical before and after. These are the
shared-grid results, not a comparison of the eventual finer-shore graphs.
A final combined-graph replay and the complete recorded-walking drive sweep
remain required. No recorded walking figure has been updated. Browser
contexts restore their mode, path preference and goal way after each pass;
requests outside the locally served files are blocked.

Reproduction and complete evidence in `~/mockups/kayak-mode/phase9/`:
`walking_compare.py`, `walking_choice.js`, each map's
`*-walking-compare.jsonl` and log, `walking_summary.py`, and
`walking-outliers.json` / `outlier_connectors.py`. The outlier file retains
full-precision taps, old/new connector endpoints and each grid's sample
counts, so the explanations do not depend on the rounded table.

**Stopped at the land-stretch reading, 2026-09-24.** A finer ordinary
simplification does not imply the proposed longitudinal containment bound.
The Abisko public scene route fails that bound at 5, 3 and 2 m. Each trial
reads the cached Kiruna Marktäcke delivery, dissolves connected water before
rings are taken, retains the lake register/minimum-per-body semantics and
builds the shared grid from Marktäcke. No offset or centre line is involved.

The prototype's 1 ha cutoff is applied to the union area of connected water
pieces, including adjoining lake and river surfaces, before clipping to the
map. Small delivery pieces of a qualifying body therefore survive; isolated
bodies below 1 ha do not enter the paddle network. All ponds remain in the
shared water grid. Lake components retain their separate height semantics
across river surfaces, while lake/river interfaces and crop edges are not
emitted as cheap shore. The source is CC BY 4.0, © Lantmäteriet; trial pages
have an explicit Paddle water credit naming dissolution, simplification and
the shared grid. These are prototype details, not accepted production code.

The fixed scene taps are (68.393226, 18.715936) →
(68.407071, 18.697511). The reader's drawn `paddled` part coordinates are
projected into EPSG:3006 and sampled at distances 0, 2, 4, … m, with the
endpoint included. A run is the distance between the first and last
consecutive dry samples; a dry sample is outside the unsimplified source
union and more than 0.0000001 m from it. A separate exact line-minus-water
intersection confirms substantial continuous runs. Source boundaries count
as water; ponds are retained in the comparison. Each public reading restores
the borrowed plan, mode, path preference, goal way and view.

| Water / tolerance | Paddled m | Longest sampled land run m | Longest exact land segment m | Maximum sampled inland deviation m |
|---|---:|---:|---:|---:|
| Topografi 50 / 10 m (before) | 2,116.110 | 114.000 | 115.524 | 9.328 |
| Marktäcke / 5 m | 2,167.118 | 96.000 | 96.258 | 4.741 |
| Marktäcke / 3 m | 2,182.974 | 80.000 | 80.693 | 2.754 |
| Marktäcke / 2 m | 2,192.258 | 76.000 | 78.765 | 1.846 |

The 2 m route's worst continuous land piece goes from
(68.39732606297036, 18.70358602024301) to
(68.3980273932845, 18.703811483457375). Its exact length is
78.76494992699133 m, with a 1.773650901046177 m maximum inland distance
sampled every 0.1 m. A long shallow excursion passes a 2 m deviation bound
but fails a 2 m land-run bound. It is neither an administrative seam nor a
centimetre encoding artifact. Plain polygon simplification independently
leaves land segments of 66.333 / 80.102 / 80.102 m at 2 / 3 / 5 m within
10 m of this scene route. The prototype's separate handling of real banks
and feature seams is therefore not the source of the missing guarantee.

The existing `libs/src/trails/network/water.py:sources` simplifies each
surface and uses that simplified surface's coverage to admit chords.
Simplification bounds deviation without choosing the water side; phase 8
prices a PADDLE edge as water by kind. Neither operation promises the new
longitudinal bound. The shore investigation's §A explicitly reports that
reducing simplification reduces leakage without establishing its absence.
Changing the land-stretch assertion to a deviation assertion would be a
changed acceptance rule. Constraining geometry to water, including a rule
for the encoded boundary, would be additional generation policy. Both are
returned to review; no implicit offset or price change is made.

**Other measured Abisko figures.** These are prototype measurements only.
The 2 m shore catalogue, sampled at at most 2 m with length weighting, has
source-boundary deviation median / p95 / maximum 0.283 / 1.376 / 1.999 m;
6.756 % of its length is more than 1 m on land. After the page's coordinate
rounding these become 0.283 / 1.377 / 2.022 m and 6.745 %. There are 50,872
candidate chords totalling 4,257.345 km; 6.404 km lies outside source water,
and 1,091 chords have more than 0.1 m of dry length. These are available
chords, not the length of a chosen journey.

The full graph grows from 75,463 to 148,991 edges. Brotli quality 11 over
the graph's embedded header and encoded data grows from 1,321,645 to
2,142,739 bytes. Whole-page Brotli grows from 1,822,895 to 2,647,099 bytes,
**+0.824204 MB**. No p95 search-time result or tolerance choice is claimed.
The baseline and candidate page hashes are retained in `2/abisko/bytes.json`.

The public scene triples move as follows. All figures are metres and all
readings restore their state; none is copied into the drive as an accepted
snapshot.

| Scene | Before: paddled / on foot | 5 m: paddled / on foot | 3 m: paddled / on foot | 2 m: paddled / on foot |
|---|---:|---:|---:|---:|
| shore | 2,116.110 / 0.000 | 2,167.118 / 0.000 | 2,182.974 / 0.000 | 2,192.258 / 0.000 |
| bay | 1,408.028 / 0.000 | 1,416.986 / 0.000 | 1,261.067 / 2.509 | 1,261.673 / 2.509 |
| portage | 336.096 / 102.465 | 417.749 / 1.450 | 413.926 / 9.616 | 414.821 / 9.616 |

**Built 2026-09-24 — Abisko trials for the stop.** The three completed
`command make map` builds run one at a time, at 2, 3 and 5 m, and write only
to `~/mockups/kayak-mode/phase9/`. A Python audit guard rejects downloads and
writes to the shared cache, and caps address space at 8 GiB. Existing tile
directories are linked for local page readings; no tile build is run. The
first construction attempt exposed rounding gaps between separately clipped
bank and crop pieces; retaining exact post-dissolution intersection points
fixed that prototype bug. A scratch Parquet export also failed on mixed
attribute types; the capture uses pickle and the successful build was rerun.
Neither failure is hidden as a successful build.

The completed pages and decoded graph captures, source lines, public scene
tracks and measurements are under `{2,3,5}/abisko/`. Reproduce the scene
readings with `scene_land.py abisko <that-directory> <tolerance>` using
`uv run --offline --with 'playwright==1.62.0' python`; `verify_land_tolerances.py`
records the sequential 3/5 m build commands. `land-witness.json` records the
exact failing piece, `geometry_measure.py` the catalogue measurement, and
`build-guard/sitecustomize.py` the build guard and measurement wrappers.
`production-prototype.patch` preserves the source, attribution and test
changes for review; `prototype/` retains that source for the scratch readers; they are removed from the worktree before the record
commit. Source changes have not passed the final hooks and are not presented
as accepted implementation.

The full nine-candidate, three-map payload/performance sweep and exhaustive
kayak-label comparison, final walking-graph comparison and recorded-walking
drive sweep, Korslångssmedja/phone/phase-2 measurements, join movements,
permanent land reading, twice-green drives and final graph/map builds remain
pending. The accepted grid and random-pair decisions stand. No tolerance is
chosen, no walking or kayak snapshot is updated, and there is no phase-9
release, push or publication.

**Review must decide:** use an inland-deviation bound with an explicit
encoding allowance, or retain the longitudinal dry-run bound and decide the
water-containment and boundary-rounding policy needed to meet it. The 15 m
offset and narrow-water centre lines remain outside this phase.

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

**Stopped at the walking price gate, 2026-09-24.** Replaying the phase-8
coordinates on the rebuilt 2 m Abisko graph reaches an ordinary-walking
price excess at index 10, the **11th pair**. The taps are
**(68.33703506111345, 18.191405035316922) →
(68.31925136413638, 18.247007022747788)**. Both remain off the network.
The same pair fails the price gate on the 3 m and 5 m trial pages too:

| Shore tolerance | New route m | New walking price | Old way priced on the new grid | Excess price |
|---|---:|---:|---:|---:|
| 5 m | 3,716.751661 | 6,558.902738 | 6,539.132686 | +19.770052 |
| 3 m | 3,717.334186 | 6,540.004731 | 6,539.132686 | +0.872045 |
| 2 m | 3,717.334030 | 6,540.004545 | 6,539.132686 | +0.871858 |

The old route is **3,717.395986 m**, priced at **6,539.132686**. Prices here
are weighted metres, not route lengths. This is not the accepted pair-72
effect: both old connectors and both new connectors at 2 m have no wet
pricing samples. Re-pricing the old way on Marktäcke leaves its price
unchanged. The new route is only 0.061956 m shorter, but costs 0.871858 more.

The source of the change is a portage's intersection with an OSM walking
path. Before, the entry is node 20794 at **(68.333678, 18.203238)**; after,
node 20863 is at **(68.333677, 18.203252)**, **0.587740 m** away. Each node
joins two OSM edges (factor 1.2) and two `Portages` edges. The portage is
not itself walkable; its intersection supplies a walking entry node.
`water.portages()` re-derives the chord from the new shore, and
`water.build()` nodes it together with the walking sources. The old point
ceases to be a node offered by `joinedRoute()`; the walking source and its
price rule are unchanged.

**The excess survives re-pricing against the new graph itself.** Project
the old entry onto the new OSM edge, rather than assuming its former
network price still holds. `nearestOnNetwork()` finds
**(68.33367790925742, 18.203237957024214)**, only **0.010255 m** from the old
point by its metric. `routeBetween()` then prices the remaining path on the
new graph, including that partial edge. The complete candidate costs
**6,539.146994**: entry 1,844.620478 + network 3,075.370209 + exit
1,619.156307. It is **0.857551 cheaper** than the new answer. This is much
larger than floating-point comparison error. The production snapper's 2 m
node preference would move a tap here to the new node; the witness uses
an edge point directly to test the old way, not a different user tap.

The distinction is the available entry set, not a changed water price or
a claim that the search fails to minimise over its current nodes. Preserving
old walking entry points, or offering positions inside walking edges to
off-network searches, needs a routing/noding decision that phase 9 does not
make. No such change is patched into this phase. **Review must resolve
this loss of a cheaper old walking way under the explicit price gate.**

**Built 2026-09-24 — Measurements up to the price stop.** The restored
source/test/attribution prototype is preserved in
`~/mockups/kayak-mode/phase9/production-prototype.patch` and `prototype/`,
then removed from the worktree again; only the records are committed.
No shore tolerance is accepted. All **600** Abisko kayak comparisons
(200 fixed phase-8 coordinate pairs on each 5 / 3 / 2 m graph, re-snapped
to that graph) match the unchanged unpruned reference in both labels.
These concurrent reference passes are not the isolated timing sweep.
The 2 m Abisko scene routes pass the revised 0.1 m sampling gate:

| Scene | Maximum inland deviation m | Longest exact land segment m |
|---|---:|---:|
| Shore | 1.865972 | 78.764950 |
| Bay | 1.310619 | 34.746599 |
| Portage | 1.693186 | 42.238743 |

The gate is 2.1 m; the land segment column is information, not acceptance.
These are the paddled parts only, tested against unsimplified Marktäcke.
The three-map walking grid-only replay already recorded above remains
valid. The rebuilt-graph replay completes 400 Abisko baseline cases
(200 per walking setting), then 11 ordinary-walking comparisons before
this stop; the 3 m and 5 m checks repeat only the failing pair. It does not
claim the final three-map walking replay is complete.

A sequential Malingsbo-Kloten 5 m map build reached the completed graph
and height pass, then was terminated during page construction at the
confirmed stop. No other new candidate build started. Attempts at the
full old-page drive encountered unrelated existing overlay and offline
pack readings before the walking scenes; they are not claimed green.
The full three-map tolerance/payload/search table, remaining reader-facing
measurements and join survey, permanent deviation reading, recorded-walking
updates, final graph/map builds and twice-green drives remain pending.
There is no shared-cache write, input download, tile build, push or publish.

Reproduction stays under `~/mockups/kayak-mode/phase9/`:
`walking_final.py abisko 2/abisko` records the first final-graph failure;
`walking_pair11.py` repeats it for 3/5 m; `price_witness.py 2` prices the
old entry on the new edge. Run from this worktree with
`uv run --offline --with playwright==1.62.0 python`, using absolute scratch
paths for the walking scripts' folder arguments. The browser measurements
restore the mode and goal way; the scene reader also restores its plan and
view. `2/abisko/walking-price-stop.json`, each tolerance's
`walking-pair11.jsonl` where present, and `2/abisko/price-witness.json`
retain the routes and prices. `harness.py` and each tolerance's
`reference-0.jsonl` retain the 600 comparisons, page hashes and Firefox
version. `densify_scene.py` and `2/abisko/scene-land.json` retain the inland
measurements. All graph scripts cap address space at 8 GiB.

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

**Stopped after the complete tolerance sweep, 2026-09-24.** No candidate meets both the
page-growth and p95-search budgets on all three maps. The full nine-row payload/search and
geometry tables are in phase 9 of the phase plan. Abisko fails the search budget at 5, 3 and
2 m. The complete scratch report, page hashes and individual results are at
`~/mockups/kayak-mode/phase9/report.md`. There is no selected tolerance or phase-9 release.

**The source prototype.** Sweden reads the nine existing municipal Marktäcke GeoPackages,
`Sjö` and `Vattendragsyta`; Norway keeps N50. Delivery and feature pieces are dissolved
before rings are taken. A 1 cm precision grid closes delivery cracks. The 1 ha test is on
connected water area before the map crop, so a small delivery fragment is kept when its body
is large enough. Lake components keep their own registered minimum or shore-percentile
level, apart from river surfaces. Internal lake/river interfaces and crop edges are not
emitted as cheap shore. The same water source builds the shared 25 m grid; its pond coverage
stays broader than the paddle network, as before. Walking still prices water at 30. The 2 m
builds level **364 / 601 / 984** lake bodies in Abisko / Malingsbo-Kloten / Lomsdal-Visten,
of which **59 / 148 / 982** use a register level; the remainder use the shore percentile.

The Swedish trial pages explicitly credit “Paddle water” to Marktäcke Nedladdning, vektor, ©
Lantmäteriet, CC BY 4.0, and name dissolution, simplification and the shared grid as
modifications. Lake names and descriptive river widths still come from their existing
loaders. Raw stream lines and dam-cut rules are unchanged; graph joins and portage feet are
regenerated against the trial banks. The complete join-identity and dam/portage audit is
pending, since no tolerance qualifies. Nearest-node diagnostics in `graph-joins.json` are
not identity-matched movements and are not presented as that audit.

A stream-specific comparison matches each former shore join to the same raw, dam-cut stream
piece, allowing the 0.1 m coordinate-encoding distance for association. Abisko retains a
water-network join on all **33** pieces; nearest old/new join displacement is **6.433 /
22.208 / 35.772 m** (median / p95 / maximum). Malingsbo-Kloten retains one for **47 of 50**
former nodes, with **3.262 / 32.054 / 111.639 m** displacement. The other three nodes belong
to two tiny stream fragments, **1.678217 m** and **0.108450 m**, now wholly inside Marktäcke
water rather than on its bank. Their former bank positions lie **1.259296 / 1.498802 m**
inside the new water. These diagnostics distinguish removed internal interfaces from
vanished stream mouths; they do not replace the complete dam/portage audit. The raw
cut-stream Parquets are byte-identical across the three tolerances on each Swedish map.

**The inland reading.** The prototype drive samples each contiguous paddled run every 0.1 m,
including its endpoint, against unsimplified source water. It restores the plan, mode, goal
way and view. The gate is maximum inland distance ≤ tolerance + 0.1 m; the longest exact
land run is informational because a curved bank permits a long shallow excursion. Abisko’s
new 2 m reading passes. Malingsbo-Kloten’s shore and bay pass but its portage fails at
**5.558376 m** inland near (59.914501001, 15.462782183), on a **2.500382 m** straight
paddled piece with no graph source in the tally. The 25 m grid classifies that piece as
water. It is identical at 5 / 3 / 2 m, so all three scene gates fail there. No source
containment, offset or connector/tally rule is changed to conceal it.

**What the reader sees.** These are fixed-tap measurements of the baseline and the 2 m
trial, not accepted replacement drive figures. Paddled and on-foot lengths are the page’s
public figures. Inland maxima use contiguous 0.1 m sampling; earlier stop tables used
coarser or per-part samples.

| Map / reading | Paddled m, before → 2 m | On foot m, before → 2 m | Maximum inland m, before → 2 m | Longest land run m, before → 2 m |
|---|---:|---:|---:|---:|
| abisko / kayak_shore | 2116.110 → 2192.258 | 0.000 → 0.000 | 9.950 → 1.866 | 115.524 → 78.765 |
| abisko / kayak_bay | 1408.028 → 1261.673 | 0.000 → 2.509 | 5.810 → 1.311 | 67.152 → 34.747 |
| abisko / kayak_portage | 336.096 → 414.821 | 102.465 → 9.616 | 6.038 → 1.693 | 29.902 → 42.239 |
| malingsbo-kloten / kayak_shore | 2122.779 → 2034.313 | 0.000 → 0.000 | 9.349 → 1.755 | 163.722 → 47.922 |
| malingsbo-kloten / kayak_bay | 1066.143 → 1079.757 | 0.000 → 0.000 | 2.156 → 1.587 | 56.317 → 78.647 |
| malingsbo-kloten / kayak_portage | 1414.654 → 27.504 | 513.463 → 917.640 | 9.250 → 5.558 | 99.877 → 2.674 |
| malingsbo-kloten / korslangssmedja | 4296.406 → 4491.354 | 0.000 → 0.000 | 11.245 → 1.954 | 151.036 → 78.745 |
| malingsbo-kloten / phone_near_59_946_15_259 | 203.342 → 130.061 | 0.000 → 15.083 | 12.973 → 1.863 | 44.666 → 15.028 |
| malingsbo-kloten / phase2_bay | 1066.143 → 1079.757 | 0.000 → 0.000 | 2.156 → 1.587 | 56.317 → 78.647 |
| malingsbo-kloten / phase2_lake | 1698.700 → 1764.394 | 0.000 → 0.000 | 9.349 → 1.755 | 133.871 → 47.922 |
| malingsbo-kloten / phase2_portage | 1902.419 → 1869.886 | 598.441 → 553.592 | 12.786 → 14.718 | 111.024 → 71.820 |

The Norway 2 m scene reading was not started after the completed sweep met the explicit
budget stop; its baseline, 5 m and 3 m readings remain in the scratch report. The phone
image’s original taps were not recoverable. The shore-report figure locations do not match
the supplied vicinity, so this reading uses the requested fallback near (59.946, 15.259):
taps (59.945021131, 15.258398890) → (59.945941164, 15.259991638), the ends of a measured 300
m baseline shore arc nearest the supplied point. It is a reproducible site comparison, not a
claim to reproduce the original screenshot route. `reader-fixtures.json` records the
selection; the Korslångssmedja and phase-2 pairs retain their original taps.

**Walking on the rebuilt trials.** The revised gate is pruned/unpruned label equality for
the same 200 seeded pairs per map in both walking settings. Re-pricing the former way on the
new grid is informational after entry nodes move. The distribution below covers all 200
pairs per row, including unchanged ways; “changed” compares the reconstructed route parts,
so it includes very small noding movements. Longer/shorter uses a 1e-8 m threshold; positive
price excess uses 1e-7 weighted metres.

| Map | Setting | Changed | Longer / shorter | Absolute change median / p95 / max m | Relative change median / p95 / max % | Positive re-pricing excess count / max |
|---|---|---:|---:|---:|---:|---:|
| abisko | Walking | 93 | 48 / 45 | 0.000 / 270.748 / 6173.860 | 0.000 / 3.678 / 77.487 | 32 / 4122.587324 |
| abisko | Stay on paths | 97 | 43 / 54 | 0.000 / 41.736 / 608.324 | 0.000 / 1.466 / 11.527 | 34 / 828.315835 |
| malingsbo-kloten | Walking | 100 | 50 / 50 | 0.000 / 29.551 / 574.182 | 0.000 / 0.301 / 291.322 | 40 / 0.056372 |
| malingsbo-kloten | Stay on paths | 95 | 45 / 50 | 0.000 / 0.672 / 285.130 | 0.000 / 0.003 / 2.178 | 43 / 49.875335 |

For the changed pairs alone:

| Map | Setting | Absolute change median / p95 / max m | Relative change median / p95 / max % |
|---|---|---:|---:|
| abisko | Walking | 7.871 / 341.961 / 6173.860 | 0.055 / 10.399 / 77.487 |
| abisko | Stay on paths | 1.086 / 78.028 / 608.324 | 0.018 / 3.265 / 11.527 |
| malingsbo-kloten | Walking | 0.004 / 225.533 / 574.182 | 0.000 / 1.479 / 291.322 |
| malingsbo-kloten | Stay on paths | 0.003 / 56.196 / 285.130 | 0.000 / 0.305 / 2.178 |

All **800 completed Swedish walking label comparisons match**. Norway’s rebuilt-graph
walking replay remains pending at the budget stop; the earlier grid-only replay is not
substituted for it. Every longer-way outlier in these completed Swedish comparisons beyond
`max(2 % of old length, 50 m)` is listed below with its taps and explanation. The full
connector coordinates, prices and old/new wet-sample counts are in
`walking-final-outliers.json`; `walking-report.md` gives the per-pair details. Pair numbers
below are one-based.

| Map / setting / pair | Taps, lat lon → lat lon | Route m, before → after | Why the longer way is chosen |
|---|---|---:|---|
| abisko / walking / 26 | 68.243051733 18.422707876 → 68.247466226 18.405288406 | 872.918 → 950.314 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| abisko / walking / 30 | 68.381330494 18.928358427 → 68.359743134 18.912754371 | 2605.625 → 2875.736 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| abisko / walking / 52 | 68.353504000 18.936781000 → 68.372263864 18.925462024 | 2341.948 → 4156.650 | Changed wet samples move the preferred entry/exit under water price 30. |
| abisko / walking / 128 | 68.348361289 18.480686130 → 68.346321041 18.492564791 | 667.734 → 950.578 | Changed wet samples move the preferred entry/exit under water price 30. |
| abisko / walking / 180 | 68.187173000 18.628745000 → 68.399840785 19.022687988 | 42652.742 → 43745.613 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| abisko / paths / 77 | 68.197836622 18.608484135 → 68.384029318 18.822435423 | 28422.168 → 29030.492 | Changed wet samples move the preferred entry/exit under water price 30. |
| abisko / paths / 186 | 68.404934981 19.071802038 → 68.398513789 19.052059257 | 1138.028 → 1269.212 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| malingsbo-kloten / walking / 34 | 60.169362209 15.058040371 → 60.153091817 15.164405431 | 10897.505 → 11133.704 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| malingsbo-kloten / walking / 42 | 60.063395062 15.323839511 → 60.065192177 15.323086771 | 204.564 → 778.746 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| malingsbo-kloten / walking / 62 | 60.065146039 15.323350741 → 60.063395062 15.323839511 | 196.972 → 770.795 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| malingsbo-kloten / walking / 133 | 60.151887531 15.166031857 → 60.110091490 15.203019839 | 6220.053 → 6452.331 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| malingsbo-kloten / paths / 34 | 60.169362209 15.058040371 → 60.153091817 15.164405431 | 10897.505 → 11133.704 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |
| malingsbo-kloten / paths / 133 | 60.151887531 15.166031857 → 60.110091490 15.203019839 | 6314.768 → 6452.331 | Rebuilt noding changes the offered entry/exit; the old connector’s wet samples are unchanged. |

**Recorded walking readings.** The same 21 selected checks were run on all three baselines
and the two Swedish 2 m trials. Norway’s 2 m recorded readings remain pending at the budget
stop. Full before/after readings, including non-distance state and exported-file
differences, are retained in `walking-selected-{before,after}-<park>.jsonl` and
`walking-drive-differences.json`. The trials are not claimed green: baseline checks already
expose the Details-page expectation and, on Abisko/Norway, a full undo-history restoration
difference. The changed recorded figures below have not been installed for a rejected
tolerance. Smaller walking changes arise from the finer shared water classification and the
rebuilt entry nodes, with the walking price unchanged.

| Map / recorded figure | Before | 2 m trial |
|---|---|---|
| abisko / dry way figures bytes | 1415f8f3f206b2051cfbb0946b410a01db711a1b11b1f996cdccde410a0f834a | e55f2166241da50dc095fd745f1ff7f2f9dff8ed78abeab4035b8506cba0bc3b |
| abisko / dry way GPX description bytes | b07496c3129f74d2fcd5ee366a8acaf53f13a8a86bcde2b94f49ce2de86be62c | 3c6ed6696078211fdff2f9556c135bf05b3fec2e092950d4e2d5295ce724ee57 |
| abisko / walking: shore-pair foot, m | 2940.88 | 2935.858 |
| abisko / walking: shore-pair water, m | 15.273 | 20.295 |
| abisko / walking: shore-pair straight land, m | 514.362 | 509.34 |
| abisko / stay on paths: shore-pair foot, m | 2963.41 | 2948.287 |
| abisko / stay on paths: shore-pair water, m | 15.283 | 30.405 |
| abisko / stay on paths: shore-pair straight land, m | 510.746 | 495.624 |
| abisko / saved reload plan, kB | 467 | 465 |
| malingsbo-kloten / dry way figures bytes | d3051c9e206aa2822e5e91206e1ad95f6fe254a8fcdd7739d04829a95ea00dd2 | 72c4041536068c8459dda7bb554ba70aa85cb523fbe596a500b983b7d764c3f9 |
| malingsbo-kloten / Dammtjärnsbäcken width, m | 66 | None |
| malingsbo-kloten / saved reload plan, kB | 648 | 653 |

**The recorded Dammtjärnsbäcken way exceeds its retained bound.** `a_goal_the_reader_sets()`
calls `wading_to_a_goal()` with the scene’s standing point **(59.826928, 15.173356)** and
goal **(59.828695, 15.168055)**. The saved drive reports a change from the short straight
way to the road. A separate sequential reading of the same goal confirms the full lengths
below, with both modes and the goal way restored.

| Setting | On foot m, before → 2 m | Water m, before → 2 m | Total m, before → 2 m |
|---|---:|---:|---:|
| Walking | 351.572461 → 2343.035623 | 5.022464 → 0.000000 | 356.594924 → 2343.035623 |
| Stay on paths | 2343.035262 → 2343.035623 | 0.000000 → 0.000000 | 2343.035262 → 2343.035623 |

Ordinary walking grows **1,986.440699 m / 557.058 %**, against `max(0.02 × 356.594924 m, 50
m)` = **50 m**. Replaying the old direct line’s pricing samples gives **2 of 15 wet** on the
old grid and **4 of 15 wet** on Marktäcke. This explains why the road can win under the
unchanged water price of 30. The former 66 m river-width description is absent because the
selected way now avoids that straight river crossing; its loader was not replaced. The
revised random-pair exemption does not cover this recorded scene. This is an additional stop
under the retained walking-length bound, not a re-pricing defect. The evidence is
`recorded_river_stop.py`, `recorded-river-stop.json` and the before/after walking drive
logs. The full recorded-way audit is still pending; these readings must not be described as
all within the accepted bound.

The dry Abisko goal also changes its displayed profile from **+382 / −332 m, steepest 76 %**
to **+373 / −323 m, steepest 49 %**, with **6,420 → 6,418** points. Its dry-route length is
**16,700.517542 → 16,700.516431 m**, with zero water in both. This is a height-profile
change, not water reclassification. Rebuilding re-samples the noded edges; lake levelling
itself is restricted to Shore/Open water. The exact changed extremum has not been traced.
Malingsbo-Kloten’s dry goal changes **9,076 → 9,079** points, with unchanged displayed GPX
figures and length **22,957.427997 → 22,957.428482 m**. The captured goal data and HTML
diffs preserve the words behind the hashes.

The reload check chooses taps by fractions of the selected chain’s vertex count. Its walked
figures change **16,836 → 16,798 m** in Abisko and **22,796 → 22,964 m** in
Malingsbo-Kloten; those taps move when the graph is re-noded, so these are not fixed-tap
route comparisons.

Other measured route-length and invariant changes are retained in the scratch comparison;
elapsed times, graph node indices and exported coordinate counts are not route-length
changes. The final recorded-way audit and phase-9 notes beside accepted replacement figures
remain pending with tolerance selection.

**Built 2026-09-24 — The full nine-page experiment.** All three maps at 5 / 3 / 2 m were
built sequentially by `command make map`, including its graph build, on cached inputs under
a no-download/no-cache-write guard. All 1,800 kayak comparisons and the 800 completed
Swedish walking comparisons pass. No final tolerance is selected, so the final-graph walking
gate remains pending on all three maps; Norway’s 2 m trial replay was not started after the
sweep met the explicit stop. The source/test/drive prototype is saved as
`production-prototype-current.patch` and `prototype-current/` in the scratch directory; the
two records alone are committed. Final graph/map builds, the join audit, updated recorded
figures and twice-green drives remain pending at the budget, recorded-walking and
connector-gate stop. No tiles, push or publication.

Review must decide the performance/payload budgets or the extra work permitted to meet them,
the recorded Dammtjärnsbäcken route change under its retained length bound, and the
inland-deviation requirement for straight pieces classified by the 25 m grid. There is no
further walking re-pricing stop.

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

The Swedish network and the shared 25 m pricing grid now read cached Marktäcke `Sjö` and
`Vattendragsyta`. Norway retains N50. Municipal and feature pieces are dissolved before
rings are extracted: only the water union's boundary is Shore. The 1 ha cutoff uses each
connected body's union area before map cropping; delivery fragments survive when their body
qualifies. Smaller ponds remain in the grid. Lake components retain their registered or
shore-derived planes, while river interiors retain sampled heights. A lake/river mouth is
emitted once as Open water at its adjacent lake's level. The Swedish page credits Marktäcke
Nedladdning, vektor, © Lantmäteriet, CC BY 4.0 for both paddle water and the shared grid,
and identifies the modifications and Topografi 50 dam points.

The shore tolerance is 5 m, as review selected from the complete 5 / 3 / 2 m sweep. The
constant names the measured p95 deviation, page growth and review's accepted search growth.
No offset or centre-line geometry is introduced. Walking keeps factor 30 and midpoint
pricing. The final grid matches the shared-grid 5 m prototype byte for byte; Norway's grid
also matches phase 8.

Dam and lock-gate discs extend the existing 25 m stream exclusion to Shore and Open water.
Analytic segment/circle intersections cut the completed lines, so the exclusion's perimeter
cannot become a new cheap shore. Stream pieces retain the earlier along-line cuts and are
also clipped against discs if they curve back toward a structure. The encoded page carries
the compact point list; kayak midpoint pricing and straight-part classification treat
samples inside discs as land. Walking continues to read the shared grid without applying dam
discs. Uniform-cell batching stops before cells touching a disc, with 7,000 independent
scalar connector checks covering the prices.

The new network has 105,088 / 289,548 / 398,191 edges (Abisko / Malingsbo-Kloten /
Lomsdal-Visten). Relative to the accepted one-copy-interface candidate, Abisko adds 26 edges
and MK adds 948 through explicit stream junctions and dam cuts; Norway is unchanged. The
earlier isolated interface correction removed 131 / 191 duplicate graph edges, and 3,306.252
/ 2,779.675 m of coincident river-side mouth geometry. The final interface audits find no
duplicate lake/river chords. Abisko's bank profile now has all 417 heights at 342 m, instead
of 342–342.700012 m.

All 33 former Abisko and 50 former MK stream-to-shore joins still have a surface join on the
same stream. Median / p95 / maximum shifts are 6.524 / 21.254 / 27.194 m and 4.437 / 33.257
/ 111.639 m respectively. Explicit vertices at enclosed-stream attachments survive
reprojection as shared nodes. The three identified MK stream pieces now reach the surface
and are reachable from it under directed traversal; all three are bidirectional after the
unchanged phase-7 height rule. The Abisko piece remains one-way and also has surface
connectivity in both traversal directions.

MK's replacement bank fixture is (59.885716, 15.671236) → (59.880484, 15.664768). It follows
831.576 m of Shore, exactly its measured Shore-plus-mouth reference, without a carry or
Open-water shortcut. Its direct chord is 686.258 m with 367.638 m classified wet. The search
selected this nearby pair from actual all-Shore routes with a mostly wet direct chord. The
carry fixture is (59.924691, 15.434425) → (59.919958, 15.439938): 619.511 m paddled and
46.348 m routed carry, with network paddle on both sides. It was selected from nearby
portage edges with shore approaches and a measured longer walking-path alternative including
its landing ties (987.719 m). The original shore/carry taps remain in the reader comparison
and the original shore taps remain in walking's regression reading.

Uwe's acceptance of the three intermediate walking changes is retained as history. On the
final graph the MK helper is 9,284.155 m, within 3.706 m of its original 9,287.861 m, after
the dam-related noding replaces the earlier 9,590.349 m candidate. Across Dammtjärnsbäcken
remains 2,343.036 m and Norway's typed leg remains 1,066.298 m. The MK dry route's HTML
changes only from 9,076 to 9,074 points; its route length changes by about 1 mm and its GPX
descriptions are byte-identical. The walking long-edge fixture retains the same 3,439.494 m
Topografi 50 road, renumbered 66935 → 67026.

Norway’s dry route changes only from 7,639 to 7,640 points in the details page, with about 6
mm of length change and byte-identical GPX descriptions.

Abisko retains the dry-profile change already reported during the shared-grid investigation:
+382 / −332 m becomes +373 / −323 m, the displayed steepest slope changes 76 % → 49 %, and
the point count changes 6,420 → 6,418 while the route length changes by less than 1 mm. The
final walking reading records the changed HTML and GPX descriptions. Rebuilding re-samples
noded walking edges; the lake-level pass still applies only to the water sources. The
particular removed height extremum was not separately traced.

**Dam exclusions and directed joins.**

Final graph and map builds completed sequentially under an 8 GiB address-space cap. The raw
geometry check allows only 0.0000001 m of projection round-off.

| Map | Points / discs intersecting eligible surface | Pre-fix PADDLE edges entering discs | Final | Graph edges before → after |
|---|---:|---:|---:|---:|
| abisko | 0 / 0 | 0 | 0 | 105062 → 105088 |
| malingsbo-kloten | 108 / 98 | 847 | 0 | 288600 → 289548 |
| lomsdal-visten | 0 / 0 | 0 | 0 | 398191 → 398191 |

The source cut changed 136 MK Shore lines and 318 Open-water chords. Before the cut, the
finished graph had 448 Shore, 387 Open-water and 12 Stream edges inside discs. The final
closest raw PADDLE geometry is 24.999999994 m from a point. Norway has no dam-point input in
the phase-7 source set; this is not a claim that Norway has no dams.

All previously identified stream pieces now reach surface water and can be reached from it
in directed traversal. The three MK pieces are bidirectional after phase 7’s measured-height
gate (2 / 1 / 1 edges). The Abisko piece remains one-way; its endpoint-to-surface
reachability works in both traversal directions through the surface network.

Korslång fixed taps: (59.9440, 15.2620) ↔ (59.9525, 15.2500). Both directions agree with the
exhaustive reference and give 1,184.862869 m paddled / 115.351819 m on foot. The carry uses
108.464503 m of OSM path plus 6.887316 m of inferred bridge connections. PORTAGE-kind edge
metres are 0: the existing mapped walking path wins. Used PADDLE geometry stays 29.432742 m
from the dam. The pre-fix finer-water route was 1,297.898649 m paddle / 0 foot; the phase-8
route was 1,267.847554 / 77.105406 m.

The portage machinery is rerun on the new surface network. Its landings are compared
geometrically, not treated as persistent feature identities. The last column measures the
new water landings against the old water network; it is not the displacement of a matched
old landing.

| Map | Portage edges, old → final | Water landing ends, old → final | New ends to old water, median / p95 / max m |
|---|---:|---:|---:|
| abisko | 869 → 661 | 975 → 782 | 1.170 / 11.392 / 791.087 |
| malingsbo-kloten | 2240 → 2060 | 1433 → 1286 | 1.834 / 25.418 / 739.227 |
| lomsdal-visten | 1473 → 1511 | 1809 → 1883 | 0.505 / 7.861 / 167.751 |

All counted final water landing ends lie exactly on their own raw PADDLE network. Other ends
are audited against the map crop and adjacent land sources below. The expanded circular
stream cut removes a further 4.539991 m in MK; Abisko’s cut stream geometry is unchanged.

Applying the circular cut to the 847 affected pre-fix graph edges trims 521 and removes 326
entirely; 18 of the trimmed edges split into multiple pieces. These are outcomes for the old
geometry, distinct from the final graph’s re-noding counts.

The physical stream-direction comparison preserves every flag: the Abisko piece is one-way
before and after (50.418025 m); MK’s three pieces are bidirectional before and after. Their
lengths are 513.028315 → 512.855691 m, 1.678217 → 1.678217 m and 0.108450 → 0.108450 m.
Directed traversal on the final graph confirms surface reachability in both traversal
directions, while retaining the one-way Abisko edge.

The supplemental endpoint audit accounts for every non-water end as a map crop. MK has two
on its western boundary, at (59.959278012, 14.967000250) and (59.961121861, 14.967000250),
31.618315 / 33.166572 m from water; the second also meets an inferred bridge. Both lie
within 0.000000001 m of the projected map boundary. Norway’s sole end is at (65.431335559,
12.202386333), 49.628153 m from water and 0.000000002 m from the approach-zone boundary.
Abisko has no such end. The initial supplemental assertion omitted crop ends; its failed
capture is retained, and the corrected audit classifies the actual build boundary without
changing production geometry.

**Final payload, search and inland readings.**

| Map | Edges | Graph Brotli MB, before → after | Page Brotli MB, before → after | Page growth MB | Kayak p95 ms, before → after | Growth | Reference pairs kayak / walking / paths |
|---|---:|---:|---:|---:|---:|---:|---:|
| abisko | 105088 | 1.320681 → 1.683781 | 1.822895 → 2.188990 | 0.366095 | 181.150 → 261.350 | +44.27% | 200 / 200 / 200 |
| malingsbo-kloten | 289548 | 4.897322 → 5.724069 | 7.116118 → 7.943361 | 0.827243 | 1016.850 → 1709.400 | +68.11% | 200 / 200 / 200 |
| lomsdal-visten | 398191 | 5.376381 → 6.016864 | 7.085092 → 7.727324 | 0.642232 | 2085.400 → 2772.950 | +32.97% | 200 / 200 / 200 |

The same 200 phase-8 taps are replayed. Timing jobs run sequentially, with four warm-up
pairs and no overlapping build or browser. Brotli quality is 11. The reference is exhaustive
and unpruned; it shares exact connector pricing including the kayak-only dam discs.
Independent scalar midpoint tests cover 7,000 connectors. Subsequent walking-reference runs
batch identical midpoint counts in uniform cells, without dam exclusions or search pruning.
Before these runs, 12,000 real-page connector prices match the unchanged scalar walking
price exactly. Earlier walking runs retain the scalar price throughout.

| Map / scene | Maximum network inland m | Longest network land run m (information) | Connector maximum inland m / longest run m (information) |
|---|---:|---:|---:|
| abisko / shore | 4.769376 | 96.257769 | 0.000000 / 0.000000 |
| abisko / bay | 4.437900 | 69.496440 | 0.000000 / 0.000000 |
| abisko / portage | 3.930065 | 57.357794 | 0.000000 / 0.000000 |
| malingsbo-kloten / shore | 4.314828 | 119.936304 | 0.000000 / 0.000000 |
| malingsbo-kloten / bay | 3.751576 | 103.941662 | 0.000000 / 0.000000 |
| malingsbo-kloten / portage | 2.606345 | 131.803892 | 0.000000 / 0.000000 |
| lomsdal-visten / shore | 3.624053 | 94.384068 | 0.000000 / 0.000000 |
| lomsdal-visten / bay | 3.624053 | 94.384068 | 0.000000 / 0.000000 |
| lomsdal-visten / portage | 4.025395 | 103.133317 | 0.000000 / 0.000000 |

**The fixed reader pairs and replacement fixtures.**

| Map / fixed-tap leg | Paddled m, before → after | On foot m, before → after | Maximum inland m, before → after | Longest land run m, before → after |
|---|---:|---:|---:|---:|
| abisko / kayak_shore | 2116.110 → 2167.118 | 0.000 → 0.000 | 9.950 → 4.769 | 115.524 → 96.258 |
| abisko / kayak_bay | 1408.028 → 1416.986 | 0.000 → 0.000 | 5.810 → 4.438 | 67.152 → 69.496 |
| abisko / kayak_portage | 336.096 → 417.749 | 102.465 → 1.450 | 6.038 → 3.930 | 29.902 → 57.358 |
| malingsbo-kloten / kayak_shore | 2122.779 → 1904.659 | 0.000 → 5.025 | 9.349 → 4.580 | 163.722 → 66.264 |
| malingsbo-kloten / kayak_bay | 1066.143 → 1073.404 | 0.000 → 0.000 | 2.156 → 3.752 | 56.317 → 103.942 |
| malingsbo-kloten / kayak_portage | 1414.654 → 2.512 | 513.463 → 942.055 | 9.250 → 5.560 | 99.877 → 2.511 |
| malingsbo-kloten / korslangssmedja | 4296.406 → 4419.018 | 0.000 → 0.000 | 11.245 → 4.822 | 151.036 → 100.076 |
| malingsbo-kloten / phone_near_59_946_15_259 | 203.342 → 126.625 | 0.000 → 15.083 | 12.973 → 3.519 | 44.666 → 10.437 |
| malingsbo-kloten / phase2_bay | 1066.143 → 1073.404 | 0.000 → 0.000 | 2.156 → 3.752 | 56.317 → 103.942 |
| malingsbo-kloten / phase2_lake | 1698.700 → 1740.551 | 0.000 → 0.000 | 9.349 → 4.580 | 133.871 → 48.730 |
| malingsbo-kloten / phase2_portage | 1902.419 → 1952.227 | 598.441 → 560.819 | 12.786 → 14.718 | 111.024 → 98.602 |
| lomsdal-visten / kayak_shore | 932.128 → 938.729 | 0.000 → 0.000 | 9.982 → 3.624 | 146.339 → 94.384 |
| lomsdal-visten / kayak_bay | 715.252 → 699.661 | 0.000 → 0.000 | 9.582 → 3.624 | 77.196 → 94.384 |
| lomsdal-visten / kayak_portage | 1597.100 → 1788.717 | 124.947 → 454.048 | 9.227 → 4.025 | 180.661 → 103.133 |

The fixed taps are retained here. Inland figures include grid-classified paddled connectors;
only used network PADDLE edges are gated in the drive. The screenshot uses the documented
fallback near 59.946, 15.259, because the original taps could not be recovered.

The screenshot’s whole drawn route, including any on-foot pieces:

| Variant / leg | Maximum inland distance m | Longest land run m |
|---|---:|---:|
| baseline / phone_near_59_946_15_259 | 12.973199 | 44.665845 |
| final / phone_near_59_946_15_259 | 4.913701 | 10.436525 |

The phase-2 carry leg’s 14.717929 m maximum is a grid-classified paddled connector; its used
network pieces reach at most 4.126528 m inland. The retained original MK carry’s 5.559623 m
maximum is also a connector.

Replacement MK drive fixtures, selected on the final network:

| Fixture | Taps, latitude / longitude | Paddled m | On foot m | Measured reference m |
|---|---|---:|---:|---:|
| bank | (59.885716, 15.671236) → (59.880484, 15.664768) | 831.576 | 0.000 | 831.576 |
| carry | (59.924691, 15.434425) → (59.919958, 15.439938) | 619.511 | 46.348 | 987.719 |

**Walking distributions and the retained bound.**

All statistics use the 200 frozen phase-8 pairs per map and setting. Changed means the route
parts differ; percentile statistics include all 200 pairs. Old-way re-pricing is information
because graph entry nodes changed. A positive difference means the new answer costs more
than the recorded old way re-priced on the new grid; values are router prices, not route
lengths.

| Map / setting | Changed | Longer / shorter | Absolute change median / p95 / max m | Relative change median / p95 / max % | Positive new-minus-old price: count / max |
|---|---:|---:|---:|---:|---:|
| abisko / walking | 93 | 55 / 38 | 0.000000 / 54.586882 / 6173.860418 | 0.000000 / 1.965435 / 77.486860 | 38 / 4122.587324 |
| abisko / paths | 97 | 52 / 45 | 0.000000 / 42.875544 / 608.326989 | 0.000000 / 1.529649 / 5.197268 | 45 / 828.315835 |
| malingsbo-kloten / walking | 100 | 49 / 51 | 0.000002 / 29.551195 / 574.181583 | 0.000000 / 0.301219 / 291.322122 | 39 / 0.028456 |
| malingsbo-kloten / paths | 95 | 47 / 48 | 0.000000 / 0.034292 / 285.121530 | 0.000000 / 0.000672 / 2.178443 | 43 / 205.010097 |
| lomsdal-visten / walking | 77 | 45 / 32 | 0.000000 / 176.411511 / 2371.469361 | 0.000000 / 1.828030 / 66.231444 | 42 / 4948.980566 |
| lomsdal-visten / paths | 80 | 45 / 35 | 0.000000 / 122.674222 / 1081.405132 | 0.000000 / 0.636793 / 66.231444 | 42 / 4948.980566 |

Every random increase exceeding max(2%, 50 m):

| Map / setting / pair | Taps, latitude / longitude | Length m, before → after | Measured explanation |
|---|---|---:|---|
| abisko / walking / 25 | (68.243051733, 18.422707876) → (68.247466226, 18.405288406) | 872.917682 → 951.366892 | 2 newly available entry/bend nodes used |
| abisko / walking / 51 | (68.353504000, 18.936781000) → (68.372263864, 18.925462024) | 2341.948253 → 4156.650412 | before connectors' priced water 992.889 → 1017.711 m; 1 old entry/bend nodes absent; nearest replacements 10.855 m |
| abisko / walking / 127 | (68.348361289, 18.480686130) → (68.346321041, 18.492564791) | 667.734344 → 950.578299 | before connectors' priced water 0.000 → 24.109 m |
| abisko / walking / 179 | (68.187173000, 18.628745000) → (68.399840785, 19.022687988) | 42652.742315 → 43745.615750 | after connectors' priced water 3823.597 → 3798.756 m; 2 old entry/bend nodes absent; nearest replacements 0.511 m, 13.207 m |
| abisko / paths / 69 | (68.399112584, 19.044229548) → (68.420551874, 19.034684148) | 2495.332083 → 2599.174847 | 1 old entry/bend nodes absent; nearest replacements 0.607 m; 1 newly available entry/bend nodes used |
| abisko / paths / 76 | (68.197836622, 18.608484135) → (68.384029318, 18.822435423) | 28422.168189 → 29030.495178 | before connectors' priced water 3233.981 → 3283.266 m; after connectors' priced water 3192.440 → 3217.212 m; 1 old entry/bend nodes absent; nearest replacements 4.197 m |
| malingsbo-kloten / walking / 33 | (60.169362209, 15.058040371) → (60.153091817, 15.164405431) | 10897.505443 → 11133.705093 | after connectors' priced water 582.268 → 533.745 m |
| malingsbo-kloten / walking / 41 | (60.063395062, 15.323839511) → (60.065192177, 15.323086771) | 204.564051 → 778.745634 | after connectors' priced water 24.913 → 0.000 m |
| malingsbo-kloten / walking / 61 | (60.065146039, 15.323350741) → (60.063395062, 15.323839511) | 196.972019 → 770.795085 | after connectors' priced water 24.301 → 0.000 m |
| malingsbo-kloten / walking / 132 | (60.151887531, 15.166031857) → (60.110091490, 15.203019839) | 6220.052996 → 6452.331124 | after connectors' priced water 684.969 → 635.650 m |
| malingsbo-kloten / paths / 33 | (60.169362209, 15.058040371) → (60.153091817, 15.164405431) | 10897.505443 → 11133.705093 | after connectors' priced water 582.268 → 533.745 m |
| malingsbo-kloten / paths / 132 | (60.151887531, 15.166031857) → (60.110091490, 15.203019839) | 6314.767531 → 6452.331124 | after connectors' priced water 684.969 → 635.650 m |
| lomsdal-visten / walking / 8 | (65.764467047, 12.380071756) → (65.796612921, 12.337392706) | 5110.394940 → 5215.670069 | 2 old entry/bend nodes absent; nearest replacements 199.650 m, 129.393 m; 1 newly available entry/bend nodes used |
| lomsdal-visten / walking / 39 | (65.618703642, 12.710460940) → (65.704707101, 12.216376696) | 43995.138019 → 46366.607380 | 1 old entry/bend nodes absent; nearest replacements 401.096 m |
| lomsdal-visten / walking / 84 | (65.745475856, 12.490797704) → (65.741685717, 12.477406797) | 745.474638 → 1239.213259 | 2 newly available entry/bend nodes used |
| lomsdal-visten / walking / 87 | (65.781097122, 12.527171445) → (65.771447117, 12.540733481) | 6856.751992 → 7021.890387 | 1 old entry/bend nodes absent; nearest replacements 3.117 m; 1 newly available entry/bend nodes used |
| lomsdal-visten / walking / 115 | (65.463569000, 12.210641000) → (65.565686591, 12.176846527) | 15177.341180 → 15806.163890 | 1 old entry/bend nodes absent; nearest replacements 468.050 m; 1 newly available entry/bend nodes used |
| lomsdal-visten / walking / 173 | (65.641428933, 12.089060182) → (65.524944379, 12.311521940) | 22837.479528 → 24139.644188 | 1 old entry/bend nodes absent; nearest replacements 7.445 m |
| lomsdal-visten / paths / 8 | (65.764467047, 12.380071756) → (65.796612921, 12.337392706) | 5110.394940 → 5215.670069 | 2 old entry/bend nodes absent; nearest replacements 199.650 m, 129.393 m; 1 newly available entry/bend nodes used |
| lomsdal-visten / paths / 67 | (65.575255000, 12.263511000) → (65.576178031, 12.238388581) | 1238.362036 → 1468.486418 | 2 old entry/bend nodes absent; nearest replacements 14.166 m, 6.383 m |
| lomsdal-visten / paths / 84 | (65.745475856, 12.490797704) → (65.741685717, 12.477406797) | 745.474638 → 1239.213259 | 2 newly available entry/bend nodes used |
| lomsdal-visten / paths / 87 | (65.781097122, 12.527171445) → (65.771447117, 12.540733481) | 7700.272801 → 7865.411196 | 1 old entry/bend nodes absent; nearest replacements 3.117 m; 1 newly available entry/bend nodes used |
| lomsdal-visten / paths / 115 | (65.463569000, 12.210641000) → (65.565686591, 12.176846527) | 15177.341180 → 15806.163890 | 1 old entry/bend nodes absent; nearest replacements 468.050 m; 1 newly available entry/bend nodes used |

**Every changed stored or measured walking figure.**

Every changed stored expectation or measured figure (`stands`) in the complete walking
readings is listed here. Some old expectations already differed from the baseline
measurement within their tolerance; these are shown separately. Structural assertions and
timing notes are not stored figures. Frozen fixed-input route lengths, both settings, are
listed separately in final-walking-distribution.md.

| Map | Check / figure | Stored before → after | Measured before → after |
|---|---|---|---|
| abisko | a_dry_way_keeps_its_words / dry way figures bytes | "1415f8f3f206b2051cfbb0946b410a01db711a1b11b1f996cdccde410a0f834a" → "e55f2166241da50dc095fd745f1ff7f2f9dff8ed78abeab4035b8506cba0bc3b" | "1415f8f3f206b2051cfbb0946b410a01db711a1b11b1f996cdccde410a0f834a" → "e55f2166241da50dc095fd745f1ff7f2f9dff8ed78abeab4035b8506cba0bc3b" |
| abisko | a_dry_way_keeps_its_words / dry way GPX description bytes | "b07496c3129f74d2fcd5ee366a8acaf53f13a8a86bcde2b94f49ce2de86be62c" → "3c6ed6696078211fdff2f9556c135bf05b3fec2e092950d4e2d5295ce724ee57" | "b07496c3129f74d2fcd5ee366a8acaf53f13a8a86bcde2b94f49ce2de86be62c" → "3c6ed6696078211fdff2f9556c135bf05b3fec2e092950d4e2d5295ce724ee57" |
| abisko | the_walking_modes_never_take_the_water / walking: shore-pair foot, m | 2940.88 → 2935.858 | 2940.88 → 2935.858 |
| abisko | the_walking_modes_never_take_the_water / walking: shore-pair water, m | 15.273 → 20.295 | 15.273 → 20.295 |
| abisko | the_walking_modes_never_take_the_water / walking: shore-pair straight land, m | 514.362 → 509.34 | 514.362 → 509.34 |
| abisko | the_walking_modes_never_take_the_water / stay on paths: shore-pair foot, m | 2963.41 → 2948.287 | 2963.41 → 2948.287 |
| abisko | the_walking_modes_never_take_the_water / stay on paths: shore-pair water, m | 15.283 → 30.405 | 15.283 → 30.405 |
| abisko | the_walking_modes_never_take_the_water / stay on paths: shore-pair straight land, m | 510.746 → 495.624 | 510.746 → 495.624 |
| abisko | a_goal_the_reader_sets / and what width it says | 22 → 20 | 20 → 20 |
| abisko | a_plan_survives_a_reload / what it weighs | 463 → 465 | 467 → 465 |
| malingsbo-kloten | a_dry_way_keeps_its_words / dry way figures bytes | "d3051c9e206aa2822e5e91206e1ad95f6fe254a8fcdd7739d04829a95ea00dd2" → "b9a411766c5ef37323f63a931694a29c6ebe53cb2e958b016be2d588d820624d" | "d3051c9e206aa2822e5e91206e1ad95f6fe254a8fcdd7739d04829a95ea00dd2" → "b9a411766c5ef37323f63a931694a29c6ebe53cb2e958b016be2d588d820624d" |
| malingsbo-kloten | a_plan_survives_a_reload / what it weighs | 647 → 652 | 648 → 652 |
| malingsbo-kloten | a_goal_the_reader_sets / and what width it says | 66 → "removed: the measured road replaces the ford" | 66 → "no crossing-width reading on the road" |
| lomsdal-visten | a_dry_way_keeps_its_words / dry way figures bytes | "947b637bac5278a41f57909091389c92e3f61ad4c5e6030e71ae50236b74f763" → "1c833efcdee246885861efc62e9c16ea14504ae5bddd4483be8d63b7e4a9e3bb" | "947b637bac5278a41f57909091389c92e3f61ad4c5e6030e71ae50236b74f763" → "1c833efcdee246885861efc62e9c16ea14504ae5bddd4483be8d63b7e4a9e3bb" |
| lomsdal-visten | a_plan_survives_a_reload / what it weighs | 549 → 549 | 540 → 541 |

**Release validation.**

All three `command make graph` and `command make map` builds completed sequentially from
cached inputs, with an 8 GiB address-space cap and a guard against downloads and
shared-cache writes. The final 1,800 labels match the exhaustive reference: 200 seeded pairs
per map in kayak, ordinary walking and Stay on paths. The kayak reference includes the
dam-disc rule. Old-way re-pricing remains information because old entry nodes need not exist
on the new graph.

The inland drive samples used network PADDLE geometry every 0.1 m and gates maximum inland
distance at 5.1 m. Longitudinal land runs and grid-classified connectors are information. A
shallow simplified line can follow a curved bank for longer than 5 m without departing more
than 5 m inland. The existing kayak checks plus this reading pass twice per page in
`dam-release-v2/`; all 21 selected walking checks per page are captured there, with the
existing map-specific skips. The table above records every changed stored or measured
walking figure. Recorded route changes stay within max(2%, 50 m), except the changes
explicitly accepted by Uwe; the final helper is back inside that original bound.

The kayak/inland drives contain 148 / 185 / 151 readings per pass (Abisko / MK / Norway);
the complete walking drives contain 327 / 312 / 330. MK retains its three existing skips: no
sound-and-island scene, no taps measured for a loop that is not worth routing, and no
measured pair beside a path. Its long-edge check runs and passes. The Korslång channel check
belongs to MK and is skipped on the other two maps.

`command make hooks-run` is green with network access: ruff format/check, mypy, both test
suites and the standard hooks. The first run found missing type narrowing and a stale
source-text assertion; explicit casts and the assertion were corrected without changing
runtime values. The final drives use that checked drive source. No tile build, source
download, shared-cache write, push or publication. The phone screenshot's original taps
could not be recovered; its comparison uses the previously documented fallback near (59.946,
15.259).

Evidence is in `~/mockups/kayak-mode/phase9/`: `final-builds-dams.log`,
`final-measurements-dams.log`, `release-summary.json`, `final-reader-table.md`,
`final-walking-distribution.md`, `final-recorded-walking-figures.md`,
`dam-cut-route-audit.json`, `direction-before-after.json`, the per-map
join/interface/landing audits and `dam-release-v2/` drive captures. The full walking report
retains every changed frozen recorded input, including changes below the drive's display
precision. `hooks-phase9-final.log` records the repository checks. The historical stops
above are resolved by the dated decisions and this build.

### Phase 8 — Water first, 2026-09-23

Uwe: *"The kayak planner prefers long land ways to the water. I want a water way always
to be taken when possible. Unless a point is explicitly set on the land way, I would
always prefer the water way."* This supersedes the phase-2 choice of P = 2 as the trade
between water and land. The route now minimises **(land metres, existing price)** in that
order. There is no large multiplier. Shore 1, open water 1.5 and the former land prices
remain the secondary comparison, so a path beats equally long ground but cannot justify
a longer carry. Ferries (`CROSSING`) count **no land metres**, as do paddle edges;
every other edge kind counts its length. A ferry crosses water and retains its flat
secondary price. Its separate ferry credit in the measured Norway totals below is unchanged.

**The reconstruction and the prerequisite.** The phone's selected line is
`topografi-50-paths-514477-6645508-1136`, measured at 1,136.739 m by the page. Its ends are
(59.946736, 15.259137) and (59.951931, 15.273215). The cached Ortnamn place Korslångssmedja
is (59.946199, 15.259790); Lövudden and Skien fix the northern part of the screenshot.
The original taps are unknown. The measured pair is the closest wet paddle nodes beside
the path ends: **(59.945871, 15.258351) → (59.952097, 15.273234)**, nodes 99722 and 99796,
105.911 and 18.525 m from those ends.

Before the change: **125.031 m paddled, 1,352.730 m on foot**, with zero inferred-portage
edge metres. The foot metres comprise 1,295.087 Topografi 50 paths, 40.961 OSM,
4.953 Topografi 50 roads and 11.730 inferred bridge connectors. Excluding every non-paddle
edge before changing the search proves a directed water way already exists: **4,296.406 m**,
4,108.453 Shore and 187.953 Open water. The new public plan takes that way: **4,296.406 m
paddled and no land**. No graph repair or source change was needed.

**The search.** `plan_mode.js` carries land metres beside price in the edge table, node
labels and heaps. Both `routeBetween` and `joinedRoute` compare the pair, including their
seeds, partial edges, direct alternative and bounds. Ground connectors count their dry
grid pieces. Their floor combines a sampled dry prefix with the old cheapest-metre
price. A dry tap's unavoidable entry has its own conservative land floor. These are
lower bounds even when the connector crosses land; exact labels remain separate. Dry pieces are counted directly so that subtracting rounded lengths
cannot make an all-water connector's primary cost negative. Walking supplies zero land
throughout and keeps its old price arithmetic and ordering. Direction, snapping, tally
and words are unchanged. The old `PORTAGE_FACTOR` now affects only the secondary price.

**The measured ways.** Public assembled metres, **paddled / on foot**, read with the
saved pre-phase script and the new one against the same built graph:

| Map and leg | Before | After |
|---|---:|---:|
| Korslångssmedja reconstruction | 125.031 / 1,352.730 | 4,296.406 / 0 |
| Malingsbo-Kloten shore | 2,122.779 / 0 | 2,122.779 / 0 |
| Malingsbo-Kloten bay, also the phase-2 sweep bay | 1,066.143 / 0 | 1,066.143 / 0 |
| Malingsbo-Kloten scene portage | 5.912 / 1,274.726 | 1,414.654 / 513.463 |
| Phase-2 sweep lake | 1,698.700 / 0 | 1,698.700 / 0 |
| Phase-2 sweep portage | 51.555 / 1,220.934 | 1,902.419 / 598.441 |
| Abisko shore | 2,116.110 / 0 | 2,116.110 / 0 |
| Abisko bay | 1,408.028 / 0 | 1,408.028 / 0 |
| Abisko portage | 0 / 335.952 | 336.096 / 102.465 |
| Lomsdal-Visten shore | 932.128 / 0 | 932.128 / 0 |
| Lomsdal-Visten bay | 715.252 / 0 | 715.252 / 0 |
| Lomsdal-Visten portage | 0 / 959.690 | 1,597.100 / 124.947 |

The scene portage's **5.912 / 1,274.726 → 1,414.654 / 513.463** is the cost of
"always water" Uwe chose: a longer paddle to shorten the carry. None of these land totals
rises. The phase-7 Korslång channel pair still paddles 1,267.848 m in both directions;
its foot metres fall from 77.190 to **77.105**, with the same whole channel and OSM path
credit. Its inferred connectors shorten from 27.454 to 27.369 m.

**The drive.** `a_kayak_uses_water_before_land` reconstructs the peninsula pair on
Malingsbo-Kloten and uses wet shore nodes on the other maps. A separate, bounded traversal
of paddle arcs establishes connectivity in the journey's direction. The public plan must
paddle every part and carry no land; a point set on a mapped land node must still be reached
by the track. The helper puts its mode, goal way, plan and view back.

`a_portage_keeps_land_short` replaces `a_portage_takes_the_path`: every carry must be
shorter than the previously measured mapped way and account for all remaining ground,
including mapped paths and inferred portages. The first Abisko drive exposed
exactly the two obsolete assertions that all land was mapped and no inferred carry was
used: the shorter carry has 31.783 m of mapped path and 70.681 m of inferred ground.
Those assertions would contradict the new primary rule.
Malingsbo-Kloten carries its remaining 513.463 m on inferred ground, as does Lomsdal-Visten
for its entire 124.947 m. The mapped-path preference is tested between equal land lengths
in the routing tests, not imposed on a longer carry.

**Long legs and the cost of searching water first.** The longest connected spans found
among eight geographic extrema per graph component, tested in both directions for
reachability, were held fixed before and after. This is a reproducible long-leg search,
not a claim to the graph's exact diameter. Five warm `routeBetween` calls after a warm-up,
with the cost table already built, give the median below; this excludes page loading,
height reading and drawing. The browser clock reports whole milliseconds.

| Map | From → to, latitude and longitude | Span m | Before → after search ms |
|---|---|---:|---:|
| Malingsbo-Kloten | (60.161083, 15.919707) → (59.744644, 14.967000) | 70,616.815 | 57 → 95 |
| Abisko | (68.460000, 18.158645) → (68.139000, 19.100000) | 52,839.410 | 15 → 25 |
| Lomsdal-Visten | (65.917728, 12.663525) → (65.178687, 13.281342) | 87,208.359 | 69 → 107 |

| Map | Before paddled / on foot, m | After paddled / on foot, m |
|---|---:|---:|
| Malingsbo-Kloten | 45,088.792 / 60,755.095 | 108,200.291 / 37,871.831 |
| Abisko | 30,064.394 / 43,534.454 | 73,543.944 / 24,175.625 |
| Lomsdal-Visten | 82,479.134 / 54,681.079 | 90,650.675 / 49,419.031 |

Norway also takes ferries: **18,372.780 → 18,169.860 m**, excluded from both paddled and
foot metres above. Its first timing pass was 67 → 104 ms; the final pass, after separating
ferry credit from foot, ranges 67–74 → 102–111 ms. Malingsbo-Kloten ranges 56–85 → 91–104 ms,
Abisko 14–20 → 22–26 ms. The new ordering costs **38 / 10 / 38 ms** at these medians and
reduces land on every long leg. These timings concern network endpoints; they do not
measure the all-node connector search for a point off the network.

**Built 2026-09-23.** The three pages were built in this worktree with
`command make map ARGS="--park <park>"`, reading cached inputs under an 8 GiB address-space
cap. The earlier stop was resolved explicitly: `make map`'s ordinary in-memory graph
rebuilding is allowed; no graph source or content change or separate `make graph` is.
All three routing headers and inflated payloads compare **byte-identical** to the pages
used for the baseline. No shared cache file was written, no source was downloaded, and no
tile tree was built. The tile directories in this worktree's output are links to the
existing trees. Nothing was pushed or published.

The recorded figures changed in `drive_map.py`, named exactly:

| Scene | Recorded figure | Before → after, m |
|---|---|---:|
| Malingsbo-Kloten | `kayak portage water, m` | 5.912 → 1,414.654 |
| Malingsbo-Kloten | `kayak portage on foot, m` | 1,274.726 → 513.463 |
| Abisko | `kayak portage water, m` | 0 → 336.096 |
| Abisko | `kayak portage on foot, m` | 335.952 → 102.465 |
| Lomsdal-Visten | `kayak portage water, m` | 0 → 1,597.100 |
| Lomsdal-Visten | `kayak portage on foot, m` | 959.690 → 124.947 |
| Malingsbo-Kloten | `Korslång upstream on foot, m` | 77.190 → 77.105 |
| Malingsbo-Kloten | `Korslång downstream on foot, m` | 77.190 → 77.105 |

The new figures are `Korslångssmedja water, m` **4,296.406** and
`Korslångssmedja on foot, m` **0**. The unchanged shore and bay figures and phase-7 channel
water figures stand. Both walking settings' six recorded length figures and the two dry
figure/GPX hashes per map compare as **identical JSON bytes**, beyond the drive's numeric
tolerances. No walking snapshot was edited.

Two final drives per page: **135 / 135 readings** on Malingsbo-Kloten,
**110 / 110** on Abisko and **110 / 110** on Lomsdal-Visten, with no broken invariant,
moved figure or unrecorded figure. The other two scenes retain only their existing Korslång-channel skip. Every new reading runs on all three maps and verifies
restoration. The land-point probe chooses a mapped node with no paddle edge and a dry grid
neighbourhood: a shoreline junction shared with water would not exercise a carry.

The selected readings are `a_kayak_uses_water_before_land`,
`the_plan_page_has_the_price_switches`, `a_kayak_way_follows_the_shore`,
`a_bay_is_cut_and_a_lake_is_not`, `a_portage_keeps_land_short`,
`a_level_channel_is_paddled_both_ways`, `a_paddled_profile_is_flat`,
`the_walking_modes_never_take_the_water` and `a_dry_way_keeps_its_words`.
The 14 executable routing tests pass, as do the full **2,017 library and 97 pipeline tests**.
The hooks run with networking enabled before committing.

Scratch: `~/mockups/kayak-mode/phase8/`. `case.json` holds the prerequisite water-only
route; `before-*.json`, `after-*.json` and `built-malingsbo-kloten.json` hold the public
ways. `long-before-*.json` and `long-after-*.json` hold the connected timing pairs;
Norway's `*-ferries.json` files correct the separate ferry tally. The disconnected
extrema attempts in the earlier scene captures are not timing evidence.
`graph-comparison.json` and `final-readings.json` hold the byte comparisons. Final drives
are `drive-malingsbo-kloten-{2,3}.log`, `drive-abisko-{8,9}.log` and
`drive-lomsdal-visten-{4,5}.log`. `hooks-final.log` is the final hook run. The copied
harness leaves the reviewing session's originals untouched; it and all measurement
scripts restore the borrowed state and bound their graph walks.

**Review built 2026-09-23 — Off-network water first.** The reviewed commit `812433e`
seeded every node at zero land when the direct connector crossed dry ground. Its
connected-leg timings did not measure this work. The new measurements use taps beyond
150 m from both eligible nodes and edges. The short and long water pairs have dry direct
lines; zero-land tap-to-anchor connectors and a directed paddle-only search between the
anchors independently establish a water way. The ground pairs start on dry grid cells.
The Norwegian lake destination is inside cached N50 `Innsjø` row 60172. The initially
selected Norwegian ground case ends on `Havflate`; it remains an additional fjord stress
case, not a substitute for the lake reading.

Before means `812433e`, after means this amendment. The same graph and coordinates
are used on both sides. Firefox runs one warm-up followed by five measured `joinedRoute`
calls with the cost table already built. Times include floor construction, connector
sampling, search and reconstruction; they exclude page load, snapping, height lookup and
drawing. The browser clock resolves whole milliseconds. Measurements ran separately
from page builds and drives; Malingsbo-Kloten's baseline was repeated after candidate
selection finished. The table gives **median / worst** of the five warm calls. Counts
include the direct, entry and exit connector calls, not just exit seeds.

**Why the bounds remain admissible.** A floor's dry prefix uses the exact connector's
midpoints and counts only samples already read dry. Exact pricing resumes after that
prefix and reuses its measured length. Prefix work is capped between 16 and 32 samples;
the dry tap's nearest wet-node connector guides that cap, without being treated as a
lower bound itself. Both connectors through that node are priced exactly before the
result may serve as an initial complete way.

For a dry off-network start, the grid also supplies a rectangle of wholly dry cells,
expanded by at most 16 rings. For every possible entry node, the same linear interpolation
parameter used by the connector gives its first exit from that rectangle. If its line
has N pieces and remains inside until t, only `max(0, floor(N*t) - 1)` pieces are counted.
This deliberately leaves a whole sample behind the boundary and remains conservative
when the node is inside the rectangle. The smallest such land floor over all nodes is
compulsory for every network way, so it may be added to the suffix queue's floor. No
physical-distance approximation to a shore is used.

As exact suffixes settle, exact entries tighten the best complete **(land, price)** pair.
Both queues stop only when their lower bounds cannot beat that pair. A positive-land
incumbent never caps the secondary price of a way with less land. Once zero land is
found, the secondary bound is the price of that complete zero-land way, not the direct
line's price. Connector sampling may stop as soon as its dry subtotal, plus any
compulsory entry land, exceeds the applicable exact-node or whole-way bound. Equality
still reads the remaining samples and compares the old price. The heap and both searches'
comments now describe the lexicographic ordering.

Ferries remain zero land with their flat secondary price; every other non-paddle edge
kind contributes its length. In these new Norway measurements the long water pair uses
9,376.712 m of ferry and the fjord ground pair 1,518.609 m, unchanged by the amendment.
Those metres are separate from paddled and on-foot totals.

| Map / leg | Warm ms, median / worst, before → after | Floors pushed, before → after | Connector calls, before → after (completed after) |
|---|---:|---:|---:|
| Malingsbo-Kloten, water ~1 km | 3,330 / 3,423 → 27 / 33 | 113,013 → 22,024 | 112,713 → 43 (41) |
| Malingsbo-Kloten, water ~10 km | 2,695 / 2,856 → 72 / 80 | 113,013 → 113,013 | 111,405 → 1,671 (82) |
| Malingsbo-Kloten, ground → lake | 3,430 / 3,547 → 118 / 121 | 113,013 → 26,740 | 116,748 → 26,301 (149) |
| Abisko, water ~1 km | 748 / 765 → 8 / 13 | 35,215 → 10,055 | 32,960 → 13 (13) |
| Abisko, water ~10 km | 852 / 899 → 25 / 32 | 35,215 → 35,215 | 32,837 → 495 (172) |
| Abisko, ground → lake | 780 / 804 → 57 / 76 | 35,215 → 11,367 | 38,113 → 12,188 (111) |
| Lomsdal-Visten, water ~1 km | 9,521 / 9,878 → 72 / 75 | 163,082 → 53,984 | 162,927 → 71 (46) |
| Lomsdal-Visten, water ~10 km | 7,442 / 7,552 → 127 / 129 | 163,082 → 163,082 | 153,399 → 3,258 (237) |
| Lomsdal-Visten, ground → fjord | 6,827 / 7,024 → 259 / 275 | 163,082 → 163,082 | 169,799 → 47,201 (59) |
| Lomsdal-Visten, ground → lake | 6,087 / 6,225 → 194 / 199 | 163,082 → 41,861 | 163,197 → 40,194 (71) |

All calls before the change completed their prices. Afterward, a call may stop once its
dry subtotal proves it cannot win; the completed counts are shown in parentheses. Prefix
and dry-box work is included in elapsed time. The separate counts-only pass adds abort
counters without supplying timing evidence. All ten searches retain exactly the same primary land metres and secondary price.
The paddle, foot and ferry totals below are derived from search prices and edge kinds,
not the public assembled tally. No measured primary land total rises; the public drive
below demonstrates why these derived totals cannot stand in for the displayed figures.

| Map / leg | From → to, latitude and longitude | Span m | Search-derived paddled / on foot / ferry m, unchanged |
|---|---|---:|---:|
| Malingsbo-Kloten, water ~1 km | (59.96592817, 15.86378171) → (59.97490373, 15.85078388) | 1,235.692 | 1,277.924 / 0.000 / 0.000 |
| Malingsbo-Kloten, water ~10 km | (60.08717062, 15.54789028) → (60.01595928, 15.64937865) | 9,742.524 | 11,052.209 / 0.000 / 0.000 |
| Malingsbo-Kloten, ground → lake | (59.95896511, 15.88470384) → (59.96618193, 15.86462658) | 1,380.003 | 1,402.156 / 518.187 / 0.000 |
| Abisko, water ~1 km | (68.44199172, 18.75049223) → (68.44250068, 18.77440042) | 982.404 | 1,049.814 / 0.000 / 0.000 |
| Abisko, water ~10 km | (68.43412499, 18.69860247) → (68.42343902, 18.94052725) | 10,001.423 | 10,305.597 / 0.000 / 0.000 |
| Abisko, ground → lake | (68.35810416, 18.92828258) → (68.36909491, 18.90938632) | 1,451.869 | 1,519.045 / 224.844 / 0.000 |
| Lomsdal-Visten, water ~1 km | (65.18147834, 13.33330052) → (65.17663041, 13.31544439) | 996.132 | 1,471.512 / 0.000 / 0.000 |
| Lomsdal-Visten, water ~10 km | (65.75249874, 12.36687305) → (65.84082397, 12.40475279) | 10,000.067 | 12,145.604 / 0.000 / 9,376.712 |
| Lomsdal-Visten, ground → fjord | (65.81011681, 12.72285289) → (65.81120047, 12.69050187) | 1,484.696 | 1,027.078 / 347.329 / 1,518.609 |
| Lomsdal-Visten, ground → lake | (65.81006802, 12.96158486) → (65.80765894, 12.94739116) | 702.655 | 2,829.941 / 221.954 / 0.000 |

**The regression reading.** `a_kayak_rounds_land_from_open_water` uses the short pair
on each map through the public planner: both taps must stay off-network, the direct
line must cross land, and the longer answer must paddle with zero **router land**.
The drive exposes `joinedRoute`, `router`, `connectorPrice` and the heap only in its
served copy of the built page, as the measurement harness does. It reads the selected
suffix's land label plus the entry connector, checks the network edges are paddled,
and requires the search and displayed way to have the same total length. Heap pops
must stay within `2 * nodes + 2 * edges + 1`. The tally's on-foot metres may differ from
the router's land by at most `cellM` per connector end; exceeding that allowance fails.
It restores the borrowed mode, goal way, plan and view. The executable routing reading
also requires a water detour dearer than the straight line to win, with fewer connector
prices than nodes and pops below `2 * nodes + 2 * edges + 1`. An eager enumeration of
every entry/exit pair checks the same answer on small wet, dry and mixed graphs; 625
direction/distance probes check that the dry-box floor never overstates sampled land.
Equality at the land ceiling and resuming a dry prefix have their own readings.

Scratch remains under `~/mockups/kayak-mode/phase8/`. `off-cases-*.json` and
`off-lake-case.json` retain full coordinates, source checks and spans; `off-before-*.json`
and `off-before-idle-malingsbo-kloten.json` are the reviewed-code baselines.
`off-tight-*.json` and `off-lake-{before,after}.json` supply the final timings.
`off-counts-*.json` records completed and aborted connector prices. Intermediate
`off-candidate`, `off-bounded`, `off-resumed`, `off-after`, `off-box` and `off-profile*`
captures document the measurements that did not yet settle the ground-case budget.
The reviewers' original harness directory is unchanged.

**Sampling stop, resolved by Uwe.** The first rebuilt Malingsbo-Kloten drive failed the new
short water pair: (59.9659281691193, 15.863781710359643) →
(59.97490373192166, 15.850783875167386). Both taps stay off-network and wet, and a
paddle-only way exists. The search returns zero land and 1,277.924 m derived water;
the public plan returns **1,257.818 m paddled and 20.106 m on foot**. Re-rendering
`812433e` into the same page reproduces exactly those public figures, so the pruning
draft did not introduce this mismatch.

`connectorPrice()` samples midpoints with `ceil(length / grid.cellM)` pieces; here the
grid cell is 25 m. `straightSamples()` uses `floor(length / PLAN.sampleStepM) + 1`
posts including both ends, with a 5 m setting, and `straightParts()` splits runs halfway
between posts. The 636.085 m entry connector has two dry profile posts at its network
end and the 428.162 m exit connector has three at its network start, although every
pricing midpoint is wet. Their displayed dry parts are 7.513 m and 12.593 m. The phase-2
record already notes the same sampling difference for another pair and retained it.

Review retained phase 2's decision: connectors stay priced on the water grid's cells,
not the profile's 5 m samples. "Fewest land metres first" means the router's land,
measured as the router measures it. The finer tally may see dry shoreline slivers
that the pricing midpoints miss. The phase-2 built-note below retains exactly this
difference for the k = 1.2 lake leg (15.032 m on foot in the tally, zero in the price).
Neither the connector pricing samples nor the tally samples change in this amendment.
The pair above has two nonzero connectors, hence four ends and a **100 m** allowance;
its **20.106 m** difference is within that bound. This allowance belongs to the drive,
not the price rule: a zero-land router label remains an exact requirement.

The original stopped drive and `off-public-before.json` retain the diagnosis in
`~/mockups/kayak-mode/phase8/`; `review-draft.patch` preserves the draft at that stop.
The reviewing session's original harness remains untouched.

**Built and driven.** All three pages rebuilt from cached inputs. Their routing headers
and inflated payloads remain byte-identical to the phase-8 baseline, and their rendered
plan scripts match the source after the build's whitespace squeeze. The selected drives
pass twice per page: **152 readings on Malingsbo-Kloten, 127 on Abisko and 127 on
Lomsdal-Visten**, with only the existing Korslång channel scene skip on the latter two.
No recorded figure moved. Each page's eight recorded walking values, including the dry
figure and GPX hashes, are byte-identical to their expected values on both runs.

| Off-network short pair | Router land m | Public paddled / on foot m | Tally allowance m | Search pops / bound |
|---|---:|---:|---:|---:|
| Malingsbo-Kloten | 0 | 1,257.818 / 20.106 | 100 | 169 / 660,271 |
| Abisko | 0 | 1,039.789 / 10.026 | 100 | 71 / 221,357 |
| Lomsdal-Visten | 0 | 1,471.512 / 0 | 100 | 277 / 1,004,437 |

`command make hooks-run` passes with networking enabled: formatting, lint, mypy, library
and pipeline tests, and the remaining hooks. Its first run identified two rendered-source
assertions still spelling the old declarations; correcting those required no runtime
change. The 19 executable routing readings pass within the full suite. Evidence is
`review-pages.json`, `review-final-readings.json`, `review-final-drive-*-{1,2}.log` and
`review-final-hooks-2.log` in the phase scratch directory. No graph source or content
change, standalone graph build, tile build, shared-cache write, push or publication.

**Differential review, 2026-09-23.** The added reference prices every off-network exit
connector eagerly, exhausts reverse Dijkstra, then prices every off-network entry in a
separate scan. It shares the production lexicographic comparison, edge prices, direction
predicate and partial-edge ends. Its label and predecessor arrays are its own. It has
no dry box, `entryLand`, dry prefix, wet-node seed, whole-way ceiling, lazy connector
skip or early termination; the direct way is compared only after the full search.
An off-network end requires exactly one complete price per node. Heap and reconstruction
loops retain explicit graph-derived bounds.

Each built page supplies 200 seeded random pairs: 50 water/water, 50 dry/water,
50 dry/dry and 50 with one end on the network. The network cases include 25 nodes and
25 partial edges, in both journey directions. Every other tap stays off the network
at the page's 150 m snap reach. Ten pairs of each kind occupy each of five logarithmic
length bands between 100 m and the map's east-west grid width. Coordinates outside
the grid, in the wrong wet/dry class or within snap reach are rejected; no routing
answer chooses a pair. Origin pools are seeded too: 2,000 per wet/dry class in Abisko,
256 in the other maps. Malingsbo-Kloten's sparse off-network wet cells did not fill
the larger pool within the 200,000-attempt cap. The seed is **20260923**, with the
unsigned 32-bit recurrence `state = 1664525 * state + 1013904223`.

The harness and every coordinate, page hash, browser version, random-stream end state
and comparison live under `~/mockups/kayak-mode/phase8/differential/`. It serves only
existing local page companions, caps memory, bounds all rejection loops, checkpoints
every comparison and stops on a disagreement. Each comparison allows only
`1e-8 + 1e-12 * max(abs(pruned), abs(reference))` of float noise in **each** label
component. A different way is acceptable only when both components agree. Temporary
page mode, path preference and goal way are restored before the browser closes.

The permanent unit reading uses the same exhaustive reference in `kayak_reference.js`:
32 pairs, a fixed seed and four synthetic grids (wet, dry, a peninsula and broken
water strips), with disconnected nodes, directed arcs, paths, paddles, portages,
ferries and partial-edge endpoints. It compares the production search's two labels
against the full reference, rather than checking the new bounds against themselves.

**Differential built 2026-09-23.** All **600 / 600** real-page pairs agree exactly:
the worst absolute difference is **0 m land and 0 secondary price**, on every map.
The reference completes 12,325,250 entry/exit connector prices on Abisko,
39,554,550 on Malingsbo-Kloten and 57,078,700 on Lomsdal-Visten, plus 200 direct
prices per map. Each off-network end's count equals the entire node count. Abisko
and Malingsbo-Kloten also agree in head, tail and edge sequence for every pair;
Lomsdal-Visten has two different sequences (indices 35 and 95), both exact label ties.

Actual sampled spans are **100.867–31,960.472 m** on Abisko,
**103.288–52,580.083 m** on Malingsbo-Kloten and **101.170–74,686.929 m** on
Lomsdal-Visten; their grid widths are 39,238.225, 53,383.681 and 75,734.761 m.
The final timing pass reproduces every coordinate and the random-stream end state,
checks the unchanged built-page hash, and compares each timed answer with its
reference again. Firefox 153.0 runs one map at a time after all reference jobs and
hooks finish: four untimed warm-ups, one per kind, then one timed search per pair.
Startup, snapping and label extraction are outside the clock. The median averages
the middle two times; p95 is the 190th of 200 sorted times.

| Map | Pairs agreeing | Worst Δ land / price | Median ms | p95 ms | Worst ms | Searches over 300 ms |
|---|---:|---:|---:|---:|---:|---:|
| Abisko | 200 / 200 | 0 / 0 | 38.5 | 717 | 1,340 | 41 |
| Malingsbo-Kloten | 200 / 200 | 0 / 0 | 205 | 4,633 | 6,464 | 92 |
| Lomsdal-Visten | 200 / 200 | 0 / 0 | 203.5 | 9,663 | 17,241 | 92 |

The earlier sub-300 ms result belongs to its ten fixed cases. This wider sample
does not meet that budget throughout. The worst cases are Abisko's 31,960.472 m
dry/dry pair (index 78), Malingsbo-Kloten's 47,500.469 m dry/water pair (157), and
Lomsdal-Visten's 74,686.929 m dry/water pair (137). The requested proof makes no
design change: their labels still match the exhaustive search exactly.

`summary.json` validates all 600 comparisons, each complete connector count and
the separate `*-timing.jsonl` labels; `*-reference*.jsonl` retains the reference
answers. The 20 executable routing tests pass, including the new 32-pair reading.
`command make hooks-run` passes with networking enabled (`unit.log`, `hooks.log`).
Only the test helper, its unit reading and these records change in this review;
the routing code and built-page hashes stay unchanged, so no rebuild or drive is
needed under the review's condition. No cache write, push or publication.

**Performance review built 2026-09-23.** The same 600 saved pairs now also run
through main's `d267de6` planner, with P = 2 and kayak mode on. The old planner
is rendered into the same local pages: graph bytes, grid, settings and coordinates
are held fixed. Each timing run uses one Firefox 153.0 process at a time, four
untimed warm-ups, then one timed search per pair. Loading, snapping, index
preparation and label extraction are outside the clock. Median averages the two
middle observations; p95 uses nearest rank. Every timing triple below is
**median / p95 / worst**, in milliseconds. The middle column is the previously
recorded Phase 8 run, before this performance review.

| Map | Baseline ms | Phase 8 before ms | After ms |
|---|---:|---:|---:|
| Abisko | 5 / 851 / 1,024 | 38.5 / 717 / 1,340 | 18 / 174 / 271 |
| Malingsbo-Kloten | 21.5 / 4,135 / 5,979 | 205 / 4,633 / 6,464 | 75 / 1,103 / 1,466 |
| Lomsdal-Visten | 19 / 8,422 / 15,166 | 203.5 / 9,663 / 17,241 | 103.5 / 2,166 / 4,420 |

The baseline already spends seconds on long random legs. Phase 8 also introduced
a separate regression on short and medium dry-endpoint legs; those are not
explained by the baseline's long-leg cost. The final figures for each pair kind
across all lengths, and each length band across all kinds, meet
`after <= max(baseline, 300 ms)` for all three statistics. Long bands that are
slow in the baseline remain possible; no search-time cutoff changes their answer.

**Abisko.**

| Kind or length band | Pairs | Baseline ms | Phase 8 before ms | After ms |
|---|---:|---:|---:|---:|
| Both off-network on water | 50 | 3.5 / 786 / 1,024 | 6 / 442 / 652 | 7 / 167 / 205 |
| One dry, one off-network on water | 50 | 10 / 878 / 948 | 106 / 603 / 922 | 36.5 / 200 / 271 |
| Both off-network on dry ground | 50 | 26 / 913 / 1,004 | 123 / 988 / 1,340 | 33 / 241 / 254 |
| One on the network | 50 | 4 / 621 / 845 | 25.5 / 740 / 901 | 6 / 161 / 170 |
| < 2 km | 98 | 3 / 18 / 44 | 21.5 / 112 / 137 | 8.5 / 36 / 49 |
| 2–10 km | 55 | 26 / 547 / 638 | 120 / 381 / 463 | 22 / 102 / 125 |
| > 10 km | 47 | 658 / 953 / 1,024 | 473 / 988 / 1,340 | 149 / 254 / 271 |

**Malingsbo-Kloten.**

| Kind or length band | Pairs | Baseline ms | Phase 8 before ms | After ms |
|---|---:|---:|---:|---:|
| Both off-network on water | 50 | 11 / 3,856 / 4,428 | 19 / 2,833 / 3,527 | 22 / 965 / 1,182 |
| One dry, one off-network on water | 50 | 38 / 4,850 / 5,979 | 332 / 5,713 / 6,464 | 109.5 / 1,309 / 1,466 |
| Both off-network on dry ground | 50 | 175.5 / 4,605 / 5,265 | 585.5 / 5,342 / 6,013 | 151 / 1,158 / 1,412 |
| One on the network | 50 | 11 / 3,797 / 4,135 | 84.5 / 2,568 / 5,027 | 13.5 / 462 / 1,289 |
| < 2 km | 97 | 9 / 20 / 42 | 41 / 292 / 429 | 20 / 88 / 108 |
| 2–10 km | 47 | 190 / 1,637 / 2,580 | 617 / 1,413 / 1,887 | 158 / 374 / 477 |
| > 10 km | 56 | 3,184.5 / 5,265 / 5,979 | 2,283.5 / 6,013 / 6,464 | 755.5 / 1,314 / 1,466 |

**Lomsdal-Visten.**

| Kind or length band | Pairs | Baseline ms | Phase 8 before ms | After ms |
|---|---:|---:|---:|---:|
| Both off-network on water | 50 | 14.5 / 8,422 / 12,342 | 35.5 / 4,023 / 13,054 | 34 / 1,898 / 4,420 |
| One dry, one off-network on water | 50 | 18.5 / 9,161 / 15,166 | 721.5 / 9,791 / 17,241 | 191.5 / 2,456 / 3,848 |
| Both off-network on dry ground | 50 | 153 / 9,572 / 12,752 | 1,210 / 11,994 / 14,670 | 279.5 / 2,794 / 3,504 |
| One on the network | 50 | 15.5 / 5,522 / 5,984 | 41 / 7,329 / 10,432 | 27 / 521 / 1,386 |
| < 2 km | 84 | 12.5 / 20 / 39 | 95.5 / 620 / 809 | 36 / 156 / 189 |
| 2–10 km | 52 | 23 / 1,114 / 1,756 | 136 / 1,919 / 2,248 | 66.5 / 487 / 555 |
| > 10 km | 64 | 5,295.5 / 12,342 / 15,166 | 3,778.5 / 13,283 / 17,241 | 896.5 / 3,528 / 4,420 |

**Where the time went.** A separate instrumented pass covers every old
Phase 8 pair over 300 ms: 41 on Abisko, 92 on Malingsbo-Kloten, 92 on
Lomsdal-Visten. These are work counts, not the timing pass. Grid reads include
both exact connector sampling and the dry-prefix sampling used for floors;
exact pops include stale entries. Price calls include calls rejected at the land
ceiling; the raw counters also retain complete-price counts. The separate forward
entry-floor search did not exist before this review.

| Map | Slow pairs | Floors pushed | Connector prices | Grid reads | Exact pops | `enter()` calls |
|---|---:|---:|---:|---:|---:|---:|
| Abisko | 41 | 1,443,815 | 1,789,387 | 670,266,032 | 958,595 | 611,498 |
| Malingsbo-Kloten | 92 | 10,058,157 | 11,869,155 | 5,012,195,189 | 3,563,479 | 2,265,433 |
| Lomsdal-Visten | 92 | 14,004,270 | 15,555,189 | 8,493,215,795 | 4,870,483 | 2,933,175 |

Connector sampling is the dominant term: these calls read billions of grid
cells, against millions of heap operations. The isolated Abisko counters spend
22,895 of 27,190 ms inside exact connector pricing, before the dry-prefix work.
The per-pair counters, including the former worst cases, are retained; aggregate
counts do not hide a slow pair.

**What changes, and why the bounds remain admissible.** Wet endpoints retain
the lazy floor queue. With a dry endpoint and a positive incumbent land label,
exit connectors are priced in a linear pass: almost every weak floor would
otherwise be pushed and popped before those same calls. Every seed put into
`best` is still an exact suffix, and the same non-negative lexicographic Dijkstra
settles it. A connector may stop when an exact suffix at its node dominates it, or when
its land plus the entry floor exceeds the incumbent whole-way ceiling. Such a
connector needs no secondary price.

For a start on the network, a forward land-only search supplies a tighter
per-node entry floor. It obeys the same direction predicate and floors each
edge and partial-edge land length to whole metres. Its retained distances are
safe integers, bounded by the incumbent's floored land; integer addition is
exact and cannot exceed the corresponding floating-point route sum. If the
floor at n is h and its suffix has land s, h + floor(s) bounds the whole route.
For an unrounded connector comparison the code uses h - 1, since
h - 1 + s <= h + floor(s). This bound also permits discarding a reverse state:
for a forward arc u -> v, h(v) <= h(u) + floor(land(u,v)), so no predecessor
relaxation of that state can restore a winning whole-way bound. This auxiliary
search has its own N + 2E pop bound; the main search retains 2N + 2E + 1.

A cached two-pass chessboard-distance field identifies uniform wet or dry
squares. The scanner batches only original midpoint samples contained in such
a square. It recomputes the last midpoint with the original arithmetic;
monotone coordinates then keep every intermediate sample inside. Reciprocal
boundary estimates choose a proposed batch, but that last-point check decides
whether it is valid. Saturating the stored radius only shrinks the square.
The wet count is the same integer as the scalar loop's, so both label components
are unchanged. Dry-prefix samples already read are still reused. A wholly dry
batch can reject a connector only after its sampled land exceeds the ceiling.
Phase 2's grid sampling, the public tally and its known shore-sliver difference
are unchanged.

The initial wet-node candidate caches which nodes are wet and uses approximate
nearness only to choose a candidate. Both connectors are then priced exactly;
it is an incumbent, never an assumed lower bound. The entry minimum scan stops
at zero, its absolute lower bound. No walking price or direction rule changes.

**Cost of the index.** This is additional memory in the page, not a payload or
shared-cache change. The one-time construction is excluded from warm timings:

| Map | Preparation ms | Additional bytes |
|---|---:|---:|
| Abisko | 123 | 4,475,900 |
| Malingsbo-Kloten | 279 | 8,481,660 |
| Lomsdal-Visten | 559 | 20,083,608 |

The measurements are Firefox on this host; physical-phone cold startup and
memory use have not been measured.

**Proof and evidence.** All 600 final timed answers agree with the saved
exhaustive reference: **0 m land and 0 secondary-price difference** on every
map. The unit reference now has its own scalar connector sampler, so it does
not share the production acceleration. Its 32 seeded network cases use packed
water grids; another 6,000 scalar comparisons exercise uniform squares, mixed
ground, grid boundaries, reverse sampling, reused dry prefixes and equal-land
ceilings. All 21 executable routing tests pass.

The harness remains in `~/mockups/kayak-mode/phase8/differential/performance/`:
`run.py`, frozen historical sources, `*-baseline-timing.jsonl`,
`*-current-timing.jsonl`, `*-before-profile.jsonl`, `*-current-profile.jsonl`,
`summary.json`, `profiles.json` and `verified.json`. `summary.json` also keeps
the kind-by-length intersections. The scripts cap memory, restore mode, path
preference and goal way, and stop on any label disagreement. `verified.json`
checks the final source hash and every requested kind and length-band budget.

On the same 225 slow cases after the change, a grid read below means either a
radius-field lookup or a scalar water lookup; one radius lookup can account for
many original midpoint cells. Instrumented wall times are not substituted for
the isolated timing run.

| Map | Floors pushed | Connector prices | Grid/radius reads | Exact pops | `enter()` calls | Entry-floor pops |
|---|---:|---:|---:|---:|---:|---:|
| Abisko | 208,297 | 1,788,156 | 87,922,946 | 861,128 | 543,219 | 179,636 |
| Malingsbo-Kloten | 2,234,068 | 10,868,255 | 668,855,997 | 3,284,562 | 2,090,692 | 612,830 |
| Lomsdal-Visten | 1,837,547 | 15,803,191 | 1,388,325,257 | 4,624,712 | 2,757,056 | 687,457 |

`command make hooks-run` passes with networking enabled (`hooks-final.log`).
The first run found one rendered-source assertion spelling the old floor
condition; updating it in `test_maps.py` required no runtime change. Formatting,
lint, mypy, library and pipeline tests, and the remaining hooks are green.

**Pages and drives.** All three `command make map ARGS="--park <park>"`
builds complete under the cache-write and input-download guard. `pages.json`
checks the exact rendered planner and unchanged graph headers and inflated
payload bytes. Each page passes the kayak checks, price switches, dry words and
foot/water reading twice: **137 readings per run** on Abisko, **162** on
Malingsbo-Kloten and **137** on Lomsdal-Visten. The Korslång channel reading is
applicable only to Malingsbo-Kloten and is the expected skip on the other two.

No previous reading changes on either run (`drive-comparison.json`), including
all recorded kayak figures. Each page's eight recorded walking values are
byte-identical. Off-network router land remains zero; public land remains
10.026 / 20.106 / 0 m, within the unchanged 100 m allowance, and search pops
remain 71 / 169 / 277 (Abisko / Malingsbo-Kloten / Lomsdal-Visten).
The full reports are `drive-<park>-{1,2}.log` and `readings.json` in the
performance scratch directory. No graph content change, standalone graph or
tile build, shared-cache write, push or publication.

### Phase 7 built — One direction follows the whole stream, 2026-09-22

Review corrected the harness and chose the chain gate. The earlier stop and
its rising-edge measurement remain unchanged below. `network/water.py` now
calls `open_level_streams()` immediately after `level_lakes(measure(network))`.
For every Streams edge it subtracts the median of the last `ceil(n / 4)`
samples from the first quarter's median, in the edge's own flow direction.
Those falls and the edge lengths are summed per chain. A chain falling less
than `max(LEVEL_FALL_M, LEVEL_GRADIENT * length_m)` opens on every edge;
`LEVEL_FALL_M = 0.3` m and `LEVEL_GRADIENT = 0.001`. Rising chains open too.
Geometry, node order, height samples and lake levels do not change, and no
stream is reversed. A missing chain or an unread stream profile fails the
build rather than opening a restriction without a measurement.

**What the two graph commands print.** Both warm-cache graph builds passed;
the Malingsbo-Kloten page build repeats these gate figures.

| Map and class | Chains opened | Edges opened | km opened |
|---|---:|---:|---:|
| Malingsbo-Kloten, level | 173 | 282 | 46.877 |
| Malingsbo-Kloten, rising | 13 | 20 | 1.623 |
| Malingsbo-Kloten, total | 186 | 302 | 48.500 |
| Abisko, level | 35 | 44 | 2.182 |
| Abisko, rising | 0 | 0 | 0.000 |

The review's 173 / 282 / 46.9 km and 35 / 44 / 2.2 km are exactly the
level-chain subsets. Including the explicitly requested rising chains adds
13 / 20 / 1.622881 km in Malingsbo-Kloten. The final captures match all 610
and 432 original stream records in geometry, heights and arrow measurements;
only the direction flags differ. Every edge of a given chain has the same
flag. The Korslång channel is one opened chain with two edges, 203.468570 m
in the graph's metric projection.

**The absolute tolerance still applies to short whole chains.** This fixes
opening a locally flat piece of a chain whose fall exceeds the threshold.
It does not promise that every opened whole chain has a gradient below
0.5 %. Fourteen short whole chains in Malingsbo-Kloten (20 edges, 0.223096 km)
and twelve in Abisko (13 edges, 0.154020 km) exceed that percentage while their
summed fall stays below 0.3 m. Their largest falls are 0.291528 and 0.296118 m;
their longest chains are 53.227592 and 40.064113 m. The measured counts match
the specified gate; these are the remaining effect of its absolute noise
allowance, not pieces opened independently of their chain.

`libs/tests/trails/network/test_water.py` adds a synthetic directed network
cut by a crossing path. The short piece of a falling chain stays directed;
level and rising chains open, including a shallow long chain which needs the
gradient arm. Middle and endpoint bumps exercise the quarter medians. The
test retains the original network, non-stream flags, geometry and heights;
separate cases reject missing, single and nonfinite sample series.

**The Korslång pair on the built page.** `drive_map.py` adds
`a_level_channel_is_paddled_both_ways` beside the kayak checks. It uses
(59.9440, 15.2620) → (59.9525, 15.2500) and the reverse pair, in kayak mode.
The existing water-leg reader now optionally measures named chains against
the public track's actual geometry. Both directions follow the entire channel
and use the named dam path, rather than merely receiving an OSM source credit.
Each reading restores and compares mode, path preference, goal way and plan.

| Public page measurement | Upstream | Downstream |
|---|---:|---:|
| Paddled | 1,267.847554 m | 1,267.847554 m |
| On foot | 77.189713 m | 77.189713 m |
| Channel, `streams-514313-6645590-203` | 203.522476 m | 203.522476 m |
| Used part of `osm-514307-6645636-108` | 20.088517 m | 20.088517 m |
| All OSM source credit | 47.074972 m | 47.074972 m |
| Inferred connectors | 27.453604 m | 27.453604 m |

The path's id describes its whole 108 m chain; the chosen journey uses only
20.089 m of it. The drive records what is carried, without extending the route
to use the whole chain. Both tracks retain the existing inferred connectors.
The channel's metric-graph length and browser length differ because the latter
uses the page's distance calculation on quantised geographic coordinates.
Its quarter-median chain fall is 0.163168 m, below the 0.3 m arm.

The scene gains the four Korslång total-length readings. None of its previous
kayak figures moves: shore **2,122.779 m** paddled, bay **1,066.143 m** paddled,
and portage **1,274.726 m** on foot plus **5.912 m** paddled. Both walking-mode
readings and the plan-page price switches still pass. No page JavaScript or
encoding changed.

**Builds and validation.** The two graph commands and the Malingsbo-Kloten
map command completed under the 8 GiB address-space cap, with network requests
and shared-cache writes blocked. No tiles or input data were fetched or built.
The page decodes 217,122 edges, including 610 Streams edges with 302 opened;
its routing payload is 9,884,753 raw bytes and 6,406,640 base64 bytes.
The page's slow step was the existing bounded Ortnamn name-pairing loop.

Two runs of `command make drive` against this worktree's page, restricted to
the new reading, the five existing kayak checks and the plan-page price
switches, each pass **107 readings: zero broken invariants, moved figures,
unrecorded figures or scene skips**. Both runs verify restoration. The
required `command make hooks-run` output is in `built-hooks-final.log` below.
The first run passed 1,994 libs tests and found one malformed-profile case:
a one-sample test array was coerced to a scalar, so validation raised
`TypeError` rather than `ValueError`. The gate now checks the array dimension
before its length, and the fixture retains its series while also testing a
scalar explicitly. Valid sampled networks and the driven page are unaffected.

Scratch remains in `~/mockups/kayak-mode/phase7/`: the two maps'
`*.opened.graph.log` and `*.opened.graph.json`,
`malingsbo-kloten.opened.map.log`, `chain-gate-summary.json`,
`measure-page.py`, `public-measure.json`, `public-page-network.json`,
`drive-1.log`, `drive-2.log`, `built-hooks.log` and `built-hooks-final.log`. The public measurement
served only local resources; its initial invocation lacked Playwright, and
the completed invocation used the drive target's cached `playwright==1.62.0`.
No source harness was edited. Phase 5's rebuild-all and publication remain
outside this phase; nothing was pushed.

### Phase 7 — Stopped at the fall measurement's direction, 2026-09-22

**The supplied measurement reverses some stream profiles a second time.**
`~/mockups/kayak-mode/korslang/falls.py`, lines 16–18, reads flag bit 0 as
meaning that a profile must be reversed to obtain its digitised direction.
That is not the payload's convention. `visualization/encoding.py`,
`encode_graph()` and `_heights()`, keep each edge's geometry and samples in
its own direction. Bit 0 records its orientation against the chain; only
`_nodes()` orders endpoints along the chain for compression, and
`js/routing_graph.js`, lines 79–85, restores `fromNode` and `toNode` on decode.
The existing `test_a_chain_walked_against_its_own_direction_comes_back_flagged`
asserts that a flagged edge keeps its original height order.

Phase 1 already restored each directed stream's digitised geometry in
`routing/graph.py::_split_into_edges()`. `routing/elevation.py::with_elevation()`
samples that geometry, and phase 3's `water.level_lakes()` leaves Streams
profiles alone. Thus the first minus last stream sample already reads fall
in the digitised direction. The harness's extra reversal changes its sign
where digitisation opposes canonical chain order. The plan's published-page
rising counts cannot be treated as evidence of opposing flow.

**Stopped under the wrong-premise rule before building the gate.** The two
requested graph builds were already running when this was found; their
finished profiles are recorded separately below. Review must correct the
measurement convention and the plan's baseline before resuming phase 7.
The model's remaining local rises do not by themselves establish opposite flow.
No threshold was adopted and no `one_way` flag was cleared: all 610
Malingsbo-Kloten Streams edges and all 432 Abisko Streams edges remain directed.

Only this record changes. The review harness is untouched. No page was built,
no browser state changed, no Korslång pair was remeasured, no kayak scene
figure moved and neither of the two acceptance drives was run, because the
gate was stopped. No later phase, tile build or publication was started.

### Phase 7 measurement — Rising edges in their own direction, 2026-09-22

Both `command make graph ARGS="--park malingsbo-kloten"` and the same command
with `--park abisko` completed in this worktree from the warm cache. A scratch
wrapper captured the returned `water.build()` network after height sampling
and lake levelling, without changing it. Each process capped address space
at 8 GiB and blocked network requests and shared-cache writes. The graph
profiles use the cached 4 m mosaic, sampled along edges at the configured
5 m spacing; these figures precede the payload's centimetre quantisation.
Lengths below are the graph's EPSG:3006 metres, not the browser's approximation.

Fall is first height minus last in the edge's own digitised direction.
For the robust reading, each end takes `ceil(sample_count / 4)` samples
and its median. The comparison threshold is the plan's starting
`max(0.3 m, 0.001 * length_m)`, used for this measurement, not adopted as
a gate. Every stream has at least two finite samples. The two samples of
a very short edge cannot distinguish a local bump from a sustained rise.

| Reading | Malingsbo-Kloten: edges / km | Abisko: edges / km |
|---|---:|---:|
| All Streams | 610 / 115.546765 | 432 / 55.806730 |
| Endpoint rise greater than 0.3 m | 44 / 7.373343 | 4 / 0.195040 |
| Quarter-median rise greater than the starting threshold | 30 / 2.299878 | 1 / 0.017060 |
| Would open under the starting quarter-median gate | 389 / 55.920709 | 104 / 2.534603 |

The corrected endpoint-rise counts are **44 and 4**, compared with the plan's
107 and 165. These are direct build measurements, not a new measurement of
the published pages. The source-level error in the supplied harness is the
stop above; the difference must not be explained as a change in water flow.

**Classes of those endpoint rises.** These classes describe sampled shapes,
not an attribution to bridges, trees or actual water flow. Level means the
absolute quarter-median fall is at most the starting threshold. A central
peak exceeds both end-quarter medians by that threshold among samples outside
the two end quarters. Monotone at every sample means no downward step;
the separate quarter-median class allows local reversals but requires all
four consecutive quarter medians to be nondecreasing (equal-sized groups,
with remainder samples assigned to the earlier groups). Other substantial rises
remain unresolved rather than being called model noise.

| Endpoint-rise class | Malingsbo-Kloten: edges / km | Abisko: edges / km |
|---|---:|---:|
| Lake-connected endpoint rise removed on interior samples | 0 / 0.000000 | 0 / 0.000000 |
| Level quarter medians, central peak | 4 / 2.150266 | 0 / 0.000000 |
| Level quarter medians, no central peak | 10 / 2.601264 | 3 / 0.177981 |
| Quarter medians fall despite endpoint rise | 6 / 1.129221 | 0 / 0.000000 |
| Monotone rise at every sample | 6 / 0.086080 | 0 / 0.000000 |
| Monotone quarter medians, local reversals | 2 / 0.129437 | 0 / 0.000000 |
| Nonmonotone rise remains | 16 / 1.277074 | 1 / 0.017060 |

A lake-connected endpoint shares a graph node with a levelled lake edge.
Two Malingsbo-Kloten endpoint rises meet one: **20.432398 m** and
**229.045316 m**. Removing that endpoint and recomputing the quarter medians
changes their falls from **−0.411445 to −0.502871 m** and from
**+0.169543 to +0.149744 m**, respectively. Neither changes class. No Abisko
endpoint rise meets a levelled lake. Six additional Malingsbo-Kloten edges
(**0.807287 km**) have a robust rise but not an endpoint rise over 0.3 m;
they explain why the robust total exceeds the 24 still-rising edges in the
endpoint table. One of those six meets a lake; dropping that end leaves its
robust fall at **−0.382906 m**.

**Flow arrows within 50 m.** The cached `hydropunkt` layer contains
**2,121** arrows in Malingsbo-Kloten and **710** in Abisko. Each edge was
compared with every arrow within 50 m, using the tangent from 5 m before
to 5 m after its projected position, clipped to the line ends. The convention
is phase 1's `bearing = 90 - rotation`; agreement is an angular difference
strictly under 90 degrees. An arrow may be counted for several noded edges.

| Edges with nearby arrows | Agree only | Oppose only | Mixed | No arrow |
|---|---:|---:|---:|---:|
| Malingsbo-Kloten, all Streams | 74 | 1 | 0 | 535 |
| Abisko, all Streams | 40 | 0 | 0 | 392 |
| Malingsbo-Kloten: lake-connected endpoint rise removed on interior samples | 0 | 0 | 0 | 0 |
| Malingsbo-Kloten: level quarter medians, central peak | 3 | 0 | 0 | 1 |
| Malingsbo-Kloten: level quarter medians, no central peak | 1 | 0 | 0 | 9 |
| Malingsbo-Kloten: quarter medians fall despite endpoint rise | 0 | 0 | 0 | 6 |
| Malingsbo-Kloten: monotone rise at every sample | 0 | 0 | 0 | 6 |
| Malingsbo-Kloten: monotone quarter medians, local reversals | 0 | 0 | 0 | 2 |
| Malingsbo-Kloten: nonmonotone rise remains | 0 | 0 | 0 | 16 |

All four Abisko endpoint rises have no nearby arrow. The Malingsbo-Kloten
rising classes with arrows are the four with level quarter medians: three
central peaks and one without. All their arrows support digitisation.
Among all 30 robust Malingsbo-Kloten rises, one has a nearby arrow and it
also supports digitisation. No measured rising edge has an opposing arrow.

The six strictly monotone Malingsbo-Kloten rises total only **86.079960 m**;
four have two or three height samples. The other two span **33.364658 m**
and **22.191013 m**. No nearby arrow establishes their opposite flow.
Abisko's one remaining robust rise is **17.059902 m**, with four heights
**868.315420, 868.603671, 868.821886, 868.687066 m**: it rises and then falls.
The stopped measurement does not settle a new water-noise tolerance or
justify reversing any of these edges. The starting gate would open 389
and 104 edges, respectively; **the actual number opened is zero on both maps**.

Scratch and evidence: `~/mockups/kayak-mode/phase7/sitecustomize.py`,
`classify.py`, each map's `.graph.log`, `.graph.json` and
`.graph.classified.json`. Captures retain every stream's id, metric geometry,
full profile, lake-end membership and nearby arrow ids, distances and angles.
The source harness and the shared cache were not edited.

Validation is recorded in `~/mockups/kayak-mode/phase7/hooks-final.log`.
The first hooks invocation passed formatting, lint, mypy and both test suites
(**1,991 libs tests and 97 pipeline tests**), but pre-commit reported that
files changed during the test hook: this record was being clarified while
it ran. The required hooks were rerun after the record was finished.

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

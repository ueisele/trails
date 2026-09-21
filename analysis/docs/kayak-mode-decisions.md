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
- **The open-water chords' bytes.** Phase 1's page is 8,114,150 bytes brotli against
  6,227,283 before (+1.89 MB, +30 %), the graph stream 5.8 MB gzip against 3.9; the chords
  are 33,082 edges and 5,078 km against 2,382 km of shore. The plan's remedy is a coarser
  ring for the chords alone (25 m: 22,584 vertices against 39,226). Measured before phase 5
  publishes, on the sweep's three legs: the same answers at 25 m, or not.
- **Norway's heights over the sea.** The Høydedata point reader rejects a depth as a missing
  height, so a Lomsdal-Visten water edge over the fjord may come back without one; phase 5's
  build measures it, and the sea's answer is 0 m (the page's `seaTerrain` says as much for a
  straight leg).

## 5. Changes

- 2026-09-21 — phase 3 stopped: the water grid and the height tiles do not guarantee a lake plane. One straight water part near the measured bay changes height by 0.96516 m in about 25 m; the stop-note below. No runtime change retained.
- 2026-09-21 — phase 0: the plan and this record opened.
- 2026-09-21 — phase R: the research in §3.5; there is no phase 6.
- 2026-09-21 — phase 2 (`bea479c`): the Kayak switch beside *Stay on paths*, the prices per mode, direction as a predicate on the step, the mode's cheapest metre as the floor, snapping by node eligibility, a paddled edge tallied like a ferry for marking but inside the reserve; the sweep settled **k = 1.5, P = 2**. Three stops on the way (the search's direction, where the settings come from, the tally); the built-note below.
- 2026-09-21 — phase 1 (`ac467b2`): the water network in the build — Shore, Open water, Streams of kind `PADDLE`, portage chords and their ties as `BRIDGE`, `NetworkSource.directed` carried to a per-edge `one_way`; the built-note below. Two stops on the way, both the plan's (the flow test, the layer of the direction).

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

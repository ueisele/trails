# Phase 11 measurements

**Stopped again at the speed gate, 2026-09-25. Phase 11 is not built.** The
first prototype improves the Kloten entries but raises Abisko kayak p95
by 3.245×. Review's lazy follow-up raises it by 4.940×; its evidence is
[below](#lazy-prototype-follow-up). Production source and tests are
unchanged. These measurements describe browser prototypes, not the
shipped planner. The first stop remains history in the following sections.

## Kloten

Inputs are the phase-10 investigation's frozen `phase10-matrix.jsonl`,
under `~/mockups/kayak-mode/kloten-start/`: z17, E/W offsets of 8, 12 and
20 m, both Stay on paths settings, to Q and the P2 proxy. These are the
24 distinct off-network rows. The z16 E20/W20 duplicates are not counted
again. Coordinates and attachment are unchanged.

All 24 proposed routes use northern launch edge 284183, whose road end is
node 141123. Their full-edge sequences equal the virtual table's sequences.
Connector prices and partial-edge lengths are read from the proposed
search; the unchanged suffix lengths come from the phase-10 table.

| Reading | Proposed | Virtual table |
|---|---:|---:|
| E8/off to Q, carry m | 231.360460815 | 231.360460815 |
| E8/off to Q, land price | 313.813413437 | 313.813413437 |
| E8/off to Q, secondary price | 649.735443651 | 649.735443651 |
| Largest carry difference, all 24 rows m | 0.000028900 | — |
| Largest land-price difference | 1.7695×10⁻⁹ | — |
| Largest secondary-price difference | 3.5434×10⁻⁹ | — |

The tiny differences come from the specified clamped analytic points;
the older virtual experiment also refined them with the page's distance
function. The proposed E8/off route retains the table's 28.514289 m paddle
to Q. The old nodes-only route carries 308.226 m and has land price
427.899423. No price factor or snap reach changes.

Before the prototype, an additional browser audit considered segment
entries on every eligible edge for E8 and W20 to Q in both settings. It
found no cheaper way than the virtual table, apart from floating-point
rounding. Its pruning uses only nonnegative partial-edge and exhaustive
suffix prices, independently of production's entry bounds. This limited
audit is not the required three-map reference comparison.

The 24 attached rows, W8's z16/z17 display tolerance, raw-tap drives,
panel and Garmin/GPX output were not remeasured before the speed stop.
No pinned regression or scene update is committed.

## Speed gate

Firefox 153.0 through Playwright 1.62.0, one browser workload at a time,
with an 8 GiB address-space cap on the harness and its descendants.
The graph is the unchanged phase-10 graph in the existing Abisko page.
Only the proposed search and connector functions are injected in memory.
The first four frozen pairs warm both versions; then each of the 200
pairs runs baseline followed by proposed search. Timing covers the search,
including candidate construction, and excludes reference work and display.
The p95 linearly interpolates zero-based indices 189 and 190 of the sorted timings.

| Map / setting / sample | Pairs | Median ms before → after | p95 ms before → after | Worst ms before → after |
|---|---:|---:|---:|---:|
| Abisko / kayak / phase 10 | 200 | 34.5 → 237.5 | 334.05 → 1,084.15 | 510 → 1,707 |

The p95 ratio is **3.245472**, exceeding the 2× gate. The baseline agrees
in scale with phase 10's recorded 347.30 ms. No browser errors were
reported. No proposed label is worse than the corresponding old label
within 10⁻⁸; this does **not** establish equality to the new reference.

| Slowest proposed pair index | Baseline ms | Proposed ms |
|---|---:|---:|
| 78 | 497 | 1,707 |
| 18 | 510 | 1,599 |
| 58 | 440 | 1,440 |
| 118 | 290 | 1,362 |
| 17 | 441 | 1,233 |

The stop occurs at the first completed map/setting. The other 11
map/setting timings on the original sample and all 12 on the second sample
are **unmeasured**. The phase-10 pairs remain intact; no second sample was
generated. Its dry, off-network construction and all 2,400 independent
comparisons remain required when phase 11 resumes. No performance claim
for those missing cells is inferred from this one.

## Lomsdal-Visten walking profile

The three slowest ordinary-walking pairs in phase 10's saved results are
56, 137 and 52. The baseline page was profiled, without changing prices or
answers. The lighter profile times `connectorPrice` calls, `endsOf` and
route reconstruction; the times include that instrumentation and are not
a fresh p95 sample.

| Pair index | Phase-10 ms | Profiled whole search ms | Connector calls | Time inside connector pricing ms | Share |
|---|---:|---:|---:|---:|---:|
| 56 | 14,742 | 16,057 | 221,128 | 15,249 | 94.97% |
| 137 | 13,699 | 15,428 | 190,593 | 14,521 | 94.12% |
| 52 | 12,662 | 14,091 | 229,430 | 13,267 | 94.15% |

A first, more intrusive profile of pair 56 counted **426,498,464** calls
to `connectorWaterAt`. Timing every midpoint inflated the search to
251,847 ms; that latency is discarded. The subsequent intrusive run was
stopped, its isolated browser closed, and the three pairs rerun with the
lighter instrumentation above. No saved user plan or goal was involved.

The measured cost belongs to this phase's connector layer:
`connectorPrice` samples walking connectors individually, while kayak
uses `connectorScan` to count unchanged midpoints in uniform grid squares.
The prototype lets walking use those same batches without the kayak dam
predicate. Its walking answers and p95 have not been validated, and this
change is restored with the rest of the rejected prototype. It is not
reported as a completed performance fix.

## Display, export and stored plans

The prototype carries the connector and partial edge separately into
`partlyRouted`, using the existing straight-part and `cutPart` machinery.
That is the shared geometry consumed by the panel and export, but public
display and file checks remain unrun. No display/export behaviour is
claimed as validated.

Stored plans are GPX. `restoreKept` calls `loadGpx(text, 'asis')`;
`pointsForLoaded` retains each leg's recorded parts and endpoint pair;
`resolve` restores that description before trying a new whole-leg search.
`restoredWalked` reroutes a **routed part between its own ends**, checking
its stored length, then tries matching and finally keeps recorded geometry.
It does not re-optimise the entire leg's connectors. Thus, if phase 11 is
built under the unchanged restoration policy, an old saved western leg
normally still shows its western geometry on reload. Editing its endpoint
pair invalidates that restoration and lets the new entry rule apply.
The generic comment above `keepLater` about rerouting refers to routed
stretches, not wholesale replanning. No restoration code is changed.

## Build and validation status

No graph, map or tile build, source download, shared-cache write, push or
publication. No selected drive or `drive-all` run. The stop is the explicit
speed gate, not a new routing-policy question. Before resuming, review
needs a faster candidate/exit search under the same decided candidate set
and objective; the retained prototype is incomplete and not release-ready.

`command make hooks-run` is green with network access: ruff format/check,
mypy, both pytest suites and the standard hooks. The shared-cache guard
remained active. This validates the restored production tree and records;
the prototype's tests were not run. Log: `hooks.log` in the scratch directory.

## Evidence

Scratch: `~/mockups/kayak-mode/phase11/`.

- `local.py`, `local.jsonl`, `local-summary.json`: all 24 local search labels,
  entry points and northern edge sequences.
- `entry-audit.py`, `entry-audit.js`, `entry-audit.jsonl`: the four preliminary
  all-edge candidate audits against phase 10's exhaustive suffix tree.
- `benchmark.py`, `benchmark-abisko-kayak.jsonl`,
  `benchmark-abisko-kayak-summary.json`, `speed-summary.json`: every timing
  and label, the frozen points, page/source hashes and percentile calculation.
- `profile-light.py`, `walking-profile-light.jsonl`: the three Norway profiles;
  `profile.py`, `walking-profile.jsonl` retain the intrusive first count.
- `prototype.patch`, `plan_mode.js`, `kayak_reference.js`: the rejected
  implementation and unvalidated reference extension. The local and timing
  harnesses read the frozen script, so they do not need a repository edit.

The Abisko page SHA-256 is
`ae6a144eaf7ba9abf8c9d3ff055f6b389895711ded96a092141ed9c96aadcfda`.
The proposed script SHA-256 is
`d2091066bedf7fb929d39e69f643436bd6d5677f2be6d144f0f0c242e3f1554e`.

## Lazy prototype follow-up

Review, 2026-09-25, keeps the candidate set, objective and speed gate, but
requests lazy discovery. Entries belong to incident edges at settled
nodes; exits belong to a floor-ordered spatial queue. Whole-edge and
candidate floors precede segment expansion and exact connector pricing.
Sparse query caches replace arrays sized by the graph, and a whole-network
dry-box bound replaces the first prototype's constant zero entry bound.
Walking batching remains conditional on equal per-connector midpoint wet
counts, floating-point-only price differences and unchanged routes.

The second prototype caches an edge bounding-box hierarchy and cumulative
geometry lengths in the router. Each query traverses that hierarchy through
the existing floors queue, expanding segments only at eligible leaves.
Incident entries are generated when their permitted end node settles.
There is no unconditional per-query loop over every edge or segment.

A route between two interior points may beat the direct connector without
reaching either real endpoint. At an expanded exit edge the prototype
therefore also offers matching source candidates, subject to a whole-edge
floor for both connectors. The same-edge sweep is restricted to that edge;
its candidates and exact connector prices share the query caches. This
handles interior routes that real-node settlement alone would miss. It
also expands source candidates before a real node settles, and is expensive
in this prototype when the floors leave distant edges eligible. This
particular scheduling choice is not established as necessary or efficient.

For the common entry floor, let `D` be a lower bound on distance to the
nearest eligible segment and `B` a lower bound on distance to the dry box's
boundary. The hierarchy finds `D` using conservative coordinate scales.
A connector contained in the box costs at least `D × offPath()` in land;
a connector leaving it has dry midpoint samples covering at least
`max(0, B − cellM)` metres. Thus
`min(D, max(0, B − cellM)) × offPath()` bounds both cases. A whole sample's
allowance makes this conservative with the unchanged 25 m midpoint grid.
This is a derived bound, not a constant zero; it can still evaluate to zero
when the known dry box is short.

### First cell: failed

The same frozen 200 Abisko kayak phase-10 pairs, same alternating
baseline/prototype method, Firefox version, page and 8 GiB cap as above.
The first four pairs warm both variants, including the cached hierarchy;
query timings include lazy discovery and pricing. No other heavy process
runs alongside the browser. The harness restores mode, path switch and
goal way and verifies the restoration.

| Map / setting / sample | Pairs | Median ms before → after | p95 ms before → after | Worst ms before → after |
|---|---:|---:|---:|---:|
| Abisko / kayak / phase 10 | 200 | 33 → 294.5 | 338.30 → 1,671.20 | 526 → 2,461 |

The ratio is **4.939994**, above the unchanged 2× gate. No browser errors.
No proposed label is worse than its old label within 10⁻⁸, which does not
prove equality to the new reference. These are search measurements only:
drawing and export have not been adapted or validated for this prototype.
The original phase-10 pair files are unchanged.

### Where the lazy search spends its time

After the failed cell, the five slowest pairs were profiled in a separate
browser run, with the hierarchy warmed. Function timers add overhead;
these totals are diagnostic, not substitute gate timings. Times inside
nested functions overlap and must not be summed.

| Pair | Gate baseline → lazy ms | Profile total ms | Connector calls | Connector ms | Exit expansion ms | Same-edge ms | Candidate generation/cache access ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| 78 | 526 → 2,461 | 3,123 | 300,513 | 1,812 | 2,113 | 1,354 | 521 |
| 18 | 500 → 2,212 | 3,178 | 343,190 | 1,792 | 1,800 | 1,233 | 493 |
| 58 | 457 → 1,987 | 2,779 | 236,628 | 1,448 | 1,749 | 1,201 | 484 |
| 194 | 338 → 1,935 | 2,770 | 366,125 | 1,424 | 1,839 | 1,172 | 481 |
| 134 | 306 → 1,912 | 2,594 | 299,929 | 1,345 | 1,786 | 1,225 | 470 |

All five expand **105,690 edges on each side**, all eligible edges in the
hierarchy. Pair 78 visits **211,379 hierarchy entries**, expands
**151,385 segments on each side**, and generates **43,144 entry candidates**
and **43,050 exit candidates**. Its **39,987 exact queue pops** lead to
**29,053 calls** to each entry function. Testing node entries takes **92 ms**;
testing incident-edge entries takes **216 ms**. Exit expansion and the
same-edge checks dominate the added work, with connector pricing accounting
for **58.02%** of the instrumented whole search.

A separate bound reading on pair 78 explains why the queue reaches every
leaf. The source's known dry-box boundary is only **4.864004 m** away, so
the derived common entry floor is **0** with the 25 m sampling allowance.
The target boundary is **185.854663 m** away, capping every exit-box land
floor at **482.563990**. The initial incumbent has **95,056.790774** land
price; even the eventual winning **27,740.071069** remains far above that
cap. Deferring these eligible leaves merely postpones a full expansion;
the box floors do not exclude them. No inference that the candidate set
itself cannot meet the gate follows from this implementation.

### Second stop and remaining work

The speed gate requires stopping here. Production source and tests were
never replaced by this prototype. No maps, graphs or tiles were built,
and no shared cache contents were changed. The first prototype's local
Kloten figures above have not been re-established for the lazy variant.

The remaining eleven original-sample cells, the entire second off-network
sample, 2,400 reference comparisons, Kloten attached/off-network regressions,
walking midpoint-count/price/route audit, display and export checks, builds
and drives remain unrun. The walking batching code is retained only in
scratch; no claim of equal wet counts, a maximum price difference, or a
walking speed improvement is made. Stored-plan behaviour remains unchanged,
as described above. No scene figures move and no built note is warranted.
Review must address the cost of eligible exit and same-edge expansions;
the candidate set, objective and speed gate remain the accepted decisions.

Evidence under `~/mockups/kayak-mode/phase11/lazy/`:

- `helpers.js`, `integrate.py`, `plan_mode.js`: the frozen lazy prototype
  and its construction from the recorded production source.
- `benchmark.py`, `benchmark-abisko.log`, `benchmark-abisko-kayak.jsonl`,
  `benchmark-abisko-kayak-summary.json`, `speed-summary.json`: all 200
  before/after timings and labels, hashes and gate calculation.
- `profile.py`, `profile-abisko.log`, `profile-abisko-kayak.jsonl`: the
  five instrumented slowest pairs and their candidate/queue counts.
- `bounds.py`, `bounds-abisko.log`, `bounds-abisko-kayak.jsonl`: the
  separate pair-78 dry-box and incumbent reading.

The lazy script SHA-256 is
`1533dd512987f00ae19245e24cf0cc2c19e793b19ecac5e9639fca00d090f645`.
The original Abisko page hash remains the one recorded above.

**Validation of the second stop.** `command make hooks-run` is green with
network access and the shared-cache guard: ruff format/check, mypy, both
test suites and the standard hooks. Log: `lazy/hooks-rerun.log`. The first
invocation passed 2,040 library and 97 pipeline tests, but pre-commit marked
the hook unsuccessful because the records were edited during that run.
The fixed-file rerun passes. These checks validate the unchanged production
tree and the records; they do not validate the scratch prototype.

## Radius measurement before Uwe's decision

**Measurement only, 2026-09-25; no radius decision or production change.**
Review proposes limiting new interior candidates to segments within a
local radius, keeping today's node candidates everywhere. Uwe asks why
250 m should be the radius. **His decision is to measure first, then decide.**
The previous whole-map prototype stops remain history above. This study
changes neither production code nor the accepted prices, snapping, grid,
attached endpoints or stored-plan behaviour. No build or drive is run.

### Candidate sets and searches

`kayak` and `walking` mean Stay on paths off; `kayak-paths` and `paths`
mean it is on in kayak and walking respectively.

The measured sets are fixed radii **0, 50, 100, 250, 500 and 1000 m**;
relative radii **d + 50, d + 100 and d + 250 m**, where `d` is the true
nearest eligible network distance for that endpoint and mode; and
**unlimited**. The radius applies independently at each off-network end.
An attached target retains `endsOf` and gets no new exit connector.

A segment qualifies when its **nearest point**, not its selected entry
point or its real end nodes, lies within the radius. The qualifying segment
then offers the unchanged clamped dry-ground `cos θ = f/g` candidate in
every allowed direction; each point permits both legal travel directions.
The exact 25 m midpoint connector price, including kayak dam discs, chooses
among them and all existing node candidates. Entries and mirrored exits,
same-edge interior pieces, and the direct whole-leg fallback are included.
R=0 offers nodes only. These are candidate optima under the defined discrete
set, not a continuously optimised entry over the water grid.

The scratch local search queries the existing `edgeIndex` cell lists,
deduplicates segment references and checks the segment's nearest distance.
Its query rectangle uses conservative metre scales over the map; it cannot
exclude an in-radius segment because of the grid's approximate cosine.
Nearest distance minimises the page's `metresBetween` along the segment
with a bounded 48-step ternary bracket and explicit endpoint checks.
Relative radii find the nearest eligible point through bounded doubling
of index search rectangles, then query the resulting radius. A segment's
cumulative along-edge distance is cached once per router. There is no
per-query pass over all edges in a timed local variant; the existing
node-seed pass remains. This measurement uses the first prototype's
conservative zero common kayak entry-land floor, with indexed local
candidate lists. It does not claim to finish the lazy production design.
The local R=0 control exposes the cost of that search bookkeeping too.

Unlimited considers every eligible segment and node, then runs a separate
reverse Dijkstra over the complete network, a separate entry scan and
brute-force same-edge pairs. Exact duplicate points from the two directions
of one segment are retained once. The reference shares the unchanged grid
price, but neither production's candidate lists nor its ordered same-edge
sweep. Its initial runs price everything without a ceiling. Later runs
reject a connector if it alone already exceeds a **fully priced feasible
nodes-only whole route**: every remaining piece has nonnegative price, so
such a connector cannot belong to a strict improvement. One extra price
unit weakens the ceiling to protect against rounding; it changes no price.
Walking also uses distance × ground rate as a connector cost floor. Kayak
counts actual dry midpoint samples before rejecting at the land ceiling.
These bounds depend on feasibility, not production's pruning bounds, and
do not restrict candidate distance. Saved unbounded answers are checked
against this optimisation before it is used for the remaining cases.
Queue bounds count possible seeds and directed arcs; they cannot discard
an optimum. **The unlimited reference is not included in the search-time
tables.** Its wall-clock duration is recorded only to explain sampling cost.

Walking connectors in the scratch variants and reference use the existing
uniform-cell `connectorScan` batches without the kayak dam predicate.
Today's baseline retains its original sample-by-sample walking loop.
R=0 in the local columns is therefore a control for this batching and
search bookkeeping, while the baseline columns measure today's code.
They have the same candidate set and prices. Any walking timing improvement
must not be attributed solely to the radius. The audits below compare
integer wet counts and exact prices on sampled connectors; this round
does not claim a completed production walking change.

### Sampling and interpretation

There are **five starts per requested offset bin per map**, reduced evenly
from the suggested 25. The bins are **8, 20, 50, 100, 250, 500, 1000 and
2000 m**. The Norway pilot's unlimited reference takes **31.38 / 31.01 s**
in the two kayak settings and **26.60 s** in ordinary walking. At 25 points
per bin, Norway's two kayak settings alone imply roughly 3.5 hours of
reference work, before the other settings, maps or local searches. Every
bin and setting is retained in the reduced sample. The reduced sample
stayed frozen after the feasible-route ceiling accelerated the reference.

The seed is **20260923**. Map numbers are Abisko=0, Malingsbo-Kloten=1 and
Lomsdal-Visten=2; bin indices are 0–7 in the order above. Each bin has its
own 32-bit seed `20260923 + 1000003 × map + 1009 × binIndex`. The generator
updates `state = (1664525 × state + 1013904223) mod 2³²` and divides by
2³². It selects a walking-eligible drawn land edge uniformly, then a
uniform distance along that edge, and either perpendicular side with
probability one half. Ferries, inferred connectors and kayak-only edges
are excluded as *generators*; every mode-eligible edge remains eligible
for nearest-distance and candidate queries.

The perpendicular move uses local metre scales. Its measured displacement
is retained alongside the requested bin and true nearest distance. The
largest displacement-versus-bin differences are **0.297444 m** in Abisko,
**0.189723 m** in Malingsbo-Kloten and **0.259998 m** in Lomsdal-Visten. Points
must fall inside the existing water grid, be dry by walking's water mask,
and be more than 0.01 m from the nearest eligible walking segment. Rejected
attempts consume the same deterministic stream. The accepted point is
passed as off-network (`node: -1`, no edge attachment), without invoking
finger snapping. Kayak uses exactly these same dry starts. A nearby second
edge can make the actual network distance much smaller than the requested
move; the distance table below shows this explicitly.

Only **one of the 120 generated starts** is actually more than 1000 m
from the eligible walking network. The largest true distances are
**1781.36 m** in Abisko, **417.45 m** in Malingsbo-Kloten and **766.61 m**
in Lomsdal-Visten. In Norway's requested 2000 m bin they range from
**7.82 to 623.26 m**. The sample therefore says little about starts whose
nearest network point really is 2 km away.

For accepted ordinal `j` within bin `b`, target index is
`(37 × j + 23 × b + 61 × map) mod 200`. The target descriptor is copied
unchanged from that map and setting's frozen phase-10 pair JSONL. Only the
start is moved. Thus there are **120 generated starts and 480 case-settings**.
The sample is uniform over edges and distance along the chosen edge,
not over network length or geography. Five starts per bin give exploratory
comparisons, not population error rates or a statistically established
best radius. Repeating starts across settings does not create independent
geographical observations.

The original **24 Kloten off-network kayak rows** are added separately:
z17, E/W 8, 12 and 20 m, both path-switch settings, Q and the P2 proxy.
The same 12 geometrical pairs are also read in both walking settings,
giving **48 supplementary case-settings**, **528 in total**. Their endpoint
descriptors are left unchanged; the two walking settings interpret edge
eligibility as usual. Kloten is a separate bin in the detailed tables.

### Measurements and aggregation

One Firefox workload at a time, using the existing phase-10 pages and
cached graph/grid data, under an inherited **8 GiB address-space cap**.
No map, graph or tile is rebuilt. The first two cases warm the baseline
and local search in each setting, including reusable indexes and the
connector radius field. Then each case runs today's baseline and each
local variant once; local-variant order rotates by the ordinal within
its bin to distribute later-run and garbage-collection effects. Search
timing includes local candidate discovery, nearest-distance queries for
relative radii, pricing and routing, but excludes route accounting,
reference work, page loading and initial index construction. No display
or export timing is inferred. These are park-graph measurements, not an
atlas benchmark; the existing nodes-only scans remain global. The straight
start-to-target distance p50 / p95 / max is **15.94 / 33.22 / 35.83 km** in
Abisko, **27.06 / 45.46 / 50.26 km** in Malingsbo-Kloten and
**35.15 / 59.98 / 71.30 km** in Lomsdal-Visten, on the 40 generated pairs
per map. These timings belong to this sample, not the original phase-10
speed-gate sample. Completed browser sessions restore and verify the original mode, path
switch and goal way before closing. The initial Malingsbo-Kloten run was
interrupted to change only the reference evaluator; its temporary,
nonpersistent browser context was discarded. Completed rows were retained,
and a fresh context resumes the remaining cases.

Percentiles linearly interpolate sorted observations at `(n−1) × p`.
Comparisons use the full stored precision; summary tables round to two
decimal places.
“Changed” means **more than 0.01 in either land or secondary price** against
unlimited. Primary excess is `max(0, local − unlimited)`: kayak land price,
walking cost. Relative excess divides by the unlimited primary price;
excess above the 0.01 comparison precision over a zero reference is
infinite, while a zero-reference excess within that precision is zero.
Extra foot metres are the **signed** difference from unlimited: dry connector
metres plus non-paddle/non-ferry edge and partial-edge lengths in kayak;
connector lengths plus walking edge lengths, excluding ferries, in walking.
A negative difference means the local route walks or carries less even
though its objective can be worse. No sub-metre drawn-part filtering is
applied to this routing measurement.

All pooled summaries weight each case-setting equally, including the
supplementary Kloten rows. Absolute primary units depend on the setting;
the per-setting tables retain that distinction. Bin tables show the same
quality, foot-distance and timing statistics as the pooled cells.

### What the measurements show

All **528 case-settings** are measured: 40 generated pairs per map in each
of four settings, plus 48 Kloten readings. Every requested bin and setting
is present. The detailed tables below retain the five observations in each
map/setting/bin cell; they should not be read as stable population percentiles.

Every nonzero radius matches unlimited on the **24 original Kloten kayak
rows**. For E8/off to Q, unlimited carries **231.360461 m**, with land price
**313.813413** and secondary price **649.735444**. Across the 24 rows, the
largest differences from the previous virtual table are **0.000029 m carry**,
**1.77 × 10⁻⁹ land price** and **3.55 × 10⁻⁹ secondary price**. The selected
entry is on the rental road edge whose real nodes are **222.360985 m** apart.
These are search readings, not a new display or raw-tap drive. Kloten shows
that local entries solve that example; it cannot distinguish 50 m from the
larger tested radii.

The supplementary Kloten walking readings do distinguish the smallest
radius: fixed **50 m** differs in **6 / 12** cases in each walking setting,
with maximum relative cost excess **0.57%** in walking and **0.98%** in paths.
Fixed **100 m** and every relative variant match unlimited there. One
omitted exit segment is **73.856556 m** from the frozen target, on a
Topografi 50 road edge whose real nodes are **254.703204 m** apart. Walking
cannot use the target's kayak attachment, so the mirrored exit matters too.

Across the entire sample, **d + 250 m** differs from unlimited in
**159 / 528 cases (30.11%)**. Its primary relative
excess is **0.00% median**, **1.04% p95**
and **11.57% maximum**. Fixed **1000 m** differs in
**142 / 528 cases (26.89%)**, with
**1.24% p95** and **18.26% maximum**
relative excess. A higher exact-match share and a lower worst loss can
therefore favour different variants. The 0.01 price threshold counts even
small differences on long routes; the excess columns state their size.

A relative radius always offers the closest eligible segment even when
that segment lies beyond the fixed radii. It does not guarantee the best
edge: the useful entry or exit can be farther away than the nearest one.
The five-worst tables identify both endpoints when needed, including the
missed edge's source and real-node spacing. Their rows are case-settings;
the same geographical pair can appear under two settings.

The largest extra foot distance is a separate concern from the largest
relative price loss. In **Abisko / paths / 500 m bin / case 26**,
d + 250 m walks **52,748.509 m**, compared with **35,377.817 m** for
unlimited: **17,370.692 m extra**, for only **1.688518%** extra weighted
cost. Today's baseline walks **35,569.724 m** and costs **98,586.376**;
the local variant costs **97,638.780**, so the longer walk is a strict
improvement under the unchanged cost objective. Unlimited costs
**96,017.507**. Its omitted entry is **1880.129 m** from the start, on a
Leder path with **2028.857 m** between real nodes; the relative entry
radius is **746.160 m**. Fixed 1000 m adds **17,355.569 m** on this same
pair. These are material distance differences despite modest price losses.
Foot distance need not decrease as candidates are added, because the
unchanged objective minimises weighted cost.

Timing compares complete local searches with today's baseline on identical
cases. The local R=0 control has the same prices and carry as today, with
maximum recorded differences **0** in all three fields. Its walking speed
change already includes midpoint batching, and its kayak search uses the
conservative common entry floor described above. Radius timing is a
measurement of this scratch implementation, not a production speed-gate
claim. There is no claim about country-scale graph performance.

Today's slowest baseline cell is **lomsdal-visten / walking**,
with p95 **13,155.55 ms**. Its local R=0 p95 is
**4,436.95 ms**; across all local variants in that same cell,
p95 ranges from **4,401.65 to
4,647.15 ms**. The final table picks each
variant's slowest *local* cell and gives today's baseline on exactly those
cases. Both comparisons retain the effect of walking connector batching.

### True nearest-network distances

Distances in metres, min / median / max. The path switch changes prices but not eligibility, so its duplicate distance rows are omitted. Targets retain their frozen attachments; a zero distance does not imply that a previously free descriptor was resnapped.

| Map | Mode | Requested offset | Start distance | Target distance |
| --- | --- | --- | --- | --- |
| abisko | kayak | 8 | 1.80 / 8.00 / 8.00 | 0.00 / 278.76 / 351.17 |
| abisko | kayak | 20 | 6.44 / 19.58 / 20.00 | 0.00 / 164.10 / 441.65 |
| abisko | kayak | 50 | 24.92 / 41.26 / 49.09 | 0.00 / 190.48 / 614.22 |
| abisko | kayak | 100 | 64.22 / 87.43 / 100.00 | 0.00 / 947.31 / 1,891.06 |
| abisko | kayak | 250 | 9.57 / 246.10 / 250.00 | 187.37 / 282.55 / 611.71 |
| abisko | kayak | 500 | 151.66 / 210.81 / 335.81 | 0.00 / 300.26 / 1,116.86 |
| abisko | kayak | 1000 | 82.21 / 566.57 / 807.79 | 0.00 / 281.80 / 693.94 |
| abisko | kayak | 2000 | 39.05 / 262.57 / 803.24 | 240.78 / 534.98 / 1,000.08 |
| abisko | walking | 8 | 1.80 / 8.00 / 8.00 | 21.83 / 303.08 / 1,901.53 |
| abisko | walking | 20 | 6.44 / 19.58 / 20.00 | 236.97 / 584.39 / 2,866.65 |
| abisko | walking | 50 | 41.26 / 48.06 / 49.24 | 169.61 / 637.26 / 1,695.94 |
| abisko | walking | 100 | 64.22 / 87.43 / 100.00 | 0.00 / 1,932.96 / 2,252.43 |
| abisko | walking | 250 | 52.53 / 246.10 / 250.00 | 248.99 / 357.54 / 2,500.63 |
| abisko | walking | 500 | 191.25 / 335.81 / 496.16 | 0.00 / 441.23 / 1,160.97 |
| abisko | walking | 1000 | 82.21 / 773.86 / 842.51 | 37.31 / 697.83 / 3,264.07 |
| abisko | walking | 2000 | 113.57 / 262.57 / 1,781.36 | 296.25 / 699.99 / 2,697.34 |
| malingsbo-kloten | kayak | 8 | 0.02 / 7.51 / 8.00 | 158.15 / 233.81 / 454.88 |
| malingsbo-kloten | kayak | 20 | 4.36 / 19.58 / 20.00 | 0.00 / 199.38 / 413.13 |
| malingsbo-kloten | kayak | 50 | 5.78 / 37.01 / 50.00 | 0.00 / 288.39 / 454.88 |
| malingsbo-kloten | kayak | 100 | 14.09 / 98.25 / 99.70 | 0.00 / 185.79 / 329.74 |
| malingsbo-kloten | kayak | 250 | 1.65 / 27.71 / 249.51 | 0.00 / 162.98 / 395.81 |
| malingsbo-kloten | kayak | 500 | 0.58 / 106.29 / 249.81 | 0.00 / 178.16 / 381.65 |
| malingsbo-kloten | kayak | 1000 | 64.48 / 284.02 / 417.45 | 158.50 / 237.01 / 272.62 |
| malingsbo-kloten | kayak | 2000 | 62.72 / 108.46 / 310.37 | 0.00 / 170.56 / 353.15 |
| malingsbo-kloten | walking | 8 | 0.02 / 7.51 / 8.00 | 254.35 / 454.88 / 587.65 |
| malingsbo-kloten | walking | 20 | 4.36 / 19.58 / 20.00 | 199.38 / 413.13 / 669.52 |
| malingsbo-kloten | walking | 50 | 5.78 / 49.64 / 50.00 | 0.00 / 398.68 / 622.50 |
| malingsbo-kloten | walking | 100 | 36.93 / 98.25 / 99.70 | 185.79 / 323.87 / 702.02 |
| malingsbo-kloten | walking | 250 | 1.65 / 27.71 / 249.51 | 0.00 / 162.98 / 991.47 |
| malingsbo-kloten | walking | 500 | 0.58 / 109.43 / 249.81 | 178.16 / 601.64 / 1,027.71 |
| malingsbo-kloten | walking | 1000 | 64.48 / 334.77 / 417.45 | 158.50 / 693.92 / 756.39 |
| malingsbo-kloten | walking | 2000 | 62.72 / 108.46 / 342.06 | 22.14 / 256.33 / 353.15 |
| lomsdal-visten | kayak | 8 | 1.75 / 7.14 / 7.93 | 0.00 / 394.28 / 4,029.33 |
| lomsdal-visten | kayak | 20 | 1.27 / 17.25 / 19.30 | 379.76 / 4,574.35 / 15,908.79 |
| lomsdal-visten | kayak | 50 | 20.42 / 45.51 / 48.34 | 0.00 / 675.87 / 4,480.33 |
| lomsdal-visten | kayak | 100 | 32.26 / 89.64 / 98.50 | 0.00 / 1,693.28 / 10,659.42 |
| lomsdal-visten | kayak | 250 | 14.26 / 45.73 / 98.67 | 362.97 / 7,229.38 / 10,325.31 |
| lomsdal-visten | kayak | 500 | 2.74 / 16.49 / 249.54 | 0.00 / 425.62 / 5,654.74 |
| lomsdal-visten | kayak | 1000 | 342.44 / 417.22 / 766.61 | 0.00 / 173.82 / 1,377.41 |
| lomsdal-visten | kayak | 2000 | 7.82 / 160.03 / 551.79 | 0.00 / 250.58 / 14,379.48 |
| lomsdal-visten | walking | 8 | 1.75 / 7.66 / 8.00 | 366.15 / 687.44 / 4,029.33 |
| lomsdal-visten | walking | 20 | 6.45 / 17.25 / 19.30 | 772.21 / 4,574.35 / 15,908.79 |
| lomsdal-visten | walking | 50 | 20.42 / 45.51 / 48.34 | 0.00 / 750.10 / 5,677.17 |
| lomsdal-visten | walking | 100 | 32.26 / 89.64 / 98.50 | 0.00 / 1,693.28 / 10,659.42 |
| lomsdal-visten | walking | 250 | 14.26 / 81.21 / 232.41 | 843.97 / 7,229.38 / 10,325.31 |
| lomsdal-visten | walking | 500 | 2.74 / 249.54 / 423.63 | 0.00 / 621.34 / 7,601.12 |
| lomsdal-visten | walking | 1000 | 365.92 / 574.01 / 766.61 | 20.33 / 265.32 / 2,540.50 |
| lomsdal-visten | walking | 2000 | 7.82 / 160.03 / 623.26 | 61.65 / 250.58 / 14,379.48 |

### Summary across maps

All 528 case-settings, including supplementary Kloten readings, equally weighted.

| Radius | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max |
| --- | --- | --- | --- | --- |
| 0 | 87.69 | 59.71 / 1,611.68 / 9,158.47 | 0.22 / 43.69 / 139.73 | 0.83 / 258.16 / 10,587.70 |
| 50 m | 62.50 | 8.78 / 1,518.00 / 9,020.27 | 0.03 / 2.92 / 20.06 | 0.00 / 242.94 / 10,588.97 |
| 100 m | 55.11 | 1.39 / 1,352.07 / 9,020.27 | 0.00 / 2.83 / 20.06 | 0.00 / 242.94 / 10,588.97 |
| 250 m | 49.24 | 0.00 / 1,202.94 / 9,020.27 | 0.00 / 2.04 / 18.26 | 0.00 / 189.46 / 10,588.97 |
| 500 m | 37.31 | 0.00 / 1,006.24 / 9,020.27 | 0.00 / 1.46 / 18.26 | 0.00 / 170.57 / 17,355.57 |
| 1000 m | 26.89 | 0.00 / 979.40 / 9,020.27 | 0.00 / 1.24 / 18.26 | 0.00 / 141.65 / 17,355.57 |
| d + 50 m | 39.20 | 0.00 / 1,006.24 / 9,020.27 | 0.00 / 1.57 / 20.06 | 0.00 / 173.89 / 17,355.57 |
| d + 100 m | 34.66 | 0.00 / 979.40 / 9,020.27 | 0.00 / 1.54 / 20.06 | 0.00 / 170.57 / 17,355.57 |
| d + 250 m | 30.11 | 0.00 / 782.80 / 9,020.27 | 0.00 / 1.04 / 11.57 | 0.00 / 146.24 / 17,370.69 |
| Unlimited | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |

### Summary across maps, keeping each setting separate

| Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| kayak | 0 | 132 | 73.48 | 9.05 / 262.22 / 859.71 | 0.05 / 36.25 / 47.43 | 0.00 / 74.09 / 10,587.70 | 734.00 / 4,602.15 / 5,107.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | 50 m | 132 | 41.67 | 0.00 / 262.22 / 859.71 | 0.00 / 2.08 / 4.96 | 0.00 / 24.92 / 10,588.97 | 750.50 / 4,377.65 / 5,477.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | 100 m | 132 | 37.12 | 0.00 / 262.22 / 859.71 | 0.00 / 1.60 / 4.96 | 0.00 / 24.92 / 10,588.97 | 744.50 / 4,551.45 / 5,495.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | 250 m | 132 | 35.61 | 0.00 / 254.18 / 859.71 | 0.00 / 1.44 / 4.96 | 0.00 / 23.14 / 10,588.97 | 690.50 / 4,462.50 / 5,580.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | 500 m | 132 | 26.52 | 0.00 / 125.69 / 859.71 | 0.00 / 0.74 / 3.16 | 0.00 / 11.44 / 10,588.97 | 730.00 / 4,452.45 / 5,357.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | 1000 m | 132 | 17.42 | 0.00 / 22.49 / 859.71 | 0.00 / 0.17 / 1.88 | 0.00 / 6.15 / 10,588.97 | 729.50 / 4,581.15 / 5,238.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | d + 50 m | 132 | 34.85 | 0.00 / 130.74 / 859.71 | 0.00 / 0.97 / 4.96 | 0.00 / 23.48 / 10,588.97 | 731.00 / 4,775.70 / 5,357.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | d + 100 m | 132 | 29.55 | 0.00 / 125.69 / 859.71 | 0.00 / 0.74 / 4.96 | 0.00 / 11.44 / 10,588.97 | 759.50 / 4,851.15 / 5,426.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | d + 250 m | 132 | 24.24 | 0.00 / 104.31 / 859.71 | 0.00 / 0.60 / 2.52 | 0.00 / 7.14 / 10,588.97 | 728.50 / 4,676.55 / 5,502.00 | 681.50 / 4,349.40 / 5,010.00 |
| kayak | Unlimited | 132 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 681.50 / 4,349.40 / 5,010.00 |
| kayak-paths | 0 | 132 | 85.61 | 49.36 / 1,090.51 / 5,735.69 | 0.45 / 100.92 / 139.73 | 1.65 / 313.20 / 3,769.08 | 671.00 / 4,380.15 / 4,959.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | 50 m | 132 | 46.97 | 0.00 / 1,090.51 / 5,735.69 | 0.00 / 5.40 / 18.26 | 0.00 / 313.20 / 3,767.81 | 752.00 / 4,389.50 / 5,005.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | 100 m | 132 | 39.39 | 0.00 / 964.98 / 5,735.69 | 0.00 / 5.40 / 18.26 | 0.00 / 294.16 / 3,767.81 | 698.00 / 4,337.70 / 5,052.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | 250 m | 132 | 31.06 | 0.00 / 949.12 / 4,663.07 | 0.00 / 2.47 / 18.26 | 0.00 / 112.48 / 3,767.81 | 723.00 / 4,337.15 / 5,283.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | 500 m | 132 | 18.18 | 0.00 / 442.52 / 3,757.04 | 0.00 / 1.02 / 18.26 | 0.00 / 22.09 / 3,767.81 | 727.00 / 4,383.15 / 5,108.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | 1000 m | 132 | 12.12 | 0.00 / 267.12 / 3,757.04 | 0.00 / 0.77 / 18.26 | 0.00 / 0.00 / 1,735.22 | 744.50 / 4,498.30 / 5,328.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | d + 50 m | 132 | 18.94 | 0.00 / 315.57 / 1,095.74 | 0.00 / 0.90 / 7.17 | 0.00 / 22.09 / 3,767.81 | 695.00 / 4,561.05 / 5,227.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | d + 100 m | 132 | 17.42 | 0.00 / 315.57 / 1,095.74 | 0.00 / 0.90 / 7.17 | 0.00 / 8.43 / 3,767.81 | 722.00 / 4,540.45 / 5,142.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | d + 250 m | 132 | 15.15 | 0.00 / 267.12 / 1,095.74 | 0.00 / 0.77 / 7.17 | 0.00 / 1.59 / 3,767.81 | 718.50 / 4,490.85 / 5,333.00 | 711.00 / 4,236.40 / 4,847.00 |
| kayak-paths | Unlimited | 132 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 711.00 / 4,236.40 / 4,847.00 |
| walking | 0 | 132 | 94.70 | 103.47 / 1,299.53 / 3,502.94 | 0.16 / 15.50 / 65.49 | 2.18 / 392.72 / 5,882.72 | 525.00 / 3,036.45 / 5,157.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | 50 m | 132 | 80.30 | 50.85 / 1,299.53 / 3,502.94 | 0.09 / 2.09 / 20.06 | 0.00 / 392.72 / 5,882.72 | 501.00 / 3,127.00 / 4,986.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | 100 m | 132 | 71.97 | 43.02 / 1,299.53 / 3,467.80 | 0.05 / 2.09 / 20.06 | 0.00 / 392.11 / 5,882.72 | 506.50 / 2,938.30 / 5,096.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | 250 m | 132 | 66.67 | 28.13 / 1,187.61 / 3,467.80 | 0.04 / 1.91 / 11.57 | 0.00 / 392.11 / 5,882.72 | 495.50 / 2,983.05 / 5,244.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | 500 m | 132 | 56.06 | 4.31 / 1,187.61 / 3,467.80 | 0.01 / 1.74 / 11.57 | 0.00 / 389.43 / 5,882.72 | 518.00 / 3,038.30 / 5,273.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | 1000 m | 132 | 42.42 | 0.00 / 1,187.61 / 3,467.80 | 0.00 / 1.65 / 11.57 | 0.00 / 389.43 / 5,882.72 | 542.50 / 3,067.25 / 4,933.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | d + 50 m | 132 | 59.09 | 5.79 / 1,299.53 / 3,467.80 | 0.01 / 1.93 / 20.06 | 0.00 / 389.43 / 5,882.72 | 543.00 / 3,268.20 / 5,589.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | d + 100 m | 132 | 52.27 | 0.42 / 1,187.61 / 3,467.80 | 0.00 / 1.93 / 20.06 | 0.00 / 389.43 / 5,882.72 | 502.50 / 3,248.45 / 5,649.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | d + 250 m | 132 | 46.21 | 0.00 / 822.06 / 3,467.80 | 0.00 / 1.65 / 11.57 | 0.00 / 398.84 / 5,874.41 | 549.50 / 3,334.55 / 5,330.00 | 1,391.00 / 7,992.20 / 14,122.00 |
| walking | Unlimited | 132 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,391.00 / 7,992.20 / 14,122.00 |
| paths | 0 | 132 | 96.97 | 253.70 / 2,746.44 / 9,158.47 | 0.40 / 9.81 / 104.19 | 6.23 / 314.09 / 2,072.06 | 286.50 / 1,849.75 / 2,548.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | 50 m | 132 | 81.06 | 102.49 / 2,743.39 / 9,020.27 | 0.27 / 4.24 / 11.94 | 0.00 / 314.09 / 2,060.39 | 286.50 / 1,882.05 / 2,807.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | 100 m | 132 | 71.97 | 87.12 / 2,743.39 / 9,020.27 | 0.16 / 4.24 / 11.94 | 0.00 / 314.09 / 2,060.39 | 281.00 / 1,775.85 / 2,623.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | 250 m | 132 | 63.64 | 71.58 / 2,645.05 / 9,020.27 | 0.12 / 3.19 / 11.94 | 0.00 / 209.72 / 2,060.39 | 284.50 / 1,762.35 / 2,624.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | 500 m | 132 | 48.48 | 0.00 / 1,480.04 / 9,020.27 | 0.00 / 1.59 / 7.72 | 0.00 / 203.59 / 17,355.57 | 287.50 / 1,732.25 / 2,578.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | 1000 m | 132 | 35.61 | 0.00 / 1,480.04 / 9,020.27 | 0.00 / 1.59 / 7.72 | 0.00 / 197.36 / 17,355.57 | 298.00 / 1,845.00 / 2,663.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | d + 50 m | 132 | 43.94 | 0.00 / 1,815.40 / 9,020.27 | 0.00 / 1.78 / 11.94 | 0.00 / 182.63 / 17,355.57 | 283.50 / 1,862.00 / 3,085.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | d + 100 m | 132 | 39.39 | 0.00 / 1,537.21 / 9,020.27 | 0.00 / 1.78 / 11.94 | 0.00 / 199.64 / 17,355.57 | 287.00 / 1,868.30 / 3,128.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | d + 250 m | 132 | 34.85 | 0.00 / 1,238.23 / 9,020.27 | 0.00 / 1.54 / 6.65 | 0.00 / 177.11 / 17,370.69 | 288.50 / 1,897.65 / 3,305.00 | 613.00 / 4,158.75 / 6,054.00 |
| paths | Unlimited | 132 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 613.00 / 4,158.75 / 6,054.00 |

### By actual start distance, pooled across maps and settings

Generated cases only; Kloten remains separate. Bands use the measured nearest eligible network point in the current mode. Target-side restrictions can also cause a difference, so these are not isolated start-entry effects.

| Actual start distance | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| (0, 8] m | 0 | 94 | 93.62 | 44.89 / 1,400.15 / 9,158.47 | 0.21 / 6.43 / 12.15 | 0.50 / 155.88 / 10,587.70 | 562.00 / 3,416.10 / 5,092.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | 50 m | 94 | 44.68 | 0.00 / 902.16 / 9,020.27 | 0.00 / 1.88 / 11.94 | 0.00 / 153.71 / 10,588.97 | 596.50 / 3,395.75 / 4,994.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | 100 m | 94 | 44.68 | 0.00 / 902.16 / 9,020.27 | 0.00 / 1.88 / 11.94 | 0.00 / 153.71 / 10,588.97 | 594.00 / 3,380.20 / 4,955.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | 250 m | 94 | 44.68 | 0.00 / 902.16 / 9,020.27 | 0.00 / 1.88 / 11.94 | 0.00 / 153.71 / 10,588.97 | 590.50 / 3,456.20 / 4,926.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | 500 m | 94 | 34.04 | 0.00 / 714.10 / 9,020.27 | 0.00 / 1.31 / 6.65 | 0.00 / 153.71 / 10,588.97 | 570.50 / 3,535.20 / 4,981.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | 1000 m | 94 | 20.21 | 0.00 / 714.10 / 9,020.27 | 0.00 / 1.29 / 6.65 | 0.00 / 153.71 / 10,588.97 | 592.00 / 3,599.60 / 5,182.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | d + 50 m | 94 | 32.98 | 0.00 / 902.16 / 9,020.27 | 0.00 / 1.72 / 11.94 | 0.00 / 153.71 / 10,588.97 | 599.00 / 3,671.20 / 5,127.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | d + 100 m | 94 | 29.79 | 0.00 / 645.71 / 9,020.27 | 0.00 / 1.72 / 11.94 | 0.00 / 174.12 / 10,588.97 | 603.50 / 3,544.40 / 4,877.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | d + 250 m | 94 | 24.47 | 0.00 / 602.15 / 9,020.27 | 0.00 / 0.92 / 6.65 | 0.00 / 119.40 / 10,588.97 | 608.00 / 3,637.20 / 4,994.00 | 781.50 / 4,960.60 / 11,121.00 |
| (0, 8] m | Unlimited | 94 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 781.50 / 4,960.60 / 11,121.00 |
| (8, 20] m | 0 | 62 | 98.39 | 31.25 / 892.87 / 2,756.55 | 0.13 / 6.89 / 14.67 | 0.10 / 135.44 / 3,769.08 | 665.50 / 4,759.60 / 5,157.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | 50 m | 62 | 53.23 | 0.68 / 892.71 / 2,749.77 | 0.00 / 0.81 / 1.61 | 0.00 / 134.08 / 3,767.81 | 651.00 / 4,676.85 / 4,986.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | 100 m | 62 | 53.23 | 0.68 / 892.71 / 2,749.77 | 0.00 / 0.81 / 1.61 | 0.00 / 121.33 / 3,767.81 | 639.50 / 4,739.30 / 5,096.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | 250 m | 62 | 50.00 | 0.00 / 892.71 / 2,749.77 | 0.00 / 0.81 / 1.61 | 0.00 / 121.33 / 3,767.81 | 675.00 / 4,828.50 / 5,244.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | 500 m | 62 | 40.32 | 0.00 / 892.71 / 2,749.77 | 0.00 / 0.81 / 1.61 | 0.00 / 93.48 / 3,767.81 | 680.00 / 4,762.70 / 5,273.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | 1000 m | 62 | 30.65 | 0.00 / 892.71 / 2,749.77 | 0.00 / 0.53 / 1.61 | 0.00 / 19.09 / 249.10 | 669.00 / 4,654.85 / 5,114.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | d + 50 m | 62 | 40.32 | 0.00 / 892.71 / 2,749.77 | 0.00 / 0.81 / 1.61 | 0.00 / 121.33 / 3,767.81 | 665.00 / 4,852.50 / 5,589.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | d + 100 m | 62 | 38.71 | 0.00 / 892.71 / 2,749.77 | 0.00 / 0.81 / 1.61 | 0.00 / 93.48 / 3,767.81 | 632.00 / 4,889.85 / 5,649.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | d + 250 m | 62 | 38.71 | 0.00 / 892.71 / 2,749.77 | 0.00 / 0.81 / 1.61 | 0.00 / 93.48 / 3,767.81 | 628.50 / 4,817.40 / 5,502.00 | 1,293.50 / 5,987.50 / 14,122.00 |
| (8, 20] m | Unlimited | 62 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,293.50 / 5,987.50 / 14,122.00 |
| (20, 50] m | 0 | 72 | 93.06 | 46.72 / 1,080.82 / 2,692.61 | 0.15 / 1.93 / 7.21 | 1.31 / 185.49 / 770.23 | 813.50 / 2,951.80 / 5,107.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | 50 m | 72 | 61.11 | 3.60 / 840.14 / 2,678.84 | 0.01 / 1.25 / 1.89 | 0.00 / 163.86 / 942.17 | 777.00 / 2,926.50 / 5,048.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | 100 m | 72 | 50.00 | 0.01 / 840.14 / 2,678.84 | 0.00 / 0.87 / 1.70 | 0.00 / 163.86 / 942.17 | 806.50 / 2,957.15 / 4,991.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | 250 m | 72 | 43.06 | 0.00 / 840.14 / 2,678.84 | 0.00 / 0.87 / 1.70 | 0.00 / 163.86 / 942.17 | 775.50 / 2,995.45 / 5,195.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | 500 m | 72 | 41.67 | 0.00 / 840.14 / 2,678.84 | 0.00 / 0.87 / 1.70 | 0.00 / 163.86 / 942.17 | 751.50 / 2,993.50 / 5,214.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | 1000 m | 72 | 30.56 | 0.00 / 820.43 / 2,678.84 | 0.00 / 0.67 / 1.70 | 0.00 / 155.62 / 942.17 | 787.00 / 3,014.05 / 5,221.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | d + 50 m | 72 | 37.50 | 0.00 / 820.43 / 2,678.84 | 0.00 / 0.67 / 1.70 | 0.00 / 163.86 / 942.17 | 767.00 / 2,979.05 / 5,201.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | d + 100 m | 72 | 36.11 | 0.00 / 820.43 / 2,678.84 | 0.00 / 0.67 / 1.70 | 0.00 / 163.86 / 942.17 | 806.50 / 3,001.30 / 5,305.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | d + 250 m | 72 | 33.33 | 0.00 / 820.43 / 2,678.84 | 0.00 / 0.67 / 1.70 | 0.00 / 163.86 / 942.17 | 829.50 / 3,137.00 / 5,185.00 | 1,222.00 / 4,932.05 / 10,993.00 |
| (20, 50] m | Unlimited | 72 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,222.00 / 4,932.05 / 10,993.00 |
| (50, 100] m | 0 | 90 | 76.67 | 23.86 / 744.48 / 3,502.94 | 0.06 / 1.82 / 4.29 | 0.00 / 192.30 / 757.40 | 522.50 / 3,026.00 / 4,569.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | 50 m | 90 | 76.67 | 23.86 / 744.48 / 3,502.94 | 0.06 / 1.82 / 4.29 | 0.00 / 192.30 / 757.40 | 490.50 / 2,912.00 / 4,540.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | 100 m | 90 | 55.56 | 0.57 / 638.50 / 3,467.80 | 0.00 / 0.94 / 2.23 | 0.00 / 130.81 / 757.40 | 527.00 / 2,914.85 / 4,680.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | 250 m | 90 | 45.56 | 0.00 / 633.60 / 3,467.80 | 0.00 / 0.94 / 2.23 | 0.00 / 127.12 / 757.40 | 499.50 / 2,949.10 / 5,201.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | 500 m | 90 | 30.00 | 0.00 / 633.60 / 3,467.80 | 0.00 / 0.84 / 2.23 | 0.00 / 79.49 / 757.40 | 510.00 / 2,976.60 / 5,018.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | 1000 m | 90 | 21.11 | 0.00 / 375.48 / 3,467.80 | 0.00 / 0.68 / 2.23 | 0.00 / 3.48 / 757.40 | 506.00 / 3,021.95 / 4,933.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | d + 50 m | 90 | 34.44 | 0.00 / 539.30 / 3,467.80 | 0.00 / 0.92 / 2.23 | 0.00 / 130.93 / 757.40 | 515.50 / 2,882.45 / 5,046.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | d + 100 m | 90 | 28.89 | 0.00 / 539.30 / 3,467.80 | 0.00 / 0.80 / 2.23 | 0.00 / 79.25 / 757.40 | 530.50 / 2,827.10 / 4,637.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | d + 250 m | 90 | 24.44 | 0.00 / 539.30 / 3,467.80 | 0.00 / 0.80 / 2.23 | 0.00 / 58.11 / 757.40 | 528.50 / 2,979.45 / 4,863.00 | 926.00 / 4,157.60 / 13,584.00 |
| (50, 100] m | Unlimited | 90 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 926.00 / 4,157.60 / 13,584.00 |
| (100, 250] m | 0 | 74 | 87.84 | 63.06 / 2,822.73 / 5,735.69 | 0.29 / 7.19 / 18.26 | 0.00 / 1,057.58 / 1,922.18 | 682.50 / 4,704.50 / 5,089.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | 50 m | 74 | 87.84 | 63.06 / 2,822.73 / 5,735.69 | 0.29 / 7.19 / 18.26 | 0.00 / 1,057.58 / 1,922.18 | 667.50 / 4,611.65 / 5,477.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | 100 m | 74 | 87.84 | 63.06 / 2,822.73 / 5,735.69 | 0.29 / 7.19 / 18.26 | 0.00 / 1,057.58 / 1,922.18 | 665.00 / 4,622.65 / 5,495.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | 250 m | 74 | 70.27 | 14.83 / 1,134.30 / 3,757.04 | 0.09 / 5.15 / 18.26 | 0.00 / 733.37 / 1,735.22 | 680.00 / 4,620.60 / 5,580.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | 500 m | 74 | 44.59 | 0.00 / 1,057.56 / 3,757.04 | 0.00 / 4.41 / 18.26 | 0.00 / 693.16 / 1,735.22 | 716.50 / 4,685.30 / 5,357.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | 1000 m | 74 | 35.14 | 0.00 / 1,057.56 / 3,757.04 | 0.00 / 4.41 / 18.26 | 0.00 / 598.32 / 1,735.22 | 696.00 / 4,875.00 / 5,328.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | d + 50 m | 74 | 60.81 | 6.83 / 1,013.98 / 3,145.10 | 0.02 / 4.23 / 11.77 | 0.00 / 693.16 / 1,123.34 | 678.50 / 4,800.75 / 5,217.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | d + 100 m | 74 | 52.70 | 0.91 / 1,013.98 / 3,093.17 | 0.00 / 4.23 / 11.57 | 0.00 / 693.16 / 1,123.34 | 680.50 / 4,630.90 / 5,084.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | d + 250 m | 74 | 39.19 | 0.00 / 1,013.98 / 3,093.17 | 0.00 / 2.98 / 11.57 | 0.00 / 500.84 / 766.63 | 688.50 / 4,632.60 / 5,222.00 | 953.00 / 4,479.75 / 5,010.00 |
| (100, 250] m | Unlimited | 74 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 953.00 / 4,479.75 / 5,010.00 |
| (250, 500] m | 0 | 52 | 75.00 | 35.18 / 3,638.51 / 5,470.70 | 0.08 / 7.73 / 14.33 | 0.00 / 356.82 / 1,904.43 | 1,048.50 / 2,794.50 / 2,874.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | 50 m | 52 | 75.00 | 35.18 / 3,638.51 / 5,470.70 | 0.08 / 7.73 / 14.33 | 0.00 / 356.82 / 1,904.43 | 1,058.50 / 2,795.00 / 2,947.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | 100 m | 52 | 75.00 | 35.18 / 3,638.51 / 5,470.70 | 0.08 / 7.73 / 14.33 | 0.00 / 356.82 / 1,904.43 | 1,039.50 / 2,834.20 / 2,899.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | 250 m | 52 | 71.15 | 35.18 / 3,601.36 / 5,470.70 | 0.08 / 7.73 / 14.33 | 0.00 / 356.82 / 1,904.43 | 1,010.00 / 2,848.90 / 2,922.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | 500 m | 52 | 46.15 | 0.00 / 976.57 / 3,623.06 | 0.00 / 1.18 / 7.72 | 0.00 / 339.33 / 17,355.57 | 1,004.50 / 2,754.50 / 3,039.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | 1000 m | 52 | 36.54 | 0.00 / 976.57 / 3,623.06 | 0.00 / 1.18 / 7.72 | 0.00 / 265.56 / 17,355.57 | 1,054.50 / 2,785.20 / 3,071.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | d + 50 m | 52 | 51.92 | 0.00 / 937.91 / 2,250.80 | 0.00 / 1.18 / 2.34 | 0.00 / 209.25 / 17,355.57 | 1,021.00 / 2,786.90 / 3,028.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | d + 100 m | 52 | 42.31 | 0.00 / 937.91 / 2,250.80 | 0.00 / 1.18 / 2.34 | 0.00 / 171.28 / 17,355.57 | 974.50 / 2,740.80 / 2,977.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | d + 250 m | 52 | 38.46 | 0.00 / 400.59 / 1,621.27 | 0.00 / 0.78 / 1.69 | 0.00 / 25.37 / 17,370.69 | 1,023.50 / 2,725.00 / 3,092.00 | 2,065.00 / 3,949.65 / 8,353.00 |
| (250, 500] m | Unlimited | 52 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,065.00 / 3,949.65 / 8,353.00 |
| (500, 1000] m | 0 | 34 | 70.59 | 55.91 / 2,599.09 / 3,107.84 | 0.07 / 10.91 / 20.06 | 0.00 / 557.46 / 1,778.27 | 314.00 / 4,017.30 / 4,141.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | 50 m | 34 | 70.59 | 55.91 / 2,599.09 / 3,107.84 | 0.07 / 10.91 / 20.06 | 0.00 / 557.46 / 1,778.27 | 312.00 / 3,937.55 / 4,120.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | 100 m | 34 | 70.59 | 55.91 / 2,599.09 / 3,107.84 | 0.07 / 10.91 / 20.06 | 0.00 / 557.46 / 1,778.27 | 292.50 / 3,956.05 / 4,173.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | 250 m | 34 | 70.59 | 44.25 / 1,618.60 / 2,738.16 | 0.07 / 3.34 / 16.51 | 0.00 / 557.46 / 1,778.27 | 298.50 / 3,907.80 / 4,065.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | 500 m | 34 | 70.59 | 33.59 / 1,618.60 / 2,738.16 | 0.04 / 3.34 / 16.51 | 0.00 / 557.46 / 1,778.27 | 301.50 / 3,954.50 / 4,127.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | 1000 m | 34 | 47.06 | 0.00 / 1,045.97 / 2,738.16 | 0.00 / 1.44 / 3.12 | 0.00 / 193.67 / 1,021.15 | 297.50 / 3,963.50 / 4,268.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | d + 50 m | 34 | 58.82 | 6.17 / 2,183.78 / 3,107.84 | 0.01 / 4.79 / 20.06 | 0.00 / 193.67 / 1,021.15 | 314.50 / 4,529.55 / 5,290.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | d + 100 m | 34 | 50.00 | 0.28 / 2,183.78 / 3,107.84 | 0.00 / 4.79 / 20.06 | 0.00 / 193.67 / 1,021.15 | 325.00 / 4,588.85 / 5,311.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | d + 250 m | 34 | 47.06 | 0.00 / 1,045.97 / 2,738.16 | 0.00 / 1.53 / 3.12 | 0.00 / 193.67 / 358.41 | 322.50 / 4,546.50 / 5,362.00 | 516.50 / 5,980.55 / 9,956.00 |
| (500, 1000] m | Unlimited | 34 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 516.50 / 5,980.55 / 9,956.00 |
| (1000, 2000] m | 0 | 2 | 100.00 | 1,560.28 / 2,388.02 / 2,479.99 | 4.16 / 6.95 / 7.26 | 2,778.20 / 5,572.27 / 5,882.72 | 80.50 / 85.45 / 86.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | 50 m | 2 | 100.00 | 1,560.28 / 2,388.02 / 2,479.99 | 4.16 / 6.95 / 7.26 | 2,778.20 / 5,572.27 / 5,882.72 | 89.50 / 98.95 / 100.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | 100 m | 2 | 100.00 | 1,560.28 / 2,388.02 / 2,479.99 | 4.16 / 6.95 / 7.26 | 2,778.20 / 5,572.27 / 5,882.72 | 83.00 / 83.00 / 83.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | 250 m | 2 | 100.00 | 1,560.28 / 2,388.02 / 2,479.99 | 4.16 / 6.95 / 7.26 | 2,778.20 / 5,572.27 / 5,882.72 | 86.00 / 91.40 / 92.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | 500 m | 2 | 100.00 | 1,560.28 / 2,388.02 / 2,479.99 | 4.16 / 6.95 / 7.26 | 2,778.20 / 5,572.27 / 5,882.72 | 81.50 / 89.15 / 90.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | 1000 m | 2 | 100.00 | 1,560.28 / 2,388.02 / 2,479.99 | 4.16 / 6.95 / 7.26 | 2,778.20 / 5,572.27 / 5,882.72 | 81.00 / 89.10 / 90.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | d + 50 m | 2 | 50.00 | 1,239.99 / 2,355.99 / 2,479.99 | 3.63 / 6.90 / 7.26 | 2,941.36 / 5,588.59 / 5,882.72 | 123.50 / 129.35 / 130.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | d + 100 m | 2 | 50.00 | 1,239.99 / 2,355.99 / 2,479.99 | 3.63 / 6.90 / 7.26 | 2,941.36 / 5,588.59 / 5,882.72 | 123.00 / 128.40 / 129.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | d + 250 m | 2 | 50.00 | 1,238.19 / 2,352.55 / 2,476.37 | 3.63 / 6.89 / 7.25 | 2,937.21 / 5,580.69 / 5,874.41 | 139.00 / 139.90 / 140.00 | 183.50 / 183.95 / 184.00 |
| (1000, 2000] m | Unlimited | 2 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 183.50 / 183.95 / 184.00 |

### Kloten supplementary readings

| Setting | Radius | Changed / n | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max |
| --- | --- | --- | --- | --- | --- |
| kayak | 0 | 12 / 12 | 118.63 / 146.78 / 146.78 | 36.30 / 47.43 / 47.43 | 67.19 / 89.42 / 89.42 |
| kayak | 50 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | 500 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | 1000 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | d + 50 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | d + 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | d + 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak | Unlimited | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | 0 | 12 / 12 | 448.46 / 510.84 / 510.84 | 106.44 / 139.73 / 139.73 | 80.82 / 88.11 / 88.11 |
| kayak-paths | 50 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | 500 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | 1000 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | d + 50 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | d + 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | d + 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| kayak-paths | Unlimited | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | 0 | 12 / 12 | 254.16 / 284.22 / 284.94 | 22.08 / 64.46 / 65.49 | 120.37 / 229.63 / 326.05 |
| walking | 50 m | 6 / 12 | 25.43 / 50.85 / 50.85 | 0.28 / 0.57 / 0.57 | 18.12 / 36.24 / 36.24 |
| walking | 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | 500 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | 1000 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | d + 50 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | d + 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | d + 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| walking | Unlimited | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | 0 | 12 / 12 | 663.39 / 754.57 / 760.17 | 32.92 / 100.62 / 104.19 | 107.31 / 140.48 / 140.77 |
| paths | 50 m | 6 / 12 | 46.61 / 93.23 / 93.23 | 0.48 / 0.98 / 0.98 | 14.61 / 29.23 / 29.23 |
| paths | 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | 500 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | 1000 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | d + 50 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | d + 100 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | d + 250 m | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| paths | Unlimited | 0 / 12 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |

### Every map, setting and variant

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 40 | 87.50 | 21.70 / 1,277.93 / 3,757.04 | 0.73 / 14.77 / 18.26 | 0.00 / 1,069.00 / 1,778.27 | 287.50 / 531.15 / 698.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | 0 | 40 | 65.00 | 1.39 / 127.83 / 303.03 | 0.03 / 3.27 / 14.67 | 0.00 / 12.16 / 25.33 | 271.50 / 515.30 / 752.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | 0 | 40 | 97.50 | 466.97 / 2,781.61 / 3,659.91 | 0.54 / 7.81 / 12.15 | 14.08 / 702.65 / 1,904.43 | 123.50 / 293.35 / 301.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | 0 | 40 | 95.00 | 138.44 / 3,109.70 / 3,502.94 | 0.23 / 7.49 / 20.06 | -3.83 / 770.59 / 5,882.72 | 259.50 / 385.90 / 540.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | 0 | 40 | 77.50 | 10.64 / 544.91 / 5,735.69 | 0.03 / 6.58 / 7.21 | 0.77 / 99.07 / 1,744.55 | 2,416.00 / 4,726.10 / 4,959.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | 0 | 40 | 82.50 | 8.83 / 667.74 / 859.71 | 0.04 / 1.78 / 3.90 | 0.00 / 73.06 / 10,587.70 | 2,631.50 / 5,089.15 / 5,107.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | 0 | 40 | 95.00 | 97.40 / 1,931.62 / 9,158.47 | 0.14 / 1.12 / 6.75 | 1.05 / 267.84 / 2,072.06 | 957.50 / 2,313.20 / 2,548.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | 0 | 40 | 90.00 | 40.97 / 1,428.88 / 2,692.61 | 0.05 / 1.37 / 1.84 | 4.49 / 284.09 / 770.23 | 1,868.00 / 4,436.95 / 5,157.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 0 | 52 | 90.38 | 154.62 / 931.87 / 4,663.07 | 0.83 / 124.06 / 139.73 | 23.14 / 313.20 / 3,769.08 | 1,136.00 / 2,690.75 / 3,134.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | 0 | 52 | 73.08 | 16.80 / 220.80 / 826.19 | 0.12 / 45.16 / 47.43 | 0.00 / 82.52 / 175.33 | 1,100.50 / 2,613.10 / 2,894.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | 0 | 52 | 98.08 | 338.37 / 1,712.35 / 5,470.70 | 0.60 / 88.47 / 104.19 | 27.01 / 179.34 / 941.16 | 329.50 / 1,032.30 / 1,116.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | 0 | 52 | 98.08 | 168.96 / 715.38 / 937.51 | 0.36 / 58.10 / 65.49 | 8.44 / 150.37 / 326.05 | 801.50 / 1,187.05 / 1,225.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | 50 m | 40 | 62.50 | 7.10 / 1,277.93 / 3,757.04 | 0.12 / 10.24 / 18.26 | 0.00 / 1,069.00 / 1,778.27 | 268.50 / 536.80 / 735.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | 50 m | 40 | 50.00 | 0.01 / 127.83 / 303.03 | 0.00 / 3.16 / 4.17 | 0.00 / 12.16 / 25.33 | 283.50 / 507.55 / 737.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | 50 m | 40 | 87.50 | 466.32 / 2,772.29 / 3,659.91 | 0.47 / 7.81 / 11.94 | 11.36 / 702.65 / 1,904.43 | 120.00 / 309.00 / 311.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | 50 m | 40 | 85.00 | 138.44 / 3,109.70 / 3,502.94 | 0.23 / 7.49 / 20.06 | -1.54 / 770.59 / 5,882.72 | 259.00 / 392.65 / 459.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | 50 m | 40 | 37.50 | 0.00 / 514.66 / 5,735.69 | 0.00 / 0.74 / 5.43 | 0.00 / 99.07 / 1,744.55 | 2,439.00 / 4,651.65 / 5,005.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | 50 m | 40 | 45.00 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 48.79 / 10,588.97 | 2,629.00 / 4,996.70 / 5,477.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | 50 m | 40 | 77.50 | 80.26 / 1,931.62 / 9,020.27 | 0.08 / 1.12 / 6.65 | 0.00 / 267.84 / 2,060.39 | 979.50 / 2,248.65 / 2,807.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | 50 m | 40 | 82.50 | 33.86 / 1,428.86 / 2,678.84 | 0.04 / 1.37 / 1.78 | 2.15 / 285.30 / 942.17 | 1,958.00 / 4,419.35 / 4,986.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 50 m | 52 | 42.31 | 0.00 / 931.87 / 4,663.07 | 0.00 / 4.78 / 14.33 | 0.00 / 313.20 / 3,767.81 | 1,075.00 / 2,625.10 / 2,921.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | 50 m | 52 | 32.69 | 0.00 / 220.80 / 826.19 | 0.00 / 1.46 / 4.96 | 0.00 / 29.45 / 175.33 | 1,158.50 / 2,678.40 / 2,901.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | 50 m | 52 | 78.85 | 79.79 / 1,618.73 / 5,470.70 | 0.25 / 2.11 / 7.67 | 0.63 / 173.07 / 941.16 | 356.00 / 974.40 / 1,081.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | 50 m | 52 | 75.00 | 49.91 / 638.96 / 937.51 | 0.09 / 1.10 / 2.92 | 0.66 / 36.24 / 222.10 | 768.50 / 1,223.60 / 1,406.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | 100 m | 40 | 50.00 | 0.00 / 1,277.93 / 3,757.04 | 0.00 / 10.24 / 18.26 | 0.00 / 1,069.00 / 1,778.27 | 286.50 / 525.50 / 684.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | 100 m | 40 | 40.00 | 0.00 / 127.83 / 303.03 | 0.00 / 3.16 / 4.17 | 0.00 / 12.16 / 25.33 | 288.50 / 504.65 / 757.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | 100 m | 40 | 82.50 | 466.32 / 2,772.29 / 3,659.91 | 0.47 / 7.81 / 11.94 | 4.22 / 702.65 / 1,904.43 | 119.00 / 290.65 / 322.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | 100 m | 40 | 80.00 | 132.84 / 3,109.70 / 3,467.80 | 0.22 / 7.49 / 20.06 | -0.79 / 770.59 / 5,882.72 | 259.00 / 414.65 / 465.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | 100 m | 40 | 32.50 | 0.00 / 514.66 / 5,735.69 | 0.00 / 0.74 / 5.43 | 0.00 / 99.07 / 1,744.55 | 2,447.00 / 4,748.35 / 5,052.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | 100 m | 40 | 42.50 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 48.79 / 10,588.97 | 2,640.50 / 4,956.80 / 5,495.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | 100 m | 40 | 72.50 | 79.70 / 1,931.62 / 9,020.27 | 0.08 / 1.12 / 6.65 | 0.00 / 267.84 / 2,060.39 | 979.00 / 2,304.70 / 2,623.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | 100 m | 40 | 80.00 | 33.86 / 1,428.86 / 2,678.84 | 0.04 / 1.37 / 1.78 | 2.00 / 285.30 / 942.17 | 1,957.50 / 4,401.65 / 5,096.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 100 m | 52 | 36.54 | 0.00 / 564.23 / 4,663.07 | 0.00 / 3.33 / 14.33 | 0.00 / 294.16 / 3,767.81 | 1,090.00 / 2,723.15 / 2,999.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | 100 m | 52 | 30.77 | 0.00 / 220.80 / 826.19 | 0.00 / 1.46 / 4.96 | 0.00 / 29.45 / 175.33 | 1,151.50 / 2,603.25 / 2,812.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | 100 m | 52 | 63.46 | 38.43 / 1,618.73 / 5,470.70 | 0.07 / 1.91 / 7.67 | 0.00 / 111.55 / 941.16 | 336.50 / 1,007.40 / 1,095.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | 100 m | 52 | 59.62 | 7.08 / 638.96 / 937.51 | 0.02 / 1.10 / 2.92 | 0.00 / 31.25 / 222.10 | 781.00 / 1,182.10 / 1,311.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | 250 m | 40 | 42.50 | 0.00 / 1,271.83 / 3,757.04 | 0.00 / 8.75 / 18.26 | 0.00 / 1,153.94 / 1,778.27 | 267.00 / 505.80 / 711.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | 250 m | 40 | 40.00 | 0.00 / 127.64 / 303.03 | 0.00 / 2.55 / 3.22 | 0.00 / 12.16 / 25.33 | 275.50 / 520.90 / 699.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | 250 m | 40 | 77.50 | 362.05 / 2,772.29 / 3,659.91 | 0.43 / 5.62 / 11.94 | 0.00 / 713.30 / 1,904.43 | 119.50 / 289.50 / 331.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | 250 m | 40 | 77.50 | 132.84 / 2,510.65 / 3,467.80 | 0.22 / 2.70 / 11.57 | 0.00 / 770.59 / 5,882.72 | 264.50 / 411.50 / 465.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | 250 m | 40 | 25.00 | 0.00 / 514.66 / 1,095.74 | 0.00 / 0.73 / 1.29 | 0.00 / 38.15 / 130.93 | 2,499.00 / 4,839.40 / 5,283.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | 250 m | 40 | 37.50 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 48.79 / 10,588.97 | 2,672.00 / 5,196.25 / 5,580.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | 250 m | 40 | 67.50 | 79.70 / 1,263.08 / 9,020.27 | 0.08 / 0.77 / 6.65 | 0.00 / 151.33 / 2,060.39 | 1,025.50 / 2,278.50 / 2,624.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | 250 m | 40 | 72.50 | 23.32 / 1,428.86 / 2,678.84 | 0.04 / 1.37 / 1.78 | 0.00 / 285.30 / 942.17 | 2,005.00 / 4,647.15 / 5,244.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 250 m | 52 | 26.92 | 0.00 / 544.33 / 4,663.07 | 0.00 / 3.23 / 14.33 | 0.00 / 229.28 / 3,767.81 | 1,139.00 / 2,665.30 / 3,022.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | 250 m | 52 | 30.77 | 0.00 / 180.94 / 826.19 | 0.00 / 1.46 / 4.96 | 0.00 / 23.95 / 175.33 | 1,140.50 / 2,676.35 / 2,860.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | 250 m | 52 | 50.00 | 0.42 / 1,597.94 / 5,470.70 | 0.00 / 1.91 / 7.67 | 0.00 / 61.34 / 941.16 | 316.50 / 1,035.15 / 1,157.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | 250 m | 52 | 53.85 | 0.18 / 638.96 / 792.37 | 0.00 / 1.10 / 2.92 | 0.00 / 27.68 / 130.97 | 755.50 / 1,207.20 / 1,300.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | 500 m | 40 | 32.50 | 0.00 / 1,200.64 / 3,757.04 | 0.00 / 7.64 / 18.26 | 0.00 / 1,153.94 / 1,778.27 | 284.00 / 527.30 / 687.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | 500 m | 40 | 30.00 | 0.00 / 89.29 / 303.03 | 0.00 / 1.91 / 3.16 | 0.00 / 6.61 / 24.58 | 286.00 / 533.90 / 738.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | 500 m | 40 | 67.50 | 210.72 / 2,738.74 / 3,623.06 | 0.32 / 3.91 / 7.72 | 0.00 / 822.80 / 17,355.57 | 128.00 / 294.70 / 344.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | 500 m | 40 | 75.00 | 116.06 / 2,510.65 / 3,467.80 | 0.12 / 2.70 / 11.57 | 0.00 / 770.59 / 5,882.72 | 282.00 / 410.55 / 451.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | 500 m | 40 | 22.50 | 0.00 / 514.66 / 1,095.74 | 0.00 / 0.73 / 1.29 | 0.00 / 38.15 / 130.93 | 2,474.50 / 4,740.60 / 5,108.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | 500 m | 40 | 35.00 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 48.79 / 10,588.97 | 2,631.00 / 5,033.50 / 5,357.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | 500 m | 40 | 60.00 | 34.11 / 1,263.08 / 9,020.27 | 0.03 / 0.68 / 6.65 | 0.00 / 151.33 / 2,060.39 | 977.00 / 2,299.45 / 2,578.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | 500 m | 40 | 67.50 | 18.52 / 1,428.86 / 2,678.84 | 0.03 / 1.37 / 1.78 | 0.00 / 285.30 / 942.17 | 1,936.00 / 4,577.20 / 5,273.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 500 m | 52 | 3.85 | 0.00 / 0.00 / 123.85 | 0.00 / 0.00 / 0.45 | 0.00 / 0.00 / 3,767.81 | 1,160.50 / 2,735.25 / 3,117.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | 500 m | 52 | 17.31 | 0.00 / 15.02 / 125.05 | 0.00 / 0.06 / 0.45 | 0.00 / 5.90 / 24.96 | 1,185.00 / 2,561.55 / 2,805.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | 500 m | 52 | 25.00 | 0.00 / 536.38 / 826.34 | 0.00 / 0.86 / 1.27 | 0.00 / 24.81 / 35.31 | 326.50 / 984.20 / 1,170.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | 500 m | 52 | 32.69 | 0.00 / 582.94 / 738.33 | 0.00 / 0.94 / 2.92 | 0.00 / 21.66 / 160.12 | 800.00 / 1,195.30 / 1,357.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | 1000 m | 40 | 22.50 | 0.00 / 961.93 / 3,757.04 | 0.00 / 3.32 / 18.26 | 0.00 / 0.06 / 1,735.22 | 283.00 / 537.85 / 710.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | 1000 m | 40 | 20.00 | 0.00 / 19.20 / 87.34 | 0.00 / 0.14 / 1.88 | 0.00 / 6.00 / 7.28 | 287.50 / 526.65 / 753.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | 1000 m | 40 | 55.00 | 116.35 / 2,738.74 / 3,623.06 | 0.22 / 3.91 / 7.72 | 0.00 / 822.80 / 17,355.57 | 141.50 / 302.15 / 353.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | 1000 m | 40 | 65.00 | 91.55 / 2,510.65 / 3,467.80 | 0.06 / 2.70 / 11.57 | 0.00 / 770.59 / 5,882.72 | 270.00 / 412.25 / 453.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | 1000 m | 40 | 15.00 | 0.00 / 237.70 / 1,095.74 | 0.00 / 0.45 / 1.29 | 0.00 / 1.75 / 97.39 | 2,472.50 / 4,841.80 / 5,328.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | 1000 m | 40 | 20.00 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 34.59 / 10,588.97 | 2,695.50 / 5,183.95 / 5,238.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | 1000 m | 40 | 57.50 | 22.13 / 1,263.08 / 9,020.27 | 0.02 / 0.68 / 6.65 | 0.00 / 151.33 / 2,060.39 | 1,013.00 / 2,285.30 / 2,663.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | 1000 m | 40 | 62.50 | 8.75 / 1,428.86 / 2,678.84 | 0.01 / 1.37 / 1.78 | 0.00 / 285.30 / 942.17 | 1,947.50 / 4,570.15 / 4,933.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 52 | 1.92 | 0.00 / 0.00 / 4.76 | 0.00 / 0.00 / 0.03 | 0.00 / 0.00 / 5.91 | 1,174.50 / 2,705.50 / 3,089.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | 1000 m | 52 | 13.46 | 0.00 / 11.85 / 74.89 | 0.00 / 0.05 / 0.45 | 0.00 / 5.90 / 24.96 | 1,186.50 / 2,612.80 / 2,940.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | 1000 m | 52 | 3.85 | 0.00 / 0.00 / 826.34 | 0.00 / 0.00 / 0.92 | 0.00 / 0.00 / 24.87 | 339.50 / 1,037.65 / 1,178.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | 1000 m | 52 | 9.62 | 0.00 / 42.92 / 738.33 | 0.00 / 0.06 / 0.75 | 0.00 / 10.21 / 96.82 | 795.50 / 1,218.30 / 1,367.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | d + 50 m | 40 | 25.00 | 0.00 / 413.23 / 1,037.01 | 0.00 / 1.14 / 7.17 | 0.00 / 1.78 / 1,123.34 | 280.00 / 521.75 / 693.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | d + 50 m | 40 | 37.50 | 0.00 / 49.67 / 126.47 | 0.00 / 1.91 / 3.30 | 0.00 / 12.20 / 131.33 | 269.50 / 519.05 / 718.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | d + 50 m | 40 | 65.00 | 270.09 / 2,738.74 / 3,200.19 | 0.32 / 5.62 / 11.94 | 0.00 / 713.30 / 17,355.57 | 122.50 / 315.10 / 319.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | d + 50 m | 40 | 72.50 | 128.09 / 3,109.70 / 3,467.80 | 0.22 / 7.49 / 20.06 | 0.00 / 770.59 / 5,882.72 | 256.50 / 401.85 / 443.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 40 | 22.50 | 0.00 / 514.66 / 1,095.74 | 0.00 / 0.73 / 1.29 | 0.00 / 38.15 / 130.93 | 2,435.00 / 5,058.95 / 5,227.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | d + 50 m | 40 | 40.00 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 48.79 / 10,588.97 | 2,689.50 / 5,220.65 / 5,357.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | d + 50 m | 40 | 57.50 | 28.84 / 1,263.08 / 9,020.27 | 0.02 / 0.68 / 6.65 | 0.00 / 151.33 / 2,060.39 | 1,009.50 / 2,670.80 / 3,085.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | d + 50 m | 40 | 72.50 | 29.77 / 1,428.86 / 2,678.84 | 0.04 / 1.37 / 1.78 | 0.00 / 285.30 / 942.17 | 1,937.50 / 4,520.65 / 5,589.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 52 | 11.54 | 0.00 / 17.08 / 311.28 | 0.00 / 0.08 / 1.48 | 0.00 / 180.86 / 3,767.81 | 1,150.50 / 2,669.05 / 2,891.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | d + 50 m | 52 | 28.85 | 0.00 / 110.90 / 826.19 | 0.00 / 0.40 / 4.96 | 0.00 / 23.95 / 172.03 | 1,107.50 / 2,603.90 / 2,872.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | d + 50 m | 52 | 17.31 | 0.00 / 254.98 / 826.34 | 0.00 / 0.52 / 1.27 | 0.00 / 2.77 / 35.31 | 359.00 / 1,001.55 / 1,097.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | d + 50 m | 52 | 38.46 | 0.00 / 228.59 / 738.33 | 0.00 / 0.30 / 2.92 | 0.00 / 75.39 / 239.00 | 776.00 / 1,148.35 / 1,472.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | d + 100 m | 40 | 25.00 | 0.00 / 413.23 / 1,037.01 | 0.00 / 1.14 / 7.17 | 0.00 / 1.78 / 1,123.34 | 284.00 / 502.65 / 747.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | d + 100 m | 40 | 30.00 | 0.00 / 37.16 / 126.47 | 0.00 / 0.80 / 2.52 | 0.00 / 7.49 / 25.33 | 285.50 / 530.25 / 768.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | d + 100 m | 40 | 60.00 | 206.79 / 2,738.74 / 3,200.19 | 0.25 / 5.62 / 11.94 | 0.00 / 713.30 / 17,355.57 | 123.50 / 293.95 / 354.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | d + 100 m | 40 | 72.50 | 128.09 / 3,093.91 / 3,467.80 | 0.22 / 7.48 / 20.06 | 0.00 / 770.59 / 5,882.72 | 284.50 / 397.25 / 473.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 40 | 20.00 | 0.00 / 514.66 / 1,095.74 | 0.00 / 0.73 / 1.29 | 0.00 / 38.15 / 130.93 | 2,405.00 / 4,900.90 / 5,142.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | d + 100 m | 40 | 37.50 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 48.79 / 10,588.97 | 2,663.50 / 5,305.30 / 5,426.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | d + 100 m | 40 | 55.00 | 11.96 / 1,199.40 / 9,020.27 | 0.01 / 0.49 / 6.65 | 0.00 / 151.33 / 2,060.39 | 1,000.50 / 2,612.05 / 3,128.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | d + 100 m | 40 | 70.00 | 14.63 / 1,179.07 / 2,678.84 | 0.02 / 0.82 / 1.78 | 0.00 / 285.30 / 942.17 | 1,985.00 / 4,485.00 / 5,649.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 52 | 9.62 | 0.00 / 12.69 / 311.28 | 0.00 / 0.05 / 1.48 | 0.00 / 3.75 / 3,767.81 | 1,229.00 / 2,735.05 / 2,882.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | d + 100 m | 52 | 23.08 | 0.00 / 15.02 / 826.19 | 0.00 / 0.06 / 4.96 | 0.00 / 5.90 / 31.64 | 1,138.50 / 2,621.30 / 2,760.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | d + 100 m | 52 | 11.54 | 0.00 / 163.38 / 783.43 | 0.00 / 0.28 / 0.92 | 0.00 / 0.00 / 242.68 | 346.50 / 940.70 / 1,152.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | d + 100 m | 52 | 23.08 | 0.00 / 165.70 / 587.22 | 0.00 / 0.22 / 2.92 | 0.00 / 12.72 / 160.12 | 807.50 / 1,105.70 / 1,481.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | d + 250 m | 40 | 22.50 | 0.00 / 413.23 / 1,037.01 | 0.00 / 1.14 / 7.17 | 0.00 / 0.06 / 11.51 | 281.00 / 503.25 / 716.00 | 276.00 / 508.05 / 688.00 |
| abisko | kayak | d + 250 m | 40 | 25.00 | 0.00 / 37.16 / 126.47 | 0.00 / 0.80 / 2.52 | 0.00 / 6.40 / 11.51 | 298.00 / 509.00 / 726.00 | 275.50 / 486.55 / 672.00 |
| abisko | paths | d + 250 m | 40 | 52.50 | 56.45 / 2,250.29 / 2,749.77 | 0.11 / 1.91 / 5.50 | 0.00 / 712.79 / 17,370.69 | 137.00 / 302.35 / 334.00 | 278.00 / 943.25 / 968.00 |
| abisko | walking | d + 250 m | 40 | 70.00 | 116.06 / 2,507.21 / 3,467.80 | 0.14 / 2.70 / 11.57 | 0.00 / 562.39 / 5,874.41 | 279.50 / 405.40 / 450.00 | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 40 | 20.00 | 0.00 / 514.66 / 1,095.74 | 0.00 / 0.73 / 1.29 | 0.00 / 38.15 / 130.93 | 2,442.50 / 5,224.45 / 5,333.00 | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | d + 250 m | 40 | 32.50 | 0.00 / 667.51 / 859.71 | 0.00 / 0.84 / 1.58 | 0.00 / 48.79 / 10,588.97 | 2,735.50 / 5,193.85 / 5,502.00 | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | d + 250 m | 40 | 55.00 | 11.96 / 1,199.40 / 9,020.27 | 0.01 / 0.49 / 6.65 | 0.00 / 151.33 / 2,060.39 | 999.00 / 2,755.30 / 3,305.00 | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | d + 250 m | 40 | 65.00 | 9.46 / 1,179.07 / 2,678.84 | 0.01 / 0.82 / 1.78 | 0.00 / 285.30 / 942.17 | 1,857.00 / 4,516.25 / 5,330.00 | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 52 | 5.77 | 0.00 / 2.14 / 123.85 | 0.00 / 0.01 / 0.45 | 0.00 / 0.89 / 3,767.81 | 1,186.00 / 2,725.00 / 3,060.00 | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | d + 250 m | 52 | 17.31 | 0.00 / 15.02 / 125.05 | 0.00 / 0.06 / 0.45 | 0.00 / 5.90 / 24.96 | 1,207.00 / 2,581.15 / 2,881.00 | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | d + 250 m | 52 | 5.77 | 0.00 / 30.18 / 783.43 | 0.00 / 0.11 / 0.92 | 0.00 / 0.00 / 24.87 | 353.00 / 1,004.25 / 1,065.00 | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | d + 250 m | 52 | 13.46 | 0.00 / 89.64 / 208.31 | 0.00 / 0.13 / 0.27 | 0.00 / 6.14 / 25.99 | 780.00 / 1,141.50 / 1,158.00 | 1,695.00 / 3,016.00 / 3,465.00 |
| abisko | kayak-paths | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 276.00 / 508.05 / 688.00 |
| abisko | kayak | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 275.50 / 486.55 / 672.00 |
| abisko | paths | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 278.00 / 943.25 / 968.00 |
| abisko | walking | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 663.50 / 1,553.05 / 1,790.00 |
| lomsdal-visten | kayak-paths | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,408.00 / 4,615.60 / 4,847.00 |
| lomsdal-visten | kayak | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,584.00 / 4,895.15 / 5,010.00 |
| lomsdal-visten | paths | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,458.00 / 5,137.80 / 6,054.00 |
| lomsdal-visten | walking | Unlimited | 40 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 4,032.50 / 13,155.55 / 14,122.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 52 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,113.00 / 2,698.00 / 3,069.00 |
| malingsbo-kloten | kayak | Unlimited | 52 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,108.00 / 2,496.25 / 2,832.00 |
| malingsbo-kloten | paths | Unlimited | 52 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 635.50 / 2,746.05 / 3,150.00 |
| malingsbo-kloten | walking | Unlimited | 52 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,695.00 / 3,016.00 / 3,465.00 |

### By requested offset bin

<details>
<summary>8 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 100.00 | 9.44 / 348.55 / 384.43 | 1.06 / 7.09 / 7.90 | 0.00 / 2.51 / 3.05 | 78.00 / 421.00 / 457.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | 0 | 5 | 80.00 | 3.93 / 39.46 / 42.24 | 0.16 / 1.93 / 2.09 | 0.00 / 1.96 / 1.97 | 78.00 / 443.40 / 485.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | 0 | 5 | 100.00 | 329.13 / 2,730.75 / 3,257.73 | 0.36 / 9.86 / 12.15 | -5.45 / 139.16 / 173.17 | 143.00 / 269.80 / 279.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | 0 | 5 | 100.00 | 125.61 / 350.99 / 406.90 | 0.09 / 1.45 / 1.74 | -91.07 / 140.84 / 174.86 | 232.00 / 383.80 / 385.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 100.00 | 4.58 / 24.87 / 29.86 | 0.02 / 0.08 / 0.09 | 3.82 / 8.33 / 8.98 | 2,718.00 / 3,916.40 / 4,071.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | 0 | 5 | 100.00 | 3.34 / 556.33 / 694.14 | 0.06 / 0.60 / 0.73 | 4.85 / 8,471.25 / 10,587.70 | 2,739.00 / 4,102.20 / 4,283.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | 0 | 5 | 100.00 | 29.86 / 1,563.03 / 1,758.23 | 0.05 / 0.82 / 0.91 | 5.29 / 10.37 / 10.71 | 969.00 / 1,794.80 / 1,951.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | 0 | 5 | 100.00 | 19.23 / 1,538.35 / 1,868.45 | 0.08 / 1.12 / 1.35 | 4.85 / 238.97 / 263.03 | 2,355.00 / 3,131.80 / 3,235.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 100.00 | 10.77 / 329.80 / 378.96 | 0.71 / 2.08 / 2.36 | -2.85 / 58.83 / 74.14 | 982.00 / 1,289.40 / 1,327.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | 0 | 5 | 20.00 | 0.00 / 104.94 / 131.18 | 0.00 / 1.04 / 1.30 | 0.00 / 0.00 / 0.00 | 846.00 / 1,283.00 / 1,320.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | 0 | 5 | 100.00 | 51.16 / 296.76 / 297.14 | 0.26 / 1.50 / 1.55 | -2.45 / 26.54 / 32.46 | 177.00 / 323.40 / 328.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | 0 | 5 | 100.00 | 57.61 / 548.05 / 587.72 | 0.37 / 2.75 / 2.92 | 4.40 / 9.33 / 9.69 | 225.00 / 703.40 / 706.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | 50 m | 5 | 20.00 | 0.00 / 200.96 / 251.20 | 0.00 / 0.56 / 0.69 | 0.00 / 0.00 / 0.00 | 94.00 / 425.40 / 464.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | 50 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 71.00 / 457.00 / 493.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | 50 m | 5 | 80.00 | 195.91 / 2,684.56 / 3,200.19 | 0.36 / 9.63 / 11.94 | 0.00 / 139.30 / 174.12 | 132.00 / 273.00 / 287.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | 50 m | 5 | 80.00 | 100.21 / 339.70 / 392.79 | 0.06 / 1.41 / 1.68 | -91.07 / 139.30 / 174.12 | 236.00 / 381.80 / 391.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,761.00 / 3,964.40 / 4,107.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | 50 m | 5 | 60.00 | 0.00 / 552.25 / 689.66 | 0.00 / 0.59 / 0.73 | 0.00 / 8,471.59 / 10,588.97 | 2,870.00 / 4,147.00 / 4,334.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | 50 m | 5 | 60.00 | 16.86 / 1,562.91 / 1,758.23 | 0.04 / 0.82 / 0.91 | 0.00 / 5.90 / 6.13 | 944.00 / 1,751.60 / 1,892.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | 50 m | 5 | 100.00 | 19.23 / 1,537.46 / 1,868.45 | 0.04 / 1.12 / 1.35 | 5.00 / 239.99 / 264.31 | 2,471.00 / 3,068.40 / 3,109.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 20.00 | 0.00 / 91.77 / 114.71 | 0.00 / 0.49 / 0.61 | 0.00 / 0.00 / 0.00 | 906.00 / 1,303.40 / 1,352.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 872.00 / 1,330.40 / 1,361.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | 50 m | 5 | 60.00 | 5.54 / 236.34 / 284.43 | 0.02 / 1.06 / 1.27 | 1.52 / 29.48 / 35.31 | 169.00 / 335.00 / 354.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | 50 m | 5 | 60.00 | 1.31 / 547.65 / 587.22 | 0.00 / 2.75 / 2.92 | 5.40 / 9.61 / 9.69 | 208.00 / 630.20 / 633.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | 100 m | 5 | 20.00 | 0.00 / 200.96 / 251.20 | 0.00 / 0.56 / 0.69 | 0.00 / 0.00 / 0.00 | 86.00 / 415.80 / 445.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | 100 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 83.00 / 444.80 / 482.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | 100 m | 5 | 80.00 | 195.91 / 2,684.56 / 3,200.19 | 0.36 / 9.63 / 11.94 | 0.00 / 139.30 / 174.12 | 152.00 / 272.80 / 287.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | 100 m | 5 | 80.00 | 100.21 / 339.70 / 392.79 | 0.06 / 1.41 / 1.68 | -91.07 / 139.30 / 174.12 | 225.00 / 387.80 / 399.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,631.00 / 3,892.80 / 4,041.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | 100 m | 5 | 60.00 | 0.00 / 552.25 / 689.66 | 0.00 / 0.59 / 0.73 | 0.00 / 8,471.59 / 10,588.97 | 3,222.00 / 4,108.20 / 4,300.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | 100 m | 5 | 60.00 | 16.86 / 1,562.91 / 1,758.23 | 0.04 / 0.82 / 0.91 | 0.00 / 5.90 / 6.13 | 961.00 / 1,822.60 / 1,925.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | 100 m | 5 | 100.00 | 19.23 / 1,537.46 / 1,868.45 | 0.04 / 1.12 / 1.35 | 5.00 / 239.99 / 264.31 | 2,200.00 / 2,969.80 / 3,034.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 20.00 | 0.00 / 91.77 / 114.71 | 0.00 / 0.49 / 0.61 | 0.00 / 0.00 / 0.00 | 868.00 / 1,279.00 / 1,313.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 868.00 / 1,279.20 / 1,299.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | 100 m | 5 | 60.00 | 5.54 / 236.34 / 284.43 | 0.02 / 1.06 / 1.27 | 1.52 / 29.48 / 35.31 | 174.00 / 318.60 / 333.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | 100 m | 5 | 60.00 | 1.31 / 547.65 / 587.22 | 0.00 / 2.75 / 2.92 | 5.40 / 9.61 / 9.69 | 198.00 / 668.00 / 672.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 200.96 / 251.20 | 0.00 / 0.56 / 0.69 | 0.00 / 0.00 / 0.00 | 76.00 / 415.60 / 452.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | 250 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 85.00 / 470.20 / 514.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | 250 m | 5 | 80.00 | 195.91 / 2,684.56 / 3,200.19 | 0.36 / 9.63 / 11.94 | 0.00 / 139.30 / 174.12 | 153.00 / 276.20 / 289.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | 250 m | 5 | 80.00 | 100.21 / 339.70 / 392.79 | 0.06 / 1.41 / 1.68 | -91.07 / 139.30 / 174.12 | 254.00 / 398.00 / 411.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,773.00 / 4,034.20 / 4,208.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | 250 m | 5 | 60.00 | 0.00 / 552.25 / 689.66 | 0.00 / 0.59 / 0.73 | 0.00 / 8,471.59 / 10,588.97 | 3,099.00 / 4,115.20 / 4,281.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | 250 m | 5 | 60.00 | 16.86 / 1,562.91 / 1,758.23 | 0.04 / 0.82 / 0.91 | 0.00 / 5.90 / 6.13 | 995.00 / 2,073.60 / 2,268.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | 250 m | 5 | 100.00 | 19.23 / 1,537.46 / 1,868.45 | 0.04 / 1.12 / 1.35 | 5.00 / 239.99 / 264.31 | 2,218.00 / 3,013.00 / 3,087.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 91.77 / 114.71 | 0.00 / 0.49 / 0.61 | 0.00 / 0.00 / 0.00 | 850.00 / 1,298.60 / 1,332.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 903.00 / 1,263.80 / 1,293.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | 250 m | 5 | 60.00 | 5.54 / 236.34 / 284.43 | 0.02 / 1.06 / 1.27 | 1.52 / 29.48 / 35.31 | 166.00 / 320.20 / 324.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | 250 m | 5 | 60.00 | 1.31 / 547.65 / 587.22 | 0.00 / 2.75 / 2.92 | 5.40 / 9.61 / 9.69 | 207.00 / 635.60 / 643.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 89.00 / 442.60 / 479.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | 500 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 93.00 / 446.80 / 486.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | 500 m | 5 | 40.00 | 0.00 / 497.90 / 622.04 | 0.00 / 0.29 / 0.36 | 0.00 / 139.30 / 174.12 | 165.00 / 260.20 / 268.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | 500 m | 5 | 80.00 | 87.85 / 121.74 / 127.12 | 0.06 / 0.25 / 0.30 | 0.00 / 144.90 / 174.12 | 271.00 / 408.00 / 421.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,720.00 / 3,871.80 / 4,021.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | 500 m | 5 | 60.00 | 0.00 / 552.25 / 689.66 | 0.00 / 0.59 / 0.73 | 0.00 / 8,471.59 / 10,588.97 | 3,292.00 / 4,093.20 / 4,253.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | 500 m | 5 | 60.00 | 16.86 / 1,562.91 / 1,758.23 | 0.04 / 0.82 / 0.91 | 0.00 / 5.90 / 6.13 | 968.00 / 2,078.80 / 2,288.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | 500 m | 5 | 100.00 | 19.23 / 1,537.46 / 1,868.45 | 0.04 / 1.12 / 1.35 | 5.00 / 239.99 / 264.31 | 2,180.00 / 3,060.80 / 3,090.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 856.00 / 1,328.80 / 1,354.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 872.00 / 1,302.60 / 1,317.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | 500 m | 5 | 20.00 | 0.00 / 227.54 / 284.43 | 0.00 / 1.01 / 1.27 | 0.00 / 28.25 / 35.31 | 186.00 / 328.20 / 330.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | 500 m | 5 | 20.00 | 0.00 / 469.78 / 587.22 | 0.00 / 2.33 / 2.92 | 0.00 / 4.32 / 5.40 | 202.00 / 656.00 / 667.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 94.00 / 444.80 / 483.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | 1000 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 95.00 / 450.20 / 488.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | 1000 m | 5 | 40.00 | 0.00 / 497.90 / 622.04 | 0.00 / 0.29 / 0.36 | 0.00 / 139.30 / 174.12 | 171.00 / 270.80 / 280.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | 1000 m | 5 | 60.00 | 87.85 / 121.74 / 127.12 | 0.06 / 0.25 / 0.30 | 0.00 / 139.30 / 174.12 | 237.00 / 377.80 / 378.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,814.00 / 3,811.60 / 3,935.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 40.00 | 0.00 / 551.73 / 689.66 | 0.00 / 0.58 / 0.73 | 0.00 / 8,471.18 / 10,588.97 | 2,951.00 / 4,145.00 / 4,269.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | 1000 m | 5 | 60.00 | 16.86 / 1,562.91 / 1,758.23 | 0.04 / 0.82 / 0.91 | 0.00 / 5.90 / 6.13 | 999.00 / 1,969.80 / 2,158.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | 1000 m | 5 | 80.00 | 19.23 / 1,537.46 / 1,868.45 | 0.02 / 1.12 / 1.35 | 5.00 / 239.99 / 264.31 | 2,305.00 / 3,085.00 / 3,158.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 897.00 / 1,381.00 / 1,419.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 860.00 / 1,335.60 / 1,358.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 189.00 / 340.60 / 351.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 219.00 / 686.80 / 687.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 72.00 / 429.40 / 464.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | d + 50 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 78.00 / 457.60 / 503.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | d + 50 m | 5 | 60.00 | 1.35 / 2,684.56 / 3,200.19 | 0.00 / 9.62 / 11.94 | 0.00 / 139.30 / 174.12 | 157.00 / 259.60 / 272.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | d + 50 m | 5 | 80.00 | 100.21 / 339.66 / 392.79 | 0.06 / 1.41 / 1.68 | -86.16 / 139.30 / 174.12 | 241.00 / 379.60 / 383.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,790.00 / 3,893.40 / 4,016.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 60.00 | 0.00 / 552.25 / 689.66 | 0.00 / 0.59 / 0.73 | 0.00 / 8,471.59 / 10,588.97 | 2,908.00 / 4,228.00 / 4,377.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 60.00 | 16.86 / 1,562.91 / 1,758.23 | 0.04 / 0.82 / 0.91 | 0.00 / 5.90 / 6.13 | 1,022.00 / 1,872.80 / 2,039.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 100.00 | 19.23 / 1,537.46 / 1,868.45 | 0.04 / 1.12 / 1.35 | 5.00 / 239.99 / 264.31 | 2,269.00 / 3,129.00 / 3,162.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 829.00 / 1,394.00 / 1,433.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 878.00 / 1,272.00 / 1,304.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 40.00 | 0.00 / 228.65 / 284.43 | 0.00 / 1.02 / 1.27 | 0.00 / 29.48 / 35.31 | 177.00 / 366.40 / 389.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 40.00 | 0.00 / 470.04 / 587.22 | 0.00 / 2.33 / 2.92 | 0.00 / 8.51 / 9.29 | 228.00 / 663.00 / 664.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 75.00 / 427.00 / 463.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | d + 100 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 69.00 / 441.40 / 478.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | d + 100 m | 5 | 60.00 | 1.35 / 2,684.56 / 3,200.19 | 0.00 / 9.62 / 11.94 | 0.00 / 139.30 / 174.12 | 131.00 / 267.60 / 276.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | d + 100 m | 5 | 80.00 | 100.21 / 339.66 / 392.79 | 0.06 / 1.41 / 1.68 | -86.16 / 139.30 / 174.12 | 232.00 / 385.40 / 387.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,736.00 / 4,073.80 / 4,214.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 60.00 | 0.00 / 552.25 / 689.66 | 0.00 / 0.59 / 0.73 | 0.00 / 8,471.59 / 10,588.97 | 2,953.00 / 4,156.80 / 4,312.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 60.00 | 16.86 / 735.06 / 781.64 | 0.04 / 0.41 / 0.44 | 0.00 / 5.90 / 6.13 | 1,000.00 / 1,830.80 / 1,990.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 100.00 | 11.44 / 174.65 / 213.50 | 0.02 / 0.15 / 0.18 | 2.06 / 212.44 / 264.31 | 2,288.00 / 3,018.40 / 3,068.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 890.00 / 1,411.00 / 1,422.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 850.00 / 1,305.40 / 1,338.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 20.00 | 0.00 / 108.46 / 135.57 | 0.00 / 0.48 / 0.60 | 0.00 / 194.15 / 242.68 | 210.00 / 339.20 / 352.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 20.00 | 0.00 / 469.78 / 587.22 | 0.00 / 2.33 / 2.92 | 0.00 / 4.32 / 5.40 | 201.00 / 650.00 / 653.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 76.00 / 424.20 / 454.00 | 75.00 / 422.80 / 454.00 |
| abisko | kayak | d + 250 m | 5 | 20.00 | 0.00 / 14.36 / 17.95 | 0.00 / 0.06 / 0.07 | 0.00 / 4.79 / 5.98 | 81.00 / 453.40 / 487.00 | 69.00 / 431.40 / 467.00 |
| abisko | paths | d + 250 m | 5 | 40.00 | 0.00 / 497.90 / 622.04 | 0.00 / 0.29 / 0.36 | 0.00 / 139.30 / 174.12 | 136.00 / 268.00 / 279.00 | 435.00 / 876.80 / 948.00 |
| abisko | walking | d + 250 m | 5 | 60.00 | 87.85 / 121.74 / 127.12 | 0.06 / 0.25 / 0.30 | 0.00 / 139.30 / 174.12 | 237.00 / 378.00 / 380.00 | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,800.00 / 4,063.00 / 4,161.00 | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 60.00 | 0.00 / 552.25 / 689.66 | 0.00 / 0.59 / 0.73 | 0.00 / 8,471.59 / 10,588.97 | 2,922.00 / 4,163.00 / 4,299.00 | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 60.00 | 16.86 / 735.06 / 781.64 | 0.04 / 0.41 / 0.44 | 0.00 / 5.90 / 6.13 | 989.00 / 1,847.40 / 2,005.00 | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 80.00 | 7.63 / 174.65 / 213.50 | 0.02 / 0.15 / 0.18 | 2.06 / 212.44 / 264.31 | 2,350.00 / 3,115.40 / 3,200.00 | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 886.00 / 1,302.60 / 1,326.00 | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 854.00 / 1,287.60 / 1,306.00 | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 195.00 / 353.40 / 366.00 | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 223.00 / 688.20 / 696.00 | 349.00 / 1,392.40 / 1,398.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 75.00 / 422.80 / 454.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 69.00 / 431.40 / 467.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 435.00 / 876.80 / 948.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 574.00 / 1,572.80 / 1,630.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,623.00 / 3,741.80 / 3,846.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,895.00 / 4,082.80 / 4,194.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,502.00 / 4,236.60 / 4,565.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 6,509.00 / 7,694.80 / 7,697.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 971.00 / 1,228.20 / 1,252.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 832.00 / 1,329.40 / 1,369.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 243.00 / 639.00 / 671.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 349.00 / 1,392.40 / 1,398.00 |

</details>

<details>
<summary>20 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 80.00 | 6.79 / 171.86 / 184.68 | 1.09 / 1.68 / 1.76 | 2.88 / 70.62 / 86.32 | 448.00 / 460.80 / 463.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | 0 | 5 | 40.00 | 0.00 / 27.72 / 34.52 | 0.00 / 0.61 / 0.75 | 0.00 / 9.21 / 11.51 | 453.00 / 504.40 / 515.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | 0 | 5 | 100.00 | 478.27 / 2,345.84 / 2,756.55 | 0.43 / 1.54 / 1.55 | -0.73 / 118.23 / 125.46 | 174.00 / 290.20 / 300.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | 0 | 5 | 100.00 | 171.82 / 871.40 / 898.69 | 0.10 / 2.02 / 2.12 | 0.01 / 128.88 / 139.24 | 327.00 / 368.40 / 378.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 100.00 | 31.22 / 539.64 / 651.57 | 0.03 / 1.35 / 1.64 | 34.15 / 87.26 / 97.39 | 4,483.00 / 4,740.40 / 4,766.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | 0 | 5 | 100.00 | 8.74 / 260.66 / 321.55 | 0.02 / 0.66 / 0.82 | -6.33 / 1.03 / 1.28 | 4,793.00 / 5,056.00 / 5,092.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | 0 | 5 | 100.00 | 779.01 / 7,574.18 / 9,158.47 | 0.33 / 5.50 / 6.75 | -0.18 / 1,658.40 / 2,072.06 | 1,552.00 / 2,344.60 / 2,526.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | 0 | 5 | 100.00 | 756.27 / 1,366.06 / 1,405.75 | 0.48 / 1.58 / 1.84 | 0.18 / 226.47 / 249.10 | 2,006.00 / 4,650.40 / 5,157.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 100.00 | 81.21 / 546.70 / 640.19 | 0.63 / 2.51 / 2.97 | -14.24 / 1.27 / 2.39 | 1,588.00 / 2,084.60 / 2,115.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | 0 | 5 | 100.00 | 13.08 / 93.59 / 113.23 | 0.05 / 0.50 / 0.60 | -2.27 / 13.29 / 16.50 | 1,483.00 / 2,137.40 / 2,190.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | 0 | 5 | 100.00 | 188.60 / 989.61 / 1,168.90 | 0.44 / 1.40 / 1.62 | 21.56 / 137.39 / 157.37 | 466.00 / 792.20 / 816.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | 0 | 5 | 100.00 | 13.08 / 673.69 / 815.42 | 0.03 / 0.97 / 1.14 | -0.19 / 14.83 / 16.50 | 971.00 / 1,125.80 / 1,133.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | 50 m | 5 | 20.00 | 0.00 / 92.06 / 115.08 | 0.00 / 0.83 / 1.04 | 0.00 / 9.21 / 11.51 | 429.00 / 450.60 / 452.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | 50 m | 5 | 20.00 | 0.00 / 27.62 / 34.52 | 0.00 / 0.60 / 0.75 | 0.00 / 9.21 / 11.51 | 426.00 / 471.00 / 480.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | 50 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 191.00 / 301.20 / 309.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | 50 m | 5 | 80.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 129.53 / 139.48 | 316.00 / 405.20 / 424.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,560.00 / 4,673.60 / 4,683.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | 50 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,748.00 / 4,961.20 / 4,994.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | 50 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,524.00 / 2,271.60 / 2,451.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | 50 m | 5 | 100.00 | 756.05 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 226.22 / 249.10 | 2,052.00 / 4,541.00 / 4,986.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 60.00 | 2.17 / 100.88 / 115.22 | 0.01 / 0.40 / 0.47 | 0.00 / 6.62 / 8.28 | 1,565.00 / 2,109.00 / 2,146.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 40.00 | 0.00 / 10.56 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.22 / 17.66 | 1,504.00 / 2,120.80 / 2,171.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | 50 m | 5 | 100.00 | 172.27 / 465.96 / 528.71 | 0.35 / 0.68 / 0.73 | 24.76 / 129.45 / 145.98 | 451.00 / 824.00 / 851.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | 50 m | 5 | 60.00 | 12.85 / 580.10 / 702.19 | 0.03 / 0.83 / 0.98 | 2.08 / 17.61 / 17.66 | 894.00 / 1,192.00 / 1,211.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | 100 m | 5 | 20.00 | 0.00 / 92.06 / 115.08 | 0.00 / 0.83 / 1.04 | 0.00 / 9.21 / 11.51 | 430.00 / 448.00 / 450.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | 100 m | 5 | 20.00 | 0.00 / 27.62 / 34.52 | 0.00 / 0.60 / 0.75 | 0.00 / 9.21 / 11.51 | 437.00 / 464.40 / 466.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | 100 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 187.00 / 307.40 / 322.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | 100 m | 5 | 60.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 71.79 / 89.74 | 325.00 / 392.40 / 404.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,561.00 / 4,711.80 / 4,748.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | 100 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,800.00 / 4,942.60 / 4,955.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | 100 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,522.00 / 2,417.20 / 2,565.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | 100 m | 5 | 100.00 | 744.01 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 203.11 / 249.10 | 1,981.00 / 4,605.20 / 5,096.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 60.00 | 2.17 / 100.88 / 115.22 | 0.01 / 0.40 / 0.47 | 0.00 / 6.62 / 8.28 | 1,594.00 / 2,034.00 / 2,039.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 40.00 | 0.00 / 10.56 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.22 / 17.66 | 1,445.00 / 2,153.20 / 2,164.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | 100 m | 5 | 100.00 | 172.27 / 465.96 / 528.71 | 0.35 / 0.68 / 0.73 | 24.76 / 129.45 / 145.98 | 469.00 / 800.20 / 810.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | 100 m | 5 | 60.00 | 12.85 / 580.10 / 702.19 | 0.03 / 0.83 / 0.98 | 2.08 / 17.61 / 17.66 | 933.00 / 1,117.40 / 1,121.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 92.06 / 115.08 | 0.00 / 0.83 / 1.04 | 0.00 / 9.21 / 11.51 | 428.00 / 458.20 / 460.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | 250 m | 5 | 20.00 | 0.00 / 27.62 / 34.52 | 0.00 / 0.60 / 0.75 | 0.00 / 9.21 / 11.51 | 441.00 / 455.00 / 458.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | 250 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 220.00 / 314.20 / 331.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | 250 m | 5 | 60.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 71.79 / 89.74 | 333.00 / 350.80 / 351.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,581.00 / 4,806.00 / 4,836.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | 250 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,876.00 / 4,957.20 / 4,965.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | 250 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,452.00 / 2,439.40 / 2,624.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | 250 m | 5 | 100.00 | 744.01 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 203.11 / 249.10 | 2,071.00 / 4,742.80 / 5,244.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 92.61 / 115.22 | 0.00 / 0.38 / 0.47 | 0.00 / 6.62 / 8.28 | 1,621.00 / 2,135.60 / 2,150.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 40.00 | 0.00 / 10.56 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.22 / 17.66 | 1,489.00 / 2,270.20 / 2,320.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | 250 m | 5 | 80.00 | 172.27 / 465.96 / 528.71 | 0.35 / 0.68 / 0.73 | 24.76 / 129.45 / 145.98 | 547.00 / 787.80 / 803.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | 250 m | 5 | 60.00 | 12.85 / 580.10 / 702.19 | 0.03 / 0.83 / 0.98 | 2.08 / 17.61 / 17.66 | 880.00 / 1,132.20 / 1,143.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 92.06 / 115.08 | 0.00 / 0.83 / 1.04 | 0.00 / 9.21 / 11.51 | 459.00 / 489.60 / 496.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | 500 m | 5 | 20.00 | 0.00 / 27.62 / 34.52 | 0.00 / 0.60 / 0.75 | 0.00 / 9.21 / 11.51 | 450.00 / 460.00 / 461.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | 500 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 206.00 / 328.60 / 344.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | 500 m | 5 | 60.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 71.79 / 89.74 | 346.00 / 380.60 / 387.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,582.00 / 4,779.60 / 4,790.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | 500 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,764.00 / 4,955.80 / 4,981.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | 500 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,648.00 / 2,350.60 / 2,517.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | 500 m | 5 | 100.00 | 744.01 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 203.11 / 249.10 | 2,025.00 / 4,766.80 / 5,273.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,716.00 / 2,187.00 / 2,214.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 40.00 | 0.00 / 10.56 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.22 / 17.66 | 1,506.00 / 2,202.40 / 2,250.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | 500 m | 5 | 40.00 | 0.00 / 431.10 / 528.71 | 0.00 / 0.61 / 0.73 | 0.00 / 23.30 / 24.76 | 545.00 / 800.20 / 815.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | 500 m | 5 | 60.00 | 12.85 / 580.10 / 702.19 | 0.03 / 0.83 / 0.98 | 2.08 / 17.61 / 17.66 | 853.00 / 1,135.00 / 1,152.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 458.00 / 505.00 / 516.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 420.00 / 470.40 / 475.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | 1000 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 216.00 / 333.80 / 353.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | 1000 m | 5 | 60.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 71.79 / 89.74 | 397.00 / 415.80 / 417.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,652.00 / 4,679.80 / 4,686.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,818.00 / 5,168.40 / 5,182.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | 1000 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,534.00 / 2,488.60 / 2,663.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | 1000 m | 5 | 100.00 | 744.01 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 203.11 / 249.10 | 2,074.00 / 4,496.60 / 4,915.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,590.00 / 2,102.40 / 2,107.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 40.00 | 0.00 / 10.30 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.13 / 17.66 | 1,593.00 / 2,102.20 / 2,120.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 511.00 / 812.60 / 827.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 20.00 | 0.00 / 10.28 / 12.85 | 0.00 / 0.02 / 0.03 | 0.00 / 14.12 / 17.66 | 854.00 / 1,165.00 / 1,168.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 92.06 / 115.08 | 0.00 / 0.83 / 1.04 | 0.00 / 9.21 / 11.51 | 420.00 / 465.00 / 468.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | d + 50 m | 5 | 20.00 | 0.00 / 27.62 / 34.52 | 0.00 / 0.60 / 0.75 | 0.00 / 9.21 / 11.51 | 429.00 / 463.00 / 466.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | d + 50 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 188.00 / 303.60 / 319.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | d + 50 m | 5 | 60.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 71.79 / 89.74 | 307.00 / 369.40 / 381.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,512.00 / 4,965.00 / 5,051.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,860.00 / 5,311.00 / 5,357.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,561.00 / 2,754.60 / 3,028.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 100.00 | 756.05 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 226.22 / 249.10 | 2,153.00 / 5,044.40 / 5,589.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,595.00 / 2,075.80 / 2,079.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 10.56 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.22 / 17.66 | 1,523.00 / 2,128.40 / 2,172.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 540.00 / 775.80 / 790.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 40.00 | 0.00 / 75.94 / 91.72 | 0.00 / 0.19 / 0.23 | 0.00 / 14.54 / 17.66 | 854.00 / 1,092.80 / 1,108.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 92.06 / 115.08 | 0.00 / 0.83 / 1.04 | 0.00 / 9.21 / 11.51 | 430.00 / 465.40 / 471.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | d + 100 m | 5 | 20.00 | 0.00 / 27.62 / 34.52 | 0.00 / 0.60 / 0.75 | 0.00 / 9.21 / 11.51 | 458.00 / 488.20 / 489.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | d + 100 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 198.00 / 297.00 / 312.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | d + 100 m | 5 | 60.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 71.79 / 89.74 | 303.00 / 381.40 / 395.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,522.00 / 4,850.40 / 4,893.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,877.00 / 5,324.20 / 5,426.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,527.00 / 2,628.00 / 2,860.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 100.00 | 744.01 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 203.11 / 249.10 | 2,170.00 / 5,037.40 / 5,649.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,536.00 / 2,216.80 / 2,250.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 10.56 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.22 / 17.66 | 1,507.00 / 2,087.00 / 2,114.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 492.00 / 762.60 / 772.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 20.00 | 0.00 / 10.28 / 12.85 | 0.00 / 0.02 / 0.03 | 0.00 / 14.12 / 17.66 | 899.00 / 1,080.20 / 1,090.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 92.06 / 115.08 | 0.00 / 0.83 / 1.04 | 0.00 / 9.21 / 11.51 | 434.00 / 459.40 / 463.00 | 418.00 / 443.20 / 444.00 |
| abisko | kayak | d + 250 m | 5 | 20.00 | 0.00 / 27.62 / 34.52 | 0.00 / 0.60 / 0.75 | 0.00 / 9.21 / 11.51 | 435.00 / 464.20 / 468.00 | 439.00 / 462.40 / 465.00 |
| abisko | paths | d + 250 m | 5 | 60.00 | 476.97 / 2,318.10 / 2,749.77 | 0.43 / 1.49 / 1.54 | 0.00 / 116.06 / 122.59 | 186.00 / 299.40 / 309.00 | 439.00 / 877.00 / 968.00 |
| abisko | walking | d + 250 m | 5 | 60.00 | 171.82 / 870.74 / 898.55 | 0.10 / 2.01 / 2.11 | 0.00 / 71.79 / 89.74 | 302.00 / 384.60 / 395.00 | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 40.00 | 0.00 / 429.08 / 513.37 | 0.00 / 1.07 / 1.29 | 0.00 / 84.92 / 97.39 | 4,520.00 / 5,174.20 / 5,271.00 | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 20.00 | 0.00 / 257.24 / 321.55 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 4,819.00 / 5,400.40 / 5,502.00 | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 80.00 | 773.31 / 7,463.62 / 9,020.27 | 0.33 / 5.42 / 6.65 | 0.00 / 1,651.21 / 2,060.39 | 1,572.00 / 2,659.80 / 2,894.00 | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 100.00 | 744.01 / 1,358.01 / 1,405.73 | 0.48 / 1.53 / 1.78 | -0.18 / 203.11 / 249.10 | 2,138.00 / 4,796.80 / 5,330.00 | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,579.00 / 2,052.20 / 2,060.00 | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 40.00 | 0.00 / 10.56 / 12.85 | 0.00 / 0.03 / 0.04 | 0.00 / 14.22 / 17.66 | 1,520.00 / 2,130.80 / 2,163.00 | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 449.00 / 772.60 / 789.00 | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 20.00 | 0.00 / 10.28 / 12.85 | 0.00 / 0.02 / 0.03 | 0.00 / 14.12 / 17.66 | 923.00 / 1,139.00 / 1,149.00 | 2,051.00 / 2,902.40 / 2,903.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 418.00 / 443.20 / 444.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 439.00 / 462.40 / 465.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 439.00 / 877.00 / 968.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 813.00 / 1,413.40 / 1,469.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 4,522.00 / 4,641.00 / 4,665.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 4,688.00 / 4,908.80 / 4,955.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 3,145.00 / 5,624.20 / 6,054.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 4,971.00 / 12,835.20 / 14,122.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,576.00 / 2,063.80 / 2,068.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,488.00 / 2,081.80 / 2,110.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,118.00 / 1,845.20 / 1,879.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,051.00 / 2,902.40 / 2,903.00 |

</details>

<details>
<summary>50 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 100.00 | 20.87 / 46.25 / 51.80 | 0.16 / 1.66 / 2.01 | 2.24 / 30.62 / 37.67 | 245.00 / 446.40 / 473.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | 0 | 5 | 100.00 | 11.08 / 17.69 / 19.06 | 0.13 / 1.54 / 1.89 | 1.32 / 5.56 / 6.35 | 248.00 / 457.20 / 481.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | 0 | 5 | 100.00 | 210.91 / 1,111.60 / 1,304.23 | 0.55 / 1.50 / 1.72 | 14.68 / 180.94 / 217.15 | 91.00 / 156.40 / 163.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | 0 | 5 | 100.00 | 51.94 / 139.46 / 140.15 | 0.16 / 0.48 / 0.52 | -1.01 / 370.58 / 449.61 | 169.00 / 250.80 / 264.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 60.00 | 0.22 / 164.57 / 201.98 | 0.00 / 5.77 / 7.21 | 1.34 / 50.79 / 62.15 | 1,565.00 / 2,767.20 / 2,822.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | 0 | 5 | 100.00 | 8.65 / 543.54 / 666.35 | 0.12 / 1.89 / 1.97 | 1.84 / 19.50 / 21.97 | 1,548.00 / 2,748.80 / 2,750.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | 0 | 5 | 100.00 | 138.52 / 854.69 / 1,008.75 | 0.18 / 0.35 / 0.37 | -0.01 / 121.17 / 151.12 | 916.00 / 1,768.80 / 1,907.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | 0 | 5 | 80.00 | 41.63 / 589.40 / 596.44 | 0.05 / 0.73 / 0.77 | 0.00 / 133.85 / 165.21 | 1,750.00 / 2,994.00 / 3,269.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 60.00 | 16.16 / 265.64 / 308.98 | 0.05 / 3.82 / 4.64 | 12.80 / 24.09 / 24.73 | 1,133.00 / 2,349.40 / 2,515.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | 0 | 5 | 60.00 | 0.01 / 73.88 / 83.80 | 0.00 / 1.14 / 1.35 | 0.00 / 18.70 / 23.00 | 1,066.00 / 2,383.20 / 2,567.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | 0 | 5 | 80.00 | 25.17 / 500.79 / 601.25 | 0.05 / 1.76 / 2.10 | 12.80 / 47.82 / 48.12 | 193.00 / 771.00 / 823.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | 0 | 5 | 100.00 | 30.15 / 316.55 / 370.96 | 0.06 / 1.14 / 1.31 | 2.43 / 45.84 / 49.55 | 194.00 / 983.40 / 987.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | 50 m | 5 | 60.00 | 0.39 / 10.31 / 11.22 | 0.00 / 0.57 / 0.70 | 0.00 / 37.21 / 46.50 | 232.00 / 448.40 / 477.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | 50 m | 5 | 80.00 | 7.03 / 17.47 / 19.06 | 0.06 / 1.54 / 1.89 | 0.57 / 5.62 / 6.35 | 262.00 / 432.40 / 450.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | 50 m | 5 | 80.00 | 195.30 / 1,067.65 / 1,252.43 | 0.51 / 1.44 / 1.65 | 8.45 / 194.18 / 231.49 | 86.00 / 136.40 / 137.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | 50 m | 5 | 60.00 | 43.46 / 139.46 / 140.15 | 0.14 / 0.48 / 0.52 | 0.00 / 369.80 / 449.61 | 176.00 / 236.40 / 248.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,468.00 / 2,855.60 / 2,922.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | 50 m | 5 | 60.00 | 3.39 / 534.81 / 666.35 | 0.03 / 1.29 / 1.58 | 0.00 / 19.50 / 21.97 | 1,590.00 / 2,854.40 / 2,875.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | 50 m | 5 | 80.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 120.27 / 149.78 | 909.00 / 1,739.80 / 1,878.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | 50 m | 5 | 80.00 | 40.32 / 589.40 / 596.44 | 0.04 / 0.73 / 0.77 | 2.24 / 133.85 / 165.21 | 1,850.00 / 3,174.60 / 3,479.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,041.00 / 2,461.00 / 2,657.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 20.00 | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 1.23 / 1.53 | 1,109.00 / 2,535.80 / 2,740.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | 50 m | 5 | 60.00 | 6.71 / 238.85 / 292.27 | 0.03 / 0.83 / 1.02 | 0.00 / 25.63 / 26.55 | 242.00 / 847.00 / 891.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | 50 m | 5 | 100.00 | 30.15 / 242.67 / 287.16 | 0.06 / 0.87 / 1.02 | 2.43 / 30.12 / 31.01 | 190.00 / 1,044.20 / 1,065.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | 100 m | 5 | 20.00 | 0.00 / 8.98 / 11.22 | 0.00 / 0.07 / 0.08 | 0.00 / 0.00 / 0.00 | 236.00 / 469.00 / 496.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | 100 m | 5 | 40.00 | 0.00 / 16.66 / 19.06 | 0.00 / 0.12 / 0.13 | 0.00 / 5.62 / 6.35 | 230.00 / 419.20 / 429.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | 100 m | 5 | 80.00 | 195.30 / 1,066.32 / 1,252.43 | 0.51 / 1.44 / 1.65 | 0.00 / 186.88 / 231.49 | 80.00 / 139.00 / 141.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | 100 m | 5 | 60.00 | 43.46 / 135.11 / 136.62 | 0.14 / 0.47 / 0.52 | 0.00 / 368.71 / 448.26 | 183.00 / 235.00 / 245.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,558.00 / 2,757.00 / 2,801.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | 100 m | 5 | 60.00 | 3.39 / 534.81 / 666.35 | 0.03 / 1.29 / 1.58 | 0.00 / 19.50 / 21.97 | 1,568.00 / 2,939.40 / 2,961.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | 100 m | 5 | 80.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 120.27 / 149.78 | 947.00 / 1,520.40 / 1,605.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | 100 m | 5 | 80.00 | 40.32 / 589.40 / 596.44 | 0.04 / 0.73 / 0.77 | 2.24 / 133.85 / 165.21 | 1,741.00 / 3,055.40 / 3,332.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,037.00 / 2,357.40 / 2,512.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 20.00 | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 1.23 / 1.53 | 1,103.00 / 2,412.00 / 2,606.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | 100 m | 5 | 60.00 | 6.71 / 238.66 / 292.27 | 0.03 / 0.83 / 1.02 | 0.00 / 25.63 / 26.55 | 203.00 / 868.40 / 945.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | 100 m | 5 | 60.00 | 23.05 / 242.67 / 287.16 | 0.05 / 0.87 / 1.02 | 0.00 / 24.96 / 26.55 | 201.00 / 976.00 / 984.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 261.00 / 473.00 / 504.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | 250 m | 5 | 40.00 | 0.00 / 16.66 / 19.06 | 0.00 / 0.12 / 0.13 | 0.00 / 5.62 / 6.35 | 236.00 / 430.60 / 432.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | 250 m | 5 | 60.00 | 195.30 / 1,066.32 / 1,252.43 | 0.51 / 1.44 / 1.65 | 0.00 / 185.20 / 231.49 | 88.00 / 141.40 / 144.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | 250 m | 5 | 60.00 | 43.46 / 135.11 / 136.62 | 0.14 / 0.47 / 0.52 | 0.00 / 368.71 / 448.26 | 178.00 / 235.80 / 248.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,530.00 / 2,786.00 / 2,806.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | 250 m | 5 | 60.00 | 0.76 / 533.75 / 666.35 | 0.00 / 1.29 / 1.58 | 0.00 / 18.98 / 21.97 | 1,518.00 / 2,920.20 / 2,960.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | 250 m | 5 | 80.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 120.27 / 149.78 | 952.00 / 1,529.40 / 1,609.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | 250 m | 5 | 80.00 | 40.32 / 589.40 / 596.44 | 0.04 / 0.73 / 0.77 | 2.24 / 133.85 / 165.21 | 1,704.00 / 3,139.40 / 3,419.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,113.00 / 2,401.20 / 2,558.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 20.00 | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 1.23 / 1.53 | 1,134.00 / 2,395.80 / 2,562.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | 250 m | 5 | 60.00 | 6.71 / 238.66 / 292.27 | 0.03 / 0.83 / 1.02 | 0.00 / 25.63 / 26.55 | 209.00 / 898.60 / 996.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | 250 m | 5 | 60.00 | 23.05 / 242.67 / 287.16 | 0.05 / 0.87 / 1.02 | 0.00 / 24.96 / 26.55 | 216.00 / 972.40 / 987.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 244.00 / 493.60 / 533.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | 500 m | 5 | 20.00 | 0.00 / 15.25 / 19.06 | 0.00 / 0.11 / 0.13 | 0.00 / 5.08 / 6.35 | 253.00 / 426.20 / 434.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | 500 m | 5 | 60.00 | 195.30 / 1,066.32 / 1,252.43 | 0.51 / 1.44 / 1.65 | 0.00 / 185.20 / 231.49 | 92.00 / 143.80 / 146.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | 500 m | 5 | 60.00 | 43.46 / 135.11 / 136.62 | 0.14 / 0.47 / 0.52 | 0.00 / 368.71 / 448.26 | 175.00 / 221.80 / 231.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,536.00 / 2,899.40 / 2,971.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | 500 m | 5 | 60.00 | 0.76 / 533.75 / 666.35 | 0.00 / 1.29 / 1.58 | 0.00 / 18.98 / 21.97 | 1,529.00 / 2,770.20 / 2,780.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | 500 m | 5 | 80.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 120.27 / 149.78 | 912.00 / 1,581.80 / 1,655.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | 500 m | 5 | 80.00 | 40.32 / 589.40 / 596.44 | 0.04 / 0.73 / 0.77 | 2.24 / 133.85 / 165.21 | 1,779.00 / 3,169.80 / 3,443.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,093.00 / 2,372.60 / 2,544.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 20.00 | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 1.23 / 1.53 | 1,125.00 / 2,392.80 / 2,572.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | 500 m | 5 | 20.00 | 0.00 / 233.81 / 292.27 | 0.00 / 0.82 / 1.02 | 0.00 / 21.24 / 26.55 | 224.00 / 828.00 / 906.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | 500 m | 5 | 20.00 | 0.00 / 229.73 / 287.16 | 0.00 / 0.81 / 1.02 | 0.00 / 21.24 / 26.55 | 198.00 / 992.00 / 1,017.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 240.00 / 481.80 / 513.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | 1000 m | 5 | 20.00 | 0.00 / 15.25 / 19.06 | 0.00 / 0.11 / 0.13 | 0.00 / 5.08 / 6.35 | 276.00 / 457.40 / 474.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | 1000 m | 5 | 40.00 | 0.00 / 1,066.32 / 1,252.43 | 0.00 / 1.44 / 1.65 | 0.00 / 185.20 / 231.49 | 105.00 / 158.60 / 161.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | 1000 m | 5 | 40.00 | 0.00 / 135.11 / 136.62 | 0.00 / 0.47 / 0.52 | 0.00 / 358.61 / 448.26 | 186.00 / 233.80 / 244.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,650.00 / 2,908.20 / 3,001.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 40.00 | 0.00 / 533.23 / 666.35 | 0.00 / 1.26 / 1.58 | 0.00 / 5.62 / 7.02 | 1,509.00 / 2,813.20 / 2,822.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | 1000 m | 5 | 80.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 120.27 / 149.78 | 924.00 / 1,611.40 / 1,692.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | 1000 m | 5 | 60.00 | 27.40 / 589.40 / 596.44 | 0.04 / 0.73 / 0.77 | 0.00 / 7.16 / 8.39 | 1,833.00 / 3,123.20 / 3,390.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,120.00 / 2,423.40 / 2,592.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,127.00 / 2,342.00 / 2,516.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 239.00 / 787.40 / 858.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 247.00 / 997.40 / 1,028.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 252.00 / 464.40 / 494.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | d + 50 m | 5 | 40.00 | 0.00 / 16.66 / 19.06 | 0.00 / 0.12 / 0.13 | 0.00 / 5.62 / 6.35 | 241.00 / 441.20 / 449.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | d + 50 m | 5 | 60.00 | 195.30 / 1,066.32 / 1,252.43 | 0.51 / 1.44 / 1.65 | 0.00 / 185.20 / 231.49 | 97.00 / 148.40 / 154.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | d + 50 m | 5 | 60.00 | 43.46 / 135.11 / 136.62 | 0.14 / 0.47 / 0.52 | 0.00 / 368.71 / 448.26 | 166.00 / 231.40 / 242.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,471.00 / 2,836.40 / 2,930.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 60.00 | 3.39 / 534.81 / 666.35 | 0.03 / 1.29 / 1.58 | 0.00 / 19.50 / 21.97 | 1,549.00 / 2,770.40 / 2,773.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 60.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 119.82 / 149.78 | 923.00 / 1,572.20 / 1,610.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 60.00 | 40.32 / 589.40 / 596.44 | 0.02 / 0.73 / 0.77 | 0.00 / 133.85 / 165.21 | 1,713.00 / 3,125.20 / 3,398.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,059.00 / 2,392.60 / 2,559.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 20.00 | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 1.23 / 1.53 | 1,071.00 / 2,296.40 / 2,459.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 201.00 / 788.80 / 839.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 20.00 | 0.00 / 51.79 / 64.74 | 0.00 / 0.24 / 0.30 | 0.00 / 0.00 / 0.00 | 206.00 / 961.20 / 985.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 264.00 / 443.40 / 470.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | d + 100 m | 5 | 20.00 | 0.00 / 15.25 / 19.06 | 0.00 / 0.11 / 0.13 | 0.00 / 5.08 / 6.35 | 256.00 / 417.80 / 425.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | d + 100 m | 5 | 60.00 | 195.30 / 1,066.32 / 1,252.43 | 0.51 / 1.44 / 1.65 | 0.00 / 185.20 / 231.49 | 87.00 / 135.60 / 138.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | d + 100 m | 5 | 60.00 | 43.46 / 135.11 / 136.62 | 0.14 / 0.47 / 0.52 | 0.00 / 368.71 / 448.26 | 156.00 / 265.40 / 283.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,487.00 / 2,891.00 / 3,009.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 60.00 | 3.39 / 534.81 / 666.35 | 0.03 / 1.29 / 1.58 | 0.00 / 19.50 / 21.97 | 1,604.00 / 2,789.80 / 2,792.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 60.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 119.82 / 149.78 | 898.00 / 1,536.00 / 1,606.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 60.00 | 40.32 / 589.40 / 596.44 | 0.02 / 0.73 / 0.77 | 0.00 / 133.85 / 165.21 | 1,866.00 / 3,178.00 / 3,469.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,130.00 / 2,532.80 / 2,762.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 20.00 | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 1.23 / 1.53 | 1,102.00 / 2,323.60 / 2,473.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 212.00 / 790.20 / 849.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 208.00 / 985.40 / 994.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 245.00 / 445.80 / 473.00 | 254.00 / 469.60 / 506.00 |
| abisko | kayak | d + 250 m | 5 | 20.00 | 0.00 / 15.25 / 19.06 | 0.00 / 0.11 / 0.13 | 0.00 / 5.08 / 6.35 | 257.00 / 431.20 / 448.00 | 243.00 / 431.80 / 453.00 |
| abisko | paths | d + 250 m | 5 | 60.00 | 195.30 / 1,066.32 / 1,252.43 | 0.51 / 1.44 / 1.65 | 0.00 / 185.20 / 231.49 | 91.00 / 160.20 / 165.00 | 133.00 / 301.20 / 303.00 |
| abisko | walking | d + 250 m | 5 | 60.00 | 43.46 / 135.11 / 136.62 | 0.14 / 0.47 / 0.52 | 0.00 / 368.71 / 448.26 | 165.00 / 244.00 / 248.00 | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,475.00 / 2,852.40 / 2,936.00 | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 60.00 | 0.76 / 533.75 / 666.35 | 0.00 / 1.29 / 1.58 | 0.00 / 18.98 / 21.97 | 1,550.00 / 2,756.40 / 2,763.00 | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 60.00 | 93.43 / 854.69 / 1,008.75 | 0.14 / 0.35 / 0.37 | 0.00 / 119.82 / 149.78 | 875.00 / 1,545.80 / 1,626.00 | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 60.00 | 40.32 / 589.40 / 596.44 | 0.02 / 0.73 / 0.77 | 0.00 / 133.85 / 165.21 | 1,796.00 / 3,268.80 / 3,580.00 | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,163.00 / 2,470.60 / 2,653.00 | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,200.00 / 2,366.20 / 2,524.00 | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 214.00 / 762.40 / 822.00 | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 225.00 / 989.40 / 990.00 | 309.00 / 2,485.60 / 2,579.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 254.00 / 469.60 / 506.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 243.00 / 431.80 / 453.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 133.00 / 301.20 / 303.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 434.00 / 572.00 / 598.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,468.00 / 2,754.00 / 2,811.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,528.00 / 2,716.20 / 2,727.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,430.00 / 3,901.20 / 4,255.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 3,805.00 / 9,994.40 / 10,993.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,093.00 / 2,289.40 / 2,462.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,045.00 / 2,229.60 / 2,378.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 295.00 / 1,807.00 / 1,977.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 309.00 / 2,485.60 / 2,579.00 |

</details>

<details>
<summary>100 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 100.00 | 22.54 / 356.96 / 384.56 | 0.81 / 1.74 / 1.81 | -1.28 / 20.34 / 23.12 | 171.00 / 229.00 / 240.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | 0 | 5 | 60.00 | 1.04 / 30.82 / 35.14 | 0.01 / 1.96 / 2.30 | 0.00 / 0.74 / 0.93 | 160.00 / 204.60 / 215.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | 0 | 5 | 100.00 | 203.14 / 1,059.12 / 1,262.25 | 0.22 / 1.53 / 1.84 | 9.24 / 90.32 / 99.55 | 54.00 / 205.60 / 225.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | 0 | 5 | 100.00 | 97.93 / 2,849.54 / 3,502.94 | 0.35 / 1.91 / 2.25 | -19.24 / 42.04 / 53.95 | 248.00 / 508.00 / 540.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 80.00 | 3.05 / 534.77 / 539.30 | 0.01 / 0.68 / 0.71 | 0.00 / 105.30 / 130.93 | 1,937.00 / 4,051.20 / 4,499.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | 0 | 5 | 80.00 | 0.35 / 116.55 / 135.97 | 0.00 / 0.42 / 0.51 | 0.00 / 1.57 / 1.93 | 2,008.00 / 4,596.00 / 5,107.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | 0 | 5 | 80.00 | 77.22 / 1,513.83 / 1,720.08 | 0.06 / 0.63 / 0.67 | -6.75 / 98.22 / 122.77 | 505.00 / 1,953.20 / 2,302.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | 0 | 5 | 80.00 | 75.48 / 2,219.06 / 2,692.61 | 0.09 / 1.46 / 1.71 | 52.89 / 642.32 / 770.23 | 1,634.00 / 2,664.60 / 2,708.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 80.00 | 58.33 / 132.67 / 136.51 | 0.50 / 0.57 / 0.57 | 14.79 / 3,022.63 / 3,769.08 | 1,634.00 / 2,262.20 / 2,320.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | 0 | 5 | 60.00 | 14.83 / 27.62 / 29.86 | 0.07 / 0.15 / 0.17 | 0.00 / 10.25 / 11.58 | 1,766.00 / 2,118.00 / 2,162.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | 0 | 5 | 100.00 | 117.33 / 353.56 / 379.60 | 0.28 / 0.61 / 0.68 | 1.26 / 33.52 / 36.82 | 484.00 / 1,035.60 / 1,078.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | 0 | 5 | 80.00 | 63.61 / 316.43 / 373.15 | 0.20 / 0.39 / 0.43 | 0.00 / 30.93 / 35.65 | 910.00 / 1,150.00 / 1,206.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | 50 m | 5 | 100.00 | 22.54 / 356.96 / 384.56 | 0.81 / 1.74 / 1.81 | -1.28 / 20.34 / 23.12 | 162.00 / 231.00 / 247.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | 50 m | 5 | 60.00 | 1.04 / 30.82 / 35.14 | 0.01 / 1.96 / 2.30 | 0.00 / 0.74 / 0.93 | 156.00 / 220.00 / 233.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | 50 m | 5 | 100.00 | 203.14 / 1,059.12 / 1,262.25 | 0.22 / 1.53 / 1.84 | 9.24 / 90.32 / 99.55 | 57.00 / 202.80 / 226.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | 50 m | 5 | 100.00 | 97.93 / 2,849.54 / 3,502.94 | 0.35 / 1.91 / 2.25 | -19.24 / 42.04 / 53.95 | 264.00 / 441.80 / 459.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 60.00 | 1.13 / 432.05 / 539.30 | 0.00 / 0.57 / 0.71 | 0.00 / 105.30 / 130.93 | 2,024.00 / 4,141.60 / 4,605.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | 50 m | 5 | 60.00 | 0.11 / 108.85 / 135.97 | 0.00 / 0.40 / 0.51 | 0.00 / 1.57 / 1.93 | 2,015.00 / 4,538.20 / 5,048.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | 50 m | 5 | 80.00 | 77.22 / 1,095.70 / 1,197.42 | 0.06 / 0.47 / 0.47 | -6.75 / 98.22 / 122.77 | 506.00 / 1,907.20 / 2,238.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | 50 m | 5 | 80.00 | 75.48 / 2,208.04 / 2,678.84 | 0.09 / 1.46 / 1.70 | 52.89 / 779.87 / 942.17 | 1,622.00 / 2,506.40 / 2,571.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 80.00 | 58.33 / 122.54 / 123.85 | 0.45 / 0.57 / 0.57 | 14.79 / 3,021.61 / 3,767.81 | 1,658.00 / 2,114.40 / 2,153.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 60.00 | 11.03 / 27.62 / 29.86 | 0.05 / 0.15 / 0.17 | 0.00 / 10.00 / 11.58 | 1,764.00 / 2,052.00 / 2,083.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | 50 m | 5 | 80.00 | 58.33 / 222.96 / 249.37 | 0.18 / 0.32 / 0.33 | 1.26 / 33.52 / 36.82 | 475.00 / 1,028.20 / 1,081.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | 50 m | 5 | 80.00 | 63.61 / 316.43 / 373.15 | 0.20 / 0.39 / 0.43 | 0.00 / 30.93 / 35.65 | 898.00 / 1,114.40 / 1,160.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | 100 m | 5 | 40.00 | 0.00 / 307.65 / 384.56 | 0.00 / 0.65 / 0.81 | 0.00 / 0.00 / 0.00 | 165.00 / 223.00 / 233.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | 100 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 151.00 / 206.60 / 214.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | 100 m | 5 | 60.00 | 111.55 / 1,032.39 / 1,239.71 | 0.22 / 1.50 / 1.80 | 0.00 / 91.34 / 100.83 | 58.00 / 220.80 / 246.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | 100 m | 5 | 80.00 | 97.93 / 2,818.73 / 3,467.80 | 0.33 / 1.89 / 2.23 | -20.17 / 42.72 / 53.40 | 257.00 / 461.20 / 465.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 20.00 | 0.00 / 431.44 / 539.30 | 0.00 / 0.57 / 0.71 | 0.00 / 104.74 / 130.93 | 1,905.00 / 4,260.60 / 4,755.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | 100 m | 5 | 60.00 | 0.11 / 108.85 / 135.97 | 0.00 / 0.40 / 0.51 | 0.00 / 1.57 / 1.93 | 2,118.00 / 4,489.60 / 4,991.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | 100 m | 5 | 60.00 | 76.08 / 1,095.70 / 1,197.42 | 0.06 / 0.47 / 0.47 | 0.00 / 98.22 / 122.77 | 532.00 / 1,792.60 / 2,091.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | 100 m | 5 | 80.00 | 75.48 / 2,208.04 / 2,678.84 | 0.09 / 1.46 / 1.70 | 52.89 / 779.87 / 942.17 | 1,612.00 / 2,449.40 / 2,451.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 60.00 | 11.61 / 120.81 / 123.85 | 0.04 / 0.50 / 0.51 | 23.38 / 3,030.92 / 3,767.81 | 1,694.00 / 2,148.20 / 2,189.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 60.00 | 11.03 / 27.62 / 29.86 | 0.05 / 0.15 / 0.17 | 0.00 / 10.00 / 11.58 | 1,741.00 / 2,036.00 / 2,066.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | 100 m | 5 | 60.00 | 9.88 / 220.21 / 248.09 | 0.02 / 0.30 / 0.31 | 9.84 / 71.64 / 83.38 | 522.00 / 1,002.40 / 1,040.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | 100 m | 5 | 80.00 | 63.61 / 316.43 / 373.15 | 0.20 / 0.39 / 0.43 | 0.00 / 30.93 / 35.65 | 893.00 / 1,111.60 / 1,156.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 307.65 / 384.56 | 0.00 / 0.65 / 0.81 | 0.00 / 0.00 / 0.00 | 155.00 / 214.60 / 227.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 153.00 / 223.80 / 235.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | 250 m | 5 | 60.00 | 111.55 / 1,032.39 / 1,239.71 | 0.22 / 1.50 / 1.80 | 0.00 / 91.34 / 100.83 | 69.00 / 199.20 / 219.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | 250 m | 5 | 80.00 | 95.24 / 2,818.73 / 3,467.80 | 0.33 / 1.89 / 2.23 | -20.17 / 42.72 / 53.40 | 275.00 / 448.60 / 465.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 431.44 / 539.30 | 0.00 / 0.57 / 0.71 | 0.00 / 104.74 / 130.93 | 1,922.00 / 4,193.40 / 4,673.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | 250 m | 5 | 40.00 | 0.00 / 108.85 / 135.97 | 0.00 / 0.40 / 0.51 | 0.00 / 0.09 / 0.12 | 2,087.00 / 4,672.60 / 5,195.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | 250 m | 5 | 60.00 | 76.08 / 1,095.70 / 1,197.42 | 0.06 / 0.47 / 0.47 | 0.00 / 98.22 / 122.77 | 564.00 / 1,772.00 / 2,067.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | 250 m | 5 | 40.00 | 0.00 / 2,208.04 / 2,678.84 | 0.00 / 1.46 / 1.70 | 0.00 / 779.87 / 942.17 | 1,527.00 / 2,615.00 / 2,668.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 116.46 / 123.85 | 0.00 / 0.45 / 0.45 | 0.00 / 3,026.19 / 3,767.81 | 1,675.00 / 2,235.80 / 2,281.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 60.00 | 11.03 / 24.59 / 26.31 | 0.05 / 0.13 / 0.15 | 0.00 / 5.45 / 5.89 | 1,701.00 / 2,134.80 / 2,163.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | 250 m | 5 | 40.00 | 0.00 / 215.85 / 248.09 | 0.00 / 0.28 / 0.28 | 0.00 / 52.70 / 59.71 | 490.00 / 1,083.60 / 1,157.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | 250 m | 5 | 80.00 | 60.05 / 293.77 / 347.34 | 0.19 / 0.36 / 0.40 | -6.12 / -1.00 / 0.00 | 879.00 / 1,076.60 / 1,111.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | 500 m | 5 | 40.00 | 0.00 / 307.65 / 384.56 | 0.00 / 0.65 / 0.81 | 0.00 / 0.00 / 0.00 | 157.00 / 214.60 / 219.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | 500 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 164.00 / 221.00 / 234.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | 500 m | 5 | 60.00 | 111.55 / 1,032.39 / 1,239.71 | 0.22 / 1.50 / 1.80 | 0.00 / 91.34 / 100.83 | 63.00 / 201.80 / 224.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | 500 m | 5 | 80.00 | 95.24 / 2,818.73 / 3,467.80 | 0.33 / 1.89 / 2.23 | -20.17 / 42.72 / 53.40 | 248.00 / 442.80 / 451.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 431.44 / 539.30 | 0.00 / 0.57 / 0.71 | 0.00 / 104.74 / 130.93 | 1,960.00 / 4,007.60 / 4,431.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | 500 m | 5 | 20.00 | 0.00 / 108.78 / 135.97 | 0.00 / 0.40 / 0.51 | 0.00 / 0.00 / 0.00 | 2,063.00 / 4,677.40 / 5,214.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | 500 m | 5 | 60.00 | 76.08 / 1,095.70 / 1,197.42 | 0.06 / 0.47 / 0.47 | 0.00 / 98.22 / 122.77 | 532.00 / 1,814.20 / 2,118.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | 500 m | 5 | 40.00 | 0.00 / 2,208.04 / 2,678.84 | 0.00 / 1.46 / 1.70 | 0.00 / 779.87 / 942.17 | 1,630.00 / 2,458.20 / 2,510.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 99.08 / 123.85 | 0.00 / 0.36 / 0.45 | 0.00 / 3,014.25 / 3,767.81 | 1,725.00 / 2,196.60 / 2,244.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 40.00 | 0.00 / 16.35 / 17.68 | 0.00 / 0.07 / 0.07 | 0.00 / 5.45 / 5.89 | 1,805.00 / 2,136.40 / 2,160.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | 500 m | 5 | 20.00 | 0.00 / 198.47 / 248.09 | 0.00 / 0.23 / 0.28 | 0.00 / 19.76 / 24.70 | 504.00 / 960.00 / 1,015.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | 500 m | 5 | 40.00 | 0.00 / 277.94 / 347.34 | 0.00 / 0.32 / 0.40 | 0.00 / 0.00 / 0.00 | 907.00 / 1,172.20 / 1,203.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | 1000 m | 5 | 40.00 | 0.00 / 307.65 / 384.56 | 0.00 / 0.65 / 0.81 | 0.00 / 0.00 / 0.00 | 185.00 / 235.60 / 248.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | 1000 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 165.00 / 223.20 / 231.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | 1000 m | 5 | 60.00 | 111.55 / 1,032.39 / 1,239.71 | 0.22 / 1.50 / 1.80 | 0.00 / 91.34 / 100.83 | 87.00 / 213.00 / 232.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | 1000 m | 5 | 80.00 | 95.24 / 2,818.73 / 3,467.80 | 0.33 / 1.89 / 2.23 | -20.17 / 42.72 / 53.40 | 283.00 / 443.20 / 453.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,887.00 / 4,183.20 / 4,627.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,117.00 / 4,699.60 / 5,221.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | 1000 m | 5 | 60.00 | 76.08 / 987.84 / 1,197.42 | 0.06 / 0.39 / 0.46 | -8.15 / 0.00 / 0.00 | 612.00 / 1,819.80 / 2,120.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | 1000 m | 5 | 40.00 | 0.00 / 2,143.41 / 2,678.84 | 0.00 / 1.36 / 1.70 | 0.00 / 753.74 / 942.17 | 1,611.00 / 2,400.40 / 2,406.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,885.00 / 2,183.00 / 2,245.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 40.00 | 0.00 / 16.35 / 17.68 | 0.00 / 0.07 / 0.07 | 0.00 / 5.45 / 5.89 | 1,820.00 / 2,117.60 / 2,125.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 507.00 / 1,000.80 / 1,058.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 950.00 / 1,171.40 / 1,203.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | d + 50 m | 5 | 40.00 | 0.00 / 307.65 / 384.56 | 0.00 / 0.65 / 0.81 | 0.00 / 0.00 / 0.00 | 159.00 / 217.60 / 231.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | d + 50 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 163.00 / 213.40 / 224.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | d + 50 m | 5 | 40.00 | 0.00 / 1,014.07 / 1,239.71 | 0.00 / 1.49 / 1.80 | 0.00 / 80.66 / 100.83 | 84.00 / 216.60 / 241.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | d + 50 m | 5 | 60.00 | 95.24 / 2,818.73 / 3,467.80 | 0.33 / 1.89 / 2.23 | -20.17 / 0.00 / 0.00 | 271.00 / 429.60 / 437.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 431.44 / 539.30 | 0.00 / 0.57 / 0.71 | 0.00 / 104.74 / 130.93 | 1,930.00 / 4,180.00 / 4,623.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 108.85 / 135.97 | 0.00 / 0.40 / 0.51 | 0.00 / 0.09 / 0.12 | 2,124.00 / 4,684.60 / 5,201.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 60.00 | 76.08 / 1,065.80 / 1,197.42 | 0.06 / 0.45 / 0.46 | 0.00 / 104.74 / 130.93 | 540.00 / 1,808.20 / 2,098.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 60.00 | 75.48 / 2,208.04 / 2,678.84 | 0.09 / 1.46 / 1.70 | 52.89 / 779.87 / 942.17 | 1,577.00 / 2,400.00 / 2,430.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 99.08 / 123.85 | 0.00 / 0.36 / 0.45 | 0.00 / 3,014.25 / 3,767.81 | 1,834.00 / 2,264.20 / 2,352.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 16.35 / 17.68 | 0.00 / 0.07 / 0.07 | 0.00 / 5.45 / 5.89 | 1,769.00 / 2,150.80 / 2,182.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 491.00 / 1,032.40 / 1,097.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 40.00 | 0.00 / 63.66 / 79.49 | 0.00 / 0.15 / 0.19 | 0.00 / 0.00 / 0.00 | 948.00 / 1,155.00 / 1,161.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | d + 100 m | 5 | 40.00 | 0.00 / 307.65 / 384.56 | 0.00 / 0.65 / 0.81 | 0.00 / 0.00 / 0.00 | 161.00 / 221.20 / 230.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | d + 100 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 154.00 / 215.80 / 226.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | d + 100 m | 5 | 40.00 | 0.00 / 1,014.07 / 1,239.71 | 0.00 / 1.49 / 1.80 | 0.00 / 80.66 / 100.83 | 66.00 / 197.00 / 220.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | d + 100 m | 5 | 60.00 | 95.24 / 2,818.73 / 3,467.80 | 0.33 / 1.89 / 2.23 | -20.17 / 0.00 / 0.00 | 296.00 / 427.40 / 440.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 431.44 / 539.30 | 0.00 / 0.57 / 0.71 | 0.00 / 104.74 / 130.93 | 1,978.00 / 4,153.80 / 4,620.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 108.85 / 135.97 | 0.00 / 0.40 / 0.51 | 0.00 / 0.09 / 0.12 | 2,078.00 / 4,753.20 / 5,305.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 60.00 | 76.08 / 1,065.80 / 1,197.42 | 0.06 / 0.45 / 0.46 | 0.00 / 104.74 / 130.93 | 506.00 / 1,830.60 / 2,128.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 60.00 | 75.48 / 2,208.04 / 2,678.84 | 0.09 / 1.46 / 1.70 | 52.89 / 779.87 / 942.17 | 1,611.00 / 2,600.60 / 2,675.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 99.08 / 123.85 | 0.00 / 0.36 / 0.45 | 0.00 / 3,014.25 / 3,767.81 | 1,773.00 / 2,205.60 / 2,272.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 16.35 / 17.68 | 0.00 / 0.07 / 0.07 | 0.00 / 5.45 / 5.89 | 1,749.00 / 2,079.20 / 2,080.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 576.00 / 954.00 / 988.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 40.00 | 0.00 / 63.66 / 79.49 | 0.00 / 0.15 / 0.19 | 0.00 / 0.00 / 0.00 | 935.00 / 1,093.20 / 1,109.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | d + 250 m | 5 | 40.00 | 0.00 / 307.65 / 384.56 | 0.00 / 0.65 / 0.81 | 0.00 / 0.00 / 0.00 | 169.00 / 220.20 / 230.00 | 168.00 / 234.20 / 248.00 |
| abisko | kayak | d + 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 169.00 / 223.60 / 234.00 | 159.00 / 219.60 / 233.00 |
| abisko | paths | d + 250 m | 5 | 40.00 | 0.00 / 1,014.07 / 1,239.71 | 0.00 / 1.49 / 1.80 | 0.00 / 80.66 / 100.83 | 104.00 / 216.20 / 242.00 | 106.00 / 677.80 / 785.00 |
| abisko | walking | d + 250 m | 5 | 60.00 | 95.24 / 2,818.73 / 3,467.80 | 0.33 / 1.89 / 2.23 | -20.17 / 0.00 / 0.00 | 308.00 / 433.20 / 450.00 | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 431.44 / 539.30 | 0.00 / 0.57 / 0.71 | 0.00 / 104.74 / 130.93 | 1,981.00 / 4,036.40 / 4,467.00 | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 40.00 | 0.00 / 108.85 / 135.97 | 0.00 / 0.40 / 0.51 | 0.00 / 0.09 / 0.12 | 2,149.00 / 4,699.20 / 5,185.00 | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 60.00 | 76.08 / 1,065.80 / 1,197.42 | 0.06 / 0.45 / 0.46 | 0.00 / 104.74 / 130.93 | 533.00 / 2,005.00 / 2,353.00 | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 40.00 | 0.00 / 2,207.70 / 2,678.84 | 0.00 / 1.46 / 1.70 | 0.00 / 779.92 / 942.17 | 1,720.00 / 2,998.40 / 3,159.00 | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 99.08 / 123.85 | 0.00 / 0.36 / 0.45 | 0.00 / 3,014.25 / 3,767.81 | 1,684.00 / 2,256.40 / 2,317.00 | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 40.00 | 0.00 / 16.35 / 17.68 | 0.00 / 0.07 / 0.07 | 0.00 / 5.45 / 5.89 | 1,775.00 / 2,087.40 / 2,112.00 | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 537.00 / 999.40 / 1,034.00 | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 920.00 / 1,093.40 / 1,136.00 | 2,077.00 / 2,800.20 / 2,917.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 168.00 / 234.20 / 248.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 159.00 / 219.60 / 233.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 106.00 / 677.80 / 785.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 936.00 / 1,684.60 / 1,790.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,912.00 / 4,107.60 / 4,562.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,070.00 / 4,412.60 / 4,892.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 985.00 / 4,229.40 / 4,981.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 3,992.00 / 5,853.20 / 5,922.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,630.00 / 2,227.00 / 2,289.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,657.00 / 2,098.80 / 2,125.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,055.00 / 2,643.20 / 2,828.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,077.00 / 2,800.20 / 2,917.00 |

</details>

<details>
<summary>250 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 100.00 | 14.04 / 992.11 / 1,212.34 | 1.34 / 13.42 / 14.67 | 1.40 / 35.87 / 36.59 | 313.00 / 376.00 / 386.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | 0 | 5 | 80.00 | 4.21 / 145.22 / 149.85 | 2.52 / 12.38 / 14.67 | 0.00 / 1.25 / 1.40 | 317.00 / 371.60 / 380.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | 0 | 5 | 100.00 | 455.68 / 1,004.63 / 1,008.00 | 0.52 / 3.22 / 3.85 | 35.71 / 586.01 / 698.75 | 99.00 / 278.20 / 281.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | 0 | 5 | 100.00 | 244.70 / 703.83 / 782.97 | 0.42 / 2.13 / 2.46 | -6.32 / 284.08 / 346.17 | 244.00 / 369.80 / 373.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 60.00 | 59.48 / 218.37 / 258.03 | 0.04 / 5.73 / 7.05 | 0.00 / 4.82 / 5.97 | 2,169.00 / 3,982.00 / 4,296.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | 0 | 5 | 80.00 | 12.86 / 31.89 / 35.39 | 0.03 / 1.43 / 1.77 | 0.00 / 37.90 / 45.88 | 2,281.00 / 3,955.00 / 4,266.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | 0 | 5 | 100.00 | 101.14 / 683.63 / 790.03 | 0.29 / 0.40 / 0.41 | 0.72 / 15.97 / 17.83 | 516.00 / 2,416.60 / 2,548.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | 0 | 5 | 100.00 | 35.39 / 565.41 / 686.82 | 0.07 / 0.25 / 0.28 | -0.16 / 44.41 / 45.88 | 804.00 / 4,541.20 / 4,569.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 100.00 | 83.48 / 479.41 / 512.96 | 0.69 / 5.42 / 6.37 | 27.61 / 125.20 / 146.57 | 2,528.00 / 2,590.20 / 2,599.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | 0 | 5 | 100.00 | 15.90 / 66.06 / 67.59 | 0.10 / 1.19 / 1.41 | -2.39 / 1.18 / 1.98 | 2,368.00 / 2,638.40 / 2,692.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | 0 | 5 | 100.00 | 218.53 / 1,544.78 / 1,823.09 | 0.50 / 6.14 / 7.51 | -3.71 / 50.22 / 52.84 | 765.00 / 1,047.40 / 1,062.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | 0 | 5 | 100.00 | 48.97 / 549.78 / 652.39 | 0.10 / 2.62 / 3.23 | -2.03 / 48.79 / 61.36 | 978.00 / 1,150.40 / 1,192.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | 50 m | 5 | 80.00 | 11.47 / 992.11 / 1,212.34 | 0.36 / 6.97 / 8.38 | 0.00 / 35.87 / 36.59 | 316.00 / 358.80 / 360.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | 50 m | 5 | 60.00 | 0.36 / 145.22 / 149.85 | 0.03 / 3.08 / 3.22 | 0.00 / 0.49 / 0.61 | 321.00 / 387.20 / 393.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | 50 m | 5 | 100.00 | 455.68 / 1,004.63 / 1,008.00 | 0.52 / 3.22 / 3.85 | 35.71 / 586.01 / 698.75 | 94.00 / 271.60 / 274.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | 50 m | 5 | 100.00 | 244.70 / 703.83 / 782.97 | 0.42 / 2.13 / 2.46 | -6.32 / 284.08 / 346.17 | 231.00 / 381.00 / 385.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 40.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.16 / 0.20 | 2,226.00 / 3,975.60 / 4,250.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | 50 m | 5 | 60.00 | 0.00 / 7.65 / 8.91 | 0.00 / 0.02 / 0.03 | 0.00 / 8.49 / 10.61 | 2,281.00 / 3,912.60 / 4,189.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | 50 m | 5 | 100.00 | 41.66 / 676.67 / 790.03 | 0.15 / 0.34 / 0.36 | 0.72 / 15.97 / 17.83 | 521.00 / 2,587.40 / 2,807.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | 50 m | 5 | 80.00 | 27.01 / 565.41 / 686.82 | 0.01 / 0.25 / 0.28 | 0.00 / 32.94 / 38.53 | 734.00 / 4,514.60 / 4,540.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 40.00 | 0.00 / 51.69 / 53.90 | 0.00 / 0.58 / 0.69 | 0.00 / 37.32 / 39.75 | 2,463.00 / 2,558.80 / 2,577.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 60.00 | 0.05 / 4.80 / 5.95 | 0.00 / 0.02 / 0.03 | 0.00 / 1.60 / 1.98 | 2,323.00 / 2,519.00 / 2,530.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | 50 m | 5 | 100.00 | 67.07 / 125.32 / 135.05 | 0.14 / 0.56 / 0.63 | -0.39 / 50.22 / 52.84 | 755.00 / 975.00 / 981.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | 50 m | 5 | 60.00 | 0.05 / 73.31 / 79.39 | 0.00 / 0.09 / 0.10 | 0.00 / 7.08 / 8.85 | 890.00 / 1,230.60 / 1,281.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | 100 m | 5 | 80.00 | 11.47 / 992.11 / 1,212.34 | 0.36 / 6.97 / 8.38 | 0.00 / 35.87 / 36.59 | 350.00 / 369.40 / 371.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | 100 m | 5 | 60.00 | 0.36 / 145.22 / 149.85 | 0.03 / 3.08 / 3.22 | 0.00 / 0.49 / 0.61 | 308.00 / 363.60 / 368.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | 100 m | 5 | 100.00 | 455.68 / 1,004.63 / 1,008.00 | 0.52 / 3.22 / 3.85 | 35.71 / 586.01 / 698.75 | 86.00 / 275.20 / 278.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | 100 m | 5 | 100.00 | 244.70 / 703.83 / 782.97 | 0.42 / 2.13 / 2.46 | -6.32 / 284.08 / 346.17 | 234.00 / 404.60 / 413.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 40.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.16 / 0.20 | 2,313.00 / 3,846.00 / 4,069.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | 100 m | 5 | 40.00 | 0.00 / 7.13 / 8.91 | 0.00 / 0.02 / 0.03 | 0.00 / 0.00 / 0.00 | 2,313.00 / 4,185.80 / 4,533.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | 100 m | 5 | 80.00 | 41.66 / 676.67 / 790.03 | 0.15 / 0.34 / 0.36 | 0.00 / 6.95 / 8.51 | 490.00 / 2,424.60 / 2,623.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | 100 m | 5 | 60.00 | 11.01 / 565.41 / 686.82 | 0.00 / 0.25 / 0.28 | 0.00 / 16.42 / 20.52 | 754.00 / 4,621.40 / 4,680.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 40.00 | 0.00 / 51.69 / 53.90 | 0.00 / 0.58 / 0.69 | 0.00 / 37.32 / 39.75 | 2,390.00 / 2,577.80 / 2,610.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 60.00 | 0.05 / 4.80 / 5.95 | 0.00 / 0.02 / 0.03 | 0.00 / 1.60 / 1.98 | 2,357.00 / 2,506.40 / 2,517.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | 100 m | 5 | 100.00 | 67.07 / 125.32 / 135.05 | 0.14 / 0.56 / 0.63 | -0.39 / 50.22 / 52.84 | 750.00 / 996.60 / 1,014.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | 100 m | 5 | 60.00 | 0.05 / 73.31 / 79.39 | 0.00 / 0.09 / 0.10 | 0.00 / 7.08 / 8.85 | 960.00 / 1,198.40 / 1,240.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 966.24 / 1,205.92 | 0.00 / 6.73 / 8.34 | 0.00 / 35.39 / 44.24 | 342.00 / 380.00 / 387.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | 250 m | 5 | 60.00 | 0.36 / 145.17 / 149.85 | 0.03 / 3.08 / 3.22 | 0.00 / 0.49 / 0.61 | 317.00 / 370.20 / 378.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | 250 m | 5 | 80.00 | 455.68 / 999.49 / 1,001.58 | 0.52 / 3.20 / 3.83 | 35.71 / 594.98 / 709.96 | 100.00 / 295.60 / 299.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | 250 m | 5 | 80.00 | 244.70 / 703.83 / 782.97 | 0.42 / 2.13 / 2.46 | 0.00 / 284.08 / 346.17 | 219.00 / 378.20 / 383.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.00 / 0.00 | 2,194.00 / 3,945.60 / 4,235.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,298.00 / 4,073.40 / 4,395.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | 250 m | 5 | 60.00 | 41.66 / 676.66 / 790.03 | 0.15 / 0.34 / 0.36 | 0.00 / 0.42 / 0.52 | 508.00 / 2,327.40 / 2,478.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | 250 m | 5 | 40.00 | 0.00 / 558.28 / 677.90 | 0.00 / 0.24 / 0.28 | 0.00 / 0.00 / 0.00 | 761.00 / 5,084.40 / 5,201.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 15.87 / 19.84 | 0.00 / 0.06 / 0.08 | 0.00 / 1.59 / 1.98 | 2,438.00 / 2,550.40 / 2,565.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 60.00 | 0.05 / 4.80 / 5.95 | 0.00 / 0.02 / 0.03 | 0.00 / 1.60 / 1.98 | 2,427.00 / 2,542.00 / 2,555.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | 250 m | 5 | 40.00 | 0.00 / 121.45 / 135.05 | 0.00 / 0.25 / 0.28 | 0.00 / 0.00 / 0.00 | 738.00 / 1,062.80 / 1,083.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | 250 m | 5 | 40.00 | 0.00 / 2.11 / 2.63 | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.00 | 939.00 / 1,245.00 / 1,292.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 829.61 / 1,037.01 | 0.00 / 5.74 / 7.17 | 0.00 / 0.00 / 0.00 | 350.00 / 365.00 / 366.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | 500 m | 5 | 40.00 | 0.00 / 118.64 / 126.47 | 0.00 / 2.39 / 2.52 | 0.00 / 0.00 / 0.00 | 321.00 / 378.00 / 385.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | 500 m | 5 | 80.00 | 455.68 / 999.45 / 1,001.58 | 0.52 / 3.20 / 3.83 | 35.71 / 594.43 / 709.96 | 92.00 / 300.20 / 308.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | 500 m | 5 | 80.00 | 244.70 / 654.84 / 721.80 | 0.39 / 2.13 / 2.46 | 32.67 / 280.17 / 341.29 | 237.00 / 379.60 / 384.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 40.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.00 / 0.00 | 2,249.00 / 4,034.40 / 4,344.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | 500 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,265.00 / 3,939.40 / 4,228.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | 500 m | 5 | 60.00 | 41.66 / 676.66 / 790.03 | 0.15 / 0.34 / 0.36 | 0.00 / 0.42 / 0.52 | 513.00 / 2,401.20 / 2,578.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | 500 m | 5 | 40.00 | 0.00 / 556.84 / 677.90 | 0.00 / 0.24 / 0.28 | 0.00 / 0.00 / 0.00 | 762.00 / 4,925.20 / 5,018.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,425.00 / 2,476.40 / 2,487.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 20.00 | 0.00 / 0.15 / 0.19 | 0.00 / 0.00 / 0.00 | 0.00 / 0.05 / 0.06 | 2,350.00 / 2,487.20 / 2,500.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | 500 m | 5 | 40.00 | 0.00 / 121.45 / 135.05 | 0.00 / 0.25 / 0.28 | 0.00 / 0.00 / 0.00 | 772.00 / 1,065.40 / 1,092.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | 500 m | 5 | 20.00 | 0.00 / 2.10 / 2.63 | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.00 | 968.00 / 1,227.00 / 1,279.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | 1000 m | 5 | 20.00 | 0.00 / 829.61 / 1,037.01 | 0.00 / 5.74 / 7.17 | 0.00 / 0.00 / 0.00 | 351.00 / 393.00 / 395.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | 1000 m | 5 | 20.00 | 0.00 / 69.87 / 87.34 | 0.00 / 1.50 / 1.88 | 0.00 / 0.00 / 0.00 | 345.00 / 375.60 / 382.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | 1000 m | 5 | 60.00 | 455.68 / 999.45 / 1,001.58 | 0.27 / 3.17 / 3.83 | 35.71 / 594.43 / 709.96 | 108.00 / 294.40 / 297.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | 1000 m | 5 | 60.00 | 105.01 / 654.84 / 721.80 | 0.06 / 2.05 / 2.46 | 32.67 / 280.17 / 341.29 | 239.00 / 390.00 / 391.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 20.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.00 / 0.00 | 2,229.00 / 4,066.60 / 4,393.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,325.00 / 3,951.40 / 4,245.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | 1000 m | 5 | 40.00 | 0.00 / 676.66 / 790.03 | 0.00 / 0.34 / 0.36 | 0.00 / 0.42 / 0.52 | 534.00 / 2,324.00 / 2,462.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | 1000 m | 5 | 40.00 | 0.00 / 556.84 / 677.90 | 0.00 / 0.24 / 0.28 | 0.00 / 0.00 / 0.00 | 802.00 / 4,856.80 / 4,933.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,395.00 / 2,483.80 / 2,495.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 20.00 | 0.00 / 0.15 / 0.19 | 0.00 / 0.00 / 0.00 | 0.00 / 0.05 / 0.06 | 2,473.00 / 2,595.00 / 2,602.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 723.00 / 1,139.20 / 1,178.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 948.00 / 1,201.20 / 1,237.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 829.61 / 1,037.01 | 0.00 / 5.74 / 7.17 | 0.00 / 0.00 / 0.00 | 339.00 / 364.20 / 368.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | d + 50 m | 5 | 40.00 | 0.00 / 118.64 / 126.47 | 0.00 / 2.39 / 2.52 | 0.00 / 0.00 / 0.00 | 317.00 / 373.00 / 381.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | d + 50 m | 5 | 80.00 | 455.68 / 999.45 / 1,001.58 | 0.52 / 3.20 / 3.83 | 35.71 / 594.43 / 709.96 | 111.00 / 275.00 / 276.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | d + 50 m | 5 | 80.00 | 244.70 / 703.77 / 782.97 | 0.42 / 2.13 / 2.46 | 0.00 / 280.17 / 341.29 | 227.00 / 386.20 / 391.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 40.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.16 / 0.20 | 2,313.00 / 4,139.20 / 4,507.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 7.13 / 8.91 | 0.00 / 0.02 / 0.03 | 0.00 / 0.00 / 0.00 | 2,399.00 / 3,982.80 / 4,284.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 40.00 | 0.00 / 676.67 / 790.03 | 0.00 / 0.34 / 0.36 | 0.00 / 0.58 / 0.72 | 507.00 / 2,500.60 / 2,652.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 40.00 | 0.00 / 565.41 / 686.82 | 0.00 / 0.25 / 0.28 | 0.00 / 0.00 / 0.00 | 760.00 / 4,935.40 / 5,046.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 15.87 / 19.84 | 0.00 / 0.06 / 0.08 | 0.00 / 1.59 / 1.98 | 2,372.00 / 2,528.20 / 2,548.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 60.00 | 0.05 / 4.80 / 5.95 | 0.00 / 0.02 / 0.03 | 0.00 / 1.60 / 1.98 | 2,436.00 / 2,698.80 / 2,743.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 20.00 | 0.00 / 53.66 / 67.07 | 0.00 / 0.22 / 0.28 | 0.00 / 0.00 / 0.00 | 733.00 / 1,028.60 / 1,056.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 40.00 | 0.00 / 2.11 / 2.63 | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.00 | 928.00 / 1,374.80 / 1,472.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 829.61 / 1,037.01 | 0.00 / 5.74 / 7.17 | 0.00 / 0.00 / 0.00 | 340.00 / 368.20 / 369.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | d + 100 m | 5 | 40.00 | 0.00 / 118.64 / 126.47 | 0.00 / 2.39 / 2.52 | 0.00 / 0.00 / 0.00 | 331.00 / 360.80 / 365.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | d + 100 m | 5 | 80.00 | 455.68 / 999.45 / 1,001.58 | 0.52 / 3.20 / 3.83 | 35.71 / 594.43 / 709.96 | 94.00 / 285.40 / 289.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | d + 100 m | 5 | 80.00 | 244.70 / 654.84 / 721.80 | 0.39 / 2.13 / 2.46 | 32.67 / 280.17 / 341.29 | 225.00 / 372.00 / 373.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 40.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.00 / 0.00 | 2,253.00 / 4,109.00 / 4,403.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 7.13 / 8.91 | 0.00 / 0.02 / 0.03 | 0.00 / 0.00 / 0.00 | 2,426.00 / 4,086.40 / 4,412.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 40.00 | 0.00 / 676.66 / 790.03 | 0.00 / 0.34 / 0.36 | 0.00 / 0.42 / 0.52 | 501.00 / 2,441.20 / 2,599.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 40.00 | 0.00 / 565.41 / 686.82 | 0.00 / 0.25 / 0.28 | 0.00 / 0.00 / 0.00 | 795.00 / 4,605.00 / 4,637.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 15.87 / 19.84 | 0.00 / 0.06 / 0.08 | 0.00 / 1.59 / 1.98 | 2,381.00 / 2,484.60 / 2,492.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 4.80 / 5.95 | 0.00 / 0.02 / 0.03 | 0.00 / 1.60 / 1.98 | 2,477.00 / 2,581.20 / 2,606.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 20.00 | 0.00 / 53.66 / 67.07 | 0.00 / 0.22 / 0.28 | 0.00 / 0.00 / 0.00 | 807.00 / 1,073.20 / 1,119.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 20.00 | 0.00 / 2.10 / 2.63 | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.00 | 899.00 / 1,379.00 / 1,481.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 829.61 / 1,037.01 | 0.00 / 5.74 / 7.17 | 0.00 / 0.00 / 0.00 | 329.00 / 371.40 / 375.00 | 322.00 / 347.20 / 351.00 |
| abisko | kayak | d + 250 m | 5 | 40.00 | 0.00 / 118.64 / 126.47 | 0.00 / 2.39 / 2.52 | 0.00 / 0.00 / 0.00 | 320.00 / 361.60 / 366.00 | 315.00 / 365.60 / 372.00 |
| abisko | paths | d + 250 m | 5 | 80.00 | 455.68 / 999.45 / 1,001.58 | 0.52 / 3.20 / 3.83 | 35.71 / 594.43 / 709.96 | 101.00 / 295.00 / 302.00 | 186.00 / 924.00 / 943.00 |
| abisko | walking | d + 250 m | 5 | 80.00 | 244.70 / 654.84 / 721.80 | 0.39 / 2.13 / 2.46 | 32.67 / 280.17 / 341.29 | 254.00 / 397.00 / 405.00 | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 40.00 | 0.00 / 178.55 / 223.19 | 0.00 / 0.33 / 0.42 | 0.00 / 0.00 / 0.00 | 2,248.00 / 4,017.00 / 4,333.00 | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,323.00 / 4,013.00 / 4,331.00 | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 40.00 | 0.00 / 676.66 / 790.03 | 0.00 / 0.34 / 0.36 | 0.00 / 0.42 / 0.52 | 514.00 / 2,645.80 / 2,748.00 | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 40.00 | 0.00 / 556.84 / 677.90 | 0.00 / 0.24 / 0.28 | 0.00 / 0.00 / 0.00 | 837.00 / 4,790.00 / 4,863.00 | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 15.87 / 19.84 | 0.00 / 0.06 / 0.08 | 0.00 / 1.59 / 1.98 | 2,467.00 / 2,573.80 / 2,596.00 | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 40.00 | 0.00 / 4.80 / 5.95 | 0.00 / 0.02 / 0.03 | 0.00 / 1.60 / 1.98 | 2,454.00 / 2,616.60 / 2,633.00 | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 20.00 | 0.00 / 53.66 / 67.07 | 0.00 / 0.22 / 0.28 | 0.00 / 0.00 / 0.00 | 759.00 / 1,040.00 / 1,065.00 | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 20.00 | 0.00 / 2.10 / 2.63 | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.00 | 961.00 / 1,130.80 / 1,158.00 | 2,272.00 / 3,075.00 / 3,159.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 322.00 / 347.20 / 351.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 315.00 / 365.60 / 372.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 186.00 / 924.00 / 943.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 598.00 / 1,364.20 / 1,380.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,177.00 / 3,762.80 / 3,997.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,309.00 / 3,973.40 / 4,289.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,005.00 / 5,432.60 / 5,837.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,814.00 / 13,493.80 / 13,584.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,406.00 / 2,451.40 / 2,459.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,315.00 / 2,412.20 / 2,424.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,831.00 / 3,055.80 / 3,150.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,272.00 / 3,075.00 / 3,159.00 |

</details>

<details>
<summary>500 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 60.00 | 0.09 / 3,096.12 / 3,757.04 | 0.00 / 16.59 / 18.26 | 0.00 / 1,388.17 / 1,735.22 | 411.00 / 519.80 / 530.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | 0 | 5 | 60.00 | 0.03 / 50.08 / 60.30 | 0.00 / 3.36 / 4.17 | 0.00 / 0.01 / 0.01 | 394.00 / 500.60 / 507.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | 0 | 5 | 100.00 | 2,568.87 / 3,457.76 / 3,659.91 | 2.68 / 7.55 / 7.80 | 184.92 / 1,561.92 / 1,904.43 | 118.00 / 285.80 / 292.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | 0 | 5 | 60.00 | 10.41 / 2,758.61 / 3,145.10 | 0.03 / 9.71 / 11.77 | 0.00 / 437.43 / 546.79 | 299.00 / 337.60 / 338.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 80.00 | 59.31 / 4,602.56 / 5,735.69 | 0.14 / 6.33 / 6.55 | 5.93 / 1,397.41 / 1,744.55 | 1,549.00 / 4,868.00 / 4,959.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | 0 | 5 | 100.00 | 17.79 / 694.59 / 859.71 | 0.18 / 3.35 / 3.90 | 5.93 / 11.16 / 11.38 | 1,461.00 / 5,010.00 / 5,089.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | 0 | 5 | 100.00 | 165.64 / 4,219.15 / 5,225.95 | 0.14 / 2.37 / 2.92 | 16.88 / 1,563.45 / 1,922.18 | 1,595.00 / 1,808.00 / 1,816.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | 0 | 5 | 100.00 | 42.26 / 130.21 / 147.83 | 0.05 / 0.11 / 0.13 | -1.41 / 549.44 / 684.11 | 1,878.00 / 3,274.20 / 3,485.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 80.00 | 37.97 / 344.41 / 347.47 | 0.21 / 7.81 / 9.35 | 59.83 / 964.02 / 1,101.50 | 1,787.00 / 2,559.40 / 2,657.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | 0 | 5 | 80.00 | 17.70 / 703.79 / 826.19 | 0.50 / 4.29 / 4.96 | 0.00 / 152.04 / 175.33 | 1,819.00 / 2,341.20 / 2,417.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | 0 | 5 | 100.00 | 36.19 / 1,400.81 / 1,616.27 | 0.06 / 1.81 / 1.86 | -0.22 / 270.43 / 321.80 | 772.00 / 1,065.00 / 1,116.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | 0 | 5 | 100.00 | 101.94 / 804.84 / 937.51 | 0.17 / 0.96 / 0.97 | 12.77 / 45.48 / 52.54 | 1,051.00 / 1,195.60 / 1,225.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | 50 m | 5 | 60.00 | 0.09 / 3,096.12 / 3,757.04 | 0.00 / 16.59 / 18.26 | 0.00 / 1,388.17 / 1,735.22 | 409.00 / 542.40 / 552.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | 50 m | 5 | 60.00 | 0.03 / 50.08 / 60.30 | 0.00 / 3.36 / 4.17 | 0.00 / 0.01 / 0.01 | 386.00 / 501.40 / 506.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | 50 m | 5 | 100.00 | 2,568.87 / 3,457.76 / 3,659.91 | 2.68 / 7.55 / 7.80 | 184.92 / 1,561.92 / 1,904.43 | 120.00 / 294.60 / 303.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | 50 m | 5 | 60.00 | 10.41 / 2,758.61 / 3,145.10 | 0.03 / 9.71 / 11.77 | 0.00 / 437.43 / 546.79 | 291.00 / 345.40 / 353.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 20.00 | 0.00 / 4,588.55 / 5,735.69 | 0.00 / 4.34 / 5.43 | 0.00 / 1,395.64 / 1,744.55 | 1,564.00 / 4,922.20 / 5,005.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | 50 m | 5 | 40.00 | 0.00 / 694.59 / 859.71 | 0.00 / 0.97 / 1.17 | 0.00 / 9.11 / 11.38 | 1,530.00 / 5,248.20 / 5,477.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | 50 m | 5 | 60.00 | 165.64 / 4,219.15 / 5,225.95 | 0.10 / 2.37 / 2.92 | 16.88 / 1,563.45 / 1,922.18 | 1,691.00 / 1,899.00 / 1,902.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | 50 m | 5 | 60.00 | 42.26 / 130.21 / 147.83 | 0.04 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 1,966.00 / 3,059.20 / 3,241.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 60.00 | 6.83 / 285.57 / 347.47 | 0.04 / 1.36 / 1.65 | 0.00 / 964.02 / 1,101.50 | 1,765.00 / 2,503.60 / 2,599.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 60.00 | 0.24 / 703.79 / 826.19 | 0.00 / 4.29 / 4.96 | 0.00 / 140.26 / 175.33 | 1,830.00 / 2,355.80 / 2,477.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | 50 m | 5 | 100.00 | 36.19 / 1,334.38 / 1,616.27 | 0.06 / 1.42 / 1.60 | -0.22 / 258.46 / 321.80 | 827.00 / 1,010.60 / 1,052.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | 50 m | 5 | 100.00 | 101.94 / 801.30 / 937.51 | 0.17 / 0.94 / 0.95 | -0.70 / 16.38 / 17.28 | 1,027.00 / 1,200.00 / 1,239.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | 100 m | 5 | 60.00 | 0.09 / 3,096.12 / 3,757.04 | 0.00 / 16.59 / 18.26 | 0.00 / 1,388.17 / 1,735.22 | 418.00 / 516.20 / 523.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | 100 m | 5 | 60.00 | 0.03 / 50.08 / 60.30 | 0.00 / 3.36 / 4.17 | 0.00 / 0.01 / 0.01 | 385.00 / 499.40 / 503.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | 100 m | 5 | 100.00 | 2,568.87 / 3,457.76 / 3,659.91 | 2.68 / 7.55 / 7.80 | 184.92 / 1,561.92 / 1,904.43 | 116.00 / 283.00 / 290.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | 100 m | 5 | 60.00 | 10.41 / 2,758.61 / 3,145.10 | 0.03 / 9.71 / 11.77 | 0.00 / 437.43 / 546.79 | 294.00 / 352.60 / 364.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 20.00 | 0.00 / 4,588.55 / 5,735.69 | 0.00 / 4.34 / 5.43 | 0.00 / 1,395.64 / 1,744.55 | 1,575.00 / 4,956.40 / 5,052.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | 100 m | 5 | 40.00 | 0.00 / 694.59 / 859.71 | 0.00 / 0.97 / 1.17 | 0.00 / 9.11 / 11.38 | 1,667.00 / 5,280.60 / 5,495.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | 100 m | 5 | 60.00 | 165.64 / 4,219.15 / 5,225.95 | 0.10 / 2.37 / 2.92 | 16.88 / 1,563.45 / 1,922.18 | 1,680.00 / 1,794.40 / 1,805.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | 100 m | 5 | 60.00 | 42.26 / 130.21 / 147.83 | 0.04 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 2,143.00 / 3,195.40 / 3,453.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 60.00 | 6.83 / 280.94 / 347.47 | 0.04 / 1.33 / 1.65 | 0.00 / 960.14 / 1,101.50 | 1,778.00 / 2,613.40 / 2,738.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 60.00 | 0.24 / 703.79 / 826.19 | 0.00 / 4.29 / 4.96 | 0.00 / 140.26 / 175.33 | 1,783.00 / 2,404.60 / 2,548.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | 100 m | 5 | 100.00 | 36.19 / 1,334.38 / 1,616.27 | 0.06 / 1.42 / 1.60 | -0.30 / 258.46 / 321.80 | 817.00 / 1,043.80 / 1,095.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | 100 m | 5 | 100.00 | 101.94 / 801.30 / 937.51 | 0.17 / 0.94 / 0.95 | -0.70 / 16.38 / 17.28 | 1,027.00 / 1,269.20 / 1,311.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | 250 m | 5 | 60.00 | 0.09 / 3,010.68 / 3,757.04 | 0.00 / 14.72 / 18.26 | 0.01 / 1,388.68 / 1,735.22 | 383.00 / 488.80 / 489.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | 250 m | 5 | 60.00 | 0.03 / 8.86 / 9.18 | 0.00 / 0.44 / 0.52 | 0.00 / 2.02 / 2.53 | 377.00 / 513.00 / 519.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | 250 m | 5 | 100.00 | 2,224.61 / 3,441.70 / 3,659.91 | 2.68 / 7.34 / 7.80 | 184.92 / 1,561.92 / 1,904.43 | 110.00 / 263.00 / 265.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | 250 m | 5 | 60.00 | 10.41 / 2,717.07 / 3,093.17 | 0.03 / 9.56 / 11.57 | 0.00 / 441.70 / 552.13 | 294.00 / 353.80 / 364.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 876.59 / 1,095.74 | 0.00 / 0.83 / 1.04 | 0.00 / 0.00 / 0.00 | 1,675.00 / 5,118.80 / 5,283.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | 250 m | 5 | 40.00 | 0.00 / 694.59 / 859.71 | 0.00 / 0.97 / 1.17 | 0.00 / 9.11 / 11.38 | 1,661.00 / 5,357.60 / 5,580.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | 250 m | 5 | 60.00 | 165.64 / 507.19 / 586.00 | 0.10 / 0.30 / 0.33 | 16.88 / 107.37 / 128.52 | 1,669.00 / 1,866.40 / 1,881.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | 250 m | 5 | 60.00 | 42.26 / 130.21 / 147.83 | 0.04 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 2,082.00 / 3,222.40 / 3,464.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 60.00 | 6.83 / 251.99 / 311.28 | 0.04 / 1.20 / 1.48 | 0.00 / 969.63 / 1,113.37 | 1,746.00 / 2,619.60 / 2,706.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 60.00 | 0.24 / 703.79 / 826.19 | 0.00 / 4.29 / 4.96 | 0.00 / 140.26 / 175.33 | 1,721.00 / 2,467.60 / 2,630.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | 250 m | 5 | 80.00 | 6.83 / 702.43 / 826.34 | 0.01 / 0.80 / 0.82 | -0.30 / 4.09 / 5.11 | 794.00 / 1,079.60 / 1,121.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | 250 m | 5 | 100.00 | 101.82 / 656.39 / 756.37 | 0.17 / 0.88 / 0.90 | -0.70 / 110.59 / 130.97 | 1,002.00 / 1,243.00 / 1,300.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | 500 m | 5 | 40.00 | 0.00 / 3,005.63 / 3,757.04 | 0.00 / 14.61 / 18.26 | 0.00 / 1,388.17 / 1,735.22 | 392.00 / 486.40 / 488.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | 500 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 389.00 / 521.20 / 533.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | 500 m | 5 | 60.00 | 2,224.61 / 3,348.61 / 3,623.06 | 2.34 / 7.28 / 7.72 | 133.54 / 14,262.47 / 17,355.57 | 119.00 / 265.80 / 266.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | 500 m | 5 | 60.00 | 0.53 / 2,717.07 / 3,093.17 | 0.00 / 9.56 / 11.57 | 0.00 / 441.70 / 552.13 | 297.00 / 330.40 / 332.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 876.59 / 1,095.74 | 0.00 / 0.83 / 1.04 | 0.00 / 0.00 / 0.00 | 1,721.00 / 5,022.20 / 5,108.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | 500 m | 5 | 40.00 | 0.00 / 694.59 / 859.71 | 0.00 / 0.97 / 1.17 | 0.00 / 9.11 / 11.38 | 1,554.00 / 4,888.00 / 5,024.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | 500 m | 5 | 40.00 | 0.00 / 501.93 / 586.00 | 0.00 / 0.28 / 0.33 | 0.00 / 21.60 / 22.78 | 1,688.00 / 1,903.80 / 1,935.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | 500 m | 5 | 40.00 | 0.00 / 130.21 / 147.83 | 0.00 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 1,939.00 / 3,389.20 / 3,686.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,769.00 / 2,563.40 / 2,676.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 20.00 | 0.00 / 59.91 / 74.89 | 0.00 / 0.36 / 0.45 | 0.00 / 19.97 / 24.96 | 1,886.00 / 2,422.60 / 2,553.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | 500 m | 5 | 40.00 | 0.00 / 702.43 / 826.34 | 0.00 / 0.80 / 0.82 | 0.00 / 4.09 / 5.11 | 780.00 / 1,106.00 / 1,170.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | 500 m | 5 | 60.00 | 101.82 / 641.96 / 738.33 | 0.17 / 0.87 / 0.90 | 0.00 / 77.46 / 96.82 | 969.00 / 1,296.80 / 1,357.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | 1000 m | 5 | 40.00 | 0.00 / 3,005.63 / 3,757.04 | 0.00 / 14.61 / 18.26 | 0.00 / 1,388.17 / 1,735.22 | 402.00 / 528.40 / 536.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | 1000 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 395.00 / 517.00 / 525.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | 1000 m | 5 | 60.00 | 2,224.61 / 3,348.61 / 3,623.06 | 2.34 / 7.28 / 7.72 | 133.54 / 14,262.47 / 17,355.57 | 123.00 / 267.60 / 268.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | 1000 m | 5 | 60.00 | 0.53 / 2,717.07 / 3,093.17 | 0.00 / 9.56 / 11.57 | 0.00 / 441.70 / 552.13 | 299.00 / 370.40 / 387.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 20.00 | 0.00 / 876.59 / 1,095.74 | 0.00 / 0.83 / 1.04 | 0.00 / 0.00 / 0.00 | 1,630.00 / 5,229.00 / 5,328.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 20.00 | 0.00 / 687.77 / 859.71 | 0.00 / 0.93 / 1.17 | 0.00 / 0.00 / 0.00 | 1,714.00 / 5,106.00 / 5,238.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | 1000 m | 5 | 40.00 | 0.00 / 501.93 / 586.00 | 0.00 / 0.28 / 0.33 | 0.00 / 21.60 / 22.78 | 1,668.00 / 1,931.80 / 1,937.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | 1000 m | 5 | 40.00 | 0.00 / 130.21 / 147.83 | 0.00 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 1,909.00 / 3,340.00 / 3,573.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,702.00 / 2,524.40 / 2,624.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 20.00 | 0.00 / 59.91 / 74.89 | 0.00 / 0.36 / 0.45 | 0.00 / 19.97 / 24.96 | 1,798.00 / 2,422.60 / 2,528.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 20.00 | 0.00 / 661.07 / 826.34 | 0.00 / 0.65 / 0.82 | 0.00 / 0.00 / 0.00 | 800.00 / 1,085.20 / 1,149.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 40.00 | 0.00 / 611.03 / 738.33 | 0.00 / 0.63 / 0.75 | 0.00 / 77.46 / 96.82 | 978.00 / 1,306.40 / 1,367.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 405.00 / 510.60 / 520.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | d + 50 m | 5 | 60.00 | 0.00 / 39.99 / 47.69 | 0.00 / 2.66 / 3.30 | 0.00 / 0.00 / 0.00 | 389.00 / 513.40 / 517.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | d + 50 m | 5 | 80.00 | 1,126.72 / 2,245.56 / 2,250.80 | 1.76 / 4.87 / 5.50 | 133.54 / 13,921.44 / 17,355.57 | 114.00 / 295.00 / 302.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | d + 50 m | 5 | 60.00 | 0.53 / 2,758.61 / 3,145.10 | 0.00 / 9.71 / 11.77 | 0.00 / 437.43 / 546.79 | 294.00 / 338.80 / 348.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 876.59 / 1,095.74 | 0.00 / 0.83 / 1.04 | 0.00 / 0.00 / 0.00 | 1,582.00 / 5,122.20 / 5,210.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 694.59 / 859.71 | 0.00 / 0.97 / 1.17 | 0.00 / 9.11 / 11.38 | 1,639.00 / 5,083.20 / 5,217.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 60.00 | 165.64 / 507.19 / 586.00 | 0.10 / 0.30 / 0.33 | 16.88 / 107.37 / 128.52 | 1,710.00 / 1,941.40 / 1,968.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 60.00 | 42.26 / 130.21 / 147.83 | 0.04 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 1,970.00 / 3,458.60 / 3,744.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 60.00 | 6.83 / 251.99 / 311.28 | 0.04 / 1.20 / 1.48 | 0.00 / 969.63 / 1,113.37 | 1,741.00 / 2,544.20 / 2,622.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 60.00 | 0.24 / 701.98 / 826.19 | 0.00 / 4.28 / 4.96 | 0.00 / 137.62 / 172.03 | 1,765.00 / 2,307.00 / 2,393.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 60.00 | 0.85 / 662.44 / 826.34 | 0.00 / 0.66 / 0.82 | -0.30 / 0.00 / 0.00 | 792.00 / 1,010.80 / 1,058.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 80.00 | 5.44 / 611.03 / 738.33 | 0.01 / 0.63 / 0.75 | 0.00 / 83.27 / 96.82 | 1,008.00 / 1,185.20 / 1,225.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 403.00 / 498.60 / 500.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | d + 100 m | 5 | 40.00 | 0.00 / 7.35 / 9.18 | 0.00 / 0.08 / 0.10 | 0.00 / 0.00 / 0.00 | 406.00 / 524.00 / 529.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | d + 100 m | 5 | 60.00 | 1,126.72 / 2,245.56 / 2,250.80 | 1.76 / 4.87 / 5.50 | 133.54 / 13,921.44 / 17,355.57 | 121.00 / 261.60 / 264.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | d + 100 m | 5 | 60.00 | 0.53 / 2,717.07 / 3,093.17 | 0.00 / 9.56 / 11.57 | 0.00 / 441.70 / 552.13 | 286.00 / 355.40 / 372.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 876.59 / 1,095.74 | 0.00 / 0.83 / 1.04 | 0.00 / 0.00 / 0.00 | 1,575.00 / 4,953.40 / 5,051.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 694.59 / 859.71 | 0.00 / 0.97 / 1.17 | 0.00 / 9.11 / 11.38 | 1,609.00 / 4,947.60 / 5,084.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 40.00 | 0.00 / 501.93 / 586.00 | 0.00 / 0.28 / 0.33 | 0.00 / 21.60 / 22.78 | 1,826.00 / 1,993.60 / 2,012.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 40.00 | 0.00 / 130.21 / 147.83 | 0.00 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 2,068.00 / 3,304.20 / 3,560.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 40.00 | 0.00 / 250.39 / 311.28 | 0.00 / 1.19 / 1.48 | 0.00 / 890.69 / 1,113.37 | 1,689.00 / 2,699.80 / 2,847.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 661.00 / 826.19 | 0.00 / 3.97 / 4.96 | 0.00 / 0.00 / 0.00 | 1,747.00 / 2,368.00 / 2,460.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 20.00 | 0.00 / 5.47 / 6.83 | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.00 | 833.00 / 1,094.20 / 1,152.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 40.00 | 0.00 / 81.51 / 101.82 | 0.00 / 0.13 / 0.17 | 0.00 / 0.00 / 0.00 | 985.00 / 1,293.80 / 1,346.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 411.00 / 498.00 / 501.00 | 383.00 / 495.00 / 496.00 |
| abisko | kayak | d + 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 410.00 / 503.80 / 507.00 | 368.00 / 481.40 / 485.00 |
| abisko | paths | d + 250 m | 5 | 40.00 | 0.00 / 2,103.94 / 2,224.61 | 0.00 / 4.74 / 5.50 | 0.00 / 13,923.26 / 17,370.69 | 127.00 / 267.00 / 270.00 | 227.00 / 729.00 / 736.00 |
| abisko | walking | d + 250 m | 5 | 60.00 | 0.53 / 2,609.25 / 3,093.17 | 0.00 / 9.42 / 11.57 | 0.00 / 442.95 / 552.13 | 298.00 / 362.20 / 376.00 | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 876.59 / 1,095.74 | 0.00 / 0.83 / 1.04 | 0.00 / 0.00 / 0.00 | 1,580.00 / 5,086.20 / 5,222.00 | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 20.00 | 0.00 / 687.77 / 859.71 | 0.00 / 0.93 / 1.17 | 0.00 / 0.00 / 0.00 | 1,537.00 / 4,916.00 / 5,038.00 | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 40.00 | 0.00 / 501.93 / 586.00 | 0.00 / 0.28 / 0.33 | 0.00 / 21.60 / 22.78 | 1,689.00 / 1,917.60 / 1,929.00 | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 40.00 | 0.00 / 130.21 / 147.83 | 0.00 / 0.11 / 0.13 | 0.00 / 547.29 / 684.11 | 1,927.00 / 3,274.00 / 3,499.00 | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 1,761.00 / 2,687.60 / 2,802.00 | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 20.00 | 0.00 / 59.91 / 74.89 | 0.00 / 0.36 / 0.45 | 0.00 / 19.97 / 24.96 | 1,769.00 / 2,441.40 / 2,560.00 | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 811.00 / 988.40 / 1,029.00 | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 20.00 | 0.00 / 81.46 / 101.82 | 0.00 / 0.13 / 0.17 | 0.00 / 0.00 / 0.00 | 984.00 / 1,127.40 / 1,147.00 | 2,267.00 / 3,296.80 / 3,465.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 383.00 / 495.00 / 496.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 368.00 / 481.40 / 485.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 227.00 / 729.00 / 736.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 848.00 / 1,015.80 / 1,042.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,602.00 / 4,759.20 / 4,847.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,586.00 / 4,869.60 / 5,010.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 3,432.00 / 4,896.80 / 5,101.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 4,037.00 / 9,915.60 / 11,121.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,776.00 / 2,485.20 / 2,640.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,702.00 / 2,386.80 / 2,510.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,928.00 / 2,723.00 / 2,887.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,267.00 / 3,296.80 / 3,465.00 |

</details>

<details>
<summary>1000 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 80.00 | 177.26 / 2,083.52 / 2,524.20 | 0.73 / 13.41 / 16.51 | -17.86 / 1,422.62 / 1,778.27 | 201.00 / 403.60 / 421.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | 0 | 5 | 40.00 | 0.00 / 242.77 / 303.03 | 0.00 / 2.53 / 3.16 | 0.00 / 0.46 / 0.58 | 221.00 / 408.80 / 425.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | 0 | 5 | 100.00 | 1,031.41 / 2,567.59 / 2,738.16 | 1.39 / 6.62 / 7.89 | 101.77 / 163.27 / 173.45 | 119.00 / 274.20 / 293.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | 0 | 5 | 100.00 | 364.38 / 2,566.40 / 3,107.84 | 0.96 / 16.25 / 20.06 | 160.23 / 968.40 / 1,021.15 | 255.00 / 392.40 / 403.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 40.00 | 0.00 / 5.07 / 6.33 | 0.00 / 0.01 / 0.01 | 0.00 / 3.39 / 4.24 | 2,284.00 / 3,755.60 / 3,976.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | 0 | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,254.00 / 3,875.00 / 4,141.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | 0 | 5 | 80.00 | 6.33 / 947.08 / 1,074.55 | 0.01 / 0.61 / 0.66 | 4.24 / 148.41 / 180.76 | 894.00 / 1,589.60 / 1,672.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | 0 | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 1,970.00 / 3,239.40 / 3,354.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 80.00 | 829.16 / 3,108.29 / 3,621.01 | 4.29 / 8.84 / 9.70 | 31.52 / 196.52 / 230.65 | 2,576.00 / 3,053.60 / 3,134.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | 0 | 5 | 40.00 | 0.00 / 213.81 / 228.84 | 0.00 / 1.22 / 1.34 | 0.00 / 31.44 / 32.38 | 2,458.00 / 2,834.40 / 2,894.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | 0 | 5 | 100.00 | 1,603.15 / 3,221.15 / 3,621.01 | 1.99 / 4.23 / 4.72 | 48.86 / 794.17 / 941.16 | 752.00 / 916.40 / 923.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | 0 | 5 | 100.00 | 303.32 / 568.01 / 579.44 | 0.38 / 0.81 / 0.86 | 4.11 / 23.86 / 27.65 | 1,130.00 / 1,178.00 / 1,183.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | 50 m | 5 | 80.00 | 177.26 / 2,083.52 / 2,524.20 | 0.73 / 13.41 / 16.51 | -17.86 / 1,422.62 / 1,778.27 | 213.00 / 375.60 / 386.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | 50 m | 5 | 40.00 | 0.00 / 242.77 / 303.03 | 0.00 / 2.53 / 3.16 | 0.00 / 0.46 / 0.58 | 213.00 / 379.20 / 385.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | 50 m | 5 | 100.00 | 1,031.41 / 2,567.59 / 2,738.16 | 1.39 / 6.62 / 7.89 | 101.77 / 163.27 / 173.45 | 120.00 / 283.40 / 309.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | 50 m | 5 | 100.00 | 364.38 / 2,566.40 / 3,107.84 | 0.96 / 16.25 / 20.06 | 160.23 / 968.40 / 1,021.15 | 254.00 / 385.00 / 391.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 40.00 | 0.00 / 5.07 / 6.33 | 0.00 / 0.01 / 0.01 | 0.00 / 3.39 / 4.24 | 2,180.00 / 3,787.80 / 3,998.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | 50 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,134.00 / 3,847.80 / 4,120.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | 50 m | 5 | 80.00 | 6.33 / 947.08 / 1,074.55 | 0.01 / 0.61 / 0.66 | 4.24 / 148.41 / 180.76 | 793.00 / 1,638.20 / 1,722.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | 50 m | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 2,097.00 / 3,287.80 / 3,400.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 80.00 | 829.16 / 3,108.29 / 3,621.01 | 4.29 / 8.84 / 9.70 | 31.52 / 196.52 / 230.65 | 2,517.00 / 2,856.40 / 2,921.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 40.00 | 0.00 / 213.81 / 228.84 | 0.00 / 1.22 / 1.34 | 0.00 / 31.44 / 32.38 | 2,548.00 / 2,846.40 / 2,901.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | 50 m | 5 | 100.00 | 1,603.15 / 3,221.15 / 3,621.01 | 1.99 / 4.23 / 4.72 | 48.86 / 794.17 / 941.16 | 707.00 / 959.40 / 969.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | 50 m | 5 | 100.00 | 303.32 / 568.01 / 579.44 | 0.38 / 0.81 / 0.86 | 4.11 / 23.86 / 27.65 | 1,163.00 / 1,357.80 / 1,406.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | 100 m | 5 | 80.00 | 177.26 / 2,083.52 / 2,524.20 | 0.73 / 13.41 / 16.51 | -17.86 / 1,422.62 / 1,778.27 | 181.00 / 386.20 / 399.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | 100 m | 5 | 40.00 | 0.00 / 242.77 / 303.03 | 0.00 / 2.53 / 3.16 | 0.00 / 0.46 / 0.58 | 179.00 / 383.80 / 387.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | 100 m | 5 | 100.00 | 1,031.41 / 2,567.59 / 2,738.16 | 1.39 / 6.62 / 7.89 | 101.77 / 163.27 / 173.45 | 118.00 / 261.80 / 281.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | 100 m | 5 | 100.00 | 364.38 / 2,566.40 / 3,107.84 | 0.96 / 16.25 / 20.06 | 160.23 / 968.40 / 1,021.15 | 261.00 / 378.60 / 385.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 40.00 | 0.00 / 5.07 / 6.33 | 0.00 / 0.01 / 0.01 | 0.00 / 3.39 / 4.24 | 2,144.00 / 3,845.80 / 4,088.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | 100 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,206.00 / 3,902.00 / 4,173.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | 100 m | 5 | 80.00 | 6.33 / 947.08 / 1,074.55 | 0.01 / 0.61 / 0.66 | 4.24 / 148.41 / 180.76 | 834.00 / 1,558.00 / 1,633.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | 100 m | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 2,056.00 / 3,404.40 / 3,542.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 60.00 | 43.06 / 3,062.64 / 3,621.01 | 0.24 / 8.84 / 9.70 | 0.00 / 54.29 / 59.99 | 2,690.00 / 2,941.40 / 2,999.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 40.00 | 0.00 / 213.81 / 228.84 | 0.00 / 1.22 / 1.34 | 0.00 / 31.44 / 32.38 | 2,594.00 / 2,769.80 / 2,812.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | 100 m | 5 | 100.00 | 1,578.46 / 3,221.15 / 3,621.01 | 1.84 / 4.18 / 4.72 | -24.47 / 762.70 / 941.16 | 777.00 / 996.00 / 999.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | 100 m | 5 | 100.00 | 303.32 / 568.01 / 579.44 | 0.38 / 0.81 / 0.86 | 4.11 / 23.86 / 27.65 | 1,126.00 / 1,201.00 / 1,214.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | 250 m | 5 | 80.00 | 177.26 / 2,083.52 / 2,524.20 | 0.73 / 13.41 / 16.51 | -17.86 / 1,422.62 / 1,778.27 | 251.00 / 399.20 / 414.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | 250 m | 5 | 40.00 | 0.00 / 242.77 / 303.03 | 0.00 / 2.53 / 3.16 | 0.00 / 0.46 / 0.58 | 184.00 / 372.40 / 377.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | 250 m | 5 | 100.00 | 121.16 / 2,396.81 / 2,738.16 | 0.22 / 1.50 / 1.53 | -11.35 / 163.27 / 173.45 | 113.00 / 274.00 / 287.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | 250 m | 5 | 100.00 | 303.05 / 393.41 / 400.67 | 0.96 / 1.45 / 1.55 | 303.96 / 968.40 / 1,021.15 | 243.00 / 394.80 / 406.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,292.00 / 3,746.00 / 3,952.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | 250 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,232.00 / 3,834.60 / 4,065.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | 250 m | 5 | 60.00 | 2.48 / 947.08 / 1,074.55 | 0.00 / 0.61 / 0.66 | 0.00 / 148.41 / 180.76 | 801.00 / 1,623.20 / 1,710.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | 250 m | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 2,092.00 / 3,268.00 / 3,382.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 60.00 | 43.06 / 3,008.59 / 3,553.45 | 0.24 / 8.69 / 9.52 | 0.00 / 54.29 / 59.99 | 2,587.00 / 2,944.00 / 3,022.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 40.00 | 0.00 / 147.98 / 153.72 | 0.00 / 1.15 / 1.34 | 0.00 / 25.91 / 32.38 | 2,597.00 / 2,834.60 / 2,860.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | 250 m | 5 | 100.00 | 1,578.46 / 3,167.11 / 3,553.45 | 1.84 / 4.11 / 4.63 | -24.47 / 762.70 / 941.16 | 746.00 / 945.20 / 952.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | 250 m | 5 | 100.00 | 303.32 / 568.01 / 579.44 | 0.38 / 0.81 / 0.86 | -33.96 / 7.79 / 8.71 | 1,070.00 / 1,247.80 / 1,271.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | 500 m | 5 | 80.00 | 177.26 / 2,083.52 / 2,524.20 | 0.73 / 13.41 / 16.51 | -17.86 / 1,422.62 / 1,778.27 | 203.00 / 412.20 / 428.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | 500 m | 5 | 40.00 | 0.00 / 242.77 / 303.03 | 0.00 / 2.53 / 3.16 | 0.00 / 0.46 / 0.58 | 191.00 / 372.00 / 376.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | 500 m | 5 | 100.00 | 121.16 / 2,396.81 / 2,738.16 | 0.22 / 1.50 / 1.53 | -11.35 / 163.27 / 173.45 | 135.00 / 271.80 / 294.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | 500 m | 5 | 100.00 | 303.05 / 393.41 / 400.67 | 0.16 / 1.01 / 1.03 | -15.08 / 968.40 / 1,021.15 | 293.00 / 382.80 / 387.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,336.00 / 3,763.00 / 3,944.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | 500 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,245.00 / 3,851.60 / 4,127.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | 500 m | 5 | 60.00 | 2.48 / 947.08 / 1,074.55 | 0.00 / 0.61 / 0.66 | 0.00 / 148.41 / 180.76 | 771.00 / 1,502.40 / 1,556.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | 500 m | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 2,000.00 / 3,237.80 / 3,400.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 3.81 / 4.76 | 0.00 / 0.02 / 0.03 | 0.00 / 4.73 / 5.91 | 2,760.00 / 3,060.00 / 3,117.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 40.00 | 0.00 / 101.00 / 125.05 | 0.00 / 0.33 / 0.40 | 0.00 / 4.73 / 5.91 | 2,508.00 / 2,749.80 / 2,805.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | 500 m | 5 | 80.00 | 412.56 / 735.89 / 783.43 | 0.48 / 0.89 / 0.92 | -11.13 / 19.89 / 24.87 | 803.00 / 910.40 / 917.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | 500 m | 5 | 100.00 | 215.39 / 568.01 / 579.44 | 0.27 / 0.81 / 0.86 | -33.96 / 128.92 / 160.12 | 1,107.00 / 1,182.60 / 1,189.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | 1000 m | 5 | 40.00 | 0.00 / 292.11 / 320.82 | 0.00 / 0.96 / 1.02 | 0.00 / 0.00 / 0.00 | 229.00 / 448.20 / 468.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | 1000 m | 5 | 20.00 | 0.00 / 1.38 / 1.73 | 0.00 / 0.02 / 0.02 | 0.00 / 0.46 / 0.58 | 225.00 / 411.60 / 416.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | 1000 m | 5 | 60.00 | 121.16 / 2,396.65 / 2,738.16 | 0.22 / 1.50 / 1.53 | 0.00 / 163.27 / 173.45 | 122.00 / 271.40 / 290.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | 1000 m | 5 | 80.00 | 303.05 / 393.41 / 400.67 | 0.16 / 1.01 / 1.03 | 0.00 / 968.40 / 1,021.15 | 257.00 / 402.60 / 412.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,284.00 / 3,800.60 / 3,983.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,227.00 / 4,014.20 / 4,268.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | 1000 m | 5 | 60.00 | 2.48 / 947.08 / 1,074.55 | 0.00 / 0.61 / 0.66 | 0.00 / 148.41 / 180.76 | 919.00 / 1,484.80 / 1,530.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | 1000 m | 5 | 60.00 | 7.61 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 20.73 / 22.51 | 2,161.00 / 3,186.20 / 3,315.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 20.00 | 0.00 / 3.81 / 4.76 | 0.00 / 0.02 / 0.03 | 0.00 / 4.73 / 5.91 | 2,701.00 / 3,013.40 / 3,089.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 20.00 | 0.00 / 3.81 / 4.76 | 0.00 / 0.03 / 0.04 | 0.00 / 4.73 / 5.91 | 2,573.00 / 2,877.20 / 2,940.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 20.00 | 0.00 / 626.74 / 783.43 | 0.00 / 0.73 / 0.92 | 0.00 / 19.89 / 24.87 | 741.00 / 993.00 / 1,021.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 40.00 | 0.00 / 63.77 / 79.68 | 0.00 / 0.08 / 0.10 | 0.00 / 21.62 / 25.99 | 1,127.00 / 1,271.60 / 1,289.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | d + 50 m | 5 | 40.00 | 0.00 / 292.11 / 320.82 | 0.00 / 0.96 / 1.02 | 0.00 / 0.00 / 0.00 | 196.00 / 424.00 / 442.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | d + 50 m | 5 | 40.00 | 0.00 / 19.05 / 23.39 | 0.00 / 0.20 / 0.24 | 0.00 / 105.18 / 131.33 | 208.00 / 391.60 / 394.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | d + 50 m | 5 | 80.00 | 1,031.41 / 2,567.59 / 2,738.16 | 1.39 / 6.62 / 7.89 | 101.77 / 163.27 / 173.45 | 163.00 / 290.80 / 317.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | d + 50 m | 5 | 100.00 | 364.38 / 2,566.40 / 3,107.84 | 0.96 / 16.25 / 20.06 | 160.23 / 968.40 / 1,021.15 | 236.00 / 428.00 / 443.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,249.00 / 3,785.60 / 3,975.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,421.00 / 3,878.60 / 4,154.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 40.00 | 0.00 / 860.14 / 1,074.55 | 0.00 / 0.53 / 0.66 | 0.00 / 144.61 / 180.76 | 879.00 / 1,479.60 / 1,515.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 1,930.00 / 3,395.00 / 3,544.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 3.81 / 4.76 | 0.00 / 0.02 / 0.03 | 0.00 / 4.73 / 5.91 | 2,674.00 / 2,886.20 / 2,891.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 101.00 / 125.05 | 0.00 / 0.33 / 0.40 | 0.00 / 4.73 / 5.91 | 2,481.00 / 2,794.40 / 2,872.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 40.00 | 0.00 / 672.92 / 783.43 | 0.00 / 0.79 / 0.92 | 0.00 / 19.89 / 24.87 | 770.00 / 931.20 / 935.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 60.00 | 0.13 / 218.11 / 241.37 | 0.00 / 0.27 / 0.30 | 0.00 / 192.02 / 239.00 | 1,123.00 / 1,136.60 / 1,138.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | d + 100 m | 5 | 40.00 | 0.00 / 292.11 / 320.82 | 0.00 / 0.96 / 1.02 | 0.00 / 0.00 / 0.00 | 196.00 / 389.80 / 399.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | d + 100 m | 5 | 20.00 | 0.00 / 1.38 / 1.73 | 0.00 / 0.02 / 0.02 | 0.00 / 0.46 / 0.58 | 217.00 / 404.00 / 411.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | d + 100 m | 5 | 80.00 | 1,031.41 / 2,567.59 / 2,738.16 | 1.39 / 6.62 / 7.89 | 101.77 / 163.27 / 173.45 | 138.00 / 322.80 / 354.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | d + 100 m | 5 | 100.00 | 364.38 / 2,566.40 / 3,107.84 | 0.96 / 16.25 / 20.06 | 160.23 / 968.40 / 1,021.15 | 276.00 / 452.80 / 473.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,391.00 / 3,773.80 / 3,986.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,364.00 / 4,028.20 / 4,291.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 40.00 | 0.00 / 860.14 / 1,074.55 | 0.00 / 0.53 / 0.66 | 0.00 / 144.61 / 180.76 | 831.00 / 1,522.60 / 1,567.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 2,053.00 / 3,375.80 / 3,535.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 20.00 | 0.00 / 3.81 / 4.76 | 0.00 / 0.02 / 0.03 | 0.00 / 4.73 / 5.91 | 2,637.00 / 2,844.20 / 2,882.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 40.00 | 0.00 / 101.00 / 125.05 | 0.00 / 0.33 / 0.40 | 0.00 / 4.73 / 5.91 | 2,532.00 / 2,736.00 / 2,760.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 40.00 | 0.00 / 672.92 / 783.43 | 0.00 / 0.79 / 0.92 | 0.00 / 19.89 / 24.87 | 752.00 / 897.80 / 902.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 60.00 | 0.13 / 197.32 / 215.39 | 0.00 / 0.25 / 0.27 | 0.00 / 128.92 / 160.12 | 1,086.00 / 1,101.80 / 1,103.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | d + 250 m | 5 | 40.00 | 0.00 / 292.11 / 320.82 | 0.00 / 0.96 / 1.02 | 0.00 / 0.00 / 0.00 | 193.00 / 379.20 / 390.00 | 190.00 / 409.40 / 426.00 |
| abisko | kayak | d + 250 m | 5 | 20.00 | 0.00 / 1.38 / 1.73 | 0.00 / 0.02 / 0.02 | 0.00 / 0.46 / 0.58 | 210.00 / 385.20 / 393.00 | 183.00 / 420.60 / 440.00 |
| abisko | paths | d + 250 m | 5 | 60.00 | 121.16 / 2,396.65 / 2,738.16 | 0.22 / 1.50 / 1.53 | 0.00 / 163.27 / 173.45 | 138.00 / 306.60 / 334.00 | 374.00 / 824.00 / 926.00 |
| abisko | walking | d + 250 m | 5 | 100.00 | 284.54 / 393.41 / 400.67 | 0.96 / 1.44 / 1.54 | -15.08 / 677.60 / 757.40 | 265.00 / 400.80 / 413.00 | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,367.00 / 3,772.80 / 3,943.00 | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 40.00 | 0.00 / 18.63 / 23.29 | 0.00 / 0.05 / 0.06 | 0.00 / 446.70 / 558.37 | 2,227.00 / 3,876.00 / 4,123.00 | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 40.00 | 0.00 / 860.14 / 1,074.55 | 0.00 / 0.53 / 0.66 | 0.00 / 144.61 / 180.76 | 844.00 / 1,531.00 / 1,586.00 | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 60.00 | 8.08 / 16.22 / 17.81 | 0.01 / 0.03 / 0.04 | 4.58 / 12.97 / 13.63 | 2,117.00 / 3,373.00 / 3,545.00 | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 20.00 | 0.00 / 3.81 / 4.76 | 0.00 / 0.02 / 0.03 | 0.00 / 4.73 / 5.91 | 2,632.00 / 3,001.80 / 3,060.00 | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 40.00 | 0.00 / 101.00 / 125.05 | 0.00 / 0.33 / 0.40 | 0.00 / 4.73 / 5.91 | 2,469.00 / 2,801.00 / 2,881.00 | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 20.00 | 0.00 / 626.74 / 783.43 | 0.00 / 0.73 / 0.92 | 0.00 / 19.89 / 24.87 | 759.00 / 976.60 / 984.00 | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 60.00 | 0.13 / 115.98 / 125.05 | 0.00 / 0.16 / 0.17 | 0.00 / 21.62 / 25.99 | 1,105.00 / 1,135.20 / 1,137.00 | 2,798.00 / 3,078.60 / 3,137.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 190.00 / 409.40 / 426.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 183.00 / 420.60 / 440.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 374.00 / 824.00 / 926.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 632.00 / 1,525.80 / 1,549.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,224.00 / 3,647.40 / 3,852.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,213.00 / 3,878.40 / 4,148.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,776.00 / 3,416.60 / 3,465.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 4,217.00 / 9,635.40 / 9,956.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,644.00 / 3,013.60 / 3,069.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,458.00 / 2,762.60 / 2,832.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,890.00 / 2,501.40 / 2,565.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,798.00 / 3,078.60 / 3,137.00 |

</details>

<details>
<summary>2000 m requested offset</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abisko | kayak-paths | 0 | 5 | 80.00 | 28.10 / 921.60 / 1,130.98 | 0.47 / 3.09 / 3.68 | 1.31 / 829.58 / 1,033.93 | 361.00 / 669.00 / 698.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | 0 | 5 | 60.00 | 3.92 / 62.97 / 73.74 | 0.03 / 0.65 / 0.73 | 1.31 / 25.18 / 25.33 | 335.00 / 705.80 / 752.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | 0 | 5 | 80.00 | 623.17 / 646.46 / 647.94 | 0.84 / 1.04 / 1.07 | 34.96 / 683.04 / 776.85 | 219.00 / 296.40 / 301.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | 0 | 5 | 100.00 | 348.58 / 2,058.22 / 2,479.99 | 0.56 / 5.96 / 7.26 | -61.14 / 4,703.41 / 5,882.72 | 330.00 / 347.60 / 349.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | 0 | 5 | 100.00 | 71.58 / 373.17 / 439.70 | 0.16 / 0.39 / 0.43 | 4.08 / 28.92 / 34.53 | 3,384.00 / 4,546.60 / 4,724.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | 0 | 5 | 60.00 | 19.41 / 45.36 / 51.84 | 0.05 / 0.12 / 0.12 | 0.00 / 39.31 / 47.52 | 3,472.00 / 4,862.80 / 5,055.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | 0 | 5 | 100.00 | 83.31 / 1,032.29 / 1,232.15 | 0.06 / 0.85 / 1.02 | -2.57 / 31.44 / 37.51 | 1,316.00 / 2,145.60 / 2,264.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | 0 | 5 | 100.00 | 28.46 / 170.27 / 188.96 | 0.02 / 0.30 / 0.35 | 12.35 / 196.15 / 210.27 | 1,858.00 / 2,711.00 / 2,874.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | 0 | 5 | 100.00 | 260.06 / 3,796.47 / 4,663.07 | 1.19 / 11.77 / 14.33 | 4.06 / 172.32 / 211.91 | 2,227.00 / 2,762.20 / 2,871.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | 0 | 5 | 60.00 | 7.36 / 593.48 / 739.40 | 0.04 / 2.36 / 2.93 | 0.00 / 27.65 / 31.64 | 2,028.00 / 2,526.80 / 2,634.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | 0 | 5 | 100.00 | 205.44 / 4,468.05 / 5,470.70 | 0.43 / 6.25 / 7.67 | -113.89 / 40.98 / 61.05 | 713.00 / 986.80 / 1,008.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | 0 | 5 | 100.00 | 159.12 / 677.52 / 792.37 | 0.28 / 1.03 / 1.20 | -14.17 / 185.73 / 222.10 | 921.00 / 954.80 / 963.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | 50 m | 5 | 80.00 | 28.10 / 921.60 / 1,130.98 | 0.47 / 3.09 / 3.68 | 1.27 / 829.58 / 1,033.93 | 347.00 / 695.20 / 735.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | 50 m | 5 | 60.00 | 3.80 / 62.97 / 73.74 | 0.02 / 0.65 / 0.73 | 1.27 / 25.18 / 25.33 | 315.00 / 697.00 / 737.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | 50 m | 5 | 80.00 | 623.17 / 646.46 / 647.94 | 0.84 / 1.04 / 1.07 | 34.96 / 683.04 / 776.85 | 217.00 / 308.40 / 311.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | 50 m | 5 | 100.00 | 348.58 / 2,058.22 / 2,479.99 | 0.56 / 5.96 / 7.26 | -61.14 / 4,703.41 / 5,882.72 | 327.00 / 347.40 / 348.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | 50 m | 5 | 80.00 | 36.86 / 364.74 / 439.70 | 0.05 / 0.36 / 0.43 | 0.00 / 6.01 / 6.49 | 3,441.00 / 4,501.00 / 4,650.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | 50 m | 5 | 20.00 | 0.00 / 15.57 / 19.47 | 0.00 / 0.08 / 0.10 | 0.00 / 5.19 / 6.49 | 3,432.00 / 4,716.40 / 4,928.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | 50 m | 5 | 80.00 | 83.31 / 1,010.88 / 1,232.15 | 0.04 / 0.84 / 1.02 | -2.57 / 5.73 / 7.17 | 1,326.00 / 2,064.60 / 2,150.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | 50 m | 5 | 100.00 | 11.44 / 128.80 / 137.12 | 0.01 / 0.22 / 0.25 | 16.40 / 158.13 / 162.75 | 1,938.00 / 2,931.00 / 3,149.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | 50 m | 5 | 100.00 | 260.06 / 3,796.47 / 4,663.07 | 1.19 / 11.77 / 14.33 | 4.06 / 172.32 / 211.91 | 2,220.00 / 2,754.00 / 2,886.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | 50 m | 5 | 60.00 | 7.36 / 593.48 / 739.40 | 0.04 / 2.36 / 2.93 | 0.00 / 27.65 / 31.64 | 2,108.00 / 2,617.80 / 2,741.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | 50 m | 5 | 100.00 | 205.44 / 4,468.05 / 5,470.70 | 0.43 / 6.25 / 7.67 | -113.89 / 40.98 / 61.05 | 619.00 / 873.40 / 874.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | 50 m | 5 | 100.00 | 159.12 / 677.52 / 792.37 | 0.28 / 1.03 / 1.20 | -14.17 / 185.73 / 222.10 | 931.00 / 985.40 / 988.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | 100 m | 5 | 80.00 | 28.10 / 921.60 / 1,130.98 | 0.47 / 3.09 / 3.68 | 1.27 / 829.58 / 1,033.93 | 333.00 / 661.80 / 684.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | 100 m | 5 | 60.00 | 3.80 / 62.97 / 73.74 | 0.02 / 0.65 / 0.73 | 1.27 / 25.18 / 25.33 | 323.00 / 712.80 / 757.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | 100 m | 5 | 80.00 | 623.17 / 646.46 / 647.94 | 0.84 / 1.04 / 1.07 | 34.96 / 683.04 / 776.85 | 251.00 / 300.40 / 303.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | 100 m | 5 | 100.00 | 348.58 / 2,058.22 / 2,479.99 | 0.56 / 5.96 / 7.26 | -61.14 / 4,703.41 / 5,882.72 | 322.00 / 395.80 / 402.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | 100 m | 5 | 80.00 | 36.86 / 364.74 / 439.70 | 0.05 / 0.36 / 0.43 | 0.00 / 6.01 / 6.49 | 3,416.00 / 4,547.40 / 4,713.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | 100 m | 5 | 20.00 | 0.00 / 15.57 / 19.47 | 0.00 / 0.08 / 0.10 | 0.00 / 5.19 / 6.49 | 3,518.00 / 4,636.00 / 4,841.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | 100 m | 5 | 80.00 | 83.31 / 1,010.88 / 1,232.15 | 0.04 / 0.84 / 1.02 | -2.57 / 5.73 / 7.17 | 1,390.00 / 2,172.00 / 2,291.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | 100 m | 5 | 100.00 | 11.44 / 128.80 / 137.12 | 0.01 / 0.22 / 0.25 | 16.40 / 158.13 / 162.75 | 1,959.00 / 2,683.60 / 2,860.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | 100 m | 5 | 80.00 | 260.06 / 3,796.47 / 4,663.07 | 1.19 / 11.77 / 14.33 | 0.00 / 181.24 / 211.91 | 2,153.00 / 2,795.80 / 2,899.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | 100 m | 5 | 40.00 | 0.00 / 593.48 / 739.40 | 0.00 / 2.36 / 2.93 | 0.00 / 25.31 / 31.64 | 2,073.00 / 2,598.00 / 2,706.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | 100 m | 5 | 80.00 | 203.67 / 4,468.05 / 5,470.70 | 0.32 / 6.25 / 7.67 | -39.30 / 43.54 / 54.43 | 637.00 / 973.40 / 1,002.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | 100 m | 5 | 100.00 | 159.12 / 677.52 / 792.37 | 0.28 / 1.03 / 1.20 | -14.17 / 185.73 / 222.10 | 946.00 / 1,034.60 / 1,035.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | 250 m | 5 | 80.00 | 22.65 / 910.40 / 1,130.98 | 0.20 / 3.04 / 3.68 | 1.27 / 901.11 / 1,123.34 | 370.00 / 676.80 / 711.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | 250 m | 5 | 60.00 | 3.80 / 62.97 / 73.74 | 0.02 / 0.65 / 0.73 | 1.27 / 25.18 / 25.33 | 310.00 / 670.60 / 699.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | 250 m | 5 | 80.00 | 623.17 / 646.46 / 647.94 | 0.69 / 1.02 / 1.07 | 27.34 / 683.04 / 776.85 | 237.00 / 280.60 / 281.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | 250 m | 5 | 100.00 | 348.58 / 2,058.22 / 2,479.99 | 0.56 / 5.96 / 7.26 | -61.14 / 4,703.41 / 5,882.72 | 319.00 / 401.40 / 421.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 112.45 / 124.35 | 0.00 / 0.12 / 0.12 | 0.00 / 5.19 / 6.49 | 3,384.00 / 4,697.00 / 4,904.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | 250 m | 5 | 20.00 | 0.00 / 15.57 / 19.47 | 0.00 / 0.08 / 0.10 | 0.00 / 5.19 / 6.49 | 3,518.00 / 4,952.80 / 5,220.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | 250 m | 5 | 80.00 | 83.31 / 758.60 / 916.79 | 0.03 / 0.63 / 0.76 | -2.57 / 2.47 / 3.09 | 1,398.00 / 2,142.80 / 2,254.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | 250 m | 5 | 100.00 | 9.05 / 128.80 / 137.12 | 0.01 / 0.22 / 0.25 | 16.40 / 158.13 / 162.75 | 1,939.00 / 2,719.80 / 2,898.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | 250 m | 5 | 40.00 | 0.00 / 3,739.58 / 4,663.07 | 0.00 / 11.50 / 14.33 | 0.00 / 75.16 / 93.95 | 2,212.00 / 2,765.20 / 2,894.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | 250 m | 5 | 40.00 | 0.00 / 593.48 / 739.40 | 0.00 / 2.36 / 2.93 | 0.00 / 25.31 / 31.64 | 2,066.00 / 2,637.20 / 2,773.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | 250 m | 5 | 60.00 | 59.91 / 4,425.16 / 5,470.70 | 0.11 / 6.20 / 7.67 | 0.00 / 43.54 / 54.43 | 666.00 / 901.60 / 915.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | 250 m | 5 | 60.00 | 9.11 / 677.52 / 792.37 | 0.02 / 1.02 / 1.20 | 0.00 / 32.21 / 40.26 | 948.00 / 998.60 / 1,003.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | 500 m | 5 | 60.00 | 12.67 / 909.31 / 1,130.98 | 0.06 / 2.98 / 3.68 | 0.00 / 898.93 / 1,123.34 | 374.00 / 655.00 / 687.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | 500 m | 5 | 60.00 | 3.80 / 61.36 / 73.74 | 0.02 / 0.62 / 0.73 | 1.27 / 20.45 / 24.58 | 313.00 / 700.60 / 738.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | 500 m | 5 | 80.00 | 612.98 / 646.46 / 647.94 | 0.69 / 1.02 / 1.07 | 27.34 / 674.86 / 766.63 | 235.00 / 289.00 / 290.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | 500 m | 5 | 80.00 | 348.58 / 2,058.22 / 2,479.99 | 0.56 / 5.96 / 7.26 | -61.14 / 4,706.18 / 5,882.72 | 341.00 / 359.80 / 361.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | 500 m | 5 | 20.00 | 0.00 / 51.91 / 64.89 | 0.00 / 0.08 / 0.10 | 0.00 / 5.19 / 6.49 | 3,417.00 / 4,552.40 / 4,697.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | 500 m | 5 | 20.00 | 0.00 / 15.57 / 19.47 | 0.00 / 0.08 / 0.10 | 0.00 / 5.19 / 6.49 | 3,528.00 / 5,048.00 / 5,357.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | 500 m | 5 | 40.00 | 0.00 / 68.06 / 83.31 | 0.00 / 0.02 / 0.03 | 0.00 / 2.47 / 3.09 | 1,324.00 / 2,157.60 / 2,275.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | 500 m | 5 | 80.00 | 1.58 / 128.80 / 137.12 | 0.00 / 0.22 / 0.25 | 0.00 / 158.13 / 162.75 | 1,815.00 / 2,783.40 / 2,996.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,167.00 / 2,637.80 / 2,715.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,063.00 / 2,565.60 / 2,682.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | 500 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 661.00 / 897.20 / 911.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | 500 m | 5 | 20.00 | 0.00 / 166.65 / 208.31 | 0.00 / 0.22 / 0.27 | 0.00 / 6.90 / 8.62 | 925.00 / 1,027.40 / 1,047.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | 1000 m | 5 | 40.00 | 0.00 / 768.91 / 957.97 | 0.00 / 2.51 / 3.12 | 0.00 / 1.01 / 1.27 | 359.00 / 682.60 / 710.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | 1000 m | 5 | 40.00 | 0.00 / 18.23 / 21.84 | 0.00 / 0.18 / 0.22 | 0.00 / 6.08 / 7.28 | 334.00 / 714.00 / 753.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | 1000 m | 5 | 60.00 | 352.66 / 635.06 / 640.58 | 0.24 / 1.02 / 1.07 | 0.00 / 656.83 / 766.63 | 248.00 / 304.40 / 305.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | 1000 m | 5 | 80.00 | 1.53 / 2,053.71 / 2,479.99 | 0.00 / 5.92 / 7.26 | 0.00 / 4,706.18 / 5,882.72 | 341.00 / 373.80 / 374.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 3,510.00 / 4,797.80 / 5,009.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 3,621.00 / 4,743.40 / 4,953.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | 1000 m | 5 | 40.00 | 0.00 / 68.06 / 83.31 | 0.00 / 0.02 / 0.03 | 0.00 / 2.47 / 3.09 | 1,378.00 / 2,154.40 / 2,276.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | 1000 m | 5 | 80.00 | 1.58 / 128.80 / 137.12 | 0.00 / 0.22 / 0.25 | 0.00 / 158.13 / 162.75 | 1,843.00 / 2,814.00 / 2,993.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,191.00 / 2,724.80 / 2,827.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,102.00 / 2,629.60 / 2,751.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 669.00 / 876.40 / 887.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | 1000 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 960.00 / 1,048.60 / 1,070.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | d + 50 m | 5 | 60.00 | 12.67 / 770.91 / 957.97 | 0.06 / 2.53 / 3.12 | 0.00 / 898.93 / 1,123.34 | 335.00 / 665.40 / 693.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | d + 50 m | 5 | 60.00 | 3.80 / 21.45 / 21.84 | 0.02 / 0.31 / 0.33 | 1.27 / 21.72 / 25.33 | 338.00 / 686.00 / 718.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | d + 50 m | 5 | 60.00 | 352.66 / 578.98 / 623.17 | 0.24 / 0.81 / 0.84 | 27.34 / 665.01 / 776.85 | 239.00 / 310.20 / 315.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | d + 50 m | 5 | 80.00 | 348.58 / 2,058.22 / 2,479.99 | 0.56 / 5.96 / 7.26 | 0.00 / 4,706.18 / 5,882.72 | 338.00 / 383.20 / 385.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | d + 50 m | 5 | 20.00 | 0.00 / 51.91 / 64.89 | 0.00 / 0.08 / 0.10 | 0.00 / 5.19 / 6.49 | 3,466.00 / 5,162.80 / 5,227.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | d + 50 m | 5 | 20.00 | 0.00 / 15.57 / 19.47 | 0.00 / 0.08 / 0.10 | 0.00 / 5.19 / 6.49 | 3,737.00 / 5,203.20 / 5,290.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | d + 50 m | 5 | 60.00 | 7.06 / 117.30 / 125.80 | 0.01 / 0.09 / 0.10 | 0.00 / 2.47 / 3.09 | 1,364.00 / 2,795.60 / 3,085.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | d + 50 m | 5 | 100.00 | 9.05 / 128.80 / 137.12 | 0.01 / 0.22 / 0.25 | 16.40 / 158.13 / 162.75 | 1,834.00 / 3,479.60 / 3,833.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,129.00 / 2,605.20 / 2,665.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | d + 50 m | 5 | 40.00 | 0.00 / 81.42 / 99.31 | 0.00 / 0.33 / 0.39 | 0.00 / 95.43 / 111.37 | 2,077.00 / 2,584.00 / 2,704.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | d + 50 m | 5 | 20.00 | 0.00 / 157.89 / 197.37 | 0.00 / 0.19 / 0.24 | 0.00 / 0.00 / 0.00 | 645.00 / 926.60 / 957.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | d + 50 m | 5 | 80.00 | 77.81 / 201.60 / 218.13 | 0.17 / 0.27 / 0.28 | 40.26 / 139.70 / 160.16 | 906.00 / 990.40 / 1,004.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | d + 100 m | 5 | 60.00 | 12.67 / 770.91 / 957.97 | 0.06 / 2.53 / 3.12 | 0.00 / 898.93 / 1,123.34 | 368.00 / 708.20 / 747.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | d + 100 m | 5 | 60.00 | 3.80 / 21.45 / 21.84 | 0.02 / 0.31 / 0.33 | 1.27 / 21.72 / 25.33 | 322.00 / 725.20 / 768.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | d + 100 m | 5 | 40.00 | 0.00 / 569.07 / 623.17 | 0.00 / 0.72 / 0.84 | 0.00 / 665.01 / 776.85 | 254.00 / 291.60 / 293.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | d + 100 m | 5 | 80.00 | 348.58 / 2,058.22 / 2,479.99 | 0.56 / 5.96 / 7.26 | 0.00 / 4,706.18 / 5,882.72 | 325.00 / 370.40 / 380.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 3,417.00 / 5,065.00 / 5,142.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 3,492.00 / 5,232.60 / 5,311.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | d + 100 m | 5 | 60.00 | 7.06 / 117.30 / 125.80 | 0.01 / 0.09 / 0.10 | 0.00 / 2.47 / 3.09 | 1,370.00 / 2,840.40 / 3,128.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | d + 100 m | 5 | 100.00 | 9.05 / 128.80 / 137.12 | 0.01 / 0.22 / 0.25 | 16.40 / 158.13 / 162.75 | 1,813.00 / 3,626.80 / 4,065.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,154.00 / 2,665.40 / 2,713.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | d + 100 m | 5 | 20.00 | 0.00 / 7.86 / 9.82 | 0.00 / 0.05 / 0.06 | 0.00 / 25.31 / 31.64 | 2,015.00 / 2,610.20 / 2,743.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | d + 100 m | 5 | 20.00 | 0.00 / 157.89 / 197.37 | 0.00 / 0.19 / 0.24 | 0.00 / 0.00 / 0.00 | 660.00 / 893.00 / 899.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | d + 100 m | 5 | 40.00 | 0.00 / 175.74 / 218.13 | 0.00 / 0.23 / 0.28 | 0.00 / 33.95 / 40.26 | 904.00 / 965.00 / 967.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | d + 250 m | 5 | 40.00 | 0.00 / 768.91 / 957.97 | 0.00 / 2.51 / 3.12 | 0.00 / 1.01 / 1.27 | 379.00 / 682.00 / 716.00 | 326.00 / 659.80 / 688.00 |
| abisko | kayak | d + 250 m | 5 | 40.00 | 0.00 / 18.23 / 21.84 | 0.00 / 0.18 / 0.22 | 0.00 / 6.08 / 7.28 | 350.00 / 690.20 / 726.00 | 307.00 / 640.80 / 672.00 |
| abisko | paths | d + 250 m | 5 | 40.00 | 0.00 / 560.91 / 612.98 | 0.00 / 0.71 / 0.82 | 0.00 / 656.83 / 766.63 | 258.00 / 290.00 / 291.00 | 626.00 / 799.80 / 800.00 |
| abisko | walking | d + 250 m | 5 | 80.00 | 149.17 / 2,050.81 / 2,476.37 | 0.30 / 5.91 / 7.25 | 0.00 / 4,794.18 / 5,874.41 | 347.00 / 390.60 / 396.00 | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 3,419.00 / 5,226.20 / 5,333.00 | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 3,754.00 / 5,261.00 / 5,362.00 | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | d + 250 m | 5 | 60.00 | 7.06 / 117.30 / 125.80 | 0.01 / 0.09 / 0.10 | 0.00 / 2.47 / 3.09 | 1,345.00 / 2,992.80 / 3,305.00 | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | d + 250 m | 5 | 100.00 | 9.05 / 128.80 / 137.12 | 0.01 / 0.22 / 0.25 | 16.40 / 158.13 / 162.75 | 1,822.00 / 3,662.60 / 4,115.00 | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,260.00 / 2,617.60 / 2,689.00 | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | d + 250 m | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 2,112.00 / 2,509.40 / 2,607.00 | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | d + 250 m | 5 | 20.00 | 0.00 / 157.89 / 197.37 | 0.00 / 0.19 / 0.24 | 0.00 / 0.00 / 0.00 | 718.00 / 873.20 / 880.00 | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | d + 250 m | 5 | 20.00 | 0.00 / 166.65 / 208.31 | 0.00 / 0.22 / 0.27 | 0.00 / 6.90 / 8.62 | 930.00 / 997.00 / 1,010.00 | 2,172.00 / 2,502.20 / 2,577.00 |
| abisko | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 326.00 / 659.80 / 688.00 |
| abisko | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 307.00 / 640.80 / 672.00 |
| abisko | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 626.00 / 799.80 / 800.00 |
| abisko | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 839.00 / 1,264.20 / 1,271.00 |
| lomsdal-visten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 3,407.00 / 4,463.40 / 4,613.00 |
| lomsdal-visten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 3,456.00 / 4,626.00 / 4,835.00 |
| lomsdal-visten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,893.00 / 4,803.40 / 5,094.00 |
| lomsdal-visten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 4,028.00 / 6,941.80 / 7,627.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,246.00 / 2,672.40 / 2,764.00 |
| malingsbo-kloten | kayak | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,003.00 / 2,505.60 / 2,606.00 |
| malingsbo-kloten | paths | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 1,339.00 / 2,384.20 / 2,449.00 |
| malingsbo-kloten | walking | Unlimited | 5 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 2,172.00 / 2,502.20 / 2,577.00 |

</details>

<details>
<summary>Kloten supplementary cases</summary>

| Map | Setting | Radius | n | Changed % | Primary excess p50 / p95 / max | Relative excess % p50 / p95 / max | Extra foot m p50 / p95 / max | Local ms p50 / p95 / max | Baseline ms p50 / p95 / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| malingsbo-kloten | kayak-paths | 0 | 12 | 100.00 | 448.46 / 510.84 / 510.84 | 106.44 / 139.73 / 139.73 | 80.82 / 88.11 / 88.11 | 10.00 / 15.35 / 17.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | 0 | 12 | 100.00 | 118.63 / 146.78 / 146.78 | 36.30 / 47.43 / 47.43 | 67.19 / 89.42 / 89.42 | 6.00 / 7.45 / 8.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | 0 | 12 | 100.00 | 663.39 / 754.57 / 760.17 | 32.92 / 100.62 / 104.19 | 107.31 / 140.48 / 140.77 | 116.50 / 226.90 / 228.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | 0 | 12 | 100.00 | 254.16 / 284.22 / 284.94 | 22.08 / 64.46 / 65.49 | 120.37 / 229.63 / 326.05 | 351.00 / 801.70 / 816.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | 50 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 6.50 / 8.00 / 8.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | 50 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 6.00 / 7.00 / 7.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | 50 m | 12 | 50.00 | 46.61 / 93.23 / 93.23 | 0.48 / 0.98 / 0.98 | 14.61 / 29.23 / 29.23 | 117.50 / 227.70 / 231.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | 50 m | 12 | 50.00 | 25.43 / 50.85 / 50.85 | 0.28 / 0.57 / 0.57 | 18.12 / 36.24 / 36.24 | 352.00 / 767.85 / 775.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 6.50 / 8.90 / 10.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 5.50 / 7.00 / 7.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 114.50 / 225.70 / 229.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 357.00 / 776.65 / 808.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 8.50 / 11.45 / 12.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 8.00 / 9.45 / 10.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 116.50 / 227.45 / 228.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 364.50 / 755.45 / 756.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | 500 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 13.00 / 19.90 / 21.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | 500 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 11.50 / 13.45 / 14.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | 500 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 129.00 / 250.25 / 253.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | 500 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 365.00 / 770.95 / 788.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | 1000 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 27.00 / 38.80 / 41.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | 1000 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 24.50 / 27.35 / 29.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | 1000 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 138.00 / 252.55 / 263.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | 1000 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 383.00 / 779.30 / 820.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | d + 50 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 6.50 / 8.00 / 8.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | d + 50 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 5.00 / 8.90 / 10.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | d + 50 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 113.00 / 233.65 / 243.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | d + 50 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 358.00 / 753.05 / 769.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | d + 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 6.50 / 8.45 / 9.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | d + 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 4.50 / 7.00 / 7.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | d + 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 112.50 / 222.00 / 233.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | d + 100 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 365.50 / 781.55 / 803.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | d + 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 8.00 / 12.35 / 14.00 | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | d + 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 7.00 / 10.90 / 12.00 | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | d + 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 120.00 / 227.60 / 232.00 | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | d + 250 m | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 350.00 / 762.15 / 766.00 | 703.50 / 1,524.85 / 1,543.00 |
| malingsbo-kloten | kayak-paths | Unlimited | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 23.00 / 32.45 / 33.00 |
| malingsbo-kloten | kayak | Unlimited | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 22.50 / 36.70 / 40.00 |
| malingsbo-kloten | paths | Unlimited | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 140.00 / 303.50 / 320.00 |
| malingsbo-kloten | walking | Unlimited | 12 | 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | — | 703.50 / 1,524.85 / 1,543.00 |

</details>

### Five worst cases per variant

Ranked by relative primary excess, then absolute primary excess, then secondary-price difference. Coordinates are latitude, longitude. Node spacing is distance along the missed edge between its real end nodes. Both omitted entry and exit segments are named when relevant.

**0**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| malingsbo-kloten / kayak-paths / Kloten / K2 | 59.895949196, 15.287872309 → 59.898026273, 15.288010427 | 510.84 / 139.73 | 87.49 | entry 45537: Topografi 50 roads (path), 222.361 m between nodes 11353–34155, segment 7.780 m away |
| malingsbo-kloten / kayak-paths / Kloten / K3 | 59.895949196, 15.287872309 → 59.952981501, 15.278743062 | 510.84 / 139.73 | 87.49 | entry 45537: Topografi 50 roads (path), 222.361 m between nodes 11353–34155, segment 7.780 m away |
| malingsbo-kloten / kayak-paths / Kloten / K6 | 59.895949196, 15.287800849 → 59.898026273, 15.288010427 | 500.66 / 124.06 | 87.57 | entry 45537: Topografi 50 roads (path), 222.361 m between nodes 11353–34155, segment 11.709 m away |
| malingsbo-kloten / kayak-paths / Kloten / K7 | 59.895949196, 15.287800849 → 59.952981501, 15.278743062 | 500.66 / 124.06 | 87.57 | entry 45537: Topografi 50 roads (path), 222.361 m between nodes 11353–34155, segment 11.709 m away |
| malingsbo-kloten / kayak-paths / Kloten / K0 | 59.895949196, 15.288158150 → 59.898026273, 15.288010427 | 413.00 / 111.96 | 74.14 | entry 45537: Topografi 50 roads (path), 222.361 m between nodes 11353–34155, segment 7.579 m away |

**50 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / walking / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364533, 18.686514024 | 3,107.84 / 20.06 | 160.23 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 959.774 m away; exit 43153: OSM (path), 3821.299 m between nodes 47864–20789, segment 303.373 m away |
| abisko / kayak-paths / 500 / 28 | 68.281888166, 18.170158248 → 68.213884244, 18.508006639 | 3,757.04 / 18.26 | 1,735.22 | exit 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 1121.362 m away |
| abisko / kayak-paths / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364981, 18.686485358 | 2,524.20 / 16.51 | 1,778.27 | entry 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 807.786 m away |
| malingsbo-kloten / kayak-paths / 2000 / 35 | 60.105749276, 15.761077078 → 59.958313555, 15.125712258 | 4,663.07 / 14.33 | -237.23 | entry 28120: Topografi 50 paths (path), 1364.487 m between nodes 22226–22227, segment 342.061 m away; exit 52996: Topografi 50 roads (path), 1189.074 m between nodes 40511–39380, segment 353.148 m away |
| abisko / paths / 8 / 1 | 68.436280001, 18.605527419 → 68.294653556, 18.828403346 | 3,200.19 / 11.94 | -272.05 | exit 44724: OSM (path), 1867.245 m between nodes 16602–21107, segment 490.741 m away |

**100 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / walking / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364533, 18.686514024 | 3,107.84 / 20.06 | 160.23 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 959.774 m away; exit 43153: OSM (path), 3821.299 m between nodes 47864–20789, segment 303.373 m away |
| abisko / kayak-paths / 500 / 28 | 68.281888166, 18.170158248 → 68.213884244, 18.508006639 | 3,757.04 / 18.26 | 1,735.22 | exit 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 1121.362 m away |
| abisko / kayak-paths / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364981, 18.686485358 | 2,524.20 / 16.51 | 1,778.27 | entry 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 807.786 m away |
| malingsbo-kloten / kayak-paths / 2000 / 35 | 60.105749276, 15.761077078 → 59.958313555, 15.125712258 | 4,663.07 / 14.33 | -237.23 | entry 28120: Topografi 50 paths (path), 1364.487 m between nodes 22226–22227, segment 342.061 m away; exit 52996: Topografi 50 roads (path), 1189.074 m between nodes 40511–39380, segment 353.148 m away |
| abisko / paths / 8 / 1 | 68.436280001, 18.605527419 → 68.294653556, 18.828403346 | 3,200.19 / 11.94 | -272.05 | exit 44724: OSM (path), 1867.245 m between nodes 16602–21107, segment 490.741 m away |

**250 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / kayak-paths / 500 / 28 | 68.281888166, 18.170158248 → 68.213884244, 18.508006639 | 3,757.04 / 18.26 | 1,735.22 | exit 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 1121.362 m away |
| abisko / kayak-paths / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364981, 18.686485358 | 2,524.20 / 16.51 | 1,778.27 | entry 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 807.786 m away |
| malingsbo-kloten / kayak-paths / 2000 / 35 | 60.105749276, 15.761077078 → 59.958313555, 15.125712258 | 4,663.07 / 14.33 | -237.23 | entry 28120: Topografi 50 paths (path), 1364.487 m between nodes 22226–22227, segment 342.061 m away; exit 52996: Topografi 50 roads (path), 1189.074 m between nodes 40511–39380, segment 353.148 m away |
| abisko / paths / 8 / 1 | 68.436280001, 18.605527419 → 68.294653556, 18.828403346 | 3,200.19 / 11.94 | -272.05 | exit 44724: OSM (path), 1867.245 m between nodes 16602–21107, segment 490.741 m away |
| abisko / walking / 500 / 27 | 68.335397446, 18.642474581 → 68.366090559, 19.020606436 | 3,093.17 / 11.57 | 552.13 | exit 35917: Topografi 50 roads (path), 2559.619 m between nodes 17513–19812, segment 1903.938 m away |

**500 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / kayak-paths / 500 / 28 | 68.281888166, 18.170158248 → 68.213884244, 18.508006639 | 3,757.04 / 18.26 | 1,735.22 | exit 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 1121.362 m away |
| abisko / kayak-paths / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364981, 18.686485358 | 2,524.20 / 16.51 | 1,778.27 | entry 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 807.786 m away |
| abisko / walking / 500 / 27 | 68.335397446, 18.642474581 → 68.366090559, 19.020606436 | 3,093.17 / 11.57 | 552.13 | exit 35917: Topografi 50 roads (path), 2559.619 m between nodes 17513–19812, segment 1903.938 m away |
| abisko / paths / 500 / 28 | 68.281888166, 18.170158248 → 68.213884244, 18.508006639 | 3,623.06 / 7.72 | 1,890.08 | exit 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 1123.042 m away |
| abisko / walking / 2000 / 36 | 68.213314847, 18.483170067 → 68.248758397, 18.852878054 | 2,479.99 / 7.26 | 5,882.72 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 2023.789 m away; exit 43158: OSM (path), 4845.640 m between nodes 20793–20794, segment 4054.364 m away |

**1000 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / kayak-paths / 500 / 28 | 68.281888166, 18.170158248 → 68.213884244, 18.508006639 | 3,757.04 / 18.26 | 1,735.22 | exit 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 1121.362 m away |
| abisko / walking / 500 / 27 | 68.335397446, 18.642474581 → 68.366090559, 19.020606436 | 3,093.17 / 11.57 | 552.13 | exit 35917: Topografi 50 roads (path), 2559.619 m between nodes 17513–19812, segment 1903.938 m away |
| abisko / paths / 500 / 28 | 68.281888166, 18.170158248 → 68.213884244, 18.508006639 | 3,623.06 / 7.72 | 1,890.08 | exit 39308: OSM (path), 4234.093 m between nodes 20282–5616, segment 1123.042 m away |
| abisko / walking / 2000 / 36 | 68.213314847, 18.483170067 → 68.248758397, 18.852878054 | 2,479.99 / 7.26 | 5,882.72 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 2023.789 m away; exit 43158: OSM (path), 4845.640 m between nodes 20793–20794, segment 4054.364 m away |
| abisko / kayak-paths / 250 / 21 | 68.239216741, 18.456345922 → 68.305848720, 18.391148087 | 1,037.01 / 7.17 | -48.57 | exit 40685: OSM (path), 1979.754 m between nodes 19319–20479, segment 1286.519 m away |

**d + 50 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / walking / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364533, 18.686514024 | 3,107.84 / 20.06 | 160.23 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 959.774 m away; exit 43153: OSM (path), 3821.299 m between nodes 47864–20789, segment 303.373 m away |
| abisko / paths / 8 / 1 | 68.436280001, 18.605527419 → 68.294653556, 18.828403346 | 3,200.19 / 11.94 | -272.05 | exit 44724: OSM (path), 1867.245 m between nodes 16602–21107, segment 490.741 m away |
| abisko / walking / 500 / 27 | 68.335397446, 18.642474581 → 68.366090559, 19.020606436 | 3,145.10 / 11.77 | 546.79 | entry 44581: OSM (path), 137.540 m between nodes 21085–20070, segment 247.297 m away; exit 35917: Topografi 50 roads (path), 2559.619 m between nodes 17513–19812, segment 1903.938 m away |
| abisko / paths / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364533, 18.686514024 | 1,885.27 / 7.89 | 101.77 | entry 4850: Leder (path), 49.732 m between nodes 4618–4619, segment 944.691 m away; exit 43153: OSM (path), 3821.299 m between nodes 47864–20789, segment 190.081 m away |
| abisko / walking / 2000 / 36 | 68.213314847, 18.483170067 → 68.248758397, 18.852878054 | 2,479.99 / 7.26 | 5,882.72 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 2023.789 m away; exit 43158: OSM (path), 4845.640 m between nodes 20793–20794, segment 4054.364 m away |

**d + 100 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / walking / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364533, 18.686514024 | 3,107.84 / 20.06 | 160.23 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 959.774 m away; exit 43153: OSM (path), 3821.299 m between nodes 47864–20789, segment 303.373 m away |
| abisko / paths / 8 / 1 | 68.436280001, 18.605527419 → 68.294653556, 18.828403346 | 3,200.19 / 11.94 | -272.05 | exit 44724: OSM (path), 1867.245 m between nodes 16602–21107, segment 490.741 m away |
| abisko / walking / 500 / 27 | 68.335397446, 18.642474581 → 68.366090559, 19.020606436 | 3,093.17 / 11.57 | 552.13 | exit 35917: Topografi 50 roads (path), 2559.619 m between nodes 17513–19812, segment 1903.938 m away |
| abisko / paths / 1000 / 31 | 68.208643782, 18.505901262 → 68.240364533, 18.686514024 | 1,885.27 / 7.89 | 101.77 | entry 4850: Leder (path), 49.732 m between nodes 4618–4619, segment 944.691 m away; exit 43153: OSM (path), 3821.299 m between nodes 47864–20789, segment 190.081 m away |
| abisko / walking / 2000 / 36 | 68.213314847, 18.483170067 → 68.248758397, 18.852878054 | 2,479.99 / 7.26 | 5,882.72 | entry 4855: Leder (path), 37.165 m between nodes 4623–4624, segment 2023.789 m away; exit 43158: OSM (path), 4845.640 m between nodes 20793–20794, segment 4054.364 m away |

**d + 250 m**

| Map / setting / bin / case | Start → target (lat, lon) | Primary excess / % | Extra foot m | Missed edge: source, kind, spacing, distance to segment |
| --- | --- | --- | --- | --- |
| abisko / walking / 500 / 27 | 68.335397446, 18.642474581 → 68.366090559, 19.020606436 | 3,093.17 / 11.57 | 552.13 | exit 35917: Topografi 50 roads (path), 2559.619 m between nodes 17513–19812, segment 1903.938 m away |
| abisko / walking / 2000 / 36 | 68.213314847, 18.483170067 → 68.248758397, 18.852878054 | 2,476.37 / 7.25 | 5,874.41 | exit 43158: OSM (path), 4845.640 m between nodes 20793–20794, segment 4054.364 m away |
| abisko / kayak-paths / 250 / 21 | 68.239216741, 18.456345922 → 68.305848720, 18.391148087 | 1,037.01 / 7.17 | -48.57 | exit 40685: OSM (path), 1979.754 m between nodes 19319–20479, segment 1286.519 m away |
| lomsdal-visten / paths / 20 / 5 | 65.383644143, 12.640774193 → 65.313491029, 12.250103293 | 9,020.27 / 6.65 | 2,060.39 | exit 150348: N50 paths (path), 1111.780 m between nodes 95217–58469, segment 10370.538 m away |
| abisko / paths / 500 / 27 | 68.335397446, 18.642474581 → 68.366090559, 19.020606436 | 2,224.61 / 5.50 | 133.54 | exit 35917: Topografi 50 roads (path), 2559.619 m between nodes 17513–19812, segment 1721.697 m away |

**Unlimited**

No differing cases.


### Checks and retained evidence

All 528 rows have finite labels. R=0 matches today's land price, secondary
price and physical foot distance exactly. All nested fixed and relative
candidate sets have non-increasing primary prices, no local primary price
beats unlimited beyond the 0.01 comparison precision, and selected local
entry/exit segments satisfy their endpoint's radius. No near-equal-land
secondary-price tie is flagged by the result audit.

The connector audit checks **48,000 individual connectors**,
4,000 per map/setting, between sampled endpoints and deterministically
selected graph nodes, in both directions. The integer wet count equals the
sample-by-sample loop for every audited connector, including kayak dam
handling. The largest price difference is **0**, even before rounding.
This is a sampled connector audit, not a claim that every connector visited
by every search was separately audited. The **18** saved unbounded-reference
cases checked after introducing the feasible-route ceiling have exactly
equal land price, secondary price and carry, with largest differences **0**.
The Norway first-case results also agree with their saved unbounded pilots.

The large Abisko walking-distance change is checked separately by restricting
the independent reference to R=0, fixed 1000 m and d + 250 m on that pair.
All three costs match exactly; the largest foot-distance difference is
**7.28 × 10⁻¹¹ m**. This confirms that the long walk comes from the candidate
set and weighted objective, rather than the route-accounting helper.

Evidence is under `~/mockups/kayak-mode/phase11/radius/`:

- `spatial.js`, `prepare.py`, `engine.js`, `reference.js`, `probe.js` and
  `run.py` define the indexed local variants, independent reference,
  sampling, price accounting and browser harness. Each completed map's
  `results/<map>/probe.js` freezes the script it executed; the earlier
  unbounded scripts are retained too.
- `*-samples-5.json` retain every source edge, perpendicular construction,
  accepted coordinate, actual displacement, nearest walking distance,
  seed, attempt number and frozen target index.
- `results/<map>/<setting>.jsonl` retain all answers, both nearest-network
  distances, local/baseline timings and the unlimited winner's entry/exit
  metadata. `*-audit.json` hold the connector checks; `metadata.json` hold
  page/script hashes, browser version and page errors.
- `verification/`, `verify-ceiling.log`, `checks.json` and `validation.json`
  retain the independent-ceiling comparisons and matrix checks.
- `verify-foot.py`, `foot-verification.js`, `foot-verification.json` and
  `verify-foot.log` retain the separate restricted-reference distance check.
- `summary.json`, `manifest.json`, `summarize.py`, `support-tables.py`,
  `finalize.py` and `assemble.py` retain the calculations and evidence
  hashes. `planned-leg-lengths.json` records the straight-leg context.

The unchanged timed local engine SHA-256 is
`573cd80be06865bb0496418db86914c0314d0ef322fe59421de4f9ab7e8365e1`.
Firefox is **153.0**, driven by Playwright **1.62.0**. The original pages
and phase-10 pair files are identified by the recorded hashes. The route
accounting helper's zero-length-edge handling was corrected during the
pilot; pilot local measurements are excluded from every result table.

Production, tests, stored-plan behaviour and shared caches remain unchanged.
No build, drive, graph work, publication or radius implementation was done.
The old phase-11 implementation checks remain pending a radius decision;
this study neither replaces them nor marks phase 11 built.

### Recommendation for Uwe

**My recommendation, not a decision: d + 250 m.** It gives an endpoint
access to the closest trail even when the endpoint is farther away than a
fixed radius. Among the tested local variants, it has the lowest p95 and
maximum relative primary loss: **1.04% / 11.57%**, against **1.24% / 18.26%**
for fixed 1000 m. Their slowest local p95 timings are similar, **5.22 s**
and **5.18 s**. Fixed 1000 m does match more cases exactly: its changed
share is **26.89%**, against **30.11%** for d + 250 m.

The remaining loss is material. In particular, the **17.37 km** extra-walking
case above must be considered alongside the price statistics; this
recommendation follows the accepted weighted objective and does not
promise shorter walking routes.

This is a recommendation between the tested choices, not evidence that
250 m is a universally correct allowance. Five points per requested bin,
only one generated start truly beyond 1 km, and park-sized graphs limit the
inference. Uwe must decide whether the measured price and distance losses are acceptable and
which radius rule to adopt. No radius is selected by this record.

### Table for Uwe

All 528 case-settings. For each local variant, the timing cell is the map/setting with its largest measured local p95; the baseline is today’s search on those same cases. R=0 local includes the scratch walking batching, so it is also the control for that optimisation. This table records a tradeoff, not a radius decision.

| Radius | Changed against unlimited | Worst relative primary excess | Slowest local map / setting | p95 ms, today → local |
| --- | --- | --- | --- | --- |
| 0 | 87.69% | 139.73% | lomsdal-visten / kayak | 4,895.15 → 5,089.15 |
| 50 m | 62.50% | 20.06% | lomsdal-visten / kayak | 4,895.15 → 4,996.70 |
| 100 m | 55.11% | 20.06% | lomsdal-visten / kayak | 4,895.15 → 4,956.80 |
| 250 m | 49.24% | 18.26% | lomsdal-visten / kayak | 4,895.15 → 5,196.25 |
| 500 m | 37.31% | 18.26% | lomsdal-visten / kayak | 4,895.15 → 5,033.50 |
| 1000 m | 26.89% | 18.26% | lomsdal-visten / kayak | 4,895.15 → 5,183.95 |
| d + 50 m | 39.20% | 20.06% | lomsdal-visten / kayak | 4,895.15 → 5,220.65 |
| d + 100 m | 34.66% | 20.06% | lomsdal-visten / kayak | 4,895.15 → 5,305.30 |
| d + 250 m | 30.11% | 11.57% | lomsdal-visten / kayak-paths | 4,615.60 → 5,224.45 |
| Unlimited | 0.00% | 0.00% | — | Untimed reference |

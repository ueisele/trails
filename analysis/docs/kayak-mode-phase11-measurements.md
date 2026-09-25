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

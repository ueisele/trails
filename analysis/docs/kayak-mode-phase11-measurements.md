# Phase 11 measurements

**Stopped at the speed gate, 2026-09-25. Phase 11 is not built.** The
prototype improves the Kloten entries, but Abisko kayak p95 rises by
3.245×. Production source and tests are restored; these measurements
describe a browser prototype, not the shipped planner.

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

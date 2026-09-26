# The kayak line off the bank, in phases

*Drafted 2026-09-25. **Approved by Uwe the same day**: “Zum Plan für den Abstand zum Ufer:
Ja genau so wie vorgeschlagen” (“On the plan for the distance from the bank: yes, exactly as
proposed”). It covers the five decisions §1 put to him — the distance, the precision, the
narrows, islands and bays, the snapping, and the resource budgets — each as recommended. On
2026-09-26 he decided that edge entries go first, which they did as phase 11 of
`kayak-mode-phases.md`, and then that this line starts now. The decisions are recorded in
`kayak-mode-decisions.md` §5; the built-notes of these phases go under their phase below.*

The next kayak step **after phases 10 and 11 on main (`6de243c`)**: follow a line about 15 m off
the bank, and the middle where the water is narrower than 30 m. Uwe, 2026-09-24:
“Normalerweise ist man schon mindestens 10 bis 20 Meter davon entfernt.” This changes the
routed geometry, its measured length and its drawing together.

The plan was written in scratch (`~/mockups/kayak-mode/offset-plan/`) without changing
this repository, building a graph or page, or starting a browser or geometry job. All
measured figures in §1–§4 are the evidence that existed then; estimates and proposed budgets
are labelled. Local geometry probes run alone in one process, under a **4 GiB address-space
limit**.

## 1. Decided

*Approved by Uwe, 2026-09-25: "Zum Plan für den Abstand zum Ufer: Ja genau so wie vorgeschlagen" — all five decisions of §1 as recommended (fixed 15 m with a small 10/20 m geometry comparison, 2 m contours with ≥ 12 m clearance, all connections kept with pruned centre lines, near-bank taps snap to the offshore line, the §4 budgets). The plan named a phase for arbitrary entry points on an edge (the optimal entry per segment, cos θ = path factor / ground factor) as the step after it; Uwe put it first, and it is built as phase 11 of `kayak-mode-phases.md`. After this plan come per-leg modes.*

Uwe's answers are recorded here and in `kayak-mode-decisions.md` §5, distinct from
implementation and review choices.

1. **15 m is the fixed starting preference.** Use one build constant, `PADDLE_OFFSET_M =
   15`, on all three maps, with no new switch or slider. Unlike k and P, this figure comes
   directly from Uwe's requested distance: route-price sweeps cannot establish a preferred
   physical clearance. Do a small **10 / 15 / 20 m geometry sensitivity comparison** on the
   same representative water bodies before implementation, but no nine-page sweep and no
   automatic selection of the cheapest variant. Keep 15 unless the evidence reveals a
   conflict requiring Uwe's decision. Estimated cost: three local geometry variants, one
   production variant; full centre-line/graph costs remain to be measured.
2. **Offset real water, then simplify and validate.** Use the unsimplified dissolved
   Marktäcke water in Sweden and N50 in Norway, retaining phase 9's 1 cm dissolution,
   connected-body 1 ha eligibility before clipping, islands, lake ownership and levels.
   Compute the negative buffer of the complete connected water, without treating lake/river
   interfaces, delivery seams, map cuts or dam-disc edges as banks. Start the new contours
   at **2 m simplification**, locally retain more vertices when validation requires it.
   Phase 9's 5 m bank simplification is not an inherited clearance guarantee: 15 − 5 leaves
   only 10 m. The new decoded ordinary offset line must stay at least **12 m from the
   source bank**, with at most 2.1 m deviation from its unsimplified offset contour.
   Estimated contour scale: about 32k / 84k / 119k vertices for Abisko / MK / Norway,
   before centre lines, joins, chords and noding (§3).
3. **Where the offset disappears, paddle through the middle.** Construct a Euclidean
   medial-axis approximation from constrained boundary-segment Voronoi geometry, locally
   refined and pruned. Use it through narrows, vanished eligible water bodies, island
   passages and terminal bays; do not fall back to the bank or insert a carry because a
   buffer vanished. Preserve every existing valid water connection, both alternative
   passages around an island, and access to the ends of meaningful bays. Prune only
   decorative branches with no access, passage, island cycle or bay coverage to preserve.
   This is the largest new implementation task: **two geometry runs**, plus integration;
   the existing study gives lower bounds of 620 / 513 / 875 reconnecting links at 15 m,
   not an actual skeleton count. A simple spanning tree is insufficient.
4. **Keep the bank access points and paddle the last water metres.** Retain phase-10
   launch anchors, existing portage landings, all walking-network contacts with water,
   stream mouths and dam-side access. Add contained paddled spurs from those anchors to
   the offset or centre line. The launch's land distance is still at most 30 m, measured
   **to the bank**, and keeps phase 10's path price; the water spur is additional and does
   not consume that allowance. A portage's land part is not lengthened by moving its
   water end offshore. Typical broad-water addition: about 15 m per bank, about 30 m for
   a two-ended carry; these are geometric estimates, not caps or measured averages.
5. **The prices keep their meaning.** Offset contours remain `Shore`, factor 1. Add
   `Narrow water` as a separate PADDLE source at factor 1 and `Landing water` for paddled
   access spurs at factor 1. Open crossings remain `Open water`, factor 1.5, between the
   new lines. Exact lake/river mouth interfaces remain lake-owned Open water; an offset
   must not manufacture cheap bay-mouth crossings. Phase 8's water-first ordering and
   phase 10's **land-price primary objective** stand: ground follows Stay on paths at
   3 / 10, mapped ways use their walking factors, launches use path price, P = 2 remains
   only in the existing secondary rule. No new crossing or exposure policy.
6. **A normal near-bank water tap selects the offshore line.** Prefer Shore or Narrow
   water for automatic water snapping near the bank; do not snap to retained bank anchors
   or the bank end of a Landing water spur. Give these automatic water candidates a
   minimum reach of **d + 2.1 m (17.1 m at d = 15)** so a high-zoom tap at the bank can
   still find the displaced line. Preserve deliberate land/path/launch starts
   and explicitly selected positions. A point deliberately placed out on the lake still
   reaches that water point under the existing off-network rules. Profiles and tallies
   include the actual water spurs and retain the phase-10 panel's whole-length split.
   Estimated payload cost for source roles: a few header fields; no second bank polygon
   layer or finer whole-map grid in the page.
7. **Approve measured limits before full builds.** Release budgets against the frozen
   baseline, main `6de243c` with phases 10 and 11 (phase 12a below): at most **50% more graph
   nodes, edges and encoded vertices**; at most **+0.5 / +1.0 / +1.5 MB Brotli per page** for
   Abisko / MK / Norway; kayak p95 at most `max(1.5 × baseline p95, 300 ms)` in each
   Stay-on-paths setting. These are
   engineering allowances, not predictions. Exceeding one stops for a concrete explanation
   and options, without weakening connectivity or changing the figure silently. Phone
   timings are measured separately, not inferred from desktop Firefox.

### Uwe's decisions, with recommendations

| Decision | Recommendation | Cost or consequence of choosing it |
|---|---|---|
| Fixed 15 m, or choose through a full 10/15/20 route sweep? | Fixed 15 m plus a small geometry comparison. | One final variant. A full sweep multiplies three-map builds and reference replays roughly threefold; it can compare consequences but cannot choose Uwe's preferred distance. |
| How much geometric precision? | New contours at 2 m, locally refined, decoded clearance ≥12 m in ordinary water. | Around 32k / 84k / 119k contour vertices in the existing proxy, more where validation repairs geometry. Keeping 5 m everywhere cannot promise this clearance. |
| What happens in narrows, around islands and inside vanished bays? | Pruned centre lines, all connections and island alternatives retained; keep terminal bay branches ≥30 m and every anchored branch, however short. | New geometry algorithm and topology audit; at least hundreds of joins per map. Only shorter unanchored indentations may be pruned; their counts and largest examples are reviewed. |
| What do the new lines cost and say? | Shore 1, Narrow water 1, Landing water 1, Open water 1.5; phase 10 otherwise unchanged. | Two source entries and explicit source totals; geometry can change chosen routes even with unchanged prices. |
| How should automatic near-bank water snapping work? | Offshore contour/centre line first, with minimum water-candidate reach 17.1 m; preserve explicit land and launch starts. | A focused browser change and ambiguous-tap fixtures; avoids snapping to the retained bank spur even at high zoom. |
| Resource allowance for the later full implementation? | Approve §4 budgets and, only after phase 10 finishes (it has, and phase 11 after it), sequential full builds under the historical **8 GiB** address-space cap. Keep local geometry probes at 4 GiB. | This is a proposal for future execution, **not permission to consume that memory now**. The old Norway build already peaked around 4.2 GB RSS; full builds under a 4 GiB address-space cap are not a credible promise. If 4 GiB must remain the future cap, insert a separate memory-reduction phase before full-map validation. |
| Scope and rollout? | All three maps, one reviewed phase at a time, release only after topology, prices and drives pass. | About ten bounded implementation/validation runs (§5), with the final review separate. No intermediate pure-buffer release. |

## 2. How to work through them

Read the phase-10 and phase-11 built-notes in `kayak-mode-phases.md` and their measurement
files first. Phase 10's brief's fixed ground factor 10 was superseded by Uwe: **Stay on paths
controls 3 / 10 in kayak too**. The merged launch kind is `LAUNCH`, source `Launches`, in
`libs/src/trails/network/launches.py`, with the measured 100 m passing-road spacing; phase 11
adds interior entries within d + 250 m of an off-network endpoint and changes no graph.

One phase per implementation run and worktree, reviewed by the session, which stops at its
end. The reviewing session checks the diff, owns acceptance readings and landing onto main
under the existing worktree rules. Read `maps.py` and `plan_mode.js` by region. Do not run
agents or measurements in parallel. Full builds wait for the resource allowance of §1.
Use cached inputs; no source downloads, tile builds, shared-cache writes, push or
publication are implied by this plan.

Keep evidence in scratch under `~/mockups/kayak-mode/offset-plan/phase-12*/`, with input hashes,
commit, source CRS, limits, wall time, peak RSS, machine/browser versions and reproduction
commands. A local measurement launches its worker with `ulimit -v 4194304`, single-thread
numeric libraries and no child workers; a limit failure is a stop, not a reason to lift the
cap. Do not install a geometry stack or run a whole-map union during this planning session.

Before integration, geometry-only results do not count as built graphs or driven pages.
Temporary synthetic payloads test contracts; intermediate production pages must not present
an incomplete offset network as usable. Only the completed variant gets full-map builds.
Later `command make hooks-run` and browser drives are part of review; neither belongs to
this document-writing task.

## 3. What was measured, and what remains an estimate

Evidence: [the kayak phase plan](kayak-mode-phases.md) §1 and phases 1, 1b, 2, 2b, 7, 8, 9;
the phase-10 brief and amendment (scratch: `~/mockups/kayak-mode/prompts/phase-10.md`,
`phase-10-review-extra.md`); the shore investigation (scratch:
`~/mockups/kayak-mode/shore-line/report.md`) §B.3–5; the phase-9 sweep report (scratch:
`~/mockups/kayak-mode/phase9/report.md`) and, for accepted final figures, the phase-9
**Built 2026-09-25** notes in the phase plan and the [decision record](kayak-mode-decisions.md).
Historical trials in the sweep report are not the final release. No new runtime measurements
were made for the plan; phase 12a's are its own.

### 3.1 A buffer alone loses too much

The original source experiments at 15 m retained a nearby contour for **90.50% / 73.90% /
83.93%** of the original bank in MK / Abisko / Norway. They lost **2 / 12 / 4** whole
eligible bodies and split **120 / 106 / 380** bodies. Island-ring counts fell from
**629 → 300 / 419 → 123 / 1,752 → 675**. Disappearing rings do not mean disappearing
physical islands: expanded island exclusions merge with one another or with the bank.

Those first two maps used the study's older Topografi 50 experiment and eligibility
conventions. They are warnings, **not phase-10 production inventories**. The separate
finer Swedish 15 m experiment split **130 MK / 95 Abisko** bodies and needed at least
**513 / 620** reconnecting links; N50 needed at least **875**. These counts keep remnants
≥1 m². They omit terminal bays and some island alternatives, and can fall when larger
offsets erase residual pools. Do not use either the count or its remnant threshold to
prune the production network.

| Existing contour proxy, simplify 2 m | 10 m vertices / Brotli bytes | 15 m vertices / Brotli bytes | 20 m vertices / Brotli bytes |
|---|---:|---:|---:|
| Abisko, finer Swedish source | 38,465 / 249,280 | 31,890 / 207,161 | 27,768 / 180,596 |
| MK, finer Swedish source | 93,281 / 617,873 | 84,140 / 558,320 | 77,424 / 514,888 |
| Norway, N50 | 133,254 / 890,891 | 119,127 / 798,479 | 106,772 / 716,915 |

These are compact coordinate-array JSON compressed at Brotli quality 9, **not production
graph or page bytes**, and do not contain centre lines, spurs, chords, heights or graph
noding. At 15 m the raw N50 buffer had 574,250 vertices before simplification. Processing
one body or bounded patch at a time is therefore part of the proposed implementation.

The finer Swedish 5 m bank proxies were 28,604 / 62,387 vertices and 190,252 / 418,282
bytes (Abisko / MK). Their 15 m offset proxies therefore add about **3.3k / 21.8k vertices**
and **17k / 140k proxy bytes**, before the unmeasured additions. That supports trying the
offset; it does not establish that the complete feature meets the page budgets.

### 3.2 Access points and the grid

The old-source endpoint diagnostic found 227 MK / 145 Abisko class-2 endpoints within 2 m
of a bank. At 15 m their nearest surviving contour was at median **44 / 146 m**, p95
**693 / 2,423 m**, maximum **1,664 / 3,804 m**. These are raw endpoint diagnostics, not
identities of final joins. Extending every stream by 15 m or to its global nearest contour
would miss vanished narrows and can connect the wrong arm of a lake.

The 25 m grid and 5 m public profile posts disagree near boundaries by design. In the old
grid experiment about **0.43 / 0.47 / 0.43%** of 15 m contour samples were in dry grid
cells for MK / Abisko / Norway. Finer Swedish 15 m contours had zero sampled points on
their own source land, but **0.89 / 1.67%** dry samples against that experiment's existing
grid. None of these percentages is a measurement against the final phase-10 grid.
Interior contours should remove most boundary questions; they cannot prove that every
connector or centre-line sample is classified wet by a 25 m grid.

### 3.3 The phase-9 baseline the plan was written against

*History. These were the latest completed figures when the plan was written. Phase 12a
replaces them with the frozen baseline of main `6de243c`, phases 10 and 11 together,
recorded [under phase 12a](#phase-12a--freeze-the-baseline-and-make-the-small-evidence-set).
Later phases compare against that, not against this table.*

| Map | Final phase-9 edges | Graph / page MB Brotli q11 | Final kayak p95 ms |
|---|---:|---:|---:|
| Abisko | 105,088 | 1.683781 / 2.188990 | 261.350 |
| MK | 289,548 | 5.724069 / 7.943361 | 1,709.400 |
| Norway | 398,191 | 6.016864 / 7.727324 | 2,772.950 |

MB are decimal. Phase 9's final costs include stream repairs, lake-owned mouths and dam
discs; its earlier 236 / 1,400 / 2,495 ms tolerance-sweep timings do not. All 1,800 final
labels matched the reference: 200/map for kayak, walking and Stay on paths. Phase 10 adds
launches and another kayak switch setting, and phase 11 interior entries; their final graph
and per-setting timings are the actual comparison baseline (phase 12a).

MK had 108 dam/lock points, 98 discs meeting eligible water. Its final graph had no PADDLE
edges entering discs; Korslång's two directions each paddled **1,184.863 m** and carried
**115.352 m**. The three repaired MK stream joins were near **(59.758503, 15.163257)**,
**(59.950575, 15.032432)** and **(59.984282, 15.005697)**. Abisko's exact shared mouths
had one lake-level copy and all 417 samples of its bank fixture read **342 m**.

The final decision record also counts **33 Abisko / 50 MK former stream-to-shore joins**,
all retained on the same stream. Final portage water-landing ends numbered **782 / 1,286 /
1,883** for Abisko / MK / Norway, before phase-10 launches. These are endpoint counts,
not deduplicated new-spur counts. If each needed a 15 m spur, that would represent about
**11.7 / 19.3 / 28.2 km** of additional network water geometry: an illustrative estimate,
not added distance on one trip. Some ends belong to streams or share anchors. Phase 9
also identified two MK and one Norway non-water ends as map crops; preserve their crop
classification rather than forcing them into the landing audit. Norway has no dam-point
input in this source set; keeping its existing exclusions does not certify an absence of dams.

### 3.4 Estimated implementation and runtime cost

Plan for six implementation/preflight runs, three map-validation runs and a final release
review. Centre-line construction and preserving contact identities are the uncertain work;
if either phase cannot finish within one run, split it by the stated deliverable before
starting the next, rather than folding integration into an unfinished geometry experiment.

Expect contour vertices in the measured range above, and **hundreds to thousands of
centre-line branches and access spurs per map** (engineering estimate, not a count).
A typical broad-water spur may need only its endpoints, while an inlet needs intermediate
vertices. Proposed capacity envelopes are up to 1.5× the baseline's nodes/edges/vertices and the
page increments in §1. They budget for extra detail and noding, not merely two source names.
Measure build time and memory per component; aim for total final build time ≤1.5× the baseline's,
and stop to investigate if it exceeds 2× on comparable cached runs. Do not extrapolate
search time linearly from edge count: water connectivity and entry candidates also matter.

## 4. Construction, reader properties and release gates

### 4.1 Geometry and topology contract

Keep two separate build products: **the physical bank/access geometry** and **the paddled
network**. The bank remains build-time input for launch eligibility, portage endpoints,
land obstacles and contact identity; it is no longer the cheap travel ring. In particular,
`water.portages()` currently reconstructs obstacle surfaces from Shore rings and measures
between paddle components. Doing that on offshore rings would shrink obstacles, lengthen
land ties and change eligible carries. Refactor it to consume explicit original water/body
and bank-anchor data. Retain phase 1b's Delaunay-neighbour rule, ≤1 km carry limit, exclusion
of intervening third water and ≤150 m walking ties. Apply those distances to their original
land-side geometry, with dam-side boundaries handled as phase 9 does. Preserve phase 10's
accepted launch spacing/deduplication and every existing valid launch.

Build the offset from the whole eligible water union, then split its geometry by the
retained lake/river ownership for height attribution. Do not erode each level group separately:
that would create a fictitious setback at a lake mouth. Work before map clipping, or with
a proven sufficient source halo; crop edges never gain Shore status. Keep genuine island
holes regardless of their own area; the 1 ha rule applies to water bodies, not islands or
buffer remnants. Union repairs must report collapsed positive-width passages and point-only
contacts; never invent a paddlable width to make a diagnostic pass.

Use a segment-based medial-axis/Voronoi construction, or a locally refined approximation
whose midpoint accuracy is validated against the original boundary segments. A polygon
straight skeleton or a Voronoi diagram of sparsely sampled vertices alone is not the
chosen Euclidean middle. No uniform 25 m or finer whole-map distance raster is proposed.
Prototype the available implementation locally; if a new native dependency is needed,
report its build/distribution cost in phase 12b before adopting it.

Retain the skeleton where clearance is below 15 m, together with short transition paths
to the contours. In a straight channel of width w <30 m the line is approximately w/2
from both banks. Pin branch junctions, contour joins, access and mouth anchors before
simplification. Prune only after marking through passages, required island cycles and
terminal bay branches. A terminal bay is retained if its unsimplified centre branch is
at least **30 m** long from the contour transition, or contains any old access/mouth/contact
anchor; shorter unanchored indentations may be pruned. This 30 m is a proposed pruning
scale (2d), not a navigability rule. Report discarded count/length and largest examples.
An eligible body whose buffer vanishes entirely still gets its pruned centre network.

Maintain a correspondence from original bank runs to their offset/centre paths. Detect
buffer caps where a vanished bay is closed: a span between distinct bay shoulders is
an Open water crossing at 1.5, not a new factor-1 Shore shortcut. Keep a factor-1 route
into a retained bay along its centre branch. Opposing banks in a genuinely narrow arm
may map to the same centre line; this deliberate merging differs from a straight cap
across a wide bay mouth. Classify using boundary generators and topology, not length alone.

**No connection lost** means more than equal component counts: inventory phase-10 bank
contacts and directed stream entry/exit anchors with source identity, station, body and dam
side; map each to the new network. Within each undirected surface component prove all those
anchors stay connected by water; across streams compare permitted directed reachability,
using component contraction rather than a quadratic all-node matrix. Separately retain
island-passage witnesses on each side of each island/channel group and terminal bay reach.
The same two points can remain connected while their only island passage is lost. Do not
identify a join merely by whichever new feature is nearest. A baseline connection requiring
actual land crossing is a documented conflict for review, not permission to create dry
PADDLE geometry. No legitimate connection may be dropped for the payload budget.

### 4.2 Contacts, crossings and barriers

| Contact or edge | Proposed treatment | What review proves |
|---|---|---|
| Phase-10 road/path launch | Preserve land anchor/tie and its kind/price. Add Landing water from the bank to its own contour/centre line. | A road end 25 m from the bank still qualifies even if the offset is 40 m away. The ≤30 m land limit and accepted spacing are unchanged; no launch crosses other water or a dam disc. |
| Portage landing and walking contact | Preserve the terrestrial endpoint/contact, attach a water-contained Landing water spur. Include direct path/shore intersections, not only named portage sources. | Same bank and path access; spur metres count as paddle, not ground or launch discount. No new carry across a vanished-buffer gap. |
| Class-2 stream mouth | Keep cut stream and phase-7 chain decision; join its actual surface-side mouth through water to a contour or centre line. | Correct downstream entry/exit and level two-way travel; no direction flipped or reopened by new short edge segmentation. Include all three phase-9 repaired MK joins. |
| Shared lake/river interface | One exact lake-owned Open water interface, noded to the new network by contained Open water links where necessary. Retain lake plane on the shared interface, river samples beyond it. | No duplicate river-height copy, invented bank or factor-1 seam. Offset pieces genuinely following a physical bank may cross that interface without becoming artificial mouth rings. |
| Dam/lock disc | Apply existing 25 m stream cuts and final analytic disc exclusion to contours, skeleton, chords, mouth links and spurs. Keep disc-side portage anchors. | No water edge inside a disc after encoding; no cheap ring around its artificial boundary. Existing connector disc-as-land sampling remains in production and reference. |
| Open-water chord | Generate sparse candidate chords between offset/centre vertices in the same real water body; preserve interfaces explicitly. Validate against unsimplified water minus dam discs. | No land/island shortcut, accidental cheap cap, or quadratic all-pairs generation. Chords can cross the 15 m margin where water-contained; their factor remains 1.5. |

Use a straight spur only when it is contained in the correct water region. Otherwise follow
a validated local route through the centre network. Do not draw a kilometre-long nearest
join across a headland because the local offset vanished. An unresolved anchor stops the
phase with coordinates and candidate geometry. Stream-line interiors outside mapped water
surfaces remain valid under the existing class-2 policy; they are not required to fit a
lake polygon. The exact-water containment rule applies to newly generated **surface-derived**
edges and joins. Existing stream geometry, heights and direction policy are not redesigned.

### 4.3 Prices, snapping, profile and tally

For all new PADDLE sources the primary label is zero. Secondary weighted metres are
`Shore ×1 + Narrow water ×1 + Landing water ×1 + Open water ×1.5`, with existing Streams,
ferries, walking, PORTAGE and Launches priced exactly as final phase 10. Retain the true
lexicographic comparison and partial-edge costs in forward/reverse searches, heaps, floors
and direct comparisons. Do not introduce a shore-distance penalty or retune k or P.

Water-first is **zero router land price beats any positive land price**, in both switch
settings. It is not a claim that the public on-foot tally must always be exactly zero.
Network PADDLE source metres stay paddled even where a coarse grid cell is dry; straight
connectors retain 25 m midpoint pricing, 5 m public sampling and the dam-disc override.
Do not relabel water spurs as grid-priced connectors. Report router primary price, router
dry metres, secondary price and public paddle/foot metres separately. Retain the existing
phase-8 allowance of one grid cell per connector end on its fixtures; do not convert a
weighted land price back to metres or impose that allowance on arbitrary routes as a new
universal theorem. Exact connector inland distance and longest dry runs are diagnostics.

Automatic snapping needs a source-role predicate, not just `kind == PADDLE`: otherwise the
new Landing water source leaves the nearest available point on the bank. With a water-only
reach of `min(PLAN.snapM, max(callerReach, d + 2.1 m))`, an ordinary water candidate near Shore/Narrow water selects
the nearest of those travel lines; Landing water and standalone bank-anchor nodes are
excluded from ordinary water candidates. Keep Streams available for river taps. Keep
Open water available for deliberate open-lake positions and normal fallback away from the
bank. Do not enlarge the global 150 m maximum. The smaller touch radius changes only for
automatic Shore/Narrow water candidates, as explicitly proposed above; ordinary land and
Open water candidates keep their existing radius. If no eligible travel line is within
the applicable radius, retain the raw point and show
its actual connector rather than falsely reporting an offshore snap.

**Where this meets phase 11 — open for 12f, not decided here.** Phase 11 offers interior
entries and exits on every segment of an eligible edge whose nearest point lies within
d + 250 m of an off-network endpoint, d being that endpoint's distance to the nearest
eligible network point in the current mode. New water lines (contours, centre lines,
Landing water spurs) add segments, so that candidate set grows with them; moving the
bank-following line 15 m out also changes d itself for a tap near the bank. The 17.1 m
minimum water reach above decides when a tap *snaps*; phase 11's rule decides which segments
a tap that does not snap may *enter*. How the two compose — whether Landing water and bank
anchors are excluded from phase 11's candidates as they are from ordinary snapping, what d
is measured to, and what the added candidates cost against the p95 budget — is for 12f to
measure and put to review.

Mapped land/path choices and explicit launch/landing selections retain their existing
meaning. In ambiguous land/water taps, preserve a deliberately selected land feature;
for ordinary nearest-feature snapping retain the closer eligible land candidate. “Near
the shore” does not mean that an intentional road start is moved into water. Test both
sides of a narrow channel and island passages so priority cannot select a distant wrong
branch. Preserve waypoint/drag/goal/import semantics, and do not turn a raw offshore point
into a shore-following point merely because the new source exists.

Lake-owned offset, centre and spur pieces use the same lake plane as phase 9; river/sea
height rules remain. Split at ownership changes, pin those vertices and avoid duplicate
height sources at mouths. The profile, source credit, heading, phase-10 compact panel and
GPX all use the same actual lengths. New source names appear as paddled lengths, never
walking marks. A two-bank trip gains its two water spurs in both the drawn track and the
profile; no hidden cosmetic translation or double counting.

### 4.4 Gates stated as properties a reader can recognise

| Property | Measurement and stop condition |
|---|---|
| **The normal bank-following line is visibly offshore.** | Against the unsimplified source bank, decoded Shore segments have continuous minimum clearance ≥12 m and symmetric deviation ≤2.1 m from their raw offset contour. Verify geometry, then public fixture samples every 0.1 m (allow for the ≤0.05 m sampling gap when proving a bound). Report median/p95/min/max by source and exception. Screen inspection at z17/z18 also checks drawing simplification. |
| **In narrow water the line is in the middle.** | On labelled opposing-bank cross sections, including bends and islands, distance from the intended medial line ≤min(1 m, 10% of local width); retain more vertices locally if needed. No 12 m minimum here. Branch junctions/transitions are checked against the validated skeleton, not an arbitrary cross section. Report worst locations. |
| **Water lines do not cut land or dams.** | Validate every new surface-derived segment before and after encoding against real water; permit only ≤0.1 m lateral encoding excursion at bank endpoints or sub-metre narrows, with exact dry length also reported. Interior contours should require none. No decoded PADDLE segment may enter a 25 m dam disc; repair rounding at its endpoints. Existing stream lines use their own source contract. |
| **Every existing valid access and water passage survives.** | Complete anchor mapping, directed reachability and island-passage witnesses in §4.1; zero missing/unresolved items. Show a through narrow, vanished body, island-bank gap, inter-island gap, retained terminal bay, launch and carry on real data. Component counts alone do not pass. |
| **Water still wins; carrying still prefers paths according to the switch.** | Phase-10 fixed legs in both settings, mapped-land waypoint still reached; phase-7 channel both directions and falling-chain reverse prohibited. Chosen labels equal independent exhaustive labels, including new sources, partial edges and disc sampling. |
| **The answer and its figures agree.** | Drawn/exported length, profile total and paddle/foot split agree within existing rounding tolerances; source totals include spurs once. Connector grid differences are shown separately and existing sampling checks remain. Lake-only portions stay on their planes; do not require an entire river-plus-lake trip to be flat. |
| **Walking retains its rules.** | Grid, prices, source eligibility and off-network sampling unchanged; new water/launch/portage edges unreachable and unsnappable in both walking settings. Same-graph pruned/reference equality on all seeded pairs. Record noding effects; recorded fixed-input walking routes stop beyond max(2% of baseline length, 50 m). Random-pair length changes and old-way re-pricing are informational, with material increases explained. |
| **The page remains affordable to load and search.** | Compare with the frozen baseline on identical inputs: graph nodes/edges/vertices ≤1.5×; page Brotli growth ≤0.5/1.0/1.5 MB; per-setting kayak p95 ≤max(1.5× baseline, 300 ms). Record graph bytes, compressed page bytes, decode/index startup, heap counters and phone cold/warm latency. A limit failure stops before release; no pruning of legitimate passages to hide it. |

The 12 m property applies to **Shore contours**, not open crossings, stream lines, narrows,
spurs at launches/landings/mouths or deliberate raw-point connectors. Each exception is
identified by construction/source, never by noticing a failed sample afterwards. Short
centre-to-contour transitions belong to Narrow water. A source-distance gate is not a
surveyed distance from today's physical waterline or a raster-blue-pixel guarantee.

For correctness, replay phase 11's harness: the fixed seed **20260923**, 200 pairs/map, and
phase 11's off-network sample (40 / 52 / 40 starts for Abisko / MK / Norway), on both kayak
switch settings and both walking settings: **2,928 same-graph differential comparisons**
(2,400 + 528). Store
raw coordinates and re-snap on each graph; retain paired old/new snap identities separately.
Use the existing independent unpruned reference, not a second call to the production
pruning code. Compare both labels with the established tolerance
`1e-8 + 1e-12 × max(abs(label), abs(reference))`. Equal-cost alternative edge sequences
are allowed. Also run scalar connector checks and synthetic adversarial topology cases.

Time the same pairs sequentially on the same machine/browser after four warm-ups, with no
concurrent heavy work. Record median/p95/worst, route categories and length bands, not just
the three short scenes. A >2× p95 regression is an immediate investigation stop even
before the tighter release budget is evaluated. If a physical phone is unavailable,
mark its startup/latency result unmeasured and leave phone acceptance to Uwe; desktop
measurements must not be labelled phone performance.

**Four phase-9 gate mistakes to avoid.** (1) A simplification tolerance bounds lateral
deviation, not the length of a shallow inland run. (2) A geometric network gate cannot be
applied to grid-classified connectors without changing the decided sampling rule.
(3) An old way re-priced on a different graph is not necessarily an available answer;
search correctness is same-graph differential equality. (4) A bank-following trip need
not contain only Shore or retain an obsolete Shore-only distance: legitimate lake-owned
mouth crossings are Open water, and source ownership matters for its profile. Use the
new Shore + Narrow water + permitted mouth-interface reference for bank fixtures, retain
their 10% comparison band where it tests the intended journey, and separately retain
all original-tap before/after readings. Budget choices also use final graphs, not an
earlier trial's lower timings. Review must approve changed fixture roles; a failing
assertion is not fixed by silently moving its taps.

## 5. The phases

Order: **12a → 12b → 12c → 12d → 12e → 12f → 12g-Abisko → 12g-MK →
12g-Norway → 12h**. Each labelled phase is a separate bounded run/review. The plan numbered
them 11a–11h; 11 is taken by edge entries. This extends phases 10 and 11 rather than
reopening their objectives. File paths below are relative to `trails`
unless an absolute scratch path is given; proposed new files are labelled.

### Phase 12a — Freeze the baseline and make the small evidence set

*Files:* scratch `phase-12a/{baseline.json,contacts.json,fixtures.json,sensitivity.md}`;
`analysis/docs/kayak-mode-decisions.md` and this plan's approval record only.
Read `network/water.py`, source assembly, the phase-10 launch code and existing
phase-8/9/10/11 harnesses; no production algorithm change.

1. Confirm phases 10 and 11 are on main and idle. Record commit, final page/graph hashes, launch
   counts/spacing, final budgets and both-switch labels from their completed evidence.
   Reuse artifacts; do not rebuild for the sake of a baseline.
2. Select at most 12 bounded source patches, across all maps, covering broad bank, narrow
   river surface, split buffer, wholly vanished body, island-bank/inter-island gaps, bay,
   stream/launch/portage access, mouth and dam. Include adversarial synthetic fixtures.
   Take IDs and coordinates from source geometry; keep original phone fallback labelled
   reconstructed, not Uwe's recovered taps.
3. Locally compare 10/15/20 m buffer survival, contour vertices/proxy bytes, and required
   anchors under 4 GiB, one process. Cap each real patch at 50k input vertices; if a
   complete selected body does not fit, substitute a bounded halo patch and record that
   it cannot prove whole-body connectivity. Inventory the full contact evidence from
   existing phase-10 artifacts without constructing a new graph.

*Drive readings:* freeze the existing scene triples, phase-2 bay/lake/portage, Korslång,
Korslångssmedja, MK old/replacement fixtures, Abisko mouth, Kloten start/off-road start,
phone-2 legs 1→2 and 2→3, and seeded pairs. No new browser drive needed if final artifacts
contain them; missing evidence is recorded for the reviewing session.

*Review and stop:* verify §1 approval and baseline amendment, sample representativeness,
cost labels and no source/worktree writes. Stop on missing baseline artifacts, resource conflict or
evidence that the fixed preference needs changing. Do not choose a new d from fewer bytes.

**Done 2026-09-26 — the baseline is frozen, 15 m stands.** Everything below is read from
existing artifacts or measured locally on cached sources; no graph, page, tile or browser
run. Evidence, scripts, input hashes and resource figures are in scratch,
`~/mockups/kayak-mode/offset-plan/phase-12a/` (`README.md` first).

*The baseline later phases compare against:* main `6de243c`, the pages published on
2026-09-26. Their graph header and data are byte-identical to phase 10's final pages and to
the pages phase 11 timed, so phase 10's graph figures and phase 11's timings describe them.

| | Abisko | Malingsbo-Kloten | Lomsdal-Visten |
|---|---:|---:|---:|
| Graph edges / nodes / vertices | 105,923 / 49,101 / 257,555 | 294,642 / 148,291 / 980,270 | 402,240 / 190,591 / 1,301,439 |
| Page Brotli bytes (the published `.br`, quality 11) | 2,202,200 | 8,006,978 | 7,778,287 |
| Graph Brotli bytes (quality 11, phase 9's method) | 1,693,176 | 5,785,282 | 6,065,334 |
| Kayak p95 ms, Stay on paths off / on | 350.30 / 352.05 | 2,069.00 / 2,124.20 | 3,779.40 / 3,724.15 |
| Kayak p95 budget ms, off / on | 525.45 / 528.08 | 3,103.50 / 3,186.30 | 5,669.10 / 5,586.23 |
| Walking p95 ms, off / on | 418.15 / 258.60 | 1,014.35 / 802.10 | 3,845.20 / 1,684.20 |
| Launch ties at 100 m spacing | 350 | 2,220 | 1,825 |
| Graph build s (phase 10's final build) | 161.8 | 388.0 | 1,025.4 |
| Page SHA-256 (first 12) | `8ccabbd26f92` | `0472af6afd53` | `6105d31ebc1a` |

The p95s are phase 11's local-entry timings on the frozen phase-10 sample (Firefox 153,
four warm-ups); the budget is `max(1.5 × p95, 300 ms)`. The page budget adds +0.5 / +1.0 /
+1.5 MB to the Brotli bytes above, the graph budget 1.5× its counts. The differential
harness is phase 11's: all 2,928 labels (land price, secondary price, carry) are frozen in
`baseline.json` with the files they come from, as are phase 10's fixed reader legs in both
switch settings and the 48 Kloten rows. The graph Brotli size existed in no artifact and
was computed from the frozen page, not by a build.

*Contacts.* The published graph's water meets land at **350 / 2,220 / 1,825** launch ends,
**771 / 1,281 / 1,825** portage landings, **258 / 677 / 501** mapped ways at a bank,
**158 / 452 / 0** stream mouths and **0 / 555 / 0** paddle ends at a dam disc (99 of MK's
108 dams), Abisko / MK / Lomsdal-Visten, plus inferred 25 m bridges that join water to water
(**1,353 / 2,515 / 2,272**) or to land (**132 / 764 / 1,053**): those bridges are existing
connections too and 12d must map them. Portage water ends counted with repeats are
821 / 1,337 / 1,894, against phase 9's 782 / 1,286 / 1,883.

*The small evidence set.* Twelve source patches: MK's bank, bay, Korslång dam and
channel, Kloten launch at Sågviken, Holmtjärnen carry and a repaired stream join;
Abisko's Torneträsk bank and mouth, bay, a vanished river surface and an island group; and
Lomsdal-Visten's bank and carry readings. Ten sit on fixtures earlier phases read, two
come from a scan of every eligible body. Only Torneträsk is above the 50,000-vertex cap
and is read as a halo patch that cannot prove whole-body connectivity. Nine synthetic
fixtures cover a 24 m channel, a 28 m lake, 20 m island–bank and 25 m inter-island gaps, a
narrow bay, a bottle bay, a lake/river mouth, a bent inlet and a broad bank; each behaves
as the 2d rule predicts.

| At d m | 10 | 15 | 20 |
|---|---:|---:|---:|
| Least clearance of the 2 m-simplified contour, twelve patches, m | 7.271 | 12.265 | 17.474 |
| Patches whose 2 m contour deviates > 2.1 m from the raw contour | 4 | 6 | 5 |
| Patch anchors with a straight / long / dry / no spur | 436 / 62 / 167 / 0 | 373 / 36 / 203 / 53 | 349 / 33 / 178 / 105 |
| Scanned bodies vanished, Abisko / MK / Lomsdal-Visten | 1 / 1 / 0 | 8 / 3 / 0 | 10 / 4 / 0 |
| Scanned bodies split, Abisko / MK / Lomsdal-Visten | 90 / 142 / 329 | 95 / 133 / 380 | 88 / 139 / 357 |

Nothing in it argues against 15 m: every figure moves monotonically with d, and nothing
behaves differently at 15 m than the geometry predicts. Three things for the later phases:

- **12b:** plain 2 m simplification keeps the 12 m clearance but not the 2.1 m deviation
  (at most 2.731 m, on closed contour rings of 100–700 m); the plan's local refinement is
  needed, not a new gate. The raw contour sits 1.08 % inside d at a headland (14.838 m at
  15 m) from the arc chords of `quad_segs=8`.
- **12c:** every vanished body is a Swedish river surface (N50's paddle water has no river
  class). Shapely offers a Voronoi diagram of points only and the environment has no
  segment Voronoi; a densified-boundary approximation validated against the segments is
  what the plan allows without a dependency. A true segment Voronoi would need a native
  library (CGAL or Boost.Polygon bindings), whose cost 12b must report if the
  approximation fails its gate. No dependency is added here.
- **12d:** 203 of 665 patch anchors at 15 m would cross land on the straightest spur and 53
  have no contour; the re-found Kloten launch (shore node 94456) has a contained but
  33.5 m spur.

*The §4.1 premise holds in today's code.* `water.portages()` builds each connected
piece's obstacle with `shapely.build_area` from its **Shore** lines and measures a carry
as `shortest_line` between whole paddle components (Delaunay neighbours of one point per
piece, ≤ 1 km, no third water crossed, ties to walking nodes ≤ 150 m). Moving Shore
offshore would move all of that. The same holds for launches, which the plan's §4.2 does
not spell out: `launches.launches()` measures its 30 m and its 100 m spacing to and along
the **Shore** source, the 5 m-simplified bank, and checks only its wet crossing against the
unsimplified water. "Measured to the bank" is today "measured to the 5 m Shore", so 12d must
hand launches an explicit bank as well. Norway has neither streams nor dams in this source
set, as the plan says.

*Missing, recorded rather than produced:* phase 10's fixed reader legs (phase-2 legs,
Korslångssmedja, phone-2, the MK replacement fixtures, Abisko's mouth) were last read as
JSON on the phase-10 page; after phase 11 they exist only as the drive's green scene
figures, not as fresh per-leg readings. Graph build peak memory, decode/index startup and
heap figures on the baseline page, and any phone timing, are not in the artifacts. The
reviewing session decides whether 12g needs them re-read on the baseline page first.

### Phase 12b — Validated contours, with no production switch

*Files:* new `libs/src/trails/network/paddle_geometry.py`, new matching geometry tests;
small interfaces in `libs/src/trails/network/water.py` for original bodies/banks/ownership;
scratch `phase-12b/` geometry evidence. No browser change.

1. Extract physical bank and full water union separately from lake-height groups. Preserve
   pre-clip eligibility and holes. Implement raw inward buffer, post-buffer simplification,
   pinned vertices, source-water and clearance validation, including encoded round trips.
2. Return contour geometry plus bank correspondence, body/height attributes and diagnostic
   failure locations; do not yet replace production sources. Detect bay caps and artificial
   boundaries explicitly rather than publishing them as Shore.
3. Exercise the frozen patches; measure raw/simplified vertices, bytes proxy, wall time and
   peak RSS. Refine offending spans, never increase the accepted deviation to save vertices.

*Drive readings:* geometry equivalents of broad-bank and island-clearance checks; serialize
and decode coordinates in a small fixture. Full page drive remains for 12f/12g.

*Review and stop:* verify buffer-before-simplify, no mouth/map/dam artificial bank, exact
source use, 12 m clearance and 2.1 m contour deviation. Stop on invalid water or loss that
cannot be diagnosed within the frozen patches. Review any proposed new dependency here.

**Done 2026-09-26 — the contours pass both gates everywhere they were drawn; nothing uses
them yet.** `paddle_geometry.contours` in `libs/src/trails/network/paddle_geometry.py`, its
tests in `libs/tests/trails/network/test_paddle_geometry.py`, and `water.eligible_bodies`,
the bodies and height owners `_dissolved` always formed, now exposed. No graph, page, tile or
browser run and no new dependency. Evidence, scripts, input hashes and resource figures are in
scratch, `~/mockups/kayak-mode/offset-plan/phase-12b/` (`README.md` first).

*What it draws.* Each eligible body (phase 9's centimetre dissolve, 1 ha before clipping,
every island hole) is offset whole before the map cut; bodies never touch, so that is the
offset of the whole union, one body in memory at a time. The contour is cut, never redrawn,
where it is not held by a bank: at the lake/river interface (a pinned vertex; each side keeps
its owner's `lake_body`, `lake_level` and `water_class`), at a **cap**, at a dam disc
(production's analytic 25 m cut) and at the map crop. Every piece carries the bank ring and
stations it follows. Each piece is simplified at 2 m with its ends pinned, written through the
page's 1e-6° grid (`encoding.DEFAULT_COORDINATE_QUANTUM`) and read back, then gated: the exact
distance of **every decoded segment** from the unsimplified bank at least 12 m, and the decoded
piece within **2.1 m of the raw contour both ways, proved** rather than sampled (distance is
1-Lipschitz, so a gap between two samples is bounded by their mean plus half the gap; gaps the
1 m pass cannot bound are resampled at 0.05 m). A failing segment, or one that crosses another
piece where the raw contours do not meet, gets the raw vertex it dropped farthest back.

*A cap* is the stretch of contour that a closed-off bay's mouth, not a bank, holds 15 m off:
the contour within d + 0.1 m of water a d-disc cannot reach, where that water reaches at least
2d = 30 m beyond the reachable water (the plan's bay scale) or holds an access anchor. At a
bay between two vertex shoulders that is their two arcs; at a smooth or wedge-shaped mouth
it is a vertex and no cap segment exists. Indentations below that scale are smoothed over and
stay shore.

*The reference contour — an implementation choice, not Uwe's.* GEOS's buffer at **32 chords
per quarter circle**. A fillet chord spans at most 1.5 angle quanta, so every raw contour point
lies between d − 15·(1 − cos(3π/256)) = d − 0.0102 m and d from the bank; measured 0.0100 to
0.0102 m on the patches, against 0.1527 to 0.1623 m at 8 chords. It costs 2.26× the raw
vertices (305,837 against 135,551 over the patches and fixtures) and 2.0–2.5× the time to
buffer and check them; the 2 m line does not grow, since the simplifier drops the chords. The
error is harmless to both gates: clearance is measured against the bank, not the reference,
and the reference lies at most 0.0102 m nearer the bank than an exact offset, a tenth of the
0.1 m the deviation gate allows beyond the 2 m tolerance.

*12a's deviation excess was the simplifier, not the geometry.* GEOS's topology-preserving
simplifier moved closed rings by up to 2.731 m; Douglas–Peucker with pinned ends (a ring keeps
three vertices, so it cannot collapse) holds 2 m by construction, and the page's grid adds at
most 0.062 m. No piece needed a vertex back for either gate. Vertices came back only where two
separately simplified pieces crossed: **34,275 → 34,280 / 89,903 → 89,905 / 127,821 →
127,823** (Abisko / Malingsbo-Kloten / Lomsdal-Visten, whole maps); none on the patches.

*Patches* (twelve frozen, nine synthetic; tables in scratch `README.md`). All pass. Least
decoded shore clearance 12.966 m, deviation bound at most 2.1 m, largest sampled deviation
2.03 m. The 2 m line has 1,812–5,504 vertices a patch, −27 % to +6 % against 12a's
topology-preserving figures (fewer where 12a's simplifier kept rings whole); the synthetic fixtures behave as the 2d rule predicts, with caps
at the 24 m channel, both island gaps, the 150 m bay and the bent inlet, none at the bottle
bay's 26 m mouth (its closed-off water reaches under 30 m) or the lake/river mouth.

*Whole maps, geometry only* — offset contours at 15 m, no centre lines, spurs, chords or
noding; not graph or page figures:

| | Abisko | Malingsbo-Kloten | Lomsdal-Visten |
|---|---:|---:|---:|
| Bodies offset | 342 | 569 | 989 |
| Raw / 2 m vertices | 326,777 / 34,280 | 995,682 / 89,905 | 1,397,807 / 127,823 |
| 2 m proxy Brotli bytes (12a's method) | 218,427 | 584,555 | 841,135 |
| The plan's §3.1 proxy at 15 m, vertices / bytes | 31,890 / 207,161 | 84,140 / 558,320 | 119,127 / 798,479 |
| Least shore clearance / p95, m | 12.967 / 14.988 | 12.957 / 14.981 | 12.957 / 14.979 |
| Caps (reach ≥ 30 m, the rest anchored only) / cap m | 1,290 (516) / 6,612 | 2,530 (651) / 13,578 | 4,564 (1,712) / 19,548 |
| Shore m | 752,700 | 1,973,927 | 2,714,545 |
| Vanished / split bodies | 8 / 96 | 3 / 134 | 0 / 381 |
| Largest deviation sample / proved bound, m | 2.030 / 2.100 | 2.042 / 2.100 | 2.048 / 2.100 |
| Wall s / peak RSS MB (4 GiB cap) | 83 / 500 | 184 / 626 | 870 / 1,560 |

The line costs 5 % more proxy bytes than the plan's estimate (11 / 26 / 43 kB), well inside
the +0.5 / +1.0 / +1.5 MB page allowances, which cannot be judged until 12e adds the rest.
Every map fits in 4 GiB body by body; Lomsdal-Visten's sea (273,219 input vertices) takes
678 s of the 870 and needs no partition at this cap.

*What 12c must know.*

- **Vanished bodies**, all Swedish river surfaces, as 12a found: Abisko 8, at (lon, lat)
  18.187043 68.22133, 19.006917 68.197736, 18.997314 68.21874, 18.415914 68.394552,
  18.558148 68.407513, 18.661879 68.37671, 18.384298 68.408979, 18.748383 68.307251;
  Malingsbo-Kloten 3, at 15.034659 59.999573, 15.908374 59.843853, 15.097146 60.139224.
  Their records, and every other one, are in `whole-<map>.json`.
- **Closed-off water** is returned per piece with its kind (terminal, loop, passage) and
  reach. Passages and loops under 30 m are not caps but still need their centre line; caps
  with no cap segment (393 / 618 / 1,478) meet the contour at a single vertex, where a centre
  branch joins.
- **Specks**: 41 / 41 / 87 offset parts under 1 m² are left out and reported; each marks a
  place where a d-disc only just fits, a narrow that the centre line must carry.
- **Contacts**: two raw pieces less than 0.13 m apart (0.019 m at the one probed) cross once
  written on the grid, and no vertex can separate them. Reported, not refined, as water
  barely wider than 2d: Malingsbo-Kloten at 15.306432 60.131638, Lomsdal-Visten at
  12.639847 65.651648 and 12.259418 65.573545.

*What 12d and 12e must know.* Sweden's water is loaded by the map box, whole features only,
so a bank just outside the box can be the edge of a neighbouring feature that was not loaded,
and the offset carries it 15 m inside. Of the contour held by a bank outside the load window
(36 / 25 / 9 pieces), Abisko's at 18.149988 68.2772 and 19.099706 68.176394 is such an edge:
the bank there changes when the window grows by 0.02°. Before the line is built for a page,
the water must be loaded with a halo of at least d + 2.1 m around the extent. Anchors here
are all of 12a's contacts, inferred bridges included; they make 60 / 74 / 62 % of the caps.

*For review.* Whether every contact kind counts as an anchor that keeps a small bay's cap, or
only access anchors (launches, landings, mouths); whether 0.13 m, twice the grid's largest
vertex move, is the right contact distance; and the reference-contour choice above.

### Phase 12c — Centre lines and all the missing passages

*Files:* `paddle_geometry.py`, geometry/topology tests, scratch
`phase-12c/{passages,pruning,geometry-costs}`. No production default change.

1. Construct the local medial approximation, stitch across patch boundaries with overlap
   witnesses, and join to pinned contours. Keep centre geometry through a wholly vanished
   body, not just between surviving pools.
2. Mark required passages, island alternatives, bay branches and all contact terminals;
   prune only surplus branches. Classify caps as Open water and keep retained bay access.
3. Validate the middle/containment criteria, continuous joins and island witnesses on the
   frozen patches and synthetic cases. Measure every retained/pruned category, nodes,
   vertices, lengths and resource use. Demonstrate stable joins under tighter local sampling.

*Drive readings:* small graph fixtures show through travel, both island alternatives,
terminal bay access and a vanished body with no invented portage. A falling-stream/dam
fixture shows that a skeleton cannot reopen a cut.

*Review and stop:* inspect pruning witnesses, not only component totals. Stop on a missing
required branch, unstable medial construction, new dependency burden or memory excess.
If algorithmic work is incomplete, split this phase before beginning access integration.

### Phase 12d — Attach the last metres and preserve the barriers

*Files:* `libs/src/trails/network/water.py`, `paddle_geometry.py`, the phase-10 launch module
`libs/src/trails/network/launches.py` (read in 12a), `libs/tests/trails/network/test_water.py`, geometry tests;
source assembly in `sweden.py` / `norway.py` only where an explicit bank input is needed.

1. Make land access use original bank/body geometry. Keep phase-1b portage eligibility,
   original walking contacts, phase-10 launches and obstacle water. Map every old contact
   identity to a retained anchor and add contained Landing water spurs.
2. Join class-2 mouths to their own surface/centre network and preserve phase-7 chain
   decisions across splitting. Keep lake-owned interfaces once and at the lake plane.
3. Cut all generated geometry at analytic dam discs, retain disc-side land access and
   validate encoded endpoints. Test ordinary launch and dam-side exceptions separately.

*Drive readings:* synthetic launch 25 m from bank plus 15 m water, two-ended carry with
water spurs, an inlet needing a bent spur, directed mouth and two-way level channel,
lake-owned shared mouth and blocked dam. Confirm zero extra land price from the water spurs.

*Review and stop:* all patch contacts mapped, exact land-side distance/price preservation,
no whole-offset-distance launch eligibility, no new PORTAGE across a narrow. Stop on
unresolved anchors or inability to retain phase-7 decisions. Do not replace real missing
joins with globally nearest straight lines.

### Phase 12e — Integrate sources, chords and encoded roles

*Files:* `water.py`, `routing/sources.py` only if attributes require it,
`visualization/encoding.py`, `js/routing_graph.js`, their tests;
`analysis/scripts/route_graph.py` / `lomsdal_visten.py` report regions as needed.

1. Assemble Shore, Narrow water, Landing water, Open water and Streams with factors and
   lake ownership. Add compact source roles for snapping; keep full bank/medial provenance
   in build evidence rather than the page payload.
2. Build sparse contained open chords with explicit interface retention; node joins using
   shared coordinates. Validate again after noding/encoding and report costs by source,
   including partial segments, duplicate removal and collapsed coordinates.
3. Preserve explicit original bank/body inputs for portages/launches. Test the combined
   source and encoder contract on small networks. Wire the completed generator only once
   12b–d pass; no incomplete graph is released.

*Drive readings:* decode a fixture containing every new role, a mouth and a dam; route and
credit each source, including partial-edge endpoints. Walking excludes all new water sources.

*Review and stop:* inspect noding direction, role encoding, source totals and candidate
growth. Stop on quadratic chord generation, duplicate mouths, or validation lost during
encoding. Whole-map capacity is still unmeasured; proxy bytes do not pass release budgets.

### Phase 12f — The tap, the line and the figures

*Files:* `libs/src/trails/visualization/js/plan_mode.js` snapping/pricing/tally regions,
`profile_panel.js` only if new source presentation requires it, `maps.py` settings/text
regions, `libs/tests/trails/visualization/test_kayak_routing.py`,
`analysis/scripts/drive_map.py` new reusable readings. Retain phase 10's panel and switch.

1. Implement the water-snap roles, including shared anchor nodes, partial edges, the
   minimum water-candidate reach, ordinary near-bank taps, ambiguous land candidates and
   explicit selections. Settle with review how they compose with phase 11's d + 250 m
   interior entries (§4.3, the open point there) before building on either reading.
2. Verify the existing lexicographic router prices the new sources correctly and that
   lower bounds remain admissible. Extend the independent reference/tests for the roles;
   do not copy pruning into the reference.
3. Verify source credit, lake profiles, public totals and export include spurs once. Add
   permanent property readings from §4.4, with restoration of mode, Stay on paths, plan,
   goal and view in `finally`, and fixed raw taps independent of scene replacement.

*Drive readings:* normal near-bank tap offshore, narrow tap central, land/path start
retained, explicit launch and offshore point, wrong-island candidate, high-zoom bank tap
with a touch radius below 15 m, upstream partial stream edge, profile/panel/GPX split, walking exclusions. Use
small synthetic browser fixtures first; real production drives follow per map.

*Review and stop:* stop on bank-spur snapping, raw-point movement outside the existing
rules, changed phase-10 pricing/grid sampling or a differential mismatch. Verify full
suite isolation; a reading that only passes under `--only` is not ready.

### Phase 12g — One final map per run: Abisko, then MK, then Norway

*Three separate runs.* *Files:* generated graph/page outputs in the authorised future
worktree/output locations; scratch `phase-12g-<park>/`; that map's new drive fixtures and
reviewed figures in `drive_map.py`; evidence and built notes in the two kayak records.
Do not edit shared geometry during a measurement without invalidating affected earlier
results and scheduling the necessary recheck.

1. After resource approval, build that map's final graph and page sequentially from cached
   inputs under the approved full-build cap. Capture full contact mapping, component and
   island witnesses, geometrical gates and source/node/edge/vertex counts. Full audit is
   per body/partition with bounded memory; no all-map dense reachability matrix.
2. Replay that map's part of phase 11's harness in all four settings against the reference
   (200 seeded pairs plus its off-network sample: 960 / 1,008 / 960 comparisons for
   Abisko / MK / Norway), then controlled timings. Report changed routes, paddle/carry totals,
   snap movements, largest increases and all budgets against the frozen baseline. Record walking noding effects and retain
   existing grid hashes and dry figures where their inputs remain identical.
3. Drive fixed historical taps and new property fixtures; inspect the actual drawn line
   at z17/z18, including source/drawing simplification. A near-bank figure must exercise
   the offset, and a routed carry must include network paddle on both sides. Keep old
   fixtures in the comparison when a new fixture is approved for a new assertion.

*Drive readings:* all scene triples and phase-10 checks in both kayak switch settings;
phase-2 sweep legs and Kloten/phone-2/Korslång/MK repaired mouths on MK; fixed Abisko mouth
and its lake plane; Norwegian islands/fjord and existing sea-height rules. All maps show
at least a narrow, bay, island and landing when the source contains that case; distinguish
an unavailable real case from a synthetic pass. Preserve the original screenshot fallback
and all original scene taps in reports.

*Review and stop:* review counts and complete failure lists before figures are updated.
Stop on any §4.4 failure; measure all independent cheap diagnostics needed to explain it,
but do not proceed to the next heavy build while it remains unresolved. Run selected
new/existing kayak checks twice green on the final page and full walking readings. Store
hashes tying drives and differentials to the precise final payload.

### Phase 12h — Review the three maps as one feature

*Reviewing session.* *Files:* final approval/build notes in
`analysis/docs/kayak-mode-phases.md` and `kayak-mode-decisions.md`; measured source wording
and figure notes already validated in 12g. No new algorithm or automatic deployment.

1. Check each final artifact has all topology/clearance gates, the full per-map differential
   harness and both-setting timings; verify records use the frozen 12a baseline and
   final candidate hashes. Explain every accepted moved figure in terms of the new line.
2. Run **`command make drive-all` once** over the final pages after the twice-green
   selected drives, then `command make hooks-run` with networking as the established
   workflow requires. Record any pre-existing issue separately; do not call a partial
   `--only` result the full suite. Recheck affected pages if a shared fix is necessary.
3. Read the line and cold/warm interaction on Uwe's phone, with exact taps and settings
   retained. Show narrow/island/bay/launch examples and the carry/paddle split. Record
   actual phone results or leave that acceptance explicitly pending.

*Stop:* missing connection, unapproved budget excess, incorrect labels or unresolved
phone acceptance prevents release. Review produces the concrete approved change and its
record under the normal worktree rules. Commit, push and publication follow the user's
existing explicit authorisation for that future execution; this planning request grants
none of them.

## 6. Outside this step

No new water source, finer shared grid, exact-width walking price, wind/fetch/exposure
model, crossing-length cap, class-1 streams, Norwegian stream classification, named canoe
routes or atlas work. The 15 m line expresses Uwe's geometry preference using the available
water data. The historical k = 1.5 remains a detour price, not a literal “bay deeper than
its mouth is wide” formula. These separate policies must not be changed to make an offset
fixture or payload target pass.

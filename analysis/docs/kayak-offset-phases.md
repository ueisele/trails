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

**Done 2026-09-27 — the middle runs wherever the offset cannot, on the patches and all three
maps, and every gate holds; nothing uses it yet.** `paddle_geometry.contours` now also returns
the centre network: `centre` (pieces, all Narrow water, each with why it is kept), `nodes`
(joins, junctions, ends, anchor nodes), `pruned` and `anchors`. Its tests are in
`test_paddle_geometry.py`. No module outside those two files imports `paddle_geometry`, so
production output cannot change; no graph, page, tile or browser run, no new dependency.
Evidence, scripts, input hashes and resource figures are in scratch,
`~/mockups/kayak-mode/offset-plan/phase-12c/` (`README.md` first).

*What it draws.* The middle is the medial axis of each body's water where its radius is under
d, built near closed-off water, near places where the contour's nearest bank jumps across at
least 20 m of bank or between two rings, near access anchors, and through vanished bodies
whole. It meets the contour exactly where its radius reaches d; that point is inserted into
the raw contour and pinned, so both lines share the vertex once written. Kept, per the brief:
every path between joins and every loop (passage, loop), the longest way of a vanished body,
a branch whose longest way from where it hangs is at least 30 m and the branches off it judged
the same way (bay), and the way to every anchor's branch (anchor). Everything else is pruned
and listed. Closed-off water the kept network runs into, or whose anchor's branch is kept, is
kept closed-off water; its cap pieces are **Open water where the nearest bank point jumps
inside the cap from one shoulder to another**, and Shore where one shoulder holds the whole
cap (the arc round an island's corner beside a straight bank).

*Construction — implementation choices, not Uwe's.* The Voronoi diagram of the bank sampled at
most every metre, symmetrically about each vertex, built from GEOS's Delaunay triangles in 1 km
tiles; ribs between neighbouring samples dropped; each edge clipped at the **exact** radius d
(the samples' overstatement is measured at the edge's ends and interpolated); every kept edge
checked for an empty circle (GEOS triangulates exactly collinear samples into flat triangles
whose 2.8·10¹⁰ m circles pass for empty, and the bisector of two samples nine apart then crossed
an Abisko river); local halving of the step round any kept node off the middle (up to 7 times)
and round edges cut at the water's edge, a pinch finer than a step (up to 3 times); corner
branches run on into their convex corner (the sampled branch stops 0.7 of a step short); joins
more than 0.1 m and up to 2 m off the contour reach it by a straight transition; ends farther
off are no joins and are tied through the speck of offset beside them or across to the other
piece of the middle within 2 m; an anchor keeps the branch its bank faces (the edges its three
nearest bank samples generate) unless a kept line's disc already reaches it within 1 m.
Simplification is Douglas–Peucker where each raw vertex moves by what the middle gate leaves
it, less the page grid's move; the written line is proved against the gate as in 12b.

*Whole maps, geometry only* — the 15 m contour and the centre network, no spurs, chords or
noding; not graph or page figures:

| | Abisko | Malingsbo-Kloten | Lomsdal-Visten |
|---|---:|---:|---:|
| Contour 2 m vertices (12b's) | 38,427 (34,280) | 96,717 (89,905) | 141,544 (127,823) |
| Centre vertices: raw / plain 2 m / delivered | 439,415 / 15,261 / 25,259 | 503,385 / 22,695 / 39,347 | 432,607 / 25,538 / 50,111 |
| Centre km (of it transitions outside closed-off water) | 239.8 (41.5) | 292.9 (68.7) | 290.7 (125.0) |
| Kept km: passage / loop / vanished / bay / anchor | 152.8 / 12.4 / 11.7 / 51.9 / 11.2 | 165.6 / 5.5 / 6.3 / 89.3 / 26.2 | 97.5 / 0.4 / 0 / 153.4 / 39.4 |
| Joins / junctions | 2,944 / 562 | 5,009 / 448 | 12,132 / 493 |
| Pruned: bay branches / side branches (km of longest ways) | 10,540 (173.9) / 11,925 (107.7) | 30,396 (506.8) / 19,854 (168.0) | 64,914 (1,081.8) / 30,654 (260.0) |
| Kept closed-off water (12b's caps) | 1,783 (1,290) | 3,396 (2,530) | 8,089 (4,564) |
| Cap pieces Open water / Shore; Open water km | 960 / 1,311; 6.94 | 1,927 / 2,037; 14.58 | 3,266 / 3,813; 24.35 |
| Anchors in closed-off water / kept | 2,788 / 2,787 | 5,816 / 5,816 | 4,280 / 4,280 |
| Proxy Brotli B (12a's method): contour + centre | 232,000 + 150,887 = 379,640 | 608,774 + 234,872 = 838,099 | 889,016 + 307,177 = 1,182,479 |
| Wall s (of it centre) / peak RSS MB, 4 GiB cap | 326 (185) / 699 | 401 (157) / 588 | 4,292 (2,971) / 1,864 |

The pruned branches are almost all corner branches under 30 m; the largest pruned are 29.96,
29.99 and 30.00 m (Abisko 18.964875 68.279803, Malingsbo-Kloten 15.075951 60.057385,
Lomsdal-Visten 12.932278 65.670543, longest way just short of 30 m to rounding). Kept closed-off
water grows over 12b's caps by the passages and loops under 30 m of reach, which 12b smoothed
over, and by bays whose branch reaches 30 m from its join though their water reaches less.
The contour gains 4,147 / 6,812 / 13,721 vertices over 12b's, from the pinned joins and the
cuts at the new caps.

*Against the §1.7 budgets, geometry only.* Page: contour plus centre proxy less the 5 m bank
proxy the plan measured (190,252 / 418,282 B) is +189,388 / +419,817 B for Abisko /
Malingsbo-Kloten, of +0.5 / +1.0 MB; Lomsdal-Visten's has no measured bank proxy, and all of its
1,182,479 B is under +1.5 MB. Vertices: contour plus centre less the 5 m bank's 28,604 / 62,387
is +35,082 / +73,677 against +128,778 / +490,135 allowed; Lomsdal-Visten's 191,655 whole
against +650,720. Spurs, chords and noding come on top in 12d and 12e.

*The gates.* Middle: every kept raw vertex within min(1 m, 10 % of width) of the true middle,
measured against the exact bank segments on both sides (worst raw 0.25 / 0.25 / 0.36 m, largest
share of width 0.0976 / 0.0946 / 0.0971 held). Where the gate leaves less than 1.5 grid moves,
about 1.2 m of water and less (1,995 / 2,994 / 5,974 vertices), it is held before encoding and
the grid adds at most 0.058 / 0.064 / 0.060 m. Labelled cross sections (straight, bend,
island), where the banks are opposing, measured from the written line along the gradient of
the two banks' distances: 5,504 of 5,504 within the gate on the patches and fixtures (worst
0.91 m at 20.5 m of water), 3,089 of 3,089 and 3,108 of 3,108 on the whole of Abisko and
Malingsbo-Kloten. Lomsdal-Visten's whole map was measured by a chord's midpoint, which is off
the true middle wherever the banks are not in line: 3 of 3,224 failed, where the banks were
144–169 degrees apart by their widths and errors, and all 95 sections round those three places
pass on 300 m halo patches the final way. Containment: no dry length before encoding; after
it 25.89 / 46.13 / 82.70 m dry in all, never more than 0.061 m out, all at bank ends or
grid-narrow water, as the plan allows. No segment enters a dam disc (least 25.0001 m). Stability: at half the step every patch has the
same number of joins and of junctions, each matched both ways within 0.145 m against
min(1 m, 10 % of width). Tiles: of
4,618 / 8,579 / 12,739 edges computed on both sides of a border, 1 / 6 / 8 differ, by at most
0.5 / 16.8 / 2.7 mm at a clip point, and 2 in Lomsdal-Visten have no counterpart.

*The witnesses*, on real data, with crop and dam cuts counted apart. Through travel: every
passage and every loop beside an island joins all the contour parts it lies between through
its own middle (671 / 765 / 1,269 witnessed; one Lomsdal-Visten loop at 12.449706 65.857187
leaves the map 40 m away and was not seen as cut by the whole-map run). Islands: every island
lies alone in a face of the network (662 / 1,201 / 1,755; the rest cut by the map). Bays:
every kept bay reaches a join (1,055 / 2,453 / 4,889). Vanished bodies: all 8 in Abisko and
2 of 3 in Malingsbo-Kloten are one piece of centre line end to end; the third is cut by its
dam. Synthetic graph fixtures in the tests show a through narrow, both ways round an island,
a 30.32 m bay kept against a 19.80 m one pruned, a 6 m bay kept for its anchor, a vanished
body crossed, a dam that the middle does not reopen, a gap 5 cm under 2d kept, a river joined
through a 6 cm pinch, and identical lines at half the step and in 60 m tiles.

*12b's three grid contacts.* At both in Lomsdal-Visten the water is within 0.03 m of 2d wide
(the reported points lie 15.013 and 14.968 m from the bank) and the middle now runs through
(0.05 and 0.14 m away); the nearest contour pieces there now meet (0.0 m apart) and the first
two no longer cross once written, but a centre-to-contour contact is reported at each. Malingsbo-
Kloten's at 15.306432 60.131638 remains: no middle is built there (the nearest is 100 m away),
and two raw contour pieces 0.093 m apart still cross once written; 12e must node it.

*What 12d must know.* The `anchors` frame maps each access anchor in closed-off water (12b's
set) to the node of the branch it keeps; one Abisko anchor faces no branch. Every join is a
pinned vertex of both lines; the 0.1–2 m transitions are Narrow water. `contact` lists the
places where a centre piece and another line pass within 0.13 m and cross once written
(56 / 40 / 90); no vertex undoes that, so 12e must node them.

*The cost 12g inherits.* Lomsdal-Visten's sea, one body of 273,219 input vertices, took 3,903 s
of the map's 4,292, its middle 2,814 s over three local halving rounds; that alone is beyond
twice the map's whole baseline graph build (1,025 s), the plan's threshold for investigating.
Each halving round rebuilds the whole body's graph and pruning, and pieces are validated one by
one; on a profiled patch (Malingsbo-Kloten's stream join, 15.3 s) the middle took 5.2 s, the
centre pieces 5.6 s (3.1 s of it validation) and the contour's validation 2.5 s. The sea was
not profiled. Before 12g's full build the middle needs partitioning by body region or an
incremental halving round.

*For review.* The cap rule (kept closed-off water, Open water only where the nearest bank
jumps between shoulders) and its growth over 12b's caps; the 2 m transition and tie reach; the
1 m anchor disc; holding the middle gate before encoding where the grid leaves it no room; and
the 20 m jump separation that decides where the construction looks at all.

**Done 2026-09-27 — 12c-2: the same geometry in 147 / 252 / 846 s instead of 326 / 401 / 4,292;
under the 1.0× limit, short of the 0.5× target.** `paddle_geometry.py` and its tests only. Every
frame `contours` returns is 12c's record for record (geometry as WKB, arrays as bytes) on all
three whole maps, and on the twelve frozen patches and nine fixtures at the 1 m and the 0.5 m
step, with one addition: a new report, `seam`, two rows in Lomsdal-Visten (below). No graph,
page, tile or browser run, no new dependency, one process. Evidence, scripts and profiles are in
scratch, `~/mockups/kayak-mode/offset-plan/phase-12c/speed/` (`README.md` first).

| Offset geometry, whole map, s | Abisko | Malingsbo-Kloten | Lomsdal-Visten |
|---|---:|---:|---:|
| Before, 12c's run (of it the middle) | 326 (185) | 401 (157) | 4,292 (2,971) |
| After (of it the middle) | 147 (75) | 252 (109) | 846 (375) |
| Against the baseline graph build (161.8 / 388.0 / 1,025.4 s) | 0.91× | 0.65× | 0.83× |
| Target 0.5× / limit 1.0× | 81 / 162 | 194 / 388 | 513 / 1,025 |
| Largest body before → after | 191 → 59 | 70 → 25 | 3,903 → 572 (the sea) |
| Peak RSS MB, 12c's code → after, same script | 644 → 695 | 511 → 563 | 1,793 → 2,143 |

The brief's table added 12b's contour-only runs to 12c's, which already contain the contour;
12c's run alone is the before figure. "The middle" is the construction up to the kept network,
the rest the contour, the cuts, simplification and both gates.

*Where the time went*, 12c's code under cProfile (349 / 436 / 4,506 s), and what changed —
implementation choices, none of them Uwe's:

| cProfile s, before → after | Abisko | Malingsbo-Kloten | Lomsdal-Visten |
|---|---:|---:|---:|
| Corner branches' `covers` test | 77 → 4 | 33 → 5 | 1,862 → 33 |
| Closed-off water's edge index, per ring (`_cut`) | 42 → 2 | 57 → 4 | 901 → 8 |
| Tiles: samples, Delaunay, Voronoi, clip | 29 → 30 | 49 → 51 | 640 → 154 |
| Contour gates (`_validated`) / centre pieces | 34 → 23 / 60 → 42 | 86 → 52 / 79 → 70 | 131 → 77 / 114 → 97 |
| Height owner lookups | 25 → 3 | 52 → 5 | 103 → 8 |
| Closed-off water, opening (`_residue`) | 12 → 13 | 22 → 23 | 190 → 185 |

- GEOS answers `covers` for a line that touches a polygon's outline by relating the whole
  polygon (2.6 ms a line against a 200,000-vertex ring, 2 µs inside it), and every corner branch
  ends on the bank. Such questions — corner branches, pinch ties, the dry test, the anchors'
  distance to the opened water, the loop/terminal test on a large opened part — now read the
  body's water cut into 1 km cells with a 100 m margin, which holds the body's outline near the
  line vertex for vertex and in its own ring direction. The cut at the water's edge stays on the
  whole water: in a cell it moved one pruned sea branch's end by 0.9 nm.
- The closed-off water's edge index is built once per body; owner polygons and large seeds are
  prepared; deviation bounds use GEOS's point-to-segment formula in numpy over the segments whose
  envelopes can hold the nearest, bit for bit the tree's figure (a test in the suite).
- A window growth kept recomputing every tile — six growths over the sea's four halving rounds,
  8,289 tile computations. A growth now keeps the tiles no added seed comes near, which would come
  out the same, and the cache holds exactly that pass's tiles as clearing did: 1,308 for the sea,
  3,905 instead of 10,886 for the map. The seeds' layout is kept between rounds. Crossings and contacts take one pass; the overlap witness runs
  in arrays. The caches are bounded (one layout, 64 cells): with more, the sea reached 4,018 MB
  of the 4,096 MB address-space cap.
- No gate or witness moved out of the build.

*What remains.* The sea is 572 s of Lomsdal-Visten's 846. The map's offset and opening at 32
chords, and the union and difference that give the closed-off water, take about 270 s under
cProfile, nearly all of it the sea's; they are 12b's construction and cannot shrink without
changing it. Beyond that the time is spread: tiles, pruning, and both gates (a third of Abisko's
and Malingsbo-Kloten's time, a sixth of Lomsdal-Visten's). Reaching 0.5× would take a cheaper gate
(proving the deviation bound from Douglas–Peucker and the grid's move instead of sampling it,
which would move the per-segment figures out of the build) or a cheaper offset; both change
what the build reports, and are for review.

*12c's open items.* Lomsdal-Visten's whole-map cross sections measured along the gradient:
3,258 of 3,258 within the gate, worst 0.931 m in 14.78 m of water at 13.555126 65.485547.
Whole-map witnesses with the crop sought along the branch: every through, bay and island witness
holds or is cut by the crop or a dam; the Lomsdal-Visten loop at 12.449706 65.857187 is now
counted as cut (through 1,269 of 2,128, 859 cut). The two overlap edges without a counterpart lie
in the sea 8,967 m outside the map: a straight bank sampled every metre faces a ring's corner
there, close to cocircular, and the two tiles triangulate the same samples differently (GEOS's
Delaunay then depends on the rest of each tile's samples). **A seam can lose a connection in
principle** — two tiles' edges can end at different nodes on a border — though none did: those two
edges are outside the map and every witness holds. The build now reports each such place beside a
kept line as `seam` with its location; a clip computed a millimetre apart at radius d or the bank
parts nothing and is not reported. That is those two rows and nothing else on the three maps.

*For review.* Whether `seam` should stop a build or only report, and whether a seam should be
repaired (joining the two ends, or triangulating a border once for both tiles), which would change
the network; and whether to accept 0.91× for Abisko or move the gates' figures out of the build.

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

**Done 2026-09-27 — 12d-1: carries and launches read the bank explicitly; every one of them
is main's, byte for byte.** `water.py`, `launches.py`, the two loaders and `test_water.py`. No
graph, page, tile or browser run, no new dependency. Evidence, scripts and logs are in scratch,
`~/mockups/kayak-mode/offset-plan/phase-12d/` (`README.md` first).

*What changed.* `water.paddle` is what `water.sources` was and also returns a `Bank`: the Shore,
Open water and Streams frames it has just drawn — the same objects, not copies — which is the
dissolved, 5 m-simplified, dam-cut bank and the lines that close each water piece. `sources`
still returns the paddled sources alone. `water.portages(bank, walking)` and
`launches.launches(bank, walking, access)` read only that bank; the loaders put it into `Access`,
and `water.build` hands `access.bank` to both and refuses paddled water without one. So when 12e
moves the paddled Shore offshore, land access keeps measuring to the bank it measures to today:
phase 1b's components, Delaunay neighbours, 1 km carries, third-water exclusion and 150 m ties,
phase 10's 30 m reach and 100 m spacing. Nothing in it is measured against the unsimplified bank.

*The proof* (`identity.py`): main `bc9e22e`'s two functions against this code on the inputs phase
10's final builds handed them (`phase10/final/<map>/launch-inputs.pkl`), compared as exact WKB in
order, with the launches' origin, bank and station:

| | Abisko | Malingsbo-Kloten | Lomsdal-Visten |
|---|---:|---:|---:|
| Portage chords / km | 437 / 207.115 | 699 / 340.986 | 1,010 / 481.243 |
| Walking ties / km | 81 / 6.616 | 701 / 47.656 | 285 / 20.203 |
| Launches / m (= their path-priced metres) | 350 / 4,915.738 | 2,220 / 30,915.681 | 1,825 / 23,232.458 |
| Identical to main; launches identical to phase 10's built catalogue | yes; yes | yes; yes | yes; yes |
| Wall s / peak RSS MB, both codes, 4 GiB cap | 34 / 350 | 82 / 535 | 108 / 723 |

On each of 12a's twelve frozen patches the whole chain was run from the surfaces as well — main's
`water.sources` against `water.paddle` on the patch's water, streams and dams: every source
identical, the bank's frames the sources' own, and portages, ties and launches identical. The
launch counts are the frozen baseline's 350 / 2,220 / 1,825.

**Stopped 2026-09-27 — 12d-2: every contact reaches the line, and phase 7's directions do not
survive the new splitting.** `paddle_geometry.landings` and its tests; one guard in 12c's
`_layout` (a round lake with no closed-off water gave the middle nothing to look for and raised).
Nothing is wired: no graph, page, tile or browser run, no new dependency. Evidence, scripts and
frames are in scratch, `~/mockups/kayak-mode/offset-plan/phase-12d/` (`README.md` first).

*What it draws.* For each contact of 12a's inventory, on its body's contour and centre lines: a
**Landing water** spur from the retained point, straight to the nearest line point where that lies
in the body's own water clear of every dam disc, else bent round the bank's corners (a visibility
search in growing windows); to 12c's node where 12c mapped the anchor, unless the node lies inside
or beyond a dam disc (237 in Malingsbo-Kloten, all reported). A contact on a stream alone stays on
its stream; a way over the water that crosses the new lines is noded where it crosses; a pure mouth
contact is its stream's mouth. For each class-2 stream: where it actually meets its body's water,
and where it ends inside it, a join to the line, unless the stream itself runs on through the water
to the line within 2d. For each body with lake and other water: every exact lake-owned interface
once, with the points where contour and centre pieces end on it (for 12e to node) and an Open water
link into a side no piece meets. Every line is checked before and after the page's grid.

| Whole map, geometry only | Abisko | Malingsbo-Kloten | Lomsdal-Visten |
|---|---:|---:|---:|
| Contacts / unresolved | 5,748 / 0 | 14,343 / 0 | 10,729 / 0 |
| Landing water spurs / km; median / p95 / max m | 3,578 / 25.347; 6.5 / 15.6 / 38.8 | 8,768 / 72.742; 8.4 / 16.4 / 42.1 | 8,894 / 75.942; 9.9 / 16.3 / 23.1 |
| of them bent (all lines) | 19 | 456 | 211 |
| Open water from contacts beyond the line / max m | 14 / 7.3 | 44 / 16.4 | 44 / 1,581.5 |
| Launch spurs / km; max m | 350 / 3.292; 19.4 | 2,220 / 19.852; 19.7 | 1,824 / 16.680; 19.7 |
| Carry spurs / km; max m | 722 / 3.510; 38.8 | 1,232 / 7.493; 42.1 | 1,825 / 7.329; 19.6 |
| Mapped ways at a bank / max m | 258 / 18.3 | 677 / 21.7 | 501 / 22.8 |
| Stream mouths and ends: joined / the stream's own crossing | 139 / 389 | 213 / 607 | – |
| Dam-side contacts / spur max m | – | 555 / 24.4 | – |
| Bridges to water / to land / at the crop | 2,519 / 132 / 122 | 4,644 / 759 / 146 | 4,329 / 1,051 / 189 |
| Interfaces / met on both sides / links | 120 / 120 / 0 | 137 / 136 / 2 (9.4, 11.7 m) | 0 |
| Least written dam clearance m; lines inside a disc | – | 25.0002; 0 | – |
| Dry beyond the bank step, total m (farthest off the water): before / after the grid | 0 / 0.32 (0.07) | 2.70 (0.07) / 8.42 (0.09) | 5.89 (0.07) / 18.50 (0.08) |
| Landings s (× baseline build) / cumulative with 12c-2's geometry | 8.9 (0.055×) / 0.989× | 22.8 (0.059×) / 0.692× | 23.7 (0.023×) / 0.815× |
| Peak RSS MB, 4 GiB cap | 733 | 830 | 2,236 |

Contacts count nodes of the frozen graph, a node once however many roles it has; per role and the
longest examples with coordinates are in `whole-<map>.json`. The longest Landing water spurs are
carries landing on slivers of water at the map's crop (Abisko 18.665796 68.139676, 38.8 m;
Malingsbo-Kloten 14.967 60.05324, 42.1 m, bent). The three repaired Malingsbo-Kloten stream joins of
phase 9 are stream ends inside the water, joined by 0.06, 0.26 / 0.12 and 7.07 / 7.02 m. On the
twelve patches every contact resolves too (`report.md`).

*Prices.* The land part of every launch and carry is 12d-1's, byte for byte; the water spurs are
separate PADDLE lines at factor 1 and add nothing to a land price. A launch keeps phase 10's ≤ 30 m
to the bank: the synthetic road end 25 m from the bank still launches, and its spur is 15 m more
water. A two-ended carry keeps its chord and gains a spur at each end.

*Implementation choices, not Uwe's — for review:*
- **The bank step.** A retained anchor lies on phase 9's 5 m bank, up to 5.1 m off the water: a spur
  may run over that land from its anchor to the water, no longer than the anchor's own distance plus
  0.5 m; where a dam's disc covers the nearest water, it may go round the disc (up to 10.2 m, never
  more than 5.1 m off the water; largest 5.61 m long, 4.91 m off). 1,352 / 3,765 / 4,091 spurs start
  on land. Beyond that step a spur may stray only by the page's 0.1 m.
- **Open water beyond the line.** A contact more than 17.1 m (d + 2.1) inside the water — an old
  open-water chord's end at a dam, a bridge to a path on land the water does not cut out — is joined
  by Open water at 1.5, not Landing water: it is not the last metres from a bank. Seven such links in
  Lomsdal-Visten run 67–1,582 m straight across open water (bridges to paths on skerries, e.g.
  12.096367 65.632495), contained, priced as today's chords.
- **Not joined.** Bridges joining a line the map's crop cut to its neighbour (109 / 114 / 176, as
  phase 9 kept crop ends out of the landing audit); water with no line inside the map, on the crop
  (a carry in Malingsbo-Kloten, a launch in Lomsdal-Visten); 433 Lomsdal-Visten points where a
  ferry crossed an old chord far out in open water (a way over the water, which 12e's chords will
  cross).
- Dam anchors are stepped straight out of their disc before routing; the bent search avoids each disc
  drawn a grid move wider; a written vertex the grid still puts inside is moved out by 12c's rule
  (278 in Malingsbo-Kloten, at most 0.125 m, all on page-rounded inventory points).

*The stop: phase 7 across the new splitting.* Phase 7's gate sums each stream edge's quarter-median
fall, so it reads how a chain is cut, and every line that crosses or joins a stream cuts it anew.
Read off the frozen heights (`phase7.py`, which first reproduces every chain's `one_way` in the
graph, 311 / 311 and 345 / 345): with the old nodes that survive, 12b–12d's crossings and 12d's
joins, **28 Malingsbo-Kloten chains (10.41 km) change direction** — 18 one way → open, 10 open → one
way, falls moving by up to 3.16 m on streams through river surfaces — and none in Abisko. 12d's own
spurs and joins alone, on today's splits, flip one (`streams-536083-6655768-253`, 0.3224 m against
0.3000 m). Deciding on each stream's own nodes flips 44, on the whole chain 43. 12e's chords are not
in the figure and will cut more. **What keeps every decision:** decide on today's splitting, which the
explicit bank now reproduces — node the streams against `Bank`'s lines for the gate alone and carry
each chain's decision to the new edges. That is a change to how the build decides direction, for
Uwe or review to choose before 12e; no rule is changed here.

*What 12e must know.* Insert each spur's end, each interface's meeting points and each mouth join's
point into the line it lands on (shared coordinates). The anchors here are the published graph's
nodes; the build must make them itself — launch and carry ends from the bank, ways noded against the
bank, stream mouths, dam-side ends — and **bridges are inferred by the graph build from loose ends**:
a loose end that bridged to the old bank must reach its spur's anchor, not whatever lies nearest.
The land side of a dam anchor must be written by the same out-of-the-disc rule as its spur. 12c maps
anchors to nodes without the dams; 237 of Malingsbo-Kloten's lie inside or beyond a disc.

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

*Uwe said "Ja" to 12e on 2026-09-27.* **Review's decisions, taken before the phase (not Uwe's):**

1. Stream directions keep phase 7's decisions exactly: decided on today's cuts, as main nodes the
   streams against `Bank`'s lines, and carried by chain onto the new, finer edges; proved on every chain.
2. The build keeps its behaviour behind one setting, default off, until 12g: off, graph and page are
   main's byte for byte; on, the offset network replaces the bank-following one.
3. The open-water chords follow today's rule on the new lines: Delaunay edges the region the new
   travel lines enclose covers, less their own segments, lake-owned seams once; no new crossing
   policy, nothing quadratic; a case the rule does not carry is a stop.
4. The water feeding `contours()` is loaded at least 17.1 m beyond the map box; `Bank`, and so every
   carry and launch, stays as today.

**Stopped 2026-09-27 — 12e: the line off the bank is wired in behind `paddle_offset`, off by
default, and the switch-off graph is main's byte for byte; Abisko's switch-on build takes 414.2 s,
2.56× the baseline, over the 2× line.** Everything else the phase asks is built and holds on
Abisko. Evidence, scripts and logs are in scratch, `~/mockups/kayak-mode/offset-plan/phase-12e/`
(`README.md` first). No page, tile or browser run, no push, no new dependency.

*What changed.* `routing/sources.py`: a source's `role` (`travel`, `landing`, `open`, `stream`) and
`settled` flag. `routing/graph.py`: a settled line's ends are never loose, no bridge lands on it, and
each end joins the line it lies on within the node tolerance, as launch ends do. `network/graphs.py`:
`Params.paddle_offset`, and `edge_costs` carries a role into the page. New
`network/paddle_network.py`: the assembly below, the checks after noding, and the halo. `water.py`:
the build behind the switch, `Access.offset`, lake planes and stream decisions that can read
another build's edges, the two new source names. `paddle_geometry.py`: the offset region per body,
and the deviation proof. `sweden.py`, `norway.py`: the halo-loaded water, only with the switch on.
`encoding.py`: refuses a table where only some paddled sources carry a role, or an unknown one.
`js/routing_graph.js`: decodes `roleOf` (per source) and `bankAnchor` (per node). The park table's
`paddle_offset` and a `--paddle-offset` flag in `route_graph.py` and `lomsdal_visten.py`; the
source totals there and in `water.report` list the new sources. Tests in `test_paddle_network.py`,
`test_encoding.py` (the page's decoder run in Node on a payload with every role) and
`test_kayak_routing.py`.

*Off is main.* Abisko built with the switch off from cached inputs (`build.py`): the encoded data
stream and every graph field of the header are byte-identical to the published page's
(`b842a001…`), and edges and chains, geometry, values and heights, to phase 10's frozen ones:
105,923 edges, 49,101 nodes, 257,555 vertices, graph Brotli 1,693,176 bytes (12a's figure, so its
method is reproduced), 161.8 s. **The page is not quite:** the decoder's
role block is new text in it, and reads nothing on a graph without roles. For review below.

*How the switch-on build works — implementation choices, not Uwe's.* The build first nodes
today's network as it always has; everything the line must keep reaching is read off it: 12a's
contact inventory in production form (launch and carry ends, ways at the bank and over the water,
bridges, mouths, stream ends, dam sides), every bridge, the stream edges phase 7 decides on and the
bank samples phase 9's lake planes read. The offset network then replaces Shore, Open water and
Streams and is noded once more with bridge inference off:

- **Sources** (roles in brackets): Shore = contour, factor 1 (travel); Narrow water = centre lines and
  transitions, 1 (travel); Landing water = spurs and mouth joins, 1 (landing); Open water = caps held
  by two shoulders, chords, the exact interfaces, interface links, 12d's open-water spurs and lake
  crop seams, 1.5 (open); Streams unchanged (stream). All but Streams are settled. Lake owners of the
  halo-loaded water take the bank's labels and registered levels by their delivery rows (364
  matched, 1 lake only in the halo, 0 merged).
- **Chords**: Delaunay edges between the written contour's vertices (Shore and caps), kept where
  one owner's unsimplified offset region, cut to the extent, covers them within 0.1 m (the written
  vertices lie a grid move off it), that are not a contour segment, not within 0.1 m along an
  interface or crop seam, and meet no contour, interface or seam between their ends; then cut at the
  dam discs as today. A lake keeps its crop seam. Abisko: 93,491 candidates, 32,533 contour segments,
  32,070 outside the region, 25 along an interface, 26 meeting a line, **28,837 chords**. Caps and
  centre transitions needed no rule of their own: a cap is part of the region's outline, and the
  centre lines lie outside it and meet it at pinned join vertices.
- **Noding**: a spur's bank end is the contact's own coordinate, its line end the exact nearest point
  of its target, joined by the settled join; a mouth join starts on its stream the same way; each
  written piece end at an interface is inserted into the interface (296). 12c's contacts where two
  written lines cross (59 on Abisko) are noded by the build at the crossing; none needed a shared
  vertex. A dam anchor whose written point 12c's rule moved out of the disc moves the carry, launch
  or bridge ending there with it (none on Abisko; tested). 17 duplicate Landing water lines dropped
  (a stream end reached both as a contact and as a mouth); none remain.
- **Bridges**: every bridge of the first noding, carried over as a settled line; none is inferred
  again. Abisko: 551 as they were (land and streams), 391 now ending at their anchor, 1 between two
  bodies to both anchors, 972 between two banks of one body dropped (the water joins them), 74
  dropped whose bank end has no spur, all at the crop, as phase 9 left such ends.
- **Stream directions**: phase 7's gate reads the first noding's stream edges, measured with the
  new network in one pass of the height model, and its decision is carried to the new edges by chain;
  lake planes read the first noding's bank samples the same way.

*Abisko, switch on, against 12a's baseline:*

| | Baseline (switch off) | Switch on | Ratio / growth |
|---|---:|---:|---:|
| Edges / nodes / vertices | 105,923 / 49,101 / 257,555 | 119,051 / 60,912 / 300,073 | 1.124 / 1.241 / 1.165 (limit 1.5) |
| Graph Brotli bytes (12a's method) | 1,693,176 | 1,815,873 | +122,697 (page allowance +0.5 MB) |
| Graph build s | 161.8 (161.8 here) | 414.2 (401.3 in an earlier run of the same graph) | **2.56×** (2× = 323.6) |
| Peak RSS MB | 1,375 | 1,651 | |

| Source, switch on | Edges | km | Bytes it costs the graph |
|---|---:|---:|---:|
| Shore | 27,621 | 752.701 | 193,349 |
| Narrow water | 7,174 | 239.816 | 172,103 |
| Landing water | 3,485 | 25.516 | 66,427 |
| Open water | 31,179 | 3,412.483 | 498,270 |
| Streams | 2,219 | 55.807 | 35,346 |
| Bridges | 1,011 (1,989 off) | 4.416 (15.789) | 12,068 |

"Bytes it costs" is the graph re-encoded without that source, subtracted. Walking: 44,994 → 45,138
edges, 1,601.6 km both (the new lines node the ways that cross them); carries, ties and launches
keep their lengths to the metre.

*Kept and checked on Abisko.* Every stream chain keeps phase 7's direction: 311 of 311, 277 one way
in both, 130 now cut into more edges and 218 cut at different places. Every lake plane is the
bank's: 364 of 364. After noding and the page's grid: Shore at least **12.9602 m** from the
unsimplified bank, no segment under 12 m, nothing dry; Narrow water 25.766 m dry over 1,209 edges
near the bank (12c's 25.89 m); Landing water 479.318 m outside the water, bank steps included;
Open water 2.164 m, all within 0.1 m of the bank (interface ends, caps, links; the chords lie at
least 12 m inside). Loose ends: Shore 24 (the crop), Narrow water 1,045 (bay branches ending at
the bank, as 12c kept them), Open water 81 (interface and seam ends on the bank), **Landing water
1,566, every one a bank anchor with nothing left on land** — mostly where the only land side was a
bridge between two banks of one body; no spur's line end failed to node (the six ends found within
2 cm of a line are anchors beside a centre branch's end). No dam in Abisko's water.

*Build time.* The 12c-2 option: on every segment Douglas–Peucker chose alone, the 2.1 m bound is
proved (both directions: a dropped vertex lies within the tolerance of its segment, and the raw run
crosses the perpendicular through any point of the segment within the tolerance; the grid adds each
segment's larger end move; the bound is the segment's largest dropped distance plus that move),
and only segments a pinned or given-back vertex split are sampled. On
Abisko's whole contour (`proof.py`): 3,798 pieces identical both ways, every sampled figure within
its proved bound, largest bound 2.0999 m, 986 pieces with a split segment; the contour 132.1 →
122.2 s. The sampled figures are in the tests and the evidence, not the build. It is not enough:

| Abisko graph build, s | Switch off | Switch on |
|---|---:|---:|
| Loading (the bank's outlines 15.2 / 16.2 of it) | 17.0 | 18.1 |
| Walking noding | 26.9 | 25.4 |
| Noding with carries and launches | 64.2 | 64.3 |
| Line off the bank: contacts / bodies / contours / landings / chords / assembly | – | 0.4 / 2.7 / 138.9 / 8.3 / 6.6 / 5.3 |
| Noding again, bridges carried | – | 75.8 |
| Checks after noding | – | 3.7 |
| Derived fields / heights (with the probes) / the rest | 20.1 / 20.5 / 13.0 | 21.3 / 25.3 / 17.8 |
| **Total** | **161.8** | **414.2** |

Options, none of them changing a line: (a) the offset geometry body by body in worker processes —
Abisko's largest body took 59 s in 12c-2, so the step floors near that, about 80 s less, still
about at the 2× line (about 334 s); (b) keep the offset geometry by a digest of its inputs (halo water, dams, anchors,
code), so a rebuild of unchanged water skips about 160 s (about 255 s, 1.6×) and only a first build pays;
(c) node the new water into the finished walking network instead of noding everything a second
time (71 s), a refactor of the graph build whose identity would need proving; (d) a larger
allowance for 12g. For Uwe or review; the gate is not weakened here.

*What 12f must know.* With the switch on every paddled source in the header carries `role`, and
the page's graph has `roleOf` (by source) and `bankAnchor` (by node: 1 where Landing water is the
only paddled line). Nothing routes differently for either; the snapping of §1.6 is 12f's. The
1,566 dead-end spurs are bank anchors a tap must not snap to. Phase 11's interior entries see the
new lines as they are: every Shore, Narrow water, Landing water and Open water segment is an
eligible kayak segment, and the bank anchors are nodes like any; excluding Landing water and bank
anchors there, as snapping excludes them, is 12f's to measure (§4.3). Open water is still one
source by that name, as `plan_mode.js` requires.

*For review.* Whether the decoder's role block may change the page while the switch is off, or
belongs in 12f; the build-time options; whether the 1,566 dead-end spurs (anchors whose only land
side was a bridge between two banks of one body, or the crop) should be left out rather than drawn;
the 74 bridges dropped at a bank end without a spur; and the choices marked above. Malingsbo-Kloten
and Lomsdal-Visten were not built: 12g. Malingsbo-Kloten's stream directions are phase 7's by
construction (the gate reads the first noding's edges) and by the tests, not yet by a build.

**Uwe's decisions, 2026-09-27, on 12e's stop.** Verbatim: *"Ja mach c und erlaube 3x Dauer."*

- **Option (c):** node the new water into the walking network once, instead of noding the whole
  network twice. Today the build nodes main's whole network first. That graph is never shipped. It
  only serves as a reference for contacts, bridges, stream decisions and lake planes. Then it nodes
  everything again with the new water.
- **Build-time allowance for the offset line:** the total graph build with the switch on may take up
  to **3×** the baseline graph build of its map (161.8 / 388.0 / 1,025.4 s). Above that is a stop.
  This replaces the plan's 1.5× aim / 2× stop for this line. Page Brotli, graph size and kayak p95
  budgets are unchanged.

**Review's decisions from the 12e report (not Uwe's).** Keep the role decoder in `routing_graph.js`
in 12e: it is inert on a graph without roles, and the graph payload with the switch off is identical.
Leave out the 1,566 dead-end Landing water spurs, whose anchor has no land side, no stream and no other
water left (mostly the dropped bridges between two banks of one body), and report the count per map;
a spur whose anchor keeps any land, stream or launch/portage side stays. Accept the 74 bridges dropped
at the crop, as phase 9 treats crop ends. Accept the 12e implementation choices listed in its note.

**Done 2026-09-27 — 12e-2: the dead-end spurs are left out and the noding is faster; option (c) is
not built, because once the noding was fast it would save at most 32.4 s of 346.2 and would not be
simpler.** Abisko's switch-on graph build takes **346.2 s, 2.14× the baseline, 139.2 s under the
3× line (485.4 s)**. The switch-off graph is still main's byte for byte. Evidence, scripts and logs:
`~/mockups/kayak-mode/offset-plan/phase-12e-2/`. No page, tile or browser run, no push.

*What changed.* `routing/noding.py`: `cut_line` cuts a line in one pass instead of calling shapely's
`substring` once per piece, which walks the line from its start every time; the pass repeats
`substring`'s own arithmetic (the same running sum in the same order, the vertices strictly between
the two distances, the same interpolated ends), and falls back to `substring` for anything but
increasing positions inside the line. `routing/graph.py`: `_join_ends` reads its candidates by array
instead of row by row. `network/paddle_network.py`: `_without_dead_ends` leaves out a Landing water
spur whose bank end no other line of the build (bank, centre and open water, bridges carried over,
streams, walking lines, carries, launches) reaches within the node tolerance; a second spur from the
same point counts as reaching it, and a stream mouth's join always stays. The evidence reports the
count as `dead-end spurs left out`.

*Why not (c).* 12e's second noding cost 75.8 s because `substring` made every noding quadratic in a
line's cuts; profiled, `cut_line` was 38 of the 52 s of a noding of Abisko's ways and water. With the
one-pass cut the three nodings take 9.5 / 32.4 / 38.8 s. What (c) removes is the middle one, main's
network with carries and launches, 32.4 s, and it would have to rebuild what that noding gives for
free: the contact roles read off the nodes where ways meet the bank, and the bridges, which depend on
which ends of the whole combined network are loose. Both would be a second copy of the graph build's
own rules, to keep in step with it; the saving, less that copy's own cost, is under a tenth of the
build. The brief's rule — land (c) only if it is proven identical and simpler — keeps 12e's flow.

*Proof.* Switch off: Abisko built on this code from cached inputs is main's published graph byte for
byte (data `b842a001…`, every header field), 105,923 edges. Switch on, the faster noding alone: the
graph is 12e's byte for byte (payload, edges and chains; built with every spur kept). Switch on with
the spurs left out, against that graph, edge by edge by source and exact coordinates (`prove.py`):

- **1,564 dead-end spurs left out** on Abisko (1,640 edges: a spur crossing a line is cut there). The
  other 2 of 12e's 1,566 loose Landing water ends are line ends a spur reaches at the crop, as phase 9
  leaves such ends; they stay.
- 115,853 edges are the same edge, every column equal but 7: 5 Landing water `chain_id`s lose the
  digest they carried only because their id clashed with a spur now left out, and 2 costs differ in
  the last bit, on lines a spur's foot cut (a piece's cost is prorated from the piece it was cut from).
  Component membership is unchanged.
- The other 752 edges are the lines the spurs' feet had cut, whole again: 750 are their pieces joined
  coordinate for coordinate, the feet dropped as vertices (costs and lengths within 3e-14 of the
  pieces' sums, directions and kinds the pieces', lake edges on their lake's plane), and 2 edges keep
  their shape with one end moved 1.8 mm: a node is the first member of its cluster within
  the node tolerance, and that member was the spur's end.
- Every stream chain keeps phase 7's direction (311 of 311, 277 one way) and every lake plane is the
  bank's (364 of 364).

The route answers on phase 11's harness pairs were not replayed: the graphs differ only by edges no
route can pass through (a dead end) and by lines joined where such an edge left them.

*Abisko, switch on, against 12a's baseline:* 116,605 edges / 58,522 nodes / 295,172 vertices
(1.101 / 1.192 / 1.146 of the baseline; limit 1.5); graph Brotli 1,778,561 bytes (+85,385; 12e
+122,697); peak RSS 1,656 MB. Landing water is 1,836 edges, 12.850 km, and costs the graph 35,859 bytes
(12e: 3,485 edges, 66,427 bytes).

| Abisko graph build, s | 12e | 12e-2 |
|---|---:|---:|
| Loading | 18.1 | 17.1 |
| Walking noding | 25.4 | 9.5 |
| Carries and launches found, and their noding | 64.3 | 43.6 |
| Line off the bank: contacts / bodies / contours / landings / chords / assembly | 0.4 / 2.7 / 138.9 / 8.3 / 6.6 / 5.3 | 0.4 / 2.7 / 143.0 / 8.9 / 7.0 / 5.5 |
| Noding again, bridges carried | 75.8 | 38.8 |
| Checks after noding | 3.7 | 3.4 |
| Derived fields / heights (with the probes) / the rest | 21.3 / 25.3 / 17.8 | 22.3 / 26.1 / 17.8 |
| **Total** | **414.2** | **346.2** |

The contour is now 41% of the build and the next place to look if a larger map needs it (12e's
options (a) and (b)). The switch-off build is faster too, 130.3 s against 161.8 s, with the same graph.

*Tests.* `test_noding.py`: `cut_line` against `substring`, coordinate for coordinate, on random lines
of every scale, with heights, with returning vertices and with cuts at vertices.
`test_paddle_network.py`: no Landing water bank end of degree one on the small map (it had 4 with every
spur kept), and the rule on its own cases. The brief's test of one noding against two is not written,
as (c) is not built.

*For review.* Whether (c) is worth building later, should 12g find a map over 3×; that the switch-off build
changes speed but not a byte; the spur rule's reach (the node tolerance, 0.01 m). Malingsbo-Kloten and
Lomsdal-Visten stay for 12g, and their dead-end counts with them.

**Uwe on 12e-2, 2026-09-27:** that (c) stays unbuilt is fine. Verbatim: *"Ja passt das nicht umgesetzt
wurde."* ("Yes, it's fine that it was not built.") With it he started 12f: *"Weiter mit 12f"*.

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

*Uwe said "Weiter mit 12f" on 2026-09-27.* **Review's decisions, taken before the phase (not Uwe's):**

1. Snapping follows §4.3 as written: an ordinary water tap near the bank snaps to Shore or Narrow water,
   whose candidates reach at least d + 2.1 m (17.1 m), capped by `snapM`; Landing water and bank anchors
   are no ordinary water candidates; streams stay snappable; open water stays for deliberate open-lake
   taps and as fallback; land keeps its radius, and a deliberate land feature, launch, landing or explicit
   position keeps its meaning; with no travel line in reach the raw point stays raw.
2. Phase 11's interior entries skip Landing water segments; their end nodes stay candidates, as all nodes
   do. Shore, Narrow water and Open water take part like any eligible edge, within d + 250 m.
3. A graph without roles behaves exactly as today; every new path is gated on the graph carrying roles.

**Done 2026-09-27 — 12f: a kayak tap near the bank takes the line off the bank, a raw point enters no
landing in its middle, and the figures count every piece once; on Abisko with the switch on, 960 of 960
comparisons equal the extended reference and kayak p95 is 425.65 / 418.30 ms against 525.45 / 528.08.**
With the switch off, Abisko's graph is main's byte for byte and its 960 answers equal 12a's frozen labels
exactly. Evidence, scripts and logs: `~/mockups/kayak-mode/offset-plan/phase-12f/` (`README.md` first).
No push, publication, tile build or cache write; the pages built are scratch.

*The cache key.* No change: it cannot mix the two. `graphs.build` is the only path that reads or writes a
cached graph, and `sweden.build` and `norway.build` send every source list holding paddled or directed
water to `water.build`, which never caches. A build with no paddled water takes the cached path, and there
the switch changes nothing, so both settings are the same graph under the same key. Every switch-off key,
and every cached main graph, is therefore unchanged.

*What changed.* `js/plan_mode.js`: `waterRoles`, `nearestByRole` and `roleSnapped`, taken by `snapped`
only in a kayak on a graph with roles; `entryGeometry` marks Landing water in the same case and
`entrySegments` skips it, so `d` is measured to the lines that remain. `maps.py` and `lomsdal_visten.py`:
the plan setting `waterSnapM`, `PADDLE_OFFSET_M + CONTOUR_DEVIATION_M` = 17.1 m. `kayak_reference.js`: the
reference skips a Landing water segment in a kayak, read off the header's role, not the page's table.
`test_kayak_routing.py`: eight tests on a synthetic bank, two islands, a channel and a stream, and a
seeded differential with roles. `drive_map.py`: `OffsetTaps` on the scene (Abisko's fixed taps), two
readings, `the tap takes the line off the bank` and `the line off the bank is counted once`, which skip
with their reason on a page without roles (listed among each scene's skips until 12g), and the drive probe
records the landings a route uses.

*How the tap is decided — implementation choices, not Uwe's or review's.* Each kind is searched within
its own reach: land (every way, carry and launch), travel, stream, open. Inside the band of d + 2.1 m round
a travel line the travel line is taken before open water (interfaces and caps end on the bank there); a
stream competes with it by distance. Beyond the band the nearest water wins as before, so a tap out on the
lake takes the chord under it. Land wins when it is at least as near as that water. The junction rule
(`NODE_FIRST_M`, 2 m) is applied per kind, so a tap can move up to 2 m beyond the band onto a travel node.
An exact position (`SAME_SPOT_M`, a goal's stop, a place) gets no widened reach and no preference, only the
line it stands on, and never a landing. Walking and graphs without roles keep the old code path. A tap
within a finger of a launch's bank end takes the launch there (land nearer than water); the launch's bank
end is also the landing's, but it is chosen as the launch — for review.

*Prices and bounds.* Nothing in the router changed. The new sources are PADDLE with land 0 and cost length
× factor; floors use only connector metres (`cheapestMetre`, Open water by name) and network land, which
the new sources do not lower, so every bound stays admissible. The synthetic tests price every role whole
and in part (12e's test) and the seeded differential compares 64 role cases with the reference; with the
landing skip taken out of production alone it finds 12 mismatches.

*Synthetic readings (Node, `test_kayak_routing.py`).* A bank tap at a 6 m finger lands on Shore 14 m out;
beside a bank anchor and beside an open link it lands on the Shore line's node; 17.5 m from the line it
stays raw; a launch's bank end is kept; a road 2 m away keeps a tap whose Shore line is 43 m off, and a road 18 m away beats Shore 27 m away;
a chord takes a tap 100 m out at z15 and z12, a tap with nothing in reach stays raw; an exact point stays raw beside
Shore and on a landing, and is found on Shore; each island's tap takes its own line; a channel's tap takes
its middle; a stream tap stays on the stream, leaving downstream only; walking never snaps to water; a
graph without roles still snaps to a landing. A raw point 0.5 m from a landing has `d` = 9 m and no
landing among its entries, equal to the reference.

*Abisko, switch on* (page `59681c7a…`, 116,605 edges, as 12e-2). Fixed taps on Torneträsk by Abisko,
chosen by `choose_taps.py`: `the tap takes the line off the bank` (104 readings) and `the line off the
bank is counted once` (60) pass twice, 169 readings in each run with the page's own. At z17 (finger 5.3 m) and z15 (21.1 m):
bank taps land on Shore 13.10 and 12.72 m out, 14.63 and 14.20 m from the source bank; the narrow tap on
Narrow water 2.68 m out, 4.15 m from its bank and 5.64 m from the far one (0.74 m off the middle); the
path and launch taps stay on land; the open-water tap stays raw (nearest travel line 105 m); the island
tap takes its own line (13.05 m; the next is 19.0 m); the stream tap stays on the one-way stream; walking
takes no water. Along the lake: 591.22 m, all paddled (Shore 538.30, Open water 52.93), on the lake's
plane; from the launch: 230.83 m paddled (Landing water 16.36, once) and 7.70 m on foot. Panel, profile,
drawn parts and both files agree with those totals in both Stay-on-paths settings.

*Harness* (phase 11's Abisko sample: 200 pairs and 40 radius starts, four settings, 960 comparisons). A
stored endpoint that was attached is found again on the new graph at `SAME_SPOT_M`, as a goal's stop is;
a raw one stays raw — 164 attached and 1,756 raw endpoints on, 306 and 1,614 off (142 stood on the old
bank line). Switch on: 0 mismatches, largest error 2.91 × 10⁻¹¹. Entry candidates on the 864 raw kayak
endpoints: 97,088 segments with landings offered, 96,188 skipped (−900, −0.93 %; median 68 → 67, max
1,351 → 1,345); no `d` moved. Timing, the 200 phase-10 pairs after four warm-ups, Firefox 153:

| Kayak p95, ms | Landings skipped (built) | Landings offered | Budget |
|---|---:|---:|---:|
| Stay on paths off | 425.65 (p50 54, max 668) | 409.20 | 525.45 |
| Stay on paths on | 418.30 (p50 55, max 700) | 437.30 | 528.08 |

The two variants give the same answer on all 400 pairs; the difference in p95 is within run-to-run noise.

*Switch off.* Graph header and data byte-identical to main's page. The harness with the stored
attachments: 960 of 960 equal to the reference (largest error 2.91 × 10⁻¹¹) and to 12a's frozen labels
exactly (largest difference 0). The phase-11 kayak and entry selection plus the two new readings
(`only-off.txt`): 203 readings, twice green, the new ones skipped by the scene. `command make drive-all`
once on that page: 1,633 readings, 0 broken, 0 moved, 6 skipped by the scene (phase 11: 1,638; the 5 fewer
are per-frame readings of `the snap is drawn`, whose count follows the animation's frames, 75 against 80).

*What 12g must know.* Each map needs its own `OffsetTaps` (chosen on its switch-on page;
`choose_taps.py` is Abisko's) and the two readings taken out of its scene's skips when it is switched on.
Taps must keep ways more than a z15 finger away (21 m at Abisko's latitude), or land wins, as the rule
says. Abisko's island tap has its second line at 19.0 m, outside the band: a case with two travel lines
inside 17.1 m was not found near the start and is covered only synthetically. The existing kayak scene
figures were not read on the switch-on page; they move with the line and are 12g's. Malingsbo-Kloten and
Lomsdal-Visten were not built.

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

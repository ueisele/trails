# Route planning: notes for reviewing the phases

Working notes, not specification. The specification is
`route-planning-decisions.md` and `route-planning-phases.md`. This holds what a
reviewer needs that those two deliberately leave out: how the numbers in them
were arrived at, what this codebase does that will bite an implementation, and
what to look at in each phase.

## Where things stand

**Phases 1, 1B, 1C, 1D, 3, 2 and 3B are built and reviewed**, and the map is
drawn from the graph and carries it. `libs/src/trails/routing/`,
`libs/src/trails/network/`, `libs/src/trails/visualization/encoding.py`,
`analysis/scripts/route_graph.py` and `lomsdal_visten.py`. Their output is the
reference in the decisions document; **4–8 remain**. The project runs on
**Python 3.14** and `uv.lock` is tracked from 1D onwards.

The order these were done in is not the order they are numbered, and that was
deliberate: 1C → 1D → **3** → 2 → 3B → 4. Phase 3 went before 2 because its
acceptance is *the map behaves as it did* and 1C and 1D had just measured that in
a browser; a fresh baseline is perishable and phase 2's API wait is not. 3B waited
for 2 because two fifths of its payload is elevation.

**Phase 3B** put the graph in the page: `routing/order.py`,
`visualization/encoding.py`, a hand-written decoder in `maps.py` and
`edge_costs` in `norway.py`. **4.12 MB** in the page against an allowance of 5,
inflating in 0.34 s and reading into arrays in 75 ms, arriving as
`window.trailsGraph` and read by nothing yet. Every browser figure held and the
graph did not move. What it cost against the estimate, and the two findings the
review left, are in *What 3B found* below.

**And then the two fields it had left out**, on the same day and by decision
rather than by review: `waymarked` and `no_path_recorded` now travel in the
payload, are summed per chain by `routing/coverage.py`, and are shown in the
popup of every walked line layer. Nothing was recomputed for the payload; the
popup cost a `GRAPH_LAYOUT` bump and two offline minutes. Figures in *What 3B
found*.

When an agent is working in this tree: **documents only, no code, no
`git commit`** — the hook stashes unstaged changes and would pull work out from
under it. `command make hooks-run` will fail on half-written files; that is not
a finding. Check `git status` before assuming a phase has ended.

**Phase 2** added `io/sources/hoydedata.py` and `routing/elevation.py`, a series
on every walked edge with its ascent and descent, and four figures on every
chain. 20,183 requests in 13.6 minutes, none at all on a second build or on a
forced `--rebuild`, and not one figure of the graph moved — checked against the
cached pre-phase-2 graph down to the geometry hash, the chain ids, the total
length to six decimals and the total cost. The one thing that did not come out
is the documented 996 m; that is in *What phase 2 found* below and the decisions
document now carries both columns.

**Phase 3** drew the map from the chains and removed the source flags. Every
browser figure held — 198 markers, one non-interactive path, 25 layers, search at
10 px above the zoom at 60, wheel 9 → 11 — and the path count fell 12,357 →
11,589, which is 11,290 chains plus 298 circle markers plus the boundary. It
found that `Ukjent` was being read as a name and deliberately did not fix it,
because that moves the count it was accepted against; the fix came immediately
after, as its own change, and moved the reference to 11,290.

**Phase 1C** refreshed `uv.lock` and nothing else. Not one figure moved, folium
did not move either, and what did change is in *What 1C found* below.

**Phase 1B** added `routing/coverage.py`, the five Turrutebasen fields and N50's
`malemetode` onto the chains, and `waymarked` and `no_path_recorded` onto every
walked edge. Every phase 1 figure came out unchanged — checked against the
cached phase 1 graph rather than against the printed report: identical chain
ids, identical geometry, identical total edge length and cost to the last digit.
Two things it changed on the way, both found by measuring:

- **`no_path_recorded` is a half-length test, not an all-or-nothing one.** The
  literal "nothing within 25 m" reports 12.7 km where the documented measurement
  says 19.9, and reports one of the three named trips as having none at all. The
  decisions document now carries the reasoning and both numbers.
- **`pd.NA` was landing on chains as the text `<NA>`.** See the trap list below.
  It cost 2,713 phantom FKB chains before it was tracked down, and it was in the
  phase 1 code all along, waiting for a source column in a nullable dtype.

What the review changed, both measured rather than argued:

- **Turrutebasen was weighted 1.00, not the specified 1.02.** The implementation
  carried a comment saying the decisions document leaves it out; it does not —
  the table gives 1.02 and phase 1B spells out the reasoning. Corrected.
- **`--route-noding-m` defaulted to 8 m and is now 0.** Built both ways: chains,
  components, reach, quays and Mosjøen come out *identical*, so all it bought was
  234,358 edges down to 166,900 and two minutes down to one. What it cost was
  4,086 nodes (4.5 %) where two edges meeting there lie more than a metre apart,
  191 over five, the worst 7.55 m — gaps in any track stitched from edges. Both
  budgets hold without it (3.3 MB against 5, two minutes against single-digit),
  so the standing rule applied: reach for it only if a budget is exceeded. The
  parameter stays available; only the default changed.

Three smaller findings from the same review are fixed. One of them was larger
than it looked and is worth remembering:
`test_a_node_sits_where_one_of_its_edges_begins` ended in
`... or edge.source == "UT.no"`, which read like a known displacement being
tolerated. It was not: the fixture put the crossing at `x=150`, on the straight
tail of the wiggly line, where the simplified copy and the drawn line coincide.
The measured displacement was **0.0** — the test had never had a case. Moving the
crossing onto a wiggle (`x=37`) produces 3.034 m, and the bound is now asserted
against the tolerance, with `assert worst > 1.0` so it cannot go vacuous again.
**A green test that exempts something is worth measuring before believing.** The
other two: `carry_positions`' docstring now matches the window projection it
uses, and `fingerprint` now digests each source's identity and attribute values,
so a change in the SSR road names or the Turrutebasen route names is noticed.

### What the map is now

Everything through phase 3 is committed; the tree carries only phase 2's work in
progress. Two changes to the map are worth knowing because they are easy to read
as regressions:

- **The map is drawn from chains**, so a drawn line and a selectable track are
  one object. `describe_whole_roads` and `highlight_keys` are gone — both faked
  what a chain now is. The source flags are gone with them, and FKB therefore
  loads over the full 15 km rather than 5.
- **A chain is never cut at the park boundary**, which costs a little colour
  accuracy: 2.4 km of FKB, 8.4 km of N50 and 14.8 km of OSM inside the park are
  drawn in the approach colour, and 35 km of FKB outside it in the park colour.
  That is the rule as written, not a bug.

Before that, an audit of the popups against what each layer's data actually
holds turned up two things now folded into phase 3: **OSM was the only line
layer showing no length**, though `clip_to` had computed it all along, and **no
layer showed provenance** though every Kartverket line layer carries it. N50 and
Turrutebasen now say how and when a line was captured — the difference between a
path somebody surveyed and one carried forward off an older map, which is 47 % of
N50's here.

`bakke` and `mo` were added to the drawn place-name types afterwards, because a
name in the register that the map never draws looks like a name the map has never
heard of. Not `utmark`: a land-use category for a tract, not a feature with a
position. **58 % of the register's points in the zone are still never drawn** —
6,260 of 10,737 across 131 of its 151 types — and since the search only finds
what is drawn, a known name can still come back empty. Mostly right, since 805
hills and 751 streams would bury the map, but it is a phase of its own if wanted.

The map's warm-cache runtime is **53 seconds**, and the graph's is about two
minutes on a full `--rebuild`. Both read one cached graph, keyed by a fingerprint
that covers the sources, the parameters, the values the chains are built from and
— since phase 2 — a `GRAPH_LAYOUT` marker for what comes *out*. It does not
cover the library versions, which is why an upgrade has to be measured with
`--rebuild` or it replays the cache and reports everything unchanged without
executing a line of shapely.

The measurement scripts that produced the figures lived in a session scratchpad
and are gone. Their methods are below so a figure can be re-derived rather than
taken on trust.

## Verifying a build, concretely

The three commands and the two probes a review starts from. Everything else in
this document assumes them.

**Rebuild and read the figures.** `command make graph ARGS="--rebuild"`, about
two minutes. `--rebuild` is not optional after a library or interpreter change:
the fingerprint does not cover versions, so a plain run replays the cache and
reports every figure unchanged without executing a line of shapely. Confirm the
run actually says *Building chains per source*.

**Load the built graph in Python.** The newest `route_graph_lomsdal-visten_*.pkl`
under `.cache/objects/`, by modification time — the hash is the fingerprint and
changes with every parameter:

    key = sorted(glob.glob(".cache/objects/route_graph_*.pkl"), key=os.path.getmtime)[-1]
    net = cache_module.Object(cache_dir=".cache/objects").load(os.path.basename(key)[:-4])["network"]
    net.chains, net.edges, net.nodes

**Rebuild the map and drive it.** `command make map`, 53 seconds warm.
`uv run --with playwright`, `p.firefox.launch()` against the `file://` URL of
`analysis/output/lomsdal-visten.html`, and wait ten seconds after load — the page
is **31.1 MB** since 3B and the two coverage rows, and was 25.4 before either.
The five probes, with what they read after both:

| | |
|---|---|
| `.leaflet-marker-pane > *` | **198** |
| `.leaflet-marker-icon` | **0** — folium overwrites the class |
| `.leaflet-overlay-pane path` | **11,589**, of which exactly **1** has `pointer-events: none` |
| `.leaflet-control-layers-overlays input` | **25** |
| children of `.leaflet-top.leaflet-left`, by `getBoundingClientRect().top` | search **10 px**, zoom **60** |

and the wheel over the map, which takes zoom **9 → 11**. Reach the map object
with `window[Object.keys(window).find(k => k.startsWith('map_'))]`. There is no
`#map`; the container is `.leaflet-container`.

**The path count in this document said 11,591 until 3B measured it.** It is
11,589, which is what the decomposition beside it — 11,290 chains, 298 circle
markers, the boundary — added up to all along. A figure and its own explanation
disagreed by two for several days and neither was re-run. **When a figure is
written next to its decomposition, add the decomposition up.**

**And the graph in the page**, since 3B. `window.trailsGraph.ready` resolves to
it; `inflateMs` and `decodeMs` say what it cost. The round trip is checkable
from the page alone — fold the decoded values as `header.checksum` was folded
and compare. It reads **1,881,995,939 / 2,401,407,269** for the coordinates and
**814,474,384 / 3,748,383,096** for the heights, over 948,465 vertices and
1,406,040 samples.

**Do not probe the popups with `map.eachLayer`.** It walks the map's top-level
layers, which are the feature groups, and never reaches the lines inside them —
so it reports zero popups on a page that has eleven thousand. Count the label in
the HTML instead: *Marking, all sources* appears **11,269** times, one per chain
that is not a ferry, and *Unrecorded ground* **10**.

## How each figure was measured

Re-derive rather than believe, if a phase's output disagrees.

**Connectivity and components.** `unary_union` over every line, then `linemerge`;
union-find over exact edge endpoints — exact, not rounded to a grid, since
`unary_union` produces coincident coordinates at real junctions and a grid splits
near-coincident ones arbitrarily. Bridging adds a connector from every degree-1
endpoint to the nearest line within tolerance, then re-nodes.

**Reach across the park.** Not the share of length, which is the misleading
number: take the largest component's vertices that fall inside the park polygon
and compare their north-south extent to the park's own. 50.8 km of 53.9.

**Chains.** `linemerge` per source already yields maximal runs between junctions.
Strokes on top: at each node, bearings taken over the first 5 m of each arm, arms
paired greedily by smallest deflection, pairs above the threshold rejected.

**Elevation accuracy.** WCS tiles at several resolutions sampled at 300–400 real
FKB path vertices, compared against `ws.geonorge.no/hoydedata/v1/punkt` for the
same coordinates. At 1 m the WCS *is* the point endpoint: median 0.00 m.

**Sampling density.** A dense reference every 2.5 m along one real route, then
each coarser series interpolated onto it and the residual measured. Note the
bias: at 5 m spacing every second reference point coincides with a sample and
contributes zero error, so 5 m looks better than it is — the true advantage over
10 m is nearer 1.5x than 2x.

**Payload sizes.** Zigzag varints over deltas between consecutive points, one run
per edge, then gzip, then base64. Twelve times smaller than JSON arrays.

**Coincidence between two sources** — the figure behind the 34 % marked, the
94 % on a mapped line and the 19.9 km on nothing. Buffer each chain of the
subject by the tolerance, `STRtree`-query the mask for hits, union *only the
hits* and intersect. Buffering the whole union first is the obvious way and does
not finish. Always run it at two tolerances: if the answer moves little between
10 m and 25 m it is a property of the ground, and if it collapses below 5 m it
was GPS noise.

**Node displacement**, which decided `node_simplify_m`. Per edge, the distance
from each end's node position to that end's own coordinate, grouped by source.
Then, per node, the widest gap between any two edge ends meeting on it — that
second one is what a stitched route actually sees.

**A chain's elevation series.** Not sampled along the chain — the build samples
per *edge*, so points taken along the chain miss the store entirely. Take the
chain's edges, order them, and concatenate their series with the shared node
counted once. Verify the ordering before trusting it, by checking that
consecutive edges touch: 2,221 chains do not join up in the frame's own order,
so an unordered concatenation silently produces a plausible profile of a route
nobody could walk.

**Order them by walking the graph, not by projecting onto the chain.** This
document said "project each edge's first coordinate onto the chain" until 3B
measured it: that leaves 35 chains still not joining, because two edges of a
chain can project to the same place. It also mis-described phase 2, which walked
node to node from the start and used projection only to decide which *way* round
the finished run goes. `trails.routing.order.chain_order` is the walk, and both
the build and the page now use it — one walk, because two would eventually
disagree and both would still look like profiles.

**Reading the elevation store.** `.cache/elevation/hoydedata_25833.parquet`,
keyed on `east` and `north` as **integers in centimetres** — `round(x * 100)`,
not a rounded float. Getting that wrong returns a store full of misses that looks
like a store full of gaps.

**Payload encoding.** Zigzag varints over deltas, one run per edge, then gzip,
then base64 — geometry at 1e-6, elevations at 0.1 m. Measure the **edge table
separately**: as JSON it is 1.98 MB and as sorted delta-encoded columns 0.27,
which is the whole margin. Do not scale one payload from another; that produced
both of this phase's budget errors, in opposite directions.

**Provenance.** `malemetode`, `noyaktighet` and `datafangstdato` on N50;
`measurement_method`, `accuracy`, `origin` on Turrutebasen; FKB has none, and its
WFS `DescribeFeatureType` is what proves it rather than an absence in the loader.
Weight the breakdown by **length**, not by feature count — the two disagree
badly. Careful with fill rates: `notna()` counts `""` as populated, which made
FKB's fields look complete when they are at 3–6 %.

## What this codebase does that will bite

Every one of these cost real debugging time in the work leading up to this, and
every one was invisible until something was actually run.

- **A boundary polygon swallows clicks.** `folium.GeoJson` paths are interactive
  by default and a fill catches pointer events at 6 % opacity. The park boundary
  is drawn last, so for a long time *no* trail inside the park was clickable in
  any layer. Fixed with `interactive=False`; watch for it whenever something
  large is drawn on top.
- **A panel outside the map container swallows the wheel.** Anything positioned
  over the map must be a Leaflet control, added with
  `L.DomEvent.disableClickPropagation` but deliberately *not*
  `disableScrollPropagation`, and text inputs must stop key events or typing a
  `+` zooms the map.
- **Leaflet appends controls to the end of a corner.** To sit above the zoom
  buttons, a control has to be moved to the front of its corner after `addTo`.
- **folium overwrites Leaflet's own marker class** with `awesome-marker`, so
  `.leaflet-marker-icon` matches nothing. DOM probes must address
  `.leaflet-marker-pane > *`. This produced a false test failure and a false
  "zero markers" reading.
- **`json.dumps` does not escape `<`.** A value carrying `</script>` closes the
  block. `maps._script_json` exists for this; use it for anything embedded in a
  script tag.
- **Redraw cost is a real constraint.** Rebuilding a layer per keystroke, and
  writing a style that is already set, each froze the map badly enough that the
  wheel piled up and only landed when typing stopped. Apply differences; read
  before writing.
- **`sjoin_nearest` emits one row per tied match**, silently lengthening a frame.
- **Proximity alone is a weak join for lines.** At a junction the first metres of
  a side road lie within tolerance of the main road: 23 % of matches followed
  their road for under half their length until `min_overlap` was added.
- **Ids are not as unique as they look.** SSR road ids repeat where a road
  crosses a municipal boundary — correctly, that is what reunites it. And a
  single null in an integer column makes pandas store it as float, so `1113860`
  becomes `1113860.0` and hashes differently.
- **There are three ways a frame says nothing and `pd.NA` is the one that gets
  through.** `None` and a float `nan` are what an object column holds; a column
  in a nullable dtype holds `pd.NA`, which is neither, and Turrutebasen's loader
  produces `string` columns throughout. A check written as
  `value is None or isnan(value)` passes it, `str()` turns it into the text
  `<NA>`, and it lands on the chain as a value. As an attribute that fills an
  empty column and reports it 100 % populated; as an *identity* it makes every
  unnamed line in the source the same way as every other unnamed line, which put
  2,713 chains onto FKB that are not there. `pd.isna` is the test. The symptom
  was a chain count moving in a source nothing had been done to — attributes had
  been added to Turrutebasen and FKB was what moved.
  **Under pandas 3.0 this is half true, and the surviving half is the dangerous
  one.** The scalar is unchanged: `str(pd.NA)` and `f"{pd.NA}"` are still the
  text `<NA>`, so the trap above stands exactly as written. What moved is the
  *vectorised* path — `Series.astype(str)` no longer stringifies a missing value,
  it leaves it missing, and `.str.cat()` then drops it. Phase 1C found this the
  only way it shows: the graph's cache fingerprint changed without one figure in
  the graph changing, because `_values_digest` concatenates exactly that way.
  That reads like an improvement and is not. Dropping a missing value throws away
  its **position**: `['A', NA]` and `[NA, 'A']` both concatenate to `'A'` and
  digest the same, where pandas 2 wrote `<NA>` into the run and kept them apart.
  So the vectorised path is no longer a safe way to summarise a column, and the
  scalar path was never one. Neither is a substitute for `pd.isna`. What this
  costs `_values_digest` is written up under *What 1C found*.
- **Merging pieces of a line does not deduplicate them.** Measuring how much of
  an edge lies near a mask, the natural form is to intersect the edge with each
  nearby line's buffer and merge the pieces. Those pieces overlap where the mask
  lines do, and at projected-CRS magnitudes they do not dissolve into one
  another: one edge came out at **3.6 times its own length**. Merge the buffers
  into one area first and intersect once. It is also 8× faster to shortcut the
  two cases that need no merge at all — one mask line covering the whole edge,
  which is 99 % of them, and only one line near it.

## Before handing a phase over

This has been done for 1B, 2, 3, 3B and 4 and **found something every time** — a
rule that was not implementable, two acceptance figures that would have failed a
correct implementation, fifteen attributes nobody had counted, a missing layer, a
forgotten payload, a budget off in both directions. Reading the phase never finds
these. The check is:

1. **Load the built graph and measure what the phase asserts.** Every figure in a
   phase should be reproducible from `.cache/objects/` in a few lines. One that
   is not is either wrong or was never measured.
2. **Ask what the phase needs that nothing provides.** The popup ascent, the node
   positions, the per-chain figures and the edge order were each specified for a
   consumer with no producer.
3. **Ask which phase receives each requirement of the decisions document.** That
   is the inverted form and it found the page encoding, which was specified over
   thirty lines and belonged to nobody.
4. **Read the phase end to end afterwards.** Patching a phase four times produces
   four contradictions; phases 2 and 4 both had to be rewritten as one text after
   being corrected in pieces.

Do not hand over a phase whose acceptance figures were derived rather than
measured. Two of them — FKB's 173 km and Sjøbergmarsjruta's 996 m — came from a
different method than the rule they were stated against, and both would have told
a correct implementation it had failed.

### The prompt that has worked

Five phases in, the shape is stable: point at the three documents and say to read
all of the phase, not the summary. Name the commit the tree is at. List the traps
by name — each one cost real time here and none is deducible. State the
acceptance as measured figures. Say what is **not** to be built and why, because
that is what stops a helpful agent widening the scope. Require a browser for
anything visual, with `uv run --with playwright` and no new dependency. End with
*run a code review, work the findings in or say why not, then stop and report*.

Give an agent an escape hatch — *if this is bigger than it reads, say so and
stop* — and take it seriously when used. It has been right both times it was
invoked.

## Reviewing each phase

The two expensive gaps in the specification were found by *running things* and by
being questioned — not by reading it. Review the same way.

**Anything, first.** Did it add a dependency? Nothing in the eight phases needs
one — shapely, geopandas, requests and pyarrow cover all of it, and the browser
work adds nothing at all. A new entry in `pyproject.toml` or a changed `uv.lock`
is a finding until it is justified, not a detail.

**Phase 1, the graph.** First: was Turrutebasen included? Every documented figure
was measured without it, so a graph that has it will exceed the stated edge count
— correctly. Judge by the reach, which should hold at 94 %, and record the new
counts as the reference.

Then the figures are the test: chains, edge count, largest
component, reach, Mosjøen, and the ferry numbers. Check that chain ids are stable
across two builds — rebuild and diff them. Check a road that branches, such as
Tveråvegen, selects one arm and not eight. Check a ring-shaped chain does not
crash whatever looks for endpoints.

**Phase 1, simplification before noding — settled, kept here as the method.**
Phase 1 reported that Turrutebasen braids against FKB and introduced a
`node_simplify_m` to deal with it. The three checks below were run and the
outcome is in "Where things stand": the geometry on the edge was never thinned
(check 1 passed cleanly), and checks 2 and 3 decided it — measured, it changed
nothing but the edge count, and cost node accuracy. The default is now 0. Re-read
this if the parameter is ever proposed again.

1. **What ends up on the edge.** The specification allows simplifying *what goes
   into the noding* and requires the **full geometry to remain on the edge**. If
   the stored geometry has been thinned, that is a finding: accuracy was the one
   thing stated as non-negotiable, and this is exactly where it would quietly go.
   Compare an edge's vertex count against its source features.
2. **Whether it was needed at all.** 24,478 extra edges take the graph from about
   130,000 to 155,000, which a Dijkstra does not notice. The drawn objects are
   untouched, since Turrutebasen keeps its routes as units. The only real symptom
   is a route able to hop between Turrutebasen and FKB every ten metres — and the
   source weights, 1.02 against 1.05, already hold it on the better one. Ask what
   the measured cost was before accepting a mechanism against it.
3. **Whether it treats the cause.** The braiding produces crossings, not
   vertices, and none of those crossings is a junction: both lines carry on the
   same way. Filtering crossings by angle — the stroke rule applied to noding
   rather than chaining — addresses that directly, where simplification only
   removes the wiggles that happen to cross. If `node_simplify_m` survives
   review, it should be because it was measured to work, not because it was the
   first thing to hand.

The same question applies to UT.no, which has the same problem for the same
reason and where the specification already sanctions simplifying the noding
input.

**The order to do this in: build without it, measure, and reach for it only if a
budget is actually exceeded.** Simplification is not a free optimisation — fewer
crossings means different nodes, which means different chains and possibly
different connectivity. It is an intervention, and it needs its own before-and-
after on reach and chain counts, not just on the edge count it was aimed at.

Budgets worth stating, so "too large" is testable:

- the graph's whole contribution to the page stays under about 5 MB, against the
  1.8 MB of geometry already measured
- noding stays within single-digit minutes

Neither looks threatened by 25,000 extra edges: a Dijkstra does not notice
155,000, the edge records add a few hundred kilobytes, and the geometry is
unchanged because it is the same vertices either way. If the measurement says
otherwise, that is worth knowing on its own.

**Phase 1B, what the graph carries.** Rewritten after the phase 1 review: three
of its four original points were already satisfied and are struck through in the
phases document. What is left is Turrutebasen's attributes, N50's `malemetode`,
and the two derived edge fields.

The acceptance is the same for all of it and it is the thing to check first:
**no figure from phase 1 may move.** Attributes ride along the chains, only
`identity_field` decides them. 11,290 chains, 234,358 edges, 757 and 747
components, 50.8 km = 94 %, 17 quays, Mosjøen at 2.17 m. If any shifts, something
touched the geometry, and that is the finding rather than the new column.

Then the two derived fields, each with a number to land on:

- `waymarked` — UT.no **31 %**, FKB **246 km**. These were re-measured under the
  rule as specified, after an earlier draft of the phase quoted 34 % and 173 km
  taken from *different* measurements: the first a plain length overlap rather
  than the half-length test, the second the `attach_nearest` name join at 25 m,
  which never saw N50's own marked paths. A correct implementation would have
  been told it had failed. **Check that a predicted figure was measured under the
  rule it is predicting, not merely near it.**
- `no_path_recorded` — near **19.9 km** of UT.no's 376, and it must be
  concentrated in three trips rather than spread thin. Spread thin means the
  25 m tolerance was not applied.

Two things the specification had wrong until they were checked, both worth
re-checking in the implementation: **ferries must be excluded** from both derived
fields — a crossing has no path mask within 25 m, so 149 km of it would be
flagged as pathless — and `waymarked` must be built from **masks over the raw
sources**, not from the edge's own attributes, because `rutemerking` reaches an
edge only through its chain, where `_combine` has already merged 158 km of it
into an ambiguous `JA / NEI`.

And the trap the whole design rests on: **its absence asserts nothing.** If any
text, name or docstring reads it as "there is a path here", that is a finding.

**Phase 1C, the dependency refresh.** Run phase 1's statistics before and after
and compare. Any movement in edges, components or reach is the upgrade's doing
and nothing else's — that is the whole reason it sits here rather than later.
Then drive the map in a browser: clicks reaching lines, the wheel reaching the
map, markers rendering at all. The trap list above was observed under **folium
0.20.0**, which is also what the upgrade left installed, so none of it needed
revisiting; the "0.17" this document used to give was the floor in
`pyproject.toml` read as a version. See *What 1C found* below.

**Phase 2, elevation — built.** The invariance is the test: the same route's
ascent at 5, 10 and 15 m sampling. Then check the cache actually holds — a second
run must issue no requests. Then check a coastal path: any profile touching
−276 m means `datakilde` is not being checked. All three passed; see *What phase
2 found* below for the one figure that did not.

Two things the phase was checked against reality for, before it was handed over:

- **Both ascent *and* descent, everywhere either is stored.** The specification
  said ascent alone until it was asked what a popup would actually show. A chain
  is oriented so its id is stable, not because a walker takes it that way, so an
  ascent figure is true in one direction and silent about the other. If only one
  number came back, that is the finding — and it was added to the phase while
  phase 2 was already being implemented, so it may need saying out loud.
- **Ask which ascent figure a number came from.** There are two and they are not
  interchangeable: per edge for routing weights, per chain over the full series
  for anything shown. Summing the per-edge ones does not approximate the
  per-chain one, it destroys it — 42 % of the edges are under 5 m and the median
  is 6.9 m, so under the threshold most report nothing at all. The decisions
  document said the opposite until this check; if a figure looks suspiciously
  low, this is why.
- **"Sjøbergmarsjruta" is three chains** — UT.no, Turrutebasen and FKB all draw
  it, all 20.48 km, all starting at the same rounded point. The acceptance names
  one figure against a name that resolves three ways, and the UT.no one is a
  consumer GPS track whose noise adds climb. Insist on all three.

What did *not* need changing, having been measured: 20,358 requests against a
documented 22,000, 1.02 million elevations against 1.1, and 16.4 minutes against
"about seventeen" — the endpoint answered a probe in 0.29 s. The graph nearly
doubled since those were written and the figures still hold, because
deduplication absorbs it.

**Phase 3, drawn from the graph.** Nothing new should work; everything old
should still work. This is the phase where a regression hides, and the specific
place it hides is a popup.

The phase was checked against the built graph before it was handed over, the way
1B was, and "popups keep what they show today" turned out **not to be achievable
as written**: fifteen attributes had to be added to the chains, UT.no's four
links and its summary among them. So the first thing to review is not the
mechanism but the content — open a popup of every one of the seven line layers
and compare it against the map committed at `8497154`.

What that inventory also turned up, and what to check it was honoured:

- **`is_dnt` splits Turrutebasen into two of the seven layers**, so a missing
  flag is a missing layer rather than a missing field. It is derivable from
  `maintenance_responsible`, but 113 of 244 chains carry more than one
  maintainer and three of those, 9.4 km, are part DNT and part not. Decided:
  `.any()`, as today. Check that the decision was taken rather than stumbled
  into.
- **`osm_id` on a chain is a list**, because 64 % of the OSM chains span more
  than one way — worst case 33. Decided: keep it joined, plural label.
- **`describe_whole_roads` should be gone.** A chain *is* the whole road arm now;
  that function existed to fake it. `road_length_km` becomes `length_m`. If both
  still exist, something was carried across that should have dissolved.
- **The whole-named-way figure** is now a sum over the chains sharing an
  identity. 132 of the 2,326 road chains carry more than one `road_id`.

And a correction to this document, which had it wrong for several days: **the
`--simplify-m` on the drawn copy does not contradict "do not simplify to save
space".** That rule governs the exported and routed geometry, which keeps full
precision. Folium writes drawn geometry as JSON coordinate arrays, measured at
22.4 MB for the network's vertices. Anyone "fixing" the apparent contradiction
by removing the simplification puts twenty megabytes into the page. The script
has said `GPX keeps full detail` all along; I read the two rules as one and they
are not.

The browser baseline is measured rather than remembered, because 1C and 1D both
drove the map and it read the same each time: **198** markers in
`.leaflet-marker-pane > *` and 0 under `.leaflet-marker-icon`, **12,357** paths
of which exactly **1** non-interactive, the search control at **10 px** against
the zoom at 60, and the wheel taking zoom **9 → 11**. All of those must come out
identical. The path count is the one figure that should move, roughly halving as
23,876 objects become 11,290 chains — it landed at **11,589**.

**Phase 3B, the page payload.** It exists because reading the decisions document
against the phases turned up an encoding specified over thirty lines — zigzag
varints, gzip, base64, `DecompressionStream` — that no phase had claimed, while
two later ones assume it. **Ask of any specification: which phase receives this?**
That question found this, and it found the popup ascent in phase 4.

Review it on the round trip, not the size: decode the whole graph in the browser
and compare against the source coordinates. A decoder correct for 99.9 % of runs
has a bug in the long ones.

Then the budget, which was measured after the phase was written and turned up two
errors in it. The geometry is **cheaper** than the scaling suggested — 2.35 MB
against 3.30, because gzip does better on more data than a linear scale assumes.
And the edge table, which the draft listed as a deliverable and left out of the
budget, is **1.98 MB as JSON** and puts the total at 6.5 MB, over. Sorted by
`from_node` with both columns delta-encoded it is **0.27 MB**. That seven-fold
difference is the whole margin: 4.8 MB against an allowance of 5.

A second pass once phase 2 had run corrected the table again in the other
direction: the elevations were estimated at 2.2 MB and measure **0.98**, so the
total is 3.6 rather than 4.8. **Both errors were estimates standing where the
document demands measurements**, and they pointed opposite ways — which is what
estimates do.

The same pass found the ordering problem is larger than the phase first said.
**2,212 chains, one in five, have edges that do not join up in the frame's own
order**, with jumps to 20 km. So the order is not something sorting breaks; it
is already lost and has to be reconstructed and carried. Phase 2 solved that for
itself by projecting each edge onto the chain, without being asked to and without
saying so — check that 3B does not assume the frame order is meaningful just
because phase 2's figures came out right.

So the check is: was the table encoded or serialised, and did the sort scramble
what ties an edge to its chain? A scrambled graph is not obviously broken.
`cost` should not be in the payload at all — it is length times a source factor
and the browser has both.

**Budgeting a payload by scaling another payload does not work.** That is what
produced both errors here, in a document that insists elsewhere on measuring.
A third followed, and it is the instructive one: see *What 3B found*.

**Built. The check that mattered, kept for the next payload:** the header's
checksums prove the *page* agrees with the *encoder*, and nothing more. They are
computed from the same array the encoder writes, so an encoder that laid the
wrong geometry against an edge would write a checksum for the wrong geometry and
the page would confirm it. Decode the stream separately — from the format
description alone, not from the encoder — and compare against the frame. Over
all 234,358 edges that reads a worst coordinate error of 0.0557 m and a worst
height error of 0.0500 m, which are exactly half a quantum each and therefore
rounding and nothing else. **Two implementations agreeing is not a round trip
when one of them defined the answer.**

**Phase 4, the profile.** Two of its requirements arrived late and by being
questioned, which is worth knowing when reviewing it.

The **popup ascent** had fallen between phases 2, 3 and 4 — the decisions
document calls it the main thing the sampling buys and no phase had claimed it.
A first attempt to place it here reasoned that phase 4 was "the first to have
both" the elevations and the rebuilt popups; that was wrong, since popups are
rendered in Python at build time and need nothing from phase 3B's payload. Phase
4 owns it only because it is the first phase after phase 2 that touches the map.

**Descent, and the direction**, arrived when the plain question was asked: after
this phase, do I see ascent *and* descent per segment? The specification said
ascent alone, stored only per edge, with descent appearing solely in the panel's
description. And a first fix — anchoring the numbers to the endpoint elevations
— was refused for the right reason: it says which direction the figures describe
but not which end of the drawn line you are standing at. The answer is one
direction shown three ways, the arrow being the part that actually orients
anybody. **A number that depends on direction is not finished until the reader
can see the direction.**

Check it is hand-drawn SVG and nothing is fetched from
a CDN — a CDN script fails silently on `file://`. Check the map still zooms while
the panel is open.

**Phase 5 and 6, export.** Open the file. A ferry or a water leg must break the
track into segments, not draw a line across the fjord. Import it somewhere.

**Phase 7, editing.** Reorder and watch the numbers; the failure mode is a stale
leg or a profile that no longer matches the line.

**Phase 8, loading.** Round-trip one of this map's own exports and check it comes
back identical — that is what the `<extensions>` exist for. Then load a foreign
track and watch the middle mode: a track running beside a parallel path will snap
to the wrong one if only distance is checked. And confirm that generated
waypoints — boundary crossings and the like — are *not* read back as waypoints
someone placed.

## The question that found the expensive gaps

Both of the specification's serious omissions were found the same way, by asking:

> **What is visible on the map but missing from the graph?**

Ferries came out of it — they were drawn all along and had been silently passed
over because nobody walks a ferry, which would have cut off the entire western
approach and eleven of seventeen quays. Free legs over water came out of the same
question one step further on.

Ask it again against the inventory below before accepting that a phase is
complete. It is a better instrument than re-reading the specification, which
found only the cheap gaps.

**And ask it of the point layers too, not only the lines.** That was the third
omission and it went the same way: the map draws 104 cabins from N50, nine named
huts from SSR, seventeen quays and eighty trailheads, and nothing in the plan
used any of them. They are not routable and should not be — but a waypoint set
beside one should carry its name into the export, which is now phase 6. The
question is not only "is it in the graph" but "does anything use it at all".

### What the map draws today

Lines, all of which belong in the graph:

| layer | in the graph |
|---|---|
| Roads, public and private [N50+SSR] | yes |
| Ferry crossings [N50] | yes, as crossings — not walking |
| Paths in park and approach [FKB] | yes |
| Paths in park and approach [N50] | yes |
| Paths in park and approach [OSM] | yes |
| Marked and DNT routes [Turrutebasen] | yes, keeping their published unit |
| Routes and access routes [UT.no] | yes, keeping their published unit |

Points, none of which are routable and none of which should be:

Cabins and wilderness huts [N50] · Named huts [SSR] · Huts and shelters [OSM] ·
Quays [SSR] · Ferry quays [OSM] · Trailheads, farms and sæters [OSM] · Towns and
villages [OSM] and [SSR] · Farms and holdings [SSR] · Terrain names [SSR] ·
National park boundary [Naturbase]

That inventory was complete at `ec9ec7f` and still is, with one addition: the
place-name layer now also draws `bakke` and `mo`. If a layer is added later, it
has to be asked the question above.

**And ask the same question of the specification, one level up:** *which phase
receives this?* That is the inverted form, and it has found two things the
inventory question could not, because neither was ever on the map — the page
encoding, which was specified over thirty lines and belonged to no phase and is
now 3B, and the popup ascent, which fell between phases 2, 3 and 4. Run it
whenever the decisions document grows.

## Known open, and never asked

Separate from the decisions taken *against* something below. These are simply
unresolved, and a reader should be able to tell the two apart.

All of what stood here has since been settled, and is recorded where it belongs:

- The six build-time GPX files are built from chains from phase 3, and carry
  `<ele>` from phase 5.
- A plan is persisted as its GPX and nowhere else, with waypoints stored as
  **coordinates, never ids**, so a rebuild of the graph cannot orphan it. Loading
  one back is phase 8, with a choice on load between taking the track as it is,
  routing afresh between its waypoints, and matching it onto the network where a
  path exists.
- What happens when the sources change under a plan therefore answers itself:
  it is re-matched against the network as it now stands, and the difference is
  visible rather than silent.
- Snapping a waypoint to a hut or a quay, and splitting a route into days, are
  both after phase 8. Neither is blocked by anything earlier.

That has since been checked and answered: the zone holds 26 nature reserves and
one landscape protection area. None of the reserves touches the park, one —
Strauman — borders it. Phase 6 therefore reports protected areas rather than the
park alone, and `naturbase.Source` needs a spatial query to find them.

One thing is open, and it is open by decision rather than by oversight:

**FKB's provenance cannot be queried, and FKB carries 90 % of the network's path
evidence.** Its WFS exposes `objtype`, `typeveg`, `vegkategori`, `vegfase`,
`vegnummer` and `kommunenummer` — nothing about how a line was captured or when.
N50, which does expose it, shows 47 % of its paths digitised from a map rather
than surveyed, with capture dates back to 1965 and accuracies to 50 m; and the
two are not independent, both being Kartverket. So "is there a path here" is
unanswerable, and phase 1B builds only the negative form of it. The Geonorge file
download would carry FKB's own `målemetode` and settle it — it needs an account
and a second loading path, which is why the module uses the WFS. That trade is
the open question, and nothing downstream is blocked on it.

One more, small and dated: the `Ukjent` fix showed that a register's word for
*nothing* is worth hunting for deliberately. Turrutebasen's is now excluded.
**No other source has been searched for its own placeholder**, and the same shape
of bug has now appeared three times — `pd.NA` as the text `<NA>`, an empty string
counted by `notna`, and "unknown" read as a name. A sweep of every carried column
for values that mean absence would be an hour's work and is nobody's phase.

Otherwise nothing is known to be open. **That has now been true four times and
was wrong all four** — the phase readiness checks found gaps in 1B, in 3, in 2
and in 3B, the last of which this document had written itself, and the 3B review
then found the payload gap above. The check that finds them is not reading the
phase; it is measuring it against the built graph. Phases 4, 5, 6, 7 and 8 have
not had it.

## What phase 2 found

**The documented 996 m does not reproduce, and the threshold is not why.** All
three digitisations of Sjøbergmarsjruta read near 1,190 m. Before saying so, the
*unthresholded* figure was measured on the same route sampled the same way: it
is 1,370 m against the decisions document's 1,214 m. The filter removes 200 m
here and 218 m there, so the two ascent rules behave alike; the series underneath
differs by some 160 m. Three other readings of "ignore gains under 5 m" were
tried and none lands on 996 m either, and two of them are not invariant, which
the document's own table requires of whatever produced it. The original
measurement scripts are gone, so what was sampled cannot be recovered. **A
predicted figure that cannot be reproduced is worth taking apart into the part
that does and the part that does not** — here the invariance reproduces exactly
and the level does not, and only the invariance was ever the point.

**The route resolves under two names.** UT.no publishes *Sjøbergmarsjruta* and
Turrutebasen *Sjøbergmarsjen*, which reaches FKB through the route-name join. The
first implementation of the check searched for the full name, found one
digitisation of three and printed a table that looked complete. The three chain
ids in the phase document are right; the name in it is one of two.

**A cache key covering only the inputs is half a key.** The elevation parameters
went into the fingerprint, so phase 1's graphs rebuilt — but when descent and the
high and low point were added afterwards, nothing about the *inputs* changed and
a cached graph without those columns was served to code that reads them. The
fingerprint now also carries a `GRAPH_LAYOUT` marker, bumped when a build starts
producing something a cached one does not carry. Worth remembering as a shape:
the digest of what went in cannot notice a change in what comes out.

**−43.9 m is real ground.** The lowest reading in the network is an N50 road
descending into a quarry — `datakilde: "dtm1"`, `terreng: "Steinbrudd"` — not an
unchecked depth contour. 580 of 1.4 million samples are below sea level, on 28
edges, and nothing is anywhere near −276 m. So the coastal check needs a second
question after "is it negative": *what does the endpoint say it read it from*.

**A chain's series is laid out of its edges', not sampled again.** Sampling the
chains separately would have doubled the requests for the same numbers, because
every edge already samples both its ends. Two independent constructions agree to
5 m over a 20 km route, which is what says the walk and the orientation are
right; the check is worth repeating if either is touched.

## What 3B found

**4.11 MB against an estimate of 3.6, and the estimate was mine.** The three
lines this document had budgeted all reproduce — the node columns at 0.26
against 0.27, the heights at 1.02 against 0.98, the sources at nothing. What was
missing had never been listed: the chain ids at 0.13, and `sampleCounts` at 0.12
and `vertexCounts` at 0.10, without which a concatenated stream cannot be cut
back into edges at all. The geometry came in at 2.46 against 2.35.

**That is the third time this payload was under-budgeted, and all three were the
same mistake.** The edge table was forgotten, then the elevations were scaled
instead of measured, and now the stream's own structure was left out. Not one of
them was a figure sized wrongly; every one was a section that was never on the
list. **Ask what else has to be in the file for the thing you budgeted to be
readable** — a length, a count, an id — because that is what does not occur to
anybody, and here it came to half a megabyte.

**Chain order beat `from_node` order, measured both ways.** Sorted by
`from_node` the node columns are 0.232 MB and this document's 0.27 reproduces —
but the edges of one chain are then scattered, so the link from a chain to its
edges costs an index and a sequence per edge, 0.453 MB. Laid out in chain order
each chain is one contiguous run: the link is one count per chain, 0.009 MB, and
the node columns cost 0.263 rather than 0.232 because consecutive edges still
share a node. 0.272 against 0.685. **The cheapest arrangement of a column is not
the cheapest arrangement of the file.**

**The ordering, measured rather than argued.** Every one of the 11,290 chains
comes back as a single run — 11,200 walk straight through, 41 are rings and 49
touch a node twice, and the walk gets through all of them in one pass. 9 edges
run against their chain. Composed from the payload, all **214,384** joins close
to **0.0000 m**, in Python and again in the page. So the run-break flag, which
exists so that two stretches are never laid end to end across a gap, is never
set here except at a chain's own beginning. It is tested against fixtures, not
against this map, and a reviewer who goes looking for it will find it dormant.

**Two findings in review, both about a figure or a name being read twice.**

- `order.py` said **91 edges run against their chain**; it is **9**, which
  `encoding.py` said correctly two files away. The 91 was a different quantity
  that had drifted onto the wrong sentence — 90 chains reach a node twice. And
  the walk's own docstring, inherited from phase 2, counted the 41 rings inside
  its "straight through" total and then added them again, which left 8 chains
  where there are 49. **Two files disagreeing about one measured number is the
  cheapest possible signal that neither was re-run.**
- `_source_table` keyed the byte code by source **name** while the table row is
  keyed by name *and* kind. Every source here carries exactly one kind, which is
  measured, so nothing was wrong — but a source that ever carried two would send
  every one of its edges to whichever row came last, and a path read as a
  crossing costs a route 5 km. `edge_costs` prices by name alone and assumes the
  same thing. It now raises, which is what the module does at every other such
  ambiguity.

**What the payload did not carry — added straight after, in three commits.**
`waymarked` and `no_path_recorded` are what a route sums to say how much of
itself is marked and how much runs where nothing is recorded. The phase named
five edge fields and these were not among them, so 3B correctly reported them
rather than adding them.

Adding them cost **no recomputation at all**, which is worth knowing before the
next one of these: both columns were already on the edges in the cached graph,
and the fingerprint covers what goes *into* a build, while the encoding happens
after it. What did need a `GRAPH_LAYOUT` bump was the popup, because that needs
the figures summed **per chain** and the chains carried nothing. Two minutes
offline, no request to any endpoint — the height store is separate and even a
`--rebuild` reads it.

Measured after: payload **4.11 → 4.12 MB**, the byte costing 0.234 raw and
0.009 gzipped. Every graph figure unchanged, every browser figure unchanged,
both checksums still matching, no page errors.

**And the part worth remembering.** The same two fields cost **1.57 MB in the
popups** — 29.6 to 31.1 MB — against 0.009 in the payload. **Popup text is
written out per feature and compresses against nothing, so showing a figure can
cost 175 times what carrying it does.** Neither budget is threatened; the ratio
is the surprise, and it is the right way round only because the payload is
encoded and the popup is not.

Three things decided while doing it, each of which could have gone the lazy way:

- **Marking is three-valued, so the popup gives kilometres per class** rather
  than a verdict. 467 chains are marked along part of their run and not the
  rest, and 3,711 km of 5,853 are honestly *not stated* — FKB says nothing about
  marking and is 90 % of the path evidence. A line labelled "marked" that is
  marked for a third of its length is worse than no answer.
- **Never asked is not nothing stated.** A crossing was never asked; an edge
  that came back `unknown` was asked and no source answered. The payload's first
  code is `null`, not `unknown`, and an unrecognised state raises rather than
  falling into code 0. That is the *fourth* appearance of this shape.
- **The label had to be new.** N50's `rutemerking` and Turrutebasen's `marking`
  already sit in those popups and are what one register says about its own
  lines. This is what any source says about the ground, so it reads *Marking,
  all sources*.

## What 1C found

The upgrade moved 102 packages and crossed three major versions — **pandas 2.3.2
→ 3.0.5**, mypy 1 → 2, pytest 8 → 9 — alongside numpy 2.3.3 → 2.5.2, shapely
2.1.1 → 2.1.2, geopandas 1.1.1 → 1.1.4 and pyarrow 21 → 25.

**Not one figure moved.** Chains, edges, nodes, vertices, components, reach,
quays, Mosjøen, and both phase 1B coverage figures came out identical, and so did
the graph underneath them: same geometry hash over all 234,358 edges, same
`chain_id` hash, same total length to six decimals (6,048,994.047071 m) and same
total cost (6,820,867.05014). Checked by rebuilding, not by re-reading a cache —
see the trap below.

**folium did not move at all**, 0.20.0 either side, so no trap in the list above
needed revisiting. The generated map is byte-identical once folium's per-build
random element ids are normalised away, and all five browser checks came out the
same: the boundary is still the one non-interactive path of 12,357 and a click
inside the park still reaches a line and opens its popup; the wheel over the
search box still zooms while `+` still types; the box still sits above the zoom
buttons; 198 markers in `.leaflet-marker-pane` and, as ever, zero under
`.leaflet-marker-icon`; and typing still applies differences rather than
rebuilding — `map.addLayer` stays flat across every keystroke and moves once,
after the debounce.

Three things did change, all of them the upgrade's doing and all confirmed
against a pre-upgrade `hooks-run` that was green:

- **The cache fingerprint changed without the graph changing.** pandas 3 stopped
  stringifying missing values in `Series.astype(str)`, which is how
  `_values_digest` builds its digest, so the key moved from `0013142f7bc05b97`
  to `82f3dc694c9a3831` and every cached graph rebuilds once. Content unchanged.
  Proven rather than inferred: restoring pandas 2's handling in that one function
  and nothing else re-derives the old key exactly. Five of the seven sources
  differ — the two that do not, UT.no and Ferries, are the two carrying no
  missing value in an identity or attribute column. The stored pickle also grew
  from 48.6 MB to 59.4 MB for the same 234,358 edges.

  **That diagnosis stopped one step short, and the step matters.** `str.cat`
  drops a missing value rather than writing a placeholder for it, so the digest
  had become blind to *whether a value is there at all*: three different frames
  of the same row count hashed identically. That is a false cache *hit*, not the
  harmless miss it looked like — and it half-defeats the reason the digest was
  added, which is that a name arriving from SSR changes neither the row count
  nor the length of the source it lands in. Fixed with `na_rep` on the same
  call; the graph rebuilds identical. Severity was low because the row count and
  the total length are in the key too, which narrows any collision.

  Worth generalising: a library that stops writing a placeholder for nothing is
  a *silent* change to anything that hashes or concatenates. It does not raise
  and it does not usually alter a figure — it alters what two different inputs
  look like to each other.

  **This left a real defect behind, found by the review and deliberately not
  fixed here.** `_values_digest` is now weaker than it was: dropping the missing
  values loses their positions, so `['A', NA]` and `[NA, 'A']` digest alike.
  Move an identity value between two rows of a source — row count, total length
  and geometry all unchanged — and the fingerprint does not notice, so `make
  graph` replays a cached graph built from different identities, which is
  precisely what `_values_digest` was added in the phase 1 review to prevent.
  The fix is a `na_rep` on the `.str.cat()` at `route_graph.py:415`, or hashing
  the raw values instead of a concatenation. It is left undone because it moves
  the cache key a third time in a phase whose whole value is that a moved figure
  has one cause; it should go in before anything else relies on that guard.
- **Four tests pinned pandas' defaults rather than this project's behaviour** —
  `[object]` for a text column and `datetime64[ns]` — both of which pandas 3
  changed, to `str` and `datetime64[us]`. They now read the dtype off the series
  they built, so they hold either side of the change. A fifth assertion in the
  same file had gone *vacuous* rather than red: `"b [object]:" not in result`
  passes for a reason that no longer has anything to do with what it was testing.
- **mypy could no longer target 3.11.** numpy 2.5 dropped 3.11 and writes its
  stubs with PEP 695 `type` statements, which mypy refuses to parse when told to
  target 3.11 — fatally, before any per-module override can apply. The setting is
  now 3.12, the lowest that parses. Two further errors surfaced from the new
  pandas and numpy stubs and are silenced at the two call sites with the reason
  named; neither is a runtime change, and `warn_unused_ignores` will flag them
  when the stubs catch up.

**The trap this phase nearly fell into**, worth keeping: `make graph` reads the
cached graph back, and the fingerprint covers the sources and the parameters but
not the library versions. Had the fingerprint *not* moved, a plain run after the
upgrade would have replayed the cache and reported every number unchanged without
executing a line of shapely. Rebuild with `--rebuild` and check that the run says
"Building chains per source", or the comparison proves nothing.

## After 1C and 1D — done, and what it turned up

All of what stood here has happened. Kept, because two of the findings were not
what they first looked like.

**`uv.lock` is tracked**, and `.gitignore` no longer hides it. It had been
ignored since the first commit under a `# uv` heading beside `.venv/`, which
reads as a template default rather than a decision. The version committed is the
one 1C verified, so the first tracked state is a checked one.

**shapely and branca were imported but never declared.** shapely appears in
thirteen modules — the whole of `routing/`, the exports, the geometry helpers and
the pipeline's transform step — and worked only because geopandas pulls it in;
branca carries the two `MacroElement`s the click-highlight and the search are
built on. Neither was found by looking for missing dependencies. Both turned up
while listing what the bounds ought to say. **A dependency that arrives
transitively looks exactly like a declared one, right up to the day it stops
arriving.**

**Raising the bounds forced the Python floor**, which is how 1D stopped being a
tidiness exercise and became unavoidable: `uv lock` refuses `numpy>=2.5.2`
against `requires-python = ">=3.11"`, because numpy 2.5 does not support it. The
floor is now 3.14 and all four version statements agree. The phase records what
that cost.

**And the `>=3.11` claim had been charging for itself invisibly.** The lockfile
carried two resolutions — numpy 2.4.6 below 3.12, 2.5.2 above — and only one was
ever run or tested. Moving to 3.14 collapsed them into one and removed a package
outright. A supported version nobody exercises is not free; it is a second build
that fails only for somebody else.

## Decisions taken not to do things

So they are not quietly reopened:

- No GraphHopper, and no server — the second asked separately from the first.
  Nothing measured requires one; the triggers that would are a second area, or
  turn restrictions and alternatives. Elevation used to be on that list and no
  longer is, since phase 2 provides it.
- No priority merge of the source geometries. Measured, it halves the reach.
- Elevation-aware routing is possible once phase 2 lands, but is a separate
  decision about the weights.
- No per-source switches on the build. `--no-osm`, `--no-n50`, `--no-fkb`,
  `--no-roads`, `--no-ut`, `--no-names` and `--fkb-km` are removed in phase 3.
  The layer control does the visual job better, and a graph missing a source is
  not smaller but wrong — quietly, and in a way that disagrees with every figure
  in the specification. A source that cannot load is an error.
- No `<copyright>` in the exported GPX, because a route mixing CC0, CC BY 4.0,
  ODbL and CC BY-NC has no single licence to name. The sources are listed
  instead.
- No timestamps on trackpoints, no speeds, no durations. A track carrying times
  reads as a recorded activity rather than a plan, and the rest would be guesses
  dressed as data.
- No reduced GPX variant: the target platforms cannot rebuild these paths from
  sparse points, and no point limit is known that would justify one.
- No offline elevation. The map's tiles are already online-only.
- **Not the strictest reading of the ascent threshold**, where any fall at all
  ends the climbing run. It is what produced the documented 996 m and it was
  recovered in review — 999.7 m on the same series the build uses — so the old
  figure was a defensible reading rather than a mistake. It is still the worse
  one: across three digitisations of the same slope it spreads 245 m, where the
  built rule holds them within 20. **The cross-source spread is the test of an
  ascent rule.** Invariance across sampling steps is necessary and not
  sufficient; the strict reading passes that and still measures the noise of a
  particular drawing rather than the hill.
- **`Ukjent` is no longer read as an identity**, and the reference moved with it:
  11,290 chains, FKB 6,201, Turrutebasen 244, 234,358 edges. Everything that
  matters held — 757 and 747 components, 79 % and 91 %, reach 50.8 km = 94 %,
  6 → 17 quays, Mosjøen 2.17 m, and both coverage figures to the decimal. The
  edge count fell by five through three fewer bridged loose ends, which is a
  knock-on of the split rather than a separate effect. This was the third time
  the same shape of bug appeared: a placeholder for *nothing* read as a value —
  `pd.NA` as the text `<NA>`, an empty string counted by `notna`, and now a
  register writing "unknown" into a name column. **Ask what a source writes when
  it has nothing to say, before trusting a column.**
- **No renaming of the `OSM` source to `OSM paths`.** It carries only paths, so
  the name is imprecise and the `N50 paths` / `N50 roads` split next to it makes
  that visible. But the source name is the **prefix of every chain id**, which
  keys the elevation cache, the highlight and the search — renaming moves all
  1,505 of them. The N50 split exists because N50 genuinely supplies both and
  both are loaded; within OSM there is nothing to disambiguate, and the layer is
  already labelled *Paths in park [OSM]*. The confusion this came from was a
  documentation one, in the cost table, and that is where it is fixed. If OSM
  roads are ever loaded, split then — that is the moment, exactly as it was for
  N50. Note the window: today a rename is free because nothing persists a chain
  id; from phase 2 it keys a cache and from phase 5 it is written into exported
  files.
- **No licence notice in the interface.** An earlier draft of the decisions
  document asked for one. Nothing here is published, and the obligations attach
  to distribution rather than use — and the mitigation is already in the right
  place, since the exported GPX is the only thing that leaves the machine and it
  carries its sources and their licences. Revisit only if the map is hosted or
  routes from it are published; ODbL's share-alike is the one with teeth.
- **No positive `on_path`.** Asked directly, measured, and refused: the sources
  over-record. FKB knows only `sti` and `traktorveg`, both asserting a physical
  feature, and calls 90 % of UT.no a path — while disclosing nothing about how
  any line was captured. N50, which does disclose, is 47 % digitised off older
  maps here, back to 1965, at accuracies to 50 m; and the two are not independent
  witnesses, both being Kartverket. Only the negative form survives, and only
  because a liberal recorder's silence means something. Two corrections to
  earlier reasoning are folded into the decisions document: FKB and N50 are not
  independent, and for paths it is **absence** that is evidence, not presence.
- **No survey-quality summary in the exported GPX.** Right in a popup, where the
  question is one line and the answer is concrete; useless in a file, where FKB's
  90 % would make it read *30 km not disclosed*.
- **No Geonorge file download for FKB.** It carries FKB's own `målemetode` and is
  the only thing that would settle the question above. It needs an account and a
  second loading path, which is exactly why the module uses the WFS. Open by
  decision, and nothing is blocked on it.
- **No park in the names of the Makefile targets.** `make map` and `make graph`
  exist, and both scripts hard-code `PARK_NAME`. Naming the targets for the park
  would be noise on every invocation while there is only one; the park is in
  `make help` instead, which is where someone looks. If a second is added, the
  scripts grow a `--park` option first and the targets follow it.

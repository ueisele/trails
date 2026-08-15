# Route planning: notes for reviewing the phases

Working notes, not specification. The specification is
`route-planning-decisions.md` and `route-planning-phases.md`. This holds what a
reviewer needs that those two deliberately leave out: how the numbers in them
were arrived at, what this codebase does that will bite an implementation, and
what to look at in each phase.

## Where things stand

**Phases 1, 1B, 1C and 1D are built and reviewed.** `libs/src/trails/routing/`
and `analysis/scripts/route_graph.py`. Their output is now the reference in the
decisions document; phases 2–8 remain. The project runs on **Python 3.14**, and
`uv.lock` is tracked from 1D onwards.

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
  234,363 edges down to 166,900 and two minutes down to one. What it cost was
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

### What is uncommitted

Everything since `7c9666d`, in three natural groups:

1. **Phase 1** — `libs/src/trails/routing/`, `libs/tests/trails/routing/`,
   `analysis/scripts/route_graph.py`, plus both READMEs. Untracked, so the
   agent's work and the review's corrections to it cannot be separated into two
   commits; they are the same never-versioned files.
2. **The map** — `analysis/scripts/lomsdal_visten.py`. The line above that said
   it was untouched is no longer true. See below.
3. **The documents** — all three.

### What changed in the map

Popups were audited against what each layer's data actually holds:

- **OSM was the only line layer with no length.** `clip_to` had been computing
  `length_km` for it all along; `OSM_POPUP_FIELDS` simply omitted the entry.
- **No layer showed provenance**, though every Kartverket line layer carries it.
  A new `describe_survey()` adds `survey_method` and `surveyed` to N50's paths,
  ferries and roads — translating `fot`/`dig`/`sat` through
  `SURVEY_METHOD_LABELS` — and to Turrutebasen, which writes its method out in
  words already. Turrutebasen also gained `origin`, `trail_significance` and
  `special_hiking_trail_type`; the last needed adding to
  `aggregate_trail_info`, which had been discarding it.
- **FKB was left alone.** Its extra fields look 100 % populated and are not:
  `notna()` counts empty strings. Really 3–6 %.

The map has been rebuilt and the new fields verified in the HTML. Its warm-cache
runtime is **53 seconds**, not the "half an hour" quoted twice in conversation —
that figure came from a timeout allowance rather than a measurement. Worth
remembering as a habit: a number nobody measured is worth nothing even when it
is only used to decide whether to bother.

The measurement scripts that produced the figures lived in a session scratchpad
and are gone. Their methods are below so a figure can be re-derived rather than
taken on trust.

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
`identity_field` decides them. 11,292 chains, 234,363 edges, 757 and 747
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

**Phase 2, elevation.** The invariance is the test: the same route's ascent at
5, 10 and 15 m sampling. Then check the cache actually holds — a second run must
issue no requests. Then check a coastal path: any profile touching −276 m means
`datakilde` is not being checked.

**Phase 3, drawn from the graph.** Nothing new should work; everything old should
still work. Object count down, layers still toggle independently, UT.no off still
leaves the network, overlapping sources still select separately. This is the
phase where a regression hides.

**Phase 4, the profile.** Check it is hand-drawn SVG and nothing is fetched from
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

That inventory is complete as of `ec9ec7f`. If a layer is added to the map later,
it has to be asked the question above.

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

Otherwise nothing is known to be open. That has been true twice
before and was wrong both times — see the question above, and ask it again.

## What 1C found

The upgrade moved 102 packages and crossed three major versions — **pandas 2.3.2
→ 3.0.5**, mypy 1 → 2, pytest 8 → 9 — alongside numpy 2.3.3 → 2.5.2, shapely
2.1.1 → 2.1.2, geopandas 1.1.1 → 1.1.4 and pyarrow 21 → 25.

**Not one figure moved.** Chains, edges, nodes, vertices, components, reach,
quays, Mosjøen, and both phase 1B coverage figures came out identical, and so did
the graph underneath them: same geometry hash over all 234,363 edges, same
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
  from 48.6 MB to 59.4 MB for the same 234,363 edges.

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

# Route planning: notes for reviewing the phases

Working notes, not specification. The specification is
`route-planning-decisions.md` and `route-planning-phases.md`. This holds what a
reviewer needs that those two deliberately leave out: how the numbers in them
were arrived at, what this codebase does that will bite an implementation, and
what to look at in each phase.

## Where things stand

**Phase 1 is being implemented by another agent, in this same working tree.**
`libs/src/trails/routing/`, `libs/tests/trails/routing/` and
`analysis/scripts/route_graph.py` are its work in progress.

While that is true, the standing instruction is: **documents only. Do not change
code and do not run tests.** That includes `command make hooks-run`, which runs
`pre-commit --all-files` over the agent's files, and `git commit`, whose hook
stashes unstaged changes and would pull work out from under it. Check
`git status` before assuming this has ended.

The three route-planning documents are uncommitted: `decisions` and `phases` are
modified since `ec9ec7f`, these notes are untracked. Everything in them past that
commit came out of a long series of questions from the maintainer, and belongs in
a commit of its own, separate from the agent's code.

The map itself — `analysis/scripts/lomsdal_visten.py` — is untouched by any of
this.

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

**Phase 1B, what the graph carries.** Three things, each cheap to miss: is
Turrutebasen in the graph at all; do edges carry the attributes phase 6 will
report on, above all whether a stretch is waymarked; does the cache key cover the
extent and the source set, so a 5 km graph cannot answer for a 15 km one. And
that a missing source is an error rather than a smaller graph.

**Phase 1C, the dependency refresh.** Run phase 1's statistics before and after
and compare. Any movement in edges, components or reach is the upgrade's doing
and nothing else's — that is the whole reason it sits here rather than later.
Then drive the map in a browser: clicks reaching lines, the wheel reaching the
map, markers rendering at all. The trap list above was written against folium
0.17; if the upgrade moves past it, the list needs revisiting.

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

One thing is knowingly unchecked: **Naturbase holds protected areas besides
national parks** — reserves, landscape protection areas — and whether any lie
inside this zone has never been looked at. The map draws only the park, and the
park share reported for a route counts only the park. If others are there, the
honest figure is closer to "crosses three protected areas" than to one number.

Beyond that, nothing is currently known to be open. That has been true twice
before and was wrong both times — see the question above, and ask it again.

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

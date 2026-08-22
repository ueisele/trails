# Route planning: what has been decided, and why

Build a plan mode into the generated map: click to set waypoints, get a route
over the drawn network between them, see the distance as you go, reorder the
points, export the result as GPX.

Everything under "What is already decided" is settled by measurement — do not
re-derive it, it took about forty minutes of compute. The work itself is cut into
phases in `route-planning-phases.md`; this document is what those phases refer
back to.

## What the map is today

`analysis/scripts/lomsdal_visten.py` builds `analysis/output/lomsdal-visten.html`
(~25 MB) from seven sources. Run it with:

```
uv run python analysis/scripts/lomsdal_visten.py
```

The library it uses lives in `libs/src/trails/`:

- `visualization/maps.py` — every Folium layer helper, plus two behaviours
  already implemented as `branca` `MacroElement`s: `_ClickHighlight` (click a
  line, it lifts out of the bundle) and `_NameSearch` (type a name, everything
  else hides). Read both before writing a third: they establish the pattern.
- `io/export/gpx.py` — `export_to_gpx`, used for the existing exports
- `utils/geo.py` — `merge_lines`, `thin_points`, `attach_nearest`
- `io/sources/` — one module per dataset, all reading from `.cache/`

## What is being asked for

1. A plan mode that can be switched on and off.
2. Clicking the map adds a waypoint, snapped to the path network.
3. Between consecutive waypoints, a route is found over the network.
4. The total distance is visible and updates continuously.
5. Waypoints can be reordered and removed; the route follows.
6. An accurate elevation profile, displayed and carried into the export.
7. The finished route downloads as GPX, importable into Komoot or
   Outdooractive.

## What is already decided

### The graph is the plain union of every source, not a merged one

The obvious idea — merge the sources by priority so each path exists once — was
measured and is **wrong for connectivity**. Cutting the lower-priority line away
where a better one exists removes redundancy that was holding the network
together: where FKB has a gap, the parallel N50 strand used to carry across it.

Measured over park + 5 km, against 53.9 km of park from north to south:

| network | components | largest | spans the park |
|---|---:|---:|---:|
| plain union, 25 m bridging | 230 | 1312 km = 67 % | **50.8 km = 94 %** |
| plain union, 45 m bridging | 188 | 1318 km = 67 % | 50.8 km = 94 % |
| priority merge 20 m, 45 m bridging | 216 | 579 km = 47 % | 25.9 km = 48 % |
| priority merge 25 m, 60 m bridging | 177 | 586 km = 48 % | 26.6 km = 49 % |

The priority merge halves the reach. Use the plain union.

Note which number matters: the *share of length* in the largest component is a
misleading 67 %, dragged down by hundreds of isolated FKB stubs recorded out in
the terrain. What decides whether a traverse can be planned is **reach** — how
far the main component spans — and that is 94 %.

### Roads belong in the graph

Without them the network collapses: the largest component drops from 59 % of
length to 5 %. Valleys connect to each other only over roads. Use
`n50.Source.load_roads` — the same data the map already draws.

### Source priority becomes an edge weight, not geometry surgery

Priority is still wanted, for a different question: which of several parallel
lines the route should follow. A route through a valley described by UT.no, FKB
and N50 alike should run on the UT.no track, not on a strand 8 m beside it.

Give each edge a cost of `length × factor`:

| source | factor | what it actually holds, measured |
|---|---:|---|
| UT.no | 1.00 | described trips |
| Turrutebasen | 1.02 | waymarked routes |
| FKB | 1.05 | `sti`, `traktorveg` |
| N50 paths | 1.10 | `sti`, `traktorveg`, `gangOgSykkelveg` |
| OSM | 1.20 | `path`, `track`, `footway`, `steps` — **no roads** |
| N50 roads | 1.30 | `enkelBilveg` — **cars only** |

**The scale means two different things and the break is between 1.20 and 1.30.**
From 1.00 to 1.20 every source holds the same kind of thing — a path — and the
factor ranks how well it was surveyed, which is the question above: where three
datasets draw one valley, follow the best-surveyed strand rather than the one
8 m beside it.

**1.30 is not a statement about N50.** N50's road geometry is perfectly good.
It is a preference about *ground*: a route should take three kilometres of path
over 2.4 km of tarmac, and 1.30 is what buys that. Read as a quality ranking it
invites exactly the wrong correction — "N50's roads are well surveyed, so why are
they last?" — and correcting it would silently change how every route behaves.

The right-hand column is there for the same reason. OSM is loaded through
`HIKING_HIGHWAY_TYPES` and carries no `residential`, `unclassified` or `service`
at all; without saying so, `OSM 1.20` sitting above `N50 roads 1.30` reads as
though the two were comparable. They are not: one is 691 km of footpath, the
other 1,514 km of road.

Dijkstra then prefers the better source wherever the detour is small, and no
path is ever lost. Tune the factors if routes take odd turns; keep them close to
1.0 or the route will make real detours to reach a preferred source. **The 1.30
in particular is an assertion nobody has yet seen on a route** — check it when
phase 6 draws the first real ones, because a factor that justifies a 30 % detour
is worth seeing before it is believed.

### Ferries are routable, but they are not walking

Include them. Without them the west of the park cannot be reached at all, which
is where the UT.no routes start. Measured over the 15 km zone:

| | components | largest | named quays reached |
|---|---:|---:|---:|
| land only | 759 | 4,348 km = 79 % | **6 of 17** |
| with ferries | 750 | 5,135 km = **91 %** | **17 of 17** |

Phase 1, built, reproduces this: 757 and 747 components, 79 % and 91 %, 6 quays
and then all 17.

Eleven quays — Bønå, Visthus, Forvik, Tjøtta, Horn, Stokkasjøen among them — hang
off the network entirely until the crossings are in it. Use
`n50.Source.load_ferries`, which the map already draws.

They are a different kind of edge and must stay one:

- **Cost is not length.** A crossing takes the same decision whether it is 2 km
  or 20, so weighting it by distance is meaningless. Give it a flat cost — the
  equivalent of a few kilometres of walking — so a route takes a ferry where it
  genuinely shortens the journey and does not cross a fjord to save two hundred
  metres.
- **Never add it to the walking distance.** Report it apart: *42 km on foot · 2
  crossings, 31 km*. The same separation the straight legs get.
- **No elevation, and do not sample any.** The endpoint answers over water with
  depths from `dybdekurver`; a ferry edge would come back at −276 m. Skip them
  in the sampling entirely rather than filtering afterwards.
- **In the GPX, a crossing ends a `<trkseg>`** and the next walking stretch
  begins a new one. A track drawn straight over open water reads as though it was
  swum; a break reads as what it is, and both Komoot and Outdooractive handle
  multiple segments.
- Drawn dashed, as they are today.

### Legs with no connection are drawn straight — and some of them cross water

21 % of the network is genuinely unreachable from the main component, and
Lomsdal-Visten is a roadless, largely pathless park where walking cross-country
is normal. When no route exists between two waypoints, draw the leg as a dashed
straight line, count its length separately, and label it so the reader knows it
is not a path. Do not fail, and do not pretend.

Some of those legs are **over water**. Reaching Austerfjorden means a boat
transfer that is nobody's scheduled ferry — UT.no's own descriptions say as
much — so a reader will draw a line across a fjord, and that line is not walking
either. It has to leave a gap, exactly as a ferry does.

**The elevation endpoint classifies it.** Every point comes back with a `terreng`
field: `"Skog"` over ground, `"Havflate"` over sea. The same check that keeps
−276 m out of a profile also tells a leg what it is. No extra dataset, no
question to the reader, and a leg that crosses a strait sorts itself out — its
samples alternate, so it splits at the shoreline into walked stretches and
crossed ones.

That leaves four kinds of leg, and only two ways of reporting them:

| leg | distance counts as | profile | in the GPX |
|---|---|---|---|
| routed over the network | on foot | yes | one segment |
| free, over land | on foot | yes, sampled on demand | one segment |
| free, over water | **crossing** | none | ends the segment |
| a ferry crossing | **crossing** | none | ends the segment |

Report the two groups apart — *42 km on foot · 3 crossings, 34 km* — and never
let a crossing into an ascent figure.

### Extent: the full 15 km approach zone

Required, not a preference: **Mosjoen has to be inside the graph**, and it lies
9.8 km from the park boundary. The extent therefore matches the one the map
already draws, `--approach-km 15`.

Measured over that zone, plain union with 25 m bridging:

| | measured before phase 1 | **phase 1, built** |
|---|---:|---:|
| input | 23,041 lines, 5,523 km | 23,876 lines, 6,001 km |
| graph | 129,616 edges, 72,113 nodes | **234,358 edges, 116,967 nodes** |
| vertices | 683,226 | **948,465** |
| chains | about 10,500 | **11,290** |
| components, land only | 759 | **757** |
| largest component | 4,350 km = 79 % | **4,637 km = 79 %** |
| its reach across the park | 50.8 km = 94 % | **50.8 km = 94 %** of 53.9 km |
| its distance to Mosjoen | 0.00 km | **2.17 m** — the town sits on it |
| with ferries | 750 comps, 91 %, 17 quays | **747, 91 %, 17 of 17** |

Connectivity is better here than over the smaller extent (79 % against 67 %),
because the road network outside the park ties the valleys together.

Per source: FKB 1,979 km · N50 roads 1,514 km · N50 paths 1,057 km · OSM 691 km ·
UT.no 376 km · Turrutebasen 235 km · ferries 149 km.

**The left column was measured without Turrutebasen in the network**, which was
an oversight in the measuring rather than a decision. The right column is phase
1's own output and is the reference from here on. Two differences are worth
naming, because neither is a fault:

- **The edge count nearly doubles.** Turrutebasen contributes 25,965 edges of its
  own and, being a second digitisation of ground FKB already holds, some 10,000
  further crossings in FKB and N50. What did *not* move is the reach, exactly as
  predicted: 94 %, unchanged to the metre.
- **UT.no reads 376 km, not 282.** 282 km was the union of the 35 trips; 376 km is
  their sum, and the sum is what goes into the graph, because a published trip
  keeps its published unit and two trips sharing a stretch each keep it.

### Full source precision, at 1.8 MB — do not simplify to save space

Accuracy is a requirement: the tracks must not be thinned to make the page
loadable. Measured, they do not have to be.

The network carries **523,857 vertices** at the sources' own resolution
(FKB 312,641 · N50 paths 62,382 · UT.no 59,847 at raw GPS density · N50 roads
57,585 · OSM 31,402). Written as JSON coordinate arrays that is 22.4 MB, which is
where an earlier estimate in this document went wrong. Written properly it is
not:

> Phase 1, built, carries more: **541,062 vertices across the chains** and
> 948,465 across the edges, the difference being the vertex each cut duplicates.
> Scaling the encoded figures below by that gives 1.9 MB for what is drawn and
> 3.3 MB for the routing graph, and that is the reason phase 1 nodes the
> published sources at their own resolution rather than a simplified one.

#### There is no size allowance, and the one this document used to name was never measured

An earlier draft said the payload had **5 MB** to spend. That number appears once,
in a note that refers to it as already settled, and nowhere is it settled: nothing
was measured to arrive at it and nothing was measured against it. It was a round
number.

It did real work all the same, and the work is worth keeping while the number
goes. It is why the edge table is encoded rather than serialised, which was 1.7 MB;
it is why the coordinate quantum was weighed against what it costs in metres
rather than taken as free; and three times it forced a figure to be measured
where an estimate would have passed. **A ceiling nobody can justify is still
useful if it makes the right question unavoidable.** It is not useful as a fact.

Measured, on the built page — 37.4 MB, of which the payload is 4.93:

| | |
|---|---:|
| HTML parsed, to `DOMContentLoaded` | 1,195 ms |
| to `load` | 1,581 ms |
| the graph inflating, off the load | 229 ms |
| reading it into arrays | 50 ms |
| decoding base64: 5 MB / 10 MB / 20 MB | 7 / 18 / 34 ms |

So quadrupling the payload costs about thirty milliseconds of a page that takes
1.6 seconds to open. **The payload is not what makes this page large.** Of the
37.4 MB it is 4.93; the rest is popup HTML and the coordinate arrays Folium
writes for the drawn lines — and the two coverage rows added in phase 3B cost
**1.57 MB in the popups against 0.009 MB in the payload**, a factor of 175.

The rules that replace the number:

- **Encode and quantise, always.** Not to stay under anything: `<ele>` values and
  coordinates written as JSON are 22.4 MB where the same data delta-encoded is
  1.8, and that difference is real whatever the ceiling.
- **Anything added is measured and argued for on its own**, never against a
  remaining allowance. "It still fits" is not a reason.
- **The acceptance is the load time**, which is 1.6 s and can be re-read on every
  build. If a change moves it, that is the finding.
- **Look at the drawn side first.** That is where a megabyte is cheap to add by
  accident and where nothing is counting.

| encoding | in the file |
|---|---:|
| JSON arrays, 6 decimals | 22.4 MB |
| delta + varint at 1e-6 (0.11 m), gzip, base64 | **1.8 MB** |
| delta + varint at 1e-5 (1.11 m), gzip, base64 | 1.1 MB |

Use **1e-6**. Quantising to 0.11 m is an order of magnitude finer than the best
source in the set — FKB is surveyed to a metre or two, N50 is a 1:50,000 product,
UT.no's tracks are consumer GPS — so nothing measurable is lost, and 1.8 MB on a
25 MB page is not worth arguing about.

Encode with zigzag varints over the delta between consecutive points, one run per
edge, then gzip, then base64. The browser inflates with `DecompressionStream`.
Twelve times smaller than JSON, and lossless at the chosen precision.

Two consequences worth stating plainly:

- The **exported GPX carries full source precision**. It is not built from the
  simplified copies the map draws.
- The map's `--simplify-m 8` stays as it is. That is a rendering decision about
  12,500 background polylines and has nothing to do with the route: the planned
  route is drawn from the graph's own geometry.

Simplifying UT.no before noding, mentioned below, is about **edge count, not
accuracy** — raw GPS density shatters every line those tracks cross, tripling the
graph. Simplify what goes into the noding; keep the full geometry on the edge.

Dropping components under 1 km is still worth doing — 21 % of the length sits in
758 fragments nothing can route to — but as housekeeping, not to save space.

### Elevation: sampled for the whole network at build time, from DTM1

Every edge gets a real elevation series, sampled every 5 m, fetched once when the
graph is built. That makes ascent and a profile available for **every path on the
map**, not only for a planned route, and makes a planned route's profile appear
instantly.

Only **straight-line legs** are fetched on demand: they are drawn freely where no
path exists and cannot be known in advance. They are small — a 1 km leg is four
requests and about a third of a second, a 10 km one forty requests and two
seconds. Cache them by their two endpoints so dragging a waypoint back and forth
does not fetch the same ground twice.

This also degrades well. Without a network the map has no tiles and is unusable
anyway, but a route that stays on existing paths still shows its full profile
from what was baked in; only a freshly drawn free leg comes up empty, and it
should say so rather than report flat ground.

#### Use the point endpoint, not the raster

`https://ws.geonorge.no/hoydedata/v1/punkt` takes
`punkter=[[east,north],…]&koordsys=25833`, returns a `z` and the terrain type per
point, caps at **50 points per request**, and sends
`Access-Control-Allow-Origin: *` so a `file://` page may call it too.

**Two of its answers are not elevations, and both look like one.** Over water it
returns a depth from `dybdekurver` with `terreng: "Havflate"` and a negative `z` —
sampling a metre offshore on a coastal path yields −276 m, which would poison the
profile and the ascent without anything looking wrong. Outside its coverage it
returns `z: null` with `datakilde: null`. So check `datakilde` on every point,
treat anything that is not a terrain model as **no reading**, and carry the gap
through the profile as a gap rather than as ground. This is not hypothetical
here: the zone reaches the fjords and the network includes ferry crossings.

The WCS `https://wms.geonorge.no/skwms1/wcs.hoyde-dtm-nhm-25833`, coverage
`NHM_DTM_25833`, returns the *same data*: sampled at 1 m it agrees with the point
endpoint to a median of 0.00 m over 300 vertices, worst case 0.38 m. It is the
same national height model. But for points strung along lines it is far the more
expensive way to get at them:

| approach | requests | transferred | accuracy |
|---|---:|---:|---|
| **point endpoint, every 5 m** | 22,000 | **~110 MB** | exact DTM1 |
| WCS at 1 m, 1 km tiles covering the network | 1,948 | 7.8 GB | exact DTM1 |
| WCS at 2 m | 1,948 | 1.9 GB | 0.19 m median |

Seventy times the bytes for the same numbers. A raster is efficient when you need
an area; this needs a thread through one. (The network's bounding box is
6,195 km²; 1,948 of the 6,300 one-kilometre tiles in it contain a line.)

So: 5,523 km at one sample per 5 m is 1.1 million points, 22,000 requests, about
110 MB and roughly fifteen minutes at twelve requests in parallel. That is less
traffic than one of the eight N50 municipality downloads this project already
makes, and it happens once.

#### Caching it properly matters more than the fetch itself

Without a cache this runs on every build. The map was rebuilt about fifteen times
in one afternoon of work on it, which would have been 330,000 requests. That
would be an abuse of a public service, and it is the part of this worth designing
rather than improvising.

**Two layers, and the second is the important one.**

The **graph cache** is the obvious one: the finished graph, elevations included,
stored under `.cache/` and keyed on what went into it, so an unchanged rebuild
costs nothing. This is what `trails.io.cache.Object` already does for every
expensive step here.

The **point store** is what makes it robust. Keep a table of
`(east, north) -> elevation` in `.cache/`, in parquet as the project does
elsewhere, and consult it before asking the endpoint anything. Then a source
update does not start from zero: only the ground that actually moved is fetched
again.

That distinction matters because of how the sampling works. Sample points are
interpolated at a fixed 5 m step along each edge, so if one vertex of an edge
changes, every sample on that edge shifts and misses a coordinate-keyed cache.
That is tolerable only because edges are short — 6,049 km across 234,358 edges
is a 26 m average, about five samples each. A changed edge costs five lookups,
not a region.

Key on the coordinate rounded to a centimetre. Do **not** quantise to a coarser
grid to raise the hit rate: in steep ground half a metre sideways is half a metre
of elevation, and this whole section exists to avoid errors of that size.

1.1 million rows is roughly ten megabytes of parquet. It is the cheapest part of
the whole design.

Built, it is: **1,017,874 rows in 11.7 MB**, keyed on the coordinate in
centimetres as two integers with the height beside them, rewritten atomically and
flushed every minute during a run so an interrupted one resumes rather than
starting again. **A point with no height is still a row** — over water and
outside the coverage the endpoint answers with something that is not a height,
and a store holding only the successes would ask again about exactly the points
that can never answer, on every build, for as long as the network touches a
coast. 1,748 of the rows are of that kind.

The run itself came out at **20,183 requests in 13.6 minutes**, six in parallel,
24.4 requests a second — against the 20,358 and sixteen minutes predicted. Both
a plain second build and a forced `--rebuild` issue **no requests at all**.

Beyond that, treat it as any other expensive fetch here: retry on failure, send a
real User-Agent, and hold the concurrency at **six** parallel requests. Twelve
measured faster, but this is a bulk run of 22,000 against a public service and
restraint counts for more than speed: six puts the build at about seventeen
minutes, once. Use the same six for the on-demand legs rather than keeping two
numbers. Doing this once is fair use; doing it on every build is not.

#### Sample every 5 m, and report ascent with a 5 m threshold

These are two different decisions and they were measured separately, because
finer sampling improves one of them and actively harms the other.

**Spacing decides how faithful the curve is.** Measured on Sjøbergmarsjruta
against a dense reference of 8,191 real readings taken every 2.5 m — how much a
given spacing misses between its own samples:

| spacing | median | p90 | max | RMSE |
|---:|---:|---:|---:|---:|
| **5 m** | 0.00 m | 0.19 m | **1.14 m** | **0.12 m** |
| 10 m | 0.08 m | 0.34 m | 2.79 m | 0.22 m |
| 15 m | 0.13 m | 0.48 m | 2.62 m | 0.31 m |
| 25 m | 0.21 m | 0.76 m | 4.13 m | 0.48 m |
| 50 m | 0.40 m | 1.39 m | 7.38 m | 0.89 m |

5 m is roughly twice as faithful as 10 m and halves the worst step it misses —
2.79 m down to 1.14 m, the difference between a visible ledge and a smooth line.
Below 5 m the interpolation error falls under DTM1's own vertical uncertainty,
around half a metre under forest canopy, so there is nothing left to win.

One caveat on that table: at 5 m spacing every second reference point coincides
with a sample and contributes zero error, at 10 m only every fourth. The
advantage of 5 m is therefore somewhat overstated — nearer 1.5x than 2x. The
ordering is unaffected.

**Threshold decides whether the ascent figure means anything.** The same route,
sampled at several spacings, with gains below a threshold ignored:

| spacing | raw | 1 m | 3 m | **5 m** | 10 m |
|---:|---:|---:|---:|---:|---:|
| 5 m | 1214 m | 1128 m | 1048 m | **996 m** | 922 m |
| 10 m | 1146 m | 1097 m | 1033 m | **992 m** | 943 m |
| 15 m | 1112 m | 1077 m | 1017 m | **994 m** | 939 m |
| 25 m | 1074 m | 1057 m | 1010 m | 972 m | 946 m |
| 50 m | 1006 m | 998 m | 972 m | 951 m | 921 m |
| 100 m | 965 m | 964 m | 949 m | 939 m | 923 m |

Raw, the figure swings 26 % with the spacing — 1,214 m against 965 m for one
route. That is not measurement error, it is the coastline effect: sample finer
and more noise counts as climbing. With a 5 m threshold the same route reads
996 / 992 / 994 m across 5, 10 and 15 m spacing, half a percent apart. A figure
that no longer depends on how you measured it is the only kind worth showing.

Below 25 m spacing the numbers fall across *every* threshold, which is real
terrain being lost rather than noise removed.

Sampling at a fixed 5 m step, rather than at each source vertex, matters for the
same reason: vertex spacing varies wildly between sources — UT.no's tracks sit
4 m apart, N50 far coarser — so per-vertex sampling would make a path's ascent
depend on which dataset happened to draw it. Interpolate onto the vertices for
the GPX.

**"Every 5 m along an edge" means `⌊length / 5⌋ + 1` samples, at least two,
spread evenly between the two ends.** That is what reproduces the measured
1,406,040 samples exactly — laying them from one end instead misses the far end
of most edges and gives the same count over a different set of points. Spreading
them evenly is also what makes an edge's last sample the same coordinate as its
neighbour's first, which is where most of the 28 % duplication comes from and
what lets a chain's series be laid out of its edges' rather than sampled again.
The floor of two is not a detail: 97,974 edges are under 5 m and 28,373 under one
metre, so a floor of zero would leave a third of the network with no profile, no
ascent and no ends to join its neighbours at.

**The floor means the spacing is 5 m or wider, never narrower**, and the review
asked the fair question of whether "every 5 m" then means what the table above
measured. Asked of the built graph, weighted by length — which is the weighting
that matters, since a short edge contributes little of the network:

| effective spacing | share of the network's length |
|---|---:|
| under 6 m | **90.5 %** |
| 6 to 8 m | 7.4 % |
| 8 to 10 m | 2.1 % |
| 10 m or wider | **0.0 %** |

Mean 5.04 m, median 5.10 m, and nothing at all at 10 m or coarser: a long edge's
spacing converges on the step, and only short edges — which carry almost no
length between them — sit above it. So the fidelity the table measured holds
over 98 % of the network by length. `⌈length / 5⌉ + 1` would put every edge at
5 m or finer and cost 1,542,371 samples against 1,406,040, a tenth more traffic
against a public endpoint for the last 2 %. Not worth it, and it would move
every figure this phase was accepted against.

For orientation, UT.no publishes +881 m for this route against our 992 m. There
is no ground truth to appeal to; UT evidently smooths harder. Since the map shows
UT's own figure alongside, staying near their convention has something to be said
for it — but this is a single route, and worth checking across several before
tuning to match.

##### Built, and the table above does not reproduce

**The invariance does; the absolute figure does not.** Phase 2, built exactly as
specified, reads Sjøbergmarsjruta at **1,176 m** on UT.no's digitisation,
**1,196 m** on Turrutebasen's and **1,195 m** on FKB's, where the table says
996 m. These are now the reference. What was checked before saying so:

| | the table above | built |
|---|---:|---:|
| 5 m spacing, no threshold | 1,214 m | **1,370 m** |
| 5 m spacing, 5 m threshold | 996 m | **1,171 m** |
| what the threshold removes | 218 m | **200 m** |
| 5 / 10 / 15 m at the 5 m threshold | 996 / 992 / 994 | **1,171 / 1,167 / 1,163** |

The right-hand column is sampled uniformly along the UT.no chain, the same way
the left-hand one describes, so the two are directly comparable — and the
disagreement is already there **with no threshold applied at all**. The filter
takes out much the same amount either way; it is the series underneath that
differs by some 160 m. So this is not the ascent rule, it is what was sampled or
what was read.

Three other readings of "ignore gains under 5 m" were tried on the built series
and none lands near 996 m: turning at the threshold gives 1,171 m, keeping only
points a threshold apart gives 1,098 m, and smoothing the series first gives
1,234 m — and the last is **not invariant**, falling to 963 m at 100 m spacing,
which the table above requires of whatever produced it.

**It was recovered afterwards, in review, and the recovery is what settles the
question.** Compose the chain's series the way the build does — out of its edges,
in order, the shared node counted once — and apply the threshold in its
*strictest* reading, where any fall at all ends the climbing run: UT.no reads
**999.7 m**. That is the 996, near enough. So the original figure was neither
invented nor mis-sampled; it came from a defensible reading of the same rule.

That reading is nevertheless the wrong one, and the reason is visible only
because the same ground is digitised three times:

| on one identical series | UT.no | Turrutebasen | FKB | spread |
|---|---:|---:|---:|---:|
| as built | 1,175.7 | 1,196.3 | 1,195.4 | **20 m** |
| strictest reading | 999.7 | 755.2 | 932.7 | **245 m** |
| no threshold | 1,375.6 | 1,394.0 | 1,389.3 | 19 m |

A steady climb that the height model dresses in centimetre wobble is chopped by
the strict reading into runs of which none reaches five metres, and how much
survives then depends on how noisy that particular digitisation is rather than on
the hill. Three drawings of one slope must not differ by a quarter of the answer.
**Take the cross-source spread as the test of an ascent rule, not the invariance
alone** — the strict reading passes invariance across sampling steps and fails
this, and only the second one asks whether the number is about the terrain.

Two smaller things the build turned up about this route:

- **It resolves under two names, not one.** UT.no publishes *Sjøbergmarsjruta*
  and Turrutebasen *Sjøbergmarsjen*, which reaches FKB through the route-name
  join. Searching for either in full finds one digitisation and misses two.
- **UT.no's reads lowest of the three**, by 20 m, against the expectation that a
  consumer GPS track's noise would add climb. At this threshold it does not: the
  noise is what the threshold removes, and what is left is the terrain, which
  the surveyed digitisations follow more closely.

#### What it costs in the page

1.1 million elevations, delta-encoded at 0.01 m next to the geometry, land under
two megabytes. A decimetre would save 0.8 MB and was what this said until an
exported file stopped agreeing with itself: the height service answers in
centimetres, the GPX states an ascent computed from them, and with the last digit
dropped a reader recomputing it off the file's own values got up to 10.5 m —
9.2 % on a short climb — away from the figure the same file states. The digit is
not precision anyone invented; it is what was measured. Measured against the built graph, the count holds: 1,017,876 unique
coordinates once they are rounded to the centimetre, which is 28 % fewer than the
1.41 million samples taken, because edge ends meet at nodes. Phase 2, built,
lands two apart: **1,406,040 samples, 1,017,874 distinct**.

Store **two sets of figures**, and do not confuse them:

- **Per edge: ascent and descent** — 234,358 numbers each, nothing — for
  elevation-aware routing, where per-edge is exactly the granularity a weight
  needs, and for nothing else.
- **Per chain: ascent, descent, high and low point**, computed over the chain's
  full series, for anything displayed.

An earlier draft said the per-edge figure was "what lets every path show its
climb without unpacking a profile". It is not, and the error is not small. The
reported ascent ignores gains under 5 m, and that threshold restarts at every
edge boundary: 42 % of the edges are shorter than 5 m and the median is 6.9 m, so
most of them report no climb at all, and a chain of twenty such edges rising
sixty metres would sum to zero. Summing per-edge ascents does not approximate the
figure — it destroys it. Over the whole network, built: **222.4 km of ascent per
chain against 148.4 km summed per edge**, which is 67 % of it.

**Descent is stored wherever ascent is**, rather than being derived later. A
chain is oriented so that its id stays stable across builds, not because a walker
is obliged to take it that way, so an ascent alone is true in one direction and
silent about the other. The high and low point carry no threshold and could
disagree with nothing — but the popup that shows them is rendered in Python at
build time, so they have to sit on the chain like the rest.

**The chain's series is laid out from its edges', not sampled a second time.**
Every edge samples both its own ends, so consecutive edges share a coordinate at
the node between them — which is where most of that 28 % of duplication comes
from — and laying the edges of a chain end to end gives the chain's own series
with each node counted once. Sampling the chain separately would double the
requests for the same numbers. A chain is linear, so its edges form a path and
following it is unambiguous; the exception is a chain that touches itself, which
leaves the walk a choice at that node. 49 of the 11,290 do, and what a walk
cannot reach in one pass is laid down after a gap rather than joined, so no climb
is counted across a step nothing was measured along.

### Elevation in the profile and in the export

- **The profile** is distance against elevation, drawn at the foot of the map,
  with total ascent and descent. It serves two things: a route being planned, and
  a track selected by clicking it. Draw it from the 5 m samples themselves — the
  smoothing that belongs here is the ascent threshold, applied to the reported
  figure, not to the curve.
- **It shares the foot of the map with the legend**, which already sits bottom
  left. Give the panel the full width and let the legend keep its corner above
  it, or move the legend — but decide it once. Both being folded away by default
  makes the clash rare, not absent.
- **Draw it as inline SVG, by hand.** No charting library: the page is
  self-contained and a script pulled from a CDN does not load from `file://`. It
  fails silently, the way the OpenStreetMap tiles once did. The curve is one
  path, two axes and a crosshair — the legend and the search box are hand-written
  for the same reason.
- Ten thousand samples do not need ten thousand points on screen. A chart 900 px
  wide needs about 900: reduce to one column per pixel, keeping that column's
  minimum and maximum so no spike is lost. Draw from the reduced series, compute
  ascent from the full one.
- **One GPX, dense.** A second, sparser variant was considered and dropped:
  Komoot and Outdooractive do not know FKB's or N50's paths — those are not in
  OSM — so they cannot reconstruct a route from widely spaced points. They would
  draw straight lines between them or snap to a network that has nothing there.
  The geometry *is* the information.

  A 50 km route at one point per 5 m is about 10,000 trackpoints, roughly 800 kB.
  That is an ordinary GPS track. No point limit is known that would justify a
  reduced file; if one turns up, adding it is a simplification pass and an hour's
  work.
- **Build the track from the vertices, then fill the gaps.** Do not simply
  resample the line every 5 m: that drops the original vertices and rounds off
  every corner between two samples. Keep every vertex, insert extra points only
  where a gap exceeds 5 m, and carry an `<ele>` on all of them.
- **A waypoint set at a named place keeps the name.** The map already draws huts,
  quays, trailheads, farms and settlements; a waypoint landing within about 50 m
  of one takes its name, type and position for the `<wpt>`, while the route stays
  on the network. Do not move the route to reach a building standing 30 m off the
  path — the name is the useful part, not the geometry. A file whose waypoints
  read *Lavasshytta → Sæterskaret skogstue → Bønå ferjekai* is a different thing
  in Komoot than three bare coordinates.
- **A planned route** carries its waypoints as `<wpt>` elements and each leg's
  mode — routed, free over land, crossing — in a small `<extensions>` block. Both
  cost nothing, both are what GPX provides for, and together they make the
  exported file a **save file**: the waypoints let a plan be rebuilt, the modes
  let it be rebuilt exactly rather than approximately. Komoot and Outdooractive
  ignore extensions they do not recognise. Write them from the first export of a
  plan, not later: a file written before the description existed can never be
  restored exactly, only matched.
- **A single exported chain** has neither waypoints nor legs, but it still says
  what it is: its name, its source and its chain id. That is enough to recognise
  it on load rather than match it, and it means the `<extensions>` mechanism is
  built once, with the writer, instead of being retrofitted when a plan first
  needs it.
- The six GPX files the map writes at build time come from the raw sources
  today. From phase 3 they are built from chains instead, so one geometry serves
  the map, the exports and the router; from phase 5 they carry `<ele>` like
  everything else.
- Elevation belongs on the trackpoints, not only in a summary: Komoot and
  Outdooractive both read `<ele>` and will draw their own profile from it.
- Every path's popup can now carry its ascent and offer its profile, not only a
  planned route. That is the main thing the build-time sampling buys.
- A straight-line leg's elevations are fetched when it is drawn. Until they
  arrive, show the leg's profile as pending rather than as flat ground.

With a height on every edge, **elevation-aware routing is now within reach** — an
edge cost with a penalty per metre climbed, so a route prefers the contour over
the ridge. The per-edge ascent figure is all it needs. Treat it as a separate
change to the weights, and check that routes do not start taking absurd detours
before turning it on.

### A selectable track is a chain, never a network

Today a click selects everything sharing a name or a register id. For a road
that branches, that is a network, and a network has no elevation profile —
there is no single sequence to lay the samples along.

This is not an edge case. Of 544 named roads in the zone, **178 branch**:

| | |
|---|---:|
| one unbranched run | 366 — 67 % |
| branching | **178 — 33 %** |

| road | length | junctions | chains |
|---|---:|---:|---:|
| Tosenveien | 44.2 km | 24 | ~40 |
| Vefsnvegen | 24.1 km | 15 | ~25 |
| Vestersidvegen | 22.8 km | 16 | ~22 |
| Tveråvegen | 15.1 km | 7 | ~8 — phase 1 built **14**, longest 5.17 km |

So **split every named group into chains** and make each chain its own selectable
track, even where they share a name.

But a chain must not end merely because something crosses it. Two tracks laid
over each other are not a branch; the track carries straight on. A chain ends
only where the same way genuinely continues in more than one direction.

**Identity decides first, geometry only where there is none.** Arriving at a
junction on a way that has a name or an id:

| other arms carrying the same identity | |
|---|---|
| exactly one | carry on into it — a crossing is not a branch, and the angle gets no veto: a hairpin that keeps its name is still the same road |
| two or more | the way itself divides. The chain ends here. |
| none | nothing to follow. Fall through to the geometry below, or end. |

That last case is the common one, not the exception: FKB carries no names at all,
nor do N50's paths. Names exist for roads through the register join, for
Turrutebasen's routes, and for OSM ways that have one.

Where identity cannot decide, use the **stroke** rule from network analysis: at
each junction, pair the arms that continue each other straightest and carry the
chain through them; an arm left without a partner starts a new chain.

The angle is measured **only at a junction**, and only between the direction an
arm arrives in and the direction a candidate leaves in, each taken over the
**first 5 m** either side of the node — or the arm's whole length where it is
shorter than that. It says nothing about how a way bends along its
own course — a road can climb a hillside in hairpins and stay one chain, because
there is no junction there and nothing to decide.

```
arriving on A at a T:        A -> B deflects 10 deg  -> paired, the chain runs on
        C                    A -> C deflects 80 deg  -> no partner, C starts its own
        |
  A ----+---- B
```

Measured against the naive rule of breaking at every junction:

| source | break at every junction | 30° | **45°** | 60° |
|---|---:|---:|---:|---:|
| FKB | 9,118 — mean 217 m | 6,160 | **5,959 — 332 m** | 5,906 |
| N50 roads | 3,908 — mean 387 m | 1,835 | **1,724 — 878 m** | 1,691 |
| N50 paths | 1,365 — mean 775 m | 997 | **961 — 1,100 m** | 950 |

**Use 45°.** N50's roads more than double their mean chain, 387 m to 878 m, and
loosening to 60° buys almost nothing. Read the threshold as: at a junction, an
arm deflecting by more than this is not a plausible continuation of the one
arriving. Where no pair at a junction comes within it, every arm ends its chain
there.

The pairing is a heuristic and it will occasionally join the wrong two arms. The
clearest case: a road that itself turns 90° at a junction while a different road
runs straight on. The angle rule follows the wrong one; identity, where it
exists, turns correctly. Where it does not — FKB carries no names — the cost is a
cosmetic error in what lights up. The selection stays linear either way, so the
profile stays well defined.

#### Give the paths an identity first, from Turrutebasen

The angle rule carries the paths only because they have no names. Some of them
can be given one.

SSR does not help here: across the eight municipalities its line layer holds
1,199 `adressenavn` and exactly **one** `sti`. Its point layer names 23 paths,
but as points — they mark a spot, not a run, and cannot be joined to a line the
way the road names were.

Turrutebasen can. It names its routes, and it is 96–100 % contained in FKB — the
measurement is in `pipeline/docs/trail-network-sources.md`, which recommends
exactly this pairing and has never been implemented. So join route names onto FKB
with `attach_nearest`, the same way road names were joined onto N50, with the
same `min_overlap` guard against a side path taking the name of the route it
meets.

Built, that names 1,214 FKB paths carrying 173 km of FKB's 1,979 km in the zone —
Turrutebasen's own 235 km is what does the naming, not what comes back named, and
an earlier draft of this document confused the two. Small in length either way,
but it is the **waymarked** part: where a walker most expects a name, and where
the chain rule most wants a reliable one instead of a guess about angles.

#### The rule, in order

For each source on its own:

1. Node it and `linemerge`. That already joins everything that meets end to end.
2. Attach identity where a source can supply it: register ids for N50's roads,
   route names from Turrutebasen for FKB, OSM's own `name`.
3. At every junction, decide what continues what:
   - the arriving way's identity appears in **exactly one** other arm — continue
     into it, whatever the angle
   - it appears in **two or more** — the way itself divides; the chain ends
   - there is no identity to follow — pair the arms deflecting least, accepting
     up to 45°
   - nothing at the junction comes within 45° — every arm ends its chain
4. Never break a chain merely because something crosses it.

UT.no trips skip all of this: one feature is one published trip, already linear
and already the unit a reader means, so they stay whole.

Turrutebasen does **not** skip it, although an earlier draft of this document
said it did. Its published unit is the named *route*, and the register draws that
as 770 separate segments — keeping its features whole would give 770 scraps, the
opposite of the intent. So it goes through the rule above, where the identity
step reassembles each route across its segments and ends a chain only where the
route genuinely divides: 770 segments become 244 chains.

The invariant the whole rule exists to protect: **a selectable unit is linear.**
Anything that would produce a branching selection is a bug, because it has no
elevation profile.

#### What a chain carries

A chain spans several source features and their values need not agree along it.
The rule, which the road layers already follow:

- a value constant across the chain passes through unchanged
- values that differ are joined, deduplicated and ordered — `sti / traktorveg`
  for a run that changes character, `JA / NEI` for one that is waymarked only in
  part. Both are true and both are useful.
- lengths and ascent are never inherited. They are computed from the chain.

A chain that closes on itself — a loop road, a round trip — has no endpoints. It
is still linear and still profilable; the profile simply begins wherever the ring
was cut. Anything reaching for "the two ends" has to cope with there being none.

Where an identity exists, the popup shows the chain's own figure *and* the named
way's total, so a stretch of Tveråvegen reads 3.2 km against the road's 15.1 km
rather than pretending to be either.

#### The graph is one artefact, not a set of options

It always holds every source over the whole extent. The extent is a parameter and
part of the cache key; which sources go in is not a choice.

The map's `--no-osm`, `--no-n50`, `--no-fkb`, `--no-roads`, `--no-ut` and
`--no-names` therefore go. They predate the layer control, which does the visual
job better — per layer, instantly, without a rebuild — and their other purpose,
skipping an expensive fetch, is answered by the cache after the first run. With a
graph they are worse than redundant: a missing source does not make it smaller,
it makes it **wrong**, and quietly. Without roads the largest component falls from
79 % of length to 5 %; without ferries eleven of seventeen quays are unreachable;
without the place-name register the chains lose the identity that keeps them
whole and fall back on the angle heuristic. Each produces a map that looks
plausible and disagrees with every figure here.

So: a source that cannot be loaded is an error, not a smaller graph.

`--fkb-km` goes as well, folded into `--approach-km`. It existed because FKB is
dense — 14,045 features over the full zone against 2,169 within 5 km — and
density is exactly what chains solve: those 14,045 become 5,959 drawn objects.
Every measurement in this document already assumes FKB over the full 15 km; every
other source was always loaded that way.

What remains: `--approach-km` as a graph parameter, `--simplify-m` for the drawn
copy only, `--force-download`, and `--highlight` as a diagnostic.

#### Chain ids have to be stable across builds

They key the elevation cache, the click highlight and the search. An id that
shifts because a source was re-downloaded churns all three and throws away work
that did not change. Derive it from something the geometry owns — the rounded
coordinate of the chain's first point together with its length reads well and
survives an unrelated edit elsewhere — never from the order chains happen to come
out in.

#### Source priority plays no part in this

Worth stating, because it is the natural thing to reach for and it is how the
earlier attempt went wrong. Priority appears in three places in this design and
they are easy to conflate:

- **Routing cost** — the per-source factor on each edge, so a route prefers the
  UT.no track over a strand of N50 lying beside it. This is where priority
  belongs.
- **Draw order** — where several sources describe the same valley, the topmost
  line is the one a click hits. That already exists in the map today.
- **Chain formation** — nowhere. Chains are built **per source, on its own**, so
  the sources never compete and there is nothing to rank.

That last one is not an oversight. The moment sources compete over geometry, the
network falls apart: cutting the lower-priority line away where a better one
exists halved the reach, 94 % of the park down to 48 %. Keep them separate and
let the weights sort out which one a route follows.

The one thing that looks like priority but is not: **identity comes from a
designated source per attribute** — road names from SSR, path names from
Turrutebasen. That is a division of responsibility, not a ranking of rivals.

Every consequence of this is good:

- A selection is always linear, so its profile is always defined. The ambiguity
  the profile panel would otherwise have to apologise for disappears.
- Clicking a side branch selects the side branch, which is what a reader means.
- Search is unaffected: it matches by name and lights every chain carrying it.
  Search decides visibility, clicking decides emphasis — they stay separate.

What is lost: clicking Tveråvegen no longer lights all 15.1 km, only the chain
under the cursor. Cover that in the popup rather than in the highlight — show
both the chain's length and the named road's total, so neither number is a lie:

```
Road          Tveråvegen
This stretch  3.2 km
Road in total 15.1 km
```

#### Draw from the graph, and keep two kinds of unit apart

The map should draw the routable layers **from the graph**, not from raw source
geometry keyed by name. What that buys is that a drawn line and a selectable
track become the same object — the chain — instead of a name-group that may be a
network.

It does **not** mean drawing the merged network. A drawn line is a chain, built
within one source; a routing edge is a piece of the merged graph, split at every
crossing. They are different things and both are needed:

| | unit | count | what it is for |
|---|---|---:|---|
| drawn, selectable | chain, per source | under 10,000 | clicking, profiling, exporting |
| routable | edge, merged | ~130,000 | finding a way from A to B |

The link between them is that **every edge names the chain it lies on**. That is
the correspondence to maintain, and it is a single field, not a spatial join
between two geometries noded differently.

Everything the map does today survives this. Each source still draws its own
layer in its own colour, so switching UT.no off still leaves the network beneath
it. Where several sources describe the same valley, their lines still lie over
each other as separate objects, and a click still takes the topmost.

Chains are still simplified for drawing, exactly as the layers are today:
`--simplify-m` applies to the drawn copy alone. The chain's own geometry, which
the profile and the export read, stays at source resolution.

The split into "in park" and "approach" survives too, but **never by cutting a
chain at the boundary** — that would rebuild exactly the fragmentation this rule
removes, and tear the profile of any way that crosses. Put each chain in the
layer where the greater part of its length lies. The toggles keep working and the
chains stay whole.

But the drawing unit and the routing unit are **not the same**, and confusing
them wrecks both:

- **Routing** uses the fully merged graph — every crossing between every source
  is a node. 234,358 edges at a 26 m average.
- **Drawing and selecting** uses units decided *within* each source. A chain
  broken wherever some unrelated parallel dataset happens to cross it is a 43 m
  scrap, useless as something to click, and there would be ten times as many of
  them as the map draws today.

Measured, chains computed within each source:

| source | drawn today | broken at every junction | the 45° angle alone | **identity first, then the angle** |
|---|---:|---:|---:|---:|
| UT.no | 35 | 15,469 | 451 | **35, kept whole** |
| Turrutebasen | 770 | 251 | 121 | **245** |
| FKB | 14,045 | 9,096 | 5,952 | **6,201** |
| N50 paths | 1,715 | 1,365 | 958 | **958** |
| N50 roads | 5,272 | 3,908 | 1,723 | **2,326** |
| OSM | 1,974 | 2,480 | 1,504 | **1,505** |
| Ferries | 65 | 47 | 21 | **21** |
| **total** | **23,876** | 32,616 | 10,730 | **11,290** |

The third column is what this document originally measured and estimated at
"about 10,500"; phase 1 reproduces it at 10,730. The fourth is what the rule
actually specifies and what the graph is built from. Identity costs 562 chains
rather than saving them, because a named way ends its chain wherever it divides,
and a named road divides at most of its junctions — that is the rule working, not
failing. Both columns are printed side by side by `route_graph.py`, so the
difference stays visible.

So drawing chains is **fewer** objects than the map draws today, not more: the
render load roughly halves. An earlier draft of this document said "well under
10,000", which was too generous — it had not counted FKB over the full extent.

One exception the table exposes: UT.no shatters into 2,411 pieces because its 35
routes overlap each other heavily and noding cuts them at every shared stretch.
A published route's natural unit is the trip, and a trip is already one line with
a well-defined profile. **Keep UT.no trips whole**; decompose only the network
sources. Turrutebasen needs the same judgement: its named routes are the unit,
split into chains only where one genuinely branches.

The rule underneath all of this: a selectable unit must be **linear**. How each
source reaches that is the source's business.

### Not GraphHopper, and why

This repository exists to build GraphHopper routing graphs, so the question is
fair. For this feature the answer is no, for one structural reason and three
practical ones.

GraphHopper is a **server**. The map is a file you open by double-clicking. Using
it would turn "open the map and plan" into "start `java -jar
graphhopper-web.jar`, arrange CORS so a `file://` page may call
`localhost:8989`, then open the map". That is the wrong trade for the ad-hoc
planning being asked for.

Beyond that, and as recorded in `pipeline/TODO.md`:

- the transform still emits raw Norwegian tag values — `highway=Fotrute`,
  `sac_scale=Enkel (Grønn)` — which GraphHopper cannot route on at all
- the workflow does not yet call the real steps
- the pipeline reads **Turrutebasen only**: 235 km inside this zone against the
  5,523 km of the merged network. It would route on a twentieth of what the map
  draws.

And 130,000 edges need no contraction hierarchies. A Dijkstra with a binary heap
answers in milliseconds.

What GraphHopper would genuinely do better is a **foot profile** that judges a
route over a ridge differently from one around it, plus turn restrictions and
alternatives. Note that the elevation work above closes the data gap that used
to make this argument decisive: with a height on every vertex, a climb penalty
in the edge cost gets most of the way there without a server. Turn restrictions
and alternatives remain genuinely absent, and remain the reason to revisit this.

### A server would help, but not with anything that is blocking

Asked separately from GraphHopper: would moving to client and server be better?
Measured, nothing in this design requires it. 1.8 MB of graph in the page, a
Dijkstra over 130,000 edges answering in milliseconds, a profile in seconds, and
94 % of the park reachable. Against that, a server turns a file you double-click
into a service you must start first.

Three things would change that, and none is true yet:

- **More than one area.** This graph fits in a page; Norway does not.
- **Elevation-aware routing**, which needs heights for the whole network. Phase 2
  now provides them, so this argument has weakened since it was first made.
- **Turn restrictions, alternative routes, a real foot profile** — GraphHopper's
  territory, and then the pipeline work pays for itself.

The one place a server would help today is elevation: it would replace repeated
calls to a public endpoint with a local sample. That needs no routing server at
all, only a small service holding a DTM extract — the sketch in
`docs/trail_routing_architecture_guide.md` is the shape of it. It is not needed
while the point store keeps a second build from asking again.

What makes this cheap to revisit: **the graph module is architecture-neutral.**
It takes GeoDataFrames and returns chains and edges. Whether that feeds a
Dijkstra in a page, a service, or the pipeline's transform step is a decision
downstream of it, and building it now commits to none of them.

### The graph module is shared ground with the pipeline

The two paths are not rivals; the second builds on the first. The merged network
specified here is exactly what the pipeline should be transforming.
`pipeline/docs/trail-network-sources.md` already recommends FKB as the geometry
base with Turrutebasen supplying attributes, and that recommendation has never
been implemented.

So shape the graph module accordingly, and the work is done once:

- Keep it a **library module under `libs/src/trails/`**, free of anything to do
  with Folium, browsers or this one park. Concretely: it takes named
  GeoDataFrames and a clipping geometry, and returns chains and edges. Choosing
  the extent, loading the sources, encoding for the page and everything Folium
  stay in the calling script — which is what lets the pipeline call the same
  module with its own sources.
- Keep the **source of each edge** on the edge. The browser uses it for the
  priority weighting; the pipeline needs it to pick the right OSM tags.
- Return **plain geometry and attributes**, not an encoded payload. Encoding for
  the browser is the map script's job, not the graph builder's.

Then `pipeline/src/graphhopper_pipeline/steps/transform.py` can consume the same
module and write its OSM PBF from a network twenty times richer than the one it
uses today.

### A plan is persisted as its GPX, and only ever as coordinates

There is no store, no database and no session. A plan lives in the page and is
exported; the exported file is what carries it forward. For ad-hoc planning that
is enough, and it has the property that a plan is portable by construction.

One constraint follows and it is worth stating before anything is built:
**waypoints are stored as coordinates, never as node or chain ids.** Coordinates
survive a rebuild of the graph; ids do not. Get this wrong and a plan saved today
points at nothing after the next source update, and the format has to be broken
to fix it.

That also answers what happens when the sources change under a plan: nothing.
It is re-matched or re-routed against whatever the network is now, and the
difference is visible rather than silent.

### What else an exported file carries

Beyond the geometry, the elevations and what the file is:

- **The data it was built from.** Turrutebasen publishes a version string, N50
  and SSR carry the date they were ordered. Load a plan months later and the
  route may differ; without this there is a difference and no cause. One line,
  and it is the difference between a puzzle and an explanation.
- **The ascent figure together with how it was reached** — `DTM1, sampled every
  5 m, gains under 5 m ignored`. The same route measured differently reads
  anywhere between 965 and 1,214 m, so the number alone asserts nothing. It also
  explains why the figure will not match the one Komoot computes from its own
  model.
- **The named ways the route follows**, in the track's `<desc>`: *via
  Tveråvegen, Gamle Stavassveg, Sjøbergmarsjruta*. That is how a person describes
  a route, and every edge already knows its chain.
- **How far it runs where no source records a path**, from phase 1B's
  `no_path_recorded`: *8 km with no path recorded in any source*. For a route
  through this park that changes the character of a day more than any other
  single figure — the three-day Rundtur reads 11 of its 42 km that way. It is
  summed from the edges, so it costs a column and nothing else.
- **When the file was written**, in `<metadata><time>`.

And one thing to leave out deliberately:

- **No `<time>` on the trackpoints.** Komoot and Outdooractive read a track
  carrying timestamps as a *recorded activity* rather than a plan. Inventing them
  would turn a route you are considering into a walk you never took. For the same
  reason, no speeds and no durations: both would be guesses dressed as data.

Per-leg source attribution is not worth carrying either — but the reason first
given for that was too narrow, and it is worth correcting rather than leaving to
be rediscovered. The file-level list settles the **licence** question. How well a
line is *evidenced* is a different question, and one this park makes sharp: N50
discloses that 47 % of its paths here were digitised off an older map rather than
surveyed, some captured in the 1960s at accuracies to 50 m.

That still does not belong in the file, for a reason that only measurement
showed: **FKB carries 90 % of the network and discloses nothing at all.** A
route-level summary would therefore read *3 km measured on the ground, 5 km seen
in imagery, 30 km not disclosed* — true, and useless to someone opening the file
in Komoot, because "not disclosed" dominates almost every route.

Where it does belong is the popup, and that is where it now is: `survey_method`
and `surveyed` on every N50 and Turrutebasen line. Looking at one line, the
answer is concrete — *digitised from a map, 1984* — and it is exactly what a
reader doubting a path needs. One line and a whole route are different questions
and want different granularity.

### How much of a route is waymarked

For a route through a roadless park this is as much a planning fact as the
distance. *8 km marked, 14 km unmarked* says what kind of day it will be;
38 km on its own does not.

The data is already there and already shown in popups: N50 carries `rutemerking`,
Turrutebasen the marking type and the maintaining body. What is new is only that
an edge has to keep it — which is why it is in phase 1B — and that a route sums
it.

Three things to get right:

- **Report it as length, not as a proportion of edges.** Marked stretches are
  long and unmarked ones fragmentary, so counting edges would flatter the marked
  share badly.
- **Unknown is its own answer.** FKB carries no marking information at all, and
  FKB is the largest source in the network. A stretch on FKB is not "unmarked",
  it is *not known*, and reporting it as unmarked would be a claim the data does
  not support. Three buckets: marked, unmarked, unknown.
- **Free legs are unmarked by construction**, not unknown. Nobody marks a line
  you drew across open ground.

#### The rule, in order

No single field answers this, so it is derived — and derived per **edge**, not
per chain, for a reason measured below.

1. **The edge's own source states it.**

   | source | says |
   |---|---|
   | Turrutebasen | **marked** — 770 of 770 segments in this zone read `marking = Marked`, so membership *is* the statement |
   | N50 paths | **marked** where `rutemerking = JA` (289), **unmarked** where `NEI` (747), nothing where unset (679) |
   | FKB · OSM · roads · UT.no | nothing |

2. **Otherwise the ground states it.** An edge with at least **half its length
   within 10 m** of an edge whose source calls it marked is marked too. Half, not
   merely near: this repository has already paid for that lesson once, when
   joining road names by nearness alone put 23 % of them onto the side road at a
   junction, and `min_overlap` was what fixed it. The same guard applies here.

3. **Otherwise `unknown`** — never `unmarked`.

**UT.no says nothing, and must not be assumed to.** It is DNT, so red-T marking
is the obvious guess, and here it is wrong: measured, only **34 % of its 376 km**
lies on ground any other source calls marked — 128.9 km within 10 m, 133.0 km
within 25 m. The figure barely moves with the tolerance, so it is a real property
of the terrain and not an artefact. Two thirds of the described routes cross
ground nobody marks, which is what this park is. Calling UT.no marked because of
who publishes it would overstate by some 250 km.

**Why per edge and not per chain.** A chain takes one value along its whole
length, and both network sources smear when it does:

| | chain level says | measured |
|---|---:|---:|
| FKB carrying a Turrutebasen route name | 560 chains, 223 km | 1,214 paths, 173 km — **50 km too much** |
| N50 paths | 38 chains read `JA / NEI`, 158 km | unresolvable at this granularity |

An edge averages 26 m, so deriving it there costs one spatial query per edge and
removes both errors at once. It is one of only two attributes that sit on the
edge rather than being read through `chain_id` — the other is below — and both
earn the exception by being summed in kilometres.

**As built, the two steps above are one test against two masks**, and step 1 is
not a special case of anything. A mask of every Turrutebasen feature and every
N50 path reading `JA` is what "marked" means; a mask of the ones reading `NEI` is
what "unmarked" means; every edge is then tested against both by the same half-
length rule, and a Turrutebasen edge comes out marked because it lies on its own
feature. Reading step 1 off the edge instead would go wrong exactly where it
matters: `rutemerking` reaches an edge only through its chain, and 38 chains
carrying 158 km of it have already been merged into an ambiguous `JA / NEI`.

Measured over the built graph, and this is the reference:

| source | marked | unmarked | unknown | total |
|---|---:|---:|---:|---:|
| UT.no | 115.8 km · 31 % | 43.8 km · 12 % | 216.5 km · 58 % | 376 km |
| Turrutebasen | 235.3 km · 100 % | — | — | 235 km |
| FKB | 246.3 km · 12 % | 376.0 km · 19 % | 1,356.8 km · 69 % | 1,979 km |
| N50 paths | 248.5 km · 24 % | 535.3 km · 51 % | 273.4 km · 26 % | 1,057 km |
| N50 roads | 42.0 km · 3 % | 1.4 km · 0 % | 1,471.0 km · 97 % | 1,514 km |
| OSM | 151.5 km · 22 % | 146.3 km · 21 % | 393.5 km · 57 % | 691 km |

Two of those are worth reading twice. **Unknown is the largest bucket in the
network**, which is what makes it its own answer rather than a rounding of
unmarked: 3,700 km of the 5,850 walked. And **FKB reads 19 % unmarked**, none of
which is FKB's own statement — it carries no marking field at all. That is N50
lying along it and saying so, which is precisely the case masks exist to catch
and reading each source's own fields would have missed.

### Whether there is a path at all — and why that cannot be answered

A route register suggests a way; a topographic dataset records one. In a park
that is largely trackless those come apart, and the obvious next question is how
much of a route runs on an actual path. It cannot be answered, and the reason is
worth writing down so nobody builds it twice.

**The sources over-record.** FKB knows only `sti` and `traktorveg` — both assert
a physical feature, and it has no category for a recommended line over open
ground. It calls 90 % of UT.no's 376 km a path. But its WFS exposes no
provenance at all: `objtype`, `typeveg`, `vegkategori`, `vegfase`, `vegnummer`,
`kommunenummer`, and nothing about how the line was captured or when.

N50 does expose it, and what it shows undermines the whole family:

| N50 paths in the zone | |
|---|---:|
| `dig` — digitised from a map | 956 km = **47 %** |
| `fot` — seen photogrammetrically | 695 km = 34 % |
| `sat` — measured on the ground | 325 km = 16 % |
| capture dates | **1965** to 2026 |
| stated accuracy | up to **5,000 cm = 50 m** |

Along one route the maintainer knows to be largely pathless — *Tverådalen–Bønå*,
32.5 km — FKB calls 82 % of it `sti` and follows the GPS track to within 2 m over
three quarters of its length. N50 covers 41 % of it with lines **digitised from a
map**, some captured in 1983, against only 15 % seen photogrammetrically. The
evidence for "there is a path here" is largely an inherited cartographic line at
an accuracy coarser than the test used to match it.

And FKB and N50 are **not independent**: both are Kartverket, and N50 is
plausibly a generalisation of the same base. The only independent record is OSM,
which covers 22 %.

**So presence proves nothing — but absence does.** That asymmetry is the whole
of what can be salvaged, and it runs the opposite way to intuition: where sources
draw lines liberally, a stretch that *none* of them records is genuinely
recorded by none of them.

Hence one edge attribute, `no_path_recorded`, true only where nothing from FKB,
N50 paths, N50 roads or OSM lies within **25 m**. The tolerance is deliberately
generous — the more that counts as recorded, the more it means when nothing is.
Its absence asserts **nothing whatever**, and that has to survive into its name,
its docstring and any text that shows it.

Measured, it is 19.9 km of UT.no's 376 and concentrated where it matters:

| trip | with nothing recorded |
|---|---|
| Alternative Midtre – Nedre Breivatn | 4.7 of 4.7 km |
| Dagstur i Godvassdalen | 3.8 of 7.2 km |
| Rundtur i Lomsdal-Visten, 3 days | **11.2 of 42.4 km** |
| the other 32 trips together | about 3 km |

**"Nothing within 25 m" turned out to mean less than half the edge, not none of
it**, and the difference is a third of the figure. The wording above describes a
length: it was measured by buffering the route and intersecting, so a stretch
counts from where the last line leaves it. An edge is not a length but a unit
that has to answer yes or no, and asked whether *anything* lies within 25 m of it
an edge answers no only where it is clear of everything along its whole run —
which hands its whole length to whatever it touches once. Fourteen UT.no edges
are in exactly that position here, averaging 535 m each and 7.5 km between them —
long edges, because a stretch nobody records is a stretch nothing crosses, and
nothing crossing is what leaves an edge long. Built that way it reports 12.7 km
rather than 19.9, and *Dagstur i Godvassdalen* as **0.0** of its 7.2 km against the 3.5
the length measurement finds. The same half-length guard `waymarked` already uses
is what reproduces the figure, and it is the same guard for the same reason: what
most of an edge does decides the edge.

Built, and this is the reference:

| | with no path recorded |
|---|---|
| UT.no | **20.2 km of 376**, 188 edges |
| Turrutebasen | 0.1 km of 235 |
| FKB · N50 paths · N50 roads · OSM | 0.0 km — they *are* the mask |
| Rundtur i Lomsdal-Visten, 3 days | 10.3 of 42.4 km |
| Alternative Midtre – Nedre Breivatn | 4.7 of 4.7 km |
| Dagstur i Godvassdalen | 3.6 of 7.2 km |
| the other 32 trips together | 1.5 km |

Ferries and bridged connectors are excluded, not flagged. Nothing is recorded
across open water, by its nature, and nobody drew a connector — which is what a
connector *is*. Left in, the rule would report all 149 km of ferry as ground with
no path recorded, and that figure would land beside the walking.

**Decided against**, so it is not reopened:

- **No positive `on_path`.** It would report a 1983 map line at 50 m accuracy as
  a path.
- **No filtering the graph by evidence quality.** Almost nothing would survive,
  and a route over a poorly evidenced path is still the only route there is.
- **No Geonorge file download for FKB.** It carries `målemetode` and
  `datafangstdato` for FKB too and is the one thing that would change this
  picture — but it needs an account and a second loading path, which is exactly
  why the module uses the WFS. Recorded as open, not as work.

What *is* worth carrying is N50's `malemetode` itself, onto the chain, for the
popup rather than for any derived field. "Digitised from a map" beside a path is
worth more to a planner than any category computed from it.

### How much of a route lies inside the park, and how it gets there

Decide it **at the 5 m samples** — the same ones that carry elevation. The park
share is then simply how many fell inside, times five metres.

An edge's share is computed once at build time and sits on the edge beside its
length and its ascent. The error is ±5 m at each boundary crossing, which on a
38 km route is noise. Water crossings are excluded, since they are not walking
distance and so not park distance either.

**A free leg does not get this from the samples it fetches**, and an earlier
draft here said it did. The samples give a *position*; the answer needs the
polygons, and at build time Python has them while the browser does not — the
page draws **one** protected area of the nineteen the walked network touches.
The height service answers `datakilde`, `terreng` and `z`, and `terreng` is
ground cover — *Havflate*, *Skog*, *InnsjøRegulert* — not a protected area. So
the page has to carry the boundaries. Measured, that is cheap: the nineteen come
to 25,144 vertices, 1.03 MB of GeoJSON and 0.37 gzipped, and simplified to 10 m
— well inside the ±5 m the sampling already accepts at each crossing — **0.08 MB
raw and 0.03 gzipped**, against a 37.5 MB page.

In the exported file this appears twice:

- **As a figure** in the description — *22 of 38 km inside Lomsdal-Visten
  nasjonalpark*.
- **As waypoints at the crossings**, so a reader sees a marker where the route
  enters and leaves. GPX has no way to carry the boundary itself; it holds
  waypoints, routes and tracks, and no polygons.

Which forces a distinction worth making before the first generated marker exists:

**Every `<wpt>` says whether it was set or generated.** A boundary marker is not
a waypoint the reader chose, and phase 8 must not read it back as one — a loaded
route would gain stations nobody placed and start routing through them. One field
in the extensions, and loading ignores the generated ones. The rule is general:
any marker the map adds by itself, at a crossing, a hut or anywhere else, falls
under it.

**It is not only the park**, and the numbers depend on the extent they are
measured over — so this one names it. Over the bounding box of the walked
network, Naturbase returns 43 protected areas: **39 nature reserves**, two
national parks, one landscape protection area and one marine protected area.
An earlier count of 26 reserves was taken over the smaller drawn zone; neither
is wrong and a figure without its extent cannot be reproduced.

**Nineteen of them are actually touched by the network**, 741.2 km of 5,853.3.
Lomsdal-Visten holds 647.8 km of that, Holmvassdalen naturreservat 25.7,
Strauman landskapsvernområde 24.9, Stavvassdalen 17.1 and Sirijorda 11.9; the
remaining fourteen share 13.8 km, and the smallest is **10 m of Innervisten
marine protected area**.

It was written here that no reserve touches the park. **Measured, Sirijorda
does** — they share a boundary at 0.0 m — and so does Innervisten. The
conclusion it was used for still holds, since sharing a boundary is not
overlapping and a route strictly inside the park is still outside Sirijorda; the
premise was simply wrong.

So report **protected areas**, not the national park alone: *38 km, of which 22
in Lomsdal-Visten nasjonalpark and 3 in Strauman landskapsvernområde*. Reserves
carry their own, sometimes stricter, rules, and a figure that counts only the
park would be silent about them.

The work is small, and it was measured rather than guessed: `naturbase.Source`
searches by name today and needs a spatial query — the same endpoint with
`geometry`, `geometryType=esriGeometryEnvelope` and
`spatialRel=esriSpatialRelIntersects` instead of a `where` clause. One request
answers. The samples then carry which area they fell in rather than a yes or no.

**Two things have to be decided rather than discovered.** *Which* `verneform`
count — `naturbase.Layer` already separates the five, and a walker reading that
a route passes a marine protected area learns something different from a nature
reserve. And **how little counts as touching**: five of the nineteen are met over
less than 400 m and one over ten. Without a threshold a route that brushes a
boundary reports an area it never entered and generates a pair of waypoints for
it — and a rounded label is a threshold like any other.

One thing is deliberately not claimed: the rules inside a Norwegian protected
area differ from outside, but *how* they differ is in each area's verneforskrift
and none has been read. The figure is a fact about the route, not advice.

### What a route's file says that a chain's cannot

A chain is one line from one register, and phase 5's file says so in one track.
A route is a sequence somebody chose, and three things about it have nowhere to
go in that shape. Each was decided while building phase 6B, against what was
measured rather than what looked tidy.

**The clicked points travel as `<wpt>`, before the track.** A waypoint is a GPX
1.1 top-level element and **not** part of the `<extensions>` mechanism — the
extensions are a block inside it — so a file putting one anywhere else parses
and fails the schema. Neither writer could write one at all before this phase:
the string appeared zero times in both.

Every one says whether it was **set or generated**, and the field goes in now
though nothing generates a waypoint until 6C. A file written before its own
description existed can never be restored exactly, only matched — and phase 8
must never read a marker the map placed at a boundary or a hut as a station
somebody chose, or a loaded route gains points nobody put down and starts
routing through them.

**No `<ele>` on a waypoint.** The track carries every height that was read and
the file states the rule they were read under; a height on the waypoint as well
would be that number in a fourth place, and where the route breaks at that very
point there is no reading to put there at all.

**A leg's mode goes on the track and cannot go on a `<trkseg>`.** That is a fact
about the geometry rather than a preference: a segment is a stretch of track and
a stretch breaks only where the ground stops, so four routed legs laid end to
end are **one** segment and a segment-level extension would carry one mode for
all four. So the track's extensions hold `<trails:legs>`, one `<trails:leg>` per
leg in the order they were clicked, each holding its parts in the order they are
walked — `routed`, `land`, `water`, `ferry`, with the metres of each. Leg *n*
runs from waypoint *n* to waypoint *n + 1*, which is what lets the list be read
without an index on either side.

**A crossing's own line is never written into the track.** It ends the segment
and leaves a gap, and the gap is the crossing. Writing it as a segment of its
own was the obvious alternative and is wrong: GPX has no way to say a segment is
a boat, so every reader would import a fjord crossing as a walked line — which is
the failure this whole distinction exists to prevent. What the file does say
about it is exact: the leg list names the part and its length, `<trails:crossed>`
sums them, and the description says *1 crossing, 5.06 km*.

So **every break in the track is a crossing** — but the count runs the other
way round from the obvious guess, and phase 8 is the one that would be caught by
it. A segment is a walked stretch, and a crossing only adds one where it lies
*between* two of them: a route that starts from a quay a ferry reaches, or ends
at one, has one crossing and **one** segment, and two crossings back to back
still yield two. `segments = crossings + 1` holds only for a route that begins
and ends on foot with no two crossings adjacent, which is most of them and not
all. Read the leg list for the order; read the breaks only as *a crossing was
here*.

Measured on a route from a quay only a ferry reaches: one leg of
`routed 2,027 m · ferry 5,057 m · routed 1,737 m`, two segments, one break.

**The sources carry their own metres.** `metres` is a field of a source credit
rather than a block of its own, so it lands on the entry that already names the
licence and the version — *3.20 km OSM (ODbL 1.0)*. A chain leaves it unset,
because a chain has one source and its length is the track's, and both writers
drop a field with nothing in it. **A ferry is credited too**: the file states its
length, and that figure is Kartverket's geometry whether or not the line is
drawn.

**An inferred connector names no source and no marking bucket.** Nobody drew it,
which is what a connector is, so it is neither a dataset to credit nor ground
anybody was asked about. Its metres are reported under their own name —
*23.1 m on connectors nobody drew* — rather than being folded into `unknown`,
which means asked and unanswered. Measured over the built graph they are 46.6 km
beside the 5,853.3 km of walked network, on 8,684 edges averaging 5.4 m.

**A route with a hole in it is refused rather than written.** A leg still being
worked out, or one the height service refused, would break the track somewhere
that is not a crossing, and nothing in the file would say so. The button says
which and stays disabled.

### An exported file names its sources, and cannot name one licence

Record in `<metadata>` the sources a file actually draws on, each with its
licence. Not in `<copyright>`, which holds exactly one — and a planned route has
no single licence to put there:

| source | licence |
|---|---|
| Turrutebasen | CC0 |
| FKB, N50, and the DTM1 heights | CC BY 4.0 |
| OpenStreetMap | ODbL, share-alike |
| UT.no | CC BY-NC, non-commercial |

ODbL and NC compose badly, and the strictest terms govern the mixture. Filling in
a single `<copyright>` would mean inventing an answer that does not exist.
Listing what is present is both honest and more useful.

It is also not the same for every route. One that runs on FKB and Turrutebasen
alone is unencumbered; one that picks up a kilometre of OSM is not. So compute it
per file and **show it at the download** — *3.2 km OSM (ODbL) · 1.1 km UT.no
(CC BY-NC)* — instead of a blanket warning nobody reads. The reader should know
what they are passing on before they pass it on.

## Licence: in the file, not in the interface

The graph carries OpenStreetMap geometry (ODbL, share-alike) and UT.no tracks
(CC BY-NC, non-commercial). Personal import into Komoot is unproblematic;
publishing routes derived from it is not.

An earlier draft asked for that to be said in the UI or the documentation as
well. **Decided against**: nothing here is published, and the obligations attach
to distribution rather than to use. The mitigation is already in the plan and
sits in the right place — **the exported file is the only thing that leaves the
machine**, and phase 5 puts the sources and their licences into its
`<metadata>` while phase 6 shows the length contributed by each before the
download. The map itself is a local HTML file.

If that ever stops being true — if the map is hosted, or routes derived from it
are published — this is the paragraph to come back to. ODbL's share-alike is
the one with teeth.

# Trail Data Analysis

Exploratory analysis and experimentation with trail data using Jupyter notebooks.

## Overview

This directory contains:
- **Notebooks** - Interactive analysis and visualization
- **Scripts** - One-off analysis tools
- **Cache** - Local data storage (git-ignored)

## Getting Started

### Launch JupyterLab

```bash
command make notebook
```

### Notebooks

- `01_data_exploration.ipynb` - Initial exploration of Norwegian trail data from Geonorge

Each notebook is self-contained and downloads/caches its own data.

### Documents

- `docs/route-planning-decisions.md` — what was decided about the route planning,
  and what was decided against
- `docs/route-planning-phases.md` — the phases it was built in, each with what it
  is accepted against
- `docs/route-planning-review-notes.md` — how every figure in those two was
  arrived at, what this codebase does that will bite, and what to pick up next.
  Start here if you are coming back to this after a while.

### Scripts

**The map** — builds `analysis/output/lomsdal-visten.html` from seven sources,
plus one GPX per source beside it. Every line it draws is a chain out of the
routing graph below, so a drawn line and a selectable track are the same object;
the two scripts share one cached build:

```bash
command make map
```

Everything it downloads is cached, so a second run does not fetch again and takes
about a minute. The first run on an empty cache fetches some 150 MB from Geonorge
and Overpass and takes considerably longer. Re-fetch on purpose with
`--force-download`; `command make cache-clean` throws the cache away entirely,
which is rarely what you want.

Both targets pass `ARGS` through, so `command make map ARGS="--approach-km 10"`
works; the script itself is `analysis/scripts/lomsdal_visten.py`.

Worth knowing:

| | |
|---|---|
| `--output-dir DIR` | write somewhere other than `analysis/output/` |
| `--approach-km N` | how far beyond the park boundary to draw (default 15) |
| `--simplify-m N` | vertex tolerance for what is *drawn*; the GPX keeps full detail |
| `--highlight NAME` | mark every position the place-name register holds for a name |

**There is no way to leave a source out, and that is deliberate.** The `--no-*`
switches and `--fkb-km` were retired in phase 3: the map draws the routing graph,
and a graph missing a source is not smaller but wrong — without the roads the
largest component falls from 79 % of the network to 5 %, without the ferries
eleven of seventeen quays are unreachable. Switch a layer off in the legend
instead; it does the visual job better, per layer, instantly and without a
rebuild. See `docs/route-planning-decisions.md`.

**The routing graph** — builds nothing visible and draws nothing. It reports the
statistics the route planning is verified against: chains per source, edges,
components, how far the network reaches across the park, and whether the coast is
reachable without the ferries. Then what each source's chains carry, and what
every walked edge is told by the ground it runs over — how much of the network is
waymarked, and how much of it runs where no source records a path at all. That
last one reads in one direction only: the sources over-record, so their silence
means something and their lines do not.

```bash
command make graph
```

The built graph is cached under `.cache/objects/` and keyed by everything that
shapes it, so an unchanged rebuild is instant and a changed one is detected
automatically. Force one with `--rebuild`. See `docs/route-planning-phases.md`.

Both scripts build it through `trails.network.norway`, with the same parameters
and therefore the same cache key, so whichever runs first pays and the second is
instant. The parameters the map does not offer fall to that module's defaults
rather than to the map's own, which is what keeps the two agreeing.

### What the map does once it is open

The legend at the bottom left **is** the layer control: every row switches its own
layer and a row whose layer is off is greyed rather than hidden, so it is still
the key to that colour. The base maps sit above the rows.

**Click a line** and the panel at the foot draws its profile — distance against
height, coloured by how steep the ground is, with the ascent, the high and low
point, the steepest stretch and which protected areas it runs through. It is
drawn **true to scale**: one metre is the same number of pixels up as along, so
the angle you see is the angle on the ground. Then:

| | |
|---|---|
| move the pointer over the curve | a reading, and a dot on the map at that exact place |
| turn the wheel over the curve | zoom in, as far as one height reading per pixel — on a long route only, since most lines are already drawn finer than they were measured |
| drag the curve | move the window along; double-click puts the whole line back |
| drag the grip on the panel's top edge | make it taller, which on a steep line is resolution rather than taste |
| *Download GPX* | the line as a file, with a height on every point and no invented time |

**Plan a route** with the button at the top right. Every click on the map places
a waypoint and the way between is worked out over the network; click the route
itself to put a point in the middle, drag a pin to move it. Click the point count
to unfold the list: one row a point, with what it is called and how far into the
walk it comes, draggable to reorder and with its own button to take one out. The
route's own profile is drawn in the same panel and marks each of your points on
it, and *Download GPX* writes it with its waypoints, its legs and the protected
areas it enters and leaves.

**A GPX can be loaded back**, with a choice made before the file is read: take
the track exactly as it is, route afresh between its waypoints, or match it onto
the network wherever a path exists.

### Checking the built page

```bash
command make drive
```

Drives the built map in a browser and reports 48 readings — the counts the page
draws, the profile's scale at several zooms, the wheel, the crosshair's mark, the
point list, and the two panels not covering each other. About a minute, of which
25 seconds is loading 39.6 MB of HTML.

**It does not overlap with `command make test`.** The tests assert on the page's
source; this asks a running browser what the page actually does, which is the
only thing that can tell you whether the drawn angle is right or a control has
gone under another. A red reading is labelled either a broken invariant — a
defect — or a moved figure, which happens legitimately when the sources change.

## Structure

```
analysis/
├── notebooks/          # Jupyter notebooks
├── scripts/            # Analysis scripts
├── docs/               # How the route planning was decided, phased and reviewed
└── README.md           # This file
```

**Note**: Cached data is stored in the repository root `.cache/` directory, shared across all components.

## Note

This is an exploratory workspace. Code here can be messy and experimental. Production code belongs in `libs/src/trails/`.

## Exporting to Production

When analysis code is mature and reusable:
1. Move it to `libs/src/trails/`
2. Add tests in `libs/tests/`
3. Import in notebooks: `from trails.analysis import your_function`

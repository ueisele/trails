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
eleven of seventeen quays are unreachable. Use the layer control instead; it does
the visual job better, per layer, instantly and without a rebuild. See
`docs/route-planning-decisions.md`.

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

## Structure

```
analysis/
├── notebooks/          # Jupyter notebooks
├── scripts/            # Analysis scripts
├── docs/               # Notebook descriptions
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

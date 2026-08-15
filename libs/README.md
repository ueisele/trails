# Trails Library

Reusable Python library for working with hiking trail data.

## Overview

The `trails` package provides modular functionality for:
- **Data sources** (`trails.io.sources`) - Loading trail data from various providers (Geonorge, OpenStreetMap, etc.)
- **Data processing** (`trails.processing`) - Transforming and enriching trail data
- **Analysis** (`trails.analysis`) - Computing metrics and statistics
- **Routing** (`trails.routing`) - Building a routable network from several line datasets
- **Visualization** (`trails.visualization`) - Creating maps and charts
- **Export formats** (`trails.io.export`) - Exporting to GPX, GeoJSON, and other formats
- **Utilities** (`trails.utils`) - Common helper functions

## Installation

From the repository root:

```bash
uv sync
```

## Usage

```python
from trails.io.sources.geonorge import GeonorgeSource
from trails.analysis import describe

# Load trail data
source = GeonorgeSource()
trails = source.fetch_trails()

# Analyze
stats = describe.describe_dataframe(trails)
```

## Structure

```
libs/
├── src/trails/          # Source code
│   ├── io/             # Data loading and export
│   ├── processing/     # Data transformations
│   ├── analysis/       # Metrics and calculations
│   ├── routing/        # Chains and the routing graph
│   ├── visualization/  # Maps and charts
│   └── utils/          # Utility functions
├── tests/              # Tests (mirrors src structure)
├── docs/               # Library documentation
└── README.md           # This file
```

## Testing

Run library tests:

```bash
command make lib-test
```

## Documentation

See `docs/` for detailed API documentation and guides.

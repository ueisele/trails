# GraphHopper Trails Pipeline

Automated pipeline for building GraphHopper routing graphs from Norwegian trail data (Turrutebasen from Geonorge).

## Overview

This pipeline:
1. **Fetches** trail data from Geonorge (Kartverket Turrutebasen)
2. **Validates** data quality (geometry, bounds, completeness)
3. **Transforms** Turrutebasen data to OSM PBF format
4. **Builds** GraphHopper routing graph with elevation data (SRTM ~30m)
5. **Releases** packaged data on GitHub

Runs weekly via GitHub Actions, but only creates releases when data changes.

## Quick Start

### Local Development

```bash
# Install dependencies (from repo root)
uv sync --all-extras

# Run pipeline locally
cd pipeline
uv run python -m graphhopper_pipeline.main --country NO

# Run with dry-run
uv run python -m graphhopper_pipeline.main --country NO --dry-run
```

### GitHub Actions

The pipeline runs automatically:
- **Schedule**: Every Saturday at 6:00 AM UTC
- **Condition**: Only if source data has changed
- **Manual trigger**: `gh workflow run pipeline-build.yml -f country=NO`

## Pipeline Status

| Step | Status | Description |
|------|--------|-------------|
| Fetch | ✅ Implemented | Downloads from Geonorge with caching |
| Validate | ✅ Implemented | Quality checks (geometry, bounds, etc.) |
| Transform | ✅ Implemented | OSM conversion with attribute mapping & inference |
| Build | ✅ Implemented | GraphHopper graph with elevation (SRTM ~30m) |
| Release | ✅ Implemented | GitHub Releases with artifacts & retention |

## Structure

```
pipeline/
├── src/                       # Pipeline implementation
│   └── graphhopper_pipeline/
│       ├── main.py           # CLI entry point
│       ├── config.py         # Configuration loading
│       └── steps/            # Pipeline steps
│           ├── fetch.py      # ✅ Data fetching
│           ├── validate.py   # ✅ Quality checks
│           ├── transform.py  # ✅ OSM conversion
│           ├── build.py      # ✅ Graph building
│           └── release.py    # ✅ GitHub Releases
├── config/                   # TOML configuration
│   ├── pipeline.toml         # Main settings
│   └── countries/
│       └── no.toml           # Norway config
├── tests/                    # Unit tests (93 passing)
│   ├── test_config.py
│   └── steps/
│       ├── test_fetch.py
│       ├── test_validate.py
│       ├── test_transform.py
│       ├── test_build.py
│       └── test_release.py
├── docs/                     # Documentation
│   ├── osm-transformation.md      # Complete OSM guide
│   ├── graphhopper-build-step.md  # GraphHopper build design
│   ├── release-step.md            # GitHub Releases design
│   ├── dtm-integration.md         # Elevation data integration
│   ├── dtm-feasibility-analysis.md # DTM10 vs SRTM cost/benefit
│   └── land-cover-integration.md  # Land cover design
└── README.md                 # This file
```

## Testing

```bash
# All tests (93 passing)
cd pipeline
uv run pytest tests/ -v

# Specific module
uv run pytest tests/test_config.py -v

# With coverage
uv run pytest tests/ --cov=src --cov-report=term-missing
```

## Configuration

### Pipeline Settings (`config/pipeline.toml`)

- Schedule: Saturday 6 AM UTC
- Retry logic: 5 attempts with exponential backoff
- Validation: Max 20% trail count drop allowed
- Retention: Keep last 2 releases

### Country Settings (`config/countries/no.toml`)

- Data source: Geonorge Turrutebasen
- CRS: EPSG:25833 (UTM Zone 33N)
- OSM mappings: 16 trail attributes
- Inference rules: Difficulty from route type

## Documentation

- `docs/osm-transformation.md` - Complete OSM transformation guide
  - Data structure and mapping
  - Inference rules
  - Implementation steps with code examples
  - Many-to-one relationship handling

## Development

```bash
# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/ tests/

# Run all checks
uv run ruff check src/ && uv run ruff format src/ && uv run mypy src/ && uv run pytest tests/
```

## CI/CD

- **CI Workflow** (`../.github/workflows/ci.yml`) - Runs on every push/PR
  - Lints, formats, type checks
  - Runs all tests
  - Checks library, pipeline, and notebooks

- **Pipeline Workflow** (`../.github/workflows/pipeline-build.yml`) - Weekly build
  - Fetches latest data
  - Transforms to OSM
  - Builds GraphHopper graph
  - Creates GitHub Release

## Features

### Elevation Data

The pipeline includes elevation data via SRTM (~30m resolution):
- Automatic download and caching by GraphHopper
- Bilinear interpolation for smooth elevation profiles
- Global coverage (works for all of Norway and beyond)
- Optional: Can be upgraded to Norwegian DTM10 (10m) for higher quality

See `docs/dtm-integration.md` for DTM upgrade guide and `docs/dtm-feasibility-analysis.md` for cost/benefit analysis.

### Surface Tags & Custom Routing (Planned)

The pipeline includes surface tags inferred from Turrutebasen trail types:
- **Current**: Surface tags from Turrutebasen (ground, paved, unpaved, rock)
  - Automatically inferred from trail type (`rutefolger` field)
  - Encoded in GraphHopper graph for routing use
  - Ready for custom routing models
- **Phase 1** (Planned): Custom routing models using existing surface data
  - Seasonal routing (summer vs winter trail preferences)
  - Difficulty-based routing (family-friendly, challenging, etc.)
  - Implementation time: 1-2 hours (configuration only)
- **Phase 2** (Future): ESA WorldCover 10m land cover data
  - Add actual land cover information (forest, grassland, etc.)
  - Enable forest preference, scenic variety routing
  - 11 land cover classes, free and open (CC BY 4.0 license)
  - ~2-3 GB download (feasible in GitHub Actions)

See `docs/land-cover-integration.md` for detailed design.

## Future Enhancements

- [ ] Custom routing models Phase 1: Use existing surface tags for seasonal/difficulty routing
- [ ] Land cover Phase 2: ESA WorldCover 10m integration for forest/terrain preferences
- [ ] Norwegian DTM10 integration (10m resolution, requires self-hosted runner)
- [ ] Multi-country support (Sweden, Denmark, Finland)
- [ ] Incremental updates (delta builds)
- [ ] GraphHopper routing validation tests

## License

MIT License. Data from Kartverket Turrutebasen licensed under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

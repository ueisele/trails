# GraphHopper Data Pipeline

Automated pipeline for preparing trail data for GraphHopper routing engine.

## Overview

This pipeline:
1. Fetches trail data from national sources (Geonorge for Norway)
2. Transforms data to OSM format for GraphHopper
3. Merges with elevation data (DTM) and land cover (AR5)
4. Builds GraphHopper routing graphs
5. Releases graphs to GitHub Releases

## Quick Start

### Local Development

```bash
# Run the pipeline locally
command make pipeline-run-local

# Download latest graph
command make pipeline-download-graph
```

### GitHub Actions

The pipeline runs automatically:
- **Schedule**: Every Saturday at 6:00 AM UTC
- **Condition**: Only if source data has changed
- **Manual**: Can be triggered via GitHub Actions UI

## Structure

```
pipeline/
├── src/                       # Pipeline code
│   └── graphhopper_pipeline/
│       ├── main.py           # Entry point
│       ├── orchestrator.py   # Pipeline orchestration
│       ├── steps/            # Pipeline steps
│       ├── validation/       # Quality checks
│       └── countries/        # Country-specific configs
├── config/                   # TOML configuration
├── scripts/                  # Helper scripts
├── tests/                    # Pipeline tests
├── docs/                     # Pipeline documentation
└── README.md                 # This file
```

## Configuration

See `config/pipeline.toml` for main configuration and `config/countries/` for country-specific settings.

## Documentation

See `docs/` for detailed setup, usage, and troubleshooting guides.

## Testing

```bash
command make pipeline-test
```

# AI Assistant Context for Trails Project

This project analyzes hiking trail data using Jupyter notebooks with modular Python code. Focus on clean, reusable code and self-contained notebooks.

## Tech Stack
- **Package Management**: uv exclusively (no pip, poetry, or conda)
- **Python**: 3.14. `requires-python = ">=3.14"` is the floor and `.python-version` is the
  pin uv actually resolves; ruff's `target-version` and mypy's `python_version` say 3.14 too.
  uv creates `.venv/` and points it at an interpreter it finds — it does not install one
  inside it — and downloads a managed CPython only when nothing on the machine matches.
- **Core Libraries**: pandas, numpy, geopandas, matplotlib, folium
- **Notebooks**: JupyterLab for analysis, PyCharm for development
- **Testing**: pytest
- **Code Quality**: ruff (linting and formatting)

## Project Structure
```
trails/
├── src/trails/          # Reusable Python package
│   ├── io/             # Data loading (GPX, GeoJSON, etc.)
│   ├── processing/     # Data transformations
│   ├── analysis/       # Metrics and calculations
│   ├── visualization/  # Maps and charts
│   └── utils/          # Utility functions
├── notebooks/          # Self-contained analysis notebooks
├── tests/             # Unit tests for src/trails/
└── .cache/            # Data cache (git-ignored)
```

## Key Principles
- **Modular Code**: All reusable logic in `src/trails/`, notebooks only for analysis
- **Self-Contained Notebooks**: Each notebook downloads/caches its own data
- **Data Caching**: Use `.cache/` for downloaded data, never commit data to git
- **Immutable Raw Data**: Never modify cached raw data, create processed versions

## Development Workflow

### Package Management
```bash
# Add dependencies
uv add package-name              # Core dependency
uv add --group jupyter package   # Jupyter-specific
uv add --dev package             # Development tools

# Run commands
uv run jupyter lab               # Start JupyterLab
uv run pytest                    # Run tests
uv run python script.py          # Execute Python scripts
```

### Notebook Conventions
- Import from `trails` package: `from trails.analysis import metrics`
- Download data at start of notebook
- Clear outputs before committing
- Use descriptive names: `01_trail_elevation_analysis.ipynb`
- Document analysis steps with markdown cells

### CRITICAL: Notebook Editing Rules
**ALWAYS check the notebook structure before and after edits:**
1. **Every section header needs a code cell** - Don't create markdown headers without corresponding code
2. **Use NotebookEdit cell_id carefully** - Cell IDs change when you insert/delete cells
3. **Check cell order after edits** - Use `cat notebook.ipynb | python -c ...` to verify structure
4. **Insert cells in correct position** - New cells go AFTER the cell_id specified
5. **Markdown sections should flow logically**:
   - Section 4 → 4.1 → 4.2 → 4.3 → Section 5 (not 4.1 → 5 → 4.2!)
6. **When refactoring sections**:
   - First: List all cells with their types (markdown/code)
   - Second: Plan the changes
   - Third: Execute changes in order
   - Fourth: Verify final structure

**Common mistakes to avoid:**
- Creating subsection headers (4.1, 4.2) without moving/adding corresponding code
- Inserting cells that break the logical flow (e.g., 4.4 appearing after Section 5)
- Forgetting that insert puts the new cell AFTER the specified cell_id
- Not checking if code cells match their section headers

### Code Style
- Type hints for all public functions
- Google-style docstrings
- 150-character line limit (`[tool.ruff] line-length` in pyproject.toml is what `make check` enforces)
- No trailing whitespace
- Use f-strings for formatting

## Data Handling

### Caching Strategy
```python
from trails.data import cache

# Check cache first
if cache.exists(key):
    data = cache.load(key)
else:
    data = download_data()
    cache.save(key, data)
```

### File Formats
- **GPS Data**: GPX, KML, GeoJSON
- **Elevation**: GeoTIFF, DEM files
- **Processed**: Parquet for DataFrames
- **Config**: TOML

## Common Tasks

### Starting New Analysis
1. Create notebook in `notebooks/`
2. Import necessary modules from `trails`
3. Download/cache required data
4. Perform analysis using package functions
5. Save results to `.cache/processed/`

### Adding New Functionality
1. Create module in appropriate `src/trails/` subdirectory
2. Write tests in `tests/`
3. Import and use in notebooks
4. Run `uv run pytest` to verify

### Quality Checks
```bash
command make lint                 # Lint code
command make format               # Format code
command make type                 # Type checking
command make test                 # Run tests
command make check                # Run all checks at once
```

## Important Constraints

### Performance
- Large GPS files (>100MB) should be processed in chunks
- Use geopandas spatial indexing for geometry operations
- Cache expensive computations (elevation matching, route calculations)

### Exploratory Scripts
Ad-hoc scripts that load the routing graph must cap their own memory, so that a
defect raises `MemoryError` with a traceback instead of reaching the kernel's
OOM killer — which kills the terminal, not the script:
```python
import resource
resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3,) * 2)
```
A `timeout` is not a substitute: it bounds seconds, not bytes.

Any loop walking the graph needs an explicit bound and must raise when it is
exceeded. Never index a numpy array with a sentinel — `-1` is a valid index and
silently returns the last element instead of failing.

### Data Sources
- Primary: User-provided GPX files
- External: OpenStreetMap, USGS elevation data
- Weather: Consider API rate limits
- Always validate coordinate systems (prefer WGS84/EPSG:4326)

## Testing Requirements
- Unit tests for all functions in `src/trails/`
- Test data fixtures in `tests/fixtures/`
- Mock external API calls
- Validate GPS parsing with sample files

## PyCharm Integration
- Project uses uv interpreter (auto-detected)
- Enable Jupyter support in settings
- Use scientific mode for debugging notebooks
- Configure code style to match project settings

## Future Enhancements (Not Yet Implemented)
- Interactive maps with Folium
- Elevation profile analysis
- Trail difficulty scoring
- Weather condition integration
- Multi-trail comparison tools
- Export to various formats (KML, GeoJSON)

## Do NOT
- Use pip install (always use uv)
- Commit data files to git
- Modify files in `.cache/`
- Create notebooks without proper documentation
- Write analysis code directly in notebooks (use src/trails/)
- Assume specific data structure without validation
- Run an unbounded `while` loop over graph data
- Index a numpy array with a sentinel value such as `-1`

## Git Workflow
- Branch from main for features
- **ALWAYS run `command make hooks-run` before committing** to ensure all checks pass
- Pre-commit hooks are configured as a last line of defense - they should never fail if you ran `command make hooks-run` first
- To install hooks: `command make hooks-install` (recommended for all developers)
- Clear notebook outputs before committing (handled automatically by pre-commit)
- Update tests when adding features
- Keep commits focused and atomic
- Use descriptive commit messages

## Useful Commands Reference

### Important: Make Command Usage
**ALWAYS use `command make` instead of `make` to avoid function definition file errors.**
When the user asks to run "make", interpret it as "command make".

```bash
# Installation
command make install              # Install default dependencies (core + dev + jupyter)
command make install-core         # Install core dependencies (core)
command make install-dev          # Install only with dev dependencies (core + dev)
command make install-all          # Install all dependencies (core + dev + jupyter)

# Development
command make notebook             # Start JupyterLab
command make notebook-clean       # Clear all notebook outputs

# The map
command make map                  # Build the Lomsdal-Visten map into analysis/output/
command make graph                # Build the routing graph and report its numbers
command make drive                # Drive the built page in a real browser (245 readings, ~185 s)
command make drive ARGS="--only the_plan_bar"   # ...or one check while working on it
command make deploy               # Publish the map make map last built, and purge the edge cache
# map/graph/drive/deploy all take ARGS="...", e.g. make deploy ARGS="--dry-run".
#
# DRIVE ONCE AND READ THE FILE. `make drive` is 180 seconds; running it twice to
# see two parts of one report is 360. Send it to a file and grep the file. And it
# reads the page `make map` last built, so build first or the run reports the
# state before the change.
#
# PUBLISHING IS TWO STEPS AND THE ORDER MATTERS: `command make map`, then the deploy.
# `make deploy` does NOT build. That is deliberate — it is what makes "publish the thing I
# just looked at" possible — so deploying without building first publishes whatever is in
# analysis/output/, however old it is.
#
# And `make deploy` is not the way in. It needs seven settings from the environment and has
# no default for any of them, because nothing identifying the Cloudflare account may be
# committed here: this repository is public. The infrastructure repository holds them and
# drives the deploy; its own `just deploy` reads them out of state, unlocks the credentials
# and calls `make deploy` here. See **Publishing** in analysis/README.md.

# Testing & Quality
command make check                # Run all checks (format check, lint, type, test)
command make lint                 # Check code style with ruff
command make lint-fix             # Auto-fix lint issues with ruff
command make format               # Format code with ruff
command make format-check         # Check if code is properly formatted
command make test                 # Run tests with pytest
command make type                 # Run type checking with mypy

# Dependency Management
command make update               # Update dependencies (respecting version constraints)
command make update-all           # Upgrade all dependencies to latest versions
command make update-package PACKAGE=numpy  # Upgrade specific package

# Test Fixtures
command make fixtures             # Generate/update test fixtures from real data
command make fixtures-info        # Show information about test fixtures
command make fixtures-clean       # Remove all test fixtures

# Utility
command make clean                # Clean up cache files
command make help                 # Show available commands

# Quick aliases
command make fmt                  # Alias for format
command make t                    # Alias for test
command make l                    # Alias for lint
```

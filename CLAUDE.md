# AI Assistant Context for Trails Project

This project analyzes hiking trail data using Jupyter notebooks with modular Python code. Focus on clean, reusable code and self-contained notebooks.

## Tech Stack
- **Package Management**: uv exclusively (no pip, poetry, or conda)
- **Python**: 3.11+ required
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

### Code Style
- Type hints for all public functions
- Google-style docstrings
- 100-character line limit
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
command make test                 # Run tests
command make type                 # Type checking
command make check                # Run all checks at once
```

## Important Constraints

### Performance
- Large GPS files (>100MB) should be processed in chunks
- Use geopandas spatial indexing for geometry operations
- Cache expensive computations (elevation matching, route calculations)

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
command make install              # Install core dependencies
command make install-dev          # Install development dependencies
command make install-all          # Install all dependencies

# Development
command make notebook             # Start JupyterLab

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

# Utility
command make clean                # Clean up cache files
command make help                 # Show available commands

# Quick aliases
command make fmt                  # Alias for format
command make t                    # Alias for test
command make l                    # Alias for lint
```

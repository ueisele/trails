# Project Structure Proposal V3 - Maximum Locality

## Core Principle: Each Component Owns Everything Related to It

Each major component (`lib/`, `pipeline/`, `analysis/`, `app/`) is **self-contained** with its own:
- Source code
- Tests
- Documentation
- Scripts

This makes it crystal clear what belongs where and makes components more independent.

## Proposed Repository Structure

```
trails/                               # Git root
│
├── .github/                          # GitHub workflows (MUST be in root)
│   └── workflows/
│       ├── pipeline.yml
│       ├── tests-lib.yml
│       ├── tests-pipeline.yml
│       └── integration-tests.yml
│
├── lib/                              # SHARED LIBRARY (self-contained)
│   ├── src/
│   │   └── trails/                   # Python package
│   │       ├── __init__.py
│   │       ├── data/                 # Data models
│   │       │   ├── __init__.py
│   │       │   ├── trail.py
│   │       │   └── geometry.py
│   │       ├── sources/              # Data sources
│   │       │   ├── __init__.py
│   │       │   ├── base.py
│   │       │   ├── norway.py
│   │       │   ├── sweden.py
│   │       │   └── osm.py
│   │       ├── formats/              # Format converters
│   │       │   ├── __init__.py
│   │       │   ├── gpx.py
│   │       │   ├── geojson.py
│   │       │   └── osm.py
│   │       ├── analysis/             # Analysis utilities
│   │       │   ├── __init__.py
│   │       │   ├── metrics.py
│   │       │   └── statistics.py
│   │       └── utils/                # Common utilities
│   │           ├── __init__.py
│   │           ├── geo.py
│   │           ├── retry.py
│   │           └── validation.py
│   ├── tests/                        # Library tests (mirrors src structure)
│   │   └── trails/
│   │       ├── data/
│   │       │   ├── test_trail.py
│   │       │   └── test_geometry.py
│   │       ├── sources/
│   │       │   ├── test_base.py
│   │       │   ├── test_norway.py
│   │       │   ├── test_sweden.py
│   │       │   └── test_osm.py
│   │       ├── formats/
│   │       │   ├── test_gpx.py
│   │       │   ├── test_geojson.py
│   │       │   └── test_osm.py
│   │       ├── analysis/
│   │       │   ├── test_metrics.py
│   │       │   └── test_statistics.py
│   │       ├── utils/
│   │       │   ├── test_geo.py
│   │       │   ├── test_retry.py
│   │       │   └── test_validation.py
│   │       └── conftest.py
│   ├── docs/                         # Library documentation
│   │   ├── api/                      # API reference
│   │   │   ├── sources.md
│   │   │   ├── formats.md
│   │   │   └── utils.md
│   │   └── guides/
│   │       ├── adding-country.md
│   │       └── custom-formats.md
│   └── README.md                     # Library overview
│
├── pipeline/                         # DATA PIPELINE (self-contained)
│   ├── src/
│   │   └── graphhopper_pipeline/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── orchestrator.py
│   │       ├── steps/
│   │       │   ├── __init__.py
│   │       │   ├── fetch.py
│   │       │   ├── transform.py
│   │       │   ├── merge.py
│   │       │   ├── build.py
│   │       │   └── release.py
│   │       ├── validation/
│   │       │   ├── __init__.py
│   │       │   ├── quality.py
│   │       │   └── routing.py
│   │       └── countries/
│   │           ├── __init__.py
│   │           ├── registry.py
│   │           ├── norway/
│   │           │   ├── __init__.py
│   │           │   ├── config.py
│   │           │   ├── mapping.py
│   │           │   └── tests.py
│   │           └── sweden/
│   │               └── ...
│   ├── config/                       # Pipeline configuration
│   │   ├── pipeline.toml
│   │   ├── countries/
│   │   │   ├── norway.toml
│   │   │   └── sweden.toml
│   │   └── quality.toml
│   ├── tests/                        # Pipeline tests (mirrors src structure)
│   │   └── graphhopper_pipeline/
│   │       ├── test_main.py
│   │       ├── test_orchestrator.py
│   │       ├── steps/
│   │       │   ├── test_fetch.py
│   │       │   ├── test_transform.py
│   │       │   ├── test_merge.py
│   │       │   ├── test_build.py
│   │       │   └── test_release.py
│   │       ├── validation/
│   │       │   ├── test_quality.py
│   │       │   └── test_routing.py
│   │       ├── countries/
│   │       │   ├── test_registry.py
│   │       │   └── norway/
│   │       │       ├── test_config.py
│   │       │       ├── test_mapping.py
│   │       │       └── test_tests.py
│   │       └── conftest.py
│   ├── scripts/                      # Pipeline scripts
│   │   ├── run-local.sh
│   │   ├── download-graph.sh
│   │   └── install-graphhopper.sh
│   ├── docs/                         # Pipeline documentation
│   │   ├── setup.md
│   │   ├── usage.md
│   │   ├── troubleshooting.md
│   │   ├── architecture.md
│   │   └── adding-country.md
│   └── README.md                     # Pipeline overview
│
├── analysis/                         # ANALYSIS TOOLS (self-contained)
│   ├── notebooks/
│   │   ├── 01_data_exploration.ipynb
│   │   ├── 02_trail_statistics.ipynb
│   │   └── 03_gpx_export.ipynb
│   ├── scripts/                      # Analysis scripts
│   │   ├── compare_sources.py
│   │   └── export-for-outdooractive.sh
│   ├── docs/                         # Analysis documentation
│   │   └── notebooks-guide.md       # What each notebook does
│   ├── .cache/                       # Local cache (git-ignored)
│   └── README.md                     # Analysis overview
│
├── app/                              # TRAIL APP (self-contained, future)
│   ├── backend/
│   │   ├── src/
│   │   ├── config/
│   │   │   └── graphhopper-config.yml
│   │   ├── docker/
│   │   │   └── Dockerfile
│   │   ├── scripts/
│   │   │   ├── start-server.sh
│   │   │   └── update-data.sh
│   │   ├── tests/
│   │   └── README.md
│   ├── frontend/
│   │   ├── src/
│   │   ├── public/
│   │   ├── tests/
│   │   ├── package.json
│   │   └── README.md
│   └── docs/
│       ├── deployment.md
│       └── architecture.md
│
├── docs/                             # ROOT-LEVEL DOCS (cross-cutting)
│   ├── architecture/
│   │   ├── overview.md               # Overall system architecture
│   │   ├── data-flow.md              # How data flows between components
│   │   └── multi-country.md          # Multi-country strategy
│   ├── graphhopper_implementation_proposals.md  # Existing
│   └── norwegian_land_cover_ar5_ar50_guide.md   # Existing
│
├── pyproject.toml                    # ALL Python dependencies
├── Makefile                          # Root-level task runner
├── .env.example
└── README.md                         # Project overview
```

## Benefits of This Structure

### 1. **Maximum Locality**
Everything related to a component lives together:
```
lib/
├── src/       # What it is
├── tests/     # How we verify it
├── docs/      # How to use it
└── README.md  # Quick overview
```

### 2. **Independent Components**
Each component can be:
- Understood independently
- Tested independently
- Documented independently
- Even extracted to separate repo if needed

### 3. **Perfect Mirroring (src ↔ tests)**
Test structure **exactly mirrors** source structure:
- `lib/src/trails/sources/norway.py` → `lib/tests/trails/sources/test_norway.py`
- `pipeline/src/graphhopper_pipeline/steps/fetch.py` → `pipeline/tests/graphhopper_pipeline/steps/test_fetch.py`

**Benefits:**
- Easy to find corresponding tests
- Easy to identify missing tests
- Consistent, predictable structure

### 4. **Scalability**
When adding a new component (e.g., `monitoring/`), the structure is obvious:
```
monitoring/
├── src/
├── tests/
├── scripts/
├── docs/
└── README.md
```

## Component Details

### lib/ - Shared Library

**Purpose:** Reusable code imported by all other components

**Structure:**
- `src/trails/` - Source code (the Python package)
- `tests/` - Library tests
- `docs/` - API reference and guides
- `README.md` - Quick start

**Import path:** `from trails.sources.norway import GeonorgeSource`

**Tests run:** `pytest lib/tests/`

---

### pipeline/ - Data Pipeline

**Purpose:** Production GraphHopper data preparation

**Structure:**
- `src/graphhopper_pipeline/` - Pipeline code
- `config/` - TOML configuration files
- `tests/` - Pipeline tests
- `scripts/` - Pipeline utilities (run-local, download-graph)
- `docs/` - Pipeline documentation
- `README.md` - How to use pipeline

**Run pipeline:** `make pipeline-run` → calls `pipeline/scripts/run-local.sh`

**Tests run:** `pytest pipeline/tests/`

---

### analysis/ - Analysis Tools

**Purpose:** Personal exploration and experimentation

**Structure:**
- `notebooks/` - Jupyter notebooks
- `scripts/` - One-off analysis scripts
- `docs/` - Notebook descriptions
- `.cache/` - Local data cache
- `README.md` - What's in here

**Can be messy:** ✅ Yes - experiments are okay

**Tests:** None needed (exploratory work)

---

### app/ - Trail Application (Future)

**Purpose:** Deployed application (server + frontend)

**Structure:**
- `backend/` - GraphHopper server deployment
  - `src/`, `config/`, `docker/`, `scripts/`, `tests/`
- `frontend/` - Web/PWA/Electron app
  - `src/`, `public/`, `tests/`, `package.json`
- `docs/` - Deployment and architecture docs

**Separate concerns:** Backend and frontend are independent

---

### docs/ - Root-Level Documentation

**Purpose:** Cross-cutting documentation that doesn't belong to one component

**What goes here:**
- Overall architecture
- Data flow between components
- Multi-country strategy
- High-level proposals and guides

**What does NOT go here:**
- Component-specific docs → Goes in component's `docs/`
- API reference → Goes in `lib/docs/api/`
- Pipeline usage → Goes in `pipeline/docs/`

---

## Updated Makefile

```makefile
# Root Makefile - delegates to component-specific tasks

# Library
.PHONY: lib-test
lib-test:
	uv run pytest lib/tests/unit -v

.PHONY: lib-test-integration
lib-test-integration:
	uv run pytest lib/tests/integration -m integration -v

# Pipeline
.PHONY: pipeline-test
pipeline-test:
	uv run pytest pipeline/tests/unit -v

.PHONY: pipeline-test-integration
pipeline-test-integration:
	uv run pytest pipeline/tests/integration -m integration -v

.PHONY: pipeline-run-local
pipeline-run-local:
	@pipeline/scripts/run-local.sh

.PHONY: pipeline-download-graph
pipeline-download-graph:
	@pipeline/scripts/download-graph.sh

# Analysis
.PHONY: analysis-notebook
analysis-notebook:
	uv run jupyter lab analysis/notebooks

# All tests (fast)
.PHONY: test
test: lib-test pipeline-test

# All tests (including slow)
.PHONY: test-all
test-all:
	uv run pytest lib/tests pipeline/tests -v

# Cleanup
.PHONY: clean
clean:
	rm -rf analysis/.cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
```

## pytest Configuration

```toml
# pyproject.toml

[tool.pytest.ini_options]
testpaths = ["lib/tests", "pipeline/tests"]  # Updated paths
markers = [
    "integration: slow integration tests",
]
addopts = "-v -m 'not integration'"
```

## Import Paths

Since we moved to `lib/src/trails/`, we need to configure the package:

```toml
# pyproject.toml

[project]
name = "trails"
version = "0.1.0"

[tool.setuptools.packages.find]
where = ["lib/src"]  # Look in lib/src for packages

[tool.setuptools.package-data]
trails = ["py.typed"]
```

## GitHub Actions Updates

```yaml
# .github/workflows/tests-lib.yml
name: Library Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run library tests
        run: uv run pytest lib/tests/unit -v
```

```yaml
# .github/workflows/tests-pipeline.yml
name: Pipeline Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run pipeline tests
        run: uv run pytest pipeline/tests/unit -v
```

## Migration from V2 to V3

### Changes:

1. **lib/trails/ → lib/src/trails/**
   - Add `src/` layer
   - Update `pyproject.toml` to point to `lib/src`

2. **tests/ → lib/tests/ + pipeline/tests/**
   - Split by component
   - Update pytest paths

3. **scripts/ → pipeline/scripts/ + analysis/scripts/**
   - Move to respective components
   - Update Makefile paths

4. **docs/ split:**
   - Component-specific → component/docs/
   - Cross-cutting → docs/ (root level)

5. **README files:**
   - Add README.md to each component
   - Update root README.md with new structure

## Pros of V3 vs V2

| Aspect | V2 | V3 |
|--------|----|----|
| Locality | Mixed | ✅ Perfect - everything together |
| Independence | Partial | ✅ Full - components self-contained |
| Clarity | Good | ✅ Excellent - obvious where things go |
| Scalability | Good | ✅ Excellent - pattern is clear |
| Navigation | Okay | ✅ Easy - fewer top-level dirs |

## Potential Concerns & Solutions

### Concern 1: "Nested structure seems deeper"

**Response:** Yes, but it's **logical nesting**:
- `lib/src/trails/` - Clear: this is library source code
- `lib/tests/` - Clear: these test the library
- `pipeline/tests/` - Clear: these test the pipeline

Each level adds meaning, not confusion.

### Concern 2: "Import paths are longer"

**Response:** Import paths **don't change**:
```python
# Still works exactly the same:
from trails.sources.norway import GeonorgeSource
```

The `lib/src/` layer is handled by setuptools configuration.

### Concern 3: "More README files to maintain"

**Response:** Each README is **simpler**:
- Root README: Project overview, links to components
- Component README: Just that component's quick start
- Less repetition overall

## Recommendation

**Use V3** - The benefits of locality and clarity outweigh the slightly deeper nesting. This structure will scale much better as the project grows.

Each component is a **clear, self-contained unit** that can be understood, tested, and documented independently.

## Questions

1. Do you prefer V3 (maximum locality) or V2 (flatter structure)?
2. Any concerns about the `lib/src/trails/` nesting?
3. Should we proceed with V3?

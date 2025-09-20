# Trails - Hiking Trail Data Analysis

A Python project for analyzing hiking trail data using Jupyter notebooks, built with modern tools and best practices.

## Project Structure

```
trails/
├── src/trails/          # Python package with reusable modules
│   ├── io/             # Data input/output utilities
│   ├── processing/     # Data processing functions
│   ├── analysis/       # Analysis and metrics
│   ├── visualization/  # Plotting and mapping
│   └── utils/          # Utility functions
├── notebooks/          # Jupyter notebooks for analysis
├── tests/             # Unit tests
└── .cache/            # Local cache for data (git-ignored)
```

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management.

### Prerequisites

1. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Python 3.11 or higher

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd trails
```

2. Install dependencies:
```bash
# Install default dependencies which are core, dev tools and Jupyter support
make install

# Install core dependencies
make install-core

# Install core dependencies with dev tools
make install-dev

# Install all dependencies which are core, dev tools and Jupyter support
make install-all
```

### Running Jupyter Notebooks

Start JupyterLab:
```bash
make notebook
```

### PyCharm Setup

1. Open the project in PyCharm
2. PyCharm should automatically detect the uv environment
3. If not, configure the interpreter:
   - Go to Settings → Project → Python Interpreter
   - Click "Add Interpreter" → "Add Local Interpreter"
   - Select "uv" from the environment types
   - PyCharm will configure everything automatically
4. Mark directories as source roots:
   - Right-click on the `src` folder → "Mark Directory as" → "Sources Root"
   - Right-click on the `tests` folder → "Mark Directory as" → "Test Sources Root"

This tells PyCharm's static analyzer where to find your package code and tests.

### Development

The project follows a modular approach:
- Reusable code lives in `src/trails/`
- Notebooks import from the package and focus on analysis
- Each notebook is self-contained and downloads its own data

Example notebook usage:
```python
from trails.utils.hello import hello_trails
from trails.analysis import metrics  # Future module
from trails.visualization import maps  # Future module

# Your analysis code here
```

### Testing

Run unit tests (default, excludes integration tests):
```bash
make test
```

Run all tests including integration tests:
```bash
make test-all
```

Run only integration tests (requires network access):
```bash
make test-integration
# Note: This will download ~150MB from Geonorge and may take several minutes
```

Run a specific test module:
```bash
uv run pytest tests/trails/io/sources/test_geonorge.py -v
```

Run specific test classes or functions:
```bash
uv run pytest tests/trails/io/sources/test_geonorge.py::TestTrailData -v
```

#### Test Coverage

Run tests with coverage report:
```bash
make test-cov         # Tests with terminal coverage report (excludes integration)
make test-cov-all     # All tests with coverage (includes integration)
make test-cov-html    # Generate HTML coverage report in htmlcov/
```

Quick aliases:
```bash
make tc               # Alias for test-cov
make tch              # Alias for test-cov-html
```

View HTML coverage report:
```bash
make test-cov-html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

#### Integration Tests

Integration tests are marked with `@pytest.mark.integration` and are excluded by default to keep regular test runs fast. These tests:
- Make real network calls to external APIs
- Download actual data files from Geonorge (~150MB)
- Test the complete end-to-end workflow
- Verify real-world compatibility

To run specific test markers:
```bash
# Run only integration tests
uv run pytest -m integration

# Run all except integration tests
uv run pytest -m "not integration"

# Run slow tests
uv run pytest -m slow
```

### Code Quality

Run all checks at once:
```bash
make check       # Run all checks (lint, format check, type, test)
```

Or run individual checks:
```bash
make lint        # Check code style with ruff
make format      # Format code with ruff
make fix         # Auto-fix lint issues
make type        # Type checking with mypy (includes notebooks)
make test        # Run tests with pytest
```

Utility commands:
```bash
make clean       # Clean cache and temporary files
make help        # Show all available commands
```

Quick aliases:
```bash
make fmt         # Alias for format
make t           # Alias for test
make l           # Alias for lint
```

## Getting Started

1. Open `notebooks/01_hello_world.ipynb` to verify your setup
2. The notebook will test that all dependencies are working
3. Start creating your own analysis notebooks!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

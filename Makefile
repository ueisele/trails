# This Makefile runs with this project's own toolchain in front of whatever the caller had.
#
# The deploy needs the AWS CLI — analysis/scripts/deploy_map.py shells out to `aws s3 cp` — and it is
# declared in mise.toml here. A caller that reached this file by cd-ing in from another repository
# carries the PATH of wherever *its* shell was activated: mise sets that at the prompt, and a `cd`
# inside a script does not re-run the hook. `just deploy` in home/trails-map is exactly that shape,
# and it failed with the script's own "aws (the AWS CLI) is not installed" while the tool sat
# installed a directory away.
#
# Put here rather than in the caller, because the caller has no business knowing how this repository
# finds its tools — and every other caller would have needed the same knowledge. Put at the top
# rather than in the deploy recipe alone, because the next tool this project declares would
# otherwise arrive with the same bug.
#
# Guarded so it stays a no-op where mise is absent: CI installs uv directly and runs `make check`
# without ever seeing mise, and that has to keep working.
MISE := $(shell command -v mise 2>/dev/null)
ifneq ($(MISE),)
export PATH := $(shell $(MISE) bin-paths | tr '\n' ':')$(PATH)
endif

.PHONY: help check format lint test test-all test-integration test-cov test-cov-all test-cov-html type clean cache-clean cache-clean-all install install-core install-dev install-all hooks-install hooks-uninstall hooks-run update update-all update-package notebook-clean fixtures fixtures-info fixtures-clean map graph drive deploy

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       Install default dependencies"
	@echo "  make install-core  Install core dependencies"
	@echo "  make install-dev   Install core with development dependencies"
	@echo "  make install-all   Install all dependencies"
	@echo "  make check         Run all checks (lint, format check, type, test)"
	@echo "  make format        Format code with ruff"
	@echo "  make lint          Check code style with ruff"
	@echo "  make lint-fix      Auto-fix lint issues with ruff"
	@echo "  make test          Run tests with pytest (excludes integration tests)"
	@echo "  make test-all      Run all tests including integration tests"
	@echo "  make test-integration Run only integration tests (requires network)"
	@echo "  make test-cov      Run tests with coverage report (excludes integration)"
	@echo "  make test-cov-all  Run all tests with coverage report"
	@echo "  make test-cov-html Generate HTML coverage report"
	@echo "  make type          Run type checking with mypy"
	@echo "  make clean         Clean up cache files (build artifacts, temp files)"
	@echo "  make cache-clean   Clean .cache directory contents (preserve directory)"
	@echo "  make cache-clean-all Remove entire .cache directory"
	@echo "  make notebook      Start JupyterLab"
	@echo "  make notebook-clean Clear all notebook outputs"
	@echo "  make map           Build the Lomsdal-Visten map into analysis/output/"
	@echo "  make graph         Build the Lomsdal-Visten routing graph and report it"
	@echo "                     both take ARGS=\"...\", e.g. make map ARGS=\"--approach-km 10\""
	@echo "  make deploy        Publish the built map and purge the edge (needs .env)"
	@echo "  make fixtures      Generate/update test fixtures from real data"
	@echo "  make fixtures-info Show information about test fixtures"
	@echo "  make fixtures-clean Remove all test fixtures"
	@echo "  make update        Update dependencies (respecting version constraints)"
	@echo "  make update-all    Upgrade all dependencies to latest versions"
	@echo "  make update-package PACKAGE=<name> Upgrade specific package to latest version"
	@echo "  make hooks-install Install git pre-commit hooks"
	@echo "  make hooks-uninstall Remove git pre-commit hooks"
	@echo "  make hooks-run     Run pre-commit hooks manually"

# Installation targets
install:
	uv sync

install-core:
	uv sync --no-default-groups

install-dev:
	uv sync --only-dev

install-all:
	uv sync --all-groups

# Main check command - runs everything
check: format-check lint type test
	@echo "✅ All checks passed!"

# Individual check commands
format:
	@echo "📝 Formatting code..."
	uv run ruff format libs/src/ libs/tests/ pipeline/src/ pipeline/tests/ analysis/scripts/ analysis/notebooks/

format-check:
	@echo "🔍 Checking code formatting..."
	uv run ruff format --check libs/src/ libs/tests/ pipeline/src/ pipeline/tests/ analysis/scripts/ analysis/notebooks/
	@echo "✅ Format check passed"

lint:
	@echo "🔍 Checking code style..."
	uv run ruff check libs/src/ libs/tests/ pipeline/src/ pipeline/tests/ analysis/scripts/ analysis/notebooks/
	@echo "✅ Lint check passed"

lint-fix:
	@echo "🔧 Auto-fixing lint issues..."
	uv run ruff check libs/src/ libs/tests/ pipeline/src/ pipeline/tests/ analysis/scripts/ analysis/notebooks/ --fix
	@echo "✅ Lint issues fixed"

test:
	@echo "🧪 Running tests (excluding integration)..."
	uv run pytest libs/tests/ -v -m "not integration"
	# Separate run: both trees have a package called "tests", so pytest cannot
	# import them in one session.
	uv run pytest pipeline/tests/ -v -m "not integration"
	@echo "✅ Tests passed"

test-all:
	@echo "🧪 Running all tests (including integration)..."
	uv run pytest libs/tests/ -v
	uv run pytest pipeline/tests/ -v
	@echo "✅ All tests passed"

test-integration:
	@echo "🌐 Running integration tests (requires network)..."
	@echo "⚠️  This will download ~150MB from Geonorge and may take several minutes"
	uv run pytest libs/tests/ -v -m integration
	@echo "✅ Integration tests passed"

test-cov:
	@echo "📊 Running tests with coverage (excluding integration)..."
	uv run pytest libs/tests/ -v -m "not integration" --cov=trails --cov-report=term-missing
	@echo "✅ Coverage report generated"

test-cov-all:
	@echo "📊 Running all tests with coverage (including integration)..."
	uv run pytest libs/tests/ -v --cov=trails --cov-report=term-missing
	@echo "✅ Full coverage report generated"

test-cov-html:
	@echo "📊 Generating HTML coverage report..."
	uv run pytest libs/tests/ -v -m "not integration" --cov=trails --cov-report=html --cov-report=term
	@echo "✅ HTML coverage report generated in htmlcov/"
	@echo "   Open htmlcov/index.html in your browser to view"

type:
	@echo "🔎 Type checking..."
	uv run mypy libs/src/ libs/tests/fixture_generators/ pipeline/src/ analysis/scripts/
	uv run nbqa mypy analysis/notebooks/
	@echo "✅ Type check passed"

# Utility commands
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name ".coverage.*" -delete 2>/dev/null || true
	@echo "✨ Clean complete"

notebook:
	@echo "🚀 Starting JupyterLab..."
	uv run --with jupyter jupyter lab

notebook-clean:
	@echo "🧹 Clearing notebook outputs..."
	@find analysis/notebooks -name "*.ipynb" -exec uv run nbstripout {} \;
	@echo "✅ Notebook outputs cleared"

# Both scripts are written for one park, which is why these targets need no
# argument to say which. If a second one is ever added, the scripts grow a --park
# option first and these follow it; naming them for the park before that would be
# noise on every invocation.
map:
	@echo "🗺️  Building the Lomsdal-Visten map (cached sources; a cold cache takes far longer)..."
	uv run python analysis/scripts/lomsdal_visten.py $(ARGS)
	@echo "✅ analysis/output/lomsdal-visten.html"

graph:
	@echo "🕸️  Building the Lomsdal-Visten routing graph..."
	uv run python analysis/scripts/route_graph.py $(ARGS)

# Publishes whatever `make map` last built — it does not build. That separation is deliberate: a
# deploy that rebuilds would make "publish the thing I just looked at" impossible, and the thing you
# just looked at is the only one worth publishing. Where it goes is not in this repository; see
# .env.example.
deploy:
	@echo "🚀 Publishing the built map..."
	uv run python analysis/scripts/deploy_map.py $(ARGS)

drive:
	@echo "🖱️  Driving the built map in a browser (about a minute; 25 s of it is the page loading)..."
	uv run --with playwright python analysis/scripts/drive_map.py $(ARGS)

cache-clean:
	@echo "🗑️  Cleaning cache directory (.cache)..."
	@if [ -d .cache ]; then \
		rm -rf .cache/*; \
		echo "✅ Cache cleaned (directory preserved)"; \
	else \
		echo "ℹ️  No cache directory found"; \
	fi

cache-clean-all:
	@echo "🗑️  Removing entire cache directory..."
	@if [ -d .cache ]; then \
		rm -rf .cache; \
		echo "✅ Cache directory removed"; \
	else \
		echo "ℹ️  No cache directory found"; \
	fi

# Dependency management
update:
	@echo "🔄 Updating dependencies (respecting version constraints)..."
	uv lock
	uv sync
	@echo "✅ Dependencies updated"

update-all:
	@echo "⬆️  Upgrading all dependencies to latest versions..."
	uv lock --upgrade
	uv sync
	@echo "✅ All dependencies upgraded to latest versions"

update-package:
	@if [ -z "$(PACKAGE)" ]; then \
		echo "❌ Please specify a package: make update-package PACKAGE=<name>"; \
		exit 1; \
	fi
	@echo "📦 Upgrading $(PACKAGE) to latest version..."
	uv lock --upgrade-package $(PACKAGE)
	uv sync
	@echo "✅ $(PACKAGE) upgraded to latest version"

# Git hooks management with pre-commit
hooks-install:
	@echo "🔧 Installing pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed! They will run automatically before each commit."
	@echo "   To run hooks manually, use: make hooks-run"

hooks-uninstall:
	@echo "🗑️  Removing pre-commit hooks..."
	uv run pre-commit uninstall
	@echo "✅ Pre-commit hooks removed"

hooks-run:
	@echo "🚀 Running pre-commit hooks..."
	uv run pre-commit run --all-files

# Test fixture management
fixtures:  ## Generate/update test fixtures from real data sources
	@echo "=================================="
	@echo "Generating Test Fixtures"
	@echo "=================================="
	@# Run fixture generation modules
	@echo "→ Generating Geonorge Turrutebasen fixtures..."
	uv run python -m lib.tests.fixture_generators.trails.io.sources.geonorge
	@# Add more fixture generators here as they are created:
	@# uv run python -m lib.tests.fixture_generators.trails.io.sources.other_source
	@echo ""
	@echo "✓ All fixtures generated successfully!"

fixtures-info:  ## Show information about test fixtures
	@echo "Test Fixtures Status:"
	@echo "===================="
	@echo ""
	@echo "Expected fixture files:"
	@echo "  • libs/tests/fixtures/trails/io/sources/geonorge/turrutebasen_minimal.zip"
	@echo "  • libs/tests/fixtures/trails/io/sources/geonorge/turrutebasen_atom_feed.xml"
	@echo ""
	@echo "Current status:"
	@for file in \
		libs/tests/fixtures/trails/io/sources/geonorge/turrutebasen_minimal.zip \
		libs/tests/fixtures/trails/io/sources/geonorge/turrutebasen_atom_feed.xml; do \
		if [ -f "$$file" ]; then \
			size=$$(du -h "$$file" | cut -f1); \
			echo "  ✓ $$file ($$size)"; \
		else \
			echo "  ✗ $$file (missing)"; \
		fi \
	done
	@echo ""
	@echo "Run 'make fixtures' to generate missing fixtures."

fixtures-clean:  ## Remove all test fixtures
	@echo "🗑️  Removing test fixtures..."
	rm -rf libs/tests/fixtures/trails/io/sources/geonorge/
	@echo "✅ Test fixtures removed."

# Quick commands for development
fmt: format
t: test
l: lint
tc: test-cov
tch: test-cov-html

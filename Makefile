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

.PHONY: help check format lint test test-all test-integration test-cov test-cov-all test-cov-html type clean cache-clean cache-clean-all install install-core install-dev install-all hooks-install hooks-uninstall hooks-run update update-all update-package notebook-clean fixtures fixtures-info fixtures-clean map graph drive drive-both deploy tiles dem shade slope nmd vegetation abisko lomsdal-visten

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
	@echo "  make map           Build a map into analysis/output/: Lomsdal-Visten, or Abisko with --park abisko"
	@echo "  make graph         Build a park's routing graph and report it (--park likewise)"
	@echo "                     both take ARGS=\"...\", e.g. make map ARGS=\"--approach-km 10\""
	@echo "  make tiles         Copy the Abisko base-map tiles out of Lantmäteriet's open download"
	@echo "  make dem           Build a map's height tiles; make shade its relief, make slope its steepness"
	@echo "                     all three take PARK=<map> (default lomsdal-visten) and are resumable"
	@echo "  make abisko        The whole Abisko chain: tiles, dem, shade, slope, graph, map (needs the Geotorget login)"
	@echo "  make lomsdal-visten  The whole Lomsdal-Visten chain: dem, shade, slope, graph, map (no login)"
	@echo "  make drive         Drive one built page in a browser: ARGS=\"--page analysis/output/abisko.html\""
	@echo "                     ARGS=\"--only <word>,<word>\" runs just those checks, which is seconds not minutes"
	@echo "  make drive-both    Drive both pages at once; ARGS goes to both"
	@echo "  make deploy        Publish the built map and purge the edge (needs .env)"
	@echo "                     ARGS=\"--tree tiles\" mirrors a tile tree instead; --tree dem the heights"
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

# Both scripts take --park (lomsdal-visten by default), so `make map ARGS="--park abisko"`
# and `make graph ARGS="--park abisko"` are the second map and no target is named for a
# park. The Swedish build reads the Topografi 50 delivery and the height mosaic off the
# cache (`make dem` puts the mosaic there); only a cold cache needs the Geotorget login.
map:
	@echo "🗺️  Building the map (cached sources; a cold cache takes far longer)..."
	uv run python analysis/scripts/lomsdal_visten.py $(ARGS)
	@echo "✅ analysis/output/<park>.html"

graph:
	@echo "🕸️  Building the routing graph..."
	uv run python analysis/scripts/route_graph.py $(ARGS)

# Publishes whatever `make map` last built — it does not build. That separation is deliberate: a
# deploy that rebuilds would make "publish the thing I just looked at" impossible, and the thing you
# just looked at is the only one worth publishing. Where it goes is not in this repository; see
# .env.example.
deploy:
	@echo "🚀 Publishing the built map..."
	uv run python analysis/scripts/deploy_map.py $(ARGS)

# Reads a 156 GB GeoPackage over FTP by byte range and writes only the box's tiles — about a
# quarter of an hour for all of z8–z17, and it resumes, so stopping it costs nothing. A new stand of
# the file on the server goes into the next version directory and the next `map` draws it; an
# unchanged stand is a no-op. Like `map` it only builds; `make deploy ARGS="--tree tiles"` is what
# uploads. See analysis/docs/abisko-decisions.md §3 and §9.20.
tiles:
	@echo "🧩 Copying Lantmäteriet's tiles for the Abisko box (resumable)..."
	uv run python analysis/scripts/lantmateriet_tiles.py $(ARGS)

# **Which map the three tile trees are cut for.** `dem`, `shade` and `slope` all cut from one height
# model over one box, and which model and which box that is, is named per map in
# `trails.processing.trees.TREES` — so they take PARK the way `map` and `graph` take `--park`, and
# default to the same map those two default to. The two chains below set it; nothing else needs to.
PARK ?= lomsdal-visten

# Reads the height model over the map's box — Lantmäteriet's 1 m squares by range request with the
# Geotorget login (GEOTORGET_USERNAME/PASSWORD in the environment; run it under sops exec-env from
# home/trails-map), or Kartverket's national model off hoydedata.no's image service, which needs no
# login at all — caches the mosaic and cuts z8–z13 height tiles. Resumable; the deploy uploads with
# --tree dem. See analysis/docs/abisko-decisions.md §6.3 and §6.10.
dem:
	@echo "⛰️  Building the $(PARK) height tiles (resumable)..."
	uv run python analysis/scripts/dem_tiles.py --park $(PARK) $(ARGS)

# Cuts the relief shadow the page draws under the contours from the same cached mosaic the height
# tiles come from, z8-z15. Needs no login once `make dem` has cached the mosaic, and none at all for
# Norway. Resumable; the deploy uploads with --tree shade. See analysis/docs/abisko-decisions.md
# §6.6 and §6.10.
shade:
	@echo "🌄 Building the $(PARK) hillshade tiles (resumable)..."
	uv run python analysis/scripts/shade_tiles.py --park $(PARK) $(ARGS)

# Colours how steep the ground is, in the SLF's classes with one of our own below them, from the
# same cached mosaic, z8-z15, cut exactly as the relief is. Needs no login once `make dem` has
# cached the mosaic, and none at all for Norway. Resumable; the deploy uploads with --tree slope.
# See analysis/docs/abisko-decisions.md §6.7 and §6.10.
slope:
	@echo "📐 Building the $(PARK) slope-class tiles (resumable)..."
	uv run python analysis/scripts/slope_tiles.py --park $(PARK) $(ARGS)

# Fetches Naturvårdsverket's NMD 2018 object rasters -- 5.8 GB of zips, 10 GB each unpacked -- and
# converts them once into .cache/vegetation/nmd2018/ as deflated GeoTIFFs, after which every Swedish
# box is a window read. `make vegetation PARK=abisko` does this itself if it finds them missing; this
# target does it ahead of time, and is safe to run again. See analysis/docs/abisko-decisions.md §6.11.
nmd:
	@echo "🌿 Fetching and converting NMD 2018 into the cache (resumable)..."
	uv run python analysis/scripts/nmd_convert.py $(ARGS)

# Colours how much stands between knee and head height in six steps, and where trees over 5 m are,
# as two trees off the laser survey: NMD 2018's classes for Sweden, Kartverket's surface model less
# its terrain model for Norway, z8-z15, both without a login. Resumable; the deploy uploads with
# --tree vegetation --tree forest. See analysis/docs/abisko-decisions.md §6.11.
vegetation:
	@echo "🌿 Building the $(PARK) vegetation and forest tiles (resumable)..."
	uv run python analysis/scripts/vegetation_tiles.py --park $(PARK) $(ARGS)

# The whole Abisko chain in one run, in the order the pieces depend on each other: the base-map
# tiles off the FTP, the height mosaic and tiles with the login, the hillshade and the slope classes
# off the same mosaic,
# then the graph (Topografi 50 through
# the delivery API with the login and the order id, Naturvårdsverket's nightly files, OSM through
# Overpass -- fetched once each and cached) and its report, then the page. Every step is resumable
# or cached, so a second run is a few minutes of checking and a rebuild of the page. It builds and
# does not publish: `just deploy --map abisko --tree tiles --tree dem --tree shade --tree slope` from
# home/trails-map is that, and `just abisko` there is this target with the login supplied.
abisko:
	$(MAKE) tiles PARK=abisko
	$(MAKE) dem shade slope vegetation PARK=abisko
	@echo "🕸️  Building and reporting the Abisko routing graph..."
	uv run python analysis/scripts/route_graph.py --park abisko
	@echo "🗺️  Building the Abisko map..."
	uv run python analysis/scripts/lomsdal_visten.py --park abisko
	@echo "✅ analysis/output/abisko.html — publish with: just deploy --map abisko --tree tiles --tree dem --tree shade --tree slope --tree vegetation --tree forest (from home/trails-map)"

# The whole Lomsdal-Visten chain, in the same order and with the same properties: the height model
# off hoydedata.no (no login, no order), the heights, the relief and the slope classes off the one
# cached mosaic, the vegetation and forest off its surface model (§6.11), then the graph and the page. There is no `tiles` step here — Kartverket serves its
# own sheet and we copy none of it — and nothing in this chain needs a credential, which is the one
# way it differs from `abisko`. See analysis/docs/abisko-decisions.md §6.10.
lomsdal-visten:
	$(MAKE) dem shade slope vegetation PARK=lomsdal-visten
	@echo "🕸️  Building and reporting the Lomsdal-Visten routing graph..."
	uv run python analysis/scripts/route_graph.py --park lomsdal-visten
	@echo "🗺️  Building the Lomsdal-Visten map..."
	uv run python analysis/scripts/lomsdal_visten.py --park lomsdal-visten
	@echo "✅ analysis/output/lomsdal-visten.html — publish with: just deploy --tree dem --tree shade --tree slope --tree vegetation --tree forest (from home/trails-map)"

# **Pinned, because the browser is not.** `--with playwright` takes the newest release, and each
# one wants a Firefox build of its own: the newest asks for `firefox-1543` and dies with
# "Executable doesn't exist", which reads like a missing browser rather than a version skew. The box
# holds `firefox-1538`, which is 1.62.0's. When the browser cache is refreshed, print
# `p.firefox.executable_path` under a few releases and move this to the one that matches.
drive:
	@echo "🖱️  Driving the built map in a browser (about eight minutes a page)..."
	uv run --with "playwright==1.62.0" python -u analysis/scripts/drive_map.py $(ARGS)

# **Both pages at once, which they may be since no reading is a wall clock.** A run
# owns its browser and serves the page on a port the kernel picks, so two of them
# share nothing but the machine -- and the machine has eight cores against one
# Firefox apiece. What used to forbid this was the suite itself: four readings
# compared elapsed seconds against figures recorded on an idle box, so two runs
# at once reported the contention as a change in the page. Those are printed and
# no longer compared, and what is claimed about a timeout is counted instead.
#
# `-u` because the output is buffered the moment it is not a terminal, and a log
# that arrives only at the end reads exactly like a run that has hung.
drive-both:
	@echo "🖱️  Driving both pages at once..."
	@uv run --with "playwright==1.62.0" python -u analysis/scripts/drive_map.py \
		--page analysis/output/lomsdal-visten.html $(ARGS) > /tmp/drive-lomsdal-visten.txt 2>&1 & \
	 lomsdal=$$!; \
	 uv run --with "playwright==1.62.0" python -u analysis/scripts/drive_map.py \
		--page analysis/output/abisko.html $(ARGS) > /tmp/drive-abisko.txt 2>&1 & \
	 abisko=$$!; \
	 wait $$lomsdal; lomsdal_said=$$?; \
	 wait $$abisko; abisko_said=$$?; \
	 cat /tmp/drive-lomsdal-visten.txt /tmp/drive-abisko.txt; \
	 exit $$((lomsdal_said + abisko_said))

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

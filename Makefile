.PHONY: help check format lint test type clean install install-dev install-all hooks-install hooks-uninstall hooks-run update update-all update-package

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       Install core dependencies"
	@echo "  make install-dev   Install development dependencies"
	@echo "  make install-all   Install all dependencies"
	@echo "  make check         Run all checks (lint, format check, type, test)"
	@echo "  make format        Format code with ruff"
	@echo "  make lint          Check code style with ruff"
	@echo "  make lint-fix      Auto-fix lint issues with ruff"
	@echo "  make test          Run tests with pytest"
	@echo "  make type          Run type checking with mypy"
	@echo "  make clean         Clean up cache files"
	@echo "  make notebook      Start JupyterLab"
	@echo "  make update        Update dependencies (respecting version constraints)"
	@echo "  make update-all    Upgrade all dependencies to latest versions"
	@echo "  make update-package PACKAGE=<name> Upgrade specific package to latest version"
	@echo "  make hooks-install Install git pre-commit hooks"
	@echo "  make hooks-uninstall Remove git pre-commit hooks"
	@echo "  make hooks-run     Run pre-commit hooks manually"

# Installation targets
install:
	uv sync

install-dev:
	uv sync --group dev

install-all:
	uv sync --all-groups

# Main check command - runs everything
check: format-check lint type test
	@echo "✅ All checks passed!"

# Individual check commands
format:
	@echo "📝 Formatting code..."
	uv run ruff format src/ tests/ notebooks/

format-check:
	@echo "🔍 Checking code formatting..."
	uv run ruff format --check src/ tests/ notebooks/
	@echo "✅ Format check passed"

lint:
	@echo "🔍 Checking code style..."
	uv run ruff check src/ tests/ notebooks/
	@echo "✅ Lint check passed"

lint-fix:
	@echo "🔧 Auto-fixing lint issues..."
	uv run ruff check src/ tests/ notebooks/ --fix
	@echo "✅ Lint issues fixed"

test:
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v
	@echo "✅ Tests passed"

type:
	@echo "🔎 Type checking..."
	uv run mypy src/
	uv run nbqa mypy notebooks/
	@echo "✅ Type check passed"

# Utility commands
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✨ Clean complete"

notebook:
	@echo "🚀 Starting JupyterLab..."
	uv run --with jupyter jupyter lab

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

# Quick commands for development
fmt: format
t: test
l: lint

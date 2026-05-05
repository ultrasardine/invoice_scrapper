# Invoice Scrapper - Makefile
# ============================
# Commands for development, testing, packaging, and running the application.

APP_NAME     := InvoiceScrapper
APP_VERSION  := 0.1.0
BUNDLE_ID    := com.invoicescrapper.app

.PHONY: help install install-dev clean test test-verbose test-coverage \
        lint format format-check run version check-deps update-deps \
        check-tesseract ci-test ci-lint ci \
        pack-macos pack-windows pack-linux

.DEFAULT_GOAL := help

# ============================================================================
# HELP
# ============================================================================

help: ## Show this help message
	@echo "Invoice Scrapper - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; section=""} \
		/^## / { section=substr($$0, 4); printf "\n\033[1m%s\033[0m\n", section } \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ============================================================================
## Setup
# ============================================================================

install: ## Install production dependencies
	uv sync --no-dev

install-dev: ## Install all dependencies including dev tools
	uv sync --all-extras

check-deps: ## Check for outdated dependencies
	uv pip list --outdated

update-deps: ## Update all dependencies to latest versions
	uv lock --upgrade
	uv sync --all-extras

check-tesseract: ## Verify Tesseract OCR is installed with Portuguese data
	@tesseract --version > /dev/null 2>&1 || \
		(echo "Tesseract not found. Install: brew install tesseract tesseract-lang" && exit 1)
	@tesseract --list-langs 2>&1 | grep -q por || \
		(echo "Portuguese lang data missing. Install: brew install tesseract-lang" && exit 1)
	@echo "Tesseract OK (with Portuguese support)"

# ============================================================================
## Development
# ============================================================================

lint: ## Run linting checks (ruff)
	uv run ruff check invoice_scrapper tests

format: ## Format code (ruff)
	uv run ruff format invoice_scrapper tests

format-check: ## Check formatting without changes
	uv run ruff format --check invoice_scrapper tests

# ============================================================================
## Testing
# ============================================================================

test: ## Run all tests
	uv run pytest tests/ -v

test-verbose: ## Run tests with stdout visible
	uv run pytest tests/ -v -s

test-coverage: ## Run tests with coverage report
	uv run pytest tests/ -v --cov=invoice_scrapper --cov-report=term-missing

# ============================================================================
## Application
# ============================================================================

run: ## Launch the desktop app
	uv run python main.py

version: ## Show current package version
	@uv run python -c "from invoice_scrapper import __version__; print(__version__)"

# ============================================================================
## Packaging (standalone desktop apps via flet pack + PyInstaller)
# ============================================================================
# Produces self-contained executables bundling Python, all dependencies,
# Tesseract OCR binary, and Portuguese/English language data.
#
# Each target MUST be run on its target OS (PyInstaller limitation).
# Cross-platform builds require CI (GitHub Actions, AppVeyor, etc).
#
# Prerequisites on the build machine:
#   - uv sync --all-extras  (installs pyinstaller + all deps)
#   - Tesseract OCR installed (brew install tesseract tesseract-lang)

# --- Locate Tesseract paths at build time ---
TESS_BIN     = $(shell which tesseract 2>/dev/null)
UNAME_S      := $(shell uname -s 2>/dev/null)

ifeq ($(UNAME_S),Darwin)
  TESSDATA_DIR = $(shell dirname $$(find /opt/homebrew/share /usr/local/share -name "por.traineddata" -print -quit 2>/dev/null) 2>/dev/null)
  SEP          = :
else ifeq ($(UNAME_S),Linux)
  TESSDATA_DIR = $(shell dirname $$(find /usr -name "por.traineddata" -print -quit 2>/dev/null) 2>/dev/null)
  SEP          = :
else
  # Windows (Git Bash / MSYS2)
  TESSDATA_DIR = $(subst \,/,$(PROGRAMFILES))/Tesseract-OCR/tessdata
  SEP          = ;
endif

PACK_BASE = uv run flet pack main.py \
	-n $(APP_NAME) \
	--product-name "Invoice Scrapper" \
	--product-version $(APP_VERSION) \
	--bundle-id $(BUNDLE_ID) \
	--add-data "invoice_scrapper$(SEP)invoice_scrapper" \
	--add-binary "$(TESS_BIN)$(SEP)." \
	--add-data "$(TESSDATA_DIR)/por.traineddata$(SEP)tessdata" \
	--add-data "$(TESSDATA_DIR)/eng.traineddata$(SEP)tessdata" \
	--hidden-import invoice_scrapper \
	--hidden-import invoice_scrapper.bundle_paths \
	--hidden-import invoice_scrapper.ui.app \
	--hidden-import invoice_scrapper.config \
	--hidden-import invoice_scrapper.models \
	--hidden-import invoice_scrapper.pdf_reader \
	--hidden-import invoice_scrapper.table_detector \
	--hidden-import invoice_scrapper.field_extractor \
	--hidden-import invoice_scrapper.invoice_processor \
	--hidden-import invoice_scrapper.excel_writer

pack-macos: check-tesseract ## Package standalone macOS .app (run on macOS only)
ifneq ($(UNAME_S),Darwin)
	$(error pack-macos must be run on macOS. Use CI for cross-platform builds.)
endif
	$(PACK_BASE) --distpath dist/macos
	@echo ""
	@echo "Built: dist/macos/$(APP_NAME).app"
	@echo "Run:   open dist/macos/$(APP_NAME).app"

pack-windows: check-tesseract ## Package standalone Windows .exe (run on Windows with make/MSYS2)
ifneq (,$(filter Linux Darwin,$(UNAME_S)))
	$(error pack-windows must be run on Windows. Use CI for cross-platform builds.)
endif
	$(PACK_BASE) \
		--distpath dist/windows \
		--company-name "Invoice Scrapper"
	@echo ""
	@echo "Built: dist\windows\$(APP_NAME).exe"

pack-linux: check-tesseract ## Package standalone Linux binary (run on Linux only)
ifneq ($(UNAME_S),Linux)
	$(error pack-linux must be run on Linux. Use CI for cross-platform builds.)
endif
	$(PACK_BASE) --distpath dist/linux
	@echo ""
	@echo "Built: dist/linux/$(APP_NAME)"

# ============================================================================
## Clean
# ============================================================================

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info/ *.spec
	rm -rf .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ============================================================================
## CI
# ============================================================================

ci-test: ## Run tests for CI (strict, short tracebacks)
	uv run pytest tests/ -v --tb=short

ci-lint: ## Run all lint checks for CI
	uv run ruff check invoice_scrapper tests
	uv run ruff format --check invoice_scrapper tests

ci: ci-lint ci-test ## Run full CI pipeline (lint + test)

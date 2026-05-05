# AGENTS.md — Invoice Scrapper

## Project Overview

Desktop app (Flet + PyInstaller) that extracts data from Portuguese PDF invoices and writes one-row-per-line-item Excel output. Designed for varied supplier layouts; handles both digital PDFs and scanned/image-based invoices.

## Architecture & Data Flow

```
PDF → pdf_reader.py (Word positions) → field_extractor.py + table_detector.py → invoice_processor.py → InvoiceData → excel_writer.py → .xlsx
```

- **`Word`** (from `pdf_reader.py`) is the core primitive — every extractor and detector works on `list[Word]`, where each `Word` carries `text`, `left`, `top`, `width`, `height` (pixel coordinates from Tesseract `image_to_data` or PyMuPDF).
- **`InvoiceData.to_rows()`** (`models.py`) is the only flattening step — it expands line items so one invoice with N items becomes N dicts. Invoice-level fields repeat on every row.
- **`bundle_paths.py`** must be imported and `configure_tesseract()` called **before** pytesseract is imported — this is why `main.py` does it at the very top before the rest of the imports.

## Key Extension Points

- **Add new table column keywords** → `_HEADER_KEYWORDS` dict in `table_detector.py`
- **Add new end-of-table markers** → `_END_MARKERS` list in `table_detector.py`
- **Add specialized field extractors** → extend the `if/elif` chain in `extract_fields()` in `field_extractor.py`
- **Add new "total" field aliases** → `_TOTAL_FIELDS` frozenset in `field_extractor.py`
- **Change OCR language** → `OCR_LANG` constant in `pdf_reader.py`

## Matching & Normalization Convention

All text matching is **accent-insensitive and case-insensitive** via `_normalize()` (strips combining characters with `unicodedata.NFKD`). This function is duplicated independently in both `field_extractor.py` and `table_detector.py`. Any new matcher must use it.

## Developer Workflows

```bash
# Setup (requires uv + Tesseract with Portuguese data)
make install-dev          # uv sync --all-extras
make check-tesseract      # verify tesseract + por language data

# Run
make run                  # uv run python main.py

# Tests (63 tests, no real PDFs needed — all mocked with Word lists)
make test                 # pytest tests/ -v
make test-coverage        # + coverage report

# Lint / format
make lint                 # ruff check
make format               # ruff format

# Full CI locally
make ci                   # ci-lint + ci-test

# Package (MUST run on target OS — no cross-compilation)
make pack-macos           # → dist/macos/InvoiceScrapper.app
make pack-linux           # → dist/linux/InvoiceScrapper
# Windows: use pack-windows.bat (not make)
```

## Test Conventions

Tests use manually constructed `Word` lists — no real PDFs or Tesseract calls. Pattern: create `Word(text=..., left=..., top=..., width=..., height=...)` objects and pass them directly to extractor/detector functions. See `tests/test_field_extractor.py` and `tests/test_table_detector.py` for examples.

## Config & State

- User config lives at `~/.invoice_scrapper/config.json` — load/save via `Config.load()` / `config.save()` in `config.py`.
- No DB, no server — entirely local/file-based.
- The UI (`ui/app.py`) runs processing in a background thread and communicates progress via a log callback passed to `invoice_processor.py`.

## Packaging Notes

- PyInstaller bundles Tesseract binary + `por.traineddata` + `eng.traineddata` alongside the app. The spec is auto-generated via `flet pack`; the `InvoiceScrapper.spec` at repo root is the last generated spec (do not hand-edit unless necessary).
- `bundle_paths.py` detects `sys.frozen` to redirect pytesseract to the bundled binary — if adding new native binaries, follow the same pattern.
- All `invoice_scrapper.*` submodules must be listed as `--hidden-import` in the `PACK_BASE` block in `Makefile` (PyInstaller misses them otherwise).


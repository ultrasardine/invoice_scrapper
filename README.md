# Invoice Scrapper

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-55%20passed-brightgreen.svg)]()

Desktop application to extract data from PDF invoices and export to Excel. Built with Flet (Python).

Designed for Portuguese invoices from multiple suppliers with varying layouts. Handles both digital PDFs and scanned/image-based invoices via OCR.

## Features

- **PDF text extraction** with OCR fallback (Tesseract) for image-based invoices
- **Table detection** for line items using img2table + OpenCV + borderless detection
- **Field extraction** via keyword proximity + regex (case/accent insensitive)
- **Customizable field list** — editable in the UI and persisted to config file
- **Excel output** — one row per line item, invoice-level fields repeated
- **Real-time log** and progress feedback during processing
- **Self-contained packaging** — standalone macOS/Windows/Linux executables via PyInstaller

## How It Works

The app processes a folder of PDF invoices through a 5-stage pipeline and outputs a single Excel file where each row represents one line item (artigo) from an invoice.

### Processing Pipeline

```
PDF File
  │
  ▼
┌─────────────────────────────────────────────────┐
│ 1. PDF Reader (pdf_reader.py)                   │
│    Try PyMuPDF text extraction per page.         │
│    If a page has no embedded text → render to    │
│    image at 300 DPI → OCR with Tesseract (por).  │
│    Output: full text + list of page images       │
└──────────────┬──────────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌──────────────┐ ┌──────────────────────────────┐
│ 2. Field     │ │ 3. Table Detector             │
│ Extractor    │ │    (table_detector.py)         │
│              │ │                                │
│ Search text  │ │ For each page image:           │
│ for field    │ │  a) img2table (primary)        │
│ labels,      │ │  b) OpenCV line detection      │
│ extract      │ │  c) Borderless text alignment  │
│ nearby       │ │                                │
│ values via   │ │ Pick best result by content    │
│ regex        │ │ cell count.                    │
│              │ │ Output: 2D string arrays       │
└──────┬───────┘ └──────────────┬───────────────┘
       │                        │
       ▼                        ▼
┌─────────────────────────────────────────────────┐
│ 4. Line Item Parser (invoice_processor.py)      │
│    Match table column headers to known keywords  │
│    (quantidade, preço unitário, qtd, p.unit...) │
│    Extract one LineItem per data row.             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ 5. Excel Writer (excel_writer.py)               │
│    One sheet "Faturas". Each invoice produces    │
│    N rows (one per line item). Invoice-level     │
│    fields are repeated on every row.             │
│    Auto-sized columns. Missing fields → blank.   │
└─────────────────────────────────────────────────┘
```

### Field Extraction Strategy

The field extractor uses a combined **keyword proximity + regex** approach:

1. **Normalize** both the invoice text and the field label (remove accents, lowercase)
2. **Search** for the field label in the text. If not found, try individual words (>3 chars)
3. **Extract** the value from a 200-character window after the label using a field-specific regex:

| Field type | Regex pattern | Example match |
|---|---|---|
| Date fields (`data`) | `dd/mm/yyyy`, `dd-mm-yyyy`, `dd.mm.yyyy` | `15/03/2024` |
| Money fields (`preço`, `total`) | Decimal with thousands separator | `1.250,00` or `1,250.00` |
| Reference fields (`número`, `referência`, `guia`, `imputação`) | Alphanumeric sequences | `FT-2024/1234`, `IMP-001` |
| Text fields (fallback) | First non-empty value after colon/space | `Empresa ABC Lda` |

Matching is **case-insensitive** and **accent-insensitive** — `"Número"` matches `"numero"`, `"NÚMERO"`, etc.

### Table Detection Strategy

Tables are detected using a 3-tier fallback approach on each page image:

1. **img2table** (primary) — uses the img2table library with Tesseract OCR to detect bordered tables with implicit rows/columns
2. **OpenCV line detection** (fallback) — detects horizontal and vertical lines via morphological operations, finds grid intersections, OCRs each cell
3. **Borderless text alignment** (last resort) — extracts all text with positions via Tesseract, groups by vertical position into rows, clusters x-positions into columns

The detector runs both img2table and OpenCV, then picks the result with more content cells (20% threshold). If neither finds anything, borderless detection is attempted.

### Excel Output Format

The output Excel file has one sheet named "Faturas" with these columns:

| Column | Source | Per-invoice or per-item |
|---|---|---|
| fornecedor | Field extractor | Per-invoice (repeated) |
| número da fatura | Field extractor | Per-invoice (repeated) |
| data da fatura | Field extractor | Per-invoice (repeated) |
| preço total sem IVA | Field extractor | Per-invoice (repeated) |
| número da imputação da fatura | Field extractor | Per-invoice (repeated) |
| referência nessa imputação | Field extractor | Per-invoice (repeated) |
| preço unitário do artigo | Table detector | Per-item |
| quantidade | Table detector | Per-item |
| número da guia de remessa | Field extractor | Per-invoice (repeated) |
| cliente ou local de entrega | Field extractor | Per-invoice (repeated) |
| ficheiro | Filename | Per-invoice (repeated) |

If an invoice has 3 line items, it produces 3 rows with the invoice-level fields repeated. If no line items are found, it produces 1 row with blank item fields.

## Architecture

```
invoice_scrapper/
├── __init__.py
├── bundle_paths.py       # Tesseract path resolver for packaged apps
├── config.py             # Config manager (~/.invoice_scrapper/config.json)
├── models.py             # InvoiceData, LineItem, ProcessingResult
├── pdf_reader.py         # PyMuPDF text extraction + Tesseract OCR fallback
├── table_detector.py     # img2table + OpenCV + borderless detection
├── field_extractor.py    # Keyword proximity + regex field extraction
├── invoice_processor.py  # Pipeline orchestrator
├── excel_writer.py       # openpyxl Excel output
└── ui/
    └── app.py            # Flet desktop UI
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Load/save config from `~/.invoice_scrapper/config.json`. Stores input dir, output file path, and field list. Falls back to defaults if file is missing or corrupted. |
| `models.py` | Data classes: `InvoiceData` (invoice-level fields + line items), `LineItem` (unit price + quantity), `ProcessingResult` (success/error per file). `InvoiceData.to_rows()` flattens to dicts for Excel. |
| `pdf_reader.py` | Opens PDF with PyMuPDF. For each page: extracts embedded text; if empty, renders at 300 DPI and OCRs with Tesseract (Portuguese). Returns full text + page images. |
| `table_detector.py` | Detects tables in page images using 3-tier fallback (img2table → OpenCV → borderless). Returns tables as `list[list[list[str]]]` (list of tables, each a 2D string array). |
| `field_extractor.py` | Searches text for field labels (accent/case insensitive), extracts values using field-type-specific regex. Skips per-item fields (handled by table detector). |
| `invoice_processor.py` | Orchestrates the pipeline: PDF reader → field extractor → table detector → line item parser. Accepts a log callback for UI integration. Processes files individually so one failure doesn't stop the batch. |
| `excel_writer.py` | Writes `list[InvoiceData]` to an Excel file with openpyxl. One sheet, auto-sized columns, configurable field list. |
| `bundle_paths.py` | Detects PyInstaller bundle (`sys.frozen`) and configures pytesseract to use the bundled Tesseract binary and tessdata. No-op when running from source. |
| `ui/app.py` | Flet desktop UI. File pickers for input/output, editable field list, save/load config, process button with progress bar, scrollable log area. Processing runs in a background thread. |

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) with Portuguese language data

### macOS

```bash
brew install tesseract tesseract-lang
```

### Ubuntu/Debian

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-por
```

### Windows

Download the installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and select Portuguese during installation. Ensure `tesseract.exe` is in your PATH.

## Setup

```bash
git clone https://github.com/ultrasardine/invoice_scrapper.git
cd invoice_scrapper

# Install all dependencies
make install-dev

# Verify Tesseract is working
make check-tesseract
```

## Usage

### Running from Source

```bash
make run
# or: uv run python main.py
```

### UI Controls

| Control | Description |
|---|---|
| **Pasta de entrada** | Folder containing PDF invoices. Default: `~/Downloads` |
| **Ficheiro Excel de saída** | Output Excel file path. Default: `~/Documents/invoice_info.xlsx` |
| **Campos a extrair** | Editable list of fields to search for. Add/remove with buttons. |
| **Guardar Config** | Save current settings to `~/.invoice_scrapper/config.json` |
| **Carregar Config** | Load settings from config file |
| **Processar Faturas** | Start processing. Shows real-time log and progress bar. |

### Configuration

Settings are stored in `~/.invoice_scrapper/config.json`:

```json
{
  "input_dir": "/Users/you/Downloads",
  "output_file": "/Users/you/Documents/invoice_info.xlsx",
  "fields": [
    "fornecedor",
    "número da fatura",
    "data da fatura",
    "preço total sem IVA",
    "número da imputação da fatura",
    "referência nessa imputação",
    "preço unitário do artigo",
    "quantidade",
    "número da guia de remessa",
    "cliente ou local de entrega"
  ]
}
```

### Default Fields

| Field | Description | Extraction method |
|---|---|---|
| fornecedor | Supplier name | Text search |
| número da fatura | Invoice number | Text search (alphanumeric regex) |
| data da fatura | Invoice date | Text search (date regex) |
| preço total sem IVA | Total price without VAT | Text search (money regex) |
| número da imputação da fatura | Imputation number | Text search (alphanumeric regex) |
| referência nessa imputação | Imputation reference | Text search (alphanumeric regex) |
| preço unitário do artigo | Unit price per item | Table detection |
| quantidade | Quantity per item | Table detection |
| número da guia de remessa | Delivery note number | Text search (alphanumeric regex) |
| cliente ou local de entrega | Client or delivery location | Text search |

## Packaging

Build standalone executables that bundle Python, all dependencies, Tesseract, and language data. End users don't need to install anything.

```bash
# macOS (run on macOS)
make pack-macos    # → dist/macos/InvoiceScrapper.app

# Windows (run on Windows)
make pack-windows  # → dist/windows/InvoiceScrapper.exe

# Linux (run on Linux)
make pack-linux    # → dist/linux/InvoiceScrapper
```

Each target must be run on its target OS (PyInstaller limitation). For cross-platform builds, use CI with a matrix strategy.

## Testing

```bash
make test              # Run all 55 tests
make test-verbose      # With stdout visible
make test-coverage     # With coverage report
```

### Test Structure

| Test file | What it covers |
|---|---|
| `test_config.py` | Config load/save, defaults, partial configs, corruption handling |
| `test_models.py` | `to_rows()` output, field defaults, line item expansion |
| `test_pdf_reader.py` | Text extraction, OCR fallback trigger, multi-page handling |
| `test_table_detector.py` | img2table/OpenCV/borderless fallback, best-table selection |
| `test_field_extractor.py` | Each field type, missing fields, case/accent insensitivity |
| `test_invoice_processor.py` | Full pipeline, error isolation, log callbacks, header matching |
| `test_excel_writer.py` | Row counts, field repetition, blank cells, custom fields |

## Makefile Reference

Run `make help` to see all available commands:

| Command | Description |
|---|---|
| `make install` | Install production dependencies |
| `make install-dev` | Install all dependencies including dev tools |
| `make check-tesseract` | Verify Tesseract OCR installation |
| `make run` | Launch the desktop app |
| `make test` | Run all tests |
| `make test-coverage` | Run tests with coverage report |
| `make lint` | Run ruff linting |
| `make format` | Format code with ruff |
| `make pack-macos` | Package standalone macOS app |
| `make pack-windows` | Package standalone Windows exe |
| `make pack-linux` | Package standalone Linux binary |
| `make clean` | Remove build artifacts and caches |
| `make ci` | Run full CI pipeline (lint + test) |

## Tech Stack

| Component | Library | Purpose |
|---|---|---|
| UI | [Flet](https://flet.dev/) 0.84.0 | Desktop GUI with Material Design |
| PDF parsing | [PyMuPDF](https://pymupdf.readthedocs.io/) | Text extraction + page rendering |
| OCR | [pytesseract](https://github.com/madmaze/pytesseract) | Tesseract wrapper for image-based PDFs |
| Table detection | [img2table](https://github.com/xavctn/img2table) | Primary table detection |
| Image processing | [OpenCV](https://opencv.org/), [Pillow](https://pillow.readthedocs.io/) | Line detection, image manipulation |
| Excel | [openpyxl](https://openpyxl.readthedocs.io/) | Excel file generation |
| Packaging | [PyInstaller](https://pyinstaller.org/) | Standalone executable bundling |

## FAQ

**Q: The app doesn't find any fields in my invoice.**
A: The field extractor searches for the exact field label text (case/accent insensitive) in the PDF. If your invoice uses different terminology (e.g., "NIF do fornecedor" instead of "fornecedor"), edit the field list in the UI to match. The extractor looks for the label and grabs the value nearby.

**Q: OCR results are poor / fields are extracted incorrectly.**
A: Ensure Tesseract has Portuguese language data installed (`make check-tesseract`). For scanned invoices, quality depends on scan resolution — 300 DPI is the minimum for reliable OCR. Very skewed or low-contrast scans may produce poor results.

**Q: No line items are detected even though the invoice has a table.**
A: The table detector looks for column headers matching keywords like "quantidade", "qtd", "preço unitário", "p.unit", "valor". If your invoices use different column names, the line item parser won't match them. This can be improved by adding more keyword variants to `invoice_processor.py`.

**Q: Can I add custom fields beyond the defaults?**
A: Yes. Click the "+" button in the UI to add new fields. The field extractor will search for whatever label you type. For best results, use the exact text that appears in your invoices near the value you want to extract.

**Q: Why does packaging use PyInstaller instead of `flet build`?**
A: `flet build` uses an embedded Python runtime that can have architecture mismatches on Apple Silicon Macs and struggles with native dependencies like `numba`/`llvmlite` (required by `img2table`). `flet pack` (PyInstaller) uses your system Python with pre-built wheels, avoiding these issues.

**Q: Can I build for Windows from macOS (or vice versa)?**
A: No. PyInstaller produces binaries for the OS it runs on. For cross-platform builds, use CI (GitHub Actions, AppVeyor) with a build matrix targeting each OS.

**Q: Where is the config file stored?**
A: `~/.invoice_scrapper/config.json`. It's created when you click "Guardar Config" in the UI. If the file is missing or corrupted, the app falls back to defaults.

**Q: What happens if a PDF fails to process?**
A: The error is logged and the app continues processing the remaining files. Failed invoices are counted in the summary. The Excel file contains data from all successfully processed invoices.

**Q: Can I process invoices in languages other than Portuguese?**
A: The OCR defaults to Portuguese (`por`). To change the language, modify the `OCR_LANG` constant in `pdf_reader.py` and `table_detector.py`, and install the corresponding Tesseract language data.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

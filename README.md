# Invoice Scrapper

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-63%20passed-brightgreen.svg)]()

Desktop application to extract data from PDF invoices and export to Excel. Built with Flet (Python).

Designed for Portuguese invoices from multiple suppliers with varying layouts. Handles both digital PDFs and scanned/image-based invoices via OCR.

## Features

- **PDF text extraction** with OCR fallback (Tesseract) for image-based invoices
- **Positional word-based extraction** — uses Tesseract's word-level coordinates for accurate field and table detection
- **Table detection** via header keyword matching + column alignment from word positions
- **Field extraction** by finding labels and grabbing values to the right/below based on coordinates
- **Customizable field list** — editable in the UI and persisted to config file
- **Excel output** — one row per line item, invoice-level fields repeated
- **Real-time log** and progress feedback during processing
- **Self-contained packaging** — standalone macOS/Windows/Linux executables via PyInstaller

## How It Works

The app processes a folder of PDF invoices through a pipeline and outputs a single Excel file where each row represents one line item (artigo) from an invoice.

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
│    Output: Word objects with text + x/y/w/h      │
│    positions, full text, and page images.         │
└──────────────┬──────────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌──────────────┐ ┌──────────────────────────────┐
│ 2. Field     │ │ 3. Table Detector             │
│ Extractor    │ │    (table_detector.py)         │
│              │ │                                │
│ Find label   │ │ Group words into rows by       │
│ words by     │ │ y-position. Find header row    │
│ position,    │ │ by matching known keywords     │
│ grab values  │ │ (QTD, P.UNIT, REFERÊNCIA...). │
│ to the       │ │ Define columns from header     │
│ right/below  │ │ positions. Assign data row     │
│ using word   │ │ words to columns by x-pos.     │
│ coordinates  │ │                                │
│              │ │ Output: 2D string arrays       │
└──────┬───────┘ └──────────────┬───────────────┘
       │                        │
       ▼                        ▼
┌─────────────────────────────────────────────────┐
│ 4. Line Item Parser (invoice_processor.py)      │
│    Match table column headers to known keywords  │
│    (quantidade, preço unitário, qtd, p.unit...) │
│    Extract one LineItem per data row.             │
│    Validate numeric values (filter OCR noise).   │
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

The field extractor uses **positional word data** from Tesseract OCR:

1. **OCR with positions** — Tesseract `image_to_data` returns each word with its bounding box (x, y, width, height)
2. **Find labels** — locate known label words (e.g., "Fatura", "Nº:", "DATA EMISSÃO") by matching against the word list
3. **Extract values** — grab words to the right of or below the label based on coordinates

| Field | Strategy | Example |
|---|---|---|
| Fornecedor (supplier) | Company suffix (LDA, S.A.) or largest font at top | `LUSO PROMOVE, LDA` |
| Número da fatura | Find "Fatura Nº:" label, grab value to right; fallback to ATCUD | `FAC 3/243` |
| Data da fatura | Find "DATA EMISSÃO" header, grab date below/right | `2025-10-28` |
| Preço total sem IVA | Find "Base Incidência" or "Total Ilíquido", grab money value | `186,28` |
| Generic fields | Find longest keyword match, grab value to the right | `IMP-2024-001` |

Matching is **case-insensitive** and **accent-insensitive** — `"Número"` matches `"numero"`, `"NÚMERO"`, etc.

### Table Detection Strategy

Tables are detected using **positional word alignment**:

1. **Group words into rows** by y-position (words within 25px vertical tolerance = same row)
2. **Find header row** by matching words against known column keywords (referência, descrição, qtd, p.unit, total, iva, etc.)
3. **Define columns** from the x-positions of matched header words
4. **Extract data rows** below the header, assigning each word to the nearest column by x-position
5. **Stop at end markers** (OBSERVAÇÕES, RESUMO DE IMPOSTOS, etc.)
6. **Validate values** — filter OCR noise from numeric columns (qty, price)

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
├── pdf_reader.py         # PyMuPDF text extraction + Tesseract OCR with positions
├── table_detector.py     # Header keyword matching + column alignment
├── field_extractor.py    # Positional word-based field extraction
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
| `pdf_reader.py` | Opens PDF with PyMuPDF. For each page: extracts embedded text with word positions; if empty, renders at 300 DPI and OCRs with Tesseract (Portuguese) using `image_to_data` for word-level positions. Returns `PageData` objects with `Word` list, full text, and page image. |
| `table_detector.py` | Groups words into rows by y-position. Finds header row by matching known column keywords. Defines columns from header word x-positions. Assigns data row words to columns. Returns tables as `list[list[list[str]]]`. |
| `field_extractor.py` | Finds field labels in positional word data, extracts values to the right/below. Specialized extractors for supplier (font size + company suffix), invoice number (Fatura Nº + ATCUD fallback), date (DATA EMISSÃO header), and total (Base Incidência). Generic extractor for other fields. |
| `invoice_processor.py` | Orchestrates the pipeline: PDF reader → field extractor → table detector → line item parser. Validates numeric values in qty/price columns. Accepts a log callback for UI integration. Processes files individually so one failure doesn't stop the batch. |
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

Download the installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and select Portuguese during installation. Keeping `tesseract.exe` in your PATH is recommended, but the Windows packaging script also auto-detects the standard install folders.

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
| fornecedor | Supplier name | Company suffix / largest font at top |
| número da fatura | Invoice number | "Fatura Nº:" label + ATCUD fallback |
| data da fatura | Invoice date | "DATA EMISSÃO" header + date below |
| preço total sem IVA | Total price without VAT | "Base Incidência" / "Total Ilíquido" |
| número da imputação da fatura | Imputation number | Generic keyword search |
| referência nessa imputação | Imputation reference | Generic keyword search |
| preço unitário do artigo | Unit price per item | Table detection |
| quantidade | Quantity per item | Table detection |
| número da guia de remessa | Delivery note number | Generic keyword search |
| cliente ou local de entrega | Client or delivery location | Generic keyword search |

## Packaging

Build standalone executables that bundle Python, all dependencies, Tesseract, and language data. End users don't need to install anything.

**Each target must be run on its target OS** (PyInstaller limitation). The Makefile enforces this with OS guards.

```bash
# macOS (run on macOS)
make pack-macos    # → dist/macos/InvoiceScrapper.app

# Linux (run on Linux)
make pack-linux    # → dist/linux/InvoiceScrapper
```

### Windows Packaging

Windows doesn't use `make`. Run the included batch script:

```cmd
pack-windows.bat
```

This auto-detects Tesseract paths and produces `dist\windows\InvoiceScrapper.exe`.

Prerequisites:
- Python 3.13+ with [uv](https://docs.astral.sh/uv/) installed
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed with Portuguese language data
- Run `uv sync --all-extras` first to install dependencies

`pack-windows.bat` looks for `tesseract.exe` in `PATH`, `%ProgramFiles%\Tesseract-OCR`, `%ProgramFiles(x86)%\Tesseract-OCR`, and `%LocalAppData%\Programs\Tesseract-OCR`. It also honors `TESSDATA_PREFIX` when language files live outside the default `tessdata` folder.

For cross-platform builds, use CI with a matrix strategy.

## Testing

```bash
make test              # Run all 63 tests
make test-verbose      # With stdout visible
make test-coverage     # With coverage report
```

### Test Structure

| Test file | What it covers |
|---|---|
| `test_config.py` | Config load/save, defaults, partial configs, corruption handling |
| `test_models.py` | `to_rows()` output, field defaults, line item expansion |
| `test_pdf_reader.py` | Text extraction, OCR fallback, word positions, PageData |
| `test_table_detector.py` | Header detection, column alignment, end-of-table, keyword matching |
| `test_field_extractor.py` | Supplier, invoice number, date, total, generic fields, normalization |
| `test_invoice_processor.py` | Full pipeline, error isolation, log callbacks, line item parsing |
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
| `make pack-macos` | Package standalone macOS app (macOS only) |
| `make pack-windows` | Package standalone Windows exe (Windows only) |
| `make pack-linux` | Package standalone Linux binary (Linux only) |
| `make clean` | Remove build artifacts and caches |
| `make ci` | Run full CI pipeline (lint + test) |

## Tech Stack

| Component | Library | Purpose |
|---|---|---|
| UI | [Flet](https://flet.dev/) 0.84.0 | Desktop GUI with Material Design |
| PDF parsing | [PyMuPDF](https://pymupdf.readthedocs.io/) | Text extraction + page rendering |
| OCR | [pytesseract](https://github.com/madmaze/pytesseract) | Tesseract wrapper — word-level positions + text |
| Image processing | [Pillow](https://pillow.readthedocs.io/) | Image handling for OCR |
| Excel | [openpyxl](https://openpyxl.readthedocs.io/) | Excel file generation |
| Packaging | [PyInstaller](https://pyinstaller.org/) | Standalone executable bundling |

## FAQ

**Q: The app doesn't find any fields in my invoice.**
A: The field extractor searches for known label patterns (e.g., "Fatura Nº:", "DATA EMISSÃO") in the OCR'd text. If your invoice uses different terminology, the extractor may not find them. For generic fields, it searches for the field name keywords and grabs the value to the right.

**Q: OCR results are poor / fields are extracted incorrectly.**
A: Ensure Tesseract has Portuguese language data installed (`make check-tesseract`). For scanned invoices, quality depends on scan resolution — 300 DPI is the minimum for reliable OCR. Very skewed or low-contrast scans may produce poor results.

**Q: No line items are detected even though the invoice has a table.**
A: The table detector looks for header rows containing keywords like "quantidade", "qtd", "preço unitário", "p.unit", "referência", "descrição". If your invoices use different column names, add them to `_HEADER_KEYWORDS` in `table_detector.py`.

**Q: Can I add custom fields beyond the defaults?**
A: Yes. Click the "+" button in the UI to add new fields. The field extractor will search for whatever label you type using the generic keyword-based extraction.

**Q: Why does packaging use PyInstaller instead of `flet build`?**
A: `flet build` uses an embedded Python runtime that can have architecture mismatches on Apple Silicon Macs and struggles with native dependencies. `flet pack` (PyInstaller) uses your system Python with pre-built wheels, avoiding these issues.

**Q: Can I build for Windows from macOS (or vice versa)?**
A: No. PyInstaller produces binaries for the OS it runs on. The Makefile enforces this — running `make pack-linux` on macOS will error. For cross-platform builds, use CI (GitHub Actions) with a build matrix targeting each OS.

**Q: Where is the config file stored?**
A: `~/.invoice_scrapper/config.json`. It's created when you click "Guardar Config" in the UI. If the file is missing or corrupted, the app falls back to defaults.

**Q: What happens if a PDF fails to process?**
A: The error is logged and the app continues processing the remaining files. Failed invoices are counted in the summary. The Excel file contains data from all successfully processed invoices.

**Q: Can I process invoices in languages other than Portuguese?**
A: The OCR defaults to Portuguese (`por`). To change the language, modify the `OCR_LANG` constant in `pdf_reader.py` and install the corresponding Tesseract language data.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

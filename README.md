# Invoice Scrapper

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-55%20passed-brightgreen.svg)]()

Desktop application to extract data from PDF invoices and export to Excel. Built with Flet (Python).

## Features

- **PDF text extraction** with OCR fallback (Tesseract) for image-based invoices
- **Table detection** for line items using img2table + OpenCV
- **Field extraction** via keyword proximity + regex (case/accent insensitive)
- **Customizable field list** — editable in the UI and persisted to config file
- **Excel output** — one row per line item, invoice-level fields repeated
- **Real-time log** and progress feedback during processing

## Architecture

```
invoice_scrapper/
├── config.py             # Config manager (~/.invoice_scrapper/config.json)
├── models.py             # InvoiceData, LineItem, ProcessingResult
├── pdf_reader.py         # PyMuPDF text extraction + Tesseract OCR fallback
├── table_detector.py     # img2table + OpenCV + borderless detection
├── field_extractor.py    # Keyword proximity + regex field extraction
├── invoice_processor.py  # Pipeline orchestrator
├── excel_writer.py       # openpyxl Excel output
└── ui/app.py             # Flet desktop UI
```

### Processing Pipeline

1. **PDF Reader** — extracts text from each page via PyMuPDF; falls back to OCR (Tesseract, Portuguese) for pages without embedded text
2. **Field Extractor** — searches for field labels in the text (case/accent insensitive) and extracts nearby values using field-specific regex patterns
3. **Table Detector** — detects tables in page images using img2table (primary), OpenCV line detection (fallback), and borderless text alignment analysis (last resort)
4. **Line Item Parser** — matches table column headers to per-item fields (preço unitário, quantidade)
5. **Excel Writer** — outputs all data to a single Excel sheet with auto-sized columns

## Prerequisites

- Python 3.13+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and in PATH
- Portuguese language data for Tesseract (`por`)

### macOS

```bash
brew install tesseract tesseract-lang
```

### Ubuntu/Debian

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-por
```

## Setup

```bash
# Clone and install
uv sync

# Install dev dependencies
uv sync --all-extras
```

## Usage

```bash
# Launch the desktop app
uv run python main.py
```

### UI Controls

- **Pasta de entrada** — select the folder containing PDF invoices (default: `~/Downloads`)
- **Ficheiro Excel de saída** — select the output Excel file path (default: `~/Documents/invoice_info.xlsx`)
- **Campos a extrair** — editable list of fields to search for in invoices
- **Guardar/Carregar Config** — persist field list and paths to `~/.invoice_scrapper/config.json`
- **Processar Faturas** — start processing with real-time log and progress bar

### Default Fields

| Field | Description |
|---|---|
| fornecedor | Supplier name |
| número da fatura | Invoice number |
| data da fatura | Invoice date |
| preço total sem IVA | Total price without VAT |
| número da imputação da fatura | Imputation number |
| referência nessa imputação | Imputation reference |
| preço unitário do artigo | Unit price (per line item) |
| quantidade | Quantity (per line item) |
| número da guia de remessa | Delivery note number |
| cliente ou local de entrega | Client or delivery location |

## Testing

```bash
uv run pytest tests/ -v
```

## Tech Stack

- **UI**: [Flet](https://flet.dev/) 0.84.0
- **PDF**: [PyMuPDF](https://pymupdf.readthedocs.io/)
- **OCR**: [pytesseract](https://github.com/madmaze/pytesseract) + [img2table](https://github.com/xavctn/img2table)
- **Image processing**: [OpenCV](https://opencv.org/), [Pillow](https://pillow.readthedocs.io/)
- **Excel**: [openpyxl](https://openpyxl.readthedocs.io/)

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

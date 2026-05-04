"""Tests for invoice processor pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from invoice_scrapper.invoice_processor import InvoiceProcessor
from invoice_scrapper.config import DEFAULT_FIELDS


SAMPLE_TEXT = """
Fornecedor: Test Corp
Número da Fatura: FT-001
Data da Fatura: 01/01/2024
Preço Total sem IVA: 500,00
"""


def _make_image():
    return Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_file_success(MockReader, MockDetector):
    reader = MockReader.return_value
    reader.extract.return_value = (SAMPLE_TEXT, [_make_image()])

    detector = MockDetector.return_value
    detector.detect_tables.return_value = [
        [["Artigo", "Quantidade", "Preço Unitário"],
         ["Widget", "10", "50,00"]]
    ]

    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    result = proc.process_file(Path("test.pdf"), DEFAULT_FIELDS)

    assert result.success
    assert result.invoice is not None
    assert result.invoice.ficheiro == "test.pdf"
    assert result.invoice.fornecedor != ""
    assert len(result.invoice.line_items) == 1
    assert result.invoice.line_items[0].quantidade == "10"
    assert len(logs) > 0


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_file_error(MockReader, MockDetector):
    reader = MockReader.return_value
    reader.extract.side_effect = RuntimeError("corrupt PDF")

    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    result = proc.process_file(Path("bad.pdf"), DEFAULT_FIELDS)

    assert not result.success
    assert len(result.errors) == 1
    assert "corrupt PDF" in result.errors[0]


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_file_no_tables(MockReader, MockDetector):
    reader = MockReader.return_value
    reader.extract.return_value = (SAMPLE_TEXT, [_make_image()])
    detector = MockDetector.return_value
    detector.detect_tables.return_value = []

    proc = InvoiceProcessor()
    result = proc.process_file(Path("no_table.pdf"), DEFAULT_FIELDS)

    assert result.success
    assert result.invoice is not None
    assert len(result.invoice.line_items) == 0


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_directory(MockReader, MockDetector, tmp_path: Path):
    # Create fake PDFs
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.pdf").touch()
    (tmp_path / "c.txt").touch()  # Not a PDF

    reader = MockReader.return_value
    reader.extract.return_value = ("text", [_make_image()])
    detector = MockDetector.return_value
    detector.detect_tables.return_value = []

    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    results = list(proc.process_directory(tmp_path, DEFAULT_FIELDS))

    assert len(results) == 2  # Only PDFs
    assert all(r.success for r in results)


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_directory_empty(MockReader, MockDetector, tmp_path: Path):
    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    results = list(proc.process_directory(tmp_path, DEFAULT_FIELDS))
    assert len(results) == 0


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_error_doesnt_stop_batch(MockReader, MockDetector, tmp_path: Path):
    (tmp_path / "good.pdf").touch()
    (tmp_path / "bad.pdf").touch()

    reader = MockReader.return_value
    call_count = 0

    def side_effect(path):
        nonlocal call_count
        call_count += 1
        if "bad" in str(path):
            raise RuntimeError("fail")
        return ("text", [_make_image()])

    reader.extract.side_effect = side_effect
    detector = MockDetector.return_value
    detector.detect_tables.return_value = []

    proc = InvoiceProcessor()
    results = list(proc.process_directory(tmp_path, DEFAULT_FIELDS))

    assert len(results) == 2
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    assert len(successes) == 1
    assert len(failures) == 1


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_log_callback_invoked(MockReader, MockDetector):
    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    proc.log("test message")
    assert "test message" in logs


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_parse_line_items_no_header(MockReader, MockDetector):
    proc = InvoiceProcessor()
    tables = [[["a", "b"], ["c", "d"]]]
    items = proc._parse_line_items(tables, DEFAULT_FIELDS)
    assert len(items) == 0


@patch("invoice_scrapper.invoice_processor.TableDetector")
@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_parse_line_items_with_header(MockReader, MockDetector):
    proc = InvoiceProcessor()
    tables = [
        [["Descrição", "Quantidade", "Preço Unitário"],
         ["Item A", "5", "10,00"],
         ["Item B", "3", "20,00"]]
    ]
    items = proc._parse_line_items(tables, DEFAULT_FIELDS)
    assert len(items) == 2
    assert items[0].quantidade == "5"
    assert items[0].preco_unitario == "10,00"

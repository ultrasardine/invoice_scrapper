"""Tests for invoice processor pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from invoice_scrapper.invoice_processor import InvoiceProcessor
from invoice_scrapper.config import DEFAULT_FIELDS
from invoice_scrapper.pdf_reader import Word, PageData
from PIL import Image


def _make_image():
    return Image.new("RGB", (100, 100))


def _make_page_data(words=None, text=""):
    """Create a PageData with optional words."""
    if words is None:
        words = []
    return PageData(words=words, text=text, image=_make_image())


def _make_invoice_words():
    """Create words simulating a simple invoice."""
    return [
        Word(text="Test", left=100, top=50, width=50, height=40),
        Word(text="Corp", left=160, top=50, width=50, height=40),
        Word(text="Lda", left=220, top=50, width=30, height=40),
        Word(text="Fatura", left=100, top=150, width=60, height=30),
        Word(text="Nº:", left=170, top=150, width=30, height=30),
        Word(text="FT-001", left=210, top=150, width=60, height=30),
        Word(text="DATA", left=100, top=250, width=50, height=30),
        Word(text="EMISSÃO", left=160, top=250, width=70, height=30),
        Word(text="01/01/2024", left=100, top=310, width=100, height=30),
        Word(text="Base", left=100, top=2500, width=40, height=30),
        Word(text="Incidência", left=150, top=2500, width=90, height=30),
        Word(text="500,00", left=100, top=2570, width=60, height=30),
    ]


@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_file_success(MockReader):
    reader = MockReader.return_value
    words = _make_invoice_words()
    # Add table words
    table_words = [
        Word(text="REFERÊNCIA", left=100, top=1000, width=100, height=25),
        Word(text="Quantidade", left=400, top=1000, width=100, height=25),
        Word(text="P.Unit", left=600, top=1000, width=60, height=25),
        Word(text="ABC123", left=100, top=1060, width=60, height=25),
        Word(text="10", left=400, top=1060, width=20, height=25),
        Word(text="50,00", left=600, top=1060, width=50, height=25),
    ]
    all_words = words + table_words
    reader.extract_pages.return_value = [
        _make_page_data(words=all_words, text="invoice text")
    ]

    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    result = proc.process_file(Path("test.pdf"), DEFAULT_FIELDS)

    assert result.success
    assert result.invoice is not None
    assert result.invoice.ficheiro == "test.pdf"
    assert len(result.invoice.line_items) == 1
    assert result.invoice.line_items[0].quantidade == "10"
    assert result.invoice.line_items[0].preco_unitario == "50,00"
    assert len(logs) > 0


@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_file_error(MockReader):
    reader = MockReader.return_value
    reader.extract_pages.side_effect = RuntimeError("corrupt PDF")

    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    result = proc.process_file(Path("bad.pdf"), DEFAULT_FIELDS)

    assert not result.success
    assert len(result.errors) == 1
    assert "corrupt PDF" in result.errors[0]


@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_file_no_tables(MockReader):
    reader = MockReader.return_value
    reader.extract_pages.return_value = [
        _make_page_data(words=_make_invoice_words(), text="text")
    ]

    proc = InvoiceProcessor()
    result = proc.process_file(Path("no_table.pdf"), DEFAULT_FIELDS)

    assert result.success
    assert result.invoice is not None
    assert len(result.invoice.line_items) == 0


@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_directory(MockReader, tmp_path: Path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.pdf").touch()
    (tmp_path / "c.txt").touch()

    reader = MockReader.return_value
    reader.extract_pages.return_value = [
        _make_page_data(words=[], text="text")
    ]

    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    results = list(proc.process_directory(tmp_path, DEFAULT_FIELDS))

    assert len(results) == 2
    assert all(r.success for r in results)


@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_process_directory_empty(MockReader, tmp_path: Path):
    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    results = list(proc.process_directory(tmp_path, DEFAULT_FIELDS))
    assert len(results) == 0


@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_error_doesnt_stop_batch(MockReader, tmp_path: Path):
    (tmp_path / "good.pdf").touch()
    (tmp_path / "bad.pdf").touch()

    reader = MockReader.return_value

    def side_effect(path):
        if "bad" in str(path):
            raise RuntimeError("fail")
        return [_make_page_data(words=[], text="text")]

    reader.extract_pages.side_effect = side_effect

    proc = InvoiceProcessor()
    results = list(proc.process_directory(tmp_path, DEFAULT_FIELDS))

    assert len(results) == 2
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    assert len(successes) == 1
    assert len(failures) == 1


@patch("invoice_scrapper.invoice_processor.PDFReader")
def test_log_callback_invoked(MockReader):
    logs: list[str] = []
    proc = InvoiceProcessor(log_callback=logs.append)
    proc.log("test message")
    assert "test message" in logs


def test_parse_line_items_no_header():
    proc = InvoiceProcessor()
    tables = [[["a", "b"], ["c", "d"]]]
    items = proc._parse_line_items(tables, DEFAULT_FIELDS)
    assert len(items) == 0


def test_parse_line_items_with_header():
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


def test_parse_line_items_filters_non_numeric():
    proc = InvoiceProcessor()
    tables = [
        [["Descrição", "Quantidade", "Preço Unitário"],
         ["Item A", "noise text", "abc"],
         ["Item B", "3", "20,00"]]
    ]
    items = proc._parse_line_items(tables, DEFAULT_FIELDS)
    # First row filtered out (no valid numbers), second kept
    assert len(items) == 1
    assert items[0].quantidade == "3"
    assert items[0].preco_unitario == "20,00"

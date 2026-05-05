"""Tests for PDF reader module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from invoice_scrapper.pdf_reader import PDFReader, Word, PageData


def _make_mock_page(text: str = "Invoice text", words=None):
    """Create a mock fitz page."""
    page = MagicMock()
    page.get_text.return_value = text
    page.number = 0
    pix = MagicMock()
    pix.width = 100
    pix.height = 100
    pix.samples = bytes(100 * 100 * 3)
    page.get_pixmap.return_value = pix
    # Mock get_text("words") for digital PDFs
    if words is None:
        words = [(10, 10, 50, 25, text, 0, 0)]
    page.get_text.side_effect = lambda fmt=None: (
        words if fmt == "words" else text
    )
    return page


def _make_mock_doc(pages):
    """Create a mock fitz document."""
    doc = MagicMock()
    doc.__enter__ = MagicMock(return_value=doc)
    doc.__exit__ = MagicMock(return_value=False)
    doc.__iter__ = MagicMock(return_value=iter(pages))
    return doc


@patch("invoice_scrapper.pdf_reader.fitz")
def test_text_based_pdf_no_ocr(mock_fitz):
    page = _make_mock_page("Fatura número 123")
    mock_fitz.open.return_value = _make_mock_doc([page])
    mock_fitz.Matrix = MagicMock()

    reader = PDFReader()
    text, images = reader.extract(Path("test.pdf"))

    assert "Fatura número 123" in text
    assert len(images) == 1


@patch("invoice_scrapper.pdf_reader.pytesseract")
@patch("invoice_scrapper.pdf_reader.fitz")
def test_ocr_fallback_when_no_text(mock_fitz, mock_tesseract):
    page = _make_mock_page("")
    # Override side_effect for empty text
    page.get_text.side_effect = lambda fmt=None: (
        [] if fmt == "words" else ""
    )
    mock_fitz.open.return_value = _make_mock_doc([page])
    mock_fitz.Matrix = MagicMock()
    mock_tesseract.image_to_data.return_value = {
        "text": ["OCR", "result"],
        "left": [10, 50],
        "top": [10, 10],
        "width": [30, 40],
        "height": [20, 20],
        "conf": [90, 90],
    }
    mock_tesseract.image_to_string.return_value = "OCR result"
    mock_tesseract.Output = MagicMock()
    mock_tesseract.Output.DICT = "dict"

    reader = PDFReader()
    text, images = reader.extract(Path("scan.pdf"))

    assert "OCR result" in text
    mock_tesseract.image_to_string.assert_called_once()


@patch("invoice_scrapper.pdf_reader.fitz")
def test_multiple_pages(mock_fitz):
    pages = []
    for i in range(3):
        p = _make_mock_page(f"Page {i}")
        p.get_text.side_effect = lambda fmt=None, i=i: (
            [(10, 10, 50, 25, f"Page {i}", 0, 0)] if fmt == "words"
            else f"Page {i}"
        )
        pages.append(p)
    mock_fitz.open.return_value = _make_mock_doc(pages)
    mock_fitz.Matrix = MagicMock()

    reader = PDFReader()
    text, images = reader.extract(Path("multi.pdf"))

    assert len(images) == 3
    assert "Page 0" in text
    assert "Page 2" in text


@patch("invoice_scrapper.pdf_reader.pytesseract")
@patch("invoice_scrapper.pdf_reader.fitz")
def test_ocr_failure_returns_empty(mock_fitz, mock_tesseract):
    page = _make_mock_page("")
    page.get_text.side_effect = lambda fmt=None: (
        [] if fmt == "words" else ""
    )
    mock_fitz.open.return_value = _make_mock_doc([page])
    mock_fitz.Matrix = MagicMock()
    mock_tesseract.image_to_data.side_effect = RuntimeError("tesseract not found")
    mock_tesseract.image_to_string.side_effect = RuntimeError("tesseract not found")
    mock_tesseract.Output = MagicMock()
    mock_tesseract.Output.DICT = "dict"

    reader = PDFReader()
    text, images = reader.extract(Path("broken.pdf"))

    assert text == ""
    assert len(images) == 1


@patch("invoice_scrapper.pdf_reader.fitz")
def test_extract_pages_returns_page_data(mock_fitz):
    page = _make_mock_page("Test text")
    mock_fitz.open.return_value = _make_mock_doc([page])
    mock_fitz.Matrix = MagicMock()

    reader = PDFReader()
    pages = reader.extract_pages(Path("test.pdf"))

    assert len(pages) == 1
    assert isinstance(pages[0], PageData)
    assert pages[0].text == "Test text"
    assert len(pages[0].words) >= 1


def test_word_properties():
    w = Word(text="hello", left=10, top=20, width=50, height=30)
    assert w.right == 60
    assert w.bottom == 50
    assert w.center_y == 35

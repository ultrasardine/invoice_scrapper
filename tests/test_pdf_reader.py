"""Tests for PDF reader module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from invoice_scrapper.pdf_reader import PDFReader


def _make_mock_page(text: str = "Invoice text"):
    """Create a mock fitz page."""
    page = MagicMock()
    page.get_text.return_value = text
    page.number = 0
    pix = MagicMock()
    pix.width = 100
    pix.height = 100
    pix.samples = bytes(100 * 100 * 3)
    page.get_pixmap.return_value = pix
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
    mock_fitz.open.return_value = _make_mock_doc([page])
    mock_fitz.Matrix = MagicMock()
    mock_tesseract.image_to_string.return_value = "OCR result"

    reader = PDFReader()
    text, images = reader.extract(Path("scan.pdf"))

    assert "OCR result" in text
    mock_tesseract.image_to_string.assert_called_once()


@patch("invoice_scrapper.pdf_reader.fitz")
def test_multiple_pages(mock_fitz):
    pages = [_make_mock_page(f"Page {i}") for i in range(3)]
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
    mock_fitz.open.return_value = _make_mock_doc([page])
    mock_fitz.Matrix = MagicMock()
    mock_tesseract.image_to_string.side_effect = RuntimeError("tesseract not found")

    reader = PDFReader()
    text, images = reader.extract(Path("broken.pdf"))

    assert text == ""
    assert len(images) == 1

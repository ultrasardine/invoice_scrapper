"""PDF text extraction with OCR fallback."""

import logging
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

DPI = 300
OCR_LANG = "por"


class PDFReader:
    """Extract text from PDFs, falling back to OCR for image-based pages."""

    def __init__(self, dpi: int = DPI, lang: str = OCR_LANG):
        self.dpi = dpi
        self.lang = lang

    def extract(self, pdf_path: Path) -> tuple[str, list[Image.Image]]:
        """Extract text and page images from a PDF.

        Returns:
            Tuple of (full_text, page_images).
            page_images contains rendered images for all pages
            (needed for table detection).
        """
        texts: list[str] = []
        images: list[Image.Image] = []

        with fitz.open(pdf_path) as doc:
            for page in doc:
                page_text = page.get_text().strip()
                img = self._render_page(page)
                images.append(img)

                if page_text:
                    texts.append(page_text)
                else:
                    logger.info(
                        "Page %d has no text, using OCR", page.number + 1
                    )
                    ocr_text = self._ocr_image(img)
                    texts.append(ocr_text)

        return "\n".join(texts), images

    def _render_page(self, page: fitz.Page) -> Image.Image:
        """Render a PDF page to a PIL Image at configured DPI."""
        zoom = self.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def _ocr_image(self, image: Image.Image) -> str:
        """OCR an image using Tesseract."""
        try:
            return pytesseract.image_to_string(image, lang=self.lang).strip()
        except Exception as e:
            logger.error("OCR failed: %s", e)
            return ""

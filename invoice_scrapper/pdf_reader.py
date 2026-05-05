"""PDF text extraction with OCR fallback and positional word data."""

import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

DPI = 300
OCR_LANG = "por"


@dataclass
class Word:
    """A single word with its position on the page."""

    text: str
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def center_y(self) -> int:
        return self.top + self.height // 2


@dataclass
class PageData:
    """OCR results for a single page."""

    words: list[Word]
    text: str
    image: Image.Image | None = None


class PDFReader:
    """Extract text from PDFs, falling back to OCR for image-based pages."""

    def __init__(self, dpi: int = DPI, lang: str = OCR_LANG):
        self.dpi = dpi
        self.lang = lang

    def extract(self, pdf_path: Path) -> tuple[str, list[Image.Image]]:
        """Extract text and page images from a PDF.

        Returns:
            Tuple of (full_text, page_images).  Only pages that required OCR
            produce an image; text-based pages return no image.
        """
        pages = self.extract_pages(pdf_path)
        text = "\n".join(p.text for p in pages)
        images = [p.image for p in pages if p.image is not None]
        return text, images

    def extract_pages(self, pdf_path: Path) -> list[PageData]:
        """Extract full page data including positional words."""
        pages: list[PageData] = []

        with fitz.open(pdf_path) as doc:
            for page in doc:
                page_text = page.get_text().strip()

                if page_text:
                    # Digital PDF - use PyMuPDF text blocks for positions.
                    # No need to render a bitmap image.
                    words = self._extract_words_from_page(page)
                    pages.append(PageData(
                        words=words, text=page_text, image=None
                    ))
                else:
                    # Image-based page - render and OCR.
                    logger.info(
                        "Page %d has no text, using OCR", page.number + 1
                    )
                    img = self._render_page(page)
                    words, ocr_text = self._ocr_with_positions(img)
                    pages.append(PageData(
                        words=words, text=ocr_text, image=img
                    ))

        return pages

    def _render_page(self, page: fitz.Page) -> Image.Image:
        """Render a PDF page to a PIL Image at configured DPI."""
        zoom = self.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def _extract_words_from_page(self, page: fitz.Page) -> list[Word]:
        """Extract words with positions from a digital PDF page."""
        zoom = self.dpi / 72.0
        words: list[Word] = []
        for block in page.get_text("words"):
            x0, y0, x1, y1, text, *_ = block
            words.append(Word(
                text=text.strip(),
                left=int(x0 * zoom),
                top=int(y0 * zoom),
                width=int((x1 - x0) * zoom),
                height=int((y1 - y0) * zoom),
            ))
        return words

    def _ocr_with_positions(
        self, image: Image.Image
    ) -> tuple[list[Word], str]:
        """OCR an image and return words with positions."""
        try:
            data = pytesseract.image_to_data(
                image, lang=self.lang, output_type=pytesseract.Output.DICT
            )
            words: list[Word] = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                if not text or int(float(data["conf"][i])) < 0:
                    continue
                words.append(Word(
                    text=text,
                    left=data["left"][i],
                    top=data["top"][i],
                    width=data["width"][i],
                    height=data["height"][i],
                ))
            full_text = pytesseract.image_to_string(
                image, lang=self.lang
            ).strip()
            return words, full_text
        except Exception as e:
            logger.error("OCR failed: %s", e)
            return [], ""

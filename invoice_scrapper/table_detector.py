"""Table detection for line items using img2table + OpenCV."""

import logging
from io import BytesIO

import cv2
import numpy as np
import pytesseract
from PIL import Image

from img2table.document import Image as Img2TableImage
from img2table.ocr import TesseractOCR

logger = logging.getLogger(__name__)

OCR_LANG = "por"


class TableDetector:
    """Detect and extract tables from page images."""

    def __init__(self, lang: str = OCR_LANG):
        self.lang = lang
        self._tesseract_ocr = TesseractOCR(lang=lang, n_threads=1)

    def detect_tables(self, image: Image.Image) -> list[list[list[str]]]:
        """Detect tables in an image.

        Returns list of tables, each table is a 2D list of strings.
        """
        try:
            img2table_result = self._detect_with_img2table(image)
            opencv_result = self._detect_with_opencv(image)
            tables = self._choose_best(img2table_result, opencv_result)
            if not tables:
                tables = self._detect_borderless(image)
            return tables
        except Exception as e:
            logger.warning("Table detection failed: %s", e)
            return []

    def _detect_with_img2table(
        self, image: Image.Image
    ) -> list[list[list[str]]]:
        """Use img2table for primary table detection."""
        try:
            buf = BytesIO()
            image.save(buf, format="PNG")
            buf.seek(0)
            img = Img2TableImage(src=buf)
            extracted = img.extract_tables(
                ocr=self._tesseract_ocr,
                implicit_rows=True,
                implicit_columns=True,
                borderless_tables=True,
                min_confidence=0,
            )
            tables: list[list[list[str]]] = []
            for et in extracted:
                df = et.df
                if df is None or df.empty:
                    continue
                table = []
                for _, row in df.iterrows():
                    table.append([
                        str(v).strip() if v is not None and str(v) not in ("nan", "None") else ""
                        for v in row
                    ])
                tables.append(table)
            return tables
        except Exception as e:
            logger.warning("img2table detection failed: %s", e)
            return []

    def _detect_with_opencv(
        self, image: Image.Image
    ) -> list[list[list[str]]]:
        """Use OpenCV line detection to find table structure."""
        try:
            cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )

            # Detect horizontal lines
            h_len = max(30, gray.shape[1] // 40)
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
            h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=2)

            # Detect vertical lines
            v_len = max(30, gray.shape[0] // 40)
            v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))
            v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=2)

            grid = cv2.add(h_lines, v_lines)
            contours, _ = cv2.findContours(
                grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return []

            bounds = self._find_table_bounds(contours, gray.shape)
            tables: list[list[list[str]]] = []

            for x, y, w, h in bounds:
                cells = self._extract_grid_cells(
                    h_lines[y:y + h, x:x + w],
                    v_lines[y:y + h, x:x + w],
                    image, x, y, w, h,
                )
                if cells:
                    tables.append(cells)
            return tables
        except Exception as e:
            logger.warning("OpenCV detection failed: %s", e)
            return []

    def _find_table_bounds(
        self, contours: list, shape: tuple[int, int]
    ) -> list[tuple[int, int, int, int]]:
        """Find bounding rects of potential tables."""
        h, w = shape
        min_area = w * h * 0.005
        max_area = w * h * 0.98
        bounds: list[tuple[int, int, int, int]] = []

        for c in contours:
            bx, by, bw, bh = cv2.boundingRect(c)
            area = bw * bh
            if area < min_area or area > max_area:
                continue
            if bw < 100 or bh < 50:
                continue
            # Check overlap with existing
            dup = False
            for ex, ey, ew, eh in bounds:
                ox = max(0, min(bx + bw, ex + ew) - max(bx, ex))
                oy = max(0, min(by + bh, ey + eh) - max(by, ey))
                if ox * oy > 0.5 * min(area, ew * eh):
                    dup = True
                    break
            if not dup:
                bounds.append((bx, by, bw, bh))

        bounds.sort(key=lambda b: b[2] * b[3], reverse=True)
        return bounds[:5]

    def _extract_grid_cells(
        self,
        h_lines: np.ndarray,
        v_lines: np.ndarray,
        image: Image.Image,
        ox: int, oy: int, tw: int, th: int,
    ) -> list[list[str]]:
        """Extract cell text from a grid region."""
        h_pos = self._find_line_positions(np.sum(h_lines, axis=1))
        v_pos = self._find_line_positions(np.sum(v_lines, axis=0))

        if len(h_pos) < 2 or len(v_pos) < 2:
            return []

        rows: list[list[str]] = []
        for ri in range(len(h_pos) - 1):
            row: list[str] = []
            for ci in range(len(v_pos) - 1):
                y1, y2 = h_pos[ri] + 3, h_pos[ri + 1] - 3
                x1, x2 = v_pos[ci] + 3, v_pos[ci + 1] - 3
                if x2 <= x1 or y2 <= y1:
                    row.append("")
                    continue
                cell_img = image.crop((ox + x1, oy + y1, ox + x2, oy + y2))
                try:
                    text = pytesseract.image_to_string(
                        cell_img, lang=self.lang
                    ).strip()
                except Exception:
                    text = ""
                row.append(text)
            rows.append(row)
        return rows

    def _find_line_positions(
        self, projection: np.ndarray, min_gap: int = 15
    ) -> list[int]:
        """Find line positions from projection profile."""
        threshold = np.max(projection) * 0.3
        above = projection > threshold
        positions: list[int] = []
        in_peak = False
        start = 0

        for i, val in enumerate(above):
            if val and not in_peak:
                in_peak = True
                start = i
            elif not val and in_peak:
                in_peak = False
                center = (start + i) // 2
                if not positions or center - positions[-1] >= min_gap:
                    positions.append(center)

        if positions and positions[0] > min_gap:
            positions.insert(0, 0)
        if positions and positions[-1] < len(projection) - min_gap:
            positions.append(len(projection) - 1)
        return positions

    def _detect_borderless(
        self, image: Image.Image
    ) -> list[list[list[str]]]:
        """Detect borderless tables via text alignment analysis."""
        try:
            data = pytesseract.image_to_data(
                image, lang=self.lang, output_type=pytesseract.Output.DICT
            )
            # Collect text regions
            regions: list[tuple[int, int, int, int, str]] = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                conf = float(data["conf"][i])
                if not text or conf < 0:
                    continue
                regions.append((
                    data["left"][i], data["top"][i],
                    data["width"][i], data["height"][i], text,
                ))

            if len(regions) < 6:
                return []

            # Group into rows by y-position
            avg_h = sum(r[3] for r in regions) / len(regions)
            sorted_r = sorted(regions, key=lambda r: r[1])
            rows: list[list[tuple[int, int, int, int, str]]] = []
            cur_row = [sorted_r[0]]
            cur_y = sorted_r[0][1]

            for r in sorted_r[1:]:
                if abs(r[1] - cur_y) <= avg_h * 0.5:
                    cur_row.append(r)
                else:
                    rows.append(sorted(cur_row, key=lambda x: x[0]))
                    cur_row = [r]
                    cur_y = r[1]
            if cur_row:
                rows.append(sorted(cur_row, key=lambda x: x[0]))

            if len(rows) < 3:
                return []

            # Detect columns by clustering x-positions
            all_x = sorted(r[0] for row in rows for r in row)
            avg_w = sum(r[2] for row in rows for r in row) / sum(
                len(row) for row in rows
            )
            cols = [all_x[0]]
            for x in all_x[1:]:
                if x - cols[-1] > avg_w * 0.3:
                    cols.append(x)

            if len(cols) < 2:
                return []

            # Build table
            table: list[list[str]] = []
            for row in rows:
                cells = [""] * len(cols)
                for r in row:
                    # Find closest column
                    ci = min(range(len(cols)), key=lambda i: abs(r[0] - cols[i]))
                    if cells[ci]:
                        cells[ci] += " " + r[4]
                    else:
                        cells[ci] = r[4]
                table.append(cells)

            return [table]
        except Exception as e:
            logger.warning("Borderless detection failed: %s", e)
            return []

    @staticmethod
    def _choose_best(
        a: list[list[list[str]]], b: list[list[list[str]]]
    ) -> list[list[list[str]]]:
        """Choose the table set with more content cells."""
        if not a and not b:
            return []
        if not a:
            return b
        if not b:
            return a

        def content_count(tables: list[list[list[str]]]) -> int:
            return sum(
                1 for t in tables for row in t for cell in row if cell.strip()
            )

        ca, cb = content_count(a), content_count(b)
        return b if cb > ca * 1.2 else a

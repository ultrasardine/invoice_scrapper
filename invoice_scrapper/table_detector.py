"""Table detection using positional word data from OCR."""

import logging
import re
import unicodedata

from invoice_scrapper.pdf_reader import Word

logger = logging.getLogger(__name__)

# Keywords that identify table header columns (normalized)
_HEADER_KEYWORDS: dict[str, str] = {
    "referencia": "referência",
    "ref": "referência",
    "codigo": "referência",
    "artigo": "referência",
    "descricao": "descrição",
    "designacao": "descrição",
    "produto": "descrição",
    "qtd": "qtd",
    "quantidade": "qtd",
    "qty": "qtd",
    "quant": "qtd",
    "uni": "uni",
    "unidade": "uni",
    "p.unit": "p.unit",
    "preco": "p.unit",
    "unitario": "p.unit",
    "unit": "p.unit",
    "s/imp": "p.unit",
    "desc": "desconto",
    "desc1": "desconto",
    "desc1+2": "desconto",
    "desconto": "desconto",
    "taxa": "taxa",
    "iva": "iva",
    "total": "total",
    "valor": "total",
    "montante": "total",
}

# Minimum number of recognized header keywords to consider a row as header
_MIN_HEADER_MATCHES = 3

# End-of-table markers (normalized)
_END_MARKERS = [
    "observa", "resumo", "imposto", "desconto global",
    "liquido", "conta corrente", "incidencia",
    "artigos faturados", "colocados", "disposicao",
    "software", "processado por programa",
]

_MONEY_RE = re.compile(r"^\d[\d.]*,\d{2}$|^\d[\d,]*\.\d{2}$")


def _normalize(text: str) -> str:
    """Remove accents and lowercase."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _group_into_rows(
    words: list[Word], tolerance: int = 25
) -> list[list[Word]]:
    """Group words into rows by y-position."""
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: (w.top, w.left))
    rows: list[list[Word]] = []
    current_row: list[Word] = [sorted_words[0]]
    current_y = sorted_words[0].center_y

    for w in sorted_words[1:]:
        if abs(w.center_y - current_y) <= tolerance:
            current_row.append(w)
        else:
            rows.append(sorted(current_row, key=lambda x: x.left))
            current_row = [w]
            current_y = w.center_y

    if current_row:
        rows.append(sorted(current_row, key=lambda x: x.left))

    return rows


def _match_header_keyword(text: str) -> str | None:
    """Match a word to a header keyword, return canonical name."""
    norm = _normalize(text).rstrip(".:()%*")
    if len(norm) < 2:
        return None
    # Direct match
    if norm in _HEADER_KEYWORDS:
        return _HEADER_KEYWORDS[norm]
    # Partial match - keyword must be substantial part of the word
    for kw, canonical in _HEADER_KEYWORDS.items():
        if len(kw) >= 3 and kw in norm:
            return canonical
    return None


def _find_header_row(
    rows: list[list[Word]],
) -> tuple[int | None, list[tuple[int, int, str]]]:
    """Find the header row and extract meaningful column positions.

    Returns (row_index, columns) where columns is list of
    (x_center, x_right, canonical_name).
    """
    for i, row in enumerate(rows):
        columns: list[tuple[int, int, str]] = []
        seen_canonicals: set[str] = set()

        for w in row:
            canonical = _match_header_keyword(w.text)
            if canonical and canonical not in seen_canonicals:
                columns.append((
                    w.left + w.width // 2,
                    w.right,
                    canonical,
                ))
                seen_canonicals.add(canonical)

        if len(columns) >= _MIN_HEADER_MATCHES:
            return i, columns

    return None, []


def _assign_to_column(
    word: Word, columns: list[tuple[int, int, str]]
) -> int | None:
    """Find which column a word belongs to based on x-position."""
    word_center = word.left + word.width // 2
    best_col = None
    best_dist = float("inf")

    for i, (col_center, _, _) in enumerate(columns):
        dist = abs(word_center - col_center)
        if dist < best_dist:
            best_dist = dist
            best_col = i

    # Max distance depends on column spacing
    if len(columns) >= 2:
        avg_spacing = (columns[-1][0] - columns[0][0]) / (len(columns) - 1)
        max_dist = avg_spacing * 0.6
    else:
        max_dist = 300

    if best_col is not None and best_dist < max_dist:
        return best_col
    return None


def _is_data_row(row: list[Word], header_y: int) -> bool:
    """Check if a row is a data row."""
    if not row:
        return False
    if row[0].top <= header_y:
        return False
    if len(row) < 2:
        return False
    # Must have at least one number
    return any(any(c.isdigit() for c in w.text) for w in row)


def _is_end_of_table(row: list[Word]) -> bool:
    """Detect end of table."""
    row_text = _normalize(" ".join(w.text for w in row))
    return any(m in row_text for m in _END_MARKERS)


def _is_sub_row(row: list[Word], prev_row: list[Word] | None) -> bool:
    """Check if row is a continuation/sub-row (e.g., 'Tamanho: L')."""
    if not row:
        return True
    # If row starts much further right than typical data rows, it's a sub-row
    row_text = " ".join(w.text for w in row)
    # Sub-rows typically have few words and no money values
    if len(row) <= 3 and not any(_MONEY_RE.match(w.text) for w in row):
        # Check if it looks like a label: value pair
        if ":" in row_text or "matricula" in _normalize(row_text):
            return True
    return False


def detect_tables(words: list[Word]) -> list[list[list[str]]]:
    """Detect tables from positional word data.

    Returns list of tables, each table is a 2D list of strings.
    """
    if not words:
        return []

    rows = _group_into_rows(words)
    header_idx, columns = _find_header_row(rows)

    if header_idx is None or not columns:
        return []

    header_y = rows[header_idx][0].top
    header_texts = [col[2] for col in columns]

    # Extract data rows
    table: list[list[str]] = [header_texts]

    for row in rows[header_idx + 1:]:
        if _is_end_of_table(row):
            break
        if not _is_data_row(row, header_y):
            continue
        if _is_sub_row(row, None):
            continue

        # Assign each word to a column
        cells = [""] * len(columns)
        for w in row:
            # Skip obvious noise
            if w.text in ("|", "'", '"', "—", "-") and len(w.text) <= 1:
                continue
            col_idx = _assign_to_column(w, columns)
            if col_idx is not None:
                if cells[col_idx]:
                    cells[col_idx] += " " + w.text
                else:
                    cells[col_idx] = w.text

        # Only add if at least 2 cells have content
        filled = sum(1 for c in cells if c.strip())
        if filled >= 2:
            table.append(cells)

    if len(table) < 2:
        return []

    return [table]


class TableDetector:
    """Detect and extract tables from page word data."""

    def __init__(self, lang: str = "por"):
        self.lang = lang

    def detect_tables_from_words(
        self, words: list[Word]
    ) -> list[list[list[str]]]:
        """Detect tables using positional word data."""
        return detect_tables(words)

    def detect_tables(self, image) -> list[list[list[str]]]:
        """Legacy interface - detect tables from image."""
        import pytesseract
        from PIL import Image as PILImage

        if not isinstance(image, PILImage.Image):
            return []

        try:
            data = pytesseract.image_to_data(
                image, lang=self.lang, output_type=pytesseract.Output.DICT
            )
            words: list[Word] = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                if not text or int(data["conf"][i]) < 0:
                    continue
                words.append(Word(
                    text=text,
                    left=data["left"][i],
                    top=data["top"][i],
                    width=data["width"][i],
                    height=data["height"][i],
                ))
            return detect_tables(words)
        except Exception as e:
            logger.warning("Table detection failed: %s", e)
            return []

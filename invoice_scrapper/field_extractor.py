"""Field extraction using positional word data from OCR."""

import re
import unicodedata

from invoice_scrapper.pdf_reader import Word

# Regex patterns for value validation
_DATE_RE = re.compile(r"\d{4}[-/.]\d{2}[-/.]\d{2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}")
_MONEY_RE = re.compile(r"\d[\d\s.]*,\d{2}|\d[\d\s,]*\.\d{2}")
_INVOICE_NUM_RE = re.compile(r"[\w/\-]+")

# Field names (normalised) that map to the total-amount extractor.
# Only these specific names are special-cased; arbitrary custom fields that
# happen to contain "preco" or "total" fall through to the generic extractor.
_TOTAL_FIELDS: frozenset[str] = frozenset({
    "preco total sem iva",
    "preco total",
    "total sem iva",
    "total com iva",
})


def _normalize(text: str) -> str:
    """Remove accents and lowercase for matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _same_line(a: Word, b: Word, tolerance: int = 20) -> bool:
    """Check if two words are on the same line."""
    return abs(a.center_y - b.center_y) <= tolerance


def _words_to_right(
    anchor: Word, words: list[Word], max_dist: int = 800
) -> list[Word]:
    """Get words to the right of anchor on the same line."""
    return sorted(
        [
            w for w in words
            if _same_line(anchor, w)
            and w.left > anchor.right
            and w.left - anchor.right < max_dist
        ],
        key=lambda w: w.left,
    )


def _words_below(
    anchor: Word, words: list[Word], max_dist: int = 80
) -> list[Word]:
    """Get words directly below anchor (same x region)."""
    return sorted(
        [
            w for w in words
            if w.top > anchor.bottom
            and w.top - anchor.bottom < max_dist
            and abs(w.left - anchor.left) < 150
        ],
        key=lambda w: w.top,
    )


def _find_words_matching(
    words: list[Word], patterns: list[str]
) -> list[Word]:
    """Find words whose normalized text contains any pattern."""
    results = []
    for w in words:
        norm = _normalize(w.text).rstrip(".:,")
        if len(norm) < 3:
            continue
        for p in patterns:
            if p in norm:
                results.append(w)
                break
    return results


def _find_sequence(
    words: list[Word], sequence: list[str]
) -> Word | None:
    """Find a sequence of words (e.g., ['fatura', 'n']) and return the last."""
    for i, w in enumerate(words):
        norm = _normalize(w.text).rstrip(":").rstrip("º")
        if sequence[0] in norm:
            # Check remaining words in sequence on same line
            matched = True
            last = w
            for s in sequence[1:]:
                right = _words_to_right(last, words, max_dist=200)
                found = False
                for r in right:
                    if s in _normalize(r.text).rstrip(":").rstrip("º"):
                        last = r
                        found = True
                        break
                if not found:
                    matched = False
                    break
            if matched:
                return last
    return None


def _extract_value_right(
    label: Word, words: list[Word], pattern: re.Pattern[str] | None = None
) -> str:
    """Extract value from words to the right of a label."""
    right = _words_to_right(label, words)
    if not right:
        return ""
    text = " ".join(w.text for w in right)
    if pattern:
        # Clean common OCR artifacts before matching
        clean = text.replace('"', '').replace('"', '').replace('"', '')
        m = pattern.search(clean)
        return m.group(0) if m else ""
    return right[0].text


def _extract_value_below(
    label: Word, words: list[Word], pattern: re.Pattern[str] | None = None
) -> str:
    """Extract value from words below a label."""
    below = _words_below(label, words)
    if not below:
        return ""
    text = " ".join(w.text for w in below)
    if pattern:
        m = pattern.search(text)
        return m.group(0) if m else ""
    return below[0].text


def _extract_supplier(words: list[Word]) -> str:
    """Extract supplier name - typically the first prominent text block.

    Strategy: Company suffix (LDA, S.A.) is most reliable when present.
    Otherwise use the largest text at the very top.
    """
    if not words:
        return ""

    max_y = max(w.bottom for w in words)
    top_words = [w for w in words if w.top < max_y * 0.25]

    skip_words = {
        "fatura", "serie", "tipo", "saft", "nº", "nr", "de", "do", "da",
        "natureza", "pagina", "página", "software", "processado", "even",
        "fax", "tel", "email", "www", "http",
    }

    # Strategy 1: Find company suffixes (LDA, S.A., etc.) - most reliable
    company_suffixes = ["lda", "s.a.", "sa", "unipessoal", "limitada"]
    for w in sorted(top_words, key=lambda x: x.top):
        norm = _normalize(w.text).rstrip(".,")
        if norm in company_suffixes:
            line_words = sorted(
                [
                    lw for lw in top_words
                    if _same_line(lw, w) and lw.left <= w.right
                    and len(lw.text) > 1 and lw.text not in ("|", "'", '"')
                ],
                key=lambda x: x.left,
            )
            name = " ".join(lw.text for lw in line_words).strip(",. ")
            # If name starts with "de:" it's a sub-name, look above
            if name.lower().startswith("de:") or name.lower().startswith("de "):
                # Look for the main company name above this line
                above = [
                    aw for aw in top_words
                    if aw.bottom < w.top
                    and len(aw.text) > 4
                    and aw.text[0].isalpha()
                    and aw.height > 30
                ]
                if above:
                    best = max(above, key=lambda x: x.height)
                    return best.text
            if len(name) > 3:
                return name

    # Strategy 2: Find the word with largest height in top 10%
    # Filter out OCR noise (quotes, brackets, single chars)
    very_top = [w for w in words if w.top < max_y * 0.10]
    name_candidates = [
        w for w in very_top
        if len(w.text) > 4
        and w.height > 30
        and w.text[0].isalpha()
        and _normalize(w.text).rstrip(".:,") not in skip_words
        and not w.text.startswith("http")
        and not w.text.startswith("www")
        and not w.text.startswith('"')
        and not w.text.startswith("'")
    ]
    if name_candidates:
        best = max(name_candidates, key=lambda w: w.height)
        line_words = sorted(
            [
                lw for lw in very_top
                if _same_line(lw, best)
                and len(lw.text) > 1
                and lw.text[0].isalpha()
                and lw.text not in ("|", "'", '"')
            ],
            key=lambda x: x.left,
        )
        name = " ".join(lw.text for lw in line_words).strip(",. ")
        if len(name) > 3:
            return name

    return ""


def _extract_invoice_number(words: list[Word]) -> str:
    """Extract invoice number - find 'Fatura' + 'Nº' or 'Série' label."""
    result = ""

    # Try "Fatura Nº:" pattern
    label = _find_sequence(words, ["fatura", "n"])
    if label:
        right = _words_to_right(label, words)
        if right:
            parts = []
            for w in right:
                if _INVOICE_NUM_RE.match(w.text):
                    parts.append(w.text)
                else:
                    break
            if parts:
                result = " ".join(parts)

    # Try "Série" pattern (e.g., "Fatura Série 1/12425")
    if not result:
        serie_words = _find_words_matching(words, ["serie"])
        for sw in serie_words:
            right = _words_to_right(sw, words, max_dist=400)
            if right:
                parts = []
                for w in right:
                    if _INVOICE_NUM_RE.match(w.text):
                        parts.append(w.text)
                    else:
                        break
                if parts:
                    result = " ".join(parts)
                    break

    # If result is too short or looks incomplete, try ATCUD
    if len(result) <= 3:
        for w in words:
            if not w.text.upper().startswith("ATCUD"):
                continue
            # The code may be embedded in the same token ("ATCUD:XXXX-1234")
            # or it may be in a separate token to the right ("ATCUD:" "XXXX-1234").
            remainder = ""
            if ":" in w.text:
                remainder = w.text[w.text.index(":") + 1:].strip()
            if not remainder:
                right = _words_to_right(w, words)
                if right:
                    remainder = right[0].text.strip()
            if not remainder:
                continue
            parts = remainder.split("-")
            if len(parts) >= 2 and len(parts[-1]) > 0:
                atcud_num = parts[-1]
                # Combine with série if available
                if result:
                    return f"{result}{atcud_num}"
                return atcud_num

    return result


def _extract_date(words: list[Word]) -> str:
    """Extract invoice date.

    Strategy: Find 'DATA EMISSÃO' or 'Data' header, get value below/right.
    """
    # Try "DATA EMISSÃO" header with value below
    emissao_words = _find_words_matching(words, ["emissao"])
    for ew in emissao_words:
        # Look for date below this header
        below = _words_below(ew, words, max_dist=120)
        for bw in below:
            m = _DATE_RE.search(bw.text.replace('"', '').replace('"', ''))
            if m:
                return m.group(0)
        # Also check to the right on same line
        right = _words_to_right(ew, words, max_dist=400)
        for rw in right:
            m = _DATE_RE.search(rw.text.replace('"', '').replace('"', ''))
            if m:
                return m.group(0)

    # Fallback: find any date near "colocados à disposição" text
    disp_words = _find_words_matching(words, ["disposicao"])
    for dw in disp_words:
        right = _words_to_right(dw, words, max_dist=600)
        for rw in right:
            m = _DATE_RE.search(rw.text)
            if m:
                return m.group(0)

    # Last resort: find first date-like value in the document
    for w in words:
        m = _DATE_RE.fullmatch(w.text.replace('"', '').replace('"', ''))
        if m:
            return m.group(0)

    return ""


def _extract_total(words: list[Word]) -> str:
    """Extract total amount (pre-tax / base incidência).

    Strategy: Find 'TOTAL' or 'Base Incidência' or 'Ilíquido', get money value.
    """
    if not words:
        return ""

    max_y = max(w.bottom for w in words)

    # Strategy 1: Find "Base Incidência" or "Total Ilíquido" (pre-tax total)
    base_words = _find_words_matching(words, ["incidencia", "iliquido"])
    for bw in base_words:
        # Look below for money value
        below = _words_below(bw, words, max_dist=150)
        for w in below:
            clean = w.text.replace("€", "").replace(" ", "").strip()
            if _MONEY_RE.match(clean):
                return clean
        # Look to the right
        right = _words_to_right(bw, words, max_dist=400)
        for w in right:
            clean = w.text.replace("€", "").replace(" ", "").strip()
            if _MONEY_RE.match(clean):
                return clean

    # Strategy 2: Find "TOTAL" with € symbol or money value nearby
    total_words = [
        w for w in words
        if "total" in _normalize(w.text) and w.top > max_y * 0.4
    ]
    # Sort by y position (bottom-most first)
    total_words.sort(key=lambda w: w.top, reverse=True)

    for tw in total_words:
        right = _words_to_right(tw, words, max_dist=600)
        for rw in right:
            clean = rw.text.replace("€", "").replace(" ", "").strip()
            if _MONEY_RE.match(clean):
                return clean
        below = _words_below(tw, words, max_dist=120)
        for bw in below:
            clean = bw.text.replace("€", "").replace(" ", "").strip()
            if _MONEY_RE.match(clean):
                return clean

    return ""


def _extract_fields_from_text(
    text: str,
    fields: list[str],
    context_window: int = 200,
) -> dict[str, str]:
    """Extract fields from plain text when no positional word data is available."""
    result: dict[str, str] = {}
    norm_text = _normalize(text)

    for field_name in fields:
        norm_field = _normalize(field_name)

        if norm_field in ("preco unitario do artigo", "quantidade"):
            result[field_name] = ""
            continue

        # Find the longest keyword (>3 chars) from the field name in the text
        field_keywords = sorted(
            [kw for kw in norm_field.split() if len(kw) > 3],
            key=len, reverse=True,
        )
        found = ""
        for kw in field_keywords:
            idx = norm_text.find(kw)
            if idx < 0:
                continue
            # Map back to original text position and grab a context window
            snippet = text[idx: idx + context_window]
            # Try date pattern
            m = _DATE_RE.search(snippet)
            if m and m.start() > 0:
                found = m.group(0)
                break
            # Try money pattern
            m = _MONEY_RE.search(snippet)
            if m and m.start() > 0:
                found = m.group(0)
                break
            # Try first token after a colon or whitespace
            m = re.search(r"[:\s]+(\S+)", snippet)
            if m:
                candidate = m.group(1).strip(".,;:")
                if len(candidate) > 1:
                    found = candidate
                    break

        result[field_name] = found

    return result


def extract_fields(
    text: str,
    fields: list[str],
    words: list[Word] | None = None,
    context_window: int = 200,
) -> dict[str, str]:
    """Extract field values from invoice.

    Uses positional word data when available, falls back to text search.

    Args:
        text: Full invoice text (used as fallback).
        fields: List of field labels to search for.
        words: Positional word data from OCR.
        context_window: Chars after keyword for text fallback.

    Returns:
        Dict mapping field names to extracted values.
    """
    if not words:
        # No positional data – fall back to plain-text extraction
        return _extract_fields_from_text(text, fields, context_window)

    result: dict[str, str] = {}

    for field_name in fields:
        norm_field = _normalize(field_name)

        if norm_field in ("preco unitario do artigo", "quantidade"):
            result[field_name] = ""
        elif "fornecedor" in norm_field:
            result[field_name] = _extract_supplier(words)
        elif "numero da fatura" in norm_field and "imputacao" not in norm_field:
            result[field_name] = _extract_invoice_number(words)
        elif "data" in norm_field and "fatura" in norm_field:
            result[field_name] = _extract_date(words)
        elif norm_field in _TOTAL_FIELDS:
            result[field_name] = _extract_total(words)
        else:
            # Generic: find the label and collect all value words to the right
            result[field_name] = _generic_field_extract(
                words, norm_field
            )

    return result


def _generic_field_extract(words: list[Word], norm_field: str) -> str:
    """Generic extraction: find label words, get all value words to the right."""
    field_words = set(norm_field.split())
    # Find the longest matching word (>3 chars) in the document
    for fw in sorted(field_words, key=len, reverse=True):
        if len(fw) <= 3:
            continue
        matches = _find_words_matching(words, [fw])
        for m in matches:
            right = _words_to_right(m, words)
            if right:
                # Collect all non-label words on the same line
                value_parts = [
                    r.text for r in right
                    if _normalize(r.text).rstrip(".:,") not in field_words
                ]
                if value_parts:
                    return " ".join(value_parts)
    return ""

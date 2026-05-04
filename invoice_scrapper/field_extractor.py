"""Field extraction using keyword proximity + regex patterns."""

import re
import unicodedata

# Context window size (chars after keyword match)
CONTEXT_WINDOW = 200

# Regex patterns for specific field types
_DATE_RE = re.compile(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}")
_MONEY_RE = re.compile(r"\d[\d\s.]*,\d{2}|\d[\d\s,]*\.\d{2}")
_ALPHANUM_RE = re.compile(r"[\w\-/]+(?:\s[\w\-/]+){0,3}")
_LINE_VALUE_RE = re.compile(r"[:\s]+(.+)")

# Map of field name keywords to their value extraction pattern
_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "data": _DATE_RE,
    "preço": _MONEY_RE,
    "total": _MONEY_RE,
    "número": _ALPHANUM_RE,
    "referência": _ALPHANUM_RE,
    "guia": _ALPHANUM_RE,
    "imputação": _ALPHANUM_RE,
}


def _normalize(text: str) -> str:
    """Remove accents and lowercase for matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _get_pattern(field_name: str) -> re.Pattern[str]:
    """Get the regex pattern for a field based on its name keywords."""
    norm = _normalize(field_name)
    for keyword, pattern in _FIELD_PATTERNS.items():
        if _normalize(keyword) in norm:
            return pattern
    return _LINE_VALUE_RE


def extract_fields(
    text: str, fields: list[str], context_window: int = CONTEXT_WINDOW
) -> dict[str, str]:
    """Extract field values from text using keyword proximity + regex.

    Args:
        text: Full invoice text.
        fields: List of field labels to search for.
        context_window: Number of chars after keyword to search.

    Returns:
        Dict mapping field names to extracted values (empty if not found).
    """
    result: dict[str, str] = {}
    norm_text = _normalize(text)

    for field_name in fields:
        # Skip per-item fields (handled by table detector)
        norm_field = _normalize(field_name)
        if norm_field in ("preco unitario do artigo", "quantidade"):
            result[field_name] = ""
            continue

        # Find the field label in the text
        pos = norm_text.find(norm_field)
        if pos == -1:
            # Try shorter variants
            for word in norm_field.split():
                if len(word) > 3:
                    pos = norm_text.find(word)
                    if pos != -1:
                        break

        if pos == -1:
            result[field_name] = ""
            continue

        # Extract context window after the keyword
        start = pos + len(norm_field)
        context = text[start:start + context_window]

        # Apply field-specific regex
        pattern = _get_pattern(field_name)
        match = pattern.search(context)
        if match:
            value = match.group(0).strip().strip(":")
            # For LINE_VALUE_RE, use group 1 if available
            if pattern is _LINE_VALUE_RE and match.lastindex:
                value = match.group(1).strip()
            # Clean up: take first line only
            value = value.split("\n")[0].strip()
            result[field_name] = value
        else:
            result[field_name] = ""

    return result

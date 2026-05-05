"""Tests for table detector module."""

from invoice_scrapper.pdf_reader import Word
from invoice_scrapper.table_detector import (
    TableDetector,
    detect_tables,
    _group_into_rows,
    _find_header_row,
    _match_header_keyword,
    _is_end_of_table,
)


def _make_words(lines: list[list[tuple[str, int, int]]]) -> list[Word]:
    """Create Word objects from (text, x, y) tuples grouped by line."""
    words = []
    for line in lines:
        for text, x, y in line:
            words.append(Word(
                text=text, left=x, top=y,
                width=len(text) * 10, height=25,
            ))
    return words


def test_detect_tables_with_header_and_data():
    words = _make_words([
        [("REFERÊNCIA", 100, 100), ("DESCRIÇÃO", 400, 100),
         ("QTD.", 800, 100), ("P.UNIT", 1000, 100), ("TOTAL", 1200, 100)],
        [("601025", 100, 160), ("Caneleiras", 400, 160),
         ("1,00", 800, 160), ("211,68", 1000, 160), ("186,28", 1200, 160)],
    ])
    tables = detect_tables(words)
    assert len(tables) == 1
    assert len(tables[0]) == 2  # header + 1 data row
    assert "referência" in tables[0][0][0]


def test_detect_tables_no_header():
    words = _make_words([
        [("random", 100, 100), ("text", 300, 100), ("here", 500, 100)],
        [("more", 100, 160), ("stuff", 300, 160), ("123", 500, 160)],
    ])
    tables = detect_tables(words)
    assert tables == []


def test_detect_tables_empty_words():
    assert detect_tables([]) == []


def test_end_of_table_detection():
    words = _make_words([
        [("OBSERVAÇÕES", 100, 500)],
    ])
    rows = _group_into_rows(words)
    assert _is_end_of_table(rows[0])


def test_end_of_table_resumo():
    words = _make_words([
        [("RESUMO", 100, 500), ("DE", 250, 500), ("IMPOSTOS", 300, 500)],
    ])
    rows = _group_into_rows(words)
    assert _is_end_of_table(rows[0])


def test_group_into_rows():
    words = _make_words([
        [("a", 100, 100), ("b", 200, 105)],  # Same row (within tolerance)
        [("c", 100, 200), ("d", 200, 200)],  # Different row
    ])
    rows = _group_into_rows(words)
    assert len(rows) == 2
    assert len(rows[0]) == 2
    assert len(rows[1]) == 2


def test_find_header_row():
    words = _make_words([
        [("Some", 100, 50), ("text", 200, 50)],
        [("REFERÊNCIA", 100, 100), ("QTD.", 400, 100), ("P.UNIT", 600, 100)],
        [("601025", 100, 160), ("1,00", 400, 160), ("50,00", 600, 160)],
    ])
    rows = _group_into_rows(words)
    idx, columns = _find_header_row(rows)
    assert idx == 1
    assert len(columns) >= 3


def test_match_header_keyword():
    assert _match_header_keyword("REFERÊNCIA") == "referência"
    assert _match_header_keyword("QTD.") == "qtd"
    assert _match_header_keyword("P.Unit.") == "p.unit"
    assert _match_header_keyword("Designação") == "descrição"
    assert _match_header_keyword("TOTAL") == "total"
    assert _match_header_keyword("IVA") == "iva"
    assert _match_header_keyword("(%)") is None  # Too short after strip
    assert _match_header_keyword("N") is None  # Too short
    assert _match_header_keyword("'") is None


def test_table_detector_class_from_words():
    words = _make_words([
        [("REFERÊNCIA", 100, 100), ("QTD.", 400, 100), ("P.UNIT", 600, 100)],
        [("ABC123", 100, 160), ("5", 400, 160), ("10,00", 600, 160)],
    ])
    detector = TableDetector()
    tables = detector.detect_tables_from_words(words)
    assert len(tables) == 1


def test_multiple_data_rows():
    words = _make_words([
        [("REFERÊNCIA", 100, 100), ("QTD.", 400, 100), ("P.UNIT", 600, 100)],
        [("ABC123", 100, 160), ("5", 400, 160), ("10,00", 600, 160)],
        [("DEF456", 100, 220), ("3", 400, 220), ("20,00", 600, 220)],
    ])
    tables = detect_tables(words)
    assert len(tables) == 1
    assert len(tables[0]) == 3  # header + 2 data rows


def test_stops_at_end_marker():
    words = _make_words([
        [("REFERÊNCIA", 100, 100), ("QTD.", 400, 100), ("P.UNIT", 600, 100)],
        [("ABC123", 100, 160), ("5", 400, 160), ("10,00", 600, 160)],
        [("OBSERVAÇÕES", 100, 220)],
        [("DEF456", 100, 280), ("3", 400, 280), ("20,00", 600, 280)],
    ])
    tables = detect_tables(words)
    assert len(tables) == 1
    assert len(tables[0]) == 2  # header + 1 row (stopped at OBSERVAÇÕES)

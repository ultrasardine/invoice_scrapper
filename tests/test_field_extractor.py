"""Tests for field extractor module."""

from invoice_scrapper.field_extractor import (
    extract_fields,
    _normalize,
    _extract_supplier,
    _extract_invoice_number,
    _extract_date,
    _extract_total,
)
from invoice_scrapper.pdf_reader import Word


def _make_words(lines: list[list[tuple[str, int, int]]]) -> list[Word]:
    """Create Word objects from (text, x, y) tuples grouped by line."""
    words = []
    for line in lines:
        for text, x, y in line:
            words.append(Word(
                text=text, left=x, top=y,
                width=len(text) * 10, height=30,
            ))
    return words


# Simulate a typical invoice layout with positional data
SAMPLE_WORDS = _make_words([
    # Supplier line (top of page, large font)
    [("Empresa", 100, 50), ("ABC", 220, 50), ("Lda", 300, 50)],
    # Invoice number
    [("Fatura", 100, 150), ("Nº:", 200, 150), ("FT", 280, 150), ("2024/1234", 320, 150)],
    # Date
    [("DATA", 100, 250), ("EMISSÃO", 200, 250)],
    [("15/03/2024", 100, 310)],
    # Total
    [("Base", 100, 2500), ("Incidência", 180, 2500)],
    [("1.250,00", 100, 2570)],
    # Imputação
    [("imputação", 100, 400), ("IMP-2024-001", 250, 400)],
    # Referência
    [("referência", 100, 450), ("REF-456", 250, 450)],
    # Guia
    [("guia", 100, 500), ("remessa", 170, 500), ("GR-789/2024", 300, 500)],
    # Cliente
    [("cliente", 100, 550), ("entrega", 200, 550), ("Armazém", 320, 550)],
])


def test_extract_fornecedor():
    # Supplier with LDA suffix - need enough words to make page "tall"
    words = _make_words([
        [("LUSO", 100, 50), ("PROMOVE,", 200, 50), ("LDA", 350, 50)],
        [("other", 100, 3000), ("content", 200, 3000)],  # Makes page tall
    ])
    result = _extract_supplier(words)
    assert "LUSO" in result
    assert "LDA" in result


def test_extract_numero_fatura():
    words = _make_words([
        [("Fatura", 100, 150), ("Nº:", 200, 150), ("FAC", 280, 150), ("3/243", 340, 150)],
    ])
    result = _extract_invoice_number(words)
    assert "FAC" in result
    assert "3/243" in result


def test_extract_data_fatura():
    words = _make_words([
        [("DATA", 100, 250), ("EMISSÃO", 200, 250)],
        [("2025-10-28", 100, 310)],
    ])
    result = _extract_date(words)
    assert "2025-10-28" in result


def test_extract_preco_total():
    words = _make_words([
        [("Base", 100, 2500), ("Incidência", 180, 2500)],
        [("186,28", 100, 2570)],
    ])
    result = _extract_total(words)
    assert "186,28" in result


def test_extract_imputacao():
    # Test generic extraction with unique keyword
    words = _make_words([
        [("imputação", 100, 400), ("IMP-2024-001", 250, 400)],
        [("other", 100, 3000)],
    ])
    result = extract_fields("", ["número da imputação da fatura"], words=words)
    assert result["número da imputação da fatura"] == "IMP-2024-001"


def test_extract_referencia():
    result = extract_fields("", ["referência nessa imputação"], words=SAMPLE_WORDS)
    assert result["referência nessa imputação"] == "REF-456"


def test_extract_guia_remessa():
    result = extract_fields("", ["número da guia de remessa"], words=SAMPLE_WORDS)
    val = result["número da guia de remessa"]
    assert "GR-789/2024" in val


def test_extract_cliente():
    result = extract_fields("", ["cliente ou local de entrega"], words=SAMPLE_WORDS)
    val = result["cliente ou local de entrega"]
    assert val != ""


def test_missing_field_returns_empty():
    words = _make_words([[("random", 100, 100), ("text", 200, 100)]])
    result = extract_fields("", ["número da fatura"], words=words)
    assert result["número da fatura"] == ""


def test_case_insensitive():
    # _normalize handles case
    assert _normalize("FORNECEDOR") == "fornecedor"
    assert _normalize("Número") == "numero"


def test_accent_insensitive():
    assert _normalize("Número") == "numero"
    assert _normalize("Referência") == "referencia"


def test_per_item_fields_skipped():
    result = extract_fields("", ["preço unitário do artigo", "quantidade"], words=SAMPLE_WORDS)
    assert result["preço unitário do artigo"] == ""
    assert result["quantidade"] == ""


def test_normalize():
    assert _normalize("Número") == "numero"
    assert _normalize("Preço") == "preco"
    assert _normalize("Referência") == "referencia"


def test_all_default_fields():
    from invoice_scrapper.config import DEFAULT_FIELDS
    result = extract_fields("", DEFAULT_FIELDS, words=SAMPLE_WORDS)
    assert len(result) == len(DEFAULT_FIELDS)
    assert result["preço unitário do artigo"] == ""
    assert result["quantidade"] == ""


def test_no_words_returns_empty():
    result = extract_fields("text", ["fornecedor"])
    assert result["fornecedor"] == ""


def test_supplier_largest_font_at_top():
    """When no LDA suffix, pick largest font word at top."""
    words = [
        Word(text="VASILPNEUS", left=200, top=70, width=300, height=101),
        Word(text="Centro", left=200, top=200, width=100, height=30),
        Word(text="footer", left=200, top=3000, width=100, height=20),
    ]
    result = _extract_supplier(words)
    assert "VASILPNEUS" in result

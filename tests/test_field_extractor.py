"""Tests for field extractor module."""

from invoice_scrapper.field_extractor import extract_fields, _normalize


SAMPLE_TEXT = """
FATURA
Fornecedor: Empresa ABC Lda
Número da Fatura: FT 2024/1234
Data da Fatura: 15/03/2024
Preço Total sem IVA: 1.250,00
Número da Imputação da Fatura: IMP-2024-001
Referência nessa Imputação: REF-456
Número da Guia de Remessa: GR-789/2024
Cliente ou Local de Entrega: Armazém Lisboa Norte
"""


def test_extract_fornecedor():
    result = extract_fields(SAMPLE_TEXT, ["fornecedor"])
    assert result["fornecedor"] != ""
    assert "Empresa ABC" in result["fornecedor"]


def test_extract_numero_fatura():
    result = extract_fields(SAMPLE_TEXT, ["número da fatura"])
    assert "2024/1234" in result["número da fatura"]


def test_extract_data_fatura():
    result = extract_fields(SAMPLE_TEXT, ["data da fatura"])
    assert "15/03/2024" in result["data da fatura"]


def test_extract_preco_total():
    result = extract_fields(SAMPLE_TEXT, ["preço total sem IVA"])
    assert "1.250,00" in result["preço total sem IVA"]


def test_extract_imputacao():
    result = extract_fields(SAMPLE_TEXT, ["número da imputação da fatura"])
    assert "IMP-2024-001" in result["número da imputação da fatura"]


def test_extract_referencia():
    result = extract_fields(SAMPLE_TEXT, ["referência nessa imputação"])
    assert "REF-456" in result["referência nessa imputação"]


def test_extract_guia_remessa():
    result = extract_fields(SAMPLE_TEXT, ["número da guia de remessa"])
    assert "GR-789/2024" in result["número da guia de remessa"]


def test_extract_cliente():
    result = extract_fields(SAMPLE_TEXT, ["cliente ou local de entrega"])
    val = result["cliente ou local de entrega"]
    assert val != ""


def test_missing_field_returns_empty():
    result = extract_fields("Some random text", ["número da fatura"])
    assert result["número da fatura"] == ""


def test_case_insensitive():
    text = "FORNECEDOR: Test Company"
    result = extract_fields(text, ["fornecedor"])
    assert result["fornecedor"] != ""


def test_accent_insensitive():
    text = "Numero da Fatura: ABC-123"
    result = extract_fields(text, ["número da fatura"])
    assert result["número da fatura"] != ""


def test_per_item_fields_skipped():
    result = extract_fields(SAMPLE_TEXT, ["preço unitário do artigo", "quantidade"])
    assert result["preço unitário do artigo"] == ""
    assert result["quantidade"] == ""


def test_normalize():
    assert _normalize("Número") == "numero"
    assert _normalize("Preço") == "preco"
    assert _normalize("Referência") == "referencia"


def test_all_default_fields():
    from invoice_scrapper.config import DEFAULT_FIELDS
    result = extract_fields(SAMPLE_TEXT, DEFAULT_FIELDS)
    assert len(result) == len(DEFAULT_FIELDS)
    # Per-item fields should be empty
    assert result["preço unitário do artigo"] == ""
    assert result["quantidade"] == ""

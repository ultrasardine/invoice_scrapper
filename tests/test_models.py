"""Tests for data models."""

from pathlib import Path

from invoice_scrapper.models import InvoiceData, LineItem, ProcessingResult


def test_to_rows_multiple_items():
    inv = InvoiceData(
        ficheiro="test.pdf",
        fornecedor="ACME",
        numero_fatura="F001",
        line_items=[
            LineItem(preco_unitario="10.00", quantidade="2"),
            LineItem(preco_unitario="20.00", quantidade="5"),
        ],
    )
    rows = inv.to_rows()
    assert len(rows) == 2
    assert rows[0]["fornecedor"] == "ACME"
    assert rows[0]["preço unitário do artigo"] == "10.00"
    assert rows[1]["preço unitário do artigo"] == "20.00"
    assert rows[1]["ficheiro"] == "test.pdf"


def test_to_rows_no_items_produces_one_row():
    inv = InvoiceData(fornecedor="ACME")
    rows = inv.to_rows()
    assert len(rows) == 1
    assert rows[0]["fornecedor"] == "ACME"
    assert rows[0]["preço unitário do artigo"] == ""
    assert rows[0]["quantidade"] == ""


def test_defaults_are_empty():
    inv = InvoiceData()
    assert inv.fornecedor == ""
    assert inv.numero_fatura == ""
    item = LineItem()
    assert item.preco_unitario == ""


def test_processing_result_defaults():
    r = ProcessingResult(source_path=Path("test.pdf"))
    assert r.success is True
    assert r.errors == []
    assert r.invoice is None


def test_invoice_level_fields_repeated():
    inv = InvoiceData(
        numero_fatura="F100",
        line_items=[LineItem(), LineItem(), LineItem()],
    )
    rows = inv.to_rows()
    assert len(rows) == 3
    for row in rows:
        assert row["número da fatura"] == "F100"


def test_line_item_extra_fields():
    inv = InvoiceData(
        line_items=[LineItem(extra={"descrição": "Widget"})],
    )
    rows = inv.to_rows()
    assert rows[0]["descrição"] == "Widget"

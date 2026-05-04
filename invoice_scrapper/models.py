"""Data models for invoice extraction."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LineItem:
    """A single line item (artigo) from an invoice."""

    preco_unitario: str = ""
    quantidade: str = ""
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class InvoiceData:
    """Extracted data from a single invoice."""

    ficheiro: str = ""
    fornecedor: str = ""
    numero_fatura: str = ""
    data_fatura: str = ""
    preco_total_sem_iva: str = ""
    numero_imputacao: str = ""
    referencia_imputacao: str = ""
    numero_guia_remessa: str = ""
    cliente_local_entrega: str = ""
    line_items: list[LineItem] = field(default_factory=list)

    def to_rows(self) -> list[dict[str, str]]:
        """Convert to list of dicts, one per line item.

        Invoice-level fields are repeated on each row.
        If no line items, returns a single row with blank item fields.
        """
        base = {
            "fornecedor": self.fornecedor,
            "número da fatura": self.numero_fatura,
            "data da fatura": self.data_fatura,
            "preço total sem IVA": self.preco_total_sem_iva,
            "número da imputação da fatura": self.numero_imputacao,
            "referência nessa imputação": self.referencia_imputacao,
            "número da guia de remessa": self.numero_guia_remessa,
            "cliente ou local de entrega": self.cliente_local_entrega,
            "ficheiro": self.ficheiro,
        }
        items = self.line_items or [LineItem()]
        rows = []
        for item in items:
            row = {
                **base,
                "preço unitário do artigo": item.preco_unitario,
                "quantidade": item.quantidade,
                **item.extra,
            }
            rows.append(row)
        return rows


@dataclass
class ProcessingResult:
    """Result of processing a single PDF file."""

    source_path: Path
    success: bool = True
    errors: list[str] = field(default_factory=list)
    invoice: InvoiceData | None = None

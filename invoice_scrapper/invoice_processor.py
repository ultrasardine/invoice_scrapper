"""Invoice processing pipeline orchestrator."""

import logging
import re
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path

from invoice_scrapper.field_extractor import extract_fields
from invoice_scrapper.models import InvoiceData, LineItem, ProcessingResult
from invoice_scrapper.pdf_reader import PDFReader
from invoice_scrapper.table_detector import TableDetector

logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None]


def _noop_log(msg: str) -> None:
    pass


def _normalize(text: str) -> str:
    """Remove accents and lowercase."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


class InvoiceProcessor:
    """Orchestrates the full invoice processing pipeline."""

    def __init__(
        self,
        log_callback: LogCallback = _noop_log,
    ):
        self.log = log_callback
        self._reader = PDFReader()
        self._table_detector = TableDetector()

    def process_file(
        self, pdf_path: Path, fields: list[str]
    ) -> ProcessingResult:
        """Process a single PDF invoice."""
        self.log(f"Processando: {pdf_path.name}")
        errors: list[str] = []

        try:
            # Step 1: Extract text and positional word data
            self.log(f"  Extraindo texto de {pdf_path.name}...")
            pages = self._reader.extract_pages(pdf_path)

            # Step 2: Extract invoice-level fields per-page.
            # Processing each page independently prevents labels on one page
            # from spuriously matching values at the same coordinates on
            # another page.
            self.log("  Extraindo campos...")
            field_values: dict[str, str] = {}
            all_text_parts: list[str] = []
            for p in pages:
                all_text_parts.append(p.text)
                page_fields = extract_fields(p.text, fields, words=p.words if p.words else None)
                for k, v in page_fields.items():
                    if v and not field_values.get(k):
                        field_values[k] = v
            # Ensure every requested field has an entry
            for f in fields:
                field_values.setdefault(f, "")

            # Step 3: Detect tables using positional word data
            self.log(f"  Detetando tabelas ({len(pages)} páginas)...")
            all_tables: list[list[list[str]]] = []
            for i, page in enumerate(pages):
                tables = self._table_detector.detect_tables_from_words(
                    page.words
                )
                all_tables.extend(tables)
                if tables:
                    self.log(
                        f"    Página {i + 1}: {len(tables)} tabela(s)"
                    )

            # Step 4: Parse line items from tables
            line_items = self._parse_line_items(all_tables, fields)
            self.log(f"  {len(line_items)} artigo(s) encontrado(s)")

            # Step 5: Build InvoiceData
            invoice = InvoiceData(
                ficheiro=pdf_path.name,
                fornecedor=field_values.get("fornecedor", ""),
                numero_fatura=field_values.get("número da fatura", ""),
                data_fatura=field_values.get("data da fatura", ""),
                preco_total_sem_iva=field_values.get(
                    "preço total sem IVA", ""
                ),
                numero_imputacao=field_values.get(
                    "número da imputação da fatura", ""
                ),
                referencia_imputacao=field_values.get(
                    "referência nessa imputação", ""
                ),
                numero_guia_remessa=field_values.get(
                    "número da guia de remessa", ""
                ),
                cliente_local_entrega=field_values.get(
                    "cliente ou local de entrega", ""
                ),
                line_items=line_items,
            )

            self.log(f"  ✓ {pdf_path.name} processado com sucesso")
            return ProcessingResult(
                source_path=pdf_path,
                success=True,
                errors=errors,
                invoice=invoice,
            )

        except Exception as e:
            msg = f"Erro ao processar {pdf_path.name}: {e}"
            logger.error(msg)
            self.log(f"  ✗ {msg}")
            return ProcessingResult(
                source_path=pdf_path,
                success=False,
                errors=[msg],
            )

    def process_directory(
        self, input_dir: Path, fields: list[str]
    ) -> Iterator[ProcessingResult]:
        """Process all PDFs in a directory."""
        pdf_files = sorted(
            f for f in input_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".pdf"
        )

        if not pdf_files:
            self.log(f"Nenhum ficheiro PDF encontrado em {input_dir}")
            return

        self.log(f"Encontrados {len(pdf_files)} ficheiro(s) PDF")

        for pdf_path in pdf_files:
            yield self.process_file(pdf_path, fields)

    def _parse_line_items(
        self,
        tables: list[list[list[str]]],
        fields: list[str],
    ) -> list[LineItem]:
        """Parse line items from detected tables."""
        items: list[LineItem] = []

        for table in tables:
            if len(table) < 2:
                continue

            # Try to identify columns from header row
            header = [_normalize(cell) for cell in table[0]]
            price_col = self._find_column(
                header, ["preco", "unitario", "p.unit", "unit", "valor"]
            )
            qty_col = self._find_column(
                header, ["quantidade", "qtd", "qty", "quant"]
            )

            # If no header match, skip this table
            if price_col is None and qty_col is None:
                continue

            # Extract data rows
            for row in table[1:]:
                if all(not cell.strip() for cell in row):
                    continue

                raw_price = (
                    row[price_col].strip()
                    if price_col is not None and price_col < len(row)
                    else ""
                )
                raw_qty = (
                    row[qty_col].strip()
                    if qty_col is not None and qty_col < len(row)
                    else ""
                )

                # Validate: price and qty should be numeric
                price = self._clean_numeric(raw_price)
                qty = self._clean_numeric(raw_qty)

                # Skip rows where neither price nor qty is valid
                if not price and not qty:
                    continue

                items.append(LineItem(
                    preco_unitario=price,
                    quantidade=qty,
                ))

        return items

    @staticmethod
    def _clean_numeric(value: str) -> str:
        """Extract numeric value, return empty if not numeric."""
        if not value:
            return ""
        # Remove common OCR noise
        clean = value.replace("|", "").replace("]", "").replace("[", "").strip()
        # Check if it looks like a number (digits with , or . separators)
        m = re.match(r"^\d[\d\s.,]*\d$|^\d$", clean)
        if m:
            return clean
        # Try to find a number within the text
        m = re.search(r"\d+[.,]\d{2}", clean)
        if m:
            return m.group(0)
        m = re.search(r"\d+", clean)
        if m and len(m.group(0)) >= 1:
            return m.group(0)
        return ""

    @staticmethod
    def _find_column(
        header: list[str], keywords: list[str]
    ) -> int | None:
        """Find column index matching any keyword."""
        for i, cell in enumerate(header):
            for kw in keywords:
                if kw in cell:
                    return i
        return None

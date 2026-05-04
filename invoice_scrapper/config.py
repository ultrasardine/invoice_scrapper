"""Configuration manager for Invoice Scrapper."""

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".invoice_scrapper"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_FIELDS: list[str] = [
    "fornecedor",
    "número da fatura",
    "data da fatura",
    "preço total sem IVA",
    "número da imputação da fatura",
    "referência nessa imputação",
    "preço unitário do artigo",
    "quantidade",
    "número da guia de remessa",
    "cliente ou local de entrega",
]


@dataclass
class Config:
    """Application configuration."""

    input_dir: str = str(Path.home() / "Downloads")
    output_file: str = str(Path.home() / "Documents" / "invoice_info.xlsx")
    fields: list[str] = field(default_factory=lambda: list(DEFAULT_FIELDS))

    def save(self, path: Path | None = None) -> None:
        """Save config to JSON file."""
        target = path or CONFIG_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "input_dir": self.input_dir,
                    "output_file": self.output_file,
                    "fields": self.fields,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load config from JSON file, falling back to defaults."""
        target = path or CONFIG_FILE
        if not target.exists():
            return cls()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            defaults = cls()
            return cls(
                input_dir=data.get("input_dir", defaults.input_dir),
                output_file=data.get("output_file", defaults.output_file),
                fields=data.get("fields", defaults.fields),
            )
        except (json.JSONDecodeError, KeyError):
            return cls()

"""Tests for configuration module."""

import json
from pathlib import Path

from invoice_scrapper.config import Config, DEFAULT_FIELDS


def test_default_config():
    cfg = Config()
    assert cfg.input_dir == str(Path.home() / "Downloads")
    assert cfg.output_file == str(Path.home() / "Documents" / "invoice_info.xlsx")
    assert cfg.fields == DEFAULT_FIELDS


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    cfg = Config(input_dir="/tmp/invoices", output_file="/tmp/out.xlsx")
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.input_dir == "/tmp/invoices"
    assert loaded.output_file == "/tmp/out.xlsx"
    assert loaded.fields == DEFAULT_FIELDS


def test_load_missing_file_returns_defaults(tmp_path: Path):
    cfg = Config.load(tmp_path / "nonexistent.json")
    assert cfg.fields == DEFAULT_FIELDS


def test_partial_config_merges_with_defaults(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"input_dir": "/custom/path"}), encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.input_dir == "/custom/path"
    assert cfg.output_file == str(Path.home() / "Documents" / "invoice_info.xlsx")
    assert cfg.fields == DEFAULT_FIELDS


def test_corrupted_config_returns_defaults(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("not valid json{{{", encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.fields == DEFAULT_FIELDS


def test_save_creates_parent_dirs(tmp_path: Path):
    path = tmp_path / "nested" / "dir" / "config.json"
    Config().save(path)
    assert path.exists()


def test_custom_fields_persist(tmp_path: Path):
    path = tmp_path / "config.json"
    cfg = Config(fields=["campo1", "campo2"])
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.fields == ["campo1", "campo2"]

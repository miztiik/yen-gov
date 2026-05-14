"""Tests for `yen_gov.core.schema_registry`.

Per CLAUDE.md sec.15 (unit tier): pure-function tests against real schema
files on disk. The registry is the single source of truth for schema
metadata; these tests pin its contract so future "let's just hand-type
the version again" regressions get caught.
"""

from __future__ import annotations

import json

import pytest

from yen_gov.core import schema_registry as sr


def test_schema_version_matches_file_x_version() -> None:
    """Round-trip: registry's version equals the file's `x-version`."""
    for path in sr._SCHEMA_DIR.glob("*.schema.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "x-version" not in doc:
            # A handful of helper schemas (e.g. *.sources.schema.json) ship
            # without x-version. The registry does not enforce x-version on
            # files nobody asks about; only files that someone calls
            # schema_version() on need it.
            continue
        assert sr.schema_version(path.name) == doc["x-version"], (
            f"{path.name}: registry returned {sr.schema_version(path.name)!r} "
            f"but file declares {doc['x-version']!r}"
        )


def test_schema_id_matches_file_id() -> None:
    """Round-trip: registry's `$id` equals the file's `$id`."""
    for path in sr._SCHEMA_DIR.glob("*.schema.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "$id" not in doc:
            continue
        assert sr.schema_id(path.name) == doc["$id"]


def test_unknown_schema_filename_raises_typed_error() -> None:
    """Missing-file failure is a SchemaRegistryError, not a bare OSError /
    KeyError 8 frames deep. The error names the file."""
    with pytest.raises(sr.SchemaRegistryError, match="not_a_real.schema.json"):
        sr.schema_doc("not_a_real.schema.json")


def test_missing_x_version_key_raises_typed_error(tmp_path, monkeypatch) -> None:
    """A schema file that exists but lacks `x-version` raises a typed error
    naming the file and the missing key — not a bare KeyError."""
    bad = tmp_path / "broken.schema.json"
    bad.write_text(json.dumps({"$id": "https://example.test/broken"}), encoding="utf-8")
    monkeypatch.setattr(sr, "_SCHEMA_DIR", tmp_path)
    sr.schema_doc.cache_clear()
    with pytest.raises(sr.SchemaRegistryError, match="x-version"):
        sr.schema_version("broken.schema.json")


def test_invalid_json_raises_typed_error(tmp_path, monkeypatch) -> None:
    """Malformed JSON raises a typed error, not a raw JSONDecodeError."""
    bad = tmp_path / "garbage.schema.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(sr, "_SCHEMA_DIR", tmp_path)
    sr.schema_doc.cache_clear()
    with pytest.raises(sr.SchemaRegistryError, match="garbage.schema.json"):
        sr.schema_doc("garbage.schema.json")


def test_cache_is_per_filename(monkeypatch, tmp_path) -> None:
    """`@lru_cache` is keyed on filename; calling for two different files
    returns two distinct dicts."""
    a = tmp_path / "a.schema.json"
    b = tmp_path / "b.schema.json"
    a.write_text(json.dumps({"$id": "x", "x-version": "1.0"}), encoding="utf-8")
    b.write_text(json.dumps({"$id": "y", "x-version": "2.0"}), encoding="utf-8")
    monkeypatch.setattr(sr, "_SCHEMA_DIR", tmp_path)
    sr.schema_doc.cache_clear()
    assert sr.schema_version("a.schema.json") == "1.0"
    assert sr.schema_version("b.schema.json") == "2.0"

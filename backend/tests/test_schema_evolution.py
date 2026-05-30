from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from yen_gov.core.schema_evolution import (
    SchemaEvolutionError,
    load_schema_evolution_ledger,
    resolve_schema_for_declared_version,
)

REPO = Path(__file__).resolve().parents[2]
LEDGER_REL = Path("datasets/schema-evolution.json")
SCHEMA_REL = Path("datasets/schemas/schema-evolution.schema.json")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _schema_doc(version: str, title: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "./example.schema.json",
        "title": title,
        "x-version": version,
        "x-changelog": [
            {
                "version": version,
                "date": "2026-05-30",
                "description": f"Fixture schema {version}.",
            }
        ],
        "type": "object",
    }


def _fixture_release(retained_path: str, retained_hash: str) -> dict[str, Any]:
    return {
        "release_id": "example-1-0-to-1-1",
        "released_on": "2026-05-30",
        "schema_file": "example.schema.json",
        "schema_id": "./example.schema.json",
        "from_version": "1.0",
        "to_version": "1.1",
        "change_class": "minor_additive",
        "compatibility_status": "historical_validation_only",
        "validation_strategy": "declared_schema",
        "retained_schema": {
            "path": retained_path,
            "version": "1.0",
            "sha256": retained_hash,
        },
        "values_changed": False,
        "value_change_summary": None,
        "provenance_changed": False,
        "methodology_changed": False,
        "methodology_break_refs": [],
        "affected_artifacts": [
            {
                "path_pattern": "datasets/example/*.json",
                "table_id": None,
                "artifact_count": 2,
                "action": "metadata_rewritten",
            }
        ],
        "pr": "#999",
        "commit": "abcdef1",
        "notes": "Fixture release proving retained-schema declared-version validation.",
    }


def _make_tmp_repo(tmp_path: Path) -> tuple[Path, str, str]:
    schema_path = tmp_path / SCHEMA_REL
    _write_json(schema_path, _load_json(REPO / SCHEMA_REL))

    current_schema = _schema_doc("1.1", "Example current")
    _write_json(tmp_path / "datasets/schemas/example.schema.json", current_schema)

    retained_rel = "datasets/schemas/archive/example/v1.0/example.schema.json"
    retained_schema = _schema_doc("1.0", "Example retained")
    retained_path = tmp_path / retained_rel
    _write_json(retained_path, retained_schema)
    retained_hash = hashlib.sha256(retained_path.read_bytes()).hexdigest()

    ledger = {
        "$schema": "./schemas/schema-evolution.schema.json",
        "$schema_version": "1.0",
        "releases": [_fixture_release(retained_rel, retained_hash)],
    }
    _write_json(tmp_path / LEDGER_REL, ledger)
    return tmp_path, retained_rel, retained_hash


def test_real_schema_evolution_ledger_validates_against_its_schema() -> None:
    schema = _load_json(REPO / SCHEMA_REL)
    ledger = _load_json(REPO / LEDGER_REL)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ledger), key=lambda error: list(error.absolute_path))

    assert errors == []


def test_resolver_returns_current_schema_for_current_declared_version(tmp_path: Path) -> None:
    repo_root, _, _ = _make_tmp_repo(tmp_path)

    resolved = resolve_schema_for_declared_version(repo_root, "example.schema.json", "1.1")

    assert resolved["title"] == "Example current"


def test_values_changed_false_release_resolves_retained_schema(tmp_path: Path) -> None:
    repo_root, _, _ = _make_tmp_repo(tmp_path)
    ledger = load_schema_evolution_ledger(repo_root)

    resolved = resolve_schema_for_declared_version(repo_root, "example.schema.json", "1.0", ledger)

    assert ledger["releases"][0]["values_changed"] is False
    assert ledger["releases"][0]["value_change_summary"] is None
    assert resolved["title"] == "Example retained"


def test_values_changed_true_release_requires_summary(tmp_path: Path) -> None:
    repo_root, retained_rel, retained_hash = _make_tmp_repo(tmp_path)
    ledger = _load_json(repo_root / LEDGER_REL)
    release = deepcopy(_fixture_release(retained_rel, retained_hash))
    release.update(
        {
            "release_id": "example-values-revised",
            "validation_strategy": "current_schema",
            "compatibility_status": "current_only",
            "retained_schema": None,
            "values_changed": True,
            "value_change_summary": "Backfilled published values from the refreshed upstream extract.",
            "provenance_changed": True,
            "affected_artifacts": [
                {
                    "path_pattern": "datasets/example/*.json",
                    "table_id": None,
                    "artifact_count": 2,
                    "action": "values_rewritten",
                }
            ],
        }
    )
    ledger["releases"] = [release]
    _write_json(repo_root / LEDGER_REL, ledger)

    loaded = load_schema_evolution_ledger(repo_root)

    assert loaded["releases"][0]["values_changed"] is True
    assert "Backfilled" in loaded["releases"][0]["value_change_summary"]


def test_values_changed_true_without_summary_fails_schema_validation(tmp_path: Path) -> None:
    repo_root, retained_rel, retained_hash = _make_tmp_repo(tmp_path)
    ledger = _load_json(repo_root / LEDGER_REL)
    release = deepcopy(_fixture_release(retained_rel, retained_hash))
    release["values_changed"] = True
    release["value_change_summary"] = None
    ledger["releases"] = [release]
    _write_json(repo_root / LEDGER_REL, ledger)

    with pytest.raises(SchemaEvolutionError, match="value_change_summary"):
        load_schema_evolution_ledger(repo_root)


def test_missing_retained_schema_file_fails_loudly(tmp_path: Path) -> None:
    repo_root, retained_rel, retained_hash = _make_tmp_repo(tmp_path)
    (repo_root / retained_rel).unlink()
    ledger = load_schema_evolution_ledger(repo_root)

    with pytest.raises(SchemaEvolutionError, match="retained schema file not found"):
        resolve_schema_for_declared_version(repo_root, "example.schema.json", "1.0", ledger)


def test_retained_schema_hash_mismatch_fails_loudly(tmp_path: Path) -> None:
    repo_root, retained_rel, _ = _make_tmp_repo(tmp_path)
    ledger = _load_json(repo_root / LEDGER_REL)
    ledger["releases"][0]["retained_schema"]["sha256"] = "0" * 64
    _write_json(repo_root / LEDGER_REL, ledger)
    loaded = load_schema_evolution_ledger(repo_root)

    with pytest.raises(SchemaEvolutionError, match="hash mismatch"):
        resolve_schema_for_declared_version(repo_root, "example.schema.json", "1.0", loaded)

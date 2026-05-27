"""CLI tests for ``check-overlap`` (PR-Z3b-cli).

Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #13, every new indicator_id MUST FK to a row in concepts.json.
``check-overlap`` is the pre-PR gate. Exits 1 if any match scores >= 0.70.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these
tests build a synthetic concepts.json under ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from yen_gov.cli import app


runner = CliRunner()


def _write_concepts(root: Path, concepts: list[dict]) -> None:
    p = root / "datasets" / "taxonomy"
    p.mkdir(parents=True, exist_ok=True)
    (p / "concepts.json").write_text(
        json.dumps(
            {
                "$schema": "../schemas/concepts.schema.json",
                "$schema_version": "1.0",
                "concepts": concepts,
            }
        ),
        encoding="utf-8",
    )


def _invoke(tmp_path: Path, **overrides: str) -> "object":
    args = [
        "check-overlap",
        "--noun", overrides.get("noun", "installed capacity"),
        "--unit", overrides.get("unit", "MW"),
        "--normalisation", overrides.get("normalisation", "absolute"),
        "--entity-kind", overrides.get("entity_kind", "state"),
        "--root", str(tmp_path),
    ]
    return runner.invoke(app, args)


def test_exits_zero_when_no_match_above_threshold(tmp_path):
    _write_concepts(
        tmp_path,
        [
            {
                "concept_id": "voter-turnout",
                "noun": "voter turnout",
                "unit_canonical": "pct",
                "normalisation": "share",
                "entity_kinds": ["state"],
                "description_short": "Share of electors who cast a vote.",
                "sources": [],
            }
        ],
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "mint_new is acceptable" in result.output


def test_exits_one_when_match_crosses_threshold(tmp_path):
    _write_concepts(
        tmp_path,
        [
            {
                "concept_id": "installed-capacity",
                "noun": "installed capacity",
                "unit_canonical": "MW",
                "normalisation": "absolute",
                "entity_kinds": ["state", "country"],
                "description_short": "Nameplate generation capacity.",
                "sources": [],
            }
        ],
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 1, result.output
    assert "installed-capacity" in result.output
    assert "FAILED" in result.output
    assert "guardrail #13" in result.output


def test_emits_recommendation_table(tmp_path):
    _write_concepts(
        tmp_path,
        [
            {
                "concept_id": "voter-turnout",
                "noun": "voter turnout",
                "unit_canonical": "pct",
                "normalisation": "share",
                "entity_kinds": ["state"],
                "description_short": ".",
                "sources": [],
            }
        ],
    )
    result = _invoke(tmp_path)
    assert "score" in result.output
    assert "action" in result.output
    assert "concept_id" in result.output
    assert "voter-turnout" in result.output


def test_no_concepts_in_registry_returns_ok(tmp_path):
    _write_concepts(tmp_path, [])
    result = _invoke(tmp_path)
    assert result.exit_code == 0
    assert "no concepts in registry" in result.output


def test_rejects_missing_required_options(tmp_path):
    result = runner.invoke(app, ["check-overlap", "--noun", "x"])
    assert result.exit_code != 0

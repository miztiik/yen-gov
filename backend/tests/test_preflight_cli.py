"""CLI smoke for `python -m yen_gov pre-flight-ingest`."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from yen_gov.cli import app
from yen_gov.core.schema_registry import schema_version

runner = CliRunner()


def _write_concepts(root: Path, concepts: list[dict]) -> None:
    d = root / "datasets" / "taxonomy"
    d.mkdir(parents=True, exist_ok=True)
    (d / "concepts.json").write_text(json.dumps({"concepts": concepts}), encoding="utf-8")


PROPOSAL = {
    "proposed_id": "livestock-foo-count",
    "family": "livestock",
    "concept": "completely novel widget",
    "unit": "count",
    "normalisation": "absolute",
    "entity_kind": "district",
    "source_producer": "NDLM",
    "source_title": "Foo registry",
    "source_vintage": "2024-25",
    "update_period_days": 30,
    "justification": "per-animal UID coverage at district grain not collapsible to state",
}


def test_cli_pass_exit_zero(tmp_path):
    _write_concepts(tmp_path, [])
    pf = tmp_path / "proposal.json"
    pf.write_text(json.dumps(PROPOSAL), encoding="utf-8")
    report_path = tmp_path / "report.json"

    result = runner.invoke(app, [
        "pre-flight-ingest",
        "--proposal-file", str(pf),
        "--report", str(report_path),
        "--root", str(tmp_path),
    ])
    # exit 0 (pass) or 1 (soft-warn: mint_new without concept_id) both acceptable
    assert result.exit_code in (0, 1), result.stdout
    assert "verdict=mint_new" in result.stdout
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "mint_new"
    assert payload["schema_version"] == schema_version("preflight-report.schema.json")


def test_cli_hard_fail_exit_two(tmp_path):
    _write_concepts(tmp_path, [])
    bad = dict(PROPOSAL)
    bad["proposed_id"] = "state-foo-count"  # grain prefix -> abort
    pf = tmp_path / "proposal.json"
    pf.write_text(json.dumps(bad), encoding="utf-8")

    result = runner.invoke(app, [
        "pre-flight-ingest",
        "--proposal-file", str(pf),
        "--root", str(tmp_path),
    ])
    assert result.exit_code == 2, result.stdout
    assert "verdict=abort" in result.stdout


def test_cli_missing_required_field_aborts(tmp_path):
    _write_concepts(tmp_path, [])
    incomplete = dict(PROPOSAL)
    incomplete.pop("update_period_days")
    pf = tmp_path / "proposal.json"
    pf.write_text(json.dumps(incomplete), encoding="utf-8")

    result = runner.invoke(app, [
        "pre-flight-ingest",
        "--proposal-file", str(pf),
        "--root", str(tmp_path),
    ])
    assert result.exit_code == 2
    assert "abort" in result.stdout


def test_cli_flag_sugar_hydrates_proposal(tmp_path):
    _write_concepts(tmp_path, [])
    result = runner.invoke(app, [
        "pre-flight-ingest",
        "--proposed-id", "livestock-foo-count",
        "--family", "livestock",
        "--concept", "completely novel widget",
        "--unit", "count",
        "--normalisation", "absolute",
        "--entity-kind", "district",
        "--source-producer", "NDLM",
        "--source-title", "Foo registry",
        "--source-vintage", "2024-25",
        "--update-period-days", "30",
        "--justification", "per-animal UID coverage at district grain not collapsible to state",
        "--root", str(tmp_path),
    ])
    assert result.exit_code in (0, 1), result.stdout
    assert "verdict=mint_new" in result.stdout

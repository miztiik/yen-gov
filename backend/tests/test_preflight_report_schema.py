"""Validate the PreflightReport JSON against the v1.0 schema for the four canned verdicts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from yen_gov.preflight import build_report

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "datasets" / "schemas" / "preflight-report.schema.json"
)


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _write_concepts(tmp_path: Path, concepts: list[dict]) -> None:
    d = tmp_path / "datasets" / "taxonomy"
    d.mkdir(parents=True, exist_ok=True)
    (d / "concepts.json").write_text(json.dumps({"concepts": concepts}), encoding="utf-8")


BASE_PROPOSAL = {
    "proposed_id": "livestock-foo-count",
    "family": "livestock",
    "concept": "foo count widget",
    "unit": "count",
    "normalisation": "absolute",
    "entity_kind": "district",
    "source_producer": "NDLM",
    "source_title": "Foo registry",
    "source_vintage": "2024-25",
    "update_period_days": 30,
    "justification": "distinct sampling frame for animal-level UID coverage at district grain",
}


def _existing(noun: str, unit: str = "count", norm: str = "absolute") -> dict:
    return {
        "concept_id": f"{noun}-existing",
        "noun": noun,
        "unit_canonical": unit,
        "normalisation": norm,
        "entity_kinds": ["district"],
    }


def test_verdict_mint_new(tmp_path, validator):
    _write_concepts(tmp_path, [_existing("totally unrelated thing")])
    report = build_report(BASE_PROPOSAL, root=tmp_path)
    assert report.verdict == "mint_new"
    assert report.exit_code in (0, 1)
    d = report.to_dict()
    errors = sorted(validator.iter_errors(d), key=lambda e: e.path)
    assert not errors, [e.message for e in errors]


def test_verdict_upsert(tmp_path, validator):
    # Concept with same noun + unit + normalisation + entity_kind -> upsert.
    _write_concepts(tmp_path, [
        {"concept_id": "foo-count-widget", "noun": "foo count widget",
         "unit_canonical": "count", "normalisation": "absolute",
         "entity_kinds": ["district"]},
    ])
    report = build_report(BASE_PROPOSAL, root=tmp_path)
    assert report.verdict == "upsert"
    d = report.to_dict()
    assert not list(validator.iter_errors(d))


def test_verdict_add_facet(tmp_path, validator):
    # Same noun + unit + normalisation but DIFFERENT entity_kind -> add_facet.
    _write_concepts(tmp_path, [
        {"concept_id": "foo-count-widget", "noun": "foo count widget",
         "unit_canonical": "count", "normalisation": "absolute",
         "entity_kinds": ["state"]},
    ])
    report = build_report(BASE_PROPOSAL, root=tmp_path)
    assert report.verdict == "add_facet"
    d = report.to_dict()
    assert not list(validator.iter_errors(d))


def test_verdict_abort_on_grain_prefix(tmp_path, validator):
    _write_concepts(tmp_path, [])
    bad = dict(BASE_PROPOSAL)
    bad["proposed_id"] = "district-foo-count"  # grain prefix
    report = build_report(bad, root=tmp_path)
    assert report.verdict == "abort"
    assert report.exit_code == 2
    d = report.to_dict()
    assert not list(validator.iter_errors(d))


def test_generated_at_is_deterministic(tmp_path):
    _write_concepts(tmp_path, [])
    r1 = build_report(BASE_PROPOSAL, root=tmp_path)
    r2 = build_report(BASE_PROPOSAL, root=tmp_path)
    assert r1.generated_at == r2.generated_at
    assert r1.generated_at.startswith("preflight:sha256:")

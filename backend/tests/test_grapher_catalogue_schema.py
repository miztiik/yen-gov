"""Tier-A tests for the grapher catalogue (frontend-owned render hints).

Per CLAUDE.md §15: tmp_path only, no mocks, no corpus walk. These tests
pin the v1.0 contract for the two new schemas:

1. Both schemas load and accept their documented example.
2. ``additionalProperties: false`` rejects unknown fields.
3. The on-disk seed files (datasets/grapher/*.json) validate against
   their respective schemas — the canary that ensures hand-edits stay
   contract-clean.

See also:
    - ADR-0045 (grapher catalogue split)
    - datasets/grapher/AGENTS.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "datasets" / "schemas"
GRAPHER_DIR = REPO_ROOT / "datasets" / "grapher"

INDICATOR_SCHEMA = SCHEMA_DIR / "grapher-indicator-render.schema.json"
TOPIC_SCHEMA = SCHEMA_DIR / "grapher-topic-render.schema.json"
INDICATOR_SEED = GRAPHER_DIR / "indicator_render.json"
TOPIC_SEED = GRAPHER_DIR / "topic_render.json"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_indicator_schema_loads_and_is_v1_0() -> None:
    schema = _load(INDICATOR_SCHEMA)
    assert schema["x-version"] == "1.0"
    assert schema["x-changelog"][-1]["version"] == "1.0"
    Draft202012Validator.check_schema(schema)


def test_topic_schema_loads_and_is_v1_0() -> None:
    schema = _load(TOPIC_SCHEMA)
    assert schema["x-version"] == "1.0"
    assert schema["x-changelog"][-1]["version"] == "1.0"
    Draft202012Validator.check_schema(schema)


def test_indicator_schema_accepts_documented_example() -> None:
    schema = _load(INDICATOR_SCHEMA)
    v = Draft202012Validator(schema)
    doc = {
        "$schema": "../schemas/grapher-indicator-render.schema.json",
        "$schema_version": "1.0",
        "indicators": [
            {
                "indicator_id": "environment/state_no2_annual_mean_ug_m3",
                "chart_type": "choropleth",
            },
            {
                "indicator_id": "district-pashu-aadhaar-count-total",
                "renderer_rules": ["no_rank_table"],
            },
            {
                "indicator_id": "economy/india_gdp_inr_crore",
                "chart_type": "stacked-trend",
                "default_mode": "absolute",
                "facet_labels": {"price_basis": "Price basis"},
            },
        ],
    }
    errors = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    assert errors == [], errors


def test_topic_schema_accepts_documented_example() -> None:
    schema = _load(TOPIC_SCHEMA)
    v = Draft202012Validator(schema)
    doc = {
        "$schema": "../schemas/grapher-topic-render.schema.json",
        "$schema_version": "1.0",
        "topics": [
            {
                "topic_id": "energy",
                "indicator_id": "energy/state_electricity_generation_by_source_gwh",
                "chart_type": "ranked",
                "dimension": "power_source",
            }
        ],
    }
    errors = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    assert errors == [], errors


def test_indicator_schema_rejects_unknown_field() -> None:
    schema = _load(INDICATOR_SCHEMA)
    v = Draft202012Validator(schema)
    doc = {
        "$schema": "x",
        "$schema_version": "1.0",
        "indicators": [
            {
                "indicator_id": "x",
                "unit": "kWh",  # data field — forbidden in grapher catalogue
            }
        ],
    }
    errors = list(v.iter_errors(doc))
    assert errors, "expected schema to reject unknown 'unit' field"


def test_topic_schema_rejects_unknown_field() -> None:
    schema = _load(TOPIC_SCHEMA)
    v = Draft202012Validator(schema)
    doc = {
        "$schema": "x",
        "$schema_version": "1.0",
        "topics": [
            {
                "topic_id": "energy",
                "indicator_id": "x",
                "kind": "indicator",  # belongs on topic-catalogue, not grapher
            }
        ],
    }
    errors = list(v.iter_errors(doc))
    assert errors, "expected schema to reject unknown 'kind' field"


def test_indicator_seed_validates() -> None:
    schema = _load(INDICATOR_SCHEMA)
    v = Draft202012Validator(schema)
    doc = _load(INDICATOR_SEED)
    errors = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    assert errors == [], errors


def test_topic_seed_validates() -> None:
    schema = _load(TOPIC_SCHEMA)
    v = Draft202012Validator(schema)
    doc = _load(TOPIC_SEED)
    errors = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    assert errors == [], errors


def test_indicator_seed_no_render_data_field_collision() -> None:
    """Grapher rows MUST NOT carry data fields (unit, value_kind, family, ...)."""
    doc = _load(INDICATOR_SEED)
    forbidden = {"unit", "value_kind", "family", "label_short", "label_long", "source_id"}
    for row in doc["indicators"]:
        offending = set(row) & forbidden
        assert not offending, f"{row['indicator_id']}: forbidden data fields {offending}"


def test_indicator_seed_rows_unique() -> None:
    doc = _load(INDICATOR_SEED)
    ids = [r["indicator_id"] for r in doc["indicators"]]
    assert len(ids) == len(set(ids)), "duplicate indicator_id rows in seed"


def test_topic_seed_pairs_unique() -> None:
    doc = _load(TOPIC_SEED)
    pairs = [(r["topic_id"], r["indicator_id"]) for r in doc["topics"]]
    assert len(pairs) == len(set(pairs)), "duplicate (topic_id, indicator_id) pairs"

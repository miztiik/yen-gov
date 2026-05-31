"""Tier-A contract tests for `datasets/schemas/indicator.schema.json`.

Locks in the three additive grounding fields introduced by PR-B0 of
docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md §2:

* ``indicator.entity_kinds[]`` — optional array mirroring the singular
  ``entity_kind`` enum, used to declare cross-grain shards.
* ``indicator.base_year`` — optional ``YYYY`` / ``YYYY-YY`` string for
  constant-prices / index base year (per ADR-0044 Rosling rule:
  don't encode base year in the indicator id).
* ``indicator.frequency`` — optional enum mirroring ``cadence``, for
  shards that fold multiple release rhythms under one id.

Plus the structural change: ``additionalProperties: false`` is no
longer enforced on the ``indicator`` block during the migration
window; the schema test continues to reject typos in KNOWN fields via
explicit assertions here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "schemas"
    / "indicator.schema.json"
)


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema: dict) -> Draft202012Validator:
    return Draft202012Validator(schema)


def _minimal_artifact(overrides: dict | None = None) -> dict:
    """Indicator-block-only fixture; we drive validation through the nested
    indicator subschema, not the top-level envelope. Keeps these tests
    focused on the v5.0 indicator-block changes."""
    body = {
        "id": "economy/test_indicator",
        "title": "Test indicator",
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "currency",
        "direction": "neutral",
        "unit": "INR crore",
    }
    if overrides:
        body.update(overrides)
    return body


@pytest.fixture(scope="module")
def indicator_validator(schema: dict) -> Draft202012Validator:
    return Draft202012Validator(schema["properties"]["indicator"])


def test_x_version_uses_schema_version_shape(schema: dict) -> None:
    assert re.fullmatch(r"\d+\.\d+", schema["x-version"])


def test_changelog_tail_matches_x_version(schema: dict) -> None:
    tail = schema["x-changelog"][-1]
    assert tail["version"] == schema["x-version"]


def test_changelog_retains_v5_grounding_entry(schema: dict) -> None:
    entries = {entry["version"]: entry for entry in schema["x-changelog"]}

    assert entries["5.0"]["date"] == "2026-05-26"
    assert "entity_kinds" in entries["5.0"]["description"]


@pytest.mark.parametrize(
    "indicator_id",
    [
        "economy/test_indicator",
        "energy/state_peak_electricity_demand_mw",
        "plain_legacy_id",
    ],
)
def test_legacy_slash_snake_indicator_ids_validate(
    indicator_validator: Draft202012Validator,
    indicator_id: str,
) -> None:
    body = _minimal_artifact({"id": indicator_id})

    assert list(indicator_validator.iter_errors(body)) == []


@pytest.mark.parametrize(
    "indicator_id",
    [
        "peak-electricity-demand-mw",
        "rpo-compliance-pct",
    ],
)
def test_canonical_kebab_indicator_ids_validate(
    indicator_validator: Draft202012Validator,
    indicator_id: str,
) -> None:
    body = _minimal_artifact({"id": indicator_id})

    assert list(indicator_validator.iter_errors(body)) == []


@pytest.mark.parametrize(
    "indicator_id",
    [
        "energy/peak-electricity-demand-mw",
        "peak_electricity-demand_mw",
        "Peak-Electricity-Demand-MW",
        "peak--electricity-demand-mw",
        "peak-electricity-demand-mw-",
    ],
)
def test_mixed_or_malformed_indicator_ids_reject(
    indicator_validator: Draft202012Validator,
    indicator_id: str,
) -> None:
    body = _minimal_artifact({"id": indicator_id})

    assert list(indicator_validator.iter_errors(body))


def test_additional_properties_lifted_on_indicator_block(schema: dict) -> None:
    """v5.0 lifts `additionalProperties: false` on the indicator block to allow
    per-family adapter blocks during the migration window."""
    assert "additionalProperties" not in schema["properties"]["indicator"]


def test_v6_removed_render_fields_stay_out_of_indicator_schema(schema: dict) -> None:
    props = schema["properties"]["indicator"]["properties"]
    assert "default_mode" not in props
    assert "facet_labels" not in props
    assert "renderer_rules" not in props


def test_minimal_v4_4_indicator_block_still_validates(indicator_validator: Draft202012Validator) -> None:
    """Back-compat: a v4.4-shaped indicator block (none of the new optional
    fields populated) still validates under v5.0."""
    body = _minimal_artifact()
    assert list(indicator_validator.iter_errors(body)) == []


def test_entity_kinds_array_accepted(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"entity_kinds": ["country", "state"]})
    assert list(indicator_validator.iter_errors(body)) == []


def test_entity_kinds_rejects_unknown_enum(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"entity_kinds": ["state", "planet"]})
    errs = list(indicator_validator.iter_errors(body))
    assert any("planet" in err.message or "enum" in err.message for err in errs)


def test_entity_kinds_rejects_empty_array(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"entity_kinds": []})
    errs = list(indicator_validator.iter_errors(body))
    assert errs, "empty entity_kinds[] should fail minItems=1"


def test_entity_kinds_rejects_duplicates(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"entity_kinds": ["state", "state"]})
    errs = list(indicator_validator.iter_errors(body))
    assert any("unique" in err.message.lower() for err in errs)


def test_base_year_yyyy_accepted(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"base_year": "2011"})
    assert list(indicator_validator.iter_errors(body)) == []


def test_base_year_fiscal_form_accepted(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"base_year": "2011-12"})
    assert list(indicator_validator.iter_errors(body)) == []


def test_base_year_rejects_malformed(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"base_year": "FY12"})
    errs = list(indicator_validator.iter_errors(body))
    assert errs, "base_year='FY12' should fail the YYYY pattern"


def test_frequency_enum_accepted(indicator_validator: Draft202012Validator) -> None:
    for freq in (
        "annual_cy",
        "annual_fy",
        "quarterly_cy",
        "quarterly_fy",
        "monthly",
        "decennial",
        "ad_hoc",
    ):
        body = _minimal_artifact({"frequency": freq})
        assert list(indicator_validator.iter_errors(body)) == [], f"valid frequency {freq!r} rejected"


def test_frequency_rejects_unknown_enum(indicator_validator: Draft202012Validator) -> None:
    body = _minimal_artifact({"frequency": "biennial"})
    errs = list(indicator_validator.iter_errors(body))
    assert any("enum" in err.message.lower() or "biennial" in err.message for err in errs)


def test_entity_kind_singular_still_required(indicator_validator: Draft202012Validator) -> None:
    """Migration-window invariant: singular `entity_kind` stays required even
    when the new plural `entity_kinds[]` is populated."""
    body = _minimal_artifact({"entity_kinds": ["country", "state"]})
    del body["entity_kind"]
    errs = list(indicator_validator.iter_errors(body))
    assert any("entity_kind" in err.message for err in errs)

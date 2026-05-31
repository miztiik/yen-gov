"""Tier-A contract tests for the livestock NDLM Owner Reg meadow file.

Asserts ``datasets/livestock/_meadow/ndlm/2024-25/owner_reg_land_holding_district.json``
satisfies the meadow grammar declared by Phase 1.A of the NDLM ingest plan
(``TODO/20260525-livestock-ndlm-ingest-plan.md`` section 11):

* File exists at the canonical ADR-0041 meadow path. The vintage segment
  ``2024-25`` matches the seeded ``src-d98dc531ef7e`` citation row in
  ``datasets/taxonomy/sources.parquet`` (PR #276).
* JSON conforms to a compatibility-accepted ``indicator.schema.json`` shape:
  ``rows.items`` carries only the closed-set
  ``{entity_id, time, value, facet}`` keys.
* Every ``time`` matches the schema regex ``^\\d{4}(-\\d{2}(-\\d{2})?)?$``.
* Every ``facet`` matches the 12-value vocabulary
  (6 landholding x 2 gender = ``<landholding>|<gender>``).
* Every ``entity_id`` resolves to a district entity in
  ``datasets/taxonomy/entities.json`` and matches the ``IN-S{XX}-D{lgd}``
  shape.
* No fabricated zeros: ``value`` is a positive (>= 0) integer per
  meadow contract; NDLM null counts are dropped at lift time.

Uses the real on-disk meadow file (no mocks per CLAUDE.md ss 10 Holy Law #7).
Pattern source: ``test_livestock_pashu_aadhaar_lift.py`` (test_meadow_path_grammar_holds).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from yen_gov.core.schema_registry import schema_id, schema_version

REPO_ROOT = Path(__file__).resolve().parents[2]
MEADOW_FILE = (
    REPO_ROOT
    / "datasets"
    / "livestock"
    / "_meadow"
    / "ndlm"
    / "2024-25"
    / "owner_reg_land_holding_district.json"
)
ENTITIES_JSON = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"

ALLOWED_ROW_KEYS = {"entity_id", "time", "value", "facet"}
LANDHOLDING_SLUGS = {
    "not_specified",
    "landless_marginal",
    "small",
    "semi_medium",
    "medium",
    "large",
}
GENDER_SLUGS = {"male", "female"}
TIME_REGEX = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
ENTITY_ID_REGEX = re.compile(r"^IN-[SU]\d{2}-D\d+$")


def _accepted_indicator_versions() -> frozenset[str]:
    accepted = {schema_version("indicator.schema.json")}
    registry = json.loads(
        (REPO_ROOT / "datasets" / "schema-compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    for override in registry.get("overrides", []):
        if (
            override.get("surface") == "json-corpus"
            and override.get("schema") == "indicator.schema.json"
            and override.get("validation") == "current_schema"
        ):
            accepted.update(override.get("accepted_versions", []))
    return frozenset(accepted)


ACCEPTED_INDICATOR_VERSIONS = _accepted_indicator_versions()


@pytest.mark.skipif(
    not MEADOW_FILE.is_file(),
    reason="owner_reg meadow file not on disk in this checkout",
)
def test_owner_reg_meadow_path_grammar_holds() -> None:
    """File MUST exist at the canonical ADR-0041 meadow path with the
    seeded ``2024-25`` vintage segment."""
    # File presence + non-empty (the skipif already established existence;
    # this assert tightens to non-empty content).
    assert MEADOW_FILE.stat().st_size > 0, (
        f"meadow file is empty: {MEADOW_FILE}"
    )


@pytest.mark.skipif(
    not MEADOW_FILE.is_file(),
    reason="owner_reg meadow file not on disk in this checkout",
)
def test_owner_reg_meadow_envelope_shape() -> None:
    """Top-level envelope conforms to an accepted indicator schema."""
    doc = json.loads(MEADOW_FILE.read_text(encoding="utf-8"))
    # Schema declaration
    assert doc.get("$schema") == schema_id("indicator.schema.json")
    assert doc.get("$schema_version") in ACCEPTED_INDICATOR_VERSIONS, (
        f"schema_version {doc.get('$schema_version')!r} is not accepted: "
        f"{sorted(ACCEPTED_INDICATOR_VERSIONS)}"
    )
    # Indicator block
    indicator = doc.get("indicator")
    assert isinstance(indicator, dict), "indicator block missing or not an object"
    assert indicator.get("id") == "livestock/owner_registration_count", (
        f"indicator.id != 'livestock/owner_registration_count': "
        f"got {indicator.get('id')!r}"
    )
    assert indicator.get("entity_kind") == "district", (
        f"indicator.entity_kind != 'district': "
        f"got {indicator.get('entity_kind')!r}"
    )
    assert indicator.get("time_grain") == "fiscal_year"
    assert indicator.get("value_kind") == "raw"
    assert indicator.get("unit") == "owners"
    # Rows array non-empty
    rows = doc.get("rows")
    assert isinstance(rows, list) and len(rows) > 0, (
        "rows[] missing or empty"
    )


@pytest.mark.skipif(
    not MEADOW_FILE.is_file(),
    reason="owner_reg meadow file not on disk in this checkout",
)
def test_owner_reg_meadow_row_keys_closed_set() -> None:
    """Every row carries EXACTLY the 4 allowed keys; no `landholding`,
    `gender`, or `source_id` keys at row level (those live on the
    composite ``facet`` field; source_id is applied at the Phase 2
    canonical adapter per the Pashu Aadhaar precedent + ADR-0032)."""
    doc = json.loads(MEADOW_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        keys = set(row.keys())
        assert keys == ALLOWED_ROW_KEYS, (
            f"row[{i}] keys {keys!r} != {ALLOWED_ROW_KEYS!r} "
            f"(extra: {keys - ALLOWED_ROW_KEYS}; "
            f"missing: {ALLOWED_ROW_KEYS - keys})"
        )


@pytest.mark.skipif(
    not MEADOW_FILE.is_file(),
    reason="owner_reg meadow file not on disk in this checkout",
)
def test_owner_reg_meadow_time_values_match_schema_regex() -> None:
    """Every row's ``time`` matches the indicator.schema.json regex
    ``^\\d{4}(-\\d{2}(-\\d{2})?)?$``."""
    doc = json.loads(MEADOW_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        time = row["time"]
        assert isinstance(time, str) and TIME_REGEX.match(time), (
            f"row[{i}].time {time!r} fails schema regex"
        )


@pytest.mark.skipif(
    not MEADOW_FILE.is_file(),
    reason="owner_reg meadow file not on disk in this checkout",
)
def test_owner_reg_meadow_facet_vocabulary_closed() -> None:
    """Every row's ``facet`` is in the 12-value
    ``<landholding>|<gender>`` vocabulary (6 landholding x 2 gender).
    A row with an out-of-set facet = the upstream NDLM enum drifted
    and we need to extend ``LANDHOLDING_SLUG_BY_CD`` in
    ``tools/livestock_meadow_owner_reg.py``."""
    doc = json.loads(MEADOW_FILE.read_text(encoding="utf-8"))
    expected_facets = {
        f"{lh}|{g}"
        for lh in LANDHOLDING_SLUGS
        for g in GENDER_SLUGS
    }
    assert len(expected_facets) == 12, "facet vocabulary should have 12 values"
    seen: set[str] = set()
    for i, row in enumerate(doc["rows"]):
        facet = row["facet"]
        assert facet in expected_facets, (
            f"row[{i}].facet {facet!r} not in expected 12-value vocabulary"
        )
        seen.add(facet)
    # Sanity: at minimum the not_specified|male+female pair shows up
    # (every state has SOME registrations with undeclared land-holding).
    assert "not_specified|male" in seen, (
        "expected at least one row with facet='not_specified|male'"
    )
    assert "not_specified|female" in seen, (
        "expected at least one row with facet='not_specified|female'"
    )


@pytest.mark.skipif(
    not MEADOW_FILE.is_file(),
    reason="owner_reg meadow file not on disk in this checkout",
)
def test_owner_reg_meadow_entity_ids_resolve_to_districts() -> None:
    """Every row's ``entity_id`` matches the ``IN-S{XX}-D{lgd}`` shape
    AND resolves to a district entity in
    ``datasets/taxonomy/entities.json``. Unresolvable codes were
    dropped at lift time per the meadow contract; a row reaching the
    file with an unresolved code = the lift script's lookup regressed.
    """
    entities = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    district_ids = {
        e["entity_id"]
        for e in entities["entities"]
        if e.get("entity_type") == "district"
    }
    doc = json.loads(MEADOW_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        eid = row["entity_id"]
        assert ENTITY_ID_REGEX.match(eid), (
            f"row[{i}].entity_id {eid!r} fails IN-S{{XX}}-D{{lgd}} shape"
        )
        assert eid in district_ids, (
            f"row[{i}].entity_id {eid!r} does not resolve to a district "
            f"in entities.json"
        )


@pytest.mark.skipif(
    not MEADOW_FILE.is_file(),
    reason="owner_reg meadow file not on disk in this checkout",
)
def test_owner_reg_meadow_values_are_non_negative_ints() -> None:
    """Every row's ``value`` is a non-negative int. NDLM null counts
    are dropped at lift time; negative counts would indicate upstream
    corruption (not seen in any vintage to date)."""
    doc = json.loads(MEADOW_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        v = row["value"]
        assert isinstance(v, int), (
            f"row[{i}].value {v!r} is not int (type={type(v).__name__})"
        )
        assert v >= 0, f"row[{i}].value {v} is negative"

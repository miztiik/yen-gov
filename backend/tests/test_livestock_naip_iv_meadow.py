"""Tier-A contract tests for the livestock NDLM NAIP IV meadow files.

Asserts ``datasets/livestock/_meadow/ndlm/2024-25/naip_iv_district.json``
+ ``datasets/livestock/_meadow/ndlm/2024-25/naip_header_count_national.json``
satisfy the meadow grammar declared by Phase 1.C of the NDLM ingest plan
(``TODO/20260525-livestock-ndlm-ingest-plan.md`` section 11):

* Files exist at the canonical ADR-0041 meadow path. The vintage
  segment ``2024-25`` matches the seeded ``src-93a2a72db482`` citation
  row in ``datasets/taxonomy/sources.parquet`` (PR #276).
* JSON conforms to a compatibility-accepted ``indicator.schema.json`` shape:
  ``rows.items`` carries only the closed-set
  ``{entity_id, time, value, facet}`` keys.
* Every ``time`` matches the schema regex ``^\\d{4}(-\\d{2}(-\\d{2})?)?$``.
* District ``facet`` is in the 5-value vocabulary
  (``{metric_family}|{sex_or_none}``); national-header ``facet`` is in
  the 3-value programme vocabulary.
* Every district ``entity_id`` resolves to a district entity in
  ``datasets/taxonomy/entities.json`` and matches the
  ``IN-S{XX}-D{lgd}`` / ``IN-U{XX}-D{lgd}`` shape; the header
  ``entity_id`` is always ``IN``.
* No fabricated zeros: ``value`` is a non-negative integer per meadow
  contract; NDLM null counts are dropped at lift time.

Uses the real on-disk meadow files (no mocks per CLAUDE.md ss 10 Holy
Law #7).

Pattern source: ``test_livestock_owner_reg_meadow.py`` (PR #298).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from yen_gov.core.schema_registry import schema_id, schema_version

REPO_ROOT = Path(__file__).resolve().parents[2]
MEADOW_DIR = (
    REPO_ROOT
    / "datasets"
    / "livestock"
    / "_meadow"
    / "ndlm"
    / "2024-25"
)
DISTRICT_FILE = MEADOW_DIR / "naip_iv_district.json"
HEADER_FILE = MEADOW_DIR / "naip_header_count_national.json"
ENTITIES_JSON = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"

ALLOWED_ROW_KEYS = {"entity_id", "time", "value", "facet"}
METRIC_FAMILIES = {
    "inseminations",
    "pregnancy_diagnoses",
    "calves_born",
    "farmers_benefitted",
}
DISTRICT_EXPECTED_FACETS = {
    "inseminations|none",
    "pregnancy_diagnoses|none",
    "calves_born|m",
    "calves_born|f",
    "farmers_benefitted|none",
}
HEADER_EXPECTED_FACETS = {
    "naip_iv|none",
    "abip|none",
    "others|none",
}
TIME_REGEX = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
DISTRICT_ENTITY_ID_REGEX = re.compile(r"^IN-[SU]\d{2}-D\d+$")


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
    not DISTRICT_FILE.is_file(),
    reason="naip_iv district meadow file not on disk in this checkout",
)
def test_naip_iv_district_meadow_envelope_shape() -> None:
    """Top-level envelope conforms to an accepted indicator schema."""
    doc = json.loads(DISTRICT_FILE.read_text(encoding="utf-8"))
    # Schema declaration
    assert doc.get("$schema") == schema_id("indicator.schema.json")
    assert doc.get("$schema_version") in ACCEPTED_INDICATOR_VERSIONS, (
        f"schema_version {doc.get('$schema_version')!r} is not accepted: "
        f"{sorted(ACCEPTED_INDICATOR_VERSIONS)}"
    )
    # Indicator block
    indicator = doc.get("indicator")
    assert isinstance(indicator, dict), (
        "indicator block missing or not an object"
    )
    assert indicator.get("id") == "livestock/naip_iv_outcomes_count", (
        f"indicator.id != 'livestock/naip_iv_outcomes_count': "
        f"got {indicator.get('id')!r}"
    )
    assert indicator.get("entity_kind") == "district", (
        f"indicator.entity_kind != 'district': "
        f"got {indicator.get('entity_kind')!r}"
    )
    assert indicator.get("time_grain") == "fiscal_year"
    assert indicator.get("value_kind") == "raw"
    assert indicator.get("unit") == "count"
    # Rows array non-empty
    rows = doc.get("rows")
    assert isinstance(rows, list) and len(rows) > 0, (
        "rows[] missing or empty"
    )


@pytest.mark.skipif(
    not DISTRICT_FILE.is_file(),
    reason="naip_iv district meadow file not on disk in this checkout",
)
def test_naip_iv_district_meadow_row_keys_closed_set() -> None:
    """Every row carries EXACTLY the 4 allowed keys; no `metric`,
    `sex`, or `source_id` keys at row level (those live on the
    composite ``facet`` field; source_id is applied at the Phase 2
    canonical adapter per the Owner Reg precedent + ADR-0032)."""
    doc = json.loads(DISTRICT_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        keys = set(row.keys())
        assert keys == ALLOWED_ROW_KEYS, (
            f"row[{i}] keys {keys!r} != {ALLOWED_ROW_KEYS!r} "
            f"(extra: {keys - ALLOWED_ROW_KEYS}; "
            f"missing: {ALLOWED_ROW_KEYS - keys})"
        )


@pytest.mark.skipif(
    not DISTRICT_FILE.is_file(),
    reason="naip_iv district meadow file not on disk in this checkout",
)
def test_naip_iv_district_meadow_time_values_match_schema_regex() -> None:
    """Every row's ``time`` matches the indicator.schema.json regex
    ``^\\d{4}(-\\d{2}(-\\d{2})?)?$``."""
    doc = json.loads(DISTRICT_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        time = row["time"]
        assert isinstance(time, str) and TIME_REGEX.match(time), (
            f"row[{i}].time {time!r} fails schema regex"
        )


@pytest.mark.skipif(
    not DISTRICT_FILE.is_file(),
    reason="naip_iv district meadow file not on disk in this checkout",
)
def test_naip_iv_district_meadow_facet_vocabulary_closed() -> None:
    """Every row's ``facet`` is in the 5-value
    ``<metric_family>|<sex>`` vocabulary. A row with an out-of-set
    facet = the lift script's metric extraction regressed (an upstream
    NDLM field was renamed) and we need to extend the facet pairs in
    ``_emit_district_rows`` in ``tools/livestock_meadow_naip_iv.py``."""
    doc = json.loads(DISTRICT_FILE.read_text(encoding="utf-8"))
    assert len(DISTRICT_EXPECTED_FACETS) == 5, (
        "district facet vocabulary should have 5 values"
    )
    seen: set[str] = set()
    for i, row in enumerate(doc["rows"]):
        facet = row["facet"]
        assert facet in DISTRICT_EXPECTED_FACETS, (
            f"row[{i}].facet {facet!r} not in expected 5-value vocabulary"
        )
        seen.add(facet)
    # Sanity: at minimum the inseminations + pregnancy_diagnoses
    # rollups show up (every state with NAIP IV coverage reports at
    # least these two metrics for at least one district).
    assert "inseminations|none" in seen, (
        "expected at least one row with facet='inseminations|none'"
    )
    assert "pregnancy_diagnoses|none" in seen, (
        "expected at least one row with facet='pregnancy_diagnoses|none'"
    )
    # Calves rows are only emitted when the sex split is non-null;
    # at least some districts in the FY 2024-25 corpus report both.
    assert "calves_born|m" in seen, (
        "expected at least one row with facet='calves_born|m'"
    )
    assert "calves_born|f" in seen, (
        "expected at least one row with facet='calves_born|f'"
    )


@pytest.mark.skipif(
    not DISTRICT_FILE.is_file(),
    reason="naip_iv district meadow file not on disk in this checkout",
)
def test_naip_iv_district_meadow_entity_ids_resolve_to_districts() -> None:
    """Every row's ``entity_id`` matches the ``IN-{S|U}{XX}-D{lgd}``
    shape AND resolves to a district entity in
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
    doc = json.loads(DISTRICT_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        eid = row["entity_id"]
        assert DISTRICT_ENTITY_ID_REGEX.match(eid), (
            f"row[{i}].entity_id {eid!r} fails IN-{{S|U}}{{XX}}-D{{lgd}} shape"
        )
        assert eid in district_ids, (
            f"row[{i}].entity_id {eid!r} does not resolve to a district "
            f"in entities.json"
        )


@pytest.mark.skipif(
    not DISTRICT_FILE.is_file(),
    reason="naip_iv district meadow file not on disk in this checkout",
)
def test_naip_iv_district_meadow_values_are_non_negative_ints() -> None:
    """Every row's ``value`` is a non-negative int. NDLM null counts
    are dropped at lift time; negative counts would indicate upstream
    corruption (not seen in any vintage to date)."""
    doc = json.loads(DISTRICT_FILE.read_text(encoding="utf-8"))
    for i, row in enumerate(doc["rows"]):
        v = row["value"]
        assert isinstance(v, int), (
            f"row[{i}].value {v!r} is not int (type={type(v).__name__})"
        )
        assert v >= 0, f"row[{i}].value {v} is negative"


@pytest.mark.skipif(
    not HEADER_FILE.is_file(),
    reason="naip_iv national header meadow file not on disk in this checkout",
)
def test_naip_header_national_meadow_shape_and_facets() -> None:
    """National header rollup carries the country-grain envelope +
    the 3-programme facet vocabulary. Serves as a sanity-check
    fixture; not routed to the Phase 2 catalogue slugs."""
    doc = json.loads(HEADER_FILE.read_text(encoding="utf-8"))
    # Schema declaration
    assert doc.get("$schema") == schema_id("indicator.schema.json")
    assert doc.get("$schema_version") in ACCEPTED_INDICATOR_VERSIONS, (
        f"schema_version {doc.get('$schema_version')!r} is not accepted: "
        f"{sorted(ACCEPTED_INDICATOR_VERSIONS)}"
    )
    # Indicator block
    indicator = doc.get("indicator")
    assert isinstance(indicator, dict), (
        "indicator block missing or not an object"
    )
    assert indicator.get("id") == "livestock/naip_header_cumulative_count", (
        f"indicator.id != 'livestock/naip_header_cumulative_count': "
        f"got {indicator.get('id')!r}"
    )
    assert indicator.get("entity_kind") == "country", (
        f"indicator.entity_kind != 'country': "
        f"got {indicator.get('entity_kind')!r}"
    )
    assert indicator.get("time_grain") == "fiscal_year"
    assert indicator.get("value_kind") == "raw"
    # Rows: 3 programmes x 1 vintage = 3 rows. All bind to entity 'IN'.
    rows = doc.get("rows")
    assert isinstance(rows, list) and len(rows) >= 1, (
        "rows[] missing or empty"
    )
    seen_facets: set[str] = set()
    for i, row in enumerate(rows):
        keys = set(row.keys())
        assert keys == ALLOWED_ROW_KEYS, (
            f"row[{i}] keys {keys!r} != {ALLOWED_ROW_KEYS!r}"
        )
        assert row["entity_id"] == "IN", (
            f"row[{i}].entity_id {row['entity_id']!r} != 'IN' "
            f"(national header is country-grain)"
        )
        time = row["time"]
        assert isinstance(time, str) and TIME_REGEX.match(time), (
            f"row[{i}].time {time!r} fails schema regex"
        )
        facet = row["facet"]
        assert facet in HEADER_EXPECTED_FACETS, (
            f"row[{i}].facet {facet!r} not in expected 3-programme "
            f"vocabulary"
        )
        assert isinstance(row["value"], int) and row["value"] >= 0, (
            f"row[{i}].value {row['value']!r} is not a non-negative int"
        )
        seen_facets.add(facet)
    # Sanity: NAIP IV programme rollup MUST be present (this is the
    # primary cross-check signal for the district file).
    assert "naip_iv|none" in seen_facets, (
        "national header file MUST include the NAIP IV programme rollup"
    )

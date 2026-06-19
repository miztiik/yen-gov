"""Tests for ``yen_gov.canonical.ingest`` (Row 1 of the ingest plan).

Covers the row's gates + the one oracle:

* gate -- a bogus ``indicator_id`` RAISES at registration;
* gate -- a ``(unit / normalisation / price_basis / sampling_frame)``
  mismatch RAISES;
* gate -- ``CanonicalBatch.source_rows`` is the 5-field source.csv shape;
* oracle -- ``CanonicalBatch.observation_rows[*]`` keys == the non-facet
  ``geo/*.csv`` column set AND a price-basis-mismatched ``IndicatorSpec``
  fails registration.

Per CLAUDE.md section 10 these tests never walk the real corpus: the
catalogue checks run against synthetic in-memory fixtures, plus one
``tmp_path`` disk-read smoke. The two drift-guard tests read the small
``columns.json`` contract artifact (the data-shape SOT, not the corpus) so
the pydantic row shapes can never silently disagree with it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.ingest import (
    CanonicalBatch,
    CanonicalObservationRow,
    CanonicalSourceRow,
    CatalogueFkError,
    ConceptCompatibilityError,
    ClaimCheck,
    IndicatorSpec,
    PriceBasis,
    RawRecord,
    ReplacementSemantics,
    SourceSpec,
    check_indicator_registration,
)

_SRC = "src-abc123def456"

# --- synthetic catalogue fixtures (never the real corpus, per section 10) ---

_CONCEPTS = [
    {
        "concept_id": "nsdp-current",
        "noun": "NSDP (current prices)",
        "unit_canonical": "inr-crore",
        "normalisation": "absolute",
        "entity_kinds": ["state"],
        "description_short": "Net State Domestic Product at current prices.",
        "sources": [],
        "price_basis": {"basis": "current", "base_year": None},
    },
    {
        "concept_id": "cattle-tags",
        "noun": "Cattle tags",
        "unit_canonical": "animals",
        "normalisation": "absolute",
        "entity_kinds": ["state"],
        "description_short": "Cattle tagged.",
        "sources": [],
        "sampling_frame": "ndlm-pashu-aadhaar-tag-register",
    },
    {
        "concept_id": "turnout-frac",
        "noun": "Turnout",
        "unit_canonical": "%",
        "normalisation": "share",
        "entity_kinds": ["state"],
        "description_short": "Voter turnout.",
        "sources": [],
    },
]

_INDICATORS = [
    {"indicator_id": "nsdp-current-inr", "concept_id": "nsdp-current", "unit": "inr-crore"},
    {"indicator_id": "cattle-tagged-count", "concept_id": "cattle-tags", "unit": "animals"},
    {"indicator_id": "state-turnout-pct", "concept_id": "turnout-frac", "unit": "%"},
    {"indicator_id": "orphan-no-concept", "concept_id": "missing-concept", "unit": "x"},
]


def _check(spec: IndicatorSpec) -> None:
    check_indicator_registration(spec, indicators=_INDICATORS, concepts=_CONCEPTS)


# --------------------------------------------------------------------------
# Drift guards: pydantic row shapes are pinned to columns.json (the SOT).
# --------------------------------------------------------------------------

def _geo_columns() -> set[str]:
    fc = load_columns().for_glob("datasets/data/datapoints/geo/*.csv")
    return {c.name for c in fc.columns}


def _source_columns() -> set[str]:
    fc = load_columns().for_glob("datasets/data/entities/source.csv")
    return {c.name for c in fc.columns}


def test_observation_row_keys_match_geo_columns() -> None:
    # ORACLE: the canonical observation shape == the non-facet geo/*.csv set.
    assert _geo_columns() == {"entity_id", "time", "value", "source_id"}
    assert set(CanonicalObservationRow.model_fields) == _geo_columns()


def test_source_row_is_five_field_shape() -> None:
    # GATE: source_rows is the 5-field source.csv shape, NOT the old 11-field row.
    assert set(CanonicalSourceRow.model_fields) == {
        "source_id",
        "producer",
        "title",
        "vintage",
        "url",
    }
    assert set(CanonicalSourceRow.model_fields) == _source_columns()


def test_canonical_batch_observation_rows_carry_geo_keys() -> None:
    # ORACLE (batch level): every observation row dumps exactly the geo keys;
    # the indicator is the batch/file identity, never a row column.
    batch = CanonicalBatch(
        indicator_id="nsdp-current-inr",
        observation_rows=[
            CanonicalObservationRow(
                entity_id="IN-S01", time=2011, value=1.5, source_id=_SRC
            ),
        ],
        source_rows=[
            CanonicalSourceRow(
                source_id=_SRC, producer="P", title="T", vintage="2011-12"
            ),
        ],
    )
    assert "indicator_id" not in _geo_columns()
    for row in batch.observation_rows:
        assert set(row.model_dump().keys()) == _geo_columns()
    assert batch.replacement_semantics is ReplacementSemantics.upsert


# --------------------------------------------------------------------------
# Spec field-split ruling (Gregor): no field repeated across levels.
# --------------------------------------------------------------------------

def test_no_field_repeated_across_spec_levels() -> None:
    source_only = set(SourceSpec.model_fields) - {"indicators"}
    indicator_fields = set(IndicatorSpec.model_fields)
    assert source_only.isdisjoint(indicator_fields)
    assert source_only == {"adapter_slug", "producer", "title", "vintage", "url"}
    assert indicator_fields == {
        "indicator_id",
        "unit",
        "normalisation",
        "price_basis",
        "sampling_frame",
    }


def test_source_spec_derives_source_id_and_carries_children() -> None:
    s = SourceSpec(
        adapter_slug="rbi-handbook",
        producer="Reserve Bank of India",
        title="Handbook of Statistics on Indian States",
        vintage="2024-25",
        indicators=(
            IndicatorSpec(
                indicator_id="state-turnout-pct", unit="%", normalisation="share"
            ),
        ),
    )
    assert s.source_id == derive_source_id(
        "Reserve Bank of India", "Handbook of Statistics on Indian States", "2024-25"
    )
    # source_id is a derived property, not a stored model field.
    assert "source_id" not in SourceSpec.model_fields
    assert len(s.indicators) == 1


def test_specs_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        IndicatorSpec(
            indicator_id="x-y", unit="u", normalisation="absolute", bogus=1
        )
    with pytest.raises(ValidationError):
        SourceSpec(
            adapter_slug="a",
            producer="p",
            title="t",
            vintage="v",
            indicators=(),  # min_length=1 -> empty tuple is rejected
        )


# --------------------------------------------------------------------------
# Catalogue FK (a): indicator_id must resolve.
# --------------------------------------------------------------------------

def test_fk_pass_on_known_indicator() -> None:
    _check(IndicatorSpec(indicator_id="state-turnout-pct", unit="%", normalisation="share"))


def test_fk_fail_on_bogus_indicator() -> None:
    with pytest.raises(CatalogueFkError) as exc:
        _check(
            IndicatorSpec(
                indicator_id="totally-bogus", unit="x", normalisation="absolute"
            )
        )
    assert "totally-bogus" in str(exc.value)


def test_fk_fail_on_dangling_concept() -> None:
    with pytest.raises(CatalogueFkError) as exc:
        _check(
            IndicatorSpec(
                indicator_id="orphan-no-concept", unit="x", normalisation="absolute"
            )
        )
    assert "missing-concept" in str(exc.value)


# --------------------------------------------------------------------------
# Concept compatibility (b): the measurement tuple must match the concept.
# --------------------------------------------------------------------------

def test_unit_mismatch_raises() -> None:
    with pytest.raises(ConceptCompatibilityError) as exc:
        _check(
            IndicatorSpec(
                indicator_id="nsdp-current-inr",
                unit="wrong-unit",
                normalisation="absolute",
                price_basis=PriceBasis(basis="current", base_year=None),
            )
        )
    assert "unit" in str(exc.value)


def test_normalisation_mismatch_raises() -> None:
    with pytest.raises(ConceptCompatibilityError) as exc:
        _check(
            IndicatorSpec(
                indicator_id="state-turnout-pct",
                unit="%",
                normalisation="absolute",  # concept is share
            )
        )
    assert "normalisation" in str(exc.value)


def test_price_basis_match_passes() -> None:
    _check(
        IndicatorSpec(
            indicator_id="nsdp-current-inr",
            unit="inr-crore",
            normalisation="absolute",
            price_basis=PriceBasis(basis="current", base_year=None),
        )
    )


def test_price_basis_mismatch_raises_constant_vs_current() -> None:
    # ORACLE: a price-basis-mismatched IndicatorSpec fails registration.
    with pytest.raises(ConceptCompatibilityError) as exc:
        _check(
            IndicatorSpec(
                indicator_id="nsdp-current-inr",
                unit="inr-crore",
                normalisation="absolute",
                price_basis=PriceBasis(basis="constant", base_year=2011),
            )
        )
    assert "price_basis" in str(exc.value)


def test_price_basis_mismatch_raises_none_vs_current() -> None:
    with pytest.raises(ConceptCompatibilityError) as exc:
        _check(
            IndicatorSpec(
                indicator_id="nsdp-current-inr",
                unit="inr-crore",
                normalisation="absolute",
                price_basis=None,  # concept declares current
            )
        )
    assert "price_basis" in str(exc.value)


def test_sampling_frame_match_passes() -> None:
    _check(
        IndicatorSpec(
            indicator_id="cattle-tagged-count",
            unit="animals",
            normalisation="absolute",
            sampling_frame="ndlm-pashu-aadhaar-tag-register",
        )
    )


def test_sampling_frame_mismatch_raises() -> None:
    with pytest.raises(ConceptCompatibilityError) as exc:
        _check(
            IndicatorSpec(
                indicator_id="cattle-tagged-count",
                unit="animals",
                normalisation="absolute",
                sampling_frame=None,  # concept declares a frame
            )
        )
    assert "sampling_frame" in str(exc.value)


def test_null_price_basis_and_frame_match_plain_concept() -> None:
    # A concept with neither field set is compatible with a spec declaring
    # neither (the common case for the 152 null concepts).
    _check(
        IndicatorSpec(
            indicator_id="state-turnout-pct", unit="%", normalisation="share"
        )
    )


# --------------------------------------------------------------------------
# Disk-read branch (default-path wiring) via tmp_path fixtures.
# --------------------------------------------------------------------------

def test_check_reads_from_disk_paths(tmp_path: Path) -> None:
    ind = tmp_path / "indicators.json"
    con = tmp_path / "concepts.json"
    ind.write_text(json.dumps({"indicators": _INDICATORS}), encoding="utf-8")
    con.write_text(json.dumps({"concepts": _CONCEPTS}), encoding="utf-8")
    check_indicator_registration(
        IndicatorSpec(
            indicator_id="cattle-tagged-count",
            unit="animals",
            normalisation="absolute",
            sampling_frame="ndlm-pashu-aadhaar-tag-register",
        ),
        indicators_path=ind,
        concepts_path=con,
    )
    with pytest.raises(CatalogueFkError):
        check_indicator_registration(
            IndicatorSpec(indicator_id="nope-x", unit="x", normalisation="absolute"),
            indicators_path=ind,
            concepts_path=con,
        )


# --------------------------------------------------------------------------
# Stage messages: construction validity + frozen-ness.
# --------------------------------------------------------------------------

def test_claim_check_and_raw_record_construct() -> None:
    cc = ClaimCheck(
        adapter_slug="rbi-handbook",
        cache_key="rbi-handbook:2011",
        content_hash="0" * 64,
        payload_ref="datasets/energy/_meadow/rbi/2011/raw.json",
    )
    assert cc.adapter_slug == "rbi-handbook"
    rr = RawRecord(
        indicator_id="nsdp-current-inr",
        source_id=_SRC,
        raw_entity="Tamil Nadu",
        raw_period="2011-12",
        value_numeric=12345.0,
    )
    assert rr.value_text is None


def test_claim_check_rejects_non_sha256_hash() -> None:
    with pytest.raises(ValidationError):
        ClaimCheck(
            adapter_slug="a",
            cache_key="k",
            content_hash="not-a-hash",
            payload_ref="datasets/x/_meadow/raw.json",
        )

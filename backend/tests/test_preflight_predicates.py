"""Pre-flight predicate unit tests + Tier-B parity test.

The parity test is load-bearing per ADR-0046 -- it guarantees the
Tier-B wrappers in ``yen_gov.validate`` and the predicates in
``yen_gov.preflight.predicates`` cannot drift on the rules they enforce.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov import validate as v
from yen_gov.preflight import predicates as P


# --- 1. grain prefix ---------------------------------------------------

@pytest.mark.parametrize(
    "indicator_id,expected",
    [
        ("installed-capacity-mw", None),
        ("livestock-pashu-aadhaar-count", None),
        ("state-installed-capacity-mw", "state-"),
        ("district-pashu-aadhaar-count", "district-"),
        ("national-gdp-inr-crore", "national-"),
        ("ac-winner-party-id", None),  # ac- is an entity_kind, not a grain prefix
        ("statewise-foo", None),  # only exact 'state-' prefix counts
    ],
)
def test_grain_prefix_violation(indicator_id, expected):
    got = P.grain_prefix_violation(indicator_id)
    assert (got is None and expected is None) or (got == expected)


# --- 2. update_period_days --------------------------------------------

@pytest.mark.parametrize(
    "value,is_violation",
    [
        (30, False),
        (365, False),
        (3650, False),
        (1, False),
        (0, True),
        (-1, True),
        (None, True),
        ("365", True),
        (3.14, True),
        (True, True),  # bool is int subclass -- explicitly rejected
    ],
)
def test_update_period_days_violation(value, is_violation):
    got = P.update_period_days_violation(value)
    assert (got is None) != is_violation


# --- 3. justification --------------------------------------------------

def test_justification_violation_short_rejected():
    assert P.justification_violation("too short") is not None


def test_justification_violation_long_accepted():
    s = "different sampling frame: ECI booth-level vs CEO state aggregate"
    assert P.justification_violation(s) is None


def test_justification_violation_whitespace_only_rejected():
    assert P.justification_violation("   " * 20) is not None


def test_justification_violation_non_string_rejected():
    assert P.justification_violation(None) is not None
    assert P.justification_violation(42) is not None


# --- 4. concept_id_exists ---------------------------------------------

def test_concept_id_exists_true():
    rows = [{"concept_id": "gdp-inr-crore"}, {"concept_id": "population"}]
    assert P.concept_id_exists("gdp-inr-crore", rows) is True


def test_concept_id_exists_false():
    rows = [{"concept_id": "gdp-inr-crore"}]
    assert P.concept_id_exists("nonexistent", rows) is False


def test_concept_id_exists_empty_registry():
    assert P.concept_id_exists("anything", []) is False


# --- 5. source_id derivation ------------------------------------------

def test_source_id_derivation_none_accepted():
    assert P.source_id_derivation_violation(
        producer="NDLM", title="t", vintage="2024-25", claimed=None
    ) is None


def test_source_id_derivation_correct_match():
    from yen_gov.canonical.citation import derive_source_id
    derived = derive_source_id("NDLM", "t", "2024-25")
    assert P.source_id_derivation_violation(
        producer="NDLM", title="t", vintage="2024-25", claimed=derived
    ) is None


def test_source_id_derivation_mismatch_rejected():
    err = P.source_id_derivation_violation(
        producer="NDLM", title="t", vintage="2024-25",
        claimed="src-deadbeefcafe",
    )
    assert err is not None
    assert "derive_source_id" in err


# --- 6. hand_typed_source_id_hits -------------------------------------

def test_hand_typed_source_id_hits_clean():
    assert P.hand_typed_source_id_hits('s = "no hits here"\n') == []


def test_hand_typed_source_id_hits_assign_detected():
    text = '\nSOURCE_IDS = {"foo": "bar"}\n'
    hits = P.hand_typed_source_id_hits(text)
    assert any(snippet == "SOURCE_IDS=" for snippet, _ in hits)


def test_hand_typed_source_id_hits_hex_literal_detected():
    text = '\nx = "src-abc123def456"\n'
    hits = P.hand_typed_source_id_hits(text)
    assert any('"src-' in snippet for snippet, _ in hits)


# --- 7. cross-grain twin clustering -----------------------------------

def test_cross_grain_twin_concepts_finds_twin():
    rows = [
        {"indicator_id": "a", "concept_id": "gdp", "entity_kinds": ["country"]},
        {"indicator_id": "b", "concept_id": "gdp", "entity_kinds": ["state"]},
        {"indicator_id": "c", "concept_id": "population", "entity_kinds": ["state"]},
    ]
    assert P.cross_grain_twin_concepts(rows) == {"gdp"}


# --- 8. concept proliferation clusters --------------------------------

def test_concept_proliferation_clusters():
    rows = [
        {"indicator_id": "x", "concept_id": "coal", "entity_kinds": ["state"]},
        {"indicator_id": "y", "concept_id": "coal", "entity_kinds": ["state"]},
        {"indicator_id": "z", "concept_id": "gas", "entity_kinds": ["state"]},
    ]
    clusters = P.concept_proliferation_clusters(rows)
    assert len(clusters) == 1
    cid, eks, ids = clusters[0]
    assert cid == "coal"
    assert eks == ("state",)
    assert ids == ["x", "y"]


# --- 9. Tier-B parity (load-bearing per ADR-0046) ---------------------

def _write_indicator_catalogue(root: Path, rows: list[dict]) -> None:
    (root / "datasets" / "taxonomy").mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "../schemas/indicator-catalogue.schema.json",
        "$schema_version": "2.3",
        "indicators": rows,
    }
    (root / "datasets" / "taxonomy" / "indicators.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_predicate_parity_with_tier_b_grain_prefix(tmp_path):
    """tier_b_indicator_id_no_grain_prefix must report exactly the rows
    that ``predicates.grain_prefix_violation`` flags."""
    rows = [
        {"indicator_id": "good-one-mw", "entity_kinds": ["country"], "update_period_days": 365},
        {"indicator_id": "state-bad-one-mw", "entity_kinds": ["state"], "update_period_days": 365},
        {"indicator_id": "national-bad-two-mw", "entity_kinds": ["country"], "update_period_days": 365},
    ]
    _write_indicator_catalogue(tmp_path, rows)

    tier_b_failures = v.tier_b_indicator_id_no_grain_prefix(tmp_path)
    predicate_violations = [
        r["indicator_id"] for r in rows
        if P.grain_prefix_violation(r["indicator_id"]) is not None
    ]
    assert len(tier_b_failures) == len(predicate_violations) == 2
    for vid in predicate_violations:
        assert any(vid in f.message for f in tier_b_failures), (
            f"tier-B did not report {vid}"
        )


def test_predicate_parity_with_tier_b_freshness(tmp_path):
    rows = [
        {"indicator_id": "good", "entity_kinds": ["country"], "update_period_days": 365},
        {"indicator_id": "no-cadence", "entity_kinds": ["country"]},
        {"indicator_id": "zero-cadence", "entity_kinds": ["country"], "update_period_days": 0},
    ]
    _write_indicator_catalogue(tmp_path, rows)

    tier_b_failures = v.tier_b_indicator_freshness_declared(tmp_path)
    predicate_violations = [
        r["indicator_id"] for r in rows
        if P.update_period_days_violation(r.get("update_period_days")) is not None
    ]
    assert len(tier_b_failures) == len(predicate_violations) == 2


def test_predicate_parity_with_tier_b_justification(tmp_path):
    rows = [
        {"indicator_id": "country-coal", "concept_id": "coal", "entity_kinds": ["country"],
         "update_period_days": 365, "meta": {"justification": "x" * 25}},
        {"indicator_id": "state-coal", "concept_id": "coal", "entity_kinds": ["state"],
         "update_period_days": 365},  # cross-grain twin, NO justification -> violation
    ]
    _write_indicator_catalogue(tmp_path, rows)

    tier_b_failures = v.tier_b_indicator_has_justification(tmp_path)
    twins = P.cross_grain_twin_concepts(rows)
    expected = [
        r["indicator_id"] for r in rows
        if r.get("concept_id") in twins
        and P.justification_violation(r.get("meta", {}).get("justification")) is not None
    ]
    assert len(tier_b_failures) == len(expected) == 1
    assert "state-coal" in tier_b_failures[0].message

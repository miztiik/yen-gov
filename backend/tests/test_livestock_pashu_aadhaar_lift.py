"""Tier-A contract tests for the livestock Pashu Aadhaar lift.

Asserts ``build_envelope(repo_root)`` returns ONE BatchEnvelope with:
    * target_family="livestock", target_table_stem="livestock_pashu_aadhaar"
    * Exactly 10 distinct facet-child indicator_ids
      (district-pashu-aadhaar-count-<species>)
    * Every row's source_id == "src-7e5d4aac4995" (ndlm_pashu_aadhaar)
    * Every period_label == "2024-25" (FY vintage only; matches the
      seeded source citation vintage. CY 2024 is preserved in raw
      `.runtime/raw/ndlm/2024/` for a follow-up PR but not lifted here
      because the inventory deriver rejects heterogeneous `time`
      vocabularies within one indicator.)
    * Every entity_id resolves to a district row in entities.parquet
    * The parent indicator district-pashu-aadhaar-count has ZERO rows
      (compute-on-read per Hans D33.8)

Uses REAL on-disk meadow shards under
``datasets/livestock/_meadow/ndlm/2024-25/`` - no mocks
(CLAUDE.md §10 Holy Law #7). Cheap (~1s); covers the adapter-build seam
end-to-end without invoking the writer.

Pattern source: ``test_energy_adapter_build.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.envelope import BatchEnvelope

REPO_ROOT = Path(__file__).resolve().parents[2]
MEADOW_DIR = REPO_ROOT / "datasets" / "livestock" / "_meadow" / "ndlm"

SPECIES_SLUGS = {
    "cattle", "buffalo", "yak", "mithun", "sheep",
    "goat", "pig", "horse", "donkey", "mule",
}
# Only the FY 2024-25 vintage is currently lifted (matches the seeded
# source citation vintage; the inventory deriver rejects mixed
# year + year_month shapes within one indicator).
VINTAGES = {"2024-25"}
MEADOW_VINTAGE_DIR = "2024-25"
PASHU_AADHAAR_SOURCE_ID = "src-7e5d4aac4995"


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_build_envelope_returns_one_with_correct_stem() -> None:
    from yen_gov.canonical.adapters.livestock import build_envelopes

    envelopes = build_envelopes(REPO_ROOT)
    assert len(envelopes) == 1

    env = envelopes[0]
    assert isinstance(env, BatchEnvelope)
    assert env.target_family == "livestock"
    assert env.target_table_stem == "livestock_pashu_aadhaar"
    assert env.observation_rows, "envelope emitted zero observation rows"


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_all_ten_species_facet_children_emit_rows() -> None:
    """The 10-species closed enum must each appear as a child
    indicator_id with >=1 observation row. A missing species = lift bug
    (either meadow shard absent or adapter loop dropped a species).
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    emitted_indicator_ids = {row.indicator_id for row in env.observation_rows}

    expected = {
        f"district-pashu-aadhaar-count-{slug}" for slug in SPECIES_SLUGS
    }
    assert emitted_indicator_ids == expected, (
        f"expected exactly the 10 species facet-children; got "
        f"{emitted_indicator_ids ^ expected!r} symmetric-difference"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_parent_indicator_has_no_observation_rows() -> None:
    """``district-pashu-aadhaar-count`` (the parent) is compute-on-read
    per Hans D33.8. Catching a row with the unsuffixed parent id here
    means the adapter accidentally lifted parent values - that breaks
    the compute-on-read contract (frontend would double-count parent +
    sum(children))."""
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    parent_rows = [
        r for r in env.observation_rows
        if r.indicator_id == "district-pashu-aadhaar-count"
    ]
    assert parent_rows == [], (
        f"parent indicator district-pashu-aadhaar-count must NOT emit "
        f"observation rows (compute-on-read per Hans D33.8); got "
        f"{len(parent_rows)} rows"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_all_rows_carry_pashu_aadhaar_source_id() -> None:
    """Every emitted row MUST FK to src-7e5d4aac4995. The writer's FK
    gate would catch this at write time; this test catches the
    regression at adapter-build time with a clearer message.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    bad = [
        r for r in env.observation_rows
        if r.source_id != PASHU_AADHAAR_SOURCE_ID
    ]
    assert not bad, (
        f"{len(bad)} rows do not carry src-7e5d4aac4995; first: "
        f"indicator_id={bad[0].indicator_id!r} source_id={bad[0].source_id!r}"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_period_labels_are_cy_or_fy_only() -> None:
    """Currently we lift only FY 2024-25 (matches the seeded source
    citation vintage). CY 2024 is preserved in raw but not lifted - the
    inventory deriver rejects heterogeneous `time` vocabularies within
    one indicator. Any other period_label = adapter parse_ndlm_period bug.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    labels = {r.period_label for r in env.observation_rows}
    assert labels == VINTAGES, (
        f"expected period_labels == {VINTAGES!r}; got {labels!r}"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_all_rows_derivation_raw() -> None:
    """Every Pashu Aadhaar row is a direct lift from the NDLM totals
    (no sum, no ratio). A non-raw derivation = an adapter regression
    that synthesised a row instead of lifting one.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    derivations = {r.derivation for r in env.observation_rows}
    assert derivations == {"raw"}, (
        f"expected all rows derivation='raw'; got {derivations!r}"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_district_entity_id_fk_closure() -> None:
    """Every observation row's entity_id MUST resolve to a district row
    in datasets/taxonomy/entities.json (the source of truth for
    entities.parquet). Citation: PR #267 grew the district roster to
    784 entities; this lift may not introduce orphans against that
    closure.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    entities_path = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"
    entity_ids = {
        e["entity_id"] for e in
        json.loads(entities_path.read_text(encoding="utf-8"))["entities"]
    }

    env = build_envelopes(REPO_ROOT)[0]
    orphans = sorted({
        r.entity_id for r in env.observation_rows
        if r.entity_id not in entity_ids
    })
    assert not orphans, (
        f"{len(orphans)} observation rows reference unknown entity_ids; "
        f"first 5: {orphans[:5]!r}. Run tools/livestock_meadow_pashu_aadhaar.py "
        f"to refresh, or expand the district roster (see "
        f"PR #267 boundary-coverage-expansion-plan)."
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_meadow_path_grammar_holds() -> None:
    """All 10 meadow shards MUST exist at the canonical path
    ``datasets/livestock/_meadow/ndlm/2024-25/`` (one per species).
    The "2024-25" vintage segment matches the seeded source citation
    (PR #276); rows for CY 2024 and FY 2024-25 are interleaved within
    each file with the period_label distinction carried on each row.

    A missing shard = the meadow generator left a gap that the
    adapter would silently skip.
    """
    expected = {
        f"district-pashu-aadhaar-count-{slug}.json"
        for slug in SPECIES_SLUGS
    }
    present = {p.name for p in (MEADOW_DIR / MEADOW_VINTAGE_DIR).glob("*.json")}
    missing = expected - present
    assert not missing, (
        f"missing {len(missing)} meadow shards under "
        f"_meadow/ndlm/{MEADOW_VINTAGE_DIR}/: {sorted(missing)!r}"
    )

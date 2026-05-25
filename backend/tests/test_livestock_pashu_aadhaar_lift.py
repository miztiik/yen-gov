"""Tier-A contract tests for the livestock Pashu Aadhaar lift.

Asserts ``build_envelope(repo_root)`` returns ONE BatchEnvelope with:
    * target_family="livestock", target_table_stem="livestock_pashu_aadhaar"
    * Exactly 20 distinct facet-child indicator_ids: 10 district-grain
      species (district-pashu-aadhaar-count-<species>) PLUS 10 state-grain
      auto-rollup siblings (state-pashu-aadhaar-count-<species>) per ADR-0043.
    * Every row's source_id == "src-7e5d4aac4995" (ndlm_pashu_aadhaar) -
      state-rollup rows REUSE the district citation row (per ADR-0032
      sources are citation ledger, NOT per-derivation events).
    * Every period_label == "2024-25" (FY vintage only; matches the
      seeded source citation vintage. CY 2024 is preserved in raw
      `.runtime/raw/ndlm/2024/` for a follow-up PR but not lifted here
      because the inventory deriver rejects heterogeneous `time`
      vocabularies within one indicator.)
    * Every district row's entity_id resolves to a district row in
      entities.parquet; every state-rollup row's entity_id resolves to
      a state-grain row.
    * The parent indicator district-pashu-aadhaar-count has ZERO rows
      (compute-on-read per Hans D33.8). Same for the new
      state-pashu-aadhaar-count parent.
    * State-rollup row values equal the SUM of their district children
      per (state, species, period) and carry derivation='sum'.

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
    """The 10-species closed enum must each appear at BOTH grains:
    district-grain (raw lift) AND state-grain (auto-rollup per ADR-0043).
    A missing species at either grain = lift bug (district = meadow gap
    or adapter species-loop drop; state = rollup pass dropped or skipped).
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    emitted_indicator_ids = {row.indicator_id for row in env.observation_rows}

    expected = {
        f"district-pashu-aadhaar-count-{slug}" for slug in SPECIES_SLUGS
    } | {
        f"state-pashu-aadhaar-count-{slug}" for slug in SPECIES_SLUGS
    }
    assert emitted_indicator_ids == expected, (
        f"expected the 10 district + 10 state-rollup species children; "
        f"got {emitted_indicator_ids ^ expected!r} symmetric-difference"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_parent_indicator_has_no_observation_rows() -> None:
    """Both parents are compute-on-read per Hans D33.8: the district-
    grain ``district-pashu-aadhaar-count`` AND the state-grain
    ``state-pashu-aadhaar-count`` (the latter introduced by ADR-0043).
    Catching a row with either unsuffixed parent id here means the
    adapter accidentally lifted parent values - that breaks the
    compute-on-read contract (frontend would double-count parent +
    sum(children))."""
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    parent_ids = {
        "district-pashu-aadhaar-count",
        "state-pashu-aadhaar-count",
    }
    parent_rows = [
        r for r in env.observation_rows if r.indicator_id in parent_ids
    ]
    assert parent_rows == [], (
        f"parent indicators {parent_ids!r} must NOT emit observation "
        f"rows (compute-on-read per Hans D33.8); got {len(parent_rows)} "
        f"rows; first: {parent_rows[0].indicator_id!r}"
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
def test_derivation_matches_grain() -> None:
    """District-grain rows are direct lifts (derivation='raw');
    state-grain rollup rows are auto-materialised SUMs of their district
    children (derivation='sum' per ADR-0043). Any other derivation =
    adapter regression.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    by_grain: dict[str, set[str]] = {}
    for r in env.observation_rows:
        grain = "district" if r.indicator_id.startswith("district-") else "state"
        by_grain.setdefault(grain, set()).add(r.derivation)
    assert by_grain == {"district": {"raw"}, "state": {"sum"}}, (
        f"expected district=raw + state=sum; got {by_grain!r}"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_entity_id_fk_closure_for_both_grains() -> None:
    """Every observation row's entity_id MUST resolve to an entities.json
    row, at the grain matching the indicator_id prefix:
    * district-* rows -> district-grain entity (kind=='district')
    * state-* rows -> state-grain entity (kind=='state' or 'union_territory')

    Citation: PR #267 grew the district roster to 784 entities. State
    entities have been in the catalogue since v0 of the project.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    entities_path = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"
    entities_by_id = {
        e["entity_id"]: e for e in
        json.loads(entities_path.read_text(encoding="utf-8"))["entities"]
    }

    env = build_envelopes(REPO_ROOT)[0]
    grain_mismatches: list[str] = []
    orphans: list[str] = []
    for r in env.observation_rows:
        ent = entities_by_id.get(r.entity_id)
        if ent is None:
            orphans.append(r.entity_id)
            continue
        entity_type = ent.get("entity_type")
        if r.indicator_id.startswith("district-") and entity_type != "district":
            grain_mismatches.append(
                f"{r.indicator_id} -> {r.entity_id} (entity_type={entity_type!r})"
            )
        elif r.indicator_id.startswith("state-") and entity_type not in (
            "state", "ut",
        ):
            grain_mismatches.append(
                f"{r.indicator_id} -> {r.entity_id} (entity_type={entity_type!r})"
            )
    assert not orphans, (
        f"{len(orphans)} observation rows reference unknown entity_ids; "
        f"first 5: {sorted(set(orphans))[:5]!r}."
    )
    assert not grain_mismatches, (
        f"{len(grain_mismatches)} rows reference entities at the wrong "
        f"grain; first 5: {grain_mismatches[:5]!r}"
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


# --- ADR-0043 auto-rollup invariants ---------------------------------------


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_state_rollup_sum_matches_district_sum_per_species() -> None:
    """Load-bearing ADR-0043 invariant: for every (state, species, period)
    the state-rollup value MUST equal the SUM of the district-grain
    children that share the same state-prefix. A mismatch = the rollup
    pass either (a) used a wrong derivation, (b) dropped a district row,
    (c) double-counted, or (d) state_prefix derivation broke.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes
    from yen_gov.canonical.adapters.livestock.pashu_aadhaar import _state_prefix

    env = build_envelopes(REPO_ROOT)[0]

    # Expected: sum district rows by (state_prefix, species, period_label)
    expected: dict[tuple[str, str, str], float] = {}
    for r in env.observation_rows:
        if not r.indicator_id.startswith("district-pashu-aadhaar-count-"):
            continue
        species = r.indicator_id.rsplit("-", 1)[-1]
        key = (_state_prefix(r.entity_id), species, r.period_label)
        expected[key] = expected.get(key, 0.0) + float(r.value_numeric)

    # Actual: state-rollup rows keyed by (entity_id, species, period_label)
    actual: dict[tuple[str, str, str], float] = {}
    for r in env.observation_rows:
        if not r.indicator_id.startswith("state-pashu-aadhaar-count-"):
            continue
        species = r.indicator_id.rsplit("-", 1)[-1]
        key = (r.entity_id, species, r.period_label)
        actual[key] = float(r.value_numeric)

    assert set(actual.keys()) == set(expected.keys()), (
        f"state-rollup key set != district sum key set; "
        f"missing-in-rollup={set(expected) - set(actual)!r}; "
        f"unexpected-in-rollup={set(actual) - set(expected)!r}"
    )
    mismatches = [
        (k, expected[k], actual[k])
        for k in expected
        if expected[k] != actual[k]
    ]
    assert not mismatches, (
        f"{len(mismatches)} state-rollup values do not equal sum of "
        f"district children; first 3: {mismatches[:3]!r}"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_state_rollup_reuses_district_source_id() -> None:
    """ADR-0032 invariant: state-rollup rows MUST reuse the district
    citation row (src-7e5d4aac4995). Sources are a citation ledger keyed
    on (producer, title, vintage), NOT per-derivation events. Minting a
    new source_id for the rollup = ledger duplication.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    bad = [
        r for r in env.observation_rows
        if r.indicator_id.startswith("state-pashu-aadhaar-count-")
        and r.source_id != PASHU_AADHAAR_SOURCE_ID
    ]
    assert not bad, (
        f"{len(bad)} state-rollup rows do not reuse {PASHU_AADHAAR_SOURCE_ID!r}; "
        f"first: indicator_id={bad[0].indicator_id!r} "
        f"source_id={bad[0].source_id!r}"
    )


@pytest.mark.skipif(
    not MEADOW_DIR.is_dir(),
    reason="livestock meadow shards not on disk in this checkout",
)
def test_state_rollup_inherits_period_axes() -> None:
    """State-rollup rows MUST carry the same period_label, year, and
    period_seq as their district children (a SUM does not invent a new
    time axis). If period_label differs, the rollup pass crossed a
    period boundary and corrupted the aggregate.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    env = build_envelopes(REPO_ROOT)[0]
    district_periods = {
        (r.period_label, r.year, r.period_seq)
        for r in env.observation_rows
        if r.indicator_id.startswith("district-pashu-aadhaar-count-")
    }
    rollup_periods = {
        (r.period_label, r.year, r.period_seq)
        for r in env.observation_rows
        if r.indicator_id.startswith("state-pashu-aadhaar-count-")
    }
    assert rollup_periods == district_periods, (
        f"state-rollup period axes drifted from district; "
        f"district-only={district_periods - rollup_periods!r}; "
        f"rollup-only={rollup_periods - district_periods!r}"
    )


def test_state_prefix_helper_raises_on_non_district_entity() -> None:
    """ADR-0043 helper invariant: _state_prefix MUST raise ValueError
    on a non-district entity_id. The helper is load-bearing: a silent
    pass-through on a malformed id would emit a malformed state-rollup
    row (entity_id == the original district id minus a non-existent
    suffix == itself).
    """
    from yen_gov.canonical.adapters.livestock.pashu_aadhaar import _state_prefix

    # Valid district shapes
    assert _state_prefix("IN-S01-D5") == "IN-S01"
    assert _state_prefix("IN-U08-D12") == "IN-U08"

    # Invalid: state-grain id, no -D segment
    with pytest.raises(ValueError, match="-D"):
        _state_prefix("IN-S01")
    with pytest.raises(ValueError, match="-D"):
        _state_prefix("IN-U08")

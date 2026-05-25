"""Tier-A contract tests for the livestock Owner Registration lift.

Asserts ``build_envelope(repo_root)`` returns a BatchEnvelope inside
``build_envelopes()`` (alongside the pashu_aadhaar envelope) with:

* target_family="livestock", target_table_stem="livestock_owner_registration"
* Exactly 12 distinct facet-child indicator_ids: 6 district-grain
  landholding brackets (district-livestock-owner-reg-count-<slug>)
  PLUS 6 state-grain auto-rollup siblings
  (state-livestock-owner-reg-count-<slug>) per ADR-0043.
* Every row's source_id == "src-d98dc531ef7e" (ndlm_owner_registration)
  - state-rollup rows REUSE the district citation row per ADR-0032.
* Every period_label == "2024-25" (FY vintage only; matches the
  seeded source citation vintage).
* Every district row's entity_id resolves to a district row in
  entities.json; every state-rollup row's entity_id resolves to a
  state or UT row.
* The parent indicators (district + state) have ZERO rows
  (compute-on-read per Hans D33.8).
* NO row's indicator_id contains the publisher facet separator ``|``
  (the gender axis was collapsed via SUM at first pass and must not
  leak into the indicator_id).
* State-rollup row values equal the SUM of their district children
  per (state, landholding, period); derivation == "sum" on BOTH grains
  (first pass = SUM-over-gender; second pass = SUM-over-districts).

Uses REAL on-disk meadow shard under
``datasets/livestock/_meadow/ndlm/2024-25/owner_reg_land_holding_district.json``
- no mocks (CLAUDE.md no.10 Holy Law no.7). Cheap (~1s); covers the
adapter-build seam end-to-end without invoking the writer.

Pattern source: ``test_livestock_pashu_aadhaar_lift.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.envelope import BatchEnvelope

REPO_ROOT = Path(__file__).resolve().parents[2]
MEADOW_DIR = REPO_ROOT / "datasets" / "livestock" / "_meadow" / "ndlm"
OWNER_REG_MEADOW = (
    MEADOW_DIR / "2024-25" / "owner_reg_land_holding_district.json"
)

LANDHOLDING_SLUGS = {
    "landless-marginal", "small", "semi-medium",
    "medium", "large", "not-specified",
}
VINTAGES = {"2024-25"}
OWNER_REG_SOURCE_ID = "src-d98dc531ef7e"


def _owner_reg_envelope():
    """Pick the owner_reg envelope from the livestock package output.

    ``build_envelopes`` returns multiple envelopes; this helper isolates
    the owner_reg one so the tests are robust to ordering changes.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    envelopes = build_envelopes(REPO_ROOT)
    matching = [
        e for e in envelopes
        if e.target_table_stem == "livestock_owner_registration"
    ]
    assert len(matching) == 1, (
        f"expected exactly one livestock_owner_registration envelope; "
        f"got {len(matching)} (out of {len(envelopes)} total)"
    )
    return matching[0]


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_build_envelope_returns_correct_stem() -> None:
    env = _owner_reg_envelope()
    assert isinstance(env, BatchEnvelope)
    assert env.target_family == "livestock"
    assert env.target_table_stem == "livestock_owner_registration"
    assert env.observation_rows, "envelope emitted zero observation rows"


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_all_six_landholding_facet_children_emit_rows() -> None:
    """The 6-bracket closed enum must each appear at BOTH grains:
    district-grain (first-pass SUM-over-gender) AND state-grain
    (second-pass SUM-over-districts per ADR-0043). A missing slug at
    either grain = lift bug (district = meadow gap or adapter loop drop;
    state = rollup pass dropped or skipped).
    """
    env = _owner_reg_envelope()
    emitted_indicator_ids = {row.indicator_id for row in env.observation_rows}

    expected = {
        f"district-livestock-owner-reg-count-{slug}" for slug in LANDHOLDING_SLUGS
    } | {
        f"state-livestock-owner-reg-count-{slug}" for slug in LANDHOLDING_SLUGS
    }
    assert emitted_indicator_ids == expected, (
        f"expected the 6 district + 6 state-rollup landholding "
        f"children; got {emitted_indicator_ids ^ expected!r} "
        f"symmetric-difference"
    )


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_parent_indicators_have_no_observation_rows() -> None:
    """Both parents are compute-on-read per Hans D33.8: the district-
    grain ``district-livestock-owner-reg-count`` AND the state-grain
    ``state-livestock-owner-reg-count``. Catching a row with either
    unsuffixed parent id here means the adapter accidentally lifted
    parent values - that breaks the compute-on-read contract (frontend
    would double-count parent + sum(children)).
    """
    env = _owner_reg_envelope()
    parent_ids = {
        "district-livestock-owner-reg-count",
        "state-livestock-owner-reg-count",
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
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_all_rows_carry_owner_reg_source_id() -> None:
    """Every emitted row MUST FK to src-d98dc531ef7e. The writer's FK
    gate would catch this at write time; this test catches the
    regression at adapter-build time with a clearer message.
    """
    env = _owner_reg_envelope()
    bad = [
        r for r in env.observation_rows
        if r.source_id != OWNER_REG_SOURCE_ID
    ]
    assert not bad, (
        f"{len(bad)} rows do not carry {OWNER_REG_SOURCE_ID!r}; first: "
        f"indicator_id={bad[0].indicator_id!r} source_id={bad[0].source_id!r}"
    )


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_period_labels_are_fy_2024_25_only() -> None:
    """Currently we lift only FY 2024-25 (the only vintage in the
    meadow shard). A different period_label = adapter parse_ndlm_period
    bug.
    """
    env = _owner_reg_envelope()
    labels = {r.period_label for r in env.observation_rows}
    assert labels == VINTAGES, (
        f"expected period_labels == {VINTAGES!r}; got {labels!r}"
    )


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_landholding_axes_are_split_kebab_no_pipe() -> None:
    """The publisher cell's facet shape is ``<landholding>|<gender>``;
    the first-pass collapse via SUM strips the gender component AND
    translates the snake_case landholding value_id to kebab-case for
    the indicator_id suffix. NO emitted indicator_id may contain the
    ``|`` separator (would mean the facet split + slug translation
    failed silently) or an underscore in the suffix (would mean the
    snake_case-to-kebab map was bypassed).
    """
    env = _owner_reg_envelope()
    for r in env.observation_rows:
        assert "|" not in r.indicator_id, (
            f"indicator_id {r.indicator_id!r} contains publisher facet "
            f"separator '|'; facet split missed in adapter."
        )
        # Suffix after the "count-" anchor must use kebab (no underscores).
        # The "count-" anchor itself is in the stem and is guaranteed
        # safe; the suffix is the translated landholding slug.
        suffix = r.indicator_id.split("count-", 1)[-1]
        assert "_" not in suffix, (
            f"indicator_id suffix {suffix!r} contains '_' (the "
            f"snake_case-to-kebab translation in LANDHOLDING_TO_SLUG "
            f"was bypassed); full id: {r.indicator_id!r}."
        )


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_derivation_is_sum_on_both_grains() -> None:
    """District-grain rows are SUM-over-gender lifts (derivation='sum'
    because the gender axis collapse is itself a SUM); state-grain
    rollup rows are SUM-over-district rows (derivation='sum' per
    ADR-0043). Both grains carry the SAME derivation; this differs
    from pashu_aadhaar (district='raw' there because there's no
    within-cell SUM).
    """
    env = _owner_reg_envelope()
    by_grain: dict[str, set[str]] = {}
    for r in env.observation_rows:
        grain = "district" if r.indicator_id.startswith("district-") else "state"
        by_grain.setdefault(grain, set()).add(r.derivation)
    assert by_grain == {"district": {"sum"}, "state": {"sum"}}, (
        f"expected district=sum + state=sum; got {by_grain!r}"
    )


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_entity_id_fk_closure_for_both_grains() -> None:
    """Every observation row's entity_id MUST resolve to an entities.json
    row, at the grain matching the indicator_id prefix:
    * district-* rows -> district-grain entity (entity_type=='district')
    * state-* rows -> state-grain entity (entity_type in {'state', 'ut'}).
    """
    entities_path = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"
    entities_by_id = {
        e["entity_id"]: e for e in
        json.loads(entities_path.read_text(encoding="utf-8"))["entities"]
    }

    env = _owner_reg_envelope()
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


# --- ADR-0043 auto-rollup invariants ---------------------------------------


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_state_rollup_sum_matches_district_sum_per_landholding() -> None:
    """Load-bearing ADR-0043 invariant: for every (state, landholding,
    period) the state-rollup value MUST equal the SUM of the
    district-grain children that share the same state-prefix. A
    mismatch = the rollup pass either (a) used a wrong derivation,
    (b) dropped a district row, (c) double-counted, or (d) state_prefix
    derivation broke.
    """
    from yen_gov.canonical.adapters.livestock.owner_reg import _state_prefix

    env = _owner_reg_envelope()

    # Expected: sum district rows by (state_prefix, landholding_slug, period_label)
    expected: dict[tuple[str, str, str], float] = {}
    for r in env.observation_rows:
        if not r.indicator_id.startswith("district-livestock-owner-reg-count-"):
            continue
        slug = r.indicator_id.split("count-", 1)[-1]
        key = (_state_prefix(r.entity_id), slug, r.period_label)
        expected[key] = expected.get(key, 0.0) + float(r.value_numeric)

    # Actual: state-rollup rows keyed by (entity_id, slug, period_label)
    actual: dict[tuple[str, str, str], float] = {}
    for r in env.observation_rows:
        if not r.indicator_id.startswith("state-livestock-owner-reg-count-"):
            continue
        slug = r.indicator_id.split("count-", 1)[-1]
        key = (r.entity_id, slug, r.period_label)
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
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_state_rollup_inherits_period_axes() -> None:
    """State-rollup rows MUST carry the same period_label, year, and
    period_seq as their district children (a SUM does not invent a
    new time axis). If period_label differs, the rollup pass crossed
    a period boundary and corrupted the aggregate.
    """
    env = _owner_reg_envelope()
    district_periods = {
        (r.period_label, r.year, r.period_seq)
        for r in env.observation_rows
        if r.indicator_id.startswith("district-livestock-owner-reg-count-")
    }
    rollup_periods = {
        (r.period_label, r.year, r.period_seq)
        for r in env.observation_rows
        if r.indicator_id.startswith("state-livestock-owner-reg-count-")
    }
    assert rollup_periods == district_periods, (
        f"state-rollup period axes drifted from district; "
        f"district-only={district_periods - rollup_periods!r}; "
        f"rollup-only={rollup_periods - district_periods!r}"
    )


def test_state_prefix_helper_raises_on_non_district_entity() -> None:
    """ADR-0043 helper invariant: ``owner_reg._state_prefix`` MUST raise
    ValueError on a non-district entity_id. The helper is load-bearing:
    a silent pass-through on a malformed id would emit a malformed
    state-rollup row.

    This mirrors the pashu_aadhaar helper test; the duplication is
    intentional (Fowler "rule of three" - the third copy in NAIP IV
    triggers extraction to backend/yen_gov/canonical/rollup.py).
    """
    from yen_gov.canonical.adapters.livestock.owner_reg import _state_prefix

    # Valid district shapes
    assert _state_prefix("IN-S01-D5") == "IN-S01"
    assert _state_prefix("IN-U08-D12") == "IN-U08"

    # Invalid: state-grain id, no -D segment
    with pytest.raises(ValueError, match="-D"):
        _state_prefix("IN-S01")
    with pytest.raises(ValueError, match="-D"):
        _state_prefix("IN-U08")


@pytest.mark.skipif(
    not OWNER_REG_MEADOW.is_file(),
    reason="owner_reg meadow shard not on disk in this checkout",
)
def test_adapter_rejects_unknown_landholding_bracket(tmp_path: Path) -> None:
    """The adapter's defensive check on unknown landholding brackets
    MUST raise ValueError naming the bracket. A silent pass-through
    would emit a row with an indicator_id that fails the writer's FK
    gate downstream with a less actionable error.

    Construct a tmp_path with a minimal meadow shard carrying an
    unknown bracket, plus a minimal entities.json so other code paths
    don't trip first.
    """
    from yen_gov.canonical.adapters.livestock.owner_reg import build_envelope

    # Minimal shard with one bogus bracket
    meadow_dir = tmp_path / "datasets" / "livestock" / "_meadow" / "ndlm" / "2024-25"
    meadow_dir.mkdir(parents=True)
    (meadow_dir / "owner_reg_land_holding_district.json").write_text(
        json.dumps({
            "rows": [
                {
                    "entity_id": "IN-S01-D502",
                    "facet": "ultra_large|male",  # not in LANDHOLDING_BRACKETS
                    "time": "2024-25",
                    "value": 1,
                }
            ]
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ultra_large"):
        build_envelope(tmp_path)

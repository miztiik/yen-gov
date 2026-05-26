"""Tier-A contract tests for the livestock NAIP IV lift.

Asserts ``build_envelope(repo_root)`` returns a BatchEnvelope inside
``build_envelopes()`` (alongside pashu_aadhaar + owner_reg envelopes)
with:

* target_family="livestock", target_table_stem="livestock_naip_iv"
* Exactly 8 distinct indicator_ids: 4 district-grain metric families
  (district-livestock-naip-iv-<slug>) PLUS 4 state-grain auto-rollup
  siblings (state-livestock-naip-iv-<slug>) per ADR-0043.
* Every row's source_id == "src-93a2a72db482" (ndlm_naip_iv) - state
  rollup rows REUSE the district citation row per ADR-0032.
* Every period_label == "2024-25" (FY vintage only; matches the
  seeded source citation vintage at slice-1 cut date).
* Every district row's entity_id resolves to a district row in
  entities.json; every state-rollup row's entity_id resolves to a
  state or UT row.
* NO row's indicator_id contains the publisher facet separator ``|``
  (the sex axis was collapsed via SUM at first pass and must not
  leak into the indicator_id).
* State-rollup row values equal the SUM of their district children
  per (state, metric, period); derivation == "sum" on BOTH grains
  (first pass = SUM-over-sex for calves_born + identity for the other
  three metric families; second pass = SUM-over-districts).
* No parent indicators exist for this lift (units differ across the
  4 metric families - events / events / calves / farmers - so a
  compute-on-read parent would be a category mistake).

Uses REAL on-disk meadow shard under
``datasets/livestock/_meadow/ndlm/2024-25/naip_iv_district.json``
- no mocks (CLAUDE.md no.10 Holy Law no.7). Cheap (~1s); covers the
adapter-build seam end-to-end without invoking the writer.

Pattern source: ``test_livestock_owner_reg_lift.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.envelope import BatchEnvelope

REPO_ROOT = Path(__file__).resolve().parents[2]
MEADOW_DIR = REPO_ROOT / "datasets" / "livestock" / "_meadow" / "ndlm"
NAIP_IV_MEADOW = MEADOW_DIR / "2024-25" / "naip_iv_district.json"

METRIC_SLUGS = {
    "inseminations",
    "pregnancy-diagnoses",
    "calves-born",
    "farmers-benefitted",
}
# The 2026-05-26 NDLM operator snapshot exposes the FY 2010-11..2025-26
# raw vintages, but NAIP IV (rolled out ~2023) only has non-zero rows in
# the last 3 FY vintages. Older vintages are still fetched at lift time
# (no data leakage) but produce no observation rows - so the lifted set
# is {2023-24, 2024-25, 2025-26}. CY vintages are preserved in raw but
# not lifted (inventory deriver rejects mixed CY+FY period shapes within
# one indicator).
VINTAGES = {"2023-24", "2024-25", "2025-26"}
NAIP_IV_SOURCE_ID = "src-93a2a72db482"


def _naip_iv_envelope():
    """Pick the naip_iv envelope from the livestock package output.

    ``build_envelopes`` returns multiple envelopes; this helper isolates
    the naip_iv one so the tests are robust to ordering changes.
    """
    from yen_gov.canonical.adapters.livestock import build_envelopes

    envelopes = build_envelopes(REPO_ROOT)
    matching = [
        e for e in envelopes
        if e.target_table_stem == "livestock_naip_iv"
    ]
    assert len(matching) == 1, (
        f"expected exactly one livestock_naip_iv envelope; "
        f"got {len(matching)} (out of {len(envelopes)} total)"
    )
    return matching[0]


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_build_envelope_returns_correct_stem() -> None:
    env = _naip_iv_envelope()
    assert isinstance(env, BatchEnvelope)
    assert env.target_family == "livestock"
    assert env.target_table_stem == "livestock_naip_iv"
    assert env.observation_rows, "envelope emitted zero observation rows"


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_all_four_metric_children_emit_rows_at_both_grains() -> None:
    """The 4-metric closed set must each appear at BOTH grains:
    district-grain (first-pass SUM-over-sex for calves_born, identity
    for the other three) AND state-grain (second-pass SUM-over-
    districts per ADR-0043). A missing slug at either grain = lift bug.
    """
    env = _naip_iv_envelope()
    emitted_indicator_ids = {row.indicator_id for row in env.observation_rows}

    expected = {
        f"district-livestock-naip-iv-{slug}" for slug in METRIC_SLUGS
    } | {
        f"state-livestock-naip-iv-{slug}" for slug in METRIC_SLUGS
    }
    assert emitted_indicator_ids == expected, (
        f"expected the 4 district + 4 state-rollup metric children; "
        f"got {emitted_indicator_ids ^ expected!r} symmetric-difference"
    )


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_no_parent_indicators_emitted() -> None:
    """Unlike pashu_aadhaar + owner_reg which have compute-on-read
    parents, NAIP IV has NO parent. Units differ across the 4 metric
    families (events / events / calves / farmers) so a parent total
    would be a category mistake. Catching any row with the bare
    ``district-livestock-naip-iv`` / ``state-livestock-naip-iv`` id =
    adapter regression.
    """
    env = _naip_iv_envelope()
    bad_ids = {
        "district-livestock-naip-iv",
        "state-livestock-naip-iv",
    }
    bad_rows = [r for r in env.observation_rows if r.indicator_id in bad_ids]
    assert bad_rows == [], (
        f"NAIP IV must NOT emit parent rows (units differ across metric "
        f"families); got {len(bad_rows)} rows; first: "
        f"{bad_rows[0].indicator_id!r}"
    )


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_all_rows_carry_naip_iv_source_id() -> None:
    """Every emitted row MUST FK to src-93a2a72db482. The writer's FK
    gate would catch this at write time; this test catches the
    regression at adapter-build time with a clearer message.
    """
    env = _naip_iv_envelope()
    bad = [
        r for r in env.observation_rows
        if r.source_id != NAIP_IV_SOURCE_ID
    ]
    assert not bad, (
        f"{len(bad)} rows do not carry {NAIP_IV_SOURCE_ID!r}; first: "
        f"indicator_id={bad[0].indicator_id!r} source_id={bad[0].source_id!r}"
    )


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_period_labels_are_naip_iv_active_vintages_only() -> None:
    """NAIP IV rolled out ~2023; the lift emits rows only for the FY
    vintages where the registry had non-zero rows (2023-24, 2024-25,
    2025-26). Older vintages are still fetched at lift time (no data
    leakage) but produce no observation rows. A period_label outside
    this set = adapter parse_ndlm_period bug. CY vintages are
    deliberately not lifted (inventory deriver rejects mixed period
    shapes).
    """
    env = _naip_iv_envelope()
    labels = {r.period_label for r in env.observation_rows}
    assert labels == VINTAGES, (
        f"expected period_labels == {VINTAGES!r}; got {labels!r}"
    )


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_metric_slugs_are_kebab_no_pipe_no_underscore() -> None:
    """The publisher cell's facet shape is ``<metric_family>|<sex>``;
    the first-pass collapse via SUM strips the sex component AND
    translates the snake_case metric_family value to kebab-case for
    the indicator_id suffix. NO emitted indicator_id may contain the
    ``|`` separator (would mean the facet split failed silently) or
    an underscore in the suffix (would mean the snake_case-to-kebab
    map was bypassed).
    """
    env = _naip_iv_envelope()
    for r in env.observation_rows:
        assert "|" not in r.indicator_id, (
            f"indicator_id {r.indicator_id!r} contains publisher facet "
            f"separator '|'; facet split missed in adapter."
        )
        suffix = r.indicator_id.split("naip-iv-", 1)[-1]
        assert "_" not in suffix, (
            f"indicator_id suffix {suffix!r} contains '_' (the "
            f"snake_case-to-kebab translation in METRIC_TO_SLUG was "
            f"bypassed); full id: {r.indicator_id!r}."
        )


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_derivation_is_sum_on_both_grains() -> None:
    """District-grain rows are SUM-over-sex lifts for calves_born and
    SUM-over-singleton-sex for the other three metric families
    (derivation='sum' uniformly because the first pass groups by
    (entity_id, metric_family, period_label) which is a SUM even when
    the input has only one sex value). State-grain rollup rows are
    SUM-over-district rows (derivation='sum' per ADR-0043).
    """
    env = _naip_iv_envelope()
    by_grain: dict[str, set[str]] = {}
    for r in env.observation_rows:
        grain = "district" if r.indicator_id.startswith("district-") else "state"
        by_grain.setdefault(grain, set()).add(r.derivation)
    assert by_grain == {"district": {"sum"}, "state": {"sum"}}, (
        f"expected district=sum + state=sum; got {by_grain!r}"
    )


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_entity_id_fk_closure_for_both_grains() -> None:
    """Every observation row's entity_id MUST resolve to an
    entities.json row, at the grain matching the indicator_id prefix:
    * district-* rows -> district-grain entity (entity_type=='district')
    * state-* rows -> state-grain entity (entity_type in {'state', 'ut'}).
    """
    entities_path = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"
    entities_by_id = {
        e["entity_id"]: e for e in
        json.loads(entities_path.read_text(encoding="utf-8"))["entities"]
    }

    env = _naip_iv_envelope()
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
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_state_rollup_sum_matches_district_sum_per_metric() -> None:
    """Load-bearing ADR-0043 invariant: for every (state, metric,
    period) the state-rollup value MUST equal the SUM of the
    district-grain children that share the same state-prefix. A
    mismatch = the rollup pass either (a) used a wrong derivation,
    (b) dropped a district row, (c) double-counted, or (d) state_prefix
    derivation broke.
    """
    from yen_gov.canonical.adapters.livestock._shared import state_prefix

    env = _naip_iv_envelope()

    # Expected: sum district rows by (state_prefix, metric_slug, period_label)
    expected: dict[tuple[str, str, str], float] = {}
    for r in env.observation_rows:
        if not r.indicator_id.startswith("district-livestock-naip-iv-"):
            continue
        slug = r.indicator_id.split("naip-iv-", 1)[-1]
        key = (state_prefix(r.entity_id), slug, r.period_label)
        expected[key] = expected.get(key, 0.0) + float(r.value_numeric)

    # Actual: state-rollup rows keyed by (entity_id, slug, period_label)
    actual: dict[tuple[str, str, str], float] = {}
    for r in env.observation_rows:
        if not r.indicator_id.startswith("state-livestock-naip-iv-"):
            continue
        slug = r.indicator_id.split("naip-iv-", 1)[-1]
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
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_state_rollup_inherits_period_axes() -> None:
    """State-rollup rows MUST carry the same period_label, year, and
    period_seq as their district children (a SUM does not invent a
    new time axis).
    """
    env = _naip_iv_envelope()
    district_periods = {
        (r.period_label, r.year, r.period_seq)
        for r in env.observation_rows
        if r.indicator_id.startswith("district-livestock-naip-iv-")
    }
    rollup_periods = {
        (r.period_label, r.year, r.period_seq)
        for r in env.observation_rows
        if r.indicator_id.startswith("state-livestock-naip-iv-")
    }
    assert rollup_periods == district_periods, (
        f"state-rollup period axes drifted from district; "
        f"district-only={district_periods - rollup_periods!r}; "
        f"rollup-only={rollup_periods - district_periods!r}"
    )


@pytest.mark.skipif(
    not NAIP_IV_MEADOW.is_file(),
    reason="naip_iv meadow shard not on disk in this checkout",
)
def test_calves_born_district_value_equals_meadow_male_plus_female_sum() -> None:
    """Hans honest-renderer invariant: for every (district, period)
    cell that has BOTH calves_born|m and calves_born|f meadow rows,
    the lifted ``district-livestock-naip-iv-calves-born`` value MUST
    equal the sum of the two meadow values. This is the load-bearing
    sex-collapse correctness check.

    Keyed by ``(entity_id, period_label)`` because the meadow now
    carries 16 FY vintages; collapsing across vintages would mask
    per-vintage SUM bugs behind a totals-equal-totals false-positive.
    """
    meadow = json.loads(NAIP_IV_MEADOW.read_text(encoding="utf-8"))
    # Expected: sum male + female per (district, period) from meadow
    expected: dict[tuple[str, str], float] = {}
    for r in meadow["rows"]:
        family, _sex = r["facet"].split("|", 1)
        if family != "calves_born":
            continue
        key = (r["entity_id"], r["time"])
        expected[key] = expected.get(key, 0.0) + float(r["value"])

    env = _naip_iv_envelope()
    actual: dict[tuple[str, str], float] = {
        (r.entity_id, r.period_label): float(r.value_numeric)
        for r in env.observation_rows
        if r.indicator_id == "district-livestock-naip-iv-calves-born"
    }
    assert set(actual.keys()) == set(expected.keys()), (
        f"(district, period) set mismatch: "
        f"missing={set(expected) - set(actual)!r}; "
        f"extra={set(actual) - set(expected)!r}"
    )
    mismatches = [
        (k, expected[k], actual[k]) for k in expected
        if expected[k] != actual[k]
    ]
    assert not mismatches, (
        f"{len(mismatches)} (district, period) cells have calves_born value != "
        f"meadow male+female sum; first 3: {mismatches[:3]!r}"
    )


def test_adapter_rejects_unknown_metric_family(tmp_path: Path) -> None:
    """The adapter's defensive check on unknown metric_family MUST
    raise ValueError. The check is load-bearing because an unknown
    family slipping through would generate a malformed indicator_id
    (e.g. ``district-livestock-naip-iv-...``) that fails FK closure
    at the writer.
    """
    # Write a minimal fake meadow with a bogus metric_family
    fake_meadow_dir = tmp_path / "datasets" / "livestock" / "_meadow" / "ndlm" / "2024-25"
    fake_meadow_dir.mkdir(parents=True, exist_ok=True)
    fake_shard = fake_meadow_dir / "naip_iv_district.json"
    fake_shard.write_text(
        json.dumps({
            "rows": [
                {
                    "entity_id": "IN-S01-D5",
                    "time": "2024-25",
                    "facet": "bogus_metric|none",
                    "value": 42.0,
                }
            ]
        }),
        encoding="utf-8",
    )

    from yen_gov.canonical.adapters.livestock.naip_iv import build_envelope

    with pytest.raises(ValueError, match="Unknown NAIP IV metric_family"):
        build_envelope(tmp_path)

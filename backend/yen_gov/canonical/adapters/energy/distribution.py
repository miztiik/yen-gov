"""Distribution-performance envelope — ``energy_distribution_performance.parquet``.

P.1.A (2 indicators) + P.1.B (8 indicators: 4 efficiency + 1 ACS-ARR
+ 3 RPO compliance segments + 1 parent each for efficiency and RPO)
= 10 lifted observation-emitting indicators.

P.1.A — Lifts 2 legacy shards (DISCOM ledger surface):

* ``state_atc_losses_pct.json`` (344 rows)
  → ``state-atc-losses-pct``.
* ``state_electricity_sales_mu.json`` (356 rows)
  → ``state-electricity-sales-mu``.

ATC = Aggregate Technical + Commercial losses, the flagship DISCOM health
indicator (UDAY target was <15% by FY19). Sales-MU is the volume of
energy DISCOMs billed end-consumers for; pairs with the ATC% to triangulate
revenue leakage.

P.1.B — Lifts 5 additional legacy shards (DISCOM finance + RPO):

* ``state_distribution_billing_efficiency_pct.json`` →
  ``distribution-efficiency-pct-billing`` (efficiency_dimension =
  billing).
* ``state_distribution_collection_efficiency_pct.json`` →
  ``distribution-efficiency-pct-collection`` (efficiency_dimension =
  collection).
* ``state_distribution_td_loss_pct.json`` →
  ``distribution-efficiency-pct-td-loss`` (efficiency_dimension =
  td_loss).
* ``state_acs_arr_gap_inr_per_kwh.json`` →
  ``state-acs-arr-gap-inr-per-kwh`` (standalone; ICED Deep Dive source).
* ``state_rpo_compliance_pct.json`` (natively 3-faceted on
  ``solar`` / ``non-solar`` / ``total``) → 3 child indicator_ids of
  ``rpo-compliance-pct`` (rpo_segment = solar / non_solar / total).

The two efficiency-percentage families (billing × collection) decompose
the commercial half of AT&C losses; ``td-loss`` is the technical half.
ACS-ARR is the per-unit revenue gap. RPO compliance is the renewable-
procurement obligation tracker. All five use ICED-published methodology
(`distribution-dashboard` for the three efficiency dimensions and RPO;
``deep-dive`` for ACS-ARR).
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import SOURCE_IDS, load_meadow, parse_iso_period, to_entity_id


# All 7 distribution-performance shards are ICED-sourced with the same
# meadow vintage (2024-25). Single helper centralises the path tuple.
_ICED_2024_25 = ("energy", "iced", "2024-25")


def _load_distribution_meadow(repo_root: Path, file: str) -> dict:
    return load_meadow(repo_root, *_ICED_2024_25, file)


# Map the RPO shard's `facet` field (legacy hyphenated form on the wire)
# to the canonical child indicator_id suffix AND the rpo_segment value_id
# (snake_case per facet-axes value_id regex). The tuple-of-tuples form is
# explicit and order-stable; iterating maps avoids dict-ordering churn in
# the emitted parquet's row order.
_RPO_FACET_DISPATCH: tuple[tuple[str, str, str], ...] = (
    # (legacy_facet, indicator_id_suffix, rpo_segment_value_id)
    ("solar",     "solar",     "solar"),
    ("non-solar", "non-solar", "non_solar"),
    ("total",     "total",     "total"),
)


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    # 1. state_atc_losses_pct.json → state-atc-losses-pct
    shard = _load_distribution_meadow(repo_root, "state_atc_losses_pct.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-atc-losses-pct",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    # 2. state_electricity_sales_mu.json → state-electricity-sales-mu
    shard = _load_distribution_meadow(repo_root, "state_electricity_sales_mu.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-electricity-sales-mu",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    # 3. P.1.B — Distribution efficiency triple (billing / collection /
    #    td-loss). Three shards collapse into three CHILD indicator_ids of
    #    ``distribution-efficiency-pct`` (compute-on-read parent
    #    holds no rows; per Hans D29 child rows carry source_id +
    #    dimension_values, parent does not).
    _EFFICIENCY_DISPATCH: tuple[tuple[str, str], ...] = (
        ("state_distribution_billing_efficiency_pct.json",    "distribution-efficiency-pct-billing"),
        ("state_distribution_collection_efficiency_pct.json", "distribution-efficiency-pct-collection"),
        ("state_distribution_td_loss_pct.json",               "distribution-efficiency-pct-td-loss"),
    )
    for shard_name, indicator_id in _EFFICIENCY_DISPATCH:
        shard = _load_distribution_meadow(repo_root, shard_name)
        for r in shard["rows"]:
            period_label, year, period_seq = parse_iso_period(r["time"])
            rows.append(ObservationRow(
                entity_id=to_entity_id(r["entity_id"]),
                year=year,
                period_label=period_label,
                period_seq=period_seq,
                indicator_id=indicator_id,
                value_numeric=float(r["value"]),
                source_id=SOURCE_IDS["iced_distribution_perf"],
                derivation="raw",
            ))

    # 4. P.1.B — ACS-ARR gap (per-unit revenue gap, ICED deep-dive
    #    source). Standalone indicator; same `iced_deep_dive` source the
    #    P.1.A AT&C losses + sales-MU rows use.
    shard = _load_distribution_meadow(repo_root, "state_acs_arr_gap_inr_per_kwh.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-acs-arr-gap-inr-per-kwh",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    # 5. P.1.B — RPO compliance (natively 3-facet shard). Dispatches each
    #    shard row to ONE of the three child indicator_ids by the row's
    #    `facet` field. Unknown facet values are a SHARD bug — fail fast
    #    rather than silently drop.
    shard = _load_distribution_meadow(repo_root, "state_rpo_compliance_pct.json")
    legacy_to_indicator: dict[str, str] = {
        legacy: f"rpo-compliance-pct-{suffix}"
        for legacy, suffix, _value_id in _RPO_FACET_DISPATCH
    }
    for r in shard["rows"]:
        legacy_facet = r.get("facet")
        if legacy_facet not in legacy_to_indicator:
            raise ValueError(
                f"state_rpo_compliance_pct.json carried unexpected facet "
                f"{legacy_facet!r}; expected one of {set(legacy_to_indicator)}"
            )
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=legacy_to_indicator[legacy_facet],
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_distribution_rpo"],
            derivation="raw",
        ))

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_distribution_performance",
        observation_rows=rows,
    )

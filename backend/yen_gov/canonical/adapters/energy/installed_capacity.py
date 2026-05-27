"""Installed capacity envelope --- ``energy_installed_capacity.parquet``.

Lifts 10 legacy shards into a single BatchEnvelope:

* 5 CEA per-fuel per-state shards
  (``installed_capacity_{coal,gas,hydro,nuclear,renewable}_mw.json``)
  → ``installed-capacity-mw-{fuel}`` (5 IN rows, derivation=sum)
  AND ``installed-capacity-snapshot-mw-{fuel}`` (35 per-state rows
  per fuel, derivation=raw) — added P.1.A C4.5 to surface CEA's monthly
  per-state per-fuel allocation snapshot. The snapshot family is
  comparable_across_states_snapshot_only (NOT a time series).
* ``state_installed_capacity_geographical_mw.json`` (407 rows)
  → ``installed-capacity-geographical-mw`` (parent, publisher total).
* ``state_installed_capacity_by_source_mw.json`` (~1815 rows)
  → ``installed-capacity-geographical-mw-{fuel}`` (after sub-fuel
  collapse to canonical 5).
* ``state_installed_capacity_with_alloc_mw.json`` (396 rows)
  → ``installed-capacity-allocated-mw`` (parent, publisher total,
  FY15-FY25, source_id=iced_deep_dive).
* ``state_installed_capacity_total_mw.json`` (374 pre-FY15 rows)
  → ``installed-capacity-allocated-mw`` (parent, RBI Handbook
  Table 140 long-arc splice, FY05-FY14, source_id=rbi_hbk_140_installed_capacity).
  Added P.1.A C4.6 per plan-doc 20260522 §3 Q-c verdict (Option 1 SPLICE).
  Pre-FY15 rows have no fuel_type field in the ObservationRow (the
  schema has no such field; fuel granularity is encoded in indicator_id,
  and the parent ``installed-capacity-allocated-mw`` is the
  publisher-total indicator that carries both ICED post-FY15 and RBI
  pre-FY15 rows). methodology_break row
  ``rbi-handbook-aggregate-no-fuel-split-pre-fy15`` documents the basis
  change at FY15 and the absence of per-fuel splits in the RBI portion.
* ``state_rooftop_solar_capacity_mw.json`` (321 rows, P.1.C PR-R)
  → ``state-rooftop-solar-capacity-mw`` (per-state cumulative rooftop
  PV MW, FY18-FY25, source_id=iced_rooftop_solar). Complements (does
  NOT replace) utility-scale solar tracked under
  ``installed-capacity-snapshot-mw-renewable``; the total state
  solar fleet = utility-scale + rooftop.
* ``india_thermal_capacity_retired_mw.json`` (29 rows, P.1.C PR-S)
  → ``india-thermal-capacity-retired-mw-{fuel}`` (FY05-FY25, national
  only, 2-facet coal/gas after SUB_FUEL_TO_CANONICAL collapse of
  publisher "oil-gas" → canonical "gas";
  source_id=iced_thermal_retired). First Pattern A-facet indicator in
  P.1.C cohort. National-only — ICED does NOT publish state-level
  retired capacity; captures only utility-scale thermal retirements.

DELIBERATELY NOT LIFTED:
* ``installed_capacity_{thermal,total}_mw.json`` — D33.8 hard drop, the
  catalogue does NOT define a ``-total-mw`` / ``-thermal-mw`` indicator.
  Totals compute on-read from per-fuel children.
* ``installed_mw_by_state.json`` — superseded by per-fuel CEA shards;
  HARD DROP per plan-doc TODO row 0e.7 P.1.A scope list. (The legacy
  facetted composite ``installed_capacity_by_source_mw.json`` was
  retired in PR 7b alongside the composer that produced it; see
  ADR-0024 "Superseded" note.)
* ``installed-capacity-allocated-mw-{fuel}`` children — the per-fuel
  ALLOCATED data does not exist in the lifted shards at FY granularity
  (ICED Deep Dive is per-FY publisher total only, no per-fuel breakdown).
  C4.5 fills the per-fuel allocated gap at MONTHLY granularity via the
  CEA Monthly snapshot family above; the ICED-sourced multi-FY per-fuel
  allocated children remain orphan in the catalogue and earn rows when
  a multi-FY per-fuel allocated source lands. Documented in plan-doc
  TODO row 0e.7 P.1 §0e.7.5 "Known scope gap".
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import (
    CANONICAL_FUELS,
    SOURCE_IDS,
    SUB_FUEL_TO_CANONICAL,
    load_meadow,
    parse_iso_period,
    to_entity_id,
)


def _load_cea_meadow(repo_root: Path, file: str) -> dict:
    return load_meadow(repo_root, "energy", "cea", "2026-03", file)


def _load_iced_meadow(repo_root: Path, file: str) -> dict:
    return load_meadow(repo_root, "energy", "iced", "2024-25", file)


def _load_rbi_meadow(repo_root: Path, file: str) -> dict:
    return load_meadow(repo_root, "energy", "rbi", "2024-25", file)


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    # 1. CEA per-fuel shards →
    #    - installed-capacity-mw-{fuel} (IN rollup, derivation=sum)
    #    - installed-capacity-snapshot-mw-{fuel} (35 per-state rows
    #      per fuel, derivation=raw). P.1.A C4.5: the CEA Monthly IC sheet
    #      is published per-state per-fuel already; ICED state allocated
    #      tracks the same allocation basis at FY granularity but lacks a
    #      per-fuel breakdown (see "Known scope gap" above). The snapshot
    #      children fill that gap with the most recent month of CEA truth.
    #      Single-snapshot, comparable_across_states_snapshot_only — NOT a
    #      time series; restate on each fresh CEA monthly drop.
    for fuel in CANONICAL_FUELS:
        shard = _load_cea_meadow(repo_root, f"installed_capacity_{fuel}_mw.json")
        shard_rows = shard["rows"]
        if not shard_rows:
            continue
        # Single-snapshot shards — all rows share the same ``time``.
        snapshot_time = shard_rows[0]["time"]
        period_label, year, period_seq = parse_iso_period(snapshot_time)

        # IN rollup (pre-existing emit; kept byte-equivalent).
        per_state_sum = sum(float(r["value"]) for r in shard_rows)
        rows.append(ObservationRow(
            entity_id="IN",
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"installed-capacity-mw-{fuel}",
            value_numeric=per_state_sum,
            source_id=SOURCE_IDS["cea_monthly_ic"],
            derivation="sum",
        ))

        # C4.5: per-state per-fuel snapshot rows. Guard catches a shard
        # truncated upstream (CEA occasionally publishes a partial sheet
        # mid-month) — fail loud rather than silently emit 5 rows.
        assert len(shard_rows) >= 30, (
            f"CEA {fuel} shard truncated: {len(shard_rows)} rows; "
            f"expected ~35 (all states/UTs)"
        )
        for r in shard_rows:
            rows.append(ObservationRow(
                entity_id=to_entity_id(r["entity_id"]),
                year=year,
                period_label=period_label,
                period_seq=period_seq,
                indicator_id=f"installed-capacity-snapshot-mw-{fuel}",
                value_numeric=float(r["value"]),
                source_id=SOURCE_IDS["cea_monthly_ic"],
                derivation="raw",
            ))

    # 2. state_installed_capacity_geographical_mw.json
    #    → installed-capacity-geographical-mw (parent, publisher total)
    shard = _load_iced_meadow(repo_root, "state_installed_capacity_geographical_mw.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="installed-capacity-geographical-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_capacity_metatable"],
            derivation="raw",
        ))

    # 3. state_installed_capacity_by_source_mw.json
    #    → installed-capacity-geographical-mw-{fuel}
    #    Sub-fuel collapse: aggregate per (entity_id, time, canonical_fuel).
    shard = _load_iced_meadow(repo_root, "state_installed_capacity_by_source_mw.json")
    agg: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for r in shard["rows"]:
        sub_fuel = r["facet"]
        canonical = SUB_FUEL_TO_CANONICAL.get(sub_fuel)
        if canonical is None:
            # Unmapped sub-fuel (e.g. ICED "Others") — drop, per shard
            # notes ("cannot be mapped to a state choropleth honestly").
            continue
        agg[(r["entity_id"], r["time"], canonical)].append(float(r["value"]))
    for (entity_id, time_s, fuel), values in sorted(agg.items()):
        period_label, year, period_seq = parse_iso_period(time_s)
        # derivation = "sum" iff more than one sub-fuel landed in the cell
        # (always true for "renewable"; rarely true for others — defensive
        # in case ICED later subdivides a bucket that today is 1:1).
        derivation = "sum" if len(values) > 1 else "raw"
        rows.append(ObservationRow(
            entity_id=to_entity_id(entity_id),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"installed-capacity-geographical-mw-{fuel}",
            value_numeric=sum(values),
            source_id=SOURCE_IDS["iced_capacity_metatable"],
            derivation=derivation,
        ))

    # 4. state_installed_capacity_with_alloc_mw.json
    #    → installed-capacity-allocated-mw (parent, publisher total)
    shard = _load_iced_meadow(repo_root, "state_installed_capacity_with_alloc_mw.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="installed-capacity-allocated-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    # 5. state_installed_capacity_total_mw.json (RBI Handbook Table 140
    #    long-arc splice, pre-FY15 only).
    #    → installed-capacity-allocated-mw (parent, FY05-FY14)
    #    P.1.A C4.6: extends the publisher-total indicator backward 11
    #    fiscal years. Per plan-doc 20260522 §3 Q-c verdict, RBI Handbook
    #    Table 140 is the long-arc canonical for pre-FY15 state
    #    installed-capacity history. The shard carries 712 rows spanning
    #    2004-04..2024-04; we accept ONLY rows with time < "2015-04" here
    #    to avoid double-counting against block 4 (ICED Deep Dive, which
    #    already covers FY15 onwards). Citation row
    #    rbi_hbk_140_installed_capacity carries the silver tier (Q-d:
    #    RBI republishes CEA's underlying numbers); the methodology break
    #    row rbi-handbook-aggregate-no-fuel-split-pre-fy15 documents BOTH
    #    the basis transition at FY15 and the absence of per-fuel splits
    #    in the RBI portion. Shard has NO "IN" national-aggregate row
    #    (verified by inspection 2026-05-24 at lift-prep); the parent
    #    indicator carries only state/UT rows in this slice.
    shard = _load_rbi_meadow(repo_root, "state_installed_capacity_total_mw.json")
    for r in shard["rows"]:
        if r["time"] >= "2015-04":
            continue  # ICED Deep Dive (block 4) owns FY15+ rows.
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="installed-capacity-allocated-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_140_installed_capacity"],
            derivation="raw",
        ))

    # 6. state_rooftop_solar_capacity_mw.json (P.1.C PR-R)
    #    → state-rooftop-solar-capacity-mw
    #    Cumulative MW of building-mounted PV across residential /
    #    commercial / industrial / public categories. COMPLEMENTS (does
    #    NOT replace) utility-scale solar tracked under
    #    installed-capacity-snapshot-mw-renewable; the total state
    #    solar fleet = utility-scale + rooftop. ICED publishes one row
    #    per (state, fiscal_year) with cumulative MW; no facets, no
    #    sub-fuel collapse needed. Originating data: MNRE / state nodal
    #    agencies via the National Rooftop Solar Programme. Includes
    #    IN national rollup as a publisher-supplied row.
    shard = _load_iced_meadow(repo_root, "state_rooftop_solar_capacity_mw.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-rooftop-solar-capacity-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_rooftop_solar"],
            derivation="raw",
        ))

    # 7. india_thermal_capacity_retired_mw.json (P.1.C PR-S)
    #    → india-thermal-capacity-retired-mw-{fuel} (2-facet: coal, gas).
    #    First Pattern A-facet indicator in P.1.C cohort. National-only
    #    (entity_id always "IN"). Publisher emits 2 facets: "coal" and
    #    "oil-gas"; SUB_FUEL_TO_CANONICAL collapses "oil-gas" → "gas"
    #    per Hans D33.8 (the canonical fuel_type axis is the 5-bucket
    #    {coal, gas, hydro, nuclear, renewable}; oil-fired + diesel +
    #    gas-fired plants all sum into the "gas" bucket). Originating
    #    data: CEA station-level retirement records; ICED is the
    #    federal aggregator. Aggregate per (entity_id, time, canonical_
    #    fuel) -- in case any future publisher rotation adds sub-fuel
    #    rows that collapse to the same canonical bucket, the SUM keeps
    #    the contract atomic.
    shard = _load_iced_meadow(repo_root, "india_thermal_capacity_retired_mw.json")
    agg: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for r in shard["rows"]:
        sub_fuel = r["facet"]
        canonical = SUB_FUEL_TO_CANONICAL.get(sub_fuel)
        if canonical is None:
            continue
        agg[(r["entity_id"], r["time"], canonical)].append(float(r["value"]))
    for (entity_id, time_s, fuel), values in sorted(agg.items()):
        period_label, year, period_seq = parse_iso_period(time_s)
        derivation = "sum" if len(values) > 1 else "raw"
        rows.append(ObservationRow(
            entity_id=to_entity_id(entity_id),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"india-thermal-capacity-retired-mw-{fuel}",
            value_numeric=sum(values),
            source_id=SOURCE_IDS["iced_thermal_retired"],
            derivation=derivation,
        ))

    # PR-Y (2026-05-26): state_renewable_grid_capacity_mw.json
    # (RBI Hbk Table 143) -> state-renewable-grid-capacity-mw.
    # Pattern A-SINGLE (scalar; no facet axis). Calendar-year end-March
    # cumulative MW snapshots. Publisher emits no facet split (combined
    # wind + solar + small-hydro + biomass + waste-to-energy).
    shard = _load_rbi_meadow(repo_root, "state_renewable_grid_capacity_mw.json")
    for r in shard["rows"]:
        # time is calendar year like "2007"; the catalogue uses period
        # YYYY-04 (end-March snapshot semantics).
        year = int(r["time"])
        period_label = f"{year}-04"
        period_seq = year * 100 + 4
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-renewable-grid-capacity-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_143_renewable_grid_capacity"],
            derivation="raw",
        ))

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_installed_capacity",
        observation_rows=rows,
    )

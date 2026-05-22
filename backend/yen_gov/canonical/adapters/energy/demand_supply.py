"""Demand & supply envelope — ``energy_demand_supply.parquet``.

Lifts 3 legacy shards:

* ``state_peak_demand_mw.json`` (396 RBI Table 142 rows)
  → ``state-peak-electricity-demand-mw``.
* ``state_peak_met_mw.json`` (396 RBI Table 142 companion rows)
  → ``state-peak-electricity-supplied-mw``.
* ``state_per_capita_electricity_consumption_kwh.json`` (555 ICED rows)
  → ``state-per-capita-electricity-consumption-kwh``.

The two RBI rows form a citizen-readable pair: peak DEMAND is the
instant the State Load Despatch Centre saw the highest simultaneous
load; peak SUPPLIED (a.k.a. "peak met") is how much of that demand was
actually served. The gap is the unmet peak — see plan-doc TODO row
0e.7 P.1 §5 for the choice between this RBI pair (citizen-canonical)
and the ICED Deep Dive tail (peak_demand_mw == 33 rows for FY26 only,
HARD DROP per scope list).
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import SOURCE_IDS, load_shard, parse_iso_period, to_entity_id


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    # 1. state_peak_demand_mw.json → state-peak-electricity-demand-mw
    shard = load_shard(repo_root, "state_peak_demand_mw.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-peak-electricity-demand-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_142_peak_demand"],
            derivation="raw",
        ))

    # 2. state_peak_met_mw.json → state-peak-electricity-supplied-mw
    shard = load_shard(repo_root, "state_peak_met_mw.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-peak-electricity-supplied-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_142_peak_met"],
            derivation="raw",
        ))

    # 3. state_per_capita_electricity_consumption_kwh.json
    shard = load_shard(repo_root, "state_per_capita_electricity_consumption_kwh.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-per-capita-electricity-consumption-kwh",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_demand_supply",
        observation_rows=rows,
    )

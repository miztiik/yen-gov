"""Demand & supply envelope — ``energy_demand_supply.parquet``.

Lifts 4 legacy shards:

* ``state_peak_demand_mw.json`` (396 RBI Table 142 rows)
  → ``state-peak-electricity-demand-mw`` (FY13–FY24).
* ``state_peak_met_mw.json`` (396 RBI Table 142 companion rows)
  → ``state-peak-electricity-supplied-mw`` (FY13–FY24).
* ``state_per_capita_electricity_consumption_kwh.json`` (555 ICED rows)
  → ``state-per-capita-electricity-consumption-kwh``.
* ``state_electricity_peak_demand_mw.json`` — FY25 ROWS ONLY (34 rows
  inc. IN national aggregate) → ``state-peak-electricity-demand-mw``.
  The FY18–FY24 rows in this shard overlap with the RBI source above
  but DIFFER on 192/221 cells; RBI Handbook Table 142 is the gold
  authority for FY13–FY24 (Hans D33), so we drop the overlap and
  extend coverage by one year only. See plan-doc
  ``TODO/20260524-p1a-data-reacquisition-plan.md`` §3 C4.7.

The two RBI rows form a citizen-readable pair: peak DEMAND is the
instant the State Load Despatch Centre saw the highest simultaneous
load; peak SUPPLIED (a.k.a. "peak met") is how much of that demand was
actually served. The gap is the unmet peak.

C4.7 design choice (verbatim from re-acquisition plan §3): shard 2
(``state_electricity_peak_demand_mw.json``, 305 rows, FY17–FY25 from
ICED state-wise-deep-dive) is the FY25 source because it includes the
``IN`` national aggregate (245 416 MW) which shard 1 omits. Shard 1
(``state_peak_electricity_demand_mw.json``, 33 state rows for FY25
from ICED powerStatistics) is a strict subset of shard 2's FY25 slice
with byte-identical state values. The mixed source_id on the same
indicator column is contract-clean per writer D7: ``source_id`` is a
per-row column NOT in the dedup key, so RBI rows (FY13–FY24) coexist
with ICED rows (FY25) on the same
``(entity_id, year, period_label, indicator_id)`` key space without
UPSERT conflict.

Retirement of both ICED legacy shards is DEFERRED — additive lift only
in this PR. The §13 browser-smoke gate on ``/s/<state>`` revealed that
the frontend state-hub indicator-widget loader fetches both shards by
slug; deleting them produces ``/indicators/in/energy/*.json`` 404s on
every state page. The strangler-fig retirement is now four phases:
Phase A (this PR — additive FY25 on canonical) → Phase B (frontend
reader-switch to canonical parquet for this indicator) → Phase C
(rewrite this lift to drop block 4 and read FY25 directly from
canonical, eliminating the backend ``load_shard`` dependency on these
two files) → Phase D (``git rm`` shards + scrub allowlist + drop docs
rows). See plan-doc §3 C4.7 for the descope narrative.
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

    # 4. state_electricity_peak_demand_mw.json (FY25 only)
    #    → state-peak-electricity-demand-mw (one-year extension)
    # Filter is required: FY18-FY24 rows in this shard overlap with
    # RBI Handbook Table 142 (lift block 1) but differ on 192/221 cells.
    # Hans D33 designates RBI as the gold authority for FY13-FY24, so we
    # take ICED only for the FY25 tail where RBI has no row. The mixed
    # source_id is contract-clean per writer D7 (source_id is per-row,
    # not in the dedup key).
    shard = load_shard(repo_root, "state_electricity_peak_demand_mw.json")
    for r in shard["rows"]:
        if r["time"] != "2025-04":
            continue
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-peak-electricity-demand-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_demand_supply",
        observation_rows=rows,
    )

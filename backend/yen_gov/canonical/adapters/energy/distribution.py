"""Distribution-performance envelope — ``energy_distribution_performance.parquet``.

Lifts 2 legacy shards (DISCOM ledger surface):

* ``state_atc_losses_pct.json`` (344 rows)
  → ``state-atc-losses-pct``.
* ``state_electricity_sales_mu.json`` (356 rows)
  → ``state-electricity-sales-mu``.

ATC = Aggregate Technical + Commercial losses, the flagship DISCOM health
indicator (UDAY target was <15% by FY19). Sales-MU is the volume of
energy DISCOMs billed end-consumers for; pairs with the ATC% to triangulate
revenue leakage.

Reserved for P.1.B (DISCOM finance pivot): ACS-ARR gap, billing
efficiency, collection efficiency, T&D losses-pct. Those indicators
exist as legacy shards under ``datasets/indicators/in/energy/`` but the
catalogue does not enumerate them yet — Hans + Max review pending.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import SOURCE_IDS, load_shard, parse_iso_period, to_entity_id


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    # 1. state_atc_losses_pct.json → state-atc-losses-pct
    shard = load_shard(repo_root, "state_atc_losses_pct.json")
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
    shard = load_shard(repo_root, "state_electricity_sales_mu.json")
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

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_distribution_performance",
        observation_rows=rows,
    )

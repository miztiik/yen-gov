"""Generation envelope — ``energy_generation.parquet``.

Lifts 2 meadow shards (per ADR-0041, ``datasets/energy/_meadow/iced/2024-25/``):

* ``state_electricity_generation_mu.json`` (407 publisher totals)
  → ``state-electricity-generation-gwh`` (1 MU = 1 GWh; same numeric).
* ``state_electricity_generation_by_source_gwh.json`` (~1685 per-fuel)
  → ``state-electricity-generation-gwh-{fuel}`` (after sub-fuel collapse).

The unit-name change (MU on the meadow shard label vs GWh on the
catalogue label) is purely cosmetic — 1 Million Unit = 1 GigaWatt-hour.
The catalogue's GWh is the citizen-honest unit (the OWID convention);
the meadow shard label is preserved verbatim for provenance.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import (
    SOURCE_IDS,
    SUB_FUEL_TO_CANONICAL,
    load_meadow,
    parse_iso_period,
    to_entity_id,
)


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    # 1. state_electricity_generation_mu.json (publisher total)
    #    → state-electricity-generation-gwh (parent). 1 MU = 1 GWh.
    shard = load_meadow(
        repo_root, "energy", "iced", "2024-25",
        "state_electricity_generation_mu.json",
    )
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-electricity-generation-gwh",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_gen_metatable"],
            derivation="raw",
        ))

    # 2. state_electricity_generation_by_source_gwh.json
    #    → state-electricity-generation-gwh-{fuel} (sub-fuel collapse).
    shard = load_meadow(
        repo_root, "energy", "iced", "2024-25",
        "state_electricity_generation_by_source_gwh.json",
    )
    agg: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for r in shard["rows"]:
        sub_fuel = r["facet"]
        canonical = SUB_FUEL_TO_CANONICAL.get(sub_fuel)
        if canonical is None:
            # Drop "Others" per shard notes — interstate / central plants
            # pre-allocation cannot be mapped to a state honestly.
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
            indicator_id=f"state-electricity-generation-gwh-{fuel}",
            value_numeric=sum(values),
            source_id=SOURCE_IDS["iced_gen_metatable"],
            derivation=derivation,
        ))

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_generation",
        observation_rows=rows,
    )

"""Generation envelope — ``energy_generation.parquet``.

Lifts 3 meadow shards (per ADR-0041, ``datasets/energy/_meadow/iced/2024-25/``):

* ``state_electricity_generation_mu.json`` (407 publisher totals)
  → ``electricity-generation-gwh`` (1 MU = 1 GWh; same numeric).
* ``state_electricity_generation_by_source_gwh.json`` (~1685 per-fuel)
  → ``electricity-generation-gwh-{fuel}`` (after sub-fuel collapse).
* ``state_plant_load_factor_pct.json`` (1652 per-fuel, PR-V 2026-05-26)
  → ``state-plant-load-factor-pct-{fuel}`` (NO sub-fuel collapse;
  1:1 mapping to 8 distinct fuel_type values).

The unit-name change (MU on the meadow shard label vs GWh on the
catalogue label) is purely cosmetic — 1 Million Unit = 1 GigaWatt-hour.
The catalogue's GWh is the citizen-honest unit (the OWID convention);
the meadow shard label is preserved verbatim for provenance.

PR-V exception to SUB_FUEL_TO_CANONICAL: PLF is a percentage (%).
Summing per-state per-FY PLF values across renewable sub-fuels
(bio-power + small-hydro + solar + wind) -- which is what
SUB_FUEL_TO_CANONICAL would force via the renewable collapse -- yields
a meaningless number (you cannot add 25% solar PLF + 25% wind PLF and
get 50%). Therefore PR-V uses ``_PLF_PUBLISHER_TO_CANONICAL_FUEL``, a
1:1 dict over the 8 publisher labels mapping to 8 distinct existing
fuel_type axis values. The parent ``state-plant-load-factor-pct``
catalogues with 0 rows; the 8 children own all passthrough obs.
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
    #    → electricity-generation-gwh (parent). 1 MU = 1 GWh.
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
            indicator_id="electricity-generation-gwh",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_gen_metatable"],
            derivation="raw",
        ))

    # 2. state_electricity_generation_by_source_gwh.json
    #    → electricity-generation-gwh-{fuel} (sub-fuel collapse).
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
            indicator_id=f"electricity-generation-gwh-{fuel}",
            value_numeric=sum(values),
            source_id=SOURCE_IDS["iced_gen_metatable"],
            derivation=derivation,
        ))

    # 3. state_plant_load_factor_pct.json (PR-V 2026-05-26) → 8-fuel PLF
    #    children. Passthrough; no sub-fuel collapse (PLF is a %).
    _append_plf_rows(repo_root, rows)

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_generation",
        observation_rows=rows,
    )


# PR-V (2026-05-26): publisher PLF fuel label → canonical fuel_type axis
# value. 1:1 mapping (NO SUB_FUEL_TO_CANONICAL renewable collapse, see
# module docstring rationale). All 8 publisher labels resolve to a
# distinct existing fuel_type axis value_id.
_PLF_PUBLISHER_TO_CANONICAL_FUEL: dict[str, str] = {
    "bio-power":   "biomass",
    "coal":        "coal",
    "hydro":       "hydro",
    "nuclear":     "nuclear",
    "oil-gas":     "gas",
    "small-hydro": "small-hydro",  # kebab indicator-id suffix; dim val is snake `small_hydro`
    "solar":       "solar",
    "wind":        "wind",
}


def _append_plf_rows(repo_root: Path, rows: list[ObservationRow]) -> None:
    """Lift state_plant_load_factor_pct.json (PR-V) into the generation
    parquet. Each (state, FY, fuel) row passes through unchanged as a
    child indicator; the parent ``state-plant-load-factor-pct`` carries
    zero rows (catalogue / facet-picker only).
    """
    shard = load_meadow(
        repo_root, "energy", "iced", "2024-25",
        "state_plant_load_factor_pct.json",
    )
    for r in shard["rows"]:
        canonical_fuel = _PLF_PUBLISHER_TO_CANONICAL_FUEL.get(r["facet"])
        if canonical_fuel is None:
            # Defensive: any unmapped publisher label is dropped rather
            # than fabricated into a catalogue child. Today the dict
            # covers 100% of publisher labels (8/8); this guard catches
            # publisher relabels.
            continue
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"state-plant-load-factor-pct-{canonical_fuel}",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_plant_load_factor"],
            derivation="raw",
        ))

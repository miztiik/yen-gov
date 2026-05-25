"""Fuel-consumption envelope -- ``energy_fuel_consumption.parquet``.

P.1.C PR-Q (1 indicator; first canonical fuel-consumption lift):

* ``state_coal_consumption_mt.json`` (450 rows, no facet)
  -> ``state-coal-consumption-mt``.

Establishes the new ``energy_fuel_consumption`` table stem that the
P.1.A ``__init__.py`` docstring reserved but never populated. Subsequent
P.1.C PRs (oil-product consumption, national primary/final energy
supply) will land additional indicators on this same stem.

Coal-consumption methodology: the ICED endpoint publishes 4 grade-level
rows per (state, FY) -- raw + washed + middlings + lignite -- AND a
precomputed ``TOTAL COAL`` row for the most-recent FYs only. The lift
drops the ``TOTAL COAL`` rows (sparse + double-counting risk) and sums
the 4 grades directly. The meadow shard ALREADY does this sum at
ingest time, so the rows arriving here are pre-aggregated state x FY
totals with NO facet field. The adapter just emits 1 ObservationRow
per shard row.

Coal-consumption is a *consumption* statistic (where coal is burned,
not where it is mined). Companions for cross-read: the coal facet of
``state-installed-capacity-allocated-mw`` (siting) and the coal facet of
``state-electricity-generation-gwh`` (gen-from-coal). Industrial heat
use (cement, steel) is the gap between consumption and gen-from-coal.

Hans+Max (data shape) + Gregor (contract) authorities apply per
CLAUDE.md S0a.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import SOURCE_IDS, load_meadow, parse_iso_period, to_entity_id


_ICED_2024_25 = ("energy", "iced", "2024-25")


def _load_fuel_consumption_meadow(repo_root: Path, file: str) -> dict:
    return load_meadow(repo_root, *_ICED_2024_25, file)


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    # 1. state_coal_consumption_mt.json -> state-coal-consumption-mt
    shard = _load_fuel_consumption_meadow(repo_root, "state_coal_consumption_mt.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="state-coal-consumption-mt",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_consumption_coal"],
            derivation="raw",
        ))

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_fuel_consumption",
        observation_rows=rows,
    )

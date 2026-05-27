"""Fuel-consumption envelope -- ``energy_fuel_consumption.parquet``.

P.1.C PR-Q (1 indicator; first canonical fuel-consumption lift):

* ``state_coal_consumption_mt.json`` (450 rows, no facet)
  -> ``state-coal-consumption-mt``.

P.1.C PR-T (1 indicator; second canonical fuel-consumption lift):

* ``state_oil_product_consumption_kt.json`` (2901 rows, 7-facet on
  the NEW ``oil_product`` axis: diesel-hsd, petrol, lpg, kerosene,
  naphtha, petroleum-coke, others)
  -> ``state-oil-product-consumption-kt-{product}`` (7 child indicators
  + 1 compute-on-read parent).

P.1.C PR-U (1 indicator; third canonical fuel-consumption lift):

* ``national_primary_energy_supply_mtoe.json`` (140 rows, 7-facet on
  the EXISTING ``fuel_type`` axis extended with `oil` + `renewable`
  value_ids; publisher "renewables" plural -> canonical "renewable"
  singular; publisher "total" rows are FILTERED at adapter time as
  compute-on-read parent)
  -> ``india-primary-energy-supply-mtoe-{fuel}`` (6 child indicators
  + 1 compute-on-read parent). National-grain (IN entity only).

Establishes the new ``energy_fuel_consumption`` table stem that the
P.1.A ``__init__.py`` docstring reserved but never populated. Subsequent
P.1.C PRs (national final energy supply) will land additional
indicators on this same stem.

Coal-consumption methodology: the ICED endpoint publishes 4 grade-level
rows per (state, FY) -- raw + washed + middlings + lignite -- AND a
precomputed ``TOTAL COAL`` row for the most-recent FYs only. The lift
drops the ``TOTAL COAL`` rows (sparse + double-counting risk) and sums
the 4 grades directly. The meadow shard ALREADY does this sum at
ingest time, so the rows arriving here are pre-aggregated state x FY
totals with NO facet field. The adapter just emits 1 ObservationRow
per shard row.

Oil-product methodology: the ICED endpoint publishes 7 product-level
rows per (state, FY); meadow drops the ``OTHERS`` state bucket and the
``IN`` national-aggregate row at ingest time. The 7 publisher labels
(DIESEL/HSD, PETROL, LPG, SKO, NAPHTHA, PETROLEUM COKE, OTHERS) are
already normalised by the ingest parser to lowercase-hyphen slugs that
match the canonical ``oil_product`` axis 1:1 (NO collapse step needed;
contrast with fuel_type's SUB_FUEL_TO_CANONICAL).

Coal-consumption is a *consumption* statistic (where coal is burned,
not where it is mined). Companions for cross-read: the coal facet of
``state-installed-capacity-allocated-mw`` (siting) and the coal facet of
``electricity-generation-gwh`` (gen-from-coal). Industrial heat
use (cement, steel) is the gap between consumption and gen-from-coal.

Oil-product consumption is also a *where-consumed* statistic. Diesel
and petrol track economic activity (transport, agriculture); LPG tracks
household-policy coverage (PMUY scheme); petroleum coke tracks
industrial heat use (cement, glass).

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

    # 2. state_oil_product_consumption_kt.json (P.1.C PR-T)
    #    -> state-oil-product-consumption-kt-{product} (7 children).
    #    7-facet Pattern A-facet on the NEW ``oil_product`` axis.
    #    Publisher labels (already normalised by the ICED ingest parser
    #    at backend/yen_gov/sources/iced_fuel/parsers.py _OIL_PRODUCT_SLUG)
    #    map 1:1 onto canonical value_ids -- no SUB_FUEL_TO_CANONICAL-style
    #    collapse step. Each emitted row is derivation="raw" because the
    #    publisher emits a single value per (state, FY, product); no
    #    aggregation happens at canonical lift time. The meadow has already
    #    dropped the ``OTHERS`` state bucket and the ``IN`` national row at
    #    ingest time, so every row arriving here resolves to a real ECI
    #    sub-national entity_id.
    shard = _load_fuel_consumption_meadow(repo_root, "state_oil_product_consumption_kt.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"state-oil-product-consumption-kt-{r['facet']}",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_consumption_oil"],
            derivation="raw",
        ))

    # 3. national_primary_energy_supply_mtoe.json (P.1.C PR-U)
    #    -> india-primary-energy-supply-mtoe-{fuel} (6 children).
    #    7-facet publisher (coal/oil/gas/hydro/nuclear/renewables/total)
    #    on the EXISTING ``fuel_type`` axis extended with `oil` +
    #    `renewable` value_ids in this PR. Publisher "renewables"
    #    (plural) collapses to canonical "renewable" (singular) per
    #    indicator-naming.md. Publisher "total" rows are FILTERED here
    #    because the parent indicator (parent_indicator_id=null) is
    #    compute-on-read: catalogue parent carries 0 obs rows; total
    #    is SUM of children at query time via
    #    allow_compute_on_read_total=True. National-grain: every row
    #    arriving has entity_id="IN" and to_entity_id passes it through.
    #    Derivation="raw" because the publisher emits a single per-
    #    (fuel, FY) value; no aggregation at canonical lift time.
    _PUBLISHER_TO_CANONICAL_FUEL = {
        "coal": "coal",
        "oil": "oil",
        "gas": "gas",
        "hydro": "hydro",
        "nuclear": "nuclear",
        "renewables": "renewable",  # publisher plural -> canonical singular
    }
    shard = _load_fuel_consumption_meadow(repo_root, "national_primary_energy_supply_mtoe.json")
    for r in shard["rows"]:
        publisher_facet = r["facet"]
        if publisher_facet == "total":
            # Compute-on-read parent: drop "total" rows so the parent
            # indicator carries 0 obs rows and frontends compute total
            # = SUM(children) at query time.
            continue
        canonical_fuel = _PUBLISHER_TO_CANONICAL_FUEL[publisher_facet]
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"india-primary-energy-supply-mtoe-{canonical_fuel}",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_primary_energy_supply"],
            derivation="raw",
        ))

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_fuel_consumption",
        observation_rows=rows,
    )

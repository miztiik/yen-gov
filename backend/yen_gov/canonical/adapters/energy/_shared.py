"""Shared helpers for the energy adapter modules.

Three concerns live here:

* ``SOURCE_IDS`` — the 6 verified source_id strings from P.1.A C3
  (`624852ff`). Hand-typed verbatim; the writer's FK gate verifies
  closure against the citation ledger before any bytes touch disk.
* ``SUB_FUEL_TO_CANONICAL`` — the sub-fuel-label → canonical-5 mapping
  that collapses ICED's 7-9 sub-fuel buckets to Hans' five-bucket
  catalogue (D33.8). Adapters MUST go through this map; in-line
  string-matching is a band-aid (Holy Law #5).
* ``parse_iso_period(time)`` — decode the legacy shard's ``time`` field
  (``"YYYY-MM"`` for month/fiscal_year grains, ``"YYYY"`` for year grain)
  into the canonical observation triple ``(period_label, year, period_seq)``
  the writer expects.

Loaders here are deliberately thin (json.loads + path resolution). Any
schema-tag inheritance from the legacy shard is forbidden — adapters
MUST use the catalogue (``datasets/taxonomy/indicators.json``) as the
sole authority for indicator metadata (attribution_geography, unit, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path


# 6 source_ids verified at P.1.A C3 (`624852ff`) + 1 added at P.1.A C4.6
# (RBI Handbook Table 140 long-arc splice) + 5 added at P.1.B (DISCOM
# finance + demand/supply lift: 2 ICED distribution endpoints + 3 RBI
# Handbook tables 138 / 139 / 141). DO NOT re-derive these in the
# adapter — the citation ledger is the source of truth, and the writer's
# FK gate verifies each appears in ``datasets/data/entities/source.csv``
# before observation rows touch disk. If a future PR changes the source
# triple (`producer | title | vintage`) for any of these, the hash will
# rotate and BOTH the catalogue + this constant must update together.
SOURCE_IDS: dict[str, str] = {
    "cea_monthly_ic":                "src-092a5dc7af3f",
    "iced_capacity_metatable":       "src-1240f07df0ac",
    "iced_deep_dive":                "src-bb1d7bec8b34",
    "iced_gen_metatable":            "src-ddbfadd51428",
    "rbi_hbk_142_peak_demand":       "src-99ac1fee8a50",
    "rbi_hbk_142_peak_met":          "src-9c02616a7166",
    # P.1.A C4.6 (RBI Handbook Table 140 long-arc FY05-FY14 splice).
    # Derived via derive_source_id("Reserve Bank of India",
    # "Handbook of Statistics on Indian States — Table 140: State-wise
    # Installed Capacity of Power", "2024-25").
    "rbi_hbk_140_installed_capacity": "src-3d1d55f8a94b",
    # P.1.B (DISCOM finance + demand/supply lift). Distinct citation
    # triples for the two ICED distribution endpoints (operational
    # performance — billing eff / collection eff / T&D loss — and RPO
    # compliance) and three RBI Handbook tables not previously cited
    # (141 power requirement, 139 power availability, 138 per-capita
    # availability). All five paired into the same `taxonomy/sources.
    # parquet` UPSERT via `energy_sources_seed.py` (12 nicknames at
    # P.1.B). The ICED Deep Dive row (`iced_deep_dive` above) continues
    # to cover the ACS-ARR gap shard (sourced from `/analytics/state-
    # wise-deep-dive`); the distribution-dashboard endpoints are
    # genuinely distinct upstream products and earn their own ledger
    # rows per ADR-0032 citation identity = (producer, title, vintage).
    # ICED ids rotated under ADR-0042 (source schema v3.0): vintage
    # flipped from "" → "2024-25" so the 5 ICED hashes are now distinct
    # from each other AND match their meadow-path vintage segment per
    # ADR-0041 §nn4 (Tier-B rule, enforced in validate.py).
    "iced_distribution_perf":            "src-650b1c25d1f7",
    "iced_distribution_rpo":             "src-0ea63ed47704",
    "rbi_hbk_141_power_requirement":     "src-f7ce9960caba",
    "rbi_hbk_139_power_availability":    "src-97a3c47d092f",
    "rbi_hbk_138_per_capita_availability": "src-9a38005d8713",
    # P.1.C PR-Q (coal consumption lift, 2026-05-25). Derived via
    # derive_source_id("NITI Aayog India Climate & Energy Dashboard",
    # "Coal Consumption (Domestic) State-wise API (per-state fiscal-year
    # coal consumption, by grade)", "2024-25"). First P.1.C source seed;
    # establishes the new ``energy_fuel_consumption`` table stem reserved
    # in __init__.py docstring as the P.1.C target.
    "iced_consumption_coal":             "src-c222a8e2cd61",
    # P.1.C PR-R (rooftop solar capacity lift, 2026-05-25). Derived via
    # derive_source_id("NITI Aayog India Climate & Energy Dashboard",
    # "Rooftop Solar Capacity (MW) State-wise API (per-state cumulative
    # rooftop solar installed capacity)", "2024-25"). Adds state-rooftop-
    # solar-capacity-mw to the existing ``energy_installed_capacity``
    # table stem (rooftop is a sub-fuel measurement of installed MW,
    # complementing utility-scale solar already tracked under
    # installed-capacity-snapshot-mw-renewable).
    "iced_rooftop_solar":                "src-018bb42f9519",
    # P.1.C PR-S (thermal capacity retired lift, 2026-05-25). Derived via
    # derive_source_id("NITI Aayog India Climate & Energy Dashboard",
    # "Retired Thermal Capacity Plants Dashboard (national fiscal-year
    # retired generating capacity by fuel)", "2024-25"). First Pattern
    # A-facet in P.1.C cohort: national-grain entity_id=IN only;
    # 2-facet axis fuel_type ∈ {coal, gas} after SUB_FUEL_TO_CANONICAL
    # collapse (publisher "oil-gas" → canonical "gas"). Lifts onto the
    # existing ``energy_installed_capacity`` table stem (retired
    # capacity is the inverse measurement of installed; same axis).
    "iced_thermal_retired":              "src-fd152bd3c6c6",
    # P.1.C PR-T (oil-product consumption lift, 2026-05-26). Derived via
    # derive_source_id("NITI Aayog India Climate & Energy Dashboard",
    # "Oil Product Consumption State-wise API (per-state fiscal-year
    # refined-petroleum-product consumption, by product)", "2024-25").
    # Pattern A-facet on the NEW ``oil_product`` axis (7 publisher
    # labels map 1:1 to canonical value_ids: diesel-hsd, petrol, lpg,
    # kerosene, naphtha, petroleum-coke, others). Lifts onto the
    # existing ``energy_fuel_consumption`` table stem reserved by PR-Q.
    "iced_consumption_oil":              "src-cba8334fedc5",
    # P.1.C PR-U (national primary energy supply lift, 2026-05-26).
    # Derived via derive_source_id("NITI Aayog India Climate & Energy
    # Dashboard", "Primary Energy Supply National API (national fiscal-
    # year primary-energy supply (TPES) by source, mtoe)", "2024-25").
    # Second Pattern A-facet in P.1.C cohort: national-grain entity_id=
    # IN only; 6-facet axis fuel_type ∈ {coal, gas, hydro, nuclear, oil,
    # renewable} (extends the existing axis with `oil` + `renewable`
    # value_ids in this PR). Publisher "renewables" (plural aggregate)
    # → canonical "renewable" singular; publisher "total" facet rows
    # are FILTERED at adapter time (compute-on-read parent semantics --
    # the catalogue parent indicator carries 0 rows; total = SUM of
    # children). Lifts onto the EXISTING ``energy_fuel_consumption``
    # table stem per the PR-Q docstring reservation for "national
    # primary/final energy supply" PRs.
    "iced_primary_energy_supply":        "src-170d3536d908",
    # P.1.C PR-V (state plant load factor by fuel, 2026-05-26). Derived
    # via derive_source_id("NITI Aayog India Climate & Energy Dashboard",
    # "Plant Load Factor by Fuel State API (state-wise per-fuel PLF
    # percentage, fiscal-year, 8 fuel buckets)", "2024-25"). Third
    # Pattern A-facet in P.1.C cohort. 8 publisher fuel labels
    # (bio-power, coal, hydro, nuclear, oil-gas, small-hydro, solar,
    # wind) map 1:1 to existing fuel_type axis values (biomass / coal
    # / hydro / nuclear / gas / small_hydro / solar / wind) with NO
    # SUB_FUEL_TO_CANONICAL collapse step (PLF is a percentage --
    # cross-fuel summation is meaningless). The catalogue parent
    # carries 0 rows; the 8 children each own per-state per-FY rows
    # for one fuel. Lifts onto the EXISTING ``energy_generation``
    # table stem (PLF is a generation-utilization metric).
    "iced_plant_load_factor":            "src-7eb929cbf2d8",
    # P.1.C PR-W (state power purchase share by source, 2026-05-26).
    # Derived via derive_source_id("NITI Aayog India Climate & Energy
    # Dashboard", "State Power Purchase Quantum and Cost API (state-wise
    # procurement-mix share by source, fiscal-year, 12 source buckets)",
    # "2024-25"). Fourth Pattern A-facet in P.1.C cohort. 12 publisher
    # source buckets (8 PR-V-style fuels + diesel + hybrid-bundled +
    # other-res + trading-and-others) -- 10 map 1:1 to existing
    # fuel_type axis values; 2 require NEW value_ids (hybrid_bundled,
    # trading_other). PR-W is a procurement-mix indicator (where
    # DISCOMs BUY from); values are percentages summing to ~100 per
    # (state, FY); cannot collapse renewable sub-fuels (same PLF-style
    # exemption as PR-V). The catalogue parent carries 0 rows; the 12
    # children each own per-state per-FY rows for one source. Lifts
    # onto the EXISTING ``energy_demand_supply`` table stem.
    "iced_power_purchase_share":         "src-1401f8087b0d",
    # P.1.C PR-X (national final-energy consumption by sector x fuel,
    # 2026-05-26). Derived via derive_source_id("NITI Aayog India
    # Climate & Energy Dashboard", "Final Energy Consumption National
    # API (national fiscal-year final-energy consumption by sector x
    # fuel composite, mtoe)", "2024-25"). Fifth Pattern A-facet in P.1.C
    # cohort. Introduces NEW `sector_fuel_pair` facet axis with 18
    # publisher (sector | fuel) pairs collapsed to kebab indicator-id
    # suffixes (publisher 'agriculture | oil' -> canonical pair-id
    # 'agriculture-oil'). National-only IN entity, FY05-FY24. Lifts
    # onto the EXISTING ``energy_demand_supply`` table stem (final
    # consumption is the consumer-side counterpart of primary supply).
    "iced_final_energy_consumption":     "src-29ecbb6dce9d",
    # P.1.C PR-Y (state-wise grid-connected renewable installed capacity
    # MW, RBI Handbook Table 143, 2026-05-26). Derived via
    # derive_source_id("Reserve Bank of India", "Handbook of Statistics
    # on Indian States, Table 143 (State-wise grid-connected renewable
    # installed capacity, MW, end-March snapshot)", "2024-25"). Pattern
    # A-SINGLE (scalar; no facet axis). End-March cumulative MW for
    # combined wind + solar + small-hydro + biomass + waste-to-energy;
    # publisher does NOT split per-source at this grain. Lifts onto
    # the EXISTING ``energy_installed_capacity`` table stem.
    "rbi_hbk_143_renewable_grid_capacity": "src-1f51c8d742bf",
    # 2026-05-27 ICED plantPipelineInfo (under-construction capacity GW).
    # Derived via derive_source_id("NITI Aayog India Climate & Energy
    # Dashboard", "Plant Pipeline Info National API (national under-
    # construction generation capacity by expected commissioning calendar-
    # year, by status, GW)", "2026-05-27"). First ingest through 4-layer
    # doctrine + ADR-0046 pre-flight gate. National-only entity_id="IN";
    # 2 status facets summed to one row per calendar year. Lifts onto the
    # NEW ``energy_capacity_pipeline`` table stem (under-construction is
    # a fundamentally different physical state from commissioned per
    # ADR-0044 concept-identity doctrine -- own stem, not facet on
    # ``energy_installed_capacity``).
    "iced_plant_pipeline":               "src-e0b2a084d204",
}


# Sub-fuel label (as it appears in the legacy shard's ``facet`` field) →
# canonical-5 fuel_type axis value. Hans' D33.8 ruling: the catalogue
# narrows to {coal, gas, hydro, nuclear, renewable}; sub-fuels collapse
# to ``renewable`` with derivation="sum" on emit so the precision loss
# is auditable.
#
# Direct 1:1 buckets stay raw; the renewable bucket is the SUM of
# bio-power + small-hydro + solar + wind + waste-to-energy on a given
# (entity_id, time) cell.
#
# ICED's ``Others`` bucket (interstate/central plants pre-allocation)
# is intentionally absent from this map — adapters drop unmapped facets
# rather than fabricate a state attribution. Same call ICED makes upstream
# for the choropleth (per state_electricity_generation_by_source_gwh.json
# notes).
SUB_FUEL_TO_CANONICAL: dict[str, str] = {
    # Direct 1:1 matches.
    "coal":            "coal",
    "hydro":           "hydro",      # ICED "Hydro" = large hydro (> 25 MW)
    "nuclear":         "nuclear",
    "oil-gas":         "gas",        # ICED labelling: gas + diesel + furnace oil
    "gas":             "gas",        # CEA per-fuel shard already uses "gas"
    "renewable":       "renewable",  # CEA per-fuel shard already uses "renewable"
    # Renewables — collapse to the 5-bucket "renewable" canonical.
    "wind":            "renewable",
    "solar":           "renewable",
    "small-hydro":     "renewable",
    "bio-power":       "renewable",
    "biomass":         "renewable",
    "waste-to-energy": "renewable",
}


# Canonical 5-bucket fuel ordering (Hans D33.8). Used by the national
# rollup so the per-fuel observation rows always emit in a deterministic
# order, regardless of which sub-fuel collapse hit the renewable bucket.
CANONICAL_FUELS: tuple[str, ...] = ("coal", "gas", "hydro", "nuclear", "renewable")


def parse_iso_period(time: str) -> tuple[str, int, int]:
    """Decode a legacy shard ``time`` value to the canonical triple.

    The shard uses ``"YYYY"`` for year grain (Wikipedia / older
    summaries), ``"YYYY-MM"`` for month and fiscal_year grains (CEA
    Monthly Executive Summary uses ``"YYYY-MM"`` directly; ICED uses
    ``"YYYY-04"`` for FY-start = April of year YYYY).

    Returns:
        (period_label, year, period_seq) where:
        * ``period_label`` is the shard string verbatim (citizen-facing).
        * ``year`` is the integer YYYY (OWID axis, observation schema
          requires ``integer ge=1500 le=2100``).
        * ``period_seq`` is month-of-year (1..12) for ``YYYY-MM`` inputs,
          defaults to 1 for year-only inputs. Lets multiple snapshots
          inside the same year sort deterministically.

    Raises:
        ValueError on a malformed input — adapters MUST validate at
        the shard boundary, not silently coerce.
    """
    if "-" in time:
        year_s, mon_s = time.split("-", 1)
        year = int(year_s)
        period_seq = int(mon_s)
        if not (1 <= period_seq <= 12):
            raise ValueError(f"Period month-segment out of range: {time!r}")
        return time, year, period_seq
    # Year-only path.
    year = int(time)
    return time, year, 1


def to_entity_id(state_code: str) -> str:
    """Canonicalise a legacy shard ``entity_id`` (``"IN"`` or ``"S07"``)
    to the catalogue form (``"IN"`` for country, ``"IN-S07"`` for state /UT).

    The catalogue authoritatively uses the ``IN-`` prefix for all sub-
    national entities (per ``datasets/taxonomy/entities.json``); legacy
    shards omit it for state/UT rows. The writer's FK gate rejects any
    observation whose ``entity_id`` is not in ``entities.json``, so this
    prefix MUST be applied at lift time.
    """
    if state_code == "IN":
        return "IN"
    return f"IN-{state_code}"


def load_meadow(
    repo_root: Path,
    family: str,
    source: str,
    vintage: str,
    file: str,
) -> dict:
    """Load a meadow-tier shard from
    ``datasets/<family>/_meadow/<source>/<vintage>/<file>``.

    Meadow tier per ADR-0041: typed, schema-validated, deterministic,
    `source_id`-bearing JSON parsed from upstream but pre-canonical.
    Backend-internal — frontend MUST NOT fetch these paths (Phase B
    allowlist routes citizen reads to canonical Parquet).

    Returns the raw parsed JSON; the adapter is responsible for
    transforming ``rows[]`` into ``ObservationRow``. Path is
    explicitly POSIX so the error messages stay portable.

    Args:
        family: indicator family, matches canonical Parquet family name
            (``"energy"``, ``"fiscal"``, ``"demography"``, ...).
        source: short producer identifier, snake_case (``"iced"``,
            ``"rbi"``, ``"cea"``, ...).
        vintage: source's own period label (publisher-native), matches
            the ``vintage`` field of the citation-ledger row in
            ``datasets/data/entities/source.csv`` (Tier-B check lands
            in PR 7c-4).
        file: descriptor with ``.json`` suffix (e.g.
            ``"state_electricity_generation_mu.json"``).
    """
    p = (
        repo_root
        / "datasets"
        / family
        / "_meadow"
        / source
        / vintage
        / file
    )
    return json.loads(p.read_text(encoding="utf-8"))


def load_indicator_catalogue(repo_root: Path) -> dict[str, dict]:
    """Index the 59-row indicator catalogue by ``indicator_id``.

    Used by the FK-closure self-check (`assert_indicator_in_catalogue`)
    so adapters fail fast on a typo before the writer's FK gate runs.
    The writer's gate is the contract; this is the cheap pre-flight.
    """
    p = repo_root / "datasets" / "taxonomy" / "indicators.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {row["indicator_id"]: row for row in doc["indicators"]}

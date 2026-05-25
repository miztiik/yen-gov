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
# FK gate verifies each appears in ``datasets/taxonomy/sources.parquet``
# before observation rows touch disk. If a future PR changes the source
# triple (`producer | title | vintage`) for any of these, the hash will
# rotate and BOTH the catalogue + this constant must update together.
SOURCE_IDS: dict[str, str] = {
    "cea_monthly_ic":                "src-092a5dc7af3f",
    "iced_capacity_metatable":       "src-ba5c6fa6acfe",
    "iced_deep_dive":                "src-be6a6d5d6493",
    "iced_gen_metatable":            "src-b60ed70f19d8",
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
    "iced_distribution_perf":            "src-cead8f51df6f",
    "iced_distribution_rpo":             "src-ca061b1b0adf",
    "rbi_hbk_141_power_requirement":     "src-f7ce9960caba",
    "rbi_hbk_139_power_availability":    "src-97a3c47d092f",
    "rbi_hbk_138_per_capita_availability": "src-9a38005d8713",
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
            ``datasets/taxonomy/sources.parquet`` (Tier-B check lands
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

"""Demand & supply envelope — ``energy_demand_supply.parquet``.

P.1.A (3 indicators) + P.1.B (3 indicators) = 6 lifted indicators.

P.1.A — Lifts 3 legacy RBI/ICED shards + 1 inline FY25 ICED snapshot:

* ``state_peak_demand_mw.json`` (396 RBI Table 142 rows)
  → ``peak-electricity-demand-mw`` (FY13–FY24).
* ``state_peak_met_mw.json`` (396 RBI Table 142 companion rows)
  → ``peak-electricity-supplied-mw`` (FY13–FY24).
* ``state_per_capita_electricity_consumption_kwh.json`` (555 ICED rows)
  → ``per-capita-electricity-consumption-kwh``.
* ``_FY25_PEAK_DEMAND_ROWS`` literal (34 rows inc. IN national
  aggregate) → ``peak-electricity-demand-mw`` (FY25 extension).

The two RBI rows form a citizen-readable pair: peak DEMAND is the
instant the State Load Despatch Centre saw the highest simultaneous
load; peak SUPPLIED (a.k.a. "peak met") is how much of that demand was
actually served. The gap is the unmet peak.

P.1.B — Lifts 3 additional legacy RBI Handbook shards (annual energy
requirement + availability + per-capita availability):

* ``state_power_requirement_mu.json`` (RBI Table 141 rows) →
  ``electricity-requirement-mu``.
* ``state_power_availability_mu.json`` (RBI Table 139 rows) →
  ``electricity-availability-mu``.
* ``state_per_capita_availability_kwh.json`` (RBI Table 138 rows) →
  ``per-capita-electricity-availability-kwh``.

Requirement minus Availability is the energy-not-supplied deficit (the
"power deficit %" India tracked closely through the 2000s). Per-capita
availability is the citizen-relevant proxy for "how much power do
people in this state actually get to use".

RBI Handbook Table 142 is the gold authority for FY13–FY24 (Hans D33).
ICED is gold ONLY for FY25 where RBI has no row. The mixed source_id
on the same indicator column is contract-clean per writer D7:
``source_id`` is a per-row column NOT in the dedup key, so RBI rows
(FY13–FY24) coexist with ICED rows (FY25) on the same
``(entity_id, year, period_label, indicator_id)`` key space without
UPSERT conflict.

C4.7 Phase C (this PR): the FY25 lift block no longer calls
``load_shard("state_electricity_peak_demand_mw.json")``. The 34 FY25
observations are inlined as the ``_FY25_PEAK_DEMAND_ROWS`` literal
below. Reasons:

  * Determinism: the lift is fully self-contained — no dependency on
    ``.runtime/raw/iced/`` (gitignored per CLAUDE.md §2; cannot be
    referenced from committed code) and no network I/O at lift time
    (would kill CI / fresh-checkout reproducibility per CLAUDE.md
    Holy Law re-run byte-identical).
  * Bootstrap-safe: re-runs from a fresh repo produce the same Parquet
    without requiring any prior on-disk state.
  * Strangler-fig closure: Phase D ``git rm`` of the two legacy shards
    (`state_electricity_peak_demand_mw.json` +
    `state_peak_electricity_demand_mw.json`) will not touch this
    block — the lift is already cut over.

The four-phase strangler-fig retirement of these shards is now:
Phase A (PR #119 — additive FY25 on canonical via shard fetch),
Phase B (PR #171 — frontend ``IndicatorCard`` reader-switch to
canonical Parquet via DuckDB-WASM allowlist seam), Phase C (this PR —
backend lift drops the shard dependency), Phase D (``git rm`` shards
+ scrub ``datasets/_ops/meadow-shard-contract.txt`` lines 79
+ 87 + drop docs rows). See plan-doc §3 C4.7 for the descope
narrative and the four-phase rollout.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import SOURCE_IDS, load_meadow, parse_iso_period, to_entity_id


# Per ADR-0041, the 5 RBI Handbook power shards (Tables 138/139/141/142)
# live at `datasets/energy/_meadow/rbi/2024-25/<file>.json`; the 1
# legacy ICED shard (`state_per_capita_electricity_consumption_kwh`)
# lives at `datasets/energy/_meadow/iced/2024-25/<file>.json`.
def _load_rbi_meadow(repo_root: Path, file: str) -> dict:
    return load_meadow(repo_root, "energy", "rbi", "2024-25", file)


def _load_iced_meadow(repo_root: Path, file: str) -> dict:
    return load_meadow(repo_root, "energy", "iced", "2024-25", file)


# FY25 peak electricity demand by state — 34 rows: IN national
# aggregate + 33 states/UTs.
#
# Provenance: NITI Aayog ICED state-wise deep-dive endpoint
# (https://iced.niti.gov.in/analytics/state-wise-deep-dive), payload
# originally fetched 2026-05-14 by ``backend/yen_gov/sources/
# iced_state_wise/ingest.py``. Values are byte-identical to the
# 34 FY25 cells published in the shard
# ``datasets/indicators/in/energy/state_electricity_peak_demand_mw.json``
# at the time of Phase A (PR #119). source_id below FK-targets the
# citation ledger row ``src-bb1d7bec8b34`` (ICED Deep Dive) — same
# row Phase A used; hash rotated under ADR-0042 (source schema v3.0)
# when ICED vintage flipped from "" → "2024-25".
#
# Tuple shape: ``(entity_code, time_label, value_mw)`` where
# ``entity_code`` is the legacy-shard form (``"IN"`` or ``"S07"`` etc;
# the loop applies ``to_entity_id`` to add the ``IN-`` prefix). The
# tuple is sorted by entity_code so the emitted parquet's row order
# stays stable across Python dict-iteration changes (defensive — the
# writer sorts by ``(indicator_id, entity_id, year, period_seq)``
# anyway, but sorting here keeps blame diffs minimal when FY26 lands).
#
# To extend coverage when FY26 publishes (typically May–Jun of FY27):
#   1. Refresh the upstream snapshot:
#        ``python -m yen_gov iced-ingest`` (writes the encrypted
#        body to ``.runtime/raw/iced/stateWiseDeepDive_2026-27.json``
#        — gitignored).
#   2. Decrypt and locate the ``Peak Demand`` rows for time
#      ``"2026-04"``.
#   3. Append 34 ``(entity_code, "2026-04", value)`` rows to this
#      tuple below the existing FY25 block.
# The lift iterates the tuple verbatim; no other code change is
# required. (Updating the docstring + the FY25/FY26 boundary in the
# block-4 comment is a small follow-up, not a structural change.)
_FY25_PEAK_DEMAND_ROWS: tuple[tuple[str, str, float], ...] = (
    ("IN",  "2025-04", 245416.0),
    ("S01", "2025-04",  14011.0),
    ("S02", "2025-04",    228.0),
    ("S03", "2025-04",   2814.0),
    ("S04", "2025-04",   8741.0),
    ("S05", "2025-04",    864.0),
    ("S06", "2025-04",  26457.0),
    ("S07", "2025-04",  13998.0),
    ("S08", "2025-04",   2302.0),
    ("S10", "2025-04",  18655.0),
    ("S11", "2025-04",   5861.0),
    ("S12", "2025-04",  19895.0),
    ("S13", "2025-04",  32419.0),
    ("S14", "2025-04",    280.0),
    ("S15", "2025-04",    397.0),
    ("S16", "2025-04",    218.0),
    ("S17", "2025-04",    210.0),
    ("S18", "2025-04",   7302.0),
    ("S19", "2025-04",  17171.0),
    ("S20", "2025-04",  19282.0),
    ("S21", "2025-04",    125.0),
    ("S22", "2025-04",  20211.0),
    ("S23", "2025-04",   3281.0),
    ("S24", "2025-04",  30632.0),
    ("S25", "2025-04",  13108.0),
    ("S26", "2025-04",   6798.0),
    ("S27", "2025-04",   2406.0),
    ("S28", "2025-04",   2910.0),
    ("S29", "2025-04",  18548.0),
    ("U02", "2025-04",    460.0),
    ("U03", "2025-04",   1416.0),
    ("U05", "2025-04",   8408.0),
    ("U07", "2025-04",    548.0),
    ("U08", "2025-04",   5050.0),
)


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    # 1. state_peak_demand_mw.json → peak-electricity-demand-mw
    shard = _load_rbi_meadow(repo_root, "state_peak_demand_mw.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="peak-electricity-demand-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_142_peak_demand"],
            derivation="raw",
        ))

    # 2. state_peak_met_mw.json → peak-electricity-supplied-mw
    shard = _load_rbi_meadow(repo_root, "state_peak_met_mw.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="peak-electricity-supplied-mw",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_142_peak_met"],
            derivation="raw",
        ))

    # 3. state_per_capita_electricity_consumption_kwh.json
    shard = _load_iced_meadow(repo_root, "state_per_capita_electricity_consumption_kwh.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="per-capita-electricity-consumption-kwh",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    # 4. FY25 extension of peak-electricity-demand-mw (Phase C).
    # Reads the inline ``_FY25_PEAK_DEMAND_ROWS`` literal — no shard
    # dependency. RBI rows above cover FY13-FY24 (gold per Hans D33);
    # this block extends coverage by one year with ICED as the gold
    # source for FY25. See the constant's docstring for the refresh
    # procedure when FY26 publishes.
    for entity_code, time_value, value in _FY25_PEAK_DEMAND_ROWS:
        period_label, year, period_seq = parse_iso_period(time_value)
        rows.append(ObservationRow(
            entity_id=to_entity_id(entity_code),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="peak-electricity-demand-mw",
            value_numeric=float(value),
            source_id=SOURCE_IDS["iced_deep_dive"],
            derivation="raw",
        ))

    # 5. P.1.B — state_power_requirement_mu.json → electricity-requirement-mu
    #    RBI Handbook Table 141 (long-arc state-wise annual energy
    #    requirement, MU = GWh; CEA-originated).
    shard = _load_rbi_meadow(repo_root, "state_power_requirement_mu.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="electricity-requirement-mu",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_141_power_requirement"],
            derivation="raw",
        ))

    # 6. P.1.B — state_power_availability_mu.json → electricity-availability-mu
    #    RBI Handbook Table 139 (long-arc state-wise annual energy
    #    availability, MU = GWh; CEA-originated). Companion to T141 above.
    shard = _load_rbi_meadow(repo_root, "state_power_availability_mu.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="electricity-availability-mu",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_139_power_availability"],
            derivation="raw",
        ))

    # 7. P.1.B — state_per_capita_availability_kwh.json →
    #    per-capita-electricity-availability-kwh
    #    RBI Handbook Table 138 (state-wise per-capita electricity
    #    availability, kWh/year; CEA-originated; Census 2011-projection
    #    denominator).
    shard = _load_rbi_meadow(repo_root, "state_per_capita_availability_kwh.json")
    for r in shard["rows"]:
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id="per-capita-electricity-availability-kwh",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["rbi_hbk_138_per_capita_availability"],
            derivation="raw",
        ))

    # PR-W (2026-05-26): state_power_purchase_share_pct.json -> 12-source
    # procurement-mix children. Passthrough; no sub-fuel collapse
    # (procurement share is a %, can't be summed across sources).
    _append_power_purchase_share_rows(repo_root, rows)

    # PR-X (2026-05-26): national_final_energy_consumption_by_sector_mtoe.json
    # -> 18 (sector x fuel) compound children. National-only (entity_id=IN).
    # Publisher facet "agriculture | oil" -> canonical pair-id "agriculture-oil".
    _append_final_energy_consumption_rows(repo_root, rows)

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_demand_supply",
        observation_rows=rows,
    )


# PR-W (2026-05-26): publisher power-purchase source label -> canonical
# fuel_type axis value. 1:1 mapping (NO SUB_FUEL_TO_CANONICAL renewable
# collapse -- procurement share is a %, summing across sources is
# meaningless). 10 publisher buckets resolve to existing axis values;
# 2 (hybrid-bundled + trading-and-others) resolve to NEW value_ids
# (hybrid_bundled + trading_other) added in this PR.
_POWER_PURCHASE_PUBLISHER_TO_CANONICAL: dict[str, str] = {
    "bio-power":           "biomass",
    "coal":                "coal",
    "diesel":              "diesel",
    "hybrid-bundled":      "hybrid-bundled",   # kebab indicator-id suffix; axis dim val is snake `hybrid_bundled`
    "hydro":               "hydro",
    "nuclear":             "nuclear",
    "oil-gas":             "gas",
    "other-res":           "renewable-other",  # kebab indicator-id suffix; axis dim val is snake `renewable_other`
    "small-hydro":         "small-hydro",      # kebab indicator-id suffix; axis dim val is snake `small_hydro`
    "solar":               "solar",
    "trading-and-others":  "trading-other",    # kebab indicator-id suffix; axis dim val is snake `trading_other`
    "wind":                "wind",
}


def _append_power_purchase_share_rows(
    repo_root: Path, rows: list[ObservationRow]
) -> None:
    """Lift state_power_purchase_share_pct.json (PR-W) into the
    demand_supply parquet. Each (state, FY, source) row passes through
    unchanged as a child indicator; the parent
    ``power-purchase-share-pct`` carries zero rows (catalogue /
    facet-picker only).
    """
    shard = _load_iced_meadow(repo_root, "state_power_purchase_share_pct.json")
    for r in shard["rows"]:
        canonical_suffix = _POWER_PURCHASE_PUBLISHER_TO_CANONICAL.get(r["facet"])
        if canonical_suffix is None:
            # Defensive: today's dict covers 100% of publisher labels
            # (12/12); this guard catches publisher relabels.
            continue
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"power-purchase-share-pct-{canonical_suffix}",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_power_purchase_share"],
            derivation="raw",
        ))


# PR-X (2026-05-26): publisher (sector | fuel) compound facet ->
# canonical sector_fuel_pair axis value. Publisher emits 18 sparse pairs
# out of the 6 sectors x 5 fuels Cartesian product (many cells are
# structurally zero, e.g. residential coal). The lift sanitises the
# publisher's "sector | fuel" string into a kebab indicator-id suffix
# `{sector}-{fuel}` -- e.g. "agriculture | oil" -> "agriculture-oil".
def _publisher_sector_fuel_to_canonical(facet: str) -> str | None:
    """Convert publisher 'sector | fuel' string to canonical kebab pair-id
    `{sector}-{fuel}`. Returns None for unrecognised facets (defensive)."""
    if " | " not in facet:
        return None
    sector, fuel = (s.strip() for s in facet.split(" | ", 1))
    return f"{sector}-{fuel}"


_FINAL_ENERGY_EXPECTED_PAIRS: frozenset[str] = frozenset({
    "agriculture-electricity", "agriculture-gas", "agriculture-oil",
    "cgd-and-others-gas",
    "commercial-electricity", "commercial-oil",
    "industry-coal", "industry-electricity", "industry-gas", "industry-oil",
    "non-energy-gas", "non-energy-oil",
    "other-electricity", "other-oil",
    "residential-electricity", "residential-oil",
    "transport-electricity", "transport-oil",
})


def _append_final_energy_consumption_rows(
    repo_root: Path, rows: list[ObservationRow]
) -> None:
    """Lift national_final_energy_consumption_by_sector_mtoe.json (PR-X)
    into the demand_supply parquet. Each (FY, sector x fuel) row passes
    through unchanged as a child indicator; the parent
    ``india-final-energy-consumption-mtoe`` carries zero rows (catalogue
    / facet-picker only)."""
    shard = _load_iced_meadow(
        repo_root, "national_final_energy_consumption_by_sector_mtoe.json",
    )
    for r in shard["rows"]:
        pair = _publisher_sector_fuel_to_canonical(r["facet"])
        if pair is None or pair not in _FINAL_ENERGY_EXPECTED_PAIRS:
            # Defensive: today the dict covers 100% of publisher pairs
            # (18/18); this guard catches publisher schema drift.
            continue
        period_label, year, period_seq = parse_iso_period(r["time"])
        rows.append(ObservationRow(
            entity_id=to_entity_id(r["entity_id"]),
            year=year,
            period_label=period_label,
            period_seq=period_seq,
            indicator_id=f"india-final-energy-consumption-mtoe-{pair}",
            value_numeric=float(r["value"]),
            source_id=SOURCE_IDS["iced_final_energy_consumption"],
            derivation="raw",
        ))

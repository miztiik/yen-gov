# Long-coverage indicator backlog

**Last Updated**: 2026-05-13
**See also**: [data-provenance](data-provenance.md), [dataset-shapes](dataset-shapes.md), [Holy Law #4](../../CLAUDE.md), per-source docs under [`docs/architecture/backend/`](../architecture/backend/)

This is the **resumability ledger** for the citizen-facing indicator expansion. If work pauses for any reason, this doc plus the per-source subsystem docs are sufficient to resume without rediscovery.

## Goal

Ship socio-economic indicators with **as much historical coverage as the source publishes** — typically 15–35 years — across the topics citizens actually ask about: fiscal flows, energy, GDP, debt, FDI, crime, health, education. Per-state where authoritative; national where state-level isn't published.

## Working policy (user-set)

- **Easy data first**: download → process → store. PDFs are last resort.
- **One indicator family per cycle**: ship, document, commit, push, then move to the next.
- **Authoritative sources only**: government publications (RBI, MoSPI, CEA, Finance Commission, ECI, NCRB, MoE, RHS) or established mirrors (Sansad, OGD).
- **No mocks, no synthetic data** (Holy Law #7).
- **Provenance mandatory** ([§12](../../CLAUDE.md)) — every artifact cites the URL fetched and the timestamp.

## Status legend

| Symbol | Meaning |
| --- | --- |
| ✅ | Shipped — artifact present under `datasets/`, validate clean, in catalogue |
| 🔄 | Cached + adapter scaffolding done; specs pending |
| 📥 | Source identified, not yet fetched |
| 🔍 | Source recon needed |
| 🚫 | Blocked (PDF-only, gated, captcha-fail, etc.) |

## Shipped (chronological)

| Indicator | Topic | Coverage | Source | Adapter | Doc |
| --- | --- | --- | --- | --- | --- |
| `fiscal/outstanding_debt_pct_gsdp` | fiscal | FY24A + FY25RE + FY26BE per state | RBI State Finances Statement 20 | [`rbi_xlsx`](../architecture/backend/sources-rbi.md) | sources-rbi.md |
| `fiscal/net_transfers_from_centre` | fiscal | FY24A + FY25RE + FY26BE per state | RBI State Finances Statement 17 | [`rbi_xlsx`](../architecture/backend/sources-rbi.md) | sources-rbi.md |
| `fiscal/centre_transfers_gross` | fiscal | FY17–FY23 per state (196 rows) | data.gov.in OGD CSV (Rajya Sabha tabled) | [`datagovin_ogd`](../../../backend/yen_gov/sources/datagovin_ogd/) | (in code header) |
| `fiscal/national_centre_transfers_total` | fiscal | FY08–FY26 (19y, all-India) | RBI State Finances Appendix Table 2, Item VI | [`rbi_appendix_national`](../architecture/backend/sources-rbi-appendix-national.md) | sources-rbi-appendix-national.md |
| `fiscal/national_devolution_central_taxes` | fiscal | FY08–FY26 (19y, all-India) | RBI App T2 Item I | `rbi_appendix_national` | sources-rbi-appendix-national.md |
| `fiscal/national_grants_from_centre` | fiscal | FY08–FY26 (19y, all-India) | RBI App T2 Item II | `rbi_appendix_national` | sources-rbi-appendix-national.md |
| `fiscal/national_gross_transfers` | fiscal | FY08–FY26 (19y, all-India) | RBI App T2 Item IV | `rbi_appendix_national` | sources-rbi-appendix-national.md |
| `energy/installed_mw_by_state` | energy | 2019, 4 states (TN/KL/AS/WB) | Wikipedia geodata | `india_geodata_power_plants` | Legacy stub. Superseded by `energy/installed_capacity_*_mw` (CEA family) for new UI consumers; kept for back-compat. |
| `energy/installed_capacity_total_mw` | energy | snapshot 2026-03; 35 states/UTs | CEA monthly Executive Summary (As on 31.03.2026) | [`cea_installed_capacity`](../architecture/backend/sources-cea-installed-capacity.md) | sources-cea-installed-capacity.md |
| `energy/installed_capacity_thermal_mw` | energy | snapshot 2026-03; 35 states/UTs | CEA monthly Executive Summary | `cea_installed_capacity` | Coal+lignite+gas+diesel rollup. |
| `energy/installed_capacity_coal_mw` | energy | snapshot 2026-03; 35 states/UTs | CEA monthly Executive Summary | `cea_installed_capacity` | Largest single fuel mode. |
| `energy/installed_capacity_gas_mw` | energy | snapshot 2026-03; 35 states/UTs | CEA monthly Executive Summary | `cea_installed_capacity` | |
| `energy/installed_capacity_nuclear_mw` | energy | snapshot 2026-03; 35 states/UTs | CEA monthly Executive Summary | `cea_installed_capacity` | Per-state only — central-unallocated nuclear (~1,230 MW) dropped. |
| `energy/installed_capacity_hydro_mw` | energy | snapshot 2026-03; 35 states/UTs | CEA monthly Executive Summary | `cea_installed_capacity` | Large hydro only; small hydro counts in renewable. |
| `energy/installed_capacity_renewable_mw` | energy | snapshot 2026-03; 35 states/UTs | CEA monthly Executive Summary | `cea_installed_capacity` | Hydro + RES-MNRE (solar/wind/biomass/small-hydro). |

## Wave 3 — In-progress / next

Each row is a single ship cycle: recon → download → adapter → tests → validate → smoke → commit → push.

| # | Indicator | Topic | Target coverage | Source | Status | Notes |
| - | --------- | ----- | --------------- | ------ | ------ | ----- |
| 1 | `energy/installed_capacity_*_mw` (7 indicators) | energy | snapshot 2026-03; 35 states/UTs × 7 fuel categories | CEA monthly Executive Summary (`cea.nic.in`) | ✅ shipped | Replaced 4-state Wikipedia stub. Single-snapshot artifact: per-state, per-fuel as of 2026-03. CEA's natural per-state grain is monthly snapshots — there is no per-state historical time-series workbook upstream; building one would mean fetching ~360 monthly workbooks (30y) and stitching, gated by a current-month-only WordPress URL pattern + intermittent CDN rejection of scripted UAs. Deferred until a tractable archive index exists. The all-India long-history macro analogue lives in RBI Handbook of Statistics (rows #5–#6 below). See [sources-cea-installed-capacity.md](../architecture/backend/sources-cea-installed-capacity.md). |
| 2 | `fiscal/national_gross_fiscal_deficit` | fiscal | FY08–FY26 (20y, all-India incl. RE/BE) | RBI AppT1 Major Deficit Indicators | ✅ shipped | Two-row-per-year layout (₹ Crore + % GDP interleaved); rows=year/cols=indicator (transpose of App T2). New sibling adapter `rbi_appendix_deficits`. See [sources-rbi-appendix-deficits.md](../architecture/backend/sources-rbi-appendix-deficits.md). |
| 3 | `fiscal/national_revenue_deficit` | fiscal | FY08–FY26 (20y, all-India) | RBI AppT1 | ✅ shipped | Same workbook as #2; co-shipped. |
| 4 | `fiscal/national_primary_deficit` | fiscal | FY08–FY26 (20y, all-India) | RBI AppT1 | ✅ shipped | Same workbook as #2; co-shipped. Bonus #4b: `fiscal/national_primary_revenue_deficit` co-shipped from column 5 of the same workbook — the strictest fiscal-discipline indicator (interest-stripped revenue balance). |
| 5 | `economy/national_gdp_constant_2011_12` | economy | FY12–present (~14y at constant prices) | RBI Handbook of Statistics on Indian Economy / MoSPI | 📥 to fetch | Long series available from RBI Handbook (also has current-price GDP back to FY51). |
| 6 | `economy/national_gdp_current_prices` | economy | FY51–present (75+ years possible) | RBI Handbook | 📥 to fetch | Caveat: nominal series across 75y is not directly comparable; useful for absolute-scale framing only. |
| 7 | `education/aishe_higher_ed_institutions_by_state` | education | ~FY12–present per state (13y) | AISHE / MoE (`aishe.gov.in/aishe/aisheReport`) | 🔍 recon | Direct download likely; per-state counts of universities, colleges, standalone institutions. |
| 8 | `economy/state_gsdp_constant_prices` | economy | per state, FY12–present | MoSPI / RBI Handbook | 📥 to fetch | Per-state GSDP series. Per-capita variant requires population denominator. |
| 9 | `economy/state_per_capita_gsdp` | economy | per state, FY12–present | MoSPI (derived) | 📥 to fetch | Composes #8 with state population. |
| 10 | `economy/national_external_debt` | economy | quarterly, ~25y available | RBI weekly statistical supplement / Status Report | 📥 to fetch | RBI publishes Status Report on External Debt half-yearly; also in RBI Handbook. |
| 11 | `economy/national_fdi_inflows` | economy | sector-wise + (where possible) state-wise | DPIIT Fact Sheet (PDF) | 🚫 PDF-only | OGD has only sector-wise manufacturing FDI. State-wise DPIIT data is PDF-only Fact Sheets. Deferred per "PDF as last option" policy. |
| 12 | `crime/state_ipc_total` | crime | per state, ~20y from NCRB | NCRB *Crime in India* | 🚫 PDF-only | NCRB ships annual reports as PDF; tables are available but require PDF table extraction. Deferred. |
| 13 | `health/rural_hospital_beds_by_state` | health | per state, ~10y | Rural Health Statistics (MoHFW) | 🚫 PDF-only | RHS is published as PDF. Deferred. |
| 14 | `economy/national_gold_reserves` | economy | monthly, 35+ years | RBI Weekly Statistical Supplement / Handbook | 📥 to fetch | Long series in Handbook of Statistics. |
| 15 | `fiscal/state_outstanding_debt_long_series` | fiscal | per state, multi-edition stitching | RBI State Finances Statement 8 (one per edition; ~3y per file) | 📥 to fetch | Requires scraping prior editions of the State Finances publication and stitching FY-by-FY across them. Higher complexity. |

## Pause/resume checklist

If work pauses:

1. **State of the tree**: `git log --oneline -10` shows the last shipped commit; the table above mirrors it.
2. **Cached sources**: `dir .runtime\raw\` (Windows) — every file there is potentially reusable; the matching subsystem doc lists the operator recipe.
3. **Pending UI work**: any `🔄 cached` row above is one parser-spec away from shipping.
4. **Unblocking PDFs**: PDF-only rows (`🚫`) are deferred. To unblock, see [Phase X — PDF parsing] (not yet authored; will sit at `docs/how-to/pdf-extraction.md` when needed).

## Conventions worth re-reading before resuming

- **Provenance**: every emitted artifact's `sources` array cites every URL the pipeline read ([§12](../../CLAUDE.md)).
- **Schema versioning**: `x-version` bumps require an `x-changelog` entry in the same commit ([§11](../../CLAUDE.md)).
- **Path rules**: relative POSIX paths in any persisted/transmitted data ([§2](../../CLAUDE.md)).
- **National convention** (introduced 2026-05-13): `entity_id="IN"`, `entity_kind="country"`, `coverage.admin_level="national"`. The schema's `entity_kind` enum already supported `country` — no schema change was needed.
- **Inflation caveat**: nominal ₹ series spanning >5 years should carry a `notes` warning that values are not deflated.
- **No mocks** ([§7](../../CLAUDE.md)) except `fetch` in loader unit tests.

## Decisions log (this expansion only)

- **2026-05-12** Captcha-driven CSV downloads from data.gov.in OGD are the portable path; the JSON API requires a registered key (SMS-OTP) and rate-limits the demo key. → adapter is CSV-cache-only.
- **2026-05-13** Country-entity national series ship as separate artifacts rather than being mixed with state rows in existing per-state files. Reason: schema's `entity_kind` is per-artifact, not per-row; mixing entity kinds in one file would weaken the contract.
- **2026-05-13** Two parsers in the `rbi_*` family by intent — per-state-wide (`rbi_xlsx`) and national-time-series (`rbi_appendix_national`). Folding them would require a layout-mode flag inside every helper. Two modules, one each, costs nothing.
- **2026-05-13** Same logic applied to a third RBI appendix shape: AppT1 (Major Deficit Indicators) is rows=year + cols=indicator, the transpose of App T2's row=item layout, with %GDP interleaved on alternating rows. It got its own sibling module `rbi_appendix_deficits` rather than a layout-flag matrix on the existing `AppendixSpec`. The bar for a new sibling is "different walking algorithm" (not "different RBI publication").
- **2026-05-13** Per-state long-history capacity is bounded by what the **publisher** publishes, not by what we choose to ingest. CEA's per-state granularity exists only as monthly snapshots — there is no canonical per-state time-series workbook upstream. "As much history as the source naturally provides" therefore = one snapshot per state for the per-state slice; the long-history macro slice belongs to the RBI Handbook all-India series (Wave 3 #5–#6). The user-stated "~35y target" applies per-source-natural-grain, not per-indicator-id.

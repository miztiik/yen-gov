# Triage: `datasets/ephemeral_datasets/` — 2026-05-14

**Status**: Recon only. No ingest until each row is greenlit. Per CLAUDE.md §12, every emitted artifact needs a real `sources[].url` — most files below arrived without one and cannot ship as-is.

## Legend

- **Action**:
  - `INGEST` — clear fit, source identifiable, fills a real gap.
  - `MERGE` — content overlaps an existing artifact; only the delta (new years, new fields) is worth lifting.
  - `SKIP-DUP` — already covered by an existing indicator; no new info.
  - `SKIP-PROV` — content is fine but provenance can't be reconstructed from the filename alone — needs your input before ingest.
  - `DELETE` — junk / unrelated to project.
  - `BLOCKED` — file unreadable or under-described.
- **Gap** — what's missing in the file itself (year, units, geography, source URL).

## Inventory & classification

| # | File | Shape | Likely upstream | Existing yen-gov coverage | Action | Gap to fill before ingest |
|---|---|---|---|---|---|---|
| 1 | `20_ST2301202696AC652FC4CE482EAAD928FC544CD86A.XLSX` | RBI Statement 20 — total outstanding liabilities (% GSDP), 38 states × ~21 years | RBI *State Finances: A Study of Budgets* | **YES** — `fiscal/outstanding_debt_pct_gsdp.json` (already ingested via `backend/yen_gov/sources/rbi_state_finances`) | `SKIP-DUP` | — |
| 2 | `33-Constituency-Wise-Detailed-Result.xls` | ECI per-AC results, 2.7 MB | ECI Statistical Report (Form-20-ish) | depends on state/year | `BLOCKED` | File is **corrupted** (BIFF stream truncated). Also no state/year in filename. Need re-download + you to tell me which election. |
| 3 | `All_Districtof_India_2026-05-14_00-35-59.xlsx` | 786 districts × {state, district code, census 2001, census 2011} | LGD portal export | **YES** — `datasets/reference/in/lgd/` already holds an LGD snapshot | `MERGE` if newer than existing | Compare snapshot date vs. existing LGD ingest; only worth re-snapshotting if district count changed. |
| 4 | `All_Stateof_India_2026-05-14_00-30-52.xlsx` | 38 states × LGD codes + Census codes | LGD portal export | **YES** — same | `SKIP-DUP` | — |
| 5 | `Electrical Vehicle Trend_1778529830995.xlsx` | **10 925 rows** — year × state × vehicle category × EV count + share | NITI ICED dashboard ("State Wise Deep Dive"), originally VAHAN | **NO** — no transport indicators yet | `INGEST` ⭐ | Need ICED page URL + `fetched_at` for `sources[]`. New category `transport/` and 1–2 indicators (`ev_share_total_registrations_pct`, `ev_registrations_count`). |
| 6 | `Electricity_Generation_1778523697714.xlsx` | 210 rows: source × state × generation MU + energy met | ICED state-wise deep dive | **YES** — `energy/state_electricity_generation_mu.json` | `SKIP-DUP` | — |
| 7 | `Financial_Health_Chennai_2014_to_2018_RsCrore_1.csv` | Chennai municipal P&L 2014–18, 4 rows | Likely a Lok/Rajya Sabha question; possibly CAG ULB study | **NO** — no urban-local-body fiscal data | `SKIP-PROV` | One city, 4 years is too narrow to justify a `governments/<city>/` SQLite by itself. Park until we have ≥10 cities, then ingest as a urban-fiscal slice. |
| 8 | `HDI_1778524667840.xlsx` | 42 rows: state → HDI value, **no year** | Most likely UNDP / Global Data Lab subnational HDI; possibly NITI | partial — no HDI artifact yet | `SKIP-PROV` ⚠ | (a) Year unknown; (b) Niti composite indices are off-roadmap (architecture cheatsheet line 41); (c) UNDP/GDL HDI is OK but needs the year + URL. Would land under `human_development/` once provenance confirmed. |
| 9 | `LGD - Local Government Directory, Government of India.xlsx` | — | LGD | — | `BLOCKED` | openpyxl can't parse (`expected Fill`). Re-export as CSV from LGD portal. |
| 10 | `Merged_Annually_Quarterly.csv` (and 2 byte-identical dups) | National GVA / GFCF / etc., annual + quarterly, by industry × institutional sector × base year (2011-12 & 2022-23 series), ~7 800 rows | MOSPI National Accounts Statistics (Press Notes) | **NO** — currently only state-level GDP; no national NAS series, no quarterly | `INGEST` ⭐ | Need MOSPI press-note URL + release date. Lands as `economy/national_gva_by_industry_inr_crore.json` (annual) + a quarterly sibling. **Delete the two `(1)`/`(2)` duplicates.** |
| 11 | `Per Capita GP vs Consumption 2012-13.xlsx` … `2023-24.xlsx` (12 files) | state × {kWh consumption, GSDP current ₹cr, population, GSDP per capita ₹cr} | ICED dashboard (composed view) | partial — `economy/state_gdp_current_inr_lakh_crore.json` and `demography/state_population_lakhs.json` exist; per-capita kWh does not | `MERGE` (consumption only) | The GSDP and population columns duplicate existing artifacts. Only the **per-capita electricity consumption (kWh)** column is new — and even that is partly redundant with `state_electricity_sales_mu / population`. Lift only as `energy/state_per_capita_electricity_consumption_kwh.json`. Need ICED URL. |
| 12 | `Per_Capita_Consumption_1778524659090.xlsx` | All-India per-capita kWh, 2009-10 → 2024-25 (~641 rows incl. states) | ICED | partial | `MERGE` with row 11 above. Same indicator, longer time series. Prefer this file as primary. |
| 13 | `Per_Capita_Income_1778524567473.xlsx` (and `..687923.xlsx`, byte-identical dup) | state × year × {current, constant} × ₹ per capita NSDP, 2004-05 → 2023-24 | MOSPI / RBI Handbook of Statistics on Indian States | **NO** — no per-capita income artifact yet (we have state GDP, not NSDP per capita) | `INGEST` ⭐ | Need MOSPI Statement URL or RBI Handbook table URL. Lands as `economy/state_per_capita_nsdp_current_inr.json` + `..._constant_2011_12_inr.json`. **Delete the `687923` duplicate.** |
| 14 | `Primary_Energy_1778523620422.xlsx` | National primary energy supply by source × year (mtoe) | ICED (sourced from MoSPI Energy Statistics / IEA) | **NO** — only have *electricity* indicators, not whole-economy primary energy | `INGEST` | Need ICED URL + the underlying MoSPI release. Lands as `energy/national_primary_energy_supply_mtoe.json`. |
| 15 | `Region and Zone Constraint Table.xlsx` | "MS CONFIDENTIAL — Azure capacity restrictions" | **Microsoft internal** — not Indian government data | n/a | `DELETE` | Has nothing to do with yen-gov. Likely landed in this folder by mistake. |
| 16 | `Renewable energy Installed and Potential Capacity.xlsx` | All-India installed vs potential, by source (Hydro/Wind/Solar/...) — 15 rows | MNRE / CEA | partial — we have state-level installed capacity; no *potential* | `INGEST` (small) | Single national snapshot; useful as a context indicator (`energy/national_renewable_potential_vs_installed_mw.json`). Need MNRE URL + as-of date. |
| 17 | `RS_Session_259_AU_1480_1.csv` | State × external debts (₹ cr), 28 rows, **no year** | Rajya Sabha unstarred question 1480, Session 259 | partial — RBI gives total liabilities, not the external sub-component | `SKIP-PROV` | Year missing in payload (Session 259 ≈ 2023, but the as-of date inside the answer matters). Need to fetch the actual RS PDF to recover the date and put it in `sources[]`. |
| 18 | `RS_Session_260_AU_1323_1.csv` | State × FY (2016-17 → 2022-23) × {own tax, non-tax, share central taxes, grants-in-aid, total revenue receipts, capex, revenue expenditure, …} | Rajya Sabha unstarred question 1323, Session 260 | partial — RBI State Finances has aggregates; this has the **disaggregated own-tax / non-tax / share / grants quadrant per FY** which we currently lack | `INGEST` ⭐ | Need RS question PDF URL. Lands as 4 fiscal indicators: `fiscal/state_own_tax_revenue_inr_crore.json`, `fiscal/state_non_tax_revenue_inr_crore.json`, `fiscal/state_share_central_taxes_inr_crore.json`, `fiscal/state_grants_in_aid_inr_crore.json`. Big win for cross-state comparison. |
| 19 | `Sectorwise Energy Consumption_1778524428158.xlsx` | National energy consumption by source × sector × year (mtoe), 365 rows | ICED → MoSPI Energy Statistics | **NO** | `INGEST` | Need ICED URL. Lands as `energy/national_final_energy_consumption_by_sector_mtoe.json`. |
| 20 | `State Wise Deep Dive 2024-25.xlsx` | 5-state pivot snapshot (AP/HR/PB/RJ + India) across electricity, allocated capacity, economy, climate | ICED export | **YES** for everything except Climate (PM/SO2 — all "N.A.") | `SKIP-DUP` | Climate columns are empty so no enrichment value. |
| 21 | `State_GDP_Map_1778524742030.xlsx` | state × year × {current, constant} × GSDP ₹ lakh crore | ICED (sourced from MoSPI) | **YES** — `economy/state_gdp_current_inr_lakh_crore.json` + `_constant_2011_12_inr_lakh_crore.json` | `SKIP-DUP` | Verify time-series end date matches ours; if newer, refresh the existing artifact rather than create a new one. |
| 22 | `State_GDP_Trends_1778524722675.xlsx` | Same as #21 + a `National_GDP_Trends_Sheet` (national GVA-by-industry, gross/per-capita) | ICED | partial — national GVA breakdown is **NOT** covered yet | `MERGE` | Lift only the `National_GDP_Trends_Sheet` if the same data isn't already in #10 above (likely overlaps — pick one). |

## Summary by action

| Action | Count | Files |
|---|---|---|
| `INGEST` (new artifact) | **6** | EV trend, Merged NAS quarterly, Per-capita NSDP, Primary energy, RE potential, RS-260 fiscal disaggregation |
| `MERGE` (delta only) | 3 | Per Capita GP×12 + Per_Capita_Consumption (one indicator), State_GDP_Trends national sheet, LGD district refresh |
| `SKIP-DUP` | 6 | RBI Stmt 20, Electricity_Generation, States LGD export, Deep Dive 2024-25, State_GDP_Map, State_GDP_Trends state sheet |
| `SKIP-PROV` ⚠ | 4 | Chennai financial health, HDI, RS-259 external debts |
| `BLOCKED` | 2 | ECI .xls (corrupt), LGD .xlsx (corrupt) |
| `DELETE` | 1 | Azure capacity table |
| Duplicates to drop | 3 | `Merged_Annually_Quarterly(1).csv`, `(2).csv`, `Per_Capita_Income_..687923.xlsx` |

## What's missing across the board (the real gap)

1. **Provenance.** Not a single file in `ephemeral_datasets/` carries a source URL + fetched_at. CLAUDE.md §12 makes this non-negotiable for anything emitted under `datasets/`. For each `INGEST` row above I need either:
   - the ICED dashboard URL you exported it from (the `_1778…` numeric suffix in the filename is the ICED export-job ID, but the human-facing URL is what goes in `sources[]`), OR
   - the upstream MoSPI / RBI / RS press-note / question PDF URL you can paste.
2. **Year metadata.** HDI (#8) and RS-259 external debts (#17) carry no year column in the payload — without the as-of date we can't slot them into the indicator schema (it requires `time_unit` + per-row `time`).
3. **State/year metadata for ECI .xls.** "33-Constituency-Wise-Detailed-Result" with no state and no year is a black box; need the original ECI URL.
4. **Schema fit for urban-local-body fiscals.** The Chennai file is fine data but yen-gov has no `governments/<city>/` slice yet — that's a new schema to design (Level 3 change), not a one-file ingest.

## Recommended next step

Pick one of:

**A. Confirm the 6 `INGEST` candidates one-by-one** — for each, you give me the source URL and `fetched_at`, I write the parser + schema + tests, validator stays green. Order I'd suggest by impact:
1. **RS-260 fiscal disaggregation** (4 new fiscal indicators, biggest cross-state-comparison win, fits Phase-6 priority #7 from the architecture cheatsheet)
2. **Per-capita NSDP** (income, missing economic primitive)
3. **EV trend** (opens a new `transport/` category)
4. **National NAS quarterly** + Primary energy + RE potential (national context indicators)

**B. Bulk-delete the `SKIP-DUP`/`DELETE`/duplicate rows first** so the folder shrinks to only the actionable items, then proceed with A.

**C. Stop here** — the table is the deliverable, ingest is a separate decision later.

I have not touched `datasets/` or deleted anything. Awaiting your call.

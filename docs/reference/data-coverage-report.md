# Data Coverage Report

**Last Updated**: 2026-05-14
**Snapshot**: counts and time spans were measured by scanning `datasets/` directly on the date above. This is a hand-authored snapshot, NOT auto-generated. (For the auto-generated election-only coverage, see [data-inventory.md](data-inventory.md).)

> Plain-English answer to *"what data do we have, for what indicators, for what time period, and what's pending?"* Pair this with [`upstream-sources.json`](../../datasets/reference/in/upstream-sources.json) (the machine-readable upstream registry) and [`data-sources.md`](data-sources.md) (the per-source narrative).

## TL;DR

| Surface | Coverage today |
| ------- | -------------- |
| **Election results** (per AC) | 21 elections × 17 states/UTs = 34 result sets, **~3,930 AC results**, from Apr 2016 → May 2026 |
| **Indicators** | 32 artifacts: 16 energy, 10 fiscal, 4 economy, 1 demography, 1 misc |
| **Time depth** | RBI national fiscal series go back to FY 2007–08 (19y); ICED state series go back to FY 2015–16 (10–11y); CEA installed capacity is a single 2026-03 snapshot |
| **Boundaries** | 31 state/UT AC polygon files + national state + district choropleth bases |
| **Governance** | CM term timelines for 31 states |
| **Reference** | 26 state constituency lists, 6 hand-authored district lists (S03, S06, S11, S22, S25, U07 done — full LGD ingest WIP), parties, topics, election event index |
| **Provenance** | Every artifact carries `sources[]`; validated by 9,312 frontend contract tests + backend `python -m yen_gov validate` |

## 1. Indicators — what's loaded

Per artifact: row count, time span the rows actually span (start..end), entity count, upstream host. Times are calendar months in `YYYY-MM` form; for fiscal-year series the month is the **April** of the FY's start (e.g. `2007-04` = FY 2007–08); for state debt the month is **March** (FY end).

### 1a. Energy (16)

| id | unit | rows | time span | n times | entities | admin | source |
|----|------|-----:|----|----:|----:|----|----|
| `energy/installed_capacity_coal_mw` | MW |   35 | 2026-03..2026-03 | 1 | 35 | state | cea.nic.in |
| `energy/installed_capacity_gas_mw` | MW |   35 | 2026-03..2026-03 | 1 | 35 | state | cea.nic.in |
| `energy/installed_capacity_hydro_mw` | MW |   35 | 2026-03..2026-03 | 1 | 35 | state | cea.nic.in |
| `energy/installed_capacity_nuclear_mw` | MW |   35 | 2026-03..2026-03 | 1 | 35 | state | cea.nic.in |
| `energy/installed_capacity_renewable_mw` | MW |   35 | 2026-03..2026-03 | 1 | 35 | state | cea.nic.in |
| `energy/installed_capacity_thermal_mw` | MW |   35 | 2026-03..2026-03 | 1 | 35 | state | cea.nic.in |
| `energy/installed_capacity_total_mw` | MW |   35 | 2026-03..2026-03 | 1 | 35 | state | cea.nic.in |
| `energy/installed_mw_by_state` | MW |   14 | 2019..2019 | 1 | 4 | state | raw.githubusercontent.com |
| `energy/state_acs_arr_gap_inr_per_kwh` | INR/kWh |  314 | 2015-04..2024-04 | 10 | 37 | state | iced.niti.gov.in |
| `energy/state_atc_losses_pct` | % |  344 | 2015-04..2024-04 | 10 | 37 | state | iced.niti.gov.in |
| `energy/state_electricity_generation_mu` | MU |  407 | 2015-04..2025-04 | 11 | 37 | state | iced.niti.gov.in |
| `energy/state_electricity_peak_demand_mw` | MW |  305 | 2017-04..2025-04 | 9 | 34 | state | iced.niti.gov.in |
| `energy/state_electricity_sales_mu` | MU |  356 | 2015-04..2024-04 | 10 | 37 | state | iced.niti.gov.in |
| `energy/state_installed_capacity_geographical_mw` | MW |  407 | 2015-04..2025-04 | 11 | 37 | state | iced.niti.gov.in |
| `energy/state_installed_capacity_with_alloc_mw` | MW |  396 | 2015-04..2025-04 | 11 | 36 | state | iced.niti.gov.in |
| `energy/state_rooftop_solar_capacity_mw` | MW |  321 | 2017-04..2025-04 | 9 | 37 | state | iced.niti.gov.in |

**Read this as**: ICED gives 8 per-state energy series, all states/UTs, ~10 years annual. CEA gives a current-month per-state nameplate-capacity snapshot by fuel. They overlap on installed capacity; ICED is the long-series, CEA is the freshness check.

### 1b. Fiscal (10)

| id | unit | rows | time span | n times | entities | admin | source |
|----|------|-----:|----|----:|----:|----|----|
| `fiscal/centre_transfers_gross` | INR (crore) |  196 | 2016-04..2022-04 | 7 | 28 | state | www.data.gov.in |
| `fiscal/national_centre_transfers_total` | INR (crore) |   19 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/national_devolution_central_taxes` | INR (crore) |   19 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/national_grants_from_centre` | INR (crore) |   19 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/national_gross_fiscal_deficit` | INR (crore) |   20 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/national_gross_transfers` | INR (crore) |   19 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/national_primary_deficit` | INR (crore) |   20 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/national_primary_revenue_deficit` | INR (crore) |   20 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/national_revenue_deficit` | INR (crore) |   20 | 2007-04..2025-04 | 19 | 1 | national | www.rbi.org.in |
| `fiscal/net_transfers_from_centre` | INR (crore) |   93 | 2023-04..2025-04 | 3 | 31 | state | rbidocs.rbi.org.in |
| `fiscal/outstanding_debt_pct_gsdp` | % |  589 | 2008-03..2026-03 | 19 | 31 | state | rbidocs.rbi.org.in |

**Read this as**:
- **National long series (8 indicators)** — RBI Handbook / State Finances publication, FY08–FY26, 19 fiscal years deep. The canonical "all-states-combined" view.
- **State debt** — `outstanding_debt_pct_gsdp` is per-state, 31 states, FY08–FY26 — the only multi-decade per-state fiscal series we ship.
- **State transfers — two slices**: `net_transfers_from_centre` (RBI, 31 states, FY24–FY26 only) and `centre_transfers_gross` (data.gov.in OGD, 28 states, FY17–FY23). Together they cover FY17–FY26 with a gap shape; neither alone is complete.

### 1c. Economy + Demography (5)

| id | unit | rows | time span | n times | entities | admin | source |
|----|------|-----:|----|----:|----:|----|----|
| `demography/state_population_lakhs` | Lakhs |  407 | 2015-04..2025-04 | 11 | 37 | state | iced.niti.gov.in |
| `economy/state_gdp_constant_2011_12_inr_lakh_crore` | INR (lakh crore) |  332 | 2015-04..2024-04 | 10 | 34 | state | iced.niti.gov.in |
| `economy/state_gdp_current_inr_lakh_crore` | INR (lakh crore) |  334 | 2015-04..2024-04 | 10 | 35 | state | iced.niti.gov.in |
| `economy/state_sectoral_gva_constant_2011_12_inr_lakh_crore` | INR (lakh crore) |  332 | 2015-04..2024-04 | 10 | 34 | state | iced.niti.gov.in |
| `economy/state_sectoral_gva_current_inr_lakh_crore` | INR (lakh crore) |  334 | 2015-04..2024-04 | 10 | 35 | state | iced.niti.gov.in |

All five come bundled in the ICED `stateWiseDeepDive` payload (one HTTP fetch covers the whole NITI energy/economy/demography wedge).

## 2. Election results — what's loaded

Per (event × state) cell shows the AC count for which we have a parsed result file under `datasets/elections/<event>/<state>/results/<ac_no>.json`.

| event | state | ACs |
|----|----|----:|
| AcGenApr2016 | S03 (Assam) | 126 |
| AcGenApr2019 | S01 (Andhra Pradesh) | 175 |
| AcGenApr2021 | S03 (Assam) | 126 |
| AcGenApr2021 | S11 (Kerala) | 140 |
| AcGenDec2019 | S27 (Jharkhand) | 81 |
| AcGenFeb2017 | S05 (Goa) | 40 |
| AcGenFeb2020 | U05 (Delhi) | 70 |
| AcGenFeb2022 | S05 (Goa) | 40 |
| AcGenFeb2025 | U05 (Delhi) | 70 |
| AcGenJun2024 | S01 (Andhra Pradesh) | 175 |
| AcGenJun2024 | S02 (Arunachal Pradesh) | 50 |
| AcGenJun2024 | S18 (Sikkim) | 147 |
| AcGenJun2024 | S21 (Odisha) | 32 |
| AcGenMay2016 | S11 (Kerala) | 140 |
| AcGenMay2018 | S10 (Karnataka) | 223 |
| AcGenMay2023 | S10 (Karnataka) | 224 |
| AcGenMay2026 | S03 (Assam) | 126 |
| AcGenMay2026 | S11 (Kerala) | 140 |
| AcGenMay2026 | S22 (Tamil Nadu) | 234 |
| AcGenMay2026 | S25 (West Bengal) | 293 |
| AcGenMay2026 | U07 (Puducherry) | 30 |
| AcGenNov2017 | S08 (Himachal Pradesh) | 68 |
| AcGenNov2020 | S04 (Bihar) | 243 |
| AcGenNov2022 | S08 (Himachal Pradesh) | 68 |
| AcGenNov2023 | S12 (Madhya Pradesh) | 230 |
| AcGenNov2023 | S16 (Mizoram) | 40 |
| AcGenNov2023 | S26 (Chhattisgarh) | 90 |
| AcGenNov2023 | S29 (Telangana) | 119 |
| AcGenNov2024 | S13 (Maharashtra) | 288 |
| AcGenNov2024 | S27 (Jharkhand) | 81 |
| AcGenNov2025 | S04 (Bihar) | 243 |
| AcGenOct2019 | S07 (Haryana) | 90 |
| AcGenOct2024 | S07 (Haryana) | 90 |
| AcGenOct2024 | U08 (J&K) | 90 |

**Read this as**: 21 distinct elections, **17 states/UTs covered at least once**, **~3,930 per-AC result files**. The May 2026 wave (the project's primary "live" target — TN, WB, Kerala, Assam, Puducherry) is fully ingested.

Each `<ac_no>.json` is parsed from ECI's per-AC results page (`results.eci.gov.in/Result<EventSlug>/Constituencywise<StateCode><AC:03d>.htm`). Per-state `parties.json` and `result.summary.json` siblings ship the registry + state-level rollup.

For the auto-generated election-coverage view (gaps in the events catalogue, per-cohort breakdown), see the sibling [data-inventory.md](data-inventory.md), which is regenerated by `python -m yen_gov coverage`.

## 3. Reference data

| Group | What ships | Notes |
| ----- | ---------- | ----- |
| `reference/in/states.json` | 28 states + 8 UTs registry | ECI codes (S01..S29, U01..U08) |
| `reference/in/state-tiers.json` | State grouping for the IA | Tiered by Lok Sabha seat count |
| `reference/in/parties.json` | Master party list | ECI party codes + display |
| `reference/in/parties-discovered.json` | Auto-discovered new parties from per-AC results | Promotion candidates |
| `reference/in/election-events.json` | Master event index | Event id, name, dates |
| `reference/in/topic-catalogue.json` | UI topic taxonomy | Indicator-id → topic |
| `reference/in/upstream-sources.json` | **Upstream registry (new, 2026-05-14)** | 21 upstreams, statuses, adapters, indicator ids |
| `reference/in/states/<S__>/constituencies.json` | Per-state AC list | 26 of 36 states/UTs covered |
| `reference/in/states/<S__>/districts.json` | Per-state district list | **6 hand-authored** (S03, S06, S11, S22, S25, U07); LGD pipeline WIP for the rest |
| `reference/in/lgd/{states,districts}-latest.csv.sources.json` | LGD download provenance stubs | Pipeline in-flight on branch `feat/lgd-districts-pipeline` |

## 4. Boundaries, features, governments

- **Boundaries** — `datasets/boundaries/in/geojson/`: 31 per-state AC polygon files (`S__-ac.geojson`) + `india-states.geojson` + `india-districts.geojson`. Each carries a sibling `.sources.json` recording the upstream geojson author + commit.
- **Features** — `datasets/features/in/energy/power-plants.geojson`: point layer of generating stations from `india-geodata`. Used by the energy hub map.
- **Governments** — `datasets/governments/in/states/<S__>/cm_terms.json`: Chief Minister term-of-office timelines for 31 states. Used to label the "who governed when" overlay.

## 5. What's NOT loaded yet (the gaps)

Two kinds of gap: (a) candidate upstreams that haven't been ingested at all; (b) loaded artifacts that need wider coverage.

### 5a. Candidate upstreams (status `candidate` in the registry)

| id | what it would unlock | priority hint |
| -- | -------------------- | ------------- |
| `rbi.handbook_state_macro` | RBI Handbook of Statistics — wider state macro panel (banking, prices, external sector) | Medium — fills the GSDP/banking gap below FY15 |
| `rbi.weekly_statistical_supplement_gold` | Weekly RBI gold reserve series | Low — niche indicator |
| `rbi.state_finances_statement_8_long_series` | RBI State Finances Statement 8 — per-state revenue/expenditure long series | **High** — pairs with the Appendix tables to give per-state fiscal long history |
| `data_gov_in.aishe_education` | AISHE per-state higher-education enrolment, faculty, GER | Medium — fills education indicator wedge |
| `ceo.state_portals` | Live election bootstrap (candidates, polling stations) before ECI consolidates | Future cycle — only useful around poll dates |
| `myneta.candidate_affidavits` | Candidate-level financial / criminal disclosures | Medium — citizen-visible hub |

### 5b. Loaded artifacts that need wider coverage

| Artifact | Current span | Gap |
| -------- | ------------ | --- |
| `energy/installed_capacity_*_mw` (CEA, 7 fuel artifacts) | single month: 2026-03 | Backfill prior months from `cea.nic.in/wp-content/uploads/installed/<YYYY>/<MM>/Website.xlsx` to get a monthly time series. ICED already covers FY15→FY25 annual, so prioritize last ~24 monthly snapshots, not deep history. |
| `fiscal/centre_transfers_gross` | FY17..FY23 | Refresh when data.gov.in publishes FY24+. Requires re-solving the captcha + dropping new CSVs into `.runtime/raw/datagovin/`. |
| `fiscal/net_transfers_from_centre` | FY24..FY26 | Backfill FY08..FY23 from older RBI State Finances editions (per-edition pin already exists in `rbi_xlsx/urls.py`). |
| Per-state constituency lists | 26 of 36 covered | Missing UTs / smaller states. Bootstrap from ECI statistical reports for any state with a past election in the inventory. |
| Per-state district lists | 6 of 36 hand-authored | Pending the LGD pipeline (see §6). |
| Election results | 17 states/UTs covered | Pre-2016 history is not ingested. The `eci` adapter already supports it; just needs `processing.json` event ids added. |

### 5c. Conscious skips (`status: skipped` in the registry)

| id | why skipped |
| -- | ----------- |
| `cea.archive_long_history` | Windows TLS chain rejects `cea.nic.in`; ICED already exposes 11 years of CEA-published values, so the marginal value isn't worth the operator-fetch monthly back to 2010. |
| `data_gov_in.rbi_search_results` | Reconned 2026-05-14: results are mostly Rajya Sabha question snapshots (bank-frauds, ombudsman complaints, demonetised-note recovery) that don't duplicate canonical RBI long-series. Promotion to `candidate` is a per-resource decision. |

## 6. Active in-flight work (not yet shipped)

- **LGD districts pipeline** (`feat/lgd-districts-pipeline` branch): converting hand-authored per-state district JSONs into a single LGD-sourced authoritative artifact. Two tests fail on this branch (`test_districts_collection_round_trip`, `test_live_districts_tn`); both are intentional WIP markers, not regressions. Tracking in TODO.
- **Frontend IA reset** (`TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md`): place-first navigation with topic front door. Doesn't change data inventory, but reshapes which indicators get surfaced where.
- **Party color rework** (`TODO/PARTY-COLORS-REWORK.md`): purely UI; no dataset impact.

## 7. How to refresh / regenerate

| Want to refresh… | Run |
| ---------------- | --- |
| Validate every dataset against its schema | `python -m yen_gov validate` (from `backend/` with the venv) |
| Regenerate the auto election-coverage report ([data-inventory.md](data-inventory.md)) | `python -m yen_gov coverage` |
| Run the full backend test suite | `cd backend && pytest -q` (the two LGD tests above will fail until that pipeline lands; `--deselect` if needed) |
| Run the frontend contract tests (every dataset) | `cd frontend && npm test -- src/contracts/datasets-conform.test.ts` (9,312 tests) |
| Ingest a new ECI election | Add the event id to `config/processing.json`, then `python -m yen_gov pipeline run --event <EventSlug>` |
| Refresh ICED state series | Re-run the ICED adapter; payload is fetched live and decrypted in-process |
| Refresh CEA installed capacity | Operator: `Invoke-WebRequest` on the next monthly XLSX into `.runtime/raw/cea/`, then run the CEA adapter |

## 8. See also

- [data-sources.md](data-sources.md) — per-source narrative (humans)
- [`datasets/reference/in/upstream-sources.json`](../../datasets/reference/in/upstream-sources.json) — machine-readable upstream registry (canonical for "what URL, what status, what adapter, what indicators")
- [data-inventory.md](data-inventory.md) — auto-generated election-only coverage (gaps in the events catalogue, per-cohort breakdown)
- [`datasets/schemas/`](../../datasets/schemas/) — schemas every artifact above conforms to
- Adapters (Python): `backend/yen_gov/sources/<adapter>/` — each has a module-level docstring explaining its upstream and quirks

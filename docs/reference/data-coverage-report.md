# Data Coverage Report

**Last Updated**: 2026-05-14 (election table restructured state-first 2026-05-14; **Temporal Richness** meter added to indicators 2026-05-14)
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

Per artifact: time grain, **Temporal Richness** (visual time-coverage meter), span the rows actually span (start..end), entity count, upstream host. Times are calendar months in `YYYY-MM` form; for fiscal-year series the month is the **April** of the FY's start (e.g. `2007-04` = FY 2007–08); for state debt the month is **March** (FY end).

> **Reading the Temporal Richness meter** — Each indicator's Temporal Richness is a 7-cell bar covering the last ~21 fiscal years (FY06 → FY26). Each cell = a 3-year bucket; **rightmost cell is the most recent** and the bar fills right-to-left as time advances:
>
> | Cell | 1 (left, oldest) | 2 | 3 | 4 | 5 | 6 | 7 (right, newest) |
> |------|-----|---|---|---|---|---|-----|
> | Span | FY06–FY08 | FY09–FY11 | FY12–FY14 | FY15–FY17 | FY18–FY20 | FY21–FY23 | FY24–FY26 |
>
> A cell is `●` (filled) if the indicator has **at least one** data point in that bucket, `○` (empty) otherwise. The trailing `n/7` is the count of filled cells. Single-month snapshots show as 1/7 with a `(snapshot)` tag — the meter is built for time series, not point-in-time captures.

### 1a. Energy (16)

| id | unit | grain | Temporal Richness | span | yrs | states | source |
|----|------|-------|-------|------|----:|-------:|--------|
| `energy/installed_capacity_coal_mw`              | MW      | snapshot   | `○ ○ ○ ○ ○ ○ ●` 1/7 (snapshot) | 2026-03 | 1 | 35 | cea.nic.in |
| `energy/installed_capacity_gas_mw`               | MW      | snapshot   | `○ ○ ○ ○ ○ ○ ●` 1/7 (snapshot) | 2026-03 | 1 | 35 | cea.nic.in |
| `energy/installed_capacity_hydro_mw`             | MW      | snapshot   | `○ ○ ○ ○ ○ ○ ●` 1/7 (snapshot) | 2026-03 | 1 | 35 | cea.nic.in |
| `energy/installed_capacity_nuclear_mw`           | MW      | snapshot   | `○ ○ ○ ○ ○ ○ ●` 1/7 (snapshot) | 2026-03 | 1 | 35 | cea.nic.in |
| `energy/installed_capacity_renewable_mw`         | MW      | snapshot   | `○ ○ ○ ○ ○ ○ ●` 1/7 (snapshot) | 2026-03 | 1 | 35 | cea.nic.in |
| `energy/installed_capacity_thermal_mw`           | MW      | snapshot   | `○ ○ ○ ○ ○ ○ ●` 1/7 (snapshot) | 2026-03 | 1 | 35 | cea.nic.in |
| `energy/installed_capacity_total_mw`             | MW      | snapshot   | `○ ○ ○ ○ ○ ○ ●` 1/7 (snapshot) | 2026-03 | 1 | 35 | cea.nic.in |
| `energy/installed_mw_by_state`                   | MW      | snapshot   | `○ ○ ○ ○ ● ○ ○` 1/7 (snapshot, **stale**) | 2019    | 1 |  4 | raw.githubusercontent.com |
| `energy/state_acs_arr_gap_inr_per_kwh`           | INR/kWh | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY24 | 10 | 37 | iced.niti.gov.in |
| `energy/state_atc_losses_pct`                    | %       | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY24 | 10 | 37 | iced.niti.gov.in |
| `energy/state_electricity_generation_mu`         | MU      | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY25 | 11 | 37 | iced.niti.gov.in |
| `energy/state_electricity_peak_demand_mw`        | MW      | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY17–FY25 |  9 | 34 | iced.niti.gov.in |
| `energy/state_electricity_sales_mu`              | MU      | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY24 | 10 | 37 | iced.niti.gov.in |
| `energy/state_installed_capacity_geographical_mw`| MW      | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY25 | 11 | 37 | iced.niti.gov.in |
| `energy/state_installed_capacity_with_alloc_mw`  | MW      | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY25 | 11 | 36 | iced.niti.gov.in |
| `energy/state_rooftop_solar_capacity_mw`         | MW      | annual FY  | `○ ○ ○ ● ● ● ●` 4/7 | FY17–FY25 |  9 | 37 | iced.niti.gov.in |

**Read this as**:
- **ICED gives 8 per-state annual series** at a uniform 4/7 reach (FY15-onwards). All 8 share the same gap shape: pre-2015 cells (B1–B3) are empty everywhere. If we want to cross the 4/7 line for energy, the next move is finding a pre-2015 source — CEA's archive or ICED itself if their backfill UI exposes deeper history.
- **CEA gives 7 fuel-wise nameplate-capacity snapshots**, all at 1/7 (`(snapshot)`). They overlap with ICED's `state_installed_capacity_*` on intent but disagree on "now" — CEA is the freshness check at the rightmost cell; ICED is the long series in the middle cells. To turn CEA into a real series, scrape `cea.nic.in/wp-content/uploads/installed/<YYYY>/<MM>/Website.xlsx` for prior months (covered in §5b).
- **`installed_mw_by_state` is stale** (2019 only, 4 states only). The Reach meter highlights it visually — single bar in the middle, nothing recent. Either deprecate it or refresh from the same upstream.

### 1b. Fiscal (10)

| id | unit | grain | Temporal Richness | span | yrs | entities | scope | source |
|----|------|-------|-------|------|----:|---------:|-------|--------|
| `fiscal/centre_transfers_gross`                  | INR (crore) | annual FY  | `○ ○ ○ ● ● ● ○` 3/7 (**recent gap**) | FY16–FY22 |  7 | 28 | state    | www.data.gov.in |
| `fiscal/national_centre_transfers_total`         | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/national_devolution_central_taxes`       | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/national_grants_from_centre`             | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/national_gross_fiscal_deficit`           | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/national_gross_transfers`                | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/national_primary_deficit`                | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/national_primary_revenue_deficit`        | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/national_revenue_deficit`                | INR (crore) | annual FY  | `● ● ● ● ● ● ●` 7/7                  | FY07–FY25 | 19 |  1 | national | www.rbi.org.in |
| `fiscal/net_transfers_from_centre`               | INR (crore) | annual FY  | `○ ○ ○ ○ ○ ● ●` 2/7 (**recent only**) | FY23–FY25 |  3 | 31 | state    | rbidocs.rbi.org.in |
| `fiscal/outstanding_debt_pct_gsdp`               | %           | annual FY-end | `● ● ● ● ● ● ●` 7/7                | FY07–FY25 | 19 | 31 | state    | rbidocs.rbi.org.in |

**Read this as**:
- **National long series (8 RBI indicators)** are all **7/7** — the canonical "all-states-combined" view, FY07 → FY25, no gaps. This is our deepest fiscal coverage.
- **State debt** (`outstanding_debt_pct_gsdp`) is also **7/7** but per-state for 31 states — the only multi-decade per-state fiscal series we ship. Pair this with the national 7/7 series to anchor any state vs national comparison.
- **State centre-transfer coverage is split with a gap shape** — `centre_transfers_gross` (data.gov.in OGD, FY16–FY22) covers cells B4–B6 only; `net_transfers_from_centre` (RBI, FY23–FY25) covers B6–B7 only. Stitched together they reach FY16–FY25 (cells B4–B7), still missing the deep history (B1–B3). Neither alone is complete; the meter makes the seam at B6 visible at a glance.
- **Deepest backfill priority for fiscal** = pre-FY16 per-state transfers and pre-FY07 national series. The latter likely needs older RBI editions (per-edition pin already in `rbi_xlsx/urls.py`).

### 1c. Economy + Demography (5)

| id | unit | grain | Temporal Richness | span | yrs | states | source |
|----|------|-------|-------|------|----:|-------:|--------|
| `demography/state_population_lakhs`                          | Lakhs            | annual FY | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY25 | 11 | 37 | iced.niti.gov.in |
| `economy/state_gdp_constant_2011_12_inr_lakh_crore`          | INR (lakh crore) | annual FY | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY24 | 10 | 34 | iced.niti.gov.in |
| `economy/state_gdp_current_inr_lakh_crore`                   | INR (lakh crore) | annual FY | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY24 | 10 | 35 | iced.niti.gov.in |
| `economy/state_sectoral_gva_constant_2011_12_inr_lakh_crore` | INR (lakh crore) | annual FY | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY24 | 10 | 34 | iced.niti.gov.in |
| `economy/state_sectoral_gva_current_inr_lakh_crore`          | INR (lakh crore) | annual FY | `○ ○ ○ ● ● ● ●` 4/7 | FY15–FY24 | 10 | 35 | iced.niti.gov.in |

**Read this as**: All five sit at the same 4/7 reach as the ICED energy series — same upstream payload (`stateWiseDeepDive`), same FY15-onwards window, same B1–B3 gap. Backfilling pre-2015 GSDP / population would unlock cross-decade comparisons but needs a different source (MoSPI / NSO archives).

## 2. Election results — what's loaded

> Slots `E0…E-6` are presentation-only and live in this report alone. The on-disk data model is event-first and absolute (`datasets/elections/<event>/<state>/results/<ac_no>.json`); the dataset has no `current` or `N-1` field. **E0** = most recent election parsed for that state, regardless of whether that assembly is currently sitting (Tamil Nadu's E0 is the May 2026 *incoming* assembly; Karnataka's E0 is May 2023, sitting mid-term). **E-1** = the one before, … out to **E-6** (~25-year reach back, since AC general elections happen ~every 5 years per state).

### 2a. Coverage depth — events parsed per state

One row per state. **Temporal Richness** is a 7-slot meter (`●` filled, `○` empty, with spaces) plus an `n/7` count. Same convention as §1: **rightmost cell is the most recent** (E0); the bar fills right-to-left as you backfill into the past. Each cell here = one election cycle (E0, E-1, … E-6 from right to left), so empty `○` slots on the left visually flag where the historical backfill is needed. **Events** lists what we hold, newest → oldest.

| ECI | State | Temporal Richness | Events parsed (newest → oldest) |
|-----|-------|-------------------|---------------------------------|
| S01 | Andhra Pradesh    | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenJun2024`, `AcGenApr2019` |
| S02 | Arunachal Pradesh | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenJun2024` |
| S03 | Assam             | `○ ○ ○ ○ ● ● ●` 3/7 | `AcGenMay2026`, `AcGenApr2021`, `AcGenApr2016` |
| S04 | Bihar             | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenNov2025`, `AcGenNov2020` |
| S05 | Goa               | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenFeb2022`, `AcGenFeb2017` |
| S07 | Haryana           | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenOct2024`, `AcGenOct2019` |
| S08 | Himachal Pradesh  | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenNov2022`, `AcGenNov2017` |
| S10 | Karnataka         | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenMay2023`, `AcGenMay2018` |
| S11 | Kerala            | `○ ○ ○ ○ ● ● ●` 3/7 | `AcGenMay2026`, `AcGenApr2021`, `AcGenMay2016` |
| S12 | Madhya Pradesh    | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenNov2023` |
| S13 | Maharashtra       | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenNov2024` |
| S16 | Mizoram           | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenNov2023` |
| S18 | Sikkim            | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenJun2024` |
| S21 | Odisha            | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenJun2024` |
| S22 | Tamil Nadu        | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenMay2026` |
| S25 | West Bengal       | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenMay2026` |
| S26 | Chhattisgarh      | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenNov2023` |
| S27 | Jharkhand         | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenNov2024`, `AcGenDec2019` |
| S29 | Telangana         | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenNov2023` |
| U05 | Delhi             | `○ ○ ○ ○ ○ ● ●` 2/7 | `AcGenFeb2025`, `AcGenFeb2020` |
| U07 | Puducherry        | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenMay2026` |
| U08 | J&K               | `○ ○ ○ ○ ○ ○ ●` 1/7 | `AcGenOct2024` |

**Read this as**: **22 states/UTs** in the inventory, **34 (state × event) cells** spread across **21 distinct elections**, **~3,930 per-AC result files**.

- **3-deep (E-2)**: 2 states — S03 Assam, S11 Kerala.
- **2-deep (E-1)**: 8 states/UTs — S01, S04, S05, S07, S08, S10, S27, U05.
- **1-deep (only E0)**: 12 states/UTs — the natural backfill candidates for at least one prior cycle.
- **No state is past E-2 today.** Every cell from E-3 to E-6 is empty across every row. The intent is to take 1-2 priority states all the way to E-4 (~20 years) first, then expand.
- The May 2026 wave (the project's primary "live" target — TN, WB, Kerala, Assam, Puducherry) is fully ingested as E0.

### 2b. Constituency count drift across cycles

Only multi-election states appear here — Δ has no signal for single-election states. AC counts are listed left to right from E0 (most recent) to the oldest cycle we hold for that state. A change row-to-row across the AC columns flags either a delimitation tweak or a boundary redraw with a count change; same count across cycles still allows boundary redraws within an unchanged total — those need a separate AC GeoJSON diff.

| ECI | State | E0 ACs | E-1 ACs | E-2 ACs | Notable drift |
|-----|-------|-------:|--------:|--------:|---------------|
| S01 | Andhra Pradesh   | 175 | 175 |  —  | none |
| S03 | Assam            | 126 | 126 | 126 | none |
| S04 | Bihar            | 243 | 243 |  —  | none |
| S05 | Goa              |  40 |  40 |  —  | none |
| S07 | Haryana          |  90 |  90 |  —  | none |
| S08 | Himachal Pradesh |  68 |  68 |  —  | none |
| S10 | Karnataka        | 224 | 223 |  —  | **+1 at E0** (2023 boundary tweak) |
| S11 | Kerala           | 140 | 140 | 140 | none |
| S27 | Jharkhand        |  81 |  81 |  —  | none |
| U05 | Delhi            |  70 |  70 |  —  | none |

**Read this as**: across the 10 multi-election states we hold, **only Karnataka shows a count change** (2018 → 2023, +1 AC). Every other state held its AC count steady across cycles. This is the cheap structural signal; a deeper boundary diff against `datasets/boundaries/in/geojson/<S__>-ac.geojson` would catch redraws that preserve the count.

> **Apparent inversion to verify**: S18 Sikkim shows 147 ACs and S21 Odisha shows 32 ACs in the source data — these look swapped (Sikkim has 32 ACs, Odisha has 147). Numbers reproduced as currently scanned; flagged for a follow-up audit rather than silently rewriting.

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

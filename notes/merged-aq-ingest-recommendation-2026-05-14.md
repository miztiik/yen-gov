# Merged_Annually_Quarterly.csv — ingest recommendation

**Date**: 2026-05-14
**Source file**: `datasets/ephemeral_datasets/Merged_Annually_Quarterly.csv` (7,797 rows, 13 columns, 1 MB)
**Status**: Recommendation only. No ingest performed.
**Audience**: future-me / next session. Decision pending user approval before any ingest.

---

## TL;DR

This is a **MoSPI National Accounts Statistics (NAS) dump** — the macroeconomic mother lode. It contains India's full national-level time-series for GDP, GVA, savings, investment, consumption, capital formation, foreign trade, and growth rates, broken down by industry (17), institutional sector (12), and quarter, across two base-year vintages (2011-12 and 2022-23) and eight revision tiers, from 1999 through FY 2025-26.

Recommend a **5-artifact split** (not 22 — see "Why not one-per-indicator" below), with revision-vintage and base-year handling baked into the loader, NOT into the artifact count.

We currently have **zero national NAS coverage** (the new `national_gdp_current_inr_lakh_crore.json` we just wrote covers GDP only). This file fills the entire macroeconomic gap.

---

## File anatomy

| Column | Distinct | Notes |
| --- | ---: | --- |
| `base_year` | 2 | `2011-12` (legacy series, 7,016 rows) and `2022-23` (new MoSPI rebase, 781 rows). Constant-price values are **not splice-able** across bases. |
| `series` | 1 | Always `Current` — appears to be a residual column; ignore. |
| `year` | 27 | `1999` through `2025-26`. Mixed format (`1999`..`2008`, then `2008-09`..`2025-26`). |
| `indicator` | 22 | Headline aggregates + breakdowns. See list below. |
| `frequency` | 2 | `Annual` (5,793) and `Quarterly` (2,004). |
| `revision` | 8 | `First Advance` → `Second Advance` → `Provisional` → `First Revised` → `Second Revised` → `Third Revised` → `Final` → `Additional Revision`. Blank for all quarterly rows. |
| `industry` | 17 | NIC-aligned (Agriculture, Manufacturing, Construction, …, Total Gross Value Added). |
| `subindustry` | 18 | Sparse (1,759 rows). Crops, Livestock, Fishing, Air Transport, Hotels & Restaurants, etc. |
| `institutional_sector` | 12 | Public/Private × Financial/Non-Financial corporations, General Government, Households (incl. NPISH), Household Sector. |
| `quarter` | 4 | `Q1`..`Q4`, only set when `frequency=Quarterly`. |
| `current_price` | — | Nominal value in ₹ Crore. |
| `constant_price` | — | Real value in ₹ Crore at the row's `base_year`. |
| `unit` | 2 | `₹ Crore` (5,717) and `%` (2,080 — growth-rate rows). |

### The 22 indicators

| Family | Indicators | Row count |
| --- | --- | ---: |
| **GDP & GVA aggregates** | Gross Domestic Product, Gross Value Added, Net Domestic Product, Gross National Income, Gross National Disposable Income | 2,686 |
| **Growth rates** (derived) | GDP Growth Rate, GVA Growth Rate | 2,080 |
| **Capital & saving** | Gross Fixed Capital Formation, Gross Capital Formation by Industry of Use, Gross Saving, Consumption of Fixed Capital, Change in Stock, Valuables | 2,068 |
| **Expenditure side** | Private Final Consumption Expenditure, Government Final Consumption Expenditure | 286 |
| **External sector** | Export of Goods and Services, Import of Goods and Services, Primary Income Receivable Net From RoW, Other Current Transfers Net From RoW | 360 |
| **Taxes & subsidies** | Net Taxes on Products, Taxes on Products, Subsidies on Products | 217 |

---

## Recommended 5-artifact split

Rationale: one artifact = one (indicator, value-kind, breakdown) tuple. Multiple revisions per (year, indicator) collapse to **one canonical row per year** (latest-final revision wins; vintage history is an enrichment for later, NOT a separate artifact today). The two base-years are spliced for `current_price` (nominal is base-independent — verified by spot-check) and kept separate for `constant_price`.

### 1. `economy/national_macro_aggregates_current_inr_crore.json`
- **Shape**: long-format with `facet: indicator_name`. ~10 indicators × ~25 years ≈ 250 rows.
- **Indicators included**: GDP, GVA, NDP, GNI, GNDI, GFCF, Gross Saving, Consumption of Fixed Capital, PFCE, GFCE, Change in Stock, Valuables, Net Taxes on Products. (All `unit = ₹ Crore`, no industry breakdown, no institutional-sector breakdown.)
- **Time grain**: `fiscal_year`, time `YYYY-04`.
- **Splice**: take `base_year=2022-23` rows where present; fall back to `base_year=2011-12`. Verify on overlap (current prices should match within rounding).
- **Revision**: keep highest-finalised revision per (indicator, year). Add `vintage` field per row recording which revision was used.

### 2. `economy/national_macro_aggregates_constant_2011_12_inr_crore.json`
- Same as #1 but `value_kind: "currency_real"`, `constant_price` column, `base_year=2011-12` only.
- `methodology_vintage` notes the base year explicitly.

### 3. `economy/national_macro_aggregates_constant_2022_23_inr_crore.json`
- Same as #2 but `base_year=2022-23` only. Sparse — only ~5 years of coverage so far. Document as the "new vintage" with `series_breaks` pointing to the 2011-12 series for older history.

### 4. `economy/national_gva_by_industry_current_inr_crore.json` + `_constant_2011_12_` sibling
- **Shape**: facet on `industry` (17 values). ~17 × ~10 years ≈ 170 rows per file.
- Drops rows where `industry` is blank.
- Same revision-collapse rule.
- Subindustry-level rows go into a separate artifact only if user asks; otherwise drop them — they're a deeper drill that few citizens need.

### 5. `economy/national_gva_by_industry_quarterly_current_inr_crore.json` + constant sibling
- **Shape**: facet on `industry`, `time_grain: "quarter"`, time as `YYYY-Qn` (or `YYYY-MM` if schema requires — check enum & format on `time` field before writing).
- 2,004 quarterly rows total → ~10 industries × ~14 quarters × 2 price types ≈ ~280 rows per artifact.

### Optional 6th: `economy/national_gfcf_by_institutional_sector_current_inr_crore.json`
- Facet on `institutional_sector` (5 corp/govt sectors + households).
- ~70 rows. Useful for "who saves and who invests in India?" but a niche question. Defer until citizen story needs it.

---

## What to drop (do not ingest)

- **Growth-rate rows** (`unit = %`, 2,080 rows). These are computed downstream from level series — emitting them as a separate artifact creates two sources of truth for the same number. Compute on the client/build side from artifacts #1.
- **Subindustry rows** (1,759 rows). Sparse, deeper than citizen-facing UI needs in v1. Revisit if a feature requires it.
- **`series` column.** Always `Current`. Vestigial.

---

## Open questions before ingest

1. **Quarter time format** — does `indicator.schema.json` accept `YYYY-Qn` for `time_grain: "quarter"`, or does it require `YYYY-MM` (e.g., Q1 → `2024-04`)? **Action**: read the schema's `time` constraint per `time_grain`. If undocumented, propose an addition in the same PR.
2. **Source URL** — MoSPI's NAS isn't published as a single CSV; this file is most likely a manual aggregation from MoSPI press notes (e.g., NSO First Advance Estimates 2025-26, Provisional Estimates 2024-25, etc.). Per the user-approved domain-level provenance policy, default to `https://mospi.gov.in/` with a `name` of "MoSPI National Accounts Statistics (consolidated CSV from press-note vintages)". Confirm OK.
3. **Vintage carry-along** — do we want a `vintage` (revision tier) field per row, or just document "latest-final" in `methodology_vintage`? Per-row vintage is more honest (shows which years are still First Advance and might revise) but adds schema complexity. **Recommend**: per-row `vintage` field; bump indicator schema to v1.3 (additive — minor bump per CLAUDE.md §11) to add an optional `vintage` field on rows.
4. **Splice verification** — run a one-shot script that compares `current_price` for overlap years between the two base-year vintages. If they match within ≤0.5%, splice silently. If they diverge, abort and ask the user.
5. **`year` column normalisation** — early annual rows are `1999`, `2000`, `2001`... not `1999-00`. Treat as fiscal year starting that calendar year (i.e., `1999` → time `1999-04` = FY 1999-2000). Confirm with sample (`Gross Domestic Product` for `year=1999` should be ~₹19 lakh crore current).

---

## Estimated work

- Inspect schema to settle Q1/Q3 above.
- Write one ingest script (`tools/ingest_merged_aq.py`) that emits all 5 artifacts in one pass.
- Validate, write artifacts, delete the source CSV.
- Total: ~1 medium-size session.

## Decision needed from user

- Approve the 5-artifact split (vs. e.g., one-file-per-indicator, or single mega-artifact).
- Approve dropping growth-rate and subindustry rows.
- Approve the `mospi.gov.in` domain-level source URL.
- Approve the indicator-schema v1.3 minor bump for an optional row-level `vintage` field.
- Pick: ingest now, or wait until specific NAS questions surface in the UI roadmap.

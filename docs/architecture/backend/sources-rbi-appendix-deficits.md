# sources/rbi_appendix_deficits — RBI Appendix Table 1 (Major Deficit Indicators)

**Last Updated**: 2026-05-13
**Module**: `backend/yen_gov/sources/rbi_appendix_deficits/`
**CLI**: `python -m yen_gov ingest-fiscal-rbi-appt1`
**Schema**: `datasets/schemas/indicator.schema.json` (v1.1)

> **Sibling of** [`sources/rbi_appendix_national`](sources-rbi-appendix-national.md). Same RBI publication ("State Finances: A Study of Budgets"), different appendix table, different layout — gets its own parser.

## What it ships

Four all-India aggregate (country-entity, fiscal-year) deficit indicators sourced from **RBI Appendix Table 1: Major Deficit Indicators of State Governments**:

| Artifact (`datasets/indicators/in/fiscal/…`) | Indicator id | RBI workbook column |
| --- | --- | --- |
| `states_combined_gross_fiscal_deficit.json` | `fiscal/states_combined_gross_fiscal_deficit` | Gross Fiscal Deficit |
| `states_combined_revenue_deficit.json` | `fiscal/states_combined_revenue_deficit` | Revenue Deficit |
| `states_combined_primary_deficit.json` | `fiscal/states_combined_primary_deficit` | Primary Deficit |
| `states_combined_primary_revenue_deficit.json` | `fiscal/states_combined_primary_revenue_deficit` | Primary Revenue Deficit |

Each artifact has 20 rows (FY 2007-08 … 2025-26 BE; the latest two years are RE/BE). Values are nominal ₹ Crore (1 Crore = 10 million).

We **intentionally do not ship** the workbook's "Net RBI Credit to States" column — it is a niche monetary-policy indicator with no citizen-facing question that needs it.

We **also do not ship** the % GDP companion series interleaved on alternating rows in the same workbook. That would need a separate indicator family with `value_kind="percent"` and a separate normalisation; tracked in [`docs/concepts/long-coverage-indicators.md`](../../concepts/long-coverage-indicators.md) as a future expansion.

## Workbook layout (verified against `AppT1_MajorDeficitIndicators_2026.xlsx`)

The workbook is a single sheet (`APPT_1`) with this anatomy — note the empty leading column A:

```
r1:                                                              (title row)
r2:    | (₹ Crore)                                                (unit row)
r3:    | Year | Gross Fiscal Deficit | Revenue Deficit | …       (HEADER ROW)
r4:    |      | 1                    | 2               | 3 | 4 | 5  (col-index)
r5:    | 2007-08 | 75454.7  | -42942.7 | -24375.9 | -142773.4 | 1140
r6:    |         | -1.5     | (-0.9)   | (-0.5)   | (-2.9)    | 0    (% GDP)
r7:    | 2008-09 | 134589.3 | -12672.2 | 31634.5  | -115627   | -1608
r8:    |         | -2.4     | (-0.2)   | 0.6      | (-2.1)    | 0    (% GDP)
…
r39:   | 2024-25 (BE)$ | 1039138.1 | 80119.5 | 475606.6 | -483412.1 | -
```

Key invariants the parser depends on:

- Column **A is blank**; "Year" sits in column **B**, indicators in **C–G**.
- Each fiscal year occupies **two consecutive rows**: the year row (₹ Crore values) and the % GDP row immediately below (year-column blank). The parser identifies year rows by parsing column-B as a fiscal-year label; non-matching rows (including % GDP rows) are silently skipped.
- Year labels accept trailing qualifiers: `"2024-25 (BE)$"`, `"2023-24 (RE)"`, `"2025-26 (Budget Estimates)"`. The trailing `$` / `*` / `#` markers are RBI footnote pointers and are tolerated.
- Negatives may appear EITHER as `-12672.2` OR wrapped in parens `"(-0.9)"` (Indian accounting convention). The parser normalises both.
- Null-token cells (`"-"`, `"—"`, `"N.A."`, `".."`, blank) coerce to `null` in the artifact (the row is still emitted — coverage gap, not silent drop).

If RBI ever changes the column ordering or the alternating-row pattern, the parser raises `RBIAppT1ShapeError` rather than silently emitting wrong values. There is no fuzzy "best effort" fallback: a contract change must be confronted, not papered over.

## Sign convention

We keep RBI's published sign convention as-is:

- **Gross Fiscal Deficit**: positive when the consolidated states ran a deficit (the normal case).
- **Revenue Deficit**: positive when revenue expenditure exceeds revenue receipts (the worrying case); **negative when there is a revenue surplus** (the reassuring case — Indian states' early-FY10s typically show surpluses).
- **Primary Deficit**: positive = this year's discretionary policy adds to debt; negative = this year is paying down some inherited interest.
- **Primary Revenue Deficit**: usually negative (the strictest fiscal-discipline indicator) — meaning current receipts cover current spending after stripping out interest.

Each indicator's `direction` is `lower_is_better` so the frontend can rank "best fiscal hygiene = lowest deficit" without per-indicator special cases.

## Operator runbook

```powershell
# 1. Open the listing page in a browser
#    https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3A+A+Study+of+Budgets
#
# 2. Pick the latest "State Finances: A Study of Budgets" edition
#    (released annually, usually January for the FY immediately following).
#
# 3. Find the appendix workbook labelled
#    "Appendix Table 1: Major Deficit Indicators of State Governments"
#    and save it to:
#       .runtime/raw/rbi/state_finances/AppT1_MajorDeficitIndicators_<YYYY>.xlsx
#    where <YYYY> is the publication year of the edition.
#
#    (Optional: set $env:RBI_APPT1_DEFICITS_PATH to point at any other path.)
#
# 4. Re-run the ingest
.venv\Scripts\python.exe -m yen_gov ingest-fiscal-rbi-appt1
```

The adapter is **cache-only by design**: the operator owns when to refresh; the pipeline doesn't quietly re-fetch in CI. RBI's CDN occasionally rejects scripted UAs, and the Appendix workbook is a stable annual artifact — automated re-fetch would buy nothing.

## Why this is a separate adapter (and not an `AppendixSpec` extension)

`rbi_appendix_national` parses App T2: **rows = line items** (devolution, grants, transfers), **columns = fiscal years**. App T1 is the transpose: **rows = fiscal years** (with ₹ Crore + % GDP interleaved), **columns = deficit indicators**. The walking direction, the year-detection logic, and the duplicate-qualifier handling are all different. A single `AppendixSpec` shape would have grown a layout-flag matrix that obscures both adapters. Two narrow modules with shared schema and shared CLI namespace ("ingest-fiscal-rbi-…") was cleaner.

If a third RBI Appendix shape lands later (e.g. multi-sheet AppT3), it gets its own sibling module too. The bar is "different walking algorithm", not "different RBI publication".

## Tests

`backend/tests/test_sources_rbi_appendix_deficits.py` — 12 tests:

- **Happy path**: emits one row per year per indicator; year/indicator/value matrix matches the in-memory fixture.
- **Layout invariants**: `% GDP` rows skipped; qualified year labels (`"2023-24 (RE)"`, `"2024-25 (BE)$"`) parse to the correct start year.
- **Coercion**: comma-grouped numbers, paren-wrapped negatives, and null tokens (`"-"`, `"—"`, `"N.A."`, `".."`, `None`) all decode correctly.
- **Column resolution**: exact-match wins over substring (so `"primary deficit"` does NOT collide with `"primary revenue deficit"`).
- **Loud failures**: missing header row → `RBIAppT1ShapeError`; no year-rows below header → `RBIAppT1ShapeError`; unknown column label → `RBIAppT1ShapeError`. No silent zero-row artifacts.
- **Spec catalogue invariants**: `SHIPPED_SPECS` ids and column-match strings are distinct; the shipped indicator set is locked to the documented four (changing it requires touching this test).

Tests use in-memory `openpyxl.Workbook` fixtures — no captured XLSX files, no mocks, fully reproducible. CLAUDE.md §15 unit + contract tier coverage is satisfied; consumer-side contract validation lives in `backend/tests/test_validate.py` (whole-tree pass).

## Schema & provenance

Each artifact carries:

- `$schema` → `indicator.schema.json` v1.1
- `$schema_version` → `"1.1"`
- `sources` → single entry with the RBI publication landing-page URL (the direct workbook URL is edition-specific and rotates; the listing page is the stable canonical attribution).
- `coverage.spatial` → `"India (all-states aggregate)"`, `coverage.admin_level` → `"national"`.
- `indicator.entity_kind` → `"country"`, `indicator.time_grain` → `"fiscal_year"`, `indicator.value_kind` → `"currency"`, `indicator.unit` → `"INR (crore)"`.

`methodology_vintage` records the cached file's mtime so the artifact is self-describing about *which* RBI edition was ingested.

## Topic catalogue

Listed under the `fiscal` topic in [`datasets/reference/in/topic-catalogue.json`](../../../datasets/reference/in/topic-catalogue.json). `fiscal/states_combined_gross_fiscal_deficit` is `featured=true` (the headline deficit indicator citizens recognise from budget commentary). The other three are `featured=false` — they show up in the "more in this topic" rail rather than the topic-page hero strip.

## See also

- [sources-rbi-appendix-national.md](sources-rbi-appendix-national.md) — sibling adapter (App T2 transfers).
- [sources-rbi-xlsx.md](sources-rbi-xlsx.md) — per-state Statement adapter (same RBI publication, per-state granularity).
- [`docs/concepts/long-coverage-indicators.md`](../../concepts/long-coverage-indicators.md) — backlog ledger; this adapter discharges the "national fiscal deficits, ~17y+ history" entry.
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md) — `sources` array semantics.

# RBI Appendix Table — National Aggregates (`sources/rbi_appendix_national`)

**Last Updated**: 2026-05-13
**Module**: [`backend/yen_gov/sources/rbi_appendix_national/`](../../../backend/yen_gov/sources/rbi_appendix_national/)
**Topic**: `fiscal`
**See also**: [`sources-rbi.md`](sources-rbi.md) (per-state companion), [`sources-eci.md`](sources-eci.md), [`overview.md`](overview.md), [Holy Law #4](../../../CLAUDE.md), [Data Provenance](../../concepts/data-provenance.md)

## What this adapter does

Reads the **Appendix Tables** of RBI's *State Finances: A Study of Budgets* — the all-India companion to the per-state Statements that [`rbi_xlsx`](sources-rbi.md) parses. Each appendix workbook carries 1–3 sheets where rows are *items* (devolution, grants, transfers) and columns are *fiscal-year periods*. Stitching the sheets gives one continuous national time series spanning ~20 fiscal years.

**Two parsers in one source family by intent** (Holy Law #5):
- `rbi_xlsx` → row=state, column=year (per-state wide tables, one Statement per file).
- `rbi_appendix_national` → row=item, column=year (national time series, one Appendix per file).

A single workbook layout can host many indicators via one-line `AppendixSpec` entries — no parser-logic edits needed.

## Source workbooks

| File | Cached path | Edition stamp | Coverage | Status |
| --- | --- | --- | --- | --- |
| Appendix Table 2: Devolution and Transfer of Resources from the Centre | `.runtime/raw/rbi/state_finances/02_APP_devolution_transfers.xlsx` | January 2026 (State Finances 2025-26) | FY08 → FY26 (BE) | Shipped |
| AppT1: Major Deficit Indicators | `.runtime/raw/rbi/state_finances/AppT1_MajorDeficitIndicators_2026.xlsx` | January 2026 | FY08 → present | Cached, not yet wired |

### Operator recipe (resumability)

If `02_APP_devolution_transfers.xlsx` is missing from cache:

1. Open the [RBI State Finances listing page](https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3A+A+Study+of+Budgets).
2. Pick the latest publication (e.g. *State Finances: A Study of Budgets of 2025-26*).
3. Download the file labelled **"Appendix Table 2: Devolution and Transfer of Resources from the Centre"**.
4. Save as `.runtime/raw/rbi/state_finances/02_APP_devolution_transfers.xlsx` (relative to repo root) — the leaf name MUST match.
5. Re-run `python -m yen_gov ingest-fiscal-rbi-appendix --root .`

Alternative: set `$RBI_APPENDIX_NATIONAL_<INDICATOR>_PATH` (e.g. `RBI_APPENDIX_NATIONAL_NATIONAL_CENTRE_TRANSFERS_TOTAL_PATH`) to an absolute path and the cache lookup is bypassed.

## Indicator catalog

All entries below: `entity_kind=country`, `entity_id="IN"`, `time_grain=fiscal_year`, `value_kind=currency`, `unit="INR (crore)"`, `coverage.admin_level=national`. Source row in the workbook is the canonical authority — every fiscal year value is what RBI published, not derived.

| Indicator id | Workbook source | Coverage | Notes |
| --- | --- | --- | --- |
| `fiscal/centre_transfers_to_states_net` | App T2 Item VI ("Net Transfer of Resources from the Centre = IV-V") | FY08–FY26 (19 rows) | Headline net transfers — gross minus loan repayments and interest. Macro envelope view. |
| `fiscal/centre_transfers_to_states_tax_devolution` | App T2 Item I ("States' Share in Central Taxes") | FY08–FY26 (19 rows) | Constitutional Finance-Commission devolution stream. 41% share post-15thFC. |
| `fiscal/centre_transfers_to_states_grants` | App T2 Item II ("Grants from the Centre") | FY08–FY26 (19 rows) | Discretionary stream — CSS, Finance Commission grants, statutory grants. |
| `fiscal/centre_transfers_to_states_gross` | App T2 Item IV ("Gross Transfer = I+II+III") | FY08–FY26 (19 rows) | Headline gross transfers, before loan netting. |

Sub-component sub-totals (e.g. State Plan Schemes, Centrally Sponsored Schemes, Finance Commission Grants) are **not** shipped as separate indicators because the sub-categorisation is not stable across years (e.g. State Plan Schemes collapsed after FY15). Add them as new `AppendixSpec` entries only if comparability is acceptable for the user-facing question.

## Schema

Each artifact validates against [`indicator.schema.json`](../../../datasets/schemas/indicator.schema.json) v1.1. Country entities use the existing `entity_kind: country` enum value (no schema bump needed). Shape:

```json
{
  "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
  "$schema_version": "1.1",
  "sources": [
    { "url": "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+...",
      "fetched_at": "2026-05-11T14:50:50Z" }
  ],
  "license": { "id": "GoI-Open", ... },
  "coverage": {
    "spatial": "India (national aggregate)",
    "temporal": "2007-04..2025-04",
    "admin_level": "national"
  },
  "indicator": {
    "id": "fiscal/centre_transfers_to_states_net",
    "title": "Net Centre-to-States transfers (all-India)",
    "entity_kind": "country",
    "time_grain": "fiscal_year",
    "value_kind": "currency",
    "unit": "INR (crore)",
    "direction": "neutral",
    "comparability": "comparable_with_normalisation",
    "attribution_geography": "where_administered",
    "funding_split": { "centre_pct": 100, "state_pct": 0, ... },
    ...
  },
  "rows": [
    { "entity_id": "IN", "time": "2007-04", "value": 247299.2 },
    { "entity_id": "IN", "time": "2008-04", "value": 279124.2 },
    ...
  ]
}
```

The `sources` array cites only the RBI listing page (canonical attribution) rather than the edition-specific direct XLSX URL, because direct URLs rotate each publication; the listing page is stable and a citizen following the citation can reach the actual workbook in two clicks.

## Year qualifier dedupe

RBI ships the latest published year multiple times in one workbook (e.g. FY24 appears as both `"2023-24 (Accounts)"` and `"2023-24 (Budget Estimates)"`). The parser:

1. Captures every period's qualifier (`accounts` / `budget estimates` / `revised estimates` / none).
2. After scanning all sheets, collapses duplicate fiscal-year keys via `prefer_qualifier` (default `("accounts",)` — Accounts is the actual realised figure).
3. Emits one row per fiscal year, keyed by `_fy_to_period(start_year)` → `"YYYY-04"` (start-of-FY).

The latest two years RBI publishes are RE / BE only (no Accounts yet); those are kept as-is and the `notes` field flags them.

## Inflation caveat

All values are **nominal ₹ Crore** as RBI publishes them. They are NOT deflated to constant prices. A 3× rise from FY08 to FY26 reflects price level changes as much as real flow changes — citizens reading the chart should hold an inflation context (CPI roughly doubled in this window). A future indicator `fiscal/centre_transfers_to_states_net_constant_2011_12` (deflated) is in the backlog ([long-coverage backlog](../../concepts/long-coverage-indicators.md)).

## Tests

Pure-parser tests in [`backend/tests/test_sources_rbi_appendix_national.py`](../../../backend/tests/test_sources_rbi_appendix_national.py): 32 cases covering period parser, value coercion (paren-negatives, comma-grouping, null tokens), header detection (requires "Item" + ≥2 fiscal-year columns), 3-sheet stitching, qualifier dedupe with preference fallback, notes-row skipping, three shape-error paths, SHIPPED_SPECS sanity (unique IDs, slug pattern, distinct row resolution).

Synthetic in-memory workbooks via openpyxl — no real RBI bytes touch the test suite (Holy Law #7).

## Why this is a separate module from `rbi_xlsx`

Same publication, different table shape, different entity kind (`country` vs `state`), different metadata flavor (no per-state ECI normalisation, no `unmatched_states` field, no funding_split state %, different comparability semantics). Folding it into `rbi_xlsx` would require a `mode` flag and `if mode == ...` branches in every helper — the kind of optionality that becomes load-bearing within two more indicators. Two modules, one for each shape, costs nothing and reads cleanly.

## Adding the next indicator from the same workbook

1. Add an `AppendixSpec` entry to `SHIPPED_SPECS` in [`parsers.py`](../../../backend/yen_gov/sources/rbi_appendix_national/parsers.py).
2. Add a matching `IndicatorMeta` to `INDICATOR_META` in [`ingest.py`](../../../backend/yen_gov/sources/rbi_appendix_national/ingest.py).
3. Add a catalogue entry under the relevant topic in [`datasets/reference/in/topic-catalogue.json`](../../../datasets/reference/in/topic-catalogue.json).
4. Run `python -m yen_gov ingest-fiscal-rbi-appendix --root .` then `python -m yen_gov validate --root .`
5. Update the indicator catalog table above.

## Adding the next workbook (different Appendix file)

Today the resolver hardcodes `CACHE_RELPATH` to Appendix Table 2. To wire AppT1 (Major Deficit Indicators) or another appendix:

1. Promote `CACHE_RELPATH` to a per-spec field on `AppendixSpec` (or a parallel registry keyed by indicator id).
2. Add the new file's operator recipe to the **Source workbooks** table above.
3. Add specs/metas as in the previous section.

This refactor is queued behind the first multi-workbook ship (likely AppT1 deficit indicators) and is documented in [the long-coverage backlog](../../concepts/long-coverage-indicators.md).

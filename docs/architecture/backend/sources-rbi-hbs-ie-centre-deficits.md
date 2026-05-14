# sources/rbi_hbs_ie_centre_deficits — RBI HBS-IE Table 89 (Centre's Key Deficit Indicators)

**Module**: `backend/yen_gov/sources/rbi_hbs_ie_centre_deficits/`
**Schema**: `datasets/schemas/indicator.schema.json` (v1.3)

> **Sibling-by-shape of** [`sources/rbi_appendix_deficits`](sources-rbi-appendix-deficits.md). Different RBI publication (Handbook of Statistics on Indian Economy, not State Finances), different fiscal actor (Union Government, not states-combined) — but identical workbook layout, so we **import** `parse_workbook` from the AppT1 sibling and only ship a thin orchestrator + Centre-flavoured indicator metadata.

## Why it exists

ADR-0025 (Step B) renamed the legacy `fiscal/national_*` ids to actor-explicit prefixes (`fiscal/states_combined_*_deficit` and `fiscal/centre_transfers_to_states_*`), and that rename surfaced a real gap: yen-gov shipped four states-combined deficit indicators but **zero Union (Centre's own) deficit indicators**. Reserved-prefix research found the matching `fiscal/union_*` slot was empty.

Without this adapter, ranked deficit tables in the frontend silently misframe responsibility: states-combined GFD ~3% of GDP looks alarming until you realise the Centre's own GFD is ~6% of GDP and never shows up beside it. Citizens encountering only the states-side data get the Hans Rosling "Blame instinct" reading — that states are profligate while the Centre only sends money out. This adapter ships the symmetric Union series so the picture isn't lopsided. See [`docs/concepts/fiscal-actor-naming.md`](../../concepts/fiscal-actor-naming.md) for the chart-trap warning in full.

## What it ships

Four Union-Government, country-entity, fiscal-year deficit indicators sourced from **RBI Handbook of Statistics on Indian Economy, Table 89: Key Deficit Indicators of the Central Government**:

| Artifact (`datasets/indicators/in/fiscal/…`) | Indicator id | RBI workbook column |
| --- | --- | --- |
| `union_gross_fiscal_deficit.json` | `fiscal/union_gross_fiscal_deficit` | Gross Fiscal Deficit |
| `union_revenue_deficit.json` | `fiscal/union_revenue_deficit` | Revenue Deficit |
| `union_primary_deficit.json` | `fiscal/union_primary_deficit` | Gross Primary Deficit |
| `union_primary_revenue_deficit.json` | `fiscal/union_primary_revenue_deficit` | Primary Revenue Deficit |

Each artifact has 40 rows (FY 1986-87 … 2025-26 BE; the latest two years are RE/BE per the workbook's own footnote 1). Values are nominal ₹ Crore.

We **intentionally do not ship** four other columns the workbook publishes:

- **Net Fiscal Deficit** and **Net Primary Deficit** — financing-side adjusted variants of the gross figures; "Gross" is the headline number citizens encounter in Budget commentary, and the gross↔net delta is itself a financing-flow concept outside the deficit-indicator scope.
- **Drawdown of Cash Balances** and **Net RBI Credit** — monetary-policy series that share the workbook for editorial convenience but answer different questions.

### Naming caveat: "Gross Primary Deficit" → `fiscal/union_primary_deficit`

RBI HBS-IE Table 89 labels the standard Primary Deficit (= GFD − interest payments) as "**Gross** Primary Deficit" to distinguish it from the financing-adjusted "Net Primary Deficit". Standard Indian fiscal usage without modifier ("the primary deficit was X% of GDP") refers to the gross variant. We therefore map:

- HBS-IE column `Gross Primary Deficit` → indicator id `fiscal/union_primary_deficit`

…matching the states-combined sibling (`fiscal/states_combined_primary_deficit`, sourced from RBI Appendix Table 1's `Primary Deficit` column, which has no Gross/Net split). Symmetric ids on both sides; the source-column-label asymmetry is documented in each artifact's `notes` field.

## Workbook layout (verified against `T89_KeyDeficitIndicators_Centre_2025.xlsx`)

Single sheet (`T_89`), 53 rows × 10 columns, with this anatomy (note the empty leading column A):

```
r1:    (blank)
r2:    | TABLE 89 : KEY DEFICIT INDICATORS OF THE CENTRAL GOVERNMENT
r3:    | (₹ Crore)
r4:    | Year | Gross Fiscal Deficit | Net Fiscal Deficit | Gross Primary Deficit | Net Primary Deficit | Revenue Deficit | Primary Revenue Deficit | Drawdown of Cash Balances | Net RBI Credit
r5:    | 1    | 2                    | 3                  | 4                     | 5                   | 6               | 7                       | 8                          | 9                (col-index)
r6:    | 1986-87 | 26342 | 17036 | 17096 | 13143 | 7777 | -1469 | 8261 | 7091
…
r45:   | 2025-26 | 1568936 | 1372092 | 292598 | 143492 | 523846 | -752492 | 2484 | -
r46:   | Notes : 1. Data for 2024-25 are RE; for 2025-26 are BE. …          (footnote rows)
```

This is structurally identical to AppT1 except: (a) **no alternating %-of-GDP row** between fiscal years, (b) **eight indicator columns instead of five**, and (c) **40 years of history instead of 20** (HBS-IE goes back to 1986-87; AppT1 starts FY07-08). The shared parser handles all three differences transparently — the column-index row is filtered by year-cell `_parse_period` returning `None` for `"1"`, the eight columns are addressed by `column_label_match` strings on `DeficitSpec`, and the year-row loop just runs more iterations.

If RBI ever changes the column ordering or label wording, the parser raises `RBIAppT1ShapeError` (raised from the shared sibling parser) rather than silently emitting wrong values.

## Sign convention

Same as the states-combined sibling — RBI's published convention is preserved as-is:

- **Gross Fiscal Deficit**: positive when the Centre ran a deficit (the normal case).
- **Revenue Deficit**: positive when revenue expenditure exceeds revenue receipts; **negative when there is a revenue surplus** (rare for the Union; visible in the early 1990s and 2007-08).
- **Primary Deficit**: positive = this year's discretionary policy adds to debt; negative = this year is paying down some inherited interest. Notable negative episodes: 2003-04, 2004-05, 2006-07, 2007-08.
- **Primary Revenue Deficit**: typically negative (= primary revenue surplus) for sustained stretches — most of 1986-2007 and again 2013-2019. The strictest fiscal-discipline indicator.

Each indicator's `direction` is `lower_is_better` so the frontend can rank "best fiscal hygiene = lowest deficit" without per-indicator special cases.

## Operator runbook

```powershell
# 1. Open the listing page in a browser
#    https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy
#
# 2. Pick the latest "Handbook of Statistics on the Indian Economy" edition
#    (released annually, usually August/September for the FY just closed).
#
# 3. Find Table 89: "Key Deficit Indicators of the Central Government"
#    and save the XLSX to:
#       .runtime/raw/rbi/hbs_ie/T89_KeyDeficitIndicators_Centre_<YYYY>.xlsx
#    where <YYYY> is the publication year of the edition.
#
#    Convenience: the 2024-25 edition direct URL is recorded as
#    PINNED_XLSX_URL_2024_25 in the adapter module and can be fetched via:
#       python tools/rbi_download.py <url> .runtime/raw/rbi/hbs_ie/T89_KeyDeficitIndicators_Centre_2025.xlsx
#    (RBI's CDN rejects naive UAs; rbi_download.py sends a Chrome-style UA + Referer.)
#
#    (Optional: set $env:RBI_HBS_IE_T89_PATH to point at any other path.)
#
# 4. Re-run the ingest from a Python REPL or pipeline command:
.venv\Scripts\python.exe -c "from pathlib import Path; from yen_gov.sources.rbi_hbs_ie_centre_deficits.ingest import ingest; ingest(repo_root=Path('.'), schema_dir=Path('datasets/schemas'))"
```

The adapter is **cache-only by design** (same rationale as the AppT1 sibling): the operator owns when to refresh; the pipeline doesn't quietly re-fetch in CI. HBS-IE is a stable annual publication.

## Why this adapter shares a parser instead of cloning it

The HBS-IE Table 89 layout is a strict subset of the AppT1 layout (no %-GDP rows; everything else identical). Cloning `parse_workbook` would duplicate ~280 lines of column-resolution and value-coercion logic for a zero-behavioural-difference outcome. We therefore `from yen_gov.sources.rbi_appendix_deficits.parsers import parse_workbook, DeficitSpec, ParsedIndicator` and let the shared parser walk both publications. The two adapters remain distinct **modules** (separate cache paths, separate listing URLs, separate exception classes, separate INDICATOR_META, separate operator runbooks) — only the dumb byte-walking is shared.

If RBI ever changes one publication's layout without changing the other, the shared parser raises and we fork. Until then, one parser, two callers.

## Tests

`backend/tests/test_sources_rbi_hbs_ie_centre_deficits.py` — 7 adapter-level tests (parser-level coverage lives in `test_sources_rbi_appendix_deficits.py`):

- **Spec catalogue invariants**: shipped specs are exactly the four `union_*_deficit` ids, distinct, every spec has matching `INDICATOR_META`.
- **Cache-missing operator recipe**: `RBIHBSIET89CacheMissing` raised with a message that mentions the listing page URL, the cache-relative path, and the env-override variable.
- **Env-override surface**: `$RBI_HBS_IE_T89_PATH` pointing at a non-existent path raises the same exception.
- **End-to-end ingest**: against an in-memory T89-shaped workbook (built via openpyxl, mirrors the real header rows + 8 indicator columns), ingest writes four schema-valid artifacts under a `tmp_path` repo root, with the correct Centre-actor framing (`implementing_authority="centre"`, `funding_split.centre_pct=100`, `coverage.spatial="India (Union Government)"`).
- **Column-mapping correctness**: the `Gross Primary Deficit` column lands in `union_primary_deficit` (NOT `Net Primary Deficit`).
- **Sign preservation**: a negative input value (e.g. primary revenue surplus -298656) round-trips as a negative artifact value, not absolute or zero.

No fixture XLSX files; in-memory workbooks only; no mocks. CLAUDE.md §15 unit + contract tier coverage is satisfied; consumer-side schema validation runs in `tests/test_validate.py`.

## Schema & provenance

Each artifact carries:

- `$schema` → `indicator.schema.json` v1.3
- `$schema_version` → `"1.3"`
- `sources` → single entry with the HBS-IE landing-page URL (the direct workbook URL is edition-specific and rotates per publication; the listing page is the stable canonical attribution — same convention as the AppT1 sibling). The pinned per-edition direct URL is recorded as `PINNED_XLSX_URL_2024_25` in the module for operator reproducibility.
- `coverage.spatial` → `"India (Union Government)"`, `coverage.admin_level` → `"national"`.
- `indicator.entity_kind` → `"country"`, `indicator.time_grain` → `"fiscal_year"`, `indicator.value_kind` → `"currency"`, `indicator.unit` → `"INR (crore)"`.
- `indicator.implementing_authority` → `"centre"`; `indicator.funding_split` → `{centre_pct: 100, state_pct: 0, source: "definition (Union Government's own budgetary deficit)"}`.

`methodology_vintage` records the cached file's mtime so the artifact is self-describing about *which* HBS-IE edition was ingested.

## Topic catalogue

The four ids are registered under the `fiscal` topic in `datasets/reference/in/topic-catalogue.json`, with `union_gross_fiscal_deficit` marked `featured: true` (mirroring the states-combined GFD as the headline of each actor family). The catalogue note for the `fiscal` topic is updated to call out the symmetric pairing and the chart-trap warning.

`datasets/reference/in/upstream-sources.json` adds an `rbi.hbs_ie_t89_centre_deficits` entry citing the listing URL and all four shipped indicator ids.

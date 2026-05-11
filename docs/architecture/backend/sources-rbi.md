# RBI as a fiscal-indicator source

**Last Updated**: 2026-05-11
**Status**: SPEC — no ingest implemented yet. This document fixes the contract so the future ingest commit is a small mechanical step instead of a design discussion.

> Per [docs/concepts/cross-state-comparison.md](../../concepts/cross-state-comparison.md), `fiscal/` is the **first** indicator family yen-gov should ship after the energy pilot. Fiscal data is the baseline that contextualises every other social and economic indicator: a state with `own-tax / GSDP = 4%` is not playing the same game as one at `7%`, and aggregators that hide this lie by omission.

## Why RBI, not MoSPI or NITI Aayog

The Reserve Bank of India publishes **State Finances: A Study of Budgets** annually (around December) covering the most recent budget cycle. The study is the canonical source for cross-state fiscal comparison because:

1. **Apples-to-apples reframe.** RBI re-classifies each state's own budget into a uniform schema, so Maharashtra's "Other Revenue Receipts" line and Tamil Nadu's are directly comparable. The state budgets themselves are not — formatting and account-head taxonomy differ across states and across years within the same state.
2. **Three-year strip.** Each annual study gives Actuals (T-2), Revised Estimates (T-1), and Budget Estimates (T-0). That alone is the trajectory primitive a citizen needs.
3. **Single PDF + a downloadable Excel companion.** The Excel companion (`Statements_*.xlsx` / `Annexures_*.xlsx`) is the machine-readable surface — the PDF is for narrative.
4. **No license fee, no API quota.** Public document under the RBI's open-publication norm.

NITI Aayog dashboards are derivative of RBI data and update later. State-level press releases are not normalised. MoSPI's National Accounts give GSDP (which we'll need as the denominator) but not fiscal aggregates.

## Source URLs

The annual study lives at `https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3A+A+Study+of+Budgets`. Each year produces a new edition; the URL pattern for the underlying PDF and Excel attachments is volatile (`Statements_<dd><MMM><yy>.xlsx` / `Annexures_<dd><MMM><yy>.xlsx`) and the recon step MUST capture the exact URL of each artifact at fetch time and pin it in `sources[]`.

The Handbook of Statistics on Indian States (`https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States`) is the secondary cross-check — it carries longer time series for headline aggregates (GSDP, own-tax revenue, etc.) but does not break down the budget head structure.

## Planned indicators

Eight indicators in the first cut. Each has its honesty fields pre-declared here so the implementation commit is mechanical.

### `own_tax_revenue_pct_gsdp`

| Field | Value |
|---|---|
| `id` | `in.fiscal.own_tax_revenue_pct_gsdp` |
| `title` | Own-tax revenue (% of GSDP) |
| `entity_kind` | `state` |
| `time_grain` | `fiscal_year` |
| `value_kind` | `share` |
| `unit` | `% of GSDP` |
| `direction` | `higher_is_better` |
| `scale_hint` | `linear` |
| `denominator` | `gsdp_current_prices` |
| `attribution_geography` | `where_administered` |
| `comparability` | `comparable_across_states` |
| `funding_split` | `{centre_pct: 0, state_pct: 100, source: "definition"}` |
| `implementing_authority` | `state` |
| `methodology_vintage` | `RBI re-classification, Statement 6 (Revenue Receipts)` |
| `icon` | `coins` |
| `series_breaks` | `[{at_time: "2017-18", kind: "definition_change", note: "Pre-GST own-tax includes central sales tax + entry tax + entertainment tax; post-GST these subsume into SGST. Trends across the break should be read as a regime shift, not a behaviour shift."}]` |

This is the **flagship**: it answers "how much of its own economic activity does this state convert into government capacity?" State capacity is upstream of every public service. Suppress neither the GST series break nor the GSDP base-year revisions — both lie if hidden.

### `revenue_deficit_pct_gsdp`

| Field | Value |
|---|---|
| `id` | `in.fiscal.revenue_deficit_pct_gsdp` |
| `direction` | `lower_is_better` (a positive value = deficit) |
| `unit` | `% of GSDP` |
| `notes` | "A revenue deficit means the state is borrowing to pay salaries and pensions, not to build assets. The Fiscal Responsibility and Budget Management (FRBM) targets call for zero." |
| `comparability` | `comparable_across_states` |
| `icon` | `trending-up` (the bad kind — direction handles colour) |

### `gross_fiscal_deficit_pct_gsdp`

Same structure as above; FRBM ceiling is 3% GSDP for states. Sign convention: positive = deficit. Direction = `lower_is_better`.

### `outstanding_debt_pct_gsdp`

| `direction` | `lower_is_better` |
| `series_breaks` | `[{at_time: "2003-04", kind: "frame_change", note: "FRBM Act 2003 imposed first hard ceiling; pre-2003 series uses different consolidation rules."}]` |

### `interest_payments_pct_revenue_receipts`

A first-order proxy for fiscal stress. When this exceeds ~20%, debt servicing crowds out development spending. Direction = `lower_is_better`. Comparability = `comparable_across_states`.

### `capital_outlay_pct_gsdp`

What the state actually invested in fixed assets — schools built, irrigation channels dug, hospitals expanded. Direction = `higher_is_better`. Comparability = `comparable_with_normalisation` (per-capita matters more than per-GSDP for some uses).

### `own_non_tax_revenue_pct_gsdp`

Royalties (mining), state-PSU dividends, user charges. Some states (Odisha, Jharkhand, Chhattisgarh) lean heavily on mineral royalties, which is a different fiscal posture than Tamil Nadu's heavy own-tax base.

| `attribution_geography` | `where_produced` (mineral royalties accrue where extraction happens) |
| `notes` | "Mineral-royalty-heavy states should not be ranked head-to-head with manufacturing/services states without a caveat. The choropleth and ranked-table will both show the comparability=comparable\_with\_normalisation banner." |
| `comparability` | `comparable_with_normalisation` |

### `central_transfers_pct_revenue_receipts`

The flip side of own-tax: how dependent is each state on central devolution + grants? Direction = `neutral` (high dependence is not inherently bad — it's by Constitutional design that poorer states get more devolution). Suppress rank entirely; this is a context indicator, not a leaderboard.

| `comparability` | `not_comparable_across_states` |
| `notes` | "By design, central transfers are higher for states with lower own-revenue capacity (Finance Commission horizontal devolution formula). A high value is not a state failure." |

## Ingest plan

1. **Recon.** A maintainer downloads the latest *State Finances* Excel companion + the *Handbook of Statistics on Indian States* Excel into `.runtime/raw/rbi/<yyyy-mm-dd>/`. Per CLAUDE.md §2 these are throwaway debug artifacts; they do **not** appear in `sources[]` of the published indicator. The exact RBI URLs go into the indicator artifact's `sources[]` with `fetched_at` set to the maintainer's download time. (Until we automate fetching, "fetch" includes manual download — the artifact still cites real URLs because that is where the bytes came from.)

2. **Parser.** A new `backend/yen_gov/sources/rbi_xlsx/` module reads the Excel companion. Each Statement (`Statement 6`, `Statement 9`, etc.) maps to one or more indicators. The parser emits **one indicator artifact per indicator id** under `datasets/indicators/in/fiscal/`, not one giant artifact. Per-indicator files keep the on-the-wire payload small and let each indicator carry its own series_breaks / methodology_vintage cleanly.

3. **GSDP denominator.** Indicator artifacts that quote `% of GSDP` need GSDP figures, which RBI's Handbook of Statistics on Indian States carries (`Statement 12: Gross State Domestic Product at Current Prices`). The parser pulls these once and caches them as a private side artifact under `.runtime/cache/`; it is **not** a published indicator (we'd want a separate `in.economy.gsdp_current_prices` indicator for that, in the next ingest pass).

4. **Schema validation.** Each emitted artifact runs through `python -m yen_gov validate` before commit. The validator already enforces `$schema_version = 1.1` for indicator artifacts.

5. **Wire-up.** Once the eight artifacts land, `frontend/src/routes/StateOverview.svelte` gains a `<section>` titled "Fiscal capacity" containing one `<IndicatorChoropleth>` + `<IndicatorRanked>` + `<IndicatorSmallMultiples>` triple per indicator. No new component code — the metadata-driven primitives carry it.

## Honesty register (things to NOT do)

- **Do not** create a composite "fiscal health index" by averaging these eight. Each captures a distinct trade-off; the average hides the trade-off. (Same reason `category_index` is off the roadmap per [cross-state-comparison.md](../../concepts/cross-state-comparison.md).)
- **Do not** silently switch denominator base years. RBI revises the GSDP base every ~5 years (currently 2011-12); when 2025-26 base lands, the artifact's `methodology_vintage` and `series_breaks` MUST be updated in the same commit.
- **Do not** rank `central_transfers_pct_revenue_receipts`. It is a context indicator. The schema enforces this via `comparability=not_comparable_across_states` and IndicatorRanked / IndicatorChoropleth both already suppress rank/comparison framing in that case.
- **Do not** include UTs in the ranked-table default view. UT fiscal accounts are constitutionally distinct (no separate GSDP, central administration). They get the optional `include_special` toggle once `state.tier` is backfilled per ADR-0020.

## See also

- [docs/concepts/cross-state-comparison.md](../../concepts/cross-state-comparison.md) — why fiscal is family #1
- [docs/architecture/frontend/indicators.md](../frontend/indicators.md) — the metadata-driven rendering contract
- [docs/architecture/decisions/0020-indicator-artifact-as-data-contract.md](../decisions/0020-indicator-artifact-as-data-contract.md) — the v1.1 honesty fields

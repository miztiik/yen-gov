# RBI State Finances (e-STATES) ingest + fiscal indicator definitions

**Last Updated**: 2026-06-25

**Status**: PLANNED - authored decision + indicator definitions; the reader and the crosswalk are not yet built. This doc is the contract an implementing agent (or the operator) turns into specs.

**Source**: RBI, *State Finances: A Study of Budgets* - the **e-STATES Database** download
(<https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3a+A+Study+of+Budgets>)

**Owner**: data layer (Hans + Max own indicator shape; Gregor owns the reader contract; Fowler owns the write seam and the expand-migrate-contract re-source)

**See also**: [state-fiscal-health](../../concepts/state-fiscal-health.md) (the indicator vocabulary this source feeds), [sources-rbi-handbook](sources-rbi-handbook.md) (the *other* RBI publication - keep them distinct), [data-spine](../../concepts/data-spine.md), [data-provenance](../../concepts/data-provenance.md), [indicator-naming](../../concepts/indicator-naming.md), [pre-flight-ingest](../../concepts/pre-flight-ingest.md), [data-coverage-report](../../reference/data-coverage-report.md).

> **Two different RBI publications - do not conflate.** *State Finances: A Study of Budgets* (this doc - the fiscal/budget publication, the e-STATES Database) is distinct from the *Handbook of Statistics on Indian States* ([sources-rbi-handbook](sources-rbi-handbook.md) - the broad socio-economic publication driven by [TODO/20260625-rbi-handbook-data-capture-and-goals-plan.md](../../../TODO/20260625-rbi-handbook-data-capture-and-goals-plan.md)). Where the two overlap on fiscal facts, **State Finances is authoritative** (see [Coordination](#9-coordination-with-the-handbook-plan)).

## 1. What this source is (confirmed on the real file)

The **e-STATES Database** is a single XLSX the RBI publishes on the State Finances page. The 2025-26 edition file (`ESTATES...XLSX`, ~13.6 MB) was explored directly. It is a **long-format database dump**, not a per-table workbook:

- Sheet `Data`: **397,575 rows x 7 columns**. Columns: `Appendix | State/UT | Budget Head | Fiscal Year | Account | Revised | Budget`.
  - `Account` = audited Actuals; `Revised` = Revised Estimate (RE); `Budget` = Budget Estimate (BE). Non-empty counts: Account ~374k, Revised ~264k, Budget ~264k.
- Sheet `Note`: data spans **1990-91 to 2025-26 (36 fiscal years)**; pre-2017-18 the "All States/UTs" aggregate **excludes** UTs (except 2000-01 to 2004-05 which include NCT Delhi); 2017-18 onward includes all states and UTs.
- **32 entities**: 31 states/UTs plus an "All States/UT" aggregate (each ~12,424 rows).
- **Four detailed budget appendices** (357 distinct budget heads total):

| Appendix | RBI title | Heads | What it carries |
| -------- | --------- | :---: | --------------- |
| Appendix-1 | Revenue Receipts | 96 | Own Tax (SGST, State Excise, Stamps, Vehicles, Electricity duty...), Share in Central Taxes, Own Non-Tax, Grants from the Centre -> `Total: TOTAL REVENUE (I+II)` |
| Appendix-2 | Revenue Expenditure | 78 | Developmental (Social + Economic services by function), Non-Developmental (Interest Payments, Administrative, Pensions), Grants-in-Aid -> `Total: TOTAL EXPENDITURE (I+II+III)` |
| Appendix-3 | Capital Receipts | 61 | Internal Debt (market loans, NSSF, WMA from RBI), Loans from the Centre, Recovery of Loans, Public Account |
| Appendix-4 | Capital Disbursements | 122 | A deficit/financing block (Revenue / Capital / Overall surplus-deficit) + `Total Capital Outlay`, Discharge of Internal Debt, Repayment of Loans to the Centre, Loans and Advances |

This single file IS the long-format consolidation of the per-edition **Appendices I-IV** the same RBI page also offers as per-edition, four-state-chunk XLSX files.

## 2. Provenance doctrine

Unlike the Handbook (where RBI is a re-publisher of SRS/ORGI vital rates), *State Finances: A Study of Budgets* is **RBI's own analytical compilation** - RBI standardises 28+ state budget documents into one cross-state-comparable budget-head taxonomy. RBI is therefore the `producer`:

```text
producer = Reserve Bank of India
title    = State Finances: A Study of Budgets (e-STATES Database)
vintage  = <edition, e.g. 2025-26>
url      = https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3a+A+Study+of+Budgets
```

`source_id` is **derived** from the `(producer, title, vintage)` triple via `citation.derive_source_id` - never hand-authored (Holy Law #9, [data-provenance](../../concepts/data-provenance.md)).

## 3. The supersede ruling (Max + Hans, converged 2026-06-25)

The user's question was: *does this one master file supersede the many URL tables - can we keep just this one file?* The answer is a precise split.

- **Per-edition Appendix I-IV chunk files -> YES, superseded.** The e-STATES Database is the same four appendices, pre-assembled across all 32 entities and 36 years. Holding both is exactly the methodology drift the [data-spine](../../concepts/data-spine.md) forbids (different editions silently revise old years). **Keep the one e-STATES file; do not ingest the per-edition appendix chunks.**
- **The derived-ratio Statements (1-37) and Appendix Tables (1-13) -> NOT superseded, but mostly DERIVED not re-fetched.** e-STATES carries the raw budget lines, not the ratios. Because yen-gov already holds per-state GSDP back to FY1994-95, the headline ratios (GFD/GSDP, RD/GSDP, own-tax/GSDP, IP/RR) are **computed by us from the e-STATES levels** - more transparent (the citizen sees level and ratio), one fewer source to keep in sync, and the publisher's own Statement 1 ("Major Fiscal Indicators") is kept only as a **validation oracle**.
- **Genuinely non-derivable items -> KEEP as separate, thinner ingests.** Outstanding Liabilities (debt **stock**, Statement 18-20) is already loaded from the right source and is NOT in e-STATES (a budget carries debt *flows*, not the cumulative stock). Outstanding **Guarantees** (Statement 28, contingent liabilities) is not in e-STATES and not derivable - a deferred gap.

One-line ruling: **keep one e-STATES file for the budget-flow picture; derive the ratios from it plus our GSDP; keep the debt-stock and guarantees statements separate.**

## 4. File anatomy that drives the indicator definitions

Exact aggregate budget-head strings (verbatim, for the crosswalk) and the two reconciliations that were checked on the real file:

- `Total: TOTAL REVENUE (I+II)` (App-1) and `Total: TOTAL EXPENDITURE (I+II+III)` (App-2, which is total **revenue** expenditure).
- **Revenue Deficit is exactly derivable:** `TOTAL EXPENDITURE (App-2) - TOTAL REVENUE (App-1)`. Verified to the paisa against App-4 `A: Surplus (+)/Deficit (-) on Revenue Account` (-61542.18 for All States/UT, FY2022-23, Account).
- **Gross Fiscal Deficit is NOT the App-4 "Overall" line.** App-4 `C: Overall Surplus (+)/Deficit (-) (A+B)` is the conventional cash/budgetary deficit (-26,774 cr for All States/UT FY2022-23) - far smaller than the true all-states GFD. **Do not map gross-fiscal-deficit to App-4 "C".** GFD must be reconstructed:

  ```text
  GFD = (Revenue Expenditure + Capital Outlay + Net Lending)
        - (Revenue Receipts + Non-debt Capital Receipts)
      = TOTAL EXPENDITURE (A2)
        + "I: Total Capital Outlay (1 + 2)" (A4)
        + "IV: Loans and Advances by State Governments (1+2)" (A4)
        - TOTAL REVENUE (A1)
        - "III: Recovery of Loans and Advances (1 to 12)" (A3)
        - disinvestment / non-debt misc capital receipts (A3)
  ```

  Validate the reconstruction against RBI Statement 1 GFD per state-year; surface material divergence (a perimeter difference in public-account treatment), never silently pick.
- **No "Salaries" budget head exists** in App-2 (salaries are object-heads spread across every function). So "committed expenditure (salaries + pensions + interest)" can only ship as a **partial Interest + Pensions proxy**, explicitly labelled (indicator #12 below).

## 5. Estimate-stage handling (Account / Revised / Budget)

Per [owid-alignment](../../concepts/owid-alignment.md) named divergence #8, the estimate stage is a methodology/vintage axis and **must not become a dimension/facet column**. Actuals (`Account`) end at **FY2023-24** on this edition; FY2024-25 is RE and FY2025-26 is BE.

**Ruling:** coalesce to **one value per (entity, year, measure), preferring Account > Revised > Budget**. This keeps the firmest available value for every historical year AND retains the newest one or two years (which exist only as RE/BE) instead of dropping them. The chosen stage is carried as **per-row provenance** (a stage marker / `processing_note`), surfaced in the tooltip, with the RE/BE tail rendered visually distinct. A stage facet *inside one card* is an optional later enhancement for the deficit and capex indicators only, where the Budget-vs-Actuals gap is itself the story - never three separate indicators. See trap #1 in [state-fiscal-health](../../concepts/state-fiscal-health.md).

## 6. Entity continuity and methodology breaks

- **Key every row on the LGD-slug `entity_id`, never the "State/UT" text** (data-spine non-negotiable #2). Resolve via [datasets/data/entities/geo.csv](../../../datasets/data/entities/geo.csv).
- **Bifurcation back-projection.** e-STATES back-projects reorganised states to 1990-91 (verified: Telangana carries 34 years of Actuals, identical to Andhra Pradesh). Carry the existing AP/Telangana (FY2014-15), Chhattisgarh/Jharkhand/Uttarakhand (FY2000-01), and J&K-UT (FY2019-20) coverage-change badges already documented in [data-coverage-report section 5d](../../reference/data-coverage-report.md).
- **The "All States/UT" aggregate has a real 2017-18 definition break** (UT inclusion). Preferred: **recompute the national rollup ourselves** from the comparable per-state set so it is methodology-stable end to end (`*-national.csv` grain, `entity_kind=country`). If RBI's published aggregate is carried instead, it MUST get a `methodology_breaks` row at 2017-18 rendered as a visible break on the line with hover-delta disabled across it.
- **MoSPI GSDP rebases** (1993-94 / 1999-2000 / 2004-05 / 2011-12) propagate into any derived `/GSDP` ratio - carry the same break markers on the ratios.

## 7. Ingest shape (Max + Hans preference; Fowler owns the final engineering call)

**Build a dedicated long-format e-STATES reader; do NOT stretch the wide-table `HbsTableSpec` system.** The `rbi_handbook` adapter parses WIDE `state x period` matrices (one matrix per indicator); e-STATES is the opposite shape - ONE long file whose rows fan out to many indicators via `(Appendix, Budget Head)`. The structural fit is:

- a single reader that loads the `Data` sheet, and
- a **committed `(appendix, budget_head) -> indicator_id` crosswalk** (the explicit, auditable curation surface that filters 357 heads down to the ~12-14 headline rows). This is the OWID "one upstream dump, many curated variables via a crosswalk" pattern; the crosswalk is a data-layer artifact, not buried in spec code.

The reader: filter to crosswalk heads -> resolve `entity_id` -> coalesce Account/RE/BE -> emit `datasets/data/datapoints/geo/<indicator_id>.csv` + upsert `variables.csv` / `concepts.csv` / `entities/source.csv`. **Cadence `update_period_days = 365`; full-replace UPSERT** on `(entity_id, year, indicator_id)` (a year migrates BE -> RE -> Actuals across three successive editions - ingest doctrine D4). Do not pre-create the reader or the crosswalk file before the implementing PR (no empty-module anti-pattern); this doc IS the spec.

## 8. Indicator definitions (the deliverable)

Grain is `state` unless noted; the "All States/UT" aggregate is a separate `country`-grain sibling (section 6). Every row carries `source_id` to the RBI State Finances row and a per-row estimate-stage marker (section 5). `direction` uses the canonical enum `{lower_is_better, higher_is_better, neutral}`. **No new `indicator_id` is minted without the [pre-flight-ingest](../../concepts/pre-flight-ingest.md) gate (ADR-0046) + a `concepts.csv` row + Hans + Max sign-off** (the verification in section 10 is a blocker for the deficit rows).

### 8a. EXTEND - UPSERT existing ids, re-source + deepen 7y -> 36y

These five already exist but cover only FY2016-FY2022 and are sourced from `src-4ead503ee617` = a **Rajya Sabha unstarred-question answer**, not the issuing authority. e-STATES replaces the source (to RBI) and deepens to FY1991-FY2026. Same `indicator_id`, UPSERT (Rosling rule - new vintage/coverage, never a re-mint). This is the single highest-value move in the file.

| indicator_id | Appendix -> budget head (verbatim) | unit | direction |
| ------------ | ---------------------------------- | ---- | --------- |
| `own-tax-revenue-inr-crore` | A1 `I.A: State's Own Tax Revenue (1 to 3)` | INR crore | neutral |
| `non-tax-revenue-inr-crore` | A1 `II.C: State's Own Non-Tax Revenue (1 to 6)` | INR crore | neutral |
| `central-tax-devolution-inr-crore` | A1 `I.B: Share in Central Taxes (i to ix)` | INR crore | neutral |
| `grants-in-aid-inr-crore` | A1 `II.D: Grants from the Centre (1 to 7)` | INR crore | neutral |
| `revenue-expenditure-inr-crore` | A2 `Total: TOTAL EXPENDITURE (I+II+III)` | INR crore | neutral |

Fowler sequences these expand-migrate-contract: write the 36-year series from e-STATES, verify against the overlapping FY16-22 window, then retire `src-4ead503ee617`.

### 8b. MINT - new per-state levels (INR crore)

Each needs a `concepts.csv` row `(noun, unit_canonical=INR crore, normalisation=absolute, entity_kinds)` and a green pre-flight report before the id is minted.

| indicator_id | concept noun | Appendix -> budget head / derivation | direction |
| ------------ | ------------ | ------------------------------------ | --------- |
| `total-revenue-receipts-inr-crore` | Total revenue receipts | A1 `Total: TOTAL REVENUE (I+II)` | neutral |
| `interest-payments-inr-crore` | Interest payments | A2 `II.C.2: Interest Payments (i to iv)` | lower_is_better |
| `capital-outlay-inr-crore` | Capital outlay | A4 `I: Total Capital Outlay (1 + 2)` | higher_is_better (quality-caveated) |
| `revenue-deficit-inr-crore` | Revenue deficit | derived: A2 TOTAL EXPENDITURE - A1 TOTAL REVENUE (= App-4 "A", verified) | lower_is_better (zero is the goal) |
| `gross-fiscal-deficit-inr-crore` | Gross fiscal deficit | derived: reconstruction in section 4 (NOT App-4 "C") | lower_is_better |

**Grain-over-entity fold:** `gross-fiscal-deficit-inr-crore` should carry per-state rows (`entity_kind=state`) AND an all-states row (`entity_kind=country`), retiring the existing `states-combined-gross-fiscal-deficit-inr-crore` (which encodes the aggregate in the id, an ADR-0044 smell). The Union government series `union-gross-fiscal-deficit-inr-crore` is a *different actor* and stays separate. This fold is a Hans + Max sign-off.

### 8c. DERIVE - ratios (the citizen-facing fiscal-health headline)

Computed from the levels above plus existing per-state GSDP / revenue receipts; not stored from a separate fetch. Carry the GSDP base-year stamp and rebase breaks (section 6). See the vocabulary and FRBM anchors in [state-fiscal-health](../../concepts/state-fiscal-health.md).

| indicator_id | normalisation | derivation | direction / anchor |
| ------------ | ------------- | ---------- | ------------------ |
| `gross-fiscal-deficit-pct-gsdp` | ratio (% GSDP) | `gross-fiscal-deficit-inr-crore` / GSDP | lower_is_better; ~3% FRBM reference line |
| `revenue-deficit-pct-gsdp` | ratio (% GSDP) | `revenue-deficit-inr-crore` / GSDP | lower_is_better; zero is the goal |
| `primary-deficit-pct-gsdp` | ratio (% GSDP) | (GFD - `interest-payments-inr-crore`) / GSDP | lower_is_better |
| `own-tax-revenue-pct-gsdp` | ratio (% GSDP) | `own-tax-revenue-inr-crore` / GSDP | higher_is_better (ceiling-caveated) |
| `own-revenue-pct-total-revenue` | share | (`own-tax-revenue` + `non-tax-revenue`) / `total-revenue-receipts` | neutral - the self-reliance trap (#7 / framing trap #3) |
| `interest-payments-pct-revenue-receipts` | ratio | `interest-payments-inr-crore` / `total-revenue-receipts-inr-crore` | lower_is_better |

### 8d. DECIDE, KEEP, DEFER

- **DECIDE - `pension-expenditure-inr-crore`:** move the source to e-STATES A2 `II.E: Pensions` (36-year arc, methodologically consistent with the rest of the spine); retire the Handbook Table 171 source. UPSERT same id.
- **KEEP unchanged - `outstanding-liabilities-pct-gsdp`** (per-state + national): debt stock, not in e-STATES, already correctly sourced.
- **DEFER (mint only with the honesty caveat) - `committed-expenditure-pct-revenue-receipts`:** ship as a PARTIAL `(interest + pensions) / revenue receipts` proxy because salaries are not separable in App-2 (section 4); the label must say "partial - excludes salaries".
- **DEFER (high-value facet) - own-tax revenue by source.** Appendix-1 carries the full own-tax breakdown - `I.A.3.vii: State Goods and Services Tax` (SGST), `I.A.3.ii: State Excise` (liquor), `I.A.2.ii: Stamps and Registration Fees`, `I.A.3.iii: Taxes on Vehicles`, `I.A.3.v: Taxes and Duties on Electricity`, `I.A.2.i: Land Revenue`, `I.A.3.vi: Entertainment Tax`, plus the Sales Tax/VAT sub-lines - and Share-in-Central-Taxes splits into CGST / Corporation Tax / Income Tax / Customs / Union Excise / IGST. This answers "where does my state's tax money come from?" - a strong promote candidate as ONE faceted `own-tax-revenue-by-source` indicator (facet picker inside one card, never N cards), after the headline `own-tax-revenue-inr-crore` aggregate ships.
- **DEFER (breadth, not now):** the ~340 functional sub-heads (education/health/water/roads spend, capital-receipt financing detail). When a concrete citizen question pulls one up, ship it as ONE `development-expenditure-by-function` indicator with a function facet inside one card (never N cards), framed as an INPUT not an outcome (framing trap #4). Education and health revenue expenditure are the first two promote candidates - note health already half-exists via SRS public-health-expenditure, a latent double-source to reconcile on promotion.
- **DEFER (separate source) - state Guarantees** (Statement 28) and longer debt-stock back-history: non-derivable; a thin Statements follow-up tracked in [docs/research](../../research/).

### 8e. Machine-ready crosswalk seed

The future reader consumes a `(appendix, budget_head) -> indicator_id` map. The level rows (8a/8b) seed it directly; the derived rows (8c) are computed post-load, not crosswalk entries:

```text
Appendix-1  "I.A: State's Own Tax Revenue (1 to 3)"        -> own-tax-revenue-inr-crore
Appendix-1  "I.B: Share in Central Taxes (i to ix)"        -> central-tax-devolution-inr-crore
Appendix-1  "II.C: State's Own Non-Tax Revenue (1 to 6)"   -> non-tax-revenue-inr-crore
Appendix-1  "II.D: Grants from the Centre (1 to 7)"        -> grants-in-aid-inr-crore
Appendix-1  "Total: TOTAL REVENUE (I+II)"                  -> total-revenue-receipts-inr-crore
Appendix-2  "Total: TOTAL EXPENDITURE (I+II+III)"          -> revenue-expenditure-inr-crore
Appendix-2  "II.C.2: Interest Payments (i to iv)"          -> interest-payments-inr-crore
Appendix-2  "II.E: Pensions"                               -> pension-expenditure-inr-crore
Appendix-4  "I: Total Capital Outlay (1 + 2)"              -> capital-outlay-inr-crore
# revenue-deficit + gross-fiscal-deficit are RECONSTRUCTED post-load (section 4), not single-head crosswalk rows.
# reconstruction inputs also needed from the load:
Appendix-4  "IV: Loans and Advances by State Governments (1+2)"   # GFD net-lending term
Appendix-3  "III: Recovery of Loans and Advances (1 to 12)"       # GFD non-debt-receipt term
```

## 9. Coordination with the Handbook plan

[TODO/20260625-rbi-handbook-data-capture-and-goals-plan.md](../../../TODO/20260625-rbi-handbook-data-capture-and-goals-plan.md) Row R8 lists fiscal items (GFD, revenue deficit, outstanding liabilities) as *Handbook* candidates. **State Finances (e-STATES) owns the per-state fiscal spine; the Handbook defers fiscal to it** - it is RBI's dedicated fiscal study, compiled from the budget documents, 36 years x 32 entities deep, vs the Handbook's thinner re-presentation. Minting the same fact from two RBI products is the exact double-ingest the overlap gate ([pre-flight-ingest](../../concepts/pre-flight-ingest.md), `check-overlap >= 70%`) exists to stop. Concrete division:

- **State Finances owns:** all per-state receipts, expenditure, capital outlay, and the deficit block. R8 should mark its fiscal candidates `defer - covered by State Finances e-STATES`.
- **Handbook keeps only what e-STATES lacks:** the Union (central) government GFD (a different entity) and the macro / banking / prices panel.
- **Pension collision -> pick e-STATES** (retire Handbook Table 171).

This doc only RECORDS the coordination; the R8 keep/defer matrix is edited by whoever owns that plan (a parallel effort - do not cross-edit it here).

## 10. Pre-mint verification (blocking for the deficit rows)

Done on the 2025-26 file (section 4): Revenue Deficit reconciles exactly; App-4 "C" is NOT GFD; no salaries head; Telangana back-projected to 1990-91; Actuals end FY2023-24. Still required before minting the GFD rows, to record in [docs/research](../../research/):

1. **GFD perimeter check** - reconstruct GFD (section 4) for all 32 entities x 36 years and reconcile against RBI Statement 1; quantify and explain any per-state divergence (public-account perimeter) before shipping `gross-fiscal-deficit-inr-crore`.
2. **Telangana pre-2014 labelling** - confirm whether back-projected values are blank or filled, and wire the bifurcation badge accordingly.
3. **Disinvestment / non-debt misc capital receipts head** - confirm the exact App-3 head(s) for the GFD non-debt-receipt term.

## Decision record

| Date | Decision | Authority |
| ---- | -------- | --------- |
| 2026-06-25 | e-STATES supersedes per-edition Appendix I-IV; does NOT supersede the ratio/debt-stock/guarantee Statements; derive ratios from e-STATES + GSDP | Max + Hans (converged) |
| 2026-06-25 | New long-format reader + `(appendix, budget_head) -> indicator_id` crosswalk; not the wide `HbsTableSpec`; full-replace UPSERT, `update_period_days=365` | Max + Hans preference; Fowler owns final engineering call |
| 2026-06-25 | Coalesce Account > RE > BE into one series, stage as per-row provenance (not a facet column) | Max + Hans (converged); owid-alignment divergence #8 |
| 2026-06-25 | EXTEND 5 ids off the Rajya Sabha-QA source to RBI e-STATES (7y -> 36y); MINT 5 levels + 6 ratios; move pension to e-STATES; keep debt-stock + guarantees separate | Max + Hans (converged) |
| 2026-06-25 | gross-fiscal-deficit is reconstructed, NOT App-4 "Overall" line (verified on file) | default-agent verification, Hans-flagged |
| 2026-06-25 | State Finances owns the fiscal spine; Handbook R8 fiscal candidates defer | Max + Hans (converged) |

The full debate (Hans governance verdict + Max coverage verdict) was run 2026-06-25; the vocabulary it produced lives in [state-fiscal-health](../../concepts/state-fiscal-health.md).

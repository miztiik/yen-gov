# yen-gov — CAG State Accounts Ingest (Scout → Source → Ingest)

**Last Updated**: 2026-05-15
**Status**: Open. Phase 0 (Source Hunt) is unowned and ready to pick up.
**Authority**: Non-authoritative scratchpad (CLAUDE.md §3). Promote agreed pieces into `docs/architecture/backend/` (and an ADR if a credible alternative is rejected, per CLAUDE.md §4) as each phase lands.
**Correction level**: Starts at **2** (Phase 0 — recon scripts only, no contract surface). Escalates to **3-4** at Phase 2 once a schema is drafted.

> **Trigger**: User pointed at the CAG (Comptroller & Auditor General) "Accounts at a Glance" PDF for Himachal Pradesh FY 2024-25 (`https://cag.gov.in/uploads/state_accounts_report/account-report-Accounts-at-a-Glance-HP-2024-25-English-03-02-2026-069d34c35588928-30644923.pdf`) and asked Hans (Governance) to scout it for indicators. Hans returned a strong "yes, ingest" recommendation. **Critical user instruction: do NOT assume the source format is PDF.** The aim is to identify the *indicators* first, then let the source-hunting agent decide whether the cleanest acquisition is CSV from data.gov.in, an RBI cross-cite, a CAG-published spreadsheet, the Accounts at a Glance PDF, or the deeper Finance Accounts PDF. Pick the cheapest-clean source per indicator; mix sources if needed.

---

## 1. Why this is worth doing (one paragraph)

CAG audited state-finance numbers are the **only** Indian source that ships (a) Budget-Estimate-vs-Actuals variance, (b) explicit off-budget borrowings, (c) outstanding government guarantees, (d) reserve-fund balances, and (e) major-head expenditure breakdown — none of which RBI Handbook or MoSPI publish. They answer the citizen question *"Did my state government collect what it said it would, spend it where it said it would, and how much of tomorrow's revenue has it already mortgaged?"* Adding this series gives yen-gov a fiscal-health tier that complements (does not duplicate) the existing RBI Handbook ingest. Full Hans report is in the chat transcript dated 2026-05-15; key bits are quoted in §3 below.

---

## 2. Indicator slice (the contract this whole TODO exists to deliver)

These are the indicators we want, ranked by extraction priority. **Source format is deliberately unspecified** — the source-hunt phase decides.

| # | Indicator (proposed `id` shape) | Unit | Coverage we want | Why it matters | Distinctive vs RBI? |
|---|----|----|----|----|----|
| 1 | `state_finance/revenue_receipts/own_tax` `…/own_non_tax` `…/central_share` `…/grants_in_aid` (4-way split) | ₹ cr & % of total | 28 states + Delhi + Puducherry × FY20 → FY25 (6 yr) | Fiscal autonomy proxy. HP ~25% own-tax vs Karnataka ~65%. | RBI has provisional; CAG is **audited final** — keep CAG as the late-binding canonical. |
| 2 | `state_finance/capital_outlay/total` + sectoral breakdown | ₹ cr & % of GSDP | same | Best fiscal-quality signal. | RBI has totals only; CAG has **sectoral**. |
| 3 | `state_finance/debt/outstanding_public_debt` + `…/off_budget_borrowings` + `…/psu_debt_serviced_from_budget` | ₹ cr & % of GSDP | same | True debt vs headline debt — politically toxic gap (Telangana, Punjab, Kerala, AP, HP all material). | **CAG-distinctive** post-Aug 2022 MoF order. |
| 4 | `state_finance/guarantees/outstanding_stock` + `…/issued_during_year` + `…/invoked_during_year` | ₹ cr & % of revenue receipts | same | Discom / PSU co-signs that become state debt on default. | **CAG-exclusive.** |
| 5 | `state_finance/interest_payments_to_revenue_receipts` | ratio (%) | same | FRBM red-line. >20% = structural distress. | RBI has it; CAG version is audited. |
| 6 | `state_finance/committed_expenditure_ratio` (salaries + pensions + interest as % of revenue exp) | ratio (%) | same | Inverse of fiscal flexibility. | RBI partial; CAG complete. |
| 7 | `state_finance/budget_vs_actuals/revenue_receipts_variance` + `…/capital_outlay_variance` | % deviation | same | "Did the ₹500 cr promised for schools actually get spent?" | **CAG-exclusive headline value.** |
| 8 | `state_finance/reserve_funds/csf_balance` + `…/grf_balance` (Consolidated Sinking Fund, Guarantee Redemption Fund) | ₹ cr; categorical "funded / partial / unfunded" | same | Quiet fiscal-seriousness signal. | **CAG-exclusive.** |

**Stretch (defer to Phase 2 — do not block MVP on these):**

| # | Indicator | Source | Notes |
|---|----|----|----|
| 9 | `state_finance/pension_outgo` YoY | CAG | OPS-vs-NPS empirical anchor. HP returned to OPS in 2023 — FY24/FY25 will show first cash impact. |
| 10 | `state_finance/suspense_remittance_balance` | CAG | Treasury-control / governance-quality signal. Niche but Pramit-grade. |
| 11 | `state_finance/wma_overdraft_days` | RBI WMA + CAG reconciliation | Cash-management red flag. |
| 12 | Adverse-audit-comment text | CAG | Citizen-readable governance signal as a `notes` field, not a number. |

**Identifier rule reminder** (CLAUDE.md §3 + lesson 2026-05-11): id pattern is `^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*$` — `/` separator, NOT `.`. The above `state_finance/...` shapes are proposals; the schema author decides final naming.

**Mandatory metadata for every indicator** (per CLAUDE.md §6 — no hardcoding, and existing `datasets/indicators/` patterns):

- `unit`, `direction` (higher_is_better / lower_is_better / neutral) — most fiscal indicators are *neutral or context-dependent*; debt/GSDP is not "lower is better" without peer context (HP 2023 floods inflated borrowings; that is not mismanagement).
- `methodology_breaks`: array of `{date, description}` — see §4 below.
- `peer_group_default`: `category_special` for HP / hill states; `all_india` rejected by Hans for fiscal indicators.
- `vintage`: one of `provisional`, `revised`, `audited` — same FY24 number appears in three vintages (state Budget Speech revised, RBI State Finances provisional, CAG Accounts at a Glance audited). yen-gov should expose all three with a vintage badge **if and only if** we ingest more than one vintage; MVP picks audited only.

---

## 3. Methodology breaks (must be encoded as schema-side annotations, not narrative-only)

Every fiscal time series must surface these vertical-line annotations. This is non-negotiable per Hans / Pramit lens — without these, single-year jumps will be misread as governance signals when they are policy-regime artefacts.

| Date | Break | Affected indicators |
|---|---|---|
| Jul 2017 | GST regime change | own-tax composition (VAT/sales tax → SGST + GST comp cess + residual VAT on petroleum/liquor) |
| Jun 2022 | GST compensation cess sunset | revenue-receipts trajectory; many "revenue deficit" jumps in FY23 are pure compensation-loss artefacts |
| FY16-FY20 → FY21-FY26 | 14th → 15th Finance Commission award periods | devolution share, grants-in-aid composition |
| FY27 onward | 16th Finance Commission award (report due Oct 2025) | same — schema must accommodate the upcoming break |
| Aug 2022 | MoF off-budget reclassification order | retroactive inflation of reported debt-to-GSDP for several states across FY22-FY26 |
| ongoing | GSDP base-year revision (2011-12 → forthcoming new series) | every `% of GSDP` ratio depends on which MoSPI vintage CAG used |
| ongoing | Cash vs accrual basis | pension liabilities, depreciation, arrears invisible until paid |
| state-specific | Revenue Deficit definitional drift (centre-vs-state on grants-for-capital-assets netting) | **always reconstruct from components, never use headline across states** |

**HP-specific footnotes** that must be attached when HP's series renders: 2023 monsoon devastation drove FY24 borrowings; return to Old Pension Scheme (2023) hits FY24/FY25 pension outgo.

---

## 4. Phased plan

### Phase 0 — Source Hunt (this is the next agent's job; deliverable is a recon report, NOT data)

**Goal**: For each of the 8 MVP indicators in §2, identify the cheapest-clean source. Do NOT assume PDF. Probe in this order:

1. **`data.gov.in` API**: existing `tools/datagovin_recon.py`, `tools/datagovin_api_probe.py`, `tools/datagovin_paging_probe.py` already exist for this. Search for "state finance", "CAG", "accounts at a glance", "Finance Accounts", "guarantees". A CSV-from-API beats a PDF every time.
2. **CAG website "FA&AA data" sub-series**: the CAG state-accounts index page (`https://cag.gov.in/en/state-accounts-report`) lists *five* sub-series — Accounts at a Glance, Appropriation Accounts, Finance Accounts, Monthly Key Indicators, **and "FA&AA data"**. Hans noted "some states publish CSV/XLSX" under FA&AA data. **Probe this first** — if any state publishes the indicators we want as XLSX, that is dramatically cheaper than parsing 28 PDFs.
3. **RBI cross-source**: some indicators (e.g. interest-payments-to-receipts, committed-expenditure ratio) are in RBI State Finances: A Study of Budgets — already partially explored (`tools/rbi_recon.py`, `tools/rbi_handbook_states_inspect.py`, `tools/rbi_hbs_*`). For indicators where RBI has the *audited* number (not just provisional), prefer the RBI source we already have ingest paths for. Hans flagged that BE-vs-Actuals variance, off-budget borrowings, guarantees, and reserve funds are **CAG-exclusive** — those four cannot be substituted.
4. **Accounts at a Glance PDF** (the original starting point): the citizen-brochure tier, 30-50pp per state. Use only if 1-3 fail.
5. **Finance Accounts PDF**: the deep ledger, 400-800pp per state. Last resort, reserved for Phase 2.

**Tooling we already have that the Phase-0 agent should reuse, not rewrite:**

- `tools/datagovin_recon.py`, `…_probe.py`, `…_api_probe.py`, `…_paging_probe.py` — data.gov.in resource discovery + paging probes.
- `tools/rbi_recon.py`, `tools/rbi_handbook_states_inspect.py`, `tools/rbi_hbs_extract_urls.py`, `tools/rbi_hbs_dump_rows.py`, `tools/rbi_hbs_dump_col1.py` — RBI publication crawl + xlsx introspection. Pattern reusable for CAG xlsx if found.
- `tools/rbi_download.py`, `tools/rbi_hbs_download.py` — browser-headers download (RBI/CAG CDNs reject naive UAs; per lesson 2026-05-11, override UA per-source at the call site, do NOT touch global `config/processing.json`).
- `backend/yen_gov/...` for `Fetcher`, schema registry, sources composer — see existing `backend/yen_gov/admin/`, `backend/yen_gov/sources/` (look at `iced_macro`, `iced_socio`, `iced_power` adapters as templates — they all follow `recon → inspect → ingest` and emit to `datasets/indicators/`).
- For PDF parsing if it comes to that: `pymupdf` and `pdfplumber` are the recommended extractors per Hans; `tabula-py` for tabular pages; OCR (`pytesseract`) only as last resort for genuinely scanned older volumes. **Test on Manipur or other NE state first** — if NE PDFs extract cleanly, all 28 will (per Hans).
- Recon recipe (lesson 2026-05-11): `tools/cag_recon.py` (HTTP scrape index page) + `tools/cag_inspect.py` (per-format introspection — pymupdf for PDF, openpyxl for xlsx, csv module for csv) + `tools/cag_download.py` (browser-headers fallback). Mirror the RBI tooling shape for muscle-memory consistency.

**Phase 0 deliverable** (one markdown file, append to this TODO under §6):

For each of the 8 MVP indicators: `{indicator_id, best_source_kind, source_url_pattern, format, coverage_actual (states × years), extraction_difficulty (1-5), blocking_caveats, fallback_source}`. Plus an answer to: "Can the entire MVP slice be served from data.gov.in / CAG xlsx alone? If not, which indicators force PDF ingestion?"

**Constraints**:

- Path rules (CLAUDE.md §2): all persisted/logged paths POSIX-relative.
- Provenance (CLAUDE.md §12): every URL the recon actually fetched goes into the recon report's `sources`. Hand-authored content (zero URLs fetched) gets `sources: []` and the rationale lives in the commit message.
- No `[DEBUG]` prints left behind (CLAUDE.md §7).
- Under `.runtime/raw/cag/` for intermediate downloads (ADR-0003), `.runtime/cag_recon/` for logs.
- No `python -c "<multi-line>"` (lesson 2026-05-11). Always write to `tools/<name>.py` and run.
- No `git stash`, no `git add .`, no force push (CLAUDE.md §8).

### Phase 1 — Schema design (Correction level 3)

After Phase 0 reports back. Inputs: indicator list (§2), methodology breaks (§3), source format mix (Phase 0 output). Author `datasets/schemas/state_finance_indicator.schema.json` (or extend the existing indicator schema if it fits — check `datasets/schemas/` first; do NOT shadow-copy). Per CLAUDE.md §11: `$id`, `x-version` major.minor, `x-changelog` non-empty, source schema-version constants from `yen_gov.core.schema_registry`. Add cross-state methodology-break annotations as a first-class schema field if the existing indicator schema lacks it.

Sign-off required from user before Phase 2.

### Phase 2 — Adapter + ingest (Correction level 3-4)

One adapter per source format chosen in Phase 1. Templates: `backend/yen_gov/sources/iced_*`. Fixtures per Holy Law #7 (real fixtures, no mocks). Tests at all four tiers per CLAUDE.md §15: unit (parsers), contract (schema conformance both producer + consumer), integration (adapter against fixture), e2e (Playwright assertion on the citizen-visible state finance page).

### Phase 3 — Frontend surfaces

Per `TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md` and existing `/t/economy` topic-front-door pattern. Hans's framing copy (§3 of his report; available in chat transcript) seeds the section headers. Per Hans, **never expose a single fiscal indicator without its companions on the same page** — debt with off-budget + guarantees, revenue deficit only after the 4-way split, etc.

UI verification per CLAUDE.md §13: agent must `read_page` and confirm new sections render + no new console errors before marking done.

### Phase 4 — Cross-validation gate (Pramit's lens)

Pick HP FY23-24 (audited in both sources by then) and confirm Revenue Receipts, Capital Outlay, Outstanding Debt match within 1% between RBI State Finances and CAG. If they don't, document the delta in `docs/concepts/` before exposing both vintages. **This is a hard gate before Phase 5.**

### Phase 5 — Topic page polish + Rosling guardrails

Force peer-group selector default to **category** (special-category/hill states peer with each other), not "all India". CM-term shading must be co-rendered with FC-award-period shading + GST-comp-period shading + national-government shading on the same chart, or the chart misleads by construction. Add the HP 2023 monsoon + OPS footnote-pin as the canary annotation.

---

## 5. Open questions for the user (do not start Phase 1 until answered)

1. **MVP scope confirmation**: 8 indicators × 30 jurisdictions × 6 years (FY20→FY25)? Or smaller pilot (e.g. 3 indicators × 5 states × 3 years) to derisk the format-mix before scaling?
2. **Vintage policy**: ingest audited-only from CAG, or also expose the provisional (RBI State Finances) and revised (state Budget Speech) tiers with a vintage badge? More accurate but ~3× the ingest surface.
3. **Peer-group taxonomy**: do we already have a `category_special` peer set in `datasets/reference/`? If not, this needs its own mini-design before Phase 5 (Hans is firm that "all states" is a misleading default for fiscal indicators).
4. **Stretch indicators (#9-#12)**: in or out of MVP? Hans recommends out; user call.
5. **Suspense / Adverse-audit-comments**: ingest as numeric + text in MVP, or push to Phase 2? These are Hans's two "Pramit-grade" picks but not load-bearing for citizen value.

---

## 6. Phase 0 deliverables (TO BE FILLED BY NEXT AGENT)

> Append the source-hunt report here. Suggested structure:
>
> ### 6.1 data.gov.in probe results
> - search terms tried, resource ids hit, coverage assessment per indicator
>
> ### 6.2 CAG "FA&AA data" probe results
> - which states publish xlsx/csv, which years covered, sample resource URLs
>
> ### 6.3 RBI cross-source coverage
> - which of the 8 MVP indicators are already audited in RBI State Finances; per-indicator decision (CAG vs RBI canonical)
>
> ### 6.4 PDF fallback assessment (only if §6.1-6.3 leave gaps)
> - test extraction on HP + Manipur + Maharashtra; report `pymupdf` quality; quantify per-state effort
>
> ### 6.5 Recommended source mix per indicator
> - the table this TODO exists to produce
>
> ### 6.6 Recon log
> - `.runtime/cag_recon/` artifacts produced; `tools/cag_recon.py` etc. committed
>
> ### 6.7 Sources (CLAUDE.md §12)
> - every URL the recon scripts actually fetched, with `fetched_at`

---

## 7. Cross-references

- Hans's full scouting report: chat transcript dated 2026-05-15 (CAG HP Accounts-at-a-Glance review). Quote-worthy bits already inlined above; the full report has citizen-readable framing copy (§"Recommended framing") that seeds Phase 3.
- CLAUDE.md §0 (non-goals — accessibility is descoped), §6 (correction levels), §11 (schema versioning), §12 (provenance), §13 (UI verification), §15 (test tiers).
- ADR-0003 (`docs/architecture/decisions/0003-*`): `.runtime/raw/<source>/` is debug, not contract.
- Sibling expansions: `TODO/SOCIO-ECONOMIC-EXPANSION.md` (broader atlas plan — CAG fits inside the "taxes / GST flows / welfare spending" slice).
- Adapter templates: `backend/yen_gov/sources/iced_macro/`, `…/iced_socio/`, `…/iced_power/`, `…/merged_aq/`.
- Tooling lessons: user-memory `lessons.md` 2026-05-11 (RBI ingest) — re-read before writing any new tool.

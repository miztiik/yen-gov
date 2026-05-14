# yen-gov — Election Enforcement (ECI Seizures) Ingest Plan

**Last Updated**: 2026-05-13
**Status**: Proposal. **No code or schema changes until §7 is signed off by the user.**
**Authority**: Non-authoritative scratchpad (CLAUDE.md §3). Promote pieces into `docs/architecture/` and ADRs on execution.
**Correction level**: 3 (new dataset family + new schema + new UI section, but no changes to existing contracts). Per CLAUDE.md §6: plan → phased execution after approval.

> **Trigger**: User pointed at ECI press note `ECI/PN/084/2026` (07.05.2026) — the per-state seizure table from the May 2026 LA elections (TN/WB/Assam/Kerala/Puducherry, total ₹1444.96 cr across Cash / Liquor / Drugs / Precious Metal / Freebies / Other). Asked whether this is worth ingesting, where similar reports live, and — given ESMS only activated 26 Feb 2026 — whether this can ship as an **optional metric** without historical backfill.

---

## 1. Framing (governance-strategist consult)

**This is enforcement-activity data, not illicit-economy data.** Every UI and copy decision flows from that distinction.

What it actually answers:

- *Citizen*: "Is the MCC period being actively policed in my state?"
- *Researcher*: "Does ESMS-era enforcement detect more than pre-ESMS enforcement, controlling for state and election size?"
- *CEO-state officer*: "Where do my FST/SST deployments convert to seizures?"

What it does **not** answer (must not be implied in UI):

- Which party "bought more votes"
- The actual stock of illicit money
- Whether enforcement changed any outcome

Seizure = `illicit_flow × enforcement_intensity × competence × political_will`. A high number can mean any of the four moved; a low number, any of the four. Frame honestly or don't ship.

## 2. Coverage reality — ship as **optional metric**, ESMS-forward only

ESMS (Election Seizure Management System) activated **26 Feb 2026**. The structured 6-category breakdown does not exist in machine-readable form before that. **Hard no on backfill** from parliamentary questions / ADR / news:

- **Category drift**: pre-ESMS press notes don't have the 6-bucket structure. Reconstructing "Freebies" or "Precious Metal" from a PQ reply is analyst judgement, not data.
- **Selection bias**: PQ replies surface where an MP asked; ADR covers what ADR prioritised. Mixing PQ-derived and ESMS-derived numbers is comparing apples to a press release.
- **Provenance cost**: every backfilled cell needs a defensible `sources` entry (CLAUDE.md §12). Mixed-provenance indicators rot fastest.

Floor to ship anything useful: **2024 LS national totals + every state poll from Feb-2026 onward.** Below that, it's a single-point factoid, not an indicator.

For older elections in the registry (AcGenMay2016 … AcGenFeb2025): **the panel simply doesn't appear** on those pages. No greyed bar, no "data coming soon", no empty placeholder. This is the same posture we use for pre-GST tax data, pre-NFHS-5 indicators, etc.

A `docs/research/eci-seizures-pre-esms.md` note will catalogue what fragmentary data exists (ADR PDFs, specific PQs) **without ingesting it** — so a future contributor doesn't re-litigate the backfill question.

## 3. Source map (acquisition)

| Source                                  | URL                                                                  | Format                            | Use                                                                  |
| --------------------------------------- | -------------------------------------------------------------------- | --------------------------------- | -------------------------------------------------------------------- |
| ECI press releases (canonical)          | `https://www.eci.gov.in/issue-details-page/press-releases`           | HTML index → per-PN PDF           | **Primary ingest.** Tables text-extractable since ~2022.             |
| ECI Election Expenditure landing        | `https://www.eci.gov.in/election-expenditure`                        | HTML + Compendium PDF             | **Definitional source** for the 6-category taxonomy. Cite in docs.   |
| ESMS                                    | `esms.eci.gov.in`                                                    | Internal-only                     | No public dashboard. Skip.                                            |
| State CEO daily MCC bulletins           | `elections.tn.gov.in`, `ceowestbengal.nic.in`, `ceoassam.nic.in`, `ceo.kerala.gov.in`, `ceopondicherry.py.gov.in` | Daily PDF, district/AC granularity | **Phase G.2 (deferred).** Must fetch during the live MCC window; sites go quiet ~6mo after results. |
| Parliamentary questions                 | `https://sansad.in/ls/questions`, `…/rs`                             | Structured HTML                    | Best surface for **revised** historical figures (MHA/Law Ministry replies). Use as triangulation. |
| ED / DRI / NCB / CBIC-PIB               | `enforcementdirectorate.gov.in`, `dri.nic.in`, `pib.gov.in`          | PDF + HTML                         | Triangulation only; double-counting risk vs ECI aggregate.           |
| ADR / PRS / Carnegie India              | `adrindia.org`, `prsindia.org`                                       | Secondary                          | Cross-checks, not primary.                                            |

ECI **Statistical Reports** (already in our plan) do **not** carry seizure data — that's an ESMS-era artifact. Two separate series, never merged.

## 4. Data model (two-layer)

Follows the same pattern we already use for RBI (raw XLSX → derived per-state series).

### 4.1 Raw layer — `datasets/events/in/eci/<event-id>/enforcement.json`

One file per ECI press note, source-faithful, audit-trail-grade. Co-located with the existing `election.json` under `datasets/events/in/eci/AcGenMay2026/`.

**Why co-located, not under a new `events/eci/enforcement/<pn-id>/`**: the press note is *about* an election event we already model. Putting it next to `election.json` lets one loader fetch both. The press-note id (`ECI-PN-084-2026`) goes inside the JSON as a field, not in the path.

Sketch (subject to schema review):

```json
{
  "$schema": "https://yen-gov.github.io/schemas/election-enforcement.schema.json",
  "$schema_version": "1.0",
  "sources": [
    { "url": "https://www.eci.gov.in/.../ECI-PN-084-2026.pdf",
      "fetched_at": "2026-05-13T09:00:00Z" }
  ],
  "eci_event_id": "AcGenMay2026",
  "press_note_id": "ECI/PN/084/2026",
  "press_note_date": "2026-05-07",
  "esms_activation_date": "2026-02-26",
  "as_of": "2026-05-06",
  "revision": "original",
  "currency": "INR_CRORE",
  "categories": ["cash", "liquor_value", "drugs_value", "precious_metal_value", "freebies_other"],
  "per_state": [
    {
      "state_code": "S22",
      "cash": 105.22,
      "liquor_qty_litres": 137248.53,
      "liquor_value": 4.94,
      "drugs_value": 78.61,
      "precious_metal_value": 165.86,
      "freebies_other": 307.65,
      "total": 662.28
    }
  ],
  "total_all_states": 1444.96,
  "comparison": {
    "baseline_year": 2021,
    "baseline_total": 1029.93,
    "delta_pct": 40.14,
    "caveats": ["pre_esms_baseline", "covid_restricted_2021_campaign", "nominal_currency_not_inflation_adjusted"]
  }
}
```

Notes:

- `revision: "original" | "revised"` — the same `eci_event_id` may get re-ingested when ECI publishes a revised number; `$schema_version` minor-bumps and the file overwrites with a new `sources[]` entry appended. Old value preserved via git history, not via parallel files.
- `comparison.caveats` is an enum the UI must surface. Don't render a delta without rendering its caveats.
- `liquor_qty_litres` kept separate from `liquor_value` — they're different units and the value-cross-state comparison is partly an excise-regime comparison.

### 4.2 Derived layer — `datasets/indicators/in/elections/seizures/<state>.json`

Per-state time-series across ESMS-era election cycles. Only built when ≥1 ESMS-era cycle exists for a state. Standard indicator shape we already use for RBI/MoSPI series.

**Trend line opens at ≥2 ESMS-era cycles for the same state.** Until then, the indicator carries a single point and the chart renders as a single bar, not a line.

National aggregate `datasets/indicators/in/elections/seizures/IN.json` is the only series with enough density to look like a trend in the near term (2024 LS + 2026 5-state AGs + 2027 state polls forward).

## 5. UI treatment (the rules that make sparsity honest)

These are non-negotiable for the panel to ship:

- **Default denominator: per 1 lakh electors.** Absolute crore is a toggle. Without normalisation, small UTs vanish and big states dominate for reasons unrelated to enforcement.
- **Bars only, never a line.** A line implies continuity across gap years.
- **Regime band on x-axis**: shaded "Pre-ESMS (before Feb 2026)" vs "ESMS era". Same pattern we'd use for pre-/post-GST.
- **One-line caption on the chart** (not a footnote): *"ESMS standardised seizure reporting in Feb 2026. Earlier elections used ad-hoc categories and are not shown."*
- **No grey-out, no "data coming soon".** Pre-ESMS elections simply don't show the panel.
- **"Freebies/Other" gets a definitional tooltip** citing the ECI Compendium URL and the year the definition last changed. This category is the politically loaded one; don't ship it bare.
- **2026-vs-2021 delta**, if shown at all, carries its caveat enum inline — pre-ESMS baseline, COVID-restricted 2021 campaign, nominal currency.

### Page placement

- **State election hub** (`/in/elections/<event-id>/<state>/`): "MCC enforcement" card, 6 categories + per-elector total, sourced from `enforcement.json`. Appears only on ESMS-era events.
- **State governance page** (`/in/states/<state>/elections/`): under a **"Since ESMS"** subsection, not in the main election summary card. Bars across that state's ESMS-era cycles when ≥2 exist; single bar when 1.
- **All-India election dashboard**: cross-state ranking, **normalised by electors** by default, absolute on toggle.

## 6. Schema + validation work (concrete deliverables)

1. New schema: `datasets/schemas/election-enforcement.schema.json`
   - `$id`, `x-version: "1.0"`, `x-changelog` initial entry, JSON Schema 2020-12.
   - Required: `eci_event_id`, `press_note_id`, `press_note_date`, `revision`, `currency`, `per_state[]`, `sources[]`.
   - `per_state[].state_code` MUST match `datasets/reference/in/states.json`.
   - `comparison.caveats` enum: `pre_esms_baseline | covid_restricted_2021_campaign | nominal_currency_not_inflation_adjusted | category_definition_changed`.
2. Producer-side validator: extend `backend/yen_gov/validate.py` to enforce the new schema. Reject any file whose `$schema_version` ≠ schema `x-version`.
3. Contract test: `backend/tests/test_validate.py` adds an enforcement.json fixture; `frontend/src/contracts/datasets-conform.test.ts` validates the same file from the consumer side.
4. Indicator schema (`datasets/schemas/indicator.schema.json`) — **no change**. The derived per-state series is just another indicator. Categories ride in the existing dimensions slot.

## 7. Phasing (proposal — needs sign-off)

| Phase  | Scope                                                                                                            | Gate                                            |
| ------ | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **G.0** | Sign-off on §4 schema sketch + §5 UI rules + §2 "no backfill" stance. Author `docs/concepts/election-seizures.md` (taxonomy + ESMS definition) and `docs/research/eci-seizures-pre-esms.md` (catalogue, no ingest). | **User approval.** No code yet.                  |
| **G.1** | Schema + validator + one hand-authored fixture for `AcGenMay2026/enforcement.json` from PN/084/2026. Source PDF cached under `.runtime/raw/eci/press-notes/` per ADR-0003. Contract tests both sides. | `pytest -q` + `npm test` green; agent-verified via browser tools on TN AC May 2026 route. |
| **G.2** | Adapter: scrape ECI press releases index, download the PN PDF, run `pdfplumber` to extract the seizure table, emit `enforcement.json`. Backfill 2024 LS (national-only press note) as a separate event under `events/in/eci/`. | Adapter produces byte-identical output to G.1 fixture from the PDF. |
| **G.3** | Frontend: "MCC enforcement" card on state election hub. Per-elector default; absolute toggle. Provenance link to PN PDF. Caveat tooltips. | Smoke-test via browser tools on at least one state route (TN), confirm no console errors, screenshot the card. |
| **G.4** | Derived indicator emission (`datasets/indicators/in/elections/seizures/{IN,S22,S25,…}.json`). National aggregate gets a trend bar chart on the all-India dashboard; per-state pages render single-bar "Since ESMS" until 2027+ cycles land. | Indicator validates; bar chart renders with regime band. |
| **G.5** *(deferred)* | State CEO daily MCC bulletins (`tools/ceo_state_bulletins/`) for sub-state granularity. Live-MCC-window fetch cadence. Separate schema. Not on the critical path. | Triggered by a future election's MCC window, not by this plan. |

## 8. Definition of Done (per CLAUDE.md §9)

For each phase:

- [ ] Schema bumped or added, with `x-changelog` entry in the same commit.
- [ ] Contract test (Tier B) on both sides — producer (`pytest`) and consumer (`vitest` + ajv).
- [ ] Integration test (Tier C) on the adapter once G.2 lands (real PDF fixture, no mocks).
- [ ] E2E test (Tier D) on the state hub route once G.3 lands — Playwright spec asserts the card renders, has the right caveat, has a `SourceList` entry pointing at the PN URL.
- [ ] Browser-tool smoke per CLAUDE.md §13 on every G.3+ change.
- [ ] `docs/concepts/election-seizures.md` updated alongside any schema or framing change.
- [ ] `sources[]` populated on every emitted file (CLAUDE.md §12).
- [ ] No `[DEBUG]`, no hardcoded state lists, no mocks beyond `fetch` at unit-test boundary.

## 9. Open questions (parking)

- Press-note revision flow: do we keep the original alongside the revised, or overwrite + rely on git history? Provisional: **overwrite + git history**, since the indicator layer is the citizen-facing surface and the raw layer's job is "what does ECI say *today*". Confirm before G.2.
- 2024 LS event id: we don't currently have a Lok Sabha event under `datasets/events/in/eci/`. Need to decide id convention (`LsGenApr2024`?) before G.2 ingests the 2024 LS seizure totals.
- Per-AC granularity from CEO bulletins: worth the effort? Decision deferred to G.5 trigger.
- Whether to surface ED/DRI/NCB-side press-release totals as a triangulation panel (audit-trail-only, no UI), or skip entirely. Lean: **skip** — double-counting risk vs ECI aggregate is real, signal-to-noise is low.

## 10. Non-goals

- Backfill of pre-ESMS election seizures from PQs / ADR / news (§2).
- Inference of "illicit economy stock" from seizure totals.
- Party-attributed seizures ("BJP cash vs DMK cash"). ECI does not publish this and the inference is unsafe.
- A live MCC-window enforcement ticker. We are a static-first site (CLAUDE.md Holy Law #1); live data is out of scope.
- Accessibility framing of any of the above (CLAUDE.md §0 non-goal).

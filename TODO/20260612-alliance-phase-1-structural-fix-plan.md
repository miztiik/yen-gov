# Alliance backfill Phase 1 — structural fix + light up curated events — 2026-06-12

**Status:** READY-TO-IMPLEMENT
**Correction level:** Level-3 (schema migration + frontend loader + tests + docs)
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §0a (data shape = Hans + Max; contracts = Gregor; engineering = Fowler) · §3 storage doctrine · §9 DoD · §10 anti-patterns (no silent demotion) · §11 schema versioning · §12 provenance.
**Predecessor:** [TODO/20260612-alliance-backfill-research-plan.md](./20260612-alliance-backfill-research-plan.md) — Hans (R1-R3) + Max (R4-R5) joint research completed 2026-06-12. This plan-doc implements their joint verdict.

## Problem (research-confirmed 2026-06-12)

Three structural defects keep the existing 60 alliance rows on disk INVISIBLE to every citizen surface. Phase 1 fixes them; no new curation. **AFTER this PR ships, the 4 already-curated events light up correctly with zero new data work.**

| # | Defect | Evidence | Severity |
| - | --- | --- | :---: |
| **D1** | **Loader / route key mismatch.** `loadAlliances(event)` in `frontend/src/lib/psephlab/alliances.ts` filters with `r.period_label === event`. Citizen routes pass canonical `event_id` (`general-2024`, `assembly-2024`, etc.). On-disk CSV carries cohort aliases (`LsGenJun2024`, `AcGenNov2024`). Strict equality → 0 matches → "Alliance data pending" shown on every event including the 4 with curated rows. | Max R4.3; verified by reading the loader + CSV + route call-sites. The e2e spec at `frontend/e2e/state-event-view.spec.ts:84-97` accepts the placeholder path with a comment saying Chhattisgarh general-2024 has "no rows today" — author didn't realise rows exist under the legacy period_label. | HIGH (data on disk is invisible) |
| **D2** | **State-scoping defect.** `period_label = AcGenApr2021` is the shared cohort id for 5 simultaneous state elections (Assam, Kerala, Tamil Nadu, West Bengal, Puducherry). The 8 rows curated under it describe ONLY the West Bengal Sanyukta Morcha. When Kerala asks the lookup for `parties.IN.CPIM`, the answer is `"Sanyukta Morcha"` — wrong; Kerala CPI(M) was LDF that election. | Hans R1.7 Trap 1; verified by reading the existing CSV rows + the `election_events.json` cohort declaration. | HIGH (lookup returns wrong answers cross-state) |
| **D3** | **Stale provenance FK.** All 11 TN-2026 rows declare `source_id = src-c3e2fd43efa5`. That src_id in `source.csv:378` resolves to *"Election Commission of India, General Election to Lok Sabha 1999 - Constituency-wise candidate results (TCPD compilation of ECI returns), vintage 1999"*. Wrong publisher, wrong electoral body, wrong vintage. | Hans R1.7 Trap 2; verified by grep on source.csv. | HIGH (Holy Law #9 violation) |

## Verdicts (locked, no re-debate)

### V1 — Schema v2.0 (major bump): rename `period_label` → `event_id`, add `state`, drop `short_name`

Rationale (Hans R3.3 Option A + R3.5):
- `event_id` is the canonical taxonomy key already used by the catalogue + every route. Renaming the column eliminates the alias-resolution gap (D1) at the data tier instead of patching it at the loader tier.
- `state` column is the LGD state code FK (`IN-S22`, `IN-S25`, etc.; `"IN"` for national events). Resolves D2 by giving every row an unambiguous state context.
- `short_name` was a denormalised aid duplicating `parties.csv.short_name` — Holy Law #6 smell. Drop it; readers join through `party_id` FK.

**New column shape (v2.0):**

| Column | Type | Nullable | PK | FK | Note |
| --- | --- | --- | --- | --- | --- |
| `party_id` | string | no | yes | `parties.csv.party_id` | unchanged |
| `event_id` | string | no | yes | logical FK to `taxonomy/election_events.json` events[*].event_id (not CSV-validated; election_events is JSON) | RENAMED from `period_label` |
| `state` | string | no | no | `geo.csv.entity_id` | NEW. LGD state code for state-scoped events; literal `"IN"` for national |
| `alliance` | string | yes | no | — | unchanged in column name; values disciplined per V2 below |
| `source_id` | string | no | no | `source.csv.source_id` | unchanged |

Composite PK is `(party_id, event_id, state)`.

### V2 — Alliance naming convention (Hans R3.4): name-as-published + year-suffix uniformly

- **State-event rows:** raw front name verbatim from the Wikipedia article (`"Mahayuti"`, `"MVA"`, `"LDF"`, `"UDF"`, `"AIADMK+"`, `"SPA"`, `"Sanyukta Morcha"`).
- **National-event rows:** `"<front-short>-YYYY"` (`"NDA-2024"`, `"INDIA-2024"`).
- Empty cell = unallied (current contract; lookup returns `null`).

Max recommended (R5.2) extending year-suffix uniformly (`Mahayuti-2024`, `MVA-2024`, `Sanyukta Morcha-2021`) so the citizen can disambiguate across cycles. Hans preferred state-event names verbatim. **Verdict for this PR: keep state-event names verbatim** (current curation discipline). The year-suffix question is a Phase 1b decision when more rows land; revisit then. Do not retro-suffix the 4 existing curations.

### V3 — FK repair on TN-2026 rows (D3) — **REVISED 2026-06-12 after subagent STOP-AND-SURFACE**

**Original V3 premise was empirically WRONG.** The first dispatch subagent verified:

- TN-AE-2026 has happened. `datasets/data/datapoints/electoral/tamil-nadu_election_results.csv` carries **6694 rows** of real polled outcomes keyed `period_label=AcGenMay2026`, including concrete winners (TVK — a party founded in 2024 — appears in the winners list, dispositive proof this is post-2024 data) and `src_id=src-3da941c21223`. Sister cohort CSVs exist for Assam (3244 rows), Kerala (3874), Puducherry (880), West Bengal (8304) — the expected simultaneous May-2026 5-state cohort.
- The 10 alliance rows describe the **post-2023 fracture landscape**: BJP+PMK ("NDA") separated from AIADMK+DMDK ("AIADMK+"). In TN-AE-2021, BJP+PMK were part of AIADMK+; they only fractured into a separate NDA bloc after September 2023. So the rows are post-fracture data, not 2021 data.

**Corrected verdict (Resolution A, authorized 2026-06-12):**

1. **Relocate** the 10 TN-AcGenMay2026 rows: `period_label=AcGenMay2026` → `event_id=assembly-2026` + `state=IN-S22`. (Plan-doc's earlier "TN-2026 hasn't happened" framing is retracted.)
2. **Repair source_id** via `derive_source_id(producer="Wikipedia", title="2026 Tamil Nadu Legislative Assembly election", vintage="2026-05", url="https://en.wikipedia.org/wiki/2026_Tamil_Nadu_Legislative_Assembly_election")`. Author the new row in `source.csv`; point all 10 alliance rows to the new src_id. The old `src-c3e2fd43efa5` row in `source.csv` STAYS — it's a legitimate citation for the 1999-LS-results data it actually describes.
3. **Acknowledge partial curation as Phase 1b**: only 10 parties of the actual TN-AE-2026 winner set are alliance-tagged. TVK, AMMK, IUML (winners per the result data) and others are not yet in the curation. Phase 1b adds them. This PR does not synthesize new alliance assignments — it migrates what's on disk.

Subagent count correction: plan-doc said "11 TN-2026 rows"; CSV actually carries 10. Cosmetic.


### V4 — `loadAlliances` rewrite: filter on `event_id`, drop alias resolution

After V1 lands, the loader filter becomes `r.event_id === event`. No alias map, no JSON catalogue cross-fetch. The state context comes from the consumer (StateElection / NationalElection / state-overview.ts) which knows its state slug; the loader can additionally filter `r.state === state || r.state === "IN"` for state-scoped consumers, OR return all rows and let the consumer pick. **Verdict: filter on event_id only; consumer disambiguates by state.** Simpler contract; less coupling; matches the `(party_id, event_id, state)` PK.

### V5 — Out of scope (Phase 1b plan-doc opens after this ships)

- Backfill of new events (general-2019, general-2014, general-2009, KA-2023, UP-2022, BR-2020, TN-2021, etc.) — Phase 1b curation queue. Hans-owned per-event review.
- Year-suffix discipline on state-event alliance names (revisit after more rows land).
- Partial-attribution inline copy on `AllianceTotals` ("Some smaller parties are uncategorised…") — Jony Phase 1b.
- Alliance-tag layout overflow on long labels in `PartyBar` — Jony Phase 1b.
- Map filter by alliance (new `cellTreatment` mode) — Phase 2 chart-extension plan.
- Reconciliation with the 3-surface alliance drift (Hans R1.7 Trap 3): `party_alliances.csv` vs `parties.json::alliance_history[]` vs `alliance_membership.csv`. Separate plan-doc; not blocking Phase 1.

## Scope (this PR — rows A through G)

| # | Change | Files | Level |
| - | --- | --- | :---: |
| A | Schema v2.0 bump: drop `short_name`, rename `period_label` → `event_id`, add `state`. Update `datasets/data/_schema/columns.json` `party_alliances` section. Add `x-changelog` entry. Add migration row to `datasets/schema-evolution.json` AND `datasets/migration-ledger.csv` per CLAUDE.md §11. | `datasets/data/_schema/columns.json` · `datasets/schema-evolution.json` · `datasets/migration-ledger.csv` | 2 |
| B | Migrate the 60 existing on-disk rows. Per-event canonical event_id resolution + state assignment + FK repair on TN-2026 rows. **CRITICAL:** verify per V3 stop-condition before authoring the new TN src row. | `datasets/data/entities/party_alliances.csv` (full rewrite, 60 rows preserved with new key shape) · `datasets/data/entities/source.csv` (one new row if V3 confirms a real curation; one optional fix row if any other stale FK surfaces) | 3 |
| C | Loader rewrite per V4. Drop the alias-resolution that doesn't exist yet but is implicit in the strict-equality bug. New contract: `r.event_id === event`. Update parser to v2.0 column shape. | `frontend/src/lib/psephlab/alliances.ts` · `frontend/src/lib/psephlab/types.ts` if `AllianceLookup` shape changes | 2 |
| D | Update `state-overview.ts` consumer per V4 (it inline-reads the CSV with DuckDB-WASM; column rename + filter rewrite). | `frontend/src/lib/view-models/state-overview.ts` | 2 |
| E | Update `alliance_membership_csv.py` backend writer per Hans R3.2 verdict ("drop its second input"). The term-shape `alliance_membership.csv` should derive ONLY from `office_holdings.json`, not from `party_alliances.csv`. **OR** if disentangling the two is non-trivial, surface as STOP and defer the writer change to a separate cleanup PR (keep the schema migration backwards-compatible by NOT renaming column references in the writer this round — let it read the v2.0 CSV and continue silently using `event_id` instead of `period_label`). | `backend/yen_gov/canonical/alliance_membership_csv.py` (minimal touch only — column reference update) | 2 |
| F | Tests: vitest for `loadAlliances` covering (i) populated path on `general-2024` (LsGenJun2024 → general-2024 NDA-2024 / INDIA-2024), (ii) state-disambiguation on `assembly-2024` Maharashtra-only (no leak from other AcGenNov2024 events if any), (iii) empty path for an uncurated event. Update existing `alliances.test.ts` to v2.0 fixtures. Update `state-event-view.spec.ts` to ASSERT the populated path on `/maharashtra/elections/assembly-2024` (not the placeholder). | `frontend/src/lib/psephlab/alliances.test.ts` · `frontend/src/lib/elections/AllianceTotals.test.ts` (verify still passes with v2.0 lookup) · `frontend/e2e/state-event-view.spec.ts` | 1 |
| G | Backend pytest if the writer touched in E. CSV schema validator (Tier-A) must pass on the migrated CSV. | `backend/tests/test_party_alliances_*.py` if exists | 1 |

## Acceptance gates

| Gate | Command |
| --- | --- |
| Tier-A schema validation | `python -m yen_gov validate --root .` (or equivalent — discover via `backend/yen_gov/admin/`) passes on the migrated `party_alliances.csv` |
| svelte-check | `cd frontend; bun x svelte-check --threshold error` — 0 NEW errors vs 30 pre-existing baseline |
| vitest | `cd frontend; bun x vitest run --pool=forks --poolOptions.forks.singleFork=true` all pass; the new state-disambiguation tests are mandatory |
| playwright | `cd frontend; bun x playwright test e2e/state-event-view.spec.ts e2e/national-event-view.spec.ts e2e/elections-scatter.spec.ts` all pass |
| backend pytest | `pytest -q backend/tests` if E touched the writer; otherwise n/a |
| browser smoke 1 | `/maharashtra/elections/assembly-2024`: `AllianceTotals` shows `Mahayuti N / MVA M / Others K` headline (NOT the amber "pending" pill); `PartyBar` rows for BJP/SHS/NCP/INC/etc. carry the alliance tag |
| browser smoke 2 | `/t/elections/general-2024`: `AllianceTotals` shows `NDA-2024 / INDIA-2024 / Others` headline |
| browser smoke 3 | `/west-bengal/elections/assembly-2021`: `AllianceTotals` shows `Sanyukta Morcha / Others` headline |
| browser smoke 4 (cross-state state-scoping check) | `/kerala/elections/assembly-2021`: `AllianceTotals` shows amber pending pill (no Kerala-LDF/UDF data curated yet; CRITICAL that it does NOT show "Sanyukta Morcha" from the WB rows leaking through — proves D2 is fixed) |
| smoke console | zero `[error]` console events across all 4 smoke surfaces |

## Risk register

| # | Risk | Mitigation | Stop? |
| - | --- | --- | --- |
| 1 | The 11 TN-2026 rows describe a hypothetical future election the agent shouldn't predict. | V3 STOP-condition above. Subagent reads the 11 rows verbatim, cross-checks Wikipedia, surfaces verdict before authoring src_id. If they're hypothetical, DELETE them (do not relocate). | YES |
| 2 | `alliance_membership_csv.py` writer breaks because of the column rename. | Row E mitigation: minimal touch (rename `period_label` → `event_id` in column references) without disentangling the two-input issue. The two-input cleanup is a separate Phase 1b plan-doc. | NO (engineering only) |
| 3 | Existing `alliances.test.ts` fixtures use the old `period_label` shape and will fail. | Row F: update fixtures to v2.0 shape; add new state-disambiguation cases. | NO |
| 4 | `AllianceTotals.svelte` race-guard at `if (ev === event) lookup = l` already exists per Max R4.1. Renaming variable from `period_label` to `event` may collide with the existing `ev` shadow. | Read end-to-end before touching. Variable names are local; the contract is the loader's return type. | NO |
| 5 | The DuckDB-WASM inline `read_csv(...)` in `state-overview.ts` may have hardcoded column names. | Row D: grep the file for `period_label` and `short_name` references, rename per v2.0. | NO |
| 6 | Tier-A validator may have a hardcoded column-list assertion for `party_alliances`. | Update validator if needed (Row A); the schema bump entry in `columns.json` is authoritative. | NO |
| 7 | The 4 already-curated events being lit up may surprise downstream consumers (e.g. AllianceTotals' empty state was the assumed default in tests / docs). | Browser smoke + e2e assertion changes (Row F) cover this. Update any docs that assert the placeholder behaviour. | NO |

## Implementation discipline

- **Worktree:** subagent works in `..\yen-gov-alliance-v2` on branch `feat/alliance-schema-v2-and-loader-fix` (file-disjoint from active worktrees per master-collision protection).
- **§13 UI verification:** subagent MUST hit all 4 browser smoke surfaces. Cross-state state-scoping check (smoke 4) is critical.
- **§7 debug logs:** zero `[DEBUG]` markers at PR finish.
- **§8 git hygiene:** named branch, explicit-path `git add`, squash-merge, post-merge cleanup. NO `git add .` / `-A`.
- **§9 lockfile:** zero `package.json` changes expected.
- **CLAUDE.md §10 STOP-AND-SURFACE:** Risk #1 (hypothetical TN-2026 rows) is the explicit stop-condition. Surface verdict before authoring.

## Out of scope (Phase 1b plan-doc opens after this ships)

See V5 above. Critically: the Wikipedia per-event backfill (general-2019/2014/2009, KA-2023, UP-2022, BR-2020, TN-2021, etc.) is a SEPARATE plan-doc requiring Hans-owned per-event curation review. This PR opens that plan-doc (Phase 1b) at the same time it ships Phase 1.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | research | Hans (R1-R3) + Max (R4-R5) joint verdict. Both surfaced D1/D2/D3 as structural fixes that must precede any backfill. Wikipedia named as Phase 1b source. |
| 2026-06-12 | scope-lock | This PR ships V1-V4 (schema v2.0 + 60-row migration + loader rewrite + FK repair). Phase 1b backfill is separate plan-doc opened concurrently. |
| 2026-06-12 | scope-correction | First dispatch subagent STOP-AND-SURFACED on Risk #1: plan-doc V3's premise ("TN-2026 hasn't happened") was empirically wrong. TN-AE-2026 has happened; 6694 rows of polled outcomes in `tamil-nadu_election_results.csv`. The 10 alliance rows describe post-2023 BJP-AIADMK fracture landscape. V3 revised with Resolution A: relocate to `event_id=assembly-2026` + `state=IN-S22` + new Wikipedia src_id for the 2026 TN AE article. Re-dispatched with corrected brief. |

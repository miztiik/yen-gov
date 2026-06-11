# Sources simplification — extraordinary cleanup plan

**Last Updated**: 2026-06-11
**Status**: PR-0 in flight. PR-1 not started.
**Level**: 3 (cross-cutting; 2 PRs; provenance + 6 chart renderers + doctrine; reversible).
**Strategy**: shrink the aspirational 11-col v2 citation ledger to the 5-col on-disk reality + collapse multi-line provenance footer to one publisher-pill row + delete the v2 dead-branch render stack. Two PRs total.

> User mandate, 2026-06-11: "sources is becoming nuisance, we need to simplify extraordinarily. extraordinarily." + "let's update docs and architecture on src hash map tracking that is becoming nonsense. clean, major clean up." Triggered by a screenshot of the current footer (RBI State Finances chart) showing the multi-line ledger + license-terms link + fetched-at timestamp + schema-version chip + "Hand-authored — see commit history" empty-state copy.

> **This plan supersedes nothing in the citation-as-(producer,title,vintage)-triple identity contract.** ADR-0032 + ADR-0042 survive on identity. What dies is the 6-column OWID-extension aspiration (`license`, `confidence_tier`, `is_issuing_authority`, `verification_method`, `citation_full`, `notes`) that was declared in v2.0 doctrine but never populated by any writer in the 6+ weeks since landing. The on-disk truth at `datasets/data/_schema/columns.json` already declares the 5-col shape (notes: "Exactly five columns per plan section 7 (O3)"); CLAUDE.md §12 + data-provenance.md are just stale.

---

## Section 0 — Operating contract

### 0.1 What this plan does

| Surface | Today | After this plan |
|---|---|---|
| Schema doctrine (CLAUDE.md §12, data-provenance.md) | 11 cols claimed | 5 cols binding (truth on disk) |
| Column name | `owner` (on disk), `producer` (doctrine + alias) | `producer` everywhere |
| Frontend render — single publisher | `▸ Sources (1) · schema v6.0` → expand → "RBI 'State Finances...' · official series · 2025-26 · Gold — issuing authority · Live-fetched · OGL India v1.0 · Publisher page" + "Methodology: ..., fetched 2026-05-11T15:18:58Z" + "Government of India open publication" + license-terms link | `Source: RBI State Finances (2025-26)   (i)` |
| Frontend render — multi-publisher | Same multi-line ledger × N | `Source: RBI State Finances, ECI Statistical Reports   (i)` (max 3 inline, `+N more` after) |
| Frontend render — empty sources | `▸ Sources (0) · schema v6.1` → expand → "Hand-authored — see commit history for rationale." | row hidden entirely |
| Info-icon copy | "About this data" (already correct) | "About this data" (uniform across surfaces; Jony verdict — no change to existing AboutThisData copy) |
| Components | `SourceList.svelte` (v1, live in AboutThisData) + `SourceListV2.svelte` (v2, live in 6 surfaces but rendering 6 NULL fields with degraded labels) + `source-list-v2/` package | ONE `SourceList.svelte` (rebuilt) + `sources/` package (renamed) |
| ledger row grain | one row per `(producer, title, vintage)` triple — **unchanged** | one row per `(producer, title, vintage)` triple — **unchanged** |
| Render-time dedup | none (every triple renders as its own row) | dedup to one pill per `(producer × series_family)` where `series_family` is derived from the title's leading clause |
| Schema-version chip on cards | shown ("schema v6.0") | deleted from cards; survives on `IndicatorDoc.svelte` route only |
| "Hand-authored — see commit history" empty copy | shown | deleted everywhere |
| License-terms link, fetched-at timestamp, confidence/verification chips, "Government of India open publication" class-level pill | shown | deleted everywhere |

### 0.2 What this plan does NOT do

- Re-litigate citation-as-`(producer, title, vintage)` identity (ADR-0032 + ADR-0042 survive on identity).
- Touch the `derive_source_id` hash. 3-arg signature `(producer, title, vintage)` preserved.
- Collapse the on-disk ledger grain. The CSV stays at title-vintage grain; simplification is a render-time aggregator only (Gregor verdict — preserves vintage cite-ability, reversibility, OWID parallel).
- Touch backend writers' value emissions (only the constant name `owner` → `producer`).
- Touch any data observation row.
- Ship the issuing-authority warning (`⚠ Includes Wikipedia-derived data`). Deferred to PR-2 after real-world card behaviour is observed.
- Touch `IndicatorDoc.svelte`'s content rendering (only its provenance sub-block uses the new component).
- Touch tests for behaviour outside the provenance footer.

### 0.3 ESCALATE triggers

The orchestrator stops ONLY at:

1. **A consumer of `taxonomy.sources` SQL projection breaks at the seam.** PR-1 drops the `owner AS producer` alias from `frontend/src/lib/duckdb.ts`. If a view-model that reads `s.producer` was actually reading through the alias and silently broke, surface — don't silently break the frontend.
2. **A 7th SourceListV2 caller discovered mid-PR-1.** The 6-caller list (StateOverview, AboutThisData, ElectionSeatsTrend, IndicatorChoropleth, Yenask, ChartShell, plus the composition-bar adapter) was hand-verified by grep in PR-0. If PR-1 finds a 7th, fold it in without surfacing; if it has fundamentally different shape requirements (e.g. takes a different prop type), STOP-AND-SURFACE.
3. **Backend pytest regression on the `owner`→`producer` writer rename.** The 4 writer files use `owner` as a hand-typed constant. Rename + test green = ship. Rename + test red on something OTHER than the constant name = STOP-AND-SURFACE.

### 0.4 Baked facts (verified 2026-06-11; do not re-derive)

| Fact | Value |
|---|---|
| On-disk source.csv columns | 5: `source_id` (pk), `owner`, `title`, `vintage`, `url` (per [datasets/data/_schema/columns.json](../datasets/data/_schema/columns.json) line 132-143) |
| Doctrine claim | 11 cols (CLAUDE.md §12; data-provenance.md "The 11 columns") — STALE |
| Hash function | `"src-" + sha256(f"{producer}|{title}|{vintage}".encode()).hexdigest()[:12]` ([backend/yen_gov/canonical/citation.py](../backend/yen_gov/canonical/citation.py) `derive_source_id`) |
| DuckDB seam | [frontend/src/lib/duckdb.ts](../frontend/src/lib/duckdb.ts#L472) aliases `owner AS producer` + `url AS url_main` + projects 6 NULLs for the missing v2 cols |
| Live v1 SourceList callers | 1: [AboutThisData.svelte:158](../frontend/src/lib/AboutThisData.svelte#L158) — renders BOTH v1 AND v2 simultaneously when `artifact.sources` AND `sources_v2` both populated |
| Live v2 SourceListV2 callers | 6: [AboutThisData.svelte:156](../frontend/src/lib/AboutThisData.svelte#L156), [StateOverview.svelte:868](../frontend/src/routes/StateOverview.svelte#L868), [ElectionSeatsTrend.svelte:170](../frontend/src/lib/ElectionSeatsTrend.svelte#L170), [IndicatorChoropleth.svelte:161](../frontend/src/lib/IndicatorChoropleth.svelte#L161), [Yenask.svelte:916](../frontend/src/routes/Yenask.svelte#L916), [ChartShell.svelte:289](../frontend/src/lib/charts/ChartShell.svelte#L289) |
| Currently-shipping degraded UX | SourceListV2 renders labels "License unknown", "Confidence unknown", "Verification unknown" on EVERY row because 6 of the 11 cols are NULL on disk |
| View-models that populate `sources_v2` | [view-models/state-overview.ts:474-505](../frontend/src/lib/view-models/state-overview.ts#L474), [charts/composition-bar/adapter-elections-seats.ts:495](../frontend/src/lib/charts/composition-bar/adapter-elections-seats.ts#L495), [canonical/indicator-from-canonical.ts:265-340](../frontend/src/lib/canonical/indicator-from-canonical.ts#L265) |
| Existing pill grammar to reuse | `inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium` ([ListBadge.svelte:38-48](../frontend/src/lib/ListBadge.svelte#L38)) — but Jony verdict picks plain-text middot, NOT this pill |
| Plain-text classes (Jony spec) | label: `text-slate-400 text-[11px]`; names: `text-slate-700 text-[11px] hover:underline`; separators: `text-slate-300` middots |
| `IndicatorDoc` route | EXISTS at `/docs/indicator/:indicator_id` ([frontend/src/routes/IndicatorDoc.svelte](../frontend/src/routes/IndicatorDoc.svelte)) — overflow target for "Read full methodology →" link |
| Backend writers using `owner` constant | [`_run_*.py` files in seed/ + reingest/] (4 files: `_run_alliance_membership.py`, `_run_eci_seed.py`, `_run_tcpd_*.py`, `_run_electoral_from_snapshot.py` fallback fieldnames) |
| Contract tests touching v2 shape | [sources-v2-shape.test.ts](../frontend/src/contracts/sources-v2-shape.test.ts) (REWRITE), [source-list-v2/format.test.ts](../frontend/src/lib/source-list-v2/format.test.ts) (REWRITE) |

### 0.5 Decisions ratified (cross-reference for PR-1 brief)

| Decision | Verdict | Authority |
|---|---|---|
| Pill grain | Publisher × major-series + edition (`RBI State Finances (2025-26)`) | User pick after Hans + Jony debate (2026-06-11) |
| Series_family derivation | First clause of `title` before colon/comma/em-dash (computed in view-model) | Hans + Gregor |
| Pill style | Plain text middot, NO chip/bg/border | Jony |
| Pill copy | Compact abbreviation per hand-authored `PUBLISHER_DISPLAY` map; default to raw `producer` | Jony |
| Click behaviour | Navigate to `url` in new tab; mute (no link) when `url` empty | Jony |
| Multi-publisher density | ≤3 inline; ≥4 → "first 3, +N more" (no wrap, no scroll) | Jony |
| Info-icon copy | "About this data" uniform across surfaces | Jony |
| Empty state | Hide row entirely | User + Jony |
| Schema-version chip on cards | Delete from cards; retain on IndicatorDoc page | All personas |
| "Hand-authored — see commit history" | Delete everywhere | All personas |
| Schema doctrine | Path α — shrink to 5 cols binding | Hans + Gregor |
| `owner` → `producer` rename | Yes, low cost, ship in PR-1 | Gregor |
| `url` → `url_main` rename | NO — keep `url` (no `url_download` distinction to disambiguate) | Gregor |
| `derive_source_id` hash | Unchanged: `(producer, title, vintage)` 3-arg | Gregor (preserved Holy Law #9 surface) |
| Issuing-authority warning | DEFER to PR-2 | User pick |
| ADR-0032 status | Superseded on field count; identity-on-triple survives | Gregor |
| ADR-0042 status | Unchanged | Gregor |
| New ADR-NNNN | Inline in data-provenance.md per ADR-0034 ADR-into-subsystem-doc rule | Gregor |

### 0.6 Per-PR workflow

Same as the rest of the repo:
1. Branch off `origin/main`.
2. Implement scope. Tests ship with the row.
3. Local gates GREEN (vitest, svelte-check, integrated-browser smoke per CLAUDE.md §13).
4. Commit + push + `gh pr merge --squash --admin --delete-branch`. Don't wait for remote CI.
5. Pull main. Start next row.

### 0.7 Closure

Plan complete when PR-1 ships green. PR-2 (issuing-authority warning) is deferred indefinitely until user trigger.

---

## Section 1 — Status Reckoner

| Row | Title | Depends on | Status | PR | Effort |
|---|---|---|---|---|---|
| PR-0 | Plan-doc + doctrine rewrites (CLAUDE.md §12 + data-provenance.md + canonical-store.md) + new `sources/` package dark + contract test | none | [ ] PENDING | _pending_ | S |
| PR-1 | Backend `owner`→`producer` rename + drop DuckDB seam alias + rewrite SourceList component + rewire 6 callers + delete v2 dead branch + delete v1 SourceList + delete legacy helpers | PR-0 | [ ] PENDING | _pending_ | L |
| PR-2 (deferred) | Issuing-authority warning surface (Hans's `⚠ Includes Wikipedia-derived data`). User-triggered, not date-gated. | PR-1 + real-world feedback | [ ] DEFERRED | — | XS |

**Effort key**: XS = <1h · S = 1-3h · M = half-day · L = full-day.

**Critical path:** PR-0 → PR-1. **Total active work: 2 sequential PRs.**

---

## Section 2 — PR-0 specification (orchestrator-authored in master worktree)

### 2.1 Scope

Land the binding doctrine + the new dark component + the contract test. **Zero existing-component changes; zero caller changes; zero backend changes.** Reviewers can read this PR in 10 minutes and understand the new contract. After merge, PR-1 will do the mechanical rewrites against this contract.

### 2.2 Files touched

**NEW files:**
- `TODO/20260611-sources-simplification-plan.md` — this plan-doc.
- `frontend/src/lib/sources/types.ts` — `SourceRow` (5-col shape) + `PublisherPill` (view-model output: deduped publisher × series_family + vintage summary + url + count). No enums for `license`/`confidence_tier`/`verification_method`.
- `frontend/src/lib/sources/format.ts` — pure helpers: `publisherDisplay(producer)`, `seriesFamily(title)`, `summarizeVintages(vintages)`, `dedupeToPills(rows)`. No DOM, no Svelte imports.
- `frontend/src/lib/sources/format.test.ts` — vitest unit tests for the 4 helpers above. ≥15 cases covering dedup, vintage summary ("2025-26" single, "2022-23 to 2025-26" range, "various" mixed), publisher display map fallback, series_family extraction edge cases (no colon, colon + comma, em-dash).
- `frontend/src/lib/sources/SourceList.svelte` — the new component (NOT yet imported by any caller). Renders the publisher-pill row from `PublisherPill[]` input. Implements:
  - Empty input → renders nothing (no row, no whitespace).
  - 1-3 pills → all inline.
  - 4+ pills → first 3 + `+N more` token where the `+N more` is a button that toggles to show the full list inline (no overlay, no popover; just inline expansion below the truncated row).
  - Mute (plain text, no link) when `pill.url` is null/empty; otherwise `<a target="_blank" rel="noopener noreferrer">`.
  - No info-icon. The info-icon stays where it already lives (`AboutThisData.svelte`).
- `frontend/src/lib/sources/index.ts` — barrel export.
- `frontend/src/lib/sources/README.md` — 30-line README naming the contract surface + the deletion targets + the migration path.
- `frontend/src/contracts/sources-pill-shape.test.ts` — contract test asserting (a) `SourceRow` shape has exactly 5 keys; (b) `dedupeToPills([])` returns `[]`; (c) `dedupeToPills` collapses multi-vintage same-(producer×series) input to 1 pill with vintage summary; (d) `publisherDisplay("Reserve Bank of India")` returns `"RBI"`; (e) the 8 publishers in the PUBLISHER_DISPLAY map all have a 2-12 char mapping.

**EDITED files:**
- `CLAUDE.md` — §12 rewrite: "11 columns, 8 required + 3 optional" → "5 columns (`source_id` pk, `producer`, `title`, `vintage`, `url`); identity-as-`(producer,title,vintage)`-triple unchanged"; inline `MIGRATING (PR-1)` marker on the `owner`→`producer` writer rename + the v2 dead-branch deletion.
- `docs/concepts/data-provenance.md` — rewrite section "The 11 columns" → "The 5 columns"; add new inline ADR-NNNN `citation-ledger-5col` (rejected β backfill-with-sentinels + γ ops-annotation-layer); update ADR-0032 status pointer "superseded on field count by ADR-NNNN, 2026-06-11; identity-on-triple survives"; ADR-0042 body unchanged.
- `docs/architecture/data/canonical-store.md` §5 — rewrite the source schema table to the 5-col shape + add OWID-deviation note ("we ship `url` not `url_main` because we don't surface `url_download`").

**NOT touched in PR-0:**
- Any existing Svelte component.
- Any existing view-model.
- Any existing backend file.
- Any existing CSV.
- The DuckDB seam (`owner AS producer` alias survives until PR-1).
- The v1 `SourceList.svelte` + v2 `SourceListV2.svelte` + `source-list-v2/` package.

### 2.3 Acceptance gates

| Gate | Command | Pass |
|---|---|---|
| 1. svelte-check | `cd frontend; bun run check` | 0 errors. New `sources/` package type-checks. |
| 2. vitest | `cd frontend; bun x vitest run --reporter=basic` | All new format.test.ts + sources-pill-shape.test.ts pass. No EXISTING test broken (we touched nothing live). |
| 3. plan-doc + doctrine spot-check | manual grep | CLAUDE.md §12 says "5 columns"; data-provenance.md "The 5 columns" present; canonical-store.md §5 table is 5-col; new sources/README.md exists. |
| 4. PR diff size | `gh pr diff --stat` | ≤700 lines (plan-doc is the bulk). |

**No browser smoke** — PR-0 touches zero render path.
**No backend tests** — PR-0 touches zero backend file.

### 2.4 Load-bearing oracle for PR-0

> The repo can be reviewed for the new sources contract by reading exactly two files: this plan-doc + `frontend/src/lib/sources/README.md`. Every claim about the rewrite (what the pill looks like, what `dedupeToPills` does, why we deleted the 6 cols) is grep-traceable from those two files to either persona verdicts archived in this plan-doc, or to grep hits in the new `sources/` package.

---

## Section 3 — PR-1 specification (subagent in sub-worktree)

### 3.1 Scope

Atomic landing of the contract switch. After this PR:
- The CSV header on `datasets/data/entities/source.csv` is `producer` (was `owner`).
- The 4 backend writers emit `producer` (constant rename only; values unchanged).
- The DuckDB seam in `frontend/src/lib/duckdb.ts` drops the `owner AS producer` alias (column is now natively `producer`).
- All 6 SourceListV2 callers + the 1 v1 caller migrate to the new `sources/SourceList`.
- Each caller hands a `PublisherPill[]` (NOT `SourceV2Row[]`); the view-models do the dedup via `dedupeToPills`.
- `SourceList.svelte` (the v1 file at `frontend/src/lib/SourceList.svelte`) is DELETED.
- `SourceListV2.svelte` is DELETED.
- `source-list-v2/` package is DELETED.
- The `sources/SourceList.svelte` from PR-0 IS the new component (component name is `SourceList`; package is `sources/`).
- The "Hand-authored — see commit history for rationale" copy is gone from every render path.
- The schema-version chip is gone from every chart card; still present on IndicatorDoc.

### 3.2 Files touched

**Backend (writer constant renames — single-line edits per file):**
- `backend/yen_gov/canonical/seed/_run_alliance_membership.py` — `"owner": LGD_SOURCE_OWNER` → `"producer": LGD_SOURCE_OWNER` (the constant name `LGD_SOURCE_OWNER` MAY also rename to `LGD_SOURCE_PRODUCER` — subagent's call, low priority).
- `backend/yen_gov/canonical/seed/_run_eci_seed.py` — same pattern, `"owner": ECI_OWNER` → `"producer": ECI_OWNER`.
- `backend/yen_gov/canonical/reingest/_run_tcpd_ae_results.py` (or whichever TCPD reingest writer holds the `owner` constant; subagent grep `'"owner":' backend/` to find the canonical list).
- `backend/yen_gov/canonical/reingest/_run_tcpd_ge_results.py` (ditto).
- `backend/yen_gov/canonical/electoral/_run_electoral_from_snapshot.py` — the fallback fieldnames constant if it lists `owner`.

**Backend tests (column-rename mirror):**
- `backend/tests/test_alliance_membership_csv.py`
- `backend/tests/test_csv_writer.py`
- `backend/tests/test_csv_columns.py`
- Any other test that asserts on `owner` as a column name; subagent greps `'owner' backend/tests/` and updates the hits.

**On-disk CSV (one rename):**
- `datasets/data/entities/source.csv` — header row first column rename `owner` → `producer`. **Body unchanged.** This MUST be the same commit as the writer + schema changes; partial state = broken FE.

**Schema:**
- `datasets/data/_schema/columns.json` — rename the `"owner"` entry under `entities/source.csv` to `"producer"`. Update the `notes` field to remove the historical "O3" reference if any; otherwise leave the notes prose alone.

**Frontend wiring + component rewrites:**
- `frontend/src/lib/duckdb.ts` — drop the `owner AS producer` alias (the source.csv column is natively `producer` now); drop the 6 NULL projections (`license`, `confidence_tier`, `is_issuing_authority`, `verification_method`, `citation_full`, `notes`); drop the `url AS url_main` alias (we keep `url`).
- `frontend/src/lib/view-models/state-overview.ts` — replace `sources_v2: SourceV2Row[]` field with `pills: PublisherPill[]`; the JOIN query result now has 5 cols; pass through `dedupeToPills(rows)`.
- `frontend/src/lib/charts/composition-bar/adapter-elections-seats.ts` — same pattern (projectSourcesV2 → `dedupeToPills`).
- `frontend/src/lib/canonical/indicator-from-canonical.ts` — same pattern (`buildSourcesV2` → returns `PublisherPill[]` via `dedupeToPills`); drop the 6 `SourceV2Row["license"]` etc. type references.
- `frontend/src/lib/AboutThisData.svelte` — replace BOTH v1 `<SourceList>` and v2 `<SourceListV2>` blocks with ONE `<SourceList pills={pills} />` block from the new `sources/` package. Drop the `sources_v2 = $derived(indicatorArtifactSourcesV2(artifact))` line.
- `frontend/src/routes/StateOverview.svelte` — `<SourceListV2 sources={summary.sources_v2} />` → `<SourceList pills={summary.pills} />`.
- `frontend/src/lib/ElectionSeatsTrend.svelte` — same.
- `frontend/src/lib/IndicatorChoropleth.svelte` — same.
- `frontend/src/routes/Yenask.svelte` — same (and update the `SourceV2Row` import).
- `frontend/src/lib/charts/ChartShell.svelte` — same; drop the `schema_version` prop pass-through if unused after the chip-deletion.
- `frontend/src/routes/IndicatorDoc.svelte` — replace the inline `projectToFourFieldSource` rendering with `<SourceList pills={pills} />`. KEEP the schema-version surfacing inline (per persona verdict — IndicatorDoc is the route where curator can read it). Drop the v1-style 4-field rendering helper.

**Frontend deletions:**
- `frontend/src/lib/SourceList.svelte` — DELETE (the v1 file).
- `frontend/src/lib/SourceListV2.svelte` — DELETE.
- `frontend/src/lib/source-list-v2/` — DELETE the entire package: `types.ts`, `format.ts`, `format.test.ts`, `index.ts`, `README.md`.
- `frontend/src/contracts/sources-v2-shape.test.ts` — DELETE (the new `sources-pill-shape.test.ts` from PR-0 replaces it).
- `frontend/src/lib/yenask/execute-plan.ts` line ~101 `coerceSourceRow` — DELETE the safe-default enum sentinel patching (no enums anymore).
- Any other dead helper that exists only to feed the 11-col shape (subagent grep `SourceV2Row\|sources_v2\|projectSourcesV2\|coerceSourceRow\|FORBIDDEN_SOURCE_FIELDS\|verificationMethodRank` and rip).

**Test updates:**
- `frontend/src/contracts/datasets-conform.test.ts` — update column-shape assertion to expect `producer` (was `owner`); the 5-col list stays the same.
- `frontend/src/routes/IndicatorDoc.test.ts` — replace `projectToFourFieldSource` assertions with `dedupeToPills` assertions.
- `frontend/src/lib/canonical/indicator-from-canonical.test.ts` — `sources_v2` assertions → `pills` assertions.

### 3.3 Acceptance gates

| Gate | Command | Pass |
|---|---|---|
| 1. svelte-check | `cd frontend; bun run check` | 0 errors. |
| 2. vitest | `cd frontend; bun x vitest run` | All green. |
| 3. backend pytest | `cd backend; pytest -q` | All green. |
| 4. validate | `python -m yen_gov validate --root .` | 0 errors. |
| 5. integrated-browser smoke | Per CLAUDE.md §13. Navigate (a) `/tamil-nadu` (StateOverview footer pills), (b) one indicator page (IndicatorChoropleth footer pills), (c) one election page (ElectionSeatsTrend footer pills). Confirm: zero "License unknown" / "Confidence unknown" / "Verification unknown" labels in DOM; zero "Hand-authored — see commit history" text; zero "schema v" string. Confirm pill rows render. | DOM grep returns 0 hits for all forbidden labels; visible pills match expected publisher list per route. |

### 3.4 Load-bearing oracle for PR-1

> `git grep -E 'SourceListV2\|SourceV2Row\|sources_v2\|source-list-v2\|projectSourcesV2\|coerceSourceRow\|verificationMethodRank\|"License unknown"\|"Confidence unknown"\|"Verification unknown"\|"Hand-authored — see commit history"' frontend/ backend/` returns ZERO hits. The doctrinal grep at `git grep -E '11 columns\|11-column citation ledger' docs/ CLAUDE.md` returns ZERO hits.

---

## Section 4 — Persona verdicts archive (PR-0 ratifies these)

The 4 persona verdicts that drove decisions in §0.5 are archived inline. Future agents reading this plan-doc do NOT need to re-run the debate.

### 4.1 Jony (UI/UX) — pill grammar verdict

- Pill shape: PLAIN TEXT middot-separated; NOT a chip-pill. Tag pills compete with the meaningful category chips (Union/State/Concurrent list, doc_status amber dot). Reserve pill grammar for category, not provenance.
- Pill copy: compact abbreviation always; hand-authored `PUBLISHER_DISPLAY` map keyed on `producer`; default to raw producer if unmapped. NO hover tooltip (mobile citizens cannot hover).
- Click: navigate to `url` in new tab; mute (plain text, no link) when `url` empty. NO inline popover (fights platform back-swipe). NO `/docs/indicator/<id>` route nav (strips chart context).
- Multi-publisher density: ≤3 inline; ≥4 → "first 3, +N more" inline-expand. Never wrap. Never scroll.
- Info-icon copy: "About this data" uniform; NOT "About data & Maps" ("Maps" lies on bar charts).
- Sources pills OUTSIDE the info-icon (always-visible). Info-icon expand carries the long-form (methodology, scope, caveats, breaks, full citation).
- Empty state: hide row entirely. "Hand-authored — see commit history" deleted; the doc_status amber dot in AboutThisData already carries the operator signal.
- Schema-version chip: delete from card; survives on IndicatorDoc route.

### 4.2 Hans (Governance) — citation integrity verdict

- Pill grain: publisher × major-series + edition. `Source: RBI State Finances (2025-26 ed.)`, not bare `Source: RBI`. RBI has 3 active flagship publications; collapsing them to "RBI" is a Rosling Destiny trap.
- Series_family is derivable from `title` (leading clause before colon/comma); no new schema column needed.
- WHAT IS LOST on dedup-to-publisher (the trap to avoid): WHICH RBI report, WHICH vintage. Both must survive in pill text.
- WHAT IS DROPPED: fetched-at timestamp (citizen does not care); license terms (republisher concern, not citizen-reading-a-chart); confidence-tier / verification-method per row (researcher-grade); "Government of India open publication" class-level pill (double-codes publisher; invites generalisation failure).
- Issuing-authority warning: conditional one-line `⚠ Includes Wikipedia-derived data` ONLY when card mixes issuing-authority + non-authority publishers. Cost: 4-line view-model + hand-authored 8-publisher allow-list. **DEFERRED to PR-2 per user pick.**
- 11→5 col reckoning: path α (shrink to 5 cols). Backfilling sentinels (β) is data-laundering; operator-only annotation layer (γ) creates a second provenance surface — exactly what ADR-0032 set out to eliminate.

### 4.3 Gregor (Architect) — schema contract verdict

- On-disk wins. The 5-col CSV is the contract. CLAUDE.md §12's 11-col claim is decoration (writers never honored it).
- Path α (shrink doctrine). β (backfill) commits ~500 rows of hand-author work to populate fields the citizen never needed. γ (middle path) keeps two surfaces.
- Rename `owner` → `producer`: yes, low cost. `owner` is semantically wrong; every citation standard (OWID, DataCite, Dublin Core, BibTeX) uses producer/publisher framing.
- Rename `url` → `url_main`: NO. OWID's `url_main` exists to distinguish from `url_download`; we ship one URL. Document the deviation per The One Rule.
- Hash key stays `(producer, title, vintage)`. UX simplification is a render-time Aggregator; ledger never simplifies. OWID precedent: same separation between origins (citation triple) and rendered "Data published by" footer.
- Rewrite SourceListV2 in-place to the new pill shape, then atomically rename to `SourceList` and delete v1. Salvage package structure (types + format split); rewrite every body.
- CLAUDE.md §12 gets immediate in-place rewrite in PR-0. data-provenance.md gets in-place rewrite. ADR-0032 status: "superseded on field count by ADR-NNNN-citation-ledger-5col, 2026-06-11; identity-on-triple survives." ADR-0042 unchanged.
- PR topology: PR-0 (doctrine, zero code) + PR-1 (code, one atomic landing). Don't split PR-1 into 1a/1b — the rename + view-model + alias drop are mechanically coupled.

### 4.4 Citizen User — gut-check verdict

- "Source: [publisher]" is enough for trust if the publisher is a known brand (RBI, ECI). Wants ONE more breadcrumb (data period like "FY 2024-25") on the card.
- Info-icon expand top-3 wants: (1) plain English of what the metric means, (2) what period the data covers + when publisher published, (3) link to publisher page for sharing on WhatsApp. NOT CSV download.
- Trusts RBI > ECI > Wikipedia. One-word cue ("Official" / "Compiled" / "Crowdsourced") or checkmark on official would help. **NOTE: deferred to PR-2.**
- "Fetched at" timestamp: does not matter. Prefers "Data through FY 2024-25" (period covered).
- 4 publishers wrapping to 2 lines on phone: acceptable IF visually distinguishable (colour-match to chart series OR mark one as primary). **NOTE: solved structurally by Hans verdict's "publisher × series" grain — most pills will read distinctly.**

---

## Section 5 — Doctrine reconciliation (per CLAUDE.md two-phase rule)

PR-0 makes the new 5-col contract BINDING in CLAUDE.md §12 + data-provenance.md + canonical-store.md §5. The actual code state on the moment PR-0 lands:

| Surface | State on PR-0 merge | MIGRATING marker? |
|---|---|---|
| `datasets/data/entities/source.csv` header | `owner` (unchanged) | YES — `MIGRATING (PR-1)`: header renames `owner`→`producer` |
| `datasets/data/_schema/columns.json` source.csv block | `owner` (unchanged) | YES — `MIGRATING (PR-1)` |
| Backend writers | emit `owner` (unchanged) | YES — `MIGRATING (PR-1)` |
| `frontend/src/lib/duckdb.ts` alias | `owner AS producer` (unchanged) | YES — `MIGRATING (PR-1)`: alias drops |
| v1 `SourceList.svelte` | live (unchanged) | YES — `MIGRATING (PR-1)`: deleted |
| v2 `SourceListV2.svelte` | live in 6 callers (unchanged) | YES — `MIGRATING (PR-1)`: deleted |
| New `sources/` package | shipped, NOT yet wired | NO (it's the new truth) |
| 6 OWID-extension cols (license, confidence_tier, ...) | not on disk, claimed in CLAUDE.md doctrine | The DOCTRINE delete is unconditional; on-disk is already 5-col. No MIGRATING needed for the deletion of the 6 cols from §12. |

Per the CLAUDE.md top-of-file two-phase rule: doctrine is rewritten when its new truth is binding regardless of code state; inline `MIGRATING (chunk)` markers cover facts that only become true mid-rip. The 5-col binding is true on disk RIGHT NOW; the writer/reader/component cleanup is the PR-1 rip.

---

## Execution contract (autonomous — follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block — the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. PR-0 is orchestrator-authored in a sub-worktree (`git worktree add ../yen-gov-sources-pr0 -b feat/sources-pr0-doctrine origin/main`); PR-1 is dispatched to a stateless `runSubagent` brief in a separate sub-worktree (`git worktree add ../yen-gov-sources-pr1 -b feat/sources-pr1-rewrite origin/main`). The subagent does the row; the orchestrator merges and moves on. **Master worktree is never the work site** — too vulnerable to parallel-agent stash collision (2026-06-11 lesson).
2. **One row = one PR = one branch.** Park master on `scratch-master-parking-2026-06-10` between PR-0 and PR-1 so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition of Done, browser-verify per CLAUDE.md §13 for PR-1.
3. **Ship loop, non-stop.** Don't wait for remote CI. As soon as gates are green locally, `gh pr merge --squash --admin --delete-branch`. Pull main, start next row.
4. **Tests ship with the row.** PR-0 ships `format.test.ts` + `sources-pill-shape.test.ts`. PR-1 updates the existing tests + deletes the now-dead `sources-v2-shape.test.ts` + `format.test.ts` (v2 one).
5. **Persona debate already converged.** §4 archives the 4 verdicts. PR-1 subagent reads §3 + §4 and proceeds; no further persona dispatch.
6. **Manage context via offload.** PR-1 brief is a self-contained subagent message. Orchestrator holds only the Reckoner + the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
8. **Stop only at a real boundary.** The 3 ESCALATE triggers in §0.3. Otherwise do not pause; the user is not watching.
9. **Closure.** Done when PR-0 + PR-1 are both MERGED + PUSHED. Archive the plan-doc per `docs/how-to/distill-a-plan.md`. PR-2 stays in the Status Reckoner as DEFERRED until user trigger.

---

## See also

- [CLAUDE.md](../CLAUDE.md) §12 (Data Provenance) — the surface being rewritten in PR-0.
- [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md) — the concept doc being rewritten in PR-0.
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) §5 — sources schema table being rewritten.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) — PR lifecycle.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) — closure ritual.

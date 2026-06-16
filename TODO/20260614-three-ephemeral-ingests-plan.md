# 2026-06-14 three ephemeral ingests plan (affidavits + seizures + TN gender)

**Last Updated**: 2026-06-14
**Level**: 4 (multi-PR structural; cross-subsystem)
**Authoring personas**: Hans (governance framing), Max (indicator shape), Fowler (engineering craft), Jony (UX)
**Authoring receipt**: User-named source files at `datasets/ephemeral/{2014_lok_sabha_affidavits,2019_eci_seizures,tn_acwise_gendercount}.csv`, ratified 2026-06-14 with 5 binding decisions captured in section 0.3.

---

## 0. Operating contract

### 0.1 Why this plan exists

The user dropped three citizen-relevant data files into `datasets/ephemeral/` and asked Fowler + Hans (+ Jony for UX) to enrich the canonical store and surface them in the UI. After parallel persona consultation (transcripts cited in section 0.2), the work decomposes into FOUR PRs covering three new data shapes plus one citizen-UX shipment. Bundling the four was rejected (zero shared writer code, three orthogonal review surfaces, mixed risk profiles).

### 0.2 Persona convergence (one-line verdicts)

- **Hans**: Ingest 2014 affidavits and 2019 seizures with caveats; **TN gender file was BLOCKED pending vintage recovery** — user named `2021` (pre-AE 2021 final roll) so the blocker is lifted. Winners-only framing must be loud on PR-B. Refuse `TOTAL seizure` mixed-unit persistence on PR-A.
- **Max**: Affidavits = extend `candidacies.csv` with 4 nullable disclosure columns (entity-attributes on dim, NOT indicator rows). Seizures = new per-event CSV under `datasets/elections/parliament/election=2019/mcc_seizures.csv` (per-event-self-contained convention). TN gender = **FACET on existing `electors` concept**, not a new mint (ADR-0044 identity test: same noun + unit + grain -> facet). Specific canonical_id: `electors-persons-by-sex`.
- **Fowler**: 3 separate data PRs (zero shared seam). Affidavit join = exact-match-only two-pass (raw name + `AltSpelling` fallback); threshold is user-named, not agent-picked. Seizures = store cumulative-as-published, derive deltas at read time, do NOT persist `TOTAL`. TN gender = strip subtotals via `Sl No.isdigit()` predicate inline in writer (no pre-clean tool).
- **Jony**: Zero new URL routes (locked grammar covers all). Seizures = ONE card "Election-period seizures (2019)" mounted on `/t/elections/general-2019` AND scoped to `/<state>/elections/general-2019` (same card, two scopes). Affidavits = "About this MP (2014 declaration)" panel on existing constituency drill + ONE optional national choropleth. TN gender = DATA-ONLY for this cycle (single-state ⇒ no card until ≥3 states have parallel rolls).

### 0.3 User-named decisions (binding; do not re-litigate)

| # | Decision | Value | Source |
|---|---|---|---|
| D1 | TN file vintage | **2021** (pre-AE 2021 final roll, Mar-2021 publication) | User answer 2026-06-14 |
| D2 | Affidavit unmatched-rate threshold | **0%** — any unmatched winner aborts the ingest | User answer 2026-06-14 |
| D3 | Seizures `TOTAL` column | **Derive at read time; do NOT persist** | User answer 2026-06-14 |
| D4 | PR topology | **3 data PRs (A/B/C) + 1 UX PR (D)** | User answer 2026-06-14 |
| D5 | Plan-doc first | **Yes** (this file) | User answer 2026-06-14 |

### 0.4 Hard scope (what is and is NOT in this plan)

**IN SCOPE.** The 4 PR-rows in section 1. Pre-ingest gates per PR. Schema bumps per PR. Source.csv row authorship per PR. Vitest contract tests + pytest unit/integration tests per PR. §13 browser smoke ONLY in PR-D (data-only PRs carry the explicit §13-SKIP receipt in PR body per CLAUDE.md §13).

**OUT OF SCOPE** (deliberately deferred per persona convergence):
- Aggregate-rollup indicator rows derived from affidavit columns ("% of 2014 winners with criminal cases by state"). These mint as separate indicator rows in a FOLLOW-ON PR after PR-B lands; surfaced as a fold-back row in this plan but not executed here.
- Backfill of 2009/2019/2024 LS affidavits, 2014/2024 LS seizures, or other-state electorate-by-sex shards. Each is a follow-on PR after the corresponding shape lands.
- Cleaning up `datasets/ephemeral/` — that tier is gitignored + Tier-B-exempt per validator docs. Writers read inputs in place via injected path.
- New chart primitives in PR-D. Jony's verdict: all surfaces render with the existing closed set + the new `EntityProfilePanel` generic (a 4-to-8-row "About this <entity>" facts panel reusable across MP / AC / party profiles). That primitive's ADR is a fold-back row.

### 0.5 ESCALATE triggers (autonomous execution stops ONLY at these)

- **E1.** PR-B's affidavit join produces ≥1 unmatched row after Pass-2 (`AltSpelling` fallback). Per D2, ABORT and surface the unmatched-rows list for operator review. Do NOT lower the threshold; do NOT smuggle a fuzzy fallback.
- **E2.** PR-A's `period_label` for the per-event CSV requires inventing a vocabulary NOT already in `datasets/elections/{assembly,parliament}/...` per-file CSV column schemas. Max's seam (per-event CSV, own column schema) sidesteps this; if implementation drifts toward the canonical `data/datapoints/*.csv` shape with a `period_label='daily'` column, STOP and re-confirm seam choice with Hans+Max.
- **E3.** PR-C's `check-overlap` returns "PASS (no overlap)" instead of "HIT" for `(electors, persons, ac)`. Expected behaviour per Max is HIT 100% (exact match against `concepts.json` line 438). If CLI returns PASS, that is a CLI bug — STOP and escalate to Max, do NOT mint a new concept.
- **E4.** Any PR triggers a MAJOR schema bump (1.x -> 2.x). All four PRs are designed as MINOR bumps only (additive). If a major bump becomes necessary, that is Level-5 and requires user sign-off per CLAUDE.md §6.
- **E5.** Any §13 browser smoke in PR-D surfaces a regression (new console error, new 404, layout break) on a route NOT introduced by this plan. STOP and triage; do not force-merge.

### 0.6 Hygiene defaults (do not re-dictate)

- Master parking: park `main` on `scratch-master-parking` so PR worktrees can cleanly `gh pr merge` without owning `main` (the cosmetic gh-merge error documented in memory).
- Worktree-per-PR pattern: `../yen-gov-ingest-<row>` slug; same pattern as recent successful PRs (PR-A worktree `../yen-gov-ingest-mcc-seizures-2019`, etc.).
- Worktree `bun install --frozen-lockfile` after `git worktree add` (frontend changes only).
- Schema-version sourcing via `yen_gov.core.schema_registry.schema_version(<file>)`; never hand-type `"1.0"` / `"2.0"`.
- ASCII-only in all committed text (commit messages, plan rows, code comments, log strings).
- Commit messages: describe the change. **No AI co-author / attribution tags.**
- Post-merge: `gh pr merge --squash --delete-branch`, prune `: gone` local branches, remove `.tmp_*` per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md).
- ALL paths in committed artifacts: POSIX, relative, no drive letters.

---

## 1. Status Reckoner

| Row | Title | Status | PR | Effort |
|---|---|---|---|---|
| **A** | ECI MCC seizures 2019 — per-event CSV + schema + source | `[ ] PENDING` | — | M |
| **B** | 2014 LS winner affidavits — extend candidacies.csv (4 cols) | `[ ] PENDING` | — | M |
| **C** | TN electors-by-sex 2021 — long-format facet on `electors` concept | `[x] DONE` (Hans+Max+Fowler unanimous Path B; receipt: [TODO/20260615-row-c-tn-electors-by-sex-handover.md](20260615-row-c-tn-electors-by-sex-handover.md)) | — | S |
| **D** | UX — seizures national+state card + 2014 affidavit MP panel | `[ ] PENDING` | — | M |
| **FB-1** | Fold-back: aggregate-rollup indicator rows from affidavit cols | `[ ] DEFERRED` | — | — |
| **FB-2** | Fold-back: backfill LS-2009/2019/2024 affidavits, 2014/2024 seizures, 35 other states' electors-by-sex | `[ ] DEFERRED` | — | — |
| **FB-3** | Fold-back: `EntityProfilePanel` generic component ADR (justified by ≥4 reuses) | `[ ] DEFERRED` | — | — |

**Dependency lines**: A and C independent (parallel-safe). B independent of A and C (data does not cross). D depends on A merged AND B merged (renders both cards/panels in one UX PR; Jony's verdict was to NOT bundle UX with data per PR but to ship the two UX surfaces together). C does NOT have a UX shipment in this plan (D3 + Jony: data-only until ≥3 states ship).

**Order of execution**: A → B → C → D. A first because Jony cited it as highest citizen-value-per-pixel AND Fowler cited it as clean (zero join machinery). B second because it carries the riskiest contract (silent misattribution potential) so it gets the freshest reviewer attention. C third because it is shape-trivial (one CSV, one facet) and surfaces no UX. D last because it depends on A+B being on `origin/main`.

---

## 2. Row A — ECI MCC seizures 2019 (per-event CSV + schema + source)

### 2.A.1 Scope

Land a new per-event self-contained CSV at `datasets/elections/parliament/election=2019/mcc_seizures.csv` carrying the 10-day campaign-window snapshot of state-level seizures. Strip the publisher's `TOTAL seizure` column at ingest (D3: do not persist; derive at read time). Strip the `(UT)` suffix from state names and resolve to canonical state slug via existing `entities/geo.csv` aliases.

### 2.A.2 Files touched

| File | Op | Notes |
|---|---|---|
| `datasets/elections/parliament/election=2019/mcc_seizures.csv` | **ADD** | New per-event CSV. 360 data rows. Filename pattern parallels the existing `candidacies.csv`/`summary.csv` per-event convention. |
| `datasets/data/_schema/columns.json` | **EDIT (MINOR)** | Add new file-class entry `datasets/elections/parliament/election=YYYY/mcc_seizures.csv` (wildcard pattern) with 11 columns: `state, state_slug, date (ISO YYYY-MM-DD), period_label (literal 'cumulative-mcc-day'), cash_inr_crore, liquor_qty_lakh_litres, liquor_value_inr_crore, drugs_qty_kg, drugs_value_inr_crore, precious_metals_qty_kg, precious_metals_value_inr_crore, other_items_value_inr_crore, source_id`. Bump `x-version` MINOR (additive file-class). Add new `x-changelog` entry. |
| `datasets/schemas/columns.schema.json` | **N/A** | No bump needed (file-class additions are accommodated by the existing meta-schema). Verify before edit. |
| `datasets/data/entities/source.csv` | **APPEND 1 ROW** | New citation: `(producer="Election Commission of India", title="Press Note - Daily Enforcement Seizures during 17th Lok Sabha General Election (MCC)", vintage="2019", url=<ECI press-release page; operator-confirms>)`. `source_id` via `derive_source_id`. |
| `backend/yen_gov/canonical/adapters/eci/mcc_seizures.py` | **ADD** | New adapter module. Reads input from `datasets/ephemeral/2019_eci_seizures.csv` (path injected); strips `TOTAL` column; strips `(UT)` suffix; resolves state slug via `entities/geo.csv`; parses date `29-Mar-19` → `2019-03-29`; emits per-event CSV. |
| `backend/yen_gov/__main__.py` (or wherever CLI commands register) | **EDIT** | Add new CLI subcommand `ingest-eci-mcc-seizures-2019 --input <path> --root .` that invokes the adapter. |
| `backend/tests/canonical/adapters/eci/test_mcc_seizures.py` | **ADD** | Pytest unit + integration tier per Fowler's matrix (section 2.A.5). |
| `frontend/src/contracts/datasets-conform.test.ts` | **N/A unless schema-conform test discovers the new CSV** | The contract test reads `columns.json` `file_classes` and validates every matching CSV on disk. New file-class auto-extends coverage. Confirm with `bun run test datasets-conform` after the schema edit. |
| `TODO/20260614-eci-mcc-seizures-2019-ingest-handover.md` | **ADD** | Per-PR handover-doc per `_TEMPLATE-ingest-handover.md`. Cites the proposal.json + report.json paths for 6 pre-flight concepts (5 + omitted-by-design `other_items`). |
| `TODO/20260614-eci-mcc-seizures-2019-ingest-handover-proposal.json` | **ADD** | Pre-flight proposal JSON for ONE representative concept (per ADR-0046, one proposal per CLI invocation). Subsequent concepts get sibling `-proposal-<n>.json` files. |
| `TODO/20260614-eci-mcc-seizures-2019-ingest-handover-report.json` | **ADD (CLI output)** | Pre-flight report. |

### 2.A.3 Schema bump details

Per CLAUDE.md §11: this is a MINOR bump (purely additive). New `x-changelog` entry on `datasets/data/_schema/columns.json`:

```
{
  "version": "2.1",
  "date": "2026-06-14",
  "summary": "Add file-class for datasets/elections/parliament/election=YYYY/mcc_seizures.csv (per-event CSV; 11 cols; ECI MCC seizure publisher format with TOTAL stripped at ingest per D3)."
}
```

`x-version` becomes `"2.1"` (was `"2.0"`). Sourced via `schema_registry.schema_version("columns.json")` in any test asserting the version.

### 2.A.4 Pre-flight proposal (the FB-1 fold-back, sketched here for receipt)

Even though row A emits raw per-event-CSV rows (no indicator-catalogue mint in this PR), the future rollup indicators DO need pre-flight. Sketch the proposal JSON here so FB-1 has a starting point:

```json
{
  "proposed_id": "elections/mcc-seizure-cash-inr-crore",
  "family": "elections",
  "concept_noun": "MCC-period seizure: cash",
  "concept_unit": "INR_crore",
  "concept_normalisation": "absolute",
  "entity_kinds": ["state", "country"],
  "update_period_days": 1825,
  "justification": "ECI publishes daily enforcement-action cash-seizure totals during the MCC window of each LS general election. Distinct from any existing fiscal / revenue concept because the sampling frame is enforcement teams' caught quantum, not the underlying flow.",
  "source_producer": "Election Commission of India",
  "source_title": "Press Note - Daily Enforcement Seizures during 17th Lok Sabha General Election (MCC)",
  "source_vintage": "2019"
}
```

The 5 facets (cash + liquor-value + liquor-qty + drugs-value + drugs-qty + metals-value + metals-qty + other) each get a sibling proposal in FB-1. Row A itself does NOT mint these.

### 2.A.5 Test tier matrix (Fowler's spec)

| Tier | What | Files |
|---|---|---|
| Unit | row parser; `(UT)` stripper; date parser (`29-Mar-19` → `2019-03-29`); state-slug resolver; `TOTAL`-stripper | `backend/tests/canonical/adapters/eci/test_mcc_seizures.py` |
| Contract (pytest) | Tier-A schema validation on emitted CSV; `pytest -q` covers via existing validator entrypoint | existing `backend/tests/test_validate.py` auto-discovers |
| Contract (vitest) | `frontend/src/contracts/datasets-conform.test.ts` runs across all `file_classes` in `columns.json` — new file-class auto-validates | existing |
| Integration (pytest) | End-to-end ingest with a 3-day × 3-state fixture in `tmp_path` → asserts 9 emitted rows, 11 columns, no `TOTAL`, state slugs lowercase | `backend/tests/canonical/adapters/eci/test_mcc_seizures.py` |
| E2E (Playwright) | **SKIP** — no frontend/ runtime change in this PR |

### 2.A.6 Oracle (the one load-bearing check)

**Bijection on `(state_slug, date)`**: after ingest, `SELECT DISTINCT state_slug, date FROM mcc_seizures` returns exactly 36 × 10 = 360 rows. If fewer, a state name failed to resolve (bug) or a row was dropped. If more, the `TOTAL` row leaked through (bug). Test this in the integration tier with a deliberate "Tamil Nadu" + "Tamil Nadu (UT)" malformed-input fixture — both must resolve to the same `tamil-nadu` slug and the duplicate must be caught.

### 2.A.7 Acceptance gates (5-gate DoD from `docs/how-to/ship-a-pr.md`)

| Gate | Command | Required? |
|---|---|---|
| G1 | `python -m yen_gov validate --root .` | yes |
| G2 | `pytest -q` | yes |
| G3 | `bun run check` (frontend svelte-check) | yes (cheap) |
| G4 | `bun run test` (vitest incl. `datasets-conform`) | yes |
| G5 | §13 browser smoke | **SKIP** — PR body carries the line: `Section 13 skipped: no frontend/ or admin/ runtime change in this PR (data + writer + schema only).` |

### 2.A.8 Pre-ingest gate (mandatory per CLAUDE.md §10)

Run `python -m yen_gov pre-flight-ingest --proposal-file ./TODO/20260614-eci-mcc-seizures-2019-ingest-handover-proposal.json --report ./TODO/20260614-eci-mcc-seizures-2019-ingest-handover-report.json` and cite both paths in §3 of the handover-doc. Expected verdict for `mcc-seizure-cash-inr-crore`: `mint_new` (no existing concept measures election-period enforcement seizures). Exit code MUST be 0 or 1; exit 2 aborts the row per ADR-0046.

Note: this row does NOT mint the catalogue entry (that is FB-1). The pre-flight RUN exists to discharge the §10 anti-pattern and produce the receipt; the actual catalogue insertion lives in the follow-on PR. The report-path citation in the handover-doc is the binding deliverable here.

---

## 3. Row B — 2014 LS winner affidavits (extend `candidacies.csv`)

### 3.B.1 Scope

Extend the per-event candidacies CSV at `datasets/elections/parliament/election=2014/candidacies.csv` with 4 nullable disclosure columns sourced from the user-provided ADR/MyNeta winners file. Two-pass exact-match join: Pass 1 on `(constituency_name, candidate_name, party_short_raw)`; Pass 2 on `(constituency_name, AltSpelling, party_short_raw)`. Per D2: ABORT if ≥1 winner stays unmatched after Pass 2. The new columns are entity-attributes on the candidacy dim, NOT indicator rows (Max's Side A, OWID precedent per indicator-catalogue.md). Aggregate rollups (e.g. "% of winners with criminal cases by state") deferred to FB-1.

### 3.B.2 Files touched

| File | Op | Notes |
|---|---|---|
| `datasets/elections/parliament/election=2014/candidacies.csv` | **EDIT** | Append 4 new columns to header; populate the 542 winner rows (where `result='won'`) by joining the affidavit file; populate `processing_note` for any winner the join hit on Pass 2 (AltSpelling); leave all 4 cols NULL for the 6130 loser rows. Verify `git diff --stat` shows exactly the expected row-edit count (542 rows touched: their existing cells stay, 4 new cells per row populated). NO column deletions. NO row deletions. |
| `datasets/data/_schema/columns.json` | **EDIT (MINOR)** | Append 4 columns to the `datasets/elections/parliament/election=*/candidacies.csv` file-class: `criminal_cases_declared (integer, nullable)`, `total_assets_inr (integer, nullable)`, `total_liabilities_inr (integer, nullable)`, `declared_election_expense_inr (integer, nullable)`. Mirror onto the assembly candidacies file-class (also a wildcard) — the columns ARE applicable to AE candidacies too, even though this PR only populates them on the 2014 LS file. Bump `x-version` MINOR. Add `x-changelog`. |
| `datasets/data/entities/source.csv` | **APPEND 1 ROW** | New citation: `(producer="Association for Democratic Reforms (ADR / MyNeta)", title="Lok Sabha 2014 Winners - Affidavit Analysis (MyNeta)", vintage="2014", url=<operator-confirms ; default https://myneta.info/ls2014/>)`. `source_id` via `derive_source_id`. |
| `backend/yen_gov/canonical/adapters/myneta/lok_sabha_2014_winners.py` | **ADD** | New adapter. Reads `datasets/ephemeral/2014_lok_sabha_affidavits.csv` (path injected); normalises name + constituency + party; two-pass exact-match join against `candidacies.csv WHERE election_year=2014 AND result='won'`; on success, UPSERTs the 4 columns into the candidacies CSV via `pandas.merge` or a direct row-rewrite; on ≥1 unmatched: writes the unmatched list to `datasets/_ops/affidavit-2014-unmatched-2026-06-14.csv` and EXITS with code 2. |
| `backend/yen_gov/__main__.py` | **EDIT** | Add CLI subcommand `enrich-2014-ls-candidacies-with-affidavits --input <path> --root .`. |
| `backend/tests/canonical/adapters/myneta/test_lok_sabha_2014_winners.py` | **ADD** | Pytest unit + integration tier. Unit: name-normaliser (case-insensitive, whitespace-fold, "Dr." stripper, "." stripper), constituency-normaliser, party-short-normaliser, threshold-enforcer (returns False/raises when unmatched > 0). Integration: 7-row affidavit fixture + 10-row candidacies fixture → asserts 5 matched on Pass 1 + 2 matched on Pass 2 → emitted CSV has 4 new cols populated on those 7 rows; same 7-row fixture with one deliberately-unmatchable row → asserts exit code 2 + unmatched-list CSV written. |
| `backend/yen_gov/canonical/adapters/myneta/_normalisers.py` | **ADD** | Pure functions: `normalise_candidate_name`, `normalise_constituency_name`, `normalise_party_short`. Reused by tests. Refactoring vocabulary per Fowler: Extract Function. |
| `TODO/20260614-2014-ls-affidavits-ingest-handover.md` | **ADD** | Per-PR handover-doc. Section 3 cites the pre-flight report path; section 7 captures the FB-1 fold-back open question. |
| `TODO/20260614-2014-ls-affidavits-ingest-handover-proposal.json` | **ADD** | Pre-flight proposal for the FB-1 concept `criminal-cases-declared`. |
| `TODO/20260614-2014-ls-affidavits-ingest-handover-report.json` | **ADD (CLI output)** | Pre-flight report. |

### 3.B.3 Schema bump details

MINOR bump on `columns.json` to `"2.2"` (or whatever the version is post-Row-A; this plan-doc assumes A merges first so B sees `"2.1"` and bumps to `"2.2"`). New changelog:

```
{
  "version": "2.2",
  "date": "2026-06-14",
  "summary": "Add 4 nullable disclosure columns (criminal_cases_declared, total_assets_inr, total_liabilities_inr, declared_election_expense_inr) to candidacies.csv file-classes (both parliament and assembly). Populated on 2014 LS winners via PR-B; NULL elsewhere."
}
```

### 3.B.4 Pre-flight proposal sketch (for FB-1)

```json
{
  "proposed_id": "elections/criminal-cases-declared-cases-affidavit",
  "family": "elections",
  "concept_noun": "Criminal cases declared (candidate affidavit)",
  "concept_unit": "cases",
  "concept_normalisation": "absolute",
  "entity_kinds": ["candidate"],
  "update_period_days": 1825,
  "justification": "Count of criminal cases pending against a candidate, self-declared on the ECI Form 26 affidavit at nomination. Distinct from any other 'criminal' or 'cases' concept because the sampling frame is candidate-affidavit-declaration, not adjudicated conviction; 'cases' unit reflects publisher granularity (count, not severity-weighted).",
  "source_producer": "Association for Democratic Reforms (ADR / MyNeta)",
  "source_title": "Lok Sabha 2014 Winners - Affidavit Analysis (MyNeta)",
  "source_vintage": "2014"
}
```

This row runs the pre-flight to discharge the §10 anti-pattern; the catalogue insertion lives in FB-1. Citation in handover-doc §3 is the binding deliverable.

### 3.B.5 Join machinery contract

**Normalisation rules** (pure, idempotent, unit-tested):
- `normalise_candidate_name(s)`: `s.strip().lower()`. Remove honorifics: `"dr."`, `"dr "`, `"shri "`, `"smt."`, `"mr."`, `"mrs."`. Collapse internal whitespace to single space. Remove all `"."`. Trailing/leading whitespace stripped again.
- `normalise_constituency_name(s)`: `s.strip().lower()`. Remove `"(sc)"`, `"(st)"` suffixes and any parenthesised qualifier. Collapse whitespace. Remove `"."`. Hyphens preserved (e.g. `"yavatmal - washim"` → `"yavatmal-washim"` after collapsing surrounding spaces around `-`).
- `normalise_party_short(s)`: `s.strip().upper()`. The affidavit `Party` column carries verbatim publisher strings; some rows have `"T"` (likely TRS), `"SHS"` (Shiv Sena), etc. The candidacies `party_short_raw` carries the verbatim TCPD label. Use `parties.csv.short` as the join key when both files map to a party_id; fall back to `party_short_raw == affidavit.Party` on raw string match.

**Two-pass algorithm**:
1. Pass 1: build a 3-tuple key `(normalised_constituency, normalised_candidate, normalised_party_short)` on each side. Join.
2. Pass 2 (only over Pass-1 misses): rebuild the candidate-side key using `AltSpelling` instead of `Candidate`. Re-join.
3. Compute `unmatched_count = sum(affidavit rows not matched after Pass 2)`. If `unmatched_count > 0`: write the unmatched list to `datasets/_ops/affidavit-2014-unmatched-<YYYY-MM-DD>.csv` (PII-light: just the 11 columns of the affidavit row + a `failure_reason` column), print the path, exit code 2. Per D2.
4. On unmatched_count == 0: UPSERT the 4 new columns into `candidacies.csv` (only on the 542 winner rows; loser rows stay NULL).
5. For rows matched on Pass 2 (AltSpelling fallback), set `processing_level='major'` and append `processing_note="affidavit join used AltSpelling fallback"` (preserve any existing processing_note via `";"` concat).

**Refactoring discipline (Fowler)**: Introduce Parameter Object for the 3-tuple key; Extract Function for each normaliser. Do NOT add a third pass. Do NOT add fuzzy matching. Do NOT smuggle a confidence threshold.

### 3.B.6 Test tier matrix

| Tier | What | Files |
|---|---|---|
| Unit | name-normaliser; constituency-normaliser; party-short-normaliser; threshold-enforcer (returns False / raises on unmatched > 0) | `backend/tests/canonical/adapters/myneta/test_lok_sabha_2014_winners.py` |
| Contract (pytest) | Tier-A schema on emitted candidacies.csv (sex enum, etc.); FK-tier (every affidavit-source row's join-key resolves to a real candidacy row) | existing `test_validate.py` auto-discovers post-schema-bump |
| Contract (vitest) | `frontend/src/contracts/datasets-conform.test.ts` re-validates the candidacies CSV against the bumped schema | existing |
| Integration (pytest) | 7-row affidavit fixture + 10-row candidacies fixture → assert 7 join successes, 4 cols populated, NULL on loser rows. Second fixture with 1 unmatchable row → assert exit code 2 + unmatched CSV written. | `backend/tests/canonical/adapters/myneta/test_lok_sabha_2014_winners.py` |
| E2E (Playwright) | **SKIP** — no frontend/ runtime change in this PR |

### 3.B.7 Oracle

**FK + completeness double-bind**: after ingest, on the candidacies CSV, the COUNT of rows where `election_year=2014 AND result='won' AND criminal_cases_declared IS NOT NULL` MUST equal 542 exactly. The COUNT where `election_year=2014 AND result='won' AND criminal_cases_declared IS NULL` MUST equal 0 (the missing 1 winner of 543 is a DATA gap in the source, not a join failure; this is the published coverage). Test in integration tier with a deliberately-tampered fixture (affidavit row dropped) and assert exit code 2.

Secondary oracle: spot-check 3 specific rows by hand. E.g. `Adilabad` 2014 winner is `Godam Nagesh` (T party in the affidavit, mapped to TRS); confirm post-ingest `total_assets_inr = 10378857`, `criminal_cases_declared = 0`. Bake the spot-check into the integration test.

### 3.B.8 Acceptance gates

Same 5-gate DoD as Row A. G5 §13 SKIP. PR body must carry the citizen-correctness contract receipt: "Affidavit join: 542/542 winners matched (exact match, 2-pass, AltSpelling fallback); unmatched_count = 0 per D2."

---

## 4. Row C — TN electors-by-sex 2021 (long-format facet on `electors` concept)

> **RESOLUTION (2026-06-15)**: This section was `BLOCKED-NEEDS-SIGNOFF`
> at the file-class shape boundary (§4.C.2 originally placed the new
> CSV under `datapoints/geo/*.csv` whose FK target is
> `entities/geo.csv`, but ACs are NOT geo entities — they are
> ECI-issued electoral units already keyed at `entities/electoral.csv`).
> Resolved via §10 STOP-AND-SURFACE persona debate (Hans + Max + Fowler
> via `runSubagent`); all three personas converged UNANIMOUSLY on
> **Path B** — introduce a new sibling file-class
> `datasets/data/datapoints/electoral_geo/*.csv` with FK target
> `entities/electoral.csv`, mirroring the LGD-vs-ECI issuing-authority
> split already present at the entities tier through to the datapoints
> tier. The shipped file path is
> `datasets/data/datapoints/electoral_geo/electors-persons-by-sex.csv`
> (NOT `datapoints/geo/...` as originally framed). Full convergence
> transcript + ship receipts in
> [TODO/20260615-row-c-tn-electors-by-sex-handover.md](20260615-row-c-tn-electors-by-sex-handover.md).
> The PR ships data-only per §5.D + D4 Jony verdict (no frontend
> allowlist or card change in this PR; deferred until ≥3 states ship
> the indicator).

### 4.C.1 Scope

Land a new long-format CSV at `datasets/data/datapoints/geo/electors-persons-by-sex.csv` carrying 702 rows (234 TN ACs × 3 sex values). Filter out the 39 publisher subtotal + grand-total rows on ingest via `Sl No.isdigit()` predicate. This is a FACET extension on the existing `electors` concept (NOT a new concept_id) per Max + ADR-0044 identity test. Wire the frontend indicator-allowlist entry as data-only (no card). Vintage: 2021 per D1.

### 4.C.2 Files touched

> **PATH-B UPDATE (2026-06-15)**: The shipped file path is
> `datasets/data/datapoints/electoral_geo/electors-persons-by-sex.csv`,
> NOT `datapoints/geo/...`. The frontend allowlist row was DEFERRED
> per D4 Jony verdict (data-only PR until ≥3 states ship). The schema
> WAS bumped `2.3 → 2.4` (MINOR additive) to register the new
> `datapoints/electoral_geo/*.csv` file-class. See the resolution
> banner above and the handover-doc for the as-shipped file list.

| File | Op | Notes |
|---|---|---|
| `datasets/data/datapoints/geo/electors-persons-by-sex.csv` | **ADD** | New long-format CSV. Columns: `entity_id, time, value, sex, source_id`. Row count: 234 × 3 = 702 (TN AC × {male, female, third_gender}). |
| `datasets/data/variables.csv` | **APPEND 1 ROW** | New variable row: `indicator_id=electors-persons-by-sex, name="Electors on roll, by sex", concept_id=electors, unit=persons, derivation="facet(sex)", topic=elections, source_id=<TN-CEO-2021-roll>, update_period_days=1825, time_min=2021, time_max=2021, entity_kinds=ac` (column names follow whatever the existing variables.csv shape is — confirm at execution time). |
| `datasets/data/entities/source.csv` | **APPEND 1 ROW** | New citation: `(producer="Office of the Chief Electoral Officer, Tamil Nadu", title="Tamil Nadu Electoral Roll - AC-wise Electors by Sex", vintage="2021", url=<operator-confirms ; default https://www.elections.tn.gov.in/>)`. `source_id` via `derive_source_id`. |
| `frontend/src/lib/canonical/indicator-allowlist.ts` | **APPEND 1 DESCRIPTOR** | `{ indicator_id: "electors-persons-by-sex", csv_path: "data/datapoints/geo/electors-persons-by-sex.csv", unit: "persons", concept_id: "electors", facet_axis: "sex", facet_values: ["male", "female", "third_gender"], default_facet: "female", entity_kinds: ["ac"] }`. Per user-memory "Per-indicator frontend allowlist seam for canonical reader-switches" doctrine. |
| `backend/yen_gov/canonical/adapters/tn_ceo/electors_by_sex.py` | **ADD** | New adapter. Reads `datasets/ephemeral/tn_acwise_gendercount.csv`; filters via `Sl No.isdigit()` predicate (234 atomic rows survive of 273 input rows); resolves AC No → `entity_id` via `entities/electoral.csv WHERE state='tamil-nadu' AND delim_year=2008 AND eci_no=<AC No>`; emits 3 rows per AC (one per sex value) in long format. |
| `backend/yen_gov/__main__.py` | **EDIT** | Add CLI subcommand `ingest-tn-electors-by-sex-2021 --input <path> --root .`. |
| `backend/tests/canonical/adapters/tn_ceo/test_electors_by_sex.py` | **ADD** | Pytest unit + integration tier. Unit: subtotal-stripper predicate (`Sl No.isdigit()` returns False for `"Total"` / `"Grand Total"`; True for `"1"`, `"234"`); entity_id resolver. Integration: 5-row fixture (3 AC rows + 1 district subtotal + 1 grand total) → assert exactly 3 × 3 = 9 emitted rows AND sum of survivor `value`s does NOT equal grand-total row's `value` (catches off-by-one). |
| `TODO/20260614-tn-electors-by-sex-2021-ingest-handover.md` | **ADD** | Per-PR handover-doc. Section 3 cites pre-flight report with verdict `add_facet`. |
| `TODO/20260614-tn-electors-by-sex-2021-ingest-handover-proposal.json` | **ADD** | Pre-flight proposal for the facet add. |
| `TODO/20260614-tn-electors-by-sex-2021-ingest-handover-report.json` | **ADD (CLI output)** | Pre-flight report. |

### 4.C.3 Schema bump details

NO schema bump needed if `datasets/data/datapoints/geo/*.csv` is already covered by a wildcard file-class in `columns.json`. The variables.csv row addition does NOT bump schema (it's a data-row addition, not a column addition). The frontend allowlist file is a TS file, not a JSON schema. **Confirm at execution time** that the existing `datapoints/geo/*.csv` file-class already supports the 5 columns `(entity_id, time, value, sex, source_id)` — if not, a MINOR bump is required to add the `sex` facet column to the file-class.

### 4.C.4 Pre-flight proposal

```json
{
  "proposed_id": "elections/electors-persons-by-sex",
  "family": "elections",
  "concept_noun": "Electors",
  "concept_unit": "persons",
  "concept_normalisation": "absolute",
  "entity_kinds": ["ac"],
  "update_period_days": 1825,
  "justification": "Existing `electors` concept (persons, ac) covers total enrolled voters per AC. This ingest adds the publisher-provided sex breakdown (male / female / third_gender) as a facet on the existing concept per ADR-0044 (same noun + unit + grain = facet, not new mint). TN CEO publishes this disaggregation before each AE cycle.",
  "source_producer": "Office of the Chief Electoral Officer, Tamil Nadu",
  "source_title": "Tamil Nadu Electoral Roll - AC-wise Electors by Sex",
  "source_vintage": "2021"
}
```

Expected verdict: **`add_facet`** (HIT >= 0.70 on the `(noun, unit, normalisation, entity_kind)` tuple against existing `electors` concept). If verdict is `mint_new`, trip E3 — that is a CLI bug per Max's verdict.

### 4.C.5 Test tier matrix

| Tier | What | Files |
|---|---|---|
| Unit | `Sl No.isdigit()` predicate; entity_id resolver (eci_no → `IN-AC-2008-tamil-nadu-eciN`) | `backend/tests/canonical/adapters/tn_ceo/test_electors_by_sex.py` |
| Contract (pytest) | Tier-A schema on emitted CSV; FK from `entity_id` resolves into `electoral.csv`; FK from `source_id` resolves into `source.csv` | existing `test_validate.py` auto-discovers |
| Contract (vitest) | `datasets-conform.test.ts` auto-validates the new CSV against the file-class schema | existing |
| Integration (pytest) | 5-row fixture (3 AC + 1 district subtotal + 1 grand total) → assert 9 emitted rows (3 × 3 sex) AND sum_of_survivors != grand_total | `backend/tests/canonical/adapters/tn_ceo/test_electors_by_sex.py` |
| E2E (Playwright) | **SKIP** — no frontend/ UI surface in this PR (allowlist entry is data-only) |

### 4.C.6 Oracle

**Cardinality bijection**: post-ingest, `SELECT entity_id, COUNT(*) FROM electors-persons-by-sex GROUP BY entity_id HAVING COUNT(*) != 3` MUST return 0 rows. Every TN AC has exactly 3 rows (one per sex). And `SELECT COUNT(DISTINCT entity_id) FROM electors-persons-by-sex` MUST equal 234 (TN's post-2008-delim AC count). Bake into integration test.

### 4.C.7 Acceptance gates

Same 5-gate DoD. G5 §13 SKIP. PR body must carry the receipt: "TN electors-by-sex: 702 rows (234 ACs × 3 sex values), data-only ingest, no citizen card per Jony D4."

---

## 5. Row D — UX shipment (seizures card + 2014 affidavit MP panel)

### 5.D.1 Scope (deps: A merged + B merged on `origin/main`)

Two citizen-facing UX surfaces:
1. **Seizures card** — ONE `<Card>` titled "Election-period seizures (2019)" mounted on `/t/elections/general-2019` (NationalElection.svelte) and on `/<state>/elections/general-2019` (StateElection.svelte). Default render: state choropleth coloured by total-seizure-value-INR-crore over the 10-day window, with a 10-day stacked sparkline below. Category picker INSIDE the card (per `topic-card-uniqueness` contract): Total ₹ (default) / Cash / Liquor / Drugs / Precious metals / Freebies. Unit toggle visible when liquor/drugs/metals is picked.
2. **MP affidavit panel** — ONE panel titled "About this MP (2014 declaration)" mounted on `Constituency.svelte` at route `/<state>/elections/general-2014/<pc-slug>`. Renders 5 rows: Education, Declared assets, Liabilities, Criminal cases, Sex, Election expense. Plus 1-line provenance footer.

Per Jony's verdict: TN gender gets NO card (single-state, defer until ≥3 states).

### 5.D.2 Files touched

| File | Op | Notes |
|---|---|---|
| `frontend/src/lib/elections/ElectionSeizuresCard.svelte` | **ADD** | New component. Uses existing `IndicatorChoropleth` primitive in choropleth mode + a sparkline (reuse existing or extend `IndicatorSmallMultiples`). Reads seizures CSV via DuckDB-WASM `read_csv(columns={...}, header=true)` per the existing canonical-read pattern. Category picker = standard facet-picker chrome (same as `/t/agriculture` cattle card). |
| `frontend/src/routes/NationalElection.svelte` | **EDIT** | Add `<ElectionSeizuresCard event_id="general-2019" />` slot. Guard: render only when event_id matches `general-2019` (or any future event with seizures data — read from a static manifest or the canonical store). |
| `frontend/src/routes/StateElection.svelte` | **EDIT** | Add `<ElectionSeizuresCard event_id="general-2019" state_slug={current_slug} />` slot. Same guard. |
| `frontend/src/lib/parties/EntityProfilePanel.svelte` | **ADD** | New generic component per FB-3 spec (Jony's "≥4 reuses earns the abstraction" rule). 4-to-8-row "About this <entity>" facts panel + provenance footer + amber-banner-when-self-declared option. Used by the MP panel here; future use cases (party header, AC header, candidate detail) reuse it. |
| `frontend/src/routes/Constituency.svelte` | **EDIT** | When `state` + `event_id=general-2014` + `pc_slug` and winner rows have non-NULL affidavit cols, render `<EntityProfilePanel entity_kind="mp" title="About this MP (2014 declaration)" rows={...} provenance="Self-declared in Form 26 affidavit at nomination, 2014. Source: ECI / MyNeta." amber_banner="Self-declared at nomination, not adjudicated." />`. |
| `frontend/src/lib/elections/ElectionSeizuresCard.test.ts` | **ADD** | Vitest projection test (no DuckDB-WASM end-to-end; mock the query layer or use a small fixture CSV). Asserts category-picker swaps the rendered measure; sparkline renders 10 days; map fill respects unit toggle. |
| `frontend/src/lib/parties/EntityProfilePanel.test.ts` | **ADD** | Vitest unit test for the generic component. Asserts row rendering, provenance footer, amber-banner toggle. |
| `frontend/src/contracts/topic-card-uniqueness.test.ts` | **N/A** | Already passes (one card for seizures, picker inside). Re-verify with the existing test. |
| `frontend/e2e/general-2019-seizures.spec.ts` | **ADD** | Playwright smoke covering `/t/elections/general-2019` and `/maharashtra/elections/general-2019`. Asserts the card renders, picker swaps the measure, hover-tooltip shows the right state. |
| `frontend/e2e/general-2014-mp-panel.spec.ts` | **ADD** | Playwright smoke covering `/maharashtra/elections/general-2014/<one-pc-slug>` (pick a PC where the affidavit join succeeded). Asserts the panel renders, provenance footer is visible, amber banner shows. |
| `TODO/20260614-ux-seizures-and-mp-panel-handover.md` | **ADD** | Per-PR handover-doc with §13 smoke transcript receipt. |

### 5.D.3 Schema / contract impact

NONE. Pure frontend. Data contracts established in Row A and Row B are stable; this row consumes them. `topic-card-uniqueness.test.ts` continues to enforce one-card-per-measure.

### 5.D.4 Test tier matrix

| Tier | What |
|---|---|
| Unit | `ElectionSeizuresCard` data-projection (CSV → category-faceted map fill); `EntityProfilePanel` row rendering |
| Contract | `topic-card-uniqueness.test.ts` re-runs (already in suite); `datasets-conform.test.ts` re-runs (already in suite) |
| Integration | Vitest covers projection layer; no separate Tier-3 needed |
| E2E (Playwright) | TWO new specs: seizures (national + state route) and MP panel (constituency route) |

### 5.D.5 Oracle

**Citizen-question pass**: at the end of §13 browser smoke, navigate to `/maharashtra/elections/general-2019` and visually confirm:
- Card title: "Election-period seizures (2019)"
- A choropleth fills with non-zero values for at least 30 of 36 states (per the input file)
- The category picker has exactly 6 options: Total / Cash / Liquor / Drugs / Precious metals / Freebies
- Tapping a state navigates somewhere sensible (no 404)
- The MP panel on `/maharashtra/elections/general-2014/<pc-slug>` shows the 6 rows + provenance footer + amber banner.

Receipt this in the handover-doc §3 with the §13 transcript per CLAUDE.md §13.

### 5.D.6 Acceptance gates

| Gate | Required |
|---|---|
| G1 | yes |
| G2 | yes |
| G3 | yes |
| G4 | yes |
| G5 (§13 browser smoke) | **YES — mandatory.** This is the only row in the plan where §13 is in scope. Transcript in PR body. |

Per CLAUDE.md §13: agent uses integrated browser tools (`open_browser_page`, `read_page`, `screenshot_page`) to confirm the change rendered, no new console errors, no new 404s. Build-clean is necessary but NOT sufficient.

---

## 6. Fold-back rows (deferred; tracked for closure)

### 6.FB-1 Aggregate-rollup indicator rows from affidavit columns

After Row B lands, the citizen-facing aggregate questions ("% of LS-2014 winners with criminal cases by state", "median declared assets of winners by party") become tractable as derived indicator rows under `datasets/data/datapoints/electoral/`. Each is a separate `mint_new` per the pre-flight sketches in §2.A.4 and §3.B.4. Hans + Max own the framing (denominator-visibility, "% of winners" vs "% of contestants", base-year/methodology-break captioning). FB-1 is a follow-on PR (or PR sequence — one per aggregate concept) NOT executed in this plan.

### 6.FB-2 Backfill (other years; other states)

LS-2009/2019/2024 winner affidavits, LS-2014/2024 seizures, 35 other states' AC-wise electors-by-sex. Each becomes its own per-source ingest PR following the same template as Rows A/B/C. Once ≥3 states ship electors-by-sex, the TN-only data-only-ingest from Row C earns its citizen card (Jony's threshold).

### 6.FB-3 `EntityProfilePanel` generic component ADR

The component is INTRODUCED in Row D (one consumer). The ADR is written when the SECOND consumer lands (typically the party header on `/parties/<slug>` widening). Jony's "≥4 reuses earns the abstraction" rule means the ADR justifies itself once 4 use-cases exist. Until then, the component lives as a Svelte file with a JSDoc header naming its consumers.

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5 / section 0.5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

---

## References

- [CLAUDE.md](../CLAUDE.md) — §0a authority table, §6 correction levels, §10 anti-patterns, §11 schema versioning, §12 provenance, §13 UI verification
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) — the 8-step ritual every persona runs
- [docs/concepts/indicator-naming.md](../docs/concepts/indicator-naming.md) — ADR-0044 grain-over-entity
- [docs/architecture/data/indicator-catalogue.md](../docs/architecture/data/indicator-catalogue.md) — ADR-0045 grapher catalogue split
- [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md) — citation-ledger v3.1, 5-col, `derive_source_id`
- [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) — one-card-per-measure, closed renderer set
- [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) — ADR-0037 / 0052 / 0053 (URL grammar locked)
- [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md) — Tier-A / Tier-B separation
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) — 5-gate DoD, post-merge cleanup
- [TODO/_TEMPLATE-ingest-handover.md](_TEMPLATE-ingest-handover.md) — per-PR handover-doc template

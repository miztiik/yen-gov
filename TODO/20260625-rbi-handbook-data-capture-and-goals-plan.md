# RBI Handbook Data Capture + Goals Activation Plan (pending items 6-12)

**Last Updated**: 2026-06-25
**Level**: 3 (multi-workstream: ingest wiring + data capture + catalogue + goals + frontend; row R8 can escalate to Level-5 data-shape - see ESCALATE)
**Authority (CLAUDE.md section 0a)**: data-shape = Hans + Max; ingest contract = Gregor; engineering craft = Fowler; UX = Jony + Citizen; goals framing = Hans.

> This is an AUTHORED plan, not yet implemented. Add it to context and say "implement R<n>" to run a row. It continues the RBI Handbook of Statistics on Indian States work whose tooling already shipped (see "Already shipped" below). Each row is a small, reversible PR.

---

## Section 0 - Operating contract

### Why this plan exists

The RBI Handbook ingest *pipeline and tooling* are built, tested, and on `main`. What remains is the *data itself*, the goal-overlay activation, the frontend, and multi-year capture. This plan covers pending items 6-12 from the 2026-06-24 status review.

### Already shipped (context - do NOT redo)

- Backend adapter [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) (registry / parser / resolver / ingest) + CLI `ingest-rbi-hbs` (PR #1102).
- 5 health/demographic indicator specs: total fertility rate, crude birth rate, crude death rate, infant mortality rate, life expectancy at birth.
- SDG goal overlay scaffolding: [datasets/data/frameworks.csv](../datasets/data/frameworks.csv) + [datasets/data/goals.csv](../datasets/data/goals.csv) + [datasets/data/goal_indicators.csv](../datasets/data/goal_indicators.csv) + `seed-goals` CLI; SDG-3 subtree seeded, `goal_indicators.csv` header-only (no mappings yet).
- Operator staging tooling: [tools/rbi_handbook_stage.py](../tools/rbi_handbook_stage.py) (single-table) + [tools/rbi_handbook_download.user.js](../tools/rbi_handbook_download.user.js) (Tampermonkey bulk grabber, v3.1.0) (PRs #1222/#1223/#1224). The userscript grabs every table on a loaded edition and saves `<year>_t<NNN>_<rbi-name>.xlsx`.

### Hard-coded scope (in-scope rows)

Rows R6-R12 in the Status Reckoner. Nothing else.

### Out of scope (do NOT smuggle in)

- A production / CI network fetcher. The userscript runs in the operator's own trusted browser; the ingest reads local files only (Holy Laws #1/#2; ingest doctrine D1).
- Re-architecting the canonical store or any schema change beyond additive catalogue rows.
- Auto-solving the RBI F5 CAPTCHA. The userscript sidesteps it via the operator's already-trusted session; never bypass an anti-bot control.
- Ingesting all 182 tables in one shot. Capture is bulk (keep everything locally), but ingest is per-decided-table (Row R8).
- Minting any new `indicator_id` without the pre-flight gate + Hans + Max sign-off (Row R8 ESCALATE).

### ESCALATE triggers (stop and ask)

- Any new `indicator_id` or `concept_id`: run `python -m yen_gov pre-flight-ingest` (ADR-0046), cite the report, get Hans + Max sign-off. No mint without a green report (Row R8).
- Any schema bump beyond additive catalogue rows: Level-5, Hans + Max.
- A goal framework whose authority class is unclear (ICRIER / CHIPS are not intergovernmental resolutions like the SDGs): Hans fixes the framing before any rows land (Row R10).
- A topic-page card-count or per-facet fanout question on the frontend: Jony decides; the schema-is-the-design-system "one card per measure" rule is binding (Row R11).

### Authority map (per CLAUDE.md section 0a)

| Row | Decision class | Authority |
| :-: | --- | --- |
| R6 | Ingest contract / resolver matching | Fowler + Gregor |
| R7 | Operator capture + run | operator (no design call) |
| R8 | Which tables, indicator/concept identity | Hans + Max |
| R9 | Goal-to-indicator mapping rows | Hans |
| R10 | New goal frameworks (ICRIER/CHIPS) | Hans |
| R11 | Goal-summary + indicator UX | Jony + Citizen |
| R12 | Multi-year capture | operator |

---

## Section 1 - Status Reckoner

Rows are PRs (or operator runs). Status starts `[ ] PENDING`, flips to `[x] DONE` with the merged PR number or a capture receipt.

| Row | Title | Status | Depends-on | Authority | Effort | Risk |
| :-: | --- | :-: | :-: | :-: | :-: | :-: |
| R6 | Resolve staged files by RBI caption slug | [ ] PENDING | none | Fowler + Gregor | S | Low |
| R7 | Capture + ingest the staged 2025 tables | [ ] PENDING | R6 + downloads | operator | M | Low |
| R8 | Decide + spec which of the 182 tables to ingest | [ ] PENDING | none (parallel) | Hans + Max | L | Med |
| R9 | Link SDG-3 goals to the landed indicators | [ ] PENDING | R7 | Hans | S | Low |
| R10 | Add ICRIER + CHIPS goal frameworks | [ ] PENDING | R8, R9 | Hans | M | Med |
| R11 | Frontend goal-summary + new-indicator views | [ ] PENDING | R7, R9 | Jony + Citizen | L | Med |
| R12 | Older-edition (multi-year) capture | [ ] PENDING | R6 | operator | M | Low |

Dependency sketch: `R6 -> R7 -> R9 -> {R10, R11}`; `R8` runs in parallel and feeds R7/R10; `R12` needs only R6.

---

## Section 2 - Rows

### R6 - Resolve staged files by RBI caption slug

**Problem.** The userscript saves `<year>_t<NNN>_<rbi-name>.xlsx` (e.g. `2025_t002_state-wise-birth-rate.xlsx`), but `HbsTableSpec.staging_filename` in [registry.py](../backend/yen_gov/canonical/adapters/rbi_handbook/registry.py) is the bare `table-birth-rate.xlsx`. The ingest will not find the prefixed files.

**Do.** Add an `rbi_caption_slug` field to `HbsTableSpec` (the stable RBI caption, e.g. `state-wise-birth-rate`). In [ingest.py](../backend/yen_gov/canonical/adapters/rbi_handbook/ingest.py), resolve each spec's workbook by globbing the staging dir for a file whose name ends with `_<rbi_caption_slug>.xlsx` (case-insensitive); keep the exact `staging_filename` match as a fallback so the single-table stager still works. Fail loud (`FileNotFoundError`) when zero or more-than-one match.

**Acceptance.**
- New unit tests with prefixed fixtures (`2025_t002_state-wise-birth-rate.xlsx`) resolve to the right spec; ambiguous/missing cases raise.
- Existing `test_canonical_rbi_handbook.py` still green (bare-name path preserved).
- No schema change; `pytest -q` green.

**Notes.** This is the highest-leverage unblocker; it makes R7 a one-command ingest. Keep the slug equal to `slugify(rbi_caption)` so it matches the userscript's own slug rule exactly.

### R7 - Capture + ingest the staged 2025 tables

**Do (operator).**
1. Run the userscript on the 2025 RBI Handbook edition; download the tables.
2. Move `Downloads/rbi/handbook-states/2025/` into `.runtime/rbi/handbook-states/2025/` (the one-liner reads the year from each filename).
3. `python -m yen_gov ingest-rbi-hbs --root . --staging-dir .runtime/rbi/handbook-states/2025`
4. `python -m yen_gov validate --root .`

**Acceptance.**
- Datapoint CSVs exist at `datasets/data/datapoints/geo/<indicator_id>.csv` for the 5 health indicators.
- Every new `source_id` FK closes to `datasets/data/entities/source.csv`; validator passes.
- Row counts + year coverage per indicator reported in the PR/handover.

**Notes.** `.runtime/` is gitignored - only the emitted `datasets/**` CSVs are committed. The parser fails loud on layout drift; fix the spec's sheet/header/period anchors on the real file if needed.

### R8 - Decide + spec which of the 182 tables to ingest

**Do.** Enumerate the 182 captured tables. For each candidate beyond the 5 health specs, decide keep / defer with Hans + Max. For each KEEP, author a spec ONLY after the pre-flight gate passes.

**Mandatory gate per new indicator (no exceptions).**
- `python -m yen_gov pre-flight-ingest --proposal-file ./proposal.json --report ./report.json` (ADR-0046); cite both paths.
- Verdict `mint_new` requires a `concepts.json` row `(noun, unit_canonical, normalisation, entity_kinds)` + a `meta.justification`.
- `indicator_id` = `<measure>-<unit>-<facet>` kebab, NO grain prefix (grain lives on `entity_kind`).
- `source_id` via `derive_source_id`; `update_period_days` declared.

**Acceptance.**
- A decided keep/defer table for all 182 (a short markdown matrix in this plan or a sibling handover).
- Specs added for the keepers; each cites a green pre-flight report.

**Notes.** Candidate families worth an early look: fiscal (GFD, revenue deficit, outstanding liabilities), SDP/GSDP, the SDG-score table (Table 106). Many will be `defer` - that is fine; the point is an explicit, cited decision, not a blanket sweep.

### R9 - Link SDG-3 goals to the landed indicators

**Do.** Once R7 lands the health indicator_ids, populate [datasets/data/goal_indicators.csv](../datasets/data/goal_indicators.csv) with FK-guarded rows mapping SDG-3 targets (e.g. under-5 mortality, neonatal mortality, MMR) to the matching `indicator_id`s. Use `seed-goals` if it owns the write path.

**Acceptance.**
- Every `goal_indicators` row FKs to both `goals.csv` and `variables.csv`; validator passes.
- The mapping is honest: only link an SDG target to an indicator that genuinely measures it (Hans rule - do not force-fit).

### R10 - Add ICRIER + CHIPS goal frameworks

**Do.** Hans fixes the `authority_class` for ICRIER and CHIPS (these are think-tank / programme frameworks, NOT intergovernmental resolutions like the SDGs - the field must say so honestly). Add `frameworks.csv` rows + the goal subtrees in `goals.csv`; add `goal_indicators` mappings only where landed data supports them.

**Acceptance.**
- Frameworks + goals validate; `authority_class` distinguishes them from the SDG row.
- No unmapped goal claims a data link it does not have.

### R11 - Frontend goal-summary + new-indicator views

**Do (Jony + Citizen).** Design and ship the citizen view that answers "show me SDG / ICRIER / CHIPS goals" - a goal-summary surface that reads the framework -> goals -> goal_indicators -> datapoints chain, plus surfacing the new health indicators on the relevant topic/state pages. One card per measure (schema-is-the-design-system); the facet picker lives inside the card.

**Acceptance.**
- Routes render with real data; browser-verified per CLAUDE.md section 13 (no new console errors / 404s).
- No per-facet card fanout; topic-card-uniqueness contract stays green.

**Notes.** Frontend was explicitly deferred until backend data lands; this row starts only after R7 (and ideally R9).

### R12 - Older-edition (multi-year) capture

**Do (operator).** For each older edition (2024 down to 2016; 2016 has ~125 tables), load that edition's page, run the userscript (it auto-detects the year and names files accordingly), move into `.runtime/rbi/handbook-states/<year>/`, and ingest. R6's caption-slug matching is what makes this safe across editions (table numbers drift; captions do not).

**Acceptance.**
- At least one older edition captured + ingested, producing a genuine multi-year series for the 5 health indicators.
- Cross-year continuity sanity-checked (no methodology-break surprises silently dropped).

---

## Section 3 - Execution notes

- Per CLAUDE.md git hygiene: one row = one small named-branch PR, staged paths only, gates green at merge.
- Backend rows (R6, R8) ship with tests at the appropriate tier; no mocks (Holy Law #7).
- Data rows (R7, R9, R12) carry `source_id` provenance on every observation row (Holy Law #9).
- Frontend row (R11) is browser-verified (section 13) and respects the no-implementation-disclosure copy rules.
- When a row closes, flip its Status Reckoner cell to `[x] DONE` with the PR number and distil durable findings into the right `docs/` home (agent-only lessons -> `/memories/`).

# D-DOC3 sub-plan - retire the ADR tier (keep the receipts)

**Last Updated**: 2026-06-04
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk D-DOC3
**Status**: IN-FLIGHT (spawned 2026-06-04)
**Authority**: Hans (data-shape doc routing for catalogue/provenance ADRs) / Gregor (contract + integration doc routing for canonical-store, schema, elections ADRs) / Jony (UX doc routing for nav, url, map ADRs) / Andre (yenask doc routing) per CLAUDE.md section 0a + parent plan section 0a authority matrix.

---

## Why this exists

Parent chunk D-DOC3 reads as one row in the parent Execution Ledger (section 22.5) but expands into a large structural docs migration: the `docs/architecture/decisions/` tier retires per section 9 (Hans-finalised 2026-06-03), with each still-live ADR's content folding into its subsystem or concept doc as two mandatory sections (`Design rationale` + `Rejected alternatives`), each superseded/rejected ADR moving to `docs/archive/decisions/`, and a redirect index minting at `docs/reference/decision-index.md` that pins every `ADR-NNNN` to its new home anchor.

Actual disk inventory (verified 2026-06-04 against `docs/architecture/decisions/0*.md`, NOT the stale README that stops at 0047 per section 9): **44 ADR files**, of which **37 are LIVE** (body still binding, fold into subsystem/concept doc) and **7 are FULL-SUPERSEDED-OR-REJECTED** (move to `docs/archive/decisions/`, fold trace into successor's `Rejected alternatives`). The section 9 list "~20 on disk (0003, 0021, 0030, 0031, 0033, 0035-0037, 0040-0050)" undercounts the live set by ~17 (missing 0015, 0016-eci-stats, 0017-eci-current-year, 0018, 0019, 0020, 0022, 0023, 0025-0028, 0034, 0039, 0051, 0052); this sub-plan honours the filesystem, not the stale enumeration (CLAUDE.md section 5 "agent memory is derived, not authoritative").

Additional cost (the load-bearing one per section 9): cross-reference rewrite. CLAUDE.md alone carries **~10 direct `ADR-NNNN` links** (0032 x2, 0034 x2, 0041 x2, 0044 x2, 0045 x2, 0046 x1, 0047 x1) plus a count of mentions in subsystem docs / agent files. Per section 22.6 the migration acceptance gate is `grep-receipts-eq`: total `## Rejected alternatives` (or `## Alternatives considered`) block headers across all `docs/**/*.md` MUST stay equal to the baselines recorded in D-DOC3.2 (strict-h2=33, broader-h2-h3=38; both load-bearing) at every intermediate state and at plan close. The original spawn body asserted 36; that was a memory-counted guess and is corrected to filesystem truth in D-DOC3.2 per `/memories/lessons.md` filesystem-truth doctrine.

Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first) and parent plan section 24.5, the right shape is a thin parent row + this sub-plan. U1, B1, B2a, B2b each followed this shape.

---

## Scope

### In scope (this sub-plan)

1. New `docs/reference/decision-index.md` mapping every `ADR-NNNN -> <doc#anchor>` (numbers never reused; section 9 mandate).
2. Each of the 37 live ADRs folded into ONE subsystem doc or concept doc as two sections: `## Design rationale` (Context + Decision + Consequences, condensed prose) and `## Rejected alternatives` (verbatim from the ADR, append-only). Section order: existing doc head -> Design rationale -> Rejected alternatives (the receipt sits at the bottom, append-only as section 9 mandates).
3. Each of the 7 fully-superseded/rejected ADRs MOVED (via `git mv`) to `docs/archive/decisions/` with the body preserved verbatim, and a one-line cross-link added to the survivor doc's `Rejected alternatives` section ("see also archived `ADR-NNNN <slug>` for the rejected approach").
4. CLAUDE.md cross-reference rewrite: every `ADR-NNNN` link rewrites to the new `decision-index.md#NNNN-<slug>` anchor (or directly to the target subsystem/concept doc anchor when one-hop is shorter). Same rewrite across subsystem docs, AGENTS.md files, and concept docs.
5. After every ADR has moved, `docs/architecture/decisions/` is DELETED (the `git rm` of the now-empty directory + the README), and the parent ledger row flips to `MERGED`.

### Out of scope (other parent chunks)

- Editing the section 22.6 gate catalogue to add a formal `grep-receipts-eq` definition: the gate is named in the parent row, defined in section 9 by reference, and operationally specified in D-DOC3.2 below; a section 22.6 edit is unnecessary scope creep.
- Agent memory (`/memories/repo/`, `/memories/`): derived per CLAUDE.md section 5; not edited here, self-corrects.
- Any new ADR: section 9 forbids new numbered ADRs. New rationale + rejected alternatives go directly into the relevant subsystem/concept doc per ADR-0034's routing rule (the one rule this sub-plan honours even as it retires the ADR file convention).
- ADR README.md content: the README itself is part of the directory; D-DOC3.10 deletes it with the directory.
- Cross-references inside ALREADY-ARCHIVED plan-docs under `docs/archive/plans/`: those are frozen historical artifacts; we do NOT rewrite their `ADR-NNNN` links (they are records of the world at the time they were authored). Only LIVE `docs/` + `CLAUDE.md` get rewritten.

---

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| D-DOC3.1 spawn (this PR; flip parent row + create this sub-plan) | - | docs-review | #723 | MERGED |
| D-DOC3.2 redirect index `docs/reference/decision-index.md` + baseline gate (records strict-h2 baseline=33 + broader-h2-h3 baseline=38; carries the per-ADR target-home map authored here) | D-DOC3.1 | grep-receipts-eq (strict=33, broader=38) | #724 | MERGED |
| D-DOC3.3 fold canonical-store + provenance ADRs into `docs/architecture/data/canonical-store.md` + `docs/concepts/data-provenance.md` (LIVE in this row: 0019, 0030, 0032, 0041, 0042, 0043; SUPERSEDED-archive in this row: 0002, 0014; LIVE deferred to D-DOC3.4: 0044 - its primary destination is `indicator-naming.md`; LIVE deferred to D-DOC3.8: 0046 - its primary destination is `backend/preflight.md`) | D-DOC3.2 | grep-receipts-eq (>=33 strict, >=38 broader) | #725 | MERGED |
| D-DOC3.4 fold indicator-naming + catalogue ADRs into `docs/concepts/indicator-naming.md` + `docs/architecture/data/indicator-catalogue.md` (LIVE: 0020, 0025, 0026, 0027, 0045; SUPERSEDED-archive: 0024) | D-DOC3.2 | grep-receipts-eq | - | TODO |
| D-DOC3.5 fold elections + electoral-hierarchy ADRs into `docs/concepts/electoral-hierarchy.md` + `docs/architecture/data/elections/*` + relevant frontend subsystem docs (LIVE: 0015, 0016-eci-stats, 0017-eci-current-year, 0023, 0035, 0048, 0049, 0051, 0052) | D-DOC3.2 | grep-receipts-eq | - | TODO |
| D-DOC3.6 fold url-grammar + place-IA + nav ADRs into `docs/concepts/url-grammar.md` (new if absent) + `docs/concepts/place-first-ia.md` (new if absent) + `docs/architecture/frontend/url-grammar.md` (LIVE: 0022, 0028, 0034, 0037, 0050; SUPERSEDED-archive: 0016-frontend-hash) | D-DOC3.2 | grep-receipts-eq | - | TODO |
| D-DOC3.7 fold boundaries + map ADRs into `docs/architecture/frontend/map.md` + `docs/architecture/data/boundaries.md` + `docs/architecture/frontend/topojson-loader.md` + `docs/architecture/data/canonical-store.md` (additive ADR-0036 h3s) (LIVE: 0031, 0036, 0047-topojson; SUPERSEDED-archive: 0029) | D-DOC3.2 | grep-receipts-eq | #726 | MERGED |
| D-DOC3.8 fold backend / ingest / schema ADRs into `docs/architecture/backend/*` + `docs/architecture/data/schema-evolution.md` (LIVE: 0003, 0018, 0033, 0047-schema-version) | D-DOC3.2 | grep-receipts-eq | - | TODO |
| D-DOC3.9 fold yenask + misc ADRs into `docs/architecture/frontend/yenask/*` + `docs/concepts/citizen-first.md` (LIVE: 0021, 0039, 0040; SUPERSEDED-archive: 0038; SUPERSEDED-archive: 0017-explore-page-uses-sql-js) | D-DOC3.2 | grep-receipts-eq | - | TODO |
| D-DOC3.10 CLAUDE.md cross-reference rewrite (~10 ADR-NNNN links to `decision-index.md#NNNN-<slug>` or direct doc anchors) + AGENTS.md sweep + DELETE `docs/architecture/decisions/` directory (and README) + flip parent ledger row -> MERGED + archive this sub-plan to `docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md` | D-DOC3.3..D-DOC3.9 | grep-receipts-eq (strict=33, broader=38) (FINAL) + grep zero `architecture/decisions/0` links in `CLAUDE.md` + zero `ADR-NNNN` un-rewritten in LIVE `docs/**/*.md` | - | TODO |

Parallel-safe groups (each fold-row touches a different subsystem/concept doc tree with no shared write target):

- **Strictly serial**: D-DOC3.1 -> D-DOC3.2 -> {D-DOC3.3..D-DOC3.9 parallel} -> D-DOC3.10
- **Wave-parallel (after D-DOC3.2)**: D-DOC3.3, D-DOC3.4, D-DOC3.5, D-DOC3.6, D-DOC3.7, D-DOC3.8, D-DOC3.9 - seven rows that may ship in any order or in parallel worktrees. Each rebases on whichever sibling merges first and re-runs the gate (the gate is a sum-across-doc-tree, so a sibling merge changes the intermediate count but not the final).
- **Final closure**: D-DOC3.10 ships only after the seven fold-rows are MERGED; it rewrites CLAUDE.md / AGENTS.md cross-refs in one PR (the rewrite needs to know every ADR's final anchor), deletes the now-empty `decisions/` directory, and flips the parent row.

The orchestrator MAY ship Wave rows in any order. Each sub-row is a separate PR with its own branch and its own gate evidence in the PR body. A sub-row that itself exceeds one PR (D-DOC3.5 elections is the most likely candidate at 9 ADRs across multiple electoral docs) spawns a sub-sub-plan per parent section 24.5 with a thin row here flipped to `DEFERRED-TO-SUBPLAN`.

---

## Per-sub-row notes

### D-DOC3.1 spawn (this PR)

- Edits `TODO/20260603-data-and-charting-platform-reset-plan.md` section 22.5 to flip the D-DOC3 row TODO -> DEFERRED-TO-SUBPLAN with forward-pointer to this file and a `_pending_` placeholder for the spawn PR#.
- Creates this file.
- No code, no test, no doc-tree edit beyond the parent row + this sub-plan. Gate: docs-review (visual review of the routing map below + the parent row flip).
- 2-commit-then-squash pattern: commit 1 = both edits with `_pending_`; commit 2 = self-stamp the PR# in both placeholders after `gh pr create` returns the number.

### D-DOC3.2 redirect index + baseline gate

- Create `docs/reference/decision-index.md` with one row per ADR: `| ADR-NNNN | <title> | <status> | <target> | <owner> |`. Target is either `[docs/path#anchor]` for live ADRs (anchor authored in D-DOC3.3..D-DOC3.9) or `[docs/archive/decisions/NNNN-<slug>.md]` for fully-superseded/rejected ADRs (path authored in D-DOC3.10's archive moves).
- Numbers NEVER reused (section 9 mandate). The index serves as the permanent redirect from any historical link.
- Record TWO BASELINE `grep-receipts-eq` counts in the index body + this row's PR body (both load-bearing; either may anchor a downstream check):
  - Strict h2 only: `grep -rc --include='*.md' -E '^## (Rejected alternatives|Alternatives considered)' docs/architecture/decisions/ | awk -F: '{s+=$2}END{print s}'` = **33**.
  - Broader h2-h3 + case-insensitive + extended phrasings: `grep -ric --include='*.md' -E '^#{2,3}\s*(Rejected alternatives|Alternatives considered)' docs/architecture/decisions/ | awk -F: '{s+=$2}END{print s}'` = **38**.
  - Audit-correction (per `/memories/lessons.md` filesystem-truth rule): the D-DOC3.1 spawn body asserted 36; filesystem enumeration of `docs/architecture/decisions/0*.md` (44 files) on 2026-06-04 returned 33 (strict) and 38 (broader). The 36 was a memory-counted guess. Truth supersedes; 33 + 38 are now the binding numbers.
- At plan close (D-DOC3.10 gate), the SAME two invocations run against the new union path set `docs/architecture/ docs/concepts/ docs/archive/decisions/` (with `docs/architecture/decisions/` deleted at D-DOC3.10) MUST return 33 (strict) AND 38 (broader) - no block lost, no block invented.
- Intermediate fold-row PRs (D-DOC3.3..D-DOC3.9) each cite the running counts using the same two patterns; a fold-row that lifts N receipts from `docs/architecture/decisions/` to a subsystem/concept doc preserves the sum-across-tree count exactly.
- The index also carries the per-ADR target-home map: a table of every ADR `NNNN` mapping to its target subsystem/concept doc and the section anchor where its receipt lands. This IS the contract the D-DOC3.3..D-DOC3.9 sub-rows execute against.

### D-DOC3.3 fold canonical-store + provenance ADRs

Live ADRs targeting `docs/architecture/data/canonical-store.md` + `docs/concepts/data-provenance.md`:

| ADR | Target doc | Notes |
| --- | --- | --- |
| 0019 dataset-topology-and-column-discipline | `docs/architecture/data/canonical-store.md` | dataset-tier layout + column-naming invariants |
| 0030 canonical-store-duckdb-wasm | `docs/architecture/data/canonical-store.md` | the foundational canonical-store ADR; folds in as the doc's Design rationale |
| 0032 sources-citation-ledger | `docs/concepts/data-provenance.md` | 11-column citation contract; vintage semantics point to 0042 inline |
| 0041 meadow-tier | `docs/architecture/data/canonical-store.md` | sub-section on the backend-internal meadow tier; carries the MIGRATING marker per CLAUDE.md section 10 anti-pattern (meadow retires at B4) |
| 0042 sources-schema-v3-vintage-as-period-anchor | `docs/concepts/data-provenance.md` | v3.0 vintage sharpening on top of 0032 |
| 0043 auto-rollup-at-canonical-write-time | `docs/architecture/data/canonical-store.md` | F7 doctrine (computed fields are first-class at write time) |
| 0044 grain-over-entity | `docs/concepts/indicator-naming.md` (cross-link from canonical-store.md) | the grain-via-entity_kind rule; primary home is naming because the rule is about ids |
| 0046 pre-flight-ingest-gate-contract | `docs/architecture/backend/ingest.md` (or sibling) | the six-check pre-flight gate; canonical-store.md cross-links |

Full-superseded ADRs moved to `docs/archive/decisions/` with trace folded:

| ADR | Successor | Trace destination |
| --- | --- | --- |
| 0002 provenance-as-sources-list | 0032 | One-line note in `docs/concepts/data-provenance.md` `Rejected alternatives`: "domain-as-identity (per archived ADR-0002)" |
| 0014 sqlite-emitter | 0030 | One-line note in `docs/architecture/data/canonical-store.md` `Rejected alternatives`: "in-bundle SQLite as canonical store (per archived ADR-0014)" |

Gate: grep-receipts-eq running total stays >=33 strict / >=38 broader at intermediate state. Per the per-ADR analysis in D-DOC3.2's index baseline: 0019 + 0030 + 0014 + 0002 each contribute 1 strict + 1 broader receipt; 0032 + 0041 + 0042 + 0043 each contribute 0 strict + 1 broader (h3 only, or non-standard h2 capitalisation). This PR ADDS new `## Rejected alternatives` h2 sections to canonical-store.md + data-provenance.md (each with N h3 subsections per fold), so canonical-store.md gains 1 strict + 5 broader; data-provenance.md gains 1 strict + 4 broader. The originals stay in place pending D-DOC3.10 (delete `docs/architecture/decisions/`). Net: strict 33 -> 35; broader 38 -> 47. Both >= baselines; gate passes.

Per-row scope adjustments (made when this row was claimed, 2026-06-04): ADRs 0044 (primary home `indicator-naming.md`) and 0046 (primary home `backend/preflight.md`) are LEFT IN PLACE for D-DOC3.4 and D-DOC3.8 respectively, because their primary subsystem/concept docs are owned by those fold-rows. The redirect index `docs/reference/decision-index.md` already pins those anchors. This keeps D-DOC3.3 strictly bounded to the canonical-store.md + data-provenance.md write targets named in the row label, honouring the parallel-safety rule "No two fold-rows write to the same target doc". No receipt count is affected by this scoping; downstream rows author the receipts for 0044 + 0046.

### D-DOC3.4 fold indicator-naming + catalogue ADRs

| ADR | Target doc | Notes |
| --- | --- | --- |
| 0020 indicator-artifact-as-data-contract | `docs/architecture/data/indicator-catalogue.md` (or canonical-store.md if catalogue doesn't exist yet) | the "indicator artifact is THE data contract" rule |
| 0025 rename-national-to-fiscal-actor-prefixes | `docs/concepts/indicator-naming.md` | actor-prefix naming convention |
| 0026 lift-collection-inventory-out-of-indicator-artifact | `docs/architecture/data/indicator-catalogue.md` | catalogue/inventory separation |
| 0027 cadence-as-separate-field-from-time-grain | `docs/concepts/indicator-naming.md` | cadence vs time-grain distinction |
| 0045 grapher-catalogue-split | `docs/architecture/data/indicator-catalogue.md` + `docs/architecture/frontend/grapher.md` | catalogue lives backend-side; grapher lives frontend-side |

Full-superseded:

| ADR | Successor | Trace destination |
| --- | --- | --- |
| 0024 backend-aggregator-for-facetted-indicators | PR 7b retirement | One-line note in `docs/architecture/data/indicator-catalogue.md` `Rejected alternatives`: "backend Aggregator composer for facetted indicators (per archived ADR-0024)" |

### D-DOC3.5 fold elections + electoral-hierarchy ADRs

This is the largest single fold-row (9 ADRs). If LOC budget exceeds one PR, spawn a sub-sub-plan per section 24.5.

| ADR | Target doc | Notes |
| --- | --- | --- |
| 0015 constituency-hierarchy-fields | `docs/concepts/electoral-hierarchy.md` | AC/PC field shape |
| 0016 eci-statistical-reports-canonical | `docs/architecture/backend/sources-eci.md` | ECI as canonical (per F1/O9 "every government source is gold") |
| 0017 eci-current-year-ingestion | `docs/architecture/backend/sources-eci.md` | current-year handling |
| 0023 election-event-identity-per-place | `docs/concepts/electoral-hierarchy.md` | event identity rule |
| 0035 persons-fork-option-b | `docs/architecture/data/elections/persons.md` | persons-table fork rationale |
| 0048 elections-drill-ia-and-tile-cartogram | `docs/architecture/frontend/charts/election-views.md` | the elections-renderer fence + tile cartogram |
| 0049 canonical-ac-join-key | `docs/concepts/electoral-hierarchy.md` | canonical AC join key (entity_id format) |
| 0051 historical-pc-crosswalk-and-delimitation-policy | `docs/concepts/electoral-hierarchy.md` | PC crosswalk + delim policy |
| 0052 election-event-in-path-not-query | `docs/architecture/frontend/url-grammar.md` (new if absent) | path-not-query for the event slug |

### D-DOC3.6 fold url-grammar + place-IA + nav ADRs

| ADR | Target doc | Notes |
| --- | --- | --- |
| 0022 place-first-ia-with-topic-catalogue | `docs/concepts/place-first-ia.md` (new if absent) | place-first IA doctrine |
| 0028 url-scheme-place-first-flat-indicator-slug | `docs/architecture/frontend/url-grammar.md` (new if absent) | URL scheme rule |
| 0034 documentation-routing-contract | CLAUDE.md section 5 + `docs/concepts/documentation-discipline.md` (new if absent) | the routing rule itself; primary home becomes CLAUDE.md section 5 (where it's already cited); the concept doc carries the verbatim 4-class table |
| 0037 url-grammar-drop-india-prefix | `docs/architecture/frontend/url-grammar.md` | drop the `/india/` prefix |
| 0050 folder-naming-lgd-slug | `docs/architecture/data/canonical-store.md` (folder-naming section) | LGD-slug folder rule |

Full-superseded:

| ADR | Successor | Trace destination |
| --- | --- | --- |
| 0016 frontend-hash-routing | 0028 | One-line note in `docs/architecture/frontend/url-grammar.md` `Rejected alternatives`: "hash-routing on the frontend (per archived ADR-0016 frontend-hash-routing); path routing on Pages adopted per ADR-0028" |

### D-DOC3.7 fold boundaries + map ADRs

| ADR | Target doc | Notes |
| --- | --- | --- |
| 0031 boundary-geometry-strategy | `docs/architecture/data/boundaries.md` | geometry strategy |
| 0036 state-identity-and-slice-registration | `docs/architecture/data/canonical-store.md` (state-identity section) + `docs/concepts/electoral-hierarchy.md` | state identity rule |
| 0047 topojson-as-render-encoding | `docs/architecture/frontend/topojson-loader.md` | topojson encoding rule |

Full-superseded:

| ADR | Successor | Trace destination |
| --- | --- | --- |
| 0029 unmapped-region-chips | D.1.A retirement | One-line note in `docs/architecture/frontend/map.md` (or `docs/concepts/unmapped-regions.md` if a concept doc exists) `Rejected alternatives`: "chip-based unmapped-region label (per archived ADR-0029); the surface was retired wholesale 2026-05-30" |

### D-DOC3.8 fold backend / ingest / schema ADRs

| ADR | Target doc | Notes |
| --- | --- | --- |
| 0003 no-fetch-cache | `docs/architecture/backend/fetcher.md` (or `docs/concepts/no-fetch-cache.md`) | no-fetch-cache rule; MIGRATING marker since `core/http.py` is deleted in B4 |
| 0018 wikipedia-district-name-resolution | `docs/architecture/backend/sources-wikipedia.md` (or relevant Wikipedia-adapter doc) | wiki name-resolution rule (note: 0033 retires the adapter; both live ADRs co-fold) |
| 0033 retire-wikipedia-districts-adapter | `docs/architecture/backend/sources-wikipedia.md` (same doc) | retirement rationale |
| 0047 schema-version-compatibility-contract | `docs/architecture/data/schema-evolution.md` | schema-version compatibility contract; CLAUDE.md section 11 already cites this |

### D-DOC3.9 fold yenask + misc ADRs

| ADR | Target doc | Notes |
| --- | --- | --- |
| 0021 no-implementation-disclosure-on-public-pages | `docs/concepts/citizen-first.md` | citizen-first rule |
| 0039 yenask-retrieval-augmented-intent-extraction | `docs/architecture/frontend/yenask/pipeline.md` (or equivalent yenask doc) | LLM-OS pipeline rationale (still live per Status pointer) |
| 0040 yenask-brand-and-lab-route | `docs/architecture/frontend/yenask/brand-and-route.md` | brand + lab route rule |

Full-superseded:

| ADR | Successor | Trace destination |
| --- | --- | --- |
| 0038 yenask-two-stage-llm-pipeline-rejected | 0039 | One-line note in yenask pipeline doc `Rejected alternatives`: "two-stage LLM pipeline (per archived ADR-0038)" |
| 0017 explore-page-uses-sql-js | 0030 | One-line note in `docs/architecture/data/canonical-store.md` `Rejected alternatives`: "sql.js for the explore page (per archived ADR-0017 explore-page-uses-sql-js)" - landing here because the canonical-store ADR superseded it |

### D-DOC3.10 CLAUDE.md cross-ref rewrite + decisions-dir DELETE + closure

- CLAUDE.md sweep: rewrite the ~10 direct `ADR-NNNN` links (verified locations L49, L97, L106, L176, L178, L187, L189, L190, L191, L195, L196, L219, L227 from the inventory grep done in spawn prep) to `decision-index.md#NNNN-<slug>` anchors OR to the target subsystem/concept doc anchor when one-hop is shorter. Specific cases: `ADR-0034` mentioned in section 5 + the anti-pattern table can keep its citation as `decision-index.md#0034-documentation-routing-contract` (the index IS the routing rule's permanent home for outside readers). `ADR-0032` x2 in section 10 + section 12 -> rewrite to `data-provenance.md#design-rationale`. `ADR-0041` x2 -> rewrite to `canonical-store.md#meadow-tier`. `ADR-0042` -> `data-provenance.md#vintage-semantics`. `ADR-0044` x2 -> `indicator-naming.md#grain-over-entity`. `ADR-0045` x2 -> `indicator-catalogue.md#grapher-split`. `ADR-0046` -> `backend/ingest.md#pre-flight-gate`. `ADR-0047` (schema) -> `data/schema-evolution.md#compatibility-contract`.
- AGENTS.md sweep across all 8 (`admin/`, `backend/yen_gov/`, `frontend/src/`, `frontend/src/lib/yenask/`, `datasets/livestock/`, `datasets/grapher/`, `tools/boundaries/`, `tools/iced_parity/`) - rewrite every `ADR-NNNN` reference.
- `git rm -r docs/architecture/decisions/` (the now-empty directory + the stale README).
- `git mv TODO/20260604-d-doc3-adr-retire-subplan.md docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md`.
- Append `## Plan complete (YYYY-MM-DD)` section with the per-row distillation map (Sub-row | PR# | Target doc(s)) to the archived sub-plan, BEFORE the existing `## See also` section (per `/memories/lessons.md` "Plan complete section BELONGS BEFORE See also").
- Flip the parent ledger row D-DOC3 from `DEFERRED-TO-SUBPLAN` to `MERGED` + stamp the closure PR#.
- Gate: `grep-receipts-eq = 36` (FINAL count across `docs/architecture/` + `docs/concepts/` + `docs/archive/decisions/`, with `docs/architecture/decisions/` now non-existent) + `grep -r 'architecture/decisions/0' CLAUDE.md docs/**/AGENTS.md` returns ZERO matches + `grep -r 'ADR-0[0-9]\{3\}' CLAUDE.md docs/**/*.md docs/**/AGENTS.md` (excluding `docs/archive/`) returns ZERO un-rewritten matches.

---

## Parallel-safety

- D-DOC3.1 (this spawn) is doc-only on `TODO/*.md` paths; parallel-safe with every other in-flight chunk.
- D-DOC3.2 (redirect index + baseline) creates ONE new file `docs/reference/decision-index.md`; parallel-safe.
- D-DOC3.3..D-DOC3.9 (the seven fold-rows) each touch a different subsystem/concept doc tree per the routing map above. No two fold-rows write to the same target doc, so worktree-parallel execution is safe. A given fold-row that creates a NEW concept doc (e.g. D-DOC3.6 `place-first-ia.md`) must check the doc doesn't already exist BEFORE creating - if it does (e.g. from a sibling fold-row racing), rebase + append rather than create.
- D-DOC3.10 (final rewrite + DELETE) MUST be strictly serial after all seven fold-rows MERGED, because the cross-reference rewrite needs every ADR's final anchor known, and the `git rm -r decisions/` only succeeds when no fold-row is in-flight.

---

## Why D-DOC3 spawning is in-doctrine per section 24.5

section 24.5 trigger: "When a chunk grows past a single PR's worth of detail - more than ~5 sub-steps, its own design forks, or its own multi-row tracker." All three apply:

1. **>5 sub-steps:** 10 sub-rows (D-DOC3.1..D-DOC3.10).
2. **Own design forks:** which ADRs land in which subsystem doc (the per-ADR routing map above is the resolution); whether to add a `Rejected alternatives` section to the 8 ADRs that lack one (gate-strict reading: do not invent - the gate counts the 36 existing blocks only); whether to also rewrite cross-refs in archived plan-docs under `docs/archive/plans/` (resolved: NO - those are frozen historical artifacts per section 22.5 + section 5 doctrine).
3. **Own multi-row tracker:** the per-row Execution Ledger above.

Precedent: U1 (4 sub-rows + spawn), B1 (7 sub-rows + spawn), B2a (8 sub-rows + spawn), B2b (5 family rows + spawn + two further sub-sub-plans at B2b.4 and B2b.5). D-DOC3 sits squarely in the same shape.

---

## See also

- Parent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) section 9 (ADR retire keep-receipts), section 22.4 (5 contract-invariants), section 22.5 (Execution Ledger), section 22.6 (gates catalogue), section 24.5 (sub-plan spawning rule).
- Routing contract: [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md) (the rule this sub-plan honours even as it retires the ADR file convention).
- Precedent sub-plans: [B2b](20260604-b2b-reingest-subplan.md), [U1 (archived)](../docs/archive/plans/20260604-u1-tokens-fonts-subplan.md), [B1 (archived)](../docs/archive/plans/20260604-b1-csv-writer-subplan.md), [B2a (archived)](../docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md).

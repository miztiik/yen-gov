# B2b sub-plan - reingest existing families to long-format CSV

**Last Updated**: 2026-06-05
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) chunk B2b
**Status**: COMPLETE 2026-06-05 (B2b.1..B2b.5 MERGED; B2b.6 closure #776)
**Authority**: Hans + Max (data shape, identity, units, F1 estimate-stage, F6 one-per-concept) / Gregor (FK contract, write order, parity gate) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk B2b reads as one row in the parent Execution Ledger (22.5) but expands into FIVE family reingests, each producing many CSV files and each gated independently by `cross-format-parity` (22.6). The five families are: `energy`, `livestock`, `governments`, `taxonomy` (the datapoint-shaped parquets, not the catalogue already shipped in B2a), and `elections-from-local-TCPD` (per plan section 21.4 - re-parse local TCPD CSV into the per-election self-contained layout, NOT a parquet -> CSV transcode).

Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first) and parent plan section 24.5, the right shape is a thin parent row + this sub-plan. Same shape B1 + B2a followed.

This sub-plan is the merge-queue authority for B2b. The parent ledger row stays `DEFERRED-TO-SUBPLAN` until B2b.6 (closure) merges, at which point parent flips to `MERGED` with the closure PR# stamped.

## Scope

In scope: building per-family ingest + canonical CSV emitters that produce the long-format datapoint CSVs (and, for elections, the per-election self-contained CSVs per 21.3) from existing on-disk sources, with cross-format parity asserted against the surviving parquet (or, for elections, against the surviving canonical parquet `elections_candidacies.parquet` + `state=*/election_results.parquet`).

For each family the emitted CSV file class is:

- `energy`, `livestock`, `governments`, `taxonomy` datapoint families -> `datasets/data/datapoints/<entity_kind>/<variable_id>.csv` with columns `entity_id, time, value, source_id` (+ optional facet column per 21.6 when the source row carries an analytical facet). FKs: `entity_id` -> `entities/geo.csv` (or `entities/electoral.csv`); `source_id` -> `entities/source.csv`; variable_id is the basename and MUST appear in `variables.csv`.
- `elections-from-local-TCPD` -> `datasets/elections/assembly/state=<lgd-slug>/election=<year>/{candidacies,summary}.csv` + `datasets/elections/parliament/election=<year>/{candidacies,summary}.csv` per 21.3 / 23.4 (parliament carries `state` as a MANDATORY column; `entity_id = IN-PC-<delim>-<state>-<pc_no>`; `summary == recompute(candidacies)`).

Out of scope (other chunks):

- B2a catalogue + entity emits: already MERGED (#688).
- F1 CSV loaders + parity-oracle-CSV rewrite: a separate chunk that blocks on B2a + B2b + U1 + D-DOC0.
- X1a reader flip / X1b parquet delete: B2b only writes CSVs alongside surviving parquet; deletion is X1b's job.
- B3/B4 producer deletion: depends on X1b.
- Network-fetch deletion (per 21.4): B4 territory. B2b only consumes LOCAL TCPD CSV that is already on disk (the parsers in `backend/yen_gov/sources/eci/` minus the URL builders).

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| B2b.1 energy family CSV reingest (6 parquets) | - | cross-format-parity | #691 | MERGED |
| B2b.2 livestock family CSV reingest (3 parquets) | - | cross-format-parity | #693 | MERGED |
| B2b.3 governments family CSV reingest (2 parquets; term-shape per 20.4) | - | cross-format-parity | #695 | MERGED |
| B2b.4 taxonomy datapoint reingest (the parquets B2a left behind: `election_events`, `facet-axes`, `ac_crosswalk`, `indicator_topic_tags`, `methodology_breaks`, `persons`, `state_tiers`) | - | cross-format-parity | #698-#708 + DROP #774 | MERGED (sub-sub-plan [docs/archive/plans/20260604-b2b4-taxonomy-subplan.md](20260604-b2b4-taxonomy-subplan.md) delivered: 6 emitters lifted via #698 methodology_breaks + #700 facet_axes + #702 state_tiers + #704 election_events + #706 indicator_topic_tags + #708 ac_crosswalk; B2b.4.7 persons DROPPED via #774 per Fowler+Hans converged verdict (zero-consumer audit registry; biographic cols migrate inline via B2b.5.x); closure docs in [canonical-writer.md](../../architecture/backend/canonical-writer.md) "Taxonomy datapoint reingest" section) |
| B2b.5 elections-from-local-TCPD per-election CSV reingest (per 21.3 + 21.4 + 23.4) | - | cross-format-parity + parity-oracle-CSV (winner+margin invariants only; full oracle rewrite is F1) | #762-#772 | MERGED (sub-sub-plan [docs/archive/plans/20260604-b2b5-elections-reingest-subplan.md](20260604-b2b5-elections-reingest-subplan.md) delivered: spine 0a-0e (#762-767) + assembly 30 states 474 CSVs ~116k candidacies (#768-771) + parliament 11 LS cycles 19336 candidacies (#772); B2b.5.5 source-backfill done inline; 0e ECI-decommission + 0d-del legacy-delete RE-SCOPED to owning chunks via disposition receipts under `datasets/_ops/`; closure docs in canonical-writer.md) |
| B2b.6 close sub-plan: flip parent B2b row to MERGED + stamp closure PR + distil into [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md) section "Datapoint reingest" + archive this sub-plan | B2b.1..B2b.5 | docs-review | #776 | IN-FLIGHT |

Parallel-safe groups (each `cross-format-parity` runs against a different on-disk family with no shared write target):

- Wave A (no blockers, all five families independent): B2b.1, B2b.2, B2b.3, B2b.4, B2b.5.
- Closure: B2b.6.

The orchestrator MAY ship Wave A rows in any order. Each sub-row is a separate PR with its own branch and its own parity-gate evidence in the PR body. A sub-row that itself exceeds one PR (B2b.5 is the prime candidate; B2b.1 / B2b.4 are likely candidates) spawns a sub-sub-plan per parent 24.5 with a thin row here flipped to `DEFERRED-TO-SUBPLAN`.

## Per-sub-row notes

### B2b.1 energy

Source parquets to reingest into `datasets/data/datapoints/<entity_kind>/`:

- `energy_capacity_pipeline.parquet`
- `energy_demand_supply.parquet`
- `energy_distribution_performance.parquet`
- `energy_fuel_consumption.parquet`
- `energy_generation.parquet`
- `energy_installed_capacity.parquet`

Per-file plan: each parquet maps to one OR MORE `variable_id` (one CSV per `(measure, unit, facet)` per F2 / 21.6). Multi-fuel / multi-direction columns become EITHER a `fuel` / `direction` column inside one long CSV OR separate facet CSVs sharing one `concept_id` (decide per file; never `__` per 21.6). Every emitted row carries `source_id` derived via `derive_source_id` (CLAUDE.md section 12); `entity_id` joins `entities/geo.csv`.

Parity gate: `backend/tests/test_csv_parquet_parity.py::test_energy` reads both parquet and the new CSV, asserts identical row count + typed per-cell equality (no float-string drift; `null is null`).

If the six files together exceed one PR's reasonable surface (>~500 LOC of writer + tests + CSV emits), spawn `TODO/20260604-b2b1-energy-subplan.md` per 24.5.

### B2b.2 livestock

Source parquets: `livestock_naip_iv.parquet`, `livestock_owner_registration.parquet`, `livestock_pashu_aadhaar.parquet`. Smaller surface than energy; expected to fit one PR.

`datasets/livestock/AGENTS.md` per 22.7 already carries the MIGRATING banner from D-DOC4 - no extra doctrine edit here. Parity gate as B2b.1.

### B2b.3 governments

Source parquets: `dim_offices.parquet`, `governments_office_holdings.parquet`. These are NOT pure datapoint shape - `governments_office_holdings.parquet` is a term-shape (one row per office-tenure), not `(entity, time, value)`. Two valid B2b.3 outcomes:

- (a) Treat office-tenure as wide, leave it as `datasets/governments/office_holdings.csv` (not under `datapoints/`) with the long-form indicator derivations (e.g. `share-of-cm-tenure-by-party`) emitted as proper datapoint CSVs in a later chunk.
- (b) Defer the whole term-shape redesign to the office-holders family chunk per plan 20.4 and ship B2b.3 as a NO-OP with documented rationale.

Decision: ship option (a) - mirror existing parquets to CSV at the same shape so parquet can be deleted in X1b without losing office data; the long-form derivation chunk follows in plan section 20.4 work.

### B2b.4 taxonomy (datapoint parquets B2a left behind)

B2a shipped the catalogue + entity emits from `taxonomy/*.json`. The remaining `taxonomy/*.parquet` artifacts (datapoint or mapping shape) still need a CSV destination so X1b can delete them:

- `election_events.parquet` -> `datasets/data/datapoints/electoral/election_events.csv` (or a sibling entity-style file - decide on first read).
- `facet-axes.parquet` -> mapping table; lives under `datasets/data/` as a small CSV.
- `ac_crosswalk.parquet` -> superseded by `entities/electoral_lgd_xwalk.csv` (B2a.7). VERIFY equivalence and mark this row DELETE-not-emit (no new file) if equivalence holds.
- `indicator_topic_tags.parquet` -> M:N table; emit as `datasets/data/indicator_topic_tags.csv` OR fold into `variables.csv` if a single `topic` column suffices (B2a.4 already carries `topic` - audit before emitting a separate file).
- `methodology_breaks.parquet` -> `datasets/data/methodology_breaks.csv` (Rosling-rule register per F6).
- `persons.parquet` -> entity family; emit as `datasets/data/entities/person.csv`.
- `state_tiers.parquet` -> small reference; emit as `datasets/data/state_tiers.csv` OR fold an `aliases` / `tier` column into `entities/geo.csv` (audit before emitting).

The PR body MUST list which of the seven becomes (i) a new CSV, (ii) a fold into an existing CSV, (iii) a delete-not-emit because B2a already covers it. Parity gate covers the (i) and (ii) cases only.

### B2b.5 elections-from-local-TCPD

Reingest, NOT transcode: per plan 21.4 the network-fetch code is BEING DELETED (B4); the citizen-facing election data is reparsed from the local TCPD CSV that is already on disk (the pure parsers in `backend/yen_gov/sources/eci/{constituencywise,partywise,people_panel}.py` survive). The surviving parquet family (`elections_candidacies.parquet` + per-state `state=<slug>/election_results.parquet`) is the parity target during this chunk; deletion is X1b.

Output layout (mandatory, per 21.3 + 23.4):

```
datasets/elections/
  assembly/state=<lgd-slug>/election=<year>/
    candidacies.csv   # candidate-grain (entity_id, state, election_year, constituency_no, ...)
    summary.csv       # constituency-grain; DERIVED projection of candidacies (F7)
  parliament/election=<year>/
    candidacies.csv   # country-wide; MUST carry `state` column (23.4)
    summary.csv       # one row per PC; entity_id = IN-PC-<delim>-<state>-<pc_no>
```

Per-election self-contained: no across-years AC file. Cross-year reads glob `assembly/state=<slug>/election=*/summary.csv` at read time.

Gates (both, not one):

- `cross-format-parity`: row counts + per-cell equality vs the surviving parquet, family-wide.
- `parity-oracle-CSV` (subset): winner + margin per constituency vs `canonical_winners_2026_05_19.json` AND `summary == recompute(candidacies)` per 23.4 / 22.6. The full F1 rewrite of `test_canonical_parity_oracle.py` does not block here; this row only needs the winner+margin invariants asserted from the new CSV path.

EL7 (`coverage.py` AC vs PC disposition per 23.4) MUST be resolved in this row's PR body before parliament data is emitted: either extend `coverage.py` to discriminate or scope-fence it to assembly with a doc note. An aggregator silently blind to a whole election class is a latent reporting bug.

Spawned as sub-sub-plan [docs/archive/plans/20260604-b2b5-elections-reingest-subplan.md](20260604-b2b5-elections-reingest-subplan.md) (2026-06-04) per 24.5: ~36 assembly states x N cycles plus parliament 1957..2024 is well over one PR. The corpus audit (42 parquets / ~161.6 MB, one `election_results.parquet` per state-dir + a single root `elections_candidacies.parquet` mixing AC + PC rows) is captured there. The spawn pattern matches B2a and B2b.4.

### B2b.6 closure

- Extend [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md) with a "Datapoint reingest" section listing each family's emitter module, its source parquet(s) (or local TCPD root for elections), and the parity-gate file path.
- Flip the parent B2b ledger row to MERGED in this same PR and stamp the closure PR number.
- Archive this sub-plan to `docs/archive/plans/20260604-b2b-reingest-subplan.md` with a "Plan complete" block per [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md).
- Confirm: every parquet under `datasets/{energy,livestock,governments,taxonomy,elections}/**` now has an emitted CSV sibling whose `cross-format-parity` gate is green; X1a may proceed.

## Contract invariants (inherited from parent 22.4)

1. Provenance FK mandatory: every emitted datapoint row carries `source_id` resolvable in `entities/source.csv` (CLAUDE.md Holy Law #9). For election rows, `source_id` derives from the TCPD release vintage via `derive_source_id`.
2. No `datetime.now` in content columns (CLAUDE.md anti-pattern). Wall-clock at write time is operational telemetry; never an observation field.
3. Deterministic sort + stable CSV serialisation: same input -> identical bytes, so diffs read clean.
4. Typed read at the boundary: every emitted CSV file class has its column contract in `datasets/data/_schema/columns.json` (or the elections column home named in B2b.5); the validator runs at write time AND the reader's `read_csv(columns=...)` map is generated from that single home (23.2).
5. No mocks: parity tests read REAL parquet + REAL CSV from disk (Holy Law #7); the gate skips cleanly only if a family is absent on this machine.

## Tracking

The parent Execution Ledger row B2b is `DEFERRED-TO-SUBPLAN -> TODO/20260604-b2b-reingest-subplan.md` in the SAME PR that lands this sub-plan. Sub-row status updates land inside each B2b.x PR per 24.3.

## See also

- Parent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) (sections 3, 20.1, 21.2, 21.3, 21.4, 22.5, 22.6, 23.1, 23.3, 23.4, 23.7, 24.5).
- B2a sub-plan precedent: [docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md](20260604-b2a-csv-catalogue-subplan.md).
- B1 sub-plan precedent: [docs/archive/plans/20260604-b1-csv-writer-subplan.md](20260604-b1-csv-writer-subplan.md).
- Canonical writer doc: [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md).
- Sub-plan spawning rule: parent section 24.5.

## Plan complete

Closed 2026-06-05 via PR #776. All five family rows MERGED + closure:

- **B2b.1 energy** -> [datasets/data/datapoints/](../../../datasets/data/datapoints/) energy datapoint CSVs (95 files). PR #691. Six source parquets re-emit as long-format `(entity_id, time, value, source_id)` rows, one CSV per `(measure, unit, facet)` per plan section F2/21.6. Closure stamp PR #692.
- **B2b.2 livestock** -> [datasets/data/datapoints/](../../../datasets/data/datapoints/) livestock datapoint CSVs (20 files). PR #693. Three source parquets (naip_iv, owner_registration, pashu_aadhaar). Closure stamp PR #694.
- **B2b.3 governments** -> [datasets/governments/](../../../datasets/governments/) term-shape CSVs (office, holder, office_holdings). PR #695. Term-shape preserved per plan 20.4; long-form derivation deferred to a successor chunk. Closure stamp PR #696.
- **B2b.4 taxonomy datapoint reingest** -> [docs/archive/plans/20260604-b2b4-taxonomy-subplan.md](20260604-b2b4-taxonomy-subplan.md). PRs #698-#708 + DROP #774 + closure #775. Six emitters lifted (methodology_breaks, facet_axes, state_tiers, election_events, indicator_topic_tags, ac_crosswalk); seventh (persons) DROPPED per Fowler+Hans converged verdict (audit-only parquet with zero frontend consumers; biographic dim_persons cols migrate inline via B2b.5.x).
- **B2b.5 elections-from-local-TCPD** -> [docs/archive/plans/20260604-b2b5-elections-reingest-subplan.md](20260604-b2b5-elections-reingest-subplan.md). PRs #762-#772. Spine 0a-0e (#762-#767) + assembly 30 states 474 CSVs ~116k candidacies (#768-#771) + parliament 11 LS cycles ~19,336 candidacies (#772). B2b.5.5 source-backfill done inline; 0e ECI-decommission + 0d-del legacy-delete RE-SCOPED to owning chunks via disposition receipts under `datasets/_ops/`.
- **B2b.6 closure** -> THIS PR (#776). Parent B2b row in grandparent ledger flipped to MERGED; this sub-plan archived to `docs/archive/plans/20260604-b2b-reingest-subplan.md`. F1 + X1a + X1b downstream chain UNBLOCKED.

Distillation map per [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md):

- Per-family emit map -> [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md). Sections: `Seed emitters (B2a)`, `Taxonomy datapoint reingest (B2b.4)`, `Elections datapoint reingest (B2b.5)`. The B2b.1/B2b.2/B2b.3 families are mirrored 1:1 from on-disk parquets and their per-family detail lives in the per-sub-row notes here + each PR body; the canonical-writer.md sections are the citable home for the ones that needed shape decisions (B2a, B2b.4, B2b.5).
- Fowler+Hans converged verdict for B2b.4.7 persons DROP -> section 0 of [docs/archive/plans/20260604-b2b4-taxonomy-subplan.md](20260604-b2b4-taxonomy-subplan.md).
- Per-PR audit trail -> stays in this archived plan + the two archived sub-sub-plans (b2b4 + b2b5).

Deletion-safety for X1b: every datapoint parquet under `datasets/{energy,livestock,governments,taxonomy,elections}/**` now either has an emitted CSV sibling whose `cross-format-parity` gate is green (B2b.1/2/3 + the six emitted B2b.4 rows + the entire B2b.5 elections re-emit), OR has a documented zero-consumer DROP receipt (B2b.4.7 persons.parquet only). X1a (reader flip) and X1b (parquet delete) MAY now proceed.

Plan-doc remains as the audit ledger; do not edit further. New work starts a new plan-doc.

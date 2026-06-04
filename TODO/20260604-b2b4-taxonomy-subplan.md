# B2b.4 sub-sub-plan - taxonomy datapoint-parquet reingest to long-format CSV

**Last Updated**: 2026-06-04
**Parent**: [TODO/20260604-b2b-reingest-subplan.md](20260604-b2b-reingest-subplan.md) row B2b.4
**Grandparent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk B2b
**Status**: IN-FLIGHT (spawned 2026-06-04)
**Authority**: Hans + Max (data shape, identity, FK target homes) / Gregor (FK contract, write order, parity gate) per CLAUDE.md section 0a

---

## Why this exists

Parent sub-plan row B2b.4 reads as one line but expands into SEVEN distinct file-shape decisions, each with its own column-contract entry, its own re-key (where applicable), its own parity gate, and one of the seven (`persons.parquet`, ~430k rows / ~30 MB CSV) is a heavy emit on its own. Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first) and parent plan section 24.5, this becomes a sub-sub-plan rather than one mega-PR.

The parent B2b sub-plan's B2b.4 row stays `DEFERRED-TO-SUBPLAN` with a forward-pointer to this file until B2b.4.8 (closure) merges, at which point B2b.4 flips to `MERGED` with the closure PR# stamped.

## Per-file audit and disposition

Surveyed 2026-06-04 against `datasets/taxonomy/*.parquet` (the seven datapoint-shape or reference-shape parquets B2a left behind after the catalogue + entity rip):

| Parquet | Rows | Cols | Shape | Disposition | Target CSV |
| --- | --- | --- | --- | --- | --- |
| `election_events.parquet` | 339 | 8 | per-state election event register (`state_code, event_id, kind, display, polled_on, term_end_estimated, data_status, notes`) | new CSV (reference) | `datasets/data/election_events.csv` |
| `facet-axes.parquet` | 127 | 8 | facet axis register (`axis_id, axis_label, axis_description, allow_compute_on_read_total, value_id, value_label, value_description, deprecated`) | new CSV (reference) | `datasets/data/facet_axes.csv` |
| `ac_crosswalk.parquet` | 4113 | 8 | full ECI-no -> LGD-AC-id mapping per delim (`state_code, eci_no, lgd_ac_id, ac_id, ac_name, delim_year, match_method, source_id`) | new CSV (NOT equivalent to `entities/electoral_lgd_xwalk.csv` which has 253 rows / 232 ACs - different shape, boundary-overlap not ECI-no mapping) | `datasets/data/entities/ac_crosswalk.csv` |
| `indicator_topic_tags.parquet` | 45 | 9 | M:N tag enrichment (`topic_id, artifact_kind, artifact_id, display, is_default, featured, scope, peer_set_default_override, in_topic_order`) | new CSV (does NOT fold into `variables.topic` - rich per-tag metadata: display label, default flag, scope, ordering) | `datasets/data/indicator_topic_tags.csv` |
| `methodology_breaks.parquet` | 5 | 7 | Rosling-rule register (`methodology_version, at_year, at_period_seq, kind, note, publisher_url, supersedes_methodology_version`) | new CSV (F6 reference) | `datasets/data/methodology_breaks.csv` |
| `persons.parquet` | 430630 | 7 | candidate-grain person entity (`person_id, display_name, source_id, confidence_tier, evidence_note_md, cluster_id, merged_candidacy_count`) | new CSV (entity family) | `datasets/data/entities/person.csv` |
| `state_tiers.parquet` | 104 | 7 | M:N tier -> state register (`tier_id, tier_label, definition_kind, definition, authority, state_code, notes`) | new CSV (does NOT fold into `geo.csv` - M:N membership with per-tier description + authority that geo cannot carry) | `datasets/data/state_tiers.csv` |

Zero `delete-not-emit` cases; zero `fold-into-existing` cases. All seven require a new file_class in `datasets/data/_schema/columns.json` and a new emitter under `backend/yen_gov/canonical/reingest/`.

## Scope

In scope: per-parquet emitter that reads the existing parquet under `datasets/taxonomy/` and writes the named target CSV via `csv_writer.write_csv(...)` against the file class declared in `datasets/data/_schema/columns.json`. Re-keys (per-row):

- `state_code` (ECI S/U code) -> LGD state slug via `lgd_states.json` for any row whose target column FKs into `entities/geo.csv` (election_events, state_tiers, ac_crosswalk's `state` projection).
- `source_id` rows MUST already exist in `entities/source.csv` (FK target shipped by B2a.1). Persons + ac_crosswalk + methodology_breaks all carry `source_id` columns from the parquet that resolve verbatim against the existing ledger.

Out of scope (other rows / chunks):

- Election candidacy / summary CSV emits per 21.3: B2b.5 (separate sub-sub-plan).
- Reader flip (X1a) + parquet delete (X1b): writer-only here; parquet survives.
- Office + holder entities: shipped under B2b.3 (term-shape).

## Sub-sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| B2b.4.1 `methodology_breaks.csv` from `methodology_breaks.parquet` (5 rows; smallest; F6 reference) | - | cross-format-parity | #698 | MERGED |
| B2b.4.2 `facet_axes.csv` from `facet-axes.parquet` (127 rows; reference) | - | cross-format-parity | #700 | MERGED |
| B2b.4.3 `state_tiers.csv` from `state_tiers.parquet` (104 rows; ECI `state_code` -> LGD slug re-key on emit) | - | cross-format-parity | #702 | MERGED |
| B2b.4.4 `election_events.csv` from `election_events.parquet` (339 rows; ECI `state_code` -> LGD slug re-key on emit) | - | cross-format-parity | #_pending_ | IN-FLIGHT |
| B2b.4.5 `indicator_topic_tags.csv` from `indicator_topic_tags.parquet` (45 rows; M:N; FK `topic_id` -> `topics.csv`; FK `artifact_id` -> `variables.csv` when `artifact_kind = 'indicator'`) | B2a.2 + B2a.4 (already MERGED) | cross-format-parity | - | TODO |
| B2b.4.6 `entities/ac_crosswalk.csv` from `ac_crosswalk.parquet` (4113 rows; `state_code` -> LGD slug; `source_id` FK to `entities/source.csv`) | - | cross-format-parity | - | TODO |
| B2b.4.7 `entities/person.csv` from `persons.parquet` (430630 rows; heaviest emit; `source_id` FK to `entities/source.csv`) | - | cross-format-parity | - | TODO |
| B2b.4.8 close sub-sub-plan: flip parent B2b.4 row to MERGED + stamp closure PR + distil per-file emit map into [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md) "Datapoint reingest" section + archive this file to `docs/archive/plans/` | B2b.4.1..B2b.4.7 | docs-review | - | TODO |

Parallel-safe groups (each `cross-format-parity` runs against a different on-disk parquet with no shared write target):

- Wave A (no blockers): B2b.4.1, B2b.4.2, B2b.4.3, B2b.4.4, B2b.4.5, B2b.4.6, B2b.4.7. All seven are independent (no cross-row FK between siblings; the FK targets they need are entity / catalogue CSVs already on disk from B2a).
- Closure: B2b.4.8.

The orchestrator MAY ship Wave A rows in any order. Each sub-sub-row is a separate PR with its own branch and its own parity-gate evidence in the PR body.

## Per-sub-row notes

### B2b.4.1 methodology_breaks

- Read `datasets/taxonomy/methodology_breaks.parquet`. Project verbatim - all 7 columns map 1:1.
- New file_class in `_schema/columns.json` keyed `datasets/data/methodology_breaks.csv` with PK `(methodology_version, at_year, at_period_seq)`.
- Parity gate asserts row-count + per-cell equality against the parquet.

### B2b.4.2 facet_axes

- Read `datasets/taxonomy/facet-axes.parquet`. Project verbatim - all 8 columns map 1:1. Filename loses the hyphen (`facet_axes.csv` per plan 21.6 underscore-in-filename convention).
- PK `(axis_id, value_id)`.

### B2b.4.3 state_tiers

- Read `datasets/taxonomy/state_tiers.parquet`. Re-key `state_code` (ECI S/U code) -> LGD state `entity_id` via `lgd_states.json` (rename column to `state_entity_id` or keep as `state` per columns.json shape - decide on emit).
- PK `(tier_id, state_entity_id)`.
- FK `state_entity_id` -> `entities/geo.csv.entity_id`.

### B2b.4.4 election_events

- Read `datasets/taxonomy/election_events.parquet`. Re-key `state_code` -> LGD state `entity_id` as B2b.4.3.
- PK `(state_entity_id, event_id)`.
- FK `state_entity_id` -> `entities/geo.csv.entity_id`.

### B2b.4.5 indicator_topic_tags

- Read `datasets/taxonomy/indicator_topic_tags.parquet`. Project verbatim.
- PK `(topic_id, artifact_kind, artifact_id)`.
- FK `topic_id` -> `topics.csv.topic`; FK `artifact_id` -> `variables.csv.indicator_id` when `artifact_kind = 'indicator'`. The validator's existing FK check handles the conditional shape.

### B2b.4.6 entities/ac_crosswalk

- Read `datasets/taxonomy/ac_crosswalk.parquet`. Re-key `state_code` -> LGD state `entity_id` via `lgd_states.json`; keep `lgd_ac_id, eci_no, ac_id, ac_name, delim_year, match_method, source_id` columns.
- PK `(state_entity_id, delim_year, eci_no)`.
- FK `state_entity_id` -> `entities/geo.csv.entity_id`; FK `source_id` -> `entities/source.csv.source_id`.
- This file is the AUTHORITATIVE ECI-no -> LGD-AC-id mapping (4113 rows). It is NOT the same as `entities/electoral_lgd_xwalk.csv` (253 rows, boundary-overlap decay-receipt shape).

### B2b.4.7 entities/person

- Read `datasets/taxonomy/persons.parquet` (430k rows). Project verbatim - all 7 columns map 1:1.
- PK `person_id`.
- FK `source_id` -> `entities/source.csv.source_id`.
- Heaviest emit; CSV size ~30 MB. No transforms; one streaming write.

### B2b.4.8 closure

- Extend [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md) "Datapoint reingest" section with each of B2b.4.1..B2b.4.7 emitter module + source parquet + parity-gate path.
- Flip the parent B2b.4 ledger row (in [TODO/20260604-b2b-reingest-subplan.md](20260604-b2b-reingest-subplan.md)) to MERGED in this same PR and stamp the closure PR number.
- Archive this file to `docs/archive/plans/20260604-b2b4-taxonomy-subplan.md` with a "Plan complete" block per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Confirm: every taxonomy parquet has an emitted CSV sibling whose `cross-format-parity` gate is green; B2b.4's deletion-safety is established for X1b.

## Contract invariants (inherited from grandparent 22.4)

1. Provenance FK mandatory: every emitted row that carries `source_id` resolves in `entities/source.csv` (CLAUDE.md Holy Law #9). The seven parquets either already carry `source_id` (persons, ac_crosswalk, methodology_breaks, election_events via `sources: []` note) or are pure reference (facet_axes, state_tiers, indicator_topic_tags) where `source_id` is omitted.
2. No `datetime.now` in content columns (CLAUDE.md anti-pattern). All seven parquets are static reference / mapping data; no run-time stamps to launder.
3. Deterministic sort + stable CSV serialisation: ORDER BY PK on emit so diffs read clean.
4. Typed read at the boundary: every emitted CSV file class has its column contract in `datasets/data/_schema/columns.json`; the validator runs at write time AND the reader's `read_csv(columns=...)` map is generated from that single home (23.2).
5. No mocks: parity tests read REAL parquet + REAL CSV from disk (Holy Law #7); the gate skips cleanly only if a family is absent.

## Tracking

The parent sub-plan row B2b.4 is `DEFERRED-TO-SUBPLAN -> TODO/20260604-b2b4-taxonomy-subplan.md` in the SAME PR that lands this sub-sub-plan. Sub-row status updates land inside each B2b.4.x PR per grandparent 24.3.

## See also

- Parent sub-plan: [TODO/20260604-b2b-reingest-subplan.md](20260604-b2b-reingest-subplan.md).
- Grandparent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) (sections 7, 20.4, 21.6, 22.4, 22.5, 22.6, 23.2, 24.5).
- B2a sub-plan precedent: [docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md](../docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md).
- B1 sub-plan precedent: [docs/archive/plans/20260604-b1-csv-writer-subplan.md](../docs/archive/plans/20260604-b1-csv-writer-subplan.md).
- Canonical writer doc: [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md).
- Sub-plan spawning rule: grandparent section 24.5.

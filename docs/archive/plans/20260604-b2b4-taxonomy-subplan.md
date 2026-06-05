# B2b.4 sub-sub-plan - taxonomy datapoint-parquet reingest to long-format CSV

**Last Updated**: 2026-06-05
**Parent**: [TODO/20260604-b2b-reingest-subplan.md](../../../TODO/20260604-b2b-reingest-subplan.md) row B2b.4
**Grandparent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) chunk B2b
**Status**: COMPLETE 2026-06-05 (B2b.4.1..B2b.4.6 MERGED + B2b.4.7 DROPPED + B2b.4.8 closure #775)
**Authority**: Hans + Max (data shape, identity, FK target homes) / Gregor (FK contract, write order, parity gate) per CLAUDE.md section 0a

---

## section 0 - Scope-change ledger (B2b.4.7 DROPPED, 2026-06-05, Fowler+Hans debate)

Per CLAUDE.md section 10 STOP-AND-SURFACE, a row the user explicitly named ("B2b.4.7 entities/person.csv from persons.parquet") may not be silently downgraded. The user's 2026-06-05 message ("I don't want a monstrous file for all AC/PC elections... let's not reintroduce those problems in CSV - how can we do this smartly Fowler/Hans?") opened the surface; the personas converged on DROP; the user's same message authorised executing the converged verdict.

| Verbatim instruction (from sub-sub-plan) | Proposed change | Reason | signoff |
| --- | --- | --- | --- |
| `B2b.4.7 entities/person.csv from persons.parquet (430630 rows; heaviest emit; source_id FK to entities/source.csv)` | **DROP the row entirely.** Do NOT emit `datasets/data/entities/person.csv`. Do NOT add the file_class to `datasets/data/_schema/columns.json`. Do NOT attempt the Path-A source-backfill from the original blocker memo. `persons.parquet` dies with the rest of the taxonomy parquets in X1b without a CSV sibling; the cross-format-parity gate is N/A for this family (no consumer means no parity claim to make). Local WIP commit `aa13d55e` on `feat/b2b-4-7-person-reingest` is abandoned via `git branch -D`. | **Empirical:** (a) grep `frontend/**` for `persons.parquet` unique cols (`confidence_tier`, `evidence_note_md`, `cluster_id`, `merged_candidacy_count`) returns 0 consumers; the 6 live `dim_persons` JOINs in frontend project columns that live ONLY on `datasets/elections/dim_persons.parquet` (`sex, age, education, profession, display_name`), not on `persons.parquet`. (b) Section 21.3 candidacies.csv schema embeds biographic cols inline, so the `dim_persons` JOIN is redundant after B2b.5 (already shipped #768-#772). (c) Path-A FK-backfill of 80 source rows is enterprise ceremony for a one-developer codebase per Fowler worldview #11+12 with no named beneficiary. (d) Hans: OWID's entities table is for stable identity (country/state); a fuzzy-clustered dedup audit with `confidence_tier` is NOT a country-grade entity. Shipping the file invites the framing "a `/p/<person>` page must be coming" - Rosling Single-perspective bias. | SIGNED 2026-06-05 (user kickoff message: "Once Part A's verdict is settled, execute B2b.4.7 per that verdict."). |

### Fowler (Engineering) verdict block - PLAN TEXT

- **Should this exist?** Worldview #11 Delete-first: 30MB CSV for an artefact with zero named beneficiary = enterprise ceremony. Recommend deletion and stop.
- **Near-term behavioural change served?** None. B2b.5.x (already shipped #768-#772) moves biographic cols INLINE onto candidacy rows per section 21.3, eliminating the `dim_persons` join in F1 / X1a window. Audit cluster_id is operator-internal; not a citizen contract.
- **FK-orphan blocker (Path A from `/memories/session/b2b-4-7-blocker.md`)?** Becomes unnecessary. The 80 missing source_ids only matter at validator-time; if no CSV is emitted, no validation, no orphan.
- **Parity-gate handling?** Section 22.6 cross-format-parity is the safety oracle for DELETION of a CONSUMED parquet. For a zero-consumer parquet, the safety statement is the audit trail: "grep frontend/ for unique cols -> 0 hits; biographic dim_persons cols migrate inline in B2b.5.x candidacies.csv". This row is removed from the parity catalogue in B2b.4.8 distillation.
- **Refactorings in play:** Delete-first; Strangler-fig (deferred death of `dim_persons` inside F1 reader-flip and X1b parquet-delete).
- **Two-hat sequence:** structural-only (deletion of a planned-emit row + scope-change ledger). No behavioural commit.

### Hans (Governance) verdict block - PLAN TEXT

- **Governance question answered?** Does the citizen benefit from a person-level entity table on disk? Only if `/p/<person>` pages or career-arc charts exist; neither is on the citizen roadmap.
- **Right shape?** Per-candidacy attributes (age-at-poll, profession-at-poll) CHANGE per election; they belong ON the candidacy row by candidacy convention. OWID precedent: their `entities` table carries STABLE identity (country code + name); per-observation attributes ride on the observation row. yen-gov's `persons.parquet` is a fuzzy-clustered DEDUP audit with `confidence_tier` - not a country-grade entity.
- **Methodology breaks?** `cluster_id` + `confidence_tier` ARE the methodology-break receipts of the person-dedup process. Internal to the ingest pipeline; not chartable; not citable on a citizen page.
- **Rosling instinct most at risk:** **Single-perspective.** Shipping a 30MB person registry invites "there must be a `/p/<person>` page coming" when none is scoped. Publish-because-it-exists is the bias OWID's discipline guards against.
- **Recommended framing:** docs/architecture/backend/canonical-writer.md "Datapoint reingest" section to record: "persons.parquet is a backend-internal dedup audit; no citizen-facing CSV sibling; dies with the rest of the taxonomy parquets in X1b. Cluster receipts, when needed, are operator-rebuildable from the ingest run."
- **Trap to avoid:** Future career-tracking is a different feature with a different (smaller, deduplicated) entity surface; designing now is speculative.

### Steelman of the opposing view (per debate-mode contract)

Strongest case FOR shipping (Option A1): (1) Holy Law #3 contracts-before-logic mandates declaring file_class; (2) Path-A source-backfill is independently valuable for ledger hygiene; (3) cross-format-parity gate is deletion-safety; (4) OWID-pure entities are universal.

Rebuttals: (1) Contracts before logic != contracts for hypothetical logic; the near-term logic (B2b.5.x) reads candidacies inline. (2) Source-backfill belongs under a different chunk (entity-source.csv hygiene), not under B2b.4.7. (3) "No consumer + dim_persons migrates inline" IS the deletion-safety statement; the parity gate exists for consumed parquets, not abandoned ones. (4) OWID divergence is first-class with a written reason per `/memories/patterns.md`; this divergence has one (fuzzy-clustered audit is not stable-entity shape).

Verdict: convergent DROP. No genuine fork remains; STOP-AND-SURFACE is satisfied by this scope-change row with user-kickoff signoff.

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
| B2b.4.4 `election_events.csv` from `election_events.parquet` (339 rows; ECI `state_code` -> LGD slug re-key on emit) | - | cross-format-parity | #704 | MERGED |
| B2b.4.5 `indicator_topic_tags.csv` from `indicator_topic_tags.parquet` (45 rows; M:N; FK `topic_id` -> `topics.csv`; FK `artifact_id` -> `variables.csv` when `artifact_kind = 'indicator'`) | B2a.2 + B2a.4 (already MERGED) | cross-format-parity | #706 | MERGED |
| B2b.4.6 `entities/ac_crosswalk.csv` from `ac_crosswalk.parquet` (4113 rows; `state_code` -> LGD slug; `source_id` FK to `entities/source.csv`) | - | cross-format-parity | #708 | MERGED |
| B2b.4.7 `entities/person.csv` from `persons.parquet` (430630 rows; heaviest emit; `source_id` FK to `entities/source.csv`) | - | N/A (see section 0) | #774 | DROPPED (2026-06-05; Fowler+Hans converged debate verdict; see section 0 Scope-change ledger; no citizen consumer of persons.parquet unique cols, biographic dim_persons cols migrate inline via B2b.5.x candidacies.csv #768-#772) |
| B2b.4.8 close sub-sub-plan: flip parent B2b.4 row to MERGED + stamp closure PR + distil per-file emit map into [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md) "Datapoint reingest" section + archive this file to `docs/archive/plans/` | B2b.4.1..B2b.4.6 + B2b.4.7-DROPPED | docs-review | #775 | IN-FLIGHT |

Parallel-safe groups (each `cross-format-parity` runs against a different on-disk parquet with no shared write target):

- Wave A (no blockers): B2b.4.1, B2b.4.2, B2b.4.3, B2b.4.4, B2b.4.5, B2b.4.6. **B2b.4.7 DROPPED 2026-06-05** (see section 0). All six are independent (no cross-row FK between siblings; the FK targets they need are entity / catalogue CSVs already on disk from B2a).
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

### B2b.4.7 entities/person (DROPPED 2026-06-05)

**Status:** DROPPED per section 0 Scope-change ledger; Fowler+Hans converged verdict. Original intent was to project `datasets/taxonomy/persons.parquet` (430k rows, 7 cols) verbatim into `datasets/data/entities/person.csv`.

**Reason summary (full reasoning in section 0):** `persons.parquet` is a backend-internal dedup AUDIT registry (cols `confidence_tier`, `evidence_note_md`, `cluster_id`, `merged_candidacy_count`) with ZERO live frontend readers. The biographic registry the 6 frontend `dim_persons` JOIN sites actually read is `datasets/elections/dim_persons.parquet` (separate file with `sex`, `age`, `education`, `profession` cols), whose biographic cols migrate INLINE to candidacies.csv per section 21.3 (already shipped via B2b.5.x #768-#772). Minting `entities/person.csv` would be enterprise ceremony for an artefact with no named beneficiary (Fowler worldview #11) and would invite the Single-perspective framing "a `/p/<person>` page must be coming" (Hans / Rosling) when none is scoped.

**Path-A FK-orphan backfill (`/memories/session/b2b-4-7-blocker.md`):** ALSO DROPPED. The 80 missing source_ids in `persons.parquet` only matter at validator-time; with no CSV emit, no validation, no orphan.

**Deletion-safety for X1b:** When X1b deletes `datasets/taxonomy/persons.parquet`, the safety statement is the audit trail in this section + the canonical-writer.md "Datapoint reingest" section + the grep receipt (0 frontend consumers of unique cols), NOT a cross-format-parity test against a CSV sibling. Cluster receipts, when ever needed, are operator-rebuildable from `backend/yen_gov/canonical/persons_seed.py`.

### B2b.4.8 closure

- Extend [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md) "Datapoint reingest" section with each of B2b.4.1..B2b.4.7 emitter module + source parquet + parity-gate path.
- Flip the parent B2b.4 ledger row (in [TODO/20260604-b2b-reingest-subplan.md](../../../TODO/20260604-b2b-reingest-subplan.md)) to MERGED in this same PR and stamp the closure PR number.
- Archive this file to `docs/archive/plans/20260604-b2b4-taxonomy-subplan.md` with a "Plan complete" block per [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md).
- Confirm: every taxonomy parquet has an emitted CSV sibling whose `cross-format-parity` gate is green; B2b.4's deletion-safety is established for X1b.

## Contract invariants (inherited from grandparent 22.4)

1. Provenance FK mandatory: every emitted row that carries `source_id` resolves in `entities/source.csv` (CLAUDE.md Holy Law #9). After 2026-06-05 DROP of B2b.4.7, the six emitted CSVs either carry `source_id` (ac_crosswalk, methodology_breaks, election_events via `sources: []` note) or are pure reference (facet_axes, state_tiers, indicator_topic_tags) where `source_id` is omitted. `persons.parquet` is no longer in scope (see section 0); its 80-source FK-orphan condition becomes operator-internal noise that dies in X1b without ever needing a backfill.
2. No `datetime.now` in content columns (CLAUDE.md anti-pattern). All six emitted parquets are static reference / mapping data; no run-time stamps to launder.
3. Deterministic sort + stable CSV serialisation: ORDER BY PK on emit so diffs read clean.
4. Typed read at the boundary: every emitted CSV file class has its column contract in `datasets/data/_schema/columns.json`; the validator runs at write time AND the reader's `read_csv(columns=...)` map is generated from that single home (23.2).
5. No mocks: parity tests read REAL parquet + REAL CSV from disk (Holy Law #7); the gate skips cleanly only if a family is absent.

## Tracking

The parent sub-plan row B2b.4 is `DEFERRED-TO-SUBPLAN -> TODO/20260604-b2b4-taxonomy-subplan.md` in the SAME PR that lands this sub-sub-plan. Sub-row status updates land inside each B2b.4.x PR per grandparent 24.3.

## See also

- Parent sub-plan: [TODO/20260604-b2b-reingest-subplan.md](../../../TODO/20260604-b2b-reingest-subplan.md).
- Grandparent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) (sections 7, 20.4, 21.6, 22.4, 22.5, 22.6, 23.2, 24.5).
- B2a sub-plan precedent: [docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md](20260604-b2a-csv-catalogue-subplan.md).
- B1 sub-plan precedent: [docs/archive/plans/20260604-b1-csv-writer-subplan.md](20260604-b1-csv-writer-subplan.md).
- Canonical writer doc: [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md).
- Sub-plan spawning rule: grandparent section 24.5.

## Plan complete

Closed 2026-06-05 via PR #775. All rows resolved (six MERGED + one DROPPED + closure):

- B2b.4.1 `methodology_breaks` -> [datasets/data/methodology_breaks.csv](../../../datasets/data/methodology_breaks.csv); emitter `backend/yen_gov/canonical/reingest/methodology_breaks.py`. PR #698.
- B2b.4.2 `facet_axes` -> [datasets/data/facet_axes.csv](../../../datasets/data/facet_axes.csv); emitter `reingest/facet_axes.py`. PR #700.
- B2b.4.3 `state_tiers` -> [datasets/data/state_tiers.csv](../../../datasets/data/state_tiers.csv); emitter `reingest/state_tiers.py`. PR #702. ECI state_code -> LGD slug re-key.
- B2b.4.4 `election_events` -> [datasets/data/election_events.csv](../../../datasets/data/election_events.csv); emitter `reingest/election_events.py`. PR #704. ECI state_code -> LGD slug re-key.
- B2b.4.5 `indicator_topic_tags` -> [datasets/data/indicator_topic_tags.csv](../../../datasets/data/indicator_topic_tags.csv); emitter `reingest/indicator_topic_tags.py`. PR #706. M:N FK.
- B2b.4.6 `ac_crosswalk` -> [datasets/data/entities/ac_crosswalk.csv](../../../datasets/data/entities/ac_crosswalk.csv); emitter `reingest/ac_crosswalk.py`. PR #708. ECI state_code -> LGD slug re-key.
- B2b.4.7 `persons` -> **DROPPED** per Fowler+Hans converged verdict (section 0). PR #774. `datasets/taxonomy/persons.parquet` is a dedup-audit registry with zero frontend consumers; cross-format-parity gate is N/A for the unconsumed parquet; biographic dim_persons cols migrate inline via B2b.5.x. Path-A FK-orphan backfill also dropped.
- B2b.4.8 closure -> THIS PR (#775). Parent B2b.4 row flipped to MERGED; canonical-writer.md `## Taxonomy datapoint reingest (B2b.4)` section appended; this file archived to `docs/archive/plans/20260604-b2b4-taxonomy-subplan.md`; the X1b deletion-safety statement for `datasets/taxonomy/persons.parquet` (zero-consumer + audit trail) is the canonical-writer doc + section 0 of this archived plan.

Distillation map per [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md):

- Per-file emit map -> [docs/architecture/backend/canonical-writer.md](../../architecture/backend/canonical-writer.md) `## Taxonomy datapoint reingest (B2b.4)` section.
- Fowler+Hans converged verdict for B2b.4.7 DROP -> section 0 of this archived plan + section 0 retained verbatim as the operator's reference.
- Per-PR audit trail -> stays in this archived plan.

Plan-doc remains as the audit ledger; do not edit further. New work starts a new plan-doc.

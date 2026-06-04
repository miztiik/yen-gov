# B2a sub-plan - emit entity + catalogue CSVs from existing taxonomy

**Last Updated**: 2026-06-04
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk B2a
**Status**: IN-FLIGHT (opened 2026-06-04)
**Authority**: Hans + Max (data shape, identity derivation) / Gregor (FK contract, write-order) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk B2a reads as one row in the parent Execution Ledger but expands into eight distinct emit deliverables (one per file class) with their own source-of-truth taxonomy artifact, their own FK ordering constraint, and in some cases their own identity-derivation fork (source_id derivation per CLAUDE.md section 12; topic parent walk for `variables.topic`; concept FK per F6). Each emit is a small writer that reads ONE existing taxonomy artifact under `datasets/taxonomy/` and writes ONE CSV under `datasets/data/` via `csv_writer.write_csv(...)` against the file class declared in `datasets/data/_schema/columns.json`.

Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first) and parent plan section 24.5, the right shape is a thin parent row + this sub-plan. Same shape B1 followed (PRs #629-#670 via sub-plan).

## Scope

In scope: building `backend/yen_gov/canonical/seed/` (or equivalent home) emitters that read existing `datasets/taxonomy/*.{parquet,json}` and write the eight file classes:

1. `datasets/data/entities/source.csv` - FK target for everything else; MUST emit first.
2. `datasets/data/topics.csv` - parent-pointer tree.
3. `datasets/data/concepts.csv` - F6 one-per-concept identity.
4. `datasets/data/variables.csv` - indicator catalogue (FKs to concepts + topics + source).
5. `datasets/data/entities/geo.csv` - LGD admin ladder.
6. `datasets/data/entities/electoral.csv` - ECI AC + PC entities per delim year.
7. `datasets/data/entities/electoral_lgd_xwalk.csv` - decay-receipt overlap crosswalk.
8. `datasets/data/entities/party.csv` - party identity (party_id sole canonical key, plan section 20.3).

Out of scope (other chunks):

- B2b: per-family datapoint reingest (the actual `datapoints/<entity_kind>/<variable_id>.csv` rows from socio-economic source data).
- Office + holder entities (plan section 20.4): they belong to a later term-shape chunk after B2b; not part of B2a's catalogue scope.
- Reader flip (X1a) + parquet delete (X1b): writer-only here; parquet survives.

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| B2a.1 source.csv from `taxonomy/sources.parquet` (+ `derive_source_id` reused per CLAUDE.md section 12) | - | fk-validator | #673 | MERGED |
| B2a.2 topics.csv from `taxonomy/topics.json` (parent-pointer flatten) | - | fk-validator | #675 | MERGED |
| B2a.3 concepts.csv from `taxonomy/concepts.json` | - | fk-validator | - | TODO |
| B2a.4 variables.csv from `taxonomy/indicators.json` (FKs to B2a.1 + B2a.2 + B2a.3) | B2a.1, B2a.2, B2a.3 | fk-validator | - | TODO |
| B2a.5 entities/geo.csv from `taxonomy/lgd_states.json` + `taxonomy/lgd_districts.json` | - | fk-validator | - | TODO |
| B2a.6 entities/electoral.csv from `taxonomy/lgd_acs.json` + `taxonomy/lgd_pcs.json` (FK to B2a.5 `state`) | B2a.5 | fk-validator | - | TODO |
| B2a.7 entities/electoral_lgd_xwalk.csv from `taxonomy/lgd_ac_pc_district_map.json` (FK to B2a.5 + B2a.6) | B2a.5, B2a.6 | fk-validator | - | TODO |
| B2a.8 entities/party.csv from `taxonomy/parties.json` | - | fk-validator | - | TODO |
| B2a.9 close sub-plan: parent B2a row -> MERGED + stamp final PR# + distil into [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md); archive this file to `docs/archive/plans/` | B2a.1..B2a.8 | docs-review | - | TODO |

Parallel-safe groups (independent inputs + the FK predecessor merged):

- Wave A (no blockers): B2a.1, B2a.2, B2a.3, B2a.5, B2a.8.
- Wave B (after Wave A): B2a.4 (needs .1 + .2 + .3), B2a.6 (needs .5).
- Wave C (after Wave B): B2a.7 (needs .5 + .6).
- Closure: B2a.9.

## Per-sub-row notes

### B2a.1 source.csv

- Read `datasets/taxonomy/sources.parquet`. Project to the five retained columns per `columns.json` (`source_id, owner, title, vintage, url`). All four content columns are nullable per plan section 7 (O3).
- `source_id` MUST be derived via `backend.yen_gov.canonical.citation.derive_source_id` - never hand-authored (CLAUDE.md Holy Law #9, section 12).
- Drop the legacy columns dropped in plan section 7 (license, confidence_tier, is_issuing_authority, verification_method, notes, citation_full, content_hash) - they have no home in the new contract.
- This is the FIRST emit because every other file class FK-targets `source.csv`.

### B2a.2 topics.csv

- Read `datasets/taxonomy/topics.json`. Emit `(topic, name, parent)` per the parent-pointer shape (plan section 3; pillars are roots with `parent IS NULL`).
- Self-FK on `parent` - the validator must accept the file under its own emit (load order: parents-before-children sort or post-validate).
- No `__` in any topic id (plan section 21.6).

### B2a.3 concepts.csv

- Read `datasets/taxonomy/concepts.json`. Emit `(concept_id, noun, unit_canonical, normalisation, entity_kinds, description)`.
- `normalisation` enum: `absolute | per_capita | share | rate | index`.
- `entity_kinds` is space-joined kinds list (e.g. `"state district"`) per columns.json string dtype.

### B2a.4 variables.csv

- Read `datasets/taxonomy/indicators.json`. Emit the 11 columns per `columns.json` (8 canonical + 3 precomputed for yen-ask grounding per plan section 20.10: `time_min, time_max, entity_kinds`).
- `concept_id` FK -> B2a.3; `topic` FK -> B2a.2; `source_id` FK -> B2a.1 (default display source only; per-row provenance rides datapoints in B2b).
- `time_min` / `time_max` / `entity_kinds`: in B2a they may be `NULL` (datapoints do not yet exist); B2b backfills as part of reingest. The columns.json declares them nullable so an empty value is contract-legal.
- No grain prefix on `indicator_id` (plan F6 / ADR-0044).

### B2a.5 entities/geo.csv

- Read `datasets/taxonomy/lgd_states.json` + `datasets/taxonomy/lgd_districts.json`.
- Emit `country` row (`IN`), then `state` rows (state_id, name, parent=`IN`), then `district` rows (district_id, name, parent=state_id).
- `aliases` column carries the pipe-delimited alias list per plan section 20.10 (yen-ask grounding); seed with ECI state code aliases (e.g. `S22` for Tamil Nadu) lifted from `lgd_states.json` if present, otherwise NULL.
- v1 freezes `entity_kind` at `country | state | district` per columns.json notes; sub-district + village admissible but not emitted (no current consumer).

### B2a.6 entities/electoral.csv

- Read `datasets/taxonomy/lgd_acs.json` + `datasets/taxonomy/lgd_pcs.json`.
- `state` FK -> B2a.5 geo `entity_id` (the LGD state code, e.g. `S22`-shaped).
- `parent`: AC -> its PC of the same `delim_year`; PC -> its state. Plan section 3 + 21.3.
- `reservation` enum: `GEN | SC | ST`.
- 2008 delimitation only in v1 (no 2026 rows yet); future delim years are append-rows-never-overwrite (plan section 3).

### B2a.7 entities/electoral_lgd_xwalk.csv

- Read `datasets/taxonomy/lgd_ac_pc_district_map.json`.
- Composite PK `(electoral_id, lgd_district_id, delim_year)` per columns.json.
- `boundary_snapshot` is the LGD vintage the overlap was computed against - the decay receipt (plan section 20.5).
- `overlap_kind` enum: `wholly_inside | majority | partial`.

### B2a.8 entities/party.csv

- Read `datasets/taxonomy/parties.json`. Emit `(party_id, short, full, eci_codes, brand_colour, symbol_asset, wikipedia)`.
- `party_id` is sole canonical key (plan section 20.3). `eci_codes` is a descriptive multi-value attribute, NOT a join key (pipe-delimited).
- `symbol_asset` is the static SVG asset id under `frontend/public/icons/` (plan section 21.10); MAY be NULL for parties whose symbol is not yet sanitised.

### B2a.9 closure

- Extend `docs/architecture/backend/canonical-writer.md` with a "Seed emitters" section listing the eight file classes + their source taxonomy artifacts.
- Flip parent B2a ledger row to MERGED and stamp the closure PR number.
- Archive this sub-plan to `docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md` with a "Plan complete" block (per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md)).

## Contract invariants (inherited from parent 22.4)

1. Provenance FK mandatory: every entity/catalogue file that carries `source_id` (variables.csv) FK-targets `entities/source.csv` (CLAUDE.md Holy Law #9).
2. LGD/ECI key separation: `entities/electoral.csv` MUST NOT carry a district FK; the only meeting point is `entities/electoral_lgd_xwalk.csv` (plan F3 / 20.5).
3. One-indicator-per-concept: every variables.csv row carries a `concept_id` FK to concepts.csv (plan F6); `check-overlap` may be re-run as a post-emit audit.
4. Schema-per-file typed: emits MUST go through `csv_writer.write_csv(file_class=...)` which validates against `columns.json` - never an ad-hoc `open(..., "w").write(",".join(...))`.
5. Static-first deterministic read path: deterministic sort by the file class's PK columns; no `datetime.now` in any content column (vintage on source.csv carries the publisher edition, not wall-clock).

## Gates (inherited from parent 22.6)

- `fk-validator`: each sub-row's PR runs `csv_validator.validate_csv(path)` over the emitted file and (where applicable) over its FK predecessors; FK miss + enum miss + sort drift + `__` rejection all fail the gate.
- `docs-review`: closure (B2a.9) ships the distilled section in `canonical-writer.md`.

## Definition of Done per sub-row (CLAUDE.md section 9 + parent 22.3)

Each sub-row's PR: emitted CSV is the SOLE source of truth for that file class going forward (parquet sibling under `datasets/taxonomy/` survives until X1b) + own gate green + full suite green at merge + ASCII-only + relative POSIX paths + no `[DEBUG]` + no new hardcoding + no new mocks + sub-row ledger flipped to MERGED with PR# stamped in the same PR.

## Open questions

None at sub-plan open. The eight emits are mechanical lifts under typed contracts (`columns.json` + `csv_writer` + `csv_validator` from B1) - all design forks for these file classes were resolved in parent plan sections 3, 7, 20.1, 20.3, 20.4, 20.5, 21.3, 21.6, 23.2.

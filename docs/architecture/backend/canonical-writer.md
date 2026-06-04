# Canonical CSV writer + validator (`yen_gov.canonical.csv_writer` + `csv_validator`)

**Last Updated**: 2026-06-04

The canonical CSV writer is the sole entry point that persists observation rows into the long-format CSV store under `datasets/data/` (and `datasets/elections/**`). It is the write seam referenced by Holy Law #2 ("backend is the only writer to `datasets/`") and the contract surface every re-pointed ingest (B1.4-B1.6 waves) funnels through, replacing the historical `core/io.write_artifact` meadow-tier path.

Distilled from sub-plan [docs/archive/plans/20260604-b1-csv-writer-subplan.md](../../archive/plans/20260604-b1-csv-writer-subplan.md) (sub-rows B1.1..B1.7, PRs #629-B1.7-closure) on 2026-06-04.

> The legacy Parquet writer at `backend/yen_gov/canonical/writer.py` (see [writer.md](writer.md)) survives in-tree until grandparent chunk B3 deletes it. Until then both writers coexist; new ingest re-points emit CSV via `csv_writer.write_csv`, never via the legacy `core/io.write_artifact` path.

## Purpose

- Emit one row per observation into the canonical long-format CSV files under `datasets/data/datapoints/<class>/<variable_id>.csv` and per-election `datasets/elections/{assembly,parliament}/state=<key>/election=<id>/{candidacies,summary}.csv` per [csv-column-contract.md](../data/csv-column-contract.md).
- Enforce the per-file-class column contract (`datasets/data/_schema/columns.json`) at write time: header order, dtype, nullability, deterministic sort, `__` ban, UTF-8 + LF + trailing newline + no BOM.
- Enforce cross-file integrity at read time: FK existence (`source_id` to `entities/source.csv` per Holy Law #9; `concept_id` to `concepts.csv` per ADR-0044 one-indicator-per-concept; `entity_id` to declared entity file), closed-enum membership, datapoint-filename equals `<variable_id>.csv`.
- Preserve the skip-write-if-equal optimisation from `core/io.write_artifact` (value-level row-list compare) so re-running ingest leaves a clean `git status`.

## Three-module surface

| Module | Role | Public API |
| --- | --- | --- |
| `yen_gov.canonical.csv_columns` (B1.1, PR #629) | Loads + caches the column contract from `datasets/data/_schema/columns.json`; validates the contract itself against `_schema/columns.schema.json` (D6 escape-hatch retained per grandparent plan section 8). | `load_columns()`, `file_class_for(path)` |
| `yen_gov.canonical.csv_writer` (B1.2, PR #631) | Sole CSV emission point. Strict on shape (header, dtype, nullability, sort, filename `__` ban). | `write_csv(*, path, file_class, rows) -> Path` |
| `yen_gov.canonical.csv_validator` (B1.3, PR #633) | Read-time cross-file integrity check. Strict on FK + closed-enum + sort + filename-equals-variable_id. No mocks (Holy Law #7); caller owns `repo_root` so fixtures stage under `tmp_path` (CLAUDE.md anti-pattern: validators MUST NOT walk the real on-disk corpus from pytest). | `validate_csv(*, path, file_class, repo_root) -> None` |

Division of labour: the writer is strict on per-row shape; the validator is strict on cross-file integrity. Anything that needs sibling-file presence (FK targets, datapoint-filename-equals-id) lives in the validator because the writer cannot assume sibling files exist yet during a partial re-ingest.

## Contract invariants enforced

Inherited from grandparent plan section 22.4 and CLAUDE.md Holy Laws #3, #6, #9:

1. **Provenance FK mandatory.** Every datapoint + candidacy row carries `source_id` -> `datasets/data/entities/source.csv` (validator-enforced).
2. **One-indicator-per-concept.** Each `variable_id` in `variables.csv` binds to one `concept_id` -> `concepts.csv` (validator-enforced FK).
3. **LGD/ECI key separation preserved.** The writer never invents a shared parent; election rows key on ECI codes per existing parser output, observation rows key on LGD ids per the entity file declared by the file class.
4. **Schema-per-file typed.** Callers pass `file_class` explicitly; there is no `read_csv_auto` round-trip. The writer is the strict half of the same typed-read contract F1 codegen will materialise on the frontend.
5. **Static-first deterministic read.** Rows sorted by the file class's PK columns in declaration order; no `datetime.now` in content columns; UTF-8 + LF + trailing newline + no BOM.
6. **Double-underscore ban.** Filenames containing `__` are rejected at write time (grandparent plan section 21.6 / 21.12).

## Re-point pattern for ingest callers

The B1.4-B1.6 waves re-pointed ~17 surviving `core/io.write_artifact` call-sites onto `csv_writer.write_csv`. The uniform shape for any future re-point:

1. Identify the canonical CSV file class the meadow JSON corresponds to (see [csv-column-contract.md section 3](../data/csv-column-contract.md)).
2. Build rows as `list[dict]` keyed by the declared columns; derive `source_id` via `backend.yen_gov.canonical.citation.derive_source_id` (never hand-author).
3. Call `write_csv(path=datapoints/<class>/<variable_id>.csv, file_class=..., rows=...)`.
4. During the B1 window the legacy `write_artifact` call MAY stay in place alongside the new CSV emit (whichever keeps the per-family gate green); deletion is deferred to grandparent chunk B3. Record the alongside choice in the sub-row's PR body.

**Alongside-NEITHER carve-out.** When a `write_artifact` site emits operator state (e.g. `datasets/elections/_inventory.json`) or a per-election shape that is one of N inputs to a downstream aggregator (B2a-owned: `entities/*.csv`, per-election `candidacies.csv` / `summary.csv`), no canonical CSV file class fits. Leave the legacy call in place, record the rationale in the sub-row PR body + sub-plan addendum, and pass `docs-review` instead of `writer-unit` + `suite-green`. Precedents: B1.6.4 (#664), B1.6.5 (#666), B1.6.6 (#668), B1.6.7 (#669) - all four alongside-NEITHER under sub-plan B1.6, all emit operator inventory or downstream-aggregator shapes.

## Seed emitters (B2a, PRs #673-#_pending_)

Sub-plan [docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md](../../archive/plans/20260604-b2a-csv-catalogue-subplan.md) delivered eight one-shot emitters under `backend/yen_gov/canonical/seed/` that lift the existing taxonomy artifacts under `datasets/taxonomy/` into the canonical CSV catalogue rows every downstream reader (B2b datapoint reingest, F1 frontend loaders, YA yen-ask grounding) joins against. Each emitter reads ONE taxonomy artifact and writes ONE CSV file class via `csv_writer.write_csv`; the validator (`csv_validator.validate_csv`) enforces FK + enum + sort across the emitted files.

| Emitter module | Reads | Emits | File class | PR |
| --- | --- | --- | --- | --- |
| `seed/source_csv.py` | `datasets/taxonomy/sources.parquet` | `datasets/data/entities/source.csv` | `entities/source.csv` (5 cols; 6 legacy cols dropped per plan section 7) | #673 |
| `seed/topics_csv.py` | `datasets/taxonomy/topics.json` | `datasets/data/topics.csv` | `topics.csv` (parent-pointer tree; pillars are roots) | #675 |
| `seed/concepts_csv.py` | `datasets/taxonomy/concepts.json` | `datasets/data/concepts.csv` | `concepts.csv` (F6 one-per-concept identity) | #677 |
| `seed/variables_csv.py` | `datasets/taxonomy/indicators.json` | `datasets/data/variables.csv` | `variables.csv` (FKs to source + topics + concepts; 11 cols incl. 3 yen-ask grounding columns nullable in B2a) | #680 |
| `seed/geo_csv.py` | `datasets/taxonomy/lgd_states.json` + `lgd_districts.json` | `datasets/data/entities/geo.csv` | `entities/geo.csv` (country -> state -> district ladder; `aliases` pipe-delimited) | #678 |
| `seed/electoral_csv.py` | `datasets/taxonomy/lgd_acs.json` + `lgd_pcs.json` | `datasets/data/entities/electoral.csv` | `entities/electoral.csv` (FK `state` -> geo; AC parent is PC of same `delim_year`) | #682 |
| `seed/electoral_lgd_xwalk_csv.py` | `datasets/taxonomy/lgd_ac_pc_district_map.json` | `datasets/data/entities/electoral_lgd_xwalk.csv` | `entities/electoral_lgd_xwalk.csv` (composite PK; `boundary_snapshot` carries the decay receipt per plan section 20.5) | #684 |
| `seed/party_csv.py` | `datasets/taxonomy/parties.json` | `datasets/data/entities/party.csv` | `entities/party.csv` (`party_id` sole canonical key per plan section 20.3; `eci_codes` is descriptive, not a join key) | #686 |

Each emitter is paired with `backend/tests/test_seed_<name>_csv.py` covering: deterministic sort, FK existence under the file class's predecessor (geo before electoral, source + topics + concepts before variables), enum membership, and `__` ban. A sibling `_run_<name>_csv.py` shim per emitter is the operator-facing runner invoked when refreshing the catalogue.

### Identity-derivation forks resolved

- **`source_id`** is re-derived inside `seed/source_csv.py` via `canonical.citation.derive_source_id` (chicken-and-egg seed path); downstream callers (B2b reingest) MUST use `citation.lookup_source_id` against the emitted CSV, never re-derive.
- **`topic.parent`** is a self-FK; emit order sorts parents-before-children so the validator passes without a deferred-FK pass.
- **`variables.concept_id`** binds to `concepts.csv` per ADR-0044 one-indicator-per-concept; `check-overlap` may be re-run as a post-emit audit (see canonical-writer `## Re-point pattern` for the binding rule on B2b ingest).
- **`variables.time_min` / `time_max` / `entity_kinds`** are nullable at B2a (no datapoints yet) and back-filled by B2b reingest per plan section 20.10.
- **`electoral.parent`** uses AC -> PC-of-same-delim_year, PC -> state; the LGD/ECI key separation invariant (#3 above) means `entities/electoral.csv` carries NO district FK - the only meeting point is `entities/electoral_lgd_xwalk.csv`.

### Parquet sibling lifecycle

Each emitter targets a CSV under `datasets/data/`; the legacy parquet sibling under `datasets/taxonomy/` survives until grandparent chunk X1b deletes it. During the B2a -> X1a -> X1b window both formats coexist; new readers MUST consume the CSV, never the parquet.

## Test surfaces

| Test | What it pins |
| --- | --- |
| `backend/tests/test_csv_writer.py` | Happy-path emit, dtype coercion, sort determinism, `__` rejection, null vs empty-string distinction, skip-write-if-equal. |
| `backend/tests/test_csv_validator.py` | FK miss, enum miss, sort drift, `__` rejection, missing `source_id`. `tmp_path` fixtures only - never walks the real corpus. |
| Per-family `test_<source>_csv_repoint.py` (one per B1.4-B1.6 wave PR) | Row-builder helper + `write_csv` round-trip for that source's file class. |
| `backend/tests/test_seed_<name>_csv.py` (one per B2a emitter) | Deterministic sort, FK existence under predecessor file class, enum membership, `__` ban. |

## Known follow-ups deliberately deferred

These surfaced during B1 execution and are recorded here so future agents do not re-discover them:

- **Per-indicator facet columns** (grandparent plan section 21.6). Writer + validator both reject undeclared columns today. Both surfaces will relax together when the first facet ingest (likely under B2b or a later family re-ingest) needs it.
- **Wall-clock-in-content-columns detector** (grandparent plan 22.6 fk-validator gate calls it out). A defensible detector needs a content-column taxonomy that `columns.json` does not yet carry. Land alongside the first ingest that would benefit.
- **Null-vs-empty-string distinction for string columns** (writer module docstring notes this). B1.2 emits `None` as the empty CSV field uniformly; a richer encoding will land if a downstream consumer needs to distinguish.
- **Parquet writer + `core/io.write_artifact` deletion.** Both survive in-tree until grandparent chunk B3. New code MUST NOT call either; the import-allowlist pattern from PR-SYM-6f is the model for B3's enforcement test.

## See also

- [../data/csv-column-contract.md](../data/csv-column-contract.md) - the binding column spec (D-DOC0, PR #627).
- [docs/archive/plans/20260604-b1-csv-writer-subplan.md](../../archive/plans/20260604-b1-csv-writer-subplan.md) - the sub-plan that delivered this writer + validator (B1.1..B1.7).
- [docs/archive/plans/20260604-b1.4-iced-repoint-subplan.md](../../archive/plans/20260604-b1.4-iced-repoint-subplan.md) - wave 1 (iced_*) per-family re-point precedent (PRs #634-#644).
- [docs/archive/plans/20260604-b1.5-rbi-repoint-subplan.md](../../archive/plans/20260604-b1.5-rbi-repoint-subplan.md) - wave 2 (rbi_*) precedent (PRs #645-#656).
- [docs/archive/plans/20260604-b1.6-misc-repoint-subplan.md](../../archive/plans/20260604-b1.6-misc-repoint-subplan.md) - wave 3 (misc) precedent including four alongside-NEITHER carve-outs (PRs #657-#669).
- [docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md](../../archive/plans/20260604-b2a-csv-catalogue-subplan.md) - the eight seed emitters (B2a.1..B2a.8, PRs #673-#686).
- [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) sections 22 (execution model), 23.1 (deletion blast radius), 24.5 (sub-plan spawning).
- [writer.md](writer.md) - legacy Parquet writer (survives until grandparent chunk B3).
- [ADR-0032](../decisions/0032-sources-citation-ledger.md) - `source_id` FK requirement.
- [ADR-0042](../decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) - `vintage` semantics for `derive_source_id`.
- [ADR-0044](../decisions/0044-grain-over-entity.md) - one-indicator-per-concept, no grain prefix on `variable_id`.
- [CLAUDE.md](../../../CLAUDE.md) Holy Laws #3, #6, #7, #9; sections 9 (DoD), 12 (provenance).

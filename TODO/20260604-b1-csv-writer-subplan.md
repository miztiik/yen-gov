# B1 sub-plan - CSV writer + per-file validator + ingest re-point

**Last Updated**: 2026-06-04
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk B1
**Status**: ACTIVE (spawned per parent plan section 24.5; parent B1 row flipped to DEFERRED-TO-SUBPLAN on PR merge)
**Authority**: Hans + Max (data shape, columns.json) / Gregor (contract surface, writer API) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk B1 reads as one row in the parent Execution Ledger but expands into five distinct deliverables with non-trivial design forks of their own:

1. `datasets/data/_schema/columns.json` - the machine-readable column contract (the on-disk artifact the `csv-column-contract.md` doc materialises).
2. `backend/yen_gov/canonical/csv_writer.py` - the new SOLE CSV emission point (replaces the parquet path of `canonical/writer.py` for the post-rip world; parquet writer survives until B3).
3. Per-file CSV validator (write-time): dtype + nullability + FK + closed-enum + double-underscore ban + deterministic-sort + `source_id` mandatory.
4. Re-point of the ~17 surviving `sources/*/ingest.py` (+ `pipeline/`, `cli.py`, `canonical/adapters/`) call-sites off `core/io.write_artifact` onto `csv_writer` so B3 can delete `core/io.write_artifact` whole.
5. Tests: writer unit + fk-validator + (light) drift assertion `writer-emitted header == columns.json` per file class.

Re-pointing 17+ callers in one PR is mechanical churn that swamps the new-code review; per CLAUDE.md correction-level discipline (4+ files structural -> propose breakdown first) and parent plan 24.5, the right shape is a thin parent row + this sub-plan.

## Scope

In scope: everything inside `backend/yen_gov/canonical/` for CSV writing, `backend/yen_gov/canonical/csv_validator.py` (new), `datasets/data/_schema/columns.json` (new), every `core/io.write_artifact` call-site re-pointed onto the new writer.

Out of scope (other chunks): emitting actual entity/catalogue CSVs from existing taxonomy (B2a); reingesting families (B2b); deleting parquet writers + `core/io.write_artifact` + dead schemas (B3); deleting fetch code (B4); the cutover (X1a/X1b).

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| B1.1 columns.json artifact (+ loader) | - | schema-of-schemas-valid | #629 | MERGED |
| B1.2 csv_writer.py core API + writer unit test | B1.1 | writer-unit | #631 | MERGED |
| B1.3 csv_validator.py (fk + enum + determinism + `__` ban) + validator unit test | B1.1 | fk-validator | #633 | MERGED |
| B1.4 ingest re-point wave 1 (`sources/iced_*`) | B1.2, B1.3 | suite-green | _pending_ | DEFERRED-TO-SUBPLAN ([TODO/20260604-b1.4-iced-repoint-subplan.md](20260604-b1.4-iced-repoint-subplan.md) per grandparent plan section 24.5; flips to MERGED when sub-row B1.4.X closes the sub-plan) |
| B1.5 ingest re-point wave 2 (`sources/rbi_*`) | B1.2, B1.3 | suite-green | - | TODO |
| B1.6 ingest re-point wave 3 (`sources/cea_*`, `sources/datagovin_ogd`, `sources/india_geodata`, `pipeline/*`, `cli.py`, `canonical/adapters/eci_ae_panel.py`) | B1.2, B1.3 | suite-green | - | TODO |
| B1.7 close sub-plan: parent B1 row -> MERGED + stamp final PR# + distil into [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md); archive this file to `docs/archive/plans/` | B1.4, B1.5, B1.6 | docs-review | - | TODO |

Waves 1-3 are parallel-safe (independent file sets, same writer API surface).

## Per-sub-row notes

### B1.1 columns.json artifact

- Authoritative spec lives in [docs/architecture/data/csv-column-contract.md](../docs/architecture/data/csv-column-contract.md) sections 2-4. The on-disk artifact MUST match that spec field-for-field (drift = bug).
- File class keys are globs against the canonical tree (e.g. `datasets/data/variables.csv`, `datasets/data/datapoints/geo/*.csv`, `datasets/elections/assembly/state=*/election=*/candidacies.csv`).
- Per-column shape: `{name, dtype, nullable, pk?, fk?, enum?, derived?}`. Enums are inlined here (single source per csv-column-contract.md section 4).
- A tiny `_schema/columns.schema.json` (JSON-Schema-of-the-contract) is retained (per plan section 8 / D6 escape-hatch) and validates the columns.json itself at load.
- Loader API: `from yen_gov.canonical.csv_columns import load_columns, file_class_for(path)` (consumed by B1.2 + B1.3 + downstream codegen in F1).

### B1.2 csv_writer.py

- API: `write_csv(*, path: Path, file_class: str, rows: Iterable[dict]) -> Path`. Sole canonical CSV emission point.
- Responsibilities: validate file_class is known; sort deterministically by the file_class's pk columns; coerce dtypes against `columns.json`; raise on extra / missing / disallowed-null columns; reject `__` in filename; emit UTF-8 + LF + trailing newline + no BOM.
- DELIBERATELY does NOT mutate `value` semantics: null stays null (labelled gap, F1).
- The skip-write-if-equal optimisation from `core/io.write_artifact` is preserved (value-level compare on parsed rows) so re-running ingest produces a clean git status.
- Test: `backend/tests/test_csv_writer.py` covers happy-path emit + dtype coercion + sort determinism + `__` rejection + null vs empty-string distinction.

### B1.3 csv_validator.py

- API: `validate_csv(path: Path) -> None` (read existing file + check against `columns.json` file class).
- Enforces beyond dtype: `source_id` FK existence in `entities/source.csv`; `concept_id` FK in `concepts.csv`; `entity_id` FK in declared entity file; closed-enum membership; no wall-clock value in content; deterministic sort; filename equals `<variable_id>.csv` for datapoints; no `__`.
- Test: `backend/tests/test_csv_validator.py` covers FK miss, enum miss, sort drift, `__` rejection, missing `source_id`. Use `tmp_path` fixtures - NEVER walks the real corpus (CLAUDE.md anti-pattern).

### B1.4-B1.6 ingest re-point waves

Per parent plan section 23.1, the existing callers emit JSON via `core/io.write_artifact` to meadow-tier paths. The post-rip world has no meadow tier (parent B4 deletes it). For each caller:

- Identify the canonical CSV file class the meadow JSON corresponds to (per csv-column-contract.md section 3).
- Replace the `write_artifact(path=meadow.json, ...)` call with `write_csv(path=datapoints/<class>/<variable_id>.csv, file_class=..., rows=...)`.
- DORMANT in B1: the OLD parquet writer (`canonical/writer.py`) is still the production canonical emit at main; the re-pointed ingest paths emit CSV alongside (or instead of) the meadow JSON. Whichever is cheaper to keep the gate green per family - record the choice in the sub-row's PR body.
- Each wave PR lists the touched files + per-file before/after of the write call.

### B1.7 closure

- Distil the writer + validator architecture into a new `docs/architecture/backend/canonical-writer.md` (single doc, CSV-only; deletes any inbound link to `canonical/writer.py` Parquet behaviour).
- Flip parent B1 ledger row to MERGED and stamp the closure PR number.
- Archive this sub-plan to `docs/archive/plans/20260604-b1-csv-writer-subplan.md` with a "Plan complete" block (per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md)).

## Contract invariants (inherited from parent 22.4)

1. Provenance FK mandatory (`source_id` on every datapoint + candidacy row).
2. LGD/ECI key separation (writer never invents a shared parent).
3. One-indicator-per-concept (`concept_id` FK enforced by B1.3).
4. Schema-per-file typed: explicit `read_csv(columns=...)` map generated from `columns.json`; `read_csv_auto` banned; the writer is the strict half of this contract.
5. Static-first deterministic read path: deterministic sort, no `datetime.now` in content columns.

## Gates (inherited from parent 22.6)

- `writer-unit`: B1.2 unit test green.
- `fk-validator`: B1.3 unit test green; covers FK + enum + `__` + null-vs-empty + sort.
- `suite-green`: full `pytest -q` green for each re-point wave PR.
- `docs-review`: B1.7 closure PR ships the distilled `canonical-writer.md`.

## Definition of Done per sub-row (CLAUDE.md section 9 + parent 22.3)

Each sub-row's PR: own gate green + full suite green at merge + ASCII-only + relative POSIX paths + no `[DEBUG]` + no new hardcoding + no new mocks + sub-row ledger flipped to MERGED with PR# stamped in the same PR.

## See also

- Parent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) sections 22 (execution model), 23 (file-level ripple corrections), 24.5 (sub-plan spawning protocol).
- [docs/architecture/data/csv-column-contract.md](../docs/architecture/data/csv-column-contract.md) - the binding column spec (D-DOC0, PR #627).
- [CLAUDE.md](../CLAUDE.md) Holy Laws #3, #6, #9, #10; sections 9 (DoD), 12 (provenance).
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - the closure ritual B1.7 follows.

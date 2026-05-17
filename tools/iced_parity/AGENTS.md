# AGENTS.md — tools/iced_parity

**Last Updated**: 2026-05-17

Module map for the ICED value-parity oracle. Canonical design and rationale live in [TODO/20260517-iced-bulk-ingest-and-parity-oracle.md](../../TODO/20260517-iced-bulk-ingest-and-parity-oracle.md) (Phase 2). Schemas: [parity-observation.schema.json](../../datasets/schemas/parity-observation.schema.json) and [indicators-parity.schema.json](../../datasets/schemas/indicators-parity.schema.json).

## Invariants

- **Self-contained.** No imports from `backend/` (CLAUDE.md §4). Pure stdlib + the existing ICED client (wired in step 7).
- **Not in pytest.** The oracle hits a live external service; per resolution §2(#4) and the 2026-05-16 validator-descope lesson, that belongs in operator tooling, not `pytest`. Unit tests for the pure helpers (`classify`, `sample`, `ledger`, `banner`) live in `backend/tests/test_iced_parity.py` because they are CODE correctness, not live oracle behaviour.
- **Append-only ledger.** `ledger.append()` is the only write path; no rewrite, no compaction. `git log datasets/parity/in/<id>.ledger.jsonl` is the history substrate per resolution §5(b).
- **Six-value status enum.** Never collapse `diverge / revised_upstream / missing_upstream / missing_ours` into a boolean (rejected-design #9 / Hans §6.d).
- **Inline `upstream_parity` carries verdict only, never cell-level data.** Full divergent cells stay on the ledger (rejected-design #1).
- **Per-record provenance.** Every ledger line carries `upstream_url + sampled_at`. No file-level `sources[]` because the file is JSONL, not JSON, and out of the yen_gov validator's Tier B scope by construction.

## Module map

| File          | Purpose                                                                                  |
| ------------- | ---------------------------------------------------------------------------------------- |
| `models.py`   | `ParityObservation` dataclass + `Status` literal — mirrors the schema field-for-field.   |
| `classify.py` | Pure six-value classifier. Implements resolution §5(a).                                  |
| `sample.py`   | Pure cell-sampling strategies (`all_cells`, `stratified_sample`) over an artifact dict.  |
| `ledger.py`   | Append-only JSONL read/append + `last_upstream_value` lookup for `prior_upstream` wiring.|
| `probe.py`    | `UpstreamFetcher` Protocol — boundary for the live HTTP fetcher (wired in step 7).       |
| `banner.py`   | Pure summariser → the `upstream_parity` object spliced into the `divergence` slot.       |

Step 7 will add `client.py` (the live `IcedApiFetcher`), `cli.py` (the operator entry point), and the splice-from-ledger wiring inside `backend/yen_gov/core/io.py::write_artifact`.

# Backend `pipeline/` — Composition & Orchestration

**Last Updated**: 2026-05-09

`backend/yen_gov/pipeline/` is the glue between adapters and emitted artifacts. It owns the order of fetches, threads partywise→constituencywise data via `party_lookup`, aggregates per-AC results into a state-level `ResultSummary`, and is the entry point for the `yen-gov` CLI.

This page covers the bottom-up composition rule (district → state → country) and the orchestrator's fail-loud policy.

## Modules

| File | Responsibility |
| ---- | -------------- |
| [`compose.py`](../../../backend/yen_gov/pipeline/compose.py) | Pure functions over adapter outputs. No I/O. `party_lookup_from_partywise(snapshot)`, `compose_result_summary(*, election, state, body, partywise, constituencies, sources)`. |
| [`run.py`](../../../backend/yen_gov/pipeline/run.py) | The orchestrator. Owns the order of fetches and the on-disk layout. `run_state_slice(*, event_id, state_code, output_dir, schema_dir, fetcher, top_n, collapse_others) -> RunResult`. |
| [`reference.py`](../../../backend/yen_gov/pipeline/reference.py) | Reference-data scrape (districts, constituencies) via the Wikipedia adapter. |
| [`yen_gov/cli.py`](../../../backend/yen_gov/cli.py) | Typer commands (`yen-gov run`, `yen-gov reference`, `yen-gov validate`) wiring `ProcessingConfig` + `Fetcher` + the orchestrator. |

## Bottom-up composition

Pipeline orchestration is strictly bottom-up. The smallest unit that produces an emit-worthy artifact is the **constituency** (an Assembly Constituency in a state election, a Parliamentary Constituency in a Lok Sabha election). District scaffolding is taxonomy, not an election unit.

1. **Constituency level** — for one `(election, state, body, eci_no)`, fetch + parse + validate + emit one `result.constituency.schema.json` artifact under `datasets/elections/<event>/<state>/<body>/<eci_no>.json`.
2. **State level** — for one `(election, state)`, read the constituency artifacts produced by step 1, plus ECI's partywise summary, and emit one `result.summary.schema.json` artifact at the state level.
3. **Country level** — for one election event spanning multiple states, compose the state-level summaries into a national rollup. Schema for this artifact does not yet exist; it lands when first needed.

Hard rules:

- **Higher-level pipeline modules MUST NOT call a lower upstream directly.** State rollup reads constituency *artifacts* (the JSON files), not raw HTML. This makes each level independently re-runnable and testable.
- The artifact directory layout mirrors the hierarchy: `datasets/elections/<event>/<state>/<body>/...`. POSIX paths only (CLAUDE.md §2).
- Each level's emit step uses `core/io.py` to stamp `$schema`, `$schema_version`, and `sources` (per [provenance contract](../decisions/0002-provenance-as-sources-list.md)). State-level `sources` is the union of contributing constituency artifacts' `sources` plus the ECI summary URL.

### Composition rationale (bottom-up)

- **Each layer is independently testable.** State rollup tests use fixture constituency JSONs, not network.
- **Re-running a single constituency** (e.g. parser bug discovered) doesn't require re-running the whole state. State rollup re-runs are cheap (read 234 files).
- **Provenance composes naturally.** State rollup's `sources` array carries every contributing URL.
- Matches the user's mental model and makes the "all states + country" extension straightforward.

Acknowledged costs: the disk artifact between levels feels redundant in a single-shot run. Worth it for testability and re-runnability. Two passes (parse-then-rollup) means a state pipeline run touches the disk twice — negligible.

### Composition — alternatives considered

- **One big monolithic emit** that fetches everything, holds it in memory, and writes both constituency-level and state-level artifacts in one pass. Rejected: couples the levels; a state-rollup bug means re-fetching all constituencies; tests need network or a giant fixture.
- **Top-down**: state pipeline drives constituency fetches as sub-tasks. Rejected: same coupling problem; you can't unit-test state rollup without a constituency-fetching test double.
- **Sideways**: each level is a peer, with a separate orchestrator. Rejected as over-engineered for the current shape.

## Why composers are pure

`party_lookup_from_partywise` and `compose_result_summary` take dataclasses/models in and return models out. No HTTP, no disk, no environment. This makes them trivially testable (the unit tests in [`test_pipeline_compose.py`](../../../backend/tests/test_pipeline_compose.py) build a `PartywiseSnapshot` directly without parsing HTML) and keeps composition logic auditable as data, not behaviour.

## Why the orchestrator owns on-disk layout

`output_dir/parties.json`, `output_dir/result.summary.json`, `output_dir/results/<eci_no>.json`. The default in the CLI is `<root>/datasets/elections/<event>/<state>/`, but `run_state_slice` accepts `output_dir` directly so tests can run into `tmp_path`. The path convention is one decision in one file; changing it is a one-line CLI edit.

## Fail-loud whole-run

A single AC parse failure aborts the run with the underlying `ValueError` propagated. We deliberately do NOT collect failures and emit a partial summary; a `result.summary.json` that silently elides one or more constituencies would mislead downstream consumers (vote shares would be off by a few percent with no indication). Operators rerun the slice after fixing the upstream cause.

This complements the parser-level fail-loud behaviour from the [ECI](sources-eci.md) and [Wikipedia](sources-wikipedia.md) adapters.

## Composition trade-offs

`compose_result_summary` walks every kept candidate (top-N) plus IND, summing votes by `party_short`. When `processing.results.collapse_others` is true, votes that landed in `OthersBucket` are excluded from per-party totals. This is a conscious trade — `OthersBucket` loses per-party identity, so we can't recover it from the artifact. A consumer that needs exact party-level vote totals across the entire field must run the pipeline with `top_n_candidates >= max_candidates_per_AC`.

`totals.votes_polled` is always the true sum from each constituency's tfoot, so vote-share denominators are correct regardless of `top_n` / `collapse_others`. It is the per-party numerators that may be slightly low.

### Surfacing parties absent from partywise

A party that won zero seats does not always appear in the partywise table (depends on ECI's display threshold). If candidates from such a party show up in any AC, the composer adds an extra `PartyTotals` row with `seats_won=0` and the votes/contests it could measure. Without this, fringe-party votes vanish silently. Cost: that row's `party_full` is `None` (we don't have it from any source) and `party_eci_code` is `None`.

## Live smoke test, not a 234-AC integration test

[`test_pipeline_run_live.py`](../../../backend/tests/test_pipeline_run_live.py) exercises the full pipeline against ONE TN AC (Gummidipoondi, #1):

- 234 fetches per CI run is rude to ECI and slow.
- The orchestrator's loop is trivial; what we actually need to know is that the wiring works (partywise → lookup → constituencywise → mapper → compose → write_artifact → schema validation). One AC exercises every link in the chain.
- The full slice is operator-driven via `yen-gov run AcGenMay2026 S22`. It runs once per election, not on every CI build.

## Orchestrator design rationale

- Composers are pure functions — tests don't need a mock HTTP server or a fixture HTML page.
- A future `pipeline/run_country()` reuses `run_state_slice` per state. Country aggregation reuses `compose_result_summary` semantics.
- The CLI is thin — config → Fetcher → orchestrator. Adding a `--dry-run` or `--only-ac N` flag is a one-block change.

Acknowledged costs:

- No parallel fetching. 234 sequential GETs from one Fetcher take a few minutes for a TN run. Acceptable for a one-shot post-result run; revisit if we add live event tracking.
- No resume support. A run that fails on AC #150 must re-fetch ACs #1..#149 (the bytes are still in `.runtime/raw/` for debugging but the orchestrator does not consult them per [no fetch cache](../decisions/0003-no-fetch-cache.md)).

## Orchestrator — alternatives considered

- **Put `compose_result_summary` in `core/models.py` as a classmethod on `ResultSummary`**. Rejected: composition is *behaviour over multiple models*, not a constructor. `core/` stays a passive data layer.
- **Have the orchestrator return failures as a list rather than raising**. Rejected: see "Fail-loud". A partial summary is more dangerous than no summary.
- **Parallel fetches via `asyncio` / `httpx.AsyncClient`**. Rejected for now: the rate-limit profile of `results.eci.gov.in` is undocumented and we'd risk getting blocked. Sequential is safe; revisit with measured throughput.
- **Resume-from-checkpoint (write a manifest, re-read on retry)**. Rejected for now: another contract surface to design and version. The 234-AC TN run completes in a few minutes; the cost of restarting is small. Worth revisiting at country scale.
- **Drop "parties absent from partywise" rows rather than synthesising them**. Rejected: silent data loss. Better a row with `party_eci_code=None` (which the schema permits) than a missing slice of the vote.

## See also

- [Backend overview](overview.md), [Core](core.md), [ECI adapter](sources-eci.md), [Wikipedia adapter](sources-wikipedia.md), [SQLite emitter](emit-sqlite.md)
- [How to run the pipeline](../../how-to/run-the-pipeline.md)
- [`docs/concepts/result-aggregation.md`](../../concepts/result-aggregation.md)
- [ADR-0002 — Provenance as a list of `{url, fetched_at}` entries](../decisions/0002-provenance-as-sources-list.md)

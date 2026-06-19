# CLI reference: `ingest`

**Last Updated**: 2026-06-19

Command reference for the `ingest` sub-app (`python -m yen_gov ingest <verb>`) plus the author-time `pre-flight-ingest` gate. The subsystem design + the honesty doctrine live in [docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md); the operator cookbook is [docs/how-to/add-a-new-data-source.md](../how-to/add-a-new-data-source.md). All commands run in the LOCAL pipeline only (Holy Law #2); production never invokes them.

The repo root defaults to the current working directory; run from the repo root or pass `--root .`. Examples assume the editable install (`pip install -e backend`) resolves `python -m yen_gov`.

## `ingest run`

Drive an indicator (primary) or an adapter scope into the canonical CSV store. Prints a one-line fan-out echo BEFORE the work, then a per-indicator summary.

```
python -m yen_gov ingest run --indicator total-fertility-rate
python -m yen_gov ingest run --indicator total-fertility-rate --adapter rbi-handbook
python -m yen_gov ingest run --adapter rbi-handbook
python -m yen_gov ingest run --indicator total-fertility-rate --staging-dir ./.staging/rbi
python -m yen_gov ingest run --indicator total-fertility-rate --resume
```

| Flag | Short | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `--indicator` | `-i` | text | - | The indicator to ingest (primary work address). Resolved to its owning adapter(s) via the derived index. |
| `--adapter` | `-a` | text | - | Restrict to this adapter (scope filter). Given ALONE, runs every indicator that adapter owns. |
| `--root` | `-r` | dir | cwd | Repo root (anchors the catalogue + emitted datapoints). |
| `--staging-dir` | `-s` | dir | none | Directory of operator-staged source files (RBI Handbook XLSX, or a fetchable cohort's flaky-TLS fallback). Required for operator-staged adapters. |
| `--resume` | | flag | off | Continue from the last completed checkpoint year (completed years skipped, remaining processed). A plain run is already idempotent with the same effect. |

At least one of `--indicator` / `--adapter` is required (exit code 2 otherwise). A bogus `--indicator`, an unknown `--adapter`, a registration-FK failure, a concept-compatibility mismatch, or an unsatisfied splice break-row gate all exit code 1 with a one-line error on stderr.

The fan-out echo is indicator-centric when an indicator is named (`total-fertility-rate <- [rbi-handbook 1971-2011]: running 1 adapter`) and adapter-centric for an adapter-only scope (`rbi-handbook -> [birth-rate, death-rate, ...]: running N indicators`). The year span is the EXISTING on-disk coverage; absent when nothing is on disk yet.

> Stage-window flags `--from STAGE` / `--to STAGE` appear in the plan's target architecture but are NOT shipped in this build (deferred). A run always executes the full preamble -> Fetch -> Enrich -> Publish flow.

## `ingest status`

Show per-indicator coverage: which `source_id` owns which year span (read off the emitted datapoints CSV) + the refresh cadence + last-checked staleness.

```
python -m yen_gov ingest status --indicator total-fertility-rate
```

| Flag | Short | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `--indicator` | `-i` | text | (required) | The indicator to report coverage + per-source year spans for. |
| `--root` | `-r` | dir | cwd | Repo root. |

Output names the owning adapter(s), the `update_period_days` cadence + `last_checked` when a checkpoint exists, and one line per source (`<source_id> (<producer>): <year_min>-<year_max> (<N> observations)`). An indicator with nothing on disk yet reports `coverage: none yet`.

## `ingest clean`

Sweep stale ingest ephemera under the runtime base (`.runtime/` by default): `logs/<run_id>/` and `cache/ingest/<adapter_slug>/`. The committed year-checkpoint under `datasets/_ops/ingest-state/` is durable state and is NEVER touched (it lives outside the runtime base, which the cleaner asserts as a fail-loud guarantee).

```
python -m yen_gov ingest clean --dry-run
python -m yen_gov ingest clean --days 120
python -m yen_gov ingest clean --days 7 --force
```

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--days` | int | 90 | Remove ephemera older than N days. |
| `--force` | flag | off | Permit `--days` below the 90-day retention floor (an aggressive sweep). Without it, `--days < 90` aborts (exit code 2). |
| `--dry-run` | flag | off | List what WOULD be removed; mutate nothing. |
| `--root` | `-r` dir | cwd | Repo root. The `YEN_GOV_RUNTIME_DIR` env override wins when set. |

Age is the NEWEST mtime in an entry's subtree, so a long, still-active run is not swept by a stale top-level directory mtime. A target that escapes the runtime base (a stray `..` or a drive letter) aborts BEFORE any deletion. Set `YEN_GOV_RUNTIME_DIR` to sweep a relocated runtime base.

## `pre-flight-ingest`

The author-time design gate ([ADR-0046](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)). Run it when DESIGNING a new indicator, before writing any adapter - it batches the six mechanical checks a reviewer would otherwise apply by hand: concept-overlap, concept FK, grain-prefix, `update_period_days`, justification, `source_id` derivation.

```
python -m yen_gov pre-flight-ingest --proposal-file TODO/<slug>/proposal.json --report TODO/<slug>/report.json
```

A JSON `--proposal-file` is the canonical input; the per-field flags below are sugar that hydrate an in-memory proposal (the file always wins when both are supplied).

| Flag | Type | Meaning |
| --- | --- | --- |
| `--proposal-file` | file | JSON proposal (canonical input). |
| `--proposed-id` | text | Proposed `indicator_id`. |
| `--family` | text | Source family. |
| `--concept` | text | Proposed concept noun. |
| `--unit` | text | Canonical unit. |
| `--normalisation` | text | `absolute` / `per_capita` / `share` / ... |
| `--entity-kind` | text | Grain (`country` / `state` / `district` / ...). |
| `--source-producer` | text | Issuing-authority producer. |
| `--source-title` | text | Citizen-readable report title. |
| `--source-vintage` | text | Publisher edition / snapshot vintage. |
| `--update-period-days` | int | Publisher refresh cadence in days. |
| `--justification` | text | Non-empty rationale (>= 20 chars). |
| `--report` | file | Write the JSON report to this path (in addition to the stdout summary). |
| `--root` | `-r` dir | Repo root. |

Exit codes: `0` = pass (verdict `mint_new` / `upsert` / `add_facet`); `1` = soft-warn (verdict + at least one warning); `2` = hard-fail (verdict `abort`). There is NO override flag (Holy Law #5): an `abort` means fix the data or the proposal, not silence the gate.

## See also

- [docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md) - the subsystem design + honesty doctrine.
- [docs/how-to/add-a-new-data-source.md](../how-to/add-a-new-data-source.md) - the end-to-end cookbook.
- [docs/concepts/pre-flight-ingest.md](../concepts/pre-flight-ingest.md) - the six checks the gate enforces.
- [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md) - the three-stage doctrine.

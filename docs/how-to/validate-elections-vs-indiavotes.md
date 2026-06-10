# How to: validate elections vs IndiaVotes

**Last Updated**: 2026-06-10

This runbook explains how to run the one-shot offline parity oracle that
compares yen-gov's canonical per-state election results against IndiaVotes
scraped HTML. The tool itself lives at
[tools/elections_parity_indiavotes/](../../tools/elections_parity_indiavotes/);
this page is for the engineer who needs to RUN it. Design context lives in
the [PR-W1c row of the election experience overhaul plan](../../TODO/20260609-election-experience-overhaul-plan.md).

## When to run it

- A new state-event slice has just landed in `datasets/data/datapoints/electoral/`
  and you want to spot-check the winner / party / margin columns against an
  independent source before declaring data complete.
- A citizen-reported discrepancy on the elections surface needs triage --
  the oracle tells you fast whether yen-gov disagrees with the public
  consensus or with itself.
- You are working on the ingest path (TCPD adapter, ECI XLSX lift, etc.)
  and want a one-shot regression check.

**Never run this from CI.** This is operator tooling. See [the
README's "never CI" section](../../tools/elections_parity_indiavotes/README.md#politeness-rules).

## Prerequisites

A clean throwaway venv with three deps, kept OUT of the project venv so
its packages never leak into the citizen pipeline:

```pwsh
cd <path-to-yen-gov>
py -m venv .venv-parity
.\.venv-parity\Scripts\activate
pip install httpx beautifulsoup4 lxml
```

On macOS / Linux replace the activate line with `source .venv-parity/bin/activate`.

## Run

```pwsh
python tools/elections_parity_indiavotes/__main__.py `
  --event general-2024 `
  --state chhattisgarh `
  --output datasets/_ops/elections-parity-vs-indiavotes-2026-06-10.csv
```

Naming convention for the output: `elections-parity-vs-indiavotes-<YYYY-MM-DD>.csv`.
The `datasets/_ops/` directory is operator state; it is NOT citizen-facing
and is NOT inventoried (see [datasets/_ops/README.md](../../datasets/_ops/README.md)).

Expected stderr (live path):

```
[parity] reading yen-gov: datasets/data/datapoints/electoral/chhattisgarh_election_results.csv
[parity] yen-gov: 11 winner buckets for general-2024
[parity] fetching IndiaVotes for general-2024 / chhattisgarh (cache: datasets/ephemeral/indiavotes-snapshots)
[parity] IndiaVotes: parsed 11 winner rows from 1 page(s)
[parity] agreement: 100.0% across 11 distinct constituencies
[parity] wrote 22 rows -> datasets/_ops/elections-parity-vs-indiavotes-2026-06-10.csv
```

Two CSV rows per constituency (one per source) make every comparison
auditable in a spreadsheet.

## Review the CSV

Open the CSV. Sort by `agrees`. Three outcomes:

| `agrees` | What it means | What to do |
| --- | --- | --- |
| `true` | Both sides report the same normalised winning party for that seat. | Move on. |
| `false` with `delta_notes = "party mismatch"` | yen-gov and IndiaVotes disagree on the winning party for a constituency they both list. | Open an ingest-bug ticket. Do NOT patch the data by hand. |
| `false` with `delta_notes = "no yen-gov match"` / `"no indiavotes match"` | One side has a constituency the other does not. | Usually a stale URL template or a constituency-name normalisation drift. Triage before deciding. |

**Holy Law #5** ([CLAUDE.md section 1](../../CLAUDE.md#1-holy-laws-read-first-every-session)):
fix the yen-gov ingest, not the symptom. The oracle exists to surface ingest
bugs; do not stash IndiaVotes-shaped rows in `source.csv` and do not
hand-edit the canonical CSV.

## When IndiaVotes is unreachable

If the network probe fails (rate-limit, 5xx, DNS, etc.) the CLI exits with
code 2 and prints a hint. To validate the diff engine works end-to-end
against a synthetic fixture (the G1-EVIDENCE path), use:

```pwsh
python tools/elections_parity_indiavotes/__main__.py `
  --event general-2024 `
  --state chhattisgarh `
  --fixture-html tools/elections_parity_indiavotes/tests/fixtures/indiavotes-chhattisgarh-general-2024.html `
  --output datasets/_ops/elections-parity-vs-indiavotes-synthetic.csv
```

The fixture is a 3-row mini-table the tool's unit tests already exercise.
Synthetic-fixture parity is enough to validate the diff engine; live parity
is a SEPARATE oracle the operator runs when IndiaVotes is reachable.

## Cache management

The HTML cache lives under
`datasets/ephemeral/indiavotes-snapshots/<YYYY-MM-DD>/<event>/<state>/page-N.html`.
The `datasets/ephemeral/` tree is gitignored. Re-running the CLI within 7
days of a cache hit is zero-network. Pass `--force-refetch` to bypass the
cache window.

To wipe the cache (rarely necessary):

```pwsh
Remove-Item -Recurse -Force datasets/ephemeral/indiavotes-snapshots
```

## Politeness invariants

The tool hardcodes:

- 1 request per second, single-threaded.
- Citizen User-Agent (no yen-gov-tagged headers, no cookies).
- One state-event landing page per invocation (no recursive crawl).
- 7-day cache window so re-runs are cheap.

If you find yourself wanting to relax any of these to scale the oracle:
**don't**. Open an issue against the plan instead.

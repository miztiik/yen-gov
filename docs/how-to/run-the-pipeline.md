# How to run the pipeline

**Last Updated**: 2026-05-09

The yen-gov pipeline has two operator-facing CLI commands. Both live in `backend/yen_gov/cli.py` and are exposed via `python -m yen_gov`.

## Prerequisites

- Python 3.13+ with the backend installed: `pip install -e backend/`.
- A populated `config/processing.json` (the committed default works).
- Network access to `results.eci.gov.in` and `en.wikipedia.org`.

## `yen-gov reference <state>` — one-shot Wikipedia scrape

Populates the per-state reference triple (district list + AC list with reservation status) under `datasets/reference/in/states/<state>/`.

```sh
python -m yen_gov reference S22
# → datasets/reference/in/states/S22/districts.json       (38 districts)
# → datasets/reference/in/states/S22/constituencies.json  (234 ACs)
```

This command is run **once per state per delimitation cycle**. The data does not change between elections; rerun only when district boundaries or reservation status change.

Wikipedia requires a descriptive User-Agent (per their bot etiquette and [backend/sources-wikipedia.md](../architecture/backend/sources-wikipedia.md#user-agent)). The default UA is appropriate; override with `--user-agent` if you need to cite a different contact URL.

## `yen-gov run <event> <state>` — full result run

Fetches one ECI partywise page and N constituencywise pages, parses them, composes a state-level summary, and writes everything under `datasets/elections/<event>/<state>/`.

```sh
python -m yen_gov run AcGenMay2026 S22
# → datasets/elections/AcGenMay2026/S22/parties.json
# → datasets/elections/AcGenMay2026/S22/result.summary.json
# → datasets/elections/AcGenMay2026/S22/results/1.json … 234.json
```

Each constituency is fetched and emitted in order; a single AC failure aborts the run with the underlying `ValueError` (per [pipeline fail-loud policy](../architecture/backend/pipeline.md#fail-loud-whole-run)). Bytes for every URL are persisted under `.runtime/raw/eci/...` for offline debugging (per [ADR-0003](../architecture/decisions/0003-no-fetch-cache.md)) — but the orchestrator does not consult them on rerun.

The composer's reconciler (`reconcile_winners_against_partywise`) cross-checks per-AC winners against the partywise seat counts; a mismatch raises before any artifact is written. This catches both ECI page corruption and parser drift.

### Knobs

`config/processing.json` controls:
- `fetch.timeout_seconds`, `fetch.retry_attempts`, `fetch.retry_backoff_seconds`, `fetch.user_agent`
- `results.top_n_candidates` — how many candidates to keep per AC (rest collapse into `OthersBucket` when `collapse_others: true`).

## `yen-gov validate` — schema gate

After any pipeline run, validate the whole repo:

```sh
python -m yen_gov validate
# → validate: OK (0 issues)
```

This runs Tier A (schemas vs draft 2020-12 meta-schema + `x-version`/`x-changelog` invariants) and Tier B (every `*.json` under `datasets/` against its declared `$schema`). Per CLAUDE.md §11, both tiers must pass before merge.

## See also

- [backend/sources-eci.md](../architecture/backend/sources-eci.md) (ECI source adapter conventions)
- [backend/sources-wikipedia.md](../architecture/backend/sources-wikipedia.md) (Wikipedia source adapter conventions)
- [backend/pipeline.md](../architecture/backend/pipeline.md) (pipeline orchestration: composers, fail-loud, top-N trade-off)
- `docs/concepts/data-provenance.md` (what `sources` means in every emitted file)

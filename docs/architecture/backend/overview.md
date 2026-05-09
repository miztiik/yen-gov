# Backend Overview

**Last Updated**: 2026-05-09

The yen-gov backend is a local Python pipeline that fetches Indian election data from multiple upstreams (ECI, Wikipedia, …), validates it against the schemas in [`datasets/schemas/`](../../../datasets/schemas/), and writes JSON + SQLite artifacts under [`datasets/`](../../../datasets/). It is **not deployed** (CLAUDE.md Holy Law #1); the static GitHub Pages bundle reads what the backend has already written.

## Layered topology — `core` / `sources` / `pipeline` / `emit`

```
backend/yen_gov/
  core/        — reusable infrastructure (no upstream knowledge)
    http.py        httpx + tenacity client; reads timeout/retry/UA from config
    io.py          schema-stamped JSON artifact writer (POSIX paths, $schema/$schema_version)
    models.py      pydantic models that mirror datasets/schemas/ 1:1
    events.py      frozen-dataclass event types emitted at each pipeline stage
    logging.py     structured logger; writes to .runtime/logs/<run-id>/
  sources/     — one subpackage per upstream
    eci/           ECI-specific URL builders, HTML parsers, model adapters
    wikipedia/     Wikipedia-specific parsers
  pipeline/    — orchestration; composes sources via core
    compose.py     pure functions that combine adapter outputs
    run.py         run_state_slice orchestrator
    reference.py   reference-data scrape (districts, constituencies)
  emit/        — projections of validated JSON into derived artifacts
    sqlite.py      writes results.sqlite next to result.summary.json
```

The package details for each layer live in:

- [Core infrastructure](core.md) — `core/` modules and their contracts.
- [ECI source adapter](sources-eci.md) — the `sources/eci/` subpackage.
- [Wikipedia source adapter](sources-wikipedia.md) — the `sources/wikipedia/` subpackage.
- [Pipeline orchestration](pipeline.md) — composers, orchestrator, fail-loud policy.
- [SQLite emitter](emit-sqlite.md) — derived per-state `.sqlite` artifact.

## Dependency rules

The dependency direction is the same one CLAUDE.md §4 declares for the whole repo, restricted to backend layers:

- `sources/` MAY import from `core/` but NOT from `pipeline/` or other `sources/*`.
- `pipeline/` MAY import from `core/` and `sources/` but pipeline modules do not import each other except to compose upward.
- `core/` MUST NOT import from `sources/` or `pipeline/`.
- `emit/` MAY import from `core/` only. It reads what `pipeline/` wrote via the filesystem; a parser regression must not break the SQLite path and vice versa.
- Cross-source data passes through pydantic models defined in `core/models.py`, never through raw dicts or HTML strings.

These rules are the canonical home for *why* the package is shaped this way — see CLAUDE.md §4 for the project-wide formulation.

## Design rationale

The backend has to ingest from multiple upstreams (ECI HTML pages, Wikipedia, future state portals and open-data feeds), each with its own quirks (HTML structure, naming, identifier conventions). The operations on top — HTTP fetching with retry, writing schema-validated JSON, structured logging, modeled events — are the same regardless of upstream.

A flat module layout that mixes "how to talk to ECI" with "how to write a JSON artifact" forces rewrites every time a new upstream appears. The four-layer split keeps:

- **Adding a new upstream** to a single new `sources/<name>/` package; nothing else changes.
- **Tests for `core/`** upstream-agnostic and stable.
- **Pipeline orchestration** top-down and grep-able.
- **Blast radius** small: a bug in `sources/eci/` cannot regress Wikipedia parsing.

The cost is a handful of layers' worth of ceremony for code that could otherwise live in one module. We pay it because we already know we need ≥2 upstreams for the first slice and the pattern scales without rework.

## Alternatives considered

- **Flat `backend/yen_gov/` with module-per-feature.** Rejected: forces upstream-specific code to leak into shared utilities the moment a second upstream is added.
- **Plugin architecture with entry-points discovery.** Rejected as premature: we have a fixed, known set of upstreams. Adding entry-point discovery now is speculative complexity (CLAUDE.md anti-pattern: building for hypothetical future requirements).
- **Single `sources/` module with one file per upstream.** Rejected: each upstream needs multiple files (URL builders, parsers, model adapters, fixtures). A subpackage scales; a single file becomes a 1000-line dumping ground.

## See also

- [Core infrastructure](core.md), [ECI adapter](sources-eci.md), [Wikipedia adapter](sources-wikipedia.md), [Pipeline](pipeline.md), [SQLite emitter](emit-sqlite.md)
- [Data flow](../data-flow.md) — the system-level picture this fits into.
- CLAUDE.md §4 — repo-wide layer & dependency rules.

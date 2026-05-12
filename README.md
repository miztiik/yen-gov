# yen-gov

> Indian election data — schema-first ingestion, processing, and static visualization. First slice: Tamil Nadu Legislative Assembly election, May 2026.

Engineering contract lives in [CLAUDE.md](CLAUDE.md). The full upstream standard it derives from is in [docs/reference/documentation-structure.md](docs/reference/documentation-structure.md); CLAUDE.md wins for this repo.

## Runtime model

Hybrid, asymmetric:

- **Production**: static-first. Frontend ships to GitHub Pages. No production server. All compute happens at build/data-generation time; runtime is browser only.
- **Local development / data pipeline**: a Python pipeline under `backend/` fetches, parses, validates, and emits data into `datasets/`. The frontend's Vite build copies `datasets/` into the static bundle.

The frontend MUST NOT depend on a live backend in production. Anything the UI needs at runtime ships in the bundle (JSON, optionally SQLite-via-WASM).

## Repository layout

```
docs/                # Canonical knowledge (Diataxis tiers)
datasets/            # Schemas, reference data, generated election outputs
  schemas/           #   8 JSON Schemas (draft 2020-12), versioned per CLAUDE.md §11
  reference/         #   Slowly-changing reference data (states, districts, etc.)
  events/            #   Event metadata (event id, scope/body, covered states)
  elections/         #   Per-event/per-state outputs (results, summaries, parties, SQLite)
config/              # Tunable knobs only (e.g. processing.json)
backend/             # Python pipeline + tests + FastAPI dev server
  yen_gov/           #   Package: validate.py, cli.py, ...
  tests/             #   pytest
.runtime/            # Ephemeral run state, cached HTML, logs           [gitignored]
TODO/                # Working scratchpads (non-authoritative)
frontend/            # Static GitHub Pages app                          [not yet]
tools/               # Standalone dev/ops tooling                       [not yet]
```

Folders marked `[not yet]` are created only when real code is about to land in them — no empty stubs.

## Quick start (current state — Phase 0)

Run two-tier validation across the repo:

```sh
PYTHONPATH=backend python -m yen_gov validate
```

Run the test suite:

```sh
PYTHONPATH=backend python -m pytest backend/tests -q
```

Both should exit 0.

Re-render the data inventory after each ingest:

```sh
PYTHONPATH=backend python -m yen_gov coverage
```

Writes [`docs/reference/data-inventory.md`](docs/reference/data-inventory.md) — the auto-generated checkpoint of which (state, event) slices have been ingested. The file is the contract; the catalogue at [`datasets/reference/in/election-events.json`](datasets/reference/in/election-events.json) is the spec; divergences surface in the inventory's "Inconsistencies" section.

## Status

**Phase 0 complete** (2026-05-08): schemas, validator, CLI, default `processing.json`, Tamil Nadu seed, architecture docs.

**Next**: Phase 0.5 — Wikipedia/ECI scraper to populate the rest of `datasets/reference/in/states.json` plus districts, constituencies, and parties for Tamil Nadu. See [`TODO/PLAN.md`](TODO/PLAN.md).

## Documentation

Canonical docs live under `docs/` and follow the Diataxis tiers (architecture / how-to / concepts / reference) with a 3-level depth cap.

- [`docs/architecture/data-flow.md`](docs/architecture/data-flow.md) — how data moves through the system.
- [`docs/architecture/data-model.md`](docs/architecture/data-model.md) — entities and relationships.
- [`docs/concepts/data-provenance.md`](docs/concepts/data-provenance.md) — every data file carries a `sources` array of `{url, fetched_at}` entries.
- [`docs/reference/schemas.md`](docs/reference/schemas.md) — current schemas with versions.
- [`docs/reference/data-inventory.md`](docs/reference/data-inventory.md) — auto-generated election data coverage checkpoint.
- [`docs/reference/identifiers.md`](docs/reference/identifiers.md) — ECI/ISO/LGD code conventions.
- [`docs/reference/documentation-structure.md`](docs/reference/documentation-structure.md) — upstream documentation standard.

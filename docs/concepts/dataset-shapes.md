# Dataset Shapes — Canonical vs Delivered

**Last Updated**: 2026-05-12

This doc explains *why* yen-gov ships the same election data in multiple physical shapes, and which shape serves which audience. It is the canonical home for the "should this be one big CSV or many small JSONs?" question — anyone proposing to consolidate or split should read this first.

## The question this answers

"For a static-first civic-data site that wants to be useful to citizens, journalists, AND psephology researchers, what is the right physical shape of published election results?"

## The three-tier policy

One source of truth, three derived deliveries. Each tier is generated deterministically from the previous; never authored independently.

| Tier | Shape | Path | Audience | Loader |
| --- | --- | --- | --- | --- |
| **1 — Canonical** | Per-constituency JSON (~1.8 KB each) | `datasets/elections/<E>/<S>/results/<eci_no>.json` | Citizen detail page; PR reviewer; schema validator | Frontend fetch, one file per AC |
| **2 — State runtime delivery** | Per-state summary JSON (~30–80 KB) | `datasets/elections/<E>/<S>/result.summary.json` | State-hub table, choropleth map, party totals | Frontend fetch, one file per (event, state) |
| **3 — Researcher delivery** | Per-state long-format CSV (the per-state SQLite sibling retired in PR-R.3, 2026-05-19; researcher SQL now runs against the canonical Parquet store via DuckDB-WASM on `/explore`) | `results.csv` next to the JSON | Journalists, academics, ADR/Lokniti/TCPD-style users | Direct download, or DuckDB-WASM on `/explore` |

Tier 1 is the contract surface (schema-validated, `x-version`-tracked, see [data-provenance.md](data-provenance.md) and CLAUDE.md §11). Tiers 2 and 3 are derived projections — they regenerate when Tier 1 changes, never the other way around.

## Why per-constituency JSON wins as canonical

Three independent arguments converge:

1. **PR-review ergonomics.** A single-AC re-ingest produces a 1-file, ~30-line JSON diff that a reviewer can read in 30 seconds. A wide CSV-per-election or one giant SQLite turns the same change into an opaque blob diff or a 1-row diff inside a 290-row file. Granularity at rest minimises cognitive load at review time.
2. **Schema evolution.** `result.constituency.schema.json` will keep getting `x-version` bumps. Migrating 290 small files is resumable and parallelisable; rewriting one big file per election is all-or-nothing and merge-conflict-prone when multiple state ingests land in parallel.
3. **Citizen-tier latency.** The detail page (estimated ~70% of traffic) reads ONE constituency. Shipping a 500 KB state bundle to render ~1.8 KB of content tanks LCP on patchy 4G. One small file beats one big file when the user only needs one row.

## Why we *also* publish per-election bundles (Tier 2)

Random-access JSON breaks down the moment a view needs the whole state:

- State results hub (searchable table of all ACs)
- Choropleth map coloured by winning party
- Party-wise totals card
- Cross-cycle "my seat" comparison (N small fetches, but parallelisable over HTTP/2)

For the first three, the static site cannot fan out to 290 fetches per page load. It needs an aggregate. `result.summary.json` is that aggregate — already emitted today.

## Why we *also* publish CSV + SQLite (Tier 3)

Indian psephology distributes data as CSV-per-election. TCPD-IED, Lokniti-CSDS, and ADR all ship this way. A researcher who has to `wget` 290 JSON files and write a glue script is being asked to do work that ten lines of `pandas.read_csv` should cover. Refusing to publish bulk shapes makes yen-gov a website-only product, not a data publisher.

The CSV is **long-format**, one row per candidate, because:

- It round-trips losslessly back to the JSON (every per-AC field is present on every row).
- `df.pivot` is one line in pandas; collapsing long → wide is cheap, the inverse is lossy.
- It matches Lokniti's convention. Wide-with-top-N-as-columns is friendlier for spreadsheets but pre-decides what "top-N" means at emit time.

The SQLite tier was retired in PR-R.3 (TODO row `1.8e`, 2026-05-19). Researchers who want SQL get it through DuckDB-WASM in the browser (or any DuckDB client locally) against the canonical Parquet store — strictly better than the per-state SQLite shards because it spans every event and state in one connection. See [`docs/architecture/data/canonical-store.md`](../architecture/data/canonical-store.md) and [ADR-0030](../architecture/decisions/0030-canonical-store-duckdb-wasm.md).

## Shapes we deliberately reject

- **One CSV per election as canonical.** Breaks random-access for the citizen tier; opaque diffs; loses nested `sources[]` and the candidate array (CSV is flat).
- **Per-state SQLite shards as a researcher artifact** (retired 2026-05-19, PR-R.3). The original argument was "queryable, byte-stable, small." The canonical Parquet store + DuckDB-WASM gives the same query surface across every event and state in one connection, while the per-state shards forced researchers to `ATTACH` 41 files just to do the kind of cross-state question SQL was meant to make easy.
- **One giant SQLite shipped to the browser as the primary loader.** sql.js + httpvfs is ~1 MB of WASM before any data loads. Only worth it past ~500 MB total or when ad-hoc SQL queries are the primary UX. Even at that point, DuckDB-WASM over Parquet (our current path) is the better answer.
- **Per-AC SQLite.** Defeats SQLite's purpose (cross-row queries) for no gain.

## Scale envelope

| Horizon | Files (approx) | Bytes (approx) |
| --- | --- | --- |
| Today (21 elections ingested) | 4,475 per-AC JSON + 21 summaries + 21 SQLite | ~8.7 MB JSON, ~5 MB SQLite |
| Full 30-state × ~5 cycles × ~150 ACs | ~22,500 per-AC JSON + ~150 summaries + ~150 SQLite | ~50 MB JSON, ~30 MB SQLite |
| + Lok Sabha cycles | +~3,000 per-AC JSON | +~6 MB |

GitHub Pages serves whatever the repo commits; git handles 25k small files comfortably; Vite's `vite-plugin-static-copy` ships them. The CDN edge cost is identical to one big file. Cognitive cost differs — see PR-review point above.

## Future work (tracked here, not yet implemented)

- **Repo-level merged SQLite** (`datasets/elections.sqlite`) — built at release time by `ATTACH`-ing every per-state DB. Useful for "compare BJP share in TN across three cycles" researcher queries. Defer until a real consumer asks; per-state SQLite + per-state CSV cover today's audience.
- **Parquet alongside CSV** — useful once researcher uptake confirms the CSV is being downloaded at scale. Cheap to add to the emitter, but premature without a user.

## See also

- [data-provenance.md](data-provenance.md) — `sources[]` policy, applies to every shape.
- [`docs/architecture/backend/emit-csv.md`](../architecture/backend/emit-csv.md) — CSV emitter design.
- [`docs/architecture/data/canonical-store.md`](../architecture/data/canonical-store.md) + [ADR-0030](../architecture/decisions/0030-canonical-store-duckdb-wasm.md) — the Parquet + DuckDB-WASM path that replaced the per-state SQLite shards.
- [ADR-0019](../architecture/decisions/0019-dataset-topology-and-column-discipline.md) — column naming.
- CLAUDE.md §11–§12 — schema versioning and provenance.

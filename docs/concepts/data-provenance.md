# Data Provenance

**Last Updated**: 2026-05-18

> Every observation yen-gov publishes carries a `source_id` foreign key to one row in `datasets/taxonomy/sources.parquet`. This is non-negotiable (CLAUDE.md Holy Law #9, §12). The mechanism is the canonical sources table, adopted from OWID (CLAUDE.md §0a "The One Rule") plus a small set of yen-gov extensions.

## The contract

`datasets/taxonomy/sources.parquet` is the **one** sources table for the whole repo. Every observation row in every Parquet family — `elections/`, `energy/`, `demography/`, `fiscal/`, `education/`, `health/`, … — carries a `source_id` that points at exactly one row in that table.

There is no per-shard sources array. There is no embedded URL on an observation row. There is no second provenance table for a particular family. One table, one FK, one shape.

This is enforced at the writer (UPSERT into DuckDB with a FK guard) and at the consumer (frontend contract tests reject any observation with NULL or dangling `source_id`).

## The sources table

The full schema lives in [`docs/architecture/data/canonical-store.md` §5](../architecture/data/canonical-store.md#5-sources-schema-d5). Citizen-facing fields (OWID `origin.*`, verbatim):

| Column | Meaning |
| --- | --- |
| `url_main` | Landing / about page URL the citizen can open. |
| `url_download` | Direct download URL (same as `url_main` for HTML scrapes). |
| `producer` | Publisher organisation — e.g. "Election Commission of India", "Reserve Bank of India". |
| `citation_full` | Full citation string suitable for the footer of a chart. |
| `date_accessed` | UTC date of first read. |
| `license` | License code (e.g. `OGL-IN-1.0`, `CC-BY-4.0`, `unknown-public`, `internal`). |
| `vintage` | The source's own period label (e.g. "FY 2024-25"), preserved verbatim. |

yen-gov extensions (NOT OWID):

| Column | Meaning |
| --- | --- |
| `source_id` (PK) | Stable identifier; the FK target on every observation row. |
| `content_hash` | sha256 of fetched bytes. Idempotency anchor: re-running ingest with byte-identical upstream is a no-op. |
| `first_fetched_at` | RFC 3339 UTC, **immutable**, citizen-facing — when the pipeline first saw this URL. |
| `last_seen_at` | RFC 3339 UTC, **mutable** telemetry — when re-fetch last confirmed the URL still resolves. Never citizen-facing. |
| `confidence_tier` | `gold` / `silver` / `bronze` — issuing authority vs research re-publisher vs single-paper source. |
| `is_issuing_authority` | bool — distinguishes ECI on votes (true) from a research aggregator republishing the same numbers (false). |

The deviations from OWID are documented in `canonical-store.md` §5.2 and signed off per §0a (Hans + Max).

## Four lifecycles, one table

Every observation row's provenance is one of four shapes. All four go through the same table:

1. **Fetched (most rows).** Pipeline pulled bytes from a URL. The sources row carries the URL, the producer, and the content hash; the observation row carries the `source_id` FK.
2. **Hand-authored.** A maintainer wrote the content directly. The sources row carries `url_main = ""`, `url_download = ""`, `producer = "yen-gov"`, `license = "internal"`, `is_issuing_authority = false`, `confidence_tier = "gold"` (we know our own provenance). The commit message records the rationale and any reference materials consulted.
3. **Derived / composed.** A rollup (e.g. state aggregate from per-constituency results) is computed by `backend/`. Each derived observation row points at the same sources row(s) as its inputs — the FK composes naturally. Aggregations join through the sources table at query time; no de-normalised URL list is materialised on the rollup row.
4. **Control-plane (operator telemetry).** `datasets/manifest.json` and run logs under `.runtime/logs/` are operator state, not citizen-facing data. They MAY stamp `generated_at` with wall-clock; they do NOT participate in the `sources.parquet` FK contract (CLAUDE.md §10 carve-out).

## Idempotency

`content_hash` is the anchor that makes re-running ingest safe.

- If the pipeline re-fetches a URL and gets byte-identical bytes, the sources row's `content_hash` is unchanged. `last_seen_at` advances; `first_fetched_at` does not. No observation row changes; no Parquet bytes change.
- If the bytes change, the writer either updates the existing sources row in place (same logical URL, new content) or inserts a new sources row, depending on the adapter's semantics. Observations that re-derive from the new content UPSERT through their `observation_id` (canonical-store.md §4) and pick up the new `source_id`.

Wall-clock at write time is operator telemetry, NOT provenance. Using `datetime.now()` as input to observation content is forbidden (CLAUDE.md §10). All citizen-facing timestamps derive from `first_fetched_at` on the sources row, which itself derives from upstream content identity, not from when the script ran.

## What does NOT live in `sources.parquet`

- **Intermediate downloaded files** under `.runtime/raw/` (per [ADR-0003](../architecture/decisions/0003-no-fetch-cache.md)). These are throwaway debug artifacts; they have no `source_id`, no schema, and no place in `datasets/`.
- **Reference materials a human consulted** to write a hand-authored entity. Those go in commit messages, not as sources rows. A sources row records what the *pipeline* fetched, not what the maintainer read.
- **Identifier conventions** — "S22 is the ECI code for Tamil Nadu" is documented in [`identifiers.md`](../reference/identifiers.md), not as a per-row source.
- **Editorial notes about an indicator** — these are typed fields on `taxonomy/indicators.json` (`description_short`, `description_long`, `excluded_notes`, methodology break narratives), not provenance.

## Why this is mandatory

Civic data without provenance is anti-data. A reader cannot:

- assess whether the upstream has been updated since,
- reproduce the result by re-fetching,
- argue with the source if a number looks wrong,
- trust the publisher.

Treating provenance as a hard contract — enforced by the writer, surfaced in `CLAUDE.md` Holy Laws, captured in every Definition of Done — is what separates a publishing pipeline from a data-laundering one.

## See also

- `CLAUDE.md` Holy Law #9, §12 — authoritative statement.
- [`docs/architecture/data/canonical-store.md` §5](../architecture/data/canonical-store.md#5-sources-schema-d5) — full sources schema with column-by-column rationale.
- [ADR-0030 — Canonical store on Hive-partitioned Parquet read by DuckDB-WASM](../architecture/decisions/0030-canonical-store-duckdb-wasm.md) — the design decision that established this contract.
- [ADR-0003 — No HTTP cache layer; intermediates live in `.runtime/raw/`](../architecture/decisions/0003-no-fetch-cache.md) — why intermediates are excluded.
- [`docs/concepts/owid-alignment.md`](owid-alignment.md) — OWID is the canonical reference (§0a).
- [`docs/reference/identifiers.md`](../reference/identifiers.md) — code conventions for entities inside payloads (separate from the provenance of the payload itself).
- [ADR-0002 — Provenance as a list of `{url, fetched_at}` entries](../architecture/decisions/0002-provenance-as-sources-list.md) — **superseded** by ADR-0030; retained for historical context.

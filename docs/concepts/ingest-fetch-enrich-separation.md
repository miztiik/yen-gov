# Ingest: Fetch -> Enrich -> Publish

**Last Updated**: 2026-06-19

Doctrine for how a new upstream endpoint lands in yen-gov. The pipeline is **three pure-filter stages - Fetch -> Enrich -> Publish** - preceded by a fail-loud **preamble** (validate the targeted spec + diff against the checkpoint). The full subsystem design lives at [docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md); the operator cookbook at [docs/how-to/add-a-new-data-source.md](../how-to/add-a-new-data-source.md).

## Why this matters

Separating fetch from enrichment lets a new endpoint be added incrementally without rewriting an existing adapter, and lets the engine cache a fetched unit once and slice many indicators out of it. The pipeline is addressed by INDICATOR (`ingest run --indicator total-fertility-rate`); the source adapter that feeds it is resolved underneath. Identity is read from the catalogue (`concepts.json -> indicators.json -> variables.csv`) and never minted by the pipeline.

## The preamble (not a stage)

Before any pure-filter stage runs, `ingest run` does its fail-loud setup:

1. **Validate the targeted spec** against the catalogue: every `IndicatorSpec.indicator_id` FKs `indicators.json`, and the spec's `(unit, normalisation, price_basis, sampling_frame)` tuple must match the resolved concept. A bogus id or a measurement-tuple mismatch RAISES here.
2. **Diff against the checkpoint**: list the cache units the indicator draws from and compare each year's raw hash to the committed `datasets/_ops/ingest-state/<adapter_slug>.json` to build the work-list (the years that actually need fetching).

A non-emitting setup step is the run's preamble, NOT a fourth pipe stage. Source DESIGN is earlier still and author-time: `pre-flight-ingest` + the typed `SourceSpec` / `IndicatorSpec`.

## The three stages

### 1. Fetch

Pull the upstream cache unit - `httpx` with a bounded 3-try loop (no `tenacity`), or `operator_staged` (read a locally-staged raw payload) for flaky-TLS sources and every test. Raw bytes land in the gitignored `.runtime/cache/ingest/`; the year-checkpoint records the hash of the RAW payload. An unchanged year emits `fetch.skipped` and does no further work. Fetch is automated in the LOCAL pipeline only (Holy Laws #1/#2: production is static, CI consumes committed CSV and never fetches).

### 2. Enrich

Parse ONLY the requested indicator's slice of the fetched unit; resolve upstream entity labels to canonical `entity_id`, units to the concept's canonical unit, and period strings to the period axis. The six India-discontinuity gates (bifurcation, code-authority, fiscal-vs-calendar, provisional-vs-revised, price-basis, publisher-bounded-universe) RAISE on bad input rather than best-guessing. Look up `source_id` via `backend.yen_gov.canonical.citation.derive_source_id` (never hand-write it). Output: a typed `CanonicalBatch`.

### 3. Publish

Validate the batch against `columns.json`; run the **divergence gate** (a second `source_id` overwriting a cell beyond the concept's tolerance fails loud) and the **splice break-row gate** (a mid-series `source_id` change refuses to publish without a `methodology_breaks` row at the seam); UPSERT into the existing long-format CSV via `csv_writer.write_csv` keyed on `(entity_id, time)`; upsert the `source.csv` citation row; advance the checkpoint.

## Enrich INTO the existing dataset, never mint a new file

When an upstream endpoint publishes a fact already in canonical (a new fuel for installed-capacity, another publisher of GSDP, a finer period grain), Publish UPSERTs into the EXISTING long-format CSV via a new `(entity_id, time)` row. It does NOT create a new CSV stem per endpoint, and it does NOT mint a new `indicator_id` per vintage / publisher / base-year - per [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) and the [CLAUDE.md](../../CLAUDE.md) anti-pattern list. The CSV path and the `indicator_id` move in lockstep: one concept -> one `indicator_id` -> one canonical CSV path -> N rows across (entity, period, vintage, facet). A vintage shift uses the `methodology_breaks` ledger (per [ADR-0042](data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor)), never a new `indicator_id`.

Before any new ingest, run `python -m yen_gov pre-flight-ingest --proposal-file ./proposal.json --report ./report.json` ([ADR-0046](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)) per the ingest handover template (see [docs/agents/ingest-checklist.md](../agents/ingest-checklist.md) section 3). The gate batches the six mechanical checks (concept overlap, concept FK, grain prefix, `update_period_days`, justification, `source_id` derivation) into a single typed report so the agent cannot proceed past `verdict=abort`. If overlap >= 0.70, the action is UPSERT or add-a-facet - never mint.

## See also

- [docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md) - the full subsystem design + honesty doctrine.
- [docs/reference/cli-ingest.md](../reference/cli-ingest.md) - the `ingest run` / `status` / `clean` CLI.
- [docs/how-to/add-a-new-data-source.md](../how-to/add-a-new-data-source.md) - the operator cookbook.
- [docs/concepts/pre-flight-ingest.md](pre-flight-ingest.md) - the six author-time checks.
- [docs/concepts/data-provenance.md](data-provenance.md) - citation-ledger rules the Publish stage upserts into.
- [docs/concepts/indicator-naming.md](indicator-naming.md) - `<measure>-<unit>-<facet>` grammar, no grain prefix.
- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) - writer PK + canonical CSV layout.
- [ADR-0042](data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) - vintage as publisher edition vs operator snapshot.
- [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) - grain lives on the row, not the id.

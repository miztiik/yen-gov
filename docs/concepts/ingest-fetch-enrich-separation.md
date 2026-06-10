# Ingest fetch-vs-enrich separation

**Last Updated**: 2026-05-27

> **Pipeline name**: The Fetch -> Parse -> Enrich -> Emit workflow is **the Lift pipeline**. The cookbook for adding a new data source through it lives at [docs/how-to/add-a-new-data-source.md](../how-to/add-a-new-data-source.md).

> Doctrine for how new upstream endpoints land in yen-gov. Splits the monolithic adapter into four layers so a new endpoint can be added incrementally without rewriting an existing adapter.

## Why this matters

Today every ICED adapter mixes HTTP fetch + JSON parse + entity resolution + unit conversion + period normalisation + canonical UPSERT in a single Python module. The on-disk evidence is stark: only ~8% of the 259 endpoints the ICED portal publishes are ingested. Every new endpoint forces a full adapter rewrite, so endpoints arrive in big bangs (or not at all) instead of one-at-a-time.

Separating fetch from enrichment unlocks three properties:

1. **Bulk-fetch once, parse later.** All 259 parameter-free endpoints can be pulled into `datasets/<family>/_meadow/iced/<vintage>/` in one sweep; parsing + enrichment land per endpoint in their own PRs.
2. **Per-endpoint enrichment PRs.** A new endpoint only touches its `parsers.py` entry + a thin `ingest.py` enricher. No HTTP code re-flow, no shared-client churn.
3. **UPSERT into the EXISTING canonical CSV.** A new endpoint that supplements an existing concept (e.g. another fuel type for installed-capacity) extends the SAME long-format CSV via the writer PK `(entity_id, year, period_label, indicator_id)`. No new CSV stems per endpoint. No new `indicator_id` per vintage / publisher / base-year -- per [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) and the [CLAUDE.md](../../CLAUDE.md) anti-pattern list.

## The four layers

Every new-endpoint ingest MUST decompose into these four layers, one commit per layer:

### 1. Fetch (`<adapter>/client.py` or shared `iced_common/client.py`)

- HTTP only. Pull bytes from upstream and write to `datasets/<family>/_meadow/<source>/<vintage>/<endpoint>.json` per [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier).
- Idempotent and deterministic: identical inputs produce byte-identical meadow files.
- No transformation, no parsing, no entity resolution. The fetch layer cannot fail on bad data shape; it just stores what the wire returned.

### 2. Parse (`<adapter>/parsers.py`)

- Pure functions: raw JSON bytes -> list of typed Python dicts.
- No I/O. No network. No entity resolution. No unit conversion.
- Lives entirely in-memory; trivially unit-testable with fixture JSON snippets.

### 3. Enrich (`<adapter>/ingest.py`)

- Resolves upstream entity names to canonical `entity_id` (e.g. ECI state code, LGD district code) via the resolver in `backend/yen_gov/canonical/entity.py`.
- Converts upstream units to the canonical unit declared in the `concepts.json` row.
- Normalises period strings to `period_label` (`FY2023-24`, `2024-Q1`, `2024-03`, ...).
- Assigns `indicator_id` per the concept-overlap rule (see below).
- Looks up `source_id` via `backend.yen_gov.canonical.citation.derive_source_id` per [CLAUDE.md §12](../../CLAUDE.md).
- Output: a list of canonical rows ready for the writer.

### 4. Emit (`yen_gov.canonical.writer`)

- UPSERTs rows into the existing long-format CSV via PK `(entity_id, year, period_label, indicator_id)`.
- NEVER creates new CSV stems per endpoint. The writer fails fast if asked to emit to a path that does not already exist in the canonical-allowlist.
- Vintage shifts use the `methodology_breaks` ledger (see the schema registry) per [ADR-0042](data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) — NEVER a new `indicator_id`.

## The doctrine

A new-endpoint PR MUST follow this 4-layer decomposition. Reviewers check:

- **Fetch commit** touches only `client.py` + raw meadow files under `datasets/<family>/_meadow/<source>/<vintage>/`.
- **Parse commit** touches only `parsers.py` + parser unit tests with fixture JSONs.
- **Enrich+Emit commit** touches `ingest.py` + the existing canonical CSV (row count increases monotonically) + a contract test that proves UPSERT (not overwrite).

A PR that mixes all three layers is a Definition-of-Done failure and must be split before merge.

## Enrich INTO existing dataset, not create new

When an upstream endpoint publishes a fact already in canonical (a new fuel for installed-capacity; another publisher of GSDP; a finer period grain of an existing series), the enrich layer UPSERTs into the EXISTING long-format CSV via a new `(entity_id, year, period_label, indicator_id)` tuple. It does NOT create `energy_installed_capacity_<new_fuel>.csv`.

This is the same rule that governs `indicator_id` minting (see [docs/concepts/indicator-naming.md](indicator-naming.md) and the [CLAUDE.md](../../CLAUDE.md) anti-pattern: "Do NOT mint a new `indicator_id` for a new vintage, new publisher, new base-year"). The CSV path and the `indicator_id` move in lockstep: one concept -> one `indicator_id` -> one canonical CSV path -> N rows across (entity, period, vintage, facet).

Before any new ingest, run `python -m yen_gov pre-flight-ingest --proposal-file ./proposal.json --report ./report.json` ([ADR-0046](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)) per the ingest handover template (`TODO/_TEMPLATE-ingest-handover.md` §3). The gate batches the six mechanical checks (concept overlap, concept FK, grain prefix, update_period_days, justification, source_id derivation) into a single typed report so the agent cannot proceed past `verdict=abort`. If overlap >= 0.70, the action is UPSERT or add-a-facet — never mint.

## See also

- [docs/concepts/pre-flight-ingest.md](pre-flight-ingest.md) — mechanical enforcer for the six checks below
- [docs/concepts/meadow-tier.md](meadow-tier.md) — backend-internal parsed-row staging
- [docs/concepts/data-provenance.md](data-provenance.md) — citation-ledger rules for the enrich layer
- [docs/concepts/indicator-naming.md](indicator-naming.md) — `<measure>-<unit>-<facet>` grammar, no grain prefix
- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) — writer PK + canonical CSV layout
- [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier) — meadow tier
- [ADR-0042](data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) — vintage as publisher edition vs operator snapshot
- [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) — grain lives on the row, not the id

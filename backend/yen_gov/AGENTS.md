# AGENTS.md - backend/yen_gov

**Last Updated**: 2026-06-04

Canonical backend rationale lives in `docs/architecture/backend/`; this file is only a fast module map for agents.

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **MIGRATING (2026-06-04).** Per the [CLAUDE.md](../../CLAUDE.md) doctrine-in-migration banner + [the platform-reset plan](../../TODO/20260603-data-and-charting-platform-reset-plan.md), the canonical store is moving from Hive-partitioned Parquet to long-format CSV under `datasets/data/`, read via DuckDB-WASM `read_csv(columns=...)`; provenance FK now targets `datasets/data/entities/source.csv`. Parquet references below are MIGRATING until the rip lands (writers B3, fetch B4, reader-flip X1a / X1a-followup, Parquet-delete X1b - X1b retired the 12 zero-reader parquets on 2026-06-06: `elections/dim_parties` + `elections/dim_pcs` + `elections/dim_persons` + `taxonomy/ac_crosswalk` + `taxonomy/persons` + `taxonomy/sources` + 6 small taxonomy orphans `election_events` / `facet-axes` / `indicator_topic_tags` / `methodology_breaks` / `state_tiers` / `topics`; the WRITERS that still emit these tables retire in B3 not X1b). Do NOT add a new Parquet writer or a network fetcher.

## Canonical Docs

- [Backend overview](../../docs/architecture/backend/overview.md)
- [Backend core](../../docs/architecture/backend/core.md)
- [Pipeline](../../docs/architecture/backend/pipeline.md)
- [Dataset coverage](../../docs/architecture/backend/coverage.md)
- [ECI source adapter](../../docs/architecture/backend/sources-eci.md)
- [Data provenance](../../docs/concepts/data-provenance.md)
- [Dataset shapes](../../docs/concepts/dataset-shapes.md)
- [Canonical store (long-format CSV + DuckDB-WASM)](../../docs/architecture/data/canonical-store.md) - current model (B2b MERGED; X1b PARTIAL on 2026-06-06; residual Parquet survivors: `election_results` + `dim_party_alliances` + `dim_acs` + `elections_candidacies` + `entities` + `indicators` + `boundary_layers`)
- [Governments data family](../../docs/architecture/data/governments.md) - office-holdings authoring + Parquet contract
- [Folded indicator](../../docs/concepts/folded-indicator.md) - **obsolete under ADR-0030**, retained as historical reference
- [Collection inventory](../../docs/concepts/collection-inventory.md) - **obsolete under ADR-0030**
- [Data quality stance](../../docs/concepts/data-quality.md)

## Invariants

- Local pipeline only; no production backend assumption.
- Producers write schema-validated artifacts to `datasets/`; consumers treat those artifacts as contracts.
- Cross-runtime sharing is data only: JSON, SQLite, CSV, schemas. No frontend imports.
- Core/domain code must not import adapters or infrastructure.
- Persisted paths are POSIX-relative, never absolute or Windows-style.
- Every emitted data file carries `sources[]` and schema metadata.
- **Canonical pivot.** New writes target long-format CSV under `datasets/data/` emitted by the canonical CSV writer (MIGRATING from Hive-partitioned Parquet written by UPSERT-into-DuckDB per plan chunk B3 - X1b PARTIAL retired the 12 zero-reader parquet DATA files on 2026-06-06, but the WRITERS that emit them stay until B3). Canonical observation row = `(entity_id, year:int, period_label:text, indicator_id, value, source_id)`. Time axis is **OWID `year:int`** (end-year for FY); `period_label` is the verbatim publisher string. Sources are a **citation table** at `datasets/data/entities/source.csv` keyed by `(producer, title, vintage)`; observation rows carry `source_id` FK (the legacy `datasets/taxonomy/sources.parquet` was retired in X1b on 2026-06-06). Fetch telemetry lives outside the citizen-facing contract. See [canonical store](../../docs/architecture/data/canonical-store.md) and [data provenance](../../docs/concepts/data-provenance.md).
- **Governments office holdings.** `datasets/taxonomy/office_holdings.json` compiles to `datasets/governments/{dim_offices,governments_office_holdings}.parquet` via `office_holdings_seed.py`. Legacy CM rows use `office_citations`; non-CM constitutional-office rows must use official `citation_groups` aligned to `sources.parquet`. TCPD office-bearer CSVs are seed/QA only while official Government of India sources exist.
- **Legacy folded JSON** (`datasets/indicators/in/<topic>/<id>.json` and its sidecar inventory/operator-state files) was superseded by the canonical Parquet store during the pivot. **No new writers** in that shape. The legacy per-event elections JSON tree (`datasets/elections/<event>/<state>/{results/<ac>.json,parties.json,result.summary.json,_inventory.json}`) still sits on disk interleaved with the new canonical Parquet (`observations.parquet`, `dim_*.parquet`); per-family cleanup is sequenced under THE PLAN rows 1.8b-1.8f. See [`docs/architecture/canonical-pivot-deletion-manifest.md`](../../docs/architecture/canonical-pivot-deletion-manifest.md). The pre-pivot rule "adapter owns opaque `{key, label, frequency}` tokens; no normaliser" is **withdrawn** for canonical artifacts - under OWID adoption, adapters write `year:int` + verbatim `period_label`, and indicators carry `cadence` on the indicator row.
- **Directory invariant** (Gregor, Phase 1.8a): for any family `F`, `datasets/F/` MUST contain only canonical Parquet (`observations.parquet`, `dim_*.parquet`, partitioned variants) plus a sibling `taxonomy/*.parquet`. It MUST NOT contain per-event nested JSON shards or per-state sqlite once that family's 1.8 sub-row lands. Violations of this invariant are caught by the admin Inventory panel (`backend/yen_gov/admin/inventory.py`) which classifies every file under `datasets/` and surfaces unknown kinds.
- Per Holy Law #9 + CLAUDE.md section 12: every emitted observation carries a `source_id` FK to `datasets/data/entities/source.csv`.

## Validation

- Backend behaviour changes need `pytest -q` in `backend/`.
- Dataset/schema changes need the producer validator tests and consumer contract tests described in [CLAUDE.md](../../CLAUDE.md#15-test-coverage-policy).
- If a source adapter changes, update its `docs/architecture/backend/sources-*.md` doc in the same commit.

# AGENTS.md - backend/yen_gov

**Last Updated**: 2026-06-04

Canonical backend rationale lives in `docs/architecture/backend/`; this file is only a fast module map for agents.

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **MIGRATING (2026-06-04, updated 2026-06-06 post-B3 + B4-pt2).** Per the [CLAUDE.md](../../CLAUDE.md) doctrine-in-migration banner + [the platform-reset plan](../../TODO/20260603-data-and-charting-platform-reset-plan.md), the canonical store is moving from Hive-partitioned Parquet to long-format CSV under `datasets/data/`, read via DuckDB-WASM `read_csv(columns=...)`; provenance FK now targets `datasets/data/entities/source.csv`. X1b retired 14 zero-reader parquets on 2026-06-06 (`elections/dim_parties` + `elections/dim_pcs` + `elections/dim_persons` + `elections/dim_acs` + `elections/elections_candidacies` + `taxonomy/ac_crosswalk` + `taxonomy/persons` + `taxonomy/sources` + 6 small taxonomy orphans `election_events` / `facet-axes` / `indicator_topic_tags` / `methodology_breaks` / `state_tiers` / `topics`). B3 (2026-06-06) deleted the 10 dedicated canonical seed writers for those parquets + the shared `writer.py` paths that emitted them + 9 dead per-parquet schemas + the `s1-persons-fork` + `ingest-people-panel` CLI commands. **B4-pt2 (2026-06-06)** retired the fetch/http stack: pt2.1 #824 stripped IcedClient + Fetcher network paths from 10 mixed iced + rbi_xlsx ingest modules (preserving B1.* CSV-emit helpers); pt2.2 #826 deleted 11 network CLI commands + `pipeline/run.py` + `pipeline/reference.py`; pt2.3 #827 deleted 6 orphan source modules (`sources/eci/{statistical_report,static_catalog,urls}.py` + `sources/wikipedia/urls.py` + `sources/iced_common/client.py` + `sources/iced_power/fetch_pipeline.py`) + stripped `sources/india_geodata/power_plants.py`; pt2.4 (this PR) deleted `core/http.py` + `test_core_http.py` + `datasets/_ops/range-mime-probe.parquet` + removed `tenacity` from pyproject. Remaining MIGRATING surfaces: the surviving parquets (`election_results` / `dim_party_alliances` / `entities` / `indicators` / `boundary_layers`) still flow through `writer.py` (observations + dim_party_alliances paths) and the dedicated `entities_seed` / `indicators_seed` / `office_holdings_seed` / `boundary_layers_seed` modules; the `legacy/folded_indicator_writer.py` module + `core/io.write_artifact` survive B4-pt2 (still has ~9 production callers including the surviving `eci-statreport-emit-local` CLI command + 6 cache-only ingest orchestrators + canonical eci adapter); a follow-up "B4-pt3" PR retires them once the surviving `write_artifact` callers are all migrated to the canonical CSV writer or deleted. Do NOT add a new Parquet writer or a network fetcher.

## Canonical Docs

- [Backend overview](../../docs/architecture/backend/overview.md)
- [Backend core](../../docs/architecture/backend/core.md)
- [Pipeline](../../docs/architecture/backend/pipeline.md)
- [Dataset coverage](../../docs/architecture/backend/coverage.md)
- [ECI source adapter](../../docs/architecture/backend/sources-eci.md)
- [Data provenance](../../docs/concepts/data-provenance.md)
- [Dataset shapes](../../docs/concepts/dataset-shapes.md)
- [Canonical store (long-format CSV + DuckDB-WASM)](../../docs/architecture/data/canonical-store.md) - current model (B2b MERGED; X1b PARTIAL on 2026-06-06; residual Parquet survivors: `election_results` + `dim_party_alliances` + `entities` + `indicators` + `boundary_layers`)
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
- **Canonical pivot.** New writes target long-format CSV under `datasets/data/` emitted by the canonical CSV writer. Post-B3 (2026-06-06): the parquet writer at `backend/yen_gov/canonical/writer.py` retains observation emit (`election_results` partitioned shards + energy/livestock observation parquets via `write_batch`) + the surviving `dim_party_alliances` dim emit; the 4 dead dim emit paths (person/ac/pc/party) + `_emit_sources` + `_emit_facet_axes` + `_emit_persons_taxonomy` + the dedicated `persons_seed` / `topics_seed` / `state_tiers_seed` / `facet_axes_seed` / `methodology_breaks_seed` / `election_events_seed` / `ac_crosswalk` / `energy_sources_seed` / `persons_fork` modules were deleted in B3 because their target parquets retired in X1b (#814). Canonical observation row = `(entity_id, year:int, period_label:text, indicator_id, value, source_id)`. Time axis is **OWID `year:int`** (end-year for FY); `period_label` is the verbatim publisher string. Sources are a **citation table** at `datasets/data/entities/source.csv` keyed by `(producer, title, vintage)`; observation rows carry `source_id` FK (the legacy `datasets/taxonomy/sources.parquet` was retired in X1b on 2026-06-06). Fetch telemetry lives outside the citizen-facing contract. See [canonical store](../../docs/architecture/data/canonical-store.md) and [data provenance](../../docs/concepts/data-provenance.md).
- **Governments office holdings.** `datasets/taxonomy/office_holdings.json` compiles to `datasets/governments/{dim_offices,governments_office_holdings}.parquet` via `office_holdings_seed.py`. Legacy CM rows use `office_citations`; non-CM constitutional-office rows must use official `citation_groups` aligned to `sources.parquet`. TCPD office-bearer CSVs are seed/QA only while official Government of India sources exist.
- **Legacy folded JSON** (`datasets/indicators/in/<topic>/<id>.json` and its sidecar inventory/operator-state files) was superseded by the canonical Parquet store during the pivot. **No new writers** in that shape. The legacy per-event elections JSON tree (`datasets/elections/<event>/<state>/{results/<ac>.json,parties.json,result.summary.json,_inventory.json}`) still sits on disk interleaved with the new canonical Parquet (`observations.parquet`, `dim_*.parquet`); per-family cleanup is sequenced under THE PLAN rows 1.8b-1.8f. See [`docs/architecture/canonical-pivot-deletion-manifest.md`](../../docs/architecture/canonical-pivot-deletion-manifest.md). The pre-pivot rule "adapter owns opaque `{key, label, frequency}` tokens; no normaliser" is **withdrawn** for canonical artifacts - under OWID adoption, adapters write `year:int` + verbatim `period_label`, and indicators carry `cadence` on the indicator row.
- **Directory invariant** (Gregor, Phase 1.8a): for any family `F`, `datasets/F/` MUST contain only canonical Parquet (`observations.parquet`, `dim_*.parquet`, partitioned variants) plus a sibling `taxonomy/*.parquet`. It MUST NOT contain per-event nested JSON shards or per-state sqlite once that family's 1.8 sub-row lands. Violations of this invariant are caught by the admin Inventory panel (`backend/yen_gov/admin/inventory.py`) which classifies every file under `datasets/` and surfaces unknown kinds.
- Per Holy Law #9 + CLAUDE.md section 12: every emitted observation carries a `source_id` FK to `datasets/data/entities/source.csv`.

## Validation

- Backend behaviour changes need `pytest -q` in `backend/`.
- Dataset/schema changes need the producer validator tests and consumer contract tests described in [CLAUDE.md](../../CLAUDE.md#15-test-coverage-policy).
- If a source adapter changes, update its `docs/architecture/backend/sources-*.md` doc in the same commit.

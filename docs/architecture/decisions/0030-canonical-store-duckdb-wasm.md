# ADR-0030: Canonical long-format store on Hive-partitioned Parquet read by DuckDB-WASM

**Last Updated**: 2026-05-18
**Status**: Accepted
**Deciders**: User; agent-deliberation across rounds R1–R11 included Hans (Governance), Max (Indicator Scout), Gregor (Architect), Fowler (Engineering), Jony (UI/UX), Citizen
**Supersedes**: [ADR-0026](0026-lift-collection-inventory-out-of-indicator-artifact.md) (lift collection inventory), [ADR-0027](0027-cadence-as-separate-field-from-time-grain.md) (cadence as separate field), and the per-shard JSON folded-indicator doctrine in [`docs/concepts/folded-indicator.md`](../../concepts/folded-indicator.md) + [`docs/concepts/collection-inventory.md`](../../concepts/collection-inventory.md). Also retires the strangler-fig coexistence stance — production is rip-and-replace (D13).
**Plan reference**: [TODO/20260517-canonical-long-format-pivot.md](../../../TODO/20260517-canonical-long-format-pivot.md) is THE PLAN; on conflict THE PLAN wins and this ADR is amended.

## Context

### Pre-pivot state

Before this ADR, yen-gov stored socio-economic and election data as ~7,300 per-shard JSON files under `datasets/indicators/in/<topic>/<id>.json` plus a parallel `datasets/elections/in/<election_id>/<state>/<ac>/*.json` tree. Each shard carried its own `sources[]` array with `fetched_at` per entry, its own `collection_inventory` overlay (lifted partially in ADR-0026), its own `cadence` (added in ADR-0027), and its own period token in the `{key, label, frequency}` shape. Citizens read this via static `fetch()` calls from the Svelte 5 + Vite 6 bundle on GitHub Pages.

This shape had four structural problems:

1. **No SQL.** Cross-shard questions ("compare all states on literacy in 2011") fanned out into N HTTP requests + client-side joins. The "Explore" page resorted to sql.js loading a full SQLite mirror (ADR-0017) just to make basic joins viable.
2. **Smeared `fetched_at`.** Re-running ingest with byte-identical upstream changed every shard's `fetched_at`, generating diff churn that defeated dict-equal write-skip gates (CLAUDE.md §10 anti-pattern, lesson-2026-05-16).
3. **File proliferation.** 110 socio-economic indicator IDs × per-shard JSON × per-cadence dimension variants generated multiple files per logical series. Adding judiciary, healthcare, water, crime, education-deep, welfare, and local-government-finance — none yet ingested — would push the count past 30,000 shards (THE PLAN §0b).
4. **Per-shard sources smear.** A single ECI page that fed 50 election shards was recorded 50 times in 50 different `sources[]` arrays. There was no FK; corrections required N rewrites.

### "The One Rule" (CLAUDE.md §0a)

User approval (R7, 2026-05-17) made **Our World in Data the canonical reference for socio-economic data modelling**. OWID has already solved the shape problems above: long-format observations on a `year:int` axis, indicator metadata as a catalogue, sources as a table keyed by `(url, content_hash)` with `origin.*` fields. Where OWID has solved a question, yen-gov adopts verbatim; deviations require Hans + Max sign-off and are documented in [`docs/architecture/data/canonical-store.md`](../data/canonical-store.md) (Phase 0.2, to be authored).

The authority assignment for this ADR (and for all future data-shape decisions) is:

| Decision class | Authority |
| --- | --- |
| Data shape — column types, enums, period axis, entity IDs, indicator metadata, sources schema, taxonomy | **Hans + Max** |
| Contract / integration — schema versioning, write seams, layer boundaries, pipes-and-filters | **Gregor** |
| Engineering craft — refactor safety, test tiers, module structure, deletion | **Fowler** |
| UX — URL grammar, visual bounds, copy, citizen framing | **Jony + Citizen** |
| Anything | **User supersedes every agent and every rule** |

### Cardinality is a moving target (THE PLAN §0b)

The "~80–120 indicator_ids" figure from the Phase 0 consolidation audit is the count after collapsing today's 110 ingested IDs into parents + selective facet-explode children. It is **not** the steady-state count. Eight source domains are queued but not yet ingested — judiciary (NJDG, NCRB-Prison, SC data), healthcare (NFHS/HMIS/disease-burden), water (CGWB/CWC), crime & policing (NCRB/BPRD), education-deep (UDISE+, AISHE, NIRF, PARAKH), environment-deep (CPCB, FSI, ENVIS), transport-deep (Vahan, IR, MoRTH), agriculture (DA&FW, FCI), welfare (NREGAsoft, PMAY-G, PDS), local-government finance (FFC/SFC, RBI municipal finances). The contract must scale to **500–1,000+ indicator_ids over 2–3 years without architectural change**.

### Boundaries are preserved (THE PLAN §0c)

`datasets/boundaries/in/` is **not** legacy. It is a sibling family to the canonical Parquet store (D25). No step in this pivot moves, renames, or deletes anything under that tree; future additions (PCs, taluks, village coverage) follow the same `{geojson|pmtiles}/` layout. Full rationale lands in ADR-0031 (Phase 0.14, to be authored).

### What this ADR resolves

A single contract for: how observations are stored, how time is modelled, how identity differs from provenance, how the catalogue carries Hans-honesty surface, how facets explode without code rent, how methodology breaks are surfaced, how the frontend reads canonical data, how the backend writes it deterministically, and how the migration off per-shard JSON happens without losing the catalogue.

## Decision

The 36 decisions below are settled per rounds R1–R11. They are grouped by theme; numbering matches THE PLAN §2 verbatim.

### Group 1 — Storage and read path

- **D1.** Canonical store = Hive-partitioned Parquet read by DuckDB-WASM in the browser. Static-hostable on GitHub Pages; SQL-queryable; columnar; OSS-mature.
- **D8.** Hive partition only when family > 15 MB; partition by `indicator_id` (or `topic_id`) when partitioned — **never by `year`** (R18). Shards ≤ 4 MB target 1.5 MB. Time-series queries scan all years for one indicator; partitioning by year would force N-file metadata fetch per series.
- **D10.** No JSON projections of canonical data for the frontend. DuckDB-WASM reads Parquet directly via HTTP Range.
- **D11.** No CI on `datasets/**`. Publish is plain static-file copy via GitHub Pages from `main`; the only CI gates are lint, type-check, pytest, frontend build, Playwright — none of which touch `datasets/` contents.

### Group 2 — Time and period axis

- **D2.** OWID `year:int` is the time axis, end-year convention for fiscal years (FY 2024-25 → 2025). Supports `WHERE year >= 2020`; simpler than struct.
- **D3.** `period_label:text` is the verbatim publisher string (`"FY 2024-25"`, `"Q3 2024-25"`, `"Jan 2020"`) **and** is the citizen-visible time string. Renderer rule: sort/query by `(year, period_seq)`; display `period_label`. Showing "2025" when the source says "FY 2024-25" is a defect.

### Group 3 — Row model and identity

- **D4.** Long-format only — one observation per row. Schema stability across cadences; trivial pivoting in SQL.

- **D7.** UPSERT-into-DuckDB + sorted Parquet emit. **Logical key = `(entity_id, year, period_label, indicator_id)`** — never `source_id`. A corrected upstream value from the same publisher keeps the same logical row; the UPSERT updates value/source pointers, it does not duplicate (R16).

- **D5 (row-shape facet) / D17 (numeric+text split).** Observation row:

  ```
  observations: (
    observation_id,    -- sha256(entity_id || year || period_label || indicator_id)
    entity_id,         -- FK -> taxonomy/entities.parquet
    year:int,          -- end-year convention
    period_label:text, -- verbatim publisher string
    period_seq:int,    -- monotonic intra-year sort key (1..N per year per indicator)
    indicator_id,      -- FK -> taxonomy/indicators.parquet
    value_numeric:DOUBLE,  -- nullable; numeric reading
    value_text:VARCHAR,    -- nullable; "Nil", "N.A.", "Not reported", categorical
    source_id          -- FK -> taxonomy/sources.parquet (provenance, NOT identity)
  )
  ```

  Both value columns are nullable; **exactly one is populated per row** (writer enforces). Administrative data emits "Nil"/"N.A." as meaningful tokens distinct from null and zero — collapsing both into a single `value:DOUBLE` (R17) would lose information. `period_seq` is the intra-year sort key: `monthly_cy` → 1..12, `quarterly_fy` → 1..4, `annual_*` and `decennial` → 1.

### Group 4 — Provenance as table

- **D5 (sources facet).** Sources = TABLE at `taxonomy/sources.parquet` with **OWID `origin.*` fields verbatim** plus **yen-gov extensions explicitly tagged** in `canonical-store.md`. OWID verbatim: `producer`, `citation_full`, `url_main`, `url_download`, `date_accessed`, `license`, `vintage`. yen-gov extensions: `source_id` (PK), `url`, `content_hash` (sha256 of fetched bytes), `first_fetched_at`, `last_seen_at`, `confidence_tier:enum(gold|silver|bronze)`, `is_issuing_authority:bool`. Curating from mixed-quality Indian shelves (issuing authority vs research re-publisher vs single-paper bronze) requires the confidence signal; OWID doesn't carry it because its editorial gate happens upstream of the table.

- **D6.** `first_fetched_at` (immutable, citizen-facing, RFC 3339 UTC) + `last_seen_at` (mutable telemetry, RFC 3339 UTC) replace the legacy smeared `fetched_at`. Re-running ingest with byte-identical upstream updates only `last_seen_at`; bytes on disk are unchanged.

- **D22.** FK referential integrity enforced at **write time** by the backend writer/validator. DuckDB-WASM via HTTP Range cannot enforce FKs in production; the writer asserts no dangling `indicator_id` / `source_id` / `entity_id` in observations before emit. The Tier-B validator (`python -m yen_gov validate --root .`) covers the same invariant.

### Group 5 — Indicator catalogue and facet model

- **D15.** `cadence` lives on the indicator row; the indicator catalogue carries the **full Hans honesty surface**. Minimum columns: `label_short`, `label_long`, `description_short`, `description_long`, `unit`, `cadence`, `default_period_seq_for_cadence`, `family`, `pillar`, `topic_tags[]`, `value_kind`, `direction`, `denominator`, `attribution_geography`, `comparability`, `implementing_authority`, `funding_split`, `methodology_vintage`, `revision_tier`, `excluded_notes`, `methodology_break_ids[]`, `series_breaks_summary`, `latest_break_year`, `breaks_count`, `coverage_states_count`, `coverage_year_min`, `coverage_year_max`, `coverage_density`. `coverage_*` are denormalised at every emit so the catalogue stays browseable without scanning multi-GB observation Parquet from the browser.

- **D26.** **Facet handling = facet-explode** with the parent+children pattern: parent indicator carries `parent_indicator_id NULL`, children carry `parent_indicator_id` FK back to parent + `dimension_values:STRUCT` populated. **Selective explode rule (Hans)**: explode iff the facet changes the *citizen's governance question*; otherwise keep as observation-row facet. At target cardinality this scales without code rent; URL grammar stays `/indicator/<id>` with no facet picker; legend stays single code path. Rejected: `dimensions:MAP<VARCHAR,VARCHAR>` typed column on every row (R26, Gregor's R1 option (c)) — registry + hash-extension + dimension-aware queries in 3 places with no Phase-1 external consumer.

- **D27.** **Entity tiering = single `entity_id` + `entity_type` enum** (`state`, `district`, `ulb`, `union_govt`, `state_govt`, `discom`, `psu`, …). OWID-canonical shape; sufficient for Phases 1–3. Max preferred separate `geo_entity_id` + `fiscal_actor_id` (R27, option (ii)) and yielded to Hans per §0a authority. Double-entry transfer rows deferred to Phase F.

- **D28.** **`methodology_version` composes Hans (FK to `methodology_breaks.parquet`) + Fowler (id-encoded variant)**. Both: GSDP-base-2011-12 and GSDP-base-2004-05 are separate `indicator_id`s (URL-visible break); the `methodology_breaks` table carries the prose narrative for chart splice markers. Split is governance-visibility (URL/id) + narrative-richness (table). One join at chart time, ~50 table rows total, no rent on every observation row.

- **D29.** Indicator catalogue column shape extends D15 with: `id` (kebab-case, ≤60 chars), `display_name`, `parent_indicator_id NULL` (self-FK), `dimension_values:STRUCT NULL` (populated iff `parent_indicator_id IS NOT NULL`), `methodology_version VARCHAR NULL` (FK to `methodology_breaks`), and **per-child `source_id`** (NOT shared across siblings — coal-capacity from CEA and solar-capacity from MNRE are siblings with different upstreams).

- **D30.** Indicator naming convention: `<entity>-<measure>-<unit>-<facet>`, kebab-case, single segment, max 60 chars. Sibling sort works via `ORDER BY id`. Approved abbreviations: `nsdp`, `gsdp`, `cpi`, `imr`, `mmr`, `tfr`, `mw`, `gwh`, `mu`, `inr`, `pct`. New abbreviations require Max sign-off. Methodology-version children encode the version in id (`-base-2011-12`). Documented in `canonical-store.md` (Phase 0.2).

- **D31.** Registered facet axes: `datasets/taxonomy/facet-axes.json` (schema-versioned) enumerates allowed `dimension_values` keys: `fuel_type`, `sector`, `head_of_account`, `gender`, `residence`, `prices_basis`, `methodology_version`, `transfer_type`, `category`, `crime_category`, `cpi_category`, `loss_type`, plus axes added by Phase 2/3 ingestion. **The catalogue validator REJECTS any `dimension_values` key not in this registry** — prevents ad-hoc dimension proliferation as the corpus grows.

- **D33.1–D33.8 (Hans's eight governance answers).** GSDP/IIP/WPI/CPI base-year rebases → `methodology_version` on same indicator_id plus id-encoded variant (D33.1). Distribution losses → one parent + `loss_type` facet; default AT&C, fall back to T&D, annotate switch (D33.2). Cognizable crimes → count AND NCRB-published rate-per-100k as measure facets on one parent; do NOT compute own rate from interpolated Census (D33.3, R30). Census H-series vs NFHS amenities → two parents with `related_indicators` cross-link (D33.4). Derived indicators (sex ratio, density, urbanisation %, road density, forest cover %) → first-class parents stored as observed (D33.5). Voter turnout GE vs AE → two parents (D33.6). CPI `combined_yoy` → facet value alongside food/fuel/housing/general; do NOT re-derive aggregates (D33.7). `fuel_type=total` → explode REPLACES the total; total is compute-on-read (`SUM(value) GROUP BY state, year`) (D33.8).

### Group 6 — Boundary geometry as sibling family

- **D25.** Boundary geometry lives **outside** the canonical Parquet store in a sibling family at `datasets/boundaries/in/`. Format split by size: GeoJSON for small layers (country, states), PMTiles for large layers (national districts when >10 MB, AC, PC, sub-districts, villages). Boundary files are EXCLUDED from the Phase 0.13 `_old/` move and from the Phase 1.8 `_old/` deletion (R25, THE PLAN §0c). Existing files preserved as-is: `boundaries/in/country/IN.json`, `boundaries/in/geojson/{india-states, india-districts, india-soi}.geojson`, per-state `S01-ac.geojson`…`S2x-ac.geojson` plus `.sources.json` sidecars. Full rationale → **ADR-0031 (Phase 0.14)**. This ADR does not duplicate that scope; see also [`docs/architecture/data/boundaries.md`](../data/boundaries.md).

### Group 7 — Methodology breaks and caveats

- **D16.** `caveats.parquet` is for **cross-cadence misleading-join banners only**; `methodology_breaks.parquet` is a **separate typed surface**. Cross-cadence joins and methodology/base-year breaks are distinct citizen risks; conflating them merges two different banner copies into one ambiguous channel (R20).

- **D32.** Chart-shell view-model addition: D19's loader return shape gains `breaks: [{period_seq, methodology_version, note}]`. Rendered as a thin vertical rule on the time axis, **visible at rest** (not tooltip-only). `breaks: []` when none. Surfaces D28 visibly; satisfies the "never smooth a line across a methodology rupture" rule (R31, Bhattacharya).

### Group 8 — Contracts

- **D9.** Local schema `$id` (relative path `./<name>.schema.json`), not URL. IDE offline validation; no broken-link rot (R14).

- **D18.** Hand-authored taxonomy files are **TEXT (JSON or CSV) in git**; the pipeline compiles them into Parquet at ingest. Parquet is binary; `operator_state.parquet` / `caveats.parquet` would be unreviewable in PR (R19). Authored shape: `taxonomy/{entities,indicators,operator_state,caveats,methodology_breaks,facet-axes}.json`. Whether the compiled `.parquet` variants are also committed is open question Q9.

- **D19.** **Chart-ready view-model loader** is a frontend contract — the DuckDB-WASM loader returns shaped view-models, never raw observation rows (R22). The loader joins `observations` + `taxonomy/indicators` + `taxonomy/sources` + `caveats` + `methodology_breaks` into the metadata-rich shape that generic renderers consume (unit, direction, cadence, comparability, source display, license, caveat/break banners). Prevents SQL from leaking into `IndicatorChoropleth`, `StackedTrend`, route files.

- **D20.** **Typed adapter→writer batch envelope** is the canonical message contract: `{ target_family, schema_version, source_rows[], observation_rows[], dimension_rows[]?, replacement_semantics }`. Every adapter speaks this envelope; the writer is a single Message Translator (Gregor: Aggregator + Canonical Data Model pattern).

- **D21.** **Parquet schema version + table id live in Parquet key-value metadata** AND a typed manifest file at `datasets/manifest.json`. JSON Schema `$schema_version` does not apply to Parquet — explicit mechanism required. Reader fails loud on unsupported version. Manifest enumerates `{table_id, family, partition_columns, files[], schema_version, row_count}` so the browser does file discovery via control-plane, not by guessing paths (R23). Manifest also indexes boundary files (D25) so the frontend never hardcodes geometry paths.

### Group 9 — Entities and validity windows

- **D23.** Entities carry validity windows: `entity_valid_from:int`, `entity_valid_to:int|null`. Telangana (2014), J&K/Ladakh (2019), and earlier state reorganisations must read as "entity didn't exist" not "no data". Choropleth greys (not hides) regions outside validity.

### Group 10 — Migration and deletion discipline

- **D13.** Rip-and-replace (no strangler-fig, no production feature flag). Site not yet live; strangler is overhead when no users depend on the old shape (R9). Isolated test harness is acceptable for the canonical writer/loader; a production toggle is not (R21).

- **D14.** Legacy JSON moves to `datasets/_old/` (Phase 0.13). Deletion of `_old/` is gated on an **explicit checklist**, not a phase date: (a) every reader rewritten and tested, (b) golden-path Playwright green, (c) `python -m yen_gov validate --root .` clean, (d) migration parity oracle green (THE PLAN §7 step 1.5), (e) admin v0 not blocking on `_old/` (Q10), (f) 5 days local observation. Until all six hold, `_old/` stays.

- **D24.** Migration ledger is a Phase 0 artifact (step 0.5). Every existing `datasets/_old/` indicator (~110 socio-economic + elections) is classified `migrated_in_phase_X` / `dropped_with_reason` / `queued_for_phase_Y`. Silent catalogue loss is not acceptable; rip-and-replace is.

- **D34.** Consolidation migration is a **one-shot dated script**, not a permanent module. Lives at `backend/yen_gov/canonical/migration/m20260520_consolidate_indicators.py`. Preserved for audit; never re-imported (R28). Module layout in `backend/yen_gov/canonical/`: `writer.py`, `reader.py`, `migration/`, `registry.py`. No `consolidator.py`.

- **D35.** Consolidation test tiers: unit (`backend/tests/canonical/test_consolidation_rules.py`, one test per collapse rule, fixture-driven) + integration (`backend/tests/canonical/test_migration_m20260520.py`, runs script against `tmp_path` fixture corpus of ~10 representative old shards, asserts row counts + FK integrity + indicator_id coverage). **Skip golden-byte** (R29) — writer determinism plus integration row-equality cover the invariant; golden-byte breaks on every legitimate writer tweak.

- **D36.** Deletion ledger format: `datasets/_old/DELETED.md` with columns `path | deleted_in_commit | replacement_indicator_id | replacement_facet_values (JSON object literal) | notes`. Plural replacements (one old → multiple new via facet-explode) handled by JSON in `replacement_facet_values`.

### Group 11 — Failure-state UX (functional correctness)

- **D17.** **Citizen-visible failure-state UX contract**: when DuckDB-WASM init / metadata fetch / partition Range fetch / query execution fails or times out, the page renders plain-language copy ("This data could not load right now") with a retry button, source/provenance visible where it can be resolved, and **never a raw stack trace**. The loader wraps every async stage and emits a typed result `{status: 'ok'|'loading'|'partial'|'failed', data?, reason?}`. Renderers MUST handle all four. Functional correctness includes "what the citizen sees while loading and when it has failed"; Phase 1 cannot ship without this. The row-shape for failed/partial cases reuses the `value_numeric` / `value_text` split (group 3) — there is no separate "missing" sentinel.

## Rejected alternatives

The 31 rows below are settled per THE PLAN §3. Each was either considered and rejected in rounds R1–R11, or is a band-aid that the canonical pivot makes unnecessary. The "Why" column is verbatim from THE PLAN.

| # | Rejected | Why |
| --- | --- | --- |
| R1 | Opaque `{key, label, frequency}` period token | OWID disagrees; loses sortability; SLM can't reason over it |
| R2 | t_instant / t_span / derived-view 5-guardrails model | Chasing tails — OWID `year:int` + `period_seq` is simpler and sufficient |
| R3 | Per-shard JSON files (folded indicator v4.0) | ~7,300 file proliferation; no SQL; smeared `fetched_at`; per-shard validation cost |
| R4 | `.data-card.json` sidecar per indicator | Same lifecycle-smushing as folded model |
| R5 | Global mutable `_inventory.json` | Underscore = confession of second-class; inventory derivable from data |
| R6 | SHA-gate on Fetcher + `.meta.json` per URL | Bytes ≠ data; UPSERT solves this one altitude up |
| R7 | `write_text_if_changed` byte-compare helpers | Same problem — fix non-determinism upstream of write seam |
| R8 | Period vocabulary normalisation (CLAUDE.md §10 pre-pivot rule) | Withdrawn under OWID adoption; `year:int` IS the normalisation, `period_label` stays verbatim |
| R9 | Strangler-fig coexistence of JSON + Parquet readers | Site not live; coexistence is pure cost |
| R10 | Per-CI dataset validation | No consumer to defend in this repo's CI |
| R11 | Frontend URL grammar change | Pure churn; Jony + Citizen rejected |
| R12 | SQL.js (sqlite-wasm) over DuckDB-WASM | DuckDB-WASM reads Parquet via HTTP Range natively; SQL.js needs full-file load |
| R13 | Migrations directory | Rebuild from upstream snapshots each run — cheaper than migration ceremony |
| R14 | URL `$id` in schemas | IDE offline support; relative path works everywhere |
| R15 | Item-level provenance overrides in `sources[]` (legacy v3.0 shape) | Removed in legacy v3.0 already; canonical uses `source_id` FK |
| R16 | `source_id` in the UPSERT identity hash | Conflates provenance with logical truth. A corrected upstream value rolls `content_hash` → new `source_id`; including it in the key would create a duplicate row for the same fact. Logical key is `(entity_id, year, period_label, indicator_id)` per D7. |
| R17 | Single `value:DOUBLE` column | Administrative data emits "Nil"/"N.A."/textual codes meaningful and distinct from null/zero. Split is D5/D17. |
| R18 | Hive partition by `year` | Destroys time-series query performance — every series query fans out to N partitions. Partition by `indicator_id` instead (D8). |
| R19 | Binary Parquet as hand-authored source of truth | Unreviewable in PR; not hand-editable. Authoring shape is JSON/CSV; Parquet is a compiled artifact (D18). |
| R20 | `caveats.parquet` as the home for methodology breaks | Two different citizen risks (cross-cadence join vs definitional break) need two surfaces with two banner copies (D16). |
| R21 | Production feature-flag coexistence of JSON and Parquet loaders | Conflicts with D13 rip-and-replace. Isolated test harness only; no production toggle. |
| R22 | Raw observation rows returned from the loader to citizen components | View-model contract per D19 — SQL stays in the loader, never in renderers. |
| R23 | File-discovery by frontend guessing `datasets/<family>/observations.parquet` paths | Brittle; partition policy becomes hidden contract. Use `datasets/manifest.json` (D21). |
| R24 | Forcing boundary geometry into Parquet / the canonical observation store | Geometry is not tabular; Parquet loses geometry-native operations (tile pyramids, simplification, GPU rendering). Sibling family + GeoJSON/PMTiles per D25. |
| R25 | Sweeping `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json` into `_old/` during Phase 0.13 | These are NOT pre-pivot artifacts; they're canonical-store siblings or the canonical store itself. Move applies to `datasets/indicators/`, `datasets/elections/`, `datasets/people/`, `datasets/governments/`, `datasets/events/`, `datasets/features/`, `datasets/reference/` (legacy) only. |
| R26 | `dimensions: MAP<VARCHAR,VARCHAR>` typed column on every observation row | At ~80–120 ids (and the §0b 500–1,000+ growth target), parent + `dimension_values:STRUCT` on the catalogue + selective facet-explode children scales without code rent. (c) would require registry + hash-extension + dimension-aware queries — code in 3 places, no Phase 1 external consumer. Gregor conceded R2. |
| R27 | Separate `geo_entity_id` + `fiscal_actor_id` for entity tiering | Hans picked single `entity_id` + `entity_type` enum per OWID precedent (D27). Max preferred separate columns and yielded; preference logged for Phase F revisit when fiscal-flow modelling lands. |
| R28 | Permanent `consolidator.py` module for 110→60 collapse | One-shot dated migration script under `backend/yen_gov/canonical/migration/` (D34). Behavioural one-shot ≠ structural permanent. |
| R29 | Golden-byte test for consolidation migration | ADR-0030 writer determinism + integration row-equality cover the invariant; golden-byte breaks on every legitimate writer tweak (D35). |
| R30 | Computing our own crime-rate denominator from interpolated Census | Smuggles a methodological choice into a "fact". Use NCRB-published rate as canonical even with known undercounts; expose count as facet (D33.3). |
| R31 | Smoothing a line across a methodology break | Bhattacharya rule. Break MUST be visible as vertical rule on time axis (D32) and the two methodologies are separate `indicator_id`s (D28). |

## Consequences

### Positive

- **One source of truth.** No JSON shadow tree. No coverage emitter producing a parallel completeness index. One row per observation, one catalogue row per indicator, one provenance row per `(url, content_hash)`.
- **SQL is back.** Cross-state / cross-indicator / cross-year questions are one DuckDB query, not a fan-out of fetches. The SLM dispatcher (Phase 4) becomes possible because the SLM has a single canonical schema in its system prompt.
- **Identity ≠ provenance.** Corrected upstream values UPSERT cleanly; provenance pointer rolls forward without duplicating the row (D7, R16).
- **`fetched_at` smear dissolves.** Re-ingest with identical bytes leaves `observations.parquet` bytes unchanged; only `last_seen_at` in `sources.parquet` ticks (D6).
- **Catalogue scales.** Parent + `dimension_values:STRUCT` + registered facet axes (D26, D31) absorb 500–1,000+ indicators without rework; URL grammar stays unchanged (D12, citizen contract).
- **Methodology breaks are honest.** D28 + D32 + D33.1 surface base-year rebases visibly on every chart that crosses them; the GSDP rebase no longer disappears into a smoothed line.
- **Static-first stays.** Pages + Parquet via HTTP Range. No backend at runtime, no CDN cache invalidation, no CI on `datasets/**` (D10, D11, CLAUDE.md Holy Law #1).

### Negative

- **Parquet is binary in git.** Diff review is impossible at the byte level; PR reviewers rely on the writer being deterministic plus the hand-authored JSON taxonomy (D18) for human review. Mitigation: the writer round-trip test asserts byte-identical re-emit (Phase 0.10).
- **DuckDB-WASM cold-start cost on first visit.** A few hundred kB of WASM plus the manifest fetch before any chart can render. Mitigation: failure-state UX (D17) renders plain-language loading copy; mobile-perf is descoped from gating per THE PLAN header stance.
- **Range-request dependence.** GitHub Pages must serve `.parquet` with `Accept-Ranges: bytes` and a sane MIME. Phase 0.7 verifies this on a deploy preview; if 206 + MIME do not hold, the pivot stalls until resolved.
- **Git repo size.** Parquet shards live in git. If clone time exceeds 60s or repo exceeds 2 GB (THE PLAN §14 open question), Fowler + Gregor convene on Git LFS vs Pages-only build artifact (Q2). Not a Phase-1 blocker; monitored at end of Phase 1.
- **Consolidation migration is a one-shot risk window.** The 110→~80–120 collapse runs once. If it loses an indicator the migration ledger (D24) misses, recovery requires re-ingesting from `_old/` (which is why D14 gates `_old/` deletion behind the migration parity oracle).

### Neutral

- **`coverage_*` columns are denormalised.** Recomputed at every emit; trade a small write cost for keeping the catalogue browseable from the browser without scanning observation Parquet.
- **Tier-B validation is local-only.** `python -m yen_gov validate --root .` runs before commit; no CI gate (D11). The frontend lives in a separate repo and pulls `datasets/**` at runtime, so this repo's CI has no consumer to defend.
- **Some `tools/` migration scripts retire later, not now.** See [deletion manifest](../canonical-pivot-deletion-manifest.md) §7 — most one-shot bump/migrate scripts wait for Phase 1.8.

## Implementation plan

Detailed in THE PLAN §6–§11:

- **Phase 0 (weeks 1–2)**: deletion manifest (0.0, ✓ merged), this ADR (0.1), `canonical-store.md` (0.2), 9 schemas (0.3), entities + facet-axes seed (0.4), migration ledger (0.5), manifest contract (0.6), Pages Range/MIME verification (0.7), DuckDB-WASM wiring (0.8), writer skeleton (0.9), Parquet contract tests (0.10), failure-state UX harness (0.11), ADR supersession (0.12), `_old/` move (0.13), ADR-0031 boundaries (0.14).
- **Phase 1 (weeks 3–6)**: elections migration; loader swap; migration parity oracle; `_old/` deletion gated on D14 checklist.
- **Phase 2 (weeks 7–9)**: first socio-economic family (energy).
- **Phase 3 (weeks 10–18)**: demography, fiscal, education, health (fiscal-actor doctrine per THE PLAN §9).
- **Phase 4 (weeks 19–22)**: SLM dispatcher with `sqlglot` or `EXPLAIN`-dry-run safety gate.
- **Phase 5 (weeks 23–26)**: admin rewrite.

Open questions Q1–Q11 (THE PLAN §12) are resolved at the phase that needs them.

## See also

- [THE PLAN](../../../TODO/20260517-canonical-long-format-pivot.md) — single source of truth (this ADR is settled inside it).
- [Canonical-pivot deletion manifest](../canonical-pivot-deletion-manifest.md) — what retires, when, and why.
- [`docs/architecture/data/canonical-store.md`](../data/canonical-store.md) — target architecture (**Phase 0.2, to be authored**; will include D30 naming convention and D31 facet-axes registry).
- ADR-0031 — boundary geometry strategy (**Phase 0.14, to be authored**; captures D25 scope, GeoJSON↔PMTiles cutover, future PCs/taluks/villages roadmap).
- [ADR-0026](0026-lift-collection-inventory-out-of-indicator-artifact.md), [ADR-0027](0027-cadence-as-separate-field-from-time-grain.md) — superseded by this ADR.
- [`CLAUDE.md`](../../../CLAUDE.md) §0a "The One Rule", §11 schema versioning, §12 data provenance.
- [`docs/agents/guardrails.md`](../../agents/guardrails.md) — rules digest.
- OWID ETL repo — pattern source for meadow/garden/grapher naming and the `origin.*` field schema adopted in D5.

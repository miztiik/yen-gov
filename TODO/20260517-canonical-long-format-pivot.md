# Canonical long-format pivot — handover plan

**Last Updated**: 2026-05-17 (R11 — Round-2 concurrence pass; this is THE plan document)
**Status**: Approved direction (user, R9). Agent reviews complete (R10 + R11). All five R2 agents (Hans, Max, Gregor, Fowler, Jony) accepted Hans+Max as data-shape authority and concurred on the contract. User signed off on R2 residuals 2026-05-17. **Ready for Phase 0 implementation.**
**ADR**: [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) (to be authored Phase 0 step 0.1, must incorporate R11 decisions).
**Supersedes**: ADR-0026 (folded-indicator), ADR-0027 (cadence-as-separate-field), and all per-shard JSON doctrine in `docs/concepts/folded-indicator.md` + `docs/concepts/collection-inventory.md` (now marked obsolete).

**Stance on performance**: functional correctness first. Mobile-performance polish is **not** an implementation-phase blocker; it is tracked but does not gate Phase 0–3. We do, however, need an explicit *failure-state UX contract* (see D17) because functional correctness includes "what the citizen sees when the loader is still loading or has failed."

---

## §0a. THIS IS THE PLAN DOCUMENT (read me first)

**Single source of truth**: `TODO/20260517-canonical-long-format-pivot.md` (this file). All implementation work follows this document. Do not invent parallel plans. If something is missing, add it here, do not start a sibling doc.

**Input artifacts** (referenced FROM this plan; not themselves the plan):

| Path | Role | Status |
| --- | --- | --- |
| `TODO/20260517-canonical-long-format-pivot.md` | **THE plan** (you are here) | authoritative |
| `TODO/20260517-indicator-corpus-survey.md` | Factual baseline: 110-ID enumeration from `datasets/indicators/in/` | input — read once |
| `TODO/20260517-indicator-consolidation-audit.md` | Max+Hans consolidation pass: 110 → ~60 parents → ~80–120 ids | input — read once; §2/§7 contain known hallucinations flagged in audit, treat as directional |
| `TODO/20260517-tcpd-tn-ae-people-sidecar-plan.md` | Older sidecar plan (TCPD-TN elections); does NOT supersede this plan | reference only |
| `TODO/sources.md` | Source backlog tracker | reference |

**On conflict**: this plan wins. Period.

---

## §0b. INDICATOR CARDINALITY IS A MOVING TARGET (read this twice)

The "~60 parents / ~80–120 indicator_ids" figure in the consolidation audit is the **count of what we have ingested so far** — it is NOT the steady-state count of yen-gov indicators. It will grow substantially as new source domains are ingested. The contract must be designed for **growth**, not for the snapshot.

**Not yet ingested** (each may contribute 10–50+ indicators):

- **Judiciary** — pendency by court level, vacancy ratios, conviction rates, prisoners, undertrials, bail rates (NJDG, NCRB-Prison Statistics, Supreme Court data).
- **Healthcare** — disease burden (NCD/communicable), hospital infrastructure per capita, doctor density, immunization full-coverage, NFHS-5 deep cuts, HMIS service utilisation, drug stockouts (HMIS, NHM dashboard, NFHS-5/6 micro).
- **Water resources** — groundwater extraction by block, river basin flows, drinking-water coverage, irrigation reach, reservoir levels (CGWB, CWC, Jal Shakti).
- **Crime & policing** — IPC + SLL by category, police strength per 100k, women's safety, custodial deaths (NCRB, BPRD).
- **Education (deep)** — UDISE+ school-level rolls, AISHE higher-ed, NIRF rankings, PARAKH learning outcomes, pupil-teacher ratio per district, dropout cohorts (UDISE+, AISHE, NIRF, NAS/PARAKH).
- **Environment (deep)** — air quality per monitoring station, forest cover change, biodiversity (CPCB, FSI, ENVIS).
- **Transport (deep)** — Vahan registrations, IR passenger/freight per zone, road accident fatalities by NH (MoRTH, Vahan, IR Annual Stats).
- **Agriculture (deep)** — crop production per district per season, MSP procurement, soil health (DA&FW, FCI, Soil Health Card).
- **Welfare schemes** — MGNREGA person-days per GP, PMAY houses built per district, PDS offtake per state (NREGAsoft, PMAY-G, PDS portal).
- **Local government finance** — ULB / Panchayat own-revenue and grants (FFC/SFC reports, RBI municipal finances).

**Implication for the contract**: the catalogue MUST scale to **500–1,000+ indicator_ids over 2-3 years** without architectural change. The R2 picks (parent + `dimension_values:STRUCT` + selective facet-explode + manifest-driven discovery + Hive partition by `indicator_id`) all support this growth path. Do NOT design as if 80–120 is the destination.

**Implication for Phase 0 catalogue seed**: include placeholder topic stubs (`judiciary`, `healthcare`, `water`, `crime`, `education_deep`, `welfare`, `local_govt_finance`) in `taxonomy/indicators.json` schema enumeration even if zero rows yet. The schema MUST accept future topics without bump.

---

## §0c. BOUNDARIES PRESERVATION — DO NOT DELETE (critical, repeated)

**`datasets/boundaries/` IS NOT LEGACY.** It is a sibling family to the canonical Parquet store (D25). The R10 boundaries pass + R11 confirm:

- Phase 0.13 `_old/` move **EXCLUDES** `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json` (per R25).
- Phase 1.8 `_old/` deletion **NEVER TOUCHES** `datasets/boundaries/`.
- Existing files preserved as-is: `boundaries/in/country/IN.json`, `boundaries/in/geojson/{india-states, india-districts, india-soi}.geojson`, `boundaries/in/geojson/S01-ac.geojson` through `S2x-ac.geojson` + all `.sources.json` sidecars.
- Future additions (PCs, taluks/sub-districts, village coverage) follow the same `datasets/boundaries/in/{geojson|pmtiles}/` layout. When a layer exceeds ~10 MB GeoJSON, switch that layer to PMTiles (Q11).
- Any agent proposing to move, rename, or delete a file under `datasets/boundaries/` MUST escalate to the user. There is no implementation step in this plan that touches that tree except to ADD new layers.

**If you are an execution agent and you find yourself running `git rm` or `git mv` on anything under `datasets/boundaries/`, STOP. You are doing something this plan forbids.**

---

## §1. The One Rule (read first; any coding agent)

> **OWID is the canonical reference for socio-economic data modelling.** Adopt verbatim. Deviate only with Hans + Max sign-off documented in [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md).

### Authority assignment (resolves agent stalls)

| Decision class | Authority |
| --- | --- |
| Data shape — columns, enums, period axis, entity IDs, indicator metadata, sources schema, taxonomy | **Hans + Max** |
| Contract / integration — schema versioning, write seams, layer boundaries, pipes-and-filters | **Gregor** |
| Engineering craft — refactor safety, test tiers, module structure, deletion | **Fowler** |
| UX — URL grammar, visual bounds, copy, citizen framing | **Jony + Citizen** |

**User approval supersedes every agent and every rule.** Already granted for OWID adoption.

### Canonical row (memorise)

```
observations: (
  observation_id,    -- sha256(entity_id || year || period_label || indicator_id)
  entity_id,         -- FK -> taxonomy/entities.parquet
  year:int,          -- end-year convention (FY 2024-25 -> 2025)
  period_label:text, -- verbatim publisher string ("FY 2024-25", "Q3 2024-25")
  period_seq:int,    -- monotonic intra-year sort key (1..N per year per indicator)
  indicator_id,      -- FK -> taxonomy/indicators.parquet
  value_numeric:DOUBLE,  -- nullable; numeric reading
  value_text:VARCHAR,    -- nullable; for "Nil"/"N.A."/categorical
  source_id          -- FK -> taxonomy/sources.parquet (provenance, NOT identity)
)
```

**Identity vs provenance (critical, amended in R10):**

- **Logical key** (what makes a row unique): `(entity_id, year, period_label, indicator_id)` — never `source_id`. A corrected upstream value from the same publisher keeps the same logical row; the UPSERT updates value/source pointers, it does not duplicate.
- **`observation_id`** is a stable hash of the logical key for UPSERT efficiency. Does NOT include `source_id`.
- **`source_id`** is provenance FK only. Carrying it on the row lets us answer "which source row backs this fact" without breaking identity when content_hash rolls forward.
- **`period_seq`** is the intra-year sort key: for `cadence='monthly_cy'`, period_seq=1..12; for `quarterly_fy`, 1..4; for `annual_*` and `decennial`, period_seq=1. The renderer sorts by `(year, period_seq)`; the citizen sees `period_label`.
- **`value_numeric` / `value_text`** split: administrative data emits "Nil", "N.A.", "Not reported" as meaningful tokens distinct from zero or null. Both columns nullable; exactly one populated per row (writer enforces).

### Frontend URL contract — DOES NOT CHANGE

Citizen URLs stay as-is. Only loader internals swap. Touch points: `frontend/src/lib/data.ts` (lines ~217, ~221, ~353, ~374) and `frontend/src/lib/paths.ts:15`. Everything else (route grammar, slugs, deep-links) is unchanged.

### Citizen renderer rule (amended R10)

- **Sorting/querying**: always `year:int` + `period_seq` (machine axis).
- **Display**: always `period_label` verbatim (citizen axis). Axis ticks, tooltips, legends, slider captions, share-link previews, and footer attribution show `period_label`, never the bare integer year. Showing "2025" when the source says "FY 2024-25" is a defect.
- **Tooltips** include: `period_label`, `value` (numeric or text), `indicator_id`-derived unit, source producer + license badge.

---

## §2. Decisions (approved this thread)

| # | Decision | Authority | Rationale |
| --- | --- | --- | --- |
| D1 | Canonical store = Hive-partitioned Parquet read by DuckDB-WASM in the browser | User + Gregor + Fowler | Static-hostable (GitHub Pages), SQL-queryable, columnar, OSS-mature |
| D2 | OWID `year:int` is the time axis (end-year for FY) | User (overrides debate) | OWID precedent, supports `WHERE year >= 2020`, simpler than struct |
| D3 | `period_label` is verbatim publisher string (not normalised) AND is the citizen-visible time string | Hans + Max + Jony + Citizen | Citizen-readable as-published; no information loss; renderer rule per §1 |
| D4 | Long-format only — one observation per row | Hans + Max (OWID) | Schema stability across cadences; trivial pivoting in SQL |
| D5 | Sources = TABLE (`taxonomy/sources.parquet`) with OWID `origin.*` fields **plus yen-gov extensions** | Hans + Max | FK-keyed dedup; replaces per-file `sources[]` smearing. **R10:** OWID `origin.*` fields stay verbatim (`producer`, `citation_full`, `url_main`, `url_download`, `date_accessed`, `license`, `vintage`). yen-gov extensions are explicitly tagged in `canonical-store.md`: `source_id` (PK), `content_hash`, `first_fetched_at`, `last_seen_at`, `confidence_tier:enum(gold\|silver\|bronze)`, `is_issuing_authority:bool`. Curating from mixed-quality Indian shelves (issuing authority vs research re-publisher vs single-paper bronze) requires the confidence signal; OWID doesn't carry it because its editorial gate happens upstream of the table. |
| D6 | `first_fetched_at` (immutable) + `last_seen_at` (mutable) replace `fetched_at` | Gregor + Hans | Dissolves the `fetched_at` smear problem |
| D7 | UPSERT-into-DuckDB + sorted Parquet emit; logical key = `(entity_id, year, period_label, indicator_id)` | Gregor + Fowler | Identity is upstream-truth, not provenance-shaped. `source_id` is a row attribute, NOT in the key. |
| D8 | Hive partition only when family > 15 MB; partition by **`indicator_id`** (or `topic_id`) when partitioned — NEVER by `year`; shards ≤ 4 MB target 1.5 MB | Gregor + Fowler (R10) | Time-series queries scan ALL years for one indicator; partitioning by year forces N-file metadata fetch per series. Partitioning by indicator keeps each series in one shard. |
| D9 | Local schema `$id` (relative path `./<name>.schema.json`), not URL | Gregor + Fowler | IDE offline validation; no broken-link rot |
| D10 | No JSON projections of canonical data for frontend | Gregor + Fowler | Single source of truth; DuckDB-WASM reads Parquet directly |
| D11 | No CI on `datasets/**` — publish is plain static copy via Pages | Fowler | Costless; matches static-first Holy Law |
| D12 | Frontend URLs unchanged under pivot | Jony + Citizen | Zero citizen-facing breakage |
| D13 | Rip-and-replace (no strangler-fig, no feature flag in production) — site not yet live | User + Fowler | Strangler is overhead when no users depend on old shape. **R10:** removes "behind a feature flag" from Phase 0; only isolated test harness is acceptable. |
| D14 | Legacy JSON moves to `datasets/_old/`; deletion gated on an **explicit checklist**, not a phase date | Fowler (R10) | See §7 step 1.6 — deletion criteria are (a) every reader rewritten + tested, (b) golden-path Playwright green, (c) `python -m yen_gov validate` clean, (d) migration parity oracle (§7 step 1.5) green, (e) admin v0 not blocking on `_old/`, (f) 5 days local observation. |
| D15 | `cadence` lives on indicator row; **indicator catalogue carries the full Hans honesty surface** | Hans + Max (R10) | Cadence is property of the series; OWID-style indicator browser needs the catalogue logic that prevents bad rankings. See §5 indicator schema. |
| D16 | `caveats.parquet` is for **cross-cadence misleading-join banners only**; `methodology_breaks.parquet` is a **separate typed surface** | Hans + Jony (R10) | Cross-cadence joins and methodology/base-year breaks are distinct citizen risks; conflating them merges two different banner copies into one ambiguous channel. |
| D17 | **Citizen-visible failure-state UX contract** — when DuckDB-WASM init / metadata fetch / partition Range fetch / query execution fails or times out, the page renders plain-language copy ("This data could not load right now") with retry, source/provenance visible where possible, and never a raw stack trace | Jony + Citizen (R10) | Functional correctness includes "what the citizen sees while the loader is loading and when it has failed." Phase 1 cannot ship without this. |
| D18 | **Hand-authored taxonomy files are TEXT (JSON or CSV) in git**; the pipeline compiles them into Parquet at ingest | Fowler + Hans (R10) | Parquet is binary; `operator_state.parquet` and `caveats.parquet` would be unreviewable in PR. Authored shape: `datasets/taxonomy/operator_state.json`, `datasets/taxonomy/caveats.json`, `datasets/taxonomy/methodology_breaks.json` — all text, all schema-validated. Ingest compiles to matching `.parquet` for DuckDB consumption. Derived parquet files MAY or MAY NOT be committed (decision Q9). |
| D19 | **Chart-ready view-model loader** is a frontend contract — the DuckDB-WASM loader returns shaped view-models, never raw observation rows | Jony + Gregor (R10) | The loader joins `observations` + `taxonomy/indicators` + `taxonomy/sources` + `caveats` + `methodology_breaks` into the metadata-rich shape generic renderers consume (unit, direction, cadence, comparability, source display, license, caveat/break banners). Prevents SQL from leaking into `IndicatorChoropleth`, `StackedTrend`, route files. |
| D20 | **Typed adapter→writer batch envelope** is the canonical message contract | Gregor (R10) | Pipes-and-filters: `{ target_family, schema_version, source_rows[], observation_rows[], dimension_rows[]?, replacement_semantics }`. Every adapter speaks this envelope; the writer is a single Message Translator. |
| D21 | **Parquet schema version + table id live in Parquet key-value metadata** AND a typed manifest file at `datasets/manifest.json` | Gregor (R10) | JSON Schema `$schema_version` does not apply to Parquet; need explicit mechanism. Reader fails loud on unsupported version. Manifest enumerates `{table_id, family, partition_columns, files[], schema_version, row_count}` so the browser does file discovery via control-plane, not by guessing paths. |
| D22 | **FK referential integrity enforced at write time** by the backend writer/validator | Fowler + Gregor (R10) | DuckDB-WASM via HTTP Range cannot enforce FKs in production. Phase 0.6/0.8 writer asserts no dangling `indicator_id` / `source_id` / `entity_id` in observations before emit. Validator covers it. |
| D23 | **Entities carry validity windows** — `entity_valid_from:int`, `entity_valid_to:int|null` | Jony + Hans (R10) | Telangana (2014), J&K/Ladakh (2019) — pre-statehood absences must read as "entity didn't exist" not "no data." Choropleth greys (not hides) regions outside validity. |
| D24 | **Migration ledger is a Phase 0 artifact** — every existing `_old/` indicator is classified migrated / dropped-with-reason / queued before `_old/` can be deleted | Max + Fowler (R10) | Repo has ~110 socio-economic artifacts plus elections. Silent catalogue loss is not acceptable; rip-and-replace is. |
| D26 (R11) | **Facet handling = (b) facet-explode** with parent+children pattern: parent indicator carries `parent_indicator_id NULL`, children carry `parent_indicator_id` FK back to parent + `dimension_values:STRUCT` populated. Selective explode rule (Hans): explode iff the facet changes the **citizen's governance question**; otherwise keep as observation-row facet. | Hans + Max + Fowler + Jony + Citizen (5/6 R1; Gregor conceded R2) | At target cardinality (~80–120 ids now, 500–1,000+ over 3 years), parent+`dims` hybrid scales without code rent; URL grammar stays `/indicator/<id>` with no facet picker; legend stays single code path. |
| D27 (R11) | **Entity tiering = (i) single `entity_id` + `entity_type` enum** (`state`, `district`, `ulb`, `union_govt`, `state_govt`, `discom`, `psu`, …). Max preferred (ii) separate geo/fiscal columns; yielded to Hans per §0a authority. Double-entry transfer rows deferred to Phase F. | Hans (Max yielded; recorded as deviation rationale for Phase F revisit) | OWID-canonical shape; sufficient for Phase 1–3; defer fiscal-flow modelling complexity until the data exists. |
| D28 (R11) | **methodology_version = compose Hans + Fowler** — BOTH (iii) FK to `methodology_breaks.parquet` (table carries narrative for chart splice markers) AND (ii) id-encoded break in `indicator_id` (e.g. `state-gsdp-base-2011-12-inr-crore` separate id from `state-gsdp-base-2004-05-inr-crore`). They compose, do not conflict. URL carries the visible break; table carries the prose. | Hans + Fowler (composite, user-approved R2) | Splits cleanly: governance-visibility (URL/id) + narrative-richness (table). One join at chart time, ~50 table rows total, no rent on every observation row. |
| D29 (R11) | **Indicator catalogue column shape** (extends D15): `id` (kebab-case, ≤60 chars), `display_name`, `parent_indicator_id NULL` (self-FK), `dimension_values:STRUCT NULL` (populated iff `parent_indicator_id IS NOT NULL`), plus all D15 honesty fields, plus `methodology_version VARCHAR NULL` (FK to `methodology_breaks`), plus `source_id` per child (NOT shared across siblings — children may have different upstreams). | Max + Hans (R2) | Per-child source_id (vs per-parent): coal-capacity from CEA and solar-capacity from MNRE are siblings with different sources; per-child is correct. Max answered Fowler's R1 question. |
| D30 (R11) | **Indicator naming convention**: `<entity>-<measure>-<unit>-<facet>`, kebab-case, single segment, max 60 chars. Sibling sort works via `ORDER BY id`. Approved abbreviations: `nsdp`, `gsdp`, `cpi`, `imr`, `mmr`, `tfr`, `mw`, `gwh`, `mu`, `inr`, `pct`. New abbreviations require Max sign-off. Methodology-version children encode the version in id (`-base-2011-12`). | Max + Jony (R2) | Greppable, deterministic, no hash. Documented in `docs/architecture/data/canonical-store.md` per Gregor's R2 concession term. |
| D31 (R11) | **Registered facet axes** — `datasets/taxonomy/facet-axes.json` (schema-versioned per §11) enumerates allowed `dimension_values` keys: `fuel_type`, `sector`, `head_of_account`, `gender`, `residence`, `prices_basis`, `methodology_version`, `transfer_type`, `category`, `crime_category`, `cpi_category`, plus axes added by Phase 2/3 ingestion. Catalogue validator REJECTS any `dimension_values` key not in this registry. | Gregor (R2 concession) | Canonical Data Model boundary; prevents ad-hoc dimension proliferation as the corpus grows (especially relevant given §0b growth path). |
| D32 (R11) | **Chart-shell view-model addition**: D19's loader return shape gains `breaks: [{period_seq, methodology_version, note}]`. Rendered as thin vertical rule on time axis, visible at rest (NOT tooltip-only). `breaks: []` when none. | Jony (R2) | Surfaces D28 methodology_version visibly; one code path; satisfies Hans's "never smooth a line across a methodology rupture" rule. |
| D33 (R11) | **Eight governance answers (Hans R2)** locked into the catalogue + breaks design — see [`TODO/20260517-indicator-consolidation-audit.md`](20260517-indicator-consolidation-audit.md) §7 for question text; answers below: | Hans (R2) | Each resolves a class of consolidation decision that will repeat as new domains land (§0b). |
| D33.1 | GSDP base-year revisions → `methodology_version` on same `indicator_id` PLUS id-encoded variant per D28; chart shows visible break-marker. Same rule for IIP, WPI, CPI, Census rebases. |  | |
| D33.2 | Distribution losses (T&D vs AT&C vs distribution-only) → ONE parent `state-distribution-losses-pct` + `loss_type` facet. Default AT&C, fall back to T&D, annotate switch. |  | |
| D33.3 | Cognizable crimes → keep BOTH count and rate-per-100k as measure facets on one parent. Canonical = NCRB-published rate (provenance honesty). Do NOT compute own rate from interpolated Census. |  | |
| D33.4 | Census H-series vs NFHS amenities → TWO parents (`-census-h-series`, `-nfhs`). Different universes/methodologies/cadences. Cross-link via `related_indicators`. |  | |
| D33.5 | Derived indicators (sex ratio, density, urbanization %, road density, forest cover %) → FIRST-CLASS parents. Store as observed; don't re-derive. |  | |
| D33.6 | Voter turnout GE vs AE → TWO parents. AE staggered, GE synchronised — different temporal logic. |  | |
| D33.7 | CPI categories → `combined_yoy` as facet value alongside food/fuel/housing/general. Don't re-derive aggregates. |  | |
| D33.8 | `fuel_type=total` coexistence → explode REPLACES the total. Total is compute-on-read (`SUM(value) GROUP BY state, year`). |  | |
| D34 (R11) | **Consolidation migration is one-shot dated script**, not a permanent module. Lives at `backend/yen_gov/canonical/migration/m20260520_consolidate_indicators.py`. Preserved for audit; never re-imported. Module layout in `backend/yen_gov/canonical/`: `writer.py`, `reader.py`, `migration/`, `registry.py`. No `consolidator.py`. | Fowler (R2) | Two-hat: consolidation is behavioural (one-shot); module structure is structural (permanent). Don't share a home. |
| D35 (R11) | **Consolidation test tiers**: unit (`backend/tests/canonical/test_consolidation_rules.py`, one test per collapse rule, fixture-driven) + integration (`backend/tests/canonical/test_migration_m20260520.py`, runs script against `tmp_path` fixture corpus of ~10 representative old shards, asserts row counts + FK integrity + indicator_id coverage). **Skip golden-byte** — ADR-0030 writer determinism + integration row-equality cover the invariant. | Fowler (R2) | Per CLAUDE.md §15 tier policy; aligns with no-corpus-walk rule (§10). |
| D36 (R11) | **Deletion ledger format**: `datasets/_old/DELETED.md` columns = `path | deleted_in_commit | replacement_indicator_id | replacement_facet_values (JSON object literal) | notes`. Plural replacements (one old → multiple new via facet-explode) handled by JSON in `replacement_facet_values`. | Fowler (R2) | Markdown for human readability; JSON literal in column for parseability if ever needed. |
| D25 | **Boundary geometry lives outside the canonical Parquet store** in a sibling family `datasets/boundaries/in/`; referenced from observations via `entity_id` FK that resolves through `taxonomy/entities.json` (which carries `entity_level` + boundary-file pointer). Format split by size: **GeoJSON** for small layers (country, states, ~few MB), **PMTiles** for large layers (national districts, ACs, PCs, sub-districts/taluks, villages — single-file vector tile archive served via HTTP Range, read natively by maplibre-gl). Boundary files are **EXCLUDED** from the §6 Phase 0.13 `_old/` move and from the §7 Phase 1.8 `_old/` deletion. The existing `datasets/boundaries/in/` tree (country IN, india-soi/states/districts GeoJSON, per-state AC GeoJSON for S01–S2x) is preserved as-is; future additions (PCs, taluks, completing village coverage) follow the same layout. `datasets/manifest.json` (D21) enumerates boundary files alongside observation Parquet so the frontend discovers them via control-plane, not by guessing paths. | Jony + Gregor (R10 boundaries pass) | Vector geometry is not tabular; forcing it into Parquet loses geometry-native operations (simplification, tile pyramids, GPU rendering). Canonical store stays focused on observations; geometry stays in the format the GIS world already solved. Full rationale → ADR-0031 (to author Phase 0). |

---

## §3. Rejected alternatives (do not re-propose)

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
| R16 (R10) | `source_id` in the UPSERT identity hash | Conflates provenance with logical truth. A corrected upstream value rolls `content_hash` → new `source_id`; including it in the key would create a duplicate row for the same fact. Logical key is `(entity_id, year, period_label, indicator_id)` per D7. |
| R17 (R10) | Single `value:DOUBLE` column | Administrative data emits "Nil"/"N.A."/textual codes meaningful and distinct from null/zero. Split is D5/D17. |
| R18 (R10) | Hive partition by `year` | Destroys time-series query performance — every series query fans out to N partitions. Partition by `indicator_id` instead (D8). |
| R19 (R10) | Binary Parquet as hand-authored source of truth (`operator_state.parquet`, `caveats.parquet` committed as authoring shape) | Unreviewable in PR; not hand-editable. Authoring shape is JSON/CSV; Parquet is a compiled artifact (D18). |
| R20 (R10) | `caveats.parquet` as the home for methodology breaks | Two different citizen risks (cross-cadence join vs definitional break) need two surfaces with two banner copies (D16). |
| R21 (R10) | Production feature-flag coexistence of JSON and Parquet loaders | Conflicts with D13 rip-and-replace. Isolated test harness only; no production toggle. |
| R22 (R10) | Raw observation rows returned from the loader to citizen components | View-model contract per D19 — SQL stays in the loader, never in renderers. |
| R23 (R10) | File-discovery by frontend guessing `datasets/<family>/observations.parquet` paths | Brittle; partition policy becomes hidden contract. Use `datasets/manifest.json` (D21). |
| R24 (R10) | Forcing boundary geometry into Parquet / the canonical observation store | Geometry is not tabular; Parquet loses geometry-native operations (tile pyramids, simplification, GPU rendering). Sibling family + GeoJSON/PMTiles per D25. |
| R25 (R10) | Sweeping `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json` into `_old/` during the Phase 0.13 move | These are NOT pre-pivot artifacts; they're canonical-store siblings or the canonical store itself. Move applies to `datasets/indicators/`, `datasets/elections/`, `datasets/people/`, `datasets/governments/`, `datasets/events/`, `datasets/features/`, `datasets/reference/` (legacy) only. |
| R26 (R11) | **`dimensions: MAP<VARCHAR,VARCHAR>` typed column on every observation row** (Gregor's R1 option (c)) | At ~80–120 ids (and even at the §0b 500–1,000+ growth target), parent + `dimension_values:STRUCT` on the catalogue + selective facet-explode children scales without code rent. (c) would require registry + hash-extension + dimension-aware queries — code in 3 places, no Phase 1 external consumer. Gregor conceded R2. |
| R27 (R11) | **`(ii) separate `geo_entity_id` + `fiscal_actor_id`** for entity tiering | Hans picked (i) single `entity_id` + `entity_type` enum per OWID precedent (D27). Max preferred (ii) and yielded; preference logged for Phase F revisit when fiscal-flow modelling lands. |
| R28 (R11) | **Permanent `consolidator.py` module** for 110→60 collapse | One-shot dated migration script under `backend/yen_gov/canonical/migration/` (D34). Behavioural one-shot ≠ structural permanent. |
| R29 (R11) | **Golden-byte test for consolidation migration** | ADR-0030 writer determinism + integration row-equality cover the invariant; golden-byte breaks on every legitimate writer tweak (D35). |
| R30 (R11) | **Computing our own crime-rate denominator from interpolated Census** | Smuggles a methodological choice into a "fact". Use NCRB-published rate as canonical even with known undercounts; expose count as facet (D33.3). |
| R31 (R11) | **Smoothing a line across a methodology break** (e.g. plotting GSDP across NAS 2004-05 → 2011-12 rebase as continuous) | Bhattacharya rule. Break MUST be visible as vertical rule on time axis (D32) and the two methodologies are separate `indicator_id`s (D28). |

---

## §4. CLAUDE.md amendments (done this thread)

| Section | Change | Status |
| --- | --- | --- |
| Header | Project description names DuckDB-WASM pivot; date 2026-05-17 | ✅ done |
| §0a NEW | "The One Rule" — OWID canonical + authority table + user-supersedes | ✅ done |
| §2 | Ephemeral runtime clause; broadened POSIX/relative scope | ✅ done |
| §3 | `datasets/` row rewritten for canonical store | ✅ done |
| §10 | REMOVED period-vocabulary normalisation ban; REMOVED coverage.temporal parse ban; rewrote `fetched_at` bullet (sources-as-table); rewrote `write_text_if_changed` bullet (UPSERT); ADDED no-JSON-projection + no-CI-on-datasets | ✅ done |
| §11 | `$id` rule: relative path local, not URL | ✅ done |
| §12 | §12.1 canonical Parquet sources.parquet (OWID `origin.*` + yen-gov extensions); §12.2 legacy JSON in `_old/` read-only | ✅ done |
| §14 | Added Git LFS monitoring open question; noted time-window queries resolved by §0a | ✅ done |

### Mirror amendments (done this thread)

| File | Status |
| --- | --- |
| `docs/agents/guardrails.md` | ✅ done |
| `docs/concepts/folded-indicator.md` (obsolescence header) | ✅ done |
| `docs/concepts/collection-inventory.md` (obsolescence header) | ✅ done |
| `backend/yen_gov/AGENTS.md` | ✅ done |
| `admin/AGENTS.md` (canonical pivot invariant) | ✅ done |
| `frontend/src/AGENTS.md` (runtime DuckDB-WASM read path; remove build-time stale claim) | ✅ done |

### Outstanding doc cleanups (Phase 0 day-1; expanded in R10)

| File | Action |
| --- | --- |
| `docs/architecture/decisions/0026-...md` | Header: superseded by ADR-0030 |
| `docs/architecture/decisions/0027-...md` | Header: superseded by ADR-0030 |
| `docs/architecture/decisions/0003-no-fetch-cache.md` | Re-check |
| `docs/concepts/data-quality.md` | Re-check for `{key,label,frequency}` references |
| `docs/concepts/data-provenance.md` (R10) | Rewrite for sources-as-table + `source_id` FK + OWID origin.* + yen-gov extensions |
| `docs/concepts/owid-alignment.md` | Reframe as "we adopt OWID, not just align with it" |
| `docs/concepts/data-flow.md` (R10) | Update for adapter→writer batch envelope (D20) + UPSERT path |
| `docs/architecture/frontend/data-loading.md` (R10) | Rewrite for DuckDB-WASM + view-model loader (D19) + failure-state UX (D17) + manifest-driven discovery (D21) |
| `docs/architecture/frontend/deployment.md` (R10) | Verify Pages serves `.parquet` with `Accept-Ranges` and correct MIME |
| `docs/architecture/backend/schemas.md` (R10) | Update for canonical schemas + Parquet schema-version mechanism (D21) |
| `docs/architecture/backend/core.md` (R10) | Update for writer module + FK enforcement (D22) |
| `docs/architecture/backend/pipeline.md` (R10) | Update for batch envelope (D20) |
| `docs/architecture/admin/overview.md` (R10) | Note Phase 5 rewrite + interim admin v0 stance (see §7 step 1.7) |
| `docs/how-to/force-recollect.md` | Rewrite — under UPSERT, force = `DELETE FROM <family> WHERE indicator_id=... AND source_id=... ; re-ingest` (logical key, not just source) |
| `docs/architecture/decisions/0031-boundary-geometry-strategy.md` (R10 boundaries) | NEW ADR — captures D25 boundary scope (GeoJSON vs PMTiles cutover, sibling-family stance, manifest integration, future PCs/taluks/villages roadmap) |
| `docs/architecture/data/boundaries.md` (R10 boundaries) | NEW — boundary file inventory + format-per-level table + how entity_id resolves to geometry |
| `README.md` | One-paragraph update naming canonical store |

---

## §5. Target architecture (one-page spec; amended R10)

### Files committed to git

```
datasets/
  manifest.json            # control-plane: {tables[], schema_version, files[], partition_columns, row_counts}
  schemas/
    observation.schema.json
    indicator.schema.json
    source.schema.json
    entity.schema.json
    caveat.schema.json
    methodology-break.schema.json
    operator-state.schema.json
    manifest.schema.json
  taxonomy/
    entities.json          # HAND-AUTHORED (text, PR-reviewable)
    indicators.json        # HAND-AUTHORED + Hans honesty fields
    operator_state.json    # HAND-AUTHORED
    caveats.json           # HAND-AUTHORED
    methodology_breaks.json # HAND-AUTHORED
    sources.json           # GENERATED by adapters (one row per (url, content_hash))
    # compiled Parquet variants (decision Q9 whether committed or rebuilt locally):
    entities.parquet
    indicators.parquet
    operator_state.parquet
    caveats.parquet
    methodology_breaks.parquet
    sources.parquet
  elections/
    observations.parquet   # if family <15MB; else indicator_id=<id>/observations.parquet
  energy/
    observations.parquet
  demography/
  fiscal/
  education/
  health/
  boundaries/              # SIBLING family — NOT in canonical Parquet store (D25)
    in/
      country/IN.json            # GeoJSON, country outline
      geojson/
        india-states.geojson
        india-districts.geojson
        india-soi.geojson
        S01-ac.geojson .. S2x-ac.geojson  # per-state AC GeoJSON (existing)
        *.sources.json             # sidecar provenance (preserved)
      pmtiles/                     # future: district / AC / PC / village PMTiles when GeoJSON too large
  _old/                    # pre-pivot per-shard JSON; EXCLUDES boundaries/, taxonomy/, schemas/, manifest.json (R25); deletion gated on §7 checklist
```

### Indicator schema (D15 — Hans honesty surface, R10)

`taxonomy/indicators.json` row shape — minimum columns:

| Column | Why |
| --- | --- |
| `indicator_id` | PK |
| `label_short`, `label_long` | Axis text vs hover text |
| `description_short`, `description_long` | What the indicator IS (OWID separates from label) |
| `unit` | Display unit (e.g. "%", "INR crore", "per 1,000 live births") |
| `cadence` | annual_fy / annual_cy / quarterly_fy / quarterly_cy / monthly_cy / decennial / ad_hoc |
| `default_period_seq_for_cadence` | so chart picks a single cadence when multiple exist |
| `family` | Storage axis (elections, energy, …) — partition column when applicable |
| `pillar` | Curation axis: People / Money / Infrastructure / Politics |
| `topic_tags[]` | Free-tagged for catalogue browse |
| `value_kind` | absolute / rate / ratio / count / index / percentage |
| `direction` | higher_is_better / lower_is_better / no_judgement |
| `denominator` | for rates/ratios — what they're per |
| `attribution_geography` | place of incidence / billing / domicile / production (esp. fiscal) |
| `comparability` | states_combined / per_state / not_comparable_across_states |
| `implementing_authority` | Union / State / both / private / unspecified |
| `funding_split` | Union-share / State-share notes (fiscal indicators) |
| `methodology_vintage` | when the current definition came into force |
| `revision_tier` | first_release / revised / final |
| `excluded_notes` | what is NOT in this indicator (Hans framing) |
| `methodology_break_ids[]` | FK[] -> methodology_breaks.json |
| `series_breaks_summary` | one-line citizen-facing |
| `latest_break_year:int | null` | denormalised for chart break-rule trip-wire |
| `breaks_count:int` | denormalised |
| `coverage_states_count:int` | denormalised — supports "≥80% states" filter |
| `coverage_year_min`, `coverage_year_max:int` | denormalised |
| `coverage_density:float` | denormalised — % of (entity × year) cells observed |

`coverage_*` columns are recomputed at every emit; they exist to keep the catalogue browseable without scanning multi-GB observation Parquet from the browser.

### Sources schema (D5 — OWID origin.* + yen-gov extensions, R10)

OWID-verbatim columns: `url_main`, `url_download`, `producer`, `citation_full`, `date_accessed`, `license`, `vintage`.

yen-gov extensions (tagged in canonical-store.md as not-OWID):
- `source_id` (PK)
- `content_hash` (sha256 of fetched bytes)
- `first_fetched_at:str` (RFC 3339; immutable; citizen-facing)
- `last_seen_at:str` (RFC 3339; mutable telemetry)
- `confidence_tier:enum(gold|silver|bronze)`
- `is_issuing_authority:bool`

### Read path (production)

```
GitHub Pages domain
    ↓ HTTP Range (Accept-Ranges enforced at Phase 0)
DuckDB-WASM in browser
    ↓ SELECT ... JOIN observations + taxonomy/indicators + taxonomy/sources + caveats + methodology_breaks
view-model loader (D19) returns chart-ready shapes
    ↓
Svelte 5 + d3 + maplibre-gl (generic renderers; no per-dataset components)
```

**Failure-state contract (D17)**: the loader wraps every async stage and emits a typed result `{status: 'ok'|'loading'|'partial'|'failed', data?, reason?}`. Renderers MUST handle all four. The "failed" state renders plain-language copy with retry; no raw stack traces; source/provenance still visible where it can be resolved.

No backend at runtime. No JSON shadow tree. No CDN cache invalidation.

### Boundary geometry (D25, R10)

| Level | Format | Path |
| --- | --- | --- |
| Country | GeoJSON | `datasets/boundaries/in/country/IN.json` |
| State (national) | GeoJSON | `datasets/boundaries/in/geojson/india-states.geojson` |
| District (national) | GeoJSON now; PMTiles when >10 MB | `datasets/boundaries/in/geojson/india-districts.geojson` → future `pmtiles/india-districts.pmtiles` |
| AC per state | GeoJSON | `datasets/boundaries/in/geojson/S<NN>-ac.geojson` (existing for S01–S2x; gaps filled by Phase 2 readiness) |
| PC national | TBD (Q11) | not yet added |
| Sub-district / taluk | TBD (Q11) | not yet added |
| Village (per state) | PMTiles | not yet added; one PMTiles file per state when ingested |

Resolution path: `observations.entity_id` → `taxonomy/entities.json` row → `(entity_level, entity_code)` → geometry file via `datasets/manifest.json` boundary index. Frontend never hardcodes geometry paths. All boundary files carry a `.sources.json` sidecar (preserved from current convention).

### Write path (local pipeline)

```
adapter (httpx + lxml + pandas)
    ↓ typed batch envelope (D20):
      { target_family, schema_version, source_rows[], observation_rows[], replacement_semantics }
canonical writer (single Message Translator)
    ↓ FK validation (D22): no dangling indicator_id / source_id / entity_id
UPSERT into local DuckDB on logical key (entity_id, year, period_label, indicator_id)
    ↓ COPY (FORMAT PARQUET, ROW_GROUP_SIZE 100000) with deterministic sort
sorted parquet emit to datasets/<family>/
    ↓ Parquet key-value metadata stamped {table_id, schema_version}
manifest.json regenerated
    ↓ git commit
GitHub Pages publish
```

Idempotency: re-running with identical upstream bytes → identical Parquet bytes (UPSERT no-op when logical key matches AND value+source unchanged).

---

## §6. Phase 0 — Foundation (weeks 1–2; expanded R10)

**Goal**: Lay the contract surface. No production data yet.

| Step | Deliverable | Owner agent |
| --- | --- | --- |
| 0.0 | **Deletion manifest** — doc-only PR listing every file/module/concept the pivot retires (folded-indicator doc, period-token helpers, `iced_parity` if subsumed, parity schemas, completeness emitter, operator-state-as-JSON-overlay legacy, `_old/` tree path). Land before any code. **Output: [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) (drafted 2026-05-17).** | Fowler |
| 0.1 | Author ADR-0030 (canonical store + DuckDB-WASM) with full rejected-alternatives table from §3 | Gregor + Hans + Max |
| 0.2 | Author `docs/architecture/data/canonical-store.md` (target architecture, partition rules, OWID `origin.*` mapping with yen-gov extensions tagged, Parquet schema-version mechanism, manifest contract, failure-state UX) | Hans + Max + Gregor |
| 0.3 | Author 9 schemas (`observation`, `indicator`, `source`, `entity`, `caveat`, `methodology-break`, `operator-state`, `manifest`, **`facet-axes` (D31)**) with local `$id` and `x-version 1.0`; **indicator schema carries the full D15 honesty surface + D29 additions (`parent_indicator_id`, `dimension_values:STRUCT`, per-child `source_id`, `methodology_version` FK)**; **id-format rule in indicator schema enforces D30 naming convention** | Gregor + Hans + Max |
| 0.4 | Seed `taxonomy/entities.json` (36 states/UTs ISO 3166-2 + first-batch districts LGD codes) with `entity_valid_from/to` (D23) AND seed `taxonomy/facet-axes.json` initial entries (`fuel_type`, `sector`, `head_of_account`, `gender`, `residence`, `prices_basis`, `methodology_version`, `transfer_type`, `category`, `crime_category`, `cpi_category`, `loss_type`) per D31. Schema-future-proof for §0b growth domains (judiciary, healthcare, water, crime, education-deep, welfare, local-govt-finance) — accept new topic enum values without bump. | Max |
| 0.5 | **Migration ledger** — every existing `datasets/_old/` indicator artifact (elections + ~110 socio-economic) classified: `migrated_in_phase_X` / `dropped_with_reason` / `queued_for_phase_Y`. Single CSV committed; Max owns. | Max + Hans |
| 0.6 | **Parquet schema-version + manifest contract**: writer stamps Parquet key-value metadata `{table_id, schema_version}`; writer regenerates `datasets/manifest.json`; reader fails loud on unsupported version. | Gregor |
| 0.7 | **Vite + GitHub Pages Range/MIME verification**: deploy preview, curl-test `Range:` + `Content-Type: application/octet-stream` (or `application/vnd.apache.parquet`); document in deployment.md. Skip if 206 + MIME confirmed on first try. | Fowler |
| 0.8 | DuckDB-WASM wired into `frontend/src/lib/data.ts` **in an isolated module + test harness (NOT a production feature flag, per D13/R21)**; one round-trip read test against a synthetic Parquet shard | Fowler |
| 0.9 | `backend/yen_gov/canonical/writer.py` skeleton: typed batch envelope intake (D20), FK validation (D22), UPSERT-into-DuckDB on logical key (D7), sorted Parquet emit with Parquet metadata stamp, manifest regen | Fowler + Gregor |
| 0.10 | **Parquet contract tests** (tmp_path fixtures, no mocks, no corpus walk): writer emits a tiny synthetic family; test asserts column names/types, nullability, sorted deterministic emit, FK integrity (rejects dangling), re-run byte-identical | Fowler |
| 0.11 | **Failure-state UX harness**: page mounts loader with a forced 404 / forced timeout / forced bad-schema parquet; assert plain-language copy renders, no stack traces, retry button works | Jony + Fowler |
| 0.12 | Mark obsolete ADRs (0026, 0027); update Outstanding doc cleanups in §4 | Fowler |
| 0.13 | Move pre-pivot JSON under `datasets/_old/` in a single commit. **EXCLUDE from move (R25)**: `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json`. Move applies to legacy `datasets/indicators/in/**`, `datasets/elections/` (legacy shape), `datasets/people/`, `datasets/governments/`, `datasets/events/`, `datasets/features/`, `datasets/reference/` only. Verify with `git status` before commit. | Fowler |
| 0.14 | **Author ADR-0031 (boundary geometry strategy) + `docs/architecture/data/boundaries.md`** capturing D25, the format-per-level table from §5, GeoJSON→PMTiles cutover (Q11), and the entity_id → geometry resolution path. | Jony + Gregor |

**Exit criteria**:
- Schemas validate (Tier A meta-validation).
- Migration ledger committed.
- Manifest contract documented + writer regenerates it.
- DuckDB-WASM round-trips a synthetic Parquet shard in the browser end-to-end.
- Writer round-trips one synthetic indicator end-to-end with FK enforcement.
- Failure-state harness renders plain-language copy on forced failure.
- Range/MIME verified on Pages preview.

---

## §7. Phase 1 — Elections (weeks 3–6; amended R10)

**Goal**: Migrate existing ECI data to canonical store. First real data on the new model.

| Step | Deliverable | Owner |
| --- | --- | --- |
| 1.1 | ECI adapter rewrite: emit canonical batch envelope (D20) instead of per-shard JSON | Hans + Fowler |
| 1.2 | Backfill all existing ECI elections (AcGenMay2026 + history) into `datasets/elections/observations.parquet` | Hans |
| 1.2b | **Dimension tables**: emit `elections.dim_candidates` + `elections.dim_acs` + `elections.dim_parties` (denormalised name / party / AC-name strings the fact table deliberately omits). PKs byte-equal to `observations.entity_id` so view-model loader reconstructs citizen shape via single LEFT JOIN. Unblocks 1.3. | Hans + Max |
| 1.3a | **DONE 2026-05-18 (PR-E)**: swap Constituency route (`/s/:state/ac/:slug`) to view-model loader `lib/view-models/constituency.ts` against `elections.{observations,dim_candidates,dim_acs,dim_parties}` + `taxonomy.sources`. `LoaderResult<T>` four-arm render in the route; legacy `fetchConstituencyResult` deleted. | Fowler + Jony |
| 1.3b | Swap State hub (`StateOverview.svelte`) + map-data loaders to view-models (PR-F); URLs unchanged; failure-state copy wired (D17) | Fowler + Jony |
| 1.4 | Playwright golden-path passes against new loader; **new assertions**: failure-state copy on forced 404; provenance visible in tooltip; `period_label` displayed verbatim | Fowler |
| 1.5 | **Migration parity oracle (test-only harness)**: compare legacy `_old/` JSON shapes against DuckDB queries over canonical Parquet for representative election summaries, per-AC results, NOTA/others/top-N, winners/margins, provenance presence. Acceptance: identical row counts and value-by-value match within rounding tolerance for elections corpus. | Fowler + Citizen |
| 1.6 | Per-AC top-N + NOTA + others cutoff validated against real data (resolves Q5) | Citizen |
| 1.7 | **Admin v0 interim stance** — either (a) pull a minimal canonical Inventory/Pipeline rewrite into Phase 1 before `_old/` deletion, or (b) explicitly retire those admin panels until Phase 5. NO four-phase broken operator console. Decision Q10. | Fowler |
| 1.8 | DELETE `datasets/_old/` gated on D14 explicit checklist (readers rewritten, Playwright green, validate clean, parity oracle green, admin stance resolved, 5 days local observation); tag `v1.0-canonical` | Fowler |
| 1.9 | Monitor git repo size; if >2 GB or clone >60s, convene Fowler + Gregor on Git LFS vs Pages-only build artifact | Fowler |

**Exit criteria**: zero JSON projections for elections; all citizen election routes served from Parquet via view-model loader; failure-state copy verified; migration parity oracle green; admin stance resolved; legacy `_old/` deleted; no regression in Playwright suite.

---

## §8. Phase 2 — Energy (weeks 7–9)

**Goal**: First socio-economic indicator family. Prove the model scales beyond elections.

| Step | Deliverable | Owner |
| --- | --- | --- |
| 2.1 | Indicator scout: pick canonical Indian energy series (CEA installed capacity + state-wise generation; cross-check OWID energy table for indicator IDs to mirror) | Max |
| 2.2 | Source adapter (CEA monthly reports) → canonical batch envelope | Hans + Fowler |
| 2.3 | Indicator + source rows seeded; `cadence='monthly_cy'` on indicator row; **`period_seq` 1..12 per year populated** | Hans + Max |
| 2.4 | First chart: state-wise installed capacity time-series; one map view; **time control keys on `(year, period_seq)`, displays `period_label`** | Jony |
| 2.5 | **Acquisition sequence for socio-economic Phase 2 families** (energy first; then ordered demography → fiscal → education → health by ≥80% states, ≥10 years, gold-source first). Drafted by Max in Phase 0.5 migration ledger. | Max |
| 2.6 | Citizen functional read-through (mid-tier Android NOT a blocker; just "can I read this page and understand it") | Citizen |

**Exit criteria**: one citizen-readable energy page live; OWID-alignment doc updated with the energy indicator mapping; no new schemas required; `caveats.parquet` display contract resolved (Q7) before this page lands.

---

## §9. Phase 3 — Demography / Fiscal / Education / Health (weeks 10–18)

**Goal**: Breadth. Same data shape, repeated across four families. Tests model stability.

| Family | First indicators | Likely source | Notes |
| --- | --- | --- | --- |
| Demography | Population, sex ratio, urbanisation | Census 2011 + SRS bulletins | `cadence='decennial'` mixed with `cadence='annual_cy'` → exercises `caveats.parquet` |
| Fiscal | State own-tax revenue, GSDP, FC devolution, GST | CAG state finance reports + FC docs | `cadence='annual_fy'`; year:int = end-year (FY 2024-25 → 2025); **fiscal-actor doctrine, R10** |
| Education | Literacy, GER, dropout rate | UDISE+ | District-level; tests entity_id scale beyond state |
| Health | IMR, MMR, immunisation coverage | NFHS-5 + HMIS | Mixed cadence; survey vs administrative — Hans annotation needed |

**Fiscal-actor doctrine (R10)** — fiscal indicators MUST classify by `attribution_geography` and `implementing_authority` in `taxonomy/indicators.json`:

- `economy_as_place` — GSDP, state-level production
- `state_government` — state own-tax, state expenditure
- `union_government` — central revenue, central expenditure
- `centre_to_state_flow` — FC devolution, CSS transfers
- `states_combined` — aggregates across all states
- `consolidated_general_government` — Union + all states net of transfers
- **GST is always `where_billed`**, never state-performance signal. Banner copy enforced via `methodology_breaks` / `caveats` when GST flows through a state-comparison chart.
- Health/education/welfare cross-state comparisons that depend on fiscal context either wait for the fiscal baseline or render a "fiscal context pending" caveat.

**Per-family steps** (parametrised over `<family>`):

1. Max scouts indicator list (OWID precedent first).
2. Hans annotates Indian-context caveats (methodology breaks, definitional shifts) → `methodology_breaks.json`.
3. Adapter authored using batch envelope (D20).
4. Backfill committed.
5. One citizen chart per family minimum.
6. `caveats.json` entries for any cross-cadence joins; `methodology_breaks.json` entries for definitional/base-year breaks (separate surfaces per D16).

**Exit criteria**: 5 indicator families live (elections + 4 here); aggregate Parquet size stays under partition thresholds (or partitions correctly applied per D8); Citizen sign-off on at least one chart per family; fiscal-actor doctrine reflected in indicator catalogue rows.

---

## §10. Phase 4 — SLM dispatcher (weeks 19–22)

**Goal**: Small language model in browser answers natural-language questions over the canonical store.

| Step | Deliverable | Owner |
| --- | --- | --- |
| 4.1 | Pick SLM (likely WebLLM or similar; <500 MB model). Functional first; mobile-perf later. | Fowler |
| 4.2 | NL→SQL prompt with canonical schema in system prompt; allow-list via `sqlglot` parser OR `DuckDB EXPLAIN` dry-run (Q3) | Gregor |
| 4.3 | Citizen UX for ask/answer; default chips for common questions ("compare TN and KL on literacy") | Jony + Citizen |
| 4.4 | Safety gate: query timeout, result-row cap, no-DDL allowlist | Fowler |
| 4.5 | Caveats + methodology-breaks banners auto-pulled when query joins across cadences or crosses a known break | Hans + Jony |

**Exit criteria**: 10 hand-picked test questions return correct answers; SLM never emits DDL; caveats AND methodology-breaks banners fire correctly on misleading joins / break crossings.

---

## §11. Phase 5 — Admin rewrite (weeks 23–26)

**Goal**: Operator console rewritten against canonical store. Becomes thin SQL UI over local DuckDB.

| Step | Deliverable | Owner |
| --- | --- | --- |
| 5.1 | Admin Inventory panel: SQL over `taxonomy/indicators.parquet` JOIN `(SELECT DISTINCT indicator_id FROM <family>)` | Fowler |
| 5.2 | Operator-state edit UI writes to `datasets/taxonomy/operator_state.json` (text!) via local FastAPI; pipeline recompiles to `.parquet` | Fowler |
| 5.3 | Pipeline-trigger panel: kick adapters; show UPSERT diffs | Fowler |
| 5.4 | Schemas panel: render schemas from disk; no editing in v1 | Gregor |

**Exit criteria**: parity with whatever admin v0 stance was chosen in §7 step 1.7; operator confirms inventory + force-recollect workflows.

---

## §12. Open questions (resolve before the relevant phase)

| ID | Question | Resolve by | Authority | R10 note |
| --- | --- | --- | --- | --- |
| Q1 | Hive partition column when family > 15 MB | Phase 2 first chart | Hans + Gregor | **R10 leans `indicator_id`** per D8; confirm with energy data |
| Q2 | Git LFS vs build-artifact when repo >2 GB | End of Phase 1 | Fowler + Gregor | unchanged |
| Q3 | SLM safety gate — `sqlglot` allowlist vs `DuckDB EXPLAIN` dry-run vs both | Phase 4 step 4.2 | Gregor + Fowler | unchanged |
| Q4 | District identifier source confirmation (LGD vs Wikipedia slug fallback) | Phase 0 step 0.4 | Max | unchanged |
| Q5 | "Top-N + others" cutoff for per-AC results | Phase 1 step 1.6 | Citizen | unchanged |
| Q6 | Failure-state UX copy library (which phrases for which failure class) | Phase 0 step 0.11 | Jony + Citizen | **R10 reframed** from "bundle size budget" to "failure-state copy"; mobile-perf descoped |
| Q7 | `caveats.parquet` display contract (when does a banner fire? severity? copy?) | **Before Phase 2 first mixed-cadence chart** (R10 tightened from "Phase 3") | Hans + Jony | mixed-cadence misleading-join is a Phase-2 risk the moment energy + decennial demography compose |
| Q8 | `methodology_breaks.parquet` display contract (separate from Q7) | Before Phase 3 fiscal chart (first break-crossing series) | Hans + Jony | NEW R10 |
| Q9 | Commit compiled Parquet to git or rebuild locally? | End of Phase 0 | Fowler + Gregor | NEW R10 — text taxonomy is committed (D18); decision is about the derived `.parquet` variants |
| Q10 | Admin v0 interim stance: minimum canonical rewrite in Phase 1, or retire panels until Phase 5? | Phase 1 step 1.7 | Fowler + user | NEW R10 |
| Q11 | Boundary format cutover — at what file size does a layer move from GeoJSON to PMTiles? (Initial guess: ~10 MB raw GeoJSON or any layer needing zoom-level tiling) | Phase 0 step 0.14 | Jony + Fowler | NEW R10 boundaries — answer feeds ADR-0031 |

**Convene rules**: any agent may propose; final decision per §1 authority table; user supersedes.

---

## §13. Instructions for next coding agent

You are picking up a fresh thread. Do these in order:

1. **Read this entire file.** Then read [`CLAUDE.md`](../CLAUDE.md) §0a, §3, §10, §12 and [`docs/agents/guardrails.md`](../docs/agents/guardrails.md). Then read the two input artifacts in §0a (corpus survey + consolidation audit) ONCE for context.
2. **THIS file is the plan.** Per §0a, do not invent parallel plans. If something needs to change, edit this file in the same commit as the code change.
3. **Do not re-debate decisions D1–D36 or rejected alternatives R1–R31.** They are settled. Escalate to the user if you believe one is wrong.
4. **The 110-ID corpus is a snapshot, not the target.** Per §0b, design for 500–1,000+ indicator_ids over 2–3 years. The catalogue schema and `taxonomy/facet-axes.json` (D31) must accept new topics (judiciary, healthcare, water, crime, education-deep, welfare, local-govt-finance) without bump.
5. **Boundaries are preserved.** Per §0c, no implementation step touches `datasets/boundaries/` except to ADD layers. Phase 0.13 + Phase 1.8 EXCLUDE that tree.
6. **Phase 0 step 0.0 is the deletion manifest.** Land that doc-only PR before any code.
7. **Then ADR-0030 (incorporating R11 decisions D26–D36) and `docs/architecture/data/canonical-store.md`.** Every other doc links to them. Canonical-store.md MUST include the naming convention (D30) and the registered facet axes (D31).
8. **Then ADR-0031 (boundaries) per Phase 0.14.** Captures D25 + Q11.
9. **Then migration ledger (0.5) — before any writer code lands.** It defines the scope of what canonical must absorb before `_old/` can die.
10. **Then schemas (0.3), manifest contract (0.6), Range/MIME verification (0.7), and writer skeleton (0.9) in parallel.**
11. **Use the authority table (§1) to resolve agent debates.** Hans+Max own data shape AND indicator consolidation (per R11 user delegation). Gregor owns contract/integration. Fowler owns engineering craft. Jony+Citizen own UX. User supersedes.
12. **Test tier discipline** (CLAUDE.md §15): every new schema → contract test; every loader → integration test; every citizen route → Playwright golden-path extension. Parquet-specific contract tests use DuckDB round-trip + tmp_path fixtures; no mocks; no corpus walk. Consolidation migration follows D35 (unit + integration, skip golden-byte).
13. **Failure-state UX (D17) is a Phase 0 deliverable, not a polish item.** Step 0.11 must land before Phase 1 starts.

### §13a. Handoff prompt for the next agent (copy-paste)

```
You are taking over implementation of yen-gov's canonical long-format pivot.

THE PLAN (single source of truth): TODO/20260517-canonical-long-format-pivot.md
Read it end-to-end before any other action. It has been through R1+R2 agent debate
and user sign-off as of 2026-05-17 (R11). All decisions D1–D36 and rejected
alternatives R1–R31 are settled; do not relitigate.

INPUTS (read once for context, do not modify):
- TODO/20260517-indicator-corpus-survey.md — factual baseline of 110 currently-ingested IDs.
- TODO/20260517-indicator-consolidation-audit.md — Max+Hans consolidation pass; §2 contains
  known hallucinated IDs flagged in the doc itself; treat the audit as directional, NOT
  as the authoritative indicator list. The authoritative list is what gets seeded in Phase 0
  step 0.4 (entities) and ingested per Phase 1/2/3.

GROUND RULES (read THE PLAN §0a/§0b/§0c carefully):
1. THE PLAN is the only plan. Do not start parallel TODO files. If scope changes, edit THE
   PLAN in the same commit.
2. Indicator cardinality is a moving target — design for 500–1,000+ IDs over 2–3 years
   (judiciary, healthcare, water, crime, education-deep, welfare, local-govt-finance are
   not yet ingested). The contract MUST scale without rework.
3. datasets/boundaries/ is NOT legacy. Never move it, never delete it, never rename files
   in it. Phase 0.13 and Phase 1.8 EXCLUDE that tree. If you find yourself about to run
   `git rm` or `git mv` against anything under datasets/boundaries/, STOP and escalate.

AUTHORITY (CLAUDE.md §0a + R11 confirmation):
- Hans + Max — data shape, entity_id tiering, indicator catalogue, consolidation decisions.
- Gregor — contracts, schema versioning, integration seams.
- Fowler — engineering craft, refactor safety, test tiers, module structure.
- Jony + Citizen — UX, URL grammar, copy, citizen framing.
- User supersedes everyone.

START SEQUENCE:
1. Read THE PLAN (TODO/20260517-canonical-long-format-pivot.md) end-to-end.
2. Read CLAUDE.md §0a, §3, §10, §11, §12, §15.
3. Read docs/agents/guardrails.md.
4. Skim the two input artifacts (§0a) once.
5. Execute Phase 0 step 0.0 (deletion manifest, doc-only PR) — see §6.
6. Then ADR-0030 (incorporating R11 decisions D26–D36) per Phase 0 step 0.1.
7. Then docs/architecture/data/canonical-store.md per Phase 0 step 0.2 — MUST include
   D30 naming convention and D31 facet-axes registry.
8. Then ADR-0031 (boundaries) per Phase 0 step 0.14.
9. Then continue Phase 0 in the order specified in §13 above.

TESTS: per CLAUDE.md §15 tiers. No corpus walk in pytest. No mocks except where Holy Law 7
explicitly allows. Real DuckDB in writer tests via tmp_path.

UI VERIFICATION: per CLAUDE.md §13, any change touching frontend/ or admin/ runtime must be
verified in a real browser via the integrated tools — not deferred to the human.

WHEN BLOCKED: classify the question per §1 authority table and convene the relevant agent(s).
For ambiguity above that level, escalate to the user. Do not invent decisions.
```

---

## §14. Round log (compressed)

- **R1–R3**: Canonical-pivot debate; converged on DuckDB-WASM + Parquet.
- **R4–R6**: Partition axis debate; converged on per-family default + partition only when >15MB.
- **R7**: User asked for OWID adoption + comprehensive zero-context plan.
- **R8**: "Chasing tails" — adopted OWID `year:int`. CLAUDE.md §10 period-normalisation rule removed. Authority table established.
- **R9**: OWID approved; CLAUDE.md cleanup + plan rewrite + 5 phases bootstrapped. All AGENTS.md / concept docs synced.
- **R10 (current)**: Six-agent architectural review run (Citizen, Hans, Max, Gregor, Fowler, Jony — Hans/Citizen/Gregor partial due to tool-rendering issues; substantive review from Max/Fowler/Jony plus consolidated user-curated feedback from prior agent pass). Plan amended to absorb:
  - UPSERT identity excludes `source_id`; includes `period_label`; logical key formalised (R16).
  - `value` split into `value_numeric` + `value_text` (R17, D5/D17).
  - `period_seq` added for sub-annual sortability.
  - Hive partition by `indicator_id`, never by `year` (R18, D8).
  - Hand-authored taxonomy in JSON/CSV; Parquet is compiled artifact (R19, D18).
  - `methodology_breaks` separated from `caveats` (R20, D16).
  - Production feature-flag coexistence rejected (R21, D13 sharpened).
  - View-model loader contract added (R22, D19).
  - Manifest-driven file discovery added (R23, D21).
  - Failure-state UX contract added as Phase 0 deliverable (D17, step 0.11).
  - OWID origin.* vs yen-gov extensions explicitly separated in sources schema (D5).
  - Indicator catalogue expanded to full Hans honesty surface (D15, §5 indicator schema).
  - Entity validity windows added (D23).
  - Migration ledger added as Phase 0.5 deliverable (D24).
  - FK referential integrity at write time (D22).
  - Typed adapter→writer batch envelope (D20).
  - Parquet schema-version mechanism + `manifest.json` (D21).
  - `_old/` deletion gated on explicit checklist, not phase date (D14 sharpened).
  - Migration parity oracle added to Phase 1 (step 1.5).
  - Admin v0 interim stance forced as Phase 1 decision (step 1.7, Q10).
  - Fiscal-actor doctrine added to Phase 3 (§9).
  - Doc cleanup list expanded (data-provenance, data-loading, schemas/core/pipeline, admin overview).
  - Range/MIME Pages verification added to Phase 0 (step 0.7).
  - Mobile-perf explicitly descoped from gating criteria; functional correctness is the bar.
- **R11 (current — concurrence pass)**: Pre-R2 consolidation audit (Max+Hans) showed the corpus has heavy duplication; 110 collapses to ~60 parents → ~80–120 ids after selective explode (NOT the ~210 R1 projection). User explicitly noted §0b: cardinality will grow to 500–1,000+ as judiciary/healthcare/water/crime/education-deep/welfare/local-govt-finance ingest. Three-round agent debate (Round 1: 5/6 picked (b) facet-explode, Gregor picked (c) dimensions:MAP; Round 2: Gregor conceded; all 5 R2 agents accepted Hans+Max as data-shape authority). User signed off on R2 residuals:
  - D26 facet-explode with parent+children + selective rule.
  - D27 entity tiering: single `entity_id` + `entity_type` enum (Max yielded; preference logged).
  - D28 methodology_version: compose Hans (FK breaks table) + Fowler (id-encoded variants) — both, they don't conflict.
  - D29 catalogue column shape with `parent_indicator_id` + `dimension_values:STRUCT` + per-child `source_id`.
  - D30 naming convention `<entity>-<measure>-<unit>-<facet>` kebab-case ≤60 chars.
  - D31 registered `taxonomy/facet-axes.json` rejects unknown dimension keys.
  - D32 chart-shell view-model adds `breaks: [{period_seq, methodology_version, note}]` visible at rest.
  - D33 eight governance answers locked (GSDP rebase as methodology_version; distribution losses one parent + facet; crime count AND rate as facets; Census vs NFHS = two parents; derived indicators first-class; voter turnout GE/AE two parents; CPI combined as facet value; fuel_type=total compute-on-read).
  - D34 consolidation as one-shot dated migration script (not permanent module).
  - D35 consolidation tests: unit + integration, skip golden-byte.
  - D36 deletion ledger format with JSON `replacement_facet_values` column.
  - R26 (c) dimensions:MAP rejected. R27 (ii) separate geo/fiscal columns rejected. R28 permanent consolidator module rejected. R29 golden-byte rejected. R30 own-computed crime rate rejected. R31 smoothing across methodology break rejected.
  - §0a NEW: This-is-THE-plan-document section + input-artifact list.
  - §0b NEW: Cardinality-is-a-moving-target section enumerating not-yet-ingested domains.
  - §0c NEW: Boundaries-preservation reinforcement (do not delete, do not move).
  - §13 rewritten; §13a NEW: copy-paste handoff prompt for next agent.

---

## See also

- [`CLAUDE.md`](../CLAUDE.md) — engineering contract (authoritative).
- [`docs/agents/guardrails.md`](../docs/agents/guardrails.md) — rules digest.
- [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md) — target architecture (TO BE WRITTEN Phase 0).
- [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) — full rationale (TO BE WRITTEN Phase 0).
- OWID ETL repo — pattern source for meadow/garden/grapher naming + `origin.*` schema.

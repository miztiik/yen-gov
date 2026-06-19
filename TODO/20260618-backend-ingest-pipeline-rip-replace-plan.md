# `ingest` - autonomous Fetch -> Enrich -> Publish pipeline (rip-and-replace)

**Last Updated**: 2026-06-19 (critic-hardened: Fowler + Hans + Jony per-topic red-team)
**Level**: 5 (core design + data model + runtime). PAUSES for user ratification before any row executes. Execution WAITS for the in-flight parallel energy/`iced_*` arc to merge. AUTHORED, not implemented.
**Strategy**: RIP AND REPLACE (target-state direct). No strangler-fig, no compat shims. The app MAY break temporarily until the migration finishes.

> Authored via `prepare-plan`. Hardened by a Fowler/Hans/Jony per-topic critic review that materially changed the design (Section 6 records the deltas). Core doctrine from the review: **an autonomous pipeline must make honesty PRECONDITIONAL, not emergent** - divergence detection, methodology-break existence, and issuing-authority evidence are fail-loud preconditions at the write seam, not after-the-fact explanations. Inspiration: `miztiik/yen-go` `backend/puzzle_manager`.

---

## Section 0 - Operating contract

### 0.1 Why this plan exists
Each upstream source (RBI, ICED, NITI, ...) runs autonomously through **Fetch -> Enrich -> Publish** when triggered, driven by a thin **`ingest` orchestrator** over an adapter registry. The operator/agent addresses work by **indicator**; the source is resolved underneath. Verified reality: the vision is already the stale "Lift" doctrine (renamed **`ingest`**, the repo's existing vocabulary); the gold template is [canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) (already on `write_csv`); the observability scaffolding exists but is unwired and leaks Windows drive letters; the indicator registry already exists (`concepts.json` -> `indicators.json` -> `variables.csv`); the Parquet `write_batch` is a Holy-Law-#1 residue on 3 ECI adapters; `manifest.json` is already `tables: []`; yen-gov already splices NSDP across base years with break markers.

### 0.2 Hard-coded scope
IN: the `canonical/ingest/` engine (run-preamble validate+discover, orchestrator + adapter registry + derived indicator->adapter index, pydantic stage messages + specs, one stage-tagged log stream, committed year-checkpoint); autonomous Fetch with batched + delta (SC-1); the honesty preconditions (divergence gate, splice-precondition break-row gate, concept-compatibility, India-discontinuity enrich gates); the Parquet REPLACE; the ICED producer correction (SC-2, evidence-gated); one greenfield proof (NITI SDG India Index); the cleanup command + path util; the subsystem doc + CLI reference + reconciling stale docs.
OUT: frontend/admin/charting; touching energy + `iced_*` WHILE the parallel arc is in flight (Phase D waits); changing `source.csv` (5-field) or `columns.json` except the documented `concepts.json` price-basis/sampling-frame additive bump (Row 1); any new indicator family beyond the one cold RBI HBS cohort (Row 5) + SDG India Index (Row 11).

### 0.3 Strategy ruling
Rip-and-replace, user-explicit ("plan for the target state directly ... we can break the app temporarily"). Rip rows delete old paths outright; canonical CSV is regenerated per-phase from a coherent corpus.

### 0.4 Scope-change ledger
| Row | Date | Intent (what / why / what it overrode) | signoff |
| --- | --- | --- | --- |
| SC-1 | 2026-06-18 | Reintroduce automated network fetch INSIDE the local pipeline with year-keyed batched + delta. OVERRIDES platform-reset 21.4 + the "no network fetcher" anti-pattern. Holy Laws #1/#2 PRESERVED (local pipeline only; prod static; CI never fetches). | user ("if this means change in doctrines, so be it") |
| SC-2 | 2026-06-18 | ICED ceases to be a `producer`; producer becomes the issuing authority where ICED is a pure passthrough, ICED moves to `title`. **Evidence-gated per endpoint (Hans critic), NOT a 31-row sweep**; ICED-originated analytics keep `producer = "NITI Aayog ICED"`. Re-mints affected `source_id`s; never touches `indicator_id`. | user-delegated to Hans+Max |
| SC-3 | 2026-06-19 | Pydantic MANDATORY for every in-process boundary type (3 stage messages, 11 log events, `SourceSpec`/`IndicatorSpec`); exceptions need Fowler/Gregor sign-off. Four DATA-contract seams stay non-pydantic (Section 0.6). Events convert WITH a hand-rolled serializer (Row 3) to preserve the POSIX-path log contract. | user ("make pydantic mandatory ... unless reason approved by fowler/gregor") |
| SC-4 | 2026-06-19 | Year-checkpoint + delta-skip is retained per the user's autonomous-delta mandate, **explicitly overriding** the prior [pipeline.md](../docs/architecture/backend/pipeline.md) rejection of resume-from-checkpoint ("another contract surface ... cost of restarting is small"). Justification: the corpus is now multi-source/multi-decade and re-fetch hits live upstreams; the checkpoint is a fetch-economy + reproducibility receipt, NOT a correctness mechanism. Explicit `--resume` is CUT (the checkpoint makes a plain re-run idempotent). | user (checkpoint mandate) + Jony honesty receipt |

### 0.5 ESCALATE triggers
Level-5: no row executes until "implement it"; execution waits for the parallel arc. During execution STOP only at: (a) a schema MAJOR bump; (b) any op deleting election-results rows vs re-formatting (Row 8); (c) Row 10 editing a `source.csv` row the parallel agent is mutating; (d) a divergence-gate or splice-precondition failure that needs a human methodology call (Rows 6/10); (e) unresolved persona conflict; (f) 3x overrun. SC-1..SC-4 are PRE-SIGNED.

### 0.6 Authority rulings baked in
| Theme | Ruling | Authority |
| --- | --- | --- |
| Subsystem name + home | `ingest`. Engine lives at **`backend/yen_gov/canonical/ingest/`** - a SIBLING to `canonical/adapters/` (NOT a new top-level home; adapters today live in BOTH `canonical/adapters/` and `sources/`). One `engine -> adapters` arrow. Cold `sources/` adapters consolidate into `canonical/adapters/` (Row 11); hot `iced_*` consolidation deferred to Phase D. Entry: `python -m yen_gov ingest <verb>`. | Fowler critic-1 |
| Pipeline stages | **THREE pure-filter stages: Fetch -> Enrich -> Publish.** "Discover/validate the spec + diff the checkpoint" is `run`'s fail-loud PREAMBLE (emits no artifact, crosses no boundary - not a stage). "Design a source" is authoring-time (`pre-flight-ingest` + the typed `SourceSpec`). | Jony critic-3 + Hans |
| CLI verbs (reduced) | **`run`** (the pipeline; `--indicator X` primary, `--adapter Y` scope filter, `--from/--to STAGE` window), **`status`** (per-indicator coverage + which source owns which years + staleness; absorbs list-indicators/list-adapters/explain), **`clean`** (user-mandated cache/log GC), and the EXISTING **`pre-flight-ingest`** (author-time gate). NO stage subcommands (duplicate `--from/--to`), NO `discover` (collides with `check-overlap`), NO `explain`/`list-*` (fold into `status`), NO `rollback`/`inventory`/`--resume`. | Jony critic-1/4 + Fowler |
| Invocation mental model | Indicator-primary, source-resolved (Message Router). A DERIVED in-memory `indicator_id -> [adapter_slug]` index (walked from specs at import; NEVER committed). `run` prints a one-line fan-out echo BEFORE work (`tfr <- [rbi-handbook 1971-2011, srs 2012-2024]: fetching 2 sources`) so multi-source resolution is never a silent surprise. `--adapter` is ONLY ever a scope filter, never a co-equal entry. | Fowler + Jony critic-2 |
| `--adapter` flag | The CLI selector + registry key is `adapter_slug` (`rbi-handbook`), surfaced as `--adapter` (precise; distinct from the citation `source_id`). Never `--source`. | user |
| Interface typing (SC-3) | Pydantic v2 `BaseModel` for the 3 stage messages, the 11 events, and `SourceSpec`/`IndicatorSpec`. FOUR pre-approved non-pydantic exceptions (cross-runtime/persisted DATA contracts): (1) `columns.json` + `csv_validator`, (2) `derive_source_id`, (3) JSON-Schema/`x-version`/`_ops`/`manifest.json`, (4) the DuckDB-WASM read seam. **Events convert but keep a HAND-ROLLED `to_extra` over `model_fields` routed through the path util - NOT `model_dump(mode="json")`, which serializes `Path` via `str()` = backslash on Windows + `+00:00` not `Z`, breaking the section-2 log contract.** `CanonicalBatch.source_rows` = the 5-field shape. | user SC-3 + Fowler critic-2 + Gregor |
| Inter-stage contract | THREE pydantic pipe messages validated at the EDGE (construct at the producing filter; trusted between hops, not re-validated each hop): `ClaimCheck{source_id, meadow_path, content_hash}`; `list[RawRecord]`; `CanonicalBatch{...}`. Never persists. Events are a Tee to the logger. | Gregor |
| Indicator identity + concept-compatibility | The catalogue (`concepts.json` -> `indicators.json` -> `variables.csv`) is the identity SOT; `IndicatorSpec.indicator_id` FKs it fail-loud at registration. **FK existence is NOT sufficient (Hans critic-5): Stage-0/enrich also assert `(unit, normalisation, price-basis, sampling-frame)` match the concept.** `price-basis` (current/constant + base year) and `sampling-frame` are ADDED to `concepts.json` for economic/survey families (minor additive bump, Row 1). | Gregor + Hans critic-5 |
| Divergence gate (NEW, Hans critic-1) | At the UPSERT seam, when a second `source_id` would overwrite an existing cell `(entity, year, period, indicator)` with a value whose relative delta exceeds a per-concept tolerance, the writer **FAILS LOUD** (no silent last-writer-wins). Within-tolerance passes (same fact re-fetched). Over-tolerance -> operator confirms precedence + records the loser value + delta in an audit row, or recognises a break. Keys on data in hand (incoming vs resident value); NO reconciliation engine. | Hans critic-1 |
| Splice is a PRECONDITION, not emergent (NEW, Hans critic-2) | NO splice verb. BUT the first time a publisher boundary appears INSIDE one `(entity_id, indicator_id)` time series (the time-ordered rows change `source_id` mid-series), the writer **REFUSES the emit unless a `methodology_breaks` row exists at the cut-over year AND the indicator's `methodology_version` FK resolves to it.** Disjoint-entity multi-source (each state contributes its own rows; no seam on any single line) does NOT trigger. Same-source new-vintage = emergent UPSERT (fine). This protects the break marker + the renderer's growth-rate guard. | Hans critic-2 |
| Splice precedence | issuing-authority-wins -> single clean cut-over year (no interleave) -> latest-vintage. Record boundary + precedence on the break row; keep each row's true `source_id`. | Hans H-C |
| Year-checkpoint honesty | Key = `(year, hash-of-RAW-fetched-payload)` (NOT the parsed projection); skip P iff `P <= last_completed AND hash(raw_P) == recorded_hash_P`. A revised old year changes its hash -> re-opens. A skip TICKS the `update_period_days` staleness clock but NEVER hides staleness. The hash gate is fetch-dedup, NOT a break detector (a circular-only methodology change slips it - documented). | Hans critic-3 + H-E |
| Config model | Two-level pydantic spec: `SourceSpec` (one per adapter; provenance + how-to-reach/parse) + `IndicatorSpec` children (the fact: id, concept FK, unit, normalisation, price-basis, sampling-frame, entity-kinds, cadence, break-expectations, bifurcation-exposure). No field repeated across the two levels. The authored template shows ONLY the irreducible fields; derived fields (`source_id`) are NOT authored. NO `config/sources.json`. | Fowler F6 + Jony critic-7 |
| Fetch + cache unit | Per-spec `fetch()` (httpx, bounded 3-try) at the source's natural cache unit; `operator_staged` fallback for flaky-TLS. `cache_units_for(indicator_id) -> tuple[CacheKey, ...]` (PLURAL - an indicator may span >1 unit); `CacheKey` is OPAQUE (orchestrator dedups by equality, never interprets). Enrich slices the requested indicator out of the parsed unit. Two requested indicators sharing one unit fetch ONCE. | Fowler critic-4 |
| State placement | (a) DURABLE year-checkpoint + delta-state = committed `datasets/_ops/ingest-state/<adapter_slug>.json` (schema + `x-version`); (b) EPHEMERAL per-run progress + the single tagged log stream = `.runtime/logs/<run_id>/run.log` (never the resume authority); (c) freshness = `manifest.json`. No state in `docs/`. | Gregor + Fowler |
| Observability | ONE stage-tagged JSON-lines stream `.runtime/logs/<run_id>/run.log` (`[fetch]`/`[enrich]`/`[publish]` tags; `grep [fetch]` for the per-stage view) - NOT five files. `run_id` = `YYYYMMDD-xxxxxxxx`. NO correlation id (in-process, not distributed tracing). Add ONE event `fetch.skipped`; `ALL_EVENT_NAMES` stays pinned. | Jony critic-6 + Fowler |
| Path discipline | `canonical/ingest/paths.py::to_repo_relative_posix(p, *, repo_root)` is the single path-emit seam (relativize, force `/`, fail-fast on a surviving drive letter/escape). Routes `events.py` - FIXES the `as_posix()` drive-letter bug. | Fowler F-E |
| Manifest + Parquet rip = REPLACE | `manifest.json` is already `tables: []`; the parquet-scan body is dead; `_regenerate_manifest` has TWO live callers (`emit-taxonomy`, `dim_acs_lgd_lift` - the latter writes a RETIRED parquet). Write a ~15-line `emit_manifest()` (version stamp + `_DEPRECATIONS`, no scan), repoint `emit-taxonomy`, DELETE `write_batch` + the scan body + `dim_acs_lgd_lift`'s dead emit (keep `load_lgd_lookup`). The question is "does anything populate `manifest.tables`?" (no), not "do the ECI callers raise." | Fowler critic-5 |
| `run_pipeline` = single-series only | Row 4 wires `rbi_handbook` onto the scaffold WITHOUT extracting `run_pipeline` (behavioural). `run_pipeline` is scoped SINGLE-SERIES; the existing faceted `iced_power.ingest_pipeline` stays a SEPARATE Strategy (the codebase already split `ingest()` vs `ingest_pipeline()`). Extract `run_pipeline` only after 2-3 single-series shapes co-exist (true Rule of Three; `rbi_handbook` + SDG are BOTH single-series, so they alone do not satisfy it). | Fowler critic-3 |
| India-discontinuity enrich gates | The six fail-loud gates MUST include: bifurcation (AP-2014 id-REUSE `IN-S01` stays valid; J&K-2019 `IN-S09`), code-authority (LGD vs Census vs ECI - fail-loud on ambiguous/unmapped, never best-guess), FY != CY normalisation, provisional-vs-revised (carry estimate status; ties to the checkpoint re-open), price-basis (refuse constant-into-current UPSERT), publisher-bounded-universe (no synthesised phantom states). | Hans critic-6 |
| Doc discipline | Keep-receipts triplet (`## Design rationale` + `## Alternatives considered` [one line + revisit trigger] + `## Deferred`). NEW `docs/architecture/ingest/pipeline.md` + `docs/reference/cli-ingest.md`; UPDATE the two stale docs. One concept once; docs land with the code; agent gotchas -> `/memories/lessons.md`. | user + Fowler F5 |
| Sequencing vs the parallel agent | Phase A greenfield. Prove on COLD `rbi_handbook` + a new HBS cohort, then greenfield SDG India Index, then touch HOT energy/`iced_*` + the `source.csv` reattribution + `sources/` consolidation LAST (after the arc merges). `source.csv` + `columns.json` FROZEN/additive-only. | Max + Gregor |

---

## Section 1 - Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| 1 | Pydantic stage messages + `SourceSpec`/`IndicatorSpec` + catalogue FK + concept-compatibility (price-basis/sampling-frame) | [ ] PENDING | - | M |
| 2 | Committed year-checkpoint (raw-payload hash + staleness-tick) receipt schema + Tier-B gate | [ ] PENDING | - | S |
| 3 | `ingest/paths.py` + one stage-tagged log stream + events->pydantic (hand-rolled serializer) + `fetch.skipped` + run_id | [ ] PENDING | - | M |
| 4 | `canonical/ingest/` orchestrator + adapter registry + derived index + run-preamble + wire `rbi_handbook` (no extract) + `run`/`status` CLI | [ ] PENDING | - | L |
| 5 | Autonomous Fetch hook + `cache_units_for` (plural) + delta-skip + 2nd cold caller | [ ] PENDING | - | M |
| 6 | Enrich India-discontinuity gates + **divergence gate** + **splice-precondition break-row gate** + status-shows-provenance + auto pre-flight | [ ] PENDING | - | L |
| 7 | REPLACE manifest: `emit_manifest()` (no scan) + delete `dim_acs_lgd_lift` dead emit (keep `load_lgd_lookup`) | [ ] PENDING | - | S |
| 8 | Flip 3 ECI adapters (`eci_ls`, `eci_ae_panel`, backfill) to `write_csv` | [ ] PENDING | - | M |
| 9 | Delete `envelope.py` + `write_batch` + scan body + residual Parquet | [ ] PENDING | - | M |
| 10 | ICED authority-tracing (`docs/research/` table FIRST) + evidence-gated producer correction (NOT a sweep) - AFTER hot arc | [ ] PENDING | - | L |
| 11 | Greenfield NITI SDG India Index (3rd single-series) -> extract+ratify `run_pipeline`; consolidate cold `sources/` adapters | [ ] PENDING | - | L |
| 12 | `ingest clean` command + runtime-dir env override | [ ] PENDING | - | S |
| 13 | Docs: `docs/architecture/ingest/pipeline.md` + `cli-ingest.md` + honesty doctrine; rewrite stale docs + CLAUDE.md + distill | [ ] PENDING | - | M |

Phase lines: A = {1,2,3} -> B = {4,5,6} -> C = {7,8,9} -> D = {10,11} (waits for the parallel arc) -> E = {12,13}. Row 8 is decoupled from Row 7 (the ECI CSV flip needs no manifest work - it can land earlier in C). Row 6 carries the honesty gates and is the heaviest behavioural row. Row 1 is a hard predecessor to anything that constructs an event/message.

---

## Section 2 - Target architecture

```
CLI (indicator-primary; prints a fan-out echo before work):
  python -m yen_gov ingest run    --indicator total-fertility-rate            # main path
  python -m yen_gov ingest run    --indicator nsdp-inr-crore                  # -> 2 adapters; UPSERT-merge; splice gate requires a break row
  python -m yen_gov ingest run    --adapter rbi-handbook                      # scope filter
  python -m yen_gov ingest run    --indicator birth-rate --from enrich        # re-enrich+publish from cache (window)
  python -m yen_gov ingest status --indicator nsdp-inr-crore                  # coverage + which source owns which years + staleness (absorbs explain/list-*)
  python -m yen_gov ingest clean   [--days N] [--force] [--dry-run]
  python -m yen_gov pre-flight-ingest --proposal-file ...                     # EXISTING author-time gate (design)
   |
   v
orchestrate(*, indicator|adapter, repo_root, config)   # THIN; never branches on adapter_slug
   |  registry {adapter_slug -> Adapter};  DERIVED {indicator_id -> [adapter_slug]} (in-memory)
   |  FK-check every IndicatorSpec.indicator_id vs indicators.json (fail-loud at registration)
   |  mint run_id; open ONE tagged logger; read committed year-checkpoint; print fan-out echo
   v
PREAMBLE (run-time, not a stage): validate spec + list cache units + diff vs checkpoint -> work-list
   |
   |-- FETCH    per-spec fetch() at the CACHE UNIT (or operator_staged); raw bytes -> _meadow/ (gitignored);
   |            update committed checkpoint (year -> hash of RAW payload); fetch.skipped on year delta
   |            -> ClaimCheck{source_id, meadow_path, content_hash}
   |-- ENRICH   parse ONLY the requested indicator's slice; resolve entity_id; canonicalise unit; normalise
   |            period; FK + CONCEPT-COMPATIBILITY (unit/normalisation/price-basis/frame); India-discontinuity
   |            gates (bifurcation/code-authority/FY-CY/provisional/price-basis/publisher-bounded); FAIL LOUD
   |            -> CanonicalBatch{...}
   |-- PUBLISH  validate vs columns.json; DIVERGENCE GATE (material cross-source disagreement -> fail loud);
   |            SPLICE PRECONDITION (publisher boundary inside one (entity,indicator) line -> require break row);
   |            UPSERT via write_csv on PK; upsert source.csv; advance checkpoint
         -> datasets/data/...csv

observability: .runtime/logs/<run_id>/run.log  (ONE stage-tagged JSON-lines stream)
durable state: datasets/_ops/ingest-state/<adapter_slug>.json  (committed: last_completed_period + per-year RAW hash)
identity SOT: concepts.json -> indicators.json -> variables.csv   (pipeline FKs in, never owns)
```

---

## Section 3 - Per-row specs (each: scope / files / gates / ONE oracle)

**Row 1** - Pydantic messages + two-level specs + catalogue FK + concept-compatibility. Files: NEW `canonical/ingest/{messages,spec,catalogue_fk}.py`; EDIT `concepts.json` + its schema (additive `price_basis` + `sampling_frame`, minor `x-version` bump); tests. Gates: a spec with a bogus `indicator_id` RAISES at registration; a spec whose declared `(unit, normalisation, price_basis, sampling_frame)` mismatches the concept RAISES; `CanonicalBatch.source_rows` is 5-field. ONE oracle: a contract test asserts `CanonicalBatch.observation_rows` keys == the non-facet `geo/*.csv` column set AND a price-basis-mismatched spec fails registration.

**Row 2** - Year-checkpoint receipt (raw-payload hash). Files: NEW `datasets/schemas/ingest-state.schema.json`; NEW `canonical/ingest/state.py`; a `tier_b_ingest_state_receipt` check; tests. Gates: skip iff raw-hash equal; a changed raw hash for an OLD year forces re-process; a skip ticks the staleness field, never clears it. ONE oracle: receipt for {2018..2022}; 2019 skipped on hash-match, FORCED on hash-change, and the staleness clock still advances on a skip (Hans critic-3).

**Row 3** - Path util + one tagged log stream + events->pydantic. Files: NEW `canonical/ingest/paths.py` + tests; EDIT `core/events.py` (dataclass->pydantic `BaseModel(frozen=True)`; KEEP a hand-rolled `to_extra` iterating `model_fields`, routing `Path` through the path util, emitting `Z`; `FetchSkipped` + `ALL_EVENT_NAMES`); EDIT `core/logging.py` (stage tag in one stream); update tests. Gates: a logged Windows `Path` emits repo-relative POSIX no `C:`; timestamps end `Z`; `ALL_EVENT_NAMES` grows by exactly one. ONE oracle: **Windows log-line BYTE-FIDELITY** - a pydantic event with a Windows abs `Path` emits a byte-identical JSON line to the pre-conversion dataclass output (posix path + `Z`).

**Row 4** - `canonical/ingest/` orchestrator + registry + derived index + run-preamble + wire `rbi_handbook` (NO extraction) + `run`/`status`. Files: NEW `canonical/ingest/{orchestrator,registry,cli}.py`; EDIT `rbi_handbook` to be driven by the orchestrator AS-IS (no `run_pipeline` extraction); EDIT top-level `cli.py` to mount the `ingest` app; tests. Gates: `ingest run --indicator total-fertility-rate` resolves to `rbi-handbook` and emits the same rows as `--adapter rbi-handbook --indicator total-fertility-rate`; the orchestrator has zero `if adapter_slug ==`; the fan-out echo prints; `status` shows coverage + per-source year spans. ONE oracle: **golden byte-identity** - `rbi_handbook`'s emitted CSV + structured log lines are byte-identical before/after being driven by the orchestrator.

**Row 5** - Fetch hook + `cache_units_for` (plural) + delta-skip + 2nd cold caller. Files: NEW `canonical/ingest/fetch.py`; NEW `canonical/adapters/rbi_hbs_<cohort>/`; EDIT specs (`fetch_url`/`fetch_mode`/`spec_version`/`cache_units`); tests with a mocked `fetch`. Gates: two indicators sharing one cache unit fetch ONCE; a 2nd run with unchanged years `fetch.skipped` + zero new bytes; a `spec_version` bump re-emits; an indicator spanning 2 cache units is representable. ONE oracle: run twice - run 2 `fetch.skipped` + CSV mtime untouched; mutating one year's raw fixture re-emits exactly that year; a 2-unit indicator fetches both units.

**Row 6** - Enrich gates + divergence gate + splice-precondition + status provenance. Files: NEW `canonical/ingest/{enrich_gates,divergence,splice_guard}.py` (start inline, split when a 2nd caller earns it); EDIT the publish seam; EDIT `status` to show per-source year spans; tests for each gate's RAISE path + a 2-source splice fixture + a divergence fixture. Gates: each India-discontinuity gate RAISES on bad input (a pre-2014 Telangana row aborts; an ambiguous code aborts; a CY token into an FY series aborts); a material cross-source disagreement on one cell FAILS LOUD; a publisher boundary inside one `(entity, indicator)` line REFUSES emit without a break row at the cut-over. ONE oracle: a 2-source fixture with a mid-series `source_id` change FAILS to publish until a `methodology_breaks` row at the cut-over exists, then publishes one series with each row's `source_id` intact; a >tolerance overlap-year disagreement fails loud.

**Row 7** - REPLACE manifest. Files: NEW `canonical/manifest.py` (`emit_manifest()` ~15 lines, no scan); EDIT `cli.py` `emit-taxonomy`; DELETE `dim_acs_lgd_lift`'s dead emit (keep `load_lgd_lookup`); tests. Gates: `manifest.json` regenerates byte-identical (it is already `tables: []`); no `_regenerate_manifest` import remains. ONE oracle: byte-identity of `manifest.json` before/after + a grep proving the parquet-scan body is gone.

**Row 8** - Flip 3 ECI adapters to `write_csv`. (Decoupled from Row 7.) Files: EDIT `eci_ls`, `eci_ae_panel`, `canonical_eci_backfill` + CLI + tests; additive `source.csv` upsert. Gates: per-event row counts preserved (a drop is an ESCALATE); CSV passes Tier-B. ONE oracle: per-event before/after parity of `(entity_id, year, indicator_id)` tuples.

**Row 9** - Delete the Parquet path. Files: DELETE `canonical/writer.py` + `canonical/envelope.py`; EDIT `canonical/__init__.py`, `eci_ae_panel.py`, `ingest_pincode.py`, `cli.py`; delete orphan tests. Gates: pytest green; `grep -r "write_batch|BatchEnvelope|to_parquet|read_parquet|FORMAT PARQUET" backend/` == 0 live hits; Tier-B green. ONE oracle: the repo-wide grep gate.

**Row 10** - ICED authority-tracing + evidence-gated producer correction (AFTER the hot arc). Files: NEW `docs/research/iced-authority-tracing.md` (per-endpoint: ICED's named upstream + passthrough-vs-derived evidence) authored + persona-reviewed FIRST; NEW `canonical/iced_authority_map.py`; EDIT iced citation calls (ICED-originated keep `producer = "NITI Aayog ICED"`); regenerate affected `source.csv` rows + datapoints; EDIT `validate.py` (FK gate + producer-not-a-product assertion). A Scope-change ledger row per the STOP-AND-SURFACE class. Gates: every reattributed endpoint cites passthrough evidence; ICED-originated endpoints keep the NITI producer; zero dangling `source_id`; the `indicator_id` set is unchanged; the divergence + splice gates hold. ONE oracle: a Tier-B check asserts every `producer` is an organisation (not a product), every `source_id` resolves, the `indicator_id` set is identical before/after, AND each changed producer has a citation in the tracing table.

**Row 11** - Greenfield SDG India Index + ratify `run_pipeline` + consolidate cold adapters. Files: NEW `canonical/adapters/niti_sdg_index/`; NOW extract `run_pipeline` (single-series; 3rd caller); git-mv the COLD `sources/` single-series adapters under `canonical/adapters/`; a committed green `pre-flight-ingest` report; tests. Gates: pre-flight verdict in {mint_new, upsert, add_facet}; the three single-series callers byte-identical vs pre-extraction; faceted `iced_power.ingest_pipeline` untouched; no hot `iced_*` moved. ONE oracle: byte-identical parity of all three single-series callers before/after the extraction.

**Row 12** - `ingest clean`. Files: NEW `canonical/ingest/cleanup.py` (`CLEAN_TARGETS`, routed through `paths.py`); EDIT `ingest/cli.py`; EDIT the runtime-dir resolver (`YEN_GOV_RUNTIME_DIR`); tests. Gates: `--dry-run` mutates nothing; every target resolves under `.runtime/`; refuses a target outside `.runtime/` (never `_ops/`, `datasets/**`, `config/`, `docs/`); `N < 90` without `--force` aborts. ONE oracle: seed an old `.runtime/logs/` dir + a `_ops/ingest-state` file; `clean` removes the log, leaves the checkpoint.

**Row 13** - Docs. Files: NEW `docs/architecture/ingest/pipeline.md` (subsystem + operator mental model + the honesty doctrine; keep-receipts triplets for every Section-5/6 decision) + NEW `docs/reference/cli-ingest.md`; rewrite the two stale docs to the `ingest`/`run_pipeline`/`write_csv` reality; record SC-1..SC-4 in `CLAUDE.md` + the decision index; distill. Gates: a grep gate proves zero `core.http`/`core.io.Source`/`write_artifact`/`write_batch`/stale-"Lift" refs in `docs/`. ONE oracle: the grep gate.

---

## Section 4 - YAGNI refusals
A DAG/workflow engine; a materialized "garden" tier; a runtime endpoint crawler; a general N-source splice engine; a reconciliation framework / unit-inference engine (the divergence + concept gates are declare-and-compare on data in hand); a second checkpoint file; `pydantic-settings`/global `Settings`/`config/sources.json`/`active_adapter`; a plugin adapter registry; `rollback`+`audit.jsonl`; an `inventory` module; an `explain`/`discover` verb; stage subcommands; an `--resume` flag; five log files + a correlation id; a committed reverse index; a committed per-run receipt; a `source_id` alias table; re-adding `tenacity`/`core/http.py`; a generated published-state report under `docs/`; folding faceted (CEA/energy) into the single-series `run_pipeline`; pre-creating 11 ingest modules (start inline, split on the 2nd caller).

---

## Section 5 - Decisions log (why / what / rejected / deferred)
| Decision | Why | Rejected alternative | Deferred |
| --- | --- | --- | --- |
| Name `ingest` | The repo already speaks it | "Lift" (user: ugly); `harvest`/`acquire` | a citizen brand |
| Indicator-primary, `--adapter` filter | Agents/humans think in indicators; precise flag avoids the `source_id` collision | source-primary; `--source` (ambiguous) | a GUI |
| 3 stages (Fetch->Enrich->Publish) | A non-emitting "stage 0" is `run`'s preamble, not a pipe stage | a 4th "Discover" stage (ceremony) | - |
| ~3 verbs (run/status/clean + pre-flight) | A verb and a flag for one act is two grammars | stage subcommands; list-*/explain/discover/rollback/inventory | - |
| Pydantic mandatory + events hand-rolled serializer | One typed model at every boundary; but `model_dump` breaks the POSIX-path log contract on Windows | events stay dataclass (Fowler's pure-craft exception #5 - overridden to honor "everything pydantic" with the serializer fix) | measuring hot-path cost if it ever matters |
| Splice PRECONDITION (break-row gate), no verb | Emergent splice without a forced break row ships a smooth line across a methodology seam (Rosling Straight-line) | emergent splice (my earlier call; reversed by Hans critic) | a multi-source precedence DSL |
| Divergence gate at UPSERT | Silent last-writer-wins hides publisher disagreement (Rosling Single-perspective) | precedence-only (decides who wins, not whether they disagree) | per-concept tolerance tuning |
| Year-checkpoint kept (SC-4) | The user's autonomous-delta mandate over the prior resume-rejection; raw-hash so revisions re-open | re-run-from-clean (Jony); the prior pipeline.md rejection | sub-year checkpoint grain |
| `run_pipeline` single-series; extract at Row 11 | `rbi_handbook`+SDG are both single-series; faceted is the real test and already separate | extract at Row 4 (1 caller; false Rule of Three) | folding faceted in |
| Manifest/Parquet = REPLACE | `manifest.json` already `tables: []`; the generator is dead | Extract-then-preserve (overstates a dead survivor) | - |
| Engine at `canonical/ingest/` | Adapters live in 2 homes; a top-level `ingest/` would be a 6th | top-level `ingest/` | hot `iced_*` consolidation -> Phase D |
| ICED SC-2 evidence-gated | A blanket CEA sweep bakes a provenance lie where ICED originates | a 31-row sweep | the per-endpoint tracing table (Row 10 prerequisite) |
| Concept-compatibility + India gates | FK existence != measuring the right thing; India breaks at bifurcation/calendar/price-basis seams | FK-only; generic six gates | adding price-basis/frame to non-economic concepts |

---

## Section 6 - Critic-review convergence (what the red-team changed)
Fowler + Hans + Jony reviewed per-topic and CONVERGED on these changes from the pre-critic plan (PR #1155):
- **Honesty made preconditional (Hans, core):** ADDED the divergence gate (no silent last-writer-wins), the splice-precondition break-row gate (splice is no longer emergent), raw-payload hashing + staleness-tick, concept-compatibility (price-basis + sampling-frame on `concepts.json`), the India-discontinuity enrich gates (bifurcation/code-authority/FY-CY/provisional/price-basis/publisher-bounded), and evidence-gated ICED reattribution (per-endpoint tracing table BEFORE Row 10).
- **Reduction (Jony):** 4 stages -> 3 (Stage 0 dissolved); 10 verbs -> ~3 (folded list-*/explain into `status`, cut stage subcommands); 5 log files -> 1 tagged stream; cut the correlation id + `--resume`; do not pre-create 11 modules.
- **Craft (Fowler):** engine at `canonical/ingest/` (not a 6th home); events = pydantic with a hand-rolled serializer (the `model_dump` Windows-path break); `run_pipeline` single-series, extracted at Row 11 not Row 4 (false Rule of Three); manifest/Parquet = REPLACE not extract (`manifest.json` already empty; 2 callers not 3); `cache_units_for` plural; golden byte-identity oracles (not smoke tests); Row 1 split events from messages; SC-4 records the checkpoint override.

---

## Execution contract (autonomous - follow blindly)
When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO questions except at an ESCALATE trigger.
1. Orchestrator + stateless `runSubagent` per row (scope/files/gates/oracle self-contained).
2. One row = one PR = one branch; park master on `scratch-master-parking`; author per `docs/how-to/ship-a-pr.md` (2-commit-squash, 5-gate DoD, browser-verify for UI).
3. Ship loop non-stop; merge `--squash --delete-branch`, pull, next; baseline-document unrelated failures.
4. Tests ship with the row; full suite green at merge; no new mocks unless asked.
5. Persona debate converges to ONE ruling on a contested call.
6. Offload breadth to subagents; the orchestrator holds only the Reckoner + current row + merge state.
7. Post-merge hygiene every time.
8. Stop only at an ESCALATE trigger, a STOP-AND-SURFACE scope-narrowing, or an audit chain past depth 3.
9. Closure: every row DONE or COLLAPSED-with-rationale; archive with a per-row distillation map.

> Binding notes: (a) Phases A->B->C->D->E; Phase D waits for the parallel energy/`iced_*` arc - rebase first. (b) `source.csv` + `columns.json` FROZEN/additive-only (the only additive bump is `concepts.json` price-basis/sampling-frame in Row 1). (c) Rows 6/8/10 touch election + provenance data: a row-count drop, a dangling FK, a divergence-gate or splice-precondition failure that needs a methodology call is an ESCALATE. (d) Each row in a dedicated worktree off fresh `origin/main`; never share a worktree with a parallel agent. (e) Every path-emit routes through `canonical/ingest/paths.py`. (f) Pydantic mandatory (SC-3); the four DATA-contract exceptions stay non-pydantic; events keep the hand-rolled serializer.

## See also
- [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) (Row 13 rewrites + renames it `ingest`)
- [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) (gold template)
- [datasets/taxonomy/concepts.json](../datasets/taxonomy/concepts.json) -> [indicators.json](../datasets/taxonomy/indicators.json) -> [variables.csv](../datasets/data/variables.csv) (identity SOT)
- [docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md) (the NSDP splice + break precedent)
- `miztiik/yen-go` `backend/puzzle_manager` (the orchestrator model)
- [CLAUDE.md](../CLAUDE.md) (authority table section 0a)

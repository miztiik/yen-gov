# `ingest` - autonomous Discover -> Fetch -> Enrich -> Publish pipeline (rip-and-replace)

**Last Updated**: 2026-06-19
**Level**: 5 (core design + data model + runtime). The whole plan PAUSES for user ratification before any row executes. Execution also WAITS for the in-flight parallel energy/`iced_*` reingest arc to merge. AUTHORED, not yet implemented.
**Strategy**: RIP AND REPLACE (target-state direct). No strangler-fig, no backwards-compat shims, no parallel old+new paths. The app MAY break temporarily until the migration finishes.

> Authored via the `prepare-plan` skill after persona consults (Fowler, Gregor, Hans, Max) + targeted debates on OWID-splicing, the orchestrator, naming, the operator mental model, and interface typing. Design inspiration: the sibling repo `miztiik/yen-go` `backend/puzzle_manager` (a thin config-driven multi-source pipeline). Every contested call carries a baked-in written ruling so execution is blind rule-following. A `Decisions log` (Section 5) records why/what/rejected/deferred for every major call. The `Execution contract` block is the whole instruction set for "implement it".

---

## Section 0 - Operating contract

### 0.1 Why this plan exists

Each upstream source (RBI, ICED, NITI, ...) must run **autonomously through staged Discover -> Fetch -> Enrich -> Publish** when triggered, driven by a **lightweight master orchestrator** that processes a source/indicator from its typed config (sources are **adapters**; many more will be added). The operator/agent addresses work by **indicator** (the thing they care about); the source is resolved underneath. The pipeline needs **typed config + sane defaults + per-invocation overrides**, **full machine-parseable observability** (per-stage + orchestrator log files, run ids, year checkpoints), and **batched + delta fetches keyed on year** so unchanged upstream is never re-processed.

Verified reality (research, 2026-06-18/19):

- The vision is **already documented** as the 4-layer "Lift pipeline" in [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) + [docs/how-to/add-a-new-data-source.md](../docs/how-to/add-a-new-data-source.md), but both are **stale** (import deleted `core.http.Fetcher`, `core.io`, `write_batch`, Parquet, the retiring `_meadow/` tier). This plan renames the subsystem **`ingest`** (the word the repo already speaks) and rewrites the docs.
- The **gold target template already exists**: [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) - a config-driven typed-spec registry + generic parser + state resolver + direct `write_csv` emit + in-place catalogue/source upsert. Each indicator there already has its own staging file (`table-total-fertility-rate.xlsx`).
- The observability scaffolding ([core/logging.py](../backend/yen_gov/core/logging.py), [core/events.py](../backend/yen_gov/core/events.py) - 11 events) **exists, is tested, wired into nothing**, and `to_extra()` calls `Path.as_posix()` which KEEPS the Windows drive letter (a live CLAUDE.md section 2 violation).
- The indicator registry **already exists**: `datasets/taxonomy/concepts.json` (identity SOT: `noun`/`unit_canonical`/`normalisation`/`entity_kinds`) -> `datasets/taxonomy/indicators.json` (catalogue, FK concept) -> `datasets/data/variables.csv` (rows). The pipeline READS it as a contract and never owns identity.
- The Parquet writer ([canonical/writer.py](../backend/yen_gov/canonical/writer.py) `write_batch`) + the typed batch ([canonical/envelope.py](../backend/yen_gov/canonical/envelope.py)) are a Holy-Law-#1 residue still live on 3 ECI adapters.
- ICED is **31 `source.csv` rows conflated under one producer string** that mashes org + product.
- yen-gov **already splices** RBI NSDP across four base years into one series with break markers ([docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md)) - OWID-at-indicator splicing is existing in-house doctrine.

### 0.2 Hard-coded scope

IN: the `ingest` subsystem (Stage 0, the master orchestrator + adapter registry + derived indicator->adapter index, typed pydantic stage messages + specs, per-stage observability, committed year-checkpoint state); autonomous network Fetch with batched + delta semantics (SC-1); the cleanup command + the POSIX/relative path util; finishing the Parquet/envelope rip; the ICED/NITI producer correction (SC-2); one greenfield proof acquisition (NITI SDG India Index); the `docs/architecture/ingest/pipeline.md` subsystem doc + CLI reference + reconciling stale docs + CLAUDE.md + bootstrap.

OUT: frontend / admin / charting; restructuring energy + `iced_*` WHILE the parallel arc is in flight (Phase D waits); changing `source.csv` (5-field) or `datasets/data/_schema/columns.json` (frozen, additive-only); any new indicator family beyond the one cold RBI HBS cohort (Row 5) and the SDG India Index proof (Row 11).

### 0.3 Strategy ruling (rip-and-replace, user-explicit)

The user overrode Fowler's strangler-fig default: "plan for the target state directly ... we can break the app temporarily." Rip rows delete old paths outright; a temporarily-broken ECI ingest between Row 7 and Row 9 is acceptable; the canonical CSV is regenerated at the end of each phase from a coherent corpus.

### 0.4 Scope-change ledger

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
| --- | --- | --- | --- |
| SC-1 | 2026-06-18 | Reintroduce automated network fetch INSIDE the local ingest pipeline: each source runs autonomously Discover -> Fetch -> Enrich -> Publish, with batched + delta fetch keyed on year. OVERRIDES platform-reset plan section 21.4 ("network-fetch code is deleted") and the CLAUDE.md "no network fetcher" anti-pattern. Holy Laws #1 + #2 PRESERVED: fetch runs ONLY in the local pipeline; production stays static; CI consumes committed CSV and never fetches. | user, 2026-06-18 ("if this means change in doctrines, then so be it") |
| SC-2 | 2026-06-18 | ICED ceases to be a `producer`: producer becomes the issuing authority (CEA / MoSPI / MoEFCC; "NITI Aayog" for NITI-originated), ICED moves into `title`. Re-mints 31 `source_id`s + rewrites FKs (no alias table). Operates on the `source_id`/`producer` axis ONLY; does NOT split any indicator series (orthogonal to identity per Hans H-B). | user-delegated to Hans+Max; ruling in Section 0.6 |
| SC-3 | 2026-06-19 | Pydantic is MANDATORY for every in-process boundary type (the 3 stage messages, the 11 log events, `SourceSpec`/`IndicatorSpec`). Exceptions require explicit Fowler/Gregor sign-off; the four pre-approved exceptions are enumerated in Section 0.6 "Interface typing". This overrides the prior "frozen dataclasses in-process" ruling. | user, 2026-06-19 ("make pydantic mandatory compliance, unless we have proper reason for exception approved by fowler/gregor") |

### 0.5 ESCALATE triggers

- Level-5: no row executes until "implement it"; execution waits for the parallel energy/`iced_*` arc to merge.
- During execution STOP only at: (a) a `datasets/schemas/*.schema.json` MAJOR bump; (b) any op that DELETES election-results rows rather than re-formatting (Row 8 - a row-count drop is an ESCALATE); (c) Row 10 would edit a `source.csv` row the parallel agent is concurrently mutating; (d) an unresolved persona conflict; (e) 3x effort overrun.
- SC-1/SC-2/SC-3 are PRE-SIGNED; not re-litigated at execution time.

### 0.6 Authority rulings baked in (zero decision points for the executor)

| Theme | Ruling | Authority |
| --- | --- | --- |
| Subsystem name | The pipeline is **`ingest`**. Subsystem module `backend/yen_gov/ingest/{orchestrator.py, registry.py, pipeline.py, cli.py, paths.py}`; `ingest/` depends on `canonical/`, never the reverse. Entry: `python -m yen_gov ingest <verb>`. ("Lift" rejected by the user as ugly; `ingest` is the repo's existing vocabulary.) | user + Fowler F1 |
| Pipeline stages | FOUR stages: **Discover + Design (Stage 0) -> Fetch -> Enrich -> Publish**. Stages are pure filters; the orchestrator holds run/checkpoint state. Stage names are a CLI contract - locked. | user + Fowler |
| CLI grammar | `run` is the full pipeline; each STAGE is also a subcommand for single-stage runs; windows use `--from`/`--to`. Verbs: `run`, `discover`, `fetch`, `enrich`, `publish`, `status`, `list-indicators`, `list-adapters`, `explain`, `validate`, `clean`. No `--only-stage` (ugly); no `rollback`/`inventory` (YAGNI). | user + Fowler F2 |
| Invocation mental model | **Indicator-primary, source-resolved** (Message Router: indicator = logical address, adapter = physical fetch route). `ingest run --indicator total-fertility-rate` is the main path; `--adapter rbi-handbook` is a scope filter. A DERIVED in-memory index `indicator_id -> [adapter_slug]` (walked from the specs at import; NEVER committed - Holy Law #6) resolves either direction. Resolution is one-directional: a source resolves FROM an indicator; identity is NEVER minted from a source. | user + Fowler F3 + Gregor G3 |
| `--adapter` flag (naming collision) | The CLI selector + registry key is **`adapter_slug`** (`rbi-handbook`), surfaced as `--adapter`. This is DISTINCT from the citation `source_id` (`src-<sha256[:12]>`). The flag is `--adapter` (precise, self-explanatory), never `--source`. | user + Fowler/Gregor flag |
| Fetch granularity / cache unit | FETCH operates at the source's natural **cache unit** (rbi_handbook = one staging file per indicator; an ICED endpoint = one response carrying many indicators). ENRICH slices the requested indicator(s) out of the cached unit. Cache key = `(adapter_slug, cache_unit)`, so `--indicator Y` reuses a response already downloaded for `--indicator X` when both live in one payload. `adapter.cache_unit_for(indicator_id) -> CacheKey` is a contract seam. | Fowler F3 + Gregor |
| Splice is not a verb | One indicator <- many sources is an **emergent UPSERT** (Aggregator on PK `(entity_id, year, period_label, indicator_id)`) with issuing-authority precedence + a visible `methodology_breaks` row - NEVER an operator command. The word "splice" appears only in the read-only `ingest explain --indicator X` diagnostic ("spliced from [a, b]"). | Fowler F3 + Gregor G3 |
| Interface typing (pydantic MANDATORY, SC-3) | Pydantic v2 `BaseModel` for EVERY in-process boundary type: the 3 stage messages (`ClaimCheck`/`RawRecord`/`CanonicalBatch`), the 11 log events, and `SourceSpec`/`IndicatorSpec`. The rule: *any value crossing a stage/process/persistence boundary, or human-authored as a spec/config, is pydantic; exceptions need Fowler/Gregor sign-off.* FOUR pre-approved exceptions stay non-pydantic (they are cross-runtime/persisted DATA contracts, not Python objects): (1) `columns.json` + `csv_validator` (read by DuckDB-WASM too), (2) `derive_source_id`, (3) the JSON-Schema + `x-version` + `_ops` delta-state + `manifest.json` artifacts, (4) the DuckDB-WASM read seam. Never collapse storage+wire+frontend onto one Python type (CDM-too-far). `CanonicalBatch.source_rows` = the 5-field shape (NOT envelope.py's retired 6 fields). | user SC-3 + Fowler F4 + Gregor G1/G4 |
| Inter-stage contract | THREE typed pydantic pipe messages (Pipes-and-Filters), validated at the EDGE (construction at the producing filter), trusted between hops - NOT re-validated every hop: Fetch->Parse = `ClaimCheck{source_id, meadow_path, content_hash}`; Parse->Enrich = `list[RawRecord]`; Enrich->Emit = `CanonicalBatch{target_family, observation_rows[], source_rows[5-field], replacement_semantics}`. Never persists (validate vs `columns.json` at the write seam). Lives under `canonical/`. Events are a Tee to the logger, never dataflow. | Gregor G1 |
| Indicator registry FK | The catalogue (`concepts.json` -> `indicators.json` -> `variables.csv`) is the identity SOT. Every `IndicatorSpec.indicator_id` MUST FK to an `indicators.json` row -> a concept, checked **fail-loud at registration**. The pipeline never mints identity (use `check-overlap` + `pre-flight-ingest`). The indicator->adapter reverse index is DERIVED, never a committed file. | Gregor G2 + Fowler F6 |
| OWID-at-indicator + source-independent fetch | OWID compliance is at the INDICATOR level (concept + unit + normalisation + provenance + break-surfacing); the acquisition FORMAT (csv/api/pdf/xlsx) is an orthogonal adapter concern; the splice happens in ENRICH. | user + Hans + Fowler |
| Splice vs two series | TARGET is ONE OWID-standard `indicator_id` with a VISIBLE break, NOT two co-plotted series. SPLICE iff (1) same concept tuple, (2) same sampling-frame/definition, (3) complementary/overlapping coverage, (4) the join break is surfaced. FORCE TWO series only when (1) or (2) fails. The parallel agent's "never one line" rule applies ONLY to the fails-(1)/(2) case. | Hans H-A |
| Provenance vs series identity | ORTHOGONAL. `indicator_id` keys on the concept; `source_id` keys on the citation. SC-2 re-labels `source_id` and NEVER touches `indicator_id` / never splits a series. | Hans H-B |
| Splice precedence | issuing-authority-wins -> single clean cut-over year (no row-by-row interleave) -> latest-vintage UPSERT (RE -> Final). Record boundary + precedence on a `methodology_breaks` row; keep each row's true `source_id`; overlap-year divergence is disclosed, never silently overwritten. | Hans H-C |
| Year checkpoint key | Key = `(year, vintage/content-fingerprint)`; skip-predicate = VALUE-EQUALITY, never year-existence. Skip P iff `P <= last_completed_period AND hash(input_P) == recorded_hash_P`. A revised old year (BE -> RE -> Final) changes its hash and FORCES re-emit. | Hans H-E + Fowler F-D |
| Config model | One typed pydantic spec registry per adapter (`SourceSpec` parent + `IndicatorSpec` children - de-duplicates the source-level provenance the current `HbsTableSpec` repeats). NOT JSON, NO pydantic-settings, NO global config object, NO `config/sources.json`. Override layering: spec (compile-time) < CLI flag (per-invocation) < env var (machine paths only). | Fowler + F6 |
| Fetch reintroduction | Per-spec optional `fetch()` hook writes raw bytes to gitignored `_meadow/` + the COMMITTED year-checkpoint receipt under `datasets/_ops/`. httpx (already a dep), bounded 3-try loop, NO tenacity, NO re-added `core/http.py`. Per-spec `fetch_mode="operator_staged"` fallback for flaky-TLS (`cea.nic.in`). | Fowler |
| State placement | (a) DURABLE resume-checkpoint + delta-state = committed `datasets/_ops/` WITH `$schema` + `x-version`; (b) EPHEMERAL per-run progress mirror + logs = `.runtime/logs/<run_id>/` (never the resume authority); (c) freshness = `manifest.json` ONLY. "Published states in /docs" REJECTED (a drifting projection of manifest.json; render at read-time instead). | Gregor + Fowler F-D |
| Observability + logs | Per-stage + orchestrator JSON-lines files `.runtime/logs/<run_id>/{orchestrator,discover,fetch,enrich,publish}.log` via a `stage` param on `StructuredLogger`. `run_id` = `YYYYMMDD-xxxxxxxx`; a `(adapter_slug, indicator_id, period)` correlation id threads a run end-to-end. Add EXACTLY ONE event `fetch.skipped`. `ALL_EVENT_NAMES` stays pinned; events become pydantic (SC-3) but keep their stable names. | Fowler F-C + SC-3 |
| Path discipline | `ingest/paths.py::to_repo_relative_posix(p, *, repo_root)` is the single path-emit seam (relativize, force `/`, fail-fast on a surviving drive letter / escape). Route `events.py` through it - FIXES the live `as_posix()` drive-letter bug. | Fowler F-E |
| Cleanup | `python -m yen_gov ingest clean [--days N] [--force] [--dry-run]`, default 90-day retention, `N < 90` requires `--force`. Targets = a declared `CLEAN_TARGETS` list (stale `.runtime/raw/` http caches + `.runtime/logs/` older than N). HARD invariant: every target resolves under `.runtime/`; NEVER touches committed `_ops/`, `datasets/**`, `config/`, `docs/`. | Fowler F-E |
| Doc discipline | Every decision gets the keep-receipts triplet: `## Design rationale` + `## Alternatives considered` (one line per rejected alt + revisit trigger) + `## Deferred / out of scope`. Home: NEW `docs/architecture/ingest/pipeline.md` (subsystem + operator mental model) + NEW `docs/reference/cli-ingest.md` + UPDATE the two stale docs. Anti-bloat: one concept once, rejected-alts one line, deferred bounded; docs land in the SAME commit as the code; agent-only gotchas -> `/memories/lessons.md`. | user + Fowler F5 |
| ICED/NITI producer | `producer` = the issuing authority, NEVER the product. ICED republishing CEA/MoSPI/MoEFCC -> producer = authority, title = "... (via NITI ICED <api>)", UPSERT into the existing concept. NITI-originated -> producer = "NITI Aayog". Fail-loud FK gate. | Hans + Max |
| Enrich hard-gates | FAIL LOUD on: entity-resolution (no fuzzy, no implicit zero), unit canonicalisation (nominal-vs-constant INR), period normalisation (fiscal != calendar), concept-overlap reuse (>= 0.70), methodology-break presence (a discontinuity with no break row HALTS), no-silent-definition-drift. | Hans |
| Sequencing vs the parallel agent | Phase A is greenfield. Prove on a COLD family (`rbi_handbook` + a new HBS cohort), then greenfield SDG India Index, then touch HOT energy/`iced_*` + the `source.csv` reattribution LAST, after the parallel arc merges. `source.csv` + `columns.json` FROZEN / additive-only. | Max + Gregor |

---

## Section 1 - Status Reckoner (rows are PRs)

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| 1 | Pydantic stage messages + `SourceSpec`/`IndicatorSpec` + indicator-registry FK gate | [ ] PENDING | - | M |
| 2 | Committed year-checkpoint + delta-state receipt schema + Tier-B gate | [ ] PENDING | - | S |
| 3 | `ingest/paths.py` util + per-stage/orchestrator log files + events->pydantic + `fetch.skipped` + run_id | [ ] PENDING | - | M |
| 4 | `ingest` master orchestrator + adapter registry + derived indicator index + Stage 0 + `run_pipeline` + CLI | [ ] PENDING | - | L |
| 5 | Autonomous Fetch hook + cache-unit fetch + delta-skip + year-checkpoint resume (2nd cold caller) | [ ] PENDING | - | M |
| 6 | Enrich hard-gates + OWID splice (emergent) + `explain` diagnostic + auto pre-flight | [ ] PENDING | - | M |
| 7 | Extract manifest writer out of `writer.py`; verify ECI Parquet callers | [ ] PENDING | - | S |
| 8 | Flip 3 ECI adapters (`eci_ls`, `eci_ae_panel`, backfill) to `write_csv` | [ ] PENDING | - | M |
| 9 | Delete `envelope.py` + `writer.py` + dead dim-rows + residual Parquet | [ ] PENDING | - | M |
| 10 | ICED -> issuing-authority producer correction (orthogonal to series) - AFTER hot arc | [ ] PENDING | - | M |
| 11 | Greenfield NITI SDG India Index (3rd caller) -> ratify shared `run_pipeline` | [ ] PENDING | - | L |
| 12 | `ingest clean` command + runtime-dir env override | [ ] PENDING | - | S |
| 13 | Docs: NEW `docs/architecture/ingest/pipeline.md` + `cli-ingest.md`; rewrite stale docs + CLAUDE.md + distill | [ ] PENDING | - | M |

Phase lines: A = {1,2,3} -> B = {4,5,6} -> C = {7,8,9} -> D = {10,11} (waits for the parallel arc) -> E = {12,13}. Row 11 depends on Rows 4-6. Row 12 depends on Row 3 (the path util). Rows 8-9 depend on Row 7.

---

## Section 1b - Plain-English PR table

| # | Feature (plain English) | Problem it fixes | How it scales / stays flexible |
| --- | --- | --- | --- |
| 1 | Typed (pydantic) hand-off slips between stages + typed source/indicator specs that must match the catalogue | Stages pass ad-hoc shapes; an adapter could invent an indicator id the catalogue never heard of | Every source speaks 3 validated messages; a bad spec fails at load, not mid-run |
| 2 | A committed year-checkpoint ledger ("what we already did, and the hash of each year") | Re-does full work every run; a revised old year could be silently skipped | Year-keyed delta; a corrected old year re-opens; survives a fresh clone |
| 3 | Per-stage + orchestrator machine logs, a run id, a never-full-path util, pydantic events | Pipeline is silent; logs leak `C:\` drive letters; no per-stage isolation | Tail one `fetch.log`; agents parse run state; paths stay POSIX/relative |
| 4 | The `ingest` orchestrator: address work by INDICATOR, resolve to its source(s); a registry of adapters | Each source hand-rolls plumbing; no hierarchical mental model; adding a source rewrites code | `ingest run --indicator tfr`; new source = one registry line + one adapter; orchestrator never changes |
| 5 | Autonomous fetch at the source's cache granularity + per-indicator slice + delta skip + resume | No automation; can't refresh one indicator without re-doing a source; no resume | Refresh one indicator from a shared download; skip unchanged years; resume after a crash |
| 6 | Fail-loud enrich gates + "splice into one honest series" + an `explain` diagnostic | Silent coercions corrupt comparisons; unclear when to merge vs split publishers | One concept = one trend line with a visible break; `explain` shows where a series came from |
| 7 | Move the manifest writer out of the Parquet module | `writer.py` is double-loaded, can't delete cleanly | Unblocks the Parquet rip |
| 8 | Switch the last 3 election adapters to CSV | They still emit Parquet via the old envelope | Finishes one-format for elections |
| 9 | Delete the Parquet writer + typed-batch + dead dims | Forbidden machinery still ships | Exactly one publish path |
| 10 | Fix ICED provenance: producer = the real issuing authority | Org+product mashed; republished CEA data mis-attributed | Provenance scales; series identity untouched |
| 11 | Prove on a brand-new source (SDG India Index) + lock the shared runner | Need a 3rd caller + a greenfield proof | The shared engine is ratified on evidence |
| 12 | A safe `ingest clean` for stale caches + old logs | `.runtime` fills up; no retention policy | 90-day default, `--force`, `--dry-run`; only touches `.runtime/` |
| 13 | Full subsystem docs + CLI reference + rewrite of the stale docs | Docs reference deleted modules; future agents must guess | The next agent copies a template that compiles; why/what/left-out recorded |

---

## Section 2 - Target architecture

```
CLI (indicator-primary; source resolved underneath):
  python -m yen_gov ingest run     --indicator total-fertility-rate            # main path
  python -m yen_gov ingest run     --indicator nsdp-inr-crore                  # -> 2 adapters; writer UPSERT-splices + break
  python -m yen_gov ingest run     --adapter rbi-handbook                      # scope filter: every indicator that adapter owns
  python -m yen_gov ingest fetch   --indicator birth-rate                      # ONE stage
  python -m yen_gov ingest enrich  --indicator birth-rate                      # re-parse from cache, no re-download
  python -m yen_gov ingest run     --indicator birth-rate --from fetch --to enrich
  python -m yen_gov ingest run     --adapter rbi-handbook --resume             # crash recovery
  python -m yen_gov ingest status                  # per-adapter last-run + staleness vs update_period_days
  python -m yen_gov ingest list-indicators [--adapter X] [--stale]
  python -m yen_gov ingest list-adapters
  python -m yen_gov ingest explain  --indicator nsdp-inr-crore                 # read-only: "spliced from [rbi-handbook, iced-state-wise]"
  python -m yen_gov ingest clean    [--days N] [--force] [--dry-run]
   |
   v
orchestrate(*, indicator|adapter, repo_root, config)         # THIN; never branches on adapter_slug
   |   registry: {adapter_slug -> Adapter}                    # Adapter = SourceSpec(IndicatorSpec...) + parser + optional fetch()
   |   DERIVED index: {indicator_id -> [adapter_slug]}        # in-memory, walked from specs; resolve indicator -> source(s)
   |   FK-check every IndicatorSpec.indicator_id vs indicators.json (fail-loud at registration)
   |   mint run_id (YYYYMMDD-xxxxxxxx); open per-stage loggers; read committed year-checkpoint
   v
run_pipeline(spec, work_list, logger)                        # source-agnostic engine; pure pydantic-typed filters
   |
   |-- STAGE 0  DISCOVER + DESIGN
   |     design (authoring-time, once): SourceSpec/IndicatorSpec + check-overlap + pre-flight-ingest -> green
   |     discover (run-time): validate spec + list local cache units + diff vs checkpoint -> work-list of periods
   |
   |-- STAGE 1  FETCH (per-spec fetch() at the source's CACHE UNIT, OR fetch_mode="operator_staged")
   |     raw bytes -> datasets/<family>/_meadow/<adapter>/<vintage>/   (gitignored)
   |     update committed year-checkpoint: datasets/_ops/ingest-state/<adapter_slug>.json
   |     emit fetch.started / fetch.completed / fetch.skipped (year delta) / fetch.failed
   |     -> ClaimCheck{source_id, meadow_path, content_hash}
   |
   |-- STAGE 2  ENRICH (pure parse of ONLY the requested indicator's slice -> resolve entity_id, canonicalise
   |     unit, normalise period, FK indicator_id, derive source_id; multi-source rows UPSERT-merge onto one
   |     indicator_id with a methodology break; FAIL LOUD on every gate)
   |     -> CanonicalBatch{target_family, observation_rows[], source_rows[], replacement_semantics}
   |
   |-- STAGE 3  PUBLISH (validate batch vs columns.json; UPSERT via write_csv on PK; upsert source.csv; advance checkpoint)
         -> datasets/data/...csv   (the one canonical store the frontend reads)

observability: .runtime/logs/<run_id>/{orchestrator,discover,fetch,enrich,publish}.log  (JSON-lines)
durable state: datasets/_ops/ingest-state/<adapter_slug>.json   (committed: last_completed_period + per-period content_hash)
freshness:     datasets/manifest.json   (machine inventory; human view = read-time render, NOT a docs file)
```

State homes (final):

| State class | Home | Committed? | Contract |
| --- | --- | --- | --- |
| Raw snapshot bytes | `datasets/<family>/_meadow/<adapter>/<vintage>/` | no (gitignored) | none (re-fetchable via checkpoint) |
| Year-checkpoint + delta-state | `datasets/_ops/ingest-state/<adapter_slug>.json` | yes | `datasets/schemas/ingest-state.schema.json` x-version, Tier-B gate |
| Per-run progress + logs | `.runtime/logs/<run_id>/{orchestrator,discover,fetch,enrich,publish}.log` | no (ephemeral) | per-line JSON; cleaned after 90d |
| Published observations | `datasets/data/**.csv` | yes | `columns.json` (frozen) |
| Provenance ledger | `datasets/data/entities/source.csv` | yes | 5-field sources schema (frozen, additive-only) |
| Indicator identity SOT | `concepts.json` -> `indicators.json` -> `variables.csv` | yes | catalogue schemas; pipeline FKs in, never owns |
| Freshness inventory | `datasets/manifest.json` | yes | `manifest.schema.json` x-version |

### 2b - Orchestrator inspiration (`puzzle_manager`), YAGNI-filtered

ADOPT: thin orchestrator over an adapter registry; `run` + stage subcommands + `status` + `list-*` + `clean --dry-run`; `run_id` = `YYYYMMDD-xxxxxxxx`; a correlation id; the `.runtime/` layout + a `YEN_GOV_RUNTIME_DIR` env override; a dedicated `paths.py`.
REFUSE: `rollback` + `audit.jsonl` (git + idempotent writer is the undo); an `inventory` module (`manifest.json` + `list-*` + `status` cover it); an `active_adapter` config default (use `--adapter`); tenacity. Keep typer.

---

## Section 3 - Per-row specs

### Row 1 - Pydantic stage messages + `SourceSpec`/`IndicatorSpec` + indicator-registry FK gate
- Scope: define the three pydantic pipe messages, the two-level pydantic spec (`SourceSpec` parent + `IndicatorSpec` children), and the fail-loud registration FK that every `IndicatorSpec.indicator_id` resolves in `indicators.json`.
- Files: NEW `backend/yen_gov/ingest/messages.py` (`ClaimCheck`, `RawRecord`, `CanonicalBatch`, `ReplacementSemantics`); NEW `backend/yen_gov/ingest/spec.py` (`SourceSpec`, `IndicatorSpec`, `FetchMode`); NEW `backend/yen_gov/ingest/catalogue_fk.py` (registration FK check vs `indicators.json`); tests.
- Gates: pytest + mypy green; `CanonicalBatch.source_rows` is the 5-field shape; a spec declaring an indicator_id absent from `indicators.json` RAISES at registration; the three messages are pydantic `BaseModel(frozen=True, extra="forbid")`.
- ONE oracle: a contract test asserts `CanonicalBatch.observation_rows` keys equal the non-facet column set of the `geo/*.csv` file class in `columns.json` AND a spec with a bogus indicator_id fails registration.

### Row 2 - Committed year-checkpoint + delta-state receipt schema + Tier-B gate
- Scope: the committed checkpoint artifact + schema + Tier-B check, carrying `last_completed_period` + `periods: {year: content_hash}`.
- Files: NEW `datasets/schemas/ingest-state.schema.json` (x-version 1.0); NEW `backend/yen_gov/ingest/state.py` (read/write/compare + composite-key + skip-predicate); a `tier_b_ingest_state_receipt` check in `validate.py`; tests.
- Gates: schema passes schema-of-schemas; Tier-B rejects a malformed receipt; helpers pure + `tmp_path`-tested; no `datetime.now()` in row content.
- ONE oracle: write a receipt for {2018..2022}; assert 2019 is skipped when its input hash matches and FORCED to re-process when the 2019 hash changes (Hans H-E).

### Row 3 - `ingest/paths.py` util + per-stage/orchestrator logs + events->pydantic + `fetch.skipped` + run_id
- Scope: the observability + path-discipline + pydantic-events seam. Add `ingest/paths.py::to_repo_relative_posix`; convert the 11 `core/events.py` events to pydantic (SC-3) routing path fields through the util (fixes the drive-letter bug); add a `stage` param to `StructuredLogger`; add `fetch.skipped`; add `_mint_run_id()`.
- Files: NEW `backend/yen_gov/ingest/paths.py` + tests; EDIT `core/events.py` (dataclass->pydantic `BaseModel(frozen=True)`; replace the `fields()` loop in `to_extra()` with `model_dump()`; ClassVar `event_name`/`level` stay class attrs; `FetchSkipped` + append to `ALL_EVENT_NAMES`); EDIT `core/logging.py` (stage param -> `<run_id>/<stage>.log`); EDIT `cli.py` (`_mint_run_id`); update tests.
- Ripple (SC-3 second-order): `to_extra()` `fields()` -> `model_dump(mode="json")`; the `emit()` signature stays; `ALL_EVENT_NAMES` pin test updated same commit; no event renamed; verify no other caller does `dataclasses.asdict()` on an event (grep confirmed none in core).
- Gates: pytest green; a logged Windows-style `Path` emits as repo-relative POSIX with no `C:`; `ALL_EVENT_NAMES` grows by exactly one (`fetch.skipped`); events are pydantic.
- ONE oracle: a test logs a Windows absolute `Path` through a pydantic event and asserts the emitted JSON field is repo-relative POSIX with no drive letter.

### Row 4 - `ingest` master orchestrator + adapter registry + derived indicator index + Stage 0 + `run_pipeline` + CLI
- Scope: the scaffold. NEW `backend/yen_gov/ingest/` subsystem: `orchestrate(*, indicator|adapter, ...)` thin driver; `{adapter_slug: Adapter}` registry; the DERIVED `{indicator_id: [adapter_slug]}` index built at import; Stage 0 (run-time discovery: validate spec + list cache units + diff vs checkpoint -> work-list); `run_pipeline(spec, work_list, logger)` extracted from `rbi_handbook` (1st caller, parity); the CLI verbs (`run`, stage subcommands, `status`, `list-indicators`, `list-adapters`, `explain`).
- Files: NEW `ingest/{orchestrator.py, registry.py, pipeline.py, cli.py}`; EDIT `rbi_handbook/ingest.py` to route through `run_pipeline`; EDIT top-level `cli.py` to mount the `ingest` typer app; tests.
- Gates: pytest green; `rbi_handbook` output byte-identical pre/post extraction (parity); `ingest run --indicator total-fertility-rate` resolves to `rbi-handbook` and emits; the orchestrator contains zero `if adapter_slug ==` branches; `list-indicators` shows the catalogue + owning adapter.
- ONE oracle: a parity test asserts `rbi_handbook` CSV output is byte-identical pre/post; AND `ingest run --indicator total-fertility-rate` produces the same rows as `--adapter rbi-handbook --indicator total-fertility-rate`.

### Row 5 - Autonomous Fetch hook + cache-unit fetch + delta-skip + year-checkpoint resume (2nd cold caller)
- Scope: the per-spec `fetch()` hook (httpx, bounded 3-try) operating at the source's cache unit; per-indicator enrich slice from the shared cache; the year-delta skip; `operator_staged` fallback; a 2nd cold caller (new RBI HBS cohort) as proof; `--resume`.
- Files: NEW `ingest/fetch.py` (`run_fetch(spec, logger) -> ClaimCheck`, cache-unit dedup); NEW `canonical/adapters/rbi_hbs_<cohort>/`; EDIT specs (`fetch_url`/`fetch_mode`/`spec_version`/`cache_unit`); promote httpx out of the `admin` extra if needed; tests with a mocked `fetch`.
- Gates: pytest green; two requested indicators sharing one cache unit fetch ONCE; a 2nd run with unchanged years emits `fetch.skipped` + zero new CSV bytes; a `spec_version` bump forces re-emit; `cea`-class resolves to `operator_staged`; NO tenacity/`core.http`.
- ONE oracle: run the cohort twice against a fixture - run 2 (identical years) `fetch.skipped` + CSV mtime untouched; mutating one year's fixture re-emits exactly that year; two indicators sharing a cache unit trigger one fetch.

### Row 6 - Enrich hard-gates + OWID splice (emergent) + `explain` diagnostic + auto pre-flight
- Scope: the six fail-loud enrich gates + the emergent splice (issuing-authority precedence, clean cut-over, break-on-join, disclosed divergence) + the read-only `ingest explain --indicator X` diagnostic + auto `check-overlap`/`pre-flight-ingest`.
- Files: NEW `ingest/enrich_gates.py` + `splice.py` (reusing `pipeline/compose.py`); EDIT `run_pipeline`; EDIT `ingest/cli.py` (`explain`); tests incl. a 2-source splice fixture.
- Gates: pytest green; each gate RAISES on bad input (an unmapped state aborts, not an implicit zero); a 2-source fixture splices onto ONE indicator_id with a break row + each row's `source_id` intact; `explain` lists the contributing adapters; pre-flight exit-2 aborts with no override.
- ONE oracle: a 2-source splice test asserts one indicator_id, rows from A (years <= cut) + B (years > cut), each `source_id` intact, exactly one `methodology_breaks` row at the boundary; `explain --indicator X` returns `[A, B]`.

### Row 7 - Extract manifest writer out of `writer.py`; verify ECI Parquet callers
- Scope: move `_regenerate_manifest` into a parquet-free `canonical/manifest.py`; repoint callers; verify whether the 3 ECI `write_batch` callers emit or already hit the `elections`-envelope raise.
- Files: NEW `canonical/manifest.py`; EDIT `cli.py` + `pipeline/dim_acs_lgd_lift.py`; PR-body verification note.
- Gates: pytest green; `manifest.json` regenerates byte-identical; no `_regenerate_manifest` import from `writer.py`.
- ONE oracle: byte-identity of `manifest.json` before/after.

### Row 8 - Flip 3 ECI adapters to `write_csv`
- Scope: convert `eci_ls`, `eci_ae_panel`, `pipeline/canonical_eci_backfill` to `write_csv`, preserving every election row; skip any caller Row 7 proved dead.
- Files: EDIT the three adapters + CLI + tests; additive `source.csv` upsert.
- Gates: pytest green; per-event row counts preserved (a drop is an ESCALATE); CSV passes Tier-B; `source.csv` append-only.
- ONE oracle: per-event before/after parity of `(entity_id, year, indicator_id)` tuples.

### Row 9 - Delete `envelope.py` + `writer.py` + dead dim-rows + residual Parquet
- Scope: the rip. Delete the Parquet writer, the typed batch, the dead dim-row dataclasses, the likely-dead `dim_acs_lgd_lift.py`; clean residual `read_parquet` / `FORMAT PARQUET` / stale docstrings.
- Files: DELETE `canonical/writer.py` + `canonical/envelope.py` + (if dead) `pipeline/dim_acs_lgd_lift.py`; EDIT `canonical/__init__.py`, `eci_ae_panel.py`, `ingest_pincode.py`, `cli.py`; delete orphan tests.
- Gates: pytest green; `grep -r "write_batch|BatchEnvelope|to_parquet|read_parquet|FORMAT PARQUET" backend/` returns ZERO live hits; full Tier-B passes.
- ONE oracle: a repo-wide grep gate proving zero Parquet writer/reader/envelope symbols remain in `backend/`.

### Row 10 - ICED -> issuing-authority producer correction (orthogonal to series) - AFTER hot arc
- Scope: per SC-2 + Hans/Max. Build the `(producer, title, vintage)` triple-registry, regenerate the 31 ICED `source.csv` rows (producer = issuing authority; ICED -> title), rewrite observation `source_id` FKs, add the fail-loud FK gate. `indicator_id` untouched. RUN ONLY after the parallel arc merges.
- Files: NEW `canonical/iced_authority_map.py` + `docs/research/iced-authority-tracing.md`; EDIT iced citation calls; regenerate `source.csv` + datapoints; EDIT `validate.py` (FK gate + producer-is-not-a-product assertion).
- Gates: pytest green; zero dangling `source_id`; no `producer` contains a product name; the set of `indicator_id`s is identical before/after.
- ONE oracle: a Tier-B check asserts every `producer` is in the closed authority set, every `source_id` exists in `source.csv`, and the `indicator_id` set is unchanged.

### Row 11 - Greenfield NITI SDG India Index (3rd caller) -> ratify shared `run_pipeline`
- Scope: ingest a new NITI-originated source end-to-end (producer = "NITI Aayog"; 3rd single-series caller). Ratify `run_pipeline` (Rule of Three; no further refactor). Faceted CEA/energy stays separate (documented).
- Files: NEW `canonical/adapters/niti_sdg_index/`; NEW CLI route; a committed green `proposal.json` + `pre-flight-ingest` report; tests + a coverage note.
- Gates: pytest green; pre-flight verdict in {mint_new, upsert, add_facet}; the three single-series callers byte-identical vs pre-ratification; faceted path explicitly NOT folded in.
- ONE oracle: byte-identical parity of all three single-series callers before/after ratification.

### Row 12 - `ingest clean` command + runtime-dir env override
- Scope: `python -m yen_gov ingest clean [--days N] [--force] [--dry-run]`; default 90d; `N < 90` requires `--force`; targets = `CLEAN_TARGETS` (stale `.runtime/raw/` + `.runtime/logs/` older than N); add the `YEN_GOV_RUNTIME_DIR` env override.
- Files: NEW `ingest/cleanup.py` (routed through `ingest/paths.py`); EDIT `ingest/cli.py`; EDIT the runtime-dir resolver; tests.
- Gates: pytest green; `--dry-run` mutates nothing; every target asserts-resolves under `.runtime/`; a test proves the cleaner REFUSES a target outside `.runtime/` (never touches `_ops/`, `datasets/**`, `config/`, `docs/`); `N < 90` without `--force` aborts.
- ONE oracle: seed `.runtime/logs/<old>` (mtime > 90d) + `datasets/_ops/ingest-state/x.json`; run `clean`; assert the old log dir is gone and the committed checkpoint is untouched.

### Row 13 - Docs: NEW subsystem + CLI reference; rewrite stale docs + CLAUDE.md + distill
- Scope: NEW `docs/architecture/ingest/pipeline.md` (subsystem + operator mental-model section, keep-receipts triplets for every Section-5 decision) + NEW `docs/reference/cli-ingest.md` (verb + flag table); rewrite [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) + [docs/how-to/add-a-new-data-source.md](../docs/how-to/add-a-new-data-source.md) to the `ingest`/`run_pipeline`/`write_csv` reality with the `SourceSpec`/`IndicatorSpec` template; record SC-1 + SC-3 in `CLAUDE.md` + the decision index; refresh bootstrap; distill this plan.
- Gates: a docs-link/grep check passes (zero `core.http`/`core.io.Source`/`write_artifact`/`write_batch`/"Lift" stale refs); CLAUDE.md + docs agree; the plan carries a per-row distillation map.
- ONE oracle: a grep gate asserts zero occurrences of the deleted symbols + the retired "Lift" brand across `docs/` (except the historical note in the decision index).

---

## Section 4 - YAGNI refusals (explicitly NOT built)

A DAG/workflow engine; a materialized "garden"/enrich tier; a runtime endpoint/period crawler; a general N-source splice engine before the first real 2-source indicator; a second checkpoint file; `pydantic-settings`/a global `Settings`/`config/sources.json`/an `active_adapter` default; a plugin/entry-point adapter registry; a `rollback`+`audit.jsonl` subsystem; an `inventory` module; a `splice` verb; a committed per-run receipt; a second human-prose log sink; a `source_id` alias table; re-adding `tenacity`/`core/http.py`; a generated published-state report under `docs/`; folding the faceted (CEA/energy) row shape into the single-series `run_pipeline`; a committed indicator->adapter reverse index.

---

## Section 5 - Decisions log (why / what / rejected / deferred)

The user requires every decision documented so future agents never guess. Each row: the decision, why, the rejected alternative (one line), and what is deferred. These seed the keep-receipts triplets in `docs/architecture/ingest/pipeline.md` (Row 13).

| Decision | Why | Rejected alternative | Deferred / left out |
| --- | --- | --- | --- |
| Name = `ingest` | The repo already speaks it (`*-ingest-handover.md`, `ingest-*` verbs, spine "acquire"); zero new vocabulary | "Lift" (user: ugly); `harvest`/`acquire` (fine, but less established) | A citizen-facing brand name (operator-only surface; not needed) |
| Indicator-primary CLI | Agents+humans think in indicators; the indicator is the logical address | Source-primary (Fowler's first call; reversed by the user) | A GUI/admin surface for the same model |
| `--adapter` flag | Precise + self-explanatory; avoids the `source` vs `source_id` collision | `--source` (familiar but ambiguous with the citation `source_id`) | An `active_adapter` default (use `--adapter` explicitly) |
| Stage subcommands + `--from`/`--to` | Self-documenting per-stage runs; plain-English windows | `--only-stage` (user: ugly); colon-slice `fetch:` (cute/obscure) | A `--to`-only "stop early" with no `--from` (no named need yet) |
| Pydantic mandatory (SC-3) | One typed object model at every boundary; bad specs/messages fail at the edge | Frozen dataclasses in-process (Fowler's first call; reversed by the user) | Converting the 4 cross-runtime DATA contracts (they stay non-pydantic by Fowler/Gregor sign-off) |
| Splice is emergent, not a verb | Two adapters sharing an indicator_id UPSERT-merge with a break; a verb would invent a Composer the static store does not need | A `splice` command | A multi-source precedence DSL beyond issuing-authority-wins |
| Year-checkpoint by `(year, content-hash)` | A revised old year must re-open; year-existence would freeze stale history | High-water-mark-only skip | A sub-year (quarter/month) checkpoint grain (add when a sub-year source lands) |
| Committed checkpoint in `_ops/`, logs in `.runtime/` | The next run reads the checkpoint (must survive a clone); logs are per-run telemetry | All state in `.runtime/` (puzzle_manager style; fresh clone would re-process) | A committed per-run receipt (no reader today) |
| Derived indicator->adapter index | Adapters are the SOT for "who fetches this"; a committed index would drift | A committed reverse-index file | - |
| Reuse the existing catalogue as identity SOT | `concepts.json`->`indicators.json`->`variables.csv` already is the SOT | A new pipeline-owned indicator registry | - |

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. The rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main`. Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** As soon as a row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next. Pre-existing unrelated failures are not gating - document the baseline.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** On a contested call, run the authority personas (CLAUDE.md section 0a) in debate; bake the single verdict into the row.
6. **Manage context via offload.** Push breadth-y reads/audits into subagents; the orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop only at an ESCALATE trigger (Level-5), a STOP-AND-SURFACE scope-narrowing (CLAUDE.md section 10), or an audit chain past depth 3.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. Archive the plan with a per-row distillation map.

> Plan-specific execution notes (binding): (a) Phases A -> B -> C -> D -> E; Phase D (Rows 10-11) waits for the parallel energy/`iced_*` arc to merge - rebase first. (b) `source.csv` + `columns.json` FROZEN / additive-only. (c) Rows 8-10 touch election + provenance data: a row-count drop or a dangling FK is an ESCALATE. (d) Work each row in a dedicated worktree off fresh `origin/main`; never share a worktree with a parallel agent. (e) Every path-emit routes through `ingest/paths.py`; the cleaner refuses any target outside `.runtime/`. (f) Pydantic is mandatory (SC-3) for new in-process boundary types; the four enumerated DATA-contract exceptions stay non-pydantic.

## See also

- [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) - the doctrine this plan modernizes + renames `ingest` (Row 13 rewrites it).
- [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) - the gold template (the 1st `run_pipeline` caller).
- [datasets/taxonomy/concepts.json](../datasets/taxonomy/concepts.json) -> [datasets/taxonomy/indicators.json](../datasets/taxonomy/indicators.json) -> [datasets/data/variables.csv](../datasets/data/variables.csv) - the indicator identity SOT.
- [docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md) - the existing RBI NSDP cross-base-year splice precedent.
- `miztiik/yen-go` `backend/puzzle_manager` - the thin config-driven orchestrator this is modelled on.
- [CLAUDE.md](../CLAUDE.md) - the engineering contract (authority table section 0a).

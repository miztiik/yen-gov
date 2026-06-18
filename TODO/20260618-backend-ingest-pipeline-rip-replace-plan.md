# Backend ingest pipeline - rip-and-replace to an autonomous Discover -> Fetch -> Enrich -> Publish ETL

**Last Updated**: 2026-06-18
**Level**: 5 (core design + data model + runtime). The whole plan PAUSES for user ratification before any row executes. Execution also WAITS for the in-flight parallel energy/`iced_*` reingest arc to merge. This document is AUTHORED, not yet implemented.
**Strategy**: RIP AND REPLACE (target-state direct). No strangler-fig, no backwards-compat shims, no parallel old+new paths. The app MAY break temporarily until the migration finishes.

> Authored via the `prepare-plan` skill after two persona consults (Fowler, Gregor, Hans, Max; then a Fowler+Hans debate on OWID-splicing and the orchestrator). Design inspiration taken from the sibling repo `miztiik/yen-go` `backend/puzzle_manager` (a thin config-driven multi-source 3-stage pipeline). Every contested call carries a baked-in written ruling so execution is blind rule-following. The `Execution contract` block near the bottom is the whole instruction set for "implement it".

---

## Section 0 - Operating contract

### 0.1 Why this plan exists

The user wants each upstream source (RBI, ICED, NITI, ...) to run **autonomously through staged Discover -> Fetch -> Enrich -> Publish** when triggered, driven by a **lightweight master orchestrator** that processes a source from its config (sources are **adapters**; many more will be added). The pipeline needs **centralized config + sane defaults + per-invocation overrides** (DRY / KISS / SOLID / YAGNI), **full machine-parseable observability** (per-stage + orchestrator log files, run ids, checkpoints), and **state-managed batched + delta fetches keyed on year** so unchanged upstream is never re-processed.

The verified reality (research, 2026-06-18):

- The vision is **already documented** as the 4-layer "Lift pipeline" (Fetch -> Parse -> Enrich -> Emit) in [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) + [docs/how-to/add-a-new-data-source.md](../docs/how-to/add-a-new-data-source.md), but both docs are **stale** (they import deleted `core.http.Fetcher`, `core.io`, `write_batch`, Parquet, the retiring `_meadow/` tier).
- The **gold target template already exists** in code: [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) - a config-driven typed-spec registry + generic parser + state resolver + direct `write_csv` emit + in-place catalogue/source upsert.
- The observability scaffolding ([core/logging.py](../backend/yen_gov/core/logging.py) `StructuredLogger`, [core/events.py](../backend/yen_gov/core/events.py) 11 typed events) **exists and is tested but is wired into nothing** - and [core/events.py](../backend/yen_gov/core/events.py) `to_extra()` calls `Path.as_posix()` which KEEPS the Windows drive letter, a live CLAUDE.md section 2 violation in every logged path.
- The Parquet writer ([canonical/writer.py](../backend/yen_gov/canonical/writer.py) `write_batch`) + the typed batch ([canonical/envelope.py](../backend/yen_gov/canonical/envelope.py)) are a **Holy-Law-#1 residue still live on 3 ECI adapters**.
- **Config infra is nil**; **delta/checkpoint state has zero implementation**; ICED is **31 source.csv rows conflated under one producer string** that mashes org + product.
- yen-gov **already splices** RBI-Handbook NSDP across four MoSPI base years into ONE long series with break markers (per [docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md)) - the OWID-at-indicator-level splice is existing in-house doctrine, not a new idea.

This plan modernizes the documented Lift doctrine, builds the autonomous orchestrated runner with a Discovery/Design Stage 0, wires the dormant observability into per-stage log files + year checkpoints, finishes the Parquet rip, and corrects the ICED/NITI provenance - all target-state-direct.

### 0.2 Hard-coded scope

IN: the shared staged pipeline scaffold (Stage 0, the master orchestrator + adapter registry, typed stage messages, config, per-stage observability, committed year-checkpoint delta-state); autonomous network Fetch with batched + delta semantics (SC-1); the cleanup command + the POSIX/relative path util; finishing the Parquet/envelope rip; the ICED/NITI producer correction (SC-2); one greenfield proof acquisition (NITI SDG India Index); reconciling the stale docs + CLAUDE.md + bootstrap.

OUT: frontend / admin / charting; restructuring the energy + `iced_*` families WHILE the parallel faceted-reingest arc is in flight (Phase D waits for it); changing the `source.csv` 5-field schema or `datasets/data/_schema/columns.json` (frozen, additive-only); any new indicator family beyond the one cold RBI HBS cohort (Row 5) and the greenfield SDG India Index proof (Row 11).

### 0.3 Strategy ruling (rip-and-replace, user-explicit)

The user overrode Fowler's default strangler-fig instinct: "bake the plan to be rip and replace ... we can break the app temporarily until we finish the migration ... plan for the target state directly." Rip rows delete old paths outright; a temporarily-broken ECI ingest between Row 7 and Row 9 is acceptable; the canonical CSV the frontend reads is regenerated at the end of each phase from a coherent corpus.

### 0.4 Scope-change ledger

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
| --- | --- | --- | --- |
| SC-1 | 2026-06-18 | Reintroduce automated network fetch INSIDE the local ingest pipeline: each source runs autonomously Discover -> Fetch -> Enrich -> Publish when triggered, with batched + delta fetch keyed on year so unchanged upstream is never re-fetched or re-emitted. OVERRIDES the 2026-06-03 platform-reset plan section 21.4 ("network-fetch code is deleted; ingest reads local source CSV") and the CLAUDE.md anti-pattern "NO agent may reintroduce ... a network fetcher". Holy Laws #1 + #2 PRESERVED: fetch runs ONLY in the local pipeline; production stays a static bundle; CI consumes committed canonical CSV and never fetches. | user, 2026-06-18 ("if this means change in doctrines, then so be it") |
| SC-2 | 2026-06-18 | ICED ceases to be a `producer`. The producer field becomes the issuing authority (CEA / MoSPI / MoEFCC for republished facts; "NITI Aayog" for NITI-originated products); "India Climate & Energy Dashboard: <endpoint>" moves into `title`. Re-mints the 31 ICED `source_id` values and rewrites their observation FKs (no alias table). This operates on the `source_id`/`producer` axis ONLY and does NOT split any indicator series (orthogonal to indicator identity per Hans H-B). | user-delegated to Hans+Max per CLAUDE.md section 0a; ruling in Section 0.6 |

### 0.5 ESCALATE triggers

- The plan is Level-5: no row executes until the user says "implement it", and execution waits for the parallel energy/`iced_*` arc to merge.
- During execution, STOP and surface only at: (a) a `datasets/schemas/*.schema.json` MAJOR bump; (b) any operation that would DELETE election-results rows rather than re-format them (Row 8 - a row-count drop is an ESCALATE); (c) Row 10 would edit a `source.csv` row the parallel agent is concurrently mutating; (d) an unresolved persona conflict; (e) 3x effort overrun.
- SC-1 and SC-2 are PRE-SIGNED; not re-litigated at execution time.

### 0.6 Authority rulings baked in (zero decision points for the executor)

| Theme | Ruling | Authority |
| --- | --- | --- |
| Pipeline stages | FOUR stages: **Discover + Design (Stage 0) -> Fetch -> Enrich -> Publish**. Stages are pure filters; the orchestrator holds run/checkpoint state. | user + Fowler |
| Stage 0 = Discover + Design | TWO faces. **Design (authoring-time, once per source):** declare the typed `SourceSpec` (concept tuple, unit, normalisation, entity-kinds, methodology-break expectations, `update_period_days` cadence, provenance plan, any splice design) and run `check-overlap` + `pre-flight-ingest` to green. **Discovery (run-time, every run):** load+validate the SourceSpec, discover LOCAL staged inputs, diff against the checkpoint -> emit the work-list of periods to process. Stage 0 is NOT a live endpoint/period crawler (the fetcher was ripped); its run-time output is orchestrator-internal state, not a committed artifact and not a 4th pipe message. | Fowler F-A + Hans H-D |
| Master orchestrator | One thin `orchestrate(source_id, *, repo_root, config)` driver over a hand-written `{source_id: Adapter}` registry. An Adapter = its `SourceSpec`(s) + parser + optional `fetch()` hook (the `rbi_handbook` quartet generalized). The orchestrator NEVER branches on `source_id` (dict dispatch -> Open-Closed: a new source is a registry entry + an adapter package, zero orchestrator edits). `run_pipeline(spec, logger)` is the source-agnostic engine the orchestrator calls per source; the orchestrator is the multi-source driver (the `puzzle_manager` analogue). | Fowler F-B |
| Inter-stage contract | THREE typed pipe messages (Pipes-and-Filters), not one god-message: Fetch->Parse = Claim-Check token `{source_id, meadow_path, content_hash}`; Parse->Enrich = `list[RawRecord]`; Enrich->Emit = `CanonicalBatch{target_family, observation_rows[], source_rows[5-field], replacement_semantics}`. Events are a Tee to the logger, never part of the dataflow. CanonicalBatch never persists (validate vs `columns.json` at the write seam); lives under `canonical/`. | Gregor |
| OWID-at-indicator + source-independent fetch | OWID compliance lives at the INDICATOR level (concept + unit + normalisation + provenance + break-surfacing); the acquisition FORMAT (csv / api / pdf / xlsx) is an orthogonal adapter concern. The splice of multiple publishers into one series happens in ENRICH. Fetch-format independence and indicator-level OWID compliance do not touch each other. | user + Hans + Fowler |
| Splice vs two series | TARGET is ONE OWID-standard `indicator_id` with a VISIBLE methodology break, NOT two co-plotted per-publisher series. SPLICE iff: (1) same concept tuple, (2) same sampling-frame/definition, (3) complementary/overlapping coverage, (4) the join break is surfaced. FORCE TWO series only when it fails (1) or (2) (genuinely different definition / universe / sampling frame / unreconciled price-basis). The parallel agent's "never one trend line" rule is correct ONLY for that fails-(1)/(2) case; it was over-generalized. yen-gov already splices RBI NSDP across 4 base-years - this is existing doctrine. | Hans H-A |
| Provenance vs series identity | ORTHOGONAL. `indicator_id` keys on the measured concept; `source_id = hash(producer, title, vintage)` keys on the citation. One `indicator_id` legitimately carries rows from many producers, each row keeping its own `source_id`. SC-2 (ICED -> issuing-authority producer) re-labels and re-hashes `source_id` and re-points FKs; it NEVER touches `indicator_id` and NEVER splits a series. SC-2 and the splice plan are not in conflict. | Hans H-B |
| Splice precedence | When two sources overlap on the same `(entity, year, indicator)`: (1) issuing authority beats aggregator/re-publisher; (2) pick a single clean cut-over year per window (do not interleave row-by-row) and let the break fall at the join; (3) latest vintage UPSERTs a revised value of the SAME publisher+concept (RE -> Final). Record the splice boundary + precedence on a `methodology_breaks` row; each kept row retains its true `source_id`; a material divergence on an overlap year is a disclosed caveat, NEVER a silent overwrite. | Hans H-C |
| Year checkpoint key | The checkpoint key is `(year, vintage/content-fingerprint)`, and the skip-predicate is VALUE-EQUALITY, never year-existence. Skip period P iff `P <= last_completed_period AND hash(input_P) == recorded_hash_P`. A revised old year (BE -> RE -> Final) changes its hash and FORCES re-enrich/re-publish even though it is below the high-water mark. The estimate stage (BE/RE/Final) is a vintage axis, not a facet. | Hans H-E + Fowler F-D |
| Config model | One typed frozen-dataclass spec registry per source (the `HbsTableSpec` pattern). NOT JSON, NOT pydantic-settings, NO global config object, NO `config/sources.json`. Override layering: spec (compile-time) < CLI flag (per-invocation) < env var (machine paths only). | Fowler F-D(prev) |
| Fetch reintroduction | Per-spec optional `fetch()` hook writes raw bytes to the gitignored `_meadow/` snapshot dir + the COMMITTED delta-state/checkpoint receipt under `datasets/_ops/`. httpx (already a dep), a bounded 3-try loop, NO tenacity, NO re-added `core/http.py`. Per-spec `fetch_mode="operator_staged"` fallback for flaky-TLS sources (`cea.nic.in`). | Fowler |
| State placement | Two artifacts, no conflict: (a) DURABLE resume-checkpoint + delta-state = committed `datasets/_ops/` WITH `$schema` + `x-version` (the next run reads it; an ephemeral one would make every fresh clone re-process); (b) EPHEMERAL per-run progress mirror + logs = `.runtime/logs/<run_id>/` (the troubleshooting surface, never the resume authority); (c) published-artifact freshness = `datasets/manifest.json` ONLY. The user's "state files help understand the last checkpoint" is the ephemeral mirror; the authoritative checkpoint is committed. | Gregor + Fowler F-D |
| "Published states in /docs" | REJECTED. A committed docs report is a drifting PROJECTION of `manifest.json` (violates Holy Law #4). The user's need is a human VIEW - render it at read-time via the admin app or a `python -m yen_gov report` command, not a committed file. User may override. | Gregor |
| Observability + logs | Per-stage + orchestrator JSON-lines log files in `.runtime/logs/<run_id>/{orchestrator,discover,fetch,enrich,publish}.log` (machine-parseable; the existing `msg` field is the only human-readable part - no second prose sink). Achieved by adding a `stage` param to `StructuredLogger` (~3 lines); `events.py` needs no structural change. Add EXACTLY ONE event `fetch.skipped`; run_id format `YYYYMMDD-xxxxxxxx`; a per-work-item correlation id `(source_id, period)` threads a run end-to-end for agent troubleshooting. Do NOT rename any existing event (`ALL_EVENT_NAMES` is pinned). | Fowler F-C + puzzle_manager |
| Path discipline | NEW `core/paths.py::to_repo_relative_posix(p, *, repo_root)` is the single path-emit seam: relativize against repo root, force `/`, fail-fast if a drive letter survives or the path escapes root. Route `events.py` (and every other path-emit site) through it - this FIXES the live `as_posix()` drive-letter bug. | Fowler F-E |
| Cleanup | `python -m yen_gov cleanup [--days N] [--force] [--dry-run]`, default 90-day retention, `N < 90` requires `--force`. Targets are a declared `CLEAN_TARGETS` list (the stale `.runtime/raw/` http caches + `.runtime/logs/` older than N). HARD invariant: every target MUST resolve under `.runtime/`; the cleaner NEVER touches the committed `datasets/_ops/` checkpoint, `datasets/**`, `config/`, or `docs/`. (User said "config-driven destinations" - shipped as a declared list; promote to a small `config/` file only if operator-editability is wanted. SURFACED for the user's call.) | Fowler F-E |
| OWID craft to adopt | Snapshot content-checksum as identity (it IS the delta key); NAME the snapshot -> meadow -> canonical stages with enrich IN-MEMORY. REFUSE a DAG/`make` runner and a materialized "garden"/enrich tier. | Fowler + Max |
| ICED/NITI producer | `producer` = the ORGANISATION / issuing authority, NEVER the product. ICED rows republishing CEA/MoSPI/MoEFCC -> producer = issuing authority, title = "... (via NITI ICED <api>)", UPSERT/facet into the existing authority concept. NITI-originated products -> producer = "NITI Aayog". One triple-registry consumed by both writers; a fail-loud FK gate makes a dangling citation impossible. | Hans + Max |
| Enrich hard-gates | The Enrich stage FAILS LOUD (never silently coerces) on: entity-resolution (no fuzzy guess, no implicit zero), unit canonicalisation (especially nominal-vs-constant-price INR), period normalisation (fiscal != calendar), concept-overlap reuse (>= 0.70 -> UPSERT/facet/splice, never mint), methodology-break presence (a level-discontinuity with no break row HALTS), and no-silent-definition-drift. | Hans |
| Sequencing vs the parallel agent | Phase A is greenfield (freeze-and-own). Prove on a COLD family first (`rbi_handbook` + a new HBS cohort), then the greenfield SDG India Index, then touch the HOT energy/`iced_*` families + the `source.csv` producer reattribution LAST, only after the parallel arc merges. `source.csv` + `columns.json` are FROZEN / additive-only. | Max + Gregor |

---

## Section 1 - Status Reckoner (rows are PRs)

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| 1 | Stage-message contracts (3 typed pipes + SourceSpec Protocol) | [ ] PENDING | - | S |
| 2 | Committed delta-state + year-checkpoint receipt schema + Tier-B gate | [ ] PENDING | - | S |
| 3 | POSIX/relative path util + per-stage & orchestrator log files + `fetch.skipped` + run_id | [ ] PENDING | - | M |
| 4 | Master orchestrator + adapter registry + Stage 0 (Discover+Design) + `run_pipeline` engine | [ ] PENDING | - | L |
| 5 | Autonomous Fetch hook + delta-skip + year-checkpoint resume (2nd cold caller proof) | [ ] PENDING | - | M |
| 6 | Enrich hard-gates + OWID splice rules (one-series splice, precedence, break) + auto pre-flight | [ ] PENDING | - | M |
| 7 | Extract manifest writer out of `writer.py`; verify ECI Parquet callers | [ ] PENDING | - | S |
| 8 | Flip 3 ECI adapters (`eci_ls`, `eci_ae_panel`, backfill) to `write_csv` | [ ] PENDING | - | M |
| 9 | Delete `envelope.py` + `writer.py` + dead dim-rows + residual Parquet | [ ] PENDING | - | M |
| 10 | ICED -> issuing-authority producer correction (orthogonal to series) - AFTER hot arc | [ ] PENDING | - | M |
| 11 | Greenfield NITI SDG India Index (3rd caller) -> ratify shared `run_pipeline` | [ ] PENDING | - | L |
| 12 | Cleanup command (config-driven targets, 90d, `--force`, `--dry-run`) + runtime-dir env override | [ ] PENDING | - | S |
| 13 | Doctrine reconciliation: rewrite Lift docs + CLAUDE.md + bootstrap + distill | [ ] PENDING | - | S |

Phase lines: A = {1,2,3} -> B = {4,5,6} -> C = {7,8,9} -> D = {10,11} (waits for the parallel arc) -> E = {12,13}. Within a phase, lower rows land first. Row 11 depends on Rows 4-6 (it is the 3rd single-series caller that ratifies the `run_pipeline` extraction). Row 12 (cleanup) depends on Row 3 (the path util). Rows 8-9 (Parquet rip) depend on Row 7.

---

## Section 1b - Plain-English PR table (what we are building and why)

| # | Feature (plain English) | Problem it fixes | How it lets us scale / constrain / stay flexible |
| --- | --- | --- | --- |
| 1 | One typed "hand-off slip" between each stage | Stages pass ad-hoc dicts/HTML; no contract | Every source speaks 3 messages; boundaries unit-testable |
| 2 | A committed year-checkpoint + "what we already fetched" ledger | We re-do full work every run; no memory; a revised old year could be missed | Year-keyed delta runs; a corrected old year re-opens; survives fresh clone & CI |
| 3 | Per-stage + orchestrator machine-readable logs, a run id, and a never-full-path util | Pipeline is silent; logs leak Windows drive letters today; no per-stage isolation | Tail one `fetch.log`; an agent can parse run state; paths stay POSIX/relative everywhere |
| 4 | A lightweight master orchestrator + a Discovery/Design Stage 0 + a source registry | Each source hand-rolls orchestration; nothing decides "what work is due"; adding a source rewrites plumbing | New source = one registry line + one adapter; the orchestrator never changes (Open-Closed) |
| 5 | Autonomous fetch with year-delta skip + resume + an operator fallback | Fetch was deleted; no automation, no "don't redo unchanged years", no resume after a crash | Runs on a trigger; skips unchanged years; resumes mid-run; flaky-TLS sources opt into staging |
| 6 | Fail-loud enrich gates + the OWID "splice into one honest series" rule | Silent coercions corrupt comparisons; unclear when to merge vs split publishers | One concept = one trend line across publishers WITH a visible break; comparisons honest by construction |
| 7 | Move the manifest writer out of the Parquet writer module | `writer.py` is double-loaded (Parquet + live manifest), can't delete cleanly | Unblocks deleting the Parquet path without breaking frontend startup |
| 8 | Switch the last 3 election adapters to CSV output | These 3 still emit Parquet via the old envelope | Finishes the one-format goal for elections |
| 9 | Delete the Parquet writer + typed-batch + dead dimension code | Forbidden Parquet machinery still ships | Exactly one publish path remains |
| 10 | Fix ICED provenance: producer = the real issuing authority | "NITI Aayog...Dashboard" mashes org+product; republished CEA data mis-attributed | Provenance scales as NITI/CEA/MoSPI products grow; series identity untouched |
| 11 | Prove it on a brand-new source (SDG India Index) + lock the shared runner | Need a 3rd real caller (Rule of Three) + a greenfield end-to-end proof | The shared `run_pipeline` is ratified on evidence; a genuinely new source validates the scaffold |
| 12 | A safe `cleanup` command for stale fetch caches + old logs | `.runtime` fills with stale http caches + logs; no retention policy | 90-day default, `--force` to go lower, `--dry-run` preview; only ever touches `.runtime/` |
| 13 | Rewrite the stale "how to add a source" docs | The doctrine docs reference deleted modules - they mislead | The next agent copies a template that compiles; doctrine matches code |

---

## Section 2 - Target architecture

```
CLI: python -m yen_gov run --source <id> [--stage discover|fetch|enrich|publish] [--resume]
     python -m yen_gov status        # what ran, how much succeeded, last checkpoint per source
     python -m yen_gov cleanup [--days N] [--force] [--dry-run]
   |
   v
orchestrate(source_id, *, repo_root, config)          # THIN driver; never branches on source_id
   |   registry: {source_id -> Adapter}                # Adapter = SourceSpec(s) + parser + optional fetch()
   |   mint run_id (YYYYMMDD-xxxxxxxx); open per-stage loggers; read committed checkpoint
   v
run_pipeline(spec, logger)                             # source-agnostic engine; pure filters
   |
   |-- STAGE 0  DISCOVER + DESIGN
   |     design (authoring-time, once): declare SourceSpec + check-overlap + pre-flight-ingest -> green
   |     discover (run-time, every run): validate spec + list local staged inputs + diff vs checkpoint
   |                                      -> work-list of periods due; logged to discover.log
   |
   |-- STAGE 1  FETCH  (per-spec fetch() OR fetch_mode="operator_staged")
   |     raw bytes -> datasets/<family>/_meadow/<source>/<vintage>/   (gitignored)
   |     update committed checkpoint: datasets/_ops/fetch-state/<source_id>.json
   |     emit fetch.started / fetch.completed / fetch.skipped (year delta hit) / fetch.failed
   |     message out: ClaimCheck{source_id, meadow_path, content_hash}
   |
   |-- STAGE 2  ENRICH (pure parse -> resolve entity_id, canonicalise unit, normalise period,
   |     assign indicator_id, derive source_id; SPLICE multi-publisher rows onto ONE indicator_id
   |     with a methodology break at the cut-over; FAIL LOUD on every gate)
   |     message out: CanonicalBatch{target_family, observation_rows[], source_rows[], replacement_semantics}
   |
   |-- STAGE 3  PUBLISH (validate batch vs columns.json; UPSERT via write_csv on PK
   |     (entity_id, year, period_label, indicator_id); upsert source.csv; advance checkpoint)
         published -> datasets/data/...csv   (the one canonical store the frontend reads)

observability: .runtime/logs/<run_id>/{orchestrator,discover,fetch,enrich,publish}.log  (JSON-lines)
durable state: datasets/_ops/fetch-state/<source_id>.json  (committed: last_completed_period + per-period content_hash)
freshness:     datasets/manifest.json   (machine inventory; human view = read-time render, NOT a docs file)
```

State homes (final):

| State class | Home | Committed? | Contract |
| --- | --- | --- | --- |
| Raw snapshot bytes | `datasets/<family>/_meadow/<source>/<vintage>/` | no (gitignored) | none (re-fetchable via checkpoint) |
| Delta-state + year-checkpoint | `datasets/_ops/fetch-state/<source_id>.json` | yes | `datasets/schemas/fetch-state.schema.json` x-version, Tier-B gate; carries `last_completed_period` + per-period `content_hash` |
| Per-run progress mirror + logs | `.runtime/logs/<run_id>/{orchestrator,discover,fetch,enrich,publish}.log` | no (ephemeral) | per-line JSON; cleaned by `cleanup` after 90d |
| Published observations | `datasets/data/**.csv` | yes | `datasets/data/_schema/columns.json` (frozen) |
| Provenance ledger | `datasets/data/entities/source.csv` | yes | 5-field sources schema (frozen, additive-only) |
| Published-artifact inventory / freshness | `datasets/manifest.json` | yes | `manifest.schema.json` x-version |

### 2b - Orchestrator inspiration (yen-go `puzzle_manager`), YAGNI-filtered

ADOPT (fits yen-gov): a thin multi-source orchestrator over an adapter registry; `run --source X [--stage S] [--resume]` + `status` CLI; `run_id` = `YYYYMMDD-xxxxxxxx`; a per-work-item correlation id `(source_id, period)` that threads a run end-to-end; the `.runtime/` subdir layout (`logs/`, plus `_meadow` staging) with an optional `YEN_GOV_RUNTIME_DIR` env override for CI/containers; `cleanup --dry-run --days N`; a dedicated `core/paths.py` (their `paths.py`) and the per-stage logger (their `pm_logging.py`).

REFUSE (YAGNI for yen-gov): their `rollback` + `audit.jsonl` (git revert + the idempotent writer is the undo); their `inventory` module (yen-gov has `manifest.json` + the `coverage` command); an `active_adapter` `sources.json` default (yen-gov passes `--source` explicitly); tenacity (a bounded httpx loop suffices). Keep typer (yen-gov's existing CLI lib) rather than copying their argparse choice.

---

## Section 3 - Per-row specs

### Row 1 - Stage-message contracts (3 typed pipes + SourceSpec Protocol)
- Scope: define the three pure typed messages + the `SourceSpec` Protocol an adapter satisfies. No behaviour, no I/O.
- Files: NEW `backend/yen_gov/canonical/stages.py` (`ClaimCheck`, `RawRecord`, `CanonicalBatch`, `SourceSpec` Protocol, `FetchMode` enum, `ReplacementSemantics` lifted from `envelope.py`); NEW `backend/tests/test_canonical_stages.py`.
- Gates: pytest + mypy green; `CanonicalBatch` carries the slim 5-field `source_rows` (no retired fields, no dim-row types).
- ONE oracle: a contract test asserts `CanonicalBatch.observation_rows` keys equal the non-facet column set of the `geo/*.csv` file class in `columns.json` (in-process message cannot drift from the persisted contract).

### Row 2 - Committed delta-state + year-checkpoint receipt schema + Tier-B gate
- Scope: define the committed checkpoint artifact + schema + Tier-B check. Carries `last_completed_period` (forward high-water mark) and `periods: {year: content_hash}` (value-equality skip key).
- Files: NEW `datasets/schemas/fetch-state.schema.json` (x-version 1.0); NEW `backend/yen_gov/canonical/fetch_state.py` (read/write/compare + composite-key + skip-predicate helpers); a `tier_b_fetch_state_receipt` check in `validate.py`; tests.
- Gates: schema passes schema-of-schemas; Tier-B rejects a malformed receipt; helpers pure + `tmp_path`-tested; no `datetime.now()` in row content.
- ONE oracle: write a receipt for years {2018..2022}; assert period 2019 is skipped when its input hash matches and FORCED to re-process when the 2019 input hash changes (Hans H-E revised-year guarantee).

### Row 3 - POSIX/relative path util + per-stage & orchestrator log files + `fetch.skipped` + run_id
- Scope: the observability + path-discipline seam. Add `core/paths.py::to_repo_relative_posix`; route `events.py` through it (fixes the drive-letter bug); add a `stage` param to `StructuredLogger` so each stage writes its own file; add the `fetch.skipped` event; add a `_mint_run_id()` helper.
- Files: NEW `backend/yen_gov/core/paths.py` + tests; EDIT `backend/yen_gov/core/logging.py` (stage param -> `<run_id>/<stage>.log`); EDIT `backend/yen_gov/core/events.py` (`FetchSkipped` + `to_extra()` routes through the path util + append `"fetch.skipped"` to `ALL_EVENT_NAMES`); EDIT `backend/yen_gov/cli.py` (`_mint_run_id`); update the event-name pin test.
- Gates: pytest green; the event-name pin updated in the same commit; no rename of any existing event; a logged `Path` emits as a repo-relative POSIX string with no drive letter.
- ONE oracle: a test logs a Windows-style absolute `Path` and asserts the emitted JSON field is repo-relative + POSIX with no `C:` (the section-2 violation is structurally fixed).

### Row 4 - Master orchestrator + adapter registry + Stage 0 (Discover+Design) + `run_pipeline` engine
- Scope: the scaffold. Extract `run_pipeline(spec, logger)` (Stage0->Fetch->Enrich->Publish as pure filters) from the `rbi_handbook` ingest (1st caller, parity); add the thin `orchestrate(source_id, *, repo_root, config)` + the `{source_id: Adapter}` registry; implement Stage 0 (run-time discovery: validate spec + list local inputs + diff vs checkpoint -> work-list); lift the shared catalogue/source upsert into `emit_helpers.py`; add `run` + `status` CLI.
- Files: NEW `backend/yen_gov/canonical/pipeline.py` (`run_pipeline`), `backend/yen_gov/canonical/orchestrator.py` (`orchestrate` + registry), `backend/yen_gov/canonical/emit_helpers.py`; EDIT `rbi_handbook/ingest.py` to route through `run_pipeline`; EDIT `cli.py` (`run`, `status`); a `docs/architecture/backend/` template note; tests.
- Gates: pytest green; `rbi_handbook` output byte-identical before/after (parity, Tidy First); `status` reports the `rbi_handbook` checkpoint; the orchestrator contains zero `if source_id ==` branches.
- ONE oracle: a parity test asserts `rbi_handbook` CSV output is byte-identical pre- and post-extraction (structure changed, behaviour did not).

### Row 5 - Autonomous Fetch hook + delta-skip + year-checkpoint resume (2nd cold caller proof)
- Scope: add the per-spec `fetch()` hook (httpx, bounded 3-try) + the year-delta skip using the Row 2 checkpoint + the `operator_staged` fallback; add a 2nd cold single-series caller (a new RBI HBS cohort) as the proof vehicle; wire `--resume`.
- Files: NEW `backend/yen_gov/canonical/fetch.py` (`run_fetch(spec, logger) -> ClaimCheck`); NEW `backend/yen_gov/canonical/adapters/rbi_hbs_<cohort>/` (copied template); EDIT specs to declare `fetch_url`/`fetch_mode`/`spec_version`; promote httpx out of the `admin` extra if needed; tests with a mocked `fetch` (loader-unit carve-out).
- Gates: pytest green; a 2nd run with unchanged years emits `fetch.skipped` + writes zero new CSV bytes; a `spec_version` bump forces re-emit; `cea`-class sources resolve to `operator_staged` and never call the network; NO tenacity / `core/http.py`.
- ONE oracle: run the cohort twice against a fixture upstream - run 2 (identical years) emits `fetch.skipped` and leaves CSV mtime untouched; mutating one year's fixture forces exactly that year to re-emit.

### Row 6 - Enrich hard-gates + OWID splice rules + auto pre-flight
- Scope: implement the six fail-loud enrich gates + the OWID splice rules (one-series splice; issuing-authority precedence; clean cut-over; break-on-join; disclosed overlap divergence) as shared helpers; auto-run `check-overlap` + `pre-flight-ingest` per source before emit.
- Files: NEW `backend/yen_gov/canonical/enrich_gates.py` + `splice.py` (reusing the `pipeline/compose.py` seam); EDIT `run_pipeline` to call them; tests for each gate's failure path + a 2-source splice fixture.
- Gates: pytest green; each gate has a RAISE test (an unmapped state aborts the row, not an implicit zero); a 2-source fixture splices onto ONE `indicator_id` with a `methodology_breaks` row at the cut-over and each row keeps its own `source_id`; pre-flight exit-2 aborts with no override.
- ONE oracle: a 2-source splice test asserts one `indicator_id`, N rows from publisher A (years <= cut) + M rows from publisher B (years > cut), each row's `source_id` intact, and exactly one `methodology_breaks` row at the boundary (Hans H-A + H-C realized).

### Row 7 - Extract manifest writer out of `writer.py`; verify ECI Parquet callers
- Scope: move `_regenerate_manifest` into a parquet-free `canonical/manifest.py`; repoint its callers; verify whether the 3 ECI `write_batch` callers emit or already hit the `elections`-envelope raise.
- Files: NEW `backend/yen_gov/canonical/manifest.py`; EDIT `cli.py` + `pipeline/dim_acs_lgd_lift.py` callers; a verification note in the PR body.
- Gates: pytest green; `manifest.json` regenerates byte-identical; no `_regenerate_manifest` import from `writer.py` remains.
- ONE oracle: byte-identity of `manifest.json` before/after the extraction.

### Row 8 - Flip 3 ECI adapters to `write_csv`
- Scope: convert `eci_ls`, `eci_ae_panel`, `pipeline/canonical_eci_backfill` from `write_batch` to `write_csv`, preserving every election row. Skip any caller Row 7 proved dead.
- Files: EDIT the three adapters + their CLI commands + tests; additive `source.csv` upsert.
- Gates: pytest green; per-event row counts preserved (a drop is an ESCALATE); CSV passes Tier-B; `source.csv` edits append-only.
- ONE oracle: per-event before/after parity of `(entity_id, year, indicator_id)` tuples (no election row lost in the format flip).

### Row 9 - Delete `envelope.py` + `writer.py` + dead dim-rows + residual Parquet
- Scope: the rip. Delete the Parquet writer, the typed batch, the dead dim-row dataclasses, the likely-dead `dim_acs_lgd_lift.py`; clean residual `read_parquet` / `FORMAT PARQUET` / stale docstrings.
- Files: DELETE `canonical/writer.py` + `canonical/envelope.py` + (if dead) `pipeline/dim_acs_lgd_lift.py`; EDIT `canonical/__init__.py`, `eci_ae_panel.py`, `ingest_pincode.py`, `cli.py`; delete orphan tests.
- Gates: pytest green; `grep -r "write_batch|BatchEnvelope|to_parquet|read_parquet|FORMAT PARQUET" backend/` returns ZERO live hits; full Tier-B passes on a regenerated corpus.
- ONE oracle: a repo-wide grep gate proving zero Parquet writer/reader/envelope symbols remain in `backend/`.

### Row 10 - ICED -> issuing-authority producer correction (orthogonal to series) - AFTER hot arc
- Scope: correct the producer taxonomy per SC-2 + Hans/Max. Build the `(producer, title, vintage)` triple-registry, regenerate the 31 ICED `source.csv` rows (producer = issuing authority; ICED -> title), rewrite observation `source_id` FKs, add the fail-loud FK gate. Series identity (`indicator_id`) is NOT touched (Hans H-B). RUN ONLY after the parallel energy/`iced_*` arc merges.
- Files: NEW `backend/yen_gov/canonical/iced_authority_map.py` + `docs/research/iced-authority-tracing.md`; EDIT iced citation calls; regenerate `source.csv` + affected datapoints; EDIT `validate.py` (FK gate + producer-is-not-a-product assertion).
- Gates: pytest green; zero dangling `source_id`; no `producer` contains a product name; no `indicator_id` changed by this row (series untouched); corpus regenerates deterministically.
- ONE oracle: a Tier-B check asserts every `producer` is in the closed authority set AND every observation `source_id` exists in `source.csv` AND the set of `indicator_id`s is identical before/after (provenance fixed, series identity untouched).

### Row 11 - Greenfield NITI SDG India Index (3rd caller) -> ratify shared `run_pipeline`
- Scope: ingest a new NITI-originated source end-to-end (producer = "NITI Aayog", title = "SDG India Index <year>"); 3rd single-series caller. With Rule of Three met, RATIFY `run_pipeline` (no further refactor) and confirm the three single-series callers share it. Faceted CEA/energy stays separate (documented).
- Files: NEW `backend/yen_gov/canonical/adapters/niti_sdg_index/`; NEW CLI `run --source niti-sdg-index`; a committed green `proposal.json` + `pre-flight-ingest` report; tests + a coverage note.
- Gates: pytest green; pre-flight verdict in {mint_new, upsert, add_facet}; the three single-series callers produce byte-identical CSV vs pre-ratification; faceted path explicitly NOT folded in.
- ONE oracle: byte-identical parity of all three single-series callers' CSV output before/after ratification (the abstraction is correct and stable).

### Row 12 - Cleanup command + runtime-dir env override
- Scope: `python -m yen_gov cleanup [--days N] [--force] [--dry-run]`; default 90-day retention; `N < 90` requires `--force`; `--dry-run` previews. Targets = declared `CLEAN_TARGETS` (stale `.runtime/raw/` http caches + `.runtime/logs/` older than N). Add the optional `YEN_GOV_RUNTIME_DIR` env override.
- Files: NEW `backend/yen_gov/canonical/cleanup.py` (CLEAN_TARGETS + age logic, routed through `core/paths.py`); EDIT `cli.py` (`cleanup`); EDIT the runtime-dir resolver to honour the env override; tests.
- Gates: pytest green; `--dry-run` mutates nothing; every clean target asserts-resolves under `.runtime/`; a test proves the cleaner REFUSES a target outside `.runtime/` (never touches `datasets/_ops/`, `datasets/**`, `config/`, `docs/`); `N < 90` without `--force` aborts.
- ONE oracle: a test seeds `.runtime/logs/<old>` (mtime > 90d) + `datasets/_ops/fetch-state/x.json`, runs `cleanup`, and asserts the old log dir is gone while the committed checkpoint is untouched.

### Row 13 - Doctrine reconciliation: rewrite Lift docs + CLAUDE.md + bootstrap + distill
- Scope: make the docs match reality. Rewrite the stale Lift doctrine + cookbook to the orchestrator / `run_pipeline` / `write_csv` world; record SC-1 in `CLAUDE.md` (replace the "no network fetcher" absolute with the local-pipeline-fetch rule) + the decision index; refresh the bootstrap banner; distill this plan.
- Files: EDIT `docs/concepts/ingest-fetch-enrich-separation.md` + `docs/how-to/add-a-new-data-source.md`; EDIT `CLAUDE.md` + `docs/agents/bootstrap.md` + `docs/agents/guardrails.md` + `docs/reference/decision-index.md`; archive-distill this plan-doc.
- Gates: a docs-link/grep check passes (no references to deleted symbols); CLAUDE.md and the docs agree; the plan carries a per-row distillation map.
- ONE oracle: a grep gate asserts zero occurrences of `core.http`, `core.io.Source`, `write_artifact`, or `write_batch` across `docs/`.

---

## Section 4 - YAGNI refusals (explicitly NOT built)

- A DAG / workflow engine (Airflow / Dagster / dvc / Luigi). The orchestrator iterating the adapter registry IS the runner.
- A materialized "garden"/enrich tier on disk. Enrich stays in-memory; the canonical CSV is the reviewable output.
- A runtime endpoint/period discovery crawler. The fetcher is local-first; Stage 0 discovery is local-disk + checkpoint, not a live API crawl.
- A general N-source splice engine before the first real 2-source indicator exists (build it from the `compose.py` seam when earned).
- A second checkpoint file. The committed `_ops/` receipt is extended in place; the `.runtime` mirror is never the resume authority.
- `pydantic-settings` / a global `Settings` object / `config/sources.json` / an `active_adapter` default config. Typed dataclass specs + CLI flags + machine-path env vars cover overrides; sources are selected by `--source`.
- A plugin / entry-point / dynamic-import adapter registry. A hand-written dict is enough.
- A `rollback` + `audit.jsonl` subsystem and an `inventory` module (the `puzzle_manager` has these; yen-gov's undo is git + the idempotent writer, and inventory/freshness already live in `manifest.json` + the `coverage` command).
- A committed per-run receipt; a second human-prose log sink; a `source_id` alias table; re-adding `tenacity` / `core/http.py`.
- A generated published-state report under `docs/` (freshness is `manifest.json`; the human view is a read-time render).
- Folding the faceted (CEA / energy) row shape into the single-series `run_pipeline` during this plan.

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3. Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt. Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

> Plan-specific execution notes (binding): (a) Phases run A -> B -> C -> D -> E; Phase D (Rows 10-11) does NOT start until the parallel energy/`iced_*` faceted-reingest arc has merged to main - rebase first and re-verify the hot-file list. (b) `datasets/data/entities/source.csv` and `datasets/data/_schema/columns.json` are FROZEN / additive-only. (c) Rows 8-10 touch election + provenance data: a row-count drop or a dangling FK is an ESCALATE, not an auto-fix. (d) Work each row in a dedicated worktree off fresh `origin/main`; never share a worktree with a parallel agent. (e) The cleaner (Row 12) and any path-emit MUST route through `core/paths.py`; the cleaner MUST refuse any target outside `.runtime/`.

## See also

- [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) - the Lift doctrine this plan modernizes (Row 13 rewrites it).
- [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) - the gold target template (the 1st `run_pipeline` caller).
- [docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md) - the existing RBI NSDP cross-base-year splice precedent.
- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) - the CSV migration whose Parquet rip this plan finishes.
- `miztiik/yen-go` `backend/puzzle_manager` - the thin config-driven multi-source orchestrator this plan's runner is modelled on.
- [CLAUDE.md](../CLAUDE.md) - the engineering contract (authority table section 0a, correction levels section 6, anti-patterns section 10).

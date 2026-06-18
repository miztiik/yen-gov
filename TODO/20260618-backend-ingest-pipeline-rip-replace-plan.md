# Backend ingest pipeline - rip-and-replace to an autonomous Fetch -> Enrich -> Publish ETL

**Last Updated**: 2026-06-18
**Level**: 5 (core design + data model + runtime). The whole plan PAUSES for user ratification before any row executes. This document is AUTHORED, not yet implemented.
**Strategy**: RIP AND REPLACE (target-state direct). No strangler-fig, no backwards-compat shims, no parallel old+new paths. The app MAY break temporarily until the migration finishes.

> Authored via the `prepare-plan` skill after a four-persona consult (Fowler, Gregor, Hans, Max). Every contested call below carries a baked-in written ruling so execution is blind rule-following. The `Execution contract` block near the bottom is the whole instruction set for "implement it".

---

## Section 0 - Operating contract

### 0.1 Why this plan exists

The user wants each upstream source (RBI, ICED, NITI, ...) to run **autonomously through staged Fetch -> Enrich -> Publish** when triggered, on a **shared pipeline scaffold every source uses as-is** (DRY / KISS / SOLID / YAGNI), with **centralized config + sane defaults + per-invocation overrides**, **full observability** (structured logging, run state, structured payloads between stages), and **state-managed batched + delta fetches** so unchanged upstream is never re-processed.

The verified reality (research, 2026-06-18):

- The vision is **already documented** as the 4-layer "Lift pipeline" (Fetch -> Parse -> Enrich -> Emit) in [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) + [docs/how-to/add-a-new-data-source.md](../docs/how-to/add-a-new-data-source.md), but both docs are **stale**: they import deleted modules (`core.http.Fetcher`, `core.io.Source/write_artifact`, `write_batch`, the Parquet writer, the retiring `_meadow/` tier).
- The **gold target template already exists** in code: [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) - a config-driven typed-spec registry + generic parser + state resolver + direct `write_csv` emit + in-place catalogue/source upsert.
- The observability scaffolding ([core/logging.py](../backend/yen_gov/core/logging.py) `StructuredLogger`, [core/events.py](../backend/yen_gov/core/events.py) 11 typed stage events) **exists and is tested but is wired into nothing**.
- The Parquet writer ([canonical/writer.py](../backend/yen_gov/canonical/writer.py) `write_batch`) + the typed batch ([canonical/envelope.py](../backend/yen_gov/canonical/envelope.py)) are a **Holy-Law-#1 residue still live on 3 ECI adapters** (`eci_ls`, `eci_ae_panel`, `pipeline/canonical_eci_backfill`); finishing the CSV migration means flipping those then deleting the Parquet path.
- **Config infra is nil** (RBI uses typed dataclasses, boundaries uses JSON, the CLI has no central config).
- **Delta-fetch state has zero implementation** (the `.runtime/<adapter>/<source_id>.json` sidecar is docstring-only).
- ICED is **31 source.csv rows conflated under one producer string** `"NITI Aayog India Climate & Energy Dashboard"` - org + product mashed into the producer field, which is the provenance bug the "split ICED and NITI" request names.

This plan modernizes the documented Lift doctrine to the post-CSV reality, builds the autonomous staged runner, finishes the Parquet rip, fixes the ICED/NITI provenance, and wires the dormant observability - target-state-direct.

### 0.2 Hard-coded scope

IN scope:
- The shared staged pipeline scaffold (contracts, runner, config, observability, delta-state).
- Autonomous network Fetch reintroduction with batched + delta semantics (see Scope-change SC-1).
- Finishing the Parquet/envelope rip (ECI flip + delete).
- ICED/NITI producer-taxonomy correction (provenance).
- One greenfield proof acquisition (NITI SDG India Index) that exercises the full pipeline end-to-end.
- Reconciling the stale doctrine docs + CLAUDE.md + bootstrap to the target state.

OUT of scope (do NOT do in this plan):
- Frontend / admin / charting changes (read-side is untouched; canonical CSV shape is frozen).
- Restructuring the energy + `iced_*` adapter families WHILE the parallel agent's faceted-reingest arc (PRs around #1106-#1111) is in flight. Phase D waits for that arc to merge.
- Changing the `source.csv` 5-field schema or `datasets/data/_schema/columns.json` (both frozen; additive-only if unavoidable).
- Any new socio-economic indicator family beyond the one cold RBI HBS cohort (Row 4) and the greenfield SDG India Index proof (Row 11).

### 0.3 Strategy ruling (rip-and-replace, user-explicit)

The user explicitly overrode Fowler's default strangler-fig instinct: "bake the plan to be rip and replace ... we can break the app temporarily until we finish the migration ... plan for the target state directly." Consequence baked into sequencing: rip rows delete old paths outright (no compat shim, no dual read/write), and a temporarily-broken ECI ingest between Row 7 and Row 9 is acceptable. The canonical CSV the frontend reads is regenerated at the end of each phase, so the deployed static bundle is only ever rebuilt from a coherent corpus.

### 0.4 Scope-change ledger

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
| --- | --- | --- | --- |
| SC-1 | 2026-06-18 | Reintroduce automated network fetch INSIDE the local ingest pipeline: each source runs autonomously Fetch -> Enrich -> Publish when triggered, with batched + delta fetch driven by committed snapshot-hash state so unchanged upstream is never re-fetched or re-emitted. This OVERRIDES the 2026-06-03 platform-reset plan section 21.4 ("network-fetch code is deleted; ingest reads local source CSV") and the CLAUDE.md anti-pattern "NO agent may reintroduce ... a network fetcher". Holy Laws #1 + #2 are PRESERVED and re-affirmed: fetch runs ONLY in the local pipeline; production stays a static bundle; CI consumes committed canonical CSV and never fetches. Flagged by Max as a doctrine reversal requiring sign-off; it is a Fowler/Gregor mechanics call, not an AI/LLM call. | user, 2026-06-18 ("if this means change in doctrines, then so be it") |
| SC-2 | 2026-06-18 | ICED ceases to be a `producer`. The producer field becomes the issuing authority (CEA / MoSPI / MoEFCC for republished facts; "NITI Aayog" for NITI-originated products); "India Climate & Energy Dashboard: <endpoint>" moves into `title`. This re-mints all 31 ICED `source_id` values and rewrites their observation FKs. Acceptable because rip-and-replace regenerates the corpus in one pass; no alias/redirect table (rejected by Hans + Max as a second provenance surface). | user-delegated to Hans+Max per CLAUDE.md section 0a; ruling recorded in Section 0.6 |

### 0.5 ESCALATE triggers (stop and ask; otherwise AUTO)

- The plan as a whole is Level-5: it does not begin executing until the user says "implement it".
- During execution, STOP and surface only at: (a) any `datasets/schemas/*.schema.json` MAJOR bump (1.x -> 2.0); (b) any operation that would DELETE election-results rows rather than re-format them (Row 8 flips emit format; it must preserve every election row - a row-count drop is an ESCALATE); (c) Row 10 would have to edit a `source.csv` row the parallel agent is concurrently mutating (coordinate, do not collide); (d) an unresolved persona conflict; (e) 3x cost/effort overrun on any row.
- SC-1 and SC-2 are PRE-SIGNED; they are not re-litigated at execution time.

### 0.6 Authority rulings baked in (zero decision points for the executor)

| Theme | Ruling | Authority |
| --- | --- | --- |
| Inter-stage contract | THREE typed pipe messages (Pipes-and-Filters), not one god-message: Fetch->Parse = Claim-Check token `{source_id, meadow_path, content_hash}`; Parse->Enrich = `list[RawRecord]` (publisher-shaped, pure, in-memory); Enrich->Emit = `CanonicalBatch{target_family, observation_rows[], source_rows[5-field], replacement_semantics}` (the envelope's one good idea, reborn slim). Stages are pure filters; the orchestrator holds all run/delta state. Events are a Tee to the logger, never part of the dataflow. | Gregor |
| CanonicalBatch persistence | NOT JSON-Schema'd - it never persists. Validate it against `datasets/data/_schema/columns.json` at the write seam (keep the exactly-one-of value + FK checks `write_batch` had). Lives under `canonical/`, not `core/`. | Gregor |
| Shared runner abstraction | The scaffold ALREADY EXISTS = the `rbi_handbook` 4-module shape. Codify it as the copy-per-source TEMPLATE now (Row 4). Extract a single shared `run_pipeline` entrypoint ONLY after the 3rd single-series caller exists (Rule of Three -> Row 11). Use a `SourceSpec` Protocol + Extract-Function/Parameterize, NEVER a base class, NEVER a plugin/entry-point registry. Do not unify the faceted (CEA / energy) row shape into the single-series runner in this plan. | Fowler |
| Config model | One typed frozen-dataclass spec registry per source (the `HbsTableSpec` pattern). NOT JSON, NOT pydantic-settings, NO global config object, NO `config/sources.json`. Override layering: spec (compile-time) < CLI flag (per-invocation: `--table`, `--dry-run`, `--staging-dir`) < env var (machine paths only). | Fowler |
| Fetch reintroduction | Per-spec optional `fetch()` hook writes raw bytes to the gitignored `_meadow/` snapshot dir + a delta-state sidecar COMMITTED to `datasets/_ops/`. The committed split is the crux: delta-state in `.runtime/` would make every fresh clone re-fetch everything. httpx (already a dep), a bounded 3-try loop, NO tenacity, NO re-added `core/http.py`. Per-spec `fetch_mode="operator_staged"` fallback for flaky-TLS sources (`cea.nic.in`). | Fowler + Gregor |
| Delta cache key | Composite `sha256(input_content_hash || spec_version || catalogue_version)`, NOT the input hash alone. `spec_version` (a one-line field on each spec) forces re-emit when the parser/spec changes even though upstream bytes are identical. Hash the RAW upstream payload, not the extracted projection. The writer is deterministic, so a false-run only wastes time and a version-in-key removes the only false-skip path: worst case is bounded staleness, never wrong data. | Gregor + Hans |
| State placement | (a) fetch/delta-state -> committed `datasets/_ops/` WITH `$schema` + `x-version` (Tier-B-enforced contract surface); (b) per-run observability receipt -> `.runtime/logs/` EPHEMERAL, never committed (no reader today); (c) published-artifact freshness -> `datasets/manifest.json` ONLY. Principle: commit state that the next run READS; keep ephemeral the state nothing reads. | Gregor + Fowler |
| "Published states in /docs" | REJECTED (the one place the personas pushed back on the user's suggestion). A committed docs report is a drifting PROJECTION of `manifest.json` - it violates Holy Law #4 ("one concept defined once") and "docs-only PRs are a smell". The user's need is a human VIEW, not a state store: render it at read-time via the admin app or a `python -m yen_gov report` command. User may override; this is the persona recommendation. | Gregor |
| Observability events | Wire the existing 11 events at stage boundaries via a DI logger (`logger: StructuredLogger | None = None`, no-op default). Add EXACTLY ONE event: `fetch.skipped` (delta hit). Do NOT rename anything (`ALL_EVENT_NAMES` is a pinned surface). NO `enrich.*` events (enrich is in-memory; `artifact.written` already reports the outcome). | Fowler |
| OWID craft to adopt | TWO only: (1) snapshot content-checksum as identity (it IS the delta key); (2) NAME the snapshot -> meadow -> canonical stages with enrich IN-MEMORY. REFUSE a DAG/`make` runner (the CLI iterating the spec registry IS the runner) and a materialized "garden"/enrich tier (no second reader). | Fowler + Max |
| ICED/NITI producer | `producer` = the ORGANISATION / issuing authority, NEVER the product. ICED rows that republish CEA/MoSPI/MoEFCC -> producer = the issuing authority, title = "... (via NITI ICED <api>)", and the fact UPSERTs/facets into the existing authority concept (never a parallel ICED series). NITI-originated products (SDG India Index, State-wise Deep Dive synthesis) -> producer = "NITI Aayog", title = the product. One triple-registry consumed by BOTH the source-row writer and the observation writer; a fail-loud FK gate makes a dangling/redefined citation structurally impossible. | Hans + Max |
| Enrich hard-gates | The Enrich stage FAILS LOUD (never silently coerces) on: entity-resolution (no fuzzy guess, no implicit zero for a missing entity), unit canonicalisation (especially nominal-vs-constant-price INR), period normalisation (fiscal-year != calendar-year), concept-overlap reuse (>= 0.70 -> UPSERT/facet, never mint), methodology-break presence (a level-discontinuity with no `methodology_breaks` row HALTS), and no-silent-definition-drift (a changed definition under the same name is a break or a new indicator, never a blind UPSERT). | Hans |
| Delta-fetch honesty | A content-hash attests BYTES, not the methodology behind them. Every skip is logged with `source_id` + vintage + last-verified and drives a cadence-based staleness surface off `update_period_days`; the `methodology_breaks` ledger is hand-curatable independent of byte deltas; a known break renders as citizen-facing chrome REGARDLESS of whether the fetch was skipped (a skip lives entirely in the operator plane and is structurally incapable of suppressing the break banner). | Hans |
| Sequencing vs the parallel agent | Phase A schemas/contracts are greenfield (freeze-and-own, zero collision). Prove the pipeline on a COLD family first (extend `rbi_handbook`). Do the greenfield NITI SDG India Index next. Touch the HOT energy + `iced_*` families and `source.csv` producer reattribution LAST, only after the parallel faceted-reingest arc merges. `source.csv` + `columns.json` are FROZEN / additive-only for this plan. | Max + Gregor |

---

## Section 1 - Status Reckoner (rows are PRs)

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| 1 | Stage-message contracts (3 typed pipes + SourceSpec Protocol) | [ ] PENDING | - | S |
| 2 | Committed delta-state receipt schema + Tier-B gate | [ ] PENDING | - | S |
| 3 | Observability seam: `fetch.skipped` event + run_id + logger DI | [ ] PENDING | - | S |
| 4 | Codify `rbi_handbook` template + shared Emit/catalogue-upsert helper + 2nd cold caller | [ ] PENDING | - | M |
| 5 | Autonomous Fetch hook + delta-skip (httpx + operator-staged fallback) | [ ] PENDING | - | M |
| 6 | Enrich hard-gates (fail-loud helpers + auto pre-flight) | [ ] PENDING | - | M |
| 7 | Extract manifest writer out of `writer.py`; verify ECI Parquet callers | [ ] PENDING | - | S |
| 8 | Flip 3 ECI adapters (`eci_ls`, `eci_ae_panel`, backfill) to `write_csv` | [ ] PENDING | - | M |
| 9 | Delete `envelope.py` + `writer.py` + dead dim-rows + residual Parquet | [ ] PENDING | - | M |
| 10 | ICED/NITI producer split (regenerate `source.csv` + FKs) - AFTER hot arc | [ ] PENDING | - | M |
| 11 | Greenfield NITI SDG India Index (3rd caller) -> extract shared `run_pipeline` | [ ] PENDING | - | L |
| 12 | Doctrine reconciliation: rewrite Lift docs + CLAUDE.md + bootstrap + distill | [ ] PENDING | - | S |

Phase lines (hard dependencies): A = {1,2,3} -> B = {4,5,6} -> C = {7,8,9} -> D = {10,11} (D waits for the parallel energy/`iced_*` arc to merge) -> E = {12}. Within a phase, lower row numbers land first. Row 11 depends on Row 4 + Row 5 + Row 6 (it is the 3rd single-series caller that unlocks the Rule-of-Three extraction).

---

## Section 1b - Plain-English PR table (what we are building and why)

| # | Feature (plain English) | Problem it fixes | How it lets us scale / constrain / stay flexible |
| --- | --- | --- | --- |
| 1 | One typed "hand-off slip" between each pipeline stage | Today stages pass raw dicts / HTML / ad-hoc shapes; there is no contract, so a change in one stage silently breaks the next | Every source speaks the same three messages, so a new source plugs in without inventing its own glue; the boundaries are unit-testable in isolation |
| 2 | A committed "what we already fetched" ledger (snapshot hashes) | We re-do the full parse+publish on every run even when upstream has not changed; there is no memory of prior work | Batched + delta runs: unchanged sources are skipped; the ledger survives a fresh clone, so CI and a new machine do not re-fetch the world |
| 3 | Structured logs + per-run id + a "skipped because unchanged" event | The pipeline is silent - no run history, no way to see what each stage did or why a source was skipped | Operators (and a future admin dashboard) can tail one JSON log per run; the dormant logging code finally has a consumer |
| 4 | A documented copy-me template + shared publish/catalogue helper | Each source hand-rolls its own orchestration; adding a source means rewriting plumbing (DRY violation) | Adding a source = copy a typed spec + write one parser; everything else (resolve, cite, publish, log) is shared - code surface shrinks per source |
| 5 | Autonomous fetch with smart skipping + an operator fallback | Fetch was deleted; sources are hand-staged with no automation and no "don't redo unchanged work" | The pipeline runs end-to-end on a trigger; flaky-TLS sources opt into operator-staging via one flag instead of breaking the run |
| 6 | Fail-loud enrichment gates (entity / unit / period / break) | Silent coercions (Orissa vs Odisha, fiscal vs calendar year, nominal vs constant rupees, a quiet definition change) corrupt cross-state / cross-year comparisons | A citizen comparison is honest by construction; a new vintage that rebases cannot smear over a methodology break |
| 7 | Move the manifest writer out of the Parquet writer module | `writer.py` is double-loaded (Parquet emit + live manifest regen), so it cannot be deleted cleanly | Unblocks deleting the Parquet path without breaking the manifest the frontend reads at startup |
| 8 | Switch the last 3 election adapters to CSV output | These 3 ECI adapters still emit Parquet via the old envelope - the last violators of the CSV-only store | Finishes the one-format goal; election ingest joins every other source on the same `write_csv` seam |
| 9 | Delete the Parquet writer + typed-batch + dead dimension code | Dead/forbidden Parquet machinery still ships in the backend | Zero Parquet writers/readers remain; the codebase has exactly one publish path |
| 10 | Fix ICED provenance: producer = the real issuing authority | "NITI Aayog India Climate & Energy Dashboard" mashes org + product into the producer; republished CEA data is mis-attributed | Provenance scales cleanly as we add more NITI/CEA/MoSPI products; citizens see who actually issued each number |
| 11 | Prove it end-to-end on a brand-new source (SDG India Index) + lock the shared runner | We need a third real caller before extracting the single shared pipeline entrypoint (Rule of Three), and a greenfield proof that the autonomous path works | The shared `run_pipeline` is extracted on evidence, not guesswork; a genuinely new source validates the whole scaffold |
| 12 | Rewrite the stale "how to add a source" docs to match reality | The doctrine docs reference deleted modules - they actively mislead the next agent | The next contributor copies a template that compiles; the doctrine matches the code (Holy Law #4) |

---

## Section 2 - Target architecture (the state the rows converge to)

```
trigger (CLI: python -m yen_gov ingest <source> [--table T] [--dry-run] [--staging-dir D])
   |
   v
run_pipeline(spec: SourceSpec, logger)            <- extracted in Row 11 (Rule of Three)
   |
   |-- FETCH  (per-spec fetch() OR fetch_mode="operator_staged")
   |     raw bytes -> datasets/<family>/_meadow/<source>/<vintage>/  (gitignored)
   |     delta-state -> datasets/_ops/fetch-state/<source_id>.json   (committed, schema'd)
   |     emit: fetch.started / fetch.completed / fetch.skipped (delta hit) / fetch.failed
   |     message out: ClaimCheck{source_id, meadow_path, content_hash}
   |
   |-- PARSE  (pure functions; no I/O, no network, no resolution)
   |     emit: parse.started / parse.completed
   |     message out: list[RawRecord]   (publisher-shaped dicts)
   |
   |-- ENRICH (resolve entity_id, canonicalise unit, normalise period, assign indicator_id,
   |           derive source_id) - FAIL LOUD on every gate; auto-run check-overlap + pre-flight
   |     message out: CanonicalBatch{target_family, observation_rows[], source_rows[], replacement_semantics}
   |
   |-- EMIT   (validate batch vs columns.json; UPSERT via write_csv on PK
   |           (entity_id, year, period_label, indicator_id); upsert source.csv rows)
         emit: artifact.written / artifact.rejected
         published -> datasets/data/...csv   (the one canonical store the frontend reads)

observability: StructuredLogger -> .runtime/logs/<run_id>/yen-gov.log  (ephemeral, Tee from each stage)
freshness:     datasets/manifest.json (machine inventory) ; human view = read-time render, NOT a committed docs file
```

State homes (final):

| State class | Home | Committed? | Contract |
| --- | --- | --- | --- |
| Raw snapshot bytes | `datasets/<family>/_meadow/<source>/<vintage>/` | no (gitignored) | none (re-fetchable via delta-state) |
| Fetch/delta-state (composite hash, last-fetch, etag) | `datasets/_ops/fetch-state/<source_id>.json` | yes | `datasets/schemas/fetch-state.schema.json` x-version, Tier-B gate |
| Published observations | `datasets/data/**.csv` | yes | `datasets/data/_schema/columns.json` (frozen) |
| Provenance ledger | `datasets/data/entities/source.csv` | yes | 5-field sources schema (frozen, additive-only) |
| Published-artifact inventory / freshness | `datasets/manifest.json` | yes | `manifest.schema.json` x-version |
| Per-run observability log | `.runtime/logs/<run_id>/yen-gov.log` | no (ephemeral) | per-line JSON (logging.py) |

---

## Section 3 - Per-row specs

### Row 1 - Stage-message contracts (3 typed pipes + SourceSpec Protocol)

- Scope: define the three pure typed messages and the `SourceSpec` Protocol that a source registry satisfies. No behaviour, no I/O. This is the freeze-and-own contract surface every later row threads.
- Files: NEW `backend/yen_gov/canonical/stages.py` (`ClaimCheck`, `RawRecord`, `CanonicalBatch`, `SourceSpec` Protocol, `FetchMode` enum, `ReplacementSemantics` lifted from `envelope.py`); NEW `backend/tests/test_canonical_stages.py`.
- Gates: pytest green; mypy clean; `CanonicalBatch` carries the slim 5-field `source_rows` (no retired fields, no dim-row types); a contract test asserts `CanonicalBatch` validates against `columns.json` column names for `datasets/data/datapoints/geo/*.csv`.
- ONE oracle: a contract test builds a `CanonicalBatch` and asserts its `observation_rows` keys are exactly the non-facet column set of the `geo/*.csv` file class (bijection with `columns.json`), proving the in-process message and the persisted contract cannot drift.

### Row 2 - Committed delta-state receipt schema + Tier-B gate

- Scope: define the committed fetch/delta-state artifact + its JSON Schema + a Tier-B validator check. This is the memory that makes batched + delta fetch possible.
- Files: NEW `datasets/schemas/fetch-state.schema.json` (x-version 1.0: `source_id`, `composite_key`, `input_content_hash`, `spec_version`, `catalogue_version`, `last_fetch_label`, optional `etag`); NEW `backend/yen_gov/canonical/fetch_state.py` (read/write/compare helpers, composite-key builder); a new `tier_b_fetch_state_receipt` check in `backend/yen_gov/validate.py`; tests.
- Gates: schema passes the schema-of-schemas; Tier-B check rejects a malformed receipt; `derive` helpers are pure + tested with `tmp_path`; no `datetime.now()` in row content (CLAUDE.md) - `last_fetch_label` is an operator label, not a wall-clock provenance stamp.
- ONE oracle: a round-trip test - write a receipt, mutate `spec_version`, and assert the composite key changes (so a parser bump forces re-emit) while mutating nothing keeps it byte-identical (so an unchanged re-run is a no-op).

### Row 3 - Observability seam: `fetch.skipped` event + run_id + logger DI

- Scope: extend the dormant event surface by exactly one event, add a run-id minter, and define the DI logger seam the runner will use. No adapter wired yet.
- Files: EDIT `backend/yen_gov/core/events.py` (add `FetchSkipped` + append `"fetch.skipped"` to `ALL_EVENT_NAMES`); EDIT `backend/yen_gov/cli.py` (a `_mint_run_id()` helper + a `--log/--no-log` flag scaffold); EDIT `backend/tests/test_core_events.py` (pin the new name).
- Gates: pytest green; `ALL_EVENT_NAMES` pin test updated in the same commit; no rename of any existing event; the logger remains optional (no-op default) so library/test callers need no `.runtime/`.
- ONE oracle: the event-name pin test asserts `ALL_EVENT_NAMES` equals the expected 12-name tuple (11 existing + `fetch.skipped`), proving the surface grew additively and nothing was renamed.

### Row 4 - Codify the `rbi_handbook` template + shared Emit/catalogue-upsert helper + 2nd cold caller

- Scope: lift the genuinely-shared Emit + catalogue/source-upsert logic out of `rbi_handbook` into a shared helper (DRY), document the 4-module shape as the copy-per-source template, and add a SECOND single-series caller on a COLD family (a new RBI HBS cohort - Fiscal / Banking / Prices tables) by copying the template. Do NOT extract `run_pipeline` yet (Rule of Three not met).
- Files: NEW `backend/yen_gov/canonical/emit_helpers.py` (shared `upsert_catalogue_and_source` + `emit_canonical_batch` wrapping `write_csv`); EDIT `backend/yen_gov/canonical/adapters/rbi_handbook/ingest.py` to call the shared helper; NEW `backend/yen_gov/canonical/adapters/rbi_hbs_<cohort>/` (registry + parser + resolver + ingest, copied pattern); NEW CLI command `ingest-rbi-hbs-<cohort>`; tests + a `docs/architecture/backend/` template note.
- Gates: pytest green; `rbi_handbook` output is byte-identical before/after the helper extraction (parity); the new cohort emits valid canonical CSV that Tier-B accepts; observability events fire at the cohort's stage boundaries.
- ONE oracle: a parity test asserts the `rbi_handbook` CSV output is byte-identical pre- and post-refactor (the shared helper changed structure, not behaviour - Tidy First discipline).

### Row 5 - Autonomous Fetch hook + delta-skip

- Scope: add the optional per-spec `fetch()` hook (httpx, bounded 3-try) and the delta-skip gate using the Row 2 composite key, with the `operator_staged` fallback. Wire it to the RBI cohort from Row 4.
- Files: NEW `backend/yen_gov/canonical/fetch.py` (`run_fetch(spec, logger) -> ClaimCheck`, snapshot write to `_meadow/`, delta-state read/write, `fetch.skipped` on key-match); EDIT the cohort spec to declare `fetch_url` + `fetch_mode` + `spec_version`; EDIT pyproject if httpx needs promoting out of the `admin` extra; tests with a mocked `fetch` (loader-unit-test carve-out per CLAUDE.md section 14).
- Gates: pytest green; a second run with unchanged upstream emits `fetch.skipped` and writes zero new CSV bytes; a `spec_version` bump forces a re-emit; `cea.nic.in`-class sources resolve to `operator_staged` and never attempt a network call; NO `tenacity` / `core/http.py` reintroduced.
- ONE oracle: an integration test runs the cohort twice against a fixture upstream - run 1 emits rows + writes delta-state; run 2 (identical bytes) emits `fetch.skipped` and leaves the CSV mtime untouched, proving the delta gate works.

### Row 6 - Enrich hard-gates (fail-loud helpers + auto pre-flight)

- Scope: implement the six fail-loud enrich gates as shared helpers and have the runner auto-invoke `check-overlap` + `pre-flight-ingest` per source before emit.
- Files: NEW `backend/yen_gov/canonical/enrich_gates.py` (entity-resolution fail-loud, unit canonicalisation incl. nominal-vs-constant, period FY!=CY, concept-overlap>=0.70 reuse, methodology-break presence, definition-drift fingerprint); EDIT the runner/template ingest to call the gates; EDIT the cohort to route through them; tests for each gate's failure path.
- Gates: pytest green; each gate has a test proving it RAISES (not coerces) on the bad input (e.g. an unmapped state name aborts the row rather than emitting an implicit zero); the pre-flight gate's exit-code-2 path aborts the ingest with no override flag (Holy Law #5).
- ONE oracle: a test feeds a row whose entity name is unresolvable and asserts the pipeline RAISES with the offending label in the message - proving "no fuzzy guess, no implicit zero" is structural, not advisory.

### Row 7 - Extract manifest writer out of `writer.py`; verify ECI Parquet callers

- Scope: the prerequisite to deleting Parquet. Move the surviving `_regenerate_manifest` logic out of `writer.py` into a parquet-free `canonical/manifest.py`, repoint its callers, and verify whether the 3 ECI `write_batch` callers actually emit Parquet or already hit the `elections`-envelope `raise` (delete-first discipline).
- Files: NEW `backend/yen_gov/canonical/manifest.py`; EDIT `backend/yen_gov/cli.py` (line ~523 caller) + `backend/yen_gov/pipeline/dim_acs_lgd_lift.py` (line ~141 caller) to import from the new module; a short verification note in the PR body recording which ECI callers are live-emit vs dead-on-raise.
- Gates: pytest green; `datasets/manifest.json` regenerates byte-identical from the new module; grep proves no remaining `_regenerate_manifest` import from `writer.py`.
- ONE oracle: regenerate `manifest.json` from the extracted module and assert byte-identity with the pre-extraction file (structural move, zero behaviour change).

### Row 8 - Flip 3 ECI adapters to `write_csv`

- Scope: convert `eci_ls`, `eci_ae_panel`, and `pipeline/canonical_eci_backfill` from the Parquet `write_batch` path to direct `write_csv` (the pattern `eci_form10_ae` already uses), preserving every election row. Skip any caller Row 7 proved dead-on-raise (straight-delete in Row 9 instead).
- Files: EDIT the three adapters + their CLI commands + tests. Touches `datasets/data/entities/source.csv` via catalogue upsert - additive-only.
- Gates: pytest green; row counts for every affected election event are preserved (a drop is an ESCALATE per Section 0.5); emitted CSV passes Tier-B; the `source.csv` edits are append-only and do not collide with the parallel agent (coordinate timing).
- ONE oracle: a before/after row-count parity assertion per election event - the CSV output must contain exactly the same `(entity_id, year, indicator_id)` tuples the Parquet path produced (no election row lost in the format flip).

### Row 9 - Delete `envelope.py` + `writer.py` + dead dim-rows + residual Parquet

- Scope: the rip. Delete the Parquet writer, the typed batch, the dead dim-row dataclasses, the likely-dead `dim_acs_lgd_lift.py`, and clean the residual `read_parquet` / `FORMAT PARQUET` / stale Parquet docstrings.
- Files: DELETE `backend/yen_gov/canonical/writer.py` + `backend/yen_gov/canonical/envelope.py` + (if dead) `backend/yen_gov/pipeline/dim_acs_lgd_lift.py`; EDIT `backend/yen_gov/canonical/__init__.py` (drop the re-exports); EDIT `eci_ae_panel.py` (drop `read_parquet`), `ingest_pincode.py` (drop `FORMAT PARQUET`), `cli.py` (strip stale Parquet docstring mentions); delete now-orphan tests.
- Gates: pytest green; `grep -r "write_batch|BatchEnvelope|to_parquet|read_parquet|FORMAT PARQUET" backend/` returns ZERO live hits; full Tier-B validate passes on a regenerated corpus.
- ONE oracle: a repo-wide grep gate (assertable as a test) proving zero Parquet writer/reader/envelope symbols remain in `backend/` - the one-format goal is met.

### Row 10 - ICED/NITI producer split (regenerate `source.csv` + FKs) - AFTER the hot arc

- Scope: correct the producer taxonomy per SC-2 + the Hans/Max ruling. Build the single `(producer, title, vintage)` triple-registry, regenerate the 31 ICED `source.csv` rows (producer = issuing authority; ICED -> title), rewrite every observation `source_id` FK, and add the fail-loud FK gate. RUN ONLY after the parallel energy/`iced_*` faceted-reingest arc has merged.
- Files: NEW `backend/yen_gov/canonical/iced_authority_map.py` (per-endpoint -> issuing-authority mapping; research-backed) + a `docs/research/iced-authority-tracing.md` note; EDIT the iced adapters' citation calls; regenerate `datasets/data/entities/source.csv` + affected `datapoints` CSVs; EDIT `validate.py` (fail-loud FK gate: every observation `source_id` must exist in `source.csv`).
- Gates: pytest green; zero observation rows with a dangling `source_id`; no `producer` field contains a product name (a Tier-B assertion: producer != contains("Dashboard")); the corpus regenerates deterministically.
- ONE oracle: a Tier-B check asserts every distinct `producer` in `source.csv` is an organisation/authority (the closed set CEA / MoSPI / MoEFCC / "NITI Aayog" / ...) and that NO `source_id` is referenced by an observation but missing from `source.csv` - provenance is correct and closed.

### Row 11 - Greenfield NITI SDG India Index (3rd caller) -> extract shared `run_pipeline`

- Scope: ingest a genuinely new NITI-originated source (SDG India Index) end-to-end through the autonomous pipeline (producer = "NITI Aayog", title = "SDG India Index <year>"). This is the 3rd single-series caller; with Rule of Three satisfied, EXTRACT the shared `run_pipeline` entrypoint and refactor the three single-series callers (`rbi_handbook`, the Row-4 cohort, SDG) onto it.
- Files: NEW `backend/yen_gov/canonical/adapters/niti_sdg_index/` (full 4-module template); NEW `backend/yen_gov/canonical/pipeline.py` (`run_pipeline(spec, logger)` threading Fetch->Parse->Enrich->Emit); EDIT the three single-series adapters to call `run_pipeline`; NEW CLI `ingest-niti-sdg-index`; the pre-flight gate runs as part of the row; tests + a coverage note.
- Gates: pytest green; a fresh `proposal.json` + `pre-flight-ingest` report is committed and green (verdict in {mint_new, upsert, add_facet}); the three refactored callers produce byte-identical CSV vs their pre-extraction output (parity); the faceted CEA/energy path is explicitly NOT folded in (documented).
- ONE oracle: byte-identical parity of all three single-series callers' CSV output before and after the `run_pipeline` extraction, proving the abstraction was extracted on evidence without changing any behaviour.

### Row 12 - Doctrine reconciliation: rewrite Lift docs + CLAUDE.md + bootstrap + distill

- Scope: make the docs match the shipped reality. Rewrite the stale Lift doctrine doc + the add-a-source cookbook to the `run_pipeline` / `write_csv` world; record SC-1 (fetch reversal) in `CLAUDE.md` (replace the "no network fetcher" absolute with the local-pipeline-fetch rule) + the decision index; refresh the bootstrap migration banner; distill this plan per the closure ritual.
- Files: EDIT `docs/concepts/ingest-fetch-enrich-separation.md` + `docs/how-to/add-a-new-data-source.md` (remove all `core.http` / `core.io` / `write_batch` references); EDIT `CLAUDE.md` (Holy Law context + anti-pattern line for the fetch reversal, citing SC-1) + `docs/agents/bootstrap.md` + `docs/agents/guardrails.md`; EDIT `docs/reference/decision-index.md`; archive-distill this plan-doc.
- Gates: a docs-link check passes (no references to deleted symbols); CLAUDE.md and the docs agree (Holy Law #4); the plan-doc carries a per-row distillation map.
- ONE oracle: a grep gate asserts zero occurrences of `core.http`, `core.io.Source`, `write_artifact`, or `write_batch` across `docs/` - the doctrine no longer misleads the next agent.

---

## Section 4 - YAGNI refusals (explicitly NOT built)

These were considered and REJECTED; do not add them without a new sign-off:

- A DAG / workflow engine (Airflow / Dagster / dvc / Luigi). The CLI iterating the spec registry IS the runner; a DAG engine is enterprise ceremony with no payer at < 20 sources / one maintainer.
- A materialized "garden" / enrich tier on disk. Enrich stays in-memory; the canonical CSV is the reviewable enrich output (single-writer + Tier-B validated). No second reader exists.
- A plugin / entry-point / dynamic-import source registry. Explicit imports of typed specs suffice (the overview doc already rejected this).
- `pydantic-settings` / a global `Settings` object / `config/sources.json`. Typed frozen-dataclass specs + CLI flags + machine-path env vars cover all override needs; G9 just retired orphan JSON tunables - do not re-mint that pattern.
- A committed per-run receipt artifact. The `.runtime/logs/` JSON log is the receipt until a real consumer (staleness dashboard) exists. Commit state with a reader; keep ephemeral the state without one.
- A `source_id` alias / redirect table. Rip-and-replace regenerates the corpus; a fail-loud FK gate is the guarantee, not a ledger.
- Re-adding `tenacity` or `core/http.py`. A bounded `httpx` retry loop is enough.
- A generated published-state report under `docs/`. Freshness lives in `manifest.json`; a human view is a read-time render (admin app / `python -m yen_gov report`), not a committed docs file.
- Folding the faceted (CEA / energy) row shape into the single-series `run_pipeline` during this plan. Premature unification of two row shapes; deferred to a post-plan PR once the parallel arc settles.

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
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

> Plan-specific execution notes (binding): (a) Phases run A -> B -> C -> D -> E; Phase D (Rows 10-11) does NOT start until the parallel energy/`iced_*` faceted-reingest arc has merged to main - rebase first and re-verify the hot-file list. (b) `datasets/data/entities/source.csv` and `datasets/data/_schema/columns.json` are FROZEN / additive-only. (c) Rows 8-10 touch election + provenance data: a row-count drop or a dangling FK is an ESCALATE, not an auto-fix. (d) Work each row in a dedicated worktree off fresh `origin/main`; never share a worktree with a parallel agent.

## See also

- [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) - the Lift doctrine this plan modernizes (Row 12 rewrites it).
- [docs/architecture/backend/overview.md](../docs/architecture/backend/overview.md) - the (stale) layered topology this plan supersedes.
- [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) - the gold target template.
- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) - the CSV migration whose Parquet rip this plan finishes.
- [CLAUDE.md](../CLAUDE.md) - the engineering contract (authority table section 0a, correction levels section 6, anti-patterns section 10).

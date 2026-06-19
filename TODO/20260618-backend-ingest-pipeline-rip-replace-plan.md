# `ingest` pipeline - execution plan (autonomous, rip-and-replace)

**Last Updated**: 2026-06-19
**Level**: 5 (core design + data model + runtime).
**Strategy**: Rip-and-replace - build the target state directly; delete old paths outright; temporary breakage of the app between rip rows is acceptable. Canonical CSV is regenerated per phase from a coherent corpus.

This is an execution spec. It runs autonomously: the orchestrator dispatches PR-rows to subagents, resolves every design ambiguity by convening a persona debate (never by asking the user), and ships row-by-row. Section 1 is the execution model; Section 2 is the parallel PR board.

---

## 0. Mission and scope

**Mission.** Build `ingest`: a thin orchestrator that, on a trigger, drives each upstream source autonomously through **Fetch -> Enrich -> Publish** into the canonical long-format CSV store. Work is addressed by **indicator** (`ingest run --indicator total-fertility-rate`); the source adapter(s) that feed it are resolved underneath. Fetch is automated and network-capable (local pipeline only; production stays a static bundle). Delta/checkpoint state makes re-runs skip unchanged years and makes a failed run resumable. The indicator catalogue (`concepts.json` -> `indicators.json` -> `variables.csv`) is the identity source-of-truth; the pipeline reads it and never mints identity.

**In scope.** The `canonical/ingest/` engine (orchestrator, adapter registry, derived indicator->adapter index, pydantic stage messages + specs, one stage-tagged log stream, committed year-checkpoint); automated Fetch with batched/delta; the honesty preconditions (concept-compatibility, divergence gate, splice break-row gate, India-discontinuity enrich gates); the Parquet replace; the ICED producer correction (evidence-gated); one greenfield proof source (NITI SDG India Index); the cleanup command + path util; the subsystem doc + CLI reference + rewrite of the two stale ingest docs.

**Out of scope.** Frontend/admin/charting; changing `source.csv` (5-field) or `columns.json` (the only additive bump is `concepts.json` gaining `price_basis` + `sampling_frame`, Row 1); any new indicator family beyond the one cold RBI HBS cohort (Row 5) and SDG India Index (Row 11). See Section 6 for deferred items.

**Binding decisions (carry context the rows depend on).**
- **D1 - Automated fetch is reintroduced** in the local pipeline (reversing the earlier "no network fetcher" rule). Holy Laws #1/#2 hold: fetch runs only locally; production is static; CI consumes committed CSV and never fetches.
- **D2 - ICED is not a `producer`.** Where ICED is a pure passthrough of an upstream (CEA/MoSPI/MoEFCC), the producer becomes that issuing authority and ICED moves into `title`; where ICED originates a derived analytic, the producer stays `"NITI Aayog ICED"`. This is decided per endpoint on cited evidence (Row 10), never as a blanket sweep. It re-mints affected `source_id`s and never changes any `indicator_id`.
- **D3 - Pydantic is mandatory** for every in-process boundary type: the 3 stage messages, the 11 log events, and `SourceSpec`/`IndicatorSpec`. The 11 events ARE converted to pydantic; they keep a hand-rolled serializer (iterate `model_fields`, route `Path` through the path util, emit `Z`) because `model_dump(mode="json")` serialises `Path` via `str()` = backslash on Windows and `+00:00` not `Z`, which would break the POSIX-path log contract. Four DATA-contract seams stay non-pydantic: `columns.json`+`csv_validator`, `derive_source_id`, the JSON-Schema/`x-version`/`_ops`/`manifest.json` artifacts, and the DuckDB-WASM read seam.
- **D4 - Year-checkpoint + resume.** A committed per-adapter checkpoint records each completed year and the hash of its raw fetched payload. A re-run skips years whose raw hash is unchanged; a revised old year (its hash changed) re-opens. A run that fails partway (agent crash, upstream site failure) is **resumable**: re-running continues from the last completed year - completed years are skipped, the failed/remaining years are processed. `run --resume` is the explicit affordance; plain `run` has the same idempotent effect.

---

## 1. Execution model (autonomous + parallel)

The implementing agent is the ORCHESTRATOR. It does not ask the user anything. It:

1. **Reads the PR board (Section 2)** and dispatches every row whose `Depends on` rows are all DONE to a stateless `runSubagent`, fanning out as many in parallel as the dependency DAG allows.
2. **Each subagent owns one row**: it sets the row `Status` to IN-PROGRESS, implements the row's scope to its gates + the one oracle, opens a PR, and on green merge sets the row DONE with the PR number; or sets BLOCKED with a one-line reason if it hits an irreducible blocker (missing upstream data, a real contradiction). A BLOCKED row does not stop the board - the orchestrator keeps shipping other unblocked rows and revisits the blocker.
3. **Resolves all design ambiguity by persona debate, never by asking the user.** When a row hits a contested call (a schema shape, a naming choice, a precedence rule, a tolerance value), the responsible subagent convenes the relevant authority personas (Gregor = contracts, Fowler = craft, Hans+Max = data shape, Jony+Citizen = UX) in debate, converges to ONE written ruling, bakes it into the row, and proceeds. Authority map: CLAUDE.md section 0a.
4. **Ships non-stop**: one row = one PR = one branch, 2-commit-then-squash, the 5-gate Definition-of-Done, `gh pr merge --squash --delete-branch`, pull, dispatch the next unblocked rows.
5. **Has no external dependency**: no other agent is running. The only subagents are the ones this plan spawns. There is no "wait for a parallel arc."

Stop conditions are limited to: a row's own irreducible blocker (-> BLOCKED, continue elsewhere), or an honesty gate that genuinely requires a methodology determination (-> resolve via a Hans+Max debate and record the ruling on the row; only if the debate cannot converge does the row go BLOCKED).

---

## 2. PR board (parallel, state-tracked)

Status legend: `[ ]` PENDING, `[~]` IN-PROGRESS (claimed by a subagent), `[B]` BLOCKED (reason), `[x]` DONE (PR #). Subagents update their own row. Rows with all `Depends on` = DONE may run concurrently.

| Row | Title | Phase | Depends on | Status | PR |
| --- | --- | --- | --- | --- | --- |
| 1 | Pydantic stage messages + `SourceSpec`/`IndicatorSpec` + catalogue FK + concept-compatibility (`price_basis`/`sampling_frame`) | A | - | [ ] | - |
| 2 | Committed year-checkpoint receipt (raw-payload hash + staleness) + Tier-B gate | A | - | [ ] | - |
| 3 | `ingest/paths.py` + one stage-tagged log stream + events->pydantic (hand-rolled serializer) + `fetch.skipped` + run_id | A | - | [ ] | - |
| 7 | REPLACE manifest: `emit_manifest()` (no parquet scan) + delete `dim_acs_lgd_lift` dead emit (keep `load_lgd_lookup`) | C | - | [ ] | - |
| 8 | Flip 3 ECI adapters (`eci_ls`, `eci_ae_panel`, backfill) to `write_csv` | C | - | [ ] | - |
| 4 | `canonical/ingest/` orchestrator + registry + derived index + run-preamble + wire `rbi_handbook` (no extraction) + `run`/`status` CLI | B | 1, 3 | [ ] | - |
| 5 | Automated Fetch hook + `cache_units_for` (plural) + delta-skip + resume + 2nd cold caller | B | 4, 2 | [ ] | - |
| 6 | Enrich India-discontinuity gates + divergence gate + splice break-row gate + status-shows-provenance + auto pre-flight | B | 4, 1 | [ ] | - |
| 9 | Delete `envelope.py` + `write_batch` + scan body + residual Parquet | C | 7, 8 | [ ] | - |
| 10 | ICED authority-tracing (`docs/research/` table) + evidence-gated producer correction | D | 9 | [ ] | - |
| 11 | Greenfield NITI SDG India Index (3rd single-series) -> extract+ratify `run_pipeline`; consolidate cold `sources/` adapters | D | 4, 5, 6 | [ ] | - |
| 12 | `ingest clean` command + runtime-dir env override | E | 3 | [ ] | - |
| 13 | Docs: `docs/architecture/ingest/pipeline.md` + `cli-ingest.md` + honesty doctrine; rewrite stale docs + CLAUDE.md | E | 1-12 | [ ] | - |

Parallel start set (no unmet dependency): **Rows 1, 2, 3, 7, 8** run concurrently. Then 4 (after 1,3); 5 (after 4,2); 6 (after 4,1); 9 (after 7,8); 10 (after 9); 11 (after 4,5,6); 12 (after 3); 13 last.

---

## 3. Binding requirements

**Naming + CLI.** Subsystem `ingest`; engine at `backend/yen_gov/canonical/ingest/` (a sibling to `canonical/adapters/`, one `engine -> adapters` import arrow; cold `sources/` adapters consolidate into `canonical/adapters/` in Row 11, hot `iced_*` left as-is). Entry `python -m yen_gov ingest <verb>`. Verbs: `run`, `status` (per-indicator coverage + which source owns which years + staleness; absorbs any list/explain need), `clean`; plus the existing `pre-flight-ingest` for author-time design. `run --indicator X` is the primary path; `--adapter Y` is a scope filter; `--from/--to STAGE` runs a window; `--resume` continues from the checkpoint. `run` prints a one-line fan-out echo before work (`tfr <- [rbi-handbook 1971-2011, srs 2012-2024]: fetching 2 sources`). A derived in-memory `indicator_id -> [adapter_slug]` index resolves indicator->source; it is never committed.

**Stages.** Three pure-filter stages: **Fetch -> Enrich -> Publish**. Spec-validate + checkpoint-diff is `run`'s fail-loud preamble, not a stage. Source design is author-time (`pre-flight-ingest` + the typed spec).

**Typing.** Per D3. `CanonicalBatch.source_rows` is the 5-field shape. Stage messages are validated at construction (the producing filter), trusted between hops.

**Identity + honesty (fail-loud preconditions).**
- Every `IndicatorSpec.indicator_id` FKs `indicators.json` at registration; additionally assert the spec's `(unit, normalisation, price_basis, sampling_frame)` match the concept. Add `price_basis` (current/constant + base year) and `sampling_frame` to `concepts.json` for economic/survey families (additive).
- **Divergence gate** at the UPSERT seam: a second `source_id` overwriting an existing cell `(entity, year, period, indicator)` with a value beyond a per-concept tolerance FAILS LOUD (no silent last-writer-wins); within-tolerance passes; over-tolerance is resolved by a recorded precedence + audit row or a methodology break.
- **Splice break-row gate** (plain English: some indicators take early years from one publisher and recent years from another, stitched into one continuous series - a "splice"; the year where the publisher changes is a "seam" where numbers can jump because the method changed). The first time a publisher boundary appears INSIDE one `(entity_id, indicator_id)` time series (the time-ordered rows change `source_id` mid-series), the writer REFUSES to publish unless a `methodology_breaks` row exists at the seam year and the indicator's `methodology_version` FK resolves to it - so the chart shows a visible marker and never computes a growth rate across the seam. Disjoint-entity multi-source (each state contributes its own rows; no seam on a single line) does not trigger it. There is no `splice` verb.
- **India-discontinuity enrich gates** (the six fail-loud gates must include): bifurcation (Andhra/Telangana 2014 is an id-REUSE - `IN-S01` stays valid - so a pre-2014 Telangana row or a post-2019 "J&K state" `IN-S09` row must fail or be force-tagged), code-authority (LGD vs Census vs ECI - fail on ambiguous/unmapped, never best-guess), fiscal-year != calendar-year, provisional-vs-revised (carry estimate status; ties to the checkpoint re-open), price-basis (refuse a constant-price UPSERT into a current-price cell), publisher-bounded-universe (do not synthesise phantom states for publisher-bounded indicators).

**Fetch + state.** Per-spec `fetch()` (httpx, bounded 3-try, no tenacity) at the source's natural cache unit; `fetch_mode="operator_staged"` fallback for flaky-TLS sources. `cache_units_for(indicator_id) -> tuple[CacheKey, ...]` (plural; an indicator may span >1 unit); `CacheKey` is opaque (orchestrator dedups by equality). Enrich slices the requested indicator out of the parsed unit; two indicators sharing one unit fetch once. Year-checkpoint committed at `datasets/_ops/ingest-state/<adapter_slug>.json` (schema + `x-version`; per-year hash of the RAW fetched payload; a skip ticks the `update_period_days` staleness clock, never hides it). Resumable per D4. One stage-tagged JSON-lines log stream at `.runtime/logs/<run_id>/run.log` (`[fetch]`/`[enrich]`/`[publish]` tags); `run_id` = `YYYYMMDD-xxxxxxxx`; no correlation id.

**Rip.** Manifest/Parquet is a REPLACE, not an extract: `manifest.json` is already `tables: []`, so write a ~15-line `emit_manifest()` (version stamp + `_DEPRECATIONS`, no scan), repoint `emit-taxonomy`, and delete `write_batch` + the scan body + `dim_acs_lgd_lift`'s dead emit (keep `load_lgd_lookup`). `run_pipeline` is scoped single-series and is extracted only at Row 11 (the 3rd single-series caller; `rbi_handbook` + the HBS cohort + SDG); the existing faceted `iced_power.ingest_pipeline` stays a separate strategy.

**Path discipline.** `canonical/ingest/paths.py::to_repo_relative_posix(p, *, repo_root)` is the single path-emit seam (relativise against repo root, force `/`, fail-fast on a surviving drive letter or an escape). Every path that leaves the process routes through it.

---

## 4. Target architecture

```
ingest run --indicator total-fertility-rate            # main path (prints fan-out echo, then runs)
ingest run --indicator nsdp-inr-crore                  # -> 2 adapters; UPSERT-merge; splice gate requires a break row
ingest run --adapter rbi-handbook                      # scope filter
ingest run --indicator birth-rate --from enrich        # window (re-enrich+publish from cache)
ingest run --resume                                    # continue from the last completed checkpoint
ingest status --indicator nsdp-inr-crore               # coverage + per-source year spans + staleness
ingest clean [--days N] [--force] [--dry-run]
pre-flight-ingest --proposal-file ...                  # EXISTING author-time design gate
   |
orchestrate(*, indicator|adapter, repo_root, config)   # thin; never branches on adapter_slug
   |  registry {adapter_slug -> Adapter};  derived {indicator_id -> [adapter_slug]} (in-memory)
   |  FK-check each IndicatorSpec.indicator_id vs indicators.json (fail-loud at registration)
   v
PREAMBLE (not a stage): validate spec + list cache units + diff vs checkpoint -> work-list
   |-- FETCH    fetch() at the cache unit (or operator_staged); raw bytes -> _meadow/ (gitignored);
   |            checkpoint year -> hash(raw payload); fetch.skipped on unchanged year -> ClaimCheck
   |-- ENRICH   parse only the requested indicator's slice; resolve entity/unit/period; concept-compat +
   |            India-discontinuity gates; FAIL LOUD -> CanonicalBatch
   |-- PUBLISH  validate vs columns.json; DIVERGENCE gate; SPLICE break-row gate; UPSERT via write_csv;
   |            upsert source.csv; advance checkpoint -> datasets/data/...csv

logs:        .runtime/logs/<run_id>/run.log   (one stage-tagged JSON-lines stream)
checkpoint:  datasets/_ops/ingest-state/<adapter_slug>.json   (committed; per-year raw hash)
identity:    concepts.json -> indicators.json -> variables.csv   (SOT; pipeline FKs in)
```

---

## 5. Per-row specs

**Row 1.** Pydantic `messages.py` (`ClaimCheck`, `RawRecord`, `CanonicalBatch`, `ReplacementSemantics`) + `spec.py` (`SourceSpec` parent + `IndicatorSpec` children, no field repeated across levels) + `catalogue_fk.py` (registration FK + concept-compatibility check) under `canonical/ingest/`; additive `price_basis`+`sampling_frame` on `concepts.json` + schema (minor `x-version`). Gates: a bogus `indicator_id` RAISES at registration; a `(unit/normalisation/price_basis/sampling_frame)` mismatch RAISES; `source_rows` is 5-field. Oracle: `CanonicalBatch.observation_rows` keys == the non-facet `geo/*.csv` column set AND a price-basis-mismatched spec fails registration.

**Row 2.** `datasets/schemas/ingest-state.schema.json` + `canonical/ingest/state.py` (read/write/compare, raw-hash skip predicate) + a `tier_b_ingest_state_receipt` check. Gates: skip iff raw-hash equal; a changed hash on an OLD year forces re-process; a skip advances the staleness field. Oracle: receipt for {2018..2022} - 2019 skipped on hash-match, forced on hash-change, staleness still advances on a skip.

**Row 3.** `canonical/ingest/paths.py`; convert the 11 `core/events.py` events to pydantic `BaseModel(frozen=True)` with a hand-rolled `to_extra` over `model_fields` routed through the path util (emit `Z`); `FetchSkipped` + `ALL_EVENT_NAMES`; one stage-tagged stream in `core/logging.py`. Gates: a logged Windows `Path` emits repo-relative POSIX, no `C:`, timestamp ends `Z`; `ALL_EVENT_NAMES` grows by one. Oracle: a pydantic event with a Windows abs `Path` emits a byte-identical log line to the pre-conversion output.

**Row 4.** `canonical/ingest/{orchestrator,registry,cli}.py`; the derived index; the run-preamble; wire `rbi_handbook` driven by the orchestrator as-is (NO `run_pipeline` extraction); `run` + `status` CLI; fan-out echo. Gates: `ingest run --indicator total-fertility-rate` == `--adapter rbi-handbook --indicator total-fertility-rate`; the orchestrator has zero `if adapter_slug ==`; `status` shows per-source year spans. Oracle: `rbi_handbook`'s emitted CSV + log lines are byte-identical before/after being driven by the orchestrator.

**Row 5.** `canonical/ingest/fetch.py` (`cache_units_for` plural, opaque key); a 2nd cold caller (new RBI HBS cohort); `--resume`. Gates: two indicators sharing a unit fetch once; a 2nd run with unchanged years emits `fetch.skipped` + zero new bytes; a `spec_version` bump re-emits; a failed run resumes from the last completed year. Oracle: run twice - run 2 `fetch.skipped` + CSV mtime untouched; mutating one year's raw fixture re-emits exactly that year; a simulated mid-run failure resumes and completes the remaining years.

**Row 6.** `canonical/ingest/{enrich_gates,divergence,splice_guard}.py` (start inline, split on a 2nd caller); the publish-seam gates; `status` per-source year spans. Gates: each India-discontinuity gate RAISES on bad input; a material cross-source disagreement FAILS LOUD; a mid-series `source_id` change REFUSES emit without a break row at the seam. Oracle: a 2-source fixture with a mid-series publisher change fails to publish until a `methodology_breaks` row at the seam exists, then publishes one series with each row's `source_id` intact; a >tolerance overlap-year disagreement fails loud.

**Row 7.** `canonical/manifest.py` (`emit_manifest()` ~15 lines, no scan); repoint `emit-taxonomy`; delete `dim_acs_lgd_lift`'s dead emit (keep `load_lgd_lookup`). Gate: `manifest.json` regenerates byte-identical. Oracle: byte-identity + a grep proving the scan body is gone.

**Row 8.** Flip `eci_ls`, `eci_ae_panel`, `canonical_eci_backfill` to `write_csv`; additive `source.csv` upsert. Gate: per-event row counts preserved (a drop is a hard fail). Oracle: per-event before/after parity of `(entity_id, year, indicator_id)` tuples.

**Row 9.** Delete `canonical/writer.py` + `canonical/envelope.py`; clean residual `read_parquet`/`FORMAT PARQUET` + `canonical/__init__.py` exports. Gate: `grep -r "write_batch|BatchEnvelope|to_parquet|read_parquet|FORMAT PARQUET" backend/` == 0 live hits; Tier-B green. Oracle: the grep gate.

**Row 10.** `docs/research/iced-authority-tracing.md` (per-endpoint: ICED's named upstream + passthrough-vs-derived evidence) authored first; `canonical/iced_authority_map.py`; evidence-gated producer correction (ICED-originated keep `"NITI Aayog ICED"`); regenerate affected `source.csv` + datapoints; `validate.py` FK + producer-not-a-product assertion. Gate: every reattributed endpoint cites passthrough evidence; zero dangling `source_id`; the `indicator_id` set is unchanged. Oracle: a Tier-B check asserts every `producer` is an organisation, every `source_id` resolves, the `indicator_id` set is identical before/after, and each changed producer is cited in the tracing table.

**Row 11.** `canonical/adapters/niti_sdg_index/`; extract `run_pipeline` (single-series; 3rd caller); git-mv the cold `sources/` single-series adapters under `canonical/adapters/`; a committed green `pre-flight-ingest` report. Gate: the three single-series callers byte-identical vs pre-extraction; faceted `iced_power.ingest_pipeline` untouched. Oracle: byte-identical parity of all three single-series callers before/after the extraction.

**Row 12.** `canonical/ingest/cleanup.py` (`CLEAN_TARGETS`, routed through `paths.py`); `ingest clean`; `YEN_GOV_RUNTIME_DIR` override. Gate: `--dry-run` mutates nothing; every target resolves under `.runtime/`; refuses a target outside `.runtime/`; `N < 90` without `--force` aborts. Oracle: seed an old `.runtime/logs/` dir + a `_ops/ingest-state` file; `clean` removes the log, leaves the checkpoint.

**Row 13.** `docs/architecture/ingest/pipeline.md` (subsystem + operator mental model + honesty doctrine, keep-receipts triplets) + `docs/reference/cli-ingest.md`; rewrite `docs/concepts/ingest-fetch-enrich-separation.md` + `docs/how-to/add-a-new-data-source.md`; record D1-D4 in `CLAUDE.md` + the decision index; distill this plan. Gate + oracle: a grep proving zero `core.http`/`core.io.Source`/`write_artifact`/`write_batch`/stale-"Lift" refs in `docs/`.

---

## 6. Deferred / out of scope

**Carried-over energy deferrals (recorded so a future agent does not rediscover them):**
- **final-energy is backend-only / orphan.** The single-axis indicator-allowlist descriptor cannot express the 2-D sector x fuel shape without double-counting; a 2-D descriptor type is future work.
- **Pre-existing peak-adapter bug.** `backend/yen_gov/sources/iced_power/ingest.py` derives `source_id` `src-152167300b98`, which is absent from `datasets/data/entities/source.csv`; flagged for a separate follow-up, not in scope here.
- **CEA+ICED plan D1/D2** (generation faceting, retired-capacity) remain deferred by design.

**YAGNI - not built:** a DAG/workflow engine; a materialized "garden" tier; a runtime endpoint crawler; a general N-source splice engine; a reconciliation framework or unit-inference engine (the divergence + concept gates are declare-and-compare on data in hand); a second checkpoint file; `pydantic-settings`/`config/sources.json`/`active_adapter`; a plugin adapter registry; `rollback`+`audit.jsonl`; an `inventory` module; `explain`/`discover`/stage subcommands; five log files + a correlation id; a committed reverse index; a committed per-run receipt; a `source_id` alias table; `tenacity`/`core/http.py`; a generated published-state report under `docs/`; folding faceted (CEA/energy) into the single-series `run_pipeline`; pre-creating empty ingest modules (start inline, split on the 2nd caller).

---

## 7. Decisions log (decision / why / rejected)

| Decision | Why | Rejected |
| --- | --- | --- |
| Name `ingest`; engine at `canonical/ingest/` | The repo's existing vocabulary; a sibling to `adapters/` avoids a sixth ingest home | "Lift"; a top-level `ingest/` |
| Indicator-primary CLI, `--adapter` filter | Agents/humans think in indicators; precise flag avoids the `source_id` collision | source-primary; `--source` (ambiguous) |
| 3 stages (Fetch->Enrich->Publish) | A non-emitting "Stage 0" is `run`'s preamble, not a pipe stage | a 4th "Discover" stage |
| ~3 verbs (run/status/clean + pre-flight) | A verb and a flag for one act is two grammars | stage subcommands; list-*/explain/discover/rollback/inventory |
| Events convert to pydantic (hand-rolled serializer) | One typed model at every boundary; the serializer preserves POSIX log paths that `model_dump` would break on Windows | exempting events as dataclasses |
| Splice = break-row precondition, no verb | An emergent splice without a forced break ships a smooth line across a methodology seam | emergent splice; a `splice` verb |
| Divergence gate at UPSERT | Silent last-writer-wins hides publisher disagreement | precedence-only |
| Year-checkpoint + resume (raw-hash) | Autonomous delta + agents/sites fail mid-run, so runs must resume; raw-hash re-opens revised years | re-run-from-clean only; no checkpoint |
| `run_pipeline` single-series, extract at Row 11 | `rbi_handbook`+SDG are both single-series; faceted is separate and already exists | extract at Row 4 (one caller) |
| Manifest/Parquet = REPLACE | `manifest.json` is already `tables: []`; the generator is dead | extract-then-preserve |
| ICED reattribution evidence-gated | A blanket CEA sweep bakes a provenance lie where ICED originates | a 31-row sweep |
| Concept-compatibility + India gates | FK existence != measuring the right thing; India breaks at bifurcation/calendar/price-basis seams | FK-only; generic gates |

---

## Execution contract

"Implement it" runs this autonomously. Orchestrator: dispatch every dependency-satisfied PR-row to a stateless subagent in parallel (start set: Rows 1,2,3,7,8); each subagent updates its board row (IN-PROGRESS -> DONE+PR / BLOCKED+reason), implements to the row's gates + the one oracle, opens a PR, and ships on green (`gh pr merge --squash --delete-branch`); resolve every design ambiguity by a persona debate that converges to one ruling baked into the row - never ask the user; park master on `scratch-master-parking` so no worktree owns `main`; each row in its own worktree off fresh `origin/main`; full suite green at merge, tests ship with the row, no new mocks; post-merge hygiene each time; `source.csv` + `columns.json` are frozen/additive-only; a row-count drop on an election/provenance row, a dangling FK, or a non-convergent methodology call sets the row BLOCKED with the reason. Closure: every row DONE or BLOCKED-with-reason; then distill this plan per `docs/how-to/distill-a-plan.md`.

## See also
- [backend/yen_gov/canonical/adapters/rbi_handbook/](../backend/yen_gov/canonical/adapters/rbi_handbook/) - the gold single-series template.
- [datasets/taxonomy/concepts.json](../datasets/taxonomy/concepts.json) -> [indicators.json](../datasets/taxonomy/indicators.json) -> [variables.csv](../datasets/data/variables.csv) - the identity SOT.
- [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) - the doctrine Row 13 rewrites.
- [CLAUDE.md](../CLAUDE.md) - the engineering contract (authority table section 0a).

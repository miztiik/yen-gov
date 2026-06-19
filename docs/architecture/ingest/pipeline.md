# Ingest pipeline

**Last Updated**: 2026-06-19

The `ingest` subsystem is the thin orchestrator that drives each upstream source autonomously through **Fetch -> Enrich -> Publish** into the canonical long-format CSV store under `datasets/data/`. Work is addressed by **indicator**; the source adapter(s) that feed it are resolved underneath. Fetch is automated and network-capable in the LOCAL pipeline only (Holy Laws #1/#2 hold: production is a static bundle, CI consumes committed CSV and never fetches). A committed per-adapter year-checkpoint makes re-runs skip unchanged years and makes a failed run resumable.

Engine home: [backend/yen_gov/canonical/ingest/](../../../backend/yen_gov/canonical/ingest/). The CLI reference is [docs/reference/cli-ingest.md](../../reference/cli-ingest.md); the operator cookbook for adding a source is [docs/how-to/add-a-new-data-source.md](../../how-to/add-a-new-data-source.md); the three-stage doctrine is [docs/concepts/ingest-fetch-enrich-separation.md](../../concepts/ingest-fetch-enrich-separation.md).

## Operator mental model (indicator-primary)

You think in indicators, not sources. `ingest run --indicator total-fertility-rate` resolves the owning adapter(s) under the hood and prints a one-line fan-out echo BEFORE any work:

```
total-fertility-rate <- [rbi-handbook 1971-2011]: running 1 adapter
```

`--adapter rbi-handbook` is a scope filter (and, given alone, the unit of work = every indicator that adapter owns). `--resume` continues from the last completed checkpoint year. `ingest status --indicator X` reports per-indicator coverage: which `source_id` owns which year span, read straight off the emitted datapoints CSV's `source_id` column (the honest on-disk truth, never a separate committed index). `ingest clean` sweeps stale ephemera under `.runtime/`. `pre-flight-ingest` (the existing author-time design gate, [ADR-0046](../backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)) is run when DESIGNING a new indicator, before any adapter code exists.

The identity source-of-truth is the catalogue chain `concepts.json -> indicators.json -> variables.csv`. The pipeline READS it and never mints identity: every `IndicatorSpec.indicator_id` FKs `indicators.json` at registration, and the spec's `(unit, normalisation, price_basis, sampling_frame)` tuple must match the resolved concept (fail-loud, see [catalogue_fk.py](../../../backend/yen_gov/canonical/ingest/catalogue_fk.py)).

## The three stages + the run-preamble

```
PREAMBLE (not a stage): validate targeted specs vs the catalogue + list cache units + diff vs checkpoint -> work-list
  |
  |-- FETCH    fetch() at the cache unit (httpx 3-try, or operator_staged); raw bytes -> .runtime/cache/ingest/ (gitignored);
  |            checkpoint year -> hash(raw payload); fetch.skipped on an unchanged year
  |-- ENRICH   parse only the requested indicator's slice; resolve entity/unit/period; concept-compatibility +
  |            the six India-discontinuity gates; FAIL LOUD -> CanonicalBatch
  |-- PUBLISH  validate vs columns.json; DIVERGENCE gate; SPLICE break-row gate; UPSERT via write_csv;
  |            upsert source.csv; advance the checkpoint -> datasets/data/...csv
```

There are exactly three pure-filter stages. **Spec-validate + checkpoint-diff is `run`'s fail-loud preamble, NOT a fourth stage** - a non-emitting "Stage 0" is the run's setup, not a pipe. Source DESIGN is author-time (`pre-flight-ingest` + the typed spec), not a runtime stage.

Stage messages ([messages.py](../../../backend/yen_gov/canonical/ingest/messages.py): `ClaimCheck`, `RawRecord`, `CanonicalBatch`, `ReplacementSemantics`) are pydantic, validated at construction (by the producing filter) and trusted between hops. `CanonicalBatch.source_rows` is the 5-field `source.csv` shape.

## Architecture: orchestrator / registry / derived index

`orchestrate()` ([orchestrator.py](../../../backend/yen_gov/canonical/ingest/orchestrator.py)) is the engine. It resolves an indicator (or adapter scope) to the adapter(s) that feed it, FK-checks the TARGETED specs, runs the preamble, and drives each adapter POLYMORPHICALLY through the registry. **It NEVER branches on `adapter_slug`** - dispatch is `registry[slug].run_indicator(...)`, so adding a source is adding a registry entry, never an `if adapter_slug ==` arm.

- **Registry** ([registry.py](../../../backend/yen_gov/canonical/ingest/registry.py)): `{adapter_slug -> Adapter}`. The `Adapter` protocol is minimal - `adapter_slug`, `source_specs() -> tuple[SourceSpec, ...]`, `run_indicator(indicator_id, *, repo_root, config)`. A `FetchableAdapter` adds `cache_units_for`, `spec_version`, `process_year` for the automated Fetch + per-year delta loop; the engine runs that loop IFF `isinstance(adapter, FetchableAdapter)` - a CAPABILITY check, never an `adapter_slug` branch.
- **Derived index**: `build_indicator_index()` turns the registry into an in-memory `{indicator_id -> [adapter_slug]}` map. It is NEVER committed - it is rebuilt from the registry (the single source of truth) every call, and asserts each `SourceSpec.adapter_slug` matches its registry key so a mis-wired adapter fails loud.
- **Specs** ([spec.py](../../../backend/yen_gov/canonical/ingest/spec.py)): a `SourceSpec` is the PARENT (adapter + the provenance quartet producer/title/vintage/url, from which `source_id` is DERIVED, never stored); its children are `IndicatorSpec` rows (indicator_id + the measurement tuple). No field repeats across the two levels - the split is by identity axis, mirroring `concepts.json -> indicators.json -> source.csv`.

One adapter can drive MORE THAN ONE source (e.g. `rbi_handbook` feeds the SRS vital-rates table and the SRS abridged life tables - two distinct `(producer, title, vintage)` citations), which is why the protocol exposes `SourceSpec` (the provenance grouping) rather than a flat indicator list.

## State: committed year-checkpoint + resume

A checkpoint ([state.py](../../../backend/yen_gov/canonical/ingest/state.py)) is the pipeline's memory of "which years of this source have I pulled, and what did the raw bytes hash to?". It lives committed at `datasets/_ops/ingest-state/<adapter_slug>.json` (schema `ingest-state.schema.json` + `x-version`; a Tier-B `tier_b_ingest_state_receipt` check guards it). It drives three behaviours:

- **Delta-skip.** A re-run SKIPS a year iff the stored `raw_sha256` equals the hash of the freshly fetched RAW payload AND that year is `completed`. Nothing is re-parsed, re-enriched, or re-written; the run emits a `fetch.skipped` event and the CSV mtime is untouched.
- **Re-open on revision.** A CHANGED hash on an already-completed OLD year means the publisher restated it (a provisional estimate becoming revised); the skip predicate returns `False` and that year re-processes.
- **Resume.** A run that failed partway left some years `completed=False`; a re-run re-processes exactly those (the skip predicate refuses to skip an incomplete year). `ingest run --resume` is the explicit affordance; a plain `run` is already idempotent with the same effect.

The hash is over the RAW bytes (before any parse), so a cosmetic upstream re-encode legitimately re-opens a year while a byte-identical re-fetch skips it. A skip still advances the `last_checked` staleness clock - staleness never hides. The checkpoint is a plain dict round-tripped through the JSON-Schema (one of the four non-pydantic data-contract seams, see D3), not a pydantic model.

The raw-bytes Fetch cache ([fetch.py](../../../backend/yen_gov/canonical/ingest/fetch.py)) lands in `.runtime/cache/ingest/` (gitignored). The DELTA contract is the committed checkpoint's `raw_sha256`, not the cache, so the cache is a within-run claim-check that need not outlive a run; `ingest clean` sweeps it.

## The honesty doctrine

Three families of fail-loud preconditions stop the engine from silently papering over a publisher disagreement, a methodology seam, or an India administrative discontinuity. None is a "best guess" - each RAISES on bad input, per Holy Law #5 (fail fast at the boundary).

### Divergence gate (UPSERT seam)

When a SECOND `source_id` overwrites a cell `(entity_id, time)` an existing `source_id` already wrote, the two publishers DISAGREE about the same fact. [divergence.py](../../../backend/yen_gov/canonical/ingest/divergence.py) makes a MATERIAL disagreement FAIL LOUD instead of silent last-writer-wins. The tolerance is RELATIVE (a fraction of the cell value, symmetric, with an absolute floor so a near-zero cell does not divide by ~0), sourced from an optional `divergence_tolerance` on the concept row, defaulting to 1% - the band two honest publishers stay inside through rounding and routine revision. A within-tolerance difference passes; an over-tolerance one is allowed ONLY with a recorded `DivergenceResolution` (the audit row naming which `source_id` wins and why). A same-`source_id` re-emit is never a divergence; a `None` on either side carries no claim. It is declare-and-compare on data in hand - there is no reconciliation engine.

### Splice break-row gate (PUBLISH seam)

Some indicators take EARLY years from one publisher and RECENT years from another, stitched into one continuous series - a "splice". The year the publisher changes is a "seam" where numbers can JUMP because the method changed, not because the world did. [splice_guard.py](../../../backend/yen_gov/canonical/ingest/splice_guard.py): the first time the time-ordered rows of one `(entity_id, indicator_id)` series change `source_id` mid-series, the writer REFUSES to publish unless (1) a `methodology_breaks` row exists at the seam year and (2) the indicator's `methodology_break_ids` FK resolves to it - so the chart shows a visible break marker and never computes a growth rate across the seam. Disjoint-entity multi-source (state A from publisher P, state B from publisher Q - no seam on any single line) does NOT trigger it; the gate is per-entity. There is no `splice` verb: the splice is an EMERGENT property of the rows, and the only affordance is to AUTHOR the break row, never to suppress the check. The breaks table is read LAZILY - a single-source run never touches it.

### The six India-discontinuity enrich gates

[enrich_gates.py](../../../backend/yen_gov/canonical/ingest/enrich_gates.py), each a pure function that RAISES on bad input:

1. **bifurcation / state-lifespan** - Andhra/Telangana 2014 is an id-REUSE (`IN-S01` stays valid for the residual state), but Telangana did not exist before 2014 and Jammu & Kashmir ceased to be a STATE in 2020. A row outside a state's administrative lifespan FAILS (or is force-tagged by an explicit operator acknowledgement).
2. **code-authority** - an entity label MUST resolve through ONE issuing authority (LGD / Census / ECI) to ONE code. Unmapped or ambiguous = FAIL; the engine never best-guesses an identity.
3. **fiscal-year != calendar-year** - a fiscal-year series (`2015-16`) anchors to its fiscal-year-start integer (2015), consistently. Treating a fiscal label as a calendar year, or mixing the two, FAILS.
4. **provisional-vs-revised** - an estimate carries a status (provisional -> revised -> final); a provisional value MUST NOT silently overwrite an already-final one. The status ties to the checkpoint's re-open behaviour.
5. **price-basis** - a constant-price (real) value MUST NOT be UPSERTed into a current-price (nominal) cell. The two are different facts; splicing them is a lie the gate refuses.
6. **publisher-bounded-universe** - when a publisher only covers a bounded set of entities, the engine MUST NOT synthesise phantom rows for the entities it omits.

## Logs

One stage-tagged JSON-lines stream per run at `.runtime/logs/<run_id>/run.log`, with `[fetch]` / `[enrich]` / `[publish]` tags; `run_id` is `YYYYMMDD-xxxxxxxx`; there is no correlation id and no per-stage log file. The 11 pipeline events ([core/events.py](../../../backend/yen_gov/core/events.py)) are pydantic `BaseModel(frozen=True)` with a HAND-ROLLED `to_extra` serializer (it routes every `Path` through the path-emit seam and emits `Z` timestamps, which `model_dump(mode="json")` would break on Windows - see D3).

## Path discipline

[paths.py](../../../backend/yen_gov/canonical/ingest/paths.py) `to_repo_relative_posix(p, *, repo_root)` is the single path-emit seam: relativise against the repo root, force `/`, fail-fast on a surviving drive letter or an escape. Every path that leaves the process (a log line, a result, a CLI echo) routes through it (CLAUDE.md section 2).

## Module map

| Module | Role |
| --- | --- |
| `orchestrator.py` | `orchestrate()` (preamble -> Fetch -> Enrich -> Publish, polymorphic dispatch) + `compute_status()` |
| `registry.py` | `Adapter` / `FetchableAdapter` protocols + `default_registry()` + the `RbiHandbookAdapter` wrapper |
| `spec.py` | `SourceSpec` / `IndicatorSpec` / `PriceBasis` author-time specs |
| `catalogue_fk.py` | registration FK (`indicator_id` vs `indicators.json`) + concept-compatibility check |
| `messages.py` | pydantic stage messages (`ClaimCheck`, `RawRecord`, `CanonicalBatch`, `ReplacementSemantics`) |
| `fetch.py` | `fetch_unit` (httpx 3-try / operator_staged) + `CacheKey` + `FetchedCache` dedup |
| `state.py` | committed year-checkpoint read/write/compare + raw-hash skip predicate + resume |
| `enrich_gates.py` | the six India-discontinuity ENRICH gates |
| `divergence.py` | the UPSERT-seam divergence gate |
| `splice_guard.py` | the mid-series splice break-row gate |
| `run_pipeline.py` | the shared SINGLE-SERIES publish pipeline (3 callers; faceted is separate) |
| `cli.py` | the `ingest run` / `status` / `clean` sub-app |
| `paths.py` | the single path-emit seam |
| `cleanup.py` | `ingest clean` target resolution (refuses any target outside `.runtime/`) |

`run_pipeline` ([run_pipeline.py](../../../backend/yen_gov/canonical/ingest/run_pipeline.py)) factors the common one-series-per-file publish flow shared by the three single-series callers - `rbi_handbook` (full-workbook `replace`), the `rbi_hbs_health` cohort (per-year `upsert`), and the greenfield `niti_sdg_index` adapter. The faceted `yen_gov.sources.iced_power.ingest_pipeline` (per-fuel / per-sector dimension columns) is a SEPARATE strategy and is deliberately NOT folded in.

## Design rationale

Keep-receipts for the binding decisions (the ADR tier is retired; rationale lives here per [ADR-0034](../../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract)). Each is decision / why.

### D1 - automated fetch reintroduced (local pipeline only)

**Decision.** The ingest pipeline fetches over the network with `httpx` (a bounded 3-try loop, no `tenacity`), reversing the earlier "no network fetcher" rule that the long-format-CSV rip had asserted.

**Why.** The rip deleted the OLD fetch stack (`core/http.py`, the ECI Fetcher) because it coupled production runtime to the network. The constraint it was protecting is unchanged: Holy Law #1 (production is a static GitHub Pages bundle) and Holy Law #2 (backend = local pipeline only). Automated fetch lives ONLY in the local backend pipeline; production never fetches; CI consumes committed CSV and never fetches. So "no network fetcher in production" still holds, while the LOCAL pipeline regains the autonomy to pull a revised year on its own. The `operator_staged` fetch mode is the flaky-TLS fallback (read a locally-staged raw payload), and is what every test uses so no test ever touches the live network.

### D2 - ICED is not a `producer`

**Decision.** Where NITI Aayog ICED is a pure passthrough of an upstream issuing authority (CEA / MoSPI / MoEFCC), the `producer` becomes that authority and ICED moves into `title`; where ICED ORIGINATES a derived analytic, the producer stays `"NITI Aayog ICED"`. This is decided PER ENDPOINT on cited evidence (the tracing table at [docs/research/iced-authority-tracing.md](../../research/iced-authority-tracing.md) + [iced_authority_map.py](../../../backend/yen_gov/canonical/iced_authority_map.py)), never as a blanket sweep.

**Why.** A `producer` is the organisation that MEASURED the fact; baking "ICED" as producer where ICED merely re-published CEA's number is a provenance lie. Correcting it re-mints the affected `source_id`s (the citation triple changes) and never changes any `indicator_id` (identity is what is measured, not who re-published it). The evidence gate is why this is not a 31-row mechanical sweep: only endpoints with cited passthrough evidence are reattributed.

### D3 - pydantic mandatory at in-process boundaries

**Decision.** Every IN-PROCESS boundary type is pydantic: the 3 stage messages, the 11 log events, and `SourceSpec`/`IndicatorSpec`. The 11 events keep a HAND-ROLLED serializer (iterate `model_fields`, route `Path` through the path util, emit `Z`) because `model_dump(mode="json")` serialises `Path` via `str()` (a backslash on Windows) and a `datetime` as `+00:00` not `Z`, which would break the POSIX-path + `Z`-timestamp log contract.

**Why.** One typed model at every boundary catches a malformed hop at construction, where the producing filter still has the context to explain it. FOUR DATA-contract seams stay deliberately non-pydantic, because they are JSON/CSV artifacts validated by their own schema, not in-process Python types: (1) `columns.json` + `csv_validator`; (2) `derive_source_id`; (3) the JSON-Schema / `x-version` / `_ops` / `manifest.json` artifacts (the year-checkpoint is one of these); (4) the DuckDB-WASM read seam. Forcing pydantic onto those would duplicate a contract that already lives in the schema.

### D4 - committed year-checkpoint + resume

**Decision.** A committed per-adapter checkpoint records each completed year and the hash of its raw fetched payload. A re-run skips years whose raw hash is unchanged; a revised old year (its hash changed) re-opens; a run that failed partway is resumable.

**Why.** The pipeline runs autonomously, and both the agent and the upstream site can fail mid-run, so a run MUST resume rather than restart from clean. The raw-hash key is what lets a revised year re-open honestly (the upstream bytes changed) while a byte-identical re-fetch skips (no work to redo). The checkpoint is committed (not in `.runtime/`) because the delta decision must survive a `clean` and be auditable in git history.

## Rejected alternatives

- **A top-level `ingest/` home, or the "Lift" name.** Rejected: the engine is a sibling to `canonical/adapters/` with one `engine -> adapters` import arrow, so it belongs under `canonical/ingest/`; a sixth top-level ingest home and the "Lift" brand both add vocabulary without adding structure. (The retired "Lift" pipeline name + the `lift-<family>` CLI were removed in the rip.)
- **Source-primary CLI (`--source`).** Rejected: agents and humans think in indicators, and `--source` collides with the `source_id` citation noun. `--indicator` is primary; `--adapter` is the precise scope filter.
- **A fourth "Discover" stage / stage subcommands.** Rejected: the non-emitting spec-validate + checkpoint-diff is `run`'s preamble, not a pipe stage, and a verb-plus-a-flag for one act is two grammars. The verbs are `run` / `status` / `clean` (+ the existing `pre-flight-ingest`); no `list` / `explain` / `discover` / `rollback` / `inventory`.
- **A `splice` verb / emergent splice with no forced break.** Rejected: an emergent splice without a forced break-row ships a smooth line across a methodology seam - a lie. The break-row precondition IS the affordance.
- **Precedence-only at the UPSERT seam (no divergence gate).** Rejected: silent last-writer-wins hides publisher disagreement behind whichever source ran last.
- **Re-run-from-clean only (no checkpoint).** Rejected: an autonomous pipeline whose agent or upstream fails mid-run must resume, and a raw-hash key is what re-opens revised years.
- **Extract `run_pipeline` at the first caller / fold the faceted strategy in.** Rejected: `run_pipeline` is extracted at the THIRD single-series caller (rule-of-three), and the faceted `iced_power.ingest_pipeline` is a genuinely different shape (dimension columns) that stays separate.
- **A blanket CEA producer sweep for ICED.** Rejected: a blanket sweep bakes a provenance lie at every endpoint where ICED actually originates the analytic; reattribution is evidence-gated per endpoint.
- **Manifest extract-then-preserve.** Rejected: `manifest.json` is already `tables: []` and the Parquet-scanning generator was dead, so the manifest is a REPLACE - `emit_manifest()` is a ~15-line version stamp + the `deprecations` ledger, no scan (see [manifest.py](../../../backend/yen_gov/canonical/manifest.py)).

## See also

- [docs/reference/cli-ingest.md](../../reference/cli-ingest.md) - the `ingest run` / `status` / `clean` + `pre-flight-ingest` CLI reference.
- [docs/concepts/ingest-fetch-enrich-separation.md](../../concepts/ingest-fetch-enrich-separation.md) - the three-stage doctrine.
- [docs/how-to/add-a-new-data-source.md](../../how-to/add-a-new-data-source.md) - the operator cookbook (NITI SDG India Index worked example).
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) - the citation-ledger rules the Publish stage upserts into.
- [docs/concepts/indicator-naming.md](../../concepts/indicator-naming.md) - `<measure>-<unit>-<facet>`, grain on the row not the id.
- [docs/architecture/backend/preflight.md](../backend/preflight.md) - the author-time `pre-flight-ingest` gate ([ADR-0046](../backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)).
- [docs/reference/decision-index.md](../../reference/decision-index.md) - the D1-D4 redirect rows.
- [TODO/20260618-backend-ingest-pipeline-rip-replace-plan.md](../../../TODO/20260618-backend-ingest-pipeline-rip-replace-plan.md) - the plan this subsystem distils.

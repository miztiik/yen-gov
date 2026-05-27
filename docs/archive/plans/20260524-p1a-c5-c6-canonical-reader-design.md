# P.1.A C5+C6 — Canonical reader switch + legacy shard retire (planning)

**Last Updated**: 2026-05-24 (Path A chosen)
**Status**: 🛑 DESIGN-PAUSED — retire-list invalidated by pre-implementation audit. **Path A CHOSEN 2026-05-24**: retire 8 SAFE shards in a near-term PR; defer 8 unsafe into 4 follow-up lift PRs scheduled at [`20260524-p1a-data-reacquisition-plan.md`](20260524-p1a-data-reacquisition-plan.md). The C5+C6 design Q1-Q6 verdicts below stay STALE — once all 8 deferred shards are no longer deferred (after C4.5 / C4.6 / C4.7 / C4.8 land), C5+C6 reopens as the final full-reader-switch + final-retire-pass commit. Until then, the Path A retire PR ships C5 reader infrastructure with a path-router that handles the 8 retired paths + falls through to legacy for the 8 deferred. Audit details: [20260524-p1a-c5-retire-list-audit-findings.md](20260524-p1a-c5-retire-list-audit-findings.md).

Original status (pre-audit): ◻ DESIGN-OPEN. Authoring Q1–Q6 below. C5+C6 is the FINAL P.1.A step; ships as ONE fused-atomic commit per CLAUDE.md §15 + Holy Law #4. Blocks the ~16-shard energy-family retire-list scrub.
**Doc class**: plan-doc per [ADR-0034](../../architecture/decisions/0034-documentation-routing-contract.md) — status + design decisions + sub-PR shape + Tier-A/B test plan. No executed-work narrative.
**Cites**: [P.1 energy pivot](20260522-phase-2-p1-energy-pivot.md) §3 verdicts + §4 P.1.A pre-flight checklist (7/8 flipped on origin/main `056a995d` as of 2026-05-24; remaining §2b ships INSIDE this commit) + [canonical-store.md §2b](../../architecture/data/canonical-store.md) + [ADR-0030](../../architecture/decisions/0030-canonical-store-duckdb-wasm.md) (D5/D11/D22/D26/D29/D33.8) + [ADR-0032](../../architecture/decisions/0032-sources-citation-ledger.md) (sources v2.0) + [frontend/src/lib/indicators.ts](../frontend/src/lib/indicators.ts) (legacy `IndicatorArtifact` shape, line 310; `fetchIndicator()`, line 328) + [frontend/src/lib/canonical/duckdb.ts](../frontend/src/lib/canonical/duckdb.ts) (WASM seam) + [frontend/src/lib/indicator-catalogue.ts](../frontend/src/lib/indicator-catalogue.ts) (catalogue reader, PR #107 v1.1).

---

## §1. Scope

Two deliverables, ONE commit:

- **C5 — Canonical reader-switch**: ship `frontend/src/lib/canonical/indicator-reader.ts` exposing `fetchIndicatorFromCanonical(canonicalId)` that reconstructs a legacy-shaped `IndicatorArtifact` (`frontend/src/lib/indicators.ts:310`) from the 4 canonical Parquets (`taxonomy/indicators.parquet`, `taxonomy/sources.parquet`, `taxonomy/methodology_breaks.parquet`, `energy/<fact-table>.parquet`) via DuckDB-WASM (`canonical/duckdb.ts`). Wire it as an interceptor at the existing `fetchIndicator(path)` seam (`indicators.ts:328`) so the **7 consumer call-sites** do not change.
- **C6 — Legacy shard retire**: `git rm` 16 P.1.A-consumed shards from `datasets/indicators/in/energy/`; scrub the 16 matching entries from `datasets/_ops/meadow-shard-contract.txt`; amend `docs/architecture/data/canonical-store.md` §2b (3→5 fact-tables + new Rule #4 per [P.1 plan-doc §2 Q-b verdict](20260522-phase-2-p1-energy-pivot.md)); migrate the 1 vitest fixture that reads a retired shard via `fs.readFileSync`.

Same commit per Holy Law #4 — citizen-surface atomic-revert preserved. Mid-step states are illegal: (a) retire without reader = 404s in production, (b) reader without retire = dead code + Tier-B allowlist drift, (c) §2b amend without code = doc lies about reality.

## §2. Authority routing (CLAUDE.md §0a)

| Decision | Authority | Why |
| --- | --- | --- |
| Reconstruction shape (which `IndicatorArtifact` fields are recoverable, which need defaults) | Hans + Max | Citizen-surface field set + cross-publisher precedent (OWID `.csv` reconstruction pattern) |
| Read-seam contract (interceptor vs new function vs config) | Gregor | Public-API stability of the existing `fetchIndicator(path)` signature consumed by 7 components + 1 vitest |
| Legacy-shard retirement discipline (atomic with reader, allowlist scrub, fixture-snapshot pattern) | Fowler | Strangler-fig step "phase B" hygiene per /memories/lessons.md 2026-05-21 T.0c |
| §2b amend exact wording for Rule #4 | Gregor | Already drafted in [P.1 plan-doc §2](20260522-phase-2-p1-energy-pivot.md); ratified at commit time |
| Citizen voice on "this indicator was permanently retired" error text (for the 4 hard-dropped composer paths) | Hans + Jony | Citizen reading an archived embed / shared link should see a useful redirect, not a stack trace |

No new persona invocation required; all 5 routes have prior locks. Plan-doc §3 verdicts (Q-a/b/c/d/e) bind the design.

## §3. Design decisions (Q1–Q6)

### Q1. Reconstruction shape — strict-equivalence OR adapted?

**Verdict (Hans + Max + Gregor)**: STRICT structural equivalence to `IndicatorArtifact` (`indicators.ts:310`), with three documented field defaults for canonical fields that the lift dropped:

| Legacy field | Recoverable from canonical? | Strategy |
| --- | --- | --- |
| `$schema`, `$schema_version` | NO | Hardcode to legacy v2.0 strings so consumer Zod-style validation passes |
| `sources[]` | YES via `source_id` JOIN | `SELECT DISTINCT source_id FROM <fact-table> WHERE indicator_id=?` → JOIN `taxonomy/sources.parquet` → map to `IndicatorSource{url, fetched_at, name, authority}` |
| `license` (object) | PARTIAL | Default `{license_id: "CC-BY-4.0", license_url: "...", attribution: "..."}` per yen-gov standard; catalogue does not carry per-indicator licence today (P.1.A scope) |
| `coverage` (block: `start_period`, `end_period`, `entities_observed`) | YES via aggregation | `SELECT MIN(period_label), MAX(period_label), COUNT(DISTINCT entity_id) FROM <fact-table> WHERE indicator_id=?` |
| `indicator` (IndicatorMeta — ~25 fields) | YES via catalogue JOIN | Catalogue row v1.1 carries label_short, label_long, description_short, description_long, unit, cadence, family, pillar, topic_tags, value_kind, direction, attribution_geography, comparability, implementing_authority, dimension_values; missing legacy fields (`renderer_rule_slug`, `documentation_status`, `methodology_breaks`, `known_caveats`, `notes`, `chart_defaults`) reconstruct from defaults or downstream JOINs |
| `rows[]` | YES (1-1) | `entity_id` → `entity_id`, `period_label` → `time`, `value_numeric` → `value`, `period_label` → `period_label`; `facet` derived from catalogue `dimension_values` (NOT from fact-table — see Q2) |
| `series_spec` (v2.0+) | NO | Hardcode `{description: ""}`; the v2.0 field is a renderer-hint, not a data-shape requirement |
| `methodology.methodology_breaks[]` | YES via JOIN | `SELECT * FROM taxonomy/methodology_breaks.parquet WHERE methodology_version IN (catalogue.methodology_break_ids)` |
| `methodology.documentation_status`, `known_caveats`, `notes`, `editor_note_md`, `policy_context` | NO | Default to `"partial"` / `[]` / `[]` / `null` / `[]`; canonical store dropped these prose fields per ADR-0030 D11 (prose belongs in concept-docs, not data) |
| `methodology.publisher` | YES via catalogue JOIN | First source row's `producer` |
| `divergence` | NO | Hardcode `null` (already a reserved-for-future field) |

Strict-equivalence rejected alternatives (do NOT re-propose):
- **(a) Leaner `ReducedIndicatorArtifact` type**: would force every consumer (StackedTrendArtifact, IndicatorChoropleth, IndicatorRanked, IndicatorSmallMultiples, IndicatorCard, Home, adapter-indicator) to gain a conditional code path. Multiplies blast radius from 1 file (reader) to 7+ files.
- **(b) Adapt the legacy `IndicatorArtifact` type to drop fields**: same problem, plus breaks the legacy-shard contract test (`indicator.schema.json` v1.5 + adapter-indicator's `IndicatorDoc` type imports `IndicatorArtifact`).
- **(c) Add the missing fields to the canonical catalogue**: violates ADR-0030 D11 (canonical store is data; prose lives elsewhere). Re-creates the per-shard prose smear that ADR-0032 just fixed for `sources`.

### Q2. Source-of-truth Parquets + JOIN topology

**Verdict (Gregor)**: 4 reads per reconstruction call, parallelisable:

1. **`datasets/taxonomy/indicators.parquet`** — catalogue row (1 query, cacheable across calls). Returns: label_short/long, description_short/long, unit, cadence, family, pillar, value_kind, direction, attribution_geography, comparability, implementing_authority, parent_indicator_id, dimension_values, methodology_version, methodology_break_ids, source_id (default), renderer_rules.
2. **`datasets/energy/<fact-table>.parquet`** — observation rows (1 query). Fact-table chosen via `INDICATOR_TO_FACT_TABLE: Record<canonicalId, "energy_installed_capacity"|"energy_generation"|"energy_distribution_performance"|"energy_demand_supply">` map (hand-curated, 16 entries; sourced from P.1 plan-doc §2 table). Returns: entity_id, period_label, value_numeric, source_id, derivation.
3. **`datasets/taxonomy/sources.parquet`** — source rows for the DISTINCT source_id set produced by step 2 (1 query with `IN (...)` clause).
4. **`datasets/taxonomy/methodology_breaks.parquet`** — break rows matching `catalogue.methodology_break_ids` (1 query with `IN (...)` clause; skipped when the list is empty).

`facet` field on each `IndicatorRow` derives from **catalogue lookup**, not fact-table column. The fact-table's `indicator_id` encodes the facet (e.g., `national-installed-capacity-mw-coal` → parent `national-installed-capacity-mw`, facet `{fuel_type: "coal"}`). The reader resolves the parent_indicator_id chain ONCE, then maps every observation row's value to the same facet dict (because all rows in a child-id query share the same facet).

The catalogue's `dimension_values` is the source-of-truth for the facet dict. Rejected: parsing the facet from the indicator_id suffix string at runtime (works for `-coal`, breaks for `-solar_rooftop`; structural fragility unacceptable for a contract surface).

### Q3. Folded-blocks fields that don't exist on canonical store

**Verdict (Hans)**: hardcoded sensible defaults; the canonical store deliberately dropped these per ADR-0030 D11.

- `series_spec.description` → `""` (renderer treats empty as "use legacy auto-description fallback")
- `methodology.documentation_status` → `"partial"` (true statement; full methodology lives in the source URL on `taxonomy/sources.parquet`)
- `methodology.known_caveats: []`, `methodology.notes: []`, `methodology.policy_context: []` — empty arrays. The B4 UDAY policy framing lives in `notes` today; lifting it to a `policy_events.json` overlay is queued for Phase 3 (§3.1 #3 of P.1 plan-doc). Until then, the legacy shards' prose is the artefact; once retired, the prose is in the methodology source URL.
- `methodology.editor_note_md` → `null`. Editor notes are operator-only metadata not surfaced to citizens.
- `methodology.related_indicators` → `[]`. The catalogue's `parent_indicator_id` chain is the new authoring surface for relatedness; this list will reconstruct from parent + sibling children of the same parent (P.1.B/C scope).
- `methodology.chart_defaults` → `{}`. Chart defaults migrate to the catalogue's `renderer_rules` array (already on disk per v1.1).
- `divergence` → `null` (reserved-for-future today, unchanged).

The legacy `coverage` block (`start_period`, `end_period`, `entities_observed`) IS recoverable via aggregation per Q1 table — NOT a folded-block dropper. Same for `sources[]` (recoverable via JOIN).

### Q4. Exact 16-shard retire list

From P.1 plan-doc §4 + §6 + on-disk grep of `datasets/indicators/in/energy/`:

**9 hard drops (no canonical replacement; §6 table)**:
1. `installed_mw_by_state.json` — community-curated GeoJSON, 4 of 35 states; Holy Law #9 fail
2. `state_peak_electricity_demand_mw.json` — ICED 1-year snapshot; subset of canonical
3. `state_electricity_peak_demand_mw.json` — ICED 9-year tail; reconciled into canonical
4. `state_electricity_generation_mu.json` — MU = GWh alias; lives as `id_aliases[]` on canonical row
5. `installed_capacity_total_mw.json` — D33.8 aggregate; compute-on-read
6. `installed_capacity_thermal_mw.json` — D33.8 aggregate; compute-on-read
7. `installed_capacity_by_source_mw.json` — composer (pipeline UNION); writer rebuilds at emit
8. `state_installed_capacity_total_mw.json` — D33.8 aggregate; FY04-14 spliced into `_allocated_mw`
9. `state_installed_capacity_with_alloc_mw.json` — total-row of `_allocated_mw`

**7 reader-replaceable (legacy shard → canonical indicator_id; reconstruction via Q1+Q2)**:
10. `installed_capacity_coal_mw.json` → `national-installed-capacity-mw-coal`
11. `installed_capacity_gas_mw.json` → `national-installed-capacity-mw-gas`
12. `installed_capacity_hydro_mw.json` → `national-installed-capacity-mw-hydro`
13. `installed_capacity_nuclear_mw.json` → `national-installed-capacity-mw-nuclear`
14. `installed_capacity_renewable_mw.json` → `national-installed-capacity-mw-renewable`
15. `state_installed_capacity_geographical_mw.json` → `state-installed-capacity-geographical-mw` (+ facet children for fuel breakdown)
16. `state_installed_capacity_by_source_mw.json` → `state-installed-capacity-geographical-mw-<fuel>` (facet view of #15)

Hard-drop paths gain a HARD-DROP entry in the path-routing map that throws a typed `IndicatorRetiredError` with citizen-readable text (Hans authority, Jony co-sign): *"This indicator was permanently retired in May 2026 because <reason>. The current equivalent is `<canonical id or compute-on-read instruction>`. See [P.1 plan-doc §6](docs/archive/plans/20260522-phase-2-p1-energy-pivot.md) for the full retire rationale."*

Replaceable paths route through `fetchIndicatorFromCanonical(canonicalId)` transparently.

**Counter-check**: every retired path MUST appear in the current `datasets/_ops/meadow-shard-contract.txt` allowlist. Verified via `Get-Content datasets\_ops\meadow-shard-contract.txt | Select-String -SimpleMatch energy` returning 41 hits; the 16 retired files are a strict subset.

### Q5. Tier-B allowlist atomic-removal

**Verdict (Fowler)**: same commit removes 16 entries from `datasets/_ops/meadow-shard-contract.txt`. The Tier-B `tier_b_meadow_shard_contract` validator (`backend/yen_gov/validate.py`) enforces (a) every allowlist entry has a matching file on disk (no orphans), (b) every file under `datasets/indicators/in/energy/` is allowlisted (no rogues). Removing both the file AND the allowlist entry in the SAME commit keeps both invariants green.

Pattern verified against `/memories/lessons.md` 2026-05-22 PR1 (allowlist-based forbidden-path fence): retirement = `git rm` + allowlist scrub in one go; never one without the other.

### Q6. `canonical-store.md` §2b amend — exact diff text

**Verdict (Gregor — already drafted in [P.1 plan-doc §2](20260522-phase-2-p1-energy-pivot.md))**:

Add to §2b table:
| Family | Fact-tables | Notes |
| `energy` (extends from 3 → 5) | `energy_installed_capacity`, `energy_generation`, `energy_distribution_performance`, **`energy_demand_supply`** (new), **`energy_fuel_consumption`** (new) | Per P.1.A 2026-05-24 |

Add Rule #4 below Rule #3:
> **Rule #4 (Gregor 2026-05-22, ratified P.1.A 2026-05-24)**: A new fact-table within a family is justified when (a) the citizen question is distinct AND (b) co-locating would force every chart on the smaller-question to scan unrelated indicator rows, OR (c) the FK-graph diverges (different `dim_*` joins). Same row-shape across files is expected, not a smell — `indicator_id` is the within-file discriminator (D5).

Update the §2b "Currently locked families" enumeration to reflect 5 energy fact-tables.

## §4. Test plan (Tier-A + Tier-B per CLAUDE.md §15)

| Gate | Test | Pass criterion |
| --- | --- | --- |
| Tier-A vitest | `frontend/src/lib/canonical/indicator-reader.test.ts` — new unit tests | Build the reconstruction shape; mock `queryParquet` to assert (a) IndicatorArtifact field shape matches legacy `IndicatorArtifact` interface exactly, (b) `rows[]` ordering matches `(year, period_seq, entity_id)`, (c) hard-drop paths throw `IndicatorRetiredError` with citizen text, (d) replaceable paths route to canonical |
| Tier-A vitest fixture migration | `frontend/src/lib/charts/stacked-trend/adapter-indicator.test.ts` — rewrite from `readFileSync(installed_capacity_by_source_mw.json)` to `readFileSync(__fixtures__/installed_capacity_by_source_mw.snapshot.json)` | Capture the artifact as a frozen JSON snapshot at commit time (`tools/snapshot_energy_artifact.py`); test asserts adapter logic against the snapshot; future canonical changes don't drift the adapter test |
| Tier-A vitest contract | Existing `frontend/src/contracts/datasets-conform.test.ts` | After `git rm`, the 16 deleted shards disappear from the contract test's discovered file set; remaining 25 energy shards continue to validate |
| Tier-A backend pytest | Existing `backend/tests/test_legacy_folded_indicator_shards_tier_b.py` | After allowlist scrub, the validator finds 0 orphans + 0 rogues for the energy family |
| Tier-A backend pytest | New `backend/tests/test_canonical_indicator_reader_parity.py` | For each of the 7 reader-replaceable paths, query the canonical Parquet directly via duckdb-py and assert: (rowcount matches the pre-retire shard's `rows[]` length) AND (sample 5 (entity, time, value) tuples match byte-for-byte) |
| Tier-B | `python -m yen_gov validate --root .` | Clean — no schema violations, no Tier-B forbidden-path matches on the meadow-shard-contract allowlist after scrub |
| §13 browser smoke | Playwright: `/` home + `/topic/energy` + `/state/IN-S22` (Tamil Nadu, energy-heavy producer) + `/state/IN-S04` (Bihar, AT&C-loss DISCOM story) | Per-route: 0 console errors, 0 network 404s on `datasets/indicators/in/energy/*.json`, ≥1 canonical-parquet read in the network trace, screenshots match pre-commit baseline on the energy stacked-trend visual |

**Golden-file diff strategy (Fowler — strangler-fig "phase B" rigour per /memories/lessons.md 2026-05-22 G.1.b)**: BEFORE staging the retire, snapshot each of the 16 retired `*.json` files to `.c5-baseline/`. AFTER `fetchIndicator(path)` is wired through the canonical reader, run the in-browser reader for each replaceable path AND emit a serialised `IndicatorArtifact` via the test harness, diff against `.c5-baseline/<file>.json`. Acceptable diffs: any field listed in Q1 column "default / NO". Unacceptable diffs: `rows[]` content, `indicator.label_long`, `sources[].url`, `methodology.methodology_breaks[].kind`. `.c5-baseline/` is a `.gitignore`-style work-artifact directory — DELETE before staging per CLAUDE.md §8.

This pattern is STRONGER than parity-oracle alone because it asserts byte-for-byte preservation of the citizen-surface portions of the artifact, not just rowcount equivalence.

## §5. Sub-PR shape — single fused-atomic commit

| File | Action | Why same-commit |
| --- | --- | --- |
| `frontend/src/lib/canonical/indicator-reader.ts` (new, ~250 LOC) | CREATE | The canonical reader; entry point for `fetchIndicatorFromCanonical()` |
| `frontend/src/lib/canonical/indicator-reader.test.ts` (new, ~200 LOC) | CREATE | Tier-A unit tests for the new reader; paired-test discipline per CLAUDE.md §15 |
| `frontend/src/lib/canonical/legacy-path-map.ts` (new, ~80 LOC) | CREATE | `LEGACY_PATH_TO_CANONICAL_ID: Record<string, string \| RetiredMarker>` — 16-entry map, hand-curated from §4 above |
| `frontend/src/lib/indicators.ts` | EDIT | Inside `fetchIndicator(path)`: lookup `LEGACY_PATH_TO_CANONICAL_ID[path]`. If marker = "RETIRED" → throw `IndicatorRetiredError`. If marker = canonical id → delegate to `fetchIndicatorFromCanonical(id)`. Otherwise → existing JSON fetch path (still active for the 25 non-retired energy shards + ~100 other family shards) |
| `frontend/src/lib/charts/stacked-trend/__fixtures__/installed_capacity_by_source_mw.snapshot.json` (new) | CREATE | Frozen snapshot of the retired artifact, so adapter-indicator.test.ts keeps testing real shape |
| `frontend/src/lib/charts/stacked-trend/adapter-indicator.test.ts` | EDIT | Switch `readFileSync` source from `datasets/indicators/in/...` to `__fixtures__/...snapshot.json`; identical assertion body |
| `datasets/indicators/in/energy/<16 files>.json` | DELETE (`git rm`) | The retire |
| `datasets/_ops/meadow-shard-contract.txt` | EDIT | Remove the 16 corresponding lines |
| `docs/architecture/data/canonical-store.md` | EDIT | §2b: bump energy from 3 to 5 fact-tables; add Rule #4 wording per Q6 |
| `docs/archive/plans/20260522-phase-2-p1-energy-pivot.md` | EDIT | Flip §4 final unchecked item `[ ] canonical-store.md §2b amended` → `[x]`; update status banner to mark P.1.A DONE |
| `tools/snapshot_energy_artifact.py` (new, ~30 LOC) | CREATE | One-shot snapshot script for the adapter-indicator fixture migration (kept for future fixture refreshes; usable on other families' adapter-tests) |

Estimated diff: ~10 files modified, ~6 new, ~20 deleted (16 shards + work-artifact cleanup). Net LOC: ~+600 / −2000 (the 16 shards are the bulk of the deletions, each ~80–200 lines).

## §6. Risk + mitigation

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Reconstruction shape drifts from legacy → consumer breakage | Medium | Q4 golden-file diff gate catches; vitest type-check catches structural drift |
| DuckDB-WASM cold-start latency on first call | Medium | `canonical/duckdb.ts` lazy init is already shipped (PR #107); first call pays ~1s WASM bundle; cached thereafter. No regression vs `fetchIndicator(path)` (which pays ~200ms HTTP per call) |
| Catalogue cache invalidation on parquet update | Low | Manifest-based revalidation (`canonical/manifest.ts:79` already does `lookupTable` with schema-version compat check). New parquet version → manifest bump → reader re-reads. Out-of-band cache invalidation not in scope |
| Source row missing for an indicator (FK violation) | Low | `source_id` is NOT NULL on canonical fact-tables (verified on disk: all 5449 rows across 4 fact-tables have non-null source_id). Reader treats missing source as a hard error, not a silent default |
| `adapter-indicator.test.ts` fixture goes stale vs canonical | Low | The fixture is a SNAPSHOT — it's deliberately frozen. Adapter logic is what's under test, not data freshness. If canonical parquet schema changes shape, snapshot needs refresh; flagged via the new `tools/snapshot_energy_artifact.py` (one-line invocation refreshes it) |
| Hard-drop error text shows stack trace, not Hans's citizen text | Low | `IndicatorRetiredError` is a custom Error subclass with a `.citizenMessage` property; every consumer (IndicatorCard, etc.) catches via existing `try/catch` and surfaces `.citizenMessage` via `<FailureState>` (already shipped) |
| §2b amend wording diverges from Q6 verbatim | Low | Plan-doc §2 has Gregor's drafted text; this PR pastes verbatim |

## §7. Rejected alternatives

| Option | Why rejected |
| --- | --- |
| **Ship C5 (reader) WITHOUT C6 (retire)** — additive-only | Citizen-surface unchanged; tests pass; allowlist drifts (canonical reader exists, legacy files exist, Tier-B passes vacuously). Leaves dead code in production with no forcing function to scrub it. Violates Fowler "no zombie code paths". |
| **Ship C6 (retire) WITHOUT C5 (reader)** — destructive-only | All 7 consumer call-sites break on the 16 retired paths (network 404, `.json` parse fail, Zod validation fail). Citizen sees broken charts. Violates Holy Law #4 atomic-revert. |
| **Ship C5+C6 as TWO commits behind a feature flag** | Doubles review surface + adds runtime branch + leaves a "flag flip" task forever. The strangler-fig "phase B" doesn't earn a flag — the reader is structurally complete or it isn't |
| **Add `series_spec`, `license`, `documentation_status` to the canonical catalogue v1.2** | Violates ADR-0030 D11 (canonical store is data; prose lives elsewhere). Re-creates the per-shard prose smear ADR-0032 fixed for sources. Defer to a Phase 3 catalogue-v1.2 bump if a real consumer surfaces |
| **Build a separate `ReducedIndicatorArtifact` type for canonical-backed indicators; keep `IndicatorArtifact` for the legacy long-tail** | Forces every consumer to gain `if (artifact.kind === "reduced") ... else ...` conditional. Multiplies blast radius 7×. Type-system cost outweighs the modest saved fields |
| **Parse the facet from `indicator_id` string suffix at runtime** | Works for `-coal` but breaks for `-solar_rooftop`, `-small_hydro`, `-waste_to_energy`. Structurally fragile. Use catalogue `dimension_values` (which is THE source-of-truth for the facet dict) |
| **Defer C5+C6 to Phase 3; ship P.1.B/C against legacy reader** | Compounds the retire-debt; the canonical store grows additively while the legacy long-tail never shrinks. C5 is the strangler's "phase B" and MUST close before P.1.B opens, or P.1.B authoring contradicts itself (writes canonical, reads legacy) |
| **Use a separate vitest fixture per retired shard** (not just the one adapter-indicator depends on) | Over-engineering; only adapter-indicator.test.ts reads a retired shard via `fs.readFileSync`. The other 6 consumers read via `fetchIndicator(path)` which IS intercepted. One fixture file is sufficient |
| **Migrate the 7 consumer call-sites to `fetchIndicatorFromCanonical(id)` directly; deprecate `fetchIndicator(path)`** | Multiplies blast radius. The path-string seam is stable and well-understood; intercepting inside `fetchIndicator()` is the minimum-blast-radius pattern per /memories/lessons.md 2026-05-21 G.1.c |

## §8. Sequence + handoff

1. **(this PR — Level-2 doc-only, ~290 lines)**: ship this planning doc; flip plan-doc status banner reference to point here; no code change.
2. **Next PR — C5+C6 fused-atomic** per §5 file list; runs all Tier-A + Tier-B + Playwright + golden-file gates; merges via `gh pr merge --squash --delete-branch`.
3. **After merge — P.1.B opens** from main with the strangler-fig phase A pattern (additive canonical writer for DISCOM + per-capita-availability + total-MW splice) per [P.1 plan-doc §4](20260522-phase-2-p1-energy-pivot.md) row P.1.B. C5 reader already supports new indicator_ids transparently via catalogue lookup; no new reader work needed for P.1.B.

## §9. Cross-refs

- [P.1 energy pivot plan-doc](20260522-phase-2-p1-energy-pivot.md) — §2 family decomposition, §3 design verdicts, §4 PR breakdown + pre-flight checklist, §6 hard-drop table, §8 strangler-fig pattern
- [canonical-store.md §2b](../../architecture/data/canonical-store.md) — the rule this PR amends
- [ADR-0030 D11 / D26 / D29 / D33.8](../../architecture/decisions/0030-canonical-store-duckdb-wasm.md) — canonical store as data-only + atomic-fuel + compute-on-read
- [ADR-0032](../../architecture/decisions/0032-sources-citation-ledger.md) — sources v2.0 (this PR consumes `taxonomy/sources.parquet` for reconstruction)
- [ADR-0034](../../architecture/decisions/0034-documentation-routing-contract.md) — doc class for this plan-doc
- [frontend/src/lib/indicators.ts](../frontend/src/lib/indicators.ts) — legacy `IndicatorArtifact` shape (line 310) + `fetchIndicator()` (line 328)
- [frontend/src/lib/canonical/duckdb.ts](../frontend/src/lib/canonical/duckdb.ts) — DuckDB-WASM seam (`queryParquet`, line 41)
- [frontend/src/lib/canonical/manifest.ts](../frontend/src/lib/canonical/manifest.ts) — manifest discovery + schema-version compat
- [frontend/src/lib/indicator-catalogue.ts](../frontend/src/lib/indicator-catalogue.ts) — catalogue Zod reader (PR #107 v1.1)
- [G.1.b lesson (2026-05-22)](/memories/lessons.md) — golden-file byte-equality gate for strangler-fig phase B
- [G.1.c lesson (2026-05-22)](/memories/lessons.md) — frontend-consumer audit + field-name adapter at data-loader seam
- [PR #87 lesson (2026-05-22)](/memories/lessons.md) — Tier-B allowlist-based forbidden-path fence

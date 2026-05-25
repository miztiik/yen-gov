# P.1.A data re-acquisition plan — 9 deferred / lost shards under Path A

**Last Updated**: 2026-05-24
**Status**: NEW — Path A of the [C5+C6 retire-list audit](20260524-p1a-c5-retire-list-audit-findings.md) is **CHOSEN**. Path A retires the 8 SAFE shards in a near-term PR but DEFERS 8 unsafe shards because canonical does not yet carry their data. Plus 1 SAFE-retired shard (`state_peak_electricity_demand_mw.json`) loses its FY25 single-window snapshot. This plan enumerates each missing data item, names the publisher + endpoint, picks the catalogue grammar for the canonical replacement, routes the Hans/Max authority decisions, and orders the lifts into 4 sub-PRs.
**Doc class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md) — status + active PRs + open Qs only; no rejected-alternative archaeology (that lives in the audit doc + the energy pivot plan-doc).
**Authority routing** (CLAUDE.md §0a): Hans + Max for snapshot-vs-time-series identity decisions + tier promotion; Gregor for catalogue / fact-table contract additions; Fowler for per-lift fused-atomic PR shape.
**Cites**: [C5+C6 retire-list audit findings](20260524-p1a-c5-retire-list-audit-findings.md) (the 9-shard list this plan re-sources); [P.1 energy pivot plan-doc](20260522-phase-2-p1-energy-pivot.md) §2 (fact-table decomposition) + §3 Q-c (long-arc splice verdict) + §3 Q-d (tier table) + §3.1 #11 (silver→gold tier promotion); [canonical-store.md §2b](../docs/architecture/data/canonical-store.md); [ADR-0030 D33.8](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) (atomic-fuel + compute-on-read); [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) (sources v2.0 + `derive_source_id`).

---

## §1. Why this plan exists

The C5+C6 audit found that 8 of the 16 shards in the original retire-list cannot safely retire — canonical does not yet carry their data. Path A (chosen) retires the 8 SAFE shards now and defers the 8 unsafe ones into separate lift PRs. This document is the schedule for those lift PRs.

**Two distinct failure modes Path A creates**:

1. **DATA LOST** (1 shard, ~33 rows): `state_peak_electricity_demand_mw.json` is in the SAFE-to-retire list but its single 2025-04 snapshot is one publication window past canonical's 2024-04 tail. Retiring removes 33 state × FY25 peak-demand rows from the citizen surface until a follow-up lift restores them.
2. **DATA DEFERRED ON DISK** (8 shards, ~1190 unique rows): the legacy shards stay on disk and out of the C6 retire pass, but they are unreachable from the canonical-only reader switch the C5 design wants. Until each is lifted, the catalogue and the on-disk shard stay in a known-mismatched state and the Tier-B forbidden-path fence has to grandfather them.

Both modes are temporary. This plan resolves them via 4 follow-up lift PRs.

## §2. The 9 data items at risk

Three publishers, three publication shapes. Inventory of canonical state per `tools/inspect_canonical_energy.py` run 2026-05-24 against `datasets/energy/energy_installed_capacity.parquet` + `energy_generation.parquet` + `energy_demand_supply.parquet`.

### §2.A — CEA Monthly Executive Summary 2026-03 per-state per-fuel (5 shards / 175 rows / NEEDS LIFT)

The five `installed_capacity_{coal,gas,hydro,nuclear,renewable}_mw.json` shards (audit §2.B) hold per-state per-fuel installed capacity for the 2026-03 snapshot from the Central Electricity Authority's Monthly Executive Summary — gold tier, issuing authority for capacity (Q-d table). Canonical already carries the NATIONAL rollup (`national-installed-capacity-mw-{fuel}` × 5 = 5 rows, derivation=`sum`) computed from these shards' per-state sums during the C4 lift (PR #106). The per-state rows are NOT yet in canonical.

| Source | Publisher | Endpoint | Fields needed | Vintage cadence | source_id |
| --- | --- | --- | --- | --- | --- |
| CEA Monthly Executive Summary, IC sheet | Central Electricity Authority, Ministry of Power | https://cea.nic.in/installed-capacity-report/?lang=en | 35-state × 5-fuel installed capacity (MW), end-of-month snapshot. Per-fuel Sub-Total row (State + Private + Central ownership tiers, including allocated shares). | Monthly; current vintage 2026-03 | `src-092a5dc7af3f` (cea_monthly_ic, already in ledger from P.1.A C3) |

**Citizen value**: a "what kind of plants are sited in my state RIGHT NOW" map — distinct from the FY-anchored ICED time series that powers the long-history view. The 2026-03 snapshot is one month newer than ICED's FY25 tail.

### §2.B — RBI Handbook Table 140 long-arc FY05-FY14 (1 shard / 305 rows / NEEDS LIFT)

`state_installed_capacity_total_mw.json` (audit §2.C row 1) holds 712 rows covering FY05-FY25 from the Reserve Bank of India's Handbook of Statistics on Indian States, Table 140 (silver tier per Q-d — RBI is the publisher of the Handbook but CEA is the issuing authority for the underlying numbers). Canonical's `state-installed-capacity-allocated-mw` covers FY15-FY25 only (396 rows / 36 entities). 305 FY05-FY14 rows are NOT in canonical.

This is the long-arc splice the P.1 energy pivot plan-doc §3 Q-c already verdict-locked (Option 1 SPLICE, NULL `fuel_type` for pre-FY15 rows). The lift adapter was conceptually scoped at C4 but C4's actual lift (PR #106) sourced from NITI ICED Capacity Metatable which only carries FY15+. The RBI Handbook XLSX lift is unstarted.

| Source | Publisher | Endpoint | Fields needed | Vintage cadence | source_id |
| --- | --- | --- | --- | --- | --- |
| RBI Handbook of Statistics on Indian States 2024-25, Table 140: State-wise Installed Capacity of Power | Reserve Bank of India (compiled from CEA, MoP) | https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/140T_111220254D8DA0B69B444492B6E9BAF30F3395C8.XLSX (annual; URL changes with publication) | Per-state total installed capacity (MW), end-of-FY, FY05-FY25, single-column-per-FY layout | Annual (vintage FY25 current) | TBD — derive via `derive_source_id("Reserve Bank of India", "Handbook of Statistics on Indian States — Table 140: State-wise Installed Capacity of Power", "2024-25")` |

### §2.C — ICED Capacity Metatable sub-fuel detail (1 shard / 678 rows / DESIGN CALL FIRST)

`state_installed_capacity_by_source_mw.json` (audit §2.C row 2) holds 1815 rows from NITI ICED Capacity Metatable. After D33.8 sub-fuel collapse to the canonical 5 fuels at C4 lift time, 1137 rows persist as `state-installed-capacity-geographical-mw-{fuel}` children. 678 rows are **not lost** — they are summed into the per-fuel children (derivation=`sum` per `_shared.py:SUB_FUEL_TO_CANONICAL`). What IS lost is the **sub-fuel granularity** (large-hydro vs small-hydro; bio-power vs waste-to-energy; wind vs solar-utility vs solar-rooftop), which the 5-bucket axis collapses by design.

This is a Hans+Max design call (Q3 in §5 below), not a missing data item — the rows ARE in canonical via the per-fuel children. The question is whether sub-fuel granularity should be a citizen-surface affordance.

| Source | Publisher | Endpoint | Fields needed | Vintage cadence | source_id |
| --- | --- | --- | --- | --- | --- |
| NITI Aayog ICED Capacity Metatable | NITI Aayog India Climate & Energy Dashboard (compiled from CEA) | https://icedapi.niti.gov.in/v1/capacity-metatable-data | Per-state per-sub-fuel installed capacity (MW), FY15-FY25; 7-9 sub-fuel buckets including `large-hydro`, `small-hydro`, `bio-power`, `wind`, `solar`, `solar-rooftop`, `waste-to-energy` | Annual | `src-ba5c6fa6acfe` (iced_capacity_metatable, already in ledger from P.1.A C3) |

### §2.D — ICED state-wise-deep-dive FY25 single-window (2 shards / ~67 rows / NEEDS LIFT)

Two shards hold the FY25 (period_label `2025-04`) single-window snapshot for peak demand from the ICED state-wise-deep-dive family. Canonical's `state-peak-electricity-demand-mw` and `state-peak-electricity-supplied-mw` both cap at 2024-04 (FY24). Both legacy shards carry FY25 = 33 + 34 unique rows.

| Shard | Endpoint | Rows | Audit verdict |
| --- | --- | --- | --- |
| `state_peak_electricity_demand_mw.json` | https://icedapi.niti.gov.in/energy/powerStatistics | 33 entities × FY25 | ✅ SAFE-retire under Path A; **LOSES FY25** on retire |
| `state_electricity_peak_demand_mw.json` | https://iced.niti.gov.in/analytics/state-wise-deep-dive | 305 rows incl. 34 × FY25 | ⚠️ NEEDS-LIFT before retire; FY13-FY24 already in canonical; FY25 unique |

Both shards point at the same publisher (NITI ICED) and the same indicator family (peak demand met). The lift extends the existing canonical indicators by +1 fiscal year — a small additive lift, no Hans-decision required.

| Source | Publisher | Endpoint | Fields needed | Vintage cadence | source_id |
| --- | --- | --- | --- | --- | --- |
| NITI Aayog ICED state-wise deep-dive | NITI Aayog India Climate & Energy Dashboard (compiled from CEA) | https://iced.niti.gov.in/analytics/state-wise-deep-dive + https://icedapi.niti.gov.in/energy/powerStatistics | Per-state annual peak demand met (MW), per-state peak demand supplied (MW), FY18-FY25 | Annual | `src-be6a6d5d6493` (iced_deep_dive, already in ledger) |

## §3. Sub-PR sequencing

Four follow-up PRs, ordered by reviewability. Each is a fused-atomic per CLAUDE.md §15 (catalogue rows + adapter + retire + Tier-B scrub + §13 smoke in ONE commit).

### P.1.A C4.7 — ICED peak-demand FY25 extension (1 day; ship FIRST)

**Why first**: smallest, no Hans-decision, restores the only Path A DATA-LOST item.

**Phase A status (2026-05-24 — SHIPPED, DESCOPED)**: extended `backend/yen_gov/canonical/adapters/energy/demand_supply.py` with lift block 4 reading FY25-only rows (`r["time"] == "2025-04"`) from `state_electricity_peak_demand_mw.json` (34 entities incl. `IN` national aggregate, value 245 416 MW). Shard 1 (`state_peak_electricity_demand_mw.json`, 33 state rows) is a strict byte-subset of shard 2's FY25 slice and was NOT lifted (would just deduplicate to the same UPSERT key). Canonical `state-peak-electricity-demand-mw` grew 396 → 430 rows (FY13–FY25, 35 entities incl. IN national). FY18–FY24 overlap between RBI (block 1) and ICED (this block) was **dropped** because 192/221 cells differ; RBI Handbook Table 142 is the gold authority per Hans D33. The mixed `source_id` on the same indicator is contract-clean per writer D7 (`source_id` is per-row, NOT in the dedup key). 4 new Tier-A parity tests pinned TN/IN FY25 cells + source_id boundary + total rowcount.

**Phase A descope rationale (consumer-audit finding)**: §13 browser smoke on `/s/tamil-nadu` revealed the frontend state-hub indicator-widget loader fetches both shards by slug (`/indicators/in/energy/state_*.json`). Deleting them — as the original C4.7 scope item 5 said — produces 404s on every state page and breaks the citizen "Peak demand" card. The backend adapter `_shared.load_shard` also reads them at lift-time (3 backend tests fail). Retirement was therefore deferred to a 4-phase strangler fig:

- **Phase A (PR #119, SHIPPED 2026-05-24)**: additive FY25 lift on canonical; both legacy shards kept.
- **Phase B (PR #171, SHIPPED 2026-05-24/25)**: frontend `IndicatorCard` reader-switch for `state-peak-electricity-demand-mw` — DuckDB-WASM canonical query against `energy_demand_supply.parquet`; legacy shard `state_peak_electricity_demand_mw.json` no longer fetched by `IndicatorCard`.
- **Phase C (this PR, SHIPPED 2026-05-25)**: backend lift drops the `load_shard("state_electricity_peak_demand_mw.json")` dependency. The 34 FY25 observations are inlined as a `_FY25_PEAK_DEMAND_ROWS` Python literal in `backend/yen_gov/canonical/adapters/energy/demand_supply.py` (values byte-identical to the legacy shard's FY25 slice, source_id `src-be6a6d5d6493` unchanged). Phase D `git rm` is now mechanical no-touch on the lift.
- **Phase D (PR #176, SHIPPED 2026-05-25)**: `git rm` both shards + scrub allowlist (`datasets/_ops/meadow-shard-contract.txt` lines 79 + 87) + removed the obsolete duplicate `energy/state_electricity_peak_demand_mw` entry from `datasets/taxonomy/topics.json` (would have 404'd post-shard-removal — the surviving wired `energy/state_peak_electricity_demand_mw` entry routes via allowlist to canonical) + auto-regenerated `docs/reference/data-inventory.md` via `python -m yen_gov coverage` + hand-edited `docs/reference/topics/energy.md`, `docs/concepts/long-coverage-indicators.md`, `docs/architecture/backend/sources-iced-state-wise.md`. Frontend allowlist KEPT (runtime router, not a temporary shim). Ingest cleanup (`backend/yen_gov/sources/iced_state_wise/ingest.py` + `iced_power/ingest.py` still write the shards) deferred to a follow-up Phase E — `tier_b_meadow_shard_contract` validator catches future regressions.

  **Phase B-extension (in the same PR #176)**: the Phase D §13 browser smoke surfaced a latent Phase B miss — `IndicatorChoropleth`, `IndicatorRanked`, `IndicatorSmallMultiples`, and `Home.svelte`'s `load_indicator_titles` all called `fetchIndicator(path)` directly, bypassing the allowlist. With both legacy shards gone they raised `Failed to load indicator: fetch /indicators/in/energy/state_peak_electricity_demand_mw.json failed: 404` banners on `/t/energy` and the topic-grid. Fix shipped in-PR rather than as a descope: added a universal `loadIndicator(path)` helper in `indicator-from-canonical.ts` (derives the legacy artifact id from the DATA_BASE path via the `/^\\/indicators\\/in\\/(.+)\\.json$/` regex, consults the allowlist via `loadIndicatorIfCanonical`, falls through to `fetchIndicator(path)` for non-canonical paths). Migrated all four widgets + `Home.svelte` to use the helper; refactored `IndicatorCard`'s inline branch to use it too (drops the now-unused `fetchIndicator` import). Five new vitest cases cover `legacyArtifactIdFromPath()` and the dispatch behaviour. Pattern is the strangler-fig "complete the reader-switch BEFORE deleting the last legacy reference" — Phase B initially scoped to one renderer, but Phase D's shard deletion is the forcing function that demanded universal coverage. Updated `/memories/lessons.md` to add the "reader-switch phase must audit ALL renderers that path-fetch the slug" rule.


**Phase B status (2026-05-24/25 — SHIPPED)**: introduced a frontend canonical-reader seam targeting ONE indicator (`state-peak-electricity-demand-mw`). 3 new files + 1 modified:
- `frontend/src/lib/canonical/indicator-allowlist.ts` — hand-authored `CanonicalIndicatorDescriptor` allowlist (one entry today) mapping legacy artifact id → canonical indicator id + DuckDB table id + `IndicatorMeta`. Designed for additive growth one indicator at a time.
- `frontend/src/lib/canonical/indicator-from-canonical.ts` — pure mapper (`buildIndicatorArtifact`) + adapter (`loadIndicatorFromCanonical`) + dispatch (`loadIndicatorIfCanonical`). Composes `registerTable` + `query<T>` from `frontend/src/lib/duckdb.ts`. Canonical entity ids stripped of `IN-` prefix to match legacy artifact entity-id shape. Synthesises stub methodology block (publisher from `implementing_authority`, definition from `meta.description`, citation `OGL-IN-1.0`, schema `v4.4`). Sources are second JOIN query against `taxonomy.sources` view; `fetched_at` left empty (citation-ledger v2.0 doctrine; `SourceList.svelte`'s `fmt()` tolerates).
- `frontend/src/lib/canonical/indicator-from-canonical.test.ts` — 24 vitest tests / 5 describe blocks (allowlist invariants, entity translation, builder edge cases, loader SQL shape, dispatch). DuckDB-WASM mocked per CLAUDE.md §15 carve-out.
- `frontend/src/lib/IndicatorCard.svelte` — single-line `$effect` branch: call `loadIndicatorIfCanonical(legacy_id)`, use canonical artifact if returned, else fall through to existing `fetchIndicator(path)`. Zero behaviour change for non-allowlisted indicators.

**Phase B acceptance gates (all GREEN)**: svelte-check (0 errors / 7 pre-existing warnings) · vitest (24/24 new + 1613/1619 full, 6 pre-existing skipped) · pytest (876 passed / 44 skipped / 0 failed; backend untouched but full suite re-run) · `python -m yen_gov validate` ("OK (0 issues)") · §13 browser smoke across `/s/tamil-nadu` (20,211 MW, 5th of 34, 2025-04), `/s/kerala` (5,861 MW, 18th of 34), `/s/bihar` (8,741 MW, 14th of 34) — all show ZERO fetches of `state_peak_electricity_demand_mw.json` and ONE fetch of `energy_demand_supply.parquet` from `IndicatorCard`; 0 console errors / 0 failed requests (pre-existing benign `/data/boundaries/in/manifest.json` 404 on state pages noted).

**Phase B scope boundary (important)**: only `IndicatorCard.svelte` was switched. Topic-grid pages like `/t/energy` use a DIFFERENT renderer that still fetches the legacy shard directly by slug — INTENTIONAL preservation; that's why both legacy shards stay on disk until Phase D. The sister shard `state_electricity_peak_demand_mw.json` (used by cards #43/#44 on every state page — "supplied" + a second "demand" series) is NOT in this PR's allowlist and continues to be fetched as before.

**Phase C status (2026-05-25 — SHIPPED)**: rewrote `backend/yen_gov/canonical/adapters/energy/demand_supply.py` lift block 4. Three options were weighed for how to source the 34 FY25 rows without `load_shard`:

- **(a) no-op rewrite** — keep block 4 emitting nothing FY25 and let only RBI block 1 own the indicator. **Rejected**: writer `replace_partition` semantics (`backend/yen_gov/canonical/writer.py` D7) DELETE FROM observations WHERE indicator_id IN envelope-indicators, then INSERT. If block 4 emits no FY25 rows but block 1 still emits the same `state-peak-electricity-demand-mw` indicator, the DELETE wipes ALL 430 rows and the INSERT re-stages only the 396 RBI rows — FY25 lost. Phase A's citizen-visible work would be silently undone on the next `lift-energy`.
- **(b) re-source upstream from ICED API** — three sub-variants: (b1) live `httpx.get` at lift time (kills determinism + breaks fresh-checkout CI per CLAUDE.md re-run-byte-identical doctrine); (b2) call `backend/yen_gov/sources/iced_state_wise/ingest.py` from the lift (circular — regenerates the very shard being retired); (b3) read pre-cached `.runtime/raw/iced/stateWiseDeepDive_2024-25.json` (CLAUDE.md §2 violation — `.runtime/` is ephemeral and MUST NOT be referenced from committed code). All three blocked.
- **(c) inline FY25 data as a Python literal** — `_FY25_PEAK_DEMAND_ROWS: tuple[tuple[str, str, float], ...]` constant with 34 rows in `demand_supply.py`. **Chosen**. Deterministic offline, bootstrap-safe, `source_id` FK to `src-be6a6d5d6493` (ICED Deep Dive) unchanged → Holy Law #9 satisfied, precedent (`_shared.SOURCE_IDS` is itself a hand-typed dict), annual cadence makes 34-row code update trivial when FY26 lands, Phase D `git rm` becomes mechanical no-touch. The constant carries a refresh-procedure docstring ("re-run `python -m yen_gov iced-ingest`, decrypt, append 34 rows").

The lift block 4 iterates `_FY25_PEAK_DEMAND_ROWS` verbatim, calls `parse_iso_period` + `to_entity_id`, emits `ObservationRow` with `source_id=SOURCE_IDS["iced_deep_dive"]` and `derivation="raw"`. Blocks 1/2/3 (RBI peak_demand, RBI peak_met, ICED per_capita) UNCHANGED; the `load_shard` import stays valid because those three blocks still use it.

**Phase C acceptance gates (all GREEN)**: targeted backend pytest (12/12 — 8 demand_supply parity + 2 adapter build + 2 emit determinism, 20s); full backend pytest (876 / 44 skipped / 0 failed); determinism (two consecutive `python -m yen_gov lift-energy --root .` runs produce byte-identical `energy_demand_supply.parquet`, SHA256 match); `python -m yen_gov validate --root .` ("OK (0 issues)"); §13 browser smoke on `/s/tamil-nadu` (20,211 MW), `/s/kerala` (5,861 MW), `/s/bihar` (8,741 MW) — citizen values unchanged from Phase B.

**Estimated (revised)**: Phase A: ~½ day actual (PR #119). Phase B: ~½ day actual (PR #171). Phase C: ~½ day actual (PR #174). Phase D: ~½ day actual (this PR, #176). **Four-phase strangler-fig closed.** See [canonical-store.md §18.1](../docs/architecture/data/canonical-store.md#181-strangler-fig-retirement-iced-peak-demand-legacy-shards-phase-ad-2026-05-24) for the consolidated retirement-pattern narrative.

### P.1.A C4.5 — CEA per-state per-fuel snapshot lift (3 days; Hans+Max Q1 needed) ✅ DONE 2026-05-24 (SHIP-LIFT-ONLY)

**Status (2026-05-24 — SHIPPED, additive)**: Q1 resolved in favour of Option α (`_snapshot_` infix grammar; snapshot ≠ allocated per OWID separate-indicators-for-distinct-methodologies precedent + §0a "The One Rule"). Catalogue +6 rows (1 parent `state-installed-capacity-snapshot-mw` + 5 children `state-installed-capacity-snapshot-mw-{coal,gas,hydro,nuclear,renewable}`); adapter `installed_capacity.py` block 1 extended to emit per-state per-fuel rows from the 5 CEA shards already lifted at C4 (+175 obs rows = 35 states × 5 fuels). Source `src-092a5dc7af3f` (cea_monthly_ic) re-used; no new triple. **Descope vs original scope**: per PR #177 strangler-fig lesson (lessons.md 2026-05-25 — Phase B reader-switch must precede Phase D `git rm` to avoid 404 banners), this PR ships **lift-only**; legacy-shard retirement (§2.A audit list — 5 CEA shards) + allowlist scrub + §13 browser smoke deferred to a follow-up reader-switch PR (sister to PR #171/#174/#177 four-phase pattern for `state_peak_electricity_demand_mw`). The 175 new canonical rows coexist with the 5 legacy shards until the reader-switch lands; no consumer migration in this PR.

**Acceptance gates (all GREEN)**: targeted backend pytest (52 / 0 failed / 0 skipped — 15 new C4.5 cell parity tests + 1 row-count test + 36 adjacent regressions); full backend pytest (901 / 44 skipped / 0 failed in 2m26s); determinism (two consecutive `python -m yen_gov lift-energy --root .` runs produce byte-identical `energy_installed_capacity.parquet`, SHA256 `9DD16669…`); `python -m yen_gov validate --root .` ("OK (0 issues)"). §13 browser smoke not required (no UI surface changes in this PR; new indicators have no rendered home until catalogue→topic mapping lands).

**Estimated (revised)**: ~½ day actual under Q1=Option α resolution + SHIP-LIFT-ONLY descope. Original 3-day estimate was full lift+retire+§13; descope shaved the retire+§13 work into a separate follow-up.

**Original scope (preserved for reference, reader-switch PR will cover the deferred work)**:

**Scope**:
1. **Q1 decision (Hans+Max)**: catalogue grammar for the per-state per-fuel CEA snapshot. Two options:
   - **Option α**: NEW indicator-ids `state-installed-capacity-snapshot-mw-{coal,gas,hydro,nuclear,renewable}` — `_snapshot_` infix preserves publisher-distinct semantics from the FY-anchored ICED time-series; orphan `state-installed-capacity-allocated-mw-{fuel}` catalogue rows (per C4 adapter docstring "Known scope gap") stay reserved for a future multi-FY per-fuel allocated source. **Recommended**: snapshot ≠ allocated; keeping them distinct is OWID-precedent (separate indicators for distinct methodologies, per §0a "The One Rule").
   - **Option β**: extend orphan `state-installed-capacity-allocated-mw-{fuel}` with single-snapshot rows. **Rejected (default)**: collapses snapshot + multi-FY allocated into one indicator-id, hiding the publisher distinction. Re-creates the audit pattern just caught for the 5 CEA shards.
2. Author 5 NEW catalogue rows in `datasets/taxonomy/indicators.json` per chosen option.
3. Extend `backend/yen_gov/canonical/adapters/energy/installed_capacity.py` to emit per-state per-fuel observation rows from the 5 CEA shards already lifted at C4. 35 states × 5 fuels = 175 rows.
4. Verify source_id `src-092a5dc7af3f` (cea_monthly_ic) covers; no new triple.
5. Retire the 5 legacy shards (§2.A list) + scrub allowlist.
6. Tier-A: 5 new catalogue rows pass schema; lift adapter unit tests cover the new 175 rows; existing 5 national rollup tests still pass; parity oracle ≥3 state-fuel cells per fuel.
7. Tier-B: validator clean post-retire.
8. §13 smoke: `/topic/energy` + 1 state hub (TN coal-heavy or KA renewable-heavy).

**Estimated**: ~3 days under Option α; Hans+Max sign-off on Q1 is the only gate.

### P.1.A C4.6 — RBI Handbook Table 140 FY05-FY14 splice (✅ MERGED 2026-05-24, SHIP-LIFT-ONLY)

**Status**: SHIPPED — additive lift block 5 in `installed_capacity.py`; FY05-FY14 long-arc rows now on canonical `state-installed-capacity-allocated-mw` carrying RBI Handbook Table 140 source_id (`src-3d1d55f8a94b`); legacy shard NOT retired this PR (Fowler pre-impl: SHIP-LIFT-ONLY pattern — additive, no retire, no allowlist extension, no `frontend/indicator-allowlist.ts` change). Legacy shard retirement deferred to a follow-up (mirrors C4.5 sequencing).

**Shipped**:
1. ~~Author NEW lift adapter `backend/yen_gov/canonical/adapters/energy/installed_capacity_long_arc.py` that parses the RBI XLSX Table 140~~ — **DESCOPED**: data already in-hand via `datasets/indicators/in/energy/state_installed_capacity_total_mw.json` (374 pre-FY15 rows). No XLSX parse needed; lifted directly from the existing shard via block 5 in `installed_capacity.py` (filter `r["time"] < "2015-04"`). Q4 (openpyxl path) is moot until a future re-acquisition wants RBI's per-fuel breakdown.
2. ✅ NEW source-triple via `derive_source_id("Reserve Bank of India", "Handbook of Statistics on Indian States — Table 140: State-wise Installed Capacity of Power", "2024-25")` → `src-3d1d55f8a94b`. Seeded in `energy_sources_seed.py` (7 rows now, was 6); written to `taxonomy/sources.parquet` via `emit-taxonomy`. Confidence tier: `silver` per Q-d (RBI republisher; CEA upstream).
3. ✅ Q2 verdict (Hans, this PR): NULL-fuel "unresolved aggregate" rows are NOT emitted because ObservationRow has no `fuel_type` column — fuel granularity lives in `indicator_id` only. Block 5 emits to the parent indicator-id `state-installed-capacity-allocated-mw` (no fuel suffix), which is the OWID-correct representation of "aggregate, no fuel split" semantics. The renderer's existing time-series widgets already render this parent indicator correctly.
4. **Legacy shard retirement DEFERRED**: `state_installed_capacity_total_mw.json` stays on disk; reader-switch + `git rm` + `_ops` allowlist scrub batched into a future follow-up (mirrors C4.5 lift-only / reader-switch deferred / retire deferred sequencing — see C4.7 footnote in §4).
5. ✅ methodology_breaks: NEW row `rbi-handbook-aggregate-no-fuel-split-pre-fy15` (at_year=2015, kind=`definition_change`) documents BOTH the basis change at FY15 (RBI Handbook → ICED Deep Dive) AND the publisher's choice to NOT break out per-fuel in the long-arc tail. Cited from the parent indicator row via `methodology_break_ids[]`.
6. ✅ Tier-A: 7 new C4.6 longarc parity tests + `test_energy_sources_seed.py` bumped 6→7 throughout. All 38/38 targeted pass.
7. ✅ Tier-B: validator clean (0 issues).
8. ✅ §13 smoke: `/t/energy` + `/s/tamil-nadu/t/energy` — 0 console errors, 0 stuck loaders; RBI Handbook source attribution + 2014 year markers verified in topic-page snapshot.

**Row delta**: `energy_installed_capacity.parquet` 2120 → 2494 rows (+374 = 11 FY × 34 states/UTs).

**Determinism**: SHA256 byte-identical across 2 consecutive lifts (`E7934B39...0662E`).

### P.1.A C4.6 — RBI Handbook Table 140 FY05-FY14 splice (original scope, kept for history)

**Scope**:
1. Author NEW lift adapter `backend/yen_gov/canonical/adapters/energy/installed_capacity_long_arc.py` that parses the RBI XLSX Table 140 and emits FY05-FY14 rows into `state-installed-capacity-allocated-mw` with `fuel_type IS NULL` per Q-c verdict (RBI publishes the aggregate, not the per-fuel split). Renderer treats NULL-fuel rows as a single grey "unresolved aggregate" band (Q-c citizen text).
2. Author NEW source-triple via `derive_source_id("Reserve Bank of India", "Handbook of Statistics on Indian States — Table 140: State-wise Installed Capacity of Power", "2024-25")` → seed citizen-text row in `datasets/taxonomy/sources.json`. Confidence tier: `silver` per Q-d (RBI republisher; CEA upstream).
3. Verify Q2 (§5): does the renderer's NULL-fuel "unresolved aggregate" band already exist on `stacked-trend` / choropleth? If not, ship the parquet in C4.6 but pause the legacy-shard retire (and the `_ops` allowlist scrub) until a separate front-end PR adds the render path.
4. Retire `state_installed_capacity_total_mw.json` (audit §2.C row 1) once Q2 is resolved.
5. methodology_breaks: NO new row — Q-c handles this via NULL fuel_type semantics, not a series break.
6. Tier-A: long-arc lift unit test against a 10-row fixture XLSX (DO NOT live-fetch RBI in tests per Holy Law #7); FK gate verifies new source row.
7. Tier-B: validator clean.
8. §13 smoke: TN + AP state hubs (long-history charts) — confirm pre-FY15 grey band renders if Q2 verdict is "render path exists".

**Estimated**: ~3-4 days. RBI XLSX parsing has Indian-tabular quirks (merged-cell headers, "P" provisional markers, footnote rows in body). openpyxl + fixture-based test is the cheapest shape (Q4 in §5).

### P.1.A C4.8 — Sub-fuel preservation (✅ DONE 2026-05-24 additive — methodology_breaks + Tier-B fence; shard retire descoped to follow-up)

**Status (2026-05-24 — SHIPPED, descoped)**: This PR ships ONLY the methodology_breaks row + Tier-B fence per Option B (Hans+Max Q3 verdict). The `state_installed_capacity_by_source_mw.json` shard retire is **descoped to a follow-up PR** because `datasets/taxonomy/topics.json:300` still references it (PR #177 strangler-fig lesson — reader-switch must precede shard retire). Future sub-fuel breakouts cannot regress D33.8's 5-bucket axis without an explicit doctrine amendment.

**Scope**:
1. **Q3 decision (Hans+Max, MUST resolve before code)**: do we want sub-fuel granularity (large-hydro vs small-hydro; bio-power vs waste-to-energy; wind vs solar-utility vs solar-rooftop) as citizen-surface indicators?
   - **Option A (preserve detail)**: widen catalogue with `state-installed-capacity-geographical-mw-{sub-fuel}` × ~4 new sub-fuels; lift the 678 currently-collapsed rows; widen `fuel_type` enum in `facet-axes.parquet`. Multiplies catalogue width; relaxes D33.8 5-bucket rule.
   - **Option B (accept collapse + fence)**: D33.8's 5-bucket axis is a permanent design choice; the 678 rows live only as derivation="sum" inputs to per-fuel children. Retire the legacy shard with a `methodology_breaks` row documenting the collapse rationale. Add a Tier-B fence banning new sub-fuel shards.
   - **Recommended**: Option B. The 5-bucket axis was Hans's D33.8 ruling; preserving sub-fuel detail re-opens it and forces every downstream chart (stacked-trend, choropleth, IndicatorRanked) to choose a fuel-axis granularity per chart — exactly the per-chart-bespoke pattern Jony's [`docs/concepts/entity-bifurcation-rendering.md`](../docs/concepts/entity-bifurcation-rendering.md) §2 already rejected as accidental complexity.
2. Under Option A: 4 new catalogue rows + ~170 new observation rows + `fuel_type` enum extension + Tier-B sub-fuel-ban removal.
3. Under Option B: retire `state_installed_capacity_by_source_mw.json` directly (no canonical change) + author a `methodology_breaks` row explaining the 5-bucket collapse + scrub allowlist.
4. Tier-A + Tier-B + §13 smoke per option.

**Estimated**: ~1 day under Option B, ~3 days under Option A. ~~**BLOCKED on Hans+Max Q3.**~~ ✅ Q3 RESOLVED 2026-05-24 — Option B adopted (additive ship — methodology_breaks row + Tier-B fence; legacy-shard retire descoped to follow-up).

## §4. Sequencing summary

1. **Now** (this PR): ship THIS doc-only re-acquisition plan.
2. **Next** (autonomous-doable): ship Path A retire PR — 8 SAFE shards including the `state_peak_electricity_demand_mw.json` FY25 loss; PR body cites this re-acquisition plan §3 C4.7 as the FY25-restore commitment.
3. **Then** (1 day; no decisions needed): P.1.A C4.7 ICED peak-demand FY25 extension; restores the FY25 data lost in step 2. **Update 2026-05-24**: Phase A SHIPPED additive (FY25 on canonical); shard retirement deferred to Phases B–D pending frontend reader-switch — see §3 C4.7 descope note.
4. **Then (parallel)**: ~~P.1.A C4.5 (3 days; Hans+Max Q1 needed)~~ ✅ DONE 2026-05-24 (lift-only; reader-switch deferred) + ~~P.1.A C4.6 (3-4 days; Hans Q2 needed for renderer)~~ ✅ DONE 2026-05-24 (SHIP-LIFT-ONLY; reader-switch + legacy-shard retire deferred to follow-up).
5. ~~**Then**: Hans+Max Q3 decision → P.1.A C4.8 execute.~~ ✅ DONE 2026-05-24 (additive — Option B; methodology_breaks row + Tier-B fence; legacy-shard retire descoped to follow-up).
6. **Last**: P.1.A C5+C6 full reader-switch + final retire pass when all 8 deferred shards are no longer deferred (the rejected-fully-fused approach from PR #116 becomes ship-able).

## §5. Open decisions (route via §0a)

| Q | Question | Owner | Recommended | Blocks |
| --- | --- | --- | --- | --- |
| Q1 | `_snapshot_` infix grammar (Option α) vs extend orphan `state-installed-capacity-allocated-mw-{fuel}` (Option β) for CEA per-state per-fuel | Hans + Max | Option α (snapshot ≠ allocated; OWID separate-indicators-for-distinct-methodologies precedent) | ✅ RESOLVED 2026-05-24 — Option α adopted (C4.5 shipped) |
| Q2 | Does the renderer's NULL-fuel "unresolved aggregate" grey band already exist on `stacked-trend` / choropleth? Or must C4.6 ship the renderer too? | Hans (verdict) + Jony (renderer audit) | Audit renderer; if missing, split C4.6 into back-end parquet ship + front-end render PR | C4.6 retire-step |
| Q3 | Sub-fuel preservation: Option A (widen catalogue) vs Option B (collapse + Tier-B fence + methodology_breaks row) | Hans + Max | Option B (preserves D33.8 5-bucket ruling) | ✅ RESOLVED 2026-05-24 — Option B adopted (additive ship: methodology_breaks + Tier-B fence; shard retire descoped to follow-up) |
| Q4 | RBI XLSX parsing: openpyxl with fixture test, or pre-stage CSV via `tools/`? | Fowler | openpyxl with fixture-based unit test (no live RBI fetch in tests per Holy Law #7) | C4.6 implementation shape |
| Q5 | Coordinated tier-promotion lifts (P.1 plan-doc §3.1 #11): 3 missing triples (CEA AGR, IEA India Energy Outlook, Coal Controller Provisional Coal Statistics) — bundle into C4.5/C4.6, or keep as a separate UX-upgrade PR? | Hans + Max | Defer; tier promotion is citizen-trust UX, not data correctness; per ADR-0032 the current silver attribution is doctrinally correct | None — C4.5/C4.6 ship without |

## §6. What this PR ships

Doc-only — this single new TODO file + small status updates to the audit doc (`§3` marks Path A CHOSEN) + the P.1 energy pivot plan-doc (`§6` hard-drops table cross-refs the per-shard re-acquisition target) + the C5+C6 design doc (status notes Path A + this plan). No code change. No schema change. No retire.

The next PR (Path A retire of 8 SAFE shards) ships separately per the audit doc §5 sub-PR shape. C4.7 (FY25 restore) ships immediately after.

## §7. Cross-refs

- [C5+C6 retire-list audit findings (PR #117)](20260524-p1a-c5-retire-list-audit-findings.md) — source of the 9 deferred/lost shards
- [C5+C6 canonical reader design (PR #116)](20260524-p1a-c5-c6-canonical-reader-design.md) — the design that gates the final retire pass
- [P.1 energy pivot plan-doc](20260522-phase-2-p1-energy-pivot.md) §2 (canonical decomposition) + §3 Q-c (long-arc splice) + §3 Q-d (tier table) + §3.1 #11 (tier promotion follow-up) + §6 (hard drops)
- [canonical-store.md §2b](../docs/architecture/data/canonical-store.md) — fact-table layout rules
- [ADR-0030 D33.8](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) — atomic-fuel + compute-on-read invariant
- [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) — `derive_source_id` for new (producer, title, vintage) triples
- [`tools/inspect_canonical_energy.py`](../tools/inspect_canonical_energy.py) — re-runnable canonical-store inventory; produced the rowcounts cited in §2
- [`backend/yen_gov/canonical/adapters/energy/installed_capacity.py`](../backend/yen_gov/canonical/adapters/energy/installed_capacity.py) — existing C4 adapter; C4.5 extends it
- /memories/lessons.md 2026-05-24 PR #117 — conceptual-map-vs-data-shape lesson that drove this plan

# 2026-05-21 — handover: Phase 2 pre-flight architecture audit (Gregor)

> **Status:** AUDIT-ONLY artifact. No code shipped from this audit. Triggered by user pushback on 2026-05-21 that the framing "canonical-pivot arc is about elections, not indicators" was wrong. Gregor (Architect persona) ran a thorough sweep of the codebase to surface every assumption that contradicts "all indicators are in canonical scope."

## TL;DR

**The canonical pivot is half-shipped.** Elections crossed cleanly to Parquet + DuckDB-WASM + v2.0 sources ledger. The 110 socio-economic indicators under `datasets/indicators/in/{9 topic dirs}/` are *decorated* with v4.4 ontology fields but **not migrated**. That asymmetry leaks across 7 surfaces, ordered below by blast radius.

The cross-cutter: **does the JSON indicator tree need to exist in any future state? It doesn't.** Plan §0e.7 P.\* already schedules per-family retirement (NFHS-5 → PLFS → UDISE+ → AISHE → NCRB → HCES 2022-23 → IMD → e-GramSwaraj/PFMS → TRAI → CAG). Disk doesn't yet reflect it.

## User's direct questions answered

| Q | Answer |
|---|---|
| Was "canonical-pivot is about elections" a short-sighted assumption? | **YES.** §0e.7 P.* schedules every indicator family to drop `datasets/indicators/in/<family>/` as it pivots. v4.0 folded artifact (ADR-0026) is interim. |
| Phase 1 done vs row 1.8 TODO contradiction? | Both true, framing was confusing. Phase 1 (elections 1.8a–f) **is done**. §0e.9 says Phase 2 ADDS new 1.8.x rows per family. Zero remote branches for any P.* family today. |
| Boundaries `.sources.json` per-file vs consolidated? | **Consolidated via citation ledger.** Each boundary file becomes a row in `manifest.json.boundaries[]` with `{file, entity_level, source_id}` FK→`taxonomy/sources.parquet`. All 73 sidecars delete. Same pattern T.0a applied to observation provenance. |

## Findings (7 + 1 cross-cutter)

### #1 — Two live data-shape contracts for "indicator" (HIGH blast radius)

| Shape | Where | Read path | Provenance |
| --- | --- | --- | --- |
| Per-shard folded JSON, `indicator.schema.json` v4.4 | `datasets/indicators/in/{energy,fiscal,...}/` | `fetch('/data/indicators/in/<topic>/<id>.json')` via `fetchIndicator` in `frontend/src/lib/indicators.ts` | `sources[].{url, fetched_at}` array per shard |
| Long-format Parquet rows in canonical store | `datasets/elections/state=*/election_results.parquet` + dims | DuckDB-WASM via `registerTable` in `frontend/src/lib/duckdb.ts` + `view-models/` | `source_id` FK → `taxonomy/sources.parquet` v2.0 citation ledger |

**Pattern:** Canonical Data Model violation (EIP §2). Plan declares canonical = Parquet + DuckDB-WASM but `datasets/indicators/in/` IS the canonical data for 80%+ of the socio-economic corpus. Every consumer has to know which shape its target lives in. Indicator shape has no `source_id` FK, no `period_seq`, no `taxonomy/indicators.parquet` row, no `value_numeric/value_text` split.

**Recommendation:** Lock §0e.7 P.* ordering. **Stop writing new content to `datasets/indicators/in/` today.** Add a Tier-B forbidden-path check that fails `python -m yen_gov validate --root .` if `git diff origin/main..HEAD --name-only datasets/indicators/in/` shows additions, accepting only modifications. Structural equivalent of `test_no_legacy_json_emit.py`, one phase early. Add to `docs/architecture/canonical-pivot-deletion-manifest.md §6a`.

### #2 — Per-shard `sources[]` arrays still ship the fetched_at smear (HIGH)

Example: `datasets/indicators/in/energy/state_per_capita_electricity_consumption_kwh.json` carries v1.0 per-shard provenance shape `"sources": [{"url": "...", "fetched_at": "..."}]`. No `source_id` FK, no row in `taxonomy/sources.parquet`. 110 indicator files × N rows × 0 FKs to the citation ledger = Holy Law #9 enforced 100% on elections rows and 0% on socio-economic rows.

`backend/yen_gov/canonical/citation.py::derive_source_id` and `SourceRow` (frozen/extra=forbid) exist but nothing in `core/io.py::write_artifact` consults them. `core/io.py:38-47` literally has `_OPERATIONAL_STRIP_PATHS` band-aid pretending `sources[].fetched_at` doesn't exist for write-skip equality. Comment in io.py is honest about it: "every entry is a place where the contract is silently leaky and we are accepting that."

**Pattern:** Fix at wrong altitude (write seam, not source-of-identity). Same disease as the 2026-05-16 fetched_at lesson, applied one layer up.

**Recommendation:** `_OPERATIONAL_STRIP_PATHS` retires alongside the first P.* family (NFHS-5). Add §6 to ADR-0032 ("Transitional state during the canonical pivot") naming the JSON tree as the last bypass and P.* as the resolution. Documented transitional state with named exit, not silent precedent.

### #3 — URL shape pre-violates §0e.3 naming rule (MEDIUM)

§0e.3 locks "Citizen URL slugs: hyphen-separated, no topic prefix, OWID convention (e.g. `outstanding-debt-pct-gsdp`, `gdp-per-capita-mospi`). Topic in URL is a single-parent lie when topics are M:N — drop it."

Every existing artifact violates this on three axes:
- Topic IS in the path (`/indicators/in/energy/…`)
- IDs use `snake_case` (`state_per_capita_electricity_consumption_kwh`), not kebab-case (D30 specifies ≤60 chars kebab)
- `entity_id` values use bare `S01..S22..U01..U09`, not the `IN-S22` country-prefixed grammar §0e.10.2-A locked

**Pattern:** Tolerant Reader (Postel) used inappropriately *within* one's own system (`frontend/src/lib/data.ts/paths.ts` already does multiple format normalisations).

**Recommendation:** When T.3 ships, `id_aliases` window MUST be ONE release. Tier-B validator rule: fail if any `id_aliases` entry is older than the previous tagged release. Otherwise alias map grows monotonically and every new family inherits four cardinalities of legacy. Add to §0e.7 T.3 row: "`id_aliases` entries carry a `deprecated_in: <tag>` field; Tier-B rejects entries older than `<tag>-1`; mechanical removal ships in the same PR as next release tag."

### #4 — Boundaries S22-villages = PMTiles avoidance condition firing (MEDIUM)

`datasets/boundaries/in/geojson/` carries 33 `S22-villages-NNN.geojson` files + 33 `.metadata.json` + 33 `.sources.json` sidecars = 99 files per state for a single state's village layer. Per-file `.sources.json` is per-shard provenance smear at the boundary layer, isomorphic to the indicator-JSON-shard smear.

§5 + D25 + ADR-0031 say "GeoJSON for small layers, **PMTiles** for large layers (>~10 MB)". Plan's Q11: "When a layer exceeds ~10 MB GeoJSON, switch that layer to PMTiles". Threshold has fired for S22-villages but hasn't been acted on.

**Pattern:** Same disease as #1 + #2, different family. Cure identical: collapse per-shard provenance into citation ledger + switch geometry packaging to PMTiles.

**Recommendation:** Boundaries become a fifth P.* family. One Tier-A commit per region: (a) write village PMTiles for state, (b) seed `sources.parquet` rows for upstream publishers (Survey of India, LGD, MoPR), (c) `git rm` per-village GeoJSON + 66 sidecars, (d) update `manifest.json.boundaries[]` to point at PMTiles. Defer until after Phase 2 NFHS-5 ships — but treat as P.* family, not "different forever". ADR-0031 + `docs/architecture/data/boundaries.md` need updates.

### #5 — T.1 + G.1 + features-audit NOT shipped (MEDIUM-HIGH; blocks Phase 2 hygiene)

Plan §0e.7 mandates:
- T.1: **Delete `_test/`. Create `_ops/`. Move operator state → `_ops/`. Audit `features/` (delete or document).**
- G.1: **Migrate `governments/in/states/<state>/cm_terms.json` → fact rows. Delete `governments/in/states/`.**

Disk today (2026-05-22 update):

- `datasets/_ops/` exists; `datasets/_test/` retired — **T.1 ✅ done** in commit `76bc5fde` (`refactor(T.1+legacy): rename _test/ -> _ops/, lift fixtures cross-language, extract folded-indicator writer to yen_gov.legacy`).
- `datasets/features/in/` contains 2 files (`energy/power-plants.geojson` + `.metadata.json`) actively written by `backend/yen_gov/sources/india_geodata/power_plants.py`, consumed by the frontend energy-hub map. **Features audit ✅ done** in PR2 — decision: KEEP (see [`datasets/features/README.md`](../datasets/features/README.md)).
- `datasets/governments/in/states/` still holds 31 hand-edited `cm_terms.json` files that `backend/yen_gov/canonical/cm_terms_seed.py` recompiles to `governments_office_holdings.parquet` + `dim_offices.parquet` on every `emit-taxonomy` run. **G.1 ⏳ deferred** to its own 3-PR strangler-fig (G.1.a/b/c) — see [`TODO/20260522-g1-cm-terms-retirement-handover.md`](20260522-g1-cm-terms-retirement-handover.md).

**Pattern (revised):** The "data already in Parquet" framing in the original recommendation was technically true but operationally misleading — JSON is the LIVE source-of-truth, Parquet is DERIVED. Single-PR delete would brick the compile step and break the citizen-facing "Your government" card. Same disease as T.0c-iii (districts.json → entities.parquet): retirement requires entity-lift, reader-switch, then deletion as separate Tier-A pairs to stay bisect-safe.

**Recommendation (revised):** Ship T.1 status update + features-KEEP doc + G.1 handover in PR2 (this descope). Run G.1.a/b/c strangler-fig before Phase 2 NFHS-5.

### #6 — `core/io.py::write_artifact` = two contracts in one function (MEDIUM)

`backend/yen_gov/core/io.py` is the JSON artifact writer. Today it does:
- **JSON envelope contract** (`$schema`/`$schema_version` stamp + structural-equality skip) — used by every non-canonical JSON writer.
- **Folded-indicator v2.0 contract** (`_maintain_folded_blocks` branch on `_is_indicator_schema(schema_id)`) — only used by the indicator JSON tree being retired.

Two seams in one function = two contracts the maintainer can't tell apart. Nothing structural prevents a new contributor writing a new adapter against the OLD shape. Worse, the write-skip band-aid is *load-bearing* for indicator re-emits; retiring the folded branch and retiring the band-aid have to ship together.

**Pattern:** Two filters joined at a point that isn't a Message Translator. Pipes-and-Filters topology calls for one filter per transformation kind.

**Recommendation:** Extract `_maintain_folded_blocks` + `_is_indicator_schema` + `_OPERATIONAL_STRIP_PATHS` into one explicitly-named legacy module — `backend/yen_gov/legacy/folded_indicator_writer.py` — with a module docstring naming the P.\* PR that will delete it. Makes the dead-man-walking visible at every import site. Add a §16 row to the plan: "JSON write-seam retirement — once P.* row 2.1 ships, move legacy folded branch into `legacy/` namespace; once all P.* rows ship, delete namespace and band-aid". No new ADR needed.

### #7 — Hand-typed schema-version literals (LOW until next bump)

CLAUDE.md §11 + lessons.md 2026-05-20 both say "Code never hand-types schema-version literals; use `yen_gov.core.schema_registry`". 110 artifacts under `datasets/indicators/in/` each stamp `"$schema_version": "4.4"` as a hand-typed literal. `core/io.py:113` takes `schema_version` as a function argument so the caller is responsible — but no adapter consults `schema_registry.schema_version("indicator.schema.json")`.

When v4.5 ships, all 110 artifacts will need a `bump_indicator_schema_to_current.py` re-run because literals didn't drift forward automatically. Registry only earns its keep if every emitter routes through it; canonical writer does, JSON writers don't.

**Recommendation:** Until P.* completion, **don't bump `indicator.schema.json` again.** Every bump today re-pays migration cost we're about to make moot. Add to §0e.7 T.3 row: "Frozen `indicator.schema.json` policy — no minor bumps between now and P.* completion; new optional fields land on `taxonomy/indicators.parquet` row schema instead, where registry guarantees they propagate". Lift freeze when last P.* PR retires the JSON tree.

### Cross-cutter — The One Rule (Hohpe-Durov)

Two findings (#1 + #6) reduce to the same prior question: **does the JSON indicator tree need to exist in any future state?** It doesn't. The Parquet store + DuckDB-WASM is the canonical model; JSON tree is transitional. So the cheapest contract is the one we already plan to delete — accelerating the JSON retirement is structurally cheaper than the workmanship of keeping the two shapes in sync.

Plan already says this. Disk doesn't yet reflect it. **That gap is the audit.**

## Things Gregor deliberately did NOT flag

- `datasets/ephemeral/` raw `.pdf` / `.xls` / `.csv` files — operator scratch space; per CLAUDE.md §2 + §10 should arguably live in `.runtime/`, but moving committed bytes out of repo is a separate decision (user has explicitly used "commit IS the backup" semantics elsewhere). Not architecture, not Gregor's seat.
- 4-arm `LoaderResult` contract (D19/D32) — correctly applied in elections view-models.
- Frontend Hive-globbing for `elections/state=*/election_results.parquet` — manifest-driven, works as designed (D21/D23).
- a11y — descoped per CLAUDE.md §0 non-goals.
- What the JSON tree should look like *after* P.\* ships — Hans + Max territory (§0a authority), not Gregor.

## Recommended sequencing (Gregor's call) — Phase-2 pre-flight ✅ CLOSED 2026-05-22

Path B (Phase 2 pre-flight cleanup) BEFORE Path C (Phase 2 P.\* NFHS-5 family). All seven steps done; Phase 2 ground is clean.

1. **Forbid new shards under `datasets/indicators/in/` (#1 partial)** — ✅ shipped commit `8de71a4a`, PR #87.
2. **T.1 status reconciliation + features-KEEP + G.1 handover (#5 descope)** — ✅ shipped commit `8fb3e935`, PR #88. T.1 ✅ shipped commit `76bc5fde`; features ✅ KEEP; G.1 deferred to G.1.a/b/c.
3. **G.1.a — entity-lift** — ✅ shipped commit `ee441193`, PR #89. 31 `entity_type='office_bearer'` rows appended to `taxonomy/entities.json`; `entity.schema.json` v1.1 → v1.2; Tier-A parity oracle pins `dim_offices.office_id == entities.entity_id[entity_type='office_bearer']`.
4. **G.1.b — reader-switch** — ✅ shipped commit `cc9ad5b7`, PR #90. `cm_terms_seed.py` reads office identity from `entities.parquet` instead of computing from JSON state codes inline; Parquet outputs verified byte-identical pre-vs-post; new Tier-A parity oracle `test_g1b_cm_terms_reader_switch_parity.py`.
5. **G.1.c — consolidate + retire** — ✅ shipped commit `36e64c87`, PR #91. 31 per-state `cm_terms.json` → 1 `datasets/taxonomy/office_holdings.json` (359 holdings + 31 office_citations); `office-holdings.schema.json` v1.0; `office_holdings_seed.py` replaces `cm_terms_seed.py`; frontend `governments.ts` rewritten with in-loader adapter back to legacy `GovernmentTerm` shape; `git rm` of 31 JSON + `cm_terms_seed.py` + `test_cm_terms_seed.py` + `state_government.schema.json` + `tools/author_cm_terms.py` + `tools/lift_cm_offices_to_entities.py`; byte-identical Parquet verified 3rd time.
6. **`core/io.py` legacy namespace move (#6)** — ✅ shipped inline with T.1 in commit `76bc5fde` (`refactor(T.1+legacy): rename _test/ -> _ops/, lift fixtures cross-language, extract folded-indicator writer to yen_gov.legacy`). `backend/yen_gov/legacy/folded_indicator_writer.py` exists with module docstring naming the final P.* PR that deletes it; `core/io.py:34-40` imports `is_indicator_schema`, `maintain_folded_blocks`, `strip_operational` from the legacy namespace. The audit's separate PR3 spec was rolled into T.1 since both were structural pre-Phase-2 hygiene.
7. **Then Phase 2 NFHS-5 P.* sub-PR** — ⏳ NEXT. First family pivot. Multi-day arc; crosses backend + frontend + Pydantic + schema + browser smoke. Planning doc: [`TODO/20260522-phase-2-p1-nfhs-5-planning.md`](20260522-phase-2-p1-nfhs-5-planning.md).

Boundaries consolidation (#4) is orthogonal — fits anywhere in Phase 2, treat as a fifth P.* family. Defer until first 1–2 indicator P.* sub-PRs ship and the pattern is locked.

## Deferrals & open decisions (consolidated 2026-05-22, post pre-flight)

The pre-flight sequence is closed, but five categories of work / decisions were intentionally deferred. They are listed here so future agents/operators don't re-discover them.

### A. Open questions for user (need a human decision before they unblock work)

1. **Operator-state file shape post-Phase-2:** when `datasets/indicators/in/` retires, where do `frozen` / `refetch_requested` / `unavailable_periods` live? Options: (a) `taxonomy/operator_state.parquet` table keyed on `indicator_id`, (b) columns on `taxonomy/indicators.parquet`, (c) hand-edited sidecar at `datasets/_ops/indicators-operator-state.json` (per T.1). **Authority**: Hans + Max (per CLAUDE.md §0a — data shape). **Blocks**: not blocking P.1 (NFHS-5 can land observation rows without operator-state on day one); blocks the FINAL P.\* PR that deletes `datasets/indicators/in/` entirely (at that point the operator state must already live elsewhere).
2. **Completeness index post-Phase-2:** `indicators-completeness.json` becomes a SQL query against observations + sources at read time, or stays as a pre-rolled JSON? Performance vs operator-feedback-loop tradeoff. **Authority**: Jony + Citizen (UX of `/data-completeness` page). **Blocks**: same as #1 — final P.\* PR.
3. **`id_aliases` window length:** Gregor recommends ONE release. User direction needed on what "release" means in yen-gov's tag scheme. **Authority**: Fowler (refactor safety) + user. **Blocks**: T.3 (indicator catalogue widen). Not blocking P.1 because P.1 IS the first family pivot — no aliases to honour yet.
4. **TCPD license confirmation (CC-BY-NC-SA 4.0):** Hans must confirm before S.1 ships. **Authority**: Hans + user. **Blocks**: S.1 (persons fork). Not blocking P.1.

### B. Scheduled-but-deferred work (no decision needed; runs after gating step)

5. **Boundaries-as-fifth-P.\*-family (#4 in this audit)** — consolidate 33 per-village `S22-villages-NNN.geojson` + 99 sidecars into PMTiles + citation ledger rows. Treat as a P.\* family alongside the 10 indicator families. **Schedule**: defer until first 1–2 indicator P.\* sub-PRs ship and the pattern is locked. **Authority**: Gregor (codec choice) + Max (citation rows). Owner: TBD when scheduled.
6. **Schema-version literal freeze on `indicator.schema.json`** (#7 in this audit) — no minor bumps between now and P.\* completion; new optional fields land on `taxonomy/indicators.parquet` row schema instead, where `schema_registry` guarantees propagation. **Lift freeze**: when the last P.\* PR retires the JSON tree. **Owner**: enforced by convention (no Tier-B check); every P.\* PR review must reject `indicator.schema.json` bumps.
7. **Final retirement of `backend/yen_gov/legacy/folded_indicator_writer.py`** — delete in the same Tier-A commit as the last P.\* PR (when the last `datasets/indicators/in/<topic>/<id>.json` shard is `git rm`'d). The module docstring already names this gate. **Owner**: whoever owns the last P.\* PR.
8. **`_OPERATIONAL_STRIP_PATHS` retirement** (#2 in this audit) — retires with the first family pivot (NFHS-5 P.1) per ADR-0032 §6 note. Add the §6 ADR amendment text in P.1's Tier-A pair. **Owner**: P.1 PR.

### C. Documentation cleanup (low-priority, post-merge tidy)

9. **`TODO/20260522-g1-cm-terms-retirement-handover.md`** — handover doc is now history (G.1.a/b/c all shipped). Parallel to T.0c handover cleanup pattern from 2026-05-21 lesson. **Action**: `git rm` in a docs-tidy PR alongside a future cleanup batch (NOT urgent). **Note**: leave in place for one release cycle as a citizen-reference for the strangler-fig pattern.
10. **`backend/tests/test_g1b_cm_terms_reader_switch_parity.py`** — Tier-A parity oracle from G.1.b stays as a back-stop for any future change to office identity resolution. **Action**: keep until the next reader-contract change to `office_holdings_seed.py`; retire then.

### D. Items SANITY-CHECKED as already correct (do not re-litigate)

- `taxonomy/sources.parquet` v2.0 citation-ledger shape is correct for indicator observations; no migration needed.
- 4-arm `LoaderResult` contract correctly applied in elections view-models.
- Frontend manifest-driven Hive globbing for elections is correct.
- §0c boundaries preservation carve-out from §6 / §7 sweeps is correct as a prevent-accidental-deletion rule (boundaries has its own *codec*, PMTiles vs Parquet, not its own forever contract).
- Phase 1 elections work (1.8a–f) is honestly DONE per on-disk audit.

### E. NOT in scope for this audit (escalate separately if surfaced)

- `datasets/ephemeral/` raw `.pdf` / `.xls` / `.csv` files — per CLAUDE.md §2 + §10 arguably should live in `.runtime/`, but moving committed bytes out of repo is a separate decision ("commit IS the backup" semantics elsewhere). Not architecture.
- What the JSON tree should look like *after* P.\* ships — Hans + Max territory; design happens INSIDE each P.\* PR, not in this audit doc.

## What was sanity-checked as already correct

- `taxonomy/sources.parquet` v2.0 citation-ledger shape is ALREADY correct for indicator observations; no migration needed.
- 4-arm `LoaderResult` contract correctly applied in elections view-models.
- Frontend manifest-driven Hive globbing for elections is correct.
- §0c boundaries preservation carve-out from §6 / §7 sweeps is correct as a prevent-accidental-deletion rule (just shouldn't be read as "boundaries has its own forever contract" — it has its own *codec*, PMTiles vs Parquet).
- Phase 1 elections work (1.8a–f) is honestly DONE per on-disk audit.

## Three Tier-A PRs Gregor's recommendation generates

Each pair includes the doctrine / doc updates that close the §0d "deferred reads like progress" gap.

### PR1 — `feat/phase-2-preflight-forbid-new-folded-indicator-shards` — ✅ done (commit `8de71a4a`, PR #87, merged 2026-05-22)
- Tier-B validator check: `tier_b_legacy_folded_indicator_shards` in `backend/yen_gov/validate.py` reads the allowlist `datasets/_ops/legacy-folded-indicator-shards.txt` and fails the validator on any `*.json` under `datasets/indicators/in/` not listed. Also fails on orphan allowlist entries (in allowlist but not on disk). No-op when the directory is absent (final-retirement contract).
- **Design refinement from spec**: original spec said `git diff origin/main..HEAD --name-only` — replaced with an on-disk allowlist because (a) validator deliberately doesn't shell out to git (it runs against any checkout, including detached HEAD or zip-extracted), (b) the allowlist file IS the doctrinal artifact: P.* retirement PRs amend it in the same Tier-A commit as the `git rm` of the shards, so the allowlist file's diff is the audit trail; (c) the same plain-text `_ops/` allowlist pattern is reusable for the planned `tier_b_no_legacy_people_acgen` / `tier_b_no_legacy_results_csv` / `tier_b_no_legacy_states_subdir` checks (see [docs/architecture/canonical-pivot-deletion-manifest.md §6d](../docs/architecture/canonical-pivot-deletion-manifest.md)).
- Add to `docs/architecture/canonical-pivot-deletion-manifest.md` (new §6d "Tier-B forbidden-path checks" subsection) — ✅ done in this PR.
- Add to CLAUDE.md §10 anti-pattern list (appended "Enforced by Tier-B" sentence to existing entry) — ✅ done in this PR.
- New mechanism doc section: `docs/architecture/backend/validator.md` "Forbidden-path checks" — ✅ done in this PR.
- 6 Tier-A tests in `backend/tests/test_validate.py` (`_seed_indicator_tree` helper + passes-allowed + rejects-new + rejects-orphan + no-op-when-absent + requires-allowlist + chained-into-`run()` regression guard).
- Allowlist `datasets/_ops/legacy-folded-indicator-shards.txt` seeded with the current 110 legacy shards (sorted, POSIX paths, `#`-comment header).
- Final shape: ~70 LOC validator + ~140 LOC tests + 110-line allowlist + ~30 LOC docs.

### PR2 — `feat/phase-2-preflight-t1-status-features-audit-g1-deferred` — ✅ done (commit `8fb3e935`, PR #88, merged 2026-05-22)
- Reconcile audit body T.1 status (was "not shipped" → now "✅ done commit `76bc5fde`").
- Features audit: KEEP decision documented in new [`datasets/features/README.md`](../datasets/features/README.md) (sole writer = india-geodata adapter; sole reader = energy-hub map; geometry has no Parquet analytical path).
- Update [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md) §2b.3 features row to "KEEP".
- G.1 explicit defer: new [`TODO/20260522-g1-cm-terms-retirement-handover.md`](20260522-g1-cm-terms-retirement-handover.md) (~150 lines) with 3-PR strangler-fig design (G.1.a entity-lift / G.1.b reader-switch / G.1.c JSON+seed-delete), rejected alternatives, acceptance criteria.
- Insert G.1.a/b/c rows in §"Recommended sequencing" between PR3 and Phase 2.
- Final shape: ~30 LOC features README + ~150 LOC G.1 handover + ~50 LOC audit-doc edits = ~230 lines.

### PR2.5 (G.1.a) — `feat/phase-2-preflight-g1a-office-bearer-entities` — ✅ done (commit `ee441193`, PR #89, merged 2026-05-22)
- Appended 31 `entity_type='office_bearer'` rows (one per state CM seat — NOT 359; reality-correction in handover doc) to `datasets/taxonomy/entities.json`.
- Regenerated `taxonomy/entities.parquet` (185 → 216 rows).
- `entity.schema.json` v1.1 → v1.2 (extended `entity_type` enum to include `office_bearer`).
- Both old (cm_terms.json) and new (entities.parquet office_bearer rows) coexist.
- Tier-A parity oracle pins `dim_offices.office_id == entities.entity_id[entity_type='office_bearer']`.

### PR2.6 (G.1.b) — `feat/phase-2-preflight-g1b-cm-terms-reader-switch` — ✅ done (commit `cc9ad5b7`, PR #90, merged 2026-05-22)
- Rewrote `backend/yen_gov/canonical/cm_terms_seed.py` to resolve office identity from `entities.parquet WHERE entity_type='office_bearer' AND entity_code='CM'` instead of computing it from `cm_terms.json` state codes inline.
- Verified byte-identical Parquet outputs (`dim_offices.parquet`, `governments_office_holdings.parquet`, `sources.parquet`) pre- vs post-rewrite.
- New Tier-A parity oracle `backend/tests/test_g1b_cm_terms_reader_switch_parity.py`.
- JSON files stayed on disk as fallback / cross-check for one PR cycle (deleted in G.1.c).

### PR2.7 (G.1.c) — `feat/phase-2-preflight-g1c-office-holdings-consolidation` — ✅ done (commit `36e64c87`, PR #91, merged 2026-05-22)
- **Option B chosen** after Hans + Fowler + Max 3-persona review (not the originally-spec'd JSON-tree delete). Consolidated 31 per-state `cm_terms.json` into ONE long-form `datasets/taxonomy/office_holdings.json` (359 holdings + 31 office_citations).
- NEW `datasets/schemas/office-holdings.schema.json` v1.0.
- NEW `backend/yen_gov/canonical/office_holdings_seed.py` (~430 LOC, replaces `cm_terms_seed.py`).
- NEW `backend/tests/test_office_holdings_seed.py` (6 Tier-A tests).
- Frontend `frontend/src/lib/governments.ts` rewritten with in-loader field-name adapter back to the legacy `GovernmentTerm` shape (Svelte components unchanged).
- `git rm` of 31 JSON + `cm_terms_seed.py` + `test_cm_terms_seed.py` + `state_government.schema.json` + `tools/author_cm_terms.py` + `tools/lift_cm_offices_to_entities.py` + `datasets/governments/in/states/` + `datasets/governments/in/`.
- 8 docs past-tense'd; `cli.py` step 6 wiring swapped.
- Byte-identical Parquet verified 3rd time.

### PR3 — `refactor/phase-2-preflight-io-legacy-namespace` — ✅ done (rolled into T.1 commit `76bc5fde`, merged earlier)
- The audit specified PR3 as a separate step, but `backend/yen_gov/legacy/folded_indicator_writer.py` was already extracted in commit `76bc5fde` (T.1 commit message: `refactor(T.1+legacy): rename _test/ -> _ops/, lift fixtures cross-language, extract folded-indicator writer to yen_gov.legacy`). T.1 absorbed PR3 because both were structural pre-Phase-2 hygiene with overlapping import-site moves.
- On-disk verification (2026-05-22):
  - `backend/yen_gov/legacy/__init__.py` exists with namespace docstring naming the gating P.\* retirement.
  - `backend/yen_gov/legacy/folded_indicator_writer.py` exists with `OPERATIONAL_STRIP_PATHS`, `is_indicator_schema`, `maintain_folded_blocks`, `strip_operational`, `_stub_methodology`, `_stub_series_spec` all moved.
  - `backend/yen_gov/core/io.py:34-40` imports from `yen_gov.legacy.folded_indicator_writer` (aliased with leading underscore to match prior internal naming).
- §16 plan row updated in T.1 commit.

After all three, Phase 2 P.\* NFHS-5 starts on clean ground. **All steps DONE as of 2026-05-22.**

## Cross-references

- Original plan: `TODO/20260517-canonical-long-format-pivot.md`
- v2.0 citation ledger: `docs/architecture/decisions/0032-sources-citation-ledger.md`
- T.0c-ii Phase A handover (now superseded): `TODO/20260521-states-json-port-blocker-entities-ut-gap.md`
- States.json Phase B + Phase C (T.0c-ii arc closer): ✅ COMPLETE — Phase B `feat/states-json-port-phase-b-backend-consumers` merged 2026-05-22 (backend consumers ported); Phase C `feat/states-json-port-phase-c-frontend-delete` (frontend `fetchStates()` wrapper + `datasets/reference/in/states.json` + `datasets/schemas/state.schema.json` + `backend/tests/test_states_parity.py` deletions + §13 browser smoke).
- ADR-0026 (folded v4.0 artifact): documents the interim shape being retired
- ADR-0031 (boundaries codec split): needs amendment per finding #4

## Provenance

- Audit performed: 2026-05-21
- Audit triggered by: user pushback that the framing "canonical-pivot is about elections, not indicators" was wrong, AND user's question "what other short-sighted assumptions and decisions have we made and implemented in the plan that should be different if all indicators are in scope"
- Audit performed by: Gregor (Architect) persona via `runSubagent`
- Audit scope: read-only across `datasets/`, `frontend/src/lib/`, `backend/yen_gov/`
- Audit invariants checked: CLAUDE.md Holy Laws #1/#3/#4/#6/#9/#10; plan §0a/§0c/§0d/§0e/§5; ADR-0026, ADR-0031, ADR-0032
- Companion same-day work: PRs #75 (Phase A entities), #76 (workflow stale path), #77 (bio testid) all merged; live citizen site deployed for first time since PR #63

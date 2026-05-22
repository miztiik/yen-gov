# 2026-05-22 — G.1 cm_terms.json retirement: 3-PR strangler-fig handover

> **Status**: G.1.a SHIPPED (`ee441193` merge of `99952afd` on `feat/phase-2-preflight-g1a-office-bearer-entities`, PR #89). G.1.b SHIPPED (commit TBD on `feat/phase-2-preflight-g1b-cm-terms-reader-switch`, PR #TBD). G.1.c open. PR2 (`feat/phase-2-preflight-t1-status-features-audit-g1-deferred`, merged as `8fb3e935` / PR #88) descoped G.1 retirement after discovering the original Gregor audit estimate ("Pure structural, sub-day, data already in Parquet") underestimated the work; this 3-PR strangler-fig executes the honest retirement.

## TL;DR

Gregor's audit recommended G.1 (`datasets/governments/in/states/<S>/cm_terms.json` retirement) as a single-PR delete. That's WRONG. JSON is the LIVE source-of-truth; `cm_terms_seed.py:178` recompiles 31 per-state files to `governments_office_holdings.parquet` + `dim_offices.parquet` on every `emit-taxonomy` run. Delete the JSON → break the compile step → empty Parquets → citizen-facing "Your government" card breaks.

Honest retirement needs a 3-PR strangler-fig modelled on T.0c-iii (districts.json → entities.parquet):

- **G.1.a — entity-lift** (SHIPPED 2026-05-22, `ee441193` / PR #89): appended 31 `entity_type='office_bearer'` rows — ONE per state CM seat — to `datasets/taxonomy/entities.json`; regenerated `entities.parquet`. Each row's `entity_id` equals the existing `dim_offices.parquet.office_id` (e.g. `IN-S22-CM` for Tamil Nadu's CM seat). Both old (`cm_terms.json`) and new (`entities.parquet` office_bearer rows) coexist.
- **G.1.b — reader-switch** (THIS PR, SHIPPED 2026-05-22): rewrote `cm_terms_seed.py::compile_to_parquet` to resolve office identity from `entities.parquet WHERE entity_type='office_bearer' AND entity_code='CM'` instead of computing it from `cm_terms.json` state codes inline. Tenure rows still come from `cm_terms.json`. Verified byte-identical Parquet outputs (`dim_offices.parquet`, `governments_office_holdings.parquet`, `sources.parquet`) pre- vs post-rewrite. Old JSON stays on disk as fallback / cross-check for one PR cycle.
- **G.1.c — delete**: `git rm` the 31 JSON files + seed module + test + cli wiring + (if exists) `cm_terms.schema.json` + retire `datasets/governments/in/` empty dir.

Each step is a separate Tier-A commit so any bisect point keeps the citizen surface working.

### Audit-vs-reality correction (2026-05-22)

The original draft of this doc said G.1.a adds **359** office_bearer rows (one per CM term, one per President's Rule interval). That was wrong, and it conflated two different things — the same conflation Plan §0e.6 explicitly warns against ("Office identity is taxonomy; office occupancy is a fact").

Reality (verified on `main` as of `8fb3e935`):

| Concept | Lives in | Row count | Lifecycle | Hand-edited? |
| --- | --- | --- | --- | --- |
| Office IDENTITY (one per CM seat) | `dim_offices.parquet` today; G.1.a moves to `entities.parquet[entity_type='office_bearer']` | **31** (one per state/UT with a CM) | Set once; constitutional | No (compiled from JSON state codes) |
| Office OCCUPANCY (one per CM tenure) | `governments_office_holdings.parquet` | **359** (each term + each President's Rule interval) | Changes with every election / dismissal | No (compiled from JSON tenure list) |
| Source-of-truth JSON | `datasets/governments/in/states/<S>/cm_terms.json` | 31 files, ~10–20 tenures each | Hand-edited by operator | YES |

G.1.a registers the **31 office identities** in the global entities taxonomy. The 359 tenures are already canonical in `governments_office_holdings.parquet` keyed on `office_id`. After G.1.a, that `office_id` is itself a valid `entity_id` in the global dim — which is what unlocks G.1.b (`cm_terms_seed.py` can resolve office identity from entities.parquet without re-globbing the 31 JSON files just to extract state codes).

## Why a strangler-fig (not single-PR delete)

| Single-PR delete | 3-PR strangler-fig |
| --- | --- |
| `git rm` 31 JSON + `cm_terms_seed.py` in one commit | G.1.a + G.1.b + G.1.c as three commits |
| `emit-taxonomy` would skip the cm_terms step → empty Parquets at next run | Each commit leaves a working `emit-taxonomy` |
| Citizen "Your government" card breaks at HEAD until follow-up | Card works at every commit |
| Bisect-unsafe (any commit between delete + restore is broken) | Bisect-safe |
| Forces person identity into `entities.parquet` ad-hoc | G.1.a does it deliberately under Hans + Max review |

The T.0c-iii arc (district.json retirement) used exactly this shape: Phase A added 145 district rows to entities.json, Phase B switched the frontend reader, Phase C deleted the JSON. Three bisectable PRs, ~30 LOC each, zero downtime.

## File inventory (G.1 scope)

**To retire (G.1.c):**

- `datasets/governments/in/states/S01/cm_terms.json` through `datasets/governments/in/states/U08/cm_terms.json` — 31 files
- `datasets/governments/in/states/` directory itself (becomes empty)
- `datasets/governments/in/` directory itself (becomes empty)
- `backend/yen_gov/canonical/cm_terms_seed.py` — ~220 LOC; deleted entirely once entities.parquet is the source
- `backend/tests/test_cm_terms_seed.py` — full file
- `datasets/schemas/cm-terms.schema.json` — if exists; check `datasets/schemas/` before deleting
- `backend/yen_gov/cli.py` lines 117 (docstring) + 193–209 (cm_terms emit block)

**To preserve (already Parquet-native):**

- `datasets/governments/dim_offices.parquet` — keep; regenerate from entities.parquet in G.1.b
- `datasets/governments/governments_office_holdings.parquet` — keep; regenerate from entities.parquet in G.1.b
- `datasets/taxonomy/sources.parquet` — keep; G.1.a doesn't touch the Wikipedia "List of CMs" rows (already upserted there)

**To update (in G.1.a) — DONE in this PR:**

- `datasets/taxonomy/entities.json` — append **31** office_bearer rows (one per state CM seat); bump `$schema_version` 1.1 → 1.2
- `datasets/schemas/entity.schema.json` — extend `entity_type` enum with `office_bearer`; bump `x-version` 1.1 → 1.2 + add `x-changelog` entry
- `backend/yen_gov/canonical/entities_seed.py` — bump `ENTITIES_ROW_SCHEMA_VERSION` to `"1.2"`; extend `EntityType` Literal with `"office_bearer"` (no other changes — office_bearer rows project through the existing `_BaseEntity` model and the `(entity_type, entity_id)` sort)
- `tools/lift_cm_offices_to_entities.py` — NEW one-shot lift tool (text-mode append, preserves entities.json single-line row format); idempotent; precedent: `tools/fold_districts_into_entities.py` from T.0c-iii Phase A (`a3d45611`)
- `backend/tests/test_g1a_office_bearer_entity_parity.py` — NEW Tier-A parity oracle (3 tests: orphan offices, unused entities, shape)
- `datasets/taxonomy/entities.parquet` — regenerated via `python -m yen_gov emit-taxonomy`; row count 185 → 216

## Rejected alternatives (do NOT re-propose)

1. **Single-PR mega-delete** — bisect-unsafe; same anti-pattern as the (since-deleted) original T.0c-iii spec. Pre-bisect "delete + rewrite" PRs caused the cm_terms_seed to silently emit zero rows mid-history. Strangler-fig is bisect-safe by construction.
2. **Relocate JSON to `datasets/taxonomy/cm_terms/`** — relocation isn't retirement. Still 31 hand-edited JSON files in tree, still a compile-step source-of-truth, still violates Plan §2b.3 ("hand-authored is text + compiled Parquet" — `taxonomy/` is for editorial taxonomy refs that compile to Parquet, not for raw fact data).
3. **Make Parquet hand-editable (drop the compile step entirely)** — no Parquet editor exists for non-technical operators; would force every CM term update through a Python REPL. Plan §8.3 explicitly rejects this for hand-curated content.
4. **Defer indefinitely** — half-shipped G.1 is exactly the trap Gregor flagged (§"#5" pattern). The `entities.parquet` row will silently grow stale if person identity isn't centralised before Phase 2 indicator pivots reference it.
5. **Author 359 office_bearer entities (one per CM term)** — conflates office IDENTITY with office OCCUPANCY. Plan §0e.6 (G.1) explicitly separates the two: `entities.parquet` is the office-IDENTITY dim ("this seat exists, it's a Chief Minister of state X, parent is state X"); `governments_office_holdings.parquet` is the OCCUPANCY fact table ("this person held this seat from D1 to D2, party Y, regime Z"). Folding tenures into the entity dim would (a) re-introduce per-tenure churn into the supposedly-stable taxonomy, (b) duplicate the person/party/date columns that are already canonical in holdings.parquet, and (c) bake every coalition-shift footnote into the entity row, making `entity_id` non-deterministic across re-runs. Office identity is set once and rarely changes (only when a new state is created); occupancy changes with every election. Keep them apart.
6. **Use `entity_id = office:cm:<state_code>:<term_index>` format** — doesn't survive the schema pattern. `entity.schema.json` v1.1 pins `entity_id` to `^[A-Z]{2}(-[A-Z0-9]+)*$`: ASCII uppercase letters + digits + dashes only. Colons and lowercase fail validation. Use the existing `IN-<state_code>-CM` shape that `dim_offices.parquet.office_id` already carries; it satisfies the pattern, matches the office-identity (rejected #5) framing, and reuses the office_id values G.1.b's reader-switch will key on.

## Acceptance criteria per phase

### G.1.a — entity-lift (THIS PR)

- [x] `datasets/taxonomy/entities.json` gains **31** office_bearer rows (one per state CM seat — the 31 states/UTs with a `datasets/governments/in/states/<S>/cm_terms.json` file).
- [x] Each row carries `entity_id` of the form `IN-<state_code>-CM` (deterministic; matches `dim_offices.parquet.office_id`; satisfies schema pattern `^[A-Z]{2}(-[A-Z0-9]+)*$`).
- [x] Each row carries `entity_type='office_bearer'`, `entity_level='fiscal_actor'`, `entity_code='CM'`.
- [x] Each row carries `display_name` = `"Chief Minister of <state-name>"` (the office name; CM person names stay in `governments_office_holdings.parquet`).
- [x] Each row carries `parent_entity_id` = the state entity (e.g. `IN-S22` for Tamil Nadu).
- [x] Each row carries `entity_valid_from` / `entity_valid_to` copied from the parent state's validity window.
- [x] `datasets/schemas/entity.schema.json`: `x-version` 1.1 → 1.2; `office_bearer` added to `entity_type` enum; `x-changelog` extended.
- [x] `backend/yen_gov/canonical/entities_seed.py`: `ENTITIES_ROW_SCHEMA_VERSION` bumped to `"1.2"`; `EntityType` Literal extended with `"office_bearer"`.
- [x] `datasets/taxonomy/entities.parquet` regenerated via `python -m yen_gov emit-taxonomy`; row count 185 → 216.
- [x] Tier-A parity test (`backend/tests/test_g1a_office_bearer_entity_parity.py`):
      every `dim_offices.parquet.office_id` is present as an `entity_type='office_bearer'` row in `entities.parquet`, and vice versa; office_bearer rows have `entity_level='fiscal_actor'` AND a resolvable `parent_entity_id`.
- [x] `cm_terms.json` files unchanged; `cm_terms_seed.py` unchanged; `dim_offices.parquet` + `governments_office_holdings.parquet` unchanged (verify with `git diff --stat`).
- [ ] `python -m yen_gov validate --root .` clean (Tier-B).
- [ ] Full `cd backend; python -m pytest -q` green.

### G.1.b — reader-switch (THIS PR, SHIPPED 2026-05-22)

- [x] `cm_terms_seed.py::compile_to_parquet`: office identity (the 31 office_id values + display_name + parent state) is read from `entities.parquet` filter `entity_type='office_bearer' AND entity_code='CM'` instead of from `cm_terms.json` state field. Tenures continue to come from `cm_terms.json` (this PR doesn't change the source of tenure facts).
- [x] Helper `_load_office_bearer_identities()` keyed on `state_code` derived from `parent_entity_id` (`IN-S22` -> `S22`); generalises to DCM/GOV via the `role` parameter when those office_bearer rows land.
- [x] Helper `_state_display_from_label()` recovers state display name from `"Chief Minister of <state>"` label — single source of truth for the inverse of G.1.a's label format.
- [x] Function signature: `entities_json: Path` → `entities_parquet: Path`; CLI wiring (`backend/yen_gov/cli.py`) updated to pass `taxonomy_dir / "entities.parquet"`.
- [x] Existing 4 tests in `test_cm_terms_seed.py` migrated to compile entities.json -> parquet via `entities_seed.compile_to_parquet` in the fixture (mirrors real production data flow). NEW test `test_missing_office_bearer_for_state_raises` asserts a cm_terms.json with no matching office_bearer entity fails loudly.
- [x] Parity oracle in NEW `backend/tests/test_g1b_cm_terms_reader_switch_parity.py` (3 tests, Holy Law #7):
      (a) every `dim_offices` row's identity columns (office_id, entity_id, role, label) equal the matching office_bearer entity;
      (b) every holdings.office_id resolves to an office_bearer entity (no orphan tenures);
      (c) row counts stable at 31 offices / 359 holdings.
- [x] `python -m yen_gov emit-taxonomy --root .` runs clean; **Parquet outputs byte-identical** to pre-PR baseline (verified via SHA256 of all three outputs: `dim_offices.parquet`, `governments_office_holdings.parquet`, `sources.parquet`).
- [x] `cli.py` `emit-taxonomy` docstring updated: office identity now comes from entities.parquet, tenures still from cm_terms.json glob; sequencing comment notes step 5 must run before step 6.
- [ ] `python -m yen_gov validate --root .` clean (Tier-B).
- [ ] Full `cd backend; python -m pytest -q` green.
- [ ] JSON files stay on disk (next PR deletes them).
- [ ] §13 browser smoke deferred to G.1.c (no citizen-surface behaviour changed in G.1.b; outputs byte-identical).

### G.1.c — delete

- [ ] `git rm` the 31 cm_terms.json files.
- [ ] `git rm` `backend/yen_gov/canonical/cm_terms_seed.py` if entities.parquet is now sufficient (verify no other consumer).
- [ ] `git rm` `backend/tests/test_cm_terms_seed.py`.
- [ ] `git rm` `datasets/schemas/cm-terms.schema.json` if it exists.
- [ ] Update `cli.py` docstring + `emit-taxonomy` block: cm_terms references removed.
- [ ] Update `docs/architecture/data/canonical-store.md §2b.3` row for `datasets/governments/in/states/` to past-tense.
- [ ] Update `docs/research/state-government-history.md` to past-tense + cross-link entities.parquet.
- [ ] Update `docs/reference/data-coverage-report.md:62` to point at Parquet path.
- [ ] Update `docs/architecture/handover-2026-05-11.md` to past-tense (or archive if fully superseded).
- [ ] `python -m yen_gov validate --root .` clean.
- [ ] `cd backend; python -m pytest -q` clean.
- [ ] §13 browser smoke: `/s/tamil-nadu` still shows "Your government" card.

## Consumer audit (already done; for G.1.c reference)

Per memory lesson 2026-05-21 ("before `git rm`, grep ALL of backend/, tools/, docs/, admin/"):

- `backend/yen_gov/cli.py:117, :195` ✓
- `backend/yen_gov/canonical/cm_terms_seed.py` (full file) ✓
- `backend/tests/test_cm_terms_seed.py:57` ✓
- Frontend: zero direct citizen reads of cm_terms.json (cross-check with `frontend/src/lib/governments.ts` if it exists)
- Docs: 6 files listed in PR2 plan; all need past-tense edits in G.1.c

## See also

- [TODO/20260521-phase-2-preflight-audit-gregor.md](20260521-phase-2-preflight-audit-gregor.md) — Gregor's original audit (§"#5" body amended in PR2)
- T.0c-iii arc (districts.json retirement) — pattern reference; commits `266777d7` (Phase A) + `2236df11` (Phase B) + `8cf37922` (Phase C)
- [CLAUDE.md §10](../CLAUDE.md) — "before `git rm` of any file under `datasets/`" doctrine

## Provenance

- Created: 2026-05-22 by default agent during PR2 execution
- Trigger: `cm_terms_seed.py:178` audit revealed JSON is live source-of-truth, contradicting Gregor audit's "data already in Parquet" framing
- Authority for shipping G.1.a: Hans + Max (entity taxonomy decision per §0a "The One Rule")
- Authority for shipping G.1.b/c: Gregor (contract / integration)

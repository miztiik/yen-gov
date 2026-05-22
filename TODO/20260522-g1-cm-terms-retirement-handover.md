# 2026-05-22 — G.1 cm_terms.json retirement: 3-PR strangler-fig handover

> **Status**: HANDOVER artifact. No code shipped from this doc. Created when PR2 (`feat/phase-2-preflight-t1-status-features-audit-g1-deferred`) descoped G.1 retirement after discovering the original Gregor audit estimate ("Pure structural, sub-day, data already in Parquet") underestimated the work.

## TL;DR

Gregor's audit recommended G.1 (`datasets/governments/in/states/<S>/cm_terms.json` retirement) as a single-PR delete. That's WRONG. JSON is the LIVE source-of-truth; `cm_terms_seed.py:178` recompiles 31 per-state files to `governments_office_holdings.parquet` + `dim_offices.parquet` on every `emit-taxonomy` run. Delete the JSON → break the compile step → empty Parquets → citizen-facing "Your government" card breaks.

Honest retirement needs a 3-PR strangler-fig modelled on T.0c-iii (districts.json → entities.parquet):

- **G.1.a — entity-lift**: append `entity_type='office_bearer'` rows for all 359 CM terms to `datasets/taxonomy/entities.json`; regen `entities.parquet`. Both old and new shapes coexist.
- **G.1.b — reader-switch**: rewrite `cm_terms_seed.py` to read office_bearer rows from `entities.parquet` instead of `cm_terms.json` glob. Old JSON stays on disk as fallback / cross-check for one PR cycle.
- **G.1.c — delete**: `git rm` the 31 JSON files + seed module + test + cli wiring + (if exists) `cm_terms.schema.json` + retire `datasets/governments/in/` empty dir.

Each step is a separate Tier-A commit so any bisect point keeps the citizen surface working.

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

**To update (in G.1.a):**

- `datasets/taxonomy/entities.json` — append 359 office_bearer rows
- `datasets/schemas/entities.schema.json` — extend `entity_type` enum to include `office_bearer` if not already there
- `backend/yen_gov/canonical/entities_seed.py` — handle office_bearer rows in compile

## Rejected alternatives (do NOT re-propose)

1. **Single-PR mega-delete** — bisect-unsafe; same anti-pattern as the (since-deleted) original T.0c-iii spec. Pre-bisect "delete + rewrite" PRs caused the cm_terms_seed to silently emit zero rows mid-history. Strangler-fig is bisect-safe by construction.
2. **Relocate JSON to `datasets/taxonomy/cm_terms/`** — relocation isn't retirement. Still 31 hand-edited JSON files in tree, still a compile-step source-of-truth, still violates Plan §2b.3 ("hand-authored is text + compiled Parquet" — `taxonomy/` is for editorial taxonomy refs that compile to Parquet, not for raw fact data).
3. **Make Parquet hand-editable (drop the compile step entirely)** — no Parquet editor exists for non-technical operators; would force every CM term update through a Python REPL. Plan §8.3 explicitly rejects this for hand-curated content.
4. **Defer indefinitely** — half-shipped G.1 is exactly the trap Gregor flagged (§"#5" pattern). The `entities.parquet` row will silently grow stale if person identity isn't centralised before Phase 2 indicator pivots reference it.

## Acceptance criteria per phase

### G.1.a — entity-lift

- [ ] `datasets/taxonomy/entities.json` contains 359 office_bearer rows (one per CM term, one per President's Rule interval).
- [ ] Each row carries `entity_id` of the form `office:cm:<state_code>:<term_index>` (deterministic; re-running the seed produces identical IDs).
- [ ] Each row carries `display_name` = CM name verbatim (NULL for President's Rule).
- [ ] Each row carries `parent_entity_id` = the state entity (e.g. `IN-S22`).
- [ ] `datasets/taxonomy/entities.parquet` regenerated; row count = previous + 359.
- [ ] Tier-A parity test: every (state, term_start, cm_name) tuple in `cm_terms.json` appears as an office_bearer row in entities.parquet.
- [ ] `python -m yen_gov validate --root .` clean.
- [ ] `cm_terms.json` files unchanged; `cm_terms_seed.py` unchanged; Parquet outputs unchanged.

### G.1.b — reader-switch

- [ ] `cm_terms_seed.py::compile_to_parquet` rewritten: input is `entities.parquet` office_bearer rows + `sources.parquet`, NOT JSON glob.
- [ ] Parity oracle in `backend/tests/test_cm_terms_seed.py`: regenerate Parquet from JSON path AND from entities path; assert byte-identical (or row-identical if column ordering differs).
- [ ] `cli.py` `emit-taxonomy` block updated: no longer globs `cm_terms.json`; reads from entities.parquet.
- [ ] `python -m yen_gov emit-taxonomy` runs clean; Parquet outputs byte-identical to pre-PR state.
- [ ] `python -m yen_gov validate --root .` clean.
- [ ] §13 browser smoke: `/s/tamil-nadu` shows "Your government" card correctly.
- [ ] JSON files stay on disk (next PR deletes them).

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

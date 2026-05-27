# 2026-05-22 — handover: T.0c-iii districts arc — Phase C paused, Phase D arc scoped

## D.3 outcome (2026-05-22) — strangler-fig arc CLOSED

**Deleted the 6 per-state `districts.json` files + `district.schema.json`.** Original Phase C scope, finally safe to execute after D.1 (adapter retire) + D.2 (LGD backfill tool retire) removed every code-path that referenced them.

**Branch**: `feat/districts-final-delete` (this commit). **Files touched** (~25 files):

- DELETED (7): `datasets/reference/in/states/{S03,S06,S11,S22,S25,U07}/districts.json` + `datasets/schemas/district.schema.json`
- Modified (code): `backend/yen_gov/cli.py` (`emit-taxonomy` docstring stale-since-Phase-B fixed); `backend/yen_gov/canonical/entities_seed.py` (Phase B notes flipped past-tense — "deleted in Phase D.3"); `backend/tests/test_entities_seed.py` (docstring matched); `backend/yen_gov/sources/wikipedia/constituencies.py` (resolution docstring repointed to entities.json); `backend/yen_gov/core/models.py` (retirement comment past-tensed); `backend/yen_gov/core/schema_registry.py` (docstring example switched to `constituency.schema.json`); `datasets/schemas/subdistrict.schema.json` (dropped "Analogous to district.schema.json" cross-reference).
- Modified (docs): `docs/architecture/data-model.md`, `docs/architecture/data/boundaries.md` (methodology-break-markers paragraph + Further-reading bullet), `docs/architecture/backend/core.md` (DistrictsCollection mirror retirement), `docs/architecture/canonical-pivot-deletion-manifest.md`, `docs/architecture/frontend/routing.md`, `docs/architecture/backend/sources-eci-vs-wikipedia.md`, `docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md` (Future-work → "Subsequent phases (now landed)"), `docs/reference/schemas.md`, `docs/reference/data-coverage-report.md`, `docs/reference/boundary-data-sources.md`, `docs/reference/lgd-opendata.md`, `docs/how-to/run-the-pipeline.md`, `docs/research/energy-power-plants.md`.
- Modified (datasets ledger + changelog): `datasets/migration-ledger.csv` (7 new D.3 rows appended); `datasets/CHANGELOG.md` (2026-05-22 entry).
- Amended: this handover doc (D.3 outcome above); `docs/archive/plans/20260517-canonical-long-format-pivot.md` row 318 (D.3 marked DONE; arc closed).

**Known structural gap (acknowledged)**: Mahe and Yanam (U07 sub-regions) are not enumerated by LGD as standalone districts; they have no `lgd_code` and did not lift into `entities.json`. This deletion removes the only on-disk record of those two regions. Eventual fix: (a) LGD revision enumerating UT sub-regions, or (b) manual override entity rows with issuing-authority identifiers. Deferred follow-up.

**Verification**:
- `entities.parquet` SHA-256 still `771ECEC3…62243ED` — byte-stable through the entire D arc, including this final commit. Proof that file deletion has zero data effect.
- pytest backend: green (no test deletions in D.3; code edits were docstring-only).
- Tier-B `python -m yen_gov validate --root .`: 0 issues (the deleted `district.schema.json` had zero `$ref` consumers in other schemas).
- vitest frontend: green (frontend never read these files — it queries `taxonomy.entities` via DuckDB-WASM since T.0c-ii-B.2).

**§13 browser smoke**: not applicable — no frontend-runtime change.

**Arc closure**: T.0c-iii strangler-fig (Phase A → B → C → D.1 → D.2 → D.3) is **DONE**. District identity is now exclusively `entity_type='district'` rows on `datasets/taxonomy/entities.json`; wikipedia districts adapter is gone; LGD backfill tool is gone; the 6 hand-authored seed files + the collection schema are gone. Only the (still-needed) constituencies adapter remains in `sources/wikipedia/` — that AC list has no alternate source yet.

---

## D.2 outcome (2026-05-22)

**Retired the LGD backfill tool.** Hans + Gregor sibling-of-D.1.c recommendation, pre-named in ADR-0033 §Future-work. `tools/lgd/backfill_lgd_codes.py` walked the per-state `districts.json` files writing `lgd_code` back into each; with D.1 having moved district identity to `entities.json` (already carrying `lgd_code`) and D.3 about to `git rm` the per-state files, the tool has no remaining target.

**Branch**: `feat/lgd-backfill-tool-retire` (this commit). **Files touched** (4 files):

- DELETED: `tools/lgd/backfill_lgd_codes.py`
- DELETED: `backend/tests/test_lgd_backfill.py`
- Modified: `docs/architecture/data/boundaries.md` (Further-reading bullet for backfill tool removed)
- Modified: `backend/yen_gov/core/models.py` (retirement comment: dropped `lgd/backfill_lgd_codes.py` from active-consumers list; appended retirement note)
- Amended: this handover doc (D.2 outcome section above)
- Amended: `docs/archive/plans/20260517-canonical-long-format-pivot.md` row 318 (D.2 marked DONE)

**Verification**:
- `git grep backfill_lgd_codes` returns zero live (non-historical-record) hits in production code; references survive only in `datasets/migration-ledger.csv` row 218 + `datasets/schemas/district.schema.json` v3.2 changelog text (both historical artefacts — schema deleted in D.3, ledger entries are append-only history per CLAUDE.md §4).
- pytest backend, Tier-B validator, vitest frontend: all green.

**§13 browser smoke**: not applicable — backend-only deletion.

## D.1 outcome (2026-05-22)

**Chosen path: D.1.c — retire the wikipedia districts adapter entirely.** Hans + Max + Gregor consulted in parallel as custom-agent subagents (per CLAUDE.md §0a authority assignment for data-shape questions); recommendation was unanimous. See [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md) for full rationale, Bootstrap-Filter framing (Gregor), OWID precedent (Max), and the four rejected alternatives.

**Branch**: `feat/wikipedia-districts-adapter-retire` (this commit). **Files touched** (13 files):

- DELETED: `backend/yen_gov/sources/wikipedia/districts.py`
- Modified: `backend/yen_gov/sources/wikipedia/urls.py` (removed `districts_url()`)
- Modified: `backend/yen_gov/core/models.py` (removed `DistrictEntry` + `DistrictsCollection`; retirement comment in place)
- Modified: `backend/yen_gov/core/schema_registry.py` (docstring example switched to `ConstituenciesCollection`)
- Modified: `backend/yen_gov/pipeline/reference.py` (added `_district_lookup_from_entities()`; dropped districts fetch+parse+write; added `entities_path` param to `scrape_state_reference()`)
- Modified: `backend/yen_gov/cli.py` (`reference` command docstring + `entities_path` wiring + echo strip)
- Modified: `backend/tests/test_core_models.py` (deleted `test_districts_collection_round_trip`; retirement comment)
- Modified: `backend/tests/test_sources_wikipedia_live.py` (deleted `test_live_districts_tn`; trimmed `test_url_builders_for_tn` → `test_url_builder_for_tn`; rewrote `test_url_builder_rejects_unknown_state` against `ac_constituencies_url`)
- Modified: `docs/architecture/backend/sources-wikipedia.md` (retirement banner + modules-row delete + district parser section retirement + district-name resolution section sourced from entities.json)
- Modified: `docs/architecture/data-model.md` (District key entry switched to LGD; districts.json sentence updated)
- NEW: `docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md`
- Amended: this handover doc (D.1 outcome section above)
- Amended: `docs/archive/plans/20260517-canonical-long-format-pivot.md` row 318 (D.1 marked DONE)

**Non-deletion**: `tools/lgd/backfill_lgd_codes.py` + `backend/tests/test_lgd_backfill.py` + the 6 per-state `districts.json` files + `district.schema.json` remain on disk. They go in Phase D.2 + Phase D.3 respectively. The schema file is no longer referenced from any Python code path (the only caller — the deleted `DistrictsCollection._schema_id = schema_id("district.schema.json")` — is gone).

**Verification**:
- `backend/yen_gov/` repo-wide grep for `DistrictsCollection|parse_districts|districts_url|DistrictEntry` returns zero live (non-comment) hits.
- Tier-A: every `*.schema.json` still validates against the meta-schema.
- Tier-B: `python -m yen_gov validate --root .` — to be re-run before commit.
- pytest backend: to be re-run before commit.
- vitest frontend: to be re-run before commit.

**§13 browser smoke**: not applicable — backend-only change with zero frontend runtime surface.

---

> **Status (pre-D.1):** Phase A (PR #81, `a3d45611`) and Phase B (PR #82, `2c9d9712`) are MERGED. Phase C as originally scoped in `docs/archive/plans/20260517-canonical-long-format-pivot.md §0e.10.4` row 318 is **PAUSED** pending a multi-PR Phase D arc. **No destructive changes shipped in this doc-only PR.** The 6 per-state `districts.json` files + `district.schema.json` remain on disk untouched.
>
> **Why paused:** Phase C was scoped as `git rm` of 6 data files + 1 schema, on the premise that Phase B made them orphans. A pre-deletion grep audit (per the 2026-05-21 lesson "audit ALL of backend/, tools/, docs/, admin/ before `git rm` of any file under `datasets/`") surfaced 9 live consumers including an **import-time crash risk** that would have broken every `pytest` collection. The audit worked exactly as the lesson predicted: it stopped a destructive operation that would have been caught only after CI ran.
>
> **What ships in this PR:** this handover doc + a corrected status block on `§0e.10.4` row 318 ("Phase C paused, Phase D arc planned"). No source code, no data file changes.

---

## TL;DR

The 6 `datasets/reference/in/states/{S03,S06,S11,S22,S25,U07}/districts.json` files and `datasets/schemas/district.schema.json` are **NOT orphans after Phase B**. They are a fully-functioning **independent subsystem** (wikipedia districts scrape pipeline) that was outside Phase A/B scope. Retiring them properly requires its own strangler-fig arc (Phase D), not a single deletion commit.

Three Phase D PRs are required before the deletion is safe:

1. **Phase D.1** — backend model + adapter surgery: replace the wikipedia adapter's output target (open Hans/Max/Gregor design question on where it should write).
2. **Phase D.2** — repoint `tools/lgd/backfill_lgd_codes.py` from walking `*/districts.json` to reading `entities.parquet` / `entities.json`.
3. **Phase D.3** — `git rm` the 7 files + delete the model + delete the now-dead tests + doc updates. This is the original Phase C scope, finally safe to execute.

---

## What the grep audit found (verbatim, sorted by severity)

### Live PRODUCERS (still actively write `districts.json`)

1. [backend/yen_gov/cli.py:339](backend/yen_gov/cli.py#L339) — `yen-gov reference <state>` CLI command, docstring: *"One-shot Wikipedia scrape: districts.json + constituencies.json for one state."*
2. [backend/yen_gov/pipeline/reference.py:71](backend/yen_gov/pipeline/reference.py#L71) — `scrape_state_reference()` writes `output_dir / "districts.json"` via `write_artifact(…, schema_for_validation=_load_schema(schema_dir, "district.schema.json"))`.
3. [backend/yen_gov/sources/wikipedia/districts.py:33](backend/yen_gov/sources/wikipedia/districts.py#L33) — wikipedia HTML parser returning a `DistrictsCollection` payload.

### Live CONSUMERS

4. [tools/lgd/backfill_lgd_codes.py:179](tools/lgd/backfill_lgd_codes.py#L179) — walks `DISTRICTS_ROOT.glob("*/districts.json")` and writes `lgd_code` back into each file. Module docstring still treats the per-state path as the canonical target for LGD code enrichment.
5. [backend/yen_gov/pipeline/reference.py:81-84](backend/yen_gov/pipeline/reference.py#L81-L84) — `build_district_lookup([(d.name, d.id) for d in districts.districts])` is the source of `district_id` cross-references baked into the live `constituencies.json` files. Deleting `districts.json` does not crash existing `constituencies.json` reads, but the next wikipedia re-scrape would have nothing to resolve `district_id` against.

### Import-time crash risk (highest-severity blocker)

6. [backend/yen_gov/core/models.py:152-153](backend/yen_gov/core/models.py#L152-L153):
   ```python
   class DistrictsCollection(_Artifact):
       _schema_id = schema_id("district.schema.json")        # ← module-level call
       _schema_version = schema_version("district.schema.json")
   ```
   `schema_id()` / `schema_version()` raise `SchemaRegistryError` when the schema file is missing. Deleting `datasets/schemas/district.schema.json` would cause **every backend module that imports `from yen_gov.core.models import ...` to crash at import time** — that is almost the entire backend, including all `pytest` collection. A green local pytest run with the schema still present would not catch this; CI would, but only at the cost of breaking the merge gate. This is the kind of failure the 2026-05-21 lesson explicitly exists to prevent.

### Backend tests that would fail

7. [backend/tests/test_core_models.py:115-120](backend/tests/test_core_models.py#L115-L120) — constructs `DistrictsCollection(...)` and round-trips through `district.schema.json`.
8. [backend/tests/test_lgd_backfill.py:27](backend/tests/test_lgd_backfill.py#L27) — fixture declares `$schema: ".../district.schema.json"`.
9. [backend/tests/test_sources_wikipedia_live.py:103-104](backend/tests/test_sources_wikipedia_live.py#L103-L104) — round-trips wikipedia output against the schema.

### Doc / plan references (these alone would have been in-scope for the original Phase C)

- [docs/architecture/data-model.md:69](docs/architecture/data-model.md)
- [docs/how-to/run-the-pipeline.md:19](docs/how-to/run-the-pipeline.md)
- [TODO/PLAN.md:74](TODO/PLAN.md)
- [docs/archive/plans/20260517-canonical-long-format-pivot.md:318](docs/archive/plans/20260517-canonical-long-format-pivot.md) (this row updated in this PR)
- `TODO/TN-GRANULAR-GEO-PLAN.md` (multiple lines)
- [datasets/migration-ledger.csv:218](datasets/migration-ledger.csv)
- [datasets/schemas/csv.sources.schema.json:29](datasets/schemas/csv.sources.schema.json)
- `datasets/schemas/postal.schema.json` (×2 — cross-refs to `district.schema.json`)
- [datasets/schemas/subdistrict.schema.json:5](datasets/schemas/subdistrict.schema.json)

### Frontend comments only (would have been a quick scrub)

- [frontend/src/lib/data.ts:97](frontend/src/lib/data.ts#L97)
- [frontend/src/lib/data.test.ts:98](frontend/src/lib/data.test.ts#L98)
- [frontend/src/routes/StateOverview.svelte:19](frontend/src/routes/StateOverview.svelte#L19)

### Phase B regression check (mandatory per the original Phase C brief)

`git grep -nE "_load_districts_files|_district_to_entity|_DistrictsFile\b|_District\b"` returned **zero matches in source code**. Only doc/plan history mentions these symbols. **Phase B's `entities_seed.py` cleanup was complete.** The discovery is at a different subsystem layer (wikipedia adapter) that the original §0e.10.4 row 318 three-phase scope did not account for.

---

## The plan-vs-reality gap

The original Phase C brief asserted *"After Phase B the seed reads only `entities.json`, so deleting the orphan files cannot affect the parquet."* That sentence is **true for `entities.parquet`** (SHA-256 verified byte-stable across Phase A → Phase B) but the deletion would still:

1. Break `pytest` collection (import-time crash via `models.py`).
2. Break the `yen-gov reference <state>` CLI command on next invocation.
3. Break 3 backend tests.
4. Leave the LGD backfill tool with no inputs to walk.
5. Sever the `constituencies.json` → `district_id` cross-reference lineage.

Items 1–3 are the wikipedia-adapter subsystem still binding to the schema; items 4–5 are downstream tools that consume the data files. Neither was in Phase A/B scope.

---

## Four resolution options considered

| Option | Scope | Files affected | Bisect-friendly? | "Phase C complete" honest? |
|---|---|---|---|---|
| **A — Pause Phase C; schedule Phase D as multi-PR arc** *(this PR's choice)* | Repoint wikipedia adapter → entities.json/parquet, repoint LGD backfill, delete `DistrictsCollection` + adapter + 3 tests, THEN delete the 7 files. 3 small PRs. | ~3–5 per PR | ✅ Yes | ✅ Yes |
| **B — Expand Phase C into one mega-PR** | Everything in A but atomic. | ~15–20 files, ~500–800 net lines | ❌ Hard to review | ✅ Yes |
| **C — Delete 6 data files + model + tests + adapter; keep schema** | Schema becomes provably orphan, deleted in cleanup PR. | ~10 files | ⚠️ Partial | ⚠️ Schema lingers |
| **D — Delete only the 6 JSON files; everything else stays** | Next `yen-gov reference <state>` re-creates them. | ~6 + doc updates | ✅ Tiny | ❌ git log lies — wikipedia adapter still emits them on next manual run |

### Why A was chosen autonomously

User was offline when the audit completed and explicitly authorized "make good decisions". Option A is the **structurally correct** call (Fowler/engineering-craft hat):

- Option B re-creates the "atomic schema-bump fused commit" pattern, which is justified when a contract surface changes but isn't here — the wikipedia adapter is a fully separate subsystem from the canonical taxonomy seed.
- Option D would land as **misleading**: the files re-appear on next ingest, which makes `git log` lie about what "Phase C complete" means. Even though the adapter is only invoked manually, `git log` is the citation surface for what the codebase intends.
- Option C is a half-state that leaves the schema as a registered-but-dead artifact, fragile under future audits.
- Option A is the only path where each bisect point is honest and each PR reviews independently.

Per CLAUDE.md operationalSafety ("for actions that are hard to reverse… ask the user before proceeding"), a `git rm` of 7 files plus a wikipedia adapter retirement question is significant. A doc-only handover that preserves all four options for the user is the autonomous-safe move.

---

## Phase D arc sketch

### Phase D.1 — backend model + adapter surgery (DESIGN QUESTION OPEN)

**Question to resolve (Hans + Max + Gregor consult per §0a authority — data-shape decision):** where should the wikipedia districts scrape output go now that `entities.json` is the canonical truth?

Three candidate shapes:

| Shape | Where adapter writes | Pros | Cons |
|---|---|---|---|
| **D.1.a — Ephemeral sidecar** | `.runtime/wikipedia/<state>.json` | Cleanly separates operator-state from citizen-trusted data (matches §2 ephemeral runtime rule + 2026-05-20 sources v2.0 ledger pattern). Adapter remains useful for one-off comparisons / fact-checks against entities.json. | Adapter output never becomes data — it's reconnaissance only. Operator must hand-merge findings into entities.json. |
| **D.1.b — Direct entities.json patch** | `datasets/taxonomy/entities.json` (in-place edit) | Adapter is data-productive again. | Entities.json is hand-authored authoritative source; an automated writer poses a churn-vs-curation tension (per the fetched_at-smear lesson 2026-05-16 — wall-clock writers smear curated content). |
| **D.1.c — Adapter retired entirely** | (nothing) | Smallest surface. Matches §3 "never invent IDs" — district IDs come from LGD (authoritative), not wikipedia (derivative). | Loses a reconnaissance tool. If a new state is created, no automation to scrape it; hand-author only. |

**Recommended preview (subject to Hans/Max/Gregor):** D.1.c — retire the adapter entirely. Reasoning: every district added to entities.json since Phase A came through hand-authoring against LGD codes, not wikipedia scrape. The adapter has been a reconnaissance tool for the seeding phase; once seeded, its outputs would compete with the curated source for authority. Phase 2+ has no obvious use case where wikipedia-scrape would beat LGD CSV + hand-author for a new district.

If D.1.c is picked, Phase D.1 PR does:
- Delete `backend/yen_gov/pipeline/reference.py` (districts portion; constituencies portion is separate — see T.0c-iv blocker)
- Delete `backend/yen_gov/sources/wikipedia/districts.py`
- Delete the `yen-gov reference <state>` CLI command (or trim it to constituencies-only if T.0c-iv still wants it)
- Delete `DistrictsCollection` class from `backend/yen_gov/core/models.py`
- Delete `backend/tests/test_sources_wikipedia_live.py` districts portion
- Delete `backend/tests/test_core_models.py` `DistrictsCollection` round-trip
- Keep `district.schema.json` and 6 data files (deleted in D.3)

If D.1.a or D.1.b is picked, the adapter stays alive but gets its output target repointed; the schema may stay (D.1.a — sidecars validate against the same schema) or get rewritten (D.1.b — entities patch shape).

### Phase D.2 — LGD backfill tool repointing

`tools/lgd/backfill_lgd_codes.py` currently walks `datasets/reference/in/states/*/districts.json` and writes `lgd_code` back into each. After Phase D.1, those files either go away (D.1.c) or move (D.1.a). The tool needs to repoint at `datasets/taxonomy/entities.json` (filter `entity_type='district'`) and write `lgd_code` updates there.

**Open question:** is this tool still needed? Phase A's fold-in script (`tools/fold_districts_into_entities.py`, deleted in Phase B) already projected `lgd_code` from the wikipedia files into entities.json. If new districts arrive, they come with LGD codes from the curator workflow (LGD CSV is the source of record). The backfill tool's job may already be done.

**Recommended preview:** delete the tool entirely as a sibling to D.1.c. Mention in commit body that `tools/lgd/backfill_lgd_codes.py` is retired because its job (one-shot LGD enrichment of wikipedia-scraped districts) is complete and not repeatable.

### Phase D.3 — the original Phase C deletion (finally safe)

After D.1 + D.2:
- `git rm datasets/reference/in/states/{S03,S06,S11,S22,S25,U07}/districts.json` (6 files)
- `git rm datasets/schemas/district.schema.json` (1 file)
- Update the 10 doc/plan/schema-cross-ref locations listed in the audit
- Update `datasets/migration-ledger.csv` row 218
- Update `datasets/CHANGELOG.md`
- §13 browser smoke (DuckDB-WASM reads parquet, so no visible change expected)
- Backend pytest + Tier-B validator + vitest all expected green (D.1 already broke the bindings)

---

## Coverage gap (must persist into Phase D commit bodies)

Two Puducherry districts — **Mahe** and **Yanam** — were never lifted into entities.parquet because they have no `lgd_code` in their wikipedia-scraped `districts.json` entries (LGD does not enumerate them as standalone districts; they are administered under Puducherry but tracked separately for postal/electoral purposes). When Phase D.3 deletes `U07/districts.json`, the only on-disk record of these two regions disappears with it.

Per CLAUDE.md §3 ("never invent IDs"), the right disposition is **explicit coverage gap acknowledgement**, not a fabricated LGD code. Phase D.3's commit body must include a `## Known coverage gap` section calling this out so future engineers don't think it was an accident. If LGD ever publishes codes for these regions, they get hand-authored into entities.json at that point.

---

## Phase D.1 design subagent dispatch (recommended next action)

When the user returns and approves Option A, the next concrete step is a planning-subagent dispatch with the three Phase D.1 candidate shapes (D.1.a / D.1.b / D.1.c) framed for Hans + Max + Gregor consult. Subagent returns a recommended Phase D.1 PR brief; user approves; subagent executes.

Recommended subagent prompt skeleton:

```
DESIGN task for yen-gov T.0c-iii Phase D.1 — where should the wikipedia
districts scrape output go now that entities.json is the canonical truth?

Reference: TODO/20260522-districts-wikipedia-adapter-retirement-handover.md §Phase D.1.

Decide between D.1.a (ephemeral sidecar), D.1.b (direct entities.json patch),
D.1.c (retire adapter entirely). Return a recommendation with rationale,
list of affected files, and a concrete PR brief that the next subagent can
execute.

Consult Hans (governance — what does the citizen need from district reconnaissance?),
Max (indicators — is wikipedia ever the right source for a new indicator?),
Gregor (architecture — what subsystem boundary keeps adapter contract clean?).
```

The user has been doing Hans+Max+Gregor consultation manually all session; the subagent should NOT auto-execute Phase D.1 — it returns a brief, user approves, separate subagent executes.

---

## What was verified safely in this audit (no destructive moves)

- `_load_districts_files` / `_district_to_entity` / `_DistrictsFile` / `_District` symbols are **truly gone from source code** (Phase B regression check clean).
- `entities.parquet` SHA-256 still `771ECEC3C96FA1F3CD7C3EBCDAC80DA54842A77B96F96C2EB43F28A0C62243ED` — byte-stable across Phase A → Phase B → this audit.
- The 6 `districts.json` files + `district.schema.json` are byte-identical to their pre-audit state — `git status --short` shows zero modifications.

---

## Why this handover exists (process note)

The 2026-05-21 lesson in `/memories/lessons.md` says: *"before `git rm` of any file under `datasets/`, grep ALL of backend/, tools/, docs/, admin/ for the literal path string — not just the frontend. Pair the deletion with all consumer-side migrations in ONE Tier-A commit so no bisect point breaks."*

This is the audit that validates the lesson. Without the repo-wide grep, Phase C would have shipped, broken every pytest import via `models.py:152`, and required an emergency revert. The lesson worked exactly as designed: pause-before-delete found the consumer that wasn't in the plan.

This handover doc is the audit's permanent record so future engineers (and future agents) inherit the constraint rather than re-discovering it.

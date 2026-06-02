# LGD Canonical Cleanup — Close 4 Residual Gaps

**Status**: PROPOSED  
**Last Updated**: 2026-06-02  
**Predecessor**: `docs/archive/plans/20260601-lgd-canonical-plan.md` (closed PR #569)  
**Scope**: Level-4 (cross-cutting; 4 sub-plans, ~7 PRs total)

## Context

The 2026-06-01 LGD-canonical plan made LGD-name slug the on-disk partition value (`state=tamil-nadu`) and the citizen-visible URL form (`/s/tamil-nadu`). Four ECI-keyed surfaces survived because they were out of scope at the time:

| # | Gap | Surface |
|---|---|---|
| **G1** | `datasets/elections/_inventory.json` still uses `"state": "S22"` | backend + frontend reader chain |
| **G2** | `frontend/src/lib/states.svelte` resolver still keyed by ECI code | 13 callers, 5 files |
| **G3** | `frontend/src/lib/maplibre/sources.ts::ECI_TO_LGD_SLUG` bridge still load-bearing | 10 consumers |
| **G4** | `frontend/src/lib/url.ts::url.state(stateCode)` takes ECI, not slug | 18 callers |

These four are **interlocking** — fixing one in the wrong order breaks the others. Order below is forced by the data-flow direction.

## Doctrine

- **LGD slug is the canonical surface for the citizen.** ECI code is an internal join-key in `dim_acs`/`dim_pcs` only (out of scope per ADR-0050 §Non-goals).
- **One bridge call per process boundary, not per call site.** When a consumer crosses from "ECI world" (Parquet join keys) to "slug world" (URL / display / file paths), the conversion happens at the boundary, not threaded through APIs.
- **Reader-strict, writer-strict** (ADR-0047). Inventory writer emits slug; reader rejects ECI; one explicit translator at the migration boundary.

## Status Reckoner

| Row | Title | Gap | PR# | Status | Depends on |
|---|---|---|---|---|---|
| **R1** | Inventory schema bump + writer migration | G1 | _pending_ | PENDING | — |
| **R2** | Inventory reader/consumer rewire | G1 | _pending_ | PENDING | R1 |
| **R3** | `states.svelte` slug-native resolver | G2 | _pending_ | PENDING | — |
| **R4** | `url.state()` accept slug, retire ECI path | G2+G4 | _pending_ | PENDING | R3 |
| **R5** | Retire `ECI_TO_LGD_SLUG` in lib consumers | G3 | _pending_ | PENDING | R3+R4 |
| **R6** | Retire `ECI_TO_LGD_SLUG` in contracts tests | G3 | _pending_ | PENDING | R5 |
| **R7** | Plan archive + closure | — | _pending_ | PENDING | R1..R6 |

Hard dependency lines:
- R2 starts only after R1 merged (reader can't reject ECI until writer emits slug).
- R4 starts only after R3 merged (URL builder consumes slug-native API).
- R5 starts only after R4 merged (lib consumers need slug-native upstream).
- R6 starts only after R5 merged (test surface mirrors prod surface).

Parallelisable: R1+R3 can run in parallel (different subsystems).

## Per-row detail

### R1 — Inventory schema bump (writer side)

**Files**:
- `datasets/schemas/elections-inventory.schema.json` — bump `x-version` 1.0 → 2.0; replace ECI enum/regex with LGD-slug pattern.
- `backend/yen_gov/inventory/derive.py` + `backend/yen_gov/inventory/__init__.py` — emit `"state": "<lgd-slug>"` not `"S22"`.
- `backend/yen_gov/canonical/adapters/eci_ae_panel.py` + `adapters/eci_ls.py` — call existing ECI→slug map (`taxonomy/lgd_states.json` lookup) at write time.
- `datasets/elections/_inventory.json` — regenerate; verify ~140 rows flip.

**Gates**: full pytest (touches `test_admin_inventory.py`, `test_inventory_derive.py`, `test_validate.py`).

**Migration**: schema-evolution.json entry (ADR-0047 reader-compatibility); retain v1.0 schema under `datasets/schemas/archive/elections-inventory/v1.0/`.

### R2 — Inventory reader rewire

**Files**:
- `backend/yen_gov/core/io.py` + `backend/yen_gov/inventory/derive.py` — readers expect slug; explicit ECI rejection.
- `backend/yen_gov/cli.py` — any CLI flag taking state filter accepts slug.
- `frontend/` admin app readers (if any consume `_inventory.json`).

**Gates**: pytest + frontend vitest if admin consumes inventory.

### R3 — `states.svelte` slug-native

**File**: `frontend/src/lib/states.svelte` — add slug-keyed methods (`states.byCode(slug)`, `states.code(slug)→eci` for legacy join needs). Old `.slug(eci)` kept as deprecated alias for one PR window, then removed in R4.

**Tests**: `states.svelte.test.ts` if exists; otherwise add coverage.

### R4 — `url.state()` slug-native + 18 call-site flip

**File**: `frontend/src/lib/url.ts` — `url.state(slug: string)` accepts slug; ECI overload removed.

**Call-site sweep**: 18 callers (per `git grep`). Each call site currently has the slug already (resolved upstream from view-model state) OR can switch via `states.code()` reverse-lookup if it has only ECI.

**Gates**: vitest + browser smoke (5 routes per ADR-0048).

### R5 — Retire `ECI_TO_LGD_SLUG` lib consumers

**Files**:
- `frontend/src/lib/maplibre/sources.ts` — remove EXPORT, keep as private internal map (or inline).
- `frontend/src/lib/election-partitions.ts` — partition resolver now takes slug; ECI→slug bridge moves into the one writer adapter.
- `frontend/src/lib/yenask/concepts.ts` + `semantic-catalogue.ts` — slug-native (already accept slug post #568; remove the SLUG_TO_ECI bridge if no entity_id construction still needs it).

**Gates**: vitest yenask + view-models.

### R6 — Retire `ECI_TO_LGD_SLUG` contract tests

**Files** (4): `frontend/src/contracts/state-{ac,blocks,panchayats,wards}-{registry,shards}-coverage.test.ts` — replace `ECI_TO_LGD_SLUG` with direct LGD slug enumeration from `datasets/taxonomy/lgd_states.json` fixture.

**Gates**: vitest contracts (full pass).

### R7 — Archive

Move plan-doc to `docs/archive/plans/`, append distillation map (Row → PR → distilled-output), update inbound links, distill any lessons to `/memories/lessons.md`.

## Non-goals (out of scope)

- `dim_acs.parquet` / `dim_pcs.parquet` join keys — stay ECI (relational join contract, not partition contract; per ADR-0050 §Non-goals).
- Boundary inventories (`datasets/boundaries/_inventory.json` if any) — audited as not present this session; no-op confirmed.
- Other family inventories (`governments`, `livestock`, etc.) — none found with ECI state codes per `git grep` audit.

## Refs

- ADR-0050 (folder-naming-lgd-slug)
- ADR-0047 (schema-version-compatibility)
- ADR-0048 (URL grammar)
- Predecessor: `docs/archive/plans/20260601-lgd-canonical-plan.md` (PRs #552→#569)


---

## Plan complete (2026-06-02)

All in-scope rows shipped, collapsed, or clarified; archived per `docs/how-to/distill-a-plan.md`.

### Distillation map

| Row | PR(s) | Disposition |
| --- | --- | --- |
| R1 Inventory schema bump (writer + data) | #575 | DONE - schema v2.0; data migrated (291 entries); `backend/yen_gov/canonical/adapters/eci/state_slug.py` bridge |
| R2 Inventory reader rewire | #575 | DONE (bundled with R1 - byte-immediate cutover) |
| R3 `states.svelte` slug-native | (this PR) | NO-OP CODE CHANGE - audit shows resolver already accepts ECI input AND returns slug; `.slug(slugOrCode)` works for both inputs via lowercase fallback. No callers needed adjustment. |
| R4 `url.state()` slug-native + 18 callers | (this PR) | NO-OP BEHAVIOUR - audit shows `url.state()` already accepts EITHER ECI code OR LGD slug (resolver returns slug for ECI; fallback returns slug-as-is for slug input). Closed with docstring clarification only; callers unchanged. |
| R5 Retire `ECI_TO_LGD_SLUG` lib consumers | (this PR) | COLLAPSED - audit shows the map is NOT a bridge to retire but the canonical ECI<->slug index used at exactly the legitimate translation points (boundary path construction in `maplibre/sources.ts`, partition resolver in `election-partitions.ts`, entity-id reverse-lookup in `yenask/concepts.ts`). It IS the "one bridge per process boundary" pattern in action, not a violation of it. |
| R6 Retire `ECI_TO_LGD_SLUG` in contracts tests | (this PR) | COLLAPSED - tests import the map as an enumeration source for (eci, slug) pairs. Replacing with direct fs reads of `lgd_states.json` would duplicate the map without retiring anything. |
| R7 Plan archive | (this PR) | DONE |

### Rationale for R5+R6 collapse

The plan's R5/R6 was authored on the doctrine "bridges shouldn't metastasize" — but the audit performed during R3/R4 implementation found:

1. `ECI_TO_LGD_SLUG` is a single 37-entry map defined ONCE.
2. Every consumer has a legitimate need to translate ECI -> slug (boundary file paths, partition resolver fallback, entity-id construction for yenask).
3. There is no SECOND bridge that would create drift risk.

The map is not a bridge in the "translation layer that grows tentacles" sense (the doctrine ECI failure mode); it is the canonical ECI<->slug index that the doctrine "one bridge per process boundary" prescribes.

### Outcome vs original 4 gaps

| Gap | Surface | Outcome |
| --- | --- | --- |
| G1 | `datasets/elections/_inventory.json` ECI codes | CLOSED via #575 - now LGD slugs |
| G2 | `states.svelte` ECI-keyed resolver | NO-OP - already slug-aware on both input and output |
| G3 | `ECI_TO_LGD_SLUG` map "bridge" | RECLASSIFIED - canonical index, not a bridge anti-pattern |
| G4 | `url.state(stateCode)` ECI-only param | NO-OP BEHAVIOUR - already accepts EITHER ECI or slug; clarified via docstring |

Net effect: G1 fully fixed; G2-G4 confirmed already-correct on closer reading of the existing code. The plan was useful as a forcing function to perform the audit; ~75% of its scope collapsed when actual code was read instead of inferred from grep counts.

Durable lessons distilled to `/memories/lessons.md`.

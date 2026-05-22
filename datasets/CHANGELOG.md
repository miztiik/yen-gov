# `datasets/` CHANGELOG

**Scope**: artifact-level changes to files under `datasets/` that external consumers (archived embeds, downstream tooling, third-party crawlers) may have linked to or cached. Renames, relocations, format changes, deletions. Schema-level changes live in each `*.schema.json`'s `x-changelog`; this file is for the **published file inventory**.

The manifest at [`datasets/manifest.json`](manifest.json) carries a programmatic mirror via the `deprecations[]` array introduced in `manifest.schema.json` v1.2 — that's the machine-readable surface; this file is the human-readable narrative.

---

## 2026-05-22 — `reference/in/states/<S>/districts.json` + `schemas/district.schema.json` deleted (T.0c-iii Phase D.3 — closes the strangler-fig arc)

**Released in**: PR #86 (commit `<TBD>`) on branch `feat/districts-final-delete`. Closes the multi-PR T.0c-iii strangler-fig: Phase A (PR #81, `a3d45611`) → B (PR #82, `2c9d9712`) → C handover (PR #83, `70bd303e`) → D.1 wikipedia districts adapter retire (PR #84, `93a9c175`) → D.2 LGD backfill tool retire (PR #85, `c6e18416`) → **D.3 (this PR) file deletion**.

**What changed**: the 6 hand-authored per-state district lists and the `district.schema.json` collection schema were deleted from disk:

- `datasets/reference/in/states/S03/districts.json` (Bihar)
- `datasets/reference/in/states/S06/districts.json` (Gujarat)
- `datasets/reference/in/states/S11/districts.json` (Kerala)
- `datasets/reference/in/states/S22/districts.json` (Tamil Nadu)
- `datasets/reference/in/states/S25/districts.json` (West Bengal)
- `datasets/reference/in/states/U07/districts.json` (Puducherry)
- `datasets/schemas/district.schema.json` (v3.3)

**Why**: district identity was lifted into `datasets/taxonomy/entities.json` as `entity_type='district'` rows during T.0c-iii Phase A (PR #81). Phase B stripped the loader; Phase D.1 retired the wikipedia adapter that produced these files; Phase D.2 retired the LGD backfill tool that mutated them. After D.2 merged, the 6 per-state files + schema had **zero readers** across `backend/`, `frontend/`, `admin/`, `tools/`. Per CLAUDE.md §11 (schemas with zero consumers should not linger on disk) and §10 (no shadow sources), the right move is to delete.

**Migration**:

- Replacement: query `datasets/taxonomy/entities.json` filtered to `entity_type='district' AND parent_entity_id=f'IN-{state}' AND entity_valid_to IS NULL`. The frontend already does this via DuckDB-WASM against `taxonomy.entities` (migrated in T.0c-ii-B.2, see `frontend/src/lib/view-models/districts.ts::loadDistricts`).
- Backend: read `datasets/taxonomy/entities.json` (or `entities.parquet`) directly; the wikipedia districts adapter (`backend/yen_gov/sources/wikipedia/districts.py`) and its CLI surface are gone — `yen-gov reference <state>` now writes only `constituencies.json`.
- The `entities.parquet` SHA-256 invariant (`771ECEC3…62243ED`) is byte-stable through the entire D arc, including this final commit — proof that the deletion has zero data effect.

**Known structural gap**: Mahe and Yanam (U07 sub-regions) are not enumerated by LGD as standalone districts and have no `lgd_code`, so they did not lift into `entities.json` during Phase A and have no on-disk record anywhere after this PR. The eventual fix is either (a) an LGD revision enumerating UT sub-regions, or (b) a manual override entity row with an issuing-authority-defined identifier. See [ADR-0033 §Losses](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md).

**Dependencies**: requires D.1 (PR #84) and D.2 (PR #85) merged first — the adapter and backfill tool would have crashed if their target files vanished while their code still existed.

---

**Released in**: PR-O.1 (commit [`9f3a1634`](https://github.com/miztiik/yen-gov/commit/9f3a1634)). Documented (this CHANGELOG + `manifest.schema.json` v1.2 `deprecations[]` surface + frontend loader warning) in PR-O.2-minimal.

**What changed**: the elections fact table — long-format observation rows for AC-level + state-rollup + party-rollup election results — moved from `datasets/elections/observations.parquet` to `datasets/elections/election_results.parquet`. Same Hive-partitioning conventions, same `observation.schema.json` shape, identical row payload byte-for-byte. The rename decouples the family directory from the table file stem so future per-family fact tables (`energy/energy_observations.parquet`, `demography/demography_observations.parquet`, …) can sit cleanly next to dim siblings (`dim_acs.parquet`, `dim_candidates.parquet`, `dim_parties.parquet`) without filename collision.

**Why**: under the canonical pivot ([TODO/20260517-canonical-long-format-pivot.md](../TODO/20260517-canonical-long-format-pivot.md) row 1.8b) every family will publish its own fact-table-per-family; `observations.parquet` was a name inherited from a single-table-fits-all draft of the pivot that did not survive review. The Fowler two-hat split (structural rename in PR-O.1, behavioural writer retirement in PR-O.3) keeps the deploy boundary clean.

**Migration**:

- Frontend code: no action — `frontend/src/lib/duckdb.ts` resolves all paths through `datasets/manifest.json` and never hard-codes Parquet URLs.
- Direct fetch consumers: switch your `${DATA_BASE}/elections/observations.parquet` URL to `${DATA_BASE}/elections/election_results.parquet`. The manifest entry at `tables[].table_id == "elections.election_results"` carries the canonical path; do not guess.
- Archived embeds / cached URLs: the deprecation is recorded in [`datasets/manifest.json`](manifest.json) under `deprecations[]` so a 404 on `elections/observations.parquet` can be resolved programmatically to the successor.
- Downstream tooling that still resolves `observations.parquet` will trigger a one-shot `console.warn` on first call in the frontend loader (PR-O.2-minimal); the legacy file does NOT exist on disk after PR-O.1, so direct fetches return 404.

**Dependencies**: relies on `manifest.schema.json` v1.2 (`deprecations[]` field) which ships in the same release window.

---

## Format

Each entry is a level-2 heading dated `YYYY-MM-DD`, then a short paragraph describing the change, the PR / commit, the rationale, and the migration path for any external consumer who may have cached the old shape. Schema-level changes are linked to the relevant `x-changelog` block rather than duplicated here.

Add new entries on top (newest first). Do not edit historical entries except to add cross-links — the historical record is the contract that lets downstream tooling reason about what changed and when.

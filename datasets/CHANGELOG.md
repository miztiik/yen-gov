# `datasets/` CHANGELOG

**Scope**: artifact-level changes to files under `datasets/` that external consumers (archived embeds, downstream tooling, third-party crawlers) may have linked to or cached. Renames, relocations, format changes, deletions. Schema-level changes live in each `*.schema.json`'s `x-changelog`; this file is for the **published file inventory**.

The manifest at [`datasets/manifest.json`](manifest.json) carries a programmatic mirror via the `deprecations[]` array introduced in `manifest.schema.json` v1.2 — that's the machine-readable surface; this file is the human-readable narrative.

---

## 2026-05-19 — `elections/observations.parquet` renamed to `elections/election_results.parquet`

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

# AGENTS.md - admin

**Last Updated**: 2026-06-04

Canonical admin-console rationale lives in [docs/architecture/admin/overview.md](../docs/architecture/admin/overview.md); this file is only a fast module map for agents.

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **MIGRATING (2026-06-04).** Per the [CLAUDE.md](../CLAUDE.md) doctrine-in-migration banner + [the platform-reset plan](../TODO/20260603-data-and-charting-platform-reset-plan.md), the canonical store is moving from Hive-partitioned Parquet to long-format CSV under `datasets/data/`. Parquet references below are MIGRATING until the rip lands.

## Invariants

- Dev-only Svelte app on port 5174; never deployed publicly.
- Operator-console UI must not imply a production backend exists.
- Backend interactions are local developer tooling contracts, not public runtime APIs.
- **Canonical pivot.** Under the canonical store, the admin UI becomes a thin SQL surface over local DuckDB reading long-format CSV under `datasets/data/` via `read_csv(columns=...)` (MIGRATING from `datasets/<family>/*.parquet` + `datasets/taxonomy/*.parquet`). Inventory derives from `SELECT DISTINCT indicator_id FROM datapoints` JOIN the indicator catalogue; operator state (frozen / refetch_requested) writes to its CSV equivalent (MIGRATING from `datasets/taxonomy/operator_state.parquet`). Full rewrite sequenced under the platform-reset plan.
- Admin route changes need admin tests when present and integrated-browser smoke verification per [CLAUDE.md](../CLAUDE.md#13-ui-verification-mandatory-for-frontend--admin-changes).
- If package manifests change, regenerate and stage the matching `bun.lock`.

## Validation

- Use the commands in [admin overview](../docs/architecture/admin/overview.md) as the canonical source.
- Keep this file limited to structure and invariants; move rationale to docs.

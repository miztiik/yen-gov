# AGENTS.md - admin

**Last Updated**: 2026-05-17

Canonical admin-console rationale lives in [docs/architecture/admin/overview.md](../docs/architecture/admin/overview.md); this file is only a fast module map for agents.

## Invariants

- Dev-only Svelte app on port 5174; never deployed publicly.
- Operator-console UI must not imply a production backend exists.
- Backend interactions are local developer tooling contracts, not public runtime APIs.
- **Canonical pivot (ADR-0030).** Under the canonical store, the admin UI becomes a thin SQL surface over local DuckDB reading `datasets/<family>/*.parquet` + `datasets/taxonomy/*.parquet`. Inventory derives from `SELECT DISTINCT indicator_id FROM <family>` JOIN `taxonomy/indicators.parquet`; operator state (frozen / refetch_requested) writes to `datasets/taxonomy/operator_state.parquet`. Full rewrite scheduled Phase 5 of the canonical pivot.
- Admin route changes need admin tests when present and integrated-browser smoke verification per [CLAUDE.md](../CLAUDE.md#13-ui-verification-mandatory-for-frontend--admin-changes).
- If package manifests change, regenerate and stage the matching `bun.lock`.

## Validation

- Use the commands in [admin overview](../docs/architecture/admin/overview.md) as the canonical source.
- Keep this file limited to structure and invariants; move rationale to docs.

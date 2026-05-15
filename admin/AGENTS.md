# AGENTS.md - admin

**Last Updated**: 2026-05-15

Canonical admin-console rationale lives in [docs/architecture/admin/overview.md](../docs/architecture/admin/overview.md); this file is only a fast module map for agents.

## Invariants

- Dev-only Svelte app on port 5174; never deployed publicly.
- Operator-console UI must not imply a production backend exists.
- Backend interactions are local developer tooling contracts, not public runtime APIs.
- Admin route changes need admin tests when present and integrated-browser smoke verification per [CLAUDE.md](../CLAUDE.md#13-ui-verification-mandatory-for-frontend--admin-changes).
- If package manifests change, regenerate and stage the matching `bun.lock`.

## Validation

- Use the commands in [admin overview](../docs/architecture/admin/overview.md) as the canonical source.
- Keep this file limited to structure and invariants; move rationale to docs.

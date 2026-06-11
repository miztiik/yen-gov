# Archived Plans

**Last Updated**: 2026-06-11

This folder stores closed, superseded, or support plan documents. Plans here are frozen historical artifacts. They may mention retired paths, old storage formats, old branch names, or old PR topology.

## Rules for Agents

- Do not use archived plans as current contract sources.
- Use archived plans only to inspect execution history, acceptance gates, or the rationale behind a live doc.
- Current contracts live in `docs/architecture/`, `docs/concepts/`, `docs/reference/`, and `CLAUDE.md`.
- When a working doc closes, add the durable outcome to the live doc first, then move the working doc here with a completion note.

## Notable Files

| File | Purpose |
| --- | --- |
| [20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md) | Historical umbrella plan for the canonical data-store pivot. Current data-store truth is [../../architecture/data/canonical-store.md](../../architecture/data/canonical-store.md). |
| [canonical-pivot-deletion-manifest.md](canonical-pivot-deletion-manifest.md) | Historical deletion ledger moved out of `docs/architecture/`; current retired-surface enforcement lives in [../../architecture/backend/validator.md](../../architecture/backend/validator.md). |
| [canonical-pivot-migration-ledger.md](canonical-pivot-migration-ledger.md) | Historical artifact-disposition ledger moved out of `docs/architecture/`. |
| [20260609-election-experience-overhaul-plan.md](20260609-election-experience-overhaul-plan.md) | Closed election-experience overhaul plan. Current URL grammar lives in [../../architecture/frontend/url-grammar.md](../../architecture/frontend/url-grammar.md). |

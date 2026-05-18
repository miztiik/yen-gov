# Agent Guardrails

**Last Updated**: 2026-05-18

This is the rules-only digest every persona must honour. It restates `CLAUDE.md` constraints in one place so an agent can scan the constraints quickly and so other docs (ADRs, agent files, code reviews) can link to specific rules. The authoritative source remains [`CLAUDE.md`](../../CLAUDE.md); if this doc and `CLAUDE.md` disagree, `CLAUDE.md` wins and this digest gets updated.

Loaded by [`bootstrap.md`](bootstrap.md) as part of every persona's startup ritual.

## The One Rule (CLAUDE.md §0a)

**OWID is the canonical reference for socio-economic data modelling.** When any data-shape question arises, first check OWID. If OWID has solved it, adopt verbatim. Deviations must be explicitly documented in [`docs/architecture/data/canonical-store.md`](../architecture/data/canonical-store.md) with Hans + Max sign-off.

**Authority assignment** (resolves stalled agent debates):

| Decision class | Authority |
| --- | --- |
| Data shape (column types, enums, period axis, entity IDs, indicator metadata, sources schema, taxonomy) | **Hans + Max** |
| Contract / integration (schema versioning, write seams, layer boundaries, pipes-and-filters) | **Gregor** |
| Engineering craft (refactor safety, test tiers, module structure, deletion) | **Fowler** |
| UX (URL grammar, visual bounds, copy, gestures, citizen framing) | **Jony + Citizen** |

**User approval supersedes every agent and every rule.**

## Holy Laws (cite by number when relevant)

1. **Static-first production.** No backend exists at runtime. Anything the UI needs ships in the bundle.
2. **Backend = local pipeline only.** `backend/` generates data; never assume it runs in production.
3. **Contracts before logic.** Every cross-boundary payload gets a typed schema before logic.
4. **Docs = agent memory; document every design decision.** Subsystem doc next to the code change, in the same commit. ADR only when both: (a) credible rejected alternative with non-trivial reversal cost, AND (b) genuinely cross-cutting.
5. **Structural fixes only.** No band-aids. Escalate the correction level.
6. **No hardcoding.** Tunable knobs in `config/`; reference data in `datasets/`. Both schema-validated.
7. **No mocks unless asked.** Real fixtures.
8. **Open source first.** Mature OSS over custom builds.
9. **Provenance is mandatory.** Every observation row carries a `source_id` FK to `datasets/taxonomy/sources.parquet`.
10. **Tests ship with the feature.** Unit / contract / integration / e2e — pick the tier that matches the surface (`CLAUDE.md §15`). Full suite green at merge.

## Project-level non-goals (do NOT raise these)

- **Accessibility (a11y / ARIA / WCAG / axe-core / contrast / keyboard-nav / screen-reader).** Descoped 2026-05-12. Visual-clarity rules (legend has numbers, colour is one signal) stand on their own merits, not as a11y compliance.
- **Production backend.** Same as Holy Law #1 — listed for emphasis.

## Forbidden git operations (without explicit user approval)

- `git stash`
- `git reset --hard`
- `git clean -fd`
- `git checkout .` / `git restore .`
- `git add .` / `git add -A`
- `git push --force` (any form)
- Amending commits that have been pushed

Commit messages describe the change. **No AI co-author / attribution tags.**

## Path discipline (for persisted artifacts)

For anything leaving the process (JSON, logs, DB rows, emitted files, error messages, sources rows, ADR cross-links):
- Relative paths only. No drive letters, no `/home/...`.
- POSIX separators (`/`) only.
- Minimal reconstructable form.
- **No `.runtime/` references in committed artifacts.** `.runtime/` is ephemeral; state that must outlive a run goes in `datasets/`, `config/`, or `docs/`.

In-memory `Path` objects for local I/O may stay platform-native.

## Identifier discipline

Never invent IDs when an issuing authority publishes one. ISO 3166 for countries/states; ECI codes for election entities; LGD codes for districts where available. Display names are fields, never identifiers.

## Layer / dependency rules

- `frontend/` MUST NOT import from `backend/`.
- `frontend/` MUST NOT commit data files.
- `backend/` MUST NOT include UI/DOM logic.
- `backend/` is the only writer of `datasets/`.
- Cross-runtime sharing via schema-validated JSON / SQLite under `datasets/`, never code imports.
- `tools/` MUST NOT import from `backend/` runtime modules.
- Domain/core MUST NOT import adapters/infrastructure.

## Schema versioning (rules only — see `CLAUDE.md §11` for full spec)

- `x-version` is `<major>.<minor>`. No patch.
- Minor = additive, backwards-compatible.
- Major = breaking.
- Every bump adds a new `x-changelog` entry in the same commit.
- Code never hand-types schema-version literals; use `yen_gov.core.schema_registry`.
- `$id` is the schema file's **relative path** (`./<name>.schema.json`) — local, not URL. Lets IDE JSON-Schema plugins validate offline.

## Data provenance (rules only — see `CLAUDE.md §12` and [`docs/concepts/data-provenance.md`](../concepts/data-provenance.md))

Per [ADR-0030](../architecture/decisions/0030-canonical-store-duckdb-wasm.md), `datasets/taxonomy/sources.parquet` is the single sources table for the whole repo. It adopts OWID `origin.*` fields (`url_main`, `url_download`, `producer`, `citation_full`, `date_accessed`, `license`, `vintage`) plus yen-gov extensions (`source_id` PK, `content_hash`, `first_fetched_at` immutable + citizen-facing, `last_seen_at` mutable telemetry, `confidence_tier`, `is_issuing_authority`). Every observation row carries a `source_id` FK to one row in this table. No per-shard sources array. No embedded URL on the observation row.

## UI verification (for `frontend/` or `admin/` runtime changes)

Per `CLAUDE.md §13`: agent uses integrated browser tools (`open_browser_page`, `read_page`, `screenshot_page`) to confirm the change rendered, no new console errors, no new 404s. Build-clean is necessary but NOT sufficient.

## Correction levels (escalation rule)

When in doubt, choose the higher level. Level 2 and above require explicit approval before code changes (`CLAUDE.md §6`).

## Anti-patterns (do NOT)

- Assume a backend exists in production.
- Hardcode taxonomy / version numbers / magic strings.
- Store absolute paths or backslashes in persisted artifacts.
- Reference `.runtime/` paths from committed artifacts.
- Build custom HTTP / retry / parsing / validation when OSS exists.
- Swallow exceptions or silently coerce invalid input.
- Mock by default.
- Emit JSON projections of canonical data for the frontend — DuckDB-WASM reads Parquet directly (ADR-0030).
- Run CI that processes `datasets/**` — publish is plain static-file copy.
- Use `datetime.now()` as input to artifact content (use upstream content-hash + `first_fetched_at` / `last_seen_at` from `sources.parquet`).
- Propose byte-compare write seams (`write_text_if_changed` shapes). Canonical writer uses UPSERT-into-DuckDB.
- Use forbidden git commands.
- Let `TODO/` or chat logs become the source of truth.
- Pre-create empty modules "for later".
- Skip the docs update.
- Edit a `package.json` without running `bun install` and staging `bun.lock` in the same commit.

## See also

- [`bootstrap.md`](bootstrap.md) — what to load before answering.
- [`../../CLAUDE.md`](../../CLAUDE.md) — the authoritative engineering contract.
- [`../concepts/data-provenance.md`](../concepts/data-provenance.md) — provenance design rationale.

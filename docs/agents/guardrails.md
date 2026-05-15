# Agent Guardrails

**Last Updated**: 2026-05-15

This is the rules-only digest every persona must honour. It restates `CLAUDE.md` constraints in one place so an agent can scan the constraints quickly and so other docs (ADRs, agent files, code reviews) can link to specific rules. The authoritative source remains [`CLAUDE.md`](../../CLAUDE.md); if this doc and `CLAUDE.md` disagree, `CLAUDE.md` wins and this digest gets updated.

Loaded by [`bootstrap.md`](bootstrap.md) as part of every persona's startup ritual.

## Holy Laws (cite by number when relevant)

1. **Static-first production.** No backend exists at runtime. Anything the UI needs ships in the bundle.
2. **Backend = local pipeline only.** `backend/` generates data; never assume it runs in production.
3. **Contracts before logic.** Every cross-boundary payload gets a typed schema before logic.
4. **Docs = agent memory; document every design decision.** Subsystem doc next to the code change, in the same commit. ADR only when both: (a) credible rejected alternative with non-trivial reversal cost, AND (b) genuinely cross-cutting.
5. **Structural fixes only.** No band-aids. Escalate the correction level.
6. **No hardcoding.** Tunable knobs in `config/`; reference data in `datasets/`. Both schema-validated.
7. **No mocks unless asked.** Real fixtures.
8. **Open source first.** Mature OSS over custom builds.
9. **Provenance is mandatory.** Every data file carries a `sources` array.
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

For anything leaving the process (JSON, logs, DB rows, emitted files):
- Relative paths only.
- POSIX separators (`/`) only.
- Minimal reconstructable form.

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

## Data provenance (rules only — see `CLAUDE.md §12` and [`docs/concepts/data-provenance.md`](../concepts/data-provenance.md))

- Every `datasets/` file has a top-level `sources` array.
- Each entry: `{url, fetched_at}`. RFC 3339 UTC.
- Empty array = hand-authored (commit message records rationale).

## UI verification (for `frontend/` or `admin/` runtime changes)

Per `CLAUDE.md §13`: agent uses integrated browser tools (`open_browser_page`, `read_page`, `screenshot_page`) to confirm the change rendered, no new console errors, no new 404s. Build-clean is necessary but NOT sufficient.

## Correction levels (escalation rule)

When in doubt, choose the higher level. Level 2 and above require explicit approval before code changes (`CLAUDE.md §6`).

## Anti-patterns (do NOT)

- Assume a backend exists in production.
- Hardcode taxonomy / version numbers / magic strings.
- Store absolute paths or backslashes in persisted artifacts.
- Build custom HTTP / retry / parsing / validation when OSS exists.
- Swallow exceptions or silently coerce invalid input.
- Mock by default.
- Use forbidden git commands.
- Let `TODO/` or chat logs become the source of truth.
- Pre-create empty modules "for later".
- Skip the docs update.
- Edit a `package.json` without running `bun install` and staging `bun.lock` in the same commit.

## See also

- [`bootstrap.md`](bootstrap.md) — what to load before answering.
- [`../../CLAUDE.md`](../../CLAUDE.md) — the authoritative engineering contract.
- [`../concepts/data-provenance.md`](../concepts/data-provenance.md) — provenance design rationale.

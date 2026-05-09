# CLAUDE.md — yen-gov Engineering Contract

**Last Updated**: 2026-05-09

This file is the non-negotiable contract for any human or AI agent working in this repository. The full standard it derives from lives in [docs/reference/documentation-structure.md](docs/reference/documentation-structure.md). When the two disagree, **this file wins for yen-gov**; the standard is generic.

> Project description: Indian election data — schema-first ingestion, processing, and static visualization. First slice: Tamil Nadu Legislative Assembly election, May 2026.

## 1. Holy Laws (Read First, Every Session)

1. **Static-first production.** The deployed app is a static bundle on GitHub Pages. There is **no production backend**. Anything the UI needs at runtime ships in the bundle.
2. **Backend = local pipeline only.** The `backend/` (when it exists) generates data sets, optionally exposed through a small local GUI/client for the developer. It MUST NOT be assumed to exist at production runtime.
3. **Contracts before logic.** Every cross-boundary payload (config, generated data, log entry, event) gets a typed schema before logic is written.
4. **Docs = agent memory. Every design decision, however granular, is documented.** Module layout, naming, library choices, why a field is optional, why an approach was rejected, every micro-decision. The default home is the relevant subsystem doc under `docs/architecture/<area>/` (or a concept doc under `docs/concepts/`) — the rationale section sits next to the description of what was decided. ADR-style entries under `docs/architecture/decisions/` are reserved for the rare decisions that meet **both** of these tests: (a) a credible rejected alternative with non-trivial reversal cost, AND (b) genuinely cross-cutting — no single subsystem doc is the natural home. If it would fit cleanly inside one subsystem doc, it goes there, not here. The doc and the code change ship in the same commit. A code commit without its rationale doc is incomplete. No exceptions.
5. **Structural fixes only.** No band-aids, no monkey patches, no "temporary" hacks. Escalate the correction level instead.
6. **No hardcoding.** No magic strings, magic numbers, or hardcoded taxonomy. Tunable knobs live in `config/`; reference data and generated artifacts live in `datasets/`. Both are schema-validated.
7. **No mocks unless asked.** Use real implementations and real fixtures. Mocks are allowed only on the user's explicit request, or for genuinely untestable external boundaries.
8. **Open source first.** Prefer mature OSS (Tailwind, Zod/Pydantic, httpx/fetch, tenacity/p-retry, lxml, sqlite, etc.) over custom builds.
9. **Provenance is mandatory.** Every data file carries a `sources` array. No anonymous data ships. See §12.

## 2. Path Rules (Mandatory)

For anything **leaving the process** (JSON, logs, DB rows, emitted artifacts, agent memory):

- Relative paths only. No absolute paths.
- POSIX separators only (`/`). Never `\`.
- Minimal reconstructable form (no redundant prefixes).

In-memory `Path` objects for local I/O may stay platform-native. The rule applies to persisted/transmitted data only.

## 3. Repository Topology

| Directory       | Status     | Purpose                                              |
| --------------- | ---------- | ---------------------------------------------------- |
| `docs/`         | created    | Canonical knowledge (Diataxis tiers, 3-level depth)  |
| `README.md`     | created    | Entry point                                          |
| `CLAUDE.md`     | created    | This file                                            |
| `datasets/`     | created    | Schemas, reference data, generated election outputs. Owned by neither runtime; written by `backend/`, read by `frontend/` at build time. |
| `config/`       | created    | Human-edited tunable knobs only (e.g. fetch concurrency, top-N cutoff). Schemas live in `datasets/schemas/`, not here. |
| `backend/`      | created    | Local Python pipeline (fetch / parse / validate / emit). FastAPI admin wrapper deferred to Phase 4. |
| `frontend/`     | created    | Static GitHub Pages app (Svelte 5 + Vite 6 + Tailwind + d3 + maplibre-gl). UI code only — never commits data files. |
| `admin/`        | not yet    | Separate dev-only Svelte app + FastAPI (Phase 4). Never deployed publicly. |
| `tools/`        | created    | Standalone dev/ops tooling (`tools/eci_recon/`, `tools/boundaries/`). No `backend/` imports. |
| `.runtime/`     | gitignored | Ephemeral run state. `.runtime/raw/<source>/...` holds intermediate downloaded HTML for debugging (ADR-0003); `.runtime/logs/<run-id>/` holds structured logs. Never a contract surface. |
| `TODO/` `notes/`| optional   | Working scratchpads — non-authoritative              |

Create each "not yet" folder only when real code is about to land in it. Empty stubs are noise.

**Identifier convention**: never invent IDs when an issuing authority publishes one. Use ISO 3166 for countries/states, ECI codes (`S22`, `167`, `2866`, `AcGenMay2026`) for election entities, LGD codes for districts where available. Display names are fields, never identifiers.

## 4. Layer & Dependency Rules

- `frontend/` MUST NOT import from `backend/`.
- `frontend/` MUST NOT commit data files. It consumes `datasets/` at build time via Vite (e.g. `vite-plugin-static-copy`), producing a self-contained bundle.
- `backend/` MUST NOT include UI/DOM logic.
- `backend/` writes to `datasets/`; it is the only writer. Any reader (frontend build, downstream tool) treats `datasets/` as a contract surface.
- Cross-runtime sharing is via **data contracts** (schema-validated JSON / SQLite under `datasets/`), never code imports.
- `tools/` MUST NOT import from `backend/` runtime modules — tools are self-contained.
- Domain/core code MUST NOT import adapters/infrastructure (dependency direction: adapters → core, never the reverse).

## 5. Documentation Discipline

- Diataxis tiers under `docs/`: `architecture/`, `how-to/`, `concepts/`, `reference/` (+ `getting-started/`, `archive/`).
- Maximum depth: `docs/<tier>/<topic>/<file>.md`. No deeper.
- Every doc has: H1 title, `Last Updated: YYYY-MM-DD`, "See also" cross-links.
- One concept defined once; everywhere else links to it.
- Docs-only PRs are a code smell — they mean a previous PR shipped without its docs.

## 6. Correction Levels

Classify every change before starting:

| Level | Scope                                | Workflow                              |
| :---: | ------------------------------------ | ------------------------------------- |
|  0    | Comments, typos, log strings         | Direct fix                            |
|  1    | 1 file, ~50 lines, isolated bug      | Direct fix                            |
|  2    | 1–2 files, explicit behavior change  | Plan → approve → execute              |
|  3    | 2–3 files, cross-cutting             | Plan → phased execution               |
|  4    | 4+ files, structural                 | Propose breakdown first               |
|  5    | Core design / data model / runtime   | Design consultation only — pause work |

When in doubt, choose the higher level. Level 2 and above require explicit approval before code changes.

## 7. Debug Logging

- Temporary logs MUST be prefixed `[DEBUG]` (e.g. `console.log("[DEBUG] state:", state)`).
- Before finalizing any change: grep for `[DEBUG]` and remove every match.
- Re-run tests after cleanup.

## 8. Git Safety (Forbidden by Default)

Do not run any of these without explicit user approval:

- `git stash` (loses untracked files on pop/drop)
- `git reset --hard`
- `git clean -fd`
- `git checkout .` / `git restore .`
- `git add .` / `git add -A`
- `git push --force` (any form)
- Amending commits that have been pushed

Safe workflow: inspect untracked (`git status --porcelain | grep "^??"`), stage only the specific files you touched, verify with `git diff --cached --name-only`, commit on a feature branch, merge with `--no-ff`.

Commit messages describe the change. **No AI co-author / attribution tags.**

## 9. Definition of Done

A change is not done until ALL hold:

- [ ] Tests added/updated for changed behavior.
- [ ] Lint, type-check, schema validation, tests all pass.
- [ ] Canonical docs updated in `docs/` (right tier).
- [ ] Schemas bumped/migrated if any persisted contract changed.
- [ ] Every new/changed data file has a `source` field per §12.
- [ ] Module `AGENTS.md` updated if structure or invariants changed.
- [ ] No `[DEBUG]` markers left in code.
- [ ] No new hardcoded values.
- [ ] No new mocks unless explicitly requested.

## 10. Anti-Patterns (Do NOT)

- Assume a backend exists in production. It doesn't.
- Hardcode taxonomy values, version numbers, magic strings.
- Store absolute paths or backslash paths in any persisted artifact.
- Build custom HTTP / retry / parsing / validation when an OSS library exists.
- Swallow exceptions or silently coerce invalid input — fail fast at the boundary.
- Mock in tests by default.
- Use forbidden git commands (Section 8).
- Let `TODO/` or chat logs become the source of truth for architecture.
- Pre-create empty modules "for later".
- Skip the docs update.

## 11. Schema Versioning (Mandatory)

Every JSON Schema under `datasets/schemas/` carries:

- `$schema`: `https://json-schema.org/draft/2020-12/schema`
- `$id`: stable URL identifying the schema.
- `title`, `description`: human-readable.
- `x-version`: `"<major>.<minor>"` only. No patch component.
- `x-changelog`: non-empty array, oldest first. Each entry: `{ "version", "date", "description" }`. The last entry's `version` MUST equal `x-version`.

Bump rules:

- **Minor** (`1.0` → `1.1`): purely additive, backwards-compatible (new optional field, broadened enum).
- **Major** (`1.x` → `2.0`): removed/renamed field, type change, narrowed constraint, semantic shift.
- Every bump adds a new `x-changelog` entry in the same commit (Holy Law #4).

Every emitted data file under `datasets/` carries `"$schema"` (URL to the schema) and `"$schema_version"` (the version it targets). Validator rejects any file whose `$schema_version` does not match the current `x-version` of its schema (until migration support lands).

Validation is two-tier and runs in CI on every PR:

- **Tier A — schema sanity**: every `*.schema.json` validates against the JSON Schema 2020-12 meta-schema; all `$ref`s resolve; `x-version`/`x-changelog` invariants hold.
- **Tier B — data conformance**: every `*.json` under `datasets/` validates against its declared `$schema`.

Both tiers must pass before merge. No silent skips.

## 12. Data Provenance (Mandatory)

Every data file under `datasets/` (and `config/`) MUST carry a top-level `sources` array declaring where its content came from. This is non-negotiable: published artifacts are only trustworthy when their lineage is visible.

```json
"sources": [
  { "url": "https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22167.htm",
    "fetched_at": "2026-05-08T14:30:12Z" }
]
```

Each entry has two required fields:

| Field        | Meaning                                                                                       |
| ------------ | --------------------------------------------------------------------------------------------- |
| `url`        | The exact `http(s)://…` URL our pipeline fetched. Not a portal landing page when a deeper page is the real source. |
| `fetched_at` | RFC 3339 UTC timestamp of when our pipeline read that URL. Re-fetches update or extend the array. |

Three valid array shapes:

- **One entry** — the simple case: one upstream, one fetch.
- **Multiple entries** — composed/aggregated artifacts (e.g. a state-level summary citing the partywise page plus every contributing constituency page). Each entry has its own `fetched_at`.
- **Empty array** — the canonical signal for **hand-authored** content. The commit message MUST record the rationale and any reference materials. There is no `hand-authored: true` flag and no sentinel string; absence of upstream URLs *is* the statement.

What does NOT live in `sources`:

- Intermediate downloaded files under `.runtime/raw/` (per ADR-0003) — they are throwaway debug artifacts, not published data.
- Reference materials a maintainer consulted — those go in commit messages or `notes` fields, not `sources` (which is reserved for URLs the pipeline actually pulled).
- Item-level provenance overrides — removed in v3.0. Aggregated artifacts list every contributing URL at file level.

Schemas enforce this with an `array of {url, fetched_at}` constraint; the validator (CLAUDE.md §11) rejects any file missing `sources` or violating its shape.

Canonical doc: [`docs/concepts/data-provenance.md`](docs/concepts/data-provenance.md). Design rationale: [ADR-0002](docs/architecture/decisions/0002-provenance-as-sources-list.md).

## 13. Open Questions (TBD)

These are unresolved and must be answered before the corresponding work starts:

- District identifier source: LGD codes (gov.in Local Government Directory) preferred; Wikipedia slug as fallback. Confirm during Phase 0 taxonomy build.
- "Top-N + others" cutoff for per-AC results: provisional default = top 5 candidates + NOTA + collapsed "others". Confirm with real data in Phase 2.
- GitHub Actions cadence: manual dispatch only for now (results don't change post-declaration). Revisit if we add live event tracking.

Update this section as decisions are made; promote each decision into an architecture doc under `docs/architecture/`.

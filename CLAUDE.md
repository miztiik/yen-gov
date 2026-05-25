# CLAUDE.md - yen-gov Engineering Contract

**Last Updated**: 2026-05-25

Non-negotiable contract for any human or AI agent working in this repo. Derived standard: [docs/reference/documentation-structure.md](docs/reference/documentation-structure.md). When the two disagree, this file wins for yen-gov.

> Indian socio-economic + election data. Schema-first ingestion, processing, static visualization. Canonical store is Hive-partitioned Parquet read by DuckDB-WASM in the browser. All indicator families (elections, fiscal, health, energy, demography, ...) are equally important; whichever family is being worked on, go depth-first before breadth.

## 0a. The One Rule

**OWID is the canonical reference for socio-economic data modelling.** Check OWID first; adopt verbatim; document deviations in [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md) signed off by Hans + Max. See [docs/concepts/owid-alignment.md](docs/concepts/owid-alignment.md).

**Authority assignment** (resolves stalled agent debates):

| Decision class | Authority |
| --- | --- |
| Data shape - column types, enums, period axis, entity IDs, indicator metadata, source schema, taxonomy | **Hans + Max** |
| Contract / integration - schema versioning, write seams, layer boundaries, pipes-and-filters topology | **Gregor** |
| Engineering craft - refactor safety, test tiers, module structure, deletion discipline | **Fowler** |
| UX - URL grammar, visual bounds, copy, gestures, citizen-readable framing | **Jony + Citizen** |
| AI / LLM app design - model selection, prompts, RAG, agent topology, evals, tokenizer/context | **Andre** |

**User approval supersedes every agent and every rule in this file.** Amend conflicting rules in the same commit.

## 0. Non-Goals

- **Accessibility (a11y / ARIA / WCAG / axe-core).** Descoped 2026-05-12. No a11y deps, assertions, agent doctrine, or `aria-*` enforcement at project level. Re-scope by editing this entry.
- **Production backend.** See Holy Law #1.

## 1. Holy Laws (Read First, Every Session)

1. **Static-first production.** Deployed app is a static bundle on GitHub Pages. No production backend. Anything the UI needs at runtime ships in the bundle.
2. **Backend = local pipeline only.** `backend/` generates datasets; MUST NOT be assumed to exist at production runtime.
3. **Contracts before logic.** Every cross-boundary payload gets a typed schema before logic is written.
4. **Docs = agent memory.** Every design decision, however granular, is documented in the same commit as the code. Default home: relevant subsystem doc under `docs/architecture/<area>/` or concept doc under `docs/concepts/`. ADRs are reserved for cross-cutting decisions with credible rejected alternatives and non-trivial reversal cost. See [ADR-0034](docs/architecture/decisions/0034-documentation-routing-contract.md).
5. **Structural fixes only.** No band-aids, no monkey patches, no "temporary" hacks. Escalate the correction level instead.
6. **No hardcoding.** Tunable knobs live in `config/`; reference data and generated artifacts live in `datasets/`. Both are schema-validated.
7. **No mocks unless asked.** Real implementations and real fixtures. Mocks only on explicit user request or for genuinely untestable external boundaries.
8. **Open source first.** Prefer mature OSS over custom builds.
9. **Provenance is mandatory.** Every observation row carries `source_id` FK to `datasets/taxonomy/sources.parquet`. See section 12.
10. **Tests ship with the feature.** Behaviour-changing commit lands with tests at the appropriate tier (section 15). Full suite green at merge.

## 2. Path Rules

For anything leaving the process (JSON, logs, DB rows, emitted artifacts, agent memory, error messages, sources rows, ADR cross-links, dataset references):

- Relative paths only. No absolute paths. No drive letters. No `/home/...`.
- POSIX separators only (`/`). Never `\`.
- Minimal reconstructable form.

In-memory `Path` objects for local I/O may stay platform-native. Rule applies at the moment a path leaves the process.

**Ephemeral runtime.** `.runtime/` is ephemeral by definition. Agents MUST NOT reference `.runtime/` paths from any committed artifact. State that outlives a run belongs in `datasets/`, `config/`, or `docs/`.

## 3. Repository Topology

| Directory       | Status     | Purpose |
| --------------- | ---------- | ------- |
| `docs/`         | created    | Canonical knowledge (Diataxis tiers, 3-level depth) |
| `README.md`     | created    | Entry point |
| `CLAUDE.md`     | created    | This file |
| `datasets/`     | created    | Canonical store + schemas + reference data + upstream snapshots. Hive-partitioned Parquet per family. Sole writer: `backend/`. See [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md). |
| `datasets/_ops/`| created    | Operator state; not citizen-facing, not inventoried. See [datasets/_ops/README.md](datasets/_ops/README.md). |
| `config/`       | created    | Human-edited tunable knobs. Schemas live in `datasets/schemas/`. |
| `backend/`      | created    | Local Python pipeline. FastAPI admin wrapper at `backend/yen_gov/admin/`. |
| `frontend/`     | created    | Static GitHub Pages app (Svelte 5 + Vite 6 + Tailwind + d3 + maplibre-gl). Never commits data files. |
| `admin/`        | created    | Dev-only Svelte app on port 5174. Never deployed publicly. |
| `tools/`        | created    | Standalone dev/ops tooling. No `backend/` imports. |
| `.runtime/`     | gitignored | Ephemeral run state. Never a contract surface. |
| `TODO/` `notes/`| optional   | Working scratchpads - non-authoritative |

Create folders only when real code is about to land. Identifier convention: use issuing-authority IDs (ISO 3166, ECI codes, LGD codes); see [docs/reference/identifiers.md](docs/reference/identifiers.md).

## 4. Layer and Dependency Rules

- `frontend/` MUST NOT import from `backend/`.
- `frontend/` MUST NOT commit data files. Dev: Vite middleware `serveDatasets()` in [frontend/vite.config.ts](frontend/vite.config.ts) serves `datasets/` under `/data/`. Deploy: workflow copies `datasets/` into `_site/data/`. See [docs/architecture/frontend/data-loading.md](docs/architecture/frontend/data-loading.md).
- `backend/` MUST NOT include UI/DOM logic.
- `backend/` is the only writer to `datasets/`; readers treat it as a contract surface.
- Cross-runtime sharing is via data contracts under `datasets/`, never code imports.
- `tools/` MUST NOT import `backend/` runtime modules.
- Domain/core code MUST NOT import adapters/infrastructure (adapters -> core, never reverse).
- `datasets/<family>/_meadow/...` is the backend-internal meadow tier. Frontend MUST NOT fetch under `_meadow/`. See [ADR-0041](docs/architecture/decisions/0041-meadow-tier.md) + [docs/concepts/meadow-tier.md](docs/concepts/meadow-tier.md).

## 5. Documentation Discipline

- Diataxis tiers under `docs/`: `architecture/`, `how-to/`, `concepts/`, `reference/` (+ `getting-started/`, `archive/`, `research/`, `agents/`).
- Max depth: `docs/<tier>/<topic>/<file>.md`.
- Every doc: H1 title, `Last Updated: YYYY-MM-DD`, "See also" cross-links.
- One concept defined once; everywhere else links to it.
- ASCII-only in agent/customization markdown (use `-`, `->`, `>=`, "section", "INR").
- **Doc-class routing:** ADR / subsystem doc / concept doc / plan-doc - each has one valid home. See [ADR-0034](docs/architecture/decisions/0034-documentation-routing-contract.md).
- Agent memory (`AGENTS.md`, `/memories/repo/`) is derived, not authoritative; if it disagrees with `docs/`, docs win.
- Personas live under `docs/agents/`; each loads [docs/agents/bootstrap.md](docs/agents/bootstrap.md) before answering. New citizen-facing features follow [docs/how-to/distill.md](docs/how-to/distill.md). Doctrine: [docs/concepts/citizen-first.md](docs/concepts/citizen-first.md).
- Open questions live in the active plan-doc under `TODO/`, not in this file.
- Docs-only PRs are a code smell.

## 6. Correction Levels

| Level | Scope | Workflow |
| :---: | --- | --- |
|  0 | Comments, typos, log strings | Direct fix |
|  1 | 1 file, ~50 lines, isolated bug | Direct fix |
|  2 | 1-2 files, explicit behavior change | Plan -> execute once scope is clear |
|  3 | 2-3 files, cross-cutting | Plan -> phased execution |
|  4 | 4+ files, structural | Propose breakdown first |
|  5 | Core design / data model / runtime | Design consultation only - pause work |

When in doubt, choose the higher level.

## 7. Debug Logging

- Temporary logs MUST be prefixed `[DEBUG]`.
- Before finalizing: grep for `[DEBUG]` and remove every match. Re-run tests after cleanup.

## 8. Git Hygiene

User saying finish / ship / merge authorizes the normal reversible git workflow: inspect, named branch, stage exact paths, commit, push, gates, merge.

Avoid (broad / lossy / history-rewriting):

- `git stash`
- `git reset --hard`
- `git clean -fd`
- `git checkout .` / broad `git restore .`
- `git add .` / `git add -A`
- `git push --force` / `git push --force-with-lease`
- Amending pushed commits

Safe workflow: `git status --porcelain`, leave unrelated dirty files alone, stage only explicit paths, verify with `git diff --cached --name-only`, small reversible commits on a named branch, push, merge after gates pass.

Commit messages describe the change. **No AI co-author / attribution tags.**

## 9. Definition of Done

- [ ] Tests added/updated at the tier appropriate to the surface (section 15). No mocks per Holy Law #7.
- [ ] Full suite green locally before commit (`npm test` in `frontend/`, `npm run test:e2e` if frontend runtime changed, `pytest -q` in `backend/`).
- [ ] Lint, type-check, schema validation, tests all pass.
- [ ] For `frontend/` or `admin/` runtime changes: smoke-tested via integrated browser tools per section 13.
- [ ] Canonical docs updated in `docs/` (right tier).
- [ ] Schemas bumped/migrated if any persisted contract changed.
- [ ] Every new/changed observation row carries `source_id` FK (section 12).
- [ ] Module `AGENTS.md` updated if structure or invariants changed.
- [ ] No `[DEBUG]` markers left.
- [ ] No new hardcoded values.
- [ ] No new mocks unless explicitly requested.
- [ ] Lockfiles in sync with manifests. If commit touches `frontend/package.json` or `admin/package.json`, regenerate the matching `bun.lock` and stage in the SAME commit. The Pages workflow runs `bun install --frozen-lockfile` and will reject any desync.

## 10. Anti-Patterns (Do NOT)

- Assume a backend exists in production.
- Hardcode taxonomy values, version numbers, magic strings.
- Store absolute / backslash paths in any persisted artifact.
- Build custom HTTP / retry / parsing / validation when an OSS library exists.
- Swallow exceptions or silently coerce invalid input - fail fast at the boundary.
- Mock in tests by default.
- Use `datetime.now()` in data-row content (observation provenance, indicator vintage, citizen-facing footers). Wall-clock at write time is operational telemetry, not provenance. Carve-out: control-plane artifacts (`datasets/manifest.json`, `.runtime/logs/`) MAY stamp `generated_at`. See [docs/concepts/data-provenance.md](docs/concepts/data-provenance.md) and [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md).
- Propose `write_text_if_changed`-style byte-compare helpers at write seams. Fix non-determinism upstream of the write seam.
- Re-litigate the sources-table design (domain-as-identity, drop-the-table, add-`content_hash`-back, require-`citation_full`). See [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md) Rejected A/B/C/D.
- Walk the real on-disk corpus from a `pytest` test or live HTTP smoke test. That is Tier-B (section 11), local-only via `python -m yen_gov validate --root .`. Inject root via env var, use `tmp_path` fixtures in tests. See [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md).
- Emit JSON projections of canonical data for the citizen frontend. Frontend reads Parquet via DuckDB-WASM only.
- Run CI that processes `datasets/**`. Publish is plain static-file copy; CI gates are lint, type-check, pytest, frontend build, Playwright only.
- Use broad / lossy / history-rewriting git commands (section 8).
- Let `TODO/`, chat logs, `AGENTS.md`, or `/memories/` become the source of truth for architecture.
- Pre-create empty modules "for later".
- Skip the docs update.
- Edit `package.json` without running `bun install` and staging the resulting `bun.lock` in the same commit.
- Create new files under `datasets/indicators/in/<topic>/<id>.json`. That path is retiring per [ADR-0041](docs/architecture/decisions/0041-meadow-tier.md). New backend-internal parsed rows go to `datasets/<family>/_meadow/<source>/<vintage>/<file>.json`; citizen-facing canonical data goes to `datasets/<family>/<family>_<role>.parquet`. Enforced by Tier-B; see [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md).
- Author `id_aliases[]` on `datasets/taxonomy/indicators.json` without a paired `deprecated_in: "YYYY-MM-DD"`. Enforced by Tier-B `tier_b_indicator_alias_window` (60-day window); see [datasets/schemas/indicator-catalogue.schema.json](datasets/schemas/indicator-catalogue.schema.json) v1.1.
- Encode topic membership as a prefix on `indicator_id`. The id is `<entity>-<measure>-<unit>-<facet>` kebab-case; topic membership lives on M:N rows in `datasets/taxonomy/indicator_topic_tags.parquet`. See [docs/concepts/indicator-naming.md](docs/concepts/indicator-naming.md).

## 11. Schema Versioning

Every JSON Schema under `datasets/schemas/` carries:

- `$schema`: `https://json-schema.org/draft/2020-12/schema`
- `$id`: relative path (`./<name>.schema.json`). Local `$id` only.
- `title`, `description`.
- `x-version`: `"<major>.<minor>"` only.
- `x-changelog`: non-empty array, oldest first; last entry's `version` MUST equal `x-version`.

Bump rules:

- **Minor** (`1.0` -> `1.1`): purely additive, backwards-compatible.
- **Major** (`1.x` -> `2.0`): removed/renamed field, type change, narrowed constraint, semantic shift.
- Every bump adds a new `x-changelog` entry in the same commit.
- **Code never hand-types schema-version literals.** Source via `yen_gov.core.schema_registry.schema_version("<file>")` / `schema_id("<file>")`.

Every emitted data file under `datasets/` carries `"$schema"` and `"$schema_version"`. Validation has two tiers (Tier A always-on in `pytest -q`; Tier B on-demand local via `python -m yen_gov validate --root .`). See [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md).

## 12. Data Provenance

Every observation row in every Parquet family under `datasets/` carries a `source_id` FK to one row in `datasets/taxonomy/sources.parquet`. Provenance is a **citation ledger**, one row per `(producer, title, vintage)` triple, not per fetch event. Adopts OWID `origin.*` fields verbatim plus four yen-gov extensions for confidence + verifiability.

Schema (11 columns, 8 required + 3 optional): [docs/architecture/data/canonical-store.md section 5](docs/architecture/data/canonical-store.md). Rationale + rejected designs: [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md). v3.0 `vintage` sharpening (publisher edition vs operator snapshot window): [ADR-0042](docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md). Concept: [docs/concepts/data-provenance.md](docs/concepts/data-provenance.md).

Build `source_id` via `backend.yen_gov.canonical.citation.derive_source_id`; never hand-author.

## 13. UI Verification (Frontend / Admin)

Any change touching `frontend/` or `admin/` runtime MUST be verified by the agent using integrated browser tools, not deferred to the human.

Minimum loop:

1. Confirm dev server up (`http://localhost:5173/` frontend, `http://localhost:5174/` admin); start if not.
2. `open_browser_page` / `navigate_page` to affected route(s) plus one cross-route smoke.
3. `read_page` and confirm: (a) new copy/structure renders, (b) no new `[error]` console events, (c) no new `404`.
4. If layout-sensitive: `screenshot_page` to confirm visual intent.
5. Only then mark done.

Does not apply to pure backend / pipeline / docs / schema-only changes.

## 14. Test Coverage Policy

Four tiers - **Unit / Contract / Integration / End-to-end**. Change without appropriate-tier test in same commit is a Definition-of-Done failure. Mock carve-outs: (a) `fetch` in loader unit tests, (b) explicit user request. No pytest test walks the real corpus; use `tmp_path` fixtures injected via env var.

Per-tier matrix, commands, fixture conventions: [docs/architecture/testing.md](docs/architecture/testing.md).

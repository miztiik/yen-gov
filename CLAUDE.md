# CLAUDE.md — yen-gov Engineering Contract

**Last Updated**: 2026-05-18

This file is the non-negotiable contract for any human or AI agent working in this repository. The full standard it derives from lives in [docs/reference/documentation-structure.md](docs/reference/documentation-structure.md). When the two disagree, **this file wins for yen-gov**; the standard is generic.

> Project description: Indian socio-economic + election data — schema-first ingestion, processing, and static visualization. Canonical store is Hive-partitioned Parquet read by DuckDB-WASM in the browser. First slice: Tamil Nadu (elections), then national/state socio-economic indicators. Depth first before breadth.

## 0a. The One Rule (project canonical reference)

**OWID is the canonical reference for socio-economic data modelling.** Our World in Data has solved most of the data-shape questions yen-gov faces: long-format observations, integer year axis, indicator metadata, source provenance, methodology breaks, entity taxonomy. When any data-shape question arises, first check OWID. If OWID has solved it, adopt verbatim. If yen-gov must deviate (India-specific need), document the deviation explicitly in [`docs/architecture/data/canonical-store.md`](docs/architecture/data/canonical-store.md) with rationale signed off by Hans + Max.

**Authority assignment** (when an agent debate stalls, this resolves it):

| Decision class | Authority |
| --- | --- |
| Data shape — column types, enums, period axis, entity IDs, indicator metadata, source schema, taxonomy choices | **Hans + Max** (data + governance + OWID precedent) |
| Contract / integration — schema versioning mechanics, write seams, layer boundaries, pipes-and-filters topology | **Gregor** |
| Engineering craft — refactor safety, test tiers, module structure, code organisation, deletion discipline | **Fowler** |
| UX — URL grammar, visual bounds, copy, gestures, citizen-readable framing | **Jony + Citizen** |

**User approval supersedes every agent and every rule in this file.** If the user has approved a direction, follow it. Do not re-debate. Amend the rules that conflict in the same commit as the change.

## 0. Non-Goals (Project-Level Descopes)

Explicit non-goals for yen-gov. Anything in this list is **out of scope** — do not add tests, lint rules, dependencies, agent doctrine, or design constraints for it. Revisiting requires an explicit user decision logged here as a removal.

- **Accessibility (a11y / ARIA / WCAG / axe-core).** Descoped 2026-05-12 by user direction. No `axe-core`, `@axe-core/playwright`, contrast-ratio assertions, screen-reader spec, keyboard-nav spec, or `aria-*` enforcement at project level. The legend-has-numbers / colour-is-one-signal patterns remain in the design system because they aid **visual clarity for sighted citizens**, not because they satisfy a WCAG criterion. Agents (UI/UX Lead, Citizen User) MUST NOT raise a11y as a blocker, MUST NOT add a11y checklists to specs, and MUST NOT propose `aria-*` attributes as required work. If a future commit chooses to add an `aria-label` for clarity, that is fine; framing it as compliance is not. To re-scope a11y, edit this entry.
- **Production backend.** See Holy Law #1 — listed here as a reminder, not a duplicate.

## 1. Holy Laws (Read First, Every Session)

1. **Static-first production.** The deployed app is a static bundle on GitHub Pages. There is **no production backend**. Anything the UI needs at runtime ships in the bundle.
2. **Backend = local pipeline only.** The `backend/` (when it exists) generates data sets, optionally exposed through a small local GUI/client for the developer. It MUST NOT be assumed to exist at production runtime.
3. **Contracts before logic.** Every cross-boundary payload (config, generated data, log entry, event) gets a typed schema before logic is written.
4. **Docs = agent memory. Every design decision, however granular, is documented.** Module layout, naming, library choices, why a field is optional, why an approach was rejected, every micro-decision. The default home is the relevant subsystem doc under `docs/architecture/<area>/` (or a concept doc under `docs/concepts/`) — the rationale section sits next to the description of what was decided. ADR-style entries under `docs/architecture/decisions/` are reserved for the rare decisions that meet **both** of these tests: (a) a credible rejected alternative with non-trivial reversal cost, AND (b) genuinely cross-cutting — no single subsystem doc is the natural home. If it would fit cleanly inside one subsystem doc, it goes there, not here. The doc and the code change ship in the same commit. A code commit without its rationale doc is incomplete. No exceptions.
5. **Structural fixes only.** No band-aids, no monkey patches, no "temporary" hacks. Escalate the correction level instead.
6. **No hardcoding.** No magic strings, magic numbers, or hardcoded taxonomy. Tunable knobs live in `config/`; reference data and generated artifacts live in `datasets/`. Both are schema-validated.
7. **No mocks unless asked.** Use real implementations and real fixtures. Mocks are allowed only on the user's explicit request, or for genuinely untestable external boundaries.
8. **Open source first.** Prefer mature OSS (Tailwind, Zod/Pydantic, httpx/fetch, tenacity/p-retry, lxml, sqlite, etc.) over custom builds.
9. **Provenance is mandatory.** No anonymous data ships. Every observation row carries a `source_id` FK to `datasets/taxonomy/sources.parquet`. See §12.
10. **Tests ship with the feature.** Every behaviour-changing commit lands with the tests that prove it works AND the tests that would have caught the bug had it existed before. The full suite (`npm test` in `frontend/`, `pytest -q` in `backend/`) MUST be green at merge. Coverage is measured across four tiers — unit, contract, integration, end-to-end — and a feature is incomplete if the tier appropriate to its surface is missing. "I'll add tests later" is a band-aid (§5). See §15 for the per-tier policy.

## 2. Path Rules (Mandatory)

For anything **leaving the process** (JSON, logs, DB rows, emitted artifacts, agent memory, error messages, sources rows, ADR cross-links, dataset references):

- Relative paths only. No absolute paths. No drive letters (`C:\...`). No `/home/...`.
- POSIX separators only (`/`). Never `\`.
- Minimal reconstructable form (no redundant prefixes).

In-memory `Path` objects for local I/O may stay platform-native. The rule applies to the moment a path leaves the process.

**Ephemeral runtime.** Anything written under `.runtime/` is ephemeral by definition. Agents MUST NOT reference `.runtime/` paths from any committed artifact (schema, doc, dataset, code comment, log record that ships). State that needs to outlive a single run belongs in `datasets/`, `config/`, or `docs/`.

## 3. Repository Topology

| Directory       | Status     | Purpose                                              |
| --------------- | ---------- | ---------------------------------------------------- |
| `docs/`         | created    | Canonical knowledge (Diataxis tiers, 3-level depth)  |
| `README.md`     | created    | Entry point                                          |
| `CLAUDE.md`     | created    | This file                                            |
| `datasets/`     | created    | Canonical store + schemas + reference data + upstream snapshots. Hive-partitioned Parquet per family (`elections/`, `energy/`, `demography/`, …) read by DuckDB-WASM in the browser. Sole writer is `backend/`. Sole reader at runtime is the static frontend via the Pages domain. See [`docs/architecture/data/canonical-store.md`](docs/architecture/data/canonical-store.md). |
| `config/`       | created    | Human-edited tunable knobs only (e.g. fetch concurrency, top-N cutoff). Schemas live in `datasets/schemas/`, not here. |
| `backend/`      | created    | Local Python pipeline (fetch / parse / validate / emit). FastAPI admin wrapper at `backend/yen_gov/admin/` (Phase 4 v0 — Inventory only). |
| `frontend/`     | created    | Static GitHub Pages app (Svelte 5 + Vite 6 + Tailwind + d3 + maplibre-gl). UI code only — never commits data files. |
| `admin/`        | created    | Separate dev-only Svelte app (Vite, port 5174) for the operator console. Never deployed publicly. v0 ships the Inventory panel; Schemas / Pipeline / Patches panels follow. |
| `tools/`        | created    | Standalone dev/ops tooling (`tools/eci_recon/`, `tools/boundaries/`). No `backend/` imports. |
| `.runtime/`     | gitignored | Ephemeral run state. `.runtime/raw/<source>/...` holds intermediate downloaded HTML for debugging (ADR-0003); `.runtime/logs/<run-id>/` holds structured logs. Never a contract surface. |
| `TODO/` `notes/`| optional   | Working scratchpads — non-authoritative              |

Create each "not yet" folder only when real code is about to land in it. Empty stubs are noise.

**Identifier convention**: never invent IDs when an issuing authority publishes one. Use ISO 3166 for countries/states, ECI codes (`S22`, `167`, `2866`, `AcGenMay2026`) for election entities, LGD codes for districts where available. Display names are fields, never identifiers.

## 4. Layer & Dependency Rules

- `frontend/` MUST NOT import from `backend/`.
- `frontend/` MUST NOT commit data files. At dev time a Vite middleware (`serveDatasets()` in [`frontend/vite.config.ts`](frontend/vite.config.ts)) serves `datasets/` under `/data/`; at deploy time the workflow copies `datasets/` into `_site/data/`. Same `fetch('/data/<rel>')` URL in both modes. See [`docs/architecture/frontend/data-loading.md`](docs/architecture/frontend/data-loading.md).
- `backend/` MUST NOT include UI/DOM logic.
- `backend/` writes to `datasets/`; it is the only writer. Any reader (frontend build, downstream tool) treats `datasets/` as a contract surface.
- Cross-runtime sharing is via **data contracts** (schema-validated JSON / SQLite under `datasets/`), never code imports.
- `tools/` MUST NOT import from `backend/` runtime modules — tools are self-contained.
- Domain/core code MUST NOT import adapters/infrastructure (dependency direction: adapters → core, never the reverse).

## 5. Documentation Discipline

- Diataxis tiers under `docs/`: `architecture/`, `how-to/`, `concepts/`, `reference/` (+ `getting-started/`, `archive/`, `research/`, `agents/`).
- Maximum depth: `docs/<tier>/<topic>/<file>.md`. No deeper.
- Every doc has: H1 title, `Last Updated: YYYY-MM-DD`, "See also" cross-links.
- One concept defined once; everywhere else links to it.
- Agent memory is derived, not authoritative. Per-module `AGENTS.md` files and `/memories/repo/` are fast-entry indexes that point back to canonical docs; if they disagree with `docs/`, the docs win and the derived memory gets updated or deleted.
- Personas (Citizen, Hans, Max, Gregor, Fowler, Jony) live as canonical docs under `docs/agents/` with thin wrappers in `.claude/skills/bootstrap/` and `.github/agents/`. Every persona loads [`docs/agents/bootstrap.md`](docs/agents/bootstrap.md) before answering. New citizen-facing features **follow** the seven-step procedure in [`docs/how-to/distill.md`](docs/how-to/distill.md) — it is a runbook, not an automated skill; the seven persona handoffs are driven manually (or by a future orchestrator under `tools/`), not by the harness. Doctrine: [`docs/concepts/citizen-first.md`](docs/concepts/citizen-first.md).
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

- [ ] Tests added/updated for changed behavior, at the tier appropriate to the surface (§15). For frontend code that means at minimum a vitest unit/contract test; for citizen-visible UI, also one Playwright assertion in `frontend/e2e/`. For backend pipeline / parsers / loaders, a `pytest` test against a real fixture (no mocks per Holy Law #7).
- [ ] Full test suite green locally before commit — `npm test` in `frontend/`, `npm run test:e2e` in `frontend/` if the change touches `frontend/` runtime, `pytest -q` in `backend/`. A red suite at commit time is a Definition-of-Done failure, not a follow-up ticket.
- [ ] Lint, type-check, schema validation, tests all pass.
- [ ] **For any change touching `frontend/` or `admin/` runtime behaviour: smoke-tested via the agent's integrated browser tools** against a running dev server (`http://localhost:5173/` for frontend, `5174` for admin). Verify both the page actually changed (`read_page` snapshot, not just code diff) AND no new console errors / 404s appeared on the affected route. See §13 for the policy.
- [ ] Canonical docs updated in `docs/` (right tier).
- [ ] Schemas bumped/migrated if any persisted contract changed.
- [ ] Every new/changed observation row carries a `source_id` FK to `datasets/taxonomy/sources.parquet` per §12.
- [ ] Module `AGENTS.md` updated if structure or invariants changed.
- [ ] No `[DEBUG]` markers left in code.
- [ ] No new hardcoded values.
- [ ] No new mocks unless explicitly requested.
- [ ] **Lockfiles in sync with manifests.** If the commit touches `frontend/package.json` or `admin/package.json`, the matching `bun.lock` MUST be regenerated (`bun install` in that directory) and staged in the SAME commit. The Pages workflow runs `bun install --frozen-lockfile` and will reject any desync with `error: lockfile had changes, but lockfile is frozen`, breaking the public site until fixed. Verify with `git status --porcelain <dir>/package.json <dir>/bun.lock` — both must be staged together, or neither.

## 10. Anti-Patterns (Do NOT)

- Assume a backend exists in production. It doesn't.
- Hardcode taxonomy values, version numbers, magic strings.
- Store absolute paths or backslash paths in any persisted artifact.
- Build custom HTTP / retry / parsing / validation when an OSS library exists.
- Swallow exceptions or silently coerce invalid input — fail fast at the boundary.
- Mock in tests by default.
- Use `datetime.now()` as input to **data-row CONTENT** (observation provenance, indicator vintage, citizen-facing doc footers). Wall-clock at write time is operational telemetry, NOT provenance. Under the canonical pivot, `sources` is a TABLE keyed by `(url, content_hash)`; per-row provenance is `source_id` (FK); `first_fetched_at` (immutable, citizen-facing) + `last_seen_at` (mutable telemetry) replace the smeared `fetched_at` field. Re-running ingest with byte-identical upstream MUST leave observation/dimension Parquet bytes unchanged. **Carve-out**: control-plane artifacts (`datasets/manifest.json`, run logs under `.runtime/logs/`) MAY stamp `generated_at` with wall-clock — they describe operator state, not citizen-facing data, and the writer that consumes them tolerates churn. See [data provenance](docs/concepts/data-provenance.md).
- Propose `write_text_if_changed`-style byte-compare helpers at write seams. Bytes ≠ data; if a re-run produces different bytes from identical upstream, fix the non-determinism upstream of the write seam. Canonical writer uses UPSERT-into-DuckDB + sorted Parquet emit (ADR-0030).
- Walk the real on-disk corpus (`datasets/**`, `config/**`) from a `pytest` test, or from an HTTP smoke test that hits a live FastAPI route which itself walks the corpus. That is Tier-B conformance (§11), which is local-only via `python -m yen_gov validate --root .`. Pytest tests assert CODE correctness against `tmp_path` fixtures; they MUST NOT assert DATA quality against the real repo. Symptoms: a single test takes >5s; the fix is "add the missing file" not "change the code"; the test fails on a teammate's machine after they pull a corpus-only change. Doctrine fix pattern: inject the root via a `_repo_root()` helper reading an env var (e.g. `YEN_GOV_REPO_ROOT`), default to the real repo at runtime, in tests `monkeypatch.setenv(...)` to point at a `tmp_path` fixture corpus. Reference fix: commit `7d407d0`. Doctrine: [`docs/architecture/backend/validator.md`](docs/architecture/backend/validator.md).
- Emit JSON projections of canonical data for the citizen frontend. Under the canonical pivot, frontend reads Parquet via DuckDB-WASM only. No precomputed per-shard JSON, no parallel projection tree, no JSON shadow of the Parquet rows. Pre-pivot per-shard JSON under `datasets/_old/` is read-only and deleted at end of Phase 1.
- Run CI that processes `datasets/**`. The publish pipeline is plain static-file copy via GitHub Pages from `main`. The only CI gates are lint, type-check, pytest, frontend build, Playwright — none of which touch `datasets/` contents.
- Use forbidden git commands (Section 8).
- Let `TODO/` or chat logs become the source of truth for architecture.
- Let `AGENTS.md` or `/memories/` become a shadow source of truth instead of linking back to `docs/`.
- Pre-create empty modules "for later".
- Skip the docs update.
- Edit a `package.json` without running `bun install` and staging the resulting `bun.lock` in the same commit. The deploy workflow uses `--frozen-lockfile`; a desync silently stops the site from updating until someone notices and pushes a lockfile-only commit.

## 11. Schema Versioning (Mandatory)

Every JSON Schema under `datasets/schemas/` carries:

- `$schema`: `https://json-schema.org/draft/2020-12/schema`
- `$id`: relative path to the schema file (`./<name>.schema.json`). Local `$id` so VS Code / IDE JSON-Schema plugins validate offline. No URL `$id`.
- `title`, `description`: human-readable.
- `x-version`: `"<major>.<minor>"` only. No patch component.
- `x-changelog`: non-empty array, oldest first. Each entry: `{ "version", "date", "description" }`. The last entry's `version` MUST equal `x-version`.

Bump rules:

- **Minor** (`1.0` → `1.1`): purely additive, backwards-compatible (new optional field, broadened enum).
- **Major** (`1.x` → `2.0`): removed/renamed field, type change, narrowed constraint, semantic shift.
- Every bump adds a new `x-changelog` entry in the same commit (Holy Law #4).
- **Code never hand-types schema-version literals.** Models and composers MUST source `_schema_version` / schema-id values via `yen_gov.core.schema_registry.schema_version("<file>")` / `schema_id("<file>")`. Hand-typed `_schema_version = "x.y"` or `SCHEMA_VERSION = "..."` constants in production code are a smell — they re-introduce the shadow-copy drift the registry exists to prevent. Test fixtures may seed legacy version strings on purpose (e.g. to exercise a migration path); production emitters may not.

Every emitted data file under `datasets/` carries `"$schema"` (URL to the schema) and `"$schema_version"` (the version it targets). Validator rejects any file whose `$schema_version` does not match the current `x-version` of its schema (until migration support lands).

Validation has two tiers with different homes:

- **Tier A — schema sanity** (always-on, in `pytest -q`): every `*.schema.json` validates against the JSON Schema 2020-12 meta-schema; all `$ref`s resolve; `x-version`/`x-changelog` invariants hold; the validator rejects malformed JSON. Tested with `tmp_path` fixtures in `backend/tests/test_validate.py` — fast, code-driven, runs on every commit.
- **Tier B — corpus conformance** (on-demand, local): every `*.json` under `datasets/` and `config/` validates against its declared `$schema`. Run via `python -m yen_gov validate --root .` before committing changes to `datasets/**`, `config/**`, or `datasets/schemas/**`. Not gated in CI: the publish workflow ([`deploy-site.yml`](.github/workflows/deploy-site.yml)) copies `datasets/` into `_site/data/` as static bytes and never re-validates them; the consumer-side ajv contract test ([`frontend/src/contracts/datasets-conform.test.ts`](frontend/src/contracts/datasets-conform.test.ts)) is the runtime-shape gate that runs in `frontend-vitest`. See [`docs/architecture/backend/validator.md`](docs/architecture/backend/validator.md).

## 12. Data Provenance (Mandatory)

Every observation row in every Parquet family under `datasets/` carries a `source_id` foreign key pointing at one row in `datasets/taxonomy/sources.parquet`. Provenance is a **table**, not a per-shard array. The sources table adopts OWID's `origin.*` field schema verbatim (per §0a "The One Rule") plus a small set of yen-gov extensions:

| Field | Source | Meaning |
| --- | --- | --- |
| `source_id` (PK) | yen-gov | stable identifier; FK target on every observation row |
| `url_main` | OWID | landing / about page URL |
| `url_download` | OWID | direct download URL (same as `url_main` for HTML scrapes) |
| `producer` | OWID | publisher org (e.g. "Election Commission of India") |
| `citation_full` | OWID | full citation string |
| `date_accessed` | OWID | UTC date pipeline first read this URL |
| `license` | OWID | license code (e.g. "OGL-IN-1.0", "CC-BY-4.0", "unknown-public", "internal") |
| `vintage` | OWID | source's own period label (e.g. "FY 2024-25"); preserved verbatim |
| `content_hash` | yen-gov | sha256 of fetched bytes (idempotency anchor) |
| `first_fetched_at` | yen-gov | RFC 3339 UTC, immutable, citizen-facing |
| `last_seen_at` | yen-gov | RFC 3339 UTC, mutable telemetry; never citizen-facing |
| `confidence_tier` | yen-gov | `gold` / `silver` / `bronze` — issuing authority vs re-publisher vs single-paper source |
| `is_issuing_authority` | yen-gov | bool — distinguishes ECI on votes (true) from a research aggregator republishing the same numbers (false) |

Hand-authored content: `url_main` and `url_download` are empty strings; `producer` = "yen-gov"; `license` = "internal"; `is_issuing_authority` = false; `confidence_tier` = "gold" (we know our own provenance).

Canonical concept: [`docs/concepts/data-provenance.md`](docs/concepts/data-provenance.md). Full schema with column-by-column rationale: [`docs/architecture/data/canonical-store.md` §5](docs/architecture/data/canonical-store.md). Design rationale: [ADR-0030](docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md).

## 13. UI Verification (Mandatory for Frontend / Admin Changes)

Any change that touches `frontend/` or `admin/` runtime behaviour MUST be verified by the agent itself using the integrated browser tools — not deferred to the human as a "please smoke test it" task. The agent has `open_browser_page`, `navigate_page`, `read_page`, `click_element`, and `screenshot_page` available; not using them when the change is UI-visible is a process violation, not a stylistic choice.

The minimum verification loop:

1. Confirm the dev server is up (`http://localhost:5173/` for frontend, `http://localhost:5174/` for admin). If not, start it before continuing.
2. `open_browser_page` (or `navigate_page` on an existing pageId) to the affected route(s) — at minimum the route the change targets, plus one cross-route smoke (e.g. home + a state hub).
3. `read_page` and confirm: (a) the new copy / structure / sections actually render, (b) no new `[error]` console events appeared in the snapshot's "Recent events" tail, (c) no new `404` for any path the change introduced.
4. If the change is layout-sensitive, `screenshot_page` to confirm visual intent.
5. Only then mark the task done. "It builds and svelte-check is clean" is necessary but NOT sufficient.

Apply this whenever applicable: route additions, copy / heading changes, data-loader changes, schema-driven section lists, theme switches, anything that changes what a citizen sees. It does NOT apply to pure backend / pipeline / docs / schema-only changes (no UI surface to read).

When the change spans many routes (e.g. an IA reset), pick a representative slice — home + one indicator page + one state hub — rather than all of them, but document which routes were checked in the commit message.

If a 404 / console error pre-exists the change and is unrelated, note it but do not block on it; if it is new and caused by the change, fix before merging.

## 14. Open Questions (TBD)

These are unresolved and must be answered before the corresponding work starts. When an open question is resolved, promote the decision into the relevant architecture doc and remove the entry here.

- District identifier source: LGD codes (gov.in Local Government Directory) preferred; Wikipedia slug as fallback for unmapped districts. Confirm during Phase 0 taxonomy seed (ADR-0030).
- "Top-N + others" cutoff for per-AC results: **resolved 2026-05-18 (Phase 1.6 / PR-K)**. Keep top-5 + NOTA + collapsed others (`config/processing.json:results.top_n_candidates`). Canonical store materialises `ac-candidates-total` + `ac-others-{votes,pct}` so the citizen sees full field size and tail aggregate even when only the top 5 candidate rows are persisted. See [`docs/architecture/data/elections-indicators.md`](docs/architecture/data/elections-indicators.md).
- Data-ingest automation cadence: local/manual only for now. Production Pages deploy is hourly plus manual dispatch, and only publishes CI-green `main`; see `docs/architecture/deployment.md`. Revisit ingest automation if we add live event tracking.
- Git repo size with committed Parquet: monitor clone time at end of Phase 1. If >60s or repo >2 GB, convene Fowler + Gregor on Git LFS vs Pages-only build artifact.
- Time-window queries on the canonical store: resolved by §0a (OWID year:int axis); SLM safety gate (sqlglot allowlist or DuckDB `EXPLAIN` dry-run) deferred to Phase 4 per ADR-0030.

Update this section as decisions are made; promote each decision into an architecture doc under `docs/architecture/`.

## 15. Test Coverage Policy (Mandatory)

Four tiers — **Unit / Contract / Integration / End-to-end**. A change without the appropriate-tier test in the same commit is a Definition-of-Done failure (§9). The only mock carve-outs are (a) `fetch` in unit tests of loaders (the loader's contract IS the fetch boundary) and (b) explicit user request — Holy Law #7. No pytest test walks the real on-disk corpus (§10); use a `tmp_path` fixture corpus injected via env var. A red test at commit time blocks the commit; "skip for now" is a structural-fix request (§5).

Full per-tier matrix (where each tier's tests live, what they assert, when they are required), command snippets, fixture conventions, and the deprecated-alias note ("Tier-A" / "Tier 2" → use word names) live in [docs/architecture/testing.md](docs/architecture/testing.md). Existing `CLAUDE.md §15` cross-references resolve here via this pointer; rename to `docs/architecture/testing.md` when next editing those files.

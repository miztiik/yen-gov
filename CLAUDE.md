# CLAUDE.md — yen-gov Engineering Contract

**Last Updated**: 2026-05-23

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
| AI / LLM app design — model selection, prompt strategy, RAG vs fine-tune, agent topology, eval framework, tokenizer/context gotchas (e.g. YENASK, in-bundle SLM) | **Andre** (synthesised from Karpathy + Willison + Husain + Howard) |

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
| `datasets/_ops/`| created    | Operator state — operational assets that are NOT citizen-facing fact tables and NOT contract surfaces with their own JSON Schema. Currently holds `range-mime-probe.parquet` (363-byte Pages MIME / Range header probe per [`docs/architecture/deployment.md`](docs/architecture/deployment.md)). NOT inventoried by the admin Inventory panel (`backend/yen_gov/admin/inventory.py:_SKIP_DIR_PREFIXES`). JSON under `_ops/` still requires `$schema`. See [`datasets/_ops/README.md`](datasets/_ops/README.md). |
| `config/`       | created    | Human-edited tunable knobs only (e.g. fetch concurrency, top-N cutoff). Schemas live in `datasets/schemas/`, not here. |
| `backend/`      | created    | Local Python pipeline (fetch / parse / validate / emit). FastAPI admin wrapper at `backend/yen_gov/admin/` (Phase 4 v0 — Inventory only). |
| `frontend/`     | created    | Static GitHub Pages app (Svelte 5 + Vite 6 + Tailwind + d3 + maplibre-gl). UI code only — never commits data files. |
| `admin/`        | created    | Separate dev-only Svelte app (Vite, port 5174) for the operator console. Never deployed publicly. v0 ships the Inventory panel; Schemas / Pipeline / Patches panels follow. |
| `tools/`        | created    | Standalone dev/ops tooling (`tools/boundaries/`). No `backend/` imports. |
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
- **`datasets/<family>/_meadow/<source>/<vintage>/<file>.json` is the backend-internal meadow tier** (parsed publisher rows, pre-canonical — see [`docs/concepts/meadow-tier.md`](docs/concepts/meadow-tier.md) + [ADR-0041](docs/architecture/decisions/0041-meadow-tier.md)). Frontend MUST NOT `fetch()` any path under `_meadow/`. Citizen reads route through the canonical Parquet allowlist (`frontend/src/lib/canonical/indicator-from-canonical.ts`) to `datasets/<family>/<family>_<role>.parquet` via DuckDB-WASM. The `_meadow/` underscore-prefix follows the CLAUDE.md §2 "private" convention; the Tier-B validator (renamed in PR 7c-4) enforces the perimeter.

## 5. Documentation Discipline

- Diataxis tiers under `docs/`: `architecture/`, `how-to/`, `concepts/`, `reference/` (+ `getting-started/`, `archive/`, `research/`, `agents/`).
- Maximum depth: `docs/<tier>/<topic>/<file>.md`. No deeper.
- Every doc has: H1 title, `Last Updated: YYYY-MM-DD`, "See also" cross-links.
- One concept defined once; everywhere else links to it.
- **Doc-class routing contract** (per [ADR-0034](docs/architecture/decisions/0034-documentation-routing-contract.md)) — every architectural statement has exactly one valid home:
  - **ADR** (`docs/architecture/decisions/NNNN-*.md`) — one decision + rejected alternatives + reversal cost. Immutable once Accepted (only the Status field changes).
  - **Subsystem doc** (`docs/architecture/<area>/*.md`) — current shape / disk layout / contracts / invariants. **Cites ADRs for rationale; never restates them.** Living snapshot, edit in place.
  - **Concept doc** (`docs/concepts/*.md`) — one vocabulary term, defined once. Linked from everywhere else, never duplicated.
  - **Plan-doc** (`TODO/<date>-<slug>.md`) — phase status + active PRs + TBD. **Cites both ADR and subsystem doc; carries no rationale.** **Single-snapshot header rule**: the header block is rewritten in place at every phase boundary; stacked "previous header" layers are a band-aid for missing snapshot semantics and forbidden by Holy Law #5 (no band-aids). History lives in `git blame` and merge-commit titles, not in the doc body.
- Agent memory is derived, not authoritative. Per-module `AGENTS.md` files and `/memories/repo/` are fast-entry indexes that point back to canonical docs; if they disagree with `docs/`, the docs win and the derived memory gets updated or deleted.
- Personas (Citizen, Hans, Max, Gregor, Fowler, Jony, Andre) live as canonical docs under `docs/agents/` with thin wrappers in `.claude/skills/bootstrap/` and `.github/agents/`. Every persona loads [`docs/agents/bootstrap.md`](docs/agents/bootstrap.md) before answering (Andre's bootstrap is optional for generic LLM-app questions that don't touch yen-gov code). New citizen-facing features **follow** the seven-step procedure in [`docs/how-to/distill.md`](docs/how-to/distill.md) — it is a runbook, not an automated skill; the seven persona handoffs are driven manually (or by a future orchestrator under `tools/`), not by the harness. Doctrine: [`docs/concepts/citizen-first.md`](docs/concepts/citizen-first.md). Andre is a parallel AI-app design specialist (one synthesised voice channelling Andrej Karpathy, Simon Willison, Hamel Husain and Jeremy Howard, with browser-inference depth absorbed into the worldview) — used for YENASK (`frontend/src/lib/yenask/`) and any future in-bundle SLM work; not part of the citizen-data distill pipeline.
- Docs-only PRs are a code smell — they mean a previous PR shipped without its docs.

## 6. Correction Levels

Classify every change before starting:

| Level | Scope                                | Workflow                              |
| :---: | ------------------------------------ | ------------------------------------- |
|  0    | Comments, typos, log strings         | Direct fix                            |
|  1    | 1 file, ~50 lines, isolated bug      | Direct fix                            |
|  2    | 1–2 files, explicit behavior change  | Plan → execute once scope is clear    |
|  3    | 2–3 files, cross-cutting             | Plan → phased execution               |
|  4    | 4+ files, structural                 | Propose breakdown first               |
|  5    | Core design / data model / runtime   | Design consultation only — pause work |

When in doubt, choose the higher level. Level 2 and above require an explicit plan before code changes; execute once scope is clear unless a §8 stop condition or unresolved design decision applies.

## 7. Debug Logging

- Temporary logs MUST be prefixed `[DEBUG]` (e.g. `console.log("[DEBUG] state:", state)`).
- Before finalizing any change: grep for `[DEBUG]` and remove every match.
- Re-run tests after cleanup.

## 8. Git Hygiene for Autonomous Merge Work

When the user says finish, ship, or merge, that authorizes the normal reversible git workflow: inspect state, use a named branch, stage exact paths, commit, push, run gates, and merge or enable automerge when green.

Do not pause merely because git is involved. Pause only when the next action would discard or overwrite unrelated work, rewrite published history, broadly mutate the working tree, or when file/branch ownership is ambiguous after inspection.

Avoid these in autonomous work because they are broad, lossy, or history-rewriting:

- `git stash`
- `git reset --hard`
- `git clean -fd`
- `git checkout .` / broad `git restore .`
- `git add .` / `git add -A`
- `git push --force` / `git push --force-with-lease`
- Amending commits that have been pushed

Safe workflow: inspect `git status --porcelain`, current branch, recent commits, relevant PRs/branches, and untracked files; leave unrelated dirty files alone; stage only explicit paths you intentionally touched; verify with `git diff --cached --name-only`; commit small reversible units on a named branch; push; merge or enable automerge after gates pass. If touched files overlap with someone else's edits, integrate deliberately or stop with a precise ownership question.

Git is the rollback ledger. Prefer branches, small commits, PRs, and merge/automerge over stash parking or broad cleanup.

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
- Use `datetime.now()` as input to **data-row CONTENT** (observation provenance, indicator vintage, citizen-facing doc footers). Wall-clock at write time is operational telemetry, NOT provenance. Under the v2.0 citation-ledger contract (ADR-0032), `sources` is a TABLE keyed by `(producer, title, vintage)` with `source_id = sha256(triple)[:12]`; fetch timestamps (`first_fetched_at`, `last_seen_at`, `date_accessed`, `content_hash`) are OUT of the contract entirely — adapters that need byte-change detection write `.runtime/<adapter>/<source_id>.json` sidecars (ephemeral, never citizen-facing). Re-running ingest with byte-identical upstream MUST leave observation/dimension Parquet bytes unchanged. **Carve-out**: control-plane artifacts (`datasets/manifest.json`, run logs under `.runtime/logs/`) MAY stamp `generated_at` with wall-clock — they describe operator state, not citizen-facing data, and the writer that consumes them tolerates churn. `vintage` is **never** wall-clock at write time either — it's the publisher edition tag or the operator's pre-chosen snapshot window (v3.0 per [ADR-0042](docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md)), authored once when the source citation is registered. See [data provenance](docs/concepts/data-provenance.md).
- Propose `write_text_if_changed`-style byte-compare helpers at write seams. Bytes ≠ data; if a re-run produces different bytes from identical upstream, fix the non-determinism upstream of the write seam. Canonical writer uses UPSERT-into-DuckDB + sorted Parquet emit (ADR-0030).
- Propose **domain-as-identity** for the sources table (`source_id = sha256(domain)`). Loses citation precision: `eci.gov.in` publishes 200+ distinct Statistical Reports, RBI publishes a new Handbook annually — collapsing them on the domain bricks per-report distinguishability. Citation identity is `(producer, title, vintage)`. See [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md) Rejected A.
- Propose **dropping `sources.parquet` and letting git-commit messages serve as citations**. Re-creates the per-shard smear; same RBI Handbook cited by 50 indicators = 50 commit messages with no shared FK target; violates Holy Law #9 (provenance is data, not commentary on data). See [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md) Rejected B.
- Propose **adding `content_hash` back as an optional column on the citizen-facing sources row** to "earn" byte-change detection. Re-introduces the fetched_at-smear class one layer up: the moment the column exists on the citizen row, some adapter starts updating it every poll. Fetch telemetry belongs in `.runtime/` sidecars. See [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md) Rejected C.
- Propose **making `citation_full` REQUIRED with adapter-mandatory templating**. Locks the schema to one display convention; dies the moment citation style evolves (APA vs Chicago vs in-line). Renderer composes `f"{producer}, {title}" + (f" ({vintage})" if vintage else "")` from the structured triple at read time; adapters set `citation_full` only when they need to override. See [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md) Rejected D.
- Walk the real on-disk corpus (`datasets/**`, `config/**`) from a `pytest` test, or from an HTTP smoke test that hits a live FastAPI route which itself walks the corpus. That is Tier-B conformance (§11), which is local-only via `python -m yen_gov validate --root .`. Pytest tests assert CODE correctness against `tmp_path` fixtures; they MUST NOT assert DATA quality against the real repo. Symptoms: a single test takes >5s; the fix is "add the missing file" not "change the code"; the test fails on a teammate's machine after they pull a corpus-only change. Doctrine fix pattern: inject the root via a `_repo_root()` helper reading an env var (e.g. `YEN_GOV_REPO_ROOT`), default to the real repo at runtime, in tests `monkeypatch.setenv(...)` to point at a `tmp_path` fixture corpus. Reference fix: commit `7d407d0`. Doctrine: [`docs/architecture/backend/validator.md`](docs/architecture/backend/validator.md).
- Emit JSON projections of canonical data for the citizen frontend. Under the canonical pivot, frontend reads Parquet via DuckDB-WASM only. No precomputed per-shard JSON, no parallel projection tree, no JSON shadow of the Parquet rows. Pre-pivot per-shard JSON (per-event `datasets/elections/<event>/<state>/{results/<ac>.json,parties.json,result.summary.json,_inventory.json}`) is superseded by the canonical store but still sits on disk pending per-family cleanup (TODO `20260517-canonical-long-format-pivot.md` rows 1.8b–1.8f); no new readers are allowed against that shape.
- Run CI that processes `datasets/**`. The publish pipeline is plain static-file copy via GitHub Pages from `main`. The only CI gates are lint, type-check, pytest, frontend build, Playwright — none of which touch `datasets/` contents.
- Use broad, lossy, or history-rewriting git commands instead of the §8 workflow.
- Let `TODO/` or chat logs become the source of truth for architecture.
- Let `AGENTS.md` or `/memories/` become a shadow source of truth instead of linking back to `docs/`.
- Pre-create empty modules "for later".
- Skip the docs update.
- Edit a `package.json` without running `bun install` and staging the resulting `bun.lock` in the same commit. The deploy workflow uses `--frozen-lockfile`; a desync silently stops the site from updating until someone notices and pushes a lockfile-only commit.
- Create new indicator artifact files under `datasets/indicators/in/<topic>/<id>.json`. That path is **retiring** per [ADR-0041 — Meadow tier](docs/architecture/decisions/0041-meadow-tier.md) ratified 2026-05-25; the legacy shape misled readers (looked citizen-facing, was always backend-internal). New backend-internal parsed publisher rows go to `datasets/<family>/_meadow/<source>/<vintage>/<file>.json` (the meadow tier — see [`docs/concepts/meadow-tier.md`](docs/concepts/meadow-tier.md)); citizen-facing canonical data goes to `datasets/<family>/<family>_<role>.parquet` + `datasets/taxonomy/indicators.parquet`. Per [TODO/20260517-canonical-long-format-pivot.md](TODO/20260517-canonical-long-format-pivot.md) §0e.7 P.* + §0e.8b the 110 existing per-indicator JSON shards retire family-by-family via the 7c-N sequence (energy: 7c-1 → 7c-4; Phase 2 P.2+ adopts meadow authoring from day one). Any new shard at the old path before the family's 7c-N PR is debt that has to migrate twice and silently re-anchors the `backend/yen_gov/legacy/folded_indicator_writer.py` retirement gate. **Enforced by Tier-B**: `python -m yen_gov validate --root .` runs `tier_b_meadow_shard_contract` (renamed from `tier_b_legacy_folded_indicator_shards` in PR-A 2026-05-25) which fails on any `*.json` under `datasets/indicators/in/` not listed in `datasets/_ops/meadow-shard-contract.txt` (renamed from `legacy-folded-indicator-shards.txt` in PR-A 2026-05-25). When a 7c-N PR retires a slice, that PR `git mv`s the family's shards to `_meadow/` AND removes the matching allowlist lines in the same Tier-A commit. See [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md) "Forbidden-path checks".
- Author an entry in `id_aliases[]` on `datasets/taxonomy/indicators.json` without a paired `deprecated_in: "YYYY-MM-DD"` on the same row. The Tier-B `tier_b_indicator_alias_window` rule treats the date as the anchor for the 60-day back-compat window; unpaired `id_aliases[]` would let a stale slug sit indefinitely with no retirement clock. The `indicators_seed.py` Pydantic `IndicatorRow` raises `ValueError` at compile time on the same pairing, so the only path that can sneak through is hand-authoring with a corrupted JSON-Schema environment. If a rename needs more than 60 days of back-compat, file an explicit ADR; do not extend `INDICATOR_ALIAS_WINDOW_DAYS` silently. See [datasets/schemas/indicator-catalogue.schema.json](datasets/schemas/indicator-catalogue.schema.json) v1.1 + [backend/yen_gov/validate.py](backend/yen_gov/validate.py) `tier_b_indicator_alias_window`.
- Encode topic membership as a prefix on `indicator_id` (e.g. `fiscal/outstanding_debt_pct_gsdp`). Per [docs/concepts/indicator-naming.md](docs/concepts/indicator-naming.md) D30 + [docs/architecture/data/canonical-store.md §2a](docs/architecture/data/canonical-store.md) the id is `<entity>-<measure>-<unit>-<facet>` kebab-case, and topic membership lives on the M:N row in `datasets/taxonomy/indicator_topic_tags.parquet` (denormalised onto `topic_tags[]` on `taxonomy/indicators.parquet` for read convenience). The legacy `<topic>/<snake>` shape is permitted ONLY in `id_aliases[]` during the 60-day window — never as a primary `indicator_id`. The indicator-catalogue v1.1 schema regex on `id_aliases[]` accepts the legacy form so an in-flight rename can still cite it; on `indicator_id` itself the kebab pattern is the floor.

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

Every observation row in every Parquet family under `datasets/` carries a `source_id` foreign key pointing at one row in `datasets/taxonomy/sources.parquet`. Provenance is a **table**, not a per-shard array. The table is a **citation ledger** (one row per `(producer, title, vintage)` triple, not per fetch event) — v2.0 shape per [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md), `vintage` semantics sharpened at v3.0 per [ADR-0042](docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md). Adopts OWID `origin.*` fields verbatim (per §0a "The One Rule") plus four yen-gov extensions for confidence + verifiability. Total: **11 columns (8 required + 3 optional)**.

| Field | Required | Source | Meaning |
| --- | :---: | --- | --- |
| `source_id` (PK) | ✓ | yen-gov | Deterministic 12-char hash: `"src-" + sha256(f"{producer}|{title}|{vintage}").hexdigest()[:12]`. FK target on every observation row. Build via `backend.yen_gov.canonical.citation.derive_source_id` — never hand-author. |
| `producer` | ✓ | OWID | publisher organisation ("Election Commission of India", "Reserve Bank of India", "yen-gov" for editorial rows) |
| `title` | ✓ | OWID | citizen-readable report name, verbatim |
| `vintage` | ✓ | OWID | **Strongest period anchor available** (v3.0 per [ADR-0042](docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md)): publisher edition when the upstream publishes one (`"2024-25"`, `"NFHS-5"`); operator snapshot window matching `datasets/<family>/_meadow/<source>/<vintage>/` path when the publisher publishes no edition tag (continuously-updated APIs). Non-empty (`minLength: 1`); v2.0 permitted `""` and v3.0 retires that. |
| `license` | ✓ | OWID | enum-locked: `OGL-IN-1.0` / `CC-BY-4.0` / `CC0-1.0` / `public-domain` / `unknown-public` / `internal` |
| `confidence_tier` | ✓ | yen-gov | `gold` / `silver` / `bronze` — issuing authority vs reputable republisher vs single-paper / activist source |
| `is_issuing_authority` | ✓ | yen-gov | bool — ECI on votes (true), aggregator republishing same numbers (false). Independent of `confidence_tier`. |
| `verification_method` | ✓ | yen-gov | enum-4: `live-fetch` / `archived-snapshot` / `transcribed` / `editorial`. Array order is canonical rank (4 strongest → 1 weakest). |
| `url_main` | — | OWID | landing / about page URL; `null` for hand-imported / transcribed / editorial rows |
| `citation_full` | — | OWID | adapter override; when null, renderer composes from `(producer, title, vintage)` |
| `notes` | — | yen-gov | operator scratchpad |

**Hand-imported / transcribed content** uses the same `producer + title + vintage` as the live-fetched path would. Same triple = same `source_id`. Only `url_main = null` and `verification_method = "transcribed"` differ. The citizen never sees split provenance for one report just because two ingest paths populated different rows.

**Editorial content** (yen-gov-derived analytical framing): `producer = "yen-gov"`, `license = "internal"`, `is_issuing_authority = false`, `confidence_tier = "gold"`, `verification_method = "editorial"`, `url_main = null`.

**Removed from v1.0** (breaking, v2.0 contract): `url`, `url_download`, `content_hash`, `first_fetched_at`, `last_seen_at`, `date_accessed` are all gone. Live-fetch adapters that need byte-change detection write `.runtime/<adapter>/<source_id>.json` sidecars — ephemeral by §2, never citizen-facing, never a contract surface.

Canonical concept: [`docs/concepts/data-provenance.md`](docs/concepts/data-provenance.md). Full schema with column-by-column rationale: [`docs/architecture/data/canonical-store.md` §5](docs/architecture/data/canonical-store.md). Design rationale + four rejected designs: [ADR-0032](docs/architecture/decisions/0032-sources-citation-ledger.md). v3.0 `vintage` sharpening + three rejected alternatives (α′ plain-operator-snapshot, β wildcard relaxation, γ schema split): [ADR-0042](docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md).

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

# Bootstrap Architecture and Documentation Standard

> **See also**:
>
> - [Documentation Structure](./documentation-structure.md) - Canonical placement and depth rules
> - [Configuration Reference](./configuration.md) - Current config governance baseline
> - [Architecture: System Overview](../architecture/system-overview.md) - Runtime boundary and deployment model
> - [Concepts: Observability](../concepts/observability.md) - Identifier and telemetry concepts
> - [Root CLAUDE](../../CLAUDE.md) - Project-level engineering contract example
> - [Backend AGENTS](../../backend/puzzle_manager/AGENTS.md) - Module architecture-map example
> - [Frontend AGENTS](../../frontend/src/AGENTS.md) - Frontend architecture-map example

**Last Updated**: 2026-05-08

This file is a portable, single-source standard for bootstrapping a new project with the same structural discipline used in Yen-Go. It is not a cookie-cutter implementation. It defines the architectural contracts, documentation model, schema governance, telemetry contract, and agent documentation shape that should exist before feature work scales.

Note on terminology: this standard uses **Diataxis** (sometimes heard as "dachshund" in speech-to-text) for documentation structure.

## 1. Engineering Principles (Read First)

These are the non-negotiable values every other section enforces.

- **Structural Fixes Over Band-Aids.** Diagnose the root cause. Brittle workarounds, monkey-patches, and "temporary" hacks are not acceptable. If a fix needs to be deeper, escalate the correction level (see Section 8) instead of patching the symptom.
- **API Contracts and Interfaces First.** Define typed data contracts at every process and module boundary before writing logic. Anything that crosses a boundary (network, file, IPC, language runtime) must have an explicit schema.
- **Documentation Is Agent Memory.** Canonical docs (`docs/`) are the long-term memory for both humans and AI agents. Every feature, architectural decision, schema change, or behavior change MUST land a documentation update in the same commit.
- **Open Source First (Buy, Don't Build).** Prefer mature, well-maintained open-source libraries over custom implementations. Examples of defaults: Tailwind for CSS, `httpx`/`fetch` for HTTP, `tenacity`/`p-retry` for retries, `pydantic`/`zod` for validation, `lxml` for XML, `sqlite` for embedded data. Custom code only when no production-grade library exists.
- **No Hardcoding.** No magic strings, magic numbers, or hardcoded taxonomy values. Everything tunable lives in `config/` and is loaded through a typed schema.
- **No Mocking by Default.** Mocks lie. Use real implementations, real fixtures, real test environments. Mocks are allowed only when (a) the user explicitly asks, or (b) crossing an external boundary that is genuinely untestable in CI.
- **SOLID / DRY / KISS / YAGNI.** Search before writing. Edit before creating. Delete unused code aggressively — git history preserves everything.
- **Explicit Over Implicit.** Type hints, named arguments, descriptive variables, error messages that say what to do next.

## 2. Definition of Done

A change is not "done" until ALL of the following are true. Skipping any of these is a defect, not a deferral.

- [ ] Tests added/updated for changed behavior (unit + integration where applicable).
- [ ] All quality gates pass (tests, lint, type-check, schema validation).
- [ ] Canonical docs updated in `docs/` (architecture rationale, how-to, concept, or reference — pick the right tier).
- [ ] Schemas bumped/migrated if any persisted contract changed.
- [ ] AGENTS.md updated if module structure or invariants changed.
- [ ] No `[DEBUG]`-prefixed logs left in code (see Section 9.3).
- [ ] No hardcoded values introduced.
- [ ] No mocks introduced unless explicitly requested.

## 3. Repository Topology Contract

Recommended root topology. The boundaries between these directories are real and enforced.

| Directory | Purpose | Lifetime |
| --- | --- | --- |
| `frontend/` | UI app and rendering concerns only | Tracked |
| `backend/` | Server runtime, pipeline, or core processing | Tracked |
| `config/` | Human-edited config and policy definitions | Tracked |
| `config/schemas/` | JSON Schema (or equivalent) contracts | Tracked |
| `docs/` | Canonical long-term project knowledge | Tracked |
| `tools/` | Standalone operational/dev tooling (must NOT import from backend/) | Tracked |
| `.runtime/` | Ephemeral run state, logs, staging | Gitignored |
| `TODO/` or `notes/` | Working scratchpads, plans-in-flight | Tracked but non-authoritative |
| `/memories/` | Agent memory (cross-session notes, scoped) | Tool-managed |

### 3.1 Memory Hierarchy

Four distinct memory tiers exist; do not blur them:

| Tier | Location | Authority | When to Use |
| --- | --- | --- | --- |
| Canonical | `docs/` | Highest — source of truth | Durable knowledge, decisions, contracts |
| Agent | `/memories/` | Per-agent, scoped | Cross-session preferences, lessons, repo facts |
| Working | `TODO/`, `notes/` | Non-authoritative | In-progress plans, drafts, handoff memos |
| Runtime | `.runtime/`, logs | Ephemeral | State, logs, staging — operational only |

Rule: distill durable insights from Working/Agent into Canonical. Never let `TODO/` become the source of truth for architecture.

## 4. Architecture Contracts

### 4.1 Layer Separation and Dependency Direction

| From | To | Allowed | Why |
| --- | --- | --- | --- |
| UI/Components | Application/Services | Yes | UI orchestrates use-cases |
| Application/Services | Domain/Core | Yes | Business logic lives in core |
| Adapters/Infrastructure | Domain/Core | Yes | Adapters implement domain contracts |
| Domain/Core | Adapters/Infrastructure | **No** | Core must remain framework-agnostic |
| Services | UI/Components | **No** | Prevent view-driven coupling |
| `tools/` | `backend/` runtime modules | **No** | Tools must be self-contained |

If frontend and backend both exist:

- Frontend MUST NOT import backend runtime code.
- Backend MUST NOT include UI logic or DOM concerns.
- Shared contracts MUST be data contracts (schemas), not cross-runtime imports.

### 4.2 Runtime Boundary Contract

Pick one runtime model and document it as a hard law in `CLAUDE.md`:

- **Static-first**: precompute everything possible at build time; runtime is browser/edge only.
- **Service-backed**: runtime APIs are first-class contracts with versioning.
- **Hybrid**: static assets + thin API layer with explicit boundary documented.

For all models: no hidden side channels. All external I/O goes through defined adapters/wrappers.

### 4.3 Path Portability Contract

For any persisted path (JSON, logs, DB rows, emitted artifacts):

- Relative paths only.
- POSIX separators only (`/`, never `\`).
- Minimal reconstructable path (don't store redundant prefixes).

In-memory `Path` objects for local I/O can stay platform-native. The rule applies only to data leaving the process.

## 5. API Contracts and Interfaces

This is the single biggest discipline that prevents long-term decay.

### 5.1 Boundary Rule

Anything crossing a process/module/network boundary must have a typed schema. Examples:

- Configuration files → JSON Schema in `config/schemas/`.
- Event payloads → schema in `config/schemas/events/`.
- HTTP/RPC APIs → OpenAPI / gRPC / typed client.
- Database rows → typed models (Pydantic, Zod, SQLAlchemy, Prisma).
- Log entries → frozen/immutable model classes.
- Cross-language data → JSON Schema generating types for each language.

### 5.2 Validation Rules

- Validate at the **boundary**, not deep inside business logic.
- Fail fast on invalid input — never silently coerce.
- Use a single validation library per language (Pydantic for Python, Zod for TypeScript, etc.).

### 5.3 Versioning Rules

- Schema versions are explicit, integer, and monotonic.
- Backward-compatibility policy is documented (strict, tolerant, migration-required).
- Breaking changes require: version bump + changelog entry + migration plan + docs update.
- Embed schema version in persisted artifacts so old data can be detected and migrated.

## 6. Schema and Config Governance

### 6.1 Centralization

All configuration and payload contracts live in one place:

- Human-edited config → `config/*.json` (or `*.yaml`, `*.toml`).
- Schemas validating that config → `config/schemas/`.
- Event/API/payload schemas → `config/schemas/events/`, `config/schemas/api/`, etc.

No schema copies scattered across modules.

### 6.2 Source-of-Truth Pattern

For each domain (taxonomies, levels, categories, feature flags):

- Pick exactly one canonical config file.
- Both frontend and backend load from it.
- Reject any code that re-defines the same taxonomy elsewhere.

### 6.3 Compliance Enforcement

- CI validates every config file against its schema.
- Runtime validates startup-critical config and fails fast on invalid input.
- A schema test suite enforces "every config file has a schema" as a structural check.

## 7. Documentation Standard (Diataxis + 3-Level Depth)

Documentation is enforced like code. **Documentation = agent memory**, so missing or stale docs cause silent regressions on the next agent session.

### 7.1 Diataxis Tiers

Every document belongs to exactly one tier:

| Tier | Directory | Reader Question |
| --- | --- | --- |
| Architecture | `docs/architecture/` | Why is it designed this way? |
| How-To | `docs/how-to/` | How do I perform a specific task? |
| Concepts | `docs/concepts/` | What is this concept / vocabulary? |
| Reference | `docs/reference/` | What are the exact options / values / contracts? |

Support tiers:

- `docs/getting-started/` — onboarding entry points.
- `docs/archive/` — historical / superseded material.

### 7.2 Depth Rule (Maximum 3 Levels)

- Allowed: `docs/tier/topic/file.md`
- Forbidden: `docs/tier/topic/subtopic/file.md` or deeper.

### 7.3 Required Elements

Every canonical document includes:

- One H1 title.
- `Last Updated: YYYY-MM-DD`.
- "See also" callout with cross-tier links (architecture ↔ how-to ↔ concepts ↔ reference).
- Content that stays in its tier (no mixed-purpose docs).

### 7.4 Single Source of Truth

- A concept is defined once and referenced everywhere else.
- No duplication across tiers.
- If behavior changes, code and canonical docs change in the **same commit**.

### 7.5 Trigger Rule

A documentation update is REQUIRED whenever:

- A new feature, API, or CLI command is added.
- An existing API, config, or behavior changes.
- A file/module is renamed, moved, or removed.
- A taxonomy or schema property changes.
- An architectural decision is made.

Docs-only PRs are a code smell — they signal a previous PR shipped without its docs.

## 8. Correction Levels (Change Severity)

Every change is classified before work begins. Higher levels require more rigor and less direct execution.

| Level | Name | Scale | Workflow |
| :---: | --- | --- | --- |
| 0 | Super Minor | Comments, typos, logs (no behavior change) | Direct fix |
| 1 | Minor | 1 file, ~50 lines, isolated bug | Direct fix |
| 2 | Medium Single | 1–2 files, ~100 lines, explicit behavior change | Plan → Approve → Execute |
| 3 | Multiple Files | 2–3 files, cross-cutting (UI + logic, config + code) | Plan → Phased execution |
| 4 | Large Scale | 4+ files, structural changes | Propose breakdown first |
| 5 | Fundamental | Core design, data model, or runtime change | Design consultation only — pause execution |

Rule of thumb: when uncertain, default to a higher (safer) level. Levels 2+ require explicit user approval before any code changes.

## 9. Debug Workflow

A standardized investigation cycle replaces ad-hoc poking.

### 9.1 The 7-Step Cycle

1. **Clarify symptoms** — when, where, what, expected vs. actual.
2. **Establish MRE** — minimal reproducible example.
3. **Gather telemetry** — logs, traces, console errors, input artifacts.
4. **Structure hypotheses** — table of candidate causes with probability and verification method.
5. **Assign correction level** — declare intent (e.g. "Level 2 fix").
6. **Execute and verify** — patch, re-run MRE, check for regressions.
7. **Handover memo** (optional) — if pausing or handing off, write a structured memo.

### 9.2 Handover Memo Template

When pausing or handing off mid-debug:

```markdown
## Debug Handover — YYYY-MM-DD
1. Target / context
2. Status (expected vs. actual)
3. Repro steps
4. Candidate causes (primary, secondary)
5. Correction level
6. Fixes attempted
7. Result and next steps
```

### 9.3 Temporary Debug Logging Rules

- ALWAYS prefix temporary logs with `[DEBUG]` (e.g. `console.log("[DEBUG] state:", state)`).
- Before finalizing the change: grep for `[DEBUG]` and remove every match.
- Verify tests still pass after cleanup.

## 10. Telemetry and Logging Standard

### 10.1 Identifier Model

Define these identifiers up front and keep them stable:

- `run_id` — one execution / job run.
- `trace_id` — one entity flowing across stages or components.
- `entity_id` — stable published / business identifier.
- `source_id` — origin adapter / source identity.

`trace_id` is the only identifier that exists across all stages — it is the backbone of debugging.

### 10.2 Event Envelope Contract

Every structured log/event includes at minimum:

- `timestamp`
- `level`
- `event_name`
- `run_id`
- `trace_id` (when applicable)
- `source_id` (when applicable)
- `message`
- structured fields map

### 10.3 Two-Tier Logging Pattern

Two destinations, two purposes:

- **Console** — concise progress, summaries, errors. Operator-facing dashboard.
- **Structured logs** — per-entity events with full context. Machine-grep / debugging.

Practical level policy:

- `ERROR` / `WARNING` / `INFO` visible to operators (console + file).
- `DETAIL` / `DEBUG` retained only in structured logs.

### 10.4 Auditability Rules

- Mutating/destructive operations write append-only audit entries.
- Telemetry must support end-to-end trace reconstruction by `trace_id` alone.
- Never log secrets, tokens, or sensitive user data.
- Persisted paths in logs follow Section 4.3 (relative + POSIX).

## 11. Reliability and Operational Safety

- **Fail fast** on invalid config and schema violations.
- **Continue per-item** for recoverable batch errors; aggregate failures into clear reports.
- **Idempotent writes** wherever possible.
- **Atomic writes** for state files and version pointers.
- **Rollback/rebuild operations** are explicit, auditable, and documented before first production deploy.

## 12. Git Safety (Mandatory for Agentic Workflows)

When AI agents and humans share a repository, careless git commands destroy untracked work.

### 12.1 Forbidden Commands by Default

- `git stash` — loses untracked files when popped/dropped.
- `git reset --hard` — destroys uncommitted changes.
- `git clean -fd` — deletes untracked files permanently.
- `git checkout .` / `git restore .` — reverts all tracked changes.
- `git add .` / `git add -A` — stages files outside the agent's scope.

### 12.2 Safe Workflow

1. Inspect untracked files before any git operation: `git status --porcelain | grep "^??"`.
2. Stage only the specific files the change touched.
3. Verify staged set: `git diff --cached --name-only`.
4. Commit on a feature branch.
5. Merge with `--no-ff` for traceable history.
6. Ask the user before switching branches with uncommitted work.

### 12.3 Commit Hygiene

- No co-author or attribution tags for AI agents.
- Commit messages describe the change, not the agent.

## 13. Quality Gates

Minimum merge gates (CI-enforced):

- Unit tests pass.
- Integration tests pass for cross-component changes.
- Lint passes (zero warnings policy).
- Type-check passes (`strict` mode).
- Schema validation passes for all config and payload changes.
- Documentation updated when behavior, contracts, or operations changed.
- No `[DEBUG]` markers in code.

## 14. Agent Documentation Standard (CLAUDE + AGENTS)

### 14.1 `CLAUDE.md` (Repository Contract)

Single root file declaring the project's non-negotiables:

- Holy laws (runtime model, persistence model, type-safety policy).
- Project structure and ownership boundaries.
- Source-of-truth config and schema locations.
- Runtime / data-flow model.
- Quality gate commands (tests, lint, type-check).
- Safety constraints (git, data, secrets).
- Path rules.
- "What NOT to do" anti-patterns.

### 14.2 `AGENTS.md` (Per-Module Architecture Map)

Every major module has its own `AGENTS.md` — dense, agent-facing, NOT user docs:

- Directory map and per-file responsibilities.
- Core entities and key methods.
- Data flow summary.
- Known gotchas and invariants.
- Fast validation commands (e.g. test markers).

Rule: if module structure or invariants change, `AGENTS.md` updates in the **same commit**.

### 14.3 Anti-Patterns (What NOT to Do)

Generic don't-do list to copy into a new project's `CLAUDE.md`:

- Hardcoding taxonomy values, version numbers, or magic strings.
- Storing absolute paths in serialized data.
- Manual string-building for structured formats (use a builder/validator).
- Custom retry/HTTP/parsing logic when a library exists.
- Swallowing exceptions or silently coercing invalid input.
- Mocking in tests unless explicitly requested.
- Skipping logs, skipping docs, skipping schema bumps.
- Using `git stash` / `git reset --hard` / `git add .`.
- Letting `TODO/` or chat logs become the source of truth.
- Assuming context — ask first when uncertain.

## 15. Optional Architectural Blueprints

These are **named, reusable patterns** lifted from real systems. Pick the ones that match the project; ignore the rest.

### Blueprint A: Static-First Deployment

- All compute happens at build time.
- Runtime is browser / edge / CDN only.
- Data ships as static SQLite (loaded via WASM) or JSON.
- User state lives in `localStorage` / IndexedDB.
- Zero backend infrastructure cost.

Best for: content-heavy apps, learning tools, offline-capable PWAs.

### Blueprint B: Multi-Stage ETL Pipeline

- Pipeline split into discrete stages (e.g. `ingest → analyze → publish`).
- Each stage has a typed `StageContext` and `StageResult`.
- State persists between stages so reruns can resume.
- Stage logs separated for clean per-stage debugging.

Best for: data processing, content pipelines, batch enrichment.

### Blueprint C: Adapter Registry Pattern

- Domain core defines an adapter protocol/interface.
- Adapters self-register via decorator (`@register_adapter("name")`).
- Discovery is automatic (`discover_adapters()`).
- Core never imports specific adapters — only the registry.

Best for: pluggable sources/sinks, multi-provider systems, extensible importers.

### Blueprint D: Append-Only Audit + Publish Log

- Every mutation writes an append-only JSONL entry.
- Publish log is the permanent record of "what was published when".
- Rollback rebuilds state from the log, never from in-place edits.

Best for: anything with publish/rollback semantics, compliance-sensitive data.

### Blueprint E: Content-Addressed Storage

- Persistent ID = `hash(content)[:N]`.
- ID == filename == primary key.
- Deduplication is automatic.
- Trace IDs separate from content IDs (one is per-run, one is permanent).

Best for: immutable content stores, dedup-heavy systems.

### Blueprint F: Run-State Resume Pattern

- Long-running jobs write state after every batch to `.runtime/state/current_run.json`.
- Re-runs detect incomplete batches and resume.
- `--resume` flag is first-class.

Best for: pipelines, crawlers, long imports.

### Blueprint G: Tiered Test Strategy

- Tier 1: fast unit tests — runs in seconds, used after every change.
- Tier 2: quick integration — runs in tens of seconds, used pre-commit.
- Tier 3: full suite — runs in minutes, used pre-PR / in CI.
- Markers / tags select tiers explicitly.

Best for: any project where the test suite has grown past 30 seconds.

## 16. Portable Bootstrap Checklist

Use this when starting a new project:

- [ ] Write `CLAUDE.md` with non-negotiable constraints (Section 14.1).
- [ ] Write a "What NOT to do" anti-pattern list (Section 14.3).
- [ ] Define module boundaries and dependency direction (Section 4.1).
- [ ] Pick a runtime boundary model (Section 4.2).
- [ ] Pick relevant blueprints from Section 15.
- [ ] Create docs tier structure (`architecture/`, `how-to/`, `concepts/`, `reference/`).
- [ ] Enforce 3-level depth and required document elements (Section 7).
- [ ] Centralize config in `config/`.
- [ ] Centralize schemas in `config/schemas/`.
- [ ] Add schema validation in CI.
- [ ] Define telemetry identifier model (`run_id`, `trace_id`, `entity_id`, `source_id`).
- [ ] Define event envelope and log level policy.
- [ ] Define audit log strategy for destructive/mutating operations.
- [ ] Add `AGENTS.md` files for each major module.
- [ ] Define and script tiered test commands (Blueprint G).
- [ ] Document rollback/rebuild operations before first production deploy.
- [ ] Add git safety rules to `CLAUDE.md` (Section 12).
- [ ] Set up tailwind / OSS defaults instead of custom-built equivalents (Section 1).

## 17. Decomposition Guidance

Keep this as one file during bootstrap. Split only when:

- A single section exceeds ~150 lines, or
- Two projects start to diverge on a section's content, or
- A section accumulates project-specific examples that don't generalize.

When splitting:

1. Keep this file as the top-level index.
2. Move docs structure → `docs/reference/documentation-structure.md`.
3. Move telemetry → `docs/concepts/observability.md`.
4. Move operational procedures → `docs/how-to/`.
5. Move blueprints → `docs/architecture/blueprints/`.
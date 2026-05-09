# Architecture Decision Records (ADRs)

**Last Updated**: 2026-05-09

This directory holds the **few** decisions that earn an immutable, append-only record of their own:

> An ADR is appropriate **only** when a decision (a) has a credible rejected alternative with non-trivial reversal cost, AND (b) is genuinely cross-cutting — no single subsystem doc is its natural home.

Everything else lives next to the thing it describes. Per CLAUDE.md Holy Law #4, design rationale is documented in the same commit as the code change — but the *home* for that rationale is the relevant subsystem doc under `docs/architecture/<area>/`, not a separate decisions register. This keeps the system map and the rationale that justifies it on the same page, instead of forcing readers to chase numbered cross-references through a parallel filing cabinet.

By that bar, today only two decisions live here. Both are repository-wide policy that no single subsystem owns.

## Format

One file per decision, named `NNNN-kebab-title.md`. Numbers are **append-only**: when an ADR is folded into a subsystem doc, its number is **not reused** (gaps record the absorption, see [mapping table](#absorbed-adrs-2026-05-09) below). Each ADR has:

- **H1 title**: `ADR-NNNN: <decision>`
- **Last Updated** date.
- **Status**: `proposed | accepted | superseded by ADR-XXXX | deprecated`.
- **Context**: the situation forcing the decision.
- **Decision**: what we chose.
- **Consequences**: what follows (good and bad).
- **Alternatives considered**: rejected options + why.

Keep ADRs short. They are immutable once accepted; a later ADR supersedes (and the older one's status is updated to point to it). Never edit an accepted ADR's decision in place.

## Index

| ID  | Title | Status |
| --- | ----- | ------ |
| [0002](0002-provenance-as-sources-list.md) | Provenance as a list of `{url, fetched_at}` entries | accepted |
| [0003](0003-no-fetch-cache.md) | No HTTP cache layer; intermediates live in `.runtime/raw/` | accepted |

## Absorbed ADRs (2026-05-09)

The following ADR numbers used to live in this directory and were absorbed into subsystem docs in a single restructure on 2026-05-09. The numbers are **not reused** — gaps in the sequence are intentional and signal "a decision used to live here; its current home is below".

| Old ADR | Subject | Now lives in |
| --- | --- | --- |
| 0001 | Layered backend architecture (core / sources / pipeline) | [backend/overview.md](../backend/overview.md) (and CLAUDE.md §4 for the dependency rules) |
| 0004 | Pydantic models mirror JSON Schemas 1:1 | [backend/core.md](../backend/core.md#pydantic-models-mirror-json-schemas-11) |
| 0005 | Bottom-up composition (district → state → country) | [backend/pipeline.md](../backend/pipeline.md#bottom-up-composition) |
| 0006 | Intermediate raw-file path derivation | [backend/core.md](../backend/core.md#intermediate-raw-file-path-derivation) |
| 0007 | Pipeline events as frozen dataclasses, not Pydantic | [backend/core.md](../backend/core.md#pipeline-events-are-frozen-dataclasses-not-pydantic) |
| 0008 | ECI source adapter — page conventions and parsing | [backend/sources-eci.md](../backend/sources-eci.md) |
| 0009 | Wikipedia source adapter — scope and conventions | [backend/sources-wikipedia.md](../backend/sources-wikipedia.md) |
| 0010 | Pipeline orchestration — composition layer + CLI run | [backend/pipeline.md](../backend/pipeline.md) |
| 0011 | Frontend stack (Svelte 5 + Vite + Tailwind + d3, bun) | [frontend/overview.md](../frontend/overview.md#stack) |
| 0012 | Dev-time data access — Vite middleware serves `/data` | [frontend/data-loading.md](../frontend/data-loading.md#dev-time-access--vite-middleware) |
| 0013 | Production data placement — CI-side staging | [frontend/data-loading.md](../frontend/data-loading.md#production-placement) |
| 0014 | SQLite emitter — derived per-state artifact | [backend/emit-sqlite.md](../backend/emit-sqlite.md) |
| 0015 | Constituency hierarchy fields + status lifecycle | [data-model.md](../data-model.md#constituency-hierarchy-and-status-lifecycle) |
| 0016 *(eci-statistical-reports-canonical)* | ECI Statistical Reports as canonical past-election source | [backend/sources-eci.md](../backend/sources-eci.md#authority-hierarchy-for-past-elections) |
| 0016 *(frontend-hash-routing)* | Frontend hash-based routing (custom, no router lib) — duplicate-numbered alongside the ECI ADR | [frontend/overview.md](../frontend/overview.md#hash-based-routing-custom-no-router-lib) |
| 0017 | `/explore` page uses `sql.js` | [frontend/data-loading.md](../frontend/data-loading.md#the-explore-page-uses-sqljs) |
| 0018 | Wikipedia AC-table district name resolution | [backend/sources-wikipedia.md](../backend/sources-wikipedia.md#district-name-resolution-for-ac-tables) |

The next new ADR will be numbered **0019** (continuing the original sequence; we do **not** reuse the duplicate 0016 slot, the gaps left by the absorbed ADRs, or renumber the survivors). The duplicate-0016 collision is recorded here so future archaeology has the answer.

## Why this directory is small

When work began, every design choice was documented as an ADR — 18 of them in the first months. In review (2026-05-09) we found the directory had become a parallel filing cabinet that readers had to cross-reference against the subsystem they actually cared about. Most ADRs were single-subsystem design facts that read more naturally as a "Design rationale" section inside the subsystem doc. Folding them in halved the number of files a reader needs to open to understand any one area, while preserving every paragraph of rationale.

The two surviving ADRs both fail the "could it live in one subsystem doc?" test:

- **Provenance** (`sources` array) is enforced by the JSON validator, the pydantic models (`core/`), the IO chokepoint (`core/io.py`), every emitter (`pipeline/`, `emit/`), every source adapter, the schemas themselves, and the deploy story. There is no single subsystem doc that owns it.
- **No fetch cache** is enforced by the HTTP fetcher (`core/`), the orchestrator (`pipeline/`), the `.runtime/` topology (CLAUDE.md §3), and every source adapter that writes to `.runtime/raw/`.

If a future decision passes the same bar — cross-cutting policy with a real rejected alternative — it gets a new ADR. If it can live in one subsystem doc, it does.

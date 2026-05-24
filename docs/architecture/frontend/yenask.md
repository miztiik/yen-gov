# YENASK — browser governance insight assistant (dev preview)

**Last Updated**: 2026-05-24 (PR-3 shipped — WebGPU fix, token observability, debug panel)

YENASK is a dev-only browser lab mounted at `/dev/yenask`. It turns a citizen governance question into a validated `InsightIntent`, then runs DuckDB-WASM directly against the canonical Parquet store to produce an `AnswerViewModel`. No backend at runtime — the lab obeys Holy Law #1 (static-first production).

This page covers **what is currently on disk** as of PR-3 (merge `63a62a4e`): the module layout, the contracts the modules pass between each other, the readiness state machine, the observability surface that ships with PR-3, and the test seams. It does **not** cover rationale-as-it-was-made — that lives in the plan-doc [`TODO/20260518-browser-governance-insight-assistant-plan.md`](../../../TODO/20260518-browser-governance-insight-assistant-plan.md) §17 (entries D-01 through D-21). Every section here cites the relevant D-NN entry instead of restating it (per CLAUDE.md §5 doc-class routing contract).

For the lab's removal contract and the "what lives where" map, see [`frontend/src/lib/yenask/AGENTS.md`](../../../frontend/src/lib/yenask/AGENTS.md).

## Why it lives inside `frontend/`

The lab ships as `frontend/src/routes/Yenask.svelte` mounted at `/dev/yenask`, with lab-internal libs under `frontend/src/lib/yenask/`. There is **no** standalone `labs/yenask/` Vite app, no separate dev port, no duplicated `serveDatasets()` middleware. The lab reads from the same `/data/` URLs production reads from, runs the same DuckDB-WASM init the production app runs, and is gated only by the dev-only route under `/dev/`.

Removing the lab is `git rm` of `frontend/src/routes/Yenask.svelte` + `frontend/src/lib/yenask/` + two lines from `frontend/src/main.ts`. Nothing in the production surface imports from `lib/yenask/`. The reverse is encouraged: `lib/yenask/` imports freely from production helpers (`../duckdb`, `../charts/*`, `../SourceListV2`, `../format`, `../url`).

Rationale: plan-doc §17 [D-01](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-01--lab-lives-inside-frontend-as-a-dev-route-not-as-a-standalone-labsyenask-vite-app), [D-02](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-02--reuse-existing-frontend-primitives-instead-of-rebuilding).

## Pipeline

```text
user question (free text OR canned starter chip)
   │
   ├── canned chip ──→ skip extract; intent is already validated
   │
   ▼
extractIntent(question, catalogue, adapter)         (impure — calls model)
   │   - buildSystemPrompt(catalogue) + buildFewShot()
   │   - one validate-or-retry loop (max_retries=1)
   │   - returns ExtractResult { ok, intent | error, diagnostics }
   │
   ▼
compileIntent(intent, catalogue)                    (PURE — no I/O)
   │   - validates intent against the SemanticCatalogue (entities, indicators)
   │   - emits DuckDBPlan { concept_id, main_sql, provenance_sql, slices[] }
   │   - JOINs taxonomy.sources implicitly so every output row is Holy-Law-#9 compliant
   │
   ▼
executePlan(plan)                                   (impure — calls DuckDB-WASM)
   │   - registers slice tables via lib/duckdb.ts
   │   - runs main_sql then provenance_sql
   │   - returns AnswerViewModel { rows, columns, source_strip[], ... }
   │
   ▼
append assistant-answer turn to conversation log
```

The pipeline is the same regardless of how the intent was produced (model-extracted vs canned). Each citizen-visible turn carries:

- **The answer table** — `<table data-testid="yenask-answer-table">`.
- **The sources accordion** — `<div data-testid="yenask-source-strip">`. Citizen-relevant: who published, what licence.
- **The per-turn footer** — one line of observability ("Answered with SmolLM2-135M-Instruct: 1× attempt · ~248 tokens in · ~87 out · 2.1s total. See Debug log below for details." OR "Canned starter prompt — no model used.").

The SQL, raw model output, and per-attempt token timing are NOT in the citizen turn — they live in the always-visible Debug log section below the chat (D-21). See [Observability surface (PR-3)](#observability-surface-pr-3).

## Module layout

```text
frontend/src/lib/yenask/
├── contracts/
│   ├── insight-intent.ts        Zod schema for what the model is allowed to output.
│   │                            Discriminated by version: "insight.intent.v0".
│   └── answer-viewmodel.ts      Zod schema for what the renderer is allowed to display.
│                                source_strip is REQUIRED non-empty (Holy Law #9).
├── types.ts                     Shared TS types not covered by Zod
│                                (DuckDBPlan, AnswerRow, slice registration shapes).
├── semantic-catalogue.ts        loadSemanticCatalogue() — derived at startup from
│                                datasets/manifest.json + taxonomy parquets.
│                                MUST NOT scan fact tables (D-04, D-14).
├── concepts.ts                  Hand-authored concept-id → query-template registry.
│                                4 concepts cover the canned-intent surface (D-13).
├── compile-intent.ts            PURE: (intent, catalogue) → DuckDBPlan.
│                                No I/O. JOINs taxonomy.sources to enforce Holy Law #9.
├── execute-plan.ts              IMPURE: (plan) → Promise<AnswerViewModel>.
│                                Calls query() from ../duckdb (D-05).
├── fixtures/
│   └── canned-intents.ts        4 PR-1 canned intents: party_totals, closest_contests,
│                                constituency_result, turnout_extremes.
├── model-registry.ts            Config-driven registry of swappable model entries
│                                (D-11). Currently 1 seed entry (D-16).
├── model-adapter.ts             Provider-dispatch + readiness state machine.
│                                The ONLY file that touches a runtime SDK (D-15).
└── extract-intent.ts            Question → InsightIntent via model + validate-or-retry
                                 loop (D-17, D-20).

frontend/src/routes/
└── Yenask.svelte                The chat surface (D-18, D-21) — composer, conversation
                                 log, starter chips, debug panel.

frontend/e2e/
└── yenask.spec.ts               One Playwright spec round-tripping the canned chip
                                 path through real DuckDB-WASM (D-08).
```

## Contracts

The lab is held together by five contracts. Modules MUST pass typed values across these boundaries — no `any`, no untyped JSON shoved between phases.

### `InsightIntent` (model output → compile input)

```ts
// contracts/insight-intent.ts (Zod schema, validated at the boundary)
{
  version: "insight.intent.v0",
  concept_id: "party_totals" | "closest_contests" | "constituency_result" | "turnout_extremes",
  filters: {
    state?: string,        // ISO 3166 sub-code (e.g. "in_s22" for Tamil Nadu)
    election_id?: string,  // ECI code (e.g. "AcGenMay2026")
    constituency?: string, // AC name or ECI no
    party?: string,        // ECI party code
    ...
  },
  ranking?: { by: string, dir: "asc" | "desc", limit: number }
}
```

The model is constrained to emit ONLY this shape. Anything else fails Zod validation and triggers a retry (D-17). The Zod schema is the entire safety boundary between citizen free text and DuckDB SQL — there is no other sanitisation layer. Rationale: plan-doc §17 [D-03](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-03--insightintent-contract-is-ts-zod-only-no-datasetsschemas-json-schema-mirror), [D-06](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-06--provenance-is-required-non-empty-at-the-zod-type-level-3-test-cases-enforce).

### `DuckDBPlan` (compile output → execute input)

```ts
// types.ts
{
  concept_id: string,            // REQUIRED first field (D-12)
  main_sql: string,              // The primary SELECT
  provenance_sql: string,        // SELECT that JOINs taxonomy.sources for source_strip
  slices: Array<{                // Per-plan slice-table registrations
    table_name: string,
    parquet_path: string,        // relative under /data/
    columns: string[]
  }>
}
```

Compile is a pure function. Same `(intent, catalogue)` → same plan, byte-for-byte. The `concept_id` lives at the top so the executor can dispatch slice-registration logic per concept (D-14).

### `AnswerViewModel` (execute output → render input)

```ts
// contracts/answer-viewmodel.ts
{
  columns: Array<{ id: string, label: string, format?: "number" | "percent" | "rank" }>,
  rows: Array<Record<string, string | number | null>>,
  source_strip: Array<SourceV2Row>,   // REQUIRED non-empty — Holy Law #9 enforced at type level
  empty_rows_message?: string,
  ...
}
```

If `source_strip` is empty, Zod throws. Three test cases enforce this at the contract layer (D-06).

### `GenerateResult` (model adapter output → extract loop input)

```ts
// model-adapter.ts (PR-3, D-20)
{
  text: string,                   // assistant reply, normalised across SDK shapes
  tokens_in: number,              // exact when tokenizer available; 0 if generate threw
  tokens_out: number,
  tokens_approximate: boolean,    // true when chars/4 fallback was used
  wall_ms: number                 // time inside the generate() call only
}
```

Every `ModelAdapter.generate()` returns this shape — provider implementations cannot return bare strings. The extract loop consumes this and produces per-attempt diagnostics.

### `ExtractAttempt` (one model call's observability record)

```ts
// extract-intent.ts (PR-3, D-20)
{
  attempt: number,                       // 1-based
  prompt_chars: number,
  tokens_in: number,
  tokens_out: number,
  tokens_approximate: boolean,
  wall_ms: number,
  raw_output: string,
  parse_status: "ok" | "json_error" | "zod_error" | "generate_error",
  parse_error?: string
}
```

Each call to `extractIntent()` returns `diagnostics.attempts_log: readonly ExtractAttempt[]` with one entry per attempt. The UI renders the full log in the Debug panel.

## Model adapter readiness state machine

`ModelAdapter.prepare()` drives a closed discriminated union the UI subscribes to:

```text
                                    ┌───────────────────┐
                                    │       idle        │
                                    └──────┬────────────┘
                                           │ prepare() called
                                           ▼
              ┌─────────────────────────────────────────────────────┐
              │  downloading { file, percent, loaded, total }       │
              │  - emitted per file, NOT aggregate                  │
              │  - per-file progress sweep                          │
              └──────┬───────────────────────────────────┬──────────┘
                     │ "done" / "ready" event            │ error
                     ▼                                   ▼
              ┌──────────────┐                    ┌──────────────────┐
              │   compiling  │                    │ failed { error } │
              └──────┬───────┘                    └──────────────────┘
                     │                                   │
                     ▼                                   │
              ┌──────────────┐                           │
              │     ready    │◄──────────────────────────┘
              └──────┬───────┘
                     │ generate() callable from here
                     ▼
              ┌─────────────────────────────────────────┐
              │ GenerateResult { text, tokens, wall_ms } │
              └─────────────────────────────────────────┘
```

The state transitions are captured into `Yenask.svelte`'s `statusHistory: StatusEvent[]` ring buffer (cap 50, consecutive same-file `downloading` ticks coalesce). The Debug log renders the timeline so an operator can see "downloaded model.onnx (12 MB) → downloaded tokenizer.json (1 MB) → compiling → ready" with timestamps.

Rationale: plan-doc §17 [D-11](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-11--model-registry-is-config-driven-multiple-models-are-first-class), [D-15](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-15--transformersjs-provider-locked-model-is-config-driven-and-swappable), [D-20](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-20--generate-exposes-tokens-inout--wall_ms-per-attempt-diagnostics-surface-as-first-class-observability).

## Model registry — adding / swapping a model

`MODEL_REGISTRY` in [`model-registry.ts`](../../../frontend/src/lib/yenask/model-registry.ts) is a `readonly ModelEntry[]`. Each entry declares:

| Field | Meaning |
| --- | --- |
| `id` | Stable kebab-case slug. Persisted in localStorage as the user pick. |
| `display_name` | Citizen-facing name shown in the picker. |
| `params_label` | Parameter-count label ("135M", "0.5B"). |
| `provider` | Runtime adapter — currently only `"transformers-js"`. |
| `repo_id` | HuggingFace repo id (e.g. `"HuggingFaceTB/SmolLM2-135M-Instruct"`). |
| `dtype` | Quantisation tag (`"q4f16"`, `"q8"`, `"fp16"`, `"fp32"`, ...). |
| `device` | `"wasm"` (stable, slower) \| `"webgpu"` (fast, currently crashes on q4f16) \| `"auto"`. |
| `estimated_download_mb` | Used for the Prepare-assistant panel's expectation copy. |
| `notes` | Operator-facing free text shown in the picker helper. |

**Swap the default**: change `DEFAULT_MODEL_ID` in the same file. No other code edit needed.

**Add an alternative**: append a new `ModelEntry` to the array. The picker (PR-2 UI scaffold) already iterates over the registry. New providers (e.g. `"litert-mediapipe"`) need a new dispatch arm in `createAdapter()` in [`model-adapter.ts`](../../../frontend/src/lib/yenask/model-adapter.ts) — rule of three; don't pre-create empty providers.

**Today's seed**: `smollm2-135m-instruct`, `dtype: "q4f16"`, `device: "wasm"`, ~88 MB cold-load. Pinned to wasm because `onnxruntime-web` WebGPU crashes on q4f16 SmolLM2 with `Mapping WebGPU buffer failed: Invalid buffer`. Rationale: plan-doc §17 [D-19](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-19--seed-model-device-pinned-to-wasm-webgpu-stays-opt-in-until-upstream-is-stable).

## Observability surface (PR-3)

The lab exposes three operator-readable signals — all of them OUT of the citizen turn body and INTO the Debug log section below the chat (D-21).

### Per-turn footer (compact, inside the citizen turn)

One line inside each assistant-answer bubble:

- **Model-extracted turn**: `Answered with SmolLM2-135M-Instruct: 1× attempt · ~248 tokens in · ~87 out · 2.1s total. See Debug log below for details.`
- **Canned-chip turn**: `Canned starter prompt — no model used.`

Approximate token counts (chars/4 fallback when the SDK doesn't expose `tokenizer.encode`) are prefixed with `~`. Exact counts have no prefix.

Testid: `data-testid="yenask-turn-footer"`.

### Assistant status timeline (Debug log)

The `statusHistory` ring buffer renders as a list of events with HH:MM:SS timestamps. Consecutive `downloading` events against the same file coalesce so a 100-frame progress sweep displays as one row instead of 100.

Testid: `data-testid="yenask-debug-status-timeline"`.

### Per-turn debug details (Debug log)

One `<details>` block per assistant-answer turn (one per assistant-failure turn too), keyed by turn id. Contains:

- `concept_id` badge (e.g. `party_totals`).
- Slice registrations list (one line per `(table_name, parquet_path)` pair).
- Main SQL — the `SELECT` that produced the answer rows.
- Provenance SQL — the `SELECT` that produced the source-strip rows.
- Per-attempt table (`yenask-debug-attempts`) — one row per `ExtractAttempt`: attempt#, prompt_chars, tokens_in, tokens_out, wall_ms, parse_status, parse_error.
- Raw model output — collapsible `<details>`. The full `raw_output` string from the LAST attempt.

Testids: `yenask-debug-turns`, `yenask-debug-attempts`, `yenask-computation` (relocated from PR-1's citizen-turn position into the debug panel — preserves the existing Playwright assertion zero-edit).

### What is NOT exposed

- The full prompt sent to the model — sensitive surface (system prompt + few-shot is hand-tuned); kept inside `extract-intent.ts` and not surfaced to the UI. If you need to inspect it during dev, hardcode a `console.log` in `extract-intent.ts` and remove before commit (per CLAUDE.md §7).
- Per-token streaming. Transformers.js supports streaming via `TextStreamer`; the current adapter does not subscribe. Generate is one round-trip.
- Cache management. transformers.js writes to IndexedDB (`transformers-cache` DB) automatically; there is no UI affordance to delete a cached model. Operators can clear via DevTools → Application → IndexedDB.

## Test seam

Per plan-doc §17 [D-08](../../../TODO/20260518-browser-governance-insight-assistant-plan.md#d-08--test-seam-vimockduckdb-for-vitest-playwright-e2e-owns-real-duckdb-wasm-round-trip), the lab uses a tiered test strategy:

| Tier | What it asserts | Where | Mocks |
| --- | --- | --- | --- |
| Unit | Pure functions: `compileIntent`, `extractJsonObject`, `buildSystemPrompt`, `countTokens` fallback | `*.test.ts` colocated | None (pure) |
| Contract | Zod schemas reject malformed input; Holy Law #9 source-strip non-empty | `compile-intent.test.ts`, `extract-intent.test.ts` | `vi.mock("../duckdb")` |
| Integration | Model adapter readiness state machine; token counting with/without tokenizer; extract loop's per-attempt diagnostics | `model-adapter.test.ts`, `extract-intent.test.ts` | Fresh `vi.fn()` per test (avoid `Object.assign` leakage across tests) |
| End-to-end | Canned-chip path round-trips through real DuckDB-WASM | `frontend/e2e/yenask.spec.ts` | None — real browser, real DuckDB-WASM |

**Anti-pattern to avoid**: mutating a shared mock pipeline with `Object.assign(handles.generateFn, { tokenizer })`. The tokenizer property leaks across test cases and the "no tokenizer" test still sees one. PR-3 fixed this — each tokenizer-related test now constructs a fresh `vi.fn().mockResolvedValueOnce(...)` pipeline.

The Playwright spec asserts the `yenask-computation` testid is visible and contains `"party_totals"` + `"election_results"`. PR-3 relocated this testid from inside the assistant-answer turn into the Debug log per-turn details block — the spec passes unchanged because the testid was moved (not deleted).

## What ships today vs what does not

| Surface | Status |
| --- | --- |
| `/dev/yenask` route + chat surface + composer + starter chips | ✅ Shipped (PR-2) |
| 4 canned intents (party_totals, closest_contests, constituency_result, turnout_extremes) | ✅ Shipped (PR-1) |
| Real model load (`SmolLM2-135M-Instruct` via Transformers.js) | ✅ Shipped (PR-2) |
| Free-text question → InsightIntent extraction with validate-or-retry | ✅ Shipped (PR-2) |
| Source-strip (Holy Law #9 provenance) on every answer | ✅ Shipped (PR-1) |
| Token in/out + wall_ms observability + per-attempt diagnostics | ✅ Shipped (PR-3) |
| Debug log section below chat (status timeline + per-turn details) | ✅ Shipped (PR-3) |
| Multiple models in the registry (picker UI ready, only 1 entry) | ⏳ Registry supports it; UI shows the picker but only SmolLM2-135M is currently registered |
| Model-download / delete / cache-management UI | ❌ Not built (transformers.js caches automatically; no UI to inspect or delete) |
| Two-stage architecture (intent extractor + SQL generator) | ❌ Not built — current pipeline is single-stage (one extract call, then PURE compile) |
| Speech-to-text / text-to-speech | ❌ Not built |
| WebGPU runtime (vs current wasm) | ❌ Blocked on upstream `onnxruntime-web` WebGPU q4f16 crash |
| Multi-turn context awareness ("what about Kerala?") | ❌ Not built — every turn is extracted stateless (D-18) |

## See also

- Plan-doc with full design-decision log (D-01 through D-21): [`TODO/20260518-browser-governance-insight-assistant-plan.md`](../../../TODO/20260518-browser-governance-insight-assistant-plan.md)
- Internal map of `lib/yenask/`: [`frontend/src/lib/yenask/AGENTS.md`](../../../frontend/src/lib/yenask/AGENTS.md)
- Holy Law #1 (static-first): [CLAUDE.md](../../../CLAUDE.md)
- Holy Law #9 (provenance is mandatory): [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md)
- Production frontend overview: [overview.md](overview.md)
- Sibling lab pattern (Psephlab): [psephlab.md](psephlab.md)

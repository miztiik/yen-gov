# `frontend/src/lib/yenask/` - YENASK lab internals

**Last Updated**: 2026-05-26
**Plan-doc**: [`TODO/20260518-browser-governance-insight-assistant-plan.md`](../../../../TODO/20260518-browser-governance-insight-assistant-plan.md)

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

## What lives here

YENASK is a dev-only browser lab mounted at `/lab/yenask` (route moved
from `/dev/yenask` per [ADR-0040](../../../../docs/architecture/frontend/yenask/brand-and-route.md#adr-0040-yenask-brand-and-lab-route)).
It turns a citizen governance question into a validated `InsightIntent`,
then runs DuckDB-WASM against the canonical store to produce an
`AnswerViewModel`. (Canonical store: X1a flipped `dim_parties` +
`taxonomy.sources` onto long-format CSV under `datasets/data/` via the
`registerCsvAsTable` seam in `lib/duckdb.ts`; dim_acs +
elections_candidacies parquets are STILL READ from the parquet store at
startup by `semantic-catalogue.ts` and retire via B3. See the
[platform-reset plan](../../../../TODO/20260603-data-and-charting-platform-reset-plan.md).)

The CITIZEN-FACING brand is **Yen-Ask** (logo + page title only). All
MODULE identifiers stay as `yenask` (directory name, route slug, LS key,
testids, ADR titles). Don't unify them - see ADR-0040 section "Brand vs
identifier separation" (supersedes ADR-0039 section D-33's earlier route
placement).

## Layout

| File | Role | Phase |
| --- | --- | --- |
| `contracts/insight-intent.ts` | Zod schema for what the model is allowed to output. Discriminated by `version: "insight.intent.v0"`. | 1 |
| `contracts/answer-viewmodel.ts` | Zod schema for what the renderer is allowed to display. `source_strip` is REQUIRED non-empty. | 1 |
| `types.ts` | Shared TS types not covered by Zod (DuckDBPlan, AnswerRow, etc.) | 1 |
| `semantic-catalogue.ts` | Derived at startup from `datasets/manifest.json` + the canonical CSV taxonomy (X1a flipped `dim_parties` + `taxonomy.sources` via `registerCsvAsTable`; `dim_acs` + `elections_candidacies` parquet reads remain pending B3). MUST NOT scan fact tables (section 17 D-04). | 1 |
| `concepts.ts` | Hand-authored citizen-question -> query-template mapping. | 1 |
| `compile-intent.ts` | PURE: `(intent, catalogue) -> DuckDBPlan`. No I/O. Joins the canonical source citation table (`datasets/data/entities/source.csv` via X1a `registerCsvAsTable('taxonomy.sources')`) to enforce Holy Law #9. | 1 |
| `execute-plan.ts` | IMPURE: `(plan) -> Promise<AnswerViewModel>`. Calls `query()` from `../duckdb`. | 1 |
| `extract-intent.ts` | `extractIntent(question, catalogue, adapter, opts?)`. Slice E.2: optional `opts.embed: EmbedFn` wires the retrieval seam - top-K narrowing + Gregor D-32 substring fallback when top-1 cosine < `COSINE_THRESHOLD` (0.6). Also exports `substringFallback(question, k)` for deterministic fallback ranking. `ExtractAttempt` carries `embed_ms: number \| null`; `ExtractDiagnostics` carries `top_concepts? \| concept_selection? \| selected_concept_ids?`. Behaviour is unchanged when `opts.embed` is omitted (back-compat). | 2, extended in 3 (E.2) |
| `fixtures/canned-intents.ts` | The four PR-1 canned intents (party_totals, closest_contests, constituency_result, turnout_extremes). | 1 |
| `fixtures/intent-eval.json` | 20 labelled citizen-style questions (5 per concept) - Slice E.2 regression alarm (Andre + Hamel + Fowler eval-as-contract lock; ADR-0039 + plan-doc D-32). Vitest `catalogue-embed.test.ts` asserts `substringFallback` top-1 accuracy >=90% (5pp tolerance under the 95% baseline measured 2026-05-24). | 3 (E.1) |
| `model-registry.ts` | TS config array, one entry per supported model. Discriminated union on `task: "text-generation" \| "embeddings"`; picker UI uses `listTextGenerationModels()`; Slice E uses `listEmbeddingsModels()`. | 2, expanded in 3 (E.1) |
| `model-adapter.ts` | Dispatches by `provider` (Transformers.js \| LiteRT \| ...). | 2 |
| `catalogue-embed.ts` | Slice E.1 retrieval surface. Hand-authored `CONCEPT_CATALOGUE` + pure-math helpers (`cosineSimilarity`, `rankByCosine`) + `findTopKConcepts(question, k, embed)`. EmbedFn is dependency-injected; module never imports transformers.js directly. ADR-0039. | 3 (E.1) |

## Removal contract (D-01)

**Nothing in `frontend/src/` outside `lib/yenask/` and `routes/Yenask.svelte`
may import yenask-internal symbols.** Removing the lab is `git rm` of those
two paths + delete two lines from `frontend/src/main.ts` (the import line
and the route registration line).

The reverse is encouraged: yenask imports freely from production
`frontend/src/lib/` (`duckdb`, `charts/*`, `SourceListV2`, `colors/*`,
`format`, `url`, `states.svelte`). See plan-doc section 17 D-02.

## Test seam

Per section 17 D-08, vitest tests in this directory mock `../duckdb`:

```ts
vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerSlice: vi.fn(),
  registerTable: vi.fn(),
}));
```

Mirrors the pattern in `frontend/src/lib/psephlab/canonical-loaders.test.ts`
and `frontend/src/lib/view-models/constituency.test.ts`. The real
DuckDB-WASM round-trip is covered by ONE Playwright e2e at
`frontend/e2e/yenask.spec.ts`.

## Reading order for a new contributor

1. The plan-doc section 17 design-log (`D-01` onward) - every decision lives there.
2. `contracts/insight-intent.ts` and `contracts/answer-viewmodel.ts` -
   the two contracts everything else hangs off of.
3. `compile-intent.ts` - the heart of the safety boundary.
4. `Yenask.svelte` (in `../../routes/`) - the UI shell that wires it all.

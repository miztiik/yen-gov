# StackedTrendV2 — citation-ledger-aligned stacked-trend model

Structural-only foundation for Phase 2 of
[TODO/20260518-frontend-charting-modernisation-plan.md](../../../../../TODO/20260518-frontend-charting-modernisation-plan.md).
This package ships the **v2 contract** (zod schema + types + fixture) and
the **inert component shell** (`StackedTrendV2.svelte` at the parent
`charts/` level — type-check green, no caller mounts it yet).
Behavioural changes (segmented mode, pinned readout, inline labels,
missing-hatch, motion, export) and caller migration land in subsequent
Track-D commits (Phases 2.2…2.7 and D10…D13).

## Phase 2.1 split (R-09)

- **2.1a** (PR #105 — DONE): types + zod model + fixture (this directory).
- **2.1b** (PR-6 / #108 — DONE): component shell at
  [`../StackedTrendV2.svelte`](../StackedTrendV2.svelte) consuming the v2
  types, returning headline + honesty chrome + an empty `<svg><g/></svg>`
  bar-layer placeholder. **Type-check green; zero render coverage; no
  caller mounts it yet.** Phases 2.2..2.7 layer behaviour onto this seam
  one PR at a time.
- **2.1 helpers** (PR-7 — this PR): pure view-model helpers
  ([`./helpers.ts`](./helpers.ts)) extracted from v1's inline math —
  `barTotal`, `maxBarTotal`, `segmentSharePct`, `segmentVisualHeightPct`,
  `visibleCategoryIds`, `isLabelEligible`, `readoutRows` — plus the
  `ReadoutRow` interface used by the future pinned-readout panel
  (Phase 2.3). All helpers are pure, exhaustively unit-tested
  ([`./helpers.test.ts`](./helpers.test.ts), 41 cases) for percent /
  absolute modes, zero totals, `__OTHER__`, missing, not_applicable,
  null values, and `bar.total` overrides. **The shell does NOT consume
  these helpers yet** — the wiring slice is Phase 2.1c.

## R-11 deferral (Phase 2.2 contract test)

The plan's R-11 resolution asks for "a contract-tier test under
`frontend/src/contracts/` per Phase 2.2: loads a real fixture Parquet
shard via DuckDB-WASM, runs the helper, asserts output validates
against the v2 props zod schema." This belongs to Phase 2.2 (segmented
mode control + citizen-visible behaviour), not Phase 2.1.

It is also infeasible inside vitest — `frontend/src/lib/canonical/manifest.test.ts`
documents the convention:

> The DuckDB-WASM round-trip lives in Playwright (Phase 1+) since vitest
> can't load DuckDB-WASM in node env.

The R-11 round-trip will therefore land as a Playwright spec under
`frontend/e2e/` once a caller migrates and the helpers run inside a
mounted page (Track-D D10). The pure unit coverage in
`./helpers.test.ts` is the Phase 2.1 tier — fast, deterministic, every
edge case in §15's "unit" tier.

## Branch by Abstraction (R-08)

v2 ships **alongside** [`frontend/src/lib/charts/stacked-trend/`](../stacked-trend/)
(v1). The v1 module is **NOT** modified, **NOT** deprecated, and **NOT**
removed during the migration window. Migration rules:

- One caller migration per PR (≤3 callers per PR per R-08).
- Every caller PR adds its own Playwright assertion on the migrated route.
- The v1 module is deleted in a single final PR after the last caller migrates.

## What changes between v1 and v2

| Surface | v1 (`stacked-trend/types.ts`) | v2 (this module) |
|---|---|---|
| Source rows | `{ url, fetched_at, name?, authority? }` | 11-column v2.0 ledger row (per ADR-0032 / R-24) |
| Schema version | implicit | `schema_version: "2.0"` (literal) |
| Categories / bars / segments / honesty / headline | as-is | **identical semantics** — v2 is polish, not rewrite |

Every other shape on the v1 zod model is mirrored verbatim. The point
of v2 is the **source contract** + the shell/behavioural slices that
follow (segmented mode control, pinned readout, inline labels,
missing-hatch, motion, export).

## Forbidden surfaces (R-24)

These v1 `StackedTrendSource` keys are **structurally absent** from the
v2 source row:

- `url` → use `url_main` (nullable for `archived-snapshot` / `transcribed` / `editorial`)
- `fetched_at` → moved to `.runtime/<adapter>/<source_id>.json` sidecars per ADR-0032 P.0e

The v2 zod schema strips unknown keys by default, so a v1-tainted source
row (containing `url` or `fetched_at`) parses cleanly but the renderer
sees `undefined` for those fields — the citizen footer **cannot**
display retired telemetry even by accident. The unit test
[`types.test.ts`](./types.test.ts) "StackedTrendV2Source — v2 ledger
discipline" pins this behaviour.

## Where the source ledger comes from

Adapters resolve each `source_id` against `taxonomy.sources` (a
manifest-registered v2.0 ledger — see
[`frontend/src/contracts/sources-v2-shape.test.ts`](../../../contracts/sources-v2-shape.test.ts))
and copy the 11 fields **inline** onto the `StackedTrendV2Model`. The
renderer is DuckDB-free; the join happens once, at adapter time.

When the same chart's data has been migrated to a shared chart-shell /
footer that reads `SourceList` v2 directly from `taxonomy.sources` via
the manifest `table_id`, the inline copy will be redundant and an
adapter pass will drop it. Until then, denormalisation keeps the
renderer self-contained.

## Constraints

| Rule | Where it lives |
|---|---|
| R-08 (Branch by Abstraction) | this module ships alongside v1 |
| R-09 (split 2.1a / 2.1b) | 2.1a = types only (this dir); 2.1b = shell at [`../StackedTrendV2.svelte`](../StackedTrendV2.svelte), zero render |
| R-24 (citation-ledger fields only) | `StackedTrendV2Source` zod schema |
| R-25 (coordination gate) | per-PR body, four-facts |
| R-27 (no JSON projections of canonical Parquet) | this module reads no parquet at all |
| R-28 (manifest `table_id` resolution) | adapters resolve `taxonomy.sources` via manifest; this module accepts the denormalised row inline |

## Fixture

[`__fixtures__/minimal.fixture.json`](./__fixtures__/minimal.fixture.json)
is the minimal-but-valid model — 3 periods, 5 categories, both
confidence tiers represented, one missing segment with availability_label,
one methodology series break. The fixture round-trips through
`StackedTrendV2Model.parse()` cleanly; the round-trip is enforced by
the first test in `types.test.ts`.

# StackedTrendV2 — citation-ledger-aligned stacked-trend model

Structural-only foundation for Phase 2 of
[TODO/20260518-frontend-charting-modernisation-plan.md](../../../../../TODO/20260518-frontend-charting-modernisation-plan.md).
This package ships the **v2 contract** (zod schema + types + fixture).
The render shell, behavioural changes, and caller migration land in
subsequent Track-D commits (D2…D13).

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
| R-09 (split 2.1a / 2.1b) | this PR is 2.1a — types only, zero render |
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

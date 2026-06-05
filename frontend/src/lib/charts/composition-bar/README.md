# composition-bar - diverging-bar adapter package

This package is the **view-model toolkit** for the single-entity 100%-stacked composition bar. It is consumed by [`CategoryBar.svelte`](../CategoryBar.svelte) `mode="diverging"` (the post-F2a.5.2 renderer). It does NOT ship its own Svelte component; the renderer body lives in `CategoryBar.svelte` and was lifted byte-identical from the retired `lib/CompositionBar.svelte` in F2a.5.1.

The package is analogous to:
- [`../bar-view-models/`](../bar-view-models/) - VM toolkit for `CategoryBar mode="ranked"`.
- [`../multi-dim-view-models/`](../multi-dim-view-models/) - VM toolkit for `CategoryBar mode="stacked"`.
- [`../time-view-models/`](../time-view-models/) - VM toolkit for time-series renderers.

Upstream Phase context: shipped as the three-PR slice (a) renderer + (b) adapter/experiment + (c) mount per R-16 of the [Phase 3.6 charting-modernisation plan snapshot](../../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md). F2a.5 (2026-06-05) consolidated the standalone renderer into `CategoryBar.svelte`; the adapter / helpers / types / fixtures stayed put.

## What this is

A generic, single-entity, single-period horizontal 100%-stacked composition. Generic = NOT election-specific; the same view-model + renderer combo handles party seat composition, energy fuel mix, age-band composition, etc. Domain bindings (party palette, NOTA wedge, FPTP framing) live in adapters that emit the typed view-model defined in [`types.ts`](./types.ts).

The package's contract surface is what the renderer treats as opaque: model, sources, segments, fills, captions. The renderer never imports `categoryColour` / `partyColour` and never names a party / fuel / age band - that knowledge is the adapter's job.

## Surfaces

| Path | Role |
| --- | --- |
| [`types.ts`](./types.ts) | Zod contract: `CompositionBarModel`, `CompositionBarSegment`, `CompositionBarHonestyBanner`. |
| [`helpers.ts`](./helpers.ts) | Pure: `totalSegmentValue`, `shareOfTotalPct`, `projectSegments`, `formatSegmentReadout`, `segmentsSumMatchesTotal`. |
| [`helpers.test.ts`](./helpers.test.ts) | 22 vitest cases on the geometry / share / lift / sum-check math. |
| [`types.test.ts`](./types.test.ts) | 18 vitest cases on the zod contract + fixture round-trip + tail / dominant-segment assertions. |
| [`adapter-elections-seats.ts`](./adapter-elections-seats.ts) | Pure assembler + async DuckDB-WASM loader. Top-N=8 with visible Others tail; NOTA via existing anchor; FPTP caption verbatim. |
| [`adapter-elections-seats.test.ts`](./adapter-elections-seats.test.ts) | 24 vitest cases - sort / top-N edge cases (N=2/5/8 + degenerate) / NOTA / FPTP caption / loader manifest-registration contract. |
| [`experiment-definition.json`](./experiment-definition.json) | GrowthBook OSS experiment: control (SeatDonut only) vs treatment (diverging composition bar + SeatDonut); 50/50; cookie-sticky on `visitor_id`. |
| [`experiment-definition.test.ts`](./experiment-definition.test.ts) | 14 vitest cases - experiment shape + R-28 manifest contract on the adapter. |
| [`__fixtures__/gujarat-2022-seats.json`](./__fixtures__/gujarat-2022-seats.json) | Single-party-dominant fixture (BJP 156 / 182 = 85.7%). Drives the round-trip + sum-check tests. |
| [`index.ts`](./index.ts) | Barrel. |
| [`../CategoryBar.svelte`](../CategoryBar.svelte) `mode="diverging"` | The Svelte 5 renderer that consumes this package's view-model. Body lifted byte-identical from the retired `lib/CompositionBar.svelte` in F2a.5.1. |

## Doctrine

- **R-08 Branch by Abstraction** - `SeatDonut.svelte` / `ParliamentArc.svelte`
  / `AcStackedBar.svelte` continue to ship. The diverging composition bar
  (`CategoryBar mode="diverging"`) mounts alongside, not in place of, the
  existing donut.
- **R-16 three-PR split** - renderer / adapter+experiment / mount.
  Each commit shipped and reviewed independently. Post-F2a.5: the renderer
  slice lives inside `CategoryBar.svelte`, not in a standalone component.
- **R-24 / R-28** - the footer slot delegates to `<SourceListV2>` via
  `<ChartShell>`. No fetch telemetry, no parquet path literal.
- **R-27** - no JSON projection of canonical parquet. The adapter reads
  the state-scoped `elections.election_results` slice and supporting
  tables via manifest registration and emits this view-model directly.

## Renderer rules (per plan lines 1308-1314)

These rules describe what the consuming renderer (`CategoryBar.svelte` `mode="diverging"` since F2a.5.2; `lib/CompositionBar.svelte` pre-F2a.5.2) MUST honour. The package's job is to emit a view-model the renderer can paint without breaking these rules.

- **No domain logic.** The renderer never names a party, fuel type, or
  age band. Everything that distinguishes the chart's subject sits in
  the adapter.
- **Visible tail.** When the adapter emits an `OTHERS` segment with
  `is_tail: true`, the renderer paints it as a visible swatch with its
  own label. The tail is *never* collapsed to a footnote.
- **Adapter-supplied fills.** Every segment carries its `fill` in the
  view-model. The renderer does not call `categoryColour` or
  `partyColour` - that's the adapter's job.
- **No variant prop.** No `variant: "donut" | "pie" | "sunburst"`
  knob. The diverging composition bar is by definition a horizontal
  stacked bar. Radial composition is `SeatDonut` / `ParliamentArc`'s
  job (existing components, single-state geometry).

## Helper rules

- **Tiny-segment lift.** Segments below `MIN_VISUAL_WIDTH_PCT` (0.6%)
  get lifted to `MIN_VISUAL_WIDTH_PCT`; the borrowed width is
  subtracted from the largest segment. Mirrors `SeatDonut.visual_angles`
  (`MIN_VISUAL_ANGLE = 0.024`) — same trick for the same reason. The
  honest share is preserved on `share_pct` for the readout / legend.
- **Sum stays at 100.** After the lift the projected `width_pct`s sum
  to 100 within float tolerance — vitest pinned at `toBeCloseTo(100, 6)`.
- **Zero-value filter.** `projectSegments` drops zero-value segments
  before laying out (a zero-width rect paints nothing anyway).

## Test gates

- `helpers.test.ts` — 22 cases: sum / share math, projection geometry,
  tiny-segment lift, single-party-dominant case, format readout,
  sum-check tolerance.
- `types.test.ts` — 18 cases: zod round-trip, schema_version literal
  guard, total_value / segments validation, default handling for
  optional fields, segment-level discipline (hex fill, non-negative
  value), Gujarat fixture sum-check + single-tail / dominant-segment
  assertions.

## What is intentionally NOT in this PR

| Out of scope | Where it lands |
| --- | --- |
| Mount on any route | Phase 3.6 (c) |
| Playwright on the rendered DOM | Phase 3.6 (c) |
| Summary-copy dominance-verb suppression test | Phase 3.6 (c) |
| Vote-share twin (`adapter-elections-votes.ts`) | Phase 3.6 (c) — second `<CompositionBar>` instance on the same card |
| Alliance binding | DEFERRED-A (separate workstream; needs `dim_alliances.parquet`). |

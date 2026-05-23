<script lang="ts">
  // CompositionBar — single-entity 100%-stacked horizontal bar (Phase 3.6 (a)).
  //
  // Per TODO/20260518-frontend-charting-modernisation-plan.md Phase 3.6.
  //
  // Generic; NOT election-specific. Renders any single-entity,
  // single-period composition as a horizontal 100%-stacked bar. Domain
  // bindings (party seats, fuel mix, age bands) live in adapters; the
  // renderer takes a typed view-model defined in
  // `./composition-bar/types.ts`.
  //
  // Doctrine ties:
  //
  //   - R-08 Branch by Abstraction: this PR ships the renderer with
  //     ZERO callers. v1 `SeatDonut.svelte` / `ParliamentArc.svelte`
  //     / `AcStackedBar.svelte` continue to ship untouched.
  //     Per-route mounts happen in the Phase 3.6 (c) mount PR.
  //
  //   - R-16 three-PR split: this PR is the renderer slice only. The
  //     adapter (`adapter-elections-seats.ts`) + GrowthBook experiment
  //     definition ship in (b); the per-state mount + Playwright in (c).
  //
  //   - R-24 / R-28: the footer slot delegates to `<SourceListV2>` via
  //     `<ChartShell>`. No fetch telemetry, no parquet path literal.
  //     Sources arrive as a typed `readonly SourceV2Row[]` resolved
  //     upstream from `taxonomy.sources` via the manifest-registered
  //     `table_id`.
  //
  //   - Plan line 1310: "Tail handling: when the upstream adapter
  //     emits an `others` segment, it renders as a visible swatch in
  //     the bar with its own label; the renderer never collapses tail
  //     to a footnote." — implemented by treating tail as a regular
  //     segment with `is_tail: true` carried through to the DOM via
  //     `data-is-tail`.
  //
  //   - Plan line 1311: "Fill: segment fills are passed in by the
  //     adapter; renderer never knows about parties, power sources, or
  //     age bands." — `fill` is required on every segment; the
  //     renderer never imports `categoryColour` / `partyColour`.
  //
  //   - Plan line 1313: "Forbidden: do NOT add a `variant: 'donut' |
  //     'pie' | 'sunburst'` prop." — no variant prop here.
  //
  //   - Plan line 1320: "Caption / framing: the FPTP doctrine
  //     footnote already used by `adapter-elections.ts` line 165 is
  //     the canonical wording for FPTP context; reuse the exact
  //     string." — the renderer surfaces `caption_fptp` as a footnote
  //     under the bar; the adapter supplies the verbatim string.
  //
  // CLAUDE.md §0 a11y descoped: no `aria-*`, no `role`. Visible
  // affordances only.
  //
  // Vitest gate: pure helpers (`./composition-bar/helpers.ts`) +
  // contract (`./composition-bar/types.ts`) — 40 cases total across
  // `helpers.test.ts` (22) and `types.test.ts` (18). Component-level
  // DOM assertions land in Playwright when the Phase 3.6 (c) mount
  // ships — vitest is node-env without jsdom (see
  // `IndicatorChoropleth.boundaries.test.ts` comment line 4).

  import ChartShell from "./charts/ChartShell.svelte";
  import { projectSegments } from "./charts/composition-bar/helpers";
  import type {
    CompositionBarModel,
  } from "./charts/composition-bar/types";
  import type {
    ChartShellActionSpec,
    SourceV2Row,
  } from "./charts/chart-shell/types";

  interface Props {
    /** The typed view-model emitted by the adapter. The renderer
     *  treats this as opaque: domain knowledge stays in the adapter. */
    model: CompositionBarModel;
    /** Footer source ledger (v2.0). Forwarded to `<ChartShell>` →
     *  `<SourceListV2>`. */
    sources?: readonly SourceV2Row[];
    /** Optional schema-version label for the source list footer. */
    schema_version?: string | null;
    /** Optional footer action specs forwarded to `<ChartShell>`.
     *  Closed-enum vocabulary (`view_data` / `download` / `copy_link`
     *  / `share` / `reset_view` / `full_range`); unknown ids are
     *  dropped silently. */
    actions?: readonly ChartShellActionSpec[];
  }

  const {
    model,
    sources,
    schema_version = null,
    actions = [],
  }: Props = $props();

  // Project segments onto the 0..100 horizontal axis with the
  // tiny-segment lift applied. Honest shares are preserved on
  // `share_pct` so the legend / data-share attribute can show the
  // truth even when the bar geometry is lifted to keep tiny segments
  // visible.
  const projection = $derived(projectSegments(model.segments));

  // Pretty-formatter for the centre denominator label. Renderer
  // never formats segment numbers (the legend pulls value + share
  // straight from the projection).
  const total_label = $derived(
    `${model.total_value.toLocaleString()} ${model.total_unit}`,
  );
</script>

<ChartShell
  title={model.label}
  subtitle={model.subtitle ?? undefined}
  honesty_banners={model.honesty_banners}
  {sources}
  {schema_version}
  {actions}
>
  <div
    class="composition-bar"
    data-component="composition-bar"
    data-dimension={model.dimension}
    data-segment-count={projection.length}
  >
    <div class="composition-bar__header">
      <span class="composition-bar__total" data-slot="total">
        {total_label}
      </span>
    </div>

    {#if projection.length === 0}
      <p class="composition-bar__empty" data-slot="empty">
        No data to display.
      </p>
    {:else}
      <svg
        class="composition-bar__svg"
        viewBox="0 0 100 8"
        preserveAspectRatio="none"
        data-slot="bar"
      >
        {#each projection as p (p.id)}
          <rect
            x={p.x_pct}
            y={0}
            width={p.width_pct}
            height={8}
            fill={p.fill}
            data-segment-id={p.id}
            data-swatch-role={p.swatch_role}
            data-is-tail={p.is_tail ? "true" : "false"}
            data-share-pct={p.share_pct.toFixed(2)}
            data-value={p.value}
          ></rect>
        {/each}
      </svg>

      <ul class="composition-bar__legend" data-slot="legend">
        {#each projection as p (p.id)}
          <li
            class="composition-bar__legend-item"
            data-segment-id={p.id}
            data-swatch-role={p.swatch_role}
            data-is-tail={p.is_tail ? "true" : "false"}
          >
            <span
              class="composition-bar__swatch"
              style:background={p.fill}
              aria-hidden="true"
            ></span>
            <span class="composition-bar__legend-label">{p.label}</span>
            <span class="composition-bar__legend-value">
              {p.value.toLocaleString()}
            </span>
            <span class="composition-bar__legend-share">
              ({p.share_pct.toFixed(1)}%)
            </span>
          </li>
        {/each}
      </ul>
    {/if}

    {#if model.caption_fptp}
      <p
        class="composition-bar__caption"
        data-slot="caption-fptp"
      >
        {model.caption_fptp}
      </p>
    {/if}
  </div>
</ChartShell>

<style>
  /* Layout-only. Visual tokens stay Tailwind-side once a real
     adapter lands; this stylesheet is the minimum so the structural
     PR previews cleanly without callers. */
  .composition-bar {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .composition-bar__header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }
  .composition-bar__total {
    font-size: 0.8125rem;
    font-weight: 600;
    color: rgb(15 23 42); /* slate-900 */
  }
  .composition-bar__svg {
    display: block;
    width: 100%;
    height: 1.25rem;
    border-radius: 0.25rem;
    overflow: hidden;
    background: rgb(241 245 249); /* slate-100 — visible behind any gap */
  }
  .composition-bar__legend {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.875rem;
  }
  .composition-bar__legend-item {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    color: rgb(51 65 85); /* slate-700 */
  }
  .composition-bar__swatch {
    display: inline-block;
    width: 0.625rem;
    height: 0.625rem;
    border-radius: 0.125rem;
  }
  .composition-bar__legend-label {
    font-weight: 500;
  }
  .composition-bar__legend-value {
    color: rgb(71 85 105); /* slate-600 */
    font-variant-numeric: tabular-nums;
  }
  .composition-bar__legend-share {
    color: rgb(100 116 139); /* slate-500 */
    font-variant-numeric: tabular-nums;
  }
  .composition-bar__caption {
    margin: 0;
    font-size: 0.6875rem;
    color: rgb(100 116 139); /* slate-500 */
    line-height: 1.4;
  }
  .composition-bar__empty {
    margin: 0;
    padding: 0.5rem 0;
    font-size: 0.75rem;
    color: rgb(148 163 184); /* slate-400 */
  }
</style>

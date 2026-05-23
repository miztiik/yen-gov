<script lang="ts" generics="T">
  // HorizontalGroupedBar — Phase 3.5 generic renderer.
  //
  // Consumes a `GroupedBarViewModel<T>` built by
  // `frontend/src/lib/charts/multi-dim-view-models/buildHorizontalGroupedBarViewModel`.
  //
  // Doctrine:
  //
  //   - Pure renderer. Zero data fetching. Zero charting library.
  //   - Layout: rows top→bottom; within each row, groups left→right.
  //     Each group renders as a thin bar whose width is
  //     `value / max_cell_value` (clamped 0..1) of the bar-area width.
  //   - Honesty: missing cells render as a light slate hatch placeholder
  //     so true-zero never reads as missing data.
  //   - Pinned rows get an amber left accent.
  //   - Value labels only on cells where `show_value_label === true`
  //     (set by the builder per the `label_threshold` policy).
  //   - Wrapped in ChartShell when `chart_title` is supplied; renderers
  //     may also be used inline (children-style) — pass
  //     `wrap_in_shell={false}` for the inline case.
  //   - No interactivity in v1: this is a static comparison view.
  //   - CLAUDE.md §0: no aria/role; affordances stay visible.

  import type { Snippet } from "svelte";
  import type {
    SourceV2Row,
    ChartShellHonestyBanner,
  } from "./chart-shell/types";
  import type { GroupedBarViewModel } from "./multi-dim-view-models";
  import ChartShell from "./ChartShell.svelte";

  interface Props {
    /** View-model from `buildHorizontalGroupedBarViewModel`. */
    view_model: GroupedBarViewModel<T>;
    /** Citizen-readable chart title. Required when `wrap_in_shell` (default true). */
    chart_title?: string;
    /** Optional subtitle (comparability / attribution one-liner). */
    chart_subtitle?: string | null;
    /** Optional honesty banners. */
    honesty_banners?: readonly ChartShellHonestyBanner[];
    /** Optional source ledger. */
    sources?: readonly SourceV2Row[];
    /** Optional schema-version label. */
    schema_version?: string | null;
    /** Wrap the chart body in `<ChartShell>`. Default true. Set false for inline embedding. */
    wrap_in_shell?: boolean;
    /** Optional `value` formatter for the cell labels. Default `Number(v).toLocaleString()`. */
    format_value?: (v: number) => string;
    /** Bar height (px) per group within a row. Default 12. */
    bar_height?: number;
    /** Gap (px) between groups within a row. Default 2. */
    bar_gap?: number;
    /** Gap (px) between rows. Default 12. */
    row_gap?: number;
    /** Render a colour-chip legend above the chart body. Default true. */
    show_legend?: boolean;
    /** Optional toolbar snippet (mode toggles, etc.). */
    toolbar?: Snippet;
  }

  let {
    view_model,
    chart_title,
    chart_subtitle = null,
    honesty_banners = [],
    sources,
    schema_version = null,
    wrap_in_shell = true,
    format_value = (v: number) => Number(v).toLocaleString(),
    bar_height = 12,
    bar_gap = 2,
    row_gap = 12,
    show_legend = true,
    toolbar,
  }: Props = $props();

  // Width fraction in [0, 1]; null / missing returns 0.
  function widthFrac(value: number | null, max_abs: number): number {
    if (value === null || value === undefined) return 0;
    if (max_abs <= 0) return 0;
    const f = Math.abs(value) / max_abs;
    if (!Number.isFinite(f)) return 0;
    return Math.min(1, Math.max(0, f));
  }
</script>

{#snippet body()}
  <div class="hgb" data-component="horizontal-grouped-bar">
    {#if show_legend && view_model.group_order.length > 0}
      <ul class="hgb__legend" data-slot="legend">
        {#each view_model.group_order as g (g.id)}
          <li class="hgb__legend-item" data-group-id={g.id}>
            <span
              class="hgb__legend-chip"
              style:background={legendColour(g.id, view_model)}
            ></span>
            <span class="hgb__legend-label">{g.label}</span>
          </li>
        {/each}
      </ul>
    {/if}
    <ol class="hgb__rows" data-slot="rows">
      {#each view_model.rows as r (r.id)}
        <li
          class="hgb__row"
          class:hgb__row--pinned={r.is_pinned}
          class:hgb__row--missing={r.is_missing}
          data-row-id={r.id}
          data-rank={r.rank ?? ""}
          data-pinned={r.is_pinned}
          data-missing={r.is_missing}
          style:--hgb-row-gap="{row_gap}px"
        >
          <div class="hgb__row-label" title={r.label}>
            {r.label}
            {#if r.is_pinned}<span class="hgb__row-pin">pinned</span>{/if}
          </div>
          <ul
            class="hgb__cells"
            data-slot="cells"
            style:gap="{bar_gap}px"
          >
            {#each r.cells as c (c.group_id)}
              <li
                class="hgb__cell"
                class:hgb__cell--missing={c.is_missing}
                data-group-id={c.group_id}
                data-missing={c.is_missing}
                title="{c.group_label}: {c.is_missing ? 'no data' : format_value(c.value as number)}"
                style:height="{bar_height}px"
              >
                {#if c.is_missing}
                  <span
                    class="hgb__cell-hatch"
                    aria-hidden="true"
                  ></span>
                {:else}
                  <span
                    class="hgb__cell-fill"
                    style:background={c.colour ?? "currentColor"}
                    style:width="{(widthFrac(c.value, view_model.max_cell_value) * 100).toFixed(3)}%"
                  ></span>
                {/if}
                {#if c.show_value_label && !c.is_missing}
                  <span class="hgb__cell-label" data-slot="cell-label">
                    {format_value(c.value as number)}
                  </span>
                {/if}
              </li>
            {/each}
          </ul>
        </li>
      {/each}
    </ol>
  </div>
{/snippet}

{#if wrap_in_shell && chart_title}
  <ChartShell
    title={chart_title}
    subtitle={chart_subtitle}
    {honesty_banners}
    {sources}
    {schema_version}
    {toolbar}
  >
    {@render body()}
  </ChartShell>
{:else}
  {@render body()}
{/if}

<script lang="ts" module>
  // Module-scope helper used by the legend chip. Picks the first
  // non-null colour seen for a given group across the view-model.
  // Falls back to a stable slate when the view-model never carries
  // a colour (renderers can override via row-level cells).
  import type { GroupedBarViewModel as GBViewModel } from "./multi-dim-view-models";
  export function legendColour<U>(
    group_id: string,
    vm: GBViewModel<U>,
  ): string {
    for (const r of vm.rows) {
      for (const c of r.cells) {
        if (c.group_id === group_id && c.colour) return c.colour;
      }
    }
    return "rgb(148 163 184)"; // slate-400
  }
</script>

<style>
  /* Layout-only. Visual tokens stay Tailwind-side when adopters need
     bespoke colours; defaults read cleanly inside ChartShell. */
  .hgb {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .hgb__legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.75rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 0.7rem;
    color: rgb(71 85 105); /* slate-600 */
  }
  .hgb__legend-item {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }
  .hgb__legend-chip {
    display: inline-block;
    width: 0.625rem;
    height: 0.625rem;
    border-radius: 2px;
  }
  .hgb__rows {
    display: flex;
    flex-direction: column;
    gap: var(--hgb-row-gap, 12px);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .hgb__row {
    display: grid;
    grid-template-columns: minmax(6rem, 9rem) 1fr;
    align-items: center;
    gap: 0.5rem;
    border-left: 2px solid transparent;
    padding-left: 0.25rem;
  }
  .hgb__row--pinned {
    border-left-color: rgb(217 119 6); /* amber-600 */
  }
  .hgb__row--missing {
    opacity: 0.6;
  }
  .hgb__row-label {
    font-size: 0.78rem;
    color: rgb(30 41 59); /* slate-800 */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hgb__row-pin {
    margin-left: 0.25rem;
    font-size: 0.625rem;
    color: rgb(146 64 14); /* amber-800 */
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .hgb__cells {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .hgb__cell {
    position: relative;
    display: flex;
    align-items: center;
    background: rgb(241 245 249); /* slate-100 — bar track */
    border-radius: 2px;
    overflow: hidden;
  }
  .hgb__cell-fill {
    display: block;
    height: 100%;
  }
  .hgb__cell-hatch {
    position: absolute;
    inset: 0;
    background-image: repeating-linear-gradient(
      45deg,
      rgb(226 232 240) 0,
      rgb(226 232 240) 2px,
      transparent 2px,
      transparent 4px
    );
  }
  .hgb__cell-label {
    position: absolute;
    right: 0.25rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.65rem;
    color: rgb(30 41 59);
    font-variant-numeric: tabular-nums;
    pointer-events: none;
  }
</style>

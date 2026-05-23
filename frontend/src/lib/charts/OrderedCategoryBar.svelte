<script lang="ts" generics="T">
  // OrderedCategoryBar — Phase 3.5 generic renderer.
  //
  // Consumes an `OrderedCategoryBarViewModel<T>` built by Phase 1.6's
  // `buildOrderedCategoryBarViewModel`. Rows are in their AXIS-ORDER
  // (poorest-to-richest, age bands, education levels) — the renderer
  // does NOT re-sort. The builder enforces `axis_order` or
  // `alphabetical` only (no value-sort policies).
  //
  // Doctrine:
  //   - Pure renderer. Zero data fetching. Zero charting library.
  //   - Each row renders as a horizontal bar; width is
  //     `value / max_abs_value` (clamped 0..1).
  //   - Missing rows render as a slate hatch placeholder so true-zero
  //     never reads as missing data (honesty rule).
  //   - Pinned rows get an amber left accent.
  //   - Value labels only on rows where `show_value_label === true`
  //     (set by the builder per `label_threshold`).
  //   - Wrapped in ChartShell when `chart_title` is supplied. Optional
  //     inline embedding via `wrap_in_shell={false}`.
  //   - No interactivity in v1.
  //   - CLAUDE.md §0: no aria/role.

  import type { Snippet } from "svelte";
  import type {
    SourceV2Row,
    ChartShellHonestyBanner,
  } from "./chart-shell/types";
  import type { OrderedCategoryBarViewModel } from "./bar-view-models";
  import ChartShell from "./ChartShell.svelte";

  interface Props {
    view_model: OrderedCategoryBarViewModel<T>;
    chart_title?: string;
    chart_subtitle?: string | null;
    honesty_banners?: readonly ChartShellHonestyBanner[];
    sources?: readonly SourceV2Row[];
    schema_version?: string | null;
    wrap_in_shell?: boolean;
    format_value?: (v: number) => string;
    bar_height?: number;
    row_gap?: number;
    /** Optional colour function: row → CSS colour. Default slate-500. */
    colour_for_row?: (row: { id: string; label: string; value: number | null }) => string;
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
    row_gap = 8,
    colour_for_row = () => "rgb(71 85 105)", // slate-500
    toolbar,
  }: Props = $props();

  function widthFrac(value: number | null, max_abs: number): number {
    if (value === null || value === undefined) return 0;
    if (max_abs <= 0) return 0;
    const f = Math.abs(value) / max_abs;
    if (!Number.isFinite(f)) return 0;
    return Math.min(1, Math.max(0, f));
  }
</script>

{#snippet body()}
  <ol
    class="ocb"
    data-component="ordered-category-bar"
    style:--ocb-row-gap="{row_gap}px"
  >
    {#each view_model.rows as r (r.sort_key.id)}
      <li
        class="ocb__row"
        class:ocb__row--pinned={r.is_pinned}
        class:ocb__row--missing={r.is_missing}
        data-row-id={r.sort_key.id}
        data-pinned={r.is_pinned}
        data-missing={r.is_missing}
      >
        <div class="ocb__label" title={r.sort_key.label}>
          {r.sort_key.label}
        </div>
        <div
          class="ocb__bar"
          style:height="{bar_height}px"
        >
          {#if r.is_missing}
            <span class="ocb__hatch" aria-hidden="true"></span>
            <span class="ocb__missing-label">no data</span>
          {:else}
            <span
              class="ocb__fill"
              style:background={colour_for_row({
                id: r.sort_key.id,
                label: r.sort_key.label,
                value: r.sort_key.value ?? null,
              })}
              style:width="{(widthFrac(r.sort_key.value ?? null, view_model.max_abs_value) * 100).toFixed(3)}%"
            ></span>
            {#if r.show_value_label}
              <span class="ocb__value">{format_value(r.sort_key.value as number)}</span>
            {/if}
          {/if}
        </div>
      </li>
    {/each}
  </ol>
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

<style>
  .ocb {
    display: flex;
    flex-direction: column;
    gap: var(--ocb-row-gap, 8px);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .ocb__row {
    display: grid;
    grid-template-columns: minmax(7rem, 10rem) 1fr;
    align-items: center;
    gap: 0.5rem;
    border-left: 2px solid transparent;
    padding-left: 0.25rem;
  }
  .ocb__row--pinned {
    border-left-color: rgb(217 119 6); /* amber-600 */
  }
  .ocb__row--missing {
    opacity: 0.7;
  }
  .ocb__label {
    font-size: 0.78rem;
    color: rgb(30 41 59); /* slate-800 */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ocb__bar {
    position: relative;
    background: rgb(241 245 249); /* slate-100 */
    border-radius: 2px;
    overflow: hidden;
  }
  .ocb__fill {
    display: block;
    height: 100%;
  }
  .ocb__hatch {
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
  .ocb__value {
    position: absolute;
    right: 0.25rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.65rem;
    color: rgb(30 41 59);
    font-variant-numeric: tabular-nums;
    pointer-events: none;
  }
  .ocb__missing-label {
    position: absolute;
    left: 0.25rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.625rem;
    color: rgb(100 116 139); /* slate-500 */
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>

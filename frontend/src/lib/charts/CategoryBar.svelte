<script module lang="ts">
  /** Closed-union discriminator over the three bar shapes. */
  export type CategoryBarMode = "ranked" | "stacked" | "diverging";

  // Re-exported from the retired HorizontalGroupedBar.svelte (F2a.4).
  // Picks the first non-null colour seen for a given group across the
  // grouped-bar view-model; falls back to slate-400 when no cell
  // carries a colour. Callers (legend chips, downstream renderers)
  // depend on this helper directly.
  import type { GroupedBarViewModel } from "./multi-dim-view-models";
  export function legendColour<U>(
    group_id: string,
    vm: GroupedBarViewModel<U>,
  ): string {
    for (const r of vm.rows) {
      for (const c of r.cells) {
        if (c.group_id === group_id && c.colour) return c.colour;
      }
    }
    return "rgb(148 163 184)"; // slate-400
  }
</script>

<script lang="ts" generics="T">
  // CategoryBar — unified Svelte renderer for the three bar shapes
  // yen-gov uses (per parent plan section 23.5):
  //
  //   mode="ranked"   — ordered category bar (axis-order or alphabetical
  //                     row sort; not value-sorted; what
  //                     `OrderedCategoryBar.svelte` did - lifted in F2a.1+F2a.2)
  //   mode="stacked"  — horizontal grouped/stacked bar
  //                     (what `HorizontalGroupedBar.svelte` did - lifted in F2a.3+F2a.4)
  //   mode="diverging" — composition bar with a baseline
  //                     (what the `composition-bar/` package did;
  //                     F2a.5 fills this branch)
  //
  // Doctrine ties:
  //   - Pure renderer. Zero data fetching. Zero charting library.
  //   - Each row/cell renders as a horizontal bar; width is
  //     `value / max_*_value` (clamped 0..1).
  //   - Missing rows/cells render as a slate hatch placeholder so
  //     true-zero never reads as missing data (honesty rule).
  //   - Pinned rows get an amber left accent.
  //   - Value labels only on rows/cells where `show_value_label === true`.
  //   - Wrapped in ChartShell when `chart_title` is supplied. Optional
  //     inline embedding via `wrap_in_shell={false}`.
  //   - No interactivity in v1.
  //   - CLAUDE.md section 0: no aria/role.

  import type { Snippet } from "svelte";
  import type {
    SourceV2Row,
    ChartShellHonestyBanner,
  } from "./chart-shell/types";
  import type { OrderedCategoryBarViewModel } from "./bar-view-models";
  import ChartShell from "./ChartShell.svelte";

  interface CommonProps {
    chart_title?: string;
    chart_subtitle?: string | null;
    honesty_banners?: readonly ChartShellHonestyBanner[];
    sources?: readonly SourceV2Row[];
    schema_version?: string | null;
    wrap_in_shell?: boolean;
    format_value?: (v: number) => string;
    toolbar?: Snippet;
  }

  interface RankedProps extends CommonProps {
    mode: "ranked";
    view_model: OrderedCategoryBarViewModel<T>;
    /** Bar height (px). */
    bar_height?: number;
    /** Vertical gap between rows (px). */
    row_gap?: number;
    /** Optional colour function: row -> CSS colour. Default slate-500. */
    colour_for_row?: (row: { id: string; label: string; value: number | null }) => string;
  }

  interface StackedProps extends CommonProps {
    mode: "stacked";
    view_model: GroupedBarViewModel<T>;
    /** Bar height (px) per group within a row. Default 12. */
    bar_height?: number;
    /** Gap (px) between groups within a row. Default 2. */
    bar_gap?: number;
    /** Gap (px) between rows. Default 12. */
    row_gap?: number;
    /** Render a colour-chip legend above the chart body. Default true. */
    show_legend?: boolean;
  }

  interface DivergingProps extends CommonProps {
    mode: "diverging";
    /** Filled in by F2a.5 with the `composition-bar`/diverging VM. */
    view_model: unknown;
  }

  type Props = RankedProps | StackedProps | DivergingProps;

  let props: Props = $props();

  // Common props (defaults applied by destructure in each branch).

  function widthFrac(value: number | null, max_abs: number): number {
    if (value === null || value === undefined) return 0;
    if (max_abs <= 0) return 0;
    const f = Math.abs(value) / max_abs;
    if (!Number.isFinite(f)) return 0;
    return Math.min(1, Math.max(0, f));
  }
</script>

{#snippet rankedBody(p: RankedProps)}
  {@const bar_height = p.bar_height ?? 12}
  {@const row_gap = p.row_gap ?? 8}
  {@const colour_for_row = p.colour_for_row ?? (() => "rgb(71 85 105)")}
  {@const format_value = p.format_value ?? ((v: number) => Number(v).toLocaleString())}
  <ol
    class="ocb"
    data-component="category-bar"
    data-mode="ranked"
    style:--ocb-row-gap="{row_gap}px"
  >
    {#each p.view_model.rows as r (r.sort_key.id)}
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
        <div class="ocb__bar" style:height="{bar_height}px">
          {#if r.is_missing}
            <span class="ocb__hatch"></span>
            <span class="ocb__missing-label">no data</span>
          {:else}
            <span
              class="ocb__fill"
              style:background={colour_for_row({
                id: r.sort_key.id,
                label: r.sort_key.label,
                value: r.sort_key.value ?? null,
              })}
              style:width="{(widthFrac(r.sort_key.value ?? null, p.view_model.max_abs_value) * 100).toFixed(3)}%"
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

{#snippet stackedBody(p: StackedProps)}
  {@const bar_height = p.bar_height ?? 12}
  {@const bar_gap = p.bar_gap ?? 2}
  {@const row_gap = p.row_gap ?? 12}
  {@const show_legend = p.show_legend ?? true}
  {@const format_value = p.format_value ?? ((v: number) => Number(v).toLocaleString())}
  <div
    class="hgb"
    data-component="category-bar"
    data-mode="stacked"
  >
    {#if show_legend && p.view_model.group_order.length > 0}
      <ul class="hgb__legend" data-slot="legend">
        {#each p.view_model.group_order as g (g.id)}
          <li class="hgb__legend-item" data-group-id={g.id}>
            <span
              class="hgb__legend-chip"
              style:background={legendColour(g.id, p.view_model)}
            ></span>
            <span class="hgb__legend-label">{g.label}</span>
          </li>
        {/each}
      </ul>
    {/if}
    <ol class="hgb__rows" data-slot="rows">
      {#each p.view_model.rows as r (r.id)}
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
                  <span class="hgb__cell-hatch"></span>
                {:else}
                  <span
                    class="hgb__cell-fill"
                    style:background={c.colour ?? "currentColor"}
                    style:width="{(widthFrac(c.value, p.view_model.max_cell_value) * 100).toFixed(3)}%"
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

{#snippet stubBody(mode: "diverging")}
  <div
    class="cb__stub"
    data-component="category-bar"
    data-mode={mode}
  >
    CategoryBar mode="{mode}" not yet implemented (F2a.5).
  </div>
{/snippet}

{#snippet body()}
  {#if props.mode === "ranked"}
    {@render rankedBody(props)}
  {:else if props.mode === "stacked"}
    {@render stackedBody(props)}
  {:else if props.mode === "diverging"}
    {@render stubBody("diverging")}
  {/if}
{/snippet}

{#if props.wrap_in_shell !== false && props.chart_title}
  <ChartShell
    title={props.chart_title}
    subtitle={props.chart_subtitle ?? null}
    honesty_banners={props.honesty_banners ?? []}
    sources={props.sources}
    schema_version={props.schema_version ?? null}
    toolbar={props.toolbar}
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
  .cb__stub {
    padding: 0.75rem;
    font-size: 0.75rem;
    color: rgb(100 116 139);
    font-style: italic;
    border: 1px dashed rgb(203 213 225);
    border-radius: 4px;
    background: rgb(248 250 252);
  }

  /* stacked-mode (lifted verbatim from HorizontalGroupedBar.svelte). */
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
    background: rgb(241 245 249); /* slate-100 - bar track */
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

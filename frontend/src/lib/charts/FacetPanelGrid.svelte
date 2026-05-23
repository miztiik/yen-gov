<script lang="ts" generics="T">
  // FacetPanelGrid — Phase 3.5 generic renderer.
  //
  // Consumes a `FacetPanelGridViewModel<T>` built by Phase 1.6's
  // `buildFacetPanelGridViewModel`. Renders one small panel per
  // facet — each panel is a tiny horizontal bar list.
  //
  // Doctrine:
  //   - Pure renderer. Zero data fetching.
  //   - Grid layout (responsive: `auto-fit` minmax).
  //   - Each panel has its own header (`panel_label`).
  //   - Inside the panel: rows in the order the builder emits.
  //   - Bar width = `value / scale` clamped 0..1. The `scale` is
  //     either the GLOBAL `global_max_abs_value` (shared_scale=true)
  //     OR the panel's own `max_abs_value`. Renderer honours the
  //     `shared_scale` flag from the view-model.
  //   - Missing rows: slate hatch placeholder + "no data" pill.
  //   - Pinned rows: amber left accent.
  //   - Value labels only on rows flagged `show_value_label === true`.
  //   - Optional ChartShell wrap via `wrap_in_shell` + `chart_title`.
  //   - CLAUDE.md §0: no aria/role.

  import type { Snippet } from "svelte";
  import type {
    SourceV2Row,
    ChartShellHonestyBanner,
  } from "./chart-shell/types";
  import type {
    FacetPanelGridViewModel,
    FacetPanelVM,
  } from "./multi-dim-view-models";
  import ChartShell from "./ChartShell.svelte";

  interface Props {
    view_model: FacetPanelGridViewModel<T>;
    chart_title?: string;
    chart_subtitle?: string | null;
    honesty_banners?: readonly ChartShellHonestyBanner[];
    sources?: readonly SourceV2Row[];
    schema_version?: string | null;
    wrap_in_shell?: boolean;
    format_value?: (v: number) => string;
    panel_min_width?: number;
    bar_height?: number;
    row_gap?: number;
    panel_gap?: number;
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
    panel_min_width = 220,
    bar_height = 10,
    row_gap = 4,
    panel_gap = 16,
    toolbar,
  }: Props = $props();

  function scaleFor(panel: FacetPanelVM<T>): number {
    return view_model.shared_scale ? view_model.global_max_abs_value : panel.max_abs_value;
  }

  function widthFrac(value: number | null, scale: number): number {
    if (value === null || value === undefined) return 0;
    if (scale <= 0) return 0;
    const f = Math.abs(value) / scale;
    if (!Number.isFinite(f)) return 0;
    return Math.min(1, Math.max(0, f));
  }
</script>

{#snippet body()}
  <div
    class="fpg"
    data-component="facet-panel-grid"
    data-shared-scale={view_model.shared_scale}
    style:--fpg-panel-min="{panel_min_width}px"
    style:--fpg-panel-gap="{panel_gap}px"
  >
    {#each view_model.panels as panel (panel.panel_id)}
      {@const scale = scaleFor(panel)}
      <section class="fpg__panel" data-panel-id={panel.panel_id}>
        <header class="fpg__panel-header">
          <span class="fpg__panel-title" title={panel.panel_label}>{panel.panel_label}</span>
          {#if panel.panel_value !== null}
            <span class="fpg__panel-value">{format_value(panel.panel_value)}</span>
          {/if}
        </header>
        <ol class="fpg__rows" style:--fpg-row-gap="{row_gap}px">
          {#each panel.rows as r (r.id)}
            <li
              class="fpg__row"
              class:fpg__row--pinned={r.is_pinned}
              class:fpg__row--missing={r.is_missing}
              data-row-id={r.id}
              data-pinned={r.is_pinned}
              data-missing={r.is_missing}
            >
              <div class="fpg__label" title={r.label}>{r.label}</div>
              <div class="fpg__bar" style:height="{bar_height}px">
                {#if r.is_missing}
                  <span class="fpg__hatch"></span>
                {:else}
                  <span
                    class="fpg__fill"
                    style:width="{(widthFrac(r.value, scale) * 100).toFixed(3)}%"
                    class:fpg__fill--max-in-panel={r.is_max_in_panel}
                  ></span>
                  {#if r.show_value_label && r.value !== null}
                    <span class="fpg__value">{format_value(r.value)}</span>
                  {/if}
                {/if}
              </div>
            </li>
          {/each}
        </ol>
      </section>
    {/each}
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

<style>
  .fpg {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(var(--fpg-panel-min, 220px), 1fr));
    gap: var(--fpg-panel-gap, 16px);
  }
  .fpg__panel {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    border: 1px solid rgb(226 232 240); /* slate-200 */
    border-radius: 4px;
    padding: 0.5rem 0.625rem;
    background: white;
  }
  .fpg__panel-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
    border-bottom: 1px solid rgb(241 245 249); /* slate-100 */
    padding-bottom: 0.25rem;
  }
  .fpg__panel-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: rgb(15 23 42); /* slate-900 */
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .fpg__panel-value {
    font-size: 0.75rem;
    color: rgb(71 85 105); /* slate-600 */
    font-variant-numeric: tabular-nums;
  }
  .fpg__rows {
    display: flex;
    flex-direction: column;
    gap: var(--fpg-row-gap, 4px);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .fpg__row {
    display: grid;
    grid-template-columns: minmax(5rem, 7rem) 1fr;
    align-items: center;
    gap: 0.4rem;
    border-left: 2px solid transparent;
    padding-left: 0.25rem;
  }
  .fpg__row--pinned {
    border-left-color: rgb(217 119 6); /* amber-600 */
  }
  .fpg__row--missing {
    opacity: 0.7;
  }
  .fpg__label {
    font-size: 0.7rem;
    color: rgb(30 41 59); /* slate-800 */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .fpg__bar {
    position: relative;
    background: rgb(241 245 249);
    border-radius: 2px;
    overflow: hidden;
  }
  .fpg__hatch {
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
  .fpg__fill {
    display: block;
    height: 100%;
    background: rgb(59 130 246); /* blue-500 */
  }
  .fpg__fill--max-in-panel {
    background: rgb(37 99 235); /* blue-600 */
  }
  .fpg__value {
    position: absolute;
    right: 0.25rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.6rem;
    color: rgb(30 41 59);
    font-variant-numeric: tabular-nums;
    pointer-events: none;
  }
</style>

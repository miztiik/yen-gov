<script module lang="ts">
  /** Closed-union discriminator over the three bar shapes. */
  export type CategoryBarMode = "ranked" | "stacked" | "diverging";
</script>

<script lang="ts" generics="T">
  // CategoryBar — unified Svelte renderer for the three bar shapes
  // yen-gov uses (per parent plan section 23.5):
  //
  //   mode="ranked"   — ordered category bar (axis-order or alphabetical
  //                     row sort; not value-sorted; what
  //                     `OrderedCategoryBar.svelte` did)
  //   mode="stacked"  — horizontal grouped/stacked bar
  //                     (what `HorizontalGroupedBar.svelte` did)
  //   mode="diverging" — composition bar with a baseline
  //                     (what the `composition-bar/` package did)
  //
  // F2a.1+F2a.2 (this PR): ships the `mode="ranked"` body verbatim
  // from the retired `OrderedCategoryBar.svelte`. Stub branches for
  // "stacked" and "diverging" raise at runtime so the type-checker
  // can keep the discriminated-union narrowing honest; subsequent
  // F2a sub-rows fill them in.
  //
  // Doctrine ties (unchanged from OrderedCategoryBar):
  //   - Pure renderer. Zero data fetching. Zero charting library.
  //   - Each row renders as a horizontal bar; width is
  //     `value / max_abs_value` (clamped 0..1).
  //   - Missing rows render as a slate hatch placeholder so true-zero
  //     never reads as missing data (honesty rule).
  //   - Pinned rows get an amber left accent.
  //   - Value labels only on rows where `show_value_label === true`.
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
    /** Filled in by F2a.3 with the `HorizontalGroupedBar`/stacked VM. */
    view_model: unknown;
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

{#snippet stubBody(mode: "stacked" | "diverging")}
  <div
    class="cb__stub"
    data-component="category-bar"
    data-mode={mode}
  >
    CategoryBar mode="{mode}" not yet implemented (F2a.{mode === "stacked" ? "3" : "5"}).
  </div>
{/snippet}

{#snippet body()}
  {#if props.mode === "ranked"}
    {@render rankedBody(props)}
  {:else if props.mode === "stacked"}
    {@render stubBody("stacked")}
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
</style>

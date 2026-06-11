<script lang="ts" generics="T">
  // DumbbellRange — Phase 3.5 generic renderer.
  //
  // Consumes a `DumbbellRangeViewModel<T>` built by Phase 1.6's
  // `buildDumbbellRangeViewModel`. Each row shows the journey from
  // `earliest` to `latest` as two dots joined by a line.
  //
  // Doctrine:
  //   - Pure renderer. Zero data fetching.
  //   - Two dots per row at fractional positions of
  //     `value / max_abs_value` (clamped 0..1). Connector line links
  //     them. Direction colour: up=green, down=red, flat=slate,
  //     missing=hatch.
  //   - Missing endpoint = open-ring marker; if both missing the
  //     row is "no data" with a slate hatch strip.
  //   - Pinned rows get an amber left accent.
  //   - Endpoint labels only when `show_endpoint_label === true`.
  //   - Delta label only when `show_delta_label === true`.
  //   - Wrapped in ChartShell when `chart_title` is supplied.
  //   - CLAUDE.md §0: no aria/role.

  import type { Snippet } from "svelte";
  import type {
    PublisherPill,
    ChartShellHonestyBanner,
  } from "./chart-shell/types";
  import type { DumbbellRangeViewModel } from "./time-view-models";
  import ChartShell from "./ChartShell.svelte";

  interface Props {
    view_model: DumbbellRangeViewModel<T>;
    chart_title?: string;
    chart_subtitle?: string | null;
    honesty_banners?: readonly ChartShellHonestyBanner[];
    pills?: readonly PublisherPill[];
    wrap_in_shell?: boolean;
    format_value?: (v: number) => string;
    format_delta?: (v: number) => string;
    row_gap?: number;
    track_height?: number;
    toolbar?: Snippet;
  }

  let {
    view_model,
    chart_title,
    chart_subtitle = null,
    honesty_banners = [],
    pills,
    wrap_in_shell = true,
    format_value = (v: number) => Number(v).toLocaleString(),
    format_delta = (v: number) => (v > 0 ? `+${v.toLocaleString()}` : v.toLocaleString()),
    row_gap = 12,
    track_height = 20,
    toolbar,
  }: Props = $props();

  function frac(value: number | null, max_abs: number): number {
    if (value === null || value === undefined) return 0;
    if (max_abs <= 0) return 0;
    const f = Math.abs(value) / max_abs;
    if (!Number.isFinite(f)) return 0;
    return Math.min(1, Math.max(0, f));
  }

  function directionColour(direction: "up" | "down" | "flat" | "missing"): string {
    if (direction === "up") return "rgb(22 163 74)";    // green-600
    if (direction === "down") return "rgb(220 38 38)";  // red-600
    if (direction === "flat") return "rgb(100 116 139)"; // slate-500
    return "rgb(148 163 184)"; // slate-400
  }
</script>

{#snippet body()}
  <ol
    class="dbr"
    data-component="dumbbell-range"
    style:--dbr-row-gap="{row_gap}px"
  >
    {#each view_model.rows as r (r.id)}
      {@const e_pct = (frac(r.earliest.value, view_model.max_abs_value) * 100).toFixed(3)}
      {@const l_pct = (frac(r.latest.value, view_model.max_abs_value) * 100).toFixed(3)}
      {@const col = directionColour(r.direction)}
      {@const both_present = !r.earliest.is_missing && !r.latest.is_missing}
      {@const lo_pct = both_present ? Math.min(parseFloat(e_pct), parseFloat(l_pct)).toFixed(3) : e_pct}
      {@const hi_pct = both_present ? Math.max(parseFloat(e_pct), parseFloat(l_pct)).toFixed(3) : l_pct}
      <li
        class="dbr__row"
        class:dbr__row--pinned={r.is_pinned}
        class:dbr__row--missing={r.is_missing}
        data-row-id={r.id}
        data-direction={r.direction}
        data-pinned={r.is_pinned}
        data-missing={r.is_missing}
      >
        <div class="dbr__label" title={r.label}>
          {r.label}
        </div>
        <div class="dbr__track" style:height="{track_height}px">
          {#if r.is_missing}
            <span class="dbr__hatch"></span>
            <span class="dbr__missing-label">no data</span>
          {:else}
            {#if both_present}
              <span
                class="dbr__connector"
                style:left="{lo_pct}%"
                style:width="calc({hi_pct}% - {lo_pct}%)"
                style:background={col}
              ></span>
            {/if}
            {#if !r.earliest.is_missing}
              <span
                class="dbr__dot dbr__dot--earliest"
                style:left="{e_pct}%"
                style:border-color={col}
              ></span>
              {#if r.earliest.show_endpoint_label}
                <span
                  class="dbr__endpoint-label dbr__endpoint-label--earliest"
                  style:left="{e_pct}%"
                >{format_value(r.earliest.value as number)}</span>
              {/if}
            {:else}
              <span class="dbr__dot dbr__dot--open" style:left="0%"></span>
            {/if}
            {#if !r.latest.is_missing}
              <span
                class="dbr__dot dbr__dot--latest"
                style:left="{l_pct}%"
                style:background={col}
                style:border-color={col}
              ></span>
              {#if r.latest.show_endpoint_label}
                <span
                  class="dbr__endpoint-label dbr__endpoint-label--latest"
                  style:left="{l_pct}%"
                >{format_value(r.latest.value as number)}</span>
              {/if}
            {:else}
              <span class="dbr__dot dbr__dot--open" style:left="100%"></span>
            {/if}
            {#if r.show_delta_label && r.delta !== null}
              <span
                class="dbr__delta"
                style:left="{((parseFloat(lo_pct) + parseFloat(hi_pct)) / 2).toFixed(3)}%"
                style:color={col}
              >{format_delta(r.delta)}</span>
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
    {pills}
    {toolbar}
  >
    {@render body()}
  </ChartShell>
{:else}
  {@render body()}
{/if}

<style>
  .dbr {
    display: flex;
    flex-direction: column;
    gap: var(--dbr-row-gap, 12px);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .dbr__row {
    display: grid;
    grid-template-columns: minmax(7rem, 10rem) 1fr;
    align-items: center;
    gap: 0.5rem;
    border-left: 2px solid transparent;
    padding-left: 0.25rem;
  }
  .dbr__row--pinned {
    border-left-color: rgb(217 119 6); /* amber-600 */
  }
  .dbr__row--missing {
    opacity: 0.7;
  }
  .dbr__label {
    font-size: 0.78rem;
    color: rgb(30 41 59); /* slate-800 */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .dbr__track {
    position: relative;
    background: rgb(248 250 252); /* slate-50 */
    border-radius: 2px;
  }
  .dbr__hatch {
    position: absolute;
    inset: 0;
    background-image: repeating-linear-gradient(
      45deg,
      rgb(226 232 240) 0,
      rgb(226 232 240) 2px,
      transparent 2px,
      transparent 4px
    );
    border-radius: 2px;
  }
  .dbr__connector {
    position: absolute;
    top: 50%;
    height: 2px;
    transform: translateY(-50%);
    border-radius: 1px;
  }
  .dbr__dot {
    position: absolute;
    top: 50%;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid rgb(100 116 139);
    background: white;
    transform: translate(-50%, -50%);
  }
  .dbr__dot--open {
    background: white;
    border-style: dashed;
    border-color: rgb(148 163 184); /* slate-400 */
  }
  .dbr__endpoint-label {
    position: absolute;
    bottom: calc(100% + 2px);
    transform: translateX(-50%);
    font-size: 0.625rem;
    color: rgb(30 41 59);
    font-variant-numeric: tabular-nums;
    pointer-events: none;
    white-space: nowrap;
  }
  .dbr__endpoint-label--earliest {
    color: rgb(71 85 105);
  }
  .dbr__delta {
    position: absolute;
    top: calc(100% + 2px);
    transform: translateX(-50%);
    font-size: 0.625rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    pointer-events: none;
    white-space: nowrap;
  }
  .dbr__missing-label {
    position: absolute;
    left: 0.25rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.625rem;
    color: rgb(100 116 139);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>

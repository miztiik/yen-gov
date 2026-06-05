<script lang="ts">
  // C3 MapTooltip (parent plan section 14.3) - region label + parent
  // (state) + formatted value + swatch chip, absolute-positioned by
  // the caller via `x` + `y` props. No positioning logic inside;
  // the renderer owns where to mount the tooltip.
  //
  // Doctrine ties:
  //   - Pure presentation leaf. No fetches, no calculations.
  //   - Caller controls position; this component never reads
  //     `pointer.x` / `pointer.y` or attaches its own listeners.
  //   - CLAUDE.md section 0: no aria/role. Visible affordances only
  //     (the tooltip surface is itself a visible affordance).

  interface Props {
    /** Horizontal pixel offset from the renderer's origin. */
    x: number;
    /** Vertical pixel offset from the renderer's origin. */
    y: number;
    /** Citizen-readable region label (e.g. "Karnataka"). */
    region_label: string;
    /** Optional parent label (e.g. "South India" or the state name
     *  for a district). Hidden when null/undefined. */
    parent_label?: string | null;
    /** Citizen-readable formatted value (e.g. "24.1 GW"). When the
     *  underlying value is null, pass a placeholder like "no data";
     *  the tooltip ALWAYS renders the value row to anchor the
     *  citizen's reading. */
    formatted_value: string;
    /** Background hex for the swatch chip (typically the
     *  ColorScale's swatch for this region's value). */
    swatch_color: string;
    /** Optional small icon glyph (e.g. lucide info or chart-bar).
     *  Hidden when null/undefined. */
    icon_glyph?: string | null;
  }

  const {
    x,
    y,
    region_label,
    parent_label = null,
    formatted_value,
    swatch_color,
    icon_glyph = null,
  }: Props = $props();
</script>

<div
  class="map-tooltip"
  data-component="map-tooltip"
  style="left: {x}px; top: {y}px;"
>
  <div class="map-tooltip__header">
    <span class="map-tooltip__swatch" style="background: {swatch_color};"></span>
    <span class="map-tooltip__region">{region_label}</span>
    {#if icon_glyph}
      <span class="map-tooltip__icon" data-glyph={icon_glyph}></span>
    {/if}
  </div>
  {#if parent_label}
    <div class="map-tooltip__parent">{parent_label}</div>
  {/if}
  <div class="map-tooltip__value" data-slot="value">{formatted_value}</div>
</div>

<style>
  .map-tooltip {
    position: absolute;
    pointer-events: none;
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    box-shadow: var(--e2);
    padding: 8px 10px;
    min-width: 140px;
    max-width: 240px;
    font-family: var(--font-sans);
    font-size: 12px;
    z-index: 30;
  }
  .map-tooltip__header {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
  }
  .map-tooltip__swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    border: 1px solid var(--line);
    flex-shrink: 0;
  }
  .map-tooltip__region {
    color: var(--ink);
  }
  .map-tooltip__icon {
    margin-left: auto;
    color: var(--ink-muted);
    font-size: 10px;
  }
  .map-tooltip__parent {
    color: var(--ink-muted);
    font-size: 11px;
    margin-top: 2px;
  }
  .map-tooltip__value {
    color: var(--ink);
    font-size: 14px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    margin-top: 4px;
  }
</style>

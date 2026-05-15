<script lang="ts">
  /**
   * VintageTooltipLine — the trailing line(s) every chart's tooltip
   * appends so vintage and (when applicable) the nearest series-break
   * note are surfaced consistently. (Phase 2 of the viz-layer plan;
   * delegates to indicator-render.vintageTooltipLine.)
   *
   * Why "every tooltip": the audit found that methodology_vintage was
   * silently dropped in chart tooltips. A 2024 NFHS-6 figure has the
   * same `time` as a 2024 NFHS-5 backcast but a different vintage; if
   * the citizen can't see vintage, they can't tell the two apart.
   *
   * Usage:
   *   <ChartTooltip ...>
   *     <VintageTooltipLine meta={artifact.indicator} atTime={hoveredTime} />
   *   </ChartTooltip>
   */

  import type { IndicatorMeta } from "../indicators";
  import { vintageTooltipLine } from "../indicator-render";

  interface Props {
    meta: Pick<IndicatorMeta, "methodology_vintage" | "series_breaks">;
    /** The point currently under the cursor — used to look up an exact
     *  series-break match. Optional; when absent, only the vintage
     *  line (if any) is shown. */
    atTime?: string;
  }

  const { meta, atTime }: Props = $props();
  const lines = $derived(vintageTooltipLine(meta, atTime));
</script>

{#if lines.vintageLine || lines.breakLine}
  <div class="vintage-tooltip mt-1 border-t border-slate-200 pt-1 text-[11px] text-slate-500">
    {#if lines.vintageLine}
      <div>{lines.vintageLine}</div>
    {/if}
    {#if lines.breakLine}
      <div class="text-amber-700">{lines.breakLine}</div>
    {/if}
  </div>
{/if}

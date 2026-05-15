<script lang="ts">
  /**
   * RebaseBanner — the banner shown above any chart whose indicator is
   * an INDEX series (`value_kind: "index"`). (Phase 2 of the viz-layer
   * plan; consumes indicator-render.indexAxisHint.)
   *
   * Two messages, composed from the unit string:
   *
   *   1. The base statement: "Index, = 100 in {base}". Without it the
   *      citizen reads e.g. "120" as "120 rupees" or "120%". With it,
   *      they read it as "20% above the base year level."
   *
   *   2. (When `series_breaks` carries a `kind: "rebase"` event) a
   *      second sentence noting that an older base existed and was
   *      ratio-spliced. This is the audit's WPI / CPI-IW case where
   *      the official series has been rebased multiple times.
   *
   * The banner is a single line so it fits above small-multiples
   * panels too; it is not a modal or a popover.
   */

  import type { IndicatorMeta } from "../indicators";
  import { indexAxisHint } from "../indicator-render";

  interface Props {
    meta: Pick<IndicatorMeta, "value_kind" | "unit" | "series_breaks">;
  }

  const { meta }: Props = $props();

  const hint = $derived(indexAxisHint(meta));
  const rebases = $derived(
    (meta.series_breaks ?? []).filter(b => b.kind === "rebase"),
  );
</script>

{#if hint.ownAxis}
  <div
    class="rebase-banner mb-2 rounded border border-amber-200 bg-amber-50
           px-3 py-1.5 text-[12px] text-amber-900"
  >
    <span class="font-medium">Index series.</span>
    {#if hint.baseCaption}
      <span>{hint.baseCaption}.</span>
    {/if}
    {#if rebases.length > 0}
      <span class="text-amber-800">
        {rebases.length === 1
          ? `Rebased once at ${rebases[0].at_time}.`
          : `Rebased ${rebases.length} times — most recent at ${rebases[rebases.length - 1].at_time}.`}
        Year-on-year change is comparable within a base period only.
      </span>
    {:else}
      <span class="text-amber-800">
        Year-on-year change is the meaningful read; level numbers are not rupees.
      </span>
    {/if}
  </div>
{/if}

<script lang="ts">
  // Legend-strip value chips for unmapped regions (Lakshadweep, A&N).
  //
  // Why a chip and not a polygon inset: the choropleth's job is letting a
  // citizen read a value bucket. Lakshadweep / A&N polygons are sub-pixel
  // even at 10× inset scale, so the fill colour is unreadable — the inset
  // surfaces geography but fails the choropleth's actual job. The chip
  // lives on the legend strip, uses the same `fillForValue` swatch the
  // polygon would have used, and carries the population anchor a policy
  // reader needs to read per-capita rankings honestly. See
  // docs/concepts/unmapped-regions.md and ADR-0029.
  //
  // Presentation-only. All data-shaping lives in ./unmapped-region-chips.ts
  // (pure, unit-tested) so this file holds layout only.

  import { chipModelFor, type UnmappedRegion } from "./unmapped-region-chips";

  interface Props {
    /** From config/unmapped_regions.json. */
    regions: UnmappedRegion[];
    /** ECI-keyed indicator values at the selected time (already aggregated by parent). */
    values: Map<string, number>;
    /** ECI-keyed absolute population counts. May be empty if the loader failed; chips render the "—" pop variant. */
    populations: Map<string, number>;
    /** Closure binding the indicator's colour scale: value → hex. The parent already has the min/max/direction/scale in scope. */
    fillFor: (value: number) => string;
    /** Closure binding the indicator's unit + formatting (e.g. `formatValue(v, meta)` curried). */
    formatValueFn: (value: number) => string;
    /** Tap handler — same identity as the map-region selection callback. */
    onSelect: (entity_id: string) => void;
  }

  let { regions, values, populations, fillFor, formatValueFn, onSelect }: Props = $props();

  const chips = $derived(
    regions.map((r) => chipModelFor(r, values, populations, fillFor, formatValueFn)),
  );
</script>

{#if chips.length > 0}
  <!-- Horizontal scroll keeps the legend strip one row tall on mobile.
       Negative side-margins let the scroll cross the parent's padding
       cleanly; the inner padding restores breathing room around the
       first/last chip. Fade-mask hints "more chips" exist to the right. -->
  <div
    class="flex gap-1.5 overflow-x-auto snap-x snap-mandatory pb-1 -mx-3 px-3"
    style:mask-image="linear-gradient(to right, black 85%, transparent)"
    style:-webkit-mask-image="linear-gradient(to right, black 85%, transparent)"
    data-testid="unmapped-region-chip-strip"
  >
    {#each chips as chip (chip.entity_id)}
      <button
        type="button"
        class="snap-start inline-flex items-center gap-2 px-2 py-1.5 rounded-md border border-slate-200 bg-white min-w-[110px] max-w-[140px] text-left active:bg-slate-50 active:scale-[0.98] transition-transform duration-75"
        data-testid="unmapped-region-chip"
        data-entity-id={chip.entity_id}
        onclick={() => onSelect(chip.entity_id)}
      >
        {#if chip.swatch}
          <span
            class="h-3.5 w-3.5 rounded-sm shrink-0"
            style:background-color={chip.swatch}
            aria-hidden="true"
          ></span>
        {:else}
          <!-- Null-data variant: dashed hollow swatch, visually distinct
               from any colour bucket. -->
          <span
            class="h-3.5 w-3.5 rounded-sm shrink-0 bg-slate-100 border border-dashed border-slate-300"
            aria-hidden="true"
          ></span>
        {/if}
        <span class="flex-1 min-w-0 leading-tight">
          <span class="flex items-baseline justify-between gap-1">
            <span class="text-[11px] font-medium text-slate-900 truncate">
              {chip.display_name}
            </span>
            <span
              class="text-[11px] font-semibold tabular-nums shrink-0"
              class:text-slate-900={chip.value !== null}
              class:text-slate-400={chip.value === null}
            >
              {chip.value_label}
            </span>
          </span>
          <span class="block text-[10px] text-slate-500 tabular-nums">
            {chip.population_label}
          </span>
        </span>
      </button>
    {/each}
  </div>
{/if}

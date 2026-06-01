<script lang="ts">
  // PR-B6 — snapping election time-slider.
  //
  // A discrete slider that scrubs the constituency map/cartogram across a
  // state's consecutive SAME-GRAIN elections. Jony constraints:
  //   - SNAPS to real election dates only (the native range input with
  //     `step=1` over stop indices makes every rest position a real cohort).
  //   - NO autoplay, NO interpolation — there is no play button and the
  //     thumb cannot stop between two elections.
  //   - Reads left=oldest, right=most-recent (stops are sorted ascending).
  //
  // The component is a thin shell: it owns no event data, it just maps the
  // index the citizen drags to an `event_id` and calls `onSelect`. The host
  // route changes the URL (`/s/<state>/elections/<event>`); the route's
  // reactive chain reloads winners + recolours the map. Single source of
  // truth = the route param, never local component state.

  import type { ElectionSliderStop } from "./election-time-slider";
  import { stopIndexForEvent } from "./election-time-slider";

  interface Props {
    /** Chronologically-ascending stops from `buildSliderStops`. */
    stops: ElectionSliderStop[];
    /** Currently-selected cohort id (the route's `:event`). */
    selectedEventId: string | null;
    /** Called with the newly-snapped cohort id when the citizen scrubs. */
    onSelect: (eventId: string) => void;
  }

  let { stops, selectedEventId, onSelect }: Props = $props();

  const index = $derived(stopIndexForEvent(stops, selectedEventId));
  const active = $derived(stops[index] ?? null);
  const maxIndex = $derived(Math.max(0, stops.length - 1));

  function handleInput(event: Event) {
    const next = Number((event.currentTarget as HTMLInputElement).value);
    const stop = stops[next];
    // Guard: only emit when the index lands on a real stop AND actually
    // changes the cohort (the native input already snaps to integers).
    if (stop && stop.event_id !== selectedEventId) onSelect(stop.event_id);
  }
</script>

{#if stops.length >= 2}
  <div
    class="rounded border border-slate-200 bg-white p-3 space-y-2"
    data-testid="election-time-slider"
  >
    <div class="flex items-baseline justify-between gap-2">
      <span class="text-xs font-medium text-slate-500">Election year</span>
      {#if active}
        <span
          class="text-xs font-semibold tabular-nums text-slate-800"
          data-testid="election-time-slider-active"
        >
          {active.display}
        </span>
      {/if}
    </div>

    <input
      type="range"
      min="0"
      max={maxIndex}
      step="1"
      value={index}
      class="w-full accent-sky-600"
      aria-label="Scrub election year"
      aria-valuetext={active ? active.display : undefined}
      data-testid="election-time-slider-input"
      list="election-time-slider-ticks"
      oninput={handleInput}
    />

    <!-- Snapping ticks: one mark per real election, no in-between stops. -->
    <datalist id="election-time-slider-ticks">
      {#each stops as stop, i (stop.event_id)}
        <option value={i} label={stop.label}></option>
      {/each}
    </datalist>

    <div class="flex justify-between text-[10px] tabular-nums text-slate-400">
      {#each stops as stop (stop.event_id)}
        <span
          class:font-semibold={stop.event_id === active?.event_id}
          class:text-slate-700={stop.event_id === active?.event_id}
          data-testid="election-time-slider-tick"
          data-event-id={stop.event_id}
        >
          {stop.label}
        </span>
      {/each}
    </div>
  </div>
{/if}

<script lang="ts">
  // YearPillStrip - PR-W4a discrete tap-to-jump pill row.
  //
  // Election experience overhaul plan (TODO/20260609-...) Jony verdict:
  // citizens navigating cross-election history want DISCRETE pills (one
  // per event year) - never a continuous slider. Continuous time
  // sliders live in `frontend/src/lib/charts/` for socio-econ series;
  // this is the elections-domain control.
  //
  // The component is a template-only wrapper around
  // `year-pill-strip-model.ts` - all sort + active-flag logic lives in
  // the pure model so vitest (node-env, no jsdom) can exercise it.

  import { deriveStrip } from "./year-pill-strip-model";
  import type { ElectionEventRow } from "../election-events";

  interface Props {
    events: readonly ElectionEventRow[];
    /** event_id of the pill that renders as filled. */
    active: string;
    /** Fired with the clicked pill's event_id. Consumer navigates. */
    onSelect: (event_id: string) => void;
  }

  let { events, active, onSelect }: Props = $props();

  const strip = $derived(deriveStrip(events, active));
</script>

<nav
  class="flex flex-wrap gap-2"
  data-testid="year-pill-strip"
  aria-label="Election year navigation"
>
  {#each strip as p (p.event_id)}
    <button
      type="button"
      class:bg-slate-900={p.is_active}
      class:text-white={p.is_active}
      class:bg-slate-100={!p.is_active}
      class:text-slate-700={!p.is_active}
      class:hover:bg-slate-200={!p.is_active}
      class="px-3 py-1 rounded-full text-xs font-medium transition tabular-nums"
      data-testid={`year-pill-${p.event_id}`}
      aria-current={p.is_active ? "true" : undefined}
      onclick={() => onSelect(p.event_id)}
    >
      {p.year}
    </button>
  {/each}
</nav>

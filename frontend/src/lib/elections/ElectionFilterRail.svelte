<script lang="ts">
  // ElectionFilterRail — the PR-B8 filter strip for a state's assembly map.
  //
  // Three controls, all of which only RECOLOUR / DIM the existing map (no
  // bespoke per-filter chart):
  //   F1  party multi-select chips      → dim every AC not won by a chosen party
  //   F2  margin band segmented control → dim every AC outside the band
  //   F3  "Colour by" dropdown          → recolour the SAME choropleth
  //
  // Turnout / Age colour options are only offered when the loaded winners
  // actually carry that field for enough seats (Max's coverage gate), so the
  // citizen never picks a mode that paints the map blank.
  //
  // A single reset affordance (the active-filter count chip) clears every
  // non-default choice. State lives in the URL; this component is controlled
  // — it emits the next ElectionFilters via `onChange` and renders nothing
  // itself.
  //
  // CLAUDE.md §0: visible affordances only; no aria/role scaffolding.

  import {
    COLOUR_MODES,
    DEFAULT_ELECTION_FILTERS,
    MARGIN_BANDS,
    activeFilterCount,
    type ColourMode,
    type ElectionFilters,
    type MarginBand,
  } from "../election-filters";

  interface PartyOption {
    code: string;
    short: string;
    color: string;
  }

  interface Props {
    filters: ElectionFilters;
    /** Distinct winning parties in the state, palette-consistent with the map. */
    parties: PartyOption[];
    /** Which continuous modes have enough coverage to offer. */
    coverage: { turnout: boolean; age: boolean };
    onChange: (next: ElectionFilters) => void;
  }
  let { filters, parties, coverage, onChange }: Props = $props();

  const MARGIN_LABELS: Record<MarginBand, string> = {
    all: "All",
    lt2: "Close (<2 pts)",
    gt20: "Landslide (>20 pts)",
  };

  const MODE_LABELS: Record<ColourMode, string> = {
    winner: "Winner",
    margin: "Margin",
    turnout: "Turnout",
    age: "Age of winner",
  };

  const available_modes = $derived(
    COLOUR_MODES.filter(
      (m) =>
        m === "winner" ||
        m === "margin" ||
        (m === "turnout" && coverage.turnout) ||
        (m === "age" && coverage.age),
    ),
  );

  const active_count = $derived(activeFilterCount(filters));

  function toggleParty(code: string): void {
    const set = new Set(filters.parties);
    if (set.has(code)) set.delete(code);
    else set.add(code);
    onChange({ ...filters, parties: [...set] });
  }

  function setMargin(band: MarginBand): void {
    onChange({ ...filters, margin: band });
  }

  function setMode(mode: ColourMode): void {
    onChange({ ...filters, mode });
  }

  function reset(): void {
    onChange({ ...DEFAULT_ELECTION_FILTERS });
  }
</script>

<div
  class="space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3"
  data-testid="election-filter-rail"
>
  <div class="flex items-center justify-between gap-2">
    <span class="text-xs font-medium uppercase tracking-wide text-slate-500"
      >Filters</span
    >
    {#if active_count > 0}
      <button
        type="button"
        class="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-700 hover:bg-slate-300"
        data-testid="election-filter-reset"
        onclick={reset}
      >
        Reset ({active_count})
      </button>
    {/if}
  </div>

  <!-- F3 Colour by -->
  <div class="flex items-center gap-2">
    <label class="text-xs text-slate-500" for="election-colour-mode">Colour by</label>
    <select
      id="election-colour-mode"
      class="rounded-md border border-slate-200 bg-white px-2 py-1 text-sm text-slate-800"
      data-testid="election-colour-mode"
      value={filters.mode}
      onchange={(e) => setMode(e.currentTarget.value as ColourMode)}
    >
      {#each available_modes as mode (mode)}
        <option value={mode}>{MODE_LABELS[mode]}</option>
      {/each}
    </select>
  </div>

  <!-- F2 Margin band -->
  <div
    class="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-sm"
    data-testid="election-margin-band"
  >
    {#each MARGIN_BANDS as band (band)}
      <button
        type="button"
        class="rounded-md px-2.5 py-1 transition-colors {filters.margin === band
          ? 'bg-slate-800 font-medium text-white'
          : 'text-slate-500 hover:text-slate-700'}"
        data-band={band}
        aria-pressed={filters.margin === band}
        onclick={() => setMargin(band)}
      >
        {MARGIN_LABELS[band]}
      </button>
    {/each}
  </div>

  <!-- F1 Party multi-select -->
  {#if parties.length > 0}
    <div class="flex flex-wrap gap-1.5" data-testid="election-party-chips">
      {#each parties as p (p.code)}
        {@const on = filters.parties.includes(p.code)}
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs transition-colors {on
            ? 'border-slate-800 bg-slate-800 text-white'
            : 'border-slate-200 bg-white text-slate-600 hover:border-slate-400'}"
          data-party={p.code}
          aria-pressed={on}
          onclick={() => toggleParty(p.code)}
        >
          <span
            class="inline-block h-2 w-2 rounded-full"
            style:background-color={p.color}
          ></span>
          {p.short}
        </button>
      {/each}
    </div>
  {/if}
</div>

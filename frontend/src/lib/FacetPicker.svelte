<script lang="ts">
  // FacetPicker — controlled pill-row primitive for picking one segment
  // of a faceted indicator.
  //
  // Design verdict: Jony PR-D (commit body) — pill-row pattern wins
  // over segmented-control / dropdown / tabs / radio-list / chip-row /
  // accordion for 3-to-8 facets on mid-tier-Android-thumb-tap.
  // Segmented-controls collapse readability past 6 facets at 320px;
  // dropdowns hide options behind a tap (violates Brichter's "inevitable
  // visibility"); tabs imply heavy content swap; radio-lists steal
  // vertical real-estate; accordions hide the active selection. Pill
  // wins because every option is visible (no discovery tax), each pill
  // is independently thumb-tappable, and wrapping degrades cleanly via
  // `flex flex-wrap`.
  //
  // Selected emphasis uses two signals (background inversion + weight
  // bump) — never colour-only, so the picker remains legible on
  // grayscale print and low-contrast monitors. (CLAUDE.md §0 makes
  // a11y/ARIA a Non-Goal; the two-signal rule is just good Jony
  // hygiene.)
  //
  // Stateless controlled component: the parent owns `selected` and
  // re-derives downstream state (filtered rows, big number, rank, the
  // sparkline) when `onSelect` fires. Keeping state in the parent is
  // the only honest shape here — the picker's siblings need to react
  // to the choice.
  //
  // Doctrine: docs/concepts/schema-is-the-design-system.md — this is
  // composition over existing chrome, not a new renderer family.

  interface Props {
    /** Facet identifiers to render, in display order. Passed verbatim
     *  from `IndicatorRow.facet` values, which the canonical adapter
     *  already produces in citizen-readable form (e.g. RPO ships
     *  "solar" / "non-solar" / "total"). */
    facets: string[];
    /** Currently-selected facet. Must be a member of `facets`. */
    selected: string;
    /** Fired when the user taps a non-selected pill. Tapping the
     *  already-selected pill is a no-op (no callback). */
    onSelect: (facet: string) => void;
  }

  let { facets, selected, onSelect }: Props = $props();
</script>

<div class="flex flex-wrap gap-2" data-testid="facet-picker">
  {#each facets as facet (facet)}
    {@const is_selected = facet === selected}
    <button
      type="button"
      class={is_selected
        ? "py-2.5 px-3 rounded-md text-sm bg-slate-900 text-white font-semibold"
        : "py-2.5 px-3 rounded-md text-sm bg-slate-100 text-slate-700 font-medium hover:bg-slate-200"}
      data-selected={is_selected ? "true" : "false"}
      data-facet={facet}
      onclick={() => {
        if (!is_selected) onSelect(facet);
      }}
    >{facet}</button>
  {/each}
</div>

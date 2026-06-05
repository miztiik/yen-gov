<script lang="ts" generics="T extends string">
  // Generic segmented control - one-of-N value picker that renders each
  // option as a tap-target with a 24px glyph (when available) or the
  // option's text label (fallback when the glyph id is unknown to the
  // icon registry, which happens for chart-type segments whose icons
  // ship in plan chunk U3 follow-ups or F2b).
  //
  // U4 (2026-06-05): this is the generic primitive the chart-type
  // switcher reuses (plan section 16.3a). The switcher composes it as
  //   <SegmentedControl options={feasibleAt(...).map(typeToOption)}
  //                     value={current} onChange={(t) => current = t} />
  // and the consumer's `current` is plain Svelte `$state` - in-memory
  // only, NEVER persisted to the URL (plan section 20.8).
  //
  // Doctrine:
  //   - One segment per option; min 44px touch target per plan
  //     section 16.3a; horizontally scrolls only if width overflows
  //     (rare for chart-types which intersect to 2-3 segments).
  //   - Active segment filled; others outlined. The active option's
  //     human name is the chart's CAPTION (not displayed by this
  //     control) per plan section 16.3a.
  //   - When `options.length === 1`, the caller (NOT this component)
  //     decides to render nothing - a one-option control is chrome
  //     that failed the deletion test. This component renders the
  //     single-option case correctly when asked; the don't-render
  //     decision lives one level up.
  //   - No URL persistence here; that is the caller's concern (and
  //     for chart-type switcher specifically: NO URL writes).
  //   - CLAUDE.md section 0 a11y descoped: no `aria-*`, no `role`.
  //     Visible `title` attribute is the hover tooltip; buttons stay
  //     real `<button>` so keyboard / pointer activation works for
  //     free.
  //
  // See also:
  //   - frontend/src/lib/grapher/feasibleAt.ts (the feasible-set source)
  //   - frontend/src/lib/grapher/catalogue.ts (the `ChartType` union)
  //   - frontend/src/routes/DevChartsSandbox.svelte (composition example)
  //   - docs/architecture/frontend/design-system.md (token vocabulary)

  import TopicIcon from "./TopicIcon.svelte";
  import { lookupIcon } from "./TopicIcon.svelte";

  interface Option {
    /** The value this segment carries. */
    value: T;
    /** Citizen-readable name; also the hover-tooltip text. */
    label: string;
    /**
     * Optional icon id (kebab-case stem of `frontend/public/icons/<id>.svg`).
     * When the id is unknown to the registry, the segment falls back to
     * rendering `label` as text. This is the path U4 takes for
     * chart-type segments whose icons land in F2b.
     */
    glyph?: string;
  }

  interface Props {
    /** The ordered list of segments. The picker renders them in this order. */
    options: readonly Option[];
    /** Currently active value. MUST equal one of `options[*].value` for
     *  the active styling to apply; otherwise no segment is highlighted. */
    value: T;
    /** Called with the new value when a non-active segment is tapped. */
    onChange: (next: T) => void;
    /** Optional outer class for the host group container. */
    cls?: string;
    /**
     * Data-test selector used by Playwright + the in-browser smoke. Set
     * to a stable value so the test can grep one switcher instance from
     * several on the same page. Defaults to "segmented-control".
     */
    testid?: string;
  }

  const {
    options,
    value,
    onChange,
    cls = "",
    testid = "segmented-control",
  }: Props = $props();

  function isActive(opt: Option): boolean {
    return opt.value === value;
  }

  function onClickSegment(opt: Option): void {
    if (isActive(opt)) return; // no-op when re-selecting active
    onChange(opt.value);
  }
</script>

<div
  class="segmented-control inline-flex items-center rounded-md border border-slate-200 bg-white p-0.5 shadow-sm {cls}"
  data-testid={testid}
  data-segment-count={options.length}
>
  {#each options as opt (opt.value)}
    {@const active = isActive(opt)}
    {@const hasGlyph = lookupIcon(opt.glyph ?? null) !== null}
    <button
      type="button"
      class="segmented-control__segment relative inline-flex items-center justify-center min-w-[44px] min-h-[44px] px-2.5 rounded text-xs font-medium transition-colors"
      class:is-active={active}
      data-segment-value={opt.value}
      data-segment-active={active}
      title={opt.label}
      onclick={() => onClickSegment(opt)}
    >
      {#if hasGlyph}
        <TopicIcon name={opt.glyph} cls="w-6 h-6" />
      {:else}
        <span class="segmented-control__label">{opt.label}</span>
      {/if}
    </button>
  {/each}
</div>

<style>
  /* Visual tokens come from app-tokens.css via Tailwind theme.extend
     (plan section 21.7 + U1 ledger row). The base layout here is
     minimal so a host with a custom `cls` can re-skin without
     fighting per-segment rules. */
  .segmented-control__segment {
    color: rgb(71 85 105); /* slate-600 default ink */
    background: transparent;
    cursor: pointer;
  }
  .segmented-control__segment:hover:not(.is-active) {
    background: rgb(248 250 252); /* slate-50 hover wash */
  }
  .segmented-control__segment.is-active {
    background: rgb(15 23 42); /* slate-900 active fill */
    color: white;
    cursor: default;
  }
  .segmented-control__segment:focus-visible {
    outline: 2px solid rgb(14 165 233); /* sky-500 focus ring */
    outline-offset: 1px;
  }
</style>

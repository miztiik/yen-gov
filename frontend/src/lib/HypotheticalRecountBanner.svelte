<script module lang="ts">
  // HypotheticalRecountBanner - mandatory honesty primitive for non-FPTP
  // counterfactual renders in the Psephlab sandbox.
  //
  // Hans's "fabricated-input" type-2 mitigation per
  // TODO/20260607-e6-alternate-counting-methods-subplan.md "Follow-up if
  // user overrides". When the user opts into a counting method other
  // than FPTP (Sainte-Lague, instant-runoff, approval, etc.) the seats
  // shown are SIMULATED, not the result Indian voters actually got -
  // this banner is the structural component that prevents misreading
  // the chart as the real election outcome.
  //
  // The ONE deliberate exception to CLAUDE.md section 0 a11y non-goal:
  // this is a structural-not-decorative WCAG SC 4.1.3 status message
  // (role="alert" + aria-live="polite") so a screen reader announces
  // the simulated-result framing before the seat tally is read out.
  // Without the live-region semantics the warning is just visual chrome
  // and the misread it exists to prevent still happens.
  //
  // Testable surface (per repo vitest doctrine - node-env, no jsdom, no
  // @testing-library/svelte; see Skeleton.test.ts +
  // MapHighlightLegend.test.ts + GallagherDisproportionality.svelte for
  // the 8-test precedent): the pure helpers + `BANNER_HEADLINE`
  // constant exported in this `<script module>` block. The Svelte
  // instance body below is the thin rendering wrapper; DOM-level
  // assertions are deferred to Playwright per CLAUDE.md section 13.

  /** The exact uppercase headline phrase. Treated as a constant so the
   *  test pins the copy precisely; future copy edits update both the
   *  constant and the test in one commit. ASCII-only (hyphen, not
   *  em-dash) per CLAUDE.md section 5. */
  export const BANNER_HEADLINE: string =
    "HYPOTHETICAL RECOUNT - NOT THE OFFICIAL RESULT";

  /** Predicate: render the assumptions <ul> only when at least one
   *  bullet is provided. Defensive against undefined / null / [] so the
   *  renderer body stays declarative. */
  export function shouldRenderAssumptions(
    assumptions: readonly string[] | undefined,
  ): boolean {
    return Array.isArray(assumptions) && assumptions.length > 0;
  }

  /** Build the optional "Official result: <label>" prefix string.
   *  Returns null when no label is provided (or only whitespace) so the
   *  caller can `{#if}` the line out cleanly. */
  export function officialResultLine(
    label: string | undefined,
  ): string | null {
    if (!label || label.trim() === "") return null;
    return `Official result: ${label}`;
  }
</script>

<script lang="ts">
  interface Props {
    /** Human-readable counting method name. Shown in <code> font.
     *  E.g. "Proportional (Sainte-Lague, state-wide)". */
    method: string;
    /** Optional list of plain-English assumption bullets specific to
     *  the counting method. Render order is caller-supplied. */
    assumptions?: string[];
    /** Optional reminder of what the OFFICIAL FPTP result was so the
     *  citizen can compare the simulated counterfactual against the
     *  reality. E.g. "DMK won 133 of 234 seats (FPTP)". */
    official_result_label?: string;
  }
  let { method, assumptions = [], official_result_label }: Props = $props();

  const officialLine = $derived(officialResultLine(official_result_label));
</script>

<div
  role="alert"
  aria-live="polite"
  class="sticky top-0 z-10 bg-rose-50 border border-rose-300 rounded-md p-4 text-rose-900"
>
  <strong class="uppercase tracking-wider text-sm">{BANNER_HEADLINE}</strong>
  <p class="text-xs mt-1">
    Counting method: <code>{method}</code>
  </p>
  {#if officialLine}
    <p class="text-xs mt-1">{officialLine}</p>
  {/if}
  {#if shouldRenderAssumptions(assumptions)}
    <ul role="list" class="mt-2 text-xs space-y-1">
      {#each assumptions as a}
        <li class="flex gap-2">
          <span aria-hidden="true">-</span>
          <span>{a}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

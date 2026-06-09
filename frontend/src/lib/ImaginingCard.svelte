<script module lang="ts">
  // ImaginingCard - encouraging-tone honesty marker for non-FPTP counting
  // methods in the Psephlab Election Studio.
  //
  // Per Hans + Jony + Fowler triple-verdict convergence (2026-06-09):
  // retires HypotheticalRecountBanner's rose-50 hazard chrome in favour
  // of a paper surface + civic-indigo accent rail. Same structural
  // honesty payload (method name, official-result comparator, per-method
  // assumptions), different visual register: invitational, not alarmist.
  // The citizen came here voluntarily knowing this is a what-if explorer.
  //
  // role="alert" + aria-live="polite" SURVIVE (the ONE deliberate
  // exception to CLAUDE.md section 0 a11y non-goal; the announcement
  // primitive is the structural reason this component exists at all,
  // independent of visual chrome). Only the colour palette moves from
  // rose to civic-indigo + slate; the screen-reader semantics are
  // identical to the retired component.
  //
  // Hans-non-negotiable: when official_result_label is provided, it
  // renders inline-above-headline so a screenshot recipient sees the
  // OFFICIAL FPTP result next to the simulated one. Without this the
  // chart fails the Pramit WhatsApp test.
  //
  // Per-method long-form (history, math, India-specific limitations)
  // lives at /docs/lab/<method-id> - the Read-how-this-counting-works
  // link emits the path via `url.docsLabMethod(method_id)` so the
  // citizen who wants depth is one tap away. In-app surface stays
  // light and encouraging; pedagogy stays in /docs.

  /**
   * The exact encouraging-tone headline. Treated as a constant so the
   * test pins the copy precisely; future edits update both the constant
   * and the test in one commit. ASCII-only per CLAUDE.md section 5.
   */
  export const IMAGINING_HEADLINE: string =
    "Imagine the seats under a different counting rule.";

  /** Predicate mirroring HypotheticalRecountBanner.shouldRenderAssumptions
   *  so the migration is byte-byte equivalent on the rendering branch.
   *  Returns true only when at least one bullet is present. */
  export function shouldRenderAssumptions(
    assumptions: readonly string[] | undefined,
  ): boolean {
    return Array.isArray(assumptions) && assumptions.length > 0;
  }

  /** Builds the "Official: X / Imagined: Y" comparator copy Hans
   *  flagged as load-bearing for the screenshot defence. Returns null
   *  when the official label is absent (FPTP itself never mounts this
   *  card so the null branch is for tests / fixtures without a
   *  precomputed FPTP result). */
  export function officialResultLine(
    label: string | undefined,
  ): string | null {
    if (!label || label.trim() === "") return null;
    return `Official: ${label}`;
  }
</script>

<script lang="ts">
  interface Props {
    /** Citizen-readable counting method name shown in the headline. */
    method: string;
    /** Optional list of plain-English assumption bullets specific to
     *  the counting method (Hans's safety-critical inline items). */
    assumptions?: string[];
    /** Optional one-line citation of the OFFICIAL FPTP result so the
     *  citizen sees the comparator inline with the simulated tally.
     *  E.g. "DMK won 133 of 234 seats (FPTP)". */
    official_result_label?: string;
    /** Optional link to /docs/lab/<method-id> for the long-form
     *  pedagogy. Caller builds via `url.docsLabMethod(method_id)`. */
    docs_href?: string;
  }
  let {
    method,
    assumptions = [],
    official_result_label,
    docs_href,
  }: Props = $props();

  const officialLine = $derived(officialResultLine(official_result_label));
</script>

<!--
  Paper surface + civic-indigo accent rail + slate body text. Mounts as
  a stuck-top status announcement so a screen reader hears the framing
  before the seat tally is read; visually it sits as a calm card.
  Border-l-4 (civic-indigo) is the only chromatic accent; no rose, no
  hazard glyph, no uppercase scream.
-->
<div
  role="alert"
  aria-live="polite"
  class="sticky top-0 z-10 bg-surface border border-line border-l-4 rounded-md p-4 shadow-sm"
  style:border-left-color="var(--accent, #3538cd)"
  data-component="imagining-card"
>
  <p class="text-sm font-semibold leading-snug" style:color="var(--ink, #0f172a)">
    {IMAGINING_HEADLINE}
  </p>
  <p class="text-xs mt-1" style:color="var(--ink-muted, #64748b)">
    Counting rule: <code class="font-mono text-xs">{method}</code>
  </p>
  {#if officialLine}
    <p class="text-xs mt-1" style:color="var(--ink-muted, #64748b)">
      {officialLine}
    </p>
  {/if}
  {#if shouldRenderAssumptions(assumptions)}
    <ul role="list" class="mt-3 text-xs space-y-1" style:color="var(--ink, #0f172a)">
      {#each assumptions as a}
        <li class="flex gap-2">
          <span aria-hidden="true" style:color="var(--ink-muted, #64748b)">-</span>
          <span>{a}</span>
        </li>
      {/each}
    </ul>
  {/if}
  {#if docs_href}
    <p class="text-xs mt-3">
      <a
        href={docs_href}
        class="hover:underline"
        style:color="var(--accent, #3538cd)"
      >Read how this counting works -&gt;</a>
    </p>
  {/if}
</div>

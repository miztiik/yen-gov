<script module lang="ts">
  // HeroExplanation - the full-width encouraging-tone hero card under
  // the MethodPickerPill. Replaces ImaginingCard's right-column
  // placement with a top-of-page, full-width treatment.
  //
  // Per Jony + Hans verdict (2026-06-09 round 2, user ask #3):
  // "the short explanation for all modes is enough using the full
  // column width". The hero card ALWAYS mounts (including under FPTP -
  // round 1 missed this teaching moment by hiding the card for FPTP).
  //
  // Hans's encouraging tone:
  //   - Headline: ≤ 12 words, visionary not warning
  //   - One-line description (caveat or assumption distillation)
  //   - Read more link surfaced prominently
  //   - Optional "Holds constant" bullet list (≤ 4 items)
  //   - Validity badge inline (Hans-non-negotiable)
  //
  // Per CLAUDE.md section 0 a11y non-goal: no aria-roles beyond what
  // <p>/<ul>/<li>/<a> grant natively. The `role="alert"` is the ONE
  // exception (mirroring ImaginingCard's structural-reason behaviour
  // - the live-region announces method changes to assistive tech).

  export interface HeroExplanationProps {
    /** Method label (Hans's encouraging short_label). */
    method_label: string;
    /** One-line encouraging headline (≤ 12 words). */
    headline: string;
    /** Optional one-paragraph encouraging caveat (the citizen-facing
     *  "what holds constant" explanation). */
    caveat?: string;
    /** Validity tier - drives the badge visual treatment. */
    validity: "fully_workable" | "medium_validity";
    /** "Holds constant" bullets (Hans's load-bearing list).
     *  Optional; when empty, the bullet block is omitted. */
    assumptions?: string[];
    /** Optional "Official FPTP" reference line for the WhatsApp
     *  screenshot defence (Hans-non-negotiable when method != FPTP). */
    official_result_label?: string;
    /** Optional /docs/lab/<method-id> URL for the long-form. */
    docs_href?: string;
    /** Whether the citizen is currently on FPTP (the official rule).
     *  FPTP gets a different visual treatment - no civic-indigo rail,
     *  no validity badge ("Fully workable" is implicit for the
     *  baseline). */
    is_official: boolean;
  }

  /** Pure helper - the validity badge text. */
  export function validityBadgeText(tier: "fully_workable" | "medium_validity"): string {
    return tier === "fully_workable" ? "Fully workable" : "Experimental";
  }

  /** Pure helper - default headline when none is set. Defensive. */
  export function defaultHeadline(method_label: string): string {
    return `Explore the seats under ${method_label}.`;
  }
</script>

<script lang="ts">
  let {
    method_label,
    headline,
    caveat,
    validity,
    assumptions = [],
    official_result_label,
    docs_href,
    is_official,
  }: HeroExplanationProps = $props();

  const has_bullets = $derived(assumptions.length > 0);
  const effective_headline = $derived(headline && headline.trim() !== "" ? headline : defaultHeadline(method_label));
</script>

<section
  role={is_official ? undefined : "alert"}
  aria-live={is_official ? undefined : "polite"}
  class="bg-surface rounded-lg border border-line shadow-sm p-5"
  class:border-l-4={!is_official}
  style:border-left-color={is_official ? undefined : "var(--accent, #3538cd)"}
  data-component="hero-explanation"
>
  <div class="flex items-baseline justify-between gap-3 flex-wrap mb-2">
    <h2 class="text-lg font-bold leading-snug" style:color="var(--ink, #0f172a)">
      {effective_headline}
    </h2>
    {#if !is_official}
      <span
        class="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded"
        class:bg-emerald-50={validity === "fully_workable"}
        class:text-emerald-700={validity === "fully_workable"}
        class:bg-amber-50={validity === "medium_validity"}
        class:text-amber-800={validity === "medium_validity"}
      >
        {validityBadgeText(validity)}
      </span>
    {/if}
  </div>

  <p class="text-xs" style:color="var(--ink-muted, #64748b)">
    Counting rule: <code class="font-mono text-xs">{method_label}</code>
  </p>

  {#if official_result_label && !is_official}
    <p class="text-xs mt-1" style:color="var(--ink-muted, #64748b)">
      Official result: {official_result_label}
    </p>
  {/if}

  {#if caveat}
    <p class="text-sm mt-3 leading-relaxed" style:color="var(--ink, #0f172a)">
      {caveat}
    </p>
  {/if}

  {#if has_bullets}
    <details class="mt-3 group">
      <summary
        class="text-xs font-semibold uppercase tracking-wide cursor-pointer select-none inline-flex items-center gap-1"
        style:color="var(--ink-muted, #64748b)"
      >
        <span>What this view holds constant</span>
        <span aria-hidden="true" class="text-[10px] group-open:rotate-180 transition-transform inline-block">v</span>
      </summary>
      <ul role="list" class="mt-2 text-xs space-y-1" style:color="var(--ink, #0f172a)">
        {#each assumptions as a (a)}
          <li class="flex gap-2">
            <span aria-hidden="true" style:color="var(--ink-muted, #64748b)">-</span>
            <span>{a}</span>
          </li>
        {/each}
      </ul>
    </details>
  {/if}

  {#if docs_href}
    <p class="text-sm mt-4">
      <a
        href={docs_href}
        class="font-medium hover:underline inline-flex items-center gap-1"
        style:color="var(--accent, #3538cd)"
      >
        <span>Read how this counting works</span>
        <span aria-hidden="true">-&gt;</span>
      </a>
    </p>
  {/if}
</section>

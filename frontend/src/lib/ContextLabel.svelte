<script module lang="ts">
  // ContextLabel - one-line "which election am I looking at" strip
  // shown directly under the method tabs in the Psephlab Election
  // Studio. Per Jony + Hans convergence (2026-06-09 debate, user
  // ask #3): the citizen MUST always know which election is on the
  // screen + whether the chamber is actuals or a what-if scenario.
  //
  // Format (three parts joined by " . "):
  //   <election-display> . <seat-count> seats . <mode-marker>
  //
  // mode-marker examples:
  //   - "actuals"                       (FPTP, zero mutations)
  //   - "1 what-if applied"             (FPTP + 1 mutation; pluralised)
  //   - "imagined under Proportional"   (non-FPTP, zero mutations)
  //   - "imagined under Proportional + 2 what-ifs"
  //   - "comparing TN Apr 2021 vs TN May 2026" (compare context)
  //
  // The election-display comes from findEvent(...).display which already
  // returns citizen-readable strings ("TN AC Apr 2021"). The state
  // prefix is NOT stripped - the citizen needs the full context for
  // screenshots (Hans's WhatsApp-screenshot defence).

  /** Pure builder for the mode-marker text. Pure so vitest can pin the
   *  copy across the matrix of (rule, mutations, compare) without
   *  mounting Svelte. */
  export interface ModeMarkerInput {
    /** Active counting rule id ("fptp" | "proportional" | ...). */
    rule_id: string;
    /** Citizen-readable rule label (e.g. "Proportional (Sainte-Lague, state-wide)"). */
    rule_label: string;
    /** Number of mutations applied to the active scenario. */
    mutation_count: number;
    /** Optional "compare-with" event display string. When set, the
     *  marker switches to a comparison format. */
    compare_with?: string | null;
  }

  export function buildModeMarker(input: ModeMarkerInput): string {
    if (input.compare_with && input.compare_with.trim() !== "") {
      return `comparing with ${input.compare_with}`;
    }
    const is_fptp = input.rule_id === "fptp";
    const mutation_part =
      input.mutation_count === 0
        ? ""
        : input.mutation_count === 1
          ? "1 what-if applied"
          : `${input.mutation_count} what-ifs applied`;
    if (is_fptp) {
      // FPTP is the official rule; zero mutations => bare "actuals".
      return mutation_part === "" ? "actuals" : mutation_part;
    }
    // Non-FPTP: prefix the imagining language so a screenshot screams
    // "this is a counterfactual" without a separate banner.
    const imagined = `imagined under ${input.rule_label}`;
    return mutation_part === "" ? imagined : `${imagined} + ${mutation_part}`;
  }

  export interface ContextLabelInput extends ModeMarkerInput {
    election_display: string | null;
    seat_count: number;
  }

  /** Full context-label string. Returns "" when election_display is
   *  null (the catalogue is still loading); the host renders a
   *  Skeleton until then. */
  export function buildContextLabel(input: ContextLabelInput): string {
    if (input.election_display == null || input.election_display === "") {
      return "";
    }
    const parts = [
      input.election_display,
      `${input.seat_count} seats`,
      buildModeMarker(input),
    ];
    return parts.join(" . ");
  }
</script>

<script lang="ts">
  interface Props {
    election_display: string | null;
    seat_count: number;
    rule_id: string;
    rule_label: string;
    mutation_count: number;
    compare_with?: string | null;
  }
  let {
    election_display,
    seat_count,
    rule_id,
    rule_label,
    mutation_count,
    compare_with,
  }: Props = $props();

  const text = $derived(
    buildContextLabel({
      election_display,
      seat_count,
      rule_id,
      rule_label,
      mutation_count,
      compare_with,
    }),
  );
</script>

{#if text}
  <p
    class="text-xs tabular-nums"
    style:color="var(--ink-muted, #64748b)"
    data-component="context-label"
  >
    {text}
  </p>
{/if}

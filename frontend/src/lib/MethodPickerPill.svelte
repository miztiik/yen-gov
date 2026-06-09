<script module lang="ts">
  // MethodPickerPill - the new method-picker entry point for the
  // Election Studio. Replaces MethodTabs's horizontal-scroll segmented
  // control (Round-1 design that hit its scaling limit at 4 methods;
  // 12 methods exceed the budget).
  //
  // Per Jony + Fowler + Hans convergence (2026-06-09 round 2 debate):
  // "the chamber is one room; the pill says which rule is in force;
  // the drawer holds the twelve doors out." One button, one tap, the
  // drawer rises (mobile) / falls (desktop) with categorised cards.
  //
  // Behaviour:
  //   - Renders a single pill: "Method: <short_label>  [Change v]".
  //   - Pill is a full 44px touch target on mobile (CLAUDE.md 13).
  //   - `onopen` is invoked with no args; the host owns the drawer
  //     open/close state and renders MethodDrawer next to this pill.
  //   - Civic-indigo accent border, paper surface, slate body text;
  //     same palette as ImaginingCard (Hans's encouraging tone).

  export interface MethodPickerPillProps {
    /** Short label of the active rule (CountingRule.short_label or
     *  fallback to label). Shown inside the pill. */
    active_label: string;
    /** Invoked when the citizen taps the pill. The host then opens
     *  the drawer (parent owns the dialog state). */
    onopen: () => void;
  }
</script>

<script lang="ts">
  let { active_label, onopen }: MethodPickerPillProps = $props();
</script>

<button
  type="button"
  class="inline-flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 min-h-[44px] text-sm font-medium shadow-sm transition-colors hover:border-accent"
  style:color="var(--ink, #0f172a)"
  data-component="method-picker-pill"
  aria-haspopup="dialog"
  aria-label="Change counting method (opens picker)"
  onclick={onopen}
>
  <span style:color="var(--ink-muted, #64748b)">Method:</span>
  <span class="font-semibold truncate max-w-[16rem] md:max-w-none">{active_label}</span>
  <span aria-hidden="true" style:color="var(--accent, #3538cd)" class="ml-1">Change v</span>
</button>

<script module lang="ts">
  // MethodTabs - method-first navigation for the Election Studio
  // (Psephlab). Per Jony + Fowler convergence (2026-06-09 debate):
  // "a counting method is a room, not a setting." The picker moves
  // from a footer dropdown to a top-of-page segmented control so the
  // citizen walks INTO a method instead of switching one inside FPTP.
  //
  // The tab strip is URL-bound. Selecting a tab navigates to
  // /lab/<state>/<event>/m/<method-id> via url.labMethod. The bare
  // /lab/<state>/<event> URL (no /m/ segment) keeps defaulting to
  // FPTP so every existing share link still works (Fowler's
  // strangler-fig EXPAND, never MIGRATE in the same PR).
  //
  // Mobile (360px): horizontal-scrollable strip; min 44px touch
  // targets per tab; selected tab fills with --accent, others stay
  // paper. Desktop: same strip, wider tabs.
  //
  // Per CLAUDE.md section 0 a11y non-goal: no aria-roles beyond a
  // single aria-label on the nav wrapper. The visible affordance
  // (selected fill + tab labels) is the contract.

  /** A method choice the tab strip can render. Mirrors the relevant
   *  subset of CountingRule so MethodTabs has no dependency on the
   *  full rules registry (Jony's "two engines, two stacks" anti-rule;
   *  the tab strip is a presentation primitive). */
  export interface MethodTabOption {
    id: string;
    label: string;
  }
</script>

<script lang="ts">
  interface Props {
    /** Ordered list of method options to render as tabs. Caller
     *  builds via `RULES.map(r => ({ id: r.id, label: r.label }))`
     *  so adding a new rule registers a new tab automatically. */
    methods: ReadonlyArray<MethodTabOption>;
    /** The currently-active method id. Filled tab is the one matching
     *  this value; non-matches stay paper-outline. */
    active_method_id: string;
    /** Click handler invoked with the picked method id. Caller
     *  navigates via `url.labMethod(state, event, method_id)`. */
    onpick: (method_id: string) => void;
  }
  let { methods, active_method_id, onpick }: Props = $props();
</script>

<nav
  aria-label="Choose a counting rule"
  class="flex gap-1 overflow-x-auto py-1 -mx-1 px-1"
  data-component="method-tabs"
>
  {#each methods as m (m.id)}
    {@const is_active = m.id === active_method_id}
    <button
      type="button"
      class="shrink-0 rounded-md text-sm font-medium transition-colors px-3 min-h-[44px] border"
      class:bg-accent={is_active}
      class:text-white={is_active}
      class:border-accent={is_active}
      class:bg-surface={!is_active}
      class:text-ink={!is_active}
      class:border-line={!is_active}
      class:hover:bg-surface-sunken={!is_active}
      style:background-color={is_active ? "var(--accent, #3538cd)" : "var(--surface, #ffffff)"}
      style:color={is_active ? "#ffffff" : "var(--ink, #0f172a)"}
      style:border-color={is_active ? "var(--accent, #3538cd)" : "var(--line, #e2e8f0)"}
      data-method-id={m.id}
      aria-pressed={is_active}
      onclick={() => onpick(m.id)}
    >
      {m.label}
    </button>
  {/each}
</nav>

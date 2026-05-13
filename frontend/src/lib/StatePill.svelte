<script lang="ts">
  // Pinned scope context at the top of the LeftRail (P3.3c).
  //
  // Replaces the previous always-open ScopePicker. The pill collapses
  // to a single line ("You're looking at: <State> ▾" or "Pick your
  // state ▾") so the rail's visual weight goes to the four IA groups,
  // not to chrome. Click expands a popover that mounts the existing
  // ScopePicker — same selects, same behaviour, no logic duplication.
  //
  // Implementation choice: native <details>/<summary>. No JS for
  // open/close, no click-outside listener, native ESC handling, works
  // offline / with no Svelte runes wrapping the state.
  //
  // ADR notes:
  //   - The label is reactive on `scope.state` via $derived; selecting
  //     a new state in the popover updates the URL (ScopePicker.navigate)
  //     and the pill re-renders.
  //   - We DO NOT auto-close on selection. The popover is small enough
  //     that a stale-open state isn't visually noisy, and forcing close
  //     would need bind:open + an effect — not worth the surface.

  import ScopePicker from "./ScopePicker.svelte";
  import { scope } from "./scope.svelte";
  import { states } from "./states.svelte";

  const label = $derived(
    scope.state
      ? `You're looking at: ${states.name(scope.state)}`
      : "Pick your state",
  );
</script>

<details class="state-pill border-b border-slate-200 bg-slate-50">
  <summary
    class="flex items-center justify-between px-3 py-2 text-sm cursor-pointer
           hover:bg-slate-100 list-none select-none"
    aria-label="Change scope"
  >
    <span class="truncate text-slate-700">{label}</span>
    <span class="text-slate-400 text-xs ml-2">▾</span>
  </summary>
  <ScopePicker />
</details>

<style>
  /* Hide the default disclosure marker on Safari/Chromium so our ▾
   * carat is the only one visible. Firefox respects list-none. */
  .state-pill > summary::-webkit-details-marker {
    display: none;
  }
</style>

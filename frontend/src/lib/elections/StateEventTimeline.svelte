<script lang="ts">
  // Per-state chronological election timeline (PR-W3a, 2026-06-10).
  //
  // Pure render component. Props: { events, state_slug }. Sorts the
  // input rows newest-first by polled_on (lexicographic == chronological
  // because polled_on is ISO YYYY-MM-DD) and emits one anchor row per
  // event, click-through to `link.stateElection(state, event_id)`.
  //
  // Body-kind chip colours match the elections-route convention
  // (PR-E4 of TODO/20260615-elections-redesign-plan.md; the prior
  // firehose route was ripped + replaced by GeneralElections.svelte +
  // AssemblyElections.svelte):
  // emerald = parliament, amber = assembly, slate = by-elections. The
  // chip is the secondary signal; the row's plain-text display field is
  // always visible so colour-blind citizens never lose the body label.
  //
  // Per-row decorations (winning party / seat count / swing vs previous
  // same-body event) are explicitly DEFERRED to a follow-up PR per the
  // PR-W3a scope. The plan-doc names them as desirable but the
  // chronological timeline + body filter is the load-bearing rip; the
  // decorations are lazy-loaded per row via loadElectionResults() in a
  // later PR.

  import type { ElectionEventRow } from "../election-events";
  import { link } from "../links";

  interface Props {
    events: ElectionEventRow[];
    /** State slug for the click-through URL builder. The builder also
     * accepts an ECI code but the caller already has the slug from
     * params.state, so we keep it slug-typed to avoid a redundant
     * lookup. */
    state_slug: string;
  }

  let { events, state_slug }: Props = $props();

  // Always-sort defensively even though listEventsForState() already
  // returns newest-first; the type contract is "ElectionEventRow[]" and
  // a future caller might not honour the order.
  const sorted = $derived(
    [...events].sort((a, b) => b.polled_on.localeCompare(a.polled_on)),
  );

  function chipClass(kind: ElectionEventRow["kind"]): string {
    if (kind === "parliament" || kind === "general_bye") {
      return "bg-emerald-100 text-emerald-700";
    }
    // assembly + assembly_bye + by_election (legacy catch-all) all share
    // the assembly colour because they are all AC-house events from the
    // citizen's perspective.
    return "bg-amber-100 text-amber-700";
  }

  function chipLabel(kind: ElectionEventRow["kind"]): string {
    switch (kind) {
      case "parliament":
        return "Parliament";
      case "assembly":
        return "Assembly";
      case "general_bye":
        return "Parliament by-election";
      case "assembly_bye":
        return "Assembly by-election";
      case "by_election":
        return "By-election";
    }
  }
</script>

{#if sorted.length === 0}
  <p
    class="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
    data-testid="state-event-timeline-empty"
  >
    No elections match this filter.
  </p>
{:else}
  <ol
    class="space-y-2 list-none p-0"
    data-testid="state-event-timeline"
  >
    {#each sorted as ev (ev.event_id)}
      <li>
        <a
          href={link.stateElection(state_slug, ev.event_id)}
          data-testid="event-timeline-row-{ev.event_id}"
          class="flex items-center justify-between gap-3 rounded border border-slate-200 bg-white p-3 hover:bg-sky-50 hover:border-sky-200 transition-colors"
        >
          <div class="flex items-center gap-3 min-w-0">
            <span
              class="font-mono text-sm font-medium text-slate-700 shrink-0 w-12"
            >
              {ev.polled_on.slice(0, 4)}
            </span>
            <span
              class="px-2 py-0.5 rounded text-xs font-medium shrink-0 {chipClass(
                ev.kind,
              )}"
            >
              {chipLabel(ev.kind)}
            </span>
            <span class="text-sm text-slate-700 truncate">
              {ev.display}
            </span>
          </div>
          <span class="text-xs text-slate-400 shrink-0">
            {ev.polled_on}
          </span>
        </a>
      </li>
    {/each}
  </ol>
{/if}

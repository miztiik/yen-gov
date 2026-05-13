<script lang="ts">
  // Seventh Schedule list-membership badge.
  //
  // Mandatory chrome on every cross-state surface per ADR-0022 (Governance
  // Strategist standing position). Renders the constitutional location of
  // the topic so the citizen knows, before reading any number, whether
  // the subject is administered by the State (police, agriculture, public
  // health), the Union (defence, railways, GST policy), the Concurrent list
  // (education, criminal law, economic planning), or none of the above
  // (process topics like elections).
  //
  // Render-only component: takes the list value, returns a coloured chip.
  // No data fetch, no state, no events — drop-in next to any topic <h2>.

  import type { SeventhScheduleList } from "./catalogue";

  interface Props {
    list: SeventhScheduleList;
    /** Optional compact variant for tight layouts (drops the "List:" prefix). */
    compact?: boolean;
  }

  let { list, compact = false }: Props = $props();

  // Colour scheme is intentional but NOT a meaning vehicle (per CLAUDE.md
  // §0: colour is one signal among many, the text label carries the actual
  // information). Slate for `na` because process topics have no list.
  const STYLES: Record<SeventhScheduleList, { bg: string; text: string; label: string }> = {
    state: { bg: "bg-emerald-50", text: "text-emerald-700", label: "State" },
    union: { bg: "bg-amber-50", text: "text-amber-700", label: "Union" },
    concurrent: { bg: "bg-sky-50", text: "text-sky-700", label: "Concurrent" },
    na: { bg: "bg-slate-100", text: "text-slate-600", label: "N/A" },
  };

  const TITLES: Record<SeventhScheduleList, string> = {
    state: "Seventh Schedule State List — administered by the state government",
    union: "Seventh Schedule Union List — administered by the Government of India",
    concurrent: "Seventh Schedule Concurrent List — both Centre and state may legislate",
    na: "Not a Seventh Schedule subject (process topic)",
  };

  const style = $derived(STYLES[list]);
  const title = $derived(TITLES[list]);
</script>

<span
  data-listbadge={list}
  title={title}
  class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium {style.bg} {style.text}"
>
  {#if !compact}<span class="text-[0.65rem] uppercase tracking-wide opacity-70">List:</span>{/if}
  <span>{style.label}</span>
</span>

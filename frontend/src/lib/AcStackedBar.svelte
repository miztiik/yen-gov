<script lang="ts">
  // Single horizontal stacked bar showing the share each candidate (top-N),
  // NOTA, and the collapsed "others" bucket took in one constituency.
  //
  // Pure presentational: takes a ConstituencyResult and renders. No fetch.
  // Segments are colored by the candidate's party via the colors store.
  import type { ConstituencyResult } from "./data";
  import { colors } from "./colors/store.svelte";

  let { result }: { result: ConstituencyResult } = $props();

  interface Seg {
    label: string;
    party_short: string;
    party_eci_code: string | null;
    pct: number;
    votes: number;
    is_winner: boolean;
    is_special?: "nota" | "others";
  }

  const segments = $derived.by<Seg[]>(() => {
    const out: Seg[] = result.candidates.map(c => ({
      label: c.name,
      party_short: c.party_short,
      party_eci_code: c.party_eci_code,
      pct: c.vote_share_pct,
      votes: c.votes,
      is_winner: !!c.is_winner,
    }));
    out.push({
      label: "NOTA",
      party_short: "NOTA",
      party_eci_code: null,
      pct: result.nota.vote_share_pct,
      votes: result.nota.votes,
      is_winner: false,
      is_special: "nota",
    });
    if (result.others) {
      out.push({
        label: `Others (${result.others.candidate_count})`,
        party_short: "Others",
        party_eci_code: null,
        pct: result.others.vote_share_pct,
        votes: result.others.votes,
        is_winner: false,
        is_special: "others",
      });
    }
    return out;
  });

  function color_for(s: Seg): string {
    if (s.is_special === "nota") return colors.fill("NOTA", "NOTA");
    if (s.is_special === "others") return "#cbd5e1";  // slate-300, neutral
    return colors.fill(s.party_eci_code, s.party_short);
  }
</script>

<div class="space-y-2">
  <div class="relative h-8 rounded overflow-hidden flex bg-slate-100">
    {#each segments as s (s.label)}
      <div
        class="h-full transition-[flex-grow] duration-500 ease-out relative group"
        style:flex-grow={s.pct}
        style:background-color={color_for(s)}
        title="{s.label} ({s.party_short}) · {s.votes.toLocaleString()} · {s.pct.toFixed(2)}%"
      >
        {#if s.pct >= 8}
          <span class="absolute inset-0 flex items-center justify-center text-[10px] font-semibold text-white drop-shadow truncate px-1">
            {s.party_short} {s.pct.toFixed(0)}%
          </span>
        {/if}
      </div>
    {/each}
  </div>

  <ul class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
    {#each segments as s (s.label)}
      <li class="flex items-center gap-1.5">
        <span class="inline-block w-2.5 h-2.5 rounded-sm" style:background-color={color_for(s)}></span>
        <span class="font-medium">{s.party_short}</span>
        <span class="text-slate-400">{s.pct.toFixed(2)}%</span>
      </li>
    {/each}
  </ul>
</div>

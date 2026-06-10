<script lang="ts">
  // Single horizontal stacked bar showing the share each candidate (top-N),
  // NOTA, and the collapsed "others" bucket took in one constituency.
  //
  // Pure presentational: takes a ConstituencyResult and renders. No fetch.
  // Segments are colored by the candidate's party via the 3-tier resolver
  // (anchor -> Wikipedia brand_colour -> algorithmic fallback). PR-SYM-6c:
  // first consumer migrated off the legacy `partyColour(eci_code, ...)` path
  // onto `getPartyColor(party_id, row)` which keys on the canonical
  // taxonomy id, not the ECI alias.
  import type { ConstituencyResult } from "./data";
  import { getPartyColor } from "./colors/resolver";
  import PartySymbolGlyph from "./PartySymbolGlyph.svelte";

  let { result }: { result: ConstituencyResult } = $props();

  interface Seg {
    label: string;
    party_id: string;
    party_short: string;
    pct: number;
    votes: number;
    is_winner: boolean;
    is_special?: "nota" | "others";
    brand_colour_hex: string | null;
    brand_colour_confidence: "high" | "medium" | "low" | null;
    // PR-SYM glyph: dim_parties.election_symbol_asset_path threaded
    // through CandidateResult so the legend can render the party's
    // ballot-symbol next to its short name (when present).
    election_symbol_asset_path: string | null;
  }

  const segments = $derived.by<Seg[]>(() => {
    const out: Seg[] = result.candidates.map(c => ({
      label: c.name,
      party_id: c.party_id,
      party_short: c.party_short,
      pct: c.vote_share_pct,
      votes: c.votes,
      is_winner: !!c.is_winner,
      brand_colour_hex: c.brand_colour_hex ?? null,
      brand_colour_confidence: c.brand_colour_confidence ?? null,
      election_symbol_asset_path: c.election_symbol_asset_path ?? null,
    }));
    out.push({
      label: "NOTA",
      party_id: "parties.IN.NOTA",
      party_short: "NOTA",
      pct: result.nota.vote_share_pct,
      votes: result.nota.votes,
      is_winner: false,
      is_special: "nota",
      brand_colour_hex: null,
      brand_colour_confidence: null,
      election_symbol_asset_path: null,
    });
    if (result.others) {
      out.push({
        label: `Others (${result.others.candidate_count})`,
        party_id: "parties.IN.OTHERS",
        party_short: "Others",
        pct: result.others.vote_share_pct,
        votes: result.others.votes,
        is_winner: false,
        is_special: "others",
        brand_colour_hex: null,
        brand_colour_confidence: null,
        election_symbol_asset_path: null,
      });
    }
    return out;
  });

  function color_for(s: Seg): string {
    if (s.is_special === "others") return "#cbd5e1"; // slate-300 neutral
    // Resolver consumes brand_colour_hex when confidence is high/medium;
    // falls through to anchor (NOTA, IND, BJP, INC, ...) or algorithmic
    // hash. NEVER mutates the returned hex.
    return getPartyColor(s.party_id, {
      party_id: s.party_id,
      brand_colour: s.brand_colour_hex
        ? {
            hex: s.brand_colour_hex,
            confidence: s.brand_colour_confidence ?? "medium",
          }
        : null,
    }).hex;
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
        <PartySymbolGlyph assetPath={s.election_symbol_asset_path} size={14} fallback="placeholder" />
        <span class="font-medium">{s.party_short}</span>
        <span class="text-slate-400">{s.pct.toFixed(2)}%</span>
      </li>
    {/each}
  </ul>
</div>

<script lang="ts">
  // SwingSankey — visualise net party-to-party vote flow between actuals
  // and the mutated scenario.
  //
  // Method: compare aggregate per-party votes in actuals vs scenario.
  // Parties whose votes dropped are "losers" (left column); parties whose
  // votes grew are "gainers" (right column). We don't have the true
  // bipartite flow matrix (mutations are per-AC and may overlap), so we
  // approximate: each loser distributes its loss to gainers in proportion
  // to each gainer's share of total gain. Loss total ≈ gain total because
  // mutations conserve per-AC totals; we accept any small drift silently
  // (rounding only).

  import type { PartyResult } from "./psephlab/types";
  import { colors } from "./colors/store.svelte";

  interface Props {
    actuals: PartyResult[];   // by_party from actuals allocation
    scenario: PartyResult[];  // by_party from scenario allocation
  }
  let { actuals, scenario }: Props = $props();

  const W = 600;
  const H = 360;
  const PAD_Y = 8;
  const COL_W = 14;
  const LEFT_X = 100;
  const RIGHT_X = W - 100 - COL_W;

  interface Node {
    party_eci_code: string;
    party_short: string;
    delta: number;            // |votes_diff|
    color: string;
  }

  // Build loser / gainer node lists from the diff.
  const diff = $derived.by(() => {
    const a_map = new Map(actuals.map(p => [p.party_eci_code, p]));
    const s_map = new Map(scenario.map(p => [p.party_eci_code, p]));
    const losers: Node[] = [];
    const gainers: Node[] = [];
    const all_codes = new Set([...a_map.keys(), ...s_map.keys()]);
    for (const code of all_codes) {
      const a = a_map.get(code);
      const s = s_map.get(code);
      const av = a?.votes ?? 0;
      const sv = s?.votes ?? 0;
      const delta = sv - av;
      const short = s?.party_short ?? a?.party_short ?? code;
      const color = colors.fill(code, short);
      if (delta < -0.5) losers.push({ party_eci_code: code, party_short: short, delta: -delta, color });
      else if (delta > 0.5) gainers.push({ party_eci_code: code, party_short: short, delta, color });
    }
    losers.sort((a, b) => b.delta - a.delta);
    gainers.sort((a, b) => b.delta - a.delta);
    return { losers, gainers };
  });

  const total_loss = $derived(diff.losers.reduce((s, n) => s + n.delta, 0));
  const total_gain = $derived(diff.gainers.reduce((s, n) => s + n.delta, 0));
  const flow_total = $derived(Math.max(total_loss, total_gain, 1));

  // Vertical layout: column heights span (H - 2*PAD_Y) proportional to
  // each node's share of the total flow.
  function stack(nodes: Node[], total: number): { y: number; h: number }[] {
    const usable = H - 2 * PAD_Y;
    const out: { y: number; h: number }[] = [];
    let y = PAD_Y;
    for (const n of nodes) {
      const h = total > 0 ? (n.delta / total) * usable : 0;
      out.push({ y, h });
      y += h + 2;       // 2px gap between bands
    }
    return out;
  }

  const left_pos = $derived(stack(diff.losers, flow_total));
  const right_pos = $derived(stack(diff.gainers, flow_total));

  // Ribbons: each loser → each gainer, share = gainer.delta / total_gain.
  // We track running offsets within each node's band so ribbons stack
  // without overlapping.
  const ribbons = $derived.by(() => {
    if (total_gain <= 0 || total_loss <= 0) return [];
    type Ribbon = { y_l_top: number; y_l_bot: number; y_r_top: number; y_r_bot: number; color: string; flow: number; from: string; to: string };
    const out: Ribbon[] = [];
    const left_used = diff.losers.map(() => 0);
    const right_used = diff.gainers.map(() => 0);
    for (let li = 0; li < diff.losers.length; li++) {
      const lp = diff.losers[li];
      const lb = left_pos[li];
      for (let ri = 0; ri < diff.gainers.length; ri++) {
        const gp = diff.gainers[ri];
        const rb = right_pos[ri];
        const flow = lp.delta * (gp.delta / total_gain);
        const lh = lb.h * (flow / lp.delta);
        const rh = rb.h * (flow / gp.delta);
        const y_l_top = lb.y + left_used[li];
        const y_r_top = rb.y + right_used[ri];
        out.push({
          y_l_top,
          y_l_bot: y_l_top + lh,
          y_r_top,
          y_r_bot: y_r_top + rh,
          color: lp.color,
          flow,
          from: lp.party_short,
          to: gp.party_short,
        });
        left_used[li] += lh;
        right_used[ri] += rh;
      }
    }
    return out;
  });

  function ribbon_path(r: { y_l_top: number; y_l_bot: number; y_r_top: number; y_r_bot: number }): string {
    const x1 = LEFT_X + COL_W;
    const x2 = RIGHT_X;
    const cxa = x1 + (x2 - x1) * 0.5;
    return [
      `M ${x1} ${r.y_l_top}`,
      `C ${cxa} ${r.y_l_top}, ${cxa} ${r.y_r_top}, ${x2} ${r.y_r_top}`,
      `L ${x2} ${r.y_r_bot}`,
      `C ${cxa} ${r.y_r_bot}, ${cxa} ${r.y_l_bot}, ${x1} ${r.y_l_bot}`,
      "Z",
    ].join(" ");
  }

  let hover_idx = $state<number | null>(null);
</script>

{#if diff.losers.length === 0 || diff.gainers.length === 0}
  <p class="text-xs text-slate-500 italic p-4 text-center">
    No vote flow detected — apply a swing or threshold mutation to see party-to-party movement.
  </p>
{:else}
  <svg viewBox="0 0 {W} {H}" class="w-full h-auto" role="img" aria-label="Party-to-party vote flow">
    <!-- Ribbons (drawn first so column blocks sit on top) -->
    {#each ribbons as r, i (i)}
      <path
        d={ribbon_path(r)}
        fill={r.color}
        opacity={hover_idx === null ? 0.35 : hover_idx === i ? 0.75 : 0.15}
        role="img" aria-label={`${r.from} to ${r.to}: ${Math.round(r.flow)} votes`}
        onmouseenter={() => (hover_idx = i)}
        onmouseleave={() => (hover_idx = null)}
      >
        <title>{r.from} → {r.to}: {Math.round(r.flow).toLocaleString()} votes</title>
      </path>
    {/each}

    <!-- Loser column -->
    {#each diff.losers as n, i (n.party_eci_code)}
      <rect x={LEFT_X} y={left_pos[i].y} width={COL_W} height={Math.max(1, left_pos[i].h)} fill={n.color} />
      <text
        x={LEFT_X - 6} y={left_pos[i].y + left_pos[i].h / 2}
        text-anchor="end" dominant-baseline="middle" font-size="11" fill="#0f172a"
      >{n.party_short}</text>
      <text
        x={LEFT_X - 6} y={left_pos[i].y + left_pos[i].h / 2 + 12}
        text-anchor="end" dominant-baseline="middle" font-size="9" fill="#64748b"
      >−{Math.round(n.delta).toLocaleString()}</text>
    {/each}

    <!-- Gainer column -->
    {#each diff.gainers as n, i (n.party_eci_code)}
      <rect x={RIGHT_X} y={right_pos[i].y} width={COL_W} height={Math.max(1, right_pos[i].h)} fill={n.color} />
      <text
        x={RIGHT_X + COL_W + 6} y={right_pos[i].y + right_pos[i].h / 2}
        text-anchor="start" dominant-baseline="middle" font-size="11" fill="#0f172a"
      >{n.party_short}</text>
      <text
        x={RIGHT_X + COL_W + 6} y={right_pos[i].y + right_pos[i].h / 2 + 12}
        text-anchor="start" dominant-baseline="middle" font-size="9" fill="#10b981"
      >+{Math.round(n.delta).toLocaleString()}</text>
    {/each}
  </svg>
  <p class="text-[10px] text-slate-400 text-center mt-1">
    Approximate flow: each loser's drop redistributed to gainers in proportion to their share of total gain.
  </p>
{/if}

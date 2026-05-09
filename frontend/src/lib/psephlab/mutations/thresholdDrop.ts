// Threshold drop: eliminate every candidate whose AC vote share is below
// `threshold_pct`, then redistribute their freed votes to the surviving
// (non-NOTA) candidates proportionally to the survivors' pre-drop share
// within the same AC.
//
// Conserves per-AC vote totals. NOTA is never dropped (it represents
// abstention rather than a candidate) and never receives redistributed
// votes (those redistribution rules treat NOTA as if it weren't there).
//
// Useful for "what if the bottom-feeders never stood?" scenarios.

import type { MutationPlugin, ThresholdDropConfig, Tallies } from "../types";

export const thresholdDrop: MutationPlugin<ThresholdDropConfig> = {
  id: "thresholdDrop",
  label: "Threshold drop",

  apply(tallies: Tallies, cfg: ThresholdDropConfig): Tallies {
    if (cfg.threshold_pct <= 0) return tallies;
    const frac = cfg.threshold_pct / 100;

    const acs = tallies.acs.map(ac => {
      const total = ac.candidates.reduce((s, c) => s + c.votes, 0);
      if (total === 0) return ac;

      const drop_idx = new Set<number>();
      let freed = 0;
      ac.candidates.forEach((c, i) => {
        if (c.party_eci_code === "NOTA") return; // NOTA exempt
        if (c.votes / total < frac) {
          drop_idx.add(i);
          freed += c.votes;
        }
      });
      if (drop_idx.size === 0) return ac;

      // Survivor pool for the redistribution denominator: non-NOTA, non-dropped.
      const survivor_idx: number[] = [];
      let survivor_total = 0;
      ac.candidates.forEach((c, i) => {
        if (drop_idx.has(i) || c.party_eci_code === "NOTA") return;
        survivor_idx.push(i);
        survivor_total += c.votes;
      });
      if (survivor_idx.length === 0) return ac; // Pathological — leave AC alone

      // Build new candidate list. Dropped → 0 votes; survivors gain
      // proportional share. Use Math.round + remainder rebalancing so the
      // AC total is exactly preserved.
      const gains = new Map<number, number>();
      let assigned = 0;
      for (const i of survivor_idx) {
        const g =
          survivor_total === 0
            ? Math.floor(freed / survivor_idx.length)
            : Math.round((ac.candidates[i].votes / survivor_total) * freed);
        gains.set(i, g);
        assigned += g;
      }
      // Push the rounding drift onto the largest survivor so totals line up.
      const drift = freed - assigned;
      if (drift !== 0) {
        const top = survivor_idx
          .slice()
          .sort((a, b) => ac.candidates[b].votes - ac.candidates[a].votes)[0];
        gains.set(top, (gains.get(top) ?? 0) + drift);
      }

      const candidates = ac.candidates.map((c, i) => {
        if (drop_idx.has(i)) return { ...c, votes: 0 };
        const g = gains.get(i) ?? 0;
        if (g === 0) return c;
        return { ...c, votes: c.votes + g };
      });
      return { ...ac, candidates };
    });

    return { ...tallies, acs };
  },

  defaultConfig(): ThresholdDropConfig {
    return { id: "thresholdDrop", threshold_pct: 5 };
  },
};

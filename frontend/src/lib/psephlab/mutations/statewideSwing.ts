// Statewide swing: shift `pct` percent of each source party's votes into a
// single destination party, applied per-AC. Many-to-one is the general
// shape; classic 1→1 is just a single-element `from_party_eci_codes`.
//
// Conserves total votes per AC: the moved chunk stays inside the same AC,
// just changes whose pile it sits in. In ACs where the destination party
// is missing, the mutation no-ops for that AC (no synthesised candidate).
// Sources missing from a particular AC simply contribute 0 there.
//
// Deliberately *proportional to each source's per-AC share*, not a flat
// percentage of total turnout: a 3% swing means "3% of party-A's voters
// defected", which is what strategists mean colloquially.

import type { MutationPlugin, StatewideSwingConfig, Tallies } from "../types";

/** Back-compat: accept legacy `from_party_eci_code: string` URLs. */
function source_codes(cfg: StatewideSwingConfig): string[] {
  if (cfg.from_party_eci_codes && cfg.from_party_eci_codes.length > 0) {
    return cfg.from_party_eci_codes;
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const legacy = (cfg as any).from_party_eci_code;
  return legacy ? [legacy] : [];
}

export const statewideSwing: MutationPlugin<StatewideSwingConfig> = {
  id: "statewideSwing",
  label: "Statewide swing",
  summary: "Per AC, move K% of each source party's votes to a single destination party. Single-target — other parties are untouched. No-op in ACs where the destination didn't contest.",
  docs_anchor: "how-statewide-swing-works",

  apply(tallies: Tallies, cfg: StatewideSwingConfig): Tallies {
    if (cfg.pct <= 0) return tallies;
    const sources = source_codes(cfg).filter(c => c !== cfg.to_party_eci_code);
    if (sources.length === 0) return tallies;
    const frac = cfg.pct / 100;
    const src_set = new Set(sources);

    const acs = tallies.acs.map(ac => {
      const to = ac.candidates.findIndex(c => c.party_eci_code === cfg.to_party_eci_code);
      if (to < 0) return ac;

      // Compute moves out of every source candidate present in this AC.
      const moves = new Map<number, number>();
      let total_moved = 0;
      for (let i = 0; i < ac.candidates.length; i++) {
        if (i === to) continue;
        if (!src_set.has(ac.candidates[i].party_eci_code)) continue;
        const m = Math.round(ac.candidates[i].votes * frac);
        if (m > 0) {
          moves.set(i, m);
          total_moved += m;
        }
      }
      if (total_moved === 0) return ac;

      const candidates = ac.candidates.map((c, i) => {
        const out = moves.get(i);
        if (out !== undefined) return { ...c, votes: c.votes - out };
        if (i === to) return { ...c, votes: c.votes + total_moved };
        return c;
      });
      return { ...ac, candidates };
    });

    return { ...tallies, acs };
  },

  defaultConfig(tallies: Tallies): StatewideSwingConfig {
    // Pick the two top parties by aggregate votes as the default swap.
    const totals = new Map<string, number>();
    for (const ac of tallies.acs) {
      for (const c of ac.candidates) {
        if (c.party_eci_code === "NOTA") continue;
        totals.set(c.party_eci_code, (totals.get(c.party_eci_code) ?? 0) + c.votes);
      }
    }
    const sorted = [...totals.entries()].sort((a, b) => b[1] - a[1]);
    return {
      id: "statewideSwing",
      from_party_eci_codes: sorted[0]?.[0] ? [sorted[0][0]] : [],
      to_party_eci_code: sorted[1]?.[0] ?? "",
      pct: 0,
    };
  },
};

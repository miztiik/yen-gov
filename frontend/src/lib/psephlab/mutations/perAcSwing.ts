// Per-AC manual swing: move a pool of votes from one or more source
// candidates to a single destination candidate within one AC.
//
// Many-to-one is the general shape; classic 1→1 is just a single-element
// `from_party_eci_codes`. The engine pulls the requested `votes` from the
// pool of source candidates' available votes; each source contributes
// proportionally to its share of the pool, clamped so no candidate ever
// goes negative.

import type { AcTally, MutationPlugin, PerAcSwingConfig, Tallies } from "../types";

function find_idx(ac: AcTally, party: string, name?: string): number {
  if (name) {
    const i = ac.candidates.findIndex(
      c => c.party_eci_code === party && c.name === name,
    );
    if (i >= 0) return i;
  }
  return ac.candidates.findIndex(c => c.party_eci_code === party);
}

/** Back-compat: accept legacy `from_party_eci_code: string` URLs. */
function source_codes(cfg: PerAcSwingConfig): string[] {
  if (cfg.from_party_eci_codes && cfg.from_party_eci_codes.length > 0) {
    return cfg.from_party_eci_codes;
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const legacy = (cfg as any).from_party_eci_code;
  return legacy ? [legacy] : [];
}

export const perAcSwing: MutationPlugin<PerAcSwingConfig> = {
  id: "perAcSwing",
  label: "Per-AC vote swing",

  apply(tallies: Tallies, cfg: PerAcSwingConfig): Tallies {
    if (cfg.votes <= 0) return tallies;
    const sources = source_codes(cfg).filter(c => c !== cfg.to_party_eci_code);
    if (sources.length === 0) return tallies;

    const acs = tallies.acs.map(ac => {
      if (ac.eci_no !== cfg.eci_no) return ac;
      const to = find_idx(ac, cfg.to_party_eci_code, cfg.to_candidate_name);
      if (to < 0) return ac;

      // Resolve sources present in this AC; capacity = current votes.
      const src = sources
        .map(p => ({ idx: find_idx(ac, p) }))
        .filter(s => s.idx >= 0)
        .map(s => ({ idx: s.idx, votes: ac.candidates[s.idx].votes }));
      const pool = src.reduce((s, x) => s + x.votes, 0);
      if (pool === 0) return ac;

      const target = Math.min(cfg.votes, pool);
      // Proportional pull, with rounding drift absorbed by the largest source.
      const moves = src.map(s => Math.floor((s.votes / pool) * target));
      const drift = target - moves.reduce((s, x) => s + x, 0);
      if (drift > 0) {
        const big = moves.indexOf(Math.max(...moves));
        moves[big] += drift;
      }
      for (let i = 0; i < src.length; i++) {
        moves[i] = Math.min(moves[i], src[i].votes);
      }
      const total_moved = moves.reduce((s, x) => s + x, 0);
      if (total_moved === 0) return ac;

      const move_by_idx = new Map(src.map((s, i) => [s.idx, moves[i]]));
      const candidates = ac.candidates.map((c, i) => {
        const out = move_by_idx.get(i);
        if (out !== undefined) return { ...c, votes: c.votes - out };
        if (i === to) return { ...c, votes: c.votes + total_moved };
        return c;
      });
      return { ...ac, candidates };
    });

    return { ...tallies, acs };
  },

  defaultConfig(tallies: Tallies): PerAcSwingConfig {
    const ac = tallies.acs[0];
    const top_two = (ac?.candidates ?? []).slice().sort((a, b) => b.votes - a.votes);
    return {
      id: "perAcSwing",
      eci_no: ac?.eci_no ?? 1,
      from_party_eci_codes: top_two[0]?.party_eci_code ? [top_two[0].party_eci_code] : [],
      to_party_eci_code: top_two[1]?.party_eci_code ?? "",
      votes: 0,
    };
  },
};

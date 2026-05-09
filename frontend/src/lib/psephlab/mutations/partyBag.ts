// Ad-hoc party bag: treat a set of parties as one bloc. Per AC, every
// member-party candidate's votes pool into one synthetic candidate
// (`party_eci_code = "bag:<name>"`, `name = "<bag name>"`). The original
// member candidates are removed from that AC.
//
// Why a synthetic ECI code: keeps the rest of the engine party-agnostic.
// The counting rule sees a bag as just another party. The UI maps
// `bag:<name>` to the bag's color (or a hashed default).
//
// Why scenario-local: alliances change between elections, mid-cycle, and
// even between two strategists comparing notes. Encoding bags as
// dataset-level reference data would create a contract surface that needs
// version-bumps for every news event (psephlab.md > "Why mutations are
// scenario-local").

import type { MutationPlugin, PartyBagConfig, Tallies } from "../types";

export function bagCode(name: string): string {
  return `bag:${name}`;
}

export const partyBag: MutationPlugin<PartyBagConfig> = {
  id: "partyBag",
  label: "Ad-hoc party bag",

  apply(tallies: Tallies, cfg: PartyBagConfig): Tallies {
    if (!cfg.name || cfg.members.length === 0) return tallies;
    const member_set = new Set(cfg.members);
    const code = bagCode(cfg.name);

    const acs = tallies.acs.map(ac => {
      let pooled = 0;
      const member_names: string[] = [];
      const non_members = ac.candidates.filter(c => {
        if (!member_set.has(c.party_eci_code)) return true;
        pooled += c.votes;
        member_names.push(c.name);
        return false;
      });
      if (member_names.length === 0) return ac;

      // The bag's "candidate" stand-in. Name lists the underlying
      // candidates so the per-AC drilldown is still legible.
      const bag = {
        party_eci_code: code,
        party_short: cfg.name,
        name: member_names.length === 1 ? member_names[0] : `${cfg.name} (${member_names.length})`,
        votes: pooled,
      };
      return { ...ac, candidates: [...non_members, bag] };
    });

    return { ...tallies, acs };
  },

  defaultConfig(): PartyBagConfig {
    return { id: "partyBag", name: "Bag", members: [] };
  },
};

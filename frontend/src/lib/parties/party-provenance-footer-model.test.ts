// Row C unit test for the pure party-page provenance footer projector.
//
// Pins `buildProvenanceFooterClauses` (vitest, node env - no DOM): the
// Jony mapped-sentence grouping, the cross-card dedupe, the Holy-Law-#9
// exhaustiveness (every publisher in any card is covered, none dropped),
// empty-clause omission, and the "no fabricated link for a url-less
// pill" rule.

import { describe, expect, it } from "vitest";
import {
  buildProvenanceFooterClauses,
  FOOTER_CLAUSE_LABELS,
} from "./party-provenance-footer-model";
import type { PublisherPill } from "../sources";
import type { PartyProvenance } from "../view-models/party-sources";

function pill(
  label: string,
  vintage_summary: string,
  url: string | null,
  count = 1,
): PublisherPill {
  return { label, vintage_summary, url, count };
}

const ECI_URL = "https://eci.gov.in";
const WIKI_URL = "https://en.wikipedia.org/wiki/Communist_Party_of_India";

// A CPI-like provenance: the official ECI series cites the four data
// cards (different vintage windows per card), and a Wikipedia row cites
// the community-sourced alliance card.
function cpiProvenance(): PartyProvenance {
  return {
    pills_per_card: {
      parliament: [pill("ECI", "1999 to 2024", ECI_URL)],
      state_assembly: [pill("ECI", "2008 to 2026", ECI_URL)],
      strongholds: [pill("ECI", "1999 to 2024", ECI_URL)],
      current_strength: [pill("ECI", "2024", ECI_URL)],
      alliance_context: [pill("Wikipedia", "2025", WIKI_URL)],
    },
  };
}

/** All distinct publisher labels present anywhere in the input - the
 *  oracle the clause union MUST equal (Holy Law #9 exhaustiveness). */
function allInputLabels(p: PartyProvenance): Set<string> {
  const s = new Set<string>();
  for (const card of Object.values(p.pills_per_card)) {
    for (const pl of card) s.add(pl.label);
  }
  return s;
}

/** Union of every label across the produced clauses. */
function coveredLabels(
  clauses: { pills: readonly PublisherPill[] }[],
): Set<string> {
  const s = new Set<string>();
  for (const c of clauses) for (const pl of c.pills) s.add(pl.label);
  return s;
}

describe("buildProvenanceFooterClauses", () => {
  it("emits exactly 2 clauses with Jony's mapped labels for a CPI-like party", () => {
    const clauses = buildProvenanceFooterClauses(cpiProvenance());
    expect(clauses).toHaveLength(2);
    expect(clauses[0]!.label).toBe(FOOTER_CLAUSE_LABELS.data);
    expect(clauses[0]!.label).toBe("Seats, vote-share and strongholds");
    expect(clauses[1]!.label).toBe(FOOTER_CLAUSE_LABELS.alliance);
    expect(clauses[1]!.label).toBe("Alliance line-ups");
  });

  it("clause A dedupes the ECI pill across the four data cards into ONE (url preserved)", () => {
    const dataClause = buildProvenanceFooterClauses(cpiProvenance())[0]!;
    expect(dataClause.pills).toHaveLength(1);
    expect(dataClause.pills[0]!.label).toBe("ECI");
    expect(dataClause.pills[0]!.url).toBe(ECI_URL);
  });

  it("clause B carries the Wikipedia pill (community source, distinct from ECI)", () => {
    const allianceClause = buildProvenanceFooterClauses(cpiProvenance())[1]!;
    expect(allianceClause.pills).toHaveLength(1);
    expect(allianceClause.pills[0]!.label).toBe("Wikipedia");
    expect(allianceClause.pills[0]!.url).toBe(WIKI_URL);
  });

  it("the union of clause pills covers EVERY publisher in the input (Holy Law #9 exhaustiveness)", () => {
    const prov = cpiProvenance();
    const clauses = buildProvenanceFooterClauses(prov);
    expect(coveredLabels(clauses)).toEqual(allInputLabels(prov));
    // Explicit: both the official ECI and community Wikipedia survive.
    expect(coveredLabels(clauses)).toEqual(new Set(["ECI", "Wikipedia"]));
  });

  it("a multi-publisher data card keeps both publishers (no publisher dropped)", () => {
    const prov = cpiProvenance();
    prov.pills_per_card.current_strength = [
      pill("ECI", "2024", ECI_URL),
      pill("Lok Sabha Secretariat", "2024", "https://sansad.in"),
    ];
    const clauses = buildProvenanceFooterClauses(prov);
    expect(coveredLabels(clauses)).toEqual(
      new Set(["ECI", "Lok Sabha Secretariat", "Wikipedia"]),
    );
    expect(clauses[0]!.pills.map((p) => p.label)).toEqual([
      "ECI",
      "Lok Sabha Secretariat",
    ]);
  });

  it("omits the alliance clause when the alliance card has no pills (only clause A renders)", () => {
    const prov = cpiProvenance();
    prov.pills_per_card.alliance_context = [];
    const clauses = buildProvenanceFooterClauses(prov);
    expect(clauses).toHaveLength(1);
    expect(clauses[0]!.label).toBe(FOOTER_CLAUSE_LABELS.data);
    // Exhaustiveness still holds against the reduced input.
    expect(coveredLabels(clauses)).toEqual(allInputLabels(prov));
  });

  it("returns zero clauses when every card is empty (sentinel party - footer sentence self-suppresses)", () => {
    const empty: PartyProvenance = {
      pills_per_card: {
        parliament: [],
        state_assembly: [],
        strongholds: [],
        current_strength: [],
        alliance_context: [],
      },
    };
    expect(buildProvenanceFooterClauses(empty)).toEqual([]);
  });

  it("keeps a url-less pill as url:null (renders plain text, no fabricated link)", () => {
    const prov: PartyProvenance = {
      pills_per_card: {
        parliament: [pill("ECI", "2024", null)],
        state_assembly: [],
        strongholds: [],
        current_strength: [],
        alliance_context: [],
      },
    };
    const clauses = buildProvenanceFooterClauses(prov);
    expect(clauses).toHaveLength(1);
    expect(clauses[0]!.pills[0]!.url).toBeNull();
  });

  it("on merge keeps the FIRST non-null url across cards (a url-less first card does not blank the link)", () => {
    const prov: PartyProvenance = {
      pills_per_card: {
        parliament: [pill("ECI", "2024", null)], // first seen: no url
        state_assembly: [pill("ECI", "2026", ECI_URL)], // later: has url
        strongholds: [],
        current_strength: [],
        alliance_context: [],
      },
    };
    const dataClause = buildProvenanceFooterClauses(prov)[0]!;
    expect(dataClause.pills).toHaveLength(1);
    expect(dataClause.pills[0]!.url).toBe(ECI_URL);
  });

  it("preserves a representative vintage_summary (first non-empty) on merge", () => {
    const prov: PartyProvenance = {
      pills_per_card: {
        parliament: [pill("ECI", "", ECI_URL)], // first: empty vintage
        state_assembly: [pill("ECI", "2008 to 2026", ECI_URL)],
        strongholds: [],
        current_strength: [],
        alliance_context: [],
      },
    };
    const dataClause = buildProvenanceFooterClauses(prov)[0]!;
    expect(dataClause.pills[0]!.vintage_summary).toBe("2008 to 2026");
  });
});

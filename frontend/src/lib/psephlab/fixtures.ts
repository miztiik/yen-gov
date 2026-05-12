import type { Tallies } from "./types";

/**
 * Tiny hand-built Tallies fixture for psephlab unit tests. 3 ACs, 3 parties
 * (DMK, AIADMK, BJP) plus NOTA. Vote totals are deliberately small and
 * round so arithmetic in tests can be checked by hand.
 *
 * AC layouts:
 *   AC 1: DMK 600, AIADMK 300, BJP 90, NOTA 10           total 1000
 *   AC 2: AIADMK 700, DMK 200, BJP 90, NOTA 10           total 1000
 *   AC 3: DMK 500, AIADMK 480, NOTA 20                   total 1000
 *
 * Under FPTP (no mutations): DMK wins AC1 + AC3 (2 seats); AIADMK wins
 * AC2 (1 seat). Votes total 3000.
 */
export const FIXTURE: Tallies = {
  scope: { country: "IN", state: "S22", election: "AcGenMay2026" },
  acs: [
    {
      eci_no: 1,
      name: "Alpha",
      electorate: 1200,
      candidates: [
        { party_eci_code: "DMK",    party_short: "DMK",    name: "A1", votes: 600 },
        { party_eci_code: "AIADMK", party_short: "AIADMK", name: "A2", votes: 300 },
        { party_eci_code: "BJP",    party_short: "BJP",    name: "A3", votes: 90 },
        { party_eci_code: "NOTA",   party_short: "NOTA",   name: "NOTA", votes: 10 },
      ],
    },
    {
      eci_no: 2,
      name: "Bravo",
      electorate: 1200,
      candidates: [
        { party_eci_code: "AIADMK", party_short: "AIADMK", name: "B1", votes: 700 },
        { party_eci_code: "DMK",    party_short: "DMK",    name: "B2", votes: 200 },
        { party_eci_code: "BJP",    party_short: "BJP",    name: "B3", votes: 90 },
        { party_eci_code: "NOTA",   party_short: "NOTA",   name: "NOTA", votes: 10 },
      ],
    },
    {
      eci_no: 3,
      name: "Charlie",
      electorate: 1200,
      candidates: [
        { party_eci_code: "DMK",    party_short: "DMK",    name: "C1", votes: 500 },
        { party_eci_code: "AIADMK", party_short: "AIADMK", name: "C2", votes: 480 },
        { party_eci_code: "NOTA",   party_short: "NOTA",   name: "NOTA", votes: 20 },
      ],
    },
  ],
};

/** Sum of votes across an AC's candidates. */
export function acTotal(ac: Tallies["acs"][number]): number {
  return ac.candidates.reduce((s, c) => s + c.votes, 0);
}

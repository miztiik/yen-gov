// Unit tests for instantRunoff rule (E6).
//
// Pins: per-AC IRV with uniform transfer + NOTA fallback + E5
// invariant + caveat/assumptions/requires_banner metadata.

import { describe, it, expect } from "vitest";
import { instantRunoff } from "./instantRunoff";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("instantRunoff — IRV with uniform transfer", () => {
  it("FIXTURE result: one winner per AC; seats sum to AC count", () => {
    const r = instantRunoff.apply(FIXTURE);
    expect(r.by_ac).toHaveLength(3);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(3);
  });

  it("preserves majority winner when one candidate has > 50% first-prefs", () => {
    // AC with DMK 60%, AIADMK 25%, BJP 15% -> DMK wins in round 1.
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "D1", votes: 600, party_id: "parties.IN.DMK" },
          { party_eci_code: "AIADMK", party_short: "AIADMK", name: "A1", votes: 250, party_id: "parties.IN.AIADMK" },
          { party_eci_code: "BJP", party_short: "BJP", name: "B1", votes: 150, party_id: "parties.IN.BJP" },
        ]),
      ],
    };
    const r = instantRunoff.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("DMK");
  });

  it("eliminates lowest-vote candidate and redistributes proportionally", () => {
    // AC with DMK 400, AIADMK 350, BJP 250.
    // No majority. BJP eliminated.
    // BJP's 250 transfers proportional to DMK:AIADMK = 400:350 = 8:7 ->
    //   DMK gets 250 * 400/750 ~= 133.33
    //   AIADMK gets 250 * 350/750 ~= 116.67
    // After transfer: DMK ~= 533.33, AIADMK ~= 466.67 -> DMK > 50% -> DMK wins.
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "D", votes: 400, party_id: "parties.IN.DMK" },
          { party_eci_code: "AIADMK", party_short: "AIADMK", name: "A", votes: 350, party_id: "parties.IN.AIADMK" },
          { party_eci_code: "BJP", party_short: "BJP", name: "B", votes: 250, party_id: "parties.IN.BJP" },
        ]),
      ],
    };
    const r = instantRunoff.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("DMK");
  });

  it("never eliminates NOTA, even when NOTA is the lowest", () => {
    // AC with DMK 400, AIADMK 350, BJP 200, NOTA 50.
    // NOTA is lowest but NOT eliminated. BJP (lowest non-NOTA) goes.
    // BJP's 200 transfers proportional to DMK:AIADMK = 400:350.
    //   DMK gets ~106.67, AIADMK gets ~93.33.
    // After: DMK ~= 506.67, AIADMK ~= 443.33, NOTA 50.
    // Non-NOTA total = 950. DMK 506.67 / 950 > 50% -> DMK wins.
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "D", votes: 400, party_id: "parties.IN.DMK" },
          { party_eci_code: "AIADMK", party_short: "AIADMK", name: "A", votes: 350, party_id: "parties.IN.AIADMK" },
          { party_eci_code: "BJP", party_short: "BJP", name: "B", votes: 200, party_id: "parties.IN.BJP" },
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 50, party_id: "parties.IN.NOTA" },
        ]),
      ],
    };
    const r = instantRunoff.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("DMK");
    const nota_seats = r.by_party.find((p) => p.party_eci_code === "NOTA")?.seats_won ?? 0;
    expect(nota_seats).toBe(0);
  });

  it("handles single non-NOTA candidate (uncontested)", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "D", votes: 100, party_id: "parties.IN.DMK" },
        ]),
      ],
    };
    const r = instantRunoff.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("DMK");
    expect(r.by_party.find((p) => p.party_eci_code === "DMK")?.seats_won).toBe(1);
  });

  it("handles an empty tally without throwing", () => {
    const r = instantRunoff.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_ac).toEqual([]);
    expect(r.by_party).toEqual([]);
    expect(r.total_votes).toBe(0);
  });

  it("is deterministic across repeated invocations", () => {
    const a = instantRunoff.apply(FIXTURE);
    const b = instantRunoff.apply(FIXTURE);
    expect(a.by_ac.map((o) => o.winner.party_eci_code)).toEqual(
      b.by_ac.map((o) => o.winner.party_eci_code),
    );
  });

  it("exposes caveat + assumptions + requires_banner metadata", () => {
    expect(instantRunoff.requires_banner).toBe(true);
    expect(instantRunoff.caveat ?? "").not.toBe("");
    expect(instantRunoff.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("caveat + assumptions are ASCII-only", () => {
    const allText = [
      instantRunoff.caveat ?? "",
      ...(instantRunoff.assumptions ?? []),
      instantRunoff.label,
    ].join("\n");
    expect(Array.from(allText).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});

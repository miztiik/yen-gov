// Unit tests for the method-preview helpers.
//
// Pure-helper tests only per repo doctrine (no jsdom; no
// @testing-library/svelte). The drawer's preview rendering is
// covered by the existing psephlab-smoke Playwright spec.

import { describe, expect, it } from "vitest";
import {
  PREVIEW_TOP_N,
  buildMethodPreviews,
  buildPreview,
  formatChamberSuffix,
  formatPreviewLine,
  type PreviewInfo,
} from "./method-preview";
import { fptp } from "./rules/fptp";
import { sainteLague } from "./rules/sainteLague";
import { mmp } from "./rules/mmp";
import { approval } from "./rules/approval";
import { condorcetProxy } from "./rules/condorcetProxy";
import { RULES } from "./rules";
import { FIXTURE } from "./fixtures";
import type { CandidateTally, SeatAllocation, Tallies } from "./types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("buildPreview - top filtering", () => {
  it("returns top 3 parties by seats_won, dropping zero-seat parties", () => {
    const allocation: SeatAllocation = {
      by_party: [
        { party_eci_code: "A", party_short: "A", seats_won: 5, votes: 500, vote_share_pct: 50, party_id: "parties.IN.A", brand_colour_hex: "#aa0000", brand_colour_confidence: "high", election_symbol_asset_path: null },
        { party_eci_code: "B", party_short: "B", seats_won: 3, votes: 300, vote_share_pct: 30, party_id: "parties.IN.B", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
        { party_eci_code: "C", party_short: "C", seats_won: 2, votes: 200, vote_share_pct: 20, party_id: "parties.IN.C", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
        { party_eci_code: "D", party_short: "D", seats_won: 0, votes: 100, vote_share_pct: 10, party_id: "parties.IN.D", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
      ],
      by_ac: [],
      total_votes: 1100,
    };
    const out = buildPreview(allocation, 10);
    expect(out.top).toHaveLength(3);
    expect(out.top.map((p) => p.party_short)).toEqual(["A", "B", "C"]);
    expect(out.top.map((p) => p.seats)).toEqual([5, 3, 2]);
  });

  it("returns empty top when every party has 0 seats", () => {
    const allocation: SeatAllocation = {
      by_party: [
        { party_eci_code: "A", party_short: "A", seats_won: 0, votes: 500, vote_share_pct: 100, party_id: "parties.IN.A", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
      ],
      by_ac: [],
      total_votes: 500,
    };
    const out = buildPreview(allocation, 1);
    expect(out.top).toEqual([]);
    expect(out.chamber).toBe(1);
  });

  it("threads brand_colour_hex + party_id through to PreviewItem", () => {
    const allocation: SeatAllocation = {
      by_party: [
        { party_eci_code: "A", party_short: "A", seats_won: 1, votes: 100, vote_share_pct: 100, party_id: "parties.IN.A", brand_colour_hex: "#1234ab", brand_colour_confidence: "high", election_symbol_asset_path: null },
      ],
      by_ac: [],
      total_votes: 100,
    };
    const out = buildPreview(allocation, 1);
    expect(out.top[0].party_id).toBe("parties.IN.A");
    expect(out.top[0].hex).toBe("#1234ab");
  });

  it("uses the default top_n constant when omitted", () => {
    expect(PREVIEW_TOP_N).toBe(3);
  });

  it("respects an explicit top_n override (cap less than 3)", () => {
    const allocation: SeatAllocation = {
      by_party: [
        { party_eci_code: "A", party_short: "A", seats_won: 5, votes: 500, vote_share_pct: 50, party_id: "parties.IN.A", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
        { party_eci_code: "B", party_short: "B", seats_won: 3, votes: 300, vote_share_pct: 30, party_id: "parties.IN.B", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
        { party_eci_code: "C", party_short: "C", seats_won: 2, votes: 200, vote_share_pct: 20, party_id: "parties.IN.C", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
      ],
      by_ac: [],
      total_votes: 1000,
    };
    const out = buildPreview(allocation, 10, 2);
    expect(out.top.map((p) => p.party_short)).toEqual(["A", "B"]);
  });
});

describe("buildPreview - chamber resolution", () => {
  it("chamber == total_acs when allocation has no chamber_seats override", () => {
    const allocation: SeatAllocation = {
      by_party: [],
      by_ac: [],
      total_votes: 0,
    };
    const out = buildPreview(allocation, 234);
    expect(out.chamber).toBe(234);
  });

  it("chamber == allocation.chamber_seats when set (MMP-shape override)", () => {
    const allocation: SeatAllocation = {
      by_party: [
        { party_eci_code: "A", party_short: "A", seats_won: 100, votes: 500, vote_share_pct: 100, party_id: "parties.IN.A", brand_colour_hex: null, brand_colour_confidence: null, election_symbol_asset_path: null },
      ],
      by_ac: [],
      total_votes: 500,
      chamber_seats: 304,
    };
    const out = buildPreview(allocation, 234);
    expect(out.chamber).toBe(304);
  });
});

describe("buildMethodPreviews", () => {
  it("returns null when tallies is null (still loading)", () => {
    expect(buildMethodPreviews(null, RULES)).toBeNull();
  });

  it("returns one entry per rule keyed by rule.id", () => {
    const map = buildMethodPreviews(FIXTURE, RULES);
    expect(map).not.toBeNull();
    if (!map) return;
    for (const rule of RULES) {
      expect(map.has(rule.id), `missing preview for ${rule.id}`).toBe(true);
    }
  });

  it("FPTP, Approval, and Condorcet proxy produce IDENTICAL preview tops (mirror invariant)", () => {
    // Approval and Condorcet proxy delegate to FPTP by construction;
    // this test catches a future regression where someone forks the
    // delegation. The mirror IS the lesson in the Election Studio.
    const map = buildMethodPreviews(FIXTURE, [fptp, approval, condorcetProxy]);
    expect(map).not.toBeNull();
    if (!map) return;
    const fptp_top = map.get("fptp")!.top.map((p) => [p.party_short, p.seats]);
    const approval_top = map.get("approval")!.top.map((p) => [p.party_short, p.seats]);
    const condorcet_top = map.get("condorcet-proxy")!.top.map((p) => [p.party_short, p.seats]);
    expect(approval_top).toEqual(fptp_top);
    expect(condorcet_top).toEqual(fptp_top);
  });

  it("MMP carries chamber > constituency_seats on a multi-AC fixture with overhang", () => {
    // 10 ACs each with BJP 51 / INC 49: BJP wins all 10 FPTP seats
    // (overhang); INC gets list-tier compensation; chamber grows to
    // 16 (see mmp.test.ts).
    const acs: Tallies["acs"] = [];
    for (let i = 1; i <= 10; i++) {
      acs.push(
        makeAc(i, [
          { party_eci_code: "BJP", party_short: "BJP", name: `B${i}`, votes: 51, party_id: "parties.IN.BJP" },
          { party_eci_code: "INC", party_short: "INC", name: `I${i}`, votes: 49, party_id: "parties.IN.INC" },
        ]),
      );
    }
    const tallies: Tallies = { scope: FIXTURE.scope, acs };
    const map = buildMethodPreviews(tallies, [mmp]);
    expect(map).not.toBeNull();
    if (!map) return;
    const preview = map.get("mmp")!;
    expect(preview.chamber).toBe(16);
    expect(preview.chamber).toBeGreaterThan(tallies.acs.length);
  });

  it("non-MMP rules carry chamber == constituency_seats", () => {
    const map = buildMethodPreviews(FIXTURE, [fptp, sainteLague]);
    expect(map).not.toBeNull();
    if (!map) return;
    expect(map.get("fptp")!.chamber).toBe(FIXTURE.acs.length);
    expect(map.get("proportional")!.chamber).toBe(FIXTURE.acs.length);
  });

  it("is deterministic across repeated invocations on the same input", () => {
    const a = buildMethodPreviews(FIXTURE, RULES);
    const b = buildMethodPreviews(FIXTURE, RULES);
    expect(a).not.toBeNull();
    expect(b).not.toBeNull();
    if (!a || !b) return;
    for (const rule of RULES) {
      const a_top = a.get(rule.id)!.top.map((p) => [p.party_short, p.seats]);
      const b_top = b.get(rule.id)!.top.map((p) => [p.party_short, p.seats]);
      expect(a_top).toEqual(b_top);
    }
  });
});

describe("formatPreviewLine", () => {
  it("joins top parties with ' / ' separator", () => {
    const preview: PreviewInfo = {
      top: [
        { party_short: "DMK", party_id: "parties.IN.DMK", seats: 133, hex: null },
        { party_short: "AIADMK", party_id: "parties.IN.AIADMK", seats: 66, hex: null },
        { party_short: "INC", party_id: "parties.IN.INC", seats: 18, hex: null },
      ],
      chamber: 234,
    };
    expect(formatPreviewLine(preview)).toBe("DMK 133 / AIADMK 66 / INC 18");
  });

  it("returns the empty string for an empty preview", () => {
    const preview: PreviewInfo = { top: [], chamber: 234 };
    expect(formatPreviewLine(preview)).toBe("");
  });

  it("output is ASCII-only", () => {
    const preview: PreviewInfo = {
      top: [
        { party_short: "DMK", party_id: "parties.IN.DMK", seats: 133, hex: null },
        { party_short: "AIADMK", party_id: "parties.IN.AIADMK", seats: 66, hex: null },
      ],
      chamber: 234,
    };
    const text = formatPreviewLine(preview);
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});

describe("formatChamberSuffix", () => {
  it("returns empty string when chamber equals constituency_seats", () => {
    const preview: PreviewInfo = { top: [], chamber: 234 };
    expect(formatChamberSuffix(preview, 234)).toBe("");
  });

  it("returns ' (234 -> 304)' when chamber grows past constituency count (MMP overhang)", () => {
    const preview: PreviewInfo = { top: [], chamber: 304 };
    expect(formatChamberSuffix(preview, 234)).toBe(" (234 -> 304)");
  });

  it("uses ASCII '->' (not a Unicode arrow)", () => {
    const preview: PreviewInfo = { top: [], chamber: 16 };
    const out = formatChamberSuffix(preview, 10);
    expect(out).toContain("->");
    expect(Array.from(out).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});

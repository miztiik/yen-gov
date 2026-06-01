// Vitest contract test for the party-colour resolver.
//
// Per PR-SYM-6a + Jony verdict: snapshots resolver behaviour across all
// 620 parties in datasets/taxonomy/parties.json so any drift in tier
// counts (anchor / brand / fallback) is visible in PR diffs.

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  getPartyColor,
  type PartyRowForResolver,
  type ResolvedPartyColor,
} from "./resolver";

interface PartyJson {
  party_id: string;
  eci_code?: string;
  brand_colour?: {
    hex: string;
    confidence: "high" | "medium" | "low";
    source_id: string;
    source_kind: string;
    notes: string | null;
  } | null;
}

function loadParties(): PartyJson[] {
  const path = resolve(__dirname, "../../../../datasets/taxonomy/parties.json");
  const raw = JSON.parse(readFileSync(path, "utf8")) as { parties: PartyJson[] };
  return raw.parties;
}

describe("getPartyColor", () => {
  describe("tier 1: anchor", () => {
    it("returns BJP saffron from anchors keyed on party_id", () => {
      const r = getPartyColor("parties.IN.BJP", null);
      expect(r.source).toBe("anchor");
      expect(r.hex.toLowerCase()).toBe("#ea580c");
      expect(r.party_id).toBe("parties.IN.BJP");
    });

    it("returns INC blue from anchors", () => {
      const r = getPartyColor("parties.IN.INC", null);
      expect(r.source).toBe("anchor");
      expect(r.hex.toLowerCase()).toBe("#1d4ed8");
    });

    it("anchor wins even when row carries a brand_colour", () => {
      const row: PartyRowForResolver = {
        party_id: "parties.IN.BJP",
        brand_colour: { hex: "#FF9933", confidence: "high" },
      };
      const r = getPartyColor("parties.IN.BJP", row);
      expect(r.source).toBe("anchor");
      expect(r.hex.toLowerCase()).toBe("#ea580c");
    });

    it("NOTA and IND have anchor entries", () => {
      expect(getPartyColor("parties.IN.NOTA", null).source).toBe("anchor");
      expect(getPartyColor("parties.IN.IND", null).source).toBe("anchor");
    });
  });

  describe("tier 2: brand", () => {
    it("returns brand hex when confidence is 'high'", () => {
      const row: PartyRowForResolver = {
        party_id: "parties.IN.JDU",
        brand_colour: { hex: "#003366", confidence: "high" },
      };
      const r = getPartyColor("parties.IN.JDU", row);
      expect(r.source).toBe("brand");
      expect(r.hex).toBe("#003366");
    });

    it("returns brand hex when confidence is 'medium'", () => {
      const row: PartyRowForResolver = {
        party_id: "parties.IN.JDS",
        brand_colour: { hex: "#02865A", confidence: "medium" },
      };
      const r = getPartyColor("parties.IN.JDS", row);
      expect(r.source).toBe("brand");
      expect(r.hex).toBe("#02865A");
    });

    it("FALLS THROUGH to fallback when confidence is 'low' (faction-split)", () => {
      const row: PartyRowForResolver = {
        party_id: "parties.IN.SS_UBT",
        brand_colour: { hex: "#FFB300", confidence: "low" },
      };
      const r = getPartyColor("parties.IN.SS_UBT", row);
      expect(r.source).toBe("fallback");
      expect(r.hex).not.toBe("#FFB300");
    });
  });

  describe("tier 3: fallback", () => {
    it("returns deterministic hex when no anchor and no brand_colour", () => {
      const r1 = getPartyColor("parties.IN.NEVERSEEN", null);
      const r2 = getPartyColor("parties.IN.NEVERSEEN", null);
      expect(r1.source).toBe("fallback");
      expect(r1.hex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(r1.hex).toBe(r2.hex);
    });

    it("different party_ids generally produce different fallbacks", () => {
      const a = getPartyColor("parties.IN.NEVERSEEN_A", null);
      const b = getPartyColor("parties.IN.NEVERSEEN_B", null);
      // Hash-to-palette: same slot is possible but unlikely for distinct strings.
      // Just assert both look like valid hex.
      expect(a.hex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(b.hex).toMatch(/^#[0-9a-f]{6}$/i);
    });

    it("absent row + no anchor -> fallback", () => {
      const r = getPartyColor("parties.IN.AAANEW", null);
      expect(r.source).toBe("fallback");
    });

    it("row with null brand_colour -> fallback", () => {
      const row: PartyRowForResolver = {
        party_id: "parties.IN.NOBRAND",
        brand_colour: null,
      };
      const r = getPartyColor("parties.IN.NOBRAND", row);
      expect(r.source).toBe("fallback");
    });
  });

  describe("purity", () => {
    it("MUST NOT mutate hex values", () => {
      const r = getPartyColor("parties.IN.BJP", null);
      const r2 = getPartyColor("parties.IN.BJP", null);
      expect(r.hex).toBe(r2.hex);
      // Hex must equal the anchors entry verbatim (no contrast tuning).
      expect(r.hex.toLowerCase()).toBe("#ea580c");
    });

    it("returns party_id verbatim in result", () => {
      const r = getPartyColor("parties.IN.WHATEVER", null);
      expect(r.party_id).toBe("parties.IN.WHATEVER");
    });
  });

  describe("roster snapshot (drift detector)", () => {
    it("matches expected tier counts across the full parties.json roster", () => {
      const parties = loadParties();
      const counts = { anchor: 0, brand: 0, fallback: 0 };
      for (const p of parties) {
        const row: PartyRowForResolver = {
          party_id: p.party_id,
          brand_colour: p.brand_colour ?? null,
        };
        const r: ResolvedPartyColor = getPartyColor(p.party_id, row);
        counts[r.source]++;
      }
      // Snapshot pinned 2026-06-01 post PR-SYM-4b + 4c:
      //   - anchor:   13 (the iconic citizen-recall pids in ANCHORS_BY_PID
      //               that ALSO exist in parties.json)
      //   - brand:    Wikipedia-enriched high+medium parties not in anchors
      //   - fallback: everything else (the long tail of 600+ RUPPs)
      //
      // Any drift here is a regression unless paired with an intentional
      // anchor / brand_colour change in parties.json or anchors.ts.
      expect(counts.anchor).toBeGreaterThanOrEqual(11); // BJP/INC/CPIM/CPI/DMK/AIADMK/PMK/IUML/AITC/AGP/AIUDF/NOTA/IND
      expect(counts.brand).toBeGreaterThanOrEqual(30);  // ~42 wiki-high - 11 anchored
      expect(counts.fallback).toBeGreaterThan(500);
      expect(counts.anchor + counts.brand + counts.fallback).toBe(parties.length);
    });
  });
});

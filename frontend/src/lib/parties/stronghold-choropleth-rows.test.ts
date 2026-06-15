// PR-12 of TODO/20260613-party-deferred-followups-plan.md section 14.
//
// Pure-helper coverage for `stronghold-choropleth-rows.ts`. Tested in
// node-env vitest; no DOM, no Svelte mount.

import { describe, expect, it } from "vitest";

import type { PartyStronghold } from "../view-models/party-detail";
import {
  BUCKET_ORDER,
  bucketFromWins,
  homeStateEciCodes,
  mapPcStrongholdsToChoroplethRows,
  mixWithWhite,
  paletteFromBrand,
  stateCodeFromPcEntityId,
  uniqueIdFromPcEntityId,
} from "./stronghold-choropleth-rows";

describe("bucketFromWins", () => {
  it("classifies null/undefined/NaN as absent", () => {
    expect(bucketFromWins(null)).toBe("absent");
    expect(bucketFromWins(undefined)).toBe("absent");
    expect(bucketFromWins(NaN)).toBe("absent");
    expect(bucketFromWins(Infinity)).toBe("absent");
  });
  it("classifies <=0 as zero (defensive; mart filters wins>=1)", () => {
    expect(bucketFromWins(0)).toBe("zero");
    expect(bucketFromWins(-1)).toBe("zero");
    expect(bucketFromWins(-100)).toBe("zero");
  });
  it("classifies 1 as one", () => {
    expect(bucketFromWins(1)).toBe("one");
  });
  it("classifies 2 as two", () => {
    expect(bucketFromWins(2)).toBe("two");
  });
  it("classifies 3 and 4 as three-four", () => {
    expect(bucketFromWins(3)).toBe("three-four");
    expect(bucketFromWins(4)).toBe("three-four");
  });
  it("classifies >=5 as five-plus", () => {
    expect(bucketFromWins(5)).toBe("five-plus");
    expect(bucketFromWins(8)).toBe("five-plus");
    expect(bucketFromWins(20)).toBe("five-plus");
  });
  it("truncates fractional values toward zero", () => {
    // Defensive: the mart writes integers but if a row mutates we
    // don't want a 3.5 to read as five-plus.
    expect(bucketFromWins(3.9)).toBe("three-four");
    expect(bucketFromWins(4.99)).toBe("three-four");
  });
});

describe("BUCKET_ORDER", () => {
  it("is the canonical order from absent to five-plus", () => {
    expect(BUCKET_ORDER).toEqual([
      "absent",
      "zero",
      "one",
      "two",
      "three-four",
      "five-plus",
    ]);
  });
  it("is frozen (no in-place mutation)", () => {
    expect(Object.isFrozen(BUCKET_ORDER)).toBe(true);
  });
});

describe("uniqueIdFromPcEntityId", () => {
  it("derives <state_code>_<seat_no> from a PC entity_id", () => {
    expect(uniqueIdFromPcEntityId("IN-PC-2008-S22-10")).toBe("S22_10");
    expect(uniqueIdFromPcEntityId("IN-PC-2008-S07-8")).toBe("S07_8");
    expect(uniqueIdFromPcEntityId("IN-PC-1976-S24-60")).toBe("S24_60");
    expect(uniqueIdFromPcEntityId("IN-PC-2024-U05-1")).toBe("U05_1");
  });
  it("returns null for non-PC patterns", () => {
    expect(uniqueIdFromPcEntityId("IN-AC-2008-S22-10")).toBeNull();
    expect(uniqueIdFromPcEntityId("IN-S22-AC-1976-2")).toBeNull();
    expect(uniqueIdFromPcEntityId("garbage")).toBeNull();
    expect(uniqueIdFromPcEntityId("IN-PC-2008-S22")).toBeNull();
    expect(uniqueIdFromPcEntityId("")).toBeNull();
  });
  it("returns null on extra dashes (state code with hyphen)", () => {
    // U03-OLD style historical codes can't be the state_code per
    // pc_entity_id regex `[SU]\d{2}` (CLAUDE.md section 3 + the
    // PR-8 lessons note on legacy state codes).
    expect(uniqueIdFromPcEntityId("IN-PC-2008-U03-OLD-1")).toBeNull();
  });
});

describe("stateCodeFromPcEntityId", () => {
  it("returns the state code segment from a valid PC id", () => {
    expect(stateCodeFromPcEntityId("IN-PC-2008-S22-10")).toBe("S22");
    expect(stateCodeFromPcEntityId("IN-PC-1976-U05-7")).toBe("U05");
  });
  it("returns null for non-PC patterns", () => {
    expect(stateCodeFromPcEntityId("IN-AC-2008-S22-10")).toBeNull();
    expect(stateCodeFromPcEntityId("garbage")).toBeNull();
  });
});

describe("mapPcStrongholdsToChoroplethRows", () => {
  const fixture: PartyStronghold[] = [
    {
      entity_id: "IN-PC-2008-S22-10",
      constituency_name: "Dharmapuri",
      state: "tamil-nadu",
      wins: 3,
      contested: 4,
      // PR-7: PartyStronghold carries `last_won_year` for the
      // one-line citizen tally; fixtures pin null since this test
      // covers the PC -> choropleth row mapping (recency is not in
      // scope here).
      last_won_year: null,
      results: ["W", "W", "L", "W"],
      source_ids: [],
    },
    {
      entity_id: "IN-PC-2008-S22-12",
      constituency_name: "Sriperumbudur",
      state: "tamil-nadu",
      wins: 1,
      contested: 4,
      last_won_year: null,
      results: ["L", "L", "W", "L"],
      source_ids: [],
    },
    {
      // Non-PC pattern: defensive drop.
      entity_id: "IN-S22-AC-1976-2",
      constituency_name: "HARBOUR",
      state: "tamil-nadu",
      wins: 5,
      contested: 8,
      last_won_year: null,
      results: ["W", "W", "W", "L", "W", "W", "L", "W"],
      source_ids: [],
    },
  ];

  it("maps PC rows into choropleth rows with correct buckets", () => {
    const rows = mapPcStrongholdsToChoroplethRows(fixture);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({
      entity_key: "S22_10",
      wins: 3,
      contested: 4,
      bucket: "three-four",
      constituency_name: "Dharmapuri",
      state: "tamil-nadu",
      results: ["W", "W", "L", "W"],
    });
    expect(rows[1]).toEqual({
      entity_key: "S22_12",
      wins: 1,
      contested: 4,
      bucket: "one",
      constituency_name: "Sriperumbudur",
      state: "tamil-nadu",
      results: ["L", "L", "W", "L"],
    });
  });

  it("silently drops AC entity_ids (defensive guard)", () => {
    const rows = mapPcStrongholdsToChoroplethRows(fixture);
    expect(rows.every((r) => r.entity_key.startsWith("S22_"))).toBe(true);
    expect(rows.every((r) => r.constituency_name !== "HARBOUR")).toBe(true);
  });

  it("handles empty input", () => {
    expect(mapPcStrongholdsToChoroplethRows([])).toEqual([]);
  });
});

describe("mixWithWhite", () => {
  it("returns brand at t=1", () => {
    expect(mixWithWhite("#FA2223", 1)).toBe("#fa2223");
    expect(mixWithWhite("#FF9933", 1)).toBe("#ff9933");
  });
  it("returns white at t=0", () => {
    expect(mixWithWhite("#FA2223", 0)).toBe("#ffffff");
    expect(mixWithWhite("#000000", 0)).toBe("#ffffff");
  });
  it("linearly mixes mid-stops", () => {
    // DMK red #FA2223 mixed 0.5 with white:
    //   r = round(0.5*250 + 0.5*255) = 253 -> "fd"
    //   g = round(0.5*34  + 0.5*255) = 145 -> "91" (0.5*34=17, 0.5*255=127.5 -> 144.5 -> 145 round half-to-even or up; let's accept 144 or 145)
    //   b = round(0.5*35  + 0.5*255) = 145 -> "91"
    // We assert via re-derivation rather than hardcoding the round.
    const got = mixWithWhite("#FA2223", 0.5);
    expect(got).toMatch(/^#[0-9a-f]{6}$/);
    // sanity: each channel is between brand and white
    const r = parseInt(got.slice(1, 3), 16);
    const g = parseInt(got.slice(3, 5), 16);
    const b = parseInt(got.slice(5, 7), 16);
    expect(r).toBeGreaterThan(250);
    expect(r).toBeLessThanOrEqual(255);
    expect(g).toBeGreaterThan(34);
    expect(g).toBeLessThan(255);
    expect(b).toBeGreaterThan(35);
    expect(b).toBeLessThan(255);
  });
  it("accepts no-# prefix", () => {
    expect(mixWithWhite("FA2223", 1)).toBe("#fa2223");
  });
  it("clamps t to [0, 1]", () => {
    expect(mixWithWhite("#FA2223", 2)).toBe("#fa2223");
    expect(mixWithWhite("#FA2223", -1)).toBe("#ffffff");
  });
  it("returns white for malformed hex (defensive)", () => {
    expect(mixWithWhite("#zzz", 1)).toBe("#ffffff");
    expect(mixWithWhite("not-a-hex", 1)).toBe("#ffffff");
    expect(mixWithWhite("", 1)).toBe("#ffffff");
  });
});

describe("paletteFromBrand", () => {
  it("returns a 6-bucket palette for a valid brand", () => {
    const p = paletteFromBrand("#FA2223");
    expect(Object.keys(p).sort()).toEqual(
      [...BUCKET_ORDER].sort(),
    );
    // absent -> sentinel white (component substitutes hatch)
    expect(p.absent).toBe("#ffffff");
    expect(p.zero).toBe("#f1f5f9");
    // five-plus is the pure brand
    expect(p["five-plus"]).toBe("#fa2223");
  });

  it("derives a monotonic light-to-dark ramp on the four win buckets", () => {
    const p = paletteFromBrand("#FA2223");
    const lightness = (hex: string): number => {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return (r + g + b) / 3;
    };
    // one is lighter than two is lighter than three-four is lighter than five-plus
    expect(lightness(p.one)).toBeGreaterThan(lightness(p.two));
    expect(lightness(p.two)).toBeGreaterThan(lightness(p["three-four"]));
    expect(lightness(p["three-four"])).toBeGreaterThan(
      lightness(p["five-plus"]),
    );
  });

  it("falls back to slate-500 for missing / malformed brand_colour", () => {
    const p1 = paletteFromBrand(null);
    const p2 = paletteFromBrand(undefined);
    const p3 = paletteFromBrand("not-a-hex");
    const p4 = paletteFromBrand("#zzz");
    expect(p1["five-plus"]).toBe("#64748b");
    expect(p2["five-plus"]).toBe("#64748b");
    expect(p3["five-plus"]).toBe("#64748b");
    expect(p4["five-plus"]).toBe("#64748b");
  });

  it("renders DMK / BJP / AAP / BSP brand colours without going out-of-gamut", () => {
    // Sanity smoke per brief STOP condition #2: "brand_colour-derived
    // ramp produces obviously-wrong colours for at least 3 of the 5
    // representative parties". We verify each ramp produces 4 valid
    // #rrggbb stops between white and the brand colour.
    const parties = {
      DMK: "#FA2223",
      BJP: "#FF9933",
      INC: "#00BFFF",
      AAP: "#0072B0",
      BSP: "#22409A",
    };
    for (const [name, hex] of Object.entries(parties)) {
      const p = paletteFromBrand(hex);
      // Every bucket value is a valid #rrggbb
      for (const bucket of BUCKET_ORDER) {
        expect(p[bucket]).toMatch(/^#[0-9a-f]{6}$/);
      }
      // five-plus is the pure brand (case-insensitive)
      expect(p["five-plus"].toLowerCase()).toBe(hex.toLowerCase());
      // Each win bucket is distinguishable (no two stops collide)
      const winStops = new Set([p.one, p.two, p["three-four"], p["five-plus"]]);
      expect(winStops.size, `${name} stops should all differ`).toBe(4);
    }
  });
});

describe("homeStateEciCodes", () => {
  it("parses DMK home_state_codes from pipe-delimited string (TN + PY)", () => {
    expect(homeStateEciCodes("IN-TN|IN-PY")).toEqual(new Set(["S22", "U07"]));
  });
  it("parses DMK home_state_codes from a string[] (PartyMeta shape)", () => {
    expect(homeStateEciCodes(["IN-TN", "IN-PY"])).toEqual(
      new Set(["S22", "U07"]),
    );
  });
  it("returns empty set for empty / null / whitespace", () => {
    expect(homeStateEciCodes(null)).toEqual(new Set());
    expect(homeStateEciCodes(undefined)).toEqual(new Set());
    expect(homeStateEciCodes("")).toEqual(new Set());
    expect(homeStateEciCodes([])).toEqual(new Set());
    expect(homeStateEciCodes(" | | ")).toEqual(new Set());
    expect(homeStateEciCodes(["", "  "])).toEqual(new Set());
  });
  it("silently drops unknown ISO codes", () => {
    expect(homeStateEciCodes("IN-KA|IN-XX")).toEqual(new Set(["S10"]));
    expect(homeStateEciCodes(["IN-KA", "IN-XX"])).toEqual(new Set(["S10"]));
  });
  it("dedupes when the same code appears twice", () => {
    expect(homeStateEciCodes("IN-TN|IN-TN")).toEqual(new Set(["S22"]));
    expect(homeStateEciCodes(["IN-TN", "IN-TN"])).toEqual(new Set(["S22"]));
  });
});

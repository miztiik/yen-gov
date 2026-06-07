// Unit tests for canonical-entity-translation.ts (R2 reader-flip seam).
//
// Pure helpers (parseCsvLine, buildCanonicalSlugToLegacyMap,
// translateCanonicalSlugToLegacy) tested in isolation. The fetch+cache
// path is exercised in indicator-from-canonical.test.ts via the mocked
// loadCanonicalSlugToLegacyMap.

import { describe, expect, it } from "vitest";

import {
  buildCanonicalSlugToLegacyMap,
  parseCsvLine,
  translateCanonicalSlugToLegacy,
} from "./canonical-entity-translation";

describe("parseCsvLine", () => {
  it("parses comma-separated cells with no quoting", () => {
    expect(parseCsvLine("a,b,c")).toEqual(["a", "b", "c"]);
  });

  it("preserves empty trailing cells", () => {
    expect(parseCsvLine("a,b,")).toEqual(["a", "b", ""]);
  });

  it("preserves empty leading cells", () => {
    expect(parseCsvLine(",b,c")).toEqual(["", "b", "c"]);
  });

  it("handles quoted cells with embedded commas", () => {
    expect(parseCsvLine('a,"b,c",d')).toEqual(["a", "b,c", "d"]);
  });

  it("handles escaped double-quotes inside quoted cells", () => {
    expect(parseCsvLine('a,"b""c",d')).toEqual(["a", 'b"c', "d"]);
  });

  it("returns a single empty cell for the empty line", () => {
    expect(parseCsvLine("")).toEqual([""]);
  });
});

describe("buildCanonicalSlugToLegacyMap — geo.csv → slug→legacy map", () => {
  it("parses country, states, and districts into a single Map", () => {
    const csv = [
      "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code",
      "IN,India,,country,IN|IND|356,,",
      "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28",
      "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33",
      "delhi,Delhi,IN,state,IN-DL|U05|lgd:7,7,7",
      "andhra-pradesh/visakhapatnam,Visakhapatnam,andhra-pradesh,district,lgd:710,,",
      "tamil-nadu/chennai,Chennai,tamil-nadu,district,lgd:635,,",
      "delhi/new-delhi,New Delhi,delhi,district,lgd:642,,",
    ].join("\n");
    const map = buildCanonicalSlugToLegacyMap(csv);
    expect(map.get("IN")).toBe("IN");
    expect(map.get("andhra-pradesh")).toBe("S01");
    expect(map.get("tamil-nadu")).toBe("S22");
    expect(map.get("delhi")).toBe("U05");
    expect(map.get("andhra-pradesh/visakhapatnam")).toBe("S01-D710");
    expect(map.get("tamil-nadu/chennai")).toBe("S22-D635");
    expect(map.get("delhi/new-delhi")).toBe("U05-D642");
  });

  it("skips state rows missing an S<n> / U<n> alias token", () => {
    const csv = [
      "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code",
      "weird,Weird State,IN,state,IN-XX|lgd:99,,",
    ].join("\n");
    const map = buildCanonicalSlugToLegacyMap(csv);
    expect(map.has("weird")).toBe(false);
  });

  it("skips district rows whose parent state has no ECI mapping (anchor gap)", () => {
    const csv = [
      "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code",
      "weird,Weird State,IN,state,IN-XX|lgd:99,,",
      "weird/floating-district,Floating,weird,district,lgd:888,,",
    ].join("\n");
    const map = buildCanonicalSlugToLegacyMap(csv);
    expect(map.has("weird/floating-district")).toBe(false);
  });

  it("skips district rows missing an lgd:<n> alias token", () => {
    const csv = [
      "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code",
      "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33",
      "tamil-nadu/unknown,Unknown,tamil-nadu,district,,,",
    ].join("\n");
    const map = buildCanonicalSlugToLegacyMap(csv);
    expect(map.has("tamil-nadu/unknown")).toBe(false);
  });

  it("throws on missing required headers", () => {
    const csv = "entity_id,name\nIN,India";
    expect(() => buildCanonicalSlugToLegacyMap(csv)).toThrow(
      /header missing required columns/,
    );
  });

  it("returns an empty Map for an empty CSV", () => {
    expect(buildCanonicalSlugToLegacyMap("").size).toBe(0);
  });

  it("handles Windows CRLF line endings", () => {
    const csv =
      "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\r\n" +
      "tamil-nadu,Tamil Nadu,IN,state,S22|lgd:33,33,33\r\n";
    const map = buildCanonicalSlugToLegacyMap(csv);
    expect(map.get("tamil-nadu")).toBe("S22");
  });
});

describe("translateCanonicalSlugToLegacy", () => {
  const map = new Map([
    ["IN", "IN"],
    ["tamil-nadu", "S22"],
    ["tamil-nadu/chennai", "S22-D635"],
  ]);

  it("translates known slugs to legacy IDs", () => {
    expect(translateCanonicalSlugToLegacy(map, "tamil-nadu")).toBe("S22");
    expect(translateCanonicalSlugToLegacy(map, "tamil-nadu/chennai")).toBe("S22-D635");
    expect(translateCanonicalSlugToLegacy(map, "IN")).toBe("IN");
  });

  it("passes unknown slugs through unchanged (caller's responsibility to drop or surface)", () => {
    expect(translateCanonicalSlugToLegacy(map, "andhra-pradesh")).toBe("andhra-pradesh");
    expect(translateCanonicalSlugToLegacy(map, "")).toBe("");
  });
});

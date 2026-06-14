// Vitest for `electoral-id-translator.ts`. Covers:
//   - AC parse happy-path (multiple states + delim_years)
//   - PC parse happy-path (multiple states + delim_years)
//   - unknown ECI state code returns null (AC + PC)
//   - malformed shapes return null (party-aggregate, candidate, state-
//     rollup, electoral.csv-shape, garbage / empty)
//   - ECI_TO_SLUG has exactly 36 entries
//   - SLUG_TO_ECI round-trips every ECI_TO_SLUG entry

import { describe, expect, it } from "vitest";

import {
  ECI_TO_SLUG,
  SLUG_TO_ECI,
  parsePeerEntityId,
} from "./electoral-id-translator";

describe("ECI_TO_SLUG", () => {
  it("has exactly 36 entries (29 states + 7 UTs per LGD register)", () => {
    expect(Object.keys(ECI_TO_SLUG)).toHaveLength(36);
  });

  it("only uses S## or U## ECI st_code keys", () => {
    for (const k of Object.keys(ECI_TO_SLUG)) {
      expect(k).toMatch(/^(S\d{2}|U\d{2})$/);
    }
  });
});

describe("SLUG_TO_ECI", () => {
  it("round-trips every ECI_TO_SLUG entry", () => {
    for (const [eci, slug] of Object.entries(ECI_TO_SLUG)) {
      expect(SLUG_TO_ECI[slug]).toBe(eci);
    }
  });

  it("has the same entry count as ECI_TO_SLUG (no slug collisions)", () => {
    expect(Object.keys(SLUG_TO_ECI)).toHaveLength(
      Object.keys(ECI_TO_SLUG).length,
    );
  });
});

describe("parsePeerEntityId — AC happy-path", () => {
  it("parses a Tamil Nadu 2008 AC entity_id", () => {
    expect(parsePeerEntityId("IN-S22-AC-2008-167")).toEqual({
      kind: "ac",
      delim_year: 2008,
      slug: "tamil-nadu",
      eci_no: 167,
    });
  });

  it("parses an Andhra Pradesh 1976 AC entity_id", () => {
    expect(parsePeerEntityId("IN-S01-AC-1976-1")).toEqual({
      kind: "ac",
      delim_year: 1976,
      slug: "andhra-pradesh",
      eci_no: 1,
    });
  });

  it("parses a Delhi UT 2008 AC entity_id", () => {
    expect(parsePeerEntityId("IN-U05-AC-2008-70")).toEqual({
      kind: "ac",
      delim_year: 2008,
      slug: "delhi",
      eci_no: 70,
    });
  });

  it("parses a multi-digit eci_no", () => {
    expect(parsePeerEntityId("IN-S24-AC-2008-403")).toEqual({
      kind: "ac",
      delim_year: 2008,
      slug: "uttar-pradesh",
      eci_no: 403,
    });
  });
});

describe("parsePeerEntityId — PC happy-path", () => {
  it("parses a Tamil Nadu 2008 PC entity_id", () => {
    expect(parsePeerEntityId("IN-PC-2008-S22-25")).toEqual({
      kind: "pc",
      delim_year: 2008,
      slug: "tamil-nadu",
      eci_no: 25,
    });
  });

  it("parses an Andhra Pradesh 1976 PC entity_id", () => {
    expect(parsePeerEntityId("IN-PC-1976-S01-1")).toEqual({
      kind: "pc",
      delim_year: 1976,
      slug: "andhra-pradesh",
      eci_no: 1,
    });
  });

  it("parses a Delhi UT 2008 PC entity_id", () => {
    expect(parsePeerEntityId("IN-PC-2008-U05-7")).toEqual({
      kind: "pc",
      delim_year: 2008,
      slug: "delhi",
      eci_no: 7,
    });
  });

  it("parses a Lakshadweep UT PC entity_id (single-seat UT)", () => {
    expect(parsePeerEntityId("IN-PC-2008-U04-1")).toEqual({
      kind: "pc",
      delim_year: 2008,
      slug: "lakshadweep",
      eci_no: 1,
    });
  });
});

describe("parsePeerEntityId — unknown state code returns null", () => {
  it("returns null for AC with an unknown S## code (defensive)", () => {
    expect(parsePeerEntityId("IN-S99-AC-2008-1")).toBeNull();
  });

  it("returns null for PC with an unknown S## code", () => {
    expect(parsePeerEntityId("IN-PC-2008-S99-1")).toBeNull();
  });

  it("returns null for AC with an unknown U## code", () => {
    expect(parsePeerEntityId("IN-U99-AC-2008-1")).toBeNull();
  });

  it("returns null for PC with an unknown U## code", () => {
    expect(parsePeerEntityId("IN-PC-2008-U99-1")).toBeNull();
  });

  it("returns null for the retired S09 code (no LGD entry)", () => {
    expect(parsePeerEntityId("IN-S09-AC-2008-1")).toBeNull();
  });
});

describe("parsePeerEntityId — malformed shapes return null", () => {
  it("returns null for party-aggregate entity_ids", () => {
    expect(parsePeerEntityId("IN-S22-AcGenApr2021-PARTY-DMK")).toBeNull();
    expect(parsePeerEntityId("IN-S24-LsGenMay2024-PARTY-BJP")).toBeNull();
  });

  it("returns null for candidate entity_ids", () => {
    expect(
      parsePeerEntityId("IN-S22-AC-2008-167-AcGenMay2026-C03"),
    ).toBeNull();
  });

  it("returns null for state-rollup entity_ids", () => {
    expect(parsePeerEntityId("IN-S22-AcGenMay2026")).toBeNull();
    expect(parsePeerEntityId("IN-S24-LsGenMay2024")).toBeNull();
  });

  it("returns null for electoral.csv-shape entity_ids (LGD slug + numeric suffix)", () => {
    expect(parsePeerEntityId("IN-AC-2008-tamil-nadu-4025")).toBeNull();
    expect(parsePeerEntityId("IN-AC-2008-tamil-nadu-eci192")).toBeNull();
    expect(parsePeerEntityId("IN-PC-2008-andhra-pradesh-411")).toBeNull();
  });

  it("returns null for arbitrary garbage", () => {
    expect(parsePeerEntityId("hello")).toBeNull();
    expect(parsePeerEntityId("")).toBeNull();
    expect(parsePeerEntityId("IN")).toBeNull();
    expect(parsePeerEntityId("IN-S22")).toBeNull();
    expect(parsePeerEntityId("IN-S22-AC")).toBeNull();
    expect(parsePeerEntityId("IN-S22-AC-2008")).toBeNull();
  });

  it("returns null when the eci_no is non-numeric", () => {
    expect(parsePeerEntityId("IN-S22-AC-2008-abc")).toBeNull();
  });

  it("returns null when the delim_year is non-4-digit", () => {
    expect(parsePeerEntityId("IN-S22-AC-08-1")).toBeNull();
    expect(parsePeerEntityId("IN-PC-08-S22-1")).toBeNull();
  });
});

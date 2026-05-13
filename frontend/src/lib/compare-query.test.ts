// Tests for the /compare query-string contract (P4).
//
// Guards: round-trip; malformed values dropped silently (no throw, no
// leak); empty state serializes to ""; states are de-duped order-preserving;
// every PEER_SET_VALUES is accepted.

import { describe, it, expect } from "vitest";
import { parseCompareQuery, serializeCompareQuery } from "./compare-query";
import { PEER_SET_VALUES } from "./catalogue";

describe("parseCompareQuery", () => {
  it("returns the empty shape when query is empty", () => {
    expect(parseCompareQuery("")).toEqual({ indicator: null, states: [], peer: null });
    expect(parseCompareQuery("?")).toEqual({ indicator: null, states: [], peer: null });
  });

  it("parses indicator id", () => {
    expect(parseCompareQuery("?i=fiscal/outstanding_debt_pct_gsdp")).toEqual({
      indicator: "fiscal/outstanding_debt_pct_gsdp",
      states: [],
      peer: null,
    });
  });

  it("parses comma-separated states preserving order", () => {
    expect(parseCompareQuery("?i=fiscal/debt&states=tamil-nadu,kerala,karnataka")).toEqual({
      indicator: "fiscal/debt",
      states: ["tamil-nadu", "kerala", "karnataka"],
      peer: null,
    });
  });

  it("de-dupes states (first occurrence wins) preserving order", () => {
    expect(parseCompareQuery("?states=tamil-nadu,kerala,tamil-nadu,andhra-pradesh").states).toEqual([
      "tamil-nadu",
      "kerala",
      "andhra-pradesh",
    ]);
  });

  it("trims whitespace inside the states csv", () => {
    expect(parseCompareQuery("?states=tamil-nadu, kerala , karnataka").states).toEqual([
      "tamil-nadu",
      "kerala",
      "karnataka",
    ]);
  });

  it("drops empty / malformed state slugs silently", () => {
    expect(parseCompareQuery("?states=,tamil-nadu,,Bad_Slug,kerala,").states).toEqual([
      "tamil-nadu",
      "kerala",
    ]);
  });

  it("drops malformed indicator ids silently", () => {
    expect(parseCompareQuery("?i=").indicator).toBeNull();
    expect(parseCompareQuery("?i=not-a-valid-id-no-slash").indicator).toBeNull();
    expect(parseCompareQuery("?i=../etc/passwd").indicator).toBeNull();
    expect(parseCompareQuery("?i=fiscal/UPPERCASE_NOT_OK").indicator).toBeNull();
  });

  it("accepts a valid peer", () => {
    expect(parseCompareQuery("?peer=general_category").peer).toBe("general_category");
  });

  it("drops unknown peer silently", () => {
    expect(parseCompareQuery("?peer=not-a-real-peer").peer).toBeNull();
  });

  it("parses all three params together", () => {
    expect(
      parseCompareQuery("?i=fiscal/debt&states=tamil-nadu,kerala&peer=general_category"),
    ).toEqual({
      indicator: "fiscal/debt",
      states: ["tamil-nadu", "kerala"],
      peer: "general_category",
    });
  });

  it("accepts URLSearchParams instance", () => {
    const p = new URLSearchParams();
    p.set("i", "energy/installed_mw_per_capita");
    p.set("states", "gujarat");
    expect(parseCompareQuery(p)).toEqual({
      indicator: "energy/installed_mw_per_capita",
      states: ["gujarat"],
      peer: null,
    });
  });

  it("accepts every PEER_SET_VALUES value", () => {
    for (const v of PEER_SET_VALUES) {
      expect(parseCompareQuery(`?peer=${v}`).peer).toBe(v);
    }
  });
});

describe("serializeCompareQuery", () => {
  it("returns empty string when every field is absent", () => {
    expect(serializeCompareQuery({ indicator: null, states: [], peer: null })).toBe("");
  });

  it("emits only the present fields", () => {
    expect(serializeCompareQuery({ indicator: "fiscal/debt", states: [], peer: null })).toBe(
      "?i=fiscal%2Fdebt",
    );
    expect(serializeCompareQuery({ indicator: null, states: ["tamil-nadu"], peer: null })).toBe(
      "?states=tamil-nadu",
    );
    expect(serializeCompareQuery({ indicator: null, states: [], peer: "general_category" })).toBe(
      "?peer=general_category",
    );
  });

  it("joins states csv in given order", () => {
    expect(
      serializeCompareQuery({ indicator: "x/y", states: ["a", "b", "c"], peer: null }),
    ).toBe("?i=x%2Fy&states=a%2Cb%2Cc");
  });

  it("round-trips a fully populated state", () => {
    const q = {
      indicator: "fiscal/debt",
      states: ["tamil-nadu", "kerala", "karnataka"],
      peer: "general_category" as const,
    };
    expect(parseCompareQuery(serializeCompareQuery(q))).toEqual(q);
  });

  it("round-trips the empty state", () => {
    const q = { indicator: null, states: [], peer: null };
    expect(parseCompareQuery(serializeCompareQuery(q))).toEqual(q);
  });
});

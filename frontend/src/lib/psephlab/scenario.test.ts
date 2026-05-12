import { describe, it, expect, vi } from "vitest";
import {
  encodeScenario,
  decodeScenario,
  EMPTY_SCENARIO,
} from "./scenario";
import type { Scenario } from "./types";

describe("encodeScenario / decodeScenario — round-trip", () => {
  it("round-trips the empty scenario", () => {
    const enc = encodeScenario(EMPTY_SCENARIO);
    expect(decodeScenario(enc)).toEqual(EMPTY_SCENARIO);
  });

  it("round-trips a scenario with mutations and color overrides", () => {
    const s: Scenario = {
      v: 1,
      rule: "fptp",
      mutations: [
        { id: "thresholdDrop", threshold_pct: 5 },
        {
          id: "statewideSwing",
          from_party_eci_codes: ["AIADMK"],
          to_party_eci_code: "DMK",
          pct: 3,
        },
      ],
      colors: { DMK: "#dd2222", AIADMK: "#22aaee" },
    };
    expect(decodeScenario(encodeScenario(s))).toEqual(s);
  });

  it("preserves non-ASCII strings (party names with diacritics, bag labels)", () => {
    const s: Scenario = {
      v: 1,
      rule: "fptp",
      mutations: [
        { id: "partyBag", name: "Évolution द", members: ["AIADMK", "DMK"] },
      ],
    };
    expect(decodeScenario(encodeScenario(s))).toEqual(s);
  });

  it("emits URL-safe base64 (no '+', '/', or '=')", () => {
    const enc = encodeScenario(EMPTY_SCENARIO);
    expect(enc).not.toMatch(/[+/=]/);
  });

  it("omits empty mutations / colors fields to keep URLs short", () => {
    const enc = encodeScenario(EMPTY_SCENARIO);
    const decoded = atob(enc.replace(/-/g, "+").replace(/_/g, "/"));
    const obj = JSON.parse(decoded);
    expect(obj).not.toHaveProperty("mutations");
    expect(obj).not.toHaveProperty("colors");
  });
});

describe("decodeScenario — graceful failure", () => {
  it("returns EMPTY_SCENARIO for null / empty input", () => {
    expect(decodeScenario(null)).toEqual(EMPTY_SCENARIO);
    expect(decodeScenario("")).toEqual(EMPTY_SCENARIO);
    expect(decodeScenario(undefined)).toEqual(EMPTY_SCENARIO);
  });

  it("returns EMPTY_SCENARIO and warns for malformed base64 / JSON", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(decodeScenario("!!!not-base64!!!")).toEqual(EMPTY_SCENARIO);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("refuses unknown future versions and warns", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    // base64url-encode JSON for v=99
    const future = btoa(JSON.stringify({ v: 99, rule: "fptp", mutations: [] }))
      .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    expect(decodeScenario(future)).toEqual(EMPTY_SCENARIO);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

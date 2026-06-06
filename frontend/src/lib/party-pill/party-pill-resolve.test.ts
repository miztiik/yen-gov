// E2 vitest unit for `party-pill-resolve.ts`. Node-env.
//
// Covers:
//   - Anchor tier (BJP=369): treatment="anchor", hex=anchor hex
//   - Brand tier: treatment="brand", hex=brand hex
//   - Fallback tier (NEVERSEEN): treatment="fallback", hex=algorithmic
//   - Null/empty id: treatment="neutral", hex=null
//   - Label fallback: missing party_short -> "Unknown"
//   - pickInkForFill: luminance branch for light vs dark fills

import { describe, expect, test } from "vitest";
import { pickInkForFill, resolvePartyPill } from "./party-pill-resolve";

describe("resolvePartyPill", () => {
  test("anchor tier: BJP -> treatment=anchor + saffron hex", () => {
    const r = resolvePartyPill({ party_id: "parties.IN.BJP", party_short: "BJP" });
    expect(r.treatment).toBe("anchor");
    expect(r.hex?.toLowerCase()).toBe("#ea580c");
    expect(r.label).toBe("BJP");
  });

  test("anchor tier: INC -> treatment=anchor + blue hex", () => {
    const r = resolvePartyPill({ party_id: "parties.IN.INC", party_short: "INC" });
    expect(r.treatment).toBe("anchor");
    expect(r.hex?.toLowerCase()).toBe("#1d4ed8");
  });

  test("brand tier: party with brand_colour confidence!=low -> treatment=brand", () => {
    const r = resolvePartyPill({
      party_id: "parties.IN.BRAND_PARTY",
      party_short: "BP",
      row: { party_id: "parties.IN.BRAND_PARTY", brand_colour: { hex: "#abcdef", confidence: "high" } },
    });
    expect(r.treatment).toBe("brand");
    expect(r.hex?.toLowerCase()).toBe("#abcdef");
  });

  test("brand tier with low confidence -> falls through to fallback", () => {
    const r = resolvePartyPill({
      party_id: "parties.IN.LOW_CONF_PARTY",
      party_short: "LCP",
      row: { party_id: "parties.IN.LOW_CONF_PARTY", brand_colour: { hex: "#222222", confidence: "low" } },
    });
    expect(r.treatment).toBe("fallback");
    // Algorithmic hash, not the low-conf brand colour
    expect(r.hex?.toLowerCase()).not.toBe("#222222");
  });

  test("fallback tier: never-seen party -> treatment=fallback + algorithmic hex", () => {
    const r = resolvePartyPill({ party_id: "NEVERSEEN", party_short: "NEW" });
    expect(r.treatment).toBe("fallback");
    expect(r.hex).toMatch(/^#[0-9a-f]{6}$/i);
  });

  test("null party_id -> treatment=neutral + hex=null", () => {
    const r = resolvePartyPill({ party_id: null, party_short: "Unaffiliated" });
    expect(r.treatment).toBe("neutral");
    expect(r.hex).toBeNull();
    expect(r.label).toBe("Unaffiliated");
  });

  test("empty-string party_id -> neutral", () => {
    const r = resolvePartyPill({ party_id: "", party_short: "X" });
    expect(r.treatment).toBe("neutral");
  });

  test("missing label -> Unknown", () => {
    const r = resolvePartyPill({ party_id: null });
    expect(r.label).toBe("Unknown");
  });

  test("missing label with anchor id still resolves correctly", () => {
    const r = resolvePartyPill({ party_id: "parties.IN.BJP" });
    expect(r.treatment).toBe("anchor");
    expect(r.label).toBe("Unknown");
  });

  test("anchor-tier 'IND' independents still anchor-styled per anchor table", () => {
    // IND is explicitly in ANCHORS_BY_PID as slate-400 (#94a3b8). Its
    // treatment is still "anchor" because the resolver classifies it
    // as such; the PILL's neutral-by-treatment-tier rule applies only
    // when party_id is null. This test guards against confusing
    // "anchor uses slate" with "this is a neutral party".
    const r = resolvePartyPill({ party_id: "parties.IN.IND", party_short: "IND" });
    expect(r.treatment).toBe("anchor");
    expect(r.hex?.toLowerCase()).toBe("#94a3b8");
  });
});

describe("pickInkForFill", () => {
  test("dark fill -> white text", () => {
    expect(pickInkForFill("#1d4ed8")).toBe("#ffffff");  // INC blue
    expect(pickInkForFill("#991b1b")).toBe("#ffffff");  // dark red
    expect(pickInkForFill("#000080")).toBe("#ffffff");  // navy
  });

  test("light fill -> dark text", () => {
    expect(pickInkForFill("#facc15")).toBe("#0f172a");  // PMK yellow
    expect(pickInkForFill("#ffffff")).toBe("#0f172a");  // white
    expect(pickInkForFill("#cbd5e1")).toBe("#0f172a");  // slate-300 (neutral)
  });

  test("null/undefined/empty -> dark text", () => {
    expect(pickInkForFill(null)).toBe("#0f172a");
    expect(pickInkForFill(undefined)).toBe("#0f172a");
    expect(pickInkForFill("")).toBe("#0f172a");
  });

  test("malformed hex -> dark text (defensive)", () => {
    expect(pickInkForFill("#zz")).toBe("#0f172a");
    expect(pickInkForFill("not a colour")).toBe("#0f172a");
  });

  test("medium-brightness fill at threshold", () => {
    // Brightness 140 is the cutoff; a near-grey at ~140 should
    // route to dark text.
    expect(pickInkForFill("#888888")).toBe("#ffffff");  // brightness 136
    expect(pickInkForFill("#a0a0a0")).toBe("#0f172a");  // brightness 160
  });
});

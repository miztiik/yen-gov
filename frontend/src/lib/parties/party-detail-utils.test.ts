import { describe, expect, it } from "vitest";
import { stateNameFromEntityId } from "./party-detail-utils";

// Stub resolver: just returns the canonical names we know we use
// in the strongholds-row smoke. `null` for the deliberately-unknown
// code so we can pin the degraded-fallback branch.
const stub = (code: string): string | null => {
  if (code === "S22") return "Tamil Nadu";
  if (code === "S24") return "Uttar Pradesh";
  if (code === "U05") return "NCT of Delhi";
  return null;
};

describe("stateNameFromEntityId", () => {
  it("parses a PC entity_id and resolves the state name", () => {
    const got = stateNameFromEntityId("IN-PC-2008-S22-10", stub);
    expect(got).toEqual({ state_code: "S22", state_name: "Tamil Nadu" });
  });

  it("parses an AC entity_id and resolves the state name", () => {
    // Assembly grammar is IN-Sxx-AC-YYYY-N (state code at parts[1]),
    // distinct from Parliament's IN-PC-YYYY-Sxx-N (state code at parts[3]).
    const got = stateNameFromEntityId("IN-S24-AC-1976-167", stub);
    expect(got).toEqual({ state_code: "S24", state_name: "Uttar Pradesh" });
  });

  it("handles UT codes (U-prefix) for both PC and AC grammars", () => {
    expect(stateNameFromEntityId("IN-PC-2008-U05-1", stub)).toEqual({
      state_code: "U05",
      state_name: "NCT of Delhi",
    });
    expect(stateNameFromEntityId("IN-U05-AC-1976-1", stub)).toEqual({
      state_code: "U05",
      state_name: "NCT of Delhi",
    });
  });

  it("falls back to the raw code when the resolver returns null", () => {
    const got = stateNameFromEntityId("IN-PC-2008-S99-1", stub);
    expect(got).toEqual({ state_code: "S99", state_name: "S99" });
  });

  it("returns the malformed-fallback for empty / non-string input", () => {
    expect(stateNameFromEntityId("", stub)).toEqual({ state_code: null, state_name: "" });
    // @ts-expect-error - intentional bad input
    expect(stateNameFromEntityId(null, stub)).toEqual({ state_code: null, state_name: "" });
    // @ts-expect-error - intentional bad input
    expect(stateNameFromEntityId(undefined, stub)).toEqual({ state_code: null, state_name: "" });
  });

  it("returns the malformed-fallback for ids with the wrong prefix", () => {
    expect(stateNameFromEntityId("FOO-PC-2008-S22-10", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
    expect(stateNameFromEntityId("IN-XX-2008-S22-10", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
    // IN-Sxx-XX-... is not AC, so does not match the assembly grammar
    expect(stateNameFromEntityId("IN-S22-XX-2008-10", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
  });

  it("returns the malformed-fallback for ids with too few segments", () => {
    expect(stateNameFromEntityId("IN-PC-2008-S22", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
    expect(stateNameFromEntityId("IN-PC", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
  });

  it("returns the malformed-fallback for ids whose state segment is not [SU]\\d{2}", () => {
    expect(stateNameFromEntityId("IN-PC-2008-XX-10", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
    expect(stateNameFromEntityId("IN-PC-2008-S2-10", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
    expect(stateNameFromEntityId("IN-PC-2008-s22-10", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
    // AC grammar: malformed state segment at parts[1]
    expect(stateNameFromEntityId("IN-XX-AC-1976-10", stub)).toEqual({
      state_code: null,
      state_name: "",
    });
  });
});

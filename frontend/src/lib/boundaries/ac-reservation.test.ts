import { describe, expect, it } from "vitest";
import { parseReservation } from "./ac-reservation";

describe("parseReservation", () => {
  it("reads the explicit reservation field (Assam-style)", () => {
    expect(parseReservation({ reservation: "SC", ac_name: "Ratabari" })).toBe(
      "SC",
    );
    expect(parseReservation({ reservation: "ST", ac_name: "Bokakhat" })).toBe(
      "ST",
    );
  });

  it("treats GEN and unknown explicit values as null", () => {
    expect(parseReservation({ reservation: "GEN", ac_name: "Dhubri" })).toBeNull();
    expect(parseReservation({ reservation: "", ac_name: "Dhubri" })).toBeNull();
  });

  it("falls back to the (SC)/(ST) name suffix (TN / Karnataka-style)", () => {
    expect(parseReservation({ ac_name: "Embalam (SC)" })).toBe("SC");
    expect(parseReservation({ ac_name: "Kollegal (ST)" })).toBe("ST");
  });

  it("is case-insensitive on the suffix", () => {
    expect(parseReservation({ ac_name: "Somewhere (sc)" })).toBe("SC");
  });

  it("returns null for an unreserved name", () => {
    expect(parseReservation({ ac_name: "Saidapet" })).toBeNull();
  });

  it("prefers the explicit field over the suffix when both present", () => {
    expect(
      parseReservation({ reservation: "ST", ac_name: "Weird (SC)" }),
    ).toBe("ST");
  });

  it("returns null for empty / missing props", () => {
    expect(parseReservation({})).toBeNull();
  });
});

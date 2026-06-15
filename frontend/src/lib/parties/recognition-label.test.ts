// Vitest pin for the citizen-facing recognition vocabulary (Hans H7).
// Pins the 5 known scopes + the default branch so any future widening
// of the ECI category taxonomy goes through review rather than landing
// silently as a "Recognition unknown" badge.

import { describe, expect, it } from "vitest";
import { recognitionLabel } from "./recognition-label";

describe("recognitionLabel", () => {
  it("renders the H7 vocabulary for every known scope", () => {
    expect(recognitionLabel("national")).toBe("Nationally recognised party");
    expect(recognitionLabel("state")).toBe("State-recognised party");
    expect(recognitionLabel("unrecognised_registered")).toBe(
      "Registered party (unrecognised)",
    );
    expect(recognitionLabel("defunct")).toBe("Defunct");
    expect(recognitionLabel("sentinel")).toBe("Special category");
  });

  it("falls back to `Recognition unknown` for null / unknown scopes", () => {
    expect(recognitionLabel(null)).toBe("Recognition unknown");
    expect(recognitionLabel("")).toBe("Recognition unknown");
    expect(recognitionLabel("future-eci-category")).toBe("Recognition unknown");
  });
});

// Status-glyph verdict helpers — pure-function unit tests.
//
// Covers the closed-union return contract: every input shape must
// map to exactly one verdict; the `direction` gate must short-circuit
// to `"neutral"` (no colour) when the indicator semantics are
// undecided.

import { describe, expect, it } from "vitest";

import { computeStatusVerdict } from "./helpers";

describe("computeStatusVerdict", () => {
  describe("missing branch", () => {
    it("returns 'missing' when state_value is null", () => {
      expect(computeStatusVerdict(null, 100, "higher_is_better")).toBe("missing");
    });

    it("returns 'missing' when reference_value is null", () => {
      expect(computeStatusVerdict(100, null, "higher_is_better")).toBe("missing");
    });

    it("returns 'missing' when state_value is undefined", () => {
      expect(computeStatusVerdict(undefined, 100, "higher_is_better")).toBe(
        "missing",
      );
    });

    it("returns 'missing' when reference_value is undefined", () => {
      expect(computeStatusVerdict(100, undefined, "higher_is_better")).toBe(
        "missing",
      );
    });

    it("returns 'missing' when state_value is NaN", () => {
      expect(computeStatusVerdict(NaN, 100, "higher_is_better")).toBe("missing");
    });

    it("returns 'missing' when reference_value is NaN", () => {
      expect(computeStatusVerdict(100, NaN, "higher_is_better")).toBe("missing");
    });

    it("missing wins over neutral direction", () => {
      // Both nulls + neutral direction -> still 'missing'; we never
      // pretend we have data we don't.
      expect(computeStatusVerdict(null, null, "neutral")).toBe("missing");
    });
  });

  describe("neutral direction gate", () => {
    it("returns 'neutral' when direction === neutral, state above ref", () => {
      expect(computeStatusVerdict(120, 100, "neutral")).toBe("neutral");
    });

    it("returns 'neutral' when direction === neutral, state below ref", () => {
      expect(computeStatusVerdict(80, 100, "neutral")).toBe("neutral");
    });

    it("returns 'neutral' when direction === neutral, state equals ref", () => {
      // Even equal -> neutral, not 'equal'; the citizen reading is
      // undecided so we never colour the glyph.
      expect(computeStatusVerdict(100, 100, "neutral")).toBe("neutral");
    });
  });

  describe("equal branch", () => {
    it("returns 'equal' when values match, higher_is_better", () => {
      expect(computeStatusVerdict(100, 100, "higher_is_better")).toBe("equal");
    });

    it("returns 'equal' when values match, lower_is_better", () => {
      expect(computeStatusVerdict(100, 100, "lower_is_better")).toBe("equal");
    });

    it("equal works with zero on both sides", () => {
      expect(computeStatusVerdict(0, 0, "higher_is_better")).toBe("equal");
    });

    it("equal works with negative values", () => {
      expect(computeStatusVerdict(-50, -50, "lower_is_better")).toBe("equal");
    });
  });

  describe("better / worse verdicts", () => {
    it("state above ref + higher_is_better -> 'better'", () => {
      // Literacy: 95% > national 85% under higher_is_better -> good.
      expect(computeStatusVerdict(95, 85, "higher_is_better")).toBe("better");
    });

    it("state below ref + higher_is_better -> 'worse'", () => {
      // Literacy: 70% < national 85% under higher_is_better -> bad.
      expect(computeStatusVerdict(70, 85, "higher_is_better")).toBe("worse");
    });

    it("state above ref + lower_is_better -> 'worse'", () => {
      // IMR: 45/1000 > national 28/1000 under lower_is_better -> bad.
      expect(computeStatusVerdict(45, 28, "lower_is_better")).toBe("worse");
    });

    it("state below ref + lower_is_better -> 'better'", () => {
      // IMR: 12/1000 < national 28/1000 under lower_is_better -> good.
      expect(computeStatusVerdict(12, 28, "lower_is_better")).toBe("better");
    });

    it("ranking works with negative values + higher_is_better", () => {
      // -10 > -20 under higher_is_better -> better
      expect(computeStatusVerdict(-10, -20, "higher_is_better")).toBe("better");
    });

    it("ranking works with negative values + lower_is_better", () => {
      // -10 > -20 under lower_is_better -> worse (we want more negative)
      expect(computeStatusVerdict(-10, -20, "lower_is_better")).toBe("worse");
    });
  });

  describe("ordering of gates (missing > neutral > equal > better/worse)", () => {
    it("missing beats neutral direction", () => {
      expect(computeStatusVerdict(null, 100, "neutral")).toBe("missing");
    });

    it("neutral direction beats equal value match", () => {
      // direction:neutral + values equal -> 'neutral' (not 'equal').
      expect(computeStatusVerdict(100, 100, "neutral")).toBe("neutral");
    });

    it("equal value match beats the better/worse branch", () => {
      // values exactly equal + non-neutral direction -> 'equal' (we
      // do NOT round up to 'better' / 'worse').
      expect(computeStatusVerdict(85.0, 85.0, "higher_is_better")).toBe("equal");
    });
  });
});

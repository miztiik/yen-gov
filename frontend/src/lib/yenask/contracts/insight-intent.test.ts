// Zod boundary tests for InsightIntent.
//
// Per plan-doc §17 D-03: this contract is the only seam the SLM /
// canned-fixtures cross. Any malformed payload is rejected here BEFORE
// the compiler sees it. These tests pin the rejection surface so an
// "additive" schema change can't accidentally widen the contract.

import { describe, expect, it } from "vitest";
import {
  parseInsightIntent,
  safeParseInsightIntent,
  InsightIntentSchema,
} from "./insight-intent";

const VALID_BASE = {
  version: "insight.intent.v0",
  concept_id: "party_totals",
  question: "What were the May 2026 Tamil Nadu party totals?",
  filters: {
    state_partition_id: "in_s22",
    period_label: "AcGenMay2026",
  },
};

describe("InsightIntent v0", () => {
  it("accepts a minimal well-formed party_totals intent", () => {
    const intent = parseInsightIntent(VALID_BASE);
    expect(intent.concept_id).toBe("party_totals");
    expect(intent.filters.state_partition_id).toBe("in_s22");
    expect(intent.version).toBe("insight.intent.v0");
  });

  it("accepts all four concept_id enum values", () => {
    for (const concept_id of [
      "party_totals",
      "closest_contests",
      "constituency_result",
      "turnout_extremes",
    ] as const) {
      const intent = parseInsightIntent({
        ...VALID_BASE,
        concept_id,
        ...(concept_id === "constituency_result"
          ? { filters: { ...VALID_BASE.filters, ac_no: 167 } }
          : {}),
      });
      expect(intent.concept_id).toBe(concept_id);
    }
  });

  it("rejects an unknown concept_id (closed enum)", () => {
    const r = safeParseInsightIntent({ ...VALID_BASE, concept_id: "unknown_thing" });
    expect(r.success).toBe(false);
  });

  it("rejects wrong version literal", () => {
    const r = safeParseInsightIntent({ ...VALID_BASE, version: "insight.intent.v1" });
    expect(r.success).toBe(false);
  });

  it("rejects state_partition_id that doesn't match in_<state>", () => {
    const r = safeParseInsightIntent({
      ...VALID_BASE,
      filters: { ...VALID_BASE.filters, state_partition_id: "tamil_nadu" },
    });
    expect(r.success).toBe(false);
  });

  it("rejects state_partition_id with uppercase", () => {
    const r = safeParseInsightIntent({
      ...VALID_BASE,
      filters: { ...VALID_BASE.filters, state_partition_id: "in_S22" },
    });
    expect(r.success).toBe(false);
  });

  it("rejects period_label that is too short or too long", () => {
    expect(
      safeParseInsightIntent({
        ...VALID_BASE,
        filters: { ...VALID_BASE.filters, period_label: "ab" },
      }).success,
    ).toBe(false);
    expect(
      safeParseInsightIntent({
        ...VALID_BASE,
        filters: { ...VALID_BASE.filters, period_label: "x".repeat(65) },
      }).success,
    ).toBe(false);
  });

  it("rejects ac_no that is negative or > 9999", () => {
    expect(
      safeParseInsightIntent({
        ...VALID_BASE,
        concept_id: "constituency_result",
        filters: { ...VALID_BASE.filters, ac_no: -1 },
      }).success,
    ).toBe(false);
    expect(
      safeParseInsightIntent({
        ...VALID_BASE,
        concept_id: "constituency_result",
        filters: { ...VALID_BASE.filters, ac_no: 10000 },
      }).success,
    ).toBe(false);
  });

  it("rejects limit greater than 100", () => {
    const r = safeParseInsightIntent({
      ...VALID_BASE,
      filters: { ...VALID_BASE.filters, limit: 101 },
    });
    expect(r.success).toBe(false);
  });

  it("rejects party_short_code that is empty or too long", () => {
    expect(
      safeParseInsightIntent({
        ...VALID_BASE,
        filters: { ...VALID_BASE.filters, party_short_code: "" },
      }).success,
    ).toBe(false);
    expect(
      safeParseInsightIntent({
        ...VALID_BASE,
        filters: { ...VALID_BASE.filters, party_short_code: "x".repeat(17) },
      }).success,
    ).toBe(false);
  });

  it("rejects extra unknown filter keys (.strict)", () => {
    const r = safeParseInsightIntent({
      ...VALID_BASE,
      filters: { ...VALID_BASE.filters, sneaky_extra_filter: "boom" },
    });
    expect(r.success).toBe(false);
  });

  it("rejects empty question string", () => {
    const r = safeParseInsightIntent({ ...VALID_BASE, question: "" });
    expect(r.success).toBe(false);
  });

  it("parseInsightIntent throws on invalid input", () => {
    expect(() => parseInsightIntent({ broken: true })).toThrow();
  });

  it("schema export is the same Zod instance used by parseInsightIntent", () => {
    expect(InsightIntentSchema.safeParse(VALID_BASE).success).toBe(true);
  });
});

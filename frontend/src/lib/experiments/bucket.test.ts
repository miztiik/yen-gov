// Vitest — local OSS-style A/B bucket helper.
//
// Pure helpers; no DOM. The cookie-aware `ensureVisitorId` is
// covered by the SSR fallback case (vitest is node-env without
// jsdom); browser-side persistence is asserted in Playwright in
// `e2e/composition-bar-mount.spec.ts`.

import { describe, expect, it } from "vitest";

import {
  VISITOR_ID_COOKIE,
  VISITOR_ID_TTL_DAYS,
  bucketFor,
  bucketForWithOverride,
  deterministicHash,
  ensureVisitorId,
  evaluateRule,
  isInTargeting,
  pickVariation,
  type ExperimentDefinition,
  type ExperimentTargetingRule,
} from "./bucket";

const TEST_EXPERIMENT: ExperimentDefinition = {
  experiment_id: "test-exp",
  feature_key: "test.flag",
  hash_attribute: "visitor_id",
  stickiness: "cookie",
  status: "running",
  variations: [
    { id: "control", key: "0", name: "Control", weight: 0.5 },
    { id: "treatment", key: "1", name: "Treatment", weight: 0.5 },
  ],
  targeting: {
    namespace: null,
    rules: [
      {
        id: "rollout-states",
        description: "test",
        condition: { state_code: { $in: ["S05", "S07"] } },
        enabled: true,
      },
    ],
  },
};

describe("deterministicHash", () => {
  it("returns the same hash for the same input", () => {
    expect(deterministicHash("hello")).toBe(deterministicHash("hello"));
  });

  it("returns different hashes for different inputs", () => {
    expect(deterministicHash("a")).not.toBe(deterministicHash("b"));
  });

  it("returns an unsigned 32-bit integer", () => {
    const h = deterministicHash("any-input");
    expect(h).toBeGreaterThanOrEqual(0);
    expect(h).toBeLessThan(2 ** 32);
    expect(Number.isInteger(h)).toBe(true);
  });
});

describe("pickVariation — 50/50 split", () => {
  it("returns one of the two variations", () => {
    const v = pickVariation("user-1", TEST_EXPERIMENT);
    expect(["control", "treatment"]).toContain(v.id);
  });

  it("is deterministic on visitor_id + experiment_id", () => {
    const v1 = pickVariation("user-42", TEST_EXPERIMENT);
    const v2 = pickVariation("user-42", TEST_EXPERIMENT);
    expect(v1.id).toBe(v2.id);
  });

  it("splits the population approximately 50/50 across many users", () => {
    let treatment = 0;
    const N = 1000;
    for (let i = 0; i < N; i++) {
      const v = pickVariation(`user-${i}`, TEST_EXPERIMENT);
      if (v.id === "treatment") treatment++;
    }
    // Expect ~500 ± 50 (2σ for a binomial p=0.5 n=1000).
    expect(treatment).toBeGreaterThan(400);
    expect(treatment).toBeLessThan(600);
  });

  it("falls back to first variation when all weights are zero", () => {
    const zeroed: ExperimentDefinition = {
      ...TEST_EXPERIMENT,
      variations: TEST_EXPERIMENT.variations.map(v => ({ ...v, weight: 0 })),
    };
    const v = pickVariation("user-1", zeroed);
    expect(v.id).toBe("control");
  });

  it("throws when there are zero variations", () => {
    const empty: ExperimentDefinition = {
      ...TEST_EXPERIMENT,
      variations: [],
    };
    expect(() => pickVariation("user-1", empty)).toThrow();
  });
});

describe("evaluateRule — $in operator", () => {
  const rule: ExperimentTargetingRule = {
    id: "r1",
    description: "test",
    condition: { state_code: { $in: ["S05", "S07"] } },
    enabled: true,
  };

  it("returns true when the value is in the allowed list", () => {
    expect(evaluateRule(rule, { state_code: "S05" })).toBe(true);
    expect(evaluateRule(rule, { state_code: "S07" })).toBe(true);
  });

  it("returns false when the value is not in the allowed list", () => {
    expect(evaluateRule(rule, { state_code: "S22" })).toBe(false);
  });

  it("returns false when the attribute is missing", () => {
    expect(evaluateRule(rule, {})).toBe(false);
  });

  it("returns false when the rule is disabled", () => {
    expect(
      evaluateRule({ ...rule, enabled: false }, { state_code: "S05" }),
    ).toBe(false);
  });
});

describe("isInTargeting", () => {
  it("returns true when at least one rule matches", () => {
    expect(
      isInTargeting(TEST_EXPERIMENT, { state_code: "S05" }),
    ).toBe(true);
  });

  it("returns false when no rule matches", () => {
    expect(
      isInTargeting(TEST_EXPERIMENT, { state_code: "S22" }),
    ).toBe(false);
  });

  it("returns true when there are zero rules (always-on)", () => {
    const open: ExperimentDefinition = {
      ...TEST_EXPERIMENT,
      targeting: { namespace: null, rules: [] },
    };
    expect(isInTargeting(open, { state_code: "S22" })).toBe(true);
  });
});

describe("bucketFor", () => {
  it("returns a variation id when in targeting + running", () => {
    const id = bucketFor(TEST_EXPERIMENT, { state_code: "S05" }, "user-1");
    expect(["control", "treatment"]).toContain(id);
  });

  it("returns null when not in targeting (TN per plan R-02)", () => {
    const id = bucketFor(TEST_EXPERIMENT, { state_code: "S22" }, "user-1");
    expect(id).toBeNull();
  });

  it("returns null when the experiment status is not 'running'", () => {
    const stopped: ExperimentDefinition = { ...TEST_EXPERIMENT, status: "stopped" };
    const id = bucketFor(stopped, { state_code: "S05" }, "user-1");
    expect(id).toBeNull();
  });

  it("returns the same bucket for the same visitor + experiment (sticky)", () => {
    const a = bucketFor(TEST_EXPERIMENT, { state_code: "S05" }, "user-42");
    const b = bucketFor(TEST_EXPERIMENT, { state_code: "S05" }, "user-42");
    expect(a).toBe(b);
  });
});

describe("ensureVisitorId — vitest SSR fallback", () => {
  it("returns a stable test-only id when document is undefined", () => {
    // vitest node-env has no document; the helper falls back to a
    // sentinel so callers never crash.
    expect(typeof document).toBe("undefined");
    expect(ensureVisitorId()).toBe("ssr-non-persistent");
  });
});

describe("module constants", () => {
  it("uses the `yg_` cookie prefix", () => {
    expect(VISITOR_ID_COOKIE).toBe("yg_visitor_id");
  });

  it("uses a 365-day TTL", () => {
    expect(VISITOR_ID_TTL_DAYS).toBe(365);
  });
});

describe("bucketForWithOverride — vitest SSR fallback", () => {
  it("delegates to bucketFor when no DOM is available", () => {
    // vitest is node-env; `window`/`document` are undefined so
    // `readOverride` short-circuits and the helper returns the same
    // value `bucketFor` would.
    const expected = bucketFor(
      TEST_EXPERIMENT,
      { state_code: "S05" },
      "user-1",
    );
    const actual = bucketForWithOverride(
      TEST_EXPERIMENT,
      { state_code: "S05" },
      "user-1",
    );
    expect(actual).toBe(expected);
  });

  it("still honours targeting (TN excluded per plan R-02)", () => {
    expect(
      bucketForWithOverride(
        TEST_EXPERIMENT,
        { state_code: "S22" },
        "user-1",
      ),
    ).toBeNull();
  });
});

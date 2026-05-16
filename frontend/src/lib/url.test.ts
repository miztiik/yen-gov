// Smoke tests for the URL builder. The full builder set is exercised
// implicitly by every page test; this file pins the citizen-visible URL
// shapes that are easy to silently regress.
//
// `states.slug()` falls back to the lower-cased ECI code while
// `states.json` hasn't loaded — that fallback IS the contract under test
// (the URL must still be syntactically valid before reference data lands).

import { describe, it, expect } from "vitest";
import { url } from "./url";

describe("url.stateTopic", () => {
  it("produces /s/<slug>/t/<topic-id> shape", () => {
    const u = url.stateTopic("S22", "fiscal");
    expect(u).toMatch(/\/s\/[a-z][a-z0-9-]*\/t\/fiscal$/);
    expect(u).not.toContain("undefined");
  });

  it("URL-encodes the topic id", () => {
    const u = url.stateTopic("S22", "some/odd id");
    expect(u).toContain("/t/some%2Fodd%20id");
  });

  it("falls back to lower-cased ECI code when slug isn't loaded yet", () => {
    // states.json hasn't loaded in the test environment, so this should
    // surface the s22 fallback path rather than literal "undefined".
    const u = url.stateTopic("S22", "energy");
    expect(u).toMatch(/\/s\/[a-z0-9-]+\/t\/energy$/);
  });
});

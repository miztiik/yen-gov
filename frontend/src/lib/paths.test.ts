// Contract test for `paths.ts`: the runtime URL prefix that every data
// loader composes against. If this drifts from what `vite.config.ts`
// serves under `/data/...` in dev, OR from what the deploy script
// uploads under `${BASE_URL}data/...` in prod, every fetch in the app
// silently 404s. The test is one assertion deep on purpose — it pins
// the contract, not the implementation.

import { describe, expect, test } from "vitest";
import { DATA_BASE } from "./paths";

describe("DATA_BASE", () => {
  test("composes import.meta.env.BASE_URL + 'data' with no double slash", () => {
    // Vitest inherits the same Vite config, so BASE_URL is "/" in tests.
    // The contract: DATA_BASE always starts with BASE_URL and ends in
    // "data" (no trailing slash — call sites add the path themselves).
    expect(DATA_BASE.endsWith("data")).toBe(true);
    expect(DATA_BASE.startsWith(import.meta.env.BASE_URL)).toBe(true);
    // No double slash anywhere in the prefix.
    expect(DATA_BASE).not.toMatch(/\/\//);
  });

  test("is safe to concatenate with a leading-slash path", () => {
    const composed = `${DATA_BASE}/elections/AcGenMay2026/S22/result.summary.json`;
    expect(composed).not.toMatch(/\/\//);
    expect(composed).toMatch(/\/data\/elections\/AcGenMay2026\/S22\/result\.summary\.json$/);
  });
});

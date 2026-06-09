// Pure-transform contract for the Grammar B -> Grammar A path rewrite
// shipped by PR-P1 of the URL prefix-drop plan
// (TODO/20260609-url-prefix-drop-phase0-plan.md / ADR-0037 Phase 2-4).
//
// `rewriteLegacyPath` is the deterministic core of
// `routes/RedirectLegacyUrl.svelte`. The on-mount caller does the I/O
// (read window.location, history.replaceState, dispatch popstate);
// this test covers only the path transform. The end-to-end behaviour
// (URL bar flips + the new route renders) is covered by the Playwright
// spec `frontend/e2e/url-prefix-drop.spec.ts`.

import { describe, it, expect } from "vitest";
import { rewriteLegacyPath } from "./redirect-legacy-url";

describe("rewriteLegacyPath - Grammar B -> Grammar A", () => {
  it("rewrites a bare state hub", () => {
    expect(rewriteLegacyPath("/s/tamil-nadu")).toBe("/tamil-nadu");
  });

  it("rewrites a state topic page", () => {
    expect(rewriteLegacyPath("/s/tamil-nadu/t/elections")).toBe(
      "/tamil-nadu/t/elections",
    );
  });

  it("rewrites a state-election landing", () => {
    expect(
      rewriteLegacyPath("/s/karnataka/elections/AcGenMay2023"),
    ).toBe("/karnataka/elections/AcGenMay2023");
  });

  it("rewrites a nested AC URL preserving the numeric-prefixed slug", () => {
    // PR-P1 deliberately does NOT collapse `1-bastar` -> `bastar`.
    // PR-P2 ships the AC slug shape change as part of the caller-migration sweep.
    expect(
      rewriteLegacyPath("/s/chhattisgarh/elections/AcGenNov2023/ac/1-bastar"),
    ).toBe("/chhattisgarh/elections/AcGenNov2023/ac/1-bastar");
  });

  it("rewrites a party page", () => {
    expect(rewriteLegacyPath("/s/karnataka/party/inc-inc")).toBe(
      "/karnataka/party/inc-inc",
    );
  });

  it("rewrites the bare-AC convenience entry", () => {
    expect(rewriteLegacyPath("/s/tamil-nadu/ac/167-mylapore")).toBe(
      "/tamil-nadu/ac/167-mylapore",
    );
  });

  it("rewrites a per-state district URL", () => {
    expect(rewriteLegacyPath("/s/tamil-nadu/d/chennai")).toBe(
      "/tamil-nadu/d/chennai",
    );
  });

  it("rewrites a per-state explore URL", () => {
    expect(rewriteLegacyPath("/s/maharashtra/explore")).toBe(
      "/maharashtra/explore",
    );
  });

  it("collapses degenerate /s/ to root", () => {
    expect(rewriteLegacyPath("/s/")).toBe("/");
  });

  it("collapses degenerate /s (no trailing slash) to root", () => {
    expect(rewriteLegacyPath("/s")).toBe("/");
  });

  it("returns non-/s/ paths unchanged (defensive)", () => {
    // The router only mounts the redirect on `/s/*` matches, but the
    // pure-function contract must be safe under any input.
    expect(rewriteLegacyPath("/tamil-nadu")).toBe("/tamil-nadu");
    expect(rewriteLegacyPath("/about")).toBe("/about");
    expect(rewriteLegacyPath("/compare/karnataka/AcGenMay2023")).toBe(
      "/compare/karnataka/AcGenMay2023",
    );
    expect(rewriteLegacyPath("/")).toBe("/");
  });

  it("never introduces a double slash at the rewrite boundary", () => {
    // Negative invariant - the `slice(2)` keeps the leading `/` of the
    // state segment; if that drift ever lands, citizens get `//...`.
    for (const grammar_b of [
      "/s/tamil-nadu",
      "/s/karnataka/elections/AcGenMay2023",
      "/s/chhattisgarh/elections/x/ac/1-bastar",
    ]) {
      expect(rewriteLegacyPath(grammar_b)).not.toMatch(/\/\//);
    }
  });
});

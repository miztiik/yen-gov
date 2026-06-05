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

// Canonical URL grammar contract (audit-driven, post-IA-reset).
//
// Each builder MUST emit one of the canonical patterns from the URL
// grammar handover. The router (frontend/src/main.ts) declares the
// matching routes; this test locks the pairing so a builder regression
// can't silently route citizens through a non-canonical shape.
//
// Patterns:
//   /
//   /s/<state>
//   /s/<state>/ac/<ac>
//   /s/<state>/party/<party>
//   /s/<state>/explore
//   /s/<state>/t/<topic>
//   /lab/<state>/<event>
//   /compare/<state>/<event>
//   /compare[?i=…&states=…&peer=…]
//   /t
//   /t/<topic>
//   /about
//   /settings
//   /disclaimer
//   /data-completeness
//
// The `<state>` token is the citizen-readable slug when states.json has
// loaded (`tamil-nadu`), or the lower-cased ECI code fallback (`s22`)
// before then — both shapes are covered by [a-z0-9-]+. ECI-code
// uppercase (`S22`) and Hive partition form (`tamil-nadu`) are NEVER emitted
// in URLs (the Hive form lives only in Parquet/GeoJSON partition paths).
describe("canonical URL grammar", () => {
  it("home is /", () => {
    expect(url.home()).toBe("/");
  });

  it("about is /about (with optional ?section= encoded)", () => {
    expect(url.about()).toBe("/about");
    expect(url.about("methods")).toBe("/about?section=methods");
  });

  it("settings is /settings", () => {
    expect(url.settings()).toBe("/settings");
  });

  it("disclaimer is /disclaimer", () => {
    expect(url.disclaimer()).toBe("/disclaimer");
  });

  it("dataCompleteness is /data-completeness", () => {
    expect(url.dataCompleteness()).toBe("/data-completeness");
  });

  it("topics index is /t", () => {
    expect(url.topics()).toBe("/t");
  });

  it("topic is /t/<topic>", () => {
    expect(url.topic("energy")).toBe("/t/energy");
  });

  it("state is /s/<state>", () => {
    expect(url.state("S22")).toMatch(/^\/s\/[a-z0-9-]+$/);
  });

  it("district is /s/<state>/d/<slug>", () => {
    expect(url.district("S22", "coimbatore")).toMatch(/^\/s\/[a-z0-9-]+\/d\/coimbatore$/);
  });

  it("district passes through an LGD state slug as the state segment", () => {
    expect(url.district("tamil-nadu", "coimbatore")).toBe("/s/tamil-nadu/d/coimbatore");
  });

  it("ac is /s/<state>/ac/<eci_no-name-slug>", () => {
    expect(url.ac("S22", 167, "Mylapore")).toMatch(/^\/s\/[a-z0-9-]+\/ac\/167-mylapore$/);
  });

  it("ac nests the event in the path (ADR-0052)", () => {
    expect(url.ac("S22", 167, "Mylapore", "AcGenMar1971"))
      .toMatch(/^\/s\/[a-z0-9-]+\/elections\/AcGenMar1971\/ac\/167-mylapore$/);
  });

  it("acByNo is /s/<state>/ac/<eci_no>", () => {
    expect(url.acByNo("S22", 167)).toMatch(/^\/s\/[a-z0-9-]+\/ac\/167$/);
  });

  it("acByNo nests the event in the path (ADR-0052)", () => {
    expect(url.acByNo("S22", 167, "AcGenMar1971"))
      .toMatch(/^\/s\/[a-z0-9-]+\/elections\/AcGenMar1971\/ac\/167$/);
  });

  it("party is /s/<state>/party/<slug>-<eci-code-lower>", () => {
    expect(url.party("S22", "DMK", "DMK")).toMatch(/^\/s\/[a-z0-9-]+\/party\/dmk-dmk$/);
  });

  it("explore is /s/<state>/explore", () => {
    expect(url.explore("S22")).toMatch(/^\/s\/[a-z0-9-]+\/explore$/);
  });

  it("lab is /lab/<state>/<event>", () => {
    expect(url.lab("S22", "AcGenMay2026")).toMatch(/^\/lab\/[a-z0-9-]+\/AcGenMay2026$/);
  });

  it("compare (election results) is /compare/<state>/<event>", () => {
    expect(url.compare("S22", "AcGenMay2026")).toMatch(/^\/compare\/[a-z0-9-]+\/AcGenMay2026$/);
  });

  it("compareIndicator is /compare (no querystring when empty)", () => {
    expect(url.compareIndicator()).toBe("/compare");
  });

  it("compareIndicator emits ?i=…&states=…&peer=… when provided", () => {
    expect(
      url.compareIndicator({ indicator: "state-gsdp-current-inr-crore", states: ["S22", "S07"], peer: "south" }),
    ).toBe("/compare?i=state-gsdp-current-inr-crore&states=S22%2CS07&peer=south");
  });

  // Negative assertions — these shapes are explicitly NOT canonical and
  // must never appear in any builder's output. (Audit found zero
  // occurrences on main; this test locks that invariant.)
  it.each([
    ["url.state", url.state("S22")],
    ["url.district", url.district("S22", "coimbatore")],
    ["url.ac", url.ac("S22", 167, "Mylapore")],
    ["url.acByNo", url.acByNo("S22", 167)],
    ["url.party", url.party("S22", "DMK", "DMK")],
    ["url.explore", url.explore("S22")],
    ["url.lab", url.lab("S22", "AcGenMay2026")],
    ["url.compare", url.compare("S22", "AcGenMay2026")],
    ["url.stateTopic", url.stateTopic("S22", "energy")],
  ])("%s never emits the uppercase ECI code form (S22 / U08)", (_label, u) => {
    expect(u).not.toMatch(/\/S\d{2}\b/);
    expect(u).not.toMatch(/\/U\d{2}\b/);
  });

  it.each([
    ["url.state", url.state("S22")],
    ["url.district", url.district("S22", "coimbatore")],
    ["url.ac", url.ac("S22", 167, "Mylapore")],
    ["url.stateTopic", url.stateTopic("S22", "energy")],
  ])("%s never emits the Hive partition form (in_s<NN>) — that's a data-layer concern", (_label, u) => {
    expect(u).not.toContain("in_s");
    expect(u).not.toContain("in_u");
  });

  it.each([
    ["url.home", url.home()],
    ["url.about", url.about()],
    ["url.topics", url.topics()],
    ["url.topic", url.topic("energy")],
    ["url.state", url.state("S22")],
    ["url.district", url.district("S22", "coimbatore")],
    ["url.ac", url.ac("S22", 167, "Mylapore")],
    ["url.acByNo", url.acByNo("S22", 167)],
    ["url.party", url.party("S22", "DMK", "DMK")],
    ["url.explore", url.explore("S22")],
    ["url.stateTopic", url.stateTopic("S22", "energy")],
    ["url.lab", url.lab("S22", "AcGenMay2026")],
    ["url.compare", url.compare("S22", "AcGenMay2026")],
  ])("%s never emits the legacy /state/<code> or /india/<topic> shape", (_label, u) => {
    expect(u).not.toContain("/state/");
    expect(u).not.toContain("/india/");
  });
});


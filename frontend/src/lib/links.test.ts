// Grammar A shape contract — pins the URLs `links.ts` emits for every
// builder. The router (frontend/src/main.ts) will declare matching routes
// in Phase 2; this test is the floor that prevents a Phase 1 links.ts
// builder from emitting Grammar B by accident.
//
// Why a separate file from `url.test.ts`: `url.ts` tests the live Grammar
// B shape (locked by PR #172). This file tests Grammar A on the parallel
// `links.ts` module. Both contracts coexist through Phase 4; once Phase 4
// deletes `url.ts`, this file becomes the only URL-shape contract.
//
// See ADR-0037 for the binding decision and the four-phase plan.

import { describe, it, expect } from "vitest";
import { link, RESERVED_PATH_TOKENS } from "./links";

// `states.svelte.ts` falls back to the lower-cased input when the entity
// registry hasn't loaded — that fallback IS the contract under test (the
// URL must still be syntactically valid before reference data lands).

describe("Grammar A — links.ts builder shapes (ADR-0037)", () => {
  it("home is /", () => {
    expect(link.home()).toBe("/");
  });

  it("stateHub is /<state-slug>, never /s/<…>, never /india/<…>", () => {
    const u = link.stateHub("S22");
    expect(u).toMatch(/^\/[a-z][a-z0-9-]*$/);
    expect(u).not.toMatch(/^\/s\//);
    expect(u).not.toMatch(/^\/india\//);
    expect(u).not.toContain("undefined");
  });

  it("acDeepLink is /<state>/<ac-name>, no `167-` numeric prefix", () => {
    const u = link.acDeepLink("S22", "Mylapore");
    expect(u).toMatch(/^\/[a-z0-9-]+\/mylapore$/);
    expect(u).not.toMatch(/\/ac\//);
    expect(u).not.toMatch(/\/\d+-/);
  });

  it("acDeepLink normalises diacritics via slugify", () => {
    // "Mylāpore" → "mylapore" — same NFKD strip as slug.ts.
    const u = link.acDeepLink("S22", "Mylāpore");
    expect(u).toMatch(/\/mylapore$/);
  });

  it("nationalIndicator is /<indicator-slug>", () => {
    expect(link.nationalIndicator("installed-capacity")).toMatch(
      /^\/installed-capacity$/,
    );
  });

  it("stateIndicator is /<state>/<indicator>", () => {
    const u = link.stateIndicator("S22", "installed-capacity");
    expect(u).toMatch(/^\/[a-z0-9-]+\/installed-capacity$/);
    expect(u).not.toMatch(/^\/s\//);
  });

  it("acIndicator is /<state>/<ac>/<indicator>", () => {
    const u = link.acIndicator("S22", "Mylapore", "installed-capacity");
    expect(u).toMatch(/^\/[a-z0-9-]+\/mylapore\/installed-capacity$/);
  });

  it("topicsIndex is /t", () => {
    expect(link.topicsIndex()).toBe("/t");
  });

  it("topicLanding is /t/<topic> (encoded)", () => {
    expect(link.topicLanding("energy")).toBe("/t/energy");
    expect(link.topicLanding("some/odd id")).toBe("/t/some%2Fodd%20id");
  });

  it("stateTopic is /<state>/t/<topic>", () => {
    const u = link.stateTopic("S22", "energy");
    expect(u).toMatch(/^\/[a-z0-9-]+\/t\/energy$/);
    expect(u).not.toMatch(/^\/s\//);
  });

  it("stateExplore is /<state>/explore", () => {
    const u = link.stateExplore("S22");
    expect(u).toMatch(/^\/[a-z0-9-]+\/explore$/);
  });

  it("partyInState is /<state>/party/<slug>", () => {
    const u = link.partyInState("S22", "dmk-aiadmk");
    expect(u).toMatch(/^\/[a-z0-9-]+\/party\/dmk-aiadmk$/);
  });

  it("electionLab is /lab/<state>/<event> (unchanged from url.ts)", () => {
    const u = link.electionLab("S22", "AcGenMay2026");
    expect(u).toMatch(/^\/lab\/[a-z0-9-]+\/AcGenMay2026$/);
  });

  it("electionCompare is /compare/<state>/<event> (unchanged from url.ts)", () => {
    const u = link.electionCompare("S22", "AcGenMay2026");
    expect(u).toMatch(/^\/compare\/[a-z0-9-]+\/AcGenMay2026$/);
  });

  it("about / settings / disclaimer / dataCompleteness are chrome at root", () => {
    expect(link.about()).toBe("/about");
    expect(link.about("methods")).toBe("/about?section=methods");
    expect(link.settings()).toBe("/settings");
    expect(link.disclaimer()).toBe("/disclaimer");
    expect(link.dataCompleteness()).toBe("/data-completeness");
  });
});

describe("Grammar A — reserved-path-token set (ADR-0037)", () => {
  it("includes every chrome surface links.ts emits", () => {
    const chromeSurfaces = [
      link.topicsIndex(),
      link.about(),
      link.settings(),
      link.disclaimer(),
      link.dataCompleteness(),
    ];
    for (const surface of chromeSurfaces) {
      const firstSegment = surface.replace(/^\//, "").split(/[/?]/)[0]!;
      expect(RESERVED_PATH_TOKENS).toContain(firstSegment as never);
    }
  });

  it("retains the Phase-4b legacy redirect anchors (s, ac, party)", () => {
    for (const anchor of ["s", "ac", "party"] as const) {
      expect(RESERVED_PATH_TOKENS).toContain(anchor as never);
    }
  });

  it("pre-reserves the future indicator-marker `i` (Max's retrofit safety net)", () => {
    expect(RESERVED_PATH_TOKENS).toContain("i" as never);
  });

  it("never overlaps with the lowercase ISO state codes / Hive form", () => {
    // Hive form `tamil-nadu` and ECI lowercase `s22` must NEVER be reserved
    // (would prevent a real state slug from landing). The reservation
    // set is structural tokens only.
    for (const token of RESERVED_PATH_TOKENS) {
      expect(token).not.toMatch(/^in_s\d+$/i);
      expect(token).not.toMatch(/^s\d+$/i);
    }
  });
});

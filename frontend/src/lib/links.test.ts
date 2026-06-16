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

  it("parties index is /parties (ADR-0053)", () => {
    expect(link.parties()).toBe("/parties");
  });

  it("party builds /parties/<lowercased-party_id-tail> (ADR-0053)", () => {
    // Bare-tail shape: party_id `parties.IN.INC` -> `/parties/inc`.
    expect(link.party("parties.IN.INC")).toBe("/parties/inc");
    expect(link.party("parties.IN.BJP")).toBe("/parties/bjp");
    expect(link.party("parties.IN.DMK")).toBe("/parties/dmk");
    expect(link.party("parties.IN.AIADMK")).toBe("/parties/aiadmk");
    expect(link.party("parties.IN.YSRCP")).toBe("/parties/ysrcp");
  });

  it("party rewrites underscored tails to dashes", () => {
    expect(link.party("parties.IN.BSP_A")).toBe("/parties/bsp-a");
    expect(link.party("parties.IN.CPI_ML_L")).toBe("/parties/cpi-ml-l");
    expect(link.party("parties.IN.SHS_UBT")).toBe("/parties/shs-ubt");
  });

  it("party applies sentinel and namespace-collision overrides", () => {
    expect(link.party("parties.IN.IND")).toBe("/parties/independent");
    expect(link.party("parties.IN.NOTA")).toBe("/parties/nota");
    expect(link.party("parties.IN.AC")).toBe("/parties/arunachal-congress");
    expect(link.party("parties.IN.GOA")).toBe("/parties/goemcarancho-otrec-astro");
    expect(link.party("parties.IN.JIND")).toBe("/parties/jind-party");
    expect(link.party("parties.IN.MAHAD")).toBe("/parties/mahakranti-dal");
  });

  it("party returns null for the UNK resolver-fallback sentinel", () => {
    // UNK has no citizen page; the caller MUST fall back to plain
    // text rendering of `party_short_raw` (no-silent-demotion rule).
    expect(link.party("parties.IN.UNK")).toBeNull();
  });

  it("party returns null for empty / null / undefined input", () => {
    expect(link.party(null)).toBeNull();
    expect(link.party(undefined)).toBeNull();
    expect(link.party("")).toBeNull();
  });

  it("party never emits a leading /s/ or /india/ prefix", () => {
    const u = link.party("parties.IN.INC");
    expect(u).not.toMatch(/^\/s\//);
    expect(u).not.toMatch(/^\/india\//);
  });

  it("ac is /<state>/ac/<name-slug> (no numeric prefix)", () => {
    const u = link.ac("S22", "Mylapore");
    expect(u).toMatch(/^\/[a-z0-9-]+\/ac\/mylapore$/);
    expect(u).not.toMatch(/\/\d+-/);
    expect(u).not.toMatch(/^\/s\//);
  });

  it("ac nests the event in the path when supplied (ADR-0052)", () => {
    const u = link.ac("S22", "Mylapore", "AcGenMar1971");
    expect(u).toMatch(/^\/[a-z0-9-]+\/elections\/AcGenMar1971\/ac\/mylapore$/);
  });

  it("ac slugifies diacritics in AC names", () => {
    expect(link.ac("S22", "Mylāpore")).toMatch(/\/ac\/mylapore$/);
  });

  it("acByNo is /<state>/ac/<eci_no>", () => {
    expect(link.acByNo("S22", 167)).toMatch(/^\/[a-z0-9-]+\/ac\/167$/);
  });

  it("acByNo nests the event in the path when supplied (ADR-0052)", () => {
    expect(link.acByNo("S22", 167, "AcGenMar1971")).toMatch(
      /^\/[a-z0-9-]+\/elections\/AcGenMar1971\/ac\/167$/,
    );
  });

  // PR-8b D8a: link.pc() mirrors link.ac() for parliamentary
  // constituencies but routes to the bare-slug W3b shape at
  // main.ts:321 (`/:state/elections/:event/:constituency`), where
  // PC vs AC is dispatched by the event prefix (`general-` -> PC,
  // `assembly-` -> AC). Unlike link.ac() there is no `/pc/` literal
  // segment - the constituency is positional.
  it("pc is /<state>/elections/<event>/<pc-slug> (bare-slug, no /pc/ marker)", () => {
    const u = link.pc("S22", "general-2024", "chennai-central");
    expect(u).toMatch(
      /^\/[a-z0-9-]+\/elections\/general-2024\/chennai-central$/,
    );
    expect(u).not.toMatch(/\/pc\//);
    expect(u).not.toMatch(/^\/s\//);
  });

  it("pc URL-encodes the event segment", () => {
    // event ids are kebab-case in W2a doctrinal form so encoding is
    // a no-op in practice, but the contract still holds for any caller
    // that hands in an exotic id.
    const u = link.pc("S22", "general 2024", "chennai-central");
    expect(u).toMatch(
      /^\/[a-z0-9-]+\/elections\/general%202024\/chennai-central$/,
    );
  });

  it("pc accepts both ECI state code and LGD slug (fallback path)", () => {
    // `stateSlug` does a `states.slug(...)` lookup against the
    // catalogue then falls back to `toLowerCase()` if unresolved.
    // In vitest the catalogue is not loaded so both surfaces emit
    // through the lowercase-fallback path - the contract here is
    // simply that neither input throws + both produce a 4-segment
    // URL of the right shape. The runtime catalogue-resolved
    // canonical slug is asserted by the §13 browser smoke.
    const fromCode = link.pc("S22", "general-2024", "chennai-central");
    const fromSlug = link.pc(
      "tamil-nadu",
      "general-2024",
      "chennai-central",
    );
    expect(fromCode).toMatch(
      /^\/[a-z0-9-]+\/elections\/general-2024\/chennai-central$/,
    );
    expect(fromSlug).toMatch(
      /^\/[a-z0-9-]+\/elections\/general-2024\/chennai-central$/,
    );
  });

  it("pc is prefixed with the deploy BASE_URL", () => {
    // BASE_URL is `/` in vitest (vite.config defaults); production
    // ships with `/yen-gov/`. The `withBase` invariant is shared
    // with link.ac() and the other builders.
    const u = link.pc("S22", "general-2024", "chennai-central");
    expect(u.startsWith("/")).toBe(true);
  });

  it("district is /<state>/<slug> (positional, no `/d/` marker)", () => {
    // Deferral 1 of TODO/20260609-url-prefix-drop-phase0-plan.md
    // (Jony's verdict) dropped the `/d/` literal marker. The router
    // now dispatches via StateSubRouter at `/:state/:position2`.
    // Under Option A (2026-06-10) the dispatcher resolves
    // district-first per Jony rule #4; on a same-slug collision the
    // AC stays reachable via the canonical event-nested URL
    // `/<state>/elections/<event>/ac/<ac>` (ADR-0052).
    expect(link.district("S22", "coimbatore")).toMatch(
      /^\/[a-z0-9-]+\/coimbatore$/,
    );
    expect(link.district("S22", "coimbatore")).not.toMatch(/^\/s\//);
    expect(link.district("S22", "coimbatore")).not.toMatch(/\/d\//);
  });

  it("district passes through an LGD state slug as the state segment", () => {
    expect(link.district("tamil-nadu", "coimbatore")).toBe(
      "/tamil-nadu/coimbatore",
    );
  });

  it("stateElection is /<state>/elections/<event>", () => {
    const u = link.stateElection("S22", "AcGenMay2026");
    expect(u).toMatch(/^\/[a-z0-9-]+\/elections\/AcGenMay2026$/);
    expect(u).not.toMatch(/^\/s\//);
  });

  it("stateElection URL-encodes the event id", () => {
    expect(link.stateElection("S22", "Ac Gen 2026")).toContain(
      "/elections/Ac%20Gen%202026",
    );
  });

  it("electionLab is /lab/<state>/<event> (unchanged from url.ts)", () => {
    const u = link.electionLab("S22", "AcGenMay2026");
    expect(u).toMatch(/^\/lab\/[a-z0-9-]+\/AcGenMay2026$/);
  });

  it("labMethod is /lab/<state>/<event>/m/<method>", () => {
    expect(link.labMethod("S22", "AcGenMay2026", "fptp")).toMatch(
      /^\/lab\/[a-z0-9-]+\/AcGenMay2026\/m\/fptp$/,
    );
  });

  // PR-W5a (2026-06-10): `electionCompare` + `compareMethod` link tests
  // retired. The corresponding link builders were deleted in this PR
  // alongside the legacy `/compare/:state/:event` and
  // `/compare/:state/:event/m/:method` routes; the new path-form
  // `compareElections` builder + its test below is the replacement.

  it("compareIndicator is /compare with no querystring when empty", () => {
    expect(link.compareIndicator()).toBe("/compare");
    expect(link.compareIndicator({})).toBe("/compare");
  });

  it("compareIndicator emits ?i=…&states=…&peer=… when provided", () => {
    expect(
      link.compareIndicator({
        indicator: "state-gsdp-current-inr-crore",
        states: ["S22", "S07"],
        peer: "south",
      }),
    ).toBe(
      "/compare?i=state-gsdp-current-inr-crore&states=S22%2CS07&peer=south",
    );
  });

  it("indicatorDoc is /docs/indicator/<topic>/<id>", () => {
    expect(link.indicatorDoc("fiscal/outstanding_debt_pct_gsdp")).toBe(
      "/docs/indicator/fiscal/outstanding_debt_pct_gsdp",
    );
  });

  it("indicatorDoc preserves the catalogue-key slash (NOT URL-encoded)", () => {
    const u = link.indicatorDoc("environment/state_pm25_annual_mean_ug_m3");
    expect(u).toContain(
      "/docs/indicator/environment/state_pm25_annual_mean_ug_m3",
    );
    expect(u).not.toContain("%2F");
  });

  it("docsLabMethod is /docs/lab/<method>", () => {
    expect(link.docsLabMethod("fptp")).toBe("/docs/lab/fptp");
  });

  it("about / settings / disclaimer / dataCompleteness are chrome at root", () => {
    expect(link.about()).toBe("/about");
    expect(link.about("methods")).toBe("/about?section=methods");
    expect(link.settings()).toBe("/settings");
    expect(link.disclaimer()).toBe("/disclaimer");
    expect(link.dataCompleteness()).toBe("/data-completeness");
  });
});

describe("Grammar A — reserved-path-token set (ADR-0037 + ADR-0053)", () => {
  it("includes every chrome surface links.ts emits", () => {
    const chromeSurfaces = [
      link.topicsIndex(),
      link.about(),
      link.settings(),
      link.disclaimer(),
      link.dataCompleteness(),
      link.parties(),
    ];
    for (const surface of chromeSurfaces) {
      const firstSegment = surface.replace(/^\//, "").split(/[/?]/)[0]!;
      expect(RESERVED_PATH_TOKENS).toContain(firstSegment as never);
    }
  });

  it("reserves `parties` (plural) per ADR-0053 (PR-0 of party-rendering plan)", () => {
    // ADR-0053 (2026-06-12) reserves the top-level `parties` token for
    // the per-party page namespace at `/parties/<slug>` and the index
    // at `/parties`. The legacy singular `party` (state-scoped
    // sub-namespace marker) was REMOVED in the same PR.
    expect(RESERVED_PATH_TOKENS).toContain("parties" as never);
    expect(RESERVED_PATH_TOKENS).not.toContain("party" as never);
  });

  it("does NOT reserve `s` (PR-P4 freed the Grammar B prefix anchor)", () => {
    // PR-P4 (2026-06-10) deleted `RedirectLegacyUrl.svelte` + the `/s/*`
    // route entry, completing the 4-phase URL-prefix-drop strangler-fig.
    // The `s` token is no longer a structural marker; freeing it means
    // a state slug literally named `s` would be allowed (none exist).
    // If PR-P4 ever needs to be reverted, restore `s` to the array AND
    // re-mount RedirectLegacyUrl on `/s/*` in `main.ts`.
    expect(RESERVED_PATH_TOKENS).not.toContain("s" as never);
  });

  it("reserves `d` (Deferral 1 future escape-hatch per Jony rule #3)", () => {
    // Deferral 1 (2026-06-10) dropped the `/:state/d/:district` route
    // entry and flipped districts to positional `/<state>/<district>`.
    // Per Jony rule #3, `d` STAYS reserved so a citizen who types
    // `/<state>/d` on the address bar lands on the 404 instead of
    // being poached by a hypothetical future district named "D". To
    // revert Deferral 1, restore the route entry AND drop `d` from
    // `RESERVED_PATH_TOKENS`.
    expect(RESERVED_PATH_TOKENS).toContain("d" as never);
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

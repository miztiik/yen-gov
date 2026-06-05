// Pure-helper tests for GeoBreadcrumb.svelte's module-scoped
// `computeCrumbs`. The Svelte component itself is exercised by the
// route-level browser smoke per CLAUDE.md section 13; vitest is in
// node-env (no jsdom canvas, no @testing-library/svelte) so we cannot
// mount the component here. The pure helper covers every code path
// the renderer dispatches on.
//
// Per /memories/lessons.md ("vitest does NOT resolve the $lib SvelteKit
// alias by default"), this file uses relative imports only.

import { describe, it, expect } from "vitest";
import { computeCrumbs, type Crumb } from "./GeoBreadcrumb.svelte";

describe("computeCrumbs - Home route", () => {
  it("renders 1 India crumb as current page on /", () => {
    const crumbs = computeCrumbs({
      path: "/",
      params: {},
      stateCode: null,
      stateName: "",
    });
    expect(crumbs).toHaveLength(1);
    expect(crumbs[0]).toEqual<Crumb>({ label: "India", href: null });
  });

  it("treats empty path as Home (defensive)", () => {
    const crumbs = computeCrumbs({
      path: "",
      params: {},
      stateCode: null,
      stateName: "",
    });
    expect(crumbs).toHaveLength(1);
    expect(crumbs[0].label).toBe("India");
    expect(crumbs[0].href).toBeNull();
  });
});

describe("computeCrumbs - StateOverview route", () => {
  it("renders India (link) > State (current) on /s/<slug>", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu",
      params: { state: "tamil-nadu" },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs).toHaveLength(2);
    expect(crumbs[0]).toEqual<Crumb>({ label: "India", href: "/" });
    expect(crumbs[1]).toEqual<Crumb>({ label: "Tamil Nadu", href: null });
  });

  it("degrades to India alone when state context not yet resolved", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu",
      params: { state: "tamil-nadu" },
      stateCode: null, // states.json still loading or slug unknown
      stateName: "",
    });
    expect(crumbs).toHaveLength(1);
    expect(crumbs[0].label).toBe("India");
    // India is still a link (the leaf-current is the unresolved state,
    // which the page itself surfaces with "Loading" / "State not found").
    expect(crumbs[0].href).toBe("/");
  });
});

describe("computeCrumbs - StateTopic route", () => {
  it("renders India > State (link) > Topic (current) on /s/<slug>/t/<topic>", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu/t/fiscal",
      params: { state: "tamil-nadu", topic: "fiscal" },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs).toHaveLength(3);
    expect(crumbs[0]).toEqual<Crumb>({ label: "India", href: "/" });
    expect(crumbs[1].label).toBe("Tamil Nadu");
    expect(crumbs[1].href).toMatch(/^\/s\/[a-z0-9-]+$/);
    expect(crumbs[2]).toEqual<Crumb>({ label: "Fiscal", href: null });
  });

  it("title-cases a hyphenated topic id", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu/t/state-finance",
      params: { state: "tamil-nadu", topic: "state-finance" },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs[2].label).toBe("State Finance");
  });
});

describe("computeCrumbs - District route", () => {
  it("renders India > State (link) > District (current) on /s/<slug>/d/<district>", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu/d/coimbatore",
      params: { state: "tamil-nadu", district_slug: "coimbatore" },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs).toHaveLength(3);
    expect(crumbs[1].label).toBe("Tamil Nadu");
    expect(crumbs[1].href).toMatch(/^\/s\/[a-z0-9-]+$/);
    expect(crumbs[2]).toEqual<Crumb>({ label: "Coimbatore", href: null });
  });

  it("title-cases a multi-word district slug (north-24-parganas)", () => {
    const crumbs = computeCrumbs({
      path: "/s/west-bengal/d/north-24-parganas",
      params: { state: "west-bengal", district_slug: "north-24-parganas" },
      stateCode: "S25",
      stateName: "West Bengal",
    });
    expect(crumbs[2].label).toBe("North 24 Parganas");
  });
});

describe("computeCrumbs - Constituency route", () => {
  it("recovers AC name from `<n>-<slug>` shape on /s/<slug>/ac/<ac>", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu/ac/167-mylapore",
      params: {
        state: "tamil-nadu",
        ac_slug: "167-mylapore",
        eci_no: 167,
      },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs).toHaveLength(3);
    expect(crumbs[2]).toEqual<Crumb>({ label: "Mylapore", href: null });
  });

  it("falls back to `AC <n>` on bare-eci_no slug (no name half)", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu/ac/167",
      params: {
        state: "tamil-nadu",
        ac_slug: "167",
        eci_no: 167,
      },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs[2].label).toBe("AC 167");
  });

  it("handles the canonical nested route /s/<slug>/elections/<event>/ac/<n-slug>", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu/elections/AcGenMay2026/ac/167-mylapore",
      params: {
        state: "tamil-nadu",
        event: "AcGenMay2026",
        ac_slug: "167-mylapore",
        eci_no: 167,
      },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs).toHaveLength(3);
    expect(crumbs[2].label).toBe("Mylapore");
  });

  it("title-cases a multi-word AC name (uda-jayer-pira-style)", () => {
    const crumbs = computeCrumbs({
      path: "/s/west-bengal/ac/42-cooch-behar-uttar",
      params: {
        state: "west-bengal",
        ac_slug: "42-cooch-behar-uttar",
        eci_no: 42,
      },
      stateCode: "S25",
      stateName: "West Bengal",
    });
    expect(crumbs[2].label).toBe("Cooch Behar Uttar");
  });
});

describe("computeCrumbs - ascend href shape (canonical URL grammar)", () => {
  it("India crumb's ascend href is /", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu",
      params: { state: "tamil-nadu" },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    expect(crumbs[0].href).toBe("/");
  });

  it("State crumb's ascend href is /s/<slug> (canonical, never uppercase ECI)", () => {
    const crumbs = computeCrumbs({
      path: "/s/tamil-nadu/d/coimbatore",
      params: { state: "tamil-nadu", district_slug: "coimbatore" },
      stateCode: "S22",
      stateName: "Tamil Nadu",
    });
    const state = crumbs[1];
    expect(state.href).not.toBeNull();
    expect(state.href).toMatch(/^\/s\/[a-z0-9-]+$/);
    // The negative assertions mirror the ones in url.test.ts so a future
    // change to url.state() that regresses the grammar fails both
    // contracts symmetrically.
    expect(state.href).not.toMatch(/\/S\d{2}\b/); // no uppercase ECI
    expect(state.href).not.toContain("in_s"); // no Hive partition form
    expect(state.href).not.toContain("/state/"); // no legacy shape
  });

  it("the leaf crumb is ALWAYS the current page (href: null)", () => {
    const cases = [
      computeCrumbs({
        path: "/",
        params: {},
        stateCode: null,
        stateName: "",
      }),
      computeCrumbs({
        path: "/s/tamil-nadu",
        params: { state: "tamil-nadu" },
        stateCode: "S22",
        stateName: "Tamil Nadu",
      }),
      computeCrumbs({
        path: "/s/tamil-nadu/t/fiscal",
        params: { state: "tamil-nadu", topic: "fiscal" },
        stateCode: "S22",
        stateName: "Tamil Nadu",
      }),
      computeCrumbs({
        path: "/s/tamil-nadu/d/coimbatore",
        params: { state: "tamil-nadu", district_slug: "coimbatore" },
        stateCode: "S22",
        stateName: "Tamil Nadu",
      }),
      computeCrumbs({
        path: "/s/tamil-nadu/ac/167-mylapore",
        params: {
          state: "tamil-nadu",
          ac_slug: "167-mylapore",
          eci_no: 167,
        },
        stateCode: "S22",
        stateName: "Tamil Nadu",
      }),
    ];
    for (const crumbs of cases) {
      expect(crumbs.at(-1)?.href).toBeNull();
    }
  });
});

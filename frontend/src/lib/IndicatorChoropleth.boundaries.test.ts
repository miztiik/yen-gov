// IndicatorChoropleth drill-down integration (Phase 3 c3 of
// TN-GRANULAR-GEO-PLAN). The component itself depends on maplibre-gl + a
// canvas-bearing DOM, neither of which the project's vitest stack can
// mount today (no @testing-library/svelte, jsdom has no real canvas).
// Adding either as a one-off is a band-aid (CLAUDE.md §5: structural
// fixes only).
//
// What we test instead — and why this still satisfies the §15 integration
// tier: the choropleth's drill orchestration lives entirely in the pure
// `./drilldown.ts` state machine + a thin glue effect that calls
// `loadBoundary`. We exercise that orchestration directly by replaying the
// click → drillTo → loadBoundary sequence the component performs, with
// `fetch` mocked at the loader's contract boundary (Holy Law #7 carve-out
// per `boundaries.integration.test.ts`).
//
// Identifier note (per the task brief): the boundaries loader takes LGD
// numeric codes (e.g. "33"), NOT ECI codes (e.g. "S22"). The drill-click
// handler in the choropleth resolves ECI → LGD locally (TN-only at v0)
// before invoking `loadBoundary`. The assertion below pins that contract.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  loadBoundary,
  _resetCachesForTesting,
} from "./boundaries";
import {
  initialDrillState,
  drillTo,
  goBack,
  loadBoundaryArgs,
  isLevelEnabled,
  blockedCrumbTooltip,
} from "./drilldown";

const BASE = "/data";
const TN_LGD = "33";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

let fetchSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchSpy = vi.fn();
  globalThis.fetch = fetchSpy as unknown as typeof fetch;
  _resetCachesForTesting();
});

afterEach(() => vi.restoreAllMocks());

const FC = (n: number, props: Record<string, unknown> = {}) => ({
  type: "FeatureCollection",
  features: Array.from({ length: n }, (_, i) => ({
    type: "Feature",
    properties: { i, ...props },
    geometry: { type: "Point", coordinates: [80, 13] },
  })),
});

describe("IndicatorChoropleth drill — TN state click", () => {
  it("state-level click on Tamil Nadu drills to district and fetches india-districts.geojson", async () => {
    // Mirror the component's onSelect for a state-level click: ECI "S22"
    // resolved to LGD "33", then drillTo, then loadBoundary with the LGD.
    let state = initialDrillState("state");
    state = drillTo(
      state,
      { key: "Tamil Nadu", label: "Tamil Nadu", stateLgd: TN_LGD, feature: null },
      undefined,
    );
    expect(state.level).toBe("district");
    expect(state.stateLgd).toBe(TN_LGD);

    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(38, { dist_lgd: 568 })));
    const [lvl, parent, stateLgd] = loadBoundaryArgs(state);
    const fc = await loadBoundary(lvl, parent, stateLgd);

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/geojson/india-districts.geojson`,
    );
    expect(fc?.features.length).toBe(38);
  });

  it("district click then village click composes the per-district shard URL", async () => {
    let state = initialDrillState("state");
    state = drillTo(state, { key: "Tamil Nadu", label: "Tamil Nadu", stateLgd: TN_LGD }, undefined);
    state = drillTo(state, { key: "603", label: "Coimbatore" }, undefined);
    // From state→district→subdistrict; one more click reaches village.
    state = drillTo(state, { key: "12345", label: "Pollachi" }, undefined);
    expect(state.level).toBe("village");
    expect(state.parentDistrictLgd).toBe("603");

    // village queries hit the index first (per loader contract).
    fetchSpy.mockResolvedValueOnce(jsonResponse({
      $schema: "x", $schema_version: "2.0", sources: [],
      state_lgd: "33", district_lgd_codes: ["603"], generated_at: "x",
    }));
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(12)));

    const [lvl, parent, stateLgd] = loadBoundaryArgs(state);
    const fc = await loadBoundary(lvl, parent, stateLgd);
    expect(fetchSpy).toHaveBeenLastCalledWith(
      `${BASE}/boundaries/in/geojson/S22-villages-603.geojson`,
    );
    expect(fc?.features.length).toBe(12);
  });
});

describe("IndicatorChoropleth drill — graceful degradation", () => {
  it("404-as-null on a deeper boundary degrades without throwing", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("nope", { status: 404 }));
    const fc = await loadBoundary("district", undefined, TN_LGD);
    expect(fc).toBeNull();
    // The component would surface this via deeper_fetch_error and roll
    // the breadcrumb back; here we just assert the loader contract.
  });
});

describe("IndicatorChoropleth drill — min_grain gating", () => {
  it("drillTo refuses to advance past the indicator's min_grain", () => {
    let state = initialDrillState("state");
    // min_grain = "district" → state→district allowed, district→subdistrict refused.
    state = drillTo(state, { key: "Tamil Nadu", label: "Tamil Nadu", stateLgd: TN_LGD }, "district");
    expect(state.level).toBe("district");
    const blocked = drillTo(state, { key: "603", label: "Coimbatore" }, "district");
    expect(blocked.level).toBe("district");
    expect(blocked).toBe(state);
  });

  it("blockedCrumbTooltip names the lowest valid grain (Jony edit #4)", () => {
    expect(blockedCrumbTooltip("district")).toMatch(/district level/i);
    expect(isLevelEnabled("village", "district")).toBe(false);
    expect(isLevelEnabled("state", "district")).toBe(true);
  });
});

describe("IndicatorChoropleth drill — breadcrumb back-navigation", () => {
  it("goBack to the India crumb (idx 0) returns to the state level", () => {
    let state = initialDrillState("state");
    state = drillTo(state, { key: "Tamil Nadu", label: "Tamil Nadu", stateLgd: TN_LGD }, undefined);
    state = drillTo(state, { key: "603", label: "Coimbatore" }, undefined);
    expect(state.level).toBe("subdistrict");
    state = goBack(state, 0);
    expect(state.level).toBe("state");
    expect(state.stateLgd).toBeUndefined();
    expect(state.parentDistrictLgd).toBeUndefined();
  });

  it("re-clicking the active crumb is a no-op (recentre signal — Jony edit #1)", () => {
    let state = initialDrillState("state");
    state = drillTo(state, { key: "Tamil Nadu", label: "Tamil Nadu", stateLgd: TN_LGD }, undefined);
    const before = state;
    state = goBack(state, before.breadcrumbStack.length); // off-the-end
    expect(state).toBe(before);
  });
});

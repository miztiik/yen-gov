// Unit tests for `loadStateSilhouette` (parent plan section 25.4 E3).
// Mocks the boundary loader + `loadStates` view-model so the test runs
// in vitest node-env without touching DuckDB-WASM or HTTP. Pattern
// mirrored from `choropleth-entity-context.test.ts`.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./view-models/states", () => ({
  loadStates: vi.fn(),
}));

vi.mock("./boundaries", () => ({
  loadBoundaryFromPath: vi.fn(),
}));

import { loadStates } from "./view-models/states";
import { loadBoundaryFromPath } from "./boundaries";
import { __resetForTests, loadStateSilhouette } from "./state-silhouette";

const mockedLoadStates = vi.mocked(loadStates);
const mockedLoadBoundary = vi.mocked(loadBoundaryFromPath);

function makeFeature(state_lgd: number, stname: string): any {
  return {
    type: "Feature",
    properties: { State_LGD: state_lgd, STNAME: stname },
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [80, 10],
          [82, 10],
          [82, 13],
          [80, 13],
          [80, 10],
        ],
      ],
    },
  };
}

const STATE_ROWS = [
  {
    entity_id: "IN-S22",
    eci_code: "S22",
    display_name: "Tamil Nadu",
    boundary_join_name: "Tamil Nadu",
    boundary_join_key: "33",
    lgd_code: "33",
    iso_3166_2: "IN-TN",
  },
  {
    entity_id: "IN-S04",
    eci_code: "S04",
    display_name: "Bihar",
    boundary_join_name: "Bihar",
    boundary_join_key: "10",
    lgd_code: "10",
    iso_3166_2: "IN-BR",
  },
  {
    entity_id: "IN-U04",
    eci_code: "U04",
    display_name: "Lakshadweep",
    boundary_join_name: "Lakshadweep",
    boundary_join_key: "31",
    lgd_code: "31",
    iso_3166_2: "IN-LD",
  },
];

const STATE_FC = {
  type: "FeatureCollection" as const,
  features: [
    makeFeature(33, "TAMIL NADU"),
    makeFeature(10, "BIHAR"),
    makeFeature(31, "LAKSHADWEEP"),
    makeFeature(99, "OTHER"),
  ],
};

describe("loadStateSilhouette", () => {
  beforeEach(() => {
    mockedLoadStates.mockReset();
    mockedLoadBoundary.mockReset();
    __resetForTests();
  });

  it("returns the feature with matching State_LGD for a covered ECI code", async () => {
    mockedLoadStates.mockResolvedValue(STATE_ROWS);
    mockedLoadBoundary.mockResolvedValue({ fc: STATE_FC, format: "topojson" });

    const f = await loadStateSilhouette("S22");
    expect(f).not.toBeNull();
    expect(f!.properties?.State_LGD).toBe(33);
    expect(f!.properties?.STNAME).toBe("TAMIL NADU");
  });

  it("returns null when the ECI -> LGD crosswalk row is missing", async () => {
    mockedLoadStates.mockResolvedValue(STATE_ROWS);
    mockedLoadBoundary.mockResolvedValue({ fc: STATE_FC, format: "topojson" });

    const f = await loadStateSilhouette("S99");
    expect(f).toBeNull();
  });

  it("returns null when the boundary corpus is missing the LGD code", async () => {
    mockedLoadStates.mockResolvedValue([
      ...STATE_ROWS,
      {
        entity_id: "IN-S99",
        eci_code: "S99",
        display_name: "Phantom",
        boundary_join_name: "Phantom",
        boundary_join_key: "999",
        lgd_code: "999",
        iso_3166_2: null,
      },
    ]);
    mockedLoadBoundary.mockResolvedValue({ fc: STATE_FC, format: "topojson" });

    const f = await loadStateSilhouette("S99");
    expect(f).toBeNull();
  });

  it("returns null when the boundary loader returns null fc", async () => {
    mockedLoadStates.mockResolvedValue(STATE_ROWS);
    mockedLoadBoundary.mockResolvedValue({ fc: null, format: null });

    const f = await loadStateSilhouette("S22");
    expect(f).toBeNull();
  });

  it("calls the canonical boundary loader path 'states/all.geojson' (try-topojson-first)", async () => {
    mockedLoadStates.mockResolvedValue(STATE_ROWS);
    mockedLoadBoundary.mockResolvedValue({ fc: STATE_FC, format: "topojson" });

    await loadStateSilhouette("S22");
    expect(mockedLoadBoundary).toHaveBeenCalledTimes(1);
    expect(mockedLoadBoundary.mock.calls[0][0]).toBe("states/all.geojson");
    // label carries the ECI code so the perf-mark / fallback warning
    // identifies which state's silhouette is being loaded.
    expect(mockedLoadBoundary.mock.calls[0][1]).toContain("s22");
  });

  it("caches per-state - two calls for the same state do not re-fetch", async () => {
    mockedLoadStates.mockResolvedValue(STATE_ROWS);
    mockedLoadBoundary.mockResolvedValue({ fc: STATE_FC, format: "topojson" });

    const a = await loadStateSilhouette("S22");
    const b = await loadStateSilhouette("S22");
    expect(a).toBe(b); // same object reference (cached)
    expect(mockedLoadBoundary).toHaveBeenCalledTimes(1);
  });

  it("returns distinct features for distinct states", async () => {
    mockedLoadStates.mockResolvedValue(STATE_ROWS);
    mockedLoadBoundary.mockResolvedValue({ fc: STATE_FC, format: "topojson" });

    const tn = await loadStateSilhouette("S22");
    const bihar = await loadStateSilhouette("S04");
    const lks = await loadStateSilhouette("U04");
    expect(tn!.properties?.State_LGD).toBe(33);
    expect(bihar!.properties?.State_LGD).toBe(10);
    expect(lks!.properties?.State_LGD).toBe(31);
  });
});

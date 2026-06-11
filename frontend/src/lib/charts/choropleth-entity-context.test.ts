// Unit tests for the IndicatorChoropleth grain-context helper (PR B.05 C2).
// Mocks the per-grain view-model loaders + asserts the projection into the
// unified EntityRow shape. The downstream IndicatorChoropleth rendering is
// covered by its component-level smoke + the Playwright golden-path spec —
// this file only polices the contract between this helper and the loaders.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../view-models/states", () => ({
  loadStates: vi.fn(),
}));

vi.mock("../view-models/districts", () => ({
  loadAllDistrictEntities: vi.fn(),
}));

import { loadStates } from "../view-models/states";
import { loadAllDistrictEntities } from "../view-models/districts";
import {
  entityContextForGrain,
  INDIA_DISTRICTS,
} from "./choropleth-entity-context";
import { INDIA_STATES } from "../boundaries/sources";

const mockedLoadStates = vi.mocked(loadStates);
const mockedLoadDistricts = vi.mocked(loadAllDistrictEntities);

describe("entityContextForGrain('state')", () => {
  beforeEach(() => {
    mockedLoadStates.mockReset();
    mockedLoadDistricts.mockReset();
  });

  it("returns INDIA_STATES as the boundary entry", () => {
    const ctx = entityContextForGrain("state");
    expect(ctx.grain).toBe("state");
    expect(ctx.boundary_entry).toBe(INDIA_STATES);
    expect(ctx.coverage_noun).toBe("states/UTs");
  });

  it("projects StateRow → EntityRow (code = eci_code, display = boundary_join_name, parent = null)", async () => {
    mockedLoadStates.mockResolvedValueOnce([
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
        entity_id: "IN-U05",
        eci_code: "U05",
        display_name: "NCT of Delhi",
        boundary_join_name: "Delhi",
        boundary_join_key: "07",
        lgd_code: "07",
        iso_3166_2: "IN-DL",
      },
    ]);

    const ctx = entityContextForGrain("state");
    const rows = await ctx.load_entities();

    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({
      code: "S22",
      display_name: "Tamil Nadu",
      boundary_join_key: "33",
      parent_display_name: null,
    });
    // boundary_join_name (citizen shortform) — NOT display_name (long form) —
    // is what the projection picks for Delhi. Lock the choice.
    expect(rows[1]).toEqual({
      code: "U05",
      display_name: "Delhi",
      boundary_join_key: "07",
      parent_display_name: null,
    });
  });

  it("does NOT invoke loadAllDistrictEntities", async () => {
    mockedLoadStates.mockResolvedValueOnce([]);
    const ctx = entityContextForGrain("state");
    await ctx.load_entities();
    expect(mockedLoadDistricts).not.toHaveBeenCalled();
  });
});

describe("entityContextForGrain('district')", () => {
  beforeEach(() => {
    mockedLoadStates.mockReset();
    mockedLoadDistricts.mockReset();
  });

  it("returns INDIA_DISTRICTS as the boundary entry", () => {
    const ctx = entityContextForGrain("district");
    expect(ctx.grain).toBe("district");
    expect(ctx.boundary_entry).toBe(INDIA_DISTRICTS);
    expect(ctx.coverage_noun).toBe("districts");
  });

  it("INDIA_DISTRICTS points at the national LGD-keyed districts geojson with dist_lgd join", () => {
    expect(INDIA_DISTRICTS.geojson_local_path).toBe("boundaries/in/districts/all.geojson");
    expect(INDIA_DISTRICTS.join_property).toBe("dist_lgd");
    expect(INDIA_DISTRICTS.id).toBe("india-districts");
  });

  it("projects DistrictEntity → EntityRow (code = entity_id, parent = parent_state_name)", async () => {
    mockedLoadDistricts.mockResolvedValueOnce([
      {
        entity_id: "IN-S22-D567",
        display_name: "Coimbatore",
        lgd_code: "567",
        boundary_join_key: "567",
        parent_entity_id: "IN-S22",
        parent_state_name: "Tamil Nadu",
      },
      {
        entity_id: "IN-S11-D588",
        display_name: "Ernakulam",
        lgd_code: "588",
        boundary_join_key: "588",
        parent_entity_id: "IN-S11",
        parent_state_name: "Kerala",
      },
    ]);

    const ctx = entityContextForGrain("district");
    const rows = await ctx.load_entities();

    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({
      code: "IN-S22-D567",
      display_name: "Coimbatore",
      boundary_join_key: "567",
      parent_display_name: "Tamil Nadu",
    });
    expect(rows[1]).toEqual({
      code: "IN-S11-D588",
      display_name: "Ernakulam",
      boundary_join_key: "588",
      parent_display_name: "Kerala",
    });
  });

  it("does NOT invoke loadStates", async () => {
    mockedLoadDistricts.mockResolvedValueOnce([]);
    const ctx = entityContextForGrain("district");
    await ctx.load_entities();
    expect(mockedLoadStates).not.toHaveBeenCalled();
  });
});

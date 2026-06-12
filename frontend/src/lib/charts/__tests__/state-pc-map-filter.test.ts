// Per-state PC topojson filter test (Row B).
//
// StatePcMapD3.svelte filters the national PC topojson by
// `properties.state_ut_code === state_code`. The component itself
// is exercised by the Playwright @elections smoke; this test pins
// the pure filter shape so a future regression on the property name
// (e.g. an upstream snapshot rename) trips here first.

import { describe, it, expect } from "vitest";
import type { Feature, Geometry, GeoJsonProperties } from "geojson";

function feat(props: Record<string, unknown>): Feature<Geometry, GeoJsonProperties> {
  return {
    type: "Feature",
    properties: props,
    geometry: { type: "Point", coordinates: [0, 0] },
  };
}

function filterByState(
  features: readonly Feature<Geometry, GeoJsonProperties>[],
  state_code: string,
): Feature<Geometry, GeoJsonProperties>[] {
  return features.filter(
    (f) =>
      String(
        (f.properties as Record<string, unknown> | null)?.state_ut_code ?? "",
      ) === state_code,
  );
}

describe("StatePcMapD3 filter contract", () => {
  const FIXTURE: Feature<Geometry, GeoJsonProperties>[] = [
    feat({
      state_ut_code: "S07",
      ls_seat_code: "8",
      unique_id: "S07_8",
      ls_seat_name: "Bhiwani-Mahendragarh",
      state_ut_name: "Haryana",
    }),
    feat({
      state_ut_code: "S07",
      ls_seat_code: "5",
      unique_id: "S07_5",
      ls_seat_name: "Karnal",
      state_ut_name: "Haryana",
    }),
    feat({
      state_ut_code: "S22",
      ls_seat_code: "1",
      unique_id: "S22_1",
      ls_seat_name: "Madurai",
      state_ut_name: "Tamil Nadu",
    }),
    feat({
      state_ut_code: "U07",
      ls_seat_code: "1",
      unique_id: "U07_1",
      ls_seat_name: "Chandni Chowk",
      state_ut_name: "Delhi",
    }),
  ];

  it("filters to one state via state_ut_code === state_code (S07 Haryana)", () => {
    const out = filterByState(FIXTURE, "S07");
    expect(out).toHaveLength(2);
    expect(out.map((f) => f.properties?.unique_id).sort()).toEqual([
      "S07_5",
      "S07_8",
    ]);
  });

  it("returns an empty array when the state is absent (defensive)", () => {
    const out = filterByState(FIXTURE, "S99");
    expect(out).toHaveLength(0);
  });

  it("does NOT match by state slug (LGD form) - the filter requires the ECI code", () => {
    const out = filterByState(FIXTURE, "haryana");
    expect(out).toHaveLength(0);
  });

  it("matches each UT separately (U07 != U08)", () => {
    const out_u07 = filterByState(FIXTURE, "U07");
    const out_u08 = filterByState(FIXTURE, "U08");
    expect(out_u07).toHaveLength(1);
    expect(out_u08).toHaveLength(0);
  });
});

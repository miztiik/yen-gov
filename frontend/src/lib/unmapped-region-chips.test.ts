import { describe, it, expect } from "vitest";
import {
  chipModelFor,
  latestPopulationFromLakhs,
  buildPopulationMap,
  type UnmappedRegion,
} from "./unmapped-region-chips";

const REGIONS: UnmappedRegion[] = [
  { entity_id: "U04", display_name: "Lakshadweep" },
  { entity_id: "U01", display_name: "Andaman & Nicobar" },
];

const fillFor = (v: number) => `#${Math.round(v).toString(16).padStart(6, "0")}`;
const formatValue = (v: number) => `${v.toFixed(1)}%`;

describe("chipModelFor", () => {
  it("projects value + population + swatch when both are present", () => {
    const values = new Map([["U04", 98.3]]);
    const populations = new Map([["U04", 64_000]]);
    const m = chipModelFor(REGIONS[0], values, populations, fillFor, formatValue);
    expect(m.entity_id).toBe("U04");
    expect(m.display_name).toBe("Lakshadweep");
    expect(m.value).toBe(98.3);
    expect(m.value_label).toBe("98.3%");
    expect(m.population_label).toBe("64k people");
    expect(m.swatch).toBe(fillFor(98.3));
  });

  it("renders the no-value variant with em-dash + null swatch", () => {
    const values = new Map<string, number>();
    const populations = new Map([["U04", 64_000]]);
    const m = chipModelFor(REGIONS[0], values, populations, fillFor, formatValue);
    expect(m.value).toBeNull();
    expect(m.value_label).toBe("—");
    expect(m.swatch).toBeNull();
    // Population row stays — the citizen still sees the size anchor.
    expect(m.population_label).toBe("64k people");
  });

  it("renders the no-population variant with em-dash in the pop slot", () => {
    const values = new Map([["U04", 98.3]]);
    const populations = new Map<string, number>();
    const m = chipModelFor(REGIONS[0], values, populations, fillFor, formatValue);
    expect(m.value_label).toBe("98.3%");
    expect(m.population_label).toBe("—");
    expect(m.swatch).not.toBeNull();
  });

  it("rejects non-finite values (treated as no data)", () => {
    const values = new Map([["U04", Number.NaN]]);
    const populations = new Map<string, number>();
    const m = chipModelFor(REGIONS[0], values, populations, fillFor, formatValue);
    expect(m.value).toBeNull();
    expect(m.swatch).toBeNull();
  });
});

describe("latestPopulationFromLakhs", () => {
  const rows = [
    { entity_id: "U04", time: "2015-04", value: 0.65 },
    { entity_id: "U04", time: "2023-04", value: 0.68 },
    { entity_id: "U04", time: "2025-04", value: 0.70 },
    { entity_id: "U01", time: "2025-04", value: 3.85 },
    { entity_id: "S22", time: "2025-04", value: 770.95 },
    { entity_id: "U09", time: "2025-04", value: null },
  ];

  it("picks the latest time and converts lakhs → absolute people", () => {
    expect(latestPopulationFromLakhs(rows, "U04")).toBe(70_000);
    expect(latestPopulationFromLakhs(rows, "U01")).toBe(385_000);
    expect(latestPopulationFromLakhs(rows, "S22")).toBe(77_095_000);
  });

  it("returns null for unknown entity", () => {
    expect(latestPopulationFromLakhs(rows, "U03")).toBeNull();
  });

  it("returns null when every row's value is null", () => {
    expect(latestPopulationFromLakhs(rows, "U09")).toBeNull();
  });
});

describe("buildPopulationMap", () => {
  it("builds the entity_id → people map across a region list", () => {
    const rows = [
      { entity_id: "U04", time: "2025-04", value: 0.70 },
      { entity_id: "U01", time: "2025-04", value: 3.85 },
    ];
    const m = buildPopulationMap(rows, REGIONS);
    expect(m.size).toBe(2);
    expect(m.get("U04")).toBe(70_000);
    expect(m.get("U01")).toBe(385_000);
  });

  it("skips regions with no usable row (does not insert a null)", () => {
    const rows = [{ entity_id: "U04", time: "2025-04", value: 0.70 }];
    const m = buildPopulationMap(rows, REGIONS);
    expect(m.has("U04")).toBe(true);
    expect(m.has("U01")).toBe(false);
  });
});

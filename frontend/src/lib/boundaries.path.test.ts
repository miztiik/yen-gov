// Unit tests for the pure path resolver. No I/O.
import { describe, it, expect } from "vitest";
import { boundaryBasename, joinKeyFor } from "./boundaries";

describe("boundaryBasename", () => {
  it("country → india-soi.geojson", () => {
    expect(boundaryBasename("country")).toBe("india-soi.geojson");
  });

  it("state → india-states.geojson", () => {
    expect(boundaryBasename("state")).toBe("india-states.geojson");
  });

  it("district → india-districts.geojson", () => {
    expect(boundaryBasename("district")).toBe("india-districts.geojson");
  });

  it("subdistrict for TN → S22-subdistricts.geojson", () => {
    expect(boundaryBasename("subdistrict", undefined, "33")).toBe(
      "S22-subdistricts.geojson",
    );
  });

  it("village for TN district 603 → S22-villages-603.geojson", () => {
    expect(boundaryBasename("village", "603", "33")).toBe(
      "S22-villages-603.geojson",
    );
  });

  it("subdistrict without stateLgd throws (caller bug)", () => {
    expect(() => boundaryBasename("subdistrict")).toThrow(/stateLgd/);
  });

  it("village without parentDistrictLgd throws (caller bug)", () => {
    expect(() => boundaryBasename("village", undefined, "33")).toThrow(
      /parentDistrictLgd/,
    );
  });

  it("subdistrict for an unmapped state throws", () => {
    expect(() => boundaryBasename("subdistrict", undefined, "27")).toThrow(
      /no per-state subdistricts/,
    );
  });
});

describe("joinKeyFor", () => {
  it("country has no join key (silhouette only)", () => {
    expect(joinKeyFor("country")).toBeNull();
  });

  it("state joins on ST_NM (datameet lineage)", () => {
    expect(joinKeyFor("state")).toBe("ST_NM");
  });

  it("district joins on dist_lgd (LGD numeric)", () => {
    expect(joinKeyFor("district")).toBe("dist_lgd");
  });

  it("subdistrict joins on subdt_lgd (ramSeraph upstream property)", () => {
    expect(joinKeyFor("subdistrict")).toBe("subdt_lgd");
  });

  it("village joins on vil_lgd (ramSeraph upstream property)", () => {
    expect(joinKeyFor("village")).toBe("vil_lgd");
  });
});

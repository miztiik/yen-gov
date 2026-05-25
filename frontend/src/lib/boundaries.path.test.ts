// Unit tests for the pure path resolver. No I/O.
//
// Post-T.0d (2026-05-22): `boundaryBasename` now returns the Hive-layout
// relative path (per ADR-0031 Amendment), aliased to `boundaryRelPath`.
// Test names + assertions updated accordingly.
import { describe, it, expect } from "vitest";
import { boundaryRelPath, boundaryBasename, joinKeyFor } from "./boundaries";

describe("boundaryRelPath (Hive layout)", () => {
  it("country → country/all.geojson", () => {
    expect(boundaryRelPath("country")).toBe("country/all.geojson");
  });

  it("state → states/all.geojson", () => {
    expect(boundaryRelPath("state")).toBe("states/all.geojson");
  });

  it("district → districts/all.geojson", () => {
    expect(boundaryRelPath("district")).toBe("districts/all.geojson");
  });

  it("subdistrict for TN → subdistricts/state=in_s22/all.geojson", () => {
    expect(boundaryRelPath("subdistrict", undefined, "33")).toBe(
      "subdistricts/state=in_s22/all.geojson",
    );
  });

  it("village for TN district 603 → villages/state=in_s22/district=603/all.geojson", () => {
    expect(boundaryRelPath("village", "603", "33")).toBe(
      "villages/state=in_s22/district=603/all.geojson",
    );
  });

  it("postal for TN resolves to the state-sharded pincode file", () => {
    expect(boundaryRelPath("postal", undefined, "33")).toBe(
      "postal/state=in_s22/all.geojson",
    );
  });

  it("postal without stateLgd throws (caller bug)", () => {
    expect(() => boundaryRelPath("postal")).toThrow(/stateLgd/);
  });

  it("postal for an unmapped state throws", () => {
    expect(() => boundaryRelPath("postal", undefined, "27")).toThrow(
      /no frontend state-code mapping/,
    );
  });

  it("subdistrict without stateLgd throws (caller bug)", () => {
    expect(() => boundaryRelPath("subdistrict")).toThrow(/stateLgd/);
  });

  it("village without parentDistrictLgd throws (caller bug)", () => {
    expect(() => boundaryRelPath("village", undefined, "33")).toThrow(
      /parentDistrictLgd/,
    );
  });

  it("subdistrict for an unmapped state throws", () => {
    expect(() => boundaryRelPath("subdistrict", undefined, "27")).toThrow(
      /no frontend state-code mapping/,
    );
  });
});

describe("boundaryBasename (deprecated alias)", () => {
  // Retained as a thin alias for one release so callers that stored the
  // symbol have time to migrate. Returns whatever boundaryRelPath returns.
  it("forwards to boundaryRelPath", () => {
    expect(boundaryBasename("country")).toBe(boundaryRelPath("country"));
    expect(boundaryBasename("village", "603", "33")).toBe(
      boundaryRelPath("village", "603", "33"),
    );
  });
});

describe("joinKeyFor", () => {
  it("country has no join key (silhouette only)", () => {
    expect(joinKeyFor("country")).toBeNull();
  });

  it("state joins on State_LGD (ramSeraph LGD-keyed lineage post-D.0)", () => {
    expect(joinKeyFor("state")).toBe("State_LGD");
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

  it("postal joins on pincode (India Post 6-digit)", () => {
    expect(joinKeyFor("postal")).toBe("pincode");
  });
});

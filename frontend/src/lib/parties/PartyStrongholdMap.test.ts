// PR-12 of TODO/20260613-party-deferred-followups-plan.md section 14.
//
// Contract test for `PartyStrongholdMap.svelte` pure helpers exported
// via `<script module>`. Tested in node-env vitest; no DOM mount per
// project doctrine (no `@testing-library/svelte`).
//
// The .svelte file's runtime behaviour (topojson load, projection
// fitting, hover state) is covered by the e2e Playwright spec at
// `frontend/e2e/party-stronghold-choropleth.spec.ts`. This file only
// covers the pure helpers that the component exposes.

import { describe, expect, it } from "vitest";
import type { Feature, Geometry, GeoJsonProperties } from "geojson";

import {
  rowsByEntityKey,
  selectFitFeatures,
  type StrongholdChoroplethRow,
} from "./PartyStrongholdMap.svelte";

/** Build a minimal GeoJSON Feature carrying just the properties the
 *  helpers need. The actual `geometry` is irrelevant for these tests. */
function feat(
  unique_id: string,
  state_code: string,
): Feature<Geometry, GeoJsonProperties> {
  return {
    type: "Feature",
    properties: { unique_id, state_ut_code: state_code },
    geometry: { type: "Point", coordinates: [0, 0] },
  };
}

describe("selectFitFeatures", () => {
  const features = [
    feat("S07_1", "S07"),
    feat("S07_8", "S07"),
    feat("S22_10", "S22"),
    feat("S22_12", "S22"),
    feat("U07_1", "U07"),
    feat("S24_60", "S24"),
  ];

  it("returns the full feature list when home_states is empty", () => {
    const out = selectFitFeatures(features, new Set(), "state_ut_code");
    expect(out).toHaveLength(features.length);
  });

  it("crops to home states when 1 <= size <= 3", () => {
    const out = selectFitFeatures(
      features,
      new Set(["S22", "U07"]),
      "state_ut_code",
    );
    expect(out).toHaveLength(3);
    expect(out.map((f) => f.properties?.unique_id).sort()).toEqual([
      "S22_10",
      "S22_12",
      "U07_1",
    ]);
  });

  it("crops to a single state", () => {
    const out = selectFitFeatures(
      features,
      new Set(["S22"]),
      "state_ut_code",
    );
    expect(out.map((f) => f.properties?.unique_id).sort()).toEqual([
      "S22_10",
      "S22_12",
    ]);
  });

  it("returns the full feature list when home_states size > 3 (national crop)", () => {
    const out = selectFitFeatures(
      features,
      new Set(["S07", "S22", "U07", "S24"]),
      "state_ut_code",
    );
    expect(out).toHaveLength(features.length);
  });

  it("returns empty when home_states matches no feature", () => {
    const out = selectFitFeatures(
      features,
      new Set(["S99"]),
      "state_ut_code",
    );
    expect(out).toEqual([]);
  });

  it("uses the configurable state_property key", () => {
    const altFeatures: Feature<Geometry, GeoJsonProperties>[] = [
      {
        type: "Feature",
        properties: { unique_id: "X", lgd_code: "33" },
        geometry: { type: "Point", coordinates: [0, 0] },
      },
      {
        type: "Feature",
        properties: { unique_id: "Y", lgd_code: "07" },
        geometry: { type: "Point", coordinates: [0, 0] },
      },
    ];
    const out = selectFitFeatures(altFeatures, new Set(["33"]), "lgd_code");
    expect(out).toHaveLength(1);
    expect(out[0]!.properties?.unique_id).toBe("X");
  });

  it("returns a fresh array (not the input reference)", () => {
    // Guards against accidental in-place mutation in the renderer.
    const out = selectFitFeatures(features, new Set(), "state_ut_code");
    expect(out).not.toBe(features);
  });
});

describe("rowsByEntityKey", () => {
  const rows: StrongholdChoroplethRow[] = [
    {
      entity_key: "S22_10",
      wins: 3,
      contested: 4,
      bucket: "three-four",
      constituency_name: "Dharmapuri",
      state: "tamil-nadu",
      results: ["W", "W", "L", "W"],
    },
    {
      entity_key: "S22_12",
      wins: 1,
      contested: 4,
      bucket: "one",
      constituency_name: "Sriperumbudur",
      state: "tamil-nadu",
      results: ["L", "L", "W", "L"],
    },
  ];

  it("indexes rows by entity_key for O(1) lookup", () => {
    const map = rowsByEntityKey(rows);
    expect(map.size).toBe(2);
    expect(map.get("S22_10")?.constituency_name).toBe("Dharmapuri");
    expect(map.get("S22_12")?.wins).toBe(1);
  });

  it("returns an empty Map for empty input", () => {
    const map = rowsByEntityKey([]);
    expect(map.size).toBe(0);
  });

  it("dedupes duplicate keys via last-wins", () => {
    const dup: StrongholdChoroplethRow[] = [
      ...rows,
      {
        entity_key: "S22_10",
        wins: 99,
        contested: 100,
        bucket: "five-plus",
        constituency_name: "Dharmapuri (replayed)",
        state: "tamil-nadu",
        results: [],
      },
    ];
    const map = rowsByEntityKey(dup);
    expect(map.size).toBe(2);
    expect(map.get("S22_10")?.wins).toBe(99);
    expect(map.get("S22_10")?.constituency_name).toBe("Dharmapuri (replayed)");
  });

  it("accepts a readonly array (typed at compile time)", () => {
    // TypeScript-only check; just ensures the signature compiles.
    const frozen = Object.freeze([...rows]);
    const map = rowsByEntityKey(frozen);
    expect(map.size).toBe(2);
  });
});

describe("module re-exports from PartyStrongholdMap.svelte", () => {
  it("re-exports the canonical helpers from stronghold-choropleth-rows.ts", async () => {
    // Smoke: the consumer (Party.svelte) should be able to import
    // all the pure helpers via the .svelte module re-export so it
    // doesn't have to know about the sibling .ts module. The actual
    // re-exports are declared at top-of-file; this test asserts they
    // round-trip.
    const mod = await import("./PartyStrongholdMap.svelte");
    expect(typeof mod.bucketFromWins).toBe("function");
    expect(typeof mod.mapPcStrongholdsToChoroplethRows).toBe("function");
    expect(typeof mod.paletteFromBrand).toBe("function");
    expect(typeof mod.stateCodeFromPcEntityId).toBe("function");
    expect(typeof mod.uniqueIdFromPcEntityId).toBe("function");
    expect(Array.isArray(mod.BUCKET_ORDER)).toBe(true);
  });
});

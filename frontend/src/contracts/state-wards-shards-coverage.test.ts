// state-wards-shards-coverage contract test.
//
// Row C moves exhaustive ward shard discovery out of default frontend
// Vitest. The shard inventory is generated from
// datasets/data/entities/boundary_encoding.csv into
// frontend/src/lib/boundaries/generated-sources.ts. This file keeps
// constant-size consumer canaries over that generated registry; backend
// Tier-B owns the exhaustive corpus walk.

import { describe, it, expect } from "vitest";
import { WARDS_BY_STATE } from "../lib/boundaries/sources";

const wardShardCount = Object.values(WARDS_BY_STATE).reduce(
  (sum, ulbs) => sum + ulbs.length,
  0,
);

describe("ward generated registry summary", () => {
  it("keeps the C.3.b coverage floor without walking datasets/boundaries/in/wards", () => {
    expect(wardShardCount).toBeGreaterThanOrEqual(3000);
    expect(Object.keys(WARDS_BY_STATE).length).toBe(29);
  });

  it("keeps representative high-density canaries", () => {
    expect(WARDS_BY_STATE.S24).toContain(800629);
    expect(WARDS_BY_STATE.S13).toContain(802640);
  });

  it("keeps the documented SBM-ward gap states absent", () => {
    const gapStates = ["S02", "S14", "S15", "S16", "S23", "U04", "U09"];
    for (const code of gapStates) {
      expect(WARDS_BY_STATE[code]).toBeUndefined();
    }
  });

  it("keeps per-state ULB codes unique and sorted", () => {
    for (const [code, ulbs] of Object.entries(WARDS_BY_STATE)) {
      expect(new Set(ulbs).size, `${code} duplicate ULB LGD codes`).toBe(ulbs.length);
      expect(ulbs, `${code} ULB LGD codes sorted`).toEqual([...ulbs].sort((a, b) => a - b));
    }
  });
});

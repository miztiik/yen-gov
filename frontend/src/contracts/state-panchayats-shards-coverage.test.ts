// state-panchayats-shards-coverage contract test.
//
// Row C moves exhaustive panchayat shard discovery out of default
// frontend Vitest. The shard inventory is generated from
// datasets/data/entities/boundary_encoding.csv into
// frontend/src/lib/boundaries/generated-sources.ts. This file keeps
// constant-size consumer canaries over that generated registry; backend
// Tier-B owns the exhaustive corpus walk.

import { describe, it, expect } from "vitest";
import { PANCHAYAT_DISTRICTS_BY_STATE } from "../lib/boundaries/sources";

const panchayatShardCount = Object.values(PANCHAYAT_DISTRICTS_BY_STATE).reduce(
  (sum, districts) => sum + districts.length,
  0,
);

describe("panchayat generated registry summary", () => {
  it("keeps the C.2.b coverage floor without walking datasets/boundaries/in/panchayats", () => {
    expect(panchayatShardCount).toBeGreaterThanOrEqual(600);
    expect(Object.keys(PANCHAYAT_DISTRICTS_BY_STATE).length).toBe(28);
  });

  it("keeps representative high-density canaries", () => {
    expect(PANCHAYAT_DISTRICTS_BY_STATE.S13).toContain(490);
    expect(PANCHAYAT_DISTRICTS_BY_STATE.S24).toContain(118);
  });

  it("keeps the documented LGD-panchayat gap states absent", () => {
    const gapStates = ["S02", "S08", "S14", "S16", "S17", "S21", "U08", "U09"];
    for (const code of gapStates) {
      expect(PANCHAYAT_DISTRICTS_BY_STATE[code]).toBeUndefined();
    }
  });

  it("keeps per-state district codes unique and sorted", () => {
    for (const [code, districts] of Object.entries(PANCHAYAT_DISTRICTS_BY_STATE)) {
      expect(new Set(districts).size, `${code} duplicate district LGD codes`).toBe(districts.length);
      expect(districts, `${code} district LGD codes sorted`).toEqual([...districts].sort((a, b) => a - b));
    }
  });
});

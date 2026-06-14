// state-blocks-registry-coverage contract test.
//
// Block registry is low-cardinality and remains hand-authored in
// sources.ts. Exhaustive corpus proof belongs to backend Tier-B; this
// default frontend test keeps bounded consumer canaries only.

import { describe, it, expect } from "vitest";
import { BLOCK_BOUNDARY, ECI_TO_LGD_SLUG } from "../lib/boundaries/sources";

describe("BLOCK_BOUNDARY registry canaries", () => {
  it("keeps full state/UT coverage at low cardinality", () => {
    expect(Object.keys(BLOCK_BOUNDARY).length).toBeGreaterThanOrEqual(36);
  });

  it("keeps the S24 auto-fallback canary configured", () => {
    const entry = BLOCK_BOUNDARY.S24;
    expect(entry).toBeDefined();
    expect(entry.id).toBe("S24-block");
    expect(entry.geojson_local_path).toBe(
      `boundaries/in/blocks/state=${ECI_TO_LGD_SLUG.S24}/all.geojson`,
    );
    expect(entry.geojson_url).toBe(
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    );
    expect(entry.join_property).toBe("block_lgd");
    expect(entry.label).toContain("Uttar Pradesh");
    expect((entry as unknown as Record<string, unknown>).attribution).toBeUndefined();
  });

  it("keeps representative non-mainland UT coverage", () => {
    expect(BLOCK_BOUNDARY.U01.geojson_local_path).toBe(
      "boundaries/in/blocks/state=andaman-and-nicobar/all.geojson",
    );
    expect(BLOCK_BOUNDARY.U09.geojson_local_path).toBe(
      "boundaries/in/blocks/state=ladakh/all.geojson",
    );
  });
});

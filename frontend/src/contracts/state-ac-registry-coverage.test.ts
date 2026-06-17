// state-ac-registry-coverage contract test.
//
// AC registry stays hand-authored. Row B's boundary_encoding.csv receipt
// covers datasets/boundaries/in/** only, while AC geometry lives under
// datasets/boundaries/electoral/**. Since the 2026-06-16 map-geometry rip
// (Row 3) EVERY STATE_AC entry's geometry is the ONE national
// `delim=2024/ac/all.topojson` (object `ac`, filtered per state by
// state_ut_code); only the per-state PAINT join config differs. Exhaustive
// corpus proof belongs to backend Tier-B; this default frontend test keeps
// bounded consumer canaries only.

import { describe, it, expect } from "vitest";
import { STATE_AC } from "../lib/boundaries/sources";

const NATIONAL_AC_PATH = "boundaries/electoral/delim=2024/ac/all.topojson";

describe("STATE_AC registry canaries", () => {
  it("keeps the known low-cardinality AC registry floor", () => {
    expect(Object.keys(STATE_AC).length).toBeGreaterThanOrEqual(31);
  });

  it("keeps a standard LGD-backed AC entry shape", () => {
    const entry = STATE_AC.S22;
    expect(entry).toBeDefined();
    expect(entry.id).toBe("S22-ac");
    expect(entry.geojson_local_path).toBe(NATIONAL_AC_PATH);
    expect(entry.topojson_object).toBe("ac");
    expect(entry.geojson_url).toMatch(/^https:\/\//);
    expect(entry.join_property).toBe("lgd_ac_id");
    expect(entry.join_property_label).toBe("ac_no");
    expect(entry.join_property_lgd).toBe("lgd_ac_id");
    expect(entry.label).toContain("Tamil Nadu");
  });

  it("keeps documented AC join-key exceptions", () => {
    expect(STATE_AC.U08.join_property).toBe("seat_id");
    expect(STATE_AC.U08.join_property_lgd).toBeUndefined();
    expect(STATE_AC.S03.join_property).toBe("ac_no");
    expect(STATE_AC.S03.join_property_lgd).toBeUndefined();
  });

  it("keeps representative electoral partition paths", () => {
    // Every state now points at the SAME national AC topojson; the
    // per-state distinction is the paint join_property, asserted above.
    expect(STATE_AC.S03.geojson_local_path).toBe(NATIONAL_AC_PATH);
    expect(STATE_AC.S03.topojson_object).toBe("ac");
    expect(STATE_AC.U08.geojson_local_path).toBe(NATIONAL_AC_PATH);
    expect(STATE_AC.U08.topojson_object).toBe("ac");
  });
});

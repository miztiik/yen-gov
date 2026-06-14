// state-ac-registry-coverage contract test.
//
// AC registry stays hand-authored in Row C. Row B's
// boundary_encoding.csv receipt covers datasets/boundaries/in/** only,
// while AC geometry lives under datasets/boundaries/electoral/**. There
// is no generated AC source to consume yet, and this row must not invent
// one. Exhaustive corpus proof belongs to backend Tier-B; this default
// frontend test keeps bounded consumer canaries only.

import { describe, it, expect } from "vitest";
import { STATE_AC, ECI_TO_LGD_SLUG } from "../lib/boundaries/sources";

describe("STATE_AC registry canaries", () => {
  it("keeps the known low-cardinality AC registry floor", () => {
    expect(Object.keys(STATE_AC).length).toBeGreaterThanOrEqual(31);
  });

  it("keeps a standard LGD-backed AC entry shape", () => {
    const entry = STATE_AC.S22;
    expect(entry).toBeDefined();
    expect(entry.id).toBe("S22-ac");
    expect(entry.geojson_local_path).toBe(
      `boundaries/electoral/delim=2008/ac/state=${ECI_TO_LGD_SLUG.S22}/all.geojson`,
    );
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
    expect(STATE_AC.S03.geojson_local_path).toBe(
      "boundaries/electoral/delim=2008/ac/state=assam/all.geojson",
    );
    expect(STATE_AC.U08.geojson_local_path).toBe(
      "boundaries/electoral/delim=2008/ac/state=jammu-and-kashmir/all.geojson",
    );
  });
});

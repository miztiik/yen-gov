// state-panchayats-registry-coverage contract test.
//
// Invariant: every nested Gram-Panchayat GeoJSON shard that exists on
// disk under `datasets/boundaries/in/panchayats/state=<lgd-slug>/district=
// <lgd>/all.geojson` MUST have a matching `PANCHAYAT_BOUNDARY_BY_DISTRICT`
// entry in `frontend/src/lib/maplibre/sources.ts`, and vice versa. The
// frontend registry and the on-disk corpus are two halves of the same
// contract; if a shard exists but no registry entry points at it, any
// panchayat-grain page silently returns "no boundary configured" (the
// citizen sees a blank map). If a registry entry points at a missing
// shard, the network request 404s.
//
// This is the C.2.c contract test
// (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) - symmetric mirror
// of the C.1.b/c `state-blocks-registry-coverage.test.ts` precedent,
// adapted for the district-keyed nested Hive layout.
//
// The C.2.b live lift (2026-05-30, ramSeraph LGD_Panchayats release)
// emitted 663 shards across 28 states/UTs from 319,287 upstream
// features. The 9-state/UT coverage gap (S02 S08 S14 S16 S17 S21 U08 U09
// + U06 not elective) is documented in the PANCHAYAT_DISTRICTS_BY_STATE
// header comment and reserved for C.2.d Bhuvan gap-fill.
//
// Per-entry shape assertions (post-A.3 BoundaryEntry):
//   - key matches `${state_code}-${district_lgd}`
//   - id matches `${key}-panchayat`
//   - geojson_local_path matches `boundaries/in/panchayats/state=<lgd-slug>/district=<lgd>/all.geojson`
//   - geojson_url points at the ramSeraph LGD_Panchayats release
//   - join_property is "gp_code"
//   - label is non-empty (contains the state name)
//
// This test runs alongside `state-panchayats-shards-coverage.test.ts`:
// the shards-coverage test locks the corpus floor (independent of the
// registry); this test locks the symmetric shards<->registry relation.

import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  PANCHAYAT_BOUNDARY_BY_DISTRICT,
  PANCHAYAT_DISTRICTS_BY_STATE,
  PANCHAYAT_STATE_NAMES,
  ECI_TO_LGD_SLUG,
} from "../lib/boundaries/sources";

const SLUG_TO_ECI: Record<string, string> = Object.fromEntries(
  Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
);

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const panchayatsDir = resolve(repoRoot, "datasets", "boundaries", "in", "panchayats");

interface DiscoveredShard {
  stateCode: string;
  districtLgd: number;
  key: string;
}

// Walk the on-disk nested Hive layout and return one entry per shard.
function discoverShards(): DiscoveredShard[] {
  if (!existsSync(panchayatsDir)) return [];
  const out: DiscoveredShard[] = [];
  for (const stateEntry of readdirSync(panchayatsDir, { withFileTypes: true })) {
    if (!stateEntry.isDirectory()) continue;
    const sm = stateEntry.name.match(/^state=(.+)$/);
    if (!sm) continue;
    const stateSlug = sm[1];
    const stateCode = SLUG_TO_ECI[stateSlug];
    if (!stateCode) continue;
    const stateDir = resolve(panchayatsDir, stateEntry.name);
    for (const distEntry of readdirSync(stateDir, { withFileTypes: true })) {
      if (!distEntry.isDirectory()) continue;
      const dm = distEntry.name.match(/^district=(\d+)$/);
      if (!dm) continue;
      const shard = resolve(stateDir, distEntry.name, "all.geojson");
      if (existsSync(shard)) {
        const districtLgd = Number(dm[1]);
        out.push({ stateCode, districtLgd, key: `${stateCode}-${districtLgd}` });
      }
    }
  }
  return out;
}

const shards = discoverShards();
const shardKeys = shards.map((s) => s.key).sort();
const registryKeys = Object.keys(PANCHAYAT_BOUNDARY_BY_DISTRICT).sort();

describe("PANCHAYAT_BOUNDARY_BY_DISTRICT registry covers every on-disk panchayat shard", () => {
  it("discovers at least 600 on-disk panchayat shards", () => {
    // C.2.b ship floor: 663 shards from the 2026-05-30 ramSeraph
    // snapshot. Floor=600 leaves ~10% headroom for normal
    // upstream-vintage churn.
    expect(shards.length).toBeGreaterThanOrEqual(600);
  });

  it("registry entry exists for every on-disk shard", () => {
    const missing = shardKeys.filter((k) => !(k in PANCHAYAT_BOUNDARY_BY_DISTRICT));
    expect(missing).toEqual([]);
  });

  it("on-disk shard exists for every registry entry", () => {
    const shardKeySet = new Set(shardKeys);
    const orphans = registryKeys.filter((k) => !shardKeySet.has(k));
    expect(orphans).toEqual([]);
  });

  it("shard count and registry count are identical", () => {
    // Tight symmetry: any drift between corpus and registry surfaces
    // via the prior two assertions, but the count match is the
    // clearest one-number invariant for review.
    expect(shardKeys.length).toBe(registryKeys.length);
  });

  it("S13-490 (Maharashtra largest shard) is present on BOTH disk and registry", () => {
    // S13 district=490 was the largest individual shard at 10.9 MB
    // in the C.2.b live lift - within budget but the closest to the
    // 12 MB SNAPSHOT_BYTE_BUDGET. If a future upstream vintage drops
    // it (or the lift somehow SKIPs it), this assertion fails loud.
    expect(shardKeys).toContain("S13-490");
    expect(registryKeys).toContain("S13-490");
  });

  it("S24-118 (Uttar Pradesh first district) is present on BOTH disk and registry", () => {
    // UP carries the most districts (75); the first district code
    // (118) anchors the start of the UP range. A regression that
    // truncates UP's per-district enumeration would surface here.
    expect(shardKeys).toContain("S24-118");
    expect(registryKeys).toContain("S24-118");
  });
});

describe("PANCHAYAT_BOUNDARY_BY_DISTRICT entry shape is well-formed", () => {
  it("every registry entry carries the post-A.3 BoundaryEntry shape", () => {
    for (const [key, entry] of Object.entries(PANCHAYAT_BOUNDARY_BY_DISTRICT)) {
      const km = key.match(/^([SU]\d{2})-(\d+)$/);
      expect(km, `key ${key} should match ${"${state}-${district}"}`).not.toBeNull();
      const [, stateCode, distLgd] = km!;
      expect(entry.id).toBe(`${key}-panchayat`);
      expect(entry.geojson_local_path).toBe(
        `boundaries/in/panchayats/state=${ECI_TO_LGD_SLUG[stateCode]}/district=${distLgd}/all.geojson`,
      );
      expect(entry.geojson_url).toMatch(/^https:\/\//);
      expect(entry.join_property).toBe("gp_code");
      expect(entry.label.length).toBeGreaterThan(3);
      // A.3 removed the attribution field from the interface; this
      // assertion is structural - if a future PR re-adds the field on
      // an entry the TS compiler catches it.
      expect((entry as unknown as Record<string, unknown>).attribution).toBeUndefined();
    }
  });

  it("all entries point at the same ramSeraph LGD_Panchayats upstream URL", () => {
    // Panchayat-level boundary source-of-truth is a single national
    // geojsonl bundle on ramSeraph (per C.2 recon verdict,
    // docs/archive/notes/2026-05-30-c2-panchayats-source-hunt-verdict.md). Any
    // per-district divergence in the upstream URL should be a
    // deliberate, reviewed decision - this assertion forces that.
    const upstreamUrl =
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/LGD_Panchayats.geojsonl.7z";
    for (const entry of Object.values(PANCHAYAT_BOUNDARY_BY_DISTRICT)) {
      expect(entry.geojson_url).toBe(upstreamUrl);
    }
  });

  it("entry label contains the state name (citizen-readable)", () => {
    // Smoke against the construction template; the label must
    // include the state name so future district-picker UI tooltips
    // (post-C.2.c shim) render a recognisable surface even before
    // the picker fetches district-name metadata.
    for (const [key, entry] of Object.entries(PANCHAYAT_BOUNDARY_BY_DISTRICT)) {
      const stateCode = key.split("-")[0];
      const stateName = PANCHAYAT_STATE_NAMES[stateCode];
      expect(stateName, `state ${stateCode} must have a name lookup`).toBeDefined();
      expect(entry.label).toContain(stateName!);
    }
  });
});

describe("PANCHAYAT_DISTRICTS_BY_STATE coverage matches the C.2.b live lift", () => {
  it("covers exactly 28 states/UTs", () => {
    // C.2.b shipped with 28 states/UTs (9-state coverage gap
    // reserved for C.2.d Bhuvan fill). A drift in either direction
    // signals an undocumented C.2.* slice update.
    expect(Object.keys(PANCHAYAT_DISTRICTS_BY_STATE).length).toBe(28);
  });

  it("PANCHAYAT_STATE_NAMES covers exactly the same 28 states/UTs", () => {
    const districtsStates = Object.keys(PANCHAYAT_DISTRICTS_BY_STATE).sort();
    const namesStates = Object.keys(PANCHAYAT_STATE_NAMES).sort();
    expect(namesStates).toEqual(districtsStates);
  });

  it("each state has at least one district", () => {
    for (const [code, districts] of Object.entries(PANCHAYAT_DISTRICTS_BY_STATE)) {
      expect(districts.length, `state ${code} should have at least one district`).toBeGreaterThan(0);
    }
  });

  it("district codes within each state are unique and sorted", () => {
    for (const [code, districts] of Object.entries(PANCHAYAT_DISTRICTS_BY_STATE)) {
      const unique = new Set(districts);
      expect(
        unique.size,
        `state ${code} has duplicate district LGD codes`,
      ).toBe(districts.length);
      const sorted = [...districts].sort((a, b) => a - b);
      expect(districts, `state ${code} district codes should be sorted ascending`).toEqual(sorted);
    }
  });

  it("documented coverage gap states are ABSENT from the registry", () => {
    // The C.2.d Bhuvan gap-fill list MUST remain absent from the
    // LGD-source registry; if any of these states accidentally
    // accumulates shards via the LGD pipeline (e.g. upstream vintage
    // change), it should require a deliberate registry update + this
    // assertion update + a plan-doc entry, not silent inclusion.
    const gapStates = ["S02", "S08", "S14", "S16", "S17", "S21", "U08", "U09"];
    for (const code of gapStates) {
      expect(
        PANCHAYAT_DISTRICTS_BY_STATE[code],
        `gap state ${code} unexpectedly present in PANCHAYAT_DISTRICTS_BY_STATE - investigate before unblocking`,
      ).toBeUndefined();
    }
  });
});

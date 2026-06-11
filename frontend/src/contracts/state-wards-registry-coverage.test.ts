// state-wards-registry-coverage contract test.
//
// Invariant: every nested Ward GeoJSON shard that exists on
// disk under `datasets/boundaries/in/wards/state=<lgd-slug>/ulb=
// <ulb_lgd>/all.geojson` MUST have a matching `WARD_BOUNDARY_BY_ULB`
// entry in `frontend/src/lib/maplibre/sources.ts`, and vice versa. The
// frontend registry and the on-disk corpus are two halves of the same
// contract; if a shard exists but no registry entry points at it, any
// ward-grain page silently returns "no boundary configured" (the
// citizen sees a blank map). If a registry entry points at a missing
// shard, the network request 404s.
//
// This is the C.3.c contract test
// (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) - symmetric mirror
// of the C.2.c `state-panchayats-registry-coverage.test.ts` precedent,
// adapted for the ULB-keyed nested Hive layout. Tests the new
// ULB-as-parent partition (vs panchayats' district-as-parent + blocks'
// flat state-keyed partitions).
//
// The C.3.b live lift (2026-05-30, ramSeraph SBM_Wards release)
// emitted 3,300 shards across 29 states/UTs from 70,419 upstream
// features. The 7-state/UT coverage gap (S02 Arunachal Pradesh,
// S14 Manipur, S15 Meghalaya, S16 Mizoram, S23 Tripura, U04
// Lakshadweep, U09 Ladakh) is documented in the WARDS_BY_STATE
// header comment and reserved for C.3.d gap-fill via LivingAtlas +
// WB AMRUT + Shillong Tier-1.5 / Tier-2 sources.
//
// Per-entry shape assertions (post-A.3 BoundaryEntry):
//   - key matches `${state_code}-${ulb_lgd}`
//   - id matches `${key}-ward`
//   - geojson_local_path matches `boundaries/in/wards/state=<lgd-slug>/ulb=<ulb_lgd>/all.geojson`
//   - geojson_url points at the ramSeraph SBM_Wards release
//   - join_property is "wardcode"
//   - label is non-empty (contains the state name)
//
// This test runs alongside `state-wards-shards-coverage.test.ts`:
// the shards-coverage test locks the corpus floor (independent of the
// registry); this test locks the symmetric shards<->registry relation.

import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  WARD_BOUNDARY_BY_ULB,
  WARDS_BY_STATE,
  WARD_STATE_NAMES,
  ECI_TO_LGD_SLUG,
} from "../lib/boundaries/sources";

const SLUG_TO_ECI: Record<string, string> = Object.fromEntries(
  Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
);

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const wardsDir = resolve(repoRoot, "datasets", "boundaries", "in", "wards");

interface DiscoveredShard {
  stateCode: string;
  ulbLgd: number;
  key: string;
}

// Walk the on-disk nested Hive layout and return one entry per shard.
function discoverShards(): DiscoveredShard[] {
  if (!existsSync(wardsDir)) return [];
  const out: DiscoveredShard[] = [];
  for (const stateEntry of readdirSync(wardsDir, { withFileTypes: true })) {
    if (!stateEntry.isDirectory()) continue;
    const sm = stateEntry.name.match(/^state=(.+)$/);
    if (!sm) continue;
    const stateSlug = sm[1];
    const stateCode = SLUG_TO_ECI[stateSlug];
    if (!stateCode) continue;
    const stateDir = resolve(wardsDir, stateEntry.name);
    for (const ulbEntry of readdirSync(stateDir, { withFileTypes: true })) {
      if (!ulbEntry.isDirectory()) continue;
      const um = ulbEntry.name.match(/^ulb=(\d+)$/);
      if (!um) continue;
      const shard = resolve(stateDir, ulbEntry.name, "all.geojson");
      if (existsSync(shard)) {
        const ulbLgd = Number(um[1]);
        out.push({ stateCode, ulbLgd, key: `${stateCode}-${ulbLgd}` });
      }
    }
  }
  return out;
}

const shards = discoverShards();
const shardKeys = shards.map((s) => s.key).sort();
const registryKeys = Object.keys(WARD_BOUNDARY_BY_ULB).sort();

describe("WARD_BOUNDARY_BY_ULB registry covers every on-disk ward shard", () => {
  it("discovers at least 3,000 on-disk ward shards", () => {
    // C.3.b ship floor: 3,300 shards from the 2026-05-30 ramSeraph
    // SBM_Wards snapshot. Floor=3,000 leaves ~10% headroom for normal
    // upstream-vintage churn.
    expect(shards.length).toBeGreaterThanOrEqual(3000);
  });

  it("registry entry exists for every on-disk shard", () => {
    const missing = shardKeys.filter((k) => !(k in WARD_BOUNDARY_BY_ULB));
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

  it("S24-800629 (Uttar Pradesh first ULB) is present on BOTH disk and registry", () => {
    // UP carries the most ULBs (638 across 75 districts); the first
    // ULB code (800629) anchors the start of the UP range. A
    // regression that truncates UP's per-ULB enumeration would
    // surface here.
    expect(shardKeys).toContain("S24-800629");
    expect(registryKeys).toContain("S24-800629");
  });

  it("S13-802640 (Maharashtra first ULB) is present on BOTH disk and registry", () => {
    // MH carries the second-most ULBs (410); 802640 anchors the start
    // of the MH range. Catches any regression that truncates MH's
    // per-ULB enumeration.
    expect(shardKeys).toContain("S13-802640");
    expect(registryKeys).toContain("S13-802640");
  });
});

describe("WARD_BOUNDARY_BY_ULB entry shape is well-formed", () => {
  it("every registry entry carries the post-A.3 BoundaryEntry shape", () => {
    for (const [key, entry] of Object.entries(WARD_BOUNDARY_BY_ULB)) {
      const km = key.match(/^([SU]\d{2})-(\d+)$/);
      expect(km, `key ${key} should match ${"${state}-${ulb}"}`).not.toBeNull();
      const [, , ulbLgd] = km!;
      expect(entry.id).toBe(`${key}-ward`);
      const stateCode = key.split("-")[0];
      expect(entry.geojson_local_path).toBe(
        `boundaries/in/wards/state=${ECI_TO_LGD_SLUG[stateCode]}/ulb=${ulbLgd}/all.geojson`,
      );
      expect(entry.geojson_url).toMatch(/^https:\/\//);
      expect(entry.join_property).toBe("wardcode");
      expect(entry.label.length).toBeGreaterThan(3);
      // A.3 removed the attribution field from the interface; this
      // assertion is structural - if a future PR re-adds the field on
      // an entry the TS compiler catches it.
      expect((entry as unknown as Record<string, unknown>).attribution).toBeUndefined();
    }
  });

  it("all entries point at the same ramSeraph SBM_Wards upstream URL", () => {
    // Ward-level boundary source-of-truth is a single national
    // geojsonl bundle on ramSeraph (per C.3 recon verdict,
    // docs/archive/notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md). Any
    // per-ULB divergence in the upstream URL should be a deliberate,
    // reviewed decision - this assertion forces that.
    const upstreamUrl =
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/urban/SBM_Wards.geojsonl.7z";
    for (const entry of Object.values(WARD_BOUNDARY_BY_ULB)) {
      expect(entry.geojson_url).toBe(upstreamUrl);
    }
  });

  it("entry label contains the state name (citizen-readable)", () => {
    // Smoke against the construction template; the label must
    // include the state name so future ULB-picker UI tooltips
    // (post-C.3.c, scope TBD) render a recognisable surface even
    // before the picker fetches ULB-name metadata.
    for (const [key, entry] of Object.entries(WARD_BOUNDARY_BY_ULB)) {
      const stateCode = key.split("-")[0];
      const stateName = WARD_STATE_NAMES[stateCode];
      expect(stateName, `state ${stateCode} must have a name lookup`).toBeDefined();
      expect(entry.label).toContain(stateName!);
    }
  });
});

describe("WARDS_BY_STATE coverage matches the C.3.b live lift", () => {
  it("covers exactly 29 states/UTs", () => {
    // C.3.b shipped with 29 states/UTs (7-state/UT coverage gap
    // reserved for C.3.d Tier-1.5 / Tier-2 gap-fill). A drift in
    // either direction signals an undocumented C.3.* slice update.
    expect(Object.keys(WARDS_BY_STATE).length).toBe(29);
  });

  it("WARD_STATE_NAMES covers exactly the same 29 states/UTs", () => {
    const ulbsStates = Object.keys(WARDS_BY_STATE).sort();
    const namesStates = Object.keys(WARD_STATE_NAMES).sort();
    expect(namesStates).toEqual(ulbsStates);
  });

  it("each state has at least one ULB", () => {
    for (const [code, ulbs] of Object.entries(WARDS_BY_STATE)) {
      expect(ulbs.length, `state ${code} should have at least one ULB`).toBeGreaterThan(0);
    }
  });

  it("ULB codes within each state are unique and sorted", () => {
    for (const [code, ulbs] of Object.entries(WARDS_BY_STATE)) {
      const unique = new Set(ulbs);
      expect(
        unique.size,
        `state ${code} has duplicate ULB LGD codes`,
      ).toBe(ulbs.length);
      const sorted = [...ulbs].sort((a, b) => a - b);
      expect(ulbs, `state ${code} ULB codes should be sorted ascending`).toEqual(sorted);
    }
  });

  it("documented coverage gap states are ABSENT from the registry", () => {
    // The C.3.d gap-fill list MUST remain absent from the SBM-source
    // registry; if any of these states accidentally accumulates
    // shards via the SBM pipeline (e.g. upstream MoHUA expanding
    // coverage), it should require a deliberate registry update +
    // this assertion update + a plan-doc entry, not silent inclusion.
    //
    // Note: the C.3.b PR plan-doc text incorrectly listed gap states
    // as "S02 HP, S09 Sikkim, S23 Goa, U06 Lakshadweep" — those state
    // names map to the WRONG codes (HP is S08 which is present;
    // Sikkim is S21 which is present; Goa is S05 which is present;
    // Lakshadweep is U04). This test locks the correct gap list per
    // the actual SBM_Wards 2026-05 snapshot.
    const gapStates = ["S02", "S14", "S15", "S16", "S23", "U04", "U09"];
    for (const code of gapStates) {
      expect(
        WARDS_BY_STATE[code],
        `gap state ${code} unexpectedly present in WARDS_BY_STATE - investigate before unblocking`,
      ).toBeUndefined();
    }
  });

  it("UP is the largest state by ULB count (638 ULBs)", () => {
    // SBM Urban 2026-05 canary: UP has the largest per-state ULB
    // count by a significant margin (638 vs MH's 410 vs MP's 335).
    // If this ratio ever inverts, investigate before accepting the
    // delta.
    const upCount = WARDS_BY_STATE["S24"]?.length ?? 0;
    expect(upCount).toBe(638);
    for (const [code, ulbs] of Object.entries(WARDS_BY_STATE)) {
      if (code === "S24") continue;
      expect(ulbs.length).toBeLessThan(upCount);
    }
  });
});

// state-wards-shards-coverage contract test.
//
// Invariant: every nested ULB-Ward GeoJSON shard that exists on disk
// under `datasets/boundaries/in/wards/state=<lgd-slug>/ulb=<ulb_lgd>/
// all.geojson` MUST sit at a well-formed Hive path and the shipped
// coverage MUST stay above the C.3.b documented floor.
//
// File-name note: docs/archive/plans/20260529-boundary-rip-and-replace-plan.md row
// C.3.b cites this file as `state-wards-registry-coverage.test.ts`.
// The deliverable was renamed `*-shards-coverage` because the frontend
// `WARD_BOUNDARY_BY_ULB` registry does NOT land until C.3.c
// (ULB-picker UI scope) — at C.3.b there is no registry to compare
// the shards AGAINST, only the on-disk corpus to lock a coverage floor
// in. When C.3.c lands the registry, it will add a separate
// `state-wards-registry-coverage.test.ts` mirroring the panchayats
// precedent (symmetric shards↔registry coverage); this file then
// continues to lock the corpus floor independently.
//
// The C.3.b live lift (2026-05-30, ramSeraph SBM_Wards release) emitted
// 3,300 shards across 29 states/UTs from 70,419 upstream features.
// Coverage gap vs blocks (36 states/UTs): ~7 states/UTs missing from
// upstream SBM_Wards (S02 HP / S09 Sikkim / S14 WB / S15 TR / S16 MZ
// / S23 Goa / U06 Lakshadweep) — reserved for C.3.d Bhuvan / Living
// Atlas / WB-AMRUT / state-level gap-fill.
//
// First-snapshot finding (C.3.b): SBM_Wards uses a THIRD distinct
// property-name convention (`statecode`/`ulbcode`/`wardcode`/`wardname`
// — concatenated lowercase numeric strings) — separate from C.1.c
// blocks long-form (`state_lgd`/`dist_lgd`) and C.2.b panchayats
// short-form (`st_lgd`/`dt_lgd`). Both `statecode` and `ulbcode` come
// as numeric strings coerced via int(); `wardcode` is heterogeneous
// (numeric strings + free-text like "Ward No 5"). See
// tools/boundaries/lift_wards_national.py module docstring + the
// SBM-Urban-schema constants block.
//
// Per-shard shape assertions:
//   - Path matches the Hive partition regex
//   - ulb= segment is a positive-integer LGD ULB code
//   - state= segment is a 3-char yen-gov entity code (lowercase s|u + 2 digits)
//   - ULB codes are unique within each state (no double-emission)

import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ECI_TO_LGD_SLUG } from "../lib/maplibre/sources";

const SLUG_TO_ECI: Record<string, string> = Object.fromEntries(
  Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
);

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const wardsDir = resolve(repoRoot, "datasets", "boundaries", "in", "wards");

interface DiscoveredShard {
  stateCode: string; // "S01" / "U02" (uppercase)
  ulbLgd: number;
}

// Discover every on-disk ward shard under the nested Hive layout.
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
        out.push({ stateCode, ulbLgd: Number(um[1]) });
      }
    }
  }
  return out;
}

const shards = discoverShards();
const statesCovered = Array.from(new Set(shards.map((s) => s.stateCode))).sort();

describe("ward shards — corpus coverage floor (C.3.b)", () => {
  it("at least 3000 on-disk ward shards", () => {
    // C.3.b ship floor: 3,300 shards from the 2026-05-30 ramSeraph
    // SBM_Wards snapshot. Floor=3000 leaves ~10% headroom for normal
    // upstream-vintage churn (ULB amalgamations / new municipal
    // notifications / spelling fixes that drop or merge a handful of
    // buckets). A sub-3000 reading indicates a regression — either
    // the upstream release shrank unexpectedly OR the lift script
    // silently SKIPped many ULBs on auto-fallback.
    expect(shards.length).toBeGreaterThanOrEqual(3000);
  });

  it("at least 28 states/UTs covered", () => {
    // C.3.b ship floor: 29 states/UTs (SBM_Wards upstream coverage;
    // the missing ~7 are HP, Sikkim, WB, TR, MZ, Goa, Lakshadweep —
    // reserved for C.3.d gap-fill). Floor=28 leaves room for a
    // single small UT to vanish without alarming.
    expect(statesCovered.length).toBeGreaterThanOrEqual(28);
  });

  it("S24 (Uttar Pradesh) is present — high-density coverage canary", () => {
    // S24 contributes 638 ULBs / 11,843 wards — the largest
    // single-state bucket by both ULB and ward count. If S24
    // vanishes, the lift's grouping has broken (silent property-name
    // drift on upstream side, or state_lgd resolver miss).
    expect(statesCovered).toContain("S24");
  });

  it("S20 (Maharashtra) is present — mega-corp ULB canary", () => {
    // S20 contributes 202 ULBs / 7,424 wards — including the
    // mega-corporations MCGM (Greater Mumbai), PMC (Pune), NMC
    // (Nagpur). If S20 vanishes, either the largest ULBs tripped
    // auto-fallback OR Maharashtra was silently dropped.
    expect(statesCovered).toContain("S20");
  });
});

describe("ward shards — well-formed shape", () => {
  it("every shard sits under state=<lgd-slug>/ulb=<lgd>/all.geojson", () => {
    // Structural: the discoverShards regex already filters
    // mal-shaped dirs; this assertion locks in that the discovery
    // yielded a non-empty set with the expected shape (i.e. no
    // empty-state dirs survived).
    expect(shards.length).toBeGreaterThan(0);
    for (const s of shards) {
      expect(s.stateCode).toMatch(/^[SU]\d{2}$/);
      expect(s.ulbLgd).toBeGreaterThan(0);
      expect(Number.isInteger(s.ulbLgd)).toBe(true);
    }
  });

  it("ULB LGD codes are unique within each state", () => {
    // Double-emission canary: a single (state_lgd, ulb_lgd) bucket
    // must produce exactly one shard. If the lift's grouping loop
    // somehow emitted the same bucket twice (e.g. an upstream
    // property duplication), this would surface as duplicate ulb=
    // dirs under the same state.
    const byState = new Map<string, number[]>();
    for (const s of shards) {
      if (!byState.has(s.stateCode)) byState.set(s.stateCode, []);
      byState.get(s.stateCode)!.push(s.ulbLgd);
    }
    for (const [state, codes] of byState) {
      const unique = new Set(codes);
      expect(
        unique.size,
        `state ${state} has duplicate ULB LGD codes: ${codes.length} shards but only ${unique.size} unique ULBs`,
      ).toBe(codes.length);
    }
  });
});

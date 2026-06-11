// state-panchayats-shards-coverage contract test.
//
// Invariant: every nested Gram-Panchayat GeoJSON shard that exists on
// disk under `datasets/boundaries/in/panchayats/state=<lgd-slug>/district=
// <lgd>/all.geojson` MUST sit at a well-formed Hive path and the
// shipped coverage MUST stay above the C.2.b documented floor.
//
// File-name note: docs/archive/plans/20260529-boundary-rip-and-replace-plan.md row
// C.2.b cites this file as `state-panchayats-registry-coverage.test.ts`.
// The deliverable was renamed `*-shards-coverage` because the frontend
// `PANCHAYAT_BOUNDARY_BY_DISTRICT` registry does NOT land until C.2.c
// (district-picker UI scope) — at C.2.b there is no registry to compare
// the shards AGAINST, only the on-disk corpus to lock a coverage floor
// in. When C.2.c lands the registry, it will add a separate
// `state-panchayats-registry-coverage.test.ts` mirroring the blocks
// precedent (symmetric shards↔registry coverage); this file then
// continues to lock the corpus floor independently.
//
// The C.2.b live lift (2026-05-30, ramSeraph LGD_Panchayats release)
// emitted 663 shards across 28 states/UTs from 319,287 upstream
// features. Coverage gap vs blocks (36 states/UTs): ~8 small states/UTs
// missing from upstream LGD_Panchayats (HP, J&K, Sikkim + most NE
// states + some UTs) — reserved for C.2.d Bhuvan gap-fill.
//
// Per-shard shape assertions:
//   - Path matches the Hive partition regex
//   - district= segment is a positive-integer LGD district code
//   - state= segment is a 3-char yen-gov entity code (lowercase s|u + 2 digits)
//   - District codes are unique within each state (no double-emission)

import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ECI_TO_LGD_SLUG } from "../lib/boundaries/sources";

const SLUG_TO_ECI: Record<string, string> = Object.fromEntries(
  Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
);

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const panchayatsDir = resolve(repoRoot, "datasets", "boundaries", "in", "panchayats");

interface DiscoveredShard {
  stateCode: string; // "S01" / "U02" (uppercase)
  districtLgd: number;
}

// Discover every on-disk panchayat shard under the nested Hive layout.
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
        out.push({ stateCode, districtLgd: Number(dm[1]) });
      }
    }
  }
  return out;
}

const shards = discoverShards();
const statesCovered = Array.from(new Set(shards.map((s) => s.stateCode))).sort();

describe("panchayat shards — corpus coverage floor (C.2.b)", () => {
  it("at least 600 on-disk panchayat shards", () => {
    // C.2.b ship floor: 663 shards from the 2026-05-30 ramSeraph
    // snapshot. Floor=600 leaves ~10% headroom for normal
    // upstream-vintage churn (district splits / merges / spelling
    // fixes that drop a handful of buckets). A sub-600 reading
    // indicates a regression — either the upstream release shrank
    // unexpectedly OR the lift script silently SKIPped many
    // districts on auto-fallback.
    expect(shards.length).toBeGreaterThanOrEqual(600);
  });

  it("at least 27 states/UTs covered", () => {
    // C.2.b ship floor: 28 states/UTs (LGD upstream coverage; the
    // missing ~8 are HP, J&K, Sikkim + most NE states + some UTs,
    // reserved for C.2.d Bhuvan gap-fill). Floor=27 leaves room for
    // a single small UT to vanish without alarming.
    expect(statesCovered.length).toBeGreaterThanOrEqual(27);
  });

  it("S13 (Madhya Pradesh) is present — high-density coverage canary", () => {
    // S13 contributes 36 districts / 35,707 panchayats — the largest
    // single-state bucket. If S13 vanishes, the lift's grouping has
    // broken (silent property-name drift on upstream side, or
    // state_lgd resolver miss).
    expect(statesCovered).toContain("S13");
  });

  it("S24 (Uttar Pradesh) is present — auto-fallback canary", () => {
    // S24 contributes 75 districts / 72,045 panchayats — the largest
    // by district count. PR #443 inherited the auto-fallback path
    // from blocks; if any district trips the precision=2 SKIP, this
    // assertion still holds because most shards land cleanly.
    expect(statesCovered).toContain("S24");
  });
});

describe("panchayat shards — well-formed shape", () => {
  it("every shard sits under state=<lgd-slug>/district=<lgd>/all.geojson", () => {
    // Structural: the discoverShards regex already filters
    // mal-shaped dirs; this assertion locks in that the discovery
    // yielded a non-empty set with the expected shape (i.e. no
    // empty-state dirs survived T.0d's sidecar purge).
    expect(shards.length).toBeGreaterThan(0);
    for (const s of shards) {
      expect(s.stateCode).toMatch(/^[SU]\d{2}$/);
      expect(s.districtLgd).toBeGreaterThan(0);
      expect(Number.isInteger(s.districtLgd)).toBe(true);
    }
  });

  it("district LGD codes are unique within each state", () => {
    // Double-emission canary: a single (state_lgd, district_lgd)
    // bucket must produce exactly one shard. If the lift's grouping
    // loop somehow emitted the same bucket twice (e.g. an upstream
    // property duplication), this would surface as duplicate
    // district= dirs under the same state.
    const byState = new Map<string, number[]>();
    for (const s of shards) {
      if (!byState.has(s.stateCode)) byState.set(s.stateCode, []);
      byState.get(s.stateCode)!.push(s.districtLgd);
    }
    for (const [state, codes] of byState) {
      const unique = new Set(codes);
      expect(
        unique.size,
        `state ${state} has duplicate district LGD codes: ${codes.length} shards but only ${unique.size} unique districts`,
      ).toBe(codes.length);
    }
  });
});

// pc-slug-alias contract test (Row 5b of the map-geometry rip plan).
//
// The PC name-slug alias table (`pc-slug-alias.ts`) remaps a handful of
// canonical (electoral.csv) PC name-slugs to the 2024 geometry's name-slug
// for SAFE same-seat cases (2014 Karnataka city renamings + a few spelling
// variants). This test reads the ONE national 2024 PC geometry off disk and
// proves two safety invariants on the curated table:
//
//   1. Every alias VALUE resolves to a real `pc_slug_uid` in the geometry —
//      so an alias can never paint a result on a non-existent seat.
//   2. Every alias KEY is a genuine MISS (NOT already a real `pc_slug_uid`) —
//      so we only fill gaps, never shadow / re-point a seat that already
//      joins correctly.
//
// It is a bounded canary over the fixed 17-entry table, NOT a corpus walk
// (it reads the single PC geometry once, asserts on the table, and never
// enumerates electoral.csv). Per CLAUDE.md §15 + the plan's no-corpus-walk
// rule.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  PC_SLUG_UID_ALIASES,
  aliasPcSlugUid,
} from "./pc-slug-alias";

const repoRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
  "..",
);
const pcGeojsonPath = resolve(
  repoRoot,
  "datasets",
  "boundaries",
  "electoral",
  "delim=2024",
  "pc",
  "all.geojson",
);

function geometryUids(): Set<string> {
  const gj = JSON.parse(readFileSync(pcGeojsonPath, "utf-8")) as {
    features: { properties: Record<string, unknown> }[];
  };
  const out = new Set<string>();
  for (const f of gj.features) {
    const uid = f.properties.pc_slug_uid;
    if (typeof uid === "string" && uid) out.add(uid);
  }
  return out;
}

describe("PC name-slug alias table", () => {
  const uids = geometryUids();

  it("geometry exposes a non-trivial pc_slug_uid set", () => {
    expect(uids.size).toBeGreaterThan(500); // 543 LS PCs
  });

  it("every alias VALUE resolves to a real 2024 pc_slug_uid", () => {
    const dangling = Object.entries(PC_SLUG_UID_ALIASES)
      .filter(([, value]) => !uids.has(value))
      .map(([key, value]) => `${key} -> ${value}`);
    expect(
      dangling,
      `alias values must point at a real 2024 PC polygon; dangling: ${dangling.join(", ")}`,
    ).toEqual([]);
  });

  it("every alias KEY is a genuine miss (does not shadow a real seat)", () => {
    const shadowing = Object.keys(PC_SLUG_UID_ALIASES).filter((key) =>
      uids.has(key),
    );
    expect(
      shadowing,
      `alias keys must be genuine misses, not real seats; shadowing: ${shadowing.join(", ")}`,
    ).toEqual([]);
  });

  it("every alias is state-prefixed and maps within the same state", () => {
    for (const [key, value] of Object.entries(PC_SLUG_UID_ALIASES)) {
      const keyState = key.split("_", 1)[0];
      const valState = value.split("_", 1)[0];
      expect(keyState).toMatch(/^[SU]\d{2}$/);
      expect(valState).toBe(keyState);
    }
  });

  it("does NOT alias any genuine-change (re-delimited) seat", () => {
    // The Assam 2023 + J&K 2022 re-delimited seats carry an `-ex-` tag in
    // the 2024 geometry; they MUST stay grey (different polygon shape), so
    // none of their canonical slugs may appear as an alias key.
    const forbiddenKeys = [
      "S03_mangaldoi",
      "S03_kaziranga",
      "S03_sonitpur",
      "S03_autonomous-district",
      "U08_anantnag",
    ];
    for (const k of forbiddenKeys) {
      expect(
        Object.prototype.hasOwnProperty.call(PC_SLUG_UID_ALIASES, k),
        `${k} is a genuine-change seat and must NOT be aliased`,
      ).toBe(false);
    }
  });

  it("aliasPcSlugUid is a no-op for numeric 2024 uids and unknown slugs", () => {
    expect(aliasPcSlugUid("S07_5")).toBe("S07_5");
    expect(aliasPcSlugUid("S07_karnal")).toBe("S07_karnal");
    expect(aliasPcSlugUid("S10_bengaluru-central")).toBe("S10_bangalore-central");
  });
});

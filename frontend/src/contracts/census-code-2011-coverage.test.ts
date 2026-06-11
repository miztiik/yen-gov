// Contract test for the census_code_2011 enrichment of the district
// topology (PR-3 of TODO/20260611-elections-off-maplibre-and-map-ux-plan.md;
// Hans + Max authority, user pre-approved 2026-06-11).
//
// Why this lives at the contract layer:
//
//   - The new property is the load-bearing join key for every
//     Census-2011-derivative dataset the frontend renders. If the
//     boundary emitter ever stops merging the sidecar, every Census-
//     keyed indicator silently becomes unjoinable. This vitest file is
//     the daily ratchet that catches the regression at PR time.
//   - Coverage is measured against the on-disk feature count (785),
//     NOT the sidecar key count (784, because two POK features both
//     carry dist_lgd=0 and collapse to one sidecar entry). The
//     denominator is the citizen-visible feature count for clarity.
//   - Chennai (dist_lgd=568) -> census_code_2011=603 is the one
//     hand-pinned oracle from the brief. Census 2011 published 603 as
//     Chennai's district code, and the data-analytics.github.io
//     topology is a Census 2011 derivative. If the upstream ever
//     republishes with a different code (vintage drift) the assertion
//     fails loud and the agent re-derives.
//
// What this does NOT assert:
//
//   - Coordinate-level integrity (covered by topojson-island-render).
//   - Geojson <-> topojson feature-count parity (covered by
//     boundaries-conform).
//   - 100% coverage. The post-2011 bifurcation residual (Telangana
//     2014, Ladakh 2019, Andhra 2022, Rajasthan 2023, etc.) is real:
//     those districts did not exist when Census 2011 was published.
//     Inheriting the parent's Census code requires a hand-curated
//     parent map that is intentionally out of scope for this PR.

import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import type { Feature, FeatureCollection, Geometry } from "geojson";

const TOPO_PATH = resolve(
  __dirname,
  "..",
  "..",
  "..",
  "datasets",
  "boundaries",
  "in",
  "districts",
  "all.topojson",
);

// Coverage threshold. Actual achieved on the 2026-06-11 emit: 641/785 =
// 81.7%. We lock in at 625/785 (>= 79.6%) which leaves headroom for one
// or two upstream LGD updates to ship without false-failing the gate,
// while still failing loud if a regression cuts the joined corpus by
// >= 16 districts. Re-derive the threshold via
// `python -m tools.boundaries.enrich_census_code_2011 --repo-root .`
// (the `matched` field of its summary JSON is the live number).
const MIN_MATCHED_DISTRICTS = 625;

// Hand-pinned oracle: Chennai's published Census 2011 district code.
// Sourced from the Office of the Registrar General & Census Commissioner
// 2011 district directory; mirrored by the data-analytics.github.io
// topology's `censuscode` property.
const CHENNAI_DIST_LGD = 568;
const CHENNAI_CENSUS_2011_CODE = 603;

interface DistrictProps {
  dist_lgd: number;
  dtname?: string;
  stname?: string;
  census_code_2011?: number | null;
}

type DistrictFeature = Feature<Geometry, DistrictProps>;
type DistrictCollection = FeatureCollection<Geometry, DistrictProps>;

function loadDistrictCollection(): DistrictCollection {
  const raw = readFileSync(TOPO_PATH, "utf8");
  const topology = JSON.parse(raw) as Topology;
  const objectKey = Object.keys(topology.objects)[0];
  return feature(topology, topology.objects[objectKey]) as unknown as DistrictCollection;
}

describe("PR-3 census_code_2011 enrichment (boundary feature property contract)", () => {
  test("every district feature carries the census_code_2011 property key", () => {
    const collection = loadDistrictCollection();
    const missing = collection.features.filter(
      (f) => !Object.prototype.hasOwnProperty.call(f.properties ?? {}, "census_code_2011"),
    );
    expect(
      missing.length,
      `${missing.length} features missing the census_code_2011 property key. ` +
        `The boundary emitter must merge the sidecar at ` +
        `datasets/boundaries/in/districts/census_code_2011.json into every ` +
        `feature's properties; absent districts must explicitly carry null, ` +
        `not undefined. Sample: ${JSON.stringify(missing.slice(0, 3).map((f) => f.properties))}`,
    ).toBe(0);
  });

  test("census_code_2011 values are integers in [1, 640] or null", () => {
    const collection = loadDistrictCollection();
    const offenders = collection.features.filter((f) => {
      const v = f.properties?.census_code_2011;
      if (v === null || v === undefined) return v === undefined; // undefined fails; null OK
      if (!Number.isInteger(v)) return true;
      // Census 2011 published 640 district codes. Values outside this
      // range are a sign the upstream LGD's synthetic dtcode11 (>= 700
      // for post-2011 districts) leaked into the sidecar.
      if (v < 1 || v > 640) return true;
      return false;
    });
    expect(
      offenders.length,
      `${offenders.length} features carry an out-of-range census_code_2011. ` +
        `Expected: integer 1..640 or null. Sample: ${JSON.stringify(
          offenders.slice(0, 5).map((f) => ({
            dist_lgd: f.properties?.dist_lgd,
            dtname: f.properties?.dtname,
            census_code_2011: f.properties?.census_code_2011,
          })),
        )}`,
    ).toBe(0);
  });

  test(`>= ${MIN_MATCHED_DISTRICTS} of 785 districts carry a non-null census_code_2011`, () => {
    const collection = loadDistrictCollection();
    const matched = collection.features.filter(
      (f) => f.properties?.census_code_2011 != null,
    ).length;
    expect(
      matched,
      `Only ${matched}/${collection.features.length} districts joined to a Census ` +
        `2011 code (threshold ${MIN_MATCHED_DISTRICTS}). Either the upstream ` +
        `data-analytics.github.io topology changed shape, the LGD source ` +
        `published a name-spelling change, or the enrich tool's normalisation ` +
        `regressed. Re-run \`python -m tools.boundaries.enrich_census_code_2011 ` +
        `--repo-root .\` and inspect datasets/_ops/census-code-2011-coverage.json.`,
    ).toBeGreaterThanOrEqual(MIN_MATCHED_DISTRICTS);
  });

  test(`Chennai (dist_lgd=${CHENNAI_DIST_LGD}) -> census_code_2011=${CHENNAI_CENSUS_2011_CODE} (hand-pinned oracle)`, () => {
    const collection = loadDistrictCollection();
    const chennai = collection.features.find(
      (f) => f.properties?.dist_lgd === CHENNAI_DIST_LGD,
    );
    expect(chennai, `Chennai feature missing from districts/all.topojson`).toBeTruthy();
    expect(chennai!.properties?.dtname).toBe("Chennai");
    expect(
      chennai!.properties?.census_code_2011,
      `Chennai's Census 2011 code drifted. Expected ${CHENNAI_CENSUS_2011_CODE} ` +
        `(per the Office of the Registrar General & Census Commissioner's 2011 ` +
        `district directory).`,
    ).toBe(CHENNAI_CENSUS_2011_CODE);
  });

  test("known LGD-to-Census Bengaluru Urban / Mumbai Suburban oracles still hold", () => {
    // Anchors that exercise the dtcode11 fallback: 'Bengaluru Urban' (LGD)
    // -> 'Bangalore' (Census 2011) name renaming; 'Mumbai Suburban' (LGD)
    // -> 'Mumbai Suburban' (Census 2011) exact-name match.
    const collection = loadDistrictCollection();
    const bengaluruUrban = collection.features.find(
      (f) =>
        f.properties?.dtname === "Bengaluru Urban" &&
        f.properties?.stname === "KARNATAKA",
    );
    const mumbaiSuburban = collection.features.find(
      (f) =>
        f.properties?.dtname === "Mumbai Suburban" &&
        f.properties?.stname === "MAHARASHTRA",
    );
    expect(bengaluruUrban, "Bengaluru Urban absent from topology").toBeTruthy();
    expect(mumbaiSuburban, "Mumbai Suburban absent from topology").toBeTruthy();
    expect(
      bengaluruUrban!.properties?.census_code_2011,
      "Bengaluru Urban -> Census 2011 'Bangalore' (572)",
    ).toBe(572);
    expect(
      mumbaiSuburban!.properties?.census_code_2011,
      "Mumbai Suburban -> Census 2011 'Mumbai Suburban' (518)",
    ).toBe(518);
  });

  test("post-2011 PoK districts (Mirpur, Muzaffarabad) carry null", () => {
    // Sanity-check that the documented null sentinel reaches the topology:
    // these two J&K districts ship under dist_lgd=0 (sentinel) and were
    // never enumerated by India's Census because they are not under Indian
    // administration.
    const collection = loadDistrictCollection();
    const pokRows = collection.features.filter(
      (f) => f.properties?.dist_lgd === 0,
    );
    expect(pokRows.length, "expected 2 PoK feature rows with dist_lgd=0").toBe(2);
    for (const row of pokRows) {
      expect(
        row.properties?.census_code_2011,
        `${row.properties?.dtname} should carry null (no Census 2011 enumeration)`,
      ).toBeNull();
    }
  });
});

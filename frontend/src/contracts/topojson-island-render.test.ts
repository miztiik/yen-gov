// F4 island-render-smoke gate per parent plan section 21.11 frozen
// requirement (a): byte-confirm Lakshadweep + Andaman & Nicobar + all
// islands actually draw from the arcs-only district topojson at
// datasets/boundaries/in/districts/all.topojson.
//
// This is the offline (vitest node-env) half of the gate: it does NOT
// render to a real DOM, but it DOES exercise the full d3-geo +
// topojson-client decode + projection + path serialisation pipeline
// that the future <GeoChoropleth> primitive (F2b) will use. If any
// link in that chain drops the island arcs, this test catches it
// before a renderer is written - which is the whole point of section
// 21.11's "byte-confirm" framing.
//
// Why this lives at the contract layer and not in Playwright:
//
//   - The relevant failure modes are (a) the topojson arcs file is
//     missing the island ring, (b) the geometry's properties dropped
//     `dist_lgd`, (c) the projection produces a degenerate path (NaN /
//     empty / zero-area). All three are pure data + math; a real DOM
//     adds nothing.
//   - Playwright lives in `frontend/e2e/` and runs only against the
//     dev / built site; it cannot answer "do the arcs exist in the
//     source file?" without the chart engine being live, which is
//     F2b's work, not F4's.
//   - Vitest node-env is the established home for non-DOM map
//     contracts (see boundaries-conform.test.ts in this folder for
//     the precedent).
//
// Doctrine:
//
//   - The four island districts are pinned by the LGD codes the
//     parent plan section 21.11 cites (Lakshadweep = `dist_lgd 553`)
//     plus the three Andaman & Nicobar districts present in
//     `datasets/boundaries/in/districts/all.topojson` (lgds 602 /
//     603 / 632 = South Andamans / Nicobars / North And Middle
//     Andaman). If the pinned LGD codes ever change (LGD vintage
//     refresh, district reorganisation), the test fails loud and
//     the pinned set must be re-derived from the same `all.topojson`
//     before the test is re-greened. The point of the smoke is to
//     catch silent drift; loosening the pin defeats it.
//
//   - The projection used is `geoMercator` because that is what
//     parent plan section 14.5 table cites as the default for the
//     d3-geo SVG welfare-map renderer. Choosing a more exotic
//     projection here would test something the future renderer will
//     not use.
//
//   - The test asserts shape, not byte-for-byte path equality.
//     Quantization, projection precision, and viewport-fitting are
//     all allowed to drift without flagging this test. What is NOT
//     allowed to drift: each island geometry produces a non-empty
//     SVG path string with non-degenerate spherical-area bounds.

import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import { geoMercator, geoPath, geoArea, geoBounds } from "d3-geo";
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

/**
 * The four island districts pinned in parent plan section 21.11.
 * Re-derived from datasets/boundaries/in/districts/all.topojson on
 * 2026-06-05 via `node -e "..." | grep islands` (see
 * docs/architecture/frontend/topojson-loader.md "Island render smoke"
 * receipt).
 */
const PINNED_ISLAND_DIST_LGD = {
  lakshadweep: 553,
  south_andamans: 602,
  nicobars: 603,
  north_and_middle_andaman: 632,
} as const;

interface DistrictProps {
  dist_lgd: number;
  dtname?: string;
  stname?: string;
}

type DistrictFeature = Feature<Geometry, DistrictProps>;
type DistrictCollection = FeatureCollection<Geometry, DistrictProps>;

function loadDistrictCollection(): DistrictCollection {
  const raw = readFileSync(TOPO_PATH, "utf8");
  const topology = JSON.parse(raw) as Topology;
  const objectKey = Object.keys(topology.objects)[0];
  const collection = feature(topology, topology.objects[objectKey]) as unknown as DistrictCollection;
  return collection;
}

function findByLgd(collection: DistrictCollection, lgd: number): DistrictFeature {
  const match = collection.features.find(f => f.properties?.dist_lgd === lgd);
  if (!match) {
    throw new Error(`Island district lgd=${lgd} missing from all.topojson; section 21.11 frozen-requirement breach`);
  }
  return match;
}

describe("F4 island-render-smoke (parent plan section 21.11 frozen requirement a)", () => {
  test("districts/all.topojson decodes into a FeatureCollection with all 785 districts", () => {
    const collection = loadDistrictCollection();
    expect(collection.type).toBe("FeatureCollection");
    expect(collection.features.length).toBe(785);
  });

  test.each(Object.entries(PINNED_ISLAND_DIST_LGD))(
    "%s (dist_lgd=%i) is present in the topojson",
    (name, lgd) => {
      const collection = loadDistrictCollection();
      const island = findByLgd(collection, lgd);
      expect(island.properties.dist_lgd).toBe(lgd);
      // dtname is the citizen-visible label; if it ever goes empty
      // the choropleth tooltip is silently broken.
      expect(island.properties.dtname).toBeTruthy();
      // The geometry payload must be non-empty.
      expect(island.geometry).toBeTruthy();
    },
  );

  test.each(Object.entries(PINNED_ISLAND_DIST_LGD))(
    "%s (dist_lgd=%i) has a non-zero spherical area in the source topojson",
    (name, lgd) => {
      const collection = loadDistrictCollection();
      const island = findByLgd(collection, lgd);
      const area = geoArea(island);
      // geoArea returns the area in steradians; islands are small but
      // emphatically not zero. The smallest island in this set
      // (Lakshadweep ~32 km^2 of land split across multiple atolls)
      // still measures well above 1e-12 sr in geographic coordinates.
      expect(area).toBeGreaterThan(0);
    },
  );

  test.each(Object.entries(PINNED_ISLAND_DIST_LGD))(
    "%s (dist_lgd=%i) has finite, non-degenerate geographic bounds",
    (name, lgd) => {
      const collection = loadDistrictCollection();
      const island = findByLgd(collection, lgd);
      const bounds = geoBounds(island);
      // bounds is [[westLon, southLat], [eastLon, northLat]] in degrees.
      for (const corner of bounds) {
        for (const coord of corner) {
          expect(Number.isFinite(coord)).toBe(true);
        }
      }
      // No collapsed bounding box.
      expect(bounds[1][0]).toBeGreaterThan(bounds[0][0]);
      expect(bounds[1][1]).toBeGreaterThan(bounds[0][1]);
      // Sanity: islands sit between roughly 6N..14N and 72E..94E in
      // the Indian context; loose-fit to allow for vintage drift.
      const [westLon, southLat] = bounds[0];
      const [eastLon, northLat] = bounds[1];
      expect(westLon).toBeGreaterThan(60);
      expect(eastLon).toBeLessThan(100);
      expect(southLat).toBeGreaterThan(0);
      expect(northLat).toBeLessThan(20);
    },
  );

  test("d3-geo geoMercator + geoPath produces a non-empty SVG path string for each island", () => {
    const collection = loadDistrictCollection();
    // Fit a single Mercator projection to the WHOLE country so the
    // islands share the projection they will get in production
    // (parent plan section 14.5: "single frame, no insets").
    const projection = geoMercator().fitSize([800, 800], collection);
    const path = geoPath(projection);
    for (const [name, lgd] of Object.entries(PINNED_ISLAND_DIST_LGD)) {
      const island = findByLgd(collection, lgd);
      const d = path(island);
      // The projected path string must:
      //   1. exist (no null = the projection accepted the geometry),
      //   2. be non-empty (no degenerate zero-segment output),
      //   3. start with the SVG moveTo command "M" (one ring or more),
      //   4. contain at least one line/curve command (L / Z / C / Q /
      //      A) - "M" alone with no following command means the
      //      projection collapsed every vertex to one point.
      expect(d, `${name} (lgd=${lgd}) projected to a null path`).toBeTruthy();
      expect(d!.length, `${name} (lgd=${lgd}) projected to an empty path`).toBeGreaterThan(0);
      expect(d!.startsWith("M"), `${name} (lgd=${lgd}) path does not start with M`).toBe(true);
      expect(/[LZCQA]/.test(d!), `${name} (lgd=${lgd}) projected to a single-point path`).toBe(true);
    }
  });
});

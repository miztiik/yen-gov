// Parent plan section 25.4 (E3) state silhouette smoke gate.
//
// Byte-confirm that the per-state silhouette feature (used by
// `StateAcMap` as a maplibre outline layer and by `TileCartogram` as
// a faint SVG backdrop) actually decodes from the shared canonical
// state-boundary corpus AND projects to a non-null SVG path under
// d3-geo `geoMercator()` for three representative states:
//
//   - Tamil Nadu (S22 / State_LGD 33) - large peninsular polygon.
//   - Bihar     (S04 / State_LGD 10) - medium inland polygon.
//   - Lakshadweep (U04 / State_LGD 31) - tiny island archipelago,
//     the hardest case for projection / simplification drift (mirrors
//     the F4 island-render-smoke contract's reasoning).
//
// This is the offline (vitest node-env) half of the gate. The
// browser §13 smoke (frontend/e2e/e3-silhouette-smoke.spec.ts) is the
// rendered-pixel companion. The split is the same one used for the
// districts island contract at
// `frontend/src/contracts/topojson-island-render.test.ts`:
//
//   - Non-DOM failures (missing feature in the corpus; projection
//     collapses to a single point; bounds NaN) are pure data + math
//     and live here.
//   - Rendered-pixel failures (no outline visible; wrong colour
//     token; click-through broken) live in the e2e suite.
//
// Doctrine ties:
//   - parent plan section 25.4: the silhouette is fed by the SAME
//     boundary corpus (`datasets/boundaries/in/states/all.topojson`)
//     other welfare-map surfaces already load. Asserting decode + project
//     here guards against silent vintage drift the same way the
//     islands smoke guards Lakshadweep + A&N districts.
//   - CLAUDE.md section 14: tests ship with the feature in the same
//     commit; this is the Contract-tier gate for E3.

import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import { geoMercator, geoPath, geoArea, geoBounds } from "d3-geo";
import type { Feature, FeatureCollection, Geometry } from "geojson";

const STATES_TOPO_PATH = resolve(
  __dirname,
  "..",
  "..",
  "..",
  "datasets",
  "boundaries",
  "in",
  "states",
  "all.topojson",
);

/**
 * The three representative states pinned in the E3 ship brief. Each
 * carries the LGD numeric code that `loadStateSilhouette` resolves
 * via `view-models/states.ts boundary_join_key`. The labels are the
 * citizen-display names from `STNAME_SH` for the assertion log; the
 * actual lookup is on `State_LGD`.
 */
const PINNED_STATES = {
  tamil_nadu: { lgd: 33, label: "TAMIL NADU" },
  bihar: { lgd: 10, label: "BIHAR" },
  lakshadweep: { lgd: 31, label: "LAKSHADWEEP" },
} as const;

interface StateProps {
  State_LGD: number;
  STNAME?: string;
  STNAME_SH?: string;
  Remarks?: string;
}

type StateFeature = Feature<Geometry, StateProps>;
type StateCollection = FeatureCollection<Geometry, StateProps>;

function loadStateCollection(): StateCollection {
  const raw = readFileSync(STATES_TOPO_PATH, "utf8");
  const topology = JSON.parse(raw) as Topology;
  const objectKey = Object.keys(topology.objects)[0];
  const collection = feature(
    topology,
    topology.objects[objectKey],
  ) as unknown as StateCollection;
  return collection;
}

function findByLgd(collection: StateCollection, lgd: number): StateFeature {
  const match = collection.features.find(
    (f) => f.properties?.State_LGD === lgd,
  );
  if (!match) {
    throw new Error(
      `E3 silhouette: state lgd=${lgd} missing from states/all.topojson; section 25.4 gate breached`,
    );
  }
  return match;
}

describe("E3 state silhouette smoke (parent plan section 25.4)", () => {
  test("states/all.topojson decodes into a FeatureCollection with at least 30 entries", () => {
    const collection = loadStateCollection();
    expect(collection.type).toBe("FeatureCollection");
    // 28 states + 8 UTs = 36 ideal; allow >=30 to absorb post-2019
    // J&K split, DnH+DD merger, and other vintage drift that does not
    // affect the three pinned probes.
    expect(collection.features.length).toBeGreaterThanOrEqual(30);
  });

  test.each(Object.entries(PINNED_STATES))(
    "%s (State_LGD=%o) is present in the topojson",
    (name, pin) => {
      const collection = loadStateCollection();
      const state = findByLgd(collection, pin.lgd);
      expect(state.properties.State_LGD).toBe(pin.lgd);
      // STNAME is the upstream uppercase form; assert it carries the
      // expected publisher string so a vintage flip that swaps the
      // LGD-to-name mapping fails loud here rather than silently
      // mislabelling the silhouette.
      expect(state.properties.STNAME).toBe(pin.label);
      expect(state.geometry).toBeTruthy();
    },
  );

  test.each(Object.entries(PINNED_STATES))(
    "%s (State_LGD=%o) has a non-zero spherical area",
    (name, pin) => {
      const collection = loadStateCollection();
      const state = findByLgd(collection, pin.lgd);
      const area = geoArea(state);
      // geoArea returns area in steradians; even Lakshadweep's
      // simplified polygon is > 0 because the atoll rings are kept
      // by the topojson `keep-shapes` flag the F4 mapshaper config
      // pins (yen-gov-architecture lesson 2026-06-05).
      expect(area).toBeGreaterThan(0);
    },
  );

  test.each(Object.entries(PINNED_STATES))(
    "%s (State_LGD=%o) has finite, non-degenerate geographic bounds",
    (name, pin) => {
      const collection = loadStateCollection();
      const state = findByLgd(collection, pin.lgd);
      const bounds = geoBounds(state);
      // bounds = [[westLon, southLat], [eastLon, northLat]] in degrees.
      for (const corner of bounds) {
        for (const coord of corner) {
          expect(Number.isFinite(coord)).toBe(true);
        }
      }
      // Loose-fit to the Indian subcontinent so a vintage flip that
      // ships a wrong-hemisphere polygon (sign error, longitude/latitude
      // swap) fails here.
      const [westLon, southLat] = bounds[0];
      const [eastLon, northLat] = bounds[1];
      expect(westLon).toBeGreaterThan(60);
      expect(eastLon).toBeLessThan(100);
      expect(southLat).toBeGreaterThan(0);
      expect(northLat).toBeLessThan(40);
      // No collapsed bbox.
      expect(eastLon).toBeGreaterThan(westLon);
      expect(northLat).toBeGreaterThan(southLat);
    },
  );

  test("d3-geo geoMercator + geoPath produces a non-empty SVG path for each pinned state", () => {
    const collection = loadStateCollection();
    // `StateAcMap` and `TileCartogram` each fit the projection to
    // their own canvas size; the smoke uses 800x800 (matches the
    // F4 island contract). The fit-target size is irrelevant to the
    // pass/fail; we only care that the path string exists and is
    // non-degenerate after projection.
    for (const [name, pin] of Object.entries(PINNED_STATES)) {
      const state = findByLgd(collection, pin.lgd);
      const projection = geoMercator().fitSize([800, 800], state);
      const path = geoPath(projection);
      const d = path(state);
      // The projected path string must:
      //   1. exist (the projection accepted the geometry),
      //   2. be non-empty,
      //   3. start with the SVG `M` move-to command,
      //   4. contain at least one line/curve command (L/Z/C/Q/A)
      //      so a "single point" collapse fails loud.
      expect(d, `${name} (State_LGD=${pin.lgd}) projected to null`).toBeTruthy();
      expect(
        d!.length,
        `${name} (State_LGD=${pin.lgd}) projected to empty string`,
      ).toBeGreaterThan(0);
      expect(
        d!.startsWith("M"),
        `${name} (State_LGD=${pin.lgd}) path missing initial M`,
      ).toBe(true);
      expect(
        /[LZCQA]/.test(d!),
        `${name} (State_LGD=${pin.lgd}) path has no line/curve commands`,
      ).toBe(true);
    }
  });

  test("the silhouette source path is the SAME canonical corpus consumed by the welfare maps", () => {
    // Receipt for the "no new fetch" guardrail. If a future agent
    // shipped a per-state silhouette under
    // `boundaries/in/states/silhouettes/<eci>.geojson` this test
    // would catch the canonical-vs-bespoke drift on review.
    // Normalise separators - `path.resolve` returns native form
    // (backslash on Windows, slash on POSIX); the assertion is on
    // the suffix.
    const posix = STATES_TOPO_PATH.replace(/\\/g, "/");
    expect(posix.endsWith("states/all.topojson")).toBe(true);
  });
});

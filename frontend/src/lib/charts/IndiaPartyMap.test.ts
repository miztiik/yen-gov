// PR-4 of TODO/20260611-elections-off-maplibre-and-map-ux-plan.md
// (IndiaMap d3-geo replacement + Lakshadweep dot marker).
//
// Pure-helper + topojson-pipeline contract for IndiaPartyMap.svelte's
// sub-threshold marker overlay. Per repo vitest doctrine (node-env, no
// jsdom canvas, no @testing-library/svelte mounts), this file does NOT
// mount the Svelte component; it covers:
//
//   1. The pure helper module (pathSpan / isSubThreshold /
//      projectedCentroid / computeSubThresholdMarkers / SUB_THRESHOLD_PX).
//   2. The end-to-end topojson -> projection -> path -> marker pipeline
//      against the real `datasets/boundaries/in/states/all.topojson`
//      (the same input the live component fetches). This proves the
//      36 states render, that Lakshadweep IS detected as sub-threshold,
//      that the citizen-clickable marker carries a sensible centroid
//      and the correct State_LGD join key, and that mainland states
//      are NOT flagged for marker rendering.
//
// The rendered SVG shape (button trio, hover tooltip, click navigate,
// d3-zoom transform) is covered by the CLAUDE.md section 13 browser
// smoke captured in the PR body. Same split as
// frontend/src/lib/maplibre/MapChoropleth.zoom-controls.test.ts +
// frontend/src/contracts/topojson-island-render.test.ts.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";
import { feature as topojsonFeature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import { geoMercator, geoPath, type GeoPermissibleObjects } from "d3-geo";
import type {
  Feature,
  FeatureCollection,
  Geometry,
} from "geojson";

import {
  SUB_THRESHOLD_PX,
  computeSubThresholdMarkers,
  isSubThreshold,
  pathSpan,
  projectedCentroid,
  resolveStateClickAction,
} from "./india-party-map-helpers";

// Same path resolution pattern as
// frontend/src/contracts/topojson-island-render.test.ts.
const TOPO_PATH = resolve(
  __dirname,
  "..",
  "..",
  "..",
  "..",
  "datasets",
  "boundaries",
  "in",
  "states",
  "all.topojson",
);

// Mirror the live component's projection size + join property so the
// test exercises the same inputs the citizen sees in the browser.
const WIDTH = 640;
const HEIGHT = 480;
const JOIN_PROPERTY = "State_LGD";
const LAKSHADWEEP_LGD = 31;
const TAMIL_NADU_LGD = 33;

interface StateProps {
  State_LGD: number;
  STNAME?: string;
  Remarks?: string;
}

type StateFeature = Feature<Geometry, StateProps>;
type StateCollection = FeatureCollection<Geometry, StateProps>;

function loadStateCollection(): StateCollection {
  const raw = readFileSync(TOPO_PATH, "utf8");
  const topology = JSON.parse(raw) as Topology;
  const objectKeys = Object.keys(topology.objects);
  const collection = topojsonFeature(
    topology,
    topology.objects[objectKeys[0]] as GeometryCollection,
  ) as unknown as StateCollection;
  return collection;
}

function buildProjectionAndPath(collection: StateCollection): {
  projection: ReturnType<typeof geoMercator>;
  path: ReturnType<typeof geoPath>;
} {
  const projection = geoMercator().fitSize(
    [WIDTH, HEIGHT],
    collection as unknown as GeoPermissibleObjects,
  );
  const path = geoPath(projection);
  return { projection, path };
}

describe("IndiaPartyMap helpers - SUB_THRESHOLD_PX constant", () => {
  test("is the calibrated 14 px value", () => {
    // Locked: a future tuning bump that changes this needs a
    // matching plan-doc note. Lakshadweep's 0.14 px max-dim at the
    // 640x480 viewBox is comfortably below 14; the threshold needs
    // to ALSO catch Chandigarh / Delhi / Goa per the PR-4 row.
    expect(SUB_THRESHOLD_PX).toBe(14);
  });
});

describe("IndiaPartyMap helpers - isSubThreshold", () => {
  test("returns true when max(width, height) < threshold", () => {
    expect(isSubThreshold({ width: 5, height: 10 }, 14)).toBe(true);
    expect(isSubThreshold({ width: 0.14, height: 0.15 }, 14)).toBe(true);
  });
  test("returns false when either dimension >= threshold", () => {
    expect(isSubThreshold({ width: 14, height: 5 }, 14)).toBe(false);
    expect(isSubThreshold({ width: 5, height: 14 }, 14)).toBe(false);
    expect(isSubThreshold({ width: 100, height: 100 }, 14)).toBe(false);
  });
  test("defaults to SUB_THRESHOLD_PX when threshold omitted", () => {
    expect(isSubThreshold({ width: 13, height: 13 })).toBe(true);
    expect(isSubThreshold({ width: 15, height: 15 })).toBe(false);
  });
});

describe("IndiaPartyMap helpers - pathSpan + projectedCentroid", () => {
  test("pathSpan returns finite width + height for a mainland state", () => {
    const collection = loadStateCollection();
    const { path } = buildProjectionAndPath(collection);
    const tn = collection.features.find(
      (f) => f.properties.State_LGD === TAMIL_NADU_LGD,
    );
    expect(tn).toBeTruthy();
    const span = pathSpan(tn as StateFeature, path);
    expect(span).not.toBeNull();
    expect(span!.width).toBeGreaterThan(20);
    expect(span!.height).toBeGreaterThan(20);
  });

  test("projectedCentroid returns finite x + y inside the viewBox for a mainland state", () => {
    const collection = loadStateCollection();
    const { projection } = buildProjectionAndPath(collection);
    const tn = collection.features.find(
      (f) => f.properties.State_LGD === TAMIL_NADU_LGD,
    );
    const c = projectedCentroid(tn as StateFeature, projection);
    expect(c).not.toBeNull();
    expect(c![0]).toBeGreaterThan(0);
    expect(c![0]).toBeLessThan(WIDTH);
    expect(c![1]).toBeGreaterThan(0);
    expect(c![1]).toBeLessThan(HEIGHT);
  });

  test("projectedCentroid returns finite x + y inside the viewBox for Lakshadweep (sub-threshold)", () => {
    const collection = loadStateCollection();
    const { projection } = buildProjectionAndPath(collection);
    const lak = collection.features.find(
      (f) => f.properties.State_LGD === LAKSHADWEEP_LGD,
    );
    const c = projectedCentroid(lak as StateFeature, projection);
    expect(c).not.toBeNull();
    // Lakshadweep sits in the Arabian Sea off Kerala's coast - its
    // projected centroid must land inside the bottom-left of the
    // viewBox (left third, lower half).
    expect(c![0]).toBeGreaterThan(0);
    expect(c![0]).toBeLessThan(WIDTH / 2);
    expect(c![1]).toBeGreaterThan(HEIGHT / 3);
    expect(c![1]).toBeLessThan(HEIGHT);
  });
});

describe("IndiaPartyMap topojson pipeline against datasets/boundaries/in/states/all.topojson", () => {
  test("topojson decodes into 36 state features", () => {
    const collection = loadStateCollection();
    expect(collection.type).toBe("FeatureCollection");
    expect(collection.features.length).toBe(36);
  });

  test("every state carries a non-null State_LGD join property", () => {
    const collection = loadStateCollection();
    for (const f of collection.features) {
      expect(typeof f.properties.State_LGD).toBe("number");
      expect(Number.isFinite(f.properties.State_LGD)).toBe(true);
    }
  });

  test("computeSubThresholdMarkers detects Lakshadweep (the citizen-visibility oracle)", () => {
    const collection = loadStateCollection();
    const { projection, path } = buildProjectionAndPath(collection);
    const markers = computeSubThresholdMarkers(
      collection.features,
      projection,
      path,
      (f) => f.properties.State_LGD,
    );
    // The whole point of PR-4. Lakshadweep MUST be in the marker
    // overlay - otherwise the citizen still can't see it.
    const lak = markers.find((m) => m.key === String(LAKSHADWEEP_LGD));
    expect(lak, "Lakshadweep marker missing from sub-threshold overlay").toBeDefined();
    expect(lak!.cx).toBeGreaterThan(0);
    expect(lak!.cx).toBeLessThan(WIDTH / 2);
    expect(lak!.cy).toBeGreaterThan(0);
    expect(lak!.cy).toBeLessThan(HEIGHT);
  });

  test("Tamil Nadu (a large mainland state) is NOT flagged for marker rendering", () => {
    const collection = loadStateCollection();
    const { projection, path } = buildProjectionAndPath(collection);
    const markers = computeSubThresholdMarkers(
      collection.features,
      projection,
      path,
      (f) => f.properties.State_LGD,
    );
    expect(markers.find((m) => m.key === String(TAMIL_NADU_LGD))).toBeUndefined();
  });

  test("marker overlay size is bounded - more than 0, fewer than half the states", () => {
    // Loose contract so future viewBox / quantization drift can be
    // accommodated without test churn. The specific membership of
    // the overlay is tested for Lakshadweep + Tamil Nadu above; this
    // sanity-checks the helper does not flag every state (a bug
    // shape that would obscure the entire map under circles).
    const collection = loadStateCollection();
    const { projection, path } = buildProjectionAndPath(collection);
    const markers = computeSubThresholdMarkers(
      collection.features,
      projection,
      path,
      (f) => f.properties.State_LGD,
    );
    expect(markers.length).toBeGreaterThan(0);
    expect(markers.length).toBeLessThan(collection.features.length / 2);
  });

  test("computeSubThresholdMarkers skips features whose feature_key extractor returns null", () => {
    const collection = loadStateCollection();
    const { projection, path } = buildProjectionAndPath(collection);
    const markers = computeSubThresholdMarkers(
      collection.features,
      projection,
      path,
      () => null,
    );
    expect(markers.length).toBe(0);
  });

  test("computeSubThresholdMarkers respects an override threshold", () => {
    // A 0 px threshold flags nothing (no max(width, height) is
    // strictly less than 0). A huge threshold (1000 px) flags every
    // state. Both branches must hold; the constant test above
    // covers the production threshold value.
    const collection = loadStateCollection();
    const { projection, path } = buildProjectionAndPath(collection);

    const none = computeSubThresholdMarkers(
      collection.features,
      projection,
      path,
      (f) => f.properties.State_LGD,
      0,
    );
    expect(none.length).toBe(0);

    const all = computeSubThresholdMarkers(
      collection.features,
      projection,
      path,
      (f) => f.properties.State_LGD,
      1000,
    );
    expect(all.length).toBe(collection.features.length);
  });

  test("every projected path string for every state is non-empty + starts with M (sanity)", () => {
    const collection = loadStateCollection();
    const { path } = buildProjectionAndPath(collection);
    for (const f of collection.features) {
      const d = path(f);
      expect(d, `state ${f.properties.STNAME ?? f.properties.State_LGD} projected to a null path`).toBeTruthy();
      expect(d!.startsWith("M")).toBe(true);
    }
  });
});

describe("IndiaPartyMap helpers - resolveStateClickAction (PR-4c)", () => {
  // The PR-4c structural fix: IndiaPartyMap's click handler used to
  // hardcode `navigate(link.state(code))`. NationalElection needs the
  // click to stay in the event cohort. The resolver below decouples
  // the lookup + dispatch decision from the side effect so the Svelte
  // component can be tested via the helper in node-env (the rest of
  // this file's doctrine).

  const KEY_TO_ECI: Record<string, string> = {
    "33": "S22", // Tamil Nadu
    "27": "S13", // Maharashtra
    "31": "U09", // Lakshadweep (sub-threshold marker target)
  };

  test("returns navigate-default when no custom callback is supplied", () => {
    // The Home-page case. Default behaviour MUST be preserved.
    const action = resolveStateClickAction("33", KEY_TO_ECI, false);
    expect(action).toEqual({ kind: "navigate-default", eciCode: "S22" });
  });

  test("returns callback when a custom callback IS supplied", () => {
    // The NationalElection case. The component will invoke the prop
    // with the ECI code (NOT the boundary join key).
    const action = resolveStateClickAction("27", KEY_TO_ECI, true);
    expect(action).toEqual({ kind: "callback", eciCode: "S13" });
  });

  test("returns noop when the boundary key has no ECI mapping", () => {
    // Happens during the initial paint (taxonomy not loaded yet) or
    // for a state that fell out of the taxonomy. The component must
    // not crash; the click is silently dropped.
    const action = resolveStateClickAction("999", KEY_TO_ECI, false);
    expect(action).toEqual({ kind: "noop" });
    const action2 = resolveStateClickAction("999", KEY_TO_ECI, true);
    expect(action2).toEqual({ kind: "noop" });
  });

  test("custom callback takes precedence over the default navigate", () => {
    // The exhaustive table the component switches against. The
    // "has callback" and "missing eci" branches are independent;
    // when the eci IS present, the callback wins regardless.
    const lakWithCallback = resolveStateClickAction("31", KEY_TO_ECI, true);
    expect(lakWithCallback.kind).toBe("callback");
    if (lakWithCallback.kind === "callback") {
      expect(lakWithCallback.eciCode).toBe("U09");
    }
    const lakWithoutCallback = resolveStateClickAction("31", KEY_TO_ECI, false);
    expect(lakWithoutCallback.kind).toBe("navigate-default");
    if (lakWithoutCallback.kind === "navigate-default") {
      expect(lakWithoutCallback.eciCode).toBe("U09");
    }
  });

  test("returns noop on an empty lookup table (no taxonomy loaded)", () => {
    expect(resolveStateClickAction("33", {}, false)).toEqual({ kind: "noop" });
    expect(resolveStateClickAction("33", {}, true)).toEqual({ kind: "noop" });
  });
});

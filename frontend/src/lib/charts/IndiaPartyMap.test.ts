// PR-4 of TODO/20260611-elections-off-maplibre-and-map-ux-plan.md
// (IndiaMap d3-geo replacement). The sub-threshold circle-marker
// overlay was retired in the map-geometry render sweep (Row 1 of
// TODO/20260616-map-geometry-rip-and-palette-plan.md) and replaced by
// a single name-scoped SQUARE marker for Lakshadweep (the one far-flung
// island that collapses to sub-pixel at the national fit). Both the
// click-action resolver and the island-marker locator are covered here
// in node-env (repo vitest doctrine: no jsdom canvas, no
// @testing-library/svelte mounts).

import { describe, expect, test } from "vitest";
import { geoMercator, geoPath } from "d3-geo";
import type {
  Feature,
  FeatureCollection,
  GeoJsonProperties,
  Geometry,
  MultiPolygon,
  Polygon,
} from "geojson";

import {
  resolveStateClickAction,
  computeIslandMarker,
  hasNoDataFeature,
} from "./india-party-map-helpers";

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

describe("IndiaPartyMap helpers - computeIslandMarker (Lakshadweep)", () => {
  // Synthetic two-feature collection: a big mainland polygon and a tiny
  // far-flung island. Projected with the same geoMercator().fitWidth the
  // national maps use so the test exercises the real projection maths.
  function sqFeature(
    name: string,
    key: string,
    lng0: number,
    lat0: number,
    lng1: number,
    lat1: number,
  ): Feature<Polygon> {
    return {
      type: "Feature",
      properties: { STNAME: name, key },
      geometry: {
        type: "Polygon",
        // Clockwise exterior ring - d3-geo's spherical convention treats
        // the interior as the SMALL side wound this way (a CCW ring is
        // read as the globe-minus-square complement).
        coordinates: [
          [
            [lng0, lat0],
            [lng0, lat1],
            [lng1, lat1],
            [lng1, lat0],
            [lng0, lat0],
          ],
        ],
      },
    };
  }

  const mainland = sqFeature("MAINLAND", "01", 70, 8, 90, 35);
  // Lakshadweep: a ~0.1-degree island in the Arabian Sea.
  const island = sqFeature("Lakshadweep", "U04", 72.6, 10.5, 72.7, 10.6);
  const collection: FeatureCollection<Polygon> = {
    type: "FeatureCollection",
    features: [mainland, island],
  };

  function projectionAndPath() {
    const projection = geoMercator().fitWidth(800, collection);
    const pre = geoPath(projection).bounds(collection);
    const [tx, ty] = projection.translate();
    projection.translate([tx - pre[0][0], ty - pre[0][1]]);
    return { projection, path: geoPath(projection) };
  }

  const keyOf = (f: Feature<Geometry, GeoJsonProperties>) =>
    f.properties?.key as string;
  const nameOf = (f: Feature<Geometry, GeoJsonProperties>) =>
    String(f.properties?.STNAME ?? "");

  test("returns a marker for the sub-threshold named island", () => {
    const { projection, path } = projectionAndPath();
    const marker = computeIslandMarker(
      collection.features,
      projection,
      path,
      keyOf,
      nameOf,
      /laksh/i,
    );
    expect(marker).not.toBeNull();
    expect(marker?.key).toBe("U04");
    expect(Number.isFinite(marker?.cx)).toBe(true);
    expect(Number.isFinite(marker?.cy)).toBe(true);
  });

  test("never marks the large mainland feature", () => {
    const { projection, path } = projectionAndPath();
    // A name pattern that ONLY matches the big mainland feature: it is
    // above threshold, so no marker is produced (it is clickable as-is).
    const marker = computeIslandMarker(
      collection.features,
      projection,
      path,
      keyOf,
      nameOf,
      /mainland/i,
    );
    expect(marker).toBeNull();
  });

  test("returns null when the name pattern matches nothing", () => {
    const { projection, path } = projectionAndPath();
    const marker = computeIslandMarker(
      collection.features,
      projection,
      path,
      keyOf,
      nameOf,
      /antarctica/i,
    );
    expect(marker).toBeNull();
  });

  test("suppresses the marker when the island fills the viewport", () => {
    const { projection, path } = projectionAndPath();
    // A tiny threshold simulates the island's own state page, where the
    // projection is fit to just the island so its span is large: no
    // marker (the polygon itself is directly clickable).
    const marker = computeIslandMarker(
      collection.features,
      projection,
      path,
      keyOf,
      nameOf,
      /laksh/i,
      0.0001,
    );
    expect(marker).toBeNull();
  });

  test("marks a scattered archipelago whose bbox is large but islands are sub-pixel", () => {
    // Regression for the Lakshadweep marker. Row 2 (combined country
    // topojson, PR #1089) made Lakshadweep a MultiPolygon of 4 islands
    // spread across ~2.5 degrees of sea; its whole-feature bbox is ~82 px
    // at national fit, so the prior whole-bbox span metric read it as "big
    // enough to click directly" and suppressed the marker even though the
    // largest island is ~1 px. computeIslandMarker now measures the largest
    // INDIVIDUAL island, so the marker renders.
    const sq = (lng0: number, lat0: number, lng1: number, lat1: number) => [
      [
        [lng0, lat0],
        [lng0, lat1],
        [lng1, lat1],
        [lng1, lat0],
        [lng0, lat0],
      ],
    ];
    const archipelago: Feature<MultiPolygon> = {
      type: "Feature",
      properties: { STNAME: "Lakshadweep", key: "U04" },
      geometry: {
        type: "MultiPolygon",
        // Two 0.05-degree islands ~2 degrees apart in latitude: a large
        // sea-dominated bbox, sub-pixel individual islands.
        coordinates: [
          sq(72.6, 10.5, 72.65, 10.55),
          sq(72.7, 12.5, 72.75, 12.55),
        ],
      },
    };
    const coll: FeatureCollection<Geometry> = {
      type: "FeatureCollection",
      features: [mainland, archipelago],
    };
    const projection = geoMercator().fitWidth(800, coll);
    const pre = geoPath(projection).bounds(coll);
    const [tx, ty] = projection.translate();
    projection.translate([tx - pre[0][0], ty - pre[0][1]]);
    const path = geoPath(projection);
    const marker = computeIslandMarker(
      coll.features,
      projection,
      path,
      (f) => f.properties?.key as string,
      (f) => String(f.properties?.STNAME ?? ""),
      /laksh/i,
    );
    expect(marker).not.toBeNull();
    expect(marker?.key).toBe("U04");
    expect(Number.isFinite(marker?.cx)).toBe(true);
    expect(Number.isFinite(marker?.cy)).toBe(true);
  });
});

describe("IndiaPartyMap helpers - hasNoDataFeature (no-data dot-grid chip)", () => {
  // The national party map paints states with a loaded winner in the
  // leading-party colour; states absent from the `fills` map fall through
  // to the no-data dot-grid. This predicate drives the "No data" chip.
  function feat(key: string | null): Feature<Geometry, GeoJsonProperties> {
    return {
      type: "Feature",
      properties: key == null ? {} : { State_LGD: key },
      geometry: { type: "Polygon", coordinates: [] },
    };
  }
  const keyOf = (f: Feature<Geometry, GeoJsonProperties>) =>
    f.properties?.State_LGD as string | undefined;

  test("false when every rendered feature has a fill entry", () => {
    const features = [feat("33"), feat("27")];
    const fills = { "33": "#abc", "27": "#def" };
    expect(hasNoDataFeature(features, fills, keyOf)).toBe(false);
  });

  test("true when at least one feature is absent from the fills map", () => {
    // J&K ("01") has no loaded winner -> no fill entry -> dot-grid.
    const features = [feat("33"), feat("01")];
    const fills = { "33": "#abc" };
    expect(hasNoDataFeature(features, fills, keyOf)).toBe(true);
  });

  test("true when a feature has a null/absent join key", () => {
    // A geometry missing its State_LGD property cannot match any fill.
    const features = [feat("33"), feat(null)];
    const fills = { "33": "#abc" };
    expect(hasNoDataFeature(features, fills, keyOf)).toBe(true);
  });

  test("true on an empty fills map (loader not settled / no winners)", () => {
    const features = [feat("33"), feat("27")];
    expect(hasNoDataFeature(features, {}, keyOf)).toBe(true);
  });

  test("false on an empty feature list", () => {
    expect(hasNoDataFeature([], {}, keyOf)).toBe(false);
  });
});

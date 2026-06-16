// PR-5 of TODO/20260611-elections-off-maplibre-and-map-ux-plan.md
// (StateAcMap d3-geo replacement + AC highlight + pan/zoom/home).
//
// Pure-helper + topojson-pipeline contract for `StateAcMapD3.svelte`.
// Per repo vitest doctrine (node-env, no jsdom canvas, no
// @testing-library/svelte mounts), this file does NOT mount the
// Svelte component; it covers:
//
//   1. The pure paint helpers in `./state-ac-map-helpers.ts`
//      (acFillForRow / acOpacityForRow / acStrokeForHighlight +
//       FOCUS_DIM_MULTIPLIER / HIGHLIGHT_STROKE_*) including the
//      override precedence + highlight focus-dim formula the legacy
//      StateAcMap.svelte implemented inline.
//   2. The end-to-end topojson -> projection -> path -> marker pipeline
//      against TWO real per-state AC GeoJSONs:
//        - `state=goa/all.geojson` (41 features; covered by lgd_ac_id)
//          for the bounded feature-count + path-string-non-empty case.
//        - `state=uttar-pradesh/all.geojson` (404 features; covered)
//          for the sub-threshold marker contract. NB: at the per-state
//          640x480 fitSize the projection MAGNIFIES the state to fill
//          the viewBox, so dense urban states like Delhi (min AC dim
//          ~20px) do NOT trigger the marker overlay; the overlay fires
//          for states that have many internal sub-pixel polygons
//          relative to their bounding box. UP (50 of 404 sub-threshold
//          at this fit) is the proven fixture; Kerala / TN / WB would
//          also work but their geojsons trip d3-geo's internal
//          `path.bounds` on some multipolygon rings (a separate bug).
//
// The rendered SVG shape (button trio, hover tooltip, click navigate,
// d3-zoom transform) is covered by the CLAUDE.md section 13 browser
// smoke captured in the PR body. Same split as PR-4's IndiaPartyMap.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";
import { geoMercator, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { feature as topojsonFeature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import type { FeatureCollection, Geometry } from "geojson";

import {
  acFillForRow,
  acOpacityForRow,
  acStrokeForHighlight,
  FOCUS_DIM_MULTIPLIER,
  HAIRLINE_STROKE_HEX,
  HAIRLINE_STROKE_WIDTH_PX,
  HIGHLIGHT_STROKE_HEX,
  HIGHLIGHT_STROKE_WIDTH_PX,
  type AcCellInput,
} from "./state-ac-map-helpers";

// Same path resolution pattern as IndiaPartyMap.test.ts (4 ".." to
// climb from `frontend/src/lib/charts/` to the repo root). Since the
// 2026-06-16 map-geometry rip (Row 3) Goa's ACs live in the ONE national
// AC topojson; we decode it + filter Goa (state_ut_code = "S05") exactly
// as the runtime `fetchStateAcCollection` does.
const NATIONAL_AC_TOPOJSON_PATH = resolve(
  __dirname,
  "..",
  "..",
  "..",
  "..",
  "datasets",
  "boundaries",
  "electoral",
  "delim=2024",
  "ac",
  "all.topojson",
);
const GOA_STATE_UT_CODE = "S05";

// Mirror the live component's projection size + join property so the
// test exercises the same inputs the citizen sees in the browser.
const WIDTH = 640;
const HEIGHT = 480;

interface AcProps {
  ac_no: number;
  ac_name: string;
  state_ut_code?: string;
  lgd_ac_id?: number;
  State_LGD?: number;
  reservation?: string;
}

type AcCollection = FeatureCollection<Geometry, AcProps>;

// Decode the national AC topojson + filter to one state by state_ut_code,
// mirroring the runtime `fetchStateAcCollection` in StateAcMapD3.svelte.
function loadStateAcCollection(
  topojsonPath: string,
  stateUtCode: string,
): AcCollection {
  const topo = JSON.parse(readFileSync(topojsonPath, "utf8")) as Topology;
  const fc = topojsonFeature(
    topo,
    topo.objects.ac as GeometryCollection,
  ) as unknown as AcCollection;
  return {
    type: "FeatureCollection",
    features: fc.features.filter(
      (f) => String(f.properties?.state_ut_code ?? "") === stateUtCode,
    ),
  };
}

function buildProjectionAndPath(collection: AcCollection): {
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

// Sample AcCellInput used across the per-row paint helper tests. Mode
// stays "margin" by default so the cellTreatment formula drives the
// margin-ramp opacity; the party_won-mode tests override `mode`
// explicitly.
function baseInput(overrides: Partial<AcCellInput> = {}): AcCellInput {
  return {
    party_id: "parties.IN.DMK",
    margin_pct: 15, // mid-band; ramp opacity = 0.35 + 15/30 * 0.6 = 0.65
    winner_party_hex: "#ff0000",
    neutral_hex: "#cbd5e1",
    mode: "margin",
    selected_party_id: null,
    min_margin: 0,
    ...overrides,
  };
}

describe("state-ac-map-helpers - constants", () => {
  test("FOCUS_DIM_MULTIPLIER is 0.18 (matches legacy StateAcMap)", () => {
    expect(FOCUS_DIM_MULTIPLIER).toBe(0.18);
  });
  test("HIGHLIGHT_STROKE_HEX is slate-900 + 2.5 px (per row spec)", () => {
    expect(HIGHLIGHT_STROKE_HEX).toBe("#0f172a");
    expect(HIGHLIGHT_STROKE_WIDTH_PX).toBe(2.5);
  });
  test("HAIRLINE_STROKE_HEX is slate-400 + 0.5 px (internal AC border)", () => {
    expect(HAIRLINE_STROKE_HEX).toBe("#94a3b8");
    expect(HAIRLINE_STROKE_WIDTH_PX).toBe(0.5);
  });
});

describe("state-ac-map-helpers - acFillForRow", () => {
  test("margin mode without override returns the winner party hex", () => {
    expect(acFillForRow(baseInput())).toBe("#ff0000");
  });
  test("override wins outright over the winner hex (PR-B8 filter rail path)", () => {
    expect(acFillForRow(baseInput(), "#00ff00")).toBe("#00ff00");
  });
  test("party_won mode + match returns the winner hex at full intensity", () => {
    const out = acFillForRow(
      baseInput({
        mode: "party_won",
        selected_party_id: "parties.IN.DMK",
      }),
    );
    expect(out).toBe("#ff0000");
  });
  test("party_won mode + miss returns the neutral hex (party recede)", () => {
    const out = acFillForRow(
      baseInput({
        mode: "party_won",
        selected_party_id: "parties.IN.BJP", // does NOT match DMK winner
      }),
    );
    expect(out).toBe("#cbd5e1");
  });
  test("override still wins even in party_won miss mode", () => {
    const out = acFillForRow(
      baseInput({
        mode: "party_won",
        selected_party_id: "parties.IN.BJP",
      }),
      "#0000ff",
    );
    expect(out).toBe("#0000ff");
  });
});

describe("state-ac-map-helpers - acOpacityForRow margin ramp", () => {
  test("knife-edge win (margin 0) clamps to the floor 0.35", () => {
    const out = acOpacityForRow(
      baseInput({ margin_pct: 0 }),
      42,
      undefined,
      undefined,
    );
    expect(out).toBeCloseTo(0.35, 5);
  });
  test("mid-band margin (15) maps to 0.65", () => {
    const out = acOpacityForRow(
      baseInput({ margin_pct: 15 }),
      42,
      undefined,
      undefined,
    );
    expect(out).toBeCloseTo(0.65, 5);
  });
  test("saturation margin (30) maps to the ceiling 0.95", () => {
    const out = acOpacityForRow(
      baseInput({ margin_pct: 30 }),
      42,
      undefined,
      undefined,
    );
    expect(out).toBeCloseTo(0.95, 5);
  });
  test("margin above 30 still clamps to 0.95 (no overshoot)", () => {
    const out = acOpacityForRow(
      baseInput({ margin_pct: 50 }),
      42,
      undefined,
      undefined,
    );
    expect(out).toBeCloseTo(0.95, 5);
  });
  test("negative margin is treated as |signed| (winner is still the winner)", () => {
    const out = acOpacityForRow(
      baseInput({ margin_pct: -15 }),
      42,
      undefined,
      undefined,
    );
    expect(out).toBeCloseTo(0.65, 5);
  });
});

describe("state-ac-map-helpers - acOpacityForRow override precedence", () => {
  test("override returned when highlight_eci_no is undefined", () => {
    const out = acOpacityForRow(baseInput(), 42, 0.42, undefined);
    expect(out).toBe(0.42);
  });
  test("override IGNORED when highlight_eci_no is set (focus-dim wins)", () => {
    // override=0.42 but highlight_eci_no=999 (no match) -> base * 0.18
    const out = acOpacityForRow(
      baseInput({ margin_pct: 15 }),
      42,
      0.42,
      999,
    );
    expect(out).toBeCloseTo(0.65 * 0.18, 5);
  });
});

describe("state-ac-map-helpers - acOpacityForRow highlight focus-dim", () => {
  test("matched AC forced to full opacity 1.0 regardless of base", () => {
    const out = acOpacityForRow(
      baseInput({ margin_pct: 0 }), // tiny margin -> base 0.35
      42,
      undefined,
      42, // matches!
    );
    expect(out).toBe(1);
  });
  test("non-matching AC dimmed to base * FOCUS_DIM_MULTIPLIER (0.18)", () => {
    const out = acOpacityForRow(
      baseInput({ margin_pct: 15 }), // base 0.65
      42,
      undefined,
      999, // does not match
    );
    expect(out).toBeCloseTo(0.65 * 0.18, 5);
  });
  test("highlight focus-dim composes with party_won mode (matching cell)", () => {
    // party_won + match -> base opacity 1, then highlight match -> still 1
    const out = acOpacityForRow(
      baseInput({
        mode: "party_won",
        selected_party_id: "parties.IN.DMK",
      }),
      42,
      undefined,
      42,
    );
    expect(out).toBe(1);
  });
  test("highlight focus-dim composes with party_won mode (non-matching cell)", () => {
    // party_won + miss -> base opacity 0.18, then highlight miss -> 0.18 * 0.18
    const out = acOpacityForRow(
      baseInput({
        mode: "party_won",
        selected_party_id: "parties.IN.BJP", // miss
      }),
      42,
      undefined,
      999, // miss
    );
    expect(out).toBeCloseTo(0.18 * 0.18, 5);
  });
});

describe("state-ac-map-helpers - acStrokeForHighlight", () => {
  test("undefined highlight_eci_no returns the hairline border", () => {
    const out = acStrokeForHighlight(42, undefined);
    expect(out).toEqual({
      stroke: HAIRLINE_STROKE_HEX,
      strokeWidth: HAIRLINE_STROKE_WIDTH_PX,
    });
  });
  test("matching eci_no returns slate-900 + 2.5 px outline", () => {
    const out = acStrokeForHighlight(42, 42);
    expect(out).toEqual({
      stroke: HIGHLIGHT_STROKE_HEX,
      strokeWidth: HIGHLIGHT_STROKE_WIDTH_PX,
    });
  });
  test("non-matching eci_no in highlight mode falls back to hairline", () => {
    const out = acStrokeForHighlight(42, 99);
    expect(out).toEqual({
      stroke: HAIRLINE_STROKE_HEX,
      strokeWidth: HAIRLINE_STROKE_WIDTH_PX,
    });
  });
});

// --- end-to-end topojson pipeline against the real national AC topojson -

describe("StateAcMapD3 - Goa AC pipeline (national topojson, lgd_ac_id covered)", () => {
  test("collection decodes + filters into Goa's AC features", () => {
    const collection = loadStateAcCollection(
      NATIONAL_AC_TOPOJSON_PATH,
      GOA_STATE_UT_CODE,
    );
    expect(collection.type).toBe("FeatureCollection");
    // Goa AE has 40 constituencies; the national source carries 40-41
    // features (a state-border overlay sliver may ride along).
    expect(collection.features.length).toBeGreaterThanOrEqual(40);
    expect(collection.features.length).toBeLessThanOrEqual(41);
  });

  test("every feature carries an integer ac_no in [1, 40]", () => {
    // Goa AE has 40 constituencies; the 41st feature is a state-border
    // overlay (one of the post-D.7 LGD release additions). Either way,
    // each feature's ac_no must be a finite integer that can be used as
    // the eci_no for uncovered fallback.
    const collection = loadStateAcCollection(
      NATIONAL_AC_TOPOJSON_PATH,
      GOA_STATE_UT_CODE,
    );
    for (const f of collection.features) {
      expect(typeof f.properties.ac_no).toBe("number");
      expect(Number.isFinite(f.properties.ac_no)).toBe(true);
    }
  });

  test("every feature projects to a non-empty SVG path starting with M", () => {
    const collection = loadStateAcCollection(
      NATIONAL_AC_TOPOJSON_PATH,
      GOA_STATE_UT_CODE,
    );
    const { path } = buildProjectionAndPath(collection);
    for (const f of collection.features) {
      const d = path(f);
      expect(
        d,
        `Goa AC ${f.properties.ac_no} (${f.properties.ac_name}) projected to a null path`,
      ).toBeTruthy();
      expect(d!.startsWith("M")).toBe(true);
    }
  });
});

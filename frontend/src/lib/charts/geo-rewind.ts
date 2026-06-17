// d3-geo winding-order normaliser for plain-GeoJSON map layers.
//
// WHY THIS EXISTS
// ---------------
// d3-geo treats polygons as spherical and uses the convention that a
// polygon's EXTERIOR ring is wound CLOCKWISE and its holes COUNTER-
// CLOCKWISE. The GeoJSON spec (RFC 7946, the "right-hand rule") uses the
// OPPOSITE convention - exterior rings counter-clockwise. When a feature
// wound per RFC 7946 is handed to `geoPath`, d3 reads the exterior ring as
// the *small* interior of the complementary spherical polygon, so the
// projected path covers (almost) the entire sphere - i.e. every polygon
// paints the whole viewBox and the map renders as one solid block.
//
// `topojson-client`'s `feature()` already emits d3-friendly (clockwise-
// exterior) winding, which is why the layers still decoded from topojson
// (IndiaPartyMap states, GeoChoropleth) render correctly. The 2026-06-16
// map-geometry rip converted the electoral PC/AC layers to PLAIN GeoJSON
// FeatureCollections (RFC 7946 winding, exterior CCW), removing that
// implicit rewind. The d3 components that fetch those geojson files
// directly (IndiaPcMapD3, StatePcMapD3, StateAcMapD3 geojson branch) must
// re-impose the clockwise-exterior convention themselves - that is what
// this module does.
//
// The transform is IDEMPOTENT: a ring already wound the way d3 wants is
// returned untouched, so applying it to an already-correct (topojson-
// decoded) collection is a harmless no-op. Only Polygon / MultiPolygon
// geometries are rewound; every other geometry type passes through.

import type {
  Feature,
  FeatureCollection,
  GeoJsonProperties,
  Geometry,
  Position,
} from "geojson";

/**
 * Signed area of a linear ring via the shoelace formula in lon/lat space
 * (x = longitude, y = latitude increasing northward). POSITIVE => the ring
 * is wound CLOCKWISE; NEGATIVE => COUNTER-CLOCKWISE. Degenerate rings
 * (< 4 positions) return 0 and are treated as "no rewind needed".
 */
export function ringSignedArea(ring: Position[]): number {
  if (ring.length < 4) return 0;
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const a = ring[i];
    const b = ring[i + 1];
    sum += (b[0] - a[0]) * (b[1] + a[1]);
  }
  return sum / 2;
}

/** Rewind one polygon's rings to d3's convention: ring 0 (exterior)
 *  clockwise, every subsequent ring (hole) counter-clockwise. Rings
 *  already wound correctly are returned by reference (no copy). */
function rewindPolygonRings(rings: Position[][]): Position[][] {
  return rings.map((ring, idx) => {
    const wantClockwise = idx === 0;
    const isClockwise = ringSignedArea(ring) > 0;
    if (isClockwise === wantClockwise) return ring;
    return ring.slice().reverse();
  });
}

/** Return a copy of `feature` whose Polygon / MultiPolygon rings follow
 *  d3-geo's clockwise-exterior winding convention. Non-areal geometries
 *  pass through unchanged. */
export function rewindFeatureForD3<P extends GeoJsonProperties = GeoJsonProperties>(
  feature: Feature<Geometry, P>,
): Feature<Geometry, P> {
  const g = feature.geometry;
  if (!g) return feature;
  if (g.type === "Polygon") {
    return {
      ...feature,
      geometry: { ...g, coordinates: rewindPolygonRings(g.coordinates) },
    };
  }
  if (g.type === "MultiPolygon") {
    return {
      ...feature,
      geometry: { ...g, coordinates: g.coordinates.map(rewindPolygonRings) },
    };
  }
  return feature;
}

/** Return a copy of `collection` with every feature rewound to d3-geo's
 *  clockwise-exterior convention. Idempotent; safe to call on collections
 *  that are already correctly wound (e.g. topojson-decoded). */
export function rewindCollectionForD3<
  P extends GeoJsonProperties = GeoJsonProperties,
>(
  collection: FeatureCollection<Geometry, P>,
): FeatureCollection<Geometry, P> {
  return {
    ...collection,
    features: collection.features.map((f) => rewindFeatureForD3(f)),
  };
}

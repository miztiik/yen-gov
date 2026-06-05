// F2b.3 pure helper module for GeoChoropleth. Lives separately from
// the .svelte file so vitest (node-env, no DOM) can cover the join +
// domain math directly. The .svelte file consumes these via
// `<script module>` re-export.
//
// Doctrine ties:
//   - Pure functions only. No DOM, no fetches, no Svelte runes.
//   - Row shape `(entity_key, time, value)` per parent plan
//     section 22.4 invariant #1 ("renderers consume (entity, time,
//     value) only").
//   - Tested by `geo-choropleth-helpers.test.ts` (sibling file).

/**
 * The minimal row shape GeoChoropleth consumes. `entity_key` is the
 * value carried on `feature.properties[feature_key]` for the join
 * (typically `st_lgd` or `dist_lgd` as a string or number; the
 * helpers stringify both sides to dodge the int-vs-string trap).
 */
export interface GeoChoroplethRow {
  /** Entity key joining to `feature.properties[feature_key]`. */
  entity_key: string | number;
  /** Time slice (year, fiscal-year label, date string). Optional;
   *  callers that have only one slice omit this field. */
  time?: string | number | null;
  /** The observation value. Null = no data (renders as hatch). */
  value: number | null;
}

/**
 * Group rows by their stringified `entity_key`, taking the LAST
 * value per key when duplicates are present (callers should
 * pre-filter to a single time slice; the renderer does this via the
 * `selected_time` prop). Returns a Map<key_string, value | null>.
 *
 * Stringification dodges the boundary-key-int-vs-string trap: the
 * topojson sometimes carries `dist_lgd: 553` (int) and the row
 * sometimes carries `entity_key: "553"` (string). Both compare equal
 * after `String()`.
 */
export function rowsByFeatureKey(
  rows: readonly GeoChoroplethRow[],
): Map<string, number | null> {
  const out = new Map<string, number | null>();
  for (const r of rows) {
    out.set(String(r.entity_key), r.value);
  }
  return out;
}

/**
 * Derive `{min, max}` from the value column of a row set. Skips null
 * values. Returns `{min: 0, max: 1}` for an all-null / empty input
 * (the renderer falls through to the hatch for every feature in that
 * case, but the domain is still well-formed so the legend renders).
 *
 * Domain derivation here mirrors what the existing IndicatorChoropleth
 * does (lib/IndicatorChoropleth.svelte ~line 168) so the two engines
 * agree on the same numeric domain when fed the same rows.
 */
export function deriveDomain(
  rows: readonly GeoChoroplethRow[],
): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const r of rows) {
    if (r.value == null || !Number.isFinite(r.value)) continue;
    if (r.value < min) min = r.value;
    if (r.value > max) max = r.value;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: 0, max: 1 };
  }
  // Defensive: collapsed-domain (single distinct value) is reported
  // as min == max so the color-scale degenerate-domain branch handles
  // it (citizen-honest: every cell reads as "this one value").
  return { min, max };
}

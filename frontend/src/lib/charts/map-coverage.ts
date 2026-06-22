// Coverage of an election result-set against the geometry it is drawn on.
//
// Old elections are rendered on the CURRENT (latest-delimitation) boundary
// set via a name-slug / eci join; constituencies that do not bind a result
// render grey. This module is the single, pure source of truth for the
// honesty caption that surfaces that shortfall - "{matched} of {total}
// {unit} matched ... coverage drops with each delimitation".
//
// Per the repo vitest doctrine (node-env, no jsdom, no component mounts),
// ALL the logic lives here as pure functions so it is unit-tested without
// mounting `MapCoverageNote.svelte`; the component is a thin renderer of
// `coverageNoteText()`.
//
// Doctrine: TODO/20260622-undivided-state-election-history-proposal.md
// (rev 2, on main via PR #1189 + #1194). The caption is render-time and
// emergent (never stored); `{geometry_year}` is read from the on-disk
// boundary path's `delim=YYYY` marker (the snapshot edition the citizen
// is looking at), never hardcoded (Holy Law #6).

export interface MapCoverage {
  /** Rendered map units that bound a result for the chosen event. */
  matched: number;
  /** Rendered map units in view (the denominator the citizen can count). */
  total: number;
}

/** The countable noun in the caption. PC + AC both render "constituencies";
 *  admin choropleths render "districts". */
export type MapUnit = "constituencies" | "districts";

// Rendered separators (middot + em-dash) kept as escapes so this source
// file stays ASCII-only per CLAUDE.md while the UI shows the glyphs from
// the ratified mockup.
const MIDDOT = "\u00b7";
const EMDASH = "\u2014";

/**
 * Count how many rendered features bind a result.
 *
 * @param featureKeys the join key of every feature ON SCREEN (one entry
 *   per rendered map unit; `null`/`undefined` for an unkeyed feature).
 * @param resultHasKey predicate that is true when a key has a result row.
 * @returns `{ matched, total }` where `total === featureKeys.length`.
 */
export function computeCoverage(
  featureKeys: ReadonlyArray<string | number | null | undefined>,
  resultHasKey: (key: string | number) => boolean,
): MapCoverage {
  let matched = 0;
  for (const k of featureKeys) {
    if (k != null && resultHasKey(k)) matched += 1;
  }
  return { matched, total: featureKeys.length };
}

/**
 * Extract the delimitation / snapshot vintage year from a boundary path
 * like `boundaries/electoral/delim=2024/pc/all.geojson` -> `"2024"`.
 * Returns `null` when the path carries no `delim=` marker (admin / district
 * layers are notified, not delimited, so they have no vintage token).
 */
export function delimVintageFromPath(
  path: string | null | undefined,
): string | null {
  if (!path) return null;
  const m = /delim=(\d{4})/.exec(path);
  return m ? m[1] : null;
}

/**
 * True only when there is a real shortfall to surface: something rendered
 * (`total > 0`) and at least one unit did not bind (`matched < total`).
 * This is the auto-hide rule - a full-coverage current-vintage map returns
 * `false` so the caption never appears on the normal case.
 */
export function hasCoverageGap(c: MapCoverage | null | undefined): boolean {
  return !!c && c.total > 0 && c.matched < c.total;
}

/**
 * The citizen caption string, or `null` when there is nothing to say.
 * Auto-hide is encoded here so every caller - and every map type - hides
 * identically. Two gates, both must pass:
 *   1. `onOldGeometry` - the event must PREDATE the geometry on screen (an
 *      old election drawn on the current boundary set). A current-vintage
 *      map never captions, even if a few structural placeholder features
 *      (e.g. the 2 J&K non-seat polygons) fail to bind - that is not a
 *      delimitation coverage drop.
 *   2. `hasCoverageGap` - at least one rendered unit did not bind.
 *
 * Shape (ratified wording, parameterized by `unit`):
 *   "{matched} of {total} {unit} matched [middot] older years use
 *    {geometryYear} boundaries [em-dash] coverage drops with each
 *    delimitation"
 *
 * The middle "older years use {geometryYear} boundaries" clause is omitted
 * when the vintage is unknown (e.g. a layer with no `delim=` marker).
 */
export function coverageNoteText(
  coverage: MapCoverage | null | undefined,
  unit: MapUnit = "constituencies",
  geometryYear: string | null = null,
  onOldGeometry: boolean = false,
): string | null {
  if (!onOldGeometry) return null;
  if (!hasCoverageGap(coverage)) return null;
  const c = coverage as MapCoverage;
  const head = `${c.matched} of ${c.total} ${unit} matched`;
  const mid = geometryYear
    ? ` ${MIDDOT} older years use ${geometryYear} boundaries`
    : "";
  return `${head}${mid} ${EMDASH} coverage drops with each delimitation`;
}

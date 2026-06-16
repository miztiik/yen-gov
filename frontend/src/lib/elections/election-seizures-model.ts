// Pure projection model for the MCC-period election-seizures card
// (Row D of TODO/20260614-three-ephemeral-ingests-plan.md).
//
// Consumes `datasets/elections/parliament/election=<year>/mcc_seizures.csv`
// (one row per (state_slug, date); 36 states/UTs × 10 dates for the
// 2019 vintage). Produces:
//
//   * `projectChoropleth(rows, cat, unit, slugToLgd, state_slug?)`
//     -> `GeoChoroplethRow[]` keyed on the LGD numeric code carried
//        by the ramSeraph LGD_States all.topojson features.
//   * `projectSparkline(rows, cat, unit, state_slug?)`
//     -> `SparklinePoint[]` (one per date in the publisher window).
//   * `categoryColumn(cat, unit)` / `categoryLabel(cat)` /
//     `categoryUnitLabel(cat, unit)` for picker + axis chrome.
//
// All functions are pure (no DuckDB-WASM, no fetch); covered by
// vitest in `election-seizures-model.test.ts`. The Svelte card
// wires these to the loader + GeoChoropleth primitive.
//
// Citizen-honesty rules baked in:
//   * Publisher's `total_seizure_inr_crore` is used verbatim per D3
//     of the parent plan (no re-derivation of totals at consume time).
//   * Empty publisher cells are NULL, not 0 (publisher silence is
//     "no action reported", not "zero seizure"). Null rows are
//     omitted from choropleth + sparkline; the no-data UI is the
//     C4 hatch fill on the map.
//   * Quantity units (lakh litres / kg) are only valid for
//     liquor / drugs / precious-metals; `categoryHasQuantity(cat)`
//     gates the unit toggle in the picker.

/** The six citizen-facing facets the seizures card exposes. */
export type SeizuresCategory =
  | "total"
  | "cash"
  | "liquor"
  | "drugs"
  | "metals"
  | "other";

/** Either value-in-INR-crore (always available) or physical quantity
 *  (lakh litres / kg; only valid for liquor / drugs / metals). */
export type SeizuresUnit = "value" | "quantity";

/** One row from the source CSV; matches the columns.json shape
 *  one-for-one. All quantity / value columns are nullable per the
 *  publisher's blank-as-no-action-reported convention. */
export interface SeizuresRow {
  readonly state_slug: string;
  readonly date: string; // ISO YYYY-MM-DD
  readonly cash_inr_crore: number | null;
  readonly liquor_qty_lakh_litres: number | null;
  readonly liquor_value_inr_crore: number | null;
  readonly drugs_qty_kg: number | null;
  readonly drugs_value_inr_crore: number | null;
  readonly precious_metals_qty_kg: number | null;
  readonly precious_metals_value_inr_crore: number | null;
  readonly other_items_seizure_value_inr_crore: number | null;
  readonly total_seizure_inr_crore: number | null;
  readonly source_id: string;
  readonly processing_level: string;
}

/** True when this category has a meaningful physical-quantity facet
 *  in addition to its INR-crore value. Drives the unit-toggle
 *  visibility in the picker chrome. */
export function categoryHasQuantity(cat: SeizuresCategory): boolean {
  return cat === "liquor" || cat === "drugs" || cat === "metals";
}

/** Resolve a (category, unit) pair to the source CSV column name.
 *  Returns null when the requested combination is invalid (e.g. a
 *  quantity unit on a value-only category like "cash" or "total");
 *  callers MUST treat null as "fall back to the value column"
 *  rather than crash. */
export function categoryColumn(
  cat: SeizuresCategory,
  unit: SeizuresUnit,
): keyof SeizuresRow | null {
  if (unit === "quantity") {
    if (cat === "liquor") return "liquor_qty_lakh_litres";
    if (cat === "drugs") return "drugs_qty_kg";
    if (cat === "metals") return "precious_metals_qty_kg";
    return null; // quantity not defined for cash / total / other
  }
  // unit === "value"
  switch (cat) {
    case "total":
      return "total_seizure_inr_crore";
    case "cash":
      return "cash_inr_crore";
    case "liquor":
      return "liquor_value_inr_crore";
    case "drugs":
      return "drugs_value_inr_crore";
    case "metals":
      return "precious_metals_value_inr_crore";
    case "other":
      return "other_items_seizure_value_inr_crore";
  }
}

/** Citizen-readable label for the category picker.
 *  "Other" surfaces as "Freebies" per the parent plan's
 *  citizen-honesty framing (the press-note's "other items" is
 *  largely freebie-distribution seizures). */
export function categoryLabel(cat: SeizuresCategory): string {
  switch (cat) {
    case "total":
      return "Total ₹";
    case "cash":
      return "Cash";
    case "liquor":
      return "Liquor";
    case "drugs":
      return "Drugs";
    case "metals":
      return "Precious metals";
    case "other":
      return "Freebies";
  }
}

/** Citizen-readable unit suffix for the legend + tooltip. */
export function categoryUnitLabel(
  cat: SeizuresCategory,
  unit: SeizuresUnit,
): string {
  if (unit === "value") return "INR crore";
  if (cat === "liquor") return "lakh litres";
  if (cat === "drugs") return "kg";
  if (cat === "metals") return "kg";
  return "INR crore"; // fallback when unit=quantity hits a value-only cat
}

/** One sparkline point: a date string + the aggregated value across
 *  whatever scope the caller asked for (national OR single-state). */
export interface SparklinePoint {
  readonly date: string;
  readonly value: number;
}

/** One choropleth point: LGD numeric code (as a string, since
 *  GeoChoropleth coerces to number for the `keys_are_numeric` path)
 *  plus the value-for-the-selected-time. `time` is the selected_date
 *  the caller passes to GeoChoropleth's `selected_time` prop. */
export interface ChoroplethPoint {
  readonly entity_key: string;
  readonly value: number;
  readonly time: string;
}

/** All distinct dates present in the row set, sorted ascending.
 *  Empty array when rows is empty. */
export function listDates(rows: readonly SeizuresRow[]): readonly string[] {
  const seen = new Set<string>();
  for (const r of rows) seen.add(r.date);
  return Array.from(seen).sort();
}

/** The latest date in the row set, or null when empty.
 *  Drives the date-slider default. */
export function latestDate(rows: readonly SeizuresRow[]): string | null {
  const all = listDates(rows);
  return all.length === 0 ? null : all[all.length - 1];
}

/** Read a (cat, unit) column from one row. Returns null when the
 *  combination is invalid OR the cell is publisher-blank. */
export function readValue(
  row: SeizuresRow,
  cat: SeizuresCategory,
  unit: SeizuresUnit,
): number | null {
  const col = categoryColumn(cat, unit);
  if (col === null) return null;
  const raw = row[col];
  return typeof raw === "number" ? raw : null;
}

/** Project the raw rows to choropleth points for ONE date.
 *  - Null-valued rows are omitted (the GeoChoropleth C4 hatch fill
 *    renders the no-data state).
 *  - Rows whose state_slug doesn't map to an LGD code (e.g. the
 *    publisher's historical UT slugs like `dadra-and-nagar-haveli`
 *    in a post-2020-merger spine) are also omitted; the renderer's
 *    no-data hatch covers them too.
 *  - `state_filter` (when supplied) narrows to that single slug
 *    (so the choropleth highlights one state on the state-page
 *    surface). When omitted, all 36 states project. */
export function projectChoropleth(
  rows: readonly SeizuresRow[],
  cat: SeizuresCategory,
  unit: SeizuresUnit,
  selected_date: string,
  slugToLgd: (slug: string) => string | null,
  state_filter?: string | null,
): readonly ChoroplethPoint[] {
  const out: ChoroplethPoint[] = [];
  for (const r of rows) {
    if (r.date !== selected_date) continue;
    if (state_filter && r.state_slug !== state_filter) continue;
    const v = readValue(r, cat, unit);
    if (v === null) continue;
    const lgd = slugToLgd(r.state_slug);
    if (!lgd) continue;
    out.push({ entity_key: lgd, value: v, time: selected_date });
  }
  return out;
}

/** Project the raw rows to a sparkline (one point per date).
 *  - When `state_filter` is supplied, the value is that one state's
 *    reading on each date (or 0 when missing).
 *  - When omitted, the value is the SUM across all states on each
 *    date - publisher's TOTAL column for the "total" category, or
 *    summed components for the other categories. (Note: the publisher
 *    rounds intermediate sums, so sum(components) on `total` may
 *    diverge from sum(total_seizure_inr_crore) by a few thousandths
 *    of a crore; we use the publisher's pre-totaled column for
 *    `total` per D3.) */
export function projectSparkline(
  rows: readonly SeizuresRow[],
  cat: SeizuresCategory,
  unit: SeizuresUnit,
  state_filter?: string | null,
): readonly SparklinePoint[] {
  const dates = listDates(rows);
  const out: SparklinePoint[] = [];
  for (const d of dates) {
    let acc = 0;
    let any = false;
    for (const r of rows) {
      if (r.date !== d) continue;
      if (state_filter && r.state_slug !== state_filter) continue;
      const v = readValue(r, cat, unit);
      if (v === null) continue;
      acc += v;
      any = true;
    }
    out.push({ date: d, value: any ? acc : 0 });
  }
  return out;
}

/** Sum-on-final-date headline. Returns null when no rows match.
 *  Used as the big-number above the choropleth. */
export function headlineValue(
  rows: readonly SeizuresRow[],
  cat: SeizuresCategory,
  unit: SeizuresUnit,
  state_filter?: string | null,
): number | null {
  const last = latestDate(rows);
  if (!last) return null;
  let acc = 0;
  let any = false;
  for (const r of rows) {
    if (r.date !== last) continue;
    if (state_filter && r.state_slug !== state_filter) continue;
    const v = readValue(r, cat, unit);
    if (v === null) continue;
    acc += v;
    any = true;
  }
  return any ? acc : null;
}

/** Ordered display sequence for the picker chrome. */
export const SEIZURES_CATEGORIES: readonly SeizuresCategory[] = [
  "total",
  "cash",
  "liquor",
  "drugs",
  "metals",
  "other",
] as const;

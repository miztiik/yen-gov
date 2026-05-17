// Pure helpers for the unmapped-region chip strip. The Svelte component
// (./UnmappedRegionChips.svelte) is presentation-only; everything below
// the line "what data does a chip carry?" lives here so it's unit-testable
// without mounting a DOM (CLAUDE.md §15 + IndicatorChoropleth.boundaries.test.ts
// precedent: this codebase tests glue, not pixels).
//
// The chip carries five facts per Hans's governance ground truth:
//   - UT name (display_name)
//   - indicator value with unit (formatted via the indicator's formatter)
//   - bucket colour (computed by the same fillForValue the choropleth uses)
//   - population anchor (size-instinct correction, Rosling Factfulness)
//   - "no data" honesty when the indicator is silent on the UT
// See docs/concepts/unmapped-regions.md.

import { formatPopulationShort } from "./format";
import { DATA_BASE } from "./paths";

export interface UnmappedRegion {
  entity_id: string;
  display_name: string;
}

/**
 * Fetch the curated list of UTs surfaced as legend-strip chips. Lives at
 * datasets/reference/in/unmapped_regions.json (schema-validated under
 * datasets/schemas/unmapped-regions.schema.json); served via the standard
 * /data/ prefix per docs/architecture/frontend/data-loading.md.
 *
 * Throws when the fetch fails (caller decides whether to surface or
 * suppress — see the IndicatorChoropleth wiring, which suppresses so the
 * chip strip just renders empty rather than breaking the map).
 */
export async function fetchUnmappedRegions(): Promise<UnmappedRegion[]> {
  const res = await fetch(`${DATA_BASE}/reference/in/unmapped_regions.json`);
  if (!res.ok) {
    throw new Error(
      `fetch unmapped_regions.json failed: ${res.status} ${res.statusText}`,
    );
  }
  const body = (await res.json()) as { regions?: UnmappedRegion[] };
  if (!Array.isArray(body.regions)) {
    throw new Error("unmapped_regions.json: missing or non-array `regions`");
  }
  return body.regions.map((r) => ({
    entity_id: r.entity_id,
    display_name: r.display_name,
  }));
}

export interface ChipModel {
  entity_id: string;
  display_name: string;
  /** Raw indicator value, or null when the UT has no datum at the selected time. */
  value: number | null;
  /** Pre-formatted value string ("98.3%") or em-dash when null. */
  value_label: string;
  /** Pre-formatted population string ("64k people") or "—" when unknown. */
  population_label: string;
  /** Hex colour for the swatch. `null` when the chip is in the no-data variant — the component renders a dashed-outline empty swatch instead. */
  swatch: string | null;
}

/**
 * Project one region into the data shape the chip renders. Pure; no I/O,
 * no Svelte. Wrap with `regions.map(r => chipModelFor(r, ...))` at the
 * call site.
 */
export function chipModelFor(
  region: UnmappedRegion,
  values: Map<string, number>,
  populations: Map<string, number>,
  fillFor: (value: number) => string,
  formatValue: (value: number) => string,
): ChipModel {
  const v = values.get(region.entity_id);
  const has_value = v !== undefined && Number.isFinite(v);
  const pop = populations.get(region.entity_id);
  return {
    entity_id: region.entity_id,
    display_name: region.display_name,
    value: has_value ? (v as number) : null,
    value_label: has_value ? formatValue(v as number) : "—",
    population_label:
      pop !== undefined ? `${formatPopulationShort(pop)} people` : "—",
    swatch: has_value ? fillFor(v as number) : null,
  };
}

/**
 * Pick the latest absolute-people count for a given entity_id out of a
 * state-population indicator artifact's rows. The artifact stores
 * `value` in lakhs (1 lakh = 100,000); we return absolute people.
 *
 * Returns null when the entity has no rows, or every row's value is
 * null / non-finite (the integration contract for the chip: missing
 * population → "—" in the pop slot, chip still renders with the indicator
 * value).
 *
 * Pure: takes the parsed artifact rows; no fetch.
 */
export function latestPopulationFromLakhs(
  rows: ReadonlyArray<{ entity_id: string; time: string; value: number | null }>,
  entity_id: string,
): number | null {
  let best_time = "";
  let best_value: number | null = null;
  for (const r of rows) {
    if (r.entity_id !== entity_id) continue;
    if (r.value == null || !Number.isFinite(r.value)) continue;
    if (r.time > best_time) {
      best_time = r.time;
      best_value = r.value;
    }
  }
  return best_value == null ? null : Math.round(best_value * 100_000);
}

/**
 * Build the entity_id → absolute-people map for a list of regions in one
 * pass. Skips regions whose entity_id has no usable row.
 */
export function buildPopulationMap(
  rows: ReadonlyArray<{ entity_id: string; time: string; value: number | null }>,
  regions: ReadonlyArray<UnmappedRegion>,
): Map<string, number> {
  const out = new Map<string, number>();
  for (const r of regions) {
    const v = latestPopulationFromLakhs(rows, r.entity_id);
    if (v !== null) out.set(r.entity_id, v);
  }
  return out;
}

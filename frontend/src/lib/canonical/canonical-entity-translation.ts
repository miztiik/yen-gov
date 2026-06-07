// Canonical entity-id translation (R2 reader-flip seam).
//
// The long-format CSV store ships entity_ids as LGD-name slugs:
//   - country     : "IN"
//   - state / UT  : "tamil-nadu", "andhra-pradesh", ...
//   - district    : "tamil-nadu/chennai", "andhra-pradesh/visakhapatnam", ...
//
// The downstream IndicatorCard / IndicatorChoropleth / IndicatorRanked
// renderers consume the legacy ECI shape (`canonicalEntityToLegacy` output):
//   - country     : "IN"
//   - state / UT  : "S22", "S01", ...
//   - district    : "S22-D635", "S01-D744", ...
//
// This module is the single translation seam. The R2 reader path
// (`loadSingleFromCanonical` / `loadFacetMultiplexedFromCanonical` when
// `descriptor.csv_path` is set) reads the CSV in slug form, then translates
// per-row via the map returned by `loadCanonicalSlugToLegacyMap()`.
//
// The map is built once per browser session by fetching + parsing
// `data/entities/geo.csv` (821 rows: 1 country + 36 states + 784 districts;
// ~50 KB on the wire, well under the cost of registering a DuckDB view for
// translation). Lazy + Promise-cached; mockable for tests via
// `__setCanonicalSlugToLegacyMapForTests`.
//
// Why a separate module (not embedded in `indicator-from-canonical.ts`)?
//   1. Mock surface: vitest tests that mock `query` to assert SQL shape
//      stay focused on the reader; the translation layer mocks
//      independently via its own helper.
//   2. Pure single-flight: no DuckDB-WASM dependency means the contract
//      tests don't have to boot DuckDB to assert the shape.
//   3. Generalisation: future canonical readers (Phase F1 view-models,
//      YENASK semantic catalogue) can reuse the same map without
//      reaching into `indicator-from-canonical.ts`.

import { DATA_BASE } from "../paths";

const GEO_CSV_URL = `${DATA_BASE}/data/entities/geo.csv`;

let mapPromise: Promise<Map<string, string>> | null = null;

/** Result Map: slug entity_id (as it appears in long-format CSV) → legacy
 *  ECI-style entity_id (as IndicatorCard / Choropleth consume). Returns
 *  the same Map instance for the lifetime of the session. */
export async function loadCanonicalSlugToLegacyMap(): Promise<Map<string, string>> {
  if (mapPromise) return mapPromise;
  mapPromise = (async () => {
    const res = await fetch(GEO_CSV_URL);
    if (!res.ok) {
      throw new Error(
        `canonical-entity-translation: fetch failed: ${res.status} ${res.statusText} (${GEO_CSV_URL})`,
      );
    }
    const csv = await res.text();
    return buildCanonicalSlugToLegacyMap(csv);
  })();
  mapPromise.catch(() => {
    mapPromise = null;
  });
  return mapPromise;
}

/** Translate a slug entity_id to the legacy ECI-style entity_id.
 *  Pass-through for unrecognised slugs (caller decides whether to drop
 *  the row or surface it as-is). */
export function translateCanonicalSlugToLegacy(
  map: ReadonlyMap<string, string>,
  slug: string,
): string {
  return map.get(slug) ?? slug;
}

/** Pure CSV → Map builder. Exported for unit tests that want to assert
 *  the parse semantics without round-tripping through `fetch`. */
export function buildCanonicalSlugToLegacyMap(csv: string): Map<string, string> {
  const result = new Map<string, string>();
  const lines = csv.split(/\r?\n/);
  // Empty CSV (no content) returns an empty Map. A single empty line is
  // still treated as empty (no header to parse).
  if (lines.length === 0 || (lines.length === 1 && lines[0] === "")) {
    return result;
  }

  // Header parse: expect at least `entity_id,name,parent,entity_kind,aliases,...`
  const header = parseCsvLine(lines[0]);
  const idxEntityId = header.indexOf("entity_id");
  const idxParent = header.indexOf("parent");
  const idxKind = header.indexOf("entity_kind");
  const idxAliases = header.indexOf("aliases");
  if (idxEntityId < 0 || idxParent < 0 || idxKind < 0 || idxAliases < 0) {
    throw new Error(
      "canonical-entity-translation: geo.csv header missing required columns " +
        "(entity_id, parent, entity_kind, aliases)",
    );
  }

  // Two-pass parse: first collect the state row's ECI code (so districts
  // can prefix it). A state's aliases carries one of `S<n>` or `U<n>`.
  const stateEci: Map<string, string> = new Map(); // slug → "S22" / "U05"

  // Row pass 1 (states + country)
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line) continue;
    const cells = parseCsvLine(line);
    const entityId = cells[idxEntityId];
    const kind = cells[idxKind];
    if (kind === "country") {
      // Country aliases carries e.g. "IN|IND|356"; the legacy id stays "IN".
      result.set(entityId, "IN");
      continue;
    }
    if (kind === "state") {
      const aliases = cells[idxAliases] ?? "";
      const eci = extractEciToken(aliases);
      if (eci !== null) {
        stateEci.set(entityId, eci);
        result.set(entityId, eci);
      }
    }
  }

  // Row pass 2 (districts) — needs stateEci populated above.
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line) continue;
    const cells = parseCsvLine(line);
    const kind = cells[idxKind];
    if (kind !== "district") continue;
    const entityId = cells[idxEntityId];
    const parent = cells[idxParent];
    const aliases = cells[idxAliases] ?? "";
    const lgdToken = extractLgdToken(aliases);
    const parentEci = stateEci.get(parent);
    if (lgdToken === null || !parentEci) continue;
    result.set(entityId, `${parentEci}-D${lgdToken}`);
  }

  return result;
}

/** Extract the first `S<n>` or `U<n>` token from a `|`-delimited aliases
 *  field. Returns null when none found. */
function extractEciToken(aliases: string): string | null {
  for (const token of aliases.split("|")) {
    const t = token.trim();
    if (/^[SU]\d{1,2}$/.test(t)) return t;
  }
  return null;
}

/** Extract the numeric LGD code from an `lgd:<n>` token in a `|`-delimited
 *  aliases field. Returns null when none found. */
function extractLgdToken(aliases: string): string | null {
  for (const token of aliases.split("|")) {
    const t = token.trim();
    if (t.startsWith("lgd:")) {
      const rest = t.slice(4);
      if (/^\d+$/.test(rest)) return rest;
    }
  }
  return null;
}

/** Minimal RFC-4180 CSV-line parser. The geo.csv we consume here has no
 *  embedded quotes / multi-line cells, so we keep the parser lean.
 *  Exported for testing. */
export function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cur += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        out.push(cur);
        cur = "";
      } else {
        cur += ch;
      }
    }
  }
  out.push(cur);
  return out;
}

// -----------------------------------------------------------------------------
// Test seam
// -----------------------------------------------------------------------------

/** Test-only: seed the cache with a fixture map and short-circuit the
 *  network fetch. Call from `beforeEach` in vitest. */
export function __setCanonicalSlugToLegacyMapForTests(
  map: Map<string, string> | null,
): void {
  mapPromise = map === null ? null : Promise.resolve(map);
}

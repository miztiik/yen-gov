// Slug-based constituency lookup against the canonical electoral entities
// CSV (datasets/data/entities/electoral.csv).
//
// Election experience overhaul plan PR-W3b (2026-06-10): the new leaf
// route `/<state>/elections/<event>/<constituency>` dispatches on the
// event-slug body prefix to decide AC vs PC, then resolves the bare
// name-slug to a canonical entity row. The `eci_no` falls out of the
// lookup result.
//
// Slug resolution rule:
//   slugify(entity.name) === constituency_slug
//   AND entity.state === state_slug
//   AND entity.entity_kind === kind ("ac" | "pc")
//
// When more than one row matches (Indian electoral geography can have
// e.g. ACs named "Bastar" across multiple delim cohorts in the same
// state), the LATEST delim_year wins. Citizens reaching a leaf URL want
// the current-delimitation seat by default.
//
// Cache shape mirrors `psephlab/alliances.ts`: module-scope Promise<string>
// for the raw CSV body (one fetch per session), then per-lookup synchronous
// table walks. The CSV is small (~4734 rows today, single hex below
// 500 KB) so loading the whole thing up-front is faster than a DuckDB
// query.

import { slugify } from "../slug";
import { DATA_BASE } from "../paths";

const ELECTORAL_CSV_PATH = "data/entities/electoral.csv";

let raw_csv_promise: Promise<string> | null = null;

/** Absolute URL for the canonical electoral entities CSV. Exposed for
 *  tests so they can stub fetch by URL match. */
export function electoralEntitiesUrl(): string {
  return `${DATA_BASE}/${ELECTORAL_CSV_PATH}`;
}

/** Reset module-scope caches. Test-only — production never calls. */
export function _resetConstituencyLookupCachesForTesting(): void {
  raw_csv_promise = null;
}

async function fetchRawCsv(): Promise<string> {
  if (raw_csv_promise) return raw_csv_promise;
  raw_csv_promise = (async () => {
    try {
      const res = await fetch(electoralEntitiesUrl());
      if (!res.ok) return "";
      return await res.text();
    } catch {
      return "";
    }
  })();
  raw_csv_promise.catch(() => {
    raw_csv_promise = null;
  });
  return raw_csv_promise;
}

/** Electoral entity row shape returned by the lookup. Mirrors the
 *  shipped columns in `datasets/data/entities/electoral.csv` (verified
 *  2026-06-10: `entity_id, name, entity_kind, delim_year, state, parent,
 *  eci_no, aliases, reservation`). All callers see strings except
 *  `eci_no` + `delim_year` which are parsed to numbers. */
export interface ConstituencyEntity {
  entity_id: string;
  name: string;
  /** "ac" or "pc" — the W3b leaf dispatches on body prefix to pick. */
  entity_kind: "ac" | "pc";
  delim_year: number;
  /** LGD slug (e.g. "chhattisgarh"). */
  state: string;
  parent: string;
  eci_no: number;
}

/** Parse the raw CSV. Pure — exposed for tests so the table walk is
 *  testable without fetch. The CSV ships with zero quoted fields per
 *  url-namespace-disjointness.test.ts comment block; naive split(",")
 *  is safe today. */
export function parseElectoralCsv(text: string): ConstituencyEntity[] {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  if (lines.length < 2) return [];
  lines.shift(); // header
  const out: ConstituencyEntity[] = [];
  for (const line of lines) {
    const cols = line.split(",");
    if (cols.length < 7) continue;
    const entity_kind = cols[2];
    if (entity_kind !== "ac" && entity_kind !== "pc") continue;
    const eci_no = parseInt(cols[6], 10);
    if (!Number.isFinite(eci_no)) continue;
    const delim_year = parseInt(cols[3], 10);
    out.push({
      entity_id: cols[0],
      name: cols[1],
      entity_kind,
      delim_year: Number.isFinite(delim_year) ? delim_year : 0,
      state: cols[4],
      parent: cols[5],
      eci_no,
    });
  }
  return out;
}

interface LookupKey {
  state: string;
  kind: "ac" | "pc";
  name_slug: string;
}

/** Pure resolution rule, exposed for tests. Returns the LATEST
 *  delim_year match when multiple rows collide. */
export function resolveConstituencyFromRows(
  rows: readonly ConstituencyEntity[],
  key: LookupKey,
): ConstituencyEntity | null {
  let best: ConstituencyEntity | null = null;
  for (const r of rows) {
    if (r.state !== key.state) continue;
    if (r.entity_kind !== key.kind) continue;
    if (slugify(r.name) !== key.name_slug) continue;
    if (!best || r.delim_year > best.delim_year) best = r;
  }
  return best;
}

/** Async API: resolve a constituency by (state slug, kind, name slug).
 *  Returns null on miss (caller renders not-found). */
export async function findConstituencyBySlug(
  state_slug: string,
  kind: "ac" | "pc",
  name_slug: string,
): Promise<ConstituencyEntity | null> {
  const text = await fetchRawCsv();
  if (text === "") return null;
  const rows = parseElectoralCsv(text);
  return resolveConstituencyFromRows(rows, {
    state: state_slug,
    kind,
    name_slug,
  });
}

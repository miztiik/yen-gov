// Alliance-membership lookup for the Psephlab counting-rule engine.
//
// Reads `datasets/data/entities/party_alliances.csv` (one row per
// (party_id, period_label) with the alliance name) and exposes
// `loadAlliances(event)` returning an `AllianceLookup`:
//
//   (party_id: string) => string | null
//
// Two alliance-aware counting rules consume this:
//   - rules/trsRound2Alliance.ts (TRS Round 2, alliance pool)
//   - rules/irvAllianceTransfer.ts (Ranked-choice, alliance-transfer)
//
// Both rules call `tallies.alliances?.(party_id) ?? null`. When the CSV
// has no rows for the active event (only TN-2026 today; other events
// degrade gracefully) the lookup returns `() => null` and the
// alliance-aware rules fall back to their proportional-transfer sibling
// (with a one-line inline caveat addendum the host UI surfaces).
//
// Caching: one cached Promise per `period_label` so repeated mount /
// unmount cycles in Psephlab.svelte do not re-fetch. Cache is per-tab
// (module-level Map); the file itself ships with the static bundle so
// the fetch is essentially synchronous after the first hit.
//
// Tests: see alliances.test.ts. The fetch is stubbed (explicit
// CLAUDE.md section 15 carve-out for canonical-store loaders). The
// real CSV at `datasets/data/entities/party_alliances.csv` is in the
// repo; the e2e smoke (psephlab-smoke.spec.ts) exercises the live
// fetch path.

import { DATA_BASE } from "../paths";
import type { AllianceLookup } from "./types";

const PARTY_ALLIANCES_PATH = "data/entities/party_alliances.csv";

// Module-level cache keyed by event id. Promise so concurrent callers
// for the same event share one fetch.
const cache = new Map<string, Promise<AllianceLookup>>();

// Module-level cache for the raw CSV body itself - the file is event-
// agnostic and small (~1 KB today, will grow to ~50 KB at full per-
// (event, state) coverage), so one fetch per session is enough.
let raw_csv_promise: Promise<string> | null = null;

/** Build the absolute URL for the alliance CSV. Exposed for tests. */
export function allianceCsvUrl(): string {
  return `${DATA_BASE}/${PARTY_ALLIANCES_PATH}`;
}

/** Fetch the raw CSV body, cached at module scope. Returns "" on 404 or
 *  network error so the caller can degrade silently to a no-alliance
 *  fallback lookup. */
async function fetchRawCsv(): Promise<string> {
  if (raw_csv_promise) return raw_csv_promise;
  raw_csv_promise = (async () => {
    try {
      const res = await fetch(allianceCsvUrl());
      if (!res.ok) {
        // 404 in dev is expected before the CSV exists; in prod it would
        // be an integrity violation but we still degrade rather than
        // crash the whole Election Studio.
        return "";
      }
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

/** Minimal CSV parser. The alliance CSV is hand-authored, ASCII-only,
 *  no quoted fields, no embedded commas - so a plain split is correct.
 *  Returns rows as objects keyed by the header columns. Exposed for
 *  tests; production code calls `loadAlliances`. */
export function parsePartyAlliancesCsv(text: string): Array<{
  party_id: string;
  period_label: string;
  alliance: string;
}> {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  if (lines.length < 2) return [];
  const header = lines[0].split(",").map((s) => s.trim());
  const idx_party = header.indexOf("party_id");
  const idx_period = header.indexOf("period_label");
  const idx_alliance = header.indexOf("alliance");
  if (idx_party === -1 || idx_period === -1 || idx_alliance === -1) return [];
  const out: Array<{ party_id: string; period_label: string; alliance: string }> = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split(",");
    const alliance = (cells[idx_alliance] ?? "").trim();
    // Empty alliance cell = party contested unallied; skip - the lookup
    // returns null for both "no row" and "row with empty alliance".
    if (alliance === "") continue;
    out.push({
      party_id: (cells[idx_party] ?? "").trim(),
      period_label: (cells[idx_period] ?? "").trim(),
      alliance,
    });
  }
  return out;
}

/** Returns an AllianceLookup for the active election event. The lookup
 *  returns the alliance label (e.g. "NDA", "INDIA", "SPA") for parties
 *  that have a row in `party_alliances.csv` with the matching
 *  `period_label`, or null for parties without a row (treated as
 *  unallied for that election).
 *
 *  When the CSV is missing / empty / has no rows for the event, returns
 *  `() => null` so the alliance-aware rules degrade transparently to
 *  their proportional sibling. */
export function loadAlliances(event: string): Promise<AllianceLookup> {
  const hit = cache.get(event);
  if (hit) return hit;
  const p = (async (): Promise<AllianceLookup> => {
    const text = await fetchRawCsv();
    if (text === "") return () => null;
    const rows = parsePartyAlliancesCsv(text).filter((r) => r.period_label === event);
    if (rows.length === 0) return () => null;
    const map = new Map<string, string>();
    for (const row of rows) map.set(row.party_id, row.alliance);
    return (party_id: string) => map.get(party_id) ?? null;
  })();
  cache.set(event, p);
  p.catch(() => cache.delete(event));
  return p;
}

/** Returns the set of unique alliance labels declared for the active
 *  event. Useful for hero-card copy ("This event has 3 declared
 *  alliances: NDA, SPA, AIADMK+"). Returns an empty Set when no rows
 *  exist for the event. */
export async function alliancesForEvent(event: string): Promise<ReadonlySet<string>> {
  const text = await fetchRawCsv();
  if (text === "") return new Set();
  const rows = parsePartyAlliancesCsv(text).filter((r) => r.period_label === event);
  return new Set(rows.map((r) => r.alliance));
}

/** Reset all caches. Test-only - production code never calls this. */
export function _resetAllianceCachesForTesting(): void {
  cache.clear();
  raw_csv_promise = null;
}

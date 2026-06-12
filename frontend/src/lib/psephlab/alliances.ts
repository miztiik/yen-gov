// Alliance-membership lookup for the Psephlab counting-rule engine.
//
// Reads `datasets/data/entities/party_alliances.csv` (one row per
// (party_id, event_id, state) with the alliance name; schema v2.0
// 2026-06-12 per TODO/20260612-alliance-phase-1-structural-fix-plan.md)
// and exposes `loadAlliances(event, state?)` returning an `AllianceLookup`:
//
//   (party_id: string) => string | null
//
// Two alliance-aware counting rules consume this:
//   - rules/trsRound2Alliance.ts (TRS Round 2, alliance pool)
//   - rules/irvAllianceTransfer.ts (Ranked-choice, alliance-transfer)
//
// Both rules call `tallies.alliances?.(party_id) ?? null`. When the CSV
// has no rows for the active event (most events today; degrades
// gracefully) the lookup returns `() => null` and the alliance-aware
// rules fall back to their proportional-transfer sibling (with a
// one-line inline caveat addendum the host UI surfaces).
//
// State scoping (D2 fix per plan-doc v2.0 schema): the `state` arg is
// the LGD state slug ("tamil-nadu", "west-bengal", "maharashtra") for
// per-state consumers (StateElection / state-overview). When provided,
// the lookup filters to rows where state matches OR state === "IN"
// (national-event rows are visible from any state page). When omitted,
// returns all rows for the event (no state filter; the legacy v1
// behaviour for callers that have no state context).
//
// Caching: one cached Promise per `event|state` key so repeated mount /
// unmount cycles do not re-fetch. Cache is per-tab (module-level Map);
// the file itself ships with the static bundle so the fetch is
// essentially synchronous after the first hit.
//
// Tests: see alliances.test.ts. The fetch is stubbed (explicit
// CLAUDE.md section 15 carve-out for canonical-store loaders). The
// real CSV at `datasets/data/entities/party_alliances.csv` is in the
// repo; the e2e smoke (psephlab-smoke.spec.ts) exercises the live
// fetch path.

import { DATA_BASE } from "../paths";
import type { AllianceLookup } from "./types";

const PARTY_ALLIANCES_PATH = "data/entities/party_alliances.csv";

// Module-level cache keyed by `${event}|${state ?? "*"}`. Promise so
// concurrent callers for the same scope share one fetch.
const cache = new Map<string, Promise<AllianceLookup>>();

// Module-level cache for the raw CSV body itself - the file is event-
// agnostic and small (~3 KB today, will grow as Phase 1b curation
// lands), so one fetch per session is enough.
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
 *  Returns rows as objects keyed by the v2.0 header columns. Exposed
 *  for tests; production code calls `loadAlliances`. */
export function parsePartyAlliancesCsv(text: string): Array<{
  party_id: string;
  event_id: string;
  state: string;
  alliance: string;
}> {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  if (lines.length < 2) return [];
  const header = lines[0].split(",").map((s) => s.trim());
  const idx_party = header.indexOf("party_id");
  const idx_event = header.indexOf("event_id");
  const idx_state = header.indexOf("state");
  const idx_alliance = header.indexOf("alliance");
  if (
    idx_party === -1 ||
    idx_event === -1 ||
    idx_state === -1 ||
    idx_alliance === -1
  ) {
    return [];
  }
  const out: Array<{
    party_id: string;
    event_id: string;
    state: string;
    alliance: string;
  }> = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split(",");
    const alliance = (cells[idx_alliance] ?? "").trim();
    // Empty alliance cell = party contested unallied; skip - the lookup
    // returns null for both "no row" and "row with empty alliance".
    if (alliance === "") continue;
    out.push({
      party_id: (cells[idx_party] ?? "").trim(),
      event_id: (cells[idx_event] ?? "").trim(),
      state: (cells[idx_state] ?? "").trim(),
      alliance,
    });
  }
  return out;
}

/** Filter rows by event_id, and (when state provided) by state OR
 *  "IN" (national events visible from every state page). Pure
 *  function exported for tests. */
function filterRowsForScope(
  rows: ReadonlyArray<{ party_id: string; event_id: string; state: string; alliance: string }>,
  event: string,
  state: string | undefined,
): Array<{ party_id: string; event_id: string; state: string; alliance: string }> {
  return rows.filter((r) => {
    if (r.event_id !== event) return false;
    if (state === undefined) return true;
    return r.state === state || r.state === "IN";
  });
}

/** Returns an AllianceLookup for the active election event, optionally
 *  scoped to a state. The lookup returns the alliance label (e.g.
 *  "NDA-2024", "INDIA-2024", "Mahayuti", "Sanyukta Morcha") for parties
 *  that have a row in `party_alliances.csv` matching the (event_id,
 *  state) scope, or null for parties without a row (treated as
 *  unallied for that election).
 *
 *  When `state` is provided, the loader matches rows where
 *  `r.state === state` OR `r.state === "IN"` (national-event rows are
 *  visible from every state page). When omitted, returns all rows for
 *  the event with no state filter (legacy behaviour).
 *
 *  When the CSV is missing / empty / has no rows for the (event,
 *  state) scope, returns `() => null` so the alliance-aware rules
 *  degrade transparently to their proportional sibling. */
export function loadAlliances(
  event: string,
  state?: string,
): Promise<AllianceLookup> {
  const cache_key = `${event}|${state ?? "*"}`;
  const hit = cache.get(cache_key);
  if (hit) return hit;
  const p = (async (): Promise<AllianceLookup> => {
    const text = await fetchRawCsv();
    if (text === "") return () => null;
    const rows = filterRowsForScope(parsePartyAlliancesCsv(text), event, state);
    if (rows.length === 0) return () => null;
    const map = new Map<string, string>();
    for (const row of rows) map.set(row.party_id, row.alliance);
    return (party_id: string) => map.get(party_id) ?? null;
  })();
  cache.set(cache_key, p);
  p.catch(() => cache.delete(cache_key));
  return p;
}

/** Returns the set of unique alliance labels declared for the active
 *  event (optionally state-scoped). Useful for hero-card copy ("This
 *  event has 3 declared alliances: NDA, SPA, AIADMK+"). Returns an
 *  empty Set when no rows exist for the (event, state) scope. */
export async function alliancesForEvent(
  event: string,
  state?: string,
): Promise<ReadonlySet<string>> {
  const text = await fetchRawCsv();
  if (text === "") return new Set();
  const rows = filterRowsForScope(parsePartyAlliancesCsv(text), event, state);
  return new Set(rows.map((r) => r.alliance));
}

/** Reset all caches. Test-only - production code never calls this. */
export function _resetAllianceCachesForTesting(): void {
  cache.clear();
  raw_csv_promise = null;
}

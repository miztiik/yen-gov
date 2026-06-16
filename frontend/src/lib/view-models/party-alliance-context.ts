// PR-8 of TODO/20260614-party-page-reimagination-plan.md.
//
// `loadPartyAllianceContext(party_id)` builds the "Who they ride
// with" Alliance Context strip view-model from
// `datasets/data/entities/party_alliances.csv` (per-event party
// alliance memberships, composite PK: party_id + event_id + state)
// cross-referenced against `datasets/data/marts/party_pages/
// history.csv` for the per-event seat counts that drive the
// "led / junior / alone" role classification.
//
// The strip is rendered DIRECTLY UNDER the Current Strength strip
// (so the citizen reads: party-now -> alliance-now -> historical
// charts). The view-model surfaces two sections:
//
//   parliament: latest Parliament general-election the focal party was in an
//     alliance for (or null if there is no national-level alliance
//     row in the corpus yet) - one line answering "what alliance
//     does this party ride with nationally right now?".
//   state_assemblies: one row per state where the focal party has
//     an alliance row in the corpus, picking the LATEST event per
//     state - answering "and what about in each state where they
//     contested?".
//
// Sentinel parties (NOTA, UNK) AND Independent (IND) return null
// from this loader - the caller suppresses the entire strip for
// them; the aggregate is structurally meaningless (sentinels do
// not form alliances; independents are by definition unallied).
//
// Per the user-memory note 2026-06-14 "Alliance rows ship
// independent of candidacies CSV": when an alliance row exists
// but per-state candidacies are not yet ingested (so seat-count
// derivation is impossible), the strip degrades honestly to
// role="alone" with empty partner_names_top - the alliance is
// recorded but the role can't be classified. The slate-400
// caveat at the bottom of the component flags the limitation.

import { csvColumnsClause } from "../canonical/csv-columns";
import { query, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { fetchStates } from "../data";
import { loadAllPartiesMeta } from "./parties";
import { slugify } from "../slug";

/** Alliance ledger paths (repo-relative for columns.json lookup +
 *  runtime URL for DuckDB-WASM HTTP reads). */
const ALLIANCES_REL = "datasets/data/entities/party_alliances.csv";
const ALLIANCES_URL = `${DATA_BASE}/data/entities/party_alliances.csv`;

/** Party-page mart paths (repo-relative + runtime URL). Duplicated
 *  here rather than imported from `party-current-strength.ts` so
 *  vitest mocks of the duckdb boundary do not need to cross both
 *  view-model files. */
const PARTY_HISTORY_REL = "datasets/data/marts/party_pages/history.csv";
const PARTY_HISTORY_URL = `${DATA_BASE}/data/marts/party_pages/history.csv`;

/** Sentinel party id for Independent candidates. Independents do not
 *  form alliances by definition; the loader short-circuits to null
 *  for this id (defence in depth alongside the upstream
 *  `is_sentinel` flag, which is set on NOTA + UNK but NOT on IND -
 *  IND carries real votes in the canonical store and is not flagged
 *  as a sentinel meta-row, so this loader has to know about it). */
const INDEPENDENT_PARTY_ID = "parties.IN.IND";

/** Max number of partner short-names to surface in the line copy.
 *  Beyond this the renderer appends "..." and exposes the total
 *  count via `partner_count`. v1: 5 (per Max M5b verbatim spec). */
const MAX_PARTNER_NAMES = 5;

/** Parliament-event state slug used in the alliance ledger to denote a
 *  national-level alliance row (vs a per-state assembly row).
 *  Mirrors the columns.json schema note for party_alliances.csv. */
const PARLIAMENT_STATE_TOKEN = "IN";

/** Render-time recency window for the Alliance Context strip.
 *  PR-11 of TODO/20260615-party-page-citizen-fixes-plan.md (Jony +
 *  Citizen, ESCALATE E4): the citizen-facing strip caps to events
 *  in the last 10 years - alliance ledger rows older than this are
 *  preserved in the canonical CSV but NOT rendered, because the
 *  political alignment of an alliance from >10y ago is rarely the
 *  same surface the citizen is asking about today (e.g. the 2009
 *  UPA vs the 2024 INDIA bloc). The cap is computed against the
 *  current calendar year inside `fetchPartyAllianceContext`; tests
 *  inject an explicit `current_year` via `loadPartyAllianceContext`
 *  opts. The cap is APPLIED INSIDE `projectAllianceContext` so the
 *  pure projection is fully test-pinnable. */
const RECENCY_CAP_YEARS = 10;

/** Parliament alliance context - the focal party's role + partners
 *  in the latest LS event with an alliance row. Null when the focal
 *  has no national alliance row in the corpus yet. */
export interface PartyAllianceContextParliament {
  /** Citizen-facing event label (e.g. "Parliament 2024"). */
  event_label: string;
  /** Canonical event id (e.g. "general-2024"). */
  event_id: string;
  /** Alliance name with year suffix stripped (e.g. "NDA-2024" ->
   *  "NDA"). The year is already in `event_label`; doubling it on
   *  the alliance pill is noise. */
  alliance: string;
  /** Role of the focal party within the alliance:
   *    - "led":    focal has the most seats among partners.
   *    - "junior": focal has fewer seats than at least one partner.
   *    - "alone":  no partners on file (alliance row exists but
   *                partner-seat data is missing - degraded display
   *                per the user-memory "alliance rows ship without
   *                candidacies" note). */
  role: "led" | "junior" | "alone";
  /** Number of OTHER parties in the alliance (excludes focal). */
  partner_count: number;
  /** Top-N partner short names by seats won (descending), truncated
   *  at MAX_PARTNER_NAMES. The renderer appends "..." when this is
   *  shorter than `partner_count` to flag the truncation. */
  partner_names_top: string[];
  /** Sum of seats won across all alliance members (focal + partners)
   *  in the LS chamber for this event. Zero when seat data is
   *  unavailable; the renderer suppresses the "(N seats)" tail in
   *  that case. */
  total_alliance_seats: number;
}

/** Per-state alliance context. One row per state where the focal
 *  party has an alliance row in the corpus, picking the LATEST
 *  event per state. */
export interface PartyAllianceContextStateAssembly {
  /** State slug (e.g. "maharashtra"). */
  state: string;
  /** Citizen-facing state name (e.g. "Maharashtra"). */
  state_name: string;
  /** Citizen-facing event label (e.g. "Maharashtra (2024)"). */
  event_label: string;
  /** Canonical event id (e.g. "assembly-2024"). */
  event_id: string;
  /** Alliance name; null when the alliance ledger row has empty
   *  alliance (focal contested alone in this state). */
  alliance: string | null;
  /** Role of the focal party within the alliance (see Parliament). */
  role: "led" | "junior" | "alone";
  /** Number of OTHER parties in the alliance (excludes focal). */
  partner_count: number;
  /** Top-N partner short names by seats won (descending). */
  partner_names_top: string[];
  /** Sum of seats won across all alliance members in this state
   *  Assembly for this event. Zero when seat data unavailable. */
  total_alliance_seats: number;
}

/** Top-level view-model for the Alliance Context strip. */
export interface PartyAllianceContext {
  parliament: PartyAllianceContextParliament | null;
  state_assemblies: PartyAllianceContextStateAssembly[];
}

/** Raw alliance ledger row from DuckDB. */
interface RawAllianceRow {
  event_id: string | null;
  state: string | null;
  alliance: string | null;
  party_id: string | null;
}

/** Raw seat-aggregation row from the history mart. */
interface RawSeatsRow {
  party_id: string | null;
  body: string | null;
  year: number | bigint | null;
  state: string | null;
  seats: number | bigint | null;
}

function intOrNull(value: number | bigint | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "bigint") return Number(value);
  return Number.isFinite(value) ? Math.trunc(value) : null;
}

/** Pure: extract the polling year from a canonical event_id
 *  (e.g. "general-2024" -> 2024, "assembly-2020" -> 2020). Returns
 *  null when the id does not end in a 4-digit year. Exported for
 *  vitest. */
export function eventIdToYear(event_id: string): number | null {
  const m = event_id.match(/(\d{4})$/);
  if (!m) return null;
  return parseInt(m[1]!, 10);
}

/** Pure: derive the citizen-facing event label for the Parliament
 *  section (e.g. "general-2024" -> "Parliament 2024"). Returns the
 *  event_id verbatim when no year suffix matches (defensive; today's
 *  corpus always carries the suffix). Exported for vitest. */
export function parliamentEventLabel(event_id: string): string {
  const year = eventIdToYear(event_id);
  if (year === null) return event_id;
  return `Parliament ${year}`;
}

/** Pure: derive the citizen-facing event label for one state
 *  Assembly row (e.g. ("Maharashtra", "assembly-2024") -> "Maharashtra
 *  (2024)"). Falls back to event_id verbatim when no year matches.
 *  Exported for vitest. */
export function stateAssemblyEventLabel(
  state_name: string,
  event_id: string,
): string {
  const year = eventIdToYear(event_id);
  if (year === null) return `${state_name} (${event_id})`;
  return `${state_name} (${year})`;
}

/** Pure: strip a trailing `-YYYY` year suffix from an alliance name
 *  (e.g. "NDA-2024" -> "NDA", "INDIA-2024" -> "INDIA"). Leaves
 *  unsuffixed names verbatim (e.g. "Mahayuti", "MVA", "LDF", "UDF").
 *  Exported for vitest. */
export function stripAllianceYearSuffix(alliance: string): string {
  return alliance.replace(/-\d{4}$/, "");
}

/** Pure: pure word-by-word Title Case of a state slug (e.g.
 *  "tamil-nadu" -> "Tamil Nadu"). Fallback for when the injected
 *  state-name resolver returns null. Lowercases small connector
 *  words ("and", "of", "the") that should not be capitalised in
 *  Title Case prose - e.g. "jammu-and-kashmir" -> "Jammu and
 *  Kashmir" (NOT "Jammu And Kashmir"). Never lowercases the FIRST
 *  word so leading "and"/"of" stays capitalised. Exported for
 *  vitest. */
export function titleCaseStateSlug(slug: string): string {
  if (!slug) return "";
  const connectors = new Set(["and", "of", "the"]);
  return slug
    .split("-")
    .map((part, idx) => {
      if (part.length === 0) return part;
      if (idx > 0 && connectors.has(part.toLowerCase())) {
        return part.toLowerCase();
      }
      return part[0]!.toUpperCase() + part.slice(1);
    })
    .join(" ");
}

/** Pure: classify the focal party's role within an alliance given
 *  the seat counts of focal vs partners. Returns "alone" when there
 *  are no partners on file (alliance row exists but partner-seat
 *  data is missing - degraded display per the user-memory note);
 *  "led" when focal has at least as many seats as the highest-seat
 *  partner; "junior" otherwise. The tie-favours-focal rule is
 *  intentional: when two partners have equal max seats, the
 *  national-narrative convention is to call the seat-leader the
 *  alliance leader (e.g. BJP-led NDA when JD(U) had 12 and BJP
 *  had 12 in some historical alliance row would still be "led").
 *  Exported for vitest. */
export function pickRoleFromSeats(
  focal_seats: number,
  partner_seats: number[],
): "led" | "junior" | "alone" {
  if (partner_seats.length === 0) return "alone";
  const max_partner = Math.max(...partner_seats);
  return focal_seats >= max_partner ? "led" : "junior";
}

/** Composite key for seat lookups - (party_id, body, year, state).
 *  For Parliament rows the state token in the alliance ledger is
 *  "IN" but the history mart carries per-state rows; the loader
 *  SUMs across states for parliament lookups so the key for
 *  Parliament rows uses state="" (the lookup helper joins on
 *  body="parliament" and ignores state). */
type SeatLookupKey = string;

function seatLookupKey(
  party_id: string,
  body: "parliament" | "assembly",
  year: number,
  state: string,
): SeatLookupKey {
  return `${party_id}\u0001${body}\u0001${year}\u0001${state}`;
}

/** Pure: build the SQL that fetches the focal party's alliance
 *  ledger rows. Returns one row per (event_id, state) for the
 *  focal party. Exported for vitest. */
export function buildFocalAllianceSql(
  safePartyId: string,
  alliancesClause: string,
  alliancesUrl: string,
): string {
  return `
    SELECT event_id, state, alliance, party_id
    FROM read_csv('${alliancesUrl}', ${alliancesClause}, header=true)
    WHERE party_id = '${safePartyId}'
    ORDER BY event_id DESC, state
  `;
}

/** Pure: build the SQL that fetches all alliance partners for the
 *  (event_id, state, alliance) tuples the focal party participates
 *  in. Uses a single literal IN list of (event_id, state, alliance)
 *  triples encoded as JSON strings to keep the SQL portable across
 *  DuckDB-WASM versions. Returns rows for ALL parties in those
 *  alliances (including the focal itself - the caller filters out
 *  the focal-id row when building partner lists).
 *
 *  Exported for vitest. */
export function buildPartnerAllianceSql(
  focal_alliance_keys: { event_id: string; state: string; alliance: string }[],
  alliancesClause: string,
  alliancesUrl: string,
): string {
  if (focal_alliance_keys.length === 0) {
    // Edge case: focal has no non-empty alliance rows (e.g. AAP,
    // which carries 4 alliance="" rows). Return a no-op SQL that
    // produces zero rows. Empty IN-list would be a syntax error.
    return `
      SELECT NULL::VARCHAR AS event_id, NULL::VARCHAR AS state,
             NULL::VARCHAR AS alliance, NULL::VARCHAR AS party_id
      WHERE 1 = 0
    `;
  }
  // Build a literal VALUES list (event_id, state, alliance) the
  // outer SELECT JOINs against. Single-quote escaping is handled
  // by the caller (which has already passed safe values through
  // `.replace(/'/g, "''")`).
  const values_list = focal_alliance_keys
    .map(
      (k) => `('${k.event_id}', '${k.state}', '${k.alliance}')`,
    )
    .join(", ");
  return `
    WITH focal_keys(event_id, state, alliance) AS (
      VALUES ${values_list}
    )
    SELECT pa.event_id, pa.state, pa.alliance, pa.party_id
    FROM read_csv('${alliancesUrl}', ${alliancesClause}, header=true) pa
    JOIN focal_keys fk
      ON pa.event_id = fk.event_id
      AND pa.state = fk.state
      AND pa.alliance = fk.alliance
  `;
}

/** Pure: build the SQL that fetches seat counts from the party-page
 *  history mart for a specific set of (party_id, year, body) tuples.
 *  The result is per-(party_id, body, year, state) so the JS caller
 *  can:
 *    - SUM across states for Parliament rows (state token = "IN" in
 *      the alliance ledger but the mart carries per-state rows).
 *    - Index by state for Assembly rows.
 *
 *  Uses a literal VALUES list of (party_id, year, body) triples and
 *  inner-joins the mart against it - cheaper than a giant OR-chain.
 *  CAST(SUM(seats) AS BIGINT) per the chronic DuckDB-WASM HUGEINT
 *  trap. Exported for vitest. */
export function buildSeatsSql(
  seat_lookups: { party_id: string; year: number; body: string }[],
  historyClause: string,
  historyUrl: string,
): string {
  if (seat_lookups.length === 0) {
    return `
      SELECT NULL::VARCHAR AS party_id, NULL::VARCHAR AS body,
             NULL::INTEGER AS year, NULL::VARCHAR AS state,
             NULL::BIGINT AS seats
      WHERE 1 = 0
    `;
  }
  const values_list = seat_lookups
    .map(
      (k) => `('${k.party_id}', ${k.year}, '${k.body}')`,
    )
    .join(", ");
  return `
    WITH lookups(party_id, year, body) AS (
      VALUES ${values_list}
    )
    SELECT h.party_id, h.body, h.year, h.state,
      CAST(SUM(h.seats) AS BIGINT) AS seats
    FROM read_csv('${historyUrl}', ${historyClause}, header=true) h
    JOIN lookups l
      ON h.party_id = l.party_id AND h.year = l.year AND h.body = l.body
    GROUP BY h.party_id, h.body, h.year, h.state
  `;
}

/** Pure: project the alliance + partner + seat rows into the final
 *  view-model shape.
 *
 *  Inputs:
 *    - focal_id: the focal party_id.
 *    - focal_rows: focal's own alliance ledger rows.
 *    - partner_rows: full alliance roster for every (event, state,
 *      alliance) the focal participates in (includes focal itself).
 *    - seat_map: (party_id, body, year, state) -> seats.
 *    - partyShortFromId: short-name resolver injected by caller.
 *    - stateNameFromSlug: state-name resolver injected by caller.
 *    - cutoff_year: optional render-time minimum polling year.
 *      Rows with `event_id`-derived year < cutoff_year are dropped
 *      from BOTH the Parliament pick and the per-state Assembly
 *      list (PR-11; see RECENCY_CAP_YEARS). Defaults to
 *      Number.NEGATIVE_INFINITY (no cap) for backward compatibility
 *      with vitest fixtures that pre-date the cap; production
 *      callers always pass a concrete year.
 *
 *  Outputs the PartyAllianceContext object the renderer consumes.
 *  Returns null when there is no useful data on either body. Exported
 *  for vitest. */
export function projectAllianceContext(
  focal_id: string,
  focal_rows: RawAllianceRow[],
  partner_rows: RawAllianceRow[],
  seat_map: Map<SeatLookupKey, number>,
  partyShortFromId: (party_id: string) => string | null,
  stateNameFromSlug: (slug: string) => string | null,
  cutoff_year?: number,
): PartyAllianceContext | null {
  const min_year = cutoff_year ?? Number.NEGATIVE_INFINITY;
  // Bucket focal rows by (body, state) - Parliament rows (state =
  // "IN") collapse to one bucket; per-state Assembly rows bucket by
  // state. Within each bucket pick the row with MAX event_id (lex
  // sort works for "general-YYYY" and "assembly-YYYY" - both end
  // in 4-digit years).
  let parliament_pick: RawAllianceRow | null = null;
  const assembly_picks_by_state = new Map<string, RawAllianceRow>();
  for (const row of focal_rows) {
    if (!row.event_id || !row.state) continue;
    if (row.state === PARLIAMENT_STATE_TOKEN) {
      if (
        parliament_pick === null ||
        row.event_id > (parliament_pick.event_id ?? "")
      ) {
        parliament_pick = row;
      }
    } else {
      const existing = assembly_picks_by_state.get(row.state);
      if (!existing || row.event_id > (existing.event_id ?? "")) {
        assembly_picks_by_state.set(row.state, row);
      }
    }
  }
  // Index partner rows by (event_id, state, alliance) -> list of
  // party_ids in that alliance.
  const partners_by_key = new Map<string, string[]>();
  for (const row of partner_rows) {
    if (!row.event_id || !row.state || !row.alliance || !row.party_id) continue;
    const key = `${row.event_id}\u0001${row.state}\u0001${row.alliance}`;
    const list = partners_by_key.get(key) ?? [];
    list.push(row.party_id);
    partners_by_key.set(key, list);
  }
  // Build Parliament section.
  let parliament: PartyAllianceContextParliament | null = null;
  if (parliament_pick && parliament_pick.event_id) {
    const event_id = parliament_pick.event_id;
    const alliance_raw = parliament_pick.alliance ?? "";
    if (alliance_raw.length > 0) {
      const year = eventIdToYear(event_id) ?? 0;
      const partner_ids = (
        partners_by_key.get(
          `${event_id}\u0001${PARLIAMENT_STATE_TOKEN}\u0001${alliance_raw}`,
        ) ?? []
      ).filter((pid) => pid !== focal_id);
      // Parliament seat lookup sums across all states. The seat_map
      // is keyed per-state for the mart, so we sum here.
      const focal_seats = sumSeatsForParliament(
        seat_map,
        focal_id,
        year,
      );
      const partner_seats_by_id = new Map<string, number>();
      for (const pid of partner_ids) {
        partner_seats_by_id.set(
          pid,
          sumSeatsForParliament(seat_map, pid, year),
        );
      }
      const partner_seats = Array.from(partner_seats_by_id.values());
      const role = pickRoleFromSeats(focal_seats, partner_seats);
      // Top-N partner shorts by seats DESC, then by id ASC for
      // deterministic ordering when seat counts tie.
      const partner_names_top = Array.from(partner_seats_by_id.entries())
        .sort((a, b) => {
          if (b[1] !== a[1]) return b[1] - a[1];
          return a[0].localeCompare(b[0]);
        })
        .slice(0, MAX_PARTNER_NAMES)
        .map(([pid]) => partyShortFromId(pid) ?? pid);
      const total_alliance_seats =
        focal_seats +
        partner_seats.reduce((sum, s) => sum + s, 0);
      parliament = {
        event_label: parliamentEventLabel(event_id),
        event_id,
        alliance: stripAllianceYearSuffix(alliance_raw),
        role,
        partner_count: partner_ids.length,
        partner_names_top,
        total_alliance_seats,
      };
    }
    // alliance_raw === "" for Parliament: focal contested alone
    // nationally. We DROP the Parliament section in that case (the
    // "contested alone in Parliament" line is rarely meaningful for
    // the citizen and clutters the strip; the historical chart
    // already covers the standalone-LS narrative).
  }
  // PR-11 recency cap: drop the Parliament pick when its year is
  // older than the cutoff. The underlying alliance ledger row stays
  // in the CSV; the citizen surface just doesn't render it.
  if (parliament !== null) {
    const py = eventIdToYear(parliament.event_id) ?? 0;
    if (py < min_year) parliament = null;
  }
  // Build per-state Assembly sections.
  const state_assemblies: PartyAllianceContextStateAssembly[] = [];
  const sorted_states = Array.from(assembly_picks_by_state.entries()).sort(
    ([a], [b]) => a.localeCompare(b),
  );
  for (const [state_slug, pick] of sorted_states) {
    if (!pick.event_id) continue;
    const event_id = pick.event_id;
    const alliance_raw = pick.alliance ?? "";
    const year = eventIdToYear(event_id) ?? 0;
    // PR-11 recency cap: drop per-state Assembly rows older than
    // the cutoff. Same rule as Parliament above; mirrors the cap
    // applied to the Parliament pick so the strip is consistent
    // across both bodies.
    if (year < min_year) continue;
    const resolved_name = stateNameFromSlug(state_slug);
    const state_name =
      resolved_name && resolved_name.trim().length > 0
        ? resolved_name
        : titleCaseStateSlug(state_slug);
    const event_label = stateAssemblyEventLabel(state_name, event_id);
    if (alliance_raw.length === 0) {
      // Focal contested alone in this state.
      state_assemblies.push({
        state: state_slug,
        state_name,
        event_label,
        event_id,
        alliance: null,
        role: "alone",
        partner_count: 0,
        partner_names_top: [],
        total_alliance_seats:
          seat_map.get(
            seatLookupKey(focal_id, "assembly", year, state_slug),
          ) ?? 0,
      });
      continue;
    }
    const partner_ids = (
      partners_by_key.get(
        `${event_id}\u0001${state_slug}\u0001${alliance_raw}`,
      ) ?? []
    ).filter((pid) => pid !== focal_id);
    const focal_seats =
      seat_map.get(
        seatLookupKey(focal_id, "assembly", year, state_slug),
      ) ?? 0;
    const partner_seats_by_id = new Map<string, number>();
    for (const pid of partner_ids) {
      partner_seats_by_id.set(
        pid,
        seat_map.get(
          seatLookupKey(pid, "assembly", year, state_slug),
        ) ?? 0,
      );
    }
    const partner_seats = Array.from(partner_seats_by_id.values());
    const role = pickRoleFromSeats(focal_seats, partner_seats);
    const partner_names_top = Array.from(partner_seats_by_id.entries())
      .sort((a, b) => {
        if (b[1] !== a[1]) return b[1] - a[1];
        return a[0].localeCompare(b[0]);
      })
      .slice(0, MAX_PARTNER_NAMES)
      .map(([pid]) => partyShortFromId(pid) ?? pid);
    const total_alliance_seats =
      focal_seats + partner_seats.reduce((sum, s) => sum + s, 0);
    state_assemblies.push({
      state: state_slug,
      state_name,
      event_label,
      event_id,
      alliance: stripAllianceYearSuffix(alliance_raw),
      role,
      partner_count: partner_ids.length,
      partner_names_top,
      total_alliance_seats,
    });
  }
  if (parliament === null && state_assemblies.length === 0) return null;
  return { parliament, state_assemblies };
}

/** Helper: sum mart seat rows across all states for a (party, year)
 *  Parliament tuple. Returns 0 when no rows match (degraded seat data). */
function sumSeatsForParliament(
  seat_map: Map<SeatLookupKey, number>,
  party_id: string,
  year: number,
): number {
  // Parliament rows in the mart are per-state; the seat_map keys
  // are `${party_id}\u0001parliament\u0001${year}\u0001${state}`.
  // Iterate the prefix to sum across all states. The map is small
  // (~16 events x ~50 parties = O(800) entries) so the linear scan
  // is cheap.
  const prefix = `${party_id}\u0001parliament\u0001${year}\u0001`;
  let sum = 0;
  for (const [key, value] of seat_map) {
    if (key.startsWith(prefix)) sum += value;
  }
  return sum;
}

/** Module-level Promise cache, keyed by party_id. Mirrors the
 *  `strengthCache` pattern from `party-current-strength.ts`: repeated
 *  calls for the same party return the SAME Promise so the browser
 *  pays the corpus-fetch + DuckDB queries exactly once per tab. */
const allianceCache = new Map<
  string,
  Promise<PartyAllianceContext | null>
>();

/**
 * Load the per-party Alliance Context view-model. Returns null for:
 *   - Null / empty party_id (defensive).
 *   - Sentinel parties via `opts.is_sentinel` (NOTA, UNK).
 *   - Independent (parties.IN.IND) - independents don't form alliances.
 *   - Parties with no alliance rows AND no derivable state context.
 *
 * Party short names + state display names are resolved INSIDE the
 * loader by calling `loadAllPartiesMeta()` (parties.csv, Map cache)
 * + `fetchStates()` (entities.json projection, Map cache). Both are
 * one-time Promise-cached at module scope upstream, so the second
 * call on the same tab is free. Tests may inject explicit resolvers
 * via `opts.stateNameFromSlug` / `opts.partyShortFromId` to avoid
 * coupling vitest fixtures to the real DuckDB / fetch boundary -
 * when injected, the loader skips the meta + states fetches.
 *
 * Per the canonical-store loader pattern: the cache survives the
 * lifetime of the browser tab; only `__resetForTests` clears it.
 * A fetch failure clears that party's cache entry so a retry
 * re-issues the underlying queries.
 */
export function loadPartyAllianceContext(
  party_id: string | null | undefined,
  opts: {
    is_sentinel?: boolean;
    stateNameFromSlug?: (slug: string) => string | null;
    partyShortFromId?: (party_id: string) => string | null;
    /** Test-only: override the calendar year used to compute the
     *  PR-11 recency cap. Production omits this and the loader
     *  uses `new Date().getFullYear()`. */
    current_year?: number;
  } = {},
): Promise<PartyAllianceContext | null> {
  if (!party_id) return Promise.resolve(null);
  if (opts.is_sentinel) return Promise.resolve(null);
  if (party_id === INDEPENDENT_PARTY_ID) return Promise.resolve(null);
  const cached = allianceCache.get(party_id);
  if (cached) return cached;
  const promise = fetchPartyAllianceContext(
    party_id,
    opts.stateNameFromSlug ?? null,
    opts.partyShortFromId ?? null,
    opts.current_year ?? null,
  ).catch((err) => {
    allianceCache.delete(party_id);
    throw err;
  });
  allianceCache.set(party_id, promise);
  return promise;
}

async function fetchPartyAllianceContext(
  party_id: string,
  stateNameFromSlugOverride:
    | ((slug: string) => string | null)
    | null,
  partyShortFromIdOverride:
    | ((party_id: string) => string | null)
    | null,
  currentYearOverride: number | null,
): Promise<PartyAllianceContext | null> {
  // Resolve party + state name lookups. Tests inject explicit
  // resolvers; production builds the resolvers from the cached
  // metadata Maps. Both Maps are Promise-cached upstream so repeat
  // calls on the same tab pay only the first round trip.
  let partyShortFromId: (pid: string) => string | null;
  let stateNameFromSlug: (slug: string) => string | null;
  if (partyShortFromIdOverride && stateNameFromSlugOverride) {
    partyShortFromId = partyShortFromIdOverride;
    stateNameFromSlug = stateNameFromSlugOverride;
  } else {
    const [partiesMap, statesResp] = await Promise.all([
      partyShortFromIdOverride ? Promise.resolve(null) : loadAllPartiesMeta(),
      stateNameFromSlugOverride ? Promise.resolve(null) : fetchStates(),
    ]);
    partyShortFromId =
      partyShortFromIdOverride ??
      ((pid: string) => partiesMap!.get(pid)?.short ?? null);
    if (stateNameFromSlugOverride) {
      stateNameFromSlug = stateNameFromSlugOverride;
    } else {
      const slugToName = new Map<string, string>();
      for (const s of statesResp!.states) {
        slugToName.set(slugify(s.name), s.name);
      }
      stateNameFromSlug = (slug: string) => slugToName.get(slug) ?? null;
    }
  }

  await Promise.all([
    registerCsvFile(ALLIANCES_URL),
    registerCsvFile(PARTY_HISTORY_URL),
  ]);
  const [alliancesClause, historyClause] = await Promise.all([
    csvColumnsClause(ALLIANCES_REL),
    csvColumnsClause(PARTY_HISTORY_REL),
  ]);
  const safePartyId = party_id.replace(/'/g, "''");

  // Step 1: focal's own alliance ledger rows.
  const focalSql = buildFocalAllianceSql(
    safePartyId,
    alliancesClause,
    ALLIANCES_URL,
  );
  const focal_rows = await query<RawAllianceRow>(focalSql);
  if (focal_rows.length === 0) return null;

  // Step 2: determine partner keys = (event_id, state, alliance)
  // triples the focal participates in with a non-empty alliance.
  // Picks are MAX(event_id) per (body, state); the bucketing logic
  // mirrors `projectAllianceContext` so we only fetch partners for
  // the rows the projector will actually use. (Fetching partners
  // for the full focal_rows set would over-fetch when the focal
  // has multiple events per state - typical for assembly states
  // with several cycles in the ledger.)
  let parliament_pick: RawAllianceRow | null = null;
  const assembly_picks_by_state = new Map<string, RawAllianceRow>();
  for (const row of focal_rows) {
    if (!row.event_id || !row.state) continue;
    if (row.state === PARLIAMENT_STATE_TOKEN) {
      if (
        parliament_pick === null ||
        row.event_id > (parliament_pick.event_id ?? "")
      ) {
        parliament_pick = row;
      }
    } else {
      const existing = assembly_picks_by_state.get(row.state);
      if (!existing || row.event_id > (existing.event_id ?? "")) {
        assembly_picks_by_state.set(row.state, row);
      }
    }
  }
  const partner_keys: { event_id: string; state: string; alliance: string }[] =
    [];
  const picks: RawAllianceRow[] = [];
  if (parliament_pick) picks.push(parliament_pick);
  for (const [, pick] of assembly_picks_by_state) picks.push(pick);
  for (const pick of picks) {
    if (
      pick.event_id &&
      pick.state &&
      pick.alliance &&
      pick.alliance.length > 0
    ) {
      partner_keys.push({
        event_id: pick.event_id.replace(/'/g, "''"),
        state: pick.state.replace(/'/g, "''"),
        alliance: pick.alliance.replace(/'/g, "''"),
      });
    }
  }

  // Step 3: fetch partner rows (full roster per alliance the focal
  // is in, including focal itself). Skips the DuckDB round-trip
  // when the focal carries only alone rows (partner_keys empty).
  let partner_rows: RawAllianceRow[] = [];
  if (partner_keys.length > 0) {
    const partnerSql = buildPartnerAllianceSql(
      partner_keys,
      alliancesClause,
      ALLIANCES_URL,
    );
    partner_rows = await query<RawAllianceRow>(partnerSql);
  }

  // Step 4: assemble (party_id, year, body) seat-lookup tuples for
  // the focal + every partner across every pick. De-dup before
  // building the SQL so the VALUES list stays small.
  const seat_lookup_set = new Set<string>();
  const seat_lookups: { party_id: string; year: number; body: string }[] = [];
  function addSeatLookup(pid: string, year: number, body: string): void {
    const key = `${pid}\u0001${year}\u0001${body}`;
    if (seat_lookup_set.has(key)) return;
    seat_lookup_set.add(key);
    seat_lookups.push({
      party_id: pid.replace(/'/g, "''"),
      year,
      body,
    });
  }
  for (const pick of picks) {
    if (!pick.event_id || !pick.state) continue;
    const year = eventIdToYear(pick.event_id);
    if (year === null) continue;
    const body = pick.state === PARLIAMENT_STATE_TOKEN ? "parliament" : "assembly";
    // Always look up focal seats for the pick.
    addSeatLookup(party_id, year, body);
    // Look up seats for every party in the alliance (if non-empty).
    if (!pick.alliance || pick.alliance.length === 0) continue;
    const key = `${pick.event_id}\u0001${pick.state}\u0001${pick.alliance}`;
    const partners_in_alliance = partner_rows.filter(
      (r) =>
        r.event_id === pick.event_id &&
        r.state === pick.state &&
        r.alliance === pick.alliance &&
        r.party_id &&
        r.party_id !== party_id,
    );
    for (const pr of partners_in_alliance) {
      if (pr.party_id) addSeatLookup(pr.party_id, year, body);
    }
    void key;
  }

  // Step 5: fetch seat counts.
  let seat_rows: RawSeatsRow[] = [];
  if (seat_lookups.length > 0) {
    const seatsSql = buildSeatsSql(
      seat_lookups,
      historyClause,
      PARTY_HISTORY_URL,
    );
    seat_rows = await query<RawSeatsRow>(seatsSql);
  }

  // Step 6: build the (party_id, body, year, state) -> seats map.
  const seat_map = new Map<SeatLookupKey, number>();
  for (const row of seat_rows) {
    if (!row.party_id || !row.body || !row.state) continue;
    const year = intOrNull(row.year);
    if (year === null) continue;
    const seats = intOrNull(row.seats);
    if (seats === null) continue;
    if (row.body !== "parliament" && row.body !== "assembly") continue;
    seat_map.set(
      seatLookupKey(row.party_id, row.body, year, row.state),
      seats,
    );
  }

  return projectAllianceContext(
    party_id,
    focal_rows,
    partner_rows,
    seat_map,
    partyShortFromId,
    stateNameFromSlug,
    (currentYearOverride ?? new Date().getFullYear()) - RECENCY_CAP_YEARS,
  );
}

/** Test-only cache reset. NOT exported from index.ts. */
export function __resetForTests(): void {
  allianceCache.clear();
}

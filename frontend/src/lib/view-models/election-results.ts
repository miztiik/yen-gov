// Generic election-results view-model (PR-W2b of the election-experience
// overhaul plan, 2026-06-10).
//
// PR-W3c (2026-06-10): additive extension of the NATIONAL-PC dispatch to
// project `electors` + `votes_polled` from parliament summary.csv. The
// fields live on `ElectionResultRow` and are populated at NATIONAL-PC
// scope only (STATE-AC + CONSTITUENCY mappers pass null). Enables
// `NationalElection.svelte` to derive Total electors / Total polled /
// Turnout % KPIs from the same per-PC rows that drive the choropleth +
// top-parties bar, with no second loader call.
//
// Collapses three bespoke per-shape loaders behind ONE typed scope:
//
//   {event}                       -> NATIONAL-PC (parliament summary.csv,
//                                   one row per PC)
//   {event, state}                -> STATE-AC (assembly summary.csv +
//                                   candidacies winner-age JOIN, one row
//                                   per AC)
//   {event, state, eci_no}        -> CONSTITUENCY (assembly candidacies.csv
//                                   + summary.csv, one row per candidate)
//
// Output is a single UNION row shape; projection helpers narrow it to
// the bespoke-loader shapes when needed. See the golden-row oracle in
// `election-results.test.ts` for the per-scope equivalence proofs vs
// `loadNationalPcWinners` + `loadStateAcWinners` + `loadConstituencyResult`.
//
// Per the PR-W2b row in TODO/20260609-election-experience-overhaul-plan.md:
// this is LIBRARY-ONLY (no call-site flips). Bespoke loaders stay live;
// they are replaced one-by-one as call-sites flip (PR-W3b/c/d) and
// deleted in PR-W5a.
//
// What is OUT OF SCOPE for W2b:
//
//   * `loadIndiaLeadingParties` is NOT folded in. It reads a DIFFERENT
//     underlying table (the long-format party-aggregate CSV at
//     `data/datapoints/electoral/<state>_election_results.csv`,
//     entity_id LIKE `IN-<state>-<event>-PARTY-%`), takes a multi-event
//     map (`Record<state, event>`), and answers a structurally different
//     question (per-(state, event) party totals, not per-constituency
//     results). Folding it in would violate the brief's "use the SAME
//     underlying data source" rule. A future PR can either add a fourth
//     scope shape to this loader against the long-format table, or
//     leave it as a separate concern.
//
//   * Alias resolution (PR-W2a renamed event_ids in election_events.json
//     with event_id_aliases[] strangler). Not needed here: this loader
//     uses `event` for CSV-path building only (via `eventYear()` which
//     extracts the trailing 4-digit year from BOTH the legacy ECI form
//     and the new slug form). No SQL filter on `period_label` is applied,
//     so callers passing either form land on the same on-disk file.

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  assemblyCandidaciesPath,
  assemblySummaryPath,
  electoralEntitiesPath,
  parliamentSummaryPath,
} from "../canonical/election-csv-paths";
import { ECI_TO_LGD_SLUG } from "../boundaries/sources";

// Reverse lookup: LGD slug -> ECI code. The on-disk electoral.csv keys
// `state` in LGD form; tile-layout / GeoJSON `unique_id` props key in
// ECI form. Mirrors the same reverse map in `national-elections.ts`.
//
// Aliases for slug variants the canonical electoral.csv emits that do
// not match the LGD-form value in `ECI_TO_LGD_SLUG` verbatim. Each
// alias resolves to the same ECI state code as the canonical slug.
// Documented here (rather than in `ECI_TO_LGD_SLUG` itself) because
// that map's values feed `boundaries/in/panchayats/state=<slug>/...`
// and `boundaries/in/wards/state=<slug>/...` path constructors via
// `sources.ts` - on-disk those subtrees follow the LGD slug, so the
// canonical map must stay anchored on the LGD form. The alias overlay
// here is local to the election-results loader and only widens the
// `state_slug -> state_code` lookup for tile-cartogram joins.
//
// FU#1 (TODO/20260612-pc-choropleth-tile-and-party-filter-restoration-plan.md
// closure): "andaman-and-nicobar-islands" on electoral.csv aliases to
// the canonical "andaman-and-nicobar" entry under U01. Closes 1 of
// the 110 pending tiles surfaced by PR #958. The remaining 109 are
// publisher-side `eci_no=0` rows (Scenario C; backend ingest follow-up)
// and tile-layout drift on the data tier (Scenario C; tile-layout
// regen follow-up).
const EXTRA_SLUG_ALIASES: Readonly<Record<string, string>> = {
  "andaman-and-nicobar-islands": "U01",
};
const SLUG_TO_ECI: Readonly<Record<string, string>> = {
  ...Object.fromEntries(
    Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
  ),
  ...EXTRA_SLUG_ALIASES,
};

/** Scope of an election-results query.
 *
 *  Three valid shapes today (checked at dispatch):
 *    - `{event}`                 -> body inferred from event prefix;
 *                                   `general*` / `Ls*` -> all PCs nationally;
 *                                   `assembly*` / `Ac*` -> not yet supported
 *                                   (no national-AC bespoke loader exists).
 *    - `{event, state}`          -> all ACs in `state`; only valid for
 *                                   assembly events today.
 *    - `{event, state, eci_no}`  -> one constituency (all candidates);
 *                                   only valid for assembly events today.
 *
 *  `state` is the ECI state code (e.g. `"S22"`); the loader translates
 *  to the LGD slug via `electionStatePartition()` for CSV-path building
 *  and tracks both forms on the output row.
 */
export interface ElectionScope {
  event: string;
  state?: string;
  eci_no?: number;
}

/** Body of the election event (PC = parliamentary, AC = assembly). */
export type ElectionBody = "pc" | "ac";

/** Union row shape across all three scopes.
 *
 *  For winner-only scopes ({event} / {event, state}), the loader returns
 *  one row per entity; candidate-level fields carry the WINNER's data,
 *  `is_winner === true`, `position === 1`.
 *
 *  For drill-down scope ({event, state, eci_no}), the loader returns
 *  one row per candidate (1+ rows per entity); `is_winner === true`
 *  only for `position === 1`. Summary-level fields (margin_pct,
 *  turnout_pct) are duplicated across the candidate rows so each row
 *  is self-describing.
 */
export interface ElectionResultRow {
  entity_id: string;
  entity_kind: ElectionBody;
  entity_name: string;
  /** LGD slug (e.g. `"tamil-nadu"`). */
  state_slug: string;
  /** ECI state code (e.g. `"S22"`). */
  state_code: string;
  eci_no: number;
  delim_year: number;
  /** The event verbatim from `scope.event` (no alias resolution).
   *  CSVs do not carry a period_label column today (election year is
   *  partition-keyed via the file path); this field echoes the caller. */
  period_label: string;

  // Candidate-level:
  candidate_name: string | null;
  position: number | null;
  votes: number | null;
  vote_share_pct: number | null;
  is_winner: boolean;

  // Party-level (LEFT JOIN dim_parties / parties.csv):
  party_id: string | null;
  party_eci_code: string | null;
  party_short: string | null;
  party_short_raw: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: "high" | "medium" | "low" | null;
  symbol_asset_path: string | null;

  // Summary-level (per-entity; duplicated across candidate rows at
  // CONSTITUENCY scope):
  margin_pct: number | null;
  turnout_pct: number | null;
  /** Registered electors for the seat (W3c KPI strip input). Populated at
   *  NATIONAL-PC scope from parliament summary.csv.electors; null at
   *  STATE-AC + CONSTITUENCY scopes until the assembly SQL projects it.
   *  Long-tail PCs whose upstream omitted the figure also surface null. */
  electors: number | null;
  /** Votes polled for the seat (W3c KPI strip input). Populated at
   *  NATIONAL-PC scope from parliament summary.csv.votes_polled; same
   *  null-arm contract as `electors`. */
  votes_polled: number | null;
  /** Winner-runnerup absolute vote gap (TODO/20260612 plan Row B). Populated
   *  at NATIONAL-PC + STATE-AC scopes from summary.csv.margin_votes. CONSTITUENCY
   *  scope leaves it null - the per-candidate rows don't carry the seat-level
   *  gap; the scatter chart only consumes NATIONAL-PC + STATE-AC rows.
   *
   *  Drives the scatter chart's radius encoding (sqrt-area proportional to
   *  the absolute vote gap) per the Citizen + Max verdict on circle-size
   *  encoding: "how decisively was this seat won". */
  margin_votes: number | null;
  /** Winning candidate's age. Always null at NATIONAL-PC scope (the
   *  bespoke `loadNationalPcWinners` doesn't JOIN candidacies; F1.3b
   *  regression). Populated at STATE-AC + CONSTITUENCY scopes via the
   *  candidacies.csv LEFT JOIN on `(entity_id, candidate_name=winner_candidate, position=1)`. */
  winner_age: number | null;
  /** Display name of the winning candidate (mirrors summary.winner_candidate). */
  winner_candidate_name: string | null;
  /** SC / ST reservation status of the constituency, sourced from
   *  `datasets/data/entities/electoral.csv.reservation`. The on-disk
   *  column is empty for every row today (PR-W4c scatter audit); the
   *  loader maps NULL/empty to `"GEN"` so the scatter's reservation
   *  filter has a stable enum to render against. A future PR backfilling
   *  the column will start surfacing SC / ST verbatim with zero code
   *  changes. Projected at every scope. */
  reservation: "GEN" | "SC" | "ST";
}

/** Infer the election body from the event id / slug. */
export function bodyFromEvent(event: string): ElectionBody {
  if (event.startsWith("general")) return "pc";
  if (event.startsWith("assembly")) return "ac";
  // Legacy ECI forms (still valid input; PR-W2a alias strangler keeps
  // them addressable for one release).
  if (event.startsWith("Ls")) return "pc";
  if (event.startsWith("Ac")) return "ac";
  throw new Error(
    `election-results: cannot infer body from event "${event}" - expected prefix general/assembly/Ls/Ac`,
  );
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

const confidenceOrNull = (
  v: unknown,
): "high" | "medium" | "low" | null =>
  v === "high" || v === "medium" || v === "low" ? v : null;

const numOrNull = (v: unknown): number | null =>
  v == null ? null : Number(v);

/** Normalise the on-disk `reservation` cell to the closed enum the
 *  scatter chart (PR-W4c) consumes. Empty / null / unknown -> `"GEN"`
 *  (the on-disk column is empty for every row today, so this is the
 *  dominant arm). */
const reservationOrGen = (v: unknown): "GEN" | "SC" | "ST" => {
  if (typeof v !== "string") return "GEN";
  const trimmed = v.trim().toUpperCase();
  if (trimmed === "SC" || trimmed === "ST") return trimmed;
  return "GEN";
};

const stateCodeOf = (state_slug: string): string =>
  SLUG_TO_ECI[state_slug] ?? state_slug.toUpperCase();

/** Test-only re-export of the slug -> state-code lookup. The
 *  uppercase fallback is preserved verbatim for callers that pass
 *  unknown slugs (e.g. synthetic fixture states). Kept exported so the
 *  FU#1 alias regression test can pin the contract without poking at
 *  the loader's SQL path. */
export const _slugToStateCodeForTests = stateCodeOf;

interface NationalPcRow {
  entity_id: string;
  state_slug: string;
  eci_no: number | null;
  delim_year: number | null;
  entity_name: string;
  party_id: string | null;
  party_eci_code: string | null;
  party_short: string | null;
  party_short_raw: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  symbol_asset_path: string | null;
  margin_pct: number | null;
  turnout_pct: number | null;
  electors: number | null;
  votes_polled: number | null;
  /** Absolute vote gap (winner_votes - runnerup_votes); TODO/20260612 Row B
   *  adds this to both parliament + assembly SQL projections so the scatter
   *  chart's radius encoding can read it from the loader. */
  margin_votes: number | null;
  winner_candidate_name: string | null;
  /** Winner candidate's share of the votes_polled denominator (in
   *  percent). Projected at STATE-AC scope (PR-W4a) from
   *  summary.csv.winner_share_pct; null at NATIONAL-PC scope until
   *  the parliament SQL also selects it. */
  vote_share_pct?: number | null;
  /** Reservation literal from electoral.csv; nullable on the SQL row
   *  shape, normalised to `"GEN" | "SC" | "ST"` at mapping time. */
  reservation: string | null;
}

interface StateAcRow extends NationalPcRow {
  winner_age: number | null;
}

interface ConstituencyCandRow {
  entity_id: string;
  state_slug: string;
  eci_no: number | null;
  delim_year: number | null;
  entity_name: string;
  candidate_name: string | null;
  party_id: string | null;
  party_eci_code: string | null;
  party_short: string | null;
  party_short_raw: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  symbol_asset_path: string | null;
  position: number | null;
  votes: number | null;
  vote_share_pct: number | null;
  age: number | null;
  reservation: string | null;
}

interface ConstituencySummaryRow {
  margin_pct: number | null;
  turnout_pct: number | null;
  winner_candidate: string | null;
  winner_age: number | null;
}

// -------------------- NATIONAL-PC dispatch --------------------

async function runNationalPcQuery(
  event: string,
): Promise<ElectionResultRow[]> {
  const sumPath = parliamentSummaryPath(event);
  const electoralPath = electoralEntitiesPath();
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;

  const [sumClause, electoralClause] = await Promise.all([
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
    registerCsvFile(sumUrl),
    registerCsvFile(electoralUrl),
    registerCsvAsTable("elections.dim_parties"),
  ]);

  // One row per PC. LEFT JOIN dim_parties so an UNK winner_party_id
  // still emits a row with null brand metadata. PR-W3c (2026-06-10):
  // additive projection of `electors` + `votes_polled` so the National
  // event view can derive the citizen-facing Total electors / Total
  // polled KPIs directly from the per-PC rows. PR-W4a (2026-06-10):
  // additive projection of `winner_share_pct` so the constituency-
  // history bar in `frontend/src/lib/elections/ConstituencyHistoryBar.svelte`
  // can render per-event winner vote-share bars at NATIONAL-PC scope
  // (mirrors the STATE-AC arm extended in W3b). PR-W4c (2026-06-10):
  // additive projection of `reservation` so the scatter chart's
  // reservation filter chip can narrow rows without a second loader.
  // TODO/20260612 Row B: additive projection of `margin_votes` so the
  // scatter chart's radius encoding can swap from electors -> absolute
  // vote gap (Citizen + Max verdict: tells the close-vs-walkover story).
  const sql = `
    SELECT
      e.entity_id                   AS entity_id,
      e.state                       AS state_slug,
      e.eci_no                      AS eci_no,
      e.delim_year                  AS delim_year,
      e.name                        AS entity_name,
      e.reservation                 AS reservation,
      s.winner_party_id             AS party_id,
      dp.eci_code                   AS party_eci_code,
      dp.short_name                 AS party_short,
      s.winner_party_short_raw      AS party_short_raw,
      dp.brand_colour_hex           AS brand_colour_hex,
      dp.brand_colour_confidence    AS brand_colour_confidence,
      dp.election_symbol_asset_path AS symbol_asset_path,
      s.margin_pct                  AS margin_pct,
      s.turnout_pct                 AS turnout_pct,
      s.electors                    AS electors,
      s.votes_polled                AS votes_polled,
      s.margin_votes                AS margin_votes,
      s.winner_share_pct            AS vote_share_pct,
      s.winner_candidate            AS winner_candidate_name
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'pc'
    LEFT JOIN dim_parties dp ON dp.party_id = s.winner_party_id
  `;
  const rows = await query<NationalPcRow>(sql);
  return rows
    .filter((r) => r.eci_no != null && r.margin_pct != null)
    .map((r) => toRow(r, event, "pc", null));
}

// -------------------- STATE-AC dispatch --------------------

async function runStateAcQuery(
  event: string,
  state_code: string,
): Promise<ElectionResultRow[]> {
  const candPath = assemblyCandidaciesPath(state_code, event);
  const sumPath = assemblySummaryPath(state_code, event);
  const electoralPath = electoralEntitiesPath();
  const candUrl = `${DATA_BASE}/${candPath.replace(/^datasets\//, "")}`;
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;

  const [candClause, sumClause, electoralClause] = await Promise.all([
    csvColumnsClause(candPath),
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
    registerCsvFile(candUrl),
    registerCsvFile(sumUrl),
    registerCsvFile(electoralUrl),
    registerCsvAsTable("elections.dim_parties"),
  ]);

  // One row per AC. Mirror of `loadStateAcWinners` SQL: winner-age via
  // LEFT JOIN on (entity_id, candidate_name=winner_candidate, position=1).
  // PR-W3b (2026-06-10): additive projection of `electors` + `votes_polled`
  // + `vote_share_pct` so the state event view's KPI strip + constituency
  // table can read them from the same per-AC rows (mirroring the
  // NATIONAL-PC arm extended in W3c). PR-W4c (2026-06-10): additive
  // projection of `reservation` for the scatter filter chip.
  // TODO/20260612 Row B: additive projection of `margin_votes` so the
  // scatter chart's radius encoding can swap from electors -> absolute
  // vote gap on state-event surfaces as well.
  const sql = `
    SELECT
      e.entity_id                           AS entity_id,
      e.state                               AS state_slug,
      e.eci_no                              AS eci_no,
      e.delim_year                          AS delim_year,
      e.name                                AS entity_name,
      e.reservation                         AS reservation,
      s.winner_party_id                     AS party_id,
      dp.eci_code                           AS party_eci_code,
      dp.short_name                         AS party_short,
      s.winner_party_short_raw              AS party_short_raw,
      dp.brand_colour_hex                   AS brand_colour_hex,
      dp.brand_colour_confidence            AS brand_colour_confidence,
      dp.election_symbol_asset_path         AS symbol_asset_path,
      s.margin_pct                          AS margin_pct,
      s.turnout_pct                         AS turnout_pct,
      s.electors                            AS electors,
      s.votes_polled                        AS votes_polled,
      s.margin_votes                        AS margin_votes,
      s.winner_share_pct                    AS vote_share_pct,
      ec.age                                AS winner_age,
      s.winner_candidate                    AS winner_candidate_name
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN read_csv('${candUrl}', ${candClause}) ec
      ON ec.entity_id = s.entity_id
     AND ec.candidate_name = s.winner_candidate
     AND ec.position = 1
    LEFT JOIN dim_parties dp ON dp.party_id = s.winner_party_id
    ORDER BY e.eci_no
  `;
  const rows = await query<StateAcRow>(sql);
  return rows
    .filter((r) => r.eci_no != null && r.margin_pct != null)
    .map((r) => toRow(r, event, "ac", r.winner_age));
}

// -------------------- CONSTITUENCY dispatch --------------------

async function runConstituencyQuery(
  event: string,
  state_code: string,
  eci_no: number,
): Promise<ElectionResultRow[]> {
  const candPath = assemblyCandidaciesPath(state_code, event);
  const sumPath = assemblySummaryPath(state_code, event);
  const electoralPath = electoralEntitiesPath();
  const candUrl = `${DATA_BASE}/${candPath.replace(/^datasets\//, "")}`;
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;

  const [candClause, sumClause, electoralClause] = await Promise.all([
    csvColumnsClause(candPath),
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
    registerCsvFile(candUrl),
    registerCsvFile(sumUrl),
    registerCsvFile(electoralUrl),
    registerCsvAsTable("elections.dim_parties"),
  ]);

  const eciLit = String(Number(eci_no));

  // Query 1: per-candidate rows for the AC. Mirror of
  // `loadConstituencyResult`'s candidatesSql but without the state-slug
  // WHERE (the entity_id JOIN to electoral.csv already pins state/eci_no
  // when combined with the explicit WHERE below). PR-W4c (2026-06-10):
  // additive projection of `reservation` so a downstream consumer
  // (today: none; tomorrow: a per-candidate scatter facet) has
  // symmetry with the NATIONAL-PC + STATE-AC arms.
  const candidatesSql = `
    SELECT
      e.entity_id                   AS entity_id,
      e.state                       AS state_slug,
      e.eci_no                      AS eci_no,
      e.delim_year                  AS delim_year,
      e.name                        AS entity_name,
      e.reservation                 AS reservation,
      ec.candidate_name             AS candidate_name,
      ec.party_id                   AS party_id,
      dp.eci_code                   AS party_eci_code,
      dp.short_name                 AS party_short,
      ec.party_short_raw            AS party_short_raw,
      dp.brand_colour_hex           AS brand_colour_hex,
      dp.brand_colour_confidence    AS brand_colour_confidence,
      dp.election_symbol_asset_path AS symbol_asset_path,
      ec.position                   AS position,
      ec.votes                      AS votes,
      ec.vote_share_pct             AS vote_share_pct,
      ec.age                        AS age
    FROM read_csv('${candUrl}', ${candClause}) ec
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = ec.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
    WHERE e.eci_no = ${eciLit}
    ORDER BY ec.position
  `;
  const candidates = await query<ConstituencyCandRow>(candidatesSql);
  if (candidates.length === 0) return [];

  // Query 2: AC summary (one row per AC). Lift margin_pct + turnout_pct +
  // winner_age onto every candidate row so each row is self-describing.
  const summarySql = `
    SELECT
      s.margin_pct                  AS margin_pct,
      s.turnout_pct                 AS turnout_pct,
      s.winner_candidate            AS winner_candidate,
      ec.age                        AS winner_age
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN read_csv('${candUrl}', ${candClause}) ec
      ON ec.entity_id = s.entity_id
     AND ec.candidate_name = s.winner_candidate
     AND ec.position = 1
    WHERE e.eci_no = ${eciLit}
    LIMIT 1
  `;
  const summaryRows = await query<ConstituencySummaryRow>(summarySql);
  const summary = summaryRows[0] ?? null;

  return candidates.map((r) => ({
    entity_id: r.entity_id,
    entity_kind: "ac" as const,
    entity_name: r.entity_name ?? "",
    state_slug: String(r.state_slug ?? ""),
    state_code: stateCodeOf(String(r.state_slug ?? "")),
    eci_no: Number(r.eci_no ?? 0),
    delim_year: Number(r.delim_year ?? 2008),
    period_label: event,
    candidate_name: r.candidate_name ?? null,
    position: r.position == null ? null : Number(r.position),
    votes: numOrNull(r.votes),
    vote_share_pct: numOrNull(r.vote_share_pct),
    is_winner: Number(r.position ?? 0) === 1,
    party_id: r.party_id ?? null,
    party_eci_code: r.party_eci_code ?? null,
    party_short: r.party_short ?? null,
    party_short_raw: r.party_short_raw ?? null,
    brand_colour_hex: r.brand_colour_hex ?? null,
    brand_colour_confidence: confidenceOrNull(r.brand_colour_confidence),
    symbol_asset_path: r.symbol_asset_path ?? null,
    margin_pct: numOrNull(summary?.margin_pct),
    turnout_pct: numOrNull(summary?.turnout_pct),
    // CONSTITUENCY scope does not project electors / votes_polled today;
    // they live on the assembly summary.csv but the assembly SQL doesn't
    // SELECT them (W3c only needs the NATIONAL-PC arm to surface KPIs).
    electors: null,
    votes_polled: null,
    // CONSTITUENCY scope: same rationale - per-candidate rows surface the
    // seat-level margin_votes nowhere today; the scatter consumers only
    // read NATIONAL-PC + STATE-AC rows.
    margin_votes: null,
    winner_age: numOrNull(summary?.winner_age),
    winner_candidate_name: summary?.winner_candidate ?? null,
    reservation: reservationOrGen(r.reservation),
  }));
}

// -------------------- shared row mapper (winner-only scopes) --------------------

function toRow(
  r: NationalPcRow & { electors?: number | null; votes_polled?: number | null; margin_votes?: number | null },
  event: string,
  body: ElectionBody,
  winner_age: number | null,
): ElectionResultRow {
  const state_slug = String(r.state_slug ?? "");
  return {
    entity_id: r.entity_id,
    entity_kind: body,
    entity_name: r.entity_name ?? "",
    state_slug,
    state_code: stateCodeOf(state_slug),
    eci_no: Number(r.eci_no ?? 0),
    delim_year: Number(r.delim_year ?? 2008),
    period_label: event,
    candidate_name: r.winner_candidate_name ?? null,
    position: 1,
    votes: null, // not projected at winner-only scopes
    vote_share_pct: numOrNull(r.vote_share_pct),
    is_winner: true,
    party_id: r.party_id ?? null,
    party_eci_code: r.party_eci_code ?? null,
    party_short: r.party_short ?? null,
    party_short_raw: r.party_short_raw ?? null,
    brand_colour_hex: r.brand_colour_hex ?? null,
    brand_colour_confidence: confidenceOrNull(r.brand_colour_confidence),
    symbol_asset_path: r.symbol_asset_path ?? null,
    margin_pct: numOrNull(r.margin_pct),
    turnout_pct: numOrNull(r.turnout_pct),
    electors: numOrNull(r.electors),
    votes_polled: numOrNull(r.votes_polled),
    margin_votes: numOrNull(r.margin_votes),
    winner_age,
    winner_candidate_name: r.winner_candidate_name ?? null,
    reservation: reservationOrGen(r.reservation),
  };
}

// -------------------- public API --------------------

/** Single generic loader.
 *
 *  Dispatches on which scope keys are present; returns LoaderResult-wrapped
 *  rows in the union shape. `partial / not_published` is returned with an
 *  empty data array when the scope resolves to zero rows (analogous to the
 *  bespoke loaders' partial arm).
 */
export async function loadElectionResults(
  scope: ElectionScope,
): Promise<LoaderResult<ElectionResultRow[]>> {
  try {
    const body = bodyFromEvent(scope.event);
    let rows: ElectionResultRow[];
    if (scope.state !== undefined && scope.eci_no !== undefined) {
      if (body !== "ac") {
        throw new Error(
          `election-results: constituency-scope drill-down is only supported for assembly events (got "${scope.event}")`,
        );
      }
      rows = await runConstituencyQuery(
        scope.event,
        scope.state,
        scope.eci_no,
      );
    } else if (scope.state !== undefined) {
      if (body !== "ac") {
        throw new Error(
          `election-results: state-scope is only supported for assembly events (got "${scope.event}")`,
        );
      }
      rows = await runStateAcQuery(scope.event, scope.state);
    } else if (scope.eci_no !== undefined) {
      throw new Error(
        "election-results: eci_no scope requires `state` to be set",
      );
    } else {
      if (body !== "pc") {
        throw new Error(
          `election-results: national scope is only supported for parliament events today (got "${scope.event}")`,
        );
      }
      rows = await runNationalPcQuery(scope.event);
    }
    if (rows.length === 0) {
      return { status: "partial", data: [], reason: "not_published" };
    }
    return { status: "ok", data: rows };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadElectionResults(scope),
    };
  }
}

/** Sort as (entity_id ASC, position ASC NULLS LAST). For drill-down scopes
 *  this surfaces the natural ranked order (winner first). For winner-only
 *  scopes it is a stable per-entity sort with position=1 across the board. */
export function projectAsConstituencyRanks(
  rows: readonly ElectionResultRow[],
): ElectionResultRow[] {
  return [...rows].sort((a, b) => {
    if (a.entity_id !== b.entity_id) {
      return a.entity_id < b.entity_id ? -1 : 1;
    }
    const ap = a.position ?? Number.POSITIVE_INFINITY;
    const bp = b.position ?? Number.POSITIVE_INFINITY;
    return ap - bp;
  });
}

/** Drops non-winners. For winner-only scopes (NATIONAL-PC / STATE-AC) this
 *  is identity (every row already has `is_winner === true`); for drill-down
 *  scope it returns just the winner row. */
export function projectAsWinnersByEntity(
  rows: readonly ElectionResultRow[],
): ElectionResultRow[] {
  return rows.filter((r) => r.is_winner);
}

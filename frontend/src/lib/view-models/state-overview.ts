// Citizen view-model loader for the StateOverview route (PR-F / Phase 1.3b).
//
// Reads the canonical Parquet store via DuckDB-WASM (see lib/duckdb.ts) and
// assembles a state-hub view-model — party totals + state totals + sources —
// to replace the per-shard `result.summary.json` projection for the
// StateOverview surface. PR-G (Phase 1.3c) routes Party.svelte's summary side
// here, plus migrated ElectionSeatsTrend, IndiaMap, and Settings onto their
// own dedicated view-model loaders; `fetchResultSummary` was deleted.
// PR-H (Phase 1.3d) extends the party JOIN with `dim_party_alliances` so
// `PartyTotals` carries `recognition` (from dim_parties) and per-event
// `alliance` (from dim_party_alliances). Party.svelte now derives party_meta
// from this single loader and `fetchParties` is gone.
// PR-I (Phase 1.4) adds `ac_winners[]` to the view-model — per-AC winning
// party + margin assembled from `ac-winner-party-id` + `ac-margin-pct`
// observations joined to `dim_acs` + `dim_parties`. StateOverview's per-AC
// badges and `MarginHistogram` now consume this slice; both surfaces drop
// their `results.sqlite` queries.
//
// What is JOINed:
//   elections.election_results     — numeric facts (party-* + state-* indicators)
//   elections.dim_parties          — party identity (short_name, full_name, eci_code, recognition)
//   elections.dim_party_alliances  — per-event alliance (LEFT JOIN on (party_id, period_label))
//   taxonomy.sources               — provenance URLs (citation-ledger v2.0)
//
// Party JOIN key: entity_id is `IN-<state>-<event>-PARTY-<short_name>`, so
// `regexp_extract(entity_id, '-PARTY-(.+)$', 1) = dim_parties.short_name`.
// LEFT JOIN so parties without a dim row still render with their extracted
// short_name (a recognised gap in the current dim_parties seed). The alliance
// LEFT JOIN then keys on dim_parties.party_id; parties without a dim row OR
// without an alliance_history entry for the event surface alliance=NULL.
//
// LoaderResult arms (mirror PR-E / constituency.ts):
//   ok       — JOIN produced 1+ party rows; full StateOverviewViewModel.
//   partial  — zero party rows for (state, event) — the cohort is not yet
//              ingested into the canonical store. Returns a skeleton +
//              reason="not_published" so the route can render an empty-state.
//   failed   — DuckDB-WASM / fetch / SQL error; `describeFailure` maps to
//              citizen-readable copy + a retry callable.

import {
  describeFailure,
  type LoaderResult,
} from "../loader-result";
import { query, registerSlice, registerTable } from "../duckdb";
import { electionStatePartition } from "../election-partitions";
import type { PartyTotals, SourceRef } from "../data";
import {
  verificationMethodRank,
  type SourceV2Row,
} from "../source-list-v2";

// View-model shape. Distinct from the legacy `ResultSummary` (which other
// routes still consume): `body` is elided — StateOverview never reads it.
// `party_totals` reuses the legacy `PartyTotals` shape so PartyBar /
// SeatDonut / the party directory render with zero prop changes. PR-I adds
// `ac_winners[]` so the per-AC winning party + margin can flow through one
// loader; StateAcMap still has its own getDb path (Phase 1.5).
export interface AcWinner {
  ac_eci_no: number;
  ac_name: string;
  /** PR-SYM-6d: canonical `parties.IN.<SLUG>`. Render code calls
   *  `getPartyColor(party_id, row)` — the resolver picks anchor /
   *  Wikipedia brand_colour / algorithmic-fallback off this key. */
  party_id: string;
  party_eci_code: string | null;
  party_short: string;
  margin_pct: number;
  // PR-B8 colour-by modes. Both are nullable/optional: turnout is
  // conditionally emitted per event and winner age is affidavit-sourced
  // (dense ~2004+, null for older events). Coverage is gated downstream.
  turnout_pct?: number | null;
  winner_age?: number | null;
  /** Winning candidate's display name (dim_persons.display_name). Null when
   *  the affidavit/candidacy join missed or upstream omitted the name. */
  winner_candidate_name?: string | null;
  /** Winning party's election-symbol asset path, root-relative
   *  (e.g. "party-symbols/rising-sun.svg"), from
   *  dim_parties.election_symbol_asset_path. Null when the party has no
   *  verified symbol asset (most parties) — the tooltip medallion then
   *  degrades silently. */
  symbol_asset_path?: string | null;
  // PR-SYM-6d additive brand_colour mirror (from dim_parties v1.1).
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
}

export interface StateOverviewViewModel {
  election: string;
  state: string;
  total_seats: number;
  totals: {
    electors?: number;
    votes_polled?: number;
    turnout_pct?: number;
  } | null;
  party_totals: PartyTotals[];
  ac_winners: AcWinner[];
  /** Legacy provenance shape — fetch-telemetry-bearing `SourceRef` for the
   *  v1 `SourceList.svelte` consumer. Filtered to rows that publish a live
   *  `url_main` (the only field v1 renders). Empty `fetched_at` per
   *  ADR-0032 P.0e — fetch telemetry left the canonical contract. */
  sources: SourceRef[];
  /** v2.0 ledger rows (`taxonomy.sources` per ADR-0032). Carries the full
   *  citizen-facing citation identity + trust signals. Includes rows with
   *  null `url_main` (archived-snapshot / transcribed / editorial) which
   *  the legacy `sources` array drops by design. Consumed by the v2
   *  `SourceListV2.svelte` render surface (Phase 1.4 of the chart-plan).
   *  R-24: NO fetch-telemetry fields are carried here. R-28: the JOIN
   *  resolves `taxonomy.sources` via `registerTable`, never a hardcoded
   *  literal path. */
  sources_v2: SourceV2Row[];
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface PartyRow {
  short_name_key: string;
  short_name: string | null;
  full_name: string | null;
  eci_code: string | null;
  recognition: string | null;
  alliance: string | null;
  // PR-SYM-6f1: project dim_parties.party_id + brand_colour_* through to
  // PartyTotals so SeatDonut (and follow-up consumers) can call
  // getPartyColor(party_id, row) off the existing dim_parties LEFT JOIN.
  party_id: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  seats_contested: number | null;
  seats_won: number | null;
  votes: number | null;
  vote_share_pct: number | null;
}

interface StateScopeRow {
  indicator_id: string;
  value_numeric: number | null;
}

interface SourceJoinRow {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  license: SourceV2Row["license"];
  confidence_tier: SourceV2Row["confidence_tier"];
  is_issuing_authority: boolean;
  verification_method: SourceV2Row["verification_method"];
  url_main: string | null;
  citation_full: string | null;
  notes: string | null;
}

interface AcWinnerRow {
  ac_eci_no: number | null;
  ac_name: string | null;
  party_id: string | null;
  party_eci_code: string | null;
  party_short: string | null;
  margin_pct: number | null;
  turnout_pct: number | null;
  winner_age: number | null;
  winner_candidate_name: string | null;
  symbol_asset_path: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
}

const num = (v: unknown): number => (v == null ? 0 : Number(v));
const numOrUndef = (v: unknown): number | undefined =>
  v == null ? undefined : Number(v);

async function runQueries(
  event: string,
  state_code: string,
): Promise<{
  parties: PartyRow[];
  stateScope: StateScopeRow[];
  sources: SourceJoinRow[];
  acWinners: AcWinnerRow[];
}> {
  await Promise.all([
    registerSlice("elections.election_results", { state: electionStatePartition(state_code) }),
    registerTable("elections.dim_parties"),
    registerTable("elections.dim_party_alliances"),
    registerTable("elections.dim_acs"),
    // PR #525 (PR-B8) extended queryAcWinners with turnout + winner-age,
    // which LEFT JOIN elections_candidacies + dim_persons. runQueries calls
    // queryAcWinners, so it must register those two tables too — otherwise
    // DuckDB throws "table does not exist", loadStateOverview returns
    // `failed`, and the whole summary-gated block (map, donut, seats-by-party,
    // seat-composition trend) silently disappears. loadStateAcWinners already
    // registers them; this keeps the two queryAcWinners callers in sync.
    registerTable("elections.elections_candidacies"),
    registerTable("elections.dim_persons"),
    registerTable("taxonomy.sources"),
  ]);

  const evt = sqlString(event);
  const sc = sqlString(state_code);
  const partyPrefix = sqlString(`IN-${state_code}-${event}-PARTY-`);
  const statePrefix = sqlString(`IN-${state_code}-`);
  const stateEntity = sqlString(`IN-${state_code}-${event}`);

  // Pivot the four party-* indicators with MAX(CASE WHEN ...). LEFT JOIN to
  // dim_parties on the extracted short_name so unmatched parties still
  // render (e.g. dim_parties currently has no row for CPIM).
  const partySql = `
    SELECT
      regexp_extract(o.entity_id, '-PARTY-(.+)$', 1) AS short_name_key,
      dp.short_name              AS short_name,
      dp.full_name               AS full_name,
      dp.eci_code                AS eci_code,
      dp.recognition             AS recognition,
      dpa.alliance               AS alliance,
      dp.party_id                AS party_id,
      dp.brand_colour_hex        AS brand_colour_hex,
      dp.brand_colour_confidence AS brand_colour_confidence,
      MAX(CASE WHEN o.indicator_id = 'party-contested-acs'  THEN o.value_numeric END) AS seats_contested,
      MAX(CASE WHEN o.indicator_id = 'party-seats-won'      THEN o.value_numeric END) AS seats_won,
      MAX(CASE WHEN o.indicator_id = 'party-votes-polled'   THEN o.value_numeric END) AS votes,
      MAX(CASE WHEN o.indicator_id = 'party-vote-share-pct' THEN o.value_numeric END) AS vote_share_pct
    FROM election_results o
    LEFT JOIN dim_parties dp
      ON dp.short_name = regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)
    LEFT JOIN dim_party_alliances dpa
      ON dpa.party_id = dp.party_id
      AND dpa.period_label = ${evt}
    WHERE o.entity_id LIKE ${partyPrefix} || '%'
      AND o.period_label = ${evt}
      AND o.indicator_id IN (
        'party-contested-acs',
        'party-seats-won',
        'party-votes-polled',
        'party-vote-share-pct'
      )
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
  `;
  const parties = await query<PartyRow>(partySql);

  if (parties.length === 0) {
    return { parties, stateScope: [], sources: [], acWinners: [] };
  }

  const stateScope = await query<StateScopeRow>(`
    SELECT indicator_id, value_numeric
    FROM election_results
    WHERE entity_id = ${stateEntity}
      AND period_label = ${evt}
      AND indicator_id IN (
        'electors-total',
        'votes-polled',
        'turnout-pct'
      )
  `);

  // Pull the FULL v2.0 ledger row, not just url_main — so the v2 footer
  // surface (SourceListV2.svelte) can read producer / title / vintage /
  // license / confidence_tier / verification_method / etc. without a
  // second round-trip. The `WHERE s.url_main IS NOT NULL` filter that v1
  // carried is intentionally DROPPED — v2.0 rows with null url_main
  // (archived-snapshot / transcribed / editorial per ADR-0032) are valid
  // citations that the v2 surface renders fully. The legacy `sources:
  // SourceRef[]` assembly downstream still filters by url_main truthiness
  // so the v1 surface keeps its existing semantics.
  const sources = await query<SourceJoinRow>(`
    SELECT DISTINCT
      s.source_id,
      s.producer,
      s.title,
      s.vintage,
      s.license,
      s.confidence_tier,
      s.is_issuing_authority,
      s.verification_method,
      s.url_main,
      s.citation_full,
      s.notes
    FROM election_results o
    JOIN sources s ON s.source_id = o.source_id
    WHERE o.period_label = ${evt}
      AND o.entity_id LIKE ${statePrefix} || '%'
    ORDER BY s.source_id
  `);

  const acWinners = await queryAcWinners(evt, sc);

  return { parties, stateScope, sources, acWinners };
}

// Per-AC winners + margin. AC observations use entity_id pattern
// `IN-<state>-AC-<delim_year>-<eci_no>` (no event in the id; period_label
// distinguishes events). `ac-winner-party-id` carries the winning party_id
// in value_text; `ac-margin-pct` carries the margin in value_numeric. We
// pivot via two CTEs and join to dim_acs (for eci_no + name) and
// dim_parties (for the citizen-visible short_name + eci_code).
//
// Extracted so `loadStateAcWinners` can reuse it for the Constituency route's
// state-map context without paying for the party/scope/sources queries
// `loadStateOverview` also runs.
async function queryAcWinners(
  evtLiteral: string,
  stateLiteral: string,
): Promise<AcWinnerRow[]> {
  return query<AcWinnerRow>(`
    WITH winner AS (
      SELECT entity_id AS ac_id, value_text AS party_id
      FROM election_results
      WHERE indicator_id = 'ac-winner-party-id'
        AND period_label = ${evtLiteral}
        AND entity_id LIKE 'IN-' || ${stateLiteral} || '-AC-%'
    ),
    margin AS (
      SELECT entity_id AS ac_id, value_numeric AS margin_pct
      FROM election_results
      WHERE indicator_id = 'ac-margin-pct'
        AND period_label = ${evtLiteral}
        AND entity_id LIKE 'IN-' || ${stateLiteral} || '-AC-%'
    ),
    turnout AS (
      SELECT entity_id AS ac_id, value_numeric AS turnout_pct
      FROM election_results
      WHERE indicator_id = 'ac-turnout-pct'
        AND period_label = ${evtLiteral}
        AND entity_id LIKE 'IN-' || ${stateLiteral} || '-AC-%'
    ),
    winner_cand AS (
      SELECT entity_id AS ac_id, value_text AS candidacy_key
      FROM election_results
      WHERE indicator_id = 'ac-winner-candidate-id'
        AND period_label = ${evtLiteral}
        AND entity_id LIKE 'IN-' || ${stateLiteral} || '-AC-%'
    )
    SELECT da.eci_no                  AS ac_eci_no,
           da.name                    AS ac_name,
           w.party_id                 AS party_id,
           dp.eci_code                AS party_eci_code,
           dp.short_name              AS party_short,
           dp.brand_colour_hex        AS brand_colour_hex,
           dp.brand_colour_confidence AS brand_colour_confidence,
           dp.election_symbol_asset_path AS symbol_asset_path,
           m.margin_pct               AS margin_pct,
           t.turnout_pct              AS turnout_pct,
           per.age                    AS winner_age,
           per.display_name           AS winner_candidate_name
    FROM winner w
    JOIN margin m ON m.ac_id = w.ac_id
    JOIN dim_acs da ON da.ac_id = w.ac_id
    LEFT JOIN dim_parties dp ON dp.party_id = w.party_id
    LEFT JOIN turnout t ON t.ac_id = w.ac_id
    LEFT JOIN winner_cand wc ON wc.ac_id = w.ac_id
    LEFT JOIN elections_candidacies ec ON ec.candidacy_key = wc.candidacy_key
    LEFT JOIN dim_persons per ON per.person_id = ec.person_id
  `);
}

function toAcWinners(rows: AcWinnerRow[]): AcWinner[] {
  return rows
    .filter((r) => r.ac_eci_no != null && r.margin_pct != null)
    .map((r) => ({
      ac_eci_no: Number(r.ac_eci_no),
      ac_name: r.ac_name ?? "",
      party_id: r.party_id ?? "parties.IN.UNK",
      party_eci_code: r.party_eci_code ?? null,
      party_short: r.party_short ?? "",
      margin_pct: Number(r.margin_pct),
      turnout_pct: r.turnout_pct == null ? null : Number(r.turnout_pct),
      winner_age: r.winner_age == null ? null : Number(r.winner_age),
      winner_candidate_name: r.winner_candidate_name ?? null,
      symbol_asset_path: r.symbol_asset_path ?? null,
      brand_colour_hex: r.brand_colour_hex ?? null,
      brand_colour_confidence:
        r.brand_colour_confidence === "high" ||
        r.brand_colour_confidence === "medium" ||
        r.brand_colour_confidence === "low"
          ? r.brand_colour_confidence
          : null,
    }));
}

function assembleResult(
  event: string,
  state_code: string,
  rows: {
    parties: PartyRow[];
    stateScope: StateScopeRow[];
    sources: SourceJoinRow[];
    acWinners: AcWinnerRow[];
  },
): StateOverviewViewModel {
  const scopeMap = new Map<string, StateScopeRow>();
  for (const r of rows.stateScope) scopeMap.set(r.indicator_id, r);
  const scopeNum = (id: string): number | undefined =>
    numOrUndef(scopeMap.get(id)?.value_numeric);

  // PartyTotals carries `party_eci_code: string | null` — dim_parties.eci_code
  // is currently null for every row in the canonical seed (a known gap), so
  // most parties surface with null here. PartyBar handles null gracefully.
  const party_totals: PartyTotals[] = rows.parties.map((r) => ({
    party_eci_code: r.eci_code ?? null,
    party_short: r.short_name ?? r.short_name_key,
    party_full: r.full_name ?? null,
    recognition: r.recognition ?? null,
    alliance: r.alliance ?? null,
    // PR-SYM-6f1: additive brand-identity fields from dim_parties. Null
    // when the LEFT JOIN missed (party not yet in canonical seed) so
    // SeatDonut's getPartyColor call falls through to the algorithmic tier.
    party_id: r.party_id ?? null,
    brand_colour_hex: r.brand_colour_hex ?? null,
    brand_colour_confidence:
      r.brand_colour_confidence === "high" ||
      r.brand_colour_confidence === "medium" ||
      r.brand_colour_confidence === "low"
        ? r.brand_colour_confidence
        : null,
    seats_contested:
      r.seats_contested == null ? null : Number(r.seats_contested),
    seats_won: num(r.seats_won),
    votes: num(r.votes),
    vote_share_pct: num(r.vote_share_pct),
  }));

  const total_seats = party_totals.reduce((s, p) => s + p.seats_won, 0);

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url_main)
    .map((s) => ({
      url: s.url_main ?? "",
      // Citation ledger (v2.0) does not carry fetch telemetry —
      // ``fetched_at`` is intentionally empty. See ADR-0032.
      fetched_at: "",
    }));

  // The full v2.0 ledger projection. Same JOIN, no url_main filter, sorted
  // by trust ordering so the citizen sees the strongest evidence first
  // (live-fetch > archived-snapshot > transcribed > editorial). Stable
  // secondary sort on source_id to keep snapshots reproducible. The
  // upstream SQL already does DISTINCT + ORDER BY s.source_id; we only
  // re-sort here for trust ordering.
  const sources_v2: SourceV2Row[] = [...rows.sources]
    .sort((a, b) => {
      const r = verificationMethodRank(a.verification_method) - verificationMethodRank(b.verification_method);
      return r !== 0 ? r : a.source_id.localeCompare(b.source_id);
    })
    .map(toSourceV2Row);

  const ac_winners = toAcWinners(rows.acWinners);

  return {
    election: event,
    state: state_code,
    total_seats,
    totals: {
      electors: scopeNum("electors-total"),
      votes_polled: scopeNum("votes-polled"),
      turnout_pct: scopeNum("turnout-pct"),
    },
    party_totals,
    ac_winners,
    sources,
    sources_v2,
  };
}

// Pure mapper — collapses a SourceJoinRow into the v2 row shape the chart
// shell consumes. Kept module-local so the column-by-column copy reads as
// one block; if a second loader grows the same need we can lift it into
// `frontend/src/lib/source-list-v2/`.
function toSourceV2Row(row: SourceJoinRow): SourceV2Row {
  return {
    source_id: row.source_id,
    producer: row.producer,
    title: row.title,
    vintage: row.vintage,
    license: row.license,
    confidence_tier: row.confidence_tier,
    is_issuing_authority: row.is_issuing_authority,
    verification_method: row.verification_method,
    url_main: row.url_main,
    citation_full: row.citation_full,
    notes: row.notes,
  };
}

function notPublishedSkeleton(
  event: string,
  state_code: string,
): StateOverviewViewModel {
  return {
    election: event,
    state: state_code,
    total_seats: 0,
    totals: null,
    party_totals: [],
    ac_winners: [],
    sources: [],
    sources_v2: [],
  };
}

export async function loadStateOverview(
  event: string,
  state_code: string,
): Promise<LoaderResult<StateOverviewViewModel>> {
  try {
    const rows = await runQueries(event, state_code);
    if (rows.parties.length === 0) {
      return {
        status: "partial",
        data: notPublishedSkeleton(event, state_code),
        reason: "not_published",
      };
    }
    return { status: "ok", data: assembleResult(event, state_code, rows) };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadStateOverview(event, state_code),
    };
  }
}

// Standalone lean loader — returns only the per-AC winners slice. Used by
// the Constituency route to populate its state-map context without paying
// for the party / state-scope / sources queries `loadStateOverview` runs.
// The StateOverview route still uses `loadStateOverview` (it needs the
// full view-model) and passes `summary.ac_winners` to its child charts.
export async function loadStateAcWinners(
  event: string,
  state_code: string,
): Promise<LoaderResult<AcWinner[]>> {
  try {
    await Promise.all([
      registerSlice("elections.election_results", { state: electionStatePartition(state_code) }),
      registerTable("elections.dim_parties"),
      registerTable("elections.dim_acs"),
      registerTable("elections.elections_candidacies"),
      registerTable("elections.dim_persons"),
    ]);
    const rows = await queryAcWinners(sqlString(event), sqlString(state_code));
    const winners = toAcWinners(rows);
    if (winners.length === 0) {
      return { status: "partial", data: [], reason: "not_published" };
    }
    return { status: "ok", data: winners };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadStateAcWinners(event, state_code),
    };
  }
}

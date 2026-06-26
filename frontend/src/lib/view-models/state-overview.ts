// Citizen view-model loader for the StateOverview route (F1.3a CSV cutover).
//
// Reads the per-(state, year) long-format CSV layout via DuckDB-WASM
// (see lib/duckdb.ts + lib/canonical/election-csv-paths.ts) and
// assembles a state-hub view-model — party totals + state totals +
// per-AC winners + sources — to replace the legacy parquet JOIN that
// fanned out from `election_results.parquet` + `dim_acs.parquet` +
// `elections_candidacies.parquet` + `dim_persons.parquet`.
//
// What is JOINed:
//   datasets/elections/assembly/state=*/election=*/candidacies.csv (per-candidacy)
//   datasets/elections/assembly/state=*/election=*/summary.csv     (per-AC summary)
//   datasets/data/entities/electoral.csv                           (AC entity + name + eci_no)
//   datasets/data/entities/party_alliances.csv                     (per-event alliance; X1a-fu2-C inline read_csv)
//   elections.dim_parties           - party identity + brand (CSV via registerCsvAsTable; X1a)
//   taxonomy.sources                - provenance ledger 5-field (CSV via registerCsvAsTable; X1a)
//
// Critical per-row contract (F1 sub-plan section 22.4 #4): every
// `read_csv(...)` carries an explicit `columns={...}` map derived from
// `datasets/data/_schema/columns.json` via `csvColumnsClause`. No
// hand-typed column lists.
//
// Known regressions vs the pre-F1.3a parquet world (documented for X1a):
// - long-tail rows where `party_id IS NULL` in candidacies.csv (the
//   ~20% TCPD shortcodes not in `parties.csv`) collapse into one
//   pseudo-row keyed `"OTHER"`. The legacy parquet aggregator picked
//   up the literal short via the `IN-<state>-<event>-PARTY-<short>`
//   entity pattern; the new CSV carries no `party_short_raw` column,
//   so we cannot reconstruct the per-party label. The OTHER bucket is
//   suppressed when zero such rows exist.

import {
  describeFailure,
  type LoaderResult,
} from "../loader-result";
import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  assemblyCandidaciesPath,
  assemblySummaryPath,
  electoralEntitiesPath,
} from "../canonical/election-csv-paths";
import { withElectionReadOpts } from "../canonical/election-read-opts";
import { electionStatePartition } from "../election-partitions";
import type { PartyTotals, SourceRef } from "../data";
import { dedupeToPills, type PublisherPill, type SourceRow } from "../sources";
import {
  assertSeatTallyInvariant,
  type SeatTallyParty,
} from "../charts/count-seats";

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
  /** Winner's share of all votes cast, in percent. Feeds the FPTP
   *  vote-share bar on the AC map hover card; null = unknown. */
  winner_share_pct?: number | null;
  // PR-B8 colour-by modes. Both are nullable/optional: turnout is
  // conditionally emitted per event and winner age is affidavit-sourced
  // (dense ~2004+, null for older events). Coverage is gated downstream.
  turnout_pct?: number | null;
  winner_age?: number | null;
  /** Winning candidate's display name (summary.csv `winner_candidate`).
   *  Null when summary did not emit a winner name. */
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
  /** Legacy provenance shape - fetch-telemetry-bearing `SourceRef` for
   *  any v1 consumer still wanting just a URL list. Filtered to rows that
   *  publish a non-empty URL. Empty `fetched_at` per ADR-0032 P.0e
   *  (fetch telemetry left the canonical contract). */
  sources: SourceRef[];
  /** Deduped publisher pills built from the citation-ledger rows via
   *  `dedupeToPills` from `$lib/sources`. One pill per (producer x
   *  series_family). Consumed by the new `<SourceList pills={...} />`
   *  component in `$lib/sources`. */
  pills: PublisherPill[];
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
  party_id: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  seats_contested: number | null;
  seats_won: number | null;
  votes: number | null;
  vote_share_pct: number | null;
}

interface StateScopeRow {
  electors: number | null;
  votes_polled: number | null;
  turnout_pct: number | null;
}

interface SourceJoinRow {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  url: string | null;
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
  acCount: number;
  stateScope: StateScopeRow | null;
  sources: SourceJoinRow[];
  acWinners: AcWinnerRow[];
}> {
  const candPath = assemblyCandidaciesPath(state_code, event);
  const sumPath = assemblySummaryPath(state_code, event);
  const electoralPath = electoralEntitiesPath();
  const partyAlliancesPath = "datasets/data/entities/party_alliances.csv";

  const candUrl = `${DATA_BASE}/${candPath.replace(/^datasets\//, "")}`;
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;
  const partyAlliancesUrl = `${DATA_BASE}/${partyAlliancesPath.replace(/^datasets\//, "")}`;

  // Typed-read clauses + URL registrations + parquet table registrations
  // in parallel. Per F1 sub-plan section 22.4 #4: read_csv MUST carry
  // `columns={...}` derived from columns.json (never `read_csv_auto`).
  // dim_parties + taxonomy.sources flipped to CSV in X1a via
  // `registerCsvAsTable` (parties.csv / source.csv). dim_party_alliances
  // flipped to inline `read_csv(party_alliances.csv, columns=...)` in
  // X1a-fu2-C (parquet retired); same JOIN keys on (party_id,
  // event_id) - the only swap is the source of dpa rows. v2.0 schema
  // (2026-06-12, plan TODO/20260612-alliance-phase-1-structural-fix-plan.md):
  // renamed period_label -> event_id (D1 fix - column joins the
  // canonical route event_id directly) + added state (D2 fix -
  // disambiguates per-state cohorts that share an event_id) + dropped
  // short_name. JOIN filters on (event_id, state OR "IN") so national
  // events (state="IN") light up on every state page while per-state
  // rows only show on their own state page.
  const [candClause, sumClause, electoralClause, partyAlliancesClause] = await Promise.all([
    csvColumnsClause(candPath),
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
    csvColumnsClause(partyAlliancesPath),
    registerCsvFile(candUrl),
    registerCsvFile(sumUrl),
    registerCsvFile(electoralUrl),
    registerCsvFile(partyAlliancesUrl),
    registerCsvAsTable("elections.dim_parties"),
    registerCsvAsTable("taxonomy.sources"),
  ]).then(([candCols, sumCols, electoralCols, partyAlliancesCols]) => [
    withElectionReadOpts(candCols),
    withElectionReadOpts(sumCols),
    withElectionReadOpts(electoralCols),
    withElectionReadOpts(partyAlliancesCols),
  ]);

  const evt = sqlString(event);
  // D2 fix: scope the alliance JOIN to (state OR "IN"). `electionStatePartition`
  // converts the loader's `state_code` ("S22") to the LGD state slug
  // ("tamil-nadu") that party_alliances.csv.state carries for state-
  // scoped events. National-event rows carry state="IN" and are visible
  // from every state page.
  const state_slug_for_alliance = sqlString(electionStatePartition(state_code));

  // Party pivot from per-candidacy CSV. Aggregate seats_contested
  // (distinct entity_id per party), seats_won (position=1), and votes
  // (SUM) per resolved party_id. The long-tail (party_id NULL) rows
  // collapse into one synthetic 'OTHER' row, suppressed downstream
  // when its seats_won is zero. LEFT JOIN dim_parties for the brand
  // identity + recognition + alliance overlay.
  const partySql = `
    WITH per_party AS (
      SELECT
        COALESCE(party_id, 'OTHER')                    AS resolved_party_id,
        COUNT(DISTINCT entity_id)                      AS seats_contested,
        SUM(CASE WHEN position = 1 THEN 1 ELSE 0 END)  AS seats_won,
        SUM(votes)                                     AS votes
      FROM read_csv('${candUrl}', ${candClause})
      GROUP BY 1
    ),
    state_total AS (
      SELECT SUM(votes) AS total_votes
      FROM read_csv('${candUrl}', ${candClause})
    )
    SELECT
      CASE
        WHEN p.resolved_party_id LIKE 'parties.IN.%'
          THEN substring(p.resolved_party_id, length('parties.IN.') + 1)
        ELSE p.resolved_party_id
      END                                  AS short_name_key,
      dp.short_name                        AS short_name,
      dp.full_name                         AS full_name,
      dp.eci_code                          AS eci_code,
      dp.recognition                       AS recognition,
      dpa.alliance                         AS alliance,
      dp.party_id                          AS party_id,
      dp.brand_colour_hex                  AS brand_colour_hex,
      dp.brand_colour_confidence           AS brand_colour_confidence,
      p.seats_contested                    AS seats_contested,
      p.seats_won                          AS seats_won,
      p.votes                              AS votes,
      CASE WHEN st.total_votes > 0
           THEN (p.votes * 100.0 / st.total_votes)
           ELSE NULL END                   AS vote_share_pct
    FROM per_party p
    CROSS JOIN state_total st
    LEFT JOIN dim_parties dp
      ON dp.party_id = p.resolved_party_id
    LEFT JOIN read_csv('${partyAlliancesUrl}', ${partyAlliancesClause}) dpa
      ON dpa.party_id = dp.party_id
      AND dpa.event_id = ${evt}
      AND (dpa.state = ${state_slug_for_alliance} OR dpa.state = 'IN')
    ORDER BY p.seats_won DESC, p.votes DESC
  `;
  const parties = await query<PartyRow>(partySql);

  if (parties.length === 0) {
    return { parties, acCount: 0, stateScope: null, sources: [], acWinners: [] };
  }

  // E5 (plan section 25.6a): source `total_seats` from a SEPARATE COUNT
  // over summary.csv (one row per AC, the canonical winners table) so the
  // seats-invariant assertion downstream is meaningful. If we summed
  // `party_totals.seats_won` here, the assertion would be trivially true
  // (sum == sum). Sourcing `total_seats` independently means a future bug
  // in EITHER feed (party-side fan-out, or summary-side row loss) trips
  // the assertion at the view-model boundary.
  const acCountSql = `
    SELECT COUNT(DISTINCT entity_id) AS ac_count
    FROM read_csv('${sumUrl}', ${sumClause})
  `;
  const acCountRows = await query<{ ac_count: number | string | bigint | null }>(
    acCountSql,
  );
  const acCount = Number(acCountRows[0]?.ac_count ?? 0);

  // State-scope totals: SUM electors / votes_polled across summary.csv
  // (one row per AC) + weighted-average turnout. summary.electors /
  // votes_polled may be NULL for ACs where the source had no
  // electorate-level fact (rare). Use SUM() with implicit NULL
  // skipping so partial coverage still surfaces a state total.
  const stateScopeSql = `
    SELECT
      SUM(electors)                                AS electors,
      SUM(votes_polled)                            AS votes_polled,
      CASE WHEN SUM(electors) > 0
           THEN SUM(votes_polled) * 100.0 / SUM(electors)
           ELSE NULL END                           AS turnout_pct
    FROM read_csv('${sumUrl}', ${sumClause})
  `;
  const stateScopeRows = await query<StateScopeRow>(stateScopeSql);
  const stateScope = stateScopeRows[0] ?? null;

  // Source rows: every source_id that appears in candidacies + summary
  // for this (state, year) -> taxonomy.sources (CSV via registerCsvAsTable
  // / X1a; 5-field shape per plan O3 - the rich v2 fields surface NULL).
  const sourceIdRows = await query<{ source_id: string }>(`
    SELECT DISTINCT source_id FROM (
      SELECT source_id FROM read_csv('${candUrl}', ${candClause}) WHERE source_id IS NOT NULL
      UNION ALL
      SELECT source_id FROM read_csv('${sumUrl}', ${sumClause}) WHERE source_id IS NOT NULL
    )
  `);
  const sourceIds = Array.from(new Set(sourceIdRows.map((r) => r.source_id)));

  let sources: SourceJoinRow[] = [];
  if (sourceIds.length > 0) {
    const idList = sourceIds.map(sqlString).join(", ");
    sources = await query<SourceJoinRow>(`
      SELECT
        s.source_id,
        s.producer,
        s.title,
        s.vintage,
        s.url
      FROM sources s
      WHERE s.source_id IN (${idList})
      ORDER BY s.source_id
    `);
  }

  // AC winners: one row per AC from summary.csv joined to electoral.csv
  // for eci_no + name. winner_age comes from candidacies.csv via
  // (entity_id, candidate_name=winner_candidate, position=1). LEFT
  // JOIN dim_parties for brand identity columns the renderer surfaces.
  // turnout_pct lives on summary.csv directly (no parquet round-trip).
  const acWinnersSql = `
    SELECT
      e.eci_no                              AS ac_eci_no,
      e.name                                AS ac_name,
      s.winner_party_id                     AS party_id,
      dp.eci_code                           AS party_eci_code,
      dp.short_name                         AS party_short,
      dp.brand_colour_hex                   AS brand_colour_hex,
      dp.brand_colour_confidence            AS brand_colour_confidence,
      dp.election_symbol_asset_path         AS symbol_asset_path,
      s.margin_pct                          AS margin_pct,
      s.turnout_pct                         AS turnout_pct,
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
  const acWinners = await query<AcWinnerRow>(acWinnersSql);

  return { parties, acCount, stateScope, sources, acWinners };
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
    acCount: number;
    stateScope: StateScopeRow | null;
    sources: SourceJoinRow[];
    acWinners: AcWinnerRow[];
  },
): StateOverviewViewModel {
  // PartyTotals carries `party_eci_code: string | null` — dim_parties.eci_code
  // is currently null for many rows in the canonical seed, so most parties
  // surface with null here. PartyBar handles null gracefully.
  // Filter the synthetic 'OTHER' bucket out when its seats_won is zero
  // (no contribution to the donut / bar) — keep it when it actually has
  // wins.
  const party_totals: PartyTotals[] = rows.parties
    .filter(
      (r) => r.short_name_key !== "OTHER" || num(r.seats_won) > 0,
    )
    .map((r) => ({
      party_eci_code: r.eci_code ?? null,
      party_short: r.short_name ?? r.short_name_key,
      party_full: r.full_name ?? null,
      recognition: r.recognition ?? null,
      alliance: r.alliance ?? null,
      // Additive brand-identity fields from dim_parties. Null when the
      // LEFT JOIN missed (party not yet in canonical seed) so
      // SeatDonut's getPartyColor call falls through to the algorithmic
      // tier.
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

  // E5 (plan section 25.6a): `total_seats` is the COUNT(DISTINCT entity_id)
  // over summary.csv (canonical winners table; one row per AC), NOT the
  // sum of `party_totals.seats_won`. The two paths MUST agree -
  // assertSeatTallyInvariant below catches any future drift (alliance JOIN
  // fan-out, summary-row loss, etc.) at the view-model boundary.
  const total_seats = rows.acCount;

  // Contract gate: sum(seats_won across parties INCLUDING the 'OTHER'
  // bucket if it has wins) MUST equal total_seats. We construct the
  // SeatTally with `short_name_key` as the synthetic party_id (always
  // non-null; 'OTHER' for the unattributed bucket) so the assertion
  // receives a coalesced tally even when the dim_parties JOIN missed.
  // Per plan section 25.6a: "fail-fast, fix the join, never silently
  // halve". Pinned by the seats-invariant-test gate (section 22.6).
  const tally_parties: SeatTallyParty[] = rows.parties
    .filter((r) => num(r.seats_won) > 0)
    .map((r) => ({
      party_id: r.party_id ?? r.short_name_key,
      seats_won: num(r.seats_won),
    }));
  assertSeatTallyInvariant(
    { total_seats, parties: tally_parties },
    `state-overview:${state_code}:${event}`,
  );

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url)
    .map((s) => ({
      url: s.url ?? "",
      // Citation ledger does not carry fetch telemetry per ADR-0032.
      // Emit empty string to satisfy the back-compat SourceRef shape.
      fetched_at: "",
    }));

  // Publisher pills built via the canonical dedupeToPills helper. One
  // pill per (producer x series_family); the SourceList component in
  // `$lib/sources` consumes this directly. Reuses the same JOIN rows.
  const pills: PublisherPill[] = dedupeToPills(
    rows.sources.map<SourceRow>((s) => ({
      source_id: s.source_id,
      producer: s.producer,
      title: s.title,
      vintage: s.vintage,
      url: s.url,
    })),
  );

  const ac_winners = toAcWinners(rows.acWinners);

  return {
    election: event,
    state: state_code,
    total_seats,
    totals: rows.stateScope
      ? {
          electors: numOrUndef(rows.stateScope.electors),
          votes_polled: numOrUndef(rows.stateScope.votes_polled),
          turnout_pct: numOrUndef(rows.stateScope.turnout_pct),
        }
      : null,
    party_totals,
    ac_winners,
    sources,
    pills,
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
    pills: [],
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

// PR-W5a (2026-06-10): the lean per-AC-winners loader `loadStateAcWinners`
// retired here. Its sole call-site (Constituency.svelte) flipped to the
// W2b generic `loadElectionResults({event, state})` + `projectAsWinnersByEntity`
// + a local `toAcWinner()` mapper. `AcWinner` + `loadStateOverview` are
// kept because they are consumed by the state hub (`StateOverview.svelte`)
// + party page (`Party.svelte`) + 8+ map/chart components.

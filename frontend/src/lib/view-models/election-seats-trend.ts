// Citizen view-model loader for the ElectionSeatsTrend chart (PR-G / Phase 1.3c).
//
// Fans the four party-* indicators across every event the caller asks for
// (typically the full per-state catalogue) and returns one PartyTotals[] per
// event_id. The wrapper component reshapes the result into ResultSummaryDoc[]
// for the existing electionsToStackedTrend adapter — the adapter stays pure
// and untouched.
//
// What is JOINed:
//   elections.election_results  - numeric facts (party-* indicators only)
//   elections.dim_parties   - party labels (short_name, eci_code) [CSV via registerCsvAsTable; X1a]
//   taxonomy.sources        - provenance for the union across events [CSV via registerCsvAsTable; X1a]
//
// LoaderResult arms mirror PR-F:
//   ok       — at least one event yielded party rows.
//   partial  — caller passed zero events (state has no partywise cohort).
//   failed   — DuckDB-WASM / fetch / SQL error.

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerCsvAsTable, registerSlice } from "../duckdb";
import { electionStatePartition } from "../election-partitions";
import type { PartyTotals, SourceRef } from "../data";
import type { StackedTrendV2Source } from "../charts/stacked-trend-v2";

export interface ElectionSeatsTrendEvent {
  event_id: string;
  party_totals: PartyTotals[];
  total_seats: number;
}

export interface ElectionSeatsTrendViewModel {
  state: string;
  events: ElectionSeatsTrendEvent[];
  /**
   * Legacy v1 SourceRef projection — `{ url, fetched_at: "" }`. Kept
   * for back-compat with the v1 `electionsToStackedTrend` adapter that
   * still ships under `frontend/src/lib/charts/stacked-trend/`. Will
   * retire alongside `frontend/src/lib/charts/StackedTrend.svelte` v1
   * once every caller migrates to v2 (Track-D D13).
   */
  sources: SourceRef[];
  /**
   * Citation-ledger v2.0 rows resolved from `taxonomy.sources` by
   * `source_id` (R-28 manifest-registered table, R-24 zero fetch
   * telemetry). Consumed by the StackedTrendV2 migration adapter
   * `stackedTrendModelToV2(model, sources_v2)`. Empty array when
   * the per-state cohort yielded no rows.
   */
  sources_v2: StackedTrendV2Source[];
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface PartyRow {
  period_label: string;
  short_name_key: string;
  short_name: string | null;
  full_name: string | null;
  eci_code: string | null;
  seats_contested: number | null;
  seats_won: number | null;
  votes: number | null;
  vote_share_pct: number | null;
  party_id: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
}

interface SourceJoinRow {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  license: string;
  confidence_tier: string;
  is_issuing_authority: boolean;
  verification_method: string;
  url_main: string | null;
  citation_full: string | null;
  notes: string | null;
}

const num = (v: unknown): number => (v == null ? 0 : Number(v));

async function runQueries(
  state_code: string,
  event_ids: string[],
): Promise<{ parties: PartyRow[]; sources: SourceJoinRow[] }> {
  await Promise.all([
    registerSlice("elections.election_results", { state: electionStatePartition(state_code) }),
    registerCsvAsTable("elections.dim_parties"),
    registerCsvAsTable("taxonomy.sources"),
  ]);

  const partyPrefix = sqlString(`IN-${state_code}-`);
  const eventList = event_ids.map(sqlString).join(", ");

  const partySql = `
    SELECT
      o.period_label                                              AS period_label,
      regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)              AS short_name_key,
      dp.short_name                                               AS short_name,
      dp.full_name                                                AS full_name,
      dp.eci_code                                                 AS eci_code,
      dp.party_id                                                 AS party_id,
      dp.brand_colour_hex                                         AS brand_colour_hex,
      dp.brand_colour_confidence                                  AS brand_colour_confidence,
      MAX(CASE WHEN o.indicator_id = 'party-contested-acs'  THEN o.value_numeric END) AS seats_contested,
      MAX(CASE WHEN o.indicator_id = 'party-seats-won'      THEN o.value_numeric END) AS seats_won,
      MAX(CASE WHEN o.indicator_id = 'party-votes-polled'   THEN o.value_numeric END) AS votes,
      MAX(CASE WHEN o.indicator_id = 'party-vote-share-pct' THEN o.value_numeric END) AS vote_share_pct
    FROM election_results o
    LEFT JOIN dim_parties dp
      ON dp.short_name = regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)
    WHERE o.entity_id LIKE ${partyPrefix} || '%-PARTY-%'
      AND o.period_label IN (${eventList})
      AND o.indicator_id IN (
        'party-contested-acs',
        'party-seats-won',
        'party-votes-polled',
        'party-vote-share-pct'
      )
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
  `;
  const parties = await query<PartyRow>(partySql);

  const sources = await query<SourceJoinRow>(`
    SELECT DISTINCT
      s.source_id          AS source_id,
      s.producer           AS producer,
      s.title              AS title,
      s.vintage            AS vintage,
      s.license            AS license,
      s.confidence_tier    AS confidence_tier,
      s.is_issuing_authority AS is_issuing_authority,
      s.verification_method AS verification_method,
      s.url_main           AS url_main,
      s.citation_full      AS citation_full,
      s.notes              AS notes
    FROM election_results o
    JOIN sources s ON s.source_id = o.source_id
    WHERE o.period_label IN (${eventList})
      AND o.entity_id LIKE ${partyPrefix} || '%'
    ORDER BY s.source_id
  `);

  return { parties, sources };
}

function assembleResult(
  state_code: string,
  rows: { parties: PartyRow[]; sources: SourceJoinRow[] },
): ElectionSeatsTrendViewModel {
  // Group rows by period_label.
  const byEvent = new Map<string, PartyRow[]>();
  for (const r of rows.parties) {
    const arr = byEvent.get(r.period_label) ?? [];
    arr.push(r);
    byEvent.set(r.period_label, arr);
  }

  const events: ElectionSeatsTrendEvent[] = [];
  for (const [event_id, arr] of byEvent) {
    const party_totals: PartyTotals[] = arr.map((r) => ({
      party_eci_code: r.eci_code ?? null,
      party_short: r.short_name ?? r.short_name_key,
      party_full: r.full_name ?? null,
      seats_contested:
        r.seats_contested == null ? null : Number(r.seats_contested),
      seats_won: num(r.seats_won),
      votes: num(r.votes),
      vote_share_pct: num(r.vote_share_pct),
      party_id: r.party_id ?? null,
      brand_colour_hex: r.brand_colour_hex ?? null,
      brand_colour_confidence:
        r.brand_colour_confidence === "high" ||
        r.brand_colour_confidence === "medium" ||
        r.brand_colour_confidence === "low"
          ? r.brand_colour_confidence
          : null,
    }));
    const total_seats = party_totals.reduce((s, p) => s + p.seats_won, 0);
    events.push({ event_id, party_totals, total_seats });
  }

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url_main)
    .map((s) => ({
      url: s.url_main ?? "",
      // Citation ledger (v2.0) does not carry fetch telemetry —
      // ``fetched_at`` is intentionally empty. See ADR-0032.
      fetched_at: "",
    }));

  // v2.0 ledger projection — every column the StackedTrendV2 renderer
  // needs lands here verbatim from `taxonomy.sources` (R-24 + ADR-0032).
  // DuckDB-WASM returns license/confidence_tier/verification_method as
  // unrestricted strings; the zod schema on StackedTrendV2Source enforces
  // the locked enums at the consumer boundary. Casting here is the
  // narrowest typed seam between SQL and zod.
  const sources_v2: StackedTrendV2Source[] = rows.sources.map(
    (s) =>
      ({
        source_id: s.source_id,
        producer: s.producer,
        title: s.title,
        vintage: s.vintage,
        license: s.license,
        confidence_tier: s.confidence_tier,
        is_issuing_authority: Boolean(s.is_issuing_authority),
        verification_method: s.verification_method,
        url_main: s.url_main,
        citation_full: s.citation_full,
        notes: s.notes,
      }) as StackedTrendV2Source,
  );

  return { state: state_code, events, sources, sources_v2 };
}

function notPublishedSkeleton(state_code: string): ElectionSeatsTrendViewModel {
  return { state: state_code, events: [], sources: [], sources_v2: [] };
}

export async function loadElectionSeatsTrend(
  state_code: string,
  event_ids: string[],
): Promise<LoaderResult<ElectionSeatsTrendViewModel>> {
  if (event_ids.length === 0) {
    return {
      status: "partial",
      data: notPublishedSkeleton(state_code),
      reason: "not_published",
    };
  }
  try {
    const rows = await runQueries(state_code, event_ids);
    if (rows.parties.length === 0) {
      return {
        status: "partial",
        data: notPublishedSkeleton(state_code),
        reason: "not_published",
      };
    }
    return { status: "ok", data: assembleResult(state_code, rows) };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadElectionSeatsTrend(state_code, event_ids),
    };
  }
}

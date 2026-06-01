// Citizen view-model loader for the National Elections Atlas (PR-B4 of the
// UK-style elections experience plan).
//
// Cross-state companion to `loadStateAcWinners` (state-overview.ts): assembles
// the per-Parliamentary-Constituency winning party + margin for ONE Lok Sabha
// event across every state, in a single national scan. The state loader slices
// to one partition; this one registers the WHOLE `election_results` table
// (all state partitions) because PC results are spread across `state=in_<x>`
// shards (ADR-0044 write-seam: PC rows live in the same per-state family as AC
// rows, disambiguated by `entity_id` prefix `IN-PC-`).
//
// Identity (ADR-0044 / baked Model C): a PC observation's entity_id is
// `IN-PC-<delim>-<state_code>-<pc_no>` (e.g. `IN-PC-2008-S07-8`). `dim_pcs`
// carries `pc_id` + `state_code` + `pc_no` + `name`. Two keys are emitted per
// winner so both render surfaces can join without re-deriving identity:
//   - `unit_id`  = pc_id            → matches the national-PC tile layout's
//                                     `unit_id` (TileCartogram / hex arm).
//   - `join_key` = `<state>_<pc_no>` → matches the INDIA_PC GeoJSON
//                                     `unique_id` property (choropleth arm).
//
// LoaderResult arms mirror `loadStateAcWinners`:
//   ok      — 1+ PC winners found; full list.
//   partial — zero PC rows for the event (PC data not yet ingested); empty
//             list + reason "not_published" so the atlas renders a graceful
//             "results pending" state and the boundary still draws.
//   failed  — DuckDB-WASM / fetch / SQL error; describeFailure + retry.

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerTable } from "../duckdb";

export interface NationalPcWinner {
  /** Canonical PC entity id (= national-PC tile-layout unit_id). */
  unit_id: string;
  /** `<state_code>_<pc_no>` — matches INDIA_PC GeoJSON `unique_id`. */
  join_key: string;
  state_code: string;
  pc_no: number;
  pc_name: string;
  party_eci_code: string | null;
  party_short: string;
  margin_pct: number;
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface PcWinnerRow {
  pc_id: string;
  state_code: string;
  pc_no: number;
  pc_name: string;
  party_eci_code: string | null;
  party_short: string | null;
  margin_pct: number | null;
}

async function queryPcWinners(evtLiteral: string): Promise<PcWinnerRow[]> {
  return query<PcWinnerRow>(`
    WITH winner AS (
      SELECT entity_id AS pc_id, value_text AS party_id
      FROM election_results
      WHERE indicator_id = 'pc-winner-party-id'
        AND period_label = ${evtLiteral}
        AND entity_id LIKE 'IN-PC-%'
    ),
    margin AS (
      SELECT entity_id AS pc_id, value_numeric AS margin_pct
      FROM election_results
      WHERE indicator_id = 'pc-margin-pct'
        AND period_label = ${evtLiteral}
        AND entity_id LIKE 'IN-PC-%'
    )
    SELECT dpc.pc_id        AS pc_id,
           dpc.state_code   AS state_code,
           dpc.pc_no        AS pc_no,
           dpc.name         AS pc_name,
           dp.eci_code      AS party_eci_code,
           dp.short_name    AS party_short,
           m.margin_pct     AS margin_pct
    FROM winner w
    JOIN margin m ON m.pc_id = w.pc_id
    JOIN dim_pcs dpc ON dpc.pc_id = w.pc_id
    LEFT JOIN dim_parties dp ON dp.party_id = w.party_id
  `);
}

function toNationalPcWinners(rows: PcWinnerRow[]): NationalPcWinner[] {
  return rows
    .filter((r) => r.pc_no != null && r.margin_pct != null)
    .map((r) => ({
      unit_id: r.pc_id,
      join_key: `${r.state_code}_${r.pc_no}`,
      state_code: r.state_code,
      pc_no: Number(r.pc_no),
      pc_name: r.pc_name ?? "",
      party_eci_code: r.party_eci_code ?? null,
      party_short: r.party_short ?? "",
      margin_pct: Number(r.margin_pct),
    }));
}

export async function loadNationalPcWinners(
  event: string,
): Promise<LoaderResult<NationalPcWinner[]>> {
  try {
    await Promise.all([
      registerTable("elections.election_results"),
      registerTable("elections.dim_parties"),
      registerTable("elections.dim_pcs"),
    ]);
    const rows = await queryPcWinners(sqlString(event));
    const winners = toNationalPcWinners(rows);
    if (winners.length === 0) {
      return { status: "partial", data: [], reason: "not_published" };
    }
    return { status: "ok", data: winners };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadNationalPcWinners(event),
    };
  }
}

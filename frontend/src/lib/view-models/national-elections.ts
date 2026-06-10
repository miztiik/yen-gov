// Citizen view-model loader for the National Elections Atlas (F1.3b CSV cutover).
//
// Cross-state companion to `loadStateAcWinners` (state-overview.ts): assembles
// the per-Parliamentary-Constituency winning party + margin for ONE Parliament
// event across every state on disk, in a single national scan.
//
// What is JOINed:
//   datasets/elections/parliament/election=*/summary.csv (one row per PC)
//   datasets/data/entities/electoral.csv                 (PC name + state + eci_no + delim_year lookup)
//   elections.dim_parties  (CSV via registerCsvAsTable; X1a reader flip)
//
// Critical per-row contract (F1 sub-plan section 22.4 #4): every
// `read_csv(...)` call carries an explicit `columns={...}` map derived
// from `datasets/data/_schema/columns.json` via `csvColumnsClause`. No
// hand-typed column lists.
//
// Identity (carried for the two render arms):
//   - `unit_id`  = `IN-PC-<delim_year>-<state_code_eci>-<pc_no>`
//                  -> matches the national-PC tile-layout `unit_id`
//                  (TileCartogram). The on-disk electoral.csv carries
//                  the entity_id in LGD-slug form
//                  (`IN-PC-2008-andhra-pradesh-411`); the tile-layout
//                  catalogue uses the ECI-coded form
//                  (`IN-PC-2008-S07-1`). The loader translates LGD slug
//                  -> ECI code via `SLUG_TO_ECI` so the tile arm joins
//                  cleanly.
//   - `join_key` = `<state_code>_<pc_no>`
//                  -> matches the INDIA_PC GeoJSON `unique_id` property
//                  (choropleth arm).
//
// LoaderResult arms:
//   ok      - 1+ PC winners found; full list.
//   partial - zero PC rows for the event (PC data not yet ingested); empty
//             list + reason "not_published" so the atlas renders a graceful
//             "results pending" state and the boundary still draws.
//   failed  - DuckDB-WASM / fetch / SQL error; describeFailure + retry.
//
// Known regression vs the pre-F1.3b parquet world (documented for X1a):
//   - `winner_age`: was JOINed from `dim_persons.age` via
//     `elections_candidacies.candidacy_key`. summary.csv carries
//     `winner_candidate` (display name string) but not age. Returns
//     `null` until X1a restores via a candidacies JOIN by name (see the
//     F1.3a same-regression note in `view-models/constituency.ts`).

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  electoralEntitiesPath,
  parliamentSummaryPath,
} from "../canonical/election-csv-paths";
import { ECI_TO_LGD_SLUG } from "../maplibre/sources";

// Reverse lookup: LGD state slug (e.g. "tamil-nadu") -> ECI state code
// (e.g. "S22"). The on-disk electoral.csv carries state in LGD form
// while the national tile-layout + INDIA_PC GeoJSON `unique_id` carry
// ECI form. This translation is the only place LGD vocabulary crosses
// into the National Elections Atlas's render arms.
const SLUG_TO_ECI: Readonly<Record<string, string>> = Object.fromEntries(
  Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
);

export interface NationalPcWinner {
  /** Canonical PC entity id in ECI form
   *  (`IN-PC-<delim>-<state_code>-<pc_no>`); matches the national-PC
   *  tile-layout `unit_id`. */
  unit_id: string;
  /** `<state_code>_<pc_no>` -> matches INDIA_PC GeoJSON `unique_id`. */
  join_key: string;
  state_code: string;
  pc_no: number;
  pc_name: string;
  /** PR-SYM-6i-pre3: canonical `parties.IN.<SLUG>` from the
   *  summary.csv `winner_party_id`. Render code calls
   *  `getPartyColor(party_id, row)` - the resolver picks anchor /
   *  Wikipedia brand_colour / algorithmic-fallback off this key. */
  party_id: string;
  party_eci_code: string | null;
  party_short: string;
  margin_pct: number;
  /** Turnout % for the seat (PR-B9 colour-by); null when not ingested. */
  turnout_pct?: number | null;
  /** Winning MP's age - null after F1.3b CSV cutover (dim_persons join
   *  retired). X1a or a later sub-PR can restore by JOINing
   *  candidacies.csv on `(entity_id, candidate_name = winner_candidate)`. */
  winner_age?: number | null;
  /** Winning candidate's display name. Read inline from
   *  summary.csv.winner_candidate. Null when upstream omitted the
   *  name. */
  winner_candidate_name?: string | null;
  /** Winning party's election-symbol asset path, root-relative
   *  (e.g. "party-symbols/lotus.svg"), from
   *  dim_parties.election_symbol_asset_path. Null when no verified symbol
   *  asset - the tooltip medallion degrades silently. */
  symbol_asset_path?: string | null;
  // PR-SYM-6i-pre3 additive brand_colour mirror (from dim_parties v1.1).
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
}

interface PcWinnerRow {
  pc_entity_id: string;
  state_slug: string;
  pc_no: number;
  delim_year: number;
  pc_name: string;
  party_id: string | null;
  party_eci_code: string | null;
  party_short: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  margin_pct: number | null;
  turnout_pct: number | null;
  winner_candidate_name: string | null;
  symbol_asset_path: string | null;
}

async function runQuery(event: string): Promise<PcWinnerRow[]> {
  const sumPath = parliamentSummaryPath(event);
  const electoralPath = electoralEntitiesPath();
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;

  // Typed-read clauses + view registrations in parallel. dim_parties
  // flipped to CSV via registerCsvAsTable in X1a (parties.csv); the
  // seam projects the legacy column shape so the LEFT JOIN below is
  // unchanged.
  const [sumClause, electoralClause] = await Promise.all([
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
    registerCsvFile(sumUrl),
    registerCsvFile(electoralUrl),
    registerCsvAsTable("elections.dim_parties"),
  ]);

  // One row per PC. LEFT JOIN dim_parties so an UNK winner_party_id
  // (long-tail party not in parties.csv) still emits a row, just with
  // null brand metadata - the renderer degrades to the algorithmic
  // colour tier via the party_id sentinel chain.
  const sql = `
    SELECT
      e.entity_id                   AS pc_entity_id,
      e.state                       AS state_slug,
      e.eci_no                      AS pc_no,
      e.delim_year                  AS delim_year,
      e.name                        AS pc_name,
      s.winner_party_id             AS party_id,
      dp.eci_code                   AS party_eci_code,
      dp.short_name                 AS party_short,
      dp.brand_colour_hex           AS brand_colour_hex,
      dp.brand_colour_confidence    AS brand_colour_confidence,
      dp.election_symbol_asset_path AS symbol_asset_path,
      s.margin_pct                  AS margin_pct,
      s.turnout_pct                 AS turnout_pct,
      s.winner_candidate            AS winner_candidate_name
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'pc'
  `;
  return query<PcWinnerRow>(sql);
}

function toNationalPcWinners(rows: PcWinnerRow[]): NationalPcWinner[] {
  return rows
    .filter((r) => r.pc_no != null && r.margin_pct != null)
    .map((r) => {
      const state_slug = String(r.state_slug ?? "");
      const state_code =
        SLUG_TO_ECI[state_slug] ?? state_slug.toUpperCase();
      const pc_no = Number(r.pc_no);
      const delim_year = Number(r.delim_year ?? 2008);
      // ECI-form unit_id (matches tile-layout). The on-disk LGD-form
      // entity_id (e.g. IN-PC-2008-andhra-pradesh-411) is NOT carried
      // through; downstream renderers all join by the ECI form.
      const unit_id = `IN-PC-${delim_year}-${state_code}-${pc_no}`;
      const join_key = `${state_code}_${pc_no}`;
      return {
        unit_id,
        join_key,
        state_code,
        pc_no,
        pc_name: r.pc_name ?? "",
        party_id: r.party_id ?? "",
        party_eci_code: r.party_eci_code ?? null,
        party_short: r.party_short ?? "",
        margin_pct: Number(r.margin_pct),
        turnout_pct:
          r.turnout_pct == null ? null : Number(r.turnout_pct),
        // F1.3b regression: no dim_persons JOIN, no candidacies JOIN
        // for the national grain. winner_age recovered in X1a (or a
        // dedicated follow-up) when readers cut over fully.
        winner_age: null,
        winner_candidate_name: r.winner_candidate_name ?? null,
        symbol_asset_path: r.symbol_asset_path ?? null,
        brand_colour_hex: r.brand_colour_hex ?? null,
        brand_colour_confidence:
          (r.brand_colour_confidence as
            | "high"
            | "medium"
            | "low"
            | null) ?? null,
      };
    });
}

export async function loadNationalPcWinners(
  event: string,
): Promise<LoaderResult<NationalPcWinner[]>> {
  try {
    const rows = await runQuery(event);
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

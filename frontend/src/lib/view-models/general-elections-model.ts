// General-elections view-model (PR-E3 of TODO/20260615-elections-redesign-plan.md).
//
// Powers the redesigned `/t/elections` route mounted in PR-E4
// (GeneralElections.svelte). Reads the per-event aggregate mart shipped
// by PR-E2 via `loadEventSummary()`, filters `scope='national'`, sorts
// by polled_on descending, derives `turnout_delta_pp` against the
// chronologically-prior General election event, and resolves
// party-display fields (color, glyph candidates) through the existing
// `getPartyColor` resolver.
//
// One row per Parliament cycle. ~11 rows today (general-1962 through
// general-2024); the row count grows by 1 per new cycle.

import { csvColumnsClause } from "../canonical/csv-columns";
import { getPartyColor } from "../colors/resolver";
import { query, registerCsvFile } from "../duckdb";
import {
  loadEventSummary,
  type EventSummaryRow,
} from "../elections/event-summary-loader";
import { link } from "../links";
import { DATA_BASE } from "../paths";
import { dedupeToPills, type PublisherPill, type SourceRow } from "../sources";
import { loadAllPartiesMeta, type PartyMeta } from "./parties";

/** One row of the General-elections table. */
export interface GeneralElectionRowViewModel {
  /** Event id like "general-2024" used for detail-page links. */
  event_id: string;
  /** Cycle year extracted from polled_on (e.g. 2024). */
  year: number;
  /** ISO date YYYY-MM-DD. */
  polled_on: string;
  /** Citizen-render leading-party card. */
  leading: LeadingPartyCell;
  seats_won: number;
  seats_contested: number;
  /** Vote-share % of the leading party. Currently null because the
   *  event_summary mart does not carry per-party vote shares; the
   *  field is reserved so PR-E4 can render an empty bar without a
   *  null-coalesce dance. A future writer enhancement (out of E3
   *  scope) may populate this. */
  vote_share_pct: number | null;
  /** Event-scope turnout %. NULL when the writer could not aggregate. */
  turnout_pct: number | null;
  /** Difference vs the previous Parliament event (percentage points).
   *  NULL for the earliest row in the sorted-descending list. */
  turnout_delta_pp: number | null;
  /** Top runner-up. NULL when the writer did not record one. */
  runner_up: RunnerUpCell | null;
  /** Per-row detail-page href (the NationalElection.svelte route). */
  detail_href: string;
  /** Citation-ledger FK to datasets/data/entities/source.csv (Holy
   *  Law #9). Surfaced so the page can resolve a provenance footer. */
  source_id: string;
  /** Seats a single party needs for a majority this cycle:
   *  floor(seats_contested / 2) + 1. Derived per-row because the house
   *  size varies (427 in 1962, 542/543 in the modern era). */
  majority_mark: number;
  /** Mandate verdict derived from seats_won vs majority_mark. */
  mandate: MandateCell;
  /** Leading-slot seat change vs the chronologically-prior cycle
   *  (this cycle's winner seats - previous cycle's winner seats).
   *  NULL for the earliest row. Tells the power-swing story that the
   *  quieter turnout delta does not. */
  seat_swing: number | null;
  /** Lead over the runner-up in seats (seats_won - runner_up seats).
   *  0 when there is no recorded runner-up. */
  margin: number;
  /** Seats held by neither the leader nor the runner-up:
   *  max(0, seats_contested - seats_won - runner_up seats). The grey
   *  band of the seat-composition stack. */
  others_seats: number;
}

/** Mandate verdict for the leading party. Derived, closed-shape. */
export interface MandateCell {
  /** True when the leading party alone reached the majority mark. */
  majority: boolean;
  /** seats_won - majority_mark. >= 0 on a majority; negative when short. */
  gap: number;
  /** Citizen-readable label: "Majority" or "Short by N". */
  label: string;
}

/** Citizen-render shape for the leading-party cell. */
export interface LeadingPartyCell {
  /** Canonical party_id; may be NULL when leader could not be derived. */
  party_id: string | null;
  /** Citizen-readable short name ("BJP", "INC"). Falls back to the
   *  party_id tail when the row is absent from parties.csv. Empty
   *  string when leader could not be derived. */
  short: string;
  /** Brand colour hex (`#RRGGBB`). Greyscale fallback when missing. */
  color: string;
  /** Per-party slug (e.g. "bjp") for the link to /parties/<slug>.
   *  NULL when the leader's slug cannot be derived (e.g. UNK). */
  detail_href: string | null;
}

/** Top runner-up cell. Shares the same shape as the leader. */
export interface RunnerUpCell extends LeadingPartyCell {
  seats: number;
}

/** Options for the loader. Tests inject overrides; production calls without. */
export interface LoadGeneralElectionsOpts {
  /** Override the event_summary fetch. Tests pass synthetic rows. */
  loadEventSummaryOverride?: () => Promise<EventSummaryRow[]>;
  /** Override the parties metadata fetch. Tests pass synthetic map. */
  loadPartiesMetaOverride?: () => Promise<Map<string, PartyMeta>>;
}

/** Project the event_summary rows into the General-elections table.
 *
 *  Loader is self-contained: by default it fetches both event_summary
 *  and parties metadata internally so any callsite gets a complete
 *  view-model without piping resolvers through. Tests inject overrides
 *  via the opts argument.
 */
export async function loadGeneralElections(
  opts: LoadGeneralElectionsOpts = {},
): Promise<GeneralElectionRowViewModel[]> {
  const fetchSummary = opts.loadEventSummaryOverride ?? loadEventSummary;
  const fetchPartiesMeta = opts.loadPartiesMetaOverride ?? loadAllPartiesMeta;
  const [rows, partiesMeta] = await Promise.all([
    fetchSummary(),
    fetchPartiesMeta(),
  ]);

  const national = rows.filter((r) => r.scope === "national");
  // Sort by polled_on ASC for delta calculation; we flip at the end.
  national.sort((a, b) => a.polled_on.localeCompare(b.polled_on));

  const out: GeneralElectionRowViewModel[] = [];
  let prevTurnout: number | null = null;
  let prevLeadingSeats: number | null = null;
  for (const r of national) {
    const year = Number.parseInt(r.polled_on.slice(0, 4), 10);
    const delta =
      prevTurnout != null && r.turnout_pct != null
        ? round1(r.turnout_pct - prevTurnout)
        : null;
    const runnerUpSeats = r.runner_up_seats ?? 0;
    const majority_mark = Math.floor(r.seats_contested / 2) + 1;
    const majority = r.seats_won >= majority_mark;
    const mandate: MandateCell = {
      majority,
      gap: r.seats_won - majority_mark,
      label: majority ? "Majority" : `Short by ${majority_mark - r.seats_won}`,
    };
    out.push({
      event_id: r.event_id,
      year,
      polled_on: r.polled_on,
      leading: _buildPartyCell(r.leading_party_id, partiesMeta),
      seats_won: r.seats_won,
      seats_contested: r.seats_contested,
      vote_share_pct: null,
      turnout_pct: r.turnout_pct,
      turnout_delta_pp: delta,
      runner_up: r.runner_up_party_id
        ? {
            ..._buildPartyCell(r.runner_up_party_id, partiesMeta),
            seats: r.runner_up_seats ?? 0,
          }
        : null,
      detail_href: link.nationalElection(r.event_id),
      source_id: r.source_id,
      majority_mark,
      mandate,
      seat_swing:
        prevLeadingSeats != null ? r.seats_won - prevLeadingSeats : null,
      margin: r.seats_won - runnerUpSeats,
      others_seats: Math.max(
        0,
        r.seats_contested - r.seats_won - runnerUpSeats,
      ),
    });
    if (r.turnout_pct != null) prevTurnout = r.turnout_pct;
    prevLeadingSeats = r.seats_won;
  }
  // Citizen-facing: newest cycle first.
  out.reverse();
  return out;
}

function _buildPartyCell(
  party_id: string | null,
  partiesMeta: Map<string, PartyMeta>,
): LeadingPartyCell {
  if (!party_id) {
    return { party_id: null, short: "", color: "#94a3b8", detail_href: null };
  }
  const meta = partiesMeta.get(party_id);
  const short = meta?.short ?? _shortFromPartyId(party_id);
  const row = meta
    ? {
        party_id: meta.party_id,
        brand_colour: meta.brand_colour
          ? { hex: meta.brand_colour, confidence: "medium" as const }
          : null,
      }
    : null;
  const color = getPartyColor(party_id, row).hex;
  return {
    party_id,
    short,
    color,
    detail_href: link.party(party_id),
  };
}

function _shortFromPartyId(party_id: string): string {
  // Fallback: take the tail after the last `.` (e.g. "BJP" from
  // "parties.IN.BJP"). The parties.csv shipped today carries every
  // valid party so this fallback exists only to defend against a
  // future mart-vs-parties drift.
  const idx = party_id.lastIndexOf(".");
  return idx >= 0 ? party_id.slice(idx + 1) : party_id;
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

// --- Provenance footer ------------------------------------------------
//
// The 11 national rows all FK to datasets/data/entities/source.csv
// (Holy Law #9). The page resolves the distinct source_ids it actually
// rendered into deduped publisher pills for a single SourceList footer
// covering both the windowed chart and the table.

const SOURCE_REL = "datasets/data/entities/source.csv";
const SOURCE_URL = `${DATA_BASE}/data/entities/source.csv`;

interface RawSourceRow {
  source_id: string | null;
  producer: string | null;
  title: string | null;
  vintage: string | null;
  url: string | null;
}

let sourceRowsCache: Promise<SourceRow[]> | null = null;

/** Reset the source.csv cache; for tests and HMR. */
export function _resetGeneralElectionsSourcesCacheForTests(): void {
  sourceRowsCache = null;
}

/** Load + cache every row of source.csv via the typed read seam. */
async function loadAllSourceRows(): Promise<SourceRow[]> {
  if (sourceRowsCache) return sourceRowsCache;
  sourceRowsCache = (async () => {
    await registerCsvFile(SOURCE_URL);
    const clause = await csvColumnsClause(SOURCE_REL);
    const sql = `SELECT source_id, producer, title, vintage, url
      FROM read_csv('${SOURCE_URL}', ${clause}, header=true)`;
    const rows = await query<RawSourceRow>(sql);
    return rows
      .filter((r): r is RawSourceRow & { source_id: string } => !!r.source_id)
      .map((r) => ({
        source_id: r.source_id,
        producer: (r.producer ?? "").trim(),
        title: (r.title ?? "").trim(),
        vintage: (r.vintage ?? "").trim(),
        url: r.url && r.url.trim().length > 0 ? r.url.trim() : null,
      }));
  })().catch((err) => {
    sourceRowsCache = null;
    throw err;
  });
  return sourceRowsCache;
}

/** Options for `loadGeneralElectionsSources`. Tests inject overrides. */
export interface LoadGeneralElectionsSourcesOpts {
  loadSourceRowsOverride?: () => Promise<SourceRow[]>;
}

/** Resolve the distinct `source_ids` the page rendered into deduped
 *  publisher pills for the SourceList footer.
 *
 *  THROWS when a cited source_id is absent from source.csv - an FK
 *  violation (citation-ledger drift) that would otherwise render an
 *  unattributed citizen-facing surface (Holy Law #9 STOP-AND-SURFACE).
 *  An empty input yields `[]` (the renderer suppresses itself). */
export async function loadGeneralElectionsSources(
  source_ids: Iterable<string>,
  opts: LoadGeneralElectionsSourcesOpts = {},
): Promise<PublisherPill[]> {
  const wanted = new Set<string>();
  for (const id of source_ids) {
    if (id) wanted.add(id);
  }
  if (wanted.size === 0) return [];
  const fetchRows = opts.loadSourceRowsOverride ?? loadAllSourceRows;
  const all = await fetchRows();
  const byId = new Map(all.map((r) => [r.source_id, r] as const));
  const matched: SourceRow[] = [];
  for (const id of wanted) {
    const row = byId.get(id);
    if (!row) {
      throw new Error(
        `general-elections: source_id "${id}" cited by a national ` +
          `election row is not present in ${SOURCE_REL} (Holy Law #9)`,
      );
    }
    matched.push(row);
  }
  return dedupeToPills(matched);
}

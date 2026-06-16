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

import { getPartyColor } from "../colors/resolver";
import {
  loadEventSummary,
  type EventSummaryRow,
} from "../elections/event-summary-loader";
import { link } from "../links";
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
  for (const r of national) {
    const year = Number.parseInt(r.polled_on.slice(0, 4), 10);
    const delta =
      prevTurnout != null && r.turnout_pct != null
        ? round1(r.turnout_pct - prevTurnout)
        : null;
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
    });
    if (r.turnout_pct != null) prevTurnout = r.turnout_pct;
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

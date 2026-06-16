// Assembly-elections view-model (PR-E3 of TODO/20260615-elections-redesign-plan.md).
//
// Powers the redesigned `/t/elections/assemblies` route mounted in
// PR-E4 (AssemblyElections.svelte). Reads the per-event aggregate mart
// shipped by PR-E2 via `loadEventSummary()`, filters `scope='state'`,
// collapses to latest-per-state by polled_on descending, AND appends 5
// "no-legislature" card stubs for the UTs without state legislatures
// per ADR-0022 (constitutional honesty) so the citizen scrolling past
// Chandigarh / Lakshadweep / etc. sees an honest "no state legislature"
// signal rather than an absence.
//
// One card per state. ~30 with-legislature + 5 no-legislature today.
// (The 5 no-leg UT slug list mirrors
// `frontend/src/routes/StateOverview.svelte:NO_ASSEMBLY_UT_SLUGS`.)

import { getPartyColor } from "../colors/resolver";
import {
  loadEventSummary,
  type EventSummaryRow,
} from "../elections/event-summary-loader";
import { link } from "../links";
import { slugify } from "../slug";
import { fetchStates, type StateEntry } from "../data";
import { loadAllPartiesMeta, type PartyMeta } from "./parties";

/** State slugs that have NO legislative assembly per ADR-0022. Mirrored
 *  from frontend/src/routes/StateOverview.svelte:NO_ASSEMBLY_UT_SLUGS.
 *  The cards on the Assembly grid render an honest one-liner for these
 *  with no party pill and no year — the absence IS the citizen signal. */
export const NO_ASSEMBLY_UT_SLUGS: ReadonlySet<string> = new Set([
  "andaman-and-nicobar-islands",
  "chandigarh",
  "dadra-and-nagar-haveli-and-daman-and-diu",
  "ladakh",
  "lakshadweep",
]);

/** Citizen-render shape for one card on the Assembly grid. */
export interface AssemblyCardViewModel {
  state_code: string | null; // null for no-leg UTs
  state_slug: string;
  state_name: string;
  has_legislature: boolean;
  /** Present when the state has a legislature AND the mart has at
   *  least one matching event_id row. Otherwise null. */
  latest_event: LatestEventCell | null;
  /** Per-state hub href (`/<state-slug>`). Always present. */
  state_hub_href: string;
  /** Number of state-level events present in the mart for this state.
   *  Used by the card chrome ("11 elections on record"). 0 when none. */
  total_events_on_record: number;
}

/** Citizen-render shape for the latest-event cell inside a card. */
export interface LatestEventCell {
  event_id: string;
  year: number;
  polled_on: string;
  leading_party_id: string | null;
  leading_short: string;
  leading_color: string;
  /** Slug for the link to /parties/<slug>. NULL when not derivable. */
  leading_party_href: string | null;
  seats_won: number;
  seats_contested: number;
  turnout_pct: number | null;
  /** Per-state per-event drill-down href (StateElection route). */
  detail_href: string;
}

/** Options for the loader. Tests inject overrides. */
export interface LoadAssemblyElectionsOpts {
  loadEventSummaryOverride?: () => Promise<EventSummaryRow[]>;
  loadPartiesMetaOverride?: () => Promise<Map<string, PartyMeta>>;
  fetchStatesOverride?: () => Promise<{ states: StateEntry[] }>;
}

/** Project the event_summary mart into the Assembly cards.
 *
 *  Self-contained loader: by default fetches event_summary + parties
 *  metadata + states catalogue internally. Tests inject via opts.
 */
export async function loadAssemblyElections(
  opts: LoadAssemblyElectionsOpts = {},
): Promise<AssemblyCardViewModel[]> {
  const fetchSummary = opts.loadEventSummaryOverride ?? loadEventSummary;
  const fetchPartiesMeta = opts.loadPartiesMetaOverride ?? loadAllPartiesMeta;
  const fetchStatesFn = opts.fetchStatesOverride ?? fetchStates;
  const [rows, partiesMeta, statesEnvelope] = await Promise.all([
    fetchSummary(),
    fetchPartiesMeta(),
    fetchStatesFn(),
  ]);
  const stateEntries = statesEnvelope.states ?? [];

  // Group state-scope rows by state_code; for each state pick the row
  // with the latest polled_on.
  const stateRows = rows.filter(
    (r) => r.scope === "state" && r.state_code != null,
  );
  const byState = new Map<string, EventSummaryRow[]>();
  for (const r of stateRows) {
    const code = r.state_code!;
    const list = byState.get(code) ?? [];
    list.push(r);
    byState.set(code, list);
  }

  const out: AssemblyCardViewModel[] = [];

  // (1) With-legislature cards from the catalogue order (entities.json)
  for (const entry of stateEntries) {
    const slug = slugify(entry.name);
    if (NO_ASSEMBLY_UT_SLUGS.has(slug)) continue;
    const stateRowsForCode = byState.get(entry.eci_code) ?? [];
    if (stateRowsForCode.length === 0) {
      // State has a legislature per the catalogue BUT no mart row yet
      // (catalogue gap or pending ingest). Render a card without a
      // latest-event so the citizen sees "0 elections on record"
      // honestly rather than dropping the state entirely.
      out.push({
        state_code: entry.eci_code,
        state_slug: slug,
        state_name: entry.name,
        has_legislature: true,
        latest_event: null,
        state_hub_href: link.stateHub(slug),
        total_events_on_record: 0,
      });
      continue;
    }
    const latest = [...stateRowsForCode].sort((a, b) =>
      b.polled_on.localeCompare(a.polled_on),
    )[0];
    out.push({
      state_code: entry.eci_code,
      state_slug: slug,
      state_name: entry.name,
      has_legislature: true,
      latest_event: _buildLatestEventCell(latest, partiesMeta, slug),
      state_hub_href: link.stateHub(slug),
      total_events_on_record: stateRowsForCode.length,
    });
  }

  // (2) No-legislature UT cards (per ADR-0022). Use the catalogue's
  // own name for each slug if present; otherwise derive a title-case
  // display from the slug.
  for (const slug of NO_ASSEMBLY_UT_SLUGS) {
    const entry = stateEntries.find((s) => slugify(s.name) === slug);
    const display = entry?.name ?? titleCaseSlug(slug);
    out.push({
      state_code: entry?.eci_code ?? null,
      state_slug: slug,
      state_name: display,
      has_legislature: false,
      latest_event: null,
      state_hub_href: link.stateHub(slug),
      total_events_on_record: 0,
    });
  }

  return out;
}

function _buildLatestEventCell(
  row: EventSummaryRow,
  partiesMeta: Map<string, PartyMeta>,
  state_slug: string,
): LatestEventCell {
  const year = Number.parseInt(row.polled_on.slice(0, 4), 10);
  const party_id = row.leading_party_id;
  const meta = party_id ? partiesMeta.get(party_id) : undefined;
  const short = meta?.short ?? (party_id ? _shortFromPartyId(party_id) : "");
  const partyRow = meta
    ? {
        party_id: meta.party_id,
        brand_colour: meta.brand_colour
          ? { hex: meta.brand_colour, confidence: "medium" as const }
          : null,
      }
    : null;
  const color = party_id ? getPartyColor(party_id, partyRow).hex : "#94a3b8";
  return {
    event_id: row.event_id,
    year,
    polled_on: row.polled_on,
    leading_party_id: party_id,
    leading_short: short,
    leading_color: color,
    leading_party_href: party_id ? link.party(party_id) : null,
    seats_won: row.seats_won,
    seats_contested: row.seats_contested,
    turnout_pct: row.turnout_pct,
    detail_href: link.stateElection(state_slug, row.event_id),
  };
}

function _shortFromPartyId(party_id: string): string {
  const idx = party_id.lastIndexOf(".");
  return idx >= 0 ? party_id.slice(idx + 1) : party_id;
}

const CONNECTORS = new Set(["and", "of", "the"]);

function titleCaseSlug(slug: string): string {
  return slug
    .split("-")
    .map((w, idx) => {
      if (idx > 0 && CONNECTORS.has(w)) return w;
      return w.length === 0 ? w : w.charAt(0).toUpperCase() + w.slice(1);
    })
    .join(" ");
}

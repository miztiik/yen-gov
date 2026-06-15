/**
 * Pure helpers that turn an event_summary.csv row + the party + state
 * lookup tables into a ShareCardInput shape (R7 of
 * TODO/20260615-state-election-event-page-redesign-plan.md, J-elevated-14).
 *
 * Kept separate from build-svg.ts so the projection logic (label
 * resolution, brand-colour lookup, slug derivation, scope=state vs
 * national branching) can be unit-tested without rasterising any
 * SVG. The build script in `frontend/scripts/build-share-cards.ts`
 * is the only place that touches disk + @resvg/resvg-js; this module
 * stays pure.
 */

import type { ShareCardInput } from "./build-svg";

/** Subset of event_summary.csv columns the projection needs. */
export interface EventSummaryRowForCard {
  event_id: string;
  /** NULL for scope=national rows; set for scope=state rows. */
  state_code: string | null;
  scope: "national" | "state";
  kind: "parliament" | "assembly" | "assembly_bye" | "general_bye" | "by_election";
  polled_on: string;
  leading_party_id: string | null;
  seats_won: number;
  seats_contested: number;
  source_id: string;
}

/** Subset of parties.csv columns the projection needs. */
export interface PartyRowForCard {
  party_id: string;
  short: string;
  brand_colour: string;
}

/** Subset of state-resolution columns. */
export interface StateRowForCard {
  /** ECI state code, e.g. "S13". */
  state_code: string;
  /** Citizen-visible name, e.g. "Maharashtra". */
  state_name: string;
  /** LGD slug used in URL paths, e.g. "maharashtra". */
  state_slug: string;
}

/** Subset of source.csv columns - just what the footer line needs. */
export interface SourceRowForCard {
  source_id: string;
  /** Publisher + title joined, e.g. "Election Commission of India". */
  producer: string;
}

/** Render plan for one card: where to write + what to put in the SVG. */
export interface CardPlan {
  /** Workspace-relative output path under frontend/public, e.g.
   *  "share/maharashtra/assembly-2024.png" or "share/national/general-2024.png". */
  output_rel_path: string;
  /** Composed shape consumed by buildShareCardSvg. */
  card: ShareCardInput;
}

/** State slug for the rare national-scope row (no state_code). */
const NATIONAL_SLUG = "national";

/** Citizen-visible name for the national scope. */
const NATIONAL_LABEL = "India";

/** Body labels keyed by event kind. */
function bodyLabelForKind(kind: EventSummaryRowForCard["kind"]): string {
  if (kind === "parliament") return "Parliament";
  if (kind === "general_bye") return "Parliament By-election";
  if (kind === "assembly_bye") return "Assembly By-election";
  if (kind === "by_election") return "By-election";
  return "Assembly";
}

/** Year as a 4-digit string extracted from the event_id; falls back
 *  to the polled_on year. */
function yearFromEventId(event_id: string, polled_on: string): string {
  const m = /(\d{4})/.exec(event_id);
  if (m) return m[1];
  return polled_on.slice(0, 4);
}

/**
 * Build the per-row card plan. Returns `null` when the row cannot be
 * rendered (no state lookup hit for a state-scope row, etc.) so the
 * build script can skip cleanly without throwing.
 */
export function buildCardPlan({
  row,
  parties_by_id,
  states_by_code,
  sources_by_id,
}: {
  row: EventSummaryRowForCard;
  parties_by_id: ReadonlyMap<string, PartyRowForCard>;
  states_by_code: ReadonlyMap<string, StateRowForCard>;
  sources_by_id: ReadonlyMap<string, SourceRowForCard>;
}): CardPlan | null {
  let scope_label: string;
  let state_slug: string;
  if (row.scope === "national") {
    scope_label = NATIONAL_LABEL;
    state_slug = NATIONAL_SLUG;
  } else {
    if (!row.state_code) return null; // mart contract: state-scope rows carry state_code
    const sr = states_by_code.get(row.state_code);
    if (!sr) return null; // unresolvable state - skip rather than render garbage
    scope_label = sr.state_name;
    state_slug = sr.state_slug;
  }

  const winner_party = row.leading_party_id
    ? parties_by_id.get(row.leading_party_id) ?? null
    : null;

  const seats_summary = `${row.seats_won} of ${row.seats_contested}`;
  const year_label = yearFromEventId(row.event_id, row.polled_on);
  const body_label = bodyLabelForKind(row.kind);

  const source = sources_by_id.get(row.source_id) ?? null;
  // The event_summary mart's own source row attributes the producer
  // as "yen-gov" (it IS a derived mart we wrote) - but for
  // citizen-facing share cards every electoral row's upstream IS
  // ECI (we derive event_summary from per-event ECI summary.csv +
  // candidacies.csv files). Reading "Source: yen-gov" on the card
  // would be a Generalisation that obscures the actual publisher.
  // When the resolved producer is "yen-gov", normalise to the
  // upstream attribution; otherwise honour the producer verbatim
  // (one-off rows attributed to a different publisher still read
  // honestly).
  const producer_resolved =
    source && source.producer.toLowerCase().includes("yen-gov")
      ? "Election Commission of India"
      : source?.producer ?? "Election Commission of India";
  const source_line = `Source: ${producer_resolved}`;

  return {
    output_rel_path: `share/${state_slug}/${row.event_id}.png`,
    card: {
      seats_summary,
      winner_label: winner_party?.short ?? null,
      winner_colour_hex: winner_party?.brand_colour ?? null,
      scope_label,
      body_label,
      year_label,
      source_line,
    },
  };
}

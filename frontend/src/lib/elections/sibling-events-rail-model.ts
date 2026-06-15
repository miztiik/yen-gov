/**
 * sibling-events-rail-model: pure projection that turns the election
 * events catalogue + the current event identity into the chip-rail
 * shape that `<SiblingEventsRail>` renders.
 *
 * R4 of TODO/20260615-state-election-event-page-redesign-plan.md
 * (2026-06-15): the Jony year-chip rail (J-elevated-4) replaces the
 * deleted "Prev / Next / Compare ->" text strip. The rail mounts
 * between `<StateEventHero>` and `<StateEventMap>` and shows one chip
 * per same-body sibling event for this state, sorted oldest-to-newest,
 * with a winner-color 2px underline per chip and a trailing
 * "Compare with {prior_year}" pill when a prior event exists. NO
 * arrows, NO chevrons, NO Prev/Next labels per the user's 2026-06-15
 * direction ("make the app for 2027 ready, not 1990 ready").
 *
 * This module is the pure projection seam; the Svelte component reads
 * the shape and renders. Keeping the math here lets vitest assert the
 * sort order, single-event edge case, year-label derivation, and the
 * compare-href construction without mounting Svelte. The winner-color
 * resolver is injected so tests can stub it; production passes a
 * closure over the loaded event_summary mart.
 */

import type {
  ElectionEventRow,
  ElectionEventsCatalogue,
  EventKind,
} from "../election-events";
import { listEventsForState } from "../election-events";

/** One year-chip in the rail. */
export interface SiblingEventChip {
  event_id: string;
  /** Year shown on the pill, e.g. "2024". For same-year same-kind
   *  collisions (catalogue v1.4 grammar; anchor Bihar 2005 Feb/Nov)
   *  the label widens to e.g. "2005 FEB" so the citizen can tell
   *  the two pills apart at a glance. */
  year_label: string;
  /** Full event display for the chip's screen-reader / title text. */
  display: string;
  /** ISO YYYY-MM-DD polled_on — used for sort stability + tests. */
  polled_on: string;
  /** Canonical href to this event's state page. */
  href: string;
  /** Winner party color hex; null when the winner is unknown or the
   *  resolver returned no mart row. The Svelte component falls back
   *  to the slate-200 underline when this is null. */
  winner_color_hex: string | null;
  /** True iff this chip represents the event the citizen is reading. */
  is_current: boolean;
}

/** The rail's full render shape. */
export interface SiblingEventsRailModel {
  /** All same-body sibling chips, sorted ASC by polled_on. */
  events: SiblingEventChip[];
  /** Year of the prior same-body event for the Compare pill; null
   *  when no prior event exists (this is the first event of this body
   *  on record for the state). */
  prior_year: number | null;
  /** Compare-route href; null when no prior event exists. */
  compare_href: string | null;
}

/**
 * Map the route's body discriminator (the URL-derived "ac" / "pc")
 * to the catalogue's `kind` enum. The rail intentionally surfaces
 * ONLY the primary kind per body — by-elections, partial polls, and
 * post-poll re-elections live on a separate surface; mixing them
 * into the same chip rail would muddy the citizen's mental model of
 * "the sequence of full Assembly / Parliament elections for this
 * state". See plan-doc Section 5 R4 spec for the J-elevated-4
 * verdict ("Spotify Now Playing pattern — one row of equally
 * weighted year chips").
 */
export function siblingKindFor(body: "ac" | "pc"): EventKind {
  return body === "ac" ? "assembly" : "parliament";
}

/**
 * Derive the year label for a chip. For the standard
 * `<kind>-<YYYY>` event_id shape we strip the kind prefix and emit
 * the bare year ("2024"). For the future catalogue v1.4 grammar
 * `<kind>-<YYYY>-<month-slug>` (Bihar 2005 Feb/Nov; not on disk yet)
 * we emit "YYYY MMM" so collision pills read distinctly. Falls back
 * to the event_id verbatim if neither shape matches.
 */
export function deriveYearLabel(event_id: string): string {
  // Match e.g. "assembly-2024", "parliament-2019", "general-2024".
  const standard = /^[a-z_]+-(\d{4})$/.exec(event_id);
  if (standard) return standard[1];
  // Match e.g. "assembly-2005-feb", "assembly-2005-nov".
  const month = /^[a-z_]+-(\d{4})-([a-z]{3,})$/.exec(event_id);
  if (month) return `${month[1]} ${month[2].toUpperCase()}`;
  return event_id;
}

/**
 * Derive the calendar year as a number from an event_id; null when
 * the event_id does not embed a 4-digit year.
 */
export function deriveYearNumber(event_id: string): number | null {
  const m = /^[a-z_]+-(\d{4})/.exec(event_id);
  if (!m) return null;
  const year = parseInt(m[1], 10);
  return Number.isFinite(year) ? year : null;
}

/**
 * Build the rail model.
 *
 * Pure projection; deterministic given the same inputs. The
 * `winner_color_for_event_id` callback is the only side-channel: in
 * production it closes over the loaded `event_summary` mart so the
 * underline matches each year's actual winner; in tests it returns a
 * stub. When the resolver returns null for an event_id, the chip's
 * `winner_color_hex` is null and the rendered underline falls back to
 * the slate-200 baseline.
 */
export function buildSiblingEventsRail({
  catalogue,
  state_code,
  state_slug,
  current_event_id,
  body,
  winner_color_for_event_id,
}: {
  catalogue: ElectionEventsCatalogue;
  state_code: string;
  state_slug: string;
  current_event_id: string;
  body: "ac" | "pc";
  winner_color_for_event_id: (event_id: string) => string | null;
}): SiblingEventsRailModel {
  const target_kind = siblingKindFor(body);
  const all = listEventsForState(catalogue, state_code).filter(
    (e) => e.kind === target_kind,
  );
  // Sort oldest-to-newest so the citizen reads left-to-right in time.
  all.sort((a, b) => a.polled_on.localeCompare(b.polled_on));

  const events: SiblingEventChip[] = all.map((e: ElectionEventRow) => {
    const winner_color_hex = winner_color_for_event_id(e.event_id);
    return {
      event_id: e.event_id,
      year_label: deriveYearLabel(e.event_id),
      display: e.display,
      polled_on: e.polled_on,
      href: `/${state_slug}/elections/${encodeURIComponent(e.event_id)}`,
      winner_color_hex,
      is_current: e.event_id === current_event_id,
    };
  });

  const current_idx = events.findIndex((c) => c.is_current);
  // Prior = the chip immediately to the left of the current one. When
  // the current event is the first chip (or missing entirely), there
  // is no prior to compare against — silently omit the trailing
  // Compare pill rather than render a disabled stub.
  const has_prior = current_idx > 0;
  const prior = has_prior ? events[current_idx - 1] : null;
  const prior_year = prior ? deriveYearNumber(prior.event_id) : null;
  const compare_href = prior
    ? `/compare/elections/${state_slug}/${encodeURIComponent(prior.event_id)}/${encodeURIComponent(current_event_id)}`
    : null;

  return { events, prior_year, compare_href };
}

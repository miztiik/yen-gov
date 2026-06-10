// Home elections rail view-model.
//
// PR-W4d (2026-06-10): replaces the prior "almost useless, hangs without
// context" elections experience on Home with a 3-card rail (anchor + hook
// + door) per Jony Q4 verdict in
// TODO/20260609-election-experience-overhaul-plan.md.
//
// Pure async composer; no DOM. Driven by:
//   - fetchElectionEvents() (the per-state events catalogue)
//   - loadElectionResults({event}) at NATIONAL-PC scope for the "closest
//     race" hook.
//
// Anchor:  most-recent parliament event flagged `data_status: "complete"`,
//          picked by max(polled_on) across every state's row list. Why
//          parliament-only: the loader's national-scope arm only supports
//          parliament events today (see runNationalPcQuery contract). An
//          assembly anchor would have no "national results" to surface
//          and would not match the brief's example.
// Hook:    smallest `margin_pct` winner row from the anchor event's
//          NATIONAL-PC results. Link points at the state-event landing
//          (`/<state>/elections/<event>`) since a PC-level URL leaf is
//          not minted yet (PR-W3b's <constituency-slug> leaf is AC-only).
//          Subtitle names the seat + margin so the citizen sees the hook
//          even before clicking.
// Door:    static `/t/elections` firehose link (no view-model needed).
//
// If the catalogue has no eligible parliament event, the builder throws
// (Home.svelte renders the loading skeleton arm; caller may degrade).
// If the hook loader fails or returns zero rows, the hook degrades to a
// static "Latest event highlights" + the same state-event landing for
// the anchor event so the card stays clickable.

import {
  fetchElectionEvents,
  type ElectionEventRow,
  type ElectionEventsCatalogue,
} from "../election-events";
import {
  loadElectionResults,
  type ElectionResultRow,
} from "./election-results";
import { link } from "../links";

export interface AnchorCard {
  title: string;
  subtitle: string;
  href: string;
}

export interface HookCard {
  title: string;
  subtitle: string;
  href: string;
}

export interface DoorCard {
  title: string;
  href: string;
}

export interface HomeElectionsRailPayload {
  anchor: AnchorCard;
  hook: HookCard;
  door: DoorCard;
}

/**
 * Walk every state row list and return the parliament event with
 * `data_status === "complete"` whose `polled_on` is the most recent.
 * Returns null when no such event exists. The catalogue stores the same
 * national event under each state's array (state slice rows); de-dup on
 * `event_id` so the picker is deterministic on the cohort, not on which
 * state happens to be first.
 */
export function pickAnchorEvent(
  catalogue: ElectionEventsCatalogue,
): ElectionEventRow | null {
  const seen = new Set<string>();
  let best: ElectionEventRow | null = null;
  for (const rows of Object.values(catalogue.states)) {
    for (const row of rows) {
      if (row.kind !== "parliament") continue;
      if (row.data_status !== "complete") continue;
      if (seen.has(row.event_id)) continue;
      seen.add(row.event_id);
      if (best === null || row.polled_on > best.polled_on) {
        best = row;
      }
    }
  }
  return best;
}

/** Year extracted from ISO `YYYY-MM-DD`. */
function yearOf(polled_on: string): string {
  return polled_on.slice(0, 4);
}

/** Smallest `margin_pct` winner row (the "closest race"). Skips rows where
 *  margin_pct is null (long-tail constituencies the upstream omitted).
 *  Returns null when no row carries a numeric margin. */
export function pickClosestRace(
  rows: readonly ElectionResultRow[],
): ElectionResultRow | null {
  let best: ElectionResultRow | null = null;
  for (const row of rows) {
    if (!row.is_winner) continue;
    if (row.margin_pct === null) continue;
    if (best === null || row.margin_pct < (best.margin_pct as number)) {
      best = row;
    }
  }
  return best;
}

/** Format a margin percentage for citizen display (1 decimal place). */
function formatMargin(margin_pct: number): string {
  return `${margin_pct.toFixed(1)}%`;
}

/** Compose the 3-card payload. Pure; consumes the catalogue + loader
 *  outputs already resolved.
 *
 *  Exported so tests can exercise composition without re-mocking fetch. */
export function composeRail(
  catalogue: ElectionEventsCatalogue,
  anchor_event: ElectionEventRow,
  national_rows: readonly ElectionResultRow[],
): HomeElectionsRailPayload {
  const year = yearOf(anchor_event.polled_on);
  const anchor: AnchorCard = {
    title: `Parliament ${year}`,
    subtitle: "National results",
    href: link.nationalElection(anchor_event.event_id),
  };
  const closest = pickClosestRace(national_rows);
  const hook: HookCard = closest !== null
    ? {
        title: `${year}'s closest seat`,
        subtitle: `${closest.entity_name} - margin ${formatMargin(closest.margin_pct as number)}`,
        href: link.stateElection(closest.state_slug, anchor_event.event_id),
      }
    : {
        // Degraded: loader returned no rows with a numeric margin, OR
        // status was failed/partial. Card still routes the citizen into
        // the cascade.
        title: `Parliament ${year}`,
        subtitle: "Latest event highlights",
        href: link.nationalElection(anchor_event.event_id),
      };
  // Silence the unused-parameter lint; catalogue is in the signature so
  // future hook strategies (closest-across-events, etc.) can read it
  // without a breaking change.
  void catalogue;
  const door: DoorCard = {
    title: "All elections",
    href: "/t/elections",
  };
  return { anchor, hook, door };
}

/** End-to-end builder: load the catalogue + national results, compose. */
export async function buildHomeElectionsRail(): Promise<HomeElectionsRailPayload> {
  const catalogue = await fetchElectionEvents();
  const anchor_event = pickAnchorEvent(catalogue);
  if (anchor_event === null) {
    throw new Error(
      "home-elections-rail: no parliament event with data_status='complete' in catalogue",
    );
  }
  const result = await loadElectionResults({ event: anchor_event.event_id });
  const rows = result.status === "ok" ? result.data : [];
  return composeRail(catalogue, anchor_event, rows);
}

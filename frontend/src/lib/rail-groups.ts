// Pure builder for the LeftRail's grouped IA (IA-reset Step #1.5).
//
// The rail's structure is data, not view: this module returns the list of
// groups and items the rail should render, given the current scope and the
// per-state default election event. The view (`LeftRail.svelte`) is a
// straight render of this output — no conditionals, no greyed stubs.
//
// Doctrine (IA-reset §1, see TODO/20260515-state-page-ia-rework-plan.md):
//
//   * Three groups, state-aware:
//       THIS STATE · ACROSS STATES · ABOUT
//   * THIS STATE lists Overview + one entry per topic in the catalogue we
//     surface; when a state is in scope, topic entries point at
//     `/s/<state>/t/<topic>` (per-state-topic view, IA-reset Step #2).
//     Without a state, the group collapses to a single hint line.
//   * NO greyed dead links. When no state is in scope, THIS STATE
//     collapses to a single hint line ("Pick a state above…") and the
//     topic sub-items are omitted entirely.
//   * The previous "Centre and states" group + "Side by side" /
//     "Explore trends" / Settings / Repo rail entries are killed in this
//     pass. The corresponding ROUTES (`/s/<state>/explore`, `/settings`,
//     `/compare/<state>/<event>`) still resolve directly by URL — only
//     the rail surfaces are removed. Repo lives on the About page.
//
// Tested by rail-groups.test.ts.

import { url } from "./url";

/** A single navigable entry in the rail. Disabled items are NEVER emitted. */
export interface RailItem {
  /** Stable ID for keyed rendering and tests. */
  id: string;
  /** Visible label. */
  label: string;
  /** href as already prefixed by `url.*` builders, OR an external URL. */
  href: string;
  /** True when the item points outside the SPA (opens in new tab). */
  external?: boolean;
  /** Predicate for "current" highlighting against `route.path` (un-prefixed). */
  match: (path: string) => boolean;
}

/** A group header + its items. May be empty (no items) iff `hint` explains why. */
export interface RailGroup {
  /** Stable ID for keyed rendering and tests. */
  id: string;
  /** Group header. */
  label: string;
  items: RailItem[];
  /** Single neutral line shown when items is empty (e.g. "Pick a state above"). */
  hint?: string;
}

export interface BuildRailGroupsArgs {
  /** ECI state code from scope, or null on India / unscoped routes. */
  state: string | null;
  /**
   * Default event_id for the current state. Carried through the signature
   * for future surfaces that need it; the current rail (Step #1.5) does
   * not render a state+event item, so it's unused by the builder today.
   */
  defaultEvent: string | null;
  /**
   * Repo URL — carried through for any future external rail link. Not
   * rendered today (Repo moved to the About page in Step #1.5).
   */
  repoUrl: string;
  /**
   * `topic_id → topic.title` map, sourced from
   * `datasets/taxonomy/topics.json`. The rail's THIS STATE
   * topic items render `topicTitles.get(id) ?? id` so the rail label
   * AND the page H1 on `/s/<state>/t/<id>` are SINGLE-SOURCED off the
   * catalogue. Two surfaces showing the same thing show the same string
   * (Jony 2026-05-16 design review — see TODO/20260515-state-page-ia-
   * rework-plan.md §11 follow-up #5). Pass `null` while the catalogue is
   * still loading; the builder will fall back to ids so the rail renders
   * something (not pretty, but present) instead of blocking.
   */
  topicTitles: ReadonlyMap<string, string> | null;
}

/**
 * The fixed topic id list under THIS STATE (in display order). Each id
 * MUST exist in `datasets/taxonomy/topics.json` — labels are
 * derived from `topic.title` via the `topicTitles` map (Jony 2026-05-16:
 * the rail does not carry its own label dictionary; the catalogue IS the
 * dictionary). Order is deliberate: money + power first (highest citizen
 * pull), then economy → people → environment → transport → elections.
 *
 * `human-development` and `demography` are intentionally absent — they
 * exist in the catalogue (Topic Front Door surfaces them) but are NOT
 * promoted into the per-state rail; this is a curatorial decision.
 */
const THIS_STATE_TOPIC_IDS: ReadonlyArray<string> = [
  "fiscal",
  "energy",
  "economy",
  "health",
  "environment",
  "transport",
  "elections",
];

/**
 * Build the rail's groups for the current scope.
 *
 * Pure function — no Svelte stores, no fetch. The view passes in the
 * already-resolved scope/event/repo and renders whatever comes back.
 */
export function buildRailGroups(args: BuildRailGroupsArgs): RailGroup[] {
  const { state, topicTitles } = args;

  const this_state: RailGroup = state
    ? {
        id: "this-state",
        label: "This state",
        items: [
          {
            id: "this-state.overview",
            label: "Overview",
            href: url.state(state),
            // Highlight on /s/<slug> exactly, NOT on its sub-pages.
            match: p =>
              p.startsWith("/s/") &&
              !p.includes("/explore") &&
              !p.includes("/ac/") &&
              !p.includes("/party/") &&
              !p.includes("/t/"),
          },
          ...THIS_STATE_TOPIC_IDS.map(id => ({
            id: `this-state.topic.${id}`,
            label: topicTitles?.get(id) ?? id,
            // IA-reset Step #2: with a state in scope, topic links go to
            // the per-state-topic view, not the national /t/<id> page.
            href: url.stateTopic(state, id),
            match: (p: string) =>
              p.startsWith("/s/") && p.endsWith(`/t/${id}`),
          })),
        ],
      }
    : {
        id: "this-state",
        label: "This state",
        items: [],
        hint: "Pick a state above to see your data.",
      };

  const across_states: RailGroup = {
    id: "across-states",
    label: "Across states",
    items: [
      {
        id: "across-states.compare",
        label: "Compare states",
        href: url.compareIndicator(),
        match: p => p === "/compare",
      },
      {
        id: "across-states.all-topics",
        label: "All topics",
        href: url.topics(),
        match: p => p === "/t",
      },
    ],
  };

  const about: RailGroup = {
    id: "about",
    label: "About",
    items: [
      {
        id: "about.about",
        label: "About & sources",
        href: url.about(),
        match: p => p === "/about",
      },
    ],
  };

  return [this_state, across_states, about];
}

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
//     surface; entries point at the national `/t/<topic>` page for now —
//     per-state-topic routes (`/s/<state>/t/<topic>`) are Step #2's work
//     and intentionally NOT pre-built here.
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
}

/**
 * The fixed topic list under THIS STATE (in display order). Each topic ID
 * MUST exist in datasets/reference/in/topic-catalogue.json — entries are
 * deliberately ordered to put money + power first (highest citizen pull),
 * then economy → people → environment → transport → elections.
 *
 * Labels are citizen-readable noun phrases, NOT schema slugs. The slugs
 * stay opaque keys; labels are tuned for the rail width and Indian
 * citizen comprehension per docs/concepts/citizen-first.md.
 *
 * Catalogue alignment (verified 2026-05-16): no `human-development` topic
 * exists — `health` is its closest analogue and is used here with the
 * citizen-friendly label "People & health". Likewise `environment` and
 * `transport` are separate catalogue entries and surface as separate
 * rail entries rather than the plan-doc's combined "Environment &
 * transport" label.
 */
const THIS_STATE_TOPICS: ReadonlyArray<{ id: string; label: string }> = [
  { id: "fiscal", label: "Money & debt" },
  { id: "energy", label: "Power & energy" },
  { id: "economy", label: "Economy" },
  { id: "health", label: "People & health" },
  { id: "environment", label: "Environment" },
  { id: "transport", label: "Transport" },
  { id: "elections", label: "Elections" },
];

/**
 * Build the rail's groups for the current scope.
 *
 * Pure function — no Svelte stores, no fetch. The view passes in the
 * already-resolved scope/event/repo and renders whatever comes back.
 */
export function buildRailGroups(args: BuildRailGroupsArgs): RailGroup[] {
  const { state } = args;

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
              !p.includes("/party/"),
          },
          ...THIS_STATE_TOPICS.map(t => ({
            id: `this-state.topic.${t.id}`,
            label: t.label,
            href: url.topic(t.id),
            match: (p: string) => p === `/t/${t.id}`,
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

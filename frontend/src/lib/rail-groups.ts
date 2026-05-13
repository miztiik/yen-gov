// Pure builder for the LeftRail's grouped IA (P3.3c, IA reset).
//
// The rail's structure is data, not view: this module returns the list of
// groups and items the rail should render, given the current scope and the
// per-state default election event. The view (`LeftRail.svelte`) is a
// straight render of this output — no conditionals, no greyed stubs.
//
// Doctrine (P3.3c, see TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md
// §"P3.3c — IA decision pending"):
//
//   * Groups, not a flat list. Top-level: My state / How states compare /
//     Centre and states / Settings.
//   * NO greyed dead links. Sub-items that need a prerequisite (state +
//     event for "Side by side") are simply omitted until satisfied; the
//     group instead surfaces a one-line hint when it's empty for a
//     contextual reason.
//   * "Psephlab" is killed from the rail entirely — it's reachable only
//     from election artifacts.
//   * "Centre and states" is rendered with one /t/fiscal entry today plus
//     a "more topics coming" line; will fill out as Union-list topics ship.
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
  /** Default event_id for the current state, resolved from election-events. */
  defaultEvent: string | null;
  /** Repo URL for the external "Repo" link in Settings group. */
  repoUrl: string;
}

/**
 * Build the rail's groups for the current scope.
 *
 * Pure function — no Svelte stores, no fetch. The view passes in the
 * already-resolved scope/event/repo and renders whatever comes back.
 */
export function buildRailGroups(args: BuildRailGroupsArgs): RailGroup[] {
  const { state, defaultEvent, repoUrl } = args;

  const my_state: RailGroup = state
    ? {
        id: "my-state",
        label: "My state",
        items: [
          {
            id: "my-state.overview",
            label: "Overview",
            href: url.state(state),
            // Highlight on /s/<slug> exactly, NOT on its sub-pages.
            match: p => p.startsWith("/s/") && !p.includes("/explore") && !p.includes("/ac/") && !p.includes("/party/"),
          },
          {
            id: "my-state.trends",
            label: "Explore trends",
            href: url.explore(state),
            match: p => p.endsWith("/explore"),
          },
        ],
      }
    : {
        id: "my-state",
        label: "My state",
        items: [],
        hint: "Pick a state above to see your data.",
      };

  const compare_items: RailItem[] = [
    {
      id: "compare.all-topics",
      label: "All topics",
      href: url.topics(),
      match: p => p === "/t",
    },
    {
      id: "compare.fiscal",
      label: "Money & debt",
      href: url.topic("fiscal"),
      match: p => p === "/t/fiscal",
    },
    {
      id: "compare.energy",
      label: "Power & energy",
      href: url.topic("energy"),
      match: p => p === "/t/energy",
    },
    {
      id: "compare.elections",
      label: "Elections",
      href: url.topic("elections"),
      match: p => p === "/t/elections",
    },
  ];
  // Side-by-side requires both a chosen state AND an event — otherwise
  // hidden (per P3.3c "no greyed stubs" rule).
  if (state && defaultEvent) {
    compare_items.push({
      id: "compare.side-by-side",
      label: "Side by side",
      href: url.compare(state, defaultEvent),
      match: p => p.startsWith("/compare/"),
    });
  }
  const compare: RailGroup = {
    id: "how-states-compare",
    label: "How states compare",
    items: compare_items,
  };

  // Centre & states: only one topic exists today (fiscal/net-transfers).
  // Hint signals that more is coming so the group doesn't read as broken.
  const centre_states: RailGroup = {
    id: "centre-and-states",
    label: "Centre and states",
    items: [
      {
        id: "centre.fiscal",
        label: "Money & debt",
        href: url.topic("fiscal"),
        match: p => p === "/t/fiscal",
      },
    ],
    hint: "More topics coming soon.",
  };

  const settings: RailGroup = {
    id: "settings",
    label: "Settings",
    items: [
      {
        id: "settings.settings",
        label: "Settings",
        href: url.settings(),
        match: p => p === "/settings",
      },
      {
        id: "settings.about",
        label: "About",
        href: url.about(),
        match: p => p === "/about",
      },
      {
        id: "settings.repo",
        label: "Repo",
        href: repoUrl,
        external: true,
        match: () => false,
      },
    ],
  };

  return [my_state, compare, centre_states, settings];
}

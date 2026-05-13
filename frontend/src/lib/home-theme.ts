/**
 * Home-page map "theme" — a tiny, schema-driven dispatcher that lets the
 * citizen swap the India choropleth between the election lens (every state
 * coloured by leading party in its own default event) and any national-scope
 * indicator artifact from the topic catalogue.
 *
 * Two themes ship in v0:
 *   - `election` — the existing `IndiaMap` renderer (party-coloured).
 *   - `indicator/<artifact-id>` — `IndicatorChoropleth` over that artifact.
 *
 * URL contract (P5 of the IA reset):
 *   /?theme=election
 *   /?theme=indicator/fiscal/outstanding_debt_pct_gsdp
 *
 * Default = `{ kind: "election" }` for now. The IA-RESET TODO calls for
 * "Default theme defers to current event window when one is live"; today
 * every event in `election-events.json` is `data_status: complete`, so
 * there is no live window to defer to. When/if a live event lands, hook
 * the default-theme logic here without touching the renderer.
 *
 * Bad / unknown `?theme=` values fall back to the default silently — same
 * graceful-degradation contract as `?peer=` on `/t/:topic`.
 */

import type { CatalogueArtifact, CatalogueTopic, TopicCatalogue } from "./catalogue";

export type HomeTheme =
  | { kind: "election" }
  | { kind: "indicator"; id: string };

export interface HomeThemeOption {
  /** URL-param value for `?theme=…`. */
  value: string;
  /** Short label for the theme chip / `<select>` option. */
  label: string;
  /** Caption that follows the "India — " prefix above the map. */
  caption: string;
  /** Topic title (or "Elections") for grouping in the chooser. */
  group: string;
  theme: HomeTheme;
}

const ELECTION_VALUE = "election";
const ELECTION_LABEL = "Leading party";
const ELECTION_CAPTION = "leading party by state";
const ELECTION_GROUP = "Elections";

/** Every national-scope indicator artifact in the catalogue, in catalogue order. */
function nationalIndicators(
  catalogue: TopicCatalogue | null,
): Array<{ topic: CatalogueTopic; artifact: CatalogueArtifact }> {
  const out: Array<{ topic: CatalogueTopic; artifact: CatalogueArtifact }> = [];
  for (const t of catalogue?.topics ?? []) {
    for (const a of t.artifacts) {
      if (a.kind !== "indicator") continue;
      if ((a.scope ?? "national") !== "national") continue;
      out.push({ topic: t, artifact: a });
    }
  }
  return out;
}

/** True iff the catalogue has an indicator artifact with this id. */
function hasIndicator(catalogue: TopicCatalogue | null, id: string): boolean {
  return nationalIndicators(catalogue).some(({ artifact }) => artifact.id === id);
}

/**
 * Parse `?theme=…` against the catalogue. Returns null when the slot is
 * missing OR malformed OR refers to an indicator the catalogue doesn't know
 * about — caller should substitute `defaultHomeTheme(catalogue)`.
 */
export function parseHomeTheme(
  search: string | URLSearchParams,
  catalogue: TopicCatalogue | null,
): HomeTheme | null {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const raw = params.get("theme");
  if (raw === null) return null;
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  if (trimmed === ELECTION_VALUE) return { kind: "election" };
  const prefix = "indicator/";
  if (!trimmed.startsWith(prefix)) return null;
  const id = trimmed.slice(prefix.length);
  if (id === "") return null;
  if (!hasIndicator(catalogue, id)) return null;
  return { kind: "indicator", id };
}

/**
 * Serialize a theme to the URL-param value. Returns `""` for the default
 * theme (so the caller can drop the `?theme=` slot from the URL entirely
 * and keep clean shareable links).
 */
export function serializeHomeTheme(theme: HomeTheme): string {
  if (theme.kind === "election") return "";
  return `indicator/${theme.id}`;
}

/**
 * Default theme. Always election today; placeholder for future
 * "current event window" detection (see file header).
 */
export function defaultHomeTheme(_catalogue: TopicCatalogue | null): HomeTheme {
  return { kind: "election" };
}

/** True when two themes refer to the same view. */
export function sameTheme(a: HomeTheme, b: HomeTheme): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "election") return true;
  return a.id === (b as { kind: "indicator"; id: string }).id;
}

/** Caption rendered after "India — " above the map. */
export function themeCaption(
  theme: HomeTheme,
  catalogue: TopicCatalogue | null,
): string {
  if (theme.kind === "election") return ELECTION_CAPTION;
  for (const { artifact } of nationalIndicators(catalogue)) {
    if (artifact.id === theme.id) {
      return artifact.display ?? artifact.id;
    }
  }
  return theme.id;
}

/**
 * Full chooser list: election first, then every national indicator
 * grouped by topic title. Stable order = catalogue order.
 */
export function homeThemeOptions(catalogue: TopicCatalogue | null): HomeThemeOption[] {
  const out: HomeThemeOption[] = [
    {
      value: ELECTION_VALUE,
      label: ELECTION_LABEL,
      caption: ELECTION_CAPTION,
      group: ELECTION_GROUP,
      theme: { kind: "election" },
    },
  ];
  for (const { topic, artifact } of nationalIndicators(catalogue)) {
    const label = artifact.display ?? artifact.id;
    out.push({
      value: `indicator/${artifact.id}`,
      label,
      caption: label,
      group: topic.title,
      theme: { kind: "indicator", id: artifact.id },
    });
  }
  return out;
}

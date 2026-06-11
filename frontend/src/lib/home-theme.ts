/**
 * Home-page map "theme" — a tiny, schema-driven dispatcher that lets the
 * citizen swap the India choropleth between the election lens (every state
 * coloured by winning party in its own default event) and any national-scope
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
 * Default theme: deterministic day-of-year rotation across the
 * `CURATED_DEFAULT_THEMES` pool (one indicator per topic family, see the
 * constant below). Same calendar day yields the same default for every
 * visitor — shareable, debuggable, refresh-stable. Election theme survives
 * as the explicit `?theme=election` choice. Closes the IA-RESET P5
 * deferred item #3 ("Default Home map theme -> NOT elections"). Authority:
 * Hans + Max for the curated pool (one per topic family); Jony + Citizen
 * for the deterministic-by-day rotation strategy (over pure-random or
 * sticky default). See plan-doc TODO/20260611-home-page-citizen-experience-plan.md
 * section 0.4 + row PR-2.
 *
 * Fallback to `{ kind: "election" }` when the catalogue is null (bootstrap)
 * OR when fewer than 3 curated indicators are present (probable catalogue
 * regression; election is the safe default). When/if a live event lands,
 * hook the live-event override here above the rotation logic.
 *
 * Bad / unknown `?theme=` values fall back to the default silently — same
 * graceful-degradation contract as `?peer=` on `/t/:topic`.
 */

import type { CatalogueArtifact, CatalogueTopic, TopicCatalogue } from "./catalogue";
import { getCanonicalDescriptor } from "./canonical/indicator-allowlist";

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
const ELECTION_LABEL = "Winning party";
const ELECTION_CAPTION = "winning party by state";
const ELECTION_GROUP = "Elections";

/**
 * Curated national-scope indicators that the Home choropleth rotates among
 * by day-of-year. One per topic family per Hans + Max ruling (plan-doc
 * TODO/20260611-home-page-citizen-experience-plan.md section 0.4 + row PR-2).
 * Today's pick = `CURATED_DEFAULT_THEMES[dayOfYear(now) % length]`.
 *
 * Order is the rotation order; do NOT alphabetise. To expand: add a row
 * (one per topic family), keep one-per-topic discipline.
 *
 * Each id MUST match a national-scope indicator artifact in
 * `datasets/taxonomy/topics.json`. The default-theme picker filters down
 * to only those present in the live catalogue at runtime — missing ids
 * are skipped, not surfaced as an error.
 */
const CURATED_DEFAULT_THEMES: readonly string[] = [
  "fiscal/outstanding_debt_pct_gsdp",           // Money & debt headline
  "economy/gdp_inr_crore",                       // Economy headline
  "prices/cpi_inflation_pct",                    // Prices & inflation headline
  "environment/india_ghg_emissions_mtco2e_by_sector", // Environment
  "agriculture/pashu_aadhaar_count_cattle",      // Farming & livestock
] as const;

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
 * Day-of-year (1-366) for the given Date in UTC. Pure helper; used by
 * `defaultHomeTheme` for shareable, refresh-stable rotation. UTC is
 * deliberate: every visitor sees the same default theme on the same UTC
 * day (the URL `/` with no `?theme=` slot is identical worldwide).
 * Local-time arithmetic with DST produces off-by-one across spring-forward
 * boundaries; UTC sidesteps it. Tests freeze `Date` via
 * `vi.useFakeTimers()` and assert the same day yields the same idx.
 */
export function dayOfYear(d: Date): number {
  const startUtc = Date.UTC(d.getUTCFullYear(), 0, 0);
  const diff = d.getTime() - startUtc;
  const oneDay = 1000 * 60 * 60 * 24;
  return Math.floor(diff / oneDay);
}

/**
 * Default theme = deterministic day-of-year rotation across the curated
 * pool (see CURATED_DEFAULT_THEMES). Falls back to `{ kind: "election" }`
 * when:
 *   - the catalogue is null (bootstrap window), OR
 *   - fewer than 3 curated ids resolve to a national-scope indicator in
 *     the live catalogue (probable catalogue regression; election is the
 *     safe default - logged as a console warning so the operator notices).
 *
 * Otherwise: `idx = dayOfYear(now) % pool.length` over the runtime-available
 * intersection of `CURATED_DEFAULT_THEMES` and `nationalIndicators(catalogue)`.
 *
 * Authority: Hans + Max for the curated pool, Jony + Citizen for the
 * deterministic-by-day strategy. See plan-doc row PR-2.
 */
export function defaultHomeTheme(catalogue: TopicCatalogue | null): HomeTheme {
  if (catalogue === null) return { kind: "election" };
  const nationalIds = new Set(nationalIndicators(catalogue).map(({ artifact }) => artifact.id));
  const availablePool = CURATED_DEFAULT_THEMES.filter(id => nationalIds.has(id));
  if (availablePool.length < 3) return { kind: "election" };
  const idx = dayOfYear(new Date()) % availablePool.length;
  return { kind: "indicator", id: availablePool[idx] };
}

/** True when two themes refer to the same view. */
export function sameTheme(a: HomeTheme, b: HomeTheme): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "election") return true;
  return a.id === (b as { kind: "indicator"; id: string }).id;
}

/**
 * Caption rendered after "India — " above the map. The optional
 * `titleMap` (artifact-id → indicator.title) lets the caller surface
 * the human-readable indicator title fetched at runtime; without it
 * we fall back to the canonical allowlist `meta.title` (synchronous),
 * then to the catalogue-level `display` override, then to the raw
 * slug. Priority order matches `homeThemeOptions` deliberately —
 * citizens see the same label in the chooser and the caption.
 *
 * The synchronous allowlist lookup matters on first paint: the
 * `titleMap` is populated asynchronously by `Home.load_indicator_titles`,
 * which runs only AFTER the topic catalogue resolves. Without the
 * allowlist fallback the bare slug (`prices/cpi_inflation_pct`) flashes
 * for ~1-2s before the title-map repopulates - the same A-bug from
 * /t/<topic> headings, just on a different surface.
 */
export function themeCaption(
  theme: HomeTheme,
  catalogue: TopicCatalogue | null,
  titleMap?: ReadonlyMap<string, string>,
): string {
  if (theme.kind === "election") return ELECTION_CAPTION;
  const allowlist_title = getCanonicalDescriptor(theme.id)?.meta?.title;
  for (const { artifact } of nationalIndicators(catalogue)) {
    if (artifact.id === theme.id) {
      return titleMap?.get(artifact.id) ?? allowlist_title ?? artifact.display ?? artifact.id;
    }
  }
  return titleMap?.get(theme.id) ?? allowlist_title ?? theme.id;
}

/**
 * Full chooser list: election first, then every national indicator
 * grouped by topic title. Stable order = catalogue order.
 *
 * Label resolution per indicator artifact, in priority order:
 *   1. `titleMap.get(artifact.id)` — the indicator's own `indicator.title`,
 *      pre-fetched by the caller (see Home.svelte). This is the
 *      human-readable label citizens should see.
 *   2. `artifact.display` — catalogue-level override (only ever set
 *      today for the May-2026 election entry).
 *   3. `artifact.id` — raw slug fallback (e.g. for the bootstrap
 *      window before the title-map resolves, or when the indicator
 *      fetch fails). Last-resort so the dropdown never goes blank.
 *
 * `titleMap` is optional so existing callers / tests keep working
 * unchanged; passing it in is purely additive UX polish.
 */
export function homeThemeOptions(
  catalogue: TopicCatalogue | null,
  titleMap?: ReadonlyMap<string, string>,
): HomeThemeOption[] {
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
    const allowlist_title = getCanonicalDescriptor(artifact.id)?.meta?.title;
    const label = titleMap?.get(artifact.id) ?? allowlist_title ?? artifact.display ?? artifact.id;
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

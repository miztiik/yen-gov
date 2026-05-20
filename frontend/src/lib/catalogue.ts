// Topic catalogue loader and small helpers.
//
// The catalogue is the IA spine for non-election + election data alike
// (ADR-0022). It maps topics to artifact references; the frontend dispatches
// on `kind` to pick the right renderer. This module only handles loading +
// typed access; rendering is the caller's concern.
//
// Doctrine reminder (ADR-0022 §Doctrine, user-mandated 2026-05-11): elections
// are NOT the spine. Social-welfare topics are first-class. The catalogue
// order in `datasets/taxonomy/topics.json` reflects this; this
// module preserves that order.

import { DATA_BASE } from "./paths";

export type ArtifactKind = "indicator" | "election" | "feature_collection";
export type ArtifactScope = "national" | "state" | "constituency";
export type SeventhScheduleList = "state" | "union" | "concurrent" | "na";
export type PeerSet =
  | "all"
  | "general_category"
  | "special_category"
  | "neh"
  | "himalayan"
  | "ut_legislature"
  | "ut_no_legislature"
  | "nct_delhi"
  | "fc_horizontal_devolution_share_quintile"
  | "coastal_states"
  | "landlocked_states"
  | "art_371_states";

/**
 * Runtime list of every valid `PeerSet` value, in the same order as the
 * type union above. Used by query-string parsers and validators that
 * need to check a string at runtime (TypeScript's union types disappear
 * at runtime, so we maintain the list here in lockstep).
 *
 * If you add a new PeerSet variant, add it here AND to the type union AND
 * to `state-tiers.json`'s tier list — `nonEmptyTierIds()` and the topic
 * catalogue's `peer_set_default` constraints both depend on this set.
 */
export const PEER_SET_VALUES: readonly PeerSet[] = [
  "all",
  "general_category",
  "special_category",
  "neh",
  "himalayan",
  "ut_legislature",
  "ut_no_legislature",
  "nct_delhi",
  "fc_horizontal_devolution_share_quintile",
  "coastal_states",
  "landlocked_states",
  "art_371_states",
] as const;

/** Type guard: true when `s` is a valid PeerSet value. */
export function isPeerSet(s: string): s is PeerSet {
  return (PEER_SET_VALUES as readonly string[]).includes(s);
}

export interface CatalogueArtifact {
  kind: ArtifactKind;
  id: string;
  display?: string;
  default?: boolean;
  featured?: boolean;
  scope?: ArtifactScope;
  /** Per-artifact override of the topic-level peer_set_default (catalogue v1.1). */
  peer_set_default?: PeerSet;
  /** Renderer hint mirrored from the indicator's chart_type (catalogue v1.2). */
  chart_type?: "choropleth" | "ranked" | "stacked-trend";
  /** Categorical dimension for stacked-trend mnemonic colours (catalogue v1.2). */
  dimension?: string;
}

export interface CatalogueTopic {
  id: string;
  title: string;
  list: SeventhScheduleList;
  summary: string;
  icon?: string;
  featured?: boolean;
  peer_set_default?: PeerSet;
  artifacts: CatalogueArtifact[];
  notes?: string;
}

export interface TopicCatalogue {
  $schema: string;
  $schema_version: string;
  sources: Array<{ url: string; fetched_at: string; name?: string; authority?: string }>;
  topics: CatalogueTopic[];
}

/** Fetch the topic catalogue. Validated against topic-catalogue.schema.json v1.0.
 *  Path moved from `reference/in/topic-catalogue.json` to `taxonomy/topics.json`
 *  in T.0b (TODO/20260517-canonical-long-format-pivot.md §0e Phase 0 closeout).
 *  Shape unchanged; the reference/in/ original is deleted in T.0c. */
export async function fetchTopicCatalogue(): Promise<TopicCatalogue> {
  const res = await fetch(`${DATA_BASE}/taxonomy/topics.json`);
  if (!res.ok) {
    throw new Error(
      `fetch /taxonomy/topics.json failed: ${res.status} ${res.statusText}`,
    );
  }
  return (await res.json()) as TopicCatalogue;
}

/**
 * Human-readable label for an artifact reference. Honours the catalogue's
 * `display` override (mandatory when `id` is a code like AcGenMay2026) and
 * falls back to the bare `id` otherwise.
 */
export function displayForArtifact(a: CatalogueArtifact): string {
  return a.display ?? a.id;
}

/**
 * Indicator-artifact path convention used by the existing renderers:
 * `id` = "fiscal/outstanding_debt_pct_gsdp"
 * path = "/indicators/in/fiscal/outstanding_debt_pct_gsdp.json"
 *
 * Only meaningful for `kind: "indicator"`. Returns null for other kinds so
 * callers can guard cleanly.
 */
export function indicatorPathForArtifact(a: CatalogueArtifact): string | null {
  if (a.kind !== "indicator") return null;
  return `/indicators/in/${a.id}.json`;
}

/**
 * Resolve the effective peer-set selector for an artifact under a topic:
 * artifact override > topic default > `"all"`. The result is always a
 * defined PeerSet; the caller passes it to resolvePeerSet() to get the
 * actual member list (or null for the no-filter case).
 */
export function resolvePeerSetDefault(
  topic: CatalogueTopic,
  artifact: CatalogueArtifact,
): PeerSet {
  return artifact.peer_set_default ?? topic.peer_set_default ?? "all";
}

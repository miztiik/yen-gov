// Topic catalogue loader and small helpers.
//
// The catalogue is the IA spine for non-election + election data alike
// (ADR-0022). It maps topics to artifact references; the frontend dispatches
// on `kind` to pick the right renderer. This module only handles loading +
// typed access; rendering is the caller's concern.
//
// Doctrine reminder (ADR-0022 §Doctrine, user-mandated 2026-05-11): elections
// are NOT the spine. Social-welfare topics are first-class. The catalogue
// order in `datasets/reference/in/topic-catalogue.json` reflects this; this
// module preserves that order.

import { DATA_BASE } from "./paths";

export type ArtifactKind = "indicator" | "election" | "feature_collection";
export type ArtifactScope = "national" | "state" | "constituency";
export type SeventhScheduleList = "state" | "union" | "concurrent" | "na";
export type PeerSet =
  | "all"
  | "general_category"
  | "neh"
  | "hill"
  | "ut_with_legislature"
  | "ut_without_legislature"
  | "nct_delhi";

export interface CatalogueArtifact {
  kind: ArtifactKind;
  id: string;
  display?: string;
  default?: boolean;
  featured?: boolean;
  scope?: ArtifactScope;
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

/** Fetch the topic catalogue. Validated against topic-catalogue.schema.json v1.0. */
export async function fetchTopicCatalogue(): Promise<TopicCatalogue> {
  const res = await fetch(`${DATA_BASE}/reference/in/topic-catalogue.json`);
  if (!res.ok) {
    throw new Error(
      `fetch /reference/in/topic-catalogue.json failed: ${res.status} ${res.statusText}`,
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

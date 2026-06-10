// Unit tests for the canonical-catalogue Zod schema, the lookup index, and
// the `resolveIndicatorId` dereferencer.
//
// v2.0 (PR-B1 2026-05-26 grain-over-entity rip per ADR-0044): id_aliases +
// deprecated_in removed; entity_kinds + default_entity_kind required.
//
// v3.0 (Deferral 2 of TODO/20260609-url-prefix-drop-phase0-plan.md,
// 2026-06-10): url_slug REQUIRED; url_slug_history OPTIONAL append-only
// ledger; bySlug index + resolveBySlug helper + cross-row + cross-history
// collision throw at index-build time.
import { describe, expect, it } from "vitest";

import {
  buildIndicatorCatalogueIndex,
  ENTITY_KIND_VALUES,
  IndicatorCatalogueRowSchema,
  resolveBySlug,
  resolveIndicatorId,
  type IndicatorCatalogueRow,
} from "./indicator-catalogue";

const BASE_ROW: IndicatorCatalogueRow = {
  indicator_id: "candidate-votes-polled",
  label_short: "Candidate votes polled",
  label_long: "Total votes polled by the candidate",
  description_short: "Sum of votes received by a candidate in a contest.",
  unit: "count",
  cadence: "ad_hoc",
  family: "elections",
  pillar: "politics",
  topic_tags: [],
  value_kind: "count",
  direction: "neutral",
  attribution_geography: "where_administered",
  comparability: "comparable_across_states_and_time",
  excluded_notes: [],
  parent_indicator_id: null,
  methodology_break_ids: [],
  renderer_rules: [],
  entity_kinds: ["candidate"],
  default_entity_kind: "candidate",
  // v3.0 (Deferral 2): citizen-facing URL slug. Mechanical-backfill rule
  // is url_slug = indicator_id verbatim.
  url_slug: "candidate-votes-polled",
};

function rowWith(overrides: Partial<IndicatorCatalogueRow>): unknown {
  return { ...BASE_ROW, ...overrides };
}

describe("IndicatorCatalogueRowSchema (v2.0)", () => {
  it("accepts a minimal row with required v2.0 entity fields", () => {
    const parsed = IndicatorCatalogueRowSchema.parse(BASE_ROW);
    expect(parsed.indicator_id).toBe("candidate-votes-polled");
    expect(parsed.entity_kinds).toEqual(["candidate"]);
    expect(parsed.default_entity_kind).toBe("candidate");
  });

  it("rejects an indicator_id that violates the D30 kebab pattern", () => {
    const bad = rowWith({ indicator_id: "State-Capacity" });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects a row missing entity_kinds", () => {
    const { entity_kinds: _drop, ...bad } = BASE_ROW;
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects empty entity_kinds (min 1)", () => {
    const bad = rowWith({ entity_kinds: [] });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects entity_kinds member outside the closed enum", () => {
    const bad = rowWith({ entity_kinds: ["village" as unknown as "state"] });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects unknown extra fields (strict mode)", () => {
    const bad = { ...BASE_ROW, id_aliases: ["some/legacy"] } as unknown as IndicatorCatalogueRow;
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("accepts a multi-grain row (entity_kinds = [country, state])", () => {
    const row = rowWith({
      indicator_id: "installed-capacity-mw",
      entity_kinds: ["country", "state"],
      default_entity_kind: "state",
    });
    const parsed = IndicatorCatalogueRowSchema.parse(row);
    expect(parsed.entity_kinds).toEqual(["country", "state"]);
  });

  it("exposes the six-member entity_kind enum", () => {
    expect(ENTITY_KIND_VALUES).toEqual([
      "country",
      "state",
      "district",
      "ac",
      "party",
      "candidate",
    ]);
  });
});

describe("buildIndicatorCatalogueIndex (v2.0)", () => {
  it("indexes by indicator_id and resolves it", () => {
    const idx = buildIndicatorCatalogueIndex([BASE_ROW]);
    expect(idx.byId.size).toBe(1);
    expect(resolveIndicatorId("candidate-votes-polled", idx)?.indicator_id).toBe(
      "candidate-votes-polled",
    );
  });

  it("returns null for unknown ids", () => {
    const idx = buildIndicatorCatalogueIndex([BASE_ROW]);
    expect(resolveIndicatorId("not-a-real-id", idx)).toBeNull();
    expect(resolveIndicatorId("", idx)).toBeNull();
  });

  it("throws on duplicate indicator_id", () => {
    const a = { ...BASE_ROW };
    const b = { ...BASE_ROW };
    expect(() => buildIndicatorCatalogueIndex([a, b])).toThrow(/collision/);
  });
});

// ---------------------------------------------------------------------------
// v3.0 (Deferral 2 of TODO/20260609-url-prefix-drop-phase0-plan.md, 2026-06-10).
// url_slug REQUIRED + url_slug_history OPTIONAL; bySlug index + resolveBySlug;
// cross-row + cross-history collision throw.
// ---------------------------------------------------------------------------

describe("IndicatorCatalogueRowSchema (v3.0 url_slug + url_slug_history)", () => {
  it("rejects a row missing url_slug", () => {
    const { url_slug: _drop, ...bad } = BASE_ROW;
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects a url_slug that violates the kebab pattern", () => {
    const bad = rowWith({ url_slug: "Bad_Slug" });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects a url_slug longer than 60 chars", () => {
    const bad = rowWith({ url_slug: "a".repeat(61) });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("accepts a row with url_slug_history present and well-formed", () => {
    const row = rowWith({
      url_slug: "candidate-votes",
      url_slug_history: ["candidate-votes-polled", "votes-by-candidate"],
    });
    const parsed = IndicatorCatalogueRowSchema.parse(row);
    expect(parsed.url_slug_history).toEqual([
      "candidate-votes-polled",
      "votes-by-candidate",
    ]);
  });

  it("accepts a row with url_slug_history absent (optional)", () => {
    const parsed = IndicatorCatalogueRowSchema.parse(BASE_ROW);
    expect(parsed.url_slug_history).toBeUndefined();
  });

  it("rejects a url_slug_history entry that violates the kebab pattern", () => {
    const bad = rowWith({ url_slug_history: ["Bad_Slug"] });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects a url_slug_history entry longer than 60 chars", () => {
    const bad = rowWith({ url_slug_history: ["a".repeat(61)] });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });
});

describe("buildIndicatorCatalogueIndex (v3.0 bySlug)", () => {
  it("indexes by url_slug and resolves it via resolveBySlug", () => {
    const idx = buildIndicatorCatalogueIndex([BASE_ROW]);
    expect(idx.bySlug.size).toBe(1);
    expect(resolveBySlug("candidate-votes-polled", idx)?.indicator_id).toBe(
      "candidate-votes-polled",
    );
  });

  it("indexes every url_slug_history entry alongside the current url_slug", () => {
    const row = rowWith({
      url_slug: "candidate-votes",
      url_slug_history: ["candidate-votes-polled", "votes-by-candidate"],
    });
    const idx = buildIndicatorCatalogueIndex([row as IndicatorCatalogueRow]);
    expect(idx.bySlug.size).toBe(3);
    // Current slug resolves.
    expect(resolveBySlug("candidate-votes", idx)?.url_slug).toBe(
      "candidate-votes",
    );
    // Historical slugs also resolve -- to the SAME row (caller checks
    // row.url_slug to decide render vs 301-redirect).
    expect(resolveBySlug("candidate-votes-polled", idx)?.url_slug).toBe(
      "candidate-votes",
    );
    expect(resolveBySlug("votes-by-candidate", idx)?.url_slug).toBe(
      "candidate-votes",
    );
  });

  it("returns null for unknown slugs", () => {
    const idx = buildIndicatorCatalogueIndex([BASE_ROW]);
    expect(resolveBySlug("not-a-real-slug", idx)).toBeNull();
    expect(resolveBySlug("", idx)).toBeNull();
  });

  it("throws when two rows share a url_slug (current vs current)", () => {
    const a = rowWith({
      indicator_id: "candidate-votes-polled",
      url_slug: "shared-slug",
    }) as IndicatorCatalogueRow;
    const b = rowWith({
      indicator_id: "candidate-vote-share-pct",
      url_slug: "shared-slug",
    }) as IndicatorCatalogueRow;
    expect(() => buildIndicatorCatalogueIndex([a, b])).toThrow(
      /url_slug collision: shared-slug/,
    );
  });

  it("throws when one row's url_slug collides with another row's url_slug_history", () => {
    // Forever-redirect safety: row A's CURRENT slug must never equal
    // row B's HISTORICAL slug, otherwise a 301 chain would loop or a
    // citizen bookmark would land on the wrong indicator.
    const a = rowWith({
      indicator_id: "candidate-votes-polled",
      url_slug: "candidate-votes",
      url_slug_history: ["old-slug"],
    }) as IndicatorCatalogueRow;
    const b = rowWith({
      indicator_id: "candidate-vote-share-pct",
      url_slug: "old-slug", // collides with a.url_slug_history[0]
    }) as IndicatorCatalogueRow;
    expect(() => buildIndicatorCatalogueIndex([a, b])).toThrow(
      /url_slug collision: old-slug/,
    );
  });

  it("throws when two rows share a url_slug_history entry", () => {
    const a = rowWith({
      indicator_id: "candidate-votes-polled",
      url_slug: "a-current",
      url_slug_history: ["shared-old"],
    }) as IndicatorCatalogueRow;
    const b = rowWith({
      indicator_id: "candidate-vote-share-pct",
      url_slug: "b-current",
      url_slug_history: ["shared-old"],
    }) as IndicatorCatalogueRow;
    expect(() => buildIndicatorCatalogueIndex([a, b])).toThrow(
      /url_slug collision: shared-old/,
    );
  });
});

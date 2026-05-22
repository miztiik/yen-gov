// Tests for `indicator-catalogue.ts` (T.3 2026-05-22 v1.1 dereferencer).
//
// Per CLAUDE.md §15 — fast pure tests against synthetic fixtures, no
// real catalogue, no DuckDB. Asserts:
//   * IndicatorCatalogueRowSchema accepts minimal + full-shape rows.
//   * IndicatorCatalogueRowSchema rejects bad indicator_id, bad alias
//     pattern, bad deprecated_in date.
//   * buildIndicatorCatalogueIndex detects three collision classes.
//   * resolveIndicatorId / resolveCanonicalIndicatorId / isAliasSlug
//     honour canonical-wins-over-alias precedence.

import { describe, expect, it } from "vitest";
import {
  IndicatorCatalogueRowSchema,
  buildIndicatorCatalogueIndex,
  isAliasSlug,
  resolveCanonicalIndicatorId,
  resolveIndicatorId,
  type IndicatorCatalogueRow,
} from "./indicator-catalogue";

const MIN_ROW: IndicatorCatalogueRow = {
  indicator_id: "candidate-votes-polled",
  label_short: "Candidate votes",
  label_long: "Votes polled by each candidate in an AC contest",
  description_short: "Votes polled by each candidate in an AC contest.",
  unit: "votes",
  cadence: "ad_hoc",
  family: "elections",
  pillar: "politics",
  topic_tags: [],
  value_kind: "count",
  direction: "neutral",
  attribution_geography: "where_resident",
  comparability: "directional_only",
  excluded_notes: [],
  parent_indicator_id: null,
  methodology_break_ids: [],
  renderer_rules: [],
  id_aliases: [],
};

function rowWith(overrides: Partial<IndicatorCatalogueRow>): IndicatorCatalogueRow {
  return { ...MIN_ROW, ...overrides };
}

describe("IndicatorCatalogueRowSchema", () => {
  it("accepts a minimal row", () => {
    const parsed = IndicatorCatalogueRowSchema.parse(MIN_ROW);
    expect(parsed.indicator_id).toBe("candidate-votes-polled");
    expect(parsed.id_aliases).toEqual([]);
    expect(parsed.deprecated_in).toBeUndefined();
  });

  it("accepts a row with v1.1 id_aliases (D30 + legacy slash-form) and deprecated_in", () => {
    const row = rowWith({
      id_aliases: ["elections/candidate_votes", "old-candidate-votes"],
      deprecated_in: "2026-05-22",
    });
    const parsed = IndicatorCatalogueRowSchema.parse(row);
    expect(parsed.id_aliases).toHaveLength(2);
    expect(parsed.deprecated_in).toBe("2026-05-22");
  });

  it("rejects indicator_id that violates D30 kebab", () => {
    const bad = rowWith({ indicator_id: "Candidate-Votes-Polled" });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects an alias that is neither D30 nor legacy slash-form", () => {
    const bad = rowWith({ id_aliases: ["Bad/Alias"] });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("rejects a deprecated_in that is not ISO YYYY-MM-DD", () => {
    const bad = rowWith({ id_aliases: ["elections/candidate_votes"], deprecated_in: "22-05-2026" });
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });

  it("accepts a null deprecated_in", () => {
    const ok = rowWith({ deprecated_in: null });
    const parsed = IndicatorCatalogueRowSchema.parse(ok);
    expect(parsed.deprecated_in).toBeNull();
  });

  it("rejects unknown fields (strict mode)", () => {
    const bad = { ...MIN_ROW, mystery: "field" };
    expect(() => IndicatorCatalogueRowSchema.parse(bad)).toThrow();
  });
});

describe("buildIndicatorCatalogueIndex", () => {
  it("builds byId + byAlias maps for the happy path", () => {
    const rows = [
      rowWith({
        indicator_id: "candidate-votes-polled",
        id_aliases: ["elections/candidate_votes", "old-candidate-votes"],
        deprecated_in: "2026-05-22",
      }),
      rowWith({
        indicator_id: "ac-turnout-pct",
        label_short: "AC turnout",
        label_long: "AC turnout as a percent of total electors",
        description_short: "AC turnout percentage of total electors.",
      }),
    ];
    const index = buildIndicatorCatalogueIndex(rows);
    expect(index.byId.size).toBe(2);
    expect(index.byAlias.size).toBe(2);
    expect(index.byId.get("candidate-votes-polled")?.indicator_id).toBe(
      "candidate-votes-polled",
    );
    expect(index.byAlias.get("elections/candidate_votes")?.indicator_id).toBe(
      "candidate-votes-polled",
    );
  });

  it("rejects duplicate indicator_id rows", () => {
    const rows = [MIN_ROW, MIN_ROW];
    expect(() => buildIndicatorCatalogueIndex(rows)).toThrow(/indicator_id collision/);
  });

  it("rejects an alias that shadows another row's canonical id", () => {
    const rows = [
      rowWith({ indicator_id: "ac-turnout-pct" }),
      rowWith({
        indicator_id: "candidate-votes-polled",
        id_aliases: ["ac-turnout-pct"],
        deprecated_in: "2026-05-22",
      }),
    ];
    expect(() => buildIndicatorCatalogueIndex(rows)).toThrow(/alias collision/);
  });

  it("rejects the same alias claimed by two different rows", () => {
    const rows = [
      rowWith({
        indicator_id: "ac-turnout-pct",
        id_aliases: ["elections/ac_turnout"],
        deprecated_in: "2026-05-22",
      }),
      rowWith({
        indicator_id: "candidate-votes-polled",
        id_aliases: ["elections/ac_turnout"],
        deprecated_in: "2026-05-22",
      }),
    ];
    expect(() => buildIndicatorCatalogueIndex(rows)).toThrow(/aliased to both/);
  });
});

describe("resolveIndicatorId", () => {
  const rows = [
    rowWith({
      indicator_id: "candidate-votes-polled",
      id_aliases: ["elections/candidate_votes", "old-candidate-votes"],
      deprecated_in: "2026-05-22",
    }),
    rowWith({
      indicator_id: "ac-turnout-pct",
      label_short: "AC turnout",
      label_long: "AC turnout as a percent of total electors",
      description_short: "AC turnout percentage of total electors.",
    }),
  ];
  const index = buildIndicatorCatalogueIndex(rows);

  it("returns the row for a canonical id", () => {
    const row = resolveIndicatorId("ac-turnout-pct", index);
    expect(row?.indicator_id).toBe("ac-turnout-pct");
  });

  it("returns the row for a legacy slash-form alias", () => {
    const row = resolveIndicatorId("elections/candidate_votes", index);
    expect(row?.indicator_id).toBe("candidate-votes-polled");
  });

  it("returns the row for a D30 rename-history alias", () => {
    const row = resolveIndicatorId("old-candidate-votes", index);
    expect(row?.indicator_id).toBe("candidate-votes-polled");
  });

  it("returns null for an unknown slug", () => {
    expect(resolveIndicatorId("not-a-real-indicator", index)).toBeNull();
  });

  it("returns null for an empty slug", () => {
    expect(resolveIndicatorId("", index)).toBeNull();
  });
});

describe("resolveCanonicalIndicatorId", () => {
  const rows = [
    rowWith({
      indicator_id: "candidate-votes-polled",
      id_aliases: ["elections/candidate_votes"],
      deprecated_in: "2026-05-22",
    }),
  ];
  const index = buildIndicatorCatalogueIndex(rows);

  it("returns the canonical id string for a canonical-hit input", () => {
    expect(resolveCanonicalIndicatorId("candidate-votes-polled", index)).toBe(
      "candidate-votes-polled",
    );
  });

  it("returns the canonical id string for an alias-hit input", () => {
    expect(resolveCanonicalIndicatorId("elections/candidate_votes", index)).toBe(
      "candidate-votes-polled",
    );
  });

  it("returns null when the slug is unknown", () => {
    expect(resolveCanonicalIndicatorId("xyz", index)).toBeNull();
  });
});

describe("isAliasSlug", () => {
  const rows = [
    rowWith({
      indicator_id: "candidate-votes-polled",
      id_aliases: ["elections/candidate_votes"],
      deprecated_in: "2026-05-22",
    }),
  ];
  const index = buildIndicatorCatalogueIndex(rows);

  it("returns false for a canonical-id slug", () => {
    expect(isAliasSlug("candidate-votes-polled", index)).toBe(false);
  });

  it("returns true for an alias slug", () => {
    expect(isAliasSlug("elections/candidate_votes", index)).toBe(true);
  });

  it("returns false for an unknown slug", () => {
    expect(isAliasSlug("not-a-real-indicator", index)).toBe(false);
  });

  it("returns false for an empty slug", () => {
    expect(isAliasSlug("", index)).toBe(false);
  });
});

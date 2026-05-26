// Unit tests for the canonical-catalogue Zod schema, the lookup index, and
// the `resolveIndicatorId` dereferencer.
//
// v2.0 (PR-B1 2026-05-26 grain-over-entity rip per ADR-0044): id_aliases +
// deprecated_in removed; entity_kinds + default_entity_kind required.
import { describe, expect, it } from "vitest";

import {
  buildIndicatorCatalogueIndex,
  ENTITY_KIND_VALUES,
  IndicatorCatalogueRowSchema,
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

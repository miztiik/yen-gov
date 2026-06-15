// Unit tests for the pure projection model in election-seizures-model.ts.
// Covers: category-column resolution, picker chrome labels, choropleth
// projection (date filter + state filter + null guards + LGD mapping
// miss), sparkline projection (national sum vs single-state), and
// headline-value derivation.

import { describe, expect, test } from "vitest";
import {
  categoryColumn,
  categoryHasQuantity,
  categoryLabel,
  categoryUnitLabel,
  headlineValue,
  latestDate,
  listDates,
  projectChoropleth,
  projectSparkline,
  readValue,
  SEIZURES_CATEGORIES,
  type SeizuresRow,
} from "./election-seizures-model";

// Tiny fixture: 3 states x 2 dates. Maharashtra carries every field;
// Tamil Nadu carries only cash + total; the publisher's UT historical
// slug `xyz-historical` is included to exercise the slug-to-LGD miss.
const FIXTURE: readonly SeizuresRow[] = [
  {
    state_slug: "maharashtra",
    date: "2019-03-29",
    cash_inr_crore: 8.03,
    liquor_qty_lakh_litres: 1.5,
    liquor_value_inr_crore: 4.2,
    drugs_qty_kg: 0.1,
    drugs_value_inr_crore: 0.5,
    precious_metals_qty_kg: 0.05,
    precious_metals_value_inr_crore: 2.1,
    other_items_seizure_value_inr_crore: 0.3,
    total_seizure_inr_crore: 15.13,
    source_id: "src-abc",
    processing_level: "minor",
  },
  {
    state_slug: "maharashtra",
    date: "2019-04-07",
    cash_inr_crore: 30.61,
    liquor_qty_lakh_litres: 8.2,
    liquor_value_inr_crore: 22.4,
    drugs_qty_kg: 0.9,
    drugs_value_inr_crore: 5.1,
    precious_metals_qty_kg: 0.6,
    precious_metals_value_inr_crore: 18.7,
    other_items_seizure_value_inr_crore: 1.2,
    total_seizure_inr_crore: 78.01,
    source_id: "src-abc",
    processing_level: "minor",
  },
  {
    state_slug: "tamil-nadu",
    date: "2019-03-29",
    cash_inr_crore: 12.1,
    liquor_qty_lakh_litres: null,
    liquor_value_inr_crore: null,
    drugs_qty_kg: null,
    drugs_value_inr_crore: null,
    precious_metals_qty_kg: null,
    precious_metals_value_inr_crore: null,
    other_items_seizure_value_inr_crore: null,
    total_seizure_inr_crore: 12.1,
    source_id: "src-abc",
    processing_level: "minor",
  },
  {
    state_slug: "tamil-nadu",
    date: "2019-04-07",
    cash_inr_crore: 40.0,
    liquor_qty_lakh_litres: null,
    liquor_value_inr_crore: null,
    drugs_qty_kg: null,
    drugs_value_inr_crore: null,
    precious_metals_qty_kg: null,
    precious_metals_value_inr_crore: null,
    other_items_seizure_value_inr_crore: null,
    total_seizure_inr_crore: 40.0,
    source_id: "src-abc",
    processing_level: "minor",
  },
  {
    state_slug: "xyz-historical",
    date: "2019-04-07",
    cash_inr_crore: 0.5,
    liquor_qty_lakh_litres: null,
    liquor_value_inr_crore: null,
    drugs_qty_kg: null,
    drugs_value_inr_crore: null,
    precious_metals_qty_kg: null,
    precious_metals_value_inr_crore: null,
    other_items_seizure_value_inr_crore: null,
    total_seizure_inr_crore: 0.5,
    source_id: "src-abc",
    processing_level: "minor",
  },
];

const SLUG_TO_LGD: Record<string, string> = {
  maharashtra: "27",
  "tamil-nadu": "33",
  // xyz-historical deliberately absent: exercises the miss path.
};
const slugToLgd = (s: string): string | null => SLUG_TO_LGD[s] ?? null;

describe("categoryColumn", () => {
  test("value mode resolves every category", () => {
    expect(categoryColumn("total", "value")).toBe("total_seizure_inr_crore");
    expect(categoryColumn("cash", "value")).toBe("cash_inr_crore");
    expect(categoryColumn("liquor", "value")).toBe("liquor_value_inr_crore");
    expect(categoryColumn("drugs", "value")).toBe("drugs_value_inr_crore");
    expect(categoryColumn("metals", "value")).toBe(
      "precious_metals_value_inr_crore",
    );
    expect(categoryColumn("other", "value")).toBe(
      "other_items_seizure_value_inr_crore",
    );
  });

  test("quantity mode resolves only physical-good categories", () => {
    expect(categoryColumn("liquor", "quantity")).toBe(
      "liquor_qty_lakh_litres",
    );
    expect(categoryColumn("drugs", "quantity")).toBe("drugs_qty_kg");
    expect(categoryColumn("metals", "quantity")).toBe(
      "precious_metals_qty_kg",
    );
  });

  test("quantity mode returns null for value-only categories", () => {
    expect(categoryColumn("total", "quantity")).toBeNull();
    expect(categoryColumn("cash", "quantity")).toBeNull();
    expect(categoryColumn("other", "quantity")).toBeNull();
  });
});

describe("categoryHasQuantity", () => {
  test("true only for liquor / drugs / metals", () => {
    expect(categoryHasQuantity("liquor")).toBe(true);
    expect(categoryHasQuantity("drugs")).toBe(true);
    expect(categoryHasQuantity("metals")).toBe(true);
    expect(categoryHasQuantity("total")).toBe(false);
    expect(categoryHasQuantity("cash")).toBe(false);
    expect(categoryHasQuantity("other")).toBe(false);
  });
});

describe("categoryLabel + categoryUnitLabel", () => {
  test("labels are citizen-readable and stable", () => {
    expect(categoryLabel("total")).toBe("Total ₹");
    expect(categoryLabel("cash")).toBe("Cash");
    expect(categoryLabel("other")).toBe("Freebies"); // citizen-honesty framing
  });

  test("value unit is INR crore for every category", () => {
    for (const c of SEIZURES_CATEGORIES) {
      expect(categoryUnitLabel(c, "value")).toBe("INR crore");
    }
  });

  test("quantity unit varies by physical good", () => {
    expect(categoryUnitLabel("liquor", "quantity")).toBe("lakh litres");
    expect(categoryUnitLabel("drugs", "quantity")).toBe("kg");
    expect(categoryUnitLabel("metals", "quantity")).toBe("kg");
  });
});

describe("listDates + latestDate", () => {
  test("returns sorted distinct dates", () => {
    expect(listDates(FIXTURE)).toEqual(["2019-03-29", "2019-04-07"]);
  });

  test("latestDate returns the max", () => {
    expect(latestDate(FIXTURE)).toBe("2019-04-07");
  });

  test("latestDate handles empty input", () => {
    expect(latestDate([])).toBeNull();
  });
});

describe("readValue", () => {
  test("returns numeric cell when present", () => {
    expect(readValue(FIXTURE[0], "cash", "value")).toBe(8.03);
    expect(readValue(FIXTURE[0], "liquor", "quantity")).toBe(1.5);
  });

  test("returns null for publisher-blank cell", () => {
    expect(readValue(FIXTURE[2], "liquor", "value")).toBeNull();
  });

  test("returns null for invalid (cat, unit) combo", () => {
    expect(readValue(FIXTURE[0], "cash", "quantity")).toBeNull();
  });
});

describe("projectChoropleth", () => {
  test("projects matching-date rows with LGD keys", () => {
    const out = projectChoropleth(
      FIXTURE,
      "total",
      "value",
      "2019-04-07",
      slugToLgd,
    );
    // MH + TN present (2 of 3 fixture rows on 2019-04-07; the third
    // is xyz-historical which misses the LGD map).
    expect(out).toHaveLength(2);
    expect(out.map((p) => p.entity_key).sort()).toEqual(["27", "33"]);
    const mh = out.find((p) => p.entity_key === "27");
    expect(mh?.value).toBe(78.01);
    expect(mh?.time).toBe("2019-04-07");
  });

  test("omits null-valued rows (publisher silence)", () => {
    const out = projectChoropleth(
      FIXTURE,
      "liquor",
      "value",
      "2019-04-07",
      slugToLgd,
    );
    // Only MH has liquor on 2019-04-07; TN's liquor is null.
    expect(out.map((p) => p.entity_key)).toEqual(["27"]);
    expect(out[0].value).toBe(22.4);
  });

  test("omits rows whose slug doesn't map to an LGD code", () => {
    const out = projectChoropleth(
      FIXTURE,
      "cash",
      "value",
      "2019-04-07",
      slugToLgd,
    );
    // xyz-historical has cash but no LGD; must be omitted.
    expect(out.find((p) => p.value === 0.5)).toBeUndefined();
  });

  test("filters to one state when state_filter is supplied", () => {
    const out = projectChoropleth(
      FIXTURE,
      "total",
      "value",
      "2019-04-07",
      slugToLgd,
      "tamil-nadu",
    );
    expect(out).toHaveLength(1);
    expect(out[0].entity_key).toBe("33");
  });

  test("returns empty when the requested date is absent", () => {
    const out = projectChoropleth(
      FIXTURE,
      "total",
      "value",
      "2099-01-01",
      slugToLgd,
    );
    expect(out).toEqual([]);
  });
});

describe("projectSparkline", () => {
  test("national sum across states on each date", () => {
    const out = projectSparkline(FIXTURE, "total", "value");
    // 2019-03-29: MH 15.13 + TN 12.1 (xyz-historical absent on this date) = 27.23
    // 2019-04-07: MH 78.01 + TN 40.0 + xyz-historical 0.5 = 118.51
    expect(out).toHaveLength(2);
    expect(out[0].date).toBe("2019-03-29");
    expect(out[0].value).toBeCloseTo(27.23, 5);
    expect(out[1].date).toBe("2019-04-07");
    expect(out[1].value).toBeCloseTo(118.51, 5);
  });

  test("single-state series when state_filter is supplied", () => {
    const out = projectSparkline(FIXTURE, "cash", "value", "maharashtra");
    expect(out).toEqual([
      { date: "2019-03-29", value: 8.03 },
      { date: "2019-04-07", value: 30.61 },
    ]);
  });

  test("zero-fills dates where the filtered state has no rows", () => {
    // Synthesize a fixture where one date has no MH row.
    const trimmed: SeizuresRow[] = FIXTURE.filter(
      (r) => !(r.state_slug === "maharashtra" && r.date === "2019-04-07"),
    );
    const out = projectSparkline(trimmed, "cash", "value", "maharashtra");
    expect(out).toEqual([
      { date: "2019-03-29", value: 8.03 },
      { date: "2019-04-07", value: 0 }, // zero-fill: no MH on this date
    ]);
  });
});

describe("headlineValue", () => {
  test("national sum on the latest date", () => {
    // 2019-04-07: 78.01 + 40.0 + 0.5 = 118.51
    expect(headlineValue(FIXTURE, "total", "value")).toBeCloseTo(118.51, 5);
  });

  test("single-state sum on the latest date", () => {
    expect(headlineValue(FIXTURE, "cash", "value", "maharashtra")).toBe(30.61);
  });

  test("null when no rows match", () => {
    expect(headlineValue([], "total", "value")).toBeNull();
    expect(
      headlineValue(FIXTURE, "liquor", "value", "tamil-nadu"),
    ).toBeNull();
  });
});

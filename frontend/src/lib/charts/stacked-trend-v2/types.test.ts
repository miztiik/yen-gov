// StackedTrendV2 — zod-model conformance tests.
//
// Per docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md Track-D D1
// (Phase 2.1a / R-09). Structural only — zero render coverage. The
// component shell + behavioural tests land in subsequent commits.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  OTHER_CATEGORY_FILL_V2,
  OTHER_CATEGORY_ID_V2,
  StackedTrendV2Bar,
  StackedTrendV2Category,
  StackedTrendV2Model,
  StackedTrendV2Source,
} from "./types";

const fixturesDir = resolve(fileURLToPath(new URL(".", import.meta.url)), "__fixtures__");

function loadFixture(name: string): unknown {
  return JSON.parse(readFileSync(resolve(fixturesDir, name), "utf8"));
}

describe("StackedTrendV2Model — shipped fixture round-trips through zod", () => {
  it("minimal.fixture.json parses cleanly", () => {
    const raw = loadFixture("minimal.fixture.json");
    const result = StackedTrendV2Model.safeParse(raw);
    if (!result.success) {
      throw new Error(
        `minimal.fixture.json failed to parse: ${JSON.stringify(result.error.issues, null, 2)}`,
      );
    }
    expect(result.success).toBe(true);
  });

  it("shipped fixture carries 2 deduped publisher pills", () => {
    const raw = loadFixture("minimal.fixture.json");
    const parsed = StackedTrendV2Model.parse(raw);
    expect(parsed.sources).toHaveLength(2);
    const labels = parsed.sources.map((s) => s.label).sort();
    expect(labels[0]).toContain("CEA");
    expect(labels[1]).toContain("Indiastat");
  });

  it("shipped fixture includes missing + availability_label segment", () => {
    const raw = loadFixture("minimal.fixture.json");
    const parsed = StackedTrendV2Model.parse(raw);
    const missing = parsed.bars
      .flatMap((b) => b.segments)
      .filter((s) => s.availability === "missing");
    expect(missing).toHaveLength(1);
    expect(missing[0].value).toBeNull();
    expect(missing[0].availability_label).toBe("Hydro disclosure pending");
  });
});

describe("StackedTrendV2Source — publisher-pill discipline (post 2026-06-11)", () => {
  const VALID: Readonly<Record<string, unknown>> = Object.freeze({
    label: "ECI Statistical Report Section 10",
    vintage_summary: "AcGenApr2021",
    url: "https://eci.gov.in/statistical-reports",
    count: 1,
  });

  it("accepts a valid publisher pill", () => {
    expect(StackedTrendV2Source.safeParse(VALID).success).toBe(true);
  });

  it("strips unknown extra fields (Zod default)", () => {
    // The retired v1 'fetched_at' and v2 'license' fields are stripped
    // silently by Zod's default behaviour - the structural guarantee
    // is that a future renderer reading those fields gets undefined.
    const tainted = { ...VALID, fetched_at: "2026-05-23T00:00:00Z", license: "MIT" };
    const parsed = StackedTrendV2Source.parse(tainted);
    expect((parsed as Record<string, unknown>).fetched_at).toBeUndefined();
    expect((parsed as Record<string, unknown>).license).toBeUndefined();
  });

  it("rejects empty label (the pill MUST identify a publisher)", () => {
    const bad = { ...VALID, label: "" };
    expect(StackedTrendV2Source.safeParse(bad).success).toBe(false);
  });

  it("permits empty vintage_summary string (no vintage on contributing rows)", () => {
    const empty = { ...VALID, vintage_summary: "" };
    expect(StackedTrendV2Source.safeParse(empty).success).toBe(true);
  });

  it("permits null url (publisher row carries no link)", () => {
    const noLink = { ...VALID, url: null };
    expect(StackedTrendV2Source.safeParse(noLink).success).toBe(true);
  });

  it("requires count to be a positive integer", () => {
    expect(StackedTrendV2Source.safeParse({ ...VALID, count: 0 }).success).toBe(false);
    expect(StackedTrendV2Source.safeParse({ ...VALID, count: -1 }).success).toBe(false);
    expect(StackedTrendV2Source.safeParse({ ...VALID, count: 1.5 }).success).toBe(false);
    expect(StackedTrendV2Source.safeParse({ ...VALID, count: 3 }).success).toBe(true);
  });
});
describe("StackedTrendV2Model — root schema discipline", () => {
  function baseModel(): unknown {
    return loadFixture("minimal.fixture.json");
  }

  it("rejects missing schema_version", () => {
    const raw = baseModel() as Record<string, unknown>;
    delete raw.schema_version;
    expect(StackedTrendV2Model.safeParse(raw).success).toBe(false);
  });

  it("rejects schema_version other than literal '2.0'", () => {
    const raw = baseModel() as Record<string, unknown>;
    raw.schema_version = "1.0";
    expect(StackedTrendV2Model.safeParse(raw).success).toBe(false);
  });

  it("rejects empty categories array", () => {
    const raw = baseModel() as Record<string, unknown>;
    raw.categories = [];
    expect(StackedTrendV2Model.safeParse(raw).success).toBe(false);
  });

  it("rejects empty bars array", () => {
    const raw = baseModel() as Record<string, unknown>;
    raw.bars = [];
    expect(StackedTrendV2Model.safeParse(raw).success).toBe(false);
  });

  it("default_mode falls back to 'percent' when omitted", () => {
    const raw = baseModel() as Record<string, unknown>;
    delete raw.default_mode;
    const parsed = StackedTrendV2Model.parse(raw);
    expect(parsed.default_mode).toBe("percent");
  });
});

describe("StackedTrendV2Category — element discipline", () => {
  it("rejects fill that is not a hex colour", () => {
    expect(
      StackedTrendV2Category.safeParse({
        id: "coal",
        label: "Coal",
        fill: "rgb(0,0,0)",
        order: 1,
      }).success,
    ).toBe(false);
  });

  it("accepts uppercase hex fill", () => {
    expect(
      StackedTrendV2Category.safeParse({
        id: "coal",
        label: "Coal",
        fill: "#37414B",
        order: 1,
      }).success,
    ).toBe(true);
  });

  it("requires non-empty id and label", () => {
    expect(
      StackedTrendV2Category.safeParse({ id: "", label: "x" }).success,
    ).toBe(false);
    expect(
      StackedTrendV2Category.safeParse({ id: "x", label: "" }).success,
    ).toBe(false);
  });
});

describe("StackedTrendV2Bar — bar discipline", () => {
  it("rejects bar without segments key", () => {
    expect(
      StackedTrendV2Bar.safeParse({
        period_id: "x",
        period_label: "X",
        order: 1,
      }).success,
    ).toBe(false);
  });

  it("accepts empty segments array (renderer responsibility to handle)", () => {
    expect(
      StackedTrendV2Bar.safeParse({
        period_id: "x",
        period_label: "X",
        order: 1,
        segments: [],
      }).success,
    ).toBe(true);
  });
});

describe("StackedTrendV2 — constants stay aligned with v1", () => {
  // Branch-by-Abstraction (R-08) demands that v1 and v2 agree on the
  // OTHER sentinel during the migration window so cross-version palette
  // helpers don't drift.
  it("OTHER_CATEGORY_ID_V2 matches v1 sentinel '__OTHER__'", () => {
    expect(OTHER_CATEGORY_ID_V2).toBe("__OTHER__");
  });

  it("OTHER_CATEGORY_FILL_V2 matches v1 grey fill", () => {
    expect(OTHER_CATEGORY_FILL_V2).toBe("#9ca3af");
  });
});

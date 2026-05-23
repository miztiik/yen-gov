// Vitest — CompositionBar contract (zod model + fixture round-trip).
//
// Pin the v1 contract shape against the Gujarat-2022 seats fixture. If
// the schema drifts (new required field added without a fixture bump,
// type narrowed silently, etc.) this suite fails loud.

import { describe, expect, it } from "vitest";

import gujarat2022 from "./__fixtures__/gujarat-2022-seats.json";
import {
  segmentsSumMatchesTotal,
  totalSegmentValue,
} from "./helpers";
import {
  CompositionBarModel,
  CompositionBarSegment,
} from "./types";

describe("CompositionBarModel — zod round-trip", () => {
  it("validates the Gujarat 2022 fixture", () => {
    const parsed = CompositionBarModel.parse(gujarat2022);
    expect(parsed.schema_version).toBe("1.0");
    expect(parsed.dimension).toBe("party");
    expect(parsed.segments.length).toBeGreaterThanOrEqual(2);
  });

  it("rejects schema_version other than 1.0", () => {
    const bad = { ...gujarat2022, schema_version: "2.0" };
    expect(() => CompositionBarModel.parse(bad)).toThrow();
  });

  it("rejects a zero or negative total_value", () => {
    expect(() =>
      CompositionBarModel.parse({ ...gujarat2022, total_value: 0 }),
    ).toThrow();
    expect(() =>
      CompositionBarModel.parse({ ...gujarat2022, total_value: -1 }),
    ).toThrow();
  });

  it("rejects an empty segments array", () => {
    expect(() =>
      CompositionBarModel.parse({ ...gujarat2022, segments: [] }),
    ).toThrow();
  });

  it("defaults honesty_banners to an empty array", () => {
    const withoutBanners = { ...gujarat2022 };
    // The fixture intentionally omits the field at runtime so the
    // default applies; the JSON file ships the explicit array so
    // human readers can see the shape at a glance.
    delete (withoutBanners as Record<string, unknown>).honesty_banners;
    const parsed = CompositionBarModel.parse(withoutBanners);
    expect(parsed.honesty_banners).toEqual([]);
  });

  it("defaults subtitle to null", () => {
    const withoutSubtitle = { ...gujarat2022 };
    delete (withoutSubtitle as Record<string, unknown>).subtitle;
    const parsed = CompositionBarModel.parse(withoutSubtitle);
    expect(parsed.subtitle).toBeNull();
  });

  it("defaults caption_fptp to null", () => {
    const withoutCaption = { ...gujarat2022 };
    delete (withoutCaption as Record<string, unknown>).caption_fptp;
    const parsed = CompositionBarModel.parse(withoutCaption);
    expect(parsed.caption_fptp).toBeNull();
  });
});

describe("CompositionBarSegment — zod discipline", () => {
  function baseSeg(): unknown {
    return {
      id: "BJP",
      label: "BJP",
      value: 156,
      fill: "#ffb236",
      swatch_role: "party",
      is_tail: false,
    };
  }

  it("validates a well-formed segment", () => {
    const parsed = CompositionBarSegment.parse(baseSeg());
    expect(parsed.id).toBe("BJP");
    expect(parsed.fill).toBe("#ffb236");
  });

  it("rejects a negative value", () => {
    expect(() =>
      CompositionBarSegment.parse({ ...(baseSeg() as object), value: -1 }),
    ).toThrow();
  });

  it("accepts a zero value (renderer omits zero-width swatches)", () => {
    const parsed = CompositionBarSegment.parse({
      ...(baseSeg() as object),
      value: 0,
    });
    expect(parsed.value).toBe(0);
  });

  it("rejects a fill that is not a 6-hex string", () => {
    expect(() =>
      CompositionBarSegment.parse({ ...(baseSeg() as object), fill: "red" }),
    ).toThrow();
    expect(() =>
      CompositionBarSegment.parse({ ...(baseSeg() as object), fill: "#fff" }),
    ).toThrow();
  });

  it("accepts a fill with uppercase hex", () => {
    const parsed = CompositionBarSegment.parse({
      ...(baseSeg() as object),
      fill: "#FFAA00",
    });
    expect(parsed.fill).toBe("#FFAA00");
  });

  it("defaults is_tail to false when omitted", () => {
    const withoutTail = baseSeg() as Record<string, unknown>;
    delete withoutTail.is_tail;
    const parsed = CompositionBarSegment.parse(withoutTail);
    expect(parsed.is_tail).toBe(false);
  });

  it("requires id / label / fill / swatch_role to be non-empty", () => {
    expect(() =>
      CompositionBarSegment.parse({ ...(baseSeg() as object), id: "" }),
    ).toThrow();
    expect(() =>
      CompositionBarSegment.parse({ ...(baseSeg() as object), label: "" }),
    ).toThrow();
    expect(() =>
      CompositionBarSegment.parse({ ...(baseSeg() as object), swatch_role: "" }),
    ).toThrow();
  });
});

describe("Gujarat 2022 fixture sum-check", () => {
  it("segments sum to total_value (182 seats)", () => {
    const parsed = CompositionBarModel.parse(gujarat2022);
    expect(parsed.total_value).toBe(182);
    expect(totalSegmentValue(parsed.segments)).toBe(182);
    expect(segmentsSumMatchesTotal(parsed)).toBe(true);
  });

  it("has exactly one tail segment (Others)", () => {
    const parsed = CompositionBarModel.parse(gujarat2022);
    const tails = parsed.segments.filter(s => s.is_tail);
    expect(tails).toHaveLength(1);
    expect(tails[0].label).toBe("Others");
  });

  it("BJP is the largest segment (single-party-dominant case)", () => {
    const parsed = CompositionBarModel.parse(gujarat2022);
    const sorted = [...parsed.segments].sort((a, b) => b.value - a.value);
    expect(sorted[0].id).toBe("BJP");
    expect(sorted[0].value).toBe(156);
  });
});

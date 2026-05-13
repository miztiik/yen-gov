// Tests for the /t/:topic query-string contract (P3.3d).
//
// What we guard:
//   - Round-trip: parse(serialize(x)) === x for every reachable shape.
//   - Unknown peer values are dropped (no throw, no leak into the page).
//   - Empty state serializes to "" (NOT "?") so default URLs stay clean.
//   - Both string and URLSearchParams inputs to parseTopicQuery work.

import { describe, it, expect } from "vitest";
import { parseTopicQuery, serializeTopicQuery } from "./topic-query";
import { PEER_SET_VALUES } from "./catalogue";

describe("parseTopicQuery", () => {
  it("returns null peer when query is empty", () => {
    expect(parseTopicQuery("")).toEqual({ peer: null });
    expect(parseTopicQuery("?")).toEqual({ peer: null });
    expect(parseTopicQuery(new URLSearchParams())).toEqual({ peer: null });
  });

  it("parses a valid peer value", () => {
    expect(parseTopicQuery("?peer=general_category")).toEqual({ peer: "general_category" });
    expect(parseTopicQuery("peer=special_category")).toEqual({ peer: "special_category" });
    expect(parseTopicQuery("?peer=all")).toEqual({ peer: "all" });
  });

  it("accepts a URLSearchParams instance directly", () => {
    const p = new URLSearchParams();
    p.set("peer", "neh");
    expect(parseTopicQuery(p)).toEqual({ peer: "neh" });
  });

  it("drops unknown peer values silently (no throw, no leak)", () => {
    expect(parseTopicQuery("?peer=not-a-real-peer")).toEqual({ peer: null });
    expect(parseTopicQuery("?peer=")).toEqual({ peer: null });
    expect(parseTopicQuery("?peer=GENERAL_CATEGORY")).toEqual({ peer: null }); // case-sensitive
  });

  it("ignores extra unknown params (forward compat)", () => {
    expect(parseTopicQuery("?peer=general_category&unknown=foo")).toEqual({
      peer: "general_category",
    });
  });

  it("accepts every value in PEER_SET_VALUES", () => {
    for (const v of PEER_SET_VALUES) {
      expect(parseTopicQuery(`?peer=${v}`).peer).toBe(v);
    }
  });
});

describe("serializeTopicQuery", () => {
  it("returns empty string for the default (all-null) state", () => {
    expect(serializeTopicQuery({ peer: null })).toBe("");
  });

  it("emits ?peer=<id> for a set peer", () => {
    expect(serializeTopicQuery({ peer: "general_category" })).toBe("?peer=general_category");
    expect(serializeTopicQuery({ peer: "all" })).toBe("?peer=all");
  });

  it("round-trips for every PEER_SET_VALUE", () => {
    for (const v of PEER_SET_VALUES) {
      const q = { peer: v };
      expect(parseTopicQuery(serializeTopicQuery(q))).toEqual(q);
    }
  });

  it("round-trips the empty state", () => {
    expect(parseTopicQuery(serializeTopicQuery({ peer: null }))).toEqual({ peer: null });
  });
});

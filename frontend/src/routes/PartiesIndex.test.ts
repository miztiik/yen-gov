// Vitest for the pure helpers exported from `PartiesIndex.svelte`'s
// `<script module>` block. Per project doctrine (Skeleton.test.ts +
// IndicatorJump.test.ts + PartyPill.test.ts precedent +
// memories/lessons.md note): `@testing-library/svelte` is NOT
// installed, so DOM-mounting + click + scroll are not assertable in
// node-env. The testable surface is the pure helpers
// (`groupByLetter`, `filterParties`, `recognitionLabel`); the Svelte
// template wires `<input>` + `<button>` events to those helpers and
// is covered by CLAUDE.md section 13 in-browser smoke + the e2e
// spec (parties-index.spec.ts).
//
// PR-3 of TODO/20260612-party-rendering-and-party-pages-plan.md.

import { describe, expect, it } from "vitest";
import {
  filterParties,
  groupByLetter,
  recognitionLabel,
  type PartyLetterBucket,
} from "./PartiesIndex.svelte";
import type { PartySummary } from "../lib/view-models/parties";

/** Build a minimal PartySummary fixture. Defaults model a typical
 *  recognised national party so per-test overrides flag only the
 *  varying axes. */
function fixture(overrides: Partial<PartySummary> = {}): PartySummary {
  return {
    party_id: "parties.IN.BJP",
    slug: "bjp",
    short: "BJP",
    full: "Bharatiya Janata Party",
    recognition_scope: "national",
    home_state_codes: "",
    founded_year: 1980,
    symbol_asset: null,
    brand_colour: "#ea580c",
    aliases: "",
    is_sentinel: false,
    ...overrides,
  };
}

// --- recognitionLabel -----------------------------------------------------

describe("recognitionLabel", () => {
  it("maps national / state / unrecognised_registered to citizen labels", () => {
    expect(recognitionLabel("national")).toBe("National");
    expect(recognitionLabel("state")).toBe("State");
    expect(recognitionLabel("unrecognised_registered")).toBe("Unrecognised");
  });

  it("maps the long-tail enum values (defunct, sentinel)", () => {
    expect(recognitionLabel("defunct")).toBe("Defunct");
    expect(recognitionLabel("sentinel")).toBe("Special");
  });

  it("returns an empty string for the blank / unknown scope (chip suppression)", () => {
    expect(recognitionLabel("")).toBe("");
    expect(recognitionLabel("unmapped_value")).toBe("");
  });
});

// --- filterParties --------------------------------------------------------

describe("filterParties", () => {
  const sample: PartySummary[] = [
    fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP", full: "Bharatiya Janata Party", recognition_scope: "national", aliases: "" }),
    fixture({ party_id: "parties.IN.INC", slug: "inc", short: "INC", full: "Indian National Congress", recognition_scope: "national", aliases: "" }),
    fixture({ party_id: "parties.IN.DMK", slug: "dmk", short: "DMK", full: "Dravida Munnetra Kazhagam", recognition_scope: "state", aliases: "" }),
    fixture({ party_id: "parties.IN.AAAP", slug: "aaap", short: "AAAP", full: "Aapki Apni Adhikar Party", recognition_scope: "", aliases: "AAAAP|AAAP" }),
    fixture({ party_id: "parties.IN.IND", slug: "independent", short: "IND", full: "Independent", recognition_scope: "sentinel", aliases: "", is_sentinel: true }),
  ];

  it("(f) empty query returns the input list filtered only by recognition", () => {
    const out = filterParties(sample, "", "all");
    expect(out).toHaveLength(sample.length);
    expect(out.map((r) => r.party_id)).toEqual(sample.map((r) => r.party_id));
  });

  it("(b) substring match on short is case-insensitive", () => {
    const out = filterParties(sample, "bjp", "all");
    expect(out.map((r) => r.party_id)).toEqual(["parties.IN.BJP"]);
    const outUpper = filterParties(sample, "BJP", "all");
    expect(outUpper).toEqual(out);
  });

  it("substring match against full name also fires (case-insensitive)", () => {
    const out = filterParties(sample, "congress", "all");
    expect(out.map((r) => r.party_id)).toEqual(["parties.IN.INC"]);
  });

  it("(c) substring match against pipe-delimited aliases fires", () => {
    // AAAP has aliases "AAAAP|AAAP"; query "AAAA" must hit it
    // via the raw pipe-joined string.
    const out = filterParties(sample, "AAAA", "all");
    expect(out.map((r) => r.party_id)).toEqual(["parties.IN.AAAP"]);
  });

  it("trims whitespace around the query", () => {
    expect(filterParties(sample, "   dmk   ", "all").map((r) => r.party_id))
      .toEqual(["parties.IN.DMK"]);
  });

  it("(d) recognition=national narrows to recognition_scope=national", () => {
    const out = filterParties(sample, "", "national");
    expect(out.map((r) => r.party_id)).toEqual([
      "parties.IN.BJP",
      "parties.IN.INC",
    ]);
  });

  it("recognition=state narrows to recognition_scope=state", () => {
    const out = filterParties(sample, "", "state");
    expect(out.map((r) => r.party_id)).toEqual(["parties.IN.DMK"]);
  });

  it("recognition=unrecognised matches recognition_scope=unrecognised_registered", () => {
    const lone = [
      fixture({
        party_id: "parties.IN.XYZ",
        slug: "xyz",
        short: "XYZ",
        recognition_scope: "unrecognised_registered",
      }),
    ];
    expect(filterParties(lone, "", "unrecognised").map((r) => r.party_id))
      .toEqual(["parties.IN.XYZ"]);
  });

  it("(e) recognition=all is a pass-through over the recognition axis", () => {
    const out = filterParties(sample, "", "all");
    expect(out).toHaveLength(sample.length);
  });

  it("combines search + recognition: 'kazh' + state narrows to DMK", () => {
    const out = filterParties(sample, "kazh", "state");
    expect(out.map((r) => r.party_id)).toEqual(["parties.IN.DMK"]);
  });

  it("combines search + recognition: 'kazh' + national returns empty (DMK is state-only)", () => {
    const out = filterParties(sample, "kazh", "national");
    expect(out).toEqual([]);
  });

  it("does NOT mutate the input array", () => {
    const before = sample.map((r) => r.party_id);
    filterParties(sample, "dmk", "state");
    expect(sample.map((r) => r.party_id)).toEqual(before);
  });
});

// --- groupByLetter --------------------------------------------------------

describe("groupByLetter", () => {
  it("(a) sentinels (IND, NOTA) bucket into a 'Special' section ABOVE 'A'", () => {
    const rows = [
      fixture({ party_id: "parties.IN.IND", slug: "independent", short: "IND", is_sentinel: true }),
      fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP" }),
      fixture({ party_id: "parties.IN.NOTA", slug: "nota", short: "NOTA", is_sentinel: true }),
    ];
    const buckets = groupByLetter(rows);
    expect(buckets.length).toBeGreaterThan(0);
    expect(buckets[0]!.letter).toBe("\u2605 Special");
    expect(buckets[0]!.anchor).toBe("special");
    expect(buckets[0]!.parties.map((r) => r.party_id).sort()).toEqual([
      "parties.IN.IND",
      "parties.IN.NOTA",
    ]);
    // Subsequent buckets are A..Z; first non-special is B for BJP.
    const nonSpecial = buckets.filter((b) => b.anchor !== "special");
    expect(nonSpecial[0]!.letter).toBe("B");
    expect(nonSpecial[0]!.parties.map((r) => r.party_id)).toEqual([
      "parties.IN.BJP",
    ]);
  });

  it("emits no 'Special' bucket when input has no sentinels", () => {
    const rows = [
      fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP" }),
      fixture({ party_id: "parties.IN.INC", slug: "inc", short: "INC" }),
    ];
    const buckets = groupByLetter(rows);
    expect(buckets.find((b) => b.anchor === "special")).toBeUndefined();
    expect(buckets.map((b) => b.letter)).toEqual(["B", "I"]);
  });

  it("buckets are keyed by the first character of `short`, uppercased", () => {
    const rows = [
      fixture({ party_id: "parties.IN.AAAP", slug: "aaap", short: "AAAP" }),
      fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP" }),
      fixture({ party_id: "parties.IN.CPI", slug: "cpi", short: "CPI" }),
    ];
    const letters = groupByLetter(rows).map((b) => b.letter);
    expect(letters).toEqual(["A", "B", "C"]);
  });

  it("skips empty letters between populated heads (sparse alphabet)", () => {
    const rows = [
      fixture({ party_id: "parties.IN.AAAP", slug: "aaap", short: "AAAP" }),
      fixture({ party_id: "parties.IN.ZZZ", slug: "zzz", short: "ZZZ" }),
    ];
    const letters = groupByLetter(rows).map((b) => b.letter);
    expect(letters).toEqual(["A", "Z"]);
  });

  it("rows whose first character is non-alpha land in a trailing '#' bucket", () => {
    const rows = [
      fixture({ party_id: "parties.IN.NUM", slug: "num", short: "0NE" }),
      fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP" }),
    ];
    const buckets = groupByLetter(rows);
    expect(buckets.map((b) => b.letter)).toEqual(["B", "#"]);
    expect(buckets[1]!.parties.map((r) => r.party_id)).toEqual([
      "parties.IN.NUM",
    ]);
  });

  it("(g) UNK is defensively dropped even if it leaks through the loader", () => {
    const rows = [
      // Loader normally filters this row at the slug=null boundary; this
      // test pins the secondary defence in groupByLetter so a future loader
      // regression doesn't surface UNK as a citizen entity.
      fixture({ party_id: "parties.IN.UNK", slug: "unk", short: "UNK", recognition_scope: "sentinel", is_sentinel: true }),
      fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP" }),
    ];
    const buckets = groupByLetter(rows);
    // UNK must NOT appear in any bucket.
    const allIds = buckets.flatMap((b) =>
      b.parties.map((r) => r.party_id),
    );
    expect(allIds).not.toContain("parties.IN.UNK");
    expect(allIds).toEqual(["parties.IN.BJP"]);
  });

  it("preserves input order WITHIN a letter bucket (SQL-sort honoured)", () => {
    const rows = [
      fixture({ party_id: "parties.IN.BJD", slug: "bjd", short: "BJD" }),
      fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP" }),
      fixture({ party_id: "parties.IN.BSP", slug: "bsp", short: "BSP" }),
    ];
    const buckets = groupByLetter(rows);
    expect(buckets).toHaveLength(1);
    expect(buckets[0]!.parties.map((r) => r.party_id)).toEqual([
      "parties.IN.BJD",
      "parties.IN.BJP",
      "parties.IN.BSP",
    ]);
  });

  it("returns an empty list when input is empty", () => {
    const buckets: PartyLetterBucket[] = groupByLetter([]);
    expect(buckets).toEqual([]);
  });

  it("emits a stable anchor per bucket (letter-x kebab-case)", () => {
    const rows = [
      fixture({ party_id: "parties.IN.IND", slug: "independent", short: "IND", is_sentinel: true }),
      fixture({ party_id: "parties.IN.AAP", slug: "aap", short: "AAP" }),
      fixture({ party_id: "parties.IN.BJP", slug: "bjp", short: "BJP" }),
    ];
    const buckets = groupByLetter(rows);
    expect(buckets.map((b) => b.anchor)).toEqual([
      "special",
      "letter-a",
      "letter-b",
    ]);
  });
});

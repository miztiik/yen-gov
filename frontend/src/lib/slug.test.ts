import { describe, it, expect } from "vitest";
import { slugify, acSlug, parseAcSlug, partySlug } from "./slug";

describe("slugify", () => {
  it("lowercases ASCII and collapses whitespace to single dash", () => {
    expect(slugify("Tamil Nadu")).toBe("tamil-nadu");
    expect(slugify("  multi   space  ")).toBe("multi-space");
  });

  it("strips diacritics via NFKD", () => {
    expect(slugify("Mylāpore")).toBe("mylapore");
    expect(slugify("Pondichéry")).toBe("pondichery");
  });

  it("collapses punctuation runs into a single dash", () => {
    expect(slugify("Foo & Bar / Baz")).toBe("foo-bar-baz");
    expect(slugify("a__b--c..d")).toBe("a-b-c-d");
  });

  it("strips leading and trailing dashes", () => {
    expect(slugify("---hello---")).toBe("hello");
  });

  it("returns empty string for input that has no [a-z0-9]", () => {
    expect(slugify("!!!")).toBe("");
    expect(slugify("")).toBe("");
  });
});

describe("acSlug", () => {
  it("composes numeric prefix and slugified name", () => {
    expect(acSlug(167, "Mylapore")).toBe("167-mylapore");
    expect(acSlug(2866, "Tiruvallur")).toBe("2866-tiruvallur");
  });

  it("falls back to bare number when name slugifies to empty", () => {
    expect(acSlug(167, "")).toBe("167");
    expect(acSlug(167, "###")).toBe("167");
  });
});

describe("parseAcSlug", () => {
  it("extracts eci_no from full slug", () => {
    expect(parseAcSlug("167-mylapore")).toBe(167);
    expect(parseAcSlug("2866-tiruvallur-east")).toBe(2866);
  });

  it("accepts bare numeric slug", () => {
    expect(parseAcSlug("167")).toBe(167);
  });

  it("returns null when slug does not start with digits", () => {
    expect(parseAcSlug("mylapore")).toBeNull();
    expect(parseAcSlug("")).toBeNull();
    expect(parseAcSlug("-167")).toBeNull();
  });

  it("round-trips against acSlug for a representative AC", () => {
    const slug = acSlug(167, "Mylapore");
    expect(parseAcSlug(slug)).toBe(167);
  });
});

describe("partySlug", () => {
  it("slugifies the short_name when non-empty", () => {
    expect(partySlug("DMK")).toBe("dmk");
    expect(partySlug("AIADMK")).toBe("aiadmk");
  });

  it("falls back to eci_code when short_name slugifies to empty", () => {
    expect(partySlug("###", "ABC1")).toBe("abc1");
  });

  it("falls back to literal 'party' when both are unusable", () => {
    expect(partySlug("")).toBe("party");
    expect(partySlug("###", null)).toBe("party");
  });
});

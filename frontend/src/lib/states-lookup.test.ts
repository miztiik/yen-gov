// Vitest pin for the Wave-F F2 round-trip in
// `frontend/src/lib/states-lookup.ts`. The defect being pinned:
//
//   - The strongholds mart for AAP-Delhi ships `state="delhi"` (LGD slug
//     for U05 NCT of Delhi). Pre-F2, `codeFromSlug("delhi")` returned
//     null because `slugify("NCT of Delhi") === "nct-of-delhi"` !=
//     "delhi", and the State-Assembly stronghold rows on `/parties/aap`
//     rendered as plain text instead of clickable `<a>` links.
//
//   - F2 widened the resolver chain with a 3rd step: `slugify(legacy_id)`
//     match. Delhi's entity carries `legacy_id="Delhi"` whose
//     slugified form ("delhi") then resolves to `U05`.
//
//   - Knock-on: `slug("delhi")` (called from links.ts builders) MUST
//     return the canonical display-name slug `"nct-of-delhi"` and NOT
//     the lowercase fallback `"delhi"` (which would mint a broken URL).
//     F2 added the matching round-trip through `resolveCodeFromSlug` in
//     `resolveSlugFromCode`.
//
// The three other entities that carry `legacy_id` today (S10 Karnataka
// = "Mysore", S22 Tamil Nadu = "Madras", U05 above) are pinned below as
// fixtures so any future widening of the entity catalogue cannot
// silently regress the legacy-id fallback shape.

import { describe, expect, it } from "vitest";
import type { StateEntry } from "./data";
import { resolveCodeFromSlug, resolveSlugFromCode } from "./states-lookup";

// Synthetic fixture mirroring the 3 entities that carry `legacy_id`
// today plus 2 control rows without one. Real entity catalogue carries
// ~36 rows; the helpers under test are O(n) and behaviour-pure, so a
// 5-row fixture is sufficient and keeps the assertions readable.
const FIXTURE: readonly StateEntry[] = [
  { eci_code: "U05", iso_3166_2: "IN-DL", name: "NCT of Delhi", kind: "union_territory", legacy_id: "Delhi" },
  { eci_code: "S10", iso_3166_2: "IN-KA", name: "Karnataka", kind: "state", legacy_id: "Mysore" },
  { eci_code: "S22", iso_3166_2: "IN-TN", name: "Tamil Nadu", kind: "state", legacy_id: "Madras" },
  { eci_code: "S01", iso_3166_2: "IN-AP", name: "Andhra Pradesh", kind: "state" },
  { eci_code: "U03", iso_3166_2: "IN-JK", name: "Jammu and Kashmir (UT)", kind: "union_territory" },
] as const;

describe("resolveCodeFromSlug (F2 3-step lookup chain)", () => {
  it("matches a direct ECI code (case-insensitive)", () => {
    expect(resolveCodeFromSlug(FIXTURE, "U05")).toBe("U05");
    expect(resolveCodeFromSlug(FIXTURE, "u05")).toBe("U05");
    expect(resolveCodeFromSlug(FIXTURE, "S22")).toBe("S22");
  });

  it("matches `slugify(name)` (canonical citizen path)", () => {
    expect(resolveCodeFromSlug(FIXTURE, "nct-of-delhi")).toBe("U05");
    expect(resolveCodeFromSlug(FIXTURE, "karnataka")).toBe("S10");
    expect(resolveCodeFromSlug(FIXTURE, "tamil-nadu")).toBe("S22");
    expect(resolveCodeFromSlug(FIXTURE, "andhra-pradesh")).toBe("S01");
  });

  it("matches `slugify(legacy_id)` (F2 LGD-mart compatibility)", () => {
    // The flagship F2 fix: AAP State-Assembly stronghold rows.
    expect(resolveCodeFromSlug(FIXTURE, "delhi")).toBe("U05");
    expect(resolveCodeFromSlug(FIXTURE, "mysore")).toBe("S10");
    expect(resolveCodeFromSlug(FIXTURE, "madras")).toBe("S22");
  });

  it("returns null for unknown slugs", () => {
    expect(resolveCodeFromSlug(FIXTURE, "atlantis")).toBeNull();
    expect(resolveCodeFromSlug(FIXTURE, "")).toBeNull();
    expect(resolveCodeFromSlug(FIXTURE, null)).toBeNull();
    expect(resolveCodeFromSlug(FIXTURE, undefined)).toBeNull();
  });

  it("does NOT cover JK-UT or A&N (entities without legacy_id)", () => {
    // Documented Wave-F partial-coverage: the JK-UT mart slug
    // `jammu-and-kashmir` does not resolve, because U03's slug is
    // `jammu-and-kashmir-ut` and the entity has no legacy_id. Same
    // shape applies to A&N Islands. The Party page still renders
    // those rows as plain text; fixing it needs a mart-side state
    // remap (out of Wave-F scope).
    expect(resolveCodeFromSlug(FIXTURE, "jammu-and-kashmir")).toBeNull();
    expect(resolveCodeFromSlug(FIXTURE, "jammu-and-kashmir-ut")).toBe("U03");
  });
});

describe("resolveSlugFromCode (F2 round-trip)", () => {
  it("returns the canonical display-name slug for a known ECI code", () => {
    expect(resolveSlugFromCode(FIXTURE, "U05")).toBe("nct-of-delhi");
    expect(resolveSlugFromCode(FIXTURE, "S22")).toBe("tamil-nadu");
    expect(resolveSlugFromCode(FIXTURE, "S01")).toBe("andhra-pradesh");
  });

  it("round-trips a legacy_id-derived slug to the canonical slug", () => {
    // The flagship F2 fix on the slug() side: link.ac("U05", ...)
    // was emitting `/delhi/...` (broken). After F2 the round-trip
    // resolves "delhi" -> "U05" -> "nct-of-delhi" before building.
    expect(resolveSlugFromCode(FIXTURE, "delhi")).toBe("nct-of-delhi");
    expect(resolveSlugFromCode(FIXTURE, "mysore")).toBe("karnataka");
    expect(resolveSlugFromCode(FIXTURE, "madras")).toBe("tamil-nadu");
  });

  it("falls back to lowercase when neither code nor slug resolves", () => {
    expect(resolveSlugFromCode(FIXTURE, "Atlantis")).toBe("atlantis");
    expect(resolveSlugFromCode(FIXTURE, "")).toBe("");
    expect(resolveSlugFromCode(FIXTURE, null)).toBe("");
    expect(resolveSlugFromCode(FIXTURE, undefined)).toBe("");
  });

  it("idempotent on the canonical slug itself", () => {
    expect(resolveSlugFromCode(FIXTURE, "nct-of-delhi")).toBe("nct-of-delhi");
    expect(resolveSlugFromCode(FIXTURE, "tamil-nadu")).toBe("tamil-nadu");
  });
});

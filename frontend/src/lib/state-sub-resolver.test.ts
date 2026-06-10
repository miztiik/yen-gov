// Unit tests for the depth-2 state-sub dispatcher (Deferral 1 of
// TODO/20260609-url-prefix-drop-phase0-plan.md).
//
// Fowler's verdict on the design: registries-as-arg keeps the
// resolver pure, so this test file uses synthetic 3-row registries
// with no fetch / no DuckDB / no Svelte mount overhead. Every case is
// O(1) and the file runs in single-digit milliseconds.
//
// Coverage matrix (each row >=1 test):
//   1. Each `kind` branch with synthetic data (district / ac / chrome /
//      notfound).
//   2. Reserved-token win over both district and AC (Jony rule #4
//      resolution order).
//   3. District resolution returns the exact registry row.
//   4. AC resolution returns the exact registry row including eci_no.
//   5. notfound when neither registry matches.
//   6. Collision case: same slug in district AND AC -> district wins
//      (first-registered per Jony rule #4); the test asserts the
//      RESOLUTION ORDER, which is the doctrine under Option A
//      (2026-06-10). The shipped corpus carries 401 such (state,
//      slug) pairs across 25 states by design; the colliding AC
//      stays reachable via the canonical event-nested URL
//      `/<state>/elections/<event>/ac/<ac>` (ADR-0052). See the
//      `state-sub-resolver.ts` module docstring for the Option A
//      rationale.
//   7. Type-discriminated union exhaustiveness via a switch that
//      compiles only when every kind has a matching arm.
//   8. Pure: same input -> same output.
//   9. Empty registries -> notfound for any non-reserved input.
//  10. Case-sensitivity contract: the resolver does NOT lowercase; the
//      caller (StateSubRouter) is responsible for slug normalisation.

import { describe, it, expect } from "vitest";
import {
  resolveStateSub,
  type AcRow,
  type DistrictRow,
  type StateSubRegistries,
  type StateSubResult,
} from "./state-sub-resolver";

// Tiny constructors so the test cases stay readable.
const d = (entity_id: string, display_name: string): DistrictRow => ({
  entity_id,
  display_name,
});
const a = (entity_id: string, name: string, eci_no: number): AcRow => ({
  entity_id,
  name,
  eci_no,
});

function makeRegistries(): StateSubRegistries {
  return {
    reserved: new Set<string>(["explore", "ac", "party", "t", "d"]),
    districts: new Map<string, DistrictRow>([
      ["coimbatore", d("IN-S22-D569", "Coimbatore")],
      ["chennai-formerly-madras", d("IN-S22-D568", "Chennai (formerly Madras)")],
      ["ariyalur", d("IN-S22-D610", "Ariyalur")],
    ]),
    acs: new Map<string, AcRow>([
      ["mylapore", a("IN-AC-2008-tamil-nadu-3881", "Mylapore", 25)],
      ["arakkonam", a("IN-AC-2008-tamil-nadu-3857", "Arakkonam", 38)],
      ["gummidipoondi", a("IN-AC-2008-tamil-nadu-3855", "Gummidipoondi", 1)],
    ]),
  };
}

describe("resolveStateSub (state-sub dispatcher, Deferral 1)", () => {
  // ---------- kind: district ----------
  it("returns kind=district when position2 is a known district slug", () => {
    const r = resolveStateSub("tamil-nadu", "coimbatore", makeRegistries());
    expect(r.kind).toBe("district");
    if (r.kind === "district") {
      expect(r.payload.entity_id).toBe("IN-S22-D569");
      expect(r.payload.display_name).toBe("Coimbatore");
    }
  });

  it("district payload carries the exact registry row identity (no clone)", () => {
    const reg = makeRegistries();
    const original = reg.districts.get("ariyalur");
    const r = resolveStateSub("tamil-nadu", "ariyalur", reg);
    expect(r.kind).toBe("district");
    if (r.kind === "district") {
      // Identity-equal, not just structurally-equal: the resolver
      // MUST NOT defensively clone (callers depend on a stable
      // reference for downstream caching).
      expect(r.payload).toBe(original);
    }
  });

  // ---------- kind: ac ----------
  it("returns kind=ac when position2 is a known AC slug", () => {
    const r = resolveStateSub("tamil-nadu", "mylapore", makeRegistries());
    expect(r.kind).toBe("ac");
    if (r.kind === "ac") {
      expect(r.payload.name).toBe("Mylapore");
      expect(r.payload.eci_no).toBe(25);
      expect(r.payload.entity_id).toBe("IN-AC-2008-tamil-nadu-3881");
    }
  });

  it("AC payload carries eci_no (the Constituency route consumes it)", () => {
    const r = resolveStateSub("tamil-nadu", "gummidipoondi", makeRegistries());
    expect(r.kind).toBe("ac");
    if (r.kind === "ac") {
      // Gummidipoondi is the canonical AC #1 in TN; if the eci_no
      // ever drifts, every existing e2e test (golden-path /
      // election-bridges-and-map-demote) breaks at the same time.
      expect(r.payload.eci_no).toBe(1);
    }
  });

  // ---------- kind: chrome (reserved) ----------
  it("returns kind=chrome when position2 is a reserved token", () => {
    const r = resolveStateSub("tamil-nadu", "explore", makeRegistries());
    expect(r.kind).toBe("chrome");
    if (r.kind === "chrome") {
      expect(r.payload.token).toBe("explore");
    }
  });

  it("reserved tokens win over districts (Jony rule #4: reserved-check first)", () => {
    // Simulate a worst-case future world where a district was named
    // "Explore". The dispatcher MUST still hand `/tamil-nadu/explore`
    // to the Explore route, not to the District route.
    const reg: StateSubRegistries = {
      reserved: new Set<string>(["explore"]),
      districts: new Map<string, DistrictRow>([
        ["explore", d("IN-S22-D999", "Explore")],
      ]),
      acs: new Map<string, AcRow>(),
    };
    const r = resolveStateSub("tamil-nadu", "explore", reg);
    expect(r.kind).toBe("chrome");
  });

  it("reserved tokens win over ACs", () => {
    const reg: StateSubRegistries = {
      reserved: new Set<string>(["party"]),
      districts: new Map<string, DistrictRow>(),
      acs: new Map<string, AcRow>([
        ["party", a("IN-AC-test", "Party", 999)],
      ]),
    };
    const r = resolveStateSub("tamil-nadu", "party", reg);
    expect(r.kind).toBe("chrome");
  });

  it("reserved `d` (Jony rule #3 future escape-hatch) wins over districts", () => {
    // The /d/ ROUTE entry was deleted in Deferral 1; the `d` token
    // stays in RESERVED_PATH_TOKENS so a future district named "D"
    // (or a citizen who types /<state>/d on the address bar) NEVER
    // poaches a recovered escape-hatch.
    const reg: StateSubRegistries = {
      reserved: new Set<string>(["d"]),
      districts: new Map<string, DistrictRow>([
        ["d", d("IN-fake", "D")],
      ]),
      acs: new Map<string, AcRow>(),
    };
    expect(resolveStateSub("tamil-nadu", "d", reg).kind).toBe("chrome");
  });

  // ---------- kind: notfound ----------
  it("returns kind=notfound when no registry matches", () => {
    const r = resolveStateSub("tamil-nadu", "no-such-thing", makeRegistries());
    expect(r.kind).toBe("notfound");
    if (r.kind === "notfound") {
      expect(r.payload).toBeNull();
    }
  });

  it("empty registries -> notfound for any non-reserved input", () => {
    const empty: StateSubRegistries = {
      reserved: new Set<string>(),
      districts: new Map<string, DistrictRow>(),
      acs: new Map<string, AcRow>(),
    };
    expect(resolveStateSub("s", "anything", empty).kind).toBe("notfound");
    expect(resolveStateSub("s", "", empty).kind).toBe("notfound");
  });

  // ---------- collision: district wins ----------
  it("collision: same slug in district AND AC -> district wins (resolution order)", () => {
    // This test pins the RESOLUTION ORDER (district before AC),
    // which is the doctrine the shipped corpus needs. Under Option A
    // (2026-06-10) the corpus carries 401 (state, slug) pairs where
    // a district name equals an AC name in the same state by design;
    // the dispatcher's deterministic first-wins resolution IS the
    // gate, and the colliding AC stays reachable via the canonical
    // event-nested URL `/<state>/elections/<event>/ac/<ac>`
    // (ADR-0052). See `state-sub-resolver.ts` module docstring and
    // `docs/architecture/frontend/routing.md` for the full rationale.
    const reg: StateSubRegistries = {
      reserved: new Set<string>(),
      districts: new Map<string, DistrictRow>([
        ["clash", d("IN-S22-Dclash", "Clash District")],
      ]),
      acs: new Map<string, AcRow>([
        ["clash", a("IN-AC-clash", "Clash AC", 99)],
      ]),
    };
    const r = resolveStateSub("s", "clash", reg);
    expect(r.kind).toBe("district");
    if (r.kind === "district") {
      expect(r.payload.display_name).toBe("Clash District");
    }
  });

  // ---------- exhaustiveness ----------
  it("discriminated union: switch exhaustiveness compiles for all four kinds", () => {
    // TypeScript exhaustiveness: if a new `kind` ever lands without a
    // matching arm here, the compiler errors and this file goes red.
    function describe(r: StateSubResult): string {
      switch (r.kind) {
        case "district":
          return `D:${r.payload.display_name}`;
        case "ac":
          return `A:${r.payload.name}#${r.payload.eci_no}`;
        case "chrome":
          return `C:${r.payload.token}`;
        case "notfound":
          return "N";
      }
    }
    const reg = makeRegistries();
    expect(describe(resolveStateSub("s", "mylapore", reg))).toBe("A:Mylapore#25");
    expect(describe(resolveStateSub("s", "coimbatore", reg))).toBe("D:Coimbatore");
    expect(describe(resolveStateSub("s", "explore", reg))).toBe("C:explore");
    expect(describe(resolveStateSub("s", "unknown", reg))).toBe("N");
  });

  // ---------- purity / determinism ----------
  it("pure: same input -> same output across repeated calls", () => {
    const reg = makeRegistries();
    const a1 = resolveStateSub("tamil-nadu", "mylapore", reg);
    const a2 = resolveStateSub("tamil-nadu", "mylapore", reg);
    expect(a1).toEqual(a2);
    expect(a1.kind).toBe("ac");
  });

  it("does NOT mutate the input registries", () => {
    const reg = makeRegistries();
    const sizesBefore = {
      reserved: reg.reserved.size,
      districts: reg.districts.size,
      acs: reg.acs.size,
    };
    resolveStateSub("tamil-nadu", "mylapore", reg);
    resolveStateSub("tamil-nadu", "no-such", reg);
    resolveStateSub("tamil-nadu", "explore", reg);
    expect(reg.reserved.size).toBe(sizesBefore.reserved);
    expect(reg.districts.size).toBe(sizesBefore.districts);
    expect(reg.acs.size).toBe(sizesBefore.acs);
  });

  // ---------- caller contract: slug normalisation is the caller's job ----------
  it("case-sensitive: capitalised position2 does NOT match a lowercase registry key", () => {
    // The resolver does NOT lowercase its input - that's the
    // StateSubRouter's responsibility, before construction of the
    // registries. If a misnormalised slug ever reaches the resolver,
    // it fails LOUD (notfound) instead of silently matching.
    const r = resolveStateSub("tamil-nadu", "MYLAPORE", makeRegistries());
    expect(r.kind).toBe("notfound");
  });

  it("does not consult the state arg for dispatch (caller filters registries)", () => {
    // The caller filters the district + AC registries to the
    // requested state before calling resolve. The resolver ignores
    // the state arg for dispatch; it stays in the signature only for
    // documentation. Passing a nonsensical state still resolves
    // correctly as long as the registries were filtered correctly.
    const reg = makeRegistries();
    const r = resolveStateSub("not-a-real-state", "mylapore", reg);
    expect(r.kind).toBe("ac");
  });
});

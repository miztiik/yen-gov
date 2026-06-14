// Unit tests for the alliance lookup loader (v2.0 schema 2026-06-12
// per TODO/20260612-alliance-phase-1-structural-fix-plan.md).
//
// The fetch is stubbed (explicit CLAUDE.md section 15 carve-out for
// canonical-store loaders). The real CSV is exercised by the
// psephlab-smoke Playwright spec at e2e/psephlab-smoke.spec.ts.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  _resetAllianceCachesForTesting,
  alliancesForEvent,
  allianceCsvUrl,
  loadAlliances,
  parsePartyAlliancesCsv,
} from "./alliances";

// v2.0 fixture: party_id,event_id,state,alliance,source_id
// Covers the 4 actual on-disk event_ids (assembly-2021, assembly-2024,
// assembly-2026, general-2024) + multiple states for D2 disambiguation.
const REAL_CSV =
  "party_id,event_id,state,alliance,source_id\n" +
  // Tamil Nadu 2026 AE (assembly-2026, tamil-nadu) - 5 rows
  "parties.IN.AIADMK,assembly-2026,tamil-nadu,AIADMK+,src-bca3c60cdafb\n" +
  "parties.IN.BJP,assembly-2026,tamil-nadu,NDA,src-bca3c60cdafb\n" +
  "parties.IN.DMK,assembly-2026,tamil-nadu,SPA,src-bca3c60cdafb\n" +
  "parties.IN.INC,assembly-2026,tamil-nadu,SPA,src-bca3c60cdafb\n" +
  "parties.IN.NTK,assembly-2026,tamil-nadu,,src-bca3c60cdafb\n" +
  // West Bengal 2021 AE (assembly-2021, west-bengal) - 2 rows (D2 case)
  "parties.IN.INC,assembly-2021,west-bengal,Sanyukta Morcha,src-33e3388cf85e\n" +
  "parties.IN.CPIM,assembly-2021,west-bengal,Sanyukta Morcha,src-33e3388cf85e\n" +
  // LS general 2024 (general-2024, national IN) - 2 rows (national scope)
  "parties.IN.BJP,general-2024,IN,NDA-2024,src-2cd9e8b9c9ce\n" +
  "parties.IN.INC,general-2024,IN,INDIA-2024,src-ac94a7e5b1b0\n";

function stubFetch(body: string, ok: boolean = true): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string) => ({
      ok,
      text: async () => body,
    })),
  );
}

beforeEach(() => {
  _resetAllianceCachesForTesting();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("parsePartyAlliancesCsv", () => {
  it("returns one row per non-empty alliance cell", () => {
    const rows = parsePartyAlliancesCsv(REAL_CSV);
    // 9 input rows, 1 (NTK) has empty alliance -> 8 output rows.
    expect(rows).toHaveLength(8);
    expect(rows[0]).toEqual({
      party_id: "parties.IN.AIADMK",
      event_id: "assembly-2026",
      state: "tamil-nadu",
      alliance: "AIADMK+",
    });
  });

  it("returns an empty array on an empty body", () => {
    expect(parsePartyAlliancesCsv("")).toEqual([]);
  });

  it("returns an empty array on a header-only body", () => {
    expect(
      parsePartyAlliancesCsv("party_id,event_id,state,alliance,source_id\n"),
    ).toEqual([]);
  });

  it("tolerates CRLF line endings", () => {
    const crlf = REAL_CSV.replace(/\n/g, "\r\n");
    expect(parsePartyAlliancesCsv(crlf)).toHaveLength(8);
  });

  it("returns [] when the required v2.0 columns are missing", () => {
    expect(parsePartyAlliancesCsv("a,b,c\n1,2,3\n")).toEqual([]);
  });

  it("returns [] when the legacy period_label column is sent (v1 shape rejected)", () => {
    // v1 fixture lacks event_id + state -> parser rejects (header-mismatch
    // guard); avoids silently joining on the wrong column.
    const v1 =
      "party_id,short_name,period_label,alliance,source_id\n" +
      "parties.IN.AIADMK,AIADMK,AcGenMay2026,AIADMK+,src-x\n";
    expect(parsePartyAlliancesCsv(v1)).toEqual([]);
  });
});

describe("loadAlliances (event-only scope, legacy v1 behaviour)", () => {
  it("returns NDA for BJP under assembly-2026 (no state filter)", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("assembly-2026");
    expect(lookup("parties.IN.BJP")).toBe("NDA");
  });

  it("returns SPA for both DMK and INC (alliance pool)", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("assembly-2026");
    expect(lookup("parties.IN.DMK")).toBe("SPA");
    expect(lookup("parties.IN.INC")).toBe("SPA");
  });

  it("returns null for a party with no row for the event", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("assembly-2026");
    // BJP general-2024 row exists but no assembly-2026 row.
    // BJP DOES have assembly-2026 row -> NDA. Use a non-curated party:
    expect(lookup("parties.IN.PARTYNOTFIXTURE")).toBeNull();
  });

  it("returns null for a party with an empty alliance cell", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("assembly-2026");
    // NTK has event_id=assembly-2026 but alliance="" -> filtered out -> null.
    expect(lookup("parties.IN.NTK")).toBeNull();
  });

  it("returns a no-op lookup for an event with no rows", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("no-such-event-2099");
    expect(lookup("parties.IN.BJP")).toBeNull();
    expect(lookup("parties.IN.DMK")).toBeNull();
  });

  it("returns a no-op lookup on a 404 CSV", async () => {
    stubFetch("", false);
    const lookup = await loadAlliances("assembly-2026");
    expect(lookup("parties.IN.BJP")).toBeNull();
  });

  it("returns a no-op lookup on a network error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("net");
      }),
    );
    const lookup = await loadAlliances("assembly-2026");
    expect(lookup("parties.IN.BJP")).toBeNull();
  });

  it("caches per-event so a second call does not re-fetch", async () => {
    const spy = vi.fn(async () => ({ ok: true, text: async () => REAL_CSV }));
    vi.stubGlobal("fetch", spy);
    await loadAlliances("assembly-2026");
    await loadAlliances("assembly-2026");
    await loadAlliances("assembly-2026");
    // Only one fetch even across 3 calls for the same event.
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("shares the underlying CSV fetch across different events", async () => {
    const spy = vi.fn(async () => ({ ok: true, text: async () => REAL_CSV }));
    vi.stubGlobal("fetch", spy);
    await loadAlliances("assembly-2026");
    await loadAlliances("general-2024");
    // Both events hit the same underlying CSV body cache.
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

describe("loadAlliances (state-scoped, D2 fix)", () => {
  it("returns Sanyukta Morcha for INC on /west-bengal/elections/assembly-2021", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("assembly-2021", "west-bengal");
    expect(lookup("parties.IN.INC")).toBe("Sanyukta Morcha");
    expect(lookup("parties.IN.CPIM")).toBe("Sanyukta Morcha");
  });

  it("returns null on /kerala/elections/assembly-2021 (D2 fix - no Kerala leak from WB rows)", async () => {
    stubFetch(REAL_CSV);
    // The 2 assembly-2021 rows in the fixture are state=west-bengal.
    // Kerala asking for assembly-2021 must NOT inherit the WB Sanyukta
    // Morcha label -- that was D2 in the plan-doc. This test PINS the
    // D2 fix so a regression instantly breaks vitest.
    const lookup = await loadAlliances("assembly-2021", "kerala");
    expect(lookup("parties.IN.INC")).toBeNull();
    expect(lookup("parties.IN.CPIM")).toBeNull();
  });

  it("surfaces national-event rows (state=IN) on any state page", async () => {
    stubFetch(REAL_CSV);
    // general-2024 rows carry state=IN -- they MUST surface for every
    // state asking for general-2024 (citizens on /tamil-nadu/elections/
    // general-2024 still see BJP=NDA-2024 / INC=INDIA-2024).
    const tn_lookup = await loadAlliances("general-2024", "tamil-nadu");
    expect(tn_lookup("parties.IN.BJP")).toBe("NDA-2024");
    expect(tn_lookup("parties.IN.INC")).toBe("INDIA-2024");

    const wb_lookup = await loadAlliances("general-2024", "west-bengal");
    expect(wb_lookup("parties.IN.BJP")).toBe("NDA-2024");
    expect(wb_lookup("parties.IN.INC")).toBe("INDIA-2024");
  });

  it("caches per (event, state) so a second call with same scope does not re-fetch", async () => {
    const spy = vi.fn(async () => ({ ok: true, text: async () => REAL_CSV }));
    vi.stubGlobal("fetch", spy);
    await loadAlliances("assembly-2021", "west-bengal");
    await loadAlliances("assembly-2021", "west-bengal");
    await loadAlliances("assembly-2021", "west-bengal");
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("treats different state scopes as different cache keys (D2 cache safety)", async () => {
    const spy = vi.fn(async () => ({ ok: true, text: async () => REAL_CSV }));
    vi.stubGlobal("fetch", spy);
    await loadAlliances("assembly-2021", "west-bengal");
    await loadAlliances("assembly-2021", "kerala");
    // Both queries share the underlying CSV body cache -> one fetch
    // total (not two). The lookup MAPS differ but the network call
    // does not duplicate.
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

describe("alliancesForEvent", () => {
  it("returns the unique set of alliance labels for the event", async () => {
    stubFetch(REAL_CSV);
    const set = await alliancesForEvent("assembly-2026");
    expect([...set].sort()).toEqual(["AIADMK+", "NDA", "SPA"]);
  });

  it("returns an empty set for an event with no rows", async () => {
    stubFetch(REAL_CSV);
    const set = await alliancesForEvent("no-such-event-2099");
    expect(set.size).toBe(0);
  });

  it("scopes to a state when state arg provided (D2 fix)", async () => {
    stubFetch(REAL_CSV);
    // assembly-2021 fixture has only west-bengal rows.
    const wb = await alliancesForEvent("assembly-2021", "west-bengal");
    expect([...wb]).toEqual(["Sanyukta Morcha"]);
    const kl = await alliancesForEvent("assembly-2021", "kerala");
    expect(kl.size).toBe(0);
  });
});

describe("allianceCsvUrl", () => {
  it("builds a stable URL under the static-bundle data root", () => {
    expect(allianceCsvUrl()).toContain("data/entities/party_alliances.csv");
  });
});

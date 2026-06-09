// Unit tests for the alliance lookup loader.
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

const REAL_CSV =
  "party_id,short_name,period_label,alliance,source_id\n" +
  "parties.IN.AIADMK,AIADMK,AcGenMay2026,AIADMK+,src-c3e2fd43efa5\n" +
  "parties.IN.BJP,BJP,AcGenMay2026,NDA,src-c3e2fd43efa5\n" +
  "parties.IN.DMK,DMK,AcGenMay2026,SPA,src-c3e2fd43efa5\n" +
  "parties.IN.INC,INC,AcGenMay2026,SPA,src-c3e2fd43efa5\n" +
  "parties.IN.NTK,NTK,AcGenMay2026,,src-c3e2fd43efa5\n" +
  "parties.IN.OTHER,Other,LsGen2024,UPA,src-historical\n";

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
    // 6 input rows, 1 (NTK) has empty alliance -> 5 output rows.
    expect(rows).toHaveLength(5);
    expect(rows[0]).toEqual({
      party_id: "parties.IN.AIADMK",
      period_label: "AcGenMay2026",
      alliance: "AIADMK+",
    });
  });

  it("returns an empty array on an empty body", () => {
    expect(parsePartyAlliancesCsv("")).toEqual([]);
  });

  it("returns an empty array on a header-only body", () => {
    expect(parsePartyAlliancesCsv("party_id,period_label,alliance\n")).toEqual([]);
  });

  it("tolerates CRLF line endings", () => {
    const crlf = REAL_CSV.replace(/\n/g, "\r\n");
    expect(parsePartyAlliancesCsv(crlf)).toHaveLength(5);
  });

  it("returns [] when the required columns are missing", () => {
    expect(parsePartyAlliancesCsv("a,b,c\n1,2,3\n")).toEqual([]);
  });
});

describe("loadAlliances", () => {
  it("returns NDA for BJP under AcGenMay2026", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("AcGenMay2026");
    expect(lookup("parties.IN.BJP")).toBe("NDA");
  });

  it("returns SPA for both DMK and INC (alliance pool)", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("AcGenMay2026");
    expect(lookup("parties.IN.DMK")).toBe("SPA");
    expect(lookup("parties.IN.INC")).toBe("SPA");
  });

  it("returns null for a party with no row for the event", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("AcGenMay2026");
    // OTHER has only a row for LsGen2024 not AcGenMay2026.
    expect(lookup("parties.IN.OTHER")).toBeNull();
  });

  it("returns null for a party with an empty alliance cell", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("AcGenMay2026");
    // NTK has period_label=AcGenMay2026 but alliance="" -> filtered out -> null.
    expect(lookup("parties.IN.NTK")).toBeNull();
  });

  it("returns a no-op lookup for an event with no rows", async () => {
    stubFetch(REAL_CSV);
    const lookup = await loadAlliances("NoSuchEvent2099");
    expect(lookup("parties.IN.BJP")).toBeNull();
    expect(lookup("parties.IN.DMK")).toBeNull();
  });

  it("returns a no-op lookup on a 404 CSV", async () => {
    stubFetch("", false);
    const lookup = await loadAlliances("AcGenMay2026");
    expect(lookup("parties.IN.BJP")).toBeNull();
  });

  it("returns a no-op lookup on a network error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("net");
      }),
    );
    const lookup = await loadAlliances("AcGenMay2026");
    expect(lookup("parties.IN.BJP")).toBeNull();
  });

  it("caches per-event so a second call does not re-fetch", async () => {
    const spy = vi.fn(async () => ({ ok: true, text: async () => REAL_CSV }));
    vi.stubGlobal("fetch", spy);
    await loadAlliances("AcGenMay2026");
    await loadAlliances("AcGenMay2026");
    await loadAlliances("AcGenMay2026");
    // Only one fetch even across 3 calls for the same event.
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("shares the underlying CSV fetch across different events", async () => {
    const spy = vi.fn(async () => ({ ok: true, text: async () => REAL_CSV }));
    vi.stubGlobal("fetch", spy);
    await loadAlliances("AcGenMay2026");
    await loadAlliances("LsGen2024");
    // Both events hit the same underlying CSV body cache.
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

describe("alliancesForEvent", () => {
  it("returns the unique set of alliance labels for the event", async () => {
    stubFetch(REAL_CSV);
    const set = await alliancesForEvent("AcGenMay2026");
    expect([...set].sort()).toEqual(["AIADMK+", "NDA", "SPA"]);
  });

  it("returns an empty set for an event with no rows", async () => {
    stubFetch(REAL_CSV);
    const set = await alliancesForEvent("NoSuchEvent2099");
    expect(set.size).toBe(0);
  });
});

describe("allianceCsvUrl", () => {
  it("builds a stable URL under the static-bundle data root", () => {
    expect(allianceCsvUrl()).toContain("data/entities/party_alliances.csv");
  });
});

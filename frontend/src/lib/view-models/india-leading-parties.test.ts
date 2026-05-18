// Unit tests for the IndiaMap leading-parties view-model loader
// (PR-G / Phase 1.3c). Mocks `query` / `registerTable` at the `../duckdb`
// boundary per Holy Law #7 carve-out (established by PR-E).

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import { loadIndiaLeadingParties } from "./india-leading-parties";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

const partyRows = [
  {
    state_code: "S22",
    period_label: "AcGenMay2026",
    short_name_key: "AIADMK",
    short_name: "AIADMK",
    full_name: "All India Anna Dravida Munnetra Kazhagam",
    eci_code: "742",
    seats_contested: 191,
    seats_won: 66,
    votes: 19_300_000,
    vote_share_pct: 33.3,
  },
  {
    state_code: "S22",
    period_label: "AcGenMay2026",
    short_name_key: "DMK",
    short_name: "DMK",
    full_name: "Dravida Munnetra Kazhagam",
    eci_code: "1234",
    seats_contested: 173,
    seats_won: 133,
    votes: 22_350_000,
    vote_share_pct: 37.7,
  },
  {
    state_code: "S11",
    period_label: "AcGenMay2026",
    short_name_key: "CPIM",
    short_name: null,
    full_name: null,
    eci_code: null,
    seats_contested: 100,
    seats_won: 62,
    votes: 8_000_000,
    vote_share_pct: 25.4,
  },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
});

describe("loadIndiaLeadingParties — happy path", () => {
  it("groups rows by state and sorts party_totals by seats_won desc", async () => {
    mockedQuery.mockResolvedValueOnce(partyRows);
    const res = await loadIndiaLeadingParties({
      S22: "AcGenMay2026",
      S11: "AcGenMay2026",
    });
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;
    expect(Object.keys(res.data.per_state).sort()).toEqual(["S11", "S22"]);
    expect(res.data.per_state.S22.event_id).toBe("AcGenMay2026");
    // DMK (133) sorts before AIADMK (66).
    expect(res.data.per_state.S22.party_totals[0].party_short).toBe("DMK");
    expect(res.data.per_state.S22.party_totals[1].party_short).toBe("AIADMK");
    // CPIM falls back to short_name_key when dim row absent.
    expect(res.data.per_state.S11.party_totals[0].party_short).toBe("CPIM");
    expect(res.data.per_state.S11.party_totals[0].party_eci_code).toBeNull();
  });

  it("registers observations + dim_parties before querying", async () => {
    mockedQuery.mockResolvedValueOnce(partyRows);
    await loadIndiaLeadingParties({ S22: "AcGenMay2026" });
    const registered = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(registered).toEqual([
      "elections.dim_parties",
      "elections.election_results",
    ]);
  });

  it("states with no observed rows are absent from per_state (not error)", async () => {
    // Only S22 has rows; caller passed S22 + S99 but S99 has no party data.
    mockedQuery.mockResolvedValueOnce(partyRows.filter((r) => r.state_code === "S22"));
    const res = await loadIndiaLeadingParties({
      S22: "AcGenMay2026",
      S99: "AcGenMay2026",
    });
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;
    expect(Object.keys(res.data.per_state)).toEqual(["S22"]);
  });

  it("empty input map returns ok with empty per_state, no SQL", async () => {
    const res = await loadIndiaLeadingParties({});
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;
    expect(res.data.per_state).toEqual({});
  });
});

describe("loadIndiaLeadingParties — failed arm", () => {
  it("maps a thrown SQL error to citizen copy + retry", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 503"));
    const res = await loadIndiaLeadingParties({ S22: "AcGenMay2026" });
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
    expect(res.reason.toLowerCase()).not.toMatch(/error:/);
    expect(typeof res.retry).toBe("function");
  });
});

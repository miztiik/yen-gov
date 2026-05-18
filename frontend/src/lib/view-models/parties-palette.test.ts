// Unit tests for the parties-palette view-model loader (PR-G / Phase 1.3c).
// Mocks `query` / `registerTable` at the `../duckdb` boundary per Holy Law #7
// carve-out.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import { loadPartiesPalette } from "./parties-palette";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

const dimRows = [
  {
    eci_code: "1234",
    short_name: "DMK",
    full_name: "Dravida Munnetra Kazhagam",
    recognition: "state",
  },
  {
    eci_code: "742",
    short_name: "AIADMK",
    full_name: "All India Anna Dravida Munnetra Kazhagam",
    recognition: "state",
  },
  {
    eci_code: null,
    short_name: "INC",
    full_name: "Indian National Congress",
    recognition: "national",
  },
];

const fallbackRows = [
  { short_name_key: "NOTA" },
  { short_name_key: "IND" },
  { short_name_key: "CPIM" },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
});

describe("loadPartiesPalette — happy path", () => {
  it("merges dim_parties with observations-only fallback", async () => {
    mockedQuery
      .mockResolvedValueOnce(dimRows)
      .mockResolvedValueOnce(fallbackRows);
    const res = await loadPartiesPalette();
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;
    const shorts = res.data.parties.map((p) => p.short_name);
    expect(shorts).toContain("DMK");
    expect(shorts).toContain("AIADMK");
    expect(shorts).toContain("INC");
    expect(shorts).toContain("NOTA");
    expect(shorts).toContain("CPIM");
    // Sorted alphabetically.
    expect(shorts).toEqual([...shorts].sort((a, b) => a.localeCompare(b)));
    // INC has null eci_code in dim — loader fills with short_name fallback.
    const inc = res.data.parties.find((p) => p.short_name === "INC");
    expect(inc?.eci_code).toBe("INC");
    // NOTA fallback row has no recognition / full_name.
    const nota = res.data.parties.find((p) => p.short_name === "NOTA");
    expect(nota?.full_name).toBeNull();
    expect(nota?.eci_code).toBe("NOTA");
  });

  it("registers observations + dim_parties before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(dimRows)
      .mockResolvedValueOnce(fallbackRows);
    await loadPartiesPalette();
    const registered = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(registered).toEqual([
      "elections.dim_parties",
      "elections.observations",
    ]);
  });
});

describe("loadPartiesPalette — failed arm", () => {
  it("maps a thrown SQL error to citizen copy + retry", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 503"));
    const res = await loadPartiesPalette();
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
    expect(res.reason.toLowerCase()).not.toMatch(/error:/);
    expect(typeof res.retry).toBe("function");
  });
});

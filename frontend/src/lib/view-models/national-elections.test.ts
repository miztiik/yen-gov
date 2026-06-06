// Unit tests for the National Elections view-model loader (F1.3b CSV cutover
// + X1a dim_parties flip).
//
// Per CLAUDE.md section 15 + parent plan section 22.4 #4: the loader's
// contract IS the SQL boundary. We mock `query` / `registerCsvFile` /
// `registerTable` / `registerCsvAsTable` (the explicit carve-out from
// Holy Law #7) and pin:
//   - happy path        - given JOINed PC rows, the loader assembles the
//                         NationalPcWinner shape NationalElectionsAtlas
//                         already renders.
//   - identity bridge   - ECI-form unit_id + join_key reconstructed from
//                         LGD slug + delim_year + eci_no (the only place
//                         LGD vocabulary crosses into the render arms).
//   - not_published     - zero PC rows for the event -> partial /
//                         not_published with empty list.
//   - failed            - injected throw -> failed arm + retry callable.
//   - registration shape - the new flip registers ONLY the 2 CSV URLs
//                          + dim_parties (via registerCsvAsTable, X1a);
//                          F1.3b explicitly drops dim_pcs, dim_persons,
//                          election_results, elections_candidacies.
//
// We mock `csvColumnsClause` from `../canonical/csv-columns` so the
// runtime fetch of columns.json never happens. The clause shape itself
// is pinned by `csv-columns.test.ts`; here we only care that the
// loader threaded a clause string into the read_csv call.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerCsvFile: vi.fn(async () => undefined),
  registerCsvAsTable: vi.fn(async () => "dim_parties"),
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

import { query, registerCsvAsTable, registerCsvFile, registerTable } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { loadNationalPcWinners } from "./national-elections";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsv = vi.mocked(registerCsvFile);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedRegister = vi.mocked(registerTable);
const mockedClause = vi.mocked(csvColumnsClause);

// Two PCs in Tamil Nadu (S22), one in Andhra Pradesh (S01) - all
// 2008-delimitation. The on-disk LGD-form entity_id is what
// electoral.csv carries; the loader translates state slug + eci_no +
// delim_year to the ECI-form unit_id the tile-cartogram joins on.
const pcWinnerRows = [
  {
    pc_entity_id: "IN-PC-2008-tamil-nadu-39",
    state_slug: "tamil-nadu",
    pc_no: 39,
    delim_year: 2008,
    pc_name: "KANYAKUMARI",
    party_id: "parties.IN.INC",
    party_eci_code: "742",
    party_short: "INC",
    brand_colour_hex: "#003c79",
    brand_colour_confidence: "high",
    margin_pct: 22.51,
    turnout_pct: 75.21,
    winner_candidate_name: "VASANTHAKUMAR H",
    symbol_asset_path: "party-symbols/hand.svg",
  },
  {
    pc_entity_id: "IN-PC-2008-tamil-nadu-1",
    state_slug: "tamil-nadu",
    pc_no: 1,
    delim_year: 2008,
    pc_name: "THIRUVALLUR",
    party_id: "parties.IN.DMK",
    party_eci_code: "1234",
    party_short: "DMK",
    brand_colour_hex: "#ff0000",
    brand_colour_confidence: "high",
    margin_pct: 18.4,
    turnout_pct: 71.05,
    winner_candidate_name: "DR. K. JAYAKUMAR",
    symbol_asset_path: "party-symbols/rising-sun.svg",
  },
  {
    pc_entity_id: "IN-PC-2008-andhra-pradesh-445",
    state_slug: "andhra-pradesh",
    pc_no: 1,
    delim_year: 2008,
    pc_name: "ARUKU",
    party_id: "parties.IN.YSRCP",
    party_eci_code: "1888",
    party_short: "YSRCP",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    margin_pct: 20.86,
    turnout_pct: 78.5,
    winner_candidate_name: "GODDETI. MADHAVI",
    symbol_asset_path: null,
  },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegisterCsv.mockReset();
  mockedRegisterCsvAsTable.mockReset();
  mockedRegister.mockReset();
  mockedClause.mockReset();
  mockedRegisterCsv.mockResolvedValue(undefined);
  mockedRegisterCsvAsTable.mockResolvedValue("dim_parties");
  mockedRegister.mockResolvedValue("noop");
  mockedClause.mockResolvedValue("columns={MOCKED}");
});

describe("loadNationalPcWinners - happy path", () => {
  it("assembles NationalPcWinner[] from JOINed PC rows", async () => {
    mockedQuery.mockResolvedValueOnce(pcWinnerRows);

    const res = await loadNationalPcWinners("LsGenApr2019");
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;

    expect(res.data).toHaveLength(3);
    expect(res.data[0]).toMatchObject({
      pc_no: 39,
      state_code: "S22",
      pc_name: "KANYAKUMARI",
      party_id: "parties.IN.INC",
      party_short: "INC",
      margin_pct: 22.51,
      turnout_pct: 75.21,
      winner_candidate_name: "VASANTHAKUMAR H",
      brand_colour_hex: "#003c79",
      brand_colour_confidence: "high",
    });
  });

  it("reconstructs ECI-form unit_id + join_key from LGD slug + delim_year + eci_no", async () => {
    mockedQuery.mockResolvedValueOnce(pcWinnerRows);

    const res = await loadNationalPcWinners("LsGenApr2019");
    if (res.status !== "ok") throw new Error("expected ok");

    // tamil-nadu -> S22
    expect(res.data[0].unit_id).toBe("IN-PC-2008-S22-39");
    expect(res.data[0].join_key).toBe("S22_39");
    expect(res.data[1].unit_id).toBe("IN-PC-2008-S22-1");
    expect(res.data[1].join_key).toBe("S22_1");

    // andhra-pradesh -> S01
    expect(res.data[2].unit_id).toBe("IN-PC-2008-S01-1");
    expect(res.data[2].join_key).toBe("S01_1");
  });

  it("sets winner_age to null (F1.3b regression vs pre-CSV parquet world)", async () => {
    mockedQuery.mockResolvedValueOnce(pcWinnerRows);

    const res = await loadNationalPcWinners("LsGenApr2019");
    if (res.status !== "ok") throw new Error("expected ok");

    for (const w of res.data) {
      expect(w.winner_age).toBeNull();
    }
  });

  it("registers the 2 CSV URLs + dim_parties (CSV-as-table); drops all 4 F1.3b parquets", async () => {
    mockedQuery.mockResolvedValueOnce(pcWinnerRows);

    await loadNationalPcWinners("LsGenApr2019");

    // 2 CSV URL registrations (parliament summary + entities/electoral).
    expect(mockedRegisterCsv).toHaveBeenCalledTimes(2);
    const csvUrls = mockedRegisterCsv.mock.calls.map((c) => c[0]);
    const allUrls = csvUrls.join(" | ");
    expect(allUrls).toContain(
      "/elections/parliament/election=2019/summary.csv",
    );
    expect(allUrls).toContain("/data/entities/electoral.csv");

    // X1a CSV-as-table: dim_parties flipped from parquet to CSV-backed view.
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls
      .map((c) => c[0])
      .sort();
    expect(csvAsTableIds).toEqual(["elections.dim_parties"]);

    // ZERO parquet `registerTable` calls remain on this surface.
    const parquetTables = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(parquetTables).toEqual([]);

    // ZERO requests for the F1.3b-decommissioned parquets.
    expect(parquetTables).not.toContain("elections.elections_candidacies");
    expect(parquetTables).not.toContain("elections.dim_persons");
    expect(parquetTables).not.toContain("elections.dim_pcs");
    expect(parquetTables).not.toContain("elections.election_results");
    // X1a flipped: dim_parties is NO LONGER on the parquet path.
    expect(parquetTables).not.toContain("elections.dim_parties");
  });

  it("issues read_csv SQL against parliament/summary.csv (no read_parquet)", async () => {
    mockedQuery.mockResolvedValueOnce(pcWinnerRows);

    await loadNationalPcWinners("LsGenApr2019");

    const sqls = mockedQuery.mock.calls.map((c) => c[0]);
    expect(sqls).toHaveLength(1);
    expect(sqls[0]).toContain("read_csv(");
    expect(sqls[0]).toContain(
      "/elections/parliament/election=2019/summary.csv",
    );
    expect(sqls[0]).toContain("/entities/electoral.csv");
    expect(sqls[0]).toContain("columns={MOCKED}");
    expect(sqls[0]).not.toContain("read_parquet(");

    // Filter shape: PC entity-kind only.
    expect(sqls[0]).toContain("e.entity_kind = 'pc'");
  });
});

describe("loadNationalPcWinners - partial / not_published", () => {
  it("returns partial when summary has zero PC rows for the event", async () => {
    mockedQuery.mockResolvedValueOnce([]);

    const res = await loadNationalPcWinners("LsGenJun2024");
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.data).toEqual([]);
    expect(res.reason).toBe("not_published");
  });

  it("filters out PC rows that lack a margin_pct value", async () => {
    mockedQuery.mockResolvedValueOnce([
      { ...pcWinnerRows[0], margin_pct: null },
      pcWinnerRows[1],
    ]);

    const res = await loadNationalPcWinners("LsGenApr2019");
    if (res.status !== "ok") throw new Error("expected ok");
    expect(res.data).toHaveLength(1);
    expect(res.data[0].pc_no).toBe(1);
  });
});

describe("loadNationalPcWinners - failed", () => {
  it("returns failed when the CSV/SQL boundary throws", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("network down"));

    const res = await loadNationalPcWinners("LsGenApr2019");
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(typeof res.retry).toBe("function");
    expect(res.reason).toBeDefined();
  });

  it("exposes a working retry closure", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("transient"));
    const res = await loadNationalPcWinners("LsGenApr2019");
    if (res.status !== "failed") throw new Error("expected failed");
    if (typeof res.retry !== "function") throw new Error("expected retry closure");

    mockedQuery.mockResolvedValueOnce(pcWinnerRows);
    const retried = (await res.retry()) as { status: string };
    expect(retried.status).toBe("ok");
  });
});

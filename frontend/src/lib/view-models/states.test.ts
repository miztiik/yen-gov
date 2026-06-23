// Unit tests for the states view-model loader.
// Perf plan Row 2 (option B, 2026-06-23): the loader flipped from
// DuckDB-WASM (`read_csv` over geo.csv) to a plain `fetch` + JS parse
// (`parseStatesCsv`) so the always-mounted scope picker no longer boots
// the wasm engine on chrome/docs pages. Tests now mock `fetch` (the
// loader's only boundary) and exercise the pure parser directly.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  loadStates,
  parseStatesCsv,
  eciFromStateName,
  lgdCodeToEci,
  __resetForTests,
} from "./states";

// geo.csv-shaped fixture. The ECI / LGD / ISO codes ride in the
// pipe-delimited `aliases` column (extracted by parseStatesCsv with the
// same patterns the retired SQL used). Rows: 5 valid states + a district
// (wrong kind), an lgd-less state, and an eci-less state (all dropped).
const GEO_CSV = [
  "entity_id,name,parent,entity_kind,aliases",
  "IN-S22,Tamil Nadu,IN,state,S22|lgd:33|IN-TN",
  "IN-S11,Kerala,IN,state,S11|lgd:32|IN-KL",
  "IN-U05,Delhi,IN,state,U05|lgd:7|IN-DL",
  "IN-U01,Andaman & Nicobar,IN,state,U01|lgd:35|IN-AN",
  "IN-U08,Jammu & Kashmir,IN,state,U08|lgd:1|IN-JK",
  "IN-S22-D1,Chennai,IN-S22,district,lgd:101",
  "IN-S99,NoLgd,IN,state,S99|IN-XX",
  "IN-X00,NoEci,IN,state,lgd:88|IN-XY",
  "",
].join("\n");

function mockFetchCsv(text: string, ok = true): ReturnType<typeof vi.fn> {
  const f = vi.fn(async () => new Response(text, { status: ok ? 200 : 500 }));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  vi.stubGlobal("fetch", f as any);
  return f;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("parseStatesCsv (geo.csv -> StateRow[], no DuckDB)", () => {
  it("keeps only entity_kind='state' rows with eci_code + display_name + lgd_code", () => {
    const out = parseStatesCsv(GEO_CSV);
    // 5 valid; the district, the lgd-less, and the eci-less rows dropped.
    expect(out).toHaveLength(5);
    expect(out.map((r) => r.eci_code)).toEqual(["S11", "S22", "U01", "U05", "U08"]);
  });

  it("extracts ECI / LGD / ISO from aliases and synthesises entity_id", () => {
    const tn = parseStatesCsv(GEO_CSV).find((r) => r.eci_code === "S22")!;
    expect(tn).toMatchObject({
      entity_id: "IN-S22",
      eci_code: "S22",
      display_name: "Tamil Nadu",
      boundary_join_name: "Tamil Nadu",
      boundary_join_key: "33",
      lgd_code: "33",
      iso_3166_2: "IN-TN",
    });
  });

  it("sets boundary_join_key=lgd_code and boundary_join_name=display_name on every row", () => {
    for (const r of parseStatesCsv(GEO_CSV)) {
      expect(r.boundary_join_key).toBe(r.lgd_code);
      expect(r.boundary_join_name).toBe(r.display_name);
    }
  });

  it("sorts by eci_code (string order, matching the retired SQL ORDER BY)", () => {
    expect(parseStatesCsv(GEO_CSV).map((r) => r.eci_code)).toEqual([
      "S11",
      "S22",
      "U01",
      "U05",
      "U08",
    ]);
  });

  it("handles a quoted name containing a comma (reused parseCsvLine)", () => {
    const csv =
      'entity_id,name,parent,entity_kind,aliases\nIN-S40,"Foo, Bar",IN,state,S40|lgd:200|IN-FB';
    const out = parseStatesCsv(csv);
    expect(out).toHaveLength(1);
    expect(out[0].display_name).toBe("Foo, Bar");
  });

  it("returns [] for empty / header-only input", () => {
    expect(parseStatesCsv("")).toEqual([]);
    expect(parseStatesCsv("entity_id,name,parent,entity_kind,aliases")).toEqual([]);
  });

  it("throws when required columns are missing from the header", () => {
    expect(() => parseStatesCsv("entity_id,foo,bar\nIN-S1,x,y")).toThrow(
      /missing required columns/,
    );
  });
});

describe("loadStates (fetch geo.csv, no DuckDB)", () => {
  beforeEach(() => __resetForTests());

  it("fetches the geo.csv URL once and returns the parsed states", async () => {
    const f = mockFetchCsv(GEO_CSV);
    const out = await loadStates();
    expect(out).toHaveLength(5);
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toContain("data/entities/geo.csv");
  });

  it("caches across calls within a session; __resetForTests clears it", async () => {
    const f = mockFetchCsv(GEO_CSV);
    const a = await loadStates();
    const b = await loadStates();
    expect(a).toBe(b);
    expect(f).toHaveBeenCalledTimes(1);
    __resetForTests();
    await loadStates();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("throws on a non-OK response", async () => {
    mockFetchCsv("nope", false);
    await expect(loadStates()).rejects.toThrow(/states: fetch failed/);
  });
});

describe("eciFromStateName", () => {
  beforeEach(() => {
    __resetForTests();
    mockFetchCsv(GEO_CSV);
  });

  it("returns the ECI code for an exact display_name match", async () => {
    expect(await eciFromStateName("Tamil Nadu")).toBe("S22");
    expect(await eciFromStateName("Kerala")).toBe("S11");
  });

  it("resolves the shortform UT names geo.csv publishes directly", async () => {
    expect(await eciFromStateName("Delhi")).toBe("U05");
    expect(await eciFromStateName("Andaman & Nicobar")).toBe("U01");
    expect(await eciFromStateName("Jammu & Kashmir")).toBe("U08");
  });

  it("returns null for an unknown name", async () => {
    expect(await eciFromStateName("Atlantis")).toBeNull();
  });

  it.each([null, undefined, ""])("returns null for %s", async (input) => {
    expect(await eciFromStateName(input as string | null | undefined)).toBeNull();
  });
});

describe("lgdCodeToEci", () => {
  beforeEach(() => {
    __resetForTests();
    mockFetchCsv(GEO_CSV);
  });

  it("resolves an integer LGD code to the ECI code", async () => {
    expect(await lgdCodeToEci(33)).toBe("S22");
    expect(await lgdCodeToEci(32)).toBe("S11");
  });

  it("resolves a zero-padded VARCHAR LGD code (parseInt-normalised)", async () => {
    expect(await lgdCodeToEci("07")).toBe("U05");
    expect(await lgdCodeToEci("35")).toBe("U01");
    expect(await lgdCodeToEci("01")).toBe("U08");
  });

  it("resolves a plain unpadded string LGD code", async () => {
    expect(await lgdCodeToEci("7")).toBe("U05");
    expect(await lgdCodeToEci("33")).toBe("S22");
  });

  it("returns null for null / undefined / empty / non-numeric input", async () => {
    expect(await lgdCodeToEci(null)).toBeNull();
    expect(await lgdCodeToEci(undefined)).toBeNull();
    expect(await lgdCodeToEci("")).toBeNull();
    expect(await lgdCodeToEci("not-a-number")).toBeNull();
  });

  it("returns null for an unknown LGD code", async () => {
    expect(await lgdCodeToEci(999)).toBeNull();
    expect(await lgdCodeToEci("999")).toBeNull();
  });
});

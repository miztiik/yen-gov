import { describe, it, expect, vi, afterEach } from "vitest";

import {
  _resetConstituencyLookupCachesForTesting,
  electoralEntitiesUrl,
  findConstituencyBySlug,
  parseElectoralCsv,
  resolveConstituencyFromRows,
  type ConstituencyEntity,
} from "./constituency-lookup";

const FIXTURE_CSV = [
  "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation",
  "IN-AC-2008-chhattisgarh-2369,Bastar,ac,2008,chhattisgarh,IN-PC-2008-chhattisgarh-294,85,,",
  "IN-PC-2008-chhattisgarh-294,Bastar,pc,2008,chhattisgarh,chhattisgarh,9,,",
  "IN-PC-2008-chhattisgarh-296,Durg,pc,2008,chhattisgarh,chhattisgarh,10,,",
  // Cross-state homonym + earlier delim — ensures state filter + latest-delim
  // selection both work.
  "IN-AC-1976-chhattisgarh-9999,Bastar,ac,1976,chhattisgarh,IN-PC-1976-chhattisgarh-9,85,,",
  "IN-PC-2008-andhra-pradesh-411,Amalapuram,pc,2008,andhra-pradesh,andhra-pradesh,2,,",
].join("\n");

afterEach(() => {
  _resetConstituencyLookupCachesForTesting();
  vi.restoreAllMocks();
});

describe("parseElectoralCsv", () => {
  it("parses the documented column order into typed rows", () => {
    const rows = parseElectoralCsv(FIXTURE_CSV);
    expect(rows.length).toBe(5);
    const bastarPc = rows.find(
      (r) => r.entity_id === "IN-PC-2008-chhattisgarh-294",
    )!;
    expect(bastarPc).toMatchObject<Partial<ConstituencyEntity>>({
      entity_id: "IN-PC-2008-chhattisgarh-294",
      name: "Bastar",
      entity_kind: "pc",
      delim_year: 2008,
      state: "chhattisgarh",
      eci_no: 9,
    });
  });

  it("skips header and empty lines", () => {
    expect(parseElectoralCsv("")).toEqual([]);
    expect(parseElectoralCsv("entity_id,name\n")).toEqual([]);
  });

  it("filters out non-ac/pc kinds and rows with non-integer eci_no", () => {
    const csv = [
      "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation",
      "IN-X,Foo,district,2008,karnataka,karnataka,9,,",
      "IN-Y,Bar,ac,2008,karnataka,IN-PC-2008-karnataka-1,not-an-int,,",
    ].join("\n");
    expect(parseElectoralCsv(csv)).toEqual([]);
  });
});

describe("resolveConstituencyFromRows", () => {
  const rows = parseElectoralCsv(FIXTURE_CSV);

  it("matches by (state, kind, slugified-name)", () => {
    const hit = resolveConstituencyFromRows(rows, {
      state: "chhattisgarh",
      kind: "pc",
      name_slug: "bastar",
    });
    expect(hit?.entity_id).toBe("IN-PC-2008-chhattisgarh-294");
    expect(hit?.eci_no).toBe(9);
  });

  it("dispatches AC vs PC for the same name in the same state", () => {
    const ac = resolveConstituencyFromRows(rows, {
      state: "chhattisgarh",
      kind: "ac",
      name_slug: "bastar",
    });
    const pc = resolveConstituencyFromRows(rows, {
      state: "chhattisgarh",
      kind: "pc",
      name_slug: "bastar",
    });
    expect(ac?.entity_kind).toBe("ac");
    expect(pc?.entity_kind).toBe("pc");
    expect(ac?.eci_no).toBe(85);
    expect(pc?.eci_no).toBe(9);
  });

  it("picks the latest delim_year when multiple matches collide", () => {
    // FIXTURE_CSV has 2 chhattisgarh AC "Bastar" rows (1976 + 2008);
    // the 2008 row wins.
    const hit = resolveConstituencyFromRows(rows, {
      state: "chhattisgarh",
      kind: "ac",
      name_slug: "bastar",
    });
    expect(hit?.entity_id).toBe("IN-AC-2008-chhattisgarh-2369");
    expect(hit?.delim_year).toBe(2008);
  });

  it("returns null when state does not match", () => {
    expect(
      resolveConstituencyFromRows(rows, {
        state: "tamil-nadu",
        kind: "pc",
        name_slug: "bastar",
      }),
    ).toBeNull();
  });

  it("returns null when name slug does not match", () => {
    expect(
      resolveConstituencyFromRows(rows, {
        state: "chhattisgarh",
        kind: "pc",
        name_slug: "no-such-place",
      }),
    ).toBeNull();
  });
});

describe("findConstituencyBySlug (fetch stubbed)", () => {
  function stubFetchOk(body: string): void {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(body, {
          status: 200,
          headers: { "Content-Type": "text/csv" },
        }),
      ),
    );
  }

  it("hits the canonical electoral.csv URL", async () => {
    const spy = vi.fn(
      async () => new Response(FIXTURE_CSV, { status: 200 }),
    );
    vi.stubGlobal("fetch", spy);
    await findConstituencyBySlug("chhattisgarh", "pc", "bastar");
    expect(spy).toHaveBeenCalled();
    const calls = spy.mock.calls as unknown as Array<[string]>;
    const url = calls[0][0];
    expect(url).toBe(electoralEntitiesUrl());
    expect(url).toContain("data/entities/electoral.csv");
  });

  it("returns the resolved entity when present", async () => {
    stubFetchOk(FIXTURE_CSV);
    const hit = await findConstituencyBySlug(
      "chhattisgarh",
      "pc",
      "bastar",
    );
    expect(hit?.entity_id).toBe("IN-PC-2008-chhattisgarh-294");
    expect(hit?.eci_no).toBe(9);
  });

  it("returns null when the slug does not exist", async () => {
    stubFetchOk(FIXTURE_CSV);
    const miss = await findConstituencyBySlug(
      "chhattisgarh",
      "pc",
      "not-a-real-seat",
    );
    expect(miss).toBeNull();
  });

  it("returns null when the CSV cannot be fetched", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("", { status: 404 })),
    );
    const miss = await findConstituencyBySlug(
      "chhattisgarh",
      "pc",
      "bastar",
    );
    expect(miss).toBeNull();
  });
});

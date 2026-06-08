// Unit tests for the typed-read CSV column-map helper (F1.3a).
//
// Per CLAUDE.md §15 + parent plan 22.4 #4: the contract is
//   "every read_csv(...) call passes columns={...} derived from
//    datasets/data/_schema/columns.json".
// These tests pin: (a) the fetch + cache shape, (b) file_class glob
// matching for partition path segments (`state=*`, `election=*`),
// (c) the DuckDB SQL fragment building rules.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  __resetForTests,
  buildColumnsClause,
  candidateFileClassKeys,
  csvColumnsClause,
  csvColumnsSpec,
  fileClassForCsvPath,
  loadCsvColumnsContract,
  type CsvColumnsContract,
} from "./csv-columns";

const FIXTURE: CsvColumnsContract = {
  $schema: "./columns.schema.json",
  $schema_version: "1.0",
  file_classes: {
    "datasets/data/entities/electoral.csv": {
      notes: "fixture - electoral entity table",
      columns: [
        { name: "entity_id", dtype: "string", nullable: false, pk: true },
        { name: "name", dtype: "string", nullable: false },
        { name: "entity_kind", dtype: "string", nullable: false },
        { name: "delim_year", dtype: "integer", nullable: false },
        { name: "state", dtype: "string", nullable: false },
        { name: "parent", dtype: "string", nullable: true },
        { name: "eci_no", dtype: "integer", nullable: true },
        { name: "aliases", dtype: "string", nullable: true },
        { name: "reservation", dtype: "string", nullable: true },
      ],
    },
    "datasets/elections/assembly/state=*/election=*/candidacies.csv": {
      notes: "fixture - assembly candidacies (per state-year)",
      columns: [
        { name: "entity_id", dtype: "string", nullable: false },
        { name: "election_year", dtype: "integer", nullable: false },
        { name: "constituency_no", dtype: "integer", nullable: false },
        { name: "candidate_name", dtype: "string", nullable: false },
        { name: "votes", dtype: "integer", nullable: false },
        { name: "vote_share_pct", dtype: "number", nullable: true, derived: true },
        { name: "is_incumbent", dtype: "boolean", nullable: true },
      ],
    },
    "datasets/data/datapoints/geo/*.csv": {
      notes: "fixture - per-indicator long-format CSV (filename-glob file class)",
      columns: [
        { name: "entity_id", dtype: "string", nullable: false, pk: true },
        { name: "time", dtype: "integer", nullable: false, pk: true },
        { name: "value", dtype: "number", nullable: true },
        { name: "source_id", dtype: "string", nullable: false },
      ],
    },
  },
};

function mockColumnsJson(body: unknown, status = 200): void {
  const fetchMock = vi.fn(async (input: unknown) => {
    const url = typeof input === "string" ? input : (input as { url: string }).url;
    if (!url.endsWith("/data/_schema/columns.json")) {
      throw new Error(`unexpected fetch URL: ${url}`);
    }
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: status === 200 ? "OK" : "ERR",
      json: async () => body,
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
}

beforeEach(() => {
  __resetForTests();
});

afterEach(() => {
  vi.unstubAllGlobals();
  __resetForTests();
});

describe("fileClassForCsvPath", () => {
  it("collapses partition value segments to globs", () => {
    expect(
      fileClassForCsvPath(
        "datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
      ),
    ).toBe(
      "datasets/elections/assembly/state=*/election=*/candidacies.csv",
    );
  });

  it("collapses parliament partition", () => {
    expect(
      fileClassForCsvPath(
        "datasets/elections/parliament/election=2019/candidacies.csv",
      ),
    ).toBe("datasets/elections/parliament/election=*/candidacies.csv");
  });

  it("leaves non-partitioned paths untouched", () => {
    expect(fileClassForCsvPath("datasets/data/entities/electoral.csv")).toBe(
      "datasets/data/entities/electoral.csv",
    );
  });
});

describe("candidateFileClassKeys (W1 2026-06-08 filename-glob fix)", () => {
  it("emits [exact] for a path that exactly matches a non-glob file_class", () => {
    expect(
      candidateFileClassKeys("datasets/data/entities/electoral.csv"),
    ).toEqual([
      "datasets/data/entities/electoral.csv",
      "datasets/data/entities/*.csv",
    ]);
  });

  it("emits [partition-glob, filename-glob] for a per-indicator datapoints CSV", () => {
    // The fileClassForCsvPath collapse is a no-op (no `=` segments);
    // the filename-glob fallback `<dirname>/*.csv` is what unblocks the
    // datapoints/geo/*.csv file_class lookup. Pre-2026-06-08 this lookup
    // returned only the exact path and silently 404'd into "no file_class
    // match" for every per-indicator canonical CSV in the energy +
    // livestock allowlist + the new W1 cohort.
    expect(
      candidateFileClassKeys(
        "datasets/data/datapoints/geo/own-tax-revenue-inr-crore.csv",
      ),
    ).toEqual([
      "datasets/data/datapoints/geo/own-tax-revenue-inr-crore.csv",
      "datasets/data/datapoints/geo/*.csv",
    ]);
  });

  it("emits [partition-glob, filename-glob] for an electoral per-state candidacies CSV", () => {
    // Partition collapse runs first; filename-glob fallback is preserved.
    expect(
      candidateFileClassKeys(
        "datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
      ),
    ).toEqual([
      "datasets/elections/assembly/state=*/election=*/candidacies.csv",
      "datasets/elections/assembly/state=*/election=*/*.csv",
    ]);
  });

  it("skips the filename-glob fallback when the path has no extension", () => {
    // Defensive: a bare path with no `.<ext>` should not emit a spurious
    // duplicate candidate. The single partition-collapsed result is enough.
    expect(candidateFileClassKeys("datasets/data/no-ext-file")).toEqual([
      "datasets/data/no-ext-file",
    ]);
  });
});

describe("buildColumnsClause", () => {
  it("maps every columns.json dtype to its DuckDB literal", () => {
    const spec = {
      columns: [
        { name: "s", dtype: "string", nullable: false },
        { name: "i", dtype: "integer", nullable: false },
        { name: "n", dtype: "number", nullable: false },
        { name: "b", dtype: "boolean", nullable: false },
        { name: "d", dtype: "date", nullable: false },
        { name: "ts", dtype: "datetime", nullable: false },
      ] as const,
    };
    const clause = buildColumnsClause(spec);
    expect(clause).toBe(
      "columns={'s': 'VARCHAR', 'i': 'BIGINT', 'n': 'DOUBLE', 'b': 'BOOLEAN', 'd': 'DATE', 'ts': 'TIMESTAMP'}",
    );
  });

  it("escapes embedded single quotes in column names", () => {
    const spec = {
      columns: [{ name: "weird'name", dtype: "string", nullable: false }],
    } as const;
    expect(buildColumnsClause(spec)).toBe(
      "columns={'weird''name': 'VARCHAR'}",
    );
  });
});

describe("loadCsvColumnsContract", () => {
  it("fetches once and caches the promise across concurrent callers", async () => {
    mockColumnsJson(FIXTURE);

    const [a, b] = await Promise.all([
      loadCsvColumnsContract(),
      loadCsvColumnsContract(),
    ]);

    expect(a).toBe(b);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it("does not cache failed fetches", async () => {
    mockColumnsJson({}, 500);

    await expect(loadCsvColumnsContract()).rejects.toThrow(
      /csv-columns: fetch failed/,
    );

    // A subsequent call should retry (cache should be cleared on the
    // rejected promise).
    mockColumnsJson(FIXTURE);
    const ok = await loadCsvColumnsContract();
    expect(ok.file_classes["datasets/data/entities/electoral.csv"]).toBeDefined();
  });

  it("rejects malformed bodies missing file_classes", async () => {
    mockColumnsJson({ $schema: "x" });
    await expect(loadCsvColumnsContract()).rejects.toThrow(
      /malformed columns.json/,
    );
  });
});

describe("csvColumnsClause", () => {
  it("returns the typed DuckDB columns={} fragment for a known file_class", async () => {
    mockColumnsJson(FIXTURE);
    const clause = await csvColumnsClause(
      "datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
    expect(clause).toContain("'entity_id': 'VARCHAR'");
    expect(clause).toContain("'election_year': 'BIGINT'");
    expect(clause).toContain("'votes': 'BIGINT'");
    expect(clause).toContain("'vote_share_pct': 'DOUBLE'");
    expect(clause).toContain("'is_incumbent': 'BOOLEAN'");
  });

  it("works for the electoral entities path (no glob segments)", async () => {
    mockColumnsJson(FIXTURE);
    const clause = await csvColumnsClause("datasets/data/entities/electoral.csv");
    expect(clause).toContain("'entity_id': 'VARCHAR'");
    expect(clause).toContain("'eci_no': 'BIGINT'");
    expect(clause).toContain("'reservation': 'VARCHAR'");
  });

  it("falls back to the filename-glob file_class for per-indicator CSVs (W1 2026-06-08)", async () => {
    // The W1 RBI State Finances cohort + the energy / livestock cohorts
    // all key per-indicator CSV file_classes by filename wildcard
    // (`datasets/data/datapoints/geo/*.csv`). Before the candidate-key
    // fallback landed, this lookup threw "no file_class match" because
    // `fileClassForCsvPath` only collapses `=*` segments, leaving the
    // concrete filename untouched. Pin the fix.
    mockColumnsJson(FIXTURE);
    const clause = await csvColumnsClause(
      "datasets/data/datapoints/geo/own-tax-revenue-inr-crore.csv",
    );
    expect(clause).toBe(
      "columns={'entity_id': 'VARCHAR', 'time': 'BIGINT', 'value': 'DOUBLE', 'source_id': 'VARCHAR'}",
    );
  });

  it("throws when the file_class is absent from the contract", async () => {
    mockColumnsJson(FIXTURE);
    await expect(
      csvColumnsClause("datasets/elections/assembly/state=x/election=1/unknown.csv"),
    ).rejects.toThrow(/no file_class match/);
  });
});

describe("csvColumnsSpec", () => {
  it("returns the raw column spec list for type-checking callers", async () => {
    mockColumnsJson(FIXTURE);
    const cols = await csvColumnsSpec(
      "datasets/data/entities/electoral.csv",
    );
    expect(cols.map((c) => c.name)).toEqual([
      "entity_id",
      "name",
      "entity_kind",
      "delim_year",
      "state",
      "parent",
      "eci_no",
      "aliases",
      "reservation",
    ]);
    expect(cols[0]).toMatchObject({ name: "entity_id", pk: true });
  });
});

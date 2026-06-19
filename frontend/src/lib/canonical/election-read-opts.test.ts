// Regression guard for the centralized hardened election CSV read
// options (fix/election-csv-read-hardening).
//
// The whole class of "election map / Data Explorer / Psephlab is broken"
// bugs came from election `read_csv(...)` clauses that did NOT carry
// `auto_detect=false` (so the DuckDB-WASM dialect sniffer mis-detected
// the comma/quote-laden CSVs) and did NOT carry `null_padding=true` (so
// the 20-column candidacies.csv files failed against the 24-column
// forward-compatible schema). This pins the exact options string + the
// helper contract so the dialect can never silently drift back.

import { describe, expect, it } from "vitest";
import {
  ELECTION_CSV_READ_OPTS,
  withElectionReadOpts,
} from "./election-read-opts";

describe("ELECTION_CSV_READ_OPTS", () => {
  it("pins the sniffer off (auto_detect=false)", () => {
    expect(ELECTION_CSV_READ_OPTS).toContain("auto_detect=false");
  });

  it("NULL-pads the 4 missing trailing affidavit columns (null_padding=true)", () => {
    expect(ELECTION_CSV_READ_OPTS).toContain("null_padding=true");
  });

  it("declares the header row + the explicit RFC-4180 comma dialect", () => {
    expect(ELECTION_CSV_READ_OPTS).toContain("header=true");
    expect(ELECTION_CSV_READ_OPTS).toContain("delim=','");
    expect(ELECTION_CSV_READ_OPTS).toContain("quote='\"'");
    expect(ELECTION_CSV_READ_OPTS).toContain("escape='\"'");
  });
});

describe("withElectionReadOpts", () => {
  it("appends the options after the columns clause", () => {
    expect(withElectionReadOpts("columns={X}")).toBe(
      `columns={X}, ${ELECTION_CSV_READ_OPTS}`,
    );
  });

  it("produces a read_csv tail the sniffer cannot interfere with", () => {
    const sql = `read_csv('u.csv', ${withElectionReadOpts("columns={X}")})`;
    expect(sql).toContain("columns={X}");
    expect(sql).toContain("auto_detect=false");
    expect(sql).toContain("null_padding=true");
  });
});

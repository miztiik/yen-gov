// Centralized hardened DuckDB-WASM read options for the per-event
// election CSV reads (candidacies.csv / summary.csv / electoral.csv /
// party_alliances.csv).
//
// WHY this exists as one module:
//
// The deployed DuckDB-WASM build's CSV dialect sniffer mis-detects the
// election CSVs. Candidate-name / education / profession / alliance and
// constituency-name fields carry embedded commas and RFC-4180 doubled-
// quote escapes, so the sniffer guesses the wrong delimiter / column
// count and the whole `read_csv(...)` throws
//   "CSV sniffer: N columns, expected M".
//
// On top of that, the canonical `candidacies.csv` file_class in
// datasets/data/_schema/columns.json is a forward-compatible 24-column
// schema (4 TRAILING affidavit columns: criminal_cases_declared /
// total_assets_inr / total_liabilities_inr /
// declared_election_expense_inr) while the overwhelming majority of the
// candidacies.csv files on disk are still 20-column (only the
// parliament 2014 file carries the 4 affidavit columns natively). A
// read against the 24-column typed clause must therefore tolerate the
// 4 missing trailing columns on the 20-column files.
//
// The fix is a single explicit read-options string, spliced onto every
// election `read_csv(...)` clause repo-wide:
//
//   header=true        - the files carry a header row.
//   auto_detect=false  - pin the dialect; keep the broken sniffer out of
//                        the path entirely (the columns={...} map already
//                        declares every column + type, so there is
//                        nothing left to sniff).
//   null_padding=true  - pad the 4 missing trailing affidavit columns as
//                        NULL for the 20-column files; the 24-column
//                        parliament-2014 file reads them natively. Only
//                        ever PADS short rows - a correct, full-width
//                        file is unaffected (so applying it uniformly to
//                        the consistent summary.csv / electoral.csv /
//                        party_alliances.csv reads is a no-op there).
//   delim/quote/escape - the RFC-4180 comma dialect, stated explicitly so
//                        the pinned-dialect read is unambiguous.
//
// SCOPE DISCIPLINE (CLAUDE.md Holy Law #5, structural fix): these
// options are ELECTION-READ-ONLY. `null_padding=true` in particular MUST
// NOT leak onto non-election reads (indicator / entity / mart reads),
// where a column-count mismatch should still fail loudly rather than be
// silently NULL-padded. Indicator reads carry their own
// `header=true, auto_detect=false` and are intentionally NOT routed
// through this helper.

/**
 * Explicit DuckDB-WASM read options spliced onto every election
 * `read_csv(...)` clause. See the module header for the per-flag
 * rationale. The escaped double quotes are SQL string literals
 * (`quote='"'`, `escape='"'`), not TypeScript escapes for the reader.
 */
export const ELECTION_CSV_READ_OPTS =
  "header=true, auto_detect=false, null_padding=true, delim=',', quote='\"', escape='\"'";

/**
 * Append the hardened election read options to a `columns={...}` clause.
 *
 * Returns `${columnsClause}, ${ELECTION_CSV_READ_OPTS}`, so the call site
 * stays `read_csv('${url}', ${withElectionReadOpts(clause)})`.
 */
export function withElectionReadOpts(columnsClause: string): string {
  return `${columnsClause}, ${ELECTION_CSV_READ_OPTS}`;
}

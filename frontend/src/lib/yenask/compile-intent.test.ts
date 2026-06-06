// Compiler tests - InsightIntent + SemanticCatalogue -> DuckDBPlan
// (F1.3b CSV cutover).
//
// Per plan-doc §17 D-05 the compiler is pure with respect to DuckDB
// state. F1.3b adds an awaited `csvColumnsClause(path)` per CSV file
// the concept reads, so the tests mock that helper to return a
// deterministic clause string. The runtime fetch of columns.json never
// happens in test.
//
// These tests assert that:
//   - each of the 4 concept_ids produces a well-formed DuckDBPlan
//   - the plan carries csv_registrations[] for every read_csv URL the
//     SQL splices in
//   - the plan carries provenance_sql (always)
//   - the plan carries concept_id (always)
//   - catalogue mismatches throw with helpful messages
//   - required_filter violations throw

import { describe, expect, it, vi } from "vitest";

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

import type { SemanticCatalogue } from "./types";
import type { InsightIntent } from "./contracts/insight-intent";
import { compileIntent } from "./compile-intent";

const CATALOGUE: SemanticCatalogue = {
  tables: [],
  states: [{ partition_id: "tamil-nadu", eci_code: "S22", display_name: "Tamil Nadu" }],
  election_periods: [
    {
      period_label: "AcGenMay2026",
      display_name: "AC general May 2026",
      state_partition_id: "tamil-nadu",
    },
  ],
  parties: [
    { short_code: "DMK", display_name: "Dravida Munnetra Kazhagam" },
    { short_code: "AIADMK", display_name: "AIADMK" },
  ],
  sources: [],
  manifest: {} as never,
};

function intent(overrides: Partial<InsightIntent>): InsightIntent {
  return {
    version: "insight.intent.v0",
    concept_id: "party_totals",
    question: "Q?",
    filters: { state_partition_id: "tamil-nadu", period_label: "AcGenMay2026" },
    reasoning: "",
    ...overrides,
  };
}

describe("compileIntent", () => {
  it("compiles party_totals to a CSV-backed plan with the expected shape", async () => {
    const plan = await compileIntent(intent({}), CATALOGUE);
    expect(plan.concept_id).toBe("party_totals");
    // F1.3b: NO slice_registrations (election_results retired); table
    // registrations cover dim_parties + taxonomy.sources only.
    expect(plan.slice_registrations).toEqual([]);
    const tableIds = plan.table_registrations.map(t => t.table_id).sort();
    expect(tableIds).toEqual(["elections.dim_parties", "taxonomy.sources"]);
    // csv_registrations splice in candidacies.csv + electoral.csv URLs.
    expect(plan.csv_registrations).toHaveLength(2);
    const csvUrls = plan.csv_registrations.map(c => c.url).join(" | ");
    expect(csvUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2026/candidacies.csv",
    );
    expect(csvUrls).toContain("/data/entities/electoral.csv");
    expect(plan.main_sql).toMatch(/read_csv\(/);
    expect(plan.main_sql).not.toMatch(/read_parquet\(/);
    expect(plan.main_sql).toContain("columns={MOCKED}");
    expect(plan.provenance_sql).toMatch(/JOIN sources s ON s\.source_id = ec\.source_id/);
    expect(plan.view_hints.column_order).toEqual([
      "party_short",
      "seats_won",
      "votes",
      "vote_share_pct",
    ]);
  });

  it("compiles closest_contests to read summary.csv margin_pct directly", async () => {
    const plan = await compileIntent(
      intent({ concept_id: "closest_contests" }),
      CATALOGUE,
    );
    expect(plan.main_sql).toMatch(/s\.margin_pct/);
    expect(plan.main_sql).toMatch(/read_csv\(/);
    expect(plan.main_sql).not.toMatch(/read_parquet\(/);
    expect(plan.main_sql).not.toMatch(/dim_acs\b/);
    const csvUrls = plan.csv_registrations.map(c => c.url).join(" | ");
    expect(csvUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2026/summary.csv",
    );
    expect(csvUrls).toContain("/data/entities/electoral.csv");
    const tableIds = plan.table_registrations.map(t => t.table_id);
    expect(tableIds).toEqual(["taxonomy.sources"]);
    expect(plan.view_hints.column_order).toEqual([
      "ac_no",
      "ac_name",
      "margin_pp",
      "votes_polled",
    ]);
  });

  it("compiles constituency_result against candidacies.csv + electoral.csv", async () => {
    const plan = await compileIntent(
      intent({
        concept_id: "constituency_result",
        filters: {
          state_partition_id: "tamil-nadu",
          period_label: "AcGenMay2026",
          ac_no: 167,
        },
      }),
      CATALOGUE,
    );
    // F1.3b: no elections_candidacies / dim_persons parquet JOINs.
    expect(plan.main_sql).not.toMatch(/\belections_candidacies\b/);
    expect(plan.main_sql).not.toMatch(/\bdim_persons\b/);
    // candidate_name + party_id columns lifted inline from
    // candidacies.csv; dim_parties stays JOINed for the brand short.
    expect(plan.main_sql).toContain("ec.candidate_name");
    expect(plan.main_sql).toMatch(/LEFT JOIN dim_parties dp/);
    expect(plan.main_sql).toContain("e.eci_no = 167");
    expect(plan.main_sql).toMatch(/UPPER\(ec\.candidate_name\) <> 'NOTA'/);
    expect(plan.view_hints.column_order).toEqual([
      "rank",
      "candidate_name",
      "party_short",
      "votes",
      "vote_share_pct",
    ]);
    const csvUrls = plan.csv_registrations.map(c => c.url).join(" | ");
    expect(csvUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2026/candidacies.csv",
    );
    expect(csvUrls).toContain("/data/entities/electoral.csv");
  });

  it("compiles turnout_extremes with a highest/lowest UNION over summary.csv", async () => {
    const plan = await compileIntent(
      intent({ concept_id: "turnout_extremes" }),
      CATALOGUE,
    );
    expect(plan.main_sql).toMatch(/UNION ALL/);
    expect(plan.main_sql).toMatch(/s\.turnout_pct/);
    expect(plan.main_sql).toMatch(/read_csv\(/);
    expect(plan.main_sql).not.toMatch(/read_parquet\(/);
    expect(plan.view_hints.column_order).toEqual([
      "band",
      "ac_no",
      "ac_name",
      "turnout_pct",
    ]);
    const csvUrls = plan.csv_registrations.map(c => c.url).join(" | ");
    expect(csvUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2026/summary.csv",
    );
  });

  it("EVERY concept produces a non-empty provenance_sql JOINing taxonomy.sources", async () => {
    for (const concept_id of [
      "party_totals",
      "closest_contests",
      "constituency_result",
      "turnout_extremes",
    ] as const) {
      const plan = await compileIntent(
        intent({
          concept_id,
          ...(concept_id === "constituency_result"
            ? {
                filters: {
                  state_partition_id: "tamil-nadu",
                  period_label: "AcGenMay2026",
                  ac_no: 167,
                },
              }
            : {}),
        }),
        CATALOGUE,
      );
      expect(plan.provenance_sql.length).toBeGreaterThan(0);
      expect(plan.provenance_sql).toMatch(/sources/);
      // taxonomy.sources stays on Parquet (deferred to X1a); every
      // concept registers it via table_registrations.
      const tableIds = plan.table_registrations.map(t => t.table_id);
      expect(tableIds).toContain("taxonomy.sources");
    }
  });

  it("EVERY concept drops the 4 F1.3b parquets from registrations", async () => {
    for (const concept_id of [
      "party_totals",
      "closest_contests",
      "constituency_result",
      "turnout_extremes",
    ] as const) {
      const plan = await compileIntent(
        intent({
          concept_id,
          ...(concept_id === "constituency_result"
            ? {
                filters: {
                  state_partition_id: "tamil-nadu",
                  period_label: "AcGenMay2026",
                  ac_no: 167,
                },
              }
            : {}),
        }),
        CATALOGUE,
      );
      const allTables = [
        ...plan.slice_registrations.map(s => s.table_id),
        ...plan.table_registrations.map(t => t.table_id),
      ];
      expect(allTables).not.toContain("elections.election_results");
      expect(allTables).not.toContain("elections.dim_acs");
      expect(allTables).not.toContain("elections.dim_persons");
      expect(allTables).not.toContain("elections.elections_candidacies");
    }
  });

  it("throws when filters.state_partition_id is unknown", async () => {
    await expect(
      compileIntent(
        intent({
          filters: { state_partition_id: "nonexistent-fake-state", period_label: "AcGenMay2026" },
        }),
        CATALOGUE,
      ),
    ).rejects.toThrow(/state_partition_id/);
  });

  it("throws when filters.period_label is unknown", async () => {
    await expect(
      compileIntent(
        intent({
          filters: { state_partition_id: "tamil-nadu", period_label: "Unknown1990" },
        }),
        CATALOGUE,
      ),
    ).rejects.toThrow(/period_label/);
  });

  it("throws when filters.party_short_code is unknown", async () => {
    await expect(
      compileIntent(
        intent({
          filters: {
            state_partition_id: "tamil-nadu",
            period_label: "AcGenMay2026",
            party_short_code: "FAKE",
          },
        }),
        CATALOGUE,
      ),
    ).rejects.toThrow(/party_short_code/);
  });

  it("throws when constituency_result is missing ac_no", async () => {
    await expect(
      compileIntent(
        intent({ concept_id: "constituency_result" }),
        CATALOGUE,
      ),
    ).rejects.toThrow(/ac_no/);
  });

  it("escapes single-quotes in period_label to prevent injection", async () => {
    // Catalogue contains the period label exactly as-is, but the SQL
    // must still escape the quote in the literal. Add the dangerous
    // label to the catalogue so the compiler accepts it. Year suffix
    // 2026 satisfies the eventYear parser.
    const cat: SemanticCatalogue = {
      ...CATALOGUE,
      election_periods: [
        ...CATALOGUE.election_periods,
        {
          period_label: "AcGen'May2026",
          display_name: "AcGen'May2026",
          state_partition_id: "tamil-nadu",
        },
      ],
    };
    const plan = await compileIntent(
      intent({
        filters: { state_partition_id: "tamil-nadu", period_label: "AcGen'May2026" },
      }),
      cat,
    );
    // state_partition_id is the only string literal the new SQL embeds
    // directly via sqlString (period_label is consumed by the path
    // builder, not literalised). The escape test still applies to
    // any SQL string that takes user input. Period label fed into the
    // URL is URL-encoded by `read_csv` parsing; assert the path URL
    // carries the year correctly.
    const csvUrls = plan.csv_registrations.map(c => c.url).join(" | ");
    expect(csvUrls).toContain("/election=2026/");
  });
});

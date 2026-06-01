// Compiler tests — pure function over a SemanticCatalogue.
//
// Per plan-doc §17 D-05 the compiler has no I/O. These tests assert that:
//   - each of the 4 concept_ids produces a well-formed DuckDBPlan
//   - the plan carries provenance_sql (always)
//   - the plan carries concept_id (always)
//   - catalogue mismatches throw with helpful messages
//   - required_filter violations throw

import { describe, expect, it } from "vitest";
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
  it("compiles party_totals to a plan with the expected shape", () => {
    const plan = compileIntent(intent({}), CATALOGUE);
    expect(plan.concept_id).toBe("party_totals");
    expect(plan.slice_registrations[0]!.table_id).toBe("elections.election_results");
    expect(plan.slice_registrations[0]!.partition_filter).toEqual({ state: "tamil-nadu" });
    expect(plan.table_registrations.map(t => t.table_id)).toContain("taxonomy.sources");
    expect(plan.main_sql).toMatch(/FROM election_results/);
    expect(plan.main_sql).toMatch(/PARTY-/);
    expect(plan.provenance_sql).toMatch(/JOIN sources s ON s\.source_id = o\.source_id/);
    expect(plan.view_hints.column_order).toEqual([
      "party_short",
      "seats_won",
      "votes",
      "vote_share_pct",
    ]);
  });

  it("compiles closest_contests to use ac-margin-pp", () => {
    const plan = compileIntent(
      intent({ concept_id: "closest_contests" }),
      CATALOGUE,
    );
    expect(plan.main_sql).toMatch(/ac-margin-pp/);
    expect(plan.table_registrations.map(t => t.table_id)).toContain("elections.dim_acs");
    expect(plan.view_hints.column_order).toEqual([
      "ac_no",
      "ac_name",
      "margin_pp",
      "votes_polled",
    ]);
  });

  it("compiles constituency_result with the per-AC join chain", () => {
    const plan = compileIntent(
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
    expect(plan.main_sql).toMatch(/elections_candidacies/);
    expect(plan.main_sql).toMatch(/dim_persons/);
    expect(plan.main_sql).toMatch(/dim_parties/);
    expect(plan.main_sql).toMatch(/da\.eci_no = 167/);
    expect(plan.view_hints.column_order).toEqual([
      "rank",
      "candidate_name",
      "party_short",
      "votes",
      "vote_share_pct",
    ]);
  });

  it("compiles turnout_extremes with a highest/lowest UNION", () => {
    const plan = compileIntent(
      intent({ concept_id: "turnout_extremes" }),
      CATALOGUE,
    );
    expect(plan.main_sql).toMatch(/UNION ALL/);
    expect(plan.main_sql).toMatch(/ac-turnout-pct/);
    expect(plan.view_hints.column_order).toEqual([
      "band",
      "ac_no",
      "ac_name",
      "turnout_pct",
    ]);
  });

  it("EVERY concept produces a non-empty provenance_sql", () => {
    for (const concept_id of [
      "party_totals",
      "closest_contests",
      "constituency_result",
      "turnout_extremes",
    ] as const) {
      const plan = compileIntent(
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
    }
  });

  it("throws when filters.state_partition_id is unknown", () => {
    expect(() =>
      compileIntent(
        intent({
          filters: { state_partition_id: "nonexistent-fake-state", period_label: "AcGenMay2026" },
        }),
        CATALOGUE,
      ),
    ).toThrow(/state_partition_id/);
  });

  it("throws when filters.period_label is unknown", () => {
    expect(() =>
      compileIntent(
        intent({
          filters: { state_partition_id: "tamil-nadu", period_label: "Unknown1990" },
        }),
        CATALOGUE,
      ),
    ).toThrow(/period_label/);
  });

  it("throws when filters.party_short_code is unknown", () => {
    expect(() =>
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
    ).toThrow(/party_short_code/);
  });

  it("throws when constituency_result is missing ac_no", () => {
    expect(() =>
      compileIntent(
        intent({ concept_id: "constituency_result" }),
        CATALOGUE,
      ),
    ).toThrow(/ac_no/);
  });

  it("escapes single-quotes in period_label to prevent injection", () => {
    // Catalogue contains the period label exactly as-is, but the SQL
    // must still escape the quote in the literal. Add the dangerous
    // label to the catalogue so the compiler accepts it.
    const cat: SemanticCatalogue = {
      ...CATALOGUE,
      election_periods: [
        ...CATALOGUE.election_periods,
        {
          period_label: "AcGenMay'2026",
          display_name: "AcGenMay'2026",
          state_partition_id: "tamil-nadu",
        },
      ],
    };
    const plan = compileIntent(
      intent({
        filters: { state_partition_id: "tamil-nadu", period_label: "AcGenMay'2026" },
      }),
      cat,
    );
    // The single-quote in the literal must be doubled (SQL-standard escape).
    expect(plan.main_sql).toContain("'AcGenMay''2026'");
  });
});

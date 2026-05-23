// Vitest contract — Phase 3.6 (b) experiment definition + R-28 manifest
// discipline.
//
// Two contracts:
//
//   1. `experiment-definition.json` is well-formed (id + key shape,
//      variations, weights, hash_attribute, rollback contract).
//
//   2. The adapter uses `registerSlice("elections.election_results", ...)`
//      + `registerTable("elections.dim_parties")` rather than any
//      hardcoded parquet path literal. Per plan line 1346: "Contract
//      test: the Phase 3.6 elections adapter resolves its Parquet
//      path through `manifest.tables[<table_id>].relative_path` and
//      not via a hardcoded literal."

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import experiment from "./experiment-definition.json";

describe("experiment-definition.json — Phase 3.6 (b)", () => {
  it("ships a stable experiment_id + feature_key", () => {
    expect(experiment.experiment_id).toBe(
      "chart-composition-bar-election-seats",
    );
    expect(experiment.feature_key).toBe(
      "chart.composition-bar.election-seats.enabled",
    );
  });

  it("declares two variations with weights summing to 1.0", () => {
    expect(experiment.variations).toHaveLength(2);
    const weights = experiment.variations.map(v => v.weight);
    const sum = weights.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1.0, 6);
  });

  it("control variation is the existing SeatDonut-only behaviour", () => {
    const control = experiment.variations.find(v => v.id === "control");
    expect(control).toBeDefined();
    expect(control!.key).toBe("0");
    expect(control!.name).toMatch(/SeatDonut only/i);
  });

  it("treatment variation mounts CompositionBar alongside SeatDonut", () => {
    const treatment = experiment.variations.find(v => v.id === "treatment");
    expect(treatment).toBeDefined();
    expect(treatment!.key).toBe("1");
    expect(treatment!.name).toMatch(/CompositionBar/);
  });

  it("uses cookie stickiness on a visitor_id hash attribute", () => {
    expect(experiment.stickiness).toBe("cookie");
    expect(experiment.hash_attribute).toBe("visitor_id");
  });

  it("targets only single-party-dominant states per R-02", () => {
    const rule = experiment.targeting.rules.find(
      r => r.id === "single-party-dominant-states",
    );
    expect(rule).toBeDefined();
    const states: string[] = rule!.condition.state_code.$in;
    expect(states).toContain("S05"); // Gujarat
    // S22 (Tamil Nadu) MUST NOT be in the rollout list per R-02
    // ("TN's verdict is alliance-led; a party-only chart misframes it").
    expect(states).not.toContain("S22");
  });

  it("documents a single-file rollback contract", () => {
    expect(experiment.rollback_contract.files_touched_by_mount).toContain(
      "frontend/src/routes/StateOverview.svelte",
    );
    expect(experiment.rollback_contract.description).toMatch(/revert/i);
  });

  it("ties the experiment to R-08 / R-16 / R-24 / R-28", () => {
    const ties = experiment.doctrine_ties.join(" | ");
    expect(ties).toMatch(/R-08/);
    expect(ties).toMatch(/R-16/);
    expect(ties).toMatch(/R-24/);
    expect(ties).toMatch(/R-28/);
  });
});

describe("R-28 manifest discipline — adapter uses manifest registration", () => {
  const adapterPath = resolve(
    __dirname,
    "adapter-elections-seats.ts",
  );
  const src = readFileSync(adapterPath, "utf-8");

  it("calls registerSlice for elections.election_results", () => {
    expect(src).toMatch(/registerSlice\("elections\.election_results"/);
  });

  it("calls registerTable for elections.dim_parties", () => {
    expect(src).toMatch(/registerTable\("elections\.dim_parties"\)/);
  });

  it("calls registerTable for taxonomy.sources", () => {
    expect(src).toMatch(/registerTable\("taxonomy\.sources"\)/);
  });

  it("does not embed a hardcoded /data/elections/ parquet path literal", () => {
    // Anything matching `"/data/elections/...parquet"` or
    // `'/data/elections/...parquet'` is the R-28 violation we are
    // guarding against. The adapter MUST go through registerTable so
    // the manifest is the single source of truth for parquet paths.
    expect(src).not.toMatch(/['"]\/data\/elections\/[^'"]*\.parquet['"]/);
  });

  it("does not embed a hardcoded relative election parquet literal", () => {
    // `"elections/.../election_results.parquet"` would also bypass
    // the manifest — guard against that too.
    expect(src).not.toMatch(
      /['"]elections\/[^'"]*election_results\.parquet['"]/,
    );
  });
});

describe("R-28 manifest registration — table_ids exist", () => {
  // Independent of the adapter source: assert the table_ids the
  // adapter registers actually exist in `datasets/manifest.json`.
  // If a curator removes one, this test fails before production does.
  const manifestPath = resolve(
    __dirname,
    "..",
    "..",
    "..",
    "..",
    "..",
    "datasets",
    "manifest.json",
  );
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const ids: string[] = manifest.tables.map((t: { table_id: string }) => t.table_id);

  it("manifest registers elections.election_results", () => {
    expect(ids).toContain("elections.election_results");
  });

  it("manifest registers elections.dim_parties", () => {
    expect(ids).toContain("elections.dim_parties");
  });

  it("manifest registers taxonomy.sources", () => {
    expect(ids).toContain("taxonomy.sources");
  });
});

// Unit tests for the per-(state, year) election CSV path builder (F1.3a).
//
// Pins (a) the ECI event-id -> 4-digit year parser, (b) the ECI->LGD slug
// translation seam, (c) the on-disk shape every view-model reads from
// after the F1.3a flip (assembly per-(state,year), parliament per-year).

import { describe, expect, it } from "vitest";

import {
  ASSEMBLY_CANDIDACIES_GLOB,
  ASSEMBLY_SUMMARY_GLOB,
  ENTITIES_ELECTORAL_GLOB,
  PARLIAMENT_CANDIDACIES_GLOB,
  PARLIAMENT_SUMMARY_GLOB,
  assemblyCandidaciesPath,
  assemblySummaryPath,
  electoralEntitiesPath,
  eventYear,
  parliamentCandidaciesPath,
  parliamentSummaryPath,
} from "./election-csv-paths";
import { fileClassForCsvPath } from "./csv-columns";

describe("eventYear", () => {
  it("extracts the trailing 4-digit year from an assembly event id", () => {
    expect(eventYear("AcGenApr2021")).toBe(2021);
    expect(eventYear("AcGenFeb2017")).toBe(2017);
    expect(eventYear("AcGenMay2026")).toBe(2026);
  });

  it("extracts the trailing 4-digit year from a Parliament event id", () => {
    expect(eventYear("LsGenJun2024")).toBe(2024);
    expect(eventYear("LsGenApr2019")).toBe(2019);
  });

  it("throws on an event id with no 4-digit suffix", () => {
    expect(() => eventYear("AcGenApr21")).toThrow(/no 4-digit year suffix/);
    expect(() => eventYear("not-an-event")).toThrow(/no 4-digit year suffix/);
  });
});

describe("assembly path builders", () => {
  it("builds the per-(state, year) candidacies path with the LGD slug", () => {
    // S22 -> "tamil-nadu" via electionStatePartition.
    expect(assemblyCandidaciesPath("S22", "AcGenApr2021")).toBe(
      "datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
  });

  it("builds the per-(state, year) summary path with the LGD slug", () => {
    expect(assemblySummaryPath("S22", "AcGenApr2021")).toBe(
      "datasets/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );
  });

  it("falls back to the lowercased ECI code when no slug map hit", () => {
    // U99 is a synthetic fixture state code not in ECI_TO_LGD_SLUG.
    expect(assemblyCandidaciesPath("U99", "AcGenJan2020")).toBe(
      "datasets/elections/assembly/state=u99/election=2020/candidacies.csv",
    );
  });
});

describe("parliament path builders", () => {
  it("builds the per-year candidacies path (no state shard)", () => {
    expect(parliamentCandidaciesPath("LsGenJun2024")).toBe(
      "datasets/elections/parliament/election=2024/candidacies.csv",
    );
  });

  it("builds the per-year summary path (no state shard)", () => {
    expect(parliamentSummaryPath("LsGenApr2019")).toBe(
      "datasets/elections/parliament/election=2019/summary.csv",
    );
  });
});

describe("electoralEntitiesPath", () => {
  it("returns the single canonical AC+PC entity table path", () => {
    expect(electoralEntitiesPath()).toBe("datasets/data/entities/electoral.csv");
  });
});

describe("globs match columns.json file_class keys", () => {
  // Every globally exported glob constant must round-trip through
  // `fileClassForCsvPath` so callers can pair the path builder with
  // `csvColumnsClause` without restating the partition pattern.
  it("ASSEMBLY_CANDIDACIES_GLOB matches its file_class shape", () => {
    expect(
      fileClassForCsvPath(assemblyCandidaciesPath("S22", "AcGenApr2021")),
    ).toBe(ASSEMBLY_CANDIDACIES_GLOB);
  });

  it("ASSEMBLY_SUMMARY_GLOB matches its file_class shape", () => {
    expect(
      fileClassForCsvPath(assemblySummaryPath("S22", "AcGenApr2021")),
    ).toBe(ASSEMBLY_SUMMARY_GLOB);
  });

  it("PARLIAMENT_CANDIDACIES_GLOB matches its file_class shape", () => {
    expect(
      fileClassForCsvPath(parliamentCandidaciesPath("LsGenJun2024")),
    ).toBe(PARLIAMENT_CANDIDACIES_GLOB);
  });

  it("PARLIAMENT_SUMMARY_GLOB matches its file_class shape", () => {
    expect(
      fileClassForCsvPath(parliamentSummaryPath("LsGenJun2024")),
    ).toBe(PARLIAMENT_SUMMARY_GLOB);
  });

  it("ENTITIES_ELECTORAL_GLOB matches its file_class shape", () => {
    expect(fileClassForCsvPath(electoralEntitiesPath())).toBe(
      ENTITIES_ELECTORAL_GLOB,
    );
  });
});

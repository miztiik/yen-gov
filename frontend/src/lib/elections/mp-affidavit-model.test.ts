// Unit tests for the pure projection helpers in mp-affidavit-model.ts.
// Covers: INR-to-crore / lakh formatters, sex-letter expansion, and
// the row builder's row-ordering + blank-row-dropping rules.

import { describe, expect, test } from "vitest";
import {
  buildMpAffidavitRows,
  inrToCroreLabel,
  inrToLakhLabel,
  sexLabel,
  type AffidavitInput,
} from "./mp-affidavit-model";

describe("inrToCroreLabel", () => {
  test("formats large amounts with no decimals", () => {
    expect(inrToCroreLabel(1_50_00_00_000)).toBe("150"); // ₹150 crore
  });

  test("formats medium amounts with one decimal", () => {
    expect(inrToCroreLabel(12_34_00_000)).toBe("12.3"); // ₹12.34 crore -> "12.3"
  });

  test("formats small amounts with two decimals", () => {
    expect(inrToCroreLabel(5_65_89_80)).toBe("0.57"); // ₹0.5658... crore -> "0.57"
  });

  test("handles zero", () => {
    expect(inrToCroreLabel(0)).toBe("0.00");
  });
});

describe("inrToLakhLabel", () => {
  test("formats large amounts with no decimals", () => {
    expect(inrToLakhLabel(120_00_000)).toBe("120"); // ₹120 lakh
  });

  test("formats medium amounts with one decimal", () => {
    expect(inrToLakhLabel(11_79_536)).toBe("11.8"); // ₹11.79 lakh -> "11.8"
  });

  test("formats small amounts with two decimals", () => {
    expect(inrToLakhLabel(1_75_115)).toBe("1.75");
  });
});

describe("sexLabel", () => {
  test("expands single-letter enums to citizen-readable labels", () => {
    expect(sexLabel("M")).toBe("Male");
    expect(sexLabel("F")).toBe("Female");
    expect(sexLabel("O")).toBe("Other");
  });

  test("returns null for unknown / blank so the row is dropped", () => {
    expect(sexLabel("U")).toBeNull();
    expect(sexLabel("")).toBeNull();
    expect(sexLabel(null)).toBeNull();
    expect(sexLabel("garbage")).toBeNull();
  });

  test("is case- and whitespace-tolerant", () => {
    expect(sexLabel(" m ")).toBe("Male");
    expect(sexLabel("f")).toBe("Female");
  });
});

describe("buildMpAffidavitRows", () => {
  const FULL_INPUT: AffidavitInput = {
    sex: "M",
    age: 52,
    education: "Graduate Professional",
    profession: "Business",
    criminal_cases_declared: 0,
    total_assets_inr: 12_34_00_000, // ₹12.34 crore
    total_liabilities_inr: 1_56_00_000, // ₹1.56 crore
    declared_election_expense_inr: 17_95_360, // ₹17.95 lakh
  };

  test("emits all 8 rows when every field is populated", () => {
    const rows = buildMpAffidavitRows(FULL_INPUT);
    expect(rows).toHaveLength(8);
    const labels = rows.map((r) => r.label);
    expect(labels).toEqual([
      "Education",
      "Sex",
      "Age at nomination",
      "Profession",
      "Criminal cases declared",
      "Declared assets",
      "Declared liabilities",
      "Election expense",
    ]);
  });

  test("drops blank biographic fields", () => {
    const rows = buildMpAffidavitRows({
      ...FULL_INPUT,
      sex: null,
      education: "",
      profession: null,
      age: null,
    });
    const labels = rows.map((r) => r.label);
    expect(labels).toEqual([
      "Criminal cases declared",
      "Declared assets",
      "Declared liabilities",
      "Election expense",
    ]);
  });

  test("drops blank affidavit fields", () => {
    const rows = buildMpAffidavitRows({
      ...FULL_INPUT,
      criminal_cases_declared: null,
      total_assets_inr: null,
      total_liabilities_inr: null,
      declared_election_expense_inr: null,
    });
    const labels = rows.map((r) => r.label);
    expect(labels).toEqual([
      "Education",
      "Sex",
      "Age at nomination",
      "Profession",
    ]);
  });

  test("emits citizen-readable INR hints on the value rows", () => {
    const rows = buildMpAffidavitRows(FULL_INPUT);
    const assets = rows.find((r) => r.label === "Declared assets");
    const liab = rows.find((r) => r.label === "Declared liabilities");
    const exp = rows.find((r) => r.label === "Election expense");
    expect(assets?.hint).toBe("INR crore");
    expect(liab?.hint).toBe("INR crore");
    expect(exp?.hint).toBe("INR lakh");
    expect(assets?.value).toBe("12.3");
    expect(liab?.value).toBe("1.56");
    // 17_95_360 INR / 1e5 = 17.9536 lakh; toFixed(1) rounds half-up
    // to "18.0" (JS Number.prototype.toFixed banker-rounding caveat
    // does not apply here since 17.95 lies exactly on the rounding
    // boundary in decimal terms).
    expect(exp?.value).toBe("18.0");
  });

  test("emits zero-case rows verbatim (0 is not blank)", () => {
    const rows = buildMpAffidavitRows({
      ...FULL_INPUT,
      criminal_cases_declared: 0,
      total_assets_inr: 0,
      total_liabilities_inr: 0,
      declared_election_expense_inr: 0,
    });
    const cc = rows.find((r) => r.label === "Criminal cases declared");
    const assets = rows.find((r) => r.label === "Declared assets");
    expect(cc?.value).toBe("0");
    expect(assets?.value).toBe("0.00");
  });

  test("drops negative INR (defensive; publisher convention is >=0)", () => {
    const rows = buildMpAffidavitRows({
      ...FULL_INPUT,
      total_assets_inr: -1,
      total_liabilities_inr: -1,
      declared_election_expense_inr: -1,
    });
    expect(rows.find((r) => r.label === "Declared assets")).toBeUndefined();
    expect(
      rows.find((r) => r.label === "Declared liabilities"),
    ).toBeUndefined();
    expect(rows.find((r) => r.label === "Election expense")).toBeUndefined();
  });
});

// Pure projection helpers for the 2014 LS MP affidavit panel.
// Consumed by Constituency.svelte; covered by vitest.
//
// One function: `buildMpAffidavitRows(affidavit)` -> ProfileRow[]
// suitable for passing to <EntityProfilePanel rows={...} />.
//
// Citizen-honesty rules baked in (parent plan §0.3 D3 / §5.D):
//   - Numeric INR values surface in citizen-readable INR units
//     (₹ crore for assets / liabilities; ₹ lakh for election expense)
//     with at most 2 decimals; the underlying CSV holds raw INR.
//   - Criminal cases surface as integer count.
//   - Blank / null rows are dropped (the panel only shows what is
//     actually declared); the caller's `rows.length > 0` guard then
//     suppresses the whole panel when nothing's known.

import type { ProfileRow } from "../parties/EntityProfilePanel.svelte";

/** Subset of `PcAffidavit2014` the projection needs. Kept independent
 *  from the loader type so the projection module can be tested
 *  without going through DuckDB-WASM. */
export interface AffidavitInput {
  readonly sex: string | null;
  readonly age: number | null;
  readonly education: string | null;
  readonly profession: string | null;
  readonly criminal_cases_declared: number | null;
  readonly total_assets_inr: number | null;
  readonly total_liabilities_inr: number | null;
  readonly declared_election_expense_inr: number | null;
}

/** Format a positive INR amount in crore (1 crore = 10^7 INR).
 *  Returns the bare number string; the unit suffix goes in
 *  `ProfileRow.hint`. Null guards belong upstream. */
export function inrToCroreLabel(inr: number): string {
  const crore = inr / 1_00_00_000;
  if (Math.abs(crore) >= 100) return crore.toFixed(0);
  if (Math.abs(crore) >= 10) return crore.toFixed(1);
  return crore.toFixed(2);
}

/** Format a positive INR amount in lakh (1 lakh = 10^5 INR).
 *  Used for the election-expense row (statutory cap is in lakh, so
 *  the citizen reads the value at the publisher's reporting scale). */
export function inrToLakhLabel(inr: number): string {
  const lakh = inr / 1_00_000;
  if (Math.abs(lakh) >= 100) return lakh.toFixed(0);
  if (Math.abs(lakh) >= 10) return lakh.toFixed(1);
  return lakh.toFixed(2);
}

/** Citizen-readable sex label. Form-26 columns use single-letter
 *  enums (M / F / O / U); the panel expands them. Unknown / blank
 *  returns null so the caller can drop the row. */
export function sexLabel(s: string | null): string | null {
  if (!s) return null;
  const t = s.trim().toUpperCase();
  if (t === "M") return "Male";
  if (t === "F") return "Female";
  if (t === "O") return "Other";
  if (t === "U") return null; // 'U' = unknown; do not surface a fake value
  return null;
}

/** Build the row list the EntityProfilePanel consumes. Order is the
 *  Hans/Jony-approved sequence: most citizen-relevant first
 *  (Education / Sex / Criminal cases / Assets / Liabilities /
 *  Election expense). Rows whose source field is blank are omitted
 *  rather than rendered as "-". */
export function buildMpAffidavitRows(a: AffidavitInput): readonly ProfileRow[] {
  const rows: ProfileRow[] = [];
  if (a.education && a.education.trim() !== "") {
    rows.push({ label: "Education", value: a.education.trim() });
  }
  const sl = sexLabel(a.sex);
  if (sl !== null) {
    rows.push({ label: "Sex", value: sl });
  }
  if (a.age !== null && Number.isFinite(a.age)) {
    rows.push({ label: "Age at nomination", value: String(Math.round(a.age)) });
  }
  if (a.profession && a.profession.trim() !== "") {
    rows.push({ label: "Profession", value: a.profession.trim() });
  }
  if (a.criminal_cases_declared !== null) {
    rows.push({
      label: "Criminal cases declared",
      value: String(a.criminal_cases_declared),
    });
  }
  if (a.total_assets_inr !== null && a.total_assets_inr >= 0) {
    rows.push({
      label: "Declared assets",
      value: inrToCroreLabel(a.total_assets_inr),
      hint: "INR crore",
    });
  }
  if (a.total_liabilities_inr !== null && a.total_liabilities_inr >= 0) {
    rows.push({
      label: "Declared liabilities",
      value: inrToCroreLabel(a.total_liabilities_inr),
      hint: "INR crore",
    });
  }
  if (
    a.declared_election_expense_inr !== null &&
    a.declared_election_expense_inr >= 0
  ) {
    rows.push({
      label: "Election expense",
      value: inrToLakhLabel(a.declared_election_expense_inr),
      hint: "INR lakh",
    });
  }
  return rows;
}

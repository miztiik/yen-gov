// SourceList v2 — vitest for pure formatters.
//
// Per Phase 1.4 of TODO/20260518-frontend-charting-modernisation-plan.md:
//   "Unit tests for source summary formatting: producer/authority/vintage
//    fallback, host fallback, empty hand-authored source case."
//
// Tests are pure helper coverage only; the contract test that the v2.0
// schema on disk matches these types lives at
// `frontend/src/contracts/sources-v2-shape.test.ts`.

import { describe, it, expect } from "vitest";
import {
  composeDefaultCitation,
  formatCollapsedSummary,
  formatExpandedDisclosure,
  verificationMethodRank,
} from "./format";
import type { SourceV2Row } from "./types";

// A fully-populated gold-tier example mirroring an ECI Statistical Report row.
const ECI_FULL: SourceV2Row = Object.freeze({
  source_id: "src-abc123def456",
  producer: "Election Commission of India",
  title: "Statistical Report Section 10 (Detailed Results) — Tamil Nadu",
  vintage: "AcGenApr2021",
  license: "OGL-IN-1.0",
  confidence_tier: "gold",
  is_issuing_authority: true,
  verification_method: "archived-snapshot",
  url_main: "https://eci.gov.in/statistical-reports",
  citation_full: null,
  notes: "XLSX layout stable since AcGenMay2016.",
});

// A republished/silver-tier example (e.g. PRS reading an ECI number).
const REPUBLISHED: SourceV2Row = Object.freeze({
  source_id: "src-fedcba654321",
  producer: "PRS Legislative Research",
  title: "State of State Finances 2024-25",
  vintage: "FY 2024-25",
  license: "CC-BY-4.0",
  confidence_tier: "silver",
  is_issuing_authority: false,
  verification_method: "live-fetch",
  url_main: "https://prsindia.org/policy/budgets",
  citation_full: null,
  notes: null,
});

// Hand-authored / internal — license=internal, vintage may be empty,
// url_main null. Tests the "empty hand-authored source case" called out
// in the plan.
const HAND_AUTHORED: SourceV2Row = Object.freeze({
  source_id: "src-000000000abc",
  producer: "yen-gov",
  title: "Editorial — state-tier classification rationale",
  vintage: "",
  license: "internal",
  confidence_tier: "bronze",
  is_issuing_authority: false,
  verification_method: "editorial",
  url_main: null,
  citation_full: null,
  notes: null,
});

// Override-style — adapter provided citation_full verbatim.
const OVERRIDDEN: SourceV2Row = Object.freeze({
  source_id: "src-111111111111",
  producer: "Reserve Bank of India",
  title: "Handbook of Statistics on Indian States",
  vintage: "2024-25",
  license: "OGL-IN-1.0",
  confidence_tier: "gold",
  is_issuing_authority: true,
  verification_method: "live-fetch",
  url_main: "https://rbi.org.in/Scripts/AnnualPublications.aspx",
  citation_full: "RBI Handbook of Statistics on Indian States, 2024-25 Edition (Table 161-A).",
  notes: null,
});

describe("formatCollapsedSummary — citizen-facing trust line", () => {
  it("issuing authority renders as 'official series'", () => {
    const out = formatCollapsedSummary(ECI_FULL);
    expect(out.authority_label).toBe("official series");
    expect(out.display).toBe(
      "Election Commission of India · official series · AcGenApr2021",
    );
  });

  it("republisher renders as 'republished'", () => {
    const out = formatCollapsedSummary(REPUBLISHED);
    expect(out.authority_label).toBe("republished");
    expect(out.display).toBe(
      "PRS Legislative Research · republished · FY 2024-25",
    );
  });

  it("empty vintage is dropped from display but exposed as null on the structured field", () => {
    const out = formatCollapsedSummary(HAND_AUTHORED);
    expect(out.vintage).toBeNull();
    expect(out.display).toBe("yen-gov · republished");
  });

  it("vintage whitespace is trimmed", () => {
    const row: SourceV2Row = { ...ECI_FULL, vintage: "  AcGenApr2021  " };
    const out = formatCollapsedSummary(row);
    expect(out.vintage).toBe("AcGenApr2021");
    expect(out.display).toBe(
      "Election Commission of India · official series · AcGenApr2021",
    );
  });

  it("producer is preserved verbatim (not normalised)", () => {
    const out = formatCollapsedSummary({
      ...ECI_FULL,
      producer: "Ministry of Statistics and Programme Implementation",
    });
    expect(out.producer).toBe("Ministry of Statistics and Programme Implementation");
  });
});

describe("composeDefaultCitation — fallback when citation_full is null", () => {
  it("mirrors backend render_citation with vintage", () => {
    expect(composeDefaultCitation(ECI_FULL)).toBe(
      "Election Commission of India, Statistical Report Section 10 (Detailed Results) — Tamil Nadu (AcGenApr2021)",
    );
  });

  it("omits vintage parenthetical when vintage is empty", () => {
    expect(composeDefaultCitation(HAND_AUTHORED)).toBe(
      "yen-gov, Editorial — state-tier classification rationale",
    );
  });

  it("trims whitespace-only vintage to empty", () => {
    expect(
      composeDefaultCitation({ ...ECI_FULL, vintage: "   " }),
    ).toBe(
      "Election Commission of India, Statistical Report Section 10 (Detailed Results) — Tamil Nadu",
    );
  });
});

describe("formatExpandedDisclosure — sources v2.0 ledger fields only", () => {
  it("uses citation_full verbatim when present", () => {
    const out = formatExpandedDisclosure(OVERRIDDEN);
    expect(out.citation).toBe(
      "RBI Handbook of Statistics on Indian States, 2024-25 Edition (Table 161-A).",
    );
  });

  it("falls back to composeDefaultCitation when citation_full is null", () => {
    const out = formatExpandedDisclosure(ECI_FULL);
    expect(out.citation).toBe(
      "Election Commission of India, Statistical Report Section 10 (Detailed Results) — Tamil Nadu (AcGenApr2021)",
    );
  });

  it("propagates the v2 ledger columns verbatim", () => {
    const out = formatExpandedDisclosure(REPUBLISHED);
    expect(out.source_id).toBe("src-fedcba654321");
    expect(out.license).toBe("CC-BY-4.0");
    expect(out.confidence_tier).toBe("silver");
    expect(out.is_issuing_authority).toBe(false);
    expect(out.verification_method).toBe("live-fetch");
    expect(out.url_main).toBe("https://prsindia.org/policy/budgets");
    expect(out.notes).toBeNull();
  });

  it("never surfaces fetch-telemetry fields (R-24 structural guarantee)", () => {
    // This is a type-level guarantee — the test is here to document intent
    // and fail loud if a future refactor sneaks one back.
    const out = formatExpandedDisclosure(HAND_AUTHORED) as Record<string, unknown>;
    expect(out).not.toHaveProperty("fetched_at");
    expect(out).not.toHaveProperty("first_fetched_at");
    expect(out).not.toHaveProperty("last_seen_at");
    expect(out).not.toHaveProperty("date_accessed");
    expect(out).not.toHaveProperty("content_hash");
    expect(out).not.toHaveProperty("url");
  });

  it("renders editorial hand-authored citation cleanly", () => {
    const out = formatExpandedDisclosure(HAND_AUTHORED);
    expect(out.citation).toBe(
      "yen-gov, Editorial — state-tier classification rationale",
    );
    expect(out.url_main).toBeNull();
    expect(out.verification_method).toBe("editorial");
    expect(out.license).toBe("internal");
  });
});

describe("verificationMethodRank — trust ordering for surfacing", () => {
  it("live-fetch is most trusted (rank 0)", () => {
    expect(verificationMethodRank("live-fetch")).toBe(0);
  });

  it("editorial is least trusted (rank 3)", () => {
    expect(verificationMethodRank("editorial")).toBe(3);
  });

  it("ordering is strict and matches backend verification_method_rank", () => {
    expect(verificationMethodRank("live-fetch")).toBeLessThan(
      verificationMethodRank("archived-snapshot"),
    );
    expect(verificationMethodRank("archived-snapshot")).toBeLessThan(
      verificationMethodRank("transcribed"),
    );
    expect(verificationMethodRank("transcribed")).toBeLessThan(
      verificationMethodRank("editorial"),
    );
  });
});

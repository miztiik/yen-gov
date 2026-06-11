// AnswerViewModel boundary tests.
//
// Per plan-doc §17 D-06: source_strip MUST be non-empty (Zod-enforced).
// The empty case is unreachable under correct executor behaviour; this
// suite is the gate that proves an executor regression cannot ship a
// sourceless answer to the renderer.
//
// Post sources-simplification PR-1 (2026-06-11): source_strip is
// PublisherPill[] (4-col: label / vintage_summary / url / count) -
// not the prior 11-col row shape.

import { describe, expect, it } from "vitest";
import {
  parseAnswerViewModel,
  safeParseAnswerViewModel,
  AnswerViewModelSchema,
  type AnswerViewModel,
} from "./answer-viewmodel";
import { synthesiseUnattestedPill } from "../types";

const VALID_SOURCE = {
  label: "ECI Constituency-wise result (May 2026)",
  vintage_summary: "May 2026",
  url: "https://results.eci.gov.in/AcGenMay2026/",
  count: 1,
};

const VALID_VM: AnswerViewModel = {
  question: "What were the May 2026 Tamil Nadu party totals?",
  rows: [
    { party_short: "DMK", seats_won: 133, votes: 18_345_678, vote_share_pct: 38.74 },
  ],
  column_order: ["party_short", "seats_won", "votes", "vote_share_pct"],
  column_labels: {
    party_short: "Party",
    seats_won: "Seats won",
    votes: "Votes",
    vote_share_pct: "Vote share",
  },
  column_formats: {
    party_short: "text",
    seats_won: "integer",
    votes: "thousands",
    vote_share_pct: "percentage",
  },
  source_strip: [VALID_SOURCE],
  provenance_status: "joined",
  computation: {
    concept_id: "party_totals",
    slice_registrations: [
      {
        table_id: "elections.election_results",
        partition_filter: { state: "tamil-nadu" },
      },
    ],
    main_sql: "SELECT 1",
    provenance_sql: "SELECT 1",
  },
};

describe("AnswerViewModel v0", () => {
  it("accepts a well-formed joined-provenance view-model", () => {
    expect(parseAnswerViewModel(VALID_VM).provenance_status).toBe("joined");
  });

  it("accepts the synthesised unattested pill", () => {
    const vm: AnswerViewModel = {
      ...VALID_VM,
      source_strip: [synthesiseUnattestedPill()],
      provenance_status: "missing",
    };
    const parsed = parseAnswerViewModel(vm);
    expect(parsed.source_strip[0]!.label).toBe("Source unattested");
    expect(parsed.provenance_status).toBe("missing");
  });

  it("REJECTS empty source_strip (D-06 gate)", () => {
    const r = safeParseAnswerViewModel({ ...VALID_VM, source_strip: [] });
    expect(r.success).toBe(false);
  });

  it("REJECTS missing source_strip entirely", () => {
    const broken = { ...VALID_VM } as Partial<AnswerViewModel>;
    delete broken.source_strip;
    const r = safeParseAnswerViewModel(broken);
    expect(r.success).toBe(false);
  });

  it("REJECTS provenance_status outside the enum", () => {
    const r = safeParseAnswerViewModel({
      ...VALID_VM,
      provenance_status: "stale",
    });
    expect(r.success).toBe(false);
  });

  it("REJECTS empty column_order", () => {
    const r = safeParseAnswerViewModel({ ...VALID_VM, column_order: [] });
    expect(r.success).toBe(false);
  });

  it("accepts rows = []", () => {
    expect(parseAnswerViewModel({ ...VALID_VM, rows: [] }).rows).toEqual([]);
  });

  it("REJECTS cell values that are objects (Arrow Vector smuggling)", () => {
    const r = safeParseAnswerViewModel({
      ...VALID_VM,
      rows: [{ ...VALID_VM.rows[0], smuggled: { hidden: true } }],
    });
    expect(r.success).toBe(false);
  });

  it("REJECTS column_formats with an unknown format", () => {
    const r = safeParseAnswerViewModel({
      ...VALID_VM,
      column_formats: { ...VALID_VM.column_formats, party_short: "scientific" },
    });
    expect(r.success).toBe(false);
  });

  it("REJECTS computation block missing main_sql", () => {
    const broken = {
      ...VALID_VM,
      computation: {
        ...VALID_VM.computation,
        main_sql: undefined,
      },
    };
    const r = safeParseAnswerViewModel(broken);
    expect(r.success).toBe(false);
  });

  it("REJECTS pill missing required label field", () => {
    const r = safeParseAnswerViewModel({
      ...VALID_VM,
      source_strip: [{ ...VALID_SOURCE, label: "" }],
    });
    expect(r.success).toBe(false);
  });

  it("schema export matches parser behaviour", () => {
    expect(AnswerViewModelSchema.safeParse(VALID_VM).success).toBe(true);
  });
});

// Tests for extract-intent.ts.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-17. The model adapter is mocked end-to-end: we hand-feed the raw
// strings the adapter would return and assert the parse + retry contract.

import { describe, expect, it, vi } from "vitest";
import {
  extractJsonObject,
  buildSystemPrompt,
  extractIntent,
} from "./extract-intent";
import type { SemanticCatalogue } from "./types";
import type {
  ChatMessage,
  GenerateOptions,
  ModelAdapter,
  ReadinessStatus,
} from "./model-adapter";
import type { ModelEntry } from "./model-registry";

// ----- fixtures --------------------------------------------------------------

const CATALOGUE: SemanticCatalogue = {
  tables: [],
  states: [
    { partition_id: "in_s22", eci_code: "S22", display_name: "Tamil Nadu" },
  ],
  election_periods: [
    {
      period_label: "AcGenMay2026",
      display_name: "Tamil Nadu AC General — May 2026",
      state_partition_id: "in_s22",
    },
  ],
  parties: [],
  sources: [],
  manifest: {} as never,
};

const MODEL: ModelEntry = {
  id: "test-model",
  display_name: "Test",
  params_label: "10M",
  provider: "transformers-js",
  repo_id: "test/repo",
  dtype: "q4f16",
  device: "auto",
  estimated_download_mb: 1,
  notes: "",
};

function fakeAdapter(
  responses: readonly string[],
): { adapter: ModelAdapter; calls: ChatMessage[][] } {
  const calls: ChatMessage[][] = [];
  let i = 0;
  const status: ReadinessStatus = { kind: "ready" };
  const adapter: ModelAdapter = {
    model: MODEL,
    status: () => status,
    prepare: async () => undefined,
    generate: async (messages: readonly ChatMessage[], _opts?: GenerateOptions) => {
      calls.push([...messages]);
      if (i >= responses.length) {
        throw new Error("fakeAdapter exhausted");
      }
      return responses[i++]!;
    },
  };
  return { adapter, calls };
}

// ----- extractJsonObject -----------------------------------------------------

describe("extractJsonObject", () => {
  it("parses a bare JSON object", () => {
    expect(extractJsonObject('{"a":1}')).toEqual({ a: 1 });
  });

  it("strips ```json fences", () => {
    expect(extractJsonObject('```json\n{"a":2}\n```')).toEqual({ a: 2 });
  });

  it("ignores prose before and after the object", () => {
    expect(
      extractJsonObject('Sure! Here you go: {"a":3} — hope that helps.'),
    ).toEqual({ a: 3 });
  });

  it("handles nested objects + escaped strings", () => {
    expect(
      extractJsonObject('text {"a":{"b":"he said \\"hi\\""}} done'),
    ).toEqual({ a: { b: 'he said "hi"' } });
  });

  it("throws when no { is present", () => {
    expect(() => extractJsonObject("nothing useful")).toThrow(
      /no JSON object/,
    );
  });

  it("throws on unbalanced braces", () => {
    expect(() => extractJsonObject('{"a":1')).toThrow(/unbalanced/);
  });
});

// ----- buildSystemPrompt -----------------------------------------------------

describe("buildSystemPrompt", () => {
  it("includes all four concept ids", () => {
    const p = buildSystemPrompt(CATALOGUE);
    for (const id of [
      "party_totals",
      "closest_contests",
      "constituency_result",
      "turnout_extremes",
    ]) {
      expect(p).toContain(id);
    }
  });

  it("includes the catalogue states", () => {
    const p = buildSystemPrompt(CATALOGUE);
    expect(p).toContain("in_s22");
    expect(p).toContain("Tamil Nadu");
  });

  it("includes the catalogue election periods", () => {
    const p = buildSystemPrompt(CATALOGUE);
    expect(p).toContain("AcGenMay2026");
  });
});

// ----- extractIntent ---------------------------------------------------------

describe("extractIntent", () => {
  const VALID_RAW = JSON.stringify({
    version: "insight.intent.v0",
    question: "Who won TN 2026?",
    concept_id: "party_totals",
    filters: {
      state_partition_id: "in_s22",
      period_label: "AcGenMay2026",
    },
    reasoning: "Seat totals for a state event.",
  });

  it("returns ok on a valid first attempt", async () => {
    const { adapter, calls } = fakeAdapter([VALID_RAW]);
    const r = await extractIntent("Who won TN 2026?", CATALOGUE, adapter);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.intent.concept_id).toBe("party_totals");
      expect(r.intent.filters.state_partition_id).toBe("in_s22");
      expect(r.diagnostics.attempts).toBe(1);
    }
    // 1 call = system + few-shot + user (single attempt).
    expect(calls.length).toBe(1);
  });

  it("retries once on invalid first attempt, succeeds on the second", async () => {
    const { adapter, calls } = fakeAdapter(["not json at all", VALID_RAW]);
    const r = await extractIntent("Who won TN 2026?", CATALOGUE, adapter);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.diagnostics.attempts).toBe(2);
    expect(calls.length).toBe(2);
    // The second call MUST include a "previous output failed" hint.
    const lastTurn = calls[1]!.at(-1)!;
    expect(lastTurn.role).toBe("user");
    expect(lastTurn.content).toMatch(/previous output failed/i);
  });

  it("returns failure after max_retries with last raw output in diagnostics", async () => {
    const { adapter } = fakeAdapter(["junk one", "junk two"]);
    const r = await extractIntent("Q?", CATALOGUE, adapter, { max_retries: 1 });
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.diagnostics.attempts).toBe(2);
      expect(r.diagnostics.last_raw_output).toBe("junk two");
      expect(r.error).toBeTruthy();
    }
  });

  it("returns failure when the JSON parses but fails Zod (bad concept_id)", async () => {
    const bad = JSON.stringify({
      version: "insight.intent.v0",
      question: "Q?",
      concept_id: "not_a_concept",
      filters: {},
    });
    const { adapter } = fakeAdapter([bad, bad]);
    const r = await extractIntent("Q?", CATALOGUE, adapter, { max_retries: 1 });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/concept_id/);
  });

  it("calls generate with temperature 0.1 for stable extraction", async () => {
    const generateSpy = vi.fn<
      (messages: readonly ChatMessage[], opts?: GenerateOptions) => Promise<string>
    >(async () => VALID_RAW);
    const adapter: ModelAdapter = {
      model: MODEL,
      status: () => ({ kind: "ready" }),
      prepare: async () => undefined,
      generate: generateSpy,
    };
    await extractIntent("Q?", CATALOGUE, adapter);
    expect(generateSpy).toHaveBeenCalledTimes(1);
    const opts = generateSpy.mock.calls[0]![1];
    expect(opts?.temperature).toBe(0.1);
  });
});

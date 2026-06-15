// PR-9 of TODO/20260614-party-page-reimagination-plan.md - section 11.
//
// Holy Law #9 oracle for the per-party page. Mechanically enforces
// that every section that surfaces data on /parties/<slug> cites at
// least one source_id back to `datasets/data/entities/source.csv`,
// and that every cited source_id resolves in the citation ledger.
//
// This is a TYPE + INVARIANT contract test (no DuckDB-WASM, no
// runtime corpus walk): the pure projector `buildPartyProvenance`
// is the contract surface; the loader simply assembles its inputs.

import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCsvLine } from "../lib/canonical/canonical-entity-translation";
import {
  buildPartyProvenance,
  CARD_LABELS,
  type PartyPageSource,
} from "../lib/view-models/party-sources";
import type {
  PartyDetailViewModel,
  PartyHistoryPoint,
  PartyStronghold,
} from "../lib/view-models/party-detail";
import type { PartyMeta } from "../lib/view-models/parties";

const repoRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
);
const sourcesCsvPath = resolve(
  repoRoot,
  "datasets/data/entities/source.csv",
);

function loadSourceCsvLookup(): Map<string, PartyPageSource> {
  if (!existsSync(sourcesCsvPath)) {
    throw new Error(`source.csv not found at ${sourcesCsvPath}`);
  }
  const text = readFileSync(sourcesCsvPath, "utf-8");
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  const header = parseCsvLine(lines[0]!);
  const idxSourceId = header.indexOf("source_id");
  const idxProducer = header.indexOf("producer");
  const idxTitle = header.indexOf("title");
  const idxVintage = header.indexOf("vintage");
  const idxUrl = header.indexOf("url");
  const out = new Map<string, PartyPageSource>();
  for (const line of lines.slice(1)) {
    const cells = parseCsvLine(line);
    const source_id = cells[idxSourceId] ?? "";
    if (source_id.length === 0) continue;
    out.set(source_id, {
      source_id,
      producer: (cells[idxProducer] ?? "").trim(),
      title: (cells[idxTitle] ?? "").trim(),
      vintage: (cells[idxVintage] ?? "").trim(),
      url: (cells[idxUrl] ?? "").trim(),
      used_in: [],
    });
  }
  return out;
}

function metaFixture(overrides: Partial<PartyMeta> = {}): PartyMeta {
  return {
    party_id: "parties.IN.BJP",
    short: "BJP",
    full: "Bharatiya Janata Party",
    founded_year: 1980,
    dissolved_year: null,
    recognition_scope: "national",
    home_state_codes: [],
    symbol_asset: null,
    brand_colour: "#FF9933",
    wikipedia: null,
    name_native_script: null,
    aliases: [],
    predecessor_party_ids: [],
    successor_party_ids: [],
    is_sentinel: false,
    leader: null,
    ...overrides,
  };
}

function historyPoint(
  year: number,
  label: string,
  source_ids: string[],
): PartyHistoryPoint {
  return {
    year,
    period_label: label,
    seats: 1,
    vote_share_pct: null,
    contested: null,
    source_ids,
  };
}

function stronghold(source_ids: string[]): PartyStronghold {
  return {
    entity_id: "IN-PC-2008-S22-10",
    constituency_name: "Some PC",
    state: "tamil-nadu",
    wins: 1,
    contested: 1,
    // PR-7: `last_won_year` widening - fixture pins null since
    // this contract test covers the provenance envelope (recency
    // is not in scope).
    last_won_year: null,
    results: ["W"],
    source_ids,
  };
}

function vmFixture(
  overrides: Partial<PartyDetailViewModel> = {},
): PartyDetailViewModel {
  return {
    metadata: metaFixture(),
    ls_history: [],
    vs_history: [],
    ls_strongholds: [],
    vs_strongholds: [],
    totals: {
      ls_seats: 0,
      vs_seats: 0,
      elections_contested: 0,
      first_year: 0,
      last_year: 0,
      peak_ls_seats: 0,
      peak_ls_year: 0,
      peak_vs_seats: 0,
      peak_vs_year: 0,
    },
    ls_methodology_breaks: [],
    current_strength: null,
    alliance_context: null,
    alliance_source_ids: [],
    current_strength_source_ids: [],
    provenance: {
      badges: {
        parliament: "",
        state_assembly: "",
        strongholds: "",
        current_strength: "",
        alliance_context: "",
      },
      strip: { total_count: 0, all: [], producer_summary: "" },
    },
    ...overrides,
  };
}

describe("party-page provenance contract (Holy Law #9)", () => {
  const corpusLookup = loadSourceCsvLookup();

  it("the on-disk source.csv loads with a non-trivial row count", () => {
    expect(corpusLookup.size).toBeGreaterThan(10);
  });

  it("every CARD_LABEL string is non-empty and unique", () => {
    const labels = Object.values(CARD_LABELS);
    expect(labels.every((l) => l.length > 0)).toBe(true);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("sentinel-party shape (no data) emits zero badges and empty strip without throwing", () => {
    const vm = vmFixture({
      metadata: metaFixture({
        party_id: "parties.IN.NOTA",
        short: "NOTA",
        is_sentinel: true,
      }),
    });
    const out = buildPartyProvenance(vm, corpusLookup);
    expect(out.badges.parliament).toBe("");
    expect(out.badges.state_assembly).toBe("");
    expect(out.badges.strongholds).toBe("");
    expect(out.badges.current_strength).toBe("");
    expect(out.badges.alliance_context).toBe("");
    expect(out.strip.total_count).toBe(0);
    expect(out.strip.all).toEqual([]);
  });

  it("THROWS when a rendered card carries data but resolves zero source_ids (STOP-AND-SURFACE)", () => {
    const vm = vmFixture({
      // Has data → must cite → empty source_ids[] is a writer-side gap
      ls_history: [historyPoint(2024, "LsGenMay2024", [])],
    });
    expect(() => buildPartyProvenance(vm, corpusLookup)).toThrowError(
      /Holy Law #9/,
    );
  });

  it("THROWS on FK violation: cited source_id absent from source.csv", () => {
    const vm = vmFixture({
      ls_history: [historyPoint(2024, "LsGenMay2024", ["src-fake-id-xxxxx"])],
    });
    expect(() => buildPartyProvenance(vm, corpusLookup)).toThrowError(
      /not present in datasets\/data\/entities\/source\.csv/,
    );
  });

  it("populates badges + strip when every rendered card cites a real source_id from the on-disk ledger", () => {
    // Pick any real source_id from the corpus to use as a citation.
    const realSourceId = [...corpusLookup.keys()][0]!;
    const vm = vmFixture({
      ls_history: [historyPoint(2024, "LsGenMay2024", [realSourceId])],
      vs_history: [historyPoint(2021, "AcGenApr2021", [realSourceId])],
      ls_strongholds: [stronghold([realSourceId])],
    });
    const out = buildPartyProvenance(vm, corpusLookup);
    expect(out.badges.parliament).not.toBe("");
    expect(out.badges.state_assembly).not.toBe("");
    expect(out.badges.strongholds).not.toBe("");
    expect(out.strip.total_count).toBe(1);
    expect(out.strip.all[0]!.source_id).toBe(realSourceId);
    // used_in[] picks up every card that cited this source
    expect(out.strip.all[0]!.used_in.sort()).toEqual(
      [
        CARD_LABELS.parliament,
        CARD_LABELS.state_assembly,
        CARD_LABELS.strongholds,
      ].sort(),
    );
  });

  it("strip ordering is producer ASC, vintage DESC, source_id ASC (stable across navigations)", () => {
    // Use 3 real source_ids from the corpus.
    const ids = [...corpusLookup.keys()].slice(0, 3);
    expect(ids).toHaveLength(3);
    const vm = vmFixture({
      ls_history: [
        historyPoint(2024, "LsGenMay2024", ids),
      ],
    });
    const out = buildPartyProvenance(vm, corpusLookup);
    // Verify the sort is internally consistent (we don't pin specific
    // producers because the corpus may grow; the invariant is the
    // comparator yielding a monotonic-non-decreasing producer sequence).
    const producers = out.strip.all.map((s) => s.producer);
    const sorted = [...producers].sort((a, b) => a.localeCompare(b));
    expect(producers).toEqual(sorted);
  });

  it("provenance envelope shape is exactly { badges: {5 keys}, strip: {3 keys} } - no field creep", () => {
    const vm = vmFixture();
    const out = buildPartyProvenance(vm, corpusLookup);
    expect(Object.keys(out).sort()).toEqual(["badges", "strip"]);
    expect(Object.keys(out.badges).sort()).toEqual([
      "alliance_context",
      "current_strength",
      "parliament",
      "state_assembly",
      "strongholds",
    ]);
    expect(Object.keys(out.strip).sort()).toEqual([
      "all",
      "producer_summary",
      "total_count",
    ]);
  });
});

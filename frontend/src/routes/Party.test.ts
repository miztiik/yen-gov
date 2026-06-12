// PR-4 vitest for `Party.svelte`'s `<script module>` helpers.
//
// Per project doctrine (`@testing-library/svelte` is NOT installed):
// pure helpers are extracted to the module block; vitest pins their
// contract without mounting Svelte. The page template is covered by
// the e2e spec (frontend/e2e/party-detail.spec.ts) and the CLAUDE.md
// section 13 in-browser smoke (7 URLs documented in the PR body).

import { describe, expect, it } from "vitest";
import {
  computeKpis,
  formatLatestSentence,
  getAvatarStyle,
  partyRowFromMeta,
  sentinelFraming,
  sparkline,
  type AvatarStyle,
  type PartyKpiStrip,
} from "./Party.svelte";
import type { PartyMeta } from "../lib/view-models/parties";
import type {
  PartyDetailViewModel,
  PartyHistoryPoint,
  PartyTotals,
} from "../lib/view-models/party-detail";

// --- fixtures -------------------------------------------------------------

function metaFixture(overrides: Partial<PartyMeta> = {}): PartyMeta {
  return {
    party_id: "parties.IN.INC",
    short: "INC",
    full: "Indian National Congress",
    founded_year: 1885,
    dissolved_year: null,
    recognition_scope: "national",
    home_state_codes: [],
    symbol_asset: null,
    brand_colour: "#1d4ed8",
    wikipedia: null,
    name_native_script: null,
    is_sentinel: false,
    ...overrides,
  };
}

function viewModelFixture(
  overrides: Partial<PartyDetailViewModel> = {},
): PartyDetailViewModel {
  const totals: PartyTotals = {
    ls_seats: 514,
    vs_seats: 0,
    elections_contested: 7,
    first_year: 1984,
    last_year: 2024,
    peak_ls_seats: 415,
    peak_ls_year: 1984,
    peak_vs_seats: 0,
    peak_vs_year: 0,
    ...overrides.totals,
  };
  return {
    metadata: metaFixture(),
    ls_history: [],
    vs_history: [],
    ls_strongholds: [],
    vs_strongholds: [],
    totals,
    ...overrides,
  };
}

// --- computeKpis ----------------------------------------------------------

describe("computeKpis", () => {
  it("emits all four KPI tile values from the totals block", () => {
    const out: PartyKpiStrip = computeKpis(viewModelFixture());
    expect(out.ls_seats).toBe(514);
    expect(out.vs_seats).toBe(0);
    expect(out.elections_contested).toBe(7);
    expect(out.active_range).toBe("1984-2024");
  });

  it("collapses active_range to a single year when first==last", () => {
    const out = computeKpis(
      viewModelFixture({
        totals: {
          ls_seats: 0,
          vs_seats: 99,
          elections_contested: 1,
          first_year: 2024,
          last_year: 2024,
          peak_ls_seats: 0,
          peak_ls_year: 0,
          peak_vs_seats: 99,
          peak_vs_year: 2024,
        },
      }),
    );
    expect(out.active_range).toBe("2024");
  });

  it("falls back to '-' for active_range when no cycles exist", () => {
    const out = computeKpis(
      viewModelFixture({
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
      }),
    );
    expect(out.active_range).toBe("-");
  });
});

// --- formatLatestSentence -------------------------------------------------

describe("formatLatestSentence", () => {
  it("returns null when the history is empty (consumer skips the line)", () => {
    expect(formatLatestSentence([], 543, "Lok Sabha")).toBeNull();
  });

  it("formats latest seats + vote share + peak framing when latest is below peak", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 1984, period_label: "LsGenDec1984", seats: 415, vote_share_pct: 49.1, contested: 517 },
      { year: 2024, period_label: "LsGenMay2024", seats: 99, vote_share_pct: 21.2, contested: 328 },
    ];
    const out = formatLatestSentence(ls, 543, "Lok Sabha");
    expect(out).toBe(
      "Lok Sabha (2024): 99 of 543 seats . 21.2% vote share . v from peak 415 in 1984.",
    );
  });

  it("omits the peak framing when the latest IS the peak (no down-framing)", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2019, period_label: "LsGenApr2019", seats: 200, vote_share_pct: 31, contested: 400 },
      { year: 2024, period_label: "LsGenMay2024", seats: 240, vote_share_pct: 36, contested: 440 },
    ];
    const out = formatLatestSentence(ls, 543, "Lok Sabha")!;
    expect(out).toMatch(/Lok Sabha \(2024\)/);
    expect(out).toMatch(/240 of 543/);
    expect(out).not.toMatch(/peak/);
  });

  it("emits the up-from-low framing when latest exceeds earlier low", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2019, period_label: "LsGenApr2019", seats: 50, vote_share_pct: 10, contested: 200 },
      { year: 2024, period_label: "LsGenMay2024", seats: 240, vote_share_pct: 36, contested: 440 },
    ];
    const out = formatLatestSentence(ls, 543, "Lok Sabha")!;
    expect(out).toMatch(/\^ from earlier low 50 in 2019/);
  });

  it("omits the 'of N' denominator when total_seats == 0 (mixed-state VS bar)", () => {
    const vs: PartyHistoryPoint[] = [
      { year: 2021, period_label: "AcGenApr2021", seats: 133, vote_share_pct: 37.7, contested: 188 },
    ];
    const out = formatLatestSentence(vs, 0, "Vidhan Sabha")!;
    expect(out).toMatch(/Vidhan Sabha \(2021\): 133 seats/);
    expect(out).not.toMatch(/of \d+/);
  });

  it("omits the vote-share clause when the latest cycle has no vote_share_pct", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2024, period_label: "LsGenMay2024", seats: 99, vote_share_pct: null, contested: 328 },
    ];
    const out = formatLatestSentence(ls, 543, "Lok Sabha")!;
    expect(out).toBe("Lok Sabha (2024): 99 of 543 seats.");
  });

  it("sorts the history defensively before picking the latest", () => {
    const out = formatLatestSentence(
      [
        { year: 2024, period_label: "LsGenMay2024", seats: 99, vote_share_pct: 21.2, contested: 328 },
        { year: 1984, period_label: "LsGenDec1984", seats: 415, vote_share_pct: 49.1, contested: 517 },
      ],
      543,
      "Lok Sabha",
    )!;
    expect(out).toMatch(/\(2024\):/);
  });
});

// --- getAvatarStyle -------------------------------------------------------

describe("getAvatarStyle", () => {
  it("returns the anchor treatment for INC (full-bleed coloured square)", () => {
    const out: AvatarStyle = getAvatarStyle(
      "parties.IN.INC",
      partyRowFromMeta(metaFixture()),
      false,
    );
    expect(out.kind).toBe("anchor");
    expect(out.fill).toBe("#1d4ed8"); // INC blue
    expect(out.ring).toBeNull();
    expect(out.ink).toMatch(/^#[0-9a-f]{6}$/i); // luminance-picked
  });

  it("returns the brand treatment for a party with a brand_colour but no anchor", () => {
    const out = getAvatarStyle(
      "parties.IN.BJD",
      {
        party_id: "parties.IN.BJD",
        brand_colour: { hex: "#16a34a", confidence: "high" },
      },
      false,
    );
    expect(out.kind).toBe("brand");
    expect(out.fill).toBeNull();
    expect(out.ring).toBe("#16a34a");
    expect(out.ink).toBe("#0f172a");
  });

  it("returns the fallback treatment when no anchor + no brand_colour", () => {
    const out = getAvatarStyle(
      "parties.IN.FICTIONAL_PARTY",
      { party_id: "parties.IN.FICTIONAL_PARTY", brand_colour: null },
      false,
    );
    expect(out.kind).toBe("fallback");
    expect(out.fill).toBeNull();
    expect(out.ring).toBeNull();
    expect(out.swatch).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it("returns the sentinel treatment for NOTA (grey neutral, regardless of resolver)", () => {
    const out = getAvatarStyle(
      "parties.IN.NOTA",
      null,
      true,
    );
    expect(out.kind).toBe("sentinel");
    expect(out.fill).toBe("#cbd5e1");
    expect(out.ink).toBe("#334155");
  });
});

// --- partyRowFromMeta -----------------------------------------------------

describe("partyRowFromMeta", () => {
  it("maps brand_colour to the resolver's typed shape with medium confidence", () => {
    const out = partyRowFromMeta(metaFixture({ brand_colour: "#ea580c" }));
    expect(out.party_id).toBe("parties.IN.INC");
    expect(out.brand_colour).toEqual({
      hex: "#ea580c",
      confidence: "medium",
    });
  });

  it("emits brand_colour=null when the meta carries no colour", () => {
    const out = partyRowFromMeta(metaFixture({ brand_colour: null }));
    expect(out.brand_colour).toBeNull();
  });
});

// --- sentinelFraming ------------------------------------------------------

describe("sentinelFraming", () => {
  it("returns the IND framing for the Independent sentinel", () => {
    const out = sentinelFraming("parties.IN.IND")!;
    expect(out).toMatch(/Independent candidates/);
    expect(out).toMatch(/not a single political party/);
  });

  it("returns the NOTA framing for the NOTA sentinel", () => {
    const out = sentinelFraming("parties.IN.NOTA")!;
    expect(out).toMatch(/NOTA \(None of the Above\)/);
    expect(out).toMatch(/leading candidate is still elected/);
  });

  it("returns null for a non-sentinel party (the consumer skips the line)", () => {
    expect(sentinelFraming("parties.IN.INC")).toBeNull();
    expect(sentinelFraming("parties.IN.BJP")).toBeNull();
  });
});

// --- sparkline ------------------------------------------------------------

describe("sparkline", () => {
  it("renders W as filled square and L as empty square", () => {
    expect(sparkline(["W", "W", "L"])).toBe("\u25AE\u25AE\u25AF");
    expect(sparkline(["L", "W", "L", "W"])).toBe("\u25AF\u25AE\u25AF\u25AE");
  });

  it("returns an empty string for an empty input (defensive)", () => {
    expect(sparkline([])).toBe("");
  });
});

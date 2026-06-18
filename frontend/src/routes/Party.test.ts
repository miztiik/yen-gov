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
  formatPeakFraming,
  getAvatarStyle,
  partyRowFromMeta,
  sentinelFraming,
  showPuclAttribution,
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
    aliases: [],
    predecessor_party_ids: [],
    successor_party_ids: [],
    is_sentinel: false,
    leader: null,
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
    ls_methodology_breaks: [],
    // PR-7: Current Strength strip view-model. Default `null` so
    // existing pure-helper tests don't have to fabricate a populated
    // strip shape; new strip-aware tests override per-case.
    current_strength: null,
    // PR-8: Alliance Context strip view-model. Same null-default
    // discipline - existing tests don't need to fabricate the
    // alliance shape; new alliance-aware tests override per-case.
    alliance_context: null,
    // PR-9: provenance envelope (Holy Law #9). Default-empty so
    // existing pure-helper tests don't have to fabricate it; the
    // provenance-aware contract test in
    // `frontend/src/contracts/party-page-provenance.test.ts`
    // exercises `buildPartyProvenance` directly.
    alliance_source_ids: [],
    current_strength_source_ids: [],
    provenance: {
      pills_per_card: {
        parliament: [],
        state_assembly: [],
        strongholds: [],
        current_strength: [],
        alliance_context: [],
      },
    },
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

// --- formatPeakFraming ----------------------------------------------------

describe("formatPeakFraming", () => {
  it("returns empty string when the history is empty (no caption)", () => {
    expect(formatPeakFraming([])).toBe("");
  });

  it("returns the down-from-peak clause when the latest sits below the peak", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 1984, period_label: "LsGenDec1984", seats: 415, vote_share_pct: 49.1, contested: 517, source_ids: [] },
      { year: 2024, period_label: "LsGenMay2024", seats: 99, vote_share_pct: 21.2, contested: 328, source_ids: [] },
    ];
    expect(formatPeakFraming(ls)).toBe(
      "Down from the party's peak of 415 seats in 1984.",
    );
  });

  it("returns empty string when the series is flat (latest equals both peak and low)", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2019, period_label: "LsGenApr2019", seats: 200, vote_share_pct: 31, contested: 400, source_ids: [] },
      { year: 2024, period_label: "LsGenMay2024", seats: 200, vote_share_pct: 33, contested: 420, source_ids: [] },
    ];
    expect(formatPeakFraming(ls)).toBe("");
  });

  it("returns the up-from-low clause when the latest exceeds the earlier low", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2019, period_label: "LsGenApr2019", seats: 50, vote_share_pct: 10, contested: 200, source_ids: [] },
      { year: 2024, period_label: "LsGenMay2024", seats: 240, vote_share_pct: 36, contested: 440, source_ids: [] },
    ];
    expect(formatPeakFraming(ls)).toBe(
      "Up from the party's earlier low of 50 in 2019.",
    );
  });

  it("returns empty string for a single-cycle history (nothing to frame against)", () => {
    const vs: PartyHistoryPoint[] = [
      { year: 2021, period_label: "AcGenApr2021", seats: 133, vote_share_pct: 37.7, contested: 188, source_ids: [] },
    ];
    expect(formatPeakFraming(vs)).toBe("");
  });

  it("sorts the history defensively before picking the latest", () => {
    // Unsorted input: the 2024 cycle (99 seats) is the latest, below
    // the 1984 peak (415). The helper must sort first, then frame.
    const out = formatPeakFraming([
      { year: 2024, period_label: "LsGenMay2024", seats: 99, vote_share_pct: 21.2, contested: 328, source_ids: [] },
      { year: 1984, period_label: "LsGenDec1984", seats: 415, vote_share_pct: 49.1, contested: 517, source_ids: [] },
    ]);
    expect(out).toBe("Down from the party's peak of 415 seats in 1984.");
  });
});

// --- getAvatarStyle -------------------------------------------------------

describe("getAvatarStyle", () => {
  it("returns the symbol treatment for BJP (anchor brand colour + lotus image)", () => {
    const out: AvatarStyle = getAvatarStyle(
      "parties.IN.BJP",
      partyRowFromMeta(
        metaFixture({
          party_id: "parties.IN.BJP",
          short: "BJP",
          brand_colour: null,
          symbol_asset: "party-symbols/lotus.svg",
        }),
      ),
      false,
      "party-symbols/lotus.svg",
    );
    expect(out.kind).toBe("symbol");
    expect(out.fill).toBe("var(--surface)");
    // Ring carries the resolver's BJP anchor hex (curated saffron;
    // current value `#ea580c`). We assert it's a hex string rather
    // than pinning the literal so a future anchor-table tweak in
    // resolver.ts doesn't pull this test into its blast radius.
    expect(out.ring).toMatch(/^#[0-9a-f]{6}$/i);
    expect(out.ring).not.toBeNull();
    expect(out.symbol_url).not.toBeNull();
    expect(out.symbol_url!.endsWith("party-symbols/lotus.svg")).toBe(true);
  });

  it("returns the symbol treatment for INC (anchor brand colour + hand image)", () => {
    const out = getAvatarStyle(
      "parties.IN.INC",
      partyRowFromMeta(
        metaFixture({ symbol_asset: "party-symbols/hand.svg" }),
      ),
      false,
      "party-symbols/hand.svg",
    );
    expect(out.kind).toBe("symbol");
    expect(out.fill).toBe("var(--surface)");
    expect(out.ring).toBe("#1d4ed8"); // INC anchor (blue-700)
    expect(out.symbol_url).not.toBeNull();
    expect(out.symbol_url!.endsWith("party-symbols/hand.svg")).toBe(true);
  });

  it("returns the symbol treatment for DMK (brand-tier colour + rising-sun image)", () => {
    const out = getAvatarStyle(
      "parties.IN.DMK",
      {
        party_id: "parties.IN.DMK",
        brand_colour: { hex: "#dc2626", confidence: "high" },
      },
      false,
      "party-symbols/rising-sun.svg",
    );
    expect(out.kind).toBe("symbol");
    expect(out.fill).toBe("var(--surface)");
    // DMK is resolver-anchored (`#dc2626` rising-sun red); ring is
    // hex regardless of which tier resolved it.
    expect(out.ring).toMatch(/^#[0-9a-f]{6}$/i);
    expect(out.symbol_url).not.toBeNull();
    expect(out.symbol_url!.endsWith("party-symbols/rising-sun.svg")).toBe(true);
  });

  it("returns the token treatment when no symbol_asset is present", () => {
    const out = getAvatarStyle(
      "parties.IN.BJD",
      {
        party_id: "parties.IN.BJD",
        brand_colour: { hex: "#16a34a", confidence: "high" },
      },
      false,
      null,
    );
    expect(out.kind).toBe("token");
    expect(out.fill).toBe("var(--surface)");
    expect(out.ring).toBe("#16a34a");
    expect(out.ink).toBe("#0f172a"); // slate-900
    expect(out.symbol_url).toBeNull();
  });

  it("returns the token treatment for the fallback tier (algorithmic palette colour on ring)", () => {
    const out = getAvatarStyle(
      "parties.IN.FICTIONAL_PARTY",
      { party_id: "parties.IN.FICTIONAL_PARTY", brand_colour: null },
      false,
      null,
    );
    expect(out.kind).toBe("token");
    expect(out.fill).toBe("var(--surface)");
    // Algorithmic palette resolves to SOME hex; we don't pin the
    // value (hash-dependent across PALETTE bumps).
    expect(out.ring).toMatch(/^#[0-9a-f]{6}$/i);
    expect(out.symbol_url).toBeNull();
  });

  it("returns the sentinel treatment for NOTA (slate-200 fill, no ring, slate-600 token)", () => {
    const out = getAvatarStyle("parties.IN.NOTA", null, true, null);
    expect(out.kind).toBe("sentinel");
    expect(out.fill).toBe("#e2e8f0"); // slate-200
    expect(out.ring).toBeNull();
    expect(out.ink).toBe("#475569"); // slate-600
    expect(out.symbol_url).toBeNull();
  });

  it("returns the sentinel treatment for IND (slate-200 fill, no ring, slate-600 token)", () => {
    const out = getAvatarStyle("parties.IN.IND", null, true, null);
    expect(out.kind).toBe("sentinel");
    expect(out.fill).toBe("#e2e8f0");
    expect(out.ring).toBeNull();
    expect(out.ink).toBe("#475569");
    expect(out.symbol_url).toBeNull();
  });

  it("ignores symbol_asset for sentinel parties (sentinel takes precedence)", () => {
    const out = getAvatarStyle(
      "parties.IN.NOTA",
      null,
      true,
      "party-symbols/should-be-ignored.svg",
    );
    expect(out.kind).toBe("sentinel");
    expect(out.symbol_url).toBeNull();
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
    expect(out).toMatch(/Independent isn't one party/);
    expect(out).toMatch(/everyone who ran without a party/);
    expect(out).toMatch(/numbers below mix them all together/);
  });

  it("returns the NOTA framing for the NOTA sentinel", () => {
    const out = sentinelFraming("parties.IN.NOTA")!;
    expect(out).toMatch(/NOTA lets you vote against every candidate/);
    expect(out).toMatch(/leading candidate still wins/);
    expect(out).toMatch(/no re-election/);
  });

  it("returns null for a non-sentinel party (the consumer skips the line)", () => {
    expect(sentinelFraming("parties.IN.INC")).toBeNull();
    expect(sentinelFraming("parties.IN.BJP")).toBeNull();
  });
});

// --- showPuclAttribution --------------------------------------------------

describe("showPuclAttribution", () => {
  it("returns true ONLY for the NOTA sentinel", () => {
    expect(showPuclAttribution("parties.IN.NOTA")).toBe(true);
  });

  it("returns false for the Independent sentinel (PUCL framing is NOTA-only)", () => {
    expect(showPuclAttribution("parties.IN.IND")).toBe(false);
  });

  it("returns false for real parties (regression check)", () => {
    expect(showPuclAttribution("parties.IN.INC")).toBe(false);
    expect(showPuclAttribution("parties.IN.BJP")).toBe(false);
    expect(showPuclAttribution("parties.IN.AAP")).toBe(false);
  });
});


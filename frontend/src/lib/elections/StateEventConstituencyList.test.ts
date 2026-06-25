// Oracle unit tests for the constituency list's pure logic (Row 2 of
// TODO/20260622-election-constituency-grouping-plan.md). The component
// (`StateEventConstituencyList.svelte`) is a thin renderer over these
// helpers, so testing the helpers IS testing the component's contract.
//
// Pure: node-env, no DOM, no Svelte mount (mirrors the dir's existing
// readFileSync/pure-helper test convention). No mocks - every assertion
// runs the real exported function the UI calls.

import { describe, it, expect } from "vitest";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  buildGroups,
  buildPartyStrip,
  fmtShare,
  fmtMarginSigned,
  marginBand,
  marginBarSegment,
  reservationKind,
  sortLeaves,
  applyFilters,
  distinctDistrictCount,
  formatCountLine,
  GRID_COLS,
  PENDING_GROUP,
  STRIP_OTHER_COLOR,
  type GroupHeaderResult,
  type StripInput,
} from "./constituency-list-tokens";

// Expand a {short: seatCount} map into per-seat strip inputs. Party id ==
// short; colour is deterministic per party.
function rowsFromCounts(counts: Record<string, number>): StripInput[] {
  const colors: Record<string, string> = {
    TDP: "#fdd835",
    YSRCP: "#1565c0",
    JSP: "#e53935",
    A: "#111111",
    B: "#222222",
    C: "#333333",
    D: "#444444",
    E: "#555555",
    F: "#666666",
  };
  const out: StripInput[] = [];
  for (const [short, n] of Object.entries(counts)) {
    for (let k = 0; k < n; k++) {
      out.push({
        winner_party_short: short,
        winner_party_id: short,
        winner_color: colors[short] ?? "#999999",
      });
    }
  }
  return out;
}

// A minimal leaf used by the filter / sort / count oracles.
interface Leaf {
  entity_id: string;
  entity_name: string;
  district?: string | null;
  reservation?: string | null;
  eci_no?: number | null;
  margin_pct: number | null;
}

function leaf(over: Partial<Leaf> & { entity_name: string }): Leaf {
  return {
    entity_id: over.entity_id ?? over.entity_name,
    entity_name: over.entity_name,
    district: over.district,
    reservation: over.reservation,
    eci_no: over.eci_no,
    margin_pct: over.margin_pct ?? null,
  };
}

describe("buildPartyStrip - proportional segmented strip", () => {
  it("ORACLE: {TDP:9, YSRCP:6, JSP:2} -> 3 segments summing 100%, desc, label 'TDP 9/17'", () => {
    const strip = buildPartyStrip(rowsFromCounts({ TDP: 9, YSRCP: 6, JSP: 2 }));

    // Exactly 3 segments (no "other" - only 3 distinct parties).
    expect(strip.segments).toHaveLength(3);
    expect(strip.segments.some((s) => s.is_other)).toBe(false);

    // Ordered descending by seat count.
    expect(strip.segments.map((s) => s.party_short)).toEqual(["TDP", "YSRCP", "JSP"]);
    expect(strip.segments.map((s) => s.count)).toEqual([9, 6, 2]);

    // Widths proportional + summing to 100%.
    const sum = strip.segments.reduce((acc, s) => acc + s.pct, 0);
    expect(sum).toBeCloseTo(100, 6);
    expect(strip.segments[0].pct).toBeCloseTo((9 / 17) * 100, 6);
    expect(strip.segments[1].pct).toBeGreaterThan(strip.segments[2].pct);

    // Leading-party label spells the leader - NEVER colour-only.
    expect(strip.leader_label).toBe("TDP 9/17");
    expect(strip.total).toBe(17);
  });

  it("ORACLE: sweep {TDP:16} -> 1 full-width segment, label 'TDP 16/16'", () => {
    const strip = buildPartyStrip(rowsFromCounts({ TDP: 16 }));
    expect(strip.segments).toHaveLength(1);
    expect(strip.segments[0].pct).toBe(100);
    expect(strip.segments[0].count).toBe(16);
    expect(strip.leader_label).toBe("TDP 16/16");
  });

  it("collapses parties beyond the top-4 into ONE 'Other' segment", () => {
    // 6 distinct parties -> top 4 + Other(E+F).
    const strip = buildPartyStrip(rowsFromCounts({ A: 5, B: 4, C: 3, D: 2, E: 1, F: 1 }));
    expect(strip.segments).toHaveLength(5);
    const other = strip.segments[strip.segments.length - 1];
    expect(other.is_other).toBe(true);
    expect(other.party_short).toBe("Other");
    expect(other.color).toBe(STRIP_OTHER_COLOR);
    expect(other.count).toBe(2); // E(1) + F(1)
    expect(strip.leader_label).toBe("A 5/16");
    const sum = strip.segments.reduce((acc, s) => acc + s.pct, 0);
    expect(sum).toBeCloseTo(100, 6);
  });

  it("empty group yields no segments and an empty label", () => {
    const strip = buildPartyStrip([]);
    expect(strip.segments).toHaveLength(0);
    expect(strip.leader_label).toBe("");
    expect(strip.total).toBe(0);
  });
});

describe("marginBand - RdYlBu bands (shared with StateOverview)", () => {
  it("< 5 is the red nail-biter band", () => {
    expect(marginBand(2.1)).toEqual({ key: "nail-biter", hex: "#d7191c", label: "nail-biter" });
  });
  it("[5,10) is the orange contestable band", () => {
    expect(marginBand(5)?.key).toBe("contestable");
    expect(marginBand(7.4)?.hex).toBe("#fdae61");
  });
  it(">= 10 is the blue comfortable band", () => {
    expect(marginBand(10)?.key).toBe("comfortable");
    expect(marginBand(12.6)?.hex).toBe("#2c7bb6");
  });
  it("returns null for an unknown margin", () => {
    expect(marginBand(null)).toBeNull();
    expect(marginBand(undefined)).toBeNull();
    expect(marginBand(Number.NaN)).toBeNull();
  });
});

describe("fmtShare + fmtMarginSigned - typed number tokens", () => {
  it("ORACLE: fmtShare is one-decimal percent WITH the % suffix", () => {
    expect(fmtShare(45.04)).toBe("45.0%");
    expect(fmtShare(0)).toBe("0.0%");
    expect(fmtShare(100)).toBe("100.0%");
  });
  it("ORACLE: fmtMarginSigned is one-decimal, LEADING SIGN, NO % (standard JS rounding)", () => {
    expect(fmtMarginSigned(15.9)).toBe("+15.9");
    expect(fmtMarginSigned(-0.36)).toBe("-0.4");
    expect(fmtMarginSigned(0)).toBe("+0.0");
  });
  it("both render the shared em-dash for null / undefined / NaN", () => {
    expect(fmtShare(null)).toBe("-");
    expect(fmtShare(undefined)).toBe("-");
    expect(fmtShare(Number.NaN)).toBe("-");
    expect(fmtMarginSigned(null)).toBe("-");
    expect(fmtMarginSigned(undefined)).toBe("-");
    expect(fmtMarginSigned(Number.NaN)).toBe("-");
  });
});

describe("marginBarSegment - magnitude bar on a fixed 0..50pp scale + shared band hue", () => {
  it("ORACLE: a 0.36pp nail-biter paints the RED band and reads shorter than a 15.9pp lead", () => {
    const tight = marginBarSegment(0.36);
    const wide = marginBarSegment(15.9);
    // Reuses marginBand() - 0.36 < 5 -> the red nail-biter band (no new palette).
    expect(tight.hex).toBe("#d7191c");
    expect(tight.hex).toBe(marginBand(0.36)?.hex);
    // Magnitude width: a tighter lead is a shorter bar.
    expect(tight.pct).toBeLessThan(wide.pct);
    expect(tight.pct).toBeCloseTo((0.36 / 50) * 100, 6);
    expect(wide.pct).toBeCloseTo((15.9 / 50) * 100, 6);
  });
  it("clamps the magnitude to 100% at >= 50pp and treats sign as magnitude", () => {
    expect(marginBarSegment(50).pct).toBe(100);
    expect(marginBarSegment(80).pct).toBe(100);
    expect(marginBarSegment(-12).pct).toBeCloseTo((12 / 50) * 100, 6);
  });
  it("an unknown margin is a zero-width neutral segment (existing slate, no new palette)", () => {
    expect(marginBarSegment(null)).toEqual({ pct: 0, hex: STRIP_OTHER_COLOR });
    expect(marginBarSegment(undefined)).toEqual({ pct: 0, hex: STRIP_OTHER_COLOR });
    expect(marginBarSegment(Number.NaN)).toEqual({ pct: 0, hex: STRIP_OTHER_COLOR });
  });
});

describe("GRID_COLS - the shared 6-track subgrid ruler", () => {
  it("is the single 6-track ruler the renderer + national rail share", () => {
    expect(GRID_COLS).toBe(
      "grid-cols-[1.25rem_minmax(0,1fr)_minmax(0,max-content)_max-content_max-content_max-content]",
    );
    // 6 tracks: glyph | name | context | share | margin | bar.
    const tracks = GRID_COLS.replace("grid-cols-[", "").replace(/\]$/, "").split("_");
    expect(tracks).toHaveLength(6);
  });
});

describe("reservationKind - GEN / SC / ST normalisation", () => {
  it("maps SC / ST (any case, padded) to themselves", () => {
    expect(reservationKind("SC")).toBe("SC");
    expect(reservationKind("st")).toBe("ST");
    expect(reservationKind(" ST ")).toBe("ST");
  });
  it("collapses GEN / null / undefined / empty to GEN (no badge)", () => {
    expect(reservationKind("GEN")).toBe("GEN");
    expect(reservationKind(null)).toBe("GEN");
    expect(reservationKind(undefined)).toBe("GEN");
    expect(reservationKind("")).toBe("GEN");
  });
});

describe("applyFilters + count line - Reserved filter AND name search", () => {
  const rows: Leaf[] = [
    leaf({ entity_name: "Alpha", reservation: "SC", district: "D1" }),
    leaf({ entity_name: "Beta", reservation: "GEN", district: "D1" }),
    leaf({ entity_name: "Gamma", reservation: "ST", district: "D2" }),
    leaf({ entity_name: "Delta", reservation: "SC", district: "D2" }),
  ];

  it("ORACLE: Reserved=SC yields only SC leaves and the count text matches", () => {
    const sc = applyFilters(rows, "", "SC");
    expect(sc.map((r) => r.entity_name)).toEqual(["Alpha", "Delta"]);
    const text = formatCountLine(sc.length, distinctDistrictCount(sc));
    expect(text).toBe("2 constituencies in 2 districts");
  });

  it("All shows every row; the count reflects the full set", () => {
    const all = applyFilters(rows, "", "All");
    expect(all).toHaveLength(4);
    expect(formatCountLine(all.length, distinctDistrictCount(all))).toBe("4 constituencies in 2 districts");
  });

  it("AND-composes the name search with the Reserved filter", () => {
    const scAlpha = applyFilters(rows, "alp", "SC");
    expect(scAlpha.map((r) => r.entity_name)).toEqual(["Alpha"]);
    expect(formatCountLine(scAlpha.length, distinctDistrictCount(scAlpha))).toBe("1 constituency in 1 district");
  });
});

describe("sortLeaves - ballot order vs by-margin", () => {
  const rows: Leaf[] = [
    leaf({ entity_id: "a", entity_name: "A", eci_no: 3, margin_pct: 12 }),
    leaf({ entity_id: "b", entity_name: "B", eci_no: 1, margin_pct: 2 }),
    leaf({ entity_id: "c", entity_name: "C", eci_no: 2, margin_pct: 7 }),
  ];

  it("ORACLE: ballot orders by eci_no ascending; margin orders nail-biters first", () => {
    expect(sortLeaves(rows, "ballot").map((r) => r.eci_no)).toEqual([1, 2, 3]);
    expect(sortLeaves(rows, "margin").map((r) => r.margin_pct)).toEqual([2, 7, 12]);
  });

  it("does not mutate the input array", () => {
    const before = rows.map((r) => r.entity_id);
    sortLeaves(rows, "margin");
    expect(rows.map((r) => r.entity_id)).toEqual(before);
  });

  it("sinks null sort keys to the end, stably", () => {
    const mixed: Leaf[] = [
      leaf({ entity_id: "x", entity_name: "X", eci_no: null, margin_pct: 5 }),
      leaf({ entity_id: "y", entity_name: "Y", eci_no: 2, margin_pct: 5 }),
      leaf({ entity_id: "z", entity_name: "Z", eci_no: 1, margin_pct: 5 }),
    ];
    expect(sortLeaves(mixed, "ballot").map((r) => r.entity_id)).toEqual(["z", "y", "x"]);
  });
});

// A leaf satisfying GroupableLeaf (what buildGroups keys on): the winner trio
// for the assembly strip + margin/eci for sorting + district/pc_group for the
// grouping key. SeatRow satisfies this structurally.
interface GLeaf {
  entity_id: string;
  entity_name: string;
  district?: string | null;
  pc_group?: string | null;
  reservation?: string | null;
  eci_no?: number | null;
  margin_pct: number | null;
  winner_party_short: string;
  winner_party_id: string;
  winner_color: string;
}

function gleaf(over: Partial<GLeaf> & { entity_name: string }): GLeaf {
  return {
    entity_id: over.entity_id ?? over.entity_name,
    entity_name: over.entity_name,
    district: over.district,
    pc_group: over.pc_group,
    reservation: over.reservation,
    eci_no: over.eci_no,
    margin_pct: over.margin_pct ?? null,
    winner_party_short: over.winner_party_short ?? "TDP",
    winner_party_id: over.winner_party_id ?? "TDP",
    winner_color: over.winner_color ?? "#fdd835",
  };
}

describe("buildGroups - assembly mode (strip) vs PC mode (header result)", () => {
  it("ORACLE: PC mode - header_result present -> group header carries the result, leaves carry district labels, NO strip", () => {
    // Three child ACs under PC "Vijayawada", each with its own LGD district.
    const rows: GLeaf[] = [
      gleaf({ entity_name: "Vijayawada West", pc_group: "Vijayawada", district: "Krishna", eci_no: 1 }),
      gleaf({ entity_name: "Mylavaram", pc_group: "Vijayawada", district: "NTR", eci_no: 2 }),
      gleaf({ entity_name: "Nandigama", pc_group: "Vijayawada", district: "NTR", reservation: "SC", eci_no: 3 }),
    ];
    const header: GroupHeaderResult = {
      chip: "TDP",
      color: "#fdd835",
      share: 54.2,
      margin: 11.0,
      child_count: 3,
      reservation: null,
    };
    const groups = buildGroups(rows, "ballot", { Vijayawada: header });

    expect(groups).toHaveLength(1);
    const g = groups[0];
    expect(g.group_key).toBe("Vijayawada");
    expect(g.mode).toBe("pc");
    // The GROUP HEADER shows the result (chip + share + margin band + child
    // count) - the renderer reads it straight off header_result.
    expect(g.header_result).toEqual(header);
    expect(g.header_result?.chip).toBe("TDP");
    expect(g.header_result?.share).toBe(54.2);
    expect(marginBand(g.header_result?.margin ?? null)?.key).toBe("comfortable");
    expect(g.header_result?.child_count).toBe(3);
    // PC mode shows NO assembly party strip (the strip is the assembly glance;
    // PC mode shows the single MP result instead).
    expect(g.strip).toBeNull();
    // The leaves render as navigation + a DISTRICT LABEL (their own LGD
    // district), in ballot order, with NO per-AC result chip - the renderer
    // switches the leaf shape on g.mode === "pc".
    expect(g.rows.map((r) => r.entity_name)).toEqual(["Vijayawada West", "Mylavaram", "Nandigama"]);
    expect(g.rows.map((r) => r.district)).toEqual(["Krishna", "NTR", "NTR"]);
  });

  it("ORACLE: assembly mode unchanged - no group_headers -> party strip + null header (leaves keep result chips)", () => {
    // Three ACs in one district; assembly mode (no group_headers supplied).
    const rows: GLeaf[] = [
      gleaf({ entity_name: "Tadikonda", district: "Guntur", winner_party_short: "YSRCP", winner_party_id: "YSRCP", winner_color: "#1565c0", margin_pct: 2.1, eci_no: 163 }),
      gleaf({ entity_name: "Mangalagiri", district: "Guntur", winner_party_short: "TDP", winner_party_id: "TDP", winner_color: "#fdd835", margin_pct: 7.4, eci_no: 164 }),
      gleaf({ entity_name: "Ponnur", district: "Guntur", winner_party_short: "TDP", winner_party_id: "TDP", winner_color: "#fdd835", margin_pct: 12.6, eci_no: 165 }),
    ];
    const groups = buildGroups(rows, "ballot");

    expect(groups).toHaveLength(1);
    const g = groups[0];
    expect(g.group_key).toBe("Guntur");
    expect(g.mode).toBe("assembly");
    // Assembly mode renders the proportional party strip in the header and
    // keeps the per-leaf result table (g.mode !== "pc"), so the leaves still
    // show their result chips exactly as before Row 3.
    expect(g.header_result).toBeNull();
    expect(g.strip).not.toBeNull();
    expect(g.strip?.leader_label).toBe("TDP 2/3");
    expect(g.strip?.segments.map((s) => s.party_short)).toEqual(["TDP", "YSRCP"]);
    // The leaf data the assembly table renders (winner chip + share + margin)
    // is intact on every row.
    expect(g.rows.map((r) => r.winner_party_short)).toContain("YSRCP");
  });

  it("PC mode: pc_group keys the group; null pc_group pools into PENDING (district ignored); PC mode only where a header exists", () => {
    const rows: GLeaf[] = [
      gleaf({ entity_name: "AC-b", pc_group: "PC-Z", district: "D2", eci_no: 5 }),
      gleaf({ entity_name: "AC-a", pc_group: "PC-A", district: "D1", eci_no: 9 }),
      gleaf({ entity_name: "AC-c", district: "D-only", eci_no: 1 }), // null pc_group + a real district
      gleaf({ entity_name: "AC-d", eci_no: 2 }),                      // null pc_group + no district
    ];
    const header: GroupHeaderResult = { chip: "X", color: "#000000", share: null, margin: null, child_count: 1 };
    const groups = buildGroups(rows, "ballot", { "PC-A": header });

    // pc_group keys the PC groups; BOTH null-pc_group leaves pool into the one
    // PENDING bucket (district is NOT a PC-mode fallback); PENDING sorts LAST.
    expect(groups.map((g) => g.group_key)).toEqual(["PC-A", "PC-Z", PENDING_GROUP]);
    // ONLY the group with a header entry is PC mode; everything else stays
    // assembly mode (a PC group with no header, and the pending bucket).
    expect(groups.find((g) => g.group_key === "PC-A")?.mode).toBe("pc");
    expect(groups.find((g) => g.group_key === "PC-Z")?.mode).toBe("assembly");
    expect(groups.find((g) => g.group_key === PENDING_GROUP)?.mode).toBe("assembly");
    // The pending bucket holds BOTH unlinked ACs regardless of their district.
    expect(groups.find((g) => g.group_key === PENDING_GROUP)?.rows.map((r) => r.entity_name)).toEqual(["AC-c", "AC-d"]);
  });

  it("PC mode: a null-pc_group leaf lands in 'Parliament seat pending', forced LAST even past a 'Zzz' group that sorts after it", () => {
    const rows: GLeaf[] = [
      gleaf({ entity_name: "Linked", pc_group: "Zzz", district: "DistX", eci_no: 1 }),
      gleaf({ entity_name: "Unlinked", pc_group: null, district: "Nizamabad", eci_no: 2 }),
    ];
    const header: GroupHeaderResult = { chip: "Z", color: "#000000", share: null, margin: null, child_count: 1 };
    const groups = buildGroups(rows, "ballot", { Zzz: header });

    // "Zzz" localeCompare-sorts AFTER "Parliament seat pending", yet PENDING is
    // forced to the very end (D5 - never wedged mid-list).
    expect(PENDING_GROUP).toBe("Parliament seat pending");
    expect(groups.map((g) => g.group_key)).toEqual(["Zzz", PENDING_GROUP]);
    expect(groups[groups.length - 1].group_key).toBe(PENDING_GROUP);
    // The unlinked AC (null pc_group, but a real district) is in PENDING.
    expect(groups.find((g) => g.group_key === PENDING_GROUP)?.rows.map((r) => r.entity_name)).toEqual(["Unlinked"]);
  });

  it("assembly mode (no group_headers) is UNCHANGED - null keys fall back to 'All constituencies', PENDING_GROUP never appears", () => {
    const rows: GLeaf[] = [
      gleaf({ entity_name: "AC-1", district: "Guntur", eci_no: 1 }),
      gleaf({ entity_name: "AC-2", district: "Krishna", eci_no: 2 }),
      gleaf({ entity_name: "AC-orphan", eci_no: 3 }), // null pc_group + null district
    ];
    const groups = buildGroups(rows, "ballot"); // assembly mode - no headers

    // The both-null leaf still uses the "All constituencies" fallback (NOT
    // PENDING); groups sort purely by localeCompare; every group is assembly.
    expect(groups.map((g) => g.group_key)).toEqual(["All constituencies", "Guntur", "Krishna"]);
    expect(groups.every((g) => g.mode === "assembly")).toBe(true);
    expect(groups.some((g) => g.group_key === PENDING_GROUP)).toBe(false);
  });

  it("PC-mode leaves re-sort by margin when the sort mode flips (shared sortLeaves path)", () => {
    const rows: GLeaf[] = [
      gleaf({ entity_name: "AC-hi", pc_group: "PC", district: "D", eci_no: 1, margin_pct: 12 }),
      gleaf({ entity_name: "AC-lo", pc_group: "PC", district: "D", eci_no: 2, margin_pct: 2 }),
    ];
    const header: GroupHeaderResult = { chip: "Y", color: "#111111", share: 50, margin: 10, child_count: 2 };
    const ballot = buildGroups(rows, "ballot", { PC: header });
    const margin = buildGroups(rows, "margin", { PC: header });
    expect(ballot[0].rows.map((r) => r.eci_no)).toEqual([1, 2]);
    expect(margin[0].rows.map((r) => r.margin_pct)).toEqual([2, 12]);
  });
});

// ---------------------------------------------------------------------------
// Row 3 (Option-E margin-bar) STRUCTURAL oracle. The project does NOT install
// `@testing-library/svelte` (node-env vitest, no Svelte mount - see the
// readFileSync precedent in state-event-heading-harmony.test.ts /
// StateElection.section-order.test.ts), so the rendered-markup oracle is
// asserted against the component SOURCE. HTML comments are stripped first so
// the descriptive "the old <table> / justify-between layout is GONE" prose in
// the source comments can never satisfy an absence assertion. The assertions
// are scoped to the constituency LIST region (from the shared-ruler <ul>
// onward); the sticky search/filter/sort TOOLBAR above it legitimately keeps
// its own `flex ... justify-between` chrome and is out of scope for the rip.
// ---------------------------------------------------------------------------

const COMPONENT_SRC = readFileSync(
  resolve(__dirname, "./StateEventConstituencyList.svelte"),
  "utf8",
);

// Everything from the shared-ruler <ul> to the end of the file = the ripped
// list render, with HTML comments removed.
const LIST_SRC = COMPONENT_SRC.slice(
  COMPONENT_SRC.indexOf("grid ${GRID_COLS}"),
).replace(/<!--[\s\S]*?-->/g, "");

describe("StateEventConstituencyList.svelte - Option-E 6-track subgrid render (Row 3)", () => {
  it("ORACLE (a): the list parent consumes the shared GRID_COLS ruler", () => {
    // The 6-track ruler is declared ONCE on the parent <ul> via the R2 token,
    // never re-hardcoded here, so the renderer + the Row 4 rail share it.
    expect(COMPONENT_SRC).toContain("grid ${GRID_COLS}");
  });

  it("ORACLE (a): every list row is a `col-span-full grid grid-cols-subgrid` row", () => {
    // The group <li>, the header <button>, and the leaf <a> are each a
    // full-span subgrid row (>= 3 occurrences), so they align track-for-track.
    const rows = LIST_SRC.match(/col-span-full grid grid-cols-subgrid/g) ?? [];
    expect(rows.length).toBeGreaterThanOrEqual(3);
  });

  it("ORACLE (a): NO `justify-between` and NO dashed result table survive in the list render", () => {
    expect(LIST_SRC).not.toContain("justify-between");
    expect(LIST_SRC).not.toContain("<table");
    expect(LIST_SRC).not.toContain("<thead");
    expect(LIST_SRC).not.toContain("<tbody");
    expect(LIST_SRC).not.toContain("<td");
  });

  it("ORACLE (b): the AC leaf is a WHOLE-ROW <a href={r.href}> with an arrow-up-right jump glyph + a map-pin district cell", () => {
    // The whole row is the link (carries the row testid on the <a>).
    expect(LIST_SRC).toMatch(
      /<a\b[\s\S]*?href=\{r\.href\}[\s\S]*?data-testid="state-event-constituency-row"/,
    );
    expect(LIST_SRC).toContain('name="arrow-up-right"');
    expect(LIST_SRC).toContain('name="map-pin"');
    expect(LIST_SRC).toContain(
      'data-testid="state-event-constituency-leaf-district"',
    );
  });

  it("ORACLE (c): a null-district leaf renders 'District pending' (no dashed cell); the pending bucket header reads 'data pending'", () => {
    expect(LIST_SRC).toContain("District pending");
    expect(LIST_SRC).toContain("data pending");
    // The unlinked-AC bucket reuses the shared PENDING_GROUP label, never a
    // bespoke dashed table.
    expect(LIST_SRC).toContain("PENDING_GROUP");
  });

  it("ORACLE (e): assembly-mode leaves carry the per-AC winner chip + share + signed margin (PC-mode leaves leave tracks 4-6 empty)", () => {
    // Tracks 4-6 are gated on !pc_mode (assembly only).
    expect(LIST_SRC).toContain("{#if !pc_mode}");
    expect(LIST_SRC).toContain("r.winner_party_short");
    expect(LIST_SRC).toContain("r.winner_color");
  });

  it("consumes the R2 typed-token + margin-bar helpers on both the PC header and the assembly leaf", () => {
    expect(LIST_SRC).toContain("fmtShare(");
    expect(LIST_SRC).toContain("fmtMarginSigned(");
    expect(LIST_SRC).toContain("marginBarSegment(");
  });
});

describe("Row 3 ORACLE (d): buildGroups is a bijection - every input leaf renders, nothing dropped", () => {
  it("PC mode: the multiset of rendered leaves == the input, and the orphans pool in the PENDING bucket", () => {
    const rows: GLeaf[] = [
      gleaf({ entity_name: "AC-1", pc_group: "PC-A", district: "D1", eci_no: 1 }),
      gleaf({ entity_name: "AC-2", pc_group: "PC-A", district: "D1", eci_no: 2 }),
      gleaf({ entity_name: "AC-3", pc_group: "PC-B", district: "D2", eci_no: 3 }),
      gleaf({ entity_name: "AC-orphan-1", pc_group: null, district: "D3", eci_no: 4 }),
      gleaf({ entity_name: "AC-orphan-2", pc_group: null, district: null, eci_no: 5 }),
    ];
    const headers: Record<string, GroupHeaderResult> = {
      "PC-A": { chip: "X", color: "#000000", share: null, margin: null, child_count: 2 },
    };
    const groups = buildGroups(rows, "ballot", headers);

    const rendered = groups.flatMap((g) => g.rows.map((r) => r.entity_id));
    // Bijection: every input id appears exactly once across all groups
    // (including the pending bucket) - nothing dropped, nothing duplicated.
    expect(rendered).toHaveLength(rows.length);
    expect(rendered.slice().sort()).toEqual(rows.map((r) => r.entity_id).slice().sort());
    // The two null-pc_group orphans pool into the one pending bucket.
    const pendingGroup = groups.find((g) => g.group_key === PENDING_GROUP);
    expect(pendingGroup?.rows.map((r) => r.entity_name)).toEqual([
      "AC-orphan-1",
      "AC-orphan-2",
    ]);
  });

  it("assembly mode: the multiset of rendered leaves == the input (null-district leaf still renders)", () => {
    const rows: GLeaf[] = [
      gleaf({ entity_name: "AC-1", district: "Guntur", eci_no: 1 }),
      gleaf({ entity_name: "AC-2", district: "Krishna", eci_no: 2 }),
      gleaf({ entity_name: "AC-3", district: null, eci_no: 3 }),
    ];
    const groups = buildGroups(rows, "ballot");
    const rendered = groups.flatMap((g) => g.rows.map((r) => r.entity_id));
    expect(rendered).toHaveLength(rows.length);
    expect(rendered.slice().sort()).toEqual(rows.map((r) => r.entity_id).slice().sort());
  });

  it("ORACLE (e, logic): assembly-mode leaves keep their winner data for the per-AC chip", () => {
    const rows: GLeaf[] = [
      gleaf({ entity_name: "AC-1", district: "D", winner_party_short: "TDP", margin_pct: 5, eci_no: 1 }),
    ];
    const groups = buildGroups(rows, "ballot");
    expect(groups[0].mode).toBe("assembly");
    expect(groups[0].rows[0].winner_party_short).toBe("TDP");
  });
});

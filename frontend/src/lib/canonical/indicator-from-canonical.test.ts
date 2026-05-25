// Vitest — Phase B canonical→legacy IndicatorArtifact adapter
// (P.1.A C4.7, plan TODO/20260524-p1a-data-reacquisition-plan.md §3).
//
// Per CLAUDE.md §15: the loader's contract IS the DuckDB-WASM boundary —
// mocking `query` / `registerTable` is the explicit carve-out from Holy
// Law #7 (no mocks). The round-trip against the real Parquet shard is
// asserted by the §13 browser-smoke (state hub /s/tamil-nadu shows the
// peak demand card with the FY13–FY25 sparkline + 245.4k MW national).

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  registerSlice: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

vi.mock("../indicators", async () => {
  // Pull in the real module so we re-export every helper the production
  // code path expects (uniqueTimes, seriesByEntity, ...). Only the
  // network-touching `fetchIndicator` gets a vi.fn() stub so the
  // Phase B-extension `loadIndicator(path)` legacy fall-through can be
  // asserted without hitting fetch().
  const actual = await vi.importActual<typeof import("../indicators")>("../indicators");
  return {
    ...actual,
    fetchIndicator: vi.fn(),
  };
});

import { query, registerTable } from "../duckdb";
import { fetchIndicator } from "../indicators";
import {
  buildIndicatorArtifact,
  canonicalEntityToLegacy,
  legacyArtifactIdFromPath,
  loadIndicator,
  loadIndicatorFromCanonical,
  loadIndicatorIfCanonical,
} from "./indicator-from-canonical";
import {
  CANONICAL_BACKED_INDICATORS,
  getCanonicalDescriptor,
  isCanonicalBacked,
  type CanonicalIndicatorDescriptor,
} from "./indicator-allowlist";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);
const mockedFetch = vi.mocked(fetchIndicator);

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
  mockedFetch.mockReset();
});

// Test fixture mirrors the on-disk shape of the C4.7 Phase A canonical row.
// Pre-loaded into the descriptor lookup; one real entry today (peak demand).
const PEAK_DEMAND_DESCRIPTOR: CanonicalIndicatorDescriptor = getCanonicalDescriptor(
  "energy/state_peak_electricity_demand_mw",
)!;

describe("indicator-allowlist (Phase B registry invariants)", () => {
  it("exports at least one descriptor (the C4.7 Phase B seed)", () => {
    expect(CANONICAL_BACKED_INDICATORS.length).toBeGreaterThan(0);
  });

  it("treats the seed peak-demand artifact as canonical-backed", () => {
    expect(isCanonicalBacked("energy/state_peak_electricity_demand_mw")).toBe(true);
  });

  it("treats unrelated artifacts as legacy-backed (false)", () => {
    expect(isCanonicalBacked("energy/state_per_capita_electricity_consumption_kwh")).toBe(false);
    expect(isCanonicalBacked("does/not/exist")).toBe(false);
    expect(isCanonicalBacked("")).toBe(false);
  });

  it("resolves the descriptor for the seed artifact and null otherwise", () => {
    const d = getCanonicalDescriptor("energy/state_peak_electricity_demand_mw");
    expect(d).not.toBeNull();
    // Seed descriptor is the kind:"single" shape — narrow before accessing
    // the single-variant canonical_indicator_id field.
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("state-peak-electricity-demand-mw");
    }
    expect(d!.table_id).toBe("energy.energy_demand_supply");
    expect(getCanonicalDescriptor("nope")).toBeNull();
  });

  it("seed descriptor carries the citizen-visible IndicatorMeta block", () => {
    expect(PEAK_DEMAND_DESCRIPTOR.meta.title).toMatch(/peak/i);
    expect(PEAK_DEMAND_DESCRIPTOR.meta.unit).toBe("MW");
    expect(PEAK_DEMAND_DESCRIPTOR.meta.entity_kind).toBe("state");
    expect(PEAK_DEMAND_DESCRIPTOR.meta.time_grain).toBe("fiscal_year");
  });
});

describe("PR 7a — additive reader-switch for 8 energy descriptors", () => {
  // Registry-shape invariants for every PR 7a descriptor. Per CLAUDE.md §15
  // these are CONTRACT tests: they assert the allowlist's published surface
  // (legacy slug → canonical indicator id + table_id + meta) matches the
  // expected wiring for each of the 8 shards reader-switched in this PR.
  // Catches accidental future edits to the wrong row or a typo'd table_id
  // (which would silently fall through to legacy fetch and 404 once Phase D
  // git-rm's the underlying shard).

  const PR_7A: ReadonlyArray<{
    legacy_id: string;
    canonical_id: string;
    table_id: string;
  }> = [
    {
      legacy_id: "energy/installed_capacity_coal_mw",
      canonical_id: "state-installed-capacity-snapshot-mw-coal",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_gas_mw",
      canonical_id: "state-installed-capacity-snapshot-mw-gas",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_hydro_mw",
      canonical_id: "state-installed-capacity-snapshot-mw-hydro",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_nuclear_mw",
      canonical_id: "state-installed-capacity-snapshot-mw-nuclear",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_renewable_mw",
      canonical_id: "state-installed-capacity-snapshot-mw-renewable",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/state_installed_capacity_geographical_mw",
      canonical_id: "state-installed-capacity-geographical-mw",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/state_installed_capacity_with_alloc_mw",
      canonical_id: "state-installed-capacity-allocated-mw",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/state_electricity_generation_mu",
      canonical_id: "state-electricity-generation-gwh",
      table_id: "energy.energy_generation",
    },
  ];

  it("registers all 8 PR 7a descriptors as canonical-backed", () => {
    for (const row of PR_7A) {
      expect(isCanonicalBacked(row.legacy_id)).toBe(true);
    }
  });

  it("wires every PR 7a legacy slug to the expected canonical id + table", () => {
    for (const row of PR_7A) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d, `descriptor missing for ${row.legacy_id}`).not.toBeNull();
      // PR 7a entries are all kind:"single" — narrow before accessing the
      // single-variant canonical_indicator_id field.
      expect(d!.kind, `descriptor for ${row.legacy_id} must be kind:single`).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id).toBe(row.canonical_id);
      }
      expect(d!.table_id).toBe(row.table_id);
    }
  });

  it("every PR 7a meta block declares entity_kind=state + unit=MW|GWh", () => {
    for (const row of PR_7A) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.id).toBe(row.canonical_id);
      expect(d.meta.entity_kind).toBe("state");
      expect(["MW", "GWh"]).toContain(d.meta.unit);
      // Title must be non-empty (rail-budget compliance is asserted by
      // topic-titles-rail-fit elsewhere; here we only require presence).
      expect(d.meta.title.length).toBeGreaterThan(0);
    }
  });

  it("snapshot-fuel descriptors (#1-#5) carry time_grain=month + comparability=snapshot_only", () => {
    const snapshot_ids = PR_7A.filter((r) =>
      r.canonical_id.startsWith("state-installed-capacity-snapshot-mw-"),
    );
    expect(snapshot_ids).toHaveLength(5);
    for (const row of snapshot_ids) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.time_grain).toBe("month");
      expect(d.meta.comparability).toBe("comparable_across_states_snapshot_only");
      expect(d.meta.attribution_geography).toBe("where_allocated");
    }
  });

  it("time-series descriptors (#6-#8) carry time_grain=fiscal_year + comparability=across_states_and_time", () => {
    const fy_ids = PR_7A.filter((r) =>
      [
        "state-installed-capacity-geographical-mw",
        "state-installed-capacity-allocated-mw",
        "state-electricity-generation-gwh",
      ].includes(r.canonical_id),
    );
    expect(fy_ids).toHaveLength(3);
    for (const row of fy_ids) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.comparability).toBe("comparable_across_states_and_time");
    }
  });

  it("allocated-shares descriptor (#7) declares FY15 series_break for the RBI splice", () => {
    const d = getCanonicalDescriptor("energy/state_installed_capacity_with_alloc_mw")!;
    expect(d.meta.series_breaks).toBeDefined();
    expect(d.meta.series_breaks!.length).toBeGreaterThanOrEqual(1);
    const fy15 = d.meta.series_breaks!.find((b) => b.at_time === "2015-04");
    expect(fy15, "FY15 series_break missing").toBeDefined();
    expect(fy15!.kind).toBe("definition_change");
    expect(fy15!.note).toMatch(/RBI/i);
  });

  it("generation descriptor (#8) keeps GWh unit (NOT MU) per ADR-0030 unit normalisation", () => {
    const d = getCanonicalDescriptor("energy/state_electricity_generation_mu")!;
    expect(d.meta.unit).toBe("GWh");
    expect(d.meta.notes).toMatch(/MU/);
  });

  it("every PR 7a legacy_id is a distinct entry in CANONICAL_BACKED_INDICATORS (no duplicates)", () => {
    const slugs = CANONICAL_BACKED_INDICATORS.map((d) => d.legacy_artifact_id);
    const uniq = new Set(slugs);
    expect(uniq.size).toBe(slugs.length);
    // And: every PR 7a slug is present at least once.
    for (const row of PR_7A) {
      expect(slugs).toContain(row.legacy_id);
    }
  });
});

describe("canonicalEntityToLegacy — entity-id translation", () => {
  it("strips IN- prefix from state ids", () => {
    expect(canonicalEntityToLegacy("IN-S22")).toBe("S22");
    expect(canonicalEntityToLegacy("IN-U08")).toBe("U08");
    expect(canonicalEntityToLegacy("IN-S01")).toBe("S01");
  });

  it("passes bare IN national aggregate through unchanged", () => {
    expect(canonicalEntityToLegacy("IN")).toBe("IN");
  });

  it("passes already-bare ECI codes through unchanged", () => {
    // Defensive — should never happen on canonical input, but the helper
    // must be idempotent so a double-call is harmless.
    expect(canonicalEntityToLegacy("S22")).toBe("S22");
  });

  it("passes unrecognised shapes through (no throw)", () => {
    expect(canonicalEntityToLegacy("foo")).toBe("foo");
    expect(canonicalEntityToLegacy("")).toBe("");
  });
});

describe("buildIndicatorArtifact — canonical rows → legacy IndicatorArtifact", () => {
  const OBS_ROWS = [
    { entity_id: "IN", period_label: "2013-04", value_numeric: 135453, source_id: "src-rbi" },
    { entity_id: "IN", period_label: "2024-04", value_numeric: 250070, source_id: "src-rbi" },
    { entity_id: "IN", period_label: "2025-04", value_numeric: 245416, source_id: "src-iced" },
    { entity_id: "IN-S22", period_label: "2013-04", value_numeric: 13522, source_id: "src-rbi" },
    { entity_id: "IN-S22", period_label: "2024-04", value_numeric: 20211, source_id: "src-rbi" },
    { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
  ];
  const SRC_ROWS = [
    {
      source_id: "src-iced",
      producer: "NITI Aayog",
      title: "India Climate & Energy Dashboard",
      vintage: "FY 2024-25",
      url_main: "https://iced.niti.gov.in/",
    },
    {
      source_id: "src-rbi",
      producer: "Reserve Bank of India",
      title: "Handbook of Statistics on Indian States",
      vintage: "2024-25",
      url_main: "https://rbi.org.in/handbook",
    },
  ];

  it("maps canonical entity_ids to legacy form (strips IN-)", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    const entities = new Set(a.rows.map((r) => r.entity_id));
    expect(entities.has("IN")).toBe(true);
    expect(entities.has("S22")).toBe(true);
    expect(entities.has("IN-S22")).toBe(false);
  });

  it("maps period_label → time and value_numeric → value", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    const tn_2025 = a.rows.find((r) => r.entity_id === "S22" && r.time === "2025-04");
    expect(tn_2025?.value).toBe(20211);
  });

  it("derives coverage.temporal from min/max time across rows", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.coverage.temporal).toBe("2013-04 to 2025-04");
    expect(a.coverage.admin_level).toBe("state");
  });

  it("collapses to a single period when all rows share the same time", () => {
    const single = OBS_ROWS.filter((r) => r.period_label === "2025-04");
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, single, SRC_ROWS);
    expect(a.coverage.temporal).toBe("2025-04");
  });

  it("emits one IndicatorSource per joined source row, with empty fetched_at", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.sources).toHaveLength(2);
    const titles = a.sources.map((s) => s.name);
    expect(titles).toContain("India Climate & Energy Dashboard (FY 2024-25)");
    expect(titles).toContain("Handbook of Statistics on Indian States (2024-25)");
    for (const s of a.sources) {
      expect(s.fetched_at).toBe("");
      expect(typeof s.url).toBe("string");
    }
  });

  it("passes the descriptor's IndicatorMeta block through verbatim", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.indicator).toBe(PEAK_DEMAND_DESCRIPTOR.meta);
  });

  it("synthesises a stub methodology block compatible with AboutThisData", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.methodology).toBeDefined();
    expect(a.methodology!.documentation_status).toBe("stub");
    expect(a.methodology!.definition.length).toBeGreaterThan(0);
    expect(a.methodology!.publisher_methodology_url).toBeNull();
    expect(a.methodology!.methodology_breaks).toEqual([]);
  });

  // PR-E (AboutThisData RPO caveat surfacing): `descriptor.caveats` is the
  // allowlist-authored bullet list lifted into `methodology.known_caveats[]`
  // so AboutThisData.svelte's "Known caveats" section can render it.
  // Descriptors without `caveats` populated keep the legacy empty-array
  // behaviour (no surface change for the ~30 non-caveat-carrying entries).
  it("emits an empty known_caveats array when the descriptor declares no caveats", () => {
    // PEAK_DEMAND_DESCRIPTOR carries no `caveats` field (commit-1 baseline).
    expect(PEAK_DEMAND_DESCRIPTOR.caveats).toBeUndefined();
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.methodology!.known_caveats).toEqual([]);
  });

  it("copies descriptor.caveats verbatim into methodology.known_caveats", () => {
    const with_caveats: CanonicalIndicatorDescriptor = {
      ...PEAK_DEMAND_DESCRIPTOR,
      caveats: [
        "First caveat — top of the bullet list.",
        "Second caveat — preserves declaration order.",
      ],
    } as CanonicalIndicatorDescriptor;
    const a = buildIndicatorArtifact(with_caveats, OBS_ROWS, SRC_ROWS);
    expect(a.methodology!.known_caveats).toEqual([
      "First caveat — top of the bullet list.",
      "Second caveat — preserves declaration order.",
    ]);
  });

  it("treats descriptor.caveats as defensive-copy (mutating the artifact does not back-mutate the descriptor)", () => {
    const original_caveats = ["caveat A", "caveat B"];
    const with_caveats: CanonicalIndicatorDescriptor = {
      ...PEAK_DEMAND_DESCRIPTOR,
      caveats: original_caveats,
    } as CanonicalIndicatorDescriptor;
    const a = buildIndicatorArtifact(with_caveats, OBS_ROWS, SRC_ROWS);
    a.methodology!.known_caveats.push("post-build mutation");
    expect(original_caveats).toEqual(["caveat A", "caveat B"]);
  });

  it("declares schema v4.4 + OGL-IN-1.0 license", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.$schema_version).toBe("4.4");
    expect(a.license.id).toBe("OGL-IN-1.0");
    expect(a.license.redistributable).toBe(true);
  });

  it("handles an empty result set without throwing", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, [], []);
    expect(a.rows).toEqual([]);
    expect(a.sources).toEqual([]);
    expect(a.coverage.temporal).toBe("");
  });
});

describe("loadIndicatorFromCanonical — DuckDB-WASM round-trip (loader)", () => {
  it("registers the fact-table and sources table before querying", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    const registered = mockedRegister.mock.calls.map((c) => c[0]);
    expect(registered).toContain("energy.energy_demand_supply");
    expect(registered).toContain("taxonomy.sources");
  });

  it("queries the fact-table view (last segment of table_id) filtered by indicator_id", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    const firstSql = mockedQuery.mock.calls[0][0] as string;
    expect(firstSql).toMatch(/FROM\s+energy_demand_supply/);
    expect(firstSql).toMatch(/indicator_id\s*=\s*'state-peak-electricity-demand-mw'/);
  });

  it("returns an empty artifact when the fact-table has no rows for this indicator", async () => {
    mockedQuery.mockResolvedValueOnce([]); // observation query
    const out = await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    expect(out.rows).toEqual([]);
    expect(out.sources).toEqual([]);
    // Second (sources) query is SKIPPED when there are no source_ids to look up.
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("issues the sources query when observation rows reference at least one source_id", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
      ])
      .mockResolvedValueOnce([
        { source_id: "src-iced", producer: "NITI", title: "ICED", vintage: "FY25", url_main: "https://example/" },
      ]);
    const out = await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    expect(mockedQuery).toHaveBeenCalledTimes(2);
    const secondSql = mockedQuery.mock.calls[1][0] as string;
    expect(secondSql).toMatch(/FROM\s+sources/);
    expect(secondSql).toMatch(/'src-iced'/);
    expect(out.sources).toHaveLength(1);
    expect(out.rows[0].entity_id).toBe("S22");
  });
});

describe("loadIndicatorIfCanonical — single dispatch entry-point", () => {
  it("returns null for legacy-backed artifacts (caller falls back to fetch)", async () => {
    const out = await loadIndicatorIfCanonical("energy/some_legacy_shard");
    expect(out).toBeNull();
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegister).not.toHaveBeenCalled();
  });

  it("returns the canonical artifact for an allowlisted id", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
      ])
      .mockResolvedValueOnce([
        { source_id: "src-iced", producer: "NITI", title: "ICED", vintage: "FY25", url_main: "https://example/" },
      ]);
    const out = await loadIndicatorIfCanonical("energy/state_peak_electricity_demand_mw");
    expect(out).not.toBeNull();
    expect(out!.indicator.id).toBe("state-peak-electricity-demand-mw");
    expect(out!.rows[0].entity_id).toBe("S22");
  });
});

describe("legacyArtifactIdFromPath — DATA_BASE path → catalogue artifact id", () => {
  it("extracts <topic>/<id> from a well-formed legacy path", () => {
    expect(legacyArtifactIdFromPath("/indicators/in/energy/state_peak_electricity_demand_mw.json"))
      .toBe("energy/state_peak_electricity_demand_mw");
    expect(legacyArtifactIdFromPath("/indicators/in/demography/state_population_lakhs.json"))
      .toBe("demography/state_population_lakhs");
  });

  it("returns the empty string for paths outside the indicators tree", () => {
    expect(legacyArtifactIdFromPath("/data/indicators/in/energy/foo.json")).toBe("");
    expect(legacyArtifactIdFromPath("/indicators/us/energy/foo.json")).toBe("");
    expect(legacyArtifactIdFromPath("/indicators/in/energy/foo.csv")).toBe("");
    expect(legacyArtifactIdFromPath("")).toBe("");
    expect(legacyArtifactIdFromPath("nonsense")).toBe("");
  });
});

describe("loadIndicator — universal entry-point (Phase B-extension)", () => {
  it("returns the canonical artifact for an allowlisted path (no fetchIndicator call)", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
      ])
      .mockResolvedValueOnce([
        { source_id: "src-iced", producer: "NITI", title: "ICED", vintage: "FY25", url_main: "https://example/" },
      ]);
    const out = await loadIndicator("/indicators/in/energy/state_peak_electricity_demand_mw.json");
    expect(out.indicator.id).toBe("state-peak-electricity-demand-mw");
    expect(out.rows[0].entity_id).toBe("S22");
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("falls through to fetchIndicator for a non-allowlisted legacy path", async () => {
    const legacy: import("../indicators").IndicatorArtifact = {
      $schema_version: "4.4",
      indicator: {
        id: "state-population-lakhs",
        title: "Population (lakhs)",
        unit: "lakhs",
        entity_kind: "state",
        time_grain: "annual",
      } as any,
      coverage: { temporal: "2011" } as any,
      license: { id: "OGL-IN-1.0", redistributable: true } as any,
      methodology: {} as any,
      sources: [],
      rows: [],
    } as any;
    mockedFetch.mockResolvedValueOnce(legacy);
    const out = await loadIndicator("/indicators/in/demography/state_population_lakhs.json");
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(mockedFetch).toHaveBeenCalledWith("/indicators/in/demography/state_population_lakhs.json");
    expect(out).toBe(legacy);
    expect(mockedQuery).not.toHaveBeenCalled();
  });

  it("falls through to fetchIndicator for a path that doesn't match the indicators shape", async () => {
    const legacy: import("../indicators").IndicatorArtifact = { rows: [] } as any;
    mockedFetch.mockResolvedValueOnce(legacy);
    const out = await loadIndicator("/data/elections/in/le/maharashtra/2024-11/results.json");
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(out).toBe(legacy);
  });
});

describe("PR 7c.5 — additive reader-switch for 7 P.1.B simple energy descriptors", () => {
  // Contract tests for the 7 simple `kind: "single"` descriptors wired in
  // PR 7c.5. Same shape as PR 7a invariants — catches accidental future
  // edits to the wrong row or a typo'd table_id.

  const PR_7C5_SIMPLE: ReadonlyArray<{
    legacy_id: string;
    canonical_id: string;
    table_id: string;
  }> = [
    {
      legacy_id: "energy/state_power_requirement_mu",
      canonical_id: "state-electricity-requirement-mu",
      table_id: "energy.energy_demand_supply",
    },
    {
      legacy_id: "energy/state_power_availability_mu",
      canonical_id: "state-electricity-availability-mu",
      table_id: "energy.energy_demand_supply",
    },
    {
      legacy_id: "energy/state_per_capita_availability_kwh",
      canonical_id: "state-per-capita-electricity-availability-kwh",
      table_id: "energy.energy_demand_supply",
    },
    {
      legacy_id: "energy/state_acs_arr_gap_inr_per_kwh",
      canonical_id: "state-acs-arr-gap-inr-per-kwh",
      table_id: "energy.energy_distribution_performance",
    },
    {
      legacy_id: "energy/state_distribution_billing_efficiency_pct",
      canonical_id: "state-distribution-efficiency-pct-billing",
      table_id: "energy.energy_distribution_performance",
    },
    {
      legacy_id: "energy/state_distribution_collection_efficiency_pct",
      canonical_id: "state-distribution-efficiency-pct-collection",
      table_id: "energy.energy_distribution_performance",
    },
    {
      legacy_id: "energy/state_distribution_td_loss_pct",
      canonical_id: "state-distribution-efficiency-pct-td-loss",
      table_id: "energy.energy_distribution_performance",
    },
  ];

  it("registers all 7 PR 7c.5 simple descriptors as canonical-backed", () => {
    for (const row of PR_7C5_SIMPLE) {
      expect(isCanonicalBacked(row.legacy_id), `not allowlisted: ${row.legacy_id}`).toBe(true);
    }
  });

  it("wires every PR 7c.5 simple slug to the expected canonical id + table (kind:single)", () => {
    for (const row of PR_7C5_SIMPLE) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d, `descriptor missing for ${row.legacy_id}`).not.toBeNull();
      expect(d!.kind, `descriptor for ${row.legacy_id} must be kind:single`).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id).toBe(row.canonical_id);
      }
      expect(d!.table_id).toBe(row.table_id);
    }
  });

  it("every PR 7c.5 simple meta block declares entity_kind=state + a citizen-readable unit", () => {
    for (const row of PR_7C5_SIMPLE) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.id).toBe(row.canonical_id);
      expect(d.meta.entity_kind).toBe("state");
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.attribution_geography).toBe("where_administered");
      expect(d.meta.unit.length).toBeGreaterThan(0);
      expect(d.meta.title.length).toBeGreaterThan(0);
    }
  });

  it("ACS-ARR descriptor flags both sign convention and policy goal in description (Jony)", () => {
    const d = getCanonicalDescriptor("energy/state_acs_arr_gap_inr_per_kwh")!;
    // The brief calls out the sign-convention copy fix: positive = loses
    // money + closed by tariff hike / loss reduction / state subsidy.
    expect(d.meta.description).toMatch(/positive/i);
    expect(d.meta.description).toMatch(/tariff|subsidy|loss reduction/i);
  });
});

describe("PR 7c.5 — RPO compliance facet-multiplexed descriptor", () => {
  // The first kind:"facet-multiplexed" descriptor. Verifies the
  // discriminated-union dispatch, hyphenated legacy facet labels,
  // single-SQL fan-in, and child-sourced provenance.

  const RPO_DESCRIPTOR = getCanonicalDescriptor("energy/state_rpo_compliance_pct")!;

  it("registers the RPO legacy slug as canonical-backed", () => {
    expect(isCanonicalBacked("energy/state_rpo_compliance_pct")).toBe(true);
  });

  it("descriptor is kind:facet-multiplexed with parent + 3 children", () => {
    expect(RPO_DESCRIPTOR.kind).toBe("facet-multiplexed");
    if (RPO_DESCRIPTOR.kind === "facet-multiplexed") {
      expect(RPO_DESCRIPTOR.canonical_parent_indicator_id).toBe("state-rpo-compliance-pct");
      expect(RPO_DESCRIPTOR.table_id).toBe("energy.energy_distribution_performance");
      expect(RPO_DESCRIPTOR.facet_axis_id).toBe("rpo_segment");
      expect(RPO_DESCRIPTOR.facet_values).toHaveLength(3);
      const child_ids = RPO_DESCRIPTOR.facet_values.map((fv) => fv.canonical_child_id);
      expect(child_ids).toEqual([
        "state-rpo-compliance-pct-solar",
        "state-rpo-compliance-pct-non-solar",
        "state-rpo-compliance-pct-total",
      ]);
    }
  });

  it("uses HYPHENATED legacy facet labels (citizen-readable, NOT snake_case canonical value_id)", () => {
    if (RPO_DESCRIPTOR.kind !== "facet-multiplexed") {
      throw new Error("RPO descriptor must be facet-multiplexed");
    }
    const labels = RPO_DESCRIPTOR.facet_values.map((fv) => fv.legacy_facet_label);
    expect(labels).toEqual(["solar", "non-solar", "total"]);
    // Defensive: explicitly assert non-solar is hyphenated, NOT underscored
    // (the canonical dimension_values.rpo_segment uses "non_solar"; the
    // legacy shard + frontend renderer use "non-solar"). Easy regression
    // to introduce by copy-paste from the catalogue row.
    expect(labels).toContain("non-solar");
    expect(labels).not.toContain("non_solar");
  });

  it("[mandatory] adapter fuses 3 child rows into one artifact with hyphenated facet labels", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        // 3 children × 1 state × 1 FY
        {
          indicator_id: "state-rpo-compliance-pct-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 95.5,
          source_id: "src-rpo",
        },
        {
          indicator_id: "state-rpo-compliance-pct-non-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 88.2,
          source_id: "src-rpo",
        },
        {
          indicator_id: "state-rpo-compliance-pct-total",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 92.1,
          source_id: "src-rpo",
        },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-rpo",
          producer: "NITI Aayog",
          title: "India Climate & Energy Dashboard — RPO",
          vintage: "FY 2024-25",
          url_main: "https://iced.niti.gov.in/",
        },
      ]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    // (1) hyphenated facet label survives end-to-end:
    expect(result.rows.some((r) => r.facet === "non-solar"), "row.facet must be hyphenated 'non-solar'").toBe(true);
    expect(result.rows.some((r) => r.facet === "solar")).toBe(true);
    expect(result.rows.some((r) => r.facet === "total")).toBe(true);
    // No row should accidentally carry the snake-case canonical value_id:
    expect(result.rows.some((r) => r.facet === "non_solar")).toBe(false);
  });

  it("[mandatory] issues ONE SQL with `indicator_id IN (` covering all 3 children", async () => {
    mockedQuery.mockResolvedValueOnce([]); // no observations, sources query is skipped
    await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    // Exactly one query (sources skipped because no source_ids harvested):
    expect(mockedQuery).toHaveBeenCalledTimes(1);
    const sql = mockedQuery.mock.calls[0][0] as string;
    expect(sql).toMatch(/indicator_id\s+IN\s*\(/);
    expect(sql).toMatch(/'state-rpo-compliance-pct-solar'/);
    expect(sql).toMatch(/'state-rpo-compliance-pct-non-solar'/);
    expect(sql).toMatch(/'state-rpo-compliance-pct-total'/);
    expect(sql).toMatch(/FROM\s+energy_distribution_performance/);
  });

  it("[mandatory] aggregates sources from CHILD rows (parent has source_id=null per D29)", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        {
          indicator_id: "state-rpo-compliance-pct-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 95.5,
          source_id: "src-rpo",
        },
        {
          indicator_id: "state-rpo-compliance-pct-non-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 88.2,
          source_id: "src-rpo",
        },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-rpo",
          producer: "NITI Aayog",
          title: "ICED RPO",
          vintage: "FY 2024-25",
          url_main: "https://iced.niti.gov.in/",
        },
      ]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    expect(result.sources).toHaveLength(1);
    expect(result.sources[0].name).toBe("ICED RPO (FY 2024-25)");
    // Sources SQL was the second call and queried by harvested child
    // source_ids — not by parent (which has source_id=null and would
    // produce zero rows).
    const sourcesSql = mockedQuery.mock.calls[1][0] as string;
    expect(sourcesSql).toMatch(/'src-rpo'/);
  });

  it("[mandatory] derives coverage.temporal from min/max across ALL fused child rows", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        // Different children cover different FYs — the parent's coverage
        // must be the UNION (min across children → max across children).
        {
          indicator_id: "state-rpo-compliance-pct-solar",
          entity_id: "IN-S22",
          period_label: "2018-04",
          value_numeric: 70.0,
          source_id: "src-rpo",
        },
        {
          indicator_id: "state-rpo-compliance-pct-non-solar",
          entity_id: "IN-S22",
          period_label: "2020-04",
          value_numeric: 80.0,
          source_id: "src-rpo",
        },
        {
          indicator_id: "state-rpo-compliance-pct-total",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 92.0,
          source_id: "src-rpo",
        },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-rpo",
          producer: "NITI",
          title: "ICED",
          vintage: "FY25",
          url_main: "https://example/",
        },
      ]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    expect(result.coverage.temporal).toBe("2018-04 to 2024-04");
  });

  it("artifact's indicator.id is the parent (NOT any child); meta block carries parent fields", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    expect(result.indicator.id).toBe("state-rpo-compliance-pct");
    expect(result.indicator.unit).toBe("%");
    expect(result.indicator.entity_kind).toBe("state");
  });

  it("loadIndicatorIfCanonical dispatches the facet-multiplexed slug to the canonical path", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    const out = await loadIndicatorIfCanonical("energy/state_rpo_compliance_pct");
    expect(out).not.toBeNull();
    expect(out!.indicator.id).toBe("state-rpo-compliance-pct");
  });
});

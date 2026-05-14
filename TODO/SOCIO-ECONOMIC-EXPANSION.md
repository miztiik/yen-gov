# yen-gov — Socio-Economic Expansion Plan

**Last Updated**: 2026-05-10
**Status**: Proposal. **No code or schema changes until §6 here is signed off by the user.**
**Authority**: Non-authoritative scratchpad (CLAUDE.md §3). Promote agreed pieces into `docs/architecture/` and split into per-phase ADRs as we execute.
**Correction level**: 5 (core data model + scope evolution). Per CLAUDE.md §6, **design consultation only — pause work** until §6 is approved.

> **Trigger**: User pointed at [`yashveeeeeeer/india-geodata`](https://github.com/yashveeeeeeer/india-geodata) — specifically `data/energy/power-plants/{INDIA_ENERGY_PLANTS.geojson, metadata.json}` — and asked: how would we consume it, what can we learn from their metadata schema, and how do we evolve yen-gov from "elections-only" to a layered socio-economic atlas (energy, healthcare, education, roads, taxes, GDP, GST flows, welfare spending) where everything can be choropleth-overlaid on state/district/AC boundaries and color-coded by ruling party over time.

---

## 1. What `india-geodata` actually is (verified facts)

A CC BY 4.0 aggregator repo on GitHub Pages. ~1,800 files across 14 categories. Small files in-repo under `data/<category>/<dataset>/`; large files in GitHub Releases (one tag per dataset, e.g. `admin/states`, `environment/forests`).

**Categories relevant to us** (from the upstream `README.md`):

| Category          | Coverage                                                        | Format(s)        | Size    | Relevance                |
| ----------------- | --------------------------------------------------------------- | ---------------- | ------- | ------------------------ |
| `administrative/` | Country, States, Districts, Subdistricts, Blocks, Panchayats    | Parquet, PMTiles, GeoJSONL, SHP | ~27 GB  | Boundary canon (replaces parts of our current `tools/boundaries`) |
| `electoral/`      | Assembly + Parliamentary Constituencies                         | SHP, GeoJSON, Parquet, PMTiles  | ~300 MB | **Direct overlap** with our `S22-ac.geojson` etc. |
| `census/`         | 2011 admin units, Historical districts (1941–2024)              | Parquet, PMTiles, CSV           | ~1.1 GB | Demographic baseline for choropleths |
| `energy/`         | Power plants (coal, diesel, hydro)                              | GeoJSON          | ~128 KB | First socio-economic slice the user named |
| `healthcare/`     | Public health facilities (PHCs, CHCs, hospitals)                | GeoJSON          | ~47 MB  | Point-layer overlay |
| `education/`      | Schools, colleges, universities, kindergartens                  | GeoJSON          | ~49 MB  | Point-layer overlay |
| `infrastructure/` | PMGSY rural roads, NH, SOI/NIC/ML/Urban roads, Railways         | Parquet, PMTiles, GeoJSONL, SHP, GeoJSON | ~20 GB | Roads coverage metric (length per state) |
| `urban/`          | Municipal wards (28 cities), Slums, ULB boundaries              | GeoJSON, KML, Parquet, PMTiles  | ~430 MB | Sub-state granularity |
| `remote-sensing/` | VIIRS nightlights 2012–2024, WorldPop 2020                      | CSV, GeoJSON, GeoTIFF | ~370 MB | **Time-series proxy for development** — directly enables the user's "is this state doing better?" question |
| `external/`       | SHRUG (socioeconomic data, 500K villages, CC BY-NC-SA)          | external link    | —       | The big socioeconomic prize, but NC license — read-only/attribution-strict use |

**What is NOT there** (and we'd have to source ourselves):

- GDP / GSDP per state per year → MoSPI / RBI Handbook of Statistics on Indian States.
- Tax devolution (centre→state), GST collections per state → Finance Commission reports, GST Council, RBI State Finances.
- Welfare-program disbursement (PM-Kisan, MGNREGA wages, pensions, subsidies) → respective ministry dashboards / data.gov.in.
- Industry / GVA breakdowns → MoSPI National Accounts.

These are **all tabular, not spatial.** They join to states/districts by code, not geometry. That's a clean separation we should exploit (see §3).

## 2. What their `metadata.json` does that ours doesn't — and what to copy

Their per-dataset metadata (verified from `data/energy/power-plants/metadata.json`):

```json
{
  "name": "energy-power-plants",
  "title": "Power Plants",
  "description": "Point locations of power plants across India …",
  "category": "energy",
  "level": "power-plants",
  "coverage":          { "spatial": "India (national)", "temporal": "2019", "admin_level": null },
  "sources":           [ { "name": "Central Electricity Authority (CEA)", "url": "https://cea.nic.in/", "authority": "Ministry of Power" }, … ],
  "license":           { "id": "Unspecified", "name": "Unspecified", "url": null },
  "formats":           ["geojson"],
  "coordinate_system": "EPSG:4326",
  "storage":           { "repo_files": true, "release_tag": null },
  "last_updated":      "2026-03-15"
}
```

### How it differs from our `sources` (CLAUDE.md §12, ADR-0002)

| Field they have               | Do we have it? | Should we add it?                                                                 |
| ----------------------------- | -------------- | --------------------------------------------------------------------------------- |
| `sources[].url`               | ✅              | —                                                                                 |
| `sources[].name`, `.authority`| ❌              | **Yes, additive.** Human attribution is missing from our shape.                  |
| `sources[].fetched_at`        | ✅ (we have it) | They don't — but ours is the better fetch-provenance signal. **Keep.**           |
| `license { id, name, url }`   | ❌              | **Yes.** Critical for redistribution. Currently implicit/unstated per file.       |
| `coverage.spatial`            | partial (path) | **Yes.** Path conveys it for elections; needs an explicit field for non-electoral data. |
| `coverage.temporal`           | partial (event)| **Yes.** Year/range is needed for non-event datasets (energy, census, GDP).      |
| `coverage.admin_level`        | ❌              | **Yes.** Distinguishes "state-level GDP" from "district-level GDP".              |
| `coordinate_system`           | ❌              | **Yes**, on geo files. We assume EPSG:4326 — should be declared, not assumed.    |
| `last_updated`                | implicit (git) | **Optional.** Git already records this; only worth duplicating if consumers need it without git context. |

**Key insight**: their `sources[]` is *human attribution* ("CEA, Ministry of Power"). Ours is *fetch provenance* ("we hit this URL at this time"). **They're complementary, not competing.** Proposed shape (additive, schema minor bump):

```json
"sources": [
  {
    "url":        "https://cea.nic.in/wp-content/.../installed-capacity-2019.csv",
    "fetched_at": "2026-05-15T09:12:00Z",
    "name":       "Installed capacity report 2019",
    "authority":  "Central Electricity Authority, Ministry of Power"
  }
]
```

`name`/`authority` are optional; existing files keep validating. **No major bump needed.**

`license`, `coverage`, `coordinate_system` go in a new optional top-level `metadata` object — also additive, also minor. Existing election artifacts ignore it.

## 3. The architectural choice that matters most

**Two ways to bolt on socio-economic data:**

### Option Spatial-First (the india-geodata mental model)
Every dataset is a geographic feature collection. Power plants are points. Roads are lines. GDP-per-state is a polygon attribute. **All overlays compose at the map layer.** The choropleth IS the data model.

### Option Indicator-First (the dashboard mental model)
Every dataset is `(entity_id, time, indicator, value, unit)` — a long-form tabular fact table. State `S22` had `gsdp_inr_crore = 18,15,000` in `2024-25`. Power plants have a count, capacity-MW, etc. summarized to state. **Geometry is a separate, reusable lookup.** The choropleth is rendered by *joining* indicators to boundaries at view time.

| Dimension                  | Spatial-First                              | Indicator-First                                         |
| -------------------------- | ------------------------------------------ | ------------------------------------------------------- |
| Cross-indicator comparison | Painful (each dataset has its own attrs)   | Trivial (uniform schema)                                |
| Time series                | Awkward (one geojson per year)             | Native (`time` is a column)                             |
| Color-by-ruling-party      | Custom join per layer                      | Single join: indicator × `state_government_history`     |
| Point/line data (plants, roads) | Native                                | Need a sibling spatial table when geometry matters      |
| File size on Pages bundle  | Big (geometry repeats per snapshot)        | Small (geometry once, indicators tiny)                  |
| User's stated goal         | "layer on choropleths"                     | "see which state is doing better over time"             |

**Recommendation: Indicator-First as the primary model, with a spatial sidecar registry.** Geometry lives once under `datasets/boundaries/`. Indicators live under a new `datasets/indicators/` tier and join by the same `(country, state, district)` keys we already use for elections. Point/line data (power plants, hospitals, roads) goes under `datasets/features/` as GeoJSON when individual locations matter, but **also** rolls up into `indicators/` so the choropleth doesn't need to know about points.

This matches yen-gov's existing strength: **hierarchical identifiers (ECI/LGD codes) as the join surface.**

---

## 4. Internal dialog

> Three voices: **Gregor (the architect — Enterprise Integration Patterns, "Pipes and Filters" guy)**, **U/X (a pragmatic UI/UX lead)**, **User (you, owner of yen-gov, building this for your own civic curiosity, with energy as the first non-electoral slice)**. The dialog is staged — they argue, we converge.

---

**User**: I want a tab next to "Elections" called Society or something. First slice is power plants. Eventually GDP, taxes, GST, hospitals, schools, roads. Layer all of it on the same map I already have. And colour the boundaries by who was in power. Tell me when something is being missed.

**Gregor**: Stop. Before you add a tab, decide whether your data model can answer the question *"is Tamil Nadu doing better than Karnataka on health since 2014?"* If the answer is "we'd have to load five GeoJSONs and reconcile their attribute schemas," your model is wrong. The right answer is one indicator table, joined to one geometry, filtered by time. That's [Canonical Data Model](https://www.enterpriseintegrationpatterns.com/patterns/messaging/CanonicalDataModel.html). Power plants can be points *and* an aggregate indicator. Don't pick.

**U/X**: I disagree on UX framing. Users don't think "indicator vs spatial." They think *layers*. They want a left rail with checkboxes — "Politics", "Energy", "Health", "Education", "Money in/out" — and toggling combines them. Whether the backing store is one fact table or twelve geojsons is invisible to them. So Gregor's model isn't wrong, but it's not the conversation that goes to the user.

**Gregor**: Granted. But invisible-to-the-user is not invisible-to-the-build. If you start with twelve GeoJSONs you will end up with twelve frontend code paths. Then someone asks "show GDP-per-capita coloured by who's in power" and you write a thirteenth. Pick the model now.

**User**: I hear "indicator-first." But power plants are real points with names. I want to click a dot and see "NTPC Vallur, 1500 MW, coal, commissioned 2014."

**Gregor**: Then power plants are *both*. The point dataset is a `feature` artifact; the rolled-up "MW per state by fuel type per year" is an `indicator` artifact. Same upstream source, two emit paths. Like Pipes and Filters with a tee. CLAUDE.md already has this discipline — `result.constituency.json` is the row, `result.summary.json` is the rollup. Same pattern.

**U/X**: That's good. Now: the political colouring. The user wants "colour-by-ruling-party-over-time". That is a temporal join, and you need a `state_government` timeline dataset. Who was CM, what party/alliance, from when to when. That's *itself* a new entity. And it has the same caveats as the party catalog: alliances drift, parties merge.

**User**: I have that data conceptually — TN has been DMK/AIADMK alternating, etc. I just need a place to put it.

**Gregor**: New schema: `state_government.schema.json`. Same pattern as `party.schema.json` but indexed by `(state, term_start, term_end)`. Point at the party using the existing party code. Then your "colour by who's in power" is a function `(state, date) → party_code`, evaluated at the chosen time slider position. Single source of truth.

**U/X**: From the UX side, the time slider is the second-most-important control after the layer toggles. Every indicator needs a time dimension or a "static / latest" flag. Don't ship an indicator that lies about its temporal coverage — show "2019 only" right on the legend, not buried in a tooltip.

**User**: How do we avoid the spaghetti where every layer has its own legend, scale, and tooltip?

**U/X**: Convention. Every indicator carries `{ unit, scale_hint, value_kind: "count|rate|share|currency|index", direction: "higher_is_better|lower_is_better|neutral" }`. The renderer picks the colour ramp from `direction` (sequential vs diverging) and the formatter from `value_kind`. If a contributor adds a new indicator and forgets these, schema validation rejects it. **The schema is the design system.**

**Gregor**: That's the right frame. Schema as the contract between the data producer and the chart code. Don't write per-indicator components. Write one `<IndicatorChoropleth>` and one `<IndicatorPointLayer>` driven by metadata.

**User**: What about licensing? `india-geodata` is CC BY 4.0 overall, but individual datasets vary — some say "Unspecified". I don't want a legal problem on a public Pages site.

**Gregor**: Provenance + license is non-negotiable. CLAUDE.md §12 already mandates `sources`. Extend it: every artifact also carries `license` (id from SPDX or a small allowed set: `CC0-1.0`, `CC-BY-4.0`, `CC-BY-NC-SA-4.0`, `ODbL-1.0`, `IndiaOGL`, `Unspecified`). The frontend filter has a "show only redistributable" toggle that drops anything `Unspecified` or `*-NC-*` from the public bundle by default. SHRUG is NC — it gets a "request access" link, not a bundle inclusion.

**U/X**: That's a wonderful UX detail too — "License: India OGL" badge on each layer. Builds trust.

**User**: One more — I don't want this to bloat the GitHub Pages bundle. It's already a static site.

**Gregor**: Three rules: (1) Indicators are tiny — a CSV/JSON of `(state, year, value)` for India is ~1 KB per indicator-year. Bundle them. (2) Points (plants, hospitals) — bundle if <5 MB compressed; lazy-load otherwise. (3) Polygons — never bundle full-resolution; use the simplification we already do in `tools/boundaries`, or PMTiles via `maplibre-gl` (already a frontend dep). For roads/buildings (multi-GB) — never bundle, link out.

**U/X**: And the navigation. Don't make a flat "Society" tab with a dropdown of 30 indicators. Group: **People** (population, literacy, health), **Money** (GSDP, taxes, GST, transfers, welfare), **Infrastructure** (energy, roads, schools, hospitals), **Politics** (the existing election work, plus the ruling-party timeline). Four pillars. User picks a pillar, then layers within it.

**User**: I like four pillars. And the existing "Elections" becomes the lead inside "Politics".

**Gregor**: One more thing — staging. Don't try to do all of this at once. The first non-electoral indicator is your forcing function. Pick one — power plants — and drive the schema through it end-to-end. Everything you're going to discover (license fields, coverage temporal, point-vs-rollup, colour-by-government overlay) gets shaken out on that one. Then the second indicator (say GSDP) takes a tenth of the time. By the fifth, the framework is mature.

**U/X**: Same on the UI side — ship power plants as both a point overlay and a "Installed MW per capita" choropleth. The two views proves the point/rollup duality is real, not theoretical.

**User**: Agreed. Phase it. Don't break the election story.

---

## 5. Synthesis — what the dialog converged on

1. **Indicator-first data model**, with optional point/line `feature` sidecars when individual geometry matters.
2. **Geometry lives once** under `datasets/boundaries/`; **indicators live under** new `datasets/indicators/`; **point/line features live under** new `datasets/features/`.
3. **Schema as design system** — every indicator carries `{ unit, value_kind, direction, scale_hint }` so the renderer is metadata-driven, not per-layer-coded.
4. **License is mandatory** on every artifact; bundle filters by license class.
5. **Time is a first-class dimension** on every indicator. Static datasets declare so explicitly.
6. **Ruling-party overlay** is its own entity (`state_government`) joined at view time — not pre-baked into every choropleth.
7. **Four-pillar navigation**: People / Money / Infrastructure / Politics. Elections is the lead inside Politics.
8. **One forcing-function dataset first** (power plants), end-to-end, before generalising.
9. **Bundle discipline**: indicators always bundled (small); points bundle if <5 MB; polygons via simplification or PMTiles; multi-GB never bundled.
10. **Adopt india-geodata's metadata vocabulary additively** — `name/authority` on sources, plus `license`, `coverage`, `coordinate_system` — without breaking existing election artifacts.

## 6. Locked decisions (signed off by user, 2026-05-10, autopilot mode)

| #   | Decision                                                                                                          | Outcome                                                                                                                                                                                                                                                                                          |
| --- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | Data model                                                                                                        | **Hybrid** — indicators primary, point/line features as sidecars where geometry matters.                                                                                                                                                                                                         |
| D2  | New repo tiers `datasets/indicators/`, `datasets/features/`, `datasets/governments/`                              | **Yes**, created on first-use.                                                                                                                                                                                                                                                                   |
| D3  | Schema metadata additions (`sources[].name/authority`, `license`, `coverage`, `coordinate_system`)                | **Yes, additive minor bumps**. Existing election artifacts keep validating; license becomes mandatory only on new non-election artifacts.                                                                                                                                                        |
| D4  | New schemas `indicator`, `state_government`, `feature_collection.metadata`                                        | **Yes.**                                                                                                                                                                                                                                                                                         |
| D5  | First socio-economic slice                                                                                        | **Energy / power plants.** Plus: every new dataset gets a research-notes entry (see [`docs/research/README.md`](../docs/research/README.md)) so future maintainers can find the upstream lineage and consider better sources (RBI for GSDP, CEA for energy, etc.).                                |
| D6  | Power-plants source                                                                                               | **Both.** Take india-geodata's GeoJSON as the immediate upstream (CC BY 4.0, attributed), keep a local copy under `datasets/features/in/energy/`. In parallel, research the CEA source files referenced in their metadata and, when a stable URL is confirmed, add it to the `sources` array.    |
| D7  | Migrate `tools/boundaries` to india-geodata releases?                                                             | **Defer.** Captured as a research item; not blocking.                                                                                                                                                                                                                                            |
| D8  | Frontend nav restructure                                                                                          | **Yes — elections is a subsystem of society/state/geography.** Four pillars: People / Money / Infrastructure / Politics. Existing election routes fold under `Politics/`. Restructure happens in Phase C, not before there is a non-election layer to motivate it.                                |
| D9  | License gating in the public bundle                                                                               | **Don't drop anything by default.** Show every layer with a clearly visible license badge. `Unspecified` is itself a label — not a reason to hide. Sort/prefer in this order: `CC0` ≻ `CC-BY-4.0` ≻ `India OGL` ≻ `ODbL` ≻ other open ≻ `Unspecified`. NC licenses (e.g. SHRUG) get a "non-commercial — see source" badge, ship as outbound link only (no bundled file). The frontend may offer a filter, but **the default is "show everything with provenance"**, not "hide".                                                                                                                                                                                                                              |
| D10 | SHRUG (CC BY-NC-SA)                                                                                               | **Link out only, never bundle.** Captured under D9.                                                                                                                                                                                                                                              |
| RP  | Ruling-party overlay (colour-by-government over time)                                                             | **Yes** — new `state_government.schema.json` with CM term records. Joined at view time via a time slider. **Colours are NOT hard-coded per party** (see Q3 below).                                                                                                                                |
| Q3  | Time resolution in `indicator.schema.json`                                                                        | **Accept all three** (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`); each indicator declares its `time_grain`.                                                                                                                                                                                                |
| SC  | Scope                                                                                                             | **Keep all phases A–G as listed in §7.** No drops.                                                                                                                                                                                                                                               |
| **C1** | **Party-colour system overhaul** (raised by user during sign-off)                                              | The current hand-curated `DEFAULT_PARTY_COLORS` map (frontend/src/lib/colors/parties.default.ts) does not scale to ~30 states × ~30 parties (~900 entries). Hash-into-10-colour fallback collides. **New direction**: deterministic OkLCh-spaced palette, generated at view time from the parties currently visible — same party always same hue, different parties guaranteed perceptual distance. Iconic colours (BJP saffron, INC blue, DMK red, AITC green) preserved as anchors. **Tracked separately as Phase C.0 — must land before Phase C nav restructure.** Detailed plan in [`TODO/PARTY-COLORS-REWORK.md`](PARTY-COLORS-REWORK.md). |

### Custom agents created for this work

The user requested specialist agents for the cross-disciplinary discussions this expansion triggers:

| Agent                | File                                       | Role                                                                                  |
| -------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------- |
| Gregor Hohpe         | `.github/agents/gregor-hohpe.agent.md`     | Software architecture, integration patterns, contracts-before-logic.                  |
| Fowler (Engineering) | `.github/agents/fowler.agent.md`           | Code-craft and evolutionary engineering — refactoring, TDD, tidy-first, expand–migrate–contract (Fowler + Beck). |
| Jony (UI/UX)         | `.github/agents/jony.agent.md`             | Information architecture, layered map UX, gesture/interaction craft (Ive + Brichter). |
| Citizen User         | `.github/agents/citizen-user.agent.md`     | The non-technical Indian citizen who actually uses yen-gov to make sense of governance.|
| Hans (Governance)    | `.github/agents/hans.agent.md`             | Indian fiscal federalism + global data-communication discipline (Rosling + Roy + Bhattacharya). |
| Max (Indicator Scout)| `.github/agents/max.agent.md`              | OWID-style coverage strategy — what indicators to acquire, from where, why (Roser + Ritchie). Upstream of Hans. |

These can be invoked from the Governance panel (or directly via `@<agent>`) for any ongoing dataset or design question.

---

### Research notes

A new `docs/research/` tier captures one note per upstream/topic so future work isn't re-research:

- `docs/research/README.md` — index + conventions.
- `docs/research/india-geodata.md` — what we adopted, what we left, attribution requirements.
- `docs/research/energy-power-plants.md` — CEA vs india-geodata vs others; what we picked and why.
- `docs/research/state-gdp-rbi.md` — RBI Handbook of Statistics on Indian States as the canonical GSDP source.
- `docs/research/healthcare-facilities.md` — NIC HealthGIS / planemad / OSM facility data lineage.
- `docs/research/state-government-history.md` — verification sources for the ruling-party timeline.
- `docs/research/license-handling.md` — how D9 is implemented end-to-end.

---

## Open gap — Union (Centre's own) deficit indicators ✅ SHIPPED

**Raised by**: Hans (Governance) on 2026-05-14 during the Step B fiscal-actor rename review (ADR-0025). **Status**: ✅ shipped 2026-05-14 in branch `feat/rbi-hbs-ie-union-deficits` — adapter `backend/yen_gov/sources/rbi_hbs_ie_centre_deficits/`, four `fiscal/union_*_deficit` artifacts (FY1986-87 → FY2025-26 BE, 40 years × 4 indicators), reusing the AppT1 parser. Verified all 4 indicator columns (including `Primary Revenue Deficit`) exist in T89 — actually 8 indicator columns total, 4 not shipped (Net Fiscal Deficit, Net Primary Deficit, Drawdown of Cash Balances, Net RBI Credit). The caveat copy below is now obsolete; remove from any frontend surface that adopted it.

The historical context below is preserved verbatim for ADR/audit traceability.

**The asymmetry to fix.** After Step B (ADR-0025) yen-gov ships:

- Four `fiscal/centre_transfers_to_states_*` indicators — Centre as benefactor (resources flowing OUT to states).
- Four `fiscal/states_combined_*_deficit` indicators — states as the borrowing actor.

**Nothing about the Centre's OWN borrowing.** A citizen looking at our pages right now concludes: states run deficits; Centre sends money. That's the Factfulness "Blame instinct" failure mode — the data architecture itself misframes responsibility. In FY24 the Union Government's gross fiscal deficit was ~5.6% of GDP; states-combined was ~3.2%. The Centre's deficit was nearly double the states-combined and we don't show it.

**Source identified — RBI HBS-IE 2024-25, Table 89: "Key Deficit Indicators of the Central Government"**.

- Landing page: `https://rbi.org.in/Scripts/PublicationsView.aspx?id=23263`
- Direct XLSX (12 kb): `https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/89T_29082025E8B3FAE53E854131998A98825CE0DAEA.XLSX`
- Sister table (states): Table 96 "Key Deficit Indicators of the State Governments" — same publication, parallel structure. T96 is the HBS-IE-vintage equivalent of the RBI Appendix T1 our `rbi_appendix_deficits` adapter already parses.

**Proposed indicators (Step C scope, four artifacts):**

- `fiscal/union_gross_fiscal_deficit`
- `fiscal/union_revenue_deficit`
- `fiscal/union_primary_deficit`
- `fiscal/union_primary_revenue_deficit` *(verify column exists in T89 before committing)*

**Adapter strategy.** New `backend/yen_gov/sources/rbi_hbs_ie_centre_deficits/` adapter, structured as a sibling of `rbi_appendix_deficits`:

- Same XLSX shape pattern (Statement-style sheet with FY columns, deficit-indicator rows).
- Same Accounts/RE/BE qualifier-preference logic; can likely reuse the existing `parse_workbook` from `rbi_appendix_deficits.parsers` with an indicator-id remap.
- Independent download URL pinning (HBS-IE editions ship annually; the document hash in the URL changes per edition).
- Coverage: HBS-IE typically publishes from FY51 onwards (much deeper than App T1's FY08 start). If true this also unlocks an optional Step C+ to extend states-combined deficits backward via T96.

**Why deferred from the rename branch.** The rename branch (ADR-0025) is mechanical and atomic — eight name changes + their references. Adding a new adapter, four new dataset artifacts, schema-validation pass, and frontend wiring is a separate concern. ADR-0025 names this gap and points here; the next branch closes it.

**Caveat copy that should land on any page surfacing the existing four `states_combined_*_deficit` indicators until Step C ships:**

> "Shows states-combined fiscal stress only. The Union Government's own fiscal deficit (currently ~5.6% of GDP, larger than the states-combined ~3.2%) will be added in a future update. See [TODO/SOCIO-ECONOMIC-EXPANSION.md](TODO/SOCIO-ECONOMIC-EXPANSION.md) §Open gap."



## 7. Phased work (only after §6 sign-off)

### Phase A — Schema & layout foundations (Level 4)

A1. Add `metadata` block (license, coverage, coordinate_system) and `sources[].name/authority` to schemas — minor bumps with `x-changelog` entries.
A2. New schemas:
  - `datasets/schemas/indicator.schema.json` (the long-form fact-table shape: `entity_kind`, `entity_id`, `time`, `value`, `unit`, `value_kind`, `direction`, `scale_hint`, `notes`).
  - `datasets/schemas/state_government.schema.json` (CM term records pointing at party_code).
  - `datasets/schemas/feature_collection.metadata.schema.json` (sidecar for non-election GeoJSONs, parallel to `boundary.sources.schema.json`).
A3. New repo tiers: `datasets/indicators/`, `datasets/features/`, `datasets/governments/`. Empty stubs forbidden — created when first artifact lands.
A4. Update `docs/architecture/data-model.md`, `docs/concepts/data-provenance.md`, `docs/reference/schemas.md`.
A5. Validator: indicators sanity (units known, value_kind/direction enums, time format).
A6. ADR for the indicator-first decision (this counts as cross-cutting per CLAUDE.md §1.4 — it's not contained to one subsystem).

**Definition of done**: schemas pass meta-validation; existing election artifacts still validate; new tiers documented; CI green.

### Phase B — Power plants forcing function (Level 3)

B1. New backend module `backend/yen_gov/sources/india_geodata/` — fetches `data/energy/power-plants/INDIA_ENERGY_PLANTS.geojson` + `metadata.json`, validates licence, emits:
  - `datasets/features/in/energy/power-plants.geojson` (+ `.metadata.json` sidecar with `sources` carrying both india-geodata and CEA upstream).
  - `datasets/indicators/in/energy/installed_mw_by_state.json` (rolled up by state code).
B2. CLI: `yen-gov ingest india-geodata energy/power-plants`.
B3. State-government timeline (hand-authored): `datasets/governments/in/states/S22.json` (TN, last 25 years). One state to start.
B4. Live test against the GitHub raw URL.

**Definition of done**: two artifacts emitted from one upstream; both validate; one state's government timeline present.

### Phase C — Frontend layered map (Level 4)

C1. Restructure routes into four pillars; existing election routes move under `Politics/`.
C2. Generic `<IndicatorChoropleth>` and `<IndicatorPointLayer>` components driven entirely by indicator metadata.
C3. Time slider; ruling-party overlay (boundary stroke colour by `state_government` at selected date).
C4. Layer rail: People / Money / Infra / Politics with checkboxes.
C5. License badge on every active layer; license-filter toggle.
C6. Playwright smoke covers the layered view.

**Definition of done**: power-plants point layer + installed-MW choropleth + ruling-party stroke render together at 60fps on a real machine.

### Phase D — Second indicator (validates the framework)

D1. Pick GSDP per state per year (MoSPI). Pure indicator, no points. Should take ~1/5 the effort of Phase B if the framework is right.
D2. If it doesn't, the framework is wrong — fix at Phase A level, don't paper over.

### Phase E — Healthcare facilities + education facilities

E1. Same shape as power plants (point + rollup). Reuses the framework.
E2. Hospitals-per-100k-population is the choropleth — needs a population indicator. WorldPop 2020 or census 2011 → indicator. (Forces a population indicator dataset, useful everywhere.)

### Phase F — Money pillar (taxes, GST, transfers, welfare)

F1. GST collections per state per quarter (GST Council).
F2. Finance Commission devolution per state per year.
F3. MGNREGA wages disbursed per state per year.
F4. Each is pure tabular. Use `data.gov.in` API where licensed; PDF-scrape fallback only with explicit user approval.

### Phase G — Roads, railways, building density (heavy spatial)

G1. Roads from `india-geodata/infrastructure/` — total km per state (indicator), not bundled geometry.
G2. Railway km per state similarly.
G3. Buildings: never bundle; if needed, render via PMTiles tile server (linked, not hosted).

## 8. What we explicitly do NOT do

- **No prefetched ad-hoc CSVs**. Every external data acquisition has a source adapter under `backend/yen_gov/sources/<provider>/` with retry, schema validation, and license enforcement. (CLAUDE.md anti-pattern: hardcoded data.)
- **No private joins.** If we compute "GDP per capita ranked", the inputs (`gsdp`, `population`) are also published as their own indicators. Audit trail intact.
- **No assumed coordinate systems.** Every GeoJSON-bearing artifact declares `coordinate_system` (default EPSG:4326 if omitted, but warned on by the validator).
- **No invented IDs** (CLAUDE.md §3). Every entity already has a code in our system; new datasets use the existing keys.
- **No bundled NC-licensed data.** SHRUG and similar ship as outbound links with attribution, not bundled assets.
- **No "TODO: add license later"**. License field is required at emit; missing → validator rejects.

## 9. Open questions (block specific phases — not the plan)

| Q   | Question                                                                 | Blocks    |
| --- | ------------------------------------------------------------------------ | --------- |
| Q1  | Allowed license classes for the published bundle — final list            | Phase A1  |
| Q2  | Is `india-geodata` itself a stable upstream we want to depend on, or do we pin to specific commit SHAs?  | Phase B1  |
| Q3  | Time-resolution standard: do we store dates as `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, or all three? Indicator schema needs a decision. | Phase A2  |
| Q4  | State-government timeline: who maintains it, what's the verification source? (Wikipedia + ECI past results)            | Phase B3  |
| Q5  | Do we adopt PMTiles for boundary rendering now or stay on simplified GeoJSON until a layer demands it?                 | Phase C   |
| Q6  | Do we keep `tools/boundaries` as our authoritative boundary builder, or migrate to `india-geodata` releases?           | Post-B    |
| Q7  | Welfare-spending data — is it published per state or only per scheme nationally? Determines whether it's an indicator. | Phase F3  |

---

## 10. Footnotes / verified references

- india-geodata repo: <https://github.com/yashveeeeeeer/india-geodata>
- Power plants metadata.json (verified 2026-05-10): `data/energy/power-plants/metadata.json`
- india-geodata is licensed CC BY 4.0; per-dataset licenses in their `metadata.json`.
- Their `electoral/` subtree has `assembly-constituencies/` and `parliamentary-constituencies/` — directly comparable to our `datasets/boundaries/in/geojson/S*-ac.geojson`. **Possible substitute** for `tools/boundaries` for AC/PC; evaluate in Q6.
- Healthcare facilities upstream is `planemad/india_health_facilities` (NIC HealthGIS, India OGL).
- Education facilities upstream is HOT/OSM (ODbL — attribution + share-alike; bundle OK with attribution).
- SHRUG is CC BY-NC-SA — **never bundle, link only.**

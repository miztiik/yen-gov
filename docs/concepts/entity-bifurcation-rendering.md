# Entity-bifurcation rendering — how reorganised states show up to the citizen

**Last Updated**: 2026-05-22
**Doc class**: concept per [ADR-0034](../architecture/decisions/0034-documentation-routing-contract.md) — one vocabulary term, defined once.
**Cites**: [ADR-0028](../architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) (URL grammar), [ADR-0030](../architecture/decisions/0030-canonical-store-duckdb-wasm.md) D23 (entity validity columns), [canonical-store.md](../architecture/data/canonical-store.md), [indicator-naming.md §2.4](indicator-naming.md), [schema-is-the-design-system.md](schema-is-the-design-system.md) (closed renderer set), [colours.md](../architecture/frontend/colours.md) (OkLCh treatment vocabulary), [Phase 2 P.1 Energy plan §3 Q-e + §3.1 #2](../../TODO/20260522-phase-2-p1-energy-pivot.md).
**Cited from**: [Phase 2 P.1 Energy plan §3.1 follow-up #2](../../TODO/20260522-phase-2-p1-energy-pivot.md) (hard-blocker for any P.1.A indicator that crosses 2014/2019 entity splits).
**See also**: [data-provenance.md](data-provenance.md), [long-coverage-indicators.md](long-coverage-indicators.md), [owid-alignment.md](owid-alignment.md).

---

## §1. Scope

This doc locks how yen-gov renders **mid-series territorial reorganisations** of Indian states and UTs across the closed renderer set. It covers the two on-disk cases today and the rule for future cases:

- **2014 — Andhra Pradesh reorganisation.** `IN-S01` (Andhra Pradesh, since 1956) is **reused** as the residual entity with `entity_valid_to: null`; `IN-S29` (Telangana, `entity_valid_from: 2014`) is the new entity. **Residual-id case**: the entity model alone does not surface the scope change — the renderer has to.
- **2019 — Jammu and Kashmir reorganisation.** `IN-S09` (Jammu and Kashmir, the composite state) is **retired** with `entity_valid_to: 2019`; `IN-U08` (J&K UT) and `IN-U09` (Ladakh UT) are new entities with `entity_valid_from: 2019`. **Retired-predecessor case**: the entity model surfaces the change cleanly.

**Out of scope.** Border adjustments smaller than a district; rename-without-territory-change (handled as a slug-rename, not a reorganisation); office_bearer reorganisations (covered by `office_holdings.parquet` per [G.1.c](../../TODO/20260517-canonical-long-format-pivot.md)).

The asymmetry between the two on-disk cases (id reuse for AP vs clean retire for J&K) is **load-bearing**: the renderer rules below must work for both. If a third case lands that introduces a third pattern, this doc earns a major revision.

## §2. Vocabulary (locked)

| Term | Meaning |
| --- | --- |
| **Reorganisation** | A territorial change in which one entity becomes two or more entities at a known date. The umbrella term for both cases above. |
| **Predecessor** | The entity whose territory is being reorganised (`IN-S01` pre-2014; `IN-S09` pre-2019). |
| **Successor** | An entity created by the reorganisation (`IN-S29`; `IN-U08`, `IN-U09`). |
| **Residual** | A successor that **reuses the predecessor id** (`IN-S01` post-2014). Specific to the AP case today. Used only when contextually needed to disambiguate from "predecessor". |
| **Reorganisation date** | The constitutional or statutory effective date (`2 Jun 2014`; `31 Oct 2019`). One date per reorganisation. |
| **Formed** | What a successor did at the reorganisation date. ("Telangana was **formed** from Andhra Pradesh in 2014.") |
| **LINEAGE_MAP** | The renderer-side mapping that resolves predecessor↔successor for the residual-id case. Hardcoded in `frontend/src/lib/entity-lineage.ts` today; promoted to `taxonomy/entity_lineage.parquet` on the third case (Q-6). |

**Banned vocabulary** (politically loaded or imprecise):

- "split" / "broke up" / "broke off"
- "carved out"
- "partitioned" / "partition"
- "secession" / "seceded"
- "separated"

Why: the reorganisations were statutory acts by Parliament (Andhra Pradesh Reorganisation Act 2014; Jammu and Kashmir Reorganisation Act 2019), not separatist events. The citizen should not infer either grievance or victory from the chart vocabulary.

## §3. The six surfaces

Each surface below locks one rendering rule. Rules consume `entity_valid_from / entity_valid_to / parent_entity_id` on `dim_entities` (per [ADR-0030 D23](../architecture/decisions/0030-canonical-store-duckdb-wasm.md)); the residual-id case additionally consumes `LINEAGE_MAP`.

### §3.1 TimeSeriesLine

On a state hub (`/india/telangana/installed-capacity`, `/india/andhra-pradesh/installed-capacity`, `/india/ladakh/...`):

- **Predecessor line** (e.g. AP for installed capacity) is drawn **continuous** across the reorganisation date. A vertical slate-300 rule at the reorganisation date is **always visible**, with a `Reorganised 2 Jun 2014` label anchored above the line.
- **Successor line** (e.g. Telangana) starts at `entity_valid_from`. The pre-formation span on the X-axis is rendered as a flat slate-100 floor band (no line drawn); a single anchored caption reads `Formed 2 Jun 2014 — no earlier values available`.
- **Tooltip on the predecessor's pre-reorganisation segment** appends: `Includes territory that became Telangana in 2014.` Same wording for J&K's pre-2019 predecessor with `J&K UT and Ladakh in 2019` appended.
- **No carry-forward, no backcast.** The renderer never invents a pre-formation value for a successor. If a publisher does backcast (rare — almost no Indian publisher does for state-level capacity), the backcast comes in as a regular row with its own `source_id` and is honoured.

*Rationale.* Continuity on the predecessor + the always-visible rule + the tooltip is OWID's "single line with annotation" pattern for USSR, Yugoslavia, Sudan. It outperforms two-line "joined ancestor" rendering on small viewports and avoids overloading the legend strip.

### §3.2 IndicatorChoropleth + MapChoropleth

On the national map at a chosen year:

- **For year < `entity_valid_from` of a successor**: the successor's polygon renders **greyed** (OkLCh `{L 0.92, C 0.02, h 250}` slate-50 fill, slate-300 stroke). Not hidden, not coloured with a backcast. The legend gains a small "pre-formation" swatch when at least one polygon in view is in this state.
- **For year < `entity_valid_to` of a predecessor that has been retired** (J&K's `IN-S09`): the historical-state polygon is rendered with its own value (the actual measurement); the post-reorganisation successor polygons are greyed for that year.
- **For residual-id case** (AP pre-2014): the **`IN-S01` polygon is coloured with the combined-AP value** because that's what `IN-S01` measures for that year. The Telangana polygon is greyed. The legend banner reads `Andhra Pradesh for years up to 2014 includes territory that later became Telangana.`
- **Tooltip on a greyed polygon** reads `Formed <date>` for successors and `Reorganised <date> — see successors` for retired predecessors. Click is a no-op for greyed polygons (no navigation; no value).
- **Polygon shape across the reorganisation**: yen-gov uses the current SOI-2019 boundary set for all years today. Pre-2014 AP is rendered with the post-2014 AP polygon (not the historical combined-AP polygon). This is documented in the legend banner. (Dynamic-polygon-by-year is Q-1 below.)

*Rationale.* Greying (vs hiding) preserves the citizen's geographical mental model. Colouring `IN-S01` with the combined value for pre-2014 is the only honest read of `IN-S01` rows for those years; the banner disclosure is the renderer's way of preventing the silent leaderboard fallacy.

### §3.3 IndicatorRanked

On a cross-state ranked table at a chosen year:

- **Pre-reorganisation years** show the predecessor row with its label suffixed: `Andhra Pradesh (combined — includes Telangana before 2014)`. The successor entity does NOT appear in the table for pre-formation years (no row, not a zero, not a NULL).
- **Post-reorganisation years** show predecessor and successor as independent rows with no suffix. (`Andhra Pradesh`, `Telangana`.)
- **Cross-year delta windows** (e.g. "change from FY10 to FY20") that **straddle** a reorganisation render a header banner: `Andhra Pradesh's FY10 value covers territory that included Telangana from FY15 onwards. The FY20 value is for residual Andhra Pradesh alone. Direct comparison overstates the change.` The rank column is **suppressed** for any state involved in a straddled reorganisation in that window; the value column remains, with a small caret marker on the cell.

*Rationale.* The most common citizen misread is "Andhra fell ten ranks" — that's not what happened; Andhra lost territory. The straddled-window banner + rank suppression is the renderer guard.

### §3.4 IndicatorSmallMultiples

On the grid of per-state mini-charts:

- **Sort order**: alphabetical by `display_name`. Successors are NOT placed adjacent to their predecessor (Telangana appears under T, not next to AP). The grid is not a lineage tree.
- **Each affected mini-chart** carries a small slate-500 caption inside the panel: `Formed 2 Jun 2014` (successor) or `Reorganised 2 Jun 2014 — combined before` (predecessor with continuing id).
- **Successor mini-charts** start their line at `entity_valid_from`; pre-formation span renders as the slate-100 floor band from §3.1.
- **Retired-predecessor mini-charts** (J&K's `IN-S09`) appear ONLY when the time window of the grid includes pre-`entity_valid_to` years. They are rendered with a slate-300 dashed border to communicate "historical entity"; the caption reads `Reorganised 31 Oct 2019 → J&K UT + Ladakh`.

*Rationale.* Lineage-adjacent placement looks tidy but breaks the grid's primary affordance (scan alphabetically). Captions inside the panel are sufficient.

### §3.5 State hub page (`/india/telangana`, `/india/jammu-kashmir`, `/india/ladakh`, `/india/andhra-pradesh`)

Under the H1 of every state hub for an entity that is a predecessor, successor, or both:

- **Chip strip** (single line, slate-700 12px, immediately under the H1):
  - Successor hubs: `Formed 2 Jun 2014 · from Andhra Pradesh` (Telangana); `Formed 31 Oct 2019 · from Jammu and Kashmir (state)` (Ladakh, J&K UT).
  - Predecessor hubs with continuing id: `Reorganised 2 Jun 2014 · Telangana formed from the same territory` (Andhra Pradesh).
- **Indicator cards** for indicators that carry pre-formation data inherited from a predecessor (only the residual-id case — AP) gain a small slate-400 corner chip reading `Pre-2014 values include Telangana`. Clicking the chip scrolls to the chart's banner.
- **Indicator cards** for indicators that genuinely have NO pre-formation data are visually identical to normal cards (no chip). The TimeSeriesLine starting at `entity_valid_from` per §3.1 is the only honesty signal needed.

### §3.6 Citizen text + chip vocabulary

Locked banner copy (placeholder voice — Hans owns the final voice pass per Q-4):

| Surface + situation | Banner text |
| --- | --- |
| TimeSeriesLine, predecessor pre-2014 (AP) | *Values up to 2014 cover Andhra Pradesh including territory that became Telangana in June 2014.* |
| TimeSeriesLine, successor before formation (Telangana) | *Telangana was formed from Andhra Pradesh on 2 June 2014. Values before that date are not available as Telangana-specific measurements.* |
| TimeSeriesLine, retired predecessor (J&K composite) | *Jammu and Kashmir was a single state until 31 October 2019, when it was reorganised into the Jammu and Kashmir Union Territory and the Ladakh Union Territory. Values up to that date refer to the combined state.* |
| TimeSeriesLine, successor before formation (J&K UT / Ladakh) | *Created from the composite Jammu and Kashmir state on 31 October 2019. Values before that date refer to the combined state and are not available as <state>-specific measurements.* |
| IndicatorChoropleth, banner when a year ≤ a reorganisation date is on-slider | *Some boundaries on this map were reorganised in <year>. Polygons before the reorganisation date are rendered greyed; predecessor values for residual entities cover the larger pre-reorganisation territory.* |
| IndicatorRanked, straddled-window banner | *<state>'s <start_year> value covers territory that included <successor> from <reorg_year>. Direct cross-year comparison overstates the change; rank not shown.* |

**Reorganisation marker glyph** (used at the vertical rule on TimeSeriesLine, on choropleth legend swatches, on small-multiples panel borders): a four-step stair-step in slate OkLCh `{L 0.70, C 0.02, h 250}`. Pattern + colour together; never colour alone. The glyph is named `bifurcation-marker` in the icon registry.

## §4. The two worked cases

### §4.1 Andhra Pradesh — 2014 (residual-id case)

| Field | Value |
| --- | --- |
| Reorganisation date | 2 Jun 2014 |
| Predecessor entity | `IN-S01` Andhra Pradesh (`entity_valid_from: 1956`, `entity_valid_to: null`) |
| Successor entities | `IN-S01` (residual — id reused), `IN-S29` Telangana (`entity_valid_from: 2014`) |
| Lineage source | `LINEAGE_MAP[IN-S29] = { predecessor: IN-S01, date: 2014-06-02 }`; the residual relationship is implicit (predecessor id is reused). |
| TimeSeriesLine on `/india/telangana/<indicator>` | §3.1 successor rule. Pre-2014 span = slate-100 floor band; vertical rule at 2014. |
| TimeSeriesLine on `/india/andhra-pradesh/<indicator>` | §3.1 predecessor rule. Line continuous across 2014; tooltip on pre-2014 segment appends "Includes territory that became Telangana in 2014." |
| Choropleth pre-2014 | `IN-S01` polygon coloured with combined-AP value; `IN-S29` polygon greyed. |
| Choropleth post-2014 | Both polygons coloured with their own values. |
| Ranked table pre-2014 | One row: `Andhra Pradesh (combined — includes Telangana before 2014)`. |
| State hub chip (Telangana) | `Formed 2 Jun 2014 · from Andhra Pradesh`. |
| State hub chip (Andhra Pradesh) | `Reorganised 2 Jun 2014 · Telangana formed from the same territory`. |

### §4.2 Jammu and Kashmir — 2019 (retired-predecessor case)

| Field | Value |
| --- | --- |
| Reorganisation date | 31 Oct 2019 |
| Predecessor entity | `IN-S09` Jammu and Kashmir (state) (`entity_valid_from: 1947`, `entity_valid_to: 2019`) |
| Successor entities | `IN-U08` Jammu and Kashmir (UT) (`entity_valid_from: 2019`), `IN-U09` Ladakh (`entity_valid_from: 2019`) |
| Lineage source | `LINEAGE_MAP[IN-U08] = { predecessor: IN-S09, date: 2019-10-31 }`; same for `IN-U09`. |
| TimeSeriesLine on `/india/jammu-kashmir/<indicator>` (= `IN-U08`) | Successor rule. Pre-2019 span = slate-100 floor band. |
| TimeSeriesLine on `/india/ladakh/<indicator>` (= `IN-U09`) | Successor rule. Pre-2019 span = slate-100 floor band. |
| TimeSeriesLine for `IN-S09` | Rendered only when the chart explicitly opts into historical-entity display (e.g. a long-arc view). Slate-300 dashed line treatment. |
| Choropleth pre-2019 | The `IN-S09` polygon (rendered with the composite J&K shape from boundaries-2018 if available, otherwise the union of U08+U09 with both tinted identically — Q-2) is coloured with the composite J&K value; U08 and U09 polygons are greyed. |
| Choropleth post-2019 | U08 and U09 coloured with their own values; S09 not rendered. |
| Ranked table pre-2019 | One row: `Jammu and Kashmir (composite state, reorganised 2019)` if the chart year is ≤ 2019. |
| State hub chips | J&K UT: `Formed 31 Oct 2019 · from Jammu and Kashmir (state)`. Ladakh: `Formed 31 Oct 2019 · from Jammu and Kashmir (state)`. |

## §5. What the entity model already gives you

The renderer is a **reader** of the entity model, not a re-implementer of it. The columns and rules below already exist on disk and in [ADR-0030](../architecture/decisions/0030-canonical-store-duckdb-wasm.md):

- `dim_entities.entity_valid_from` (int year) — when the entity began. Used by §3.1 / §3.2 / §3.4 to start successor lines and grey successor polygons.
- `dim_entities.entity_valid_to` (int year, nullable) — when the entity ended. NULL = current. Used to identify retired predecessors and to bound their charts.
- `dim_entities.parent_entity_id` — present for districts under states; **NOT** used to express bifurcation lineage (predecessor↔successor is not a parent↔child relationship in the entity model).
- `dim_entities.notes` (free-form) — already carries human-readable text on the four bifurcation rows (`IN-S01`, `IN-S09`, `IN-S29`, `IN-U08`, `IN-U09`) including "render greyed (D23)" hints. The renderer does NOT parse this string; it is for operator/editor context only.

For the residual-id case (AP), there is no entity-model column that says "`IN-S01` post-2014 ≠ `IN-S01` pre-2014." This is the **load-bearing reason** for `LINEAGE_MAP`: the renderer needs an explicit hand-curated table to know that a 2013 `IN-S01` row covers a larger territory than a 2015 `IN-S01` row.

## §6. Open questions

Items below need a decision before they unblock the surface they affect. Each item names the authority per CLAUDE.md §0a.

| # | Question | Recommended default | Authority | Blocks |
| - | --- | --- | --- | --- |
| Q-1 | Static SOI-2019 polygons across reorganisations, or dynamic boundaries-by-year? | Stay with static SOI-2019; document the caveat in the choropleth legend banner per §3.2. Dynamic polygons are a boundaries-team workstream + a per-year polygon set per source. | **Gregor** (boundaries contract) + **user** (priority) | §3.2 sub-bullet on polygon shape — current spec assumes static. |
| Q-2 | How does a pre-2019 `IN-S09` value render on the static U08+U09 polygon pair when boundaries-2018 is not on disk? | Union-of-children (both polygons tinted identically, composite-J&K tooltip "Combined Jammu and Kashmir, <year>: <value>"). Cleaner than a fabricated composite polygon. | **Gregor** + **Jony** (this doc ratifies once Gregor confirms) | §3.2 J&K row in §4.2. |
| Q-3 | Should `IN-S01` be forked into `IN-S01-1956` + `IN-S01-2014` to match OWID's no-id-reuse pattern, eliminating `LINEAGE_MAP` for the AP case? | Keep current `IN-S01` reuse; renderer carries the load via `LINEAGE_MAP`. Forking would force a backfill across every family already on canonical Parquet (elections, governments) and create a slug-rename in the URL space. | **Hans + Max** (§0a — entity model is data shape) | Architecture only; not blocking. **ADR-needed** if (b) chosen. |
| Q-4 | Final voice pass on the §3.6 banner copy. Placeholders today; Hans owns the binding voice. | Hans rewrites in the same commit that promotes B3/B7 to `methodology_breaks.parquet` (during P.1.A). | **Hans** | §3.6 copy — current text is placeholder. |
| Q-5 | Does `/india/jammu-kashmir-state` (historical `IN-S09`) get its own citizen route, or do successors carry the predecessor's history? | No standalone route; successor pages carry predecessor history via §3.5 chip + §3.1 banner. A historical-entity route would extend ADR-0028 grammar (`/india/historical/<slug>`) and is an ADR-level call. | **Gregor** (ADR-0028 extension if (b)) | §3.5 list of state-hub routes. |
| Q-6 | When does `LINEAGE_MAP` get promoted from a hardcoded TS constant to a typed `taxonomy/entity_lineage.parquet`? | YAGNI for two cases. Promote on the third bifurcation case. | **Gregor** (taxonomy contract) | Architecture only; not blocking. |

## §7. OWID precedent

OWID handles territorial reorganisations (USSR 1991, Yugoslavia 1991–2008, Sudan/South Sudan 2011, Germany 1990, Czechoslovakia 1993) by issuing a **new entity id** for every successor and **retiring** the predecessor at the dissolution date. There is no id reuse: post-2011 Sudan and pre-2011 Sudan are different entity ids in OWID's catalogue. Time-series renderers draw the predecessor up to the dissolution year and the successors from that year onward; choropleths render the historical polygon greyed in the post-dissolution period (and vice versa). Banner copy is matter-of-fact: *"Data refer to the combined entity prior to <date>."*

yen-gov **diverges** from OWID on the residual-id case (`IN-S01`): current Indian convention preserves the parent's identifier for the residual entity (same NIC code, same `iso_3166_2`, same passport stamp). Forking `IN-S01` would diverge from upstream LGD codes and complicate every backwards-compat join. The renderer carries the load via `LINEAGE_MAP` (§2 / Q-6); the citizen-facing rules above match OWID's surface behaviour (continuous predecessor line + greyed pre-formation polygons + banner disclosure) even where the underlying id model differs. This divergence is **named** here so it does not get re-litigated.

The J&K case (`IN-S09` retired with `entity_valid_to: 2019`) matches OWID's pattern verbatim — no divergence.

## §8. What this doc does NOT cover

- **District-level reorganisations** (e.g. Punjab's 1966 carve-out of Haryana + Himachal carved further) — out of scope; same rules apply by analogy when promoted to a renderer that consumes `entity_type='district'`.
- **Schema changes** — none. The entity model already carries `entity_valid_from / entity_valid_to`. The `taxonomy/entity_lineage.parquet` mentioned in §2 and Q-6 is a future addition, not an existing schema.
- **New components** outside the closed renderer set ([schema-is-the-design-system.md](schema-is-the-design-system.md)) — none required. All six surfaces compose from existing components.
- **a11y / WCAG / ARIA** — out of scope per CLAUDE.md §0 non-goals. The pattern + colour stair-step glyph (§3.6) serves visual clarity for sighted citizens, not WCAG compliance.

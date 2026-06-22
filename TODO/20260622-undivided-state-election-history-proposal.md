# Proposal: surfacing undivided-state election history (Andhra Pradesh / Telangana, and every bifurcation)

**Last Updated**: 2026-06-22
**Doc class**: proposal (working-doc under `TODO/`, non-authoritative per CLAUDE.md section 3). Captures a Max + Jony opinion for user ratification before any code lands.
**Status**: PROPOSAL - awaiting sign-off. No code changes in this PR.
**Authority**: data shape = Hans + Max (CLAUDE.md section 0a); UX = Jony + Citizen; contract/wiring = Gregor. User approval supersedes.
**Cites**: [docs/concepts/entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md), [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md), [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md), [datasets/taxonomy/state_formation_events.json](../datasets/taxonomy/state_formation_events.json), [datasets/taxonomy/methodology_breaks.json](../datasets/taxonomy/methodology_breaks.json), [datasets/taxonomy/election_events.json](../datasets/taxonomy/election_events.json).

---

## 0. TL;DR (the opinion)

The citizen-reported symptom ("Andhra Pradesh hides its older elections; neither AP nor Telangana shows the undivided-state assemblies") is really **three separate problems wearing one coat**. Solve them in order; do not bundle:

1. **A data gap, not a display bug (for assembly).** Pre-2014 undivided-AP **assembly** results are a *documented deferral* - they are not in the store at all. AP **parliament** data already goes back to 1962. So nothing is being "hidden"; the assembly rows do not yet exist. **Max: ingest them** (TCPD Lok Dhaba, cheap, reuses the shipped adapter). This alone lifts `/t/elections/assemblies` from "Andhra Pradesh - 3 ON RECORD" to ~15.

2. **A missing honesty layer (shippable now, on parliament).** AP parliament 2009/2014/2019 *already* paint on today's geometry by name-slug join, with unmatched seats silently grey. The fix is one small caption primitive - **Jony's `MapCoverageNote`** - that turns silent grey into "38 of 42 seats placed". This ships independently of (1).

3. **An attribution + overlay question (the actual design call).** Where do undivided-AP events live, and how does the map show territory that is now Telangana? **Both personas converge:** under residual **`IN-S01` only** (never Telangana), rendered as **"the territory of the time"** (the seats that genuinely voted), marked with **one dashed present-day border + one `Telangana - formed 2014` label** - and **explicitly NOT** the user's "overlay/hatch the now-Telangana districts" decoration, which both personas reject as clutter and as a quiet misrepresentation.

The "generic module depending on context" the user asked for is **two reusable pieces**, both reading reference data that already exists - no new schema, no hardcoded per-state map.

---

## 1. The citizen problem

- `https://miztiik.github.io/yen-gov/andhra-pradesh` -> Election dropdown lists 14 events: 3 assembly (2014/2019/2024) + 11 parliament (1962..2024). The pre-2014 assembly era is absent.
- `https://miztiik.github.io/yen-gov/t/elections/assemblies` -> "Andhra Pradesh - Latest 2024 - 3 ON RECORD" and "Telangana - 3 events". Undivided-AP assemblies appear under neither.
- Citizen mental model (median civic-curious Indian): "Andhra Pradesh is ~70 years of assembly history, not 10." The page silently amputates everything before 2014.

User's instinct (intent, paraphrased): Andhra Pradesh was the parent state and kept the name, so older events belong in its history; when shown, overlay the now-Telangana district info over the Telangana districts, with a caveat under the map like *"x of y pc/ac/districts matched - older years use {year-slug} boundaries - coverage drops with each delimitation"*; build a generic context-aware module and reuse it.

---

## 2. Verified facts (root cause)

| Fact | Evidence |
| --- | --- |
| AP `IN-S01` catalogue = 3 assembly + 11 parliament. | [datasets/taxonomy/election_events.json](../datasets/taxonomy/election_events.json) `states.S01`. |
| Pre-2014 undivided-AP assembly is a **documented deferral**. | The `assembly-2014` note: *"Residual Andhra Pradesh phase ... pre-2014 undivided Andhra Pradesh rows remain deferred."* |
| AP **parliament** results exist back to 1962. | `andhra-pradesh_election_results.csv` carries `LsGenFeb1962` period labels. |
| Telangana `IN-S29` assembly correctly starts 2014 (`entity_valid_from: 2014`). | catalogue `states.S29`. |
| Other states carry deep assembly history already (Arunachal S02 from 1978). | catalogue. So the catalogue format + UI already support deep history; AP is special only because of the deferral. |
| The split is modelled but not wired to surfacing. | [datasets/taxonomy/state_formation_events.json](../datasets/taxonomy/state_formation_events.json): `{parent_state_ids:[S01], successor_state_ids:[S01,S29], event_date:2014-06-02, parent_window_start_year:1956}`. |
| Only `delim=2024` geometry exists (175 AP ACs + 119 TG ACs). No undivided-AP 294-AC polygon family. | [datasets/data/entities/boundary_layer.csv](../datasets/data/entities/boundary_layer.csv); on-disk `boundaries/electoral/delim=2024/`. |
| The "N ON RECORD" count is a pure row-count of `event_summary.csv` (scope=state). | `assembly-elections-model.ts`. So the count is honest; it just has 3 rows to count. |

**Two corrections to assumptions found during exploration:**

- The concept doc [entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md) (dated 2026-05-22) **locks the bifurcation principles** (residual-id under `IN-S01`, grey the successor pre-formation, banner disclosure, never backcast) - but it covers the **indicator** surfaces (TimeSeriesLine, IndicatorChoropleth, IndicatorRanked) under the *old* `/india/<state>/<indicator>` URL grammar. It does **not** cover the **election** constituency maps that this proposal is about.
- The `LINEAGE_MAP` / `frontend/src/lib/entity-lineage.ts` that the concept doc references as "hardcoded today" **does not exist in the codebase**. It was specified but never built. So there is no working bifurcation renderer to "just wire up"; the principles are sound but the election-side implementation is genuinely new.

**Net:** the bifurcation *doctrine* is decided and binding; the election-surface *implementation* is the new work; the assembly *data* is a separate ingest.

---

## 3. Max's verdict (data shape - Hans + Max authority)

- **A. Attribution.** Pre-2014 undivided-AP rows live under **`IN-S01` only. Never under both. Never under `IN-S29`.** This is the residual-id case already locked in the concept doc. `IN-S01` is the same NIC/ISO/LGD code the Indian state itself preserved through the 2014 Reorganisation Act; the honest read of an `IN-S01` 2009 row is "the territory `IN-S01` measured in 2009" = combined AP. Telangana (`entity_valid_from: 2014`) carries no pre-formation rows - no backcast, no zero, no NULL-as-data. **Double-counting risk: none by construction** (only S01 carries the row). OWID precedent: successors get fresh ids, predecessor retires; yen-gov's *named, signed-off* divergence is to reuse `IN-S01` for the residual and carry lineage in the renderer. Do not re-litigate (concept-doc Q-3).
- **B. Ingest now.** **Yes - acquire the deferred pre-2014 undivided-AP assembly data.** High value, low cost. The blocker was never the source - it was the historical-entity decision, which is now made (item A). Recommended source: **TCPD Lok Dhaba `All_States_AE.csv` (DelimID 1-3)** - the *same* file the post-2014 slice already uses, so ingest is incremental. ECI Statistical Reports are GOLD but PDF-only pre-2014 (sustained hand-digitisation is out of scope). Each backfilled row carries a `source_id` FK (Holy Law #9) and a `processing_note` for the segment/delimitation context.
- **C. The caveat is render-time; the break is the data receipt.** Keep two distinct breaks from being conflated: the **reorganisation break** (2014, territory) is carried by `entity_valid_from/to` + lineage; the **delimitation break** (1967/1976/2008, constituencies redrawn) is carried by [methodology_breaks.json](../datasets/taxonomy/methodology_breaks.json) `lspc-delim-*` rows ("per-constituency not comparable across this break; per-state aggregate is"). The live "x of y matched" is the join-cardinality of (current polygons) intersect (that year's result rows) - a pure read-time function. **Do not store the match-count** (it would freeze one geometry assumption into the data layer; violates methodology-stable comparability).
- **D. Reject "paint modern TG geometry as a stand-in" on the *national* choropleth.** Painting 2024 TG district shapes as a proxy for undivided-AP geometry is dishonest twice: it implies Telangana existed and was measured separately before it did, and it back-projects a 2024 boundary onto a 1999 measurement. The honest national surface is the locked banner + greyed successor polygon.
- **E. The context contract already exists.** Do not invent new fields: `entity_valid_from/to` (entities), `parent_state_ids/successor_state_ids/event_date/parent_window_start_year` ([state_formation_events.json](../datasets/taxonomy/state_formation_events.json)), and the delimitation break rows. This already generalises to MP/Chhattisgarh-2000, UP/Uttarakhand-2000, Bihar/Jharkhand-2000, AP/Telangana-2014, J&K/Ladakh-2019. The YAGNI gate to promote the (never-built) hardcoded lineage map to read `state_formation_events.json` **has fired** (5 cases on disk) - so reading the existing JSON is now doctrine-mandated, not speculative.

**Max's biggest risk:** scope-creep from "ingest deep AP history" (do it) into "build a per-year historical-geometry overlay engine" (do not). There is no undivided-AP 294-AC polygon family; if a reviewer lets "overlay the now-Telangana districts" survive into the build as a *fabricated polygon set*, we ship a chart that lies.

---

## 4. Jony's verdict (UX - Jony + Citizen authority)

- **A. Placement: YES, NO on the word "overlay."** AP is the continuing legal entity; Telangana was formed from it. The parent keeps the history. An undivided-2009 event belongs in AP's dropdown - but labelled **"undivided Andhra Pradesh"**, never today's AP. The reductionist correction: you are not "overlaying Telangana onto AP", you are **rendering the territory of the time** - the union of today's AP + TG seats - because that *is* the undivided electorate. Those TG seats genuinely voted; they get the winner colour like any other seat. Nothing is "overlaid."
- **B. The caveat caption - kill the jargon.** "delimitation", "matched", "{year-slug}", "pc/ac" are developer words. The line must say, in citizen terms, *we drew an old election on today's map, and some seats could not be placed.* Use counts not percentages ("38 of 42" beats "90%"). Variants:
  - Full match, current vintage: **render nothing** (do not caption the normal case).
  - Partial / old-on-today's-map: *"Shown on today's map - 38 of 42 seats placed. This older election used different boundaries, so a few seats can't be shown."* + when a bifurcation is in frame, append: *"Includes areas now in Telangana (formed 2014)."*
  - No geometry: the caption does not appear; the placeholder/tile fallback replaces the map.
- **C. The generic module: `MapCoverageNote.svelte`.** A caption sibling to `MarginLegend` / `MapHighlightLegend` / `MapTooltip`. Props: `{ matched:number, total:number, unit:"seats"|"constituencies"|"districts", on_old_geometry:boolean, bifurcation?:{ child_label:string; formed_year:number } | null }`. Pure presentation - it does NOT fetch, join, or touch the SVG; the map already computes matched/total and feeds it up. Three render states (nothing / coverage line / coverage + bifurcation clause). It deliberately does NOT render a no-geometry branch (that is a different DOM shape - the placeholder card), an unmatched-seat table, per-seat reasons, or any colour.
- **D. The overlay visual - two fills, not three.** Matched and coloured (winner colour at margin opacity) vs unmatched/no-result (existing slate-200, one legend line "Grey - no result on file for this seat"). **"Now-another-state" is NOT a third fill** - those seats had results, so they are coloured. The only marks for the split are **one dashed present-day border + one `Telangana - formed 2014` label**. No hatching, no opacity tier, no pattern. Colour stays one signal.
- **E. Failure state (results but no geometry, e.g. pre-2009 parliament).** Never show an empty map when the results exist. The repo already ships `TileCartogram` (equal-seats hex). Reuse it: results-as-tiles beats results-as-nothing. If even tiles are out of scope, keep the placeholder card but drop the apology and promote the results table directly beneath.

**Jony's single removal:** the per-seat "overlay/hatch the now-Telangana districts" decoration. Colour those seats like any other; let one thin dashed present-day border + one `Telangana - formed 2014` label carry the entire "this is now another state" message.

---

## 5. Reconciliation - the one subtlety that matters

Max says "grey the successor"; Jony says "colour the seats." These are **not in conflict** - they are about **two different maps**:

| Surface | Pre-2014 undivided-AP behaviour | Owner |
| --- | --- | --- |
| **National state choropleth** (`IndiaPartyMap`, Home / national views) - one polygon per *state* | Telangana was not a state -> **grey the Telangana polygon**; colour `IN-S01` with the combined value; banner. (Concept-doc section 3.2, already doctrine.) | Max's rule |
| **State constituency map** (`StateAcMapD3` / `StatePcMapD3`, the `/andhra-pradesh/elections/<event>` page) - one polygon per *constituency* | Those constituencies genuinely voted in the undivided election -> **colour the matched seats** (incl. the now-Telangana ones), grey the unmatched, mark the split with one dashed border + label, caption the coverage. | Jony's rule |

The honesty in Jony's surface comes from the **caption + the methodology-break receipt**, exactly as Max requires - NOT from pretending the modern 2024 polygon set is the historical one. We reuse the existing safe-by-construction name-slug join (already shipping for parliament): matched seats coloured, unmatched grey. We do **not** fabricate a 294-AC undivided-AP polygon family (Max's tar pit). This two-surface split is the load-bearing reconciliation of the proposal.

---

## 6. Recommended approach (the generic, context-aware module)

The user's "generic module depending on context, reuse it" resolves to **two reusable pieces, both reading reference data that already exists** (Holy Law #6 - no hardcoded per-state map):

### 6.1 `MapCoverageNote.svelte` - the honesty caption (ship first)

- Jony's contract from section 4C. Pure presentation; the map emits `{ matched, total }` upward (it already knows them).
- Mounts in the existing caption slot under `StateEventMap` (the `text-xs text-slate-500` line). Renders nothing on the normal full-match current-vintage case.
- **Immediate payoff:** lights up on AP parliament 2009/2014/2019 today (those already name-slug join with silent grey seats) - independent of any data ingest.

### 6.2 A bifurcation reader over existing reference data - the "context"

- The `bifurcation` prop and the present-day-border + label come from a small typed reader over [datasets/taxonomy/state_formation_events.json](../datasets/taxonomy/state_formation_events.json) (parent/successor/date) + `entity_valid_from/to`. This is the doctrine-mandated promotion of the never-built `LINEAGE_MAP` directly onto the existing JSON (skip the hardcoded TS map; the YAGNI gate has fired with 5 cases).
- Because every Indian bifurcation is the same shape (child formed from parent, parent keeps the name), this reader generalises for free to MP/CG, BR/JH, UP/UK, AP/TG, J&K/Ladakh. AC maps, PC maps, and district choropleths all feed the same `{matched,total,unit}` tuple, so the caption is built once and every bifurcation lights up.
- The "territory of the time" render (colour the now-successor seats on the undivided event, plus the dashed present border + label) is added inside `StateAcMapD3` / `StatePcMapD3`, reusing the existing name-slug join and `geo-rewind`. No new geometry files.

### 6.3 The data ingest (separate workstream)

- Ingest pre-2014 undivided-AP assembly from TCPD Lok Dhaba `All_States_AE.csv` (DelimID 1-3) under residual `IN-S01`, per Max section 3B. Pre-2014 rows label as "Andhra Pradesh (combined - includes Telangana before 2014)" per concept-doc section 3.3. This is what flips `/t/elections/assemblies` from 3 to ~15 and populates the older slots in the `/andhra-pradesh` dropdown. Telangana correctly stays at 3.

---

## 7. Scope - PR split (do not merge into one)

| PR | Title | Depends on | Lights up | Risk |
| --- | --- | --- | --- | --- |
| **A** | `MapCoverageNote` honesty caption | none | AP/all-state **parliament** 2009-2019 maps gain "N of M seats placed" | Low - one presentation primitive over an existing join |
| **B** | Bifurcation reader + "territory of the time" render + dashed-border/label | A | Undivided events render the full electorate with the split marked | Medium - touches the two state map components |
| **C** | Ingest pre-2014 undivided-AP assembly (TCPD, DelimID 1-3) under `IN-S01` | none (parallel to A/B) | `/t/elections/assemblies` 3 -> ~15; dropdown older slots populate | Medium - data acquisition + provenance |
| **D** | Extend [entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md) to the election surfaces; fix the stale `/india/` URLs and the non-existent `entity-lineage.ts` reference | A, B | doctrine matches code | Low - docs |

Ship A first (pure win, no data dependency). C can run fully in parallel. B and D follow.

---

## 8. Decisions needed before build (sign-off surface)

1. **Ratify attribution** (Hans + Max): pre-2014 undivided-AP events under `IN-S01` only; Telangana stays post-2014. (Personas: already doctrine; this is a confirm.)
2. **Approve the ingest** (Hans + Max + user priority): acquire pre-2014 undivided-AP assembly from TCPD Lok Dhaba. Is the single-state deep backfill worth the slot now?
3. **Ratify "render nothing on the normal case"** (Jony + Citizen): the caption is silent unless coverage is partial or geometry is old. Confirm we do not want an always-on "100% placed" line.
4. **Confirm the removal** (user): drop the per-seat "overlay/hatch the now-Telangana districts" decoration in favour of one dashed border + one label. This is a deliberate narrowing of the user's stated idea and needs explicit OK.
5. **Banner/caption voice** (Hans): final wording pass on the citizen copy in section 4B (concept-doc Q-4 voice pass is still open).

---

## 9. What this proposal does NOT do

- Does **not** fabricate an undivided-AP 294-AC historical polygon family (no such data; Max's tar pit).
- Does **not** backcast, zero-fill, or duplicate any undivided-AP row onto Telangana `IN-S29`.
- Does **not** store the match-count as data (render-time only).
- Does **not** add per-seat hatching/opacity tiers (colour is one signal; grey is the one second signal).
- Does **not** change the URL grammar or the `event_summary` mart schema.
- Does **not** raise a11y (project non-goal, CLAUDE.md section 0).

---

## 10. See also

- [docs/concepts/entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md) - the bifurcation principles (indicator surfaces today; section 7 PR-D extends to elections).
- [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) - d3-geo choropleths, delimitation join, geo-rewind.
- [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) - locked state-event URL grammar.
- [datasets/taxonomy/state_formation_events.json](../datasets/taxonomy/state_formation_events.json) - the bifurcation context the module reads.
- [datasets/taxonomy/methodology_breaks.json](../datasets/taxonomy/methodology_breaks.json) - the delimitation break receipts.

# Proposal: surfacing undivided-state election history, generalized to every state and UT

**Last Updated**: 2026-06-23
**Doc class**: proposal (working-doc under `TODO/`, non-authoritative per CLAUDE.md section 3). Captures a Max + Jony opinion for user ratification before any code lands.
**Status**: PROPOSAL (rev 2) - awaiting sign-off. No code in this PR.
**Authority**: data shape = Hans + Max (CLAUDE.md section 0a); UX = Jony + Citizen; contract/wiring = Gregor. User approval supersedes.
**Cites**: [docs/concepts/entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md), [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md), [datasets/taxonomy/state_formation_events.json](../datasets/taxonomy/state_formation_events.json), [datasets/taxonomy/methodology_breaks.json](../datasets/taxonomy/methodology_breaks.json), [datasets/data/entities/boundary_layer.csv](../datasets/data/entities/boundary_layer.csv), [datasets/taxonomy/election_events.json](../datasets/taxonomy/election_events.json).

> **Rev 2 (2026-06-23)** answers the user's review: (1) the 14-event state/national breakdown + the missing-count arithmetic; (2) adopts the USER's caption wording (the verbose Jony copy is dropped); (3) generalizes the whole design to ALL states and UTs and ALL years (delimitation is universal, e.g. 1962 vs 2024); (4) an enumerated changes -> PR -> problem table; (5) confirms the caption goes INSIDE the map card per the user's mockup.

---

## 0. TL;DR (the opinion)

The citizen-reported symptom is three separate problems. Solve them in order; do not bundle:

1. **A data gap (assembly), not a display bug.** Pre-2014 undivided-AP **assembly** results are a documented deferral - not in the store. AP **parliament** data already runs back to 1962. So nothing is "hidden"; the rows do not exist yet. Ingest them (TCPD Lok Dhaba) -> AP assemblies go from 3 to ~15.
2. **A missing honesty caption (universal, shippable now).** Every old election rendered on today's geometry has seats that do not match - not just AP, every state, because boundaries are redrawn at each delimitation (1962 used the 1951 Order; 2024 uses 2008). One small primitive - **`MapCoverageNote`, using the USER's wording** - turns silently-grey seats into `217 of 542 constituencies matched ...`.
3. **The bifurcation render (the real design call).** Undivided-AP events live under residual **`IN-S01` only**. The trap Max caught: if we draw them on the post-2014 AP-only map, the caption lies "175 of 175 - full coverage" while dropping the ~119 now-Telangana seats out of the denominator. The fix: render undivided events on the **union of parent + successor geometry** ("the territory of the time"), driven by `state_formation_events.json`, marked with **one dashed present-day border + one neutral label** - never per-seat hatching.

The "generic module depending on context" = **one text caption primitive + one map-overlay driven by reference data that already exists** (no new schema, no hardcoded per-state map). It generalizes across PC / AC / district and across every state, UT, and bifurcation.

---

## 1. The citizen problem

- `/andhra-pradesh` -> Election dropdown lists 14 events; the pre-2014 assembly era is absent.
- `/t/elections/assemblies` -> "Andhra Pradesh - 3 ON RECORD" and "Telangana - 3 events". Undivided-AP assemblies appear under neither.
- Citizen mental model: "Andhra Pradesh is ~70 years of assembly history, not 10."

---

## 2. Clarification: the 14 Andhra Pradesh events (answers "how many state vs national?")

The 14 on `/andhra-pradesh` are **3 state (assembly) + 11 national (parliament)**:

| Kind | Count | Years |
| --- | :---: | --- |
| **State** - Assembly (`kind: assembly`) | **3** | 2014, 2019, 2024 |
| **National** - Parliament (`kind: parliament`) | **11** | 2024, 2019, 2014, 2009, 2004, 1999, 1998, 1996, 1991, 1989, 1962 |

(Source: [election_events.json](../datasets/taxonomy/election_events.json) `states.S01`, lines 6-176.)

**Why the topic page shows only 3 (answers "how many of the 14 get added?")**: `/t/elections/assemblies` counts **assembly events only**. The 11 parliament events are a different `kind` and surface on the sibling **`/t/elections/general`** page (where Andhra Pradesh is a state-slice of each national general election). So **none of the other 11 "move" into the assembly count - they were never assembly events.** The 14 split cleanly: 3 -> assemblies page, 11 -> general page. Nothing is lost between the two pages.

**What IS missing** (the "obviously something is missing"): the **pre-2014 undivided-AP assembly elections** - roughly 12 (1955, 1962, 1967, 1972, 1978, 1983, 1985, 1989, 1994, 1999, 2004, 2009; Telangana-region voters were part of every one). These are not in the 14 and not in the store (deferred). The arithmetic:

| State | Assemblies today | After ingest | Why |
| --- | :---: | :---: | --- |
| Andhra Pradesh (`IN-S01`) | 3 | **~15** | residual entity inherits the undivided history (kept the name + ECI code) |
| Telangana (`IN-S29`) | 3 | **3** | formed 2014; no pre-formation rows (no backcast) |

(Secondary gap, out of headline scope: AP's national list also has holes - it jumps 1962 -> 1989, missing 1967/71/77/80/84 and 1952/57. Same fix shape if pursued.)

---

## 3. Verified facts (root cause)

| Fact | Evidence |
| --- | --- |
| Pre-2014 undivided-AP assembly is a **documented deferral**. | `assembly-2014` note: "pre-2014 undivided Andhra Pradesh rows remain deferred." |
| AP **parliament** results exist back to 1962; assembly only 2014+. | `andhra-pradesh_election_results.csv` (`LsGenFeb1962` present). |
| The split is modelled but unwired to surfacing. | [state_formation_events.json](../datasets/taxonomy/state_formation_events.json): `{parent:[S01], successors:[S01,S29], event_date:2014-06-02}`. |
| Only `delim=2024` geometry exists; old elections name-slug-join it; unmatched seats already render grey. | [boundary_layer.csv](../datasets/data/entities/boundary_layer.csv); `StatePcMapD3`/`StateAcMapD3`. |
| The PC delimitation eras are on disk (PC only). | [methodology_breaks.json](../datasets/taxonomy/methodology_breaks.json): `lspc-delim-1967` (1951-Order 1952-62; 1962 Commission 1967-71), `lspc-delim-1976` (frozen 1977-2004), `lspc-delim-2008` (2009-2024). No AC rows, no per-state rows. |
| `matched`/`unmatched` is already computed render-time. | [frontend/src/lib/elections/seat-flow-model.ts](../frontend/src/lib/elections/seat-flow-model.ts). |
| The map card already has a caption slot. | [frontend/src/lib/elections/StateEventMap.svelte](../frontend/src/lib/elections/StateEventMap.svelte) `text-[11px] text-slate-500`, inside the map `<section>`, below the legend. |

**Two assumption corrections** carried from rev 1: the concept doc [entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md) locks the bifurcation *principles* but covers the **indicator** surfaces under the old `/india/` URLs - not the election maps; and the `LINEAGE_MAP` / `entity-lineage.ts` it references **was never built**. The principles are binding; the election implementation is new.

---

## 4. The design, generalized to ALL states and UTs (answers "solve for all states and UT")

The honesty caption is **about delimitation/boundary coverage, which is universal** - every state's every old election, drawn on current geometry, has a coverage shortfall. Bifurcation is one extra axis layered on top. There are **four coverage-drop axes**; one caption honestly covers two, and a second guard is needed for the other two:

| # | Axis | Source of truth | Single caption honest? |
| --- | --- | --- | :---: |
| a | PC delimitation redraws (national: 1951 / 1962 / 1971-frozen / 2008) | `methodology_breaks` (present, PC) | yes |
| b | AC delimitation redraws (per-state; Assam-2023, J&K-2022 specials) | `methodology_breaks` (absent for AC) | yes (number); "why" receipt missing |
| c | Bifurcations (AP/TG-2014, J&K/Ladakh-2019, MP/CG, BR/JH, UP/UK-2000, Goa-1987) | `state_formation_events` (present) | **no - needs the guard** |
| d | Entity did not exist in the older year (TG, CG, JH, UK, Ladakh, Goa) | `state_formation_events` | **no - needs the guard** |

### 4.1 The coverage caption - the USER's wording (adopted)

Jony's earlier verbose copy is **dropped**. The caption is the user's line, parameterized by `{unit}` so it serves PC, AC, and district:

```
{matched} of {total} {unit} matched &middot; older years use {geometry_year} boundaries &mdash; coverage drops with each delimitation
```

Rendered (the user's mockup, a national PC choropleth of an old general election):

> `217 of 542 constituencies matched &middot; older years use 2019 boundaries &mdash; coverage drops with each delimitation`

- `{matched}` / `{total}`: **emergent, computed render-time, never stored** (Max; already shipped in `seat-flow-model.ts`). `total` = features in the rendered layer for the state/UT; `matched` = those that bind a result after the join.
- `{geometry_year}`: **read from `boundary_layer.csv.delimitation_vintage`** of the layer actually rendered (never a hardcoded `"2024"`, Holy Law #6). Semantics = "the snapshot edition the citizen is looking at" (the honest token; "1976" would assert boundaries we do not hold).
- `{unit}` in {`constituencies` (PC + AC), `districts`}.

**One word needs your nod (Jony's flag):** "delimitation" is an electoral term and does not describe a *district* boundary change. To keep ONE caption across constituencies + districts, the last clause could become unit-neutral: `coverage drops as boundaries are redrawn`. Keep "delimitation" verbatim if the caption stays constituency-only; switch to "boundaries are redrawn" if it must also caption district choropleths. **Decision D-5 below.**

### 4.2 The three render states (answers the 1962 example)

The splitter is a `floor` threshold on the same emergent `matched` count (a render-policy config constant - Jony + Citizen, not data):

1. **Partial match** (`matched > floor`, e.g. an old general on 2008-era geometry) -> render the map, grey the unmatched, show the caption.
2. **No usable geometry** (`matched == 0` or `< floor`; e.g. **1962 LS used the 1951 Order - no 1951 geometry on disk**) -> a near-all-grey map is dishonest (reads "no data" when the truth is "no map"); fall back to the existing table / `TileCartogram`, caption: `No boundary map for this year &ndash; {unit} shown below.`
3. **No results at all** (the deferred pre-2014 AP assembly set, until ingest) -> "not yet available" empty state.

### 4.3 The bifurcation trap and its fix (Max's single biggest risk)

Because the caption counts **map units**, drawing undivided-AP 1999 on the post-2014 AP-only geometry (175 ACs) makes all 175 bind -> caption reads **"175 of 175 matched - full coverage"** while the ~119 now-Telangana result rows have **no polygon and never enter the denominator**. The caption says "complete" while hiding 40% of the contest. The successor side fails opposite: a Telangana viewer pre-2014 would see "0 of 119", which looks like a delimitation drop but is really "this state did not exist".

**Fix (driven by `state_formation_events.json`, no new table):**
- **Parent / residual side** (undivided event under `IN-S01`): render on the **union of today's parent + successor geometry** (AP 175 + TG 119 = 294) - "the territory of the time" - so the denominator includes the seceded seats and the caption is honest. Mark the split with **one dashed present-day border + one neutral label** (e.g. the successor's name + formed-year), no per-seat hatching.
- **Successor side** (`IN-S29` before formation): an **existence-guard fires before the caption** - no "0 of 119" map; instead a one-line redirect ("part of the parent before the formation date; see the parent"). This is the same guard for axis (d) - states/UTs that did not exist yet.

### 4.4 Placement - INSIDE the map card (answers "shall we do the same as the screenshot?")

**Yes.** The caption sits **inside the map's box/div, directly below the legend**, muted `text-[11px] text-slate-500` - exactly the user's mockup and exactly the existing slot in `StateEventMap.svelte`. Same slot for AC / PC / district. Two carve-outs: the **no-geometry** line lives inside the placeholder / tile card (there is no map div), and the **equal-seats hex** view renders nothing (tiles are complete by construction - no grey seats to explain).

---

## 5. The reusable module (the "generic module depending on context")

Two pieces, both reading reference data that already exists - this is the generalization the user asked for:

- **`MapCoverageNote.svelte`** - pure text caption. Props `{ matched, total, unit, geometry_year }`. Branches: `matched === total` -> render nothing; `geometry_year == null` -> the no-geometry line; else the partial line. It does NOT fetch, join, or touch the SVG (the map already computes the numbers and passes them up). Serves PC, AC, and district unchanged.
- **The bifurcation overlay** - the union render + dashed border + neutral label + the successor existence-guard. Driven by a typed reader over [state_formation_events.json](../datasets/taxonomy/state_formation_events.json) (the doctrine-mandated promotion of the never-built `LINEAGE_MAP` directly onto the existing JSON; the YAGNI gate fired at 5 cases). `successor_label` is a MAP prop, **not** a caption prop - keeping the text primitive free of map concerns is what lets it serve all three map types. Generalizes free to MP/CG, BR/JH, UP/UK, AP/TG, J&K/Ladakh.

No new schema. One data-layer change only: a **one-line semantic pin** on `boundary_layer.csv.delimitation_vintage` ("snapshot edition the citizen sees", so a later agent does not "correct" 2024 to the 2008 order-year). One known generalization gap: admin/district layers carry an **empty** `delimitation_vintage` (districts are notified, not delimited) - the district `{geometry_year}` token needs either an analogous snapshot-vintage populated on admin layers or a different provenance field (**decision D-6**).

---

## 6. What changed this round (Max + Jony, rev 2)

- **Adopted the user's caption wording**; dropped Jony's verbose "This older election used different boundaries... Includes areas now in Telangana" (rejected as verbose + AP-specific + non-generalizing).
- **Generalized to all states/UT/years**: the caption is cause-agnostic (reports the symptom, not the cause), so it honestly covers PC + AC delimitation drops everywhere. **1962** is the worked failure case (no 1951 geometry -> table/tile fallback).
- **Caught the parent/residual asymmetry** (Max): map-unit counting hides seceded territory; fixed by the union render + the `state_formation_events` existence-guard.
- **Confirmed placement** inside the map card (Jony), and that the count line **is** the grey legend (drop any separate grey swatch).
- **Bifurcation = one line**: the successor is shown once on the map (border + label), never repeated in the caption text. No "Telangana" string in copy.

---

## 7. Enumerated changes -> PRs -> problems solved (answers "how many PR / what problems")

**5 PRs.** PR-A is shippable immediately and independently; PR-C runs fully in parallel; B/D/E follow.

| PR | Change (enumerated) | Surface / files | Problem it solves |
| --- | --- | --- | --- |
| **A** | 1. New `MapCoverageNote.svelte` (props `{matched,total,unit,geometry_year}`). 2. Mount in the existing caption slot in `StateEventMap`. 3. Pass the already-computed `matched`/`total` up from `StateAcMapD3` / `StatePcMapD3`. 4. Read `{geometry_year}` from `boundary_layer.csv.delimitation_vintage`. | `frontend/src/lib/elections/` + `frontend/src/lib/charts/` | **Silent grey seats.** Every old election on current geometry (e.g. AP/all-state parliament 2009-2019) gains an honest "N of M matched" line. Universal, no data dependency. |
| **B** | 5. Typed reader over `state_formation_events.json`. 6. Union-of-parent+successor geometry render for undivided events under the residual entity. 7. One dashed present-day border + one neutral label. 8. Successor existence-guard (redirect, no "0 of N" map). | `frontend/src/lib/charts/` + a small lineage reader | **The bifurcation trap.** Parent map no longer lies "175 of 175"; successor no longer shows a false "0 of 119". Generalizes to all 5+ bifurcations. |
| **C** | 9. Ingest pre-2014 undivided-AP assembly from TCPD Lok Dhaba `All_States_AE.csv` (DelimID 1-3) under `IN-S01`, each row with `source_id` FK + `processing_note`. 10. Catalogue rows + `event_summary` mart refresh. | `backend/` + `datasets/` | **The data gap.** `/t/elections/assemblies` 3 -> ~15; the `/andhra-pradesh` dropdown's older slots populate. Telangana stays 3. |
| **D** | 11. Author AC + per-state delimitation rows in `methodology_breaks.json` (Assam-2023, J&K-2022, AC-2008 ...). 12. One-line semantic pin on `boundary_layer.csv.delimitation_vintage`. | `datasets/taxonomy/` + `datasets/data/entities/` | **The "why" receipt.** Makes the caption's causal clause auditable for AC (today only PC is); pins the `{geometry_year}` semantics. |
| **E** | 13. Extend [entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md) to the election surfaces; fix the stale `/india/` URLs and the non-existent `entity-lineage.ts` reference. | `docs/` | **Doc-vs-code drift.** Doctrine matches the shipped election rendering. |

**Minimum viable for the citizen report**: PR-A (universal honesty) + PR-C (the AP data). PR-B makes the undivided maps correct; D/E are the durable-receipt + docs tail.

---

## 8. Decisions needed before build (sign-off surface)

1. **D-1 Attribution** (Hans + Max): undivided-AP events under `IN-S01` only; Telangana stays post-2014. (Already doctrine - confirm.)
2. **D-2 Ingest** (Hans + Max + user priority): acquire pre-2014 undivided-AP assembly from TCPD Lok Dhaba now?
3. **D-3 Union render** (Jony + user): for undivided events, render the union of parent+successor geometry with one dashed border + one neutral label (NOT per-seat hatching, NOT a parent-only map that hides the seceded seats). Confirm.
4. **D-4 Silent on full match** (Jony + Citizen): the caption renders nothing when every seat matches on current geometry. Confirm (no always-on "100%" line).
5. **D-5 The word "delimitation"** (user): keep verbatim for constituency maps, or switch the last clause to unit-neutral "coverage drops as boundaries are redrawn" so the same line also serves district choropleths? (This touches your ratified wording, so it needs an explicit call - STOP-AND-SURFACE.)
6. **D-6 District `{geometry_year}`** (Gregor + Max): admin layers carry empty `delimitation_vintage`; populate a snapshot-vintage on district layers, or accept a different provenance token there?
7. **D-7 Voice pass** (Hans): final wording of the no-geometry + existence-guard lines.

---

## 9. Next step

1. You ratify the decisions above (at minimum D-2, D-3, D-5).
2. Ship **PR-A** first - the `MapCoverageNote` caption is a pure presentation primitive over numbers the maps already compute; it lights up the honesty line on every old election immediately, with zero data or geometry dependency. It is the safest, highest-signal first move and validates the wording in the live UI (CLAUDE.md section 13).
3. Kick off **PR-C** (ingest) in parallel - independent of the frontend.
4. Then **PR-B** (union render + guard), then **D/E**.

If you approve, I will turn this proposal into an execution-ready plan-doc (per the `prepare-plan` skill) with per-PR DoD, test tiers, and the smoke loop - then implement PR-A.

---

## 10. What this proposal does NOT do

- Does **not** fabricate a historical undivided-AP 294-AC polygon family - it reuses the union of today's parent+successor polygons via the existing name-slug join.
- Does **not** backcast, zero-fill, or duplicate any undivided row onto Telangana `IN-S29`.
- Does **not** store the match-count (render-time only).
- Does **not** add per-seat hatching/opacity tiers - colour is one signal; grey + the count line is the one second signal.
- Does **not** add a new `delimitation_events` table (over-engineering; the "why" goes in existing `methodology_breaks.json`).
- Does **not** name a successor state in caption text - the map carries that once.
- Does **not** raise a11y (project non-goal).

---

## 11. See also

- [docs/concepts/entity-bifurcation-rendering.md](../docs/concepts/entity-bifurcation-rendering.md) - bifurcation principles (PR-E extends them to elections).
- [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) - d3-geo choropleths, delimitation join, geo-rewind.
- [datasets/taxonomy/state_formation_events.json](../datasets/taxonomy/state_formation_events.json) - drives the union render + existence-guard.
- [datasets/taxonomy/methodology_breaks.json](../datasets/taxonomy/methodology_breaks.json) - the delimitation "why" receipts (PC today; AC in PR-D).
- [datasets/data/entities/boundary_layer.csv](../datasets/data/entities/boundary_layer.csv) - carries `delimitation_vintage` (the `{geometry_year}` token).

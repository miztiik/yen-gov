# State-page IA rework — discussion doc

**Created**: 2026-05-15  
**Status**: **DECISIONS LOCKED 2026-05-15** — ready for subagent execution. Open questions resolved (§5).  
**Trigger**: Live walkthrough of `/s/tamil-nadu` with Citizen User + Jony agents, signed off by Hans (governance) and Max (indicator scout) and Fowler (engineering).  
**Related**: [TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md), [TODO/VIZ-LAYER-GAPS-PLAN.md](VIZ-LAYER-GAPS-PLAN.md), [TODO/PLAN.md](PLAN.md)

---

## Guiding principle (user-stated, 2026-05-15) — binding for Jony, Max, Fowler

> *"We are definitely going to add more indicators. That doesn't mean every indicator has to land on `/s/<state>`. We don't load everything in one page — we give them options to navigate, they choose the area of interest, and they navigate to depth. Like a book: a 1000-page book doesn't show all 1000 pages on its cover. It has a table of contents, sections, and the narrative leads to depth."*

**Implication for the plan:**
- `/s/<state>` is the **book cover + table of contents**, not chapter 1.
- `/s/<state>/t/<topic>` is a **chapter opener** — 5–8 indicators per topic, the editorially-curated tour.
- `/i/<indicator>` is a **footnote-grade citation page** — every indicator addressable, none auto-rendered on a landing surface.
- New ingest is **always welcome**. The IA absorbs growth structurally: a new indicator gets a `topic` field on its schema and slots into the right `/s/<state>/t/<topic>` automatically. It does **not** lengthen `/s/<state>`.
- Ingest workstream and IA rework run **in parallel**, coordinated only by the indicator-schema `topic` field contract.

---

---

## 0. The diagnosis (measured, live)

`/s/tamil-nadu` on the dev build at `http://localhost:5173/`:

| Metric | Today | Target |
| --- | --- | --- |
| Document height | **222,073 px** (~270 phone screenfuls) | ≤ 6 phone screenfuls |
| `<h2>` headings | **106** | ≤ 8 |
| `<h3>` headings | **332** (almost all duplicated copies of the H2) | ≤ ~16 |
| MapLibre maps mounted at first paint | **99** India choropleths | 0 India choropleths on this surface |
| Sidebar topic links | Drop state context (go to `/t/<topic>`) | Stay state-scoped (`/s/<state>/t/<topic>`) |
| `/s/<state>/t/<topic>` route | **404** | Exists |
| "Explore trends" sidebar item | Opens "Data explorer — Tamil Nadu" (election query UI) | Either renamed or deleted (open Q) |
| `/` map "Theme" dropdown | Raw schema slugs (`fiscal/outstanding_debt_pct_gsdp`) | Human labels with slug as `<title>` |
| First card "YOUR GOVERNMENT" | Renders developer prose: *"Downstream UI MUST treat null cm_name + null party_code…"* | One neutral sentence in plain English |

**One-line root cause** (Jony): *"The catalogue equals the page — every schema row in `datasets/indicators/` becomes an H2, every H2 mounts its own map. There is no editorial layer."*

---

## 1. The left rail — TODAY vs PROPOSED

### Today (verbatim render order)

```
Yen Gov                         (logo)
[ Pick your state ▾ ]           (36 entries)

MY STATE
  Overview              → /s/<state>
  Explore trends        → /s/<state>/explore   ← actually "Data explorer", not trends

HOW STATES COMPARE
  All topics            → /t
  Money & debt          → /t/fiscal            ← drops state context
  Power & energy        → /t/energy            ← drops state context
  Elections             → /t/elections         ← drops state context
  Compare states        → /compare
  Side by side          → /compare/<state>/<election-id>

CENTRE AND STATES                              ← group of one
  Money & debt          → /t/fiscal            ← duplicate link

SETTINGS
  Settings · About · Repo
```

**What's wrong** (Jony's audit):
- Topic coverage is a lie — rail advertises **3 topics**, data has **10** (Economy, Demography, HD, Environment, Prices, Transport, Public health invisible).
- "Money & debt" appears **twice** under different group headers, same URL.
- "CENTRE AND STATES" is a **group-of-one** whose only member is a duplicate.
- Every topic link **drops state context** — the small betrayal that teaches citizens not to trust nav.
- "Explore trends" writes a cheque the page doesn't cash.
- Repo link in nav is wrong altitude — belongs in `/about` footer.

### Proposed (Jony — 3 groups, ≤ 11 links, state-context-aware)

```
Yen Gov                                 (logo, /)
[ Tamil Nadu ▾ ]                        (state picker)

THIS STATE                              (collapses to "Pick a state…" if none selected)
  Overview                  → /s/<state>
  Money & debt              → /s/<state>/t/fiscal
  Power & energy            → /s/<state>/t/energy
  Economy                   → /s/<state>/t/economy
  People & development      → /s/<state>/t/human-development
  Environment & transport   → /s/<state>/t/environment
  Elections                 → /s/<state>/t/elections

ACROSS STATES
  Compare states            → /compare
  All topics                → /t

ABOUT
  About & sources           → /about
  Settings                  → /settings
```

**State-aware behaviour, explicit:**
- When **no state is selected**, "THIS STATE" collapses to a single line ("Pick a state to see its data") and the topic links don't render.
- When **a state is selected**, "THIS STATE" expands; cross-state `/t/<topic>` links do **not** appear in the rail (they're reached from inside each topic page via "See how all states compare →").
- Repo link → footer of `/about`. Not navigation.
- Deleted: `Explore trends`, `Side by side`, `Centre and states` group, the duplicate `Money & debt`, the duplicate `All topics`, the Repo link, "More topics coming soon".

---

## 2. The 99 India choropleths — where do they go?

### Today
99 India choropleths render inline on `/s/<state>`, one per indicator card. Each weighs a maplibre-gl GPU canvas. None is the right shape for the question the citizen is actually asking on this surface.

### Proposed migration

| Surface | Has India choropleth? | Why |
| --- | --- | --- |
| `/s/<state>` | **No.** | Wrong question. Citizen on a state page asks "how is *my state* doing?", not "where does it rank?" Indicator card replaces the map with: **big number + sparkline + 1-line rank + "See all states →" link**. |
| `/s/<state>/t/<topic>` | **No.** | Still state-scoped. If a sub-state map exists (district / AC), use that; otherwise time series. |
| `/t/<topic>` | **YES — this is the home.** | Cross-state question; one choropleth per indicator card. |
| `/i/<indicator>` | **YES — once, prominently.** | Single-indicator citation page; the map is the headline visual + sources + methodology + CSV. |

**The card on `/s/<state>` (Jony's spec):**
- Indicator title (single, deduplicated H3).
- Big number = latest value for this state.
- Sparkline = this state's series over the available time range.
- One-line rank: *"3rd of 28 states, 2024."*
- Footer link: *"See all states →"* → `/i/<indicator>` (or `/t/<topic>` if the indicator page doesn't exist yet).

**Citizen sanity check** ✅ — addresses all four citizen complaints from the walkthrough (page length, no India context dump, "what does this number mean for me", "stay in my state").

---

## 3. The 5 suggestions → expanded list with agent ratings

Original 5 were drafted by the orchestrator. Agents added items, regraded, and disputed the ordering. Below: the **superset list**, each item rated, with the **ordering dispute called out as an open question** (§5).

| # | Item | Class | Citizen | Jony | Hans | Max | Fowler |
| -- | ---- | ----- | :-----: | :--: | :--: | :-: | :----: |
| 1 | **Delete India choropleths from `/s/<state>`** (replace with sparkline + rank + link out per card) | Behavioural | ✅ | A | ✅ | ✅ | B (only after #2) |
| 1.5 | **Rebuild left rail** per §1 above (3 groups, state-aware, delete duplicates & mislabels) | Structural+B | ✅ | A | (silent — no objection) | (silent) | (subsumes most of #5) |
| 2 | **Add `/s/<state>/t/<topic>` route** (stub, lists topic indicator cards for that state) + sidebar links repointed | Structural | ✅ | A− | ✅ | ✅ (needs #6 first) | A — *strangler-fig prereq* |
| 2.5 | **Indicator-card spec** (sparkline + big number + rank + link out) — used by #1, #2, #4 | Structural | ✅ | required | (implicit) | (implicit) | (implicit) |
| 3a | **Fix duplicated H3 at the card-title slot** (one root-cause bug → 332 symptoms vanish) | Structural | ✅ | required | (silent) | (silent) | A (Fowler's "ship today" pick) |
| 3b | **Strip developer copy from "YOUR GOVERNMENT" card** | Behavioural | ✅ | required | (implicit) | (silent) | A− |
| 3c | **Humanise home-page Theme dropdown** (hide raw slugs behind labels) | Behavioural | ✅ | required | (silent) | (silent) | A− |
| 4 | **Reframe `/s/<state>` Overview as 6-section page** (identity, headline numbers, politics, topic shelves, places, provenance) | Big — Level 4 | ✅ | B (defer) | ✅ (needs #6+#7) | ✅ (needs #6) | C — *big-bang risk; its own arc* |
| 5 | **Rename "Explore trends" → "Election explorer"** | Structural (rename) | (n/a) | **D — delete the rail item entirely (subsumed by #1.5)** | ✅ rename, but flag district-drill gap | ✅ rename | A — pure rename, ship today |
| 6 | **Lock headline-tile indicator picks** (Hans's 5 + Max's 6 reconciled — see §4 below) | Editorial decision | (n/a) | required | required | required | (needed before #2 stub renders content) |
| 7 | **Lock per-topic deep-dive indicator picks** (5–8 per topic — Max's spec, see §4) | Editorial decision | (n/a) | required | required | required | (needed before #2/#4) |
| 8 | **Lazy-mount any maps that survive** via IntersectionObserver + vitest contract `≤ N maps mounted at first paint` | Behavioural | (invisible) | (implicit) | (silent) | (silent) | required (Fowler) |
| 9 | **Test gate per CLAUDE.md §15** — every commit touching `/s/<state>` or new `/s/<state>/t/<topic>` extends `frontend/e2e/golden-path.spec.ts` (route loads, no `pageerror`, DOM assertion, `SourceList` assertion) | Process gate | (invisible) | (implicit) | (implicit) | (implicit) | required (Fowler) |
| 10 | **Data-recency badge on every headline number** ("FY 2023-24 · latest available") | Behavioural | (implicit in wishlist) | (silent) | required (Hans) | (implicit) | (silent) |
| 11 | **"What changed this year" one-sentence prose strip** above headline numbers (Plain Facts discipline) | Behavioural | (implicit in wishlist) | (silent) | required (Hans) | (silent) | (silent) |
| 12 | **Catalogue gaps to scout next** — PLFS labour-force participation, ASER learning outcome (Max's pick) | New ingest | (implicit) | (silent) | ✅ | required (Max) | (out of scope here) |

---

## 4. Headline numbers (Hans) × Topic-shelf tiles (Max) — reconciled

The 6-section overview (§3 #4) needs two indicator commitments:

- **Section 2 — "The state right now"** = 3-5 headline numbers (Hans's editorial pick).
- **Section 4 — Six topic-shelf tiles** = one number per tile (Max's editorial pick).

These overlap heavily and align cleanly. Proposed reconciliation:

| Topic tile (Max) | Tile indicator (Max) | Hans's "right now" pick? | Hans's comparison frame |
| --- | --- | --- | --- |
| Money & debt | `outstanding_liabilities_pct_gsdp` | **Yes** (also includes `gross_fiscal_deficit_pct_gsdp` as a 2nd number) | vs FRBM 3% ceiling + state's 5-yr trend |
| Power & energy | `at_and_c_losses_pct` | (not in Hans's 5 — open Q) | vs national median, vs state's 5-yr trend |
| Economy & jobs | `per_capita_nsdp_constant` | **Yes** | vs all-India per-capita NDP, same year, same base |
| People & health | `imr` | **Yes** | vs all-India IMR + state's IMR 5 yrs prior |
| Environment | `pm25_annual_mean` (population-weighted) | **Yes** | vs WHO 5 µg/m³ + Indian NAAQS 40 µg/m³ |
| Transport | `ev_share_of_new_registrations` | (not in Hans's 5 — open Q) | vs national EV share, same year |

**Headline-number recommendation (5 numbers, max):** Money (outstanding liabilities %GSDP), Money (fiscal deficit %GSDP — paired with FRBM ceiling), Economy (per-capita NSDP), Health (IMR), Environment (PM2.5). Energy and Transport ride on their topic tiles (one screen below).

**Per-topic deep-dive picks** (Max's spec, 5–8 per topic; the rest stay catalogue-only at `/i/<indicator>`):

- **Money & debt → 6 indicators** on `/s/<state>/t/fiscal`: outstanding liabilities, gross fiscal deficit, revenue deficit, own-tax revenue, share of central taxes + grants, interest payments. **~16 fiscal indicators stay catalogue-only** (Union twins, pension expenditure, external debt, gross/net/devolution decompositions, etc.).
- **Power & energy → 7 indicators** on `/s/<state>/t/energy`: AT&C losses, ACS-ARR gap, installed capacity by source share (one stacked indicator, not 8 separate), peak demand met %, per-capita consumption, renewable share of generation, RE pipeline GW. **~31 energy indicators stay catalogue-only**.
- Same pattern (tile + 5–7 deep-dive + long catalogue tail) for the other four topics.

---

## 5. Open questions — RESOLVED 2026-05-15

### Q1 — Order: ship #1 first or #2 first?

**Decision: Jony's order.** *("Doesn't matter, all of them have to be done; no urgency in one going before the other.")*

Final sequence: **#0 (H3 root-cause) → #1 (delete India choropleths from `/s/<state>`) → #1.5 (rail rework) → #2 (state-aware sidebar + `/s/<state>/t/<topic>` stub route) → #2.5 (card spec) → #3a/b/c (hygiene splits) → #4-DEFERRED.**

**Caveat from Fowler (acknowledged, mitigation in place):** shipping #1 before #2 deletes the India view from `/s/<state>` before its dedicated home (`/s/<state>/t/<topic>`) exists. Mitigation: the new card on `/s/<state>` includes a *"See all states →"* footer link pointing to the existing `/t/<topic>` page (which already has India choropleths today). The citizen never has zero options for the India view; they just temporarily lose state context on that one click — same as today's broken sidebar behaviour, fixed by #2 shortly after.

### Q2 — Rename or delete "Explore trends"?

**Decision: Jony wins (Frontend authority = Jony + Max).** Delete the rail item entirely as part of #1.5 (rail rework). No standalone rename commit. Election-explorer functionality migrates inside the Elections topic page, where it belongs.

### Q3 — Six-section reframe (#4) — part of this arc or separate?

**Decision: Deferred as a tracked line-item ("#4-DEFERRED").** Too big to absorb into this arc; needs its own plan doc when picked up. Tracked here so it doesn't get forgotten. Pre-conditions for promoting it out of deferred: #0–#3 all green on main, plus Hans's headline-tile picks (§4) and Max's per-topic deep-dive picks (§4) locked.

*(Note: this is the page reframe — identity / headline numbers / politics / topic shelves / places / provenance — NOT the left rail. The rail rework is #1.5 and is in scope.)*

---

## 6. Process gates (non-negotiable, per CLAUDE.md)

- **§6 Correction levels**: #1, #1.5, #3a-c, #5 are Level 1–2. #2 + #2.5 are Level 2–3. #4 is Level 4 — gets its own design pass before any code.
- **§9 Definition of Done**: every commit touching `/s/<state>` or `/s/<state>/t/<topic>` smoke-tested via integrated browser (§13).
- **§15 Test tier**: every commit extends `frontend/e2e/golden-path.spec.ts` with route loads + no `pageerror` + DOM assertion + `SourceList` assertion. The duplicated-H3 fix (#3a) needs a vitest unit asserting one `<h3>` per indicator card.
- **Two-hat discipline (Beck/Fowler)**: never mix structural + behavioural in the same commit. #3 is three separate fixes; ship as three commits.

---

## 7. Suggested first commit (Fowler's pick) — for discussion

> **Fix duplicated indicator H3 at the card-title slot — one root-cause bug, ~332 symptoms gone.**

- **Why first**: pure structural (Tidy First), Level-1, ~one file, no behaviour change. Removes visual noise that's making every other diff on `/s/tamil-nadu` unreadable. *"Make the change easy, then make the easy change."*
- **Likely files**: card-title slot inside the indicator card components under `frontend/src/lib/`. Best guess: `IndicatorIcon.svelte` is rendering its `title` prop as a text sibling instead of inside `<svg><title>…</title></svg>`. Verify before editing.
- **Test**: vitest case asserting one `<h3>` per rendered card; e2e Playwright assertion `expect(page.locator('h3', { hasText: title })).toHaveCount(1)` on `/s/tamil-nadu`.
- **Sign-off chain**: Citizen ✅ ("stop showing me stutter") · Jony required · Fowler A · Max/Hans silent (not their lens).

---

## 8. What this doc does NOT decide

- Implementation details of any of #1–#12 (delegated to per-commit subagent dispatch).
- Whether `/i/<indicator>` page exists yet (it's referenced as the destination for "See all states →"; if it doesn't exist, the link goes to `/t/<topic>` for now).
- Visual/typography decisions inside the new card spec (Jony reserves these for the spec PR).
- Naming of `/s/<state>/t/<topic>` (aligns with existing `/t/<topic>` slugs).
- Anything inside `4-DEFERRED` — that earns its own plan doc when picked up.

---

## 9. Execution plan — subagent dispatch (locked)

All commits dispatched to subagents per user direction. Main thread orchestrates + reviews + handles git.

| Step | Item | Subagent | Class | Level (§6) | Notes |
| --- | --- | --- | --- | :---: | --- |
| **0** ✅ | Fix duplicated H3 at card-title slot (one slot bug → 332 symptoms gone) | `Fowler (Engineering)` (advisor) → main thread (apply) | Structural | 1 | **DONE 2026-05-15** on branch `fix/duplicated-indicator-h3`. Root cause: `IndicatorChoropleth.svelte` passed `title={artifact.indicator.title}` to `IndicatorIcon`, which renders `<svg><title>…</title></svg>`; `Element.textContent` walks the SVG title, duplicating the heading. Fix: drop the prop (icon is decorative; component default `aria-hidden="true"` applies). Tests: vitest 10,244 ✅; Playwright golden-path 8/8 ✅ including new H3-dup regression assertion. UI verified at `/s/tamil-nadu`: H3s=332, dups=0. Awaiting user approval to merge to main. |
| **1** | Delete India choropleths from `/s/<state>`; replace each card with `big-number + sparkline + 1-line rank + "See all states →"` (links to `/t/<topic>` until `/i/<indicator>` exists) | `Fowler (Engineering)` | Behavioural | 2 | Page weight + first-paint maps drop dramatically here. Smoke-test via integrated browser per §13; e2e assertion on `/s/tamil-nadu` map count = 0. |
| **1.5** | Rebuild left rail per §1 (3 groups, state-aware, delete `Explore trends` + `Side by side` + `Centre and states` group + duplicate `Money & debt` + `Repo` + `More topics coming soon`) | `Fowler (Engineering)` | Structural+B | 2 | Sidebar links use existing `/t/<topic>` until #2 lands. Resolves Q2 (delete `Explore trends`). |
| **2** | Add `/s/<state>/t/<topic>` stub route; sidebar topic links repointed when state is selected | `Fowler (Engineering)` | Structural | 2 | Stub renders the topic's indicator cards filtered to the state, using the #2.5 card spec. |
| **2.5** | Indicator-card spec (formal): big number, sparkline, 1-line rank, "See all states →" link, source list | `Jony (UI/UX)` (spec) → `Fowler (Engineering)` (impl) | Structural | 2 | Spec = doc commit; impl = component PR. Tests: vitest for the card, Playwright for one rendered card. |
| **3a** | Strip dev copy from "YOUR GOVERNMENT" card | `Fowler (Engineering)` | Behavioural | 1 | Citizen-visible copy fix. |
| **3b** | Humanise home-page Theme dropdown (hide raw schema slugs behind labels) | `Fowler (Engineering)` | Behavioural | 1 | Pull labels from indicator metadata. |
| **4-DEFERRED** | Six-section Overview reframe (identity / headline numbers / politics / topic shelves / places / provenance) | (TBD when picked up) | Big | 4 | **Deferred per Q3 decision.** Pre-condition: §4 indicator picks locked (Hans + Max) + #0–#3 green on main. Earns its own plan doc. |

**Parallel ingest workstream (unblocked, runs concurrently):**
- New indicators may be ingested at any time. They MUST declare a `topic` field on their schema (gates whether the schema needs a Tier-A bump per CLAUDE.md §11 before the IA work catches them).
- Max's scouting picks (PLFS labour-force participation, ASER learning outcome) explicitly approved to run in parallel.
- Coordination rule: ingest commits do NOT change the indicator-card data contract (the JSON shape `Indicator*.svelte` consumes) while #0–#3 are in flight. New indicators yes; new contract shapes only via their own Level-2 commit with `x-version` minor + `x-changelog`.

### 9.1 Active ingest queue (added 2026-05-15)

| Track | Owner doc | Status | Blocks IA work? |
| --- | --- | --- | --- |
| **ICED Air Quality — NO2 / SO2 / PM10** (mechanical clones of the just-shipped PM2.5 ingest) | [TODO/20260515-iced-aq-no2-so2-pm10-handover.md](20260515-iced-aq-no2-so2-pm10-handover.md) | Ready to pick up. Parser is already pollutant-agnostic; this is 3 ingest function clones + catalogue wiring (2 files). | No — additive only. |
| **State health ingest — Statement 27 / Statement 37 / HBS T5/T7/T16/T17** (RBI HBS + State Finances) | [TODO/20260515-health-ingest-handover.md](20260515-health-ingest-handover.md) | P0 = `health/state_health_expenditure_share_of_total_expenditure_pct` (Statement 27). Subsequent waves (life expectancy, MMR, capacity) follow per the handover sequence. | No — additive only. Statement 37 gated behind a docs-first crosswalk per the handover. |

### 9.2 Schema coordination — RESOLVED 2026-05-15 (no bump needed)

Earlier draft of this section proposed a Tier-A bump on `indicator.schema.json` to add an `indicator.topic` field (claimed Step #2 needed it to filter cards). **That was wrong.** [ADR-0022](../docs/architecture/decisions/0022-place-first-ia-with-topic-catalogue.md) deliberately put topic membership on the **catalogue** (`datasets/reference/in/topic-catalogue.json`), not on the artifact, "to keep `indicator.schema.json` free of IA leakage". Step #2 reads `topic-catalogue.json`'s `topics[].artifacts[]` directly — that mapping already exists. **No schema bump. No new field. Do not re-propose without overturning ADR-0022.**

Lesson banked: when a schema description says *"deliberately not here"*, read the linked ADR before bumping.

### 9.3 Parallel ingest — collision risk (RESOLVED 2026-05-15)

Earlier draft worried that parallel ingests would race on `topic-catalogue.json` and `upstream-sources.json`. Re-checked: both ingests in flight (ICED `environment` topic, RBI Statement 27 `fiscal`/new `health` topic) edit different topic objects in the catalogue (no diff overlap), and append to the end of the `upstreams[]` array (trivial 1-line rebase if it ever conflicts). Hygiene rule: each subagent on its own branch, main thread merges sequentially. No structural change required.

**Execution discipline:**
- Two-hat (Beck): never structural + behavioural in the same commit.
- Test gate (CLAUDE.md §15): every commit touching `/s/<state>` or `/s/<state>/t/<topic>` extends `frontend/e2e/golden-path.spec.ts` (route loads, no `pageerror`, DOM assertion, `SourceList` assertion).
- UI verification (CLAUDE.md §13): every behavioural commit smoke-tested via integrated browser before marking done.
- Subagents return diffs + test runs to the main thread for review before merge.

---

## 10. Awaiting from user

- ✅ ~~Green light to dispatch Step #0~~ — done. Step #0 staged on `fix/duplicated-indicator-h3`. **Need approval to merge to main** (no push; merge-only on local).
- **Decide §9.2 schema coordination** — Option A (pre-bump 1.4 → 1.5 to add `indicator.topic`) recommended. This is the next Level-2 commit if approved.
- **Confirm parallel ingest queue order** — pickMerged to main as `634f6d0` (no push).
- ✅ ~~Decide §9.2 schema coordination~~ — withdrawn (see §9.2: ADR-0022 already covers this).
- **In flight**: naming-policy doc (`docs/concepts/indicator-naming.md`) by `Hans (Governance)` + `Max (Indicator Scout)` + `Fowler (Engineering)`. Locks indicator-id slug shape, scope-prefix, unit suffix, comparability marker, and citizen-readable title convention before two ingests mint ids in different conventions.
- **Queued (after naming doc lands)**: parallel ingest dispatch — ICED NO2/SO2/PM10 + RBI Statement 27 health-share, each on its own branch. Main thread merges sequentially.

---

## 11. Return path to the original IA arc

This sub-arc (Step #0 + naming doc + 2 ingests) was triggered by the user's "Go for step zero and ICED + health ingest" direction on 2026-05-15. Once the queued items above land, the next move is back to **Step #1** of the original execution table (§9): delete India choropleths from `/s/<state>` and replace each with the `big-number + sparkline + 1-line rank + "See all states →"` card. Steps #1.5, #2, #2.5, #3 then continue per §9.

This file is the single source of truth for "where are we in the IA rework". Sub-arcs that don't materially change the IA plan (Step #0 fix, ingest of new indicators, naming-policy doc) are tracked here as side notes; they do not redefine the spine.

---

## 12. Orthogonal follow-up arc — 2026-05-16

The IA-reset arc surfaced six items that were OFF the original spine but worth closing before further IA work, per user direction "go ahead and do the orthogonal follow up which is not in the original plan and surfaced during the arc". Tracked here so the audit trail stays one document. Branch: `fix/comparability-ladder-canshowrank` (named after the first item; the branch carried all six since they cluster around the same risk surface). All commits local; no push without explicit instruction.

| # | Surface                                                  | Resolution                                                                                                                                                              | Commit(s)                          | Status |
|---|----------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------|--------|
| 1 | `themeCaption` resolves caption from indicator slug      | Add optional `titleMap?` 3rd param to `themeCaption`; Home.svelte passes `indicator_titles` map. Caption now reads "Outstanding liabilities (% of GSDP)" not the slug.   | `740dd3e`                          | DONE   |
| 2 | `/data/boundaries/in/manifest.json` 404 on every page    | Not-a-bug. `sources.ts:212` already falls through to GeoJSON tier gracefully; only cosmetic console noise. Follow-up: emit empty stub manifest from `tools/boundaries/`. | (none — diagnostic)                | NOT-A-BUG; stub follow-up FILED |
| 3 | `.notes.json` sidecars failed `datasets-conform` (§12)   | Gregor Option B: bump `indicator-notes.schema.json` v1.0→v1.1 (additive `sources[]`); backfill 10 sidecars with `sources:[]`; teach `catalogue-coverage` to skip sidecars; ADR-0002 clarification + `data-provenance.md` example. | `282dcaf`                          | DONE   |
| 4 | `canShowRank` cast + ladder mismatch                     | Widen TS `comparability` union to v1.5 ladder + add `RendererRuleSlug` (structural commit); rewrite `canShowRank` as switch, drop both `as` casts, add 3 tests, doc fix (behavioural commit).                                       | `dae6c7e` + `eeb0c7c`              | DONE   |
| 5 | Rail labels vs catalogue titles disagreed                | Jony Option B: rail wins. Edit 6 catalogue titles to citizen voice; collapse `THIS_STATE_TOPICS` to id-only; builder derives label from `topic.title`; new rail-fit contract test; e2e specs updated. Page H1s now agree with rail.   | `ef0207b`                          | DONE   |
| 6 | v1.5 `renderer_rules` description said "TBD"             | Add `docs/concepts/indicator-naming.md` §10 (ladder + vocabulary + 3-place change rule); flip schema description to reference the doc. Description-only edit, no `x-version` bump.                                                  | `80a0c9f`                          | DONE   |

**Lessons logged** (also written to `/memories/lessons.md`):
- A schema enum extension MUST update its paired TS union in the same Tier-A commit. Drift forces runtime casts that live for sprints.
- A controlled-vocabulary field MUST ship with its reference doc at field-definition time. "TBD" in a schema description is technical debt with a half-life of weeks.
- Any file declaring `$schema` is a contract surface and carries the full §12 envelope — no filename-pattern exemptions. If a schema FORBIDS what the contract REQUIRES (as v1.0 indicator-notes did), the schema is the bug.
- Two in-app surfaces that show the same thing MUST share their string source. A synonym table between them is evidence the canonical name is wrong, not the synonyms.

**Deferred** (NOT done this arc, surfaced for next user decision):
- Overview reframe (was the user's "section 6 review" item) — explicitly deferred per user "I will take it up as a separate item".
- Boundaries-manifest stub emit (#2 follow-up) — small `tools/boundaries/` change to mint an empty `manifest.json` so the loader doesn't emit a 404. Cosmetic; can land any time.

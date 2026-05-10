# Cross-state comparison

> **Status**: design rationale, written 2026-05-11. The comparison view itself is in Phase 6D — see [`TODO/PLAN.md`](../../TODO/PLAN.md). This doc captures what fair comparison *means* before we commit to widgets.

## The mandate

User mandate, 2026-05-11: *"the idea is we should be able to compare states' performance and categorise them based on categories like how are we doing on power."* yen-gov began as an election-data viewer; cross-state comparison is the next evolution.

The seductive but wrong answer is "rank states on every indicator and call the highest-ranked the winner." This document explains why that is wrong, what the right primitives are, and what the site will and will not do.

## Five ways naive comparison goes wrong

### 1. Attribution geography mismatch

Some indicators measure where an asset *sits*; others measure where service is *consumed*. Aggregating "installed power capacity" by the state in whose polygon the plant stands is a *siting* statistic, not a *service* statistic. Talcher (Odisha) feeds the Eastern grid; Kudankulam (TN) is a central-sector station serving five southern states under CEA allocations.

**What we do**: every indicator declares `attribution_geography ∈ {where_produced, where_consumed, where_billed, where_resident, where_administered}`. Maps with `where_produced` indicators show an explicit banner: *"This map shows where the asset is sited, not who uses it."* Ranked tables suppress the rank column for `where_produced` indicators.

### 2. Centre vs state attribution

A "states ranked on health" map credits or blames the state government. Reality: NHM funds 60% of district-hospital recurring costs; Samagra Shiksha funds the bulk of elementary-school teacher salaries; PMAY-G builds the houses; Jal Jeevan Mission lays the pipes. The state's discretion is largest in **own-tax effort, agriculture extension, police, land records, and intra-state transport**, and shrinks rapidly elsewhere.

**What we do**: indicators carry optional `funding_split` (centre%/state%/source) and `implementing_authority ∈ {state, centre, joint, local_body, parastatal}`. The renderer surfaces these as a chip next to the indicator title — e.g. *"Per-capita electricity consumption · Centre + state"*. The citizen sees attribution at first glance, not buried in a footnote.

### 3. Fiscal devolution baseline

Bihar receives roughly ₹1.30 from the divisible pool for every ₹1 it raises in own-tax revenue; Maharashtra receives roughly ₹0.15. Comparing their "social-sector spend per capita" without showing the fiscal context credits/blames the wrong actor. Until the `fiscal/` baseline is ingested (see Phase 6.0 in PLAN.md), every economic and social indicator is missing the context that makes it interpretable.

**What we will do**: ingest RBI *State Finances: A Study of Budgets* as the first new indicator family. Then on every economic/social indicator's page, render a one-line strip: *"TN: own-tax 6.8% of GSDP, devolution ₹4,200/capita, CSS ₹3,800/capita (FY 2024-25, RBI)."* This is the single most powerful fairness intervention the site can make.

### 4. Methodology vintage and series breaks

GSDP at constant prices has had three base years in living memory (2004-05, 2011-12, 2017-18). Census is 2011 + projections (2021 round indefinitely postponed). NFHS rounds are years apart with sampling-frame changes. UDISE became UDISE+ in 2018-19 with definition changes for "school" and "enrolment".

**What we do**: indicators declare `methodology_vintage` (free-form string, e.g. `"GSDP base 2011-12"`) and `series_breaks[]` (`{at_time, kind, note}`). Charts must draw a vertical marker at each break and refuse to compute growth rates that cross one. (The compute-rate check is planned; the chip is live.)

### 5. Special-category states + UTs

Eight North-Eastern states + Uttarakhand + Himachal + J&K (UT) + Ladakh have 90:10 CSS funding ratios (vs 60:40), Article 371 carve-outs, NEC and DoNER allocations, and a separate central ministry. UTs without legislatures (A&N, Lakshadweep, Chandigarh, DNH&DD, Ladakh) do not have a Council of Ministers; the LG is the executive. Delhi and Puducherry have legislatures with limited powers.

**What we do**: `state.schema.json` v3.3 added optional `tier ∈ {general_category, special_category_neh, special_category_hill, ut_with_legislature, ut_without_legislature, nct_delhi}`. Default cross-state ranked tables filter to `general_category` (28 → 18 entities), with a "Include special-category and UTs" toggle plus a one-line caveat. Small-multiples and category-index views always include all 36 entities — the visual itself communicates difference; ranking is what's misleading.

## Comparison primitives — what we will build

The four primitives we considered, ranked from "default" to "specialist":

### A. Ranked table (default, citizen-first)

One row per state, sortable by the chosen indicator, with the user's "home" state pinned and visually distinct. Three columns by default: name, value, decile bar. Reads on a phone without horizontal scroll.

This is the answer to *"how does my state stack up on X?"* — the citizen's first question. It uses the same `IndicatorRow[]` data the choropleth uses; no new primitive is required.

### B. Compare-two view

The user picks a second state; both rows are highlighted in the ranked table; a side-by-side strip above the table shows the absolute and per-capita gap. Optional: small line chart of both states' trajectories when `times.length > 1`.

This answers *"how is my state doing vs my neighbour?"* — the second-most-asked civic question.

### C. Small-multiples (specialist)

The same indicator over time, one tiny chart per state, on a single page. Lets the citizen spot trajectory differences (is Kerala growing solar faster than TN?). Useful when `times.length` is large and the *shape of change* is the story rather than the level.

### D. Category index (deferred indefinitely)

A weighted composite ("development score") looks great in design mocks but is the worst option for civic data. It hides the trade-offs that *are* the story (Kerala high on literacy, low on industrial output) and a static-first deployment can't credibly let users re-weight the index. We will not ship a default category index. We may surface bucket-internal *medians* for orientation, never composites.

### Not on the roadmap (for good reason)

- **State-card grids**: scan all 30 cards but never compare two specifically. Designer-bait, not user need.
- **Choropleth as the comparison primitive**: a colour ramp answers "where is the high concentration" much better than "is X better than Y by how much". Maps stay on the indicator detail view; ranked tables drive comparison.

## Indicator categories — starting taxonomy

From the Governance Strategist review, eight buckets ordered by governance leverage rather than data availability. Each lists the canonical 2–3 indicators and the issuing authority. All are publicly available; none requires login.

| Category | Canonical indicators (2–3) | Authority |
|---|---|---|
| **`fiscal/`** *(the baseline that contextualises everything else)* | own-tax revenue % GSDP; devolution per capita; debt-to-GSDP | **RBI** — *State Finances: A Study of Budgets* |
| **`economy/`** | GSDP at constant prices (2011-12 series); per-capita NSDP; sectoral GVA share | **MoSPI** + **RBI** *Handbook of Statistics on Indian States* |
| **`demographics/`** | total population (Census 2011 + UIDAI projection); decadal growth; sex ratio at birth | **RGI / Census** + **CRS** |
| **`human_development/`** | IMR; under-5 mortality; total fertility rate; institutional-delivery share | **NFHS-5** + **SRS** (RGI) |
| **`education/`** | adult literacy; GER secondary & higher-secondary; pupil-teacher ratio; ASER reading-level | **UDISE+** (MoE) + **AISHE** + **ASER** (Pratham) |
| **`livelihood/`** | LFPR (15+); unemployment rate (CWS); MGNREGA person-days per rural household | **PLFS** (MoSPI) + **MoRD MIS** + **Labour Bureau** |
| **`infrastructure/`** | electrification % households; piped-water % households; road density; rail route-km | **CEA / MoP** + **JJM dashboard** + **MoRTH** + **Indian Railways Year Book** |
| **`governance/`** *(meta-bucket: how well the machinery functions)* | criminal cases pending per 1000 population; IPC cognisable crime rate; CPGRAMS disposal time | **NJDG** + **NCRB** + **CPGRAMS** + **CIC** |

Notes:

- **`fiscal/` is listed first** because it must be ingested before any economic or social indicator is rendered with full context.
- **`governance/` is the highest marginal-utility category** for yen-gov — it is the bucket most underserved by existing aggregators (PRS, India Data Portal, Niti Aayog dashboards).
- **Avoid Niti Aayog composite indices** (SDG India Index, Health Index, School Education Quality Index) as primary inputs. They are weighted aggregates with their own methodology choices; reproduce from underlying indicators when needed.

## Visualisations beyond the choropleth

The IndicatorChoropleth is the entry point. The following are planned for Phase 6D, each driven by the same indicator metadata so no per-indicator code is needed:

1. **Stacked-area "where the money comes from"** — for budget indicators, with `funding_split` driving the segments. Citizen reads "of every ₹100 spent on X in TN, ₹60 came from the Centre".
2. **Decile strip with home-state pin** — companion to the ranked table; one tall bar showing the national distribution with a marker where "your" state sits.
3. **Convergence/divergence panel** — for time-series indicators, plot every state's change-from-baseline against its starting level. Shows whether laggards are catching up or stagnating.
4. **Per-capita switch** — when an indicator has a `denominator`, a toggle re-renders the choropleth and ranked table per-capita. Defaults: per-capita on for `count`-kind indicators with declared denominator; absolute on for `share`/`rate`/`index`.

## Five questions a policy researcher would ask

These are the questions yen-gov should be able to answer end-to-end. The first two are addressable with already-planned data; the last three motivate Phase 6E indicator depth.

1. *"For TN, of every ₹100 the state government spends on health, how much originates from the Centre vs own revenue, and how has that mix changed across the last three CMs?"* — needs `fiscal/`, state-budget functional classification, and CM-term overlay (already in `governments/`).
2. *"Which states have improved IMR fastest after controlling for their starting level?"* — needs NFHS rounds + convergence-panel viz.
3. *"In the 2024 LS election, which AC segments swung against the incumbent state government, and does that swing correlate with district-level distress indicators?"* — needs PC-2024 results disaggregated to AC segments + district-level MGNREGA + bivariate AC choropleth.
4. *"How much of the variation in per-capita NSDP across states is explained by sectoral composition vs Centre-to-state transfers vs own-tax effort?"* — needs GSDP sectoral GVA + RBI fiscal indicators + a scatter/decomposition view.
5. *"For each centrally-sponsored scheme, which states are leaving allocated funds unspent, and is the underspend correlated with administrative capacity or with political alignment with the Union government?"* — politically loaded, requires neutral framing — present both correlates side-by-side, let the citizen judge.

## Decisions log

- **2026-05-11 — Ranked table is the default comparison primitive, not state-card grid or category index.** Citizen-first. Rank suppressed for `not_comparable_across_states` indicators.
- **2026-05-11 — `state.tier` enum added to `state.schema.json` (v3.3)** so ranked tables can default-filter to general-category states. UTs and special-category states are includable via toggle, never silently mixed in.
- **2026-05-11 — Composite indices off the roadmap.** They hide the trade-offs that *are* the story.
- **2026-05-11 — Fiscal baseline is the next ingest, not more election data**, per Governance Strategist re-ordering. Without `fiscal/`, every economic/social indicator ships without context.

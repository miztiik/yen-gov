# State fiscal health (the indicator vocabulary)

**Last Updated**: 2026-06-25

**Owner**: data layer (Hans owns the governance framing; Max owns coverage; Jony + Citizen own how it renders)

**See also**: [data-spine](data-spine.md), [owid-alignment](owid-alignment.md), [indicator-naming](indicator-naming.md), [fiscal-actor-naming](fiscal-actor-naming.md), [cross-state-comparison](cross-state-comparison.md), the source + ingest plan in [sources-rbi-state-finances](../architecture/backend/sources-rbi-state-finances.md), and the live inventory in [data-coverage-report](../reference/data-coverage-report.md).

## The citizen question this concept serves

> "How does my state manage public money - what it earns, what it spends, how big the gap is, and how much debt it is piling up - and is that healthy or not?"

A single rupee figure cannot answer that. "My state spent INR 50,000 crore" means nothing without "out of what income, against what economy, leaving what gap." This doc names the **globally-recognised vocabulary** a public-finance economist, an IMF Government Finance Statistics (GFS) desk, a Finance Commission member, or an IAS Finance Secretary uses to judge a **sub-national** government's fiscal health, and the **framing traps** each one carries. It is the dictionary; the source that feeds it and the exact indicator definitions live in [sources-rbi-state-finances](../architecture/backend/sources-rbi-state-finances.md).

## Three rules before any number

1. **Level + ratio, never level alone.** An absolute INR-crore level favours big states and hides whether a number is large or small *relative to the economy*. Every headline fiscal fact ships as a level (INR crore) AND a ratio (per cent of GSDP, or per cent of revenue receipts). The ratio is what makes Bihar and Maharashtra comparable.
2. **Composition beats magnitude.** A deficit that builds roads and irrigation is investment; the same-sized deficit that pays salaries and interest is the disease. The honest read of a deficit is *what it financed*, so the deficit indicators always travel with the revenue-vs-capital split.
3. **One methodology-stable series.** A new edition of the source is an UPSERT of the same indicator, never a re-mint (the [data-spine](data-spine.md) Rosling rule). A definition change (base-year rebase, territory split, a perimeter change) is a `methodology_breaks` row rendered as a visible break on the line, never a silent jump.

## The indicator set

Ranked by how load-bearing each is for judging a state government. "Direction" is the honest reading - several are deliberately **neutral** because a naive good/bad colouring would mislead.

| # | Indicator | What it measures | Honest direction | FRBM / FC anchor | The citizen trap |
| - | --------- | ---------------- | ---------------- | ---------------- | ---------------- |
| 1 | **Revenue Deficit / GSDP** | Is the state borrowing just to fund day-to-day running (salaries, pensions, interest, subsidies)? | Lower better; **zero / surplus genuinely IS the goal** | FRBM target = revenue balance (RD = 0) | The most damning single signal, yet citizens confuse it with the fiscal deficit. RD > 0 = eating the seed corn. |
| 2 | **Gross Fiscal Deficit (GFD) / GSDP** | Total borrowing requirement as a share of the economy (all spending beyond non-borrowed income) | Lower *generally* better - but **not zero**; a developing state SHOULD borrow to build (the golden rule) | ~3% GSDP FRBM ceiling, with FC flexes for power-sector reform; 4-5% in COVID years | "Deficit = bad." A deficit financing capital assets is investment; one financing the wage bill is the disease. Composition (rule 2) matters more than level. |
| 3 | **Primary Deficit / GSDP** | GFD minus interest payments - the deficit you would run with no inherited debt | Lower better; a primary surplus means current policy is not adding to the burden | implicit in the GFD glide path | The blame disentangler - separates *this* government's choices from *yesterday's* interest bill. |
| 4 | **Outstanding Liabilities / GSDP** | Accumulated debt **stock** as a share of the economy | Lower better | N.K. Singh FRBM combined 60% (centre ~40 / states ~20); per-state legislated anchors ~20-25% | STOCK (cumulative) vs FLOW (this year's deficit) - citizens conflate them. The denominator is each state's own base-year GSDP, so sub-1pp year-on-year moves are inside the noise band. |
| 5 | **Interest Payments / Revenue Receipts** | How much of every rupee earned is pre-committed to servicing old debt | Lower better; ~10% comfortable, high-teens = stress | FC flags high ratios | The debt-trap early warning. A state can have "fine" debt/GSDP yet a strangling IP/RR if its revenue base is thin. |
| 6 | **Own-Tax Revenue / GSDP** (tax effort) | How hard the state taxes its own economy | Higher *generally* better, with a ceiling | ~6-8% typical for a mid-size state | A rich state can run a LOW own-tax/GSDP and be fine (large base); a poor state with HIGH effort is straining its citizens. Not a governance scoreboard. |
| 7 | **Own Revenue / Total Revenue** (self-reliance) | Share of income the state raises itself vs receives from the Centre | Higher = more autonomy - but **low is NOT automatically failure** | - | **The most dangerous framing in the set.** "Your state lives off Delhi's money" ignores that the Finance Commission formula *deliberately* equalises toward poorer and special-category states. |
| 8 | **Committed Expenditure / Revenue Receipts** (salaries + pensions + interest) | How much income is locked in before a single new scheme | Lower better; > ~50% = severe rigidity | - | The "how much room does my state actually have to govern?" number. Where salaries are not separable in the source, only a partial (pensions + interest) proxy can be shown, and it must say so. |
| 9 | **Capital Outlay / GSDP** (and capex / total expenditure) | Building durable assets vs running the machine | Higher *generally* better (build vs maintain) | - | The worst Budget-vs-Actuals gap of any indicator - states over-budget capex and under-spend it. The citizen must see Actuals, not the Budget Estimate. |
| 10 | **Development Expenditure share** (social + economic services / total) | Share going to human and physical capital vs administration and debt service | Higher dev-share generally better | - | "Developmental" is an accounting class, not an outcome. INR on education is an INPUT, not a literate child. |

### The two pairings the level-only view hides

- **Quality of the deficit = Revenue Deficit / Gross Fiscal Deficit.** A GFD that is 100% capital is healthy; one that is 80% revenue deficit is a crisis. The same headline GFD/GSDP can be either.
- **Decompose the GFD** into the revenue half (eating the seed corn) and the capital half (building assets). This is the single most important honest framing for the deficit indicators.

## The four framing traps

These hold for any state-fiscal source. The renderer carries the corrective or the indicator does not ship.

1. **Estimate stage (Budget vs Revised vs Actuals).** Budgets carry three numbers per year: the **Budget Estimate** (the aspiration tabled before the year ran - the only number that exists for the newest one or two years), the **Revised Estimate** (a mid-year revision), and the **Accounts / Actuals** (audited, what actually happened, ~2-year lag). A BE is a *political document*: capex is systematically over-budgeted and under-spent, deficits under-budgeted and overshot. Plotting recent-year BE against old-year Actuals on one line lets the citizen read aspiration as achievement. **Corrective:** one coalesced "best realisation" series (Actuals where available, else Revised, else Budget), the chosen stage carried as per-row provenance and the estimate tail rendered visually distinct. Never splice a Budget Estimate onto an Actuals series without the stage tag.
2. **The GSDP-denominator base year.** A ratio is only honest when numerator and denominator share a base year. State GSDP is rebased by MoSPI (1993-94 / 1999-2000 / 2004-05 / 2011-12), so a deficit/GSDP ratio computed across a rebase boundary mixes two definitions. **Corrective:** stamp the GSDP base year used, carry the rebase boundaries as breaks on derived ratios, and treat the publisher's own published ratio as a correctness oracle, surfacing material divergence rather than hiding it.
3. **The self-reliance / blame instinct.** A choropleth that paints transfer-dependent states red as "living off Delhi" credits or blames a state government for what the Finance Commission formula *engineers on purpose* (devolution equalises toward poorer and special-category states; GST compensation withdrawal and the devolution cycle move the ratio independently of any state choice). **Corrective:** every fiscal-federal ratio (self-reliance, tax effort, transfer dependence) ships with the co-determinant caveat or it does not ship. This is the Rosling "blame" instinct, and it is the highest-risk colouring in the whole pillar.
4. **Development = input, not outcome.** "Development expenditure" and "social services expenditure" are accounting classes. High education spend is an INPUT; it is not a literate child. **Corrective:** never imply an outcome from a spend line; pair with an outcome indicator (literacy, IMR) where one exists, and label the spend as an input.

## Stock vs flow, and what cannot be derived from a budget

A budget (receipts and expenditure flows) gives you the **deficit** (a flow) honestly, but it does **not** give you:

- **Debt stock** (Outstanding Liabilities). Accumulating annual borrowing flows forward is error-prone, misses the opening balance, write-offs, and conversions. Debt stock comes from the publisher's dedicated debt statement, not reconstructed from flows.
- **Contingent liabilities** (state **Guarantees** to public-sector undertakings and special-purpose vehicles - where states park off-balance-sheet borrowing). Not in any budget; a separate statement.

So a complete state-fiscal-health picture is **budget flows (deep, one source) + debt stock + guarantees (separate, shallower sources)**. The indicator that is *missing* is as much a part of the honest picture as the one that is present.

## What yen-gov has, needs, and does not have

The live, dated inventory is [data-coverage-report](../reference/data-coverage-report.md); the acquisition plan and exact indicator definitions are in [sources-rbi-state-finances](../architecture/backend/sources-rbi-state-finances.md). In summary, as of 2026-06-25:

- **Have (but shallow / wrongly sourced):** own-tax, non-tax, central-tax-devolution, grants-in-aid, revenue-expenditure - all per-state but only a ~7-year window (FY2016-FY2022) and sourced from a one-off Parliamentary answer, not the issuing authority. Plus pension expenditure, net transfers, outstanding-liabilities/GSDP, and national-only gross fiscal deficit.
- **Need (the headline gaps):** per-state Gross Fiscal Deficit, Revenue Deficit, Primary Deficit, Capital Outlay, Interest Payments, Total Revenue Receipts, and the ratios in the table above - plus a 36-year (FY1991-FY2026) re-source of the five shallow series above, from the issuing authority.
- **Do not have / cannot derive from a budget:** state Guarantees (contingent liabilities); a longer-than-current debt-stock back-history.

The RBI *State Finances: A Study of Budgets* e-STATES Database supplies the budget-flow half of this for all states across 36 years; see the source doc for how it maps to every indicator above.

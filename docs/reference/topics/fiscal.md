# Fiscal

> Topic spine for the [`fiscal/`](../../../datasets/indicators/in/fiscal/) indicator family.
> Per-indicator pages link UP to this page for shared methodology that
> would otherwise repeat across siblings.

**Last Updated**: 2026-05-15
**Maintainer**: yen-gov contributors
**Plan**: [TODO/PER-INDICATOR-DOCS-PLAN.md](../../../TODO/PER-INDICATOR-DOCS-PLAN.md)

## What this topic covers

The `fiscal` topic captures the **revenue and expenditure accounts of the Union and the States** — the two government layers that the Indian Constitution endows with independent taxation and spending powers. The artifacts here are the standard public-finance flows (own-tax revenue, devolution, grants, revenue and capital expenditure, fiscal-deficit aggregates) and the standard stocks (outstanding liabilities, external debt). Almost every series is sourced from the Reserve Bank of India's two annual Handbooks of Statistics — the *Indian Economy* handbook for Centre and all-India aggregates, and the *Indian States* handbook for per-state series.

What is **adjacent but NOT here**:

- **GSDP / NSDP denominators** live under [`economy/`](../../../datasets/indicators/in/economy/) — fiscal indicators that need a denominator (debt-to-GSDP, deficit-to-GSDP) reach into the economy topic for it.
- **Inflation-indexation of nominal flows** uses [`prices/`](../../../datasets/indicators/in/prices/) — when interpreting a multi-year nominal series like state pension expenditure, deflate against `prices/national_cpi_combined_index_annual` (post-2012) or splice with `prices/national_cpi_iw_index_annual` for the longer back-history.
- **Quasi-fiscal liabilities** carried by state-owned electricity discoms (the ACS-ARR gap, AT&C losses, off-balance-sheet debt) live in [`energy/`](../../../datasets/indicators/in/energy/) — they are economically fiscal but the data lineage is power-sector regulatory, not RBI HBS.
- **Election-cycle expenditure / freebie commitments** are descriptive narrative, not budget-line data, and are intentionally absent from this catalogue.

## Upstream sources

| Source | What they publish | Cadence | License |
| --- | --- | --- | --- |
| RBI Handbook of Statistics on the Indian Economy ([landing](https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy)) | Centre fiscal aggregates (Tables on Union Government finances), all-states-combined deficits, transfers from Centre to states (gross / net / grants / devolution) | Annual (Sep–Oct release for prior FY) | RBI publication, attribution-required, redistributable for non-commercial |
| RBI Handbook of Statistics on Indian States ([landing](https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States)) | Per-state revenue and expenditure heads, pension, debt-to-GSDP, share in central taxes, grants-in-aid | Annual (Dec release for prior FY) | RBI publication, attribution-required |
| Union Budget — Receipts & Expenditure documents ([indiabudget.gov.in](https://www.indiabudget.gov.in/)) | Centre's own A/RE/BE numbers (RBI's HBS-IE compiles from here) | Annual (1 February) | Government publication |
| State Budgets (state Finance department portals) | Per-state A/RE/BE; only intermittently scraped — RBI HBS-IS is the canonical re-publisher | Annual | Varies by state |
| Finance Commission reports ([fincomindia.nic.in](https://fincomindia.nic.in/)) | Award-period devolution formula and grant allocations | Once per 5-year award cycle | Government publication |

## Series anchors (what to read for which question)

| Question | Canonical answer | Why |
| --- | --- | --- |
| "How much is the Union Government borrowing this year?" | [`fiscal/union_gross_fiscal_deficit`](../../../datasets/indicators/in/fiscal/union_gross_fiscal_deficit.json) | This is the FRBM headline number, glide-path-anchored, Budget-Day commentary's centre-piece. Pair with [`fiscal/union_primary_deficit`](../../../datasets/indicators/in/fiscal/union_primary_deficit.json) to strip out interest. |
| "How much are all states combined borrowing this year?" | [`fiscal/states_combined_gross_fiscal_deficit`](../../../datasets/indicators/in/fiscal/states_combined_gross_fiscal_deficit.json) | The Centre + states-combined "general government" deficit is the IMF / rating-agency view; this is its states component. |
| "How indebted is a particular state?" | [`fiscal/outstanding_debt_pct_gsdp`](../../../datasets/indicators/in/fiscal/outstanding_debt_pct_gsdp.json) | The 15th FC's 20%-by-FY25 anchor. A ratio, so movement reflects both numerator (stock) and denominator (nominal GSDP). |
| "How much fiscal autonomy does this state have?" | [`fiscal/state_own_tax_revenue_inr_crore`](../../../datasets/indicators/in/fiscal/state_own_tax_revenue_inr_crore.json) divided by [`fiscal/state_revenue_expenditure_inr_crore`](../../../datasets/indicators/in/fiscal/state_revenue_expenditure_inr_crore.json) | "Own-tax / total-spend" is the cleanest read on whether the state can pay for itself or depends on Centre transfers. |
| "How dependent on the Centre is this state?" | [`fiscal/state_share_central_taxes_inr_crore`](../../../datasets/indicators/in/fiscal/state_share_central_taxes_inr_crore.json) + [`fiscal/state_grants_in_aid_inr_crore`](../../../datasets/indicators/in/fiscal/state_grants_in_aid_inr_crore.json) | Devolution + grants together capture the constitutional and discretionary Centre flows. |
| "Is the Centre cutting transfers to states?" | [`fiscal/centre_transfers_to_states_net`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_net.json) | Net of loan repayments. Pair with [`fiscal/centre_transfers_to_states_gross`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_gross.json) to see whether the gap reflects gross compression or repayment churn. |
| "What is the cess-vs-divisible-pool composition?" | Read [`fiscal/centre_transfers_to_states_tax_devolution`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_tax_devolution.json) (the constitutional share) against the Centre's Receipts Budget table on cess + surcharge collections. The yen-gov corpus does not yet carry an explicit cess artifact. | The cess-share-of-gross-tax wedge is the structural states-vs-Centre fiscal grievance of the 2020s. |
| "Is OPS / pension cost a fiscal-stability risk for state X?" | [`fiscal/state_pension_expenditure_inr_crore`](../../../datasets/indicators/in/fiscal/state_pension_expenditure_inr_crore.json) divided by [`fiscal/state_own_tax_revenue_inr_crore`](../../../datasets/indicators/in/fiscal/state_own_tax_revenue_inr_crore.json) | Pension is committed revenue expenditure; its share of own-tax is the cleanest read on residual discretionary room. |
| "How tight is the Centre's primary stance after stripping out interest?" | [`fiscal/union_primary_deficit`](../../../datasets/indicators/in/fiscal/union_primary_deficit.json) | The cleanest read on the *current* government's fiscal posture, free of legacy debt-servicing inheritance. |

## Conceptual taxonomy

### Centre vs States vs General Government

The Indian fiscal architecture has three vantage points and a careful reader should know which one the chart is showing:

- **Union (Centre) only** — Union Budget receipts and expenditure, owned by the Ministry of Finance. The headline `union_gross_fiscal_deficit` series goes back to FY 1986-87 in the RBI HBS-IE.
- **All states combined** — sum across 28 states + UTs with legislatures, before consolidating intergovernmental transfers. This is the lens that lets you ask "how much are sub-national governments borrowing in aggregate?" without per-state granularity. The `states_combined_*` artifacts hold these aggregates.
- **General government** — Centre + states combined and *consolidated* (intergovernmental transfers netted out). This is the IMF / rating-agency view and the only number directly comparable across countries. yen-gov does not yet emit a `general_government_*` series; it can be derived as Centre deficit + states-combined deficit minus the share of Centre transfers that finances state spending, but the consolidation is non-trivial because the Centre's gross loans to states are not a deficit financing item for states.

### Divisible-pool tax devolution vs cess vs grants vs loans

Centre-to-state money flows in four legally distinct streams. Conflating them is the single most common error in fiscal commentary:

1. **Divisible-pool devolution** ([`centre_transfers_to_states_tax_devolution`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_tax_devolution.json)). The states' share in net Centre tax revenue (excluding cess and surcharge), set by each Finance Commission for a five-year award. The 14th FC raised it to 42%; the 15th FC trimmed to 41% on J&K's UT-isation. This is constitutional, formulaic, and untied — states can spend it as they choose.
2. **Cess and surcharge.** Sit *outside* the divisible pool. Their share of Centre's gross tax receipts has roughly doubled since FY12 (~10% to ~20%+), shrinking the share of Centre's tax base that states have any constitutional claim on. yen-gov does not yet carry a stand-alone cess artifact; it can be inferred from the gross-tax-vs-divisible-pool gap in the Receipts Budget.
3. **Grants-in-aid** ([`centre_transfers_to_states_grants`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_grants.json)). Three families: (a) Finance Commission grants (post-devolution revenue deficit, local-body, SDRF, sector-specific); (b) Centrally Sponsored Scheme grants (PMAY, MGNREGA, PMGSY, Samagra Shiksha — Centre share); and (c) Central Sector Scheme transfers. Grants are largely *tied* — strings attached.
4. **Loans.** Gross loans from Centre to states ([`centre_transfers_to_states_gross`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_gross.json) minus the devolution + grants components) net of repayments give the [`centre_transfers_to_states_net`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_net.json) wedge. Most legacy Centre-state loans were converted to grants on 14th FC's recommendation, so the gross-vs-net gap has narrowed sharply since FY15.

### Revenue vs Capital and Gross Fiscal Deficit decomposition

Every government's annual financing requirement (gross fiscal deficit, GFD) decomposes as:

> GFD = revenue deficit + capital expenditure + net lending − non-debt capital receipts

The `*_revenue_deficit` artifacts isolate the *revenue* side — the gap that exists before any capital spending. A revenue-deficit-funded GFD is widely considered worse than a capital-expenditure-funded one (the former finances current consumption with future taxes; the latter finances assets that will themselves help service the debt). The `*_primary_*` artifacts strip out interest payments, isolating the *current* government's borrowing posture from the legacy interest inheritance — interest is the only fiscal line item this year's Finance Minister cannot influence.

### A vs RE vs BE — the three vintages of every Indian budget number

Almost every fiscal series in the corpus carries values at three different epistemic tiers depending on year:

- **Actuals (A)** — audited outturns. Available for years two or more behind the most recent Budget.
- **Revised Estimates (RE)** — the executive's mid-year update on the prior-year number, presented alongside the new Budget. RE figures are revised one more time when actuals come in.
- **Budget Estimates (BE)** — the plan for the year being budgeted. Citizens should treat BE as a *commitment to try* rather than an outturn.

The RBI HBS strips the (A) / (RE) / (BE) suffix from column headers at parse time, so artifacts do not carry it inline; the [`fiscal/state_pension_expenditure_inr_crore`](../../../datasets/indicators/in/fiscal/state_pension_expenditure_inr_crore.json) artifact is the prototype that records the per-period revision tier in the new `revision_tier_by_period[]` field (schema 1.5+). Apply the same vintage discipline to *every* fiscal artifact: the most recent two fiscal years are almost always RE/BE and **must not be charted with the same visual weight as Actuals**. Renderers that surface fiscal artifacts should distinguish A from RE/BE (different stroke, label suffix, or shaded tail).

### Finance Commission award windows

The Finance Commission (FC) is the constitutional body that, once every five years, sets the vertical share of Centre tax revenue going to states (the devolution percentage) and the horizontal share among states (the inter-state formula). The relevant award periods overlapping this corpus are:

- **13th FC** — FY 2010-11 to FY 2014-15. Vertical: 32%.
- **14th FC** — FY 2015-16 to FY 2019-20. Vertical: 42% (a sharp jump that re-shaped state finances from FY16 onwards). Horizontal formula introduced "demographic change" (1971-vs-2011 population shift) over the objections of the southern states.
- **15th FC** — FY 2020-21 to FY 2025-26. Vertical: 41% (the 1pp reduction reflects J&K's UT-isation; UTs are not in the divisible pool). The 15th FC's headline target was debt/GSDP at 20% by FY25 — a target that, on the [`fiscal/outstanding_debt_pct_gsdp`](../../../datasets/indicators/in/fiscal/outstanding_debt_pct_gsdp.json) chart, almost no major state will meet.
- **16th FC** — constituted Dec 2023, award covers FY 2026-27 to FY 2030-31. Will revisit both vertical devolution and the horizontal formula. The southern-states-vs-Hindi-belt fiscal politics around 2011-population weighting is the live political-economy conversation behind every 16th FC artifact in the next two years.

When reading any fiscal artifact across an FC-award boundary, expect a level shift in the year of the new award (FY16, FY21, FY27 in the future).

## Vintage and revision discipline

The dominant revision pattern in this topic is the **A/RE/BE cycle** described above. RBI re-publishes its Handbook annually, and each new edition restates the prior year's RE as A, the prior year's BE as RE, and adds a new BE. An indicator value tied to FY 2024-25 in the 2024-25 HBS edition (BE) will be a different number in the 2025-26 edition (RE) and different again in the 2026-27 edition (A). The artifact's `methodology_vintage` field records the HBS edition the values came from; readers comparing across yen-gov re-pulls should treat the most-recent two years as provisional.

There are a small number of structural revision moments that matter for this topic:

- **Centre data quality jump after Budget restructuring (2018, removal of Plan/Non-Plan distinction).** Pre-FY18 Union expenditure series carry a Plan / Non-Plan split that disappears thereafter; the *aggregates* (revenue, capital, total) are continuous, but anyone trying to splice the legacy Plan series across FY18 will find a false discontinuity.
- **GST rollout (1 July 2017).** State own-tax composition shifted overnight: VAT, entry tax, octroi, luxury tax and entertainment tax were subsumed into SGST. The aggregate ([`fiscal/state_own_tax_revenue_inr_crore`](../../../datasets/indicators/in/fiscal/state_own_tax_revenue_inr_crore.json)) is continuous but autonomy *within* it dropped because every SGST rate change requires GST Council assent.
- **GST compensation cess termination (June 2022).** The 14% YoY revenue-growth guarantee to states ended; states whose pre-GST own-tax revenue was growing slower than 14% saw a permanent revenue cliff in FY23 — visible on the chart for BIMARU-grouping states.
- **COVID-era deficit relaxations (FY21–FY23).** The FRBM ceiling was raised to 5% (FY21), 4% (FY22) and 3.5% (FY23) for the Centre; states got an additional 0.5%-of-GSDP borrowing window each year tied to power-sector reforms (15th FC). All `*_fiscal_deficit` artifacts show a sharp spike in FY21 and a multi-year glide back.
- **15th FC's 0.5% conditional borrowing window for power-sector reform.** States like Andhra Pradesh, Punjab and Rajasthan have used it heavily; this leaks fiscal-stress signal into the [`energy/`](../../../datasets/indicators/in/energy/) topic via discom finances.

## Comparability gotchas

- **J&K UT-isation (October 2019).** From FY21 onwards Jammu & Kashmir is no longer in the divisible-pool denominator (it's a UT, financed directly by the Centre). Reading per-state shares of devolution, this is why every other state's share ticks up slightly from FY21 — the same pie, one slice removed. Aggregate `states_combined_*` series simply lose J&K from FY21 forward.
- **Telangana split (June 2014).** Andhra Pradesh and Telangana appear as separate entities in fiscal artifacts from FY15 onwards. The pre-split AP fiscal flows are not redistributed retroactively; analysts who want a continuous AP-residual or composite AP+Telangana series must construct it themselves.
- **Per-state vs all-states-combined.** The yen-gov fiscal corpus has both lenses but at different temporal depth. Per-state series (`state_*`) are the RBI HBS-IS tables, currently FY16 onwards; all-states-combined (`states_combined_*`) are the RBI HBS-IE tables, FY07 onwards. For long-history all-India fiscal stress, use the combined series; for state-vs-state ranking in the current decade, use the per-state.
- **Nominal vs real (price-deflation).** Every artifact in the topic is in nominal ₹ Crore. A 10% YoY growth in pension expenditure during a year of 7% CPI inflation is roughly 3% real growth, not 10%. Charts that show fiscal levels over 10+ years should either deflate using [`prices/national_cpi_combined_index_annual`](../../../datasets/indicators/in/prices/national_cpi_combined_index_annual.json) (or the spliced WPI/CPI-IW for deeper history) or normalise by GSDP / total expenditure to control for nominal growth.
- **Comparability ladder (4-level).** Most fiscal indicators are at level 3 (`comparable_within_state_over_time`) when read as raw ₹ Crore — Maharashtra and Sikkim are not directly rankable on a debt-stock basis. They become level 1 (`comparable_across_states_and_time`) once normalised by GSDP, population, or own-revenue. The [`fiscal/outstanding_debt_pct_gsdp`](../../../datasets/indicators/in/fiscal/outstanding_debt_pct_gsdp.json) artifact is one of the few in the topic that ships at level 1 because the denominator is baked in.

## Related topic spines

- **[Economy](../../../datasets/indicators/in/economy/)** — every fiscal ratio (debt/GSDP, deficit/GSDP, own-tax/GSDP, capex/GSDP) reaches into the economy topic for its denominator. The `economy/state_gdp_current_inr_lakh_crore` and `economy/state_per_capita_nsdp_*` family are the canonical denominators.
- **[Prices](./prices.md)** — every nominal fiscal time-series benefits from price-deflation; CPI-Combined is the right anchor for post-2012 reads.
- **[Demography](../../../datasets/indicators/in/demography/)** — per-capita fiscal reads (per-capita capex, per-capita revenue receipts) need population from `demography/state_population_lakhs`.
- **[Energy](./energy.md)** — discom AT&C losses and ACS-ARR gaps are *quasi-fiscal* liabilities of state governments. State-budget subsidy transfers to discoms appear in `state_revenue_expenditure_inr_crore`; the off-budget portion shows up only in the energy topic's discom-finance artifacts.

## Indicator pages in this topic

- [`fiscal/centre_transfers_gross`](../../../datasets/indicators/in/fiscal/centre_transfers_gross.json) — Per-state gross transfers from Centre (devolution + grants + gross loans), FY17–FY23.
- [`fiscal/centre_transfers_to_states_grants`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_grants.json) — All-India Centre-to-states grants (CSS + FC grants + State Plan legacy + statutory), FY08 onwards.
- [`fiscal/centre_transfers_to_states_gross`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_gross.json) — All-India gross transfers (Item IV = devolution + grants + gross loans), FY08 onwards.
- [`fiscal/centre_transfers_to_states_net`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_net.json) — All-India net Centre-to-states transfers (gross minus loan repayments and interest), FY08 onwards.
- [`fiscal/centre_transfers_to_states_tax_devolution`](../../../datasets/indicators/in/fiscal/centre_transfers_to_states_tax_devolution.json) — All-India divisible-pool devolution (the FC-formula stream), FY08 onwards.
- [`fiscal/net_transfers_from_centre`](../../../datasets/indicators/in/fiscal/net_transfers_from_centre.json) — Per-state net Centre-to-State transfers, FY24–FY26.
- [`fiscal/outstanding_debt_pct_gsdp`](../../../datasets/indicators/in/fiscal/outstanding_debt_pct_gsdp.json) — Per-state outstanding liabilities as % of GSDP, end-March, FY08 onwards.
- [`fiscal/state_external_debt_inr_crore`](../../../datasets/indicators/in/fiscal/state_external_debt_inr_crore.json) — Per-state external debt outstanding (one-shot Rajya Sabha snapshot, ~Aug 2023).
- [`fiscal/state_grants_in_aid_inr_crore`](../../../datasets/indicators/in/fiscal/state_grants_in_aid_inr_crore.json) — Per-state grants-in-aid received from Centre, FY17–FY23.
- [`fiscal/state_non_tax_revenue_inr_crore`](../../../datasets/indicators/in/fiscal/state_non_tax_revenue_inr_crore.json) — Per-state non-tax revenue (interest, dividends, royalties, user charges), FY17–FY23.
- [`fiscal/state_own_tax_revenue_inr_crore`](../../../datasets/indicators/in/fiscal/state_own_tax_revenue_inr_crore.json) — Per-state own-tax revenue (SGST, excise, stamp duty, MV tax), FY17–FY23.
- [`fiscal/state_pension_expenditure_inr_crore`](../../../datasets/indicators/in/fiscal/state_pension_expenditure_inr_crore.json) — Per-state pension expenditure (revenue account), FY05–FY25.
- [`fiscal/state_revenue_expenditure_inr_crore`](../../../datasets/indicators/in/fiscal/state_revenue_expenditure_inr_crore.json) — Per-state total revenue expenditure (salaries, pensions, interest, subsidies, scheme outlays), FY17–FY23.
- [`fiscal/state_share_central_taxes_inr_crore`](../../../datasets/indicators/in/fiscal/state_share_central_taxes_inr_crore.json) — Per-state share in divisible-pool central taxes, FY17–FY23.
- [`fiscal/states_combined_gross_fiscal_deficit`](../../../datasets/indicators/in/fiscal/states_combined_gross_fiscal_deficit.json) — All-states-combined gross fiscal deficit, FY08 onwards.
- [`fiscal/states_combined_primary_deficit`](../../../datasets/indicators/in/fiscal/states_combined_primary_deficit.json) — All-states-combined primary deficit (GFD minus interest), FY08 onwards.
- [`fiscal/states_combined_primary_revenue_deficit`](../../../datasets/indicators/in/fiscal/states_combined_primary_revenue_deficit.json) — Strictest fiscal-discipline indicator, all-states, FY08 onwards.
- [`fiscal/states_combined_revenue_deficit`](../../../datasets/indicators/in/fiscal/states_combined_revenue_deficit.json) — All-states-combined revenue deficit, FY08 onwards.
- [`fiscal/union_gross_fiscal_deficit`](../../../datasets/indicators/in/fiscal/union_gross_fiscal_deficit.json) — Centre's gross fiscal deficit, FY87 onwards. The headline FRBM number.
- [`fiscal/union_primary_deficit`](../../../datasets/indicators/in/fiscal/union_primary_deficit.json) — Centre's primary deficit, FY87 onwards.
- [`fiscal/union_primary_revenue_deficit`](../../../datasets/indicators/in/fiscal/union_primary_revenue_deficit.json) — Centre's primary revenue deficit, FY87 onwards.
- [`fiscal/union_revenue_deficit`](../../../datasets/indicators/in/fiscal/union_revenue_deficit.json) — Centre's revenue deficit, FY87 onwards.

## Further reading

- **RBI, *State Finances: A Study of Budgets***, annual. The most authoritative analytical companion to the per-state HBS tables; flags structural risks (OPS, discom losses, off-budget borrowing) that the bare numbers alone do not surface. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3a+A+Study+of+Budgets>.
- **Finance Commission of India.** Award reports for 13th, 14th, 15th, and the in-progress 16th FC. <https://fincomindia.nic.in/>.
- **Comptroller & Auditor General, *Reports on State Finances***, per-state. The audit lens — flags off-budget borrowing, scheme-execution failures, contingent-liability creep that RBI's compilation does not capture. <https://cag.gov.in/>.
- **Ministry of Finance, *Indian Public Finance Statistics***, annual. Centre's own publication, deeper Centre-side detail than HBS-IE. <https://dea.gov.in/>.
- **Ministry of Finance, Union Budget documents.** Receipts Budget, Expenditure Profile, Finance Bill, Annual Financial Statement. <https://www.indiabudget.gov.in/>.

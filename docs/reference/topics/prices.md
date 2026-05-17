# Prices

> Topic spine for the [`prices/`](../../../datasets/indicators/in/prices/) indicator family.
> Per-indicator pages link UP to this page for shared methodology that
> would otherwise repeat across siblings.

**Last Updated**: 2026-05-15
**Maintainer**: yen-gov contributors
**Plan**: [TODO/PER-INDICATOR-DOCS-PLAN.md](../../../TODO/PER-INDICATOR-DOCS-PLAN.md)

## What this topic covers

The `prices` topic carries **price-level indices and inflation rates** at the national and state level. India publishes three structurally different price series — Wholesale Price Index (WPI), CPI for Industrial Workers (CPI-IW), and CPI-Combined (Rural+Urban) — and a careful reader needs to know which one answers which question. The topic also carries the state-wise CPI sub-baskets (general, food, fuel-and-light, housing) that NSO releases monthly and yen-gov annual-averages.

What is **adjacent but NOT here**:

- **CPI sub-baskets that NSO does not publish per-state** — most notably *rural* housing CPI (NSO publishes urban-only because rural housing is imputed differently in the methodology). The [`prices/state_cpi_housing_urban_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_housing_urban_inflation_pct.json) artifact carries the urban-only series with the rural absence flagged inline.
- **GDP deflator** (the implicit price-level deflator for nominal GDP) lives under [`economy/`](../../../datasets/indicators/in/economy/). It is conceptually the broadest inflation measure but it's a *derived* number from National Accounts, not a directly-collected price series.
- **Food procurement prices** (MSP, central-issue price, FCI economic cost) are agriculture-policy artifacts and live elsewhere; they influence WPI and CPI-Food but are not price-level indices in their own right.
- **Asset prices** — equities, real-estate transaction prices, gold — are not in scope for the consumer / producer inflation lens this topic covers.

## Upstream sources

| Source | What they publish | Cadence | License |
| --- | --- | --- | --- |
| Office of the Economic Adviser, MoCI ([eaindustry.nic.in](https://eaindustry.nic.in/)) | Wholesale Price Index, all commodities and sub-groups | Monthly (15-day lag) | Government publication, attribution-required |
| Labour Bureau, MoLE ([labourbureau.gov.in](https://labourbureau.gov.in/)) | CPI for Industrial Workers (CPI-IW) | Monthly | Government publication |
| National Statistical Office (NSO/MoSPI) ([mospi.gov.in](https://www.mospi.gov.in/)) | CPI-Combined (Rural+Urban), CPI-Rural, CPI-Urban; sub-basket breakdown by state | Monthly (12-day lag) | Government publication |
| RBI Handbook of Statistics on Indian Economy ([landing](https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy)) | Annual averages of WPI and CPI series — yen-gov's actual ingest path for the national series | Annual (Sep–Oct) | RBI publication, attribution-required |

The yen-gov pipeline reads RBI HBS-IE annual averages (Tables 36 and 37) for the national WPI and CPI series rather than ingesting MoCI / Labour Bureau / NSO directly — RBI is the authoritative re-publisher and ships pre-spliced annual averages, which is what the artifact contract here needs. State-wise CPI sub-baskets are read from MoSPI's monthly bulletin and annual-averaged at parse time.

## Series anchors (what to read for which question)

| Question | Canonical answer | Why |
| --- | --- | --- |
| "What is India's official inflation rate?" | [`prices/national_cpi_combined_index_annual`](../../../datasets/indicators/in/prices/national_cpi_combined_index_annual.json), converted to YoY in the renderer | RBI's monetary-policy anchor since the Feb 2015 framework agreement and the 2016 Monetary Policy Committee Act. The 4% ± 2% inflation target is on this series. |
| "How much have prices risen for an industrial worker over a 30-year window?" | [`prices/national_cpi_iw_index_annual`](../../../datasets/indicators/in/prices/national_cpi_iw_index_annual.json) | The deepest continuous CPI India publishes, FY94 onwards. Used for DA (Dearness Allowance) calculations for Centre and PSU employees. |
| "What was producer-stage inflation 40 years ago?" | [`prices/national_wpi_all_commodities_index_annual`](../../../datasets/indicators/in/prices/national_wpi_all_commodities_index_annual.json) | The deepest historical price series (FY75 onwards), but spliced across 5 base years and weakly comparable across the splices. Read directionally only. |
| "Which state has the highest food inflation this year?" | [`prices/state_cpi_food_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_food_inflation_pct.json) | The Food and Beverages sub-basket carries ~46% weight in CPI-Combined; food shocks (tomato, onion, pulses) drive headline CPI volatility. |
| "How are LPG / electricity tariff hikes hitting households?" | [`prices/state_cpi_fuel_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_fuel_inflation_pct.json) | The Fuel and Light sub-basket bundles LPG cylinder, kerosene, electricity tariff, firewood — captures the per-state pass-through from the Centre's LPG subsidy regime and SERC tariff orders. |
| "How fast are urban housing rents rising?" | [`prices/state_cpi_housing_urban_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_housing_urban_inflation_pct.json) | NSO's Housing CPI is urban-only by methodology; it captures owner-equivalent rent and actual contract rent in urban centres. |
| "What is general headline CPI by state?" | [`prices/state_cpi_general_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_general_inflation_pct.json) | The state-level YoY corresponding to national CPI-Combined. |

## Conceptual taxonomy

### WPI vs CPI-IW vs CPI-Combined — three measures, three jobs

The three Indian price indices differ on **what they measure**, **whose basket they price**, and **how they weight the basket**. Treating them as interchangeable is the most common mis-read in Indian inflation reporting.

| Dimension | WPI | CPI-IW | CPI-Combined |
| --- | --- | --- | --- |
| Stage of transaction | Producer / first point of bulk sale | Consumer (retail) | Consumer (retail) |
| Whose basket | National economy (commodities) | Industrial-worker households at 88 centres | All-India households (rural + urban) |
| Services included | Largely no (a few electricity / freight items) | Yes, household services | Yes, full services basket |
| Food weight | ~24% | ~39% | ~46% |
| Housing | Excluded | Yes (small) | Yes (~10%) |
| Compiling agency | Office of Economic Adviser, MoCI | Labour Bureau, MoLE | NSO, MoSPI |
| Base year | 2011-12 | 2016 | 2012 |
| Series start (annual) | FY 1974-75 | FY 1993-94 | FY 2014-15 (CPI-Combined; CPI-Rural and CPI-Urban from FY 2011-12) |
| Used for | Industrial-input price tracking, GDP deflator inputs, escalation clauses in commercial contracts | DA calculations for Centre / PSU employees | RBI's monetary-policy inflation target (4% ± 2%) since 2016 |

**Operating rule:**

- For **monetary-policy framing**, "RBI is on track / off track on inflation," "is the MPC behind the curve" — use CPI-Combined.
- For **wage / pension indexation in policy debate** — use CPI-IW (it is what DA formulas reference).
- For **historical inflation 30+ years back** or **producer-side inflation pass-through to industry** — use WPI, but read directionally.
- **Never quote WPI as 'India's inflation' in a citizen-facing context** — the press still routinely conflates WPI with retail inflation; this is wrong.

### Headline vs core vs food and fuel

CPI-Combined decomposes into:

- **Food and beverages** (~46% weight) — the biggest single driver of headline volatility. Vegetables, pulses, cereals are the swing components.
- **Fuel and light** (~10%) — LPG, kerosene, electricity tariff, firewood. Highly policy-driven (LPG subsidy, ATF excise pass-through, SERC tariff orders).
- **Core** — headline excluding food and fuel. The cleaner read of demand-side / wage-push inflation. yen-gov does not yet ship a separate `core_inflation` artifact; it is a sub-totalling derivation of the full sub-basket structure.
- **Housing** (~10%, urban only). Slow-moving; tracks owner-equivalent and contract rent in urban centres.
- **Clothing and footwear, transport and communication, recreation, education, health, personal care and effects, miscellaneous** — the remainder.

The state-wise sub-basket artifacts in this corpus cover the four most-watched sub-indices: general, food, fuel-and-light, and housing-urban. The other sub-baskets (clothing, transport, education, health) are available in the same MoSPI bulletin but are not yet ingested by yen-gov.

### Index level vs YoY rate — keep the level, compute the rate

Every yen-gov price artifact at the national level (WPI, CPI-IW, CPI-Combined) ships as **index level**, not YoY rate. The renderer is responsible for computing growth. This is deliberate:

- A level series can always be re-rebased in the renderer (visualise base = 2012 or base = FY15 = 100 as needed); a YoY rate series cannot.
- Splice handling (see below) is honest only on levels — taking YoY of a spliced index across a rebase produces a meaningless number.
- Base-period choice for a particular chart is a presentation concern, not an artifact concern.

The state-wise sub-basket artifacts are an exception: NSO publishes them as YoY % directly, and yen-gov re-publishes that. The trade-off is that a chart that wants to plot the state-wise *level* cannot do so without re-pulling the underlying monthly index.

### Producer-stage WPI as a leading indicator

WPI tends to lead CPI-Food and CPI-Fuel by 1–3 months at major price shocks (a kharif crop failure, a global crude spike, an LPG-subsidy reset). Analysts use the WPI–CPI gap as a rough early-warning signal for the next print of headline CPI. This is one of the few citizen-facing reasons to keep tracking WPI even though monetary policy has moved entirely to CPI.

## Vintage and revision discipline

### Base-year splices — the structural break that breaks renderers

WPI, CPI-IW, and CPI-Rural/Urban all undergo periodic **base-year revisions**: the basket of goods is updated, weights are reweighted from the latest household-consumption survey, and the index is re-anchored to a new base year (= 100). The level series is then **spliced** across the rebase using the overlap-period ratio. yen-gov ships the spliced series with a `series_breaks[]` entry at every splice point and a `renderer_rules: ["no_growth_across_break"]` guard that the chart layer must honour.

The full splice history this corpus tracks:

- **WPI** ([`prices/national_wpi_all_commodities_index_annual`](../../../datasets/indicators/in/prices/national_wpi_all_commodities_index_annual.json)): 1970-71 → 1981-82 (FY82), 1981-82 → 1993-94 (FY94), 1993-94 → 2004-05 (FY05), 2004-05 → 2011-12 (FY12). The current base is 2011-12. A fifth rebase to base 2017-18 has been long pending — the WPI revision committee report exists but the new series has not gone live; when it does, expect another splice entry.
- **CPI-IW** ([`prices/national_cpi_iw_index_annual`](../../../datasets/indicators/in/prices/national_cpi_iw_index_annual.json)): 1960-61 → 1982 (FY82), 1982 → 2001 (FY01), 2001 → 2016 (FY16). The current base is 2016, with the centre coverage expanded from 78 to 88.
- **CPI-Combined** ([`prices/national_cpi_combined_index_annual`](../../../datasets/indicators/in/prices/national_cpi_combined_index_annual.json)): single base (2012) so far. A rebase to base 2024 (or thereabouts) is in the NSO pipeline but not yet released; when it does, the new base will be tagged in `series_breaks[]`.

The `no_growth_across_break` renderer rule is the correctness guard: a YoY computation that crosses a splice point produces a number that is *not* an inflation rate; it is the ratio of two indices on different baskets, weights and methodologies. The chart must skip that bar / draw a hatched gap, not pretend the values are commensurable.

### Revision tier — much smaller than fiscal

CPI and WPI series do *not* share the A/RE/BE problem the fiscal topic has. Once a month's index is published, it is provisional for one month and final thereafter (CPI-Combined explicitly carries a "F" / "P" flag in the bulletin). Annual averages computed from monthly indices stabilise within ~6 weeks of the fiscal-year close. The biggest revision risk is **base-year-revision back-revisions**: when WPI or CPI-IW is rebased, the entire spliced history can shift by 0.1–0.3 percentage points on every YoY in the affected window. This is captured by the `series_breaks[]` discipline above.

### Annual-averaging convention

Every price artifact at fiscal_year time-grain in this corpus is the **simple arithmetic average of the 12 monthly indices for the fiscal year (April–March)**. This matches the RBI HBS publishing convention and the citation-pattern in finance-ministry / NITI Aayog policy documents. Some IMF / World Bank publications use the **December-on-December** convention (CPI in December of year T against December of year T−1) which can differ by 50–100 basis points from the FY-average. yen-gov's choice is FY-average throughout.

## Comparability gotchas

- **WPI is `directional_only` (level 4 on the Hans comparability ladder).** A 50-year WPI level chart spans five different baskets and weighting schemes; the YoY computed across a splice is not an inflation rate. The `renderer_rules` field enforces the gap visually, but a careless analyst can still take the level series, compute simple growth, and report a wrong number — this is the single biggest mis-read risk in this topic.
- **State-wise CPI sub-baskets are level 2 (`comparable_across_states_snapshot_only`) at best.** State-CPI weights are the all-India weights re-applied to state-collected price data; states with very different consumption patterns (Northeast vs Punjab, Goa vs Bihar) carry methodological noise in the weighted aggregate. A state with rapidly-shifting consumption (e.g. Kerala, where remittance-driven demand has reshaped the basket) is harder to read than a state where consumption patterns track the all-India average.
- **CPI-IW and CPI-Combined are NOT spliceable to each other in level terms.** They have different baskets, different weights, different population universes. Charting them on the same axis as "the CPI" is technically wrong; doing it as two separate series with their own labels is fine.
- **WPI vs CPI divergence is a real economic signal, not a data error.** WPI captures producer prices (commodities + manufactured); CPI captures consumer prices (heavy services + housing). When global commodity prices fall and services inflation stays sticky, WPI prints negative while CPI prints +5%. Both numbers are correct.
- **State-wise rural housing inflation does not exist in the corpus or the upstream data.** [`prices/state_cpi_housing_urban_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_housing_urban_inflation_pct.json) is urban-only because NSO's CPI-Rural methodology imputes housing differently (it does not publish a rural housing sub-index at all). This is not a yen-gov omission; it is an upstream methodology choice that any rural-housing question must respect.

## Related topic spines

- **[Fiscal](./fiscal.md)** — every nominal fiscal time-series benefits from price-deflation; CPI-Combined is the right deflator for post-2012 reads, spliced CPI-IW for the longer back-history. Centre and state subsidy-formula indexation (LPG, fertiliser, food) reach into prices for inflation triggers.
- **[Economy](../../../datasets/indicators/in/economy/)** — real GDP and real per-capita NSDP series are deflated using the GDP deflator (NSO derived), not directly using these CPI / WPI artifacts; but the deflator is closely related to WPI for goods sectors and CPI for services sectors.
- **[Energy](./energy.md)** — fuel inflation in CPI is driven by LPG subsidy resets, ATF excise pass-through, and SERC tariff orders, all of which originate in the energy topic's regulatory artifacts.
- **[Agriculture](../../../datasets/indicators/in/agriculture/)** — CPI-Food volatility is driven by kharif / rabi crop outcomes, MSP changes, and global commodity prices; the agriculture topic carries the upstream causes of the food-inflation prints in this topic.

## Indicator pages in this topic

- [`prices/national_cpi_combined_index_annual`](../../../datasets/indicators/in/prices/national_cpi_combined_index_annual.json) — All-India CPI-Combined (Rural + Urban), base 2012=100, annual average from FY15. The RBI monetary-policy anchor.
- [`prices/national_cpi_iw_index_annual`](../../../datasets/indicators/in/prices/national_cpi_iw_index_annual.json) — CPI for Industrial Workers, spliced 1982 / 2001 / 2016 base years, annual average from FY94. Used for Centre/PSU DA indexation.
- [`prices/national_wpi_all_commodities_index_annual`](../../../datasets/indicators/in/prices/national_wpi_all_commodities_index_annual.json) — Wholesale Price Index, All Commodities, spliced across 5 base years, annual average from FY75. Read directionally only across splices.
- [`prices/state_cpi_food_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_food_inflation_pct.json) — State-wise CPI Food and Beverages YoY %, FY15 onwards.
- [`prices/state_cpi_fuel_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_fuel_inflation_pct.json) — State-wise CPI Fuel and Light YoY %, FY15 onwards.
- [`prices/state_cpi_general_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_general_inflation_pct.json) — State-wise headline CPI YoY %, FY15 onwards.
- [`prices/state_cpi_housing_urban_inflation_pct`](../../../datasets/indicators/in/prices/state_cpi_housing_urban_inflation_pct.json) — State-wise CPI Housing (urban only) YoY %, FY15 onwards.

## Further reading

- **RBI, Monetary Policy Reports**, half-yearly. The authoritative analytical companion to CPI-Combined; explains every print, the food-fuel-core decomposition, and the MPC's stance. <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Monetary+Policy+Report>.
- **Office of the Economic Adviser, MoCI — WPI Bulletin**, monthly, with the methodology note for the current 2011-12 base. <https://eaindustry.nic.in/>.
- **NSO/MoSPI, *Methodology for Estimation of Consumer Price Indices***. The technical reference for the CPI-Combined / Rural / Urban basket and weight construction. <https://www.mospi.gov.in/>.
- **Labour Bureau, *CPI-IW Methodology*** (2016 base series report). <https://labourbureau.gov.in/>.
- **Patnaik, Shah & Veronese, "Hedging inflation risk in India"** (NIPFP working paper series, multiple years). Practical analytical use of the CPI and WPI series for inflation hedging and policy analysis.

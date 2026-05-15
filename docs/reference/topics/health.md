# Health

> Topic spine for the [`health/`](../indicators/health/) indicator family.
> Per-indicator pages link UP to this page for shared methodology that
> would otherwise repeat across siblings.

**Last Updated**: 2026-05-15
**Maintainer**: yen-gov contributors
**Plan**: [TODO/PER-INDICATOR-DOCS-PLAN.md](../../../TODO/PER-INDICATOR-DOCS-PLAN.md)

## What this topic covers

The `health` topic carries **vital-statistics rates and public-health expenditure** at the state level — the four SRS-derived population-health rates (Crude Birth Rate, Crude Death Rate, Infant Mortality Rate, Total Fertility Rate) plus state public expenditure on health. It is intentionally a small, demography-of-health corpus today; the larger universe of health-system performance indicators (institutional delivery, immunisation coverage, OPD volumes, doctor-density, NCD prevalence) is governed by NFHS / HMIS and is not yet ingested.

What is **adjacent but NOT here**:

- **Population denominators** for any per-capita health-spend or per-1000 derivation are in [`demography/`](../indicators/demography/) — `demography/state_population_lakhs` is the canonical denominator.
- **NFHS (National Family Health Survey)** indicators — anaemia, child stunting, contraceptive prevalence, full immunisation, institutional-delivery, ANC coverage. These exist in periodic survey rounds (NFHS-5 in 2019-21; NFHS-6 fieldwork ongoing). Out of scope until ingested.
- **Hospital-level / facility-level data** from the Health Management Information System (HMIS) and the National Health Authority (PM-JAY claims). HMIS is monthly facility-reported data of variable quality; PM-JAY is procedural-volume data only for the empanelled-hospital subset. Both deferred per the per-indicator-docs plan.
- **Disease surveillance** (IDSP, COVID dashboards, dengue / malaria reports). Real-time epidemic signal, not the long-run vital-statistics lens this topic covers.
- **Health expenditure on the household-side** (out-of-pocket health spend, private health insurance penetration). Lives in NSO Consumption Expenditure Survey rounds and is conceptually a household-economy indicator.

## Upstream sources

| Source | What they publish | Cadence | License |
| --- | --- | --- | --- |
| Sample Registration System (SRS), Office of the Registrar General of India ([censusindia.gov.in/SRS](https://censusindia.gov.in/census.website/data/SRS)) | State-wise CBR, CDR, IMR, neonatal mortality, under-5 mortality, MMR (triennial), TFR | Annual SRS Statistical Report; TFR with one-year lag | Government publication, attribution-required |
| RBI Handbook of Statistics on Indian States ([landing](https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States)) | Re-publishes the SRS rates as Tables 2 (CBR), 3 (CDR), 4 (IMR), 6 (TFR); also Table 80 series for state public-health expenditure | Annual (Dec for prior year) | RBI publication, attribution-required |
| Civil Registration System (CRS), ORGI | Registered births and deaths — administrative not sampled | Annual report (~2-year lag) | Government publication |
| National Health Profile, Central Bureau of Health Intelligence (CBHI) | Aggregate health-infrastructure and disease-burden tables | Annual | Government publication |

The yen-gov pipeline ingests SRS rates via the RBI HBS-IS (Tables 2, 3, 4, 6) rather than the SRS Statistical Report directly. RBI is the authoritative re-publisher and ships pre-cleaned state series with the AP/Telangana split treated consistently across the back-history.

## Series anchors (what to read for which question)

| Question | Canonical answer | Why |
| --- | --- | --- |
| "How healthy is this state's mother-and-child ecosystem?" | [`health/state_infant_mortality_rate_per_1000`](../indicators/health/state_infant_mortality_rate_per_1000.md) | Single most cited summary of state public-health performance. Integrates antenatal care, institutional-delivery quality, neonatal nutrition, and immunisation coverage in one number. |
| "What stage of demographic transition is this state in?" | [`health/state_total_fertility_rate`](../indicators/health/state_total_fertility_rate.md) | Replacement-level (2.1) crossing is the demographic-transition milestone. Below-2.1 carries downstream consequences for school-age population, working-age share, dependency ratio, and pension fiscal stress (see [`fiscal/state_pension_expenditure_inr_crore`](../indicators/fiscal/state_pension_expenditure_inr_crore.md)). |
| "Is this state ageing?" | [`health/state_total_fertility_rate`](../indicators/health/state_total_fertility_rate.md) trended down + [`health/state_death_rate_per_1000`](../indicators/health/state_death_rate_per_1000.md) trending **up** for age-structural reasons | Once TFR is below replacement and CDR starts rising again, that is the population-pyramid inversion (Kerala's CDR has been creeping up since ~2017 for exactly this reason — not because public health is worsening). |
| "How much is this state spending on health from its own budget?" | [`health/state_public_health_expenditure_inr_crore`](../indicators/health/state_public_health_expenditure_inr_crore.md) | Captures Medical & Public Health + Family Welfare + Water Supply & Sanitation revenue+capital heads. Is a fiscal artifact at heart; its economic interpretation needs `economy/` denominators. |
| "Why is this state's CDR rising even as healthcare improves?" | Pair [`health/state_death_rate_per_1000`](../indicators/health/state_death_rate_per_1000.md) (rises) with [`health/state_total_fertility_rate`](../indicators/health/state_total_fertility_rate.md) (falls) and [`demography/state_population_age_bands`](../indicators/demography/) (older share rising) | CDR is *crude*: it is the per-1000 death count, unadjusted for age structure. A state with a higher share of >60 will *always* show a higher CDR even with identical age-specific mortality. |
| "How does fertility decline match birth-rate decline?" | [`health/state_birth_rate_per_1000`](../indicators/health/state_birth_rate_per_1000.md) and [`health/state_total_fertility_rate`](../indicators/health/state_total_fertility_rate.md) together | CBR is a stock outcome (births per 1000 of *all* population, including non-fertile age bands); TFR is the per-woman intensity. Both fall as a state's transition matures, but at different speeds. |

## Conceptual taxonomy

### Sample Registration System (SRS) — the sample frame that makes it possible

India does not have a complete civil-registration system that captures every birth and death in real time. The Civil Registration System (CRS) achieves >90% birth coverage but ~75% death coverage, with wide state variation (Bihar's death-registration was below 50% as recently as 2020). To produce nationally comparable vital-statistics rates, the Office of the Registrar General of India runs the **Sample Registration System (SRS)** — a dual-record system in which a part-time enumerator continuously logs vital events in a stratified panel of ~8,000 sample units (~1.5 million households, ~7 million population), reconciled twice a year against an independent half-yearly survey of the same units. The discrepancy resolution is what makes SRS more reliable than naive registration counts.

Operationally what this means for any series in this topic:

- **All SRS series carry a sampling-error margin.** Small states (Sikkim, Mizoram, Goa) have wide confidence bands; year-on-year wiggles within ±5–10% of the central estimate are noise, not signal.
- **SRS coverage of UTs is uneven.** Most artifacts in this topic carry ~22–35 entities, not the full 36 (states + UTs); the missing UTs are typically Andaman, Lakshadweep, Daman & Diu / DNH, where the SRS sample frame is too thin.
- **Rural vs urban breakdowns** are published in the SRS report but are not always re-published in the RBI HBS tables; the per-state-aggregate values in this corpus are the rural+urban combined SRS estimate.

### Calendar year, not fiscal year

SRS rates are **calendar-year** (1 January – 31 December), not fiscal-year (1 April – 31 March). This is the convention used throughout this topic — `time_grain: year` rather than `fiscal_year`. The choice matters when joining health rates to fiscal artifacts: a `2023` IMR observation is not directly mergeable with a `2023-04` (FY24) state-pension observation; one is calendar 2023, the other is fiscal 2023-24. The yen-gov entity / time taxonomy keeps these grains distinct on purpose so accidental cross-grain joins fail loudly rather than silently.

`state_public_health_expenditure_inr_crore` is the one exception in this topic — it is a budget series and uses `fiscal_year` grain consistent with the rest of the [`fiscal/`](./fiscal.md) topic.

### Crude vs age-adjusted rates

The "Crude" prefix on **Crude** Birth Rate and **Crude** Death Rate is methodologically load-bearing:

- **Crude Birth Rate (CBR)** = (live births in year) / (mid-year population) × 1000. The denominator includes everyone — children, post-menopausal women, men. So CBR depends both on the *intensity* of fertility and on the *age structure* of the population. A state with the same per-woman fertility but a younger age structure (more women in 15–49 age band) will show a higher CBR.
- **Crude Death Rate (CDR)** = (deaths in year) / (mid-year population) × 1000. Symmetrically: depends on age-specific mortality rates *and* on the age structure. Kerala and Tamil Nadu have *better* age-specific mortality than UP / Bihar at every age band but show *higher* CDR because they have a much older population.

The age-structure-confounded nature of CDR is the single biggest mis-read trap in this topic. A casual chart that ranks states by CDR and concludes "Kerala has worse health than Bihar" is wrong — Kerala has *better* health, but it's been good for so long that its population pyramid is older and the unadjusted death rate is consequently higher. The honest framing is: CBR and CDR are **demographic** indicators; IMR and TFR are **public-health-performance** indicators. Use them accordingly.

### IMR — the integrating indicator

Infant Mortality Rate (IMR = deaths under 1 year per 1000 live births) is the consensus single-number summary of state public-health performance because:

- It is age-narrow (under-1) so age-structure confounding is small.
- It depends on antenatal care quality, delivery-setting safety, neonatal-care availability, immunisation coverage, post-natal nutrition (breastfeeding, complementary feeding) — basically the full preventive-health stack.
- It correlates strongly with under-5 mortality, MMR, and life expectancy at birth, so it is a single proxy for several rates a chart can't always afford to show.
- The inter-state spread in India is wide and persistent (Kerala under 7; MP / UP near 30 in 2023 SRS), giving the chart real signal.

### TFR and the demographic transition

Total Fertility Rate is the average number of children a woman would have over her lifetime at the year's age-specific fertility rates. Replacement is conventionally 2.1 (the 0.1 above 2 covers child mortality and the slight male skew at birth). India's national TFR fell below 2.1 around 2020. State-wise the picture is:

- **Below replacement since the 1990s/2000s**: Kerala, Tamil Nadu, Andhra Pradesh, Karnataka, Punjab, Himachal, West Bengal.
- **Crossed replacement in the 2010s**: Maharashtra, Gujarat, Telangana, Odisha, J&K.
- **Still above replacement (FY23 SRS)**: Bihar (~2.9), Uttar Pradesh (~2.3), Madhya Pradesh, Rajasthan, Jharkhand, Meghalaya, Arunachal.

Once a state crosses the replacement transition, the policy-relevant question shifts from "how do we lower fertility" to "how do we manage the demographic-window opportunity, and prepare for the post-window ageing fiscal stress." This is where the [`fiscal/`](./fiscal.md) cross-link matters: a low-TFR state's pension liabilities will eventually start to dominate its discretionary fiscal space.

### Public health expenditure and the National Health Mission

[`health/state_public_health_expenditure_inr_crore`](../indicators/health/state_public_health_expenditure_inr_crore.md) sums the Medical & Public Health, Family Welfare, and Water Supply & Sanitation heads from the state revenue + capital accounts. Three structural points:

- The 2017 National Health Policy committed health spending (Centre + states combined) to 2.5% of GDP by 2025. This series tracks the state share of that target and almost no state is on track.
- A large share of state health spending is centrally co-funded under the **National Health Mission (NHM)** — so a state's "public health expenditure" is partially Centre money flowing through the state budget. The artifact does not currently disentangle the Centre-funded and state-funded shares.
- The Water Supply & Sanitation head is included by RBI's classification. Some analysts strip it out to compute a narrower "medical" health expenditure; this corpus does not yet ship that variant.

## Vintage and revision discipline

- **SRS revision pattern.** The SRS Statistical Report for calendar year T is released in late T+1 or early T+2. Within a given year the value is published once and rarely revised; state-level estimates can be revised by ±0.1 (TFR) or ±1 (IMR) in subsequent SRS sample-frame updates. The ten-year sample-frame revision (typically aligned with each Census) is the larger inflection.
- **2011-Census frame.** The current SRS sample frame is anchored to Census 2011. Census 2021 has been postponed; when the new Census is held and the SRS frame is re-stratified to the new geography, expect a one-time level shift in all per-1000 rates as the underlying mid-year population denominator updates. This will appear as a series-break candidate at the moment it lands; today the corpus carries no such break.
- **Methodology vintage** for every artifact in this topic is recorded as "RBI Handbook 2024-25 edition" (the parser run against the most recent HBS-IS). Re-running yen-gov against the 2025-26 HBS-IS will pick up the FY24 calendar-year SRS estimate and may slightly revise FY22-23 numbers if RBI has incorporated SRS back-revisions.
- **No A/RE/BE issue** in this topic — vital-statistics rates do not have the budget-vintage problem the fiscal topic has. The closest analogue is the SRS *provisional* vs *final* tag, which RBI HBS does not preserve in its re-publication.

## Comparability gotchas

- **AP / Telangana split (June 2014).** From calendar-year 2014 onwards Andhra Pradesh and Telangana appear as separate entities in SRS. The pre-split AP data is not redistributed retroactively — the historical AP series ends in 2013 and two new series start in 2014 (and in some artifacts, 2015 once SRS re-stratified its AP/T sample frames). Charts that show "all India minus J&K" or "south India" should be careful about the FY14–FY15 transition.
- **J&K UT-isation (October 2019).** SRS continues to report J&K as a single entity post-UT-isation; Ladakh is *not* separately broken out in the SRS Statistical Report. So the entity layer in this topic is more stable than the [fiscal](./fiscal.md) topic across the J&K change.
- **Crude rates are NOT directly state-rankable.** As noted above, CBR and CDR depend on age structure. Rank states on IMR or TFR (which are largely free of age-structure confound) for citizen-facing comparisons. Hans's 4-level comparability ladder would put CBR and CDR at level 3 (`comparable_within_state_over_time`) rather than level 1 (`comparable_across_states_and_time`).
- **Small-state noise.** Sikkim, Goa, Mizoram, Manipur, Arunachal, Nagaland have small SRS sample frames. Year-on-year wiggles of 5–15% in TFR or 2–4 in IMR for these states are largely sampling noise. Use 3-year moving averages for any small-state trend assertion.
- **Public-health expenditure denominators.** The [`health/state_public_health_expenditure_inr_crore`](../indicators/health/state_public_health_expenditure_inr_crore.md) artifact is a nominal ₹ Crore series. Per-capita health spend needs `demography/state_population_lakhs`; share-of-state-spend needs `fiscal/state_revenue_expenditure_inr_crore`; share-of-GSDP needs an `economy/` denominator. The artifact ships the raw level on purpose so each downstream ratio is composable.

## Related topic spines

- **[Demography](../indicators/demography/)** — population denominators for any per-capita derivation. The vital-statistics rates here describe the *flows* into and out of the population stocks the demography topic carries.
- **[Fiscal](./fiscal.md)** — `state_public_health_expenditure_inr_crore` is itself a fiscal series at heart. The downstream pension-stress consequence of low TFR is a fiscal artifact ([`fiscal/state_pension_expenditure_inr_crore`](../indicators/fiscal/state_pension_expenditure_inr_crore.md)).
- **[Education](../indicators/education/)** (when ingested) — the school-age population denominator changes with TFR; literacy and enrolment are the next-decade downstream of today's birth rates.
- **[Environment](../indicators/environment/)** — air pollution, water quality, climate-shock health-burden. Conceptually adjacent but with different data lineage.

## Indicator pages in this topic

- [`health/state_birth_rate_per_1000`](../indicators/health/state_birth_rate_per_1000.md) — Crude Birth Rate, per 1,000 mid-year population, calendar year, 2004 onwards. Demographic-transition reading; trends down across all states.
- [`health/state_death_rate_per_1000`](../indicators/health/state_death_rate_per_1000.md) — Crude Death Rate, per 1,000 mid-year population, calendar year, 2004 onwards. Age-confounded — do not rank states without an age-adjustment caveat.
- [`health/state_infant_mortality_rate_per_1000`](../indicators/health/state_infant_mortality_rate_per_1000.md) — Infant Mortality Rate, per 1,000 live births, calendar year, 2004 onwards. The single most-cited public-health-performance indicator.
- [`health/state_public_health_expenditure_inr_crore`](../indicators/health/state_public_health_expenditure_inr_crore.md) — Per-state public expenditure on health (medical + family welfare + water/sanitation), ₹ Crore, FY13–FY20.
- [`health/state_total_fertility_rate`](../indicators/health/state_total_fertility_rate.md) — Total Fertility Rate, children per woman, calendar year, 2003 onwards. The demographic-transition lens.

## Further reading

- **Office of the Registrar General of India, *SRS Statistical Report***, annual. The authoritative source; methodology appendix explains the dual-record reconciliation. <https://censusindia.gov.in/census.website/data/SRS>.
- **National Family Health Survey (NFHS) reports**, IIPS for MoHFW. NFHS-5 (2019-21) is the latest published; NFHS-6 fieldwork is ongoing. Captures the survey-side health indicators (anaemia, stunting, immunisation, ANC, contraceptive prevalence) that SRS does not. <https://rchiips.org/nfhs/>.
- **National Health Profile**, Central Bureau of Health Intelligence (CBHI), DGHS. Aggregate health-infrastructure and disease-burden snapshot. <https://cbhidghs.mohfw.gov.in/>.
- **Government of India, *National Health Policy 2017***. The policy statement behind the 2.5%-of-GDP health-expenditure target. <https://main.mohfw.gov.in/>.
- **WHO India, *India Health Profile***, periodic. International-comparable framing of Indian health metrics.

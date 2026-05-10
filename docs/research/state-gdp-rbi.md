# Research: State GDP — RBI Handbook of Statistics on Indian States

**Last Updated**: 2026-05-10
**Status**: planned — Phase D (second indicator, post power-plants)

## Question

Where do we get authoritative **GSDP / NSDP per state per year** time series for India?

## Candidates

### A. RBI — Handbook of Statistics on Indian States (preferred)

- Portal: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States>
- Format: Excel workbook released annually; the canonical cross-state time series.
- Coverage: GSDP/NSDP at constant and current prices, going back several decades for major states; sectoral breakdowns; per-capita income.
- License: RBI publication — terms-of-use page applies; usually permissive for research/non-commercial use with attribution. **Confirm exact terms before publishing the indicator.**
- Why preferred: the user explicitly named RBI as the GSDP source. It's also the source MoSPI itself republishes from for state series.

### B. MoSPI — National Statistical Office (alternate)

- Portal: <https://mospi.gov.in/>
- Format: separate state-wise releases; less consolidated than RBI's single workbook.
- Use as a cross-check or where RBI lags a quarter.

### C. data.gov.in (re-publication)

- Portal: <https://www.data.gov.in/>
- License: India OGL (clear).
- Coverage: variable — sometimes lags behind RBI; sometimes only the latest year.
- Use when RBI has terms-of-use friction we don't want to inherit.

## Decision (provisional, pending Phase D research)

**v1**: parse the RBI Handbook Excel workbook into `datasets/indicators/in/economy/gsdp_constant_prices.json` — long-form `(state, year, value_inr_crore, base_year)`. Document license precisely in the artifact's `metadata.license`.

**v2**: layer in MoSPI for the most recent year if RBI lags, with `sources[]` recording both upstreams.

## Open follow-ups

- Decide base-year handling: indicator schema either supports a `notes` / `unit_qualifier` field, or we emit one indicator per base-year-series.
- Real vs nominal: emit both as separate indicators (`gsdp_current_prices`, `gsdp_constant_prices_2011_12`).
- Per-capita derivations are NOT raw indicators — they're computed at view time from `gsdp` × `population`. Per the umbrella plan §8, every derivation's inputs must be published as their own indicators.

## References

- RBI Handbook portal (visited 2026-05-10): <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States>
- MoSPI: <https://mospi.gov.in/>
- data.gov.in: <https://www.data.gov.in/>

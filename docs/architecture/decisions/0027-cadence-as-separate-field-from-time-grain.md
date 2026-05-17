# ADR-0027 — `indicator.cadence` as a separate field from `indicator.time_grain`

**Status**: Accepted
**Date**: 2026-05-17
**Deciders**: User; agent-deliberation included Fowler (Engineering), Gregor (Architect), Max (Indicator Scout)
**Supersedes / supersedes**: builds on ADR-0026 (lift `collection_inventory` out of artifact); resolves an open question surfaced by the [TODO/20260517-coverage-temporal-range-plan.md](../../../TODO/20260517-coverage-temporal-range-plan.md) Phase #1 spike
**Schema impact**: `datasets/schemas/indicator.schema.json` v4.0 → v4.1 (additive; new optional `indicator.cadence` field)

## Context

Phase #1 of the coverage-temporal-range plan added a pure
`derive_temporal_range(indicator)` function that returns the observed
min/max time, observed period count, and a `gap_count_within_range`
(expected periods at the declared cadence minus observed periods). A
spike across all 110 production artifacts surfaced eight artifacts
with non-zero `gap_count_within_range`:

| Witness | Range | Observed | Computed gap | Reality |
| --- | --- | --- | --- | --- |
| `state_population_by_residence_count` | 1961 → 2011 | 6 | 45 | Census is **decennial**; 6 obs is the full universe |
| `state_population_by_sex_count` | 1961 → 2011 | 6 | 45 | same |
| `india_ghg_emissions_by_subsector_ggco2e` | 1994 → 2020 | 14 | 13 | UNFCCC NATCOM/BUR is **ad-hoc** (1994, 2000, 2010, 2014, 2016, 2020 …) |
| `india_ghg_emissions_mtco2e_by_sector` | 1994 → 2020 | 14 | 13 | same |
| `state_pm25_annual_mean_ug_m3` | 2014 → 2023 | 9 | 1 | Genuine **annual** series with a real 2020 hole (COVID monitoring) — the load-bearing signal the feature exists to surface |
| `state_hdi` | 2011 → 2017 (FY) | 2 | 5 | Subnational HDI is sparse — possibly **ad-hoc**, possibly source-availability gap (acquisition-incomplete); needs adapter audit |
| `india_external_balance_inr_crore` | 2000-04 → 2023-04 | 15 | 9 | RBI HBS-IS is annual; 9 missing fiscal years smells like a parser bug, not real data — needs adapter audit |
| `india_capacity_pipeline_gw` | 2011 → 2031 | 20 | 1 | CEA mixes historic + forward projections — fundamentally **ad-hoc** |

The function is computing exactly what its docstring says: expected
periods at the declared `time_grain` cadence, minus observed
periods. The 5 unambiguous cases (#1, #2, #3, #4, #8) are noise *from
the function's perspective*: their `time_grain=year` (or
`fiscal_year`) declares an annual cadence the publisher never
promised. The function is honest; the *artifact* is lying about
cadence.

This is the spike doing exactly what a spike should — surfacing a
contract gap before a citizen-facing surface ships on top of it.

### What `time_grain` is for

`indicator.time_grain ∈ {year, fiscal_year, quarter, month, date}`
declares **the resolution of a single `rows[].time` token**. For a
Census row, each observation IS stamped at year resolution — the
token is `"1961"`, not `"1961-decade"`. `time_grain=year` is
*correct* for Census: it tells the renderer how to format the time
axis. The grain says nothing about how often the publisher releases
a new observation.

### What's missing

A second field that declares **how often the publisher releases new
observations** — i.e. the publisher's release cadence. Today the
schema has no such field. v4.0 explicitly removed
`series_spec.expected_periods[].frequency` (and the whole
`expected_periods` array) per ADR-0026, lifting that operator-axis
state into the external completeness index. What survived was
`time_grain` — and `time_grain` cannot answer "is this series
expected to publish a new value every year".

## Decision

Add a new **optional** field `indicator.cadence` to the indicator
artifact in schema v4.0 → v4.1 (additive minor bump per CLAUDE.md
§11). The field declares the publisher's release cadence. It is
distinct from `time_grain` (which describes per-row time-token
resolution) — the two carry different concepts, neither subsumes
the other, and both stay on the citizen-axis artifact because both
inform citizen reading.

Enum (initial set, aligned with the legacy
`expected_periods[].frequency` vocabulary the lifted v3 schema
used):

| `cadence` value | Meaning | Renderer behaviour |
| --- | --- | --- |
| `annual_cy` | Annual, calendar year | gap_count defined |
| `annual_fy` | Annual, fiscal year (April-anchored) | gap_count defined |
| `quarterly_cy` | Quarterly, calendar year | gap_count defined |
| `quarterly_fy` | Quarterly, fiscal year | gap_count defined |
| `monthly` | Monthly | gap_count defined |
| `weekly` | Weekly | gap_count defined (future use) |
| `daily` | Daily | gap_count defined (future use) |
| `decennial` | Every 10 years (Census) | gap_count **omitted**; no "gaps" pill |
| `ad_hoc` | Irregular publisher schedule | gap_count **omitted**; no "gaps" pill |

The field is optional in v4.1. When absent, `derive_temporal_range`
falls back to its v4.0 behaviour: best-effort inference from
`time_grain`. Adapters add `cadence` opportunistically; the four
unambiguous witnesses (#1, #2, #3, #4 in the table above) are
retagged in the same commit as the schema bump.

`derive_temporal_range` reads `indicator.cadence` and:

- For `cadence ∈ {decennial, ad_hoc}` → omits **both**
  `gap_count_within_range` AND `observed_periods_within_range`.
  These series have no defined expected cadence; surfacing
  "observed = 6 of 51 expected" or even "observed = 6" against a
  range invites the citizen to read patchiness into a complete
  record (per Max). `min_time` / `max_time` / `*_period_label` /
  `time_grain` are still returned — the range itself is honest.
- For `cadence ∈ {annual_*, quarterly_*, monthly, weekly, daily}`
  → computes `gap_count_within_range` against that cadence.
- For `cadence` absent → falls back to inferring from `time_grain`
  (today's behaviour), preserving back-compat for unmigrated
  artifacts.

## Consequences

**Citizen surface (Phase #3 of the temporal-range plan).** The
caption builder reads `cadence` (not `time_grain`) to choose the
`grainWord` slot — `"annual"`, `"every 10 years"`, `"irregular
updates"`, etc. (see Max's draft vocabulary in the plan's debate
log). For `decennial` / `ad_hoc`, the renderer shows only the range
(`1961 → 2011 · every 10 years`) and suppresses any
gap/completeness pill.

**Operator surface (Phase #2 of the plan).** The completeness index
emitter mirrors what `derive_temporal_range` returns: index rows for
decennial/ad_hoc indicators have absent
`gap_count_within_range`/`observed_periods_within_range` keys. The
operator reads "this indicator's cadence is undefined; gap math
doesn't apply", which is the truth.

**Migration cost.** Adding one optional field is additive. Four
artifacts get a one-line `cadence` retag in the same commit
(Census×2, BUR-GHG×2). Three artifacts (RBI external balance, CEA
capacity pipeline, HDI) are flagged for a separate adapter-quality
audit; until that lands they will continue to show their current
"misleading" `gap_count_within_range` on the operator surface — that
IS the discovery signal driving the audit. CEA capacity pipeline is
also a candidate for `cadence: ad_hoc` because it mixes historic
observations with forward projections.

**Frontend TS impact.** `frontend/src/lib/indicators.ts` adds an
optional `cadence?: <enum>` field to `IndicatorMeta`. The Phase #3
caption builder is the first consumer.

**Validator impact.** Tier A (schema sanity) — the new enum
validates as a normal additive change. Tier B (corpus conformance,
local-only per CLAUDE.md §11) — absent field on the other 106
artifacts remains valid.

**Doctrine impact.** `CLAUDE.md §10` gains a bullet codifying the
publisher-vocabulary corollary surfaced by Gregor in the debate: if
`derive_temporal_range` raises mixed-vocab, fix the adapter to emit
one shape per artifact OR split the artifact — do not coerce tokens
to silence the error. The cadence field is the structural answer to
"but my publisher publishes irregularly"; coercion is not.

## Alternatives considered (and rejected)

### A. Extend `indicator.time_grain` enum to include `decennial` and `ad_hoc`

The simpler-looking path Gregor initially recommended in the debate.
Rejected because:

- It conflates two distinct concepts onto one enum: stamp resolution
  (the existing `time_grain` semantics — "the token is YYYY") AND
  release cadence ("a new value drops every 10 years"). A
  `decennial` time_grain value is a category error: Census rows still
  use `time = "1961"` (a YYYY token, year resolution), not some
  decennial-stamp format.
- It would break the renderer's existing `time_grain → token format`
  contract: `time_grain=year → YYYY`; `time_grain=date → YYYY-MM-DD`.
  Adding `decennial` and `ad_hoc` to this enum gives them no defined
  token format, forcing per-value special cases.
- It would not solve the underlying problem cleanly: a future
  ad-hoc-but-monthly-stamped indicator (e.g. RBI press release
  series) would still need cadence and stamp expressed
  independently.

### B. Read cadence from `series_spec.period.frequency` (Max's first proposal)

Max initially recommended this because that path is the natural home
in OWID-style schemas (and was the home in yen-gov's v2 folded
indicator model). Rejected because:

- v4.0 of `indicator.schema.json` (ADR-0026, 2026-05-17) explicitly
  removed `series_spec.expected_periods` and its `frequency`
  sub-field. In v4.0, `series_spec` is `{description}` only — there
  is no cadence field on the artifact anywhere. Restoring it inside
  `series_spec` would be re-introducing the v3 shape ADR-0026
  deliberately collapsed.
- A new top-level `series_spec.cadence` would also have to be
  defined as an optional additive bump, with the same enum and the
  same downstream wiring as Option C — at which point the only
  difference is where the field lives. Putting it on `indicator`
  groups it with the other adapter-declared "what is this series"
  metadata (`time_grain`, `value_kind`, `direction`, `unit`), which
  is where citizen and operator surfaces already look.

### C. No schema change; let `derive_temporal_range` infer cadence from spacing

Tempting because zero contract change. Rejected because:

- It would have to special-case Census ("if observed-spacing modal
  is 10 years, assume decennial"). That is exactly the
  band-aid/normaliser pattern CLAUDE.md §10 / Holy Law #5 forbid:
  silently inferring a cadence the publisher never declared.
- It puts cadence truth in code instead of data — a future renderer
  in TS would need to re-implement the same inference (or duplicate
  the derivation), violating one-rule-many-consumers.
- The five sparse-by-design cases (Census×2, GHG×2, HDI?) cannot be
  distinguished from "this is annual but most years are missing
  upstream" without a declaration. The function would have to guess,
  and a wrong guess on the citizen page is a credibility loss.

## Open questions

- **RBI external balance #3**: 15 observations over 24 fiscal years
  in `india_external_balance_inr_crore` is either an adapter parser
  bug, an RBI methodology break that dropped historic rows from
  newer Statement releases, or genuine source unavailability. The
  audit lives in [TODO/20260517-coverage-temporal-range-plan.md
  §"Deferred follow-ups"](../../../TODO/20260517-coverage-temporal-range-plan.md).
- **HDI #8**: We may be reading the UNDP HDR 2018 subnational
  table (2 reference years); Global Data Lab now publishes
  annual subnational HDI 2010–2022. Whether to switch sources or
  retag `cadence: ad_hoc` is a Max + adapter-author decision in
  the same follow-up.
- **CEA capacity pipeline #4**: Mixed historic observations + NEP
  forward projections. Likely `cadence: ad_hoc`. Coordinate with
  the next CEA ingest pass.

## See also

- [TODO/20260517-coverage-temporal-range-plan.md](../../../TODO/20260517-coverage-temporal-range-plan.md) — the plan whose Phase #1 spike surfaced this gap.
- [ADR-0026](0026-lift-collection-inventory-out-of-indicator-artifact.md) — the v4.0 lift that removed `series_spec.expected_periods.frequency` from the artifact.
- [ADR-0020](0020-indicator-artifact-as-data-contract.md) — the artifact-as-contract baseline.
- `CLAUDE.md` §10 — no normalisation of publisher vocabularies; cadence is a declaration, not an inference.
- `/memories/lessons.md` 2026-05-17 entry #1 — schema enum extension MUST update paired TS union in the same commit.

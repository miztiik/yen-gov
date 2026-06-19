# NITI Aayog SDG India Index - ingest (greenfield single-series proof)

**Last Updated**: 2026-06-19

The greenfield proof source for the `ingest` rip-and-replace plan
([TODO/20260618-backend-ingest-pipeline-rip-replace-plan.md](../../../TODO/20260618-backend-ingest-pipeline-rip-replace-plan.md),
Row 11): the **third single-series caller** of the shared
`canonical/ingest/run_pipeline.run_pipeline` (after `rbi_handbook` and the
`rbi_hbs_health` cohort).

## What it is

NITI Aayog's **SDG India Index** scores each state and UT from 0 to 100 on its
distance to the 2030 Sustainable Development Goal targets, aggregating the
goal-wise scores NITI computes from a basket of official indicators (100 = every
tracked target met). NITI **originates** this composite index (it is NITI's own
analytic), so per Holy Law #9 the citation `producer` is the issuing authority
**NITI Aayog** - this is NOT an ICED-style passthrough where the producer is a
separate upstream.

- **Indicator**: `sdg-india-index-score` (registered in
  [datasets/taxonomy/indicators.json](../../../datasets/taxonomy/indicators.json) -
  the first ingest indicator registered in the taxonomy SOT).
- **Concept**: `sdg-india-index-score` (registered in
  [datasets/taxonomy/concepts.json](../../../datasets/taxonomy/concepts.json);
  `noun="SDG India Index score"`, `unit_canonical="score"`,
  `normalisation="index"`, `entity_kinds=[country, state]`).
- **Adapter**: `backend/yen_gov/canonical/adapters/niti_sdg_index/` (parser +
  `run_pipeline` driver), wired into `default_registry()` so
  `ingest run --indicator sdg-india-index-score` drives it.

## Honesty caveats

- **`comparability = comparable_across_states_snapshot_only`.** NITI revises the
  indicator basket and methodology each edition (2018, 2019-20, 2020-21,
  2023-24), so a score is comparable across states **within one edition** but
  NOT cleanly across editions. The renderer must not draw a cross-edition growth
  rate.
- **A policy dashboard, not a direct outcome.** The score is a distance-to-target
  governance index, not a measured outcome like life expectancy.
- **`attribution_geography = where_resident`**: the score describes development
  outcomes for the resident population of the state/UT.

## Staged input

[`sdg-india-index-2020-21.csv`](sdg-india-index-2020-21.csv) is an
operator-staged sample (`state,year,score`) of the **SDG India Index & Dashboard
2020-21** (3rd edition) national + state composite scores, transcribed from the
published NITI report. It is a documented **subset** (India + 10 states spanning
the published range, top to bottom) staged for the greenfield ingest proof; a
production run stages the full official CSV for every state/UT. `time` is the
edition end-year (2021). No network: the pipeline reads this local file only
(parent plan section 21.4 - local-only Fetch).

Source: NITI Aayog, *SDG India Index & Dashboard 2020-21*
(<https://sdgindiaindex.niti.gov.in>).

## Pre-flight gate (ADR-0046)

[`proposal.json`](proposal.json) + the committed green
[`preflight-report.json`](preflight-report.json) record the
`python -m yen_gov pre-flight-ingest` gate run for this source (all six checks
`pass`; `source_id` left to the writer to derive per CLAUDE.md section 12).

## See also

- [docs/concepts/data-spine.md](../../concepts/data-spine.md) - the five
  non-negotiables every indicator family honours.
- [backend/yen_gov/canonical/ingest/run_pipeline.py](../../../backend/yen_gov/canonical/ingest/run_pipeline.py) -
  the shared single-series publish primitive.

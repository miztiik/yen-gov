# Goal-framework overlay (SDG / NITI / ICRIER / CHIPS)

**Last Updated**: 2026-06-17
**Status**: Active. SDG-3 subtree seeded; NITI / ICRIER / CHIPS deferred pending pinned citations.
**Owner**: Hans (honesty framing) + Max (coverage / source vetting), per [CLAUDE.md section 0a](../../CLAUDE.md)
**Seed**: `python -m yen_gov seed-goals` -> [`backend/yen_gov/canonical/goals_seed.py`](../../backend/yen_gov/canonical/goals_seed.py)
**See also**: [data-spine](data-spine.md), [data-provenance](data-provenance.md), [sources-rbi-handbook](../architecture/backend/sources-rbi-handbook.md), [cross-state-comparison](cross-state-comparison.md)

## What this is

A **metadata overlay** that lets a citizen see "how is my place doing against the goals society has set?" across country / state / district - by mapping curated yen-gov indicators to goal-framework targets (UN SDG today; NITI SDG India Index, ICRIER indices, CHIPS later). It adds **no new datapoints**: the summary view is a read-time join of the goal catalogue against the existing datapoint CSVs.

It answers a goal **lens**, not a verdict. The gap between a state's value and a goal line is a *distance to travel*, not a judgment on the people who govern that state ([Rosling's Blame instinct](cross-state-comparison.md)). yen-gov surfaces the target text next to the trajectory and leaves the "on track / off track" call to the reader - the same posture as OWID's SDG-Tracker.

## The three catalogue files

Additive file-classes in [`columns.json`](../../datasets/data/_schema/columns.json) (schema 2.8), mirroring the existing `topics.csv` (parent-pointer tree) + `indicator_topic_tags.csv` (M:N) patterns:

### `datasets/data/frameworks.csv` - the framework register

One row per framework, carrying the **authority honesty discriminator**:

- `authority_class` enum: `intergovernmental_resolution` (UN SDG - a **non-binding** UN General Assembly Resolution A/RES/70/1, NOT a treaty), `national_programme` (NITI SDG India Index), `think_tank_index` (ICRIER / CHIPS), `yen_gov_editorial` (a yen-gov-authored lens).
- `disclaimer` - the one-line citizen-facing "what this framework is / is not", surfaced before any score so a UN agreement never looks like a think-tank index.
- `source_id` FK to the defining-document citation.

### `datasets/data/goals.csv` - the goal tree (parent-pointer)

One row per goal / target / official-indicator node (`sdg-3` goal -> `sdg-3.2` target -> `sdg-3.2.1` official indicator). Two design rules:

- **Targets live on the node, one threshold per leaf.** A multi-threshold UN target (under-5 mortality <= 25 AND neonatal <= 12) splits into official-indicator children, each carrying one number. No `targets.csv` side table is needed - the tree gives every threshold a single owner.
- **`target_scope`** (`global` / `national` / `sub_national_statutory` / `none`) is the geography-honesty field. SDG targets are global / national aspirations, so the renderer draws a **national reference line, never a per-district pass/fail**. No SDG row may claim `sub_national_statutory` (that requires a statute citation, and none of the demographic indicators have one). `source_id` is required whenever `target_value` is non-null (no uncited number - Holy Law #9).

### `datasets/data/goal_indicators.csv` - the M:N mapping

Which yen-gov indicator answers which goal node. The mapping is **yen-gov's editorial judgement**, distinct from the framework's own authorship (the two-provenance rule):

- `mapping_method` = `official_crosswalk` (the framework itself names this exact indicator) vs `editorial_judgement` (yen-gov chose the closest honest proxy).
- `mapping_confidence` = `exact` / `proxy` / `context` - gates target-line inheritance. Only `exact` lets an indicator inherit the node's number; `proxy` shows it faintly with a caveat; `context` shows no line.
- `caveat` - the per-mapping citizen-facing honesty note.
- `indicator_id` FKs `variables.csv`, so a mapping **cannot exist for an unshipped indicator**. FK closure makes the overlay self-protecting: the seed only activates mappings whose indicators are already on disk.

## SDG-3 seed and the per-indicator honesty call

The seed carries the citable UN SDG-3 numbers (from A/RES/70/1): MMR <= 70, under-5 mortality <= 25, neonatal mortality <= 12, all by 2030. Against the five shipped SRS indicators, Hans's inclusion call:

| Indicator | Scorecard verdict | Why |
| --- | --- | --- |
| `infant-mortality-rate-per-1000` | **INCLUDE (proxy)** | SDG-3.2-adjacent; but SDG sets thresholds on under-5 and neonatal, not infant mortality - so it is a labelled proxy, no number inherited |
| `life-expectancy-at-birth-years` | **CONTEXT only** | a legitimate whole-goal outcome, but not an SDG indicator; no target line |
| `total-fertility-rate` | **EXCLUDE from scoring** | SDG sets no fertility target; replacement-level 2.1 is a demographic benchmark, not a governance score |
| `crude-birth-rate-per-1000` | **EXCLUDE** | no honest direction-of-good; falls naturally with development |
| `crude-death-rate-per-1000` | **EXCLUDE** | not age-standardised - an older-population state shows a higher CDR despite better health; a leaderboard arrow here is actively deceptive |

Only IMR earns a scorecard arrow; the rest are context or excluded. A goal scorecard across states is a leaderboard by construction, so any cross-state goal ranking defaults to an honest [peer set](cross-state-comparison.md) and forbids trajectory-projection to the target line (Rosling's Straight-line instinct).

## What is collectable under SDG, and from where

The overlay is only as honest as the indicators beneath it. For SDG-3 (health) specifically:

| SDG-3 target | yen-gov indicator | Source status |
| --- | --- | --- |
| 3.2 (under-5 / neonatal mortality) | IMR (proxy today) | SRS via RBI Handbook - **shipped path** ([sources-rbi-handbook](../architecture/backend/sources-rbi-handbook.md)) |
| 3.1 (maternal mortality <= 70) | none yet | SRS Special Bulletin (MMR) - **gap**, needs the interval-time contract |
| 3.2 (true under-5 / neonatal rate) | none yet | SRS / NFHS - **gap**; IMR is only a proxy |
| 3.7 (family planning) | TFR (context) | SRS - shipped, but as context not a target |

The honest sub-national path for SDG targets is the **NITI Aayog SDG India Index**, which publishes India state-grain SDG scores (0-100) and bands - something raw UN SDG does not. It is the strongest next framework to scout (`authority_class = national_programme`). **Do not** bake NITI band thresholds, ICRIER index definitions, or CHIPS numbers from memory - each needs a pinned citation in `docs/research/` first.

## Open follow-ups (-> `docs/research/`)

- Pin the NITI SDG India Index current-edition band thresholds + state targets, with citations, before seeding that framework.
- Pin ICRIER's specific index (pillars, licence) and a CHIPS definition + source - CHIPS is currently unverified and will not be modelled without one.
- Decide the interval-time contract for MMR / life-expectancy windows so SDG-3.1 can gain a real indicator.
- Ingest the SRS health cohort (`ingest-rbi-hbs`) so the FK-guarded mappings activate.

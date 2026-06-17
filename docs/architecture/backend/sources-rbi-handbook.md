# RBI Handbook of Statistics ingest (`canonical/adapters/rbi_handbook`)

**Last Updated**: 2026-06-17
**Module**: [`backend/yen_gov/canonical/adapters/rbi_handbook/`](../../../backend/yen_gov/canonical/adapters/rbi_handbook/)
**CLI**: `python -m yen_gov ingest-rbi-hbs`
**Owner**: data layer (Hans + Max own shape; Gregor owns the spec contract; Fowler owns the write seam)
**See also**: [data-spine](../../concepts/data-spine.md), [csv-column-contract](../data/csv-column-contract.md), [data-provenance](../../concepts/data-provenance.md), [goal-frameworks](../../concepts/goal-frameworks.md), [identifiers](../../reference/identifiers.md)

## What this adapter is

One **reusable, config-driven** ingester for every `state x period` table the Reserve Bank of India publishes in its **Handbook of Statistics on Indian States**. Adding a new table is one `HbsTableSpec` in the registry - no new parser code. The first shipped cohort is the SRS vital rates the citizen asked for (total fertility rate, birth rate, death rate, infant mortality rate) plus life expectancy at birth.

This module REPLACES the retired per-publication ECI-keyed parsers (`rbi_xlsx`, `rbi_hbs`, `rbi_hbs_ie_state_sdp`), which emitted ECI state codes (`S01`, `U08`) that do not FK-close against the canonical LGD-slug `entity_id` in [`datasets/data/entities/geo.csv`](../../../datasets/data/entities/geo.csv). See [Retired emitters](#retired-emitters) below.

## Provenance doctrine: RBI is the access surface, not the source of origin

RBI **republishes** these statistics; the issuing authority is the **Sample Registration System (SRS), Office of the Registrar General & Census Commissioner (ORGI)**. Per [Holy Law #9](../../../CLAUDE.md) the `source.csv` row names the source-of-origin as `producer` and the RBI Handbook as the access path in `title`:

```
producer = Office of the Registrar General & Census Commissioner, India
title    = Sample Registration System (via RBI Handbook of Statistics on Indian States)
vintage  = <Handbook edition, e.g. 2024-25>
```

`source_id` is **derived** from the `(producer, title, vintage)` triple via `citation.derive_source_id` - never hand-authored.

## How collection works (operator workflow)

The pipeline is **local-file only** - there is no network fetcher (deleted in the platform rip; see [plan section 21.4](../../../TODO/20260603-data-and-charting-platform-reset-plan.md)). The operator stages the workbook, then runs the CLI:

1. **Download** the table you want from the RBI Handbook of Statistics on Indian States listing page:
   <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States>
   The "Social and Demographic Indicators" section is the first cohort's home; each table is its own small XLSX (15-50 KB).
2. **Stage** each XLSX into a local staging directory under the filename the spec declares in `staging_filename` (e.g. `table-total-fertility-rate.xlsx`). The staging dir is operator input, never a committed contract surface.
3. **Run** the ingester:
   ```
   python -m yen_gov ingest-rbi-hbs --root . --staging-dir <dir>
   # or a subset:
   python -m yen_gov ingest-rbi-hbs --root . --staging-dir <dir> -i total-fertility-rate -i life-expectancy-at-birth-years
   ```
4. For each table the command melts the `state x period` matrix to long format, resolves each RBI state label to its LGD `entity_id` slug (all-India rows -> `IN`), and emits:
   - `datasets/data/datapoints/geo/<indicator_id>.csv` (the observation rows),
   - upserted `variables.csv` + `concepts.csv` + `entities/source.csv` catalogue rows.
5. Run `python -m yen_gov validate --root .` (Tier-B) before committing.

The run is **idempotent**: the canonical writer skip-writes byte-identical output, so re-running with the same edition leaves a clean `git status`.

## The reusable spec (extend without code)

Each table is one `HbsTableSpec` (in [`registry.py`](../../../backend/yen_gov/canonical/adapters/rbi_handbook/registry.py)). The fields it carries:

| Group | Fields | Purpose |
| --- | --- | --- |
| Identity / output | `indicator_id`, `name`, `concept_id`, `concept_noun`, `concept_description`, `unit`, `unit_canonical`, `normalisation`, `topic`, `entity_kinds`, `update_period_days` | the `variables.csv` + `concepts.csv` rows |
| Provenance | `source_producer`, `source_title`, `source_vintage`, `source_url` | the `source.csv` row; `source_id` is derived |
| Layout | `staging_filename`, `sheet`, `state_label_match`, `time_kind`, `value_scale`, `value_sub_label`, `skip_labels`, `all_india_labels` | drive the generic parser |

The two generalization knobs:

- **`time_kind`** = `calendar_year` (plain `2016`, `2024` column headers - the SRS vital rates) or `interval_window_end` (multi-year windows like `2016-20`, stamped at the end year - life expectancy / MMR). The parser auto-detects the header row and the period columns from this.
- **`value_sub_label`** - banded (two-row) header support. Life Expectancy publishes Male / Female / Total under each window; setting `value_sub_label="Total"` keeps only the Total band so the series is ONE comparable file, not three fragmented ones. This is the de-fragmentation rule in action (see [No fragmentation](#no-fragmentation)).

A future agent adds a new RBI Handbook table (any section: State Domestic Product, Fiscal, Banking, Agriculture, Prices) by appending one spec. State-name resolution, the melt, all-India handling, and the catalogue upsert are unchanged.

## State-name resolution

[`resolver.py`](../../../backend/yen_gov/canonical/adapters/rbi_handbook/resolver.py) builds a `display-name -> LGD slug` map at run time from `geo.csv` (`name` + the pipe-delimited `aliases` column, which carries `IN-AP|S01|lgd:28`), plus a small RBI/SRS dialect override map (`Orissa -> odisha`, `Uttaranchal -> uttarakhand`, `Pondicherry -> puducherry`, `NCT of Delhi -> delhi`). All-India rows resolve to the country entity `IN`. An unmatched, non-skip-listed state label **fails loud** - a silent coverage drop would lie to the citizen.

## No fragmentation

A measure is ONE file. The vital rates are naturally single-series; life expectancy keeps only its Total band rather than splitting into male/female/total files. A male/female facet (if ever wanted) is a deferred Hans + Max decision (facet column vs sibling file-class), NOT three more files. This is the answer to the over-fragmentation seen in older families (e.g. the `-accounts` / `-re` / `-be` fiscal triplet) - the parser collapses publisher sub-columns at read time.

## Shipped cohort (first wave)

| `indicator_id` | concept | unit | normalisation | topic | source-of-origin |
| --- | --- | --- | --- | --- | --- |
| `total-fertility-rate` | total-fertility-rate | children per woman | ratio | health | SRS Statistical Report |
| `crude-birth-rate-per-1000` | crude-birth-rate | per 1,000 population | ratio | demography | SRS |
| `crude-death-rate-per-1000` | crude-death-rate | per 1,000 population | ratio | demography | SRS |
| `infant-mortality-rate-per-1000` | infant-mortality-rate | per 1,000 live births | ratio | health | SRS |
| `life-expectancy-at-birth-years` | life-expectancy-at-birth | years | ratio | health | SRS Abridged Life Tables |

`crude-death-rate` carries a Hans caveat in its concept description (not age-standardised - an older-population state shows a higher CDR despite better health; never rank naively). `life-expectancy` is interval data (multi-year windows); the source vintage carries the window.

## What can be collected from RBI Handbook vs sourced elsewhere

The Handbook's "Social and Demographic Indicators" + "Health" sections are a republished convenience surface. What is **honest to ingest here** vs what needs a **different primary source**:

| Want | Collectable via RBI Handbook? | Honest primary source / note |
| --- | --- | --- |
| TFR, birth rate, death rate, IMR (annual) | Yes (this cohort) | SRS / ORGI is the issuing authority; RBI is the access surface |
| Life expectancy at birth | Yes (banded, Total band) | SRS Abridged Life Tables; interval windows, not point years |
| Maternal mortality ratio (MMR) | Partially (windowed) | SRS Special Bulletin; needs the interval-time contract before it lands |
| Literacy, sex ratio, density, decadal growth, population | Yes but **census-decennial** | Census / ORGI; latest hard point is 2011 (2021 Census delayed) - render as a labelled snapshot, never a trend. Population overlaps the existing `state-population-lakhs` (NITI projection) - UPSERT/facet, do not mint |
| Poverty rate | **Defer (STOP-AND-SURFACE)** | Methodology-unstable (Tendulkar vs Rangarajan vs NITI-MPI); no continuous official series post-2011-12; a cross-time poverty line is a fake trend |
| District-grain TFR / life expectancy | No | SRS is state-grain by design. District TFR exists only as NFHS survey-round snapshots (a separate methodology family); district life expectancy is not a routine official output |
| Anaemia (children / pregnant women) | Listed in Handbook | NFHS rounds only (NFHS-4 2015-16, NFHS-5 2019-21) - two survey points, not an annual trend |

For the full source-vetting + framing rationale see the Hans + Max verdicts captured in the plan-doc and [data-spine](../../concepts/data-spine.md).

## Goal-framework overlay (SDG)

The SRS health indicators feed the [goal-framework overlay](../../concepts/goal-frameworks.md): once `infant-mortality-rate-per-1000` / `total-fertility-rate` / `life-expectancy-at-birth-years` land in `variables.csv`, the FK-guarded `goal_indicators.csv` mappings (seeded by `python -m yen_gov seed-goals`) activate, surfacing each place's trajectory under the SDG-3 lens. Of the five, only IMR is a scorecard member (as an SDG-3.2 proxy); life expectancy is context; TFR / birth / death rates carry no SDG target.

## Tests

[`backend/tests/test_canonical_rbi_handbook.py`](../../../backend/tests/test_canonical_rbi_handbook.py) builds in-memory openpyxl workbooks (single-value + banded layouts), exercises the resolver, both parser modes, the fail-loud paths, and the full ingest -> emitted CSV passing the canonical validator under `tmp_path`. No real-corpus walk.

## Retired emitters

Deleted 2026-06-17 (rip-and-replace, user-authorized). These emitted ECI state codes that do not FK-close against the LGD-slug canonical store, and were all CLI-orphaned (no live command called them):

| Retired module | Was | Replacement |
| --- | --- | --- |
| `sources/rbi_xlsx` | per-state State Finances Statements (ECI-keyed) | this adapter; the 2 fiscal indicators it once produced (`outstanding_debt_pct_gsdp`, `net_transfers_from_centre`) are frozen canonical CSV from the W1 migration |
| `sources/rbi_hbs` | shared HBS name-map + cell primitives (ECI-keyed) | `resolver.py` + `parser.py` here |
| `sources/rbi_hbs_ie_state_sdp` | HBS-IE state SDP tables (ECI-keyed, folded JSON) | a future SDP spec in this registry |
| `sources/datagovin_ogd/{parsers,ingest}.py` | data.gov.in fiscal CSV (imported the rbi_xlsx ECI normaliser) | the datagovin **pincode** path in the same package is preserved and untouched |

The on-disk data those modules produced was already frozen canonical CSV (slug-keyed, from the W1 migration), so no citizen-facing data was lost. The national-aggregate siblings `rbi_appendix_national`, `rbi_appendix_deficits`, and `rbi_hbs_ie_centre_deficits` survive (they emit `entity_id = "IN"`, no ECI state map) but are CLI-orphaned; retiring or re-pointing them onto this adapter is a tracked follow-up.

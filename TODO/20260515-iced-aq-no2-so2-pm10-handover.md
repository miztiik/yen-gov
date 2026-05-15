# Handoff — ICED Air Quality: NO2 / SO2 / PM10 sibling indicators

**For**: the next agent extending the ICED air-quality adapter.
**From**: agent that shipped FGD (`c53540f`) and PM2.5 (`85f2d92`) on 2026-05-15.
**Read first**: [CLAUDE.md](../CLAUDE.md), [docs/architecture/backend/sources-iced-api.md](../docs/architecture/backend/sources-iced-api.md), [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md).
**Status**: Ready to pick up. Mechanical follow-up — the parser and writer are already in place; this is three near-identical clones of `ingest_pm25` plus catalogue wiring.

---

## 1. Goal

Ship three sibling indicators alongside the PM2.5 one that just landed:

| Indicator id | Pollutant key | Series start |
|---|---|---|
| `environment/state_no2_annual_mean_ug_m3` | `no2` | 2010 |
| `environment/state_so2_annual_mean_ug_m3` | `so2` | 2010 |
| `environment/state_pm10_annual_mean_ug_m3` | `pm10` | 2010 |

PM2.5 starts in 2014 because the network only began measuring fine particulates then; the other three are recorded back to 2010 in the same NAMP feed (verified against the captured snapshot — see `coverage` field in [datasets/reference/in/upstream-sources.json](../datasets/reference/in/upstream-sources.json#L188-L201)).

All three inherit the same honesty framing as PM2.5:

- `comparability: not_comparable_across_states` (CPCB monitor network is uneven, urban-biased, sparse outside metros — ranking states by raw mean is dishonest)
- `attribution_geography: where_consumed`
- `implementing_authority: centre`
- `direction: lower_is_better`
- `chart_type: choropleth`
- `series_breaks`: 2020 coverage gap (COVID-era monitoring disruption — same as PM2.5)

## 2. Why this is mechanical

The aggregator is already pollutant-agnostic. From [backend/yen_gov/sources/iced_air_quality/markers_parsers.py](../backend/yen_gov/sources/iced_air_quality/markers_parsers.py):

```python
PM25_FIELD = "pm25"
NO2_FIELD = "no2"
SO2_FIELD = "so2"
PM10_FIELD = "pm10"

def aggregate_state_year_mean(decrypted: dict, *, pollutant: str) -> list[StateYearMean]:
    ...
```

A parametrized test (`test_all_pollutants_aggregate` in [backend/tests/test_sources_iced_air_quality_markers.py](../backend/tests/test_sources_iced_air_quality_markers.py)) already proves all four pollutant keys produce non-empty, well-shaped output against the captured fixture. **No parser changes needed.**

## 3. Concrete steps

### 3.1 Backend — three new ingest functions

Edit [backend/yen_gov/sources/iced_air_quality/markers_ingest.py](../backend/yen_gov/sources/iced_air_quality/markers_ingest.py). Pattern-match on `ingest_pm25` + `_build_pm25_payload`; the only differences per pollutant are:

1. Constants block: `NO2_INDICATOR_ID`, `NO2_INDICATOR_TITLE`, `NO2_INDICATOR_DESCRIPTION`, `NO2_INDICATOR_NOTES`, `NO2_SERIES_START_YEAR = 2010` (and same triplet for SO2, PM10).
2. The `pollutant=` argument passed to `aggregate_state_year_mean(...)`.
3. The `out_path` filename.
4. The pollutant-specific description and notes (see §3.3 for citizen-readable copy).
5. `unit` stays `"µg/m³"` for all three — same field as PM2.5.

Recommended refactor only if the body is becoming repetitive: extract a private `_ingest_pollutant(repo_root, *, pollutant, indicator_id, title, description, notes, series_start_year)` helper. **Do not refactor before the second clone exists** — that's premature abstraction. After NO2 lands, look at the diff against PM2.5 and decide whether to extract before SO2.

### 3.2 Catalogue wiring (two files)

**[datasets/reference/in/upstream-sources.json](../datasets/reference/in/upstream-sources.json)**, entry `iced.air_quality_namp_markers` (~line 188): extend the `indicator_ids` array from one entry to four:

```json
"indicator_ids": [
  "environment/state_pm25_annual_mean_ug_m3",
  "environment/state_no2_annual_mean_ug_m3",
  "environment/state_so2_annual_mean_ug_m3",
  "environment/state_pm10_annual_mean_ug_m3"
],
```

The `notes` field for that entry already says "NO2 / SO2 / PM10 are mechanical follow-up indicators using the same parser called with a different pollutant argument." — no edit needed there.

**[datasets/reference/in/topic-catalogue.json](../datasets/reference/in/topic-catalogue.json)**, environment topic, after the PM2.5 entry (~line 660): append three more `kind: indicator` entries with the same shape (`scope: state`, `chart_type: choropleth`, `featured: true` for at least NO2 and PM10; SO2 may be `featured: false` since SO2 levels in India are typically low and pair more naturally with FGD on the topic page rather than as a standalone hero).

### 3.3 Pollutant-specific copy (citizen-readable, distinct caveats)

Each indicator's `notes` should differ from PM2.5's so the citizen learns something specific. Suggested skeletons:

**NO2** — WHO 2021 annual guideline 10 µg/m³; India NAAQS 40 µg/m³.
> Sources: vehicle exhaust (especially diesel) and thermal-plant flue gas. Concentrated in metros and along highways. The 2020 dip reflects both COVID lockdown traffic collapse AND the network gap noted below — do not read 2020 as a real reduction.

**SO2** — WHO has no annual guideline (24-hour 40 µg/m³); India NAAQS 50 µg/m³ annual.
> Sources: predominantly thermal-plant flue gas (high-sulphur Indian coal). National levels are typically well below the standard, which is why SO2 abatement (FGD installation — see the FGD compliance indicator on this page) has been politically deprioritised. State-level mean often hides plant-specific hotspots.

**PM10** — WHO 2021 annual guideline 15 µg/m³; India NAAQS 60 µg/m³.
> Includes PM2.5 plus coarser particulates from road dust, construction, and crop residue burning. Tends to track PM2.5 in metros but stays elevated in dry/dusty regions even where PM2.5 is moderate.

Description text follows PM2.5's pattern: one-line definition, WHO guideline, India NAAQS standard.

### 3.4 Tests

Extend [backend/tests/test_sources_iced_air_quality_markers.py](../backend/tests/test_sources_iced_air_quality_markers.py). For each new indicator, mirror what exists for PM2.5:

- Loud-fail on unknown state spelling (already covered by parametrized test — verify it passes).
- At-most-one row per `(entity_id, year)` (already covered).
- Plausible-range pin: pick one well-known state-year (e.g. Delhi 2019 NO2 should be ≥30; Goa 2018 SO2 should be ≤20). Keep these loose — purpose is to catch a parser regression, not to pin a specific upstream value.
- Year-range assertion per pollutant: `min(year) >= series_start_year` and `max(year) >= 2024` (network is still publishing).

Each new ingest function gets its own `test_ingest_<pollutant>_emits_artifact` end-to-end test that runs the ingest against the fixture and validates the emitted artifact against the indicator schema (mirror the PM2.5 version).

Expected delta: backend `+12` tests (4 each × 3 pollutants) → ~437 total. Frontend contract tests: `+6` (3 new artifacts × {file-validates-against-schema, sources-shape}) → 9621 total.

### 3.5 Run order

1. Implement NO2 (clone PM2.5 path end-to-end). Run `pytest backend/tests/test_sources_iced_air_quality_markers.py -v` — should be green.
2. Run `python -m yen_gov.cli ingest-iced-aq-no2` (add this CLI command alongside the existing `ingest-iced-aq-pm25`).
3. Run `pytest backend/tests/test_validate.py backend/tests/test_datasets_integrity.py -q` — the new artifact must validate against `indicator.schema.json` and pass cross-registry consistency.
4. Run `npm test --prefix frontend` — the contract tests should auto-discover the new artifact and validate it.
5. Repeat for SO2 and PM10.
6. After all three are on disk, smoke-test `/t/environment` per CLAUDE.md §13 — the page should now show 8 environment indicators (GHG sector, GHG subsector, state CO2, FGD, PM2.5, NO2, SO2, PM10). Verify each renders with its honesty banner ("Illustrative — not a ranking. CPCB monitor coverage is uneven across states.") and that no new console errors / 404s appear.

## 4. Definition of done

- [ ] Three new artifacts on disk, each validating against `indicator.schema.json` v1.3.
- [ ] `iced.air_quality_namp_markers.indicator_ids` lists all four pollutants.
- [ ] `topic-catalogue.json` environment topic lists all three new indicators in the order: PM2.5 → PM10 → NO2 → SO2 (most-citizen-relevant first).
- [ ] Backend tests +12, all green.
- [ ] Frontend contract tests +6, all green.
- [ ] `/t/environment` rendered, screenshot taken, no new console errors.
- [ ] Each indicator's `notes` block has a pollutant-specific paragraph (NOT a copy of the PM2.5 boilerplate).
- [ ] All artifacts list both `MARKERS_API_URL` and `CPCB_NAMP_URL` in `sources` (dual-provenance per Hans 2026-05-15).
- [ ] Single commit per pollutant (`backend/iced_air_quality: ship NO2 ...`, `... ship SO2 ...`, `... ship PM10 ...`) OR one combined commit if the diff stays under ~500 lines — your call.

## 5. Out of scope (do NOT pull in)

- City-year aggregation (the markers feed has lat/lng — tempting but a different concept; needs a city reference dataset that doesn't exist yet).
- Station-level point dataset (per-monitor time series — would need its own schema, not an indicator).
- Cross-pollutant composite AQI (CPCB has its own AQI calculation; reproducing it is a separate ingest).
- WHO/NAAQS reference lines drawn on the choropleth legend (legend redesign is a separate frontend ticket).
- Re-running PM2.5 ingest. It's already on disk. Don't touch its artifact.

## 6. Reference commits (to mimic)

- `c53540f` — FGD compliance indicator (first ICED AQ commit; established the dual-provenance pattern and the ICEDShapeError loud-fail).
- `85f2d92` — PM2.5 indicator + pollutant-agnostic aggregator (the template you're cloning).
- `1002a66` — endpoint catalogue registration (already done; you don't need to re-add endpoints).

## 7. Known gotchas

- The ICED feed spells some states unusually ("Tamilnadu" for Tamil Nadu; pre-2020 "Dadra & Nagar Haveli" / "Daman & Diu" both legacy halves). Aliases are already in `iced_common.entities.ENTITY_MAP`. If the parser raises `ICEDShapeError("unknown state ...")` against a fresh fetch, add the alias there — don't strip it in the parser.
- `0` is a valid measurement (deep rural station with low SO2). Do NOT add `0` to `_NULL_TOKENS`. Already correct in `markers_parsers.py`; verify your tests don't accidentally expect zeros to be dropped.
- Schema version literals MUST come from `schema_registry.schema_version("indicator.schema.json")`. Do not hand-type `"1.3"` (CLAUDE.md §11).
- PowerShell on Windows: do not run `python -c "<multiline>"` (hangs). Write any inspection script to a `tools/<name>.py` file. Do not use `git add .` (CLAUDE.md §8) — stage only the specific files you touched.

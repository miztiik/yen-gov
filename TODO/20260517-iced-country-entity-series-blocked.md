# Country-entity ICED series — blocked on Phase 4 renderer

**Created**: 2026-05-17  •  **Status**: blocked, design recorded  •  **Owner**: next ICED ingest commit after Phase 4 ships

## What is blocked

Three ICED endpoints carry **multi-decade national series** that we
cannot honestly ship today because yen-gov's frontend has no
country-entity renderer yet (Phase 4 work, deferred):

| Endpoint | Series | Native cadence | Earliest year |
| --- | --- | --- | --- |
| `/economy-demography/key-economic-indicators/per-capita-consumption` | All-India PFCE per capita (the `indiaWorld` segment of the dict the parser currently drops — see [iced_socio/parsers.py:215](../backend/yen_gov/sources/iced_socio/parsers.py)) | annual_fy | **1971** |
| `/energy/sourceWiseEnergySupply` | National primary energy supply by source (coal/oil/gas/nuclear/hydro/RE) | annual_fy | ~2000 |
| `/climate-environment/climate-variability/temperatureAnnual` | National annual mean temperature anomaly | annual_cy | ~1900 (varies) |

The state-level companions of these endpoints ARE already shipped (or
will be in the next bound-parser commit). What is missing is the
country-entity row class and the renderer that draws a single-series
line for an "India" entity rather than a state choropleth or peer
ranking.

## Why this is a renderer problem, not an ingest problem

- The `indicator.schema.json` already has `entity_kind` as a free string;
  the artifacts can declare `entity_kind: "country"` today without a
  schema bump.
- What we lack:
  1. A `country.schema.json` / country-entity registry analogous to
     `state.schema.json` (single member: India, with its ECI/ISO code).
  2. A renderer route. The state pages key off `/s/<state>/...`; an
     India page needs `/c/in/...` or equivalent IA.
  3. A topic-catalogue convention for "this indicator is national-only,
     do NOT try to render a choropleth for it" — currently the indicator
     panel assumes state-disaggregable rows.
- All three are Phase 4 (post-IA-reset) per the conversation summary;
  see also `TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md`.

## What MUST NOT happen as a workaround

- **Do not** fake the country series by emitting it as 36 identical
  state rows. That would silently invent state-level disaggregation
  the data does not support — a §10 anti-pattern (hardcoded taxonomy,
  governance bug).
- **Do not** fold the country series into the existing state artifact
  under a fake `entity_id: "IN"` row. Schema validators will accept it
  but the citizen UI will then render India as another "state" choropleth
  cell, which is meaningless.
- **Do not** spin up a one-off `/india` page just to host these three
  charts. The renderer needs to be the general country-entity surface,
  used by every future national-aggregate indicator.

## Action when Phase 4 lands

1. Promote `iced_socio/parsers.py:parse_per_capita_consumption` to
   return BOTH `state` and `indiaWorld` slices.
2. Emit a new artifact
   `datasets/indicators/in/economy/india_per_capita_consumption_inr.json`
   with `entity_kind: "country"`, full 1971→2024 series, sourced from
   the same endpoint (already in `endpoints.py` as
   `economy_per_capita_consumption`).
3. Bind a parser for `energy_source_wise_supply` (already in
   `endpoints.py` from the wave-2 catalogue expansion) and emit
   `india_primary_energy_supply_by_source_mtoe.json`.
4. Bind a parser for `climate_temperature_annual` (wave-2 entry) and
   emit `india_temperature_anomaly_c.json`.
5. Delete this handover.

## See also

- [docs/architecture/backend/sources-iced-api.md](../docs/architecture/backend/sources-iced-api.md) — endpoint catalogue and wave-2 expansion note.
- [backend/yen_gov/sources/iced_socio/parsers.py](../backend/yen_gov/sources/iced_socio/parsers.py) — current parser that explicitly drops `indiaWorld`.
- `TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md` — Phase 4 IA plan.

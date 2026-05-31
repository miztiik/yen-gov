# sources/rbi_hbs_ie_state_sdp - RBI HBS-IE State SDP Tables

**Last Updated**: 2026-05-31

## Purpose

`backend/yen_gov/sources/rbi_hbs_ie_state_sdp/` ingests cached Reserve Bank of India Handbook of Statistics on Indian Economy state SDP workbooks and writes the legacy folded economy indicator artifacts through the backend artifact writer.

It replaces the retired `tools/rbi_hbs_ingest_state_gdp.py` script. The change is structural: the active producer now lives in `backend/`, uses the schema registry, validates through `core.io.write_artifact`, and no longer emits render fields removed from `indicator.schema.json` v6.

## Inputs

The adapter is cache-only. Operators place the four HBS-IE 2024-25 workbooks under `.runtime/raw/rbi/handbook_economy_2024_25/`:

- `T05_NSDP_Statewise_Current.xlsx`
- `T06_NSDP_Statewise_Constant.xlsx`
- `T09_PCNSDP_Statewise_Current.xlsx`
- `T10_PCNSDP_Statewise_Constant.xlsx`

`.runtime/` is not a contract surface; the committed artifacts cite the RBI URLs through the legacy folded `sources[]` array stamped by the writer.

## Outputs

The adapter writes three folded indicator artifacts under `datasets/indicators/in/economy/`:

- `nsdp_inr_crore.json` - facetted `current` / `constant` NSDP rows from Tables 5 and 6.
- `per_capita_nsdp_current_inr.json` - per-capita NSDP at current prices from Table 9.
- `per_capita_nsdp_constant_inr.json` - per-capita NSDP at constant prices from Table 10.

For overlapping base-year sections, the most recent base wins in this order: `2011-12`, `2004-05`, `1999-2000`, `1993-94`. Each row carries the selected base in `rows[].vintage` so the renderer can disclose methodology breaks.

## Schema Discipline

The adapter calls `schema_id("indicator.schema.json")` and `schema_version("indicator.schema.json")`; it does not hand-type the current schema version. It also avoids `indicator.facet_labels`, `indicator.default_mode`, and `indicator.renderer_rules`, which were removed from the canonical indicator schema in v6. Render hints belong in the grapher catalogue per ADR-0045.

## Tests

`backend/tests/test_sources_rbi_hbs_ie_state_sdp.py` builds in-memory HBS-IE-shaped workbooks with `openpyxl`, writes them under a `tmp_path` cache, and proves:

- the missing-cache error carries an operator recipe;
- the adapter writes all three expected artifacts;
- the artifacts stamp the current indicator schema version;
- v6-removed render fields stay out of the indicator block;
- latest-base collapse picks the 2011-12 section for overlapping years;
- the per-capita all-India reference row is preserved when RBI publishes it.

## See also

- [Backend overview](overview.md)
- [RBI as a fiscal-indicator source](sources-rbi.md)
- [sources/rbi_hbs_ie_centre_deficits](sources-rbi-hbs-ie-centre-deficits.md)
- [Canonical writer](writer.md)
- [Data provenance](../../concepts/data-provenance.md)
- [ADR-0045](../decisions/0045-grapher-catalogue-split.md)
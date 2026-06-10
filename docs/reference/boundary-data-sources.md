# Boundary Data Sources

**Last Updated**: 2026-06-11

Reference catalogue for boundary geometry sources: country, state, district, subdistrict, village, Assembly Constituency, Parliamentary Constituency, and postal polygons.

## See Also

- [lgd-opendata.md](lgd-opendata.md) - LGD registry table catalogue.
- [identifiers.md](identifiers.md) - identifier conventions.
- [docs/architecture/data/boundaries.md](../architecture/data/boundaries.md) - boundary storage and validation contract.
- [tools/boundaries/README.md](../../tools/boundaries/README.md) - operational pipeline.
- [docs/concepts/boundary-data-philosophy.md](../concepts/boundary-data-philosophy.md) - rejected source families and selection rationale.

## Current Shipping Ledger

The current boundary inventory is `datasets/data/entities/boundary_layer.csv`. It carries one row per shipped boundary layer or shard, including source id, geometry path, simplification metadata, notes, and validity fields. Source citations resolve through `datasets/data/entities/source.csv`.

For exact current counts, do not count this Markdown table. Query the CSV ledger.

## Terminology

| Term | Meaning |
| --- | --- |
| AC | Assembly Constituency, elects one MLA. |
| PC | Parliamentary Constituency, elects one MP. |
| LGD code | Numeric identifier issued by the Local Government Directory for administrative units. |
| Delimitation vintage | Legal boundary vintage for electoral geography. |

## Shipped Source Families

| Layer | Shipped source family | Join key | Notes |
| --- | --- | --- | --- |
| `country` | yashveeeeeeer/india-geodata, SoI-derived outline | fixed country id | India outline only. |
| `state` | ramSeraph `LGD_States` / BharatMaps lineage | LGD state code / canonical state slug | Current state/UT outline layer. |
| `district` | ramSeraph `LGD_Districts` | `dist_lgd` | National district polygons keyed to LGD. |
| `subdistrict` | ramSeraph `LGD_Subdistricts` | `subdist_lgd` | One shard per state/UT. |
| `village` | ramSeraph `LGD_Villages` | `village_lgd` | Available for 27 of 36 states/UTs; 9 upstream gaps remain. |
| `ac` | Mixed: ramSeraph LGD ACs, HTL shapefiles, shijithpk J&K | `AC_ID`, `AC_NO`, or source-specific seat id | Per-state parity checks decide promotion from HTL to LGD lineage. |
| `pc` | shijithpk 2024 LS seats | `ls_seat_code` | Researcher-quality 2024 PC geometry; survey-grade LGD PC remains a candidate. |
| `postal` | Department of Posts / data.gov.in pincode boundary dataset | six-digit pincode when keyed | Search geometry only, not a choropleth drill rung. |

## Known Gaps and Candidate Triggers

| Gap | Current stance | Candidate trigger |
| --- | --- | --- |
| Village polygons for AR, HP, MN, ML, MZ, NL, SK, J&K, Ladakh | Missing from ramSeraph LGD village upstream. | Adopt a per-state fallback only when a village-keyed citizen surface needs that state. |
| Survey-grade AC consolidation for remaining HTL states | Keep current HTL shards while they match the gazetted delimitation. | Promote per state only after parity check against the constituency SoT. |
| Survey-grade PC geometry | Current shijithpk file is suitable for visualisation, not area/distance analysis. | Evaluate ramSeraph `LGD_Parliament_Constituencies` when a PC surface needs survey-grade joins. |
| Census-2011 polygons | Catalogue only. | Adopt when a Census-2011 anchored indicator needs historical polygon joins. |
| Blocks, panchayats, ULBs, wards | Catalogue only. | Adopt when local-body governance or scheme-delivery indicators ship. |

## Source Selection Bar

Before adding a new boundary source to `tools/boundaries/pipeline.json`:

1. Confirm license compatibility from the upstream license file.
2. Name the property that carries the join key.
3. Name the delimitation or administrative vintage.
4. Add or update citation rows in `datasets/data/entities/source.csv` through the canonical source-id path.
5. Add parity or shape tests for any electoral layer.
6. Keep per-state or per-layer adoption narrow; no bulk source swaps just because a newer catalogue exists.

## Rejected Defaults

- GADM is not a yen-gov source. Licensing, disputed-boundary treatment, identifier shape, and stale India administrative splits make it unsuitable for this static citizen site.
- Topographic raster basemaps are out of scope. yen-gov renders administrative-boundary choropleths, not terrain.
- OpenStreetMap is useful as a cross-check, not as the primary constituency source.

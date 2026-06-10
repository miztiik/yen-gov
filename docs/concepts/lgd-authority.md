# LGD authority

**Last Updated**: 2026-06-01

## What is LGD

The **Local Government Directory** (`https://lgdirectory.gov.in/`) is the Ministry of Panchayati Raj's master register of every administrative entity in India: state, district, sub-district, block, panchayat, urban local body, ULB ward, and Assembly Constituency. It is the central government's own canonical naming and numbering authority.

Every entity has:

- a numeric **LGD id** (globally unique within its level: state ids are 1-37, district ids ~600-700+, AC ids ~4123, etc.)
- a canonical **English name**
- a canonical **local-language name**
- a **parent** pointer (district -> state, AC -> district, etc.)
- a **created_on** date that captures bifurcation / reorganisation history (e.g. Telangana's split from Andhra Pradesh in 2014, J&K's UT reorganisation in 2019, Sikkim's 4 -> 6 district reorg in 2021)

## Why LGD is the canonical join key for yen-gov

Every non-electoral indicator that the Government of India publishes - NFHS health rounds, MoSPI NSO surveys, Census, RBI Handbook fiscal, NDLM air-quality, Bhuvan landcover, data.gov.in district-keyed datasets - references entities by **LGD id**. The LGD portal IS the authoritative spine for indicator joins.

If yen-gov adopted any other identity (ECI state codes, Census2001 numbering, OWID country codes adapted-to-states) as the internal join key, every future indicator would need a per-indicator translation table. That tax compounds. Within a year, yen-gov's adapter layer would be a pile of `lookup(eci_to_lgd[st_code])` translators scattered across every indicator family. This is the "chasing tails" failure mode the [LGD-canonical plan](../../docs/archive/plans/20260601-lgd-canonical-plan.md) exists to escape.

The strategic call (locked 2026-06-01): **LGD is the canonical internal join key for every geographic entity** in yen-gov. ECI codes survive only as election-domain display labels.

## How LGD differs from ECI

| Dimension | LGD | ECI |
| --- | --- | --- |
| Authority | Ministry of Panchayati Raj | Election Commission of India |
| Scope | Every administrative entity (state / district / AC / panchayat / ward / ULB / village) | Election artefacts (events, results, candidates, parties) |
| AC numbering | Globally-unique numeric id per AC (~4123 nationwide) | Per-state 1..N ballot enumeration |
| Identity stability | Names stable; numeric codes have historically reshuffled across census cycles (Census2001 -> Census2011) | Per-state numbering re-issued each delimitation cycle (2008 / 2018 / per-state) |
| Citizen-legibility | Opaque numeric ids (e.g. `lgd_ac_id = 33042`) | Citizen-recognised ballot numbers (e.g. `ac_no = 42` on the ballot paper) |

ECI is canonical for what it issues - elections. LGD is canonical for what IT issues - administrative geography. The principle "use the issuing authority's id" applies symmetrically; the LGD-canonical decision is just naming which authority issues what.

## How LGD looks in yen-gov data

- **Folder partitions** (per [ADR-0050](../architecture/data/canonical-store.md#adr-0050-folder-naming-lgd-slug)): `state=<lgd-name-slug>`, e.g. `datasets/boundaries/electoral/delim=2008/ac/state=haryana/all.geojson` (electoral AC subtree) or `datasets/boundaries/in/subdistricts/state=haryana/all.geojson` (admin spine).
- **Row columns**: every observation row carries an `lgd_state_id` / `lgd_district_id` / `lgd_ac_id` as the join attribute. The display-only `state_code` (ECI form) survives for citizen readability where it matters (URL slugs, election results pages).
- **Taxonomy authority**: `datasets/data/entities/lgd/` holds LGD snapshot CSVs (states, districts, ACs). Every join in yen-gov resolves through one of these files.

## How LGD looks to a citizen

A citizen never sees an LGD id. URLs use ECI ballot numbers + name slugs (per [ADR-0048](../architecture/frontend/charts/election-views.md#adr-0048-elections-drill-ia-and-tile-cartogram) and [ADR-0049](electoral-hierarchy.md#adr-0049-canonical-ac-join-key)):

```
/s/haryana/ac/42-rohtak           <-- citizen-facing URL (eci_no + name slug)
                                      lgd_ac_id is INTERNAL-ONLY, never in a URL
```

The folder partition (`state=haryana`) coincidentally is also citizen-legible because the LGD canonical name and the citizen slug happen to be the same shape. This is a deliberate by-product of the slug-stability choice: stable slug = stable URL = stable bookmark.

## What "GoI-only single source" means in practice

The execution handover ([docs/archive/plans/20260601-lgd-execution-handover.md](../../docs/archive/plans/20260601-lgd-execution-handover.md)) tightened the source doctrine: every entity row written into the canonical store traces to a Government of India source. Concretely:

- **Use** LGD portal for entity codes + names + parent pointers.
- **Use** ECI for election artefacts (events, results, candidates).
- **Use** Survey of India for geometry where it publishes; otherwise Bhuvan/NRSC; otherwise Census of India vintage.
- **Demote** community mirrors (ramSeraph, shijithpk, Garuda), academic compilations (Susewind), and Wikimedia overlays to **verification-only** Tier-3 references. They appear in research notes; they never get written into `datasets/data/entities/source.csv` as the citation of record.
- **Exception**: when GoI has not yet published a layer (e.g. J&K post-2022 AC geometry), use the best Tier-2 source AND open a follow-up ticket to ingest the GoI artefact when it appears.


## For future LLM agents reading this

If you (an LLM agent) are about to mint a new identity (a new state / district / AC) or join two indicators on a code:

1. The join key is the LGD id at the relevant level (`lgd_state_id` / `lgd_district_id` / `lgd_ac_id`).
2. The folder partition is `state=<lgd-name-slug>` (kebab-case English name from `lgd_states.json`).
3. The URL slug a citizen sees is the same kebab-case name. The ECI ballot number rides as a route segment (e.g. `/s/haryana/ac/42-rohtak`).
4. The citation row in `datasets/data/entities/source.csv` names the GoI authority that issued the fact (LGD for entity identity, ECI for election artefact, SoI/Bhuvan/Census for geometry).
5. If a community mirror snapshot was used to obtain the data, that goes in the source-hunt note under `docs/research/` or the relevant handover doc, not in `source.csv`.

## See also

- [ADR-0049](electoral-hierarchy.md#adr-0049-canonical-ac-join-key) - lgd_ac_id as canonical internal AC join key
- [ADR-0050](../architecture/data/canonical-store.md#adr-0050-folder-naming-lgd-slug) - folder convention `state=<lgd-name-slug>`
- [docs/archive/plans/20260601-lgd-canonical-plan.md](../../docs/archive/plans/20260601-lgd-canonical-plan.md) - strategic plan (archived)
- [docs/archive/plans/20260601-lgd-execution-handover.md](../../docs/archive/plans/20260601-lgd-execution-handover.md) - per-row execution split (archived)
- [docs/concepts/admin-level-sourcing.md](admin-level-sourcing.md) - LGD-golden doctrine context
- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) - how taxonomy seeds plug in

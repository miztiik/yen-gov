# Identifier Conventions

**Last Updated**: 2026-05-10

yen-gov never invents identifiers when an upstream authority publishes one (CLAUDE.md §3, Anti-pattern §10). Display names live as fields, not as keys. This document records which authority owns which kind of ID, and how to verify it.

## At a glance

| Concept              | ID source                                | Format                          | Example                                  |
| -------------------- | ---------------------------------------- | ------------------------------- | ---------------------------------------- |
| Country              | ISO 3166-1 alpha-2                       | `^[A-Z]{2}$`                    | `IN`                                     |
| State / UT (machine) | Election Commission of India (ECI)       | `^[SU]\d{2}$`                   | `S22` (Tamil Nadu)                       |
| State / UT (cross-ref) | ISO 3166-2                             | `^[A-Z]{2}-[A-Z0-9]{2,3}$`      | `IN-TN`                                  |
| District             | LGD (Local Government Directory) numeric, else Wikipedia URL slug | string | `603` or `tirunelveli-district` |
| Constituency         | ECI numeric, scoped by `(state, body)`   | integer ≥ 1                     | `167` in `(S22, AC)` is a TN AC          |
| Party                | ECI numeric code (string)                | `^\d+$`                         | `2866`                                   |
| Election event       | ECI URL slug                             | string                          | `AcGenMay2026`                           |

## Verification sources

### ECI state codes
ECI publishes state codes inside the URL of every result page:

```
https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm
                                                              ^^^
```

`S` prefix denotes a State, `U` prefix denotes a Union Territory. Two digits zero-padded. The mapping has shifted historically (Jammu & Kashmir was `S09` while a state, became `U` after 2019). **Source-of-truth is whatever the most recent ECI publication uses.** Older datasets must record the code in use *at the time of the event*.

### ISO 3166-2 codes
The ISO online browsing platform is authoritative: `https://www.iso.org/obp/ui/#iso:code:3166:IN`. These codes change rarely; the values committed here should match a current ISO publication.

### LGD district codes
Local Government Directory at `https://lgdirectory.gov.in/`. LGD assigns numeric codes to districts. Where LGD data is not accessible, fall back to a Wikipedia URL slug and set `id_source: "wikipedia"`. Never mix the two formats in a single id without recording the source. Catalogue of the LGD mirror yen-gov ingests from — 37 daily-refreshed entity tables, URL pattern, per-component adoption verdict — in [`lgd-opendata.md`](lgd-opendata.md).

### ECI constituency numbers
Constituency numbers appear in result URLs:

```
https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22167.htm
                                                              ^^^^^^^
                                                              S22 = state, 167 = AC number
```

Numbers are stable within `(state, body)` across elections **unless ECI redraws boundaries** (delimitation). When that happens, the new constituencies get the new numbers; old result files retain the numbers they were emitted with.

### ECI party codes
Visible inside party-wise winner URLs:

```
https://results.eci.gov.in/ResultAcGenMay2026/partywisewinresult-2866S22.htm
                                                                 ^^^^
                                                                 party 2866, in state S22
```

Stored as a string (not an integer) to preserve any leading zeros and to keep the type consistent with how ECI emits it.

### ECI event slugs
Used as the path segment after `/Result` in result URLs. `AcGenMay2026` = "Assembly (AC) General election, May 2026". yen-gov adopts the upstream slug verbatim as the **backend cohort identifier** (`backend/yen_gov/sources/eci/events.py` `EventInfo.event_id`, the `period_label` column in `datasets/data/datapoints/electoral/*.csv`, and the parse target of `parse_period_label`). Translation tables are bug magnets.

**Citizen-facing event slug (PR-W2a, 2026-06-10).** The citizen-facing `datasets/taxonomy/election_events.json` catalogue exposes a separate **citizen-readable slug** for the same event: `assembly-<YYYY>` for state assemblies, `general-<YYYY>` for national Parliament, `assembly-bye-<YYYY>-<seat-slug>` for assembly by-elections (state is in URL path), `general-bye-<YYYY>-<state-slug>-<seat-slug>` for Parliament by-elections. The catalogue carries the prior cohort id in a per-row `event_id_aliases[]` array (one-release strangler so legacy bookmarks still resolve). For example, `AcGenMay2026` (the backend cohort id) maps to `assembly-2026` (the citizen slug) on the catalogue, while the on-disk `period_label` value remains `AcGenMay2026`. The alias array is the bridge; see [docs/architecture/frontend/url-grammar.md](../architecture/frontend/url-grammar.md) for the URL contract.

## Composite paths

Where two upstream IDs combine to identify a thing, the directory structure mirrors the composition:

```
datasets/elections/AcGenMay2026/S22/results/167.json
                    └─ event ──┘ └state┘  └─AC─┘
```

This makes the path itself a complete primary key.

## When in doubt

Two rules:

1. **Cite the URL** in the file's `sources[]` entries (`url` + `fetched_at`). Future-you will thank present-you.
2. **Prefer the upstream code over a name.** Names get translated, transliterated, and abbreviated; codes don't.

## Canonical column names (SQLite emitters)

Per [ADR-0019](../architecture/data/canonical-store.md#adr-0019-dataset-topology-and-column-discipline), every SQLite emitter uses these exact column names whenever the underlying concept is present in a row. State and event are encoded in the **file path** (per ADR-0014); they appear as columns only in cross-state aggregates, where the literal is injected at query time.

| Column                | Type      | Concept                                            | Source row in §"At a glance" above |
| --------------------- | --------- | -------------------------------------------------- | ---------------------------------- |
| `state_eci_code`      | `TEXT`    | ECI state code, e.g. `S22`                         | State / UT (machine)               |
| `district_lgd_code`   | `INTEGER` | LGD numeric district code                          | District (LGD branch)              |
| `ac_eci_no`           | `INTEGER` | ECI Assembly Constituency number, scoped by state  | Constituency                       |
| `year`                | `INTEGER` | Calendar year, four digits                         | —                                  |

Adding a new canonical name (e.g. `pc_eci_no`, `block_lgd_code`, `village_lgd_code`, `gender`, `age_band`, `year_quarter`) is additive: append a row here in the same commit as the first emitter that uses it. **Renaming** an existing canonical column requires a follow-up ADR — every emitter and every saved `/explore` query depends on these names.

When the LGD code is not yet known for a district, fall back to `district_id` (`TEXT`) plus an `id_source` column with values `lgd` or `wikipedia`, per the District row in §"At a glance" above.

## See also

- [`docs/architecture/data-model.md`](../architecture/data-model.md) — entities the IDs key into.
- [`docs/reference/schemas.md`](schemas.md) — schemas that enforce the patterns above.
- [`docs/reference/lgd-opendata.md`](lgd-opendata.md) — LGD source catalogue (the upstream that issues `district_lgd_code`).
- [ADR-0019: dataset topology and column discipline](../architecture/data/canonical-store.md#adr-0019-dataset-topology-and-column-discipline) — why these column names are locked.
- `CLAUDE.md` §3 (identifier convention paragraph).

# Data Model

**Last Updated**: 2026-05-09

This document describes the entities yen-gov tracks, how they relate, and which schemas govern them.

## Entities

```
                       ┌──────────────┐
                       │   Country    │  (implicit; only "IN" today)
                       └──────┬───────┘
                              │
                       ┌──────▼───────┐         ┌──────────────┐
                       │    State     │◄────────│   Election   │  scope=state
                       │  (S22, …)    │         │ (AcGenMay…)  │
                       └──────┬───────┘         └──────┬───────┘
                              │                        │
                ┌─────────────┼─────────────┐          │
                │             │             │          │
       ┌────────▼─────┐  ┌────▼──────┐  ┌──▼───────┐  │
       │  District    │  │ Constit.  │  │ Party    │◄─┘  (per-event snapshot)
       │  (LGD/wiki)  │  │ (eci_no)  │  │ (eci #)  │
       └──────────────┘  └────┬──────┘  └────┬─────┘
                              │              │
                              └──────┬───────┘
                                     │
                            ┌────────▼──────────┐
                            │ ResultConstituency│  (per (event, state, body, eci_no))
                            └────────┬──────────┘
                                     │ aggregate
                            ┌────────▼──────────┐
                            │   ResultSummary   │  (per (event, state, body))
                            └───────────────────┘
```

## Identifiers

Every entity uses an identifier published by an upstream authority. yen-gov never invents IDs (CLAUDE.md §3). Display names are fields, not keys.

| Entity        | Key                                  | Schema                                         |
| ------------- | ------------------------------------ | ---------------------------------------------- |
| Country       | ISO 3166-1 alpha-2 (`IN`)            | implicit; appears in `state.schema.json`       |
| State         | ECI state code (`S22`)               | `state.schema.json`                            |
| District      | LGD numeric code, else Wikipedia slug| `district.schema.json`                         |
| Constituency  | `(state, body, eci_no)`              | `constituency.schema.json`                     |
| Party         | ECI numeric code (string), per event | `party.schema.json`                            |
| Election      | ECI URL slug (`AcGenMay2026`)        | `election.schema.json`                         |
| Per-AC result | `(election, state, body, eci_no)`    | `result.constituency.schema.json`              |
| Summary       | `(election, state, body)`            | `result.summary.schema.json`                   |

See [`docs/reference/identifiers.md`](../reference/identifiers.md) for the rationale and verification sources.

## Why party catalogs are event-and-state scoped

Parties merge, split, change symbols, switch alliances. A single global "parties" file would lie about what was true on a given polling date. So party snapshots live under the `(event, state)` slice:

```
datasets/elections/AcGenMay2026/S22/parties.json
```

When a future event reuses a party, it gets a new snapshot. ECI's numeric code typically remains stable, which is what makes longitudinal joins possible.

## Why districts and constituencies are state-scoped

Districts belong to a state by definition. Constituencies (for a given body — Assembly or Lok Sabha) are also numbered within a state. The `(state, body)` partition keeps file sizes manageable and makes the path itself self-describing:

```
datasets/reference/in/states/S22/districts.json
datasets/reference/in/states/S22/constituencies.json
```

## Per-AC result structure

A `result.constituency.json` carries:

- The full **top-N** candidates list (configurable via `config/processing.json`, default 5).
- **NOTA** broken out separately — never counted as a candidate.
- An **`others`** bucket that collapses everyone below top-N (count, total votes, share). Null if no collapsing happened.
- The `top_n_cutoff` value used at emit time, so consumers can reproduce the breakdown.
- A `winner` block with name, party, vote count, and margin (votes + percent).

This shape is a deliberate trade-off: full per-candidate fidelity inflates payloads (sometimes 50+ candidates per AC, mostly with <100 votes each) without informing any visualization. The `others` bucket preserves accurate totals while keeping the file small.

## Constituency hierarchy and status lifecycle

`constituency.schema.json` (current major version v4) carries the AC↔PC↔district relationship as first-class fields, gated by a file-level `status` lifecycle.

### Item-level fields

| Field             | Type                      | Required when            | Purpose |
| ----------------- | ------------------------- | ------------------------ | ------- |
| `district_id`     | string                    | `body=AC` ∧ `status=complete` | Hierarchical link to `district.id` in same state's districts file. |
| `pc_id`           | string `^[SU]\d{2}-PC-\d+$` | `body=AC` ∧ `status=complete` | Composite id of the PC this AC nests in. **Forbidden** when `body=PC`. |
| `electors`        | integer ≥ 0               | never                    | Latest electoral-roll snapshot. Optional. |
| `established_year`| integer                   | never                    | Year of the Delimitation Order that drew the current boundary. Optional. |

### File-level field

`status: "provisional" | "complete"` — required.

- **`provisional`** — file was bootstrapped from a single (typically Wikipedia) source. Hierarchy fields may be absent; this is intentional. Validator does not require `district_id` or `pc_id` per item.
- **`complete`** — file has been cross-checked against an authoritative ECI source (Delimitation Order 2008 PDF or `results.eci.gov.in` constituency pages). For `body=AC` the validator REQUIRES `district_id` and `pc_id` on every item. Promoting a file from `provisional` to `complete` MUST add the ECI URL to `sources[]` in the same commit.

Conditional requirement is enforced via JSON Schema `if/then/allOf`, so a single schema covers both AC and PC files and both lifecycle states.

### `pc_id` format

Composite string `<state>-PC-<eci_no>` (e.g. `S22-PC-2`). Chosen over a bare integer because:

- It is globally unique without context, so a downstream tool can treat it as a foreign key without first knowing the state.
- It mirrors the natural id of the eventual `body=PC` reference file (where `state="S22"` and `eci_no=2`), so a future cross-file resolver is mechanical.
- It survives copy-paste into bug reports without ambiguity.

### `electors` lives here, "change from previous" does not

`electors` is a property of the constituency at a point in time (electoral roll snapshot). It belongs on the reference object.

`electors_change_from_previous`, turnout %, and similar comparison metrics are properties of an *election result*, not the constituency. They belong on `result.constituency.schema.json` (or a derived comparison artifact). Putting them on the constituency object would conflate the entity with its history and force every reference file to know about elections that may not have happened yet.

### Source cascade for `status=complete`

A `complete` constituency file MUST have at least one ECI-domain URL in `sources[]`. Acceptable ECI sources, in order of authority:

1. ECI Delimitation of Parliamentary and Assembly Constituencies Order, 2008 (PDF on `eci.gov.in`).
2. ECI results portal constituency pages on `results.eci.gov.in` (confirms ECI numbering and reservation; does not directly give district or PC parent).
3. CEO state office publications for electoral roll counts (`ceo<state>.nic.in` / `ceo<state>.gov.in`).

Wikipedia remains a valid `provisional` source and may stay in `sources[]` after promotion (multi-entry `sources` per the [provenance contract](decisions/0002-provenance-as-sources-list.md) is exactly for this case).

### Hierarchy & lifecycle rationale

- AC↔PC↔district relationships are first-class, machine-readable, and validator-enforced for any file claiming completeness. Frontend search, district rollups, and PC-level analytics work without extra joins.
- `status` lets us ship Wikipedia-bootstrapped reference data immediately (CI passes) without lying that it has been ECI-validated.
- Splits result-time metrics (turnout, change-vs-previous) from reference-time properties (electors, district), keeping both schemas honest.
- One schema, conditional requirements — no duplication between AC and PC files.

Acknowledged costs:

- `provisional` files exist in the repo. A reader skimming a file must check `status` before trusting that `district_id`/`pc_id` exhaust the universe. Mitigated by surfacing `status` prominently in any visualization.
- Promoting to `complete` is real work — for TN it means reading the 2008 Delimitation Order to confirm 234 AC→PC mappings and 234 AC→district mappings. Acceptable: that work is the entire point.

### Hierarchy & lifecycle — alternatives considered

- **Make `district_id` and `pc_id` unconditionally required.** Rejected: forces ECI cross-check before any reference file can land, blocking the entire frontend on the slowest data path. The two-commit rollout (`status=provisional` → `status=complete`) operationalizes the user-approved plan cleanly.
- **Embed Lok Sabha constituency by *name* rather than id.** Rejected: PC names are not unique across states (e.g. multiple "Bangalore"s historically), and they are renamed more often than ECI numbers change. An id-based reference is a foreign key; a name is a label.
- **Add `previous_name` / `succeeded_by` lineage fields now.** Rejected as scope creep. Useful but not requested; can land in a future minor bump.
- **Put `electors` and "change from previous" both on the constituency object.** Rejected: see "where does change-from-previous live" above. Conflating entity and event always rots.
- **Use a separate `hierarchy.json` file mapping AC→PC→district instead of inline fields.** Rejected: one more file to keep in sync, no real upside. The hierarchy IS the constituency definition; splitting it across files is bureaucracy.

## See also

- [`docs/architecture/data-flow.md`](data-flow.md) — how data moves through the system.
- [`docs/reference/schemas.md`](../reference/schemas.md) — current schema versions.
- [`docs/reference/identifiers.md`](../reference/identifiers.md) — ID source-of-truth conventions.
- [`docs/concepts/electoral-hierarchy.md`](../concepts/electoral-hierarchy.md)
- [Provenance contract (ADR-0002)](decisions/0002-provenance-as-sources-list.md)
- `CLAUDE.md` §3, §11, §12 — authoritative contracts.

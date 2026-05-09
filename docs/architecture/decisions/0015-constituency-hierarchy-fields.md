# ADR-0015: Constituency hierarchy fields (`district_id`, `pc_id`) and `status` lifecycle

**Last Updated**: 2026-05-09
**Status**: accepted

## Context

Schema v3.0 of `constituency.schema.json` carried only `eci_no`, `name`, `reservation`, and an *optional* `district_id`. That shape lets us bootstrap a state's constituency list from Wikipedia in one shot, but it loses two relationships that are intrinsic to Indian electoral geography:

1. **District** — every Assembly Constituency (AC) sits inside exactly one district. Optional `district_id` lets a file ship without it; that defers a problem we will hit on every consumer (search, district-level rollups, "how did Coimbatore vote").
2. **Lok Sabha (PC) parent** — every AC nests inside exactly one Parliamentary Constituency per the Election Commission's Delimitation Order. v3.0 had no field for this at all. Without it we cannot answer "how does a PC's component ACs split politically", which is one of the highest-value cross-body queries on this dataset.

Wikipedia tables for `List_of_constituencies_of_the_<state>_Legislative_Assembly` carry `District`, `Lok Sabha constituency`, and (often) `Number of electors` columns. The fields are available; v3.0 simply did not name them. The user's directive: "district has to be mandatory, which Lok Sabha constituency it is part of has to be mandatory because these two are hierarchical entities. [They] should always exist."

The user also asked about `electors` (count) and "change from previous election". The first is a stable-ish constituency property (electoral roll snapshot). The second is *not* — it is a derived comparison between two election results and belongs in `result.constituency.schema.json`, not in reference data. This ADR codifies that split.

The user further asked for a second, authoritative source to validate Wikipedia. The ECI's [Delimitation of Parliamentary and Assembly Constituencies Order, 2008](https://eci.gov.in/delimitation-website/) is the legal source for AC↔PC↔district mapping; the CEO state offices publish electoral roll PDFs for elector counts; `results.eci.gov.in` confirms ECI numbering. None of these are scrapable in one go, and none are needed to *start* a constituency file — only to *finalize* it. This motivates a `status` lifecycle.

## Decision

### Schema v4.0 adds four item-level fields

| Field             | Type                      | Required when            | Purpose |
| ----------------- | ------------------------- | ------------------------ | ------- |
| `district_id`     | string                    | `body=AC` ∧ `status=complete` | Hierarchical link to `district.id` in same state's districts file. |
| `pc_id`           | string `^[SU]\d{2}-PC-\d+$` | `body=AC` ∧ `status=complete` | Composite id of the PC this AC nests in. **Forbidden** when `body=PC`. |
| `electors`        | integer ≥ 0               | never                    | Latest electoral-roll snapshot. Optional. |
| `established_year`| integer                   | never                    | Year of the Delimitation Order that drew the current boundary. Optional. |

### Schema v4.0 adds one file-level field

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

Wikipedia remains a valid `provisional` source and may stay in `sources[]` after promotion (multi-entry `sources` per ADR-0002 is exactly for this case).

## Consequences

- **Good**: AC↔PC↔district relationships are first-class, machine-readable, and validator-enforced for any file claiming completeness. Frontend search, district rollups, and PC-level analytics work without extra joins.
- **Good**: `status` lets us ship Wikipedia-bootstrapped reference data immediately (CI passes) without lying that it has been ECI-validated.
- **Good**: Splits result-time metrics (turnout, change-vs-previous) from reference-time properties (electors, district), which keeps both schemas honest.
- **Good**: One schema, conditional requirements — no duplication between AC and PC files.
- **Cost**: `provisional` files exist in the repo. A reader skimming a file must check `status` before trusting that `district_id`/`pc_id` exhaust the universe. Mitigated by surfacing `status` prominently in the file and in any future visualization.
- **Cost**: Promoting to `complete` is real work — for TN it means reading the 2008 Delimitation Order to confirm 234 AC→PC mappings and 234 AC→district mappings. Acceptable: that work is the entire point.
- **Migration**: Schemas v3.0 → v4.0 is a major bump. The one existing data file (`datasets/reference/in/states/S22/constituencies.json`) is rewritten in this commit to add `status: "provisional"` and bump `$schema_version`. No `district_id` / `pc_id` added yet — that ships in a follow-up commit when the ECI cross-check happens.

## Alternatives considered

- **Make `district_id` and `pc_id` unconditionally required.** Rejected: forces ECI cross-check before any reference file can land, blocking the entire frontend on the slowest data path. The user explicitly approved a two-commit rollout, which `status=provisional` operationalizes cleanly.
- **Embed Lok Sabha constituency by *name* rather than id.** Rejected: PC names are not unique across states (e.g. multiple "Bangalore"s historically), and they are renamed more often than ECI numbers change. An id-based reference is a foreign key; a name is a label.
- **Add `previous_name` / `succeeded_by` lineage fields now.** Rejected as scope creep. Useful but not requested; can land in a future minor bump.
- **Put `electors` and "change from previous" both on the constituency object.** Rejected: see "where does change-from-previous live" above. Conflating entity and event always rots.
- **Use a separate `hierarchy.json` file mapping AC→PC→district instead of inline fields.** Rejected: one more file to keep in sync, no real upside. The hierarchy IS the constituency definition; splitting it across files is bureaucracy.

## See also

- Schema: [`datasets/schemas/constituency.schema.json`](../../../datasets/schemas/constituency.schema.json) (v4.0)
- Concept primer: [`docs/concepts/electoral-hierarchy.md`](../../concepts/electoral-hierarchy.md)
- Provenance contract: [ADR-0002](0002-provenance-as-sources-list.md), [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md)
- Identifiers: ECI codes (state, AC/PC `eci_no`), LGD codes (district), per CLAUDE.md §3.

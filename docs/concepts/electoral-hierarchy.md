# Electoral Hierarchy

**Last Updated**: 2026-05-09

> Indian electoral geography is a strict hierarchy. Every Assembly Constituency (AC) sits inside exactly one district AND exactly one Lok Sabha (Parliamentary) Constituency (PC). yen-gov's reference data treats both relationships as first-class, validator-enforced fields.

## The hierarchy

```
Country (IN)
└── State / UT (S22 = Tamil Nadu, …)
    ├── District (LGD code or Wikipedia slug)
    │   └── Assembly Constituency (AC)        ← `body=AC`, `eci_no` 1..N within state
    └── Parliamentary Constituency (PC)       ← `body=PC`, `eci_no` 1..M within state
        └── (each AC also nests under one PC)
```

Two facts make this a *strict* hierarchy for ACs:

1. **An AC is wholly inside one district.** District boundaries are administrative; AC boundaries are drawn so they never split a district. (When a district is later carved out of an older one, ACs migrate cleanly to the new district.)
2. **An AC is wholly inside one PC.** This is set by the Election Commission's [Delimitation of Parliamentary and Assembly Constituencies Order, 2008](https://eci.gov.in/delimitation-website/) and revised only when delimitation is redone (currently scheduled post-2026 census).

PCs themselves do *not* nest inside districts — a single PC routinely spans 6–8 districts. So `district_id` is required on AC items but absent from PC items, and `pc_id` is required on AC items but forbidden on PC items.

## Why this matters for the schema

Without these two fields you cannot answer questions every consumer of this dataset will ask:

- "Show me all ACs in Coimbatore district" — needs `district_id` on each AC.
- "How did the 7 ACs that make up the Sriperumbudur Lok Sabha seat split between alliances?" — needs `pc_id` on each AC.
- "What is the district-level swing between 2021 and 2026?" — needs `district_id` to aggregate AC results.
- Free-text search for "Coimbatore" returning both the PC and its constituent ACs — needs the link.

These are the bread-and-butter queries of election analysis, not edge cases. Reference data that omits the hierarchy forces every consumer to reinvent it from PDFs, which is exactly the kind of work the project exists to eliminate once.

## The `status` lifecycle

Reference files declare a `status`:

- **`provisional`** — bootstrapped from a single source (typically Wikipedia). Hierarchy fields MAY be absent. Useful for shipping the long tail quickly without lying about validation.
- **`complete`** — cross-checked against an authoritative ECI source (Delimitation Order 2008 or `results.eci.gov.in`). For `body=AC`, `district_id` and `pc_id` are REQUIRED on every item. Promotion to `complete` adds the ECI URL to `sources[]` in the same commit.

This is enforced by the validator via JSON Schema `if/then`. A `complete` AC file missing `pc_id` on any item fails CI.

See [data-model.md](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle) for the full rationale.

## Source cascade

For Indian electoral geography, the trustworthy sources in descending order:

| Source | Authority for | Trade-off |
| ------ | ------------- | --------- |
| ECI Delimitation Order 2008 (PDF) | AC↔PC↔district mapping, reservation, AC/PC numbering | Authoritative but PDF; one-time scrape per state |
| `results.eci.gov.in` constituency pages | ECI numbering, name spelling, reservation | Live; no district/PC mapping |
| CEO state office (`ceo<state>.nic.in`) | Electoral roll counts, polling station lists | Inconsistent format across states |
| LGD portal (`lgdirectory.gov.in`) | District codes, names, lineage | Authoritative for districts, irrelevant for constituencies |
| Wikipedia constituency-list pages | All of the above, in one table | Crowd-sourced; useful for bootstrap, never sufficient alone for `complete` |

## What goes where

| Field | Lives on | Why |
| ----- | -------- | --- |
| `district_id`, `pc_id` | constituency reference (`constituency.schema.json`) | Stable hierarchy; doesn't change between elections |
| `electors` (snapshot) | constituency reference, optional | Roll snapshot is closer to a constituency property than to a result |
| `established_year` | constituency reference, optional | Property of the boundary, not of any one election |
| Turnout %, votes-cast counts, change vs. previous election | result schemas (`result.constituency.schema.json`) | Properties of an *election event*, not of the constituency itself |
| Winner, candidate list | result schemas | Same |

This split keeps reference data stable across elections and makes result-time data composable.

## See also

- [data-model.md — Constituency hierarchy fields and status lifecycle](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle)
- [backend/sources-eci.md — ECI Statistical Reports as canonical past-election source](../architecture/backend/sources-eci.md#authority-hierarchy-for-past-elections)
- [`docs/reference/data-sources.md`](../reference/data-sources.md) — live catalogue of every external source
- [`datasets/schemas/constituency.schema.json`](../../datasets/schemas/constituency.schema.json) (v4.0)
- [`docs/concepts/data-provenance.md`](data-provenance.md) — how `sources[]` interacts with `status`
- CLAUDE.md §3 — identifier convention (ECI / LGD / Wikipedia slug)

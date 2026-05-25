# Village coverage gap — 9 states/UTs missing from upstream

**Date**: 2026-05-25
**Phase**: C (village national lift)
**Authority for this note**: Max (Indicator Scout — what upstream we should source) + Hans (Governance — fiscal-federalism framing of the gap).

## Summary

The ramSeraph `LGD_Villages.geojsonl` upstream extract (used by Phase C) carries village polygons for 27 of India's 36 states/UTs. **9 states/UTs are missing** from the upstream feed and were therefore not emitted by [`tools/boundaries/lift_villages_national.py`](../tools/boundaries/lift_villages_national.py):

| ECI | State / UT | Plan-doc had this in the gap? |
| --- | --- | --- |
| S02 | Arunachal Pradesh | Yes ("AR") |
| S08 | Himachal Pradesh | Yes ("HP") |
| S14 | Manipur | Yes ("MN") |
| S15 | Meghalaya | Yes ("ML") |
| S16 | Mizoram | Yes ("MZ") |
| S17 | Nagaland | Yes ("NL") |
| S21 | Sikkim | Yes ("Sikkim") |
| U08 | Jammu and Kashmir (UT) | Yes ("J&K") |
| U09 | Ladakh | **No (implicit)** — the plan-doc's "J&K" item was counted as a single state; in the post-2019 entity geometry it is two (UT J&K = U08, UT Ladakh = U09). Both are missing upstream. |

The plan-doc's "8-state gap" estimate is corrected here to **9** for accuracy.

## What this means for citizens TODAY

Citizens looking at a state's hub for one of these 9 will not see per-village polygons on any district drill-down page. The next layer up (district polygons via ramSeraph `LGD_Districts`) is on disk for all 9 — village-level drill is the only thing missing.

Today no citizen surface in the codebase actually consumes village-level geometry beyond Tamil Nadu's smoke pages, so this gap is **not citizen-visible** as of this PR. It would become visible only when:

1. A village-keyed indicator ships (e.g. a JJM coverage tracker or a Census-2011 village-level metric), AND
2. The frontend renders that indicator on a village-drilled choropleth for a state in the gap list.

The order of operations is on our side: indicator before geometry. The gap is recorded here so that when (1) lands, (2) is a known follow-up rather than a surprise 404.

## Possible fall-backs (deferred, NOT in scope for Phase C)

The ramSeraph release also carries:

- `bhuvan_villages.geojsonl.7z` — bhuvan-derived village polygons with broader (but not exhaustive) coverage. Different upstream than LGD; uses bhuvan-internal village identifiers, not `village_lgd`. Pivoting to bhuvan for the 9 gap states would introduce a mixed-key ledger (`village_lgd` for 27 states, bhuvan internal codes for 9), which would propagate into every village-keyed indicator's join logic.
- `Bhuvan_JK_Villages.geojsonl.7z` — J&K-specific bhuvan extract. Same mixed-key trade-off but scoped to U08 + (likely) U09.

The Phase C plan-doc anchor said bhuvan fall-back is **OUT OF SCOPE for Phase C**, and that holds:

- Adopting a mixed-key boundary ledger is a join-discipline change with downstream blast radius (every village-keyed indicator's vitest contract has to learn the dispatch logic). That's a separate PR with its own design conversation (Gregor: data contract; Fowler: join code).
- We haven't shipped a village-keyed citizen indicator yet, so the bhuvan adoption has no concrete citizen-need behind it. Speculative adoption is exactly the over-engineering trap the plan-doc was built to avoid.

## Decision logic when (if) a village-keyed indicator ships for a gap state

When a citizen surface needs village geometry for one of the 9 gap states:

1. **First check**: does the surface render at district zoom, NOT village zoom? If yes, the existing district polygons are sufficient and no fall-back is needed.
2. **If village zoom is unavoidable**: open a follow-up PR that adopts the bhuvan fall-back for ONLY the requested gap state(s), with explicit `boundary_layers.parquet` rows carrying a separate `source_id` (so the citation panel is honest about provenance: "bhuvan, not LGD"). Add a join-discipline test asserting the village-keyed indicator's join logic handles BOTH `village_lgd` (canonical) and `bhuvan_village_id` (fall-back) without ambiguity.
3. **Only adopt bhuvan for the specific gap states** — do NOT replace the 27 LGD-keyed states. Mixing is acceptable per-state; mixing within a state is not.

## Other notes

- The 27 emitted states cover every state where LGD_Villages publishes geometry. No state has a partial extract (e.g. "Karnataka but only 10 of 31 districts") — coverage is binary at the state level.
- Total villages across emitted states: 584,615. The 9 gap states would add roughly ~25k–40k villages (rough estimate: the missing states are mostly low-population NE + hill states with smaller village counts; the LGD villages master at ~620k nationally implies ~35k for the gap).
- `state_lgd_resolver.load_state_lgd_to_eci_map(entities.json)` returned 36 mappings (every active state/UT); the orchestrator iterates all 36 and silently skips states with zero buckets. The "skip silently" behaviour is what kept the emitted count clean — no per-gap-state "0 villages" log line clutter.

## Cross-references

- [Phase C plan-doc anchor](../TODO/20260524-boundary-coverage-expansion-plan.md#phase-c--village-national-lift)
- [Boundary data sources catalogue](../docs/reference/boundary-data-sources.md)
- [ADR-0031: Boundary geometry strategy](../docs/architecture/decisions/0031-boundary-geometry-strategy.md)

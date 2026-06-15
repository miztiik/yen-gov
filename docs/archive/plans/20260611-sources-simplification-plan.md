# Sources simplification -- extraordinary cleanup plan (CLOSED + DISTILLED)

**Last Updated**: 2026-06-15
**Status**: Closed 2026-06-11 (PR-0 + PR-1 both merged); distilled 2026-06-15.
**Level**: 3 (cross-cutting; 2 PRs; provenance + 6 chart renderers + doctrine; reversible).

User mandate (2026-06-11): "sources is becoming nuisance, simplify extraordinarily." Triggered by a screenshot of the legacy 11-column v2 footer rendering "License unknown / Confidence unknown / Verification unknown" on every row. Two PRs shipped the rip; this archive is the audit ledger.

## Shipped

| Row | Title | PR | Commit | Merged |
|---|---|---|---|---|
| PR-0 | Doctrine rewrites (CLAUDE.md section 12 + data-provenance.md + canonical-store.md section 5) + ship dark `frontend/src/lib/sources/` package + contract test | #943 | `eb6066b4c` | 2026-06-11 |
| PR-1 | Backend `owner` -> `producer` rename (4 writers + CSV header + schema) + drop DuckDB `owner AS producer` alias + rewrite SourceList component + rewire 6 callers + delete v2 dead branch (SourceListV2 + source-list-v2 package + v1 SourceList) | #945 | `557278e91` | 2026-06-11 |

## Deferred

| Item | Trigger | Notes |
|---|---|---|
| PR-2 -- Issuing-authority warning surface ("Includes Wikipedia-derived data" conditional one-liner when a card mixes issuing-authority + non-authority publishers) | User-triggered, not date-gated | Hans verdict 2026-06-11: cost is ~4 lines of view-model + a hand-authored 8-publisher allow-list. Defer until real-world card behaviour surfaces the need. NOT in any active follow-up tracker; this archive entry IS the durable trigger record. |

## Where the durable findings live now (distillation routing per docs/how-to/distill-a-plan.md)

| Finding | Distilled home |
|---|---|
| Sources schema is a 5-column citation ledger, identity-on-`(producer, title, vintage)`-triple, single global table | [CLAUDE.md](../../../CLAUDE.md) section 12 + Holy Law #9 |
| 7-point inventory of how yen-gov diverges from OWID `origin.*` (the 5-column subset + no fetch telemetry + single `url` + deterministic PK + extended `vintage` + global table + `producer` rename) | [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) Named Divergence #7 |
| Why the 5-column shape was chosen + rejected alternatives (backfill sentinels; operator-only annotation layer; collapse ledger to one row per producer; keep chip-pill render style; OWID `url_main` rename) | [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) |
| Field-by-field rationale + "what is NOT in the schema" table + parties-dimension coupling | [docs/architecture/data/canonical-store.md](../../architecture/data/canonical-store.md) section 5 |
| Frontend pill grammar (plain-text middot, no chip; one publisher x major-series pill; max 3 inline + "+N more"; mute when url empty) | [frontend/src/lib/sources/README.md](../../../frontend/src/lib/sources/README.md) + the `sources/` package itself |
| Hash function `derive_source_id(producer, title, vintage)` is the 3-arg identity contract (Holy Law #9 surface) | [backend/yen_gov/canonical/citation.py](../../../backend/yen_gov/canonical/citation.py) |
| `fetched_at smear` lesson (why fetch telemetry was removed from the citation row) | `/memories/lessons.md` 2026-05-16 (already captured); summarised in [data-provenance.md](../../concepts/data-provenance.md) |

## Persona verdicts archive

The 4 persona verdicts (Jony pill grammar; Hans citation integrity; Gregor schema contract; Citizen gut-check) that drove the 4-way convergence on path alpha (shrink doctrine to 5 cols, render-time aggregator, plain-text pill, no chip) are summarised in [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) under the rationale section and the rejected-alternatives table. The plan-doc's original verbatim transcripts were operational scaffolding; the distilled summaries are the live knowledge.

## See also

- [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md) -- the runbook this archive follows.
- [CLAUDE.md](../../../CLAUDE.md) section 5 (Documentation Discipline) + section 12 (Data Provenance).
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) -- the concept-doc home for the rationale.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) -- the divergence registry.
- [docs/architecture/data/canonical-store.md](../../architecture/data/canonical-store.md) section 5 -- the schema authority.

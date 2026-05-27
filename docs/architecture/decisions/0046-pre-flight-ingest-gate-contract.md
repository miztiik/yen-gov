# ADR-0046: Pre-flight ingest gate contract

**Status**: Accepted
**Date**: 2026-05-27
**Deciders**: Gregor (contract), Fowler (refactor), with Hans + Max ratification on the six-check set

## Context

CLAUDE.md §1 Holy Law #5 (structural fixes only) and §10 anti-patterns ("Skip the pre-ingest overlap check before adding any new ingest") put the onus on every agent shipping a new ingest to manually run [`python -m yen_gov check-overlap`](../../../backend/yen_gov/cli.py) and to paste the verdict into the handover-doc per [TODO/_TEMPLATE-ingest-handover.md](../../../TODO/_TEMPLATE-ingest-handover.md) §3. Practice has shown this is fragile:

- Six guardrails (#6, #13-#18) all touch new-ingest authoring; each is enforced by a separate Tier-B check or a separate doctrine paragraph. Agents discover them PR-by-PR rather than in one batch.
- The overlap check is invoked manually; agents sometimes omit it, then a downstream Tier-B check fails the PR after substantial work is done.
- The handover-doc verdict is plain text — a reviewer cannot mechanically diff "what the proposal said" against "what the registry actually returns" today vs at PR-open time.
- The grain-rip arc (#388 through #406) re-confirmed that DRY drift between predicates (e.g. `_INDICATOR_ID_GRAIN_PREFIX_RE` lived only in `validate.py`) makes the rules hard for a CLI to evaluate on a candidate proposal that does not yet exist in the repo.

## Decision

Mint a **pre-flight ingest gate** at `python -m yen_gov pre-flight-ingest` that runs the six mechanical checks in a single batched call and emits a typed [PreflightReport](../../../backend/yen_gov/preflight/__init__.py) (validated against [preflight-report.schema.json](../../../datasets/schemas/preflight-report.schema.json) v1.0). Agents cite the report path in the handover-doc; CI rejects PRs that ship a `proposal.json` under `TODO/` whose report exits with code 2.

### The six checks (single source of truth)

| # | check | predicate | failure verdict |
|---|---|---|---|
| 1 | `concept_overlap` | `concept_registry.find_overlap` | drives `mint_new` / `upsert` / `add_facet` |
| 2 | `concept_fk` | `predicates.concept_id_exists` | warn (if `mint_new` without new concept row) / fail (if FK not resolvable) |
| 3 | `grain_prefix` | `predicates.grain_prefix_violation` | fail (abort) |
| 4 | `update_period_days` | `predicates.update_period_days_violation` | fail (abort) |
| 5 | `justification` | `predicates.justification_violation` | fail (abort) |
| 6 | `source_id_derivation` | `predicates.source_id_derivation_violation` | fail (abort) |

### Module layout

```
backend/yen_gov/preflight/
  __init__.py         # orchestrator: build_report(), load_proposal(), PreflightReport
  predicates.py       # six pure predicates (single source of truth)
```

`backend/yen_gov/validate.py` Tier-B wrappers (`tier_b_indicator_id_no_grain_prefix`, `tier_b_indicator_freshness_declared`, `tier_b_no_hand_typed_source_id`, `tier_b_indicator_has_justification`) become thin wrappers calling into `preflight.predicates`. A predicate-parity test (`backend/tests/test_preflight_predicates.py::test_predicate_parity_with_tier_b`) asserts the two seams cannot drift.

### Verdict / exit-code mapping

| verdict | exit code | agent action |
|---|---|---|
| `mint_new` (no overlap >= 0.70) | 0 | proceed; mint new id; new concepts.json row REQUIRED in same PR |
| `upsert` (overlap >= 0.85) | 0 | UPSERT into existing indicator (new vintage / publisher) |
| `add_facet` (0.70 <= overlap < 0.85) | 0 | add a facet axis on existing indicator |
| any of above + soft warn | 1 | proceed with the named concern documented |
| `abort` (any check `fail`) | 2 | correct proposal and re-run; **no override flag** (Holy Law #5) |

### Deterministic `generated_at`

The report's `generated_at` field is `preflight:sha256:<hex16>` derived from a canonical JSON dump of `input_echo`, NOT a wall-clock timestamp (CLAUDE.md §10 anti-pattern). The carve-out for control-plane artifacts does NOT apply: the report is agent-consumable contract output that should diff cleanly between two runs against the same input.

## Rejected alternatives

**(A) Run the checks at PR-open time via CI only, no agent-facing CLI.** Rejected: agents discover failures post-push, slowing the loop and burning CI minutes. The whole point is to enforce before code is written, not after.

**(B) Add an `--override` / `--force` flag for "the orchestrator is sure".** Rejected by Hans + Holy Law #5. The six checks are mechanical truths; if a check fails, the proposal is wrong, not the gate.

**(C) Inline-copy the predicate bodies into `preflight/` instead of `git mv`-style refactor.** Rejected: two seams will drift; the entire point of the predicates module is single-source-of-truth. The parity test makes drift impossible to land silently.

**(D) Use wall-clock `datetime.now()` for `generated_at`.** Rejected per CLAUDE.md §10. The report is a contract output, not a control-plane log line.

## Consequences

- Agents now have ONE command to run before any new ingest; no more PR-by-PR discovery of guardrails.
- Tier-B `tier_b_*` functions in `validate.py` shrink and share a single predicate seam with the pre-flight gate.
- The handover-doc template ([TODO/_TEMPLATE-ingest-handover.md](../../../TODO/_TEMPLATE-ingest-handover.md)) §3 now requires citing a `report.json` path; the CI workflow extension fails loud if the report exits with code 2.
- Adding a 7th check is a single-file edit in `predicates.py` plus a wrapper call in `preflight/__init__.py`; see [docs/architecture/backend/preflight.md](../backend/preflight.md).

## References

- [docs/concepts/pre-flight-ingest.md](../../concepts/pre-flight-ingest.md) — what the six checks are, exit codes, report shape
- [docs/architecture/backend/preflight.md](../backend/preflight.md) — module layout, how to add a 7th check
- [docs/agents/ingest-checklist.md](../../agents/ingest-checklist.md) — agent-followable checklist with literal commands + decision tree
- [ADR-0034](0034-documentation-routing-contract.md) — documentation routing contract
- [ADR-0044](0044-grain-over-entity.md) — grain-over-entity (predicate #3)
- [docs/concepts/ingest-fetch-enrich-separation.md](../../concepts/ingest-fetch-enrich-separation.md) — the layered pipeline this gate fronts

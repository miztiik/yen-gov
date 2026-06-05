# Pre-flight ingest gate (subsystem)

**Last Updated**: 2026-05-27

> Module-level reference for [`backend/yen_gov/preflight/`](../../../backend/yen_gov/preflight/). User-facing semantics live in [docs/concepts/pre-flight-ingest.md](../../concepts/pre-flight-ingest.md); design rationale in [ADR-0046](../decisions/0046-pre-flight-ingest-gate-contract.md).

## Module layout

```
backend/yen_gov/preflight/
  __init__.py        # orchestrator + types
  predicates.py      # six pure predicates (single source of truth)
```

### `predicates.py`

Pure functions over primitive inputs. No I/O. Re-used by:

1. `yen_gov.preflight.build_report` (this subsystem)
2. `yen_gov.validate.tier_b_*` wrappers (the on-disk validators)

The parity test [backend/tests/test_preflight_predicates.py](../../../backend/tests/test_preflight_predicates.py) asserts that for any synthetic catalogue fixture, the Tier-B wrappers report exactly the violations the predicates compute. Drift is therefore impossible to land silently.

### `__init__.py`

Public surface:

- `build_report(proposal: dict, *, root: Path) -> PreflightReport` — runs all six checks against the proposal + repo root.
- `load_proposal(*, proposal_file: Path | None, cli_overrides: dict | None) -> dict` — file always wins.
- `PreflightReport`, `CheckResult`, `RecommendedAction` — frozen dataclasses with `to_dict()` for JSON emit.
- `PREFLIGHT_REPORT_SCHEMA_VERSION` — pinned to the `x-version` of [preflight-report.schema.json](../../../datasets/schemas/preflight-report.schema.json).

The orchestrator is a straight-line sequence of six checks. It does not short-circuit on the first failure — agents benefit from seeing ALL the violations in one report.

## CLI surface

```
python -m yen_gov pre-flight-ingest \
  --proposal-file TODO/<date>-<source>-ingest/proposal.json \
  --report        TODO/<date>-<source>-ingest/report.json
```

CLI flag sugar (`--proposed-id`, `--family`, etc.) hydrates an in-memory proposal when no file is supplied. When both are given the file wins.

## Adding a seventh check

1. Write the pure predicate in `predicates.py` (input: primitives; output: `str | None` or `list[...]`).
2. Add a `CheckResult` block in `build_report` after the existing six.
3. Add a parametrized test case in `backend/tests/test_preflight_predicates.py`.
4. Add a canned-fixture verdict in `backend/tests/test_preflight_report_schema.py`.
5. Bump `preflight-report.schema.json` `x-version` to 1.1 (additive — new `checks[]` entry, no schema-shape change) with an `x-changelog` entry per [CLAUDE.md §11](../../../CLAUDE.md).
6. If the check needs a Tier-B counterpart, add a thin wrapper in `validate.py` that imports the predicate and chain it into `validate.run()` as a separate test sentinel.

## Layer rule

`backend/yen_gov/preflight/` lives under `backend/`, NOT `tools/`. Per CLAUDE.md §4 layer rule, `tools/` cannot import from `backend/`; the gate is core enforcement, not standalone tooling.

---

## Design rationale

This section consolidates the rationale (Context + Decision + Consequences, condensed) of the originating ADR that pinned the cross-cutting choice for this subsystem (the pre-flight gate contract); the originating ADR file under `docs/architecture/decisions/` was deleted in [docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md](../../archive/plans/20260604-d-doc3-adr-retire-subplan.md) D-DOC3.10 closure. The redirect map lives at [decision-index.md](../../reference/decision-index.md). Folded into this doc per D-DOC3.8 (2026-06-04).

### ADR-0046: pre-flight-ingest-gate-contract

Status: accepted 2026-05-27. Deciders: Gregor (contract), Fowler (refactor), with Hans + Max ratification on the six-check set.

**Context.** [CLAUDE.md section 1 Holy Law #5](../../../CLAUDE.md) (structural fixes only) and section 10 anti-patterns ("Skip the pre-ingest overlap check before adding any new ingest") put the onus on every agent shipping a new ingest to manually run `python -m yen_gov check-overlap` and to paste the verdict into the handover-doc per [TODO/_TEMPLATE-ingest-handover.md](../../../TODO/_TEMPLATE-ingest-handover.md) section 3. Practice has shown this is fragile: six guardrails (#6, #13-#18) all touch new-ingest authoring; each is enforced by a separate Tier-B check or a separate doctrine paragraph, so agents discover them PR-by-PR rather than in one batch. The overlap check is invoked manually; agents sometimes omit it, then a downstream Tier-B check fails the PR after substantial work is done. The handover-doc verdict is plain text - a reviewer cannot mechanically diff "what the proposal said" against "what the registry actually returns" today vs at PR-open time. The grain-rip arc (#388 through #406) re-confirmed that DRY drift between predicates (e.g. `_INDICATOR_ID_GRAIN_PREFIX_RE` lived only in `validate.py`) makes the rules hard for a CLI to evaluate on a candidate proposal that does not yet exist in the repo.

**Decision.** Mint a pre-flight ingest gate at `python -m yen_gov pre-flight-ingest` that runs the six mechanical checks in a single batched call and emits a typed `PreflightReport` (validated against `preflight-report.schema.json` v1.0). Agents cite the report path in the handover-doc; CI rejects PRs that ship a `proposal.json` under `TODO/` whose report exits with code 2. The six checks are `concept_overlap` (drives `mint_new` / `upsert` / `add_facet` verdict), `concept_fk` (warn if `mint_new` without new concept row; fail if FK not resolvable), `grain_prefix` (fail), `update_period_days` (fail), `justification` (fail), and `source_id_derivation` (fail). Verdict / exit-code mapping: `mint_new` / `upsert` / `add_facet` = 0; any of those + soft warn = 1; `abort` = 2 (no override flag per Holy Law #5). The report's `generated_at` field is `preflight:sha256:<hex16>` derived from a canonical JSON dump of `input_echo`, NOT a wall-clock timestamp ([CLAUDE.md section 10](../../../CLAUDE.md) anti-pattern); the control-plane carve-out does NOT apply because the report is agent-consumable contract output that should diff cleanly between two runs against the same input. Module layout splits into `backend/yen_gov/preflight/__init__.py` (orchestrator + types) and `predicates.py` (six pure predicates, single source of truth). `backend/yen_gov/validate.py` Tier-B wrappers become thin wrappers calling into `preflight.predicates`; a predicate-parity test asserts the two seams cannot drift.

**Consequences.** Agents now have ONE command to run before any new ingest; no more PR-by-PR discovery of guardrails. Tier-B `tier_b_*` functions in `validate.py` shrink and share a single predicate seam with the pre-flight gate. The handover-doc template ([TODO/_TEMPLATE-ingest-handover.md](../../../TODO/_TEMPLATE-ingest-handover.md)) section 3 now requires citing a `report.json` path; the CI workflow extension fails loud if the report exits with code 2. Adding a 7th check is a single-file edit in `predicates.py` plus a wrapper call in `preflight/__init__.py` (see [Adding a seventh check](#adding-a-seventh-check) above).

> **DOCTRINE NOTE (2026-06-04, plan section 22.7).** ADR-0046's six-check gate survives the data-platform reset verbatim. The checks key on `datasets/taxonomy/concepts.json` + `datasets/taxonomy/indicators.json` + `datasets/data/entities/source.csv` (per the MIGRATING provenance FK target). Plan chunks B2a / X1a do NOT remove the gate; they re-target check #6 (`source_id_derivation`) to the new long-format-CSV provenance file. The `verdict=abort` -> exit code 2 contract and the no-override rule (Holy Law #5) stay binding.

---

## Rejected alternatives

This section preserves the rejected-alternatives receipts from the ADR whose rationale is folded above, verbatim and append-only per [docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md](../../archive/plans/20260604-d-doc3-adr-retire-subplan.md) D-DOC3.8 (2026-06-04). Each subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0046 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **(A) Run the checks at PR-open time via CI only, no agent-facing CLI.** Rejected: agents discover failures post-push, slowing the loop and burning CI minutes. The whole point is to enforce before code is written, not after.
- **(B) Add an `--override` / `--force` flag for "the orchestrator is sure".** Rejected by Hans + Holy Law #5. The six checks are mechanical truths; if a check fails, the proposal is wrong, not the gate.
- **(C) Inline-copy the predicate bodies into `preflight/` instead of `git mv`-style refactor.** Rejected: two seams will drift; the entire point of the predicates module is single-source-of-truth. The parity test makes drift impossible to land silently.
- **(D) Use wall-clock `datetime.now()` for `generated_at`.** Rejected per [CLAUDE.md section 10](../../../CLAUDE.md). The report is a contract output, not a control-plane log line.

---

## See also

- [docs/concepts/pre-flight-ingest.md](../../concepts/pre-flight-ingest.md) — user-facing semantics
- [docs/agents/ingest-checklist.md](../../agents/ingest-checklist.md) — agent checklist
- [ADR-0046](../decisions/0046-pre-flight-ingest-gate-contract.md) — design rationale
- [backend/yen_gov/validate.py](../../../backend/yen_gov/validate.py) — Tier-B wrappers sharing the predicate seam

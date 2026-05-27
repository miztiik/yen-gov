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

## See also

- [docs/concepts/pre-flight-ingest.md](../../concepts/pre-flight-ingest.md) — user-facing semantics
- [docs/agents/ingest-checklist.md](../../agents/ingest-checklist.md) — agent checklist
- [ADR-0046](../decisions/0046-pre-flight-ingest-gate-contract.md) — design rationale
- [backend/yen_gov/validate.py](../../../backend/yen_gov/validate.py) — Tier-B wrappers sharing the predicate seam

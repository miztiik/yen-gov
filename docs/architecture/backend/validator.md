# Validator (`yen_gov.validate`)

**Last Updated**: 2026-05-16

The two-tier validator that enforces CLAUDE.md §11 (schema versioning)
and §12 (provenance) shape across schemas and data files. This doc
explains where each tier runs, why, and what the deliberate descope of
corpus validation from CI is protecting.

## See also

- [CLAUDE.md §11](../../../CLAUDE.md) — schema versioning rules.
- [CLAUDE.md §12](../../../CLAUDE.md) — provenance rules.
- [CLAUDE.md §15](../../../CLAUDE.md) — test coverage policy.
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md)
- Source: [`backend/yen_gov/validate.py`](../../../backend/yen_gov/validate.py)
- CLI entry: [`backend/yen_gov/cli.py`](../../../backend/yen_gov/cli.py) `validate` command

## The two tiers

| Tier | What it asserts | Where it runs | Wall time |
| --- | --- | --- | --- |
| **A — schema sanity** | Every `*.schema.json` validates against the JSON Schema 2020-12 meta-schema; `x-version` is `<major>.<minor>`; `x-changelog` is non-empty and its tail entry's `version` matches `x-version`; malformed JSON is reported, not crashed on. | `pytest -q` in `backend/`, via fixture tests in `tests/test_validate.py` that construct synthetic schemas in `tmp_path`. Always on; runs in CI. | <1s |
| **B — corpus conformance** | Every `*.json` under `datasets/` and `config/` declares `$schema` and `$schema_version`; the schema resolves; `$schema_version` matches the schema's current `x-version`; the file validates against the schema. | `python -m yen_gov validate --root .` invoked locally before committing changes that touch `datasets/**`, `config/**`, or `datasets/schemas/**`. NOT gated in CI. | ~60s (≈5k files) |

## Why Tier B is local-only

The production frontend lives in a separate repository and pulls
`datasets/**` at runtime via `https://raw.githubusercontent.com/...`
URLs. This repo's CI builds a Python package and an admin app; neither
artifact carries the corpus into production. Re-validating every
`datasets/**/*.json` on every PR here would be gating a build that
doesn't consume what's being validated.

The contract that actually matters is **between the corpus on `main`
and the frontend reading it over HTTP at runtime**. That contract is
defended in two places:

1. **Producer side, locally**: the engineer making the change runs
   `python -m yen_gov validate --root .` before pushing. CLAUDE.md §11
   and §15 require this for any commit touching schemas or data.
2. **Consumer side, in the frontend repo**: `frontend/src/contracts/datasets-conform.test.ts`
   validates fetched samples against the schemas at frontend build /
   test time.

Putting a third gate in this repo's CI — walking 4,842 files on every
PR, including PRs that touch only Python source code — was busywork
that delivered no signal a local pre-commit run wouldn't catch first.

## CLI

```powershell
cd backend
python -m yen_gov validate --root .   # full corpus walk
```

Exit 0 = clean. Exit 1 = at least one Tier-A or Tier-B failure;
per-failure line printed as `[tier X] path: message`.

The `--root` option is the only flag. There is no `--path` filter
today; if three concrete callers earn one, add it then.

## Tests

- `backend/tests/test_validate.py` — fixture-based, runs in pytest.
  All cases use `tmp_path` and construct synthetic schemas/data. None
  walk the on-disk corpus.
- The previous `test_repo_passes_validation` (which walked all of
  `datasets/`) and `test_trigger_validate_end_to_end` in
  `test_admin_pipeline.py` (which spawned the walk as a subprocess and
  took 60-180s) were deleted on 2026-05-16. They tested data quality,
  not code correctness, and were the dominant reason devs ran
  `pytest --ignore=tests/test_admin_pipeline.py`.

## Rejected designs

These were considered and explicitly NOT adopted; do not re-propose
without new evidence:

1. **A `.github/workflows/validate-corpus.yml` with workflow-level
   `on.pull_request.paths:` filter on `datasets/**` etc.** Rejected
   because there is no CI consumer in this repo. A PR touching only
   datasets does not produce a build that consumes them; the gate
   belongs at the consumer (frontend repo against raw.githubusercontent
   URLs) or upstream of the push (local pre-commit run).
2. **A `validate --path GLOB` selective CLI.** Premature. Adding a
   knob before three concrete callers ask for it is hardcoding the
   wrong shape. If/when added, the trigger is real call sites, not
   speculation.
3. **A `.pre-commit-config.yaml` hook running the validator.**
   Rejected as ceremony. A 60s pre-commit hook trains engineers to
   `--no-verify`; doctrine that says "run `yen_gov validate` before
   committing data" is a clearer cultural rule than a slow hook devs
   route around.

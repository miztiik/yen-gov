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
- `backend/tests/test_admin_schemas.py` — same pattern, one altitude
  up. Tests the `/api/schemas` FastAPI route by pointing it at a
  `tmp_path` fixture corpus via the `YEN_GOV_REPO_ROOT` env var
  (`monkeypatch.setenv`). Three tests run in ~0.2s. The previous
  version of this file hit the live endpoint, which walked the real
  `datasets/**` corpus inside the route handler — 22s per test, 66s
  total. The endpoint's behaviour was reasserting Tier-B conformance
  on the real repo in HTTP disguise.
- The previous `test_repo_passes_validation` (which walked all of
  `datasets/`), `test_trigger_validate_end_to_end` in
  `test_admin_pipeline.py` (which spawned the walk as a subprocess and
  took 60-180s), and `test_repo_schemas_are_clean` in
  `test_admin_schemas.py` (which asserted the live endpoint reported
  zero corpus failures against the real repo) were all deleted on
  2026-05-16 / 2026-05-17. They tested data quality, not code
  correctness, and were the dominant reason devs ran
  `pytest --ignore=...`. Combined wall-clock savings: ~150s per
  `pytest -q`.

## Pattern: env-var injection for "endpoint walks the corpus"

Any FastAPI route, CLI, or tool that defaults to the real repo root
MUST take that root via an injectable parameter, not a module-level
constant. The shape used here is:

```python
# backend/yen_gov/admin/schemas.py
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]

def _repo_root() -> Path:
    override = os.environ.get("YEN_GOV_REPO_ROOT")
    return Path(override) if override else _DEFAULT_REPO_ROOT
```

Tests then `monkeypatch.setenv("YEN_GOV_REPO_ROOT", str(tmp_path))`
and build whatever minimal corpus the test needs. Production
behaviour is unchanged (env var is absent). The handler reads the root
exactly once per request and threads it through.

Symptoms that this pattern is missing:

- A single pytest test takes >5s and most of that is walking
  `datasets/**`.
- The fix for a "test failed" report is "add the missing file" or
  "regenerate the artifact", not "change the code".
- The test starts failing on a teammate's machine after they pull a
  corpus-only PR.

When you see those, refactor to inject the root before extending the
test.

## Frontend repo split: where the consumer-side test goes

`frontend/src/contracts/datasets-conform.test.ts` is the consumer-side
counterpart to backend Tier-B — it walks every `datasets/**/*.json`
and validates against the declared `$schema`. Today it lives in this
repo because the frontend is still co-located; per the deployment
doctrine the frontend will move to a separate repo and pull
`datasets/**` at runtime from `raw.githubusercontent`.

When that split happens:

1. `datasets-conform.test.ts` moves with the frontend, NOT with the
   backend. It is the frontend's bet that the data it fetches over
   HTTP conforms to the schemas it codes against.
2. The backend repo's vitest suite goes away entirely.
3. The "no test walks the real corpus" rule generalises from "no
   pytest test" to "no test in the backend repo, period, regardless
   of language". The producer-side gate stays local
   (`python -m yen_gov validate --root .` before commit) and the
   consumer-side gate stays in the frontend repo.

Until the split: this test stays here, but it follows the same
collect-vs-test discipline as everything else — file enumeration is
cheap (glob only), JSON.parse runs inside each `it()` so the cost
parallelises across vitest workers rather than blocking the collect
phase.

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

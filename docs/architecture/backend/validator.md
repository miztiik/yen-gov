# Validator (`yen_gov.validate`)

**Last Updated**: 2026-05-30

The two-tier validator that enforces CLAUDE.md §11 (schema versioning)
and §12 (provenance) shape across schemas and data files. This doc
explains where each tier runs, why, and what the deliberate descope of
corpus validation from CI is protecting.

## See also

- [CLAUDE.md §11](../../../CLAUDE.md) — schema versioning rules.
- [CLAUDE.md §12](../../../CLAUDE.md) — provenance rules.
- [CLAUDE.md §15](../../../CLAUDE.md) — test coverage policy.
- [ADR-0047](../decisions/0047-schema-version-compatibility-contract.md) - writer-strict / reader-compatible schema policy.
- [docs/architecture/data/schema-evolution.md](../data/schema-evolution.md)
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md)
- Source: [`backend/yen_gov/validate.py`](../../../backend/yen_gov/validate.py)
- CLI entry: [`backend/yen_gov/cli.py`](../../../backend/yen_gov/cli.py) `validate` command

## The two tiers

| Tier | What it asserts | Where it runs | Wall time |
| --- | --- | --- | --- |
| **A — schema sanity** | Every `*.schema.json` validates against the JSON Schema 2020-12 meta-schema; `x-version` is `<major>.<minor>`; `x-changelog` is non-empty and its tail entry's `version` matches `x-version`; malformed JSON is reported, not crashed on. | `pytest -q` in `backend/`, via fixture tests in `tests/test_validate.py` that construct synthetic schemas in `tmp_path`. Always on; runs in CI. | <1s |
| **B - corpus conformance** | Every `*.json` under `datasets/` and `config/` declares `$schema` and `$schema_version`; the schema resolves; the declared version is accepted by the active compatibility contract; the file validates against the schema the reader is allowed to use. Row E consumes `datasets/schema-compatibility.json` for the `json-corpus` surface; accepted old minors still validate against the current schema until Row H lands retained historical schemas. | `python -m yen_gov validate --root .` invoked locally before committing changes that touch `datasets/**`, `config/**`, or `datasets/schemas/**`. NOT gated in CI. | ~60s (~5k files) |

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

## Schema-version compatibility

Tier B is the corpus-side reader contract. Per [ADR-0047](../decisions/0047-schema-version-compatibility-contract.md), writers stay strict while readers may become compatible by explicit contract.

The explicit contract lives at `datasets/schema-compatibility.json`, validated by `datasets/schemas/schema-compatibility.schema.json`. Row E of [TODO/20260530-schema-version-compatibility-plan.md](../../../TODO/20260530-schema-version-compatibility-plan.md) makes Tier B consume that registry for the `json-corpus` surface. The default remains current-schema only, but an override can accept an older same-major changelog version when `validation` is `current_schema` and the artifact still validates against the current schema.

Declared-version schema resolution waits for Row H. Until retained historical schemas or translators exist, accepted old JSON versions are additive minors only; unsupported future versions and old majors still fail loud.

Tier B still fails for:

- Unknown schema ids.
- Unsupported future versions.
- Unsupported major versions.
- Declared versions whose artifact shape is invalid for the allowed schema path.
- Old versions that require a retained historical schema or translator that does not exist.

Tier B must not accept an artifact by guessing defaults for missing historical fields.

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

## Subtree exemptions (`_EXCLUDED_PATH_SEGMENTS`)

Some subtrees under `DATA_ROOTS` are exempt from Tier-B conformance
because they are not contract surfaces. Exemption is a doctrine
decision; the exempt set is small, hand-curated, and a literal
basename match (not a glob / prefix / leading-underscore heuristic).
Stray underscore-prefixed dirs (e.g. an accidental `_scratch/`) MUST
still fail Tier B loudly — per Fowler review 2026-05-17.

Currently exempt:

| Segment | Why exempt |
| --- | --- |
| `ephemeral` | Operator scratch directory (`datasets/ephemeral/...`). Whole subtree is gitignored (`.gitignore = *`); same rationale as `.runtime/` per CLAUDE.md §2. Holds raw XLSX/PDF dumps, restored legacy-corpus snapshots, and operator inventory sidecars (e.g. `_ingest_inventory.json`) that are NOT contract surfaces. Added 2026-05-20 — `python -m yen_gov validate` was reporting `datasets/ephemeral/_ingest_inventory.json: missing or empty '$schema' field` for a gitignored operator sidecar, which is the validator-tests-DATA-not-CODE smell from the 2026-05-16 descope lesson one layer up: pytest-tier-A doesn't walk it, but Tier-B was. |

Historical note: `_test` was previously exempt as a cross-language
test-fixture subtree (`datasets/_test/temporal-range-fixtures/cases.json`).
T.1 (TODO/20260517 §0e.7) deleted that subtree — shared cross-language
fixtures now live under `backend/tests/fixtures/` (Python-owned, single
source of truth) pointed at by both pytest (`backend/tests/test_derive_temporal_range.py`)
and vitest (`frontend/src/lib/indicators.test.ts`). `_ops/` is NOT in the
exempt set: JSON under `_ops/` MUST carry `$schema` like any other contract
surface (current contents are non-JSON Parquet).

To add a new exemption:

1. Open a Plan-tier discussion: why is this subtree not a contract
   surface? What gitignore / lifecycle / consumer story justifies
   skipping it?
2. Add the literal basename to `_EXCLUDED_PATH_SEGMENTS` in
   `backend/yen_gov/validate.py` (NOT a glob, NOT a prefix — literal
   `parts` match).
3. Add a fixture test in `backend/tests/test_validate.py` mirroring
   `test_tier_b_skips_ephemeral_subtree` that constructs a fake
   subtree under `tmp_path` and asserts no failures reference it.
4. Update this table in the same commit.

Do NOT exempt subtrees that contain published artifacts the frontend
consumes at runtime. That's the consumer-side contract; skipping it
here is silently breaking the bet from "Frontend repo split: where the
consumer-side test goes" above.

## Forbidden-path checks

Beyond per-file schema conformance, Tier-B carries a small registry of
**forbidden-path** checks that enforce CLAUDE.md §10 anti-patterns
computationally rather than purely textually. Each check is a stand-alone
function in `backend/yen_gov/validate.py` chained into `run()`; tests live
in `backend/tests/test_validate.py` and use `tmp_path` fixtures (no real
corpus walks per CLAUDE.md §10 anti-pattern).

| Function | What it forbids | Allowlist input | Tests |
| --- | --- | --- | --- |
| `tier_b_meadow_shard_contract` | New `*.json` files under `datasets/indicators/in/`. The 110 legacy folded-indicator shards (pre-canonical-pivot artifacts) retire family-by-family per TODO/20260517 §0e.7 P.*. New content must land on the canonical Parquet store. | `datasets/_ops/meadow-shard-contract.txt` (one POSIX path per line; `#`-comments + blank lines ignored). | 6 cases — passes when allowlisted, rejects new shard, rejects orphan allowlist entry, no-op when indicators dir absent, requires allowlist when indicators dir present, regression guard that `run()` chains the check. |

### Shape of a forbidden-path check

Each check is a `def tier_b_<name>(root: Path) -> list[Failure]:` function
that takes a repo root and returns a list of `Failure` records. The check
is responsible for:

1. **No-op gating** — if the forbidden subtree is gone (final retirement
   PR has shipped), the check returns `[]` without requiring the allowlist.
   This is the retirement contract: the directory, the allowlist, and the
   check all disappear together; the check must not fail mid-retirement.
2. **Allowlist-present sanity** — if the forbidden subtree exists but the
   allowlist file is missing, fail loudly. Prevents silent passes from
   accidental allowlist deletion.
3. **Two symmetric failure modes** — files on disk not in allowlist
   ("forbidden new …"), and allowlist entries with no on-disk file
   ("orphan allowlist entry …"). Both surface so the allowlist stays in
   sync with reality.
4. **Plain-text allowlist** — `.txt` format under `datasets/_ops/` (per
   the operator-state directory's purpose per CLAUDE.md §3). JSON
   allowlists would themselves require `$schema` under §11, adding
   ceremony with no upside. `#`-comments and blank lines supported.

### Why allowlists live under `datasets/_ops/`

`datasets/_ops/` is the operator-state directory per CLAUDE.md §3 — it
holds operational assets that are committed (vs `.runtime/`'s ephemeral
gitignored state) but are NOT citizen-facing fact tables. A forbidden-path
allowlist is exactly this shape: it documents WHICH files are permitted
to exist under a forbidden subtree pending family-by-family retirement.
Operators editing a P.* family retirement PR amend the allowlist as part
of the same change. When the allowlist becomes empty AND the forbidden
subtree is empty, the allowlist file deletes alongside the legacy code.

Alternative homes considered and rejected:

1. **Constants in `validate.py`** — violates CLAUDE.md §6 (hardcoding
   taxonomy). The allowlist is reference data, not validator logic.
2. **`datasets/indicators/in/.allowlist`** — co-located but hidden-file
   pattern is discoverable only via `ls -la`; doesn't fit the established
   `_ops/` pattern; would need a per-forbidden-subtree dot-file rather
   than one canonical home.
3. **JSON allowlist with `$schema`** — heavier than the use case warrants.
   Plain text is grep-able, diff-friendly, and one-`Set.add`-per-line to
   parse. Schema overhead has no downstream consumer.

### Adding a new forbidden-path check

1. Add a sorted plain-text allowlist under `datasets/_ops/` (e.g.
   `datasets/_ops/<name>-allowlist.txt`).
2. Add the path constants near the top of `backend/yen_gov/validate.py`
   alongside `LEGACY_INDICATOR_SHARDS_*` (one DIR constant, one ALLOWLIST
   constant).
3. Add a `tier_b_<name>(root: Path) -> list[Failure]` function modelled
   on `tier_b_meadow_shard_contract` (see "Shape of a
   forbidden-path check" above).
4. Chain the function into `run()`.
5. Mirror the six Tier-A test cases in `backend/tests/test_validate.py`,
   reusing the `_seed_indicator_tree` helper as a template (parameterise
   on dir + allowlist constants).
6. Add a row to the table at the top of this section.
7. Add an entry to `datasets/_ops/README.md`.
8. Add an "Enforced by Tier-B" sentence to the matching CLAUDE.md §10
   anti-pattern entry.
9. Add a row to the table in
   [docs/architecture/canonical-pivot-deletion-manifest.md §6d](../canonical-pivot-deletion-manifest.md).

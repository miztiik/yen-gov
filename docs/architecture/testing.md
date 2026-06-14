# Test Coverage Policy

**Last Updated**: 2026-06-14

> This is the canonical home for yen-gov's test-tier policy. [CLAUDE.md §15](../../CLAUDE.md) carries a one-paragraph summary and links here. The non-negotiable rules (mock carve-outs, no-corpus-walk, red-suite-blocks-commit) remain in CLAUDE.md because they are contract-grade; the matrix, command snippets, and fixture conventions live here.

Every feature lands with tests at the tier(s) appropriate to its surface. Coverage is split into four tiers; missing the tier that matches your change is a Definition-of-Done failure ([CLAUDE.md §9](../../CLAUDE.md)).

## Tier names

The four tiers are named by purpose: **Unit**, **Contract**, **Integration**, **End-to-end**. They are **not numbered**.

Older docs and ADRs occasionally use aliases like "Tier-A test" ([routing.md](frontend/routing.md), [ADR-0028](../reference/decision-index.md), [data-loading.md](frontend/data-loading.md)) or "Tier 2 contract test" ([catalogue-drift-detector.md](frontend/catalogue-drift-detector.md), [stacked-trend.md](frontend/charts/stacked-trend.md)). Those aliases are **deprecated** for two reasons:

1. The lettered/numbered schemes drifted across files without a canonical mapping.
2. "Tier A" / "Tier B" collide with the **validator-internal** taxonomy in [CLAUDE.md §11](../../CLAUDE.md) (Tier A = schema sanity, Tier B = corpus conformance) and [docs/architecture/backend/validator.md](backend/validator.md). That is a different taxonomy entirely — it describes validation phases, not test scopes.

When you encounter a deprecated alias in an existing doc: treat "Tier-A" as "Unit or Contract" (best-guess), treat "Tier 2" as "Contract", and rename to the word-named tier when you next edit that file. Do not block on a rename PR by itself.

## The matrix

| Tier | Where it lives | What it asserts | When it's required |
| --- | --- | --- | --- |
| **Unit** | [`frontend/src/**/*.test.ts`](../../frontend/src) (vitest), [`backend/tests/test_*.py`](../../backend/tests) (pytest) | Pure functions, formatters, parsers, slug round-trips, math invariants. No I/O, no DOM, no network. | Any change to a pure function or pure module. |
| **Contract** | [`frontend/src/contracts/*.test.ts`](../../frontend/src/contracts) (ajv against [`datasets/schemas/`](../../datasets/schemas)), [`backend/tests/test_validate.py`](../../backend/tests/test_validate.py), [`backend/tests/test_datasets_integrity.py`](../../backend/tests/test_datasets_integrity.py) | Frontend contract tests prove consumer behavior with fixtures and representative canaries. Backend validator fixture tests prove Tier-A/Tier-B rules without walking the real corpus. Exhaustive JSON and boundary corpus validation lives in `python -m yen_gov validate --root .`; `$schema_version` is current for writer outputs or accepted by the explicit compatibility contract ([CLAUDE.md section 11](../../CLAUDE.md), [ADR-0047](../reference/decision-index.md)); provenance shape ([CLAUDE.md section 12](../../CLAUDE.md)); cross-registry consistency (frontend catalogue to backend `events.py`, tier partition, allowlisted countermands, no-folded-sidecar regression). | Any schema bump, new emitted artifact, new boundary geometry, or new loader - producer AND consumer side. |
| **Integration** | [`frontend/src/**/*.test.ts`](../../frontend/src) for loader+fixture composition; [`backend/tests/test_pipeline_*.py`](../../backend/tests) for adapter+pipeline composition. | Loaders compose paths correctly, mocked `fetch` returns the expected shape, the 404-as-null and other graceful-degradation contracts hold; pipeline adapters compose end-to-end against fixture pages. | Any new loader, adapter, or composed pipeline step. |
| **End-to-end** | [`frontend/e2e/*.spec.ts`](../../frontend/e2e) (Playwright, public citizen site on port 5173); [`admin/e2e/*.spec.ts`](../../admin/e2e) (Playwright, admin operator console on port 5174, mocks `/api/*` via `page.route`). | Citizen-visible route loads without `pageerror`; one DOM assertion that proves the route's content is there; one `SourceList` provenance assertion if the route surfaces data. Admin panels render and exercise their typed API contract via mocked routes. | Any new citizen-visible route or meaningful change to an existing one; any admin panel addition. |

## Repo-integrity tests are Contract, not End-to-end

[`backend/tests/test_datasets_integrity.py`](../../backend/tests/test_datasets_integrity.py) lives in the **Contract** row above, not End-to-end. Its tests are targeted cross-registry drift checks (frontend catalogue ↔ backend `events.py`, tier partition vs `states.json`, allowlisted missing-AC set, no `.notes.json` sidecars after the folded-indicator migration) that defend **named runtime contracts** — NOT a full-corpus schema walk ([CLAUDE.md §10](../../CLAUDE.md) forbids that).

A new integrity test needs to name the contract it defends. If the answer is "every JSON file under `datasets/**` is well-formed", that is Tier-B corpus conformance and belongs in `python -m yen_gov validate --root .`, not pytest. See [docs/architecture/backend/validator.md](backend/validator.md) for the Tier-A/B split.

## Non-negotiables

- A change that touches [`frontend/src/lib/**`](../../frontend/src/lib) MUST have a corresponding `*.test.ts` covering the new or changed behaviour, in the same commit.
- A new `datasets/**/*.json` artifact (or a schema bump) MUST be validated locally by `python -m yen_gov validate --root .` before commit. If it adds a new frontend-visible artifact class, update the bounded canary list in [`frontend/src/contracts/datasets-conform.test.ts`](../../frontend/src/contracts/datasets-conform.test.ts) only when the existing canaries do not cover the reader risk. Both sides validate their tier: producer exhaustiveness in Tier-B, consumer wiring in fixed frontend canaries. Writers emit the current schema version; readers accept older versions only through the compatibility contract.
- A change to `datasets/schema-compatibility.json` or `datasets/schemas/schema-compatibility.schema.json` MUST keep both backend and frontend contract tests green (`backend/tests/test_schema_compatibility_registry.py` and `frontend/src/contracts/schema-compatibility.test.ts`). Runtime behavior changes still belong in the later reader rows that consume the registry.
- A new citizen-visible route or a meaningful change to an existing one MUST extend [`frontend/e2e/golden-path.spec.ts`](../../frontend/e2e/golden-path.spec.ts) (or add a sibling spec) with at least: route loads, no `pageerror`, one DOM assertion that proves the new content is there, one provenance (`SourceList`) assertion if the route surfaces data.
- Mocks remain forbidden ([Holy Law #7](../../CLAUDE.md)) except: (a) `fetch` in unit tests of loaders — the loader's contract IS the fetch boundary, so mocking it is testing the contract; (b) explicit user request.
- **No pytest test walks the real on-disk corpus.** Any test that opens files under `datasets/**` or `config/**` of the real repo (directly, via a CLI subprocess, or via an HTTP route that itself walks) is Tier-B conformance smuggled into Tier A — see [CLAUDE.md §10](../../CLAUDE.md). Use a `tmp_path` fixture corpus and inject the root through an env var (e.g. `YEN_GOV_REPO_ROOT`). Red flag for review: any single backend test with a duration > 5 s. Reference fix: commit `7d407d0` ([`admin/schemas.py`](../../backend/yen_gov/admin/schemas.py) + [`test_admin_schemas.py`](../../backend/tests/test_admin_schemas.py)).
- **No default frontend test scales with corpus cardinality.** No default frontend Vitest may create one test per dataset file, shard, row, district, village, ward, panchayat, constituency, party, indicator, path, or schema artifact. Frontend tests prove consumer behavior with fixtures and representative canaries. Exhaustive corpus validation belongs to producer receipts plus backend Tier-B validation. Review smell: broad `globSync`, recursive `readdirSync`, or loops over `datasets/**` that generate test cases, unless bounded by a small explicit canary list.
- A red test at commit time blocks the commit. "Skip this for now" is a structural-fix request ([§5](../../CLAUDE.md)), not a casual override.

## Schema Versions In Tests

This section governs how tests assert schema-version behavior. It does not define reader compatibility, retained historical schemas, migration policy, or which old artifact versions validators may accept. Those choices belong to [ADR-0047](../reference/decision-index.md), [data/schema-evolution.md](data/schema-evolution.md), and the active schema-compatibility plan rows.

Tests MUST NOT assert a production schema's current version as a hand-typed point value when the behavior under test is "whatever the current writer emits today".

Prefer relationship assertions:

- Emitted `$schema_version` equals the schema file's `x-version`.
- A schema changelog tail entry's `version` equals `x-version`.
- Backend code/tests use `yen_gov.core.schema_registry.schema_version("<file>")` or `schema_id("<file>")` where backend imports are legal.
- `tools/` helpers read the relevant schema JSON directly, or use a tools-local helper with a drift test. `tools/` MUST NOT import backend runtime modules.
- Frontend current-emission tests use one named frontend policy/helper and a drift test against the schema JSON. A reader compatibility allowlist is a separate contract.

Forbidden shape when the literal means "current":

```python
assert schema["x-version"] == "6.0"
assert payload["$schema_version"] == "6.0"
assert schema["x-changelog"][-1]["date"] == "2026-05-26"
```

Replacement shape:

```python
from yen_gov.core.schema_registry import schema_version

assert payload["$schema_version"] == schema_version("indicator.schema.json")
assert schema["x-changelog"][-1]["version"] == schema["x-version"]
```

Explicit version literals are allowed only when the literal is part of the behavior under test: migration fixtures, historical/backcompat cases, intentionally bad versions, changelog-entry history, or synthetic fixtures disconnected from production current schemas. The test name or nearby prose must make that purpose clear.

This rule does not cover source vintage dates, methodology dates, business fixture dates, API mock versions, row-count sentinels, or schema changelog history inside `datasets/schemas/**`. Those may have their own review smell, but they are not current-schema-version pins.

## Runtime fragility — known issues (do NOT "fix" the tests)

Some tests fail not because the test code or production code is wrong, but because the **runtime stack** (a specific OS × Python × DuckDB combination) has a known crash. The tests are CORRECT. Deleting or weakening them would be a band-aid forbidden by [Holy Law #5](../../CLAUDE.md). The correct response is to **deselect at the runner boundary** and document the deselect here.

### DuckDB on Windows + Python 3.14 — empty-Parquet segfault

First observed: 2026-05-25 (boundary-coverage sprint, PR #259 follow-up smoke). Symptom: backend pytest crashes the Python interpreter (Windows access violation, no Python traceback, exit code 0xC0000005) inside three specific tests that read or write a zero-row Parquet via DuckDB. Root cause sits inside DuckDB's empty-batch handling on Windows under Python 3.14's new ABI; reproducible only on the Windows × Python 3.14 × DuckDB 1.1.x intersection. Linux + macOS + Python 3.12/3.13 are unaffected.

**Standing deselect line** (copy verbatim into every backend pytest invocation on Windows + Python 3.14):

```powershell
pytest -q `
  --deselect=backend/tests/test_canonical_writer.py::test_empty_dim_lists_do_not_touch_existing_dim_files `
  --deselect=backend/tests/test_topics_seed.py::test_compile_accepts_topic_without_artifacts `
  --deselect=backend/tests/test_canonical_writer_partition.py::test_pre_existing_monolith_swept_after_partitioned_emit
```

Expected baseline (2026-05-25): **998 passed / 44 skipped / 3 deselected**.

The three deselected tests each defend a real invariant; they MUST stay in the suite:

| Test | Invariant it defends |
| --- | --- |
| `test_canonical_writer.py::test_empty_dim_lists_do_not_touch_existing_dim_files` | A partial ingest (e.g. only observations, no dim updates) MUST NOT clobber existing dim Parquets. Prevents a dim-corruption regression class. |
| `test_topics_seed.py::test_compile_accepts_topic_without_artifacts` | A topic in `topics.json` with zero indicator entries MUST still compile to the taxonomy Parquet. Prevents a placeholder-topic schema regression that would block T.2-style structural-slot PRs. |
| `test_canonical_writer_partition.py::test_pre_existing_monolith_swept_after_partitioned_emit` | When emitting partitioned Parquet over a pre-existing monolith, the monolith MUST be swept. Prevents the dual-source-of-truth class. |

**What NOT to do**:

- **Do not delete or `@skip` the tests.** They run green on Linux CI today and protect real invariants.
- **Do not "fix" them with workaround code** (e.g. wrapping every DuckDB read in a try/except). That is a band-aid for a runtime crash, in production code that has no runtime bug.
- **Do not block a PR on these three tests.** The deselect line above is the standing operating procedure.

**Reversal triggers** (re-run without the deselect on each):

- Any DuckDB release ≥ 1.2.0.
- Any Python 3.14 patch release.
- Any pyduckdb wheel rebuild on Windows.

If the green count returns to 1001 passed / 44 skipped / 0 deselected, drop the deselect line in the same PR that observed the fix.

**Escalation if upstream stalls > 3 months**: convert the deselect-at-runner-boundary into structural skipif decorators in the same commit:

```python
import sys
import pytest

@pytest.mark.skipif(
    sys.platform == "win32" and sys.version_info[:2] >= (3, 14),
    reason="DuckDB empty-Parquet segfault on Windows + Python 3.14; see docs/architecture/testing.md",
)
def test_empty_dim_lists_do_not_touch_existing_dim_files(...):
    ...
```

Structural skipif self-heals (the gate evaporates when CI moves to Python 3.15) and stops every agent from having to re-paste the deselect line.

Doctrine summary: **tests are correct; runtime is fragile; deletion is band-aid; deselect is structural; document here so agents don't re-litigate.**

## Running the suites

### Frontend (Vitest + Playwright)

From [`frontend/`](../../frontend):

```sh
npm test                 # vitest: unit + contract + integration
npm test -- foo          # vitest, filtered by name
npm run test:e2e         # Playwright, citizen e2e against port 5173
```

`bun run test` / `bun run test:e2e` also work — bun reads `package.json` scripts.

### Admin (Vitest + Playwright)

From [`admin/`](../../admin):

```sh
npm test                 # vitest
npm run test:e2e         # Playwright, admin e2e against port 5174 (mocks /api/*)
```

### Backend (pytest)

From [`backend/`](../../backend):

```sh
pytest -q                                        # full suite
pytest -q tests/test_validate.py                 # only validator fixtures
pytest -q -k canonical                           # only canonical-pivot tests
pytest -q --durations=10                         # surface slow tests (>5 s = red flag, see above)
```

### Local Tier-B corpus check (validator)

From the repo root:

```sh
python -m yen_gov validate --root .
```

Not gated in CI ([CLAUDE.md §11](../../CLAUDE.md)). Run before committing changes to [`datasets/**`](../../datasets), [`config/**`](../../config), or [`datasets/schemas/**`](../../datasets/schemas). The publish workflow ([`deploy-site.yml`](../../.github/workflows/deploy-site.yml)) copies `datasets/` into `_site/data/` as static bytes and never re-validates them; the runtime-shape gate is the consumer-side ajv contract test ([`datasets-conform.test.ts`](../../frontend/src/contracts/datasets-conform.test.ts)).

As of 2026-06-14, this same Tier-B command also owns exhaustive boundary
geometry corpus checks for known Hive path shape, TopoJSON sibling pairs,
and TopoJSON/GeoJSON feature-count parity. Frontend boundary tests keep
only bounded canaries.

### Boundary gzip budget check

Boundary GeoJSON byte budgets are data-pipeline validation, not everyday frontend contract tests. The frontend suite keeps cheap consumer canaries (Hive path shape, no legacy sidecars, ledger presence, join-key shape, bounded TopoJSON decode); it does not gzip every shipped boundary shard or validate every sibling pair on every vitest run. Exhaustive shape/sibling/feature-count checks live in backend Tier-B.

Run the full boundary size check from the repo root whenever a PR changes `datasets/boundaries/in/**`, `datasets/boundaries/boundary_layers.parquet`, or `tools/boundaries/simplify.py`:

```sh
python tools/boundaries/simplify.py --dry-run --skip-parquet
```

This command reads `tools/boundaries/simplify.py:LAYER_TUNING`, reports every shard sorted by gzipped size, and exits non-zero if any file exceeds its configured ceiling. If a shard fails, either re-run simplification as a data PR or document and implement a finer partition strategy; do not silently raise the ceiling from a frontend test.

## e2e scope and canary subset

End-to-end (Playwright) coverage is the most expensive tier. It must stay scoped to representative citizen journeys; cheaper tiers own exhaustive coverage. The runtime trim landed in PRs #520, #521, #522 and codified four rules:

- **Cheap tiers own exhaustive coverage.** If a fact can be proven by reading on-disk files + a TS module (registry symmetry, shard presence, slug round-trips, humanised label maps, temporal-caption vocabulary), it belongs in vitest / contract / pytest. Re-asserting in e2e doubles CI time for zero incremental citizen-invariant proof. When you delete an e2e assertion, the equivalent must already exist in a cheaper tier (or land in the same commit).
- **Per-entity matrices ship as canary + opt-in full.** A spec that iterates every state/district/UT on every PR is appropriate only as a one-time migration receipt, not as a standing PR gate. The standing shape: a 5-code canary covering each distinct risk on every PR, with the full matrix env-gated (`AC_COVERAGE_FULL=1`) and triggered nightly + on path-filtered PRs that touch the files the canary cannot protect (registry source, on-disk shards, taxonomy, the contract test, the spec itself). Reference: [frontend/e2e/state-ac-coverage.spec.ts](../../frontend/e2e/state-ac-coverage.spec.ts) + [.github/workflows/e2e-ac-full.yml](../../.github/workflows/e2e-ac-full.yml).
- **`mobile-pixel-5` runs only where a breakpoint-specific code path exists.** The default is desktop-chromium. Mobile only runs specs whose production code branches on `lg:` / `md:` / mobile-specific viewport (today: `golden-path.spec.ts`, `extended-routes.spec.ts`, `indicator-ranked-polish.spec.ts`). Doubling CI minutes to retest identical desktop/mobile code paths is waste. Configured via per-project `testMatch` in [frontend/playwright.config.ts](../../frontend/playwright.config.ts).
- **Performance benchmarks ship behind `@bench`.** CDP-throttled benchmarks (currently `boundary-benchmark.spec.ts`) are excluded by default via `grepInvert: /@bench/`. Run on demand via `PLAYWRIGHT_GREP=@bench bunx playwright test ...`. They are not citizen invariants and should not gate PRs.

Playwright runs `fullyParallel: true` with `workers: process.env.CI ? 2 : 4`. Add new specs assuming parallel execution; do not introduce shared on-disk state without an explicit `@bench`-style exclusion or test-context scoping.

## Fixture conventions

- **`tmp_path`** for any test that needs a filesystem corpus. Per [CLAUDE.md §10](../../CLAUDE.md) and [docs/architecture/backend/validator.md](backend/validator.md), pytest tests MUST NOT walk the real `datasets/**`.
- **Inject the corpus root via env var** (e.g. `YEN_GOV_REPO_ROOT`); in tests use `monkeypatch.setenv(...)` to point at a `tmp_path` fixture corpus. The runtime default reads the real repo. Reference fix: commit `7d407d0`.
- **`openpyxl.Workbook` in-memory** for any backend XLSX adapter (RBI, CEA, etc.). No captured `.xlsx` binary fixtures unless the adapter exists specifically to test binary parsing edge cases. See [sources-rbi-appendix-deficits.md](backend/sources-rbi-appendix-deficits.md) and [sources-rbi-hbs-ie-centre-deficits.md](backend/sources-rbi-hbs-ie-centre-deficits.md) for the pattern.
- **Mocked `fetch`** in vitest loader tests — the loader's contract IS the fetch boundary. See [data-loading.md](frontend/data-loading.md) for the DuckDB-WASM-aware variant of this pattern.

## New tiers

Component, mobile, and visual-regression tiers are tracked under [CLAUDE.md §14](../../CLAUDE.md) Open Questions until they ship. Each gets a row in the matrix above once it lands.

Accessibility is a project-level non-goal per [CLAUDE.md §0](../../CLAUDE.md) and is intentionally absent from this matrix. Do not add ARIA / WCAG / axe-core rows.

## See also

- [CLAUDE.md §9](../../CLAUDE.md) — Definition of Done (which tier(s) MUST land with a change)
- [CLAUDE.md §10](../../CLAUDE.md) — no-corpus-walk anti-pattern (the doctrine line that protects this policy)
- [CLAUDE.md §11](../../CLAUDE.md) — schema versioning and the **validator-internal** Tier A/B split (do not confuse with the test tiers above)
- [docs/architecture/backend/validator.md](backend/validator.md) — validator design and Tier A/B descope rationale
- [docs/architecture/data/schema-evolution.md](data/schema-evolution.md) - schema-version compatibility testing policy
- [ADR-0047](../reference/decision-index.md) - writer-strict / reader-compatible decision
- [docs/concepts/data-provenance.md](../concepts/data-provenance.md) — provenance shape that contract tests assert against

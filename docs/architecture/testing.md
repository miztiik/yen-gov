# Test Coverage Policy

**Last Updated**: 2026-05-18

> This is the canonical home for yen-gov's test-tier policy. [CLAUDE.md §15](../../CLAUDE.md) carries a one-paragraph summary and links here. The non-negotiable rules (mock carve-outs, no-corpus-walk, red-suite-blocks-commit) remain in CLAUDE.md because they are contract-grade; the matrix, command snippets, and fixture conventions live here.

Every feature lands with tests at the tier(s) appropriate to its surface. Coverage is split into four tiers; missing the tier that matches your change is a Definition-of-Done failure ([CLAUDE.md §9](../../CLAUDE.md)).

## Tier names

The four tiers are named by purpose: **Unit**, **Contract**, **Integration**, **End-to-end**. They are **not numbered**.

Older docs and ADRs occasionally use aliases like "Tier-A test" ([routing.md](frontend/routing.md), [ADR-0028](decisions/0028-url-scheme-place-first-flat-indicator-slug.md), [data-loading.md](frontend/data-loading.md)) or "Tier 2 contract test" ([catalogue-drift-detector.md](frontend/catalogue-drift-detector.md), [stacked-trend.md](frontend/charts/stacked-trend.md)). Those aliases are **deprecated** for two reasons:

1. The lettered/numbered schemes drifted across files without a canonical mapping.
2. "Tier A" / "Tier B" collide with the **validator-internal** taxonomy in [CLAUDE.md §11](../../CLAUDE.md) (Tier A = schema sanity, Tier B = corpus conformance) and [docs/architecture/backend/validator.md](backend/validator.md). That is a different taxonomy entirely — it describes validation phases, not test scopes.

When you encounter a deprecated alias in an existing doc: treat "Tier-A" as "Unit or Contract" (best-guess), treat "Tier 2" as "Contract", and rename to the word-named tier when you next edit that file. Do not block on a rename PR by itself.

## The matrix

| Tier | Where it lives | What it asserts | When it's required |
| --- | --- | --- | --- |
| **Unit** | [`frontend/src/**/*.test.ts`](../../frontend/src) (vitest), [`backend/tests/test_*.py`](../../backend/tests) (pytest) | Pure functions, formatters, parsers, slug round-trips, math invariants. No I/O, no DOM, no network. | Any change to a pure function or pure module. |
| **Contract** | [`frontend/src/contracts/*.test.ts`](../../frontend/src/contracts) (ajv against [`datasets/schemas/`](../../datasets/schemas)), [`backend/tests/test_validate.py`](../../backend/tests/test_validate.py), [`backend/tests/test_datasets_integrity.py`](../../backend/tests/test_datasets_integrity.py) | Every `datasets/**/*.json` validates against its declared `$schema`; `$schema_version` matches `x-version` ([§11](../../CLAUDE.md)); provenance shape ([§12](../../CLAUDE.md)); cross-registry consistency (frontend catalogue ↔ backend `events.py`, tier partition, allowlisted countermands, no-folded-sidecar regression). | Any schema bump, new emitted artifact, or new loader — producer AND consumer side. |
| **Integration** | [`frontend/src/**/*.test.ts`](../../frontend/src) for loader+fixture composition; [`backend/tests/test_pipeline_*.py`](../../backend/tests) for adapter+pipeline composition. | Loaders compose paths correctly, mocked `fetch` returns the expected shape, the 404-as-null and other graceful-degradation contracts hold; pipeline adapters compose end-to-end against fixture pages. | Any new loader, adapter, or composed pipeline step. |
| **End-to-end** | [`frontend/e2e/*.spec.ts`](../../frontend/e2e) (Playwright, public citizen site on port 5173); [`admin/e2e/*.spec.ts`](../../admin/e2e) (Playwright, admin operator console on port 5174, mocks `/api/*` via `page.route`). | Citizen-visible route loads without `pageerror`; one DOM assertion that proves the route's content is there; one `SourceList` provenance assertion if the route surfaces data. Admin panels render and exercise their typed API contract via mocked routes. | Any new citizen-visible route or meaningful change to an existing one; any admin panel addition. |

## Repo-integrity tests are Contract, not End-to-end

[`backend/tests/test_datasets_integrity.py`](../../backend/tests/test_datasets_integrity.py) lives in the **Contract** row above, not End-to-end. Its tests are targeted cross-registry drift checks (frontend catalogue ↔ backend `events.py`, tier partition vs `states.json`, allowlisted missing-AC set, no `.notes.json` sidecars after the folded-indicator migration) that defend **named runtime contracts** — NOT a full-corpus schema walk ([CLAUDE.md §10](../../CLAUDE.md) forbids that).

A new integrity test needs to name the contract it defends. If the answer is "every JSON file under `datasets/**` is well-formed", that is Tier-B corpus conformance and belongs in `python -m yen_gov validate --root .`, not pytest. See [docs/architecture/backend/validator.md](backend/validator.md) for the Tier-A/B split.

## Non-negotiables

- A change that touches [`frontend/src/lib/**`](../../frontend/src/lib) MUST have a corresponding `*.test.ts` covering the new or changed behaviour, in the same commit.
- A new `datasets/**/*.json` artifact (or a schema bump) MUST be covered by the consumer-side contract test [`frontend/src/contracts/datasets-conform.test.ts`](../../frontend/src/contracts/datasets-conform.test.ts) AND validated locally by `python -m yen_gov validate --root .` before commit. Both sides validate; never just one.
- A new citizen-visible route or a meaningful change to an existing one MUST extend [`frontend/e2e/golden-path.spec.ts`](../../frontend/e2e/golden-path.spec.ts) (or add a sibling spec) with at least: route loads, no `pageerror`, one DOM assertion that proves the new content is there, one provenance (`SourceList`) assertion if the route surfaces data.
- Mocks remain forbidden ([Holy Law #7](../../CLAUDE.md)) except: (a) `fetch` in unit tests of loaders — the loader's contract IS the fetch boundary, so mocking it is testing the contract; (b) explicit user request.
- **No pytest test walks the real on-disk corpus.** Any test that opens files under `datasets/**` or `config/**` of the real repo (directly, via a CLI subprocess, or via an HTTP route that itself walks) is Tier-B conformance smuggled into Tier A — see [CLAUDE.md §10](../../CLAUDE.md). Use a `tmp_path` fixture corpus and inject the root through an env var (e.g. `YEN_GOV_REPO_ROOT`). Red flag for review: any single backend test with a duration > 5 s. Reference fix: commit `7d407d0` ([`admin/schemas.py`](../../backend/yen_gov/admin/schemas.py) + [`test_admin_schemas.py`](../../backend/tests/test_admin_schemas.py)).
- A red test at commit time blocks the commit. "Skip this for now" is a structural-fix request ([§5](../../CLAUDE.md)), not a casual override.

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
- [docs/concepts/data-provenance.md](../concepts/data-provenance.md) — provenance shape that contract tests assert against

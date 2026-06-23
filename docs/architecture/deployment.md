# Deployment

**Last Updated**: 2026-06-23

yen-gov deploys as a single static bundle to GitHub Pages. There is no production backend (CLAUDE.md Holy Law #1). This page is the operator-level overview; the design rationale lives in [frontend/data-loading > production placement](frontend/data-loading.md#production-placement).

## Workflow Contracts

| Workflow | Contract | Trigger | Publishes? |
| -------- | -------- | ------- | ---------- |
| [`deploy-site.yml`](../../.github/workflows/deploy-site.yml) | Public static citizen bundle. On PRs it runs frontend Vitest plus a verification build. On `main` push / manual dispatch it runs the same checks, deploys the artifact, then performs a live CSV smoke check. | every PR + push to main + manual dispatch | Yes - only after green `main` push / manual dispatch. |
| [`post-merge-deploy.yml`](../../.github/workflows/post-merge-deploy.yml) | Bridges the auto-merge deploy gap (below): on a PR that merges into `main` it dispatches `deploy-site.yml` so the publish actually fires. | `pull_request: closed` (acts only when `merged == true` and base is `main`) | Indirectly - it triggers `deploy-site.yml`, which publishes. |
| [`backend.yml`](../../.github/workflows/backend.yml) | Dev/operator tooling: ingest pipeline pytest, admin FastAPI route pytest, admin SPA svelte-check + vitest, and admin Playwright e2e (mocks `/api/*` via `page.route`). | push / PR with `paths:` filter on `backend/**`, `admin/**`, `datasets/**`, the workflow file itself + manual `workflow_dispatch` | No - everything here is dev-only (CLAUDE.md section 3) and never ships in `_site/`. |
| [`indicator-add-gate.yml`](../../.github/workflows/indicator-add-gate.yml) | Governance gate for multi-indicator additions and ingest proposal pre-flight. It reads PR metadata / proposal files; it is not a publish prerequisite. | PRs touching indicator catalogue, ingest proposal, meadow, or related source paths | No. |
| [`e2e-ac-full.yml`](../../.github/workflows/e2e-ac-full.yml) | Sentinel coverage for the full 31-state AC e2e matrix. It catches drift beyond the cheap/default checks and remains outside the Pages deploy path. | nightly schedule + path-filtered PRs + manual dispatch | No. |

The split mirrors the deployment reality: `deploy-site.yml` defends the public artifact; `backend.yml` defends the local dev/operator tooling; `indicator-add-gate.yml` and `e2e-ac-full.yml` defend domain-governance and drift-sentinel concerns. There is intentionally no `workflow_run` chain between these contracts. A red dev/operator or sentinel workflow never blocks a green public bundle from publishing.

### One workflow for the site, not two

The site build IS the verification, and on green main the same artifact is the deploy artifact. There is exactly one `bun run build` per workflow run - no throwaway build separate from the deploy build. Rapid-fire commits to main are batched naturally by `concurrency.cancel-in-progress: true` keyed on the ref: a 5-commit burst queues 5 runs, the in-progress ones get cancelled, only the latest completes and publishes. No cron, no preflight that has to dedupe-by-SHA, no second build at deploy time.

The deploy step itself is one job (`deploy-pages`) gated by `if: (github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main'` and `needs: [frontend-vitest, frontend-build]`. PR runs evaluate that `if` to false and skip the deploy entirely; the gating jobs still run and report status on the PR.

### The auto-merge deploy gap (why `post-merge-deploy.yml` exists)

The "push to main publishes" contract above has a sharp edge. `auto-merge.yml` squash-merges PRs using the default `GITHUB_TOKEN`, and GitHub deliberately does **not** start new workflow runs from a push authored by the `GITHUB_TOKEN` (its recursive-run guard). So an auto-merged PR's push to `main` never fires `deploy-site.yml`'s `push:` trigger, and production silently drifts behind `main` - a whole feature can merge yet never publish (observed 2026-06-23: 17 commits merged, zero deploys; the public site stayed on the previous build for a day). Only a non-`GITHUB_TOKEN` push (a maintainer PAT / direct push) or a manual dispatch deployed.

[`post-merge-deploy.yml`](../../.github/workflows/post-merge-deploy.yml) closes the gap. The `pull_request: closed` webhook **is** delivered for a native auto-merge completion, so it runs post-merge; it then calls `gh workflow run deploy-site.yml --ref main`. `workflow_dispatch` (with `repository_dispatch`) is the one documented exception to the `GITHUB_TOKEN`-no-trigger rule, so the dispatched run *does* start and publishes `main` through the existing, proven deploy path. No PAT or secret is needed - the built-in `GITHUB_TOKEN` with `actions: write` can dispatch a workflow in its own repo. Batching still holds: every dispatched deploy lands in `deploy-site.yml`'s `deploy site-refs/heads/main` concurrency group (`cancel-in-progress: true`), so a burst of merges collapses to a single final publish. To republish without a merge, dispatch `deploy-site.yml` on `main` manually.

### Why backend pytest is not in the publish gate

The deployed bundle is pure static (Svelte build + datasets/ staged under `_site/data/`). No Python ever runs in production. The backend pytest suite covers code that:

- ran *locally* to produce `datasets/**` (by the time CI runs, the data is already committed),
- never executes again until the next local ingest,
- has no presence in the deployed artifact.

Gating publish on it would conflate "my dev tooling is healthy" with "the public site is healthy". They are different concerns. The publish-relevant defences are: (a) do the frontend unit / contract / integration tests pass (`frontend-vitest`), (b) does the bundle build and stage `datasets/` correctly (`frontend-build`), and (c) does the deployed origin serve the expected CSV static bytes (the smoke step in `deploy-pages`). That is what `deploy-site.yml` checks; everything else lives outside the publish path.

### Why admin lives under backend.yml, not its own workflow

The admin operator console is a separate local-only Svelte app on port 5174 (CLAUDE.md section 3, [admin/AGENTS.md](../../admin/AGENTS.md)) and nothing under `admin/` is copied into the deployed Pages bundle. Earlier the admin checks lived in their own workflow (`admin-checks.yml`); they collapsed into `backend.yml` because the unifying axis is "dev-only / never deployed" rather than "admin specifically". The admin console (Svelte SPA) and the admin API (FastAPI shim under `backend/yen_gov/admin/`) are the operator-facing face of the same local pipeline that `pipeline-pytest` already covers. Coupling admin tests to the publish gate would create an inverted incentive: any flake in admin e2e (vite webServer boot race, Playwright timing) indefinitely blocks the public site from updating. The workflow-contract split makes that impossible by construction: `deploy-site.yml` never depends on `backend.yml`.

The `pipeline-pytest` job in `backend.yml` installs only the `[dev]` extra and `--ignore`s the four `test_admin_*.py` files, so a transitive `import fastapi` failure in admin tests cannot accidentally pull admin coverage into the pipeline-pytest job. The matching `admin-api-pytest` job installs `[dev,admin]` and runs only those four files.

`pipeline-pytest` is currently non-blocking inside `backend.yml` while chronic corpus-contract failures are worked down. That is degraded operator-health signal, not a public deploy gate. The desired end state is to make it blocking again inside `backend.yml` once it is green on current `main`.

## Job naming

Workflow job names read top-to-bottom and say what the job actually does, so PR check lists are self-describing without anyone having to open the YAML:

| Workflow | Job id | Display name |
| -------- | ------ | ------------ |
| `deploy-site.yml` | `frontend-vitest` | vitest (frontend unit + contract + integration) |
| `deploy-site.yml` | `frontend-build` | build citizen site (Pages artifact) |
| `deploy-site.yml` | `deploy-pages` | deploy to GitHub Pages |
| `backend.yml` | `pipeline-pytest` | pytest (ingest pipeline, non-admin) |
| `backend.yml` | `admin-api-pytest` | pytest (admin FastAPI routes) |
| `backend.yml` | `admin-console-vitest` | vitest (admin console unit + contract) |
| `backend.yml` | `admin-console-e2e` | Playwright e2e (admin operator console) |
| `indicator-add-gate.yml` | `gate` | indicator-add justification gate |
| `indicator-add-gate.yml` | `preflight` | pre-flight ingest gate (ADR-0046) |
| `e2e-ac-full.yml` | `ac-coverage-full` | Playwright e2e (AC coverage, full 31-state matrix) |

`admin-console-e2e` (in `backend.yml`) covers the dev-only operator console on port 5174. Playwright e2e for the public citizen site is run locally by developers via `bun run test:e2e` in `frontend/`; it is not part of the CI gating chain.

## Branch protection

Branch protection on `main` is not currently configured (verified empty via `gh api repos/miztiik/yen-gov/branches/main/protection` -> 404). For a solo repo at low frequency this is intentional: red tests show up as red checks on the commit but do not block merging. The `deploy-pages` job's own `needs:` chain already prevents a broken bundle from publishing.

If branch protection is ever enabled (multi-author repo, for example), the required status checks should be only the PR-running public-site checks:

- `frontend-vitest`
- `frontend-build`

`deploy-pages` MUST NOT be a required check - it never runs on PRs (its `if` requires push or workflow_dispatch on main), so requiring it would block every merge. Jobs from `backend.yml`, `indicator-add-gate.yml`, and `e2e-ac-full.yml` MUST NOT be globally required either - they are path-filtered, scheduled, manual, or deliberately outside the public deploy contract.

Corpus conformance is the engineer's local pre-emit responsibility (`python -m yen_gov validate --root .`), since this repo's CI has no build that consumes `datasets/**` to defend - see [backend/validator.md](backend/validator.md).

Scraping ECI/Wikipedia and rebuilding boundary geometry are **local-only** operations (CLAUDE.md §1, §13): run `python -m yen_gov run <event> <state>` and the boundary consolidation tools (`tools/topojson/build_country.py`, `tools/boundaries/consolidate_ac_2024.py`) on a maintainer machine, commit the regenerated `datasets/` through a normal PR. Both artifacts change rarely (results don't change post-declaration; boundaries change once per delimitation cycle), so a CI dispatch is unnecessary overhead. The contract between scraping and deploying is the `datasets/` directory committed to main.

## Pages artifact shape

The deploy step assembles (per [frontend/data-loading > production placement](frontend/data-loading.md#production-placement)):

```text
_site/
├── index.html               (from frontend/dist/)
├── assets/...               (from frontend/dist/)
└── data/                    (from datasets/, copied at deploy time)
    ├── data/datapoints/electoral/<slug>_election_results.csv
    ├── data/datapoints/geo/<canonical_id>.csv
    ├── data/entities/...
    └── schemas/...
```

`fetch('/data/<rel>')` resolves the same way in dev (Vite middleware) and prod (this static layout) — see [frontend/data-loading](frontend/data-loading.md). The smoke step in `deploy-site.yml` (the `deploy-pages` job) enforces that contract by fetching `data/data/datapoints/electoral/tamil-nadu_election_results.csv` from the deployed origin and asserting it is non-empty and carries the expected long-format header (`entity_id,year,period_label,...`). Post-X1a-fu2 (2026-06-07) all canonical Parquet has been retired in favour of long-format CSV; TN (S22) is the canonical first-slice state.

## Pages URL base

The bundle is served under a project Pages subpath (`https://miztiik.github.io/yen-gov/`), so both emitted asset URLs (`/yen-gov/assets/...`) and runtime data URLs (`/yen-gov/data/...`) must carry the prefix. The mechanism:

1. The `frontend-build` job in `deploy-site.yml` exports `BASE_URL=/yen-gov/` to the `bun run build` step.
2. [`frontend/vite.config.ts`](../../frontend/vite.config.ts) reads `process.env.BASE_URL` (default `/`) and passes it as Vite's [`base`](https://vitejs.dev/config/shared-options.html#base). Vite then rewrites `<script>`/`<link>` URLs in `index.html` and exposes the value to client code as `import.meta.env.BASE_URL` (always trailing-slashed).
3. [`frontend/src/lib/paths.ts`](../../frontend/src/lib/paths.ts) defines `DATA_BASE` from `import.meta.env.BASE_URL` plus `data` - the single constant every fetch under `datasets/` must use ([`data.ts`](../../frontend/src/lib/data.ts), [`sql.ts`](../../frontend/src/lib/sql.ts), [`maplibre/sources.ts`](../../frontend/src/lib/maplibre/sources.ts)).
4. [`frontend/src/lib/config/cdn.ts`](../../frontend/src/lib/config/cdn.ts) is the single base/CDN resolution seam every frontend module reads. It owns `CDN_BASE` (= `import.meta.env.BASE_URL`), the canonical `withBase` (in-app route hrefs, consumed by `link.*`), and `assetUrl` (runtime `public/` asset `src` URLs - svg/png glyphs, brand logos); `paths.ts` `DATA_BASE`/`SHARE_BASE` re-export through it. Two mirrored contract tests guard the seam: [`in-app-hrefs-use-base.test.ts`](../../frontend/src/contracts/in-app-hrefs-use-base.test.ts) forbids base-less in-app `href`s, and [`cdn-assets-use-seam.test.ts`](../../frontend/src/contracts/cdn-assets-use-seam.test.ts) forbids base-less runtime asset `src`s (added after a base-less `<img src="/brands/wikipedia.svg">` 404'd on the deployed `/yen-gov/` site). CSS `url()` and `index.html` are out of scope - Vite rewrites those at build time.

To move the bundle (custom domain, user/org Pages, CDN, S3 origin) change **only** the `BASE_URL` env var in the workflow — the value flows through Vite to every URL builder. Local `bun run dev` / `bun run preview` keep their root mount because `BASE_URL` is unset.

Hardcoding the repo name in source is forbidden (CLAUDE.md §6); the env var is the structural seam.

## Static CSV Serving Contract

Post-X1a-fu2, the live deploy contract for tabular canonical data is fetchable long-format CSV under `/data/data/...`, not Parquet range serving. The frontend reads these files through DuckDB-WASM `read_csv(columns=..., header=true, auto_detect=false)` or typed loader code. GitHub Pages therefore has to serve the committed CSV bytes at the expected URL and must not return an HTML fallback page for data paths.

The `deploy-pages` smoke check enforces the current contract by fetching the Tamil Nadu election-results CSV from the live Pages URL:

```text
https://miztiik.github.io/yen-gov/data/data/datapoints/electoral/tamil-nadu_election_results.csv
```

The smoke asserts that the file is non-empty and that its header is exactly:

```text
entity_id,year,period_label,period_seq,indicator_id,value_numeric,value_text,source_id,derivation
```

This smoke catches the two deploy failures that matter for the static CSV seam: `datasets/` was not staged into `_site/data`, or the Pages origin is serving the wrong bytes for the canonical CSV path.

## What is NOT deployed

- `backend/` — local pipeline only.
- `admin/` — dev-only operator console on port 5174 (CLAUDE.md §3). Its checks live alongside the rest of the dev-only tooling in [`backend.yml`](../../.github/workflows/backend.yml).
- `tools/` — dev tooling.
- `.runtime/` — gitignored.
- `config/` — read by `backend/`, not by the bundle.

## See also

- [Frontend overview](frontend/overview.md)
- [Frontend data loading](frontend/data-loading.md)
- [docs/how-to/release.md](../how-to/release.md)
- [Data flow](data-flow.md)

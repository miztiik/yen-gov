# Deployment

**Last Updated**: 2026-05-19

yen-gov deploys as a single static bundle to GitHub Pages. There is no production backend (CLAUDE.md Holy Law #1). This page is the operator-level overview; the design rationale lives in [frontend/data-loading > production placement](frontend/data-loading.md#production-placement).

## Two workflows: front-end and back-end

| Workflow | Trigger | What it does | Publishes? |
| -------- | ------- | ------------ | ---------- |
| [`deploy-site.yml`](../../.github/workflows/deploy-site.yml) | every PR + push to main + manual dispatch | All gating jobs for the public citizen site (vitest frontend, build, Playwright on the citizen frontend) AND, on push to main / manual dispatch only, the Pages deploy of the bundle this run just built + a live smoke check. Stale runs for the same PR/branch are cancelled. | Yes - on green push to main. |
| [`backend.yml`](../../.github/workflows/backend.yml) | push / PR with `paths:` filter on `backend/**`, `admin/**`, `datasets/**`, the workflow file itself + manual `workflow_dispatch` | All dev-only tooling: pytest of the ingest pipeline (non-admin), pytest of the admin FastAPI routes, admin SPA svelte-check + vitest, admin Playwright e2e (mocks `/api/*` via `page.route`). Frontend-only commits skip this workflow entirely. No cron - dev tooling doesn't break without code changes. Live tests skipped via `YEN_GOV_NO_NET=1`. Tier-B corpus conformance is a LOCAL pre-emit check, not gated here - see [backend/validator.md](backend/validator.md). | No - everything here is dev-only (CLAUDE.md §3) and never ships in `_site/`. |

The split mirrors the deployment reality: anything in `frontend/` ships; anything in `backend/` or `admin/` does not. `deploy-site.yml` defends the public artifact; `backend.yml` defends the local dev/operator tooling that produces and manages it. The two workflows are independent - a red `backend.yml` never blocks a green `deploy-site.yml` from publishing.

### One workflow for the site, not two

The site build IS the verification, and on green main the same artifact is the deploy artifact. There is exactly one `bun run build` per workflow run - no throwaway build separate from the deploy build. Rapid-fire commits to main are batched naturally by `concurrency.cancel-in-progress: true` keyed on the ref: a 5-commit burst queues 5 runs, the in-progress ones get cancelled, only the latest completes and publishes. No cron, no preflight that has to dedupe-by-SHA, no second build at deploy time.

The deploy step itself is one job (`deploy-pages`) gated by `if: (github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main'` and `needs: [frontend-vitest, frontend-build, citizen-site-e2e]`. PR runs evaluate that `if` to false and skip the deploy entirely; the gating jobs still run and report status on the PR.

### Why backend pytest is not in the publish gate

The deployed bundle is pure static (Svelte build + datasets/ staged under `_site/data/`). No Python ever runs in production. The backend pytest suite covers code that:

- ran *locally* to produce `datasets/**` (by the time CI runs, the data is already committed),
- never executes again until the next local ingest,
- has no presence in the deployed artifact.

Gating publish on it would conflate "my dev tooling is healthy" with "the public site is healthy". They are different concerns. The publish-relevant defences are: (a) does the bundle build (`frontend-build`), (b) does the built app actually render (`citizen-site-e2e`), (c) does the deployed origin respond correctly (the smoke step in `deploy-pages`). That is what `deploy-site.yml` checks; everything else lives in `backend.yml`.

### Why admin lives under backend.yml, not its own workflow

The admin operator console is a separate local-only Svelte app on port 5174 (CLAUDE.md §3, [admin/AGENTS.md](../../admin/AGENTS.md)) and nothing under `admin/` is copied into the deployed Pages bundle. Earlier the admin checks lived in their own workflow (`admin-checks.yml`); they collapsed into `backend.yml` because the unifying axis is "dev-only / never deployed" rather than "admin specifically". The admin console (Svelte SPA) and the admin API (FastAPI shim under `backend/yen_gov/admin/`) are the operator-facing face of the same local pipeline that `pipeline-pytest` already covers. Coupling admin tests to the publish gate would create an inverted incentive: any flake in admin e2e (vite webServer boot race, Playwright timing) indefinitely blocks the public site from updating. The two-workflow split makes that impossible by construction: `deploy-site.yml` never depends on `backend.yml`.

The `pipeline-pytest` job in `backend.yml` installs only the `[dev]` extra and `--ignore`s the four `test_admin_*.py` files, so a transitive `import fastapi` failure in admin tests cannot accidentally pull admin coverage into the pipeline-pytest job. The matching `admin-api-pytest` job installs `[dev,admin]` and runs only those four files.

## Job naming

Workflow job names read top-to-bottom and say what the job actually does, so PR check lists are self-describing without anyone having to open the YAML:

| Workflow | Job id | Display name |
| -------- | ------ | ------------ |
| `deploy-site.yml` | `frontend-vitest` | vitest (frontend unit + contract + integration) |
| `deploy-site.yml` | `frontend-build` | build citizen site (Pages artifact) |
| `deploy-site.yml` | `citizen-site-e2e` | Playwright e2e (public citizen site) |
| `deploy-site.yml` | `deploy-pages` | deploy to GitHub Pages |
| `backend.yml` | `pipeline-pytest` | pytest (ingest pipeline, non-admin) |
| `backend.yml` | `admin-api-pytest` | pytest (admin FastAPI routes) |
| `backend.yml` | `admin-console-vitest` | vitest (admin console unit + contract) |
| `backend.yml` | `admin-console-e2e` | Playwright e2e (admin operator console) |

The two Playwright suites are distinct apps: `citizen-site-e2e` covers the public site that ships to https://miztiik.github.io/yen-gov/; `admin-console-e2e` covers the dev-only operator console on port 5174.

## Branch protection

Branch protection on `main` is not currently configured (verified empty via `gh api repos/miztiik/yen-gov/branches/main/protection` -> 404). For a solo repo at low frequency this is intentional: red tests show up as red checks on the commit but do not block merging. The `deploy-pages` job's own `needs:` chain already prevents a broken bundle from publishing.

If branch protection is ever enabled (multi-author repo, for example), the required status checks should be:

- `frontend-vitest`
- `frontend-build`
- `citizen-site-e2e`

`deploy-pages` MUST NOT be a required check - it never runs on PRs (its `if` requires push or workflow_dispatch on main), so requiring it would block every merge. Jobs from `backend.yml` MUST NOT be required either - they are path-filtered and would not run on pure-frontend PRs, blocking every such merge.

Corpus conformance is the engineer's local pre-emit responsibility (`python -m yen_gov validate --root .`), since this repo's CI has no build that consumes `datasets/**` to defend - see [backend/validator.md](backend/validator.md).

Scraping ECI/Wikipedia and rebuilding boundary PMTiles are **local-only** operations (CLAUDE.md §1, §13): run `python -m yen_gov run <event> <state>` and `python tools/boundaries/build.py` on a maintainer machine, commit the regenerated `datasets/` through a normal PR. Both artifacts change rarely (results don't change post-declaration; boundaries change once per delimitation cycle), so a CI dispatch is unnecessary overhead. The contract between scraping and deploying is the `datasets/` directory committed to main.

## Pages artifact shape

The deploy step assembles (per [frontend/data-loading > production placement](frontend/data-loading.md#production-placement)):

```text
_site/
├── index.html               (from frontend/dist/)
├── assets/...               (from frontend/dist/)
└── data/                    (from datasets/, copied at deploy time)
    ├── elections/election_results.parquet
    ├── elections/dim_acs.parquet
    ├── elections/dim_candidates.parquet
    ├── elections/dim_parties.parquet
    ├── reference/in/states/<state>/...
    └── schemas/...
```

`fetch('/data/<rel>')` resolves the same way in dev (Vite middleware) and prod (this static layout) — see [frontend/data-loading](frontend/data-loading.md). The smoke step in `deploy-site.yml` (the `deploy-pages` job) enforces that contract by fetching `data/elections/election_results.parquet` from the deployed origin and asserting it carries the Parquet magic header (`PAR1` at offsets 0 and -4). The legacy per-state `result.summary.json` smoke target retired in PR-O.4 (TODO row `1.8b-ii`).

## Pages URL base

The bundle is served under a project Pages subpath (`https://miztiik.github.io/yen-gov/`), so both emitted asset URLs (`/yen-gov/assets/...`) and runtime data URLs (`/yen-gov/data/...`) must carry the prefix. The mechanism:

1. The `frontend-build` job in `deploy-site.yml` exports `BASE_URL=/yen-gov/` to the `bun run build` step.
2. [`frontend/vite.config.ts`](../../frontend/vite.config.ts) reads `process.env.BASE_URL` (default `/`) and passes it as Vite's [`base`](https://vitejs.dev/config/shared-options.html#base). Vite then rewrites `<script>`/`<link>` URLs in `index.html` and exposes the value to client code as `import.meta.env.BASE_URL` (always trailing-slashed).
3. [`frontend/src/lib/paths.ts`](../../frontend/src/lib/paths.ts) defines `DATA_BASE` from `import.meta.env.BASE_URL` plus `data` - the single constant every fetch under `datasets/` must use ([`data.ts`](../../frontend/src/lib/data.ts), [`sql.ts`](../../frontend/src/lib/sql.ts), [`maplibre/sources.ts`](../../frontend/src/lib/maplibre/sources.ts)).

To move the bundle (custom domain, user/org Pages, CDN, S3 origin) change **only** the `BASE_URL` env var in the workflow — the value flows through Vite to every URL builder. Local `bun run dev` / `bun run preview` keep their root mount because `BASE_URL` is unset.

Hardcoding the repo name in source is forbidden (CLAUDE.md §6); the env var is the structural seam.

## HTTP Range + MIME (canonical Parquet contract)

DuckDB-WASM in the browser reads Parquet via HTTP `Range:` requests so it never has to download a full file to project a few columns. The canonical store therefore depends on GitHub Pages honouring two HTTP properties:

1. `Accept-Ranges: bytes` on every static asset.
2. `206 Partial Content` + a correct `Content-Range` header when the client sends `Range: bytes=N-M`.
3. A non-`text/html` content type for `.parquet` so DuckDB-WASM does not try to parse it as HTML on error pages. Pages defaults unknown extensions to `application/octet-stream`, which is the contract DuckDB-WASM expects.

Verified Phase 0.7 (2026-05-18) against the live Pages deploy:

```
$ curl -sI https://miztiik.github.io/yen-gov/data/elections/election_results.parquet
HTTP/1.1 200 OK
Content-Length: <varies>
Content-Type: application/octet-stream
Accept-Ranges: bytes

$ curl -s -o /dev/null -w "%{http_code} %header{content-range}\n" \
    -H "Range: bytes=100-199" \
    https://miztiik.github.io/yen-gov/data/elections/election_results.parquet
206 bytes 100-199/<total>

$ curl -sI https://miztiik.github.io/yen-gov/data/_test/range-mime-probe.parquet
HTTP/1.1 200 OK
Content-Length: 363
Content-Type: application/octet-stream
Accept-Ranges: bytes

$ curl -s -o /dev/null -w "%{http_code} %{content_type} %header{content-range}\n" \
    -H "Range: bytes=0-99" \
    https://miztiik.github.io/yen-gov/data/_test/range-mime-probe.parquet
206 application/octet-stream bytes 0-99/363
```

The Parquet-MIME probe lives at `datasets/_test/range-mime-probe.parquet` (363 bytes, hand-emitted via DuckDB COPY with KV metadata `purpose=pages-range-mime-probe-phase-0.7`). It is the single asset under `datasets/_test/` whose sole purpose is to keep the Pages MIME contract observable after every deploy. Do not delete it; do not consume it from frontend code.

If the Pages contract ever regresses (any of `Accept-Ranges`, `206`, or `Content-Type != text/html` on the probe), the canonical store is unreadable in the browser and the deploy MUST be rolled back. Add a curl-based smoke check to the `deploy-pages` job in `deploy-site.yml` if that ever happens.

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

# Deployment

**Last Updated**: 2026-05-19

yen-gov deploys as a single static bundle to GitHub Pages. There is no production backend (CLAUDE.md Holy Law #1). This page is the operator-level overview; the design rationale lives in [frontend/data-loading > production placement](frontend/data-loading.md#production-placement).

## Two workflows

| Workflow | Trigger | What it does | Publishes? |
| -------- | ------- | ------------ | ---------- |
| [`site.yml`](../../.github/workflows/site.yml) | every PR + push to main + manual dispatch | All gating jobs for the public citizen site (pytest non-admin, vitest frontend, build, Playwright on the citizen frontend) AND, on push to main / manual dispatch only, the Pages deploy of the bundle this run just built + a live smoke check. Live tests skipped via `YEN_GOV_NO_NET=1`. Stale runs for the same PR/branch are cancelled. Tier-B corpus conformance is a LOCAL pre-emit check, not gated here - see [backend/validator.md](backend/validator.md). | Yes - on green push to main. |
| [`admin-checks.yml`](../../.github/workflows/admin-checks.yml) | push / PR with `paths:` filter on `admin/**`, `backend/yen_gov/admin/**`, `backend/tests/test_admin_*.py`, the workflow file itself + manual `workflow_dispatch` | pytest of `backend/tests/test_admin_*.py` (FastAPI route contracts), admin SPA svelte-check + vitest, admin Playwright e2e (mocks `/api/*` via `page.route`). Runs only when admin code is touched, OR manually. No cron - admin doesn't break without code changes. | No - admin is dev-only (CLAUDE.md §3) and never ships in `_site/`. |

### One workflow for the site, not two

The site build IS the verification, and on green main the same artifact is the deploy artifact. There is exactly one `bun run build` per workflow run - no throwaway build separate from the deploy build. Rapid-fire commits to main are batched naturally by `concurrency.cancel-in-progress: true` keyed on the ref: a 5-commit burst queues 5 runs, the in-progress ones get cancelled, only the latest completes and publishes. No cron, no preflight that has to dedupe-by-SHA, no second build at deploy time.

The deploy step itself is one job (`deploy-pages`) gated by `if: (github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main'` and `needs: [pytest, frontend-vitest, frontend-build, citizen-site-e2e]`. PR runs evaluate that `if` to false and skip the deploy entirely; the gating jobs still run and report status on the PR.

### Why admin is a separate workflow

The admin operator console is a separate local-only Svelte app on port 5174 (CLAUDE.md §3, [admin/AGENTS.md](../../admin/AGENTS.md)) and nothing under `admin/` is copied into the deployed Pages bundle. Coupling admin tests to the publish gate created an inverted incentive: any flake in admin e2e (vite webServer boot race, Playwright timing) indefinitely blocks the public site from updating. The split makes that impossible by construction: `site.yml` never depends on `admin-checks.yml`, and `admin-checks.yml` only runs when admin code actually changes (or on manual dispatch). A green public-site bundle with red admin is a deployable state.

The `pytest` job in `site.yml` installs only the `[dev]` extra and `--ignore`s the four `test_admin_*.py` files, so a transitive `import fastapi` failure in admin tests cannot accidentally pull admin coverage back into the publish gate. The matching `admin-api-pytest` job in `admin-checks.yml` installs `[dev,admin]` and runs only those four files.

## Job naming

Workflow job names read top-to-bottom and say what the job actually does, so PR check lists are self-describing without anyone having to open the YAML:

| Workflow | Job id | Display name |
| -------- | ------ | ------------ |
| `site.yml` | `pytest` | pytest (backend, non-admin) |
| `site.yml` | `frontend-vitest` | vitest (frontend unit + contract + integration) |
| `site.yml` | `frontend-build` | build citizen site (Pages artifact) |
| `site.yml` | `citizen-site-e2e` | Playwright e2e (public citizen site) |
| `site.yml` | `deploy-pages` | deploy to GitHub Pages |
| `admin-checks.yml` | `admin-api-pytest` | pytest (admin FastAPI routes) |
| `admin-checks.yml` | `admin-console-vitest` | vitest (admin console unit + contract) |
| `admin-checks.yml` | `admin-console-e2e` | Playwright e2e (admin operator console) |

The two Playwright suites are distinct apps: `citizen-site-e2e` covers the public site that ships to https://miztiik.github.io/yen-gov/; `admin-console-e2e` covers the dev-only operator console on port 5174.

## Branch protection

Required status checks for merge to main:

- `pytest`
- `frontend-vitest`
- `frontend-build`
- `citizen-site-e2e`

`deploy-pages` MUST NOT be a required check - it never runs on PRs (its `if` requires push or workflow_dispatch on main), so requiring it would block every merge. `admin-console-e2e` / `admin-console-vitest` / `admin-api-pytest` MAY be optional non-blocking checks; do not mark them required because `admin-checks.yml` is path-filtered and would not run on non-admin PRs, blocking every non-admin merge.

Corpus conformance is the engineer's local pre-emit responsibility (`python -m yen_gov validate --root .`), since this repo's CI has no build that consumes `datasets/**` to defend - see [backend/validator.md](backend/validator.md).

Scraping ECI/Wikipedia and rebuilding boundary PMTiles are **local-only** operations (CLAUDE.md §1, §13): run `python -m yen_gov run <event> <state>` and `python tools/boundaries/build.py` on a maintainer machine, commit the regenerated `datasets/` through a normal PR. Both artifacts change rarely (results don't change post-declaration; boundaries change once per delimitation cycle), so a CI dispatch is unnecessary overhead. The contract between scraping and deploying is the `datasets/` directory committed to main.

## Pages artifact shape

The deploy step assembles (per [frontend/data-loading > production placement](frontend/data-loading.md#production-placement)):

```text
_site/
├── index.html               (from frontend/dist/)
├── assets/...               (from frontend/dist/)
└── data/                    (from datasets/, copied at deploy time)
    ├── elections/<event>/<state>/result.summary.json
    ├── reference/in/states/<state>/...
    └── schemas/...
```

`fetch('/data/<rel>')` resolves the same way in dev (Vite middleware) and prod (this static layout) — see [frontend/data-loading](frontend/data-loading.md). The smoke step in `site.yml` (the `deploy-pages` job) enforces that contract by fetching `data/elections/AcGenMay2026/S22/result.summary.json` from the deployed origin and asserting `state == "S22"`.

## Pages URL base

The bundle is served under a project Pages subpath (`https://miztiik.github.io/yen-gov/`), so both emitted asset URLs (`/yen-gov/assets/...`) and runtime data URLs (`/yen-gov/data/...`) must carry the prefix. The mechanism:

1. The `frontend-build` job in `site.yml` exports `BASE_URL=/yen-gov/` to the `bun run build` step.
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
$ curl -sI https://miztiik.github.io/yen-gov/data/elections/AcGenMay2026/S22/result.summary.json
HTTP/1.1 200 OK
Content-Length: 15909
Content-Type: application/json; charset=utf-8
Accept-Ranges: bytes

$ curl -s -o /dev/null -w "%{http_code} %header{content-range}\n" \
    -H "Range: bytes=100-199" \
    https://miztiik.github.io/yen-gov/data/elections/AcGenMay2026/S22/result.summary.json
206 bytes 100-199/15909

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

If the Pages contract ever regresses (any of `Accept-Ranges`, `206`, or `Content-Type != text/html` on the probe), the canonical store is unreadable in the browser and the deploy MUST be rolled back. Add a curl-based smoke check to the `deploy-pages` job in `site.yml` if that ever happens.

## What is NOT deployed

- `backend/` — local pipeline only.
- `admin/` — dev-only operator console on port 5174 (CLAUDE.md §3). Has its own gated-out workflow [`admin-checks.yml`](../../.github/workflows/admin-checks.yml).
- `tools/` — dev tooling.
- `.runtime/` — gitignored.
- `config/` — read by `backend/`, not by the bundle.

## See also

- [Frontend overview](frontend/overview.md)
- [Frontend data loading](frontend/data-loading.md)
- [docs/how-to/release.md](../how-to/release.md)
- [Data flow](data-flow.md)

# Deployment

**Last Updated**: 2026-05-18

yen-gov deploys as a single static bundle to GitHub Pages. There is no production backend (CLAUDE.md Holy Law #1). This page is the operator-level overview; the design rationale lives in [frontend/data-loading > production placement](frontend/data-loading.md#production-placement).

## Two workflows

| Workflow | Trigger | What it does |
| -------- | ------- | ------------ |
| [`ci-checks.yml`](../../.github/workflows/ci-checks.yml) | every PR + push to main | pytest (includes Tier-A schema sanity via fixture tests), frontend/admin builds, unit/contract/integration tests, and Playwright smoke. Live tests skipped via `YEN_GOV_NO_NET=1`. Gate only - nothing publishes. Stale runs for the same PR/branch are cancelled. Tier-B corpus conformance is a LOCAL pre-emit check, not gated here - see [backend/validator.md](backend/validator.md). |
| [`deploy-site.yml`](../../.github/workflows/deploy-site.yml) | hourly schedule + manual | checks that the latest `main` SHA has a successful CI run, skips scheduled redeploys of an already-published SHA, builds `frontend/dist/`, stages `datasets/` next to it as `data/`, uploads to Pages, smoke-tests the live URL. |

## Deploy cadence and CI gate

Production deploy is intentionally **batched hourly** instead of publishing every green commit. During active development, `main` can receive several small commits in quick succession; rebuilding and publishing Pages for every commit adds queue noise and compute churn without changing the public data story meaningfully. The hourly schedule publishes the newest eligible bundle, while `workflow_dispatch` remains available when an operator wants an immediate release.

`deploy-site.yml` has a preflight job before the Pages build:

1. It resolves the current `main` SHA from GitHub.
2. It requires a successful completed `ci-checks.yml` run for that exact SHA.
3. On scheduled runs, it checks whether `deploy-site.yml` has already successfully deployed that SHA and skips if so.
4. On manual runs, it still requires green CI, but may redeploy the same SHA when an operator deliberately asks for a fresh Pages publish.

This keeps the release pipe simple: CI proves the static bundle builds and the code's invariants hold; deploy publishes only a CI-green `main` bundle. Corpus conformance is the engineer's local pre-emit responsibility (`python -m yen_gov validate --root .`), since this repo's CI has no build that consumes `datasets/**` to defend - see [backend/validator.md](backend/validator.md). Branch protection should still require the CI jobs before merging, but the deploy preflight is a second guard against direct pushes or administrative bypasses.

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

`fetch('/data/<rel>')` resolves the same way in dev (Vite middleware) and prod (this static layout) — see [frontend/data-loading](frontend/data-loading.md). The smoke step in `deploy-site.yml` enforces that contract by fetching `data/elections/AcGenMay2026/S22/result.summary.json` from the deployed origin and asserting `state == "S22"`.

## Pages URL base

The bundle is served under a project Pages subpath (`https://miztiik.github.io/yen-gov/`), so both emitted asset URLs (`/yen-gov/assets/...`) and runtime data URLs (`/yen-gov/data/...`) must carry the prefix. The mechanism:

1. The deploy workflow exports `BASE_URL=/yen-gov/` to the `bun run build` step.
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

If the Pages contract ever regresses (any of `Accept-Ranges`, `206`, or `Content-Type != text/html` on the probe), the canonical store is unreadable in the browser and the deploy MUST be rolled back. Add a curl-based smoke check to `deploy-site.yml` if that ever happens.

## What is NOT deployed

- `backend/` — local pipeline only.
- `tools/` — dev tooling.
- `.runtime/` — gitignored.
- `config/` — read by `backend/`, not by the bundle.

## See also

- [Frontend overview](frontend/overview.md)
- [Frontend data loading](frontend/data-loading.md)
- [docs/how-to/release.md](../how-to/release.md)
- [Data flow](data-flow.md)

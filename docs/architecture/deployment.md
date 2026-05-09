# Deployment

**Last Updated**: 2026-05-09

yen-gov deploys as a single static bundle to GitHub Pages. There is no production backend (CLAUDE.md Holy Law #1). This page is the operator-level overview; the design rationale lives in [frontend/data-loading > production placement](frontend/data-loading.md#production-placement).

## Three workflows

| Workflow | Trigger | What it does |
| -------- | ------- | ------------ |
| [`validate.yml`](../../.github/workflows/validate.yml) | every PR + push to main | pytest, schema/data validation, frontend build. Live tests skipped via `YEN_GOV_NO_NET=1`. |
| [`pipeline.yml`](../../.github/workflows/pipeline.yml) | manual dispatch | scrapes ECI (and optionally Wikipedia reference) into `datasets/`, runs the validator, opens a PR with the diff. |
| [`deploy.yml`](../../.github/workflows/deploy.yml)     | push to main + manual | builds `frontend/dist/`, stages `datasets/` next to it as `data/`, uploads to Pages, smoke-tests the live URL. |

The flows are deliberately decoupled: scraping never deploys, deploying never scrapes. The contract between them is the `datasets/` directory committed to main.

## Pages artifact shape

The deploy step assembles (per [frontend/data-loading > production placement](frontend/data-loading.md#production-placement)):

```
_site/
├── index.html               (from frontend/dist/)
├── assets/...               (from frontend/dist/)
└── data/                    (from datasets/, copied at deploy time)
    ├── elections/<event>/<state>/result.summary.json
    ├── reference/in/states/<state>/...
    └── schemas/...
```

`fetch('/data/<rel>')` resolves the same way in dev (Vite middleware) and prod (this static layout) — see [frontend/data-loading](frontend/data-loading.md). The smoke step in `deploy.yml` enforces that contract by fetching `data/elections/AcGenMay2026/S22/result.summary.json` from the deployed origin and asserting `state == "S22"`.

## Pages URL base

The bundle is served under a project Pages subpath (`https://miztiik.github.io/yen-gov/`), so both emitted asset URLs (`/yen-gov/assets/...`) and runtime data URLs (`/yen-gov/data/...`) must carry the prefix. The mechanism:

1. The deploy workflow exports `BASE_URL=/yen-gov/` to the `bun run build` step.
2. [`frontend/vite.config.ts`](../../frontend/vite.config.ts) reads `process.env.BASE_URL` (default `/`) and passes it as Vite's [`base`](https://vitejs.dev/config/shared-options.html#base). Vite then rewrites `<script>`/`<link>` URLs in `index.html` and exposes the value to client code as `import.meta.env.BASE_URL` (always trailing-slashed).
3. [`frontend/src/lib/paths.ts`](../../frontend/src/lib/paths.ts) defines `DATA_BASE = ` `${import.meta.env.BASE_URL}data` — the single constant every fetch under `datasets/` must use ([`data.ts`](../../frontend/src/lib/data.ts), [`sql.ts`](../../frontend/src/lib/sql.ts), [`maplibre/sources.ts`](../../frontend/src/lib/maplibre/sources.ts)).

To move the bundle (custom domain, user/org Pages, CDN, S3 origin) change **only** the `BASE_URL` env var in the workflow — the value flows through Vite to every URL builder. Local `bun run dev` / `bun run preview` keep their root mount because `BASE_URL` is unset.

Hardcoding the repo name in source is forbidden (CLAUDE.md §6); the env var is the structural seam.

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

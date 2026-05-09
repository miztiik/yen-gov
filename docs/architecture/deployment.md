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

If the repo is deployed at a *project* Pages URL (`https://<user>.github.io/<repo>/`), absolute fetches like `/data/...` resolve to the wrong origin path. Two options:

- Use a **user/org Pages site** or a **custom domain** so the bundle is at the root.
- Set Vite `base` to the subpath and prefix fetches with `import.meta.env.BASE_URL` in `data.ts`.

Today the bundle assumes root. Switching adds one line of Vite config and one substitution in `data.ts`; revisit if the choice is forced.

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

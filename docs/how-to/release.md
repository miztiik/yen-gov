# How to release

**Last Updated**: 2026-05-15

A release is "the bundle on Pages reflects the latest validated `datasets/`". Two paths reach that state.

## Path A — code-only change (UI tweak, schema-compatible refactor)

1. Branch, commit, push, open PR.
2. `ci-checks.yml` runs (pytest + schema/data validation + frontend build). Wait for green.
3. Merge to main. The next hourly `deploy-site.yml` run publishes the latest CI-green main bundle, unless that exact SHA has already been deployed.
4. For an urgent release, manually dispatch `deploy-site.yml` from `main`; it still refuses to publish if the current main SHA has not passed CI.
5. Confirm the smoke job in `deploy-site.yml` passes — it fetches the live `result.summary.json` and asserts `state == "S22"`. Failure here means the dev/prod URL contract (see [frontend/data-loading.md](../architecture/frontend/data-loading.md)) is broken.

That's the entire flow when no upstream data is changing.

## Path B — refresh data from upstream

Scraping is local-only (CLAUDE.md §1, §13) — there is no `scrape` workflow. From a maintainer machine:

1. `cd backend && python -m yen_gov run <event> <state> --root ..` (defaults you'd typically use: `AcGenMay2026 S22`). Add `python -m yen_gov reference <state> --root ..` first when re-scraping district/AC reference data from Wikipedia is intended.
2. `python -m yen_gov validate --root ..` to confirm the regenerated `datasets/` passes Tier A + Tier B.
3. Review the `git diff datasets/**`. **Look for unexpected swings** — a sudden NOTA spike, a vanished party, a vote count that dropped — which usually signals an upstream HTML change rather than reality. If anything looks wrong, discard and dig into the parser before re-running.
4. Branch, commit, push, open PR. Path A from here on (`ci-checks.yml` -> merge -> hourly or manual `deploy-site.yml`).

## Deploy timing

Pages deploy is batched to reduce unnecessary rebuilds while the project is moving quickly:

- Automatic: once per hour, `deploy-site.yml` checks the latest `main` commit and publishes it only if CI is green and that SHA has not already been deployed.
- Manual: run `deploy-site.yml` from the Actions tab when a validated change needs to go live before the next hourly tick.
- Skipped: scheduled runs do nothing when `main` is red, still running CI, or already deployed.

## Local pre-flight (optional but recommended)

Before pushing or dispatching, run the same checks the CI runs:

```bash
# Backend
cd backend
pytest -q
YEN_GOV_NO_NET=1 python -m yen_gov validate --root ..

# Frontend
cd ../frontend
bun install --frozen-lockfile
bun run build
```

If any of these fail locally, they will fail in CI.

## Rollback

There is no separate rollback button. To revert:

1. `git revert` the offending commit (whether code or data) on main.
2. Wait for `ci-checks.yml` to pass on the revert commit.
3. Let the next hourly `deploy-site.yml` publish it, or manually dispatch `deploy-site.yml` from `main` to publish immediately.

Because each deploy is a fresh artifact (no incremental state on Pages), a revert fully restores the previous bundle.

## See also

- [Deployment architecture](../architecture/deployment.md)
- [Run the pipeline (locally)](run-the-pipeline.md)
- [frontend/data-loading.md](../architecture/frontend/data-loading.md#production-placement)

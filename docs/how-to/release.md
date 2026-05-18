# How to release

**Last Updated**: 2026-05-19

A release is "the bundle on Pages reflects the latest validated `datasets/`". Two paths reach that state.

## Path A — code-only change (UI tweak, schema-compatible refactor)

1. Branch, commit, push, open PR.
2. `site.yml` runs (pytest non-admin + frontend vitest + build + Playwright on the citizen site). Wait for green. Note: Tier-B corpus validation is a LOCAL pre-emit check, not a CI gate - see [validator.md](../architecture/backend/validator.md).
3. Merge to main. The same `site.yml` workflow re-runs on the merge commit; on green, its `deploy-pages` job publishes the bundle this run just built. Rapid-fire merges are batched naturally - `concurrency.cancel-in-progress: true` cancels in-flight runs when a newer commit lands, so only the latest green main publishes.
4. For an urgent republish without a new commit, manually dispatch `site.yml` from `main` in the Actions tab.
5. Confirm the smoke step in `deploy-pages` passes — it fetches the live `result.summary.json` and asserts `state == "S22"`. Failure here means the dev/prod URL contract (see [frontend/data-loading.md](../architecture/frontend/data-loading.md)) is broken.

That's the entire flow when no upstream data is changing.

## Path B — refresh data from upstream

Scraping is local-only (CLAUDE.md §1, §13) — there is no `scrape` workflow. From a maintainer machine:

1. `cd backend && python -m yen_gov run <event> <state> --root ..` (defaults you'd typically use: `AcGenMay2026 S22`). Add `python -m yen_gov reference <state> --root ..` first when re-scraping district/AC reference data from Wikipedia is intended.
2. `python -m yen_gov validate --root ..` to confirm the regenerated `datasets/` passes Tier A + Tier B.
3. Review the `git diff datasets/**`. **Look for unexpected swings** — a sudden NOTA spike, a vanished party, a vote count that dropped — which usually signals an upstream HTML change rather than reality. If anything looks wrong, discard and dig into the parser before re-running.
4. Branch, commit, push, open PR. Path A from here on (`site.yml` -> merge -> auto-deploy from the same workflow on green main).

## Deploy timing

Pages deploy follows the workflow, not a separate schedule:

- Automatic: every push to `main` runs `site.yml`. On green, the `deploy-pages` job publishes the bundle this run built. A burst of N commits collapses naturally via `concurrency.cancel-in-progress: true` keyed on the ref - the in-progress runs cancel and only the latest completes.
- Manual: dispatch `site.yml` from the Actions tab to re-publish the current `main` without a new commit (e.g. to test a Pages settings change).
- Skipped: `deploy-pages` only runs when its `if` is true (push or workflow_dispatch on main) AND every gating job is green. PRs run the gating jobs but never deploy.

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
2. The revert is a push to `main`, so `site.yml` runs against the revert commit. On green, `deploy-pages` publishes the reverted bundle automatically.
3. If you need it live before the workflow finishes (rare), dispatch `site.yml` manually after the revert merges - it just runs the same workflow again.

Because each deploy is a fresh artifact (no incremental state on Pages), a revert fully restores the previous bundle.

## See also

- [Deployment architecture](../architecture/deployment.md)
- [Run the pipeline (locally)](run-the-pipeline.md)
- [frontend/data-loading.md](../architecture/frontend/data-loading.md#production-placement)

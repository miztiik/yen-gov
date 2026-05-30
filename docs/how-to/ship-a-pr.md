# How to ship a PR

**Last Updated**: 2026-05-30

The end-to-end runbook for taking a worker branch from "ready to commit" to "merged + cleaned up". Covers the 2-commit-then-squash pattern, the 5-gate Definition of Done, and the post-merge cleanup that closes the loop. This is the procedural counterpart to [CLAUDE.md](../../CLAUDE.md) §8 (Git Hygiene) + §9 (Definition of Done) + §13 (UI Verification).

This doc exists because the post-merge cleanup steps (delete stale remote branch when `gh pr merge` cosmetic-errors, prune `: gone` local branches, recover the worker worktree to a known state) were operator-tribal-knowledge for >20 PRs before being written down. Every PR was paying the same ~2 min cleanup tax and every session resume started with "what state is the worktree in?". This runbook ends both.

## When to run

For any PR you author. The mechanics are identical whether the PR is a recon-only docs change, a single-file fix, a multi-file retirement sweep, or a feature implementation. The runbook scales with the change; it does not add steps for small PRs.

## Inputs

- A correction-level assessment per [CLAUDE.md](../../CLAUDE.md) §6 (Level 0 / 1 / 2 / 3 / 4 / 5). Level 5 stops here for design consultation.
- Branch name in the form `<type>/<scope>-<slug>` (e.g. `feat/c1-blocks-recon`, `chore/catalogue-coverage-unblock`, `docs/phase-b-verdict-correction`).
- Knowledge of which worktree you are in. If you are not sure, run `git worktree list` (see Pre-flight below).

## Pre-flight

### Worktree state check

```powershell
cd <worker-worktree>
git worktree list
```

The output lists every worktree and which branch it has checked out. **This is the source of truth for branch ownership across worktrees**, NOT the master worktree's current branch. Use this to predict whether `gh pr merge` will succeed cleanly or cosmetic-error:

| Any worktree holds `[main]`? | `gh pr merge` outcome |
| --- | --- |
| No | Clean exit. gh auto-deletes remote branch + (sometimes) local branch. |
| Yes | Cosmetic error: `failed to run git: fatal: 'main' is already used by worktree at ...`. **Server-side merge still succeeds.** Manual cleanup of the remote branch IS required (gh skipped its post-merge git steps). |

This prediction is reliable because gh's post-merge cleanup tries to `git switch main` locally; if any worktree already has `main` checked out, that step fails and aborts the cleanup chain (without aborting the actual merge, which happened on the server side first).

### Branching

Always branch from `origin/main`, not from the worker's local `main` (which may be stale):

```powershell
git fetch origin main
git checkout -b <type>/<scope>-<slug> origin/main
```

If the worker can't checkout `main` because master holds it, that is fine — you do not need a local `main` to branch from `origin/main`. The `git checkout -b ... origin/main` form bypasses the conflict.

## The 2-commit-then-squash pattern

Use this pattern when your PR's diff needs to cite its own to-be-allocated PR number. The cost is one extra commit on the branch (~5 lines of churn) that vanishes at squash; the value is the in-doc PR# stamp lands in the same merge SHA as the work.

### Commit 1 — structural

All file edits, deletes, schema bumps, test changes. The plan-doc / ADR / how-to entries that reference this PR cite `PR #_pending_` as a placeholder. Write the commit message to a tmp file, then commit:

```powershell
git add <named paths>
git status --short  # Verify EVERY named path shows M / A / D / R in column 1.
                    # Any ' M' (space-M) entry means the path is NOT staged.
git commit -F .tmp_commit_msg.txt
```

The `git status --short` verification is the rule from a prior cascade-scrub miss: 6 files were staged-then-silently-unstaged, the commit shipped without them, `/t/energy` rendered 8 "Failed to load" placeholders. Always confirm column-1 is non-space for every named path.

If your scratch-file authoring tool inserts a UTF-8 BOM, prefer `[System.IO.File]::WriteAllText($p, $c, [System.Text.UTF8Encoding]::new($false))` over `Set-Content -Encoding utf8`. `git commit -F` itself treats the BOM as content and the BOM will show up in `git log --format=%B`.

### Push + create PR

```powershell
git push -u origin <branch>
gh pr create --base main --head <branch> --title "<title>" --body-file .tmp_pr_body.md
```

`gh pr create` may print a `Warning: N uncommitted changes` line to stderr if you have untracked `.tmp_*.md` files; this is informational and the PR creation proceeds normally. Capture the PR number from the URL it prints.

### Commit 2 — stamp

Replace `_pending_` with `#NNN` in every doc that references this PR:

```powershell
# Edit files: plan-doc row + narrative + ADR retirement-list + map.md + etc.
git add <stamped paths>
git commit -m "stamp(<scope>): PR #NNN"
git push
```

## The 5-gate Definition of Done

Run all five gates before merge. The full per-tier matrix is [docs/architecture/testing.md](../architecture/testing.md); the operational shorthand is below. Reference: [CLAUDE.md](../../CLAUDE.md) §9 (DoD) + §13 (UI verification) + §14 (test coverage policy).

### Gate 1 — validate

```powershell
$env:PYTHONPATH = '<worker>\backend'
& '<repo>\.venv\Scripts\python.exe' -m yen_gov validate --root . 2>&1 | Tee-Object .tmp_validate.log | Select-Object -Last 5
```

Must exit 0. Tier A + Tier B both run.

The `$env:PYTHONPATH` prepend is load-bearing in multi-worktree setups: master's `pip install -e backend` editable install silently shadows worker imports otherwise (`import yen_gov` resolves to master's stale code). Canary check: `python -c "import yen_gov; print(yen_gov.__file__)"` — if the path is not the worker's, your tests are running against master.

### Gate 2 — pytest

```powershell
& '<repo>\.venv\Scripts\python.exe' -m pytest backend/tests -q 2>&1 | Tee-Object .tmp_pytest.log | Select-Object -Last 5
```

Pre-existing-failure baseline is recorded in [docs/architecture/testing.md](../architecture/testing.md); your PR's run must match it (no NEW failures) unless your PR explicitly addresses one of the pre-existing items. Differentiate via `git diff --stat origin/main..HEAD -- <subsystem paths>` returning empty.

### Gate 3 — svelte-check

```powershell
cd <worker>\frontend
bun run check 2>&1 | Tee-Object .tmp_svelte.log | Select-Object -Last 8
```

### Gate 4 — vitest

```powershell
cd <worker>\frontend
bun run test 2>&1 | Tee-Object .tmp_vitest.log | Select-Object -Last 10
```

Script is `test` (which runs `vitest run`), NOT `test:run` (does not exist in this repo).

### Gate 5 — browser smoke

For any change touching `frontend/` or `admin/` runtime. Open the affected routes plus one cross-route smoke; confirm new copy/structure renders, no new `[error]` console events, no new `404`. Reference: [CLAUDE.md](../../CLAUDE.md) §13.

## Merge

```powershell
gh pr merge NNN --squash --delete-branch
```

Both commits squash to one entry on `main`. The merged-to-main commit contains the correct `PR #NNN` reference inline.

**Do NOT use `--auto`** in this repo: `enablePullRequestAutoMerge` is not enabled until repo settings turn it on, and `--auto` will return a GraphQL error. Use plain `--squash --delete-branch`.

## Post-merge cleanup

This is the loop that was previously implicit. Run every step in order.

### Step 1 — verify the merge actually happened

```powershell
gh pr view NNN --json state,mergedAt,mergeCommit
```

`state` MUST be `MERGED`. If gh cosmetic-errored on merge, the server-side merge usually succeeded anyway — this command confirms.

### Step 2 — delete the remote branch if gh skipped it

If `gh pr merge` cosmetic-errored, its post-merge git steps were skipped, including the remote branch delete:

```powershell
git push origin --delete <branch>
```

Expected output: `[deleted]`. If gh's `--delete-branch` ran successfully, this returns `error: unable to delete '<branch>': remote ref does not exist` — which is the GOOD outcome (already deleted).

### Step 3 — fetch + sync worker's view of origin/main

```powershell
git fetch origin main
git log --oneline origin/main -1
```

Confirms the new main HEAD matches the merge commit you just landed.

### Step 4 — prune stale local branches

After several merges, the worker accumulates local branches whose remote-tracking ref is `: gone`. Prune in bulk, skipping the current branch (which `git branch -vv` prefixes with `* `):

```powershell
git fetch --prune
git branch -vv | Select-String ': gone\]' | ForEach-Object {
    $tokens = ($_.Line.TrimStart('*',' ').Trim() -split '\s+')
    $branchName = $tokens[0]
    if ($branchName -and -not ($branchName -match '^(main|HEAD)$')) {
        git branch -D $branchName
    }
}
```

Use `git branch -D` (force), not `-d` (merged-only), because squash-merged branches do not look "merged" to git even though they are. The `: gone` marker is the safe signal — it means `gh pr merge --delete-branch` (or your Step 2 above) deleted the upstream, which only happens after the PR merges.

Do NOT prune branches without a `: gone` marker; those have live upstreams and may be a parallel agent's work-in-progress.

### Step 5 — clean up tmp files

```powershell
Remove-Item .tmp_*.txt, .tmp_*.md, .tmp_*.log -ErrorAction SilentlyContinue
```

The `.tmp_*` pattern is the convention for ephemeral PR-authoring files. Gate logs (`.tmp_*.log`) and commit-message scratch (`.tmp_commit_msg*`) are matched by patterns in [.gitignore](../../.gitignore); PR-body scratch (`.tmp_*.md`, generic `.tmp_*.txt`) is NOT, so this cleanup step is what keeps them out of the worktree. If a tmp file ever gets staged by accident, `git rm --cached <path>` recovers.

### Step 6 — distill lessons

If the PR taught you something durable — a new pattern, a gotcha, a generalisable rule — distill it per [distill-a-plan.md](distill-a-plan.md) so the next agent does not rediscover it.

### Step 7 — leave the worker on a known state

For the next session:

- If you have follow-up work queued on the same plan: branch the next PR's slug from `origin/main` now (`git checkout -b <next-branch> origin/main`), so the next session starts with a known state.
- If the plan is complete: stay on the (now-stale) feature branch and document handover via the lesson file. Do not switch to `main` — master holds it.
- If you want a fully clean state for an unrelated next plan: `git checkout -b chore/<dated-slug> origin/main`. The named branch is the rest state.

## See also

- [CLAUDE.md](../../CLAUDE.md) §8 (Git Hygiene), §9 (Definition of Done), §13 (UI Verification), §14 (Test Coverage Policy)
- [distill-a-plan.md](distill-a-plan.md) — what to do with the lessons a PR produced
- [release.md](release.md) — what happens after merge from the CI / Pages perspective
- [run-the-pipeline.md](run-the-pipeline.md) — what runs locally before any PR that touches `datasets/`
- [ADR-0034](../architecture/decisions/0034-documentation-routing-contract.md) — which doc class owns which kind of statement

# T.3 indicator-catalogue widening — READY but MERGE-BLOCKED on P.1.A

**Date**: 2026-05-22
**Branch**: [`feat/t3-indicator-catalogue-v1.1-topic-tags-and-aliases`](https://github.com/miztiik/yen-gov/tree/feat/t3-indicator-catalogue-v1.1-topic-tags-and-aliases) @ commit landing in this session (push pending)
**Stacked on**: [`feat/p1-energy-pivot`](https://github.com/miztiik/yen-gov/tree/feat/p1-energy-pivot) @ `624852ff`
**Status**: ALL implementation gates green. Cannot open PR → `main` until **P.1.A merges first**.

---

## 1. Why this is blocked (the load-bearing constraint)

The 2 T.3 commits sit on top of `feat/p1-energy-pivot` (commits `4c87b85e` → `f13708df` parented at `624852ff`). The T.3 changeset modifies [datasets/taxonomy/indicators.json](datasets/taxonomy/indicators.json) to carry 59 catalogue rows — **30 elections + 29 energy** — and `topic_tags[]` populated on every row. The 29 energy rows came in via P.1.A C1 (commit `6f2c1cf2`); they are NOT on `main` yet.

If T.3 were rebased onto `main` today (which is at `de463eca` = the T.0e merge), the rebase would drop the 29 energy rows because they don't exist in main's ancestry — leaving a 30-row JSON file plus a `topic_tags` denormalisation that exercises only the elections side of the schema widening. That is a half-applied migration; the user prompt's escape clause forbids that.

Two ways out, in priority order:

1. **Wait for P.1.A to merge to main.** Then rebase T.3 onto the new main. The 29 energy rows arrive via P.1.A's history; T.3's `topic_tags` populate them at rebase time; no row-count divergence. This is the path the prior T.3 commit author flagged in `4c87b85e`'s commit body ("preferably AFTER P.1.A merges, then rebased onto clean main").
2. **Carve T.3 down to elections-only.** Rebase T.3 onto main; manually shrink `indicators.json` back to 30 rows; drop the 29 `topic_tags: ["energy"]` rows; open as "T.3-elections-only" PR. P.1.A would then ship the 29 energy rows already topic-tagged (because P.1.A would be re-based onto the T.3-elections-only main and read schema v1.1). This is strictly more work than path 1, and risks two rounds of conflict resolution on the same file. Reject unless P.1.A is going to stall for >1 week.

**Recommended**: path 1. The handover does not push a PR.

---

## 2. What landed this session (3 commits on T.3 branch — push pending)

| # | Commit | Scope |
|---|---|---|
| 1 | `4c87b85e` (prior) | Schema bump v1.0 → v1.1 (additive: `id_aliases[]`, `deprecated_in`, `topic_tags[]` confirmed optional); JSON `$schema_version` 1.1 + `topic_tags` on all 59 rows; Pydantic `IndicatorRow` widening + 33-col DDL; Tier-B `tier_b_indicator_alias_window` (60-day window) + `INDICATOR_ALIAS_WINDOW_DAYS = 60`; 30 backend tests + 23 vitest tests |
| 2 | `f13708df` (prior) | Docstring polish on `indicators_seed.py` — names JSON Schema as single source of truth for regex; documents paired-semantic gate; same code |
| 3 | (this session) | `indicators.parquet` regen (33 cols, 59 rows; verified `id_aliases`, `deprecated_in`, `topic_tags` columns present); [CLAUDE.md](CLAUDE.md) §10 two new anti-pattern bullets (`id_aliases` pairing + topic-prefix-forbidden); [TODO/20260517-canonical-long-format-pivot.md](TODO/20260517-canonical-long-format-pivot.md) row T.3 status bumped to READY-MERGE-AFTER-P.1.A; this handover |

---

## 3. Decisions locked by user 2026-05-22 (do NOT re-debate)

Per `/memories/session/plan.md` "T.3 decisions" block — applied verbatim by the prior T.3 agent:

- **Q1 release-tag scheme for `deprecated_in:`** → **ISO date `YYYY-MM-DD`**. Lexicographic sort; matches every `Last Updated:` doc convention; no semver math required for a repo with zero git tags.
- **Q2 migration scope** → **Option A — schema + mechanism + denorm on already-present rows only**. Specifically: schema v1.1, Pydantic + TS Zod widening, indicator parquet regen against 33-col DDL, Tier-B rule, frontend dereferencer DESCOPED, 110 legacy id rewrites DESCOPED. Each P.* PR rewrites its own family's ids and fills `id_aliases[]` at lift time. T.3 enables the rails; the families ride them when they pivot.
- **Q3 alias window length** → **60 days** (one release, strict-leaning). Tier-B literal: `(today - deprecated_in_date).days <= 60` else fail. If a rename needs more than 60 days, file an explicit ADR; do not extend `INDICATOR_ALIAS_WINDOW_DAYS` silently.

---

## 4. Validation gates run this session (all green)

| Gate | Command | Baseline | Actual | Δ |
|---|---|---:|---:|---:|
| Backend pytest | `cd backend; python -m pytest -q` | 799/41 | **844/41** | +45 (T.3 +30; main since prompt +15) |
| Tier-B validator | `python -m yen_gov validate --root .` | OK | **OK (0 issues)** | — |
| Frontend vitest | `cd frontend; bun run test --run` | 15,666/6 | **15,691/6** | +25 (T.3 +23; main since prompt +2) |
| Parquet regen | `python -m yen_gov emit-taxonomy --root .` | (n/a) | **59 rows / 33 cols / `id_aliases`+`deprecated_in`+`topic_tags` present** | — |

§13 browser smoke — **NOT applicable to this PR**. The two new commits this session touch zero `frontend/` runtime code (CLAUDE.md doc + plan-doc + parquet binary regen + handover doc). The prior T.3 commit's frontend changes (`frontend/src/lib/indicator-catalogue.ts` consumer module + 23 vitest tests) ran green under `bun run test --run` and have no Svelte component touch (consumer module only). When T.3 finally rebases onto post-P.1.A main and opens its PR, the rebase agent MUST run §13 smoke on `/`, `/t/elections`, and one indicator route to satisfy the v1.1 schema-driven render path.

---

## 5. Files touched (cumulative across all 3 commits)

**Schema / data contract** (1)
- [datasets/schemas/indicator-catalogue.schema.json](datasets/schemas/indicator-catalogue.schema.json) — v1.0 → v1.1, `id_aliases[]` + `deprecated_in`, `x-changelog` 2026-05-22 entry

**Backend** (2)
- [backend/yen_gov/canonical/indicators_seed.py](backend/yen_gov/canonical/indicators_seed.py) — Pydantic `IndicatorRow` adds `id_aliases: list[str] | None`, `deprecated_in: str | None`; DDL `["?"] * 31` → `["?"] * 33`; compile-time `ValueError` on `id_aliases` set without `deprecated_in`
- [backend/yen_gov/validate.py](backend/yen_gov/validate.py) — new `INDICATOR_ALIAS_WINDOW_DAYS = 60`; new `tier_b_indicator_alias_window(root, today=None)` rule; wired into `run()` chain

**Frontend** (2)
- `frontend/src/lib/indicator-catalogue.ts` (new) — TS consumer module with `IndicatorCatalogueEntry` type + Zod widen (file created on prior commit)
- `frontend/src/lib/stacked-trend/types.ts` — Zod schema widening (paired per [/memories/lessons.md 2026-05-16](memories/lessons.md) #1 backend↔frontend pairing rule)

**Data / artifact regen** (2)
- [datasets/taxonomy/indicators.json](datasets/taxonomy/indicators.json) — `$schema_version` 1.0 → 1.1; `topic_tags` populated on all 59 rows (30 elections + 29 energy)
- [datasets/taxonomy/indicators.parquet](datasets/taxonomy/indicators.parquet) — regen against 33-col DDL

**Backend tests** (new in prior commit; 30 tests)
- `backend/tests/test_indicators_seed.py` widening — pairing rule, DDL col count, Pydantic acceptance
- `backend/tests/test_validate_alias_window.py` (new) — 60-day window edge cases, no-op on missing catalogue, test-pin via `today=` param

**Frontend tests** (new in prior commit; 23 tests)
- `frontend/src/lib/indicator-catalogue.test.ts` (new)
- additions to `src/contracts/datasets-conform.test.ts` for v1.1 envelope

**Doc / process** (this session, 3)
- [CLAUDE.md](CLAUDE.md) — §10 two new anti-pattern bullets (`id_aliases` pairing rule + topic-prefix-forbidden rule)
- [TODO/20260517-canonical-long-format-pivot.md](TODO/20260517-canonical-long-format-pivot.md) — row T.3 status bumped to READY-MERGE-AFTER-P.1.A with reason text
- [TODO/20260522-t3-ready-blocked-on-p1a-handover.md](TODO/20260522-t3-ready-blocked-on-p1a-handover.md) — this doc

---

## 6. Next-agent action plan (after P.1.A merges)

When `feat/p1-energy-pivot` merges to `main` (currently no PR open; expected PR-route per repo convention):

```powershell
Set-Location c:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov
git fetch origin
git checkout feat/t3-indicator-catalogue-v1.1-topic-tags-and-aliases

# Rebase onto post-P.1.A main. Expected: clean rebase because
# T.3 only ADDS columns to indicators.json (topic_tags / id_aliases /
# deprecated_in); P.1.A only ADDS rows. No same-row collisions.
git rebase origin/main

# If conflicts appear on indicators.json (unexpected):
#   - resolve by KEEPING all rows from both sides
#   - re-populate topic_tags = ["energy"] on the 29 energy rows
#   - confirm indicator-catalogue.schema.json stays at v1.1
#   - re-run python -m yen_gov emit-taxonomy --root . to refresh parquet

# Force-push with explicit lease (per /memories/lessons.md 2026-05-22
# "force-push polish discovery" — needs user approval per CLAUDE.md §8)
git rev-parse origin/feat/t3-indicator-catalogue-v1.1-topic-tags-and-aliases
git push --force-with-lease=feat/t3-indicator-catalogue-v1.1-topic-tags-and-aliases:<that-sha> origin feat/t3-indicator-catalogue-v1.1-topic-tags-and-aliases

# Re-run all 4 gates on the rebased branch
cd backend; python -m pytest -q 2>&1 > pb-t3-rebased.log; Get-Content pb-t3-rebased.log -Tail 5
cd ..; python -m yen_gov validate --root . 2>&1 | Select-Object -Last 3
cd frontend; bun run test --run 2>&1 > ..\vt-t3-rebased.log; Get-Content ..\vt-t3-rebased.log -Tail 5

# §13 browser smoke (MANDATORY before merge — see Section 4 caveat)
cd ..\frontend; bun run dev   # in a background terminal
# In another terminal / browser: open localhost:5173/, /t/elections,
# /indicator/<one elections id> — confirm zero console errors, parquet load works

# Open PR
gh pr create --base main --head feat/t3-indicator-catalogue-v1.1-topic-tags-and-aliases --body-file pr-body.md
```

---

## 7. Gotchas / lessons re-confirmed this session

1. **Stash-led-summary trap (2026-05-22 top of /memories/lessons.md)** — the prior conversation's summary suggested Q1/Q2/Q3 were unanswered, but `/memories/session/plan.md` had them locked. Re-asking would have violated CLAUDE.md §0a "do not re-debate". `git branch --show-current` + `git status` at session start saved a re-ask round-trip.
2. **PowerShell pipeline buffering trap (re-confirmed ~6th time)** — `python -m pytest -q 2>&1 | Select-Object -Last 15` buffers ALL output until pytest exits; for a 199-second run that looks hung. Workaround held: `python -m pytest -q 2>&1 > pb-t3.log; Get-Content pb-t3.log -Tail 15`. Log file size grew incrementally; `Get-Item pb-t3.log` showed `Length` ticking up which proved progress.
3. **Stale-working-tree-on-wrong-branch** — at session start I was on `feat/p1-energy-pivot` with `M CLAUDE.md`. The diff was a REVERSAL (working tree was OLDER than HEAD), not new work. `git restore CLAUDE.md` cleared it safely. No T.3 work was in that stale diff.
4. **Rebase-onto-different-base risk** — T.3 commits sit on `feat/p1-energy-pivot`. Rebasing them onto `main` (which lacks P.1.A's 29-row append) is path 2 from §1 above — strictly worse than path 1. Documented explicitly here so the next agent doesn't take the shortcut.

---

## 8. Why not just merge T.3 to main as-is (without rebase)

A merge commit from T.3 → main would pull in **all of feat/p1-energy-pivot's C0-C3 commits** as part of the merge (because they're in T.3's ancestry and not in main's). That contaminates the T.3 PR scope with energy indicator catalogue rows, methodology breaks parquet, energy sources rows, etc. — the C4 PR (Energy lift adapter) would then have a much smaller diff because the prerequisites already landed via T.3.

Per CLAUDE.md §0a authority routing and the prior T.3 commit's explicit framing, T.3 ships **independently**. The clean separation requires P.1.A to merge first, then T.3 rebases.

---

**Authority for any T.3 decision after this point** (per CLAUDE.md §0a):
- Data shape (`topic_tags[]` denorm, `id_aliases[]` regex, alias window) → Hans + Max.
- Contract / Tier-B / paired-semantic gate → Gregor.
- Frontend dereferencer scope (when it lands per-family in P.*) → Jony + Citizen.
- Refactor / squash decision on the 3 T.3 commits at PR time → Fowler.

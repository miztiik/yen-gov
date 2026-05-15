# Catalogue drift detector

**Last Updated**: 2026-05-15

## What this is

A contract test, [`frontend/src/contracts/catalogue-coverage.test.ts`](../../../frontend/src/contracts/catalogue-coverage.test.ts), that fails the build whenever an indicator artifact under `datasets/indicators/in/` is on disk but neither wired into [`datasets/reference/in/topic-catalogue.json`](../../../datasets/reference/in/topic-catalogue.json) nor justified in [`frontend/src/contracts/catalogue-coverage.allowlist.json`](../../../frontend/src/contracts/catalogue-coverage.allowlist.json).

## Why it exists

The 2026-05-15 audit (see [`docs/reference/data-coverage-report.md`](../../reference/data-coverage-report.md) §6) found 41 of 80 indicator artifacts present on disk but unreachable from the IA. Every recent ingest (RBI Handbook splices, SRS health, NSO prices, transport EV) widened the gap; none of it was visible to a citizen.

Two roads from there:

1. **Convention.** "Reviewers should remember to wire new artifacts." Convention does not survive contributor turnover, batch ingests, or rebases.
2. **Ratchet.** A test that makes the gap concrete and forces every PR that adds an artifact to also decide its visibility — wire it OR explicitly defer it.

We took the ratchet. Holy Law #5 (structural fixes only): the underlying defect is "the IA does not enforce coverage of its own data layer," not "we forgot to wire some files."

## How it works

Three rules, enforced as separate `it()` blocks so failures point at the right defect:

1. **No silent orphans.** Every id in `datasets/indicators/in/**/*.json` (computed as `<category>/<basename-without-ext>`) must appear in `WIRED ∪ ALLOWED`.
2. **No stale allowlist.** Every entry in the allowlist must reference an artifact that still exists on disk. Renames and deletions force a follow-up edit.
3. **No double-listing.** An id is wired OR allowlisted, never both. Once wired, the allowlist entry is redundant and must be removed (the count of allowlisted ids is the gap; double-counting hides it).

A fourth rule — every allowlist entry has a non-empty `reason` — exists so the allowlist reads as a backlog, not a dumping ground.

## How to use it

Adding a new indicator artifact:

- **Citizen-facing now**: add an `{ "kind": "indicator", "id": "..." }` entry under the right topic in `topic-catalogue.json`. Done.
- **Not yet ready**: add `{ "id": "...", "reason": "..." }` to the allowlist. The reason is plain English; tag it with the phase from [`TODO/VIZ-LAYER-GAPS-PLAN.md`](../../../TODO/VIZ-LAYER-GAPS-PLAN.md) it is blocked on (e.g. `phase3-pending (new topic: prices): blocked on RebaseBanner (Phase 2)`).

Closing the gap:

- The success metric is "lines in the allowlist file going down over time." Phase 3 of the plan is mechanical: move ids from the allowlist into the catalogue, one topic at a time, each landing with its renderer guardrails already in place.

## Why an allowlist instead of just wiring everything

Some unwired artifacts are intentional:

- **Redundant ingests** kept on disk for diff-checking against newer splices (e.g. `state_per_capita_nsdp_current_inr` superseded by `_long`).
- **Honesty-blocked artifacts** that would mislead if rendered today (absolute ₹Cr health spending, vintage-spliced NSDP without break annotations, current-prices NSDP without snapshot badges). Wiring these without the Phase 1+2 honesty primitives would ship dishonest charts (Fowler yellow → red).

The allowlist makes the deferral visible and reviewable. "Why is this still unwired?" has an answer in the file, not in someone's head.

## What it does NOT do

- It does NOT validate the data — that is [`datasets-conform.test.ts`](../../../frontend/src/contracts/datasets-conform.test.ts) (CLAUDE.md §11 consumer side).
- It does NOT check that the catalogue itself is well-formed — that is the topic-catalogue schema test on the backend side.
- It does NOT cover non-indicator artifacts (events, boundaries, governments). Those have their own reachability paths and would deserve their own drift detectors if the same gap problem surfaced.

## See also

- [`TODO/VIZ-LAYER-GAPS-PLAN.md`](../../../TODO/VIZ-LAYER-GAPS-PLAN.md) — the phased plan this test is Phase 0 of.
- [`docs/reference/data-coverage-report.md`](../../reference/data-coverage-report.md) §6 — Fowler/Jony/Hans audit findings.
- [`docs/reference/data-inventory.md`](../../reference/data-inventory.md) §1Z — auto-generated inventory of the same unwired set.
- CLAUDE.md §15 — test-tier policy (this is a Tier 2 contract test).

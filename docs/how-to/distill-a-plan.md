# How to distill a plan-doc

**Last Updated**: 2026-05-30

The procedure for lifting durable findings out of a `TODO/<date>-<slug>.md` plan-doc into the right canonical home under `docs/`. The plan-doc is the work ledger; once a row closes, anything worth keeping past the merge belongs somewhere else.

Note the name-clash: [distill.md](distill.md) is a separate runbook for distilling a citizen question into a shipped answer (the 7-persona handoff). This doc is about plan-doc distillation only.

This doc exists because plan-docs were silently accumulating findings that the next agent had to rediscover. The fix is mechanical, not editorial: every closed row is examined for distillation candidates, each candidate is routed per [ADR-0034](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract), and the plan-doc is left as a thin audit ledger pointing at its distilled outputs.

## When to run

- After any plan-doc row closes (PR merged + status flipped to `Closed` / `Done`).
- Before declaring an entire plan-doc complete.
- When picking up a stale plan-doc and noticing it has grown rationale narrative that belongs elsewhere.

Do NOT run for in-flight rows. Distillation only happens after the finding has stabilised through merge.

## Inputs

- One closed plan-doc row + its `CLOSED` narrative sub-section (per the [ship-a-pr.md](ship-a-pr.md) 2-commit-then-squash stamp pattern).
- The merged commit SHA on `main` (for cross-reference).
- Read access to [ADR-0034](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract) — the doc-class routing contract.

## The routing decision

For each finding in the closed row's narrative, ask the questions in [ADR-0034](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract) §Decision rule order and route to ONE home:

| Finding shape | Destination | Example |
| --- | --- | --- |
| Decision with credible rejected alternatives + non-trivial reversal cost + cross-cuts subsystems | **Fold rationale into the relevant subsystem or concept doc** as new `## Design rationale` + `## Rejected alternatives` sections; cite via [docs/reference/decision-index.md](../reference/decision-index.md) | "Why is the canonical Parquet partition Hive-style?" → [ADR-0030](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) (folded receipt in canonical-store.md) |
| Current shape / layout / contract of one subsystem | **Subsystem doc** under `docs/architecture/<area>/<slug>.md` | "How does the frontend join geojson to election results?" → [docs/architecture/frontend/map.md](../architecture/frontend/map.md) |
| Vocabulary term used in multiple subsystems | **Concept doc** under `docs/concepts/<slug>.md` | "What is the meadow tier?" → [docs/concepts/meadow-tier.md](../concepts/meadow-tier.md) |
| Operator runbook / step-by-step procedure | **How-to doc** under `docs/how-to/<verb>-<slug>.md` | "How do I ship a PR?" → [ship-a-pr.md](ship-a-pr.md) |
| Agent-only execution lesson (gotcha, recurring trap, tool quirk) | **`/memories/lessons.md`** (memory tool) | "`bun run test` not `test:run` in this repo"; "23rd cosmetic gh-merge confirmation" |
| Per-PR audit trail | **Stays in the plan-doc `CLOSED` sub-section** | Diff stat, gate results, discoveries specific to this PR's execution |

If a finding fits two destinations, pick the more durable one (ADR > subsystem > concept > how-to > lesson). If it fits none, it probably is not durable — leave it in the plan-doc `CLOSED` sub-section and move on.

## What to distill, what to leave

### Distill

- New invariants the PR established (e.g. "every observation row carries `source_id`")
- New decision rationale + the rejected alternatives the PR's discussion ruled out
- New citizen-facing copy or behaviour rules ("all entities render on the map at true geographic location")
- New vocabulary the PR introduced or sharpened
- New operator procedures the PR exposed gaps in

### Leave in the plan-doc

- The diff stat, the gate results, the merge commit SHA, the cosmetic-error counter — these are per-PR execution context, not durable knowledge.
- "Discovery" notes that are PR-specific framing of a finding that has already been distilled. The distilled doc is the source of truth; the plan-doc points to it.
- Anything that was distilled by an earlier PR in the same plan. Do not re-distill.

### Leave nowhere (delete from the plan-doc on close)

- In-flight TODO bullets the row resolved.
- Speculative scope-expansion sketches that did not ship.
- Stacked "previous header" status blocks (forbidden by [ADR-0034](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract) §single-snapshot-header).

## The mechanics

### Step 1 — read the closed `CLOSED` sub-section

For row `X.Y` in plan-doc `TODO/<date>-<slug>.md`, the merge commit landed a sub-section titled `#### X.Y - CLOSED YYYY-MM-DD (PR #NNN)`. List its discoveries, findings, and audit notes.

### Step 2 — route each finding

For each finding, apply the routing table above. Open the target doc; add the finding in the doc's existing tone and structure (do not paste plan-doc prose verbatim — the plan-doc was action-narrative; the target is reference).

### Step 3 — back-reference

In the plan-doc `CLOSED` sub-section, replace the finding's full text with a one-line pointer:

```
- Finding 1: [now-canonical title](../docs/concepts/<slug>.md) — distilled from this PR.
```

This preserves the audit trail (someone reading the plan-doc later sees what was discovered + where it lives now) without duplicating the content.

### Step 4 — agent-only lessons go to `/memories/lessons.md`

Use the memory tool. Findings that are about *how to do agent work* (PR-shipping gotchas, command-line quirks, parallelisation traps, recurring failure modes) belong in user memory, not in `docs/`. The line is: `docs/` is for project knowledge a citizen-engineer would read; `/memories/lessons.md` is for agent execution craft.

### Step 5 — declare the plan-doc closed

When the last live row closes, append a final block:

```
## Plan complete

Closed YYYY-MM-DD. All rows merged. Distillation complete:
- Row X.Y → [target](path)
- Row X.Z → [target](path)
- ...

Plan-doc remains as the audit ledger; do not edit further. New work starts a new plan-doc.
```

Do NOT delete the plan-doc. It is the durable record of what was tried, in what order, by which PR — a tree-ring artifact. The distilled findings are the live knowledge; the plan-doc is the history of how they came to be.

## Anti-patterns

- **Plan-doc as the only home for a finding.** A future agent searching `docs/` for the topic will not find the plan-doc; plan-docs are not browseable knowledge. If the finding is durable, lift it to `docs/`.
- **Re-distillation in a later PR.** Once a finding is in `docs/`, later PRs that touch the same area edit the doc directly. Do not re-lift the same finding from a new plan-doc.
- **Distilling speculation.** Only distill what shipped. A "considered approach we did not take" goes in the ADR's Rejected alternatives section, not in subsystem docs or concept docs.
- **Editorial bloat in the lifted doc.** The target doc gets a sentence or two, not the plan-doc's full narrative. If the lifted text is longer than the doc it joins, you are pasting, not distilling.
- **Skipping the back-reference step.** Without the pointer, the plan-doc reads like the finding vanished. The pointer is a one-liner; do it.

## See also

- [ADR-0034](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract) — the four-class doc routing contract
- [ship-a-pr.md](ship-a-pr.md) — the PR lifecycle whose `CLOSED` sub-sections are this runbook's input
- [CLAUDE.md](../../CLAUDE.md) §5 (Documentation Discipline) — the rules every distilled doc must honour
- [docs/reference/documentation-structure.md](../reference/documentation-structure.md) — the Diataxis tier definitions

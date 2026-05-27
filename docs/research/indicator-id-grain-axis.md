# Indicator-id grain axis — Path A vs Path B

**Last Updated**: 2026-05-26
**Status**: RESOLVED-Path-B-rip-and-replace (see [ADR-0044](../architecture/decisions/0044-grain-over-entity.md), 2026-05-26)
**Subject**: should `indicator_id` encode entity-grain as a prefix (`state-`, `district-`, `ac-`), or should one `indicator_id` carry rows at multiple grains discriminated by the row's `entity_kind`?

> **Resolution (2026-05-26)** — Path B is adopted via [ADR-0044](../architecture/decisions/0044-grain-over-entity.md), rip-and-replace per user mandate. No expand–migrate–contract; one-shot DuckDB CTAS migration per family under `tools/migrate/path_b_<family>.py`. Tier-B `tier_b_indicator_id_no_grain_prefix` rejects new ids with grain prefixes (dark in PR-B1, enforced in PR-B9 of [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](../../docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md)). This note is preserved as the costed comparison that informed the decision.

> **Routing note** — this is a research note (input), not a decision (ADR). Per [ADR-0034](../architecture/decisions/0034-documentation-routing-contract.md), data-shape decisions need an ADR with Hans + Max sign-off (per CLAUDE.md §0a authority table). This note captures Jony + Fowler subagent verdicts gathered 2026-05-25 (B.04 of the livestock NDLM 9-PR sprint) so that future Hans + Max can decide from a costed comparison rather than re-discovering the trade-offs.

## 1. Question

Two siblings landed in PR #281 + PR #284 + PR #287 of the livestock NDLM sprint:

- `agriculture/state-pashu-aadhaar-animals-tagged-count` (state-grain SUM rollup)
- `agriculture/district-pashu-aadhaar-count-cattle` (district-grain SoT, first species)

Both id strings begin with an entity-grain prefix (`state-` / `district-`). The same pattern repeats across 77 of 77 catalogue rows today (verified 2026-05-25): `state-`, `district-`, `national-`, `ac-`, `candidate-`, `party-`. The catalogue currently treats `(grain × measure)` pairs as **two distinct ids**.

**Path A** (current convention, codified in [`docs/concepts/indicator-naming.md`](../concepts/indicator-naming.md) §2.2): keep the entity prefix; ship state and district as siblings.

**Path B** (proposed retirement, OWID-aligned): drop the entity prefix from the id; ship ONE id per measure (`agriculture/pashu-aadhaar-animals-tagged-count`); the renderer dispatches on the row's `entity_kind`.

## 2. Candidates

### Path A — entity-prefix-in-id (status quo)

| Field | Value |
| --- | --- |
| Convention doc | [`docs/concepts/indicator-naming.md`](../concepts/indicator-naming.md) §2.2 |
| OWID alignment | Deviates from OWID convention (OWID treats entity as a row dimension, not a slug component) |
| Citizen surface | `indicator_id` appears on **2 surfaces**: [`DataCompleteness.svelte`](../../frontend/src/routes/DataCompleteness.svelte) (dim/monospace power-user disclosure) + `/compare?i=<id>` query-string. Title is what citizens read everywhere else. |
| Catalogue rows today | 77 of 77 follow this pattern |
| Sibling-pair clarity | Two rows per measure × grain; explicit but verbose |
| URL grammar | Stable. `/compare?i=state-X` and `/compare?i=district-X` are distinct shareable URLs. |

### Path B — entity-prefix-stripped (proposed)

| Field | Value |
| --- | --- |
| Convention doc | Would supersede §2.2 |
| OWID alignment | Aligns with OWID precedent — entity is a row dimension; id names the measure |
| Citizen surface | Unchanged — citizens never read the raw id; the title carries the grain (e.g. "Cattle tagged with Pashu Aadhaar (state)") |
| Catalogue rows touched | ~10–12 pair migrations (district + state siblings: pashu-aadhaar × 11 species, future livestock duals). Election-grain pairs (`ac-` vs `state-` vs `candidate-`) are NOT candidates — they are genuinely different facts per OWID one-noun rule. |
| Sibling-pair clarity | One row per measure; grain dispatched by renderer |
| URL grammar | `/compare?i=<id>` would alias old → new for 60 days via `id_aliases[]` mechanism (schema v1.1) |
| Mechanism | Needs `id_aliases[]` + `deprecated_in` + dual-emit at the canonical writer during the window |

## 3. Verdicts

### 3.1 Jony (UX) — 2026-05-25

> "Defer to Hans + Max + Gregor on the architectural call; indicator-id is invisible to the citizen on every primary surface, so the UX frame does not break the tie. My UX-side bias is **Path B IF B.05 ships 'one grain-aware component'**; otherwise Path A."

Key findings:

- **Citizen visibility evidence**: indicator-id appears on exactly **2 surfaces** — [`DataCompleteness.svelte:172-173`](../../frontend/src/routes/DataCompleteness.svelte) (small, dim, monospace; power-user honesty page) and the `/compare?i=<id>` query-string (no path-slug usage). Everywhere else, the citizen reads `meta.title`, never `meta.id`.
- **OWID alignment finding**: "yen-gov has already taken one named OWID divergence on geography ([ADR-0028](../architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) — geography goes in URL path, not query) because the audience case is 'my place first.' Stacking a second divergence ('entity ALSO goes in indicator-id') earns its keep only if a citizen-facing reason exists. None does."
- **Refusal**: if Path A continues, the existing sibling-pair name asymmetry (`state-pashu-aadhaar-count-cattle` shipped per-species in B.03, while the plan reserves `state-pashu-aadhaar-animals-tagged-count` per-aadhaar-count) MUST be repaired — asymmetric Path A forfeits its only argument.

### 3.2 Fowler (Engineering) — 2026-05-25

> "Defer the Path-A → Path-B decision; do NOT block the 9-PR livestock sprint on it. Per-pair migration cost is bounded (alias mechanism is per-pair, not per-family). Shipping PR 5/6/7 in Path A adds ~9 more Path-A ids; that's bounded."

Cost estimate (per Fowler):

| Surface | Path A → Path B effort |
| --- | --- |
| [`datasets/taxonomy/indicators.json`](../../datasets/taxonomy/indicators.json) | ~12 catalogue edits (per-pair alias rows) across 2 PRs |
| [`datasets/taxonomy/topics.json`](../../datasets/taxonomy/topics.json) | ~10 artifact entries collapse 2 → 1 |
| [`frontend/src/lib/canonical/indicator-allowlist.ts`](../../frontend/src/lib/canonical/indicator-allowlist.ts) | New `kind: "multi-grain"` descriptor variant + ~12 entry rewrites + 1 type-system change |
| [`frontend/src/lib/canonical/indicator-from-canonical.test.ts`](../../frontend/src/lib/canonical/indicator-from-canonical.test.ts) | ~25 SQL-fragment assertion rewrites + multi-grain coverage |
| [`backend/yen_gov/canonical/adapters/`](../../backend/yen_gov/canonical/adapters/) | ~10–15 `indicator_id="..."` string-literal edits across 5 adapter files |
| **Observation parquet rows** (load-bearing) | THE real cost. Two options: (a) dual-emit during 60-day window (cheap revert; doubles disk for 60 days), or (b) rewrite-in-place (cheaper disk; higher reversibility cost). |

**Scope level**: Level-5 per CLAUDE.md §6. Touches canonical-row PK + observation-row logical key + frontend allowlist + backend adapter write seam + is upstream of the B.05 renderer decision. Cross-cutting; non-trivial reversal; needs an ADR.

**Migration mechanism viability**: `id_aliases[]` + 60-day `deprecated_in` (schema v1.1) is **necessary but not sufficient** — it handles read-side dereferencing but does NOT migrate persisted observation-row `indicator_id` values. Needs a paired dual-emit strategy at the canonical writer (Beck/Sadalage expand-migrate-contract).

**Reversibility**: asymmetric. Dual-emit path (Fowler's recommended option) keeps revert cost at Level-2/3. Rewrite-in-place locks revert at Level-4+ (full-corpus regen).

**Decomposition (if Path B is later chosen)**: 6 sub-PRs (S+S+B+B+S+D), each Level-3 or below, all green at the gate:

1. **(S)** Add `kind: "multi-grain"` descriptor variant + unit tests; zero entries use it yet
2. **(S)** Add `derive_entity_kind_from_entity_id()` helper + 8-row unit table; no callers yet
3. **(B)** Pilot Path B on ONE indicator-pair (pashu-aadhaar parent) with dual-write + alias + topic mount + §13 smoke
4. **(B)** Roll Path B to remaining ~10 pair candidates (one PR per indicator-family)
5. **(S)** Add Tier-B test `tier_b_indicator_alias_window` exercising real-world `deprecated_in` rows
6. **(D)** After 60-day window, contract step: delete legacy `state-*` and `district-*` rows + drop dual-emit + delete legacy SQL-fragment assertions

## 4. Recommendation

**Recommendation for the deferred Hans + Max consult: ratify Path A for the duration of the 9-PR livestock NDLM sprint; reopen via ADR-0044 post-sprint.**

Rationale (synthesis of both verdicts):

1. **Sequencing**: Jony's B.05 verdict (two stacked cards; refuse state↔district toggle) implies the renderer wants two distinct descriptors, which Path A naturally provides. Path A continues to fit the citizen-surface shape.
2. **Bounded cost**: Fowler's per-pair alias mechanism means future Path A → Path B cost is roughly constant per indicator-pair regardless of how many sprint PRs ship first. The cost-of-delay penalty is small.
3. **Authority**: per CLAUDE.md §0a, data-shape decisions belong to Hans + Max. This note + a paired ADR draft is the right input for that decision; neither Jony nor Fowler can pre-empt it.
4. **One asymmetry to repair if Path A is ratified**: rename `state-pashu-aadhaar-count-cattle` (B.03) to symmetric form with its sibling, OR rename `state-pashu-aadhaar-animals-tagged-count` (the plan-reserved id) to match. Asymmetric Path A is the worst of both worlds.

## 5. Open follow-ups

1. **Hans + Max consult to mint ADR-0044** ("Indicator-id naming: Path A keep vs Path B retire"). Inputs: this note + Fowler's 6-PR decomposition + Jony's UX finding.
2. **If Path B is later ratified**: execute Fowler's expand-migrate-contract decomposition (6 sub-PRs).
3. **If Path A is ratified**: repair the `state-pashu-aadhaar-count-cattle` vs `state-pashu-aadhaar-animals-tagged-count` asymmetry; codify the "per-species suffix" rule explicitly in `indicator-naming.md` §2.5.

## 6. References

- [CLAUDE.md](../../CLAUDE.md) §0a (authority table — data-shape = Hans + Max), §6 (correction levels), §10 (anti-patterns)
- [docs/concepts/indicator-naming.md](../concepts/indicator-naming.md) §2.2 + §8 anti-pattern #2
- [docs/concepts/owid-alignment.md](../concepts/owid-alignment.md) (table row 2: indicator id = internal namespace, not citizen surface)
- [docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md](../architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) (existing named OWID divergence on geography)
- [docs/architecture/decisions/0034-documentation-routing-contract.md](../architecture/decisions/0034-documentation-routing-contract.md) (research note vs ADR routing)
- [docs/architecture/decisions/0043-auto-rollup-at-canonical-write-time.md](../architecture/decisions/0043-auto-rollup-at-canonical-write-time.md) (write-time multi-grain auto-rollup that triggered this question)
- [datasets/schemas/indicator-catalogue.schema.json](../../datasets/schemas/indicator-catalogue.schema.json) v1.1 (`id_aliases[]` + `deprecated_in` migration mechanism)
- PRs #281, #284, #287 (the three sprint PRs that landed the first state + district sibling pair)
- Source: Jony + Fowler subagent verdicts gathered 2026-05-25 during B.04 of the livestock NDLM 9-PR sprint

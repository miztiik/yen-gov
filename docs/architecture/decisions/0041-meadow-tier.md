# ADR-0041 — Meadow tier: parsed publisher rows as canonical input

**Last Updated**: 2026-05-25
**Status**: Accepted
**Deciders**: User (autonomous mandate, 2026-05-25) + Hans (Governance) + Max (Indicator Scout) + Gregor (Architect) — parallel custom-agent consult 2026-05-25; all three personas converged on Strategy F (Gregor's framing). Authority assignment per CLAUDE.md §0a: data shape = Hans + Max; integration topology = Gregor.
**Supersedes**: nothing. **Refines**: [ADR-0030 D1/D10/D13](0030-canonical-store-duckdb-wasm.md) (canonical store position) and the `meadow-shard-contract.txt` allowlist contract (semantics changed from "countdown to retirement" → "perimeter for canonical-input contract"; file rename deferred to PR 7c-4).
**Plan reference**: [`TODO/20260517-canonical-long-format-pivot.md` §0e.8a + §0e.8b](../../../TODO/20260517-canonical-long-format-pivot.md). On conflict THE PLAN wins and this ADR is amended.

## Context

### What this resolves

By 2026-05-24 the canonical-pivot strangler-fig (ADR-0030) had landed Phase A (canonical writer) and Phase B (frontend allowlist routing to canonical Parquet) for the energy family, but Phase D (`git rm` of the legacy JSON shards under `datasets/indicators/in/<topic>/<id>.json`) was blocked. The blocker: backend canonical adapters under `backend/yen_gov/canonical/adapters/energy/*.py` still read the same shards as **primary input** via `_shared.load_shard()`. The contract at [`datasets/_ops/meadow-shard-contract.txt`](../../../datasets/_ops/meadow-shard-contract.txt) lines 23-26 said the family's Phase-D `git rm` MUST land in the same Tier-A commit as the canonical pivot — but PR 7a (the energy canonical-writer landing) wired adapters to read shards instead of dropping the dependency. Strategy C never happened.

A new lesson (2026-05-25, `/memories/lessons.md`) captured the trap: a "Phase B frontend reader-switch" does NOT imply "backend can drop the shard." Per-adapter Phase-C must be verified before any Phase-D `git rm` is scoped. User chose Fowler's Option 2 (per-adapter Phase-C, 3-4 small PRs, clean architecture not band-aid). This ADR ratifies the structural decision that follows.

### "The One Rule" (CLAUDE.md §0a) — OWID precedent

OWID's ETL pipeline has FIVE tiers, named explicitly:

```
upstream → snapshots (ephemeral) → meadow (parsed, committed) → garden (curated) → grapher (frontend)
```

yen-gov already had four of those tiers without naming the third. The shards under `datasets/indicators/in/<topic>/<id>.json` are the meadow tier: typed, schema-validated, deterministic, `source_id` FK-bearing, parsed from upstream but pre-canonical (sub-fuel collapse, methodology splices, canonical-axis joins all happen downstream in the canonical adapter, not in the shard). The shard's role is **identical** to OWID's `etl/meadow/`. yen-gov mislabelled it "legacy folded-indicator" and put it at a path (`datasets/indicators/in/`) that looked citizen-facing.

Per §0a "The One Rule" — when OWID has solved a question, adopt verbatim. The meadow tier was the missing vocabulary.

### Pre-pivot defect

The misleading path created three structural problems:

1. **3-way node ambiguity**. The same shard file was: (a) ingest adapter's output, (b) canonical adapter's input, (c) deprecated frontend reader's input. No structural separation between roles.
2. **Phase-C blast-radius trap**. Removing the shard breaks (b) silently; the only signal is the next `replace_partition` lift emitting an empty Parquet.
3. **Naming precision**. "indicator artifact" can mean many things; "meadow" is OWID's exact term for this grain.

## Decision

### Promote shards to a named meadow tier

Rename `datasets/indicators/in/<topic>/<id>.json` → `datasets/<family>/_meadow/<source>/<vintage>/<file>.json`.

- `<family>`: indicator family (`energy`, `demography`, `fiscal`, `health`, …) — matches the canonical Parquet family name.
- `<source>`: short producer identifier (`rbi`, `cea`, `iced`, `eci`, `nfhs`, …).
- `<vintage>`: matches the `vintage` field on the citation-ledger row in `datasets/taxonomy/sources.parquet` (per [ADR-0032](0032-sources-citation-ledger.md)).
- `<file>`: descriptor (e.g. `installed_capacity.json`).

Example: `datasets/energy/_meadow/rbi/2024-25/hbk_table_142_peak_demand.json`.

### Meadow-tier contract (one paragraph per guarantee)

1. **Schema-validated**: typed JSON conforming to an existing per-family schema under `datasets/schemas/`. No new schemas added by this ADR; reuses what shards already validate against.
2. **Deterministic**: identical upstream bytes → identical meadow file bytes on re-run. No `datetime.now()` in content (CLAUDE.md §10).
3. **Provenance**: every observation row in the meadow file carries a `source_id` FK to `datasets/taxonomy/sources.parquet` per §12 + [ADR-0032](0032-sources-citation-ledger.md).
4. **Backend-internal**: frontend MUST NOT `fetch()` meadow paths. Enforced by (a) `_meadow/` underscore-prefix per CLAUDE.md §2 ("private" convention); (b) new CLAUDE.md §4 layer rule; (c) Tier-B validator gate (renamed in PR 7c-4); (d) Phase B allowlist routes all citizen reads to canonical Parquet — legacy `fetch('/data/indicators/in/...')` URLs 404 after rename.

### Migration sequence (5 PRs — supersedes the original single PR 7c)

| PR | Adapter | Shards | Scope |
| :-: | --- | :-: | --- |
| **7c-0 (this PR)** | none | 0 | Docs only: ADR-0041 + concept doc + CLAUDE.md §4/§10 + canonical-store.md §2 amend. |
| **7c-1** | `generation.py` | 2 | Introduce `load_meadow()` helper in `_shared.py`; `git mv` 2 ICED-gen shards to `_meadow/iced/<vintage>/`; allowlist + smoke. |
| **7c-2** | `distribution.py` | 6 | Same pattern; reuse `load_meadow()`. Parallel-safe with 7c-3. |
| **7c-3** | `demand_supply.py` | 7 | Same pattern; PR #174 inline-literal block stays. |
| **7c-4** | `installed_capacity.py` | 8 | Same pattern + finalisation: retire `load_shard()`; rename `datasets/_ops/meadow-shard-contract.txt` → `meadow-shard-contract.txt`; rewrite header semantics ("perimeter" not "countdown"); delete empty `datasets/indicators/in/energy/`. |

### Forcing function (why the rename is structural, not cosmetic)

Each per-adapter `git mv` simultaneously does three things in one commit:

1. **Repoints the backend canonical adapter** (Phase C — adapter reads `_meadow/` not legacy path).
2. **Breaks any legacy frontend `fetch('/data/indicators/in/<topic>/<id>.json')` URL** → forces Phase B allowlist completion (404 if any consumer missed migration; C5 work).
3. **Deletes the old path** (Phase D, completed atomically per slice).

This collapses what was previously "Phase C / C5 / Phase D = three separate PRs each potentially deferred" into one observable structural action per adapter. The PR 7c blocker dissolves because the question "drop shard dependency how?" is reframed as "rename shard to honest path."

### Completion criterion

`datasets/indicators/in/` does not exist on `main`. Single observable: `git ls-tree origin/main -- datasets/indicators/in/` returns empty. No countdown, no allowlist size count, no docstring inspection.

## Rationale

The Hans+Max+Gregor 2026-05-25 consult surfaced 5 candidate strategies (a/b/c/d/e in their initial framing) and converged on a 6th — Strategy F — that Gregor named the "meadow tier rename." F is the only strategy that:

1. Names a layer that already exists (no new abstraction).
2. Has a structural forcing function (`git mv` simultaneously closes Phase C + Phase D + Phase B remainder).
3. Generalises to Phase 2 P.2+ (~10 more families, ~80+ more meadow shards) without per-family debate.
4. Adopts OWID precedent verbatim per §0a "The One Rule."
5. Adds zero new schemas.
6. Has a single-query completion criterion.

## Rejected Alternatives

### A — Inline-literal rewrite (Gregor's initial framing)

Adapter embeds shard rows as Python list literals; shard deletes.

**Rejected because** at PR #174's 34-row scale this worked (FY25 ICED peak-demand supplement) and a reviewer could eyeball the diff. Energy shards carry **1,815 / 1,685 / 712 / 396 / 374 / 555 rows** ([installed_capacity.py:91-100](../../../backend/yen_gov/canonical/adapters/energy/installed_capacity.py#L91-L100) etc). A 1,815-row Python tuple is anti-auditable: no reviewer can confirm "Tamil Nadu coal FY20 = X" against publisher PDF by reading source code. Hans non-negotiable #4: no inline literal beyond ~100 rows.

**Reversal cost**: high (need to re-derive thousands of rows from upstream snapshots after each adapter PR). **Verdict**: acceptable for ≤100-row supplements; not for primary inputs.

### B — Upstream-direct re-fetch at lift time

Adapter calls publisher API at lift; shard deletes.

**Rejected because** kills lift determinism (ADR-0030 D7 UPSERT contract; Holy Law re-run byte-stability). Network at lift breaks CI reproducibility and fresh-checkout reliability. Even the "`.runtime/raw/` cached snapshot as input" variant is blocked: CLAUDE.md §2 forbids committed code referencing `.runtime/` paths; ICED endpoints have moved twice in this project's lifetime; RBI republishes Handbook tables every fiscal with subtle revisions. Provenance becomes only as strong as upstream availability.

**Reversal cost**: not reversible (lost determinism is permanent contract erosion). **Verdict**: structurally forbidden.

### C — Reframe shards as canonical-input contract IN PLACE (Hans's initial proposal)

Keep shards at `datasets/indicators/in/<topic>/<id>.json`; amend allowlist header + CLAUDE.md §10 to declare them "permanent canonical-input layer"; rename `_ops/meadow-shard-contract.txt` → `_ops/canonical-input-shards.txt`.

**Rejected because** the path lie persists: `datasets/indicators/in/` reads as citizen-facing even after the rename. Tier-B validator becomes ceremony ("permanent allowlist" never shrinks). No forcing function for Phase B allowlist completion: the legacy `fetch('/data/indicators/in/...')` URL still works after the rename, so any consumer that missed migration keeps reading the shard silently. Phase 2 P.2+ contributors learning the project would see `datasets/indicators/in/` and assume citizen-readable status, then have to be told the convention reversed.

**Reversal cost**: medium (renaming again to F's shape is straightforward but each path-typo gets cited in docs). **Verdict**: preserves what's wrong about the current state.

### D — Promote `.runtime/raw/<source>/` to `datasets/_raw/<source>/` (Max's α)

Commit upstream byte-faithful snapshots (encrypted ICED bodies, RBI XLS bytes); adapter re-parses at lift; shards delete.

**Rejected because** Max picked the wrong OWID tier — `etl/snapshots/` is bytes-in-git (HTML/PDF archives), orthogonal to meadow. yen-gov already HAS the meadow tier (typed, parsed); promoting `.runtime/raw/` adds a NEW layer at high repo-size cost (estimated ~550 MB ICED alone across 11 FYs of encrypted blobs). Repository scale is already a concern (CLAUDE.md §10 anti-patterns). Doubling the pre-canonical layer defeats the canonical-pivot's file-system clarity goal. Also: re-parsing every lift makes the lift cycle-time linear in upstream byte size, not in meadow row count.

**Reversal cost**: high (repo-size growth is hard to undo without `git filter-repo` rewrites). **Verdict**: wrong tier; meadow already exists.

### E — Hybrid (ingest writes meadow + canonical simultaneously)

Ingest adapter knows canonical shape; writes both meadow and canonical Parquet directly.

**Rejected because** collapses the Message Translator pattern (ADR-0030 D20 — Canonical Data Model). Ingest now needs canonical schema awareness; future canonical-shape changes ripple back into every ingest adapter. Erases the layer separation that makes per-family schema evolution safe.

**Reversal cost**: very high (re-introducing the canonical adapter layer mid-flight). **Verdict**: structurally inverts the pipes-and-filters topology.

## Consequences

### Wins

- **Phase-C blocker dissolves per-adapter** via the `git mv` forcing function.
- **Phase B allowlist completion is structurally enforced** — legacy URLs 404 after rename; no slow-decaying coverage gaps.
- **5-tier OWID topology named explicitly** — future contributors find the layer by name, not by archaeology.
- **Zero new schemas** — reuses existing per-family JSON schemas that adapters already validate against.
- **Tier-B fence becomes a perimeter** (canonical-input contract: every `_meadow/` file deterministic, schema-valid, `source_id` FK closed) instead of a countdown to retirement.
- **Single observable completion criterion**: `datasets/indicators/in/` does not exist on `main`.
- **Phase 2 P.2+ adopts meadow-tier authoring from day one** — no per-family Phase-C debate.

### Costs

- **5 sequential PRs** to migrate the energy family (7c-0 through 7c-4) instead of one. Mitigated: each PR is small, reviewable, reversible; the forcing function makes each PR's success criteria observable.
- **`load_meadow()` helper coexists with `load_shard()` during the transition** (between 7c-1 and 7c-4). Mitigated: Gregor non-negotiable #5 — 7c-4 retires `load_shard()` atomically; no half-state on `main`.
- **CLAUDE.md §4 + §10 amendments** load onto an already-dense root contract. Mitigated: §4 gets one new bullet; §10 amends one existing entry's first sentence and adds an ADR-0041 link.

### Non-negotiables (Gregor + Hans, ratified by user 2026-05-25)

1. No backend writes outside `datasets/<family>/_meadow/<source>/<vintage>/` for staging.
2. CLAUDE.md §4 layer rule MUST land in 7c-0 (this PR) — otherwise F slips into a 3-way node within months.
3. No network at lift, ever; `.runtime/raw/` stays gitignored ephemeral.
4. Vintage in meadow path MUST match `vintage` field of the citation row the `source_id` FK resolves to. (Tier-B check, added in PR 7c-4.) **Structurally enforced** since PR-B (ADR-0042) by `tier_b_meadow_vintage_matches_source_id` in `backend/yen_gov/validate.py`: for every file under `datasets/<family>/_meadow/<source>/<vintage>/*.json`, the rule walks `MEADOW_PRODUCER_REGISTRY` to resolve `<source>` → full producer and asserts at least one row in `datasets/taxonomy/sources.parquet` exists with that `(producer, vintage)` pair. The rule was unenforceable before ADR-0042 because v2.0 of the source schema allowed `vintage=""`, defeating strict equality (multiple meadow files could share a single `vintage=""` citation row).
5. Sequencing: 7c-1 introduces `load_meadow`; 7c-4 retires `load_shard` atomically.
6. No editorial creep into 7c-N PRs — each PR is structural rename + adapter switch + allowlist + smoke only.
7. Methodology breaks (RBI Table 140 ↔ 142 splice, UDAY effect, CEA fuel-classification changes) render visibly on the chart, not just as a `methodology_breaks.parquet` row. (Hans non-negotiable — strategy-independent.)

## References

- **OWID `etl/meadow/`** — reference implementation of the meadow tier (https://github.com/owid/etl)
- **CLAUDE.md §0a** — "The One Rule" (OWID as canonical reference)
- **CLAUDE.md §4** — Layer & Dependency Rules (backend-internal meadow constraint, added in this PR)
- **CLAUDE.md §10** — Anti-patterns (meadow path enforcement, amended in this PR)
- **[ADR-0030](0030-canonical-store-duckdb-wasm.md) D1 / D7 / D20** — canonical Parquet position, UPSERT determinism, Canonical Data Model
- **[ADR-0032](0032-sources-citation-ledger.md)** — sources citation ledger (meadow rows carry same `source_id` FK as canonical observations)
- **[ADR-0034](0034-documentation-routing-contract.md)** — doc-class routing contract (this ADR qualifies per dual test: credible rejected alternative + cross-cutting)
- **[`docs/concepts/meadow-tier.md`](../../concepts/meadow-tier.md)** — meadow vocabulary + topology (defined once, linked from everywhere)
- **[`docs/architecture/data/canonical-store.md`](../data/canonical-store.md) §2b.5** — per-family directory invariant amended to include `_meadow/`
- **[`TODO/20260517-canonical-long-format-pivot.md` §0e.8a + §0e.8b](../../../TODO/20260517-canonical-long-format-pivot.md)** — pending-work tracker + Strategy F ratification
- **`/memories/lessons.md` 2026-05-25** — strangler-fig blast-radius trap (PR 7c discovery that motivated this ADR)

# ADR-0034 — Documentation routing contract (four doc classes)

**Status**: Accepted
**Date**: 2026-05-22
**Deciders**: User (autonomous mandate, this session) + Gregor (Architect, parallel custom-agent dispatch) + Fowler (Engineering, parallel custom-agent dispatch). Both agents converged on the same shape; Gregor framed the contract, Fowler proposed the lift mechanics.

## Context

By 2026-05-22 the project had four kinds of documents on disk, each carrying architectural rationale, and **no defined contract for which kind of doc owns what kind of statement**:

1. **CLAUDE.md** (root engineering contract; Holy Laws + non-negotiables).
2. **ADRs** under `docs/architecture/decisions/` (24 numbered, 0002–0033).
3. **Subsystem docs** under `docs/architecture/<area>/` (e.g. `data/canonical-store.md`, `frontend/data-loading.md`).
4. **Concept docs** under `docs/concepts/` (vocabulary — `data-provenance.md`, `indicator-naming.md`, `owid-alignment.md`, etc.).
5. **Plan-docs** under `TODO/` (active work plans).

The result was an 895-line plan-doc (`docs/archive/plans/20260517-canonical-long-format-pivot.md`, 204 KB) that mixed:

- A "One Rule" pointer (duplicated in `CLAUDE.md §0a`).
- 36 numbered "decisions" D1–D36 (all already verbatim in `ADR-0030`).
- 31 numbered "rejected alternatives" R1–R31 (also in `ADR-0030`).
- Phase-status narrative for already-shipped work (Phase 0, Phase 1.8a–1.8f, T.0a, T.0a-ii, T.0b, T.0c, T.1, T.2, G.1.a/b/c).
- Three stacked "previous header" layers contradicting each other on whether Phase 2 = Energy or Phase 2 = NFHS-5.
- Active plan rows (the actual reason a plan-doc exists).

Without a routing rule the same decision lived in 3–4 places, drifted between them, and produced the contradiction the user surfaced on 2026-05-22 ("the plan has become extremely messy"). Per CLAUDE.md Holy Law #4, design rationale is documented next to the code it justifies; but if every doc class can carry rationale, "next to" stops being meaningful and the system loses its single-source-of-truth property.

The same drift had already produced one near-miss: `docs/architecture/data/canonical-store.md` grew to 828 lines and started absorbing both the canonical disk-layout spec AND the indicator-catalogue spec AND the sources-ledger spec — three orthogonal axes that change for different reasons. Without a routing rule the next subsystem doc would have done the same.

## Decision

Adopt a **four-class routing contract** for every architectural statement in the repository. Each doc class has exactly one audience, one mutability rule, one allowed content type, and one forbidden-content rule.

| Class | Path pattern | Audience | Mutability | Contains | Forbidden |
| --- | --- | --- | --- | --- | --- |
| **ADR** | `docs/architecture/decisions/NNNN-*.md` | Future agent debugging *why* | Immutable once Accepted (Status field flips: Proposed → Accepted → Superseded-by-NNNN) | One decision + rejected alternatives + reversal cost + consequences | Implementation detail; current-state snapshot; status updates beyond the Status field |
| **Subsystem doc** | `docs/architecture/<area>/*.md` | Engineer building or extending the subsystem | Living snapshot (edit in place) | Shape, disk layout, contracts, naming conventions, invariants, write/read paths | Rationale prose; rejected alternatives narrative |
| **Concept doc** | `docs/concepts/*.md` | Anyone learning project vocabulary | Living, terse | One term, defined once, with cross-links | Duplication of any term defined elsewhere |
| **Plan-doc** | `TODO/<YYYY-MM-DD>-<slug>.md` | Next person picking up work | Single-snapshot (no stacked headers) | Phase status, active PR breakdown, TBD list, pointers | Rationale prose; decisions; rejected alternatives |

### Routing rules (derive a new statement's home)

1. **Does it have a credible rejected alternative with non-trivial reversal cost AND cross-cut multiple subsystems?** → New ADR (per the README.md bar that already existed).
2. **Is it the current shape/layout/contract of one subsystem?** → Subsystem doc under `docs/architecture/<area>/`. **Cite the ADR for rationale; do not restate it.**
3. **Is it a vocabulary term used in multiple subsystems?** → Concept doc under `docs/concepts/`. Defined once, linked from everywhere else.
4. **Is it "which PRs land when"?** → Plan-doc in `TODO/`. **Cite both ADR and subsystem doc; carry no rationale.**

### Single-snapshot header rule (plan-docs)

A plan-doc's top is exactly one block:

```
# <title>
**Last Updated**: YYYY-MM-DD
**Status**: <one paragraph: phase X complete, phase Y active (PRs N.a–N.d), phase Z next>
```

Previous status text is **deleted** at every phase boundary. History lives in `git blame` and merge-commit titles. Stacked "previous header" layers are a band-aid for missing snapshot semantics and forbidden by CLAUDE.md §5 (band-aids are forbidden).

### Cross-doc consistency mechanism

- **ADRs are source-of-truth events.** Once Accepted, the decision text is immutable; only the Status field changes.
- **Subsystem docs link UP to the ADR(s) that birthed each invariant.** Format: `**ADR**: [ADR-NNNN](../decisions/NNNN-*.md)` near the top, plus inline `(per ADR-NNNN)` for specific clauses.
- **Plan-docs link ACROSS to both.** Format: `**Spec**: [canonical-store.md](...)`, `**Decision rationale**: [ADR-0030](...)`.
- **Concept docs link LATERALLY to other concept docs and DOWN to the subsystem docs that operationalise them.**

### What this ADR consciously does NOT do

- Does NOT create a CI gate that asserts every ADR is referenced by ≥1 subsystem doc. That gate is plausible future work but adds enforcement complexity for a discipline that fits in this routing table.
- Does NOT split `docs/architecture/data/canonical-store.md` into the three sibling docs Gregor recommended (canonical-store + indicator-catalogue + sources-ledger). That split is a Tidy-First follow-up; this ADR records the routing rule that justifies it when next edited.
- Does NOT impose retroactive ADR-per-decision splits. ADR-0030 currently bundles D1–D36 as Groups 1–11; that bundling is correct because the decisions are facets of one coherent canonical-store choice. Future cross-cutting decisions get their own ADR; existing bundles stay.

## Consequences

### Good

- A new architectural statement has exactly one valid home. Reviewers can reject a PR that puts rationale in the plan-doc or invariants in an ADR.
- The 895-line plan-doc can be slimmed to ~140 lines without information loss because every D# already lives in ADR-0030 and every R# is a "Rejected alternatives" entry there.
- Future doc drift is bounded: when invariant X changes, exactly one subsystem doc updates; when a decision is revisited, exactly one ADR supersedes.
- The stacked-header anti-pattern is named and forbidden by rule, not just by taste.

### Bad

- Adds one more thing to remember at PR time ("which doc class does this belong in?"). Mitigation: the four-row table is short and the rules are mechanical.
- Splits the friendly habit of "drop a paragraph of context at the top of the plan." Reviewers may push rationale into commit messages instead — acceptable; commit messages are git's event log, parallel to ADRs.
- Subsystem docs become drier (no rationale narrative). Mitigation: the rationale is one click away via the ADR back-reference.

## Alternatives considered (rejected)

### A — Status quo, write-anywhere

Continue letting any doc class carry rationale, status, invariants, vocabulary. Cheap to continue.

**Rejected** because it produced the 895-line plan-doc and the canonical-store.md 828-line drift in exactly four months. No mechanism prevents the same accretion happening again on the next family pivot.

### B — Collapse to ADRs + concept docs only (drop subsystem docs as a class)

Treat `docs/architecture/<area>/` as a thin index that points to ADRs; put all current-state content in ADRs.

**Rejected** because ADRs are timestamped event logs and citizen-store invariants change living-document-style. "What is the current Parquet disk layout" is a snapshot question; forcing readers to reconstruct the snapshot from a chain of `superseded-by-NNNN` ADRs adds load every time someone joins the project. Subsystem docs ARE the snapshot; ADRs are the why-chain that produced it.

### C — One ADR per D#/R# from the plan-doc (33 + 31 = 64 new ADRs)

Take Fowler's "should every D# become its own ADR" and answer yes. Split ADR-0030's Groups 1–11 into 36 numbered ADRs.

**Rejected** as speculative generality (Fowler's word). D1–D36 are facets of one coherent canonical-store decision; splitting them fragments the rationale narrative ADR-0030 already tells coherently. The bar for ADR creation (README.md, restated above as Rule 1) requires a credible rejected alternative AND cross-cutting scope. Most D# entries have neither — they are operational consequences of the canonical-store choice, not independent decisions.

### D — Move rationale into git commit messages exclusively, retire the ADR class

Use `git log` as the architectural decision register; eliminate `docs/architecture/decisions/` entirely.

**Rejected** because commit messages are not browseable by topic, do not survive squash-merges intact in many workflows, and require a git checkout to read. ADRs are content-addressable by number, browseable in any file tree viewer, and stable across history rewrites. Git's event log and the ADR event log serve overlapping but distinct audiences; both stay.

## Doc impact (this ADR's required edits, landed in the same commit)

- **[CLAUDE.md §5](../../../CLAUDE.md)** — append the routing-rule paragraph and the single-snapshot header rule. Note that subsystem docs cite ADRs without restating.
- **[docs/reference/documentation-structure.md §7](../../reference/documentation-structure.md)** — add §7.6 "Doc-class routing contract" with the four-row table. The bootstrap-standard previously said "Diataxis tiers" and "one concept defined once" but did not name the mutability axis; this addition names it.
- **[docs/architecture/decisions/README.md](README.md)** — append a one-line pointer to this ADR for the "when is a new ADR appropriate" rule.

## Follow-up (NOT in this ADR's commit)

- **Lift §0e.4 from `docs/archive/plans/20260517-canonical-long-format-pivot.md` into a new `docs/concepts/topic-taxonomy.md`** — vocabulary for the 17 topic slugs.
- **Lift §0e.5 (persons fork) into a new ADR-0035** — credible rejected alternative (Option A "smallest reversible step"), cross-cuts elections + governments families.
- **Archive `§6` (Phase 0 audit narrative) and `§7` (Phase 1 deletion sweep narrative) into `docs/archive/`** — executed work history, not active plan.
- **Slim `docs/archive/plans/20260517-canonical-long-format-pivot.md` to ~140 lines** — pure phase ledger + active phase + Phase 3 sketch.
- **Retire `TODO/20260522-phase-2-p1-nfhs-5-planning.md` into `docs/archive/`** — was based on the wrong-phase assumption (Phase 2 = NFHS-5 instead of Phase 2 = Energy); content is preserved for the eventual NFHS-5 P.\* row.
- **Replace it with a fresh `docs/archive/plans/20260522-phase-2-p1-energy-pivot.md`** — small, focused, current.
- **Future Tidy-First**: split `docs/architecture/data/canonical-store.md` (828 lines) into `canonical-store.md` (disk layout, read/write paths, ~250 lines) + `indicator-catalogue.md` (~200 lines) + `sources-ledger.md` (~150 lines) + `taxonomy.md` (~100 lines). Track as a marker in canonical-store.md; execute when the doc is next substantively edited.

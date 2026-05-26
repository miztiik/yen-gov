# ADR-0044: Grain-over-entity for `indicator_id` (rip-and-replace)

**Last Updated**: 2026-05-26
**Status**: Accepted
**Deciders**: User (autonomous mandate, 2026-05-26 — "Move grain to OWID-style grain-over-entity. Stop smooshing state + district + village into one chart; create sub-pages.") + Hans + Max (data shape, per CLAUDE.md §0a) + Gregor (contract seam) + Jony (UX surface).
**Supersedes**: [docs/concepts/indicator-naming.md](../../concepts/indicator-naming.md) §2.2 ("entity-prefix mandatory") + §2.4 ("when to include `state_` / `district_` / `national_`"). Both sections are rewritten in the same commit as this ADR lands.
**Resolves**: [docs/research/indicator-id-grain-axis.md](../../research/indicator-id-grain-axis.md) Path A vs Path B — Path B selected.
**Plan reference**: [TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md](../../../TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md) PR-A1.

## Context

`indicator_id` today encodes the entity-grain as a leading slug segment: `state-pashu-aadhaar-count-cattle` and `district-pashu-aadhaar-count-cattle` are the same concept measured at two grains, but the catalogue stores them as two rows, two allowlist entries, and two topic-page cards. As of 2026-05-26 the canonical catalogue carries 121 rows; 77 of them lead with `state-` / `district-` / `national-` / `ac-` / `candidate-` / `party-`. The first three are entity-grain prefixes; the last three are fact-grain prefixes (different observation grains, not different entity grains) and stay.

OWID, the World Bank, the IMF, the FAO and the UN Statistical Division converge on a different convention: **one `Variable` per `(concept, unit, normalisation)`; the entity rides on the row, dispatched by the renderer.** See [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) and OWID's `etl/data_helpers/geo.py` for the precedent. yen-gov's prior position (Path A, "entity-prefix mandatory") was a localism. The cost of maintaining the localism is paid every time a sub-state-grain family lands: two ids, two cards, two test bodies, two AGENTS.md notes, and an "expand–migrate–contract" rename runbook to climb back out (per the old [docs/concepts/indicator-naming.md](../../concepts/indicator-naming.md) §7).

The accumulated debt is now visible: `/t/agriculture` ships 18 stacked species cards because 11 species × 2 grains were each minted as separate ids. PR #281 + PR #284 + PR #287 + PR #304 each had to fan out per-species ids and re-author per-species caveats. The pattern is going to repeat across livestock owner-reg (14 ids), NAIP-IV (8 ids), every future sub-state-grain ingest.

Three options were considered (rehashed from the research note):

- **α — keep Path A; build dispatcher tooling.** Cheap today, expensive every PR. Rejected.
- **β — Path B with expand–migrate–contract aliases (60-day deprecation window).** OWID-aligned eventually; pays a 60-day double-bookkeeping cost per family. Rejected: user mandate is "rip-and-replace, no strangler-fig" (2026-05-26); everything is in git, revert via `git revert <sha>` if a smoke gate fails.
- **γ — Path B, rip-and-replace, one PR per family with a one-shot DuckDB CTAS migration script committed under `tools/migrate/`.** **Accepted.**

## Decision

**`indicator_id` MUST NOT encode the entity-grain.** The grain is a property of the OBSERVATION ROW, carried by `entity_id` and surfaced through the indicator-catalogue's new `entity_kinds: array<enum["country","state","district","ac"]>` field (added in PR-B1) + `default_entity_kind: enum` field. The renderer dispatches the chart shape from the row's `entity_kind`, not from the id slug.

### Concrete grammar

Old (Path A):

```
state-pashu-aadhaar-count
district-pashu-aadhaar-count
state-pashu-aadhaar-count-cattle
district-pashu-aadhaar-count-cattle
state-installed-capacity-mw
state-installed-capacity-coal-mw
national-installed-capacity-mw
national-installed-capacity-coal-mw
```

New (Path B):

```
pashu-aadhaar-count                    # entity_kinds: [state, district];   species facet on the row
installed-capacity-mw                  # entity_kinds: [country, state];    fuel facet on the row
```

The id is `<noun>-<aggregate?>-<unit?>-<facet?>` kebab-case. The leading `<entity_prefix>-` segment is **deleted**, not made optional — the regex on the catalogue schema (PR-B1) rejects ids that start with `state-` / `district-` / `national-`. Fact-grain prefixes (`ac-`, `candidate-`, `party-`) are NOT entity-grain prefixes and stay.

### What rides where

| Property | Where it lives |
| --- | --- |
| What is being measured (concept) | `indicator_id` noun |
| Unit | `indicator_id` unit suffix + catalogue `unit` field |
| Normalisation (raw / per-capita / per-area / share) | `indicator_id` (per-capita / share is part of identity per OWID rule O1) |
| **Entity grain (country / state / district / subdistrict / village)** | **`observation.entity_id` + `indicator.entity_kinds[]` + `indicator.default_entity_kind`** |
| Facet (species / fuel / sector) | `observation.<facet_col>` (one column per facet axis) + catalogue `facet_axes` |
| Vintage | `observation.source_id` + `sources.parquet.vintage` |
| Methodology break | `methodology_breaks.parquet` row keyed on same `indicator_id` |
| Render shape (chart_type, default_mode, renderer_rules, facet_labels, dimension) | Grapher catalogue at `datasets/grapher/` per ADR-0045 |

### Renderer dispatch

The frontend reads each observation row's `entity_kind` and picks the renderer per grain. `IndicatorChoropleth.svelte`'s current `entity_kind === "state"` constraint (lines 8-11) is removed in PR-C1; the component dispatches to the right boundary layer (state / district / subdistrict / village) from the row, not from a per-id allowlist.

### Identity test (OWID-aligned, replaces the §2.4 default-geography test)

Before minting a new `indicator_id`, every author MUST answer YES to ALL of:

1. Is the **concept** different from every concept in `datasets/taxonomy/concepts.json`?
2. Is the **unit** different from the closest concept-match?
3. Is the **normalisation** different (raw / per-capita / per-area / share / index)?

If all 3 are YES, mint a new id. If any answer is NO, UPSERT into the existing id OR add a facet axis. **Entity-kind is NOT an identity axis.** Same concept at country + state + district is ONE id with `entity_kinds: ["country","state","district"]` and rows distinguished by `entity_id`. The 4th identity question used in earlier drafts ("is the entity_kind different?") is explicitly retired by this ADR.

## Consequences

**Positive:**

- Catalogue row count drops by ~60% in livestock + energy + economy + fiscal blocks (standing reference table in the plan-doc §2 enumerates the collapses: 77 → ~16 rows in those families).
- Topic pages stop stacking grain-cards (the `/t/agriculture` 18-card mess is closed by PR-C2).
- Citizen explorer surfaces `/i/<indicator>` and `/i/<indicator>/<grain>` (PR-C1) become possible.
- Aligns yen-gov with OWID / World Bank / IMF / FAO precedent on indicator identity (OWID Variable model).
- One caveat array per measure instead of one per (measure × grain × facet) — Hans-curated bullets stop fragmenting.

**Negative:**

- The rename is a hard cutover. Every observation parquet under `datasets/<family>/**.parquet` carrying a `state-` / `district-` / `national-` `indicator_id` MUST be rewritten by a one-shot DuckDB CTAS committed under `tools/migrate/path_b_<family>.py`. Reverted via `git revert <sha>` if any smoke gate fails.
- `/compare?i=state-X` and `/compare?i=district-X` URLs in any existing bookmarks 404 — there is no alias window. Per CLAUDE.md §0ter standing limit, the citizen-route SMOKE gate must show a working successor URL (`/compare?i=X` and a `/i/X` explorer surface from PR-C1) before each Phase B PR merges. Bookmarks ARE allowed to 404 — the standing limit covers in-app routes, not external bookmarks.
- The frontend allowlist must learn to project a per-grain descriptor from a single catalogue row. Tooling change is in PR-A3b + PR-C1.
- The §8 anti-pattern list in `docs/concepts/indicator-naming.md` is reworked — anti-pattern #2 (the `india_` vs `national_` collision) flips from "soft style drift" to "MUST NOT prefix grain on id, full stop."

**Permanent guardrails** (shipped in PR-Z1 + PR-Z3 alongside this ADR; each enforced by a Tier-B check):

- Guardrail #1: `indicator_id` MUST NOT start with `state-` / `district-` / `national-`. Enforced by `tier_b_indicator_id_no_grain_prefix` in [backend/yen_gov/validate.py](../../../backend/yen_gov/validate.py) (dark in PR-B1, enforced in PR-B9).
- Guardrail #13: new ingest MUST FK to a row in `datasets/taxonomy/concepts.json` declaring `(concept, unit, normalisation, entity_kind)`. Two indicators with the same 4-tuple are rejected by `tier_b_one_indicator_per_concept`.
- Guardrail #16: `tier_b_facet_promotion_warning` flags per-fuel / per-species id proliferation (≥3 siblings differing only in one slug segment).
- Guardrail #19: methodology break = same id + `methodology_breaks.parquet` row, NEVER a renamed id (Rosling rule, mirrors ADR-0042).

## Migration sequence

Per the plan-doc Phase B (PR-B1 through PR-B9):

1. **PR-B1** ships schema v2.0 with `entity_kinds` + `default_entity_kind`, retires `id_aliases` + `deprecated_in`, adds dark `tier_b_indicator_id_no_grain_prefix`.
2. **PR-B2 through PR-B8** rip per family (elections / energy / livestock / economy / fiscal / prices). Each ships a `tools/migrate/path_b_<family>.py` CTAS and refreshes the parity oracle.
3. **PR-B9** chains the Tier-B check into `run()`. After PR-B9 merges, the rip is permanent.

## Cross-refs

- [ADR-0030](0030-canonical-store-duckdb-wasm.md) — canonical store; entity dispatch lives in DuckDB-WASM.
- [ADR-0034](0034-documentation-routing-contract.md) — this is a cross-cutting ADR (multiple subsystems affected, non-trivial reversal cost), routed per §3.
- [ADR-0043](0043-auto-rollup-at-canonical-write-time.md) — sub-state-grain rollup; `derivation="sum"` rows under one id at multiple grains is exactly the shape this ADR depends on.
- [ADR-0045](0045-grapher-catalogue-split.md) — companion: render fields move from canonical catalogue to grapher catalogue.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) — Variable / Origin / Dataset model; this ADR closes the prior divergence row.
- [docs/concepts/indicator-naming.md](../../concepts/indicator-naming.md) — §2.2 + §2.4 rewritten in the same commit as this ADR; §8 anti-pattern #2 promoted to MUST-NOT.
- [docs/research/indicator-id-grain-axis.md](../../research/indicator-id-grain-axis.md) — status flips from `deferred` to `RESOLVED-Path-B-rip-and-replace`.

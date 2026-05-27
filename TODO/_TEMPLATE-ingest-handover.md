# [DATE] [SOURCE] ingest handover

**Last Updated**: YYYY-MM-DD

> Template for new-source ingest handover docs. Copy to `TODO/YYYYMMDD-<source>-ingest-handover.md` (or `-plan.md`) and fill in. Every section below is MANDATORY. The §"Concept overlap audit" section is load-bearing per [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](../docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md) §0quat guardrail #14 and is enforced by reviewer convention until a Tier-B check is wired.

## 1. Source

- **Publisher**: <authority + URL>
- **Vintage / cadence**: <e.g. annual FY release; monthly CY release; ad hoc>
- **License**: <link>
- **Sampling frame / methodology**: <frame, base year, deflator, etc.>

## 2. Scope

- **Concept(s) measured**: <noun(s) being measured, e.g. "installed electricity generating capacity">
- **Unit canonical**: <e.g. `MW`, `INR_crore`, `pct`>
- **Normalisation**: <one of `absolute` / `per_capita` / `per_area` / `share` / `ratio` / `index`>
- **Entity grain(s)**: <country / state / district / ac / party / candidate — list all that apply>
- **Time range**: <FY start - FY end>

## 3. Concept overlap audit (MANDATORY — guardrail #14 + ADR-0046)

> Before authoring any new `indicator_id`, run [`python -m yen_gov pre-flight-ingest`](../backend/yen_gov/preflight/__init__.py) (ADR-0046) and cite the report path below. The gate batches the six mechanical checks (concept overlap, concept FK, grain prefix, update_period_days, justification, source_id derivation) into one call. Exit code 2 = abort; correct the proposal and re-run. No override flag per CLAUDE.md Holy Law #5.

Drop a proposal JSON next to this handover-doc as `./proposal.json`, then run:

```bash
python -m yen_gov pre-flight-ingest \
  --proposal-file ./proposal.json \
  --report        ./report.json
```

(The legacy `python -m yen_gov check-overlap` CLI is still available and is invoked internally by the pre-flight gate as check #1, but new handover-docs MUST use the batched gate so the verdict for ALL six checks is captured in one report.)

Cite the results below:

- **Proposal**: [proposal.json](./proposal.json)
- **Report**: [report.json](./report.json)
- **Verdict**: <one of `mint_new` / `upsert` / `add_facet`>
- **Target indicator_id** (if not `mint_new`): `<family>/<existing-id>`
- **Exit code**: <0 pass / 1 soft-warn>

**Verdict** (per concept):

- [ ] `<concept noun>` -> `mint_new` (no match >= 0.70; new id authored is `<family>/<measure>-<unit>-<facet>`)
- [ ] `<concept noun>` -> `add_facet` on existing id `<family>/<existing-id>` (matched >= 0.70 on noun + unit + normalisation; new rows carry an additional `facet` value)
- [ ] `<concept noun>` -> `upsert` into existing id `<family>/<existing-id>` (matched >= 0.85 across all 4 axes; this ingest is a new vintage / publisher of the SAME fact)

If `mint_new`, also confirm:

- [ ] A row exists (or is added in this PR) in [datasets/taxonomy/concepts.json](../datasets/taxonomy/concepts.json) declaring `(noun, unit_canonical, normalisation, entity_kinds[])` for the new concept. The new `indicator_id` MUST FK to that `concept_id` via `meta.concept_id`.
- [ ] `meta.justification` on the new indicator row names the dimension that distinguishes it from the nearest existing concept (e.g. "different sampling frame: ECI booth-level vs CEO state aggregate").

## 4. Identifiers

- **`indicator_id`**: `<family>/<measure>-<unit>-<facet>` (kebab-case; NO `<grain>-` prefix per [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md); grain lives on each row's `entity_kind`).
- **`concept_id`**: <FK to `datasets/taxonomy/concepts.json`>
- **`source_id`**: derived via `backend.yen_gov.canonical.citation.derive_source_id` (never hand-author per CLAUDE.md §12).
- **`update_period_days`**: <publisher refresh cadence in days, e.g. 365 for annual, 30 for monthly — required per guardrail #18>

## 5. Pipeline plan

- **Meadow tier**: `datasets/<family>/_meadow/<source>/<vintage>/<file>.json` (per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md))
- **Canonical adapter**: <module path>
- **Schemas**: <list any new / bumped schemas under `datasets/schemas/`>
- **Tier-A tests**: <list>
- **Tier-B impact**: <name any new validators or which existing ones must continue to pass>

## 6. Acceptance gates

- [ ] G1 `python -m yen_gov validate --root .` OK
- [ ] G2 `pytest -q` green (targeted module + downstream readers)
- [ ] G3 `bun run check` (frontend) 0 errors
- [ ] G4 `bun run test` (vitest) green
- [ ] G5 `/s/<state>/t/<topic>` browser smoke per CLAUDE.md §13 (if frontend route affected)

## 7. Open questions

- <questions for Hans / Max / Gregor>

## 8. References

- [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](../docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md)
- [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md) grain over entity
- [ADR-0045](../docs/architecture/decisions/0045-grapher-catalogue-split.md) grapher catalogue split
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md)
- [docs/concepts/indicator-naming.md](../docs/concepts/indicator-naming.md)

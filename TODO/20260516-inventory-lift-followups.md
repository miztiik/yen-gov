# Inventory lift follow-ups (post-ADR-0026)

**Created**: 2026-05-16
**Status**: deferred backlog
**Parent work**: PR #7 (commit `07e33b3`) — schema v3.0 → v4.0, ADR-0026, completed and merged.

> **FROZEN — do not re-execute the ADR-0026 work.** The lift of
> `collection_inventory` and `series_spec.expected_*` out of the
> indicator artifact already shipped in PR #7 (merged
> commit `07e33b3` on `main`). The full 1052-line design plan that
> drove it has been decomposed into [ADR-0026](../docs/architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md),
> [`docs/concepts/folded-indicator.md`](../docs/concepts/folded-indicator.md),
> [`docs/concepts/collection-inventory.md`](../docs/concepts/collection-inventory.md),
> the v4.0 schema changelog, and the backend `AGENTS.md`. This file is
> the residue: items that were explicitly deferred OR that were on the
> v4 commit slate (§16.2 of the now-deleted plan) but skipped because
> they were strictly behavioural follow-ons, not preconditions for the
> schema lift.

The lessons learned from the design + execution are in
`/memories/lessons.md` (entries dated 2026-05-16 and 2026-05-17).
The 11 rejected design alternatives are archived inside ADR-0026
itself; don't re-propose them.

---

## Deferred items (none are blockers)

Each item has a one-line rationale for why it didn't ship in PR #7.
None are urgent. Pick them up one at a time; each is a small,
independent PR.

### A. Behavioural follow-ons from the v4 slate

1. **Refresh-shape guard at `write_artifact`.** Detect drift in
   `(indicator.id, entity_kind, time_grain, direction, comparability,
   attribution_geography, denominator-shape, set(rows[].entity_id),
   set(rows[].time), facet_names, unit, value_kind, columns)` between
   the new and prior artifact. On divergence, refuse the write and
   append a row to `docs/reference/refresh-report.md`. CLI prints
   summary at end of run. — *Skipped because the dict-equal skip
   (shipped) already prevents the most common smear; the shape guard
   is a stricter belt-and-suspenders layer.*
2. **Per-adapter Option B `fetched_at` derivation.** Where the
   publisher exposes `Last-Modified` or content has a clear release
   vintage (CEA filenames, RBI doc footers, data.gov.in OGD), derive
   `fetched_at` from that — never from wall-clock. Start with CEA +
   RBI + data.gov.in OGD; other adapters fall through to the
   dict-equal skip. — *Skipped because dict-equal already eliminates
   the smear in practice; Option B is an honesty upgrade per adapter.*
3. **ICED `datetime.now()` migration.** Roughly 10 sites in
   `backend/yen_gov/sources/iced_*/` still take `now()` into emit
   content. Migrate each to cache-mtime (matches
   `datagovin_ogd/ingest.py` pattern in repo today). Becomes moot for
   any ICED endpoint covered by item 2.
4. **Wire `refetch_requested`.** Admin POST endpoint to flip the
   operator-state flag; collector adapters read the flag at start of
   run and clear it on successful re-collect. Today the field is
   read-only status.

### B. UI follow-ons

5. **`<CoverageVerdict>` component.** ~40-line Svelte renderer per
   the verbal-verdict table archived in ADR-0026 §"UI verdicts"
   (citizen-facing sentences like "On our backlog — published by
   {publisher}, not yet collected on yen-gov."). Reads
   `indicators-completeness.json`. — *Skipped because removing the
   Coverage block from `AboutThisData.svelte` (shipped) left the
   citizen surface coherent enough to defer the replacement.*
6. **Admin Indicators panel.** Read `indicators-completeness.json`;
   pair with item 4's write endpoint for operator-state edits. — *Read
   only is enough for v1; design conversation deferred.*

### C. Hygiene / cosmetic

7. **Lift methodology + series_spec content into each adapter's
   `INDICATOR_META`.** Today every adapter still relies on
   `_maintain_folded_blocks`'s prior-on-disk fallback in
   `backend/yen_gov/core/io.py` to preserve the migration-seeded
   content. The fallback is safe under v4.0 (the dict-equal skip
   keeps re-runs idempotent), but the cleaner home is the adapter
   itself. Touch ~15-20 ingest.py files.
8. **AST guard `tests/test_no_runtime_llm.py`.** ~30 lines that
   forbids `openai`, `anthropic`, `llama_index`, etc. imports anywhere
   under `backend/yen_gov/` outside `tools/`. Codifies the "no LLM in
   build step" doctrine.
9. **`.runtime/` → `.operator_cache/<source>/` split.** Separate
   raw-cache from operator telemetry. Update `CLAUDE.md` §3 and
   ADR-0003 in the same commit.
10. **Doc-generator schema-version interpolation rip.** Remove
    `f"v{schema_version}"` patterns from
    `backend/yen_gov/coverage_indicator_pages.py`; regenerate the 110
    `docs/reference/indicators/**` files once. Otherwise every schema
    bump churns 110 doc citations.
11. **`CLAUDE.md` §10 amendment.** Document the dict-equal carve-out
    at the `write_artifact` seam and note that ADR-0026 removed the
    upstream sin's main propagation path.

### D. Pre-existing deferred items (not introduced by ADR-0026)

These were on the original plan's §13 list and remain non-goals for
now. Listed here so the next agent doesn't re-discover them.

12. **Adapter `source_capability.available_periods[]` declaration.**
    Strangler-fig phase 2 of three-way intersection. The schema today
    has no `expected_periods` to intersect against; this item is
    contingent on a different design conversation about how (or
    whether) yen-gov should declare publisher commitments at all. See
    ADR-0026's discussion of why v4.0 removed the publisher-promise
    tier.
13. **Frontend cross-indicator comparison display convention.** When
    a chart pulls from multiple indicators with different
    publisher-label vocabularies, display the indicator's `frequency`
    rather than the per-row `label`. Frontend ADR-level decision; no
    schema change.
14. **Max's divergence-band methodology.** Schema reserves
    `divergence: null` in v4.0. Methodology + band thresholds authored
    in a follow-on PR.
15. **Unified `collect <indicator>` CLI wrapper.** Per-source
    `ingest-*` typer commands keep their names. Wrapper deferred until
    an indicator-keyed planner UI lands.
16. **Renaming per-source CLI commands.** Out of scope; high churn
    risk; cosmetic.
17. **Elections-as-indicators.** Elections live under
    `datasets/elections/` with their own model. Folding them into the
    indicator schema is a separate design conversation.
18. **`tools/` directory consolidation.** ~50 scripts with mixed
    quality. Triage and consolidation deferred.
19. **CEA xlsx ingest redesign.** Operator-drops-xlsx workflow under
    `.runtime/raw/cea/` preserved as-is. If xlsx lost, operator
    re-downloads from CEA portal.
20. **Global `coverage.py` rollup output replacement.**
    [`docs/reference/data-inventory.md`](../docs/reference/data-inventory.md)
    survives unchanged. Future PR may replace with view-time
    aggregation of `indicators-completeness.json`.
21. **Issue-template for citizen-reported data errors.** Mentioned in
    `Disclaimer.svelte` copy ("File an issue"); template setup
    deferred.

---

## Where to read instead of relitigating

- **Why we lifted** — [ADR-0026](../docs/architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md).
  Includes the 11-row "rejected designs" archive and the
  "what didn't fit / what did" discussion.
- **What the artifact looks like now** —
  [`docs/concepts/folded-indicator.md`](../docs/concepts/folded-indicator.md)
  (v4.0 top-level keys + glossary).
- **How `indicators-completeness.json` + `indicators-operator-state.json`
  work together** —
  [`docs/concepts/collection-inventory.md`](../docs/concepts/collection-inventory.md).
- **What lessons came out of all of it** —
  `/memories/lessons.md` entries dated 2026-05-16 (ADR-0026 lift) and
  2026-05-17 (original folded-indicator design loop).
- **Provenance rules that survived unchanged** —
  [`docs/concepts/data-provenance.md`](../docs/concepts/data-provenance.md).

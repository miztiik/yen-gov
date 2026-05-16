# `series_spec.expected_geographies` / `expected_periods` audit — synthesis

**Date**: 2026-05-16
**Branch context**: PR #6 (`feature/folded-indicator-inventory`) shipped folded v3.0; this report feeds the NEXT PR.
**Convened personas**: Fowler (Engineering), Hans (Governance), Max (Indicator Scout).
**Prompt**: User pushback — "Nuclear isn't in every state; coal/iron/marine fisheries have irregular publisher universes; expected×observed gap math creates phantom pending entries that will NEVER resolve. The fields smell."

## Verdict (all three personas converged)

| Field | Verdict | Action |
| --- | --- | --- |
| `series_spec.expected_geographies` | **REMOVE in v4.0** (via MAKE-OPTIONAL v3.1) | Universe = `distinct(rows[].entity_id) ∪ structured_unavailable_entities`. No declared expected list. |
| `series_spec.expected_periods` | **KEEP — but only when load-bearing** | Retain ONLY when `expected_periods_inference.basis ∈ {authored_from_publisher_catalogue, authored_from_source_schedule}`. Drop `seeded_from_observed_rows` as a valid basis. |
| `collection_inventory.pending_periods` | **Keep, fix the math** | Period-only set diff (`expected − observed − unavailable_keys`). Drop the geography cross-product entirely. |

No persona voted KEEP-AS-IS. No persona voted DEFER. The convergence was independent — they ran in parallel without seeing each other.

## Why all three agree

**Fowler (engineering / contract-fit)**: One consumer of `expected_geographies` exists ([frontend/src/lib/AboutThisData.svelte#L102](frontend/src/lib/AboutThisData.svelte#L102)), reads `.length` only, fully recoverable from `distinct(rows[].entity_id)`. Same audit that just deleted `universes.json` (zero consumers) applies recursively. Field is a self-fulfilling prophecy — auto-seeded from rows, then compared against rows ([backend/yen_gov/inventory/derive.py#L175-L184](backend/yen_gov/inventory/derive.py#L175-L184)). Tautology dressed up as a contract.

**Hans (governance / citizen)**: Phantom-pending entries trigger the Rosling **gap instinct** AND **generalisation instinct**, training citizens and journalists to read "yen-gov hasn't done its job for Goa" when the truth is "NPCIL has never published a Goa number and never will." When ~30–40% of Indian sector indicators are constitutionally-universal (population, GSDP, fiscal transfers, NFHS, UDISE) and ~60–70% are publisher-bounded (nuclear, coal, marine fisheries, major ports, mining royalties), forcing the same `expected_geographies` shape on both is a category error. The "publisher's reporting universe" is the right denominator; "all 36 states" is an invented one.

**Max (catalogue / OWID lens)**: OWID maintains zero per-variable `expected_countries` and zero per-variable `expected_years` manifests across thousands of indicators. The universe a chart shows IS the universe the source publishes; missing entities are handled in one-sentence prose footnotes ("Data only available for endemic countries"), not enumerated counterfactual lists. Cadence ("Annual", "Updated every 2-3 years") lives at source-level, surfaced as derived `(observed_max, source_cadence)` on the chart header. The cross-product gap is editorial debt that scales linearly with the catalogue (200+ indicators planned for yen-gov) and pays back only at the spine.

## Convergent reframing — three independent statements of the same shape

| Persona | Phrasing |
| --- | --- |
| Fowler | "Replace Field with Derivation: geography count comes from `rows[]`, not a declared field. Strangler-fig v3.1 → v4.0." |
| Hans | "REFRAME-AS-NEGATIVE-SPACE: universe of the indicator becomes `observed ∪ unavailable` — both sides citizen-readable, both grounded in something the publisher actually said or didn't say." |
| Max | "ADOPT-OWID-PATTERN: default behaviour, universe = observed entities. Keep `expected_geographies` ONLY for the small set where the publisher genuinely promises 'all states, every period'." |

## Proposed plan (NEXT PR, not this one)

This PR (#6, folded-indicator-inventory) ships the structural wins it set out to ship — schema fold, collection_inventory, universes decomposition, About/Disclaimer/AboutThisData/admin Indicators — and merges as-is. The audit feeds a follow-up arc.

### Commit sequence for the follow-up PR

1. **structural** — schema v3.1 (additive, minor): make `series_spec.expected_geographies` optional; add `$comment` directing authors not to add new ones; add `seeded_from_observed_rows` to a `x-deprecated` list in `expected_periods_inference.basis`.
2. **structural** — `AboutThisData.svelte` lines 100-103: derive "Tracked for N geographies" from `distinct(rows[].entity_id)`, not from `series_spec.expected_geographies`. Verify in browser per CLAUDE.md §13.
3. **behavioural** — `_pending_periods` in [backend/yen_gov/inventory/derive.py#L145](backend/yen_gov/inventory/derive.py#L145): rewrite as period-only set diff. Delete the geo cross-product. Add the test that catches the nuclear-in-Goa case (unit-tier in `backend/tests/test_inventory_derive.py`): indicator with rows covering 8 of 35 states + no `expected_geographies` → `pending_periods == []`.
4. **behavioural** — re-derive all 110 inventories; assert no artifact byte-changes EXCEPT the publisher-bounded family (nuclear, coal, marine fisheries, major ports) whose phantom-pending vanishes. Likely a one-shot tool: `tools/recompose_inventories.py`.
5. **observation period** (1-2 ingest cycles, ~2 weeks of real use). Watch /data-completeness for honest signal.
6. **structural** — schema v4.0: drop `expected_geographies` outright; `tools/bump_indicator_schema_to_current.py --strip-expected-geographies` removes the field from all artifacts in one commit.

### Two UI affordances for coverage (Hans-authored)

Not the same component for both shapes:

- **Publisher-bounded** (nuclear, coal, ports, fisheries, mining): one-sentence **"Publisher universe"** chip. Example for nuclear: *"Reported for 22 states/UTs as of March 2026. NPCIL allocates centrally-generated nuclear capacity via the regional grid; states without an allocation share are not listed by CEA. Updated monthly."*
- **Constitutionally-universal** (population, GSDP, NFHS, fiscal): **"Pending releases"** list. Example for GSDP: *"Reported for 33 of 36 states/UTs through FY 2023-24. Telangana series begins FY 2014-15; Ladakh series begins FY 2019-20. Andhra Pradesh and West Bengal have not released FY 2023-24 yet."*

The schema does NOT need to encode which shape an indicator is — that's derivable from whether `expected_periods_inference.basis ∈ {authored_from_publisher_catalogue, authored_from_source_schedule}`. If basis is authored, render the "Pending releases" list. Otherwise render the "Publisher universe" chip with a single observed-count sentence.

## Out of scope for the follow-up PR

- Editorial backfill of real `expected_periods_inference.basis = authored_from_publisher_catalogue` for cadenced indicators. Separate Hans-led arc; that's where `expected_periods` will actually start paying rent.
- Restructuring `coverage.spatial` (currently free-text "35 states/UTs"). Tempting, but no consumer asks. Speculative generality.
- Touching `unavailable_periods` semantics. Structure is fine; only the derivation math is wrong.

## Process lesson recorded

When a previous session's handover doc proposes a substantive design (here: `expected_geographies` + cross-product pending math), AND the user explicitly asks "did the relevant personas agree to this," THE HONEST answer matters more than defending the prior decision. The previous-session-agent shipped the design without running this debate. Three independent persona runs in parallel converged on the same direction — same answer the user's gut had been giving for two sessions. Worth the parallel cost for any "what does this field MEAN" question. (Already in user-memory `lessons.md` after the `fetched_at` arc; this is a second data point for the same rule.)

## References

- Full Fowler audit: see session transcript (subagent run, 2026-05-16, "Audit expected_geographies/expected_periods", verdict MAKE-OPTIONAL v3.1 → REMOVE-IN-V4).
- Full Hans audit: see session transcript (verdict REFRAME-AS-NEGATIVE-SPACE in v4).
- Full Max audit: see session transcript (verdict ADOPT-OWID-PATTERN; drop both to optional in v4).
- Folded-indicator schema: [datasets/schemas/indicator.schema.json](datasets/schemas/indicator.schema.json) v3.0.
- Universe decomposition (this PR, 2026-05-16): commit `b223a46`.
- Deferred-items batch (this PR, 2026-05-16): commit `630f7ed`.

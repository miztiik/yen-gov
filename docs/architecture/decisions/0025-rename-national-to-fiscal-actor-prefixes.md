# ADR-0025 — Rename `national_*` fiscal indicators to fiscal-actor prefixes

**Status**: Accepted
**Date**: 2026-05-14
**Deciders**: User; agent-deliberation included Fowler (Engineering), Hans (Governance), Gregor Hohpe (Architect)
**Supersedes / supersedes**: —

## Context

`datasets/indicators/in/fiscal/` contained eight indicators all prefixed `national_*`:

```
national_centre_transfers_total           ← from RBI Appendix T2 (State Finances)
national_devolution_central_taxes         ← T2
national_grants_from_centre               ← T2
national_gross_transfers                  ← T2
national_gross_fiscal_deficit             ← from RBI Appendix T1 (State Finances)
national_revenue_deficit                  ← T1
national_primary_deficit                  ← T1
national_primary_revenue_deficit          ← T1
```

The `national_` prefix was honest about *granularity* (country-level series, `entity_id="IN"`, one row per fiscal year) but silent about *which fiscal actor produced the number*. That silence misleads:

- The four T2 indicators are flows **from the Union Government to the states.** The Centre is the actor.
- The four T1 indicators are the **combined borrowing of all state governments aggregated to all-India.** The states (collectively) are the actor — emphatically NOT the Centre.

A reader scanning indicator IDs would reasonably assume `national_gross_fiscal_deficit` is the *Centre's* GFD (the headline "India's fiscal deficit" number that dominates Budget commentary). It is not. It is the all-states-combined GFD. This is a Factfulness Blame-instinct trap baked into the data architecture itself.

A schema-validation pass would never catch this — every artifact validates fine. The defect is semantic, in the names. By yen-gov's Holy Law #6 (no hardcoded magic), names that hide their meaning are a structural problem (Holy Law #5 — fix structurally).

## Decision

Rename all eight indicators to make the fiscal actor explicit in the slug. Two patterns, one per actor:

| Old | New |
| --- | --- |
| `fiscal/national_centre_transfers_total` | `fiscal/centre_transfers_to_states_net` |
| `fiscal/national_devolution_central_taxes` | `fiscal/centre_transfers_to_states_tax_devolution` |
| `fiscal/national_grants_from_centre` | `fiscal/centre_transfers_to_states_grants` |
| `fiscal/national_gross_transfers` | `fiscal/centre_transfers_to_states_gross` |
| `fiscal/national_gross_fiscal_deficit` | `fiscal/states_combined_gross_fiscal_deficit` |
| `fiscal/national_revenue_deficit` | `fiscal/states_combined_revenue_deficit` |
| `fiscal/national_primary_deficit` | `fiscal/states_combined_primary_deficit` |
| `fiscal/national_primary_revenue_deficit` | `fiscal/states_combined_primary_revenue_deficit` |

The two prefixes are deliberately patterned:

- `centre_transfers_to_states_*` — the four Centre→States transfer flows. The `_to_states_` infix prevents a future indicator like `centre_transfers_to_psu_*` from collapsing into the same namespace.
- `states_combined_*` — the four states-aggregate fiscal balances. The word **combined** matches RBI's own terminology in the *State Finances: A Study of Budgets* publication (which uses "All States" / "Combined" headers); we deliberately avoided **aggregate** because in Indian fiscal usage "aggregate" often denotes Centre+States *consolidated*, which is exactly NOT what these series are. The eight-indicator sibling group lexicographically clusters under the new prefix, which the old one did not.

The internal slug-segment word order is **actor → action → object → attribute** (`centre_transfers_to_states_net`), not English noun order (`net_centre_transfers_to_states`). Sort order then groups by actor first, which is what a citizen scanning a topic catalogue actually wants.

No schema change in this commit. The schema stays at v1.3. The concept doc that explains the naming pattern is [docs/concepts/fiscal-actor-naming.md](../../concepts/fiscal-actor-naming.md).

## Rejected alternatives

### Alternative A — blanket rename `national_* → centre_*`

Rejected. This was the original plan. Discovery during execution: the eight indicators do NOT share a fiscal actor. Four are Centre-actor; four are states-aggregate. A blanket rename would have actively mislabelled the deficits as Centre's deficits — making the citizen confusion *worse*, not better.

### Alternative B — keep `national_` and add a typed `fiscal_actor` enum field (Gregor Hohpe's recommendation)

Rejected by user. The proposal was to keep slugs as-is and add `indicator.fiscal_actor: "centre" | "states_combined" | "union" | "consolidated"` to the schema (v1.4 minor bump), letting the UI render an "Actor: States (combined)" pill alongside the title. This is structurally cleaner — the actor becomes a queryable field rather than a parser-prone substring of the slug.

Why overruled:

- Slugs are the most-frequent surface — they appear in URLs, log lines, fixture filenames, copy-paste in Slack, error messages. A typed field that's three layers down in JSON helps tools, not citizens.
- The frontend has zero references to these eight IDs today. There is no consumer that would benefit from a typed field RIGHT NOW; there is one consumer (the citizen reading the slug) who benefits from honest names IMMEDIATELY.
- Adding both — typed field AND honest slug — is the long-term endpoint, but each step should pay its own way. Slug rename pays now; typed field pays when we have a UI control that sorts/groups by actor. That's a Step C concern, not a Step B concern.
- Fowler's call: "the rename IS the structural fix; the typed field is the next refactor, not a substitute for this one."

### Alternative C — defer the rename, ship the new indicators with the new prefix and leave the old ones alone

Rejected. Two prefix conventions in the same directory permanently is worse than one transition. The rename is small (~100 substitutions across 21 files, atomic commit) and it is the kind of correction that compounds in cost the longer it waits — every new piece of code, doc, or test that references the old IDs is debt to repay later.

## Consequences

**Immediate:**

- Eight `git mv` operations on `datasets/indicators/in/fiscal/`.
- ~100 string substitutions across 21 files (adapters, parsers, tests, reference catalogues, dataset artifacts, four docs).
- Test suite stays green (302 / 1 baseline; one pre-existing flaky test unrelated).
- Schema unchanged (still v1.3).
- Frontend untouched (no references existed).

**Follow-ups recorded:**

- The Union (Centre's own) deficit indicators are absent. This rename names the actor "Centre" only as a benefactor (transfers OUT) and the actor "states_combined" as the borrower. The Centre's own borrowing (gross fiscal deficit ~5.6% of GDP in FY24, larger than states-combined ~3.2%) is missing from the data architecture. RBI HBS-IE Table 89 "Key Deficit Indicators of the Central Government" is the source. Tracked in [TODO/SOCIO-ECONOMIC-EXPANSION.md](../../../TODO/SOCIO-ECONOMIC-EXPANSION.md) §Open gap. Until that ships, any frontend page surfacing the four `states_combined_*_deficit` indicators MUST carry the caveat copy specified in that TODO entry — otherwise the data architecture continues to misframe responsibility.
- The schema v1.4 bump (introducing the `composes` field for facetted indicators) deferred to Step C alongside the typed-actor field if/when we add it.
- Verify RBI's exact terminology in the *State Finances* 2024-25 volume — we picked "combined" over "aggregate" on Hans's call, but should sanity-check against the actual cover page when next pulling that PDF.

**Chart-trap warning** (raised by Hans, captured in the concept doc): the four `centre_transfers_to_states_*` indicators are NOT independent series. They are one envelope decomposed:

- `_net = _gross − loan_recoveries`
- `_gross ≈ _tax_devolution + _grants + loans`

A naive stacked-bar chart that places `_net`, `_tax_devolution`, `_grants`, and `_gross` side by side lets a reader double-count. Any visualisation that groups these MUST use the decomposition explicitly (gross as the total, devolution + grants + loans as the parts, net as a separately-labelled "after recoveries" reference line) or pick one and only one for the headline view.

## See also

- [docs/concepts/fiscal-actor-naming.md](../../concepts/fiscal-actor-naming.md) — naming pattern + chart-trap warning, citizen-readable.
- [docs/architecture/backend/sources-rbi-appendix-national.md](../backend/sources-rbi-appendix-national.md) — Centre→States transfers adapter.
- [docs/architecture/backend/sources-rbi-appendix-deficits.md](../backend/sources-rbi-appendix-deficits.md) — states-combined deficits adapter.
- [TODO/SOCIO-ECONOMIC-EXPANSION.md](../../../TODO/SOCIO-ECONOMIC-EXPANSION.md) §Open gap — Union deficit follow-up.

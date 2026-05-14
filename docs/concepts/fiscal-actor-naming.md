# Fiscal-actor naming pattern for indicator slugs

**Last Updated**: 2026-05-14

> A fiscal indicator's slug must answer two questions a citizen would ask of any number with a rupee sign on it: **whose money is this** and **what is the money doing**. Granularity ("national" vs "per-state") is the third question, and it lives in `entity_kind`, not the slug.

## The pattern

For any indicator whose value depends on which fiscal actor produced it (Centre, individual state government, all states combined, Centre + states consolidated), the actor name is the **first segment** after the topic prefix:

```
fiscal/<actor>_<flow>_<qualifier>
```

| Actor segment | Meaning | Example |
| --- | --- | --- |
| `centre_*` | The Union (Central) Government as the fiscal actor. | `fiscal/centre_transfers_to_states_net` |
| `state_*` | A single state government's own number (per-row entity is the state). | `fiscal/state_own_tax_revenue_inr_crore` |
| `states_combined_*` | All state governments aggregated to an all-India number (per-row entity is `IN`). | `fiscal/states_combined_gross_fiscal_deficit` |
| `union_*` | Reserved for the Union Government's *own* fiscal balances (deficit, revenue, expenditure) — distinct from `centre_*` which is reserved for flows from Centre to other actors. | *(planned — see TODO/SOCIO-ECONOMIC-EXPANSION.md §Open gap)* |
| `consolidated_*` | Reserved for Centre + states combined (the "general government" view in IMF/IFS terminology). | *(none yet)* |

**Granularity is NOT in the slug.** A series whose `entity_kind` is `country` is not labelled `national_*`; the data model already says `entity_kind: "country"`. Repeating it in the slug is noise; worse, "national" sometimes connotes "aggregate of states", sometimes "Union Government", sometimes "country-as-subject-of-comparison" — three different things. The actor segment names *who*, the data model says *at what granularity*, and there is no overlap.

## Why two distinct prefixes for the Union — `centre_*` and `union_*`?

In Indian public-finance language the words "Centre" and "Union" are interchangeable when describing the actor (both mean the Government of India). yen-gov uses them with a deliberate domain split inside slugs:

- `centre_*_to_states_*` — the **flow** verb. Used when the indicator measures something the Centre sends OUT to other actors. The infix `_to_states_` (or `_to_psu_`, etc.) names the recipient. This makes it impossible to confuse a transfer with the Centre's own fiscal stance.
- `union_*` — the **balance** noun. Used when the indicator measures the Union Government's own fiscal position (Union GFD, Union revenue deficit, Union total expenditure). No `_to_*` infix because there is no second actor; the number is purely about the Union's own books.

This split prevents a future bug: a contributor adding "Union Government's gross fiscal deficit" would, under a one-word convention, be tempted to call it `centre_gross_fiscal_deficit` — which sits awkwardly next to `centre_transfers_to_states_net`. Reading the two together suggests the deficit is *also* a transfer, which it is not. Two prefixes keep the two concepts on different shelves.

## Why `states_combined_*` and not `states_aggregate_*` or `national_*`?

- **Not `national_*`**: the historical mistake (see ADR-0025). It conflates granularity (one row per FY) with actor (states, in this case) and lets readers default-assume "Centre".
- **Not `states_aggregate_*`**: in Indian fiscal usage "aggregate" is a loaded word — RBI itself uses "**Aggregate Public Finances**" to mean *Centre + states consolidated*, which is exactly NOT what these series measure. Calling our states-combined series "aggregate" would import that wrong connotation.
- **`states_combined_*`**: matches the cover-page terminology of RBI's *State Finances: A Study of Budgets* (which our adapters parse) — the publication uses "All States" and "Combined" interchangeably for the all-India sum-of-state-governments view. This is the language the upstream uses; using it ourselves keeps the lineage transparent.

## Chart-trap warning — the four `centre_transfers_to_states_*` indicators are NOT independent

The four Centre→States transfer indicators are one fiscal envelope decomposed four ways:

```
_gross  ≈  _tax_devolution  +  _grants  +  loans
_net    =  _gross           −  loan_recoveries
```

| Indicator | What it is | Relation to the others |
| --- | --- | --- |
| `centre_transfers_to_states_gross` | Total resources flowing OUT from Centre to states in the year. | The envelope total. |
| `centre_transfers_to_states_tax_devolution` | States' share of central tax pool (Finance Commission formula). | Largest component of `_gross`. |
| `centre_transfers_to_states_grants` | Discretionary + scheme grants to states. | Second component of `_gross`. |
| `centre_transfers_to_states_net` | `_gross` minus loan repayments / interest the Centre claws back from states the same year. | The "what actually stays with states" figure citizens care about. |

A stacked bar chart that puts `_gross`, `_tax_devolution`, `_grants`, and `_net` side by side lets a reader visually add four numbers that already overlap, double- or triple-counting the same rupees.

**Visualisation rule.** Any chart that surfaces more than one of these four MUST either:

1. Use the decomposition explicitly — show `_gross` as the totalled bar with `_tax_devolution` + `_grants` + loans as its stacked components, and `_net` rendered separately as a reference line ("after Centre's loan recoveries: ..."). The decomposition relationship is part of the chart's title or caption.
2. Or pick exactly one of the four as the headline (most pages should pick `_net` — it is the figure citizens actually feel) and link to the other three as drill-downs.

The same rule applies in reverse for `states_combined_*_deficit`: the four deficit indicators are derived from the same accounting identity (GFD = RD + capital deficit; PD = GFD − interest; PRD = RD − interest). They are *related views* of state finances, not four independent measures. A chart that shows all four side by side without explaining the relationship invites the reader to "add them up", which is not meaningful.

## Sort order, namespace clustering, the small mechanical wins

A consequence — not a goal but a happy by-product — of putting the actor first is that lexicographic sort groups indicators by actor. Reading the catalogue alphabetically now produces:

```
centre_transfers_to_states_grants
centre_transfers_to_states_gross
centre_transfers_to_states_net
centre_transfers_to_states_tax_devolution
state_grants_in_aid_inr_crore
state_own_tax_revenue_inr_crore
states_combined_gross_fiscal_deficit
states_combined_primary_deficit
states_combined_primary_revenue_deficit
states_combined_revenue_deficit
union_*  (when added)
```

…instead of the previous random scatter of `national_*` interleaved with `state_*`. A grep for "what does the Centre do" returns four lines that all start with `centre_`. A grep for "what is the states-combined fiscal stance" returns four lines that all start with `states_combined_`. The slug structure does the work the topic catalogue used to have to do prose-style.

## See also

- [ADR-0025 — Rename `national_*` fiscal indicators to fiscal-actor prefixes](../architecture/decisions/0025-rename-national-to-fiscal-actor-prefixes.md) — the decision and its rejected alternatives.
- [docs/architecture/backend/sources-rbi-appendix-national.md](../architecture/backend/sources-rbi-appendix-national.md) — `centre_transfers_to_states_*` adapter.
- [docs/architecture/backend/sources-rbi-appendix-deficits.md](../architecture/backend/sources-rbi-appendix-deficits.md) — `states_combined_*_deficit` adapter.
- [TODO/SOCIO-ECONOMIC-EXPANSION.md](../../TODO/SOCIO-ECONOMIC-EXPANSION.md) §Open gap — when `union_*_deficit` ships and what to caveat in the meantime.

# 2026-06-15 UX: MCC seizures card + 2014 MP affidavit panel — handover

**Last Updated**: 2026-06-15
**Parent plan**: [TODO/20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md) (Row D)
**Branch**: `feat/2014-affidavit-ux-and-seizures-card`
**Base**: `feat/2014-ls-affidavit-enrichment` (Row B PR #1050; merge-train target)
**PR**: <pending — to be filed against Row B head>

## 1. Scope

Frontend-only PR. Surfaces TWO new citizen-facing UX elements over data ingested by Rows A + B of the three-ephemeral-ingests plan:

1. **Election-period seizures card** (Row A consumer): renders on the national election surface (`/t/elections/general-2019`) and per-state election surface (`/<state>/elections/general-2019`). Sources `datasets/elections/parliament/election=2019/mcc_seizures.csv`. ONE card per parent plan §5.D.
2. **MP affidavit panel** (Row B consumer): renders on the Parliament constituency drill-down (`/<state>/elections/general-2014/<pc>`) when a winner row exists in the 2014 candidacies CSV with non-empty self-declared affidavit fields. Sources `datasets/elections/parliament/state=<slug>/election=2014/candidacies.csv` (Row B output).

Row C of the parent plan (AC affidavit ingest) is BLOCKED-NEEDS-SIGNOFF (see plan §0.7 scope-change ledger); not in this PR.

## 2. Files touched

### New (11)

- `frontend/src/lib/elections/election-seizures-model.ts` — pure projection helpers (~250 lines)
- `frontend/src/lib/elections/election-seizures-model.test.ts` — 24 vitest tests
- `frontend/src/lib/elections/election-seizures-loader.ts` — DuckDB-WASM loader (~70 lines)
- `frontend/src/lib/elections/ElectionSeizuresCard.svelte` — card component (~410 lines)
- `frontend/src/lib/parties/EntityProfilePanel.svelte` — generic profile dl/dt/dd panel (~90 lines)
- `frontend/src/lib/parties/EntityProfilePanel.test.ts` — 8 vitest source-pin tests
- `frontend/src/lib/elections/pc-affidavit-2014-loader.ts` — self-contained loader (~165 lines; per user-memory PR #1027 rule, NOT a resolver-callback loader)
- `frontend/src/lib/elections/mp-affidavit-model.ts` — pure projection helpers (~115 lines)
- `frontend/src/lib/elections/mp-affidavit-model.test.ts` — 16 vitest tests
- `frontend/e2e/general-2019-seizures.spec.ts` — 2 Playwright e2e tests
- `frontend/e2e/general-2014-mp-panel.spec.ts` — 2 Playwright e2e tests

### Edited (3 + 1 doc)

- `frontend/src/routes/NationalElection.svelte` — mount `<ElectionSeizuresCard event_id={event} />` after Alliance totals when `event ∈ {general-2019}`. No `state_slug` prop (national rollup).
- `frontend/src/routes/StateElection.svelte` — mount `<ElectionSeizuresCard event_id={event} state_slug={params.state} />` after Alliance totals when `event ∈ {general-2019}`.
- `frontend/src/routes/Constituency.svelte` — mount `<EntityProfilePanel entity_kind="mp" ... />` inside the resolved-PC-winner branch when (`event = general-2014`, `kind = pc`, eci_no resolved, affidavit rows non-empty).
- `TODO/20260614-three-ephemeral-ingests-plan.md` — §0.7 scope-change ledger row for Row C contract-gap surface; Status Reckoner Row C flipped to BLOCKED-NEEDS-SIGNOFF.

## 3. Design notes

- **Seizures card**: ONE component per parent plan §5.D. Picker chrome surfaces 6 categories (Total ₹ / Cash / Liquor / Drugs / Precious metals / Freebies); the "other" enum from the CSV renders as "Freebies" citizen-side (parent plan §0.3 D3 citizen-honesty framing). Inline Value/Quantity toggle appears only when the active category has a physical-quantity facet (liquor/drugs/metals). Publisher's `total_seizure_inr_crore` is rendered verbatim — components never re-summed (parent plan §0.3 D3). Headline shows `<category> on <date>: <value> <unit>`. Choropleth defaults to the national 36-state spine via `GeoChoropleth` + `boundaries/in/states/all.topojson` (feature_key=`State_LGD`); state-filter narrows the rollup numbers only (citizen always sees the national context per parent plan §0.3 J3). Sparkline is plain inline SVG (no D3 dep).
- **MP affidavit panel**: Generic `EntityProfilePanel` component (intended for reuse on MLA / party / donor surfaces in later PRs) consumes a `readonly ProfileRow[]` and renders `<dl>/<dt>/<dd>`. Blank rows dropped at the model layer. Loader is **self-contained per user-memory PR #1027 rule** — imports `parties` view-model + `states` view-model internally rather than taking resolver callbacks; the citizen never sees a raw ID. Amber banner per parent plan §0.3 B3 ("Self-declared at nomination, not adjudicated.") + provenance line ("Self-declared in Form 26 affidavit at nomination, 2014. Source: ECI / MyNeta.").
- **Svelte 5 trap avoided**: card prop is named `state_slug` (NOT `state`) to avoid shadowing the `$state()` rune in the destructured `$props()`.
- **Slug→title fallback** (user-memory PR #1027): `titleCaseSlug` in the seizures card lowercases connectors `{and, of, the, in}` when `idx > 0` so the scope label reads "Jammu and Kashmir only" not "Jammu And Kashmir only".

## 4. Acceptance gates

### G1 — backend validate

```
python -m yen_gov validate --root .
```

Not run; pure-frontend PR, no datasets touched.

### G2 — pytest

Not run; pure-frontend PR, no Python touched.

### G3 — `bun run check` (TypeScript / Svelte)

Pre-existing repo errors only (14 errors: all in `src/contracts/g5-bulk.test.ts` plus a11y warnings in `Matrix.svelte` / `Treemap.svelte` / `CirclePack.svelte`). **Zero errors from Row D files**.

### G4 — `bun run test` (vitest)

- **Row D scope** (48/48 green): `election-seizures-model.test.ts` (24) + `EntityProfilePanel.test.ts` (8) + `mp-affidavit-model.test.ts` (16).
- **Full repo** (3464 passed): 2 flaky-timeout failures in `party-colour-import-allowlist.test.ts` (3157ms) + `state-wards-registry-coverage.test.ts` (1499ms). Both PASS in isolation with `--testTimeout=60000` (verified). Pre-existing parallel-run timeout flake; not Row D regression.

### G5 — §13 browser smoke (MANDATORY per CLAUDE.md)

Dev server started on `localhost:5174`. Four URLs probed; all four pass:

#### Probe 1 — `http://localhost:5174/t/elections/general-2019` (national)

```
data-testid election-seizures-card        : mounted
data-testid election-seizures-picker      : 6 options (Total ₹ / Cash / Liquor / Drugs / Precious metals / Freebies)
data-testid election-seizures-headline    : "Freebies on 07 Apr: 35.4 INR crore" (after Freebies probe; default = Total ₹ on fresh page)
data-testid election-seizures-map         : mounted with 6 legend ticks (0.00, 3.03, 6.06, 9.08, 12.11, 15.14)
data-testid election-seizures-date-slider : 29 Mar - 07 Apr (range slider, value=9)
data-testid election-seizures-sparkline   : mounted (label "all India daily")
source attribution                        : "Election Commission of India (MCC press notes) (as of 2019 general election, 2019-03-29 to 2019-04-07)"
loadSeizures('general-2019')              : 360 rows (probed in-page)
```

#### Probe 2 — `http://localhost:5174/maharashtra/elections/general-2019` (state)

```
data-testid election-seizures-card                : mounted
data-state-slug attribute                         : "maharashtra"
scope label                                       : "Maharashtra only"
data-testid election-seizures-headline (default)  : "Total ₹ on 07 Apr: 96.3 INR crore"
data-testid election-seizures-headline (Cash)     : "Cash on 07 Apr: 30.6 INR crore"  (after click on data-category=cash)
data-testid election-seizures-picker-option       : 6 options
data-testid election-seizures-map                 : mounted
data-testid election-seizures-sparkline           : mounted
data-testid election-seizures-error               : 0 (no error)
```

#### Probe 3 — `http://localhost:5174/maharashtra/elections/general-2014/buldhana` (positive affidavit)

```
data-testid constituency-pc-winner                : mounted (SHS / JADHAV PRATAPRAO GANPATRAO / margin 16.31%)
data-testid entity-profile-panel                  : mounted
data-entity-kind attribute                        : "mp"
heading                                           : "About this MP (2014 declaration)"
data-testid entity-profile-panel-amber            : 1 ("Self-declared at nomination, not adjudicated. Read alongside other public records.")
data-testid entity-profile-panel-provenance       : 1 ("Self-declared in Form 26 affidavit at nomination, 2014. Source: ECI / MyNeta.")
rows rendered                                     : 5
  - Education            : 12th Pass
  - Criminal cases declared : 2
  - Declared assets      : 3.60 INR crore
  - Declared liabilities : 0.07 INR crore
  - Election expense     : 38.9 INR lakh
rows dropped (blank in CSV) : Sex, Age at nomination, Profession
```

#### Probe 4 — `http://localhost:5174/maharashtra/elections/general-2024/buldhana` (negative)

```
data-testid constituency-pc-winner  : mounted (SHS / JADHAV PRATAPRAO GANPATRAO; margin 2.66%)
data-testid entity-profile-panel    : 0 (correctly NOT mounted; 2024 affidavits not yet ingested)
```

## 5. Forward gaps

- **2024 affidavit ingest**: deferred. The `EVENTS_WITH_AFFIDAVITS` set in `Constituency.svelte` is `{general-2014}`. To extend to 2019 / 2024, add the event_id AND ensure `datasets/elections/parliament/state=*/election=<year>/candidacies.csv` carries the 4 affidavit columns (assets/liabilities/criminal_cases/election_expense_inr) populated for that year (Row B ingested 2014 only).
- **2014 affidavit ingest for non-MH states**: panel is event-gated, not state-gated; it renders for any state where Row B has populated rows. Verify by visiting other 2014 PCs once the merge train lands.
- **Per-event seizures ingest**: `EVENTS_WITH_SEIZURES` set is `{general-2019}` because Row A ingested only the 2019 vintage. Extending to 2024 requires adding the event_id and the corresponding `datasets/elections/parliament/election=2024/mcc_seizures.csv` ingest (NOT this PR).
- **AC pages**: AC-equivalent affidavit panel is blocked on Row C (parent plan §0.7); no UX surface here yet.
- **EntityProfilePanel reuse**: the `entity_kind="mp"` variant lands now; future PRs can mount `entity_kind="mla"` / `"party"` / `"donor"` over the same component once the corresponding loader + model land.

## 6. References

- [TODO/20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md) — parent plan (Rows A + B + C + D)
- [CLAUDE.md §13](../CLAUDE.md) — §13 mandatory browser smoke
- User memory `lessons-2026-06-12-yen-gov-pc-tile.md` — view-model loader self-containment rule (PR #1027)
- User memory — DuckDB-WASM `SUM(BIGINT)` HUGEINT-as-string trap (PR #1024); does NOT apply here (no SUMs in seizures or affidavit loaders).

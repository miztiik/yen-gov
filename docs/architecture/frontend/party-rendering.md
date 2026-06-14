# Party rendering — PartyPill contract + `/parties/<slug>` link doctrine

**Last Updated**: 2026-06-13
**Status**: Active citizen contract. PR-0 of [TODO/20260612-party-rendering-and-party-pages-plan.md](../../../TODO/20260612-party-rendering-and-party-pages-plan.md) shipped this doc; PRs 1-4 of the same plan execute against it.

This page is the binding contract for how political parties render across yen-gov citizen surfaces. It sits alongside [colours.md](colours.md) (the 3-tier party-colour resolver) and [url-grammar.md](url-grammar.md) (ADR-0053, the `/parties/<slug>` route grammar). The colour resolver and URL grammar are the two underlying capabilities; THIS doc is the rule that says every surface uses them consistently.

## The single rule

Every citizen-facing party reference renders via the `<PartyPill>` component AND links to `/parties/<slug>` unless the reference falls into one of four explicit exclusions (named below). The Tier-A contract test at [frontend/src/contracts/party-rendering.test.ts](../../../frontend/src/contracts/party-rendering.test.ts) (lands in PR-2 of the plan-doc) walks every `.svelte` file under `frontend/src/routes/` and `frontend/src/lib/charts/` and asserts the rule. When the test goes red the fix is to adopt PartyPill, not to add an exception.

## PartyPill component

[frontend/src/lib/party-pill/PartyPill.svelte](../../../frontend/src/lib/party-pill/PartyPill.svelte) is the SINGLE coloured party-rendering primitive. Four treatment tiers (selected by the [3-tier colour resolver](colours.md)):

- **Anchor** — full-bleed coloured pill body. Ink picked by `pickInkForFill(hex)` for contrast. Reserved for the ~12 hand-anchored major parties (BJP saffron, INC blue, DMK red, AIADMK green, CPI red, CPIM red, AAP blue, etc.).
- **Brand** — paper-neutral pill body + 2px coloured ring. Used when the party row carries a `brand_colour` from `datasets/data/entities/parties.csv` but is NOT an anchor; the ring identifies the party while the body stays paper-neutral (resolver doctrine: brand colour is never full chrome).
- **Fallback** — paper-neutral pill body + small coloured swatch chip + label. Used when no `brand_colour` is present; the swatch is hash-derived from `party_id` (deterministic; reserves hue bands occupied by anchors). The label is always present; a bare swatch is never allowed.
- **Neutral** — `--party-neutral` body + `--party-neutral-text` ink. The "Unknown party" affordance for null `party_id` or unresolved rows.

Click semantics: when the pill carries an `onclick` prop it renders as a `<button>` (chart-affordance like the existing PartyBar mute toggle); when it does NOT, it renders as a `<span>` that the caller MAY wrap in `<a href={link.party(party_id)}>`. Both shapes are valid per the rule above.

## Tooltip (PR-1 of the plan-doc)

The PartyPill gains a hover/focus/click-pin popover landed in PR-1 of the plan-doc. The tooltip renders fields from parties.csv:

- **Header**: party symbol glyph (only when `symbol_asset` is non-null per the missing-symbol rule below) + party short in semi-bold.
- **Body**: party full name; founded year (only when `founded_year` is populated); dissolved year (only when `dissolved_year` is populated); recognition badge (lucide `landmark` icon); name in native script (italic secondary line, only when `name_native_script` is populated).
- **Footer**: wiki external-link icon (lucide `external-link`) when `wikipedia` is populated.

The tooltip does NOT render a "Chief / President" line — parties.csv has no `chief` column today and synthesising one would be dishonest (Max section 3 of the plan-doc). Adding the field is a separate Wikidata P488 ingest PR.

Interaction model: hover-open + focus-open + click-pin. Esc closes any unpinned tooltip. Click-outside dismisses pinned tooltips. The popover is hand-rolled CSS-positioned (mirroring [ChartTooltip.svelte](../../../frontend/src/lib/ChartTooltip.svelte)'s fixed-viewport-edge-clamp pattern) — no `@floating-ui` dependency. The tooltip is interactive (`pointer-events: auto`) so the wiki link inside it is clickable.

UNK is the only party that does NOT open a tooltip on hover — UNK is operator telemetry, not a citizen entity, and `link.party("parties.IN.UNK")` returns `null`.

## Missing-symbol rule

When a party's `symbol_asset` cell in parties.csv is blank, the surface MUST render NOTHING in the symbol's place — no placeholder image, no initials avatar, no coloured circle. Per the user (2026-06-12): "show symbol if it is there; if not, remove the symbol — don't show placeholder." The pill collapses gracefully to label-only; the tooltip header left-aligns the short text. This already matches [PartySymbolGlyph.svelte](../../../frontend/src/lib/PartySymbolGlyph.svelte)'s default `fallback="silent"` mode.

This rule applies to every surface: PartyPill, tooltip header, WinnerBadge, AcStackedBar, party detail page header card, parties index rows.

## Explicit exclusions (the four rule-out cases)

Four classes of party reference do NOT render via PartyPill or carry a `/parties/<slug>` link. Each exception is named here so the contract test can carry an allowlist comment for it rather than silently degrade.

1. **KPI numerators inside sentences.** Plain numeric text like "INC: 99 of 543 seats" inside a one-line summary. The party token here is part of a sentence, not a navigable affordance; pill-wrapping every party mention in body prose would noise the page. The party detail page surfaces its own party identity in the header card; downstream sentence-text references stay plain text.

2. **Sort column headers in compare tables.** The `<th>` "INC winner" / "DMK winner" column headers in compare-elections sortable tables are NOT party references — they are table-column captions naming the side of the comparison. Wrapping them in PartyPill would suggest each column header is a navigable link, which it isn't.

3. **Breadcrumb labels.** The breadcrumb leaf on `/parties/<slug>` renders as title-cased text ("INC" / "Bjp" / "Cpi-m") to match the URL slug, not as a self-referential PartyPill. (The breadcrumb leaf is the page you're already on; clickability is wrong.)

4. **Tooltip body itself.** The PartyPill tooltip body renders the party's own metadata (short, full, founded, etc.) as plain text styled inside the popover card; it does NOT contain another PartyPill (that would be infinite-recursion-shaped and noisy).

Any other "I need to render a party here without using PartyPill" case is a regression. File an issue + a STOP-AND-SURFACE rather than expanding this list.

## URL grammar (ADR-0053)

Per [url-grammar.md ADR-0053](url-grammar.md#adr-0053-party-rendering-and-per-party-pages):

- Parties index at `/parties` (alphabetical + recognition filter + search; PartiesIndex.svelte, body lands in PR-3 of the plan-doc).
- Per-party detail at `/parties/<slug>` (header + KPIs + LS chart + VS chart + strongholds + metadata footer; Party.svelte, body lands in PR-4 of the plan-doc).
- Slug derivation: lowercased `party_id` tail with `_` -> `-` (via [`partyIdToSlug`](../../../frontend/src/lib/slug.ts)). Sentinel overrides: IND -> `independent`, NOTA -> `nota`, AC (Arunachal Congress) -> `arunachal-congress`, GOA (Goa party vs state slug) -> `goemcarancho-otrec-astro`, MAHAD (Mahakranti Dal vs Maharashtra AC) -> `mahakranti-dal`, JIND (party tail vs Haryana AC slug) -> `jind-party`. UNK -> NULL (no page).

Link builder: `link.party(party_id): string | null` from [links.ts](../../../frontend/src/lib/links.ts). Returns `null` for UNK and any falsy input; callers MUST handle null by skipping the `<a>` wrapper.

## Party detail data loading

The `/parties/<slug>` detail page reads the backend-derived party-page marts:

- `datasets/data/marts/party_pages/history.csv`
- `datasets/data/marts/party_pages/strongholds.csv`
- `datasets/data/marts/party_pages/manifest.csv`

The generator is `python -m yen_gov derive-party-pages --root .` and the implementation lives at `backend/yen_gov/canonical/derived/party_pages.py`. The mart is a reproducible read model over canonical electoral rows, not a source of truth. The browser MUST NOT read `datasets/data/datapoints/electoral/*.csv` for one party page; that corpus is large and belongs in backend precompute. Tier-B validation recomputes the mart input signature and fails when an electoral ingest changes the source CSVs without refreshing the mart.

Citizen methodology constraints: Parliament and Assembly stay separate; vote share is votes-weighted where vote totals are available; missing coverage is a gap, not zero; `parties.IN.IND` and `parties.IN.NOTA` keep their sentinel framing; alliance membership is not added to a party's own totals.

## See also

- [colours.md](colours.md) — the 3-tier party-colour resolver (anchor / brand / fallback) the PartyPill consumes.
- [url-grammar.md](url-grammar.md) — ADR-0053 (this contract's URL routing decision) + the 6-way disjointness invariant.
- [PartyPill.svelte](../../../frontend/src/lib/party-pill/PartyPill.svelte) — the rendering component.
- [PartySymbolGlyph.svelte](../../../frontend/src/lib/PartySymbolGlyph.svelte) — the party-election-symbol SVG primitive (used inside the tooltip header and on the per-party detail page).
- [TODO/20260612-party-rendering-and-party-pages-plan.md](../../../TODO/20260612-party-rendering-and-party-pages-plan.md) — the 5-PR plan-doc that authored this contract.
